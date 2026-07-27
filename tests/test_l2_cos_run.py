"""End-to-end pipeline test for the L2-COS Automation Layer (run.py)."""

from __future__ import annotations

import json

from l2_cos import archive, run


def test_run_end_to_end_advances_and_archives(capsys):
    run.run(action_override="BOOKED")
    out = capsys.readouterr().out
    assert "Acquired 2 load(s)." in out
    assert "publisher-eligible" in out  # the clean sample load clears the threshold
    assert "publisher: not sent (SMTP not configured)" in out  # offline .eml fallback

    dispatch_dir = archive.ARCHIVE_ROOT / "Dispatch"
    records = sorted(dispatch_dir.glob("*.json"))
    assert len(records) == 2
    for path in records:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["stage"] == "BOOKED"
        assert len(payload["history"]) == 1

    # Only the clean sample load (score >= 90) triggers the publisher workflow.
    publisher_records = list((archive.ARCHIVE_ROOT / "Publisher").glob("*.json"))
    assert len(publisher_records) == 1
    result = json.loads(publisher_records[0].read_text(encoding="utf-8"))
    assert result["sent"] is True
    assert result["artifacts"]["rate_confirmation_package"] is True


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


def test_run_publisher_declines_when_artifacts_incomplete(monkeypatch, capsys):
    from l2_cos.models.intelligence import InquiryArtifacts

    monkeypatch.setattr(
        run.intelligence_store, "load_carrier_documents", lambda: InquiryArtifacts(business_card=True)
    )
    run.run(action_override="BOOKED")
    out = capsys.readouterr().out
    assert "publisher: declined to send (inquiry artifacts incomplete:" in out


def test_run_publisher_dry_run_never_calls_smtp(monkeypatch, capsys):
    """Even with SMTP fully configured, L2_COS_EMAIL_DRY_RUN=1 must keep the
    end-to-end run from placing a live call — the publisher step has no
    human gate, so this is the safety net for test/staging execution."""
    from l2_cos import email_delivery

    def _boom(*a, **k):
        raise AssertionError("SMTP must never be contacted during a dry run")

    monkeypatch.setenv("L2_COS_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("L2_COS_EMAIL_DRY_RUN", "1")
    monkeypatch.setattr(email_delivery.smtplib, "SMTP", _boom)

    run.run(action_override="BOOKED")
    out = capsys.readouterr().out
    assert "dry-run (L2_COS_EMAIL_DRY_RUN=1)" in out
