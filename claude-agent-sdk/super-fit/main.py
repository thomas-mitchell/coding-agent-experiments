"""Super Fit support agent - interactive CLI.

Usage:
    python main.py                       Start a chat session
    python main.py "how do I cancel?"    Answer one question and exit
    python main.py --verbose             Chat, showing which tools the agent calls

The chat session uses ClaudeSDKClient, which keeps one session open across turns so
the agent remembers the conversation. The one-shot mode uses query(), which starts a
fresh session per call.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKClient,
    ClaudeSDKError,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from support_agent.agent import build_options, run_once

BANNER = """
Super Fit support assistant
---------------------------
Ask about memberships, billing, classes, personal training, facilities, or the app.
Type 'quit' or press Ctrl+C to leave.
"""

# Friendly labels so --verbose output reads as actions, not tool names.
TOOL_LABELS = {
    "mcp__faq__search_faqs": "searching the FAQs",
    "mcp__faq__get_faq": "reading an FAQ entry",
    "mcp__faq__list_categories": "listing FAQ topics",
    "mcp__faq__escalate_to_human": "raising a support ticket",
}


def check_credentials() -> None:
    """The SDK reads ANTHROPIC_API_KEY from the process environment, not from .env.

    With no key set, it falls back to an existing Claude Code login on this machine,
    which is fine for local development. Anything you deploy should use an API key.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return

    if (Path.home() / ".claude" / ".credentials.json").exists():
        print("[no ANTHROPIC_API_KEY set - using your local Claude Code login]\n")
        return

    print(
        "ANTHROPIC_API_KEY is not set.\n"
        "Copy .env.example to .env and put your key in it, or set it in this shell:\n"
        '  PowerShell:  $env:ANTHROPIC_API_KEY = "sk-ant-..."\n'
        "  bash:        export ANTHROPIC_API_KEY=sk-ant-...\n"
        "Get a key at https://platform.claude.com/",
        file=sys.stderr,
    )
    raise SystemExit(1)


async def stream_reply(client: ClaudeSDKClient, verbose: bool) -> None:
    """Print one full agent response, from the tool calls through to the answer."""
    printed_prefix = False

    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    if not printed_prefix:
                        print("Super Fit: ", end="")
                        printed_prefix = True
                    print(block.text.strip())
                elif isinstance(block, ToolUseBlock) and verbose:
                    label = TOOL_LABELS.get(block.name, block.name)
                    print(f"  [{label}]")
        elif isinstance(message, ResultMessage):
            if message.is_error:
                print(f"  [the agent hit an error: {message.subtype}]", file=sys.stderr)
            if verbose and message.total_cost_usd:
                print(f"  [{message.num_turns} turns, ${message.total_cost_usd:.4f}]")


async def chat(verbose: bool) -> None:
    print(BANNER)

    # The client holds one session open, so follow-up questions keep their context.
    async with ClaudeSDKClient(options=build_options()) as client:
        while True:
            try:
                # input() blocks the event loop, so run it on a worker thread.
                question = (await asyncio.to_thread(input, "You: ")).strip()
            except (EOFError, KeyboardInterrupt):
                print("\nThanks for stopping by.")
                return

            if not question:
                continue
            if question.lower() in {"quit", "exit", "bye"}:
                print("Thanks for stopping by.")
                return

            await client.query(question)
            await stream_reply(client, verbose)
            print()


async def main() -> None:
    # Windows consoles default to a legacy codepage, which turns any character the
    # model emits outside it into a replacement glyph mid-sentence.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors="replace")

    load_dotenv()  # the SDK does not read .env itself, so do it here first
    check_credentials()

    args = [a for a in sys.argv[1:] if a not in {"-v", "--verbose"}]
    verbose = len(args) != len(sys.argv[1:])

    if args:
        # The interactive path reports failures through stream_reply; do the same
        # here so a one-shot run fails with a message rather than a traceback.
        try:
            print(await run_once(" ".join(args)))
        except (RuntimeError, ClaudeSDKError) as exc:
            print(f"The agent could not answer that: {exc}", file=sys.stderr)
            raise SystemExit(1) from None
    else:
        await chat(verbose)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
