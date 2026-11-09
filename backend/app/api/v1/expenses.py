from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import get_current_user
from app.db.dynamodb import get_table
from app.schemas import ExpenseCreate, ExpenseResponse, ExpenseUpdate, MonthlySummary
from app.services import expense_service

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get("/monthly-summary", response_model=list[MonthlySummary])
def monthly_summary(user_id: str = Depends(get_current_user), table=Depends(get_table)):
    return expense_service.monthly_summary(table, user_id)


@router.get("/", response_model=list[ExpenseResponse])
def list_expenses(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    store: str | None = Query(None),
    user_id: str = Depends(get_current_user),
    table=Depends(get_table),
):
    return expense_service.list_expenses(table, user_id, start_date, end_date, store)


@router.post("/", response_model=ExpenseResponse, status_code=201)
def create_expense(
    payload: ExpenseCreate, user_id: str = Depends(get_current_user), table=Depends(get_table)
):
    return expense_service.create_expense(table, user_id, payload)


@router.get("/{expense_id}", response_model=ExpenseResponse)
def get_expense(
    expense_id: str, user_id: str = Depends(get_current_user), table=Depends(get_table)
):
    expense = expense_service.get_expense(table, user_id, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@router.put("/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    expense_id: str,
    payload: ExpenseUpdate,
    user_id: str = Depends(get_current_user),
    table=Depends(get_table),
):
    updated = expense_service.update_expense(table, user_id, expense_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Expense not found")
    return updated


@router.delete("/{expense_id}", status_code=204)
def delete_expense(
    expense_id: str, user_id: str = Depends(get_current_user), table=Depends(get_table)
):
    if not expense_service.delete_expense(table, user_id, expense_id):
        raise HTTPException(status_code=404, detail="Expense not found")
