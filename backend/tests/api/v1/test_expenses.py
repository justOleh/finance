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
    client.post(
        "/expenses/",
        json={**SAMPLE_EXPENSE, "store": "Other Shop", "date": "2024-02-20", "total": 5.00},
    )

    filtered = client.get("/expenses/?store=Super")
    assert filtered.status_code == 200
    assert all("Super" in item["store"] for item in filtered.json())

    summary = client.get("/expenses/monthly-summary")
    assert summary.status_code == 200
    assert len(summary.json()) == 2


def test_get_after_create_and_delete_missing(client):
    created = client.post("/expenses/", json=SAMPLE_EXPENSE).json()
    got = client.get(f"/expenses/{created['id']}")
    assert got.status_code == 200
    assert got.json()["items"] == SAMPLE_EXPENSE["items"]

    assert client.delete(f"/expenses/{created['id']}").status_code == 204
    assert client.delete(f"/expenses/{created['id']}").status_code == 404
    assert client.put(f"/expenses/{created['id']}", json={"total": 1}).status_code == 404


def test_date_range_filter_and_update_moves_date(client):
    first = client.post("/expenses/", json=SAMPLE_EXPENSE).json()
    client.post("/expenses/", json={**SAMPLE_EXPENSE, "date": "2024-03-01"})

    in_range = client.get("/expenses/?start_date=2024-01-01&end_date=2024-01-15").json()
    assert [e["id"] for e in in_range] == [first["id"]]

    client.put(f"/expenses/{first['id']}", json={"date": "2024-05-05"})
    assert client.get("/expenses/?start_date=2024-01-01&end_date=2024-01-31").json() == []
    newest_first = client.get("/expenses/").json()
    assert [e["date"] for e in newest_first] == ["2024-05-05", "2024-03-01"]


def test_user_cannot_access_another_users_expense(client_as):
    alice = client_as("alice")
    created = alice.post("/expenses/", json=SAMPLE_EXPENSE).json()

    bob = client_as("bob")
    assert bob.get(f"/expenses/{created['id']}").status_code == 404
    assert bob.put(f"/expenses/{created['id']}", json={"store": "x"}).status_code == 404
    assert bob.delete(f"/expenses/{created['id']}").status_code == 404
    assert bob.get("/expenses/").json() == []
    assert bob.get("/expenses/monthly-summary").json() == []

    alice = client_as("alice")
    assert alice.get(f"/expenses/{created['id']}").status_code == 200
