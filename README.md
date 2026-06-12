# wordmill

A document summarization API service. It provides a simple REST API that accepts requests to
summarize a document. Under the hood, it reaches out to an LLM hosted on any OpenAI-compatible API
service.

Wordmill abstracts away the "AI" details from your user base. Many people in your organization want
to summarize documents. Not as many of them care to know all the details related to LLMs, prompts,
document prep, model selection, etc. The service allows administrators to configure and customize
these aspects based on the incoming document type. All the end users need to do is request a summary.

## Prerequisites

- Python 3.12+
- [pyenv][pyenv] (recommended)
- [Pipenv][pipenv]
- Access to an OpenAI-compatible LLM API endpoint

## Installation

1. Install pyenv (recommended) and ensure Python 3.12 is available:

   ```shell
   pyenv install 3.12
   ```

2. Install dependencies:

   ```shell
   pipenv install --dev
   ```

3. Create a `.env` file with your LLM access credentials:

   ```text
   LLM_API_KEY=<your key>
   LLM_BASE_URL="https://my-llm-server:443/v1"
   LLM_MODEL_NAME="mistral-7b-instruct"
   ```

## Running

Start the API server:

```shell
pipenv shell
flask run
```

The server runs on `http://0.0.0.0:8000` by default (configured in `.flaskenv`).

## API Endpoints

| Method | Path | Description |
| ------ | ---- | ----------- |
| `POST` | `/summarize` | Submit a document for summarization (returns task ID) |
| `GET` | `/summary/<id>` | Poll for summary status and result |
| `GET` | `/prompt` | Retrieve the current LLM prompt |
| `POST` | `/prompt` | Update the LLM prompt |
| `GET` | `/health` | Health check |

### Example Usage

The service accepts a request to summarize a document and returns a task ID. A background task
reaches out to the LLM and streams the response. Poll the summary endpoint until the status shifts
to `done` (or `error` if something went wrong).

Summaries are stored in an in-memory cache (`SimpleCache`) and are not persisted across restarts.
For production use, the cache backend should be changed to Redis or Memcached.

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

## Container

Build and run with Docker:

```shell
docker build -t wordmill .
docker run -p 8000:8000 \
  -e LLM_API_KEY="<your key>" \
  -e LLM_BASE_URL="https://my-llm-server:443/v1" \
  -e LLM_MODEL_NAME="mistral-7b-instruct" \
  wordmill
```

The image is based on `registry.access.redhat.com/ubi9/python-312` and runs as a non-root user
(UID 1001), suitable for OpenShift deployments.

## Development

### Setup

```shell
pipenv install --dev
pipenv shell
```

### Dev Dependencies

The project includes `ruff` and `flake8` as dev dependencies for linting, and `pytest` for testing.
Note that no test files or linter configurations currently exist in the repository.

### Architecture

For internal design details — concurrency model, caching strategy, LLM integration, and key
tradeoffs — see the [architecture document][architecture].

## License

This project is licensed under the [Apache License 2.0][license].

[pyenv]: https://github.com/pyenv/pyenv?tab=readme-ov-file#installation
[pipenv]: https://pipenv.pypa.io/
[architecture]: ./ARCHITECTURE.md
[license]: ./LICENSE
