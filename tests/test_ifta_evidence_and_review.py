"""Tests for Phase 5: fuel-purchase evidence linkage and the
Dispatch-native IFTA review dashboard. Built from Hold's proven
_resolve_line_evidence()/worksheet provenance/build_dashboard() shapes,
adapted to Dispatch's own data model per
DISPATCH_IFTA_PHASE5_LAUNCH_PACKAGE_v2."""

from __future__ import annotations

import inspect
import io

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


def _seed_taxable_quarter():
    """Two jurisdictions with different rates so total_due is genuinely
    positive rather than the single-jurisdiction $0 identity (same
    fixture technique as Phase 4's own tests)."""
    services.add_ifta_trip_leg(jurisdiction="CA", miles=1000, date="2025-01-15")
    services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=50, amount=175, date="2025-01-16")


def _approve_token(approval_id: str) -> str:
    from cin_lite import email_delivery
    return email_delivery.make_token(approval_id, "approve")


# ── Provenance tracking in _ifta_aggregate() ─────────────────────────


class TestProvenanceTracking:
    def test_jurisdiction_line_lists_contributing_leg_and_purchase_ids(self):
        leg = services.add_ifta_trip_leg(jurisdiction="CA", miles=1000, date="2025-01-15")
        purchase = services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=50, amount=175, date="2025-01-16")
        report = services.get_ifta_quarterly_report(2025, 1)

        ca_line = next(j for j in report["jurisdictions"] if j["jurisdiction"] == "CA")
        ok_line = next(j for j in report["jurisdictions"] if j["jurisdiction"] == "OK")
        assert ca_line["leg_ids"] == [leg["leg_id"]]
        assert ca_line["purchase_ids"] == []
        assert ok_line["purchase_ids"] == [purchase["purchase_id"]]
        assert ok_line["leg_ids"] == []

    def test_provenance_does_not_change_the_tax_totals(self):
        """Additive only -- adding leg_ids/purchase_ids must not perturb
        the existing, already-tested tax computation."""
        _seed_taxable_quarter()
        report = services.get_ifta_quarterly_report(2025, 1)
        assert report["total_due"] == 9.95


# ── attach_ifta_fuel_evidence() ──────────────────────────────────────


class TestAttachFuelEvidence:
    def test_attach_refuses_unknown_purchase(self):
        with pytest.raises(ValueError, match="not found"):
            services.attach_ifta_fuel_evidence(
                purchase_id="FUEL-NOPE", file_data=b"receipt bytes",
                original_filename="receipt.pdf",
            )

    def test_attach_creates_checksummed_evidence_and_links_purchase(self):
        purchase = services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=40, amount=140, date="2025-01-10")
        ev = services.attach_ifta_fuel_evidence(
            purchase_id=purchase["purchase_id"], file_data=b"receipt bytes",
            original_filename="receipt.pdf", uploaded_by="dispatcher@example.com",
        )
        assert ev["purchase_id"] == purchase["purchase_id"]
        assert ev["checksum"]
        assert ev["file_size"] == len(b"receipt bytes")

        updated = store.get_ifta_fuel_purchase(purchase["purchase_id"])
        assert updated["evidence_id"] == ev["evidence_id"]

    def test_evidence_file_is_actually_written_and_retrievable(self):
        purchase = services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=40, amount=140, date="2025-01-10")
        ev = services.attach_ifta_fuel_evidence(
            purchase_id=purchase["purchase_id"], file_data=b"receipt bytes",
            original_filename="receipt.pdf",
        )
        result = services.get_ifta_fuel_evidence_file(ev["evidence_id"])
        assert result is not None
        file_path, download_name = result
        assert file_path.read_bytes() == b"receipt bytes"
        assert download_name == "receipt.pdf"

    def test_second_attachment_overwrites_the_link_not_the_first_file(self):
        """No delete-on-replace behavior is implemented -- the purchase's
        evidence_id simply points at whichever evidence was attached most
        recently; the earlier evidence row/file is untouched."""
        purchase = services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=40, amount=140, date="2025-01-10")
        first = services.attach_ifta_fuel_evidence(
            purchase_id=purchase["purchase_id"], file_data=b"first", original_filename="a.pdf",
        )
        second = services.attach_ifta_fuel_evidence(
            purchase_id=purchase["purchase_id"], file_data=b"second", original_filename="b.pdf",
        )
        updated = store.get_ifta_fuel_purchase(purchase["purchase_id"])
        assert updated["evidence_id"] == second["evidence_id"]
        assert services.get_ifta_fuel_evidence_file(first["evidence_id"]) is not None


