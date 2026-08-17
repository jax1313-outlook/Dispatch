"""Tests for the Email Helper review-package step (D3's "Publisher Creates Documents ->
Email Helper Review Package -> Human Review -> Submit").

Covers: portal.models.email_helper (drafting, editing, the submit approval gate), the
/email-package API routes, and never-auto-sends behavior end to end from End Load through
Submit.
"""

from __future__ import annotations

import pytest

from dispatch import services
from dispatch.db import set_db_path


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    set_db_path(tmp_path / "test.db")

    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

    set_db_path(None)


def _delivered_load_with_client(client, **overrides):
    payload = {"customer": "Email Helper Co"}
    payload.update(overrides)
    r = client.post("/api/dispatch/loads", json=payload)
    load = r.get_json()["load"]
    for status in (
        "dispatched", "en_route_pickup", "at_pickup", "picked_up",
        "in_transit", "at_delivery", "delivered",
    ):
        client.patch(f"/api/dispatch/loads/{load['load_id']}", json={"status": status})
    return load


# ── portal.models.email_helper ──────────────────────────────────────────


class TestEmailHelperModel:
    def test_create_draft_is_idempotent(self, client):
        from portal.models import email_helper
        load = _delivered_load_with_client(client)
        first = email_helper.create_draft(load["load_id"], load, None)
        second = email_helper.create_draft(load["load_id"], load, None)
        assert first["id"] == second["id"]

    def test_draft_fills_broker_email_from_contact(self, client):
        from portal.models import email_helper
        load = _delivered_load_with_client(client, broker_shipper="Acme Brokerage")
        contact = {"company_name": "Acme Brokerage", "contact_name": "Jane", "email": "jane@acme.test"}
        package = email_helper.create_draft(load["load_id"], load, contact)
        assert package["broker_email"] == "jane@acme.test"
        assert "Jane" in package["broker_body"]

    def test_draft_leaves_customer_email_blank_honestly(self, client):
        from portal.models import email_helper
        load = _delivered_load_with_client(client)
        package = email_helper.create_draft(load["load_id"], load, None)
        assert package["customer_email"] == ""

    def test_submit_rejects_missing_identity(self, client):
        from portal.models import email_helper
        load = _delivered_load_with_client(client)
        email_helper.create_draft(load["load_id"], load, {"email": "b@test.com"})
        with pytest.raises(email_helper.EmailHelperSubmitError):
            email_helper.submit_package(load["load_id"], None)

    def test_submit_rejects_system_identity(self, client):
        from portal.models import email_helper
        load = _delivered_load_with_client(client)
        email_helper.create_draft(load["load_id"], load, {"email": "b@test.com"})
        with pytest.raises(email_helper.EmailHelperSubmitError):
            email_helper.submit_package(load["load_id"], "PUBLISHER")

    def test_submit_rejects_no_recipients(self, client):
        from portal.models import email_helper
        load = _delivered_load_with_client(client)
        email_helper.create_draft(load["load_id"], load, None)  # no broker contact, no customer email
        with pytest.raises(ValueError, match="no recipient"):
            email_helper.submit_package(load["load_id"], "Mike Zachary")

    def test_submit_writes_local_fallback_without_smtp(self, client, monkeypatch):
        from portal.models import email_helper
        monkeypatch.delenv("DISPATCH_SMTP_HOST", raising=False)
        load = _delivered_load_with_client(client)
        email_helper.create_draft(load["load_id"], load, {"email": "broker@test.com"})
        package = email_helper.submit_package(load["load_id"], "Mike Zachary")
        assert package["status"] == "SUBMITTED"
        assert package["reviewed_by"] == "Mike Zachary"
        assert len(package["send_results"]) == 1
        assert "not sent" in package["send_results"][0]["result"]

    def test_submit_is_idempotent(self, client):
        from portal.models import email_helper
        load = _delivered_load_with_client(client)
        email_helper.create_draft(load["load_id"], load, {"email": "broker@test.com"})
        first = email_helper.submit_package(load["load_id"], "Mike Zachary")
        second = email_helper.submit_package(load["load_id"], "Someone Else")
        assert first["submitted_at"] == second["submitted_at"]
        assert second["reviewed_by"] == "Mike Zachary"  # not overwritten by the second call

    def test_cannot_edit_after_submit(self, client):
        from portal.models import email_helper
        load = _delivered_load_with_client(client)
        email_helper.create_draft(load["load_id"], load, {"email": "broker@test.com"})
        email_helper.submit_package(load["load_id"], "Mike Zachary")
        with pytest.raises(ValueError, match="already submitted"):
            email_helper.update_draft(load["load_id"], broker_body="edited")


