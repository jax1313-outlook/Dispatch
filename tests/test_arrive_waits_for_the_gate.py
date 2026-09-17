"""ARRIVE, pressed the way a driver presses it.

**Owner ruling, 2026-09-17:** *"gate refuses, no notice goes."* — and, for an
arrival the gate accepts, *"notice must go out, email must be sent."*

The route used to mail the customer **first** and look at the load afterwards,
so a mission that had never been committed — no load, no run, nobody having
pressed START RUN — still put *"Truck arrived on site SAFELY"* in front of a
broker under Level 1 Transport's name. Nothing in the engine stopped it because
the engine was never asked.

Every test here arrives through the HTTP route. `tests/test_arrival_notice.py`
calls `arrival.deliver()` directly and passed throughout, which is why the
ordering defect survived: the unit under test was never the one that was wrong.
"""

from __future__ import annotations

import pytest

from portal.models import sandbox


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    monkeypatch.setenv("DISPATCH_DB_PATH", str(tmp_path / "dispatch.db"))
    monkeypatch.setenv("DISPATCH_PACKET_ROOT", str(tmp_path / "packets"))

    from dispatch import scheduling

    monkeypatch.setattr(scheduling, "_outlook_is_running", lambda: False)
    yield


class _Mail:
    """A mail connector that records instead of sending. No test may reach real
    Outlook (`CLAUDE.md`), and the whole question here is *whether* something
    was handed to mail at all."""

    def __init__(self):
        self.sent = []
        self.drafted = []

    def send(self, to, subject, body, bcc=""):
        self.sent.append({"to": to, "subject": subject, "body": body})
        return {"ok": True}

    def draft(self, to, subject, body, bcc=""):
        self.drafted.append({"to": to, "subject": subject, "body": body})
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
        with c.session_transaction() as s:
            s["driver_open"] = True
            s["role"] = "Driver"
        yield c


CAPTURE = {
    "origin": "Jacksonville, FL", "destination": "Savannah, GA",
    "contact": "Penske Logistics", "commodity": "Auto Parts",
    "pickup_date": "2026-09-21 09:00", "delivery_date": "2026-09-21 14:00",
}


#: A mailbox nobody owns. No test may reach a real inbox (`CLAUDE.md`), and
#: `.invalid` is reserved by RFC 2606 so it can never resolve.
CUSTOMER_EMAIL = "broker@example.invalid"


def _captured(opportunity_id: str, *, email: str = CUSTOMER_EMAIL) -> str:
    """A captured card, given a customer address.

    `from_capture` normalises to a fixed shape that holds no email at all --
    SWEEP, voice and paste never collect one, and it is typed on the brief
    before COMMIT. So the address is written on afterwards, as the New Mission
    screen would have written it. It is contact data, not the act under test:
    nothing here presses ARRIVE by hand or writes a milestone.
    """
    from portal.models import opportunity_card as oc

    rid = oc.from_capture(dict(CAPTURE, opportunity_id=opportunity_id))["id"]
    data = sandbox._load()
    data[rid]["customer_email"] = email
    sandbox._save(data)
    return rid


def _commit(client, record_id: str):
    """COMMIT, through the route. The sole authoritative commitment operation
    (Batch 2) — a fixture that writes the field instead is the habit the
    primary rule forbids."""
    with client.session_transaction() as s:
        s["user_id"] = "mike"
    answer = client.post("/brief/mission/%s/commit" % record_id)
    assert answer.status_code in (200, 302), answer.status_code
    with client.session_transaction() as s:
        s.pop("user_id", None)


def _arrive(client, record_id: str, view: str = "PICKUP"):
    return client.post("/portal/mission/%s/arrive" % record_id,
                       data={"view": view})


