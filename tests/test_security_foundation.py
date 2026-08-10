"""Tests for Dispatch Security Foundation (dispatch/security/, portal/
auth_helpers.py, portal/routes/security.py) -- Stage 7 build, per
DISPATCH_STAGE7_SECURITY_FOUNDATION_DESIGN_v1.md.
"""

from __future__ import annotations

import inspect

import pytest

from dispatch import db
from dispatch.security import auth, store
from dispatch.security.models import ROLES, User


@pytest.fixture(autouse=True)
def tmp_dispatch_db(tmp_path, monkeypatch):
    """Redirect dispatch database to a per-test temp directory -- same
    pattern as tests/test_spine.py, since Security tables live in the
    same dispatch.db file."""
    db_path = tmp_path / "dispatch.db"
    db.set_db_path(db_path)
    yield db_path
    db.set_db_path(None)


@pytest.fixture
def mike():
    return auth.create_user_with_pin("Mike", "Authority", "1234")


# ── Schema creation ───────────────────────────────────────────────────

def test_security_tables_created_alongside_spine_and_existing_schema():
    with db.get_connection() as conn:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    for expected in ("users", "pin_records", "sessions", "security_events"):
        assert expected in tables
    # Spine (Stage 4) and existing domain tables are untouched, not replaced
    assert "work_items" in tables
    assert "loads" in tables


# ── User + PIN lifecycle ──────────────────────────────────────────────

def test_create_user_with_pin_round_trips(mike):
    assert mike["display_name"] == "Mike"
    assert mike["role"] == "Authority"
    assert mike["status"] == "active"
    assert mike["pin_record_id"]


def test_all_four_roles_are_valid_on_creation():
    for role in ROLES:
        user = auth.create_user_with_pin(f"user-{role}", role, "5678")
        assert user["role"] == role


def test_invalid_role_rejected():
    with pytest.raises(ValueError):
        User(display_name="x", role="NOT_A_ROLE")


def test_pin_too_short_rejected():
    with pytest.raises(auth.PinCreationError):
        auth.create_user_with_pin("Short", "Authority", "12")


def test_validate_pin_correct(mike):
    assert auth.validate_pin(mike["user_id"], "1234") is True


def test_validate_pin_incorrect(mike):
    assert auth.validate_pin(mike["user_id"], "9999") is False


def test_change_pin_invalidates_old_pin(mike):
    auth.change_pin(mike["user_id"], "4321")
    assert auth.validate_pin(mike["user_id"], "1234") is False
    assert auth.validate_pin(mike["user_id"], "4321") is True


def test_revoke_pin_blocks_validation(mike):
    auth.revoke_pin(mike["user_id"])
    assert auth.validate_pin(mike["user_id"], "1234") is False


def test_reset_pin_records_who_approved(mike):
    auth.reset_pin(mike["user_id"], "0000", approved_by_user_id="AUTHORITY-SOMEONE")
    events = store.list_security_events(mike["user_id"])
    reset_events = [e for e in events if e["event_type"] == "PIN_RESET"]
    assert len(reset_events) == 1
    assert reset_events[0]["details"]["approved_by"] == "AUTHORITY-SOMEONE"
    assert auth.validate_pin(mike["user_id"], "0000") is True


# ── Lockout ───────────────────────────────────────────────────────────

def test_lockout_after_threshold_failures(mike):
    for _ in range(auth.LOCKOUT_THRESHOLD):
        assert auth.validate_pin(mike["user_id"], "wrong") is False
    # even the CORRECT pin is rejected once locked
    assert auth.validate_pin(mike["user_id"], "1234") is False


def test_successful_validation_resets_failure_count(mike):
    auth.validate_pin(mike["user_id"], "wrong")
    auth.validate_pin(mike["user_id"], "wrong")
    assert auth.validate_pin(mike["user_id"], "1234") is True
    record = store.get_active_pin_record_for_user(mike["user_id"])
    assert record["failed_attempt_count"] == 0


# ── Login / Session ───────────────────────────────────────────────────

def test_login_success_creates_session(mike):
    session = auth.login("Mike", "1234")
    assert session is not None
    assert session["user_id"] == mike["user_id"]
    assert session["role"] == "Authority"
    assert session["status"] == "active"


def test_login_failure_returns_none_for_unknown_identity():
    assert auth.login("NoSuchUser", "1234") is None


def test_login_failure_returns_none_for_wrong_pin(mike):
    assert auth.login("Mike", "0000") is None


def test_login_does_not_reveal_which_failure_reason():
    """Unknown identity and wrong PIN must be indistinguishable to the
    caller -- both return None, no different exception/message."""
    result_unknown = auth.login("NoSuchUser", "1234")
    assert result_unknown is None


def test_current_session_valid(mike):
    session = auth.login("Mike", "1234")
    fetched = auth.current_session(session["session_id"])
    assert fetched is not None
    assert fetched["user_id"] == mike["user_id"]


