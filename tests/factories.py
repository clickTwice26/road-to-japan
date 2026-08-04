"""Model factories for tests."""

from __future__ import annotations

import factory
from factory.alchemy import SQLAlchemyModelFactory
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import User

DEFAULT_PASSWORD = "password123"


class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session_factory = staticmethod(lambda: db.session)
        sqlalchemy_session_persistence = "commit"

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    full_name = factory.Faker("name")
    is_active = True
    password_hash = factory.LazyFunction(lambda: generate_password_hash(DEFAULT_PASSWORD))
