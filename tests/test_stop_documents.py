"""The paper a driver carries in, prepared before he needs it.

**Owner, 2026-09-17**, describing his own day:

    the truck is parked and stored at a location miles away. The driver begins
    ELD, pre-trip inspection, fuels along the way. at some point the activation
    of pickup is done and Publisher creates load documents and ques for
    printing upon arrival at pickup location. Driver prints, clipboards them
    and enters.

And what the two documents are, from `D:\\Library\\Templates\\Document List.docx`:

    Pickup Confirmation - POP - this document is signed by shipping personnel
    ... These documents will be scanned before departure.

    Delivery Confirmation - POD is signed and scanned ... This is a legal
    receipt of goods for Florida lien laws and UCC1 filing if needed.

**They are forms a person signs at a dock**, and `closing_packet.build()`
produced them when the load reached `completed` -- after the POD had already
come back. They could never have served their purpose. This file holds the
correction: generation at activation, and the closing packet stops making them.

There is no PRINT control and there should not be one. *"done it for years ...
it can open emails with attachments and send to a local API connected printer.
no browser is used."* He prints in the cab. Dispatch's whole job is to have the
mail sitting there before he arrives.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from portal.models import sandbox

DOC = ("<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
       "<w:document xmlns:w='x'><w:body>%s</w:body></w:document>")

#: His numbering. The two dock forms, the four the closing packet still makes,
#: and the onboarding policy that should reach neither.
SHELF = {
    "01_Invoice 1.docx": "{{load_number}}",
    "02_POD_Cover 1.docx": "{{load_number}}",
    "03_Delivery_Confirmation 1.docx": "{{load_number}} {{consignee}}",
    "04_Billing_Cover 1.docx": "{{load_number}}",
    "05_Pickup_Confirmation 1.docx": "{{load_number}} {{pickup_location}}",
    "06_Closeout_Thank_You 1.docx": "{{customer}}",
    "07_Detention_Policy 1.docx": "{{customer}}",
}


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    monkeypatch.setenv("DISPATCH_DB_PATH", str(tmp_path / "dispatch.db"))
    monkeypatch.setenv("DISPATCH_PACKET_ROOT", str(tmp_path / "packets"))

    templates = tmp_path / "Memory" / "Templates"
    templates.mkdir(parents=True)
    for name, body in SHELF.items():
        with zipfile.ZipFile(str(templates / name), "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("word/document.xml",
                       DOC % ("<w:p><w:r><w:t>%s</w:t></w:r></w:p>" % body))
    monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(tmp_path / "Memory"))

    from dispatch import scheduling

    monkeypatch.setattr(scheduling, "_outlook_is_running", lambda: False)
    yield


class _Mail:
    """Records what it was asked to send. Sends nothing anywhere."""

    def __init__(self):
        self.sent = []

    def send(self, to, subject, body, bcc="", attachments=None, **kw):
        self.sent.append({"to": to, "subject": subject, "body": body,
                          "attachments": list(attachments or [])})
        return {"ok": True}

    def draft(self, to, subject, body, bcc="", attachments=None, **kw):
        return {"ok": True}


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
        with c.session_transaction() as s:
            s["driver_open"] = True
            s["role"] = "Driver"
        yield c


@pytest.fixture()
def running(client, mail):
    """A committed mission, not yet started."""
    from portal.models import opportunity_card as oc

    rid = oc.from_capture({
        "opportunity_id": "STOP-1", "origin": "Jacksonville, FL",
        "destination": "Savannah, GA", "contact": "Penske Logistics",
        "commodity": "Auto Parts", "pickup_date": "2026-09-21 09:00",
        "delivery_date": "2026-09-21 16:00"})["id"]
    with client.session_transaction() as s:
        s["user_id"] = "mike"
    assert client.post("/brief/mission/%s/commit" % rid).status_code in (200, 302)
    with client.session_transaction() as s:
        s.pop("user_id", None)
    return rid


def _milestone(client, record_id, event):
    return client.post("/portal/mission/%s/milestone" % record_id,
                       data={"milestone_event": event})


def _prepared(record_id):
    return (sandbox.get(record_id) or {}).get("stop_documents") or {}


class TestStartRunPreparesThePickupForm:
    def test_the_form_is_filled_when_the_run_starts(self, client, running):
        """Not at the dock, and not at the end of the run."""
        _milestone(client, running, "en_route_pickup")

        report = _prepared(running)["pickup"]
        assert report["documents"]
        assert Path(report["documents"][0]["output"]).exists()

    def test_it_is_the_pickup_confirmation_and_nothing_else(self, client, running):
        """*"pickup set 05"* -- one form, the one that gets signed."""
        _milestone(client, running, "en_route_pickup")

        names = [Path(d["output"]).name for d in _prepared(running)["pickup"]["documents"]]
        assert len(names) == 1
        assert names[0].startswith("05")

    def test_it_is_filed_under_its_own_stop(self, client, running):
        """So the second stop does not overwrite the first."""
        _milestone(client, running, "en_route_pickup")

        assert Path(_prepared(running)["pickup"]["folder"]).name == "pickup"

    def test_it_reaches_the_cab_as_an_attachment(self, client, running, mail):
        """*"Doc files in folders emails with attachments."* He opens it in the
        truck and prints to the local printer."""
        _milestone(client, running, "en_route_pickup")

        assert mail.sent, "nothing was sent to the cab"
        assert mail.sent[0]["attachments"], "the mail carried no document"
        assert mail.sent[0]["attachments"][0].endswith(".docx")

    def test_the_subject_says_which_stop(self, client, running, mail):
        _milestone(client, running, "en_route_pickup")

        assert "Pickup" in mail.sent[0]["subject"]


class TestRollingPreparesTheDeliveryForm:
    def test_the_delivery_form_is_filled_when_he_rolls(self, client, running):
        """*"delivery set 03"*, prepared at departure so it is waiting when he
        arrives."""
        for event in ("en_route_pickup", "arrived_pickup", "loaded",
                      "departed_pickup"):
            _milestone(client, running, event)

        names = [Path(d["output"]).name
                 for d in _prepared(running)["delivery"]["documents"]]
        assert len(names) == 1
        assert names[0].startswith("03")

    def test_both_stops_are_kept(self, client, running):
        for event in ("en_route_pickup", "arrived_pickup", "loaded",
                      "departed_pickup"):
            _milestone(client, running, event)

        assert set(_prepared(running)) == {"pickup", "delivery"}

    def test_a_milestone_that_carries_no_paper_prepares_nothing(self, client, running):
        _milestone(client, running, "en_route_pickup")
        before = dict(_prepared(running))

        _milestone(client, running, "arrived_pickup")

        assert _prepared(running) == before


class TestTheClosingPacketStopsMakingDockForms:
    def test_neither_dock_form_is_generated_at_the_end(self, client, running):
        """**The correction.** They were produced at `completed`, after the POD
        had already come back -- a form for a dock, made when the run was over.
        What reaches the packet now is the scanned signed copy."""
        from dispatch import closing_packet

        names = [p.name for p in closing_packet.templates_in(
            _shelf().parent, without=closing_packet._NOT_IN_THE_CLOSING_PACKET)]

        assert not any(n.startswith("03") for n in names)
        assert not any(n.startswith("05") for n in names)

    def test_the_onboarding_policy_is_not_a_load_document(self):
        """*"yes, exclude 07"*. His Document List names what the Closing Packet
        holds, and the Detention Time Policy is not among them."""
        from dispatch import closing_packet

        names = [p.name for p in closing_packet.templates_in(
            _shelf().parent, without=closing_packet._NOT_IN_THE_CLOSING_PACKET)]

        assert not any(n.startswith("07") for n in names)

    def test_the_four_that_belong_are_still_made(self):
        from dispatch import closing_packet

        names = sorted(p.name[:2] for p in closing_packet.templates_in(
            _shelf().parent, without=closing_packet._NOT_IN_THE_CLOSING_PACKET))

        assert names == ["01", "02", "04", "06"]

    def test_a_set_the_shelf_cannot_answer_says_so(self):
        """An empty packet that looks successful is worse than a refusal."""
        from dispatch import closing_packet

        report = closing_packet.build({"load_number": "L1-TEST"},
                                      shelf=_shelf().parent, only=("99",))

        assert report["ok"] is False
        assert "99" in report["note"]


def _shelf() -> Path:
    """The Templates folder. `templates_in` takes the shelf above it."""
    import os

    return Path(os.environ["DISPATCH_MEMORY_ROOT"]) / "Templates"


class TestItNeverCostsTheRun:
    def test_a_quiet_mailbox_does_not_stop_the_milestone(self, client, running,
                                                         monkeypatch):
        """A driver who has started his run has started it, whether or not
        Outlook was open."""
        from dispatch import services as dispatch_svc
        from portal.routes import joe_portal

        monkeypatch.setattr(joe_portal, "_mail_connector", lambda: None)

        _milestone(client, running, "en_route_pickup")

        assert dispatch_svc.get_load(running)["status"] == "en_route_pickup"
        assert _prepared(running)["pickup"]["sent"] is False

    def test_the_documents_are_still_filed_when_nothing_is_sent(self, client,
                                                                running, monkeypatch):
        from portal.routes import joe_portal

        monkeypatch.setattr(joe_portal, "_mail_connector", lambda: None)

        _milestone(client, running, "en_route_pickup")

        assert _prepared(running)["pickup"]["documents"]
