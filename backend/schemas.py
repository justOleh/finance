"""
backend.schemas
---------------
Pydantic v2 request/response schemas for the My Finance API.

Classes
~~~~~~~
ExpenseCreate
    Payload for ``POST /expenses``.
ExpenseUpdate
    Partial-update payload for ``PUT /expenses/{id}``.  All fields are
    optional; only supplied fields are applied.
ExpenseResponse
    Full expense representation returned by every expense endpoint.
UserCreate
    Payload for creating a user account (reserved for future auth).
UserResponse
    Public user representation (no password hash exposed).
"""

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
    user_id: Optional[int] = None
    created_at: datetime


class UserCreate(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    created_at: datetime
