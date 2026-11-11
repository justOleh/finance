"""The HTTP surface AgentCore Runtime calls: POST /invocations (SSE) and GET /ping."""

import json

from starlette.testclient import TestClient

from finance_agent import main


def events_of(response) -> list[dict]:
    return [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]


def test_ping():
    assert TestClient(main.app).get("/ping").status_code == 200


def test_invalid_prompt_is_answered_as_one_sse_error_event():
    response = TestClient(main.app).post("/invocations", json={"prompt": "  "})

    assert response.headers["content-type"].startswith("text/event-stream")
    assert events_of(response) == [{"type": "error", "message": "Type a message first."}]


def test_the_forwarded_token_and_session_reach_the_turn(monkeypatch):
    seen = {}

    async def fake_run_turn(prompt, session, api, settings, model_factory, session_id):
        seen.update(prompt=prompt, owner=session.owner, session_id=session_id, api=api)
        seen["auth"] = api._client.headers.get("Authorization")
        yield {"type": "text", "text": "hi"}

    monkeypatch.setattr(main, "run_turn", fake_run_turn)

    response = TestClient(main.app).post(
        "/invocations",
        json={"prompt": "hello"},
        headers={
            "Authorization": "Bearer a.eyJzdWIiOiJ1c2VyLTEifQ.c",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": "s" * 40,
        },
    )

    assert events_of(response) == [{"type": "text", "text": "hi"}]
    assert (seen["prompt"], seen["owner"], seen["session_id"]) == ("hello", "user-1", "s" * 40)
    assert seen["auth"] == "Bearer a.eyJzdWIiOiJ1c2VyLTEifQ.c"
