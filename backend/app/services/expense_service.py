from datetime import date
from typing import Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.expense import Expense
from app.schemas import ExpenseCreate, ExpenseUpdate, MonthlySummary


def list_expenses(db: Session, start_date: Optional[date], end_date: Optional[date], store: Optional[str]) -> list[Expense]:
    query = db.query(Expense)
    if start_date:
        query = query.filter(Expense.date >= start_date)
    if end_date:
        query = query.filter(Expense.date <= end_date)
    if store:
        query = query.filter(Expense.store.ilike(f"%{store}%"))
    return query.order_by(Expense.date.desc()).all()


def get_expense(db: Session, expense_id: int) -> Expense | None:
    return db.query(Expense).filter(Expense.id == expense_id).first()


def create_expense(db: Session, payload: ExpenseCreate) -> Expense:
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
    return expense


def update_expense(db: Session, expense: Expense, payload: ExpenseUpdate) -> Expense:
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
    return expense


def delete_expense(db: Session, expense: Expense) -> None:
    db.delete(expense)
    db.commit()


def monthly_summary(db: Session) -> list[MonthlySummary]:
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
