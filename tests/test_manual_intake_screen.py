"""Every source produces the same Mission Record.

    One Mission Template. Multiple intake methods. One Mission Record.
    One workflow.

A broker calling, a courier run phoned in, a shipper emailing direct, a text
message, an existing customer -- all of them arrive as a Mission Card, not as
special cases. The source is a **label on the record**, never a different kind
of mission: there is no courier form and no phone-load form.

The template itself was already built and already worked; what was missing was
the way in. Intake only ran from a Python prompt, which is not a way for a man
with a phone in his hand to open a load.
"""

from __future__ import annotations

import pytest

from dispatch import commitment, mission_template as mt
from portal.models import sandbox


COMPLETE = {
    "customer": "Baptist Health Logistics",
    "pickup_location": "Jacksonville, FL 32202",
    "pickup_window": "2026-09-08 07:00",
    "delivery_location": "Gainesville, FL 32608",
    "delivery_window": "2026-09-08 11:00",
    "commodity": "Medical specimens",
}


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    from dispatch import scheduling

    monkeypatch.setattr(scheduling, "_outlook_is_running", lambda: False)
    yield


@pytest.fixture()
def client():
    from portal.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _create(client, source="PHONE", **over):
    # What the page posts since the one-page layout, 2026-09-15: no Taken by.
    data = dict(COMPLETE, source=source, **over)
    return client.post("/intake", data=data, follow_redirects=False)


class TestTheFormNoLongerAsksHowItCameIn:
    """**Mike's analysis, 2026-09-06.** Six sources were rendered, validated and
    stored, and nothing in the program ever branched on one. He took the list
    apart: phone, email and text are methods of communication; JOE is a capture
    method with no contact with the outside world; courier and medical are
    freight types belonging on `service`.

    What survives is *did a machine find this, or did a customer bring it to
    me* -- and a person at this screen can only ever be the second. **A field
    with one reachable value is a field that should not be asked.**
    """

    def test_a_mission_opens_with_no_source_on_the_form(self, client):
        assert _create(client).status_code == 302
        records = list(sandbox.get_all().values())
        assert len(records) == 1
        assert commitment.state_of(records[0]) == commitment.CANDIDATE

    def test_the_record_sets_its_own_source(self, client):
        _create(client)
        record = list(sandbox.get_all().values())[0]
        assert record["card_data"]["source"] == mt.SOURCE_DIRECT.lower()

    def test_a_source_posted_by_hand_is_ignored_not_obeyed(self, client):
        """The field is gone from the screen. Anything still posting one --
        an old bookmark, a stale form, a script -- must not be able to label a
        hand-opened mission as a sweep."""
        _create(client, source="SWEEP")
        record = list(sandbox.get_all().values())[0]
        assert record["card_data"]["source"] == mt.SOURCE_DIRECT.lower()

    def test_the_chooser_is_gone_from_the_page(self, client):
        html = client.get("/intake").get_data(as_text=True)
        assert 'name="source"' not in html
        assert "HOW IT CAME IN" not in html
        # Who took it was a different question, asked until the one-page
        # layout of 2026-09-15 took it off the page.
        assert 'name="taken_by"' not in html
        assert "WHO TOOK IT" not in html

    def test_a_supplied_load_number_is_kept_exactly(self, client):
        _create(client, load_number="CVS-44912")
        record = list(sandbox.get_all().values())[0]
        assert record["load_number"] == "CVS-44912"

    def test_dispatch_numbers_work_nobody_else_numbered(self, client):
        _create(client)
        record = list(sandbox.get_all().values())[0]
        assert record["load_number"].startswith("L1-")
        assert record["card_data"]["load_id"] == ""

    def test_the_old_source_values_still_resolve(self, client):
        """Records stored before 2026-09-06 carry PHONE, TEXT, COURIER and the
        rest. They stay valid -- nothing was migrated and nothing was deleted."""
        for old_value in ("PHONE", "CUSTOMER", "COURIER", "EMAIL", "TEXT", "JOE"):
            assert old_value in mt.INTAKE_SOURCES


