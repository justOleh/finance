import json
from urllib.parse import quote_plus

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from parse_receipt.engine import DummyEngine, ParsedReceipt
from parse_receipt.processor import mark_failed, process_message

BUCKET = "test-receipts"
OWNER = "user-a"
RECEIPT_ID = "abc123"
KEY = f"receipts/{OWNER}/{RECEIPT_ID}.png"  # converted PNG: what the Lambda is triggered by
UPLOAD_KEY = f"receipts/{OWNER}/{RECEIPT_ID}.heic"  # original upload, stored on the record


@pytest.fixture
def aws():
    with mock_aws():
        s3 = boto3.client("s3", region_name="eu-west-1")
        s3.create_bucket(
            Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "eu-west-1"}
        )
        s3.put_object(Bucket=BUCKET, Key=KEY, Body=b"fake-image", ContentType="image/png")
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
            "s3_key": UPLOAD_KEY,
        }
    )


def _event(key=KEY):
    # S3 URL-encodes keys in notifications ("/" becomes %2F): the Lambda must decode them.
    return json.dumps(
        {"Records": [{"s3": {"bucket": {"name": BUCKET}, "object": {"key": quote_plus(key)}}}]}
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


class FixedEngine:
    model_version = "fixed"

    def __init__(self, parsed: ParsedReceipt):
        self.parsed = parsed

    def extract(self, image_bytes, content_type):
        return self.parsed


def _expenses(table):
    return [i for i in table.scan()["Items"] if i["sk"].startswith("EXPENSE#")]


def test_success_stores_a_draft_and_never_creates_an_expense(aws):
    s3, table = aws
    _put_uploading_record(table)

    process_message(_event(), s3=s3, table=table, engine=DummyEngine())

    # Only the user's Save (backend POST /expenses) creates the expense.
    assert _item(table)["status"] == "PARSED"
    assert _expenses(table) == []


@pytest.mark.parametrize(
    "parsed",
    [
        ParsedReceipt(store="Shop", date="2026-03-01", items=[], total=0.0, notes="bottom only"),
        ParsedReceipt(store="", date="2026-03-01"),
    ],
)
def test_unreadable_receipt_is_failed_without_an_expense_and_without_a_retry(aws, parsed):
    s3, table = aws
    _put_uploading_record(table)

    # Does not raise: a retry would give the same answer, so the message must be deleted.
    process_message(_event(), s3=s3, table=table, engine=FixedEngine(parsed))

    item = _item(table)
    assert item["status"] == "FAILED"
    assert "лише частину чека" in item["error"]
    assert _expenses(table) == []


def test_total_without_items_is_still_a_draft(aws):
    s3, table = aws
    _put_uploading_record(table)
    parsed = ParsedReceipt(store="Shop", date="2026-03-01", items=[], total=99.9)

    process_message(_event(), s3=s3, table=table, engine=FixedEngine(parsed))

    item = _item(table)
    assert item["status"] == "PARSED"
    assert float(item["result"]["total"]) == 99.9
