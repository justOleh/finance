import json
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from app.db.session import get_table
from app.schemas import ExpenseCreate, ExpenseUpdate, MonthlySummary


def _plain(value):
    """Convert DynamoDB Decimals back to int/float (recursively)."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def _to_dynamo(value):
    """DynamoDB rejects floats; round-trip through JSON to get Decimals."""
    return json.loads(json.dumps(value), parse_float=Decimal)


def _all_items() -> list[dict]:
    table = get_table()
    resp = table.scan()
    items = resp.get("Items", [])
    while "LastEvaluatedKey" in resp:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp.get("Items", []))
    return [_plain(i) for i in items]


def list_expenses(start_date: Optional[date], end_date: Optional[date], store: Optional[str]) -> list[dict]:
    items = _all_items()
    if start_date:
        items = [i for i in items if i["date"] >= start_date.isoformat()]
    if end_date:
        items = [i for i in items if i["date"] <= end_date.isoformat()]
    if store:
        needle = store.lower()
        items = [i for i in items if needle in i["store"].lower()]
    return sorted(items, key=lambda i: (i["date"], i["created_at"]), reverse=True)


def get_expense(expense_id: str) -> dict | None:
    item = get_table().get_item(Key={"id": expense_id}).get("Item")
    return _plain(item) if item else None


def _put(item: dict) -> dict:
    get_table().put_item(Item=_to_dynamo(item))
    return item


def create_expense(payload: ExpenseCreate) -> dict:
    item = {
        "id": str(uuid.uuid4()),
        "date": payload.date.isoformat(),
        "store": payload.store,
        "items": payload.items,
        "total": payload.total,
        "notes": payload.notes,
        "receipt_image_path": payload.receipt_image_path,
        "created_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    }
    return _put(item)


def update_expense(expense: dict, payload: ExpenseUpdate) -> dict:
    changes = payload.model_dump(exclude_none=True)
    if "date" in changes:
        changes["date"] = changes["date"].isoformat()
    return _put({**expense, **changes})


def delete_expense(expense: dict) -> None:
    get_table().delete_item(Key={"id": expense["id"]})


def monthly_summary() -> list[MonthlySummary]:
    totals: dict[tuple[int, int], float] = defaultdict(float)
    counts: dict[tuple[int, int], int] = defaultdict(int)
    for item in _all_items():
        d = date.fromisoformat(item["date"])
        totals[(d.year, d.month)] += float(item["total"])
        counts[(d.year, d.month)] += 1
    return [
        MonthlySummary(year=y, month=m, total=totals[(y, m)], count=counts[(y, m)])
        for (y, m) in sorted(totals)
    ]
