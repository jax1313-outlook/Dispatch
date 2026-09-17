"""Batch 2: one commitment operation, one determination, one authority.

**Owner's authoritative ruling, 2026-09-16:**

    Dispatch contains no operational legacy data requiring backward
    compatibility. Do not preserve accepted_at as a commitment compatibility
    field ... BOOK must not write accepted_at. BOOK must not create committed
    state. BOOK must not satisfy is_committed(). COMMIT becomes the sole
    authoritative commitment operation.

    One commitment operation. One commitment determination.
    One commitment state. One commitment authority.

The defect it removes: `accepted_at` was read as a legacy alias for
`committed_at`, **and BOOK wrote it** — so pressing *Book Load* committed the
record everywhere that asks the gate, with none of COMMIT's consequences.
"""

from __future__ import annotations

import pytest

from dispatch import commitment
from portal.models import sandbox


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    monkeypatch.setenv("DISPATCH_DB_PATH", str(tmp_path / "dispatch.db"))
    from dispatch import scheduling

    monkeypatch.setattr(scheduling, "_outlook_is_running", lambda: False)
    yield


@pytest.fixture()
def client():
    from portal.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with c.session_transaction() as s:
            s["user_id"] = "mike"
        yield c


def _card(number: str = "AUTH-1") -> str:
    from portal.models import opportunity_card as oc

    return oc.from_capture({
        "opportunity_id": number, "origin": "Jacksonville, FL",
        "destination": "Savannah, GA", "contact": "Penske Logistics",
        "commodity": "Auto Parts", "pickup_date": "2026-09-21 09:00",
        "delivery_date": "2026-09-21 14:00"})["id"]


class TestOneCommitmentDetermination:
    def test_the_gate_reads_one_field(self):
        assert commitment.committed_at({"committed_at": "2026-09-16T12:00:00Z"})
        assert commitment.is_committed({"committed_at": "2026-09-16T12:00:00Z"})

    def test_accepted_at_no_longer_commits_anything(self):
        """*"Do not retain is_committed() logic that treats accepted_at as a
        commitment event."*"""
        stale = {"accepted_at": "2026-08-15T10:00:00Z"}

        assert commitment.committed_at(stale) == ""
        assert commitment.is_committed(stale) is False

    def test_there_is_no_legacy_field_left_to_read(self):
        assert not hasattr(commitment, "LEGACY_FIELD")


class TestBookDoesNotCommit:
    def test_booking_records_its_own_fact(self):
        record_id = _card("AUTH-2")

        sandbox.mark_accepted(record_id, 7)

        entry = sandbox.get(record_id)
        assert entry[sandbox.BOOKED_FIELD]
        assert "accepted_at" not in entry

    def test_a_booked_record_is_not_committed(self):
        """The whole defect in one assertion. It left LOADS, took the day on the
        Booking board and printed "Committed" on the brief — with no calendar
        hold, no portal access and no COMMIT."""
        record_id = _card("AUTH-3")

        sandbox.mark_accepted(record_id, 8)

        assert commitment.is_committed(sandbox.get(record_id)) is False

    def test_booking_twice_is_idempotent(self):
        record_id = _card("AUTH-4")
        first = sandbox.mark_accepted(record_id, 9)

        again = sandbox.mark_accepted(record_id, 99)

        assert again[sandbox.BOOKED_FIELD] == first[sandbox.BOOKED_FIELD]
        assert again["mission_number"] == 9, "the number is not reissued"


