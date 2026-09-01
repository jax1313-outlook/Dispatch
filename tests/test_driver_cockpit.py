"""The Driver Cockpit: one screen, three modes, nothing moving between them.

Pinned from the operator's design record of 31 August 2026. These tests are
mostly about restraint -- what the screen refuses to do -- because the failures
that matter here are a layout that shifts under a driver's eye and a checklist
that closes itself while he is counting pallets on a dock.
"""

from __future__ import annotations

import re

import pytest

from portal import cockpit


RECORD = {
    "id": "SBX-1",
    "title": "Dry Van - Jacksonville FL to Atlanta GA",
    "numbers": {"mission_label": "Mission 1", "load_label": "Load 847261"},
    "card_data": {"origin": "Jacksonville, FL", "destination": "Atlanta, GA",
                  "commodity": "CNC spare assemblies",
                  "pallets": 4, "pieces": 4, "weight_lbs": 8400},
    "pickup_window": "07:00 - 08:30 EST",
    "delivery_window": "13:30 - 15:00 EST",
    "broker": "Southeast Logistics Partners",
    "broker_phone": "(904) 555-0199",
}


class TestTheThreeModes:
    def test_the_three_modes(self):
        assert [m["label"] for m in cockpit.MODES] == ["PICKUP", "CURRENT", "DELIVERY"]

    def test_an_in_transit_url_still_opens(self):
        """A link written while the label read IN TRANSIT must not land elsewhere."""
        assert cockpit.normalise_mode("IN_TRANSIT") == cockpit.MODE_IN_TRANSIT

    def test_a_current_url_opens(self):
        assert cockpit.normalise_mode("CURRENT") == cockpit.MODE_IN_TRANSIT

    def test_an_unknown_mode_falls_back_rather_than_failing(self):
        assert cockpit.normalise_mode("nonsense") == cockpit.MODE_IN_TRANSIT
        assert cockpit.normalise_mode(None) == cockpit.MODE_IN_TRANSIT

    def test_in_transit_maps_onto_the_resolver(self):
        assert cockpit.backend_view(cockpit.MODE_IN_TRANSIT) == "CURRENT"
        assert cockpit.backend_view(cockpit.MODE_PICKUP) == "PICKUP"


class TestEmphasisNotHiding:
    """The mode changes which end is bright, never which end exists."""

    def test_pickup_mode_brightens_pickup(self):
        e = cockpit.emphasis_for(cockpit.MODE_PICKUP)
        assert e["pickup"] == "bright" and e["delivery"] == "subdued"

    def test_delivery_mode_brightens_delivery(self):
        e = cockpit.emphasis_for(cockpit.MODE_DELIVERY)
        assert e["delivery"] == "bright" and e["pickup"] == "subdued"

    def test_in_transit_favours_neither(self):
        assert cockpit.emphasis_for(cockpit.MODE_IN_TRANSIT) == {
            "pickup": "neutral", "delivery": "neutral"}

    @pytest.mark.parametrize("mode", [cockpit.MODE_PICKUP,
                                      cockpit.MODE_IN_TRANSIT,
                                      cockpit.MODE_DELIVERY])
    def test_no_mode_ever_hides_an_end(self, mode):
        """Orientation is lost the moment one end disappears."""
        emphasis = cockpit.emphasis_for(mode)
        assert set(emphasis) == {"pickup", "delivery"}
        assert "hidden" not in emphasis.values()


