"""Tests for batch status update on dispatch page."""

from __future__ import annotations

import pytest

from dispatch import services
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── API ─────────────────────────────────────────────────────────────


class TestBatchStatusAPI:
    def test_batch_update_single(self, client):
        load = services.create_load(customer="Batch A")
        resp = client.post(
            "/api/dispatch/loads/batch-status",
            json={"load_ids": [load["load_id"]], "status": "dispatched"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["updated"] == 1
        assert data["errors"] == []
        updated = services.get_load(load["load_id"])
        assert updated["status"] == "dispatched"

    def test_batch_update_multiple(self, client):
        load1 = services.create_load(customer="Batch B1")
        load2 = services.create_load(customer="Batch B2")
        resp = client.post(
            "/api/dispatch/loads/batch-status",
            json={"load_ids": [load1["load_id"], load2["load_id"]], "status": "dispatched"},
        )
        data = resp.get_json()
        assert data["updated"] == 2

    def test_batch_update_partial_failure(self, client):
        load1 = services.create_load(customer="Batch C1")
        load2 = services.create_load(customer="Batch C2")
        # load2 is already dispatched, so created->dispatched won't apply;
        # but in_transit requires intermediate steps from dispatched
        services.update_load(load2["load_id"], status="dispatched")
        resp = client.post(
            "/api/dispatch/loads/batch-status",
            json={
                "load_ids": [load1["load_id"], load2["load_id"]],
                "status": "en_route_pickup",
            },
        )
        data = resp.get_json()
        # load1 is created -> en_route_pickup (invalid), load2 is dispatched -> en_route_pickup (valid)
        assert data["updated"] == 1
        assert len(data["errors"]) == 1
        assert load1["load_id"] in data["errors"][0]

    def test_batch_update_invalid_transition(self, client):
        load = services.create_load(customer="Batch D")
        resp = client.post(
            "/api/dispatch/loads/batch-status",
            json={"load_ids": [load["load_id"]], "status": "delivered"},
        )
        data = resp.get_json()
        assert data["updated"] == 0
        assert len(data["errors"]) == 1

    def test_batch_update_nonexistent_load(self, client):
        resp = client.post(
            "/api/dispatch/loads/batch-status",
            json={"load_ids": ["LOAD-NOPE"], "status": "dispatched"},
        )
        data = resp.get_json()
        assert data["updated"] == 0
        assert len(data["errors"]) == 1

    def test_batch_update_empty_ids(self, client):
        resp = client.post(
            "/api/dispatch/loads/batch-status",
            json={"load_ids": [], "status": "dispatched"},
        )
        assert resp.status_code == 400

    def test_batch_update_missing_status(self, client):
        resp = client.post(
            "/api/dispatch/loads/batch-status",
            json={"load_ids": ["LOAD-X"], "status": ""},
        )
        assert resp.status_code == 400

    def test_batch_logs_activities(self, client):
        load = services.create_load(customer="Batch Log")
        client.post(
            "/api/dispatch/loads/batch-status",
            json={"load_ids": [load["load_id"]], "status": "dispatched"},
        )
        activities = services.list_activities(load["load_id"])
        status_acts = [a for a in activities if a["activity_type"] == "status_change"]
        assert len(status_acts) == 1


# ── UI ──────────────────────────────────────────────────────────────


class TestBatchStatusUI:
    def test_checkboxes_present(self, client):
        services.create_load(customer="Checkbox Test")
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert 'class="batch-check"' in html
        assert 'id="batch-select-all"' in html

    def test_batch_bar_present(self, client):
        services.create_load(customer="Bar Test")
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert 'id="batch-bar"' in html
        assert 'id="batch-status"' in html

    def test_batch_advance_function_present(self, client):
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "batchAdvance" in html

    def test_select_all_function_present(self, client):
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "toggleSelectAll" in html

    def test_batch_bar_hidden_by_default(self, client):
        services.create_load(customer="Hidden Bar")
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert 'id="batch-bar" style="display:none;' in html
