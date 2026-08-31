"""The Driver Cockpit: one screen, three modes, nothing moving between them.

Pinned from the operator's design record of 31 August 2026. These tests are
mostly about restraint -- what the screen refuses to do -- because the failures
that matter here are a layout that shifts under a driver's eye and a checklist
that closes itself while he is counting pallets on a dock.
"""

from __future__ import annotations

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
    def test_the_modes_are_the_drivers_words(self):
        assert [m["label"] for m in cockpit.MODES] == ["PICKUP", "IN TRANSIT", "DELIVERY"]

    def test_current_is_gone_from_the_drivers_vocabulary(self):
        """CURRENT is a software state. A driver is going somewhere."""
        assert "CURRENT" not in [m["label"] for m in cockpit.MODES]

    def test_a_legacy_current_url_still_opens(self):
        """A bookmark must not break because the vocabulary improved."""
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
        held = dict(RECORD, artifacts_held=list(cockpit.PICKUP_ARTIFACTS))
        assert cockpit.document_status(held, cockpit.MODE_PICKUP)["state"] == "COMPLETE"

    def test_one_missing_artifact_is_not_complete(self):
        held = dict(RECORD, artifacts_held=list(cockpit.PICKUP_ARTIFACTS[:-1]))
        assert cockpit.document_status(held, cockpit.MODE_PICKUP)["state"] == "READY"

    def test_the_checklist_holds_artifacts_not_information(self):
        """A working list of what the driver must obtain. Addresses, contacts
        and instructions live in the details drawers, not here."""
        labels = [i["label"].lower()
                  for i in cockpit.document_checklist(RECORD, cockpit.MODE_PICKUP)]
        assert any("bill of lading" in label for label in labels)
        assert any("load diagram" in label for label in labels)
        assert not any("address" in label or "contact" in label
                       or "instruction" in label for label in labels)

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

    def test_the_delivery_checklist_is_not_padded_to_look_finished(self):
        """The final lists are an operating-procedure decision, not a guess."""
        assert len(cockpit.DELIVERY_ARTIFACTS) <= 4
