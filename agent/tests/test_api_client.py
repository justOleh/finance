import httpx
import pytest

from finance_agent.api_client import ApiError, FinanceApi


def test_every_call_carries_the_callers_token(api, backend):
    api.list_expenses("2026-10-01", "2026-10-31", "silpo")

    assert backend.last.headers["Authorization"] == "Bearer user-token"
    assert dict(backend.last.url.params) == {
        "start_date": "2026-10-01",
        "end_date": "2026-10-31",
        "store": "silpo",
    }


def test_missing_arguments_are_not_sent(api, backend):
    api.list_expenses(None, None, None)

    assert backend.last.url.params == httpx.QueryParams()


def test_no_token_means_no_authorization_header(backend):
    api = FinanceApi("http://localhost:8000", None, transport=httpx.MockTransport(backend.handler))

    api.spending_summary(None, None, "none", None)

    assert "Authorization" not in backend.last.headers


@pytest.mark.parametrize(
    ("status", "expected"),
    [(401, "not signed in"), (404, "Not found"), (422, "invalid arguments"), (500, "an error")],
)
def test_errors_are_mapped_to_safe_messages(api, backend, status, expected):
    backend.status = status

    with pytest.raises(ApiError) as caught:
        api.get_expense("a" * 32)

    assert caught.value.status == status
    assert expected in caught.value.message
    assert "secret internal detail" not in caught.value.message


def test_network_failure_is_an_api_error():
    def boom(request):
        raise httpx.ConnectError("no route")

    api = FinanceApi("https://api.test", "Bearer t", transport=httpx.MockTransport(boom))

    with pytest.raises(ApiError) as caught:
        api.list_expenses(None, None, None)

    assert caught.value.status == 503


def test_repr_never_shows_the_token(api):
    assert "user-token" not in repr(api)
