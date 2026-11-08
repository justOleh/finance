import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app.db.dynamodb import get_table
from app.main import app

TABLE_NAME = "test-app"


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
    app.dependency_overrides[get_table] = lambda: table
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
