import gradio as gr
from agent import deep_research

async def chat(message, history):
    # Pass the user query to our multi-step deep research workflow
    report = await deep_research(message)
    return report

# Create a ChatInterface using Gradio
demo = gr.ChatInterface(
    fn=chat,
    title="Deep Research Agent",
    description="A multi-agent system powered by gpt-5-mini and Pydantic AI. Enter a topic or stock ticker to get a detailed research report."
)

if __name__ == "__main__":
    demo.launch()
