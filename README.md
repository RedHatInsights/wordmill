# summAIrizer

## Setup

1. It is recommended to [install pyenv](https://github.com/pyenv/pyenv?tab=readme-ov-file#installation).

     NOTE: Make sure to follow all steps! (A, B, C, D, and so on)

2. Set up the virtual environment:

    ```shell
    pipenv install --dev
    ```

## Running

```shell
pipenv shell
LLM_API_KEY=<your key> LLM_BASE_URL="https://mistral-7b-instruct-v0-3-maas-apicast-production.apps.prod.rhoai.rh-aiservices-bu.com:443/v1" LLM_MODEL_NAME="mistral-7b-instruct" flask run
```

## Example Usage

```python
import requests
import json

with open("incident.json") as fp:
  data = json.load(fp)

print(requests.post("http://127.0.0.1:8000", json=data).json()["summary"])
```
