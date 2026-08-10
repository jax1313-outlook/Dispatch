"""Dispatch Security Foundation -- PIN hashing, login/logout, lockout.

See DISPATCH_STAGE7_SECURITY_FOUNDATION_DESIGN_v1.md Sections 4-6 for
the approved design this implements. PIN credential hashing is
deliberately distinct from cin_lite/archive.py's file-integrity
SHA-256 use -- a fast hash is correct for detecting tampering, wrong
for a short, low-entropy PIN, which needs a slow, salted hash.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

from dispatch.models import _utc_now
from dispatch.security import store
from dispatch.security.models import PinRecord, SecurityEvent, Session, User

PBKDF2_ITERATIONS = 600_000
LOCKOUT_THRESHOLD = 5
LOCKOUT_MINUTES = 15


class PinCreationError(ValueError):
    """Raised when a PIN fails basic shape validation (e.g. too short)."""


def _generate_salt() -> bytes:
    return os.urandom(16)


def _hash_pin(pin: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, PBKDF2_ITERATIONS).hex()


def _lockout_expiry() -> str:
    expiry = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
    return expiry.strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_locked(pin_record: dict) -> bool:
    locked_until = pin_record.get("locked_until")
    if not locked_until:
        return False
    return locked_until > _utc_now()


def _validate_pin_shape(pin: str) -> None:
    if not pin or not pin.isdigit() or len(pin) < 4:
        raise PinCreationError("PIN must be at least 4 digits")


# ── User + PIN lifecycle ─────────────────────────────────────────────

def create_user_with_pin(display_name: str, role: str, pin: str) -> dict:
    """Creates a new Identity and its initial PIN together -- every
    user has exactly one managed PIN (Security Spec Sections 4.1-4.2).
    """
    _validate_pin_shape(pin)
    user = store.create_user(User(display_name=display_name, role=role))
    salt = _generate_salt()
    pin_hash = _hash_pin(pin, salt)
    record = store.create_pin_record(
        PinRecord(user_id=user["user_id"], pin_hash=pin_hash, salt=salt.hex())
    )
    store.update_user(user["user_id"], pin_record_id=record["pin_record_id"])
    store.create_security_event(SecurityEvent(event_type="PIN_CREATED", user_id=user["user_id"]))
    return store.get_user(user["user_id"])


def change_pin(user_id: str, new_pin: str) -> dict:
    """User-initiated PIN change (Security Spec Section 4.4)."""
    _validate_pin_shape(new_pin)
    existing = store.get_active_pin_record_for_user(user_id)
    salt = _generate_salt()
    pin_hash = _hash_pin(new_pin, salt)
    if existing:
        updated = store.update_pin_record(
            existing["pin_record_id"],
            pin_hash=pin_hash,
            salt=salt.hex(),
            failed_attempt_count=0,
            locked_until=None,
            reset_required=False,
        )
    else:
        updated = store.create_pin_record(
            PinRecord(user_id=user_id, pin_hash=pin_hash, salt=salt.hex())
        )
        store.update_user(user_id, pin_record_id=updated["pin_record_id"])
    store.create_security_event(SecurityEvent(event_type="PIN_CHANGED", user_id=user_id))
    return updated


def reset_pin(user_id: str, new_pin: str, *, approved_by_user_id: str) -> dict:
    """PIN reset requires Authority approval (Security Spec Section
    4.5). The caller is responsible for confirming
    `approved_by_user_id` actually carries the Authority role before
    calling this -- this function records who approved it, it does not
    itself check the approver's role (no route calls this in this
    build; provided for a future Portal reset workflow).
    """
    updated = change_pin(user_id, new_pin)
    store.create_security_event(
        SecurityEvent(
            event_type="PIN_RESET",
            user_id=user_id,
            details={"approved_by": approved_by_user_id},
        )
    )
    return updated


def revoke_pin(user_id: str) -> dict | None:
    existing = store.get_active_pin_record_for_user(user_id)
    if not existing:
        return None
    updated = store.update_pin_record(existing["pin_record_id"], status="revoked")
    store.create_security_event(SecurityEvent(event_type="PIN_REVOKED", user_id=user_id))
    return updated


def validate_pin(user_id: str, pin: str) -> bool:
    """Validates a PIN against the user's active PIN record, tracking
    failed attempts and locking out after LOCKOUT_THRESHOLD consecutive
    failures. A revoked or locked PIN record never validates, even with
    the correct PIN.
    """
    record = store.get_active_pin_record_for_user(user_id)
    if record is None:
        return False
    if _is_locked(record):
        return False
    salt = bytes.fromhex(record["salt"])
    candidate_hash = _hash_pin(pin, salt)
    valid = hmac.compare_digest(candidate_hash, record["pin_hash"])
    if valid:
        store.reset_pin_failures(record["pin_record_id"])
    else:
        new_count = record["failed_attempt_count"] + 1
        lock_until = _lockout_expiry() if new_count >= LOCKOUT_THRESHOLD else None
        store.record_pin_failure(record["pin_record_id"], lock_until=lock_until)
    return valid


# ── Login / Session ──────────────────────────────────────────────────

def login(display_name: str, pin: str) -> dict | None:
    """Returns a new Session dict on success, None on any failure.
    Deliberately does not distinguish "unknown identity" from "wrong
    PIN" in its return value, so a caller can't use the response to
    enumerate valid identities (Security Spec's login flow, Section 4.3).
    """
    user = store.get_user_by_display_name(display_name)
    if user is None or user["status"] != "active":
        store.create_security_event(
            SecurityEvent(event_type="LOGIN_FAILURE", details={"display_name": display_name})
        )
        return None
    if not validate_pin(user["user_id"], pin):
        store.create_security_event(
            SecurityEvent(event_type="LOGIN_FAILURE", user_id=user["user_id"])
        )
        return None
    session = store.create_session(Session(user_id=user["user_id"], role=user["role"]))
    store.update_user(user["user_id"], last_login_at=_utc_now())
    store.create_security_event(SecurityEvent(event_type="LOGIN_SUCCESS", user_id=user["user_id"]))
    store.create_security_event(
        SecurityEvent(
            event_type="SESSION_CREATED",
            user_id=user["user_id"],
            details={"session_id": session["session_id"]},
        )
    )
    return session


def logout(session_id: str) -> None:
    store.revoke_session(session_id)


def current_session(session_id: str | None) -> dict | None:
    """Loads and validates a session by ID. Returns None if missing,
    revoked, or otherwise not active. This build has no configured
    session lifetime/expiry window -- `status == 'active'` is
    sufficient; a time-based expiry is a Portal-Wide Enforcement-era
    refinement, not required for this build's narrow scope (Section 1).
    """
    if not session_id:
        return None
    session = store.get_session(session_id)
    if session is None or session["status"] != "active":
        return None
    store.touch_session(session_id)
    return session


# ── Security Sub-Library (mechanism only, per design Section 4.5) ──

def require_security_sublibrary_pin(session: dict | None, pin: str) -> bool:
    """The Security Sub-Library's separate PIN re-check
    (LIBRARY_INGESTION_RULE.md Section 6): re-validates a PIN at the
    moment of access, distinct from the general login check above, but
    reusing the same validate_pin() function and pin_records table --
    one PIN system, a second trigger point, not a second PIN system.

    Not called from any route in this build -- there is no "security"
    Library section to protect until Stage 9's Library `origin` field
    lands. Provided and tested now so that future work has a ready
    mechanism instead of needing to invent one.
    """
    if session is None:
        return False
    return validate_pin(session["user_id"], pin)