# ── resolve_ifta_evidence_for_snapshot() ─────────────────────────────


class TestResolveEvidenceForSnapshot:
    def test_purchase_with_no_evidence_resolves_with_none(self):
        services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=50, amount=175, date="2025-01-16")
        report = services.get_ifta_quarterly_report(2025, 1)
        resolved = services.resolve_ifta_evidence_for_snapshot(report)
        ok_entry = next(j for j in resolved if j["jurisdiction"] == "OK")
        assert len(ok_entry["purchases"]) == 1
        assert ok_entry["purchases"][0]["evidence"] is None

    def test_purchase_with_evidence_resolves_the_evidence_record(self):
        purchase = services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=50, amount=175, date="2025-01-16")
        ev = services.attach_ifta_fuel_evidence(
            purchase_id=purchase["purchase_id"], file_data=b"receipt", original_filename="r.pdf",
        )
        report = services.get_ifta_quarterly_report(2025, 1)
        resolved = services.resolve_ifta_evidence_for_snapshot(report)
        ok_entry = next(j for j in resolved if j["jurisdiction"] == "OK")
        assert ok_entry["purchases"][0]["evidence"]["evidence_id"] == ev["evidence_id"]

    def test_deleted_purchase_is_skipped_not_raised(self):
        """A frozen snapshot's purchase_ids can outlive the purchase row
        itself (e.g. deleted after submission) -- resolution must skip,
        never raise, matching Hold's own _resolve_line_evidence() spirit
        that evidence bundling must never block an already-computed
        report."""
        purchase = services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=50, amount=175, date="2025-01-16")
        report = services.get_ifta_quarterly_report(2025, 1)
        services.delete_ifta_fuel_purchase(purchase["purchase_id"])
        resolved = services.resolve_ifta_evidence_for_snapshot(report)
        ok_entry = next(j for j in resolved if j["jurisdiction"] == "OK")
        assert ok_entry["purchases"] == []

    def test_legacy_snapshot_without_provenance_keys_resolves_empty(self):
        """A snapshot captured before Phase 5 (no leg_ids/purchase_ids
        keys) must not crash resolution."""
        legacy_snapshot = {"jurisdictions": [{"jurisdiction": "OK"}]}
        resolved = services.resolve_ifta_evidence_for_snapshot(legacy_snapshot)
        assert resolved[0]["purchases"] == []


# ── approve_ifta_quarter() wiring ────────────────────────────────────


class TestSealedRecordIncludesResolvedEvidence:
    def test_sealed_compliance_record_includes_resolved_evidence(self, tmp_path):
        import json
        purchase_id = services.add_ifta_fuel_purchase(
            jurisdiction="OK", gallons=50, amount=175, date="2025-01-16"
        )["purchase_id"]
        services.attach_ifta_fuel_evidence(
            purchase_id=purchase_id, file_data=b"receipt", original_filename="r.pdf",
        )
        services.add_ifta_trip_leg(jurisdiction="CA", miles=1000, date="2025-01-15")
        approval = services.submit_ifta_quarter_for_approval(2025, 1)
        token = _approve_token(approval["approval_id"])
        services.approve_ifta_quarter(approval["approval_id"], token)

        sealed_file = tmp_path / "archive_root" / "Compliance" / "ifta_sealed_report" / f"{approval['approval_id']}.json"
        payload = json.loads(sealed_file.read_text(encoding="utf-8"))
        assert "resolved_evidence" in payload
        ok_entry = next(j for j in payload["resolved_evidence"] if j["jurisdiction"] == "OK")
        assert ok_entry["purchases"][0]["evidence"]["original_filename"] == "r.pdf"


