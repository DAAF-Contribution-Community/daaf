"""Offline loopback harness for the real provider shim subprocess.

The helpers in this module deliberately keep translator logic out of the test
process.  Every projection is obtained by starting the production shim, routing
it to a deterministic loopback Responses server, and calling the shim's
Anthropic-compatible HTTP endpoint.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import select
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Iterable, Optional


DAAF_ROOT = Path("/daaf")
PRODUCTION_SHIM = DAAF_ROOT / "scripts/provider_shim/anthropic_openai_shim.py"
SCRATCH_ROOT = DAAF_ROOT / "scripts/scratch"
SCRATCH_PREFIX = "provider-shim-unittest-"
FAKE_OPENAI_KEY = "sk-FAKE_PROVIDER_SHIM_UNITTEST_OPENAI_000000000000"
FAKE_REFRESH_TOKEN = "FAKE_PROVIDER_SHIM_REFRESH_TOKEN_000000000000"
FAKE_ID_TOKEN = "FAKE_PROVIDER_SHIM_ID_TOKEN_000000000000"
FAKE_ACCOUNT_ID = "acct_provider_shim_unittest"
USAGE = {"input_tokens": 31, "output_tokens": 17, "total_tokens": 48}
NONSTREAM_REJECTION_BODY = {"detail": "Stream must be set to true"}
TERMINAL_FIELD_OMITTED = object()

CENTRAL_SOURCE_DELTAS = [
    "**Planning ",
    "tests**",
    "**Validating boundaries**",
    "**Checking reset**",
]
CENTRAL_LEGACY_TEXT = "".join(CENTRAL_SOURCE_DELTAS)
CENTRAL_DESIRED_TEXT = (
    "**Planning tests**\n\n"
    "**Validating boundaries**\n\n"
    "**Checking reset**"
)


@dataclass(frozen=True)
class TypedSSEFrame:
    """One ordered SSE frame with its event name and decoded data payload."""

    event: Optional[str]
    data: Any
    raw_data: str


@dataclass
class HTTPResult:
    status: int
    headers: dict[str, str]
    body: bytes

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


@dataclass
class BackendRequest:
    path: str
    headers: dict[str, str]
    body: dict[str, Any]


@dataclass
class Scenario:
    """Deterministic upstream streaming and non-streaming response pair."""

    name: str
    stream_events: list[dict[str, Any]]
    nonstream_response: dict[str, Any]
    reject_nonstream: bool = False
    append_done: bool = True
    raw_stream_frames: Optional[list[bytes]] = None
    abrupt_eof: bool = False
    stream_status: int = 200
    stream_headers: dict[str, str] = field(default_factory=dict)
    stream_error_body: bytes = b'{"error":{"message":"fixture backend rejection"}}'
    disconnect_phase: Optional[str] = None
    disconnect_delay: float = 1.8


@dataclass(frozen=True)
class RawDisconnectMetadata:
    """Bounded observations from one raw downstream request and close."""

    request_bytes_sent: int
    response_headers_seen: bool
    marker_seen: bool
    bytes_observed: int


@dataclass
class LifecycleReport:
    starts: list[tuple[int, str]] = field(default_factory=list)
    stops: list[int] = field(default_factory=list)
    open_at_end: set[int] = field(default_factory=set)


@dataclass
class FailureLifecycleReport:
    starts: list[tuple[int, str]] = field(default_factory=list)
    stops: list[int] = field(default_factory=list)
    error: dict[str, Any] = field(default_factory=dict)
    open_at_end: set[int] = field(default_factory=set)


class _EventBuilder:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.sequence_number = 0

    def add(self, event_type: str, **fields: Any) -> dict[str, Any]:
        event = {
            "type": event_type,
            "sequence_number": self.sequence_number,
            **fields,
        }
        self.sequence_number += 1
        self.events.append(event)
        return event


def _reasoning_item(item_id: str, parts: Iterable[dict[str, Any]]) -> dict[str, Any]:
    summary = []
    for part in parts:
        text = part.get("full_text")
        if text is None:
            text = "".join(part.get("deltas") or [])
        summary.append({"type": "summary_text", "text": text})
    return {
        "type": "reasoning",
        "id": item_id,
        "status": "completed",
        "summary": summary,
        "encrypted_content": f"ENC_{item_id}",
    }


def _append_reasoning_item(
    builder: _EventBuilder,
    item_id: str,
    output_index: int,
    parts: list[dict[str, Any]],
) -> dict[str, Any]:
    builder.add(
        "response.output_item.added",
        output_index=output_index,
        item={"type": "reasoning", "id": item_id, "status": "in_progress"},
    )
    for part in parts:
        summary_index = part["summary_index"]
        deltas = list(part.get("deltas") or [])
        full_text = part.get("full_text")
        if full_text is None:
            full_text = "".join(deltas)
        builder.add(
            "response.reasoning_summary_part.added",
            item_id=item_id,
            output_index=output_index,
            summary_index=summary_index,
            part={"type": "summary_text", "text": ""},
        )
        for delta in deltas:
            builder.add(
                "response.reasoning_summary_text.delta",
                item_id=item_id,
                output_index=output_index,
                summary_index=summary_index,
                delta=delta,
            )
        builder.add(
            "response.reasoning_summary_text.done",
            item_id=item_id,
            output_index=output_index,
            summary_index=summary_index,
            text=full_text,
        )
        builder.add(
            "response.reasoning_summary_part.done",
            item_id=item_id,
            output_index=output_index,
            summary_index=summary_index,
            part={"type": "summary_text", "text": full_text},
        )
    item = _reasoning_item(item_id, parts)
    builder.add(
        "response.output_item.done",
        output_index=output_index,
        item=item,
    )
    return item


def _append_text_item(
    builder: _EventBuilder,
    output_index: int,
    text: str = "Final answer.",
) -> dict[str, Any]:
    item_id = f"msg_fixture_{output_index}"
    builder.add(
        "response.output_item.added",
        output_index=output_index,
        item={
            "type": "message",
            "id": item_id,
            "role": "assistant",
            "status": "in_progress",
            "content": [],
        },
    )
    builder.add(
        "response.output_text.delta",
        item_id=item_id,
        output_index=output_index,
        content_index=0,
        delta=text,
    )
    item = {
        "type": "message",
        "id": item_id,
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": text}],
    }
    builder.add("response.output_item.done", output_index=output_index, item=item)
    return item


def _append_tool_item(
    builder: _EventBuilder,
    output_index: int,
    call_id: str = "call_fixture_1",
    item_id: str = "fc_fixture_1",
) -> dict[str, Any]:
    arguments = '{"file_path":"/daaf/README.md"}'
    builder.add(
        "response.output_item.added",
        output_index=output_index,
        item={
            "type": "function_call",
            "id": item_id,
            "call_id": call_id,
            "name": "Read",
            "status": "in_progress",
        },
    )
    builder.add(
        "response.function_call_arguments.delta",
        item_id=item_id,
        output_index=output_index,
        delta='{"file_path":"/daaf/',
    )
    builder.add(
        "response.function_call_arguments.delta",
        item_id=item_id,
        output_index=output_index,
        delta='README.md"}',
    )
    # LIVE-WIRE SHAPE (2026-07-16 shim.log evidence): the Codex backend omits
    # `name` on arguments.done — the shim resolves it from output_item.added.
    # The public OpenAI API documents a `name` field here; that name-bearing
    # variant is covered by a dedicated test, not by the default fixture.
    builder.add(
        "response.function_call_arguments.done",
        item_id=item_id,
        output_index=output_index,
        arguments=arguments,
    )
    item = {
        "type": "function_call",
        "id": item_id,
        "call_id": call_id,
        "name": "Read",
        "arguments": arguments,
        "status": "completed",
    }
    builder.add("response.output_item.done", output_index=output_index, item=item)
    return item


def _finish_response(
    builder: _EventBuilder,
    response_id: str,
    output: list[dict[str, Any]],
) -> None:
    builder.add(
        "response.completed",
        response={
            "id": response_id,
            "status": "completed",
            "output": output,
            "usage": dict(USAGE),
        },
    )


def _nonstream_response(
    response_id: str,
    output: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": response_id,
        "model": "gpt-fixture",
        "status": "completed",
        "output": output,
        "usage": dict(USAGE),
        "incomplete_details": None,
        "error": None,
    }


def central_multipart_scenario(transition: Optional[str] = None) -> Scenario:
    """Capture-faithful two-item fixture with a per-item summary-index reset."""

    builder = _EventBuilder()
    builder.add(
        "response.created",
        response={"id": "resp_multipart", "status": "in_progress"},
    )
    item_a_parts = [
        {"summary_index": 0, "deltas": ["**Planning ", "tests**"]},
        {"summary_index": 1, "deltas": ["**Validating boundaries**"]},
    ]
    item_b_parts = [
        {"summary_index": 0, "deltas": ["**Checking reset**"]},
    ]
    output = [
        _append_reasoning_item(builder, "rs_fixture_A", 0, item_a_parts),
        _append_reasoning_item(builder, "rs_fixture_B", 1, item_b_parts),
    ]
    if transition == "text":
        output.append(_append_text_item(builder, 2))
    elif transition == "tool":
        output.append(_append_tool_item(builder, 2))
    elif transition is not None:
        raise ValueError(f"unsupported transition: {transition}")
    _finish_response(builder, "resp_multipart", output)
    return Scenario(
        name=f"central-multipart-{transition or 'reasoning-only'}",
        stream_events=builder.events,
        nonstream_response=_nonstream_response("resp_multipart_ns", output),
    )


def identity_parts_scenario(
    name: str,
    parts: list[dict[str, Any]],
    transition: Optional[str] = None,
) -> Scenario:
    """Build one or more serialized reasoning items from explicit part identities."""

    builder = _EventBuilder()
    builder.add("response.created", response={"id": f"resp_{name}", "status": "in_progress"})
    output: list[dict[str, Any]] = []
    position = 0
    while position < len(parts):
        item_id = parts[position]["item_id"]
        output_index = parts[position]["output_index"]
        grouped = []
        while (
            position < len(parts)
            and parts[position]["item_id"] == item_id
            and parts[position]["output_index"] == output_index
        ):
            grouped.append(parts[position])
            position += 1
        output.append(_append_reasoning_item(builder, item_id, output_index, grouped))
    next_index = max((part["output_index"] for part in parts), default=-1) + 1
    if transition == "text":
        output.append(_append_text_item(builder, next_index))
    elif transition == "tool":
        output.append(_append_tool_item(builder, next_index))
    elif transition is not None:
        raise ValueError(f"unsupported transition: {transition}")
    _finish_response(builder, f"resp_{name}", output)
    return Scenario(
        name=name,
        stream_events=builder.events,
        nonstream_response=_nonstream_response(f"resp_{name}_ns", output),
    )


def malformed_identity_scenario() -> Scenario:
    """Reasoning deltas whose identity is absent or malformed by construction."""

    builder = _EventBuilder()
    builder.add("response.created", response={"id": "resp_malformed", "status": "in_progress"})
    builder.add(
        "response.reasoning_summary_text.delta",
        item_id="rs_missing_summary",
        output_index=0,
        delta="M",
    )
    builder.add(
        "response.reasoning_summary_text.delta",
        item_id="rs_string_summary",
        output_index=0,
        summary_index="1",
        delta="N",
    )
    builder.add(
        "response.reasoning_summary_text.delta",
        item_id="rs_bool_output",
        output_index=True,
        summary_index=0,
        delta="O",
    )
    _finish_response(builder, "resp_malformed", [])
    return Scenario(
        name="malformed-identity",
        stream_events=builder.events,
        nonstream_response=_nonstream_response("resp_malformed_ns", []),
    )


def mixed_identity_scenario() -> Scenario:
    """Identity becomes less complete mid-part, disabling later synthesis."""

    builder = _EventBuilder()
    builder.add("response.created", response={"id": "resp_mixed", "status": "in_progress"})
    builder.add(
        "response.reasoning_summary_text.delta",
        item_id="rs_mixed",
        output_index=0,
        summary_index=0,
        delta="A",
    )
    builder.add(
        "response.reasoning_summary_text.delta",
        item_id="rs_mixed",
        summary_index=0,
        delta="B",
    )
    builder.add(
        "response.reasoning_summary_text.delta",
        item_id="rs_mixed",
        output_index=0,
        summary_index=1,
        delta="C",
    )
    _finish_response(builder, "resp_mixed", [])
    return Scenario(
        name="mixed-identity",
        stream_events=builder.events,
        nonstream_response=_nonstream_response("resp_mixed_ns", []),
    )


def raw_reasoning_delta_scenario(
    name: str,
    deltas: list[dict[str, Any]],
    nonstream_output: Optional[list[dict[str, Any]]] = None,
) -> Scenario:
    """Build a stream from exact reasoning-delta fields, including omissions."""

    builder = _EventBuilder()
    builder.add("response.created", response={"id": f"resp_{name}", "status": "in_progress"})
    for fields in deltas:
        builder.add("response.reasoning_summary_text.delta", **dict(fields))
    output = list(nonstream_output or [])
    _finish_response(builder, f"resp_{name}", output)
    return Scenario(
        name=name,
        stream_events=builder.events,
        nonstream_response=_nonstream_response(f"resp_{name}_ns", output),
    )


def reopened_thinking_scenario() -> Scenario:
    """Synthetic reasoning -> tool -> reasoning ordering for state-reset coverage."""

    builder = _EventBuilder()
    builder.add("response.created", response={"id": "resp_reopen", "status": "in_progress"})
    output = [
        _append_reasoning_item(
            builder,
            "rs_before_tool",
            0,
            [{"summary_index": 0, "deltas": ["Before tool"]}],
        ),
        _append_tool_item(
            builder,
            1,
            call_id="call_reopen_fixture",
            item_id="fc_reopen_fixture",
        ),
        _append_reasoning_item(
            builder,
            "rs_after_tool",
            2,
            [{"summary_index": 0, "deltas": ["After tool"]}],
        ),
    ]
    _finish_response(builder, "resp_reopen", output)
    return Scenario(
        name="reopened-thinking",
        stream_events=builder.events,
        nonstream_response=_nonstream_response("resp_reopen_ns", output),
    )


def minimal_dual_mode_scenario() -> Scenario:
    return identity_parts_scenario(
        "dual-mode",
        [
            {"item_id": "rs_dual", "output_index": 0, "summary_index": 0, "deltas": ["A"]},
            {"item_id": "rs_dual", "output_index": 0, "summary_index": 1, "deltas": ["B"]},
        ],
        transition="text",
    )


def full_response_scenario(*, reject_nonstream: bool = False) -> Scenario:
    """Completed Responses SSE whose terminal event carries full output and usage."""

    builder = _EventBuilder()
    builder.add("response.created", response={"id": "resp_full", "status": "in_progress"})
    output = [
        _append_reasoning_item(
            builder,
            "rs_full",
            0,
            [{"summary_index": 0, "deltas": ["Inspecting stream semantics."]}],
        ),
        _append_text_item(builder, 1, text="Aggregated answer."),
        _append_tool_item(
            builder,
            2,
            call_id="call_full_fixture",
            item_id="fc_full_fixture",
        ),
    ]
    _finish_response(builder, "resp_full", output)
    return Scenario(
        name="full-response",
        stream_events=builder.events,
        nonstream_response=_nonstream_response("resp_full_nonstream", output),
        reject_nonstream=reject_nonstream,
    )


def events_scenario(
    name: str,
    events: list[dict[str, Any]],
    *,
    nonstream_response: Optional[dict[str, Any]] = None,
    append_done: bool = True,
) -> Scenario:
    """Build an exact ordered semantic-event fixture without normalizing fields."""

    return Scenario(
        name=name,
        stream_events=list(events),
        nonstream_response=(
            dict(nonstream_response)
            if nonstream_response is not None
            else _nonstream_response(f"resp_{name}_nonstream", [])
        ),
        append_done=append_done,
    )


def terminal_contract_scenario(
    name: str,
    event_type: str,
    *,
    status: Any = TERMINAL_FIELD_OMITTED,
    output: Any = TERMINAL_FIELD_OMITTED,
    usage: Any = TERMINAL_FIELD_OMITTED,
    leading_events: Optional[list[dict[str, Any]]] = None,
    trailing_events: Optional[list[dict[str, Any]]] = None,
) -> Scenario:
    """Build one exact terminal event and matching JSON response for schema tests."""

    response: dict[str, Any] = {"id": f"resp_{name}"}
    if status is not TERMINAL_FIELD_OMITTED:
        response["status"] = status
    if output is not TERMINAL_FIELD_OMITTED:
        response["output"] = output
    if usage is not TERMINAL_FIELD_OMITTED:
        response["usage"] = usage
    events = list(leading_events or [])
    events.append({"type": event_type, "response": response})
    events.extend(trailing_events or [])
    return events_scenario(
        name,
        events,
        nonstream_response=response,
    )


def raw_sse_scenario(name: str, frames: list[bytes]) -> Scenario:
    """Build an exact byte-framing fixture for upstream SSE parser contracts."""

    return Scenario(
        name=name,
        stream_events=[],
        nonstream_response=_nonstream_response(f"resp_{name}_nonstream", []),
        append_done=False,
        raw_stream_frames=list(frames),
    )


def backend_status_scenario(
    name: str,
    status: int,
    *,
    retry_after: Optional[str] = None,
) -> Scenario:
    """Return the same deterministic backend status on every streamed attempt."""

    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    return Scenario(
        name=name,
        stream_events=[],
        nonstream_response=_nonstream_response(f"resp_{name}_nonstream", []),
        append_done=False,
        stream_status=status,
        stream_headers=headers,
        stream_error_body=(
            b'{"error":{"type":"fixture_status","message":"fixture rejection"}}'
        ),
    )


def delayed_header_disconnect_scenario(delay: float = 1.8) -> Scenario:
    """Normal SSE response whose HTTP headers are withheld for disconnect testing."""

    scenario = full_response_scenario()
    scenario.name = "disconnect-delayed-headers"
    scenario.disconnect_phase = "headers"
    scenario.disconnect_delay = delay
    return scenario


def delayed_body_disconnect_scenario(delay: float = 1.8) -> Scenario:
    """Valid text prefix followed by a stalled SSE body and delayed terminal write."""

    builder, output = _prefix_events("text")
    return Scenario(
        name="disconnect-delayed-body",
        stream_events=builder.events,
        nonstream_response=_nonstream_response("resp_disconnect_body_ns", output),
        append_done=False,
        disconnect_phase="body",
        disconnect_delay=delay,
    )


def retry_sleep_disconnect_scenario(delay: float = 1.8) -> Scenario:
    """Retryable pre-content status with a deterministic Retry-After delay."""

    scenario = backend_status_scenario(
        "disconnect-retry-sleep",
        503,
        retry_after=str(delay),
    )
    scenario.disconnect_phase = "retry"
    scenario.disconnect_delay = delay
    return scenario


def sequential_two_tools_scenario() -> Scenario:
    """Two fully serialized function calls used as the overlap-control fixture."""

    builder = _EventBuilder()
    builder.add(
        "response.created",
        response={"id": "resp_two_tools", "status": "in_progress"},
    )
    output = [
        _append_tool_item(
            builder,
            0,
            call_id="call_sequential_1",
            item_id="fc_sequential_1",
        ),
        _append_tool_item(
            builder,
            1,
            call_id="call_sequential_2",
            item_id="fc_sequential_2",
        ),
    ]
    _finish_response(builder, "resp_two_tools", output)
    return Scenario(
        name="sequential-two-tools",
        stream_events=builder.events,
        nonstream_response=_nonstream_response("resp_two_tools_nonstream", output),
    )


def incomplete_response_scenario() -> Scenario:
    """Incomplete Responses SSE whose terminal event carries output and usage."""

    builder = _EventBuilder()
    builder.add(
        "response.created",
        response={"id": "resp_incomplete", "status": "in_progress"},
    )
    output = [_append_text_item(builder, 0, text="Truncated fixture answer.")]
    builder.add(
        "response.incomplete",
        response={
            "id": "resp_incomplete",
            "status": "incomplete",
            "output": output,
            "usage": dict(USAGE),
            "incomplete_details": {"reason": "max_output_tokens"},
        },
    )
    return Scenario(
        name="incomplete-response",
        stream_events=builder.events,
        nonstream_response={
            **_nonstream_response("resp_incomplete_nonstream", output),
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
        },
    )


def _prefix_events(prefix: str) -> tuple[_EventBuilder, list[dict[str, Any]]]:
    """Build one deliberately unfinished content prefix for failure fixtures."""

    builder = _EventBuilder()
    builder.add(
        "response.created",
        response={"id": f"resp_prefix_{prefix}", "status": "in_progress"},
    )
    output: list[dict[str, Any]] = []
    if prefix == "thinking":
        builder.add(
            "response.output_item.added",
            output_index=0,
            item={"type": "reasoning", "id": "rs_prefix", "status": "in_progress"},
        )
        builder.add(
            "response.reasoning_summary_part.added",
            item_id="rs_prefix",
            output_index=0,
            summary_index=0,
            part={"type": "summary_text", "text": ""},
        )
        builder.add(
            "response.reasoning_summary_text.delta",
            item_id="rs_prefix",
            output_index=0,
            summary_index=0,
            delta="Partial thinking.",
        )
    elif prefix == "text":
        builder.add(
            "response.output_item.added",
            output_index=0,
            item={
                "type": "message",
                "id": "msg_prefix",
                "role": "assistant",
                "status": "in_progress",
                "content": [],
            },
        )
        builder.add(
            "response.output_text.delta",
            item_id="msg_prefix",
            output_index=0,
            content_index=0,
            delta="Partial text.",
        )
    elif prefix == "tool":
        arguments = '{"file_path":"/daaf/README.md"}'
        builder.add(
            "response.output_item.added",
            output_index=0,
            item={
                "type": "function_call",
                "id": "fc_prefix",
                "call_id": "call_prefix",
                "name": "Read",
                "status": "in_progress",
            },
        )
        builder.add(
            "response.function_call_arguments.delta",
            item_id="fc_prefix",
            output_index=0,
            delta=arguments,
        )
        # Live-wire shape: no `name` on arguments.done (see _append_tool_item).
        builder.add(
            "response.function_call_arguments.done",
            item_id="fc_prefix",
            output_index=0,
            arguments=arguments,
        )
    else:
        raise ValueError(f"unsupported prefix: {prefix}")
    return builder, output


def terminal_failure_scenario(prefix: str, terminal: str) -> Scenario:
    """In-band response.failed or error after a selected unfinished prefix."""

    builder, output = _prefix_events(prefix)
    if terminal == "response.failed":
        builder.add(
            "response.failed",
            response={
                "id": f"resp_failed_{prefix}",
                "status": "failed",
                "output": output,
                "usage": dict(USAGE),
                "error": {"code": "fixture_failure", "message": "fixture response failed"},
            },
        )
    elif terminal == "error":
        builder.add(
            "error",
            error={"type": "server_error", "message": "fixture in-band error"},
        )
    else:
        raise ValueError(f"unsupported terminal: {terminal}")
    return Scenario(
        name=f"{terminal}-after-{prefix}",
        stream_events=builder.events,
        nonstream_response={
            "id": f"resp_failed_{prefix}_nonstream",
            "status": "failed",
            "output": output,
            "usage": dict(USAGE),
            "error": {"code": "fixture_failure", "message": "fixture response failed"},
        },
    )


def abrupt_eof_scenario(prefix: str) -> Scenario:
    """Valid content prefix followed by a genuine framing-level abrupt EOF."""

    builder, output = _prefix_events(prefix)
    return Scenario(
        name=f"abrupt-eof-after-{prefix}",
        stream_events=builder.events,
        nonstream_response=_nonstream_response(f"resp_abrupt_{prefix}", output),
        append_done=False,
        abrupt_eof=True,
    )


def reasoning_while_text_open_scenario() -> Scenario:
    """Malformed ordering: a reasoning delta arrives while text remains open."""

    builder, _output = _prefix_events("text")
    builder.add(
        "response.reasoning_summary_text.delta",
        item_id="rs_after_text",
        output_index=1,
        summary_index=0,
        delta="Out-of-order thinking.",
    )
    _finish_response(builder, "resp_reasoning_after_text", [])
    return Scenario(
        name="reasoning-while-text-open",
        stream_events=builder.events,
        nonstream_response=_nonstream_response("resp_reasoning_after_text_ns", []),
    )


def reasoning_while_tool_open_scenario() -> Scenario:
    """Malformed ordering: reasoning follows tool args before output_item.done."""

    builder, _output = _prefix_events("tool")
    builder.add(
        "response.reasoning_summary_text.delta",
        item_id="rs_after_tool",
        output_index=1,
        summary_index=0,
        delta="Out-of-order thinking.",
    )
    _finish_response(builder, "resp_reasoning_after_tool", [])
    return Scenario(
        name="reasoning-while-tool-open",
        stream_events=builder.events,
        nonstream_response=_nonstream_response("resp_reasoning_after_tool_ns", []),
    )


def missing_terminal_response_scenario() -> Scenario:
    """Well-formed SSE reaches [DONE] without a terminal response object."""

    builder, output = _prefix_events("text")
    return Scenario(
        name="missing-terminal-response",
        stream_events=builder.events,
        nonstream_response=_nonstream_response("resp_missing_terminal_ns", output),
    )


def malformed_sse_scenario() -> Scenario:
    """One valid SSE prefix followed by a syntactically malformed data event."""

    builder, output = _prefix_events("text")
    frames = []
    for event in builder.events:
        event_name = event.get("type", "message")
        frames.append(
            (
                f"event: {event_name}\n"
                f"data: {json.dumps(event, separators=(',', ':'))}\n\n"
            ).encode("utf-8")
        )
    frames.append(b"event: response.output_text.delta\ndata: {malformed-json\n\n")
    frames.append(b"data: [DONE]\n\n")
    return Scenario(
        name="malformed-sse",
        stream_events=[],
        nonstream_response=_nonstream_response("resp_malformed_sse_ns", output),
        append_done=False,
        raw_stream_frames=frames,
    )


def _assert_loopback_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise AssertionError(f"URL is not loopback-only: {url!r}")
    if parsed.port is None:
        raise AssertionError(f"loopback URL has no explicit dynamic port: {url!r}")


def is_loopback_url(url: str) -> bool:
    try:
        _assert_loopback_url(url)
    except (AssertionError, ValueError):
        return False
    return True


def _direct_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _direct_request(request: urllib.request.Request, timeout: float) -> HTTPResult:
    try:
        with _direct_opener().open(request, timeout=timeout) as response:
            return HTTPResult(
                status=response.status,
                headers={key.lower(): value for key, value in response.headers.items()},
                body=response.read(),
            )
    except urllib.error.HTTPError as error:
        return HTTPResult(
            status=error.code,
            headers={key.lower(): value for key, value in error.headers.items()},
            body=error.read(),
        )


def _wait_for_peer_close(
    connection: socket.socket,
    deadline: float,
    release: Optional[threading.Event] = None,
) -> bool:
    """Observe FIN/RST without consuming bytes, bounded by a monotonic deadline."""

    while time.monotonic() < deadline:
        if release is not None and release.is_set():
            return False
        remaining = deadline - time.monotonic()
        readable, _writable, exceptional = select.select(
            [connection],
            [],
            [connection],
            min(0.05, max(remaining, 0.0)),
        )
        if exceptional:
            return True
        if not readable:
            continue
        try:
            peeked = connection.recv(1, socket.MSG_PEEK)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return True
        if peeked == b"":
            return True
        return False
    return False


class MockResponsesServer(AbstractContextManager["MockResponsesServer"]):
    """Threaded loopback Responses/OAuth server on an OS-assigned port."""

    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.responses_requests: list[BackendRequest] = []
        self.response_timestamps: list[float] = []
        self.oauth_requests: list[BackendRequest] = []
        self.first_response_request = threading.Event()
        self.second_response_request = threading.Event()
        self.oauth_request_received = threading.Event()
        self.oauth_response_release = threading.Event()
        self.oauth_response_sent = threading.Event()
        self.delay_oauth_response = False
        self.rotated_access_token = _make_fake_jwt(int(time.time()) + 365 * 86400)
        self.body_prefix_flushed = threading.Event()
        self.peer_closed_before_delayed_send = threading.Event()
        self.delayed_send_failed = threading.Event()
        self.delayed_send_succeeded = threading.Event()
        self.delayed_send_completed = threading.Event()
        self.release_delayed_send = threading.Event()
        self._lock = threading.Lock()
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self.base_url = ""

    def __enter__(self) -> "MockResponsesServer":
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, _format: str, *args: Any) -> None:
                return

            def _send_bytes(
                self,
                status: int,
                content_type: str,
                payload: bytes,
                extra_headers: Optional[dict[str, str]] = None,
            ) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Connection", "close")
                for name, value in (extra_headers or {}).items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(payload)
                self.wfile.flush()
                self.close_connection = True

            def _send_abrupt_sse(self, frames: list[bytes]) -> None:
                # Deliberately omit Content-Length and the terminating zero-sized
                # chunk. The peer observes a framing-level EOF after complete SSE
                # frames rather than a timing-dependent server delay.
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Transfer-Encoding", "chunked")
                self.send_header("Connection", "close")
                self.end_headers()
                for frame in frames:
                    self.wfile.write(f"{len(frame):X}\r\n".encode("ascii"))
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
                self.close_connection = True

            def _stream_bytes(self, events: list[dict[str, Any]], append_done: bool) -> bytes:
                frames = []
                for event in events:
                    event_name = event.get("type", "message")
                    frames.append(
                        (
                            f"event: {event_name}\n"
                            f"data: {json.dumps(event, separators=(',', ':'))}\n\n"
                        ).encode("utf-8")
                    )
                if append_done:
                    frames.append(b"data: [DONE]\n\n")
                return b"".join(frames)

            def _record_delayed_send(self, send: Callable[[], None]) -> None:
                deadline = time.monotonic() + owner.scenario.disconnect_delay
                peer_closed = _wait_for_peer_close(
                    self.connection,
                    deadline,
                    owner.release_delayed_send,
                )
                if peer_closed:
                    # Once the cancellation contract has already been observed, try
                    # the delayed write immediately. Waiting out the original delay
                    # made the follow-up outcome assertion depend on how *quickly* a
                    # correct implementation closed: faster cancellation paradoxically
                    # left more delay than the assertion's fixed wait budget.
                    owner.peer_closed_before_delayed_send.set()
                else:
                    remaining = deadline - time.monotonic()
                    if remaining > 0:
                        owner.release_delayed_send.wait(remaining)
                try:
                    send()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    owner.delayed_send_failed.set()
                else:
                    owner.delayed_send_succeeded.set()
                finally:
                    owner.delayed_send_completed.set()

            def _send_delayed_headers(self) -> None:
                payload = self._stream_bytes(
                    owner.scenario.stream_events,
                    owner.scenario.append_done,
                )

                def send() -> None:
                    self._send_bytes(200, "text/event-stream", payload)

                self._record_delayed_send(send)

            def _send_delayed_body(self) -> None:
                prefix = self._stream_bytes(owner.scenario.stream_events, False)
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Transfer-Encoding", "chunked")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(f"{len(prefix):X}\r\n".encode("ascii"))
                self.wfile.write(prefix)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
                owner.body_prefix_flushed.set()

                terminal = {
                    "type": "response.completed",
                    "response": {
                        "id": "resp_disconnect_body",
                        "status": "completed",
                        "output": [],
                        "usage": dict(USAGE),
                    },
                }
                terminal_frame = self._stream_bytes([terminal], True)

                def send() -> None:
                    self.wfile.write(
                        f"{len(terminal_frame):X}\r\n".encode("ascii")
                    )
                    self.wfile.write(terminal_frame)
                    self.wfile.write(b"\r\n0\r\n\r\n")
                    self.wfile.flush()
                    self.close_connection = True

                self._record_delayed_send(send)

            def _read_json(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                parsed = json.loads(raw.decode("utf-8"))
                if not isinstance(parsed, dict):
                    raise ValueError("request body is not a JSON object")
                return parsed

            def do_POST(self) -> None:
                try:
                    body = self._read_json()
                except (ValueError, json.JSONDecodeError):
                    self._send_bytes(400, "application/json", b'{"error":"bad json"}')
                    return
                record = BackendRequest(
                    path=self.path,
                    headers={key.lower(): value for key, value in self.headers.items()},
                    body=body,
                )
                if self.path.endswith("/responses"):
                    with owner._lock:
                        owner.responses_requests.append(record)
                        owner.response_timestamps.append(time.monotonic())
                        if len(owner.responses_requests) == 1:
                            owner.first_response_request.set()
                        elif len(owner.responses_requests) == 2:
                            owner.second_response_request.set()
                    if owner.scenario.reject_nonstream and body.get("stream") is not True:
                        payload = json.dumps(
                            NONSTREAM_REJECTION_BODY,
                            separators=(",", ":"),
                        ).encode("utf-8")
                        self._send_bytes(400, "application/json", payload)
                        return
                    if body.get("stream") is True:
                        if owner.scenario.disconnect_phase == "headers":
                            self._send_delayed_headers()
                            return
                        if owner.scenario.disconnect_phase == "body":
                            self._send_delayed_body()
                            return
                        if owner.scenario.stream_status >= 400:
                            self._send_bytes(
                                owner.scenario.stream_status,
                                "application/json",
                                owner.scenario.stream_error_body,
                                owner.scenario.stream_headers,
                            )
                            return
                        if owner.scenario.raw_stream_frames is not None:
                            frames = list(owner.scenario.raw_stream_frames)
                        else:
                            frames = []
                            for event in owner.scenario.stream_events:
                                event_name = event.get("type", "message")
                                frames.append(
                                    (
                                        f"event: {event_name}\n"
                                        f"data: {json.dumps(event, separators=(',', ':'))}\n\n"
                                    ).encode("utf-8")
                                )
                            if owner.scenario.append_done:
                                frames.append(b"data: [DONE]\n\n")
                        if owner.scenario.abrupt_eof:
                            self._send_abrupt_sse(frames)
                        else:
                            self._send_bytes(200, "text/event-stream", b"".join(frames))
                    else:
                        payload = json.dumps(
                            owner.scenario.nonstream_response,
                            separators=(",", ":"),
                        ).encode("utf-8")
                        self._send_bytes(200, "application/json", payload)
                    return
                if self.path.endswith("/oauth/token"):
                    with owner._lock:
                        owner.oauth_requests.append(record)
                    owner.oauth_request_received.set()
                    if owner.delay_oauth_response:
                        if not owner.oauth_response_release.wait(10.0):
                            self._send_bytes(
                                504,
                                "application/json",
                                b'{"error":"fixture oauth release timed out"}',
                            )
                            return
                    refreshed = {
                        "access_token": owner.rotated_access_token,
                        "refresh_token": FAKE_REFRESH_TOKEN + "_ROTATED",
                        "id_token": FAKE_ID_TOKEN + "_ROTATED",
                        "expires_in": 365 * 86400,
                        "token_type": "Bearer",
                    }
                    self._send_bytes(
                        200,
                        "application/json",
                        json.dumps(refreshed, separators=(",", ":")).encode("utf-8"),
                    )
                    owner.oauth_response_sent.set()
                    return
                self._send_bytes(404, "application/json", b'{"error":"not found"}')

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        host, port = self._server.server_address[:2]
        self.base_url = f"http://{host}:{port}"
        _assert_loopback_url(self.base_url)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name=f"provider-shim-mock-{port}",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.release_delayed_send.set()
        self.oauth_response_release.set()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                raise RuntimeError("mock server thread did not stop")
        self._server = None
        self._thread = None

    @property
    def responses_url(self) -> str:
        return f"{self.base_url}/responses"

    @property
    def oauth_url(self) -> str:
        return f"{self.base_url}/oauth/token"

    def assert_request_counts(self, responses: int, oauth: int = 0) -> None:
        actual = (len(self.responses_requests), len(self.oauth_requests))
        expected = (responses, oauth)
        if actual != expected:
            raise AssertionError(
                f"mock request counts differ: actual={actual!r} expected={expected!r}"
            )


class OccupiedLoopbackPort(AbstractContextManager["OccupiedLoopbackPort"]):
    """Listening loopback socket used to inject a deterministic address collision."""

    def __init__(self) -> None:
        self._socket: Optional[socket.socket] = None
        self.port = 0

    def __enter__(self) -> "OccupiedLoopbackPort":
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        self._socket = sock
        self.port = int(sock.getsockname()[1])
        _assert_loopback_url(f"http://127.0.0.1:{self.port}")
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self._socket is not None:
            self._socket.close()
        self._socket = None


class _ClosedLoopbackEndpoint(AbstractContextManager["_ClosedLoopbackEndpoint"]):
    """Bound but non-listening loopback socket used as an always-closed proxy."""

    def __init__(self) -> None:
        self._socket: Optional[socket.socket] = None
        self.url = ""

    def __enter__(self) -> "_ClosedLoopbackEndpoint":
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        host, port = sock.getsockname()
        self._socket = sock
        self.url = f"http://{host}:{port}"
        _assert_loopback_url(self.url)
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self._socket is not None:
            self._socket.close()
        self._socket = None


def _b64url_json(value: dict[str, Any]) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _make_fake_jwt(expiry: int) -> str:
    header = _b64url_json({"alg": "none", "typ": "JWT"})
    payload = _b64url_json(
        {
            "exp": expiry,
            "marker": "FABRICATED_PROVIDER_SHIM_UNITTEST_ONLY",
            "https://api.openai.com/auth": {"chatgpt_account_id": FAKE_ACCOUNT_ID},
        }
    )
    signature = base64.urlsafe_b64encode(b"fabricated-signature").rstrip(b"=").decode("ascii")
    return f"{header}.{payload}.{signature}"


def provider_scratch_residue() -> set[Path]:
    if not SCRATCH_ROOT.exists():
        return set()
    return {path for path in SCRATCH_ROOT.glob(f"{SCRATCH_PREFIX}*") if path.exists()}


def _reserve_dynamic_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _is_confirmed_address_in_use(error: BaseException) -> bool:
    """Recognize only OS/uvicorn diagnostics that prove a bind collision."""

    message = str(error).lower()
    return any(
        marker in message
        for marker in (
            "address already in use",
            "errno 98",
            "errno 48",
            "winerror 10048",
            "eaddrinuse",
        )
    )


@dataclass
class PortRaceSelector:
    """Select one injected port first, then fresh loopback candidates on retries."""

    first_port: int
    selected: list[int] = field(default_factory=list)

    def __call__(self) -> int:
        port = self.first_port if not self.selected else _reserve_dynamic_port()
        self.selected.append(port)
        return port


class RealShim(AbstractContextManager["RealShim"]):
    """One real production-shim subprocess with isolated fake credentials."""

    _CONTROLLED_BASE_ENV = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
    }
    _CONTROLLED_CHILD_ENV_NAMES = frozenset({
        "SHIM_PORT",
        "SHIM_BACKEND_MODE",
        "SHIM_BACKEND_BASE_URL",
        "SHIM_BACKEND_API_KEY",
        "OPENAI_API_KEY",
        "CODEX_HOME",
        "SHIM_OAUTH_TOKEN_URL",
        "SHIM_OAUTH_CLIENT_ID",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
        "PYTHONUNBUFFERED",
    })

    def __init__(
        self,
        backend: MockResponsesServer,
        mode: str,
        *,
        port_selector: Optional[Callable[[], int]] = None,
    ) -> None:
        if mode not in {"openai", "chatgpt"}:
            raise ValueError(f"unsupported shim mode: {mode}")
        self.backend = backend
        self.mode = mode
        self._port_selector = port_selector or _reserve_dynamic_port
        self.port = 0
        self.base_url = ""
        self.backend_base_url = ""
        self.oauth_url = ""
        self.proxy_url = ""
        self.scratch_dir: Optional[Path] = None
        self.auth_path: Optional[Path] = None
        self.child_env: dict[str, str] = {}
        self.health: dict[str, Any] = {}
        self.stderr = ""
        self.process: Optional[subprocess.Popen[str]] = None
        self._stderr_lines: list[str] = []
        self._stderr_condition = threading.Condition()
        self._stderr_thread: Optional[threading.Thread] = None
        self._proxy_guard: Optional[_ClosedLoopbackEndpoint] = None

    def __enter__(self) -> "RealShim":
        if not PRODUCTION_SHIM.is_file():
            raise FileNotFoundError(PRODUCTION_SHIM)
        try:
            SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
            self.scratch_dir = SCRATCH_ROOT / f"{SCRATCH_PREFIX}{uuid.uuid4().hex}"
            self.scratch_dir.mkdir(mode=0o700)
            self.auth_path = self.scratch_dir / "auth.json"
            fake_access = _make_fake_jwt(int(time.time()) + 365 * 86400)
            auth = {
                "OPENAI_API_KEY": FAKE_OPENAI_KEY,
                "auth_mode": "chatgpt",
                "last_refresh": "2099-01-01T00:00:00.000000000Z",
                "tokens": {
                    "access_token": fake_access,
                    "account_id": FAKE_ACCOUNT_ID,
                    "id_token": FAKE_ID_TOKEN,
                    "refresh_token": FAKE_REFRESH_TOKEN,
                },
            }
            self.auth_path.write_text(json.dumps(auth), encoding="utf-8")
            self.auth_path.chmod(0o600)

            self._proxy_guard = _ClosedLoopbackEndpoint()
            self._proxy_guard.__enter__()
            self.proxy_url = self._proxy_guard.url

            # SECURITY: construct the child environment from a fixed allowlist,
            # never from os.environ. This prevents arbitrary parent credentials
            # (including unknown *_TOKEN/*_SECRET/*_PASSWORD names) from reaching
            # the production-shim subprocess. PATH/locale/TZ are controlled test
            # constants; every remaining key below is a fabricated or loopback-only
            # shim input. HOME and broad PYTHON* state are intentionally absent.
            env = dict(self._CONTROLLED_BASE_ENV)

            self.backend_base_url = (
                f"{self.backend.base_url}/v1"
                if self.mode == "openai"
                else self.backend.base_url
            )
            self.oauth_url = self.backend.oauth_url
            for url in (self.backend_base_url, self.oauth_url, self.proxy_url):
                _assert_loopback_url(url)

            env.update(
                {
                    "SHIM_BACKEND_MODE": self.mode,
                    "SHIM_BACKEND_BASE_URL": self.backend_base_url,
                    "SHIM_BACKEND_API_KEY": FAKE_OPENAI_KEY,
                    "OPENAI_API_KEY": FAKE_OPENAI_KEY,
                    "CODEX_HOME": str(self.scratch_dir),
                    "SHIM_OAUTH_TOKEN_URL": self.oauth_url,
                    "SHIM_OAUTH_CLIENT_ID": "app_FAKE_PROVIDER_SHIM_UNITTEST",
                    "HTTP_PROXY": self.proxy_url,
                    "HTTPS_PROXY": self.proxy_url,
                    "ALL_PROXY": self.proxy_url,
                    "NO_PROXY": "127.0.0.1,localhost",
                    "http_proxy": self.proxy_url,
                    "https_proxy": self.proxy_url,
                    "all_proxy": self.proxy_url,
                    "no_proxy": "127.0.0.1,localhost",
                    "PYTHONUNBUFFERED": "1",
                }
            )

            # The reserve/release/start sequence has an unavoidable test-only bind
            # race. Retry at most twice, and only when uvicorn's captured startup
            # diagnostic confirms EADDRINUSE. Each failed child is fully reaped and
            # its pipes closed before selecting a fresh candidate; unrelated startup
            # errors propagate immediately through the outer cleanup path.
            for startup_attempt in range(3):
                self.port = self._port_selector()
                self.base_url = f"http://127.0.0.1:{self.port}"
                _assert_loopback_url(self.base_url)
                env["SHIM_PORT"] = str(self.port)
                self.child_env = dict(env)
                self.health = {}
                self.stderr = ""
                self._stderr_lines = []
                self._stderr_thread = None
                self.process = subprocess.Popen(
                    [sys.executable, str(PRODUCTION_SHIM)],
                    cwd=str(DAAF_ROOT),
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self._stderr_thread = threading.Thread(
                    target=self._capture_stderr,
                    name=f"provider-shim-stderr-{self.port}",
                    daemon=True,
                )
                self._stderr_thread.start()
                try:
                    self.health = self._wait_ready()
                except BaseException as startup_error:
                    self._stop_process()
                    if (
                        startup_attempt < 2
                        and _is_confirmed_address_in_use(startup_error)
                    ):
                        continue
                    raise
                return self
            raise RuntimeError("shim startup retry loop exhausted")
        except BaseException:
            # __exit__ is never called when __enter__ raises. Enclose every
            # acquisition step so scratch/auth, proxy socket, and any partial
            # subprocess are still released while preserving the original error.
            try:
                self._stop_process()
            except BaseException:
                pass
            try:
                self._cleanup_files()
            except BaseException:
                pass
            try:
                self._close_proxy()
            except BaseException:
                pass
            raise

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        process_error: Optional[BaseException] = None
        try:
            self._stop_process()
        except BaseException as error:
            process_error = error
        try:
            self._cleanup_files()
        finally:
            self._close_proxy()
        if process_error is not None:
            raise process_error

    def _capture_stderr(self) -> None:
        """Drain child stderr continuously and expose complete line barriers."""

        process = self.process
        if process is None or process.stderr is None:
            return
        for line in process.stderr:
            with self._stderr_condition:
                self._stderr_lines.append(line)
                self._stderr_condition.notify_all()

    def wait_for_stderr_line(
        self,
        marker: str,
        *,
        timeout: float = 5.0,
    ) -> tuple[str, float]:
        """Wait for one non-secret production log marker and timestamp observation."""

        deadline = time.monotonic() + timeout
        with self._stderr_condition:
            while True:
                matches = [line for line in self._stderr_lines if marker in line]
                if matches:
                    return matches[-1], time.monotonic()
                if self.process is not None and self.process.poll() is not None:
                    raise RuntimeError(
                        f"shim exited before stderr marker {marker!r}: "
                        f"{''.join(self._stderr_lines)[-2000:]}"
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        f"stderr marker {marker!r} not observed within {timeout:.2f}s"
                    )
                self._stderr_condition.wait(min(0.05, remaining))

    def captured_stderr(self) -> str:
        with self._stderr_condition:
            return "".join(self._stderr_lines)

    def _wait_ready(self, timeout: float = 15.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_error: Optional[BaseException] = None
        while time.monotonic() < deadline:
            if self.process is not None and self.process.poll() is not None:
                stderr = self.captured_stderr()
                raise RuntimeError(
                    f"production shim exited before readiness rc={self.process.returncode}: "
                    f"{stderr[-2000:]}"
                )
            request = urllib.request.Request(f"{self.base_url}/health", method="GET")
            try:
                result = _direct_request(request, timeout=0.5)
                if result.status == 200:
                    health = result.json()
                    if health.get("status") != "ok":
                        raise RuntimeError(f"unexpected health body: {health!r}")
                    if health.get("backend_mode") != self.mode:
                        raise RuntimeError(f"unexpected backend mode: {health!r}")
                    return health
            except (OSError, ValueError, urllib.error.URLError) as error:
                last_error = error
            time.sleep(0.05)
        raise TimeoutError(f"shim /health readiness timed out: {last_error!r}")

    def _stop_process(self) -> None:
        process = self.process
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if self._stderr_thread is not None:
            self._stderr_thread.join(timeout=5)
            if self._stderr_thread.is_alive():
                raise RuntimeError("shim stderr capture thread did not stop")
        self.stderr = self.captured_stderr()
        if process.stderr is not None:
            process.stderr.close()
        if process.poll() is None:
            raise RuntimeError("shim subprocess remained alive after cleanup")
        self.process = None
        self._stderr_thread = None

    def _cleanup_files(self) -> None:
        if self.scratch_dir is not None and self.scratch_dir.exists():
            shutil.rmtree(self.scratch_dir)

    def _close_proxy(self) -> None:
        if self._proxy_guard is not None:
            self._proxy_guard.__exit__(None, None, None)
        self._proxy_guard = None

    def expire_auth_access_token(self) -> None:
        """Replace only the fabricated access token with an already-expired JWT."""

        if self.auth_path is None:
            raise RuntimeError("shim auth store is not initialized")
        auth = json.loads(self.auth_path.read_text(encoding="utf-8"))
        auth["tokens"]["access_token"] = _make_fake_jwt(int(time.time()) - 3600)
        self.auth_path.write_text(json.dumps(auth), encoding="utf-8")
        self.auth_path.chmod(0o600)

    def post_messages(
        self,
        *,
        stream: bool,
        model: str = "gpt-fixture",
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> HTTPResult:
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": 256,
            "stream": stream,
            "messages": [{"role": "user", "content": "Exercise the fixture."}],
        }
        if tools is not None:
            body["tools"] = tools
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/v1/messages",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return _direct_request(request, timeout=30.0)

    def get_health(self, timeout: float = 2.0) -> HTTPResult:
        request = urllib.request.Request(f"{self.base_url}/health", method="GET")
        return _direct_request(request, timeout=timeout)

    def stop_for_disconnect_test(self) -> None:
        """Stop and reap the child while retaining context-owned fixture metadata."""

        self._stop_process()

    def assert_offline_contract(self) -> None:
        if self.scratch_dir is None or self.auth_path is None:
            raise AssertionError("shim context was not initialized")
        for url in (self.base_url, self.backend_base_url, self.oauth_url, self.proxy_url):
            _assert_loopback_url(url)
        if Path(self.child_env["CODEX_HOME"]) != self.scratch_dir:
            raise AssertionError("child CODEX_HOME did not point to isolated scratch")
        if self.auth_path.parent != self.scratch_dir:
            raise AssertionError("fabricated auth.json escaped the isolated scratch directory")
        if not str(self.scratch_dir).startswith(str(SCRATCH_ROOT) + os.sep):
            raise AssertionError("isolated credential directory is outside scripts/scratch")
        if self.child_env.get("OPENAI_API_KEY") != FAKE_OPENAI_KEY:
            raise AssertionError("child OpenAI key is not the fabricated test key")
        allowed_names = set(self._CONTROLLED_BASE_ENV) | set(self._CONTROLLED_CHILD_ENV_NAMES)
        unexpected_names = set(self.child_env) - allowed_names
        if unexpected_names:
            raise AssertionError(
                f"child environment contains non-allowlisted names: {sorted(unexpected_names)!r}"
            )
        if "HOME" in self.child_env:
            raise AssertionError("child environment inherited HOME unexpectedly")
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
            if self.child_env.get(name) != self.proxy_url:
                raise AssertionError(f"{name} does not target the closed loopback proxy")
        if self.child_env.get("NO_PROXY") != "127.0.0.1,localhost":
            raise AssertionError("NO_PROXY does not explicitly permit loopback fixtures")


def raw_disconnect_messages(
    shim: RealShim,
    *,
    marker: Optional[bytes | str] = None,
    close_after_event: Optional[threading.Event] = None,
    timeout: float = 5.0,
    max_observed_bytes: int = 64 * 1024,
) -> RawDisconnectMetadata:
    """Send one real request, optionally await bounded response evidence, then close."""

    if timeout <= 0:
        raise ValueError("raw disconnect timeout must be positive")
    if max_observed_bytes <= 0:
        raise ValueError("raw disconnect observation cap must be positive")
    marker_bytes = marker.encode("utf-8") if isinstance(marker, str) else marker
    body = {
        "model": "gpt-fixture",
        "max_tokens": 256,
        "stream": True,
        "messages": [{"role": "user", "content": "Exercise disconnect cancellation."}],
    }
    payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
    request_bytes = (
        b"POST /v1/messages HTTP/1.1\r\n"
        + f"Host: 127.0.0.1:{shim.port}\r\n".encode("ascii")
        + b"Content-Type: application/json\r\n"
        + b"Accept: text/event-stream\r\n"
        + b"Connection: close\r\n"
        + f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii")
        + payload
    )
    deadline = time.monotonic() + timeout
    observed = bytearray()
    response_headers_seen = False
    marker_seen = marker_bytes is None
    sock: Optional[socket.socket] = None
    try:
        sock = socket.create_connection(("127.0.0.1", shim.port), timeout=timeout)
        sock.settimeout(min(0.25, timeout))
        sock.sendall(request_bytes)
        if close_after_event is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not close_after_event.wait(remaining):
                raise TimeoutError(
                    "raw disconnect close gate was not observed before deadline"
                )
        if marker_bytes is not None:
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                sock.settimeout(min(0.25, max(remaining, 0.001)))
                remaining_capacity = max_observed_bytes - len(observed)
                if remaining_capacity <= 0:
                    raise AssertionError(
                        "raw disconnect response reached observation cap before marker"
                    )
                try:
                    chunk = sock.recv(min(4096, remaining_capacity))
                except socket.timeout:
                    continue
                if not chunk:
                    break
                observed.extend(chunk)
                if len(observed) > max_observed_bytes:
                    raise AssertionError("raw disconnect response exceeded observation cap")
                response_headers_seen = b"\r\n\r\n" in observed
                marker_seen = marker_bytes in observed
                if response_headers_seen and marker_seen:
                    break
            if not response_headers_seen or not marker_seen:
                raise TimeoutError(
                    "raw disconnect did not observe required downstream headers/marker "
                    f"within {timeout:.2f}s: headers={response_headers_seen} "
                    f"marker={marker_seen} bytes={len(observed)}"
                )
        return RawDisconnectMetadata(
            request_bytes_sent=len(request_bytes),
            response_headers_seen=response_headers_seen,
            marker_seen=marker_seen,
            bytes_observed=len(observed),
        )
    finally:
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()


def outer_cancel_after_stream_enter_report() -> dict[str, Any]:
    """Exercise production stream ownership at the successful-enter/cancel seam."""

    import asyncio
    import importlib.util

    async def exercise() -> dict[str, Any]:
        module_name = f"provider_shim_cancel_probe_{uuid.uuid4().hex}"
        spec = importlib.util.spec_from_file_location(module_name, PRODUCTION_SHIM)
        if spec is None or spec.loader is None:
            raise RuntimeError("could not load production shim for ownership probe")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original_client = module._client
        exit_count = 0
        peer_closed = asyncio.Event()
        downstream_terminal_events: list[str] = []

        class ProbeResponse:
            status_code = 200

        class ProbeStreamContext:
            async def __aenter__(self) -> ProbeResponse:
                outer_task = asyncio.current_task()
                if outer_task is None:
                    raise RuntimeError("ownership probe has no outer request task")
                outer_task.cancel("cancel-after-successful-stream-enter")
                return ProbeResponse()

            async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
                nonlocal exit_count
                exit_count += 1
                peer_closed.set()

        class ProbeClient:
            def stream(self, *args: Any, **kwargs: Any) -> ProbeStreamContext:
                return ProbeStreamContext()

        module._client = ProbeClient()
        disconnect_event = asyncio.Event()

        async def request_flow() -> None:
            try:
                await module._open_backend_stream(
                    "http://127.0.0.1:1/responses",
                    {"Authorization": "Bearer FABRICATED_TEST_ONLY"},
                    {"stream": True},
                    disconnect_event,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                downstream_terminal_events.append("error")
            else:
                downstream_terminal_events.append("success")

        request_task = asyncio.create_task(request_flow(), name="outer-cancel-request")
        cancellation_message = None
        try:
            await request_task
        except asyncio.CancelledError as cancellation:
            cancellation_message = cancellation.args[0] if cancellation.args else None
        await asyncio.sleep(0)
        pending = [
            task
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task() and not task.done()
        ]
        await original_client.aclose()
        return {
            "request_cancelled": request_task.cancelled(),
            "cancellation_message": cancellation_message,
            "context_exit_count": exit_count,
            "peer_closed": peer_closed.is_set(),
            "downstream_terminal_events": list(downstream_terminal_events),
            "pending_task_count": len(pending),
        }

    return asyncio.run(exercise())


def parse_typed_sse(payload: bytes | str) -> list[TypedSSEFrame]:
    """Parse ordered SSE frames without deduplicating repeated event/data pairs."""

    text = payload.decode("utf-8", "replace") if isinstance(payload, bytes) else payload
    frames: list[TypedSSEFrame] = []
    event_name: Optional[str] = None
    data_lines: list[str] = []

    def flush() -> None:
        nonlocal event_name, data_lines
        if event_name is None and not data_lines:
            return
        raw_data = "\n".join(data_lines)
        if raw_data == "[DONE]":
            decoded: Any = "[DONE]"
        else:
            try:
                decoded = json.loads(raw_data)
            except ValueError:
                decoded = raw_data
        frames.append(TypedSSEFrame(event=event_name, data=decoded, raw_data=raw_data))
        event_name = None
        data_lines = []

    for raw_line in text.splitlines():
        if raw_line == "":
            flush()
            continue
        if raw_line.startswith(":"):
            continue
        field_name, separator, value = raw_line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]
        if field_name == "event":
            event_name = value
        elif field_name == "data":
            data_lines.append(value)
    flush()
    return frames


def event_dicts(frames: Iterable[TypedSSEFrame]) -> list[dict[str, Any]]:
    return [frame.data for frame in frames if isinstance(frame.data, dict)]


def thinking_delta_values(frames: Iterable[TypedSSEFrame]) -> list[str]:
    values = []
    for event in event_dicts(frames):
        delta = event.get("delta") or {}
        if event.get("type") == "content_block_delta" and delta.get("type") == "thinking_delta":
            values.append(delta.get("thinking", ""))
    return values


def text_delta_values(frames: Iterable[TypedSSEFrame]) -> list[str]:
    values = []
    for event in event_dicts(frames):
        delta = event.get("delta") or {}
        if event.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
            values.append(delta.get("text", ""))
    return values


def block_starts(frames: Iterable[TypedSSEFrame]) -> list[dict[str, Any]]:
    return [event for event in event_dicts(frames) if event.get("type") == "content_block_start"]


def lifecycle_report(frames: Iterable[TypedSSEFrame]) -> LifecycleReport:
    events = event_dicts(frames)
    event_types = [event.get("type") for event in events]
    if event_types.count("message_start") != 1:
        raise AssertionError(
            f"success stream must contain exactly one message_start: {event_types!r}"
        )
    if not events or events[0].get("type") != "message_start":
        raise AssertionError("message_start is not the first Anthropic event")
    if event_types.count("message_delta") != 1:
        raise AssertionError(
            f"success stream must contain exactly one message_delta: {event_types!r}"
        )
    if event_types.count("message_stop") != 1:
        raise AssertionError(
            f"success stream must contain exactly one message_stop: {event_types!r}"
        )
    message_delta_at = event_types.index("message_delta")
    message_stop_at = event_types.index("message_stop")
    if message_stop_at != len(events) - 1:
        raise AssertionError("message_stop is not the final Anthropic event")
    if message_delta_at >= message_stop_at:
        raise AssertionError("message_delta does not precede message_stop")
    if "error" in event_types:
        raise AssertionError("terminal error appears in success stream")

    open_indexes: set[int] = set()
    starts: list[tuple[int, str]] = []
    stops: list[int] = []
    seen_indexes: set[int] = set()
    last_started_index = -1
    for position, event in enumerate(events):
        event_type = event.get("type")
        index = event.get("index")
        if (
            position > message_delta_at
            and event_type in {
                "content_block_start",
                "content_block_delta",
                "content_block_stop",
            }
        ):
            raise AssertionError(
                f"content block event follows terminal message_delta: {event!r}"
            )
        if event_type == "message_delta" and open_indexes:
            raise AssertionError(
                f"message_delta arrived with open blocks: {open_indexes!r}"
            )
        if event_type == "content_block_start":
            if not isinstance(index, int) or isinstance(index, bool):
                raise AssertionError(f"content block start has malformed index: {index!r}")
            if open_indexes:
                raise AssertionError(f"content blocks overlap before index {index}: {open_indexes!r}")
            if index in seen_indexes:
                raise AssertionError(f"content block index was reused: {index}")
            if index <= last_started_index:
                raise AssertionError(
                    f"content block indexes are not monotonic: {last_started_index} then {index}"
                )
            kind = (event.get("content_block") or {}).get("type", "")
            starts.append((index, kind))
            seen_indexes.add(index)
            open_indexes.add(index)
            last_started_index = index
        elif event_type == "content_block_delta":
            if index not in open_indexes:
                raise AssertionError(f"delta targeted a non-open content block: {index!r}")
        elif event_type == "content_block_stop":
            if index not in open_indexes:
                raise AssertionError(f"stop targeted a non-open content block: {index!r}")
            open_indexes.remove(index)
            stops.append(index)
    if open_indexes:
        raise AssertionError(f"content blocks remained open: {open_indexes!r}")
    if len(starts) != len(stops):
        raise AssertionError(f"start/stop count differs: starts={starts!r} stops={stops!r}")
    return LifecycleReport(starts=starts, stops=stops, open_at_end=set(open_indexes))


def failure_lifecycle_report(
    frames: Iterable[TypedSSEFrame],
) -> FailureLifecycleReport:
    """Validate the terminal-error contract independently of success lifecycle checks."""

    typed_frames = list(frames)
    semantic_frames = [frame for frame in typed_frames if isinstance(frame.data, dict)]
    if not semantic_frames:
        raise AssertionError("failure stream contains no semantic events")
    events = [frame.data for frame in semantic_frames]
    event_types = [event.get("type") for event in events]
    if event_types.count("message_start") != 1:
        raise AssertionError(
            f"failure stream must contain exactly one message_start: {event_types!r}"
        )
    if events[0].get("type") != "message_start":
        raise AssertionError("message_start is not the first failure-stream event")
    if event_types.count("error") != 1:
        raise AssertionError(
            f"failure stream must contain exactly one terminal error: {event_types!r}"
        )
    if event_types.count("message_delta") != 0 or event_types.count("message_stop") != 0:
        raise AssertionError(
            f"success terminal events appear in failure stream: {event_types!r}"
        )
    final_frame = semantic_frames[-1]
    final_event = final_frame.data
    if final_frame.event != "error" or final_event.get("type") != "error":
        raise AssertionError(
            f"final semantic event is not Anthropic event:error: "
            f"frame={final_frame.event!r} data={final_event!r}"
        )
    error = final_event.get("error") or {}
    if error.get("type") != "api_error":
        raise AssertionError(f"terminal error type is not api_error: {error!r}")
    if not isinstance(error.get("message"), str) or not error.get("message"):
        raise AssertionError(f"terminal api_error has no message: {error!r}")

    open_indexes: set[int] = set()
    seen_indexes: set[int] = set()
    starts: list[tuple[int, str]] = []
    stops: list[int] = []
    stop_counts: dict[int, int] = {}
    error_seen = False
    last_started_index = -1
    for event in events:
        event_type = event.get("type")
        index = event.get("index")
        if error_seen:
            raise AssertionError(f"semantic event follows terminal error: {event!r}")
        if event_type in {"message_delta", "message_stop"}:
            raise AssertionError(f"success terminal event appears in failure stream: {event_type}")
        if event_type == "content_block_start":
            if not isinstance(index, int) or isinstance(index, bool):
                raise AssertionError(f"content block start has malformed index: {index!r}")
            if open_indexes:
                raise AssertionError(
                    f"content blocks overlap before failure at index {index}: {open_indexes!r}"
                )
            if index in seen_indexes:
                raise AssertionError(f"content block index was reused: {index}")
            if index <= last_started_index:
                raise AssertionError(
                    f"content block indexes are not monotonic: {last_started_index} then {index}"
                )
            kind = (event.get("content_block") or {}).get("type", "")
            starts.append((index, kind))
            seen_indexes.add(index)
            open_indexes.add(index)
            last_started_index = index
        elif event_type == "content_block_delta":
            if index not in open_indexes:
                raise AssertionError(f"delta targeted a non-open content block: {index!r}")
        elif event_type == "content_block_stop":
            stop_counts[index] = stop_counts.get(index, 0) + 1
            if index not in open_indexes:
                raise AssertionError(f"stop targeted a non-open content block: {index!r}")
            open_indexes.remove(index)
            stops.append(index)
        elif event_type == "error":
            error_seen = True

    if open_indexes:
        raise AssertionError(f"content blocks remained open at terminal error: {open_indexes!r}")
    if len(starts) != len(stops):
        raise AssertionError(f"start/stop count differs: starts={starts!r} stops={stops!r}")
    for index, _kind in starts:
        if stop_counts.get(index) != 1:
            raise AssertionError(
                f"opened block did not receive exactly one stop: index={index} "
                f"count={stop_counts.get(index, 0)}"
            )
    return FailureLifecycleReport(
        starts=starts,
        stops=stops,
        error=dict(error),
        open_at_end=set(open_indexes),
    )


def extract_nonstream_thinking(message: dict[str, Any]) -> str:
    blocks = [block for block in message.get("content", []) if block.get("type") == "thinking"]
    if len(blocks) != 1:
        raise AssertionError(f"expected exactly one non-stream thinking block, got {blocks!r}")
    return blocks[0].get("thinking", "")


def normalized_non_reasoning_projection(frames: Iterable[TypedSSEFrame]) -> list[dict[str, Any]]:
    """Remove thinking payload bytes and normalize the shim-generated message id."""

    projected: list[dict[str, Any]] = []
    for original in event_dicts(frames):
        event = json.loads(json.dumps(original))
        delta = event.get("delta") or {}
        if event.get("type") == "content_block_delta" and delta.get("type") == "thinking_delta":
            continue
        if event.get("type") == "message_start":
            message = event.get("message") or {}
            if "id" in message:
                message["id"] = "<dynamic-message-id>"
        projected.append(event)
    return projected


READ_TOOL = {
    "name": "Read",
    "description": "Read a file.",
    "input_schema": {
        "type": "object",
        "properties": {"file_path": {"type": "string"}},
        "required": ["file_path"],
    },
}