class TestBookIsRefusedOnACommittedMission:
    def test_it_cannot_be_booked_after_commit(self, client):
        """*"assigned once at ACCEPT LOAD and never reissued to that record."*
        BOOK was still offered on a committed mission and minted it a fresh
        Mission Number."""
        from dispatch import mission as mission_svc
        from dispatch import services as dispatch_svc

        record_id = _card("AUTH-5")
        client.post("/brief/mission/%s/commit" % record_id)
        committed = sandbox.get(record_id)
        assert commitment.is_committed(committed)

        with pytest.raises(mission_svc.MissionError) as refused:
            mission_svc.accept_load(record_id, sandbox, dispatch_svc, None)

        assert "committed" in str(refused.value).lower()

    def test_the_mission_number_survives_the_attempt(self, client):
        from dispatch import mission as mission_svc
        from dispatch import services as dispatch_svc

        record_id = _card("AUTH-6")
        client.post("/brief/mission/%s/commit" % record_id)
        before = sandbox.get(record_id)["mission_number"]

        with pytest.raises(mission_svc.MissionError):
            mission_svc.accept_load(record_id, sandbox, dispatch_svc, None)

        assert sandbox.get(record_id)["mission_number"] == before


class TestEveryCommittedMissionHasATracingNumber:
    """The 49th finding, raised by a test that pressed the POD button rather
    than calling the packet builder.

    A load typed on the New Mission screen gets a number at intake. **A load
    captured by voice, paste or an alert never did**, and COMMIT did not either
    — so a completed captured run filed its POD and invoice in a folder called
    `no-load-number`. The load number is the tracing number: *"a folder inside
    of Library according to that number for retervial from Archive."*
    """

    def test_a_captured_card_has_none_before_commit(self):
        assert not sandbox.get(_card("AUTH-7")).get("load_number")

    def test_commit_assigns_one(self, client):
        record_id = _card("AUTH-8")

        client.post("/brief/mission/%s/commit" % record_id)

        assert sandbox.get(record_id)["load_number"]

    def test_a_number_the_broker_gave_is_kept_exactly(self, client):
        """*"a number we tidied up is a number that no longer matches theirs on
        an invoice."*"""
        from portal.models import opportunity_card as oc

        record = oc.from_capture({
            "opportunity_id": "AUTH-9", "origin": "Jacksonville, FL",
            "destination": "Savannah, GA", "commodity": "Pallets"})
        data = sandbox._load()
        data[record["id"]]["card_data"]["load_id"] = "Tallahassee-1487"
        sandbox._save(data)

        client.post("/brief/mission/%s/commit" % record["id"])

        assert sandbox.get(record["id"])["load_number"] == "Tallahassee-1487"

    def test_the_packet_is_filed_under_a_real_number(self, client):
        from dispatch import closing_packet

        record_id = _card("AUTH-10")
        client.post("/brief/mission/%s/commit" % record_id)

        number = sandbox.get(record_id)["load_number"]
        assert closing_packet.folder_for(number).name == number
        assert closing_packet.folder_for(number).name != "no-load-number"


class TestPassRefusesACommittedMission:
    def test_it_does_not_archive_a_live_mission(self, client):
        """The guard refused the discard and then **fell through** — setting the
        committed mission's status to PASS and writing an Archive record for
        freight still on the truck."""
        record_id = _card("AUTH-11")
        client.post("/brief/mission/%s/commit" % record_id)

        answer = client.post("/api/action",
                             json={"sandbox_id": record_id, "action": "PASS"})

        assert answer.status_code == 409
        entry = sandbox.get(record_id)
        assert entry["status"] != "PASS"
        assert commitment.is_committed(entry), "still Dispatch's to run"

    def test_it_writes_nothing_at_all_before_refusing(self, client):
        """A refusal that leaves a trace is a half-completed act. Checked
        explicitly because the old fall-through wrote **both** the status and an
        Archive record."""
        from portal.models import archive as arc_model

        record_id = _card("AUTH-12")
        client.post("/brief/mission/%s/commit" % record_id)
        before = sandbox.get(record_id)
        archived_before = len(arc_model.get_section("load"))

        client.post("/api/action", json={"sandbox_id": record_id, "action": "PASS"})

        assert sandbox.get(record_id) == before, "the record is untouched"
        assert len(arc_model.get_section("load")) == archived_before
