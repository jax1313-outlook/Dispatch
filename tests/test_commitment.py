"""COMMIT: where Booking ends and Dispatch begins.

    Everything before COMMIT is Booking.
    Everything after COMMIT is Mission Execution.

COMMIT does not mean a broker awarded the load, or that a rate was agreed, or
that a carrier packet went out. It means everything necessary to execute now
exists -- and the moment it is pressed, capacity is taken and the driver's
workflow becomes real.

That is why it is a gate and not a status. A broker saying "it's yours" is a
sentence; committing is an act with consequences.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from dispatch import booking, commitment, mission


MONDAY = date(2026, 9, 7)


def _record(committed=False, legacy=False, pickup=""):
    record = {"id": "SBX-1", "load_number": "L1-TEST",
              "card_data": {"load_id": "L1-TEST", "origin": "A",
                            "destination": "B", "pickup_window": pickup}}
    if committed:
        record["committed_at"] = "2026-09-01T10:00:00Z"
    if legacy:
        record["accepted_at"] = "2026-08-15T10:00:00Z"
    return record


class TestTheGateHasAName:
    def test_a_record_is_a_candidate_until_it_is_committed(self):
        assert commitment.state_of(_record()) == commitment.CANDIDATE
        assert commitment.is_committed(_record()) is False

    def test_committing_moves_it_to_dispatch(self):
        record = _record(committed=True)
        assert commitment.state_of(record) == commitment.COMMITTED
        assert commitment.phase_of(record) == commitment.PHASE_DISPATCH

    def test_a_candidate_belongs_to_booking(self):
        assert commitment.phase_of(_record()) == commitment.PHASE_BOOKING

    def test_records_committed_before_the_rename_are_still_committed(self):
        """The gate has been in the data since the beginning as accepted_at.
        Renaming a field is not a reason to lose a commitment."""
        record = _record(legacy=True)
        assert commitment.is_committed(record) is True
        assert commitment.committed_at(record) == "2026-08-15T10:00:00Z"

    def test_the_new_name_wins_when_both_are_present(self):
        record = _record(committed=True, legacy=True)
        assert commitment.committed_at(record) == "2026-09-01T10:00:00Z"

    def test_committing_creates_nothing(self):
        """The record SWEEP found is the record that runs."""
        fields = commitment.commit(_record(), when="2026-09-02T08:00:00Z")
        assert fields == {"committed_at": "2026-09-02T08:00:00Z"}

    def test_it_never_commits_twice(self):
        assert commitment.commit(_record(committed=True), when="later") == {}

    def test_awarded_is_doctrine_and_is_not_wired(self):
        """The operator named it as the missing middle state -- the broker has
        said it is his, and rate confirmation and onboarding are outstanding.
        A state nothing sets and nothing reads is a field that lies about
        being used, so it is named and left unbuilt."""
        assert commitment.AWARDED == "AWARDED"
        assert commitment.state_of(_record()) != commitment.AWARDED


class TestPurposeReadsTheGate:
    def test_a_candidate_is_an_opportunity(self):
        assert mission.purpose_of(_record()) == mission.PURPOSE_OPPORTUNITY
        assert mission.is_mission(_record()) is False

    def test_a_committed_record_is_a_mission(self):
        assert mission.purpose_of(_record(committed=True)) == mission.PURPOSE_MISSION

    def test_the_legacy_field_still_resolves(self):
        assert mission.is_mission(_record(legacy=True)) is True


class TestBookingRespectsTheGate:
    """The defect this fixes.

    A day read BOOKED because a Mission Record had a pickup window on it. Under
    the gate that is wrong: a candidate still being negotiated would claim a
    Tuesday and shrink the unsold count on freight that is not his yet.
    """

    def _board(self, *records):
        store = {"r%d" % i: r for i, r in enumerate(records)}
        return booking.build(store, {}, today=MONDAY, weeks=2)

    def test_a_candidate_does_not_take_the_day(self):
        book = self._board(_record(pickup=MONDAY.isoformat()))
        assert book["board"][0]["state"] == booking.OPEN
        assert book["booked_count"] == 0

    def test_a_committed_mission_does(self):
        book = self._board(_record(committed=True, pickup=MONDAY.isoformat()))
        assert book["board"][0]["state"] == booking.BOOKED
        assert book["booked_count"] == 1

    def test_a_candidate_day_is_still_counted_as_unsold(self):
        """Until COMMIT the day is still sellable to somebody else."""
        book = self._board(_record(pickup=MONDAY.isoformat()))
        assert book["board"][0] in book["unsold"]

    def test_the_candidate_is_shown_but_not_as_a_load(self):
        """He should see what is in play on a day without being told he has
        freight he has not got."""
        day = self._board(_record(pickup=MONDAY.isoformat()))["board"][0]
        assert day["loads"] == []
        assert len(day["candidates"]) == 1
        assert day["candidates"][0]["phase"] == "Pickup"

    def test_a_committed_mission_is_a_load_not_a_candidate(self):
        day = self._board(_record(committed=True,
                                  pickup=MONDAY.isoformat()))["board"][0]
        assert len(day["loads"]) == 1
        assert day["candidates"] == []

    def test_depth_counts_only_committed_work(self):
        """How far out am I covered is a question about freight he has."""
        far = (MONDAY + timedelta(days=8)).isoformat()
        assert self._board(_record(pickup=far))["depth"]["has_work"] is False
        assert self._board(_record(committed=True,
                                   pickup=far))["depth"]["has_work"] is True


class TestTheScreenShowsBoth:
    """Asserted against the template and stylesheet rather than a rendered
    board: what is in the store on the day the suite runs is not the thing
    under test."""

    def test_the_board_renders_candidates(self):
        template = open("portal/templates/booking.html", encoding="utf-8").read()
        assert "day.candidates" in template
        assert "candidate.load_number" in template

    def test_a_candidate_is_drawn_differently_from_a_booking(self):
        """Drawn like a booking, it would tell him he has freight he has not
        got."""
        css = open("portal/static/booking.css", encoding="utf-8").read()
        rule = css[css.index(".candidate {"):]
        rule = rule[:rule.index("}")]
        assert "dashed" in rule

    def test_the_page_still_renders_with_both_kinds(self):
        from portal.app import create_app

        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as client:
            assert client.get("/booking").status_code == 200
