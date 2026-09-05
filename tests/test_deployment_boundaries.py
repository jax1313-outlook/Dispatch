"""Tests for the two adapter/API boundaries built during the deployment-
matrix hardening pass, per governance rule 9 ("create the adapter/API
boundary but do not fake live integration"):

    - dispatch/customer_notifications.py -- customer/broker-facing email
      transport (nothing sent this before; all existing notify_* functions
      are internal-reviewer-only, confirmed by audit).
    - dispatch/accounting_export.py -- accounting handoff (confirmed
      absent everywhere else; self-labeled "Planned" on the live /settings
      page).

Neither is wired into the Load/Settlement lifecycle automatically --
deciding when to fire them is a business-rule decision out of scope here.
These tests only prove the boundary itself works and degrades safely.
"""

from __future__ import annotations

import json

import pytest

from dispatch import accounting_export, customer_notifications


class TestCustomerNotificationBoundary:
    def test_requires_an_explicit_recipient(self):
        with pytest.raises(ValueError):
            customer_notifications.notify_customer("", "Subject", "Body", "fallback-1")

    def test_falls_back_to_local_file_when_smtp_unconfigured(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DISPATCH_SMTP_HOST", raising=False)
        from cin_lite import email_delivery
        monkeypatch.setattr(email_delivery, "_OUTBOX", tmp_path / "Outbox")

        result = customer_notifications.notify_customer(
            "broker@example.com", "Load complete", "Thanks for the load.", "test-fallback-1",
        )

        assert "not sent" in result
        outbox = tmp_path / "Outbox"
        assert outbox.exists()
        assert any(outbox.iterdir())

    def test_never_raises_even_if_smtp_send_fails(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISPATCH_SMTP_HOST", "smtp.invalid.example")
        from cin_lite import email_delivery
        monkeypatch.setattr(email_delivery, "_OUTBOX", tmp_path / "Outbox")

        # Unreachable host -- should degrade to the local fallback, not raise.
        result = customer_notifications.notify_customer(
            "broker@example.com", "Load complete", "Thanks for the load.", "test-fallback-2",
        )
        assert "delivery failed" in result or "not sent" in result


class TestAccountingExportBoundary:
    def test_writes_a_local_export_when_unconfigured(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISPATCH_ACCOUNTING_EXPORT_DIR", str(tmp_path / "AccountingExport"))
        settlement = {
            "settlement_id": "STL-TEST-001",
            "load_id": "LOAD-001",
            "invoice_number": "INV-001",
            "invoice_amount": 1450.0,
            "payment_status": "invoiced",
        }

        receipt = accounting_export.export_settlement(settlement)

        assert receipt["status"] == "written_locally"
        exported = json.loads(open(receipt["path"]).read())
        assert exported["settlement_id"] == "STL-TEST-001"
        assert exported["invoice_amount"] == 1450.0
        assert "exported_at" in exported

    def test_never_raises_on_a_bad_export_dir(self, monkeypatch):
        # Point at a path that can't be created (a file, not a directory, as
        # a parent) to exercise the failure branch without touching real disk
        # layout elsewhere.
        import tempfile
        with tempfile.NamedTemporaryFile() as f:
            monkeypatch.setenv("DISPATCH_ACCOUNTING_EXPORT_DIR", f"{f.name}/AccountingExport")
            receipt = accounting_export.export_settlement({"settlement_id": "STL-TEST-002"})
            assert receipt["status"] == "export_failed"
            assert "error" in receipt
