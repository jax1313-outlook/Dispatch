"""Operations Portal — read layer over the Archive tree.

The Archive (l2_cos/archive.py) is the underlying system of record; this
module never holds load state itself, it only re-reads what's already been
persisted there (Processed, Intelligence, Dispatch, Publisher) and resolves
each load's facility/broker records from the Operational Intelligence
Libraries. Cards, Briefs, Drafts, and the Source view are all built from the
same `LoadBundle`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

from l2_cos import archive, intelligence_store
from l2_cos.models.intelligence import BrokerIntelligence, LocationIntelligence
from l2_cos.models.state import Load


class LoadBundle(NamedTuple):
    load_id: str
    raw_load: dict
    intelligence: dict
    overall_score: int
    load: Load
    facility_pickup: LocationIntelligence | None
    facility_delivery: LocationIntelligence | None
    broker: BrokerIntelligence | None
    publisher_result: dict | None


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_ids() -> list[str]:
    processed_dir = archive.ARCHIVE_ROOT / "Processed"
    if not processed_dir.exists():
        return []
    return sorted(p.stem for p in processed_dir.glob("*.json"))


def get_load_bundle(load_id: str) -> LoadBundle | None:
    """Assemble one load's full bundle from the Archive, or None if this
    load_id has no Processed record (i.e. it was never run through the
    pipeline)."""
    processed = _read_json(archive.ARCHIVE_ROOT / "Processed" / f"{load_id}.json")
    if processed is None:
        return None

    raw_load = processed["load"]
    intelligence = _read_json(archive.ARCHIVE_ROOT / "Intelligence" / f"{load_id}.json") or {}
    dispatch = _read_json(archive.ARCHIVE_ROOT / "Dispatch" / f"{load_id}.json")
    load = Load(**dispatch) if dispatch else Load(load_id=load_id, broker_id=raw_load.get("broker_id"))
    publisher_result = _read_json(archive.ARCHIVE_ROOT / "Publisher" / f"{load_id}.json")

    facilities = intelligence_store.load_facilities()
    brokers = intelligence_store.load_brokers()

    return LoadBundle(
        load_id=load_id,
        raw_load=raw_load,
        intelligence=intelligence,
        overall_score=processed["metadata"].get("overall_score", 0),
        load=load,
        facility_pickup=facilities.get(raw_load.get("pickup_facility_id")),
        facility_delivery=facilities.get(raw_load.get("delivery_facility_id")),
        broker=brokers.get(raw_load.get("broker_id")),
        publisher_result=publisher_result,
    )


def list_load_bundles() -> list[LoadBundle]:
    """Every load currently in the Archive, for the Cards view."""
    bundles = []
    for load_id in _load_ids():
        bundle = get_load_bundle(load_id)
        if bundle is not None:
            bundles.append(bundle)
    return bundles


def list_publisher_results() -> list[dict]:
    """Every publisher/auto-contact result on file, for the Sandbox Tracking view."""
    publisher_dir = archive.ARCHIVE_ROOT / "Publisher"
    if not publisher_dir.exists():
        return []
    return [
        json.loads(path.read_text(encoding="utf-8")) for path in sorted(publisher_dir.glob("*.json"))
    ]
