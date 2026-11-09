"""Extraction engines. The parse Lambda only depends on the `extract` interface.

`ClaudeEngine` (claude_engine.py) is the real one. `DummyEngine` returns fixed data so the whole
pipeline can be exercised without calling the model (`ENGINE=dummy`).
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class ParsedReceipt:
    store: str
    date: str  # ISO yyyy-mm-dd
    items: list[dict] = field(default_factory=list)  # [{"name": str, "price": float}]
    total: float = 0.0
    notes: str = ""


class Engine(Protocol):
    model_version: str

    def extract(self, image_bytes: bytes, content_type: str) -> ParsedReceipt: ...


class DummyEngine:
    model_version = "dummy-1"

    def extract(self, image_bytes: bytes, content_type: str) -> ParsedReceipt:
        # Proves the Lambda really read the image; the content is otherwise ignored.
        return ParsedReceipt(
            store="Dummy Market",
            date=date.today().isoformat(),
            items=[
                {"name": "Milk 1L", "price": 42.5},
                {"name": "Bread", "price": 25.0},
                {"name": "Apples 1kg", "price": 60.0},
            ],
            total=127.5,
            notes=f"dummy parse of {len(image_bytes)} bytes ({content_type})",
        )
