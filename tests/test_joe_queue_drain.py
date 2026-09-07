"""Draining JOE's queue into the seventh contract.

The mission: *consume queued requests from JOE-Assistant and write them through
the seventh contract.* Six requirements, and the ones that matter here are the
last two — handle reconnect, and return honest failure reports.

**Dispatch does not import Joe-Assistant.** They are separate repositories and
the dependency would run the wrong way, so the drain is duck-typed on
`pending()` and these fakes stand in for JOE exactly as a real port would.
"""

from __future__ import annotations

import pytest

from adapters.dispatch_session import (ACTS_ON, DispatchError, DrainReport,
                                       NodeNotAccepting, drain)


class FakeRequest:
    """The shape `dispatch_port.ActionRequest` presents: a kind and a detail."""

    def __init__(self, kind: str, detail: str = ""):
        self.kind = kind
        self.detail = detail
        # JOE's own flags. The drain must not touch them -- accepting is a
        # decision and the queue is JOE's to own.
        self.accepted = False
        self.performed = False


class FakePort:
    def __init__(self, *requests):
        self._requests = list(requests)

    def pending(self):
        return list(self._requests)


class FakeResult:
    def __init__(self, ok=True, data=None, note=""):
        self.ok = ok
        self.note = note
        self.data = data or {}

    def get(self, key, default=None):
        return self.data.get(key, default)


class FakeSession:
    def __init__(self, *, raises=None, ok=True):
        self.raises = raises
        self.ok = ok
        self.calls = []

    def capture_opportunity(self, **fields):
        self.calls.append(fields)
        if self.raises:
            raise self.raises
        if not self.ok:
            return FakeResult(ok=False, note="board, lane or rate missing")
        return FakeResult(data={"opportunity_id": "OPP-TEST01",
                                "echo": "LOGGED. OPPORTUNITY OPP-TEST01."})


CAPTURE = "log this one DAT. Jacksonville to Tampa. $750. pickup Thursday"


class TestItWritesOnlyWhatIsClassOne:
    def test_a_capture_is_written(self):
        session = FakeSession()
        report = drain(FakePort(FakeRequest(ACTS_ON, CAPTURE)), session)
        assert len(report.captured) == 1
        assert session.calls[0]["source_board"] == "DAT"
        assert session.calls[0]["rate"] == 750.0

    @pytest.mark.parametrize("kind", ["finding", "recommendation", "draft",
                                      "explanation", "question", "proposed_change"])
    def test_every_other_kind_is_left_for_mike(self, kind):
        """`dispatch_port.py`: *JOE never writes to Dispatch. It submits a
        request that Dispatch or Mike accepts or rejects.* **Accepting is a
        decision**, and Opportunity Capture is the only queued thing that is not
        one — OPP-CAPTURE section 1 rules it Class 1."""
        session = FakeSession()
        report = drain(FakePort(FakeRequest(kind, CAPTURE)), session)
        assert report.captured == []
        assert session.calls == [], "a proposal was executed as though it were an action"
        assert len(report.left_queued) == 1

    def test_a_request_that_is_not_a_capture_is_left_queued(self):
        """Board and lane are the load's identity. Without them there is nothing
        to log and nothing to deduplicate against, and inventing either would be
        worse than leaving it queued."""
        session = FakeSession()
        report = drain(FakePort(FakeRequest(ACTS_ON, "remind me about the Penske run")),
                       session)
        assert report.captured == []
        assert "missing" in report.left_queued[0][1]

    def test_a_missing_rate_does_not_block_a_capture(self):
        """Sparse capture is valid capture. The rate is the one thing worth a
        question, and questions are asked of Mike, not of the queue."""
        session = FakeSession()
        report = drain(FakePort(FakeRequest(ACTS_ON, "log this one DAT. Ocala to Tampa")),
                       session)
        assert len(report.captured) == 1

    def test_the_queue_is_never_mutated(self):
        """JOE's queue is JOE's. A consumer that emptied it would be reaching
        across a boundary drawn on purpose."""
        request = FakeRequest(ACTS_ON, CAPTURE)
        port = FakePort(request)
        drain(port, FakeSession())
        assert len(port.pending()) == 1
        assert request.accepted is False and request.performed is False


class TestFailureIsReportedHonestly:
    def test_a_closed_node_stops_the_drain_and_says_so(self):
        """Fail-closed is the node working, not a fault to route around."""
        session = FakeSession(raises=NodeNotAccepting("node not accepting", status=503))
        report = drain(FakePort(FakeRequest(ACTS_ON, CAPTURE),
                                FakeRequest(ACTS_ON, CAPTURE)), session)
        assert report.unreachable is True
        assert report.ok is False
        assert len(session.calls) == 1, "it kept trying after the node said no"

    def test_an_unreachable_node_leaves_the_queue_alone(self):
        session = FakeSession(raises=DispatchError("the node did not answer"))
        report = drain(FakePort(FakeRequest(ACTS_ON, CAPTURE)), session)
        assert report.unreachable is True
        assert report.captured == []
        assert "UNREACHABLE" in " ".join(report.lines())
        assert "THE QUEUE IS UNCHANGED" in " ".join(report.lines())

    def test_a_refusal_is_reported_not_swallowed(self):
        session = FakeSession(ok=False)
        report = drain(FakePort(FakeRequest(ACTS_ON, CAPTURE)), session)
        assert report.captured == []
        assert report.failed and "missing" in report.failed[0][1]

    def test_a_queue_that_cannot_be_read_is_a_reported_failure(self):
        class Broken:
            def pending(self):
                raise RuntimeError("port is not connected")

        report = drain(Broken(), FakeSession())
        assert report.ok is False
        assert "could not be read" in report.failed[0][1]

    def test_one_bad_request_does_not_lose_the_others(self):
        session = FakeSession()
        report = drain(FakePort(FakeRequest("finding", "something"),
                                FakeRequest(ACTS_ON, CAPTURE),
                                FakeRequest(ACTS_ON, "nonsense")), session)
        assert len(report.captured) == 1
        assert len(report.left_queued) == 2

    def test_the_report_speaks_in_the_locked_voice(self):
        report = drain(FakePort(FakeRequest("finding", "x"),
                                FakeRequest(ACTS_ON, CAPTURE)), FakeSession())
        lines = report.lines()
        assert any(l.startswith("LOGGED.") for l in lines)
        assert any(l.startswith("LEFT QUEUED.") for l in lines)


class TestReconnect:
    def test_reset_clears_both_halves_together(self):
        """Cookies bind a CSRF token to a session. Clearing one and keeping the
        other produces a client that looks connected and cannot write."""
        from adapters.dispatch_session import DispatchSession

        s = DispatchSession(token="t", driver="mike")
        s._csrf = "stale"
        s.reset()
        assert s._csrf == ""
        assert len(list(s._jar)) == 0

    def test_reconnect_reports_failure_rather_than_raising(self):
        """A caller draining a queue needs to decide what to do with the queue,
        not catch an exception."""
        from adapters.dispatch_session import DispatchSession

        s = DispatchSession(base_url="http://127.0.0.1:1", token="t", driver="mike",
                            timeout=0.4)
        assert s.reconnect() is False