class TestNothingMovesBetweenModes:
    """The layout is static. Only contents, emphasis and live actions change."""

    def _keys(self, mode):
        return sorted(cockpit.cockpit_context(RECORD, mode))

    def test_every_mode_produces_the_same_slots(self):
        assert (self._keys(cockpit.MODE_PICKUP)
                == self._keys(cockpit.MODE_IN_TRANSIT)
                == self._keys(cockpit.MODE_DELIVERY))

    def test_every_mode_produces_the_same_drawers_in_the_same_order(self):
        def order(mode):
            return [d["key"] for d in cockpit.drawers_for(RECORD, mode)]
        assert (order(cockpit.MODE_PICKUP)
                == order(cockpit.MODE_IN_TRANSIT)
                == order(cockpit.MODE_DELIVERY))

    def test_a_drawer_always_opens_from_the_same_side(self):
        """A control that changes sides between modes is a control relearned."""
        def sides(mode):
            return {d["key"]: d["side"] for d in cockpit.drawers_for(RECORD, mode)}
        assert sides(cockpit.MODE_PICKUP) == sides(cockpit.MODE_DELIVERY)


class TestDocumentStatus:
    def test_only_two_states_exist(self):
        assert {cockpit.STATUS_READY, cockpit.STATUS_COMPLETE} == {"READY", "COMPLETE"}

    def test_the_label_carries_the_mode(self):
        assert cockpit.document_status(RECORD, cockpit.MODE_PICKUP)["label"] == "PICKUP - READY"
        assert cockpit.document_status(RECORD, cockpit.MODE_DELIVERY)["label"] == "DELIVERY - READY"

    def test_complete_only_when_every_artifact_is_held(self):
        held = dict(RECORD, arrived_at="2026-08-31T10:00:00Z",
                    artifacts_held=list(cockpit.PICKUP_ARTIFACTS))
        assert cockpit.document_status(held, cockpit.MODE_PICKUP)["state"] == "COMPLETE"

    def test_holding_every_document_is_not_complete_without_arriving(self):
        """The Arrival Notice is satisfied by pressing ARRIVE, not by filing."""
        held = dict(RECORD, artifacts_held=list(cockpit.PICKUP_ARTIFACTS))
        assert cockpit.document_status(held, cockpit.MODE_PICKUP)["state"] == "READY"

    def test_one_missing_artifact_is_not_complete(self):
        held = dict(RECORD, artifacts_held=list(cockpit.PICKUP_ARTIFACTS[:-1]))
        assert cockpit.document_status(held, cockpit.MODE_PICKUP)["state"] == "READY"

    def test_the_checklist_holds_artifacts_not_information(self):
        """A working list of what the driver must obtain. Addresses, contacts
        and instructions live in the details drawers, not here."""
        labels = [i["label"].lower()
                  for i in cockpit.document_checklist(RECORD, cockpit.MODE_PICKUP)]
        assert any("bill of lading" in label for label in labels)
        assert not any("address" in label or "contact" in label
                       or "instruction" in label for label in labels)

    def test_the_load_diagram_is_not_a_checklist_item(self):
        """Ruled: a mission-execution item he works from, not an artifact he
        collects and hands over."""
        for mode in (cockpit.MODE_PICKUP, cockpit.MODE_DELIVERY):
            labels = [i["label"].lower()
                      for i in cockpit.document_checklist(RECORD, mode)]
            assert not any("load diagram" in label for label in labels)

    def test_the_arrival_notice_leads_both_lists(self):
        for mode in (cockpit.MODE_PICKUP, cockpit.MODE_DELIVERY):
            first = cockpit.document_checklist(RECORD, mode)[0]["label"]
            assert first == cockpit.ARRIVAL_NOTICE

    def test_the_arrival_notice_ticks_itself_once_arrived(self):
        """Dispatch generated and sent it. Asking him to fetch it is nonsense."""
        arrived = dict(RECORD, arrived_at="2026-08-31T10:00:00Z")
        assert cockpit.document_checklist(arrived, cockpit.MODE_PICKUP)[0]["done"] is True
        assert cockpit.document_checklist(RECORD, cockpit.MODE_PICKUP)[0]["done"] is False

    def test_the_checklist_drawer_is_sticky(self):
        """Worked from while walking a dock. A stray touch must not shut it."""
        docs = [d for d in cockpit.drawers_for(RECORD, cockpit.MODE_PICKUP)
                if d["key"] == "documents"][0]
        assert docs.get("sticky") is True


