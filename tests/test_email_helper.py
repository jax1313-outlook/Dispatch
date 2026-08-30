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


# ── Document-generation content (Lane M4: itemized closeout summary) ───


class TestEmailHelperClosoutContent:
    """closeout_data enrichment: the drafted body must include the load's real
    pickup/delivery, rate, invoice, and POD details -- not just a generic placeholder.
    """

    def _closeout_data(self, load, **overrides):
        data = {
            "load": load,
            "rate_confirmation": {
                "rate_amount": 2450.0,
                "rate_type": "flat",
                "distance_miles": 512.0,
            },
            "settlement": {
                "invoice_number": "INV-TEST-9001",
                "invoice_amount": 2450.0,
                "payment_status": "invoiced",
            },
            "pods": [{"status": "generated", "recipient": "J. Rivera"}],
        }
        data.update(overrides)
        return data

    def test_broker_body_includes_generic_placeholder_without_closeout_data(self, client):
        from portal.models import email_helper
        load = _delivered_load_with_client(
            client, pickup_location="Dallas, TX", delivery_location="Reno, NV",
        )
        package = email_helper.create_draft(load["load_id"], load, {"email": "b@test.com"})
        assert "available and can be provided on request" in package["broker_body"]
        assert "Rate:" not in package["broker_body"]

    def test_broker_body_includes_real_rate_invoice_pod_details(self, client):
        from portal.models import email_helper
        load = _delivered_load_with_client(
            client,
            pickup_location="Dallas, TX",
            delivery_location="Reno, NV",
            pickup_datetime="2026-08-10T08:00:00Z",
            delivery_datetime="2026-08-12T14:30:00Z",
        )
        closeout = self._closeout_data(load)
        package = email_helper.create_draft(
            load["load_id"], load, {"email": "b@test.com"}, closeout_data=closeout,
        )
        body = package["broker_body"]

        assert "Pickup: Dallas, TX (2026-08-10 08:00)" in body
        assert "Delivery: Reno, NV (2026-08-12 14:30)" in body
        assert "Rate: $2450.00 (flat), 512.0 mi" in body
        assert "Invoice #: INV-TEST-9001 ($2450.00, invoiced)" in body
        assert "POD: generated (recipient: J. Rivera)" in body

    def test_customer_body_includes_real_rate_invoice_pod_details(self, client):
        from portal.models import email_helper
        load = _delivered_load_with_client(
            client, pickup_location="Dallas, TX", delivery_location="Reno, NV",
        )
        closeout = self._closeout_data(load)
        package = email_helper.create_draft(
            load["load_id"], load, None, closeout_data=closeout,
        )
        body = package["customer_body"]

        assert "Pickup: Dallas, TX" in body
        assert "Delivery: Reno, NV" in body
        assert "Rate: $2450.00 (flat), 512.0 mi" in body
        assert "Invoice #: INV-TEST-9001 ($2450.00, invoiced)" in body
        assert "POD: generated (recipient: J. Rivera)" in body

    def test_missing_pieces_render_honest_placeholders_not_invented_values(self, client):
        """No rate confirmed, no settlement, no POD generated yet -- summary must say so
        rather than inventing numbers (matches this module's own never-invent-facts rule).
        """
        from portal.models import email_helper
        load = _delivered_load_with_client(
            client, pickup_location="Dallas, TX", delivery_location="Reno, NV",
        )
        closeout = {
            "load": load,
            "rate_confirmation": None,
            "settlement": None,
            "pods": [],
        }
        package = email_helper.create_draft(
            load["load_id"], load, {"email": "b@test.com"}, closeout_data=closeout,
        )
        body = package["broker_body"]
        assert "Rate: not yet confirmed" in body
        assert "Invoice: not yet generated" in body
        assert "POD: not yet generated" in body

    def test_full_flow_draft_from_real_load_data_via_api(self, client):
        """End-to-end: confirm a real rate, generate a real POD, create a real
        settlement/invoice, End Load, then draft the email package through the actual API
        route (draft_email_package) and confirm those exact values reached the body.
        """
        load = _delivered_load_with_client(
            client,
            pickup_location="Chicago, IL",
            delivery_location="Denver, CO",
            pickup_datetime="2026-08-05T09:00:00Z",
            delivery_datetime="2026-08-07T17:00:00Z",
        )
        load_id = load["load_id"]

        rate_resp = client.post(
            f"/api/dispatch/loads/{load_id}/rate",
            json={"rate_amount": 3100.5, "rate_type": "flat", "distance_miles": 980},
        )
        assert rate_resp.status_code == 201

        pod_resp = client.post(
            f"/api/dispatch/loads/{load_id}/pod", json={"recipient": "T. Nguyen"},
        )
        assert pod_resp.status_code == 201

        settlement_resp = client.post(f"/api/dispatch/loads/{load_id}/settlement", json={})
        assert settlement_resp.status_code == 201
        invoice_number = settlement_resp.get_json()["settlement"]["invoice_number"]

        client.post(f"/api/dispatch/loads/{load_id}/end-load")
        draft_resp = client.post(f"/api/dispatch/loads/{load_id}/email-package/draft")
        assert draft_resp.status_code == 201
        body = draft_resp.get_json()["package"]["broker_body"]

        assert "Pickup: Chicago, IL (2026-08-05 09:00)" in body
        assert "Delivery: Denver, CO (2026-08-07 17:00)" in body
        assert "Rate: $3100.50 (flat), 980.0 mi" in body
        assert f"Invoice #: {invoice_number}" in body
        assert "$3100.50, invoiced" in body
        assert "POD: complete (recipient: T. Nguyen)" in body


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
