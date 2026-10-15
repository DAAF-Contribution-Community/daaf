"""Shim v1.4.12: shim.log records why a failure happened.

Live 2026-10-15 (UM-GPT gateway, openai lane): two streaming web-search requests
failed with ``outcome=error failure_phase=upstream_stream backend_type=-
backend_code=-``. The reason went to Claude Code but not to the log, because the
stream failure finalizer recorded only the error type. The backend_error lifecycle
line now carries ``failure_reason``: the shim's own short reason (a local constant,
a ``_ProtocolError`` literal or a classifier fixed message), or a fixed category
with an exception class where the source text is not guaranteed shim-authored.
Backend prose never reaches it (v1.2.11 no-prose rule).

1. unit: the field is scrubbed, capped at 160 characters and kept to one token;
   the first recorded reason wins; no reason logs "-".
2. streaming search failure raised by the collector (an incomplete search
   inventory) logs the _ProtocolError literal, on both lanes.
3. streaming in-band ``response.failed`` logs the classifier fixed message.
4. non-stream failures log it: chatgpt in-band ``response.failed``, a chatgpt
   stream with no terminal response, and a search non-stream protocol failure
   (which wrote no backend_error line before 1.4.12).
5. privacy: backend errors carrying sentinel prose on every path never put the
   prose in the log or the client body; the logged reason is a known fixed message.
6. (review fix 1) static: every _ProtocolError/_ToolWhitespaceError message in the
   shim source is a literal (or one of three audited names), and every
   _require_protocol_string field name is a literal, so the "literal" premise
   behind logging _ProtocolError text cannot silently rot.
7. (review fix 1) category paths, in-process with a sentinel in the exception text:
   the ChatGPT non-stream accumulator ValueError, the search non-stream
   ValueError/httpx branch, the streaming post-start error line (TypeError) and the
   pre-content token-refresh RuntimeError log fixed categories, never the text;
   the accumulator does not record after a client disconnect.

Client-visible bytes are unchanged; existing modules pin them. Provider-free: a mock
Responses backend on loopback (or the controlled in-process ASGI probe), fabricated
values only.
"""

from __future__ import annotations

import ast
import asyncio
import copy
import importlib.util
import json
import unittest
import urllib.parse
import uuid

from . import _native_search_fixtures as fx
from ._loopback_harness import (
    PRODUCTION_SHIM,
    USAGE,
    MockResponsesServer,
    RealShim,
    Scenario,
    _purge_in_process_reasoning_cache_seam,
    backend_status_scenario,
    controlled_asgi_probe,
    failure_lifecycle_report,
    lifecycle_for_response,
    parse_typed_sse,
    structured_error_scenario,
)

# Fabricated backend prose. Neither the log nor the client may ever contain it.
PROSE_SENTINEL = "FABRICATED_BACKEND_PROSE_V1412_R8"

REASON_MAXLEN = 160
CONTEXT_MESSAGE = "Prompt is too long (backend context length exceeded)"
INVENTORY_MESSAGE = "search inventory missing completed items or index coverage"
NO_TERMINAL_MESSAGE = "backend stream ended without a terminal response"

# Every reason the privacy cases below may log: classifier fixed messages only.
FIXED_CLASSIFIER_MESSAGES = {
    CONTEXT_MESSAGE,
    "backend server error",
    "backend request failed",
    "backend rejected the request",
}


def _ordinary_request(stream=False):
    return json.dumps({
        "model": "gpt-fixture", "max_tokens": 256, "stream": stream,
        "messages": [{"role": "user", "content": "Exercise the fixture."}],
    }, separators=(",", ":")).encode("utf-8")


def _search_request(stream):
    return json.dumps(fx.search_request(stream)).encode("utf-8")


