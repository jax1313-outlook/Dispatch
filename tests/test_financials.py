"""Tests for rate confirmation and financial tracking."""

from __future__ import annotations

import pytest

from dispatch import services as dispatch_svc
from dispatch import store
from dispatch.db import set_db_path
from dispatch.models import (
    EXPENSE_CATEGORIES,
    RATE_TYPES,
    Expense,
    RateConfirmation,
)


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture()
def load():
    return dispatch_svc.create_load(
        customer="Test Broker",
        broker_shipper="Test Broker",
        pickup_location="Jacksonville, FL",
        delivery_location="Savannah, GA",
    )


# ── RateConfirmation Model ──────────────────────────────────────────


class TestRateConfirmationModel:
    def test_defaults(self):
        rc = RateConfirmation(load_id="L1", rate_amount=500.0)
        assert rc.confirmation_id.startswith("RC-")
        assert rc.rate_type == "flat"
        assert rc.confirmed_at

    def test_flat_revenue(self):
        rc = RateConfirmation(rate_amount=625.0, rate_type="flat")
        assert rc.revenue == 625.0

    def test_per_mile_revenue(self):
        rc = RateConfirmation(rate_amount=4.50, rate_type="per_mile", distance_miles=140)
        assert rc.revenue == 630.0

    def test_per_mile_no_distance(self):
        rc = RateConfirmation(rate_amount=4.50, rate_type="per_mile", distance_miles=0)
        assert rc.revenue == 4.50

    def test_to_dict_includes_revenue(self):
        rc = RateConfirmation(rate_amount=500.0)
        d = rc.to_dict()
        assert "revenue" in d
        assert d["revenue"] == 500.0

    def test_invalid_rate_type(self):
        with pytest.raises(ValueError, match="rate_type"):
            RateConfirmation(rate_amount=100, rate_type="hourly")

    def test_valid_rate_types(self):
        for rt in RATE_TYPES:
            rc = RateConfirmation(rate_amount=100, rate_type=rt)
            assert rc.rate_type == rt


# ── Expense Model ───────────────────────────────────────────────────


class TestExpenseModel:
    def test_defaults(self):
        exp = Expense(load_id="L1", amount=50.0)
        assert exp.expense_id.startswith("EXP-")
        assert exp.category == "other"
        assert exp.incurred_at

    def test_invalid_category(self):
        with pytest.raises(ValueError, match="category"):
            Expense(category="unknown")

    def test_all_categories_valid(self):
        for cat in EXPENSE_CATEGORIES:
            exp = Expense(category=cat, amount=10)
            assert exp.category == cat

    def test_to_dict(self):
        exp = Expense(load_id="L1", category="fuel", amount=80.5)
        d = exp.to_dict()
        assert d["category"] == "fuel"
        assert d["amount"] == 80.5


# ── Store CRUD ──────────────────────────────────────────────────────


class TestRateConfirmationStore:
    def test_create_and_get(self, load):
        rc = RateConfirmation(load_id=load["load_id"], rate_amount=625.0)
        result = store.create_rate_confirmation(rc)
        assert result["rate_amount"] == 625.0

        fetched = store.get_rate_confirmation(load["load_id"])
        assert fetched is not None
        assert fetched["rate_amount"] == 625.0

    def test_get_nonexistent(self, load):
        assert store.get_rate_confirmation(load["load_id"]) is None

    def test_update(self, load):
        rc = RateConfirmation(load_id=load["load_id"], rate_amount=500.0)
        store.create_rate_confirmation(rc)

        updated = store.update_rate_confirmation(load["load_id"], rate_amount=600.0)
        assert updated["rate_amount"] == 600.0

    def test_update_nonexistent(self):
        assert store.update_rate_confirmation("NONE", rate_amount=100) is None

    def test_delete(self, load):
        rc = RateConfirmation(load_id=load["load_id"], rate_amount=500.0)
        store.create_rate_confirmation(rc)
        assert store.delete_rate_confirmation(load["load_id"])
        assert store.get_rate_confirmation(load["load_id"]) is None

    def test_delete_nonexistent(self):
        assert not store.delete_rate_confirmation("NONE")


