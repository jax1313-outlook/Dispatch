"""Sync engine — core pull-only synchronization logic."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from sync.config import SyncConfig
from sync.manifest import Manifest
from sync.reports import SyncReport, clean_old_logs
from sync.transport import BaseTransport

SYNC_SUBDIRS = [
    "staging", "conflicts", "logs", "reports",
    "loads", "brokers", "customers", "library", "archive",
    "publisher", "locations",
    "intelligence/location", "intelligence/broker", "intelligence/customer",
    "intelligence/route", "intelligence/position", "intelligence/market",
]


class SyncEngine:

    def __init__(self, config: SyncConfig, transport: BaseTransport):
        self.config = config
        self.transport = transport
        self.manifest = Manifest(config.primary_path / "manifest.json")
        self.report = SyncReport()

    def run(self, dry_run: bool = False) -> int:
        run_id = uuid.uuid4().hex[:8]
        self.report.start(run_id)

        self._ensure_directories()

        if not self._connect_with_retry():
            self.manifest.set_run_info(run_id, "FAILED")
            if not dry_run:
                self.manifest.save()
            self.report.finish("FAILED")
            self._write_reports()
            return 2

        try:
            for data_type in self.config.data_types:
                self._sync_data_type(data_type, dry_run)
        except Exception as e:
            self.report.log_error(f"Unexpected error: {e}")
        finally:
            self.transport.disconnect()

        status = "SUCCESS" if not self.report.has_errors() else "PARTIAL"

        if not dry_run:
            self.manifest.set_run_info(run_id, status)
            self.manifest.save()
            self._mirror_manifest()

        self.report.finish(status)
        self._write_reports()
        self._clean_staging()

        clean_old_logs(self.config.primary_path, self.config.log_retention_days)

        return 0 if status == "SUCCESS" else 1

    def _connect_with_retry(self) -> bool:
        for attempt in range(self.config.retry_count):
            try:
                self.transport.connect()
                self.report.set_connection("OK")
                return True
            except Exception as e:
                self.report.log_error(
                    f"Connection attempt {attempt + 1}/{self.config.retry_count} failed: {e}"
                )
                if attempt < self.config.retry_count - 1:
                    import time
                    backoff = self.config.retry_backoff[min(attempt, len(self.config.retry_backoff) - 1)]
                    time.sleep(backoff)

        self.report.set_connection("FAILED")
        return False

    def _sync_data_type(self, data_type: str, dry_run: bool) -> None:
        self.report.init_data_type(data_type)
        high_water = self.manifest.get_last_sync(data_type)

        remote_path = data_type
        try:
            files = self.transport.list_files(remote_path, since=high_water if high_water else None)
        except Exception as e:
            self.report.log_data_type_error(data_type, f"Failed to list remote files: {e}")
            return

        pulled = 0
        for file_info in files:
            self.report.log_checked(data_type)
            name = file_info["name"]
            record_id = name.replace(".json", "")

            staging_path = self.config.primary_path / "staging" / data_type / name
            try:
                self.transport.download_file(f"{remote_path}/{name}", staging_path)
            except Exception as e:
                self.report.log_data_type_error(data_type, f"Failed to download {name}: {e}")
                continue

            record = self._validate_record(staging_path)
            if record is None:
                self.report.log_skipped(data_type, record_id, "invalid JSON")
                self._remove_staged(staging_path)
                continue

            if "id" in record:
                record_id = str(record["id"])

            record_status = record.get("status", "")
            if record_status and record_status not in self.config.approved_statuses:
                self.report.log_skipped(data_type, record_id, f"status '{record_status}' not approved")
                self._remove_staged(staging_path)
                continue

            primary_dest = self.config.primary_path / data_type / f"{record_id}.json"
            if primary_dest.exists():
                self._save_conflict(data_type, record_id, staging_path)
                self.report.log_conflict(data_type, record_id, "duplicate — local copy preserved")
                self._remove_staged(staging_path)
                continue

            if dry_run:
                self.report.log_pulled(data_type, record_id)
                self._remove_staged(staging_path)
                pulled += 1
                continue

            self._commit_record(data_type, record_id, staging_path)
            self.report.log_pulled(data_type, record_id)
            pulled += 1

        if not dry_run:
            status = "SUCCESS" if not self.report._by_type.get(data_type, {}).get("errors") else "PARTIAL"
            self.manifest.update_data_type(data_type, pulled, status)

    def _validate_record(self, path: Path) -> dict | None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return None
            return data
        except (json.JSONDecodeError, OSError):
            return None

    def _commit_record(self, data_type: str, record_id: str, staging_path: Path) -> None:
        primary_dest = self.config.primary_path / data_type / f"{record_id}.json"
        primary_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(staging_path), str(primary_dest))

        backup_dest = self.config.backup_path / data_type / f"{record_id}.json"
        backup_dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(str(staging_path), str(backup_dest))
        except OSError:
            self.report.log_error(f"Backup write failed for {data_type}/{record_id} — primary copy OK")

        self._remove_staged(staging_path)

    def _save_conflict(self, data_type: str, record_id: str, staging_path: Path) -> None:
        conflict_dir = self.config.primary_path / "conflicts" / data_type
        conflict_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest = conflict_dir / f"{record_id}_remote_{ts}.json"
        shutil.copy2(str(staging_path), str(dest))

    def _remove_staged(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    def _clean_staging(self) -> None:
        staging = self.config.primary_path / "staging"
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
            staging.mkdir(parents=True, exist_ok=True)

    def _ensure_directories(self) -> None:
        for base in (self.config.primary_path, self.config.backup_path):
            for sub in SYNC_SUBDIRS:
                (base / sub).mkdir(parents=True, exist_ok=True)

    def _mirror_manifest(self) -> None:
        src = self.config.primary_path / "manifest.json"
        dst = self.config.backup_path / "manifest.json"
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(str(src), str(dst))
            except OSError:
                self.report.log_error("Failed to mirror manifest to backup")

    def _write_reports(self) -> None:
        self.report.write_to(self.config.primary_path)
        try:
            self.report.write_to(self.config.backup_path)
        except OSError:
            self.report.log_error("Failed to write reports to backup location")
