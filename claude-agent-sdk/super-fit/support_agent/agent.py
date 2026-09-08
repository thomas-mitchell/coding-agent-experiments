"""Agent configuration: turns the tools and prompt into ClaudeAgentOptions."""

from __future__ import annotations

import os

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from .faq_tools import FAQ_TOOL_NAMES, faq_server
from .prompts import build_system_prompt

# Sonnet 5 is the sensible default for support: fast, cheap enough to run per-message,
# and strong at following the grounding rules in the system prompt. Override with
# SUPER_FIT_MODEL=claude-opus-5 for harder reasoning.
DEFAULT_MODEL = os.environ.get("SUPER_FIT_MODEL", "claude-sonnet-5")


def build_options() -> ClaudeAgentOptions:
    """Options for a customer-facing agent that can only touch the FAQ tools."""
    return ClaudeAgentOptions(
        system_prompt=build_system_prompt(),
        # In-process MCP server. The dict key 'faq' is what makes each tool's full
        # name mcp__faq__<tool>.
        mcp_servers={"faq": faq_server},
        # tools=[] removes every built-in (Read, Write, Bash, WebSearch...) from
        # Claude's context. A customer-facing bot has no business touching the disk.
        tools=[],
        # Pre-approve the FAQ tools so they run without a permission prompt...
        allowed_tools=FAQ_TOOL_NAMES,
        # ...and deny anything not pre-approved, rather than blocking on a prompt
        # nobody is there to answer.
        permission_mode="dontAsk",
        # Don't load CLAUDE.md, user settings, or project settings: the agent's
        # behaviour should come from this file alone, not from the machine it runs on.
        setting_sources=[],
        model=DEFAULT_MODEL,
        # A support turn is a few searches at most; this bounds a runaway loop.
        max_turns=8,
    )


async def run_once(question: str) -> str:
    """Answer a single question with no conversation history. Returns the reply text.

    `query()` opens a fresh session per call - use this for one-shot jobs like email
    triage or batch evaluation. For a conversation, use ClaudeSDKClient (see main.py).
    """
    reply: list[str] = []

    async for message in query(prompt=question, options=build_options()):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    reply.append(block.text)
        elif isinstance(message, ResultMessage) and message.is_error:
            raise RuntimeError(f"Agent run failed: {message.subtype}")

    return "\n".join(reply).strip()
