from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.expense import Expense
from app.schemas import ExpenseCreate, ExpenseUpdate, ExpenseResponse, MonthlySummary
from app.services import expense_service

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
        created_at=expense.created_at,
    )


@router.get("/monthly-summary", response_model=list[MonthlySummary])
def monthly_summary(db: Session = Depends(get_db)):
    return expense_service.monthly_summary(db)


@router.get("/", response_model=list[ExpenseResponse])
def list_expenses(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    store: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    expenses = expense_service.list_expenses(db, start_date, end_date, store)
    return [_to_response(e) for e in expenses]


@router.post("/", response_model=ExpenseResponse, status_code=201)
def create_expense(payload: ExpenseCreate, db: Session = Depends(get_db)):
    expense = expense_service.create_expense(db, payload)
    return _to_response(expense)


@router.get("/{expense_id}", response_model=ExpenseResponse)
def get_expense(expense_id: int, db: Session = Depends(get_db)):
    expense = expense_service.get_expense(db, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return _to_response(expense)


@router.put("/{expense_id}", response_model=ExpenseResponse)
def update_expense(expense_id: int, payload: ExpenseUpdate, db: Session = Depends(get_db)):
    expense = expense_service.get_expense(db, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    updated = expense_service.update_expense(db, expense, payload)
    return _to_response(updated)


@router.delete("/{expense_id}", status_code=204)
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    expense = expense_service.get_expense(db, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    expense_service.delete_expense(db, expense)
