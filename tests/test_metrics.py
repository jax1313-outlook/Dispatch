"""Tests for the pipeline metrics and analytics module."""

from __future__ import annotations

import json

from cin_lite import metrics


class TestRunMetrics:
    def test_basic_lifecycle(self):
        m = metrics.RunMetrics(run_id="test-run-001")
        m.record_acquisition(3)

        with m.track_contract("CIN-001"):
            pass
        with m.track_contract("CIN-002"):
            pass

        m.record_action("approve_proposal")
        m.record_action("reject")
        m.record_action("approve_proposal")

        record = m.finalize()
        assert record["run_id"] == "test-run-001"
        assert record["contracts_acquired"] == 3
        assert record["contracts_processed"] == 2
        assert record["actions"] == {"approve_proposal": 2, "reject": 1}
        assert record["error_count"] == 0
        assert record["elapsed_seconds"] >= 0
        assert len(record["contract_timings"]) == 2
        assert record["avg_contract_ms"] >= 0

    def test_error_recording(self):
        m = metrics.RunMetrics()
        m.record_error("CIN-X", "processing", "rule failed")
        record = m.finalize()
        assert record["error_count"] == 1
        assert record["errors"][0]["stage"] == "processing"

    def test_empty_run(self):
        m = metrics.RunMetrics()
        record = m.finalize()
        assert record["contracts_processed"] == 0
        assert record["avg_contract_ms"] == 0


class TestPersistence:
    def test_save_and_load(self, tmp_path):
        m = metrics.RunMetrics(run_id="persist-test")
        m.record_acquisition(1)
        with m.track_contract("C1"):
            pass
        m.record_action("reject")
        record = m.finalize()

        path = metrics.save(record, metrics_dir=tmp_path)
        assert path.exists()

        history = metrics.load_history(metrics_dir=tmp_path)
        assert len(history) == 1
        assert history[0]["run_id"] == "persist-test"

    def test_load_empty_dir(self, tmp_path):
        assert metrics.load_history(metrics_dir=tmp_path) == []

    def test_multiple_saves_append(self, tmp_path):
        for i in range(3):
            m = metrics.RunMetrics(run_id=f"run-{i}")
            record = m.finalize()
            metrics.save(record, metrics_dir=tmp_path)

        history = metrics.load_history(metrics_dir=tmp_path)
        assert len(history) == 3

    def test_load_limit(self, tmp_path):
        for i in range(10):
            metrics.save({"type": "pipeline_run", "run_id": f"r{i}"}, metrics_dir=tmp_path)
        history = metrics.load_history(metrics_dir=tmp_path, limit=3)
        assert len(history) == 3
        assert history[0]["run_id"] == "r7"


class TestSummaryReport:
    def test_report_with_data(self, tmp_path):
        m = metrics.RunMetrics(run_id="report-test")
        m.record_acquisition(2)
        with m.track_contract("C1"):
            pass
        with m.track_contract("C2"):
            pass
        m.record_action("approve_proposal")
        m.record_action("reject")
        metrics.save(m.finalize(), metrics_dir=tmp_path)

        report = metrics.summary_report(metrics_dir=tmp_path)
        assert "Pipeline Metrics Summary" in report
        assert "Total runs" in report
        assert "approve_proposal" in report
        assert "reject" in report

    def test_report_empty(self, tmp_path):
        report = metrics.summary_report(metrics_dir=tmp_path)
        assert "No pipeline runs recorded" in report

    def test_report_with_errors(self, tmp_path):
        m = metrics.RunMetrics(run_id="err-test")
        m.record_error("CIN-X", "acquisition", "timeout")
        with m.track_contract("CIN-X"):
            pass
        m.record_action("reject")
        metrics.save(m.finalize(), metrics_dir=tmp_path)

        report = metrics.summary_report(metrics_dir=tmp_path)
        assert "Recent errors" in report
        assert "timeout" in report

    def test_corrupt_jsonl_line_skipped(self, tmp_path):
        path = tmp_path / "pipeline.jsonl"
        path.write_text('{"type":"pipeline_run","run_id":"ok"}\nNOT JSON\n{"type":"pipeline_run","run_id":"ok2"}\n')
        history = metrics.load_history(metrics_dir=tmp_path)
        assert len(history) == 2

    def test_records_without_pipeline_run_type(self, tmp_path):
        path = tmp_path / "pipeline.jsonl"
        path.write_text('{"type":"other","data":1}\n')
        report = metrics.summary_report(metrics_dir=tmp_path)
        assert "No pipeline runs recorded" in report
