"""Tests for fuel cost estimator feature."""

from __future__ import annotations

import pytest

from dispatch.db import set_db_path
from dispatch import services, store
from dispatch.models import IFTAFuelPurchase, IFTATripLeg, RateConfirmation


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


def _make_load(**kw) -> dict:
    defaults = {"customer": "Test Co", "pickup_location": "A", "delivery_location": "B"}
    defaults.update(kw)
    return services.create_load(**defaults)


def _add_fuel_purchase(gallons=50.0, amount=200.0, jurisdiction="TX", vehicle_id="TRK-1"):
    return services.add_ifta_fuel_purchase(
        jurisdiction=jurisdiction, gallons=gallons, amount=amount,
        date="2026-07-15", vehicle_id=vehicle_id,
    )


def _add_trip_leg(miles=300.0, jurisdiction="TX", vehicle_id="TRK-1"):
    return services.add_ifta_trip_leg(
        jurisdiction=jurisdiction, miles=miles,
        date="2026-07-15", vehicle_id=vehicle_id,
    )


# ── Service tests ────────────────────────────────────────────────────


class TestFuelEstimatorService:
    def test_estimate_with_all_params(self):
        result = services.estimate_fuel_cost(
            distance_miles=500, mpg=7.0, fuel_price=4.50,
        )
        assert result["distance_miles"] == 500
        assert result["mpg"] == 7.0
        assert result["fuel_price_per_gallon"] == 4.50
        assert result["gallons_needed"] == round(500 / 7.0, 2)
        assert result["estimated_cost"] == round(500 / 7.0 * 4.50, 2)
        assert result["cost_per_mile"] > 0

    def test_estimate_zero_distance(self):
        result = services.estimate_fuel_cost(distance_miles=0, mpg=7, fuel_price=4)
        assert result["estimated_cost"] == 0
        assert result["gallons_needed"] == 0
        assert result["cost_per_mile"] == 0

    def test_estimate_uses_fleet_mpg_default(self):
        _add_trip_leg(miles=700)
        _add_fuel_purchase(gallons=100, amount=400)
        result = services.estimate_fuel_cost(distance_miles=350, fuel_price=4.0)
        assert result["mpg"] == 7.0
        expected_gallons = round(350 / 7.0, 2)
        assert result["gallons_needed"] == expected_gallons

    def test_estimate_uses_avg_fuel_price_default(self):
        _add_fuel_purchase(gallons=100, amount=450)
        result = services.estimate_fuel_cost(distance_miles=200, mpg=6.5)
        assert result["fuel_price_per_gallon"] == 4.50

    def test_estimate_from_load_distance(self):
        load = _make_load()
        store.create_rate_confirmation(RateConfirmation(
            load_id=load["load_id"], rate_amount=2000, distance_miles=600,
        ))
        result = services.estimate_fuel_cost(
            load_id=load["load_id"], mpg=6.0, fuel_price=4.0,
        )
        assert result["distance_miles"] == 600
        assert result["gallons_needed"] == 100
        assert result["estimated_cost"] == 400

    def test_estimate_explicit_distance_overrides_load(self):
        load = _make_load()
        store.create_rate_confirmation(RateConfirmation(
            load_id=load["load_id"], rate_amount=2000, distance_miles=600,
        ))
        result = services.estimate_fuel_cost(
            distance_miles=300, load_id=load["load_id"], mpg=6.0, fuel_price=4.0,
        )
        assert result["distance_miles"] == 300

    def test_estimate_no_data_returns_zeros(self):
        result = services.estimate_fuel_cost()
        assert result["estimated_cost"] == 0
        assert result["mpg"] == 0
        assert result["fuel_price_per_gallon"] == 0

    def test_get_avg_fuel_price_no_data(self):
        assert services.get_avg_fuel_price() == 0.0

    def test_get_avg_fuel_price_with_data(self):
        _add_fuel_purchase(gallons=50, amount=200)
        _add_fuel_purchase(gallons=50, amount=250)
        avg = services.get_avg_fuel_price()
        assert avg == round(450 / 100, 4)

    def test_get_fleet_mpg_no_data(self):
        assert services.get_fleet_mpg() == 0.0

    def test_get_fleet_mpg_with_data(self):
        _add_trip_leg(miles=500)
        _add_trip_leg(miles=300)
        _add_fuel_purchase(gallons=100, amount=400)
        mpg = services.get_fleet_mpg()
        assert mpg == 8.0

    def test_cost_per_mile(self):
        result = services.estimate_fuel_cost(
            distance_miles=1000, mpg=8.0, fuel_price=4.0,
        )
        assert result["cost_per_mile"] == 0.5


