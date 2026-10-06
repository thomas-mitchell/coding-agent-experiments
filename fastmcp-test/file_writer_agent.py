# FastMCP test
from dotenv import load_dotenv
from fastmcp import FastMCP
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset

load_dotenv()  # reads OPENAI_API_KEY from a .env file

LLM = "openai:gpt-5-mini"

mcp = FastMCP("file_write")

@mcp.tool()
def write(a: str) -> str:
    with open("out.txt", "w", encoding="utf-8") as f:
        f.write(a)
    return "the file was created"

tool_sets = MCPToolset(mcp)

writingagent = Agent(LLM, system_prompt="write a file based on the user prompt", toolsets=[tool_sets])

out = writingagent.run_sync("write a poem on ai as a text file")

print(out.output)
