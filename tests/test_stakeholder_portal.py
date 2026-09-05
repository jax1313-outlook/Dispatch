"""Tests for the external stakeholder portal (broker/shipper/customer
read-only view of a single load, D11 disclosure chain). Covers: token
security (HMAC verify + PIN-gate exemption), correct data rendering, and
that internal-only content (Level 1 Transport's own profit/margin,
driver personal contact info, internal notes/activity thread, server
filesystem paths) never reaches this route.
"""

from __future__ import annotations

import pytest

from dispatch import notifications, services
from dispatch.db import set_db_path


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


def _url(load_id: str, token: str | None = None) -> str:
    token = notifications.make_stakeholder_token(load_id) if token is None else token
    return f"/portal/loads/{load_id}?token={token}"


# ── Token security ───────────────────────────────────────────────────


class TestStakeholderTokenSecurity:
    def test_valid_token_verifies(self):
        assert notifications.verify_stakeholder_token(
            "LOAD-1", notifications.make_stakeholder_token("LOAD-1")
        )

    def test_wrong_load_id_fails(self):
        token = notifications.make_stakeholder_token("LOAD-1")
        assert not notifications.verify_stakeholder_token("LOAD-2", token)

    def test_decision_token_cannot_be_replayed_as_stakeholder_token(self):
        """A stakeholder-view token and a decision-action token are HMACs
        over different namespaced strings -- one must never verify as the
        other, even for the same load_id."""
        decision_token = notifications.make_token("LOAD-1", "acknowledge")
        assert not notifications.verify_stakeholder_token("LOAD-1", decision_token)

    def test_missing_token_rejected(self, client):
        load = services.create_load(customer="Stakeholder Sec Co")
        resp = client.get(f"/portal/loads/{load['load_id']}")
        assert resp.status_code == 403

    def test_bad_token_rejected(self, client):
        load = services.create_load(customer="Stakeholder Sec Co 2")
        resp = client.get(_url(load["load_id"], token="not-the-real-token"))
        assert resp.status_code == 403

    def test_nonexistent_load_with_valid_token_is_404(self, client):
        resp = client.get(_url("LOAD-DOES-NOT-EXIST"))
        assert resp.status_code == 404

    def test_route_reachable_without_login_session(self, client):
        """The whole point of this route: no portal session, no PIN --
        this exercises the exemption in portal/app.py's before_request
        gate directly against TESTING=True's LOGIN_DISABLED default."""
        load = services.create_load(customer="Stakeholder No Login Co")
        resp = client.get(_url(load["load_id"]))
        assert resp.status_code == 200


class TestStakeholderRouteBypassesRealPinGate:
    """Exercises the real DISPATCH_PIN gate (LOGIN_DISABLED explicitly
    False), mirroring TestDispatchPinAuthentication in test_portal.py."""

    @pytest.fixture
    def auth_app(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "auth_portal_data"))
        from portal.app import create_app
        return create_app({"TESTING": True, "SECRET_KEY": "test", "LOGIN_DISABLED": False})

    @pytest.fixture
    def auth_client(self, auth_app):
        return auth_app.test_client()

    def test_unauthenticated_internal_route_still_redirects(self, auth_client):
        """Sanity check: the gate itself is on -- an ordinary internal
        route still bounces to /login under this fixture."""
        resp = auth_client.get("/home")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_stakeholder_route_bypasses_the_real_gate(self, auth_client):
        load = services.create_load(customer="Real Gate Bypass Co")
        token = notifications.make_stakeholder_token(load["load_id"])
        resp = auth_client.get(f"/portal/loads/{load['load_id']}?token={token}")
        assert resp.status_code == 200


# ── Renders shared data ─────────────────────────────────────────────


