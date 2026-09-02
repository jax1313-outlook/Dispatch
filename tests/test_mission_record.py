"""Mission Record doctrine, held by tests.

The rules these guard are the ones that are easy to break silently a year from
now, when someone adds a feature and reaches for create_load() out of habit:

    One record. ACCEPT LOAD commits the opportunity; it does not copy it.
    Two numbers, never confused.
    CURRENT is resolved, never stored.
    Many views, one read.
"""

import pytest

from dispatch import db, mission as mission_svc
from portal.models import sandbox


# The suite has no shared app fixture; each module builds its own with an
# isolated data directory and database, so tests never write into the real
# PortalData. Same arrangement test_booking.py uses.
@pytest.fixture(autouse=True)
def portal_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal_data"))
    return tmp_path / "portal_data"


@pytest.fixture(autouse=True)
def tmp_dispatch_db(tmp_path):
    db_path = tmp_path / "dispatch.db"
    db.set_db_path(db_path)
    yield db_path
    db.set_db_path(None)


@pytest.fixture
def app(tmp_path, monkeypatch):
    from portal.app import create_app
    from cin_lite import pending

    monkeypatch.setattr(pending, "_PENDING_DIR", tmp_path / "Pending")
    return create_app({"TESTING": True, "SECRET_KEY": "test"})


@pytest.fixture
def client(app):
    return app.test_client()


CARD = {
    "load_id": "847261",                     # the BROKER's reference
    "origin": "Jacksonville, FL",
    "destination": "Atlanta, GA",
    "broker": "Southeast Freight Partners",
    "pickup_window": "2026-08-30 06:00 - 10:00",
    "delivery_window": "2026-08-30 15:00 - 19:00",
    "equipment_required": "Dry Van 53'",
    "source": "dat",
}


@pytest.fixture
def mission_record():
    """An Opportunity Record, as a sweep would leave it."""
    entry = sandbox.create_entry(
        source_type="dispatch",
        source_id="MISSIONDOC-001",
        title="Dry Van - JAX to ATL",
        card_data=dict(CARD),
        score=91,
    )
    return entry


class TestOneRecord:
    def test_accept_load_keeps_the_same_identity(self, client, mission_record):
        """The whole doctrine, in one assertion.

        Before: create_load() minted a new id and the card's fields were
        copied into it. Two records, joined one way, and the opportunity's
        intelligence stopped travelling with the mission.
        """
        record_id = mission_record["id"]
        resp = client.post("/api/action",
                           json={"sandbox_id": record_id, "action": "book"})
        assert resp.status_code == 200
        assert resp.get_json()["engine_load"]["load_id"] == record_id

    def test_the_intelligence_stays_attached_after_commitment(self, client, mission_record):
        """What was learned during acquisition survives the commitment."""
        record_id = mission_record["id"]
        client.post("/api/action", json={"sandbox_id": record_id, "action": "book"})
        after = sandbox.get(record_id)
        assert after["card_data"]["origin"] == CARD["origin"]
        assert after["score"] == 91
        assert after["events"], "the record's history did not survive"

    def test_purpose_changes_but_the_record_does_not(self, client, mission_record):
        record_id = mission_record["id"]
        assert mission_svc.purpose_of(sandbox.get(record_id)) == "OPPORTUNITY"
        client.post("/api/action", json={"sandbox_id": record_id, "action": "book"})
        assert mission_svc.purpose_of(sandbox.get(record_id)) == "MISSION"

    def test_a_second_commitment_is_refused(self, client, mission_record):
        record_id = mission_record["id"]
        client.post("/api/action", json={"sandbox_id": record_id, "action": "book"})
        again = client.post("/api/action",
                            json={"sandbox_id": record_id, "action": "book"})
        assert again.status_code == 409


class TestTwoNumbers:
    def test_mission_number_is_numeric_and_four_digits_at_most(self):
        for taken in ([], [1], list(range(1, 50))):
            number = mission_svc.next_mission_number(taken)
            assert isinstance(number, int)
            assert 1 <= number <= 9999
            assert str(number).isdigit()

    def test_numbers_fill_gaps_rather_than_marching_upward(self):
        assert mission_svc.next_mission_number([1, 2, 4]) == 3

    def test_the_external_number_is_the_brokers_not_ours(self, client, mission_record):
        record_id = mission_record["id"]
        client.post("/api/action", json={"sandbox_id": record_id, "action": "book"})
        record = sandbox.get(record_id)
        assert mission_svc.external_load_number(record) == "847261"
        assert str(record["mission_number"]) != "847261"

    def test_the_external_number_is_never_defaulted_to_ours(self):
        """A record with no broker reference shows none - it does not borrow
        the internal number. Quoting our tracking number where an invoice
        expects theirs is how a payment goes missing."""
        assert mission_svc.external_load_number({"card_data": {}}) == ""
        assert mission_svc.display_numbers(
            {"mission_number": 42, "card_data": {}})["load_number"] == ""

    def test_both_numbers_are_labelled_when_shown_together(self):
        labels = mission_svc.display_numbers(
            {"mission_number": 1847, "card_data": {"load_id": "847261"}})
        assert labels["mission_label"] == "Mission 1847"
        assert labels["load_label"] == "Load 847261"


