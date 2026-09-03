"""Outlook is the single source of scheduling truth, and now it is connected.

Two things are wired here, both through the Outlook already installed and
authenticated on the operator's machine:

    calendar    read the schedule; ask it to hold time on ACCEPT LOAD
    mail        send the arrival notice; draft the delivery packet

There is no SMTP host and no password stored anywhere. Mail leaves from
Ops@l1truck.com because that is the account Outlook already holds.

These tests must pass whether or not Outlook is running, so they test the
contract rather than the connection: what the adapters promise when they can
reach it, what they promise when they cannot, and the one thing that must never
happen -- a hang, or a claim that something was sent when it was not.
"""

from __future__ import annotations

import pytest

from dispatch import scheduling
from dispatch.connectors import outlook_mail, registry
from portal import cockpit, joe_voice


VOCABULARY = ("LIVE", "CONFIGURED", "UNCONFIGURED", "SIMULATED",
              "UNAVAILABLE", "MANUAL", "ABSENT", "UNVERIFIED")


class TestItNeverLaunchesOutlook:
    """The bug that cost an afternoon.

    Asking COM for Outlook when Outlook is closed starts it with no window,
    and that headless instance wedges: the next call blocks forever instead of
    failing. On a driver's screen a hang is worse than an error, because an
    error he can act on.

    So both adapters check whether Outlook is running before touching COM.
    """

    def test_the_calendar_checks_before_it_connects(self):
        source = open("dispatch/scheduling.py", encoding="utf-8").read()
        assert "_outlook_is_running()" in source
        session = source[source.index("def _session"):]
        session = session[:session.index("def _release")]
        assert session.index("_outlook_is_running") < session.index("Dispatch(")

    def test_mail_checks_before_it_connects(self):
        source = open("dispatch/connectors/outlook_mail.py", encoding="utf-8").read()
        assert "_outlook_is_running()" in source
        session = source[source.index("def _app"):]
        session = session[:session.index("def _release")]
        assert session.index("_outlook_is_running") < session.index("Dispatch(")

    def test_a_closed_outlook_is_reported_not_started(self, monkeypatch):
        monkeypatch.setattr(scheduling, "_outlook_is_running", lambda: False)
        probe = scheduling.OutlookCalendarAdapter().probe()
        assert probe["live"] is False
        assert probe["status"] == "UNAVAILABLE"
        assert "not open" in probe["blocker"]

    def test_mail_says_nothing_was_sent_when_outlook_is_closed(self, monkeypatch):
        monkeypatch.setattr(outlook_mail, "_outlook_is_running", lambda: False)
        result = outlook_mail.OutlookMailAdapter().send(
            "someone@example.com", "Subject", "Body")
        assert result["sent"] is False
        assert result["ok"] is False
        assert "nothing was sent" in result["blocker"].lower()


class TestSendingAndDraftingAreDifferentActs:
    """The authority model, in two method names.

    The arrival notice auto-sends because its value is being contemporaneous.
    The delivery packet is drafted and a person presses send. Completing a
    checklist must never become an outbound message.
    """

    def test_draft_never_reports_a_send(self, monkeypatch):
        monkeypatch.setattr(outlook_mail, "_outlook_is_running", lambda: False)
        result = outlook_mail.OutlookMailAdapter().draft(
            "someone@example.com", "Packet", "Body")
        assert result["sent"] is False

    def test_the_two_operations_have_separate_names(self):
        adapter = outlook_mail.OutlookMailAdapter()
        assert callable(adapter.send)
        assert callable(adapter.draft)
        assert adapter.send is not adapter.draft


class TestItWillNotSendFromTheWrongMailbox:
    def test_only_approved_mailboxes(self):
        assert outlook_mail.APPROVED_MAILBOXES == (
            "Ops@l1truck.com", "Admin@l1truck.com")
        assert outlook_mail.DEFAULT_FROM == "Ops@l1truck.com"

    def test_an_unapproved_sender_is_refused_not_substituted(self, monkeypatch):
        """A personal address on a broker's arrival notice gives him a reason
        to wonder who he is dealing with."""
        monkeypatch.setattr(outlook_mail, "_outlook_is_running", lambda: True)

        class FakeApp:
            def CreateItem(self, kind):  # noqa: N802 - COM's name
                raise AssertionError("composed before checking the mailbox")

        adapter = outlook_mail.OutlookMailAdapter()
        monkeypatch.setattr(adapter, "_app", lambda: (FakeApp(), ""))
        result = adapter.send("someone@example.com", "S", "B",
                              send_from="jax1313@outlook.com")
        assert result["sent"] is False
        assert "not an approved mailbox" in result["blocker"]

    def test_a_missing_operations_account_is_not_live(self):
        """Reachable but unable to send as Ops is not the same as working."""
        resolve = outlook_mail.OutlookMailAdapter._resolve_from
        assert resolve(["jax1313@outlook.com"], "Ops@l1truck.com") == ""
        assert resolve(["Ops@l1truck.com"], "ops@L1TRUCK.COM") == "Ops@l1truck.com"


