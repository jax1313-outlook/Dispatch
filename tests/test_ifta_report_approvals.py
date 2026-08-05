"""Tests for the IFTA finalization gate (Phase 4) -- submit for approval,
token-verified sealing, payment recommendation, and the routes/template
around them. Ported from Hold's proven ifta_clerk/prepare.py,
ifta/package.py, and ifta_clerk/recommend.py test techniques."""

from __future__ import annotations

import inspect
import json

import pytest

from dispatch.db import set_db_path
from dispatch import services, store


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture(autouse=True)
def _compliance_root(tmp_path, monkeypatch):
    monkeypatch.setenv("DISPATCH_ARCHIVE_ROOT", str(tmp_path / "archive_root"))


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _seed_taxable_quarter():
    """A single-jurisdiction leg+purchase always nets to exactly zero
    (taxable_gallons collapses to the fuel_gallons that produced
    fleet_mpg in the first place) -- this uses two jurisdictions with
    different rates (CA > OK) so the aggregate has a real, positive
    total_due, producing a genuine 'remit' recommendation rather than
    the zero-net case."""
    services.add_ifta_trip_leg(jurisdiction="CA", miles=1000, date="2025-01-15")
    services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=50, amount=175, date="2025-01-16")


def _approve_token(approval_id: str) -> str:
    from cin_lite import email_delivery
    return email_delivery.make_token(approval_id, "approve")


# ── Service-level: submit ──────────────────────────────────────────


class TestSubmitForApproval:
    def test_submit_creates_draft_with_frozen_snapshot(self):
        _seed_taxable_quarter()
        approval = services.submit_ifta_quarter_for_approval(2025, 1)
        assert approval["status"] == "draft"
        assert approval["year"] == 2025
        assert approval["quarter"] == 1
        assert approval["snapshot_json"]["total_due"] > 0

    def test_submit_refuses_invalid_quarter(self):
        with pytest.raises(ValueError, match="quarter"):
            services.submit_ifta_quarter_for_approval(2025, 5)

    def test_submit_refuses_double_submission(self):
        _seed_taxable_quarter()
        services.submit_ifta_quarter_for_approval(2025, 1)
        with pytest.raises(services.AlreadySubmittedError):
            services.submit_ifta_quarter_for_approval(2025, 1)

    def test_submit_refuses_double_submission_even_after_data_changes(self):
        """Mirrors Hold's AlreadySubmittedError exactly -- there is no path
        to resubmit, only to approve the one submission a period got, even
        if the underlying trip legs/fuel purchases change afterward."""
        _seed_taxable_quarter()
        services.submit_ifta_quarter_for_approval(2025, 1)
        services.add_ifta_trip_leg(jurisdiction="TX", miles=500, date="2025-01-20")
        with pytest.raises(services.AlreadySubmittedError):
            services.submit_ifta_quarter_for_approval(2025, 1)

    def test_submit_propagates_missing_rate_refusal(self, monkeypatch):
        """Phase 2's refuse-on-missing-rate fix must still fire through
        this new path -- submission is not a way around it."""
        from dispatch.models import IFTA_TAX_RATES
        services.add_ifta_trip_leg(jurisdiction="TX", miles=500, date="2025-01-15")
        monkeypatch.delitem(IFTA_TAX_RATES, "TX")
        with pytest.raises(ValueError, match="TX"):
            services.submit_ifta_quarter_for_approval(2025, 1)

    def test_submit_different_vehicle_ids_are_independent(self):
        _seed_taxable_quarter()
        services.submit_ifta_quarter_for_approval(2025, 1, vehicle_id="V1")
        # A different vehicle_id for the same period is a distinct
        # submission -- not blocked by V1's.
        approval = services.submit_ifta_quarter_for_approval(2025, 1, vehicle_id="V2")
        assert approval["status"] == "draft"

    def test_submit_sends_approval_email(self, tmp_path):
        """No SMTP host is configured in tests, so cin_lite.email_delivery
        falls back to writing a .eml file -- confirms the approval link
        was actually built and handed to the delivery layer, not silently
        dropped."""
        _seed_taxable_quarter()
        approval = services.submit_ifta_quarter_for_approval(2025, 1)
        outbox = tmp_path / "Archive" / "Outbox"
        eml_path = outbox / f"ifta-approval-{approval['approval_id']}.eml"
        assert eml_path.exists()
        assert "approve" in eml_path.read_text(encoding="utf-8")


