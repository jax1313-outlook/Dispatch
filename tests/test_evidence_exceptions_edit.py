"""Tests for evidence edit/delete and exception update (PR 35)."""

from __future__ import annotations

import pytest

from dispatch import services
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


@pytest.fixture
def sample_load():
    return services.create_load(customer="Test Corp")


# ── Evidence store/service layer ─────────────────────────────────


class TestEvidenceUpdate:
    def test_update_description(self, sample_load):
        ev = services.attach_evidence(sample_load["load_id"], description="original")
        updated = services.update_evidence(ev["evidence_id"], description="corrected")
        assert updated["description"] == "corrected"

    def test_update_evidence_type(self, sample_load):
        ev = services.attach_evidence(sample_load["load_id"], evidence_type="document")
        updated = services.update_evidence(ev["evidence_id"], evidence_type="photo")
        assert updated["evidence_type"] == "photo"

    def test_update_uploaded_by(self, sample_load):
        ev = services.attach_evidence(sample_load["load_id"], uploaded_by="alice")
        updated = services.update_evidence(ev["evidence_id"], uploaded_by="bob")
        assert updated["uploaded_by"] == "bob"

    def test_update_nonexistent_returns_none(self):
        assert services.update_evidence("NOPE", description="x") is None

    def test_update_ignores_disallowed_fields(self, sample_load):
        ev = services.attach_evidence(sample_load["load_id"])
        updated = services.update_evidence(ev["evidence_id"], load_id="HACK")
        assert updated["load_id"] == sample_load["load_id"]

    def test_update_no_fields_returns_existing(self, sample_load):
        ev = services.attach_evidence(sample_load["load_id"], description="keep")
        updated = services.update_evidence(ev["evidence_id"])
        assert updated["description"] == "keep"


class TestEvidenceDelete:
    def test_delete_evidence(self, sample_load):
        ev = services.attach_evidence(sample_load["load_id"])
        assert services.delete_evidence(ev["evidence_id"]) is True
        remaining = services.list_evidence(sample_load["load_id"])
        assert len(remaining) == 0

    def test_delete_nonexistent_returns_false(self):
        assert services.delete_evidence("NOPE") is False

    def test_delete_one_keeps_others(self, sample_load):
        ev1 = services.attach_evidence(sample_load["load_id"], description="keep")
        ev2 = services.attach_evidence(sample_load["load_id"], description="remove")
        services.delete_evidence(ev2["evidence_id"])
        remaining = services.list_evidence(sample_load["load_id"])
        assert len(remaining) == 1
        assert remaining[0]["description"] == "keep"


# ── Evidence API endpoints ───────────────────────────────────────


class TestEvidenceAPI:
    def test_patch_evidence(self, client, sample_load):
        ev = services.attach_evidence(sample_load["load_id"], description="old")
        resp = client.patch(
            f"/api/dispatch/evidence/{ev['evidence_id']}",
            json={"description": "new"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["evidence"]["description"] == "new"

    def test_patch_evidence_validates_type(self, client, sample_load):
        ev = services.attach_evidence(sample_load["load_id"])
        resp = client.patch(
            f"/api/dispatch/evidence/{ev['evidence_id']}",
            json={"evidence_type": "INVALID"},
        )
        assert resp.status_code == 400

    def test_patch_evidence_not_found(self, client):
        resp = client.patch("/api/dispatch/evidence/NOPE", json={"description": "x"})
        assert resp.status_code == 404

    def test_delete_evidence_api(self, client, sample_load):
        ev = services.attach_evidence(sample_load["load_id"])
        resp = client.delete(f"/api/dispatch/evidence/{ev['evidence_id']}")
        assert resp.status_code == 200

    def test_delete_evidence_not_found(self, client):
        resp = client.delete("/api/dispatch/evidence/NOPE")
        assert resp.status_code == 404


# ── Evidence UI buttons ──────────────────────────────────────────


class TestEvidenceUI:
    def test_edit_button_shown(self, client, sample_load):
        services.attach_evidence(sample_load["load_id"], description="test doc")
        resp = client.get(f"/dispatch/{sample_load['load_id']}")
        html = resp.data.decode()
        assert "Edit</button>" in html

    def test_remove_button_shown(self, client, sample_load):
        services.attach_evidence(sample_load["load_id"])
        resp = client.get(f"/dispatch/{sample_load['load_id']}")
        html = resp.data.decode()
        assert "Remove</button>" in html

    def test_actions_column_header(self, client, sample_load):
        services.attach_evidence(sample_load["load_id"])
        resp = client.get(f"/dispatch/{sample_load['load_id']}")
        html = resp.data.decode()
        assert "<th>Actions</th>" in html


# ── Exception update ─────────────────────────────────────────────


class TestExceptionUpdate:
    def test_update_severity(self, sample_load):
        exc = services.open_exception(sample_load["load_id"], severity="low")
        updated = services.update_exception(exc["exception_id"], severity="critical")
        assert updated["severity"] == "critical"

    def test_update_description(self, sample_load):
        exc = services.open_exception(sample_load["load_id"], description="wrong")
        updated = services.update_exception(exc["exception_id"], description="corrected")
        assert updated["description"] == "corrected"

    def test_update_nonexistent(self):
        assert services.update_exception("NOPE", severity="high") is None


class TestExceptionUpdateAPI:
    def test_patch_exception(self, client, sample_load):
        exc = services.open_exception(sample_load["load_id"], severity="low")
        resp = client.patch(
            f"/api/dispatch/exceptions/{exc['exception_id']}",
            json={"severity": "high"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["exception"]["severity"] == "high"

    def test_patch_validates_severity(self, client, sample_load):
        exc = services.open_exception(sample_load["load_id"])
        resp = client.patch(
            f"/api/dispatch/exceptions/{exc['exception_id']}",
            json={"severity": "INVALID"},
        )
        assert resp.status_code == 400

    def test_patch_validates_exception_type(self, client, sample_load):
        exc = services.open_exception(sample_load["load_id"])
        resp = client.patch(
            f"/api/dispatch/exceptions/{exc['exception_id']}",
            json={"exception_type": "INVALID"},
        )
        assert resp.status_code == 400

    def test_patch_not_found(self, client):
        resp = client.patch("/api/dispatch/exceptions/NOPE", json={"severity": "low"})
        assert resp.status_code == 404
