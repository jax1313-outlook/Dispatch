"""Tests for the L2-COS Operations Portal's FastAPI routes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from l2_cos.ui.app import app

client = TestClient(app)


def test_dashboard_lists_seeded_loads(seeded_l2_cos_archive):
    resp = client.get("/")
    assert resp.status_code == 200
    for load_id in seeded_l2_cos_archive:
        assert load_id in resp.text
    assert "HIGH VALUE MATCH" in resp.text


def test_dashboard_empty_when_no_loads():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "No loads in the Archive yet." in resp.text


@pytest.mark.parametrize("view", ["brief", "draft", "source", "lifecycle"])
def test_load_detail_views(seeded_l2_cos_archive, view):
    load_id = seeded_l2_cos_archive[0]
    resp = client.get(f"/loads/{load_id}/{view}")
    assert resp.status_code == 200
    assert load_id in resp.text


@pytest.mark.parametrize("view", ["brief", "draft", "source", "lifecycle"])
def test_load_detail_views_404_for_unknown_load(view):
    resp = client.get(f"/loads/NOPE/{view}")
    assert resp.status_code == 404
    assert "unknown load" in resp.json()["detail"]


def test_locations_and_brokers_pages():
    assert client.get("/locations").status_code == 200
    assert client.get("/brokers").status_code == 200


def test_publisher_alerts_page_after_run(seeded_l2_cos_archive):
    resp = client.get("/publisher")
    assert resp.status_code == 200
    assert "Sandbox" in resp.text


def test_advance_load_happy_path(seeded_l2_cos_archive):
    load_id = seeded_l2_cos_archive[0]
    resp = client.post(f"/loads/{load_id}/advance", data={"action": "PLANNED"})
    assert resp.status_code == 200
    assert resp.json() == {"load_id": load_id, "stage": "PLANNED"}

    # persisted: fetching the lifecycle view now shows the new stage
    lifecycle_resp = client.get(f"/loads/{load_id}/lifecycle")
    assert "PLANNED" in lifecycle_resp.text


def test_advance_load_illegal_action_returns_400(seeded_l2_cos_archive):
    load_id = seeded_l2_cos_archive[0]
    resp = client.post(f"/loads/{load_id}/advance", data={"action": "CLOSED"})
    assert resp.status_code == 400
    assert "illegal action" in resp.json()["detail"]


def test_advance_unknown_load_returns_404():
    resp = client.post("/loads/NOPE/advance", data={"action": "BOOKED"})
    assert resp.status_code == 404
