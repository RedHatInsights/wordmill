# Architecture

Internal architecture overview for wordmill — a Flask REST API for LLM-based document
summarization.

## Application Structure

Wordmill uses the Flask app factory pattern with `flask-restful` for resource management. There are
no blueprints; all resources are registered on a single `Api` instance.

```
src/wordmill/
├── __init__.py          # App factory (create_app), default prompt, CORS/cache/API init
├── cache.py             # Flask-Caching singleton instance
├── llm.py               # OpenAI client, streaming handler, ThreadPoolExecutor
└── resources/
    ├── __init__.py      # Empty
    ├── api.py           # Resource classes (PromptApi, SummaryApi, SummarizeApi, HealthCheckApi)
    └── routes.py        # Route registration function
```

The factory function `create_app()` in `src/wordmill/__init__.py` performs:

1. Creates a `Flask("wordmill")` instance with DEBUG logging.
2. Enables CORS via `flask-cors`.
3. Initializes the cache singleton and seeds it with the default prompt.
4. Creates a `flask_restful.Api` and delegates to `initialize_routes()` for resource registration.

## Request Flow

A summarization request follows this path:

1. Client sends `POST /summarize` with `{"document": "..."}`.
2. `SummarizeApi.post()` validates the JSON body, generates a UUID task key, and calls
   `llm_client.summarize()`.
3. `LlmClient.summarize()` validates the prompt contains `{document}`, formats it with the document
   text, and sends it to the OpenAI-compatible API as a streaming `chat.completions.create()` call.
   The response stream is wrapped in an `LlmResponseHandler` and submitted to a
   `ThreadPoolExecutor` to consume in a background thread.
4. A separate daemon `threading.Thread` (the "handler watcher") polls the handler every 100ms and
   writes `handler.to_dict()` into the cache under the UUID key.
5. The endpoint returns `202 Accepted` with `{"message": "generating summary", "id": "<uuid>"}`.
6. The client polls `GET /summary/<id>` until `status` is `done` or `error`.

## Concurrency Model

Background processing uses a two-tier threading approach:

- **Tier 1 — `ThreadPoolExecutor(max_workers=3)`**: A module-level singleton in `src/wordmill/llm.py`
  owns this executor. Each `summarize()` call submits `LlmResponseHandler._worker()` to consume the
  OpenAI streaming response chunk-by-chunk.
- **Tier 2 — daemon `threading.Thread`**: A watcher thread per task polls the handler every 100ms
  and writes a serialized snapshot into the cache. This bridges the handler object (in thread memory)
  and the cache (read by the polling endpoint).

Maximum concurrency is 3 simultaneous LLM streams (hard-coded). Additional calls queue in the
executor. There is no limit on watcher threads.

`LlmResponseHandler.content` is mutated by the executor thread and read by the watcher thread
without explicit synchronization. This works in practice due to CPython's GIL but is not formally
thread-safe.

## Caching Strategy

The cache uses `flask-caching` with `SimpleCache` — an in-process dictionary.

| Key | Value | Set by |
| --- | ----- | ------ |
| `"prompt"` | Current system prompt string | `create_app()` (default), `PromptApi.post()` (user override) |
| `<uuid>` | `{"done": bool, "content": str, "exception": str\|None}` | `_handler_watcher()` thread |

**Tradeoffs:**

- All data is lost on process restart.
- Multi-worker deployments (e.g., gunicorn with multiple workers) would have isolated caches — a
  summary started in worker A returns 404 when polled by worker B.
- `SimpleCache` has a default timeout of 300 seconds, after which entries are evicted.
- The code acknowledges this: `"simple cache used for POC, move to something more robust later"`
  (`src/wordmill/cache.py`).

## LLM Integration

The `openai` Python SDK is configured against an OpenAI-compatible endpoint (the base URL is
configurable, so it is not limited to OpenAI itself).

### Configuration

Three environment variables are required, loaded from `.env` with `os.environ` taking precedence:

| Variable | Purpose |
| -------- | ------- |
| `LLM_MODEL_NAME` | Model identifier for `chat.completions.create()` |
| `LLM_API_KEY` | API authentication key |
| `LLM_BASE_URL` | Base URL for the OpenAI-compatible API |

If any is missing, a `ValueError` is raised at import time (the `LlmClient` is instantiated at
module level as a singleton).

### Prompt Management

A default prompt is defined in `src/wordmill/__init__.py` and seeded into the cache at startup. It
can be changed at runtime via `POST /prompt`. Prompts must contain the `{document}` placeholder,
enforced by validation in `LlmClient.validate_prompt()`.

Note: `DEFAULT_PROMPT` is duplicated in both `src/wordmill/__init__.py` and `src/wordmill/llm.py`.

### Error Handling

Exceptions during stream consumption are caught broadly (`except Exception`), logged, and stored on
`handler.exception`. The handler marks `done = True`, the watcher writes the error to cache, and the
polling endpoint surfaces it as `"status": "error"`.

## API Design

| Method | Path | Resource Class | Description | Success Code |
| ------ | ---- | -------------- | ----------- | ------------ |
| `POST` | `/summarize` | `SummarizeApi` | Submit a document for summarization | `202 Accepted` |
| `GET` | `/summary/<id>` | `SummaryApi` | Poll for summary status/result | `200 OK` / `404` |
| `GET` | `/prompt` | `PromptApi` | Retrieve current prompt | `200 OK` |
| `POST` | `/prompt` | `PromptApi` | Update the prompt | `200 OK` / `400` |
| `GET` | `/health` | `HealthCheckApi` | Health check | `200 OK` |

The summarization API follows an **asynchronous request-reply** pattern: `POST /summarize` returns
immediately with a task ID (202), and the client polls `GET /summary/<id>` until completion.
`GET /summary/<id>` only includes `content` when `done` is `true`, but `bytes_received` is included
for any non-empty content, providing a progress indicator during streaming.

## Dependency Graph

```
__init__.py
├── flask, flask_cors, flask_restful
├── .cache (cache singleton)
└── .resources.routes (initialize_routes)

cache.py
└── flask_caching

llm.py
├── openai, dotenv, concurrent.futures
└── no internal imports (independent of Flask and cache)

resources/api.py
├── wordmill.cache
└── wordmill.llm

resources/routes.py
└── .api (all four Resource classes)
```

The dependency graph is acyclic: `__init__` -> `routes` -> `api` -> `{cache, llm}`. The `llm`
module is fully independent of Flask, meaning the LLM layer could be reused outside Flask with
minimal changes.

## Key Design Decisions

| Decision | Rationale | Tradeoff |
| -------- | --------- | -------- |
| In-memory `SimpleCache` | Simplicity for POC | No persistence, no multi-worker support, 300s eviction |
| Threading over async | Flask is synchronous; threads are simpler | Capped at 3 concurrent LLM streams |
| Polling over SSE/WebSocket | Simpler to implement with Flask | Client must implement polling logic; 100ms watcher interval is a CPU/freshness balance |
| Module-level LLM singleton | Fail-fast if credentials are missing | Environment variables must be present at import time |
| No authentication | POC / internal-use posture | Not production-ready as-is |
