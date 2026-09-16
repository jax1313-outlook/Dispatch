"""Score -- what Mike may not see. CO-3, 2026-09-14.

The Owner's must-have: *"Assistance scoring the loads to see what I may not
see."* Miles with their source, empty miles from where the truck really is, the
fleet's equipment, and the warnings a board never prints. All advisory; none of
it decides.
"""

from __future__ import annotations

import pathlib
import re
from datetime import date, datetime

import pytest

from dispatch import distance, drive_time, load_assessment, scoring
from dispatch.db import set_db_path
from portal import helpers
from portal.models import sandbox

TODAY = date(2026, 9, 15)
CARGO_VAN = [{"equipment_type": "cargo_van", "unit_number": "V1", "payload_lb": 3500,
              "cargo_length_in": 144}]


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    set_db_path(tmp_path / "dispatch.db")
    from dispatch import scheduling

    monkeypatch.setattr(scheduling, "_outlook_is_running", lambda: False)
    yield
    set_db_path(None)


@pytest.fixture
def client():
    from portal.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _committed(record_id="M1", *, number="L1-0001", destination="Atlanta, GA",
               pickup="2026-09-21 06:00", delivery="2026-09-22 10:00"):
    return {"id": record_id, "committed_at": "2026-09-14T12:00:00+00:00",
            "load_number": number,
            "card_data": {"origin": "Jacksonville, FL", "destination": destination,
                          "pickup_window": pickup, "delivery_window": delivery}}


def _codes(result):
    return [w["code"] for w in result["warnings"]]


class TestDistance:
    def test_the_provider_is_unconfigured_and_says_so(self):
        assert distance.provider_status() == "UNCONFIGURED"

    def test_typed_miles_come_before_the_table(self):
        trip = distance.miles_between("Jacksonville FL", "Atlanta GA", typed="352")
        assert (trip["miles"], trip["status"]) == (352.0, "MANUAL")
        assert "UNCONFIGURED" in trip["note"]

    def test_the_table_is_the_last_resort_and_unverified(self):
        trip = distance.miles_between("Jacksonville FL", "Atlanta GA")
        assert (trip["miles"], trip["basis"], trip["status"]) == (
            345.0, distance.BASIS_TABLE, "UNVERIFIED")

    def test_a_lane_nobody_can_answer_has_no_miles(self):
        trip = distance.miles_between("Ocala FL", "Macon GA")
        assert trip["miles"] is None and trip["status"] == "ABSENT"

    def test_a_configured_provider_answers_first(self, monkeypatch):
        """When a provider is chosen its answer wins, carrying its own status word."""
        from dispatch.connectors import registry
        from dispatch.connectors.contract import ConnectorStatus

        class _Mapped:
            def fetch(self, request):
                from dispatch.connectors.mapping_connector import MappingAndRoutingConnector
                real = MappingAndRoutingConnector()
                payload = real.payload("route_geometry", {"miles": 372},
                                       status=ConnectorStatus.SIMULATED)
                return real.success(request, payload)

        monkeypatch.setattr(registry, "get", lambda cid: _Mapped())
        trip = distance.miles_between("Jacksonville FL", "Atlanta GA", typed="352")
        assert (trip["miles"], trip["basis"], trip["status"]) == (
            372.0, distance.BASIS_PROVIDER, "SIMULATED")

    def test_no_provider_is_named_outside_its_adapter(self):
        text = pathlib.Path("dispatch/distance.py").read_text(encoding="utf-8").lower()
        for vendor in ("google", "mapbox", "here.com", "pc miler", "pcmiler", "trimble",
                       "bing", "openroute", "osrm"):
            assert vendor not in text


