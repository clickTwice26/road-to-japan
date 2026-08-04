"""Application factory."""

from __future__ import annotations

import structlog
from flask import Flask, jsonify

from app.config import Settings, get_settings
from app.errors import register_error_handlers
from app.extensions import cache, cors, db, init_redis, limiter, migrate
from app.logging_config import configure_logging, register_request_logging

__version__ = "0.1.0"

log = structlog.get_logger(__name__)


def create_app(settings: Settings | None = None) -> Flask:
    """Build a fully wired Flask application.

    Passing ``settings`` lets tests construct an app against a throwaway
    database without touching the process environment.
    """
    settings = settings or get_settings()

    configure_logging(level=settings.LOG_LEVEL, json_output=settings.LOG_JSON)

    app = Flask(__name__)
    app.config.from_mapping(settings.as_flask_config())
    app.extensions["settings"] = settings

    _init_extensions(app, settings)
    _register_blueprints(app, settings)
    register_error_handlers(app)
    register_request_logging(app)

    from app.cli import register_cli

    register_cli(app)

    log.info("app_initialised", env=settings.ENV, version=__version__)
    return app


def _init_extensions(app: Flask, settings: Settings) -> None:
    db.init_app(app)
    migrate.init_app(app, db, directory="migrations", compare_type=True)
    cache.init_app(app)
    limiter.init_app(app)
    cors.init_app(
        app,
        resources={rf"{settings.API_PREFIX}/*": {"origins": settings.CORS_ORIGINS}},
        supports_credentials=True,
    )
    init_redis(settings.REDIS_SESSION_URL)

    # Import models so Alembic autogenerate and `db.create_all()` see them.
    from app import models  # noqa: F401


def _register_blueprints(app: Flask, settings: Settings) -> None:
    from app.api import api_v1

    app.register_blueprint(api_v1, url_prefix=settings.API_PREFIX)

    @app.get("/")
    def index():
        return jsonify(
            service=settings.APP_NAME,
            version=__version__,
            environment=settings.ENV,
            docs=f"{settings.API_PREFIX}/health/ready",
        )