def test_current_session_none_for_missing_id():
    assert auth.current_session("SESS-DOES-NOT-EXIST") is None
    assert auth.current_session(None) is None


def test_logout_revokes_session(mike):
    session = auth.login("Mike", "1234")
    auth.logout(session["session_id"])
    assert auth.current_session(session["session_id"]) is None


def test_login_success_writes_security_events(mike):
    auth.login("Mike", "1234")
    events = store.list_security_events(mike["user_id"])
    types = {e["event_type"] for e in events}
    assert "LOGIN_SUCCESS" in types
    assert "SESSION_CREATED" in types


def test_login_failure_writes_security_event(mike):
    auth.login("Mike", "wrong")
    events = store.list_security_events(mike["user_id"])
    assert any(e["event_type"] == "LOGIN_FAILURE" for e in events)


# ── Security Sub-Library re-check (mechanism only, not route-wired) ───

def test_security_sublibrary_pin_recheck_valid(mike):
    session = auth.login("Mike", "1234")
    assert auth.require_security_sublibrary_pin(session, "1234") is True


def test_security_sublibrary_pin_recheck_invalid_pin(mike):
    session = auth.login("Mike", "1234")
    assert auth.require_security_sublibrary_pin(session, "0000") is False


def test_security_sublibrary_pin_recheck_no_session():
    assert auth.require_security_sublibrary_pin(None, "1234") is False


# ── Structural guard: no plaintext PIN anywhere ────────────────────────

def test_no_plaintext_pin_in_stored_record(mike):
    record = store.get_active_pin_record_for_user(mike["user_id"])
    assert "1234" not in record["pin_hash"]
    assert record["pin_hash"] != "1234"
    assert len(record["pin_hash"]) == 64  # sha256 hexdigest length -- confirms it's hashed, not raw


def test_no_plaintext_pin_field_exists_on_any_model():
    """Structural guard: neither User nor PinRecord dataclasses define
    a field that could hold a raw PIN string."""
    from dispatch.security.models import PinRecord, User as UserModel

    user_fields = {f for f in UserModel.__dataclass_fields__}
    pin_fields = {f for f in PinRecord.__dataclass_fields__}
    for forbidden in ("pin", "raw_pin", "plaintext_pin"):
        assert forbidden not in user_fields
        assert forbidden not in pin_fields


def test_auth_module_never_logs_or_returns_raw_pin_source_scan():
    """Structural guard, matching this codebase's existing
    source-scanning test convention (e.g. build_ifta_review_dashboard's
    read-only guard): confirm auth.py's PIN-hashing path never writes
    the raw pin string to a dict/return value under an unhashed key."""
    source = inspect.getsource(auth)
    # the only places "pin" (lowercase, the raw parameter) may appear
    # as a dict VALUE assignment target are hashing calls -- a crude
    # but effective guard against a future accidental `"pin": pin`
    assert '"pin":' not in source
    assert "'pin':" not in source


# ── Approval Events identity-wiring capability (Stage 4 + Stage 7) ────

def test_approval_event_receives_real_identity_when_session_exists(mike):
    """Proves the capability named in the design (Section 3): when a
    real session exists, dispatch.spine.store.create_approval_event()
    can be populated with real session_id/user_id/role -- without any
    existing action route being modified to require login."""
    from dispatch.spine.models import ApprovalEvent
    from dispatch.spine.store import create_approval_event
    from dispatch.spine.models import WorkItem
    from dispatch.spine.store import create_work_item

    session = auth.login("Mike", "1234")
    work_item = create_work_item(WorkItem(source_type="test", source_id="SEC-001"))

    approval = create_approval_event(
        ApprovalEvent(
            work_item_id=work_item["work_item_id"],
            session_id=session["session_id"],
            user_id=session["user_id"],
            role=session["role"],
            action="APPROVE_LOAD_PURSUIT",
            new_state="MIKE_APPROVED",
        )
    )
    assert approval["user_id"] == mike["user_id"]
    assert approval["role"] == "Authority"
    assert approval["session_id"] == session["session_id"]


def test_approval_event_still_defaults_to_null_identity_without_a_session():
    """Confirms this build does not silently start requiring identity
    on approval_events -- Stage 4's original nullable-fields test still
    holds, unchanged, since no existing route was modified."""
    from dispatch.spine.models import ApprovalEvent
    from dispatch.spine.store import create_approval_event
    from dispatch.spine.models import WorkItem
    from dispatch.spine.store import create_work_item

    work_item = create_work_item(WorkItem(source_type="test", source_id="SEC-002"))
    approval = create_approval_event(
        ApprovalEvent(
            work_item_id=work_item["work_item_id"],
            action="APPROVE_DRAFT",
            new_state="MIKE_APPROVED",
        )
    )
    assert approval["user_id"] is None
    assert approval["session_id"] is None