class TestPositionAndDeadhead:
    def test_with_nothing_committed_the_truck_starts_at_home(self):
        result = load_assessment.assess(
            {"origin": "Savannah, GA", "destination": "Charlotte, NC", "rate": 900,
             "pickup_window": "2026-09-24 08:00"}, records=[], today=TODAY)
        assert result["position"]["basis"] == "home base"
        assert result["deadhead_miles"] == 140.0
        assert "home base" in result["deadhead_basis"]

    def test_after_a_committed_delivery_the_truck_starts_there(self):
        result = load_assessment.assess(
            {"origin": "Charlotte, NC", "destination": "Columbia, SC", "rate": 500,
             "pickup_window": "2026-09-23 08:00"},
            records=[_committed()], today=TODAY)
        assert result["position"]["location"] == "Atlanta, GA"
        assert "L1-0001" in result["position"]["basis"]
        assert result["deadhead_miles"] == 245.0

    def test_a_committed_load_delivering_after_this_pickup_is_not_the_start(self):
        result = load_assessment.assess(
            {"origin": "Savannah, GA", "destination": "Charlotte, NC", "rate": 900,
             "pickup_window": "2026-09-20 08:00"},
            records=[_committed()], today=TODAY)
        assert result["position"]["basis"] == "home base"

    def test_scoring_uses_the_empty_miles_it_is_given(self):
        load = {"origin": "Charlotte, NC", "destination": "Columbia, SC", "rate": 500,
                "distance_miles": 90, "position_deadhead_miles": 245}
        assert scoring.compute_deadhead_miles(load) == 245.0
        assert "$1.49" in scoring.compute_economic_opportunity(load)


class TestEquipment:
    def test_a_match_and_a_mismatch_against_the_active_fleet(self):
        assert load_assessment.equipment_fit("Cargo Van", CARGO_VAN)["match"] == "match"
        fit = load_assessment.equipment_fit("Reefer 53'", CARGO_VAN)
        assert fit["match"] == "mismatch" and "cargo van" in fit["note"]

    def test_unknowns_are_unknown(self):
        assert load_assessment.equipment_fit("Hopper", CARGO_VAN)["match"] == ""
        assert load_assessment.equipment_fit("Dry Van", [])["match"] == ""
        assert load_assessment.equipment_fit("", CARGO_VAN)["match"] == ""


