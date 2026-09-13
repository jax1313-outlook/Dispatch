"""Capacity stops built from real loads.

`dispatch/capacity.py` could evaluate stop sequences and appointment windows
from the day it was written, and none of it ran: nothing in production built a
`Stop`, so `scoring.assess_capacity()` called the engine without `stops=`. The
checks had unit tests and no reachable caller -- the most convincing kind of
dead code.

These tests cover the constructor that closes that gap, and most of them are
about what it refuses to invent. A capacity answer built on a guessed dwell or
a guessed drive time is worse than no answer, because it looks like an answer.
"""

from __future__ import annotations

import pytest

from dispatch import load_stops, scoring
from dispatch.capacity import DynamicCapacity, PhysicalCapacity, Stop
from dispatch.load_stops import NOT_RECORDED, UNREADABLE, USABLE, parse_appointment


# ── reading what the operator typed ──────────────────────────────────────


class TestReadingAnAppointment:
    def test_nothing_recorded_is_absent_not_a_guess(self):
        for empty in ("", "   ", None):
            assert parse_appointment(empty).status == NOT_RECORDED

    def test_a_window_gives_both_ends(self):
        a = parse_appointment("2026-07-30 06:00 - 10:00")
        assert a.status == USABLE and a.is_window
        assert a.start.startswith("2026-07-30T06:00")
        assert a.end.startswith("2026-07-30T10:00")

    def test_a_bare_closing_time_inherits_the_opening_date(self):
        """'06:00 - 10:00' plainly means one morning, not a window that closed
        in 1900. The date carries across."""
        a = parse_appointment("2026-07-30 06:00 - 10:00")
        assert a.end[:10] == a.start[:10] == "2026-07-30"

    def test_a_full_date_on_both_sides_spans_days(self):
        a = parse_appointment("2026-07-30 22:00 - 2026-07-31 04:00")
        assert a.start[:10] == "2026-07-30" and a.end[:10] == "2026-07-31"

    def test_a_single_time_is_a_time_and_not_a_window(self):
        """The tempting bug: set end = start and report a complete window.

        A zero-width window demands arrival to the second, so the engine would
        call almost every load infeasible. An honest gap beats a confident
        falsehood in the direction that costs money.
        """
        a = parse_appointment("2026-07-30T06:00:00Z")
        assert a.status == USABLE
        assert a.start and not a.end
        assert not a.is_window
        assert "not a window" in a.note

    def test_unreadable_text_says_so_rather_than_vanishing(self):
        a = parse_appointment("some time tuesday-ish")
        assert a.status == UNREADABLE
        assert not a.start and not a.end
        assert a.note

    def test_every_usable_value_carries_an_offset(self):
        """The whole reason this module exists.

        The engine treats a naive timestamp as BLOCKING, correctly -- '06:00' is
        not an instant. Dispatch's own fields are routinely naive, so passing
        them raw would have turned a correct refusal into a false alarm on
        nearly every load.
        """
        for raw in ("2026-07-30 06:00 - 10:00", "2026-07-30 06:00", "2026-07-30T06:00:00Z"):
            a = parse_appointment(raw)
            for value in (a.start, a.end):
                if value:
                    assert value.endswith("Z") or value[-6] in "+-", value


# ── what the drive leg is allowed to claim ───────────────────────────────


class TestTransitHours:
    @pytest.mark.parametrize("distance", [None, "", 0, 0.0, "abc", -5])
    def test_an_unknown_distance_is_none_never_zero(self, distance):
        """Zero drive hours says the truck arrives the instant it leaves, and
        the engine would project arrivals from it and call tight appointments
        comfortable. None makes it decline instead."""
        assert load_stops.transit_hours({"distance_miles": distance}) is None

    def test_a_recorded_distance_converts(self):
        assert load_stops.transit_hours({"distance_miles": 600}) == 12.0
        assert load_stops.transit_hours({"distance_miles": "250"}) == 5.0

    def test_no_load_in_dispatch_records_a_distance_today(self):
        """Recorded so the day someone adds the field, this test says so."""
        from dispatch.models import Load

        assert not hasattr(Load(), "distance_miles")


# ── building the two stops ───────────────────────────────────────────────


