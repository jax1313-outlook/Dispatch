"""Auth routes — DISPATCH_PIN login/logout (Authority role only).

See portal/models/identity.py and PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md (Claude-3 repo)
for the full design and what's deferred. The identity itself is created out-of-band by the
`cin-portal-init-admin` CLI command (portal/cli.py) -- there is no "register" route here, by
design (see identity.bootstrap_authority's single-use refusal).
"""

from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, session, url_for

from portal.models import identity as identity_model

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", error=None)

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


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
