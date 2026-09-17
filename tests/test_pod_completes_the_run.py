"""The POD path, pressed the way a driver presses it.

**Owner ruling, 2026-09-16:** *"POD sent completes the load and triggers the
closing packet."*

The ruling was implemented in `_MILESTONE_TO_STATUS` and the packet trigger was
wired to the milestone route -- but the button a driver actually presses posts
to `cockpit_pod`, which only attached the file. So the load stayed `delivered`,
the cockpit went on asking for the POD that had just been sent, and the packet
was reachable only from the hidden milestone drawer. The regression audit found
it the same day.

**Every test here arrives through an HTTP route**, because that is the only
thing that would have caught it. From `CLAUDE.md` §7: *"A test that builds its
own precondition proves the logic and says nothing about whether the
application can reach it."* `tests/test_closing_packet.py` calls `build()`
directly and passed throughout; that is exactly why the dead end survived.
"""

from __future__ import annotations

import io
import zipfile

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
    path = templates / "02_POD_Cover_Sheet 1.docx"
    with zipfile.ZipFile(str(path), "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", DOC % (
            "<w:p><w:r><w:t>{{load_number}} : {{delivery_status}}</w:t></w:r></w:p>"))
    monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(shelf))

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
            s["driver_open"] = True
            s["role"] = "Driver"
        yield c


@pytest.fixture()
def delivered(client):
    """A load walked to `delivered` through the cockpit's own routes."""
    from dispatch import commitment
    from portal.models import opportunity_card as oc
    from portal.routes import joe_portal

    record = oc.from_capture({
        "opportunity_id": "POD-1", "origin": "Jacksonville, FL",
        "destination": "Savannah, GA", "contact": "Penske Logistics",
        "commodity": "Auto Parts", "pickup_date": "2026-09-21 09:00",
        "delivery_date": "2026-09-21 14:00",
    })
    rid = record["id"]
    data = sandbox._load()
    data[rid].update(commitment.commit(dict(data[rid]), when="2026-09-20T12:00:00Z"))
    sandbox._save(data)
    joe_portal._open_operational_load(rid, sandbox.get(rid))

    for event in ("en_route_pickup", "arrived_pickup", "loaded",
                  "departed_pickup", "arrived_delivery", "delivered"):
        client.post("/portal/mission/%s/milestone" % rid,
                    data={"milestone_event": event})
    return rid


def _status(record_id: str) -> str:
    from dispatch import services as dispatch_svc

    return str((dispatch_svc.get_load(record_id) or {}).get("status") or "")


def _send_pod(client, record_id: str, name: str = "pod.pdf"):
    return client.post("/portal/mission/%s/pod" % record_id,
                       data={"pod_file": (io.BytesIO(b"%PDF-1.4 signed"), name)},
                       content_type="multipart/form-data")


