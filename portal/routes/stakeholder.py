"""External stakeholder portal -- read-only, token-secured, non-PIN-gated.

Broker/shipper/customer view of a single load (D11: Manufacturer -> Shipper
-> Broker -> Level 1 Transport is a genuine disclosure chain, not a set of
synonyms -- see dispatch/services.py::build_stakeholder_view() for exactly
what is and is not shared with these parties).

    GET /portal/loads/<load_id>?token=<hmac_token>

The token is produced by dispatch.notifications.make_stakeholder_token() and
must be generated from inside the (PIN-gated) portal -- see the "Stakeholder
Link" control on the load detail page. This route itself carries no session
requirement; it is exempted from the DISPATCH_PIN gate in portal/app.py the
same way the existing decision-email action links are, because it must work
for a recipient with no portal login of their own.

Distinct from the INTERNAL, PIN-gated read-only load view added for Load
Search (portal/routes/pages.py::search_load_detail, `/search/loads/<id>`,
portal/templates/load_readonly_detail.html) -- that page is for Dispatch's
own staff to look a load up without risk of editing it; this one is for an
external party with no Dispatch login at all.
"""

from __future__ import annotations

from flask import Blueprint, render_template, request

from dispatch import notifications, services

stakeholder_bp = Blueprint("stakeholder", __name__)


@stakeholder_bp.route("/loads/<load_id>")
def stakeholder_view(load_id: str):
    token = request.args.get("token", "")

    if not notifications.verify_stakeholder_token(load_id, token):
        return render_template(
            "stakeholder_view.html",
            error="Invalid or expired link.",
            load_id=load_id,
        ), 403

    view = services.build_stakeholder_view(load_id)
    if not view:
        return render_template(
            "stakeholder_view.html",
            error="Load not found.",
            load_id=load_id,
        ), 404

    return render_template("stakeholder_view.html", error=None, **view)
