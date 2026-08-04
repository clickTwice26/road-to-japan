"""Decorators that turn request data into validated pydantic models."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from flask import request
from pydantic import BaseModel, ValidationError

from app.errors import ValidationFailedError

M = TypeVar("M", bound=BaseModel)
F = TypeVar("F", bound=Callable[..., Any])


def _fail(exc: ValidationError) -> ValidationFailedError:
    return ValidationFailedError(
        details=exc.errors(include_url=False, include_context=False)
    )


def validate_body(model: type[M]) -> Callable[[F], F]:
    """Parse and validate the JSON body, injecting it as the ``body`` kwarg."""

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            payload = request.get_json(silent=True)
            if payload is None:
                raise ValidationFailedError("Request body must be valid JSON.")
            try:
                kwargs["body"] = model.model_validate(payload)
            except ValidationError as exc:
                raise _fail(exc) from exc
            return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def validate_query(model: type[M]) -> Callable[[F], F]:
    """Validate the query string, injecting it as the ``query`` kwarg."""

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                kwargs["query"] = model.model_validate(request.args.to_dict())
            except ValidationError as exc:
                raise _fail(exc) from exc
            return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
