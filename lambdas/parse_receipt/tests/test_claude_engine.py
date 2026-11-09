import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from parse_receipt.claude_engine import (
    DEFAULT_EFFORT,
    DEFAULT_MODEL,
    RECEIPT_SCHEMA,
    ClaudeEngine,
    ReceiptParseError,
)

IMAGE = b"\x89PNG fake image bytes"

GOOD_REPLY = {
    "store": " Silpo ",
    "date": "2026-03-14",
    "items": [
        {"name": "Milk 1L", "price": 42.5},
        {"name": " Bread ", "price": 25},
        {"name": "Discount", "price": -5.5},
    ],
    "total": 62.0,
    "notes": "Currency: UAH",
}


def _response(reply=None, *, text=None, stop_reason="end_turn", category=None):
    if text is None and reply is not None:
        text = json.dumps(reply)
    content = [SimpleNamespace(type="text", text=text)] if text is not None else []
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=content,
        stop_details=SimpleNamespace(category=category),
    )


class FakeClient:
    """Stands in for anthropic.Anthropic: records the request, returns a canned response."""

    def __init__(self, response):
        self.response = response
        self.calls: list[dict] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def _engine(response, **kwargs) -> tuple[ClaudeEngine, FakeClient]:
    client = FakeClient(response)
    return ClaudeEngine(client=client, **kwargs), client


def test_extract_maps_the_reply_to_a_parsed_receipt():
    engine, _ = _engine(_response(GOOD_REPLY))

    parsed = engine.extract(IMAGE, "image/png")

    assert parsed.store == "Silpo"
    assert parsed.date == "2026-03-14"
    assert parsed.items == [
        {"name": "Milk 1L", "price": 42.5},
        {"name": "Bread", "price": 25.0},
        {"name": "Discount", "price": -5.5},
    ]
    assert parsed.total == 62.0
    assert parsed.notes == "Currency: UAH"


def test_request_has_the_image_schema_and_effort_and_no_removed_parameters():
    engine, client = _engine(_response(GOOD_REPLY))

    engine.extract(IMAGE, "image/png")

    (call,) = client.calls
    assert call["model"] == DEFAULT_MODEL == "claude-sonnet-5-5"
    assert call["output_config"] == {
        "effort": DEFAULT_EFFORT,
        "format": {"type": "json_schema", "schema": RECEIPT_SCHEMA},
    }
    image_block, text_block = call["messages"][0]["content"]
    assert image_block["type"] == "image"
    assert image_block["source"]["type"] == "base64"
    assert image_block["source"]["media_type"] == "image/png"
    assert text_block["type"] == "text"
    # Rejected with a 400 on Claude Sonnet 5.5: must never be sent.
    for forbidden in ("temperature", "top_p", "top_k", "thinking", "tool_choice"):
        assert forbidden not in call
    assert call["messages"][-1]["role"] == "user"  # no assistant prefill


def test_model_and_effort_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL", "claude-haiku-5-5")
    monkeypatch.setenv("CLAUDE_EFFORT", "low")
    engine, client = _engine(_response(GOOD_REPLY))

    engine.extract(IMAGE, "image/png")

    assert client.calls[0]["model"] == "claude-haiku-5-5"
    assert client.calls[0]["output_config"]["effort"] == "low"
    assert engine.model_version == "claude-haiku-5-5"


def test_jpg_alias_and_charset_suffix_are_normalised():
    engine, client = _engine(_response(GOOD_REPLY))

    engine.extract(IMAGE, "image/jpg")
    engine.extract(IMAGE, "IMAGE/JPEG; charset=binary")

    media_types = [c["messages"][0]["content"][0]["source"]["media_type"] for c in client.calls]
    assert media_types == ["image/jpeg", "image/jpeg"]


@pytest.mark.parametrize("content_type", ["image/heic", "application/pdf", "", None])
def test_unsupported_media_type_fails_without_calling_the_model(content_type):
    engine, client = _engine(_response(GOOD_REPLY))

    with pytest.raises(ReceiptParseError, match="Unsupported image type"):
        engine.extract(IMAGE, content_type)

    assert client.calls == []


@pytest.mark.parametrize("date", ["", "not a date", "14/03/2026", "2026-13-40"])
def test_missing_or_invalid_date_falls_back_to_today_and_says_so(date):
    engine, _ = _engine(_response({**GOOD_REPLY, "date": date, "notes": ""}))

    parsed = engine.extract(IMAGE, "image/png")

    assert parsed.date == datetime.now(UTC).date().isoformat()
    assert "Date not found" in parsed.notes


def test_refusal_raises_with_the_category():
    engine, _ = _engine(_response(text=None, stop_reason="refusal", category="general_harms"))

    with pytest.raises(ReceiptParseError, match="declined.*general_harms"):
        engine.extract(IMAGE, "image/png")


def test_truncated_reply_raises():
    engine, _ = _engine(_response(text='{"store": "Si', stop_reason="max_tokens"))

    with pytest.raises(ReceiptParseError, match="max_tokens"):
        engine.extract(IMAGE, "image/png")


def test_reply_without_text_raises():
    engine, _ = _engine(_response(text=None))

    with pytest.raises(ReceiptParseError, match="no text"):
        engine.extract(IMAGE, "image/png")


def test_invalid_json_raises():
    engine, _ = _engine(_response(text="Sorry, here is your receipt: ..."))

    with pytest.raises(ReceiptParseError, match="not valid JSON"):
        engine.extract(IMAGE, "image/png")


def test_building_the_engine_does_not_need_an_api_key():
    # The client is created on first use; import and construction never touch the key.
    assert ClaudeEngine().model_version == DEFAULT_MODEL


def test_schema_is_strict_and_lists_every_field():
    assert RECEIPT_SCHEMA["additionalProperties"] is False
    assert set(RECEIPT_SCHEMA["required"]) == set(RECEIPT_SCHEMA["properties"])
    item = RECEIPT_SCHEMA["properties"]["items"]["items"]
    assert item["additionalProperties"] is False
    assert set(item["required"]) == {"name", "price"}
