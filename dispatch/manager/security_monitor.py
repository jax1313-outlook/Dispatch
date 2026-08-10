"""Security event pattern detection for Manager -- Stage 12 Phase M6.

Read-only: the only dispatch.security call anywhere in this module is
list_security_events(). No PIN, session, or role write function is
ever called here -- confirmed by a structural guard test matching
tests/test_security_foundation.py's own no-write convention.

A "pattern" is an aggregation over multiple SecurityEvent rows, not a
single persisted record, so it doesn't fit signals.py's one-record-
one-signal shape -- kept as its own module per
DISPATCH_STAGE12_MANAGER_M4_M6_BUILD_DESIGN_v1.md Section 2.

Grouping key for LOGIN_FAILURE: dispatch/security/auth.py's login()
writes two different shapes -- unknown identity (user_id=None,
details={"display_name": ...}) and known identity/wrong PIN
(user_id set, no display_name). These are deliberately NOT conflated
into one key even for the same real person: an unauthenticated-identity
attempt and an authenticated-wrong-PIN attempt are different risk
shapes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dispatch.security.store import list_security_events

SECURITY_PATTERN = "security_pattern"

_PATTERN_THRESHOLD = 3
_WINDOW_HOURS = 24


def _parse_ts(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _login_failure_key(event: dict) -> str:
    if event.get("user_id"):
        return f"user:{event['user_id']}"
    display_name = (event.get("details") or {}).get("display_name", "unknown")
    return f"identity:{display_name}"


def _permission_denied_key(event: dict) -> str:
    path = (event.get("details") or {}).get("path", "unknown")
    return f"{event.get('user_id', 'unknown')}:{path}"


_GROUPERS = {
    "LOGIN_FAILURE": _login_failure_key,
    "PERMISSION_DENIED": _permission_denied_key,
}


def detect_patterns() -> list[dict]:
    """Returns one raw signal per (event_type, key) pair whose count in
    the trailing window meets or exceeds the pattern threshold. Each
    signal's source_id is stable per calendar day, so an ongoing
    pattern doesn't re-materialize a duplicate Work Item within the
    same day, while a pattern continuing into a new day gets a fresh
    entry rather than staying permanently silent.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_WINDOW_HOURS)
    groups: dict[tuple[str, str], list[dict]] = {}

    for event in list_security_events():
        grouper = _GROUPERS.get(event["event_type"])
        if grouper is None:
            continue
        try:
            ts = _parse_ts(event["timestamp"])
        except (ValueError, TypeError):
            continue
        if ts < cutoff:
            continue
        key = grouper(event)
        groups.setdefault((event["event_type"], key), []).append(event)

    raw: list[dict] = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for (event_type, key), events in groups.items():
        if len(events) < _PATTERN_THRESHOLD:
            continue
        raw.append({
            "source_type": SECURITY_PATTERN,
            "source_id": f"{event_type}:{key}:{today}",
            "data": {
                "event_type": event_type,
                "key": key,
                "count": len(events),
                "window_hours": _WINDOW_HOURS,
            },
        })
    return raw