class TestExpenseStore:
    def test_create_and_get(self, load):
        exp = Expense(load_id=load["load_id"], category="fuel", amount=80.0)
        result = store.create_expense(exp)
        assert result["amount"] == 80.0

        fetched = store.get_expense(result["expense_id"])
        assert fetched is not None
        assert fetched["category"] == "fuel"

    def test_list_expenses(self, load):
        for cat in ["fuel", "tolls", "lumper"]:
            exp = Expense(load_id=load["load_id"], category=cat, amount=25.0)
            store.create_expense(exp)

        items = store.list_expenses(load["load_id"])
        assert len(items) == 3

    def test_update(self, load):
        exp = Expense(load_id=load["load_id"], category="fuel", amount=50.0)
        result = store.create_expense(exp)

        updated = store.update_expense(result["expense_id"], amount=75.0)
        assert updated["amount"] == 75.0

    def test_update_nonexistent(self):
        assert store.update_expense("NONE", amount=100) is None

    def test_delete(self, load):
        exp = Expense(load_id=load["load_id"], amount=30.0)
        result = store.create_expense(exp)
        assert store.delete_expense(result["expense_id"])
        assert store.get_expense(result["expense_id"]) is None

    def test_delete_nonexistent(self):
        assert not store.delete_expense("NONE")

    def test_empty_list(self, load):
        assert store.list_expenses(load["load_id"]) == []


# ── Service Functions ───────────────────────────────────────────────


class TestConfirmRateService:
    def test_confirm_new(self, load):
        rc = dispatch_svc.confirm_rate(
            load["load_id"], rate_amount=625.0, rate_type="flat"
        )
        assert rc["rate_amount"] == 625.0
        assert rc["revenue"] == 625.0

    def test_confirm_per_mile(self, load):
        rc = dispatch_svc.confirm_rate(
            load["load_id"], rate_amount=4.50, rate_type="per_mile",
            distance_miles=140,
        )
        assert rc["revenue"] == 630.0

    def test_confirm_updates_existing(self, load):
        dispatch_svc.confirm_rate(load["load_id"], rate_amount=500.0)
        updated = dispatch_svc.confirm_rate(load["load_id"], rate_amount=600.0)
        assert updated["rate_amount"] == 600.0

    def test_confirm_nonexistent_load(self):
        with pytest.raises(ValueError, match="not found"):
            dispatch_svc.confirm_rate("BOGUS", rate_amount=100)

    def test_get_rate(self, load):
        dispatch_svc.confirm_rate(load["load_id"], rate_amount=500.0)
        rc = dispatch_svc.get_rate_confirmation(load["load_id"])
        assert rc is not None
        assert rc["rate_amount"] == 500.0


class TestExpenseService:
    def test_add(self, load):
        exp = dispatch_svc.add_expense(
            load["load_id"], category="fuel", amount=80.0, description="Fuel stop I-95"
        )
        assert exp["category"] == "fuel"
        assert exp["amount"] == 80.0

    def test_add_nonexistent_load(self):
        with pytest.raises(ValueError, match="not found"):
            dispatch_svc.add_expense("BOGUS", amount=50)

    def test_list(self, load):
        dispatch_svc.add_expense(load["load_id"], category="fuel", amount=80)
        dispatch_svc.add_expense(load["load_id"], category="tolls", amount=12)
        items = dispatch_svc.list_expenses(load["load_id"])
        assert len(items) == 2

    def test_update(self, load):
        exp = dispatch_svc.add_expense(load["load_id"], amount=50)
        updated = dispatch_svc.update_expense(exp["expense_id"], amount=75)
        assert updated["amount"] == 75.0

    def test_delete(self, load):
        exp = dispatch_svc.add_expense(load["load_id"], amount=30)
        assert dispatch_svc.delete_expense(exp["expense_id"])
        assert dispatch_svc.list_expenses(load["load_id"]) == []


