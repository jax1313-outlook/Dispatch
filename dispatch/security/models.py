"""Canonical data models for Dispatch Security Foundation.

Mirrors dispatch/models.py's dataclass + validation + serialization
style, reusing its _gen_id/_utc_now/_validate_choice helpers rather
than duplicating them. Field names follow
docs/SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md Sections 2-5, 16.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from dispatch.models import _gen_id, _utc_now, _validate_choice

ROLES = ["Authority", "Driver", "External Viewer", "System Service"]

USER_STATUSES = ["active", "inactive", "locked"]

PIN_STATUSES = ["active", "revoked"]

SESSION_STATUSES = ["active", "expired", "revoked"]

SECURITY_EVENT_TYPES = [
    "LOGIN_SUCCESS",
    "LOGIN_FAILURE",
    "PIN_CREATED",
    "PIN_CHANGED",
    "PIN_RESET",
    "PIN_REVOKED",
    "SESSION_CREATED",
    "SESSION_EXPIRED",
    "PERMISSION_DENIED",
]

# Role -> permission set, per Security Spec Section 6. A static lookup in
# code, not a stored per-user column, mirroring dispatch/spine/state.py's
# ALLOWED_TRANSITIONS -- this build assigns permissions by role, not
# individually.
ROLE_PERMISSIONS = {
    "Authority": {
        "view_portal", "view_internal_card", "approve_draft", "approve_packet",
        "approve_library_promotion", "approve_archive_action",
        "approve_load_pursuit", "approve_deployment", "approve_doctrine_change",
        "approve_architecture_change", "view_settings",
    },
    "Driver": {
        "view_portal", "view_driver_assignment", "upload_driver_document",
    },
    "External Viewer": {
        "view_external_status",
    },
    "System Service": {
        "view_portal",
    },
}


def permissions_for_role(role: str) -> set:
    return set(ROLE_PERMISSIONS.get(role, ()))


@dataclass
class User:
    user_id: str = ""
    display_name: str = ""
    role: str = "Authority"
    status: str = "active"
    pin_record_id: str | None = None
    created_at: str = ""
    updated_at: str = ""
    last_login_at: str | None = None

    def __post_init__(self) -> None:
        if not self.user_id:
            self.user_id = _gen_id("USER")
        now = _utc_now()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        _validate_choice(self.role, ROLES, "role")
        _validate_choice(self.status, USER_STATUSES, "status")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PinRecord:
    pin_record_id: str = ""
    user_id: str = ""
    pin_hash: str = ""
    salt: str = ""
    status: str = "active"
    reset_required: bool = False
    failed_attempt_count: int = 0
    locked_until: str | None = None
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.pin_record_id:
            self.pin_record_id = _gen_id("PIN")
        now = _utc_now()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        _validate_choice(self.status, PIN_STATUSES, "status")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Session:
    session_id: str = ""
    user_id: str = ""
    role: str = ""
    started_at: str = ""
    last_active_at: str = ""
    status: str = "active"
    authentication_method: str = "DISPATCH_PIN"

    def __post_init__(self) -> None:
        if not self.session_id:
            self.session_id = _gen_id("SESS")
        now = _utc_now()
        if not self.started_at:
            self.started_at = now
        if not self.last_active_at:
            self.last_active_at = now
        _validate_choice(self.role, ROLES, "role")
        _validate_choice(self.status, SESSION_STATUSES, "status")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SecurityEvent:
    event_id: str = ""
    event_type: str = ""
    user_id: str | None = None
    timestamp: str = ""
    details: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = _gen_id("SECEV")
        if not self.timestamp:
            self.timestamp = _utc_now()
        _validate_choice(self.event_type, SECURITY_EVENT_TYPES, "event_type")

    def to_dict(self) -> dict:
        return asdict(self)
