"""Load-board alert emails become cards. Read-only, allowlisted, never a guess.

Owner direction, 2026-09-15: *"i like this very much"* ... *"if we can create a
small email sort to push the incoming emails from specific senders to a box then
the reader can do it's thing."*

EVERY ALERT IN THIS FILE IS AN INVENTED EXAMPLE. No real board alert had been
seen when this was written; the senders use the reserved `.example` domain and
the loads, numbers and references are made up. When Mike forwards real alerts,
they become fixtures beside these, labelled as his.

No test here talks to a mailbox. The alert mailbox is a fake that fails the test
if anything tries to change a message, and the real adapter's
`_outlook_is_running` guard is patched to False so no COM call can happen.

THE TEST REALITY RULE: the check is reached the way the screen reaches it --
the CHECK ALERTS NOW button's POST -- as well as directly.
"""

from __future__ import annotations

import json
import pathlib
from datetime import timedelta

import pytest

from dispatch import alert_reader, clock, opportunity
from dispatch.connectors import alert_mailbox
from dispatch.connectors.alert_mailbox import AlertMailboxPort, answer
from dispatch.db import set_db_path
from portal.models import load_alerts, opportunity_card, sandbox

BOARD_ONE = "alerts@loadboard-one.example"      # invented
BOARD_TWO = "notify@mail.board-two.example"     # invented
BOARD_THREE = "loads@board-three.example"       # invented


def _day(offset: int) -> str:
    return (clock.home_date() + timedelta(days=offset)).isoformat()


def multi_load_alert() -> str:
    """INVENTED EXAMPLE: three loads, separated by rule lines, with a footer."""
    return f"""Your saved search "FL Dry Van" has 3 new matches

Jacksonville, FL -> Atlanta, GA
Pickup: {_day(1)} 08:00
Dry Van  42,000 lbs  345 mi
Rate: $1,250
Ref: LB1-1001
------------------------------
Tampa, FL -> Charlotte, NC
Pickup: {_day(1)} 10:00
Reefer  38,000 lbs  580 mi
Rate: $1,900
Ref: LB1-1002
------------------------------
Orlando, FL -> Savannah, GA
Pickup: {_day(2)}
Dry Van  300 mi
Rate: $1,050
Ref: LB1-1003

Unsubscribe from these alerts: https://loadboard-one.example/unsub
"""


def lane_line_alert() -> str:
    """INVENTED EXAMPLE: one load per line, no separators."""
    return (f"New loads matching your alert:\n"
            f"Savannah, GA to Charlotte, NC  {_day(1)}  $980  Reefer\n"
            f"Macon, GA to Tampa, FL  {_day(1)}  $1,150  Dry Van\n")


UNREADABLE_ALERT = "Loads available near Jacksonville! Log in to see the details."  # invented
CANNOT_SPLIT_ALERT = ("Two loads for you: Ocala FL to Macon GA $900 and "
                      "Lakeland FL to Albany GA $1,100")  # invented


def message(mid: str, sender: str, body: str, subject: str = "New load matches",
            received: str = "2026-09-15 07:30:00") -> dict:
    return {"message_id": mid, "sender": sender, "subject": subject,
            "received_at": received, "body": body}


class FakeAlertMailbox(AlertMailboxPort):
    """TEST DOUBLE. Answers with invented messages. Any write fails the test."""

    name = "fake_alert_mailbox"

    def __init__(self, messages=(), status="LIVE", reason=""):
        self.messages = list(messages)
        self.status = status
        self.reason = reason
        self.calls = []

    def read_since(self, *, mailbox, folder, since=None, limit=200, known=()):
        self.calls.append({"mailbox": mailbox, "folder": folder, "since": since})
        return answer(self.status, mailbox=mailbox, folder=folder, reason=self.reason,
                      messages=[dict(m) for m in self.messages] if self.status in (
                          "LIVE", "SIMULATED") else [])

    def _refuse(self, *args, **kwargs):
        pytest.fail("The alert mailbox was asked to change a message. It is read-only.")

    send = reply = reply_all = forward = move = copy = delete = save = _refuse
    flag = mark_read = mark_unread = set_category = create_folder = create_rule = _refuse


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    set_db_path(tmp_path / "dispatch.db")
    from dispatch import scheduling
    from dispatch.connectors import outlook_alert_mailbox, outlook_mail

    for module in (scheduling, outlook_mail, outlook_alert_mailbox):
        monkeypatch.setattr(module, "_outlook_is_running", lambda: False)
    # A test that forgets to supply a fake gets a failure, never the real mailbox.
    monkeypatch.setattr(load_alerts, "_adapter",
                        lambda: pytest.fail("no fake alert mailbox was supplied"))
    yield
    set_db_path(None)


