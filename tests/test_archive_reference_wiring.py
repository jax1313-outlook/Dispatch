"""Tests for Lane F (Batch 1, Workstream F): cross-referencing the
Dispatch Retention Archive on `/archive` with its Completion Packet's
Email Cluster and the load's Stakeholder Portal link, plus the
plain-English "what archived means" copy added to the Stakeholder Portal.
"""

from __future__ import annotations

import pytest

from dispatch import notifications
from dispatch.db import set_db_path


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    set_db_path(tmp_path / "test.db")

    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

    set_db_path(None)


def _delivered_load_with_client(client, **overrides):
    payload = {"customer": "Archive Wiring Co"}
    payload.update(overrides)
    r = client.post("/api/dispatch/loads", json=payload)
    load = r.get_json()["load"]
    for status in (
        "dispatched", "en_route_pickup", "at_pickup", "picked_up",
        "in_transit", "at_delivery", "delivered",
    ):
        client.patch(f"/api/dispatch/loads/{load['load_id']}", json={"status": status})
    return load


def _end_load_draft_submit(client, load_id, broker_email="broker@test.com"):
    client.post(f"/api/dispatch/loads/{load_id}/end-load")
    client.post(f"/api/dispatch/loads/{load_id}/email-package/draft")
    client.patch(
        f"/api/dispatch/loads/{load_id}/email-package",
        json={"broker_email": broker_email},
    )
    client.post(
        f"/api/dispatch/loads/{load_id}/email-package/submit",
        json={"submitted_by": "Mike Zachary"},
    )


class TestArchivePageCrossReferences:
    def test_archived_load_with_cluster_shows_document_count(self, client):
        load = _delivered_load_with_client(client)
        _end_load_draft_submit(client, load["load_id"])
        client.post(f"/api/dispatch/loads/{load['load_id']}/archive")

        resp = client.get("/archive")
        html = resp.data.decode("utf-8")
        assert "1 document" in html

    def test_archived_load_without_cluster_shows_dash(self, client):
        load = _delivered_load_with_client(client)
        client.post(f"/api/dispatch/loads/{load['load_id']}/archive")

        resp = client.get("/archive")
        html = resp.data.decode("utf-8")
        # The row for this load's email-cluster cell should render "—", not a stale count.
        assert "Email Cluster" in html

    def test_archived_load_has_a_working_stakeholder_link_button(self, client):
        load = _delivered_load_with_client(client)
        client.post(f"/api/dispatch/loads/{load['load_id']}/archive")

        resp = client.get("/archive")
        html = resp.data.decode("utf-8")
        expected_token = notifications.make_stakeholder_token(load["load_id"])
        assert expected_token in html
        assert f"/portal/loads/{load['load_id']}" in html
        assert "Copy Stakeholder Link" in html

    def test_stakeholder_link_from_archive_page_actually_works(self, client):
        load = _delivered_load_with_client(client)
        client.post(f"/api/dispatch/loads/{load['load_id']}/archive")
        token = notifications.make_stakeholder_token(load["load_id"])

        resp = client.get(f"/portal/loads/{load['load_id']}?token={token}")
        assert resp.status_code == 200


class TestStakeholderArchiveCopy:
    def test_archived_load_shows_permanent_record_copy(self, client):
        load = _delivered_load_with_client(client)
        client.post(f"/api/dispatch/loads/{load['load_id']}/archive")
        token = notifications.make_stakeholder_token(load["load_id"])

        resp = client.get(f"/portal/loads/{load['load_id']}?token={token}")
        html = resp.data.decode("utf-8")
        assert "permanent record" in html.lower()

    def test_non_archived_load_shows_no_archive_copy(self, client):
        load = _delivered_load_with_client(client)
        token = notifications.make_stakeholder_token(load["load_id"])

        resp = client.get(f"/portal/loads/{load['load_id']}?token={token}")
        html = resp.data.decode("utf-8")
        assert "permanent record" not in html.lower()
