"""What Dispatch shows when a page fails, instead of what Flask shows.

Flask's default for an unhandled exception is a bare page reading *"Internal Server
Error — the server encountered an internal error and was unable to complete your
request."* It names nothing, offers nothing, and does not mention that a log exists.

That is a 70 MPH Test failure of the plainest kind, and it is not hypothetical: the
first time Dispatch ever ran on Mike's Windows laptop, `/home` and `/dispatch` both
returned exactly that page. Everything up to it had worked -- the launcher started, the
PIN was set, sign-in succeeded -- and the screen still gave him nothing to act on and
nothing to send. Two rounds went by hunting for a log file whose location the failing
page could simply have printed.

So this module makes a failed page say four things:

*What happened*, in the exception's own words rather than a generic sentence.
*What is still working* -- one page failing does not mean Dispatch is down, and an
operator who thinks it is will stop using it.
*Where the log is*, as an exact path on this machine.
*What to send*, as one selectable block.

Two rules hold absolutely:

**It must never fail itself.** An error page that raises replaces a useful message with
Flask's useless one, at exactly the moment the operator most needs help. Every step
below is wrapped, and the last resort is plain text with no template involved.

**It must never print a secret.** The traceback can contain a signing key, a token from
a URL, or a PIN, and this page is meant to be copied and sent. Values whose names look
secret are redacted; the names are kept, because the name is the part that helps.
"""

from __future__ import annotations

import os
import re
import traceback
from pathlib import Path

from flask import render_template, request

#: Substring markers matched case-insensitively against a *name*. Deliberately the same
#: list as `dispatch_launcher.redaction.SECRET_NAME_MARKERS` and
#: `dispatch.backup._is_secret_name`, duplicated rather than imported: the portal must
#: not depend on the launcher (the launcher starts the portal, not the other way round),
#: and THE MIKE RULE prefers a little duplication to a shared abstraction across a
#: subsystem boundary. `tests/test_error_page.py` pins the three copies together.
SECRET_NAME_MARKERS = ("SECRET", "KEY", "PASSWORD", "TOKEN", "PIN", "CREDENTIAL")

REDACTED = "[REDACTED]"

_MARKERS = "|".join(SECRET_NAME_MARKERS)

#: `NAME=value`, `NAME: value`, `"NAME": "value"`, `?name=value` -- the shapes a secret
#: actually appears in inside a traceback line. Over-redaction is the chosen failure
#: direction: a page that hides one harmless value is a nuisance, a page that prints one
#: real signing key is a breach.
_ASSIGNMENT = re.compile(
    rf"(?P<name>[\"'\w\-\.]*(?:{_MARKERS})[\"'\w\-\.]*)"
    rf"(?P<sep>\s*[=:]\s*|=)"
    rf"(?P<value>\"[^\"]*\"|'[^']*'|[^\s,;)&}}\]]+)",
    re.IGNORECASE,
)


def redact(text: str) -> str:
    """Replace the value of anything whose name looks secret. Keeps the name."""
    if not text:
        return ""

    def _sub(match: re.Match[str]) -> str:
        return f"{match.group('name')}{match.group('sep')}{REDACTED}"

    try:
        return _ASSIGNMENT.sub(_sub, text)
    except Exception:  # pragma: no cover - re never raises on a str, but this page
        # must not fail even if that stops being true.
        return "(the details could not be shown safely, so they were withheld)"


def log_directory() -> Path:
    """Where the launcher writes the portal log.

    Duplicates `dispatch_launcher.locations.logs_dir` deliberately, for the reason in
    this module's docstring. Pinned by a test so the two cannot drift -- an error page
    that names the wrong log file is worse than one that names none, because the
    operator looks there, finds nothing, and concludes the page is lying.
    """
    explicit = os.environ.get("DISPATCH_LAUNCHER_LOG_DIR")
    if explicit:
        return Path(explicit)
    ops_root = os.environ.get("DISPATCH_OPERATIONS_ROOT")
    if ops_root:
        return Path(ops_root) / "Logs"
    return Path(__file__).resolve().parent.parent / "logs"


def log_path() -> Path:
    return log_directory() / "dispatch-portal.log"


def describe(exc: BaseException) -> dict:
    """Everything the page needs, already redacted. Never raises."""
    try:
        kind = type(exc).__name__
    except Exception:  # pragma: no cover
        kind = "Error"
    try:
        message = redact(str(exc)) or "(no message)"
    except Exception:  # pragma: no cover
        message = "(no message)"
    try:
        trace = redact(
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        )
    except Exception:  # pragma: no cover
        trace = "(the traceback could not be read)"
    try:
        where = request.path
    except Exception:  # pragma: no cover - outside a request context
        where = "(unknown)"
    known = recognise(exc)
    return {
        "kind": kind,
        "message": message,
        "traceback": trace,
        "where": where,
        "log_path": str(log_path()),
        "known_headline": known[0] if known else "",
        "known_steps": known[1] if known else [],
    }


