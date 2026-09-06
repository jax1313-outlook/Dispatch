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


def _create(client, source="PHONE", taken_by="Mike", **over):
    data = dict(COMPLETE, source=source, taken_by=taken_by, **over)
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
        # Who took it is a different question and is still asked.
        assert 'name="taken_by"' in html

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
                                                "taken_by": "Mike",
                                                "customer": "Somebody"})
        assert response.status_code == 400
        assert sandbox.get_all() == {}

    def test_everything_typed_comes_back(self, client):
        """Losing a call's worth of notes to a validation message is how a
        screen stops being used."""
        response = client.post("/intake", data={
            "source": "PHONE", "taken_by": "Mike",
            "customer": "Baptist Health Logistics",
            "notes": "Sally says detention after two hours"})
        html = response.get_data(as_text=True)
        assert "Baptist Health Logistics" in html
        assert "detention after two hours" in html

    def test_it_says_every_problem_not_the_first(self, client):
        html = client.post("/intake", data={"source": "PHONE",
                                            "taken_by": "Mike"}).get_data(as_text=True)
        assert html.count("<li>") >= 4

    def test_it_will_not_create_without_who_took_it(self, client):
        """A mission arrives on somebody's word and the record says whose."""
        response = client.post("/intake", data=dict(COMPLETE, source="PHONE"))
        assert response.status_code == 400
        assert "Who took it" in response.get_data(as_text=True)

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

    def test_rejecting_records_rather_than_deletes(self, client):
        """The same broker rings back with the same lane, and what he offered
        last time is the useful thing to have."""
        _create(client)
        record_id = list(sandbox.get_all())[0]
        client.post(f"/brief/mission/{record_id}/reject",
                    data={"reason": "Rate too low"})
        record = sandbox.get(record_id)
        assert record is not None
        assert record["rejected_at"]
        assert record["rejected_reason"] == "Rate too low"

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
        assert "CANDIDATES" in actions
        assert actions.index("CANDIDATES") < actions.index("COCKPIT"), (
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
