"""Decision endpoint — processes email action clicks from the checkpoint email.

Each action button in the HTML email links to:
    GET /api/decision/<contract_id>/<action>?token=<hmac_token>

The endpoint verifies the token, then delegates to the shared
``pipeline.resolve_decision()`` for archive/routing.
"""

from __future__ import annotations

from flask import Blueprint, render_template, request

from cin_lite import control, email_delivery, pending
from cin_lite.pipeline import resolve_decision

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

    if not pending.load(contract_id):
        return render_template(
            "decision.html",
            success=False,
            error="Decision already processed or contract not found.",
            contract_id=contract_id,
        ), 404

    result = resolve_decision(contract_id, action)

    return render_template(
        "decision.html",
        success=True,
        contract_id=result["contract_id"],
        title=result["title"],
        action_label=result["action_label"],
        route=result["route"],
        proposal=result.get("proposal"),
    )