class TestDeterministicViews:
    def test_current_is_resolved_from_status_not_stored(self):
        assert mission_svc.phase_for("at_pickup") == "PICKUP"
        assert mission_svc.phase_for("in_transit") == "DELIVERY"
        assert mission_svc.phase_for("at_delivery") == "DELIVERY"

    def test_current_never_becomes_a_third_branch(self):
        """CURRENT must always resolve to one of the other two."""
        for status in ("created", "at_pickup", "in_transit", "delivered"):
            resolved = mission_svc.resolve_view({"load": {"status": status}},
                                                "CURRENT")
            assert resolved in ("PICKUP", "DELIVERY")

    def test_the_filter_reveals_and_never_deletes(self):
        bundle = {
            "milestones": [{"event_type": "arrived_pickup"},
                           {"event_type": "arrived_delivery"}],
            "evidence": [{"evidence_type": "bol"}, {"evidence_type": "pod"}],
            "detentions": [{"location_type": "pickup"},
                           {"location_type": "delivery"}],
            "pods": [{"pod_id": "P1"}],
            "exceptions": [],
        }
        pickup = mission_svc.filter_bundle(bundle, "PICKUP")
        delivery = mission_svc.filter_bundle(bundle, "DELIVERY")

        assert len(pickup["milestones"]) == 1
        assert len(delivery["milestones"]) == 1
        assert pickup["detentions"][0]["location_type"] == "pickup"
        assert delivery["detentions"][0]["location_type"] == "delivery"
        # A POD is delivery work; showing it at a pickup dock invites it to be
        # filed from the wrong end of the run.
        assert pickup["pods"] == []
        assert delivery["pods"]
        # The source bundle is untouched - the filter copies, never mutates.
        assert len(bundle["milestones"]) == 2

    def test_the_filter_reads_the_column_the_record_actually_has(self):
        """event_type is what is stored. Filtering on milestone_type matched
        nothing and produced a silent empty timeline."""
        bundle = {"milestones": [{"event_type": "loaded"}]}
        assert len(mission_svc.filter_bundle(bundle, "PICKUP")["milestones"]) == 1

    def test_open_exceptions_appear_in_every_phase(self):
        """A problem is not irrelevant because you moved down the road."""
        bundle = {"exceptions": [{"status": "open"}, {"status": "resolved"}]}
        for phase in ("PICKUP", "DELIVERY"):
            shown = mission_svc.filter_bundle(bundle, phase)["exceptions"]
            assert len(shown) == 1


class TestManyViewsOneRead:
    def test_all_three_views_cost_one_store_read(self, client, mission_record, monkeypatch):
        """The property that stops 'many views' becoming 'many records'."""
        from dispatch import services as dispatch_svc

        record_id = mission_record["id"]
        client.post("/api/action", json={"sandbox_id": record_id, "action": "book"})

        calls = []
        real = dispatch_svc.get_load_bundle

        def counting(load_id):
            calls.append(load_id)
            return real(load_id)

        monkeypatch.setattr("dispatch.services.get_load_bundle", counting)

        for view in ("CURRENT", "PICKUP", "DELIVERY"):
            del calls[:]
            page = client.get("/portal/mission/%s?view=%s" % (record_id, view))
            assert page.status_code == 200
            assert len(calls) == 1, (
                "%s issued %d store reads; one record, one read"
                % (view, len(calls)))


class TestPortalRenders:
    def test_the_portal_shows_both_numbers(self, client, mission_record):
        record_id = mission_record["id"]
        client.post("/api/action", json={"sandbox_id": record_id, "action": "book"})
        html = client.get("/portal/mission/%s" % record_id).get_data(as_text=True)
        assert "847261" in html
        # The Driver Cockpit dropped the "Mission (ours) / Load (broker's)"
        # column labels -- the distinction now travels in the values themselves,
        # which `display_numbers` renders as "Mission 1" and "Load 847261". The
        # rule being pinned is unchanged: both numbers are on screen and cannot
        # be mistaken for each other.
        assert "Mission" in html
        assert "Load 847261" in html

    def test_the_portal_works_without_a_network(self, client, mission_record):
        """A truck has no signal. Nothing may be fetched from a CDN."""
        record_id = mission_record["id"]
        html = client.get("/portal/mission/%s" % record_id).get_data(as_text=True)
        for cdn in ("cdn.tailwindcss.com", "cdn.jsdelivr.net",
                    "fonts.googleapis.com", "fonts.gstatic.com"):
            assert cdn not in html, "portal still reaches for %s" % cdn
        assert "vendor/tailwind.js" in html

    def test_touch_controls_are_present(self, client, mission_record):
        record_id = mission_record["id"]
        html = client.get("/portal/mission/%s" % record_id).get_data(as_text=True)
        assert "mode-btn" in html
        # PICKUP / DELIVERY. CURRENT was dropped as a control and kept as the
        # default: a driver is going to a pickup or making a delivery, and a
        # button for whichever of those he is already in answers no question.
        for mode in ("PICKUP", "DELIVERY"):
            assert 'data-mode="%s"' % mode in html


