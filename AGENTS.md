# wordmill

## Project Overview

Wordmill is a document summarization REST API built with Flask. It accepts documents via HTTP,
delegates summarization to an OpenAI-compatible LLM endpoint, and returns results asynchronously
via a polling interface. It is distributed as a Python package on PyPI and as a UBI9-based container
image.

## Dependencies

- **Runtime:** flask, flask-restful, flask-cors, flask-caching, openai, python-dotenv
- **Dev:** pytest, ruff, flake8, pre-commit, requests, ipython, setuptools, hatchling, twine
- **Build:** hatchling (PEP 517)
- **Python:** 3.12+

## Development Commands

See [Development Setup][readme-dev] in the README for the full command reference.

```shell
# install all dependencies (including dev)
pipenv install --dev

# enter the virtual environment
pipenv shell

# run the flask server
flask run
```

There are no test files in the repository. `pytest` is a dev dependency but there is nothing to run.
Neither `ruff` nor `flake8` have configuration files; no linting is enforced in CI.

CI runs only a build-and-publish pipeline (`python -m build`) on push to `master` and on tag push.
There is no CI test or lint job.

## Architecture

The application uses the Flask app factory pattern with `flask-restful`. Source code lives in
`src/wordmill/`. The entry point is `create_app()` in `src/wordmill/__init__.py`. Key modules are
`llm.py` (OpenAI client and thread pool) and `resources/api.py` (REST resource classes).

For full architectural details — concurrency model, caching strategy, LLM integration, and design
tradeoffs — see the [architecture document][architecture].

## Code Style

No active linter or formatter configuration exists. Both `ruff` and `flake8` are listed as dev
dependencies but neither has a config file (`ruff.toml`, `.ruff.toml`, `[tool.ruff]` in
`pyproject.toml`, `.flake8`, `setup.cfg` — none present) and neither is run in CI. These are
currently legacy/unused dev dependencies.

Python 3.12+ is required (pinned in `.python-version` and `Pipfile`).

## Common Mistakes

1. **Missing LLM environment variables at import time.** The `LlmClient` is instantiated at module
   level (`src/wordmill/llm.py`). If `LLM_API_KEY`, `LLM_BASE_URL`, or `LLM_MODEL_NAME` are not
   set when the module is first imported, the application crashes immediately with a `ValueError`.
   Always ensure these are set before starting the server.

1. **Duplicated `DEFAULT_PROMPT` constant.** The default prompt string is defined identically in
   both `src/wordmill/__init__.py` and `src/wordmill/llm.py`. When modifying the prompt, update
   both locations or the fallback will diverge from what is seeded into the cache.

1. **In-memory cache is not shared across workers.** `SimpleCache` stores data in the process's
   memory. Multi-worker deployments (e.g., gunicorn with multiple workers) will have isolated
   caches — a summary started in one worker returns 404 when polled by another. The cache also
   evicts entries after 300 seconds by default.

1. **No thread synchronization on handler state.** `LlmResponseHandler.content` is written by the
   executor thread and read by the watcher thread without locks. This relies on CPython's GIL for
   safety and would break on alternative Python implementations.

1. **Linter configs appear missing, not intentionally absent.** `ruff`, `flake8`, and `pre-commit`
   are dev dependencies but have no configuration files. Do not assume code style rules are
   enforced — they are not.

## Deployment

The project is published to PyPI via trusted OIDC publishing on tag push (see
`.github/workflows/release.yml`). Artifacts are signed with Sigstore and attached to GitHub
Releases.

A `Dockerfile` is provided for container builds, based on `registry.access.redhat.com/ubi9/python-312`.
The container runs as non-root (UID 1001) and is OpenShift-compatible. LLM credentials must be
injected as environment variables at runtime.

[readme-dev]: ./README.md#development
[architecture]: ./ARCHITECTURE.md