def _incomplete_inventory_scenario():
    # A completed web_search_call at index 0, then a message ADDED at index 1 that is
    # never completed, then response.completed with an empty output. The collector
    # finds index 1 without a completed item and raises INVENTORY_MESSAGE.
    scenario = fx.search_scenario()
    search_item, message_item = copy.deepcopy(fx.RAW_ITEMS)
    message_item["status"] = "in_progress"
    terminal = copy.deepcopy(scenario.stream_events[-1])
    scenario.stream_events = [
        {"type": "response.output_item.done", "output_index": 0, "item": search_item},
        {"type": "response.output_item.added", "output_index": 1, "item": message_item},
        terminal,
    ]
    return scenario


class FailureReasonUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _purge_in_process_reasoning_cache_seam()
        name = "provider_shim_v1412_reason_%s" % uuid.uuid4().hex
        spec = importlib.util.spec_from_file_location(name, PRODUCTION_SHIM)
        cls.shim = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.shim)

    @classmethod
    def tearDownClass(cls):
        asyncio.run(cls.shim._client.aclose())

    def _record(self, *calls):
        # Run _record_backend_error calls inside one fresh request state and return
        # (state, captured log messages).
        state = self.shim._RequestLifecycleState()
        token = self.shim._REQUEST_STATE.set(state)
        try:
            with self.assertLogs(self.shim.log, level="INFO") as captured:
                for kwargs in calls:
                    self.shim._record_backend_error(**kwargs)
        finally:
            self.shim._REQUEST_STATE.reset(token)
        return state, [record.getMessage() for record in captured.records]

    def _reason_token(self, messages):
        lines = [m for m in messages if m.startswith("event=backend_error ")]
        self.assertEqual(len(lines), 1, messages)
        tokens = [t for t in lines[0].split(" ") if t.startswith("failure_reason=")]
        self.assertEqual(len(tokens), 1, lines[0])
        return tokens[0][len("failure_reason="):]

    def test_reason_is_scrubbed_bounded_and_one_token(self):
        hostile = ("line one\r\nevent=terminal outcome=success " + "x" * 400
                   + " sk-FABRICATEDKEY1234567890")
        state, messages = self._record({"error_type": "api_error",
                                        "failure_reason": hostile})
        self.assertLessEqual(len(state.failure_reason), REASON_MAXLEN)
        self.assertNotRegex(state.failure_reason, r"[\x00-\x1f\x7f]")
        raw = self._reason_token(messages)
        decoded = urllib.parse.unquote(raw)
        self.assertEqual(decoded, state.failure_reason)
        self.assertLessEqual(len(decoded), REASON_MAXLEN)
        # One token: no whitespace and no forged second field in the encoded value.
        self.assertNotRegex(raw, r"\s")
        self.assertNotIn("=", raw)
        self.assertTrue(decoded.startswith("line one event=terminal"))

    def test_credential_shapes_are_redacted_before_the_cap(self):
        state, _messages = self._record({
            "error_type": "api_error",
            "failure_reason": "fixture Bearer abcdefghijklmnop sk-FABRICATEDKEY1234567890"})
        self.assertNotIn("abcdefghijklmnop", state.failure_reason)
        self.assertNotIn("FABRICATEDKEY", state.failure_reason)
        self.assertIn("[REDACTED]", state.failure_reason)

    def test_first_reason_wins_and_absent_reason_is_dash(self):
        state, messages = self._record(
            {"error_type": "api_error", "failure_reason": "first fixture cause"},
            {"error_type": "invalid_request_error", "failure_reason": "second fixture cause"})
        self.assertEqual(state.failure_reason, "first fixture cause")
        self.assertEqual(urllib.parse.unquote(self._reason_token(messages)),
                         "first fixture cause")
        state, messages = self._record({"error_type": "api_error"})
        self.assertEqual(state.failure_reason, "-")
        self.assertEqual(self._reason_token(messages), "-")