# ── API tests ────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app({"TESTING": True})
    with app.test_client() as c:
        yield c


class TestFuelEstimatorAPI:
    def test_estimate_get_with_params(self, client):
        resp = client.get("/api/dispatch/fuel-estimate?distance_miles=500&mpg=7&fuel_price=4.5")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["estimated_cost"] == round(500 / 7 * 4.5, 2)

    def test_estimate_post(self, client):
        resp = client.post("/api/dispatch/fuel-estimate", json={
            "distance_miles": 300, "mpg": 6.5, "fuel_price": 4.0,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["estimated_cost"] == round(300 / 6.5 * 4.0, 2)

    def test_estimate_with_load_id(self, client):
        resp = client.post("/api/dispatch/loads", json={"customer": "API Co"})
        load_id = resp.get_json()["load"]["load_id"]
        client.post(f"/api/dispatch/loads/{load_id}/rate", json={
            "rate_amount": 2000, "distance_miles": 450,
        })
        resp = client.get(f"/api/dispatch/fuel-estimate?load_id={load_id}&mpg=7&fuel_price=4")
        data = resp.get_json()
        assert data["distance_miles"] == 450

    def test_estimate_no_params(self, client):
        resp = client.get("/api/dispatch/fuel-estimate")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["estimated_cost"] == 0

    def test_fuel_defaults_endpoint(self, client):
        resp = client.get("/api/dispatch/fuel-defaults")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "avg_fuel_price" in data
        assert "fleet_mpg" in data

    def test_fuel_defaults_with_data(self, client):
        _add_trip_leg(miles=700)
        _add_fuel_purchase(gallons=100, amount=400)
        resp = client.get("/api/dispatch/fuel-defaults")
        data = resp.get_json()
        assert data["fleet_mpg"] == 7.0
        assert data["avg_fuel_price"] == 4.0

    def test_add_estimate_as_expense(self, client):
        resp = client.post("/api/dispatch/loads", json={"customer": "Expense Co"})
        load_id = resp.get_json()["load"]["load_id"]
        resp = client.post(f"/api/dispatch/loads/{load_id}/expenses", json={
            "category": "fuel",
            "description": "500 mi @ 7 MPG, $4.500/gal",
            "amount": 321.43,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["expense"]["category"] == "fuel"
        assert data["expense"]["amount"] == 321.43


# ── Template tests ───────────────────────────────────────────────────


class TestFuelEstimatorTemplate:
    def test_page_loads(self, client):
        resp = client.get("/fuel-estimator")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Fuel Cost Estimator" in html

    def test_form_elements(self, client):
        resp = client.get("/fuel-estimator")
        html = resp.data.decode()
        assert 'id="fuel-distance"' in html
        assert 'id="fuel-mpg"' in html
        assert 'id="fuel-price"' in html
        assert 'id="fuel-load-id"' in html

    def test_reference_table(self, client):
        resp = client.get("/fuel-estimator")
        html = resp.data.decode()
        assert "Quick Reference" in html
        assert "6 MPG" in html
        assert "7 MPG" in html
        assert "8 MPG" in html

    def test_defaults_displayed(self, client):
        _add_trip_leg(miles=700)
        _add_fuel_purchase(gallons=100, amount=400)
        resp = client.get("/fuel-estimator")
        html = resp.data.decode()
        assert "7.0" in html
        assert "4.000" in html

    def test_nav_link(self, client):
        resp = client.get("/fuel-estimator")
        html = resp.data.decode()
        assert "fuel-estimator" in html

    def test_add_as_expense_button(self, client):
        resp = client.get("/fuel-estimator")
        html = resp.data.decode()
        assert "Add as Fuel Expense" in html

    def test_ifta_link(self, client):
        resp = client.get("/fuel-estimator")
        html = resp.data.decode()
        assert "IFTA Report" in html
