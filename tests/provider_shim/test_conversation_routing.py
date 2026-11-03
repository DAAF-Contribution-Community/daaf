"""Synthetic CLI identity contracts, not SDK/authentication/cache-isolation proof."""
import json
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock

from ._loopback_harness import (
    MockResponsesServer, RealShim, controlled_asgi_probe, heartbeat_text_scenario,
    lifecycle_for_response,
)


SESSION = "abcdefab-1234-4567-89ab-abcdefabcdef"
OTHER_SESSION = "22222222-2222-4222-8222-222222222222"
WORKER = "a0123456789abcdef"
OTHER_WORKER = "aFED-0123456789abcdef"
DEVICE = "synthetic-device-identifier"
ACCOUNT = "synthetic-account-identifier"


def identity(session=SESSION):
    return {"device_id": DEVICE, "account_uuid": ACCOUNT, "session_id": session}


def request_body(session=SESSION, *, marker="synthetic routing", stream=False):
    return {"model": "gpt-fixture", "max_tokens": 256, "stream": stream,
            "messages": [{"role": "user", "content": marker}],
            "metadata": {"user_id": json.dumps(identity(session))}}


def worker_route(session, worker):
    return str(uuid.uuid5(uuid.UUID(session), "daaf-claude-worker-v1:" + worker))


