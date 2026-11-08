import datetime as dt

from pydantic import BaseModel


class MonthlySummary(BaseModel):
    year: int
    month: int
    total: float
    count: int


class ExpenseCreate(BaseModel):
    date: dt.date
    store: str
    items: list[dict]
    total: float
    notes: str | None = None
    receipt_image_path: str | None = None


class ExpenseUpdate(BaseModel):
    date: dt.date | None = None
    store: str | None = None
    items: list[dict] | None = None
    total: float | None = None
    notes: str | None = None
    receipt_image_path: str | None = None


class ExpenseResponse(BaseModel):
    id: str
    date: dt.date
    store: str
    items: list[dict]
    total: float
    receipt_image_path: str | None = None
    notes: str | None = None
    created_at: dt.datetime


class ReceiptDraftResponse(BaseModel):
    date: dt.date
    store: str
    items: list[dict]
    total: float
    notes: str | None = None
    receipt_image_path: str | None = None
