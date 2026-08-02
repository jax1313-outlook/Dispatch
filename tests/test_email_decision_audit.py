"""Tests for email decision audit trail — PR 26.

Covers: milestone creation on email action clicks, all four action types,
token verification, and source type validation.
"""

from __future__ import annotations

import pytest

from dispatch import notifications, services
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestEmailDecisionAuditTrail:
    def _make_load(self):
        return services.create_load(customer="Acme")

    def test_acknowledge_creates_milestone(self, client):
        load = self._make_load()
        token = notifications.make_token(load["load_id"], "acknowledge")

        resp = client.get(f"/api/dispatch/decision/{load['load_id']}/acknowledge?token={token}")
        assert resp.status_code == 200

        milestones = services.get_timeline(load["load_id"])
        email_ms = [m for m in milestones if m["source"] == "email"]
        assert len(email_ms) == 1
        assert "Acknowledge" in email_ms[0]["note"]
        assert email_ms[0]["event_type"] == "checkpoint"
        assert email_ms[0]["entered_by"] == "reviewer"

    def test_flag_review_creates_milestone_and_exception(self, client):
        load = self._make_load()
        token = notifications.make_token(load["load_id"], "flag_review")

        resp = client.get(f"/api/dispatch/decision/{load['load_id']}/flag_review?token={token}")
        assert resp.status_code == 200

        milestones = services.get_timeline(load["load_id"])
        email_ms = [m for m in milestones if m["source"] == "email"]
        assert len(email_ms) == 1
        assert "Flag for Review" in email_ms[0]["note"]

        exceptions = services.list_exceptions(load_id=load["load_id"])
        assert len(exceptions) == 1
        assert exceptions[0]["severity"] == "medium"

    def test_escalate_creates_milestone_and_exception(self, client):
        load = self._make_load()
        token = notifications.make_token(load["load_id"], "escalate")

        resp = client.get(f"/api/dispatch/decision/{load['load_id']}/escalate?token={token}")
        assert resp.status_code == 200

        milestones = services.get_timeline(load["load_id"])
        email_ms = [m for m in milestones if m["source"] == "email"]
        assert len(email_ms) == 1
        assert "Escalate" in email_ms[0]["note"]

        exceptions = services.list_exceptions(load_id=load["load_id"])
        assert len(exceptions) == 1
        assert exceptions[0]["severity"] == "high"

    def test_request_info_creates_milestone(self, client):
        load = self._make_load()
        token = notifications.make_token(load["load_id"], "request_info")

        resp = client.get(f"/api/dispatch/decision/{load['load_id']}/request_info?token={token}")
        assert resp.status_code == 200

        milestones = services.get_timeline(load["load_id"])
        email_ms = [m for m in milestones if m["source"] == "email"]
        assert len(email_ms) == 1
        assert "Request More Info" in email_ms[0]["note"]

    def test_invalid_token_no_milestone(self, client):
        load = self._make_load()

        resp = client.get(f"/api/dispatch/decision/{load['load_id']}/acknowledge?token=bad")
        assert resp.status_code == 403

        milestones = services.get_timeline(load["load_id"])
        assert len(milestones) == 0

    def test_unknown_action_no_milestone(self, client):
        load = self._make_load()

        resp = client.get(f"/api/dispatch/decision/{load['load_id']}/invalid_action?token=x")
        assert resp.status_code == 400

        milestones = services.get_timeline(load["load_id"])
        assert len(milestones) == 0

    def test_load_not_found_no_milestone(self, client):
        token = notifications.make_token("FAKE-ID", "acknowledge")
        resp = client.get(f"/api/dispatch/decision/FAKE-ID/acknowledge?token={token}")
        assert resp.status_code == 404


class TestEmailMilestoneSource:
    def test_email_is_valid_source(self):
        from dispatch.models import MILESTONE_SOURCES
        assert "email" in MILESTONE_SOURCES

    def test_email_source_milestone_via_api(self, client):
        load = services.create_load(customer="Test")
        resp = client.post(
            f"/api/dispatch/loads/{load['load_id']}/milestones",
            json={"event_type": "checkpoint", "source": "email", "note": "Test"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["milestone"]["source"] == "email"
