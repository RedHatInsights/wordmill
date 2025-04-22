import os
import uuid
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI
from openai.lib.streaming.chat import ChatCompletionStream

from dotenv import load_dotenv

import logging


log = logging.getLogger(__name__)


def _get_env_vars():
    load_dotenv()

    model_name = os.environ.get("LLM_MODEL_NAME")
    api_key = os.environ.get("LLM_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL")

    if not all([model_name, api_key, base_url]):
        raise ValueError(
            "provide the following env vars to the app: LLM_MODEL_NAME, LLM_API_KEY, LLM_BASE_URL"
        )

    return model_name, api_key, base_url


PROMPT = """
You are an assistant helping site reliability engineers summarize technical incidents from JSON data.

The JSON object describes a technical incident with fields such as:
- summary
- description
- incident_id
- products (indicates which company product the incident impacts)
- status
- external_coordination (indicates slack or google meet URLs where the incident is being discussed)
- created_at
- resolved_at
- private (indicates whether incident is public or private)
- incident_owner (indicates who opened the incident)
- participants (a list of people who worked on the incident)
- events (a list of event objects)

Each event object contains:
- note (the text)
- event_type ('comment' is a comment made by an engineer, 'audit_log' indicates a key change that was recorded in the incident tracking system)
- creation (the person who recorded the event)
- created_at (the time the note was created)

Any other fields in the JSON that are not mentioned above can be ignored.

Your task is to convert the JSON into a concise Markdown summary for engineering managers. Convert any ISO timestamps encounter using a human-readable date with the format: 'Month Day, Year Hour:Minute:Second Timezone' (e.g., 'April 22, 2025 14:30:15 UTC'). Format the summary with the following structure:

# Summary of Incident {{incident_id}}

## 🔧 Incident Details

- **Products Impacted:** {{bullet list of products}}
- **Status:** {{status}}
- **Private:** {{private}}
- **Created at:** {{created_at}}
- **Owner:** {{incident_owner}}
- **Resolved at:** {{resolved_at}}
- **Engineers Involved:** {{bullet list of participants}}

---

## 📋 Incident Summary
{{summary}}

---

## 🧪 Troubleshooting Timeline
Summarize key moments from the incident events, showing how the incident was diagnosed and resolved. Use bullet points. If the incident status changed, report the time this occurred. If an event note provides a URL link for a Slack workspace, a Google Docs document, or issues.redhat.com, please include the full link (but you can ignore dynatrace links).

---

### Here is the JSON:
{document}

### Now generate the Markdown summary:
"""

class LlmResponseHandler:
    def __init__(self, stream: ChatCompletionStream):
        self.done = False
        self.content = ""
        self.stream = stream
        self.exception = None

    def append(self, content: str) -> None:
        self.content += content

    def set_done(self) -> None:
        self.done = True

    def _worker(self):
        try:
            for chunk in self.stream:
                if chunk.choices:
                    self.append(chunk.choices[0].delta.content)
        except Exception as exc:
            log.exception("error handling llm response")
            self.exception = exc
        finally:
            self.set_done()


class LlmClient:
    def __init__(self):
        self.model_name, self.api_key, self.base_url = _get_env_vars()

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

        self.executor = ThreadPoolExecutor(max_workers=3)

    def summarize(self, document):
        messages = [
            {
                "role": "user",
                "content": PROMPT.format(document=document),
            },
        ]

        stream = self.client.chat.completions.create(
            model=self.model_name, messages=messages, stream=True
        )

        handler = LlmResponseHandler(stream)
        self.executor.submit(handler._worker)
        return handler


llm_client = LlmClient()
