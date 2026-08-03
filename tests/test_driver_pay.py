"""Tests for driver pay tracking feature."""

from __future__ import annotations

import pytest

from dispatch.db import set_db_path
from dispatch.models import (
    PAY_TYPES, PAY_STATUSES, Driver, DriverPay,
)
from dispatch import services, store


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


def _make_driver(**kw) -> dict:
    defaults = {"name": "Test Driver"}
    defaults.update(kw)
    return services.create_driver(**defaults)


# ── Model Tests ─────────────────────────────────────────────────────


class TestDriverPayModel:
    def test_auto_id(self):
        p = DriverPay(driver_id="DRV-1")
        assert p.pay_id.startswith("PAY-")

    def test_driver_id_required(self):
        with pytest.raises(ValueError, match="Driver ID"):
            DriverPay()

    def test_valid_pay_types(self):
        for t in PAY_TYPES:
            p = DriverPay(driver_id="DRV-1", pay_type=t)
            assert p.pay_type == t

    def test_invalid_pay_type(self):
        with pytest.raises(ValueError, match="pay_type"):
            DriverPay(driver_id="DRV-1", pay_type="invalid")

    def test_valid_statuses(self):
        for s in PAY_STATUSES:
            p = DriverPay(driver_id="DRV-1", status=s)
            assert p.status == s

    def test_invalid_status(self):
        with pytest.raises(ValueError, match="status"):
            DriverPay(driver_id="DRV-1", status="invalid")

    def test_auto_calculate_per_mile(self):
        p = DriverPay(driver_id="DRV-1", pay_type="per_mile", rate=0.55, miles=500)
        assert p.amount == 275.0

    def test_auto_calculate_hourly(self):
        p = DriverPay(driver_id="DRV-1", pay_type="hourly", rate=25.0, hours=8)
        assert p.amount == 200.0

    def test_no_auto_calc_when_amount_set(self):
        p = DriverPay(driver_id="DRV-1", pay_type="per_mile", amount=100, rate=0.55, miles=500)
        assert p.amount == 100

    def test_to_dict(self):
        p = DriverPay(driver_id="DRV-1", amount=100)
        d = p.to_dict()
        assert d["driver_id"] == "DRV-1"
        assert d["amount"] == 100


# ── Store Tests ─────────────────────────────────────────────────────


class TestDriverPayStore:
    def test_create_and_get(self):
        pay = DriverPay(driver_id="DRV-1", amount=500, pay_type="per_load")
        result = store.create_driver_pay(pay)
        assert result["amount"] == 500
        fetched = store.get_driver_pay(result["pay_id"])
        assert fetched is not None
        assert fetched["amount"] == 500

    def test_get_nonexistent(self):
        assert store.get_driver_pay("PAY-NOPE") is None

    def test_list_by_driver(self):
        store.create_driver_pay(DriverPay(driver_id="DRV-A", amount=100))
        store.create_driver_pay(DriverPay(driver_id="DRV-B", amount=200))
        store.create_driver_pay(DriverPay(driver_id="DRV-A", amount=300))
        result = store.list_driver_pay(driver_id="DRV-A")
        assert len(result) == 2

    def test_list_by_status(self):
        store.create_driver_pay(DriverPay(driver_id="DRV-A", status="pending", amount=100))
        store.create_driver_pay(DriverPay(driver_id="DRV-A", status="paid", amount=200))
        result = store.list_driver_pay(status="paid")
        assert len(result) == 1
        assert result[0]["amount"] == 200

    def test_list_by_pay_period(self):
        store.create_driver_pay(DriverPay(driver_id="DRV-A", pay_period="2026-W31", amount=100))
        store.create_driver_pay(DriverPay(driver_id="DRV-A", pay_period="2026-W32", amount=200))
        result = store.list_driver_pay(pay_period="2026-W31")
        assert len(result) == 1

    def test_list_by_load(self):
        store.create_driver_pay(DriverPay(driver_id="DRV-A", load_id="LD-1", amount=100))
        store.create_driver_pay(DriverPay(driver_id="DRV-A", load_id="LD-2", amount=200))
        result = store.list_driver_pay(load_id="LD-1")
        assert len(result) == 1

    def test_update(self):
        pay = DriverPay(driver_id="DRV-1", amount=500)
        created = store.create_driver_pay(pay)
        updated = store.update_driver_pay(created["pay_id"], amount=600, status="approved")
        assert updated["amount"] == 600
        assert updated["status"] == "approved"

    def test_update_nonexistent(self):
        assert store.update_driver_pay("PAY-NOPE", amount=100) is None

    def test_update_ignores_disallowed_fields(self):
        pay = DriverPay(driver_id="DRV-1", amount=500)
        created = store.create_driver_pay(pay)
        updated = store.update_driver_pay(created["pay_id"], driver_id="DRV-OTHER")
        assert updated["driver_id"] == "DRV-1"

    def test_delete(self):
        pay = DriverPay(driver_id="DRV-1", amount=500)
        created = store.create_driver_pay(pay)
        assert store.delete_driver_pay(created["pay_id"]) is True
        assert store.get_driver_pay(created["pay_id"]) is None

    def test_delete_nonexistent(self):
        assert store.delete_driver_pay("PAY-NOPE") is False

    def test_summary(self):
        store.create_driver_pay(DriverPay(driver_id="DRV-1", amount=1000, pay_type="per_load", status="paid"))
        store.create_driver_pay(DriverPay(driver_id="DRV-1", amount=500, pay_type="bonus", status="pending"))
        store.create_driver_pay(DriverPay(driver_id="DRV-1", amount=200, pay_type="deduction", status="paid"))
        summary = store.get_driver_pay_summary("DRV-1")
        assert summary["gross_pay"] == 1500.0
        assert summary["deductions"] == 200.0
        assert summary["net_pay"] == 1300.0
        assert summary["paid_amount"] == 1000.0
        assert summary["pending_amount"] == 500.0
        assert summary["entry_count"] == 3

    def test_summary_by_period(self):
        store.create_driver_pay(DriverPay(driver_id="DRV-1", amount=100, pay_period="2026-W31"))
        store.create_driver_pay(DriverPay(driver_id="DRV-1", amount=200, pay_period="2026-W32"))
        summary = store.get_driver_pay_summary("DRV-1", pay_period="2026-W31")
        assert summary["entry_count"] == 1