@pytest.fixture
def client():
    from portal.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _configure(senders=(BOARD_ONE, "board-two.example"), **over):
    form = {"mailbox": "Ops@l1truck.com", "folder": "Load Alerts",
            "senders": "\n".join(senders), "check_every_minutes": "0", "profiles": ""}
    form.update(over)
    saved = load_alerts.save_settings(form)
    assert saved["ok"], saved["problems"]
    return saved["settings"]


def _use(monkeypatch, fake):
    monkeypatch.setattr(load_alerts, "_adapter", lambda: fake)
    return fake


def _cards():
    return {sid: e for sid, e in sandbox.get_all().items() if e["source_type"] == "dispatch"}


# ------------------------------------------------------------------ the reader

class TestSenders:
    def test_addresses_and_domains(self):
        allowed = alert_reader.normalise_senders([BOARD_ONE, "@board-two.example", "junk here"])
        assert allowed == [BOARD_ONE, "@board-two.example"]
        assert alert_reader.sender_allowed("Board One <ALERTS@loadboard-one.example>", allowed)
        assert alert_reader.sender_allowed(BOARD_TWO, allowed)          # subdomain
        assert not alert_reader.sender_allowed("other@loadboard-one.example", allowed)
        assert not alert_reader.sender_allowed("x@board-two.example.evil.example", allowed)
        assert not alert_reader.sender_allowed("", allowed)

    def test_a_stranger_is_ignored_and_never_read(self):
        read = alert_reader.read_alert(message("1", "someone@unknown.example",
                                               multi_load_alert()), allowed=[BOARD_ONE])
        assert read["allowed"] is False
        assert read["loads"] == [] and read["needs_look"] == []


