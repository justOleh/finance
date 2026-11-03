import os

# Fake credentials so boto3 never touches a real account; must be set before imports.
os.environ.update(
    AWS_ACCESS_KEY_ID="testing",
    AWS_SECRET_ACCESS_KEY="testing",
    AWS_SESSION_TOKEN="testing",
    AWS_REGION="eu-west-1",
    DYNAMODB_TABLE="expenses-test",
)
os.environ.pop("DYNAMODB_ENDPOINT_URL", None)

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app.db.session import get_table
from app.main import app


@pytest.fixture(autouse=True)
def dynamodb():
    with mock_aws():
        get_table.cache_clear()
        boto3.client("dynamodb", region_name="eu-west-1").create_table(
            TableName="expenses-test",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield
        get_table.cache_clear()


@pytest.fixture
def client(dynamodb):
    with TestClient(app) as c:
        yield c
