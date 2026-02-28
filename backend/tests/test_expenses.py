import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite:///:memory:"

# Patch database before importing the app
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import Base, get_db
import main  # noqa: E402 – must come after sys.path insert

engine_test = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture
def client(setup_db):  # noqa: F811 – explicit dependency ensures tables exist first
    main.app.dependency_overrides[get_db] = override_get_db
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()


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


def test_get_expenses(client):
    client.post("/expenses/", json=SAMPLE_EXPENSE)
    resp = client.get("/expenses/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


def test_get_expense_by_id(client):
    created = client.post("/expenses/", json=SAMPLE_EXPENSE).json()
    resp = client.get(f"/expenses/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]
    assert resp.json()["store"] == "Super Mart"


def test_get_expense_not_found(client):
    resp = client.get("/expenses/99999")
    assert resp.status_code == 404


def test_update_expense(client):
    created = client.post("/expenses/", json=SAMPLE_EXPENSE).json()
    update_payload = {"store": "Updated Store", "total": 10.00}
    resp = client.put(f"/expenses/{created['id']}", json=update_payload)
    assert resp.status_code == 200
    assert resp.json()["store"] == "Updated Store"
    assert resp.json()["total"] == 10.00


def test_delete_expense(client):
    created = client.post("/expenses/", json=SAMPLE_EXPENSE).json()
    del_resp = client.delete(f"/expenses/{created['id']}")
    assert del_resp.status_code == 204
    get_resp = client.get(f"/expenses/{created['id']}")
    assert get_resp.status_code == 404


def test_filter_expenses_by_store(client):
    client.post("/expenses/", json=SAMPLE_EXPENSE)
    other = {**SAMPLE_EXPENSE, "store": "Other Shop"}
    client.post("/expenses/", json=other)
    resp = client.get("/expenses/?store=Super")
    assert resp.status_code == 200
    results = resp.json()
    assert all("Super" in e["store"] for e in results)


def test_monthly_summary(client):
    client.post("/expenses/", json=SAMPLE_EXPENSE)
    # Add a second expense in the same month
    second = {**SAMPLE_EXPENSE, "total": 10.00}
    client.post("/expenses/", json=second)
    # Add an expense in a different month
    other_month = {**SAMPLE_EXPENSE, "date": "2024-02-20", "total": 5.00}
    client.post("/expenses/", json=other_month)

    resp = client.get("/expenses/monthly-summary")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2

    jan = next((m for m in data if m["month"] == 1), None)
    assert jan is not None
    assert jan["year"] == 2024
    assert jan["count"] == 2
    assert abs(jan["total"] - (6.48 + 10.00)) < 0.01

    feb = next((m for m in data if m["month"] == 2), None)
    assert feb is not None
    assert feb["count"] == 1
    assert abs(feb["total"] - 5.00) < 0.01

