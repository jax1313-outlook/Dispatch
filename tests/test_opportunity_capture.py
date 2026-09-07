"""Opportunity capture — the seventh contract, OPP-CAPTURE v1.0.

The walking skeleton: the first real freight through the full stack. These tests
cover what the plan actually rules, in its own words, and THE CAPTURE TEST of §7
end to end including the fail-closed path.
"""

from __future__ import annotations

import pytest

from dispatch import audit, opportunity as opp
from dispatch.db import set_db_path

TOKEN = "test-token-not-a-real-secret"


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    set_db_path(tmp_path / "test.db")
    monkeypatch.setenv("DISPATCH_JOE_TOKEN", TOKEN)
    yield
    set_db_path(None)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    from portal.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _post(client, **fields):
    body = {"source_board": "DAT", "origin": "Jacksonville, FL",
            "destination": "Tampa, FL", "rate": 750}
    body.update(fields)
    return client.post("/api/joe/opportunity", json=body,
                       headers={"Authorization": "Bearer " + TOKEN,
                                "X-Driver": "mike"})


# ------------------------------------------------------------------ §7

class TestTheCaptureTest:
    """§7, verbatim:

        "Joe, log this one: [board], one pallet, Jacksonville to Tampa, $750,
        pickup Thursday." -> "LOGGED. OPPORTUNITY [id]. [board], JACKSONVILLE TO
        TAMPA, $750, PICKUP THURSDAY."
    """

    def test_it_logs_and_echoes_the_card(self, client):
        r = _post(client, pieces_weight="one pallet", pickup_date="Thursday")
        assert r.status_code == 201
        d = r.get_json()
        assert d["ok"] is True and d["verdict"] == "NEW"
        assert d["opportunity_id"].startswith("OPP-")
        echo = d["echo"]
        assert echo.startswith("LOGGED. OPPORTUNITY OPP-")
        for part in ("DAT,", "JACKSONVILLE, FL TO TAMPA, FL,", "$750", "PICKUP THURSDAY"):
            assert part in echo, echo

    def test_the_record_carries_driver_attribution(self, client):
        rid = _post(client).get_json()["opportunity_id"]
        assert opp.get(rid)["captured_by"] == "mike"

    def test_the_audit_entry_is_complete(self, client):
        _post(client, pickup_date="Thursday")
        entry = [e for e in audit.entries(limit=50)
                 if e["action"] == "opportunity-capture"][0]
        assert entry["driver"] == "mike"
        assert entry["result"] == audit.RESULT_SUCCESS
        assert entry["mission_id"].startswith("OPP-")
        assert entry["timestamp"]

    def test_a_re_capture_merges_rather_than_doubles(self, client):
        first = _post(client, pickup_date="2026-09-10").get_json()
        second = _post(client, pickup_date="2026-09-10").get_json()
        assert second["verdict"] == "MERGED"
        assert second["opportunity_id"] == first["opportunity_id"]
        assert len(opp.all_open()) == 1

    def test_capture_fails_closed_when_the_token_is_unset(self, client, monkeypatch):
        """The blocker path, honestly reported rather than worked around."""
        monkeypatch.delenv("DISPATCH_JOE_TOKEN", raising=False)
        r = _post(client)
        assert r.status_code == 503
        assert r.get_json()["ok"] is False
        assert opp.all_open() == [], "nothing may be stored by a refused call"


# ------------------------------------------------------------------ §1, §2

class TestClassOne:
    def test_no_confirmation_is_required(self, client):
        """Class 1 is internal, reversible, and touches no Mission Record.
        Requiring a read-back here would be confirmation that does not match
        consequence."""
        assert _post(client).status_code == 201

    def test_a_capture_still_needs_somebodys_authority(self, client):
        r = client.post("/api/joe/opportunity",
                        json={"source_board": "DAT", "origin": "A",
                              "destination": "B", "rate": 1},
                        headers={"Authorization": "Bearer " + TOKEN})
        assert r.status_code == 400
        assert opp.all_open() == []


