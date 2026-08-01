"""Sync manifest — tracks per-data-type high-water marks and sync state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Manifest:

    def __init__(self, path: Path):
        self._path = path
        self._data: dict = {
            "version": "1.0",
            "last_run_id": "",
            "last_run_status": "",
            "last_run_timestamp": "",
            "data_types": {},
        }
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get_last_sync(self, data_type: str) -> float:
        dt = self._data.get("data_types", {}).get(data_type, {})
        return dt.get("last_sync_epoch", 0.0)

    def update_data_type(self, data_type: str, records_synced: int, status: str) -> None:
        if "data_types" not in self._data:
            self._data["data_types"] = {}
        now = _now_iso()
        existing = self._data["data_types"].get(data_type, {})
        existing_total = existing.get("total_records_synced", 0)
        self._data["data_types"][data_type] = {
            "last_sync_timestamp": now,
            "last_sync_epoch": datetime.now(timezone.utc).timestamp(),
            "records_synced_this_run": records_synced,
            "total_records_synced": existing_total + records_synced,
            "last_status": status,
        }

    def set_run_info(self, run_id: str, status: str) -> None:
        self._data["last_run_id"] = run_id
        self._data["last_run_status"] = status
        self._data["last_run_timestamp"] = _now_iso()

    @property
    def last_run_id(self) -> str:
        return self._data.get("last_run_id", "")

    @property
    def last_run_status(self) -> str:
        return self._data.get("last_run_status", "")

    def to_dict(self) -> dict:
        return dict(self._data)