class TestStakeholderViewRenders:
    def test_renders_load_info(self, client):
        load = services.create_load(
            customer="Acme Mfg",
            broker_shipper="National Freight Brokerage",
            pickup_location="Dallas, TX",
            delivery_location="Houston, TX",
        )
        resp = client.get(_url(load["load_id"]))
        html = resp.data.decode("utf-8")
        assert "Acme Mfg" in html
        assert "National Freight Brokerage" in html
        assert "Dallas, TX" in html
        assert "Houston, TX" in html

    def test_renders_milestones(self, client):
        load = services.create_load(customer="Stakeholder MS Co")
        services.add_milestone(load["load_id"], "dispatched", location="Yard A")
        resp = client.get(_url(load["load_id"]))
        html = resp.data.decode("utf-8")
        assert "Dispatched" in html
        assert "Yard A" in html

    def test_renders_rate_and_settlement(self, client):
        """D11: rate/fee/cost figures ARE shared with this chain."""
        load = services.create_load(customer="Stakeholder Rate Co")
        services.confirm_rate(load["load_id"], rate_amount=1500, distance_miles=400)
        stl = services.create_settlement(load["load_id"])
        resp = client.get(_url(load["load_id"]))
        html = resp.data.decode("utf-8")
        assert "1500.00" in html or "1,500.00" in html
        assert stl["invoice_number"] in html


# ── Internal-only content is excluded ────────────────────────────────


class TestStakeholderViewExcludesInternalContent:
    def test_excludes_profit_and_margin(self, client):
        """Level 1 Transport's own P&L on the load is not a rate/fee/cost
        figure covered by D11 -- it must never reach this external view."""
        load = services.create_load(customer="Stakeholder PL Co")
        services.confirm_rate(load["load_id"], rate_amount=2000, distance_miles=500)
        services.add_expense(load["load_id"], category="fuel", amount=300)
        resp = client.get(_url(load["load_id"]))
        html = resp.data.decode("utf-8")
        assert "margin_pct" not in html
        assert "profit" not in html.lower()

    def test_excludes_driver_personal_contact_info(self, client):
        load = services.create_load(customer="Stakeholder Driver Co")
        driver = services.create_driver(
            name="Jane Trucker", phone="555-867-5309", email="jane@example.com",
            license_number="DL-SECRET-999",
        )
        services.update_load(load["load_id"], driver_id=driver["driver_id"])
        resp = client.get(_url(load["load_id"]))
        html = resp.data.decode("utf-8")
        assert "Jane Trucker" in html
        assert "555-867-5309" not in html
        assert "jane@example.com" not in html
        assert "DL-SECRET-999" not in html

    def test_excludes_internal_note_and_activity_thread(self, client):
        load = services.create_load(customer="Stakeholder Internal Note Co")
        services.update_visibility_notes(
            load["load_id"], customer_note="On schedule", internal_note="Driver called in sick once"
        )
        services.add_activity(load["load_id"], activity_type="comment", message="Internal ops chatter", author="dispatcher")
        resp = client.get(_url(load["load_id"]))
        html = resp.data.decode("utf-8")
        assert "On schedule" in html
        assert "Driver called in sick once" not in html
        assert "Internal ops chatter" not in html

    def test_excludes_evidence_file_paths_and_download_links(self, client):
        load = services.create_load(customer="Stakeholder Evidence Co")
        services.attach_evidence(
            load["load_id"], evidence_type="photo", original_filename="pod.jpg",
            file_path="/srv/dispatch/uploads/secret-internal-path/pod.jpg",
        )
        resp = client.get(_url(load["load_id"]))
        html = resp.data.decode("utf-8")
        assert "secret-internal-path" not in html
        assert "download_evidence" not in html

    def test_excludes_archive_location_filesystem_path(self, client):
        load = services.create_load(customer="Stakeholder Archive Path Co")
        for status in (
            "dispatched", "en_route_pickup", "at_pickup", "picked_up",
            "in_transit", "at_delivery", "delivered",
        ):
            services.update_load(load["load_id"], status=status)
        services.archive_load(load["load_id"])
        retention = services.build_stakeholder_view(load["load_id"])["retention"]
        assert "archive_location" not in retention
        resp = client.get(_url(load["load_id"]))
        assert resp.status_code == 200
