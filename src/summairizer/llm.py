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
- start_time
- stop_time
- resolved_time
- current_status
- engineers (a list of people who worked on the incident)
- root_cause_analysis (text)
- comments (a list of troubleshooting notes and updates from engineers)

Your task is to convert the JSON into a concise Markdown summary for engineering managers. Format the summary with the following structure:

## 🔧 Incident Summary

**Status:** {current_status}
**Start Time:** {start_time}
**Stop Time:** {stop_time}
**Resolved Time:** {resolved_time}
**Engineers Involved:** {comma-separated list of engineers}

---

## 📋 Root Cause Analysis
{root_cause_analysis}

---

## 🧪 Troubleshooting Timeline
Summarize key moments from the comments field, showing how the incident was diagnosed and resolved. Use bullet points.

---

### Here is the JSON:
<your_json_here>

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
