"""Login/logout routes -- Dispatch Security Foundation.

Per DISPATCH_STAGE7_SECURITY_FOUNDATION_DESIGN_v1.md, these routes and
/settings are the only Portal surfaces gated by session auth in this
build. Every other existing route is unaffected.
"""

from __future__ import annotations

from flask import Blueprint, redirect, render_template, request
from flask import session as flask_session
from flask import url_for

from dispatch.security import auth

security_bp = Blueprint("security", __name__)


@security_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        pin = request.form.get("pin", "").strip()
        result = auth.login(display_name, pin)
        if result:
            flask_session["dispatch_session_id"] = result["session_id"]
            next_url = request.args.get("next") or url_for("pages.home")
            return redirect(next_url)
        error = "Invalid identity or PIN."
    return render_template("login.html", error=error)


@security_bp.route("/logout", methods=["GET", "POST"])
def logout():
    session_id = flask_session.pop("dispatch_session_id", None)
    if session_id:
        auth.logout(session_id)
    return redirect(url_for("security.login"))
