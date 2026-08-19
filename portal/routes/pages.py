"""Page routes — all Portal sections."""

from __future__ import annotations

from pathlib import Path

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


@pages_bp.route("/operations")
def operations():
    """Consequence-sorted decision feed -- one screen for everything open
    across Publisher/Conflicts/Pipeline/Exceptions/Settlements/Stalled
    Loads/Queues/Library gaps. See portal/models/operations_feed.py."""
    from portal.models import operations_feed
    feed = operations_feed.build_feed()
    return render_template("operations.html", **feed)


@pages_bp.route("/home")
def home():
    from dispatch import services as dispatch_svc

    all_entries = sandbox.get_all()
    sam_entries = {k: v for k, v in all_entries.items() if v["source_type"] == "sam"}
    dispatch_entries = {k: v for k, v in all_entries.items() if v["source_type"] == "dispatch"}

    sam_sorted = sorted(sam_entries.values(), key=_priority_key, reverse=True)[:5]
    dispatch_sorted = sorted(dispatch_entries.values(), key=_priority_key, reverse=True)[:5]

    unresolved = conflict.get_unresolved()
    pub_queue = [a for a in publisher.get_queue() if a["status"] not in ("APPROVED", "ARCHIVED")]

    pending_items = pending.list_pending()

    all_engine_loads = dispatch_svc.list_loads()
    active_engine = [l for l in all_engine_loads if l["status"] not in ("archived", "cancelled", "completed")]

    fleet_summary = dispatch_svc.get_fleet_summary()
    fin_dashboard = dispatch_svc.get_financial_dashboard()

    stalled = dispatch_svc.check_stalled_loads()
    from dispatch import store as dispatch_store
    recent_activity = dispatch_store.get_recent_activity(limit=15)
    chart_data = dispatch_svc.get_chart_data()
    attention_needed = helpers.attention_needed()

    return render_template(
        "home.html",
        sam_cards=sam_sorted,
        dispatch_cards=dispatch_sorted,
        conflict_count=len(unresolved),
        publisher_count=len(pub_queue),
        archive_count=arc_model.total_count(),
        intel_count=intel_model.total_count(),
        pending_count=len(pending_items),
        engine_load_count=len(active_engine),
        fleet_summary=fleet_summary,
        fin_dashboard=fin_dashboard,
        stalled_loads=stalled,
        recent_activity=recent_activity,
        chart_data=chart_data,
        attention_needed=attention_needed,
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
    customer_search = request.args.get("customer", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    engine_loads = dispatch_svc.list_loads(
        status=status_filter,
        customer=customer_search or None,
        date_from=date_from or None,
        date_to=date_to or None,
    )
    fin_dashboard = dispatch_svc.get_financial_dashboard()

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
            scoring = load.get("_scoring")
            if scoring:
                sandbox.update_scoring(entry["id"], scoring)
            conflict.check_dispatch_card(load, entry["id"])
        all_entries = sandbox.get_all()
        dispatch_entries = {k: v for k, v in all_entries.items() if v["source_type"] == "dispatch"}

    _sync_booked_entries(dispatch_entries)

    entries_sorted = sorted(dispatch_entries.values(), key=_priority_key, reverse=True)
    active_drivers = dispatch_svc.list_drivers(status="active")
    active_equipment = dispatch_svc.list_equipment(status="active")
    stalled = dispatch_svc.check_stalled_loads()
    stalled_ids = {ld["load_id"] for ld in stalled}
    lane_templates = dispatch_svc.list_lane_templates()
    return render_template(
        "dispatch.html",
        entries=entries_sorted,
        engine_loads=engine_loads,
        load_statuses=LOAD_STATUSES,
        status_filter=status_filter,
        card_visual=helpers.card_visual,
        format_score=helpers.format_score,
        fin_dashboard=fin_dashboard,
        active_drivers=active_drivers,
        active_equipment=active_equipment,
        customer_search=customer_search,
        date_from=date_from,
        date_to=date_to,
        stalled_loads=stalled,
        stalled_ids=stalled_ids,
        lane_templates=lane_templates,
    )


@pages_bp.route("/dispatch/<load_id>")
def dispatch_detail(load_id):
    from dispatch import services as dispatch_svc
    from dispatch.models import (
        LOAD_STATUSES,
        MILESTONE_TYPES, MILESTONE_SOURCES, EVIDENCE_TYPES,
        EXCEPTION_TYPES, SEVERITY_LEVELS, EXCEPTION_STATUSES,
        EXPENSE_CATEGORIES, RATE_TYPES, SETTLEMENT_STATUSES, PAYMENT_METHODS,
    )

    from portal.models import completion_packet as cp_model
    from dispatch import email_helper, notifications

    bundle = dispatch_svc.get_load_bundle(load_id)
    if not bundle:
        return redirect(url_for("pages.dispatch"))
    stakeholder_token = notifications.make_stakeholder_token(load_id)
    stakeholder_url = url_for(
        "stakeholder.stakeholder_view", load_id=load_id, token=stakeholder_token, _external=True
    )
    return render_template(
        "dispatch_detail.html",
        stakeholder_url=stakeholder_url,
        load_statuses=LOAD_STATUSES,
        milestone_types=MILESTONE_TYPES,
        milestone_sources=MILESTONE_SOURCES,
        evidence_types=EVIDENCE_TYPES,
        exception_types=EXCEPTION_TYPES,
        severity_levels=SEVERITY_LEVELS,
        exception_statuses=EXCEPTION_STATUSES,
        expense_categories=EXPENSE_CATEGORIES,
        rate_types=RATE_TYPES,
        settlement_statuses=SETTLEMENT_STATUSES,
        payment_methods=PAYMENT_METHODS,
        completion_packet=cp_model.get_packet(load_id),
        email_package=email_helper.get_package(load_id),
        **bundle,
    )


@pages_bp.route("/dispatch/<load_id>/rate-confirmation/print")
def rate_confirmation_print(load_id):
    import os
    from dispatch import services as dispatch_svc

    bundle = dispatch_svc.get_load_bundle(load_id)
    if not bundle:
        return redirect(url_for("pages.dispatch"))

    financials = bundle["financials"]
    if not financials or not financials.get("rate_confirmation"):
        return redirect(url_for("pages.dispatch_detail", load_id=load_id))

    company = {
        "name": os.environ.get("DISPATCH_COMPANY_NAME", ""),
        "address": os.environ.get("DISPATCH_COMPANY_ADDRESS", ""),
        "phone": os.environ.get("DISPATCH_COMPANY_PHONE", ""),
        "email": os.environ.get("DISPATCH_COMPANY_EMAIL", ""),
        "mc_number": os.environ.get("DISPATCH_MC_NUMBER", ""),
        "dot_number": os.environ.get("DISPATCH_DOT_NUMBER", ""),
    }

    return render_template(
        "rate_confirmation_print.html",
        load=bundle["load"],
        rate=financials["rate_confirmation"],
        financials=financials,
        company=company,
        assigned_driver=bundle.get("assigned_driver"),
        assigned_equipment=bundle.get("assigned_equipment"),
    )


@pages_bp.route("/brokers")
def brokers():
    from dispatch import services as dispatch_svc
    from dispatch.models import BROKER_STATUSES
    scorecards = dispatch_svc.get_broker_scorecards()
    contacts = dispatch_svc.list_broker_contacts()
    return render_template(
        "brokers.html",
        scorecards=scorecards,
        contacts=contacts,
        broker_statuses=BROKER_STATUSES,
    )


@pages_bp.route("/profitability")
def profitability():
    from dispatch import services as dispatch_svc
    from dispatch.models import LOAD_STATUSES

    sort_by = request.args.get("sort_by", "profit")
    sort_order = request.args.get("sort_order", "desc")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    status_filter = request.args.get("status", "")
    result = dispatch_svc.get_load_profitability(
        sort_by=sort_by,
        sort_order=sort_order,
        date_from=date_from or None,
        date_to=date_to or None,
        status=status_filter or None,
    )
    return render_template(
        "profitability.html",
        loads=result["loads"],
        summary=result["summary"],
        load_statuses=LOAD_STATUSES,
        sort_by=sort_by,
        sort_order=sort_order,
        date_from=date_from,
        date_to=date_to,
        status_filter=status_filter,
    )


@pages_bp.route("/email-templates")
def email_templates():
    from dispatch.notifications import EMAIL_TEMPLATES
    template_key = request.args.get("template", "dispatched")
    return render_template(
        "email_templates.html",
        templates=EMAIL_TEMPLATES,
        selected=template_key,
    )


@pages_bp.route("/calendar")
def load_calendar():
    from dispatch import services as dispatch_svc
    from datetime import date

    today = date.today()
    try:
        year = int(request.args.get("year", today.year))
        month = int(request.args.get("month", today.month))
    except (ValueError, TypeError):
        year, month = today.year, today.month
    if month < 1:
        month, year = 12, year - 1
    elif month > 12:
        month, year = 1, year + 1

    cal_data = dispatch_svc.get_load_calendar(year, month)
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    return render_template(
        "calendar.html",
        cal=cal_data,
        prev_year=prev_year, prev_month=prev_month,
        next_year=next_year, next_month=next_month,
    )


@pages_bp.route("/ifta")
def ifta():
    from dispatch import services as dispatch_svc
    from dispatch.models import IFTA_JURISDICTIONS
    from datetime import date

    today = date.today()
    view_mode = request.args.get("view", "quarter")
    try:
        year = int(request.args.get("year", today.year))
        quarter = int(request.args.get("quarter", (today.month - 1) // 3 + 1))
        month = int(request.args.get("month", today.month))
    except (ValueError, TypeError):
        year = today.year
        quarter = (today.month - 1) // 3 + 1
        month = today.month

    vehicle_id = request.args.get("vehicle_id", "")

    report = None
    error = None
    try:
        if view_mode == "month":
            report = dispatch_svc.get_ifta_monthly_report(year, month, vehicle_id)
        else:
            report = dispatch_svc.get_ifta_quarterly_report(year, quarter, vehicle_id)
    except ValueError as exc:
        error = str(exc)

    equipment = dispatch_svc.list_equipment(status="active")

    approval = None
    if view_mode != "month" and report is not None:
        approval = dispatch_svc.get_latest_ifta_report_approval(year, quarter, vehicle_id)

    return render_template(
        "ifta.html",
        report=report,
        error=error,
        jurisdictions=IFTA_JURISDICTIONS,
        equipment=equipment,
        sel_year=year,
        sel_quarter=quarter,
        sel_month=month,
        sel_vehicle=vehicle_id,
        view_mode=view_mode,
        approval=approval,
    )


@pages_bp.route("/ifta/review")
def ifta_review():
    from dispatch import services as dispatch_svc
    from datetime import date

    today = date.today()
    try:
        year = int(request.args.get("year", today.year))
        quarter = int(request.args.get("quarter", (today.month - 1) // 3 + 1))
    except (ValueError, TypeError):
        year = today.year
        quarter = (today.month - 1) // 3 + 1

    vehicle_id = request.args.get("vehicle_id", "")
    equipment = dispatch_svc.list_equipment(status="active")

    error = None
    try:
        dashboard = dispatch_svc.build_ifta_review_dashboard(year, quarter, vehicle_id)
    except ValueError as exc:
        dashboard = None
        error = str(exc)

    return render_template(
        "ifta_review.html",
        dashboard=dashboard,
        error=error,
        equipment=equipment,
        sel_year=year,
        sel_quarter=quarter,
        sel_vehicle=vehicle_id,
    )


@pages_bp.route("/compliance")
def compliance():
    from dispatch import services as dispatch_svc
    from dispatch.models import COMPLIANCE_DOC_TYPES, COMPLIANCE_DOC_STATUSES, COMPLIANCE_ENTITY_TYPES

    entity_type = request.args.get("entity_type", "")
    doc_type = request.args.get("doc_type", "")
    status = request.args.get("status", "")

    filters = {}
    if entity_type:
        filters["entity_type"] = entity_type
    if doc_type:
        filters["doc_type"] = doc_type
    if status:
        filters["status"] = status

    docs = dispatch_svc.list_compliance_documents(**filters)
    expiring = dispatch_svc.get_expiring_compliance_documents(days_ahead=30)
    drivers = dispatch_svc.list_drivers()
    equipment = dispatch_svc.list_equipment()

    return render_template(
        "compliance.html",
        docs=docs,
        expiring=expiring,
        drivers=drivers,
        equipment=equipment,
        doc_types=COMPLIANCE_DOC_TYPES,
        doc_statuses=COMPLIANCE_DOC_STATUSES,
        entity_types=COMPLIANCE_ENTITY_TYPES,
        sel_entity_type=entity_type,
        sel_doc_type=doc_type,
        sel_status=status,
    )


@pages_bp.route("/fuel-estimator")
def fuel_estimator():
    from dispatch import services as dispatch_svc
    defaults = {
        "avg_fuel_price": dispatch_svc.get_avg_fuel_price(),
        "fleet_mpg": dispatch_svc.get_fleet_mpg(),
    }
    return render_template("fuel_estimator.html", defaults=defaults)


@pages_bp.route("/fleet")
def fleet():
    from dispatch import services as dispatch_svc
    from dispatch.models import (
        DRIVER_STATUSES, LICENSE_CLASSES,
        EQUIPMENT_TYPES, EQUIPMENT_STATUSES,
    )

    driver_status = request.args.get("driver_status")
    driver_search = request.args.get("driver_name", "").strip()
    equip_status = request.args.get("equip_status")
    equip_type = request.args.get("equip_type")
    equip_search = request.args.get("unit_number", "").strip()

    drivers = dispatch_svc.list_drivers(
        status=driver_status or None,
        name=driver_search or None,
    )
    equipment = dispatch_svc.list_equipment(
        status=equip_status or None,
        equipment_type=equip_type or None,
        unit_number=equip_search or None,
    )
    summary = dispatch_svc.get_fleet_summary()
    from dispatch import store as dispatch_store
    assignments = dispatch_store.get_fleet_assignments()

    return render_template(
        "fleet.html",
        drivers=drivers,
        equipment=equipment,
        summary=summary,
        assignments=assignments,
        driver_statuses=DRIVER_STATUSES,
        license_classes=LICENSE_CLASSES,
        equipment_types=EQUIPMENT_TYPES,
        equipment_statuses=EQUIPMENT_STATUSES,
        driver_status_filter=driver_status or "",
        driver_search=driver_search,
        equip_status_filter=equip_status or "",
        equip_type_filter=equip_type or "",
        equip_search=equip_search,
    )


@pages_bp.route("/fleet/driver/<driver_id>")
def driver_detail(driver_id):
    from dispatch import services as dispatch_svc, store as dispatch_store
    from dispatch.models import DRIVER_STATUSES, LICENSE_CLASSES
    driver = dispatch_svc.get_driver(driver_id)
    if not driver:
        return "Driver not found", 404
    active_load = dispatch_store.get_active_load_for_driver(driver_id)
    load_history = dispatch_store.get_loads_for_driver(driver_id)
    from dispatch.models import PAY_TYPES, PAY_STATUSES
    pay_entries = dispatch_svc.list_driver_pay(driver_id=driver_id)
    pay_summary = dispatch_svc.get_driver_pay_summary(driver_id)
    return render_template(
        "driver_detail.html",
        driver=driver,
        active_load=active_load,
        load_history=load_history,
        pay_entries=pay_entries,
        pay_summary=pay_summary,
        pay_types=PAY_TYPES,
        pay_statuses=PAY_STATUSES,
        driver_statuses=DRIVER_STATUSES,
        license_classes=LICENSE_CLASSES,
    )


@pages_bp.route("/driver-pay")
def driver_pay():
    from dispatch import services as dispatch_svc
    from dispatch.models import PAY_TYPES, PAY_STATUSES
    drivers = dispatch_svc.list_drivers()
    driver_id = request.args.get("driver_id", "")
    pay_period = request.args.get("pay_period", "")
    status_filter = request.args.get("status", "")
    entries = dispatch_svc.list_driver_pay(
        driver_id=driver_id or None,
        status=status_filter or None,
        pay_period=pay_period or None,
    )
    summary = None
    if driver_id:
        summary = dispatch_svc.get_driver_pay_summary(
            driver_id, pay_period=pay_period or None
        )
    return render_template(
        "driver_pay.html",
        drivers=drivers,
        entries=entries,
        summary=summary,
        pay_types=PAY_TYPES,
        pay_statuses=PAY_STATUSES,
        driver_id=driver_id,
        pay_period=pay_period,
        status_filter=status_filter,
    )


@pages_bp.route("/fleet/equipment/<equipment_id>")
def equipment_detail(equipment_id):
    from dispatch import services as dispatch_svc, store as dispatch_store
    from dispatch.models import EQUIPMENT_TYPES, EQUIPMENT_STATUSES
    equip = dispatch_svc.get_equipment(equipment_id)
    if not equip:
        return "Equipment not found", 404
    active_load = dispatch_store.get_active_load_for_equipment(equipment_id)
    load_history = dispatch_store.get_loads_for_equipment(equipment_id)
    from dispatch.models import SERVICE_TYPES, MAINTENANCE_STATUSES
    maint_schedules = dispatch_svc.list_maintenance_schedules(equipment_id=equipment_id)
    return render_template(
        "equipment_detail.html",
        equip=equip,
        active_load=active_load,
        load_history=load_history,
        maint_schedules=maint_schedules,
        service_types=SERVICE_TYPES,
        maintenance_statuses=MAINTENANCE_STATUSES,
        equipment_types=EQUIPMENT_TYPES,
        equipment_statuses=EQUIPMENT_STATUSES,
    )


@pages_bp.route("/billing")
def billing():
    from dispatch import services as dispatch_svc
    from dispatch.models import PAYMENT_METHODS, SETTLEMENT_STATUSES

    status_filter = request.args.get("status")
    customer_search = request.args.get("customer", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    invoice_search = request.args.get("invoice", "").strip()

    settlements = dispatch_svc.list_settlements(
        payment_status=status_filter if status_filter else None,
        customer=customer_search or None,
        date_from=date_from or None,
        date_to=date_to or None,
        invoice_number=invoice_search or None,
    )

    loads_by_id: dict[str, dict] = {}
    for stl in settlements:
        lid = stl["load_id"]
        if lid not in loads_by_id:
            load = dispatch_svc.get_load(lid)
            loads_by_id[lid] = load or {}
        stl["customer"] = loads_by_id[lid].get("customer", "")

    fin_dashboard = dispatch_svc.get_financial_dashboard()
    disputed_count = sum(1 for s in settlements if s["payment_status"] == "disputed")
    written_off_count = sum(1 for s in settlements if s["payment_status"] == "written_off")
    uninvoiced_loads = dispatch_svc.list_uninvoiced_loads()

    return render_template(
        "billing.html",
        settlements=settlements,
        settlement_statuses=SETTLEMENT_STATUSES,
        payment_methods=PAYMENT_METHODS,
        status_filter=status_filter or "",
        customer_search=customer_search,
        date_from=date_from,
        date_to=date_to,
        invoice_search=invoice_search,
        fin_dashboard=fin_dashboard,
        disputed_count=disputed_count,
        written_off_count=written_off_count,
        uninvoiced_loads=uninvoiced_loads,
    )


@pages_bp.route("/exceptions")
def exceptions():
    from dispatch import services as dispatch_svc
    from dispatch.models import EXCEPTION_TYPES, SEVERITY_LEVELS, EXCEPTION_STATUSES

    status_filter = request.args.get("status")
    severity_filter = request.args.get("severity")
    type_filter = request.args.get("exception_type")

    all_exceptions = dispatch_svc.list_exceptions(status=status_filter or None)
    if severity_filter:
        all_exceptions = [e for e in all_exceptions if e.get("severity") == severity_filter]
    if type_filter:
        all_exceptions = [e for e in all_exceptions if e.get("exception_type") == type_filter]

    load_cache: dict[str, dict] = {}
    for exc in all_exceptions:
        lid = exc["load_id"]
        if lid not in load_cache:
            load_cache[lid] = dispatch_svc.get_load(lid) or {}
        exc["customer"] = load_cache[lid].get("customer", "")
        exc["load_status"] = load_cache[lid].get("load_status", load_cache[lid].get("status", ""))

    open_count = sum(1 for e in all_exceptions if e.get("status") == "open") if not status_filter else None
    investigating_count = sum(1 for e in all_exceptions if e.get("status") == "investigating") if not status_filter else None
    critical_count = len([
        e for e in dispatch_svc.list_exceptions(status="open")
        if e.get("severity") == "critical"
    ])
    high_count = len([
        e for e in dispatch_svc.list_exceptions(status="open")
        if e.get("severity") == "high"
    ])

    return render_template(
        "exceptions.html",
        exceptions=all_exceptions,
        exception_types=EXCEPTION_TYPES,
        severity_levels=SEVERITY_LEVELS,
        exception_statuses=EXCEPTION_STATUSES,
        status_filter=status_filter or "",
        severity_filter=severity_filter or "",
        type_filter=type_filter or "",
        open_count=open_count,
        investigating_count=investigating_count,
        critical_count=critical_count,
        high_count=high_count,
    )


@pages_bp.route("/search")
def search():
    from dispatch import services as dispatch_svc
    q = request.args.get("q", "").strip()
    results = None
    total = 0
    if q and len(q) >= 2:
        results = dispatch_svc.global_search(q)
        total = sum(len(v) for v in results.values())
    return render_template(
        "search.html",
        query=q,
        results=results,
        total=total,
    )


@pages_bp.route("/search/loads/<load_id>")
def search_load_detail(load_id):
    """Read-only load lookup (Driver-First Doctrine D6/D9).

    Reachable only from Load Search results. Reuses the same
    get_load_bundle() data assembly as dispatch_detail, but renders it
    through a template with no create/modify/delete/archive/complete/
    dispatch/send affordances -- pure text/tables, so a driver looking
    up a load from search can never accidentally trigger an action.
    The full editable page (dispatch_detail) remains reachable from the
    main Dispatch list, unchanged.
    """
    from dispatch import services as dispatch_svc

    from portal.models import completion_packet as cp_model
    from dispatch import email_helper

    bundle = dispatch_svc.get_load_bundle(load_id)
    if not bundle:
        return redirect(url_for("pages.search"))
    return render_template(
        "load_readonly_detail.html",
        completion_packet=cp_model.get_packet(load_id),
        email_package=email_helper.get_package(load_id),
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

    from dispatch import services as dispatch_svc
    from portal.models import driver_pin_registry as driver_pin_model

    all_drivers = {d["driver_id"]: d for d in dispatch_svc.list_drivers()}
    pin_cards = driver_pin_model.list_pin_cards()
    for card in pin_cards:
        driver = all_drivers.get(card["driver_id"])
        card["driver_name"] = driver.get("name", card["driver_id"]) if driver else "(deleted driver)"
        card["driver_phone"] = driver.get("phone", "") if driver else ""
    drivers_without_cards = [
        d for d in all_drivers.values()
        if d["driver_id"] not in {c["driver_id"] for c in pin_cards}
    ]

    return render_template(
        "library.html", sections=sections,
        driver_pin_cards=pin_cards, drivers_without_cards=drivers_without_cards,
    )


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
    pipeline_archived = []
    pipeline_archive_error = None
    try:
        pipeline_archived = cin_archive.list_contracts()
    except cin_archive.ArchiveIntegrityError as exc:
        pipeline_archive_error = str(exc)

    from dispatch import notifications, services as dispatch_svc
    from portal.models import completion_packet as cp_model

    dispatch_archived = dispatch_svc.list_retentions()
    for ret in dispatch_archived:
        packet = cp_model.get_packet(ret["load_id"])
        ret["email_cluster_doc_count"] = (
            len(packet["email_cluster"]["documents"])
            if packet and packet.get("email_cluster")
            else 0
        )
        ret["stakeholder_url"] = url_for(
            "stakeholder.stakeholder_view", load_id=ret["load_id"],
            token=notifications.make_stakeholder_token(ret["load_id"]), _external=True,
        )

    return render_template(
        "archive.html",
        sections=sections,
        sandbox_archived=sandbox_archived,
        pipeline_archived=pipeline_archived,
        pipeline_archive_error=pipeline_archive_error,
        dispatch_archived=dispatch_archived,
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

    from cin_lite import archive as cin_archive
    from dispatch.db import get_db_path
    from dispatch.services import _STALL_THRESHOLDS_HOURS, _get_upload_dir
    from portal.models import get_data_dir, get_memory_dir, get_archive_dir
    from portal.models import integrations_registry

    storage_paths = {
        "ops_root": os.environ.get("DISPATCH_OPERATIONS_ROOT", ""),
        "archive_root": os.environ.get("DISPATCH_ARCHIVE_ROOT", ""),
        "memory_root": os.environ.get("DISPATCH_MEMORY_ROOT", ""),
        "portal_data": str(get_data_dir().resolve()),
        "database": str(get_db_path().resolve()),
        "uploads": str(_get_upload_dir().resolve()),
        "archive": str(cin_archive.ARCHIVE_ROOT.resolve()),
        "outbox": str((cin_archive.ARCHIVE_ROOT / "Outbox").resolve()),
        "library_intel": str(get_memory_dir().resolve()),
        "archive_records": str(get_archive_dir().resolve()),
    }

    return render_template(
        "settings.html",
        config=Config,
        cin_config=cin_config,
        stall_thresholds=_STALL_THRESHOLDS_HOURS,
        storage_paths=storage_paths,
        integration_entries=integrations_registry.list_entries(),
    )


def _sync_booked_entries(entries: dict) -> None:
    """Pull engine load status into any sandbox entries that have an engine_load_id."""
    from dispatch import services as dispatch_svc

    for sid, entry in entries.items():
        engine_load_id = entry.get("engine_load_id")
        if not engine_load_id:
            continue
        load = dispatch_svc.get_load(engine_load_id)
        if not load:
            continue
        current = entry.get("card_data", {}).get("engine_status")
        if current != load["status"]:
            sandbox.update_engine_status(sid, load["status"])
            entry["card_data"]["engine_status"] = load["status"]


def _priority_key(entry: dict) -> tuple:
    """Sort key: active statuses first, then by score (if available), then by date."""
    status = entry.get("status", "OPEN")
    active = status in ("OPEN", "INTERESTED", "PURSUE", "WATCH", "INQUIRY_DRAFTED", "PUBLISHER_REQUIRED")
    score = entry.get("score") or 0

    decision = entry.get("decision", {})
    priority_map = {"urgent": 4, "high": 3, "medium": 2, "low": 1}
    priority_val = priority_map.get(decision.get("priority", ""), 0)

    return (active, score, priority_val, entry.get("updated_at", ""))
