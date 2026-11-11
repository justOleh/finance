import pytest

from finance_agent.tools import UNTRUSTED_NOTE, build_tools
from tests.conftest import EXPENSES, dumps


@pytest.fixture
def drafts():
    return []


@pytest.fixture
def tools(api, drafts):
    return {t.tool_name: t for t in build_tools(api, drafts, max_rows=1)}


def test_the_agent_has_exactly_the_five_tools_of_adr_014(tools):
    assert set(tools) == {
        "list_expenses",
        "spending_summary",
        "get_expense",
        "get_receipt_draft",
        "propose_expense",
    }


def test_no_tool_accepts_a_user_id(tools):
    for tool in tools.values():
        properties = tool.tool_spec["inputSchema"]["json"].get("properties", {})
        assert not any("user" in name.lower() for name in properties), tool.tool_name


def test_no_tool_can_write(tools, backend):
    """Run every tool once: the API must only ever see GET requests."""
    tools["list_expenses"]()
    tools["spending_summary"](group_by="store")
    tools["get_expense"](expense_id="a" * 32)
    tools["get_receipt_draft"](receipt_id="c" * 32)
    tools["propose_expense"](date="2026-11-11", store="Silpo", total=10)

    assert {r.method for r in backend.requests} == {"GET"}
    assert len(backend.requests) == 4  # propose_expense calls nothing


# --- list_expenses ------------------------------------------------------------------------


def test_list_expenses_trims_rows_and_marks_them_as_untrusted(tools):
    result = tools["list_expenses"](start_date="2026-10-01", end_date="2026-10-31")

    assert result["note"] == UNTRUSTED_NOTE
    assert result["data"] == [
        {"id": "a" * 32, "date": "2026-10-20", "store": "Silpo", "total": 250.5, "item_count": 2}
    ]
    assert "receipt_image_path" not in dumps(result)


def test_list_expenses_says_when_it_was_truncated(tools):
    result = tools["list_expenses"]()

    assert (result["returned"], result["matching"]) == (1, len(EXPENSES))
    assert "spending_summary" in result["truncated"]


def test_list_expenses_includes_items_only_on_request(tools):
    result = tools["list_expenses"](include_items=True)

    assert result["data"][0]["items"] == [
        {"name": "Milk", "price": 50.5},
        {"name": "Cheese", "price": 200},
    ]


def test_bad_dates_come_back_as_an_error_without_calling_the_api(tools, backend):
    result = tools["list_expenses"](start_date="last month")

    assert "YYYY-MM-DD" in result["error"]
    assert backend.requests == []


def test_api_errors_become_tool_errors(tools, backend):
    backend.status = 500

    assert "error" in tools["list_expenses"]()
    assert "error" in tools["spending_summary"]()


# --- spending_summary ---------------------------------------------------------------------


def test_spending_summary_passes_the_grouping_through(tools, backend):
    result = tools["spending_summary"](start_date="2026-10-01", group_by="month", store="atb")

    assert dict(backend.last.url.params) == {
        "start_date": "2026-10-01",
        "group_by": "month",
        "store": "atb",
    }
    assert (result["data"]["total"], result["currency"]) == (349.5, "UAH")


def test_spending_summary_rejects_an_unknown_grouping(tools, backend):
    assert "error" in tools["spending_summary"](group_by="category")
    assert backend.requests == []


# --- get_expense / get_receipt_draft ------------------------------------------------------


def test_get_expense_returns_items(tools):
    assert len(tools["get_expense"](expense_id="a" * 32)["data"]["items"]) == 2


@pytest.mark.parametrize("bad_id", ["", "../receipts/1", "a b", "A" * 32, "1; drop"])
def test_ids_that_are_not_ids_never_reach_the_api(tools, backend, bad_id):
    assert "error" in tools["get_expense"](expense_id=bad_id)
    assert "error" in tools["get_receipt_draft"](receipt_id=bad_id)
    assert backend.requests == []


def test_unknown_expense_is_reported_as_not_found(tools):
    assert tools["get_expense"](expense_id="d" * 32) == {"error": "No expense with this id."}


def test_receipt_still_processing_has_no_draft(tools):
    assert tools["get_receipt_draft"](receipt_id="c" * 32)["data"] == {"status": "UPLOADING"}


def test_parsed_receipt_returns_a_trimmed_draft(tools, backend):
    backend.receipt = {
        "id": "c" * 32,
        "status": "PARSED",
        "error": None,
        "draft": {
            "date": "2026-11-10",
            "store": "Silpo",
            "total": 42.5,
            "items": [{"name": "Milk", "price": 42.5}],
            "notes": "raw text",
            "receipt_image_path": "receipts/u/c.png",
        },
    }

    data = tools["get_receipt_draft"](receipt_id="c" * 32)["data"]

    assert data["status"] == "PARSED"
    assert set(data["draft"]) == {"date", "store", "total", "items"}


def test_failed_receipt_carries_the_error(tools, backend):
    backend.receipt = {"id": "c" * 32, "status": "FAILED", "error": "Unreadable", "draft": None}

    assert tools["get_receipt_draft"](receipt_id="c" * 32)["data"] == {
        "status": "FAILED",
        "error": "Unreadable",
    }


# --- propose_expense ----------------------------------------------------------------------


def test_propose_expense_hands_a_draft_to_the_ui_and_says_it_is_not_saved(tools, drafts):
    result = tools["propose_expense"](
        date="2026-11-11",
        store="  Silpo ",
        total=42.499,
        items=[{"name": "Milk", "price": 42.499, "sku": "x"}],
        notes=" lunch ",
    )

    assert result["saved"] is False
    assert drafts == [
        {
            "date": "2026-11-11",
            "store": "Silpo",
            "total": 42.5,
            "items": [{"name": "Milk", "price": 42.5}],
            "notes": "lunch",
        }
    ]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"date": "yesterday", "store": "Silpo", "total": 1},
        {"date": "2026-11-11", "store": " ", "total": 1},
        {"date": "2026-11-11", "store": "Silpo", "total": -1},
        {"date": "2026-11-11", "store": "Silpo", "total": 1, "items": [{"name": "Milk"}]},
        {"date": "2026-11-11", "store": "Silpo", "total": 1, "items": ["Milk"]},
    ],
)
def test_propose_expense_rejects_invalid_drafts(tools, drafts, kwargs):
    assert "error" in tools["propose_expense"](**kwargs)
    assert drafts == []
