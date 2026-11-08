from functools import lru_cache
from typing import Any

import boto3

from app.core.config import settings


@lru_cache
def get_table() -> Any:
    """Return the app's DynamoDB Table resource (FastAPI dependency).

    Credentials come from boto3's default chain (AWS_PROFILE, env vars, role).
    """
    if not settings.dynamodb_table_name:
        raise RuntimeError("DYNAMODB_TABLE_NAME is not set")
    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    return dynamodb.Table(settings.dynamodb_table_name)
