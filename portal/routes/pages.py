"""Page routes — all Portal sections."""

from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for

from portal import helpers
from portal.models import sandbox, publisher, conflict

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

    return render_template(
        "home.html",
        sam_cards=sam_sorted,
        dispatch_cards=dispatch_sorted,
        conflict_count=len(unresolved),
        publisher_count=len(pub_queue),
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
        card_visual=helpers.card_visual,
        format_score=helpers.format_score,
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
    company_docs = [
        {"name": "W-9", "status": "placeholder"},
        {"name": "Insurance", "status": "placeholder"},
        {"name": "Authority", "status": "placeholder"},
        {"name": "Business Card", "status": "placeholder"},
        {"name": "Rate Sheets", "status": "placeholder"},
        {"name": "Terms", "status": "placeholder"},
        {"name": "Capabilities", "status": "placeholder"},
        {"name": "Compliance Documents", "status": "placeholder"},
    ]
    location_fields = [
        "Facility Name", "Address", "Gate Notes", "Dock Notes",
        "Check-in Procedure", "Security Requirements", "Liftgate Requirement",
        "Pallet Jack Requirement", "Forklift Availability", "Load Time",
        "Unload Time", "Detention History", "Driver Notes",
    ]
    sections = [
        {"name": "Company Library", "entries": company_docs},
        {"name": "Broker Library", "entries": []},
        {"name": "Customer Library", "entries": []},
        {"name": "Location Intelligence Library", "fields": location_fields},
        {"name": "Operations Library", "entries": []},
        {"name": "Intelligence Library", "entries": []},
    ]
    return render_template("library.html", sections=sections)


@pages_bp.route("/archive")
def archive_view():
    all_entries = sandbox.get_all()
    archived = [
        v for v in all_entries.values()
        if v["status"] in ("PASS", "CLOSED", "EXPIRED", "BOOKED")
    ]
    sections = [
        {"name": "Load Archive", "description": "Completed load records and decisions"},
        {"name": "Decision Archive", "description": "Historical decision records"},
        {"name": "Publisher Archive", "description": "Published document packages"},
        {"name": "Location History Archive", "description": "Historical location intelligence"},
        {"name": "Broker History Archive", "description": "Historical broker performance"},
    ]
    return render_template("archive.html", sections=sections, archived=archived)


@pages_bp.route("/conflicts")
def conflicts():
    all_notices = conflict.get_all()
    unresolved = [n for n in all_notices if not n.get("resolved")]
    resolved = [n for n in all_notices if n.get("resolved")]
    return render_template("conflicts.html", unresolved=unresolved, resolved=resolved)


@pages_bp.route("/settings")
def settings():
    from portal.config import Config
    return render_template("settings.html", config=Config)


def _priority_key(entry: dict) -> tuple:
    """Sort key: active statuses first, then by score (if available), then by date."""
    status = entry.get("status", "OPEN")
    active = status in ("OPEN", "INTERESTED", "PURSUE", "WATCH", "INQUIRY_DRAFTED", "PUBLISHER_REQUIRED")
    score = entry.get("score") or 0

    decision = entry.get("decision", {})
    priority_map = {"urgent": 4, "high": 3, "medium": 2, "low": 1}
    priority_val = priority_map.get(decision.get("priority", ""), 0)

    return (active, score, priority_val, entry.get("updated_at", ""))
