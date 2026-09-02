"""Editing the brief, and the COMMIT that ends Booking.

The brief is where the work of a broker call lands. Broker phone, broker email,
pickup contact, pickup hours, delivery appointment, customer contact, a rate
that moved, notes from the negotiation -- all of it is discovered on the phone
and none of it exists until somebody writes it down.

So every field on the sheet is editable, including the per-stop ones: on a
multi-stop run the dock phone and the party holding load control are exactly
what the call is for.

Then COMMIT. Not a status change -- the moment it is pressed capacity is taken,
a calendar entry is held, and the mission enters the driver's workflow. That is
why the brief comes first.
"""

from __future__ import annotations

import pytest

from dispatch import commitment
from portal import brief
from portal.models import sandbox


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    # COMMIT asks Outlook to hold the time. No test may reach a real calendar.
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


@pytest.fixture()
def mission():
    entry = sandbox.create_entry(
        source_type="dispatch", source_id="EDIT-1", title="Edit probe",
        card_data={"load_id": "EDIT-1"}, summary="")
    data = sandbox._load()
    data[entry["id"]]["stops"] = [
        {"number": 1, "label": "STOP 1", "facility": "Mayo Clinic"},
        {"number": 2, "label": "STOP 2", "facility": "Publix DC Lakeland"},
    ]
    sandbox._save(data)
    return entry["id"]


class TestEveryFieldIsEditable:
    def test_what_a_broker_call_produces_can_all_be_written_in(self, client, mission):
        """The operator's own list of what gets discovered on the phone."""
        client.post(f"/brief/mission/{mission}/save", data={
            "customer_phone": "904-555-0199",
            "customer_email": "sally@xpo.example",
            "pickup_contact": "Fred Jones",
            "pickup_notes": "Gate opens 05:00",
            "delivery_window": "2026-09-02 12:00",
            "customer_poc": "Sally Smith",
            "rate": "950",
            "notes": "Agreed 950 with Sally, detention after 2 hours",
        })
        record = sandbox.get(mission)
        assert record["customer_phone"] == "904-555-0199"
        assert record["customer_email"] == "sally@xpo.example"
        assert record["pickup_contact"] == "Fred Jones"
        assert record["rate"] == "950"
        assert "detention" in record["notes"]

    def test_no_section_field_is_left_read_only(self):
        """Every field the template can capture carries an edit key."""
        card = brief.card_for({"card_data": {}})
        for section in card["sections"]:
            if not section["editable"]:
                continue
            assert all(f["key"] for f in section["fields"]), section["title"]

    def test_stop_fields_are_editable_too(self, client, mission):
        """On a multi-stop run the dock phone and who holds load control are
        exactly what the call is for."""
        client.post(f"/brief/mission/{mission}/save", data={
            "stop:2:phone": "863-555-0114",
            "stop:2:poc": "Dock 7 - K. Mills",
            "stop:2:control_name": "Gulf Coast Paper",
            "stop:2:control_role": "shipper",
        })
        stops = sandbox.get(mission)["stops"]
        assert stops[1]["phone"] == "863-555-0114"
        assert stops[1]["control_name"] == "Gulf Coast Paper"

    def test_editing_one_stop_leaves_the_others_alone(self, client, mission):
        client.post(f"/brief/mission/{mission}/save",
                    data={"stop:2:phone": "863-555-0114"})
        stops = sandbox.get(mission)["stops"]
        assert stops[0].get("phone", "") == ""
        assert stops[0]["facility"] == "Mayo Clinic"

    def test_the_resolved_control_is_rebuilt_after_an_edit(self, client, mission):
        """The stop card reads a resolved block, so writing the raw field and
        leaving the resolved one stale would show the old party."""
        client.post(f"/brief/mission/{mission}/save",
                    data={"stop:2:control_name": "Gulf Coast Paper",
                          "stop:2:control_role": "shipper"})
        stop = sandbox.get(mission)["stops"][1]
        assert stop["control"]["name"] == "Gulf Coast Paper"
        assert stop["control"]["role_label"] == "Shipper"

    def test_the_edit_screen_shows_an_input_for_every_editable_field(self, client,
                                                                    mission):
        html = client.get(f"/brief/mission/{mission}?edit=1").get_data(as_text=True)
        card = brief.card_for(sandbox.get(mission))
        expected = sum(1 for s in card["sections"] if s["editable"]
                       for f in s["fields"] if f["key"])
        expected += sum(len(s["fields"]) for s in card["stops"])
        assert html.count('<input type="text"') == expected

    def test_a_field_that_was_not_sent_is_not_cleared(self, client, mission):
        """Two calls, two facts. The second must not wipe the first."""
        client.post(f"/brief/mission/{mission}/save", data={"rate": "950"})
        client.post(f"/brief/mission/{mission}/save", data={"customer_poc": "Sally"})
        record = sandbox.get(mission)
        assert record["rate"] == "950" and record["customer_poc"] == "Sally"


