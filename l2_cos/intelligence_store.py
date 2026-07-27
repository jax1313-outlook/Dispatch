"""Operational Intelligence Libraries loader (System Rule 14).

Loads Location and Broker intelligence once — from local sample data by
default, or from the archived library once persisted (see
l2_cos/archive.py:store_location / store_broker) — and serves lookups by id
to acquisition, processing, and dispatch alike. No layer re-derives facility
or broker facts per load; they read this shared store instead.
"""

from __future__ import annotations

import json
from pathlib import Path

from l2_cos.models.intelligence import BrokerIntelligence, LocationIntelligence

SAMPLE_DIR = Path(__file__).resolve().parent / "sample_data"


def load_facilities(path: Path | None = None) -> dict[str, LocationIntelligence]:
    """id -> LocationIntelligence, keyed for O(1) lookup by rule modules."""
    path = path or SAMPLE_DIR / "facilities.json"
    if not path.exists():
        return {}
    records = json.loads(path.read_text(encoding="utf-8"))
    return {r["facility_id"]: LocationIntelligence(**r) for r in records}


def load_brokers(path: Path | None = None) -> dict[str, BrokerIntelligence]:
    """id -> BrokerIntelligence, keyed for O(1) lookup by rule modules."""
    path = path or SAMPLE_DIR / "brokers.json"
    if not path.exists():
        return {}
    records = json.loads(path.read_text(encoding="utf-8"))
    return {r["broker_id"]: BrokerIntelligence(**r) for r in records}
