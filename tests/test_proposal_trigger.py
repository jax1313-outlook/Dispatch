"""Tests for the Phase 2 proposal-trigger workflow."""

from __future__ import annotations

import json

from cin_lite.agents import proposal_writer
from cin_lite.workflows import proposal


def test_is_triggered():
    assert proposal.is_triggered("approve_proposal") is True
    for other in ("approve_archive", "reject", "flag_review", "deeper_analysis"):
        assert proposal.is_triggered(other) is False


def test_milestones_computed_backward_from_deadline():
    ms = proposal._milestones("2026-08-15T17:00:00-04:00")
    by_name = {m["name"]: m["date"] for m in ms}
    assert by_name == {
        "kickoff": "2026-08-01",
        "draft_complete": "2026-08-08",
        "internal_review": "2026-08-12",
        "submit": "2026-08-14",
    }


def test_milestones_empty_for_unparseable_date():
    assert proposal._milestones(None) == []
    assert proposal._milestones("not-a-date") == []


def test_build_brief(mapped_contract, intelligence, flags):
    decision = {"priority": "high", "recipient": "proposal-team"}
    brief = proposal.build_brief(mapped_contract, "CIN-20260627-ABCD1234",
                                 intelligence, decision, "summary", flags)
    assert brief["proposal_id"] == "PROP-20260627-ABCD1234"
    assert brief["status"] == "initiated"
    assert brief["priority"] == "high"
    assert brief["assigned_to"] == "proposal-team"
    assert len(brief["milestones"]) == 4
    assert "541512" in brief["naics"]
    # checklist derived from intelligence
    joined = " ".join(brief["requirements_checklist"]).lower()
    assert "set-aside" in joined
    assert any("bid/no-bid" in item.lower() for item in brief["requirements_checklist"])


def test_trigger_persists_and_returns(tmp_archive, mapped_contract, intelligence, flags):
    decision = {"priority": "high", "recipient": "proposal-team"}
    result = proposal.trigger(mapped_contract, "CIN-20260627-ABCD1234",
                              intelligence, decision, "summary", flags)

    assert result["proposal_id"] == "PROP-20260627-ABCD1234"
    assert result["json_path"].exists()
    assert result["outline_path"].exists()
    assert result["outline_path"].suffix == ".md"
    assert isinstance(result["email_status"], str)

    saved = json.loads(result["json_path"].read_text(encoding="utf-8"))
    assert saved["proposal_id"] == "PROP-20260627-ABCD1234"
    assert "outline" in saved and saved["outline"]

    outline = result["outline_path"].read_text(encoding="utf-8")
    assert "Proposal Outline" in outline
    assert "Compliance Matrix" in outline


def test_trigger_kickoff_email_written_offline(tmp_archive, mapped_contract, intelligence, flags):
    decision = {"priority": "high", "recipient": "proposal-team"}
    result = proposal.trigger(mapped_contract, "CIN-X", intelligence, decision, "summary", flags)
    assert "written to" in result["email_status"]
    eml = tmp_archive / "Outbox" / "PROP-X-kickoff.eml"
    assert eml.exists()
    body = eml.read_text(encoding="utf-8")
    assert "Proposal kickoff" in body


# --------------------------------------------------------------------------- proposal-writer agent

def test_outline_deterministic(mapped_contract, intelligence):
    brief = {"response_deadline": "2026-08-15", "flags": ["value_missing"]}
    out = proposal_writer.draft_outline(mapped_contract, intelligence, brief, "summary")
    assert "Proposal Outline" in out
    assert "Compliance Matrix" in out
    assert "Win Themes" in out


def test_outline_claude_success(mapped_contract, intelligence, install_anthropic):
    install_anthropic("# Custom Claude Outline")
    out = proposal_writer.draft_outline(mapped_contract, intelligence, {"flags": []}, "summary")
    assert out == "# Custom Claude Outline"


def test_outline_claude_failure_falls_back(mapped_contract, intelligence, install_anthropic):
    install_anthropic(RuntimeError("api down"))
    out = proposal_writer.draft_outline(
        mapped_contract, intelligence, {"response_deadline": None, "flags": []}, "summary"
    )
    assert "Proposal Outline" in out
