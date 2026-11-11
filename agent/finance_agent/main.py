"""Entry point for Amazon Bedrock AgentCore Runtime (and for a local run on port 8080).

AgentCore Runtime has already verified the caller's Cognito token when this code runs. The
`Authorization` header reaches us because it is on the runtime's request header allowlist
(terraform/agent_runtime); we hand it to the API client and to nothing else.

Local run:   API_BASE_URL=http://localhost:8000 uv run python -m finance_agent.main
             curl -N localhost:8080/invocations -H 'Content-Type: application/json' \
                  -d '{"prompt": "How much did I spend this month?"}'
"""

import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from strands.models import BedrockModel, CacheConfig

from finance_agent.api_client import FinanceApi
from finance_agent.chat import SessionStore, run_turn, user_from_authorization, validate_prompt
from finance_agent.config import settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
# httpx logs every request URL at INFO; the query string holds store names and dates.
logging.getLogger("httpx").setLevel(logging.WARNING)

_middleware = (
    [
        Middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_methods=["POST"],
            allow_headers=["*"],
        )
    ]
    if settings.cors_origins
    else []
)

app = BedrockAgentCoreApp(middleware=_middleware)
sessions = SessionStore()


def make_model() -> BedrockModel:
    # No temperature / top_p: the Claude 5 generation rejects them (ADR-012).
    return BedrockModel(
        model_id=settings.model_id,
        region_name=settings.aws_region,
        max_tokens=settings.max_output_tokens,
        # System prompt and tool definitions are identical on every call: cache them where the
        # model supports cache points (Claude does; Amazon Nova logs a warning per call).
        cache_config=CacheConfig(strategy="auto") if "anthropic" in settings.model_id else None,
    )


@app.entrypoint
async def invoke(payload: dict, context):
    payload = payload if isinstance(payload, dict) else {}
    problem = validate_prompt(payload.get("prompt"), settings)
    if problem:
        yield {"type": "error", "message": problem}
        return

    authorization = (context.request_headers or {}).get("Authorization")
    session_id = context.session_id or "local"
    session = sessions.get(session_id, user_from_authorization(authorization))

    api = FinanceApi(settings.api_base_url, authorization)
    try:
        async for event in run_turn(
            payload["prompt"], session, api, settings, make_model, session_id
        ):
            yield event
    finally:
        api.close()


if __name__ == "__main__":
    app.run()
