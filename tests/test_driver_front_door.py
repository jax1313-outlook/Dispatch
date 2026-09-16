"""The Driver Portal's own front door.

**Owner ruling, 2026-09-16:**

    Driver PIN -> Driver Calendar -> Select Day -> Driver Cockpit -> Work

*"The calendar is the driver's landing page. Not the Driver Cockpit. Not a blank
screen. Not a mission card."*

The gap he found: a driver PIN landed on `joe_portal.portal_home` -- Operations'
front page. *"You don't get to see a map. Excuse me, A calendar? All you see is
a blank screen."* The Driver Portal is a separate workspace: Operations creates
and commits work, the driver executes it.

The rule that shapes every test here: **looking is not acting.** He can open any
day of any month and nothing is reserved, nothing advances, nothing is written.
*"The system must never turn a glance into a commitment."*
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from dispatch import booking
from portal.models import sandbox


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
        with c.session_transaction() as s:
            s["driver_open"] = True
            s["role"] = "Driver"
        yield c


def _committed(number: str, day: date) -> str:
    """A committed mission on one day, as COMMIT would leave it."""
    from dispatch import commitment
    from portal.models import opportunity_card as oc

    record = oc.from_capture({
        "opportunity_id": number,
        "origin": "Jacksonville, FL", "destination": "Savannah, GA",
        "broker": "Penske Logistics", "commodity": "Auto Parts",
        "pickup_date": "%s 09:00" % day.isoformat(),
        "delivery_date": "%s 14:00" % day.isoformat(),
    })
    data = sandbox._load()
    data[record["id"]].update(
        commitment.commit(dict(data[record["id"]]), when="%sT12:00:00Z" % day.isoformat()))
    sandbox._save(data)
    return record["id"]


class TestEveryDayBeginsOpen:
    """*"Dispatch does not decide: when Mike works, when Mike rests, when Mike
    performs maintenance, when Mike reserves capacity, which days are closed."*"""

    def test_no_weekday_is_held_or_closed_by_the_pattern(self):
        monday = date(2026, 9, 14)
        for offset in range(7):
            assert booking.pattern_for(monday + timedelta(days=offset)) == booking.OPEN

    def test_a_day_with_freight_on_it_is_booked(self):
        assert booking.day_state(date(2026, 9, 17), [{"phase": "Pickup"}]) == booking.BOOKED

    def test_the_states_are_kept_as_vocabulary(self):
        """HELD, MAINTENANCE and CLOSED are not deleted. Nothing produces one
        now; they remain the words for a day Outlook or a later ruling says is
        not sellable."""
        for state in (booking.HELD, booking.MAINTENANCE, booking.CLOSED):
            assert state in booking.LABELS


class TestTheMonthIsOneCalculation:
    """*"One calendar, one source of truth, multiple views."* The Booking board
    and this grid read the same function, so they cannot disagree about a
    Tuesday."""

    def test_it_covers_the_whole_month_in_weeks(self):
        grid = booking.month_of(2026, 9, [], today=date(2026, 9, 16))

        assert len(grid["days"]) == 30
        assert all(len(week) == 7 for week in grid["weeks"])
        assert grid["weeks"][0][0] is None      # September 2026 starts Tuesday
        assert grid["weeks"][0][1]["day"] == 1

    def test_an_empty_future_day_is_a_gap(self):
        """The thing he opens the screen to see."""
        grid = booking.month_of(2026, 9, [], today=date(2026, 9, 16))
        by_day = {d["day"]: d for d in grid["days"]}

        assert by_day[20]["gap"] is True
        assert by_day[2]["gap"] is False, "a day already gone is not an opportunity"

    def test_a_committed_day_is_not_a_gap(self):
        _committed("FRONT-1", date(2026, 9, 21))

        grid = booking.month_of(2026, 9, sandbox._load(), today=date(2026, 9, 16))
        by_day = {d["day"]: d for d in grid["days"]}

        assert by_day[21]["loads"]
        assert by_day[21]["gap"] is False
        assert grid["committed_days"] == 1

    def test_a_candidate_never_counts_as_capacity(self):
        """Until COMMIT the day is still sellable to somebody else."""
        from portal.models import opportunity_card as oc

        oc.from_capture({"opportunity_id": "FRONT-2", "origin": "Jacksonville, FL",
                         "destination": "Savannah, GA", "commodity": "Pallets",
                         "pickup_date": "2026-09-22 09:00",
                         "delivery_date": "2026-09-22 14:00"})

        grid = booking.month_of(2026, 9, sandbox._load(), today=date(2026, 9, 16))
        by_day = {d["day"]: d for d in grid["days"]}

        assert by_day[22]["candidates"], "shown, because what is in play matters"
        assert by_day[22]["loads"] == []
        assert by_day[22]["gap"] is True, "still sellable"