# ── Service Tests ───────────────────────────────────────────────────


class TestDriverPayService:
    def test_add_pay_entry(self):
        drv = _make_driver()
        result = services.add_driver_pay(drv["driver_id"], "per_mile", 275.0)
        assert result["amount"] == 275.0
        assert result["pay_type"] == "per_mile"

    def test_add_pay_driver_not_found(self):
        with pytest.raises(ValueError, match="Driver not found"):
            services.add_driver_pay("DRV-NOPE", "per_mile", 100)

    def test_add_pay_invalid_type(self):
        drv = _make_driver()
        with pytest.raises(ValueError, match="Invalid pay type"):
            services.add_driver_pay(drv["driver_id"], "invalid", 100)

    def test_add_pay_load_not_found(self):
        drv = _make_driver()
        with pytest.raises(ValueError, match="Load not found"):
            services.add_driver_pay(drv["driver_id"], "per_load", 100, load_id="LD-NOPE")

    def test_add_pay_with_load(self):
        drv = _make_driver()
        load = services.create_load(customer="Test Co")
        result = services.add_driver_pay(
            drv["driver_id"], "per_load", 800.0,
            load_id=load["load_id"],
        )
        assert result["load_id"] == load["load_id"]

    def test_add_pay_with_rate_and_miles(self):
        drv = _make_driver()
        result = services.add_driver_pay(
            drv["driver_id"], "per_mile", rate=0.55, miles=1000
        )
        assert result["amount"] == 550.0

    def test_list_driver_pay(self):
        drv = _make_driver()
        services.add_driver_pay(drv["driver_id"], "per_load", 500)
        services.add_driver_pay(drv["driver_id"], "bonus", 100)
        entries = services.list_driver_pay(driver_id=drv["driver_id"])
        assert len(entries) == 2

    def test_get_pay_entry(self):
        drv = _make_driver()
        created = services.add_driver_pay(drv["driver_id"], "per_load", 500)
        fetched = services.get_driver_pay_entry(created["pay_id"])
        assert fetched is not None
        assert fetched["amount"] == 500

    def test_update_driver_pay(self):
        drv = _make_driver()
        created = services.add_driver_pay(drv["driver_id"], "per_load", 500)
        updated = services.update_driver_pay(created["pay_id"], amount=600)
        assert updated["amount"] == 600

    def test_update_invalid_type(self):
        drv = _make_driver()
        created = services.add_driver_pay(drv["driver_id"], "per_load", 500)
        with pytest.raises(ValueError, match="Invalid pay type"):
            services.update_driver_pay(created["pay_id"], pay_type="nope")

    def test_update_invalid_status(self):
        drv = _make_driver()
        created = services.add_driver_pay(drv["driver_id"], "per_load", 500)
        with pytest.raises(ValueError, match="Invalid status"):
            services.update_driver_pay(created["pay_id"], status="nope")

    def test_delete_driver_pay(self):
        drv = _make_driver()
        created = services.add_driver_pay(drv["driver_id"], "per_load", 500)
        assert services.delete_driver_pay(created["pay_id"]) is True
        assert services.get_driver_pay_entry(created["pay_id"]) is None

    def test_get_summary(self):
        drv = _make_driver()
        services.add_driver_pay(drv["driver_id"], "per_load", 1000)
        services.add_driver_pay(drv["driver_id"], "deduction", 150)
        summary = services.get_driver_pay_summary(drv["driver_id"])
        assert summary["gross_pay"] == 1000.0
        assert summary["deductions"] == 150.0
        assert summary["net_pay"] == 850.0

    def test_approve_driver_pay(self):
        drv = _make_driver()
        p1 = services.add_driver_pay(drv["driver_id"], "per_load", 500)
        p2 = services.add_driver_pay(drv["driver_id"], "per_load", 300)
        count = services.approve_driver_pay([p1["pay_id"], p2["pay_id"]])
        assert count == 2
        assert services.get_driver_pay_entry(p1["pay_id"])["status"] == "approved"
        assert services.get_driver_pay_entry(p2["pay_id"])["status"] == "approved"

    def test_mark_paid(self):
        drv = _make_driver()
        p1 = services.add_driver_pay(drv["driver_id"], "per_load", 500)
        count = services.mark_driver_pay_paid([p1["pay_id"]], paid_date="2026-08-01")
        assert count == 1
        entry = services.get_driver_pay_entry(p1["pay_id"])
        assert entry["status"] == "paid"
        assert entry["paid_date"] == "2026-08-01"

    def test_mark_paid_auto_date(self):
        drv = _make_driver()
        p1 = services.add_driver_pay(drv["driver_id"], "per_load", 500)
        services.mark_driver_pay_paid([p1["pay_id"]])
        entry = services.get_driver_pay_entry(p1["pay_id"])
        assert entry["paid_date"] != ""

    def test_percentage_pay_with_rate_confirmation(self):
        from dispatch.models import RateConfirmation
        drv = _make_driver()
        load = services.create_load(customer="Test Co")
        store.create_rate_confirmation(RateConfirmation(
            load_id=load["load_id"],
            rate_type="flat",
            rate_amount=2000.0,
        ))
        result = services.add_driver_pay(
            drv["driver_id"], "percentage",
            load_id=load["load_id"],
            percentage=30,
        )
        assert result["amount"] == 600.0


