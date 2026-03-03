def test_upload_rejects_invalid_content_type(client):
    response = client.post(
        "/receipts/upload",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


def test_upload_receipt_success_with_parser(monkeypatch, client):
    from app.api.v1 import receipts

    monkeypatch.setattr(
        receipts.receipt_service,
        "prepare_receipt_image",
        lambda filename, content_type, image_bytes: ("abc.jpg", "image/jpeg", image_bytes),
    )
    monkeypatch.setattr(
        receipts.receipt_service,
        "persist_receipt_file",
        lambda filename, image_bytes: f"./data/receipts/{filename}",
    )
    monkeypatch.setattr(
        receipts.receipt_service,
        "parse_receipt_with_service",
        lambda filename, image_bytes, content_type: {
            "date": "2024-01-15",
            "store": "Market",
            "items": [{"name": "Apple", "price": 2.5}],
            "total": 2.5,
            "raw_text": "Market Apple",
        },
    )

    response = client.post(
        "/receipts/upload",
        files={"file": ("receipt.jpg", b"fake-jpeg", "image/jpeg")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["store"] == "Market"
    assert body["total"] == 2.5
    assert body["items"] == [{"name": "Apple", "price": 2.5}]


def test_upload_receipt_parser_failure_fallback(monkeypatch, client):
    from app.api.v1 import receipts

    monkeypatch.setattr(
        receipts.receipt_service,
        "prepare_receipt_image",
        lambda filename, content_type, image_bytes: ("abc.jpg", "image/jpeg", image_bytes),
    )
    monkeypatch.setattr(
        receipts.receipt_service,
        "persist_receipt_file",
        lambda filename, image_bytes: f"./data/receipts/{filename}",
    )

    def _raise(*_args, **_kwargs):
        raise RuntimeError("parser down")

    monkeypatch.setattr(receipts.receipt_service, "parse_receipt_with_service", _raise)

    response = client.post(
        "/receipts/upload",
        files={"file": ("receipt.jpg", b"fake-jpeg", "image/jpeg")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["store"] == "Unknown"
    assert body["total"] == 0.0
    assert body["items"] == []
