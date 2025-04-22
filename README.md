# summAIrizer

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

1. Install [OCM CLI](https://github.com/openshift-online/ocm-cli)

2. Authenticate with OCM: `ocm login --use-auth-code`

3. Run script for a given incident ID:

```shell
pipenv shell
WEBRCA_TOKEN=$(ocm token) python summarize_webrca_incident.py ITN-2025-00094
```

## Running API server

```shell
pipenv shell
flask run
```

## Example Usage of the API server

```python
import json
import requests
import time


with open("incident.json") as fp:
    data = json.load(fp)

id = requests.post("http://127.0.0.1:8000/summarize", json=data).json()["id"]

while True:
    # wait for summary to be generated...
    time.sleep(5)
    summary = requests.get(f"http://127.0.0.1:8000/summary/{id}").json()
    if summary["status"] == "done":
        print(summary["content"])
        break
```
