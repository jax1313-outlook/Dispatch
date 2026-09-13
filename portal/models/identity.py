"""Identity model — DISPATCH_PIN authentication (Authority role only).

Minimal first build against SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md (Claude-3 repo,
found in the Jules-3/Claude-2 doctrine-review repos) -- Authority role only, per
governance/PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md. PIN records are never stored in
Library here -- the specification makes that storage choice conditional on Mike's decision
(Section 11), not a default, and Library's real schema (portal/models/library.py) has no
credential concept to retrofit.

Driver and External Viewer roles, PIN self-service change/reset, and the full session/
permission-snapshot model from the specification are explicitly deferred -- not built here.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from portal.models import get_data_dir, atomic_write_json, guarded

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


class IdentityError(ValueError):
    """Raised for identity/PIN operations that violate the auth model (e.g. bootstrap called
    when an identity already exists, or an invalid PIN at creation time)."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _identity_path() -> Path:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "identity.json"


def _load() -> dict:
    path = _identity_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save(data: dict) -> None:
    path = _identity_path()
    atomic_write_json(path, data)


def _public(record: dict) -> dict:
    """Strip pin_hash, and read the lockout state from where it is authoritative.

    `failed_attempt_count` and `locked_until` are no longer stored in this file.
    They are counters under contention, and every store in this package does
    read-modify-write on the whole file, so two concurrent failures wrote 1 and 1
    instead of 1 and 2 -- the lockout was defeated by sending the guesses at the
    same time. They live in `dispatch.authcounters` now, where the increment is a
    single UPDATE inside a transaction. The shape returned to callers is
    unchanged, which is why this reads them back in here.
    """
    from dispatch import authcounters

    out = {k: v for k, v in record.items() if k != "pin_hash"}
    if record.get("user_id"):
        state = authcounters.get_state(authcounters.KIND_AUTHORITY, record["user_id"])
        out["failed_attempt_count"] = state["failed_attempt_count"]
        out["locked_until"] = state["locked_until"]
    return out


def has_any_identity() -> bool:
    return bool(_load())


def get_authority_user_id() -> str | None:
    """Return the sole Authority identity's user_id, or None if not yet bootstrapped.

    This build supports exactly one identity, so the real Portal login form does not need to
    ask "who are you" -- only "what's the PIN." A future multi-role build would replace this
    with a real identity-selection step (spec Section 4.3, step 1).
    """
    for uid, rec in _load().items():
        if rec.get("role") == "Authority":
            return uid
    return None


def get_identity(user_id: str) -> dict | None:
    rec = _load().get(user_id)
    return _public(rec) if rec else None


@guarded(_identity_path)
def bootstrap_authority(user_id: str, display_name: str, pin: str) -> dict:
    """Create the first (and, in this build, only) Authority identity.

    Refuses if any identity already exists -- this is a one-time bootstrap operation, not a
    general "create user" function. There is no general create-user path in this build; a
    second Authority identity, or a Driver/External Viewer identity, is out of scope (see
    PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md Section 1 -- single-role build).
    """
    data = _load()
    if data:
        raise IdentityError(
            "bootstrap_authority() refused: an identity already exists. This build supports "
            "exactly one Authority identity, created once."
        )
    if not user_id or not display_name:
        raise IdentityError("user_id and display_name are both required.")
    if not pin or len(pin) < 4:
        raise IdentityError("PIN must be at least 4 characters.")

    now = _utc_now()
    record = {
        "user_id": user_id,
        "display_name": display_name,
        "role": "Authority",
        "status": "active",
        "pin_hash": generate_password_hash(pin),
        "created_at": now,
        "updated_at": now,
        "last_login_at": None,
        # failed_attempt_count / locked_until are NOT stored here; see _public().
    }
    data[user_id] = record
    _save(data)
    _log_event("PIN_CHANGED", user_id, {"reason": "bootstrap"})
    return _public(record)


