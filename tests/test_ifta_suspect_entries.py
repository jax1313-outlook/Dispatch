"""Tests for Phase 7: the Suspect Entries panel -- persisting the
extraction_confidence Phase 6b's receipt scan already computes (and
previously discarded on save), then surfacing scanned fuel purchases
below a confidence threshold. Deliberately not a governed exception
(no persistence to ifta_exceptions, never affects readiness_status) --
a direct, small port of Hold's own _suspect_entries() contract. Per
DISPATCH_IFTA_PHASE7_SUSPECT_ENTRIES_LAUNCH_PACKAGE_v1."""

from __future__ import annotations

import inspect

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


@pytest.fixture(autouse=True)
def _upload_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _approve_token(approval_id: str) -> str:
    from cin_lite import email_delivery
    return email_delivery.make_token(approval_id, "approve")


# ── add_ifta_fuel_purchase() persists confidence ─────────────────────


class TestPersistConfidence:
    def test_manual_entry_defaults_to_none(self):
        purchase = services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=40, amount=140, date="2025-01-10")
        assert purchase["extraction_confidence"] is None

    def test_scanned_entry_persists_confidence(self):
        purchase = services.add_ifta_fuel_purchase(
            jurisdiction="TX", gallons=40, amount=140, date="2025-01-10",
            extraction_confidence=0.42,
        )
        assert purchase["extraction_confidence"] == 0.42
        stored = store.get_ifta_fuel_purchase(purchase["purchase_id"])
        assert stored["extraction_confidence"] == 0.42

    def test_high_confidence_also_persists(self):
        purchase = services.add_ifta_fuel_purchase(
            jurisdiction="TX", gallons=40, amount=140, date="2025-01-10",
            extraction_confidence=0.95,
        )
        assert purchase["extraction_confidence"] == 0.95


# ── list_suspect_ifta_fuel_purchases() ────────────────────────────────


class TestListSuspectEntries:
    def test_below_threshold_included(self):
        services.add_ifta_fuel_purchase(
            jurisdiction="TX", gallons=40, amount=140, date="2025-01-10",
            extraction_confidence=0.5,
        )
        suspects = services.list_suspect_ifta_fuel_purchases(2025, 1)
        assert len(suspects) == 1

    def test_above_threshold_excluded(self):
        services.add_ifta_fuel_purchase(
            jurisdiction="TX", gallons=40, amount=140, date="2025-01-10",
            extraction_confidence=0.95,
        )
        suspects = services.list_suspect_ifta_fuel_purchases(2025, 1)
        assert suspects == []

    def test_exactly_at_threshold_excluded(self):
        """Boundary is strict-less-than, matching Hold's own '<' comparison."""
        services.add_ifta_fuel_purchase(
            jurisdiction="TX", gallons=40, amount=140, date="2025-01-10",
            extraction_confidence=services.DEFAULT_SUSPECT_CONFIDENCE_THRESHOLD,
        )
        suspects = services.list_suspect_ifta_fuel_purchases(2025, 1)
        assert suspects == []

    def test_manual_entry_never_a_suspect(self):
        services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=40, amount=140, date="2025-01-10")
        suspects = services.list_suspect_ifta_fuel_purchases(2025, 1)
        assert suspects == []

    def test_scoped_to_the_requested_quarter(self):
        services.add_ifta_fuel_purchase(
            jurisdiction="TX", gallons=40, amount=140, date="2025-01-10",
            extraction_confidence=0.3,
        )
        services.add_ifta_fuel_purchase(
            jurisdiction="TX", gallons=40, amount=140, date="2025-04-10",
            extraction_confidence=0.3,
        )
        q1_suspects = services.list_suspect_ifta_fuel_purchases(2025, 1)
        q2_suspects = services.list_suspect_ifta_fuel_purchases(2025, 2)
        assert len(q1_suspects) == 1
        assert len(q2_suspects) == 1

    def test_custom_threshold(self):
        services.add_ifta_fuel_purchase(
            jurisdiction="TX", gallons=40, amount=140, date="2025-01-10",
            extraction_confidence=0.6,
        )
        assert services.list_suspect_ifta_fuel_purchases(2025, 1, threshold=0.5) == []
        assert len(services.list_suspect_ifta_fuel_purchases(2025, 1, threshold=0.7)) == 1

    def test_invalid_quarter_raises(self):
        with pytest.raises(ValueError, match="quarter"):
            services.list_suspect_ifta_fuel_purchases(2025, 5)

    def test_read_only_no_writes(self):
        """Structural guard, matching every prior phase's convention."""
        source = inspect.getsource(services.list_suspect_ifta_fuel_purchases)
        for line in source.splitlines():
            stripped = line.strip()
            for forbidden in ("store.create_", "store.update_", "store.delete_"):
                assert forbidden not in stripped, f"calls a write function: {stripped}"


