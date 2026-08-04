"""Application exceptions and the JSON error contract.

Every error leaving the API has the same shape::

    {"error": {"code": "not_found", "message": "User not found"}}

so clients can branch on ``code`` without parsing prose.
"""

from __future__ import annotations

from typing import Any

import structlog
from flask import Flask, jsonify
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.exceptions import HTTPException

log = structlog.get_logger(__name__)


class AppError(Exception):
    """Base class for errors we deliberately surface to the client."""

    status_code = 500
    code = "internal_error"
    message = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details is not None:
            payload["details"] = self.details
        return {"error": payload}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "Resource not found."


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "Resource already exists."


class ValidationFailedError(AppError):
    status_code = 422
    code = "validation_failed"
    message = "Request payload failed validation."


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    message = "Authentication required."


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
    message = "You do not have access to this resource."


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"
    message = "A required dependency is unavailable."


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AppError)
    def _handle_app_error(exc: AppError):
        log.warning("app_error", code=exc.code, message=exc.message, status=exc.status_code)
        return jsonify(exc.to_dict()), exc.status_code

    @app.errorhandler(ValidationError)
    def _handle_pydantic_error(exc: ValidationError):
        err = ValidationFailedError(details=exc.errors(include_url=False, include_context=False))
        return jsonify(err.to_dict()), err.status_code

    @app.errorhandler(IntegrityError)
    def _handle_integrity_error(exc: IntegrityError):
        from app.extensions import db

        db.session.rollback()
        log.warning("integrity_error", error=str(exc.orig))
        err = ConflictError("The operation violates a database constraint.")
        return jsonify(err.to_dict()), err.status_code

    @app.errorhandler(SQLAlchemyError)
    def _handle_sqlalchemy_error(exc: SQLAlchemyError):
        from app.extensions import db

        db.session.rollback()
        log.exception("database_error")
        err = AppError("A database error occurred.", code="database_error")
        return jsonify(err.to_dict()), err.status_code

    @app.errorhandler(HTTPException)
    def _handle_http_exception(exc: HTTPException):
        payload = {
            "error": {
                "code": (exc.name or "http_error").lower().replace(" ", "_"),
                "message": exc.description or "",
            }
        }
        return jsonify(payload), exc.code or 500

    @app.errorhandler(Exception)
    def _handle_unexpected(exc: Exception):
        log.exception("unhandled_exception")
        err = AppError()
        return jsonify(err.to_dict()), err.status_code
