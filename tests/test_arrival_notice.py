"""ARRIVE, and the four notices that get read before any go on their own.

Pressing ARRIVE creates a documented arrival event and produces the Arrival
Notice from it. It is the only outbound act in the system that does not wait
for a human, because arrival evidence is worth nothing if it is not
contemporaneous.

The first four are drafted. The operator reads them in Outlook and confirms the
template says what he wants said under his company's name. After that there is
nothing left to re-check: it is one fixed template filled from the load card and
the arrival event, with no per-broker variation.
"""

from __future__ import annotations

import pytest

from dispatch import arrival
from portal import cockpit, joe_voice
from portal.models import sandbox


class FakeMail:
    """Records what it was asked to do. Sends nothing anywhere."""

    def __init__(self, ok=True):
        self.ok = ok
        self.drafted = []
        self.sent = []

    def draft(self, to, subject, body, **kw):
        self.drafted.append({"to": to, "subject": subject, "body": body, **kw})
        return {"ok": self.ok, "drafted": self.ok, "sent": False,
                "blocker": "" if self.ok else "Outlook is not open"}

    def send(self, to, subject, body, **kw):
        self.sent.append({"to": to, "subject": subject, "body": body, **kw})
        return {"ok": self.ok, "sent": self.ok, "drafted": False,
                "blocker": "" if self.ok else "Outlook is not open"}


def _records(produced):
    """A store holding `produced` notices already made."""
    return {f"M{i}": {"arrival_notice_sent_at": "2026-09-0%d" % (i + 1)}
            for i in range(produced)}


NOTICE = {"title": "DELIVERY ARRIVAL NOTICE", "phase": "DELIVERY",
          "opening": "Truck arrived on site.",
          "fields": [{"key": "Date", "value": "2026-09-02"},
                     {"key": "Time", "value": "12:04"},
                     {"key": "Facility", "value": "Mayo Clinic, San Pablo Rd"},
                     {"key": "GPS", "value": ""}],
          "follows_intro": "The following documents will be provided:",
          "follows": ("Signed POD", "Packing List")}

RECORD = {"card_data": {"load_id": "ROC-2026-884471"},
          "load_number": "ROC-2026-884471"}


class TestTheVettingPeriod:
    @pytest.mark.parametrize("produced,drafts", [(0, True), (1, True),
                                                 (2, True), (3, True),
                                                 (4, False), (9, False)])
    def test_the_first_four_are_drafted_and_the_rest_are_sent(self, produced, drafts):
        assert arrival.should_draft(_records(produced)) is drafts

    def test_it_counts_notices_rather_than_keeping_a_counter(self):
        """A counter is a second source of truth that can disagree with what
        actually happened. Counting the notices that exist cannot."""
        store = {"A": {"arrival_notice_sent_at": "x"},
                 "B": {"arrival_notice_drafted_at": "y"},
                 "C": {"arrived_at": "z"}}  # arrived, no notice produced
        assert arrival.notices_produced(store) == 2
        assert arrival.vetting_remaining(store) == 2

    def test_a_drafted_notice_counts_toward_the_four(self):
        """The point is reading them, not sending them."""
        assert arrival.notices_produced(
            {"A": {"arrival_notice_drafted_at": "x"}}) == 1


class TestWhatItDoesWithTheNotice:
    def test_the_first_one_is_drafted_never_sent(self):
        mail = FakeMail()
        out = arrival.deliver(RECORD, NOTICE, records={}, mail=mail,
                              recipient="dispatch@xpo.example")
        assert out["drafted"] is True
        assert out["sent"] is False
        assert mail.sent == []
        assert len(mail.drafted) == 1

    def test_the_fifth_one_sends(self):
        mail = FakeMail()
        out = arrival.deliver(RECORD, NOTICE, records=_records(4), mail=mail,
                              recipient="dispatch@xpo.example")
        assert out["sent"] is True
        assert out["drafted"] is False
        assert len(mail.sent) == 1

    def test_every_notice_is_blind_copied_to_the_office(self):
        """The office holds the evidence whether or not the driver is
        reachable later."""
        mail = FakeMail()
        arrival.deliver(RECORD, NOTICE, records={}, mail=mail,
                        recipient="dispatch@xpo.example")
        assert mail.drafted[0]["bcc"] == arrival.NOTICE_BCC == "Ops@l1truck.com"

    def test_the_load_number_is_on_the_subject(self):
        mail = FakeMail()
        arrival.deliver(RECORD, NOTICE, records={}, mail=mail,
                        recipient="dispatch@xpo.example")
        assert "ROC-2026-884471" in mail.drafted[0]["subject"]

    def test_every_field_appears_even_when_empty(self):
        """An empty field is not a negative -- it means no entry, and it says
        so where it can be seen. A field that disappears when unfilled hides
        the gap from the one person who could still close it."""
        text = arrival.notice_text(NOTICE)
        assert "GPS:" in text
        assert "Mayo Clinic, San Pablo Rd" in text

    def test_an_empty_field_is_left_empty_not_filled_in(self):
        """Showing the label is not the same as inventing a value. This goes
        out under Level 1 Transport's name."""
        text = arrival.notice_text(NOTICE)
        gps = [l for l in text.splitlines() if l.startswith("GPS:")][0]
        assert gps.strip() == "GPS:"

    def test_it_says_the_truck_arrived_safely(self):
        """The operator's word. A customer wanted to know the truck is fine
        before they wanted to know it is on the property."""
        notice = cockpit.arrival_notice_for(RECORD, cockpit.MODE_DELIVERY)
        assert notice["opening"] == "Truck arrived on site SAFELY."

    def test_there_is_a_way_to_answer_it(self):
        """A notice giving the reader no reply path is a broadcast."""
        text = arrival.notice_text(NOTICE)
        assert text.rstrip().endswith("Ops@l1truck.com")

    def test_it_signs_off_as_the_company(self):
        text = arrival.notice_text(NOTICE)
        assert "Level 1 Transport" in text
        assert "Jacksonville Regional Micro-Response Carrier" in text


