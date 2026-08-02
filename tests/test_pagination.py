"""Tests for pagination across all list endpoints."""

from __future__ import annotations

import pytest

from dispatch import services
from dispatch.db import set_db_path
from dispatch.store import DEFAULT_PER_PAGE, MAX_PER_PAGE


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _bulk_loads(n):
    for i in range(n):
        services.create_load(customer=f"Customer {i:03d}")


def _bulk_drivers(n):
    for i in range(n):
        services.create_driver(name=f"Driver {i:03d}")


def _bulk_equipment(n):
    for i in range(n):
        services.create_equipment(unit_number=f"UNIT-{i:03d}", equipment_type="dry_van")


def _bulk_settlements(n):
    for i in range(n):
        load = services.create_load(customer=f"Stl Customer {i:03d}")
        services.confirm_rate(load["load_id"], rate_amount=1000 + i)
        services.create_settlement(load["load_id"])


def _bulk_exceptions(n):
    load = services.create_load(customer="Exception Bulk Co")
    for i in range(n):
        services.open_exception(
            load_id=load["load_id"],
            exception_type="delay",
            severity="medium",
            description=f"Exception {i:03d}",
        )


# ── Store-level pagination ───────────────────────────────────────────


class TestStorePagination:
    def test_no_page_param_returns_list(self):
        _bulk_loads(5)
        result = services.list_loads()
        assert isinstance(result, list)
        assert len(result) == 5

    def test_page_param_returns_dict(self):
        _bulk_loads(5)
        result = services.list_loads(page=1, per_page=3)
        assert isinstance(result, dict)
        assert "items" in result
        assert result["total"] == 5
        assert result["page"] == 1
        assert result["per_page"] == 3
        assert result["pages"] == 2
        assert len(result["items"]) == 3

    def test_second_page(self):
        _bulk_loads(5)
        result = services.list_loads(page=2, per_page=3)
        assert len(result["items"]) == 2
        assert result["page"] == 2

    def test_empty_page_beyond_data(self):
        _bulk_loads(3)
        result = services.list_loads(page=5, per_page=3)
        assert result["items"] == []
        assert result["total"] == 3
        assert result["pages"] == 1

    def test_default_per_page(self):
        _bulk_loads(3)
        result = services.list_loads(page=1)
        assert result["per_page"] == DEFAULT_PER_PAGE

    def test_max_per_page_capped(self):
        _bulk_loads(3)
        result = services.list_loads(page=1, per_page=999)
        assert result["per_page"] == MAX_PER_PAGE

    def test_page_zero_treated_as_one(self):
        _bulk_loads(3)
        result = services.list_loads(page=0, per_page=2)
        assert result["page"] == 1
        assert len(result["items"]) == 2

    def test_negative_page_treated_as_one(self):
        _bulk_loads(3)
        result = services.list_loads(page=-5, per_page=2)
        assert result["page"] == 1

    def test_pagination_with_filters(self):
        for i in range(5):
            services.create_load(customer="Alpha")
        for i in range(3):
            services.create_load(customer="Beta")
        result = services.list_loads(customer="Alpha", page=1, per_page=2)
        assert result["total"] == 5
        assert len(result["items"]) == 2
        assert result["pages"] == 3


# ── API-level pagination ─────────────────────────────────────────────


class TestLoadsPagination:
    def test_no_pagination_params(self, client):
        _bulk_loads(3)
        resp = client.get("/api/dispatch/loads")
        data = resp.get_json()
        assert data["count"] == 3
        assert "total" not in data
        assert "page" not in data

    def test_with_page_param(self, client):
        _bulk_loads(5)
        resp = client.get("/api/dispatch/loads?page=1&per_page=2")
        data = resp.get_json()
        assert data["count"] == 2
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["per_page"] == 2
        assert data["pages"] == 3

    def test_page_two(self, client):
        _bulk_loads(5)
        resp = client.get("/api/dispatch/loads?page=2&per_page=2")
        data = resp.get_json()
        assert data["count"] == 2
        assert data["total"] == 5
        assert data["page"] == 2

    def test_last_page_partial(self, client):
        _bulk_loads(5)
        resp = client.get("/api/dispatch/loads?page=3&per_page=2")
        data = resp.get_json()
        assert data["count"] == 1
        assert data["total"] == 5


class TestSettlementsPagination:
    def test_no_pagination(self, client):
        _bulk_settlements(3)
        resp = client.get("/api/dispatch/settlements")
        data = resp.get_json()
        assert data["count"] == 3
        assert "page" not in data

    def test_paginated(self, client):
        _bulk_settlements(5)
        resp = client.get("/api/dispatch/settlements?page=1&per_page=2")
        data = resp.get_json()
        assert data["count"] == 2
        assert data["total"] == 5
        assert data["pages"] == 3


class TestDriversPagination:
    def test_no_pagination(self, client):
        _bulk_drivers(3)
        resp = client.get("/api/dispatch/drivers")
        data = resp.get_json()
        assert data["count"] == 3
        assert "page" not in data

    def test_paginated(self, client):
        _bulk_drivers(5)
        resp = client.get("/api/dispatch/drivers?page=1&per_page=2")
        data = resp.get_json()
        assert data["count"] == 2
        assert data["total"] == 5
        assert data["pages"] == 3


class TestEquipmentPagination:
    def test_no_pagination(self, client):
        _bulk_equipment(3)
        resp = client.get("/api/dispatch/equipment")
        data = resp.get_json()
        assert data["count"] == 3
        assert "page" not in data

    def test_paginated(self, client):
        _bulk_equipment(5)
        resp = client.get("/api/dispatch/equipment?page=1&per_page=2")
        data = resp.get_json()
        assert data["count"] == 2
        assert data["total"] == 5
        assert data["pages"] == 3


class TestExceptionsPagination:
    def test_no_pagination(self, client):
        _bulk_exceptions(3)
        resp = client.get("/api/dispatch/exceptions")
        data = resp.get_json()
        assert data["count"] == 3
        assert "page" not in data

    def test_paginated(self, client):
        _bulk_exceptions(5)
        resp = client.get("/api/dispatch/exceptions?page=1&per_page=2")
        data = resp.get_json()
        assert data["count"] == 2
        assert data["total"] == 5
        assert data["pages"] == 3


# ── Backward compatibility ───────────────────────────────────────────


class TestBackwardCompatibility:
    def test_existing_load_tests_still_work(self, client):
        services.create_load(customer="Compat Test")
        resp = client.get("/api/dispatch/loads")
        data = resp.get_json()
        assert data["status"] == "ok"
        assert isinstance(data["loads"], list)
        assert data["count"] == 1

    def test_existing_filter_with_pagination(self, client):
        services.create_load(customer="Alpha")
        services.create_load(customer="Beta")
        resp = client.get("/api/dispatch/loads?customer=Alpha&page=1&per_page=10")
        data = resp.get_json()
        assert data["total"] == 1
        assert data["loads"][0]["customer"] == "Alpha"

    def test_invalid_page_ignored(self, client):
        services.create_load(customer="Test")
        resp = client.get("/api/dispatch/loads?page=abc")
        data = resp.get_json()
        assert data["count"] == 1
        assert "page" not in data
