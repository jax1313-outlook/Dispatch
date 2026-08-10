"""Tests for Dispatch Manager -- Stage 12 build, per
DISPATCH_STAGE12_MANAGER_BUILD_DESIGN_v1.md.
"""

from __future__ import annotations

import inspect

import pytest

from dispatch import db, services
from dispatch.manager import classify, priority, security_monitor, signals, staff_report
from dispatch.spine.store import get_work_item, list_portal_cards
from portal.models import conflict as conflict_model


@pytest.fixture(autouse=True)
def isolated_dispatch_state(tmp_path, monkeypatch):
    """Redirect both the SQLite dispatch.db and Conflict Notice's
    JSON-file portal data store to a per-test temp directory -- the
    two storage mechanisms Manager reads from need separate isolation.
    """
    db.set_db_path(tmp_path / "dispatch.db")
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal_data"))
    yield
    db.set_db_path(None)


# ── Fixture builders ────────────────────────────────────────────────────

def _make_stalled_load(hours_past_threshold_multiple: float = 1.2) -> dict:
    load = services.create_load(customer="Test Customer")
    # default "created" threshold is 24h; back-date updated_at accordingly.
    hours_ago = 24 * hours_past_threshold_multiple
    from datetime import datetime, timedelta, timezone

    stale_ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    from dispatch import store

    store.update_load(load["load_id"], updated_at=stale_ts)
    return load


def _make_overdue_settlement(days_overdue: int = 3) -> dict:
    load = services.create_load(customer="Overdue Customer")
    from datetime import datetime, timedelta, timezone

    due = (datetime.now(timezone.utc) - timedelta(days=days_overdue)).strftime("%Y-%m-%d")
    stl = services.create_settlement(load["load_id"], due_date=due)
    services.update_settlement(load["load_id"], payment_status="overdue")
    return stl


def _make_open_exception(severity: str = "medium") -> dict:
    load = services.create_load(customer="Exception Customer")
    return services.open_exception(load["load_id"], severity=severity, description="test")


def _make_conflict_notice(severity: str = "warning", human_decision_required: bool = True) -> dict:
    return conflict_model.create_notice(
        conflict_type="missing_rate",
        severity=severity,
        sandbox_id="SBX-TEST-001",
        explanation="Test conflict",
        recommended_action="Review",
        human_decision_required=human_decision_required,
    )


def _make_suspect_ifta_entry() -> dict:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    purchase = services.add_ifta_fuel_purchase(
        jurisdiction="TX",
        gallons=100.0,
        amount=350.0,
        date=now.strftime("%Y-%m-%d"),
        vehicle_id="TRUCK-1",
        extraction_confidence=0.3,
    )
    return purchase


def _make_draft_ifta_approval_with_exception(status: str = "draft") -> tuple[dict, dict]:
    from dispatch import store
    from dispatch.models import IFTAException, IFTAReportApproval

    approval = store.create_ifta_report_approval(
        IFTAReportApproval(year=2026, quarter=1, status=status)
    )
    exc = store.create_ifta_exception(
        IFTAException(
            approval_id=approval["approval_id"],
            exception_type="fuel_no_miles",
            detail="Test IFTA exception",
        )
    )
    return approval, exc


def _make_security_events(event_type: str, count: int, *, user_id: str | None = None,
                           display_name: str | None = None, path: str | None = None) -> None:
    from dispatch.security.models import SecurityEvent
    from dispatch.security.store import create_security_event

    details = {}
    if display_name:
        details["display_name"] = display_name
    if path:
        details["path"] = path
    for _ in range(count):
        create_security_event(
            SecurityEvent(event_type=event_type, user_id=user_id, details=details)
        )


# ── Signal aggregation ───────────────────────────────────────────────────

def test_empty_state_produces_no_signals():
    assert signals.collect_signals() == []


def test_stalled_load_detected():
    load = _make_stalled_load()
    raw = signals.collect_signals()
    matches = [s for s in raw if s["source_type"] == signals.STALLED_LOAD]
    assert len(matches) == 1
    assert matches[0]["source_id"] == load["load_id"]


def test_overdue_settlement_detected():
    stl = _make_overdue_settlement()
    raw = signals.collect_signals()
    matches = [s for s in raw if s["source_type"] == signals.OVERDUE_SETTLEMENT]
    assert len(matches) == 1
    assert matches[0]["source_id"] == stl["load_id"]


def test_open_exception_detected():
    exc = _make_open_exception()
    raw = signals.collect_signals()
    matches = [s for s in raw if s["source_type"] == signals.OPEN_EXCEPTION]
    assert len(matches) == 1
    assert matches[0]["source_id"] == exc["exception_id"]


