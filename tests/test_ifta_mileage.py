"""Tests for IFTA mileage & fuel tracking — models, store, services, API, template."""

from __future__ import annotations

import json

import pytest

from dispatch.db import set_db_path
from dispatch.models import (
    IFTA_JURISDICTIONS,
    IFTA_QUARTERS,
    IFTAFuelPurchase,
    IFTATripLeg,
)
from dispatch import services, store


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


# ── Model tests ────────────────────────────────────────────────────


class TestIFTATripLegModel:
    def test_defaults(self):
        leg = IFTATripLeg(jurisdiction="TX", miles=150)
        assert leg.leg_id.startswith("IFTA-")
        assert leg.jurisdiction == "TX"
        assert leg.miles == 150
        assert leg.date
        assert leg.created_at

    def test_invalid_jurisdiction(self):
        with pytest.raises(ValueError, match="jurisdiction"):
            IFTATripLeg(jurisdiction="ZZ", miles=100)

    def test_to_dict(self):
        leg = IFTATripLeg(jurisdiction="CA", miles=200)
        d = leg.to_dict()
        assert d["jurisdiction"] == "CA"
        assert d["miles"] == 200

    def test_empty_jurisdiction_allowed(self):
        leg = IFTATripLeg(miles=100)
        assert leg.jurisdiction == ""

    def test_vehicle_id(self):
        leg = IFTATripLeg(jurisdiction="TX", miles=50, vehicle_id="EQP-001")
        assert leg.vehicle_id == "EQP-001"


class TestIFTAFuelPurchaseModel:
    def test_defaults(self):
        p = IFTAFuelPurchase(jurisdiction="TX", gallons=50, amount=175.50)
        assert p.purchase_id.startswith("FUEL-")
        assert p.jurisdiction == "TX"
        assert p.gallons == 50
        assert p.amount == 175.50

    def test_price_per_gallon(self):
        p = IFTAFuelPurchase(jurisdiction="OK", gallons=40, amount=140)
        assert p.price_per_gallon == 3.5

    def test_price_per_gallon_zero_gallons(self):
        p = IFTAFuelPurchase(jurisdiction="OK", gallons=0, amount=0)
        assert p.price_per_gallon == 0.0

    def test_invalid_jurisdiction(self):
        with pytest.raises(ValueError, match="jurisdiction"):
            IFTAFuelPurchase(jurisdiction="INVALID", gallons=10, amount=35)

    def test_to_dict_has_price_per_gallon(self):
        p = IFTAFuelPurchase(jurisdiction="CA", gallons=100, amount=450)
        d = p.to_dict()
        assert d["price_per_gallon"] == 4.5

    def test_jurisdictions_list(self):
        assert "TX" in IFTA_JURISDICTIONS
        assert "CA" in IFTA_JURISDICTIONS
        assert "ON" in IFTA_JURISDICTIONS
        assert len(IFTA_QUARTERS) == 4


# ── Store tests ────────────────────────────────────────────────────


class TestIFTATripLegStore:
    def test_create_and_get(self):
        leg = IFTATripLeg(jurisdiction="TX", miles=150, date="2025-01-15")
        result = store.create_ifta_trip_leg(leg)
        assert result["jurisdiction"] == "TX"
        fetched = store.get_ifta_trip_leg(result["leg_id"])
        assert fetched is not None
        assert fetched["miles"] == 150

    def test_list_with_filters(self):
        store.create_ifta_trip_leg(IFTATripLeg(jurisdiction="TX", miles=100, date="2025-01-15"))
        store.create_ifta_trip_leg(IFTATripLeg(jurisdiction="OK", miles=80, date="2025-01-20"))
        store.create_ifta_trip_leg(IFTATripLeg(jurisdiction="TX", miles=120, date="2025-02-10"))

        all_legs = store.list_ifta_trip_legs()
        assert len(all_legs) == 3

        tx_legs = store.list_ifta_trip_legs(jurisdiction="TX")
        assert len(tx_legs) == 2

        jan_legs = store.list_ifta_trip_legs(date_from="2025-01-01", date_to="2025-01-31")
        assert len(jan_legs) == 2

    def test_update(self):
        leg = IFTATripLeg(jurisdiction="TX", miles=100, date="2025-01-15")
        result = store.create_ifta_trip_leg(leg)
        updated = store.update_ifta_trip_leg(result["leg_id"], {"miles": 200})
        assert updated["miles"] == 200

    def test_delete(self):
        leg = IFTATripLeg(jurisdiction="TX", miles=100, date="2025-01-15")
        result = store.create_ifta_trip_leg(leg)
        assert store.delete_ifta_trip_leg(result["leg_id"]) is True
        assert store.get_ifta_trip_leg(result["leg_id"]) is None

    def test_delete_nonexistent(self):
        assert store.delete_ifta_trip_leg("IFTA-NOPE") is False

    def test_get_nonexistent(self):
        assert store.get_ifta_trip_leg("IFTA-NOPE") is None

    def test_list_by_vehicle(self):
        store.create_ifta_trip_leg(IFTATripLeg(jurisdiction="TX", miles=100, vehicle_id="V1"))
        store.create_ifta_trip_leg(IFTATripLeg(jurisdiction="OK", miles=80, vehicle_id="V2"))
        v1_legs = store.list_ifta_trip_legs(vehicle_id="V1")
        assert len(v1_legs) == 1
        assert v1_legs[0]["vehicle_id"] == "V1"

    def test_list_by_load_id(self):
        store.create_ifta_trip_leg(IFTATripLeg(jurisdiction="TX", miles=100, load_id="LOAD-1"))
        store.create_ifta_trip_leg(IFTATripLeg(jurisdiction="OK", miles=80, load_id="LOAD-2"))
        legs = store.list_ifta_trip_legs(load_id="LOAD-1")
        assert len(legs) == 1


