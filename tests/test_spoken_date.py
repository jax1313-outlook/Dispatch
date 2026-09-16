"""A date, however it was said.

The silent miss these exist to prevent: a voice capture says "Thursday",
booking copies the word into the operational row, and the calendar -- which
groups loads by the first seven characters of the date -- compares "Thursda"
against "2026-09" and shows nothing. No error. The load is just not there.
"""

from __future__ import annotations

from datetime import date

import pytest

from dispatch import spoken_date

#: A Wednesday, so "Thursday" is tomorrow and "Tuesday" is nearly a week out.
WEDNESDAY = date(2026, 9, 9)


class TestWhatMikeActuallySays:
    @pytest.mark.parametrize("said,expected", [
        ("Thursday", "2026-09-10"),
        ("thurs", "2026-09-10"),
        ("thu", "2026-09-10"),
        ("Monday", "2026-09-14"),
        ("today", "2026-09-09"),
        ("tomorrow", "2026-09-10"),
    ])
    def test_a_weekday_is_the_soonest_one(self, said, expected):
        assert spoken_date.resolve(said, today=WEDNESDAY) == expected

    def test_the_day_being_said_is_today_not_a_week_away(self):
        """Said on a Wednesday, "Wednesday" means this one. A driver reading a
        board is talking about the load in front of him."""
        assert spoken_date.resolve("Wednesday", today=WEDNESDAY) == "2026-09-09"

    def test_next_weekday_is_the_one_after(self):
        assert spoken_date.resolve("next Thursday", today=WEDNESDAY) == "2026-09-17"

    @pytest.mark.parametrize("said,expected", [
        ("September 15", "2026-09-15"),
        ("Sept 15th", "2026-09-15"),
        ("the 15th", "2026-09-15"),
        ("9/15", "2026-09-15"),
        ("09/15/2026", "2026-09-15"),
        ("2026-09-15", "2026-09-15"),
    ])
    def test_a_date_said_as_a_date(self, said, expected):
        assert spoken_date.resolve(said, today=WEDNESDAY) == expected

    def test_a_month_and_day_already_past_rolls_to_next_year(self):
        """A listing dictated in December for the third of January is next
        year's third."""
        december = date(2026, 12, 20)
        assert spoken_date.resolve("January 3", today=december) == "2027-01-03"

    @pytest.mark.parametrize("said,expected", [
        ("Thursday 6am", "2026-09-10 06:00"),
        ("Thursday at 2pm", "2026-09-10 14:00"),
        ("Thursday 0600", "2026-09-10 06:00"),
        ("Thursday 14:30", "2026-09-10 14:30"),
    ])
    def test_a_time_comes_along_when_one_was_said(self, said, expected):
        assert spoken_date.resolve(said, today=WEDNESDAY) == expected


class TestItRefusesRatherThanGuesses:
    @pytest.mark.parametrize("said", [
        "", None, "as soon as possible", "whenever they can take it",
        "next week sometime", "flexible",
    ])
    def test_what_it_cannot_read_comes_back_empty(self, said):
        assert spoken_date.resolve(said, today=WEDNESDAY) == ""

    def test_an_impossible_date_is_refused_not_rounded(self):
        assert spoken_date.resolve("2026-02-30", today=WEDNESDAY) == ""
        assert spoken_date.resolve("13/45", today=WEDNESDAY) == ""

    def test_looks_resolved_only_says_yes_to_a_real_date(self):
        assert spoken_date.looks_resolved("2026-09-10 06:00") is True
        assert spoken_date.looks_resolved("Thursday") is False
        assert spoken_date.looks_resolved("") is False


class TestOrdinaryWordsAreNotDates:
    """CO-2, 2026-09-14. "may", "sat" and "sun" are English before they are dates."""

    @pytest.mark.parametrize("said,expected", [
        ("Thursday, may load late", "2026-09-10"),
        ("may need 2 straps", ""),
        ("sun is out", ""),
        ("sat on the dock 2 hours", ""),
        ("sat", "2026-09-12"),
        ("sat 0800", "2026-09-12 08:00"),
        ("next sun", "2026-09-20"),
        ("May 3", "2027-05-03"),
        ("3rd of May", "2027-05-03"),
        ("15 Sept", "2026-09-15"),
    ])
    def test_a_word_only_counts_in_the_shape_of_a_date(self, said, expected):
        assert spoken_date.resolve(said, today=WEDNESDAY) == expected


class TestTheDayIsTheHomeTerminals:
    def test_the_default_day_comes_from_the_home_clock(self, monkeypatch):
        """At 9pm Eastern a UTC-clocked machine is already on tomorrow. The
        default day is the one `clock.home_date` gives, never `date.today()`."""
        from dispatch import clock

        monkeypatch.setattr(clock, "home_date", lambda: WEDNESDAY)
        assert spoken_date.resolve("tomorrow") == "2026-09-10"
        assert spoken_date.resolve("Thursday") == "2026-09-10"


