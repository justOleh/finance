import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Name comes from `terraform output -raw app_table_name`.
    dynamodb_table_name: str = os.getenv("DYNAMODB_TABLE_NAME", "")
    aws_region: str = os.getenv("AWS_REGION", "eu-west-1")
    receipt_parser_url: str = os.getenv("RECEIPT_PARSER_URL", "http://localhost:8001")
    receipts_dir: str = os.getenv("RECEIPTS_DIR", "./data/receipts")
    # Comma-separated browser origins allowed by CORS (the frontend URL).
    cors_origins: tuple[str, ...] = tuple(
        o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()
    )


settings = Settings()
