"""Tests for load profitability ranking feature."""

from __future__ import annotations

import pytest

from dispatch.db import set_db_path
from dispatch import services, store
from dispatch.models import RateConfirmation


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


def _create_load_with_financials(customer, rate=0, expenses=None, distance=0, rate_type="flat"):
    load = services.create_load(customer=customer)
    if rate > 0:
        rc = RateConfirmation(
            load_id=load["load_id"],
            rate_amount=rate,
            rate_type=rate_type,
            distance_miles=distance,
        )
        store.create_rate_confirmation(rc)
    for exp in (expenses or []):
        services.add_expense(
            load_id=load["load_id"],
            category=exp.get("category", "fuel"),
            amount=exp["amount"],
        )
    return load


# ── Service Tests ────────────────────────────────────────────────────


class TestProfitabilityService:
    def test_basic_profitability(self):
        _create_load_with_financials("Cust A", rate=1000, expenses=[{"amount": 300}])
        result = services.get_load_profitability()
        assert len(result["loads"]) == 1
        load = result["loads"][0]
        assert load["revenue"] == 1000.0
        assert load["total_expenses"] == 300.0
        assert load["profit"] == 700.0
        assert load["margin_pct"] == 70.0

    def test_ranking_order_by_profit_desc(self):
        _create_load_with_financials("Low", rate=500, expenses=[{"amount": 400}])
        _create_load_with_financials("High", rate=2000, expenses=[{"amount": 200}])
        _create_load_with_financials("Mid", rate=1000, expenses=[{"amount": 300}])
        result = services.get_load_profitability(sort_by="profit", sort_order="desc")
        profits = [l["profit"] for l in result["loads"]]
        assert profits == sorted(profits, reverse=True)
        assert result["loads"][0]["rank"] == 1
        assert result["loads"][0]["customer"] == "High"

    def test_ranking_order_by_margin(self):
        _create_load_with_financials("LowMargin", rate=1000, expenses=[{"amount": 800}])
        _create_load_with_financials("HighMargin", rate=500, expenses=[{"amount": 50}])
        result = services.get_load_profitability(sort_by="margin_pct", sort_order="desc")
        assert result["loads"][0]["customer"] == "HighMargin"

    def test_ranking_order_asc(self):
        _create_load_with_financials("Profitable", rate=1000, expenses=[{"amount": 100}])
        _create_load_with_financials("Losing", rate=500, expenses=[{"amount": 800}])
        result = services.get_load_profitability(sort_by="profit", sort_order="asc")
        assert result["loads"][0]["customer"] == "Losing"

    def test_revenue_per_mile(self):
        _create_load_with_financials("PerMile", rate=2.5, distance=400, rate_type="per_mile")
        result = services.get_load_profitability()
        load = result["loads"][0]
        assert load["revenue"] == 1000.0
        assert load["revenue_per_mile"] == 2.5

    def test_no_rate_confirmation(self):
        _create_load_with_financials("NoRate", rate=0, expenses=[{"amount": 50}])
        result = services.get_load_profitability()
        load = result["loads"][0]
        assert load["revenue"] == 0.0
        assert load["profit"] == -50.0
        assert load["margin_pct"] == 0.0

    def test_no_expenses(self):
        _create_load_with_financials("NoExp", rate=1000)
        result = services.get_load_profitability()
        load = result["loads"][0]
        assert load["total_expenses"] == 0.0
        assert load["profit"] == 1000.0
        assert load["margin_pct"] == 100.0

    def test_multiple_expenses(self):
        _create_load_with_financials("MultiExp", rate=1000, expenses=[
            {"amount": 100, "category": "fuel"},
            {"amount": 50, "category": "tolls"},
            {"amount": 25, "category": "parking"},
        ])
        result = services.get_load_profitability()
        assert result["loads"][0]["total_expenses"] == 175.0

    def test_summary_stats(self):
        _create_load_with_financials("Profit1", rate=1000, expenses=[{"amount": 200}])
        _create_load_with_financials("Profit2", rate=800, expenses=[{"amount": 100}])
        _create_load_with_financials("Loss", rate=300, expenses=[{"amount": 500}])
        result = services.get_load_profitability()
        s = result["summary"]
        assert s["total_loads"] == 3
        assert s["total_revenue"] == 2100.0
        assert s["total_expenses"] == 800.0
        assert s["total_profit"] == 1300.0
        assert s["profitable_count"] == 2
        assert s["unprofitable_count"] == 1

    def test_empty_loads(self):
        result = services.get_load_profitability()
        assert result["loads"] == []
        assert result["summary"]["total_loads"] == 0
        assert result["summary"]["avg_margin_pct"] == 0.0

    def test_filter_by_status(self):
        load = _create_load_with_financials("StatusTest", rate=1000)
        _create_load_with_financials("Other", rate=500)
        services.update_load(load["load_id"], status="dispatched")
        result = services.get_load_profitability(status="dispatched")
        assert len(result["loads"]) == 1
        assert result["loads"][0]["customer"] == "StatusTest"

    def test_invalid_sort_by(self):
        with pytest.raises(ValueError, match="Invalid sort_by"):
            services.get_load_profitability(sort_by="invalid")

    def test_invalid_sort_order(self):
        with pytest.raises(ValueError, match="Invalid sort_order"):
            services.get_load_profitability(sort_order="sideways")

    def test_sort_by_revenue_per_mile(self):
        _create_load_with_financials("Low RPM", rate=1.5, distance=100, rate_type="per_mile")
        _create_load_with_financials("High RPM", rate=3.0, distance=200, rate_type="per_mile")
        result = services.get_load_profitability(sort_by="revenue_per_mile", sort_order="desc")
        assert result["loads"][0]["customer"] == "High RPM"

    def test_sort_by_expenses(self):
        _create_load_with_financials("LowExp", rate=500, expenses=[{"amount": 50}])
        _create_load_with_financials("HighExp", rate=500, expenses=[{"amount": 400}])
        result = services.get_load_profitability(sort_by="total_expenses", sort_order="desc")
        assert result["loads"][0]["customer"] == "HighExp"


