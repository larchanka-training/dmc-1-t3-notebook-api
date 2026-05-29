"""
Base factory for SQLAlchemy models using factory-boy.

Usage:

    from tests.factories import BaseFactory

    class UserFactory(BaseFactory):
        class Meta:
            model = User

        email = factory.Faker("email")

The `sqlalchemy_session` attribute is bound at runtime by the autouse
`_bind_factory_session` fixture in `tests/conftest.py`, using whichever
`db_session` is active for the current test.
"""
from __future__ import annotations

from factory.alchemy import SQLAlchemyModelFactory


class BaseFactory(SQLAlchemyModelFactory):
    class Meta:
        abstract = True
        sqlalchemy_session_persistence = "flush"
