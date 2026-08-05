"""User business logic.

Routes stay thin: they parse, delegate here, and serialise. Anything that
touches the database or the cache lives in this layer so it can be unit-tested
without an HTTP request.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import func, select

from app.errors import ConflictError, NotFoundError
from app.extensions import cache, db
from app.models import User
from app.schemas.user import UserCreate, UserRead, UserUpdate

log = structlog.get_logger(__name__)

CACHE_TTL = 300


def _cache_key(user_id: uuid.UUID) -> str:
    return f"user:{user_id}"


def _invalidate(user_id: uuid.UUID) -> None:
    cache.delete(_cache_key(user_id))


def get_user(user_id: uuid.UUID) -> UserRead:
    """Read-through cache: Redis first, Postgres on miss."""
    cached = cache.get(_cache_key(user_id))
    if cached is not None:
        return UserRead.model_validate(cached)

    user = db.session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found.")

    dto = UserRead.model_validate(user)
    cache.set(_cache_key(user_id), dto.model_dump(mode="json"), timeout=CACHE_TTL)
    return dto


def list_users(
    page: int, per_page: int, *, active_only: bool = False
) -> tuple[list[UserRead], int]:
    stmt = select(User).order_by(User.created_at.desc())
    count_stmt = select(func.count()).select_from(User)
    if active_only:
        stmt = stmt.where(User.is_active.is_(True))
        count_stmt = count_stmt.where(User.is_active.is_(True))

    total = db.session.scalar(count_stmt) or 0
    rows = db.session.scalars(stmt.offset((page - 1) * per_page).limit(per_page)).all()
    return [UserRead.model_validate(r) for r in rows], total


def create_user(data: UserCreate) -> UserRead:
    exists = db.session.scalar(select(User.id).where(User.email == data.email))
    if exists is not None:
        raise ConflictError(f"A user with email {data.email} already exists.")

    user = User(email=data.email, full_name=data.full_name)
    user.set_password(data.password)
    db.session.add(user)
    db.session.commit()

    log.info("user_created", user_id=str(user.id))
    return UserRead.model_validate(user)


def update_user(user_id: uuid.UUID, data: UserUpdate) -> UserRead:
    user = db.session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found.")

    fields = data.model_dump(exclude_unset=True)

    new_email = fields.pop("email", None)
    if new_email is not None and new_email != user.email:
        clash = db.session.scalar(select(User.id).where(User.email == new_email))
        if clash is not None:
            raise ConflictError(f"A user with email {new_email} already exists.")
        user.email = new_email

    password = fields.pop("password", None)
    if password is not None:
        user.set_password(password)

    for key, value in fields.items():
        setattr(user, key, value)

    db.session.commit()
    _invalidate(user_id)

    log.info("user_updated", user_id=str(user_id), fields=sorted(data.model_fields_set))
    return UserRead.model_validate(user)


def delete_user(user_id: uuid.UUID) -> None:
    user = db.session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found.")

    db.session.delete(user)
    db.session.commit()
    _invalidate(user_id)

    log.info("user_deleted", user_id=str(user_id))
