import os
import uuid

from llama_stack_client import Agent, AgentEventLogger
from llama_stack.distribution.library_client import LlamaStackAsLibraryClient

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8321")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "meta-llama/Llama-3.2-3B-Instruct")
SUMMARY_PROMPT = """
    You are received a list of documents in JSON format. Your task is to generate a comprehensive and highly readable summary of all the information contained within these documents. Format the summary in Markdown for clarity and structure.
"""

class LlmClient:
    def __init__(self):
        self.client = LlamaStackAsLibraryClient("ollama")
        # self.client =  LlamaStackAsLibraryClient("/home/jbarea/Documents/projects/summ-ai-rizer/custom-template.yaml")
        self.client.initialize()

        self.agent = Agent(
            self.client,
            model=LLM_MODEL_NAME,
            instructions="You are an agent that generate summaries of documents",
        )

    def summarize(self, documents):
        try:
            response = self.agent.create_turn(
                messages=[{"role": "user", "content": SUMMARY_PROMPT}],
                documents=documents,
                stream=False,
                session_id=self.agent.create_session(str(uuid.uuid4())),
            )
            return response.output_message.content
        except Exception as e:
            print(f"Error creating the agent turn: {e}")
            raise

llm_client = LlmClient()