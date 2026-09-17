"""What Booking says about a commitment, and what it must never do about it.

**BOOKING CONFLICT PREVENTION DOCTRINE, Mike Zachary, 2026-09-16:**

    LEVEL 1 - Position Conflict ... LEVEL 2 - Time Conflict ...
    LEVEL 3 - HOS Awareness

    RULE: "Display warning only. Do not block. Do not reserve capacity.
           Do not reject commitment. Human authority remains final."

All three were doctrine and none of them existed. The half that matters most
here is the second half: **the tests that prove a warning changes nothing.**
A warning that quietly held a day would be worse than no warning at all --
*"Dispatch does not decide: when Mike works, when Mike rests ... Human
authority remains final."*
"""

from __future__ import annotations

import pytest

from dispatch import booking, conflicts


def _card(rid, pickup, delivery, *, origin="Jacksonville, FL",
          destination="Savannah, GA", committed=True):
    record = {
        "id": rid,
        "pickup_window": pickup,
        "delivery_window": delivery,
        "card_data": {"origin": origin, "destination": destination},
        "pickup_location": origin,
        "delivery_location": destination,
        "load_number": rid,
    }
    if committed:
        record["committed_at"] = "2026-09-17T08:00:00Z"
    return record


class TestTimeConflict:
    """*"Two commitments overlap or create an impossible sequence."*"""

    def test_two_loads_on_the_same_day_are_named(self):
        mine = _card("NEW", "2026-09-21 09:00", "2026-09-21 17:00")
        theirs = _card("L1-AAAA", "2026-09-21 08:00", "2026-09-21 12:00")

        found = conflicts.check(mine, {"L1-AAAA": theirs})

        assert [w["level"] for w in found] == [conflicts.TIME]

    def test_a_multi_day_run_takes_the_days_between(self):
        """*"the truck is not sellable on a day it is driving somebody's
        freight."*"""
        mine = _card("NEW", "2026-09-22 09:00", "2026-09-22 17:00")
        theirs = _card("L1-BBBB", "2026-09-21 08:00", "2026-09-23 12:00")

        found = conflicts.check(mine, {"L1-BBBB": theirs})

        assert found and found[0]["level"] == conflicts.TIME

    def test_the_other_load_is_named_by_its_number(self):
        mine = _card("NEW", "2026-09-21 09:00", "2026-09-21 17:00")
        theirs = _card("L1-CCCC", "2026-09-21 08:00", "2026-09-21 12:00")

        found = conflicts.check(mine, {"L1-CCCC": theirs})

        assert "L1-CCCC" in found[0]["line"]

    def test_a_clear_day_raises_nothing(self):
        mine = _card("NEW", "2026-09-25 09:00", "2026-09-25 17:00")
        theirs = _card("L1-DDDD", "2026-09-21 08:00", "2026-09-21 12:00")

        assert conflicts.check(mine, {"L1-DDDD": theirs}) == []

    def test_an_uncommitted_card_takes_no_capacity(self):
        """*"until COMMIT the day is still sellable to somebody else."*"""
        mine = _card("NEW", "2026-09-21 09:00", "2026-09-21 17:00")
        theirs = _card("L1-EEEE", "2026-09-21 08:00", "2026-09-21 12:00",
                       committed=False)

        assert conflicts.check(mine, {"L1-EEEE": theirs}) == []

    def test_a_card_does_not_conflict_with_itself(self):
        mine = _card("L1-FFFF", "2026-09-21 09:00", "2026-09-21 17:00")

        assert conflicts.check(mine, {"L1-FFFF": mine}) == []


class TestHosAwareness:
    """*"return back to Jacksonville at 11pm and next proposed load is 4am
    there is not enough time for 10hr break"*"""

    def test_his_own_example_raises_it(self):
        mine = _card("NEW", "2026-09-22 04:00", "2026-09-22 14:00")
        theirs = _card("L1-GGGG", "2026-09-21 08:00", "2026-09-21 23:00")

        found = conflicts.check(mine, {"L1-GGGG": theirs})

        assert conflicts.HOS in [w["level"] for w in found]

    def test_twelve_clear_hours_raise_nothing(self):
        """Twelve, not ten: *"the break is ten, and fuelling, paperwork, a
        shower and getting to the shipper are not part of it."*"""
        mine = _card("NEW", "2026-09-22 12:00", "2026-09-22 20:00")
        theirs = _card("L1-HHHH", "2026-09-20 08:00", "2026-09-21 23:00")

        found = conflicts.check(mine, {"L1-HHHH": theirs})

        assert conflicts.HOS not in [w["level"] for w in found]

    def test_it_reads_two_typed_times_and_computes_no_drive_time(self):
        """`load_assessment.py:225` stands: *"this system does not need to
        track drive times for nay reason."* Level 3 is the gap between two
        windows a person typed, and nothing else."""
        source = open("dispatch/conflicts.py", encoding="utf-8").read()

        assert "drive_time" not in source