class TestSendingThePodEndsTheRun:
    def test_the_load_is_delivered_before_it_goes_up(self, client, delivered):
        assert _status(delivered) == "delivered"

    def test_uploading_the_pod_completes_the_load(self, client, delivered):
        """The defect: this used to attach the file and stop."""
        _send_pod(client, delivered)

        assert _status(delivered) == "completed"

    def test_the_cockpit_stops_asking_for_it(self, client, delivered):
        """*"the cockpit went on asking for a POD after it had been sent, for
        ever."*"""
        _send_pod(client, delivered)

        page = client.get("/portal/mission/%s" % delivered).get_data(as_text=True)

        assert "UPLOAD THE POD" not in page

    def test_the_closing_packet_is_filed(self, client, delivered):
        _send_pod(client, delivered)

        report = sandbox.get(delivered)["closing_packet"]
        assert report["ok"] is True
        assert report["documents"]

    def test_the_packet_is_filed_under_the_load_number(self, client, delivered):
        from pathlib import Path

        _send_pod(client, delivered)

        report = sandbox.get(delivered)["closing_packet"]
        folder = Path(report["folder"])
        assert list(folder.glob("*.docx"))
        assert folder.name == (report["load_number"] or "no-load-number")

    @pytest.mark.xfail(reason="Finding, 2026-09-16: a captured load never gets a "
                              "load number, so its packet files under "
                              "'no-load-number'. The tracing number is the "
                              "whole filing system. Owner's to rule: assign at "
                              "COMMIT.", strict=True)
    def test_a_captured_load_is_filed_under_a_real_number(self, client, delivered):
        """**Found by this file, not by the audit.** A load typed on the New
        Mission screen gets a number from `mission_template.to_record`. A load
        captured by voice, paste or alert goes through `from_capture`, which
        assigns none, and COMMIT does not either -- so a completed captured run
        files its POD, invoice and closing documents in a folder called
        `no-load-number`.

        Against the filing ruling of 2026-09-15: *"a folder inside of Library
        according to that number for retervial from Archive. **that is the
        tracing number.** same system used by FedEx/ UPS and others."*"""
        _send_pod(client, delivered)

        assert sandbox.get(delivered)["closing_packet"]["load_number"]

    def test_the_document_says_delivered(self, client, delivered):
        from pathlib import Path

        _send_pod(client, delivered)

        out = Path(sandbox.get(delivered)["closing_packet"]["documents"][0]["output"])
        with zipfile.ZipFile(str(out)) as z:
            assert "Delivered" in z.read("word/document.xml").decode("utf-8")


class TestItIsKeyedOnWhatHappened:
    """Not on which button was pressed. An earlier version fired on the event
    without looking at the result."""

    def test_a_pod_on_a_load_that_never_delivered_builds_no_packet(self, client):
        """The evidence is kept -- a POD is a fact -- but the run did not
        finish, so nothing is filed and no customer document claims it did."""
        from dispatch import commitment
        from portal.models import opportunity_card as oc
        from portal.routes import joe_portal

        record = oc.from_capture({
            "opportunity_id": "POD-2", "origin": "Jacksonville, FL",
            "destination": "Savannah, GA", "commodity": "Pallets",
            "pickup_date": "2026-09-21 09:00", "delivery_date": "2026-09-21 14:00"})
        rid = record["id"]
        data = sandbox._load()
        data[rid].update(commitment.commit(dict(data[rid]), when="2026-09-20T12:00:00Z"))
        sandbox._save(data)
        joe_portal._open_operational_load(rid, sandbox.get(rid))

        answer = _send_pod(client, rid)

        assert answer.status_code in (200, 302)
        assert _status(rid) == "created", "the transition is still gated"
        assert "closing_packet" not in sandbox.get(rid)

    def test_the_packet_is_built_once(self, client, delivered):
        """Pressing again must not rewrite documents that may already have gone
        out."""
        _send_pod(client, delivered)
        first = sandbox.get(delivered)["closing_packet"]

        client.post("/portal/mission/%s/milestone" % delivered,
                    data={"milestone_event": "pod_received"})

        assert sandbox.get(delivered)["closing_packet"] == first


class TestTheRunEndsWithoutLying:
    def test_the_finished_driver_is_not_told_his_load_was_never_opened(
            self, client, delivered):
        """The audit's finding: `completed` was in the driver's closed-status
        list, so the cockpit said *"This mission has no open load yet.
        Operations opens it with Book Load."* at the exact moment the work was
        done."""
        _send_pod(client, delivered)

        page = client.get("/portal/mission/%s" % delivered).get_data(as_text=True)

        assert "no open load yet" not in page
        assert "Book Load" not in page

    def test_the_status_area_says_the_run_is_complete(self, client, delivered):
        _send_pod(client, delivered)

        page = client.get("/portal/mission/%s" % delivered).get_data(as_text=True)

        assert "COMPLETED" in page

    def test_a_completed_load_is_still_asked_to_be_filed(self):
        """It used to fall silent: `delivered` had a 24-hour stall line and
        `completed` had none, so a finished load could sit unarchived for ever
        with nothing saying so."""
        from dispatch import services as dispatch_svc

        assert "completed" in dispatch_svc._STALL_THRESHOLDS_HOURS