# ── API Tests ───────────────────────────────────────────────────────


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestDriverPayAPI:
    def test_create_pay(self, client):
        drv = _make_driver()
        r = client.post("/api/dispatch/driver-pay", json={
            "driver_id": drv["driver_id"],
            "pay_type": "per_load",
            "amount": 500,
        })
        assert r.status_code == 201
        assert r.get_json()["amount"] == 500

    def test_create_pay_missing_driver(self, client):
        r = client.post("/api/dispatch/driver-pay", json={
            "pay_type": "per_load", "amount": 500,
        })
        assert r.status_code == 400

    def test_create_pay_bad_driver(self, client):
        r = client.post("/api/dispatch/driver-pay", json={
            "driver_id": "DRV-NOPE",
            "pay_type": "per_load", "amount": 500,
        })
        assert r.status_code == 400

    def test_list_pay(self, client):
        drv = _make_driver()
        client.post("/api/dispatch/driver-pay", json={
            "driver_id": drv["driver_id"], "pay_type": "bonus", "amount": 100,
        })
        r = client.get(f"/api/dispatch/driver-pay?driver_id={drv['driver_id']}")
        assert r.status_code == 200
        assert len(r.get_json()) == 1

    def test_get_pay(self, client):
        drv = _make_driver()
        created = client.post("/api/dispatch/driver-pay", json={
            "driver_id": drv["driver_id"], "pay_type": "per_load", "amount": 500,
        }).get_json()
        r = client.get(f"/api/dispatch/driver-pay/{created['pay_id']}")
        assert r.status_code == 200
        assert r.get_json()["amount"] == 500

    def test_get_pay_not_found(self, client):
        r = client.get("/api/dispatch/driver-pay/PAY-NOPE")
        assert r.status_code == 404

    def test_update_pay(self, client):
        drv = _make_driver()
        created = client.post("/api/dispatch/driver-pay", json={
            "driver_id": drv["driver_id"], "pay_type": "per_load", "amount": 500,
        }).get_json()
        r = client.patch(f"/api/dispatch/driver-pay/{created['pay_id']}", json={
            "amount": 600,
        })
        assert r.status_code == 200
        assert r.get_json()["amount"] == 600

    def test_delete_pay(self, client):
        drv = _make_driver()
        created = client.post("/api/dispatch/driver-pay", json={
            "driver_id": drv["driver_id"], "pay_type": "per_load", "amount": 500,
        }).get_json()
        r = client.delete(f"/api/dispatch/driver-pay/{created['pay_id']}")
        assert r.status_code == 200

    def test_summary(self, client):
        drv = _make_driver()
        client.post("/api/dispatch/driver-pay", json={
            "driver_id": drv["driver_id"], "pay_type": "per_load", "amount": 1000,
        })
        r = client.get(f"/api/dispatch/driver-pay/summary/{drv['driver_id']}")
        assert r.status_code == 200
        data = r.get_json()
        assert data["gross_pay"] == 1000.0

    def test_approve(self, client):
        drv = _make_driver()
        p1 = client.post("/api/dispatch/driver-pay", json={
            "driver_id": drv["driver_id"], "pay_type": "per_load", "amount": 500,
        }).get_json()
        r = client.post("/api/dispatch/driver-pay/approve", json={
            "pay_ids": [p1["pay_id"]],
        })
        assert r.status_code == 200
        assert r.get_json()["approved"] == 1

    def test_approve_empty(self, client):
        r = client.post("/api/dispatch/driver-pay/approve", json={"pay_ids": []})
        assert r.status_code == 400

    def test_mark_paid(self, client):
        drv = _make_driver()
        p1 = client.post("/api/dispatch/driver-pay", json={
            "driver_id": drv["driver_id"], "pay_type": "per_load", "amount": 500,
        }).get_json()
        r = client.post("/api/dispatch/driver-pay/mark-paid", json={
            "pay_ids": [p1["pay_id"]], "paid_date": "2026-08-01",
        })
        assert r.status_code == 200
        assert r.get_json()["paid"] == 1

    def test_mark_paid_empty(self, client):
        r = client.post("/api/dispatch/driver-pay/mark-paid", json={"pay_ids": []})
        assert r.status_code == 400