class TestFinancialsSummary:
    def test_no_rate_no_expenses(self, load):
        fin = dispatch_svc.get_financials(load["load_id"])
        assert fin is not None
        assert fin["rate_confirmation"] is None
        assert fin["expenses"] == []
        assert fin["summary"]["revenue"] == 0.0
        assert fin["summary"]["profit"] == 0.0

    def test_rate_only(self, load):
        dispatch_svc.confirm_rate(load["load_id"], rate_amount=625.0)
        fin = dispatch_svc.get_financials(load["load_id"])
        assert fin["summary"]["revenue"] == 625.0
        assert fin["summary"]["profit"] == 625.0
        assert fin["summary"]["margin_pct"] == 100.0

    def test_rate_and_expenses(self, load):
        dispatch_svc.confirm_rate(load["load_id"], rate_amount=625.0)
        dispatch_svc.add_expense(load["load_id"], category="fuel", amount=150.0)
        dispatch_svc.add_expense(load["load_id"], category="tolls", amount=25.0)

        fin = dispatch_svc.get_financials(load["load_id"])
        assert fin["summary"]["revenue"] == 625.0
        assert fin["summary"]["total_expenses"] == 175.0
        assert fin["summary"]["profit"] == 450.0
        assert fin["summary"]["margin_pct"] == 72.0

    def test_loss_scenario(self, load):
        dispatch_svc.confirm_rate(load["load_id"], rate_amount=200.0)
        dispatch_svc.add_expense(load["load_id"], category="fuel", amount=250.0)

        fin = dispatch_svc.get_financials(load["load_id"])
        assert fin["summary"]["profit"] == -50.0
        assert fin["summary"]["margin_pct"] < 0

    def test_nonexistent_load(self):
        assert dispatch_svc.get_financials("BOGUS") is None

    def test_expenses_without_rate(self, load):
        dispatch_svc.add_expense(load["load_id"], category="fuel", amount=100)
        fin = dispatch_svc.get_financials(load["load_id"])
        assert fin["summary"]["revenue"] == 0.0
        assert fin["summary"]["total_expenses"] == 100.0
        assert fin["summary"]["profit"] == -100.0
        assert fin["summary"]["margin_pct"] == 0.0


class TestLoadBundleFinancials:
    def test_bundle_includes_financials(self, load):
        dispatch_svc.confirm_rate(load["load_id"], rate_amount=500.0)
        dispatch_svc.add_expense(load["load_id"], category="fuel", amount=80.0)

        bundle = dispatch_svc.get_load_bundle(load["load_id"])
        assert "financials" in bundle
        assert bundle["financials"]["summary"]["revenue"] == 500.0
        assert bundle["financials"]["summary"]["total_expenses"] == 80.0

    def test_bundle_financials_empty_by_default(self, load):
        bundle = dispatch_svc.get_load_bundle(load["load_id"])
        assert bundle["financials"]["rate_confirmation"] is None
        assert bundle["financials"]["expenses"] == []


# ── API Endpoints ───────────────────────────────────────────────────


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    set_db_path(tmp_path / "api_test.db")

    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

    set_db_path(None)


@pytest.fixture()
def api_load(client):
    resp = client.post("/api/dispatch/loads", json={"customer": "API Test Broker"})
    return resp.get_json()["load"]


class TestRateAPI:
    def test_confirm_rate(self, client, api_load):
        resp = client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/rate",
            json={"rate_amount": 625, "rate_type": "flat"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["rate_confirmation"]["rate_amount"] == 625.0

    def test_get_rate(self, client, api_load):
        client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/rate",
            json={"rate_amount": 500},
        )
        resp = client.get(f"/api/dispatch/loads/{api_load['load_id']}/rate")
        assert resp.status_code == 200
        assert resp.get_json()["rate_confirmation"]["rate_amount"] == 500.0

    def test_get_rate_404(self, client, api_load):
        resp = client.get(f"/api/dispatch/loads/{api_load['load_id']}/rate")
        assert resp.status_code == 404

    def test_rate_missing_amount(self, client, api_load):
        resp = client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/rate",
            json={"rate_type": "flat"},
        )
        assert resp.status_code == 400

    def test_rate_invalid_type(self, client, api_load):
        resp = client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/rate",
            json={"rate_amount": 500, "rate_type": "hourly"},
        )
        assert resp.status_code == 400

    def test_rate_invalid_amount(self, client, api_load):
        resp = client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/rate",
            json={"rate_amount": "abc"},
        )
        assert resp.status_code == 400

    def test_rate_nonexistent_load(self, client):
        resp = client.post(
            "/api/dispatch/loads/BOGUS/rate",
            json={"rate_amount": 500},
        )
        assert resp.status_code == 404

    def test_per_mile_rate(self, client, api_load):
        resp = client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/rate",
            json={"rate_amount": 4.50, "rate_type": "per_mile", "distance_miles": 140},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["rate_confirmation"]["revenue"] == 630.0


