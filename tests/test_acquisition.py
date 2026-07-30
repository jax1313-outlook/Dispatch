"""Tests for the SAM.gov live acquisition path (with faked urllib)."""

from __future__ import annotations

import io
import json
import urllib.error

from cin_lite import acquisition


class _FakeResp:
    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._data


def test_acquire_sam_success(monkeypatch, sam_opportunity):
    monkeypatch.setenv("CIN_LITE_SAM_API_KEY", "k")
    payload = json.dumps({"opportunitiesData": [sam_opportunity]}).encode()
    monkeypatch.setattr(acquisition.urllib.request, "urlopen",
                        lambda req, timeout=30: _FakeResp(payload))

    contracts = acquisition.acquire()
    assert len(contracts) == 1
    c = contracts[0]
    assert c["solicitation_number"] == "FA8773-26-R-0007"
    assert c["naics_text"] == "NAICS 541512, 541519"
    assert c["_sam_notice_id"] == "TESTNOTICE001"


def test_acquire_sam_http_error_falls_back(monkeypatch):
    monkeypatch.setenv("CIN_LITE_SAM_API_KEY", "k")

    def boom(req, timeout=30):
        raise urllib.error.HTTPError("u", 403, "Forbidden", None, io.BytesIO(b'{"error":"bad key"}'))

    monkeypatch.setattr(acquisition.urllib.request, "urlopen", boom)
    contracts = acquisition.acquire()
    assert contracts  # fell back to local sample_data
    assert all("_sam_notice_id" not in c for c in contracts)


def test_acquire_sam_network_error_falls_back(monkeypatch):
    monkeypatch.setenv("CIN_LITE_SAM_API_KEY", "k")

    def boom(req, timeout=30):
        raise OSError("network down")

    monkeypatch.setattr(acquisition.urllib.request, "urlopen", boom)
    assert acquisition.acquire()  # local fallback, non-empty


def test_fetch_description_plaintext():
    out = acquisition._fetch_description({"description": "<p>Hello   world</p>"}, "k")
    assert out == "Hello world"


def test_fetch_description_url(monkeypatch):
    body = json.dumps({"description": "<b>Desc</b> text"}).encode()
    monkeypatch.setattr(acquisition.urllib.request, "urlopen",
                        lambda url, timeout=30: _FakeResp(body))
    out = acquisition._fetch_description({"description": "https://api.sam.gov/desc?x=1"}, "k")
    assert out == "Desc text"


def test_fetch_description_url_error_returns_empty(monkeypatch):
    def boom(url, timeout=30):
        raise OSError("nope")

    monkeypatch.setattr(acquisition.urllib.request, "urlopen", boom)
    assert acquisition._fetch_description({"description": "https://x/desc"}, "k") == ""


def test_award_amount_parsing():
    assert acquisition._award_amount({"award": {"amount": "123"}}) == 123.0
    assert acquisition._award_amount({"award": {"amount": None}}) is None
    assert acquisition._award_amount({"award": {"amount": "n/a"}}) is None
    assert acquisition._award_amount({}) is None


def test_naics_text_dedup():
    assert acquisition._naics_text({"naicsCode": "541512", "naicsCodes": ["541512", "541519"]}) \
        == "NAICS 541512, 541519"
    assert acquisition._naics_text({}) == ""