#: Failures Dispatch can recognise by sight, and what to do about each.
#:
#: The generic page already names the exception and hands over a traceback, which is
#: enough for a builder. It is not enough for an operator: `sqlite3.DatabaseError: file
#: is not a database` is a precise, correct sentence that tells Mike nothing he can act
#: on, and the action in that case is two minutes of work he could do himself.
#:
#: So a condition earns an entry here when all three are true: it is recognisable from
#: the exception alone, it has a remedy an operator can carry out, and getting it wrong
#: is not destructive. Anything else stays generic -- a confident wrong instruction is
#: worse than an honest "send me this".
#:
#: Each entry is (predicate, headline, steps).
KNOWN_CONDITIONS = []


def _is_corrupt_database(exc: BaseException) -> bool:
    """A `dispatch.db` that is not a readable SQLite file.

    Reproduced deliberately before this was written: a truncated database returns 500 on
    every page that reads freight data while `/login` still works, because sign-in reads
    a small JSON file and never opens the database. A missing database and a zero-byte
    one are both fine -- SQLite creates or initialises those -- so this is specifically
    the partially-written case.
    """
    import sqlite3

    if not isinstance(exc, sqlite3.DatabaseError):
        return False
    text = str(exc).lower()
    return any(
        marker in text
        for marker in (
            "file is not a database",
            "database disk image is malformed",
            "file is encrypted",
        )
    )


def _corrupt_database_steps() -> list[str]:
    from dispatch import db as dispatch_db

    try:
        where = str(dispatch_db.get_db_path())
    except Exception:  # pragma: no cover - path resolution should not fail here
        where = "dispatch.db (search for it in File Explorer)"
    return [
        "Stop Dispatch — press 8 in the black window, or close it.",
        f"Open this file's folder: {where}",
        "Rename dispatch.db to dispatch.db.old. If dispatch.db-wal or dispatch.db-shm "
        "are beside it, rename those too.",
        "Start Dispatch again. It rebuilds the database automatically.",
        "Rename rather than delete, so nothing is lost if this was not the cause.",
    ]


KNOWN_CONDITIONS = [
    (
        _is_corrupt_database,
        "Dispatch's database file is damaged and could not be opened.",
        _corrupt_database_steps,
    ),
]


def recognise(exc: BaseException) -> tuple[str, list[str]] | None:
    """Match a known condition, or None. Never raises."""
    for predicate, headline, steps in KNOWN_CONDITIONS:
        try:
            if predicate(exc):
                return headline, steps()
        except Exception:  # pragma: no cover - a broken recogniser must not win
            continue
    return None


#: The last resort. No template, no Jinja, no context processor -- if the styled page
#: cannot render, this still reaches the operator, and it still carries the traceback
#: they need to send.
_PLAIN = """DISPATCH - this page could not be built

Page:  {where}
Error: {kind}: {message}
{known_block}
The rest of Dispatch is still running. Only this page failed.

The full details are in:
  {log_path}

Send everything below this line.
------------------------------------------------------------
{traceback}
"""


def register(app) -> None:
    """Install the handler. Called from create_app."""

    @app.errorhandler(Exception)
    def _unhandled(exc):  # noqa: ANN001 - Flask's signature
        # Let Flask's own HTTP errors (404, 405, 413 ...) keep their normal behaviour.
        # This page is for a *crash*, and dressing a 404 up as one would be a lie.
        from werkzeug.exceptions import HTTPException

        if isinstance(exc, HTTPException):
            return exc

        detail = describe(exc)
        # Log it too, so the record exists even if nobody copies the screen.
        try:
            app.logger.error(
                "Unhandled error on %s: %s", detail["where"], detail["traceback"]
            )
        except Exception:  # pragma: no cover
            pass
        if detail["known_headline"]:
            steps = "\n".join(f"  {i}. {s}" for i, s in enumerate(detail["known_steps"], 1))
            detail = {**detail, "known_block": f"\n{detail['known_headline']}\n\n{steps}\n"}
        else:
            detail = {**detail, "known_block": ""}
        try:
            return render_template("error.html", **detail), 500
        except Exception:  # pragma: no cover - a broken template must not win
            return _PLAIN.format(**detail), 500, {"Content-Type": "text/plain; charset=utf-8"}
