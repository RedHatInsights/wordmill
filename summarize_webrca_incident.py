import concurrent.futures
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone

import click
import mdformat
import requests
from rich.console import Console
from rich.logging import RichHandler
from rich.spinner import Spinner
from rich.traceback import install

from summairizer.llm import llm_client

WEBRCA_V1_API_BASE_URL = os.environ.get(
    "WEBRCA_V1_API_BASE_URL", "https://api.openshift.com/api/web-rca/v1"
).lstrip("/")
WEBRCA_TOKEN = os.environ.get("WEBRCA_TOKEN")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", 1))


log = logging.getLogger(__name__)


def _get(api_path: str, params: dict = None) -> dict:
    url = f"{WEBRCA_V1_API_BASE_URL}{api_path}"
    headers = {"Authorization": f"Bearer {WEBRCA_TOKEN}"}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()


def _patch(api_path: str, json_data: dict) -> dict:
    url = f"{WEBRCA_V1_API_BASE_URL}{api_path}"
    headers = {"Authorization": f"Bearer {WEBRCA_TOKEN}"}
    response = requests.patch(url, headers=headers, json=json_data)
    response.raise_for_status()
    return response.json()


def _get_all_items(api_path: str, params: dict = None) -> dict:
    items = []
    page = 1
    if not params:
        params = {"page": page}

    while True:
        params["page"] = page
        data = _get(api_path, params)
        items.extend(data["items"])
        log.debug(
            "fetched page %d, fetched items %d, current items %d",
            page,
            len(items),
            data["total"],
        )
        if len(items) >= data["total"]:
            break
        page += 1

    return items


def _filter_by_keys(d: dict, desired_keys: list[str]) -> None:
    for key in list(d.keys()):
        if key not in desired_keys:
            del d[key]


def _cleanup_event_note(text: str) -> str:
    # make sure code block syntax is surrounded by newlines
    text = re.sub("```", "\n```\n", text)

    # remove dynatrace links, they are often really large
    text = re.sub(r"\S+http(s?):\/\/\S+dynatrace\S+", "[dynatrace url]", text)

    # remove hyperlinks and just display plain text
    text = re.sub(r"<(\S+)\|([^\r\n\t\f\v]+)>", r"\2", text)

    # remove multi-line code blocks, they are often large log outputs
    lines = []
    in_code_block = False
    for line in text.split("\n"):
        if line == "```" and not in_code_block:
            in_code_block = True
            # remove text within code block, but preserve indentation of the block
            whitespace = " " * (len(line) - len(line.lstrip()))
            lines.append(f"{whitespace}[code block/log snippet]")
        elif in_code_block:
            if line == "```":
                in_code_block = False
            continue
        else:
            lines.append(line)

    return "\n".join(lines)


def _parse_events(events: list[dict]) -> None:
    desired_keys = ("note", "creator", "created_at", "updated_at")

    for event in events:
        _filter_by_keys(event, desired_keys)

        if "note" in event:
            # remove code blocks from notes
            event["note"] = _cleanup_event_note(event["note"])

        if "creator" in event:
            creator_keys = ("name", "email")
            _filter_by_keys(event["creator"], creator_keys)
            if not event["creator"]:
                # sometimes after filtering, no "desired keys" are left
                del event["creator"]


def _filter_keys(incident: dict) -> None:
    desired_keys = (
        "id",
        "summary",
        "description",
        "incident_id",
        "products",
        "status",
        "external_coordination",
        "created_at",
        "resolved_at",
        "private",
        "creator",
        "incident_owner",
        "participants",
    )
    _filter_by_keys(incident, desired_keys)
    _filter_by_keys(incident["creator"], ("name",))
    if "incident_owner" in incident:
        _filter_by_keys(incident["incident_owner"], ("name",))
    for participant in incident.get("participants", {}):
        _filter_by_keys(participant, ("name",))


def _process_incident(incident: dict) -> dict:
    public_id = incident["incident_id"]
    log.info("Processing incident '%s' ...", public_id)

    incident_id = incident["id"]

    api_path = f"/incidents/{incident_id}/events"
    params = {
        "order_by": "occurred_at desc",
        "page": 1,
        "size": 999,
    }

    _filter_keys(incident)

    log.info("Fetching events for incident '%s' ...", public_id)
    events = _get_all_items(api_path, params)
    if events:
        _parse_events(events)

    incident["events"] = events

    log.info("Incident '%s' num events: %d", public_id, len(events))

    return incident


def get_incident(public_id: str) -> dict:
    log.info("Fetching incident '%s' from WebRCA...", public_id)

    api_path = f"/incidents"
    params = {"public_id": public_id}
    items = _get(api_path, params).get("items", [])

    if not items:
        raise ValueError(f"incident {public_id} not found")

    incident = items[0]

    return incident


