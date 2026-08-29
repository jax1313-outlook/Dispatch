"""Sweep Control. Activation event 1.

The Intelligence sweep can be started two ways: a button, or a clock. Both
live here, and the clock's controls live in the Portal rather than in a
configuration file or on the public website.

    Starting a sweep creates or enriches Opportunity Records.
    It never creates a Mission Record. Only ACCEPT LOAD does that.

WHAT IS REAL AND WHAT IS NOT
============================

The sweep itself is `dispatch/acquisition.py`, which is real and already in
the repository. This module drives it and remembers the schedule.

The *scheduler* is a boundary, not a daemon. Nothing in this repository runs
continuously, so a timer that claims to fire at 05:30 while the program is
closed would be a lie. `next_run()` computes and reports the next due time
honestly, and `due()` says whether that moment has passed - so whatever does
run the process (a launcher, a task, a person opening the portal) can ask and
act. The portal shows the real answer either way, including "the program was
not running, so it did not fire".
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATE_FILE = "sweep_state.json"

STATE_IDLE = "idle"
STATE_RUNNING = "running"
STATE_ERROR = "error"


def _state_path() -> Path:
    from portal.models import get_data_dir

    directory = Path(get_data_dir())
    directory.mkdir(parents=True, exist_ok=True)
    return directory / STATE_FILE


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read() -> dict:
    path = _state_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write(state: dict) -> dict:
    _state_path().write_text(
        json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state


# ---- schedule ----------------------------------------------------------

def next_run(state: dict | None = None) -> str:
    """When the sweep is next due, or empty if the timer is off.

    Reported in plain local clock terms because a driver reads it, not a cron
    parser.
    """
    state = state if state is not None else _read()
    if not state.get("timer_enabled"):
        return ""
    daily_at = str(state.get("daily_at") or "").strip()
    if not daily_at or ":" not in daily_at:
        return ""
    try:
        hour, minute = (int(part) for part in daily_at.split(":")[:2])
    except ValueError:
        return ""
    now = datetime.now()
    due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if due <= now:
        due = due + timedelta(days=1)
    return due.strftime("%Y-%m-%d %H:%M")


def due(state: dict | None = None) -> bool:
    """Has the scheduled moment passed without a run since?"""
    state = state if state is not None else _read()
    if not state.get("timer_enabled"):
        return False
    scheduled = next_run(state)
    if not scheduled:
        return False
    last = str(state.get("last_run") or "")
    # next_run() always reports a FUTURE time, so the question is whether the
    # previous occurrence was missed.
    previous = datetime.strptime(scheduled, "%Y-%m-%d %H:%M") - timedelta(days=1)
    if not last:
        return datetime.now() >= previous
    try:
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
    except ValueError:
        return True
    return last_dt.replace(tzinfo=None) < previous <= datetime.now()


def set_schedule(timer_enabled: bool, daily_at: str = "") -> dict:
    """Save the timer settings the driver typed into the Portal."""
    state = _read()
    state["timer_enabled"] = bool(timer_enabled)
    if daily_at:
        state["daily_at"] = str(daily_at)[:5]
    state["schedule_saved_at"] = _now().isoformat()
    return status(_write(state))


# ---- running -----------------------------------------------------------

def start(runner=None) -> dict:
    """Run a sweep now.

    `runner` is injected so this can be exercised without touching the real
    acquisition engine. Left unset, it uses the real one.
    """
    state = _read()
    state["state"] = STATE_RUNNING
    state["message"] = ""
    _write(state)

    try:
        if runner is None:
            from dispatch import acquisition

            result = acquisition.acquire()
        else:
            result = runner()
        state = _read()
        state["state"] = STATE_IDLE
        state["last_run"] = _now().isoformat()
        state["last_result"] = _describe(result)
        state["message"] = ""
    except Exception as error:  # noqa: BLE001 - reported, never swallowed
        state = _read()
        state["state"] = STATE_ERROR
        state["last_run"] = _now().isoformat()
        # Plain language. A driver should not have to read a stack trace to
        # learn that the load board did not answer.
        state["message"] = _plain(error)
    return status(_write(state))


def _describe(result) -> str:
    """What the sweep actually did, in words."""
    if isinstance(result, dict):
        found = result.get("created", result.get("count"))
        if found is not None:
            return "%s opportunity record(s)" % found
    if isinstance(result, (list, tuple)):
        return "%d opportunity record(s)" % len(result)
    return "completed"


def _plain(error: Exception) -> str:
    """Turn an exception into something worth reading at a truck stop."""
    text = str(error) or error.__class__.__name__
    lowered = text.lower()
    if "connection" in lowered or "timed out" in lowered or "network" in lowered:
        return ("The load board did not answer. That is usually signal, not "
                "the program. Try again when you have bars.")
    if "permission" in lowered or "denied" in lowered or "401" in text or "403" in text:
        return ("The load board refused the login. The credentials may have "
                "expired.")
    if "no such file" in lowered or "not found" in lowered:
        return "A file the sweep needs is missing: " + text
    return text[:200]


# ---- what the portal shows --------------------------------------------

def status(state: dict | None = None) -> dict:
    """Everything the Sweep Control area displays, already in plain terms."""
    state = state if state is not None else _read()
    scheduled = next_run(state)
    return {
        "state": state.get("state", STATE_IDLE),
        "timer_enabled": bool(state.get("timer_enabled")),
        "daily_at": state.get("daily_at", "05:30"),
        "last_run": _human(state.get("last_run")),
        "last_result": state.get("last_result", ""),
        "next_run": scheduled or "",
        "due_now": due(state),
        "message": state.get("message", ""),
    }


def _human(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        stamp = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return str(iso)
    return stamp.astimezone().strftime("%Y-%m-%d %H:%M")
