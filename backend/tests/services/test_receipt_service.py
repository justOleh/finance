from datetime import date

from app.services import receipt_service


def test_normalize_parser_payload_uses_gpt_json_and_maps_where():
    payload = {
        "gpt_json": {
            "where": [{"name": "beef", "item_price": 150.0}],
            "total": 150.0,
        }
    }

    normalized = receipt_service.normalize_parser_payload(payload)

    assert "where" in normalized
    assert normalized["items"] == normalized["where"]
    assert normalized["total"] == 150.0


def test_prepare_receipt_image_defaults_to_jpg_suffix():
    filename, content_type, image_bytes = receipt_service.prepare_receipt_image(
        filename=None,
        content_type=None,
        image_bytes=b"raw-bytes",
    )

    assert filename.endswith(".jpg")
    assert content_type == "application/octet-stream"
    assert image_bytes == b"raw-bytes"


def test_parse_expense_date_valid_and_invalid():
    assert receipt_service.parse_expense_date("2026-03-01") == date(2026, 3, 1)
    assert isinstance(receipt_service.parse_expense_date("bad-date"), date)
    assert isinstance(receipt_service.parse_expense_date(None), date)


def test_parse_receipt_with_service(monkeypatch):
    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"gpt_json": {"store": "Test", "where": []}}

    monkeypatch.setattr(receipt_service.httpx, "post", lambda *args, **kwargs: DummyResponse())

    parsed = receipt_service.parse_receipt_with_service("f.jpg", b"x", "image/jpeg")
    assert parsed["store"] == "Test"
    assert parsed["items"] == []