class TestSplitting:
    def test_separator_lines_split_three_loads(self):
        read = alert_reader.read_alert(message("1", BOARD_ONE, multi_load_alert()),
                                       allowed=[BOARD_ONE])
        assert read["how"] == "separator lines"
        lanes = [(l["fields"]["origin"], l["fields"]["destination"]) for l in read["loads"]]
        assert lanes == [("Jacksonville, FL", "Atlanta, GA"), ("Tampa, FL", "Charlotte, NC"),
                         ("Orlando, FL", "Savannah, GA")]
        assert [l["fields"]["rate"] for l in read["loads"]] == [1250.0, 1900.0, 1050.0]
        assert read["loads"][1]["card_extras"]["load_id"] == "LB1-1002"
        assert read["needs_look"] == []

    def test_one_load_per_lane_line(self):
        read = alert_reader.read_alert(message("1", BOARD_TWO, lane_line_alert()),
                                       allowed=["board-two.example"])
        assert read["how"] == "one load per lane line"
        assert [l["fields"]["rate"] for l in read["loads"]] == [980.0, 1150.0]

    def test_several_rates_it_cannot_separate_are_not_cut_by_guesswork(self):
        read = alert_reader.read_alert(message("1", BOARD_ONE, CANNOT_SPLIT_ALERT),
                                       allowed=[BOARD_ONE])
        assert read["loads"] == []
        assert "could not be told apart" in read["needs_look"][0]["reason"]

    def test_nothing_readable_is_a_needs_a_look(self):
        read = alert_reader.read_alert(message("1", BOARD_ONE, UNREADABLE_ALERT),
                                       allowed=[BOARD_ONE])
        assert read["loads"] == []
        assert read["needs_look"][0]["reason"] == "No load could be read in it."

    def test_a_load_without_a_rate_is_a_needs_a_look(self):
        read = alert_reader.read_alert(
            message("1", BOARD_ONE, f"Ocala, FL -> Macon, GA\nPickup: {_day(1)}"),
            allowed=[BOARD_ONE])
        assert read["loads"] == []
        assert read["needs_look"][0]["reason"] == "Missing rate."
        assert read["needs_look"][0]["fields"]["origin"] == "Ocala, FL"

    def test_links_are_removed_and_the_footer_dropped(self):
        cleaned = alert_reader.clean("Rate: $900\nSee https://board.example/load/1 now\n"
                                     "Manage your alerts here\nOcala, FL")
        assert "http" not in cleaned
        assert "Ocala" not in cleaned

    def test_a_board_profile_translates_its_own_labels(self):
        body = f"Orig: Valdosta, GA\nDest: Tifton, GA\nAmt: 700\nAvail: {_day(1)}"
        plain = alert_reader.read_alert(message("1", BOARD_THREE, body), allowed=[BOARD_THREE])
        assert plain["loads"] == []  # no dollar sign and no known label: never guessed
        profiles = {"board-three.example": {"name": "Board Three", "labels": {
            "Orig": "origin", "Dest": "destination", "Amt": "rate", "Avail": "pickup_date"}}}
        tuned = alert_reader.read_alert(message("1", BOARD_THREE, body), allowed=[BOARD_THREE],
                                        profiles=profiles)
        assert tuned["board"] == "Board Three"
        assert tuned["loads"][0]["fields"]["rate"] == 700.0
        assert tuned["loads"][0]["fields"]["pickup_date"] == _day(1)

    def test_a_board_split_pattern(self):
        body = (f"Load 1: Valdosta, GA\nTifton, GA\n$700\n"
                f"Load 2: Albany, GA\nDothan, AL\n$650\n")
        profiles = {"board-three.example": {"split": r"^Load \d+:"}}
        read = alert_reader.read_alert(message("1", BOARD_THREE, body), allowed=[BOARD_THREE],
                                       profiles=profiles)
        assert read["how"] == "board split pattern"
        assert [l["fields"]["destination"] for l in read["loads"]] == ["Tifton, GA", "Dothan, AL"]

    def test_bad_profiles_are_named(self):
        problems = alert_reader.check_profiles(
            {"x.example": {"split": "(", "labels": {"Pay": "money"}, "colour": "red"}})
        assert len(problems) == 3

    def test_a_forwarded_alert_is_read_as_the_board_that_wrote_it(self):
        body = ("Test forward.\n\n---------- Forwarded message ---------\n"
                f"From: Board One <{BOARD_ONE}>\nDate: Mon, Sep 14, 2026\n"
                "Subject: New matches\nTo: mike.test@example.com\n\n" + lane_line_alert())
        fwd = message("1", "mike.test@example.com", body, subject="Fwd: New matches")
        read = alert_reader.read_alert(fwd, allowed=["mike.test@example.com", BOARD_ONE])
        assert read["original_sender"] == BOARD_ONE
        assert len(read["loads"]) == 2
        # His own address on the list does not make a forward from anyone else a load.
        stranger = fwd | {"body": body.replace(BOARD_ONE, "who@unknown.example")}
        assert alert_reader.read_alert(stranger, allowed=["mike.test@example.com",
                                                          BOARD_ONE])["allowed"] is False

    def test_html_is_stripped_to_lines(self):
        text = alert_mailbox.strip_html(
            "<html><style>p{}</style><table><tr><td>Tampa, FL</td><td>Miami, FL</td>"
            "<td>$900</td></tr></table><p>Tap <a href='https://x.example'>here</a></p></html>")
        assert "Tampa, FL\tMiami, FL\t$900" in text
        assert "https" not in text and "p{}" not in text

    def test_the_reader_imports_nothing_that_reaches_a_network(self):
        for rel in ("dispatch/alert_reader.py", "dispatch/connectors/alert_mailbox.py"):
            source = pathlib.Path(rel).read_text(encoding="utf-8")
            for module in ("urllib", "requests", "socket", "http.client", "imaplib",
                           "poplib", "smtplib", "webbrowser"):
                assert "import %s" % module not in source, rel
                assert "from %s" % module not in source, rel


