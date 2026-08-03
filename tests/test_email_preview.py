"""Tests for email template preview feature."""

from __future__ import annotations

import pytest

from dispatch.db import set_db_path
from dispatch.notifications import EMAIL_TEMPLATES, preview_notification


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


# ── Preview Function Tests ───────────────────────────────────────────


class TestPreviewNotification:
    def test_all_templates_render(self):
        for key in EMAIL_TEMPLATES:
            result = preview_notification(key)
            assert result is not None, f"Template {key} returned None"
            assert result["key"] == key
            assert result["name"] == EMAIL_TEMPLATES[key]
            assert "<div" in result["html"]
            assert len(result["text"]) > 0
            assert "[DISPATCH]" in result["subject"]

    def test_dispatched_preview(self):
        r = preview_notification("dispatched")
        assert "Dispatched" in r["subject"]
        assert "Load Dispatched" in r["html"]
        assert "John Smith" in r["html"]

    def test_exception_preview(self):
        r = preview_notification("exception")
        assert "EXCEPTION" in r["subject"]
        assert "Delay at Pickup" in r["html"]
        assert "high" in r["html"]

    def test_delivered_preview(self):
        r = preview_notification("delivered")
        assert "Delivered" in r["subject"]
        assert "Delivery Confirmed" in r["html"]

    def test_pod_generated_preview(self):
        r = preview_notification("pod_generated")
        assert "POD" in r["subject"]
        assert "POD Package Generated" in r["html"]

    def test_archived_preview(self):
        r = preview_notification("archived")
        assert "Archived" in r["subject"]
        assert "Load Archived" in r["html"]

    def test_invoice_created_preview(self):
        r = preview_notification("invoice_created")
        assert "Invoice" in r["subject"]
        assert "2,450" in r["html"]

    def test_payment_received_preview(self):
        r = preview_notification("payment_received")
        assert "Payment" in r["subject"]
        assert "ACH Transfer" in r["html"]

    def test_payment_overdue_preview(self):
        r = preview_notification("payment_overdue")
        assert "OVERDUE" in r["subject"]
        assert "32" in r["html"]

    def test_stalled_preview(self):
        r = preview_notification("stalled")
        assert "STALLED" in r["subject"]
        assert "8.5 hours" in r["html"]

    def test_unknown_template(self):
        assert preview_notification("nonexistent") is None

    def test_sample_load_data(self):
        r = preview_notification("dispatched")
        assert "Acme Logistics" in r["html"]
        assert "Dallas, TX" in r["html"]
        assert "Atlanta, GA" in r["html"]
        assert "LOAD-20260801-SAMPLE" in r["html"]

    def test_action_buttons_present(self):
        r = preview_notification("dispatched")
        assert "Acknowledge" in r["html"]
        assert "Flag for Review" in r["html"]

    def test_has_plain_text(self):
        r = preview_notification("dispatched")
        assert "DISPATCH" in r["text"]
        assert "Load ID" in r["text"]
        assert "Acme Logistics" in r["text"]


# ── API Tests ────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestEmailPreviewAPI:
    def test_list_templates(self, client):
        r = client.get("/api/dispatch/email-preview")
        assert r.status_code == 200
        data = r.get_json()
        assert "dispatched" in data
        assert "exception" in data
        assert len(data) == len(EMAIL_TEMPLATES)

    def test_get_preview_json(self, client):
        r = client.get("/api/dispatch/email-preview/dispatched")
        assert r.status_code == 200
        data = r.get_json()
        assert data["key"] == "dispatched"
        assert "html" in data
        assert "text" in data
        assert "subject" in data

    def test_get_preview_raw_html(self, client):
        r = client.get("/api/dispatch/email-preview/dispatched?raw=1")
        assert r.status_code == 200
        assert r.content_type.startswith("text/html")
        assert b"DISPATCH" in r.data

    def test_get_preview_not_found(self, client):
        r = client.get("/api/dispatch/email-preview/bogus")
        assert r.status_code == 404


# ── Template Tests ───────────────────────────────────────────────────


class TestEmailPreviewTemplate:
    def test_page_loads(self, client):
        r = client.get("/email-templates")
        assert r.status_code == 200
        html = r.data.decode()
        assert "Email Template Preview" in html

    def test_page_shows_template_list(self, client):
        r = client.get("/email-templates")
        html = r.data.decode()
        for name in EMAIL_TEMPLATES.values():
            assert name in html

    def test_page_has_preview_frame(self, client):
        r = client.get("/email-templates")
        html = r.data.decode()
        assert "preview-iframe" in html
        assert "preview-subject" in html

    def test_page_has_view_toggle(self, client):
        r = client.get("/email-templates")
        html = r.data.decode()
        assert "toggleView" in html
        assert "Plain Text" in html

    def test_nav_link(self, client):
        r = client.get("/email-templates")
        html = r.data.decode()
        assert "Email Templates" in html
