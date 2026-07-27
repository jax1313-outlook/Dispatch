"""Tests for the L2-COS Archive Layer."""

from __future__ import annotations

import json
import re

from l2_cos import archive, processing
from l2_cos.models.state import Load, LifecycleStage


def test_make_id_format_and_determinism(clean_load):
    a = archive.make_id(clean_load)
    b = archive.make_id(clean_load)
    assert a == b
    assert re.fullmatch(r"LOAD-\d{8}-[0-9A-F]{8}", a)


def test_make_id_differs_by_load(clean_load, risky_load):
    assert archive.make_id(clean_load) != archive.make_id(risky_load)


def test_ensure_tree_creates_subdirs(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "ARCHIVE_ROOT", tmp_path / "Archive")
    archive.ensure_tree()
    for sub in ("Raw", "Processed", "Intelligence", "Dispatch", "Locations", "Brokers"):
        assert (tmp_path / "Archive" / sub).is_dir()


def test_store_writes_all_artifacts(clean_load, clean_broker):
    intelligence = processing.process(clean_load, broker=clean_broker)
    score = processing.overall_score(intelligence)
    metadata = archive.store(clean_load, intelligence, score)

    lid = metadata["load_id"]
    assert (archive.ARCHIVE_ROOT / "Raw" / f"{lid}.json").exists()
    assert (archive.ARCHIVE_ROOT / "Processed" / f"{lid}.json").exists()
    assert (archive.ARCHIVE_ROOT / "Intelligence" / f"{lid}.json").exists()

    saved_intel = json.loads((archive.ARCHIVE_ROOT / "Intelligence" / f"{lid}.json").read_text(encoding="utf-8"))
    assert "lane_fit" in saved_intel
    assert metadata["overall_score"] == score
    assert metadata["flag_count"] == sum(len(r["flags"]) for r in intelligence.values())


def test_record_dispatch_persists_history():
    load = Load(load_id="LOAD-TEST-1")
    load.advance(LifecycleStage.BOOKED, actor="tester")
    path = archive.record_dispatch(load)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["stage"] == "BOOKED"
    assert len(payload["history"]) == 1
    assert payload["history"][0]["actor"] == "tester"


def test_store_location_and_broker(clean_facility, clean_broker):
    loc_path = archive.store_location(clean_facility)
    brk_path = archive.store_broker(clean_broker)

    assert loc_path.exists() and brk_path.exists()
    assert json.loads(loc_path.read_text(encoding="utf-8"))["facility_id"] == "FAC-001"
    assert json.loads(brk_path.read_text(encoding="utf-8"))["broker_id"] == "BRK-001"


def test_writes_isolated_to_tmp(tmp_path, monkeypatch, clean_load, clean_broker):
    # Sanity: the autouse tmp_archive fixture really redirected l2_cos writes.
    intelligence = processing.process(clean_load, broker=clean_broker)
    archive.store(clean_load, intelligence, processing.overall_score(intelligence))
    assert "L2COSArchive" in str(archive.ARCHIVE_ROOT)
