"""Tests for activity feed filtering."""

from __future__ import annotations

import os

import pytest

from dispatch import services
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture()
def app():
    os.environ.setdefault("SECRET_KEY", "test")
    from portal.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def load_with_activities():
    load = services.create_load(customer="Filter Test Co")
    services.add_activity(load["load_id"], "Test comment", activity_type="comment", author="tester")
    services.add_activity(load["load_id"], "Status to dispatched", activity_type="status_change")
    services.add_activity(load["load_id"], "Assigned driver", activity_type="assignment")
    services.add_activity(load["load_id"], "Auto-generated event", activity_type="system")
    services.add_activity(load["load_id"], "Second comment", activity_type="comment", author="tester")
    return load


# ── Service layer tests ──────────────────────────────────────────────


def test_list_activities_no_filter(load_with_activities):
    load = load_with_activities
    items = services.list_activities(load["load_id"])
    assert len(items) == 5


def test_list_activities_filter_comment(load_with_activities):
    load = load_with_activities
    items = services.list_activities(load["load_id"], activity_type="comment")
    assert len(items) == 2
    assert all(a["activity_type"] == "comment" for a in items)


def test_list_activities_filter_status_change(load_with_activities):
    load = load_with_activities
    items = services.list_activities(load["load_id"], activity_type="status_change")
    assert len(items) == 1
    assert items[0]["activity_type"] == "status_change"


def test_list_activities_filter_assignment(load_with_activities):
    load = load_with_activities
    items = services.list_activities(load["load_id"], activity_type="assignment")
    assert len(items) == 1


def test_list_activities_filter_system(load_with_activities):
    load = load_with_activities
    items = services.list_activities(load["load_id"], activity_type="system")
    assert len(items) == 1


def test_list_activities_filter_returns_empty_for_no_match():
    load = services.create_load(customer="Empty Co")
    items = services.list_activities(load["load_id"], activity_type="comment")
    assert items == []


# ── API tests ────────────────────────────────────────────────────────


def test_api_activities_no_filter(client, load_with_activities):
    load = load_with_activities
    r = client.get(f"/api/dispatch/loads/{load['load_id']}/activities")
    assert r.status_code == 200
    assert len(r.get_json()) == 5


def test_api_activities_filter_comment(client, load_with_activities):
    load = load_with_activities
    r = client.get(f"/api/dispatch/loads/{load['load_id']}/activities?type=comment")
    assert r.status_code == 200
    data = r.get_json()
    assert len(data) == 2
    assert all(a["activity_type"] == "comment" for a in data)


def test_api_activities_filter_system(client, load_with_activities):
    load = load_with_activities
    r = client.get(f"/api/dispatch/loads/{load['load_id']}/activities?type=system")
    assert r.status_code == 200
    assert len(r.get_json()) == 1


def test_api_activities_invalid_type(client, load_with_activities):
    load = load_with_activities
    r = client.get(f"/api/dispatch/loads/{load['load_id']}/activities?type=bogus")
    assert r.status_code == 400
    assert "Invalid type" in r.get_json()["error"]


def test_api_activities_filter_not_found(client):
    r = client.get("/api/dispatch/loads/nonexistent/activities?type=comment")
    assert r.status_code == 404


# ── Template tests ───────────────────────────────────────────────────


def test_detail_page_has_filter_buttons(client, load_with_activities):
    load = load_with_activities
    r = client.get(f"/dispatch/{load['load_id']}")
    html = r.data.decode()
    assert 'id="activity-filters"' in html
    assert "filterActivities('comment')" in html
    assert "filterActivities('status_change')" in html
    assert "filterActivities('assignment')" in html
    assert "filterActivities('system')" in html
    assert "filterActivities('all')" in html


def test_detail_page_activity_items_have_data_type(client, load_with_activities):
    load = load_with_activities
    r = client.get(f"/dispatch/{load['load_id']}")
    html = r.data.decode()
    assert 'data-type="comment"' in html
    assert 'data-type="status_change"' in html
    assert 'data-type="assignment"' in html
    assert 'data-type="system"' in html


def test_detail_page_has_filter_js(client, load_with_activities):
    load = load_with_activities
    r = client.get(f"/dispatch/{load['load_id']}")
    html = r.data.decode()
    assert "function filterActivities" in html
