"""Tests for D10: Email Archive Handling.

'Email Sent -> Render Email to Business Document -> Attach Related Files -> Create Email
Cluster -> Store With Completion Package -> Archive Takes Custody.' Covers cluster creation
on Submit, custody cross-referencing on Archive Load, and that Archive Load's own trigger
condition (a human clicking the button) is unchanged.
"""

from __future__ import annotations

import pytest

from dispatch import services
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
    payload = {"customer": "D10 Co"}
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
    resp = client.post(
        f"/api/dispatch/loads/{load_id}/email-package/submit",
        json={"submitted_by": "Mike Zachary"},
    )
    return resp.get_json()["package"]


# ── portal.models.completion_packet email cluster / custody ────────────


class TestEmailCluster:
    def test_create_email_cluster_renders_broker_document(self, client):
        from portal.models import completion_packet
        load = _delivered_load_with_client(client)
        package = _end_load_draft_submit(client, load["load_id"])
        packet = completion_packet.get_packet(load["load_id"])
        assert packet["status"] == "CLUSTERED"
        docs = packet["email_cluster"]["documents"]
        assert len(docs) == 1
        assert docs[0]["type"] == "broker_email"
        assert docs[0]["to"] == "broker@test.com"
        assert docs[0]["send_result"] is not None

    def test_cluster_attaches_related_files(self, client):
        from portal.models import completion_packet
        load = _delivered_load_with_client(client)
        client.post(f"/api/dispatch/loads/{load['load_id']}/rate", json={"rate_amount": 500})
        client.post(f"/api/dispatch/loads/{load['load_id']}/pod", json={})
        _end_load_draft_submit(client, load["load_id"])
        packet = completion_packet.get_packet(load["load_id"])
        attached = packet["email_cluster"]["attached_files"]
        assert attached["pod_id"] is not None

    def test_cluster_creation_is_idempotent(self, client):
        from portal.models import completion_packet
        load = _delivered_load_with_client(client)
        package = _end_load_draft_submit(client, load["load_id"])
        first = completion_packet.get_packet(load["load_id"])["email_cluster"]
        completion_packet.create_email_cluster(load["load_id"], package)
        second = completion_packet.get_packet(load["load_id"])["email_cluster"]
        assert first["created_at"] == second["created_at"]

    def test_draft_or_reviewed_package_is_not_clustered(self, client):
        from portal.models import completion_packet
        load = _delivered_load_with_client(client)
        client.post(f"/api/dispatch/loads/{load['load_id']}/end-load")
        client.post(f"/api/dispatch/loads/{load['load_id']}/email-package/draft")
        packet = completion_packet.get_packet(load["load_id"])
        assert packet["status"] == "ROUTED"
        assert packet["email_cluster"] is None


class TestArchiveCustody:
    def test_archive_load_marks_custody_when_clustered(self, client):
        from portal.models import completion_packet
        load = _delivered_load_with_client(client)
        _end_load_draft_submit(client, load["load_id"])

        resp = client.post(f"/api/dispatch/loads/{load['load_id']}/archive")
        assert resp.status_code == 201
        packet = completion_packet.get_packet(load["load_id"])
        assert packet["status"] == "ARCHIVED"
        assert packet["retention_archive_id"] == resp.get_json()["retention"]["archive_id"]

    def test_archive_load_without_cluster_leaves_packet_alone(self, client):
        from portal.models import completion_packet
        load = _delivered_load_with_client(client)
        client.post(f"/api/dispatch/loads/{load['load_id']}/end-load")  # ROUTED, no cluster

        resp = client.post(f"/api/dispatch/loads/{load['load_id']}/archive")
        assert resp.status_code == 201
        packet = completion_packet.get_packet(load["load_id"])
        assert packet["status"] == "ROUTED"
        assert packet["retention_archive_id"] is None

    def test_archive_load_without_any_completion_packet_still_works(self, client):
        load = _delivered_load_with_client(client)
        resp = client.post(f"/api/dispatch/loads/{load['load_id']}/archive")
        assert resp.status_code == 201

    def test_archive_load_trigger_is_still_manual(self, client):
        """Submitting the email package must not, by itself, archive the load."""
        load = _delivered_load_with_client(client)
        _end_load_draft_submit(client, load["load_id"])
        current = services.get_load(load["load_id"])
        assert current["status"] != "archived"
        assert services.get_retention(load["load_id"]) is None

    def test_mark_archived_is_idempotent(self, client):
        from portal.models import completion_packet
        load = _delivered_load_with_client(client)
        _end_load_draft_submit(client, load["load_id"])
        first = completion_packet.mark_archived(load["load_id"], "RET-0001")
        second = completion_packet.mark_archived(load["load_id"], "RET-0002")
        assert second["retention_archive_id"] == "RET-0001"  # not overwritten


class TestArchiveHandlingPage:
    def test_page_shows_cluster_before_archive(self, client):
        load = _delivered_load_with_client(client)
        _end_load_draft_submit(client, load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}")
        assert b"Email Cluster" in resp.data
        assert b"Awaiting Archive Load to take custody" in resp.data

    def test_page_shows_custody_after_archive(self, client):
        load = _delivered_load_with_client(client)
        _end_load_draft_submit(client, load["load_id"])
        client.post(f"/api/dispatch/loads/{load['load_id']}/archive")
        resp = client.get(f"/dispatch/{load['load_id']}")
        assert b"Archive has taken custody" in resp.data
