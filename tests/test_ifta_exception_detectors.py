"""Tests for Phase 6a: IFTA exception detectors -- six of Hold's ten
(src/dispatch/ifta/exceptions.py), ported to Dispatch's real data model,
persisted at submission time, and surfacing on the review dashboard's
Exceptions panel in place of Phase 5's ad hoc plausibility-warning
mechanism. Per DISPATCH_IFTA_PHASE6A_EXCEPTION_DETECTORS_LAUNCH_PACKAGE_v1."""

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


def _seal_quarter(year=2025, quarter=1, vehicle_id=""):
    approval = services.submit_ifta_quarter_for_approval(year, quarter, vehicle_id)
    token = _approve_token(approval["approval_id"])
    return services.approve_ifta_quarter(approval["approval_id"], token)


# ── Individual detectors, via run_ifta_exception_detectors() ─────────


class TestFuelNoMiles:
    def test_fires_when_fuel_purchased_with_zero_miles(self):
        services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=50, amount=175, date="2025-01-16")
        findings = services.run_ifta_exception_detectors(2025, 1)
        assert any(f["exception_type"] == "fuel_no_miles" and "OK" in f["detail"] for f in findings)

    def test_silent_when_jurisdiction_has_both(self):
        services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=50, amount=175, date="2025-01-16")
        services.add_ifta_trip_leg(jurisdiction="OK", miles=500, date="2025-01-15")
        findings = services.run_ifta_exception_detectors(2025, 1)
        assert not any(f["exception_type"] == "fuel_no_miles" for f in findings)


class TestMilesNoFuelGap:
    def test_fires_above_threshold(self):
        services.add_ifta_trip_leg(jurisdiction="CA", miles=1000, date="2025-01-15")
        findings = services.run_ifta_exception_detectors(2025, 1)
        assert any(f["exception_type"] == "miles_no_fuel_gap" and "CA" in f["detail"] for f in findings)

    def test_silent_below_threshold(self):
        services.add_ifta_trip_leg(jurisdiction="CA", miles=10, date="2025-01-15")
        findings = services.run_ifta_exception_detectors(2025, 1)
        assert not any(f["exception_type"] == "miles_no_fuel_gap" for f in findings)


class TestFleetMpgOutOfBand:
    def test_fires_outside_band(self):
        services.add_ifta_trip_leg(jurisdiction="CA", miles=5000, date="2025-01-15")
        services.add_ifta_fuel_purchase(jurisdiction="CA", gallons=10, amount=35, date="2025-01-16")
        findings = services.run_ifta_exception_detectors(2025, 1)
        assert any(f["exception_type"] == "fleet_mpg_out_of_band" for f in findings)

    def test_silent_inside_band(self):
        services.add_ifta_trip_leg(jurisdiction="CA", miles=250, date="2025-01-15")
        services.add_ifta_fuel_purchase(jurisdiction="CA", gallons=50, amount=175, date="2025-01-16")
        findings = services.run_ifta_exception_detectors(2025, 1)
        assert not any(f["exception_type"] == "fleet_mpg_out_of_band" for f in findings)


class TestCornerClipping:
    def test_fires_for_small_nonzero_miles(self):
        services.add_ifta_trip_leg(jurisdiction="NV", miles=2.5, date="2025-01-15")
        findings = services.run_ifta_exception_detectors(2025, 1)
        assert any(f["exception_type"] == "corner_clipping" and "NV" in f["detail"] for f in findings)

    def test_silent_for_zero_miles(self):
        # a jurisdiction with 0 miles never appears in the jurisdictions
        # list at all (nothing to report), so corner_clipping can't fire.
        findings = services.run_ifta_exception_detectors(2025, 1)
        assert not any(f["exception_type"] == "corner_clipping" for f in findings)


class TestBrokenEvidenceLinkage:
    def test_silent_when_file_intact(self):
        purchase = services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=50, amount=175, date="2025-01-16")
        services.attach_ifta_fuel_evidence(
            purchase_id=purchase["purchase_id"], file_data=b"receipt", original_filename="r.pdf",
        )
        findings = services.run_ifta_exception_detectors(2025, 1)
        assert not any(f["exception_type"] == "broken_evidence_linkage" for f in findings)

    def test_fires_when_file_deleted_from_disk(self):
        purchase = services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=50, amount=175, date="2025-01-16")
        ev = services.attach_ifta_fuel_evidence(
            purchase_id=purchase["purchase_id"], file_data=b"receipt", original_filename="r.pdf",
        )
        file_path, _ = services.get_ifta_fuel_evidence_file(ev["evidence_id"])
        file_path.unlink()
        findings = services.run_ifta_exception_detectors(2025, 1)
        assert any(
            f["exception_type"] == "broken_evidence_linkage" and "missing on disk" in f["detail"]
            for f in findings
        )

    def test_fires_when_file_content_tampered(self):
        purchase = services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=50, amount=175, date="2025-01-16")
        ev = services.attach_ifta_fuel_evidence(
            purchase_id=purchase["purchase_id"], file_data=b"receipt", original_filename="r.pdf",
        )
        file_path, _ = services.get_ifta_fuel_evidence_file(ev["evidence_id"])
        file_path.write_bytes(b"tampered content")
        findings = services.run_ifta_exception_detectors(2025, 1)
        assert any(
            f["exception_type"] == "broken_evidence_linkage" and "no longer matches" in f["detail"]
            for f in findings
        )