# ── Template Tests ──────────────────────────────────────────────────


class TestDriverPayTemplate:
    def test_page_loads(self, client):
        r = client.get("/driver-pay")
        assert r.status_code == 200
        html = r.data.decode()
        assert "Driver Pay" in html

    def test_page_has_filter_form(self, client):
        r = client.get("/driver-pay")
        html = r.data.decode()
        assert "pay_period" in html
        assert "Filter" in html

    def test_page_has_add_form(self, client):
        r = client.get("/driver-pay")
        html = r.data.decode()
        assert "Add Pay Entry" in html

    def test_page_has_bulk_actions(self, client):
        drv = _make_driver()
        services.add_driver_pay(drv["driver_id"], "per_load", 500)
        r = client.get("/driver-pay")
        html = r.data.decode()
        assert "Approve Selected" in html
        assert "Mark Paid" in html

    def test_page_shows_entries(self, client):
        drv = _make_driver()
        services.add_driver_pay(drv["driver_id"], "per_load", 500, description="Trip pay")
        r = client.get("/driver-pay")
        html = r.data.decode()
        assert "Trip pay" in html
        assert "500.00" in html

    def test_page_filter_by_driver(self, client):
        drv = _make_driver()
        services.add_driver_pay(drv["driver_id"], "per_load", 500)
        r = client.get(f"/driver-pay?driver_id={drv['driver_id']}")
        html = r.data.decode()
        assert "Gross Pay" in html

    def test_nav_link(self, client):
        r = client.get("/driver-pay")
        html = r.data.decode()
        assert "Driver Pay" in html

    def test_driver_detail_shows_pay(self, client):
        drv = _make_driver()
        services.add_driver_pay(drv["driver_id"], "bonus", 250, description="Safety bonus")
        r = client.get(f"/fleet/driver/{drv['driver_id']}")
        html = r.data.decode()
        assert "Safety bonus" in html
        assert "250.00" in html

    def test_driver_detail_pay_summary(self, client):
        drv = _make_driver()
        services.add_driver_pay(drv["driver_id"], "per_load", 1000)
        r = client.get(f"/fleet/driver/{drv['driver_id']}")
        html = r.data.decode()
        assert "Gross:" in html
        assert "1000.00" in html
