from functools import lru_cache

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings


@lru_cache(maxsize=1)
def get_table():
    resource = boto3.resource(
        "dynamodb",
        region_name=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url or None,
    )
    return resource.Table(settings.dynamodb_table)


def ensure_table() -> None:
    """Create the table if missing. Only used with DynamoDB Local; in AWS Terraform owns the table."""
    table = get_table()
    try:
        table.load()
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        table.meta.client.create_table(
            TableName=settings.dynamodb_table,
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
