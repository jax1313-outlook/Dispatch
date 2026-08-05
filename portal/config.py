"""Portal configuration — environment-based, VPS-ready."""

import os
import sys
from pathlib import Path

_PORTAL_DIR = Path(__file__).resolve().parent

_DEFAULT_SECRET = "dev-portal-key-change-in-production"


def _resolve_data_dir() -> str:
    explicit = os.environ.get("PORTAL_DATA_DIR")
    if explicit:
        return explicit
    ops_root = os.environ.get("DISPATCH_OPERATIONS_ROOT")
    if ops_root:
        return str(Path(ops_root) / "Current Workspace" / "PortalData")
    return str(_PORTAL_DIR / "data")


def _resolve_upload_dir() -> str:
    explicit = os.environ.get("PORTAL_UPLOAD_DIR")
    if explicit:
        return explicit
    memory_root = os.environ.get("DISPATCH_MEMORY_ROOT")
    if memory_root:
        return str(Path(memory_root) / "Evidence")
    return str(Path(_resolve_data_dir()) / "uploads")


class Config:
    SECRET_KEY = os.environ.get("PORTAL_SECRET_KEY", _DEFAULT_SECRET)
    DATA_DIR = _resolve_data_dir()
    UPLOAD_FOLDER = _resolve_upload_dir()
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB
    INQUIRY_THRESHOLD = int(os.environ.get("PORTAL_INQUIRY_THRESHOLD", "90"))
    INQUIRY_MODE = os.environ.get("PORTAL_INQUIRY_MODE", "HUMAN_REVIEW")
    HOST = os.environ.get("PORTAL_HOST", "127.0.0.1")
    PORT = int(os.environ.get("PORTAL_PORT", "8080"))


def check_secret_key() -> None:
    if Config.SECRET_KEY == _DEFAULT_SECRET:
        print("portal: WARNING — using the default SECRET_KEY; "
              "set PORTAL_SECRET_KEY for production use.", file=sys.stderr)
