# wordmill

A work-in-progress.

wordmill is a document summary API service. It provides a simple REST API which accepts requests to summarize a document. Under the hood, it reaches out to a LLM hosted on any OpenAI-compatible API service.

It is designed to abstract away the "AI" details from your user base. Many people in your organization want to summarize documents. Not as many of them care to know all the details related to LLMs, prompts, document prep, model selection, etc. The service will allow administrators to configure and customize these aspects based on the incoming document type. All the end users need to do is request a summary.

## Setup

1. It is recommended to [install pyenv](https://github.com/pyenv/pyenv?tab=readme-ov-file#installation).

     NOTE: Make sure to follow all steps! (A, B, C, D, and so on)

2. Set up the virtual environment:

    ```shell
    pipenv install --dev
    ```

3. Add your LLM access info into `.env`, example:

   ```text
   LLM_API_KEY=<your key>
   LLM_BASE_URL="https://my-llm-server:443/v1"
   LLM_MODEL_NAME="mistral-7b-instruct"
   ```

## Running API server

To run the server:

```shell
pipenv shell
flask run
```

## Example Usage of the API server

The service accepts a request to summarize the document and returns a URL that you should visit to check the status of your summary.

A background task reaches out to the LLM and awaits the response. Eventually, the status of your summarize task will shift to 'done' and you can view the LLM-generated content. Your task may also shift to 'error' if something went wrong.

Since these summaries do not need to be long-lived, currently we are using flask-caching's "SimpleCache" to store the data. For production purposes, the cache service used by flask-caching will need to be changed to redis or memcached

```python
import json
import requests
import time

# load the document you wish to summarize
with open("incident.json") as fp:
    data = json.load(fp)

# customize the prompt passed to the LLM (optional)
requests.post(
    "http://127.0.0.1:8000/prompt",
    json={"prompt": "Please summarize this document:\n\n{document}"}
)

# submit request to summarize and get background task id
id = requests.post("http://127.0.0.1:8000/summarize", json={"document": data}).json()["id"]

# repeatedly check on the 'summarize' task and wait for summary to be generated...
while True:
    time.sleep(5)
    summary = requests.get(f"http://127.0.0.1:8000/summary/{id}").json()
    if summary["status"] == "done":
        print(summary["content"])
        break
```
