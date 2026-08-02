"""Tests for load activity / comment thread."""

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
def load():
    return services.create_load(customer="Activity Test Corp")


# ── Model ───────────────────────────────────────────────────────────


class TestActivityModel:
    def test_activity_id_generated(self):
        from dispatch.models import LoadActivity
        act = LoadActivity(load_id="LOAD-X", message="hello")
        assert act.activity_id.startswith("ACT-")

    def test_default_type_is_comment(self):
        from dispatch.models import LoadActivity
        act = LoadActivity(load_id="LOAD-X", message="hello")
        assert act.activity_type == "comment"

    def test_invalid_type_raises(self):
        from dispatch.models import LoadActivity
        with pytest.raises(ValueError, match="activity_type"):
            LoadActivity(load_id="LOAD-X", activity_type="invalid")

    def test_invalid_source_raises(self):
        from dispatch.models import LoadActivity
        with pytest.raises(ValueError, match="source"):
            LoadActivity(load_id="LOAD-X", source="alien")


# ── Store ───────────────────────────────────────────────────────────


class TestActivityStore:
    def test_create_and_list(self, load):
        from dispatch import store
        from dispatch.models import LoadActivity
        act = LoadActivity(load_id=load["load_id"], message="Test note")
        result = store.create_activity(act)
        assert result["message"] == "Test note"
        activities = store.list_activities(load["load_id"])
        assert len(activities) == 1
        assert activities[0]["activity_id"] == result["activity_id"]

    def test_list_returns_newest_first(self, load):
        from dispatch import store
        from dispatch.models import LoadActivity
        store.create_activity(LoadActivity(
            load_id=load["load_id"], message="first",
            created_at="2025-01-01T00:00:00Z",
        ))
        store.create_activity(LoadActivity(
            load_id=load["load_id"], message="second",
            created_at="2025-01-02T00:00:00Z",
        ))
        activities = store.list_activities(load["load_id"])
        assert activities[0]["message"] == "second"
        assert activities[1]["message"] == "first"

    def test_delete_activity(self, load):
        from dispatch import store
        from dispatch.models import LoadActivity
        act = store.create_activity(LoadActivity(load_id=load["load_id"], message="to delete"))
        assert store.delete_activity(act["activity_id"])
        assert len(store.list_activities(load["load_id"])) == 0

    def test_delete_nonexistent_returns_false(self):
        from dispatch import store
        assert not store.delete_activity("ACT-NOPE")

    def test_cascade_delete_with_load(self, load):
        from dispatch import store
        from dispatch.models import LoadActivity
        store.create_activity(LoadActivity(load_id=load["load_id"], message="will cascade"))
        store.delete_load(load["load_id"])
        assert len(store.list_activities(load["load_id"])) == 0


# ── Service ─────────────────────────────────────────────────────────


class TestActivityService:
    def test_add_comment(self, load):
        act = services.add_activity(load["load_id"], "Hello from service")
        assert act["activity_type"] == "comment"
        assert act["message"] == "Hello from service"

    def test_add_with_author(self, load):
        act = services.add_activity(load["load_id"], "Noted", author="Jane")
        assert act["author"] == "Jane"

    def test_add_to_nonexistent_load_raises(self):
        with pytest.raises(ValueError, match="not found"):
            services.add_activity("LOAD-NOPE", "oops")

    def test_list_activities(self, load):
        services.add_activity(load["load_id"], "one")
        services.add_activity(load["load_id"], "two")
        result = services.list_activities(load["load_id"])
        assert len(result) == 2

    def test_delete_activity(self, load):
        act = services.add_activity(load["load_id"], "bye")
        assert services.delete_activity(act["activity_id"])

    def test_status_change_auto_logs(self, load):
        services.update_load(load["load_id"], status="dispatched")
        activities = services.list_activities(load["load_id"])
        status_acts = [a for a in activities if a["activity_type"] == "status_change"]
        assert len(status_acts) == 1
        assert "created" in status_acts[0]["message"]
        assert "dispatched" in status_acts[0]["message"]

    def test_bundle_includes_activities(self, load):
        services.add_activity(load["load_id"], "bundle test")
        bundle = services.get_load_bundle(load["load_id"])
        assert "activities" in bundle
        assert len(bundle["activities"]) == 1


# ── API ─────────────────────────────────────────────────────────────


class TestActivityAPI:
    def test_post_comment(self, client, load):
        resp = client.post(
            f"/api/dispatch/loads/{load['load_id']}/activities",
            json={"message": "API comment", "author": "Tester"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["message"] == "API comment"
        assert data["author"] == "Tester"

    def test_post_empty_message_rejected(self, client, load):
        resp = client.post(
            f"/api/dispatch/loads/{load['load_id']}/activities",
            json={"message": ""},
        )
        assert resp.status_code == 400

    def test_post_invalid_type_rejected(self, client, load):
        resp = client.post(
            f"/api/dispatch/loads/{load['load_id']}/activities",
            json={"message": "x", "activity_type": "nope"},
        )
        assert resp.status_code == 400

    def test_post_to_nonexistent_load(self, client):
        resp = client.post(
            "/api/dispatch/loads/LOAD-NOPE/activities",
            json={"message": "x"},
        )
        assert resp.status_code == 404

    def test_list_activities(self, client, load):
        services.add_activity(load["load_id"], "listed")
        resp = client.get(f"/api/dispatch/loads/{load['load_id']}/activities")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1

    def test_delete_activity(self, client, load):
        act = services.add_activity(load["load_id"], "to remove")
        resp = client.delete(f"/api/dispatch/activities/{act['activity_id']}")
        assert resp.status_code == 200

    def test_delete_nonexistent_activity(self, client):
        resp = client.delete("/api/dispatch/activities/ACT-NOPE")
        assert resp.status_code == 404


# ── UI ──────────────────────────────────────────────────────────────


class TestActivityUI:
    def test_activity_section_present(self, client, load):
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Activity" in html
        assert 'name="message"' in html
        assert "Add a comment" in html

    def test_comment_displayed(self, client, load):
        services.add_activity(load["load_id"], "Visible comment", author="Bob")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Visible comment" in html
        assert "Bob" in html

    def test_status_change_displayed(self, client, load):
        services.update_load(load["load_id"], status="dispatched")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Status Change" in html

    def test_remove_button_on_comments(self, client, load):
        services.add_activity(load["load_id"], "removable")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "deleteComment" in html

    def test_activity_css_present(self, client):
        resp = client.get("/static/style.css")
        css = resp.data.decode()
        assert ".activity-thread" in css
        assert ".activity-item" in css
