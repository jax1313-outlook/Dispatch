"""Pipeline API routes — trigger, pending decisions, decide, and history.

Bridges the CIN-Lite pipeline into the portal so it can be triggered and
managed from the web UI or external automation tools (n8n, webhooks).
"""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from cin_lite import control, pending
from cin_lite.pipeline import process_contracts, resolve_decision, routing_history

pipeline_bp = Blueprint("pipeline", __name__)


@pipeline_bp.route("/run", methods=["POST"])
def run_pipeline():
    """Trigger the acquisition-to-checkpoint pipeline.

    Optional JSON body:
        {"action": "approve_archive"}   — auto-decide all contracts
    """
    data = request.get_json(silent=True) or {}
    action_override = data.get("action")

    if action_override and action_override not in control.ACTIONS:
        return jsonify({"error": f"Invalid action: {action_override}"}), 400

    results = process_contracts(action_override)
    return jsonify({
        "status": "ok",
        "processed": len(results),
        "contracts": results,
    })


@pipeline_bp.route("/pending", methods=["GET"])
def list_pending():
    """List all contracts awaiting a decision."""
    items = pending.list_pending()
    summaries = []
    for item in items:
        contract = item.get("contract", {})
        decision = item.get("decision", {})
        summaries.append({
            "contract_id": item["contract_id"],
            "title": contract.get("title"),
            "agency": contract.get("agency"),
            "solicitation_number": contract.get("solicitation_number"),
            "estimated_value": contract.get("estimated_value"),
            "summary": item.get("summary", ""),
            "recommendation": decision.get("action"),
            "priority": decision.get("priority"),
            "flag_count": len(item.get("flags", [])),
            "flags": item.get("flags", []),
        })
    return jsonify({"status": "ok", "pending": summaries, "count": len(summaries)})


@pipeline_bp.route("/decide", methods=["POST"])
def decide():
    """Process a decision from the portal UI (no token needed — session-authenticated).

    JSON body: {"contract_id": "CIN-...", "action": "approve_archive"}
    """
    data = request.get_json(force=True)
    contract_id = data.get("contract_id")
    action = data.get("action")

    if not contract_id or not action:
        return jsonify({"error": "contract_id and action required"}), 400

    if action not in control.ACTIONS:
        return jsonify({"error": f"Invalid action: {action}"}), 400

    try:
        result = resolve_decision(contract_id, action)
        return jsonify({"status": "ok", **result})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@pipeline_bp.route("/history", methods=["GET"])
def history():
    """Return completed routing decisions (most recent first)."""
    records = routing_history()
    return jsonify({"status": "ok", "history": records, "count": len(records)})
