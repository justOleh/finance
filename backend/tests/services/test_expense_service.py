from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from botocore.exceptions import ClientError

from app.db import dynamodb
from app.schemas import ExpenseCreate, ExpenseUpdate
from app.services import expense_service as svc


def make(**overrides) -> ExpenseCreate:
    data = {
        "date": date(2024, 1, 15),
        "store": "Super Mart",
        "items": [{"name": "Milk", "price": 2.99, "qty": 2}],
        "total": 6.48,
        "notes": "groceries",
        "receipt_image_path": "./data/receipts/a.jpg",
    }
    return ExpenseCreate(**{**data, **overrides})


# --- number conversion ------------------------------------------------------


def test_to_dynamo_converts_floats_to_decimal_recursively():
    converted = svc._to_dynamo({"total": 6.48, "items": [{"price": 2.99, "qty": 2}]})
    assert converted["total"] == Decimal("6.48")
    assert converted["items"][0]["price"] == Decimal("2.99")
    assert isinstance(converted["items"][0]["qty"], int)


def test_from_dynamo_returns_int_for_whole_numbers_and_float_otherwise():
    assert svc._from_dynamo(Decimal("5")) == 5
    assert isinstance(svc._from_dynamo(Decimal("5")), int)
    assert svc._from_dynamo({"a": [Decimal("1.5")]}) == {"a": [1.5]}


# --- create / get -----------------------------------------------------------


def test_create_then_get_round_trips_all_fields(table):
    created = svc.create_expense(table, make())
    fetched = svc.get_expense(table, created.id)

    assert fetched == created
    assert fetched.store == "Super Mart"
    assert fetched.total == 6.48
    assert fetched.items == [{"name": "Milk", "price": 2.99, "qty": 2}]
    assert fetched.date == date(2024, 1, 15)


def test_create_writes_expected_keys(table):
    created = svc.create_expense(table, make())
    raw = table.get_item(Key={"pk": f"EXPENSE#{created.id}", "sk": "META"})["Item"]

    assert raw["gsi1pk"] == "EXPENSES"
    assert raw["gsi1sk"] == f"2024-01-15#{created.id}"
    assert raw["store_lower"] == "super mart"


def test_create_generates_unique_ids(table):
    ids = {svc.create_expense(table, make()).id for _ in range(5)}
    assert len(ids) == 5


def test_get_missing_returns_none(table):
    assert svc.get_expense(table, "nope") is None


# --- list -------------------------------------------------------------------


def test_list_orders_newest_first(table):
    for day in (date(2024, 1, 1), date(2024, 3, 1), date(2024, 2, 1)):
        svc.create_expense(table, make(date=day))

    dates = [e.date for e in svc.list_expenses(table, None, None, None)]
    assert dates == [date(2024, 3, 1), date(2024, 2, 1), date(2024, 1, 1)]


def test_list_date_range_is_inclusive_on_both_ends(table):
    for day in (date(2024, 1, 1), date(2024, 1, 15), date(2024, 1, 31), date(2024, 2, 1)):
        svc.create_expense(table, make(date=day))

    result = svc.list_expenses(table, date(2024, 1, 1), date(2024, 1, 31), None)
    assert [e.date.day for e in result] == [31, 15, 1]


def test_list_open_ended_ranges(table):
    for day in (date(2024, 1, 1), date(2024, 6, 1)):
        svc.create_expense(table, make(date=day))

    assert len(svc.list_expenses(table, date(2024, 3, 1), None, None)) == 1
    assert len(svc.list_expenses(table, None, date(2024, 3, 1), None)) == 1


def test_list_store_filter_is_case_insensitive_substring(table):
    svc.create_expense(table, make(store="Super Mart"))
    svc.create_expense(table, make(store="Corner Shop"))

    assert [e.store for e in svc.list_expenses(table, None, None, "SUPER")] == ["Super Mart"]
    assert [e.store for e in svc.list_expenses(table, None, None, "mart")] == ["Super Mart"]
    assert svc.list_expenses(table, None, None, "zzz") == []


def test_list_follows_pagination(table, monkeypatch):
    for day in range(1, 6):
        svc.create_expense(table, make(date=date(2024, 1, day)))

    real_query = table.query
    calls = []

    def one_item_per_page(**kwargs):
        calls.append(kwargs.get("ExclusiveStartKey"))
        return real_query(Limit=1, **kwargs)

    monkeypatch.setattr(table, "query", one_item_per_page)

    assert len(svc.list_expenses(table, None, None, None)) == 5
    assert len(calls) > 1  # needed several round trips, so LastEvaluatedKey was followed


# --- update -----------------------------------------------------------------