def test_resolved_exception_not_detected():
    exc = _make_open_exception()
    services.resolve_exception(exc["exception_id"])
    raw = signals.collect_signals()
    assert not [s for s in raw if s["source_type"] == signals.OPEN_EXCEPTION]


def test_unresolved_conflict_detected():
    notice = _make_conflict_notice()
    raw = signals.collect_signals()
    matches = [s for s in raw if s["source_type"] == signals.UNRESOLVED_CONFLICT]
    assert len(matches) == 1
    assert matches[0]["source_id"] == notice["id"]


def test_resolved_conflict_not_detected():
    notice = _make_conflict_notice()
    conflict_model.resolve_notice(notice["id"])
    raw = signals.collect_signals()
    assert not [s for s in raw if s["source_type"] == signals.UNRESOLVED_CONFLICT]


def test_ifta_suspect_entry_detected():
    purchase = _make_suspect_ifta_entry()
    raw = signals.collect_signals()
    matches = [s for s in raw if s["source_type"] == signals.IFTA_SUSPECT_ENTRY]
    assert len(matches) == 1
    assert matches[0]["source_id"] == purchase["purchase_id"]


# ── Phase M5: IFTA exceptions (draft approvals only) ──────────────────────

def test_ifta_exception_on_draft_approval_detected():
    _approval, exc = _make_draft_ifta_approval_with_exception(status="draft")
    raw = signals.collect_signals()
    matches = [s for s in raw if s["source_type"] == signals.IFTA_EXCEPTION]
    assert len(matches) == 1
    assert matches[0]["source_id"] == exc["exception_id"]


def test_ifta_exception_on_sealed_approval_not_detected():
    _make_draft_ifta_approval_with_exception(status="sealed")
    raw = signals.collect_signals()
    assert not [s for s in raw if s["source_type"] == signals.IFTA_EXCEPTION]


# ── Phase M6: security event patterns ──────────────────────────────────────

def test_login_failure_below_threshold_produces_no_pattern():
    _make_security_events("LOGIN_FAILURE", 2, user_id="USER-X")
    raw = signals.collect_signals()
    assert not [s for s in raw if s["source_type"] == security_monitor.SECURITY_PATTERN]


def test_login_failure_at_threshold_produces_one_pattern():
    _make_security_events("LOGIN_FAILURE", 3, user_id="USER-X")
    raw = signals.collect_signals()
    matches = [s for s in raw if s["source_type"] == security_monitor.SECURITY_PATTERN]
    assert len(matches) == 1
    assert matches[0]["data"]["event_type"] == "LOGIN_FAILURE"
    assert matches[0]["data"]["count"] == 3


def test_unknown_identity_and_known_identity_failures_not_conflated():
    """A wrong-PIN attempt (user_id set) and an unknown-identity
    attempt (user_id None, keyed by display_name) must never merge
    into the same pattern, even if a human later realizes they're the
    same person -- different risk shapes, different keys."""
    _make_security_events("LOGIN_FAILURE", 2, user_id="USER-X")
    _make_security_events("LOGIN_FAILURE", 2, display_name="Mike")
    raw = signals.collect_signals()
    matches = [s for s in raw if s["source_type"] == security_monitor.SECURITY_PATTERN]
    assert matches == []  # 2 + 2, neither group alone reaches the threshold of 3


def test_permission_denied_pattern_grouped_by_user_and_path():
    _make_security_events("PERMISSION_DENIED", 3, user_id="USER-Y", path="/settings")
    raw = signals.collect_signals()
    matches = [s for s in raw if s["source_type"] == security_monitor.SECURITY_PATTERN]
    assert len(matches) == 1
    assert matches[0]["data"]["event_type"] == "PERMISSION_DENIED"


def test_security_monitor_never_calls_security_write_functions():
    """Structural guard: security_monitor.py must call exactly
    list_security_events() and nothing else in dispatch.security."""
    source = inspect.getsource(security_monitor)
    forbidden = (
        "create_user_with_pin", "change_pin", "reset_pin", "revoke_pin",
        "create_session", "revoke_session", "auth.login(",
    )
    for name in forbidden:
        assert name not in source


def test_check_overdue_settlements_never_called_directly():
    """Structural guard: signals.py must read already-overdue
    settlements, never call the mutating check_overdue_settlements()
    (which marks settlements overdue and sends an email as a side
    effect) -- confirmed by source scan, not just behavior."""
    source = inspect.getsource(signals)
    assert "services.check_overdue_settlements(" not in source