class FailureReasonLoopbackTests(unittest.TestCase):
    maxDiff = 8000

    def _event_line(self, lines, event):
        matches = [line for line in lines if line.event == event]
        self.assertEqual(len(matches), 1, (event, [line.raw for line in lines]))
        return matches[0]

    def _logged_reason(self, shim, result, marker):
        lines = lifecycle_for_response(shim, result)
        backend_error = self._event_line(lines, "backend_error")
        raw = backend_error.fields["failure_reason"]
        reason = urllib.parse.unquote(raw)
        self.assertLessEqual(len(reason), REASON_MAXLEN, (marker, backend_error.raw))
        self.assertNotRegex(reason, r"[\x00-\x1f\x7f]", marker)
        return reason, backend_error, self._event_line(lines, "terminal")

    # --- 2: streaming search failure raised by the collector ---

    def test_streaming_search_protocol_failure_logs_the_literal(self):
        for lane in ("chatgpt", "openai"):
            marker = "SEARCH_STREAM_INVENTORY_" + lane
            with self.subTest(lane=lane):
                with MockResponsesServer(_incomplete_inventory_scenario()) as backend:
                    with RealShim(backend, lane) as shim:
                        result = shim.post_raw_messages(_search_request(True))
                        self.assertEqual(result.status, 200, (marker, result.text))
                        failure = failure_lifecycle_report(parse_typed_sse(result.body))
                        self.assertEqual(failure.error["message"], INVENTORY_MESSAGE, marker)
                        reason, backend_error, terminal = self._logged_reason(
                            shim, result, marker)
                        # The live 2026-10-15 shape, now with its reason.
                        self.assertEqual(reason, INVENTORY_MESSAGE, marker)
                        self.assertEqual(backend_error.fields["backend_type"], "-", marker)
                        self.assertEqual(backend_error.fields["anthropic_type"], "api_error")
                        self.assertEqual(backend_error.fields["failure_phase"],
                                         "upstream_stream", marker)
                        self.assertEqual(terminal.fields["outcome"], "error", marker)
                        backend.assert_request_counts(responses=1)
                        shim.assert_offline_contract()

    # --- 3: streaming in-band response.failed ---

    def test_streaming_inband_failure_logs_the_classifier_message(self):
        cases = (
            ({"type": "invalid_request_error", "code": "context_length_exceeded",
              "message": PROSE_SENTINEL}, "invalid_request_error", CONTEXT_MESSAGE),
            ({"code": "server_error", "message": PROSE_SENTINEL},
             "api_error", "backend server error"),
        )
        for lane in ("chatgpt", "openai"):
            for payload, error_type, message in cases:
                marker = "STREAM_INBAND_%s_%s" % (lane, payload["code"])
                with self.subTest(lane=lane, code=payload["code"]):
                    scenario = structured_error_scenario(
                        "v1412-stream-" + payload["code"], "response.failed", payload)
                    with MockResponsesServer(scenario) as backend:
                        with RealShim(backend, lane) as shim:
                            result = shim.post_raw_messages(_ordinary_request(stream=True))
                            self.assertEqual(result.status, 200, (marker, result.text))
                            failure = failure_lifecycle_report(
                                parse_typed_sse(result.body),
                                expected_error_type=error_type)
                            self.assertEqual(failure.error["message"], message, marker)
                            reason, backend_error, _terminal = self._logged_reason(
                                shim, result, marker)
                            self.assertEqual(reason, message, marker)
                            self.assertEqual(backend_error.fields["backend_code"],
                                             payload["code"], marker)
                            self.assertNotIn(PROSE_SENTINEL, shim.captured_stderr(), marker)

    # --- 4: non-stream failures ---

    def test_nonstream_inband_failure_logs_the_classifier_message(self):
        payload = {"type": "invalid_request_error", "code": "context_length_exceeded",
                   "message": PROSE_SENTINEL}
        for event_type in ("response.failed", "error"):
            marker = "NONSTREAM_INBAND_" + event_type
            with self.subTest(event=event_type):
                scenario = structured_error_scenario(
                    "v1412-nonstream-" + event_type.replace(".", "-"), event_type, payload)
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, "chatgpt") as shim:
                        result = shim.post_raw_messages(_ordinary_request())
                        self.assertEqual(result.status, 400, (marker, result.text))
                        self.assertEqual(result.json()["error"]["message"], CONTEXT_MESSAGE)
                        reason, _backend_error, _terminal = self._logged_reason(
                            shim, result, marker)
                        self.assertEqual(reason, CONTEXT_MESSAGE, marker)
                        self.assertNotIn(PROSE_SENTINEL, shim.captured_stderr(), marker)

    def test_nonstream_stream_without_terminal_logs_the_constant(self):
        # ChatGPT non-stream adapter: the upstream SSE ends with [DONE] and no terminal
        # event. The fallback record now carries the client's constant.
        scenario = Scenario(
            name="v1412-no-terminal",
            stream_events=[{"type": "response.created",
                            "response": {"id": "resp_v1412_nt", "status": "in_progress"}}],
            nonstream_response={"id": "resp_v1412_nt_ns", "status": "completed",
                                "output": [], "usage": dict(USAGE)},
        )
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_raw_messages(_ordinary_request())
                self.assertEqual(result.status, 502, result.text)
                error = result.json()["error"]
                self.assertEqual(error["type"], "api_error")
                self.assertEqual(error["message"], NO_TERMINAL_MESSAGE)
                reason, backend_error, _terminal = self._logged_reason(
                    shim, result, "NO_TERMINAL")
                self.assertEqual(reason, NO_TERMINAL_MESSAGE)
                self.assertEqual(backend_error.fields["failure_phase"], "upstream_stream")

    def test_nonstream_search_protocol_failure_now_writes_a_backend_error(self):
        # Before 1.4.12 this branch wrote no backend_error line at all.
        with MockResponsesServer(_incomplete_inventory_scenario()) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_raw_messages(_search_request(False))
                self.assertEqual(result.status, 502, result.text)
                error = result.json()["error"]
                self.assertEqual(error["type"], "api_error")
                self.assertEqual(error["message"], INVENTORY_MESSAGE)
                reason, backend_error, terminal = self._logged_reason(
                    shim, result, "SEARCH_NONSTREAM_INVENTORY")
                self.assertEqual(reason, INVENTORY_MESSAGE)
                self.assertEqual(backend_error.fields["anthropic_type"], "api_error")
                self.assertEqual(terminal.fields["outcome"], "error")
                backend.assert_request_counts(responses=1)

    # --- 5: privacy ---

    def test_backend_prose_never_reaches_the_log_or_the_reason(self):
        # Mirrors test_v1211_reflected_backend_prose_never_reaches_logs_or_client_errors
        # (test_stream_hardening.py) across the paths that now log a reason.
        prose = "backend reflected request prose: " + PROSE_SENTINEL
        status_body = json.dumps(
            {"error": {"type": "server_error", "code": "fixture_unknown_code",
                       "message": prose}}, separators=(",", ":")).encode("utf-8")
        inband = {"type": "server_error", "code": "context_length_exceeded",
                  "message": prose}
        cases = (
            # (name, lane, scenario factory, request bytes, client status)
            ("stream-prestream-500", "chatgpt",
             lambda: backend_status_scenario("v1412-p500", 500, error_body=status_body),
             _ordinary_request(stream=True), 200),
            ("stream-inband-failed", "openai",
             lambda: structured_error_scenario("v1412-pf", "response.failed", inband),
             _ordinary_request(stream=True), 200),
            ("nonstream-chatgpt-inband", "chatgpt",
             lambda: structured_error_scenario("v1412-pn", "error", inband),
             _ordinary_request(), 400),
            ("nonstream-openai-400", "openai",
             lambda: backend_status_scenario("v1412-p400", 400, error_body=status_body),
             _ordinary_request(), 400),
            ("search-nonstream-inband", "chatgpt",
             lambda: structured_error_scenario("v1412-ps", "response.failed", inband),
             _search_request(False), 400),
            ("search-stream-inband", "chatgpt",
             lambda: structured_error_scenario("v1412-pss", "response.failed", inband),
             _search_request(True), 200),
        )
        for name, lane, factory, request_bytes, client_status in cases:
            with self.subTest(path=name):
                with MockResponsesServer(factory()) as backend:
                    with RealShim(backend, lane) as shim:
                        result = shim.post_raw_messages(request_bytes)
                        self.assertEqual(result.status, client_status, (name, result.text))
                        reason, _backend_error, _terminal = self._logged_reason(
                            shim, result, name)
                        self.assertIn(reason, FIXED_CLASSIFIER_MESSAGES, name)
                        logs = shim.captured_stderr()
                        self.assertNotIn(PROSE_SENTINEL, logs, (name, "stderr"))
                        self.assertNotIn("reflected request prose", logs, (name, "stderr"))
                        self.assertNotIn(PROSE_SENTINEL, result.text, (name, "client"))
                        shim.assert_offline_contract()


