"""The Booking board: the forward view of the truck.

    How far out am I covered, and what is still sellable?

Not to be confused with `test_booking.py`, which covers booking a load into the
engine. This is the two-week board.

The week is a business model, not a calendar:

    MON TUE WED     sellable
    THU FRI         held for high-value expedited
    SAT             maintenance
    SUN             closed

That pattern is policy and lives in four lines. What is booked is read from the
records. Nothing about a day is stored, because Outlook is the single source of
scheduling truth and a stored day-state would be exactly the second calendar the
doctrine forbids.

Two ideas here are easy to lose and both are guarded:

  - Thursday and Friday are not empty. They are unsold on purpose, and a screen
    drawing them as gaps says he has a problem where he has a position.

  - Personal appointments are flagged, never blocking. Only he can weigh a
    09:00 dentist against a 06:00 gate time in Savannah.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from dispatch import booking


MONDAY = date(2026, 9, 7)     # a Monday, for a deterministic fortnight


def _record(load="L1-TEST", pickup="", delivery="", committed=True):
    """A committed mission by default.

    Only committed missions take capacity -- a candidate still being
    negotiated must not claim a day. These tests are about what a booked day
    looks like, so they commit; the gate itself is covered in
    `test_commitment.py`.
    """
    record = {"id": "SBX-1", "load_number": load,
              "card_data": {"load_id": load, "origin": "A", "destination": "B",
                            "pickup_window": pickup, "delivery_window": delivery}}
    if committed:
        record["committed_at"] = "2026-09-01T10:00:00Z"
    return record


def _board(records=None, calendar=None, today=MONDAY, weeks=2):
    return booking.build(records or {}, calendar or {}, today=today, weeks=weeks)


class TestTheWeekIsABusinessModel:
    @pytest.mark.parametrize("offset,expected", [
        (0, booking.OPEN), (1, booking.OPEN), (2, booking.OPEN),
        (3, booking.HELD), (4, booking.HELD),
        (5, booking.MAINTENANCE), (6, booking.CLOSED),
    ])
    def test_the_pattern_is_the_operators_week(self, offset, expected):
        assert booking.pattern_for(MONDAY + timedelta(days=offset)) == expected

    def test_maintenance_is_saturday_only(self):
        """Ruled after weighing it: Friday afternoon is prime expedited
        freight -- the weekend deadline is what makes shippers pay premium --
        so giving Friday to maintenance would cost the best loads of the week."""
        values = list(booking.WEEK_PATTERN.values())
        assert values.count(booking.MAINTENANCE) == 1
        assert booking.WEEK_PATTERN[5] == booking.MAINTENANCE
        assert booking.WEEK_PATTERN[3] == booking.WEEK_PATTERN[4] == booking.HELD

    def test_booked_is_resolved_never_planned(self):
        assert booking.BOOKED not in booking.WEEK_PATTERN.values()

    def test_nothing_about_a_day_is_stored(self):
        """Dispatch is not a calendar. A stored day-state would be the second
        source of scheduling truth the doctrine forbids."""
        source = open("dispatch/booking.py", encoding="utf-8").read()
        assert "_save" not in source
        assert "sandbox" not in source


class TestHeldIsAPositionNotAGap:
    def test_thursday_and_friday_read_as_held(self):
        held = [d for d in _board()["board"] if d["state"] == booking.HELD]
        assert len(held) == 4          # two Thursdays, two Fridays
        assert all(d["sub"] == "Expedited capacity" for d in held)

    def test_held_days_are_not_counted_as_unsold(self):
        """Thursday empty is success. Monday empty in four days is not."""
        book = _board()
        assert all(d["planned"] == booking.OPEN for d in book["unsold"])
        assert book["unsold_count"] == book["sellable_count"] == 6

    def test_taking_an_expedited_load_on_a_held_day_is_marked(self):
        """Not a problem -- it is the position paying off -- but worth seeing."""
        thursday = (MONDAY + timedelta(days=3)).isoformat()
        day = [d for d in _board({"a": _record(pickup=thursday)})["board"]
               if d["iso"] == thursday][0]
        assert day["state"] == booking.BOOKED
        assert day["held_and_taken"] is True

    def test_a_booked_sellable_day_is_not_marked_as_expedited(self):
        day = _board({"a": _record(pickup=MONDAY.isoformat())})["board"][0]
        assert day["state"] == booking.BOOKED
        assert day["held_and_taken"] is False


class TestWhatIsBooked:
    def test_a_load_makes_the_day_booked(self):
        board = _board({"a": _record(pickup=MONDAY.isoformat())})["board"]
        assert board[0]["state"] == booking.BOOKED
        assert board[0]["loads"][0]["phase"] == "Pickup"

    def test_both_ends_land_on_their_own_days(self):
        book = _board({"a": _record(pickup=MONDAY.isoformat(),
                                    delivery=(MONDAY + timedelta(days=1)).isoformat())})
        assert book["board"][0]["loads"][0]["phase"] == "Pickup"
        assert book["board"][1]["loads"][0]["phase"] == "Delivery"

    def test_a_day_has_exactly_one_state(self):
        """A day cannot be two things, so nothing can disagree."""
        for day in _board({"a": _record(pickup=MONDAY.isoformat())})["board"]:
            assert day["state"] in (booking.BOOKED, booking.OPEN, booking.HELD,
                                    booking.MAINTENANCE, booking.CLOSED)

    def test_depth_answers_how_far_out_he_is_covered(self):
        far = (MONDAY + timedelta(days=8)).isoformat()
        depth = _board({"a": _record(pickup=far)})["depth"]
        assert depth["has_work"] is True
        assert depth["days_out"] == 8
        assert "Booked through" in depth["line"]

    def test_an_empty_book_says_so(self):
        assert _board()["depth"]["line"] == "Nothing booked."

    def test_an_unparseable_window_is_left_off_not_guessed(self):
        """A day placed by a guessed parse is worse than a day left out: the
        whole screen answers how far out he is covered."""
        assert _board({"a": _record(pickup="sometime next week")})["booked_count"] == 0

    def test_a_gate_time_note_still_parses(self):
        """Real records carry '2026-09-02 06:00 (GATE 6 arrival time)'."""
        book = _board({"a": _record(pickup=MONDAY.isoformat()
                                    + " 06:00 (GATE 6 arrival time)")})
        assert book["board"][0]["state"] == booking.BOOKED


class TestAppointmentsAreFlaggedNotBlocking:
    def _calendar(self, when, subject="Dr Kessler DDS"):
        return {"status": "LIVE",
                "entries": [{"subject": subject, "start": when, "all_day": False}]}

    def test_it_does_not_change_the_day_state(self):
        """A 09:00 dentist does not stop a Monday delivery. Only he can weigh
        it against a 06:00 gate time in Savannah."""
        monday = _board(calendar=self._calendar(
            MONDAY.isoformat() + " 09:00"))["board"][0]
        assert monday["state"] == booking.OPEN
        assert len(monday["appointments"]) == 1

    def test_it_shows_what_the_appointment_is(self):
        book = _board(calendar=self._calendar(MONDAY.isoformat() + " 09:00"))
        assert book["board"][0]["appointments"][0]["subject"] == "Dr Kessler DDS"

    def test_it_never_blocks_a_booked_day(self):
        book = _board({"a": _record(pickup=MONDAY.isoformat())},
                      self._calendar(MONDAY.isoformat() + " 09:00"))
        assert book["board"][0]["state"] == booking.BOOKED
        assert book["board"][0]["appointments"]


class TestItIsHonestWhenTheCalendarIsQuiet:
    def test_no_calendar_means_no_invented_appointments(self):
        book = _board(calendar={"status": "UNAVAILABLE", "entries": []})
        assert book["calendar_status"] == "UNAVAILABLE"
        assert all(not d["appointments"] for d in book["board"])

    def test_the_freight_view_still_works_without_outlook(self):
        book = _board({"a": _record(pickup=MONDAY.isoformat())},
                      {"status": "UNAVAILABLE", "entries": []})
        assert book["board"][0]["state"] == booking.BOOKED

    def test_the_board_never_uses_the_demonstration_adapter(self):
        """It derives entries from the mission records, which on a planning
        board would draw invented appointments as real commitments."""
        source = open("portal/routes/joe_portal.py", encoding="utf-8").read()
        view = source[source.index("def booking_board"):]
        view = view[:view.index("@joe_bp.route", 10)]
        # Code only. The comment above the call explains why get_adapter() is
        # not used, and a check that reads prose fails on its own explanation.
        code = " ".join(line for line in view.splitlines()
                        if not line.strip().startswith("#"))
        assert "OutlookCalendarAdapter" in code
        assert "get_adapter()" not in code


class TestTheScreen:
    @pytest.fixture()
    def client(self):
        from portal.app import create_app

        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_it_renders(self, client):
        html = client.get("/booking").get_data(as_text=True)
        assert "BOOKING" in html
        assert "held for expedited" in html

    def test_the_headline_is_unsold_sellable_days(self, client):
        """Not revenue, not miles. Those are the days he can still sell, and
        they expire worthless."""
        html = client.get("/booking").get_data(as_text=True)
        assert "unsold" in html and "these expire" in html

    def test_a_quiet_calendar_is_explained_in_his_words(self, client):
        from portal import joe_voice

        html = client.get("/booking").get_data(as_text=True)
        if "Appointments are not showing" in html:
            note = html[html.index("Appointments are not showing"):]
            assert joe_voice.is_driver_safe(note[:note.index("<")]) == []


class TestItRunsMondayToSunday:
    """A fortnight starting on whatever today happens to be splits the week
    pattern across rows and makes it unreadable. Mon-Wed sellable, Thu-Fri
    held, Saturday maintenance only reads as a shape when the row is a week."""

    def test_every_row_starts_on_monday_and_ends_on_sunday(self):
        for week in _board()["weeks"]:
            assert len(week) == 7
            assert week[0]["date"].weekday() == 0
            assert week[6]["date"].weekday() == 6

    def test_the_board_starts_at_this_weeks_monday(self):
        wednesday = MONDAY + timedelta(days=2)
        book = _board(today=wednesday)
        assert book["starts"] == MONDAY
        assert book["board"][0]["date"] == MONDAY

    def test_days_already_gone_are_shown_but_marked(self):
        """Shown to keep the week whole; marked so they do not compete with
        the days he can still act on."""
        wednesday = MONDAY + timedelta(days=2)
        board = _board(today=wednesday)["board"]
        assert [d["past"] for d in board[:3]] == [True, True, False]

    def test_a_past_day_is_not_counted_as_unsold(self):
        """A day that has gone is not unsold inventory. It is just gone."""
        wednesday = MONDAY + timedelta(days=2)
        book = _board(today=wednesday)
        assert book["sellable_count"] == 4      # Wed, then Mon Tue Wed
        assert all(not d["past"] for d in book["unsold"])


class TestTheHorizonSwitches:
    def test_two_weeks_is_the_default(self):
        assert _board()["weeks_shown"] == 2
        assert len(_board()["weeks"]) == 2

    def test_a_month_is_the_same_board_deeper(self):
        """Not a second screen. Same states, same rules, more rows."""
        fortnight, month = _board(), _board(weeks=4)
        assert len(month["weeks"]) == 4
        assert month["board"][:14] == fortnight["board"]

    def test_the_sellable_count_scales_with_the_horizon(self):
        assert _board(weeks=4)["sellable_count"] == 12   # four weeks of Mon-Wed

    def test_the_pattern_holds_at_any_depth(self):
        for day in _board(weeks=6)["board"]:
            assert day["planned"] == booking.pattern_for(day["date"])