class TestArrive:
    """A mission transition event, not a status button."""

    def test_it_is_live_at_both_ends(self):
        assert cockpit.arrive_for(RECORD, cockpit.MODE_PICKUP)["available"]
        assert cockpit.arrive_for(RECORD, cockpit.MODE_DELIVERY)["available"]

    def test_it_is_not_live_in_transit(self):
        """You cannot arrive somewhere you are still driving towards."""
        assert not cockpit.arrive_for(RECORD, cockpit.MODE_IN_TRANSIT)["available"]

    def test_it_knows_which_packet_it_starts(self):
        assert "pickup" in cockpit.arrive_for(RECORD, cockpit.MODE_PICKUP)["sub"].lower()
        assert "delivery" in cockpit.arrive_for(RECORD, cockpit.MODE_DELIVERY)["sub"].lower()


class TestFacilityMap:
    def test_it_targets_the_active_end(self):
        assert "Jacksonville" in cockpit.facility_map_for(RECORD, cockpit.MODE_PICKUP)["target"]
        assert "Atlanta" in cockpit.facility_map_for(RECORD, cockpit.MODE_DELIVERY)["target"]

    def test_coordinates_beat_an_address_when_given(self):
        """Hazmat bills often carry GPS. Prefer it."""
        record = dict(RECORD, delivery_gps="33.7490,-84.3880")
        target = cockpit.facility_map_for(record, cockpit.MODE_DELIVERY)["target"]
        assert target == "33.7490,-84.3880"

    def test_there_is_no_map_in_transit(self):
        """The driver is using truck navigation."""
        assert not cockpit.facility_map_for(RECORD, cockpit.MODE_IN_TRANSIT)["available"]

    def test_no_address_means_no_button(self):
        bare = {"numbers": {}, "card_data": {}}
        assert not cockpit.facility_map_for(bare, cockpit.MODE_PICKUP)["available"]


class TestStops:
    def test_a_single_stop_run_reports_one_of_one(self):
        stops = cockpit.stops_for(RECORD)
        assert stops["number"] == 1 and stops["total"] == 1

    def test_a_multi_stop_run_counts(self):
        stops = cockpit.stops_for(dict(RECORD, stop_number=2, stop_total=5))
        assert stops["number"] == 2 and stops["total"] == 5
        assert "3" in stops["next_sub"]

    def test_the_last_stop_says_so_rather_than_offering_a_sixth(self):
        stops = cockpit.stops_for(dict(RECORD, stop_number=5, stop_total=5))
        assert "last stop" in stops["next_sub"].lower()

    def test_a_nonsense_stop_number_does_not_crash_the_cab(self):
        stops = cockpit.stops_for(dict(RECORD, stop_number="x", stop_total=None))
        assert stops["number"] == 1 and stops["total"] == 1


class TestItInventsNothing:
    def test_a_bare_record_still_renders(self):
        context = cockpit.cockpit_context({"numbers": {}, "card_data": {}},
                                          cockpit.MODE_IN_TRANSIT)
        assert context["ends"]["pickup"]["place"] == "—"

    def test_missing_cargo_says_so_rather_than_guessing(self):
        cargo = cockpit.cargo_for({"numbers": {}, "card_data": {}})
        assert cargo["description"] == "Not stated"
        assert "no cargo detail" in cargo["brackets"]

    def test_the_checklists_are_the_operators_lists_not_invented_ones(self):
        """Specified on 31 August 2026. Nothing added, nothing dropped."""
        assert cockpit.PICKUP_ARTIFACTS == (
            "Arrival Notice",
            "Packing List",
            "Bill of Lading (BOL)",
            "Photos - Load Securement",
        )
        assert cockpit.DELIVERY_ARTIFACTS == (
            "Arrival Notice",
            "Proof Of Delivery Document",
            "Packing List (if included)",
            "Photos - Condition / Delivery",
            "Invoice To Broker",
        )


