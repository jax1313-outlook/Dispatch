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

from flask import Flask

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


def _print_storage_map() -> None:
    from cin_lite import archive as cin_archive
    from dispatch.db import get_db_path
    from dispatch.services import _get_upload_dir

    print("  Storage:")
    print(f"    Database         {get_db_path().resolve()}")
    print(f"    Portal data      {Path(Config.DATA_DIR).resolve()}")
    print(f"    Evidence uploads {_get_upload_dir().resolve()}")
    print(f"    Contract archive {cin_archive.ARCHIVE_ROOT.resolve()}")
    print(f"    Email outbox     {(cin_archive.ARCHIVE_ROOT / 'Outbox').resolve()}")
    print()


if __name__ == "__main__":
    app = create_app()
    host = Config.HOST
    port = Config.PORT
    print(f"\n  L2-COS Operations Portal v1")
    print(f"  http://{host}:{port}\n")
    _print_storage_map()
    app.run(host=host, port=port, debug=True)
