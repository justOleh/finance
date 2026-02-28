"""
backend.routers.expenses
------------------------
FastAPI router for expense CRUD operations (``/expenses`` prefix).

Endpoints
~~~~~~~~~
GET    /expenses                 List all expenses; supports ``start_date``,
                                 ``end_date``, and ``store`` query-string filters.
POST   /expenses                 Create a new expense record.
GET    /expenses/monthly-summary Monthly aggregated totals and counts.
GET    /expenses/{id}            Retrieve a single expense by primary-key ID.
PUT    /expenses/{id}            Partially update an existing expense.
DELETE /expenses/{id}            Delete an expense (returns HTTP 204 No Content).

All responses use the ``ExpenseResponse`` Pydantic schema.
"""

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
from models import Expense
from schemas import ExpenseCreate, ExpenseUpdate, ExpenseResponse, MonthlySummary

router = APIRouter(prefix="/expenses", tags=["expenses"])



def _to_response(expense: Expense) -> ExpenseResponse:
    return ExpenseResponse(
        id=expense.id,
        date=expense.date,
        store=expense.store,
        items=expense.items,
        total=expense.total,
        receipt_image_path=expense.receipt_image_path,
        notes=expense.notes,
        user_id=expense.user_id,
        created_at=expense.created_at,
    )


@router.get("/monthly-summary", response_model=list[MonthlySummary])
def monthly_summary(db: Session = Depends(get_db)):
    """Return total spending and expense count grouped by year and month."""
    rows = (
        db.query(
            func.strftime("%Y", Expense.date).label("year"),
            func.strftime("%m", Expense.date).label("month"),
            func.sum(Expense.total).label("total"),
            func.count(Expense.id).label("count"),
        )
        .group_by(
            func.strftime("%Y", Expense.date),
            func.strftime("%m", Expense.date),
        )
        .order_by(
            func.strftime("%Y", Expense.date),
            func.strftime("%m", Expense.date),
        )
        .all()
    )
    return [
        MonthlySummary(year=int(r.year), month=int(r.month), total=r.total, count=r.count)
        for r in rows
    ]


@router.get("/", response_model=list[ExpenseResponse])
def list_expenses(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    store: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Expense)
    if start_date:
        query = query.filter(Expense.date >= start_date)
    if end_date:
        query = query.filter(Expense.date <= end_date)
    if store:
        query = query.filter(Expense.store.ilike(f"%{store}%"))
    expenses = query.order_by(Expense.date.desc()).all()
    return [_to_response(e) for e in expenses]


@router.post("/", response_model=ExpenseResponse, status_code=201)
def create_expense(payload: ExpenseCreate, db: Session = Depends(get_db)):
    expense = Expense(
        date=payload.date,
        store=payload.store,
        total=payload.total,
        notes=payload.notes,
    )
    expense.items = payload.items
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return _to_response(expense)


@router.get("/{expense_id}", response_model=ExpenseResponse)
def get_expense(expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return _to_response(expense)


@router.put("/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    expense_id: int, payload: ExpenseUpdate, db: Session = Depends(get_db)
):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    if payload.date is not None:
        expense.date = payload.date
    if payload.store is not None:
        expense.store = payload.store
    if payload.items is not None:
        expense.items = payload.items
    if payload.total is not None:
        expense.total = payload.total
    if payload.notes is not None:
        expense.notes = payload.notes
    db.commit()
    db.refresh(expense)
    return _to_response(expense)


@router.delete("/{expense_id}", status_code=204)
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(expense)
    db.commit()