def get_all_incidents() -> dict:
    api_path = f"/incidents"
    return _get_all_items(api_path)


def _wait_with_spinner(console, handler):
    time.sleep(0.1)  # allow HTTP POST log to print before spinner
    text = "[magenta]Waiting on LLM response... (bytes received: {bytes_received})[/magenta]"

    spinner = Spinner("aesthetic", text=text.format(bytes_received=0))
    with console.status(spinner):
        while not handler.done:
            bytes_received = len(handler.content.encode("utf-8"))
            spinner.update(text=text.format(bytes_received=bytes_received))
            time.sleep(0.1)


def summarize_incident(prompt, incident, console=None):
    incident = _process_incident(incident)
    as_json = json.dumps(incident)

    log.info(
        "Requesting LLM to summarize... prompt size: %d chars, context size: %d chars",
        len(prompt),
        len(as_json),
    )

    start_time = time.perf_counter()
    handler = llm_client.summarize(as_json, prompt=prompt)

    if console:
        _wait_with_spinner(console, handler)
    else:
        while not handler.done:
            time.sleep(0.1)
        bytes_received = len(handler.content.encode("utf-8"))
        log.info("Summary generated, %d bytes received", bytes_received)

    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    log.info(
        f"Summary successfully generated (time elapsed: {elapsed_time:.4f} seconds)"
    )

    try:
        md = mdformat.text(handler.content)
    except Exception as err:
        log.warning("mdformat failed: %s, markdown may contain syntax errors", err)
        md = handler.content

    return md


def summarize_incident_and_update_webrca(prompt, incident, console=None):
    threading.current_thread().name = incident["incident_id"]

    summary_md = summarize_incident(prompt, incident, console)

    incident_uuid = incident["id"]
    api_path = f"/incidents/{incident_uuid}"
    _patch(api_path, json_data={"ai_summary": summary_md})


def _get_incidents_to_update(max_days_since_update: int) -> list[dict]:
    if max_days_since_update:
        since_time = datetime.now(tz=timezone.utc) - timedelta(
            days=max_days_since_update
        )
    else:
        since_time = datetime.min.replace(tzinfo=timezone.utc)

    incidents = get_all_incidents()

    incidents_to_update = []

    for incident in incidents:
        id = incident["id"]
        updated_time = datetime.fromisoformat(incident["updated_at"])
        ai_summary_updated_at = incident.get("ai_summary_updated_at")
        if ai_summary_updated_at:
            ai_summary_updated_time = datetime.fromisoformat(ai_summary_updated_at)
        else:
            ai_summary_updated_time = datetime.min.replace(tzinfo=timezone.utc)

        if updated_time < since_time:
            log.debug(
                "incident %s last updated more than %d days ago, skipping",
                id,
                max_days_since_update,
            )
        elif updated_time > ai_summary_updated_time:
            log.debug("incident %s needs AI summary updated", id)
            incidents_to_update.append(incident)
        else:
            log.debug("incident %s summary up-to-date")

    return incidents_to_update


def load_prompt():
    with open("summarize_webrca_incident_prompt.txt") as fp:
        return fp.read()


@click.group()
def cli():
    install(show_locals=True)
    logging.basicConfig(
        level=LOG_LEVEL,
        format="(%(threadName)14s) %(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )


@cli.command(help="generate summary for a single incident")
@click.option(
    "--id", required=True, help="incident public ID (example: ITN-2025-00096)"
)
def generate(id):
    console = Console()

    incident = get_incident(id)
    summary_md = summarize_incident(load_prompt(), incident, console)

    console.rule("AI-generated Summary")
    console.print(summary_md)


@cli.command(help="generate summaries for all incidents and update web-rca")
@click.option(
    "--since",
    "max_days_since_update",
    type=int,
    help="summarize only if updated_at is less than N days old",
)
def worker(max_days_since_update):
    incidents_to_update = _get_incidents_to_update(max_days_since_update)
    prompt = load_prompt()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)

    errors = 0
    successes = 0

    future_to_incident = {}
    for incident in incidents_to_update:
        future = executor.submit(summarize_incident_and_update_webrca, prompt, incident)
        future_to_incident[future] = incident["incident_id"]

    for future in concurrent.futures.as_completed(future_to_incident):
        incident_id = future_to_incident[future]
        try:
            future.result()
        except Exception as exc:
            log.error("summarization failed for incident %s", incident_id)
            errors += 1
        else:
            log.info("summarization successful for incident %s", incident_id)
            successes += 1

    log.info(
        "incident summarization worker completed (%d errors, %d successes)",
        errors,
        successes,
    )


if __name__ == "__main__":
    cli()
