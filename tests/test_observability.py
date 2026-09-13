"""The structured log, tested where it first gets used.

`dispatch/observability.py` is the logging substrate `dispatch/outbound.py`
writes to. It is here rather than with the delivery records that also use it
because a module that production code imports has to arrive working, not
arrive and wait for the PR that tests it.

What matters about a log nobody reads until something has gone wrong: the
fields survive, the order is stable so two lines can be diffed, a value with a
space in it stays one field, and it rotates so it can never be the reason a
disk fills.
"""

from __future__ import annotations

import logging
import logging.handlers

import pytest

from dispatch import observability


@pytest.fixture(autouse=True)
def _fresh_logging(tmp_path, monkeypatch):
    monkeypatch.setenv("DISPATCH_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(observability, "_configured", False)
    yield
    root = logging.getLogger(observability.LOGGER_ROOT)
    for handler in list(root.handlers):
        handler.close()
        root.removeHandler(handler)
    monkeypatch.setattr(observability, "_configured", False)


def _format(message: str, **fields) -> str:
    record = logging.LogRecord(
        name="dispatch.test", level=logging.WARNING, pathname=__file__,
        lineno=1, msg=message, args=(), exc_info=None,
    )
    record.fields = fields
    return observability.KeyValueFormatter().format(record)


class TestTheLineYouReadAtSixInTheMorning:
    def test_the_fields_are_in_the_line(self):
        line = _format("send failed", kind="rate_confirmation", load_id="LOAD-1")
        assert "send failed" in line
        assert "kind=rate_confirmation" in line
        assert "load_id=LOAD-1" in line

    def test_field_order_is_stable_so_two_lines_can_be_compared(self):
        a = _format("x", zebra=1, alpha=2, middle=3)
        b = _format("x", middle=3, alpha=2, zebra=1)
        assert a == b, "field order depends on kwargs order; two identical events would diff"

    def test_a_value_with_a_space_stays_one_field(self):
        line = _format("x", detail="connection refused")
        assert 'detail="connection refused"' in line

    def test_the_level_and_the_logger_name_are_both_there(self):
        line = _format("x")
        assert "WARNING" in line and "dispatch.test" in line

    def test_the_timestamp_is_utc(self):
        assert _format("x").split(" ")[0].endswith("Z")


class TestGettingALogger:
    def test_a_bare_name_is_placed_under_the_dispatch_root(self):
        assert observability.get_logger("outbound").name == "dispatch.outbound"

    def test_an_already_qualified_name_is_left_alone(self):
        assert observability.get_logger("dispatch.outbound").name == "dispatch.outbound"

    def test_event_puts_its_kwargs_where_the_formatter_looks(self):
        # Not caplog: configure() takes the dispatch root off propagation, so
        # pytest's root-level capture never sees these records. That is
        # deliberate -- it keeps Dispatch's log out of whatever else is
        # listening -- so the test attaches its own handler, like a reader would.
        seen: list[logging.LogRecord] = []

        class Capture(logging.Handler):
            def emit(self, record):
                seen.append(record)

        log = observability.get_logger("dispatch.eventtest")
        handler = Capture()
        log.addHandler(handler)
        try:
            observability.event(log, logging.INFO, "installed", transport="file_outbox")
        finally:
            log.removeHandler(handler)

        assert seen, "the event never reached a handler"
        assert seen[-1].fields == {"transport": "file_outbox"}


class TestItCannotFillTheDisk:
    def test_the_handler_rotates(self):
        observability.configure(force=True)
        root = logging.getLogger(observability.LOGGER_ROOT)
        rotating = [h for h in root.handlers
                    if isinstance(h, logging.handlers.RotatingFileHandler)]
        assert rotating, "no rotating handler; the log grows without bound"
        assert rotating[0].maxBytes > 0
        assert rotating[0].backupCount > 0

    def test_it_writes_where_it_says_it_does(self, tmp_path):
        observability.configure(force=True)
        log = observability.get_logger("dispatch.writetest")
        observability.event(log, logging.WARNING, "hello", n=1)
        for handler in logging.getLogger(observability.LOGGER_ROOT).handlers:
            handler.flush()
        written = list((tmp_path / "logs").glob("*.log"))
        assert written, f"nothing in {tmp_path / 'logs'}"
        assert "hello" in written[0].read_text(encoding="utf-8")
