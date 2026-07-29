"""Route registration for the Portal."""

from flask import Flask

from portal.routes.pages import pages_bp
from portal.routes.api import api_bp


def register_routes(app: Flask) -> None:
    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
