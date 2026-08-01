"""Portal data models — local JSON storage."""

import os
from pathlib import Path


def get_data_dir() -> Path:
    default = str(Path(__file__).resolve().parent.parent / "data")
    return Path(os.environ.get("PORTAL_DATA_DIR", default))