# ── Service-level: approve / seal ───────────────────────────────────


class TestApproveQuarter:
    def test_approve_with_bad_token_refuses(self):
        _seed_taxable_quarter()
        approval = services.submit_ifta_quarter_for_approval(2025, 1)
        with pytest.raises(services.InvalidApprovalTokenError):
            services.approve_ifta_quarter(approval["approval_id"], "not-a-real-token")

    def test_approve_unknown_id_raises(self):
        with pytest.raises(ValueError, match="No such"):
            services.approve_ifta_quarter("IFTAAPR-NOPE", "whatever")

    def test_approve_with_valid_token_seals(self):
        _seed_taxable_quarter()
        approval = services.submit_ifta_quarter_for_approval(2025, 1)
        token = _approve_token(approval["approval_id"])
        sealed = services.approve_ifta_quarter(approval["approval_id"], token)
        assert sealed["status"] == "sealed"
        assert sealed["sealed_at"]
        assert sealed["approved_by"]

    def test_approve_is_idempotent_on_already_sealed(self):
        """Mirrors Hold's attempt_seal(): a repeat visit to an already-sealed
        approval is a no-op success, even with a garbage token -- there is
        nothing left to verify against."""
        _seed_taxable_quarter()
        approval = services.submit_ifta_quarter_for_approval(2025, 1)
        token = _approve_token(approval["approval_id"])
        services.approve_ifta_quarter(approval["approval_id"], token)
        sealed_again = services.approve_ifta_quarter(approval["approval_id"], "garbage")
        assert sealed_again["status"] == "sealed"

    def test_approve_writes_compliance_records(self, tmp_path):
        _seed_taxable_quarter()
        approval = services.submit_ifta_quarter_for_approval(2025, 1)
        token = _approve_token(approval["approval_id"])
        services.approve_ifta_quarter(approval["approval_id"], token)

        compliance_root = tmp_path / "archive_root" / "Compliance"
        sealed_file = compliance_root / "ifta_sealed_report" / f"{approval['approval_id']}.json"
        recommendation_file = compliance_root / "ifta_payment_recommendation" / f"{approval['approval_id']}.json"
        assert sealed_file.exists()
        assert sealed_file.with_name(sealed_file.name + ".sha256").exists()
        assert recommendation_file.exists()
        assert recommendation_file.with_name(recommendation_file.name + ".sha256").exists()

    def test_compliance_records_live_outside_cin_subtree(self, tmp_path):
        """The one thing this design deliberately avoids: nesting IFTA
        compliance records under cin_lite.archive's CIN-specific root."""
        _seed_taxable_quarter()
        approval = services.submit_ifta_quarter_for_approval(2025, 1)
        token = _approve_token(approval["approval_id"])
        services.approve_ifta_quarter(approval["approval_id"], token)

        cin_root = tmp_path / "archive_root" / "CIN"
        compliance_root = tmp_path / "archive_root" / "Compliance"
        assert compliance_root.exists()
        assert not (cin_root / "Compliance").exists()


# ── Payment recommendation (pure function) ──────────────────────────


class TestPaymentRecommendation:
    def test_positive_total_due_recommends_remit(self):
        rec = services.compute_ifta_payment_recommendation({"total_due": 123.45})
        assert rec["recommendation"] == "remit"
        assert rec["amount"] == 123.45

    def test_negative_total_due_recommends_credit(self):
        rec = services.compute_ifta_payment_recommendation({"total_due": -50.0})
        assert rec["recommendation"] == "credit"
        assert rec["amount"] == 50.0

    def test_zero_total_due_recommends_no_payment(self):
        rec = services.compute_ifta_payment_recommendation({"total_due": 0.0})
        assert rec["recommendation"] == "no_payment_due"
        assert rec["amount"] == 0.0

    def test_no_network_import_anywhere_in_recommendation_path(self):
        """Structural guard, ported from Hold's own test technique
        (tests/ifta_clerk/test_recommend.py): the recommendation function
        must never be able to send anything anywhere -- generating it is
        the entire action. Scans source, not behavior, so it can't be
        defeated by a code path that merely isn't exercised."""
        source = inspect.getsource(services.compute_ifta_payment_recommendation)
        for forbidden in ("requests", "smtplib", "urllib", "http.client"):
            assert forbidden not in source, f"found forbidden import/reference: {forbidden}"


