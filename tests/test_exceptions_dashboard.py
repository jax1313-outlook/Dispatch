"""Tests for the exceptions dashboard: global API, page route, bug fixes."""

from __future__ import annotations

import pytest

from dispatch import services
from dispatch.db import set_db_path
from dispatch.models import EXCEPTION_TYPES, SEVERITY_LEVELS


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


def _make_load_with_exception(customer="TestCo", exc_type="delay", severity="medium"):
    load = services.create_load(customer=customer)
    exc = services.open_exception(
        load_id=load["load_id"],
        exception_type=exc_type,
        severity=severity,
        description=f"Test {exc_type} exception",
    )
    return load, exc


# ── Global Exceptions API ──────────────────────────────────────────


class TestGlobalExceptionsAPI:
    def test_list_all_exceptions(self, client):
        _make_load_with_exception(customer="A")
        _make_load_with_exception(customer="B")
        resp = client.get("/api/dispatch/exceptions")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 2

    def test_filter_by_status(self, client):
        _, exc = _make_load_with_exception()
        _make_load_with_exception(customer="Other")
        services.resolve_exception(exc["exception_id"], "fixed it")
        resp = client.get("/api/dispatch/exceptions?status=open")
        data = resp.get_json()
        assert data["count"] == 1

    def test_filter_by_severity(self, client):
        _make_load_with_exception(severity="low")
        _make_load_with_exception(severity="critical")
        resp = client.get("/api/dispatch/exceptions?severity=critical")
        data = resp.get_json()
        assert data["count"] == 1
        assert data["exceptions"][0]["severity"] == "critical"

    def test_filter_by_type(self, client):
        _make_load_with_exception(exc_type="damage")
        _make_load_with_exception(exc_type="weather")
        resp = client.get("/api/dispatch/exceptions?exception_type=damage")
        data = resp.get_json()
        assert data["count"] == 1
        assert data["exceptions"][0]["exception_type"] == "damage"

    def test_invalid_status_returns_400(self, client):
        resp = client.get("/api/dispatch/exceptions?status=bogus")
        assert resp.status_code == 400

    def test_invalid_severity_returns_400(self, client):
        resp = client.get("/api/dispatch/exceptions?severity=bogus")
        assert resp.status_code == 400

    def test_invalid_type_returns_400(self, client):
        resp = client.get("/api/dispatch/exceptions?exception_type=bogus")
        assert resp.status_code == 400

    def test_empty_result(self, client):
        resp = client.get("/api/dispatch/exceptions")
        data = resp.get_json()
        assert data["count"] == 0
        assert data["exceptions"] == []


# ── Exceptions Page Route ──────────────────────────────────────────


class TestExceptionsPage:
    def test_page_loads_empty(self, client):
        resp = client.get("/exceptions")
        assert resp.status_code == 200
        assert b"Exceptions" in resp.data

    def test_page_shows_exceptions(self, client):
        _make_load_with_exception(customer="Acme Corp", exc_type="damage", severity="high")
        resp = client.get("/exceptions")
        assert resp.status_code == 200
        assert b"Acme Corp" in resp.data
        assert b"Damage" in resp.data

    def test_page_filters_by_status(self, client):
        _, exc = _make_load_with_exception(customer="Open Co")
        services.resolve_exception(exc["exception_id"], "done")
        _make_load_with_exception(customer="Still Open")
        resp = client.get("/exceptions?status=open")
        assert resp.status_code == 200
        assert b"Still Open" in resp.data
        assert b"Open Co" not in resp.data

    def test_page_filters_by_severity(self, client):
        _make_load_with_exception(customer="Low Sev", severity="low")
        _make_load_with_exception(customer="Crit Sev", severity="critical")
        resp = client.get("/exceptions?severity=critical")
        assert resp.status_code == 200
        assert b"Crit Sev" in resp.data
        assert b"Low Sev" not in resp.data

    def test_page_filters_by_type(self, client):
        _make_load_with_exception(customer="Weather Co", exc_type="weather")
        _make_load_with_exception(customer="Delay Co", exc_type="delay")
        resp = client.get("/exceptions?exception_type=weather")
        assert resp.status_code == 200
        assert b"Weather Co" in resp.data
        assert b"Delay Co" not in resp.data

    def test_summary_cards_present(self, client):
        _make_load_with_exception(severity="critical")
        resp = client.get("/exceptions")
        assert b"Critical (Open)" in resp.data
        assert b"High (Open)" in resp.data

    def test_status_pills_rendered(self, client):
        resp = client.get("/exceptions")
        assert b"All Statuses" in resp.data
        assert b"Open" in resp.data
        assert b"Investigating" in resp.data
        assert b"Resolved" in resp.data
        assert b"Closed" in resp.data


