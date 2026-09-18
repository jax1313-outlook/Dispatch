"""BATCH 10: one load, cradle to archive, through the controls a person presses.

**MISSION: CONSTITUTIONAL REGRESSION RECONCILIATION**, primary rule:

    Each consequential business act shall have one authoritative operation.
    Every screen, API route, helper, and test representing that act must call
    the same authoritative operation.

Nine batches corrected that one act at a time. This file walks a single mission
from capture to retention **without touching an engine function directly** --
every step is an HTTP request a driver or Operations makes -- and checks that
each batch's ruling still holds at the end of the whole chain rather than in
isolation.

From `CLAUDE.md` §7: *"A test that builds its own precondition proves the logic
and says nothing about whether the application can reach it."* Every regression
these nine batches found was reachable and unreached: a POD button that filed
nothing, an ARRIVE that mailed before the gate, an Advance button that retired a
load into no record. Each had passing unit tests beside it.

    Driver completes the mission. Operations closes the file.
    Archive performs retention.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from portal.models import sandbox

DOC = ("<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
       "<w:document xmlns:w='x'><w:body>%s</w:body></w:document>")


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    monkeypatch.setenv("DISPATCH_DB_PATH", str(tmp_path / "dispatch.db"))
    monkeypatch.setenv("DISPATCH_PACKET_ROOT", str(tmp_path / "packets"))

    shelf = tmp_path / "Memory"
    templates = shelf / "Templates"
    templates.mkdir(parents=True)
    with zipfile.ZipFile(str(templates / "02_POD_Cover 1.docx"), "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", DOC % (
            "<w:p><w:r><w:t>{{load_number}} : {{delivery_status}}</w:t></w:r></w:p>"))
    monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(shelf))

    from dispatch import scheduling

    monkeypatch.setattr(scheduling, "_outlook_is_running", lambda: False)
    yield


class _Mail:
    """Records. Sends nothing anywhere -- no test may reach real Outlook."""

    def __init__(self):
        self.sent, self.drafted = [], []

    def send(self, to, subject, body, bcc=""):
        self.sent.append({"to": to, "subject": subject})
        return {"ok": True}

    def draft(self, to, subject, body, bcc=""):
        self.drafted.append({"to": to, "subject": subject})
        return {"ok": True}

    @property
    def handled(self):
        return self.sent + self.drafted


@pytest.fixture()
def mail(monkeypatch):
    from portal.routes import joe_portal

    box = _Mail()
    monkeypatch.setattr(joe_portal, "_mail_connector", lambda: box)
    return box


@pytest.fixture()
def client():
    from portal.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


#: Session keys the two roles own. Swapped rather than cleared: `session.clear()`
#: mints a fresh CSRF token while the client still holds the old cookie, and the
#: suite runs **with** the protection on rather than around it (`tests/conftest.py`).
_ROLE_KEYS = ("user_id", "driver_open", "driver_id", "role")


def _become(client, **who):
    with client.session_transaction() as s:
        for key in _ROLE_KEYS:
            s.pop(key, None)
        s.update(who)


def _as_operations(client):
    _become(client, user_id="mike")


def _as_driver(client):
    _become(client, driver_open=True, role="Driver")


def _status(record_id):
    from dispatch import services as dispatch_svc

    return str((dispatch_svc.get_load(record_id) or {}).get("status") or "")


class Run:
    """One mission, walked by pressing things. Every method is a person."""

    def __init__(self, client):
        self.c = client

    def captured(self, opportunity_id="WHOLE-1"):
        from portal.models import opportunity_card as oc

        self.id = oc.from_capture({
            "opportunity_id": opportunity_id,
            "origin": "Jacksonville, FL", "destination": "Savannah, GA",
            "contact": "Penske Logistics", "commodity": "Auto Parts",
            "pickup_date": "2026-09-21 09:00",
            "delivery_date": "2026-09-21 16:00"})["id"]
        data = sandbox._load()
        data[self.id]["customer_email"] = "broker@example.invalid"
        sandbox._save(data)
        return self

    def committed(self):
        _as_operations(self.c)
        answer = self.c.post("/brief/mission/%s/commit" % self.id)
        assert answer.status_code in (200, 302), answer.status_code
        return self

    def milestone(self, event):
        _as_driver(self.c)
        self.c.post("/portal/mission/%s/milestone" % self.id,
                    data={"milestone_event": event})
        return self

    def arrived(self, view="PICKUP"):
        _as_driver(self.c)
        self.last = self.c.post("/portal/mission/%s/arrive" % self.id,
                                data={"view": view})
        return self

    def attached(self, classification, name="doc.pdf"):
        _as_driver(self.c)
        self.last = self.c.post(
            "/portal/mission/%s/attach" % self.id,
            data={"classification": classification,
                  "artifact": (io.BytesIO(b"%PDF-1.4 signed"), name)},
            content_type="multipart/form-data")
        return self

    def closed_out(self, note=""):
        _as_operations(self.c)
        self.last = self.c.post("/api/dispatch/loads/%s/closeout" % self.id,
                                json={"note": note})
        return self

    def archived(self):
        _as_operations(self.c)
        self.last = self.c.post("/api/dispatch/loads/%s/archive" % self.id)
        return self

    @property
    def record(self):
        return sandbox.get(self.id)


@pytest.fixture()
def run(client, mail):
    return Run(client).captured()


class TestTheRunHappens:
    """Every step, in order, pressed."""

    def test_a_captured_card_is_not_yet_a_load(self, run):
        from dispatch import services as dispatch_svc

        assert dispatch_svc.get_load(run.id) is None

    def test_commit_opens_the_load_and_numbers_it(self, run):
        """BATCH 2: *"One commitment operation. One commitment determination.
        One commitment state. One commitment authority."* -- and COMMIT is what
        assigns the tracing number, including for a card nobody typed."""
        run.committed()

        assert _status(run.id) == "created"
        assert run.record.get("load_number")

    def test_the_driver_starts_the_run(self, run):
        """BATCH 1: assigning a truck is not starting a run. START RUN is the
        driver's act."""
        run.committed().milestone("en_route_pickup")

        assert _status(run.id) == "en_route_pickup"

    def test_arrive_tells_the_customer_once_the_run_is_real(self, run, mail):
        """BATCH 4: *"gate refuses, no notice goes"* -- and on an arrival the
        gate accepts, *"notice must go out, email must be sent."*"""
        run.committed().milestone("en_route_pickup").arrived("PICKUP")

        assert mail.sent, "the customer was told nothing about a real arrival"

    def test_the_bol_can_be_attached(self, run):
        """BATCH 8: the controlling freight document had no door at all."""
        run.committed().milestone("en_route_pickup").attached("bol", "bol.pdf")

        from dispatch import services as dispatch_svc

        kinds = [e["evidence_type"]
                 for e in dispatch_svc.get_load_bundle(run.id)["evidence"]]
        assert "bol" in kinds

    def test_the_pod_finishes_the_run_and_files_the_packet(self, run):
        """BATCH 3: *"POD sent completes the load and triggers the closing
        packet."*"""
        _walk_to_delivered(run)

        run.attached("pod", "pod.pdf")

        assert _status(run.id) == "completed"
        assert run.record["closing_packet"]["documents"]

    def test_the_packet_is_filed_under_the_tracing_number(self, run):
        _walk_to_delivered(run)
        run.attached("pod", "pod.pdf")

        report = run.record["closing_packet"]
        assert Path(report["folder"]).name == report["load_number"]

    def test_operations_closes_the_file(self, run):
        """BATCH 5: *"Driver completes the mission. Operations closes the
        file."*"""
        _walk_to_delivered(run)
        run.attached("pod", "pod.pdf").closed_out()

        assert run.last.status_code == 200

    def test_archive_retains_it_with_a_way_back_to_the_packet(self, run):
        """BATCH 5, point 9: *"a folder inside of Library according to that
        number for retervial from Archive. that is the tracing number."*"""
        _walk_to_delivered(run)
        run.attached("pod", "pod.pdf")
        folder = run.record["closing_packet"]["folder"]
        run.closed_out().archived()

        assert run.last.status_code == 201
        retention = run.last.get_json()["retention"]
        assert retention["packet_location"] == folder
        assert Path(retention["packet_location"]).is_dir()