class TestWhatTheLastCheckDoes:
    """Completing the delivery checklist PREPARES a packet. It does not send one.

        Publisher packet creation -> JOE review -> Outlook draft creation

    Human review and Outlook send remain required. The driver ticking the last
    box authorises preparation, and the screen must say exactly that -- an
    earlier version claimed it sent to the broker, which told him an outbound
    act had happened when it had not.
    """

    def _complete(self):
        return dict(RECORD, arrived_at="2026-08-31T10:00:00Z",
                    artifacts_held=list(cockpit.DELIVERY_ARTIFACTS))

    def test_an_incomplete_list_prepares_nothing(self):
        effect = cockpit.completion_effect(RECORD, cockpit.MODE_DELIVERY)
        assert effect["prepares_packet"] is False
        assert "nothing is prepared" in effect["note"].lower()

    def test_it_says_what_the_last_box_does_before_it_is_ticked(self):
        effect = cockpit.completion_effect(RECORD, cockpit.MODE_DELIVERY)
        assert "prepares" in effect["consequence"].lower()
        assert "review" in effect["consequence"].lower()

    def test_completing_delivery_prepares_the_packet(self):
        effect = cockpit.completion_effect(self._complete(), cockpit.MODE_DELIVERY)
        assert effect["prepares_packet"] is True
        assert "prepared" in effect["consequence"].lower()

    def test_it_never_says_it_sent_anything(self):
        """The correction that matters. Preparation is not transmission."""
        for record in (RECORD, self._complete()):
            effect = cockpit.completion_effect(record, cockpit.MODE_DELIVERY)
            words = " ".join([effect["consequence"], effect["note"], effect["chain"]]).lower()
            assert "sends the" not in words
            assert "sent to the broker" not in words
            assert "has been sent" not in words

    def test_it_names_the_chain_and_who_finishes_it(self):
        """Publisher -> JOE -> Outlook draft, and a human presses send."""
        chain = cockpit.completion_effect(self._complete(), cockpit.MODE_DELIVERY)["chain"]
        assert "publisher" in chain.lower()
        assert "joe review" in chain.lower()
        assert "outlook draft" in chain.lower()
        assert "you review and send" in chain.lower()

    def test_completing_pickup_does_not_prepare_a_broker_packet(self):
        held = dict(RECORD, artifacts_held=list(cockpit.PICKUP_ARTIFACTS))
        effect = cockpit.completion_effect(held, cockpit.MODE_PICKUP)
        assert effect["prepares_packet"] is False

    def test_it_does_not_claim_a_draft_that_was_never_made(self):
        effect = cockpit.completion_effect(self._complete(), cockpit.MODE_DELIVERY)
        if effect["transmission"] != "CONFIGURED":
            assert "nothing has been prepared" in effect["note"].lower()

    def test_it_reports_transmission_rather_than_assuming_it(self):
        assert cockpit.transmission_status() in (
            "CONFIGURED", "UNCONFIGURED", "SIMULATED", "UNAVAILABLE")

    def test_the_effect_reaches_the_checklist_drawer(self):
        docs = [d for d in cockpit.drawers_for(self._complete(), cockpit.MODE_DELIVERY)
                if d["key"] == "documents"][0]
        assert docs["effect"]["prepares_packet"] is True


class TestTheModeSurvivesTheRedirect:
    """/portal redirects to the mission being worked. The mode must ride along.

    Without this a bookmark to /portal?view=DELIVERY lands in CURRENT: the
    driver presses a saved shortcut, gets a different screen than the one he
    saved, and nothing on it explains why.
    """

    @pytest.fixture()
    def client(self):
        from portal.app import create_app

        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    @pytest.mark.parametrize("mode", ["PICKUP", "DELIVERY", "CURRENT"])
    def test_the_requested_mode_survives(self, client, mode):
        html = client.get("/portal?view=" + mode, follow_redirects=True).get_data(as_text=True)
        selected = re.search(
            r'data-mode="([A-Z_]+)"[^>]*aria-selected="true"', html, re.S)
        assert selected and selected.group(1) == mode

    def test_delivery_reaches_the_delivery_checklist(self, client):
        """The end-to-end symptom that exposed it."""
        html = client.get("/portal?view=DELIVERY", follow_redirects=True).get_data(as_text=True)
        assert "prepares the final document packet" in html


