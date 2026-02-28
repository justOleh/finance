from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from models import Expense
from schemas import ExpenseCreate, ExpenseUpdate, ExpenseResponse

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
