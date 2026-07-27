"""Tests for the L2-COS Acquisition Layer (local fallback + load-board adapter)."""

from __future__ import annotations

import io
import json
import urllib.error

from l2_cos import acquisition


class _FakeResp:
    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._data


def test_acquire_local_excludes_intelligence_libraries():
    loads = acquisition._acquire_local()
    assert len(loads) == 2
    ids = {load["load_id"] for load in loads}
    assert ids == {"LB-100001", "LB-100002"}
    assert all("_source_file" in load for load in loads)


def test_acquire_falls_back_to_local_when_unconfigured():
    loads = acquisition.acquire()
    assert len(loads) == 2


def test_acquire_load_board_success(monkeypatch):
    monkeypatch.setenv("L2_COS_LOAD_BOARD_URL", "https://example.test/loads")
    monkeypatch.setenv("L2_COS_LOAD_BOARD_API_KEY", "test-key")
    payload = json.dumps({"loads": [{"load_id": "X-1", "origin": "A", "destination": "B"}]}).encode()
    captured_requests = []

    def _urlopen(req, timeout=30):
        captured_requests.append(req)
        return _FakeResp(payload)

    monkeypatch.setattr(acquisition.urllib.request, "urlopen", _urlopen)

    loads = acquisition.acquire()
    assert len(loads) == 1
    assert loads[0]["load_id"] == "X-1"
    assert loads[0]["_source_file"] == "load-board/X-1"
    assert captured_requests[0].get_header("Authorization") == "Bearer test-key"


def test_acquire_load_board_http_error_falls_back(monkeypatch):
    monkeypatch.setenv("L2_COS_LOAD_BOARD_URL", "https://example.test/loads")

    def boom(req, timeout=30):
        raise urllib.error.HTTPError("u", 403, "Forbidden", None, io.BytesIO(b'{"error":"bad key"}'))

    monkeypatch.setattr(acquisition.urllib.request, "urlopen", boom)
    loads = acquisition.acquire()
    assert len(loads) == 2  # local fallback


def test_acquire_load_board_network_error_falls_back(monkeypatch):
    monkeypatch.setenv("L2_COS_LOAD_BOARD_URL", "https://example.test/loads")

    def boom(req, timeout=30):
        raise OSError("network down")

    monkeypatch.setattr(acquisition.urllib.request, "urlopen", boom)
    assert len(acquisition.acquire()) == 2


def test_map_load_defaults_missing_fields():
    mapped = acquisition._map_load({})
    assert mapped["load_id"] == ""
    assert mapped["_source_file"] == "load-board"
    assert mapped["notes"] == ""


def test_map_load_uses_id_fallback():
    mapped = acquisition._map_load({"id": "Y-2"})
    assert mapped["load_id"] == "Y-2"
    assert mapped["_source_file"] == "load-board/Y-2"
