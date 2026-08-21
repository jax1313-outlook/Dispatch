"""Identity model — DISPATCH_PIN authentication (Authority role only).

Minimal first build against SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md (Claude-3 repo,
found in the Jules-3/Claude-2 doctrine-review repos) -- Authority role only, per
PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md (Claude-3 repo). PIN records are never stored in
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

from portal.models import get_data_dir, atomic_write_json

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
    """Strip pin_hash before returning a record to any caller outside this module."""
    return {k: v for k, v in record.items() if k != "pin_hash"}


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
        "failed_attempt_count": 0,
        "locked_until": None,
    }
    data[user_id] = record
    _save(data)
    _log_event("PIN_CHANGED", user_id, {"reason": "bootstrap"})
    return _public(record)


def _is_locked(record: dict) -> bool:
    locked_until = record.get("locked_until")
    if not locked_until:
        return False
    expiry = datetime.strptime(locked_until, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) < expiry


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

    if check_password_hash(record["pin_hash"], pin):
        record["failed_attempt_count"] = 0
        record["locked_until"] = None
        record["last_login_at"] = _utc_now()
        record["updated_at"] = _utc_now()
        _save(data)
        _log_event("LOGIN_SUCCESS", user_id, {})
        return _public(record)

    record["failed_attempt_count"] = record.get("failed_attempt_count", 0) + 1
    if record["failed_attempt_count"] >= MAX_FAILED_ATTEMPTS:
        record["locked_until"] = (
            datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
    record["updated_at"] = _utc_now()
    _save(data)
    _log_event(
        "LOGIN_FAILURE", user_id,
        {"reason": "bad_pin", "failed_attempt_count": record["failed_attempt_count"]},
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
