"""Portal configuration — environment-based, VPS-ready."""

import os
import sys
from pathlib import Path

_PORTAL_DIR = Path(__file__).resolve().parent

_DEFAULT_SECRET = "dev-portal-key-change-in-production"


class Config:
    SECRET_KEY = os.environ.get("PORTAL_SECRET_KEY", _DEFAULT_SECRET)
    DATA_DIR = os.environ.get("PORTAL_DATA_DIR", str(_PORTAL_DIR / "data"))
    INQUIRY_THRESHOLD = int(os.environ.get("PORTAL_INQUIRY_THRESHOLD", "90"))
    INQUIRY_MODE = os.environ.get("PORTAL_INQUIRY_MODE", "HUMAN_REVIEW")
    HOST = os.environ.get("PORTAL_HOST", "127.0.0.1")
    PORT = int(os.environ.get("PORTAL_PORT", "8080"))


def check_secret_key() -> None:
    if Config.SECRET_KEY == _DEFAULT_SECRET:
        print("portal: WARNING — using the default SECRET_KEY; "
              "set PORTAL_SECRET_KEY for production use.", file=sys.stderr)
