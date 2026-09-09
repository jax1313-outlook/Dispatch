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
        month. This is the comparison that silently failed."""
        from portal.routes.api import _extract_window_start
        written = _extract_window_start("September 15")
        assert written[:7] == "2026-09"
