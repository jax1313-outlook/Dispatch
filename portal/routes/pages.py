"""Page routes — all Portal sections."""

from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for

from portal import helpers
from portal.models import sandbox, publisher, conflict
from portal.models import library as lib_model
from portal.models import archive as arc_model
from portal.models import intelligence as intel_model
from cin_lite import control, pending

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    return redirect(url_for("pages.home"))


@pages_bp.route("/home")
def home():
    all_entries = sandbox.get_all()
    sam_entries = {k: v for k, v in all_entries.items() if v["source_type"] == "sam"}
    dispatch_entries = {k: v for k, v in all_entries.items() if v["source_type"] == "dispatch"}

    sam_sorted = sorted(sam_entries.values(), key=_priority_key, reverse=True)[:5]
    dispatch_sorted = sorted(dispatch_entries.values(), key=_priority_key, reverse=True)[:5]

    unresolved = conflict.get_unresolved()
    pub_queue = [a for a in publisher.get_queue() if a["status"] not in ("APPROVED", "ARCHIVED")]

    pending_items = pending.list_pending()

    return render_template(
        "home.html",
        sam_cards=sam_sorted,
        dispatch_cards=dispatch_sorted,
        conflict_count=len(unresolved),
        publisher_count=len(pub_queue),
        archive_count=arc_model.total_count(),
        intel_count=intel_model.total_count(),
        pending_count=len(pending_items),
        card_visual=helpers.card_visual,
        format_score=helpers.format_score,
    )


@pages_bp.route("/sam")
def sam():
    all_entries = sandbox.get_all()
    sam_entries = {k: v for k, v in all_entries.items() if v["source_type"] == "sam"}

    if not sam_entries or request.args.get("refresh"):
        results = helpers.load_and_process_sam()
        for r in results:
            c = r["contract"]
            source_id = c.get("solicitation_number") or c.get("_sam_notice_id") or "unknown"
            sandbox.create_entry(
                source_type="sam",
                source_id=source_id,
                title=c.get("title", "Unknown"),
                card_data=c,
                intelligence=r["intelligence"],
                flags=r["flags"],
                summary=r["summary"],
                decision=r["decision"],
            )
        all_entries = sandbox.get_all()
        sam_entries = {k: v for k, v in all_entries.items() if v["source_type"] == "sam"}

    entries_sorted = sorted(sam_entries.values(), key=_priority_key, reverse=True)
    return render_template(
        "sam.html",
        entries=entries_sorted,
        card_visual=helpers.card_visual,
        format_score=helpers.format_score,
    )


@pages_bp.route("/dispatch")
def dispatch():
    from dispatch import services as dispatch_svc
    from dispatch.models import LOAD_STATUSES

    status_filter = request.args.get("status")
    engine_loads = dispatch_svc.list_loads(status=status_filter)

    all_entries = sandbox.get_all()
    dispatch_entries = {k: v for k, v in all_entries.items() if v["source_type"] == "dispatch"}

    if not dispatch_entries or request.args.get("refresh"):
        loads = helpers.load_dispatch_data()
        for load in loads:
            load_id = load.get("load_id", "unknown")
            entry = sandbox.create_entry(
                source_type="dispatch",
                source_id=load_id,
                title=load.get("title", "Unknown"),
                card_data=load,
                score=load.get("score"),
            )
            conflict.check_dispatch_card(load, entry["id"])
        all_entries = sandbox.get_all()
        dispatch_entries = {k: v for k, v in all_entries.items() if v["source_type"] == "dispatch"}

    entries_sorted = sorted(dispatch_entries.values(), key=_priority_key, reverse=True)
    return render_template(
        "dispatch.html",
        entries=entries_sorted,
        engine_loads=engine_loads,
        load_statuses=LOAD_STATUSES,
        status_filter=status_filter,
        card_visual=helpers.card_visual,
        format_score=helpers.format_score,
    )


@pages_bp.route("/dispatch/<load_id>")
def dispatch_detail(load_id):
    from dispatch import services as dispatch_svc
    from dispatch.models import MILESTONE_TYPES, MILESTONE_SOURCES, EVIDENCE_TYPES

    bundle = dispatch_svc.get_load_bundle(load_id)
    if not bundle:
        return redirect(url_for("pages.dispatch"))
    return render_template(
        "dispatch_detail.html",
        milestone_types=MILESTONE_TYPES,
        milestone_sources=MILESTONE_SOURCES,
        evidence_types=EVIDENCE_TYPES,
        **bundle,
    )


@pages_bp.route("/brief/<sandbox_id>")
def brief(sandbox_id: str):
    entry = sandbox.get(sandbox_id)
    if not entry:
        return "Sandbox entry not found", 404

    related_conflicts = [n for n in conflict.get_all() if n.get("sandbox_id") == sandbox_id]
    related_publisher = [a for a in publisher.get_queue() if a.get("sandbox_id") == sandbox_id]

    return render_template(
        "brief.html",
        entry=entry,
        conflicts=related_conflicts,
        publisher_actions=related_publisher,
        card_visual=helpers.card_visual,
        format_score=helpers.format_score,
        publisher_action_types=publisher.ACTION_TYPES,
    )


@pages_bp.route("/publisher")
def publisher_view():
    queue = publisher.get_queue()
    return render_template("publisher.html", queue=queue)


