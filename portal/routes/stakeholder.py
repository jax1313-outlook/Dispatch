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

    GET /portal/loads/<load_id>/evidence/<evidence_id>?token=<hmac_token>

Token-scoped evidence file download -- the fast-follow flagged (but
deliberately not built) in build_stakeholder_view()'s docstring. Same
verify_stakeholder_token() check as the view route above, PLUS a mandatory
IDOR check: the evidence record's own load_id must equal the load_id in the
URL. A stakeholder token is scoped to exactly one load; without this check
anyone holding a valid token for load A could enumerate evidence_ids and
pull evidence that belongs to a completely different load B. Any failure
of that check -- evidence not found, or found but scoped to a different
load -- returns a flat 404, never a 403, so the response never confirms or
denies whether a given evidence_id exists (just under a different load).
"""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request, send_file

from dispatch import notifications, services, store

stakeholder_bp = Blueprint("stakeholder", __name__)


@stakeholder_bp.route("/loads/<load_id>")
def stakeholder_view(load_id: str):
    token = request.args.get("token", "")
    as_json = request.args.get("format") == "json"

    if not notifications.verify_stakeholder_token(load_id, token):
        error = "Invalid or expired link."
        if as_json:
            return jsonify({"error": error}), 403
        return render_template(
            "stakeholder_view.html",
            error=error,
            load_id=load_id,
        ), 403

    view = services.build_stakeholder_view(load_id)
    if not view:
        error = "Load not found."
        if as_json:
            return jsonify({"error": error}), 404
        return render_template(
            "stakeholder_view.html",
            error=error,
            load_id=load_id,
        ), 404

    if as_json:
        return jsonify(view)
    return render_template("stakeholder_view.html", error=None, **view)


@stakeholder_bp.route("/loads/<load_id>/evidence/<evidence_id>")
def stakeholder_evidence_download(load_id: str, evidence_id: str):
    token = request.args.get("token", "")

    if not notifications.verify_stakeholder_token(load_id, token):
        return jsonify({"error": "Invalid or expired link."}), 403

    # IDOR check: an evidence_id that exists but belongs to a different
    # load must 404 exactly the same as an evidence_id that doesn't exist
    # at all -- never reveal which case it is.
    evidence = store.get_evidence(evidence_id)
    if not evidence or evidence.get("load_id") != load_id:
        return jsonify({"error": "Evidence not found."}), 404

    result = services.get_evidence_file(evidence_id)
    if not result:
        return jsonify({"error": "Evidence not found."}), 404

    file_path, download_name = result
    return send_file(file_path, download_name=download_name, as_attachment=True)