class TestTheCommitGate:
    def test_a_new_record_is_a_candidate(self, client, mission):
        html = client.get(f"/brief/mission/{mission}").get_data(as_text=True)
        assert "CANDIDATE" in html
        assert "COMMIT LOAD" in html

    def test_committing_sets_the_timestamp(self, client, mission):
        client.post(f"/brief/mission/{mission}/commit")
        assert commitment.is_committed(sandbox.get(mission))

    def test_it_creates_nothing(self, client, mission):
        """The record SWEEP found is the record that runs."""
        before = set(sandbox.get_all())
        client.post(f"/brief/mission/{mission}/commit")
        assert set(sandbox.get_all()) == before

    def test_a_committed_record_offers_no_second_commit(self, client, mission):
        client.post(f"/brief/mission/{mission}/commit")
        html = client.get(f"/brief/mission/{mission}").get_data(as_text=True)
        assert "COMMIT LOAD" not in html
        assert "COMMITTED" in html

    def test_committing_twice_does_not_move_the_timestamp(self, client, mission):
        client.post(f"/brief/mission/{mission}/commit")
        first = commitment.committed_at(sandbox.get(mission))
        client.post(f"/brief/mission/{mission}/commit")
        assert commitment.committed_at(sandbox.get(mission)) == first

    def test_it_records_whether_outlook_took_the_appointment(self, client, mission):
        """Committing must not depend on whether Outlook happens to be open,
        and a mission that quietly failed to reach the calendar is how an
        appointment gets missed."""
        client.post(f"/brief/mission/{mission}/commit")
        hold = sandbox.get(mission)["calendar_hold"]
        assert hold["held"] is False          # Outlook forced closed here
        assert "yourself" in hold["note"].lower()

    def test_a_failed_calendar_hold_does_not_undo_the_commitment(self, client,
                                                                mission):
        client.post(f"/brief/mission/{mission}/commit")
        record = sandbox.get(mission)
        assert commitment.is_committed(record)
        assert record["calendar_hold"]["held"] is False

    def test_committing_gives_it_a_mission_number(self, client, mission):
        client.post(f"/brief/mission/{mission}/commit")
        assert sandbox.get(mission)["mission_number"]

    def test_it_leaves_a_trail(self, client, mission):
        client.post(f"/brief/mission/{mission}/commit")
        actions = [e.get("action") for e in sandbox.get(mission).get("events", [])]
        assert "committed" in actions

    def test_an_unknown_mission_commits_nothing(self, client):
        assert client.post("/brief/mission/NOPE/commit").status_code == 302
        assert sandbox.get("NOPE") is None


class TestCommittingChangesWhatBookingShows:
    def test_a_committed_load_takes_the_day(self, client, mission):
        from datetime import date

        from dispatch import booking

        client.post(f"/brief/mission/{mission}/save",
                    data={"pickup_window": date(2026, 9, 7).isoformat()})
        before = booking.build(sandbox.get_all(), {}, today=date(2026, 9, 7))
        assert before["board"][0]["state"] == booking.OPEN

        client.post(f"/brief/mission/{mission}/commit")
        after = booking.build(sandbox.get_all(), {}, today=date(2026, 9, 7))
        assert after["board"][0]["state"] == booking.BOOKED