class TestIFTAFuelPurchaseStore:
    def test_create_and_get(self):
        p = IFTAFuelPurchase(jurisdiction="TX", gallons=50, amount=175, date="2025-01-15")
        result = store.create_ifta_fuel_purchase(p)
        assert result["jurisdiction"] == "TX"
        assert result["price_per_gallon"] == 3.5
        fetched = store.get_ifta_fuel_purchase(result["purchase_id"])
        assert fetched is not None
        assert fetched["gallons"] == 50

    def test_list_with_filters(self):
        store.create_ifta_fuel_purchase(IFTAFuelPurchase(jurisdiction="TX", gallons=50, amount=175, date="2025-01-15"))
        store.create_ifta_fuel_purchase(IFTAFuelPurchase(jurisdiction="OK", gallons=40, amount=140, date="2025-01-20"))
        store.create_ifta_fuel_purchase(IFTAFuelPurchase(jurisdiction="TX", gallons=60, amount=210, date="2025-02-10"))

        all_p = store.list_ifta_fuel_purchases()
        assert len(all_p) == 3
        assert all("price_per_gallon" in p for p in all_p)

        tx_p = store.list_ifta_fuel_purchases(jurisdiction="TX")
        assert len(tx_p) == 2

    def test_update(self):
        p = IFTAFuelPurchase(jurisdiction="TX", gallons=50, amount=175, date="2025-01-15")
        result = store.create_ifta_fuel_purchase(p)
        updated = store.update_ifta_fuel_purchase(result["purchase_id"], {"gallons": 60, "amount": 210})
        assert updated["gallons"] == 60
        assert updated["amount"] == 210

    def test_delete(self):
        p = IFTAFuelPurchase(jurisdiction="TX", gallons=50, amount=175, date="2025-01-15")
        result = store.create_ifta_fuel_purchase(p)
        assert store.delete_ifta_fuel_purchase(result["purchase_id"]) is True
        assert store.get_ifta_fuel_purchase(result["purchase_id"]) is None

    def test_delete_nonexistent(self):
        assert store.delete_ifta_fuel_purchase("FUEL-NOPE") is False


# ── Service tests ──────────────────────────────────────────────────


