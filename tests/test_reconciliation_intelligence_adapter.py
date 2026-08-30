"""Tests for reconciliation.adapters.intelligence_adapter (Stage 4 — pure translation, no I/O)."""
from __future__ import annotations

import pytest

from reconciliation.adapters.intelligence_adapter import (
    INTEL_TYPE_TO_COLLECTION,
    adapt_all,
    dispatch_record_to_library_object,
)
from reconciliation.contracts import LibraryObjectSource


def _record(**overrides):
    base = {
        "id": "INT-LOC-0001",
        "intel_type": "location",
        "subject": "Jacksonville Port Terminal 4",
        "content": "Gate opens 6am, requires TWIC",
        "source": "driver_note",
        "metadata": {},
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


def test_every_dispatch_intel_type_has_a_collection_mapping():
    # portal/models/intelligence.py's real INTEL_TYPES, hardcoded so this fails loudly if
    # Dispatch's list changes without this adapter being updated.
    real_intel_types = {"location", "broker", "customer", "route", "position", "market"}
    assert real_intel_types <= set(INTEL_TYPE_TO_COLLECTION)


def test_location_maps_to_location_intelligence_collection():
    obj = dispatch_record_to_library_object(_record())
    assert obj.collection == "Location_Intelligence"
    assert obj.title == "Jacksonville Port Terminal 4"


def test_route_maps_to_route_intelligence_collection():
    obj = dispatch_record_to_library_object(
        _record(id="INT-ROU-0001", intel_type="route", subject="I-95 corridor")
    )
    assert obj.collection == "Route_Intelligence"


def test_position_and_market_map_to_reference():
    position = dispatch_record_to_library_object(_record(id="INT-POS-0001", intel_type="position"))
    market = dispatch_record_to_library_object(_record(id="INT-MAR-0001", intel_type="market"))
    assert position.collection == "Reference"
    assert market.collection == "Reference"


def test_unknown_intel_type_raises_rather_than_guessing():
    with pytest.raises(ValueError, match="no mapping"):
        dispatch_record_to_library_object(_record(intel_type="not_a_real_type"))


def test_never_claims_a_verified_human_approver():
    obj = dispatch_record_to_library_object(_record())
    assert "UNKNOWN" in obj.accepted_by
    assert obj.source == LibraryObjectSource.LEGACY_UNVERIFIED_ORIGIN


def test_source_tag_preserved_in_tags():
    obj = dispatch_record_to_library_object(_record())
    assert "dispatch_source:driver_note" in obj.tags
    assert "dispatch_intel_type:location" in obj.tags


def test_adapt_all_processes_every_intel_type():
    data = {
        "location": [_record(id="INT-LOC-0001")],
        "broker": [_record(id="INT-BRO-0001", intel_type="broker", subject="BlueHorizon")],
    }
    results = adapt_all(data)
    assert len(results) == 2
    assert {r.object_code for r in results} == {"INT-LOC-0001", "INT-BRO-0001"}
