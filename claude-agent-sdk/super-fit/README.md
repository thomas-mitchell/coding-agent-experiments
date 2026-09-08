# Super Fit support agent

A customer support agent for a fictional gym chain, built on the [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview).
It answers questions **only** from a FAQ knowledge base it reads through custom tools,
and hands anything it can't answer to a human.

## Quick start

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope Process RemoteSigned
pip install -r requirements.txt

copy .env.example .env              # then put your key in it
python main.py
```

Get an API key at <https://platform.claude.com/>. The SDK reads `ANTHROPIC_API_KEY`
from the process environment and does **not** read `.env` itself — `main.py` calls
`load_dotenv()` first to bridge that. With no key set, it falls back to an existing
Claude Code login on the machine, which is fine locally but not for anything deployed.

```bash
python main.py                      # chat session
python main.py --verbose            # chat, showing each tool call and the cost
python main.py "how do I cancel?"   # answer one question and exit
python smoke_test.py                # offline checks, no API calls, no key needed
```

## How it fits together

```
main.py                    CLI: chat loop (ClaudeSDKClient) + one-shot mode (query)
support_agent/
  agent.py                 ClaudeAgentOptions - the agent's whole configuration
  prompts.py               system prompt: identity, grounding rules, escalation, limits
  faq_tools.py             the four tools, wrapped in an in-process MCP server
  knowledge.py             loads faqs.json, keyword search with IDF + phrase matching
data/
  faqs.json                the knowledge base — edit this to change what the agent knows
  escalations.jsonl        tickets written by escalate_to_human (gitignored)
```

### The tools

The agent has no built-in tools at all. `tools=[]` in `agent.py` strips `Read`,
`Write`, `Bash`, and the rest out of its context — a customer-facing bot has no
business touching the filesystem. All it can do is:

| Tool | What it does |
| --- | --- |
| `search_faqs` | Finds FAQ entries relevant to the customer's question |
| `get_faq` | Re-reads one entry verbatim by id |
| `list_categories` | Lists the topics the agent can help with |
| `escalate_to_human` | Writes a ticket to `data/escalations.jsonl`, returns a reference |

They're defined with the `@tool` decorator and wrapped in `create_sdk_mcp_server`,
which runs **in this process** — no subprocess, no MCP config file. The server is
registered under the key `faq`, which is what makes each tool's full name
`mcp__faq__<tool>`. Those four names are listed in `allowed_tools` so they run without
a permission prompt, and `permission_mode="dontAsk"` denies anything else outright
rather than blocking on a prompt no one is there to answer.

### Grounding

Two things keep the agent from making up policy:

1. **The system prompt** (`prompts.py`) requires a search before any answer about the
   company, forbids inventing prices or policies, and lists when to escalate.
2. **The search returns nothing** for off-topic questions rather than a weak match, and
   says so in the tool result, so the agent has nothing to lean on but "I don't know".

Verified behaviour: asked whether the gym sells protein shakes (not in the FAQs), the
agent says it can't confirm and offers a human — it doesn't guess.

## Customising it

**Change what it knows:** edit `data/faqs.json`. Each entry needs `id`, `category`,
`question`, `answer`, and `tags`. Tags are where you put customer phrasing the question
line doesn't use ("no show", "penalised", "money back"). Run `python smoke_test.py`
afterwards — it checks that real customer questions still retrieve the right entries.

**Change how it behaves:** edit `prompts.py`. Tone, escalation triggers, and hard
limits all live there. Reach for this before changing code.

**Change the model:** `SUPER_FIT_MODEL=claude-opus-5 python main.py`, or edit
`DEFAULT_MODEL` in `agent.py`. Defaults to `claude-sonnet-5`.

**Scale the knowledge base:** the search in `knowledge.py` is keyword-based with IDF
weighting and a phrase bonus — good to a few hundred entries. Past that, swap the body
of `search()` for an embedding lookup; the tool layer won't need to change.

## Notes on the retrieval

`knowledge.py` scores each FAQ by summing IDF-weighted matches, weighted by where they
hit: question line (4.0) > tags (2.5) > answer body (1.0). Two details that came out of
the test cases:

- **IDF is capped** at 2.5. Uncapped, "how do I book a spin class" ranked the entry that
  merely *lists* Spin above the one explaining how to book, because "spin" appears in a
  single entry and its rarity dominated everything else.
- **Phrase pairs get a bonus.** "Why was I charged after I cancelled" shares every
  individual word with the general refund policy; the pair `charged after` is what
  separates them.

Tokens are stemmed crudely (`cancelled`, `cancelling`, `cancel` → one key) and a
stopword list strips chat filler, which otherwise scores highly — "am" is rare in the
corpus, so without it "am I penalised" matched "When am I billed".

## Docs

- [Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview)
- [Python SDK reference](https://code.claude.com/docs/en/agent-sdk/python)
- [Custom tools](https://code.claude.com/docs/en/agent-sdk/custom-tools)
- [Permissions](https://code.claude.com/docs/en/agent-sdk/permissions)
- [Modifying system prompts](https://code.claude.com/docs/en/agent-sdk/modifying-system-prompts)
