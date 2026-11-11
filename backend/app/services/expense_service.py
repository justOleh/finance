import hashlib
import json
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from app.schemas import (
    ExpenseCreate,
    ExpenseResponse,
    ExpenseUpdate,
    MonthlySummary,
    SpendingSummary,
    SummaryGroup,
)

# Single-table design (see terraform/main.tf and ADR-009). Every key contains the owner's
# Cognito `sub`, so a user can only ever address their own items:
#   item:  pk = USER#<sub>, sk = EXPENSE#<id>          -> get / update / delete by id
#   gsi1:  gsi1pk = USER#<sub>, gsi1sk = <date>#<id>   -> list by date range (newest first)
_GSI = "gsi1"


def _user_pk(user_id: str) -> str:
    return f"USER#{user_id}"


def _key(user_id: str, expense_id: str) -> dict[str, str]:
    return {"pk": _user_pk(user_id), "sk": f"EXPENSE#{expense_id}"}


def _to_dynamo(value: Any) -> Any:
    """boto3 rejects float: round-trip through JSON to get Decimal numbers."""
    return json.loads(json.dumps(value), parse_float=Decimal)


def _from_dynamo(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [_from_dynamo(v) for v in value]
    if isinstance(value, dict):
        return {k: _from_dynamo(v) for k, v in value.items()}
    return value


def _to_response(item: dict) -> ExpenseResponse:
    return ExpenseResponse(
        id=item["id"],
        date=date.fromisoformat(item["date"]),
        store=item["store"],
        items=_from_dynamo(item["items"]),
        total=_from_dynamo(item["total"]),
        receipt_image_path=item.get("receipt_image_path"),
        notes=item.get("notes"),
        created_at=datetime.fromisoformat(item["created_at"]),
    )


def _build_item(
    user_id: str,
    expense_id: str,
    day: date,
    store: str,
    items: list,
    total: float,
    notes: str | None,
    receipt_image_path: str | None,
    created_at: str,
) -> dict:
    return {
        **_key(user_id, expense_id),
        "gsi1pk": _user_pk(user_id),
        "gsi1sk": f"{day.isoformat()}#{expense_id}",
        "id": expense_id,
        "user_id": user_id,
        "date": day.isoformat(),
        "store": store,
        "store_lower": store.lower(),
        "items": _to_dynamo(items),
        "total": _to_dynamo(total),
        "notes": notes,
        "receipt_image_path": receipt_image_path,
        "created_at": created_at,
    }


def _query_items(
    table,
    user_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
    store: str | None = None,
) -> list[dict]:
    low = start_date.isoformat() if start_date else "0000-00-00"
    # "~" sorts after any hex id char, so the end date is inclusive.
    high = f"{end_date.isoformat()}#~" if end_date else "9999-99-99#~"
    kwargs: dict[str, Any] = {
        "IndexName": _GSI,
        "KeyConditionExpression": Key("gsi1pk").eq(_user_pk(user_id))
        & Key("gsi1sk").between(low, high),
        "ScanIndexForward": False,
    }
    if store:
        kwargs["FilterExpression"] = Attr("store_lower").contains(store.lower())

    items: list[dict] = []
    while True:
        resp = table.query(**kwargs)
        items.extend(resp["Items"])
        if "LastEvaluatedKey" not in resp:
            return items
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def list_expenses(
    table, user_id: str, start_date: date | None, end_date: date | None, store: str | None
) -> list[ExpenseResponse]:
    return [_to_response(i) for i in _query_items(table, user_id, start_date, end_date, store)]


def get_expense(table, user_id: str, expense_id: str) -> ExpenseResponse | None:
    item = table.get_item(Key=_key(user_id, expense_id)).get("Item")
    return _to_response(item) if item else None


def _idempotent_id(user_id: str, idempotency_key: str) -> str:
    """Same user + same key always gives the same expense id (32 hex chars, like uuid4().hex)."""
    return hashlib.sha256(f"{user_id}:{idempotency_key}".encode()).hexdigest()[:32]


def _new_item(user_id: str, expense_id: str, payload: ExpenseCreate) -> dict:
    return _build_item(
        user_id=user_id,
        expense_id=expense_id,
        day=payload.date,
        store=payload.store,
        # Typed items (ADR-014) go back to plain dicts for DynamoDB.
        items=[i.model_dump() for i in payload.items],
        total=payload.total,
        notes=payload.notes,
        receipt_image_path=payload.receipt_image_path,
        created_at=datetime.now(UTC).isoformat(),
    )


def create_expense(table, user_id: str, payload: ExpenseCreate) -> ExpenseResponse:
    item = _new_item(user_id, uuid.uuid4().hex, payload)
    table.put_item(Item=item)
    return _to_response(item)


def create_expense_once(
    table, user_id: str, payload: ExpenseCreate, idempotency_key: str
) -> tuple[ExpenseResponse, bool]:
    """Create an expense at most once per (user, key). Returns (expense, created).

    The id is derived from the key and the write is conditional, so a retry (double click,
    network retry, an agent repeating itself) returns the first expense instead of creating a
    second one: created is then False. See ADR-014.
    """
    expense_id = _idempotent_id(user_id, idempotency_key)
    item = _new_item(user_id, expense_id, payload)
    try:
        table.put_item(Item=item, ConditionExpression=Attr("pk").not_exists())
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        existing = table.get_item(Key=_key(user_id, expense_id), ConsistentRead=True)["Item"]
        return _to_response(existing), False
    return _to_response(item), True


def update_expense(
    table, user_id: str, expense_id: str, payload: ExpenseUpdate
) -> ExpenseResponse | None:
    # Read-modify-write: the date is part of the GSI sort key, so it must be rebuilt.
    current = table.get_item(Key=_key(user_id, expense_id)).get("Item")
    if not current:
        return None
    current = _from_dynamo(current)

    # model_dump turns the typed items back into plain dicts for DynamoDB.
    changes = payload.model_dump(exclude_none=True)
    item = _build_item(
        user_id=user_id,
        expense_id=expense_id,
        day=changes.get("date", date.fromisoformat(current["date"])),
        store=changes.get("store", current["store"]),
        items=changes.get("items", current["items"]),
        total=changes.get("total", current["total"]),
        notes=changes.get("notes", current.get("notes")),
        receipt_image_path=changes.get("receipt_image_path", current.get("receipt_image_path")),
        created_at=current["created_at"],
    )
    try:
        table.put_item(Item=item, ConditionExpression=Attr("pk").exists())
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return None  # deleted between read and write
        raise
    return _to_response(item)


def delete_expense(table, user_id: str, expense_id: str) -> bool:
    try:
        table.delete_item(Key=_key(user_id, expense_id), ConditionExpression=Attr("pk").exists())
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
    return True


def monthly_summary(table, user_id: str) -> list[MonthlySummary]:
    # Personal-scale data: aggregate in Python instead of maintaining counters.
    totals: dict[tuple[int, int], list] = {}
    for item in _query_items(table, user_id):
        year, month = int(item["date"][:4]), int(item["date"][5:7])
        bucket = totals.setdefault((year, month), [0.0, 0])
        bucket[0] += _from_dynamo(item["total"])
        bucket[1] += 1
    return [
        MonthlySummary(year=y, month=m, total=round(t, 2), count=c)
        for (y, m), (t, c) in sorted(totals.items())
    ]


def spending_summary(
    table,
    user_id: str,
    start_date: date | None,
    end_date: date | None,
    group_by: str = "none",
    store: str | None = None,
) -> SpendingSummary:
    """Total and count for a date range, optionally grouped by store or by month.

    Sums use Decimal (the type DynamoDB returns), so there is no float drift.
    """
    total = Decimal("0")
    count = 0
    groups: dict[str, list] = defaultdict(lambda: [Decimal("0"), 0])
    labels: dict[str, str] = {}
    for item in _query_items(table, user_id, start_date, end_date, store):
        amount = Decimal(str(item["total"]))
        total += amount
        count += 1
        if group_by == "store":
            # Group case-insensitively, show the first spelling seen (the newest expense).
            key = item.get("store_lower") or item["store"].lower()
            labels.setdefault(key, item["store"])
        elif group_by == "month":
            key = item["date"][:7]
        else:
            continue
        groups[key][0] += amount
        groups[key][1] += 1

    return SpendingSummary(
        start_date=start_date,
        end_date=end_date,
        group_by=group_by,
        total=float(round(total, 2)),
        count=count,
        groups=[
            SummaryGroup(key=labels.get(key, key), total=float(round(amount, 2)), count=n)
            for key, (amount, n) in sorted(groups.items(), key=lambda kv: (-kv[1][0], kv[0]))
        ],
    )