class TestSparseCaptureIsValidCapture:
    """§2: *"only board, origin, destination, and rate are required. A capture
    with gaps beats a listing lost to the next screen."*"""

    def test_the_four_alone_are_enough(self, client):
        r = _post(client)
        assert r.status_code == 201
        record = opp.get(r.get_json()["opportunity_id"])
        for gap in ("pieces_weight", "equipment", "pickup_date", "contact", "notes"):
            assert record[gap] == ""

    @pytest.mark.parametrize("missing", ["source_board", "origin", "destination"])
    def test_each_of_the_four_is_actually_required(self, client, missing):
        r = _post(client, **{missing: ""})
        assert r.status_code == 400
        assert missing in r.get_json()["note"]

    def test_a_missing_rate_is_refused_not_defaulted(self, client):
        """Zero is a number a broker could have said. A missing rate is not
        free freight, so it is never invented."""
        r = _post(client, rate="")
        assert r.status_code == 400
        assert "rate" in r.get_json()["note"]

    def test_a_rate_of_zero_is_a_real_answer(self, client):
        assert _post(client, rate=0).status_code == 201

    def test_a_refused_capture_stores_nothing(self, client):
        _post(client, origin="")
        assert opp.all_open() == []


class TestTheContractIsVendorAgnostic:
    """Contract-First Rule: *"vendor-specific concepts shall not appear in the
    authoritative contract layer."*"""

    @pytest.mark.parametrize("board", ["DAT", "Truckstop", "123Loadboard",
                                       "Truck Smarter", "a board nobody has heard of"])
    def test_the_board_is_stored_as_the_owner_says_it(self, client, board):
        rid = _post(client, source_board=board).get_json()["opportunity_id"]
        assert opp.get(rid)["source_board"] == board

    def test_channels_are_named_by_nature_not_by_product(self):
        assert opp.CHANNELS == ("VOICE", "CHAT", "MISSIONSCREEN", "SWEEP")

    def test_an_unknown_channel_does_not_lose_the_capture(self, client):
        """Speed outranks completeness. A bad channel label is not worth losing
        a listing over."""
        rid = _post(client, captured_via="SEMAPHORE").get_json()["opportunity_id"]
        assert opp.get(rid)["captured_via"] in opp.CHANNELS


# ------------------------------------------------------------------ §3

class TestTheDeduplicationRule:
    """§3: *"One load = one Opportunity record"* — and *"the engine never
    silently guesses two loads are one."*"""

    def test_a_different_board_is_a_different_load(self, client):
        _post(client, source_board="DAT", pickup_date="2026-09-10")
        r = _post(client, source_board="Truckstop", pickup_date="2026-09-10")
        assert r.get_json()["verdict"] == "NEW"
        assert len(opp.all_open()) == 2

    def test_a_different_lane_is_a_different_load(self, client):
        _post(client, pickup_date="2026-09-10")
        r = _post(client, destination="Orlando, FL", pickup_date="2026-09-10")
        assert r.get_json()["verdict"] == "NEW"

    def test_a_rate_within_tolerance_is_the_same_load(self, client):
        _post(client, rate=750, pickup_date="2026-09-10")
        r = _post(client, rate=770, pickup_date="2026-09-10")
        assert r.get_json()["verdict"] == "MERGED"

    def test_a_rate_far_outside_tolerance_is_not_silently_merged(self, client):
        _post(client, rate=750, pickup_date="2026-09-10")
        d = _post(client, rate=1800, pickup_date="2026-09-10").get_json()
        assert d["verdict"] == "AMBIGUOUS"
        assert d["flag"] == opp.FLAG_POSSIBLE_DUPLICATE
        assert len(opp.all_open()) == 2, "ambiguity makes a record, never a merge"

    def test_a_missing_pickup_date_is_ambiguous_not_a_match(self, client):
        """Sparse capture makes this common. Not knowing is a third answer."""
        _post(client, pickup_date="2026-09-10")
        d = _post(client, pickup_date="").get_json()
        assert d["verdict"] == "AMBIGUOUS"
        assert d["possible_duplicate_of"]

    def test_a_flagged_record_names_the_one_it_may_duplicate(self, client):
        first = _post(client, pickup_date="2026-09-10").get_json()
        second = _post(client, rate=1800, pickup_date="2026-09-10").get_json()
        assert second["possible_duplicate_of"] == first["opportunity_id"]


