"""Tests for Workstream 2: Route Risk Foundation."""

from __future__ import annotations

import pytest
from dispatch import services as dispatch_svc
from dispatch import route_risk


@pytest.fixture(autouse=True)
def _clear_route_risk_events():
    route_risk._ROUTE_RISK_EVENTS.clear()
    yield
    route_risk._ROUTE_RISK_EVENTS.clear()


def test_get_route_risk_default_stub():
    res = route_risk.get_route_risk("LOAD-999")
    assert res["load_id"] == "LOAD-999"
    assert res["available"] is False
    assert res["consequence_level"] == 0
    assert res["is_live_data"] is False
    assert "No active Route Risk events" in res["summary"]


def test_record_route_risk_event_minor():
    route_risk._ROUTE_RISK_EVENTS.clear()
    event = route_risk.record_route_risk_event(
        load_id="LOAD-201",
        condition_summary="Heavy rain near Glynn County, GA.",
        consequence_level=1,
        estimated_delay_minutes=15,
        delivery_commitment_status="achievable",
        affected_area="Glynn County, GA",
    )
    assert event["load_id"] == "LOAD-201"
    assert event["consequence_level"] == 1
    assert event["estimated_delay_minutes"] == 15
    assert event["driver_notification_required"] is True
    assert event["stakeholder_notification_required"] is False
    assert event["is_live_data"] is False

    risk = route_risk.get_route_risk("LOAD-201")
    assert risk["available"] is True
    assert risk["consequence_level"] == 1
    assert risk["summary"] == "Heavy rain near Glynn County, GA."


def test_record_route_risk_event_significant():
    event = route_risk.record_route_risk_event(
        load_id="LOAD-202",
        condition_summary="Severe storm & flooding on I-95 corridor.",
        consequence_level=3,
        estimated_delay_minutes=150,
        delivery_commitment_status="at_risk",
        affected_corridor="I-95 South",
    )
    assert event["consequence_level"] == 3
    assert event["delivery_commitment_status"] == "at_risk"
    assert event["stakeholder_notification_required"] is True
    assert event["comi_required"] is True
    assert event["map_visual_placeholder"]["available"] is True
    assert event["is_live_data"] is False
