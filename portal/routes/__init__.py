"""Route registration for the Portal."""

from flask import Flask

from portal.routes.pages import pages_bp
from portal.routes.api import api_bp
from portal.routes.auth import auth_bp
from portal.routes.decisions import decisions_bp
from portal.routes.pipeline import pipeline_bp
from portal.routes.dispatch_api import dispatch_bp


def register_routes(app: Flask) -> None:
    app.register_blueprint(auth_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(decisions_bp, url_prefix="/api")
    app.register_blueprint(pipeline_bp, url_prefix="/api/pipeline")
    app.register_blueprint(dispatch_bp, url_prefix="/api/dispatch")