class TestItNeverClaimsWhatItDidNotDo:
    def test_no_recipient_means_nothing_went_and_it_says_so(self):
        mail = FakeMail()
        out = arrival.deliver(RECORD, NOTICE, records={}, mail=mail, recipient="")
        assert out["sent"] is False and out["drafted"] is False
        assert mail.drafted == [] and mail.sent == []
        assert "on record" in out["note"]

    def test_a_failed_send_is_reported_as_failed(self):
        mail = FakeMail(ok=False)
        out = arrival.deliver(RECORD, NOTICE, records=_records(4), mail=mail,
                              recipient="dispatch@xpo.example")
        assert out["sent"] is False
        assert out["arrival_notice_error"]

    def test_no_connector_still_records_the_arrival(self):
        out = arrival.deliver(RECORD, NOTICE, records={}, mail=None,
                              recipient="dispatch@xpo.example")
        assert out["ok"] is False
        assert "on record" in out["note"]

    @pytest.mark.parametrize("case", ["no_recipient", "no_mail", "failed"])
    def test_the_driver_never_reads_an_engineering_word(self, case):
        mail = {"no_recipient": FakeMail(), "no_mail": None,
                "failed": FakeMail(ok=False)}[case]
        out = arrival.deliver(
            RECORD, NOTICE, records={}, mail=mail,
            recipient="" if case == "no_recipient" else "a@b.example")
        assert joe_voice.is_driver_safe(out.get("note", "")) == []


class TestTheButtonIsActuallyWired:
    """It carried `data-action="arrive"` and nothing listened to it."""

    @pytest.fixture(autouse=True)
    def _isolate(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
        yield

    @pytest.fixture()
    def client(self):
        from portal.app import create_app

        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    @pytest.fixture()
    def mission(self):
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="ARRIVE-1", title="Arrive probe",
            card_data={"load_id": "ARRIVE-1"}, summary="")
        return entry["id"]

    def test_the_page_listens_for_the_click(self, client, mission):
        html = client.get(f"/portal/mission/{mission}?view=DELIVERY").get_data(as_text=True)
        assert 'data-action="arrive"' in html
        assert "'[data-action=\"arrive\"]'" in html or \
               '[data-action="arrive"]' in html.split("<script>")[-1]

    def test_arriving_stamps_the_record(self, client, mission, monkeypatch):
        from portal.routes import joe_portal

        monkeypatch.setattr(joe_portal, "_mail_connector", lambda: FakeMail())
        response = client.post(f"/portal/mission/{mission}/arrive",
                               data={"view": "DELIVERY"})
        assert response.status_code == 200
        record = sandbox.get(mission)
        assert record["arrived_at"]
        assert record["arrived_date"] and record["arrived_time"]

    def test_a_gps_fix_is_recorded_when_offered(self, client, mission, monkeypatch):
        from portal.routes import joe_portal

        monkeypatch.setattr(joe_portal, "_mail_connector", lambda: FakeMail())
        client.post(f"/portal/mission/{mission}/arrive",
                    data={"view": "DELIVERY", "gps": "30.25861, -81.44028"})
        assert sandbox.get(mission)["delivery_gps"] == "30.25861, -81.44028"

    def test_no_gps_invents_none(self, client, mission, monkeypatch):
        from portal.routes import joe_portal

        monkeypatch.setattr(joe_portal, "_mail_connector", lambda: FakeMail())
        client.post(f"/portal/mission/{mission}/arrive", data={"view": "DELIVERY"})
        assert not sandbox.get(mission).get("delivery_gps")

    def test_an_unknown_mission_arrives_nowhere(self, client):
        assert client.post("/portal/mission/NOPE/arrive").status_code == 404