@pages_bp.route("/library")
def library():
    all_records = lib_model.get_all()
    missing = lib_model.get_missing_company_assets()
    sections = [
        {"name": "Company Library", "key": "company",
         "description": "Approved company documents available for Publisher production and broker packets.",
         "records": all_records.get("company", []),
         "missing": missing},
        {"name": "Broker Library", "key": "broker",
         "description": "Approved broker profiles, contact history, and performance records.",
         "records": all_records.get("broker", [])},
        {"name": "Customer Library", "key": "customer",
         "description": "Approved customer/shipper profiles and relationship data.",
         "records": all_records.get("customer", [])},
        {"name": "Location Intelligence Library", "key": "location_intelligence",
         "description": "Approved facility data, dock notes, and location-specific operational knowledge.",
         "records": all_records.get("location_intelligence", [])},
        {"name": "Operations Library", "key": "operations",
         "description": "Approved operational templates, checklists, and standard procedures.",
         "records": all_records.get("operations", [])},
        {"name": "Intelligence Library", "key": "intelligence",
         "description": "Approved intelligence products, market data, and analytical references.",
         "records": all_records.get("intelligence", [])},
    ]
    return render_template("library.html", sections=sections)


@pages_bp.route("/archive")
def archive_view():
    from cin_lite import archive as cin_archive
    all_archive = arc_model.get_all()
    all_sandbox = sandbox.get_all()
    sandbox_archived = [
        v for v in all_sandbox.values()
        if v["status"] in ("PASS", "CLOSED", "EXPIRED", "BOOKED")
    ]
    sections = []
    for key in arc_model.ARCHIVE_SECTIONS:
        sections.append({
            "name": arc_model.SECTION_LABELS[key],
            "key": key,
            "records": all_archive.get(key, []),
        })
    pipeline_archived = cin_archive.list_contracts()
    return render_template(
        "archive.html",
        sections=sections,
        sandbox_archived=sandbox_archived,
        pipeline_archived=pipeline_archived,
    )


@pages_bp.route("/intelligence")
def intelligence_view():
    all_intel = intel_model.get_all()
    sections = []
    for key in intel_model.INTEL_TYPES:
        sections.append({
            "name": intel_model.INTEL_LABELS[key],
            "key": key,
            "records": all_intel.get(key, []),
        })
    return render_template("intelligence.html", sections=sections)


@pages_bp.route("/conflicts")
def conflicts():
    all_notices = conflict.get_all()
    unresolved = [n for n in all_notices if not n.get("resolved")]
    resolved = [n for n in all_notices if n.get("resolved")]
    return render_template("conflicts.html", unresolved=unresolved, resolved=resolved)


@pages_bp.route("/pipeline")
def pending_decisions():
    items = pending.list_pending()
    summaries = []
    for item in items:
        contract = item.get("contract", {})
        decision = item.get("decision", {})
        enriched = item.get("enriched", {})
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
            "risk_level": enriched.get("risk_level"),
            "pursuit_readiness": enriched.get("pursuit_readiness"),
            "strategic_assessment": enriched.get("strategic_assessment"),
        })
    from cin_lite.pipeline import routing_history
    history = routing_history()
    return render_template(
        "pending.html",
        pending=summaries,
        actions=control.ACTIONS,
        history=history,
    )


@pages_bp.route("/queues")
def queues():
    from cin_lite.pipeline import routing_history
    review_queue = routing_history(route_filter="HUMAN_REVIEW")
    analysis_queue = routing_history(route_filter="DEEP_ANALYSIS_QUEUE")
    return render_template(
        "queues.html",
        review_queue=review_queue,
        analysis_queue=analysis_queue,
    )


@pages_bp.route("/settings")
def settings():
    import os
    from portal.config import Config, _DEFAULT_SECRET
    from cin_lite import email_delivery

    cin_config = {
        "sam_api_key": bool(os.environ.get("DISPATCH_SAM_API_KEY")),
        "sam_limit": os.environ.get("DISPATCH_SAM_LIMIT", "10"),
        "sam_naics": os.environ.get("DISPATCH_SAM_NAICS", ""),
        "sam_ptype": os.environ.get("DISPATCH_SAM_PTYPE", ""),
        "sam_fetch_desc": os.environ.get("DISPATCH_SAM_FETCH_DESCRIPTION", "1") == "1",
        "smtp_host": os.environ.get("DISPATCH_SMTP_HOST", ""),
        "anthropic_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "email_from": email_delivery.from_address(),
        "email_reviewer": email_delivery.reviewer_address(),
        "email_domain": email_delivery.domain(),
        "email_secret_set": not email_delivery._using_default_secret(),
        "portal_url": os.environ.get("DISPATCH_PORTAL_URL", "http://127.0.0.1:8080"),
        "portal_secret_set": Config.SECRET_KEY != _DEFAULT_SECRET,
    }
    return render_template("settings.html", config=Config, cin_config=cin_config)


def _priority_key(entry: dict) -> tuple:
    """Sort key: active statuses first, then by score (if available), then by date."""
    status = entry.get("status", "OPEN")
    active = status in ("OPEN", "INTERESTED", "PURSUE", "WATCH", "INQUIRY_DRAFTED", "PUBLISHER_REQUIRED")
    score = entry.get("score") or 0

    decision = entry.get("decision", {})
    priority_map = {"urgent": 4, "high": 3, "medium": 2, "low": 1}
    priority_val = priority_map.get(decision.get("priority", ""), 0)

    return (active, score, priority_val, entry.get("updated_at", ""))
