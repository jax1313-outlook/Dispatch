"""Driver PIN Registry — a Library-managed asset (Mike's explicit decision
exercising the option `portal/models/identity.py` left conditional: "PIN
records are never stored in Library here -- the specification makes that
storage choice conditional on Mike's decision (Section 11), not a
default". This module is that decision, made for the Driver role only --
Authority's own PIN registry (identity.py) is untouched and still lives
outside Library).

Storage lives under `get_memory_dir()` -- the same root `library.json`
uses -- so a Driver PIN Card is literally a Library asset on disk, not
just administratively presented as one. It gets its own file
(`driver_pin_registry.json`) rather than folding into `library.py`'s
generic `add_record()`/section schema, for the same reason identity.py
gave for keeping Authority's PIN out of Library's generic schema in the
first place: Library's record shape (name/content/metadata/status) has
no credential concept, and a PIN hash is not a "record" -- retrofitting
one to hold the other would either weaken the credential schema or
bloat the document schema. Keeping it a sibling module lets the Driver
PIN Card model be exactly as strict as Authority's (hashed PIN, hashed
recovery word, lockout) while still living inside Library's data root.

One card per Driver, linked by `driver_id` to the existing
`dispatch/store.py` drivers table -- the driver's name/phone/license
stay on that record as the single source of truth; this module never
duplicates them. Login is Phone Number + PIN: the phone number is
looked up live from the driver record at login time (dispatch/
store.get_driver_by_phone), not copied here, so there is exactly one
place a phone number can go stale.

Explicitly out of scope, per the "no enterprise identity management, no
complex role frameworks" instruction: no self-registration (only Mike
creates a card, mirroring identity.bootstrap_authority's single-creator
model), no multi-factor beyond PIN + a single recovery word, no
per-permission role grants -- a Driver PIN Card grants exactly one
thing, Driver Portal access, on or off (`status`).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from portal.models import get_data_dir, get_memory_dir, atomic_write_json

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

STATUSES = ["active", "inactive"]


class DriverPinError(ValueError):
    """Raised for Driver PIN Registry operations that violate the model (duplicate card,
    unknown driver, driver has no phone on file, PIN/recovery word too short, unknown status)."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _registry_path() -> Path:
    d = get_memory_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "driver_pin_registry.json"


def _load() -> dict:
    path = _registry_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save(data: dict) -> None:
    path = _registry_path()
    atomic_write_json(path, data)


def _public(record: dict) -> dict:
    """Strip pin_hash and recovery_word_hash before returning a record to any caller
    outside this module -- mirrors identity.py's _public()."""
    return {k: v for k, v in record.items() if k not in ("pin_hash", "recovery_word_hash")}


def _is_locked(record: dict) -> bool:
    locked_until = record.get("locked_until")
    if not locked_until:
        return False
    expiry = datetime.strptime(locked_until, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) < expiry


# ── CRUD ──────────────────────────────────────────────────────────────


def get_pin_card(driver_id: str) -> dict | None:
    rec = _load().get(driver_id)
    return _public(rec) if rec else None


def list_pin_cards() -> list[dict]:
    return [_public(rec) for rec in _load().values()]


def create_pin_card(driver_id: str, pin: str, recovery_word: str, created_by: str) -> dict:
    """Issue a new Driver PIN Card. Route-layer responsibility (not enforced here, same
    split identity.py uses) is to only expose this behind the Authority PIN gate -- there
    is no self-registration path."""
    from dispatch import store as dispatch_store

    driver = dispatch_store.get_driver(driver_id)
    if not driver:
        raise DriverPinError(f"Unknown driver: {driver_id}")
    if not driver.get("phone"):
        raise DriverPinError(
            "Driver has no phone number on file -- Driver Portal login is phone + PIN, "
            "so a phone number is required before a PIN card can be issued."
        )
    if driver_id in _load():
        raise DriverPinError(f"Driver {driver_id} already has a PIN card.")
    if not pin or len(pin) < 4:
        raise DriverPinError("PIN must be at least 4 characters.")
    if not recovery_word or len(recovery_word) < 3:
        raise DriverPinError("Recovery word must be at least 3 characters.")

    now = _utc_now()
    record = {
        "driver_id": driver_id,
        "status": "active",
        "pin_hash": generate_password_hash(pin),
        "recovery_word_hash": generate_password_hash(recovery_word.strip().lower()),
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
        "last_login_at": None,
        "failed_attempt_count": 0,
        "locked_until": None,
    }
    data = _load()
    data[driver_id] = record
    _save(data)
    _log_event("DRIVER_PIN_CREATED", driver_id, {"created_by": created_by})
    return _public(record)


def reset_pin(driver_id: str, new_pin: str, reset_by: str) -> dict:
    """Mike-initiated PIN reset (no recovery word needed -- Mike is Authority). Also
    clears any lockout, since a fresh PIN from Mike should not stay locked out."""
    if not new_pin or len(new_pin) < 4:
        raise DriverPinError("PIN must be at least 4 characters.")
    data = _load()
    record = data.get(driver_id)
    if not record:
        raise DriverPinError(f"No PIN card for driver: {driver_id}")
    record["pin_hash"] = generate_password_hash(new_pin)
    record["failed_attempt_count"] = 0
    record["locked_until"] = None
    record["updated_at"] = _utc_now()
    _save(data)
    _log_event("DRIVER_PIN_CHANGED", driver_id, {"reason": "authority_reset", "reset_by": reset_by})
    return _public(record)