class TestTheTwoWorkflowsAreNotTheSame:
    """ARRIVE auto-sends. The final packet does not. They are separate."""

    def test_arrive_auto_sends(self):
        for mode in (cockpit.MODE_PICKUP, cockpit.MODE_DELIVERY):
            assert cockpit.arrive_for(RECORD, mode)["auto_sends"] is True

    def test_arrive_is_blind_copied_to_the_office(self):
        """So the evidence exists whether or not the broker acknowledges it."""
        assert cockpit.arrive_for(RECORD, cockpit.MODE_PICKUP)["bcc"] == "Ops@l1truck.com"

    def test_the_final_packet_never_auto_sends(self):
        complete = dict(RECORD, arrived_at="2026-08-31T10:00:00Z",
                        artifacts_held=list(cockpit.DELIVERY_ARTIFACTS))
        effect = cockpit.completion_effect(complete, cockpit.MODE_DELIVERY)
        assert "auto" not in effect["consequence"].lower()
        assert "you review and send" in effect["chain"].lower()

    def test_arrive_does_not_send_in_transit(self):
        assert cockpit.arrive_for(RECORD, cockpit.MODE_IN_TRANSIT)["auto_sends"] is False


class TestTheArrivalNotice:
    def test_it_names_what_will_follow(self):
        notice = cockpit.arrival_notice_for(RECORD, cockpit.MODE_PICKUP)
        follows = [f.lower() for f in notice["follows"]]
        assert any("bill of lading" in f for f in follows)
        assert any("load diagram" in f for f in follows)

    def test_delivery_promises_different_documents(self):
        notice = cockpit.arrival_notice_for(RECORD, cockpit.MODE_DELIVERY)
        follows = [f.lower() for f in notice["follows"]]
        assert any("invoice" in f for f in follows)
        assert any("pod" in f or "bol" in f for f in follows)

    def test_it_carries_the_broker_and_both_points_of_contact(self):
        """A notice proving a truck arrived is only useful to someone who can
        act on it, and the facility contact is who the broker rings to confirm
        it from the other end."""
        keys = [f["key"] for f in cockpit.arrival_notice_for(RECORD, cockpit.MODE_PICKUP)["fields"]]
        assert "Broker" in keys
        assert "Broker POC" in keys
        assert "Facility POC" in keys

    def test_a_contact_joins_a_name_and_a_number(self):
        record = dict(RECORD, broker_poc="D. Reyes")
        notice = cockpit.arrival_notice_for(record, cockpit.MODE_PICKUP)
        value = {f["key"]: f["value"] for f in notice["fields"]}["Broker POC"]
        assert "D. Reyes" in value
        assert "555-0199" in value

    def test_it_leaves_unknown_fields_empty_rather_than_inventing_them(self):
        """This text reaches a broker under the company name."""
        notice = cockpit.arrival_notice_for({"numbers": {}, "card_data": {}},
                                            cockpit.MODE_PICKUP)
        values = {f["key"]: f["value"] for f in notice["fields"]}
        assert values["Date"] == ""
        assert values["GPS"] == ""
        assert values["Broker POC"] == ""

    def test_screen_placeholders_never_reach_the_notice(self):
        """The cockpit shows an em dash so the driver sees an unanswered field.
        A broker reading the same character in a document sees an answer."""
        notice = cockpit.arrival_notice_for({"numbers": {}, "card_data": {}},
                                            cockpit.MODE_PICKUP)
        for field in notice["fields"]:
            assert field["value"] not in ("—", "Not stated", "Unknown")

    def test_it_reports_whether_it_actually_went(self):
        notice = cockpit.arrival_notice_for(RECORD, cockpit.MODE_PICKUP)
        assert notice["sent"] is False
        assert notice["transmission"] in ("CONFIGURED", "UNCONFIGURED",
                                          "SIMULATED", "UNAVAILABLE")


