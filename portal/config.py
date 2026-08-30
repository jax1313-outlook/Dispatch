"""Portal configuration — environment-based, VPS-ready."""

import os
import sys
from datetime import timedelta
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

    # Session cookie policy. Flask sets none of these by default, which left
    # sessions that never expired, were readable by scripts, and were sent
    # over plain HTTP. SECURE is env-gated because a local HTTP run would
    # otherwise never receive the cookie at all.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("PORTAL_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=int(os.environ.get("PORTAL_SESSION_HOURS", "12"))
    )


class InsecureConfigurationError(RuntimeError):
    """Raised instead of starting an operational deployment on a published
    default secret."""


# Both of these are published in this repository. A deployment that misses the
# environment variable is not "using a weak key" -- it is using a key anyone
# who can read the source already knows, which makes every signed session
# cookie forgeable and every stakeholder and decision link mintable by a
# stranger.
_PUBLISHED_DEFAULTS = {
    "PORTAL_SECRET_KEY": _DEFAULT_SECRET,
    "DISPATCH_EMAIL_SECRET": "dispatch-dev-secret",
}


def is_development_mode() -> bool:
    """Development mode is opt-in and explicit.

    The default is operational, deliberately. A misconfigured deployment must
    fail loudly rather than quietly behave like a dev box -- the failure mode
    being designed against is someone putting this on a VPS having forgotten
    one environment variable, and it working.
    """
    return os.environ.get("DISPATCH_MODE", "operational").strip().lower() in (
        "dev", "development", "local"
    )


def check_secrets(*, host: str | None = None) -> list[str]:
    """Refuse to start an operational deployment on a default secret.

    Returns the warnings issued in development mode; raises in operational
    mode. Called from create_app(), so nothing can reach a route without
    having passed through here.
    """
    weak = [
        name
        for name, published in _PUBLISHED_DEFAULTS.items()
        if os.environ.get(name, published) == published
    ]
    if not weak:
        return []

    listed = ", ".join(sorted(weak))
    if not is_development_mode():
        raise InsecureConfigurationError(
            f"Refusing to start: {listed} is unset or still set to the published "
            f"default from this repository. Set a real value, or set "
            f"DISPATCH_MODE=development to run locally with reduced protection."
        )

    warnings = [
        f"portal: DEVELOPMENT MODE — {listed} is a published default. "
        f"Sessions are forgeable and every signed link is mintable by anyone "
        f"who can read this repository. Never expose this process."
    ]
    bind = host if host is not None else Config.HOST
    if bind not in ("127.0.0.1", "localhost", "::1"):
        warnings.append(
            f"portal: DEVELOPMENT MODE refuses to bind {bind}. A development "
            f"process running on published secrets stays on the loopback "
            f"interface; set real secrets to bind anything else."
        )
    for line in warnings:
        print(line, file=sys.stderr)
    return warnings


def development_host(requested: str) -> str:
    """In development mode a process running on published secrets is pinned to
    the loopback interface. This is the one place the mode actually restricts
    behaviour rather than just talking about it."""
    if is_development_mode() and requested not in ("127.0.0.1", "localhost", "::1"):
        return "127.0.0.1"
    return requested


def check_secret_key() -> None:
    """Backwards-compatible name for the pre-campaign warning-only check."""
    check_secrets()
