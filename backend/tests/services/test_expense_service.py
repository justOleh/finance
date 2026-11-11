from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from botocore.exceptions import ClientError

from app.db import dynamodb
from app.schemas import ExpenseCreate, ExpenseUpdate
from app.services import expense_service as svc

U = "user-a"
OTHER = "user-b"


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
    created = svc.create_expense(table, U, make())
    fetched = svc.get_expense(table, U, created.id)

    assert fetched == created
    assert fetched.store == "Super Mart"
    assert fetched.total == 6.48
    assert [i.model_dump() for i in fetched.items] == [{"name": "Milk", "price": 2.99, "qty": 2}]
    assert fetched.date == date(2024, 1, 15)


def test_create_writes_expected_keys(table):
    created = svc.create_expense(table, U, make())
    raw = table.get_item(Key={"pk": f"USER#{U}", "sk": f"EXPENSE#{created.id}"})["Item"]

    assert raw["gsi1pk"] == f"USER#{U}"
    assert raw["user_id"] == U
    assert raw["gsi1sk"] == f"2024-01-15#{created.id}"
    assert raw["store_lower"] == "super mart"


def test_create_generates_unique_ids(table):
    ids = {svc.create_expense(table, U, make()).id for _ in range(5)}
    assert len(ids) == 5


def test_get_missing_returns_none(table):
    assert svc.get_expense(table, U, "nope") is None


# --- list -------------------------------------------------------------------


def test_list_orders_newest_first(table):
    for day in (date(2024, 1, 1), date(2024, 3, 1), date(2024, 2, 1)):
        svc.create_expense(table, U, make(date=day))

    dates = [e.date for e in svc.list_expenses(table, U, None, None, None)]
    assert dates == [date(2024, 3, 1), date(2024, 2, 1), date(2024, 1, 1)]


def test_list_date_range_is_inclusive_on_both_ends(table):
    for day in (date(2024, 1, 1), date(2024, 1, 15), date(2024, 1, 31), date(2024, 2, 1)):
        svc.create_expense(table, U, make(date=day))

    result = svc.list_expenses(table, U, date(2024, 1, 1), date(2024, 1, 31), None)
    assert [e.date.day for e in result] == [31, 15, 1]


def test_list_open_ended_ranges(table):
    for day in (date(2024, 1, 1), date(2024, 6, 1)):
        svc.create_expense(table, U, make(date=day))

    assert len(svc.list_expenses(table, U, date(2024, 3, 1), None, None)) == 1
    assert len(svc.list_expenses(table, U, None, date(2024, 3, 1), None)) == 1


def test_list_store_filter_is_case_insensitive_substring(table):
    svc.create_expense(table, U, make(store="Super Mart"))
    svc.create_expense(table, U, make(store="Corner Shop"))

    assert [e.store for e in svc.list_expenses(table, U, None, None, "SUPER")] == ["Super Mart"]
    assert [e.store for e in svc.list_expenses(table, U, None, None, "mart")] == ["Super Mart"]
    assert svc.list_expenses(table, U, None, None, "zzz") == []


def test_list_follows_pagination(table, monkeypatch):
    for day in range(1, 6):
        svc.create_expense(table, U, make(date=date(2024, 1, day)))

    real_query = table.query
    calls = []

    def one_item_per_page(**kwargs):
        calls.append(kwargs.get("ExclusiveStartKey"))
        return real_query(Limit=1, **kwargs)

    monkeypatch.setattr(table, "query", one_item_per_page)

    assert len(svc.list_expenses(table, U, None, None, None)) == 5
    assert len(calls) > 1  # needed several round trips, so LastEvaluatedKey was followed


# --- update -----------------------------------------------------------------


def test_update_changes_only_given_fields(table):
    created = svc.create_expense(table, U, make())

    updated = svc.update_expense(table, U, created.id, ExpenseUpdate(store="New Store"))

    assert updated.store == "New Store"
    assert updated.total == created.total
    assert updated.items == created.items
    assert updated.notes == created.notes
    assert updated.created_at == created.created_at
    assert svc.get_expense(table, U, created.id) == updated


