import requests
import json
import os
import sys
import re


WEBRCA_TOKEN = os.environ.get("WEBRCA_TOKEN")

BASE_URL = "https://api.openshift.com/api/web-rca/v1"


def _get(api_path: str, params: dict) -> requests.Response:
    url = f"{BASE_URL}{api_path}"
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
    _filter_by_keys(incident["incident_owner"], ("name",))
    for participant in incident.get("participants", {}):
        _filter_by_keys(participant, ("name",))


def _cleanup_event_note(text):
    # make sure code block syntax is surrounded by newlines
    text = re.sub('```', '\n```\n', text)

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

        if event.get("note"):
            # remove code blocks from notes
            event["note"] = _cleanup_event_note(event["note"])

        if event.get("creator"):
            creator_keys = ("name", "email")
            _filter_by_keys(event["creator"], creator_keys)
            if not event["creator"]:
                # sometimes after filtering, no "desired keys" are left
                del event["creator"]


def get_incident(public_id):
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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <incident id>")
        sys.exit(1)

    public_id = sys.argv[1]
    output = json.dumps(get_incident(public_id), indent=2)
    print(output)
    print("chars: ", len(output))
