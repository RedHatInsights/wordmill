import logging
import os
from concurrent.futures import ThreadPoolExecutor

from dotenv import dotenv_values
from openai import OpenAI
from openai.lib.streaming.chat import ChatCompletionStream

log = logging.getLogger(__name__)


DEFAULT_PROMPT = (
    "You are a helpful assistant. Write a summary for the following document using "
    "markdown syntax:\n\n{document}"
)


def _get_env_vars():
    config = {
        **dotenv_values(".env"),  # load shared development variables
        **os.environ,  # override loaded values with environment variables if they exist
    }

    model_name = config.get("LLM_MODEL_NAME")
    api_key = config.get("LLM_API_KEY")
    base_url = config.get("LLM_BASE_URL")

    if not all([model_name, api_key, base_url]):
        raise ValueError(
            "provide the following env vars to the app: LLM_MODEL_NAME, LLM_API_KEY, LLM_BASE_URL"
        )

    return model_name, api_key, base_url


class LlmResponseHandler:
    def __init__(self, stream: ChatCompletionStream):
        self.done = False
        self.content = ""
        self.stream = stream
        self.exception = None

    def to_dict(self):
        """
        Translate handler status to plain dictionary for use with caches
        """
        return {
            "done": self.done,
            "content": self.content,
            "exception": str(self.exception) if self.exception else None,
        }

    def _worker(self):
        log.debug("llm handler begin processing stream")

        try:
            for chunk in self.stream:
                if chunk.choices:
                    self.content += chunk.choices[0].delta.content
        except Exception as exc:
            log.exception("llm handler hit unexpected error")
            self.exception = exc
        finally:
            self.done = True

        log.debug("llm handler done")


class LlmClient:
    def __init__(self):
        self.model_name, self.api_key, self.base_url = _get_env_vars()

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

        self.executor = ThreadPoolExecutor(max_workers=3)

    @staticmethod
    def validate_prompt(prompt: str):
        if "{document}" not in prompt:
            raise ValueError("prompt must contain key word '{document}'")

    def summarize(self, document: str, prompt=DEFAULT_PROMPT):
        self.validate_prompt(prompt)

        messages = [
            {
                "role": "user",
                "content": prompt.format(document=document),
            },
        ]

        stream = self.client.chat.completions.create(
            model=self.model_name, messages=messages, stream=True
        )

        handler = LlmResponseHandler(stream)
        self.executor.submit(handler._worker)
        return handler


llm_client = LlmClient()
