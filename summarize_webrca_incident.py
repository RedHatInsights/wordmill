import json
import logging
import os
import re
import sys
import time

import mdformat
import requests
from rich.console import Console
from rich.json import JSON
from rich.logging import RichHandler
from rich.markdown import Markdown
from rich.spinner import Spinner
from rich.traceback import install

from summairizer.llm import llm_client

WEBRCA_V1_API_BASE_URL = os.environ.get(
    "WEBRCA_V1_API_BASE_URL", "https://api.openshift.com/api/web-rca/v1"
).lstrip("/")
WEBRCA_TOKEN = os.environ.get("WEBRCA_TOKEN")


log = logging.getLogger(__name__)


def _get(api_path: str, params: dict) -> dict:
    url = f"{WEBRCA_V1_API_BASE_URL}{api_path}"
    headers = {"Authorization": f"Bearer {WEBRCA_TOKEN}"}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()


def _filter_by_keys(d: dict, desired_keys: list[str]) -> None:
    for key in list(d.keys()):
        if key not in desired_keys:
            del d[key]


def _parse_incident(incident: dict) -> None:
    desired_keys = (
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


def get_incident(public_id: str) -> dict:
    api_path = f"/incidents"
    params = {"public_id": public_id}
    items = _get(api_path, params).get("items", [])

    if not items:
        raise ValueError(f"incident {public_id} not found")
    incident = items[0]

    incident_id = incident["id"]
    api_path = f"/incidents/{incident_id}/events"
    params = {
        "order_by": "occurred_at desc",
        "page": 1,
        "size": 999,
    }

    _parse_incident(incident)

    # TODO: handle pagination
    events = _get(api_path, params).get("items", [])
    if events:
        _parse_events(events)

    incident["events"] = events

    return incident


def main():
    install(show_locals=True)
    console = Console()

    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <incident id>")
        sys.exit(1)

    public_id = sys.argv[1]

    logging.basicConfig(
        level="INFO",
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )

    with open("summarize_webrca_incident_prompt.txt") as fp:
        prompt = fp.read()

    log.info(f"Fetching incident <{public_id}> from WebRCA...")
    incident = get_incident(public_id)
    as_json = json.dumps(incident)
    events = incident.get("events") or []
    log.info(
        f"Success, num events: {len(events)}, processed size: {len(as_json)} chars"
    )

    log.info("Requesting LLM to summarize...")

    start_time = time.perf_counter()
    handler = llm_client.summarize(as_json, prompt=prompt)
    time.sleep(0.1)  # allow HTTP POST log to print before spinner
    spinner = Spinner(
        "aesthetic", text="[magenta]Waiting on LLM response... [/magenta]"
    )
    with console.status(spinner):
        while not handler.done:
            bytes_received = len(handler.content.encode("utf-8"))
            spinner.update(
                text=f"[magenta]Waiting on LLM response... (bytes received: {bytes_received})[/magenta]"
            )
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

    md = Markdown(md)

    console.rule("AI-generated Summary")
    console.print(md)


if __name__ == "__main__":
    main()
