# Deep Research Agent

This project is a multi-agent system built using **Pydantic AI** and **Gradio**. It serves as a Deep Research assistant that can take a free text query or a stock ticker (e.g., NVDA) and produce a highly structured, detailed research report using information gathered from the web via DuckDuckGo.

## How it works
The research is powered by `gpt-5-mini` and orchestrated through four specialized Pydantic AI agents:

1. **Intent & Entity Detection**: Detects whether the input is a general query or a stock ticker. If it's a ticker, it resolves it to the company name and context (e.g., NVDA -> NVIDIA, semiconductors, GPUs, AI).
2. **Initial Discovery Search**: Runs an initial DuckDuckGo search to generate 3-4 non-overlapping research angles (keywords).
3. **Parallel Deep Dives**: For each angle, a separate DuckDuckGo search is performed concurrently. Webpage contents are fetched, and key facts, claims, and numbers are extracted and mapped to their sources.
4. **Synthesis**: The findings are compiled into a highly structured final Markdown report featuring an executive summary, key findings per section, evidence bullets with citations, risks/uncertainties, and a "what to watch next" list.

## Prerequisites

- Python 3.10 or higher
- An OpenAI API Key

## Setup & Run

1. **Install the dependencies:**
   Open a terminal in this project directory and run:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure your Environment Variables:**
   Create a `.env` file (if you haven't already) and add your OpenAI API key:
   ```env
   OPENAI_API_KEY="sk-..."
   ```

3. **Run the Application:**
   Start the Gradio frontend by running:
   ```bash
   python app.py
   ```

4. **Start your Deep Research!**
   Once the script runs, it will output a local URL (e.g., `http://127.0.0.1:7860`). Open that URL in your web browser, type in a topic or ticker, and watch the agents build a comprehensive report!