class TestItRefusesRatherThanLosingTheCall:
    def test_an_incomplete_load_is_not_created(self, client):
        response = client.post("/intake", data={"source": "PHONE",
                                                "customer": "Somebody"})
        assert response.status_code == 400
        assert sandbox.get_all() == {}

    def test_everything_typed_comes_back(self, client):
        """Losing a call's worth of notes to a validation message is how a
        screen stops being used."""
        response = client.post("/intake", data={
            "source": "PHONE",
            "customer": "Baptist Health Logistics",
            "notes": "Sally says detention after two hours"})
        html = response.get_data(as_text=True)
        assert "Baptist Health Logistics" in html
        assert "detention after two hours" in html

    def test_it_says_every_problem_not_the_first(self, client):
        html = client.post("/intake", data={"source": "PHONE"}).get_data(as_text=True)
        assert html.count("<li>") >= 4

    def test_it_no_longer_refuses_for_want_of_who_took_it(self, client):
        """Taken by left the page in the one-page layout, 2026-09-15, so the
        screen can no longer refuse a mission for it."""
        response = client.post("/intake", data=dict(COMPLETE, source="PHONE"))
        assert response.status_code == 302
        assert "Who took it" not in response.get_data(as_text=True)

    def test_the_record_still_says_whose_word_it_arrived_on(self, client):
        """Not shown, still recorded: the signed-in user, else "operations" --
        the same word a REJECT from this screen records."""
        _create(client)
        record = list(sandbox.get_all().values())[0]
        assert record["intake_taken_by"] == "operations"

    def test_the_new_mission_page_shows_the_one_page_layout(self, client):
        html = client.get("/intake").get_data(as_text=True)
        for gone in ("Taken by", "Load number (theirs)", "Load control is the",
                     "Load control phone", "Stop 1 load control", "Cargo items",
                     "Pallets (total)", "Amount to collect"):
            assert gone not in html, gone
        for section in mt.SECTIONS:
            assert "<h2>%s</h2>" % section in html

    def test_an_unknown_source_cannot_get_in(self):
        """It used to be refused at the door. Now there is no door -- the form
        does not accept a source at all, so an unknown one cannot arrive.
        Checked at the model, since the route no longer reads the field."""
        assert "TELEPATHY" not in mt.INTAKE_SOURCES


class TestTheCandidateQueue:
    def test_it_lists_candidates(self, client):
        _create(client)
        html = client.get("/candidates").get_data(as_text=True)
        assert "Baptist Health Logistics" in html
        assert "COMMIT" in html and "REJECT" in html

    def test_a_committed_mission_leaves_the_queue(self, client):
        """It has left Booking and belongs to Dispatch. A queue that keeps
        showing it is a queue he stops trusting to mean 'these need me'."""
        _create(client)
        record_id = list(sandbox.get_all())[0]
        client.post(f"/brief/mission/{record_id}/commit")
        assert "Baptist Health" not in client.get("/candidates").get_data(as_text=True)

    def test_rejecting_an_uncommitted_candidate_discards_it(self, client):
        """This test used to hold that a rejection is recorded, not deleted.
        Superseded by Owner ruling D12, 2026-09-14: "program only processes
        committed loads. due to the life span of only hours to minuties it makes
        no sense to keep any uncommitted load information." """
        _create(client)
        record_id = list(sandbox.get_all())[0]
        client.post(f"/brief/mission/{record_id}/reject",
                    data={"reason": "Rate too low"})
        assert sandbox.get(record_id) is None

    def test_rejecting_a_committed_mission_records_rather_than_deletes(self, client, tmp_path):
        """A committed record is never discarded."""
        from dispatch.db import set_db_path

        set_db_path(tmp_path / "dispatch.db")
        try:
            _create(client)
            record_id = list(sandbox.get_all())[0]
            client.post(f"/brief/mission/{record_id}/commit")
            client.post(f"/brief/mission/{record_id}/reject",
                        data={"reason": "Rate too low"})
            record = sandbox.get(record_id)
            assert record is not None
            assert record["rejected_at"]
            assert record["rejected_reason"] == "Rate too low"
        finally:
            set_db_path(None)

    def test_a_rejected_candidate_leaves_the_queue(self, client):
        _create(client)
        record_id = list(sandbox.get_all())[0]
        client.post(f"/brief/mission/{record_id}/reject")
        assert "Baptist Health" not in client.get("/candidates").get_data(as_text=True)

    def test_it_counts_the_gaps_without_scoring_them(self, client):
        _create(client)
        html = client.get("/candidates").get_data(as_text=True)
        assert "with no entry" in html
        assert "%" not in html.split("cand-gaps")[1][:200]

    def test_an_empty_queue_says_so_plainly(self, client):
        html = client.get("/candidates").get_data(as_text=True)
        assert "Nothing waiting" in html