class TestMergingEnrichesAndNeverOverwrites:
    """§3: *"Sweep data enriches sparse voice captures (fills gaps), never
    overwrites Owner-dictated values."*"""

    def test_a_gap_is_filled(self, client):
        first = _post(client, captured_via="VOICE",
                      pickup_date="2026-09-10").get_json()
        _post(client, captured_via="SWEEP", pickup_date="2026-09-10",
              equipment="reefer", contact="Sally 904-555-0100")
        record = opp.get(first["opportunity_id"])
        assert record["equipment"] == "reefer"
        assert record["contact"] == "Sally 904-555-0100"

    def test_what_the_owner_dictated_is_never_replaced(self, client):
        first = _post(client, captured_via="VOICE", equipment="dry van",
                      pickup_date="2026-09-10").get_json()
        _post(client, captured_via="SWEEP", equipment="reefer",
              pickup_date="2026-09-10")
        assert opp.get(first["opportunity_id"])["equipment"] == "dry van"

    def test_the_origin_trail_records_both_sightings(self, client):
        """§3: *"append the new origin to the audit trail (e.g. captured VOICE
        09:14, seen SWEEP 09:30)."*"""
        first = _post(client, captured_via="VOICE",
                      pickup_date="2026-09-10").get_json()
        _post(client, captured_via="SWEEP", pickup_date="2026-09-10")
        origins = opp.get(first["opportunity_id"])["origins"]
        assert len(origins) == 2
        assert origins[0].startswith("VOICE") and origins[1].startswith("SWEEP")

    def test_a_merge_says_what_it_filled(self, client):
        _post(client, pickup_date="2026-09-10")
        d = _post(client, pickup_date="2026-09-10", notes="detention after 2").get_json()
        assert d["filled"] == ["notes"]

    def test_a_merge_is_audited_as_a_merge(self, client):
        _post(client, pickup_date="2026-09-10")
        _post(client, pickup_date="2026-09-10")
        notes = [e["note"] for e in audit.entries(limit=50)
                 if e["action"] == "opportunity-capture"]
        assert any("merged into existing" in n for n in notes)


# ------------------------------------------------------------------ §6

class TestTheDictationOrderComesFromTheForm:
    """§6: *"the form definition in Dispatch is the single source of truth for
    field order, and Code derives the parser's expected sequence from it — the
    protocol follows the form automatically if the form ever changes."*"""

    def test_every_contract_field_appears_exactly_once(self):
        order = opp.dictation_order()
        assert sorted(order) == sorted(opp.FIELDS)

    def test_the_order_follows_the_mission_card(self):
        from dispatch import mission_template as mt

        card = [f.key for f in mt.TEMPLATE]
        order = opp.dictation_order()
        assert order.index("origin") < order.index("destination")
        assert order.index("pickup_date") < order.index("delivery_date")
        # And the card really does put pickup before delivery, so the assertion
        # above is testing derivation rather than a coincidence.
        assert card.index("pickup_location") < card.index("delivery_location")

    def test_it_moves_when_the_form_moves(self, monkeypatch):
        """The claim that matters. Reorder the card and the protocol reorders —
        no hardcoded sequence anywhere."""
        from dispatch import mission_template as mt

        flipped = list(mt.TEMPLATE)
        i = next(n for n, f in enumerate(flipped) if f.key == "pickup_location")
        j = next(n for n, f in enumerate(flipped) if f.key == "delivery_location")
        flipped[i], flipped[j] = flipped[j], flipped[i]
        monkeypatch.setattr(mt, "TEMPLATE", tuple(flipped))
        assert opp.dictation_order().index("destination") < \
               opp.dictation_order().index("origin")
