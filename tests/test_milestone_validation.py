"""Tests for milestone validation workflow and visibility notes (PR 32)."""

from __future__ import annotations

import pytest

from dispatch import services, store as dispatch_store
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
def load_with_milestone():
    load = services.create_load(customer="Validation Corp")
    ms = services.add_milestone(
        load["load_id"], event_type="dispatched", location="HQ"
    )
    return load, ms


# ── store.update_milestone ────────────────────────────────────────


class TestStoreUpdateMilestone:
    def test_update_validation_status(self, load_with_milestone):
        _, ms = load_with_milestone
        updated = dispatch_store.update_milestone(
            ms["milestone_id"], validation_status="validated"
        )
        assert updated["validation_status"] == "validated"

    def test_update_note(self, load_with_milestone):
        _, ms = load_with_milestone
        updated = dispatch_store.update_milestone(
            ms["milestone_id"], note="Updated note"
        )
        assert updated["note"] == "Updated note"

    def test_nonexistent_milestone(self):
        assert dispatch_store.update_milestone("MS-FAKE", validation_status="validated") is None

    def test_ignores_disallowed_fields(self, load_with_milestone):
        _, ms = load_with_milestone
        updated = dispatch_store.update_milestone(
            ms["milestone_id"], event_type="in_transit"
        )
        assert updated["event_type"] == "dispatched"


# ── services.validate_milestone ───────────────────────────────────


class TestValidateMilestone:
    def test_validate(self, load_with_milestone):
        _, ms = load_with_milestone
        result = services.validate_milestone(ms["milestone_id"], "validated")
        assert result["validation_status"] == "validated"

    def test_dispute(self, load_with_milestone):
        _, ms = load_with_milestone
        result = services.validate_milestone(ms["milestone_id"], "disputed")
        assert result["validation_status"] == "disputed"

    def test_back_to_pending(self, load_with_milestone):
        _, ms = load_with_milestone
        services.validate_milestone(ms["milestone_id"], "validated")
        result = services.validate_milestone(ms["milestone_id"], "pending")
        assert result["validation_status"] == "pending"

    def test_invalid_status_raises(self, load_with_milestone):
        _, ms = load_with_milestone
        with pytest.raises(ValueError, match="Invalid validation_status"):
            services.validate_milestone(ms["milestone_id"], "approved")

    def test_nonexistent_returns_none(self):
        assert services.validate_milestone("MS-FAKE", "validated") is None


# ── store.update_visibility_notes ─────────────────────────────────


class TestStoreUpdateVisibilityNotes:
    def test_update_customer_note(self, load_with_milestone):
        load, _ = load_with_milestone
        result = dispatch_store.update_visibility_notes(
            load["load_id"], customer_note="Delayed by weather"
        )
        assert result["customer_note"] == "Delayed by weather"

    def test_update_internal_note(self, load_with_milestone):
        load, _ = load_with_milestone
        result = dispatch_store.update_visibility_notes(
            load["load_id"], internal_note="Driver called in sick"
        )
        assert result["internal_note"] == "Driver called in sick"

    def test_update_both_notes(self, load_with_milestone):
        load, _ = load_with_milestone
        result = dispatch_store.update_visibility_notes(
            load["load_id"],
            customer_note="ETA revised",
            internal_note="Rerouted via I-80",
        )
        assert result["customer_note"] == "ETA revised"
        assert result["internal_note"] == "Rerouted via I-80"

    def test_nonexistent_load(self):
        assert dispatch_store.update_visibility_notes("FAKE", customer_note="x") is None

    def test_no_fields_returns_existing(self, load_with_milestone):
        load, _ = load_with_milestone
        result = dispatch_store.update_visibility_notes(load["load_id"])
        assert result is not None


# ── services.update_visibility_notes ──────────────────────────────