# ── Exception Status Transitions via API ───────────────────────────


class TestExceptionStatusTransitions:
    def test_investigate_exception(self, client):
        _, exc = _make_load_with_exception()
        resp = client.patch(
            f"/api/dispatch/exceptions/{exc['exception_id']}",
            json={"status": "investigating"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["exception"]["status"] == "investigating"

    def test_resolve_exception(self, client):
        _, exc = _make_load_with_exception()
        resp = client.post(
            f"/api/dispatch/exceptions/{exc['exception_id']}/resolve",
            json={"resolution_note": "Fixed the delay"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["exception"]["status"] == "resolved"
        assert data["exception"]["resolution_note"] == "Fixed the delay"

    def test_close_resolved_exception(self, client):
        _, exc = _make_load_with_exception()
        services.resolve_exception(exc["exception_id"], "done")
        resp = client.patch(
            f"/api/dispatch/exceptions/{exc['exception_id']}",
            json={"status": "closed"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["exception"]["status"] == "closed"


# ── Exception Type Dropdown Bug Fix ────────────────────────────────


class TestExceptionTypeBugFix:
    def test_detail_page_uses_model_types(self, client):
        load = services.create_load(customer="Bug Test")
        resp = client.get(f"/dispatch/{load['load_id']}")
        assert resp.status_code == 200
        for et in EXCEPTION_TYPES:
            label = et.replace("_", " ").title()
            assert label.encode() in resp.data, f"Missing exception type: {label}"
        assert b"Refusal" not in resp.data
        assert b"Shortage" not in resp.data
        assert b"Overage" not in resp.data

    def test_detail_page_uses_model_severities(self, client):
        load = services.create_load(customer="Sev Test")
        resp = client.get(f"/dispatch/{load['load_id']}")
        assert resp.status_code == 200
        for sv in SEVERITY_LEVELS:
            assert sv.title().encode() in resp.data

    def test_all_model_exception_types_are_valid(self, client):
        load = services.create_load(customer="Valid Types")
        for et in EXCEPTION_TYPES:
            exc = services.open_exception(
                load_id=load["load_id"],
                exception_type=et,
                description=f"Testing {et}",
            )
            assert exc["exception_type"] == et


# ── Settlements API Filter Pass-through ────────────────────────────


class TestSettlementsAPIFilters:
    def test_filter_by_customer(self, client):
        load1 = services.create_load(customer="Alpha Inc")
        load2 = services.create_load(customer="Beta LLC")
        services.confirm_rate(load1["load_id"], rate_amount=1000)
        services.confirm_rate(load2["load_id"], rate_amount=2000)
        services.create_settlement(load1["load_id"])
        services.create_settlement(load2["load_id"])
        resp = client.get("/api/dispatch/settlements?customer=Alpha")
        data = resp.get_json()
        assert data["count"] == 1

    def test_filter_by_invoice(self, client):
        load = services.create_load(customer="Invoice Test")
        services.confirm_rate(load["load_id"], rate_amount=500)
        stl = services.create_settlement(load["load_id"])
        inv = stl["invoice_number"]
        resp = client.get(f"/api/dispatch/settlements?invoice={inv[:8]}")
        data = resp.get_json()
        assert data["count"] == 1


# ── Sidebar Navigation ────────────────────────────────────────────


class TestSidebarNavigation:
    def test_exceptions_link_in_sidebar(self, client):
        resp = client.get("/")
        assert resp.status_code in (200, 302)
        resp = client.get("/home")
        assert b"/exceptions" in resp.data
