"""Tests for broker contact directory feature."""

from __future__ import annotations

import json

import pytest

from dispatch.db import set_db_path
from dispatch.models import BROKER_STATUSES, BrokerContact


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


# ── Model Tests ──────────────────────────────────────────────────────


class TestBrokerContactModel:
    def test_create_with_defaults(self):
        b = BrokerContact(company_name="Test Broker")
        assert b.broker_id.startswith("BRK-")
        assert b.company_name == "Test Broker"
        assert b.status == "active"
        assert b.created_at
        assert b.updated_at == b.created_at

    def test_requires_company_name(self):
        with pytest.raises(ValueError, match="company name is required"):
            BrokerContact()

    def test_validates_status(self):
        with pytest.raises(ValueError, match="Invalid status"):
            BrokerContact(company_name="X", status="invalid")

    def test_valid_statuses(self):
        for s in BROKER_STATUSES:
            b = BrokerContact(company_name="Test", status=s)
            assert b.status == s

    def test_to_dict(self):
        b = BrokerContact(company_name="ABC Freight", phone="555-1234")
        d = b.to_dict()
        assert d["company_name"] == "ABC Freight"
        assert d["phone"] == "555-1234"
        assert "broker_id" in d

    def test_all_fields_populated(self):
        b = BrokerContact(
            company_name="Full Broker",
            contact_name="John Doe",
            phone="555-0000",
            email="john@broker.com",
            mc_number="MC-123456",
            dot_number="DOT-789",
            address="123 Main St",
            payment_terms="Net 30",
            notes="Reliable",
        )
        d = b.to_dict()
        assert d["contact_name"] == "John Doe"
        assert d["mc_number"] == "MC-123456"
        assert d["dot_number"] == "DOT-789"
        assert d["address"] == "123 Main St"
        assert d["payment_terms"] == "Net 30"


# ── Service Tests ────────────────────────────────────────────────────


class TestBrokerContactService:
    def test_add_broker(self):
        from dispatch.services import add_broker_contact
        b = add_broker_contact(company_name="Service Broker", phone="555-1111")
        assert b["company_name"] == "Service Broker"
        assert b["phone"] == "555-1111"
        assert b["status"] == "active"

    def test_add_broker_requires_name(self):
        from dispatch.services import add_broker_contact
        with pytest.raises(ValueError, match="Company name is required"):
            add_broker_contact(company_name="")

    def test_add_broker_strips_name(self):
        from dispatch.services import add_broker_contact
        b = add_broker_contact(company_name="  Spaced Broker  ")
        assert b["company_name"] == "Spaced Broker"

    def test_add_duplicate_broker(self):
        from dispatch.services import add_broker_contact
        add_broker_contact(company_name="Unique Broker")
        with pytest.raises(ValueError, match="already exists"):
            add_broker_contact(company_name="Unique Broker")

    def test_add_broker_validates_status(self):
        from dispatch.services import add_broker_contact
        with pytest.raises(ValueError, match="Invalid status"):
            add_broker_contact(company_name="Bad Status", status="unknown")

    def test_get_broker(self):
        from dispatch.services import add_broker_contact, get_broker_contact
        b = add_broker_contact(company_name="Get Test")
        result = get_broker_contact(b["broker_id"])
        assert result["company_name"] == "Get Test"

    def test_get_broker_not_found(self):
        from dispatch.services import get_broker_contact
        assert get_broker_contact("BRK-NONEXIST") is None

    def test_list_brokers(self):
        from dispatch.services import add_broker_contact, list_broker_contacts
        add_broker_contact(company_name="Alpha Freight")
        add_broker_contact(company_name="Beta Logistics")
        result = list_broker_contacts()
        assert len(result) == 2

    def test_list_brokers_filter_status(self):
        from dispatch.services import add_broker_contact, list_broker_contacts
        add_broker_contact(company_name="Active One")
        add_broker_contact(company_name="Inactive One", status="inactive")
        active = list_broker_contacts(status="active")
        assert len(active) == 1
        assert active[0]["company_name"] == "Active One"

    def test_list_brokers_search(self):
        from dispatch.services import add_broker_contact, list_broker_contacts
        add_broker_contact(company_name="XYZ Express", mc_number="MC-999")
        add_broker_contact(company_name="ABC Freight")
        result = list_broker_contacts(search="MC-999")
        assert len(result) == 1
        assert result[0]["company_name"] == "XYZ Express"

    def test_update_broker(self):
        from dispatch.services import add_broker_contact, update_broker_contact
        b = add_broker_contact(company_name="Before Update")
        result = update_broker_contact(b["broker_id"], {"phone": "555-9999"})
        assert result["phone"] == "555-9999"
        assert result["updated_at"] >= b["updated_at"]

    def test_update_broker_validates_status(self):
        from dispatch.services import add_broker_contact, update_broker_contact
        b = add_broker_contact(company_name="Status Test")
        with pytest.raises(ValueError, match="Invalid status"):
            update_broker_contact(b["broker_id"], {"status": "bogus"})

    def test_update_broker_duplicate_name(self):
        from dispatch.services import add_broker_contact, update_broker_contact
        add_broker_contact(company_name="Existing Broker")
        b2 = add_broker_contact(company_name="Other Broker")
        with pytest.raises(ValueError, match="already exists"):
            update_broker_contact(b2["broker_id"], {"company_name": "Existing Broker"})

    def test_update_broker_same_name_ok(self):
        from dispatch.services import add_broker_contact, update_broker_contact
        b = add_broker_contact(company_name="Self Name")
        result = update_broker_contact(b["broker_id"], {"company_name": "Self Name"})
        assert result["company_name"] == "Self Name"

    def test_update_broker_not_found(self):
        from dispatch.services import update_broker_contact
        assert update_broker_contact("BRK-NONE", {"phone": "x"}) is None

    def test_delete_broker(self):
        from dispatch.services import add_broker_contact, delete_broker_contact, get_broker_contact
        b = add_broker_contact(company_name="Delete Me")
        assert delete_broker_contact(b["broker_id"]) is True
        assert get_broker_contact(b["broker_id"]) is None

    def test_delete_broker_not_found(self):
        from dispatch.services import delete_broker_contact
        assert delete_broker_contact("BRK-NONE") is False

    def test_get_broker_with_stats(self):
        from dispatch.services import add_broker_contact, get_broker_contact_with_stats
        b = add_broker_contact(company_name="Stats Broker")
        result = get_broker_contact_with_stats(b["broker_id"])
        assert result["load_count"] == 0
        assert result["loads"] == []

    def test_get_broker_with_stats_not_found(self):
        from dispatch.services import get_broker_contact_with_stats
        assert get_broker_contact_with_stats("BRK-NONE") is None


