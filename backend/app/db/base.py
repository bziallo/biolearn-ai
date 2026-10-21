from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


def utc_now() -> datetime:
    """Return an aware UTC timestamp for application-side defaults."""

    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Shared SQLAlchemy declarative base for all ORM models."""
