"""What a person wrote for the customer stays written.

**BATCH 6.** Four places built a `LoadVisibilityRecord` from scratch and wrote
it over the old one. Two carried `customer_note` and `internal_note` across;
**two did not.** So a note Operations wrote for a customer survived exactly
until the driver tapped his next milestone, then vanished -- no trace, nobody
told. Archiving dropped them again, and `next_expected_milestone` with them.

The bug was never in any one of the four. It was that one act had four
hand-written copies, so a field reached whichever of them somebody remembered.

And the other half: `update_load` wrote the `loads` row and never touched
visibility at all, so a status advanced from the Dispatch screen showed the new
state to the office and the old one to the customer, indefinitely.
"""

from __future__ import annotations

import pytest

from dispatch import services, store

NOTE = "Driver is running two hours behind. Receiver has been called."
INTERNAL = "Broker slow to answer. Chase before 16:00."


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    from dispatch import db

    db.set_db_path(tmp_path / "dispatch.db")
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    yield
    db.set_db_path(None)


@pytest.fixture()
def noted():
    """A running load carrying a note somebody wrote by hand."""
    load = services.create_load(customer="Penske Logistics",
                                pickup_location="Jacksonville, FL",
                                delivery_location="Savannah, GA")
    lid = load["load_id"]
    services.add_milestone(lid, "dispatched")
    services.update_visibility_notes(lid, customer_note=NOTE, internal_note=INTERNAL)
    assert services.get_visibility(lid)["customer_note"] == NOTE
    return lid


def _notes(load_id):
    vis = store.get_visibility(load_id) or {}
    return vis.get("customer_note", ""), vis.get("internal_note", "")


class TestAMilestoneDoesNotEraseIt:
    def test_the_customer_note_survives_one_milestone(self, noted):
        """The defect, at its plainest."""
        services.add_milestone(noted, "en_route_pickup")

        assert _notes(noted)[0] == NOTE

    def test_the_internal_note_survives_too(self, noted):
        services.add_milestone(noted, "en_route_pickup")

        assert _notes(noted)[1] == INTERNAL

    def test_it_survives_the_whole_run(self, noted):
        """Not one milestone -- every one of them, which is the way a driver
        actually works a load."""
        for event in ("en_route_pickup", "arrived_pickup", "loaded",
                      "departed_pickup", "arrived_delivery", "delivered"):
            services.add_milestone(noted, event)

        assert _notes(noted) == (NOTE, INTERNAL)

    def test_the_milestone_still_does_its_own_job(self, noted):
        services.add_milestone(noted, "en_route_pickup")

        vis = store.get_visibility(noted)
        assert vis["current_status"] == "en_route_pickup"
        assert vis["last_milestone"] == "en_route_pickup"


class TestNorDoesAnythingElse:
    def test_an_exception_keeps_it(self, noted):
        services.open_exception(noted, description="Dock closed", severity="high")

        assert _notes(noted) == (NOTE, INTERNAL)

    def test_resolving_an_exception_keeps_it(self, noted):
        exc = services.open_exception(noted, description="Dock closed")
        services.resolve_exception(exc["exception_id"], resolution_note="Reopened")

        assert _notes(noted) == (NOTE, INTERNAL)

    def test_retention_keeps_it(self, noted):
        """*"Archive performs retention."* Retaining a record is not a reason
        to discard the part of it a person wrote."""
        from tests.conftest import close_the_file

        for event in ("en_route_pickup", "arrived_pickup", "loaded",
                      "departed_pickup", "arrived_delivery", "delivered"):
            services.add_milestone(noted, event)
        close_the_file(noted, by="operations")
        services.archive_load(noted)

        assert _notes(noted) == (NOTE, INTERNAL)

    def test_retention_keeps_the_next_step_too(self, noted):
        """Archiving dropped `next_expected_milestone` as well."""
        from tests.conftest import close_the_file

        for event in ("en_route_pickup", "arrived_pickup", "loaded",
                      "departed_pickup", "arrived_delivery", "delivered"):
            services.add_milestone(noted, event)
        before = store.get_visibility(noted)["next_expected_milestone"]
        close_the_file(noted, by="operations")
        services.archive_load(noted)

        assert store.get_visibility(noted)["next_expected_milestone"] == before


class TestTheCustomerIsNotToldTheOldStory:
    def test_update_load_refreshes_visibility(self, noted):
        """`update_load` wrote the load row and left visibility behind, so the
        office and the customer read different states with nothing saying which
        was true."""
        services.update_load(noted, status="en_route_pickup")

        assert store.get_visibility(noted)["current_status"] == "en_route_pickup"

    def test_and_still_keeps_the_note(self, noted):
        services.update_load(noted, status="en_route_pickup")

        assert _notes(noted) == (NOTE, INTERNAL)

    def test_a_field_that_is_not_the_status_changes_nothing_else(self, noted):
        services.update_load(noted, notes="Reweighed at the scale")

        vis = store.get_visibility(noted)
        assert vis["current_status"] == "dispatched"
        assert vis["customer_note"] == NOTE


class TestOneOperation:
    def test_visibility_is_written_in_one_place(self):
        """The fix is not four careful copies -- it is one operation. A field
        added to the record must not depend on somebody remembering four
        sites."""
        source = open("dispatch/services.py", encoding="utf-8").read()

        assert source.count("store.upsert_visibility(") <= 2, (
            "visibility is being written from more than the one place that "
            "carries everything forward")

    def test_a_caller_that_says_nothing_about_the_notes_keeps_them(self, noted):
        services.refresh_visibility(noted, current_status="in_transit")

        assert _notes(noted) == (NOTE, INTERNAL)

    def test_a_caller_can_still_change_a_note_on_purpose(self, noted):
        services.update_visibility_notes(noted, customer_note="Delivered early.")

        assert _notes(noted)[0] == "Delivered early."