def test_update_store_refreshes_search_attribute(table):
    created = svc.create_expense(table, U, make(store="Old"))
    svc.update_expense(table, U, created.id, ExpenseUpdate(store="Brand New"))

    assert len(svc.list_expenses(table, U, None, None, "brand")) == 1
    assert svc.list_expenses(table, U, None, None, "old") == []


def test_update_date_rewrites_gsi_sort_key(table):
    created = svc.create_expense(table, U, make(date=date(2024, 1, 15)))
    svc.update_expense(table, U, created.id, ExpenseUpdate(date=date(2024, 5, 5)))

    raw = table.get_item(Key={"pk": f"USER#{U}", "sk": f"EXPENSE#{created.id}"})["Item"]
    assert raw["gsi1sk"] == f"2024-05-05#{created.id}"
    # still one item, not a stale copy under the old date
    assert len(svc.list_expenses(table, U, None, None, None)) == 1


def test_update_missing_returns_none(table):
    assert svc.update_expense(table, U, "nope", ExpenseUpdate(store="x")) is None
    assert svc.list_expenses(table, U, None, None, None) == []


def test_update_returns_none_if_item_deleted_before_write(table, monkeypatch):
    created = svc.create_expense(table, U, make())
    real_get = table.get_item

    def get_then_delete(**kwargs):
        result = real_get(**kwargs)
        table.delete_item(Key=kwargs["Key"])  # concurrent delete after our read
        return result

    monkeypatch.setattr(table, "get_item", get_then_delete)

    assert svc.update_expense(table, U, created.id, ExpenseUpdate(store="x")) is None
    assert svc.list_expenses(table, U, None, None, None) == []  # not resurrected


def test_update_reraises_unexpected_client_errors(table, monkeypatch):
    created = svc.create_expense(table, U, make())
    error = ClientError({"Error": {"Code": "ProvisionedThroughputExceededException"}}, "PutItem")

    def boom(**kwargs):
        raise error

    monkeypatch.setattr(table, "put_item", boom)

    with pytest.raises(ClientError):
        svc.update_expense(table, U, created.id, ExpenseUpdate(store="x"))


# --- delete -----------------------------------------------------------------


def test_delete_existing_then_missing(table):
    created = svc.create_expense(table, U, make())

    assert svc.delete_expense(table, U, created.id) is True
    assert svc.get_expense(table, U, created.id) is None
    assert svc.delete_expense(table, U, created.id) is False


def test_delete_reraises_unexpected_client_errors(table, monkeypatch):
    error = ClientError({"Error": {"Code": "InternalServerError"}}, "DeleteItem")

    def boom(**kwargs):
        raise error

    monkeypatch.setattr(table, "delete_item", boom)

    with pytest.raises(ClientError):
        svc.delete_expense(table, U, "any")


# --- monthly summary --------------------------------------------------------


def test_monthly_summary_empty(table):
    assert svc.monthly_summary(table, U) == []


def test_monthly_summary_groups_sums_and_sorts_by_month(table):
    svc.create_expense(table, U, make(date=date(2024, 2, 10), total=10.10))
    svc.create_expense(table, U, make(date=date(2024, 1, 5), total=0.1))
    svc.create_expense(table, U, make(date=date(2024, 1, 20), total=0.2))
    svc.create_expense(table, U, make(date=date(2023, 12, 31), total=7))

    summary = [(s.year, s.month, s.total, s.count) for s in svc.monthly_summary(table, U)]

    # 0.1 + 0.2 would be 0.30000000000000004 without rounding
    assert summary == [(2023, 12, 7, 1), (2024, 1, 0.3, 2), (2024, 2, 10.1, 1)]


# --- tenant isolation -------------------------------------------------------


