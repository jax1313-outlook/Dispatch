"""Step 18 proves persistence by comparison, and fails when it should.

The step is the only automated check in the proof path that looks at the
*content* of what survived a restart rather than at whether the application
came back up. Two ways it can lie, and both are tested here as failures:

  * the evidence row is intact but the bytes on disk changed;
  * the evidence row is intact and the file is gone.

Neither surfaces anywhere else. The load list still renders, the POD page still
links, and only a recompute of the hash recorded at upload says otherwise.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dispatch import proof, services
from dispatch.db import set_db_path


@pytest.fixture
def estate(tmp_path, monkeypatch):
    """A load with a driver, a milestone and two uploaded evidence files."""
    monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "Evidence"))
    set_db_path(tmp_path / "dispatch.db")
    try:
        load = services.create_load(customer="Acme Foods", broker_shipper="TQL")
        load_id = load["load_id"]
        services.add_milestone(load_id, "dispatched", note="left the yard")
        services.attach_evidence(
            load_id, description="BOL", uploaded_by="Mike",
            file_data=b"%PDF-1.4 bill of lading", original_filename="bol.pdf",
        )
        services.attach_evidence(
            load_id, description="POD", uploaded_by="Mike",
            file_data=b"%PDF-1.4 proof of delivery", original_filename="pod.pdf",
        )
        yield load_id
    finally:
        set_db_path(None)


class TestVerifyWithoutASnapshot:
    """The database already carries the upload-time checksum, so this needs nothing."""

    def test_an_untouched_estate_passes(self, estate):
        result = proof.verify_persistence(estate)
        assert result["ok"] is True
        assert result["load_present"] is True
        assert {r["verdict"] for r in result["evidence_integrity"]["rows"]} == {"LIVE"}

    def test_altered_bytes_fail_even_though_the_row_is_perfect(self, estate):
        evidence = services.list_evidence(estate)
        target = Path(evidence[0]["file_path"])
        target.write_bytes(b"%PDF-1.4 bill of lading (edited)")

        result = proof.verify_persistence(estate)

        assert result["ok"] is False
        bad = [r for r in result["evidence_integrity"]["rows"] if r["verdict"] != "LIVE"]
        assert len(bad) == 1
        assert bad[0]["verdict"] == "UNAVAILABLE"
        assert bad[0]["recorded_checksum"] != bad[0]["recomputed_sha256"]

    def test_a_missing_file_fails_and_is_named(self, estate):
        evidence = services.list_evidence(estate)
        Path(evidence[1]["file_path"]).unlink()

        result = proof.verify_persistence(estate)

        assert result["ok"] is False
        absent = [r for r in result["evidence_integrity"]["rows"] if r["verdict"] == "ABSENT"]
        assert len(absent) == 1
        assert absent[0]["evidence_id"] == evidence[1]["evidence_id"]

    def test_a_vanished_load_fails(self, estate):
        result = proof.verify_persistence("LD-DOESNOTEXIST")
        assert result["ok"] is False
        assert result["load_present"] is False

    def test_a_row_with_no_recorded_checksum_is_unverified_not_passed(self, estate, monkeypatch):
        """A gap in the record is not evidence of survival."""
        from dispatch import store

        real = store.list_evidence

        def blank_checksum(load_id):
            rows = [dict(r) for r in real(load_id)]
            rows[0]["checksum"] = ""
            return rows

        monkeypatch.setattr(store, "list_evidence", blank_checksum)
        result = proof.verify_persistence(estate)
        assert result["ok"] is False
        assert any(r["verdict"] == "UNVERIFIED" for r in result["evidence_integrity"]["rows"])


class TestVerifyAgainstASnapshot:
    """The stricter comparison: what appeared, as well as what vanished."""

    def test_matching_snapshot_passes(self, estate):
        snap = proof.snapshot_persistence(estate)
        result = proof.verify_persistence(estate, snapshot=snap)
        assert result["ok"] is True
        assert result["snapshot_comparison"]["identical"] is True

    def test_a_record_that_disappeared_is_reported(self, estate):
        snap = proof.snapshot_persistence(estate)
        evidence = services.list_evidence(estate)
        services.delete_evidence(evidence[0]["evidence_id"])

        result = proof.verify_persistence(estate, snapshot=snap)

        assert result["ok"] is False
        rows = {r["table"]: r for r in result["snapshot_comparison"]["record_ids"]["rows"]}
        assert rows["evidence"]["missing"] == [evidence[0]["evidence_id"]]

    def test_a_record_that_appeared_from_nowhere_is_reported(self, estate):
        """Only the snapshot comparison can see this; a self-check cannot."""
        snap = proof.snapshot_persistence(estate)
        services.add_milestone(estate, "arrived_pickup", note="added after the snapshot")

        result = proof.verify_persistence(estate, snapshot=snap)

        assert result["ok"] is False
        rows = {r["table"]: r for r in result["snapshot_comparison"]["record_ids"]["rows"]}
        assert len(rows["milestones"]["unexpected"]) == 1


class TestRendering:
    def test_the_report_shows_both_hashes_not_a_verdict(self, estate):
        result = proof.verify_persistence(estate)
        text = proof.render_verify_result(result)
        for row in result["evidence_integrity"]["rows"]:
            assert row["recorded_checksum"] in text
            assert row["recomputed_sha256"] in text
        assert "RESULT: PASSED" in text

    def test_a_failure_says_failed(self, estate):
        Path(services.list_evidence(estate)[0]["file_path"]).unlink()
        text = proof.render_verify_result(proof.verify_persistence(estate))
        assert "RESULT: FAILED" in text


class TestTheCliItself:
    """Exercised through the parser and handler the operator actually reaches."""

    def _tool(self):
        import importlib.util

        path = Path(__file__).resolve().parent.parent / "scripts" / "dispatch_proof.py"
        spec = importlib.util.spec_from_file_location("_proof_cli_under_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _run(self, argv):
        tool = self._tool()
        args = tool.build_parser().parse_args(argv)
        return args.func(args)

    def test_verify_exits_zero_on_an_intact_estate(self, estate, capsys):
        assert self._run(["verify", "--load-id", estate]) == 0
        assert "RESULT: PASSED" in capsys.readouterr().out

    def test_verify_exits_one_when_evidence_changed(self, estate, capsys):
        target = Path(services.list_evidence(estate)[0]["file_path"])
        target.write_bytes(b"tampered")
        assert self._run(["verify", "--load-id", estate]) == 1

    def test_snapshot_then_verify_round_trips_through_a_file(self, estate, tmp_path, capsys):
        out = tmp_path / "snap.json"
        assert self._run(["snapshot", "--load-id", estate, "--output", str(out)]) == 0
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["load_id"] == estate
        assert self._run(["verify", "--load-id", estate, "--snapshot", str(out)]) == 0

    def test_snapshot_refuses_an_unknown_load(self, estate, tmp_path):
        assert self._run(["snapshot", "--load-id", "LD-NOPE", "--output", str(tmp_path / "x.json")]) == 1

    def test_verify_refuses_a_snapshot_for_a_different_load(self, estate, tmp_path):
        out = tmp_path / "snap.json"
        self._run(["snapshot", "--load-id", estate, "--output", str(out)])
        payload = json.loads(out.read_text(encoding="utf-8"))
        payload["load_id"] = "LD-SOMEONEELSE"
        out.write_text(json.dumps(payload), encoding="utf-8")
        assert self._run(["verify", "--load-id", estate, "--snapshot", str(out)]) == 2

    def test_verify_reports_a_missing_snapshot_rather_than_passing(self, estate, tmp_path):
        assert self._run(["verify", "--load-id", estate, "--snapshot", str(tmp_path / "absent.json")]) == 2

    def test_json_output_is_machine_readable(self, estate, capsys):
        assert self._run(["verify", "--load-id", estate, "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["ok"] is True
