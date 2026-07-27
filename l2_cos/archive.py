"""Archive Layer — L2-COS Dispatch.

Cloned from cin_lite/archive.py (Rule 15). Assigns each load a unique
`LOAD-YYYYMMDD-<hash>` ID and persists raw/processed/intelligence artifacts
plus the dispatch (lifecycle) record into the Archive folder tree. Also
persists the two Operational Intelligence Libraries (System Rule 14) —
Locations and Brokers — each captured once and reused, never duplicated per
load.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from l2_cos.models.intelligence import BrokerIntelligence, LocationIntelligence
from l2_cos.models.state import Load

ARCHIVE_ROOT = Path(__file__).resolve().parent / "Archive"
_SUBDIRS = ("Raw", "Processed", "Intelligence", "Dispatch", "Locations", "Brokers")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_tree() -> None:
    for sub in _SUBDIRS:
        (ARCHIVE_ROOT / sub).mkdir(parents=True, exist_ok=True)


def make_id(load: dict) -> str:
    """Deterministic, human-readable unique ID: LOAD-YYYYMMDD-<8 hex>."""
    seed = str(load.get("load_id") or repr(load))
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8].upper()
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"LOAD-{day}-{digest}"


def _write_json(subdir: str, key: str, payload: Any) -> Path:
    path = ARCHIVE_ROOT / subdir / f"{key}.json"
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)
    return path


def store(load: dict, intelligence: dict, overall_score: int) -> dict:
    """Persist raw/processed/intelligence for one load; return the metadata bundle."""
    ensure_tree()
    load_id = make_id(load)

    metadata = {
        "load_id": load_id,
        "source": load.get("_source_file", "unknown"),
        "origin": load.get("origin"),
        "destination": load.get("destination"),
        "broker_id": load.get("broker_id"),
        "processed_at": _utc_now(),
        "overall_score": overall_score,
        "flag_count": sum(len(r.get("flags", [])) for r in intelligence.values()),
    }

    _write_json("Raw", load_id, load)
    _write_json("Processed", load_id, {"metadata": metadata, "load": load})
    _write_json("Intelligence", load_id, intelligence)

    return metadata


def record_dispatch(load: Load) -> Path:
    """Persist the load's current stage plus its full transition history."""
    ensure_tree()
    payload = json.loads(load.model_dump_json())
    return _write_json("Dispatch", load.load_id, payload)


def store_location(facility: LocationIntelligence) -> Path:
    """Persist one Location Intelligence Library entry (capture once)."""
    ensure_tree()
    return _write_json("Locations", facility.facility_id, json.loads(facility.model_dump_json()))


def store_broker(broker: BrokerIntelligence) -> Path:
    """Persist one Broker Intelligence Library entry (capture once)."""
    ensure_tree()
    return _write_json("Brokers", broker.broker_id, json.loads(broker.model_dump_json()))
