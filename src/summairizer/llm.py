import os
import uuid

from llama_stack_client import Agent, AgentEventLogger
from llama_stack.distribution.library_client import LlamaStackAsLibraryClient

# LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8321")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "llama3.2:3b")
SUMMARY_PROMPT = """
    You are received a list of documents in JSON format. Your task is to generate a comprehensive and highly readable summary of all the information contained within these documents. Format the summary in Markdown for clarity and structure.
"""


class LlmClient:
    def __init__(self):
        self.client =  LlamaStackAsLibraryClient(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "../../config.yaml"
            )
        )
        self.client.initialize()

        self.agent = Agent(
            self.client,
            model=LLM_MODEL_NAME,
            instructions="You are an agent that generate summaries of documents",
        )

    def summarize(self, documents):
        try:
            session_id = self.agent.create_session(session_name=str(uuid.uuid4()))
            response = self.agent.create_turn(
                session_id=session_id,
                messages=[{"role": "user", "content": SUMMARY_PROMPT}],
                documents=documents,
                stream=False,
            )
            return response.output_message.content
        except Exception as e:
            print(f"Error creating the agent turn: {e}")
            raise


llm_client = LlmClient()