# ── API Tests ────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestBrokerContactAPI:
    def test_create_broker(self, client):
        r = client.post("/api/dispatch/broker-contacts", json={"company_name": "API Broker"})
        assert r.status_code == 201
        data = r.get_json()
        assert data["company_name"] == "API Broker"

    def test_create_broker_missing_name(self, client):
        r = client.post("/api/dispatch/broker-contacts", json={})
        assert r.status_code == 400

    def test_list_brokers(self, client):
        client.post("/api/dispatch/broker-contacts", json={"company_name": "List A"})
        client.post("/api/dispatch/broker-contacts", json={"company_name": "List B"})
        r = client.get("/api/dispatch/broker-contacts")
        assert r.status_code == 200
        data = r.get_json()
        assert len(data) == 2

    def test_list_brokers_filter_status(self, client):
        client.post("/api/dispatch/broker-contacts", json={"company_name": "Active", "status": "active"})
        client.post("/api/dispatch/broker-contacts", json={"company_name": "Inactive", "status": "inactive"})
        r = client.get("/api/dispatch/broker-contacts?status=active")
        data = r.get_json()
        assert len(data) == 1

    def test_list_brokers_search(self, client):
        client.post("/api/dispatch/broker-contacts", json={"company_name": "Searchable", "mc_number": "MC-555"})
        client.post("/api/dispatch/broker-contacts", json={"company_name": "Other"})
        r = client.get("/api/dispatch/broker-contacts?search=MC-555")
        data = r.get_json()
        assert len(data) == 1

    def test_get_broker(self, client):
        r = client.post("/api/dispatch/broker-contacts", json={"company_name": "Get API"})
        bid = r.get_json()["broker_id"]
        r = client.get(f"/api/dispatch/broker-contacts/{bid}")
        assert r.status_code == 200
        assert r.get_json()["company_name"] == "Get API"

    def test_get_broker_not_found(self, client):
        r = client.get("/api/dispatch/broker-contacts/BRK-NONE")
        assert r.status_code == 404

    def test_update_broker(self, client):
        r = client.post("/api/dispatch/broker-contacts", json={"company_name": "Update API"})
        bid = r.get_json()["broker_id"]
        r = client.put(f"/api/dispatch/broker-contacts/{bid}", json={"phone": "555-UPDATED"})
        assert r.status_code == 200
        assert r.get_json()["phone"] == "555-UPDATED"

    def test_update_broker_not_found(self, client):
        r = client.put("/api/dispatch/broker-contacts/BRK-NONE", json={"phone": "x"})
        assert r.status_code == 404

    def test_delete_broker(self, client):
        r = client.post("/api/dispatch/broker-contacts", json={"company_name": "Delete API"})
        bid = r.get_json()["broker_id"]
        r = client.delete(f"/api/dispatch/broker-contacts/{bid}")
        assert r.status_code == 200

    def test_delete_broker_not_found(self, client):
        r = client.delete("/api/dispatch/broker-contacts/BRK-NONE")
        assert r.status_code == 404


# ── Template Tests ───────────────────────────────────────────────────


class TestBrokerContactTemplate:
    def test_brokers_page_loads(self, client):
        r = client.get("/brokers")
        assert r.status_code == 200
        html = r.data.decode()
        assert "Contact Directory" in html
        assert "Performance Scorecard" in html

    def test_brokers_page_shows_contacts(self, client):
        client.post("/api/dispatch/broker-contacts", json={
            "company_name": "Template Broker",
            "mc_number": "MC-TMPL",
            "phone": "555-TMPL",
        })
        r = client.get("/brokers")
        html = r.data.decode()
        assert "Template Broker" in html
        assert "MC-TMPL" in html
        assert "555-TMPL" in html

    def test_brokers_page_shows_status_badges(self, client):
        client.post("/api/dispatch/broker-contacts", json={
            "company_name": "Badge Broker",
            "status": "blacklisted",
        })
        r = client.get("/brokers")
        html = r.data.decode()
        assert "blacklisted" in html

    def test_brokers_page_add_form_present(self, client):
        r = client.get("/brokers")
        html = r.data.decode()
        assert "add-broker-form" in html
        assert "company_name" in html

    def test_brokers_page_search_present(self, client):
        r = client.get("/brokers")
        html = r.data.decode()
        assert "broker-search" in html