class TestServiceUpdateVisibilityNotes:
    def test_update_notes(self, load_with_milestone):
        load, _ = load_with_milestone
        result = services.update_visibility_notes(
            load["load_id"], customer_note="Shipment delayed"
        )
        assert result["customer_note"] == "Shipment delayed"

    def test_load_not_found_raises(self):
        with pytest.raises(ValueError, match="Load not found"):
            services.update_visibility_notes("FAKE", customer_note="test")


# ── API: PATCH /milestones/<id> ───────────────────────────────────


class TestMilestoneValidationAPI:
    def test_validate_milestone(self, client, load_with_milestone):
        _, ms = load_with_milestone
        resp = client.patch(
            f"/api/dispatch/milestones/{ms['milestone_id']}",
            json={"validation_status": "validated"},
        )
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["milestone"]["validation_status"] == "validated"

    def test_dispute_milestone(self, client, load_with_milestone):
        _, ms = load_with_milestone
        resp = client.patch(
            f"/api/dispatch/milestones/{ms['milestone_id']}",
            json={"validation_status": "disputed"},
        )
        assert resp.get_json()["milestone"]["validation_status"] == "disputed"

    def test_invalid_status_400(self, client, load_with_milestone):
        _, ms = load_with_milestone
        resp = client.patch(
            f"/api/dispatch/milestones/{ms['milestone_id']}",
            json={"validation_status": "approved"},
        )
        assert resp.status_code == 400

    def test_nonexistent_milestone_404(self, client):
        resp = client.patch(
            "/api/dispatch/milestones/MS-FAKE",
            json={"validation_status": "validated"},
        )
        assert resp.status_code == 404

    def test_no_validation_status_404(self, client):
        resp = client.patch(
            "/api/dispatch/milestones/MS-FAKE",
            json={},
        )
        assert resp.status_code == 404


# ── API: PATCH /loads/<id>/visibility ─────────────────────────────


class TestVisibilityNotesAPI:
    def test_update_customer_note(self, client, load_with_milestone):
        load, _ = load_with_milestone
        resp = client.patch(
            f"/api/dispatch/loads/{load['load_id']}/visibility",
            json={"customer_note": "Weather delay"},
        )
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["visibility"]["customer_note"] == "Weather delay"

    def test_update_both_notes(self, client, load_with_milestone):
        load, _ = load_with_milestone
        resp = client.patch(
            f"/api/dispatch/loads/{load['load_id']}/visibility",
            json={"customer_note": "ETA 3pm", "internal_note": "Driver resting"},
        )
        data = resp.get_json()
        assert data["visibility"]["customer_note"] == "ETA 3pm"
        assert data["visibility"]["internal_note"] == "Driver resting"

    def test_load_not_found_404(self, client):
        resp = client.patch(
            "/api/dispatch/loads/FAKE/visibility",
            json={"customer_note": "test"},
        )
        assert resp.status_code == 404


# ── Template rendering ────────────────────────────────────────────


class TestMilestoneValidationUI:
    def test_validation_column_present(self, client, load_with_milestone):
        load, _ = load_with_milestone
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert ">Validation<" in html

    def test_pending_badge_shown(self, client, load_with_milestone):
        load, _ = load_with_milestone
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "validation-pending" in html

    def test_validate_button_shown(self, client, load_with_milestone):
        load, _ = load_with_milestone
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Validate</button>" in html

    def test_dispute_button_shown(self, client, load_with_milestone):
        load, _ = load_with_milestone
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Dispute</button>" in html

    def test_validated_badge_shown(self, client, load_with_milestone):
        load, ms = load_with_milestone
        services.validate_milestone(ms["milestone_id"], "validated")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "validation-validated" in html

    def test_visibility_notes_textarea(self, client, load_with_milestone):
        load, _ = load_with_milestone
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "vis-customer-note" in html
        assert "vis-internal-note" in html
        assert "Save Notes" in html

    def test_visibility_notes_prefilled(self, client, load_with_milestone):
        load, _ = load_with_milestone
        services.update_visibility_notes(
            load["load_id"], customer_note="Delayed"
        )
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Delayed" in html
