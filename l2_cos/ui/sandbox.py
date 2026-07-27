"""Publisher Alerts & Sandbox Tracking.

ASSUMPTION: this hold-period concept was not part of the four System Rules
established earlier in this project — it's introduced here per this task's
request. Once the publisher/auto-contact workflow evaluates a load (sent or
declined), it is treated as entering a fixed-length "sandbox" hold —
SANDBOX_HOLD_HOURS, defaulting to the requested ~3 hours — before dispatch
should re-check or escalate it. This module only tracks and flags that
hold; it never changes publisher.trigger()'s send/decline decision.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

SANDBOX_HOLD_HOURS = 3
EXPIRING_SOON_MINUTES = 30

ACTIVE = "active"
EXPIRING_SOON = "expiring_soon"
EXPIRED = "expired"


class SandboxEntry(BaseModel):
    load_id: str
    entered_at: datetime
    sent: bool
    reason: str | None = None


def expires_at(entry: SandboxEntry) -> datetime:
    return entry.entered_at + timedelta(hours=SANDBOX_HOLD_HOURS)


def time_remaining(entry: SandboxEntry, now: datetime | None = None) -> timedelta:
    now = now or datetime.now(timezone.utc)
    return expires_at(entry) - now


def status(entry: SandboxEntry, now: datetime | None = None) -> str:
    remaining = time_remaining(entry, now)
    if remaining.total_seconds() <= 0:
        return EXPIRED
    if remaining <= timedelta(minutes=EXPIRING_SOON_MINUTES):
        return EXPIRING_SOON
    return ACTIVE


def build_entry(publisher_result: dict) -> SandboxEntry | None:
    """Build a SandboxEntry from a persisted Archive/Publisher/<id>.json
    record, or None if it predates entered_at being recorded."""
    entered_at = publisher_result.get("entered_at")
    load_id = publisher_result.get("load_id")
    if not entered_at or not load_id:
        return None
    return SandboxEntry(
        load_id=load_id,
        entered_at=entered_at,
        sent=publisher_result.get("sent", False),
        reason=publisher_result.get("reason"),
    )
