"""Tests for D1: archive_load() enforces valid status transitions.

Covers the deployment decision register's D1 item: archive_load() previously
called store.update_load(load_id, status="archived") directly, bypassing
validate_status_transition() entirely, so a load could be "archived" from any
status at all. This adds the missing gate (and the "cancelled" -> "archived"
entry in _VALID_TRANSITIONS that a cancelled load needs to be archivable).

Scope: only archive_load()'s own status check plus the one _VALID_TRANSITIONS
entry. add_milestone()'s status-cascade logic is untouched (see CLAUDE.md /
the deployment blueprint's decision register -- that's a separate, not-yet
-attempted item referred to elsewhere as finding #5 / A1).
"""

from __future__ import annotations

import pytest

from dispatch import services as dispatch_svc
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture()
def load():
    return dispatch_svc.create_load(
        customer="Test Broker",
        broker_shipper="Test Broker",
        pickup_location="Jacksonville, FL",
        delivery_location="Savannah, GA",
    )


def _deliver(load_id: str) -> None:
    """Drive a load to "delivered" via the milestone cascade (untouched logic)."""
    dispatch_svc.add_milestone(load_id, "dispatched")
    dispatch_svc.add_milestone(load_id, "delivered")


def _complete(load_id: str) -> None:
    """Drive a load to "completed" via the milestone cascade (untouched logic)."""
    _deliver(load_id)
    dispatch_svc.add_milestone(load_id, "completed")


# ── cancelled -> archived is now allowed ────────────────────────────────


class TestCancelledCanArchive:
    def test_validate_status_transition_allows_cancelled_to_archived(self):
        # Direct check of the transition table entry itself.
        dispatch_svc.validate_status_transition("cancelled", "archived")

    def test_archive_load_succeeds_from_cancelled(self, load):
        load_id = load["load_id"]
        dispatch_svc.update_load(load_id, status="cancelled")
        assert dispatch_svc.get_load(load_id)["status"] == "cancelled"

        ret = dispatch_svc.archive_load(load_id)

        assert ret["load_id"] == load_id
        assert ret["final_status"] == "cancelled"
        assert dispatch_svc.get_load(load_id)["status"] == "archived"


# ── archiving from a disallowed source status is now rejected ──────────


class TestArchiveRejectsInvalidSourceStatus:
    def test_archive_load_from_created_raises(self, load):
        # "created" only allows -> {"dispatched", "cancelled"}; "archived" is
        # not reachable directly, so this must fail loudly rather than
        # silently succeed the way the old, unvalidated archive_load() did.
        load_id = load["load_id"]
        with pytest.raises(ValueError, match="Invalid status transition"):
            dispatch_svc.archive_load(load_id)
        assert dispatch_svc.get_load(load_id)["status"] == "created"
        assert dispatch_svc.get_retention(load_id) is None

    def test_archive_load_from_dispatched_raises(self, load):
        # "dispatched" only allows -> {"en_route_pickup", "cancelled"}.
        load_id = load["load_id"]
        dispatch_svc.update_load(load_id, status="dispatched")
        with pytest.raises(ValueError, match="Invalid status transition"):
            dispatch_svc.archive_load(load_id)
        assert dispatch_svc.get_load(load_id)["status"] == "dispatched"
        assert dispatch_svc.get_retention(load_id) is None

    def test_archive_load_from_picked_up_raises(self, load):
        # "picked_up" only allows -> {"in_transit"}.
        load_id = load["load_id"]
        dispatch_svc.add_milestone(load_id, "dispatched")
        dispatch_svc.add_milestone(load_id, "loaded")  # -> "picked_up"
        assert dispatch_svc.get_load(load_id)["status"] == "picked_up"
        with pytest.raises(ValueError, match="Invalid status transition"):
            dispatch_svc.archive_load(load_id)
        assert dispatch_svc.get_load(load_id)["status"] == "picked_up"
        assert dispatch_svc.get_retention(load_id) is None


# ── previously-allowed archive paths still work unchanged ──────────────


class TestArchiveStillWorksFromAllowedStatuses:
    def test_archive_load_from_delivered_still_succeeds(self, load):
        load_id = load["load_id"]
        _deliver(load_id)
        assert dispatch_svc.get_load(load_id)["status"] == "delivered"

        ret = dispatch_svc.archive_load(load_id)

        assert ret["load_id"] == load_id
        assert ret["final_status"] == "delivered"
        assert dispatch_svc.get_load(load_id)["status"] == "archived"

    def test_archive_load_from_completed_still_succeeds(self, load):
        load_id = load["load_id"]
        _complete(load_id)
        assert dispatch_svc.get_load(load_id)["status"] == "completed"

        ret = dispatch_svc.archive_load(load_id)

        assert ret["load_id"] == load_id
        assert ret["final_status"] == "completed"
        assert dispatch_svc.get_load(load_id)["status"] == "archived"
