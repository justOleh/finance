import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


@dataclass(frozen=True)
class Settings:
    # Base URL of the existing REST API (the HTTP API in front of the backend, or
    # http://localhost:8000 for a local run). The agent has no other way to reach data.
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    # Bedrock inference profile. "eu." keeps inference in EU regions. Amazon Nova needs no
    # third-party agreement; Claude models need the Anthropic use-case form first (agent/README).
    model_id: str = os.getenv("MODEL_ID", "eu.amazon.nova-pro-v1:0")
    aws_region: str = os.getenv("AWS_REGION", "eu-west-1")

    # --- Limits (ADR-014, AGENTCOST07-BP01). One request = one user message. -----------------
    max_prompt_chars: int = _int("MAX_PROMPT_CHARS", 2000)
    max_tool_calls: int = _int("MAX_TOOL_CALLS", 8)
    max_output_tokens: int = _int("MAX_OUTPUT_TOKENS", 2000)
    max_turns_per_session: int = _int("MAX_TURNS_PER_SESSION", 30)
    history_window: int = _int("HISTORY_WINDOW", 30)  # messages kept in the model's context
    max_rows: int = _int("MAX_ROWS", 50)  # expenses returned by one list_expenses call

    # USD per million tokens, only used for the cost estimate in the usage log.
    # Defaults are the Nova Pro on-demand list price from an AWS launch post (US region, may
    # be out of date): check the Bedrock pricing page for your region and model.
    price_in_per_mtok: float = _float("PRICE_IN_PER_MTOK", 0.8)
    price_out_per_mtok: float = _float("PRICE_OUT_PER_MTOK", 3.2)

    # Only for running the agent on a laptop with a browser pointed at it. On AgentCore Runtime
    # the managed endpoint answers CORS itself.
    cors_origins: tuple[str, ...] = tuple(
        o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()
    )


settings = Settings()
