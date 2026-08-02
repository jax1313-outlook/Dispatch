"""Tests for recurring lane templates: model, store, service, API, and UI."""

from __future__ import annotations

import pytest

from dispatch import services, store
from dispatch.db import set_db_path
from dispatch.models import LaneTemplate


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture()
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── Model ───────────────────────────────────────────────────────────


class TestLaneTemplateModel:
    def test_auto_id_and_timestamps(self):
        tpl = LaneTemplate(name="DFW → HOU")
        assert tpl.template_id.startswith("LNT-")
        assert tpl.created_at
        assert tpl.updated_at == tpl.created_at

    def test_name_required(self):
        with pytest.raises(ValueError, match="name is required"):
            LaneTemplate(name="")

    def test_to_dict(self):
        tpl = LaneTemplate(name="Test Lane")
        d = tpl.to_dict()
        assert d["name"] == "Test Lane"
        assert d["usage_count"] == 0


# ── Store layer ─────────────────────────────────────────────────────


class TestLaneTemplateStore:
    def test_create_and_get(self):
        tpl = LaneTemplate(name="DFW-HOU", customer="Acme", pickup_location="Dallas", delivery_location="Houston")
        created = store.create_lane_template(tpl)
        assert created["name"] == "DFW-HOU"
        fetched = store.get_lane_template(tpl.template_id)
        assert fetched["customer"] == "Acme"

    def test_list_sorted_by_usage(self):
        t1 = LaneTemplate(name="Low Use", usage_count=1)
        t2 = LaneTemplate(name="High Use", usage_count=10)
        store.create_lane_template(t1)
        store.create_lane_template(t2)
        result = store.list_lane_templates()
        assert result[0]["name"] == "High Use"

    def test_update(self):
        t = LaneTemplate(name="Original")
        store.create_lane_template(t)
        updated = store.update_lane_template(t.template_id, name="Renamed")
        assert updated["name"] == "Renamed"

    def test_update_nonexistent(self):
        assert store.update_lane_template("fake-id", name="X") is None

    def test_delete(self):
        t = LaneTemplate(name="ToDelete")
        store.create_lane_template(t)
        assert store.delete_lane_template(t.template_id) is True
        assert store.get_lane_template(t.template_id) is None

    def test_delete_nonexistent(self):
        assert store.delete_lane_template("fake-id") is False

    def test_increment_usage(self):
        t = LaneTemplate(name="Counter")
        store.create_lane_template(t)
        store.increment_lane_template_usage(t.template_id)
        store.increment_lane_template_usage(t.template_id)
        fetched = store.get_lane_template(t.template_id)
        assert fetched["usage_count"] == 2


# ── Service layer ───────────────────────────────────────────────────


class TestLaneTemplateService:
    def test_create(self):
        tpl = services.create_lane_template(name="Svc Test", customer="Acme")
        assert tpl["name"] == "Svc Test"
        assert tpl["customer"] == "Acme"

    def test_list_and_get(self):
        tpl = services.create_lane_template(name="List Test")
        assert any(t["template_id"] == tpl["template_id"] for t in services.list_lane_templates())
        assert services.get_lane_template(tpl["template_id"])["name"] == "List Test"

    def test_update_and_delete(self):
        tpl = services.create_lane_template(name="Lifecycle")
        updated = services.update_lane_template(tpl["template_id"], customer="NewCo")
        assert updated["customer"] == "NewCo"
        assert services.delete_lane_template(tpl["template_id"]) is True

    def test_create_load_from_template(self):
        tpl = services.create_lane_template(
            name="DFW Route",
            customer="RouteCo",
            broker_shipper="BrokerX",
            pickup_location="Dallas, TX",
            delivery_location="Houston, TX",
            equipment="Flatbed",
            notes="Handle with care",
        )
        load = services.create_load_from_template(tpl["template_id"])
        assert load["customer"] == "RouteCo"
        assert load["broker_shipper"] == "BrokerX"
        assert load["pickup_location"] == "Dallas, TX"
        assert load["delivery_location"] == "Houston, TX"
        assert load["equipment"] == "Flatbed"
        assert load["notes"] == "Handle with care"
        assert load["status"] == "created"
        refreshed = services.get_lane_template(tpl["template_id"])
        assert refreshed["usage_count"] == 1

    def test_create_load_from_nonexistent_template(self):
        assert services.create_load_from_template("fake-id") is None


# ── API layer ───────────────────────────────────────────────────────


class TestLaneTemplateAPI:
    def test_crud_lifecycle(self, client):
        resp = client.post("/api/dispatch/lane-templates", json={
            "name": "API Lane", "customer": "APICo",
            "pickup_location": "A", "delivery_location": "B",
        })
        assert resp.status_code == 201
        tpl = resp.get_json()
        tid = tpl["template_id"]

        resp = client.get("/api/dispatch/lane-templates")
        assert resp.status_code == 200
        assert any(t["template_id"] == tid for t in resp.get_json())

        resp = client.get(f"/api/dispatch/lane-templates/{tid}")
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "API Lane"

        resp = client.patch(f"/api/dispatch/lane-templates/{tid}", json={"customer": "UpdatedCo"})
        assert resp.status_code == 200
        assert resp.get_json()["customer"] == "UpdatedCo"

        resp = client.delete(f"/api/dispatch/lane-templates/{tid}")
        assert resp.status_code == 200

    def test_create_requires_name(self, client):
        resp = client.post("/api/dispatch/lane-templates", json={"customer": "NoName"})
        assert resp.status_code == 400
        assert "name" in resp.get_json()["error"]

    def test_get_nonexistent(self, client):
        resp = client.get("/api/dispatch/lane-templates/fake-id")
        assert resp.status_code == 404

    def test_create_load_from_template(self, client):
        resp = client.post("/api/dispatch/lane-templates", json={
            "name": "API Create Lane", "customer": "LoadCo",
            "pickup_location": "X", "delivery_location": "Y",
        })
        tid = resp.get_json()["template_id"]
        resp = client.post(f"/api/dispatch/lane-templates/{tid}/create-load")
        assert resp.status_code == 201
        load = resp.get_json()
        assert load["customer"] == "LoadCo"
        assert load["pickup_location"] == "X"

    def test_create_load_nonexistent_template(self, client):
        resp = client.post("/api/dispatch/lane-templates/fake-id/create-load")
        assert resp.status_code == 404


# ── Template rendering ──────────────────────────────────────────────


class TestLaneTemplateUI:
    def test_template_selector_shown(self, client):
        services.create_lane_template(
            name="UI Lane", pickup_location="A", delivery_location="B"
        )
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "Use Template:" in html
        assert "UI Lane" in html

    def test_no_template_selector_when_empty(self, client):
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "Use Template:" not in html

    def test_templates_button_shown(self, client):
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "Templates</button>" in html

    def test_template_management_section(self, client):
        services.create_lane_template(
            name="Manage Lane", customer="MgmtCo",
            pickup_location="P", delivery_location="Q"
        )
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "Manage Lane" in html
        assert "MgmtCo" in html
