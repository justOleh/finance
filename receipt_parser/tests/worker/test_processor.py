import json
from urllib.parse import quote_plus

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from worker.engine import DummyEngine
from worker.processor import mark_failed, process_message

BUCKET = "test-receipts"
OWNER = "user-a"
RECEIPT_ID = "abc123"
KEY = f"receipts/{OWNER}/{RECEIPT_ID}.jpg"


@pytest.fixture(autouse=True)
def fake_aws_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)


@pytest.fixture
def aws():
    with mock_aws():
        s3 = boto3.client("s3", region_name="eu-west-1")
        s3.create_bucket(
            Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "eu-west-1"}
        )
        s3.put_object(Bucket=BUCKET, Key=KEY, Body=b"fake-image", ContentType="image/jpeg")
        table = boto3.resource("dynamodb", region_name="eu-west-1").create_table(
            TableName="test-app",
            BillingMode="PAY_PER_REQUEST",
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
        )
        yield s3, table


def _put_uploading_record(table):
    table.put_item(
        Item={
            "pk": f"USER#{OWNER}",
            "sk": f"RECEIPT#{RECEIPT_ID}",
            "status": "UPLOADING",
            "s3_key": KEY,
        }
    )


def _event(key=KEY):
    # S3 URL-encodes keys in notifications ("/" becomes %2F): the worker must decode them.
    return json.dumps(
        {
            "Records": [
                {"s3": {"bucket": {"name": BUCKET}, "object": {"key": quote_plus(key)}}}
            ]
        }
    )


def _item(table):
    return table.get_item(Key={"pk": f"USER#{OWNER}", "sk": f"RECEIPT#{RECEIPT_ID}"})["Item"]


def test_process_message_stores_parsed_result(aws):
    s3, table = aws
    _put_uploading_record(table)

    process_message(_event(), s3=s3, table=table, engine=DummyEngine())

    item = _item(table)
    assert item["status"] == "PARSED"
    assert item["result"]["store"] == "Dummy Market"
    assert item["result"]["total"] == 127.5
    assert len(item["result"]["items"]) == 3
    assert item["model_version"] == "dummy-1"
    # It really downloaded the image: the dummy echoes the byte count.
    assert "10 bytes" in item["result"]["notes"]


def test_process_message_is_idempotent(aws):
    s3, table = aws
    _put_uploading_record(table)

    process_message(_event(), s3=s3, table=table, engine=DummyEngine())
    first = _item(table)["result"]
    process_message(_event(), s3=s3, table=table, engine=DummyEngine())

    assert _item(table)["result"] == first


def test_s3_test_event_is_ignored(aws):
    s3, table = aws
    body = json.dumps({"Service": "Amazon S3", "Event": "s3:TestEvent"})

    process_message(body, s3=s3, table=table, engine=DummyEngine())

    assert table.scan()["Items"] == []


def test_orphan_upload_without_record_raises_and_creates_nothing(aws):
    s3, table = aws

    with pytest.raises(ClientError) as exc:
        process_message(_event(), s3=s3, table=table, engine=DummyEngine())

    assert exc.value.response["Error"]["Code"] == "ConditionalCheckFailedException"
    assert table.scan()["Items"] == []


def test_unexpected_key_layout_raises(aws):
    s3, table = aws

    with pytest.raises(ValueError):
        process_message(_event("other/file.jpg"), s3=s3, table=table, engine=DummyEngine())


def test_engine_failure_propagates_and_mark_failed_records_it(aws):
    s3, table = aws
    _put_uploading_record(table)

    class BrokenEngine:
        model_version = "broken"

        def extract(self, image_bytes, content_type):
            raise RuntimeError("model crashed")

    with pytest.raises(RuntimeError):
        process_message(_event(), s3=s3, table=table, engine=BrokenEngine())
    assert _item(table)["status"] == "UPLOADING"  # unchanged until the last attempt

    mark_failed(_event(), "model crashed", table=table)

    item = _item(table)
    assert item["status"] == "FAILED"
    assert item["error"] == "model crashed"
