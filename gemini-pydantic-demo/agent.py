import os
import asyncio
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from duckduckgo_search import DDGS

load_dotenv()

# Data Models

class Intent(BaseModel):
    is_ticker: bool = Field(description="True if input is a stock ticker, False for general query")
    resolved_query: str = Field(description="The primary query to search for")
    company_name: str | None = Field(default=None, description="Resolved company name if it is a ticker")
    context: str | None = Field(default=None, description="Industry/sector context for the ticker")

class Angles(BaseModel):
    angles: list[str] = Field(description="3-4 non-overlapping research angles (keywords)")

class Fact(BaseModel):
    claim: str = Field(description="The extracted fact or claim")
    source_url: str = Field(description="URL of the source")
    source_title: str = Field(description="Title of the source")

class ExtractedFacts(BaseModel):
    angle: str = Field(description="The research angle these facts belong to")
    facts: list[Fact] = Field(description="List of extracted facts")

# Agents

intent_agent = Agent(
    'openai:gpt-5-mini',
    output_type=Intent,
    system_prompt=(
        "You are an intent detection assistant. Analyze the user's input.\n"
        "Detect whether the input is a stock ticker or a general query.\n"
        "If it's a ticker, resolve to the company name and provide context (e.g. NVDA -> NVIDIA, semiconductors, GPUs, AI).\n"
        "If it's a general query, set is_ticker to False and copy the query to resolved_query."
    )
)

angles_agent = Agent(
    'openai:gpt-5-mini',
    output_type=Angles,
    system_prompt=(
        "You are a research planning assistant.\n"
        "Given the user's intent and the initial search results, generate 3-4 research angles (keywords) that are relevant and non-overlapping.\n"
        "For a stock, examples include 'SWOT analysis', 'last 12 months stock performance', 'competition and market positioning', 'latest quarterly results and forward guidance'.\n"
        "For general queries, create angles that cover different aspects of the topic."
    )
)

facts_agent = Agent(
    'openai:gpt-5-mini',
    output_type=ExtractedFacts,
    system_prompt=(
        "You are a fact extraction assistant. You will be provided with a research angle and webpage content.\n"
        "Extract key facts, numbers, and claims. Only include facts supported by the text.\n"
        "Track which source supports which claim by filling in the source_url and source_title."
    )
)

synthesis_agent = Agent(
    'openai:gpt-5-mini',
    system_prompt=(
        "You are an expert research analyst. Produce a single detailed markdown report based on the provided facts and angles.\n"
        "Include the following sections:\n"
        "- Executive summary\n"
        "- Key findings per section (one section per angle)\n"
        "- Evidence bullets with citations (url + source title)\n"
        "- Risks/uncertainties and conflicting info\n"
        "- 'What to watch next' list\n"
        "Constraints:\n"
        "- Prefer primary sources (financials, earnings releases, filings) and reputable outlets for news.\n"
        "- Ensure the report is highly structured, detailed, and professional."
    )
)

async def search_ddg(query: str, max_results: int = 3) -> list[dict]:
    # Run synchronous DDGS in a thread to avoid blocking asyncio
    def _search():
        try:
            results = DDGS().text(query, max_results=max_results)
            return list(results)
        except Exception as e:
            print(f"Search failed for {query}: {e}")
            return []
    return await asyncio.to_thread(_search)

async def fetch_page_content(url: str, title: str) -> str:
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")
            for script in soup(["script", "style"]):
                script.extract()
            text = soup.get_text(separator=' ', strip=True)
            # truncate to 3000 chars to avoid massive context
            return f"Source Title: {title}\nSource URL: {url}\nContent:\n{text[:3000]}"
    except Exception as e:
        return f"Source Title: {title}\nSource URL: {url}\nFailed to fetch content: {str(e)}"

async def run_deep_dive(angle: str) -> ExtractedFacts:
    print(f"Deep dive for angle: {angle}")
    results = await search_ddg(angle, max_results=2)
    
    if not results:
        return ExtractedFacts(angle=angle, facts=[])
    
    # Fetch page contents in parallel
    tasks = [fetch_page_content(r.get("href", ""), r.get("title", "")) for r in results if r.get("href")]
    contents = await asyncio.gather(*tasks, return_exceptions=True)
    
    valid_contents = [c for c in contents if isinstance(c, str)]
    
    if not valid_contents:
        return ExtractedFacts(angle=angle, facts=[])
    
    combined_content = f"Research Angle: {angle}\n\n" + "\n\n---\n\n".join(valid_contents)
    
    try:
        result = await facts_agent.run(combined_content)
        return result.output
    except Exception as e:
        print(f"Failed to extract facts for {angle}: {e}")
        return ExtractedFacts(angle=angle, facts=[])

async def deep_research(query: str) -> str:
    print(f"Starting deep research for: {query}")
    try:
        intent_result = await intent_agent.run(query)
        intent = intent_result.output
        print(f"Detected Intent: {intent.model_dump_json()}")
        
        search_query = intent.resolved_query
        if intent.is_ticker and intent.company_name:
            search_query = f"{intent.company_name} {intent.context or ''}".strip()
            
        initial_results = await search_ddg(search_query, max_results=3)
        if not initial_results:
            initial_results = [{"title": "No results", "body": "DuckDuckGo returned no results or rate limited."}]
            
        angles_prompt = f"Intent: {intent.model_dump_json()}\nInitial Search Results: {initial_results}"
        angles_result = await angles_agent.run(angles_prompt)
        angles = angles_result.output
        print(f"Generated Angles: {angles.angles}")
        
        deep_dive_tasks = [run_deep_dive(angle) for angle in angles.angles]
        all_facts_results = await asyncio.gather(*deep_dive_tasks, return_exceptions=True)
        
        all_facts = []
        for f in all_facts_results:
            if isinstance(f, ExtractedFacts) and f.facts:
                all_facts.append(f)
                
        if not all_facts:
            return "Failed to extract facts or rate limited by search engine. Please try again later."
                
        synthesis_prompt = (
            f"Original Query: {query}\n"
            f"Intent Details: {intent.model_dump_json()}\n"
            f"Extracted Facts by Angle:\n"
        )
        for ext_fact in all_facts:
            synthesis_prompt += f"\nAngle: {ext_fact.angle}\n"
            for fact in ext_fact.facts:
                synthesis_prompt += f"- {fact.claim} (Source: [{fact.source_title}]({fact.source_url}))\n"
                
        synthesis_result = await synthesis_agent.run(synthesis_prompt)
        return synthesis_result.output
    except Exception as e:
        return f"An error occurred during deep research: {str(e)}"

# Export for Gradio integration
agent = Agent(
    'openai:gpt-5-mini', 
    system_prompt="This is a proxy agent for app.py to avoid rewriting the app completely."
)
# We won't actually use this proxy agent.run directly in app.py, we will modify app.py.
