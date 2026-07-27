"""Tests for the Operations Portal's read layer over the Archive tree."""

from __future__ import annotations

from l2_cos.ui import repository


def test_list_load_bundles_empty_when_no_archive():
    assert repository.list_load_bundles() == []


def test_list_publisher_results_empty_when_no_archive():
    assert repository.list_publisher_results() == []


def test_list_load_bundles_after_run(seeded_l2_cos_archive):
    bundles = repository.list_load_bundles()
    assert {b.load_id for b in bundles} == set(seeded_l2_cos_archive)
    for bundle in bundles:
        assert bundle.load.stage.value == "BOOKED"
        assert bundle.intelligence  # six rule modules present


def test_get_load_bundle_resolves_facility_and_broker(seeded_l2_cos_archive):
    bundle = repository.get_load_bundle(seeded_l2_cos_archive[0])
    assert bundle is not None
    assert bundle.facility_pickup is not None
    assert bundle.broker is not None


def test_get_load_bundle_without_dispatch_record_defaults_available(tmp_path, monkeypatch):
    import json

    from l2_cos import archive as l2_cos_archive

    l2_cos_archive.ensure_tree()
    load_id = "LOAD-NODISPATCH"
    (l2_cos_archive.ARCHIVE_ROOT / "Processed" / f"{load_id}.json").write_text(
        json.dumps({"metadata": {"overall_score": 55}, "load": {"origin": "A", "destination": "B"}}),
        encoding="utf-8",
    )
    bundle = repository.get_load_bundle(load_id)
    assert bundle is not None
    assert bundle.load.stage.value == "AVAILABLE"
    assert bundle.overall_score == 55


def test_list_publisher_results_after_run(seeded_l2_cos_archive):
    results = repository.list_publisher_results()
    assert len(results) == 1  # only the clean sample load clears the publish threshold
    assert results[0]["sent"] is True