class TestExpenseAPI:
    def test_add_expense(self, client, api_load):
        resp = client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/expenses",
            json={"category": "fuel", "amount": 80, "description": "Fuel I-95"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["expense"]["category"] == "fuel"

    def test_list_expenses(self, client, api_load):
        for amt in [80, 12, 25]:
            client.post(
                f"/api/dispatch/loads/{api_load['load_id']}/expenses",
                json={"amount": amt},
            )
        resp = client.get(f"/api/dispatch/loads/{api_load['load_id']}/expenses")
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 3

    def test_expense_missing_amount(self, client, api_load):
        resp = client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/expenses",
            json={"category": "fuel"},
        )
        assert resp.status_code == 400

    def test_expense_invalid_category(self, client, api_load):
        resp = client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/expenses",
            json={"amount": 50, "category": "unknown"},
        )
        assert resp.status_code == 400

    def test_expense_invalid_amount(self, client, api_load):
        resp = client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/expenses",
            json={"amount": "abc", "category": "fuel"},
        )
        assert resp.status_code == 400

    def test_update_expense(self, client, api_load):
        resp = client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/expenses",
            json={"amount": 50},
        )
        eid = resp.get_json()["expense"]["expense_id"]
        resp = client.patch(
            f"/api/dispatch/expenses/{eid}",
            json={"amount": 75},
        )
        assert resp.status_code == 200
        assert resp.get_json()["expense"]["amount"] == 75.0

    def test_update_expense_invalid_category(self, client, api_load):
        resp = client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/expenses",
            json={"amount": 50},
        )
        eid = resp.get_json()["expense"]["expense_id"]
        resp = client.patch(
            f"/api/dispatch/expenses/{eid}",
            json={"category": "invalid"},
        )
        assert resp.status_code == 400

    def test_update_expense_404(self, client):
        resp = client.patch("/api/dispatch/expenses/BOGUS", json={"amount": 100})
        assert resp.status_code == 404

    def test_delete_expense(self, client, api_load):
        resp = client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/expenses",
            json={"amount": 30},
        )
        eid = resp.get_json()["expense"]["expense_id"]
        resp = client.delete(f"/api/dispatch/expenses/{eid}")
        assert resp.status_code == 200

    def test_delete_expense_404(self, client):
        resp = client.delete("/api/dispatch/expenses/BOGUS")
        assert resp.status_code == 404

    def test_expense_nonexistent_load(self, client):
        resp = client.post(
            "/api/dispatch/loads/BOGUS/expenses",
            json={"amount": 50},
        )
        assert resp.status_code == 404


class TestFinancialsAPI:
    def test_get_financials(self, client, api_load):
        client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/rate",
            json={"rate_amount": 625},
        )
        client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/expenses",
            json={"category": "fuel", "amount": 150},
        )
        resp = client.get(f"/api/dispatch/loads/{api_load['load_id']}/financials")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["summary"]["revenue"] == 625.0
        assert data["summary"]["total_expenses"] == 150.0
        assert data["summary"]["profit"] == 475.0

    def test_financials_nonexistent_load(self, client):
        resp = client.get("/api/dispatch/loads/BOGUS/financials")
        assert resp.status_code == 404

    def test_financials_in_bundle(self, client, api_load):
        client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/rate",
            json={"rate_amount": 500},
        )
        resp = client.get(f"/api/dispatch/loads/{api_load['load_id']}/bundle")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "financials" in data
        assert data["financials"]["summary"]["revenue"] == 500.0


class TestFinancialsInArchive:
    def test_archive_with_financials(self, load):
        lid = load["load_id"]
        dispatch_svc.confirm_rate(lid, rate_amount=625.0)
        dispatch_svc.add_expense(lid, category="fuel", amount=150)

        dispatch_svc.add_milestone(lid, "dispatched")
        dispatch_svc.add_milestone(lid, "delivered", location="Savannah, GA")

        ret = dispatch_svc.archive_load(lid)
        assert ret["final_status"] == "delivered"
