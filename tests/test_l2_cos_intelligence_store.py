"""Tests for the Operational Intelligence Libraries loader (System Rule 14)."""

from __future__ import annotations

from pathlib import Path

from l2_cos import intelligence_store


def test_load_facilities_from_sample_data():
    facilities = intelligence_store.load_facilities()
    assert set(facilities) == {"FAC-001", "FAC-002", "FAC-003"}
    assert facilities["FAC-001"].name == "Riverside Distribution Center"
    assert facilities["FAC-002"].historical_problems == []


def test_load_brokers_from_sample_data():
    brokers = intelligence_store.load_brokers()
    assert set(brokers) == {"BRK-001", "BRK-002"}
    assert brokers["BRK-001"].historical_rates["CA-TX"] == 2.15
    assert brokers["BRK-002"].payment_terms == "Net 90"


def test_load_facilities_missing_file_returns_empty(tmp_path):
    assert intelligence_store.load_facilities(tmp_path / "nope.json") == {}


def test_load_brokers_missing_file_returns_empty(tmp_path):
    assert intelligence_store.load_brokers(tmp_path / "nope.json") == {}


def test_load_facilities_custom_path(tmp_path):
    path = tmp_path / "custom_facilities.json"
    path.write_text(
        '[{"facility_id": "F9", "name": "Custom", "address": "1 Test St"}]', encoding="utf-8"
    )
    facilities = intelligence_store.load_facilities(path)
    assert facilities["F9"].name == "Custom"


def test_load_brokers_custom_path(tmp_path):
    path = tmp_path / "custom_brokers.json"
    path.write_text(
        '[{"broker_id": "B9", "company_name": "Custom Broker"}]', encoding="utf-8"
    )
    brokers = intelligence_store.load_brokers(path)
    assert brokers["B9"].company_name == "Custom Broker"
