# Chat agent

A chat facade over the my-finance REST API ([ADR-014](../docs/architecture/ADRs/ADR-014-chat-agent-facade-on-agentcore.md)).
It runs on Amazon Bedrock AgentCore Runtime, uses a Claude model on Bedrock through
[Strands Agents](https://strandsagents.com), and reaches data only by calling the REST API with
the caller's own Cognito token. It has no write tools: it proposes an expense, the user saves it.

```
finance_agent/
  main.py          AgentCore entry point (POST /invocations as SSE, GET /ping on port 8080)
  chat.py          one chat turn: sessions, limits, event translation, usage log
  tools.py         the five tools (read-only API calls + propose_expense)
  api_client.py    the only door to the data: the REST API with the caller's token
  prompts/system.md
  config.py        settings from environment variables
tests/             unit tests, no AWS or network needed
evals/             fixed questions with expected behaviour, run against the real model
```

## Tests

```bash
cd agent
uv sync --extra dev
uv run pytest                      # 50+ tests, no AWS or network
../scripts/ruff-fix.sh agent       # from anywhere: lint + format
```

`tests/test_strands_integration.py` runs the real Strands loop with a scripted model, so it
catches framework upgrades that change stream events or hooks.

## Evals (real model, costs a few cents)

```bash
uv run python -m evals.run_evals              # all cases
uv run python -m evals.run_evals injection    # ids starting with "injection"
```

Last run (2026-11-11): `eu.amazon.nova-pro-v1:0` passes 20/20 (about 67k input and 3k output
tokens for the whole set); `eu.amazon.nova-2-lite-v1:0` passed 14/20 on the earlier, stricter
checks (it mangled a receipt id and answered an English question in Ukrainian). To try another
model: `MODEL_ID=<profile id> uv run python -m evals.run_evals`.

Amazon Nova writes its planning inline as `<thinking>...</thinking>`; `chat.py` strips it from
the stream and the evals fail if it leaks.

**Model access for Claude (one time per account).** Amazon models work without it. Anthropic
models on Bedrock need a use-case form before the first call. Without it every call fails with `AccessDeniedException: ... is not
available for this account`. In the Bedrock console (region `eu-west-1`) open Model catalog,
choose the model, and submit the use-case details; access usually follows within minutes.
Check the state without spending anything:

```bash
uv run python -c "import boto3; print(boto3.client('bedrock', region_name='eu-west-1').get_foundation_model_availability(modelId='anthropic.claude-sonnet-5-5')['agreementAvailability'])"
```

`AVAILABLE` means calls will work. (AWS CLI 2.27 does not have this command yet; boto3 does.)

Needs AWS credentials allowed to call `bedrock:InvokeModel*` on the model in `MODEL_ID`. The
REST API is faked with fixed data, so no backend is needed and no real expense is touched.
Run it before changing `prompts/system.md` or a tool docstring, and bump `PROMPT_VERSION` in
`chat.py` when you do.

## Run locally

```bash
# Terminal 1: the backend (see the repo README), then:
API_BASE_URL=http://localhost:8000 CORS_ORIGINS=http://localhost:5173 \
    uv run python -m finance_agent.main

# Terminal 2
curl -N localhost:8080/invocations -H 'Content-Type: application/json' \
     -d '{"prompt": "How much did I spend this month?"}'
```

For the browser, start the frontend with `VITE_AGENT_URL=http://localhost:8080/invocations`.
With `AUTH_DISABLED=true` on the backend no token is needed; against a deployed API add
`-H "Authorization: Bearer <Cognito access token>"`.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `API_BASE_URL` | `http://localhost:8000` | REST API the tools call |
| `MODEL_ID` | `eu.amazon.nova-pro-v1:0` | Bedrock inference profile (`aws bedrock list-inference-profiles`) |
| `AWS_REGION` | `eu-west-1` | Region of the Bedrock call |
| `MAX_TOOL_CALLS` | 8 | Tool calls per user message |
| `MAX_OUTPUT_TOKENS` | 2000 | Output cap per model call |
| `MAX_PROMPT_CHARS` | 2000 | Longest accepted user message |
| `MAX_TURNS_PER_SESSION` | 30 | User messages per conversation |
| `HISTORY_WINDOW` | 30 | Messages kept in the model's context |
| `PRICE_IN_PER_MTOK`, `PRICE_OUT_PER_MTOK` | 0.8, 3.2 | Only for the cost estimate in the usage log. Defaults are an old US list price for Nova Pro; check the Bedrock pricing page |
| `CORS_ORIGINS` | empty | Local browser use only; on AgentCore the managed endpoint answers CORS |

## What is logged

One JSON line per turn (`"event": "chat_turn"`): user id, session, model, prompt version, tool
calls, latency, tokens and an estimated cost. Prompts, answers and tokens are never logged.
On AWS the lines are in the log group `/aws/bedrock-agentcore/runtimes/<runtime id>-DEFAULT`.
