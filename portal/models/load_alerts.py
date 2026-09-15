"""Load-board alert emails become cards: settings, the check, and what the Loads screen shows.

Owner direction, 2026-09-15, on the idea of load-board alert emails becoming
cards while he drives: *"i like this very much"* ... *"i will setup. can we use
Ops@l1truck .com? if we can create a small email sort to push the incoming
emails from specific senders to a box then the reader can do it's thing."*

    mailbox folder --read-only--> alert reader --> capture contract --> card

**What a check does, in order.**

  1. Nothing at all while the settings are not there (`UNCONFIGURED`): no
     mailbox is opened without a sender list.
  2. Asks the alert mailbox adapter for the folder's messages from the last day.
     Not `LIVE` -- Outlook closed, the folder missing -- and the check stops and
     says why (`UNAVAILABLE`).
  3. Clears uncommitted loads whose pickup has gone by (D12), as a paste does.
  4. Each message not handled before: a sender not on the list is ignored and
     counted; an allowed one is read (`dispatch/alert_reader.py`) and each load
     in it goes through the paste's own capture path
     (`opportunity_card.capture_from_text`) -- dedupe and merge rules and all.
     A load whose pickup has passed is not carded. A load matching a committed
     record is left alone. What cannot be read is kept as *needs a look*.
  5. Remembers every message it handled, by the mailbox's id and by a
     fingerprint, in this store -- never by marking anything in the mailbox.

**The mailbox is never changed.** No send, reply, move, delete, flag or
read-mark, from here or from the adapter.

**Scheduled checking is opt-in** (`check_every_minutes`, default 0 = off), runs
on one background thread started with the portal, one check at a time, never
under TESTING, and never inside a request. It needs Outlook open on the node.

Stores, both in the portal data directory beside `sandbox.json`:
`load_alerts_settings.json` (what Mike set) and `load_alerts_state.json` (what
was handled, the last check's report, the needs-a-look list).
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

from portal.models import atomic_write_json, get_data_dir

SETTINGS_FILE = "load_alerts_settings.json"
STATE_FILE = "load_alerts_state.json"

DEFAULT_FOLDER = "Load Alerts"

#: How often a scheduled check may run, in minutes. 0 is off, and is the default.
INTERVALS = (0, 5, 10, 15, 30, 60)

#: Environment overrides, for a node set up from its launcher. They win over the file.
ENV = {
    "mailbox": "DISPATCH_ALERT_MAILBOX",
    "folder": "DISPATCH_ALERT_FOLDER",
    "senders": "DISPATCH_ALERT_SENDERS",
    "check_every_minutes": "DISPATCH_ALERT_CHECK_MINUTES",
}

#: How far back each check reads. Handled messages are skipped by id, so reading
#: a whole day costs little and survives the node having been offline.
LOOKBACK_HOURS = 24

#: How long a handled message is remembered. Longer than any alert stays in the window.
REMEMBER_DAYS = 30

#: How many needs-a-look items are kept for the screen.
NEEDS_LOOK_KEPT = 25

#: The card's source label, and the audit channel. Named by nature.
SOURCE_LABEL = "email alert"
AUDIT_CHANNEL = "EMAIL"

#: The capture contract's channel for a load a machine found rather than a
#: person said or typed. The contract's channels are ratified (VOICE, CHAT,
#: MISSIONSCREEN, SWEEP); a new EMAIL channel is the Owner's to add, so the
#: card's `source` says "email alert" and the contract row says SWEEP.
CAPTURE_VIA = "SWEEP"

STATUS_LIVE = "LIVE"
STATUS_CONFIGURED = "CONFIGURED"
STATUS_UNCONFIGURED = "UNCONFIGURED"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_SIMULATED = "SIMULATED"

COUNT_KEYS = ("messages", "alerts_read", "new_cards", "merged", "possible_duplicates",
              "ignored_senders", "needs_look", "expired_skipped", "committed_untouched",
              "already_seen")

_CHECK_LOCK = threading.Lock()
_STORE_LOCK = threading.RLock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _path(name: str):
    folder = get_data_dir()
    folder.mkdir(parents=True, exist_ok=True)
    return folder / name


def _read_json(name: str) -> dict:
    path = _path(name)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


# ------------------------------------------------------------------ settings

def approved_mailboxes() -> tuple:
    from dispatch.connectors import registry

    return registry.approved_mailboxes()


def _default_mailbox() -> str:
    approved = approved_mailboxes()
    return approved[0] if approved else ""


def settings() -> dict:
    """What is set, file first then environment, with which keys the environment set."""
    from dispatch import alert_reader

    stored = _read_json(SETTINGS_FILE)
    merged = {
        "mailbox": str(stored.get("mailbox") or _default_mailbox()),
        "folder": str(stored.get("folder") or DEFAULT_FOLDER),
        "senders": alert_reader.normalise_senders(stored.get("senders") or []),
        "check_every_minutes": _interval(stored.get("check_every_minutes")),
        "profiles": stored.get("profiles") if isinstance(stored.get("profiles"), dict) else {},
        "from_env": [],
    }
    for key, var in ENV.items():
        raw = os.environ.get(var)
        if raw is None or not raw.strip():
            continue
        if key == "senders":
            merged[key] = alert_reader.normalise_senders([raw])
        elif key == "check_every_minutes":
            merged[key] = _interval(raw)
        else:
            merged[key] = raw.strip()
        merged["from_env"].append(key)
    return merged


def _interval(value) -> int:
    try:
        minutes = int(str(value).strip())
    except (TypeError, ValueError):
        return 0
    return minutes if minutes in INTERVALS else 0


def unconfigured_reason(current: dict) -> str:
    """Why checking cannot run on these settings, or empty when it can."""
    approved = [m.lower() for m in approved_mailboxes()]
    if not current.get("mailbox"):
        return "No mailbox is set."
    if current["mailbox"].lower() not in approved:
        return "%s is not an approved mailbox." % current["mailbox"]
    if not current.get("folder"):
        return "No folder is set."
    if not current.get("senders"):
        return "No alert senders are listed yet. Add the boards' sender addresses."
    return ""


def save_settings(form: dict) -> dict:
    """Validate and store the settings form. `{"ok", "problems", "settings"}`. Nothing is
    stored when anything is wrong."""
    from dispatch import alert_reader

    problems = []
    mailbox = str(form.get("mailbox") or "").strip()
    approved = approved_mailboxes()
    if mailbox.lower() not in [m.lower() for m in approved]:
        problems.append("The mailbox must be one of: %s." % ", ".join(approved))
    else:
        mailbox = next(m for m in approved if m.lower() == mailbox.lower())
    folder = str(form.get("folder") or "").strip()
    if not folder:
        problems.append("The folder name is required.")

    raw_senders = str(form.get("senders") or "")
    senders = alert_reader.normalise_senders(raw_senders.splitlines())
    typed = [p for p in raw_senders.replace(",", "\n").replace(";", "\n").split() if p.strip()]
    rejected = [p for p in typed if not alert_reader.normalise_senders([p])]
    if rejected:
        problems.append("Not an address or a domain: %s." % ", ".join(rejected))

    minutes_raw = str(form.get("check_every_minutes") or "0").strip()
    minutes = _interval(minutes_raw)
    if str(minutes) != minutes_raw and minutes_raw not in ("", "0"):
        problems.append("Check every must be one of %s minutes."
                        % ", ".join(str(i) for i in INTERVALS))

    profiles_raw = str(form.get("profiles") or "").strip()
    profiles = {}
    if profiles_raw:
        try:
            profiles = json.loads(profiles_raw)
        except ValueError as exc:
            problems.append("The board hints do not read as JSON (%s)." % exc)
            profiles = {}
        else:
            problems.extend(alert_reader.check_profiles(profiles))

    if problems:
        return {"ok": False, "problems": problems, "settings": None}

    stored = {"mailbox": mailbox, "folder": folder, "senders": senders,
              "check_every_minutes": minutes,
              "profiles": {str(k).strip().lower().lstrip("@"): v for k, v in profiles.items()}}
    with _STORE_LOCK:
        atomic_write_json(_path(SETTINGS_FILE), stored)
    return {"ok": True, "problems": [], "settings": settings()}


# --------------------------------------------------------------------- state

def _state() -> dict:
    state = _read_json(STATE_FILE)
    state.setdefault("processed", {})
    state.setdefault("needs_look", [])
    state.setdefault("last_check", {})
    return state


def _save_state(state: dict) -> None:
    cutoff = (_utc_now() - timedelta(days=REMEMBER_DAYS)).isoformat()
    state["processed"] = {k: v for k, v in state["processed"].items()
                          if str((v or {}).get("at") or "") >= cutoff}
    state["needs_look"] = state["needs_look"][:NEEDS_LOOK_KEPT]
    atomic_write_json(_path(STATE_FILE), state)


def message_keys(message: dict) -> list:
    """How a handled message is recognised again: the mailbox's id, and a fingerprint.

    The fingerprint (sender, subject, received time) still recognises it if the
    mailbox ever gives the same message a new id.
    """
    keys = []
    if str(message.get("message_id") or "").strip():
        keys.append("id:%s" % message["message_id"])
    print_of = "|".join(str(message.get(k) or "").strip().lower()
                        for k in ("sender", "subject", "received_at"))
    keys.append("print:%s" % hashlib.sha1(print_of.encode("utf-8")).hexdigest())
    return keys


# --------------------------------------------------------------------- check

def _adapter():
    """The alert mailbox adapter. Tests replace this with a fake."""
    from dispatch.connectors import registry

    return registry.alert_mailbox()


def _blank_report(how: str, driver: str) -> dict:
    return {"status": "", "reason": "", "checked_at": _utc_now().isoformat(),
            "how": how, "driver": driver, "mailbox": "", "folder": "",
            "counts": {k: 0 for k in COUNT_KEYS}, "needs_look": [], "cards": []}


def check_now(*, driver: str = "operations", how: str = "manual", adapter=None) -> dict:
    """Run one check. One at a time: a second caller is told a check is running.

    Returns the report the Loads screen shows. Never raises for an operational
    condition; an unexpected error is reported as UNAVAILABLE with its type.
    """
    if not _CHECK_LOCK.acquire(blocking=False):
        return {"busy": True, "status": "", "reason": "A check is already running.",
                "counts": {k: 0 for k in COUNT_KEYS}, "needs_look": [], "cards": []}
    try:
        report = _blank_report(how, driver)
        try:
            _run(report, driver=driver, adapter=adapter)
        except Exception as exc:  # noqa: BLE001 - reported, never silent
            report["status"] = STATUS_UNAVAILABLE
            report["reason"] = "The check stopped on an unexpected error (%s)." % type(exc).__name__
        with _STORE_LOCK:
            state = _state()
            state["last_check"] = report
            state["needs_look"] = report["needs_look"] + state["needs_look"]
            _save_state(state)
        _audit(report)
        return report
    finally:
        _CHECK_LOCK.release()


def _run(report: dict, *, driver: str, adapter) -> None:
    from dispatch import alert_reader
    from portal.models import opportunity_card

    current = settings()
    report["mailbox"], report["folder"] = current["mailbox"], current["folder"]
    missing = unconfigured_reason(current)
    if missing:
        report["status"], report["reason"] = STATUS_UNCONFIGURED, missing
        return

    adapter = adapter if adapter is not None else _adapter()
    if adapter is None:
        report["status"] = STATUS_UNAVAILABLE
        report["reason"] = "There is no mailbox reader on this build."
        return

    with _STORE_LOCK:
        processed = dict(_state()["processed"])
    known_ids = [k[3:] for k in processed if k.startswith("id:")]
    read = adapter.read_since(mailbox=current["mailbox"], folder=current["folder"],
                              since=_utc_now() - timedelta(hours=LOOKBACK_HOURS),
                              known=known_ids)
    status = str(read.get("status") or "")
    if status not in (STATUS_LIVE, STATUS_SIMULATED):
        report["status"] = status if status in (STATUS_UNAVAILABLE, STATUS_UNCONFIGURED) \
            else STATUS_UNAVAILABLE
        report["reason"] = str(read.get("reason") or "The mailbox could not be read.")
        return
    report["status"] = status
    origin = STATUS_LIVE if status == STATUS_LIVE else STATUS_SIMULATED

    # D12: expired uncommitted loads go when work is done, as a paste does.
    opportunity_card.discard_expired(driver=driver)

    handled = {}
    for message in read.get("messages") or []:
        report["counts"]["messages"] += 1
        keys = message_keys(message)
        if any(k in processed or k in handled for k in keys):
            report["counts"]["already_seen"] += 1
            continue
        outcome = alert_reader.read_alert(message, allowed=current["senders"],
                                          profiles=current["profiles"])
        if not outcome["allowed"]:
            report["counts"]["ignored_senders"] += 1
            _remember(handled, keys, message, "ignored sender")
            continue
        report["counts"]["alerts_read"] += 1
        results = [_card_one(load, outcome, message, report, driver=driver, origin=origin)
                   for load in outcome["loads"]]
        for item in outcome["needs_look"]:
            _needs_look(report, message, outcome, item["reason"], item.get("fields"))
        _remember(handled, keys, message, ", ".join(results) or "needs a look")

    with _STORE_LOCK:
        state = _state()
        state["processed"].update(handled)
        _save_state(state)


def _remember(handled: dict, keys: list, message: dict, outcome: str) -> None:
    entry = {"at": _utc_now().isoformat(), "sender": str(message.get("sender") or ""),
             "subject": str(message.get("subject") or "")[:200], "outcome": outcome}
    for key in keys:
        handled[key] = entry


def _needs_look(report: dict, message: dict, outcome: dict, reason: str, fields=None) -> None:
    report["counts"]["needs_look"] += 1
    report["needs_look"].append({
        "subject": str(message.get("subject") or "")[:200],
        "sender": outcome.get("original_sender") or outcome.get("sender") or "",
        "board": outcome.get("board", ""),
        "received_at": str(message.get("received_at") or ""),
        "reason": reason,
        "read": {k: v for k, v in (fields or {}).items()
                 if k in ("origin", "destination", "rate", "pickup_date")},
        "noted_at": report["checked_at"],
    })


def _card_one(load: dict, outcome: dict, message: dict, report: dict, *,
              driver: str, origin: str) -> str:
    """One load read out of an alert, through the paste's capture path. Returns what happened."""
    from dispatch import clock, opportunity
    from portal.models import opportunity_card, sandbox

    fields = load["fields"]
    deadline = opportunity_card.pickup_deadline(fields.get("pickup_date") or "",
                                                day=clock.home_date())
    if deadline is not None and clock.home_now() > deadline:
        report["counts"]["expired_skipped"] += 1
        return "pickup passed"

    verdict, twin = opportunity.classify(fields, opportunity.all_open())
    if verdict == "MATCH" and twin is not None:
        existing = sandbox.get("SBX-%s-%s" % (opportunity_card.SOURCE_TYPE.upper(),
                                              twin["opportunity_id"])) or {}
        if opportunity_card.is_protected(existing):
            report["counts"]["committed_untouched"] += 1
            return "matches a committed load; left alone"

    sender = outcome.get("original_sender") or outcome.get("sender") or ""
    captured = opportunity_card.capture_from_text(
        load["text"], kind=load["kind"], driver=driver, via=CAPTURE_VIA,
        audit_channel=AUDIT_CHANNEL, data_origin=origin,
        told_as="email alert from %s" % sender,
        card_facts={"source": SOURCE_LABEL, "alert_board": outcome.get("board", ""),
                    "alert_sender": sender,
                    "alert_subject": str(message.get("subject") or "")[:200],
                    "alert_received_at": str(message.get("received_at") or "")})
    if not captured["ok"]:
        _needs_look(report, message, outcome, captured["note"] or "The card was refused.",
                    fields)
        return "refused"

    record = captured["record"]
    verdict = record.get("verdict", "NEW")
    key = {"MERGED": "merged", "AMBIGUOUS": "possible_duplicates"}.get(verdict, "new_cards")
    report["counts"][key] += 1
    report["cards"].append({"id": captured["entry"]["id"], "verdict": verdict,
                            "lane": "%s to %s" % (record.get("origin", ""),
                                                  record.get("destination", ""))})
    return verdict.lower()