class TestTheOnePageMissionRunsEndToEnd:
    """New Mission -> brief -> Driver Cockpit, through the real routes, on the
    one-page layout of 2026-09-15."""

    def test_the_brief_and_cockpit_show_what_new_mission_took(self, client):
        assert _create(client, service="LTL", controlled_by="Level 1",
                       customer_email="ops@baptist.example",
                       pieces_pallets="2 pallets / 14 pieces",
                       weight_lbs="1200", amount="450").status_code == 302
        record_id = list(sandbox.get_all())[0]
        record = sandbox.get(record_id)
        assert record["mission_number"]

        import re

        brief_html = client.get(f"/brief/mission/{record_id}").get_data(as_text=True)

        def shown(label):
            match = re.search(r">%s</dt>\s*<dd[^>]*>\s*(.*?)\s*</dd>" % re.escape(label),
                              brief_html, re.S)
            assert match, label
            return match.group(1)

        assert shown("Service Type") == "LTL"
        assert shown("Load control") == "Level 1"
        assert shown("Their email") == "ops@baptist.example"
        assert shown("Pieces / Pallets") == "2 pallets / 14 pieces"
        assert shown("Weight (lbs, total)") == "1200"
        assert shown("Amount") == "450"
        assert shown("Mission Number") == str(record["mission_number"])
        for gone in (">Status<", ">Intake<", ">Taken by<", "operations"):
            assert gone not in brief_html, gone

        cockpit = client.get(f"/portal/mission/{record_id}?view=DELIVERY")
        assert cockpit.status_code == 200
        cockpit_html = cockpit.get_data(as_text=True)
        assert "Gainesville, FL 32608" in cockpit_html
        assert "2 pallets / 14 pieces" in cockpit_html
        assert '<span class="control-name">Level 1</span>' in cockpit_html


class TestThereIsOnlyOneTemplate:
    def test_the_screen_is_built_from_the_template(self, client):
        """Not a second field list. A form with its own list drifts from the
        record by the second revision."""
        html = client.get("/intake").get_data(as_text=True)
        for field in mt.TEMPLATE:
            assert 'name="%s"' % field.key in html, field.key

    def test_choosing_a_source_does_not_change_the_form(self, client):
        """There is no courier template."""
        phone = client.get("/intake?source=PHONE").get_data(as_text=True)
        courier = client.get("/intake?source=COURIER").get_data(as_text=True)
        assert phone.count('name="') == courier.count('name="')

    def test_sweep_and_api_are_not_offered_to_a_person(self, client):
        """They are how machines bring work in, never chosen on a screen."""
        offered = [key for key, _, _ in mt.MANUAL_SOURCES]
        assert "SWEEP" not in offered and "API" not in offered