def test_update_changes_only_given_fields(table):
    created = svc.create_expense(table, make())

    updated = svc.update_expense(table, created.id, ExpenseUpdate(store="New Store"))

    assert updated.store == "New Store"
    assert updated.total == created.total
    assert updated.items == created.items
    assert updated.notes == created.notes
    assert updated.created_at == created.created_at
    assert svc.get_expense(table, created.id) == updated


def test_update_store_refreshes_search_attribute(table):
    created = svc.create_expense(table, make(store="Old"))
    svc.update_expense(table, created.id, ExpenseUpdate(store="Brand New"))

    assert len(svc.list_expenses(table, None, None, "brand")) == 1
    assert svc.list_expenses(table, None, None, "old") == []


def test_update_date_rewrites_gsi_sort_key(table):
    created = svc.create_expense(table, make(date=date(2024, 1, 15)))
    svc.update_expense(table, created.id, ExpenseUpdate(date=date(2024, 5, 5)))

    raw = table.get_item(Key={"pk": f"EXPENSE#{created.id}", "sk": "META"})["Item"]
    assert raw["gsi1sk"] == f"2024-05-05#{created.id}"
    # still one item, not a stale copy under the old date
    assert len(svc.list_expenses(table, None, None, None)) == 1


def test_update_missing_returns_none(table):
    assert svc.update_expense(table, "nope", ExpenseUpdate(store="x")) is None
    assert svc.list_expenses(table, None, None, None) == []


def test_update_returns_none_if_item_deleted_before_write(table, monkeypatch):
    created = svc.create_expense(table, make())
    real_get = table.get_item

    def get_then_delete(**kwargs):
        result = real_get(**kwargs)
        table.delete_item(Key=kwargs["Key"])  # concurrent delete after our read
        return result

    monkeypatch.setattr(table, "get_item", get_then_delete)

    assert svc.update_expense(table, created.id, ExpenseUpdate(store="x")) is None
    assert svc.list_expenses(table, None, None, None) == []  # not resurrected


def test_update_reraises_unexpected_client_errors(table, monkeypatch):
    created = svc.create_expense(table, make())
    error = ClientError({"Error": {"Code": "ProvisionedThroughputExceededException"}}, "PutItem")

    def boom(**kwargs):
        raise error

    monkeypatch.setattr(table, "put_item", boom)

    with pytest.raises(ClientError):
        svc.update_expense(table, created.id, ExpenseUpdate(store="x"))


# --- delete -----------------------------------------------------------------


def test_delete_existing_then_missing(table):
    created = svc.create_expense(table, make())

    assert svc.delete_expense(table, created.id) is True
    assert svc.get_expense(table, created.id) is None
    assert svc.delete_expense(table, created.id) is False


def test_delete_reraises_unexpected_client_errors(table, monkeypatch):
    error = ClientError({"Error": {"Code": "InternalServerError"}}, "DeleteItem")

    def boom(**kwargs):
        raise error

    monkeypatch.setattr(table, "delete_item", boom)

    with pytest.raises(ClientError):
        svc.delete_expense(table, "any")


# --- monthly summary --------------------------------------------------------


def test_monthly_summary_empty(table):
    assert svc.monthly_summary(table) == []


def test_monthly_summary_groups_sums_and_sorts_by_month(table):
    svc.create_expense(table, make(date=date(2024, 2, 10), total=10.10))
    svc.create_expense(table, make(date=date(2024, 1, 5), total=0.1))
    svc.create_expense(table, make(date=date(2024, 1, 20), total=0.2))
    svc.create_expense(table, make(date=date(2023, 12, 31), total=7))

    summary = [(s.year, s.month, s.total, s.count) for s in svc.monthly_summary(table)]

    # 0.1 + 0.2 would be 0.30000000000000004 without rounding
    assert summary == [(2023, 12, 7, 1), (2024, 1, 0.3, 2), (2024, 2, 10.1, 1)]


# --- get_table dependency ---------------------------------------------------


def test_get_table_requires_table_name(monkeypatch):
    dynamodb.get_table.cache_clear()
    monkeypatch.setattr(dynamodb, "settings", replace(dynamodb.settings, dynamodb_table_name=""))

    with pytest.raises(RuntimeError, match="DYNAMODB_TABLE_NAME"):
        dynamodb.get_table()


def test_get_table_builds_table_resource_for_configured_name(table, monkeypatch):
    dynamodb.get_table.cache_clear()
    monkeypatch.setattr(
        dynamodb, "settings", replace(dynamodb.settings, dynamodb_table_name=table.name)
    )

    try:
        resolved = dynamodb.get_table()
        assert resolved.name == table.name
        assert dynamodb.get_table() is resolved  # cached
    finally:
        dynamodb.get_table.cache_clear()
