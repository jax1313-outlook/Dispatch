"""Tests for the Dispatch Synchronization Utility."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest

from sync.config import SyncConfig, DATA_TYPES, DEFAULT_APPROVED_STATUSES
from sync.manifest import Manifest
from sync.transport import LocalTransport, BaseTransport
from sync.engine import SyncEngine, SYNC_SUBDIRS
from sync.reports import SyncReport, clean_old_logs
from sync.cli import build_parser, main as cli_main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dirs(tmp_path):
    """Create VPS-like source, primary, and backup directories."""
    vps = tmp_path / "vps"
    primary = tmp_path / "primary"
    backup = tmp_path / "backup"
    for d in (vps, primary, backup):
        d.mkdir()
    return {"vps": vps, "primary": primary, "backup": backup}


@pytest.fixture
def sample_config(tmp_dirs, tmp_path):
    """Write a valid sync_config.json and return its path."""
    cfg = {
        "vps": {
            "hostname": "localhost",
            "port": 22,
            "username": "test",
            "ssh_key_path": str(tmp_path / "fake_key"),
            "remote_base_path": str(tmp_dirs["vps"]),
            "connection_timeout": 5,
        },
        "local": {
            "primary_path": str(tmp_dirs["primary"]),
            "backup_path": str(tmp_dirs["backup"]),
        },
        "sync": {
            "retry_count": 1,
            "retry_backoff": [0],
            "approved_statuses": DEFAULT_APPROVED_STATUSES,
            "log_retention_days": 90,
        },
        "data_types": DATA_TYPES,
    }
    # Create fake SSH key so validation passes
    (tmp_path / "fake_key").write_text("fake")

    cfg_path = tmp_path / "sync_config.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    return cfg_path


def _write_vps_record(vps_dir: Path, data_type: str, record_id: str,
                       status: str = "APPROVED", extra: dict | None = None) -> Path:
    """Helper to write a JSON record into the mock VPS directory."""
    d = vps_dir / data_type
    d.mkdir(parents=True, exist_ok=True)
    record = {"id": record_id, "status": status, "title": f"Test {record_id}"}
    if extra:
        record.update(extra)
    p = d / f"{record_id}.json"
    p.write_text(json.dumps(record), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Config Tests
# ---------------------------------------------------------------------------

class TestConfig:

    def test_load_valid(self, sample_config):
        cfg = SyncConfig(sample_config)
        assert cfg.vps_hostname == "localhost"
        assert cfg.vps_port == 22
        assert cfg.retry_count == 1
        assert len(cfg.data_types) == len(DATA_TYPES)

    def test_missing_config_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            SyncConfig(tmp_path / "nonexistent.json")

    def test_validate_missing_hostname(self, sample_config):
        cfg = SyncConfig(sample_config)
        cfg.vps_hostname = ""
        errors = cfg.validate()
        assert any("hostname" in e for e in errors)

    def test_validate_missing_ssh_key(self, sample_config):
        cfg = SyncConfig(sample_config)
        cfg.vps_ssh_key_path = "/nonexistent/key"
        errors = cfg.validate()
        assert any("SSH key" in e for e in errors)

    def test_validate_clean(self, sample_config):
        cfg = SyncConfig(sample_config)
        assert cfg.validate() == []

    def test_default_approved_statuses(self, sample_config):
        cfg = SyncConfig(sample_config)
        assert "APPROVED" in cfg.approved_statuses
        assert "BOOKED" in cfg.approved_statuses

    def test_all_data_types_present(self, sample_config):
        cfg = SyncConfig(sample_config)
        assert "loads" in cfg.data_types
        assert "intelligence/location" in cfg.data_types
        assert "intelligence/market" in cfg.data_types


# ---------------------------------------------------------------------------
# Manifest Tests
# ---------------------------------------------------------------------------

class TestManifest:

    def test_new_manifest(self, tmp_path):
        m = Manifest(tmp_path / "manifest.json")
        assert m.get_last_sync("loads") == 0.0
        assert m.last_run_id == ""

    def test_save_and_reload(self, tmp_path):
        p = tmp_path / "manifest.json"
        m = Manifest(p)
        m.set_run_info("abc123", "SUCCESS")
        m.update_data_type("loads", 5, "SUCCESS")
        m.save()

        m2 = Manifest(p)
        assert m2.last_run_id == "abc123"
        assert m2.last_run_status == "SUCCESS"
        assert m2.get_last_sync("loads") > 0

    def test_incremental_totals(self, tmp_path):
        p = tmp_path / "manifest.json"
        m = Manifest(p)
        m.update_data_type("loads", 3, "SUCCESS")
        m.save()

        m2 = Manifest(p)
        m2.update_data_type("loads", 2, "SUCCESS")
        data = m2.to_dict()
        assert data["data_types"]["loads"]["total_records_synced"] == 5

    def test_corrupted_manifest_fallback(self, tmp_path):
        p = tmp_path / "manifest.json"
        p.write_text("not json", encoding="utf-8")
        m = Manifest(p)
        assert m.get_last_sync("loads") == 0.0


# ---------------------------------------------------------------------------
# Transport Tests
# ---------------------------------------------------------------------------

class TestLocalTransport:

    def test_connect(self, tmp_dirs):
        t = LocalTransport(tmp_dirs["vps"])
        t.connect()
        t.disconnect()

    def test_connect_missing_dir(self, tmp_path):
        t = LocalTransport(tmp_path / "nonexistent")
        with pytest.raises(FileNotFoundError):
            t.connect()

    def test_list_files_empty(self, tmp_dirs):
        t = LocalTransport(tmp_dirs["vps"])
        t.connect()
        assert t.list_files("loads") == []

    def test_list_files_with_records(self, tmp_dirs):
        _write_vps_record(tmp_dirs["vps"], "loads", "L001")
        _write_vps_record(tmp_dirs["vps"], "loads", "L002")
        t = LocalTransport(tmp_dirs["vps"])
        t.connect()
        files = t.list_files("loads")
        assert len(files) == 2
        names = {f["name"] for f in files}
        assert "L001.json" in names
        assert "L002.json" in names

    def test_list_files_since_filter(self, tmp_dirs):
        _write_vps_record(tmp_dirs["vps"], "loads", "L001")
        future_ts = time.time() + 1000
        t = LocalTransport(tmp_dirs["vps"])
        t.connect()
        files = t.list_files("loads", since=future_ts)
        assert len(files) == 0

    def test_download_file(self, tmp_dirs):
        _write_vps_record(tmp_dirs["vps"], "loads", "L001")
        t = LocalTransport(tmp_dirs["vps"])
        t.connect()
        dest = tmp_dirs["primary"] / "staging" / "L001.json"
        t.download_file("loads/L001.json", dest)
        assert dest.exists()
        data = json.loads(dest.read_text())
        assert data["id"] == "L001"

    def test_ignores_non_json(self, tmp_dirs):
        (tmp_dirs["vps"] / "loads").mkdir(parents=True)
        (tmp_dirs["vps"] / "loads" / "readme.txt").write_text("not json")
        t = LocalTransport(tmp_dirs["vps"])
        t.connect()
        assert t.list_files("loads") == []


# ---------------------------------------------------------------------------
# Engine Tests
# ---------------------------------------------------------------------------

class TestEngine:

    def _make_engine(self, sample_config, tmp_dirs):
        cfg = SyncConfig(sample_config)
        transport = LocalTransport(tmp_dirs["vps"])
        return SyncEngine(cfg, transport)

    def test_basic_sync(self, sample_config, tmp_dirs):
        _write_vps_record(tmp_dirs["vps"], "loads", "L001")
        engine = self._make_engine(sample_config, tmp_dirs)
        code = engine.run()
        assert code == 0
        assert (tmp_dirs["primary"] / "loads" / "L001.json").exists()

    def test_dual_write(self, sample_config, tmp_dirs):
        _write_vps_record(tmp_dirs["vps"], "loads", "L001")
        engine = self._make_engine(sample_config, tmp_dirs)
        engine.run()
        assert (tmp_dirs["primary"] / "loads" / "L001.json").exists()
        assert (tmp_dirs["backup"] / "loads" / "L001.json").exists()
        primary_data = json.loads((tmp_dirs["primary"] / "loads" / "L001.json").read_text())
        backup_data = json.loads((tmp_dirs["backup"] / "loads" / "L001.json").read_text())
        assert primary_data == backup_data

    def test_duplicate_detection(self, sample_config, tmp_dirs):
        _write_vps_record(tmp_dirs["vps"], "loads", "L001")
        (tmp_dirs["primary"] / "loads").mkdir(parents=True)
        (tmp_dirs["primary"] / "loads" / "L001.json").write_text(
            json.dumps({"id": "L001", "status": "LOCAL_COPY", "local": True})
        )
        engine = self._make_engine(sample_config, tmp_dirs)
        engine.run()
        local_data = json.loads((tmp_dirs["primary"] / "loads" / "L001.json").read_text())
        assert local_data.get("local") is True
        assert local_data["status"] == "LOCAL_COPY"

    def test_conflict_saved(self, sample_config, tmp_dirs):
        _write_vps_record(tmp_dirs["vps"], "loads", "L001")
        (tmp_dirs["primary"] / "loads").mkdir(parents=True)
        (tmp_dirs["primary"] / "loads" / "L001.json").write_text(
            json.dumps({"id": "L001", "local": True})
        )
        engine = self._make_engine(sample_config, tmp_dirs)
        engine.run()
        conflicts = list((tmp_dirs["primary"] / "conflicts" / "loads").glob("L001_remote_*.json"))
        assert len(conflicts) == 1

    def test_status_filter(self, sample_config, tmp_dirs):
        _write_vps_record(tmp_dirs["vps"], "loads", "L001", status="APPROVED")
        _write_vps_record(tmp_dirs["vps"], "loads", "L002", status="DRAFT")
        engine = self._make_engine(sample_config, tmp_dirs)
        engine.run()
        assert (tmp_dirs["primary"] / "loads" / "L001.json").exists()
        assert not (tmp_dirs["primary"] / "loads" / "L002.json").exists()

    def test_invalid_json_skipped(self, sample_config, tmp_dirs):
        (tmp_dirs["vps"] / "loads").mkdir(parents=True)
        (tmp_dirs["vps"] / "loads" / "bad.json").write_text("not json at all")
        engine = self._make_engine(sample_config, tmp_dirs)
        code = engine.run()
        assert not (tmp_dirs["primary"] / "loads" / "bad.json").exists()

    def test_incremental_sync(self, sample_config, tmp_dirs):
        _write_vps_record(tmp_dirs["vps"], "loads", "L001")
        engine = self._make_engine(sample_config, tmp_dirs)
        engine.run()

        time.sleep(0.01)
        p = _write_vps_record(tmp_dirs["vps"], "loads", "L002")
        future_time = time.time() + 2.0
        os.utime(p, (future_time, future_time))
        engine2 = self._make_engine(sample_config, tmp_dirs)
        engine2.run()
        assert (tmp_dirs["primary"] / "loads" / "L001.json").exists()
        assert (tmp_dirs["primary"] / "loads" / "L002.json").exists()

    def test_dry_run(self, sample_config, tmp_dirs):
        _write_vps_record(tmp_dirs["vps"], "loads", "L001")
        engine = self._make_engine(sample_config, tmp_dirs)
        code = engine.run(dry_run=True)
        assert code == 0
        assert not (tmp_dirs["primary"] / "loads" / "L001.json").exists()

    def test_manifest_updated_after_sync(self, sample_config, tmp_dirs):
        _write_vps_record(tmp_dirs["vps"], "loads", "L001")
        engine = self._make_engine(sample_config, tmp_dirs)
        engine.run()
        manifest = json.loads((tmp_dirs["primary"] / "manifest.json").read_text())
        assert manifest["last_run_status"] == "SUCCESS"
        assert manifest["data_types"]["loads"]["records_synced_this_run"] == 1

    def test_manifest_mirrored_to_backup(self, sample_config, tmp_dirs):
        _write_vps_record(tmp_dirs["vps"], "loads", "L001")
        engine = self._make_engine(sample_config, tmp_dirs)
        engine.run()
        assert (tmp_dirs["backup"] / "manifest.json").exists()

    def test_directories_created(self, sample_config, tmp_dirs):
        engine = self._make_engine(sample_config, tmp_dirs)
        engine.run()
        for sub in SYNC_SUBDIRS:
            assert (tmp_dirs["primary"] / sub).exists()
            assert (tmp_dirs["backup"] / sub).exists()

    def test_staging_cleaned_after_sync(self, sample_config, tmp_dirs):
        _write_vps_record(tmp_dirs["vps"], "loads", "L001")
        engine = self._make_engine(sample_config, tmp_dirs)
        engine.run()
        staging = tmp_dirs["primary"] / "staging"
        staged_files = list(staging.rglob("*.json"))
        assert len(staged_files) == 0

    def test_multiple_data_types(self, sample_config, tmp_dirs):
        _write_vps_record(tmp_dirs["vps"], "loads", "L001")
        _write_vps_record(tmp_dirs["vps"], "brokers", "B001")
        _write_vps_record(tmp_dirs["vps"], "intelligence/location", "LOC001")
        engine = self._make_engine(sample_config, tmp_dirs)
        engine.run()
        assert (tmp_dirs["primary"] / "loads" / "L001.json").exists()
        assert (tmp_dirs["primary"] / "brokers" / "B001.json").exists()
        assert (tmp_dirs["primary"] / "intelligence" / "location" / "LOC001.json").exists()

    def test_record_without_status_accepted(self, sample_config, tmp_dirs):
        d = tmp_dirs["vps"] / "loads"
        d.mkdir(parents=True, exist_ok=True)
        (d / "L099.json").write_text(json.dumps({"id": "L099", "title": "No status field"}))
        engine = self._make_engine(sample_config, tmp_dirs)
        engine.run()
        assert (tmp_dirs["primary"] / "loads" / "L099.json").exists()

    def test_non_dict_json_skipped(self, sample_config, tmp_dirs):
        d = tmp_dirs["vps"] / "loads"
        d.mkdir(parents=True, exist_ok=True)
        (d / "array.json").write_text(json.dumps([1, 2, 3]))
        engine = self._make_engine(sample_config, tmp_dirs)
        engine.run()
        assert not (tmp_dirs["primary"] / "loads" / "array.json").exists()

    def test_record_id_from_json(self, sample_config, tmp_dirs):
        d = tmp_dirs["vps"] / "loads"
        d.mkdir(parents=True, exist_ok=True)
        (d / "file.json").write_text(json.dumps({"id": "REAL_ID", "status": "APPROVED"}))
        engine = self._make_engine(sample_config, tmp_dirs)
        engine.run()
        assert (tmp_dirs["primary"] / "loads" / "REAL_ID.json").exists()


# ---------------------------------------------------------------------------
# Report Tests
# ---------------------------------------------------------------------------

class TestReports:

    def test_report_lifecycle(self):
        r = SyncReport()
        r.start("run1")
        r.set_connection("OK")
        r.init_data_type("loads")
        r.log_checked("loads")
        r.log_pulled("loads", "L001")
        r.log_conflict("loads", "L002")
        r.finish("PARTIAL")

        s = r.summary()
        assert s["checked"] == 1
        assert s["pulled"] == 1
        assert s["conflicts"] == 1

    def test_report_json_output(self, tmp_path):
        r = SyncReport()
        r.start("run2")
        r.finish("SUCCESS")
        r.write_to(tmp_path)
        reports = list((tmp_path / "reports").glob("*.json"))
        assert len(reports) == 1
        data = json.loads(reports[0].read_text())
        assert data["status"] == "SUCCESS"

    def test_report_log_output(self, tmp_path):
        r = SyncReport()
        r.start("run3")
        r.finish("SUCCESS")
        r.write_to(tmp_path)
        logs = list((tmp_path / "logs").glob("*.log"))
        assert len(logs) == 1

    def test_has_errors(self):
        r = SyncReport()
        assert not r.has_errors()
        r.log_error("something broke")
        assert r.has_errors()

    def test_clean_old_logs(self, tmp_path):
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        old_file = logs_dir / "old.log"
        old_file.write_text("old log")
        old_time = time.time() - (100 * 86400)
        os.utime(old_file, (old_time, old_time))

        new_file = logs_dir / "new.log"
        new_file.write_text("new log")

        deleted = clean_old_logs(tmp_path, retention_days=90)
        assert deleted == 1
        assert not old_file.exists()
        assert new_file.exists()


# ---------------------------------------------------------------------------
# CLI Tests
# ---------------------------------------------------------------------------

class TestCLI:

    def test_parser_defaults(self):
        p = build_parser()
        args = p.parse_args([])
        assert args.config is None
        assert args.dry_run is False
        assert args.verbose is False

    def test_parser_flags(self):
        p = build_parser()
        args = p.parse_args(["--dry-run", "--verbose", "-c", "my.json"])
        assert args.dry_run is True
        assert args.verbose is True
        assert args.config == "my.json"

    def test_cli_missing_config(self, tmp_path):
        code = cli_main(["-c", str(tmp_path / "nonexistent.json")])
        assert code == 2

    def test_cli_with_local_source(self, sample_config, tmp_dirs):
        _write_vps_record(tmp_dirs["vps"], "loads", "L001")
        code = cli_main([
            "-c", str(sample_config),
            "--local-source", str(tmp_dirs["vps"]),
        ])
        assert code == 0
        assert (tmp_dirs["primary"] / "loads" / "L001.json").exists()

    def test_cli_dry_run(self, sample_config, tmp_dirs):
        _write_vps_record(tmp_dirs["vps"], "loads", "L001")
        code = cli_main([
            "-c", str(sample_config),
            "--local-source", str(tmp_dirs["vps"]),
            "--dry-run",
        ])
        assert code == 0
        assert not (tmp_dirs["primary"] / "loads" / "L001.json").exists()


# ---------------------------------------------------------------------------
# Connection Failure Tests
# ---------------------------------------------------------------------------

class TestConnectionFailure:

    def test_unreachable_source(self, sample_config, tmp_dirs):
        cfg = SyncConfig(sample_config)
        transport = LocalTransport(tmp_dirs["vps"] / "nonexistent_subdir")
        engine = SyncEngine(cfg, transport)
        code = engine.run()
        assert code == 2
        assert engine.report.status == "FAILED"


# ---------------------------------------------------------------------------
# Ownership Protection Tests
# ---------------------------------------------------------------------------

class TestOwnershipProtection:

    def test_local_never_overwritten(self, sample_config, tmp_dirs):
        """Local record must survive even when VPS has a different version."""
        local_record = {"id": "L001", "status": "LOCAL", "my_data": "precious"}
        (tmp_dirs["primary"] / "loads").mkdir(parents=True)
        (tmp_dirs["primary"] / "loads" / "L001.json").write_text(json.dumps(local_record))

        _write_vps_record(tmp_dirs["vps"], "loads", "L001", extra={"my_data": "remote_version"})

        cfg = SyncConfig(sample_config)
        transport = LocalTransport(tmp_dirs["vps"])
        engine = SyncEngine(cfg, transport)
        engine.run()

        result = json.loads((tmp_dirs["primary"] / "loads" / "L001.json").read_text())
        assert result["my_data"] == "precious"

    def test_local_never_deleted(self, sample_config, tmp_dirs):
        """Records that exist locally but not on VPS must not be touched."""
        (tmp_dirs["primary"] / "loads").mkdir(parents=True)
        (tmp_dirs["primary"] / "loads" / "LOCAL_ONLY.json").write_text(
            json.dumps({"id": "LOCAL_ONLY", "local": True})
        )
        cfg = SyncConfig(sample_config)
        transport = LocalTransport(tmp_dirs["vps"])
        engine = SyncEngine(cfg, transport)
        engine.run()
        assert (tmp_dirs["primary"] / "loads" / "LOCAL_ONLY.json").exists()

    def test_vps_never_modified(self, sample_config, tmp_dirs):
        """VPS source files must remain untouched after sync."""
        vps_file = _write_vps_record(tmp_dirs["vps"], "loads", "L001")
        original_content = vps_file.read_text()
        original_mtime = vps_file.stat().st_mtime

        cfg = SyncConfig(sample_config)
        transport = LocalTransport(tmp_dirs["vps"])
        engine = SyncEngine(cfg, transport)
        engine.run()

        assert vps_file.read_text() == original_content
        assert vps_file.stat().st_mtime == original_mtime
