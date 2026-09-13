"""A message that did not reach anyone says so, somewhere a person will look.

`_notify_safe()` caught every exception from every notification send -- twelve
call sites -- and wrote one line to stderr. The reasoning was right as far as it
went: the load *was* invoiced, and an SMTP failure should not turn a committed
write into a 500. The second half was missing. There was no database row, no
screen indicator, no counter and no retry, so a broker notification that failed
authentication left Mike looking at a successful Submit and a broker who never
heard from him.

The truth vocabulary already had the word for it. Nothing was in a position to
display it, because nothing recorded it.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytest

from dispatch import delivery, services
from dispatch.db import set_db_path

NOW = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def database(tmp_path):
    set_db_path(tmp_path / "dispatch.db")
    try:
        yield
    finally:
        set_db_path(None)


def _boom(message="535 5.7.139 Authentication unsuccessful"):
    def send():
        raise RuntimeError(message)

    return send


class TestTheRecordItself:
    def test_a_failed_send_leaves_a_row_naming_the_reason(self, database):
        result = delivery.send_with_record(
            "broker_email", _boom(), subject_ref="LOAD-1", recipient="ops@broker.test"
        )
        assert result["ok"] is False

        row = delivery.get(result["attempt_id"])
        assert row["status"] == delivery.FAILED
        assert "535" in row["last_error"]
        assert row["subject_ref"] == "LOAD-1"
        assert row["recipient"] == "ops@broker.test"

    def test_the_row_exists_before_the_send_is_attempted(self, database):
        """A process killed mid-send must leave something the next sweep can see."""
        seen = {}

        def send():
            seen["rows"] = delivery.list_attempts()
            return "sent via smtp.example.com"

        delivery.send_with_record("broker_email", send, subject_ref="LOAD-1")
        assert len(seen["rows"]) == 1
        assert seen["rows"][0]["status"] == delivery.QUEUED

    def test_a_successful_send_records_the_receipt(self, database):
        result = delivery.send_with_record(
            "broker_email", lambda: "sent via smtp.office365.com", subject_ref="LOAD-1"
        )
        assert delivery.get(result["attempt_id"])["status"] == delivery.SENT
        assert "smtp.office365.com" in delivery.get(result["attempt_id"])["receipt"]

    def test_a_local_outbox_write_is_not_recorded_as_sent(self, database):
        """"Written to Archive/Outbox" and "a mail server accepted it" are
        different facts, and only one means the broker heard from Mike."""
        result = delivery.send_with_record(
            "broker_email",
            lambda: "not sent (SMTP not configured); written to /Archive/Outbox/x.eml",
            subject_ref="LOAD-1",
        )
        assert result["status"] == delivery.SIMULATED
        assert delivery.get(result["attempt_id"])["status"] == delivery.SIMULATED

    def test_the_exception_is_still_swallowed(self, database):
        """The committed write must not fail because the email did."""
        delivery.send_with_record("broker_email", _boom(), subject_ref="LOAD-1")  # no raise


class TestRetry:
    def test_backoff_lengthens_and_then_gives_up(self, database):
        result = delivery.send_with_record("broker_email", _boom(), subject_ref="L", now=NOW)
        attempt_id = result["attempt_id"]

        expected = [1, 5, 15, 60]
        assert delivery.get(attempt_id)["next_retry_at"] == "2026-03-01T12:01:00Z"
        for index, minutes in enumerate(expected[1:], start=1):
            outcome = delivery.mark_failed(attempt_id, "still failing", now=NOW)
            assert outcome["status"] == delivery.FAILED
            assert outcome["next_retry_at"] == (NOW + timedelta(minutes=minutes)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

        final = delivery.mark_failed(attempt_id, "still failing", now=NOW)
        assert final["status"] == delivery.ABANDONED
        assert final["next_retry_at"] is None

    def test_nothing_is_due_before_its_time(self, database):
        delivery.send_with_record("broker_email", _boom(), subject_ref="L", now=NOW)
        assert delivery.retry_due(now=NOW) == []
        assert len(delivery.retry_due(now=NOW + timedelta(minutes=2))) == 1

    def test_an_abandoned_attempt_is_never_due_again(self, database):
        result = delivery.send_with_record("broker_email", _boom(), subject_ref="L", now=NOW)
        for _ in range(delivery.MAX_ATTEMPTS):
            delivery.mark_failed(result["attempt_id"], "no", now=NOW)
        assert delivery.retry_due(now=NOW + timedelta(days=30)) == []

    def test_a_success_clears_the_retry(self, database):
        result = delivery.send_with_record("broker_email", _boom(), subject_ref="L", now=NOW)
        delivery.mark_sent(result["attempt_id"], receipt="sent via relay", now=NOW)
        row = delivery.get(result["attempt_id"])
        assert row["status"] == delivery.SENT
        assert row["next_retry_at"] is None
        assert row["last_error"] == ""


class TestTheRetrySweep:
    def test_it_resends_what_is_due_and_records_the_outcome(self, database, monkeypatch):
        from dispatch import notifications, notifications_retry

        load = services.create_load(customer="Acme")
        result = delivery.send_with_record(
            "load_stalled", _boom(), subject_ref=load["load_id"], now=NOW
        )
        monkeypatch.setattr(notifications, "notify_stalled", lambda ld: "sent via relay")

        outcome = notifications_retry.run_due(now=NOW)
        assert outcome["attempted"] == 0, "the first retry is not due for a minute"

        outcome = notifications_retry.run_due(now=NOW + timedelta(minutes=2))
        assert outcome["sent"] == 1
        assert delivery.get(result["attempt_id"])["status"] == delivery.SENT

    def test_an_attempt_whose_load_is_gone_is_abandoned_not_guessed(self, database):
        from dispatch import notifications_retry

        delivery.send_with_record(
            "load_stalled", _boom(), subject_ref="LOAD-DELETED", now=NOW
        )
        outcome = notifications_retry.run_due(now=NOW + timedelta(minutes=2))
        assert outcome["abandoned"] == 1
        assert "cannot be rebuilt" in delivery.open_failures()[0]["last_error"]

    def test_nothing_resends_on_a_timer(self, database, monkeypatch):
        """No thread, no scheduler inside the portal process."""
        import threading

        started = []
        monkeypatch.setattr(threading.Thread, "start", lambda self: started.append(self))
        delivery.send_with_record("broker_email", _boom(), subject_ref="L")
        assert started == []


class TestThroughAServiceOperation:
    def test_a_failing_delivery_notification_is_recorded_not_printed(self, database, monkeypatch):
        from dispatch import notifications

        load = services.create_load(customer="Acme")
        load_id = load["load_id"]
        for event_type in ("dispatched", "en_route_pickup", "arrived_pickup", "loaded",
                           "departed_pickup", "in_transit", "arrived_delivery"):
            services.add_milestone(load_id, event_type)

        monkeypatch.setattr(notifications, "notify_delivered", lambda *a, **k: _boom()())
        services.add_milestone(load_id, "delivered")

        failures = delivery.open_failures()
        assert len(failures) == 1
        assert failures[0]["kind"] == "load_delivered"
        assert failures[0]["subject_ref"] == load_id
        # The write itself still committed. That was always the point.
        assert services.get_load(load_id)["status"] == "delivered"

    def test_the_summary_counts_what_needs_attention(self, database):
        delivery.send_with_record("broker_email", _boom(), subject_ref="A")
        delivery.send_with_record("broker_email", lambda: "sent via relay", subject_ref="B")
        summary = delivery.summary()
        assert summary["counts"][delivery.FAILED] == 1
        assert summary["counts"][delivery.SENT] == 1
        assert summary["needs_attention"] == 1


class TestTheScreens:
    @pytest.fixture
    def client(self, database, monkeypatch, tmp_path):
        monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "PortalData"))
        from portal.app import create_app

        app = create_app({"TESTING": True})
        app.config["LOGIN_DISABLED"] = True
        return app.test_client()

    def test_home_shows_the_count(self, client, database):
        delivery.send_with_record("broker_email", _boom(), subject_ref="LOAD-1")
        body = client.get("/home").get_data(as_text=True)
        assert "have not reached anyone" in body

    def test_home_says_nothing_when_there_is_nothing_to_say(self, client, database):
        body = client.get("/home").get_data(as_text=True)
        assert "have not reached anyone" not in body

    def test_maintenance_lists_them_with_the_reason(self, client, database):
        delivery.send_with_record(
            "broker_email", _boom(), subject_ref="LOAD-1", recipient="ops@broker.test"
        )
        body = client.get("/maintenance").get_data(as_text=True)
        assert "535" in body
        assert "LOAD-1" in body


class TestLogging:
    def test_a_failure_is_logged_with_structured_fields(self, database, caplog):
        from dispatch.observability import configure

        # configure() owns its logger's handlers, so a captor has to be attached
        # after it rather than before -- which is also how a host application
        # would do it.
        logger = configure(force=True)
        captured: list[logging.LogRecord] = []

        class Captor(logging.Handler):
            def emit(self, record):
                captured.append(record)

        logger.addHandler(Captor())
        delivery.send_with_record("broker_email", _boom(), subject_ref="LOAD-1")

        record = next(r for r in captured if r.name == "dispatch.delivery")
        assert record.fields["status"] == delivery.FAILED
        assert "535" in record.fields["error"]
        assert record.fields["attempt"].startswith("DLV-")

    def test_the_log_file_is_bounded(self, tmp_path, monkeypatch):
        """An unbounded log on the disk the database lives on is a way to lose both."""
        import logging.handlers

        from dispatch import observability

        monkeypatch.setenv("DISPATCH_LOG_DIR", str(tmp_path / "logs"))
        logger = observability.configure(force=True)
        rotating = [h for h in logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]
        assert rotating, "no rotating handler; the log would grow without limit"
        assert rotating[0].maxBytes > 0
        assert rotating[0].backupCount > 0

    def test_stderr_still_carries_everything(self, tmp_path, monkeypatch):
        """The launcher captures stderr into server.log; that must keep working."""
        from dispatch import observability

        monkeypatch.setenv("DISPATCH_LOG_DIR", str(tmp_path / "logs"))
        logger = observability.configure(force=True)
        assert any(type(h) is logging.StreamHandler for h in logger.handlers)

    def test_an_unwritable_log_directory_does_not_stop_dispatch(self, tmp_path, monkeypatch):
        from dispatch import observability

        blocker = tmp_path / "not-a-dir"
        blocker.write_text("", encoding="utf-8")
        monkeypatch.setenv("DISPATCH_LOG_DIR", str(blocker))
        logger = observability.configure(force=True)  # must not raise
        assert logger.handlers


class TestTheTransportAndTheRecordAgreeOnWords:
    """Split out of tests/test_transport.py, which cannot import this module.

    The transport reports a status and writes a receipt; the delivery record
    classifies the attempt from them. If the two ever spell SIMULATED
    differently, a message that was only written to disk starts reading as one
    that was actually sent, and nothing anywhere says otherwise.
    """

    def test_simulated_is_the_same_word_on_both_sides(self):
        from dispatch.transport.contract import SIMULATED as transport_simulated

        assert delivery.SIMULATED == transport_simulated

    def test_the_outbox_receipt_is_what_the_record_classifies_by(self, tmp_path):
        from dispatch.transport.adapters import FileOutboxTransport
        from dispatch.transport.contract import OutboundMessage

        result = FileOutboxTransport(tmp_path / "Outbox").send(
            OutboundMessage(
                to=("ops@broker.test",),
                subject="Rate confirmation",
                body_text="body",
            )
        )
        assert result.status == delivery.SIMULATED
        assert result.receipt.startswith("not sent")
        assert result.delivered is False