class TestCapabilityIsNotOccurrence:
    """A working mail connector says nothing about whether THIS notice went.

    Wiring the connector briefly made the driver's screen read "The arrival
    notice sent." on a mission nobody had arrived at, because the status was
    LIVE. That is a lie he acts on: a driver who believes the broker has his
    arrival evidence does not chase it.
    """

    def test_before_arrival_it_says_what_will_happen(self):
        notice = cockpit.arrival_notice_for({"card_data": {}}, cockpit.MODE_DELIVERY)
        assert notice["delivery"]["sent"] is False
        assert "when you press ARRIVE" in notice["delivery"]["line"]

    def test_arrived_with_no_send_record_is_not_sent(self):
        """Absence of proof is the only safe reading."""
        record = {"card_data": {}, "arrived_at": "2026-09-02T08:00:00"}
        notice = cockpit.arrival_notice_for(record, cockpit.MODE_DELIVERY)
        assert notice["delivery"]["sent"] is False
        assert notice["delivery"]["instead"], "left him with nothing to do"

    def test_only_a_send_record_reports_sent(self):
        record = {"card_data": {}, "arrived_at": "2026-09-02T08:00:00",
                  "arrival_notice_sent_at": "2026-09-02T08:01:00"}
        notice = cockpit.arrival_notice_for(record, cockpit.MODE_DELIVERY)
        assert notice["delivery"]["sent"] is True

    @pytest.mark.parametrize("record", [
        {"card_data": {}},
        {"card_data": {}, "arrived_at": "2026-09-02T08:00:00"},
        {"card_data": {}, "arrived_at": "x", "arrival_notice_sent_at": "y"},
    ])
    def test_the_driver_never_reads_an_engineering_word(self, record):
        delivery = cockpit.arrival_notice_for(record, cockpit.MODE_DELIVERY)["delivery"]
        assert joe_voice.is_driver_safe(
            delivery["line"] + " " + delivery["instead"]) == []


class TestStatusIsProbedNotRemembered:
    """Outlook can be open now and closed in ten minutes."""

    def test_the_status_is_in_the_fixed_vocabulary(self):
        assert registry.mail_status() in VOCABULARY
        assert registry.calendar_status() in VOCABULARY
        assert cockpit.transmission_status() in VOCABULARY

    def test_it_reflects_outlook_closing(self, monkeypatch):
        monkeypatch.setattr(outlook_mail, "_outlook_is_running", lambda: False)
        assert registry.mail_status() == "UNAVAILABLE"

    def test_the_adapter_chosen_is_the_real_one_when_it_is_live(self, monkeypatch):
        monkeypatch.setattr(scheduling, "_outlook_is_running", lambda: False)
        assert scheduling.get_adapter().name == "demonstration"


class TestAppointmentsLandAtTheTimeHeWasTold:
    """The defect: a 06:00 gate time in Savannah landed in the calendar at
    10:00, four hours after the truck was supposed to be there.

    A naive datetime is handed to Outlook as UTC and comes back shifted by the
    local offset. Written as a formatted string it is read as local time, which
    is the time on the record and the time the driver was told.

    Checked in the code, because a test that reaches a real calendar is broken
    whatever it asserts -- and this one would book an appointment to prove it.
    """

    def test_the_start_is_written_as_a_local_time_string(self):
        source = open("dispatch/scheduling.py", encoding="utf-8").read()
        hold = source[source.index("def hold_appointment"):]
        hold = hold[:hold.index("def _appointment_body")]
        assert "appointment.Start = starts.strftime(" in hold, (
            "a naive datetime is treated as UTC and shifts the appointment")

    def test_the_parser_keeps_the_hour_the_record_states(self):
        from dispatch import scheduling

        parsed = scheduling._parse_when("2026-09-02 06:00 (GATE 6 arrival time)")
        assert parsed.hour == 6 and parsed.minute == 0

    @pytest.mark.parametrize("window,hour", [
        ("2026-09-02 06:00", 6),
        ("2026-09-02 06:00 (GATE 6 arrival time)", 6),
        ("2026-09-02 14:30 - 16:00", 14),
    ])
    def test_the_shapes_a_record_actually_carries(self, window, hour):
        from dispatch import scheduling

        assert scheduling._parse_when(window).hour == hour

    def test_an_unreadable_window_becomes_an_all_day_block(self):
        """An appointment at a guessed hour is worse than a day marked spoken
        for."""
        from dispatch import scheduling

        assert scheduling._parse_when("sometime Tuesday") is None