class TestStopManagement:
    """The screen showed the mission but not where the driver sat inside it."""

    def test_it_labels_the_position_in_the_run(self):
        stops = cockpit.stops_for(dict(RECORD, stop_number=2, stop_total=5))
        assert stops["label"] == "STOP 2 OF 5"

    def test_a_middle_stop_offers_both_directions(self):
        stops = cockpit.stops_for(dict(RECORD, stop_number=2, stop_total=3))
        assert stops["has_previous"] and stops["has_next"]

    def test_the_first_stop_offers_no_previous(self):
        stops = cockpit.stops_for(dict(RECORD, stop_number=1, stop_total=3))
        assert not stops["has_previous"]

    def test_the_last_stop_offers_no_next(self):
        stops = cockpit.stops_for(dict(RECORD, stop_number=3, stop_total=3))
        assert not stops["has_next"]


class TestLoadDiagram:
    def test_it_reports_where_the_freight_sits(self):
        record = dict(RECORD, load_position="Back 4 pallets across end")
        assert "Back 4 pallets" in cockpit.load_diagram_for(record)["position"]

    def test_no_diagram_says_so_rather_than_implying_one(self):
        assert cockpit.load_diagram_for(RECORD)["position"] == "Not recorded"
        assert cockpit.load_diagram_for(RECORD)["available"] is False

    def test_it_has_its_own_drawer(self):
        keys = [d["key"] for d in cockpit.drawers_for(RECORD, cockpit.MODE_PICKUP)]
        assert "loaddiagram" in keys


class TestEmptyPositionsAreCapacity:
    """An empty pallet space is not a gap in a picture. It is capacity.

    It answers "can I take two more on the way back", which is a question asked
    at a truck stop with a phone in one hand -- and a diagram drawing only what
    is loaded answers half of it.
    """

    LOADED = {
        "pallet_positions": 6,
        "load_plan": [
            {"position": 1, "stop": "Stop 1", "description": "Aviation parts"},
            {"position": 2, "stop": "Stop 1", "description": "Aviation parts"},
            {"position": 3, "stop": "Stop 2", "description": "Fasteners"},
        ],
    }

    def test_every_position_is_shown_not_only_the_full_ones(self):
        diagram = cockpit.load_diagram_for(self.LOADED)
        assert len(diagram["positions"]) == 6

    def test_the_empty_ones_are_marked_empty(self):
        diagram = cockpit.load_diagram_for(self.LOADED)
        assert [p["position"] for p in diagram["positions"] if p["empty"]] == [4, 5, 6]

    def test_it_counts_what_is_still_available(self):
        diagram = cockpit.load_diagram_for(self.LOADED)
        assert diagram["occupied_count"] == 3
        assert diagram["empty_count"] == 3
        assert "3 available" in diagram["capacity_line"]

    def test_each_loaded_position_says_which_stop_it_belongs_to(self):
        """Which decides whether stop three is reachable without unloading four."""
        diagram = cockpit.load_diagram_for(self.LOADED)
        assert diagram["positions"][2]["stop"] == "Stop 2"

    def test_unknown_capacity_is_reported_not_invented(self):
        """The van is not bought. A guessed six would sit under a real decision."""
        diagram = cockpit.load_diagram_for({"load_plan": [{"position": 1}]})
        assert diagram["total"] is None
        assert diagram["empty_count"] is None
        assert "UNCONFIGURED" in diagram["capacity_line"]

    def test_no_plan_produces_no_invented_positions(self):
        assert cockpit.load_diagram_for({}) ["positions"] == []