class TestPositionConflict:
    """*"Truck physically unlikely to be where the next commitment
    requires."*"""

    def test_a_far_repositioning_is_named(self, monkeypatch):
        from dispatch import distance

        monkeypatch.setattr(distance, "miles_between",
                            lambda o, d, **kw: {"miles": 900, "basis": "provider"})
        mine = _card("NEW", "2026-09-23 08:00", "2026-09-23 18:00",
                     origin="Miami, FL")
        theirs = _card("L1-IIII", "2026-09-21 08:00", "2026-09-21 18:00",
                       destination="Atlanta, GA")

        found = conflicts.check(mine, {"L1-IIII": theirs})

        assert conflicts.POSITION in [w["level"] for w in found]

    def test_the_basis_is_always_said(self, monkeypatch):
        """*"and the basis is always said"* -- a mileage he cannot check is not
        evidence."""
        from dispatch import distance

        monkeypatch.setattr(distance, "miles_between",
                            lambda o, d, **kw: {"miles": 900, "basis": "provider"})
        mine = _card("NEW", "2026-09-23 08:00", "2026-09-23 18:00",
                     origin="Miami, FL")
        theirs = _card("L1-JJJJ", "2026-09-21 08:00", "2026-09-21 18:00",
                       destination="Atlanta, GA")

        line = conflicts.check(mine, {"L1-JJJJ": theirs})[0]["line"]

        assert "provider" in line

    def test_a_short_hop_raises_nothing(self, monkeypatch):
        from dispatch import distance

        monkeypatch.setattr(distance, "miles_between",
                            lambda o, d, **kw: {"miles": 40, "basis": "provider"})
        mine = _card("NEW", "2026-09-23 08:00", "2026-09-23 18:00")
        theirs = _card("L1-KKKK", "2026-09-21 08:00", "2026-09-21 18:00")

        found = conflicts.check(mine, {"L1-KKKK": theirs})

        assert conflicts.POSITION not in [w["level"] for w in found]


class TestItDecidesNothing:
    """**The half that matters.** *"Display warning only. Do not block. Do not
    reserve capacity. Do not reject commitment."*"""

    def test_checking_writes_nothing_to_the_record(self):
        mine = _card("NEW", "2026-09-21 09:00", "2026-09-21 17:00")
        theirs = _card("L1-LLLL", "2026-09-21 08:00", "2026-09-21 12:00")
        before = dict(mine)

        conflicts.check(mine, {"L1-LLLL": theirs})

        assert mine == before

    def test_it_holds_no_day(self):
        """Every day begins OPEN and a warning does not change that."""
        mine = _card("NEW", "2026-09-21 09:00", "2026-09-21 17:00")
        theirs = _card("L1-MMMM", "2026-09-21 08:00", "2026-09-21 12:00")
        records = {"L1-MMMM": theirs}

        conflicts.check(mine, records)

        assert records == {"L1-MMMM": theirs}

    def test_they_are_types_not_severities(self):
        """One display rule for all three. Nothing ranks them."""
        for warning in (conflicts.POSITION, conflicts.TIME, conflicts.HOS):
            assert isinstance(warning, str)
        source = open("dispatch/conflicts.py", encoding="utf-8").read()
        assert "severity" not in source.lower()

    def test_a_mileage_failure_never_costs_the_screen(self, monkeypatch):
        from dispatch import distance

        def boom(*a, **kw):
            raise RuntimeError("provider down")

        monkeypatch.setattr(distance, "miles_between", boom)
        mine = _card("NEW", "2026-09-23 08:00", "2026-09-23 18:00")
        theirs = _card("L1-NNNN", "2026-09-21 08:00", "2026-09-21 18:00")

        with pytest.raises(RuntimeError):
            conflicts.check(mine, {"L1-NNNN": theirs})


class TestTheWeekModelIsGone:
    """**The board drew one rule and the footer named another.** WEEK_PATTERN
    was opened to seven OPEN days by the doctrine; the Booking screen went on
    printing "Mon-Wed and Sat sellable / Thu-Fri held for expedited / Sun
    closed" underneath it."""

    def test_every_day_is_open(self):
        assert set(booking.WEEK_PATTERN.values()) == {booking.OPEN}

    def test_nothing_produces_a_held_day(self):
        from datetime import date

        for offset in range(7):
            day = date(2026, 9, 21) + __import__("datetime").timedelta(days=offset)
            assert booking.day_state(day, []) == booking.OPEN

    def test_the_legend_no_longer_names_the_abolished_week(self):
        page = open("portal/templates/booking.html", encoding="utf-8").read()
        legend = page.split('class="week-model"')[1].split("</span>")[0]

        assert "held for expedited" not in legend
        assert "Sun" not in legend

    def test_the_headline_no_longer_counts_held_days(self):
        page = open("portal/templates/booking.html", encoding="utf-8").read()

        assert "held_count" not in page

    def test_the_board_no_longer_carries_the_dead_counters(self):
        source = open("dispatch/booking.py", encoding="utf-8").read()
        built = source.split("def month_of")[0]

        assert '"held_count"' not in built
        assert '"held_and_taken"' not in built