class TestNoScreenIsADeadEnd:
    """The operator had to use the browser's back button to leave a brief.

    Its only exit went to the Driver Cockpit -- the truck's screen -- when he
    had arrived from the load listing. A screen whose one way out goes
    somewhere else is a screen he leaves with the back button, and that is not
    navigation.
    """

    def _screens(self, client):
        _create(client)
        record_id = list(sandbox.get_all())[0]
        return {
            "candidates": "/candidates",
            "booking": "/booking",
            "intake": "/intake",
            "brief": "/brief/mission/%s" % record_id,
        }

    def test_every_booking_screen_reaches_every_other(self, client):
        for name, url in self._screens(client).items():
            html = client.get(url).get_data(as_text=True)
            assert 'class="ops-nav"' in html, name
            for target in ("/candidates", "/booking", "/intake"):
                assert target in html, "%s cannot reach %s" % (name, target)

    def test_the_brief_returns_to_the_listing_he_came_from(self, client):
        screens = self._screens(client)
        html = client.get(screens["brief"]).get_data(as_text=True)
        actions = html[html.index('class="brief-actions"'):]
        actions = actions[:actions.index("</nav>")]
        # LOADS, not CANDIDATES, since decision D-LOADS on 2026-09-09. Freight
        # office language: the screen holds loads, not candidate records.
        assert "LOADS" in actions
        assert actions.index("LOADS") < actions.index("COCKPIT"), (
            "leaving a brief should return him to the load listing, not the truck")

    def test_the_cockpit_is_still_reachable_from_the_brief(self, client):
        """Still there, just not the way out."""
        screens = self._screens(client)
        assert "COCKPIT" in client.get(screens["brief"]).get_data(as_text=True)

    def test_the_sidebar_carries_the_booking_screens(self, client):
        """Reachable from the rest of the portal, not only by typing a URL."""
        source = open("portal/templates/base.html", encoding="utf-8").read()
        for endpoint in ("joe_portal.candidate_queue",
                         "joe_portal.booking_board",
                         "joe_portal.mission_intake"):
            assert endpoint in source, endpoint

    def test_the_strip_does_not_print(self, client):
        """The brief is carried to a phone call. Navigation on paper is noise."""
        css = open("portal/static/booking.css", encoding="utf-8").read()
        assert "@media print { .ops-nav { display: none; } }" in css


class TestTheSourceSurvivesIntoTheLoadRecord:
    """**The analytics field, end to end.** Mike, 2026-09-06:

        *"which load_board would be a need to know i had not considered. this
        could be a report field that could help me with internal analytics."*

    It already could. `models.LOAD_SOURCES` names the boards -- `dat`,
    `truckstop`, `referral`, `direct` -- and `mission.py` copies the card's
    source onto the load when it recognises one.

    **It recognised almost nothing.** Of the six values the intake form offered,
    five were not in `LOAD_SOURCES`, so booking silently blanked the field. A
    report on where freight comes from would have shown one category: empty.
    """

    def test_direct_is_a_value_the_load_record_accepts(self):
        from dispatch.models import LOAD_SOURCES

        assert mt.SOURCE_DIRECT.lower() in LOAD_SOURCES

    def test_the_boards_mike_would_report_on_are_all_there(self):
        from dispatch.models import LOAD_SOURCES

        for board in ("direct", "dat", "truckstop", "referral"):
            assert board in LOAD_SOURCES

    def test_the_old_values_are_the_ones_that_were_dropped(self):
        """Kept as the record of what went wrong, so it is not reintroduced."""
        from dispatch.models import LOAD_SOURCES

        for dropped in ("customer", "phone", "courier", "text", "joe"):
            assert dropped not in LOAD_SOURCES

    def test_a_hand_opened_mission_books_as_direct(self, client):
        """The whole point: open one on the form, book it, and the load record
        says where it came from."""
        from dispatch import mission as mission_svc
        from dispatch import services as dispatch_svc
        from dispatch import store as dispatch_store

        _create(client)
        record = list(sandbox.get_all().values())[0]
        assert record["card_data"]["source"] == "direct"

        mission_svc.accept_load(record["id"], sandbox_module=sandbox,
                                dispatch_services=dispatch_svc,
                                store_module=dispatch_store)
        load = dispatch_svc.get_load(record["id"])
        assert load is not None, "booking did not create a load record"
        assert load["source"] == "direct", (
            "the source was dropped on the way into the load record"
        )


