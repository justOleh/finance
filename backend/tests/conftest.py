import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app.core.auth import get_current_user
from app.db.dynamodb import get_table
from app.db.s3 import get_s3_client
from app.main import app

TABLE_NAME = "test-app"


def _signing_only_s3_client():
    """Presigning is computed locally (no network), so tests need no S3 mock."""
    return boto3.client("s3", region_name="eu-west-1")


@pytest.fixture(autouse=True)
def fake_aws_env(monkeypatch):
    """Make sure tests can never reach a real AWS account."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)


@pytest.fixture
def table(fake_aws_env):
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="eu-west-1")
        yield dynamodb.create_table(
            TableName=TABLE_NAME,
            BillingMode="PAY_PER_REQUEST",
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
                {"AttributeName": "gsi1pk", "AttributeType": "S"},
                {"AttributeName": "gsi1sk", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "gsi1",
                    "KeySchema": [
                        {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                        {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
        )


@pytest.fixture
def client(table):
    """TestClient signed in as "user-a" (token verification is covered in test_auth.py)."""
    app.dependency_overrides[get_table] = lambda: table
    app.dependency_overrides[get_s3_client] = _signing_only_s3_client
    app.dependency_overrides[get_current_user] = lambda: "user-a"
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def client_as(table):
    """Factory: client_as("user-b") returns a TestClient acting as that user."""
    app.dependency_overrides[get_table] = lambda: table
    app.dependency_overrides[get_s3_client] = _signing_only_s3_client

    def make_client(user_id: str) -> TestClient:
        app.dependency_overrides[get_current_user] = lambda: user_id
        return TestClient(app)

    yield make_client
    app.dependency_overrides.clear()
