"""Tests for load board source indicator — model, service, API, template."""

from __future__ import annotations

import pytest

from dispatch.db import set_db_path
from dispatch.models import LOAD_SOURCES, Load
from dispatch import services


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


# ── Model tests ────────────────────────────────────────────────────


class TestLoadSourceModel:
    def test_load_sources_defined(self):
        assert "dat" in LOAD_SOURCES
        assert "truckstop" in LOAD_SOURCES
        assert "direct" in LOAD_SOURCES
        assert "broker_call" in LOAD_SOURCES
        assert "email" in LOAD_SOURCES
        assert "referral" in LOAD_SOURCES
        assert "website" in LOAD_SOURCES
        assert "other" in LOAD_SOURCES

    def test_load_with_source(self):
        load = Load(customer="Test", source="dat")
        assert load.source == "dat"

    def test_load_empty_source_allowed(self):
        load = Load(customer="Test")
        assert load.source == ""

    def test_load_invalid_source_rejected(self):
        with pytest.raises(ValueError, match="source"):
            Load(customer="Test", source="invalid_source")

    def test_load_to_dict_includes_source(self):
        load = Load(customer="Test", source="truckstop")
        d = load.to_dict()
        assert d["source"] == "truckstop"

    def test_all_sources_valid(self):
        for src in LOAD_SOURCES:
            load = Load(customer="Test", source=src)
            assert load.source == src


# ── Service tests ──────────────────────────────────────────────────


class TestLoadSourceService:
    def test_create_load_with_source(self):
        load = services.create_load(customer="Acme", source="dat")
        assert load["source"] == "dat"

    def test_create_load_without_source(self):
        load = services.create_load(customer="Acme")
        assert load["source"] == ""

    def test_create_load_invalid_source(self):
        with pytest.raises(ValueError, match="source"):
            services.create_load(customer="Acme", source="invalid")

    def test_update_load_source(self):
        load = services.create_load(customer="Acme")
        updated = services.update_load(load["load_id"], source="broker_call")
        assert updated["source"] == "broker_call"

    def test_source_stats_empty(self):
        stats = services.get_load_source_stats()
        assert stats["total"] == 0
        assert stats["by_source"] == {}

    def test_source_stats_with_data(self):
        services.create_load(customer="A", source="dat")
        services.create_load(customer="B", source="dat")
        services.create_load(customer="C", source="direct")
        services.create_load(customer="D")

        stats = services.get_load_source_stats()
        assert stats["total"] == 4
        assert stats["by_source"]["dat"] == 2
        assert stats["by_source"]["direct"] == 1
        assert stats["by_source"]["unset"] == 1

    def test_source_preserved_on_update(self):
        load = services.create_load(customer="Acme", source="email")
        updated = services.update_load(load["load_id"], customer="Acme Corp")
        assert updated["source"] == "email"


# ── API tests ──────────────────────────────────────────────────────


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestLoadSourceAPI:
    def test_create_load_with_source(self, client):
        resp = client.post("/api/dispatch/loads", json={
            "customer": "Test Co", "source": "dat"
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["load"]["source"] == "dat"

    def test_create_load_invalid_source(self, client):
        resp = client.post("/api/dispatch/loads", json={
            "customer": "Test Co", "source": "invalid"
        })
        assert resp.status_code == 400

    def test_update_load_source(self, client):
        resp = client.post("/api/dispatch/loads", json={"customer": "Test Co"})
        load_id = resp.get_json()["load"]["load_id"]
        resp2 = client.patch(f"/api/dispatch/loads/{load_id}", json={"source": "truckstop"})
        assert resp2.status_code == 200
        assert resp2.get_json()["load"]["source"] == "truckstop"

    def test_source_stats_endpoint(self, client):
        client.post("/api/dispatch/loads", json={"customer": "A", "source": "dat"})
        client.post("/api/dispatch/loads", json={"customer": "B", "source": "direct"})
        resp = client.get("/api/dispatch/loads/source-stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 2
        assert data["by_source"]["dat"] == 1

    def test_load_bundle_includes_source(self, client):
        resp = client.post("/api/dispatch/loads", json={
            "customer": "Test Co", "source": "email"
        })
        load_id = resp.get_json()["load"]["load_id"]
        resp2 = client.get(f"/api/dispatch/loads/{load_id}/bundle")
        assert resp2.status_code == 200
        assert resp2.get_json()["load"]["source"] == "email"


# ── Template tests ─────────────────────────────────────────────────


class TestLoadSourceTemplate:
    def test_dispatch_page_has_source_column(self, client):
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "Source" in html

    def test_dispatch_page_source_in_create_form(self, client):
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert 'name="source"' in html
        assert "DAT" in html
        assert "Truckstop" in html

    def test_dispatch_detail_shows_source(self, client):
        resp = client.post("/api/dispatch/loads", json={
            "customer": "Test Co", "source": "dat"
        })
        load_id = resp.get_json()["load"]["load_id"]
        resp2 = client.get(f"/dispatch/{load_id}")
        assert resp2.status_code == 200
        html = resp2.data.decode()
        assert "source-dat" in html

    def test_dispatch_detail_edit_form_has_source(self, client):
        resp = client.post("/api/dispatch/loads", json={"customer": "Test Co"})
        load_id = resp.get_json()["load"]["load_id"]
        resp2 = client.get(f"/dispatch/{load_id}")
        html = resp2.data.decode()
        assert 'name="source"' in html

    def test_source_tag_with_load_in_table(self, client):
        client.post("/api/dispatch/loads", json={
            "customer": "Test Co", "source": "broker_call"
        })
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "source-broker_call" in html
        assert "Broker Call" in html
