"""Mission Record -> Attach Artifact. One path, many classifications.

**MISSION ARTIFACT ATTACHMENT RULE, Mike Zachary, 2026-09-16:**

    The answer should always be: Mission Record -> Attach Artifact.
    Everything else is classification.

There were three attach routes -- `cockpit_pod` and `cockpit_photos` twice --
and **no way at all to attach a Bill of Lading**, which is the controlling
freight document (*"Federal BOL = controlling freight document"*). Asked where
a document goes, the build had three answers and one shrug.

**Every test here arrives through an HTTP route.** The last two batches were
both made possible by consequences that lived in a handler rather than in the
act, and only a test that presses the real control can tell the difference.
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
    with zipfile.ZipFile(str(templates / "02_POD_Cover 1.docx"), "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", DOC % (
            "<w:p><w:r><w:t>{{load_number}}</w:t></w:r></w:p>"))
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
def running(client):
    """A committed mission with a run under way."""
    from portal.models import opportunity_card as oc

    rid = oc.from_capture({
        "opportunity_id": "ART-1", "origin": "Jacksonville, FL",
        "destination": "Savannah, GA", "contact": "Penske Logistics",
        "commodity": "Auto Parts", "pickup_date": "2026-09-21 09:00",
        "delivery_date": "2026-09-21 14:00"})["id"]
    with client.session_transaction() as s:
        s["user_id"] = "mike"
    assert client.post("/brief/mission/%s/commit" % rid).status_code in (200, 302)
    with client.session_transaction() as s:
        s.pop("user_id", None)
    for event in ("en_route_pickup", "arrived_pickup", "loaded"):
        client.post("/portal/mission/%s/milestone" % rid,
                    data={"milestone_event": event})
    return rid


def _attach(client, record_id, classification, name="doc.pdf", count=1):
    files = [(io.BytesIO(b"%PDF-1.4 signed"), "%d_%s" % (i, name))
             for i in range(count)]
    return client.post(
        "/portal/mission/%s/attach" % record_id,
        data={"classification": classification,
              "artifact": files if count > 1 else files[0]},
        content_type="multipart/form-data")


def _kinds(record_id):
    from dispatch import services as dispatch_svc

    return [e["evidence_type"]
            for e in dispatch_svc.get_load_bundle(record_id)["evidence"]]


class TestTheBillOfLadingHasADoor:
    """It had none. The controlling freight document could not be attached by
    anyone, from any screen, at all."""

    def test_a_bol_can_be_attached(self, client, running):
        answer = _attach(client, running, "bol")

        assert answer.status_code in (200, 302)
        assert "bol" in _kinds(running)

    def test_the_cockpit_offers_it(self, client, running):
        page = client.get("/portal/mission/%s" % running).get_data(as_text=True)

        assert "SIGNED BOL" in page

    def test_attaching_a_bol_tells_no_customer(self, client, running):
        """A BOL is evidence, not an announcement. Telling a customer is a
        different act with a different owner."""
        before = sandbox.get(running)

        _attach(client, running, "bol")

        after = sandbox.get(running)
        assert after.get("arrival_notice_sent_at") == before.get("arrival_notice_sent_at")

    def test_it_does_not_finish_the_run(self, client, running):
        from dispatch import services as dispatch_svc

        _attach(client, running, "bol")

        assert dispatch_svc.get_load(running)["status"] != "completed"


class TestOnePath:
    def test_every_cockpit_tile_posts_to_the_one_route(self):
        """Separate tiles are classification, not separate paths: a driver at a
        dock taps one thing rather than working a dropdown."""
        page = open("portal/templates/joe_portal.html", encoding="utf-8").read()
        drawer = page.split('id="drawer-uploads"')[1].split("</aside>")[0]

        assert "cockpit_pod" not in drawer
        assert "cockpit_photos" not in drawer
        # Five tiles since 2026-09-17: BOL, POD, and his three photo moments.
        # It was four, and the two photo tiles carried the wrong names.
        assert drawer.count("cockpit_attach") == 5
        for name in ("PHOTOS - LOADED VEHICLE", "PHOTOS - MID-ROUTE SECUREMENT",
                     "PHOTOS - FINAL CONDITION"):
            assert name in drawer, name
        assert "FREIGHT CONDITION" not in drawer

    def test_the_old_routes_are_gone(self, client, running):
        """Not redirected -- gone. A second door that still opens is still a
        second answer.

        405 rather than 404 because `<path:record_id>` swallows the suffix, so
        the URL resolves to the read-only mission view; either way no handler
        accepts the post."""
        for gone in ("pod", "photos"):
            answer = client.post("/portal/mission/%s/%s" % (running, gone))
            assert answer.status_code >= 400, gone
        assert _kinds(running) == []

    def test_an_unknown_classification_is_refused(self, client, running):
        _attach(client, running, "receipt_maybe")

        assert _kinds(running) == []

    def test_the_refusal_names_what_was_expected(self, client, running):
        answer = client.post("/portal/mission/%s/attach" % running,
                             data={"classification": "bol"},
                             content_type="multipart/form-data",
                             follow_redirects=True)

        assert "No signed bol was attached." in answer.get_data(as_text=True)

    def test_a_single_document_is_not_attached_in_bulk(self, client, running):
        """A POD is one document. Two of them is a mistake worth catching, not
        two PODs."""
        _attach(client, running, "pod", count=2)

        assert _kinds(running) == []


class TestTheClassificationCarriesTheConsequence:
    def test_a_pod_finishes_the_run(self, client, running):
        from dispatch import services as dispatch_svc

        for event in ("departed_pickup", "arrived_delivery", "delivered"):
            client.post("/portal/mission/%s/milestone" % running,
                        data={"milestone_event": event})

        _attach(client, running, "pod")

        assert dispatch_svc.get_load(running)["status"] == "completed"

    def test_and_files_the_closing_packet(self, client, running):
        for event in ("departed_pickup", "arrived_delivery", "delivered"):
            client.post("/portal/mission/%s/milestone" % running,
                        data={"milestone_event": event})

        _attach(client, running, "pod")

        assert sandbox.get(running)["closing_packet"]["documents"]

    def test_photos_still_reach_mission_visibility(self, client, running):
        _attach(client, running, "securement_photo", name="strap.jpg", count=2)

        assert _kinds(running) == ["securement_photo", "securement_photo"]


class TestTheParkedScreenIsNotASecondAnswer:
    """The Driver Portal is parked but its POD route still worked -- and
    **completed a run without filing the packet**, because the packet was built
    by the cockpit's handler rather than by the act. The same dead end the
    regression audit found, surviving on the other screen."""

    def test_the_packet_follows_the_act_not_the_route(self):
        source = open("portal/routes/driver_portal.py", encoding="utf-8").read()

        assert "artifact_intake.attach" in source
        assert "driver_actions.upload_pod" not in source

    def test_the_packet_builder_lives_with_the_act(self):
        source = open("portal/artifact_intake.py", encoding="utf-8").read()

        assert "def build_closing_packet" in source