# ── Classification ───────────────────────────────────────────────────────

def test_stalled_load_below_multiple_classifies_status():
    _make_stalled_load(hours_past_threshold_multiple=1.1)
    raw = [s for s in signals.collect_signals() if s["source_type"] == signals.STALLED_LOAD][0]
    classified = classify.classify_signal(raw)
    assert classified["classification"] == classify.STATUS
    assert classified["card_level"] == 1


def test_stalled_load_above_multiple_classifies_decision_needed():
    _make_stalled_load(hours_past_threshold_multiple=2.5)
    raw = [s for s in signals.collect_signals() if s["source_type"] == signals.STALLED_LOAD][0]
    classified = classify.classify_signal(raw)
    assert classified["classification"] == classify.DECISION_NEEDED
    assert classified["card_level"] == 3


def test_open_exception_severity_maps_to_classification():
    cases = {
        "low": classify.REVIEW_NEEDED,
        "medium": classify.REVIEW_NEEDED,
        "high": classify.DECISION_NEEDED,
        "critical": classify.CONFLICT,
    }
    for severity, expected in cases.items():
        raw = {
            "source_type": signals.OPEN_EXCEPTION, "source_id": "x",
            "data": {"severity": severity, "load_id": "LOAD-X"},
        }
        assert classify.classify_signal(raw)["classification"] == expected


def test_unresolved_conflict_card_level_maps_to_classification():
    notice = _make_conflict_notice(severity="critical", human_decision_required=True)
    raw = [s for s in signals.collect_signals() if s["source_type"] == signals.UNRESOLVED_CONFLICT][0]
    classified = classify.classify_signal(raw)
    assert notice["card_level"] == 4
    assert classified["classification"] == classify.CONFLICT


def test_ifta_suspect_entry_classifies_review_needed():
    _make_suspect_ifta_entry()
    raw = [s for s in signals.collect_signals() if s["source_type"] == signals.IFTA_SUSPECT_ENTRY][0]
    assert classify.classify_signal(raw)["classification"] == classify.REVIEW_NEEDED


def test_ifta_exception_classifies_review_needed():
    _make_draft_ifta_approval_with_exception()
    raw = [s for s in signals.collect_signals() if s["source_type"] == signals.IFTA_EXCEPTION][0]
    assert classify.classify_signal(raw)["classification"] == classify.REVIEW_NEEDED


def test_security_pattern_always_classifies_conflict():
    _make_security_events("LOGIN_FAILURE", 3, user_id="USER-X")
    raw = [s for s in signals.collect_signals() if s["source_type"] == security_monitor.SECURITY_PATTERN][0]
    assert classify.classify_signal(raw)["classification"] == classify.CONFLICT


def test_clears_review_bar_threshold():
    assert classify.clears_review_bar({"card_level": 2}) is True
    assert classify.clears_review_bar({"card_level": 1}) is False
    assert classify.clears_review_bar({"card_level": 0}) is False


# ── Priority ranking ──────────────────────────────────────────────────────

def test_ifta_exception_and_security_pattern_are_tier_one():
    ifta_signal = {"source_type": signals.IFTA_EXCEPTION, "classification": classify.REVIEW_NEEDED, "card_level": 2}
    security_signal = {"source_type": security_monitor.SECURITY_PATTERN, "classification": classify.CONFLICT, "card_level": 4}
    for signal in (ifta_signal, security_signal):
        assert priority.assign_priority(signal)["priority_tier"] == priority.TIER_SAFETY_SECURITY_LEGAL_COMPLIANCE_AUTHORITY


def test_tier_one_always_ranks_above_lower_tiers_regardless_of_card_level():
    tier1_low_level = {
        "source_type": signals.IFTA_SUSPECT_ENTRY, "classification": classify.REVIEW_NEEDED,
        "card_level": 2,
    }
    tier5_high_level = {
        "source_type": signals.STALLED_LOAD, "classification": classify.DECISION_NEEDED,
        "card_level": 3,
    }
    ranked = priority.rank([tier5_high_level, tier1_low_level])
    assert ranked[0]["source_type"] == signals.IFTA_SUSPECT_ENTRY


def test_within_tier_tiebreak_by_card_level_descending():
    a = {"source_type": signals.STALLED_LOAD, "classification": classify.STATUS, "card_level": 1}
    b = {"source_type": signals.STALLED_LOAD, "classification": classify.DECISION_NEEDED, "card_level": 3}
    ranked = priority.rank([a, b])
    assert ranked[0]["card_level"] == 3


# ── Spine interaction ──────────────────────────────────────────────────────