class TestIFTATripLegService:
    def test_add_trip_leg(self):
        result = services.add_ifta_trip_leg(jurisdiction="TX", miles=150, date="2025-01-15")
        assert result["jurisdiction"] == "TX"
        assert result["miles"] == 150

    def test_add_trip_leg_invalid_jurisdiction(self):
        with pytest.raises(ValueError, match="jurisdiction"):
            services.add_ifta_trip_leg(jurisdiction="ZZ", miles=100)

    def test_add_trip_leg_negative_miles(self):
        with pytest.raises(ValueError, match="Miles"):
            services.add_ifta_trip_leg(jurisdiction="TX", miles=-10)

    def test_update_trip_leg(self):
        result = services.add_ifta_trip_leg(jurisdiction="TX", miles=100)
        updated = services.update_ifta_trip_leg(result["leg_id"], miles=200)
        assert updated["miles"] == 200

    def test_update_trip_leg_not_found(self):
        with pytest.raises(ValueError, match="not found"):
            services.update_ifta_trip_leg("IFTA-NOPE", miles=100)

    def test_update_trip_leg_invalid_jurisdiction(self):
        result = services.add_ifta_trip_leg(jurisdiction="TX", miles=100)
        with pytest.raises(ValueError, match="jurisdiction"):
            services.update_ifta_trip_leg(result["leg_id"], jurisdiction="ZZ")

    def test_delete_trip_leg(self):
        result = services.add_ifta_trip_leg(jurisdiction="TX", miles=100)
        assert services.delete_ifta_trip_leg(result["leg_id"]) is True

    def test_list_trip_legs(self):
        services.add_ifta_trip_leg(jurisdiction="TX", miles=100, date="2025-01-15")
        services.add_ifta_trip_leg(jurisdiction="OK", miles=80, date="2025-01-20")
        legs = services.list_ifta_trip_legs()
        assert len(legs) == 2

    def test_update_negative_miles(self):
        result = services.add_ifta_trip_leg(jurisdiction="TX", miles=100)
        with pytest.raises(ValueError, match="Miles"):
            services.update_ifta_trip_leg(result["leg_id"], miles=-5)


class TestIFTAFuelPurchaseService:
    def test_add_fuel_purchase(self):
        result = services.add_ifta_fuel_purchase(
            jurisdiction="TX", gallons=50, amount=175, date="2025-01-15"
        )
        assert result["jurisdiction"] == "TX"
        assert result["gallons"] == 50
        assert result["price_per_gallon"] == 3.5

    def test_add_fuel_purchase_invalid_jurisdiction(self):
        with pytest.raises(ValueError, match="jurisdiction"):
            services.add_ifta_fuel_purchase(jurisdiction="ZZ", gallons=10, amount=35)

    def test_add_fuel_purchase_negative_gallons(self):
        with pytest.raises(ValueError, match="Gallons"):
            services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=-10, amount=35)

    def test_add_fuel_purchase_negative_amount(self):
        with pytest.raises(ValueError, match="Amount"):
            services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=10, amount=-35)

    def test_update_fuel_purchase(self):
        result = services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=50, amount=175)
        updated = services.update_ifta_fuel_purchase(result["purchase_id"], gallons=60, amount=210)
        assert updated["gallons"] == 60

    def test_update_fuel_purchase_not_found(self):
        with pytest.raises(ValueError, match="not found"):
            services.update_ifta_fuel_purchase("FUEL-NOPE", gallons=10)

    def test_delete_fuel_purchase(self):
        result = services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=50, amount=175)
        assert services.delete_ifta_fuel_purchase(result["purchase_id"]) is True

    def test_list_fuel_purchases(self):
        services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=50, amount=175)
        services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=40, amount=140)
        purchases = services.list_ifta_fuel_purchases()
        assert len(purchases) == 2


