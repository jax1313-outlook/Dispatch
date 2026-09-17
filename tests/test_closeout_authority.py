"""Retiring a load is one act, and it has one operation.

**Mike Zachary, 2026-09-17:** *"closeout is mine at a desk."* So there is a
control, and it is his — and there must be exactly one, because the act files
a retention record and a status written on its own files nothing.

Three doors reached `archived`:

    PATCH /api/dispatch/loads/<id>        {"status": "archived"}   the Advance row
    POST  /api/dispatch/loads/batch-status                         the list control
    POST  /api/dispatch/loads/<id>/archive                         Archive Load

**Only the third filed anything.** The first two ran through `update_load`,
which validated the transition and wrote the status, so a load could be retired
with no retention record, no evidence index, no `archived_at` and no path to
its closing packet: gone from every active list, with nothing anywhere saying
it had ever been archived.

The primary rule, from the reconciliation brief: *"Each consequential business
act shall have one authoritative operation. Every screen, API route, helper,
and test representing that act must call the same authoritative operation."*
"""

from __future__ import annotations

import pytest

from dispatch import services, store


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    monkeypatch.setenv("DISPATCH_DB_PATH", str(tmp_path / "dispatch.db"))

    from dispatch import scheduling

    monkeypatch.setattr(scheduling, "_outlook_is_running", lambda: False)
    yield


@pytest.fixture()
def client():
    from portal.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as s:
            s["user_id"] = "mike"
        yield c


@pytest.fixture()
def delivered():
    """A load that has run and been delivered, ready for the desk."""
    load = services.create_load(
        customer="Penske Logistics", pickup_location="Jacksonville, FL",
        delivery_location="Savannah, GA")
    lid = load["load_id"]
    for event in ("en_route_pickup", "arrived_pickup", "loaded",
                  "departed_pickup", "arrived_delivery", "delivered"):
        services.add_milestone(lid, event_type=event, source="driver",
                               entered_by="driver:test")
    assert store.get_load(lid)["status"] == "delivered"
    return lid


class TestTheBypassesAreClosed:
    def test_the_advance_button_cannot_archive(self, client, delivered):
        """The defect: this wrote `archived` and filed nothing."""
        answer = client.patch("/api/dispatch/loads/%s" % delivered,
                              json={"status": "archived"})

        assert answer.status_code >= 400
        assert store.get_load(delivered)["status"] == "delivered"

    def test_it_says_which_operation_owns_the_act(self, client, delivered):
        """A refusal nobody can act on is a dead end."""
        answer = client.patch("/api/dispatch/loads/%s" % delivered,
                              json={"status": "archived"})

        assert "archive_load" in answer.get_data(as_text=True)

    def test_the_batch_control_cannot_archive(self, client, delivered):
        """Worse than the single case: this retired loads by the handful."""
        answer = client.post("/api/dispatch/loads/batch-status",
                             json={"load_ids": [delivered], "status": "archived"})

        assert answer.get_json()["updated"] == 0
        assert store.get_load(delivered)["status"] == "delivered"

    def test_nothing_was_filed_by_the_refused_attempts(self, client, delivered):
        client.patch("/api/dispatch/loads/%s" % delivered, json={"status": "archived"})
        client.post("/api/dispatch/loads/batch-status",
                    json={"load_ids": [delivered], "status": "archived"})

        assert store.get_retention_by_load(delivered) is None

    def test_the_engine_refuses_it_directly_too(self, delivered):
        """**The glass is not authoritative.** Removing the button from the
        Advance row is presentation; this is the protection."""
        with pytest.raises(ValueError, match="archive_load"):
            services.update_load(delivered, status="archived")


class TestTheDoorThatWorks:
    @pytest.fixture()
    def reviewed(self, client, delivered):
        """Operations has closed the file. *"Driver completes the mission.
        Operations closes the file. Archive performs retention."* -- the middle
        act has to have happened before the third one can."""
        assert client.post("/api/dispatch/loads/%s/closeout" % delivered,
                           json={}).status_code == 200
        return delivered

    def test_archive_load_still_retires_it(self, client, reviewed):
        answer = client.post("/api/dispatch/loads/%s/archive" % reviewed)

        assert answer.status_code == 201
        assert store.get_load(reviewed)["status"] == "archived"

    def test_and_files_a_retention_record(self, client, reviewed):
        client.post("/api/dispatch/loads/%s/archive" % reviewed)

        retention = store.get_retention_by_load(reviewed)
        assert retention and retention["archived_at"]

    def test_a_load_that_never_delivered_is_still_refused(self, client):
        """The transition gate is unchanged. A load nobody worked cannot be
        retired as though it had run."""
        load = services.create_load(customer="Nobody", pickup_location="A",
                                    delivery_location="B")

        answer = client.post("/api/dispatch/loads/%s/archive" % load["load_id"])

        assert answer.status_code >= 400
        assert store.get_load(load["load_id"])["status"] == "created"


