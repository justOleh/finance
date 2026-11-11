"""One chat turn: build the agent for this request, run it, translate its events for the UI.

The stream sent to the browser is a small, stable vocabulary (one JSON object per SSE line):

    {"type": "text",  "text": "..."}                    a piece of the answer
    {"type": "tool",  "name": "list_expenses"}          the agent started using a tool
    {"type": "draft", "draft": {...}}                   an expense for the confirm card
    {"type": "done",  "usage": {...}, "stop_reason": "end_turn"}
    {"type": "error", "message": "..."}

Raw framework events never leave the process: they are large, change between versions and can
contain tool inputs the UI has no use for.
"""

import base64
import json
import logging
import time
import uuid
from collections import OrderedDict
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.hooks import BeforeToolCallEvent

from finance_agent.api_client import FinanceApi
from finance_agent.config import Settings
from finance_agent.tools import build_tools

logger = logging.getLogger("finance_agent")

_PROMPT = (Path(__file__).parent / "prompts" / "system.md").read_text(encoding="utf-8")
PROMPT_VERSION = "2026-11-11.1"  # bump with every change to prompts/system.md or the tool docs

GENERIC_ERROR = "Something went wrong while answering. Please try again."
LOCAL_USER = "local"


def system_prompt(today: date | None = None) -> str:
    return _PROMPT.replace("{today}", (today or date.today()).isoformat())


def user_from_authorization(authorization: str | None) -> str:
    """Read the `sub` claim, only to label logs and to tie a session to its owner.

    The signature is NOT checked here and this value is never used to authorise anything:
    AgentCore Runtime verified the token before this code ran, and the backend verifies it
    again on every tool call.
    """
    if not authorization:
        return LOCAL_USER
    try:
        payload = authorization.split()[-1].split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return str(claims["sub"])
    except Exception:
        return "unknown"


# --- Sessions ----------------------------------------------------------------------------
# AgentCore Runtime keeps one microVM per session id, so conversation history can live in
# memory: it disappears when the session ends, which is the intended lifetime (no long-term
# memory, ADR-014). The store is still keyed and bounded so a local run behaves the same.


@dataclass
class Session:
    owner: str
    messages: list = field(default_factory=list)
    turns: int = 0


class SessionStore:
    def __init__(self, max_sessions: int = 100):
        self._sessions: OrderedDict[str, Session] = OrderedDict()
        self._max = max_sessions

    def get(self, session_id: str, owner: str) -> Session:
        session = self._sessions.get(session_id)
        # A session id presented by a different user never gets the first user's history.
        if session is None or session.owner != owner:
            session = Session(owner=owner)
            self._sessions[session_id] = session
        self._sessions.move_to_end(session_id)
        while len(self._sessions) > self._max:
            self._sessions.popitem(last=False)
        return session


# --- Limits ------------------------------------------------------------------------------


class ToolCallLimit:
    """Cancel tool calls beyond the per-request cap (stops loops, bounds cost)."""

    def __init__(self, limit: int):
        self.limit = limit
        self.calls = 0

    def __call__(self, event: BeforeToolCallEvent) -> None:
        self.calls += 1
        if self.calls > self.limit:
            event.cancel_tool = (
                "Tool call limit for this message reached. Answer with what you already have "
                "and tell the user to ask a narrower question."
            )


# --- Event translation -------------------------------------------------------------------


class ThinkingFilter:
    """Remove `<thinking>...</thinking>` from streamed text.

    Some models (Amazon Nova) write their planning inline in the answer, wrapped in these
    tags, instead of in a separate reasoning channel. It is not meant for the user. Text
    arrives in arbitrary pieces, so a tag can be split across two chunks: the end of a chunk
    that could be the start of a tag is held back until the next chunk decides.
    """

    OPEN, CLOSE = "<thinking>", "</thinking>"

    def __init__(self) -> None:
        self._buffer = ""
        self._inside = False
        self._emitted = False

    def feed(self, text: str) -> str:
        self._buffer += text
        out = []
        while self._buffer:
            tag = self.CLOSE if self._inside else self.OPEN
            index = self._buffer.find(tag)
            if index >= 0:
                if not self._inside:
                    out.append(self._buffer[:index])
                self._buffer = self._buffer[index + len(tag) :]
                self._inside = not self._inside
                continue
            # No complete tag: keep back a tail that may be the beginning of one.
            keep = next(
                (n for n in range(len(tag) - 1, 0, -1) if self._buffer.endswith(tag[:n])), 0
            )
            if not self._inside:
                out.append(self._buffer[: len(self._buffer) - keep])
            self._buffer = self._buffer[len(self._buffer) - keep :] if keep else ""
            break
        visible = "".join(out)
        if not self._emitted:
            visible = visible.lstrip()  # no blank lines where the thinking block was
        self._emitted = self._emitted or bool(visible)
        return visible

    def flush(self) -> str:
        """End of the answer: a held-back tail that never became a tag is ordinary text."""
        tail, self._buffer = ("" if self._inside else self._buffer), ""
        return tail