def _audit(report: dict) -> None:
    from dispatch import audit

    counts = report["counts"]
    if report["status"] in (STATUS_LIVE, STATUS_SIMULATED):
        result = audit.RESULT_PARTIAL if counts["needs_look"] else audit.RESULT_SUCCESS
    else:
        result = audit.RESULT_FAILURE
    note = "%s check, %s: %s" % (report["how"], report["status"], ", ".join(
        "%s %d" % (k.replace("_", " "), counts[k]) for k in COUNT_KEYS if counts[k]))
    if report["reason"]:
        note += " -- " + report["reason"]
    try:
        audit.record(action="load-alert-check", driver=report["driver"] or "operations",
                     channel=AUDIT_CHANNEL, result=result, note=note)
    except Exception:  # noqa: BLE001 - the report is already stored; the check is done
        pass


# ------------------------------------------------------------ what is shown

def strip() -> dict:
    """What the Loads screen's LOAD ALERTS strip shows. Reads; changes nothing (D9).

    Never opens the mailbox: the status is the settings' state, or what the
    last check found, with when.
    """
    current = settings()
    with _STORE_LOCK:
        state = _state()
    last = state.get("last_check") or {}
    missing = unconfigured_reason(current)
    if missing:
        status, reason = STATUS_UNCONFIGURED, missing
    elif last.get("status") and last.get("status") != STATUS_UNCONFIGURED:
        status, reason = last["status"], last.get("reason", "")
    else:
        status, reason = STATUS_CONFIGURED, "Set up, not checked yet."
    return {
        "status": status,
        "reason": reason,
        "mailbox": current["mailbox"],
        "folder": current["folder"],
        "senders": len(current["senders"]),
        "every_minutes": current["check_every_minutes"],
        "last_check": last.get("checked_at", ""),
        "last_how": last.get("how", ""),
        "counts": dict({k: 0 for k in COUNT_KEYS}, **(last.get("counts") or {})),
        "needs_look": state.get("needs_look", [])[:5],
        "running": _CHECK_LOCK.locked(),
    }


