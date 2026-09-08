"""Loads the FAQ knowledge base and scores entries against a customer's question.

This is deliberately dependency-free: the FAQ set is small enough that a keyword
search with IDF weighting beats the complexity of a vector store. Swap the body of
`search` for an embedding lookup when the FAQ set outgrows a few hundred entries -
the tool layer in `faq_tools.py` won't need to change.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FAQ_FILE = DATA_DIR / "faqs.json"

# Words too common to carry signal in a support question. Chat questions are full of
# them ("am i", "do i need to", "hi, i just wanted to ask"), and without this list a
# rare-looking token like "am" outscores the words that actually matter.
STOPWORDS = frozenset(
    """a about am an and any anyone are as at be been being but by can cant cannot
    could did do does doing done dont for from get got had has have hi hello how i
    id if ill im in is it its ive just know like me my need no not of on or our
    please so some than thanks that the their them then there these they this to up
    us very want was we were what when where which who why will with would you
    your""".split()
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Faq:
    id: str
    category: str
    question: str
    answer: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class SearchHit:
    faq: Faq
    score: float


def _stem(token: str) -> str:
    """Crude suffix stripping so 'cancelled', 'cancelling', and 'cancel' all match.

    Not linguistically correct - it just has to fold a word and its inflections onto
    the same key. Trailing 'e' is always dropped so 'charge'/'charged' both land on
    'charg'.
    """
    if len(token) <= 3 or token[0].isdigit():
        return token

    for suffix in ("ing", "ed"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            token = token[: -len(suffix)]
            # "cancelled" -> "cancell" -> "cancel"
            if len(token) > 2 and token[-1] == token[-2] and token[-1] not in "aeiou":
                token = token[:-1]
            break
    else:
        if token.endswith("ies") and len(token) > 4:
            token = token[:-3] + "y"
        elif token.endswith("es") and len(token) > 4:
            token = token[:-2]
        elif token.endswith("s") and not token.endswith("ss") and len(token) > 3:
            token = token[:-1]

    if len(token) > 3 and token.endswith("e"):
        token = token[:-1]
    return token


def _tokenize(text: str) -> list[str]:
    return [
        _stem(t)
        for t in _TOKEN_RE.findall(text.lower())
        if t not in STOPWORDS and len(t) > 1
    ]


def _bigrams(tokens: list[str]) -> set[tuple[str, str]]:
    return set(zip(tokens, tokens[1:]))


@lru_cache(maxsize=1)
def _load() -> tuple[dict, tuple[Faq, ...]]:
    """Read and cache faqs.json. Raises if the file is missing or malformed."""
    if not FAQ_FILE.exists():
        raise FileNotFoundError(f"FAQ knowledge base not found at {FAQ_FILE}")

    raw = json.loads(FAQ_FILE.read_text(encoding="utf-8"))
    faqs = tuple(
        Faq(
            id=entry["id"],
            category=entry["category"],
            question=entry["question"],
            answer=entry["answer"],
            tags=tuple(entry.get("tags", [])),
        )
        for entry in raw["faqs"]
    )
    return raw.get("business", {}), faqs


def business_info() -> dict:
    """Company-level details (name, support hours, contact) from the knowledge base."""
    return _load()[0]


def all_faqs() -> tuple[Faq, ...]:
    return _load()[1]


def categories() -> dict[str, int]:
    """Category name -> number of FAQs in it, in knowledge-base order."""
    counts: dict[str, int] = {}
    for faq in all_faqs():
        counts[faq.category] = counts.get(faq.category, 0) + 1
    return counts


def get_by_id(faq_id: str) -> Faq | None:
    wanted = faq_id.strip().upper()
    return next((faq for faq in all_faqs() if faq.id.upper() == wanted), None)


# Capped so one rare word can't decide the ranking on its own. Without this, a
# question like "how do I book a spin class" ranks the entry that merely lists Spin
# above the one that explains booking, because "spin" appears in a single entry.
_MAX_IDF = 2.5


@lru_cache(maxsize=1)
def _idf() -> dict[str, float]:
    """Inverse document frequency, so 'membership' counts for less than 'dishonour'."""
    faqs = all_faqs()
    doc_count = len(faqs)
    seen: dict[str, int] = {}
    for faq in faqs:
        for token in set(_tokenize(f"{faq.question} {faq.answer} {' '.join(faq.tags)}")):
            seen[token] = seen.get(token, 0) + 1
    return {token: min(math.log(1 + doc_count / n), _MAX_IDF) for token, n in seen.items()}


# The question line is the entry's canonical statement of what it answers, so it
# outranks tags (mere synonyms) and the answer body (passing mentions).
_FIELD_WEIGHTS = (("question", 4.0), ("tags", 2.5), ("answer", 1.0))

# Word pairs are strong evidence: "charged after" separates "why was I charged after
# I cancelled" from the general refund policy, which shares every individual word.
_BIGRAM_BONUS = {"question": 5.0, "tags": 4.0}


@lru_cache(maxsize=None)
def _index(faq_id: str) -> dict:
    """Pre-tokenized fields for one FAQ, built once and reused across searches."""
    faq = get_by_id(faq_id)
    assert faq is not None
    question = _tokenize(faq.question)
    # Bigrams are taken within each tag, so "no show" and "day pass" stay distinct
    # instead of pairing the tail of one tag with the head of the next.
    tag_tokens = [_tokenize(tag) for tag in faq.tags]
    return {
        "question": set(question),
        "tags": {token for tokens in tag_tokens for token in tokens},
        "answer": set(_tokenize(faq.answer)),
        "question_bigrams": _bigrams(question),
        "tag_bigrams": set().union(*(_bigrams(t) for t in tag_tokens)) if tag_tokens else set(),
    }


def _score(faq: Faq, query_tokens: set[str], query_bigrams: set, idf: dict[str, float]) -> float:
    fields = _index(faq.id)

    score = 0.0
    for token in query_tokens:
        weight = idf.get(token, 0.5)  # unseen words still count a little
        for field, field_weight in _FIELD_WEIGHTS:
            if token in fields[field]:
                score += weight * field_weight
                break  # count each query term once, at its strongest field

    for bigram in query_bigrams:
        if bigram in fields["question_bigrams"]:
            score += _BIGRAM_BONUS["question"]
        elif bigram in fields["tag_bigrams"]:
            score += _BIGRAM_BONUS["tags"]

    return score


def search(query: str, limit: int = 3, category: str | None = None) -> list[SearchHit]:
    """Return the FAQs most relevant to `query`, best match first.

    Hits scoring below 20% of the best hit are dropped, so a vague question returns
    one or two entries rather than a long tail of weak matches.
    """
    tokens = _tokenize(query)
    query_tokens = set(tokens)
    if not query_tokens:
        return []

    query_bigrams = _bigrams(tokens)
    idf = _idf()
    candidates = all_faqs()
    if category:
        wanted = category.strip().lower()
        candidates = tuple(faq for faq in candidates if faq.category.lower() == wanted)

    hits = [SearchHit(faq, _score(faq, query_tokens, query_bigrams, idf)) for faq in candidates]
    hits = [hit for hit in hits if hit.score > 0]
    hits.sort(key=lambda hit: (-hit.score, hit.faq.id))

    if not hits:
        return []

    cutoff = hits[0].score * 0.2
    return [hit for hit in hits[:limit] if hit.score >= cutoff]
