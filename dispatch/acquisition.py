"""Dispatch Acquisition Layer.

Normalizes load board data into a consistent load shape for the scoring
engine and sandbox.  Follows the same pattern as cin_lite.acquisition:
acquire() -> list[dict], with a configurable live source + local fallback.

Each load is mapped into the dispatch load shape:
    load_id, title, origin, destination, distance_miles, rate, rpm,
    pickup_window, delivery_window, equipment_required, equipment_match,
    weight_lbs, broker, broker_email, broker_phone, source_link,
    detention_history, location_intelligence, broker_intelligence, notes

Configuration (environment):
    DISPATCH_LOAD_SOURCE       path to a directory of JSON load files
                               (default: portal/sample_dispatch_data)
    DISPATCH_LOAD_API_URL      future: URL for a load board API endpoint
    DISPATCH_LOAD_API_KEY      future: API key for the load board endpoint
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


_DEFAULT_SAMPLE_DIR = Path(__file__).resolve().parent.parent / "portal" / "sample_dispatch_data"

_REQUIRED_FIELDS = {"load_id"}

_LOAD_SHAPE_FIELDS = [
    "load_id", "title", "origin", "destination", "distance_miles",
    "rate", "rpm", "pickup_window", "delivery_window",
    "equipment_required", "equipment_match", "weight_lbs",
    "broker", "broker_email", "broker_phone", "source_link",
    "hard_stop", "hard_stop_reason",
    "detention_history", "location_intelligence", "broker_intelligence",
    "notes",
]


#: Origin of a record, in the repository's fixed status vocabulary.
#: SIMULATED means bundled sample data -- never to be shown as if it were real.
ORIGIN_SIMULATED = "SIMULATED"
ORIGIN_LIVE = "LIVE"


def acquire() -> list[dict]:
    """Return normalized load dicts from the configured source.

    Every record carries `data_origin`. Records read from the bundled sample
    directory are `SIMULATED`; records from a source the operator configured are
    `LIVE`. Nothing downstream has to guess, and no surface can show sample
    freight as though it were real -- `CLAUDE.md` §6.
    """
    api_url = os.environ.get("DISPATCH_LOAD_API_URL")
    if api_url:
        return _acquire_api(api_url)
    source_dir = _get_source_dir()
    return _acquire_local(source_dir)


def _origin_for(source_dir: Path) -> str:
    """Bundled samples are SIMULATED. A configured directory is LIVE."""
    try:
        return ORIGIN_SIMULATED if Path(source_dir).resolve() == _DEFAULT_SAMPLE_DIR.resolve() else ORIGIN_LIVE
    except OSError:
        return ORIGIN_LIVE


def _get_source_dir() -> Path:
    env_dir = os.environ.get("DISPATCH_LOAD_SOURCE")
    if env_dir:
        return Path(env_dir)
    return _DEFAULT_SAMPLE_DIR


def _acquire_local(source_dir: Path, origin: str | None = None) -> list[dict]:
    """Load and normalize JSON files from a directory.

    One malformed or wrongly-shaped file (invalid JSON, or valid JSON whose
    top level isn't an object) must not abort every other load in the
    directory -- skip and log the offending file, keep going.
    """
    loads: list[dict] = []
    origin = origin or _origin_for(source_dir)
    if not source_dir.exists():
        return loads
    for path in sorted(source_dir.glob("*.json")):
        try:
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError(f"expected a JSON object, got {type(data).__name__}")
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            print(f"[dispatch.acquisition] skipping {path.name}: {exc}", file=sys.stderr)
            continue
        data.setdefault("_source_file", path.name)
        record = _normalize(data)
        record["data_origin"] = origin
        loads.append(record)
    return loads


def _acquire_api(api_url: str) -> list[dict]:
    """Fetch loads from a load board API endpoint.

    Expects a JSON response with a top-level list of load objects, or
    a dict with a "loads" key containing the list.  Falls back to local
    sample data on failure.
    """
    import sys
    import urllib.error
    import urllib.request

    api_key = os.environ.get("DISPATCH_LOAD_API_KEY", "")
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(api_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
    except Exception as exc:
        # The source was UNAVAILABLE. Returning bundled samples as though the
        # call had succeeded is the fabrication v1.0.1 shipped and v1.1 removed;
        # the records come back explicitly SIMULATED instead.
        print(
            f"dispatch: load board API UNAVAILABLE ({exc}); "
            "returning bundled SIMULATED samples, not live loads",
            file=sys.stderr,
        )
        return _acquire_local(_get_source_dir(), origin=ORIGIN_SIMULATED)

    if isinstance(body, list):
        raw_loads = body
    elif isinstance(body, dict):
        raw_loads = body.get("loads", body.get("data", []))
    else:
        raw_loads = []

    return [dict(_normalize(load), data_origin=ORIGIN_LIVE) for load in raw_loads]


def _normalize(data: dict) -> dict:
    """Ensure the load dict has all expected fields with sensible defaults."""
    normalized = {}
    for field in _LOAD_SHAPE_FIELDS:
        normalized[field] = data.get(field)

    if not normalized.get("load_id"):
        normalized["load_id"] = data.get("id", "UNKNOWN")

    if not normalized.get("title"):
        parts = []
        if normalized.get("equipment_required"):
            parts.append(normalized["equipment_required"].split()[0])
        else:
            parts.append("Load")
        origin = (normalized.get("origin") or "").split(",")[0]
        dest = (normalized.get("destination") or "").split(",")[0]
        if origin and dest:
            parts.append(f"- {origin} to {dest}")
        normalized["title"] = " ".join(parts)

    for key in data:
        if key.startswith("_"):
            normalized[key] = data[key]

    return normalized
