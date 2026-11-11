"""The only door to the data: the existing REST API, called with the caller's own token.

The backend decides whose data a request touches from that token (ADR-009). Nothing here, and
nothing the model says, can name another user.
"""

from typing import Any

import httpx


class ApiError(Exception):
    """The API answered with an error; `message` is safe to show to the model."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class FinanceApi:
    def __init__(
        self,
        base_url: str,
        authorization: str | None,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ):
        headers = {"Authorization": authorization} if authorization else {}
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout, transport=transport
        )

    def __repr__(self) -> str:  # never let the token end up in a log line or a traceback
        return f"FinanceApi({self._client.base_url})"

    def close(self) -> None:
        self._client.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        try:
            response = self._client.get(path, params=clean)
        except httpx.HTTPError as exc:
            raise ApiError(503, "The expense service is not reachable right now.") from exc
        if response.status_code == 404:
            raise ApiError(404, "Not found.")
        if response.status_code in (401, 403):
            raise ApiError(
                response.status_code, "The user is not signed in or the session expired."
            )
        if response.status_code == 422:
            raise ApiError(422, "The request had invalid arguments.")
        if response.status_code >= 400:
            raise ApiError(response.status_code, "The expense service returned an error.")
        return response.json()

    def list_expenses(self, start_date: str | None, end_date: str | None, store: str | None):
        return self._get(
            "/expenses/", {"start_date": start_date, "end_date": end_date, "store": store}
        )

    def get_expense(self, expense_id: str):
        return self._get(f"/expenses/{expense_id}")

    def spending_summary(
        self, start_date: str | None, end_date: str | None, group_by: str, store: str | None
    ):
        return self._get(
            "/expenses/summary",
            {"start_date": start_date, "end_date": end_date, "group_by": group_by, "store": store},
        )

    def get_receipt(self, receipt_id: str):
        return self._get(f"/receipts/{receipt_id}")