class TestWarnings:
    def test_delivery_timing_is_parked(self):
        """Mike Zachary, 2026-09-15: drive times do not enter the decision process. The
        check in dispatch/drive_time.py is kept, but no warning comes from it."""
        result = load_assessment.assess(
            {"origin": "A", "destination": "B", "rate": 2000, "distance_miles": 700,
             "pickup_window": "2026-09-22 06:00", "delivery_window": "2026-09-22 14:00"},
            records=[], today=TODAY)
        assert "CANNOT_MAKE_DELIVERY" not in _codes(result)
        assert result["timing"] == {}

    def test_the_breaks_are_counted(self):
        # The parked module still counts correctly; the speed is passed explicitly.
        trip = drive_time.earliest_arrival(datetime(2026, 9, 22, 6, 0), 450, mph=50)
        # 9 h driving: a 30-minute break after 8 hours, no reset.
        assert (trip["breaks"], trip["resets"]) == (1, 0)
        assert trip["arrive"] == datetime(2026, 9, 22, 15, 30)

    def test_missing_facts_are_named_not_guessed(self):
        check = drive_time.delivery_check("Thursday", "2026-09-22", 300)
        assert check["can_make"] is None and "pickup date and time" in check["line"]

    def test_a_weekend_delivery_is_worth_checking(self):
        """The receiver may not be open. That is about the consignee's door, not
        about Mike's week."""
        saturday = load_assessment.assess({"origin": "A", "destination": "B", "rate": 900,
                                           "delivery_window": "2026-09-26"}, today=TODAY)
        assert "WEEKEND_DELIVERY" in _codes(saturday)

    def test_no_day_is_closed_against_him_any_more(self):
        """**BOOKING CONFLICT PREVENTION DOCTRINE, 2026-09-16:** every day begins
        OPEN and *"Dispatch does not decide ... which days are closed."* Sunday
        used to raise CLOSED_DAY off the week pattern. The check is kept -- a day
        Outlook or a later ruling closes would still raise it -- but the pattern
        no longer closes one."""
        sunday = load_assessment.assess({"origin": "A", "destination": "B", "rate": 900,
                                         "delivery_window": "2026-09-27"}, today=TODAY)
        assert "CLOSED_DAY" not in _codes(sunday)
        assert "WEEKEND_DELIVERY" in _codes(sunday), "a Sunday is still a weekend"

    def test_collides_with_a_committed_load_including_its_transit_day(self):
        committed = _committed(pickup="2026-09-21 06:00", delivery="2026-09-23 10:00")
        result = load_assessment.assess(
            {"origin": "Tampa, FL", "destination": "Miami, FL", "rate": 900,
             "pickup_window": "2026-09-22 08:00", "delivery_window": "2026-09-22 16:00"},
            records=[committed], today=TODAY)
        assert "COLLIDES_WITH_COMMITTED" in _codes(result)

    def test_a_candidate_never_collides_with_another_candidate(self):
        """Reality and Possibility never merge."""
        other = dict(_committed(), committed_at="")
        result = load_assessment.assess(
            {"origin": "Tampa, FL", "destination": "Miami, FL", "rate": 900,
             "pickup_window": "2026-09-21 08:00", "delivery_window": "2026-09-21 16:00"},
            records=[other], today=TODAY)
        assert "COLLIDES_WITH_COMMITTED" not in _codes(result)

    def test_a_stranded_gap_day(self):
        result = load_assessment.assess(
            {"origin": "Atlanta, GA", "destination": "Charlotte, NC", "rate": 900,
             "pickup_window": "2026-09-24 08:00", "delivery_window": "2026-09-24 16:00"},
            records=[_committed()], today=TODAY)
        stranded = [w for w in result["warnings"] if w["code"] == "STRANDED_GAP_DAY"]
        assert stranded and "Wed 23 Sep" in stranded[0]["text"]

    def test_below_the_floor_after_empty_miles(self):
        result = load_assessment.assess(
            {"origin": "Atlanta, GA", "destination": "Birmingham, AL", "rate": 700,
             "pickup_window": "2026-09-24 08:00"}, records=[], today=TODAY)
        # 150 loaded + 345 empty from home base, plus the run home = under $1.41 a mile.
        assert "BELOW_FLOOR_AFTER_DEADHEAD" in _codes(result)

    def test_the_floor_counts_the_run_home(self):
        """Mike Zachary, 2026-09-15: "rate floor should include all miles driven including
        return home." Jacksonville to Atlanta and back: loaded miles alone clear the floor,
        but the empty run home brings the load under it."""
        card = {"origin": "Jacksonville, FL", "destination": "Atlanta, GA",
                "pickup_window": "2026-09-24 08:00"}
        loaded = load_assessment.assess(dict(card, rate=0.1), records=[], today=TODAY)["distance"]["miles"]
        home = load_assessment.assess(dict(card, rate=0.1), records=[], today=TODAY)["return_home_miles"]
        assert loaded and home, "the 22-lane table must know Jacksonville-Atlanta both ways"
        # A rate that clears the floor over loaded miles but not over loaded plus the run home.
        rate = 2.60 * loaded
        result = load_assessment.assess(dict(card, rate=rate), records=[], today=TODAY)
        floor = [w for w in result["warnings"] if w["code"] == "BELOW_FLOOR_AFTER_DEADHEAD"]
        assert floor and "home to" in floor[0]["text"]

    def test_overweight_against_the_fleet_and_without_one(self):
        heavy = {"origin": "A", "destination": "B", "rate": 900, "weight_lbs": 5000}
        assert "OVERWEIGHT" in _codes(load_assessment.assess(heavy, fleet=CARGO_VAN, today=TODAY))
        assert "OVERWEIGHT" not in _codes(load_assessment.assess(heavy, fleet=[], today=TODAY))
        heavier = dict(heavy, weight_lbs=48000)
        assert "OVERWEIGHT" in _codes(load_assessment.assess(heavier, fleet=[], today=TODAY))

    def test_a_card_without_a_rate_is_rate_pending_not_a_warning(self):
        """Was NEEDS_RATE, first in the warning list. **Owner ruling, 2026-09-15:**
        *"holding a load with out a rate will need an astric or blank is not
        negative."* A neutral line, not a warning."""
        result = load_assessment.assess({"origin": "A", "destination": "B"}, today=TODAY)
        assert result["rate_pending"] is True
        assert result["rate_line"] == "* Rate pending"
        assert "NEEDS_RATE" not in _codes(result)
        assert not any("rate" in w["text"].lower() for w in result["warnings"])
        assert "MISSING_FACTS" in _codes(result)

    def test_the_floor_check_does_not_fire_without_a_rate(self):
        """Rate-dependent warnings simply do not run: the load that was below the
        floor at $700 says nothing about the floor with no rate."""
        card = {"origin": "Atlanta, GA", "destination": "Birmingham, AL",
                "pickup_window": "2026-09-24 08:00"}
        assert "BELOW_FLOOR_AFTER_DEADHEAD" not in _codes(
            load_assessment.assess(card, records=[], today=TODAY))
        assert "BELOW_FLOOR_AFTER_DEADHEAD" not in _codes(
            load_assessment.assess(dict(card, rate=0), records=[], today=TODAY))


