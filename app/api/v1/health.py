"""Liveness and readiness probes."""

from __future__ import annotations

from typing import Any

import structlog
from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from app.extensions import db, limiter, redis_client

log = structlog.get_logger(__name__)

bp = Blueprint("health", __name__, url_prefix="/health")


def _check_postgres() -> tuple[bool, str | None]:
    try:
        db.session.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # noqa: BLE001 - probe reports, never raises
        log.warning("healthcheck_postgres_failed", error=str(exc))
        return False, str(exc)


def _check_redis() -> tuple[bool, str | None]:
    try:
        redis_client.ping()
        return True, None
    except Exception as exc:  # noqa: BLE001 - probe reports, never raises
        log.warning("healthcheck_redis_failed", error=str(exc))
        return False, str(exc)


@bp.get("/live")
@limiter.exempt
def live():
    """Process is up. Deliberately checks no dependencies — a failing database
    must not cause the orchestrator to restart a healthy container."""
    return jsonify(status="ok", service=current_app.config["APP_NAME"]), 200


@bp.get("/ready")
@limiter.exempt
def ready():
    """Dependencies are reachable, so this instance can serve traffic."""
    pg_ok, pg_err = _check_postgres()
    redis_ok, redis_err = _check_redis()

    checks: dict[str, Any] = {
        "postgres": {"ok": pg_ok, **({"error": pg_err} if pg_err else {})},
        "redis": {"ok": redis_ok, **({"error": redis_err} if redis_err else {})},
    }
    healthy = pg_ok and redis_ok
    return jsonify(status="ok" if healthy else "degraded", checks=checks), (200 if healthy else 503)
