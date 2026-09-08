"""Cross-site request forgery protection for every mutating route.

The whole-program audit's finding S-4: `grep -rniE "csrf"` across `portal/`
returned nothing, while 109 of 218 routes accepted POST, PATCH, PUT or DELETE
authenticated by a session cookie alone. Any page on any site could submit a
form or fire a request to Dispatch and the browser would attach Mike's session
to it -- archiving a load, approving a settlement, deleting evidence.

The design is a session-bound synchronizer token:

  * one random token per session, minted lazily and held in the session cookie
    itself, which is already signed and already HttpOnly;
  * every mutating request must echo it, in the `X-CSRF-Token` header or a
    `csrf_token` form field;
  * comparison is constant-time, and a token from a different session fails
    because it was never in this session to begin with.

EXEMPTIONS are exactly the ones the login gate already carries, and for the
same reason -- these endpoints have no session to bind a token to, and are
authenticated by their own signed tokens instead:

  * the `decisions` blueprint (cin_lite's email action links),
  * the `stakeholder` blueprint (the external read-only broker view),
  * `dispatch_api.dispatch_decision` (the freight email action link), and only
    that endpoint, never its whole blueprint,
  * the `joe_api` blueprint -- the seven contracts JOE speaks to.

`joe_api` is exempt for a different reason than the rest, and the difference is
the justification. **CSRF is a defence against ambient authority.** It exists
because a browser attaches the session cookie to a request whether or not the
page that made it had any business making it, so the server needs a second proof
that the page was one of its own. `joe_api` has no ambient authority to abuse:
every route on it carries `@authenticated`, which requires a bearer token in an
`Authorization` header. **No browser sends that header on its own.** A forged
cross-site request to `/api/joe/opportunity` arrives without the token and is
refused by the auth guard, which is the gate that was actually holding the door.

Requiring CSRF here bought nothing and cost something real. A machine client had
to fetch a page, keep two cookies and replay a token before its first write, and
when any of that lapsed the refusal came back as a 403 indistinguishable from a
bad token. JOE speaks this contract from a tablet over a link CONOPS v1.1 calls
intermittent by design, so "the session went away" is the normal case here, not
the exceptional one.

**This is scoped by `PORTAL_HOST` being `127.0.0.1`** -- the condition
`docs/DISPATCH_SECURITY_DEFERRAL.md` names. The day Phase 3 binds to the network
for the tablet, this entry is re-read rather than inherited, along with the rest
of that deferral.

Widening this list is how CSRF protection quietly stops protecting anything, so
it is defined once, here, and each entry carries the reason it earned its place.
"""

from __future__ import annotations

import hmac
import secrets

from flask import Flask, abort, g, request, session

_SESSION_KEY = "_csrf_token"
_HEADER = "X-CSRF-Token"
_FORM_FIELD = "csrf_token"
_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}

EXEMPT_BLUEPRINTS = {"decisions", "stakeholder", "joe_api"}
EXEMPT_ENDPOINTS = {"dispatch_api.dispatch_decision", "auth.login",
                    "driver_portal.driver_login", "driver_portal.driver_forgot_pin"}


def issue_token() -> str:
    """The token for this session, minted on first use.

    Login itself is exempt, which is deliberate: the login POST happens before
    a session exists to bind a token to, and it is not a state-changing action
    on Mike's behalf -- an attacker who could forge it would only be logging
    the victim in as themselves.
    """
    token = session.get(_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[_SESSION_KEY] = token
    return token


def _submitted() -> str:
    header = request.headers.get(_HEADER, "")
    if header:
        return header
    if request.form:
        return request.form.get(_FORM_FIELD, "")
    # A JSON body may carry it too, for a caller that cannot set headers.
    if request.is_json:
        body = request.get_json(silent=True)
        if isinstance(body, dict):
            return str(body.get(_FORM_FIELD, ""))
    return ""


def is_exempt() -> bool:
    if request.blueprint in EXEMPT_BLUEPRINTS:
        return True
    return request.endpoint in EXEMPT_ENDPOINTS


def init_csrf(app: Flask) -> None:
    """Install the gate and make the token reachable from every template."""

    @app.before_request
    def _require_csrf_token():
        if request.method not in _MUTATING:
            return None
        if not app.config.get("CSRF_ENABLED", True):
            return None
        if request.endpoint is None or is_exempt():
            return None

        expected = session.get(_SESSION_KEY, "")
        submitted = _submitted()
        if not expected or not submitted or not hmac.compare_digest(expected, submitted):
            # 403 rather than 400: this is a refusal to act, not a malformed
            # request, and the distinction matters to whoever reads the logs.
            abort(403, description="CSRF token missing or invalid.")
        return None

    @app.context_processor
    def _csrf_in_templates():
        return {"csrf_token": issue_token}

    @app.after_request
    def _expose_token_to_the_page(response):
        """The token also rides on a readable cookie so a page loaded before
        the session existed can still fire a request. It is NOT the credential
        -- the session cookie is -- so a script being able to read this one
        costs nothing, and it is what makes the double-submit work for the
        fetch() calls scattered through the templates."""
        if request.endpoint is None:
            return response
        try:
            # Set on EVERY endpoint, exempt ones included. /login is exempt from
            # the check -- there is no session yet to bind a token to -- but it
            # is exactly where a browser first arrives, so it must be where the
            # token is first handed out. Skipping exempt endpoints here left the
            # cookie unset until after the first mutating request had already
            # been refused.
            response.set_cookie(
                "csrf_token", issue_token(), samesite="Lax", httponly=False
            )
        except RuntimeError:
            pass
        return response