# ── Route-level ──────────────────────────────────────────────────────


class TestReportApprovalRoutes:
    def test_submit_via_api(self, client):
        _seed_taxable_quarter()
        resp = client.post("/api/dispatch/ifta/report-approvals", json={"year": 2025, "quarter": 1})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "draft"

    def test_submit_missing_fields(self, client):
        resp = client.post("/api/dispatch/ifta/report-approvals", json={})
        assert resp.status_code == 400

    def test_double_submit_returns_409(self, client):
        _seed_taxable_quarter()
        client.post("/api/dispatch/ifta/report-approvals", json={"year": 2025, "quarter": 1})
        resp = client.post("/api/dispatch/ifta/report-approvals", json={"year": 2025, "quarter": 1})
        assert resp.status_code == 409

    def test_list_and_detail(self, client):
        _seed_taxable_quarter()
        created = client.post("/api/dispatch/ifta/report-approvals", json={"year": 2025, "quarter": 1}).get_json()

        listing = client.get("/api/dispatch/ifta/report-approvals").get_json()
        assert listing["status"] == "ok"
        assert len(listing["approvals"]) == 1

        detail = client.get(f"/api/dispatch/ifta/report-approvals/{created['approval_id']}")
        assert detail.status_code == 200
        assert detail.get_json()["approval_id"] == created["approval_id"]

    def test_detail_not_found(self, client):
        resp = client.get("/api/dispatch/ifta/report-approvals/IFTAAPR-NOPE")
        assert resp.status_code == 404

    def test_approve_via_link_bad_token_renders_clean_error(self, client):
        _seed_taxable_quarter()
        created = client.post("/api/dispatch/ifta/report-approvals", json={"year": 2025, "quarter": 1}).get_json()
        resp = client.get(f"/api/dispatch/ifta/report-approvals/{created['approval_id']}/approve?token=bad")
        assert resp.status_code == 403
        assert "Approval Failed" in resp.data.decode()

    def test_approve_via_link_good_token_renders_success(self, client):
        from cin_lite import email_delivery
        _seed_taxable_quarter()
        created = client.post("/api/dispatch/ifta/report-approvals", json={"year": 2025, "quarter": 1}).get_json()
        token = email_delivery.make_token(created["approval_id"], "approve")
        resp = client.get(f"/api/dispatch/ifta/report-approvals/{created['approval_id']}/approve?token={token}")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Quarter Sealed" in html


# ── Template: /ifta page status badges ──────────────────────────────


class TestIFTAPageApprovalStatus:
    def test_shows_draft_badge_with_no_approval(self, client):
        _seed_taxable_quarter()
        resp = client.get("/ifta?year=2025&quarter=1")
        assert "DRAFT" in resp.data.decode()
        assert "Submit for Approval" in resp.data.decode()

    def test_shows_submitted_badge_after_submission(self, client):
        _seed_taxable_quarter()
        client.post("/api/dispatch/ifta/report-approvals", json={"year": 2025, "quarter": 1})
        resp = client.get("/ifta?year=2025&quarter=1")
        assert "SUBMITTED" in resp.data.decode()

    def test_shows_sealed_badge_after_approval(self, client):
        from cin_lite import email_delivery
        _seed_taxable_quarter()
        created = client.post("/api/dispatch/ifta/report-approvals", json={"year": 2025, "quarter": 1}).get_json()
        token = email_delivery.make_token(created["approval_id"], "approve")
        client.get(f"/api/dispatch/ifta/report-approvals/{created['approval_id']}/approve?token={token}")
        resp = client.get("/ifta?year=2025&quarter=1")
        assert "SEALED" in resp.data.decode()

    def test_no_status_badge_on_monthly_view(self, client):
        _seed_taxable_quarter()
        resp = client.get("/ifta?view=month&year=2025&month=1")
        html = resp.data.decode()
        assert "DRAFT" not in html
        assert "Submit for Approval" not in html