def check_for_request(*, driver: str, wait_seconds: float = 20.0) -> dict:
    """The CHECK ALERTS NOW button. Runs the check off the request thread and waits a
    little for it; a slow mailbox never holds the screen longer than that."""
    holder: dict = {}

    def _work():
        holder["report"] = check_now(driver=driver, how="manual")

    worker = threading.Thread(target=_work, name="load-alert-check-now", daemon=True)
    worker.start()
    worker.join(timeout=wait_seconds)
    if worker.is_alive():
        return {"still_running": True}
    return holder.get("report") or {"still_running": True}


def summary_line(report: dict) -> str:
    """The one line a check leaves on the Loads screen."""
    if report.get("still_running"):
        return "Still checking the alert folder. Look again in a minute."
    if report.get("busy"):
        return "A check is already running."
    status = report.get("status", "")
    if status not in (STATUS_LIVE, STATUS_SIMULATED):
        return "Load alerts %s: %s" % (status, report.get("reason", ""))
    c = report["counts"]
    parts = ["%d new card%s" % (c["new_cards"], "" if c["new_cards"] == 1 else "s"),
             "%d merged" % c["merged"]]
    if c["possible_duplicates"]:
        parts.append("%d possible duplicate%s" % (c["possible_duplicates"],
                                                  "" if c["possible_duplicates"] == 1 else "s"))
    parts.append("%d ignored sender%s" % (c["ignored_senders"],
                                          "" if c["ignored_senders"] == 1 else "s"))
    parts.append("%d need%s a look" % (c["needs_look"], "s" if c["needs_look"] == 1 else ""))
    if c["expired_skipped"]:
        parts.append("%d past pickup, not carded" % c["expired_skipped"])
    if c["committed_untouched"]:
        parts.append("%d matched a committed load, left alone" % c["committed_untouched"])
    return "Load alerts %s: %s." % (status, ", ".join(parts))


