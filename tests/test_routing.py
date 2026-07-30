"""Tests for the routing-decision agent (deterministic + Claude code path)."""

from __future__ import annotations

import json

from cin_lite.agents import router
from cin_lite.control import ACTIONS


def _decision_shape_ok(d: dict) -> bool:
    return (
        d["action"] in ACTIONS
        and d["priority"] in router.PRIORITIES
        and all(isinstance(d[k], str) and d[k] for k in ("reason", "recipient", "notes"))
    )


def test_decision_shape(mapped_contract, intelligence, flags):
    d = router.decide(mapped_contract, intelligence, "summary", flags)
    assert _decision_shape_ok(d)


def test_set_aside_routes_to_proposal(mapped_contract, intelligence, flags):
    # Rich contract has a qualifying 8(a) set-aside -> approve_proposal.
    d = router.decide(mapped_contract, intelligence, "summary", flags)
    assert d["action"] == "approve_proposal"
    assert d["recipient"] == "proposal-team"
    assert d["priority"] in ("high", "medium")


def test_value_anomaly_routes_to_review():
    intel = {"set_aside_detection": {"findings": {"set_asides": ["8(a)"]}}}
    d = router._deterministic_decision(intel, ["set_aside_present", "value_above_band"])
    assert d["action"] == "flag_review"
    assert d["priority"] == "high"


def test_missing_value_is_not_an_anomaly():
    intel = {"set_aside_detection": {"findings": {"set_asides": ["8(a)"]}}}
    d = router._deterministic_decision(intel, ["set_aside_present", "value_missing"])
    assert d["action"] == "approve_proposal"
    assert "no estimated value published" in d["notes"]


def test_no_set_aside_routes_to_deeper_analysis():
    d = router._deterministic_decision({}, ["full_and_open_or_unspecified"])
    assert d["action"] == "deeper_analysis"


def test_claude_success_path(mapped_contract, intelligence, flags, install_anthropic):
    canned = {
        "action": "approve_proposal",
        "reason": "Strong fit.",
        "priority": "high",
        "recipient": "anything",  # should be normalized to canonical queue
        "notes": "n/a",
    }
    install_anthropic(json.dumps(canned))
    d = router.decide(mapped_contract, intelligence, "summary", flags)
    assert d["action"] == "approve_proposal"
    assert d["recipient"] == "proposal-team"  # normalized


def test_claude_invalid_json_falls_back(mapped_contract, intelligence, flags, install_anthropic):
    install_anthropic("not json at all")
    d = router.decide(mapped_contract, intelligence, "summary", flags)
    assert _decision_shape_ok(d)  # deterministic fallback


def test_claude_invalid_action_falls_back(mapped_contract, intelligence, flags, install_anthropic):
    install_anthropic(json.dumps({"action": "nope", "reason": "x", "priority": "high",
                                  "recipient": "x", "notes": "x"}))
    d = router.decide(mapped_contract, intelligence, "summary", flags)
    assert d["action"] in ACTIONS  # fell back to a valid action