class TestThePinLandsOnTheCalendar:
    def test_the_calendar_is_the_front_door(self, client):
        assert client.get("/driver/calendar").status_code == 200

    def test_a_driver_who_is_not_signed_in_is_sent_to_sign_in(self):
        from portal.app import create_app

        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as stranger:
            answer = stranger.get("/driver/calendar")

        assert answer.status_code == 302
        assert "/driver/login" in answer.headers["Location"]

    def test_the_landing_is_no_longer_operations(self):
        """It was `joe_portal.portal_home` -- Operations' front page, reached
        with a driver PIN."""
        from portal.routes import driver_portal

        from portal.app import create_app

        app = create_app()
        with app.test_request_context():
            assert driver_portal._cockpit() == "/driver/calendar"


class TestLookingIsNotActing:
    """*"He can look at Monday through Sunday without any consequences. Looking
    is not acting. Viewing is not committing."*"""

    def test_any_month_opens_and_nothing_changes(self, client):
        _committed("FRONT-3", date(2026, 9, 21))
        before = sandbox._load()

        for month in (8, 9, 10, 11):
            assert client.get("/driver/calendar?year=2026&month=%d" % month).status_code == 200

        assert sandbox._load() == before

    def test_opening_a_day_changes_nothing(self, client):
        _committed("FRONT-4", date(2026, 9, 21))
        before = sandbox._load()

        assert client.get("/driver/day/2026-09-21").status_code == 200
        assert client.get("/driver/day/2026-09-22").status_code == 200

        assert sandbox._load() == before

    def test_a_day_with_nothing_on_it_says_so(self, client):
        page = client.get("/driver/day/2026-09-23").get_data(as_text=True)

        assert "Nothing on this day" in page

    def test_a_nonsense_date_goes_back_to_the_calendar(self, client):
        answer = client.get("/driver/day/not-a-date")

        assert answer.status_code == 302
        assert "/driver/calendar" in answer.headers["Location"]

    def test_the_day_offers_the_mission_and_starts_nothing(self, client):
        record_id = _committed("FRONT-5", date(2026, 9, 21))

        page = client.get("/driver/day/2026-09-21").get_data(as_text=True)

        assert record_id in page, "the mission is reachable"
        assert "OPEN" in page
        for act in ("START MISSION", "BEGIN WORK", "PICKUP</button>"):
            assert act not in page, "%s is an act, and this page only shows" % act


class TestWhatTheDayHoldsBehindTheSquare:
    def test_committed_freight_comes_before_candidates(self, client):
        from portal.models import opportunity_card as oc

        _committed("FRONT-6", date(2026, 9, 24))
        oc.from_capture({"opportunity_id": "FRONT-7", "origin": "Jacksonville, FL",
                         "destination": "Orlando, FL", "commodity": "Pallets",
                         "pickup_date": "2026-09-24 08:00",
                         "delivery_date": "2026-09-24 12:00"})

        entries = booking.loads_on(date(2026, 9, 24), sandbox._load())

        assert entries[0]["committed"] is True
        assert entries[-1]["committed"] is False
