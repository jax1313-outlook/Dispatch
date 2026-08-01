"""Sync configuration — loads sync_config.json, validates, provides defaults."""

from __future__ import annotations

import json
from pathlib import Path

_SYNC_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = _SYNC_DIR / "sync_config.json"

DATA_TYPES = [
    "loads",
    "brokers",
    "customers",
    "library",
    "archive",
    "publisher",
    "locations",
    "intelligence/location",
    "intelligence/broker",
    "intelligence/customer",
    "intelligence/route",
    "intelligence/position",
    "intelligence/market",
]

DEFAULT_APPROVED_STATUSES = [
    "APPROVED",
    "BOOKED",
    "CLOSED",
    "PASS",
    "EXPIRED",
]


class SyncConfig:

    def __init__(self, config_path: str | Path | None = None):
        path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        if not path.exists():
            raise FileNotFoundError(f"Sync config not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        vps = raw.get("vps", {})
        self.vps_hostname: str = vps.get("hostname", "")
        self.vps_port: int = vps.get("port", 22)
        self.vps_username: str = vps.get("username", "")
        self.vps_ssh_key_path: str = vps.get("ssh_key_path", "")
        self.vps_remote_base: str = vps.get("remote_base_path", "/approved_records")
        self.vps_timeout: int = vps.get("connection_timeout", 30)

        local = raw.get("local", {})
        self.primary_path: Path = Path(local["primary_path"]) if local.get("primary_path") else Path()
        self.backup_path: Path = Path(local["backup_path"]) if local.get("backup_path") else Path()

        sync = raw.get("sync", {})
        self.retry_count: int = sync.get("retry_count", 3)
        self.retry_backoff: list[int] = sync.get("retry_backoff", [5, 15, 30])
        self.approved_statuses: list[str] = sync.get("approved_statuses", DEFAULT_APPROVED_STATUSES)
        self.log_retention_days: int = sync.get("log_retention_days", 90)

        self.data_types: list[str] = raw.get("data_types", DATA_TYPES)

    def validate(self) -> list[str]:
        errors = []
        if not self.vps_hostname:
            errors.append("vps.hostname is required")
        if not self.vps_username:
            errors.append("vps.username is required")
        if not self.vps_ssh_key_path:
            errors.append("vps.ssh_key_path is required")
        elif not Path(self.vps_ssh_key_path).exists():
            errors.append(f"SSH key not found: {self.vps_ssh_key_path}")
        if not str(self.primary_path):
            errors.append("local.primary_path is required")
        if not str(self.backup_path):
            errors.append("local.backup_path is required")
        return errors
