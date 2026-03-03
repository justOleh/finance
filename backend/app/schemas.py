from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class MonthlySummary(BaseModel):
    year: int
    month: int
    total: float
    count: int


class ExpenseCreate(BaseModel):
    date: date
    store: str
    items: list[dict]
    total: float
    notes: Optional[str] = None


class ExpenseUpdate(BaseModel):
    date: Optional[date] = None
    store: Optional[str] = None
    items: Optional[list[dict]] = None
    total: Optional[float] = None
    notes: Optional[str] = None


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    store: str
    items: list[dict]
    total: float
    receipt_image_path: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