class TestCaptureReadsTheDateWhenItIsSaid:
    """Through the capture contract, the way the Owner's voice reaches it."""

    def test_a_dictated_weekday_reaches_the_card_as_a_date(self, tmp_path, monkeypatch):
        from dispatch import clock
        from dispatch.db import set_db_path
        from portal.app import create_app
        from portal.models import sandbox

        set_db_path(tmp_path / "dispatch.db")
        monkeypatch.setenv("DISPATCH_JOE_TOKEN", "test-token")
        monkeypatch.setattr(clock, "home_date", lambda: WEDNESDAY)
        # The capture's own timestamp is today; pin the day it is read against.
        from portal.models import opportunity_card
        monkeypatch.setattr(opportunity_card, "capture_day", lambda record: WEDNESDAY)
        try:
            app = create_app()
            app.config["TESTING"] = True
            with app.test_client() as client:
                resp = client.post(
                    "/api/joe/opportunity",
                    json={"origin": "Jacksonville FL", "destination": "Tampa FL",
                          "rate": 750, "pickup_date": "Thursday 6am",
                          "delivery_date": "asap"},
                    headers={"Authorization": "Bearer test-token", "X-Driver": "mike"},
                )
            data = resp.get_json()
            assert data["ok"] is True
            # The contract's own record keeps the words exactly as said.
            assert data["opportunity"]["pickup_date"] == "Thursday 6am"
            card = next(e for e in sandbox.get_all().values()
                        if e["source_id"] == data["opportunity_id"])["card_data"]
            assert card["pickup_window"] == "2026-09-10 06:00"
            assert card["pickup_as_said"] == "Thursday 6am"
            # What cannot be read stays as the words, visibly undated.
            assert card["delivery_window"] == "asap"
            assert "delivery_as_said" not in card
        finally:
            set_db_path(None)


class TestTheBookingSeam:
    """`_extract_window_start` is where the miss happened."""

    def test_a_board_window_is_unchanged(self):
        from portal.routes.api import _extract_window_start
        assert _extract_window_start("2026-07-30 06:00 - 10:00") == "2026-07-30 06:00"

    def test_a_dictated_window_becomes_a_date(self):
        from portal.routes.api import _extract_window_start
        result = _extract_window_start("Thursday")
        assert result, "a spoken weekday must not reach the row as a word"
        assert spoken_date.looks_resolved(result)

    def test_a_window_nothing_can_read_is_empty_not_a_word(self):
        """The whole point. An undated load is recoverable. A load dated
        'Thursda' is not, because it looks like data."""
        from portal.routes.api import _extract_window_start
        assert _extract_window_start("as soon as possible") == ""

    def test_the_calendar_can_match_what_booking_now_writes(self):
        """The calendar groups by the first seven characters against a year and
        month. This is the comparison that silently failed.

        `_extract_window_start` reads the real clock, so the spoken day is a
        month out from today -- a date said today never lands in a past month,
        and never rolls into next year the way a fixed "September 15" did the
        morning after the fifteenth."""
        from portal.routes.api import _extract_window_start
        from datetime import timedelta
        spoken_day = date.today() + timedelta(days=30)
        written = _extract_window_start(f"{spoken_day:%B} {spoken_day.day}")
        assert written[:7] == f"{spoken_day:%Y-%m}"


class TestADictatedCityStillFindsItsLane:
    """A comma used to be required to separate the state.

    "Jacksonville, FL" split cleanly and "Jacksonville FL" did not, so every
    voice capture failed the distance lookup, economics came back "rate or
    distance data missing", and every card scored the same. Invisible while
    every load came from a board, because boards write the comma.
    """

    def test_a_lane_matches_with_or_without_the_comma(self):
        from dispatch.scoring import known_distance

        assert known_distance("Jacksonville, FL", "Savannah, GA") == 140
        assert known_distance("Jacksonville FL", "Savannah GA") == 140

    def test_a_lane_the_table_does_not_hold_stays_unknown(self):
        """None, not an estimate. Scoring says so rather than pricing a guess."""
        from dispatch.scoring import known_distance

        assert known_distance("Ocala FL", "Macon GA") is None

    def test_the_card_gets_the_distance_and_the_score_moves(self):
        from dispatch.scoring import score_load

        known = score_load({"origin": "Jacksonville FL", "destination": "Savannah GA",
                            "rate": 1150, "distance_miles": 140})
        unknown = score_load({"origin": "Ocala FL", "destination": "Macon GA",
                              "rate": 900})

        assert known["score"] > unknown["score"]
        assert "missing" in unknown["economic_opportunity_flag"]
        assert "/mi" in known["economic_opportunity_flag"]