class TestServiceTypeIsPickedNotTyped:
    """**Mike's list, 2026-09-06**, twelve kinds of run -- **reduced to two by
    the one-page layout, 2026-09-15:** *"drop status type is LTL / Courier"*.

    Courier moved here from the intake source list on 2026-09-06, where it was
    a category error -- a courier run is a kind of freight, not a way a load
    reached the office.

    Picked, never typed, because the whole point is counting them later.
    """

    def test_the_list_is_mikes_list(self):
        assert mt.SERVICE_TYPES == ("LTL", "Courier")

    def test_courier_is_still_a_kind_of_run(self):
        """Courier was an intake source until 2026-09-06."""
        assert "Courier" in mt.SERVICE_TYPES

    def test_the_field_carries_them(self):
        field = next(f for f in mt.TEMPLATE if f.key == "service")
        assert field.choices == mt.SERVICE_TYPES

    def test_the_screen_offers_a_picker_not_a_text_box(self, client):
        html = client.get("/intake").get_data(as_text=True)
        assert "<select" in html
        assert '<option value="LTL"' in html
        assert '<option value="Courier"' in html
        assert "Emergency / Expedited" not in html

    def test_the_picks_are_a_dropdown_not_radio_buttons(self, client):
        """The New Mission screen draws every pick list the same way."""
        html = client.get("/intake").get_data(as_text=True)
        assert len(mt.SERVICE_TYPES) == 2
        assert 'type="radio"' not in html

    def test_a_chosen_service_reaches_the_record(self, client):
        """It lands at the top level of the record, **not on the card.** The
        card is what the Driver Cockpit reads, so today the service type is
        stored and reportable but not shown to the driver. Recorded here rather
        than changed, because whether he needs to see it is Mike's call."""
        _create(client, service="Courier")
        record = list(sandbox.get_all().values())[0]
        assert record.get("service") == "Courier"

    def test_load_control_is_picked_too(self, client):
        """*"2) yes either"* -- the Customer, or Level 1."""
        html = client.get("/intake").get_data(as_text=True)
        assert '<select name="controlled_by">' in html
        assert '<option value="Level 1"' in html
        _create(client, controlled_by="Level 1")
        record = list(sandbox.get_all().values())[0]
        assert record.get("controlled_by") == "Level 1"

    def test_it_is_optional_and_a_blank_is_not_invented(self, client):
        """Leave anything you do not know blank -- do not guess. The footer of
        the form says so, and it has to be true."""
        assert _create(client).status_code == 302
        record = list(sandbox.get_all().values())[0]
        assert record.get("service", "") == ""


class TestEveryBoardMikeUsesIsAccepted:
    """`mission.py` copies a card's source onto the load **only** when it names
    something `LOAD_SOURCES` recognises, and drops it silently otherwise. So a
    board missing from that list is a board whose loads book with no source at
    all -- and a report on where his work comes from would simply not see them.

    Mike named his four on 2026-09-06: DAT, Truckstop, 123Loadboard, Truck
    Smarter. **Two were absent.**
    """

    @pytest.mark.parametrize("board", ["dat", "truckstop",
                                       "123loadboard", "trucksmarter"])
    def test_the_board_reaches_the_load_record(self, board):
        from dispatch.models import LOAD_SOURCES

        assert board in LOAD_SOURCES

    def test_direct_sits_alongside_them(self):
        """A hand-opened mission and a swept one land in one vocabulary, so a
        single report can compare them."""
        from dispatch.models import LOAD_SOURCES

        assert mt.SOURCE_DIRECT.lower() in LOAD_SOURCES

    def test_an_unknown_board_is_still_refused(self):
        """The list stays fixed. Adding a board is a deliberate act, because a
        list that accepts anything cannot be grouped."""
        from dispatch.models import LOAD_SOURCES

        assert "loadboard_we_never_signed_up_for" not in LOAD_SOURCES
