"""Portal configuration — environment-based, VPS-ready."""

import os
from pathlib import Path

_PORTAL_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("PORTAL_SECRET_KEY", "dev-portal-key-change-in-production")
    DATA_DIR = os.environ.get("PORTAL_DATA_DIR", str(_PORTAL_DIR / "data"))
    INQUIRY_THRESHOLD = int(os.environ.get("PORTAL_INQUIRY_THRESHOLD", "90"))
    INQUIRY_MODE = os.environ.get("PORTAL_INQUIRY_MODE", "HUMAN_REVIEW")
    HOST = os.environ.get("PORTAL_HOST", "127.0.0.1")
    PORT = int(os.environ.get("PORTAL_PORT", "8080"))