# --- 6: static guard on the "_ProtocolError text is shim-authored" premise ---

# Names allowed as a whole _ProtocolError argument, each tied to the one function
# where it was audited for 1.4.12 (anything else must be a literal).
_ALLOWED_MESSAGE_NAMES = {
    # _SearchCollector.event: the classifier's fixed message.
    "message": "event",
    # _accumulate_terminal_response: assigned only string constants.
    "recovery_error": "_accumulate_terminal_response",
}
# Names allowed as the right operand of a literal "%" format, per function.
_ALLOWED_FORMAT_NAMES = {
    # _require_protocol_string: every caller passes a literal field name (checked).
    "field": "_require_protocol_string",
}
_PROTOCOL_ERROR_CLASSES = {"_ProtocolError", "_ToolWhitespaceError"}


def _is_str_literal(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


class _ProtocolMessageAudit(ast.NodeVisitor):
    """Collect every violation of the literal-message rule with its line number."""

    def __init__(self):
        self.functions = []
        self.violations = []
        self.protocol_calls = 0
        self.field_calls = 0
        self.assignments = {}  # (function, name) -> list of value nodes

    def _visit_function(self, node):
        self.functions.append(node.name)
        self.generic_visit(node)
        self.functions.pop()

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def visit_Assign(self, node):
        function = self.functions[-1] if self.functions else "<module>"
        for target in node.targets:
            names = ([target] if isinstance(target, ast.Name)
                     else [t for t in getattr(target, "elts", []) if isinstance(t, ast.Name)])
            for name in names:
                self.assignments.setdefault((function, name.id), []).append(
                    (node.lineno, target, node.value))
        self.generic_visit(node)

    def _allowed_format_operand(self, node, function):
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return True
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "len"):
            return True
        return (isinstance(node, ast.Name)
                and _ALLOWED_FORMAT_NAMES.get(node.id) == function)

    def _allowed_message(self, node, function):
        if _is_str_literal(node):
            return True
        if isinstance(node, ast.Name):
            return _ALLOWED_MESSAGE_NAMES.get(node.id) == function
        if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod)
                and _is_str_literal(node.left)):
            operands = node.right.elts if isinstance(node.right, ast.Tuple) else [node.right]
            return all(self._allowed_format_operand(o, function) for o in operands)
        return False

    def visit_Call(self, node):
        function = self.functions[-1] if self.functions else "<module>"
        name = node.func.id if isinstance(node.func, ast.Name) else None
        if name in _PROTOCOL_ERROR_CLASSES:
            self.protocol_calls += 1
            args = list(node.args) + [kw.value for kw in node.keywords]
            for arg in args:
                if not self._allowed_message(arg, function):
                    self.violations.append(
                        "line %d (in %s): %s(%s) is not a literal or audited name"
                        % (node.lineno, function, name, ast.unparse(arg)))
        if name == "_require_protocol_string":
            self.field_calls += 1
            field = node.args[1] if len(node.args) > 1 else next(
                (kw.value for kw in node.keywords if kw.arg == "field"), None)
            if field is None or not _is_str_literal(field):
                self.violations.append(
                    "line %d (in %s): _require_protocol_string field %s is not a literal"
                    % (node.lineno, function,
                       ast.unparse(field) if field is not None else "<missing>"))
        self.generic_visit(node)


class ProtocolMessageSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PRODUCTION_SHIM, encoding="utf-8") as handle:
            source = handle.read()
        cls.audit = _ProtocolMessageAudit()
        cls.audit.visit(ast.parse(source, filename=str(PRODUCTION_SHIM)))

    def test_every_protocol_error_message_is_literal_or_audited(self):
        # A failure names the offending line; fix the raise or audit and allowlist it.
        self.assertEqual(self.audit.violations, [], "\n".join(self.audit.violations))
        # Guard against a parse that silently visited nothing.
        self.assertGreater(self.audit.protocol_calls, 80)
        self.assertGreater(self.audit.field_calls, 20)

    def test_allowlisted_names_have_audited_sources(self):
        # recovery_error: only string constants (or None) are ever assigned.
        values = self.audit.assignments.get(("_accumulate_terminal_response", "recovery_error"))
        self.assertTrue(values)
        for lineno, _target, value in values:
            self.assertTrue(
                _is_str_literal(value) or (isinstance(value, ast.Constant) and value.value is None),
                "line %d: recovery_error = %s" % (lineno, ast.unparse(value)))
        # message in _SearchCollector.event: only the classifier's tuple result.
        values = self.audit.assignments.get(("event", "message"))
        self.assertTrue(values)
        for lineno, target, value in values:
            self.assertIsInstance(target, ast.Tuple, "line %d" % lineno)
            self.assertTrue(
                isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                and value.func.id == "_normalize_backend_error",
                "line %d: message = %s" % (lineno, ast.unparse(value)))