# ── Routes ────────────────────────────────────────────────────────────


class TestEvidenceRoutes:
    def test_attach_via_multipart_upload(self, client):
        purchase = services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=40, amount=140, date="2025-01-10")
        resp = client.post(
            f"/api/dispatch/ifta/fuel-purchases/{purchase['purchase_id']}/evidence",
            data={"file": (io.BytesIO(b"receipt bytes"), "receipt.pdf")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201
        assert resp.get_json()["evidence"]["purchase_id"] == purchase["purchase_id"]

    def test_attach_missing_file_400(self, client):
        purchase = services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=40, amount=140, date="2025-01-10")
        resp = client.post(f"/api/dispatch/ifta/fuel-purchases/{purchase['purchase_id']}/evidence", data={})
        assert resp.status_code == 400

    def test_attach_unknown_purchase_404(self, client):
        resp = client.post(
            "/api/dispatch/ifta/fuel-purchases/FUEL-NOPE/evidence",
            data={"file": (io.BytesIO(b"x"), "r.pdf")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 404

    def test_attach_disallowed_extension_400(self, client):
        purchase = services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=40, amount=140, date="2025-01-10")
        resp = client.post(
            f"/api/dispatch/ifta/fuel-purchases/{purchase['purchase_id']}/evidence",
            data={"file": (io.BytesIO(b"x"), "malware.exe")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_download_roundtrip(self, client):
        purchase = services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=40, amount=140, date="2025-01-10")
        created = client.post(
            f"/api/dispatch/ifta/fuel-purchases/{purchase['purchase_id']}/evidence",
            data={"file": (io.BytesIO(b"receipt bytes"), "receipt.pdf")},
            content_type="multipart/form-data",
        ).get_json()["evidence"]
        resp = client.get(f"/api/dispatch/ifta/fuel-evidence/{created['evidence_id']}/download")
        assert resp.status_code == 200
        assert resp.data == b"receipt bytes"

    def test_download_unknown_evidence_404(self, client):
        resp = client.get("/api/dispatch/ifta/fuel-evidence/FUELEV-NOPE/download")
        assert resp.status_code == 404

    def test_list_evidence_for_purchase(self, client):
        purchase = services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=40, amount=140, date="2025-01-10")
        client.post(
            f"/api/dispatch/ifta/fuel-purchases/{purchase['purchase_id']}/evidence",
            data={"file": (io.BytesIO(b"x"), "r.pdf")},
            content_type="multipart/form-data",
        )
        resp = client.get(f"/api/dispatch/ifta/fuel-purchases/{purchase['purchase_id']}/evidence")
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 1


# ── build_ifta_review_dashboard() ────────────────────────────────────


class TestReviewDashboard:
    def test_zero_data_period_is_readiness_no_data(self):
        dash = services.build_ifta_review_dashboard(2030, 1)
        assert dash["readiness_status"] == "no data recorded yet this quarter"
        assert dash["total_purchase_count"] == 0
        assert dash["tax_position_source"] == "live_preview"

    def test_unlinked_purchase_drives_readiness_and_count(self):
        services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=50, amount=175, date="2025-01-16")
        services.add_ifta_trip_leg(jurisdiction="CA", miles=1000, date="2025-01-15")
        dash = services.build_ifta_review_dashboard(2025, 1)
        assert dash["unlinked_purchase_count"] == 1
        assert dash["total_purchase_count"] == 1
        assert "no receipt attached" in dash["readiness_status"]

    def test_all_linked_and_no_exceptions_is_ready_to_submit(self):
        purchase = services.add_ifta_fuel_purchase(jurisdiction="CA", gallons=50, amount=175, date="2025-01-16")
        services.attach_ifta_fuel_evidence(
            purchase_id=purchase["purchase_id"], file_data=b"r", original_filename="r.pdf",
        )
        services.add_ifta_trip_leg(jurisdiction="CA", miles=250, date="2025-01-15")
        dash = services.build_ifta_review_dashboard(2025, 1)
        assert dash["unlinked_purchase_count"] == 0
        assert dash["exceptions"] == []
        assert dash["readiness_status"] == "ready to submit"

    def test_implausible_mpg_produces_exception(self):
        # 5000 miles on 10 gallons -> 500 mpg, well outside DEFAULT_MPG_BAND
        services.add_ifta_trip_leg(jurisdiction="CA", miles=5000, date="2025-01-15")
        services.add_ifta_fuel_purchase(jurisdiction="CA", gallons=10, amount=35, date="2025-01-16")
        dash = services.build_ifta_review_dashboard(2025, 1)
        assert dash["exceptions"]
        assert any(e["exception_type"] == "fleet_mpg_out_of_band" for e in dash["exceptions"])
        assert "outside plausible range" in dash["exceptions"][0]["detail"]

    def test_sealed_quarter_shows_frozen_snapshot(self):
        _seed_taxable_quarter()
        approval = services.submit_ifta_quarter_for_approval(2025, 1)
        token = _approve_token(approval["approval_id"])
        services.approve_ifta_quarter(approval["approval_id"], token)
        dash = services.build_ifta_review_dashboard(2025, 1)
        assert dash["tax_position_source"] == "sealed"
        assert dash["readiness_status"] == "sealed"
        assert dash["approval_status"] == "sealed"

    def test_missing_rate_period_reports_blocked_not_raise(self, monkeypatch):
        from dispatch.models import IFTA_TAX_RATES
        services.add_ifta_trip_leg(jurisdiction="TX", miles=500, date="2025-01-15")
        monkeypatch.delitem(IFTA_TAX_RATES, "TX")
        dash = services.build_ifta_review_dashboard(2025, 1)
        assert dash["tax_position_source"] == "unavailable"
        assert "TX" in dash["tax_position_error"]

    def test_invalid_quarter_raises(self):
        with pytest.raises(ValueError, match="quarter"):
            services.build_ifta_review_dashboard(2025, 5)

    def test_dashboard_is_read_only(self):
        """Structural guard mirroring Hold's own dashboard boundary-refusal
        test technique: scans source for any store write call, proving
        the dashboard can't mutate data no matter what inputs it's given."""
        source = inspect.getsource(services.build_ifta_review_dashboard)
        forbidden_prefixes = (
            "store.create_", "store.update_", "store.delete_",
        )
        for line in source.splitlines():
            stripped = line.strip()
            for forbidden in forbidden_prefixes:
                assert forbidden not in stripped, f"dashboard calls a write function: {stripped}"


# ── Route: /ifta/review page ─────────────────────────────────────────


class TestReviewPage:
    def test_renders_with_zero_data(self, client):
        resp = client.get("/ifta/review?year=2030&quarter=1")
        assert resp.status_code == 200
        assert "no data recorded yet this quarter" in resp.data.decode()

    def test_renders_with_exception(self, client):
        services.add_ifta_trip_leg(jurisdiction="CA", miles=5000, date="2025-01-15")
        services.add_ifta_fuel_purchase(jurisdiction="CA", gallons=10, amount=35, date="2025-01-16")
        resp = client.get("/ifta/review?year=2025&quarter=1")
        assert resp.status_code == 200
        assert "outside plausible range" in resp.data.decode()
        assert "fleet_mpg_out_of_band" in resp.data.decode()

    def test_renders_with_mixed_linked_and_unlinked_purchases(self, client):
        linked = services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=50, amount=175, date="2025-01-16")
        services.attach_ifta_fuel_evidence(
            purchase_id=linked["purchase_id"], file_data=b"r", original_filename="receipt-ok.pdf",
        )
        services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=20, amount=70, date="2025-01-17")
        services.add_ifta_trip_leg(jurisdiction="CA", miles=1000, date="2025-01-15")
        resp = client.get("/ifta/review?year=2025&quarter=1")
        html = resp.data.decode()
        assert resp.status_code == 200
        assert "receipt-ok.pdf" in html
        assert "no receipt attached" in html

    def test_review_link_present_on_ifta_page(self, client):
        resp = client.get("/ifta?year=2025&quarter=1")
        assert "/ifta/review" in resp.data.decode()