def set_recovery_word(driver_id: str, recovery_word: str, set_by: str) -> dict:
    if not recovery_word or len(recovery_word) < 3:
        raise DriverPinError("Recovery word must be at least 3 characters.")
    data = _load()
    record = data.get(driver_id)
    if not record:
        raise DriverPinError(f"No PIN card for driver: {driver_id}")
    record["recovery_word_hash"] = generate_password_hash(recovery_word.strip().lower())
    record["updated_at"] = _utc_now()
    _save(data)
    _log_event("DRIVER_RECOVERY_WORD_CHANGED", driver_id, {"set_by": set_by})
    return _public(record)


def set_status(driver_id: str, status: str, changed_by: str) -> dict:
    """Active/Inactive control (independent of the driver's own roster `status` on
    dispatch/store.py's drivers table -- this one controls Driver Portal access only;
    Mike may suspend portal access without touching the driver's employment status, or
    vice versa)."""
    if status not in STATUSES:
        raise DriverPinError(f"Invalid status: {status!r}. Must be one of {STATUSES}.")
    data = _load()
    record = data.get(driver_id)
    if not record:
        raise DriverPinError(f"No PIN card for driver: {driver_id}")
    record["status"] = status
    record["updated_at"] = _utc_now()
    _save(data)
    _log_event("DRIVER_STATUS_CHANGED", driver_id, {"status": status, "changed_by": changed_by})
    return _public(record)


def delete_pin_card(driver_id: str, deleted_by: str) -> bool:
    data = _load()
    if driver_id not in data:
        return False
    del data[driver_id]
    _save(data)
    _log_event("DRIVER_PIN_DELETED", driver_id, {"deleted_by": deleted_by})
    return True


# ── Driver Portal authentication (Phone Number + PIN) ───────────────


def verify_login(phone: str, pin: str) -> dict | None:
    """Validate phone + PIN. Returns the public PIN card record (plus the matched
    driver_id) on success, None on failure. Phone is looked up live against the
    driver record, never stored here -- see module docstring."""
    from dispatch import store as dispatch_store

    phone = (phone or "").strip()
    if not phone:
        return None
    driver = dispatch_store.get_driver_by_phone(phone)
    if not driver:
        _log_event("DRIVER_LOGIN_FAILURE", phone, {"reason": "unknown_phone"})
        return None

    data = _load()
    record = data.get(driver["driver_id"])
    if not record or record.get("status") != "active":
        _log_event("DRIVER_LOGIN_FAILURE", driver["driver_id"], {"reason": "no_card_or_inactive"})
        return None

    if _is_locked(record):
        _log_event("DRIVER_LOGIN_FAILURE", driver["driver_id"], {"reason": "locked"})
        return None

    if check_password_hash(record["pin_hash"], pin or ""):
        record["failed_attempt_count"] = 0
        record["locked_until"] = None
        record["last_login_at"] = _utc_now()
        record["updated_at"] = _utc_now()
        _save(data)
        _log_event("DRIVER_LOGIN_SUCCESS", driver["driver_id"], {})
        return _public(record)

    record["failed_attempt_count"] = record.get("failed_attempt_count", 0) + 1
    if record["failed_attempt_count"] >= MAX_FAILED_ATTEMPTS:
        record["locked_until"] = (
            datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
    record["updated_at"] = _utc_now()
    _save(data)
    _log_event(
        "DRIVER_LOGIN_FAILURE", driver["driver_id"],
        {"reason": "bad_pin", "failed_attempt_count": record["failed_attempt_count"]},
    )
    return None


# ── Recovery Word self-service reset ────────────────────────────────


def verify_recovery_word(phone: str, recovery_word: str) -> dict | None:
    """Check a recovery word against the card matched by phone. Requires an active
    card, same as verify_login -- a deactivated card cannot self-recover either."""
    from dispatch import store as dispatch_store

    phone = (phone or "").strip()
    if not phone or not recovery_word:
        return None
    driver = dispatch_store.get_driver_by_phone(phone)
    if not driver:
        return None
    record = _load().get(driver["driver_id"])
    if not record or record.get("status") != "active":
        return None
    if check_password_hash(record["recovery_word_hash"], recovery_word.strip().lower()):
        return _public(record)
    return None


def reset_pin_with_recovery_word(phone: str, recovery_word: str, new_pin: str) -> dict | None:
    """Self-service PIN reset: recovery word stands in for the (forgotten) old PIN.
    Returns the updated public record on success, None if the recovery word didn't
    match (deliberately the same None-on-failure shape as verify_login -- callers
    should not be able to distinguish "wrong recovery word" from "unknown phone")."""
    matched = verify_recovery_word(phone, recovery_word)
    if not matched:
        return None
    if not new_pin or len(new_pin) < 4:
        raise DriverPinError("PIN must be at least 4 characters.")

    driver_id = matched["driver_id"]
    data = _load()
    record = data[driver_id]
    record["pin_hash"] = generate_password_hash(new_pin)
    record["failed_attempt_count"] = 0
    record["locked_until"] = None
    record["updated_at"] = _utc_now()
    _save(data)
    _log_event("DRIVER_PIN_CHANGED", driver_id, {"reason": "self_service_recovery_word"})
    return _public(record)


# ── Security log (shared file with Authority's identity.py, distinguished by
#    event-type prefix, so there is one audit trail to look at, not two) ──────


def _security_log_path() -> Path:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "security_events.jsonl"


def _log_event(event_type: str, subject_id: str, detail: dict) -> None:
    event = {
        "event_type": event_type,
        "user_id": subject_id,
        "detail": detail,
        "timestamp": _utc_now(),
    }
    path = _security_log_path()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
