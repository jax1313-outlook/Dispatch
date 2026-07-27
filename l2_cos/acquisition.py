"""Acquisition Layer — L2-COS Dispatch.

Cloned from cin_lite/acquisition.py (Rule 15): fetches load records from a
configured source and maps each into the pipeline's load shape so it flows
through the deterministic rule modules unchanged. When no source is
configured it falls back to local sample data, so the pipeline still runs
offline.

`L2_COS_LOAD_BOARD_URL` / `L2_COS_LOAD_BOARD_API_KEY` are a generic,
provider-agnostic HTTP adapter — NOT a specific load board's real schema.
Point them at whatever load-board or broker TMS API you integrate (DAT,
Truckstop, a private broker feed, ...) and adjust `_map_load` below to that
provider's actual field names. The adapter expects a JSON envelope shaped
`{"loads": [...]}` and a bearer-token `Authorization` header; adjust both to
match the real provider before pointing this at production traffic.

Configuration (environment):
    L2_COS_LOAD_BOARD_URL        search endpoint (its presence enables the live adapter)
    L2_COS_LOAD_BOARD_API_KEY    sent as `Authorization: Bearer <key>`
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SAMPLE_DIR = Path(__file__).resolve().parent / "sample_data"
# Intelligence-library files live alongside load samples but aren't loads themselves.
_EXCLUDED_SAMPLE_FILES = {"facilities.json", "brokers.json", "carrier_documents.json"}


def acquire() -> list[dict]:
    """Return raw load dicts from the configured source (load board or local)."""
    url = os.environ.get("L2_COS_LOAD_BOARD_URL")
    if url:
        print("Acquisition: live load-board adapter")
        return _acquire_load_board(url)
    print("Acquisition: local sample_data (set L2_COS_LOAD_BOARD_URL for a live load board)")
    return _acquire_local()


# --------------------------------------------------------------------------- local

def _acquire_local() -> list[dict]:
    loads: list[dict] = []
    for path in sorted(SAMPLE_DIR.glob("*.json")):
        if path.name in _EXCLUDED_SAMPLE_FILES:
            continue
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        data.setdefault("_source_file", path.name)
        loads.append(data)
    return loads


# --------------------------------------------------------------------------- load board

def _http_get(url: str, api_key: str | None) -> bytes:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _acquire_load_board(url: str) -> list[dict]:
    api_key = os.environ.get("L2_COS_LOAD_BOARD_API_KEY")
    try:
        body = _http_get(url, api_key)
        data = json.loads(body)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        print(f"l2_cos: load-board request failed (HTTP {exc.code}): {detail}", file=sys.stderr)
        print("l2_cos: falling back to local sample_data.", file=sys.stderr)
        return _acquire_local()
    except Exception as exc:  # network/parse failure — keep the pipeline running
        print(f"l2_cos: load-board acquisition failed ({exc}); falling back to local.", file=sys.stderr)
        return _acquire_local()

    raw_loads = data.get("loads", [])
    return [_map_load(raw) for raw in raw_loads]


def _map_load(raw: dict) -> dict:
    """Map one provider load record into the pipeline's load shape.

    Adjust the right-hand field names here to match the configured
    provider's actual schema.
    """
    load_id = raw.get("load_id") or raw.get("id", "")
    return {
        "load_id": load_id,
        "origin": raw.get("origin"),
        "destination": raw.get("destination"),
        "origin_state": raw.get("origin_state"),
        "destination_state": raw.get("destination_state"),
        "miles": raw.get("miles"),
        "deadhead_miles": raw.get("deadhead_miles"),
        "equipment_type": raw.get("equipment_type"),
        "rate_total": raw.get("rate_total"),
        "rate_per_mile": raw.get("rate_per_mile"),
        "weight_lbs": raw.get("weight_lbs"),
        "pickup_facility_id": raw.get("pickup_facility_id"),
        "delivery_facility_id": raw.get("delivery_facility_id"),
        "broker_id": raw.get("broker_id"),
        "pickup_date": raw.get("pickup_date"),
        "delivery_date": raw.get("delivery_date"),
        "notes": raw.get("notes", ""),
        "_source_file": f"load-board/{load_id}" if load_id else "load-board",
    }
