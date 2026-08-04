"""API v1 — mounts every resource blueprint under a single parent."""

from __future__ import annotations

from flask import Blueprint

from app.api.v1 import health, users

api_v1 = Blueprint("api_v1", __name__)
api_v1.register_blueprint(health.bp)
api_v1.register_blueprint(users.bp)

__all__ = ["api_v1"]
