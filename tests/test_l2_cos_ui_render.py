"""Tests for the Operations Portal's stdlib HTML rendering."""

from __future__ import annotations

from datetime import datetime, timezone

from l2_cos.ui import cards, render, repository, sandbox
from l2_cos.models.intelligence import BrokerIntelligence, LocationIntelligence
from l2_cos.models.state import Load, LifecycleStage


def _bundle(load_id="L-1", score=93):
    facility = LocationIntelligence(
        facility_id="FAC-1", name="Test DC", address="1 Rd",
        historical_problems=["late gate"], security_requirements="TWIC",
    )
    broker = BrokerIntelligence(broker_id="BRK-1", company_name="Test Broker", payment_terms="Net 90")
    load = Load(load_id=load_id, intelligence_score=score)
    return repository.LoadBundle(
        load_id=load_id,
        raw_load={"origin": "Riverside, CA", "destination": "Dallas, TX", "equipment_type": "Dry Van",
                   "rate_per_mile": 2.2, "deadhead_miles": 40},
        intelligence={"lane_fit": {"score": 100, "flags": ["preferred_lane_match"], "findings": {}},
                      "broker_risk": {"score": 40, "flags": ["slow_payment_terms"], "findings": {}}},
        overall_score=score,
        load=load,
        facility_pickup=facility,
        facility_delivery=facility,
        broker=broker,
        publisher_result=None,
    )


def test_render_dashboard_lists_cards_and_empty_state():
    bundle = _bundle()
    card = cards.build_card(bundle)
    html = render.render_dashboard([card])
    assert "L2-COS Operations Portal" in html
    assert card.load_id in html
    assert "HIGH VALUE MATCH" in html

    empty_html = render.render_dashboard([])
    assert "No loads in the Archive yet." in empty_html


def test_render_card_shows_red_flags_and_links():
    bundle = _bundle()
    card = cards.build_card(bundle)
    html = render.render_card(card)
    assert "late gate" in html
    assert "TWIC" in html
    assert f"/loads/{card.load_id}/brief" in html
    assert f"/loads/{card.load_id}/draft" in html
    assert f"/loads/{card.load_id}/source" in html
    assert f"/loads/{card.load_id}/lifecycle" in html


def test_render_brief_contains_key_facts():
    bundle = _bundle()
    card = cards.build_card(bundle)
    html = render.render_brief(bundle, card)
    assert "Brief" in html
    assert "Test DC" in html
    assert "2.2" in html


def test_render_draft_contains_modules_and_history():
    bundle = _bundle()
    bundle.load.advance(LifecycleStage.BOOKED, actor="tester")
    card = cards.build_card(bundle)
    html = render.render_draft(bundle, card)
    assert "lane_fit" in html
    assert "preferred_lane_match" in html
    assert "BOOKED" in html
    assert "tester" in html


def test_render_draft_no_history_yet():
    bundle = _bundle()
    card = cards.build_card(bundle)
    html = render.render_draft(bundle, card)
    assert "none yet" in html


def test_render_source_contains_raw_json():
    bundle = _bundle()
    html = render.render_source(bundle)
    assert "Riverside, CA" in html
    assert "<pre>" in html


def test_render_lifecycle_contains_action_form():
    bundle = _bundle()
    from l2_cos import control

    actions = control.available_actions(bundle.load)
    html = render.render_lifecycle(bundle, actions)
    assert "AVAILABLE" in html
    assert 'value="BOOKED"' in html


def test_render_locations_and_brokers_tables():
    facility = LocationIntelligence(facility_id="FAC-1", name="Test DC", address="1 Rd")
    broker = BrokerIntelligence(broker_id="BRK-1", company_name="Test Broker", historical_rates={"CA-TX": 2.1})

    locations_html = render.render_locations({"FAC-1": facility})
    assert "Test DC" in locations_html
    assert "none" in locations_html  # no historical problems for this facility

    brokers_html = render.render_brokers({"BRK-1": broker})
    assert "Test Broker" in brokers_html
    assert "CA-TX: 2.1" in brokers_html


def test_render_publisher_alerts_shows_hold_and_status():
    entry = sandbox.SandboxEntry(load_id="L-1", entered_at=datetime.now(timezone.utc), sent=True)
    html = render.render_publisher_alerts([(entry, sandbox.ACTIVE)])
    assert "L-1" in html
    assert str(sandbox.SANDBOX_HOLD_HOURS) in html
    assert "active" in html


def test_render_publisher_alerts_empty():
    html = render.render_publisher_alerts([])
    assert "Publisher Alerts" in html
