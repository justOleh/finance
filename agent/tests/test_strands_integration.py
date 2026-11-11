"""run_turn against the real Strands agent loop, with a scripted model instead of Bedrock.

The other tests replace `Agent` entirely. This one keeps the framework and replaces only the
model, so it fails if a Strands upgrade changes the stream events, the hook or the tool
plumbing that `chat.py` relies on. No network, no AWS.
"""

import asyncio

from strands.models.model import Model

from finance_agent.chat import Session, run_turn
from finance_agent.config import Settings


class ScriptedModel(Model):
    """Replays one scripted assistant message per model call, as Bedrock stream events."""

    def __init__(self, replies: list[list[dict]]):
        self.replies = list(replies)
        self.calls: list[dict] = []

    def update_config(self, **model_config):
        pass

    def get_config(self):
        return {"model_id": "scripted"}

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError
        yield  # pragma: no cover

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        self.calls.append({"messages": list(messages), "tool_specs": tool_specs})
        blocks = self.replies.pop(0)
        yield {"messageStart": {"role": "assistant"}}
        for block in blocks:
            if "text" in block:
                yield {"contentBlockStart": {"start": {}}}
                yield {"contentBlockDelta": {"delta": {"text": block["text"]}}}
            else:
                use = block["toolUse"]
                start = {"toolUse": {"toolUseId": use["toolUseId"], "name": use["name"]}}
                yield {"contentBlockStart": {"start": start}}
                yield {"contentBlockDelta": {"delta": {"toolUse": {"input": use["input"]}}}}
            yield {"contentBlockStop": {}}
        stop = "tool_use" if any("toolUse" in b for b in blocks) else "end_turn"
        yield {"messageStop": {"stopReason": stop}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 100, "outputTokens": 10, "totalTokens": 110},
                "metrics": {"latencyMs": 1},
            }
        }


def tool_use(tool_id: str, name: str, json_input: str) -> dict:
    return {"toolUse": {"toolUseId": tool_id, "name": name, "input": json_input}}


def collect(async_gen) -> list[dict]:
    async def run():
        return [event async for event in async_gen]

    return asyncio.run(run())


def test_real_agent_loop_calls_the_api_and_streams_ui_events(api, backend):
    model = ScriptedModel(
        [
            [
                tool_use(
                    "t1", "spending_summary", '{"start_date": "2026-10-01", "group_by": "none"}'
                )
            ],
            [
                tool_use(
                    "t2",
                    "propose_expense",
                    '{"date": "2026-11-11", "store": "Silpo", "total": 12.5}',
                )
            ],
            [{"text": "You spent 349.50 UAH. Check the card."}],
        ]
    )
    session = Session(owner="alice")

    events = collect(run_turn("how much?", session, api, Settings(), lambda: model, "s1"))

    kinds = [e["type"] for e in events]
    assert kinds == ["tool", "tool", "draft", "text", "done"]
    assert [e["name"] for e in events if e["type"] == "tool"] == [
        "spending_summary",
        "propose_expense",
    ]
    assert events[2]["draft"]["store"] == "Silpo"
    assert events[-1]["usage"] == {
        "input_tokens": 300,
        "output_tokens": 30,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
    }
    assert events[-1]["stop_reason"] == "end_turn"

    # The tool reached the API with the caller's token, and the model saw every tool spec.
    assert backend.last.url.path == "/expenses/summary"
    assert backend.last.headers["Authorization"] == "Bearer user-token"
    assert len(model.calls[0]["tool_specs"]) == 5
    # user, assistant(tool), user(result), assistant(tool), user(result), assistant(text)
    assert len(session.messages) == 6


def test_real_agent_loop_enforces_the_tool_call_cap(api, backend):
    call = '{"group_by": "none"}'
    model = ScriptedModel(
        [
            [tool_use("t1", "spending_summary", call)],
            [tool_use("t2", "spending_summary", call)],
            [{"text": "That is all I can check."}],
        ]
    )

    events = collect(
        run_turn("loop", Session(owner="alice"), api, Settings(max_tool_calls=1), lambda: model)
    )

    assert events[-1]["type"] == "done"
    assert len(backend.requests) == 1  # the second call was cancelled before it ran
    cancelled = model.calls[2]["messages"][-1]["content"][0]["toolResult"]
    assert "limit" in cancelled["content"][0]["text"]


def test_history_is_carried_into_the_next_turn(api):
    model = ScriptedModel([[{"text": "first"}], [{"text": "second"}]])
    session = Session(owner="alice")

    collect(run_turn("one", session, api, Settings(), lambda: model))
    collect(run_turn("two", session, api, Settings(), lambda: model))

    assert session.turns == 2
    assert [m["role"] for m in model.calls[1]["messages"]] == ["user", "assistant", "user"]
