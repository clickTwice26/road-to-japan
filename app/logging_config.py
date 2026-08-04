"""structlog setup: JSON in production, coloured key-value pairs in dev."""

from __future__ import annotations

import logging
import sys
import uuid

import structlog
from flask import Flask, g, request


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
        force=True,
    )
    # Gunicorn installs its own handlers; route them through structlog's format.
    for name in ("gunicorn.error", "gunicorn.access", "werkzeug"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True

    processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    processors.append(
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def register_request_logging(app: Flask) -> None:
    """Attach a request id to every log line emitted while handling a request."""
    log = structlog.get_logger("http")

    @app.before_request
    def _bind_request_context() -> None:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        g.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.path,
            remote_addr=request.remote_addr,
        )

    @app.after_request
    def _log_response(response):
        response.headers["X-Request-ID"] = g.get("request_id", "")
        log.info("request_completed", status=response.status_code)
        return response

    @app.teardown_request
    def _clear_context(exc: BaseException | None = None) -> None:
        structlog.contextvars.clear_contextvars()