def _walk_to_delivered(run):
    run.committed()
    for event in ("en_route_pickup", "arrived_pickup", "loaded",
                  "departed_pickup", "arrived_delivery", "delivered"):
        run.milestone(event)
    assert _status(run.id) == "delivered"
    return run


class TestWhatTheRunMustNotDo:
    """The other half of every batch. A ruling that only says what happens is
    half a ruling: each of these was a live defect."""

    def test_arrive_on_an_uncommitted_mission_tells_nobody(self, run, mail):
        """BATCH 4. It used to mail a broker "Truck arrived on site SAFELY"
        for a mission with no load, no run and no START RUN."""
        run.arrived("PICKUP")

        assert mail.handled == []

    def test_book_does_not_commit(self, run):
        """BATCH 2. Pressing *Book Load* satisfied `is_committed()` everywhere
        that asks the gate, with none of COMMIT's consequences."""
        from dispatch import commitment

        _as_operations(run.c)
        run.c.post("/api/sandbox/%s/accept" % run.id)

        assert not commitment.is_committed(run.record)

    def test_the_advance_button_cannot_archive(self, run):
        """BATCH 5. It wrote `archived` and filed nothing -- the load left
        every active list with no record it had been archived."""
        _walk_to_delivered(run)
        run.attached("pod", "pod.pdf")
        _as_operations(run.c)

        answer = run.c.patch("/api/dispatch/loads/%s" % run.id,
                             json={"status": "archived"})

        assert answer.status_code >= 400
        assert _status(run.id) == "completed"

    def test_archive_refuses_a_file_nobody_reviewed(self, run):
        """BATCH 5. *"Archive eligibility therefore depends upon: Mission
        completion / Operations closeout review / Recorded closeout act."*"""
        _walk_to_delivered(run)
        run.attached("pod", "pod.pdf").archived()

        assert run.last.status_code >= 400

    def test_a_started_run_cannot_be_deleted(self, run):
        """BATCH 1. `en_route_pickup -> cancelled -> delete` removed a run that
        had begun, over the API, with no trace."""
        run.committed().milestone("en_route_pickup")
        _as_operations(run.c)

        run.c.delete("/api/dispatch/loads/%s" % run.id)

        from dispatch import services as dispatch_svc

        assert dispatch_svc.get_load(run.id) is not None

    def test_the_old_attach_routes_are_gone(self, run):
        """BATCH 8. A second door that still opens is still a second answer."""
        run.committed()
        _as_driver(run.c)

        for gone in ("pod", "photos"):
            assert run.c.post("/portal/mission/%s/%s" % (run.id, gone)).status_code >= 400