class TestScoreBands:
    def test_bands_are_shares_of_the_real_maximum(self):
        assert helpers.card_visual(scoring.MAX_SCORE)["css"] == "card-high"
        assert helpers.card_visual(81)["css"] == "card-high"
        assert helpers.card_visual(80)["css"] == "card-strong"

    def test_with_the_rate_pending_the_bands_are_the_same_shares_of_sixty(self):
        """Owner ruling 2026-09-15, "2a": scored without the rate factor and read
        against the maximum that excludes it."""
        assert scoring.MAX_SCORE_WITHOUT_RATE == scoring.MAX_SCORE - scoring.RATE_POINTS == 60
        assert helpers.card_visual(54, rate_pending=True)["css"] == "card-high"    # 0.90 of 60
        assert helpers.card_visual(53, rate_pending=True)["css"] == "card-strong"
        assert helpers.card_visual(45, rate_pending=True)["css"] == "card-strong"  # 0.75 of 60
        assert helpers.card_visual(36, rate_pending=True)["css"] == "card-moderate"
        assert helpers.card_visual(24, rate_pending=True)["css"] == "card-low"
        assert helpers.format_score(52, True) == "52 of 60 · * rate pending"
        assert helpers.format_score(70) == "70"

    def test_a_missing_rate_is_not_a_penalty(self):
        """The same load scores exactly the other factors: nothing added for the
        rate, nothing taken away, and never above sixty."""
        rated = {"origin": "Jacksonville, FL", "destination": "Savannah, GA",
                 "distance_miles": 140, "rate": 200, "equipment_match": "match"}
        pending = dict(rated)
        pending.pop("rate")
        # A below-floor rate earns the rate factor 0 points, so the two differ
        # only in which maximum they are read against.
        assert scoring.compute_score(pending) == scoring.compute_score(rated)
        assert scoring.score_max_for(pending) == 60 and scoring.score_max_for(rated) == 90
        excellent = dict(rated, rate=900)
        assert scoring.compute_score(excellent) - scoring.compute_score(pending) == 30
        assert scoring.compute_score({"load_id": "x"}) <= 60
        result = scoring.score_load(pending)
        assert scoring.rate_pending(pending) is True and result["score"] <= 60
        assert "below floor" not in result["economic_opportunity_flag"].lower()

    def test_the_divergent_scorer_is_on_no_screen_path(self):
        """dispatch/opportunities.py carries a second scorer used only by tests.
        No portal module may reach it, so no card can show its number."""
        offenders = []
        for path in pathlib.Path("portal").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if re.search(r"dispatch\.opportunities\b|from dispatch import [^\n]*\bopportunities\b",
                         text):
                offenders.append(str(path))
        assert offenders == []


