import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExpenseItem(BaseModel):
    """One line of an expense, as stored and returned.

    Lenient on purpose: items written before ADR-014 were free-form dicts (the old parser used
    `item_price`, tests used `qty`), so unknown fields are kept and missing ones get defaults.
    """

    model_config = ConfigDict(extra="allow")

    name: str = Field("", description="What was bought, as printed on the receipt.")
    price: float = Field(0.0, description="Amount paid for this line, in UAH.")

    @model_validator(mode="before")
    @classmethod
    def _legacy_price(cls, data):
        if isinstance(data, dict) and "price" not in data and "item_price" in data:
            return {**data, "price": data["item_price"]}
        return data


class ExpenseItemIn(ExpenseItem):
    """An item sent by a client: name and price are required."""

    name: str = Field(min_length=1, description="What was bought.")
    price: float = Field(description="Amount paid for this line, in UAH.")


class MonthlySummary(BaseModel):
    year: int
    month: int
    total: float
    count: int


SummaryGroupBy = Literal["none", "store", "month"]


class SummaryGroup(BaseModel):
    key: str = Field(description="Store name, or month as YYYY-MM.")
    total: float
    count: int


class SpendingSummary(BaseModel):
    """Totals computed by the backend, so no client (or model) has to add numbers up."""

    start_date: dt.date | None
    end_date: dt.date | None
    group_by: SummaryGroupBy
    total: float
    count: int
    groups: list[SummaryGroup] = Field(description="Largest total first; empty for group_by=none.")


class ExpenseCreate(BaseModel):
    date: dt.date
    store: str
    items: list[ExpenseItemIn]
    total: float
    notes: str | None = None
    receipt_image_path: str | None = None


class ExpenseUpdate(BaseModel):
    date: dt.date | None = None
    store: str | None = None
    items: list[ExpenseItemIn] | None = None
    total: float | None = None
    notes: str | None = None
    receipt_image_path: str | None = None


class ExpenseResponse(BaseModel):
    id: str
    date: dt.date
    store: str
    items: list[ExpenseItem]
    total: float
    receipt_image_path: str | None = None
    notes: str | None = None
    created_at: dt.datetime


class ReceiptDraftResponse(BaseModel):
    date: dt.date
    store: str
    items: list[ExpenseItem]
    total: float
    notes: str | None = None
    receipt_image_path: str | None = None


class ReceiptUploadRequest(BaseModel):
    content_type: str


class ReceiptUploadResponse(BaseModel):
    """Everything the browser needs for a direct S3 POST (fields first, file last)."""

    receipt_id: str
    upload_url: str
    fields: dict[str, str]


class ReceiptStatusResponse(BaseModel):
    id: str
    status: str  # UPLOADING | PARSED | FAILED
    error: str | None = None
    draft: ReceiptDraftResponse | None = None
