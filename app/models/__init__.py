"""SQLAlchemy models.

Every model must be imported here — Alembic's autogenerate only sees tables
that are registered on ``Base.metadata`` at import time.
"""

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import User

__all__ = ["Base", "TimestampMixin", "UUIDPrimaryKeyMixin", "User"]
