"""Portal-side session helpers bridging Flask's session cookie to
dispatch.security.auth.

Kept separate from dispatch/security/, which has no Flask dependency
at all (mirrors how dispatch/spine/ has no Portal dependency) -- this
file is the one place Flask's `session`/`g` meet the Security
Foundation module.
"""

from __future__ import annotations

from functools import wraps

from flask import g, redirect, request, session as flask_session, url_for

from dispatch.security import auth, store
from dispatch.security.models import SecurityEvent


def get_current_session() -> dict | None:
    """Returns the current request's validated Dispatch session dict,
    or None if not logged in / session invalid. Cached on `g` for the
    duration of the request -- Flask's `g` is request-scoped."""
    if "dispatch_session_id" not in flask_session:
        return None
    if not hasattr(g, "_dispatch_session"):
        g._dispatch_session = auth.current_session(flask_session.get("dispatch_session_id"))
    return g._dispatch_session


def get_current_user() -> dict | None:
    sess = get_current_session()
    if sess is None:
        return None
    if not hasattr(g, "_dispatch_user"):
        g._dispatch_user = store.get_user(sess["user_id"])
    return g._dispatch_user


def login_required(view):
    """Requires any valid session. Used only on /settings and the
    security routes themselves in this build -- see
    DISPATCH_STAGE7_SECURITY_FOUNDATION_DESIGN_v1.md Section 3. Every
    other existing route is deliberately NOT wrapped with this."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if get_current_session() is None:
            return redirect(url_for("security.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def authority_required(view):
    """Requires a valid session carrying the Authority role."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        sess = get_current_session()
        if sess is None:
            return redirect(url_for("security.login", next=request.path))
        if sess["role"] != "Authority":
            store.create_security_event(
                SecurityEvent(
                    event_type="PERMISSION_DENIED",
                    user_id=sess["user_id"],
                    details={"path": request.path, "required_role": "Authority"},
                )
            )
            return "Forbidden — Authority role required.", 403
        return view(*args, **kwargs)

    return wrapped