def test_materialized_work_item_reaches_portal_card_created_via_allowed_path():
    _make_conflict_notice(severity="critical")
    report = staff_report.generate_staff_report()
    assert len(report["cards"]) == 1
    card = report["cards"][0]
    work_item = get_work_item(card["work_item_id"])
    assert work_item["current_state"] == "PORTAL_CARD_CREATED"


def test_portal_card_has_fixed_required_closing():
    _make_conflict_notice(severity="critical")
    report = staff_report.generate_staff_report()
    card = report["cards"][0]
    assert card["required_closing"] == (
        "This is a recommendation only. No action is authorized. Mike decides."
    )


def test_status_and_routine_signals_never_materialize_a_work_item():
    _make_stalled_load(hours_past_threshold_multiple=1.1)  # Status, card_level 1
    report = staff_report.generate_staff_report()
    assert report["cards"] == []
    assert report["counts"].get(classify.STATUS) == 1


def test_never_touches_routed_to_manager_state():
    """No Work Item this build creates should ever pass through
    ROUTED_TO_MANAGER -- confirmed directly against persisted state,
    not just against the transition path constant."""
    _make_conflict_notice(severity="critical")
    report = staff_report.generate_staff_report()
    work_item = get_work_item(report["cards"][0]["work_item_id"])
    assert work_item["current_state"] != "ROUTED_TO_MANAGER"


# ── Dedup ──────────────────────────────────────────────────────────────

def test_second_run_does_not_duplicate_work_items():
    """The card stays visible on every pass (it's still unresolved),
    but no *second* Work Item/Card is created for the same signal --
    dedup blocks re-materialization, it doesn't blank the display."""
    from dispatch.spine.store import list_work_items

    _make_conflict_notice(severity="critical")
    first = staff_report.generate_staff_report()
    second = staff_report.generate_staff_report()
    assert len(first["cards"]) == 1
    assert len(second["cards"]) == 1
    assert first["cards"][0]["card_id"] == second["cards"][0]["card_id"]
    assert len(list_work_items()) == 1


def test_two_distinct_signals_each_materialize_once():
    _make_conflict_notice(severity="critical")
    _make_open_exception(severity="critical")
    report = staff_report.generate_staff_report()
    assert len(report["cards"]) == 2


def test_ifta_exception_second_run_does_not_duplicate():
    from dispatch.spine.store import list_work_items

    _make_draft_ifta_approval_with_exception()
    staff_report.generate_staff_report()
    staff_report.generate_staff_report()
    assert len(list_work_items()) == 1


def test_security_pattern_second_run_same_day_does_not_duplicate():
    from dispatch.spine.store import list_work_items

    _make_security_events("LOGIN_FAILURE", 3, user_id="USER-X")
    first = staff_report.generate_staff_report()
    second = staff_report.generate_staff_report()
    assert len(first["cards"]) == 1
    assert len(second["cards"]) == 1
    assert len(list_work_items()) == 1


# ── Structural guards ─────────────────────────────────────────────────────

def test_manager_never_writes_current_state_directly():
    """Source-scan guard, matching the codebase's existing convention
    (e.g. dispatch/security/'s no-plaintext-PIN guard): Manager code
    must never contain a raw work_items UPDATE -- apply_transition()
    is the only allowed path."""
    for module in (signals, classify, priority, staff_report, security_monitor):
        source = inspect.getsource(module)
        assert "UPDATE work_items" not in source
        assert "current_state=" not in source
    assert "apply_transition" in inspect.getsource(staff_report)


def test_manager_never_calls_security_write_functions():
    forbidden = (
        "create_user_with_pin", "change_pin", "reset_pin", "revoke_pin",
        "create_session", "revoke_session", "auth.login(",
    )
    for module in (staff_report, signals, security_monitor):
        source = inspect.getsource(module)
        for name in forbidden:
            assert name not in source


def test_manager_never_calls_approval_or_booking_functions():
    source = inspect.getsource(staff_report)
    forbidden = ("create_approval_event", "book", "approve_ifta_quarter", "deliver_decision")
    for name in forbidden:
        assert name not in source


def test_manager_route_is_get_only():
    import portal.routes.manager as manager_route_module

    source = inspect.getsource(manager_route_module)
    assert "methods=" not in source  # no explicit methods list -> Flask default GET-only


# ── Portal rendering ──────────────────────────────────────────────────────

@pytest.fixture
def client():
    from portal.app import create_app

    app = create_app({"TESTING": True, "SECRET_KEY": "test"})
    return app.test_client()