# ------------------------------------------------------------ the schedule

_worker = None
_stop = threading.Event()

#: How often the background thread looks at the setting. A change on the
#: settings screen takes effect within this, without a restart.
POLL_SECONDS = 30


def start_background(app=None):
    """Start the scheduled checker with the portal. Returns the thread, or None.

    Never under TESTING or a test run. The thread idles while
    `check_every_minutes` is 0, so turning it on from the settings screen needs
    no restart. One check at a time is held by `check_now` itself.
    """
    global _worker
    if app is not None and app.config.get("TESTING"):
        return None
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    if _worker is not None and _worker.is_alive():
        return _worker
    _stop.clear()
    _worker = threading.Thread(target=_loop, name="load-alert-schedule", daemon=True)
    _worker.start()
    return _worker


def _loop() -> None:
    last_run = None
    while not _stop.wait(POLL_SECONDS):
        try:
            minutes = settings()["check_every_minutes"]
        except Exception:  # noqa: BLE001 - a bad settings file must not kill the thread
            continue
        if minutes <= 0:
            continue
        if last_run is not None and time.monotonic() - last_run < minutes * 60:
            continue
        last_run = time.monotonic()
        try:
            check_now(driver="operations", how="scheduled")
        except Exception:  # noqa: BLE001 - check_now reports its own failures
            pass
