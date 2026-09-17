"""START RUN: the one act on the driver's screen.

**Owner ruling, 2026-09-16.** The name is his own word -- *"there are no runs for
Monday. There are runs scheduled and on the calendar"* -- and he never said
"start mission" except reading it off this screen.

    Calendar     tap any day, any month          nothing happens
    Day          see what is on it               nothing happens
    Cockpit      read it, toggle PICKUP/DELIVERY nothing happens
                 -- START RUN --                 reality changes, for this load

*"Viewing and execution remain separate concepts ... The system must never turn
a glance into a commitment."*

The blue area used to render `STATUS: {{ mode_label }}` -- announcing which half
of the screen you were looking at as though it were your status. That is why
PICKUP and DELIVERY felt like execution controls: the screen was calling a view
a state.
"""

from __future__ import annotations

import pytest

from portal.models import sandbox


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
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
            s["driver_open"] = True
            s["role"] = "Driver"
        yield c


@pytest.fixture()
def mission(client):
    """A committed mission with its load row open -- what COMMIT leaves behind."""
    from dispatch import commitment
    from portal.models import opportunity_card as oc
    from portal.routes import joe_portal

    record = oc.from_capture({
        "opportunity_id": "RUN-1",
        "origin": "Jacksonville, FL", "destination": "Savannah, GA",
        "contact": "Penske Logistics", "commodity": "Auto Parts",
        "pickup_date": "2026-09-21 09:00", "delivery_date": "2026-09-21 14:00",
    })
    rid = record["id"]
    data = sandbox._load()
    data[rid].update(commitment.commit(dict(data[rid]), when="2026-09-20T12:00:00Z"))
    sandbox._save(data)
    joe_portal._open_operational_load(rid, sandbox.get(rid))
    return rid


def _page(client, rid: str) -> str:
    return client.get("/portal/mission/%s" % rid).get_data(as_text=True)


def _status(client, rid: str) -> str:
    from dispatch import services as dispatch_svc

    return str((dispatch_svc.get_load(rid) or {}).get("status") or "")


class TestTheNameIsHisWord:
    def test_the_act_is_called_start_run(self):
        from portal.routes import joe_portal

        assert joe_portal.START_RUN == "START RUN"
        assert joe_portal.NEXT_STEP["created"] == ("START RUN", "en_route_pickup")

    def test_nothing_on_the_screen_says_start_mission(self, client, mission):
        page = _page(client, mission)

        assert "START MISSION" not in page
        assert "START RUN" in page


class TestBeforeTheRunBegins:
    def test_the_status_area_says_ready(self, client, mission):
        """Not a milestone. A load sitting `created` is ready and nothing more."""
        page = _page(client, mission)

        assert "STATUS: READY" in page

    def test_the_act_is_offered_in_one_place_on_the_glass(self, client, mission):
        """Two buttons for one act is two things to decide between at a dock, so
        the Mission Actions column does not repeat it.

        The manual milestone drawer still lists `Start run` -- that is the
        closed list of every milestone, for one he missed, and it is behind a
        drawer rather than on the glass."""
        page = _page(client, mission)

        assert "NEXT: START RUN" not in page
        assert page.count('class="run-btn"') == 1


class TestThePressChangesReality:
    def test_one_press_puts_him_on_the_road(self, client, mission):
        """**Owner, 2026-09-16:** *"same act. Two terms for same act."* It used
        to record `dispatched` and leave a second button, ON MY WAY TO PICKUP,
        that told nobody anything the first had not."""
        assert _status(client, mission) == "created"

        client.post("/portal/mission/%s/milestone" % mission,
                    data={"milestone_event": "en_route_pickup"})

        assert _status(client, mission) == "en_route_pickup"

    def test_the_next_thing_asked_for_is_the_pickup(self, client, mission):
        """Not a second way of saying he has started."""
        client.post("/portal/mission/%s/milestone" % mission,
                    data={"milestone_event": "en_route_pickup"})

        page = _page(client, mission)

        assert "ON MY WAY TO PICKUP" not in page
        assert "ARRIVE" in page

    def test_afterwards_the_area_reports_where_the_load_is(self, client, mission):
        """The status area goes back to being a display and tracks the load."""
        client.post("/portal/mission/%s/milestone" % mission,
                    data={"milestone_event": "en_route_pickup"})

        page = _page(client, mission)

        assert "EN ROUTE PICKUP" in page
        assert 'class="run-btn"' not in page, "a run already started cannot be started"

    def test_there_is_no_off(self, client, mission):
        """*"That action changes reality."* It sends an arrival notice to a
        broker and that cannot be un-sent. Pause, cancel and done are three
        different things, and none of them is this button."""
        client.post("/portal/mission/%s/milestone" % mission,
                    data={"milestone_event": "en_route_pickup"})

        page = _page(client, mission)

        for off in ("STOP RUN", "END RUN", "CANCEL RUN", "UNSTART"):
            assert off not in page