class TestTheRecordTellsTheTruthAfterwards:
    def test_a_note_written_for_the_customer_survives_the_whole_run(self, run):
        """BATCH 6. It survived until the driver tapped anything."""
        from dispatch import services as dispatch_svc

        run.committed()
        dispatch_svc.update_visibility_notes(
            run.id, customer_note="Receiver called; dock open till 18:00.")
        for event in ("en_route_pickup", "arrived_pickup", "loaded",
                      "departed_pickup", "arrived_delivery", "delivered"):
            run.milestone(event)
        run.attached("pod", "pod.pdf").closed_out().archived()

        assert dispatch_svc.get_visibility(run.id)["customer_note"] == \
            "Receiver called; dock open till 18:00."

    def test_the_finished_driver_is_not_told_his_load_was_never_opened(self, run):
        """BATCH 3 and BATCH 9. `completed` was in the closed-status list, so
        the cockpit denied the run at the moment it was finished -- and pointed
        at *Book Load*, which had stopped opening anything."""
        _walk_to_delivered(run)
        run.attached("pod", "pod.pdf")
        _as_driver(run.c)

        page = run.c.get("/portal/mission/%s" % run.id).get_data(as_text=True)

        assert "COMPLETED" in page
        assert "Book Load" not in page

    def test_the_closing_document_prints_no_word_about_the_delivery(self, run):
        """BATCH 3 made the packet print "Delivered" only when the load row
        said so -- it had printed it unconditionally, including for a load that
        never delivered.

        **The Owner then struck the placeholder entirely** (2026-09-17): *"delete
        delivery_status and pod_status, they are software created too."* The
        safeguard is not weakened, it is unnecessary: there is no longer a
        status line to get wrong. The milestone is the fact."""
        _walk_to_delivered(run)
        run.attached("pod", "pod.pdf")

        report = run.record["closing_packet"]
        out = Path(report["documents"][0]["output"])
        with zipfile.ZipFile(str(out)) as z:
            body = z.read("word/document.xml").decode("utf-8")
        assert "Delivered" not in body
        assert "delivery_status" in report["removed"]
        assert _status(run.id) == "completed"

    def test_the_closeout_records_who_looked(self, run):
        """BATCH 5. The act recorded is *"I reviewed this file."*"""
        from dispatch import store

        _walk_to_delivered(run)
        run.attached("pod", "pod.pdf").closed_out(note="POD came back clean.")

        load = store.get_load(run.id)
        assert load["closed_out_at"] and load["closed_out_by"] == "mike"
        assert load["closeout_note"] == "POD came back clean."