def _load(**over):
    base = {
        "load_id": "LOAD-TEST",
        "pickup_location": "Dallas TX",
        "delivery_location": "Houston TX",
        "pickup_datetime": "2026-07-30 06:00 - 10:00",
        "delivery_datetime": "2026-07-30 16:00 - 20:00",
    }
    base.update(over)
    return base


class TestBuildingTheStops:
    def test_a_load_has_exactly_its_own_two_stops(self):
        """No intermediate stops are derived. That would be route planning, and
        CLAUDE.md 5.5 is explicit that Dispatch builds no second scheduler."""
        stops, _ = load_stops.stops_for_load(_load())
        assert [s.stop_type for s in stops] == ["pickup", "delivery"]
        assert [s.sequence for s in stops] == [1, 2]

    def test_locations_and_windows_come_from_the_load(self):
        stops, _ = load_stops.stops_for_load(_load())
        pickup, delivery = stops
        assert pickup.location == "Dallas TX"
        assert delivery.location == "Houston TX"
        assert pickup.appointment_start.startswith("2026-07-30T06:00")
        assert delivery.appointment_end.startswith("2026-07-30T20:00")

    def test_the_pickup_leg_is_zero_and_that_is_an_anchor(self):
        """Not an unknown. The walk starts the clock at the pickup window;
        getting there is deadhead, which PositionCapacity answers."""
        stops, _ = load_stops.stops_for_load(_load(), drive_hours=4.0)
        assert stops[0].drive_hours_to_stop == 0.0
        assert stops[1].drive_hours_to_stop == 4.0

    def test_an_unrecorded_dwell_stays_none(self):
        stops, gaps = load_stops.stops_for_load(_load())
        assert all(s.service_hours is None for s in stops)
        assert any(g["field"] == "service_hours" for g in gaps)

    def test_a_recorded_dwell_is_used(self):
        stops, gaps = load_stops.stops_for_load(_load(), default_service_hours=1.5)
        assert all(s.service_hours == 1.5 for s in stops)
        assert not any(g["field"] == "service_hours" for g in gaps)


class TestTheGapsAreForAPerson:
    def test_a_missing_appointment_is_reported(self):
        _, gaps = load_stops.stops_for_load(_load(pickup_datetime=""))
        gap = next(g for g in gaps if g["field"] == "pickup_datetime")
        assert gap["status"] == NOT_RECORDED
        assert "cannot check" in gap["message"]

    def test_a_missing_location_is_reported(self):
        _, gaps = load_stops.stops_for_load(_load(delivery_location=""))
        assert any(g["field"] == "delivery_location" for g in gaps)

    def test_a_single_time_is_reported_with_how_to_fix_it(self):
        _, gaps = load_stops.stops_for_load(_load(pickup_datetime="2026-07-30 06:00"))
        gap = next(g for g in gaps if g["field"] == "pickup_datetime")
        assert "closing time" in gap["message"]

    def test_a_missing_distance_is_reported(self):
        _, gaps = load_stops.stops_for_load(_load(), drive_hours=None)
        assert any(g["field"] == "distance_miles" for g in gaps)


# ── the checks that were unreachable, now reached ────────────────────────


def _asset():
    capacity = DynamicCapacity(equipment_id="EQ-TEST")
    capacity.physical = PhysicalCapacity(
        max_weight_lbs=44000, max_linear_feet=53, max_pallets=26
    )
    return capacity


def _findings(load, **kw):
    stops, _ = load_stops.stops_for_load(
        load, drive_hours=load_stops.transit_hours(load), **kw
    )
    result = scoring.assess_capacity(load, _asset(), stops=stops).to_dict()
    return [f for f in result["findings"] if f["dimension"].upper() == "STOP_SEQUENCE"], result


def _codes(findings, severity=None):
    return {f["code"] for f in findings if severity is None or f["severity"] == severity}