# ------------------------------------------------------------------ the check

class TestTheCheck:
    def test_alerts_become_cards_through_the_capture_contract(self, monkeypatch):
        _configure()
        _use(monkeypatch, FakeAlertMailbox([
            message("A1", BOARD_ONE, multi_load_alert()),
            message("A2", BOARD_TWO, lane_line_alert()),
            message("A3", "someone@unknown.example", multi_load_alert()),
            message("A4", BOARD_ONE, UNREADABLE_ALERT, subject="Log in to see loads"),
        ]))
        report = load_alerts.check_now()
        counts = report["counts"]
        assert report["status"] == "LIVE"
        assert counts["new_cards"] == 5
        assert counts["ignored_senders"] == 1
        assert counts["needs_look"] == 1
        assert counts["alerts_read"] == 3

        cards = _cards()
        assert len(cards) == 5
        entry = next(e for e in cards.values() if e["card_data"].get("load_id") == "LB1-1001")
        card = entry["card_data"]
        assert entry["data_origin"] == "LIVE"
        assert card["source"] == "email alert"
        assert card["alert_sender"] == BOARD_ONE
        assert card["alert_board"] == "loadboard-one.example"
        assert card["captured_via"] == "SWEEP"
        assert len(opportunity.all_open()) == 5

        look = load_alerts.strip()["needs_look"][0]
        assert look["subject"] == "Log in to see loads" and look["sender"] == BOARD_ONE

    def test_the_same_alert_is_never_carded_twice(self, monkeypatch):
        _configure()
        fake = _use(monkeypatch, FakeAlertMailbox([message("A1", BOARD_ONE, multi_load_alert())]))
        load_alerts.check_now()
        second = load_alerts.check_now()
        assert second["counts"]["already_seen"] == 1
        assert second["counts"]["new_cards"] == 0
        assert len(_cards()) == 3
        assert len(fake.calls) == 2

    def test_the_same_load_in_a_later_alert_merges_into_one_card(self, monkeypatch):
        _configure()
        fake = _use(monkeypatch, FakeAlertMailbox([message("A1", BOARD_ONE, multi_load_alert())]))
        load_alerts.check_now()
        fake.messages = [message("B7", BOARD_TWO, multi_load_alert(), received="2026-09-15 09:00:00")]
        report = load_alerts.check_now()
        assert report["counts"]["merged"] == 3
        assert report["counts"]["new_cards"] == 0
        assert len(_cards()) == 3

    def test_a_pickup_that_has_passed_is_not_carded(self, monkeypatch):
        _configure()
        body = f"Ocala, FL -> Macon, GA\nPickup: {_day(-2)} 08:00\nRate: $900"
        _use(monkeypatch, FakeAlertMailbox([message("A1", BOARD_ONE, body)]))
        report = load_alerts.check_now()
        assert report["counts"]["expired_skipped"] == 1
        assert _cards() == {} and opportunity.all_open() == []

    def test_a_committed_record_is_never_touched(self, monkeypatch, client):
        _configure()
        first = f"Ocala, FL -> Macon, GA\nPickup: {_day(1)} 08:00\nRate: $900"
        fake = _use(monkeypatch, FakeAlertMailbox([message("A1", BOARD_ONE, first)]))
        load_alerts.check_now()
        (sid, entry), = _cards().items()
        client.post(f"/brief/mission/{sid}/commit")
        committed = sandbox.get(sid)
        assert committed.get("committed_at")
        row_before = opportunity.get(entry["source_id"])

        fake.messages = [message("A2", BOARD_ONE, first + "\nContact: New Broker Co\n"
                                 "Commodity: Paper", received="2026-09-15 08:10:00")]
        report = load_alerts.check_now()
        assert report["counts"]["committed_untouched"] == 1
        assert sandbox.get(sid)["card_data"] == committed["card_data"]
        assert opportunity.get(entry["source_id"]) == row_before
        assert len(_cards()) == 1

    def test_a_simulated_read_makes_simulated_cards(self, monkeypatch):
        _configure()
        _use(monkeypatch, FakeAlertMailbox([message("A1", BOARD_TWO, lane_line_alert())],
                                           status="SIMULATED"))
        report = load_alerts.check_now()
        assert report["status"] == "SIMULATED"
        assert {e["data_origin"] for e in _cards().values()} == {"SIMULATED"}

    def test_one_check_at_a_time(self, monkeypatch):
        _configure()
        _use(monkeypatch, FakeAlertMailbox([]))
        assert load_alerts._CHECK_LOCK.acquire(blocking=False)
        try:
            assert load_alerts.check_now()["busy"] is True
        finally:
            load_alerts._CHECK_LOCK.release()

    def test_every_check_is_audited(self, monkeypatch):
        from dispatch import audit

        _configure()
        _use(monkeypatch, FakeAlertMailbox([message("A1", BOARD_TWO, lane_line_alert())]))
        load_alerts.check_now()
        entries = [e for e in audit.entries() if e["action"] == "load-alert-check"]
        assert entries and entries[-1]["channel"] == "EMAIL"
        assert "new cards 2" in entries[-1]["note"]


