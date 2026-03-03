SAMPLE_EXPENSE = {
    "date": "2024-01-15",
    "store": "Super Mart",
    "items": [{"name": "Milk", "price": 2.99}, {"name": "Bread", "price": 3.49}],
    "total": 6.48,
    "notes": "Weekly groceries",
}


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_create_expense(client):
    resp = client.post("/expenses/", json=SAMPLE_EXPENSE)
    assert resp.status_code == 201
    data = resp.json()
    assert data["store"] == "Super Mart"
    assert data["total"] == 6.48
    assert len(data["items"]) == 2
    assert data["id"] is not None


def test_get_expense_not_found(client):
    resp = client.get("/expenses/99999")
    assert resp.status_code == 404


def test_update_and_delete_expense(client):
    created = client.post("/expenses/", json=SAMPLE_EXPENSE).json()

    update_payload = {"store": "Updated Store", "total": 10.00}
    upd = client.put(f"/expenses/{created['id']}", json=update_payload)
    assert upd.status_code == 200
    assert upd.json()["store"] == "Updated Store"

    dele = client.delete(f"/expenses/{created['id']}")
    assert dele.status_code == 204


def test_filter_and_monthly_summary(client):
    client.post("/expenses/", json=SAMPLE_EXPENSE)
    client.post("/expenses/", json={**SAMPLE_EXPENSE, "store": "Other Shop", "date": "2024-02-20", "total": 5.00})

    filtered = client.get("/expenses/?store=Super")
    assert filtered.status_code == 200
    assert all("Super" in item["store"] for item in filtered.json())

    summary = client.get("/expenses/monthly-summary")
    assert summary.status_code == 200
    assert len(summary.json()) == 2
