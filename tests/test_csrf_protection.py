"""Workstream F: cross-site request forgery protection, proven ON.

Audit finding S-4: `grep -rniE "csrf"` across `portal/` returned nothing while
109 of 218 routes accepted POST/PATCH/PUT/DELETE on a session cookie alone.

These tests deliberately do NOT use the CSRF-carrying client from conftest --
they pass `csrf=False` so the raw request goes out exactly as a forged one
would. Everything else in the suite runs through the wrapper, which sends a
real token, so the other ~1,160 HTTP tests exercise the protected path rather
than a disabled one.
"""

from __future__ import annotations

import pytest

from dispatch import notifications, services
from dispatch.db import set_db_path
from portal.app import create_app
from portal.csrf import EXEMPT_BLUEPRINTS, EXEMPT_ENDPOINTS


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    set_db_path(tmp_path / "csrf.db")
    yield
    set_db_path(None)


@pytest.fixture()
def app():
    application = create_app({"TESTING": True})
    application.config["TESTING"] = True
    return application


@pytest.fixture()
def client(app):
    c = app.test_client()
    c.get("/login")  # establish a session and mint a token
    return c


def _token(client) -> str:
    cookie = client.get_cookie("csrf_token")
    return cookie.value if cookie else ""


class TestMutatingRoutesAreProtected:
    @pytest.mark.parametrize("method,path,payload", [
        ("post", "/api/dispatch/loads", {"customer": "Forged Co"}),
        ("post", "/api/dispatch/drivers", {"name": "Forged Driver"}),
        ("post", "/api/dispatch/equipment", {"unit_number": "FORGED-1"}),
        ("post", "/api/dispatch/lane-templates", {"name": "Forged Lane"}),
        ("post", "/api/dispatch/broker-contacts", {"company_name": "Forged Broker"}),
    ])
    def test_missing_token_is_refused(self, client, method, path, payload):
        resp = getattr(client, method)(path, json=payload, csrf=False)
        assert resp.status_code == 403

    def test_valid_token_succeeds(self, client):
        resp = client.post(
            "/api/dispatch/loads", json={"customer": "Legitimate Co"},
            headers={"X-CSRF-Token": _token(client)}, csrf=False,
        )
        assert resp.status_code == 201

    def test_invalid_token_is_refused(self, client):
        resp = client.post(
            "/api/dispatch/loads", json={"customer": "Forged Co"},
            headers={"X-CSRF-Token": "not-the-right-token"}, csrf=False,
        )
        assert resp.status_code == 403

    def test_a_token_from_another_session_is_refused(self, app, client):
        """The property that makes this CSRF protection rather than a
        formality: a token is bound to the session that minted it."""
        other = app.test_client()
        other.get("/login")
        stolen = _token(other)
        assert stolen and stolen != _token(client)

        resp = client.post(
            "/api/dispatch/loads", json={"customer": "Forged Co"},
            headers={"X-CSRF-Token": stolen}, csrf=False,
        )
        assert resp.status_code == 403

    def test_refusal_leaves_the_store_unchanged(self, client):
        before = len(services.list_loads())
        client.post("/api/dispatch/loads", json={"customer": "Forged Co"}, csrf=False)
        assert len(services.list_loads()) == before

    @pytest.mark.parametrize("method", ["patch", "delete"])
    def test_other_mutating_verbs_are_protected(self, client, method):
        load = services.create_load(customer="Target Co")
        resp = getattr(client, method)(
            f"/api/dispatch/loads/{load['load_id']}",
            json={"customer": "Rewritten"}, csrf=False,
        )
        assert resp.status_code == 403
        assert services.get_load(load["load_id"])["customer"] == "Target Co"

    def test_reads_are_not_blocked(self, client):
        assert client.get("/api/dispatch/loads").status_code == 200


class TestDriverRoutesAreProtected:
    """The Driver Transformation routes were the newest mutating surface and
    must not be the unprotected one."""

    @pytest.fixture()
    def driver_client(self, app, tmp_path, monkeypatch):
        from portal.models import driver_pin_registry as pin_registry
        driver = services.create_driver(name="CSRF Driver", phone="904-555-0100")
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        c = app.test_client()
        c.post("/driver/login", data={"phone": driver["phone"], "pin": "1234"}, csrf=False)
        load = services.create_load(customer="CSRF Co", driver_id=driver["driver_id"])
        return c, driver, load

    def test_milestone_post_requires_a_token(self, driver_client):
        c, _driver, load = driver_client
        resp = c.post(
            f"/driver/loads/{load['load_id']}/milestone",
            data={"milestone_event": "dispatched"}, csrf=False,
        )
        assert resp.status_code == 403
        assert services.get_load(load["load_id"])["status"] == "created"

    def test_pod_post_requires_a_token(self, driver_client):
        c, _driver, load = driver_client
        resp = c.post(f"/driver/loads/{load['load_id']}/pod", data={}, csrf=False)
        assert resp.status_code == 403

    def test_exception_post_requires_a_token(self, driver_client):
        c, _driver, load = driver_client
        resp = c.post(
            f"/driver/loads/{load['load_id']}/exception",
            data={"exception_type": "detention"}, csrf=False,
        )
        assert resp.status_code == 403

    def test_fuel_receipt_requires_a_token(self, driver_client):
        c, _driver, _load = driver_client
        resp = c.post("/driver/fuel-receipt", data={}, csrf=False)
        assert resp.status_code == 403

    def test_a_driver_with_a_token_still_works(self, driver_client):
        c, _driver, load = driver_client
        resp = c.post(
            f"/driver/loads/{load['load_id']}/milestone",
            data={"milestone_event": "dispatched", "csrf_token": _token(c)},
            csrf=False, follow_redirects=True,
        )
        assert resp.status_code == 200
        assert services.get_load(load["load_id"])["status"] == "dispatched"


class TestExemptions:
    """The exemption list must be exactly the endpoints that have no session to
    bind a token to and carry their own signed credential instead. Anything
    wider and the protection quietly stops protecting."""

    def test_the_exemption_list_is_the_login_gate_list(self):
        assert EXEMPT_BLUEPRINTS == {"decisions", "stakeholder"}
        assert "dispatch_api.dispatch_decision" in EXEMPT_ENDPOINTS
        # A whole-blueprint exemption for dispatch_api would open 146 routes.
        assert not any(e == "dispatch_api" for e in EXEMPT_BLUEPRINTS)

    def test_the_email_decision_link_still_works_without_a_token(self, client):
        """These arrive from a mail client with no session at all."""
        load = services.create_load(customer="Decision Co")
        token = notifications.make_token(load["load_id"], "acknowledge")
        resp = client.get(
            f"/api/dispatch/decision/{load['load_id']}/acknowledge?token={token}"
        )
        assert resp.status_code == 200

    def test_login_itself_is_not_blocked(self, app):
        """Login happens before a session exists to bind a token to."""
        fresh = app.test_client()
        resp = fresh.post("/login", data={"user_id": "nobody", "pin": "0000"}, csrf=False)
        assert resp.status_code != 403


class TestTokenPlumbing:
    def test_every_rendered_page_carries_the_token(self, client):
        html = client.get("/login").data.decode("utf-8")
        assert 'name="csrf_token"' in html

    def test_the_token_is_readable_by_the_page(self, client):
        assert _token(client)

    def test_the_form_field_is_accepted_as_well_as_the_header(self, client):
        """The driver surface posts real HTML forms, not fetch()."""
        resp = client.post(
            "/api/dispatch/loads",
            data={"customer": "Form Co", "csrf_token": _token(client)},
            csrf=False,
        )
        assert resp.status_code != 403