class TestChecksThatHadNoCallerBefore:
    def test_a_delivery_that_opens_before_its_pickup_is_blocking(self):
        findings, _ = _findings(
            _load(
                pickup_datetime="2026-07-30 14:00 - 18:00",
                delivery_datetime="2026-07-30 06:00 - 10:00",
            )
        )
        assert "STOP_APPOINTMENT_CONFLICT" in _codes(findings, "BLOCKING")

    def test_a_window_that_closes_before_it_opens_is_blocking(self):
        findings, _ = _findings(_load(pickup_datetime="2026-07-30 18:00 - 06:00"))
        assert "STOP_APPOINTMENT_WINDOW_INVALID" in _codes(findings, "BLOCKING")

    def test_a_sound_load_raises_nothing_blocking(self):
        """The other half of the bargain. A check that fires on good data is
        noise, and noise is how a real finding gets scrolled past."""
        findings, _ = _findings(_load())
        assert _codes(findings, "BLOCKING") == set()

    def test_naive_timestamps_do_not_become_blocking_findings(self):
        """Before this constructor existed, feeding the engine Dispatch's own
        naive fields would have blocked nearly every load."""
        findings, _ = _findings(
            _load(pickup_datetime="2026-07-30 06:00 - 10:00",
                  delivery_datetime="2026-07-30 16:00 - 20:00")
        )
        assert "STOP_APPOINTMENT_TIMESTAMP_UNUSABLE" not in _codes(findings)


class TestTheForwardWalk:
    def test_it_stays_off_without_a_dwell_and_a_distance(self):
        _, result = _findings(_load())
        assert result["stop_sequence"]["appointments_evaluated"] is False
        assert result["stop_sequence"]["projected_arrivals"] == []

    def test_it_turns_on_when_both_are_known(self):
        _, result = _findings(_load(distance_miles=600), default_service_hours=1.5)
        assert result["stop_sequence"]["appointments_evaluated"] is True
        assert len(result["stop_sequence"]["projected_arrivals"]) == 2

    def test_an_unreachable_delivery_window_is_blocking(self):
        findings, _ = _findings(
            _load(distance_miles=600, delivery_datetime="2026-07-30 12:00 - 14:00"),
            default_service_hours=1.5,
        )
        assert "STOP_APPOINTMENT_INFEASIBLE" in _codes(findings, "BLOCKING")

    def test_the_same_load_with_room_is_not_blocking(self):
        findings, _ = _findings(
            _load(distance_miles=600, delivery_datetime="2026-07-31 06:00 - 12:00"),
            default_service_hours=1.5,
        )
        assert "STOP_APPOINTMENT_INFEASIBLE" not in _codes(findings)


class TestTheServiceCall:
    def test_assess_load_capacity_returns_the_gaps(self, tmp_path, monkeypatch):
        from dispatch import capacity_store, services
        from dispatch.db import set_db_path

        monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
        set_db_path(tmp_path / "dispatch.db")
        try:
            truck = services.create_equipment(unit_number="T-9", equipment_type="dry_van")
            capacity = DynamicCapacity(equipment_id=truck["equipment_id"])
            capacity.physical = PhysicalCapacity(max_weight_lbs=44000)
            capacity_store.save_profile(capacity)

            created = services.create_load(
                customer="Gap Co",
                equipment_id=truck["equipment_id"],
                pickup_location="Dallas TX",
                delivery_location="Houston TX",
                pickup_datetime="2026-07-30 14:00 - 18:00",
                delivery_datetime="2026-07-30 06:00 - 10:00",
            )
            result = services.assess_load_capacity(created["load_id"])

            assert result["status"] == "LIVE"
            assert isinstance(result["stop_gaps"], list)
            codes = {
                f["code"]
                for f in result["assessment"]["findings"]
                if f["dimension"].upper() == "STOP_SEQUENCE"
            }
            assert "STOP_APPOINTMENT_CONFLICT" in codes
        finally:
            set_db_path(None)

    def test_the_dwell_setting_is_read_and_validated(self, monkeypatch):
        from dispatch import services

        monkeypatch.delenv("DISPATCH_DEFAULT_DWELL_HOURS", raising=False)
        assert services.default_dwell_hours() is None
        monkeypatch.setenv("DISPATCH_DEFAULT_DWELL_HOURS", "1.5")
        assert services.default_dwell_hours() == 1.5
        for rubbish in ("", "  ", "not-a-number", "-3"):
            monkeypatch.setenv("DISPATCH_DEFAULT_DWELL_HOURS", rubbish)
            assert services.default_dwell_hours() is None
