from datetime import date
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from app.schemas import ExpenseCreate, ExpenseUpdate, ExpenseResponse, MonthlySummary
from app.services import expense_service

router = APIRouter(prefix="/expenses", tags=["expenses"])


def _get_or_404(expense_id: str) -> dict:
    expense = expense_service.get_expense(expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@router.get("/monthly-summary", response_model=list[MonthlySummary])
def monthly_summary():
    return expense_service.monthly_summary()


@router.get("/", response_model=list[ExpenseResponse])
def list_expenses(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    store: Optional[str] = Query(None),
):
    return expense_service.list_expenses(start_date, end_date, store)


@router.post("/", response_model=ExpenseResponse, status_code=201)
def create_expense(payload: ExpenseCreate):
    return expense_service.create_expense(payload)


@router.get("/{expense_id}", response_model=ExpenseResponse)
def get_expense(expense_id: str):
    return _get_or_404(expense_id)


@router.put("/{expense_id}", response_model=ExpenseResponse)
def update_expense(expense_id: str, payload: ExpenseUpdate):
    return expense_service.update_expense(_get_or_404(expense_id), payload)


@router.delete("/{expense_id}", status_code=204)
def delete_expense(expense_id: str):
    expense_service.delete_expense(_get_or_404(expense_id))