class TestStatusWords:
    def test_no_senders_is_unconfigured_and_the_mailbox_is_never_opened(self, monkeypatch):
        fake = _use(monkeypatch, FakeAlertMailbox([message("A1", BOARD_ONE, multi_load_alert())]))
        assert load_alerts.strip()["status"] == "UNCONFIGURED"
        report = load_alerts.check_now()
        assert report["status"] == "UNCONFIGURED"
        assert fake.calls == []
        assert _cards() == {}

    def test_set_up_but_not_checked_is_configured(self):
        _configure()
        assert load_alerts.strip()["status"] == "CONFIGURED"

    def test_an_unreachable_mailbox_is_unavailable_with_its_reason(self, monkeypatch):
        _configure()
        _use(monkeypatch, FakeAlertMailbox(status="UNAVAILABLE",
                                           reason="The folder is not there."))
        report = load_alerts.check_now()
        strip = load_alerts.strip()
        assert report["status"] == strip["status"] == "UNAVAILABLE"
        assert strip["reason"] == "The folder is not there."

    def test_live_only_after_a_read_succeeded(self, monkeypatch):
        _configure()
        _use(monkeypatch, FakeAlertMailbox([]))
        load_alerts.check_now()
        assert load_alerts.strip()["status"] == "LIVE"

    def test_the_real_adapter_with_the_mail_program_closed_is_unavailable(self):
        from dispatch.connectors.outlook_alert_mailbox import AlertFolderAdapter

        read = AlertFolderAdapter().read_since(mailbox="Ops@l1truck.com", folder="Load Alerts")
        assert read["status"] == "UNAVAILABLE"
        assert "not open" in read["reason"]
        assert read["messages"] == []

    def test_the_real_adapter_refuses_a_mailbox_that_is_not_approved(self):
        from dispatch.connectors.outlook_alert_mailbox import AlertFolderAdapter

        read = AlertFolderAdapter().read_since(mailbox="someone@else.example", folder="X")
        assert read["status"] == "UNCONFIGURED"

    def test_the_port_refuses_a_word_outside_the_eight(self):
        with pytest.raises(ValueError):
            answer("CONNECTED")


class TestReadOnly:
    #: Every call in the mail program's object model that changes a message or a folder.
    WRITES = (".Send(", ".Reply(", ".ReplyAll(", ".Forward(", ".Move(", ".Copy(",
              ".Delete(", ".Save(", ".SaveAs(", "UnRead", ".MarkAsTask(", "FlagRequest",
              "FlagStatus", ".Categories", ".Folders.Add(", ".Add(", "Rules", ".CreateItem(",
              ".ClearTaskFlag(", ".Close(", ".Display(")

    def test_the_adapter_calls_nothing_that_changes_the_mailbox(self):
        source = pathlib.Path("dispatch/connectors/outlook_alert_mailbox.py").read_text(
            encoding="utf-8")
        for call in self.WRITES:
            assert call not in source, call

    def test_the_check_asks_the_mailbox_only_to_read(self, monkeypatch):
        """The fake fails the test on any write; a full check runs clean."""
        _configure()
        _use(monkeypatch, FakeAlertMailbox([message("A1", BOARD_ONE, multi_load_alert()),
                                            message("A2", "x@unknown.example", "hello")]))
        load_alerts.check_now()


