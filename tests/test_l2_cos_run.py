"""End-to-end pipeline test for the L2-COS Automation Layer (run.py)."""

from __future__ import annotations

import json

from l2_cos import archive, run


def test_run_end_to_end_advances_and_archives(capsys):
    run.run(action_override="BOOKED")
    out = capsys.readouterr().out
    assert "Acquired 2 load(s)." in out
    assert "publisher-eligible" in out  # the clean sample load clears the threshold

    dispatch_dir = archive.ARCHIVE_ROOT / "Dispatch"
    records = sorted(dispatch_dir.glob("*.json"))
    assert len(records) == 2
    for path in records:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["stage"] == "BOOKED"
        assert len(payload["history"]) == 1


def test_run_hold_action_does_not_advance(capsys):
    from l2_cos import control

    run.run(action_override=control.HOLD_ACTION)
    dispatch_dir = archive.ARCHIVE_ROOT / "Dispatch"
    for path in sorted(dispatch_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["stage"] == "AVAILABLE"
        assert payload["history"] == []


def test_run_no_loads(monkeypatch, capsys):
    monkeypatch.setattr(run.acquisition, "acquire", lambda: [])
    run.run(action_override="BOOKED")
    assert "No loads acquired" in capsys.readouterr().out


def test_main_list_actions_not_required(monkeypatch, capsys):
    # main() with --action delegates straight to run(); smoke-test the CLI wiring.
    monkeypatch.setattr("sys.argv", ["l2_cos.run", "--action", "BOOKED"])
    run.main()
    assert "Acquired 2 load(s)." in capsys.readouterr().out
