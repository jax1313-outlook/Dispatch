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
    return app


if __name__ == "__main__":
    app = create_app()
    host = Config.HOST
    port = Config.PORT
    print(f"\n  L2-COS Operations Portal v1")
    print(f"  http://{host}:{port}\n")
    app.run(host=host, port=port, debug=True)