# ── API Tests ────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestProfitabilityAPI:
    def test_endpoint_returns_data(self, client):
        _create_load_with_financials("API Test", rate=1000, expenses=[{"amount": 300}])
        r = client.get("/api/dispatch/profitability")
        assert r.status_code == 200
        data = r.get_json()
        assert "loads" in data
        assert "summary" in data
        assert len(data["loads"]) == 1

    def test_sort_params(self, client):
        _create_load_with_financials("A", rate=500)
        _create_load_with_financials("B", rate=1000)
        r = client.get("/api/dispatch/profitability?sort_by=revenue&sort_order=desc")
        data = r.get_json()
        assert data["loads"][0]["customer"] == "B"

    def test_invalid_sort(self, client):
        r = client.get("/api/dispatch/profitability?sort_by=bogus")
        assert r.status_code == 400

    def test_status_filter(self, client):
        load = _create_load_with_financials("Filtered", rate=500)
        services.update_load(load["load_id"], status="dispatched")
        r = client.get("/api/dispatch/profitability?status=dispatched")
        data = r.get_json()
        assert len(data["loads"]) == 1


# ── Template Tests ───────────────────────────────────────────────────


class TestProfitabilityTemplate:
    def test_page_loads(self, client):
        r = client.get("/profitability")
        assert r.status_code == 200
        html = r.data.decode()
        assert "Load Profitability Ranking" in html

    def test_page_shows_loads(self, client):
        _create_load_with_financials("Visible Load", rate=1000, expenses=[{"amount": 200}])
        r = client.get("/profitability")
        html = r.data.decode()
        assert "Visible Load" in html
        assert "$800" in html or "800" in html

    def test_page_shows_summary(self, client):
        _create_load_with_financials("Summary Test", rate=500)
        r = client.get("/profitability")
        html = r.data.decode()
        assert "Total Revenue" in html
        assert "Total Profit" in html
        assert "Avg Margin" in html

    def test_page_shows_rank_badges(self, client):
        _create_load_with_financials("R1", rate=1000)
        _create_load_with_financials("R2", rate=500)
        r = client.get("/profitability")
        html = r.data.decode()
        assert "rank-badge" in html

    def test_page_filter_form(self, client):
        r = client.get("/profitability")
        html = r.data.decode()
        assert "sort_by" in html
        assert "sort_order" in html
        assert "date_from" in html

    def test_empty_state(self, client):
        r = client.get("/profitability")
        html = r.data.decode()
        assert "No loads found" in html

    def test_nav_link(self, client):
        r = client.get("/profitability")
        html = r.data.decode()
        assert "Profitability" in html
