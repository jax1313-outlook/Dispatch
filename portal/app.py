"""L2-COS Operations Portal v1 — app.py entry point.

Run locally:
    python portal/app.py

Or from project root:
    python -m portal.app
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, redirect, request, session, url_for

from portal.config import Config, check_secret_key
from portal.routes import register_routes


def create_app(config: dict | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )
    app.config.from_object(Config)
    if config:
        app.config.update(config)
    if not app.config.get("TESTING"):
        check_secret_key()
    register_routes(app)

    @app.before_request
    def _require_authority_login():
        """DISPATCH_PIN login gate (PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md, Claude-3
        repo). Fails closed in real (non-TESTING) use: a missing/unbootstrapped identity does
        NOT bypass this gate -- it just means /login correctly reports there's nothing to log
        into yet, rather than the rest of Portal silently staying open.

        LOGIN_DISABLED (Flask-Login's own config-key convention, reused here) defaults to
        TESTING's value, checked live on every request rather than snapshotted once at
        create_app() time -- most of the ~67 pre-existing test files in this repo call
        create_app() with no config dict at all and set app.config["TESTING"] = True on the
        returned app afterward, which a creation-time default would miss entirely. Checking
        live means none of those files need individual changes. A config dict that explicitly
        passes LOGIN_DISABLED (True or False) at creation time still wins, since that sets
        app.config directly -- see TestDispatchPinAuthentication in tests/test_portal.py,
        which passes False to exercise the real gate under TESTING.

        The `decisions` blueprint (cin_lite's HMAC-token email action links) is excluded on
        purpose: those links must work without a browser session, and already carry their own,
        separate token-based authentication -- see portal/routes/decisions.py.
        """
        login_disabled = app.config.get("LOGIN_DISABLED")
        if login_disabled is None:
            login_disabled = app.config.get("TESTING", False)
        if login_disabled:
            return None
        if request.endpoint is None or request.endpoint == "static":
            return None
        if request.blueprint == "decisions":
            return None
        if request.endpoint in ("auth.login", "auth.logout"):
            return None
        if not session.get("user_id"):
            return redirect(url_for("auth.login"))
        return None

    @app.template_filter("time_ago")
    def _time_ago(iso_str: str) -> str:
        if not iso_str:
            return "—"
        from datetime import datetime, timezone
        try:
            ts = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return "—"
        delta = datetime.now(timezone.utc) - ts
        hours = delta.total_seconds() / 3600
        if hours < 1:
            return f"{int(delta.total_seconds() / 60)}m"
        if hours < 24:
            return f"{int(hours)}h"
        days = int(hours / 24)
        return f"{days}d"

    return app


def _ensure_storage_dirs() -> None:
    """Create the D:\\ folder tree on startup when root env vars are set."""
    ops_root = os.environ.get("DISPATCH_OPERATIONS_ROOT")
    if ops_root:
        for sub in (
            "Code", "Constitution", "Context", "Config", "Launchers",
            "Logs", "Temp", "Current Workspace", "Deployment",
        ):
            Path(ops_root, sub).mkdir(parents=True, exist_ok=True)
        Path(ops_root, "Current Workspace", "PortalData").mkdir(parents=True, exist_ok=True)

    archive_root = os.environ.get("DISPATCH_ARCHIVE_ROOT")
    if archive_root:
        for sub in ("Loads", "POD", "Retention", "Reports", "Historical Records"):
            Path(archive_root, sub).mkdir(parents=True, exist_ok=True)
        cin = Path(archive_root, "CIN")
        for cin_sub in (
            "Raw", "Processed", "Intelligence", "Summaries",
            "Routing", "Proposals", "Pending", "Outbox",
        ):
            (cin / cin_sub).mkdir(parents=True, exist_ok=True)

    memory_root = os.environ.get("DISPATCH_MEMORY_ROOT")
    if memory_root:
        for sub in (
            "Company Library", "Broker Library", "Customer Library",
            "Location Intelligence", "Operational Intelligence",
            "Forms", "Templates", "Procedures", "Manuals",
            "Receipts", "Fuel", "Compliance", "Equipment",
            "Drivers", "Insurance", "Certifications", "Evidence", "Documents",
        ):
            Path(memory_root, sub).mkdir(parents=True, exist_ok=True)


def _print_storage_map() -> None:
    from cin_lite import archive as cin_archive
    from dispatch.db import get_db_path
    from dispatch.services import _get_upload_dir
    from portal.models import get_memory_dir, get_archive_dir

    print("  Storage Roots:")
    ops = os.environ.get("DISPATCH_OPERATIONS_ROOT")
    arc = os.environ.get("DISPATCH_ARCHIVE_ROOT")
    mem = os.environ.get("DISPATCH_MEMORY_ROOT")
    print(f"    Operations       {ops or '(not set — using defaults)'}")
    print(f"    Archive          {arc or '(not set — using defaults)'}")
    print(f"    Memory           {mem or '(not set — using defaults)'}")
    print()
    print("  Resolved Paths:")
    print(f"    Database         {get_db_path().resolve()}")
    from portal.models import get_data_dir
    print(f"    Portal data      {get_data_dir().resolve()}")
    print(f"    Evidence uploads {_get_upload_dir().resolve()}")
    print(f"    Contract archive {cin_archive.ARCHIVE_ROOT.resolve()}")
    print(f"    Email outbox     {(cin_archive.ARCHIVE_ROOT / 'Outbox').resolve()}")
    print(f"    Library/Intel    {get_memory_dir().resolve()}")
    print(f"    Archive records  {get_archive_dir().resolve()}")
    print()


if __name__ == "__main__":
    _ensure_storage_dirs()
    app = create_app()
    host = Config.HOST
    port = Config.PORT
    print(f"\n  L2-COS Operations Portal v1")
    print(f"  http://{host}:{port}\n")
    _print_storage_map()
    app.run(host=host, port=port, debug=True)
