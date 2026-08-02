"""Tests for batch invoice creation and queue page enhancements."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dispatch import services, store
from dispatch.db import set_db_path
from dispatch.models import Load, RateConfirmation


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture()
def app():
    from portal.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


def _make_load(load_id="LD-001", status="delivered", customer="Acme"):
    load = Load(
        load_id=load_id,
        customer=customer,
        status=status,
        pickup_location="Origin",
        delivery_location="Dest",
    )
    return store.create_load(load)


def _make_rate(load_id="LD-001", rate_amount=5000.0):
    rc = RateConfirmation(load_id=load_id, rate_amount=rate_amount)
    return store.create_rate_confirmation(rc)


# ── Batch Invoice Creation (API) ────────────────────────────────────


class TestBatchCreateSettlements:
    def test_batch_create_success(self, client):
        _make_load("LD-B1", status="delivered")
        _make_load("LD-B2", status="completed")
        _make_rate("LD-B1", rate_amount=1000.0)
        _make_rate("LD-B2", rate_amount=2000.0)

        resp = client.post(
            "/api/dispatch/settlements/batch-create",
            json={"load_ids": ["LD-B1", "LD-B2"], "due_date": "2026-09-01"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["created"] == 2
        assert data["errors"] == []

        stl1 = store.get_settlement("LD-B1")
        assert stl1["payment_status"] == "invoiced"
        assert stl1["invoice_amount"] == 1000.0
        stl2 = store.get_settlement("LD-B2")
        assert stl2["invoice_amount"] == 2000.0

    def test_batch_create_partial_failure(self, client):
        _make_load("LD-B3", status="delivered")
        _make_rate("LD-B3")
        services.create_settlement(load_id="LD-B3")

        _make_load("LD-B4", status="delivered")
        _make_rate("LD-B4")

        resp = client.post(
            "/api/dispatch/settlements/batch-create",
            json={"load_ids": ["LD-B3", "LD-B4"]},
        )
        data = resp.get_json()
        assert data["created"] == 1
        assert len(data["errors"]) == 1
        assert "LD-B3" in data["errors"][0]

    def test_batch_create_empty_list(self, client):
        resp = client.post(
            "/api/dispatch/settlements/batch-create",
            json={"load_ids": []},
        )
        assert resp.status_code == 400

    def test_batch_create_missing_load_ids(self, client):
        resp = client.post(
            "/api/dispatch/settlements/batch-create",
            json={},
        )
        assert resp.status_code == 400

    def test_batch_create_nonexistent_loads(self, client):
        resp = client.post(
            "/api/dispatch/settlements/batch-create",
            json={"load_ids": ["FAKE-1", "FAKE-2"]},
        )
        data = resp.get_json()
        assert data["created"] == 0
        assert len(data["errors"]) == 2

    def test_batch_create_with_due_date(self, client):
        _make_load("LD-B5", status="delivered")

        resp = client.post(
            "/api/dispatch/settlements/batch-create",
            json={"load_ids": ["LD-B5"], "due_date": "2026-12-31"},
        )
        data = resp.get_json()
        assert data["created"] == 1

        stl = store.get_settlement("LD-B5")
        assert stl["due_date"] == "2026-12-31"


# ── Billing Page Batch UI ────────────────────────────────────────────


class TestBillingBatchUI:
    def test_billing_page_has_checkboxes(self, client):
        _make_load("LD-CHK1", status="delivered")
        resp = client.get("/billing")
        html = resp.data.decode()
        assert 'class="uninvoiced-check"' in html
        assert 'id="select-all-uninvoiced"' in html
        assert "toggleAllUninvoiced" in html

    def test_billing_page_has_batch_button(self, client):
        _make_load("LD-CHK2", status="delivered")
        resp = client.get("/billing")
        html = resp.data.decode()
        assert 'id="batch-invoice-btn"' in html
        assert "batchCreateInvoices" in html

    def test_billing_page_no_batch_when_no_uninvoiced(self, client):
        resp = client.get("/billing")
        html = resp.data.decode()
        assert "Uninvoiced Loads" not in html
        assert "select-all-uninvoiced" not in html


# ── Queue Page Enhancements ──────────────────────────────────────────


class TestQueuePage:
    def test_queues_page_renders(self, client):
        resp = client.get("/queues")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Routing Queues" in html

    def test_queues_page_has_summary_column(self, client, archive_dir):
        routing_dir = archive_dir / "Routing"
        record = {
            "contract_id": "CIN-SUM-TEST",
            "action": "flag_review",
            "action_label": "Flag for review",
            "route": "HUMAN_REVIEW",
            "decided_at": "2026-08-01T12:00:00Z",
            "flags": [],
            "summary": "Summary text",
            "metadata": {"title": "T"},
        }
        (routing_dir / "CIN-SUM-TEST.json").write_text(
            json.dumps(record), encoding="utf-8"
        )
        resp = client.get("/queues")
        html = resp.data.decode()
        assert ">Summary</th>" in html

    def test_queues_page_empty_state(self, client):
        resp = client.get("/queues")
        html = resp.data.decode()
        assert "No contracts in the review queue" in html
        assert "No contracts in the analysis queue" in html

    @pytest.fixture()
    def archive_dir(self, tmp_path, monkeypatch):
        from cin_lite import archive

        root = tmp_path / "Archive"
        monkeypatch.setattr(archive, "ARCHIVE_ROOT", root)
        archive.ensure_tree()
        return root

    def test_queues_page_with_review_item(self, client, archive_dir):
        routing_dir = archive_dir / "Routing"
        record = {
            "contract_id": "CIN-20260801-ABCD1234",
            "action": "flag_review",
            "action_label": "Flag for review",
            "route": "HUMAN_REVIEW",
            "decided_at": "2026-08-01T12:00:00Z",
            "flags": ["set_aside", "foreign_influence"],
            "summary": "Test contract for review",
            "metadata": {"title": "Test Contract Title"},
        }
        (routing_dir / "CIN-20260801-ABCD1234.json").write_text(
            json.dumps(record), encoding="utf-8"
        )

        resp = client.get("/queues")
        html = resp.data.decode()
        assert "CIN-20260801-ABCD1234" in html
        assert "Test Contract Title" in html
        assert "2 flags" in html
        assert "Test contract for review" in html
        assert "archive" in html.lower()

    def test_queues_page_with_analysis_item(self, client, archive_dir):
        routing_dir = archive_dir / "Routing"
        record = {
            "contract_id": "CIN-20260801-EFGH5678",
            "action": "deeper_analysis",
            "action_label": "Request deeper analysis",
            "route": "DEEP_ANALYSIS_QUEUE",
            "decided_at": "2026-08-01T14:00:00Z",
            "flags": ["pricing_anomaly"],
            "summary": "Needs deeper analysis",
            "metadata": {"title": "Analysis Contract"},
        }
        (routing_dir / "CIN-20260801-EFGH5678.json").write_text(
            json.dumps(record), encoding="utf-8"
        )

        resp = client.get("/queues")
        html = resp.data.decode()
        assert "CIN-20260801-EFGH5678" in html
        assert "Analysis Contract" in html
        assert "Deeper Analysis" in html