@guarded(_identity_path)
def set_pin(user_id: str, pin: str) -> dict:
    """Replace an existing identity's PIN. The recovery path for a forgotten one.

    `bootstrap_authority` deliberately refuses once an identity exists, which is correct for a
    one-time bootstrap and left the build with no way back in: a forgotten PIN meant deleting
    `identity.json` by hand or losing access to Dispatch entirely. This is that missing path,
    and it is a **reset**, not a change -- it does not ask for the old PIN, because the person
    who needs it by definition does not have it.

    What makes that acceptable is the trust basis, and it is worth stating plainly rather than
    leaving implied: this function is reachable only from the launcher running locally on the
    machine that holds the data. Somebody with physical access to that machine can already read
    `identity.json`, delete it, or copy the whole database. A local reset grants no authority
    they did not already have; it just means they do not have to destroy anything to use it.
    There is no route, no token and no remote caller -- adding one would change the trust basis
    completely and is not what this is.

    A deliberate reset also clears a lockout. A person locked out by failed attempts and then
    resetting their PIN at the keyboard has proven the only thing lockout was protecting
    against, and leaving them locked for the remainder of the window would punish the recovery.
    """
    data = _load()
    record = data.get(user_id)
    if not record:
        raise IdentityError(f"No identity named {user_id!r} exists.")
    if not pin or len(pin) < 4:
        raise IdentityError("PIN must be at least 4 characters.")

    record["pin_hash"] = generate_password_hash(pin)
    from dispatch import authcounters

    authcounters.clear(authcounters.KIND_AUTHORITY, user_id)
    record["updated_at"] = _utc_now()
    _save(data)
    # PIN_CHANGED is the event type this build already emits for a bootstrap; the reason
    # distinguishes the two in the log without inventing an event type the spec defers.
    _log_event("PIN_CHANGED", user_id, {"reason": "reset"})
    return _public(record)


def _is_locked(record: dict) -> bool:
    from dispatch import authcounters

    return authcounters.is_locked(authcounters.KIND_AUTHORITY, record.get("user_id", ""))


@guarded(_identity_path)
def verify_pin(user_id: str, pin: str) -> dict | None:
    """Validate a PIN. Returns the public identity record on success, None on failure.

    Handles lockout: after MAX_FAILED_ATTEMPTS consecutive failures, the identity is locked for
    LOCKOUT_MINUTES -- a correct PIN during that window is still rejected without even being
    checked, matching the specification's "revoked/locked PINs may not authenticate" rule
    (Section 4.6) applied to lockout as well as revocation.
    """
    data = _load()
    record = data.get(user_id)
    if not record or record.get("status") != "active":
        _log_event("LOGIN_FAILURE", user_id, {"reason": "unknown_or_inactive_identity"})
        return None

    if _is_locked(record):
        _log_event("LOGIN_FAILURE", user_id, {"reason": "locked"})
        return None

    from dispatch import authcounters

    if check_password_hash(record["pin_hash"], pin):
        authcounters.record_success(authcounters.KIND_AUTHORITY, user_id)
        record["last_login_at"] = _utc_now()
        record["updated_at"] = _utc_now()
        _save(data)
        _log_event("LOGIN_SUCCESS", user_id, {})
        return _public(record)

    state = authcounters.record_failure(
        authcounters.KIND_AUTHORITY, user_id,
        max_attempts=MAX_FAILED_ATTEMPTS, lockout_minutes=LOCKOUT_MINUTES,
    )
    _log_event(
        "LOGIN_FAILURE", user_id,
        # The count the attempt actually reached, read back from the statement
        # that incremented it -- not the number this process believed it was
        # setting, which is precisely what went wrong under concurrency.
        {"reason": "bad_pin", "failed_attempt_count": state["failed_attempt_count"]},
    )
    return None


def record_session_created(user_id: str) -> None:
    """Log SESSION_CREATED. Called by the login route after Flask sets the session, not by
    verify_pin() -- session handling is a route/Flask concern, kept out of this module so it
    stays testable without a Flask request context."""
    _log_event("SESSION_CREATED", user_id, {})


def _security_log_path() -> Path:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "security_events.jsonl"


def _log_event(event_type: str, user_id: str, detail: dict) -> None:
    """Append-only security event log. Minimum event set for this build, per
    PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md Section 6: LOGIN_SUCCESS, LOGIN_FAILURE,
    SESSION_CREATED, PIN_CHANGED. The remaining 8 event types from the full specification
    (PIN_CREATED, PIN_RESET, PIN_REVOKED, SESSION_EXPIRED, AUTHORITY_ACTION_APPROVED,
    AUTHORITY_ACTION_REJECTED, PERMISSION_DENIED, SUSPICIOUS_ACTIVITY) are deferred."""
    event = {
        "event_type": event_type,
        "user_id": user_id,
        "detail": detail,
        "timestamp": _utc_now(),
    }
    path = _security_log_path()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