class TestLookingIsStillNotActing:
    """PICKUP and DELIVERY are display modes and always were -- `normalise_mode`
    is pure. What was wrong is that the screen called the view a status."""

    def test_the_view_is_never_called_a_status(self, client, mission):
        page = _page(client, mission)

        assert "STATUS: PICKUP" not in page
        assert "STATUS: DELIVERY" not in page

    def test_toggling_the_view_starts_nothing(self, client, mission):
        before = _status(client, mission)

        for view in ("PICKUP", "DELIVERY", "PICKUP"):
            assert client.get("/portal/mission/%s?view=%s"
                              % (mission, view)).status_code == 200

        assert _status(client, mission) == before == "created"

    def test_toggling_the_view_writes_nothing_to_the_record(self, client, mission):
        before = sandbox._load()

        client.get("/portal/mission/%s?view=DELIVERY" % mission)
        client.get("/portal/mission/%s?view=PICKUP" % mission)

        assert sandbox._load() == before

    def test_reading_the_mission_starts_nothing(self, client, mission):
        _page(client, mission)
        _page(client, mission)

        assert _status(client, mission) == "created"


class TestOnceStartedTheFlowKeepsGoing:
    """**Owner, 2026-09-16:** *"once the action button is pressed the
    deterministic flow has begun even if the truck stops over night the flow
    path is moving toward completion."*

    There is no pause, and nothing may quietly undo a started run."""

    def test_an_overnight_stop_does_not_end_the_run(self, client, mission):
        """A run that spans two days is normal freight, not an abandoned card."""
        from datetime import datetime, timedelta, timezone

        client.post("/portal/mission/%s/milestone" % mission,
                    data={"milestone_event": "en_route_pickup"})
        sandbox.start_hold(mission)

        swept = sandbox.run_hold_sweep(
            now=datetime.now(timezone.utc) + timedelta(days=1))

        assert mission not in swept
        assert sandbox.get(mission), "the truck is carrying this freight"
        assert _status(client, mission) == "en_route_pickup"

    def test_the_two_protection_tests_agree(self):
        """`sandbox._is_protected` is `opportunity_card.is_protected` written
        out rather than imported: this module sits under the connector boundary,
        which forbids reaching `dispatch.services` even transitively, and the
        twin reaches it for the fleet. Importing it broke the boundary the moment
        it was added -- so the two are held in agreement here instead."""
        from portal.models import opportunity_card as oc

        for entry in ({}, {"committed_at": "2026-09-16T12:00:00Z"},
                      {"engine_load_id": "LOAD-1"}, {"operational_load": True},
                      {"hold_expires_at": "2026-09-16T12:00:00Z"}):
            assert sandbox._is_protected(entry) is oc.is_protected(entry), entry

    def test_a_candidate_nobody_committed_to_is_still_swept(self):
        """The HOLD clock still governs what it was always for."""
        from datetime import datetime, timedelta, timezone

        from portal.models import opportunity_card as oc

        card = oc.from_capture({"opportunity_id": "HOLD-1",
                                "origin": "Jacksonville, FL",
                                "destination": "Savannah, GA",
                                "commodity": "Pallets"})
        sandbox.start_hold(card["id"])

        swept = sandbox.run_hold_sweep(
            now=datetime.now(timezone.utc) + timedelta(days=1))

        assert card["id"] in swept


class TestAMissedStartIsStillReachable:
    def test_the_milestone_list_offers_it_by_the_same_name(self):
        """For a run he forgot to start before he rolled."""
        from portal.routes import joe_portal

        assert ("Start run", "en_route_pickup") in joe_portal.ALL_MILESTONES
        assert not any(label == "Start mission"
                       for label, _ in joe_portal.ALL_MILESTONES)

    def test_the_list_does_not_offer_two_words_for_one_act(self):
        """*"same act. Two terms for same act."* A list carrying both asks him
        to choose between two names for one thing."""
        from portal.routes import joe_portal

        labels = [label for label, _ in joe_portal.ALL_MILESTONES]
        events = [event for _, event in joe_portal.ALL_MILESTONES]

        assert "On my way to pickup" not in labels
        assert events.count("en_route_pickup") == 1
        assert "dispatched" not in events
