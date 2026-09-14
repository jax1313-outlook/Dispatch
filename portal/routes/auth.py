"""Auth routes — DISPATCH_PIN login/logout (Authority role only).

See portal/models/identity.py and governance/PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md
for the full design and what's deferred. The identity itself is created out-of-band by the
`cin-portal-init-admin` CLI command (portal/cli.py) -- there is no "register" route here, by
design (see identity.bootstrap_authority's single-use refusal).
"""

from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, session, url_for

from portal.models import identity as identity_model
from portal.models import pin_service

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", error=None, pin_service_configured=pin_service.configured())

    if pin_service.configured():
        return _login_with_pin_service()

    user_id = identity_model.get_authority_user_id()
    if not user_id:
        return render_template(
            "login.html",
            error="No identity configured yet. Run cin-portal-init-admin on the server first.",
        ), 400

    pin = request.form.get("pin", "")
    record = identity_model.verify_pin(user_id, pin)
    if not record:
        return render_template(
            "login.html", error="Incorrect PIN, or the account is temporarily locked.",
        ), 401

    session["user_id"] = record["user_id"]
    session["role"] = record["role"]
    identity_model.record_session_created(record["user_id"])
    return redirect(url_for("pages.home"))


_LOOPBACK = ("127.0.0.1", "::1", "localhost")


def _first_operations_pin_open() -> bool:
    """Before any Operations user exists, the dialog opens on the server itself only."""
    return request.remote_addr in _LOOPBACK and not pin_service.operations_users()


@auth_bp.route("/joe/operations-pin", methods=["GET", "POST"])
def operations_pin():
    """The dialog box with Joe in which Mike Zachary authorizes an Operations PIN.

    Mike Zachary, 2026-09-13: an Operations PIN is his alone to authorize,
    "through voice or dialog box entry with Joe." The Library holds the rule and
    refuses anyone else; this page only decides who is at the dialog:

      * Mike, signed in to Operations with his own PIN -- the name comes from
        that sign-in, never from the form; or
      * before any Operations PIN exists, whoever is at the server laptop
        itself, who types the authorizing name. The Library accepts only
        Mike Zachary.

    Voice reaches the same Library rule with channel VOICE through Joe
    (worker bus capability pin_create); it is not wired into this portal.
    """
    if not pin_service.configured():
        return render_template("operations_pin.html", error="The Library PIN Service is not configured on this server.",
                               done=None, first=False, signed_in_as=None), 503
    try:
        first = _first_operations_pin_open()
    except pin_service.PinServiceUnavailable as exc:
        return render_template("operations_pin.html", error=str(exc), done=None, first=False, signed_in_as=None), 503
    signed_in_as = session.get("display_name") if session.get("user_id") else None
    if not first and not pin_service.is_operations_authority(signed_in_as):
        return render_template("operations_pin.html", error=f"Only {pin_service.OPERATIONS_AUTHORITY} authorizes "
                               "an Operations PIN. Sign in to Operations with his PIN first.",
                               done=None, first=False, signed_in_as=signed_in_as), 403
    if request.method == "GET":
        return render_template("operations_pin.html", error=None, done=None, first=first, signed_in_as=signed_in_as)

    authorized_by = signed_in_as if not first else (request.form.get("authorized_by") or "").strip()
    name = (request.form.get("name") or "").strip()
    pin, again = request.form.get("pin", ""), request.form.get("pin_again", "")

    def say(error=None, done=None, status=200):
        return render_template("operations_pin.html", error=error, done=done, first=first,
                               signed_in_as=signed_in_as), status

    if not name:
        return say("Who is the PIN for?", status=400)
    if "".join(pin.split()).upper() != "".join(again.split()).upper():
        return say("The two PINs are not the same.", status=400)
    try:
        existing = any(u["display_name"] == name for u in pin_service.operations_users())
        if existing and request.form.get("action") == "reset":
            pin_service.reset_operations_pin(name, pin, authorized_by=authorized_by, channel="DIALOG")
            return say(done=f"{name}'s Operations PIN is changed. The old one no longer works.")
        pin_service.create_operations_pin(name, pin, authorized_by=authorized_by, channel="DIALOG")
    except pin_service.PinRefused as exc:
        return say(f"Joe: I can't do that -- {exc}.", status=400)
    except pin_service.PinServiceUnavailable as exc:
        return say(str(exc), status=503)
    return say(done=f"{name} can now sign in to Operations, as authorized by {authorized_by}.")


def _login_with_pin_service():
    """Operations Portal -> Library PIN Service (portal/models/pin_service.py)."""
    try:
        answer = pin_service.validate(pin_service.OPERATIONS, request.form.get("pin", ""), request.remote_addr)
    except pin_service.PinServiceUnavailable as exc:
        return render_template("login.html", error=str(exc)), 503
    if not answer:
        return render_template("login.html", error="Denied."), 401
    session.clear()
    session["user_id"] = answer["identity_id"]
    session["role"] = answer["role"]
    session["display_name"] = answer["display_name"]
    return redirect(url_for("pages.home"))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