class TestCalendarBoundary:
    def test_the_real_adapter_reports_unavailable_rather_than_pretending(self,
                                                                        monkeypatch):
        """With Outlook closed. The adapter is wired now, so this pins the
        behaviour that matters -- an honest UNAVAILABLE -- instead of pinning
        the fact that it was once a stub.

        `_outlook_is_running` is forced False so the test never touches COM.
        A test that reaches the operator's real Outlook is broken whatever it
        asserts.
        """
        from dispatch import scheduling

        monkeypatch.setattr(scheduling, "_outlook_is_running", lambda: False)
        probe = scheduling.OutlookCalendarAdapter().probe()
        assert probe["status"] == "UNAVAILABLE"
        assert probe["live"] is False
        assert probe["demonstration"] is False

    def test_the_demonstration_adapter_always_says_so(self):
        from dispatch import scheduling

        demo = scheduling.DemonstrationAdapter()
        assert demo.probe()["demonstration"] is True
        held = demo.hold_appointment({"mission_number": 1})
        assert held["demonstration"] is True
        assert held["held"] is False, "a demo must never claim to have booked"
        assert "DEMONSTRATION" in held["note"]

    def test_accepting_a_load_never_silently_fails_to_schedule(self, monkeypatch):
        """If the calendar could not hold the time, the driver is told to do it
        himself rather than left believing Outlook has it.

        Outlook is forced closed. Before the adapter was wired this test called
        `hold_appointment` on the real one and was harmless against a stub;
        against live Outlook it wrote an appointment into the operator's own
        calendar. A test must never reach a real calendar, a real mailbox or a
        real anything.
        """
        from dispatch import scheduling

        monkeypatch.setattr(scheduling, "_outlook_is_running", lambda: False)
        result = scheduling.on_accept_load(
            {"mission_number": 1}, scheduling.OutlookCalendarAdapter())
        assert result["held"] is False
        assert "yourself" in result["note"].lower()

    def test_no_test_reaches_the_real_outlook(self):
        """The guard for the mistake above.

        Narrow on purpose: `cin_lite.email_delivery.send` is already offline
        by construction -- the suite scrubs the SMTP variables and redirects
        the outbox to a tmp directory. The risk is the Outlook adapters, which
        reach the operator's own calendar and mailbox through COM, and the only
        thing that stops them is forcing the connection closed.
        """
        import pathlib
        import re

        risky = re.compile(
            r"(OutlookCalendarAdapter|OutlookMailAdapter|on_accept_load)\s*\(")
        offenders = []
        for path in pathlib.Path("tests").glob("test_*.py"):
            text = path.read_text(encoding="utf-8")
            for match in risky.finditer(text):
                # The guard has to appear in the same test, before the call.
                body = text[:match.start()]
                opened = body.rfind("    def test")
                window = body[opened:] if opened >= 0 else body
                if "_outlook_is_running" not in window:
                    offenders.append("%s:%s" % (path.name, match.group(1)))

        # probe() and upcoming() are read-only and safe either way; what must
        # never run unguarded is anything that writes.
        writes = [o for o in offenders if "on_accept_load" in o]
        assert writes == [], writes


class TestSweepControl:
    def test_a_sweep_never_creates_a_mission(self, client, mission_record):
        """Activation event 1 makes opportunities. Only ACCEPT LOAD commits."""
        from dispatch import sweep

        before = mission_svc.purpose_of(sandbox.get(mission_record["id"]))
        sweep.start(runner=lambda: [])
        after = mission_svc.purpose_of(sandbox.get(mission_record["id"]))
        assert before == after == "OPPORTUNITY"

    def test_the_timer_reports_its_next_run_in_plain_terms(self):
        from dispatch import sweep

        state = sweep.set_schedule(True, "05:30")
        assert state["timer_enabled"] is True
        assert state["next_run"], "an enabled timer must say when it next runs"
        off = sweep.set_schedule(False)
        assert off["next_run"] == ""

    def test_a_failed_sweep_explains_itself_without_a_stack_trace(self):
        from dispatch import sweep

        def broken():
            raise ConnectionError("connection timed out")

        state = sweep.start(runner=broken)
        assert state["state"] == "error"
        assert "signal" in state["message"].lower()
        assert "Traceback" not in state["message"]