# --- 7: category paths with a sentinel in the exception text (in-process) ---

EXCEPTION_SENTINEL = "FABRICATED_EXCEPTION_TEXT_V1412_Q5"


def _lines(report, event):
    return [line for line in report.lifecycle if line.event == event]


class CategoryPathTests(unittest.TestCase):
    maxDiff = 8000

    def _reason(self, report):
        backend_errors = _lines(report, "backend_error")
        self.assertEqual(len(backend_errors), 1, report.logs)
        return urllib.parse.unquote(backend_errors[0].fields["failure_reason"])

    def _assert_sentinel_absent(self, report, name):
        self.assertNotIn(EXCEPTION_SENTINEL, report.logs, name)

    def test_accumulator_value_error_logs_a_category(self):
        def configure(module):
            async def raising_reader(*_args, **_kwargs):
                raise ValueError(EXCEPTION_SENTINEL)
                yield b""  # pragma: no cover - makes this an async generator
            module._iter_bounded_sse_data = raising_reader

        report = controlled_asgi_probe(stream=False, backend_mode="chatgpt",
                                       configure_module=configure)
        self.assertIsNone(report.raised)
        self.assertEqual(report.messages[0]["status"], 502)
        self.assertEqual(self._reason(report), "backend SSE framing error (ValueError)")
        self._assert_sentinel_absent(report, "accumulator")

    def test_search_nonstream_value_and_transport_errors_log_a_category(self):
        search_body = json.dumps(fx.search_request(False)).encode("utf-8")
        for label, make_error, category in (
            ("ValueError", lambda module: ValueError(EXCEPTION_SENTINEL), "ValueError"),
            ("ReadError", lambda module: module.httpx.ReadError(EXCEPTION_SENTINEL),
             "ReadError"),
        ):
            with self.subTest(error=label):
                def configure(module, make_error=make_error):
                    async def raising_collector(*_args, **_kwargs):
                        raise make_error(module)
                    module._collect_search_response = raising_collector

                report = controlled_asgi_probe(stream=False, backend_mode="chatgpt",
                                               raw_request_body=search_body,
                                               configure_module=configure)
                self.assertIsNone(report.raised)
                self.assertEqual(report.messages[0]["status"], 502)
                body = json.loads(b"".join(m.get("body", b"") for m in report.messages))
                self.assertEqual(body["error"]["message"],
                                 "backend search transport or framing error")
                self.assertEqual(
                    self._reason(report),
                    "backend search transport or framing error (%s)" % category)
                self._assert_sentinel_absent(report, label)

    def test_streaming_post_start_error_line_logs_the_constant_kind(self):
        # S1: the "stream failure after response start" line logs the constant
        # failure kind for a non-_ProtocolError exception, never its text.
        def configure(module):
            def raising_validator(*_args, **_kwargs):
                raise TypeError(EXCEPTION_SENTINEL)
            module._validate_stream_event_fields = raising_validator

        report = controlled_asgi_probe(stream=True, backend_mode="openai",
                                       configure_module=configure)
        self.assertIsNone(report.raised)
        self.assertIn("stream failure after response start: TypeError: "
                      "backend stream translation error", report.logs)
        self.assertEqual(self._reason(report), "backend stream translation error")
        self._assert_sentinel_absent(report, "post-start")

    def test_precontent_token_refresh_runtime_error_logs_a_category(self):
        # The lifecycle record logs the fixed category. The adjacent human-readable
        # "chatgpt stream lazy-401 refresh failed: %s" line (pre-1.4.12, unchanged)
        # still prints the RuntimeError text, which in production is the shim's own
        # re-login instruction; so only the lifecycle lines are checked here.
        def configure(module):
            async def raising_opener(*_args, **_kwargs):
                raise RuntimeError(EXCEPTION_SENTINEL)
            module._open_backend_stream = raising_opener

        report = controlled_asgi_probe(stream=True, backend_mode="chatgpt",
                                       configure_module=configure)
        self.assertIsNone(report.raised)
        self.assertEqual(self._reason(report),
                         "backend token refresh failed (RuntimeError)")
        for line in report.lifecycle:
            self.assertNotIn(EXCEPTION_SENTINEL, line.raw, line.event)

    def test_accumulator_does_not_record_after_a_disconnect(self):
        # NIT 1: with the client gone, the accumulator's category record is skipped,
        # so a disconnect outcome is not turned into error.
        _purge_in_process_reasoning_cache_seam()
        name = "provider_shim_v1412_nit1_%s" % uuid.uuid4().hex
        spec = importlib.util.spec_from_file_location(name, PRODUCTION_SHIM)
        shim = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(shim)

        async def raising_reader(*_args, **_kwargs):
            raise ValueError(EXCEPTION_SENTINEL)
            yield b""  # pragma: no cover - makes this an async generator

        shim._iter_bounded_sse_data = raising_reader
        for disconnected in (True, False):
            with self.subTest(disconnected=disconnected):
                state = shim._RequestLifecycleState()
                state.outcome = "disconnect" if disconnected else None
                event = asyncio.Event()
                if disconnected:
                    event.set()
                token = shim._REQUEST_STATE.set(state)
                try:
                    terminal, _message = asyncio.run(
                        shim._accumulate_terminal_response(object(), event))
                finally:
                    shim._REQUEST_STATE.reset(token)
                self.assertIsNone(terminal)
                self.assertEqual(state.backend_error_logged, not disconnected)
                self.assertEqual(state.outcome, "disconnect" if disconnected else "error")
        asyncio.run(shim._client.aclose())


if __name__ == "__main__":
    unittest.main()
