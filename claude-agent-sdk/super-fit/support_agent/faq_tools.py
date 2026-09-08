"""Custom tools the support agent can call, exposed as an in-process MCP server.

Each `@tool` handler returns a `content` array - the exact text Claude reads back as
the tool result. Handlers return `is_error: True` on failure so Claude gets a message
it can act on (ask a follow-up, try another search) rather than a raw traceback.

Tool names reach Claude as `mcp__faq__<tool name>`, where `faq` is the key this
server is registered under in `ClaudeAgentOptions.mcp_servers`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from claude_agent_sdk import ToolAnnotations, create_sdk_mcp_server, tool

from . import knowledge

# Escalations are appended here as JSON Lines - one ticket per line, easy to tail
# or pipe into a real ticketing system later.
ESCALATION_LOG = Path(__file__).resolve().parent.parent / "data" / "escalations.jsonl"


def _text(message: str, is_error: bool = False) -> dict[str, Any]:
    """Wrap a string in the content-array shape every tool handler must return."""
    result: dict[str, Any] = {"content": [{"type": "text", "text": message}]}
    if is_error:
        result["is_error"] = True
    return result


def _business_info() -> dict[str, Any]:
    """Company details, or an empty dict if the knowledge base can't be read.

    Escalation has to keep working when the FAQ file is missing - that is precisely
    when a customer needs a human - so this degrades instead of raising.
    """
    try:
        return knowledge.business_info()
    except (OSError, ValueError, KeyError):
        return {}


def _format_hit(faq: knowledge.Faq, score: float | None = None) -> str:
    header = f"[{faq.id}] ({faq.category}) {faq.question}"
    if score is not None:
        header += f"  -- relevance {score:.1f}"
    return f"{header}\n{faq.answer}"


@tool(
    "search_faqs",
    "Search the Super Fit FAQ knowledge base for entries relevant to a customer's "
    "question. Pass the customer's own wording as the query. Optionally pass "
    "'category' to restrict the search and 'limit' (default 3) for how many entries "
    "to return. Returns the full answer text of each matching FAQ.",
    {"query": str},
    annotations=ToolAnnotations(
        title="Search FAQs",
        readOnlyHint=True,  # lets Claude run several searches in parallel
        openWorldHint=False,
    ),
)
async def search_faqs(args: dict[str, Any]) -> dict[str, Any]:
    # 'category' and 'limit' are left out of the schema (which makes every key
    # required) and read with .get() so they behave as optional parameters.
    query = str(args.get("query", "")).strip()
    if not query:
        return _text("No query supplied. Pass the customer's question as 'query'.", is_error=True)

    try:
        limit = max(1, min(int(args.get("limit", 3)), 10))
    except (TypeError, ValueError):
        limit = 3

    category = args.get("category") or None

    try:
        hits = knowledge.search(query, limit=limit, category=category)
    except FileNotFoundError as exc:
        return _text(f"Knowledge base unavailable: {exc}", is_error=True)

    if not hits:
        known = ", ".join(knowledge.categories())
        return _text(
            f"No FAQ matched '{query}'. The knowledge base only covers: {known}. "
            "Do not answer from general knowledge - tell the customer this needs a "
            "human, or call escalate_to_human if they want it handed over."
        )

    body = "\n\n".join(_format_hit(hit.faq, hit.score) for hit in hits)
    return _text(f"{len(hits)} FAQ match(es) for '{query}':\n\n{body}")


@tool(
    "get_faq",
    "Retrieve one FAQ entry verbatim by its id (for example 'BILL-002'). Use this "
    "when a search result referenced an id and you need its full text again.",
    {"faq_id": str},
    annotations=ToolAnnotations(title="Get FAQ by id", readOnlyHint=True, openWorldHint=False),
)
async def get_faq(args: dict[str, Any]) -> dict[str, Any]:
    faq_id = str(args.get("faq_id", "")).strip()
    try:
        faq = knowledge.get_by_id(faq_id)
        if faq is None:
            available = ", ".join(entry.id for entry in knowledge.all_faqs())
            return _text(f"No FAQ with id '{faq_id}'. Valid ids: {available}", is_error=True)
    except (OSError, ValueError, KeyError) as exc:
        return _text(f"Knowledge base unavailable: {exc}", is_error=True)
    return _text(_format_hit(faq))


@tool(
    "list_categories",
    "List the FAQ categories in the knowledge base and how many entries each holds. "
    "Use this to tell a customer what topics you can help with.",
    {},
    annotations=ToolAnnotations(title="List FAQ categories", readOnlyHint=True, openWorldHint=False),
)
async def list_categories(args: dict[str, Any]) -> dict[str, Any]:
    info = _business_info()
    try:
        lines = [f"{name}: {count} entries" for name, count in knowledge.categories().items()]
    except (OSError, ValueError, KeyError) as exc:
        return _text(f"Knowledge base unavailable: {exc}", is_error=True)
    return _text(
        "Super Fit FAQ categories:\n"
        + "\n".join(lines)
        + f"\n\nHuman support hours: {info.get('support_hours', 'unknown')}"
        + f"\nSupport email: {info.get('support_email', 'unknown')}"
    )


@tool(
    "escalate_to_human",
    "Hand the conversation to a human support agent. Use this when the FAQs do not "
    "cover the question, when the customer needs something done on their account "
    "(refunds, waiving a notice period, reversing a no-show, fixing account details), "
    "or when they ask for a person. Optionally pass 'customer_email' and 'urgency' "
    "(low, normal, high). Returns a ticket reference to give the customer.",
    {"summary": str, "reason": str},
    annotations=ToolAnnotations(
        title="Escalate to human agent",
        readOnlyHint=False,
        destructiveHint=False,  # creates a ticket; nothing is overwritten
        openWorldHint=True,
    ),
)
async def escalate_to_human(args: dict[str, Any]) -> dict[str, Any]:
    summary = str(args.get("summary", "")).strip()
    reason = str(args.get("reason", "")).strip()
    if not summary or not reason:
        return _text(
            "Both 'summary' (what the customer wants) and 'reason' (why it needs a "
            "human) are required.",
            is_error=True,
        )

    urgency = str(args.get("urgency", "normal")).lower()
    if urgency not in {"low", "normal", "high"}:
        urgency = "normal"

    ticket = {
        "ticket_id": f"SF-{uuid4().hex[:8].upper()}",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": summary,
        "reason": reason,
        "urgency": urgency,
        "customer_email": args.get("customer_email"),
    }

    try:
        ESCALATION_LOG.parent.mkdir(parents=True, exist_ok=True)
        with ESCALATION_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(ticket) + "\n")
    except OSError as exc:
        # Compose the failure so Claude tells the customer to email support rather
        # than silently claiming a ticket was raised.
        return _text(
            f"Could not record the escalation ({exc}). Tell the customer to email "
            f"{_business_info().get('support_email', 'support')} directly.",
            is_error=True,
        )

    info = _business_info()
    return _text(
        f"Escalation recorded as ticket {ticket['ticket_id']} ({urgency} urgency). "
        f"Give this reference to the customer and tell them a human agent will reply "
        f"during support hours ({info.get('support_hours', 'business hours')})."
    )


# The server runs inside this process - no subprocess, no separate MCP config file.
faq_server = create_sdk_mcp_server(
    name="faq",
    version="1.0.0",
    tools=[search_faqs, get_faq, list_categories, escalate_to_human],
)

# Pre-approved in ClaudeAgentOptions so these run without a permission prompt.
FAQ_TOOL_NAMES = [
    "mcp__faq__search_faqs",
    "mcp__faq__get_faq",
    "mcp__faq__list_categories",
    "mcp__faq__escalate_to_human",
]
