"""An appointment time an operator typed is stored so it cannot be misread.

Found while wiring the capacity engine into production, and it is the reason
wiring it would otherwise have made every load unassessable.

`capacity.parse_operational_timestamp` is right about the hard part -- "a pickup
window in an unstated zone is genuinely ambiguous, and guessing costs a load" --
and returns TIMESTAMP_NAIVE for a value with no offset, which the caller turns
into a SEVERITY_BLOCKING finding. The load form's own placeholder was
`YYYY-MM-DD HH:MM`: a naive timestamp. Every load entered in the documented
format would have produced a blocking capacity finding, and the conclusion a
person draws from that is "the capacity engine refuses everything".

The same gap had a quieter effect. `get_load_calendar()` selected a month by
string prefix on a free-text field, so a load typed as `9/14/2026 08:00` -- the
format a US dispatcher writes by hand, accepted without complaint by a
`type="text"` input -- was simply not on the calendar. No error, no warning, no
row.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from dispatch import services, timestamps
from dispatch.capacity import (
    TIMESTAMP_NAIVE,
    TIMESTAMP_PARSED,
    parse_operational_timestamp,
)
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _eastern(monkeypatch):
    monkeypatch.setenv("DISPATCH_OPERATING_TIMEZONE", "America/New_York")


@pytest.fixture
def database(tmp_path):
    set_db_path(tmp_path / "dispatch.db")
    try:
        yield
    finally:
        set_db_path(None)


class TestNormalisation:
    @pytest.mark.parametrize(
        "typed",
        [
            "2026-09-14 08:00",
            "2026-09-14T08:00",
            "2026-09-14T08:00:00",
            "9/14/2026 08:00",
            "9/14/2026 8:00 AM",
            "09/14/2026 8:00 a.m.",
        ],
    )
    def test_every_format_an_operator_types_becomes_the_same_instant(self, typed):
        result = timestamps.normalize(typed)
        assert result["status"] == timestamps.NORMALIZED
        assert result["instant"] == datetime(
            2026, 9, 14, 12, 0, tzinfo=timezone.utc
        ), f"{typed!r} -> {result['value']}"

    def test_a_value_that_already_carries_an_offset_is_left_alone(self):
        """Re-serialising a correct value changes it for no reason, and for
        anything comparing stored strings that is a change."""
        result = timestamps.normalize("2026-09-14T08:00:00Z")
        assert result["status"] == timestamps.ALREADY_OFFSET
        assert result["value"] == "2026-09-14T08:00:00Z"

    def test_what_cannot_be_read_is_kept_exactly_as_typed(self):
        result = timestamps.normalize("next tuesday, after the Dallas run")
        assert result["status"] == timestamps.UNVERIFIED
        assert result["value"] == "next tuesday, after the Dallas run"
        assert "could not read" in result["note"]

    def test_empty_is_missing_not_an_error(self):
        for value in ("", "   ", None):
            assert timestamps.normalize(value)["status"] == timestamps.MISSING

    def test_daylight_saving_is_taken_from_the_zone_not_assumed(self):
        summer = timestamps.normalize("2026-07-14 08:00")["value"]
        winter = timestamps.normalize("2026-01-14 08:00")["value"]
        assert summer.endswith("-04:00")
        assert winter.endswith("-05:00")


class TestTheCapacityEngineAcceptsWhatTheFormProduces:
    """The whole point. Before this, it did not."""

    def test_the_documented_input_format_is_no_longer_blocking(self):
        raw = "2026-09-14 08:00"
        assert parse_operational_timestamp(raw)[1] == TIMESTAMP_NAIVE

        stored = timestamps.normalize(raw)["value"]
        parsed, status = parse_operational_timestamp(stored)
        assert status == TIMESTAMP_PARSED
        assert parsed == datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)

    def test_a_load_created_through_the_service_is_assessable(self, database):
        load = services.create_load(customer="Acme", pickup_datetime="2026-09-14 08:00")
        stored = services.get_load(load["load_id"])["pickup_datetime"]
        assert parse_operational_timestamp(stored)[1] == TIMESTAMP_PARSED

    def test_an_updated_appointment_is_normalised_too(self, database):
        load = services.create_load(customer="Acme")
        services.update_load(load["load_id"], pickup_datetime="9/14/2026 8:00 AM")
        stored = services.get_load(load["load_id"])["pickup_datetime"]
        assert parse_operational_timestamp(stored)[1] == TIMESTAMP_PARSED


class TestTheCalendarStopsLosingLoads:
    def test_a_us_format_appointment_appears(self, database):
        load = services.create_load(customer="Acme", pickup_datetime="9/14/2026 08:00")
        calendar = services.get_load_calendar(2026, 9)
        assert "2026-09-14" in calendar["pickups"]
        assert calendar["pickups"]["2026-09-14"][0]["load_id"] == load["load_id"]

    def test_the_day_is_the_operators_day_not_the_strings(self, database):
        """A delivery at 2026-09-15T01:00Z is the evening of the 14th in Eastern
        time. It used to be filed on the 15th because the day was sliced off the
        raw string."""
        services.create_load(customer="Acme", delivery_datetime="2026-09-15T01:00:00Z")
        calendar = services.get_load_calendar(2026, 9)
        assert "2026-09-14" in calendar["deliveries"]
        assert "2026-09-15" not in calendar["deliveries"]

    def test_an_unreadable_appointment_is_reported_not_dropped(self, database):
        load = services.create_load(customer="Acme", pickup_datetime="whenever they call")
        calendar = services.get_load_calendar(2026, 9)
        assert any(u["load_id"] == load["load_id"] for u in calendar["unreadable"])

    def test_the_calendar_names_the_zone_it_is_showing(self, database):
        assert "New_York" in services.get_load_calendar(2026, 9)["timezone"]


class TestDisplay:
    def test_a_person_reads_a_time_not_an_iso_string(self):
        rendered = timestamps.describe("2026-09-14 08:00")
        assert "14 Sep 2026" in rendered
        assert "08:00" in rendered
        assert "EDT" in rendered
        assert "T08:00:00-04:00" not in rendered

    def test_an_unreadable_value_is_shown_as_typed(self):
        assert timestamps.describe("call the broker") == "call the broker"

    def test_the_rate_confirmation_a_broker_receives_is_readable(self, database, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "PortalData"))
        from portal.app import create_app

        app = create_app({"TESTING": True})
        app.config["LOGIN_DISABLED"] = True
        client = app.test_client()

        load = services.create_load(customer="Acme", pickup_datetime="2026-09-14 08:00")
        services.confirm_rate(load["load_id"], rate_amount=1500.0, confirmed_by="Mike")
        html = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print").get_data(as_text=True)
        assert "14 Sep 2026, 08:00" in html


class TestFallbacks:
    def test_an_unavailable_zone_still_produces_an_unambiguous_value(self, monkeypatch):
        """A missing tzdata is a deployment fact, not a reason to refuse to start
        -- but the screen has to say which zone it actually used."""
        monkeypatch.setenv("DISPATCH_OPERATING_TIMEZONE", "Mars/Olympus_Mons")
        result = timestamps.normalize("2026-09-14 08:00")
        assert result["status"] == timestamps.NORMALIZED
        assert parse_operational_timestamp(result["value"])[1] == TIMESTAMP_PARSED
        assert "unavailable" in timestamps.timezone_name()