class TestLateArrivalClosedQuarter:
    def test_silent_before_sealing(self):
        services.add_ifta_trip_leg(jurisdiction="CA", miles=1000, date="2025-01-15")
        services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=50, amount=175, date="2025-01-16")
        findings = services.run_ifta_exception_detectors(2025, 1)
        assert not any(f["exception_type"] == "late_arrival_closed_quarter" for f in findings)

    def test_fires_for_record_added_after_sealing(self):
        services.add_ifta_trip_leg(jurisdiction="CA", miles=1000, date="2025-01-15")
        services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=50, amount=175, date="2025-01-16")
        _seal_quarter()

        late_leg = services.add_ifta_trip_leg(jurisdiction="TX", miles=200, date="2025-01-20")
        findings = services.run_ifta_exception_detectors(2025, 1)
        matches = [f for f in findings if f["exception_type"] == "late_arrival_closed_quarter"]
        assert any(late_leg["leg_id"] in f["related_record_ids"] for f in matches)

    def test_silent_for_records_that_were_part_of_the_seal(self):
        services.add_ifta_trip_leg(jurisdiction="CA", miles=1000, date="2025-01-15")
        services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=50, amount=175, date="2025-01-16")
        _seal_quarter()

        findings = services.run_ifta_exception_detectors(2025, 1)
        assert not any(f["exception_type"] == "late_arrival_closed_quarter" for f in findings)


class TestRunDetectorsValidation:
    def test_invalid_quarter_raises(self):
        with pytest.raises(ValueError, match="quarter"):
            services.run_ifta_exception_detectors(2025, 7)

    def test_exception_types_are_the_documented_six(self):
        from dispatch.models import IFTA_EXCEPTION_TYPES
        assert IFTA_EXCEPTION_TYPES == [
            "fuel_no_miles", "miles_no_fuel_gap", "fleet_mpg_out_of_band",
            "broken_evidence_linkage", "late_arrival_closed_quarter", "corner_clipping",
        ]

    def test_read_only_no_writes(self):
        """Structural guard, mirroring Phase 5's dashboard read-only test
        and Hold's own source-scan technique: neither the public
        entrypoint nor the internal runner may call a store write
        function."""
        for fn in (services.run_ifta_exception_detectors, services._run_ifta_exception_detectors_on_snapshot):
            source = inspect.getsource(fn)
            for line in source.splitlines():
                stripped = line.strip()
                for forbidden in ("store.create_", "store.update_", "store.delete_"):
                    assert forbidden not in stripped, f"{fn.__name__} calls a write function: {stripped}"


# ── Persistence at submission time ────────────────────────────────────


class TestPersistenceAtSubmission:
    def test_findings_persisted_and_tied_to_approval(self):
        services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=50, amount=175, date="2025-01-16")
        approval = services.submit_ifta_quarter_for_approval(2025, 1)
        persisted = services.list_ifta_exceptions(approval["approval_id"])
        assert any(e["exception_type"] == "fuel_no_miles" for e in persisted)

    def test_no_findings_persists_empty_list_not_nothing(self):
        services.add_ifta_trip_leg(jurisdiction="CA", miles=250, date="2025-01-15")
        services.add_ifta_fuel_purchase(jurisdiction="CA", gallons=50, amount=175, date="2025-01-16")
        approval = services.submit_ifta_quarter_for_approval(2025, 1)
        assert services.list_ifta_exceptions(approval["approval_id"]) == []

    def test_sealed_dashboard_reads_persisted_not_recomputed(self):
        """Once sealed, the dashboard's exceptions must come from the
        frozen ifta_exceptions rows, not a fresh live run -- confirmed by
        deleting the underlying purchase's evidence file *after* sealing
        and checking the dashboard still reports the same persisted
        findings (an empty set), not a newly-detected broken-linkage
        exception that a live re-run would find."""
        purchase = services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=50, amount=175, date="2025-01-16")
        services.attach_ifta_fuel_evidence(
            purchase_id=purchase["purchase_id"], file_data=b"receipt", original_filename="r.pdf",
        )
        services.add_ifta_trip_leg(jurisdiction="CA", miles=250, date="2025-01-15")
        sealed = _seal_quarter()
        persisted_before = services.list_ifta_exceptions(sealed["approval_id"])

        # tamper with the evidence file after sealing
        ev_id = store.get_ifta_fuel_purchase(purchase["purchase_id"])["evidence_id"]
        file_path, _ = services.get_ifta_fuel_evidence_file(ev_id)
        file_path.unlink()

        dash = services.build_ifta_review_dashboard(2025, 1)
        assert dash["exceptions"] == persisted_before


# ── Routes ────────────────────────────────────────────────────────────


class TestExceptionsRoute:
    def test_list_exceptions_for_approval(self, client):
        client.post("/api/dispatch/ifta/fuel-purchases", json={"jurisdiction": "OK", "gallons": 50, "amount": 175, "date": "2025-01-16"})
        created = client.post("/api/dispatch/ifta/report-approvals", json={"year": 2025, "quarter": 1}).get_json()
        resp = client.get(f"/api/dispatch/ifta/report-approvals/{created['approval_id']}/exceptions")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert any(e["exception_type"] == "fuel_no_miles" for e in data["exceptions"])

    def test_exceptions_for_unknown_approval_404(self, client):
        resp = client.get("/api/dispatch/ifta/report-approvals/IFTAAPR-NOPE/exceptions")
        assert resp.status_code == 404
