"""Signed operational tokens with a real lifecycle — issue, verify, revoke, audit.

Replaces the previous design, which was a bare keyed digest:

    HMAC(secret, "dispatch-stakeholder:" + load_id)

That token carried no timestamp, no nonce and no version. The same string was
valid forever, could not be revoked, and the only way to invalidate one was to
rotate the global secret, which invalidated every other link at the same time.
A stakeholder link mailed to a broker in March still opened the load in
December, and nothing in the system could stop it.

Every token issued here carries, inside the signed payload:

    purpose     what the token may be used for (its scope)
    object_id   the single object it addresses
    issued_at   when it was minted
    expires_at  when it stops working, on its own
    nonce       so two tokens for the same object are distinguishable,
                which is what makes individual revocation possible at all

and is recorded in `operational_tokens` so it can be revoked by id, by object,
or by purpose, and so that issue/verify-failure/revoke leave an audit trail.

Fail-closed is the rule throughout: malformed, unknown-version, wrong-purpose,
wrong-object, expired, revoked and badly-signed tokens all return the same
kind of refusal, and refusal is the default on any path that is not an
explicit success.

THE OLD TOKENS. Legacy digests are rejected by default -- treating them as
valid forever is the defect this module exists to fix. A deployment that has
live links already in the wild can set DISPATCH_LEGACY_TOKENS_UNTIL to an ISO
date to keep accepting them until then; every such acceptance is recorded as
its own audit event with reason "legacy_grace". Past that date, or with the
variable unset, they fail like anything else. The grace window is deliberately
an explicit, expiring, audited decision rather than a silent compatibility
shim.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

_VERSION = "dt1"

# Defaults chosen for what each link is actually for. A stakeholder view is a
# courtesy to a broker on one load and has no reason to outlive the load's
# billing cycle; a decision link is answered in hours, not weeks.
DEFAULT_TTL_HOURS: dict[str, int] = {
    "stakeholder_view": 30 * 24,
    "load_decision": 14 * 24,
    "ifta_approval": 30 * 24,
}
_FALLBACK_TTL_HOURS = 7 * 24

_SCHEMA = """
CREATE TABLE IF NOT EXISTS operational_tokens (
    token_id     TEXT PRIMARY KEY,
    purpose      TEXT NOT NULL,
    object_id    TEXT NOT NULL,
    issued_at    TEXT NOT NULL,
    issued_by    TEXT NOT NULL DEFAULT '',
    expires_at   TEXT NOT NULL,
    revoked_at   TEXT,
    revoked_by   TEXT,
    revoke_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_operational_tokens_object
    ON operational_tokens(purpose, object_id);

CREATE TABLE IF NOT EXISTS token_audit (
    audit_id   TEXT PRIMARY KEY,
    token_id   TEXT NOT NULL DEFAULT '',
    purpose    TEXT NOT NULL DEFAULT '',
    object_id  TEXT NOT NULL DEFAULT '',
    event      TEXT NOT NULL,
    reason     TEXT NOT NULL DEFAULT '',
    actor      TEXT NOT NULL DEFAULT '',
    at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_token_audit_token ON token_audit(token_id);
"""


def init_token_schema(conn: sqlite3.Connection) -> None:
    """Called from dispatch.db._init_db, next to the Spine's own initializer --
    the same pattern, for the same reason: a subsystem owns its tables."""
    conn.executescript(_SCHEMA)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(stamp: str) -> datetime | None:
    try:
        return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _secret() -> bytes:
    """The signing key.

    portal/config.py::check_secrets refuses to start an operational deployment
    on the published default, so by the time anything issues a token the key is
    either real or the process never came up. The fallback stays only so the
    test suite and an explicitly-flagged development run work offline.
    """
    return os.environ.get("DISPATCH_EMAIL_SECRET", "dispatch-dev-secret").encode()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class TokenVerdict:
    """Why a token was accepted or refused.

    A bool would be enough for the routes, which all fail closed the same way.
    The reason exists for the audit trail and for the operator asking "why did
    the broker's link stop working" -- "expired 2026-09-01" and "revoked by
    mike" are different answers and the system should be able to tell them
    apart.
    """

    valid: bool
    reason: str = ""
    token_id: str = ""
    purpose: str = ""
    object_id: str = ""
    expires_at: str = ""

    def __bool__(self) -> bool:
        return self.valid


def _record(conn, *, token_id="", purpose="", object_id="", event, reason="", actor=""):
    conn.execute(
        "INSERT INTO token_audit (audit_id, token_id, purpose, object_id, event, reason, actor, at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (uuid.uuid4().hex, token_id, purpose, object_id, event, reason, actor, _iso(_utc_now())),
    )


def issue(
    purpose: str,
    object_id: str,
    *,
    ttl_hours: int | None = None,
    issued_by: str = "",
) -> str:
    """Mint a scoped, expiring token and record it so it can be revoked later."""
    from dispatch.db import get_connection

    if not purpose or not object_id:
        raise ValueError("A token needs both a purpose and an object to address.")

    now = _utc_now()
    hours = ttl_hours if ttl_hours is not None else DEFAULT_TTL_HOURS.get(purpose, _FALLBACK_TTL_HOURS)
    expires = now + timedelta(hours=hours)
    token_id = f"TOK-{uuid.uuid4().hex[:12].upper()}"

    payload = json.dumps(
        {
            "t": token_id,
            "p": purpose,
            "o": object_id,
            "i": _iso(now),
            "e": _iso(expires),
            "n": secrets.token_urlsafe(8),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    encoded = _b64(payload.encode())

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO operational_tokens (token_id, purpose, object_id, issued_at, issued_by, expires_at) "
            "VALUES (?,?,?,?,?,?)",
            (token_id, purpose, object_id, _iso(now), issued_by, _iso(expires)),
        )
        _record(conn, token_id=token_id, purpose=purpose, object_id=object_id,
                event="issued", actor=issued_by)

    return f"{_VERSION}.{encoded}.{_sign(encoded)}"


def _legacy_grace_open() -> bool:
    until = os.environ.get("DISPATCH_LEGACY_TOKENS_UNTIL", "").strip()
    if not until:
        return False
    try:
        deadline = datetime.strptime(until, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return _utc_now() <= deadline + timedelta(days=1)


def verify(purpose: str, object_id: str, token: str, *, legacy_digest: str | None = None) -> TokenVerdict:
    """Validate a token against the purpose and object it claims to address.

    Order matters: signature before payload, payload before database. A token
    whose signature does not check out is never looked up, so a forged token
    cannot be used to probe which object ids exist.
    """
    from dispatch.db import get_connection

    def refuse(reason: str, **extra) -> TokenVerdict:
        try:
            with get_connection() as conn:
                _record(conn, purpose=purpose, object_id=object_id,
                        event="verify_failed", reason=reason, **{k: v for k, v in extra.items()})
        except sqlite3.Error:
            # An audit write must never be the thing that lets a bad token
            # through, so a failure here is swallowed and the refusal stands.
            pass
        return TokenVerdict(False, reason)

    if not token:
        return refuse("missing")

    parts = token.split(".")
    if len(parts) != 3 or parts[0] != _VERSION:
        # Not one of ours. It may be a pre-lifecycle digest.
        if legacy_digest and hmac.compare_digest(legacy_digest, token):
            if not _legacy_grace_open():
                return refuse("legacy_token_rejected")
            try:
                with get_connection() as conn:
                    _record(conn, purpose=purpose, object_id=object_id,
                            event="verified", reason="legacy_grace")
            except sqlite3.Error:
                pass
            return TokenVerdict(True, "legacy_grace", purpose=purpose, object_id=object_id)
        return refuse("malformed")

    _, encoded, signature = parts
    if not hmac.compare_digest(_sign(encoded), signature):
        return refuse("bad_signature")

    try:
        claims = json.loads(_unb64(encoded).decode())
    except (ValueError, UnicodeDecodeError):
        return refuse("malformed_payload")

    token_id = claims.get("t", "")
    if claims.get("p") != purpose:
        return refuse("wrong_purpose", token_id=token_id)
    if claims.get("o") != object_id:
        return refuse("wrong_object", token_id=token_id)

    expires = _parse(claims.get("e", ""))
    if expires is None:
        return refuse("malformed_expiry", token_id=token_id)
    if _utc_now() > expires:
        return refuse("expired", token_id=token_id)

    with get_connection() as conn:
        row = conn.execute(
            "SELECT revoked_at FROM operational_tokens WHERE token_id=?", (token_id,)
        ).fetchone()
        if row is None:
            # Correctly signed but unknown to the ledger. That means the row was
            # purged, or the token was minted against a different database.
            # Either way it cannot be checked for revocation, so it is refused.
            _record(conn, token_id=token_id, purpose=purpose, object_id=object_id,
                    event="verify_failed", reason="unknown_token")
            return TokenVerdict(False, "unknown_token")
        if row["revoked_at"]:
            _record(conn, token_id=token_id, purpose=purpose, object_id=object_id,
                    event="verify_failed", reason="revoked")
            return TokenVerdict(False, "revoked")
        _record(conn, token_id=token_id, purpose=purpose, object_id=object_id, event="verified")

    return TokenVerdict(True, "ok", token_id=token_id, purpose=purpose,
                        object_id=object_id, expires_at=claims.get("e", ""))


def revoke(token_id: str, *, reason: str = "", actor: str = "") -> bool:
    """Kill one token. Returns False if it was already dead or never existed."""
    from dispatch.db import get_connection

    with get_connection() as conn:
        row = conn.execute(
            "SELECT purpose, object_id, revoked_at FROM operational_tokens WHERE token_id=?",
            (token_id,),
        ).fetchone()
        if row is None or row["revoked_at"]:
            return False
        conn.execute(
            "UPDATE operational_tokens SET revoked_at=?, revoked_by=?, revoke_reason=? WHERE token_id=?",
            (_iso(_utc_now()), actor, reason, token_id),
        )
        _record(conn, token_id=token_id, purpose=row["purpose"], object_id=row["object_id"],
                event="revoked", reason=reason, actor=actor)
    return True


def revoke_for_object(purpose: str, object_id: str, *, reason: str = "", actor: str = "") -> int:
    """Kill every live token for one object -- the operator's "that link got
    forwarded to the wrong person" control. Returns how many were revoked."""
    from dispatch.db import get_connection

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT token_id FROM operational_tokens "
            "WHERE purpose=? AND object_id=? AND revoked_at IS NULL",
            (purpose, object_id),
        ).fetchall()
        token_ids = [r["token_id"] for r in rows]

    return sum(1 for tid in token_ids if revoke(tid, reason=reason, actor=actor))


def list_tokens(purpose: str | None = None, object_id: str | None = None) -> list[dict]:
    from dispatch.db import get_connection

    sql = "SELECT * FROM operational_tokens"
    clauses, params = [], []
    if purpose:
        clauses.append("purpose=?")
        params.append(purpose)
    if object_id:
        clauses.append("object_id=?")
        params.append(object_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY issued_at DESC"
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def list_audit(token_id: str | None = None, object_id: str | None = None) -> list[dict]:
    from dispatch.db import get_connection

    sql = "SELECT * FROM token_audit"
    clauses, params = [], []
    if token_id:
        clauses.append("token_id=?")
        params.append(token_id)
    if object_id:
        clauses.append("object_id=?")
        params.append(object_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY at DESC, rowid DESC"
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