class TestTheStopCardHoldsOneFact:
    """Superseded the four-line card. The rule is stronger than a line count.

    The stop card carries stop progress and nothing else. Cargo, load position
    and the broker moved out to sections of their own, because a card that
    accumulates the whole mission is a card nobody can read at a glance.
    """

    @pytest.fixture()
    def client(self):
        from portal.app import create_app

        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def _card(self, client):
        html = client.get("/portal?view=CURRENT",
                          follow_redirects=True).get_data(as_text=True)
        start = html.index('class="stop-card"')
        return html[start:html.index("</div>", start)]

    def test_it_shows_the_stop_progress(self, client):
        assert "STOP" in self._card(client)

    def test_it_does_not_carry_the_broker(self, client):
        assert "Southeast" not in self._card(client)

    def test_it_does_not_carry_the_cargo(self, client):
        card = self._card(client)
        assert "CARGO" not in card
        assert "pallets" not in card

    def test_it_does_not_carry_the_load_position(self, client):
        assert "LOAD POSITION" not in self._card(client)
        assert "LOAD ARRANGEMENT" not in self._card(client)

    def test_the_mission_number_is_gone_from_the_screen(self, client):
        """Removed on instruction. The load number is the one he is asked for."""
        html = client.get("/portal?view=CURRENT",
                          follow_redirects=True).get_data(as_text=True)
        body = html[html.index("<body"):]
        assert "Mission 1" not in body

    def test_stop_navigation_appears_only_when_there_is_somewhere_to_go(self, client):
        """Offering a dead control is filler wearing a button."""
        html = client.get("/portal?view=CURRENT",
                          follow_redirects=True).get_data(as_text=True)
        from portal.models import sandbox

        record = sandbox.get("SBX-DISPATCH-E2E-DEMO-001") or {}
        stops = cockpit.stops_for(record)
        assert ('data-action="next-stop"' in html) == stops["has_next"]
        assert ('data-action="previous-stop"' in html) == stops["has_previous"]


class TestTheMissionLevelSections:
    """Cargo and Load Arrangement became sections of their own."""

    RECORD = {
        "numbers": {"load_label": "Load 847261"},
        "card_data": {"pallets": 4, "weight_lbs": 8400},
        "pallet_positions": 6,
        "load_plan": [
            {"position": 1, "stop": "Stop 1", "description": "Aviation parts"},
            {"position": 2, "stop": "Stop 1", "description": "Aviation parts"},
            {"position": 3, "stop": "Stop 2", "description": "Fasteners"},
        ],
    }

    def test_cargo_is_truck_wide_not_current_stop(self):
        """A summary showing only this stop hides the freight behind it."""
        rows = cockpit.cargo_by_stop(self.RECORD)["rows"]
        assert {r["stop"] for r in rows} == {"Stop 1", "Stop 2"}

    def test_cargo_counts_pallets_per_stop(self):
        rows = {r["stop"]: r["pallets"] for r in cockpit.cargo_by_stop(self.RECORD)["rows"]}
        assert rows["Stop 1"] == 2 and rows["Stop 2"] == 1

    def test_cargo_carries_a_truck_wide_total(self):
        total = cockpit.cargo_by_stop(self.RECORD)["total"]
        assert "4 pallets" in total and "8400 lbs" in total

    def test_no_plan_reports_rather_than_inventing_stops(self):
        assert cockpit.cargo_by_stop({"card_data": {}})["has_rows"] is False


