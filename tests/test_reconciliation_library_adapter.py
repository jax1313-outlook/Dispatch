"""Tests for reconciliation.adapters.library_adapter (Stage 4 — pure translation, no I/O)."""
from __future__ import annotations

import pytest

from reconciliation.adapters.library_adapter import (
    SECTION_TO_COLLECTION,
    UNKNOWN_APPROVER,
    adapt_all,
    dispatch_record_to_library_object,
)
from reconciliation.contracts import LibraryObjectSource, LibraryObjectStatus


def _record(**overrides):
    base = {
        "id": "LIB-COM-0001",
        "section": "company",
        "name": "W-9",
        "content": "W-9 on file",
        "metadata": {},
        "status": "approved",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


def test_every_dispatch_section_has_a_collection_mapping():
    # These are portal/models/library.py's real SECTIONS values, hardcoded here so this test
    # fails loudly if Dispatch's SECTIONS list ever changes without this adapter being updated.
    real_dispatch_sections = {
        "company", "broker", "customer", "location_intelligence", "operations", "intelligence",
    }
    assert real_dispatch_sections <= set(SECTION_TO_COLLECTION)


def test_translates_known_section_to_matching_collection():
    obj = dispatch_record_to_library_object("company", _record())
    assert obj.collection == "Company"
    assert obj.object_code == "LIB-COM-0001"
    assert obj.title == "W-9"
    assert obj.body_or_uri == "W-9 on file"


def test_intelligence_section_maps_to_reference():
    obj = dispatch_record_to_library_object("intelligence", _record(id="LIB-INT-0001"))
    assert obj.collection == "Reference"


def test_unknown_section_raises_rather_than_guessing():
    with pytest.raises(ValueError, match="no mapping"):
        dispatch_record_to_library_object("not_a_real_section", _record())


def test_never_claims_a_verified_human_approver():
    # Dispatch's data has no field recording who approved a record. The adapter must not
    # invent one -- it must say so explicitly.
    obj = dispatch_record_to_library_object("company", _record())
    assert obj.accepted_by == UNKNOWN_APPROVER
    assert "UNKNOWN" in obj.accepted_by


def test_source_is_legacy_not_human_placed():
    # Claiming HUMAN_PLACED would assert a fact (a human explicitly reviewed and placed this)
    # that Dispatch's schema does not establish.
    obj = dispatch_record_to_library_object("company", _record())
    assert obj.source == LibraryObjectSource.LEGACY_UNVERIFIED_ORIGIN
    assert obj.status == LibraryObjectStatus.CURRENT


def test_adapt_all_processes_every_section():
    data = {
        "company": [_record(id="LIB-COM-0001")],
        "broker": [_record(id="LIB-BRO-0001", section="broker")],
    }
    results = adapt_all(data)
    assert len(results) == 2
    assert {r.object_code for r in results} == {"LIB-COM-0001", "LIB-BRO-0001"}


def test_adapt_all_is_pure_no_file_io(tmp_path, monkeypatch):
    # Point Dispatch's data dir somewhere that doesn't exist; adapt_all must not touch disk at
    # all, so this must not raise even though the path is bogus.
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "does-not-exist"))
    results = adapt_all({"company": [_record()]})
    assert len(results) == 1
