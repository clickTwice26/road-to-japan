"""User CRUD endpoints."""

from __future__ import annotations

import uuid

from flask import Blueprint, jsonify

from app.extensions import limiter
from app.schemas.common import PaginationParams
from app.schemas.user import UserCreate, UserUpdate
from app.services import user_service
from app.utils.validation import validate_body, validate_query

bp = Blueprint("users", __name__, url_prefix="/users")


class UserListQuery(PaginationParams):
    active_only: bool = False


@bp.get("")
@validate_query(UserListQuery)
def list_users(query: UserListQuery):
    items, total = user_service.list_users(
        page=query.page, per_page=query.per_page, active_only=query.active_only
    )
    pages = (total + query.per_page - 1) // query.per_page
    return jsonify(
        items=[u.model_dump(mode="json") for u in items],
        page=query.page,
        per_page=query.per_page,
        total=total,
        pages=pages,
    )


@bp.get("/<uuid:user_id>")
def get_user(user_id: uuid.UUID):
    return jsonify(user_service.get_user(user_id).model_dump(mode="json"))


@bp.post("")
@limiter.limit("10 per minute")
@validate_body(UserCreate)
def create_user(body: UserCreate):
    user = user_service.create_user(body)
    return jsonify(user.model_dump(mode="json")), 201


@bp.patch("/<uuid:user_id>")
@validate_body(UserUpdate)
def update_user(user_id: uuid.UUID, body: UserUpdate):
    return jsonify(user_service.update_user(user_id, body).model_dump(mode="json"))


@bp.delete("/<uuid:user_id>")
def delete_user(user_id: uuid.UUID):
    user_service.delete_user(user_id)
    return "", 204