def test_users_cannot_see_or_touch_each_others_expenses(table):
    mine = svc.create_expense(table, U, make(store="Mine"))
    theirs = svc.create_expense(table, OTHER, make(store="Theirs"))

    assert [e.store for e in svc.list_expenses(table, U, None, None, None)] == ["Mine"]
    assert [e.store for e in svc.list_expenses(table, OTHER, None, None, None)] == ["Theirs"]
    assert [s.count for s in svc.monthly_summary(table, U)] == [1]

    # another user's id behaves exactly like a missing one
    assert svc.get_expense(table, U, theirs.id) is None
    assert svc.update_expense(table, U, theirs.id, ExpenseUpdate(store="Hacked")) is None
    assert svc.delete_expense(table, U, theirs.id) is False

    assert svc.get_expense(table, OTHER, theirs.id).store == "Theirs"
    assert svc.get_expense(table, U, mine.id).store == "Mine"


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


# --- typed items (ADR-014) --------------------------------------------------


def test_items_written_before_typing_are_still_readable(table):
    created = svc.create_expense(table, U, make())
    # An item as the old parser stored it: `item_price` instead of `price`, and no name.
    table.update_item(
        Key={"pk": f"USER#{U}", "sk": f"EXPENSE#{created.id}"},
        UpdateExpression="SET #i = :i",
        ExpressionAttributeNames={"#i": "items"},
        ExpressionAttributeValues={":i": [{"item_price": Decimal("4.5"), "unit": "kg"}]},
    )

    item = svc.get_expense(table, U, created.id).items[0]

    assert (item.name, item.price) == ("", 4.5)
    assert item.model_dump()["unit"] == "kg"


def test_new_items_need_a_name_and_a_price():
    with pytest.raises(ValueError):
        make(items=[{"price": 1.0}])
    with pytest.raises(ValueError):
        make(items=[{"name": "Milk"}])


# --- idempotent create (ADR-014) --------------------------------------------


def test_create_once_returns_the_first_expense_on_a_repeated_key(table):
    first, created = svc.create_expense_once(table, U, make(store="First"), "key-12345")
    again, created_again = svc.create_expense_once(table, U, make(store="Second"), "key-12345")

    assert (created, created_again) == (True, False)
    assert again == first
    assert len(svc.list_expenses(table, U, None, None, None)) == 1


def test_create_once_keys_are_per_user(table):
    mine, _ = svc.create_expense_once(table, U, make(), "key-12345")
    theirs, created = svc.create_expense_once(table, OTHER, make(), "key-12345")

    assert created is True
    assert mine.id != theirs.id


# --- spending summary (ADR-014) ---------------------------------------------


def _seed_summary(table):
    svc.create_expense(table, U, make(store="Silpo", date=date(2024, 1, 5), total=0.1))
    svc.create_expense(table, U, make(store="SILPO", date=date(2024, 1, 20), total=0.2))
    svc.create_expense(table, U, make(store="ATB", date=date(2024, 2, 10), total=10.10))
    svc.create_expense(table, OTHER, make(store="Silpo", date=date(2024, 1, 7), total=99))


def test_summary_totals_a_date_range_without_float_drift(table):
    _seed_summary(table)

    summary = svc.spending_summary(table, U, date(2024, 1, 1), date(2024, 1, 31))

    assert (summary.total, summary.count, summary.groups) == (0.3, 2, [])


def test_summary_groups_by_store_case_insensitively_largest_first(table):
    _seed_summary(table)

    summary = svc.spending_summary(table, U, None, None, group_by="store")

    assert [(g.key, g.total, g.count) for g in summary.groups] == [
        ("ATB", 10.1, 1),
        ("SILPO", 0.3, 2),  # label = spelling of the newest expense
    ]
    assert summary.total == 10.4


def test_summary_groups_by_month_and_filters_by_store(table):
    _seed_summary(table)

    by_month = svc.spending_summary(table, U, None, None, group_by="month")
    silpo = svc.spending_summary(table, U, None, None, store="silpo")

    assert [(g.key, g.total) for g in by_month.groups] == [("2024-02", 10.1), ("2024-01", 0.3)]
    assert (silpo.total, silpo.count) == (0.3, 2)


def test_summary_of_nothing_is_zero(table):
    summary = svc.spending_summary(table, U, None, None, group_by="store")

    assert (summary.total, summary.count, summary.groups) == (0.0, 0, [])
