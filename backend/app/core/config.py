import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    aws_region: str = os.getenv("AWS_REGION", "eu-west-1")
    dynamodb_table: str = os.getenv("DYNAMODB_TABLE", "expenses")
    # Set for DynamoDB Local in dev (e.g. http://dynamodb:8000); empty means real AWS.
    dynamodb_endpoint_url: str = os.getenv("DYNAMODB_ENDPOINT_URL", "")
    receipt_parser_url: str = os.getenv("RECEIPT_PARSER_URL", "http://localhost:8001")
    receipts_dir: str = os.getenv("RECEIPTS_DIR", "./data/receipts")


settings = Settings()