class Translator:
    """Turn framework stream events into the UI vocabulary above."""

    def __init__(self) -> None:
        self._announced: set[str] = set()
        self._thinking = ThinkingFilter()
        self.result: Any = None

    def translate(self, event: dict) -> list[dict]:
        if event.get("reasoning"):
            return []  # the model's thinking is not shown
        if isinstance(event.get("data"), str) and event["data"]:
            text = self._thinking.feed(event["data"])
            return [{"type": "text", "text": text}] if text else []
        tool_use = event.get("current_tool_use")
        if isinstance(tool_use, dict) and tool_use.get("toolUseId") and tool_use.get("name"):
            if tool_use["toolUseId"] not in self._announced:
                self._announced.add(tool_use["toolUseId"])
                return [{"type": "tool", "name": tool_use["name"]}]
        if "result" in event:
            self.result = event["result"]
            tail = self._thinking.flush()
            return [{"type": "text", "text": tail}] if tail else []
        return []


def usage_of(result: Any) -> dict:
    usage = getattr(getattr(result, "metrics", None), "accumulated_usage", None) or {}
    return {
        "input_tokens": int(usage.get("inputTokens", 0)),
        "output_tokens": int(usage.get("outputTokens", 0)),
        "cache_read_tokens": int(usage.get("cacheReadInputTokens", 0)),
        "cache_write_tokens": int(usage.get("cacheWriteInputTokens", 0)),
    }


def estimate_cost_usd(usage: dict, settings: Settings) -> float:
    """Rough cost of a turn. Ignores cache discounts, so it errs on the high side."""
    return round(
        usage["input_tokens"] / 1e6 * settings.price_in_per_mtok
        + usage["output_tokens"] / 1e6 * settings.price_out_per_mtok,
        6,
    )


# --- The turn ----------------------------------------------------------------------------


def validate_prompt(prompt: Any, settings: Settings) -> str | None:
    """Return an error message for the user, or None if the prompt is acceptable."""
    if not isinstance(prompt, str) or not prompt.strip():
        return "Type a message first."
    if len(prompt) > settings.max_prompt_chars:
        return f"The message is too long (limit: {settings.max_prompt_chars} characters)."
    return None


async def run_turn(
    prompt: str,
    session: Session,
    api: FinanceApi,
    settings: Settings,
    model_factory: Callable[[], Any],
    session_id: str = "",
    today: date | None = None,
) -> AsyncIterator[dict]:
    if session.turns >= settings.max_turns_per_session:
        yield {
            "type": "error",
            "message": "This conversation reached its length limit. Start a new chat.",
        }
        return

    started = time.monotonic()
    drafts: list[dict] = []
    limiter = ToolCallLimit(settings.max_tool_calls)
    translator = Translator()
    snapshot = list(session.messages)
    status = "ok"

    try:
        agent = Agent(
            model=model_factory(),
            tools=build_tools(api, drafts, settings.max_rows),
            system_prompt=system_prompt(today),
            messages=list(session.messages),
            conversation_manager=SlidingWindowConversationManager(
                window_size=settings.history_window
            ),
            callback_handler=None,
        )
        agent.hooks.add_callback(BeforeToolCallEvent, limiter)

        async for event in agent.stream_async(prompt.strip()):
            for ui_event in translator.translate(event):
                yield ui_event
            while drafts:
                yield {"type": "draft", "draft": {"id": uuid.uuid4().hex, **drafts.pop(0)}}

        session.messages = agent.messages
        session.turns += 1
        result = translator.result
        yield {
            "type": "done",
            "usage": usage_of(result),
            "stop_reason": str(getattr(result, "stop_reason", "")),
        }
    except Exception:
        # A failed turn can leave a tool call without its result in the history, which the
        # model API rejects on the next turn: go back to the state before this message.
        session.messages = snapshot
        status = "error"
        logger.exception("chat turn failed")
        yield {"type": "error", "message": GENERIC_ERROR}
    finally:
        usage = usage_of(translator.result)
        # One structured line per turn: the source for cost per user and per day (AGENTCOST05).
        # Never log the prompt, the answer or the token.
        logger.info(
            json.dumps(
                {
                    "event": "chat_turn",
                    "status": status,
                    "user": session.owner,
                    "session": session_id,
                    "model": settings.model_id,
                    "prompt_version": PROMPT_VERSION,
                    "tool_calls": limiter.calls,
                    "tool_limit_hit": limiter.calls > limiter.limit,
                    "latency_ms": int((time.monotonic() - started) * 1000),
                    **usage,
                    "est_cost_usd": estimate_cost_usd(usage, settings),
                }
            )
        )