# ── API routes ────────────────────────────────────────────────────────


class TestEmailPackageRoutes:
    def test_draft_requires_end_load_first(self, client):
        load = _delivered_load_with_client(client)
        resp = client.post(f"/api/dispatch/loads/{load['load_id']}/email-package/draft")
        assert resp.status_code == 409

    def test_full_flow_draft_edit_submit(self, client):
        load = _delivered_load_with_client(client)
        client.post(f"/api/dispatch/loads/{load['load_id']}/end-load")

        draft_resp = client.post(f"/api/dispatch/loads/{load['load_id']}/email-package/draft")
        assert draft_resp.status_code == 201
        package = draft_resp.get_json()["package"]
        assert package["status"] == "DRAFT"

        edit_resp = client.patch(
            f"/api/dispatch/loads/{load['load_id']}/email-package",
            json={"broker_email": "edited-broker@test.com"},
        )
        assert edit_resp.status_code == 200
        assert edit_resp.get_json()["package"]["status"] == "REVIEWED"

        submit_resp = client.post(
            f"/api/dispatch/loads/{load['load_id']}/email-package/submit",
            json={"submitted_by": "Mike Zachary"},
        )
        assert submit_resp.status_code == 200
        final = submit_resp.get_json()["package"]
        assert final["status"] == "SUBMITTED"
        assert final["send_results"][0]["to"] == "edited-broker@test.com"

    def test_submit_without_identity_is_rejected(self, client):
        load = _delivered_load_with_client(client)
        client.post(f"/api/dispatch/loads/{load['load_id']}/end-load")
        client.post(f"/api/dispatch/loads/{load['load_id']}/email-package/draft")
        client.patch(
            f"/api/dispatch/loads/{load['load_id']}/email-package",
            json={"broker_email": "b@test.com"},
        )
        resp = client.post(f"/api/dispatch/loads/{load['load_id']}/email-package/submit", json={})
        assert resp.status_code == 403

    def test_get_email_package_404_before_draft(self, client):
        load = _delivered_load_with_client(client)
        resp = client.get(f"/api/dispatch/loads/{load['load_id']}/email-package")
        assert resp.status_code == 404


# ── Load detail page ─────────────────────────────────────────────────


class TestEmailPackagePage:
    def test_no_draft_button_before_end_load(self, client):
        load = _delivered_load_with_client(client)
        resp = client.get(f"/dispatch/{load['load_id']}")
        assert b"Email Helper Review Package" not in resp.data

    def test_draft_button_shown_after_end_load(self, client):
        load = _delivered_load_with_client(client)
        client.post(f"/api/dispatch/loads/{load['load_id']}/end-load")
        resp = client.get(f"/dispatch/{load['load_id']}")
        assert b"Draft Review Package" in resp.data

    def test_page_shows_submitted_results(self, client):
        load = _delivered_load_with_client(client)
        client.post(f"/api/dispatch/loads/{load['load_id']}/end-load")
        client.post(f"/api/dispatch/loads/{load['load_id']}/email-package/draft")
        client.patch(
            f"/api/dispatch/loads/{load['load_id']}/email-package",
            json={"broker_email": "b@test.com"},
        )
        client.post(
            f"/api/dispatch/loads/{load['load_id']}/email-package/submit",
            json={"submitted_by": "Mike Zachary"},
        )
        resp = client.get(f"/dispatch/{load['load_id']}")
        assert b"SUBMITTED" in resp.data
        assert b"Send Results" in resp.data