class TestARouteThatHasNotStarted:
    def test_a_mission_with_no_open_load_tells_no_customer(self, client, mail):
        """The defect, at its plainest. Nothing was committed, so there is no
        run — and a notice claiming an arrival on it is a false statement."""
        rid = _captured("ARR-1")

        answer = _arrive(client, rid)

        assert mail.handled == [], "a broker was told about a run that never began"
        assert answer.get_json()["sent"] is False

    def test_the_driver_is_told_what_to_press(self, client, mail):
        """The 70 MPH test. A refusal he cannot act on is a dead end."""
        rid = _captured("ARR-2")

        note = _arrive(client, rid).get_json()["note"]

        assert "START RUN" in note

    def test_the_arrival_is_still_his_evidence(self, client, mail):
        """The truck was where he says it was. What a refusal withholds is the
        outbound claim, not the record."""
        rid = _captured("ARR-3")

        _arrive(client, rid)

        assert sandbox.get(rid)["arrived_at"], "his own arrival time was thrown away"

    def test_a_committed_load_that_never_started_tells_no_customer(self, client, mail):
        """COMMIT opens the load; it does not start the run. START RUN is the
        driver's act, so `created` is not an arrival."""
        rid = _captured("ARR-4")
        _commit(client, rid)

        _arrive(client, rid)

        assert mail.handled == []


class TestAnArrivalTheGateAccepts:
    @pytest.fixture()
    def rolling(self, client, mail):
        rid = _captured("ARR-5")
        _commit(client, rid)
        client.post("/portal/mission/%s/milestone" % rid,
                    data={"milestone_event": "en_route_pickup"})
        return rid

    def test_the_notice_goes_out(self, client, mail, rolling):
        """*"notice must go out, email must be sent."* No review step, no
        queue: an arrival notice that is not contemporaneous is worth nothing.
        """
        answer = _arrive(client, rolling)

        assert mail.sent, "the customer was told nothing about a real arrival"
        assert answer.get_json()["sent"] is True

    def test_the_customer_is_the_one_told(self, client, mail, rolling):
        _arrive(client, rolling)

        assert "broker@example.invalid" in mail.sent[0]["to"]

    def test_the_record_carries_the_send(self, client, mail, rolling):
        _arrive(client, rolling)

        stored = sandbox.get(rolling)
        assert stored["arrival_notice_sent_at"]
        assert "arrival_notice_refused" not in stored


class TestWhatTheNoticePromises:
    """*"true from all Template emails. Photos will be available on the
    upcoming website through the Customer Screen."*"""

    def test_no_photographs_are_promised_by_email(self):
        from portal import cockpit

        for phase, follows in cockpit.ARRIVAL_NOTICE_FOLLOWS.items():
            for line in follows:
                assert "photo" not in line.lower(), \
                    "%s still promises %r in an email" % (phase, line)

    def test_the_documents_are_still_promised(self):
        from portal import cockpit

        assert "Bill of Lading (BOL)" in cockpit.ARRIVAL_NOTICE_FOLLOWS["PICKUP"]
        assert "Invoice" in cockpit.ARRIVAL_NOTICE_FOLLOWS["DELIVERY"]


class TestTheScreenDoesNotInventASend:
    def test_arriving_is_not_sending(self):
        """`sent` read `arrived_at`. The two were the same fact only while
        every arrival mailed."""
        from portal import cockpit

        notice = cockpit.arrival_notice_for(
            {"arrived_at": "2026-09-17T09:00:00", "card_data": {}, "numbers": {}},
            cockpit.MODE_PICKUP)

        assert notice["sent"] is False

    def test_a_withheld_notice_is_not_reported_as_a_mail_failure(self):
        """Two different facts with two different answers: nothing was sent
        because the run had not reached this arrival, not because mail broke.
        Telling him the second sends him hunting a problem that is not there."""
        from portal import cockpit

        line = cockpit.arrival_notice_for(
            {"arrived_at": "2026-09-17T09:00:00", "card_data": {}, "numbers": {},
             "arrival_notice_refused": "Press START RUN first."},
            cockpit.MODE_PICKUP)["delivery"]

        assert line["sent"] is False
        assert "couldn't send" not in line["line"]
        assert "START RUN" in line["instead"]