class TestSchedule:
    def test_off_by_default(self):
        assert load_alerts.settings()["check_every_minutes"] == 0

    def test_never_starts_under_tests(self):
        from portal.app import create_app, start_background_work

        app = create_app()
        app.config["TESTING"] = True
        assert load_alerts.start_background(app) is None
        start_background_work(app)
        assert load_alerts._worker is None or not load_alerts._worker.is_alive()


# ------------------------------------------------------------------ the screens

class TestTheScreens:
    def test_the_loads_screen_carries_the_strip(self, client):
        page = client.get("/loads").get_data(as_text=True)
        assert "LOAD ALERTS" in page
        assert "CHECK ALERTS NOW" in page
        assert "UNCONFIGURED" in page

    def test_check_alerts_now_cards_the_alerts(self, client, monkeypatch):
        _configure()
        _use(monkeypatch, FakeAlertMailbox([message("A1", BOARD_ONE, multi_load_alert()),
                                            message("A2", "x@unknown.example", "hello")]))
        resp = client.post("/loads/alerts/check")
        assert resp.status_code == 302
        page = client.get("/loads").get_data(as_text=True)
        assert "Load alerts LIVE: 3 new cards" in page
        assert "1 ignored sender" in page
        assert "LB1-1003" in page
        assert "email alert" in page
        assert len(_cards()) == 3

    def test_looking_at_the_loads_screen_never_checks(self, client, monkeypatch):
        _configure()
        fake = _use(monkeypatch, FakeAlertMailbox([message("A1", BOARD_ONE, multi_load_alert())]))
        client.get("/loads")
        client.get("/loads/alerts/settings")
        assert fake.calls == []

    def test_settings_save(self, client):
        page = client.get("/loads/alerts/settings").get_data(as_text=True)
        assert "LOAD ALERT SETTINGS" in page and "Load Alerts" in page
        resp = client.post("/loads/alerts/settings", data={
            "mailbox": "ops@l1truck.com", "folder": "Load Alerts",
            "senders": f"{BOARD_ONE}\nboard-two.example", "check_every_minutes": "15",
            "profiles": json.dumps({"board-two.example": {"name": "Board Two"}})})
        assert resp.status_code == 302
        current = load_alerts.settings()
        assert current["mailbox"] == "Ops@l1truck.com"
        assert current["senders"] == [BOARD_ONE, "board-two.example"]
        assert current["check_every_minutes"] == 15
        assert current["profiles"]["board-two.example"]["name"] == "Board Two"
        assert "Load alert settings saved." in client.get("/loads/alerts/settings").get_data(
            as_text=True)

    def test_a_mailbox_that_is_not_approved_is_refused_and_nothing_is_saved(self, client):
        resp = client.post("/loads/alerts/settings", data={
            "mailbox": "someone@else.example", "folder": "Load Alerts",
            "senders": BOARD_ONE, "check_every_minutes": "0", "profiles": ""})
        assert resp.status_code == 400
        assert "must be one of" in resp.get_data(as_text=True)
        assert load_alerts.settings()["senders"] == []

    def test_bad_board_hints_are_refused(self, client):
        resp = client.post("/loads/alerts/settings", data={
            "mailbox": "Ops@l1truck.com", "folder": "Load Alerts", "senders": BOARD_ONE,
            "check_every_minutes": "0", "profiles": "{not json"})
        assert resp.status_code == 400
        assert "do not read as JSON" in resp.get_data(as_text=True)

    def test_the_driver_cockpit_does_not_reach_alert_routes(self):
        from portal.routes.joe_portal import DRIVER_COCKPIT_ENDPOINTS

        assert not any("alert" in name for name in DRIVER_COCKPIT_ENDPOINTS)
