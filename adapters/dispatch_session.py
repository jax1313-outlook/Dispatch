"""DispatchSession — the one way anything calls the Joe contract layer.

**THIS IS AN ADAPTER.** It is a client of the Dispatch HTTP API and nothing
more. Per `CODE_MISSION_MCP_SERVER.md`: *"the MCP server calls the Dispatch HTTP
API over localhost. It must not import Spine internals or touch the database
directly."* This module imports no Spine internals and opens no database. Every
doctrine control enforced at the API — authentication, authority classes,
fail-closed 503, audit logging — therefore stays in force underneath it.

WHY IT EXISTS
=============

Four of the seven contracts are mutating, and a machine client needs three
things at once to reach them: the bearer token, a CSRF token, and the session
cookie that CSRF token is bound to. Miss the third and every write returns 403,
which reads like an authentication failure and gets the bearer token blamed.

That is not a caller's problem to solve seven times. It is solved here, once.

**Standard library only.** `flask` is this program's single hard dependency and
that is worth keeping — Dispatch runs on a laptop in a Pelican case, and a
`pip install` on the roadside is not a plan. `urllib` and `http.cookiejar` do
everything needed.

WHAT IT WILL NOT DO
===================

- **It does not work around a 503.** An unset token means the node is not
  accepting Joe calls, and saying so is the correct behaviour, not an obstacle.
- **It does not retry a 401.** A wrong token is wrong; retrying is noise.
- **It never retries more than once**, and only for the one failure that is
  genuinely recoverable — an expired CSRF token on a mutating call.
- **It does not decide anything.** Class 2 read-back and Class 3 authority live
  at the API and in the man, not in a client library.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import urllib.error
import urllib.request

#: Where the node answers. Loopback by default, because that is what
#: `PORTAL_HOST` is and what CONOPS v1.1 describes: the node is the operational
#: centre of gravity and the tablet is a portal into it.
DEFAULT_BASE = "http://127.0.0.1:8080"

#: The header the CSRF gate reads, and the cookie it is issued on.
CSRF_HEADER = "X-CSRF-Token"
CSRF_COOKIE = "csrf_token"

#: A cheap read used only to obtain the cookies. It changes nothing.
CSRF_PRIMER = "/api/joe/schedule-fit"

MUTATING = {"POST", "PATCH", "PUT", "DELETE"}


class DispatchError(RuntimeError):
    """A call did not succeed, and carries what the node actually said."""

    def __init__(self, message: str, *, status: int = 0, note: str = ""):
        super().__init__(message)
        self.status = status
        self.note = note


class NodeNotAccepting(DispatchError):
    """503 — `DISPATCH_JOE_TOKEN` is unset on the node.

    **Not an error to work around.** The node is fail-closed by design: an
    unauthenticated write path into the Mission Record is worse than no API.
    """


class NotAuthorised(DispatchError):
    """401 — the token presented is not the token configured."""


class Result:
    """What a call returned, reported honestly.

    `ok` is the node's own verdict, not the transport's. A 400 that says *board,
    lane or rate missing* is a complete, successful conversation with a node
    that refused — and it is reported as `ok=False` with the reason, never as an
    exception, because a refusal is information the caller acts on.
    """

    __slots__ = ("status", "data", "ok", "note")

    def __init__(self, status: int, data: dict):
        self.status = status
        self.data = data if isinstance(data, dict) else {}
        self.ok = bool(self.data.get("ok", 200 <= status < 300))
        self.note = str(self.data.get("note", ""))

    def __repr__(self) -> str:
        return "Result(status=%d, ok=%s, note=%r)" % (self.status, self.ok, self.note)

    def __getitem__(self, key):
        return self.data[key]

    def get(self, key, default=None):
        return self.data.get(key, default)


class DispatchSession:
    """One session, one cookie jar, one place the three credentials meet.

    ```python
    joe = DispatchSession(driver="mike")
    joe.capture_opportunity(source_board="DAT", origin="Jacksonville",
                            destination="Tampa", rate=750)
    ```

    The CSRF token is acquired lazily — on the first mutating call, not at
    construction — so creating a session costs nothing and a read-only client
    never asks for one.
    """

    def __init__(self, base_url: str = DEFAULT_BASE, *, token: str | None = None,
                 driver: str = "", channel: str = "CHAT", timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        # Read from the environment by default. The token is never written to
        # disk by this program and never travels to the tablet (CONOPS R9).
        self.token = token if token is not None else os.environ.get("DISPATCH_JOE_TOKEN", "")
        self.driver = driver
        self.channel = channel
        self.timeout = timeout
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar))
        self._csrf = ""

    # ------------------------------------------------------------- plumbing

    def _cookie(self, name: str) -> str:
        for c in self._jar:
            if c.name == name:
                return c.value or ""
        return ""

    def acquire_csrf(self) -> str:
        """GET once, and keep both cookies.

        **Both.** The CSRF check is a double-submit: the header must match a
        value held in the session, so carrying the token without the session
        cookie fails exactly as if no token had been sent. The cookie jar is the
        point of this class.
        """
        self._raw("GET", CSRF_PRIMER)
        self._csrf = self._cookie(CSRF_COOKIE)
        if not self._csrf:
            raise DispatchError(
                "The node did not issue a CSRF token. Writes cannot proceed, and "
                "guessing one would fail closed anyway.")
        return self._csrf

    def _raw(self, method: str, path: str, body: dict | None = None) -> Result:
        url = self.base_url + path
        payload = json.dumps(body).encode("utf-8") if body is not None else None

        headers = {"X-Driver": self.driver, "X-Channel": self.channel}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if method in MUTATING and self._csrf:
            headers[CSRF_HEADER] = self._csrf

        request = urllib.request.Request(url, data=payload, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", "replace")
                status = response.status
        except urllib.error.HTTPError as failure:
            raw = failure.read().decode("utf-8", "replace")
            status = failure.code
        except urllib.error.URLError as unreachable:
            raise DispatchError(
                "The node did not answer at %s (%s). Dispatch may not be running."
                % (self.base_url, unreachable.reason)) from None

        try:
            data = json.loads(raw)
        except ValueError:
            data = {"ok": False, "note": raw[:200]}
        return Result(status, data)

    def reset(self) -> None:
        """Drop the session and start clean.

        Cookies bind a CSRF token to a session, so a node restart invalidates
        both together. Clearing one and keeping the other produces a client that
        looks connected and cannot write.
        """
        self._jar.clear()
        self._csrf = ""
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar))

    def reconnect(self) -> bool:
        """Re-establish the session after the node went away and came back.

        **CONOPS v1.1 treats connectivity as intermittent by design**, and the
        node itself restarts -- for a settings change, for a power cycle in the
        truck. Both end a session without warning, and the symptom is a 403 that
        looks exactly like a CSRF failure.

        Returns True when a session is live again. Returns False rather than
        raising, because a caller draining a queue needs to decide what to do
        with the queue, not catch an exception.
        """
        self.reset()
        try:
            self.acquire_csrf()
            return True
        except DispatchError:
            return False

    def request(self, method: str, path: str, body: dict | None = None) -> Result:
        """Every call goes through here, and so does every refusal.

        The one retry: a mutating call refused 403 has an expired or absent CSRF
        token, which is the single failure a client can honestly recover from.
        Acquire once, retry once, and never loop — a second 403 is a real
        refusal and is reported as one.
        """
        method = method.upper()
        if method in MUTATING and not self._csrf:
            self.acquire_csrf()

        try:
            result = self._raw(method, path, body)
        except DispatchError:
            # The node did not answer. It may have restarted between calls --
            # that is normal in a truck, not exceptional. One reconnect, one
            # retry, and then the truth.
            if not self.reconnect():
                raise
            result = self._raw(method, path, body)

        if result.status == 403 and method in MUTATING:
            # An expired session and an expired CSRF token look identical from
            # here, so recover both rather than guessing which it was.
            self.reconnect()
            result = self._raw(method, path, body)

        if result.status == 503:
            raise NodeNotAccepting(
                "This Dispatch node is not accepting Joe calls yet. "
                "DISPATCH_JOE_TOKEN is unset on the node.",
                status=503, note=result.note)
        if result.status == 401:
            raise NotAuthorised(
                "Not authorised. The token presented is not the token the node "
                "is configured with.", status=401, note=result.note)
        return result

    def get(self, path: str, **params) -> Result:
        if params:
            from urllib.parse import urlencode

            path = "%s?%s" % (path, urlencode({k: v for k, v in params.items()
                                               if v not in (None, "")}))
        return self.request("GET", path)

    def post(self, path: str, **body) -> Result:
        return self.request("POST", path, body)

    def patch(self, path: str, **body) -> Result:
        return self.request("PATCH", path, body)

    # -------------------------------------------------- the seven contracts

    def mission_status(self, mission: str = "") -> Result:
        """Class 1. What the truck is doing."""
        return self.get("/api/joe/mission-status", mission=mission)

    def facility_intel(self, facility_id: str) -> Result:
        """Class 1. What is known about a facility, and only what is known."""
        from urllib.parse import quote

        return self.get("/api/joe/facility-intel/" + quote(str(facility_id)))

    def schedule_fit(self, **params) -> Result:
        """Class 1. Reports the board and decides nothing."""
        return self.get("/api/joe/schedule-fit", **params)

    def driver_status(self, status: str, *, mission: str = "", note: str = "") -> Result:
        """Class 1. The locked vocabulary — ON TIME, DELAYED, AT RISK. A word
        outside it is refused by the node rather than stored."""
        return self.post("/api/joe/driver-status", status=status,
                         mission=mission, note=note)

    def capture_opportunity(self, *, source_board: str, origin: str,
                            destination: str, rate, **optional) -> Result:
        """Class 1. The seventh contract.

        Board, lane and rate are required; everything after money is optional,
        because a capture with gaps beats a listing lost to the next screen.
        """
        return self.post("/api/joe/opportunity", source_board=source_board,
                         origin=origin, destination=destination, rate=rate,
                         **optional)

    def send_notice(self, *, confirmed: bool, **body) -> Result:
        """**Class 2 — the read-back happened before this was called.**

        `confirmed` is not defaulted and cannot be omitted. A client library that
        supplied it would be performing the confirmation on the driver's behalf,
        which is the one thing the class system exists to prevent. The node
        refuses without it; this refuses to hide that.
        """
        return self.post("/api/joe/send-notice", confirmed=bool(confirmed), **body)

    def update_mission_record(self, mission_id: str, *, confirmed: bool, **fields) -> Result:
        """**Class 2.** Field-level corrections. Same rule as `send_notice`:
        `confirmed` is the caller's to supply, never this library's to assume.
        The response carries old and new values for the audit log."""
        from urllib.parse import quote

        return self.patch("/api/joe/mission-record/" + quote(str(mission_id)),
                          confirmed=bool(confirmed), **fields)


# --------------------------------------------------- consuming JOE's queue

#: The only submission kind this drain will act on, and it acts on it only when
#: it parses as an Opportunity Capture.
#:
#: **Everything else stays queued.** `finding`, `recommendation`, `draft`,
#: `explanation`, `question` and `proposed_change` are proposals for a human.
#: Acting on one would be Dispatch deciding, and `dispatch_port.py` is explicit:
#: *"JOE never writes to Dispatch. It submits a request that Dispatch or Mike
#: accepts or rejects."* Accepting is a decision. Capture is the one thing that
#: is not, because OPP-CAPTURE section 1 rules it Class 1 -- internal,
#: reversible, touching no Mission Record and no outside party.
ACTS_ON = "action_request"


class DrainReport:
    """What the drain did, and what it refused to do.

    **Refusals are the point.** A drain that reported only successes would look
    identical whether it had written six captures or skipped six decisions, and
    the second is the one Mike needs to see.
    """

    __slots__ = ("captured", "left_queued", "failed", "unreachable")

    def __init__(self):
        self.captured = []      # (request, Result)
        self.left_queued = []   # (request, why)
        self.failed = []        # (request, error)
        self.unreachable = False

    @property
    def ok(self) -> bool:
        return not self.failed and not self.unreachable

    def __repr__(self) -> str:
        return ("DrainReport(captured=%d, left_queued=%d, failed=%d, unreachable=%s)"
                % (len(self.captured), len(self.left_queued), len(self.failed),
                   self.unreachable))

    def lines(self) -> list:
        """The report in the locked declarative voice, one fact per line."""
        out = []
        for request, result in self.captured:
            out.append(result.get("echo") or "LOGGED. OPPORTUNITY %s."
                       % result.get("opportunity_id", ""))
        for request, why in self.left_queued:
            out.append("LEFT QUEUED. %s. %s" % (str(getattr(request, "kind", "")).upper(), why))
        for request, error in self.failed:
            out.append("NOT LOGGED. %s" % error)
        if self.unreachable:
            out.append("DISPATCH UNREACHABLE. NOTHING WAS WRITTEN. THE QUEUE IS UNCHANGED.")
        return out


def drain(port, session, *, parse=None) -> DrainReport:
    """Consume queued requests from JOE and write the captures through the
    seventh contract.

    `port` is anything with a `pending()` returning objects that carry `kind`
    and `detail` -- **duck-typed on purpose.** Dispatch does not import
    Joe-Assistant and must not: they are separate repositories and the
    dependency would run the wrong way. `dispatch_port.py` says the interface
    belongs to Dispatch; this consumes what JOE hands over without knowing what
    JOE is.

    **It removes nothing from the queue.** JOE's queue is in-memory and JOE's to
    own; a consumer that mutated it would be reaching across a boundary that was
    drawn deliberately. What was written is reported, and what to do with the
    original is JOE's business.

    **Nothing executes by default** (Constitution 3.1). This runs when it is
    called, writes only Class 1 captures, and leaves every decision queued.
    """
    from dispatch import opportunity as opp

    parse = parse or opp.parse_dictation
    report = DrainReport()

    try:
        pending = list(port.pending())
    except Exception as unreadable:  # noqa: BLE001
        report.failed.append((None, "the queue could not be read: %s"
                              % type(unreadable).__name__))
        return report

    for request in pending:
        kind = str(getattr(request, "kind", "")).strip().lower()
        detail = str(getattr(request, "detail", "") or "").strip()

        if kind != ACTS_ON:
            report.left_queued.append(
                (request, "a %s is a proposal for Mike, not an action for Dispatch"
                 % kind or "request"))
            continue

        parsed = parse(detail)
        gaps = [g for g in parsed["missing"] if g != "rate"]
        if gaps:
            # Board and lane are the load's identity. Without them there is
            # nothing to log and nothing to deduplicate against, and inventing
            # either would be worse than leaving it queued.
            report.left_queued.append(
                (request, "not a capture: %s missing" % ", ".join(gaps)))
            continue

        try:
            result = session.capture_opportunity(**parsed["fields"])
        except NodeNotAccepting as closed:
            # Fail-closed is the node working, not a fault to route around.
            report.failed.append((request, str(closed)))
            report.unreachable = True
            break
        except DispatchError as down:
            report.failed.append((request, str(down)))
            report.unreachable = True
            break

        if result.ok:
            report.captured.append((request, result))
        else:
            report.failed.append((request, result.note or "refused by the node"))

    return report
