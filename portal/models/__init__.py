"""Portal data models — local JSON storage."""

import os
from pathlib import Path


def get_data_dir() -> Path:
    explicit = os.environ.get("PORTAL_DATA_DIR")
    if explicit:
        return Path(explicit)
    ops_root = os.environ.get("DISPATCH_OPERATIONS_ROOT")
    if ops_root:
        return Path(ops_root) / "Current Workspace" / "PortalData"
    return Path(__file__).resolve().parent.parent / "data"


def get_memory_dir() -> Path:
    explicit = os.environ.get("DISPATCH_MEMORY_ROOT")
    if explicit:
        return Path(explicit)
    return get_data_dir()


def get_archive_dir() -> Path:
    explicit = os.environ.get("DISPATCH_ARCHIVE_ROOT")
    if explicit:
        return Path(explicit)
    return get_data_dir()
