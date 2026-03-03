import json
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Date, Text, DateTime
from app.db.session import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    store = Column(String, nullable=False)
    _items = Column("items", Text, nullable=False, default="[]")
    total = Column(Float, nullable=False)
    receipt_image_path = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    @property
    def items(self) -> list:
        try:
            return json.loads(self._items) if self._items else []
        except (json.JSONDecodeError, TypeError):
            return []

    @items.setter
    def items(self, value: list):
        self._items = json.dumps(value)
