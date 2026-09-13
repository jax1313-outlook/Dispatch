"""The Portal's own JSON stores live in the portal data directory, never in the Library shelf.

Owner ruling, Mike Zachary, 2026-09-13: DISPATCH_MEMORY_ROOT (D:\\Memory) is the Library
Department's physical shelf. Intelligence records and the driver PIN registry -- a credential
store -- used to be written into it. These tests hold them out of it, and prove that a file an
earlier version left in the shelf is still read (so no driver loses a PIN card) and never modified.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from portal.models import StoreInShelfError, get_store_dir, legacy_shelf_store


@pytest.fixture()
def roots(tmp_path, monkeypatch):
    memory = tmp_path / "Memory"
    data = tmp_path / "PortalData"
    memory.mkdir()
    monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(memory))
    monkeypatch.setenv("PORTAL_DATA_DIR", str(data))
    return memory, data


def _listing(root):
    return sorted((p.name, hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                  for p in root.iterdir())


def test_the_store_directory_is_the_portal_data_directory(roots):
    memory, data = roots
    assert get_store_dir() == data


def test_the_store_directory_refuses_to_be_the_shelf(roots, monkeypatch):
    memory, _ = roots
    monkeypatch.setenv("PORTAL_DATA_DIR", str(memory))
    with pytest.raises(StoreInShelfError):
        get_store_dir()


def test_intelligence_records_stay_out_of_the_shelf(roots):
    from portal.models import intelligence

    memory, data = roots
    intelligence.create_record("broker", "Tidewater Logistics", "Quick pay")
    assert (data / "intelligence.json").is_file()
    assert list(memory.iterdir()) == []


def test_the_driver_pin_registry_stays_out_of_the_shelf(roots):
    from portal.models import driver_pin_registry

    memory, data = roots
    driver_pin_registry._save({"DRV-1": {"driver_id": "DRV-1", "pin_hash": "x", "status": "active"}})
    assert (data / "driver_pin_registry.json").is_file()
    assert list(memory.iterdir()) == []
    assert driver_pin_registry.get_pin_card("DRV-1")["status"] == "active"
    assert "pin_hash" not in driver_pin_registry.get_pin_card("DRV-1")


def test_a_registry_left_in_the_shelf_is_read_and_never_modified(roots):
    from portal.models import driver_pin_registry

    memory, data = roots
    left = {"DRV-OLD": {"driver_id": "DRV-OLD", "pin_hash": "old", "status": "active"}}
    (memory / "driver_pin_registry.json").write_text(json.dumps(left), encoding="utf-8")
    before = _listing(memory)

    assert driver_pin_registry.get_pin_card("DRV-OLD")["status"] == "active", "an existing card must survive the move"
    data_now = driver_pin_registry._load()
    data_now["DRV-NEW"] = {"driver_id": "DRV-NEW", "pin_hash": "new", "status": "active"}
    driver_pin_registry._save(data_now)

    assert set(json.loads((data / "driver_pin_registry.json").read_text(encoding="utf-8"))) == {"DRV-OLD", "DRV-NEW"}
    assert _listing(memory) == before, "the file in the shelf was modified"
    assert set(driver_pin_registry._load()) == {"DRV-OLD", "DRV-NEW"}


def test_intelligence_left_in_the_shelf_is_read_and_never_modified(roots):
    from portal.models import intelligence

    memory, data = roots
    (memory / "intelligence.json").write_text(json.dumps({"broker": [{
        "id": "INT-OLD", "intel_type": "broker", "subject": "Old", "content": "c"}]}), encoding="utf-8")
    before = _listing(memory)
    assert [r["id"] for r in intelligence.get_all()["broker"]] == ["INT-OLD"]
    intelligence.create_record("broker", "New Broker", "content")
    assert _listing(memory) == before
    assert len(json.loads((data / "intelligence.json").read_text(encoding="utf-8"))["broker"]) == 2


def test_no_legacy_lookup_when_the_shelf_is_not_configured(roots, monkeypatch):
    monkeypatch.delenv("DISPATCH_MEMORY_ROOT")
    assert legacy_shelf_store("driver_pin_registry.json") is None