class TestTheEndPanelsCarryTheWholeEnd:
    """Load number, address, POC, phone, appointment, instructions, items."""

    RECORD = {
        "numbers": {"load_label": "Load 847261"},
        "card_data": {"origin": "Jacksonville, FL", "destination": "Atlanta, GA"},
        "delivery_contact": "Dock 4 - K. Mills",
        "delivery_phone": "770-555-0142",
        "delivery_window": "15:00 - 19:00",
        "delivery_notes": "Dock 4 after 06:00",
        "stop_number": 1, "stop_total": 2,
        "load_plan": [{"position": 1, "stop": "Stop 1", "description": "Aviation parts"}],
    }

    def test_the_load_number_leads(self):
        """The broker's number: the one on the paperwork and asked for at a gate."""
        assert cockpit.end_detail(self.RECORD, "delivery")["load_number"] == "Load 847261"

    def test_every_specified_field_is_present(self):
        detail = cockpit.end_detail(self.RECORD, "delivery")
        for key in ("load_number", "address", "poc", "phone",
                    "appointment", "instructions", "items"):
            assert key in detail

    def test_it_carries_the_contact_and_number(self):
        detail = cockpit.end_detail(self.RECORD, "delivery")
        assert "K. Mills" in detail["poc"]
        assert "770-555-0142" in detail["phone"]

    def test_delivery_items_are_this_stops_items(self):
        assert cockpit.end_detail(self.RECORD, "delivery")["items"] == ["Aviation parts"]

    def test_a_missing_field_says_so_rather_than_disappearing(self):
        detail = cockpit.end_detail({"numbers": {}, "card_data": {}}, "pickup")
        assert detail["poc"] == "—"
        assert detail["items"] == ["—"]

    def test_the_far_end_carries_distance_and_drive_time(self):
        """Travel facts. Needed to decide whether the appointment is reachable."""
        detail = cockpit.end_detail(dict(self.RECORD, distance_miles=350), "delivery")
        assert detail["distance"] == "350 mi"
        assert detail["drive_time"] == "7h 00m"

    def test_the_near_end_claims_no_distance(self):
        """Dispatch does not know where the truck is now, so it says nothing."""
        detail = cockpit.end_detail(dict(self.RECORD, distance_miles=350), "pickup")
        assert detail["distance"] == ""

    def test_access_notes_are_never_shared_between_ends(self):
        """One load-level note under both addresses sends a driver to the wrong
        door with paperwork telling him he is right."""
        record = {
            "numbers": {},
            "card_data": {"location_intelligence": "Dock 4, lumper $85"},
            "pickup_notes": "Gate 2, guard shack",
        }
        assert cockpit.end_detail(record, "pickup")["instructions"] == "Gate 2, guard shack"
        # The delivery end has no note of its own, so it says so rather than
        # borrowing the pickup's.
        assert cockpit.end_detail(record, "delivery")["instructions"] == "—"


class TestCargoOwnsTheDiagram:
    """Load arrangement folded into Cargo: one section, two controls.

    Where the freight sits and what is still free is a fact about the same
    cargo, and a section of its own for one line was a section too many.
    """

    @pytest.fixture()
    def client(self):
        from portal.app import create_app

        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def _html(self, client):
        return client.get("/portal?view=CURRENT",
                          follow_redirects=True).get_data(as_text=True)

    def test_there_is_one_cargo_block(self, client):
        assert self._html(client).count('class="fact-row block cargo-block"') == 1

    def test_the_diagram_button_lives_inside_it(self, client):
        html = self._html(client)
        block = html[html.index("cargo-block"):]
        block = block[:block.index("data-drawer=\"broker\"")]
        assert "OPEN LOAD DIAGRAM" in block

    def test_load_arrangement_is_no_longer_its_own_row(self, client):
        assert 'fact-row block arrangement' not in self._html(client)

    def test_the_load_number_is_labelled_and_bold(self, client):
        """It is the number he is asked for at a gate, so it must read as one."""
        html = self._html(client)
        assert "end-load-tag" in html
        css = open("portal/static/joe_portal.css", encoding="utf-8").read()
        block = css[css.index(".end-load {"):]
        block = block[:block.index("}")]
        assert "font-weight: 800" in block
