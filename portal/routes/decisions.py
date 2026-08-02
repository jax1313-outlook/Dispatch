"""Decision endpoint — processes email action clicks from the checkpoint email.

Each action button in the HTML email links to:
    GET /api/decision/<contract_id>/<action>?token=<hmac_token>

The endpoint verifies the token, loads the pending decision, completes the
archive/routing flow, and returns a confirmation page.
"""

from __future__ import annotations

from flask import Blueprint, render_template, request

from cin_lite import archive, control, email_delivery, pending
from cin_lite.workflows import proposal

decisions_bp = Blueprint("decisions", __name__)


@decisions_bp.route("/decision/<contract_id>/<action>")
def process_decision(contract_id: str, action: str):
    token = request.args.get("token", "")

    if action not in control.ACTIONS:
        return render_template(
            "decision.html",
            success=False,
            error=f"Unknown action: {action}",
            contract_id=contract_id,
        ), 400

    if not email_delivery.verify_token(contract_id, action, token):
        return render_template(
            "decision.html",
            success=False,
            error="Invalid or expired token.",
            contract_id=contract_id,
        ), 403

    record = pending.load(contract_id)
    if not record:
        return render_template(
            "decision.html",
            success=False,
            error="Decision already processed or contract not found.",
            contract_id=contract_id,
        ), 404

    label, route = control.resolve(action)

    contract_data = record["contract"]
    intelligence = record["intelligence"]
    summary = record["summary"]
    decision = record["decision"]
    flags = record["flags"]

    metadata = archive.store(contract_data, intelligence, summary)
    archive.record_routing(metadata["contract_id"], action, route, metadata, decision)
    email_delivery.deliver_decision(
        contract_data, metadata["contract_id"], summary, decision, action, route, flags,
    )

    proposal_info = None
    if proposal.is_triggered(action):
        result = proposal.trigger(
            contract_data, metadata["contract_id"], intelligence, decision, summary, flags,
        )
        proposal_info = result

    pending.complete(contract_id)

    return render_template(
        "decision.html",
        success=True,
        contract_id=metadata["contract_id"],
        title=contract_data.get("title", ""),
        action_label=label,
        route=route,
        proposal=proposal_info,
    )
