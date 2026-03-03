import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/finance.db")
    receipt_parser_url: str = os.getenv("RECEIPT_PARSER_URL", "http://localhost:8001")
    receipts_dir: str = os.getenv("RECEIPTS_DIR", "./data/receipts")


settings = Settings()
