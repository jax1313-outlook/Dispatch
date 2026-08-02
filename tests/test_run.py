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
