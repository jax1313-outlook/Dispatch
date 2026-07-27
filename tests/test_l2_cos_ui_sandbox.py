"""Tests for Publisher Alerts & Sandbox Tracking (l2_cos/ui/sandbox.py)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from l2_cos.ui import sandbox


def _entry(minutes_ago: float) -> sandbox.SandboxEntry:
    entered_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return sandbox.SandboxEntry(load_id="L-1", entered_at=entered_at, sent=True)


def test_expires_at_is_entered_at_plus_hold_hours():
    entry = _entry(0)
    delta = sandbox.expires_at(entry) - entry.entered_at
    assert delta == timedelta(hours=sandbox.SANDBOX_HOLD_HOURS)


def test_status_active_when_far_from_expiry():
    entry = _entry(minutes_ago=10)
    assert sandbox.status(entry) == sandbox.ACTIVE


def test_status_expiring_soon_within_window():
    entry = _entry(minutes_ago=sandbox.SANDBOX_HOLD_HOURS * 60 - sandbox.EXPIRING_SOON_MINUTES + 1)
    assert sandbox.status(entry) == sandbox.EXPIRING_SOON


def test_status_expired_past_hold():
    entry = _entry(minutes_ago=sandbox.SANDBOX_HOLD_HOURS * 60 + 5)
    assert sandbox.status(entry) == sandbox.EXPIRED


def test_time_remaining_uses_explicit_now():
    entry = _entry(minutes_ago=0)
    later = datetime.now(timezone.utc) + timedelta(hours=sandbox.SANDBOX_HOLD_HOURS, minutes=1)
    assert sandbox.time_remaining(entry, now=later).total_seconds() < 0


def test_build_entry_from_publisher_result():
    result = {
        "load_id": "L-9",
        "entered_at": datetime.now(timezone.utc).isoformat(),
        "sent": True,
    }
    entry = sandbox.build_entry(result)
    assert entry is not None
    assert entry.load_id == "L-9"
    assert entry.sent is True


def test_build_entry_returns_none_without_entered_at():
    assert sandbox.build_entry({"load_id": "L-9", "sent": True}) is None


def test_build_entry_returns_none_without_load_id():
    assert sandbox.build_entry({"entered_at": datetime.now(timezone.utc).isoformat()}) is None
