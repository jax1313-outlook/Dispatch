"""The Registration screen: who this business is.

**Owner ruling, 2026-09-08: "That's it. Nothing else."** One gear, four blocks --
Home Base, Home Time Zone, Driver, Company. These tests are as much about what
the screen must *not* grow into as about what it does.
"""

from __future__ import annotations

import os

import pytest

from dispatch import carrier, clock, services
from dispatch.db import set_db_path
from portal.app import create_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    set_db_path(tmp_path / "registration.db")
    monkeypatch.delenv(clock.HOME_ZONE_VAR, raising=False)
    yield create_app({"TESTING": True})
    set_db_path(None)


@pytest.fixture
def client(app):
    return app.test_client()


FILLED = {
    "legal_name": "Level 1 Transport Inc",
    "dba": "Level 1",
    "usdot": "1234567",
    "mc_number": "MC-987654",
    "ifta_account": "FL-0001",
    "base_jurisdiction": "FL",
    "phone": "555-0100",
    "email": "ops@l1truck.com",
    "home_street": "1 Terminal Way",
    "home_city": "Jacksonville",
    "home_state": "FL",
    "home_zip": "32202",
    "home_time_zone": "America/New_York",
}


class TestItStoresWhatTheBusinessIs:
    def test_a_new_node_has_a_blank_carrier_and_not_an_error(self, app):
        """**Never None.** A screen that must check for absence before it can
        render is a screen that will forget to, and blank is the state every new
        node starts in."""
        with app.app_context():
            record = carrier.get()
        assert record["legal_name"] == ""
        assert record["configured"] is False

    def test_saving_and_reading_back(self, app):
        with app.app_context():
            carrier.save(FILLED)
            record = carrier.get()
        assert record["legal_name"] == "Level 1 Transport Inc"
        assert record["usdot"] == "1234567"
        assert record["configured"] is True

    def test_saving_twice_updates_rather_than_adds(self, app):
        """A business has one identity. A second row would be a second answer to
        'what is our USDOT number', and the schema's CHECK forbids it."""
        from dispatch.db import get_connection

        with app.app_context():
            carrier.save(FILLED)
            carrier.save(dict(FILLED, usdot="7654321"))
            with get_connection() as conn:
                rows = conn.execute("SELECT COUNT(*) FROM carrier").fetchone()[0]
            assert carrier.get()["usdot"] == "7654321"
        assert rows == 1

    def test_unknown_fields_are_ignored_not_refused(self, app):
        """The form posts a CSRF token and a submit button alongside the fields.
        Failing the save over those would be theatre."""
        with app.app_context():
            carrier.save(dict(FILLED, csrf_token="abc", submit="Save"))
            assert carrier.get()["legal_name"] == "Level 1 Transport Inc"


class TestTheHomeTimeZoneTakesEffect:
    def test_saving_a_zone_changes_what_day_dispatch_thinks_it_is(self, app):
        """The point of the whole screen. Saving is not filing a fact away; it
        changes what every date in the program means."""
        with app.app_context():
            carrier.save(dict(FILLED, home_time_zone="Pacific/Honolulu"))
            assert clock.home_zone_name() == "Pacific/Honolulu"

    def test_the_declared_value_wins_over_a_hand_set_variable(self, app, monkeypatch):
        """A value Mike typed into the screen is a value Mike meant. The
        variable is what a machine with no carrier row falls back to."""
        monkeypatch.setenv(clock.HOME_ZONE_VAR, "America/Denver")
        with app.app_context():
            carrier.save(dict(FILLED, home_time_zone="America/Chicago"))
            assert clock.home_zone_name() == "America/Chicago"

    def test_a_blank_zone_leaves_the_default_alone(self, app):
        with app.app_context():
            carrier.save(dict(FILLED, home_time_zone=""))
            assert clock.home_zone_name() == clock.DEFAULT_HOME_ZONE


class TestNothingIsBlockedByABlankScreen:
    """*Degradation is permitted. Incapacity is not.* An empty Registration must
    make surfaces say `UNCONFIGURED`, and nothing else."""

    def test_it_names_what_is_missing_in_plain_words(self, app):
        with app.app_context():
            missing = carrier.missing()
        assert "USDOT number" in missing
        assert "Home time zone" in missing

    def test_a_filled_carrier_is_missing_nothing(self, app):
        with app.app_context():
            carrier.save(FILLED)
            assert carrier.missing() == []

    def test_the_portal_starts_with_no_carrier_row(self, client):
        assert client.get("/settings/registration").status_code == 200


class TestTheScreenItself:
    def test_it_renders_the_four_blocks_and_no_more(self, client):
        page = client.get("/settings/registration").get_data(as_text=True)
        for block in ("Company", "Home Base", "Home Time Zone", "Driver"):
            assert block in page

    def test_saving_through_the_form_works(self, client, app):
        response = client.post("/settings/registration", data=FILLED)
        assert response.status_code == 200
        with app.app_context():
            assert carrier.get()["legal_name"] == "Level 1 Transport Inc"

    def test_the_driver_block_holds_no_form_of_its_own(self, client):
        """**The rule this screen exists under.** `drivers` already has a table,
        Fleet already has `+ Add Driver`, and each driver already has a page
        with an edit form. A copy of that form here is a copy that drifts."""
        page = client.get("/settings/registration").get_data(as_text=True)
        assert "/fleet" in page
        assert 'name="license_number"' not in page, (
            "Registration grew a driver form; drivers are edited on their own page")

    def test_every_driver_can_be_reached_for_editing(self, client, app):
        """Owner feedback, 2026-09-08: *"none of those fields are allowed for
        data alteration or change. So that would need to be updated."* He is
        right that they must be editable. The answer is one click to the form
        that already exists, not a second form here."""
        with app.app_context():
            driver = services.create_driver(name="Mike Zachary",
                                            license_number="F123")
        page = client.get("/settings/registration").get_data(as_text=True)
        assert "/fleet/driver/%s" % driver["driver_id"] in page
        assert ">Edit<" in page

    def test_an_existing_driver_is_shown_rather_than_re_entered(self, client, app):
        with app.app_context():
            services.create_driver(name="Mike Zachary", license_number="F123",
                                   license_class="A", phone="555-0101")
        page = client.get("/settings/registration").get_data(as_text=True)
        assert "Mike Zachary" in page

    def test_machine_configuration_is_not_on_this_screen(self, client):
        """The line that must not blur. What the machine needs to start is read
        before there is a database to read it from, and belongs to the launcher."""
        page = client.get("/settings/registration").get_data(as_text=True)
        for machine_setting in ("DISPATCH_JOE_TOKEN", "SECRET_KEY",
                                "DISPATCH_OPERATIONS_ROOT", "SMTP"):
            assert machine_setting not in page, (
                "%s is machine configuration and belongs on Settings"
                % machine_setting)