class TestThroughTheScreens:
    def test_a_pasted_listing_shows_its_warnings_on_the_loads_screen(self, client):
        sandbox.create_entry(source_type="dispatch", source_id="L1-0001", title="Committed",
                             card_data=_committed()["card_data"])
        sandbox.mark_accepted("SBX-DISPATCH-L1-0001", 1)

        resp = client.post("/loads/paste", data={"pasted": (
            "Atlanta, GA to Charlotte, NC\nPickup: 2099-09-22 08:00\n"
            "Delivery: 2099-09-22 09:00\nRate: $300\nEquipment: Reefer")})
        assert resp.status_code == 302
        card = next(e for e in sandbox.get_all().values()
                    if e["id"] != "SBX-DISPATCH-L1-0001")["card_data"]
        assert card["distance_basis"].startswith(distance.BASIS_TABLE)
        codes = [w["code"] for w in card["warnings"]]
        assert "BELOW_FLOOR_AFTER_DEADHEAD" in codes
        # Delivery timing is parked (Mike Zachary, 2026-09-15): not a warning, not on the screen.
        assert "CANNOT_MAKE_DELIVERY" not in codes

        page = client.get("/loads").get_data(as_text=True)
        assert "below the $2.50 floor" in page
        assert "Earliest legal delivery" not in page

    def test_a_swept_load_without_a_rate_is_scored_with_the_rate_pending(self, client):
        """Was: unscored, "Score: needs rate". **Owner ruling, 2026-09-15** --
        *"(a) a score from everything except the rate, marked '* rate pending'"*:
        **"2a"**."""
        from portal.models import opportunity_card

        opportunity_card.from_acquired([{
            "load_id": "NR-1", "title": "No rate", "origin": "Jacksonville, FL",
            "destination": "Savannah, GA", "pickup_window": "2099-09-22 08:00",
            "data_origin": "SIMULATED"}])
        entry = sandbox.get("SBX-DISPATCH-NR-1")
        card = entry["card_data"]
        assert card["rate_pending"] is True and card["score_max"] == 60
        assert "needs_rate" not in card
        assert entry["score"] is not None and 0 <= entry["score"] <= 60
        # Not lower than the same card scored with the rate factor left out.
        other_factors = scoring.compute_score(dict(card, rate=None))
        assert entry["score"] >= other_factors
        page = client.get("/dispatch").get_data(as_text=True)
        assert "Score %s of 60 · * rate pending" % entry["score"] in page
        assert "* Rate pending" in page
        assert "needs rate" not in page.lower()
        assert "<strong>Rate:</strong> *" in page

    def test_the_inquiry_threshold_compares_like_with_like(self, client):
        """The threshold (81 of 90) is a share. A rate-pending card is measured as a
        share of 60: 54 clears it, 53 does not. A rated card is unchanged. Only the
        gate is compared; the draft is still a human-review draft and nothing sends."""
        def entry(sid, score, pending):
            sandbox.create_entry(source_type="dispatch", source_id=sid, title=sid,
                                 card_data={"broker_email": "b@example.com",
                                            "rate_pending": pending}, score=score)
            return client.post("/api/inquiry/create",
                               json={"sandbox_id": "SBX-DISPATCH-%s" % sid}).get_json()

        assert entry("P54", 54, True)["status"] == "DRAFT_CREATED"
        low = entry("P53", 53, True)
        assert low["status"] == "NOT_READY" and "53 of 60 · * rate pending" in low["reason"]
        assert "(54)" in low["reason"]
        assert entry("R80", 80, False)["status"] == "NOT_READY"
        assert entry("R81", 81, False)["status"] == "DRAFT_CREATED"

    def test_the_loads_screen_shows_the_rate_as_an_asterisk(self, client):
        client.post("/loads/paste", data={"pasted": "Jacksonville, FL to Savannah, GA\n"
                                                    "Pickup: 2099-09-22 08:00"})
        entry = next(iter(sandbox.get_all().values()))
        page = client.get("/loads").get_data(as_text=True)
        assert '<span class="cand-rate">*</span>' in page
        assert "Score %s of 60 · * rate pending" % entry["score"] in page
        assert "* Rate pending" in page
        assert "&#9888; * Rate pending" not in page  # a neutral line, not a warning
