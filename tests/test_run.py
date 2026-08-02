"""End-to-end orchestrator tests (the Automation Layer)."""

from __future__ import annotations

import sys

from cin_lite import run, acquisition
from cin_lite.pipeline import process_contracts


def test_run_approve_proposal_triggers_workflow(capsys, tmp_archive):
    run.run("approve_proposal")
    out = capsys.readouterr().out
    assert "Processed" in out
    assert "proposal triggered" in out
    assert list((tmp_archive / "Proposals").glob("*.json"))
    assert list((tmp_archive / "Routing").glob("*.json"))


def test_run_reject_does_not_trigger_proposal(capsys, tmp_archive):
    run.run("reject")
    out = capsys.readouterr().out
    assert "proposal triggered" not in out
    assert not (tmp_archive / "Proposals").exists()


def test_run_no_contracts(capsys, monkeypatch):
    monkeypatch.setattr(acquisition, "acquire", lambda: [])
    run.run("reject")
    assert "No contracts acquired" in capsys.readouterr().out


def test_main_list_actions(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run", "--list-actions"])
    run.main()
    out = capsys.readouterr().out
    assert "approve_proposal" in out and "PROPOSAL_QUEUE" in out


def test_main_with_action(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run", "--action", "reject"])
    run.main()
    assert "Processed" in capsys.readouterr().out


def test_run_handles_error_status(capsys, monkeypatch):
    from cin_lite import acquisition as acq_mod, processing

    good = {"title": "Good One", "solicitation_number": "SOL-G",
            "agency": "GSA", "naics_text": "", "description": "ok",
            "estimated_value": None, "response_date": None, "notes": ""}
    bad = {"title": "Bad One"}

    monkeypatch.setattr(acq_mod, "acquire", lambda: [good, bad])

    orig = processing.process
    def blow_up(contract):
        if contract is bad:
            raise RuntimeError("boom")
        return orig(contract)
    monkeypatch.setattr(processing, "process", blow_up)

    run.run(None)
    out = capsys.readouterr().out
    assert "Processed 2 contract(s)" in out
    assert "ERROR: Bad One" in out
    assert "boom" in out
    assert "Good One" in out
