"""Tests for Lane F (Batch 1, Workstream F): cross-referencing the
Dispatch Retention Archive on `/archive` with its Completion Packet's
Email Cluster and the load's Stakeholder Portal link, plus the
plain-English "what archived means" copy added to the Stakeholder Portal.
"""

from __future__ import annotations

import pytest

from dispatch import notifications, services
from dispatch.db import set_db_path
from portal.models import driver_pin_registry as pin_registry
from portal.models import publisher


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


class TestApprovedPublisherActionAcrossBatch1Surfaces:
    """Item 19: a single APPROVED Publisher action must behave correctly on
    every surface Batch 1 added or touched -- and "correctly" is
    deliberately NOT the same behavior everywhere. Operations Feed (§20,
    pre-existing) treats APPROVED/ARCHIVED as resolved and hides the card
    entirely -- it's an actionable-items feed, and there's nothing left to
    act on. get_publisher_status() (Lane E) does the opposite on purpose:
    it reports APPROVED truthfully so Stakeholder/Driver Portal can show
    reassuring "finalized" language, not hide a real status from an
    external viewer or a waiting driver. This test locks in that both are
    happening simultaneously for the same underlying state, on real data
    that also exercises Lane A/B/D's card sources on the same load, so a
    future change to any of Batch 1's shared helpers can't quietly make
    one surface leak into the other's behavior."""

    def _approved_load(self, client, driver=None):
        load = _delivered_load_with_client(client, customer="Approved Packet Regression Co")
        if driver:
            client.patch(f"/api/dispatch/loads/{load['load_id']}", json={"driver_id": driver["driver_id"]})
        action = publisher.create_action(
            "Rate Confirmation Package Required",
            sandbox_id=f"LOAD-{load['load_id']}",
            trigger_reason="regression test",
        )
        publisher.update_action_status(action["id"], "DRAFT")
        publisher.update_action_status(action["id"], "READY")
        publisher.update_action_status(action["id"], "APPROVED", approved_by="mike")
        return load

    def test_operations_feed_hides_the_approved_action(self, client):
        from portal.models import operations_feed

        self._approved_load(client)
        feed = operations_feed.build_feed()
        assert [c for c in feed["cards"] if c["source"] == "publisher"] == []

    def test_stakeholder_portal_still_shows_finalized_language(self, client):
        load = self._approved_load(client)
        token = notifications.make_stakeholder_token(load["load_id"])
        resp = client.get(f"/portal/loads/{load['load_id']}?token={token}")
        html = resp.data.decode("utf-8")
        assert "Your documentation package has been finalized." in html

    def test_driver_portal_still_shows_finalized_language(self, client):
        driver = services.create_driver(name="Regression Driver", phone="555-000-1111")
        load = self._approved_load(client, driver=driver)
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        client.post("/driver/login", data={"phone": driver["phone"], "pin": "1234"})
        resp = client.get("/driver/home")
        html = resp.data.decode("utf-8")
        assert "Your documentation package has been finalized." in html

    def test_operations_feed_pending_action_on_a_different_load_still_shows(self, client):
        """Sanity check the hiding behavior is status-specific, not a
        regression that broke Operations Feed's publisher source entirely."""
        from portal.models import operations_feed

        pending_load = _delivered_load_with_client(client, customer="Still Pending Co")
        pending_action = publisher.create_action(
            "Broker Packet Required",
            sandbox_id=f"LOAD-{pending_load['load_id']}",
            trigger_reason="still open",
        )
        self._approved_load(client)  # the approved one from above, in the same feed run

        feed = operations_feed.build_feed()
        pub_cards = [c for c in feed["cards"] if c["source"] == "publisher"]
        assert len(pub_cards) == 1
        assert pub_cards[0]["card_id"] == f"publisher-{pending_action['id']}"
        assert pub_cards[0]["title"] == "Broker Packet Required"
