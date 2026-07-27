"""Tests for the L2-COS Control Layer: stage-transition actions, email, collect."""

from __future__ import annotations

import builtins

import pytest

from l2_cos import control
from l2_cos.models.state import Load, LifecycleStage


def test_available_actions_from_available():
    load = Load(load_id="L-1")
    actions = control.available_actions(load)
    assert set(actions) == {"BOOKED", control.HOLD_ACTION}


def test_available_actions_terminal_stage_only_hold():
    load = Load(load_id="L-1", stage=LifecycleStage.CLOSED)
    actions = control.available_actions(load)
    assert set(actions) == {control.HOLD_ACTION}


def test_resolve_advances_to_target():
    load = Load(load_id="L-1")
    target = control.resolve("BOOKED", load)
    assert target == LifecycleStage.BOOKED


def test_resolve_hold_returns_none():
    load = Load(load_id="L-1")
    assert control.resolve(control.HOLD_ACTION, load) is None


def test_resolve_illegal_action_raises():
    load = Load(load_id="L-1")
    with pytest.raises(ValueError):
        control.resolve("LOADED", load)  # not the single legal next stage


def test_render_email_contains_all_sections(clean_broker, clean_facility):
    load = Load(load_id="L-1", intelligence_score=95, broker_id="BRK-001")
    intelligence = {"lane_fit": {"score": 100, "flags": ["preferred_lane_match"], "findings": {}}}
    email = control.render_email(load, intelligence, clean_facility, clean_facility, clean_broker)

    assert "Load        : L-1" in email
    assert "Broker      : Acme Logistics" in email
    assert "Module scores:" in email
    assert "Flags raised: preferred_lane_match" in email
    assert "publisher-eligible" in email
    assert "[ ] BOOKED" in email


def test_render_email_below_threshold_and_no_intelligence():
    load = Load(load_id="L-2", intelligence_score=40)
    email = control.render_email(load, {})
    assert "below publish threshold" in email
    assert "Flags raised: none" in email


def test_render_email_without_score():
    load = Load(load_id="L-3")
    email = control.render_email(load, {})
    assert "Intelligence score" not in email


def test_collect_non_interactive_default():
    actions = {"BOOKED": "Confirm Booked", control.HOLD_ACTION: "Hold"}
    assert control.collect(actions, default="BOOKED") == "BOOKED"


def test_collect_rejects_invalid_then_accepts(monkeypatch):
    actions = {"BOOKED": "Confirm Booked", control.HOLD_ACTION: "Hold"}
    answers = iter(["nonsense", "BOOKED"])
    monkeypatch.setattr(builtins, "input", lambda *_: next(answers))
    assert control.collect(actions) == "BOOKED"