class TestTheGlassOffersOnlyTheRealDoor:
    def test_the_advance_row_does_not_offer_archived(self):
        """It offered a door the engine now refuses, which would read as a
        broken button rather than a rule."""
        page = open("portal/templates/dispatch_detail.html", encoding="utf-8").read()
        block = page.split("{% set transitions = {")[1].split("} %}")[0]

        assert "archived" not in block

    def test_archive_load_is_still_on_the_page(self):
        """*"closeout is mine at a desk."* The control he presses."""
        page = open("portal/templates/dispatch_detail.html", encoding="utf-8").read()

        assert "archiveLoad(" in page


class TestTheReviewIsTheGate:
    """**AUTHORITATIVE RULING, 2026-09-17:** *"The Archive gate is a
    reviewed-closeout gate, not a mechanical artifact gate ... The act being
    recorded is 'I reviewed this file.' not 'Every artifact exists.'"*"""

    def test_archive_refuses_a_file_nobody_reviewed(self, client, delivered):
        answer = client.post("/api/dispatch/loads/%s/archive" % delivered)

        assert answer.status_code >= 400
        assert store.get_retention_by_load(delivered) is None

    def test_it_says_who_has_to_act(self, client, delivered):
        answer = client.post("/api/dispatch/loads/%s/archive" % delivered)

        assert "closed out" in answer.get_data(as_text=True).lower()

    def test_a_reviewed_file_archives(self, client, delivered):
        client.post("/api/dispatch/loads/%s/closeout" % delivered, json={})

        answer = client.post("/api/dispatch/loads/%s/archive" % delivered)

        assert answer.status_code == 201

    def test_a_file_with_nothing_on_it_can_still_be_closed(self, client, delivered):
        """The ruling's whole point. This load has no POD, no BOL, no packet --
        and a mechanical gate would strand it for ever, which is exactly what
        the 2026-09-16 ruling refused: *"some loads genuinely end without a POD
        coming back."*"""
        from dispatch import closeout

        assert closeout.review(store.get_load(delivered))["missing"]

        answer = client.post("/api/dispatch/loads/%s/closeout" % delivered,
                             json={"note": "Broker never returned the POD. Accepted."})

        assert answer.status_code == 200
        assert client.post("/api/dispatch/loads/%s/archive" % delivered).status_code == 201

    def test_the_reason_is_kept(self, client, delivered):
        client.post("/api/dispatch/loads/%s/closeout" % delivered,
                    json={"note": "Broker never returned the POD."})

        assert store.get_load(delivered)["closeout_note"] == "Broker never returned the POD."

    def test_who_looked_and_when_are_kept(self, client, delivered):
        client.post("/api/dispatch/loads/%s/closeout" % delivered, json={})

        load = store.get_load(delivered)
        assert load["closed_out_at"] and load["closed_out_by"] == "mike"

    def test_a_file_is_reviewed_once(self, client, delivered):
        """A closeout that can be overwritten is not a record of who looked."""
        client.post("/api/dispatch/loads/%s/closeout" % delivered, json={})

        answer = client.post("/api/dispatch/loads/%s/closeout" % delivered, json={})

        assert answer.status_code == 409

    def test_an_unfinished_mission_cannot_be_closed(self, client):
        """*"Archive eligibility therefore depends upon: Mission completion."*"""
        load = services.create_load(customer="Still running", pickup_location="A",
                                    delivery_location="B")

        answer = client.post("/api/dispatch/loads/%s/closeout" % load["load_id"],
                             json={})

        assert answer.status_code == 409


class TestTheQueueIsVisible:
    def test_a_finished_mission_is_waiting_on_operations(self, client, delivered):
        page = client.get("/closeout").get_data(as_text=True)

        assert delivered in page or "Waiting on review" in page

    def test_it_prints_what_is_missing(self, client, delivered):
        page = client.get("/closeout").get_data(as_text=True)

        assert "Signed POD" in page

    def test_a_reviewed_file_moves_to_awaiting_archive(self, client, delivered):
        client.post("/api/dispatch/loads/%s/closeout" % delivered, json={})

        page = client.get("/closeout").get_data(as_text=True)

        assert "awaiting Archive" in page

    def test_an_archived_mission_leaves_the_queue(self, client, delivered):
        from dispatch import closeout

        client.post("/api/dispatch/loads/%s/closeout" % delivered, json={})
        client.post("/api/dispatch/loads/%s/archive" % delivered)

        assert closeout.queue(services.list_loads()) == []

    def test_closeout_is_on_the_operations_nav(self):
        """Work waiting on a person that no screen shows is work nobody does."""
        page = open("portal/templates/base.html", encoding="utf-8").read()

        assert "pages.closeout_queue" in page


class TestTheReviewOnlyReports:
    def test_it_refuses_nothing(self, delivered):
        """`review()` decides nothing -- `close_file` is the act and
        `is_closed_out` is the gate."""
        from dispatch import closeout

        report = closeout.review(store.get_load(delivered))

        assert set(report) >= {"present", "missing", "packet", "closed_out"}
        assert report["closed_out"] is False

    def test_the_bol_is_listed_even_though_nothing_can_supply_one_yet(self):
        """The BOL is the controlling freight document and has no upload route
        until BATCH 8. Listed rather than hidden, because a missing artifact
        nobody can see is one nobody chases."""
        from dispatch import closeout

        assert "bol" in [kind for kind, _ in closeout.ARTIFACTS]