class TestIFTAQuarterlyReport:
    def test_empty_report(self):
        report = services.get_ifta_quarterly_report(2025, 1)
        assert report["year"] == 2025
        assert report["quarter"] == 1
        assert report["quarter_label"] == "Q1 2025"
        assert report["total_miles"] == 0
        assert report["total_gallons"] == 0
        assert report["fleet_mpg"] == 0
        assert report["jurisdictions"] == []

    def test_invalid_quarter(self):
        with pytest.raises(ValueError, match="quarter"):
            services.get_ifta_quarterly_report(2025, 5)

    def test_report_with_data(self):
        services.add_ifta_trip_leg(jurisdiction="TX", miles=500, date="2025-01-15")
        services.add_ifta_trip_leg(jurisdiction="OK", miles=200, date="2025-02-10")
        services.add_ifta_trip_leg(jurisdiction="TX", miles=300, date="2025-03-05")
        services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=100, amount=350, date="2025-01-20")
        services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=40, amount=140, date="2025-02-15")

        report = services.get_ifta_quarterly_report(2025, 1)
        assert report["total_miles"] == 1000
        assert report["total_gallons"] == 140
        assert report["fleet_mpg"] == pytest.approx(1000 / 140, abs=0.01)
        assert len(report["jurisdictions"]) == 2

        tx = next(j for j in report["jurisdictions"] if j["jurisdiction"] == "TX")
        assert tx["miles"] == 800
        assert tx["fuel_gallons"] == 100

        ok = next(j for j in report["jurisdictions"] if j["jurisdiction"] == "OK")
        assert ok["miles"] == 200
        assert ok["fuel_gallons"] == 40

    def test_report_date_filtering(self):
        services.add_ifta_trip_leg(jurisdiction="TX", miles=500, date="2025-01-15")
        services.add_ifta_trip_leg(jurisdiction="TX", miles=300, date="2025-04-10")

        q1 = services.get_ifta_quarterly_report(2025, 1)
        assert q1["total_miles"] == 500
        assert q1["trip_leg_count"] == 1

        q2 = services.get_ifta_quarterly_report(2025, 2)
        assert q2["total_miles"] == 300
        assert q2["trip_leg_count"] == 1

    def test_report_vehicle_filter(self):
        services.add_ifta_trip_leg(jurisdiction="TX", miles=500, date="2025-01-15", vehicle_id="V1")
        services.add_ifta_trip_leg(jurisdiction="TX", miles=300, date="2025-01-20", vehicle_id="V2")
        services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=50, amount=175, date="2025-01-15", vehicle_id="V1")

        report = services.get_ifta_quarterly_report(2025, 1, vehicle_id="V1")
        assert report["total_miles"] == 500
        assert report["total_gallons"] == 50
        assert report["vehicle_id"] == "V1"

    def test_net_taxable_gallons(self):
        services.add_ifta_trip_leg(jurisdiction="TX", miles=1000, date="2025-01-15")
        services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=200, amount=700, date="2025-01-20")

        report = services.get_ifta_quarterly_report(2025, 1)
        tx = report["jurisdictions"][0]
        mpg = report["fleet_mpg"]
        expected_taxable = 1000 / mpg
        expected_net = expected_taxable - 200
        assert tx["taxable_gallons"] == pytest.approx(expected_taxable, abs=0.01)
        assert tx["net_taxable_gallons"] == pytest.approx(expected_net, abs=0.01)

    def test_fuel_only_jurisdiction(self):
        services.add_ifta_trip_leg(jurisdiction="TX", miles=1000, date="2025-01-15")
        services.add_ifta_fuel_purchase(jurisdiction="OK", gallons=50, amount=175, date="2025-01-20")

        report = services.get_ifta_quarterly_report(2025, 1)
        assert len(report["jurisdictions"]) == 2
        ok = next(j for j in report["jurisdictions"] if j["jurisdiction"] == "OK")
        assert ok["miles"] == 0
        assert ok["fuel_gallons"] == 50
        assert ok["net_taxable_gallons"] < 0

    def test_quarter_date_ranges(self):
        from dispatch.services import _quarter_date_range
        assert _quarter_date_range(2025, 1) == ("2025-01-01", "2025-03-31")
        assert _quarter_date_range(2025, 2) == ("2025-04-01", "2025-06-30")
        assert _quarter_date_range(2025, 3) == ("2025-07-01", "2025-09-30")
        assert _quarter_date_range(2025, 4) == ("2025-10-01", "2025-12-31")