def test_manager_page_renders_empty_state(client):
    resp = client.get("/manager")
    assert resp.status_code == 200
    assert b"Nothing needs your attention" in resp.data


def test_manager_page_renders_cards_and_counts(client):
    _make_conflict_notice(severity="critical")
    _make_stalled_load(hours_past_threshold_multiple=1.1)  # Status only, no card
    resp = client.get("/manager")
    html = resp.data.decode()
    assert resp.status_code == 200
    assert "Test conflict" in html
    assert "Status" in html  # summary count label present


def test_level_one_signal_never_appears_as_individual_card(client):
    _make_stalled_load(hours_past_threshold_multiple=1.1)  # Status, card_level 1
    resp = client.get("/manager")
    html = resp.data.decode()
    assert "Cards Needing Attention" not in html


# ── Phase M4: Stage Gate (docs/STAGE_STATUS.json mirror) ──────────────────

@pytest.fixture
def isolated_status_file(tmp_path, monkeypatch):
    """Redirects stage_gate's mirror-file path to an isolated tmp file
    so tests never read or depend on the real docs/STAGE_STATUS.json."""
    from dispatch.manager import stage_gate

    path = tmp_path / "STAGE_STATUS.json"
    monkeypatch.setattr(stage_gate, "_STATUS_FILE", path)
    return path


def _write_status(path, **overrides):
    import json as json_mod

    payload = {
        "schema_version": 1,
        "last_synced": "2026-08-10T00:00:00Z",
        "synced_from": "test",
        "stages": [
            {"number": 1, "name": "Test Stage", "status": "approved", "depends_on": [],
             "blocked": False, "blocked_reason": None, "open_questions": [],
             "test_status": None, "walkthrough_reports": []},
        ],
        "next_recommended_stage": 1,
        "next_recommended_reason": "test",
    }
    payload.update(overrides)
    path.write_text(json_mod.dumps(payload))


def test_stage_gate_missing_file_returns_none(isolated_status_file):
    from dispatch.manager import stage_gate

    assert stage_gate.build_summary() is None


def test_stage_gate_malformed_json_returns_none(isolated_status_file):
    from dispatch.manager import stage_gate

    isolated_status_file.write_text("{not valid json")
    assert stage_gate.build_summary() is None


def test_stage_gate_wrong_schema_version_returns_none(isolated_status_file):
    from dispatch.manager import stage_gate

    _write_status(isolated_status_file, schema_version=2)
    assert stage_gate.build_summary() is None


def test_stage_gate_well_formed_no_blocked_stages(isolated_status_file):
    from dispatch.manager import stage_gate

    _write_status(isolated_status_file)
    summary = stage_gate.build_summary()
    assert summary is not None
    assert summary["card_level"] == 1
    assert summary["blocked_stages"] == []
    assert summary["next_recommended_stage"] == 1


def test_stage_gate_blocked_stage_bumps_card_level(isolated_status_file):
    from dispatch.manager import stage_gate

    _write_status(isolated_status_file, stages=[
        {"number": 6, "name": "Archive/IFTA", "status": "redefined_analysis_only_delivered",
         "depends_on": [4], "blocked": True, "blocked_reason": "Needs Mike authorization",
         "open_questions": [], "test_status": None, "walkthrough_reports": []},
    ])
    summary = stage_gate.build_summary()
    assert summary["card_level"] == 2
    assert len(summary["blocked_stages"]) == 1
    assert summary["blocked_stages"][0]["blocked_reason"] == "Needs Mike authorization"


def test_stage_gate_never_writes_to_docs():
    """Structural guard: stage_gate.py must never write to docs/ or
    anywhere else -- read-only against one local file."""
    from dispatch.manager import stage_gate

    source = inspect.getsource(stage_gate)
    assert 'open(' not in source  # uses Path.read_text(), no raw open() at all
    assert '"w"' not in source
    assert "'w'" not in source


def test_manager_page_renders_without_stage_gate_panel_when_file_missing(client, isolated_status_file):
    """The core, already-shipped signal pipeline must be provably
    unaffected by a missing mirror file -- this is the whole point of
    failing soft."""
    resp = client.get("/manager")
    assert resp.status_code == 200
    assert b"Stage Gate Status" not in resp.data
    assert b"Nothing needs your attention" in resp.data


def test_manager_page_renders_stage_gate_panel_when_file_present(client, isolated_status_file):
    _write_status(isolated_status_file)
    resp = client.get("/manager")
    html = resp.data.decode()
    assert resp.status_code == 200
    assert "Stage Gate Status" in html
    assert "Recommended next stage" in html
    assert "Cards Needing Attention" not in html
