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

Your task is to convert the JSON into a concise Markdown summary for engineering managers. Format the summary with the following structure:

## 🔧 Incident Details: {{incident_id}}

**Status:** {{status}}
**Created at:** {{created_at}}
**Owner:** {{incident_owner}}
**Resolved at:** {{resolved_time}}
**Engineers Involved:** {{bullet list of participants}}
**Private:** {{private}}

---

## 📋 Incident Summary
{{summary}}

---

## 🧪 Troubleshooting Timeline
Summarize key moments from the incident events, showing how the incident was diagnosed and resolved. Use bullet points.

---

### Here is the JSON:
{document}

### Now generate the Markdown summary:
"""


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
