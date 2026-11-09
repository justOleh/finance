def test_upload_rejects_invalid_content_type(client):
    response = client.post(
        "/receipts/upload",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


def test_parse_receipt_success_without_db_write(monkeypatch, client):
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

    parse_response = client.post(
        "/receipts/parse",
        files={"file": ("receipt.jpg", b"fake-jpeg", "image/jpeg")},
    )

    assert parse_response.status_code == 200
    body = parse_response.json()
    assert body["store"] == "Market"
    assert body["total"] == 2.5
    assert body["items"] == [{"name": "Apple", "price": 2.5}]

    expenses_response = client.get("/expenses/")
    assert expenses_response.status_code == 200
    assert expenses_response.json() == []


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


def test_upload_receipt_accepts_heic(monkeypatch, client):
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
        files={"file": ("receipt.heic", b"fake-heic", "image/heic")},
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


# --- async pipeline: upload-url + status polling (ADR-010) -----------------------------


def _configure_bucket(monkeypatch):
    import dataclasses

    from app.api.v1 import receipts

    monkeypatch.setattr(
        receipts,
        "settings",
        dataclasses.replace(receipts.settings, receipts_bucket="test-receipts"),
    )


def test_upload_url_creates_uploading_record_and_presigned_post(monkeypatch, client, table):
    _configure_bucket(monkeypatch)

    response = client.post("/receipts/upload-url", json={"content_type": "image/jpeg"})

    assert response.status_code == 201
    body = response.json()
    receipt_id = body["receipt_id"]
    assert "test-receipts" in body["upload_url"]
    # The object key embeds the owner and id: the worker derives both from it.
    assert body["fields"]["key"] == f"receipts/user-a/{receipt_id}.jpg"
    assert body["fields"]["Content-Type"] == "image/jpeg"
    assert "policy" in body["fields"]

    item = table.get_item(Key={"pk": "USER#user-a", "sk": f"RECEIPT#{receipt_id}"})["Item"]
    assert item["status"] == "UPLOADING"
    assert item["s3_key"] == body["fields"]["key"]
    # No GSI attributes: receipt records must never appear in expense listings.
    assert "gsi1pk" not in item
    assert client.get("/expenses/").json() == []


def test_upload_url_rejects_unsupported_content_type(monkeypatch, client):
    _configure_bucket(monkeypatch)

    response = client.post("/receipts/upload-url", json={"content_type": "application/pdf"})

    assert response.status_code == 400


def test_upload_url_fails_closed_without_bucket(client):
    response = client.post("/receipts/upload-url", json={"content_type": "image/png"})

    assert response.status_code == 500


def test_get_receipt_uploading_has_no_draft(monkeypatch, client):
    _configure_bucket(monkeypatch)
    receipt_id = client.post("/receipts/upload-url", json={"content_type": "image/png"}).json()[
        "receipt_id"
    ]

    response = client.get(f"/receipts/{receipt_id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": receipt_id,
        "status": "UPLOADING",
        "error": None,
        "draft": None,
    }


def test_get_receipt_parsed_returns_draft(monkeypatch, client, table):
    _configure_bucket(monkeypatch)
    created = client.post("/receipts/upload-url", json={"content_type": "image/png"}).json()
    receipt_id = created["receipt_id"]
    # Simulate the worker's write (floats are Decimal in DynamoDB).
    from decimal import Decimal

    table.update_item(
        Key={"pk": "USER#user-a", "sk": f"RECEIPT#{receipt_id}"},
        UpdateExpression="SET #s = :s, #r = :r",
        ExpressionAttributeNames={"#s": "status", "#r": "result"},
        ExpressionAttributeValues={
            ":s": "PARSED",
            ":r": {
                "date": "2026-11-09",
                "store": "Dummy Market",
                "items": [{"name": "Milk", "price": Decimal("42.5")}],
                "total": Decimal("42.5"),
                "notes": "dummy",
            },
        },
    )

    body = client.get(f"/receipts/{receipt_id}").json()

    assert body["status"] == "PARSED"
    assert body["draft"]["store"] == "Dummy Market"
    assert body["draft"]["total"] == 42.5
    assert body["draft"]["items"] == [{"name": "Milk", "price": 42.5}]
    assert body["draft"]["receipt_image_path"] == created["fields"]["key"]


def test_get_receipt_failed_returns_error(monkeypatch, client, table):
    _configure_bucket(monkeypatch)
    receipt_id = client.post("/receipts/upload-url", json={"content_type": "image/png"}).json()[
        "receipt_id"
    ]
    table.update_item(
        Key={"pk": "USER#user-a", "sk": f"RECEIPT#{receipt_id}"},
        UpdateExpression="SET #s = :s, #e = :e",
        ExpressionAttributeNames={"#s": "status", "#e": "error"},
        ExpressionAttributeValues={":s": "FAILED", ":e": "boom"},
    )

    body = client.get(f"/receipts/{receipt_id}").json()

    assert body["status"] == "FAILED"
    assert body["error"] == "boom"
    assert body["draft"] is None


def test_get_receipt_of_another_user_is_404(monkeypatch, client_as):
    _configure_bucket(monkeypatch)
    receipt_id = (
        client_as("user-a")
        .post("/receipts/upload-url", json={"content_type": "image/png"})
        .json()["receipt_id"]
    )

    assert client_as("user-b").get(f"/receipts/{receipt_id}").status_code == 404


def test_get_unknown_receipt_is_404(client):
    assert client.get("/receipts/does-not-exist").status_code == 404
