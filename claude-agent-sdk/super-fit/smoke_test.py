"""Offline checks: exercises the FAQ search and every tool handler directly.

Runs no API calls and needs no API key, so use it after editing data/faqs.json to
confirm the knowledge base still loads and real customer questions retrieve the
entries you expect.

    python smoke_test.py
"""

from __future__ import annotations

import asyncio
import sys

from support_agent import faq_tools, knowledge

# Question a customer might type -> the FAQ id that should come back first.
EXPECTED_TOP_HIT = {
    "how much does a membership cost?": "MEM-001",
    "i want to cancel my membership": "MEM-002",
    "can i put my membership on hold while i travel": "MEM-003",
    "my card got declined": "BILL-002",
    "i got charged after i cancelled, i want my money back": "BILL-004",
    "how do i book a spin class": "CLS-001",
    "i missed a class am i penalised": "CLS-002",
    "what does a personal trainer cost": "PT-001",
    "are you open on sunday night": "FAC-001",
    "can i bring my girlfriend to the gym": "FAC-002",
    "do you have a swimming pool": "FAC-003",
    "the qr code at the door wont scan": "APP-001",
    "my son is 15 can he join": "POL-001",
    "i hurt my shoulder on the bench press": "POL-002",
}


def check_search() -> int:
    failures = 0
    print(f"Loaded {len(knowledge.all_faqs())} FAQs in {len(knowledge.categories())} categories.\n")

    for question, expected_id in EXPECTED_TOP_HIT.items():
        hits = knowledge.search(question)
        actual = hits[0].faq.id if hits else "NO MATCH"
        ok = actual == expected_id
        failures += 0 if ok else 1
        print(f"{'ok  ' if ok else 'FAIL'} {question!r} -> {actual} (expected {expected_id})")

    # An off-topic question should retrieve nothing, so the agent is forced to say
    # it does not know rather than answering from a weak match.
    off_topic = knowledge.search("what is the capital of France")
    print(f"\n{'ok  ' if not off_topic else 'FAIL'} off-topic question returns no hits")
    failures += 1 if off_topic else 0

    return failures


async def check_tools() -> int:
    failures = 0
    print("\nTool handlers:")

    result = await faq_tools.search_faqs.handler({"query": "freeze my membership"})
    ok = "MEM-003" in result["content"][0]["text"]
    print(f"{'ok  ' if ok else 'FAIL'} search_faqs returns the freeze policy")
    failures += 0 if ok else 1

    result = await faq_tools.get_faq.handler({"faq_id": "bill-001"})
    ok = "fortnightly" in result["content"][0]["text"]
    print(f"{'ok  ' if ok else 'FAIL'} get_faq is case-insensitive on the id")
    failures += 0 if ok else 1

    result = await faq_tools.get_faq.handler({"faq_id": "NOPE-999"})
    ok = result.get("is_error") is True
    print(f"{'ok  ' if ok else 'FAIL'} get_faq flags an unknown id as an error")
    failures += 0 if ok else 1

    result = await faq_tools.list_categories.handler({})
    ok = "memberships" in result["content"][0]["text"]
    print(f"{'ok  ' if ok else 'FAIL'} list_categories lists the categories")
    failures += 0 if ok else 1

    result = await faq_tools.escalate_to_human.handler(
        {"summary": "smoke test ticket", "reason": "verifying the escalation path"}
    )
    ok = "SF-" in result["content"][0]["text"] and not result.get("is_error")
    print(f"{'ok  ' if ok else 'FAIL'} escalate_to_human writes a ticket")
    failures += 0 if ok else 1
    if ok:
        print(f"     (appended to {faq_tools.ESCALATION_LOG})")

    result = await faq_tools.escalate_to_human.handler({"summary": "missing reason"})
    ok = result.get("is_error") is True
    print(f"{'ok  ' if ok else 'FAIL'} escalate_to_human rejects a missing reason")
    failures += 0 if ok else 1

    return failures


async def main() -> int:
    failures = check_search() + await check_tools()
    print()
    if failures:
        print(f"{failures} check(s) failed.")
    else:
        print("All checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
