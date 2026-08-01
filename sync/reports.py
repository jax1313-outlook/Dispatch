"""Sync reporting — log files and machine-readable JSON reports."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SyncReport:

    def __init__(self):
        self.run_id: str = ""
        self.start_time: str = ""
        self.end_time: str = ""
        self.status: str = ""
        self.vps_connection: str = ""
        self._by_type: dict[str, dict] = {}
        self._conflicts: list[dict] = []
        self._errors: list[str] = []
        self._log_lines: list[str] = []

    def start(self, run_id: str) -> None:
        self.run_id = run_id
        self.start_time = _now_iso()
        self._log(f"Sync run {run_id} started")

    def finish(self, status: str) -> None:
        self.end_time = _now_iso()
        self.status = status
        self._log(f"Sync run {self.run_id} finished: {status}")

    def set_connection(self, status: str) -> None:
        self.vps_connection = status
        self._log(f"VPS connection: {status}")

    def init_data_type(self, data_type: str) -> None:
        self._by_type[data_type] = {
            "checked": 0, "pulled": 0, "skipped": 0, "conflicts": 0, "errors": 0,
        }

    def log_checked(self, data_type: str) -> None:
        self._ensure_type(data_type)
        self._by_type[data_type]["checked"] += 1

    def log_pulled(self, data_type: str, record_id: str) -> None:
        self._ensure_type(data_type)
        self._by_type[data_type]["pulled"] += 1
        self._log(f"PULLED {data_type}/{record_id}")

    def log_skipped(self, data_type: str, record_id: str, reason: str) -> None:
        self._ensure_type(data_type)
        self._by_type[data_type]["skipped"] += 1
        self._log(f"SKIPPED {data_type}/{record_id}: {reason}")

    def log_conflict(self, data_type: str, record_id: str, reason: str = "duplicate") -> None:
        self._ensure_type(data_type)
        self._by_type[data_type]["conflicts"] += 1
        self._conflicts.append({
            "data_type": data_type, "record_id": record_id, "reason": reason,
        })
        self._log(f"CONFLICT {data_type}/{record_id}: {reason}")

    def log_error(self, message: str) -> None:
        self._errors.append(message)
        self._log(f"ERROR: {message}")

    def log_data_type_error(self, data_type: str, message: str) -> None:
        self._ensure_type(data_type)
        self._by_type[data_type]["errors"] += 1
        self.log_error(f"{data_type}: {message}")

    def has_errors(self) -> bool:
        return len(self._errors) > 0

    def pulled_count(self, data_type: str) -> int:
        return self._by_type.get(data_type, {}).get("pulled", 0)

    def _ensure_type(self, data_type: str) -> None:
        if data_type not in self._by_type:
            self.init_data_type(data_type)

    def _log(self, message: str) -> None:
        ts = _now_iso()
        line = f"[{ts}] {message}"
        self._log_lines.append(line)
        logging.info(message)

    def summary(self) -> dict:
        total = {"checked": 0, "pulled": 0, "skipped": 0, "conflicts": 0, "errors": 0}
        for counts in self._by_type.values():
            for k in total:
                total[k] += counts[k]
        return total

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
            "vps_connection": self.vps_connection,
            "summary": self.summary(),
            "by_data_type": dict(self._by_type),
            "conflicts": list(self._conflicts),
            "errors": list(self._errors),
        }

    def write_to(self, base_path: Path) -> None:
        ts = self.start_time.replace(":", "").replace("-", "").replace("+", "")
        logs_dir = base_path / "logs"
        reports_dir = base_path / "reports"
        logs_dir.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)

        log_file = logs_dir / f"sync_{ts}.log"
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("\n".join(self._log_lines))

        report_file = reports_dir / f"report_{ts}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)


def clean_old_logs(base_path: Path, retention_days: int) -> int:
    """Delete log and report files older than retention_days. Returns count deleted."""
    deleted = 0
    now = datetime.now(timezone.utc).timestamp()
    cutoff = now - (retention_days * 86400)

    for subdir in ("logs", "reports"):
        d = base_path / subdir
        if not d.exists():
            continue
        for f in d.iterdir():
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
                deleted += 1
    return deleted