class ConversationRoutingTests(unittest.TestCase):
    def probe(self, *, body=None, headers=(), mode="chatgpt", refresh=False):
        auth = AsyncMock(side_effect=["SYNTHETIC_FIRST", "SYNTHETIC_REFRESHED"])
        def configure(module):
            # Only the token provider is replaced; real header builder and retry run.
            if refresh:
                module._get_access_token = auth
        report = controlled_asgi_probe(
            scenario=heartbeat_text_scenario(gap_s=0), stream=False, backend_mode=mode,
            raw_request_body=body if body is not None else json.dumps(request_body()).encode(),
            raw_scope_headers=list(headers), configure_module=configure,
            attempt_outcomes=[401, 200] if refresh else None)
        self.assertIsNone(report.raised)
        self.assertFalse(report.cancelled)
        self.assertEqual(report.messages[0]["status"], 200)
        self.assertEqual(report.pending_task_count, 0)
        self.assertEqual(report.upstream_calls, 2 if refresh else 1)
        self.assertEqual(len(report.outbound_headers), report.upstream_calls)
        for outgoing in report.outbound_headers:
            lowered = {key.lower(): value for key, value in outgoing.items()}
            self.assertNotIn("x-claude-code-agent-id", lowered)
            self.assertNotIn("x-claude-code-parent-agent-id", lowered)
            self.assertNotIn("thread-id", lowered)
            self.assertNotIn(DEVICE, str(outgoing))
            self.assertNotIn(ACCOUNT, str(outgoing))
            self.assertNotIn(WORKER, str(outgoing))
        for value in (SESSION, OTHER_SESSION, WORKER, OTHER_WORKER, DEVICE, ACCOUNT,
                      worker_route(SESSION, WORKER), worker_route(SESSION, OTHER_WORKER)):
            self.assertNotIn(value, report.logs)
        return report, auth

    def assert_route(self, expected, **kwargs):
        report, _ = self.probe(**kwargs)
        self.assertEqual(report.outbound_headers[0].get("session-id"), expected)
        return report

    def test_parent_uuid_is_canonical_lowercase(self):
        self.assert_route(SESSION, body=json.dumps(request_body(SESSION.upper())).encode())

    def test_distinct_workers_share_cli_but_not_route(self):
        routes = []
        for worker in (WORKER, OTHER_WORKER):
            report = self.assert_route(worker_route(SESSION, worker), headers=[(b"x-claude-code-agent-id", worker.encode())])
            routes.append(report.outbound_headers[0]["session-id"])
        self.assertEqual(len(set(routes + [SESSION])), 3)

    def test_same_worker_in_independent_cli_namespaces(self):
        routes = []
        for session in (SESSION, OTHER_SESSION):
            report = self.assert_route(worker_route(session, WORKER), body=json.dumps(request_body(session)).encode(),
                                       headers=[(b"x-claude-code-agent-id", WORKER.encode())])
            routes.append(report.outbound_headers[0]["session-id"])
        self.assertNotEqual(*routes)

    def test_repeat_and_resume_keep_route_but_request_ids_are_unique(self):
        reports = [self.assert_route(worker_route(SESSION, WORKER), headers=[(b"x-claude-code-agent-id", WORKER.encode())]) for _ in range(2)]
        self.assertNotEqual(reports[0].outbound_headers[0]["X-Client-Request-Id"],
                            reports[1].outbound_headers[0]["X-Client-Request-Id"])

    def test_invalid_metadata_json_and_uuid_omit_routing(self):
        for user_id in ("not-json", "[]", "null", "{}", json.dumps(identity("not-a-uuid")),
                        json.dumps(identity("00000000-0000-0000-0000-000000000000")),
                        json.dumps({**identity(), "device_id": 1}), "x" * 4097):
            with self.subTest(user_id=user_id[:100]):
                body = request_body()
                body["metadata"]["user_id"] = user_id
                self.assert_route(None, body=json.dumps(body).encode(), headers=[(b"x-claude-code-agent-id", WORKER.encode())])

    def test_duplicate_json_identity_keys_omit_routing(self):
        metadata = json.dumps(request_body()["metadata"])
        nested = json.dumps(identity())[:-1] + ',"session_id":' + json.dumps(OTHER_SESSION) + '}'
        base = json.dumps({key: value for key, value in request_body().items() if key != "metadata"})[:-1]
        cases = [base + ',"metadata":' + metadata + ',"metadata":' + metadata + '}',
                 base + ',"metadata":{"user_id":' + json.dumps(json.dumps(identity())) + ',"user_id":' + json.dumps(json.dumps(identity())) + '}}',
                 base + ',"metadata":{"user_id":' + json.dumps(nested) + '}}']
        for index, raw in enumerate(cases):
            with self.subTest(duplicate_level=index):
                self.assert_route(None, body=raw.encode(), headers=[(b"x-claude-code-agent-id", WORKER.encode())])

    def test_case_insensitive_header_name_and_maximum_prefix(self):
        for worker in (WORKER, "a" + "Z" * 63 + "-" + "a" * 16):
            with self.subTest(worker=worker):
                self.assert_route(worker_route(SESSION, worker), headers=[(b"X-Claude-Code-Agent-ID", worker.encode())])

    def test_duplicate_worker_headers_never_fall_back_to_parent(self):
        for second in (WORKER, OTHER_WORKER):
            with self.subTest(second=second):
                self.assert_route(None, headers=[(b"x-claude-code-agent-id", WORKER.encode()),
                                                  (b"X-Claude-Code-Agent-Id", second.encode())])

    def test_hostile_and_unknown_custom_workers_omit_routing(self):
        for worker in (b"", b" a0123456789abcdef", b"a0123456789abcdef\r\nHost:evil", b"worker@team",
                       b"\xff", b"a" * 82, b"a0123456789ABCDEF0", b"%610123456789abcdef"):
            with self.subTest(worker=worker):
                self.assert_route(None, headers=[(b"x-claude-code-agent-id", worker)])

    def test_parent_only_header_omits_but_valid_worker_still_routes(self):
        parent = (b"X-Claude-Code-Parent-Agent-Id", OTHER_WORKER.encode())
        self.assert_route(None, headers=[parent])
        self.assert_route(worker_route(SESSION, WORKER), headers=[parent, (b"x-claude-code-agent-id", WORKER.encode())])

    def test_absent_metadata_does_not_trust_inbound_session_headers(self):
        body = request_body()
        body.pop("metadata")
        self.assert_route(None, body=json.dumps(body).encode(), headers=[(b"session-id", SESSION.encode()),
                                                                        (b"x-claude-code-agent-id", WORKER.encode())])

    def test_openai_api_lane_remains_without_conversation_header(self):
        for headers in ([], [(b"x-claude-code-agent-id", WORKER.encode())]):
            with self.subTest(headers=headers):
                report = self.assert_route(None, mode="openai", headers=headers)
                self.assertEqual(set(report.outbound_headers[0]), {"Authorization", "Content-Type", "X-Client-Request-Id"})
                self.assertFalse(report.outbound_payloads[0]["stream"])

    def test_401_refresh_preserves_route_and_request_id(self):
        report, auth = self.probe(headers=[(b"x-claude-code-agent-id", WORKER.encode())], refresh=True)
        first, retry = report.outbound_headers
        self.assertEqual(first["session-id"], worker_route(SESSION, WORKER))
        self.assertEqual(retry["session-id"], first["session-id"])
        self.assertEqual(retry["X-Client-Request-Id"], first["X-Client-Request-Id"])
        self.assertNotEqual(first["authorization"], retry["authorization"])
        self.assertEqual(auth.await_count, 2)
        self.assertTrue(auth.await_args_list[1].kwargs["force_refresh"])
        self.assertEqual(auth.await_args_list[1].kwargs["rejected_token"], "SYNTHETIC_FIRST")

    def test_concurrent_parent_and_workers_have_isolated_wire_headers(self):
        # INTENT: hold three accepted backend requests before releasing any reply.
        # REASONING: proves overlapping real handler lifetimes, not merely threads.
        # ASSUMES: synthetic CLI-shaped identities; no real CLI or auth-origin claim.
        for mode in ("chatgpt", "openai"):
            with self.subTest(mode=mode), MockResponsesServer(heartbeat_text_scenario(gap_s=0)) as backend:
                gates = [backend.gate_response_request(i) for i in (1, 2, 3)]
                with RealShim(backend, mode) as shim:
                    expected = {}
                    with ThreadPoolExecutor(max_workers=3) as pool:
                        futures = []
                        try:
                            for index, worker in enumerate((None, WORKER, OTHER_WORKER)):
                                marker = "concurrent_route_" + str(index)
                                expected[marker] = (SESSION if worker is None else worker_route(SESSION, worker)) if mode == "chatgpt" else None
                                headers = {"x-claude-code-agent-id": worker} if worker else {}
                                futures.append(pool.submit(shim.post_raw_messages,
                                    json.dumps(request_body(marker=marker, stream=bool(index % 2))).encode(), headers=headers))
                            for entered, _ in gates:
                                self.assertTrue(entered.wait(5), "three upstream requests must overlap")
                        finally:
                            for _, release in gates:
                                release.set()
                        for future in futures:
                            result = future.result(timeout=10)
                            self.assertEqual(result.status, 200)
                            lifecycle_for_response(shim, result)
                    self.assertEqual(len(backend.responses_requests), 3)
                    for outgoing in backend.responses_requests:
                        raw = json.dumps(outgoing.body["input"])
                        markers = [marker for marker in expected if '"' + marker + '"' in raw]
                        self.assertEqual(len(markers), 1)
                        self.assertEqual(outgoing.headers.get("session-id"), expected[markers[0]])
                        self.assertNotIn("x-claude-code-agent-id", outgoing.headers)
                    self.assertEqual(len({r.headers["x-client-request-id"] for r in backend.responses_requests}), 3)
                    for value in (SESSION, WORKER, OTHER_WORKER, worker_route(SESSION, WORKER), worker_route(SESSION, OTHER_WORKER)):
                        self.assertNotIn(value, shim.captured_stderr())
                    shim.assert_offline_contract()

    def test_two_cli_namespaces_repeat_exact_outgoing_mock_headers(self):
        with MockResponsesServer(heartbeat_text_scenario(gap_s=0)) as backend:
            with RealShim(backend, "chatgpt") as shim:
                for session in (SESSION, OTHER_SESSION, SESSION, OTHER_SESSION):
                    result = shim.post_raw_messages(json.dumps(request_body(session)).encode(),
                                                    headers={"x-claude-code-agent-id": WORKER})
                    self.assertEqual(result.status, 200)
                    lifecycle_for_response(shim, result)
                    self.assertEqual(backend.responses_requests[-1].headers["session-id"], worker_route(session, WORKER))
                self.assertEqual(len({r.headers["session-id"] for r in backend.responses_requests}), 2)
                self.assertEqual(len({r.headers["x-client-request-id"] for r in backend.responses_requests}), 4)
                for value in (SESSION, OTHER_SESSION, WORKER, worker_route(SESSION, WORKER), worker_route(OTHER_SESSION, WORKER)):
                    self.assertNotIn(value, shim.captured_stderr())
                shim.assert_offline_contract()