class TestTheDoctrineHoldsAcrossTheWhole:
    """Not any one act -- the rules that must be true of all of them."""

    def test_every_day_still_begins_open(self):
        """BATCH 7. *"Dispatch does not decide ... which days are closed.
        Human authority remains final."*"""
        from dispatch import booking

        assert set(booking.WEEK_PATTERN.values()) == {booking.OPEN}

    def test_a_committed_run_reserves_no_day(self, run):
        """Booking identifies conflicts; it never reserves."""
        from dispatch import booking

        run.committed()
        board = booking.build(records=sandbox.get_all())

        assert all(d["state"] in (booking.OPEN, booking.BOOKED) for d in board["board"])

    def test_one_operation_writes_a_retention_record(self):
        source = open("dispatch/services.py", encoding="utf-8").read()

        assert source.count("store.create_retention(") == 1

    def test_one_operation_writes_visibility(self):
        source = open("dispatch/services.py", encoding="utf-8").read()

        assert source.count("store.upsert_visibility(") == 1

    def test_the_engine_does_not_reach_further_into_the_portal(self):
        """**A ratchet, not a rule.** The engine imports the portal in nine
        modules -- for data directories, the sandbox, the publisher, the
        conflict model. Whether that is allowed is an architectural question
        the Owner has not answered, and it is on his open list; an engineer
        deciding it by deleting fifteen imports would be writing doctrine.

        So this pins what exists. It cannot get worse without somebody reading
        this docstring and going to him for a ruling.

        BATCH 10 found it. `dispatch/audit.py` is the only one at module level;
        the rest are deferred inside functions, which is why nothing has broken
        yet -- an optional plug-in absent still imports."""
        import pathlib

        found = set()
        for path in sorted(pathlib.Path("dispatch").rglob("*.py")):
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith(("from portal", "import portal")):
                    found.add("%s: %s" % (path.as_posix(), stripped))

        assert len(found) == 15, (
            "the engine's reach into the portal changed (%d, was 15). "
            "Adding one needs the Owner's ruling on the boundary; removing "
            "one, update this number and say so in the DECISION_LOG.\n%s"
            % (len(found), "\n".join(sorted(found))))
