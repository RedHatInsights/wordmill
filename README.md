# summAIrizer

This repo currently contains 2 components that are a work-in-progress:

- a tool for summarizing web-rca incidents
- an API service that will serve as a generic "summarizer tool" that can accept requests to summarize a document and reach out to the LLM to return generated content to the user

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
   LLM_BASE_URL="https://mistral-7b-instruct-v0-3-maas-apicast-production.apps.prod.rhoai.rh-aiservices-bu.com:443/v1"
   LLM_MODEL_NAME="mistral-7b-instruct"
   ```

## Running summarize_webrca_incident CLI script

This script reaches out directly to WebRCA to fetch incident info, then it passes JSON to the LLM for summarization.

TODO: Eventually, the code from this will be used to summarize all WebRCA incidents and store them in the web-rca DB.

1. Install [OCM CLI](https://github.com/openshift-online/ocm-cli)

2. Authenticate with OCM: `ocm login --use-auth-code`

3. Run script for a given incident ID:

```shell
pipenv shell
WEBRCA_TOKEN=$(ocm token) python summarize_webrca_incident.py ITN-2025-00094
```

## Running API server

This project also contains a flask API server which can receive a document summarize it. This API is a work-in-progress.

To run the server:

```shell
pipenv shell
flask run
```

## Example Usage of the API server

The service accepts a request to summarize the document and returns a URL that you should visit to check the status of your summary.

A background task reaches out to the LLM and awaits the response. Eventually, the status of your summarize task will shift to 'done'
and you can view the LLM-generated content. Your task may also shift to 'error' if something went wrong.

Since these summaries do not need to be long-lived, currently we are using flask-caching's "SimpleCache" to store the data. For production purposes,
the cache service used by flask-caching will need to be changed to redis or memcached

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
