"""Tests for the Driver PIN Registry (portal/models/driver_pin_registry.py)
and the Driver Portal (portal/routes/driver_portal.py) -- Phone Number + PIN
authentication for the Driver role, issued and managed only by Mike
(Authority), separate from both the internal Authority DISPATCH_PIN login
and the external token-secured stakeholder portal.

Covers: PIN Card CRUD, phone+PIN login (including lockout, mirroring
identity.py's own lockout tests), Active/Inactive status control, Recovery
Word self-service reset, that hashes never leak out of the model, that a
driver session cannot reach internal Authority-only pages (checked against
the real DISPATCH_PIN gate, not just the TESTING default), COMI lookup,
Route Risk lookup (the honest "not yet available" stub), SMS/email contact
retrieval, and Mike's admin CRUD surface on the Library page.
"""

from __future__ import annotations

import pytest

from dispatch import services
from dispatch.db import set_db_path
from portal.models import driver_pin_registry as pin_registry


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture(autouse=True)
def _portal_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal_data"))


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def driver():
    return services.create_driver(name="Jane Trucker", phone="904-555-0100")


# ── PIN Card CRUD ────────────────────────────────────────────────────


class TestCreatePinCard:
    def test_create_succeeds_and_strips_hashes(self, driver):
        card = pin_registry.create_pin_card(
            driver["driver_id"], pin="1234", recovery_word="anchor", created_by="mike",
        )
        assert card["driver_id"] == driver["driver_id"]
        assert card["status"] == "active"
        assert "pin_hash" not in card
        assert "recovery_word_hash" not in card

    def test_get_and_list_also_strip_hashes(self, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        got = pin_registry.get_pin_card(driver["driver_id"])
        assert "pin_hash" not in got and "recovery_word_hash" not in got
        listed = pin_registry.list_pin_cards()
        assert len(listed) == 1
        assert "pin_hash" not in listed[0]

    def test_unknown_driver_rejected(self):
        with pytest.raises(pin_registry.DriverPinError):
            pin_registry.create_pin_card("LOAD-DOES-NOT-EXIST", "1234", "anchor", "mike")

    def test_driver_with_no_phone_rejected(self):
        drv = services.create_driver(name="No Phone Driver")
        with pytest.raises(pin_registry.DriverPinError):
            pin_registry.create_pin_card(drv["driver_id"], "1234", "anchor", "mike")

    def test_duplicate_card_rejected(self, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        with pytest.raises(pin_registry.DriverPinError):
            pin_registry.create_pin_card(driver["driver_id"], "5678", "other", "mike")

    def test_short_pin_rejected(self, driver):
        with pytest.raises(pin_registry.DriverPinError):
            pin_registry.create_pin_card(driver["driver_id"], "12", "anchor", "mike")

    def test_short_recovery_word_rejected(self, driver):
        with pytest.raises(pin_registry.DriverPinError):
            pin_registry.create_pin_card(driver["driver_id"], "1234", "ab", "mike")


class TestResetAndRecoveryWord:
    def test_reset_pin_allows_login_with_new_pin(self, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        pin_registry.reset_pin(driver["driver_id"], "9999", reset_by="mike")
        assert pin_registry.verify_login(driver["phone"], "9999") is not None
        assert pin_registry.verify_login(driver["phone"], "1234") is None

    def test_set_recovery_word_changes_it(self, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        pin_registry.set_recovery_word(driver["driver_id"], "newword", set_by="mike")
        assert pin_registry.verify_recovery_word(driver["phone"], "anchor") is None
        assert pin_registry.verify_recovery_word(driver["phone"], "newword") is not None


class TestStatusControl:
    def test_deactivate_blocks_login(self, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        pin_registry.set_status(driver["driver_id"], "inactive", changed_by="mike")
        assert pin_registry.verify_login(driver["phone"], "1234") is None

    def test_reactivate_restores_login(self, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        pin_registry.set_status(driver["driver_id"], "inactive", changed_by="mike")
        pin_registry.set_status(driver["driver_id"], "active", changed_by="mike")
        assert pin_registry.verify_login(driver["phone"], "1234") is not None

    def test_invalid_status_rejected(self, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        with pytest.raises(pin_registry.DriverPinError):
            pin_registry.set_status(driver["driver_id"], "banned", changed_by="mike")

    def test_deactivate_does_not_touch_driver_roster_status(self, driver):
        """PIN Card status controls Driver Portal access only -- independent of the
        driver's own employment/roster status on the drivers table."""
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        pin_registry.set_status(driver["driver_id"], "inactive", changed_by="mike")
        assert services.get_driver(driver["driver_id"])["status"] == "active"


class TestDeletePinCard:
    def test_delete_removes_card(self, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        assert pin_registry.delete_pin_card(driver["driver_id"], deleted_by="mike") is True
        assert pin_registry.get_pin_card(driver["driver_id"]) is None
        assert pin_registry.verify_login(driver["phone"], "1234") is None

    def test_delete_nonexistent_returns_false(self):
        assert pin_registry.delete_pin_card("no-such-driver", deleted_by="mike") is False


# ── Phone Number + PIN login ─────────────────────────────────────────


class TestVerifyLogin:
    def test_correct_credentials_succeed(self, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        record = pin_registry.verify_login(driver["phone"], "1234")
        assert record is not None
        assert record["driver_id"] == driver["driver_id"]
        assert record["last_login_at"] is not None

    def test_wrong_pin_fails(self, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        assert pin_registry.verify_login(driver["phone"], "0000") is None

    def test_unknown_phone_fails(self, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        assert pin_registry.verify_login("000-000-0000", "1234") is None

    def test_driver_with_no_card_cannot_login(self, driver):
        assert pin_registry.verify_login(driver["phone"], "1234") is None

    def test_lockout_after_max_failed_attempts(self, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        for _ in range(pin_registry.MAX_FAILED_ATTEMPTS):
            pin_registry.verify_login(driver["phone"], "wrong")
        # Correct PIN is still rejected while locked out.
        assert pin_registry.verify_login(driver["phone"], "1234") is None

    def test_successful_login_resets_failed_attempt_count(self, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        pin_registry.verify_login(driver["phone"], "wrong")
        pin_registry.verify_login(driver["phone"], "wrong")
        pin_registry.verify_login(driver["phone"], "1234")
        card = pin_registry.get_pin_card(driver["driver_id"])
        assert card["failed_attempt_count"] == 0
        assert card["locked_until"] is None


class TestRecoveryWordReset:
    def test_correct_recovery_word_resets_pin(self, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        result = pin_registry.reset_pin_with_recovery_word(driver["phone"], "anchor", "5678")
        assert result is not None
        assert pin_registry.verify_login(driver["phone"], "5678") is not None
        assert pin_registry.verify_login(driver["phone"], "1234") is None

    def test_wrong_recovery_word_fails(self, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        assert pin_registry.reset_pin_with_recovery_word(driver["phone"], "wrongword", "5678") is None
        assert pin_registry.verify_login(driver["phone"], "1234") is not None

    def test_recovery_word_reset_clears_lockout(self, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        for _ in range(pin_registry.MAX_FAILED_ATTEMPTS):
            pin_registry.verify_login(driver["phone"], "wrong")
        pin_registry.reset_pin_with_recovery_word(driver["phone"], "anchor", "5678")
        assert pin_registry.verify_login(driver["phone"], "5678") is not None

    def test_inactive_card_cannot_self_recover(self, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        pin_registry.set_status(driver["driver_id"], "inactive", changed_by="mike")
        assert pin_registry.reset_pin_with_recovery_word(driver["phone"], "anchor", "5678") is None

    def test_short_new_pin_raises(self, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        with pytest.raises(pin_registry.DriverPinError):
            pin_registry.reset_pin_with_recovery_word(driver["phone"], "anchor", "12")


# ── Route: Driver Portal ─────────────────────────────────────────────


class TestDriverPortalRoutes:
    def test_login_page_renders(self, client):
        resp = client.get("/driver/login")
        assert resp.status_code == 200
        assert b"Driver Portal" in resp.data

    def test_home_without_session_redirects_to_login(self, client):
        resp = client.get("/driver/home")
        assert resp.status_code == 302
        assert "/driver/login" in resp.headers["Location"]

    def test_login_success_redirects_home(self, client, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        resp = client.post("/driver/login", data={"phone": driver["phone"], "pin": "1234"})
        assert resp.status_code == 302
        assert "/driver/home" in resp.headers["Location"]

    def test_login_failure_returns_401(self, client, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        resp = client.post("/driver/login", data={"phone": driver["phone"], "pin": "0000"})
        assert resp.status_code == 401

    def test_home_shows_driver_name_and_active_load(self, client, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        load = services.create_load(
            customer="COMI Test Co", pickup_location="Dallas, TX", delivery_location="Reno, NV",
        )
        services.update_load(load["load_id"], driver_id=driver["driver_id"])
        client.post("/driver/login", data={"phone": driver["phone"], "pin": "1234"})
        resp = client.get("/driver/home")
        html = resp.data.decode("utf-8")
        assert "Jane Trucker" in html
        assert "Dallas, TX" in html
        assert "Reno, NV" in html

    def test_home_excludes_archived_loads(self, client, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        load = services.create_load(customer="Archived Co", pickup_location="X", delivery_location="Y")
        services.update_load(load["load_id"], driver_id=driver["driver_id"])
        for status in (
            "dispatched", "en_route_pickup", "at_pickup", "picked_up",
            "in_transit", "at_delivery", "delivered",
        ):
            services.update_load(load["load_id"], status=status)
        services.archive_load(load["load_id"])
        client.post("/driver/login", data={"phone": driver["phone"], "pin": "1234"})
        resp = client.get("/driver/home")
        assert "No active loads assigned" in resp.data.decode("utf-8")

    def test_home_shows_route_risk_not_available(self, client, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        load = services.create_load(customer="Risk Co")
        services.update_load(load["load_id"], driver_id=driver["driver_id"])
        client.post("/driver/login", data={"phone": driver["phone"], "pin": "1234"})
        resp = client.get("/driver/home")
        assert b"not yet available" in resp.data

    def test_home_shows_comi_status(self, client, driver):
        from portal.models import email_helper

        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        load = services.create_load(customer="COMI Status Co")
        services.update_load(load["load_id"], driver_id=driver["driver_id"])
        email_helper.create_draft(load["load_id"], load=services.get_load(load["load_id"]))
        client.post("/driver/login", data={"phone": driver["phone"], "pin": "1234"})
        resp = client.get("/driver/home")
        assert b"DRAFT" in resp.data

    def test_home_shows_broker_contact(self, client, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        services.add_broker_contact(
            company_name="Acme Brokerage", contact_name="Bob Broker",
            phone="555-111-2222", email="bob@acmebrokerage.example.com",
        )
        load = services.create_load(customer="Contact Co", broker_shipper="Acme Brokerage")
        services.update_load(load["load_id"], driver_id=driver["driver_id"])
        client.post("/driver/login", data={"phone": driver["phone"], "pin": "1234"})
        resp = client.get("/driver/home")
        html = resp.data.decode("utf-8")
        assert "Bob Broker" in html
        assert "555-111-2222" in html

    def test_home_shows_dispatch_contact_email(self, client, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        client.post("/driver/login", data={"phone": driver["phone"], "pin": "1234"})
        resp = client.get("/driver/home")
        assert b"@" in resp.data

    def test_logout_clears_session(self, client, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        client.post("/driver/login", data={"phone": driver["phone"], "pin": "1234"})
        client.post("/driver/logout")
        resp = client.get("/driver/home")
        assert resp.status_code == 302
        assert "/driver/login" in resp.headers["Location"]

    def test_forgot_pin_page_renders(self, client):
        resp = client.get("/driver/forgot-pin")
        assert resp.status_code == 200

    def test_forgot_pin_success_allows_new_login(self, client, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        resp = client.post("/driver/forgot-pin", data={
            "phone": driver["phone"], "recovery_word": "anchor", "new_pin": "5678",
        })
        assert resp.status_code == 200
        assert b"PIN updated" in resp.data
        login_resp = client.post("/driver/login", data={"phone": driver["phone"], "pin": "5678"})
        assert login_resp.status_code == 302

    def test_forgot_pin_wrong_word_returns_401(self, client, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        resp = client.post("/driver/forgot-pin", data={
            "phone": driver["phone"], "recovery_word": "wrong", "new_pin": "5678",
        })
        assert resp.status_code == 401


class TestDriverSessionCannotReachAuthorityPages:
    """A driver session (session['driver_id']) must never satisfy the Authority
    gate (session['user_id']) -- exercised against the REAL DISPATCH_PIN gate,
    mirroring TestStakeholderRouteBypassesRealPinGate's pattern in
    test_stakeholder_portal.py."""

    @pytest.fixture
    def auth_app(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "auth_portal_data"))
        from portal.app import create_app
        return create_app({"TESTING": True, "SECRET_KEY": "test", "LOGIN_DISABLED": False})

    @pytest.fixture
    def auth_client(self, auth_app):
        return auth_app.test_client()

    def test_driver_portal_bypasses_the_real_gate(self, auth_client):
        resp = auth_client.get("/driver/login")
        assert resp.status_code == 200

    def test_logged_in_driver_still_redirected_from_internal_pages(self, auth_app, auth_client):
        with auth_app.app_context():
            drv = services.create_driver(name="Gate Test Driver", phone="111-222-3333")
            pin_registry.create_pin_card(drv["driver_id"], "1234", "anchor", "mike")
        auth_client.post("/driver/login", data={"phone": "111-222-3333", "pin": "1234"})
        resp = auth_client.get("/home")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]
        assert "/driver/login" not in resp.headers["Location"]


# ── Mike's admin CRUD API ────────────────────────────────────────────


class TestDriverPinApi:
    def test_create_via_api(self, client, driver):
        resp = client.post("/api/driver-pin/create", json={
            "driver_id": driver["driver_id"], "pin": "1234", "recovery_word": "anchor",
        })
        assert resp.status_code == 200
        assert resp.get_json()["record"]["driver_id"] == driver["driver_id"]

    def test_create_via_api_missing_fields(self, client, driver):
        resp = client.post("/api/driver-pin/create", json={"driver_id": driver["driver_id"]})
        assert resp.status_code == 400

    def test_reset_via_api(self, client, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        resp = client.post("/api/driver-pin/reset", json={
            "driver_id": driver["driver_id"], "new_pin": "5678",
        })
        assert resp.status_code == 200
        assert pin_registry.verify_login(driver["phone"], "5678") is not None

    def test_recovery_word_via_api(self, client, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        resp = client.post("/api/driver-pin/recovery-word", json={
            "driver_id": driver["driver_id"], "recovery_word": "newword",
        })
        assert resp.status_code == 200
        assert pin_registry.verify_recovery_word(driver["phone"], "newword") is not None

    def test_status_via_api(self, client, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        resp = client.post("/api/driver-pin/status", json={
            "driver_id": driver["driver_id"], "status": "inactive",
        })
        assert resp.status_code == 200
        assert pin_registry.get_pin_card(driver["driver_id"])["status"] == "inactive"

    def test_delete_via_api(self, client, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        resp = client.post("/api/driver-pin/delete", json={"driver_id": driver["driver_id"]})
        assert resp.status_code == 200
        assert pin_registry.get_pin_card(driver["driver_id"]) is None

    def test_delete_via_api_nonexistent_404(self, client):
        resp = client.post("/api/driver-pin/delete", json={"driver_id": "no-such-driver"})
        assert resp.status_code == 404


# ── Library page shows the registry ─────────────────────────────────


class TestLibraryPageShowsRegistry:
    def test_page_lists_issue_button_for_driver_without_card(self, client, driver):
        resp = client.get("/library")
        assert resp.status_code == 200
        assert f"Issue PIN for {driver['name']}".encode() in resp.data

    def test_page_lists_existing_card(self, client, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        resp = client.get("/library")
        html = resp.data.decode("utf-8")
        assert driver["name"] in html
        assert "Driver PIN Registry" in html
