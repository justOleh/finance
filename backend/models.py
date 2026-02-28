"""
backend.models
--------------
SQLAlchemy ORM models for the My Finance application.

Tables
~~~~~~
users
    Optional user accounts.  For the current single/two-user use-case the
    ``user_id`` foreign-key on expenses is nullable, so authentication is not
    required.

expenses
    Core table that stores every tracked expense.  The ``items`` column holds a
    JSON-encoded list of ``{"name": str, "price": float}`` dicts.  The Python
    ``items`` property transparently serialises/deserialises the JSON so callers
    work with plain Python lists.

All ``created_at`` timestamps are stored in UTC.
"""

import json
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Date, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base


def _utcnow():
    """Return the current UTC datetime (used as a column default)."""
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    expenses = relationship("Expense", back_populates="user")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    store = Column(String, nullable=False)
    _items = Column("items", Text, nullable=False, default="[]")
    total = Column(Float, nullable=False)
    receipt_image_path = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="expenses")

    @property
    def items(self) -> list:
        try:
            return json.loads(self._items) if self._items else []
        except (json.JSONDecodeError, TypeError):
            return []

    @items.setter
    def items(self, value: list):
        self._items = json.dumps(value)
