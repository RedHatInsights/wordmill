import os
import uuid

from openai import OpenAI


def _get_env_vars():
    model_name = os.environ.get("LLM_MODEL_NAME")
    api_key = os.environ.get("LLM_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL")

    if not all([model_name, api_key, base_url]):
        raise ValueError(
            "provide the following env vars to the app: LLM_MODEL_NAME, LLM_API_KEY, LLM_BASE_URL"
        )

    return model_name, api_key, base_url


PROMPT = (
    "You are a helpful assistant who summarizes technical incident reports written for site "
    "reliability engineers. You are given a document in JSON format. Your task is to generate a "
    "comprehensive and highly readable summary of all the information pertaining to the incident. "
    "Format the summary in Markdown for clarity and structure.\n\n"
    "--- Begin JSON document ---\n\n{document}\n\n--- End JSON document ---"
)


class LlmClient:
    def __init__(self):
        self.model_name, self.api_key, self.base_url = _get_env_vars()

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def summarize(self, document):
        messages = [
            {
                "role": "user",
                "content": PROMPT.format(document=document),
            },
        ]

        completion = self.client.chat.completions.create(
            model=self.model_name, messages=messages
        )

        return completion.choices[0].message.content


llm_client = LlmClient()
