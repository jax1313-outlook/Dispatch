"""Tests for the dispatch acquisition layer."""

from __future__ import annotations

import json

import pytest

from dispatch import acquisition


SAMPLE_LOAD = {
    "load_id": "LOAD-TEST-001",
    "title": "Dry Van - Jacksonville FL to Savannah GA",
    "origin": "Jacksonville, FL 32202",
    "destination": "Savannah, GA 31401",
    "distance_miles": 140,
    "broker": "Southeast Freight Partners",
    "rate": 625,
    "rpm": 4.46,
    "pickup_window": "2026-07-30 06:00 - 10:00",
    "delivery_window": "2026-07-30 14:00 - 18:00",
    "equipment_required": "Dry Van 53'",
    "equipment_match": "match",
    "weight_lbs": 38000,
}


class TestAcquireLocal:
    def test_loads_from_directory(self, tmp_path, monkeypatch):
        load_dir = tmp_path / "loads"
        load_dir.mkdir()
        (load_dir / "load1.json").write_text(json.dumps(SAMPLE_LOAD))
        monkeypatch.setattr(acquisition, "_DEFAULT_SAMPLE_DIR", load_dir)

        result = acquisition.acquire()
        assert len(result) == 1
        assert result[0]["load_id"] == "LOAD-TEST-001"

    def test_multiple_files_sorted(self, tmp_path, monkeypatch):
        load_dir = tmp_path / "loads"
        load_dir.mkdir()
        for i in range(3):
            data = {**SAMPLE_LOAD, "load_id": f"LOAD-{i:03d}"}
            (load_dir / f"load_{i:02d}.json").write_text(json.dumps(data))
        monkeypatch.setattr(acquisition, "_DEFAULT_SAMPLE_DIR", load_dir)

        result = acquisition.acquire()
        assert len(result) == 3
        assert result[0]["load_id"] == "LOAD-000"
        assert result[2]["load_id"] == "LOAD-002"

    def test_empty_directory(self, tmp_path, monkeypatch):
        load_dir = tmp_path / "loads"
        load_dir.mkdir()
        monkeypatch.setattr(acquisition, "_DEFAULT_SAMPLE_DIR", load_dir)

        result = acquisition.acquire()
        assert result == []

    def test_missing_directory(self, tmp_path, monkeypatch):
        monkeypatch.setattr(acquisition, "_DEFAULT_SAMPLE_DIR", tmp_path / "nonexistent")

        result = acquisition.acquire()
        assert result == []

    def test_custom_source_via_env(self, tmp_path, monkeypatch):
        load_dir = tmp_path / "custom"
        load_dir.mkdir()
        (load_dir / "custom.json").write_text(json.dumps(SAMPLE_LOAD))
        monkeypatch.setenv("DISPATCH_LOAD_SOURCE", str(load_dir))

        result = acquisition.acquire()
        assert len(result) == 1

    def test_source_file_metadata(self, tmp_path, monkeypatch):
        load_dir = tmp_path / "loads"
        load_dir.mkdir()
        (load_dir / "test_load.json").write_text(json.dumps(SAMPLE_LOAD))
        monkeypatch.setattr(acquisition, "_DEFAULT_SAMPLE_DIR", load_dir)

        result = acquisition.acquire()
        assert result[0]["_source_file"] == "test_load.json"


class TestNormalize:
    def test_all_fields_present(self):
        result = acquisition._normalize(SAMPLE_LOAD)
        for field in acquisition._LOAD_SHAPE_FIELDS:
            assert field in result

    def test_missing_fields_default_none(self):
        result = acquisition._normalize({"load_id": "LOAD-X"})
        assert result["load_id"] == "LOAD-X"
        assert result["origin"] is None
        assert result["rate"] is None

    def test_auto_title_generation(self):
        data = {
            "load_id": "LOAD-X",
            "equipment_required": "Dry Van 53'",
            "origin": "Jacksonville, FL",
            "destination": "Savannah, GA",
        }
        result = acquisition._normalize(data)
        assert "Dry" in result["title"]
        assert "Jacksonville" in result["title"]
        assert "Savannah" in result["title"]

    def test_auto_title_no_equipment(self):
        data = {
            "load_id": "LOAD-X",
            "origin": "JAX, FL",
            "destination": "SAV, GA",
        }
        result = acquisition._normalize(data)
        assert result["title"].startswith("Load")

    def test_auto_title_no_locations(self):
        data = {"load_id": "LOAD-X"}
        result = acquisition._normalize(data)
        assert result["title"] == "Load"

    def test_preserves_underscore_fields(self):
        data = {**SAMPLE_LOAD, "_source_file": "test.json", "_custom": "value"}
        result = acquisition._normalize(data)
        assert result["_source_file"] == "test.json"
        assert result["_custom"] == "value"

    def test_fallback_load_id(self):
        result = acquisition._normalize({"id": "alt-id"})
        assert result["load_id"] == "alt-id"

    def test_missing_load_id(self):
        result = acquisition._normalize({})
        assert result["load_id"] == "UNKNOWN"

    def test_existing_title_preserved(self):
        result = acquisition._normalize(SAMPLE_LOAD)
        assert result["title"] == "Dry Van - Jacksonville FL to Savannah GA"


class TestAcquireAPI:
    def test_api_list_response(self, monkeypatch):
        loads = [SAMPLE_LOAD, {**SAMPLE_LOAD, "load_id": "LOAD-002"}]
        monkeypatch.setenv("DISPATCH_LOAD_API_URL", "http://test.example/api/loads")
        monkeypatch.setattr(
            acquisition, "_acquire_api",
            lambda url: [acquisition._normalize(l) for l in loads],
        )

        result = acquisition.acquire()
        assert len(result) == 2

    def test_api_dict_response_with_loads_key(self, monkeypatch):
        body = {"loads": [SAMPLE_LOAD], "total": 1}
        monkeypatch.setenv("DISPATCH_LOAD_API_URL", "http://test.example/api/loads")
        monkeypatch.setattr(
            acquisition, "_acquire_api",
            lambda url: [acquisition._normalize(l) for l in body["loads"]],
        )

        result = acquisition.acquire()
        assert len(result) == 1


class TestIntegrationWithHelpers:
    def test_load_dispatch_data_uses_acquisition(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
        load_dir = tmp_path / "loads"
        load_dir.mkdir()
        (load_dir / "test.json").write_text(json.dumps(SAMPLE_LOAD))
        monkeypatch.setattr(acquisition, "_DEFAULT_SAMPLE_DIR", load_dir)

        from portal.helpers import load_dispatch_data
        loads = load_dispatch_data()
        assert len(loads) == 1
        assert loads[0]["score"] >= 0
        assert "_scoring" in loads[0]
