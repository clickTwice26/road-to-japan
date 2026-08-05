"""Decorators that turn request data into validated pydantic models."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import request
from pydantic import BaseModel, ValidationError

from app.errors import ValidationFailedError


def _fail(exc: ValidationError) -> ValidationFailedError:
    return ValidationFailedError(details=exc.errors(include_url=False, include_context=False))


def validate_body[M: BaseModel](model: type[M]) -> Callable[[Callable], Callable]:
    """Parse and validate the JSON body, injecting it as the ``body`` kwarg."""

    def decorator(fn: Callable) -> Callable:
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

        return wrapper

    return decorator


def validate_query[M: BaseModel](model: type[M]) -> Callable[[Callable], Callable]:
    """Validate the query string, injecting it as the ``query`` kwarg."""

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                kwargs["query"] = model.model_validate(request.args.to_dict())
            except ValidationError as exc:
                raise _fail(exc) from exc
            return fn(*args, **kwargs)

        return wrapper

    return decorator