# ── Route ─────────────────────────────────────────────────────────────


class TestAddFuelPurchaseRoute:
    def test_route_accepts_extraction_confidence(self, client):
        resp = client.post(
            "/api/dispatch/ifta/fuel-purchases",
            json={"jurisdiction": "TX", "gallons": 40, "amount": 140, "date": "2025-01-10", "extraction_confidence": 0.33},
        )
        assert resp.status_code == 201
        assert resp.get_json()["extraction_confidence"] == 0.33

    def test_route_omitted_confidence_defaults_to_none(self, client):
        resp = client.post(
            "/api/dispatch/ifta/fuel-purchases",
            json={"jurisdiction": "TX", "gallons": 40, "amount": 140, "date": "2025-01-10"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["extraction_confidence"] is None

    def test_route_explicit_null_confidence_stays_none(self, client):
        resp = client.post(
            "/api/dispatch/ifta/fuel-purchases",
            json={"jurisdiction": "TX", "gallons": 40, "amount": 140, "date": "2025-01-10", "extraction_confidence": None},
        )
        assert resp.status_code == 201
        assert resp.get_json()["extraction_confidence"] is None


# ── Dashboard integration ─────────────────────────────────────────────


class TestReviewDashboardSuspectEntries:
    def test_suspect_entries_present_on_draft_quarter(self):
        services.add_ifta_fuel_purchase(
            jurisdiction="TX", gallons=40, amount=140, date="2025-01-10",
            extraction_confidence=0.4,
        )
        dash = services.build_ifta_review_dashboard(2025, 1)
        assert len(dash["suspect_entries"]) == 1

    def test_suspect_entries_do_not_affect_readiness_status(self):
        """Resolved open question: this is informational only, matching
        Hold's own precedent -- a low-confidence scan never downgrades
        readiness_status the way an exception or unlinked evidence does."""
        purchase = services.add_ifta_fuel_purchase(
            jurisdiction="CA", gallons=50, amount=175, date="2025-01-16",
            extraction_confidence=0.2,
        )
        services.attach_ifta_fuel_evidence(
            purchase_id=purchase["purchase_id"], file_data=b"r", original_filename="r.pdf",
        )
        services.add_ifta_trip_leg(jurisdiction="CA", miles=250, date="2025-01-15")
        dash = services.build_ifta_review_dashboard(2025, 1)
        assert len(dash["suspect_entries"]) == 1
        assert dash["readiness_status"] == "ready to submit"

    def test_suspect_entries_present_on_sealed_quarter_too(self):
        """Unlike Exceptions (which reads a frozen snapshot once sealed),
        Suspect Entries is always a live read of the stored field --
        present identically whether the quarter is draft or sealed."""
        services.add_ifta_fuel_purchase(
            jurisdiction="OK", gallons=50, amount=175, date="2025-01-16",
            extraction_confidence=0.3,
        )
        services.add_ifta_trip_leg(jurisdiction="CA", miles=1000, date="2025-01-15")
        approval = services.submit_ifta_quarter_for_approval(2025, 1)
        token = _approve_token(approval["approval_id"])
        services.approve_ifta_quarter(approval["approval_id"], token)

        dash = services.build_ifta_review_dashboard(2025, 1)
        assert dash["approval_status"] == "sealed"
        assert len(dash["suspect_entries"]) == 1

    def test_no_suspect_entries_is_empty_list(self):
        dash = services.build_ifta_review_dashboard(2025, 1)
        assert dash["suspect_entries"] == []

    def test_blocked_dashboard_still_includes_suspect_entries_key(self, monkeypatch):
        from dispatch.models import IFTA_TAX_RATES
        services.add_ifta_trip_leg(jurisdiction="TX", miles=500, date="2025-01-15")
        monkeypatch.delitem(IFTA_TAX_RATES, "TX")
        dash = services.build_ifta_review_dashboard(2025, 1)
        assert dash["tax_position_source"] == "unavailable"
        assert dash["suspect_entries"] == []


class TestReviewPageRendersSuspectEntries:
    def test_renders_suspect_entry(self, client):
        services.add_ifta_fuel_purchase(
            jurisdiction="TX", gallons=40, amount=140, date="2025-01-10",
            extraction_confidence=0.4,
        )
        resp = client.get("/ifta/review?year=2025&quarter=1")
        html = resp.data.decode()
        assert resp.status_code == 200
        assert "Suspect Entries" in html
        assert "confidence 0.40" in html

    def test_renders_no_suspect_entries_message(self, client):
        resp = client.get("/ifta/review?year=2030&quarter=1")
        assert "No suspect entries for this period." in resp.data.decode()