# ── API tests ──────────────────────────────────────────────────────


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestIFTATripLegAPI:
    def test_add_trip_leg(self, client):
        resp = client.post("/api/dispatch/ifta/trip-legs", json={
            "jurisdiction": "TX", "miles": 150, "date": "2025-01-15"
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["jurisdiction"] == "TX"

    def test_add_trip_leg_invalid(self, client):
        resp = client.post("/api/dispatch/ifta/trip-legs", json={
            "jurisdiction": "ZZ", "miles": 150
        })
        assert resp.status_code == 400

    def test_list_trip_legs(self, client):
        client.post("/api/dispatch/ifta/trip-legs", json={
            "jurisdiction": "TX", "miles": 100, "date": "2025-01-15"
        })
        resp = client.get("/api/dispatch/ifta/trip-legs")
        assert resp.status_code == 200
        assert len(resp.get_json()) == 1

    def test_update_trip_leg(self, client):
        resp = client.post("/api/dispatch/ifta/trip-legs", json={
            "jurisdiction": "TX", "miles": 100
        })
        leg_id = resp.get_json()["leg_id"]
        resp2 = client.patch(f"/api/dispatch/ifta/trip-legs/{leg_id}", json={"miles": 200})
        assert resp2.status_code == 200
        assert resp2.get_json()["miles"] == 200

    def test_delete_trip_leg(self, client):
        resp = client.post("/api/dispatch/ifta/trip-legs", json={
            "jurisdiction": "TX", "miles": 100
        })
        leg_id = resp.get_json()["leg_id"]
        resp2 = client.delete(f"/api/dispatch/ifta/trip-legs/{leg_id}")
        assert resp2.status_code == 200

    def test_delete_trip_leg_not_found(self, client):
        resp = client.delete("/api/dispatch/ifta/trip-legs/IFTA-NOPE")
        assert resp.status_code == 404

    def test_list_with_filters(self, client):
        client.post("/api/dispatch/ifta/trip-legs", json={
            "jurisdiction": "TX", "miles": 100, "date": "2025-01-15"
        })
        client.post("/api/dispatch/ifta/trip-legs", json={
            "jurisdiction": "OK", "miles": 80, "date": "2025-04-10"
        })
        resp = client.get("/api/dispatch/ifta/trip-legs?jurisdiction=TX")
        assert len(resp.get_json()) == 1


class TestIFTAFuelPurchaseAPI:
    def test_add_fuel_purchase(self, client):
        resp = client.post("/api/dispatch/ifta/fuel-purchases", json={
            "jurisdiction": "TX", "gallons": 50, "amount": 175, "date": "2025-01-15"
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["jurisdiction"] == "TX"
        assert data["price_per_gallon"] == 3.5

    def test_add_fuel_purchase_invalid(self, client):
        resp = client.post("/api/dispatch/ifta/fuel-purchases", json={
            "jurisdiction": "ZZ", "gallons": 50, "amount": 175
        })
        assert resp.status_code == 400

    def test_list_fuel_purchases(self, client):
        client.post("/api/dispatch/ifta/fuel-purchases", json={
            "jurisdiction": "TX", "gallons": 50, "amount": 175
        })
        resp = client.get("/api/dispatch/ifta/fuel-purchases")
        assert resp.status_code == 200
        assert len(resp.get_json()) == 1

    def test_update_fuel_purchase(self, client):
        resp = client.post("/api/dispatch/ifta/fuel-purchases", json={
            "jurisdiction": "TX", "gallons": 50, "amount": 175
        })
        pid = resp.get_json()["purchase_id"]
        resp2 = client.patch(f"/api/dispatch/ifta/fuel-purchases/{pid}", json={"gallons": 60})
        assert resp2.status_code == 200
        assert resp2.get_json()["gallons"] == 60

    def test_delete_fuel_purchase(self, client):
        resp = client.post("/api/dispatch/ifta/fuel-purchases", json={
            "jurisdiction": "TX", "gallons": 50, "amount": 175
        })
        pid = resp.get_json()["purchase_id"]
        resp2 = client.delete(f"/api/dispatch/ifta/fuel-purchases/{pid}")
        assert resp2.status_code == 200

    def test_delete_fuel_purchase_not_found(self, client):
        resp = client.delete("/api/dispatch/ifta/fuel-purchases/FUEL-NOPE")
        assert resp.status_code == 404


class TestIFTAReportAPI:
    def test_report_endpoint(self, client):
        client.post("/api/dispatch/ifta/trip-legs", json={
            "jurisdiction": "TX", "miles": 500, "date": "2025-01-15"
        })
        client.post("/api/dispatch/ifta/fuel-purchases", json={
            "jurisdiction": "TX", "gallons": 100, "amount": 350, "date": "2025-01-20"
        })
        resp = client.get("/api/dispatch/ifta/report?year=2025&quarter=1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_miles"] == 500
        assert data["total_gallons"] == 100

    def test_report_missing_params(self, client):
        resp = client.get("/api/dispatch/ifta/report")
        assert resp.status_code == 400

    def test_report_invalid_quarter(self, client):
        resp = client.get("/api/dispatch/ifta/report?year=2025&quarter=5")
        assert resp.status_code == 400


# ── Template tests ─────────────────────────────────────────────────


class TestIFTATemplate:
    def test_ifta_page_loads(self, client):
        resp = client.get("/ifta")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "IFTA" in html
        assert "Trip Leg" in html
        assert "Fuel Purchase" in html

    def test_ifta_page_with_quarter(self, client):
        resp = client.get("/ifta?year=2025&quarter=2")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Q2 2025" in html

    def test_ifta_page_with_data(self, client):
        client.post("/api/dispatch/ifta/trip-legs", json={
            "jurisdiction": "TX", "miles": 500, "date": "2025-01-15"
        })
        client.post("/api/dispatch/ifta/fuel-purchases", json={
            "jurisdiction": "TX", "gallons": 100, "amount": 350, "date": "2025-01-20"
        })
        resp = client.get("/ifta?year=2025&quarter=1")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "TX" in html
        assert "500" in html

    def test_ifta_nav_link(self, client):
        resp = client.get("/ifta")
        html = resp.data.decode()
        assert "/ifta" in html

    def test_print_button(self, client):
        resp = client.get("/ifta?year=2025&quarter=1")
        html = resp.data.decode()
        assert "Print" in html
        assert "Export CSV" in html
