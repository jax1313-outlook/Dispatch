"""Tests for compliance document tracker — models, store, services, API, template."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from dispatch.db import set_db_path
from dispatch.models import (
    COMPLIANCE_DOC_TYPES,
    COMPLIANCE_DOC_STATUSES,
    COMPLIANCE_ENTITY_TYPES,
    ComplianceDocument,
)
from dispatch import services, store


@pytest.fixture(autouse=True)
def _db(tmp_path):
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


def _future_date(days: int) -> str:
    return (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d")


def _past_date(days: int) -> str:
    return (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")


# ── Model tests ──────────────────────────────────────────────────


class TestComplianceDocumentModel:
    def test_defaults(self):
        doc = ComplianceDocument(title="Test", doc_type="insurance_liability")
        assert doc.doc_id.startswith("COMP-")
        assert doc.entity_type == "company"
        assert doc.status == "active"
        assert doc.alert_days == 30
        assert doc.created_at
        assert doc.updated_at

    def test_invalid_doc_type(self):
        with pytest.raises(ValueError, match="doc_type"):
            ComplianceDocument(title="Test", doc_type="invalid")

    def test_invalid_entity_type(self):
        with pytest.raises(ValueError, match="entity_type"):
            ComplianceDocument(title="Test", entity_type="invalid")

    def test_invalid_status(self):
        with pytest.raises(ValueError, match="status"):
            ComplianceDocument(title="Test", status="invalid")

    def test_to_dict(self):
        doc = ComplianceDocument(title="My Insurance", doc_type="insurance_cargo")
        d = doc.to_dict()
        assert d["title"] == "My Insurance"
        assert "is_expired" in d
        assert "days_until_expiry" in d
        assert "needs_alert" in d

    def test_is_expired_past_date(self):
        doc = ComplianceDocument(title="Test", expiry_date=_past_date(10))
        assert doc.is_expired is True

    def test_is_expired_future_date(self):
        doc = ComplianceDocument(title="Test", expiry_date=_future_date(10))
        assert doc.is_expired is False

    def test_is_expired_no_date(self):
        doc = ComplianceDocument(title="Test")
        assert doc.is_expired is False

    def test_days_until_expiry(self):
        doc = ComplianceDocument(title="Test", expiry_date=_future_date(15))
        assert doc.days_until_expiry == 15

    def test_days_until_expiry_negative(self):
        doc = ComplianceDocument(title="Test", expiry_date=_past_date(5))
        assert doc.days_until_expiry == -5

    def test_days_until_expiry_none(self):
        doc = ComplianceDocument(title="Test")
        assert doc.days_until_expiry is None

    def test_needs_alert_within_window(self):
        doc = ComplianceDocument(title="Test", expiry_date=_future_date(15), alert_days=30)
        assert doc.needs_alert is True

    def test_needs_alert_outside_window(self):
        doc = ComplianceDocument(title="Test", expiry_date=_future_date(60), alert_days=30)
        assert doc.needs_alert is False

    def test_needs_alert_no_date(self):
        doc = ComplianceDocument(title="Test", alert_days=30)
        assert doc.needs_alert is False

    def test_doc_types_list(self):
        assert "insurance_liability" in COMPLIANCE_DOC_TYPES
        assert "medical_card" in COMPLIANCE_DOC_TYPES
        assert "cdl" in COMPLIANCE_DOC_TYPES
        assert "ifta_license" in COMPLIANCE_DOC_TYPES
        assert len(COMPLIANCE_DOC_TYPES) == 16

    def test_entity_types_list(self):
        assert COMPLIANCE_ENTITY_TYPES == ["company", "driver", "equipment"]

    def test_doc_statuses_list(self):
        assert COMPLIANCE_DOC_STATUSES == ["active", "expiring_soon", "expired", "renewed"]


# ── Store tests ──────────────────────────────────────────────────


class TestComplianceDocumentStore:
    def test_create_and_get(self):
        doc = ComplianceDocument(title="Liability Insurance", doc_type="insurance_liability",
                                 expiry_date=_future_date(90))
        result = store.create_compliance_document(doc)
        assert result["title"] == "Liability Insurance"
        fetched = store.get_compliance_document(result["doc_id"])
        assert fetched is not None
        assert fetched["doc_type"] == "insurance_liability"
        assert "is_expired" in fetched
        assert "days_until_expiry" in fetched

    def test_list_all(self):
        store.create_compliance_document(ComplianceDocument(title="Doc 1", doc_type="insurance_liability"))
        store.create_compliance_document(ComplianceDocument(title="Doc 2", doc_type="medical_card"))
        docs = store.list_compliance_documents()
        assert len(docs) == 2

    def test_list_by_entity_type(self):
        store.create_compliance_document(ComplianceDocument(title="Co Doc", entity_type="company"))
        store.create_compliance_document(ComplianceDocument(title="Driver Doc", entity_type="driver", entity_id="D1"))
        docs = store.list_compliance_documents(entity_type="driver")
        assert len(docs) == 1
        assert docs[0]["entity_type"] == "driver"

    def test_list_by_doc_type(self):
        store.create_compliance_document(ComplianceDocument(title="Ins", doc_type="insurance_liability"))
        store.create_compliance_document(ComplianceDocument(title="Med", doc_type="medical_card"))
        docs = store.list_compliance_documents(doc_type="medical_card")
        assert len(docs) == 1

    def test_list_by_status(self):
        store.create_compliance_document(ComplianceDocument(title="Active", status="active"))
        store.create_compliance_document(ComplianceDocument(title="Expired", status="expired"))
        docs = store.list_compliance_documents(status="active")
        assert len(docs) == 1

    def test_update(self):
        doc = ComplianceDocument(title="Test", doc_type="cdl")
        result = store.create_compliance_document(doc)
        updated = store.update_compliance_document(result["doc_id"], title="Updated CDL")
        assert updated["title"] == "Updated CDL"

    def test_update_nonexistent(self):
        result = store.update_compliance_document("COMP-NOPE", title="X")
        assert result is None

    def test_delete(self):
        doc = ComplianceDocument(title="Test", doc_type="cdl")
        result = store.create_compliance_document(doc)
        assert store.delete_compliance_document(result["doc_id"]) is True
        assert store.get_compliance_document(result["doc_id"]) is None

    def test_delete_nonexistent(self):
        assert store.delete_compliance_document("COMP-NOPE") is False

    def test_get_nonexistent(self):
        assert store.get_compliance_document("COMP-NOPE") is None

    def test_get_expiring(self):
        store.create_compliance_document(ComplianceDocument(
            title="Expiring", doc_type="insurance_liability",
            expiry_date=_future_date(10), status="active"))
        store.create_compliance_document(ComplianceDocument(
            title="Not expiring", doc_type="insurance_cargo",
            expiry_date=_future_date(90), status="active"))
        docs = store.get_expiring_compliance_documents(days_ahead=30)
        assert len(docs) == 1
        assert docs[0]["title"] == "Expiring"

    def test_get_expiring_includes_expired(self):
        store.create_compliance_document(ComplianceDocument(
            title="Past", doc_type="cdl",
            expiry_date=_past_date(5), status="active"))
        docs = store.get_expiring_compliance_documents(days_ahead=30)
        assert len(docs) == 1
        assert docs[0]["is_expired"] is True

    def test_list_enriches_docs(self):
        store.create_compliance_document(ComplianceDocument(
            title="Test", expiry_date=_future_date(10)))
        docs = store.list_compliance_documents()
        assert docs[0]["is_expired"] is False
        assert docs[0]["days_until_expiry"] == 10
        assert docs[0]["needs_alert"] is True


# ── Service tests ────────────────────────────────────────────────


class TestComplianceDocumentService:
    def test_add_document(self):
        doc = services.add_compliance_document(
            doc_type="insurance_liability",
            title="General Liability",
            expiry_date=_future_date(180),
        )
        assert doc["title"] == "General Liability"
        assert doc["doc_type"] == "insurance_liability"

    def test_add_document_no_title(self):
        with pytest.raises(ValueError, match="Title"):
            services.add_compliance_document(doc_type="cdl", title="")

    def test_add_document_blank_title(self):
        with pytest.raises(ValueError, match="Title"):
            services.add_compliance_document(doc_type="cdl", title="   ")

    def test_add_document_negative_alert_days(self):
        with pytest.raises(ValueError, match="Alert days"):
            services.add_compliance_document(doc_type="cdl", title="Test", alert_days=-1)

    def test_add_document_invalid_doc_type(self):
        with pytest.raises(ValueError, match="doc_type"):
            services.add_compliance_document(doc_type="bogus", title="Test")

    def test_update_document(self):
        doc = services.add_compliance_document(doc_type="cdl", title="CDL")
        updated = services.update_compliance_document(doc["doc_id"], title="CDL - Class A")
        assert updated["title"] == "CDL - Class A"

    def test_update_document_not_found(self):
        with pytest.raises(ValueError, match="not found"):
            services.update_compliance_document("COMP-NOPE", title="X")

    def test_update_invalid_doc_type(self):
        doc = services.add_compliance_document(doc_type="cdl", title="CDL")
        with pytest.raises(ValueError, match="doc_type"):
            services.update_compliance_document(doc["doc_id"], doc_type="invalid")

    def test_update_invalid_status(self):
        doc = services.add_compliance_document(doc_type="cdl", title="CDL")
        with pytest.raises(ValueError, match="status"):
            services.update_compliance_document(doc["doc_id"], status="invalid")

    def test_update_invalid_entity_type(self):
        doc = services.add_compliance_document(doc_type="cdl", title="CDL")
        with pytest.raises(ValueError, match="entity_type"):
            services.update_compliance_document(doc["doc_id"], entity_type="invalid")

    def test_update_negative_alert_days(self):
        doc = services.add_compliance_document(doc_type="cdl", title="CDL")
        with pytest.raises(ValueError, match="Alert days"):
            services.update_compliance_document(doc["doc_id"], alert_days=-5)

    def test_delete_document(self):
        doc = services.add_compliance_document(doc_type="cdl", title="CDL")
        assert services.delete_compliance_document(doc["doc_id"]) is True

    def test_get_document(self):
        doc = services.add_compliance_document(doc_type="cdl", title="CDL")
        fetched = services.get_compliance_document(doc["doc_id"])
        assert fetched["title"] == "CDL"

    def test_list_documents(self):
        services.add_compliance_document(doc_type="cdl", title="CDL")
        services.add_compliance_document(doc_type="medical_card", title="Med Card")
        docs = services.list_compliance_documents()
        assert len(docs) == 2

    def test_get_expiring(self):
        services.add_compliance_document(
            doc_type="insurance_liability", title="Expiring",
            expiry_date=_future_date(10))
        docs = services.get_expiring_compliance_documents(days_ahead=30)
        assert len(docs) == 1

    def test_check_alerts_marks_expired(self):
        services.add_compliance_document(
            doc_type="cdl", title="Expired CDL",
            expiry_date=_past_date(5))
        result = services.check_compliance_alerts()
        assert result["expired"] == 1
        doc = services.list_compliance_documents(status="expired")
        assert len(doc) == 1

    def test_check_alerts_marks_expiring_soon(self):
        services.add_compliance_document(
            doc_type="insurance_liability", title="Expiring Insurance",
            expiry_date=_future_date(15), alert_days=30)
        result = services.check_compliance_alerts()
        assert result["expiring_soon"] == 1
        doc = services.list_compliance_documents(status="expiring_soon")
        assert len(doc) == 1

    def test_check_alerts_skips_safe(self):
        services.add_compliance_document(
            doc_type="insurance_liability", title="Safe Insurance",
            expiry_date=_future_date(90), alert_days=30)
        result = services.check_compliance_alerts()
        assert result["expired"] == 0
        assert result["expiring_soon"] == 0

    def test_entity_type_driver(self):
        doc = services.add_compliance_document(
            doc_type="medical_card", title="Med Card",
            entity_type="driver", entity_id="DRV-001")
        assert doc["entity_type"] == "driver"
        assert doc["entity_id"] == "DRV-001"

    def test_entity_type_equipment(self):
        doc = services.add_compliance_document(
            doc_type="irp_registration", title="IRP",
            entity_type="equipment", entity_id="EQP-001")
        assert doc["entity_type"] == "equipment"


# ── API tests ────────────────────────────────────────────────────


class TestComplianceDocumentAPI:
    def test_add_document(self, client):
        resp = client.post("/api/dispatch/compliance", json={
            "doc_type": "insurance_liability",
            "title": "General Liability Policy",
            "expiry_date": _future_date(180),
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["title"] == "General Liability Policy"

    def test_add_document_no_title(self, client):
        resp = client.post("/api/dispatch/compliance", json={
            "doc_type": "cdl",
            "title": "",
        })
        assert resp.status_code == 400

    def test_get_document(self, client):
        resp = client.post("/api/dispatch/compliance", json={
            "doc_type": "cdl", "title": "CDL"
        })
        doc_id = resp.get_json()["doc_id"]
        resp2 = client.get(f"/api/dispatch/compliance/{doc_id}")
        assert resp2.status_code == 200
        assert resp2.get_json()["title"] == "CDL"

    def test_get_document_not_found(self, client):
        resp = client.get("/api/dispatch/compliance/COMP-NOPE")
        assert resp.status_code == 404

    def test_list_documents(self, client):
        client.post("/api/dispatch/compliance", json={"doc_type": "cdl", "title": "CDL"})
        client.post("/api/dispatch/compliance", json={"doc_type": "medical_card", "title": "Med"})
        resp = client.get("/api/dispatch/compliance")
        assert resp.status_code == 200
        assert len(resp.get_json()) == 2

    def test_list_with_filters(self, client):
        client.post("/api/dispatch/compliance", json={
            "doc_type": "cdl", "title": "CDL", "entity_type": "driver"
        })
        client.post("/api/dispatch/compliance", json={
            "doc_type": "insurance_liability", "title": "Insurance"
        })
        resp = client.get("/api/dispatch/compliance?doc_type=cdl")
        assert len(resp.get_json()) == 1

    def test_update_document(self, client):
        resp = client.post("/api/dispatch/compliance", json={
            "doc_type": "cdl", "title": "CDL"
        })
        doc_id = resp.get_json()["doc_id"]
        resp2 = client.patch(f"/api/dispatch/compliance/{doc_id}", json={
            "title": "CDL Class A"
        })
        assert resp2.status_code == 200
        assert resp2.get_json()["title"] == "CDL Class A"

    def test_update_document_invalid(self, client):
        resp = client.post("/api/dispatch/compliance", json={
            "doc_type": "cdl", "title": "CDL"
        })
        doc_id = resp.get_json()["doc_id"]
        resp2 = client.patch(f"/api/dispatch/compliance/{doc_id}", json={
            "doc_type": "invalid"
        })
        assert resp2.status_code == 400

    def test_delete_document(self, client):
        resp = client.post("/api/dispatch/compliance", json={
            "doc_type": "cdl", "title": "CDL"
        })
        doc_id = resp.get_json()["doc_id"]
        resp2 = client.delete(f"/api/dispatch/compliance/{doc_id}")
        assert resp2.status_code == 200

    def test_delete_not_found(self, client):
        resp = client.delete("/api/dispatch/compliance/COMP-NOPE")
        assert resp.status_code == 404

    def test_expiring_endpoint(self, client):
        client.post("/api/dispatch/compliance", json={
            "doc_type": "insurance_liability", "title": "Expiring",
            "expiry_date": _future_date(10),
        })
        resp = client.get("/api/dispatch/compliance/expiring?days=30")
        assert resp.status_code == 200
        assert len(resp.get_json()) == 1

    def test_check_alerts_endpoint(self, client):
        client.post("/api/dispatch/compliance", json={
            "doc_type": "cdl", "title": "Expired CDL",
            "expiry_date": _past_date(5),
        })
        resp = client.post("/api/dispatch/compliance/check-alerts")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["expired"] == 1


# ── Template tests ───────────────────────────────────────────────


class TestComplianceTemplate:
    def test_page_loads(self, client):
        resp = client.get("/compliance")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Compliance Document Tracker" in html
        assert "Add Document" in html

    def test_nav_link(self, client):
        resp = client.get("/compliance")
        html = resp.data.decode()
        assert "/compliance" in html

    def test_filter_controls(self, client):
        resp = client.get("/compliance")
        html = resp.data.decode()
        assert "All Entities" in html
        assert "All Types" in html
        assert "All Statuses" in html

    def test_doc_types_in_form(self, client):
        resp = client.get("/compliance")
        html = resp.data.decode()
        assert "insurance_liability" in html
        assert "medical_card" in html
        assert "cdl" in html

    def test_empty_state(self, client):
        resp = client.get("/compliance")
        html = resp.data.decode()
        assert "No compliance documents found" in html

    def test_with_documents(self, client):
        client.post("/api/dispatch/compliance", json={
            "doc_type": "insurance_liability",
            "title": "General Liability Policy",
            "expiry_date": _future_date(90),
        })
        resp = client.get("/compliance")
        html = resp.data.decode()
        assert "General Liability Policy" in html
        assert "Insurance Liability" in html

    def test_expired_badge(self, client):
        resp = client.post("/api/dispatch/compliance", json={
            "doc_type": "cdl", "title": "Old CDL",
            "expiry_date": _past_date(10),
        })
        doc_id = resp.get_json()["doc_id"]
        client.post("/api/dispatch/compliance/check-alerts")
        resp2 = client.get("/compliance?status=expired")
        html = resp2.data.decode()
        assert "Old CDL" in html

    def test_alert_bar_all_clear(self, client):
        resp = client.get("/compliance")
        html = resp.data.decode()
        assert "All compliance documents are current" in html

    def test_alert_bar_with_expiring(self, client):
        client.post("/api/dispatch/compliance", json={
            "doc_type": "insurance_liability",
            "title": "Expiring Insurance",
            "expiry_date": _future_date(10),
        })
        resp = client.get("/compliance")
        html = resp.data.decode()
        assert "expiring within 30 days" in html

    def test_check_alerts_button(self, client):
        resp = client.get("/compliance")
        html = resp.data.decode()
        assert "Check Alerts" in html

    def test_entity_type_filter(self, client):
        client.post("/api/dispatch/compliance", json={
            "doc_type": "medical_card", "title": "Med Card",
            "entity_type": "driver", "entity_id": "DRV-001"
        })
        client.post("/api/dispatch/compliance", json={
            "doc_type": "insurance_liability", "title": "Insurance"
        })
        resp = client.get("/compliance?entity_type=driver")
        html = resp.data.decode()
        assert "Med Card" in html
        assert "Documents (1)" in html
