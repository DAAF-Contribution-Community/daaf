"""Deterministic contracts for the v1.3.1 quota-state cache write.

The v1.3.1 shim, on every chatgpt-lane 2xx, additionally caches the quota snapshot
to ``<log dir>/quota_state.json`` (an atomic, 0600, absolutely-fail-open write) so
the statusline can render a "Plan usage:" segment on shim-lane sessions. These tests
exercise the write helper and its guard IN-PROCESS: the production shim module is
imported via importlib (the same seam the harness uses for its ownership probe) so the
module-level state-file path and ``SHIM_BACKEND_MODE`` can be monkeypatched to a tmp
directory — no subprocess, and the real ``scripts/provider_shim/logs/`` directory is
never touched.

1. chatgpt-lane 2xx writes the state file: correct JSON keys, ``captured_at`` within
   the test wall-clock bounds, header values passed through, absent headers -> "-".
2. The guard holds: the openai lane and a chatgpt non-2xx write no file.
3. Overwrite semantics: a second 2xx replaces the content and leaves no ``.tmp``
   sibling behind.
4. Write failure is swallowed: an unwritable log dir or an ``os.replace`` that raises
   leaves the response path unaffected (no exception escapes) and no stale ``.tmp``.

v1.3.2 adds the ``DAAF_QUOTA_STATE_FILE`` redirect seam (the same env var the reader,
context-bar.sh, already honors) plus its end-to-end consequences, verified with the
spawned production shim via the loopback harness:

5. Seam honored: a spawned chatgpt-lane shim writes its snapshot to the seam path (the
   harness's per-instance scratch dir), with the expected content shape and 0600 mode.
6. Production-file non-pollution (the regression that matters): a representative spawned
   chatgpt-lane exchange leaves the install-shared ``scripts/provider_shim/logs/
   quota_state.json`` byte- and mtime-identical, because the harness seams every spawned
   shim away from it.
7. Default derivation unchanged: with the env var unset/empty the module-level state
   path resolves to the ``__file__``-derived location (and to the seam value when set),
   probed via an out-of-process ``python -c`` import of the two module constants so no
   unseamed production shim is ever spawned against the live file.

The v1.3.2 fix cycle closes the residual in-process pollution path (2026-07-21 incident):
``e665fbe`` seamed spawned shims and the in-process unit tests here, but
``controlled_asgi_probe`` loads a fresh production module *in the test-runner process*
and drives the real request path, so its chatgpt-lane 2xx wrote the install-shared file
because ``DAAF_QUOTA_STATE_FILE`` was unset in the runner. A runner-level
``os.environ.setdefault`` in the loopback harness now seams every in-process load:

8. In-process non-pollution: running tonight's exact polluter case through
   ``controlled_asgi_probe`` leaves the install-shared ``quota_state.json`` byte- and
   mtime-identical, because the runner-level seam redirects its write to scratch.
"""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

import httpx

from ._loopback_harness import (
    PRODUCTION_SHIM,
    MockResponsesServer,
    RealShim,
    controlled_asgi_probe,
    full_response_scenario,
    lifecycle_for_response,
    parse_typed_sse,
)


def _load_shim_module():
    """Import a fresh instance of the production shim in-process (no subprocess)."""
    module_name = f"provider_shim_quota_state_probe_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, PRODUCTION_SHIM)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load production shim for quota-state probe")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Synthetic subscription-quota header surface modeled on the live chatgpt-lane
# capture. Secondary-window headers are intentionally omitted so the
# "absent header -> field renders as -" contract is exercised end to end.
QUOTA_HEADERS = {
    "x-codex-plan-type": "pro",
    "x-codex-active-limit": "premium",
    "x-codex-primary-used-percent": "73",
    "x-codex-primary-window-minutes": "10080",
    "x-codex-primary-reset-after-seconds": "402168",
    "x-codex-credits-has-credits": "False",
    "x-codex-credits-balance": "0",
    "x-codex-credits-unlimited": "False",
}

_ALL_SNAPSHOT_FIELDS = (
    "plan_type",
    "active_limit",
    "primary_used_pct",
    "primary_window_min",
    "primary_reset_s",
    "secondary_used_pct",
    "secondary_window_min",
    "secondary_reset_s",
    "credits_has",
    "credits_balance",
    "credits_unlimited",
)


class _FakeResponse:
    """Minimal stand-in for the httpx response _record_upstream_headers reads."""

    def __init__(self, status_code, headers=None, http_version="HTTP/1.1"):
        self.status_code = status_code
        self.headers = httpx.Headers(headers or {})
        self.http_version = http_version


class ProviderShimV131QuotaStateTests(unittest.TestCase):
    maxDiff = 12000

    def setUp(self) -> None:
        self.module = _load_shim_module()
        # Redirect the install-shared state file into a per-test tmp directory so the
        # real scripts/provider_shim/logs/ directory is never written during tests.
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state_dir = Path(self._tmp.name)
        self.state_path = self.state_dir / "quota_state.json"
        self.module._QUOTA_STATE_DIR = str(self.state_dir)
        self.module._QUOTA_STATE_PATH = str(self.state_path)

    def _drive_record(self, mode, response) -> None:
        # Exercise the real call site (_record_upstream_headers) with a live request
        # state, exactly as the request path would, under the chosen backend lane.
        self.module.SHIM_BACKEND_MODE = mode
        state = self.module._RequestLifecycleState()
        token = self.module._REQUEST_STATE.set(state)
        try:
            self.module._record_upstream_headers(response)
        finally:
            self.module._REQUEST_STATE.reset(token)

    def _tmp_siblings(self):
        return sorted(p.name for p in self.state_dir.glob("quota_state.*.tmp"))

    def test_chatgpt_2xx_writes_state_file_with_expected_fields(self) -> None:
        before = int(time.time())
        self._drive_record("chatgpt", _FakeResponse(200, QUOTA_HEADERS))
        after = int(time.time())

        self.assertTrue(self.state_path.exists(), "state file was not written")
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))

        # captured_at is an int recorded at write time, within the test's wall clock.
        self.assertIsInstance(payload["captured_at"], int)
        self.assertGreaterEqual(payload["captured_at"], before)
        self.assertLessEqual(payload["captured_at"], after)

        # Every one of the 11 snapshot fields is present.
        for field in _ALL_SNAPSHOT_FIELDS:
            self.assertIn(field, payload)

        # Present headers pass through as their raw string values.
        self.assertEqual(payload["plan_type"], "pro")
        self.assertEqual(payload["active_limit"], "premium")
        self.assertEqual(payload["primary_used_pct"], "73")
        self.assertEqual(payload["primary_window_min"], "10080")
        self.assertEqual(payload["primary_reset_s"], "402168")
        self.assertEqual(payload["credits_has"], "False")
        self.assertEqual(payload["credits_balance"], "0")
        self.assertEqual(payload["credits_unlimited"], "False")

        # Absent secondary-window headers render as "-".
        self.assertEqual(payload["secondary_used_pct"], "-")
        self.assertEqual(payload["secondary_window_min"], "-")
        self.assertEqual(payload["secondary_reset_s"], "-")

        # Locks the telemetry-hygiene contract (0600) against a future refactor
        # to the write call that silently loses the mkstemp-inherited mode.
        self.assertEqual(stat.S_IMODE(os.stat(self.state_path).st_mode), 0o600)

        # No temp sibling is left behind after a successful atomic publish.
        self.assertEqual(self._tmp_siblings(), [])

    def test_openai_lane_writes_no_state_file(self) -> None:
        self._drive_record("openai", _FakeResponse(200, QUOTA_HEADERS))
        self.assertFalse(self.state_path.exists())
        self.assertEqual(self._tmp_siblings(), [])

    def test_chatgpt_non_2xx_writes_no_state_file(self) -> None:
        self._drive_record("chatgpt", _FakeResponse(429, QUOTA_HEADERS))
        self.assertFalse(self.state_path.exists())
        self.assertEqual(self._tmp_siblings(), [])

    def test_second_2xx_overwrites_and_leaves_no_temp_sibling(self) -> None:
        self._drive_record("chatgpt", _FakeResponse(200, QUOTA_HEADERS))
        first = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(first["primary_used_pct"], "73")

        second_headers = dict(QUOTA_HEADERS)
        second_headers["x-codex-primary-used-percent"] = "88"
        second_headers["x-codex-secondary-used-percent"] = "5"
        second_headers["x-codex-secondary-window-minutes"] = "300"
        second_headers["x-codex-secondary-reset-after-seconds"] = "600"
        self._drive_record("chatgpt", _FakeResponse(200, second_headers))

        replaced = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(replaced["primary_used_pct"], "88")
        self.assertEqual(replaced["secondary_used_pct"], "5")
        self.assertEqual(replaced["secondary_window_min"], "300")
        self.assertGreaterEqual(replaced["captured_at"], first["captured_at"])

        # Overwrite still leaves no stale temp sibling.
        self.assertEqual(self._tmp_siblings(), [])

    def test_write_failure_on_unwritable_dir_is_swallowed(self) -> None:
        # Point the state dir at a path that is a FILE, not a directory, so mkstemp
        # raises NotADirectoryError. The response path must be unaffected: no
        # exception escapes and no file is created.
        not_a_dir = self.state_dir / "regular_file"
        not_a_dir.write_text("x", encoding="utf-8")
        self.module._QUOTA_STATE_DIR = str(not_a_dir / "logs")
        self.module._QUOTA_STATE_PATH = str(not_a_dir / "logs" / "quota_state.json")

        # Must not raise.
        self._drive_record("chatgpt", _FakeResponse(200, QUOTA_HEADERS))
        self.assertFalse((not_a_dir / "logs" / "quota_state.json").exists())

    def test_os_replace_raising_is_swallowed_and_leaves_no_temp(self) -> None:
        # Directly exercise the helper with os.replace monkeypatched to raise: the
        # write must be swallowed and the uniquely-named temp sibling cleaned up.
        original_replace = os.replace

        def _raising_replace(src, dst):  # noqa: ANN001
            raise RuntimeError("synthetic replace failure")

        os.replace = _raising_replace
        try:
            # Must not raise.
            self.module._write_quota_state({field: "-" for field in _ALL_SNAPSHOT_FIELDS})
        finally:
            os.replace = original_replace

        self.assertFalse(self.state_path.exists())
        self.assertEqual(self._tmp_siblings(), [])


# The install-shared quota-state file the shim writes when NOT seamed. The v1.3.2
# regression proves a seamed spawned shim never touches this path.
_INSTALL_SHARED_STATE = PRODUCTION_SHIM.parent / "logs" / "quota_state.json"


def _stat_snapshot(path: Path):
    """Return (st_mtime_ns, raw bytes) for path, or None if it does not exist."""
    try:
        return (path.stat().st_mtime_ns, path.read_bytes())
    except FileNotFoundError:
        return None


# Out-of-process probe: import the production shim by file and print the two module-
# level state-path constants as JSON. Run under a controlled env so DAAF_QUOTA_STATE_FILE
# is either explicitly absent or explicitly set. Importing the module only evaluates the
# constant/def bodies (it never calls _write_quota_state), so this probe touches no state
# file — the reason it is used instead of spawning an unseamed production shim.
_PATH_PROBE = (
    "import importlib.util, json, sys\n"
    "spec = importlib.util.spec_from_file_location('shim_path_probe', sys.argv[1])\n"
    "m = importlib.util.module_from_spec(spec)\n"
    "spec.loader.exec_module(m)\n"
    "print(json.dumps({'dir': m._QUOTA_STATE_DIR, 'path': m._QUOTA_STATE_PATH}))\n"
)


class ProviderShimV132QuotaStateSeamTests(unittest.TestCase):
    """v1.3.2 DAAF_QUOTA_STATE_FILE redirect-seam contracts (spawned production shim)."""

    maxDiff = 12000

    def _run_path_probe(self, extra_env):
        env = {k: v for k, v in os.environ.items() if k != "DAAF_QUOTA_STATE_FILE"}
        env.update(extra_env)
        completed = subprocess.run(
            [sys.executable, "-c", _PATH_PROBE, str(PRODUCTION_SHIM)],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout.strip())

    def test_spawned_chatgpt_shim_writes_snapshot_to_seam_path(self) -> None:
        scenario = full_response_scenario()
        scenario.stream_headers = dict(QUOTA_HEADERS)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                parse_typed_sse(result.body)
                # Drain the lifecycle log; the state write fires on upstream headers,
                # so it has certainly landed by the time the full body is parsed.
                lifecycle_for_response(shim, result)

                # The harness seams the write into this instance's scratch dir.
                seam_path = Path(shim.child_env["DAAF_QUOTA_STATE_FILE"])
                self.assertEqual(seam_path, shim.scratch_dir / "quota_state.json")
                self.assertTrue(
                    seam_path.exists(), "snapshot did not land at the seam path"
                )

                payload = json.loads(seam_path.read_text(encoding="utf-8"))
                self.assertIsInstance(payload["captured_at"], int)
                for field in _ALL_SNAPSHOT_FIELDS:
                    self.assertIn(field, payload)
                self.assertEqual(payload["primary_used_pct"], "73")
                self.assertEqual(payload["primary_window_min"], "10080")
                # Absent secondary headers pass through as "-".
                self.assertEqual(payload["secondary_used_pct"], "-")

                # Same telemetry-hygiene contract as the in-process write: 0600.
                self.assertEqual(
                    stat.S_IMODE(os.stat(seam_path).st_mode), 0o600
                )
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)

    def test_spawned_chatgpt_shim_does_not_touch_install_shared_file(self) -> None:
        # The regression that matters: a full spawned chatgpt-lane exchange must leave the
        # install-shared state file byte- and mtime-identical (or still-absent).
        before = _stat_snapshot(_INSTALL_SHARED_STATE)
        scenario = full_response_scenario()
        scenario.stream_headers = dict(QUOTA_HEADERS)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                parse_typed_sse(result.body)
                lifecycle_for_response(shim, result)
                # Confirm the shim really did write a snapshot (to its seam), so this
                # test cannot pass vacuously by the write never happening at all.
                seam_path = Path(shim.child_env["DAAF_QUOTA_STATE_FILE"])
                self.assertTrue(seam_path.exists())
                shim.assert_offline_contract()
        after = _stat_snapshot(_INSTALL_SHARED_STATE)
        self.assertEqual(
            before,
            after,
            "spawned shim polluted the install-shared quota_state.json",
        )

    def test_in_process_asgi_probe_does_not_touch_install_shared_file(self) -> None:
        # Locks the v1.3.2 fix-cycle contract: an in-process load of the production shim
        # in the test-runner process must not write the install-shared quota_state.json.
        #
        # 2026-07-21 in-process pollution incident: e665fbe seamed spawned shims (child
        # env) and the in-process unit tests here (setUp constant patching), but missed a
        # third context — controlled_asgi_probe loads a FRESH production module in-process
        # and drives the real request path, so a chatgpt-lane case reaching a mocked 200
        # ran the real _record_upstream_headers -> _write_quota_state. With
        # DAAF_QUOTA_STATE_FILE unset in the runner process, that module resolved
        # _QUOTA_STATE_PATH to the live install-shared file and rewrote it (all-dash
        # snapshot) on every run. The fix is a runner-level os.environ.setdefault in the
        # loopback harness; this test runs the exact polluter case and asserts the
        # production file is untouched.
        before = _stat_snapshot(_INSTALL_SHARED_STATE)
        # tonight's exact deterministic polluter: chatgpt-lane (lazy_401_refresh), a 401
        # then a mocked 200, with a local cleanup failure on attempt 1.
        controlled_asgi_probe(
            attempt_outcomes=[401, 200],
            close_fail_attempts={1},
            lazy_401_refresh=True,
        )
        after = _stat_snapshot(_INSTALL_SHARED_STATE)
        self.assertEqual(
            before,
            after,
            "in-process ASGI probe polluted the install-shared quota_state.json",
        )
        # Non-vacuity: the runner-level seam is present, so the write the probe drives has
        # a scratch destination to land in (a missing seam would send it to production).
        self.assertTrue(os.environ.get("DAAF_QUOTA_STATE_FILE"))

    def test_default_path_derivation_is_file_relative_without_seam(self) -> None:
        # Unset/empty seam -> the __file__-derived default, byte-identical to prior
        # behavior. Probed out-of-process so no unseamed shim runs against the live file.
        expected_dir = PRODUCTION_SHIM.parent / "logs"
        for extra_env in ({}, {"DAAF_QUOTA_STATE_FILE": ""}):
            with self.subTest(extra_env=extra_env):
                got = self._run_path_probe(extra_env)
                self.assertEqual(got["dir"], str(expected_dir))
                self.assertEqual(
                    got["path"], str(expected_dir / "quota_state.json")
                )

    def test_seam_env_redirects_module_state_path(self) -> None:
        # Set + non-empty seam -> the module constants resolve to the seam path and its
        # dirname (the other direction of the same probe).
        with tempfile.TemporaryDirectory() as tmp:
            seam = str(Path(tmp) / "redirected_quota.json")
            got = self._run_path_probe({"DAAF_QUOTA_STATE_FILE": seam})
            self.assertEqual(got["path"], seam)
            self.assertEqual(got["dir"], str(Path(tmp)))


if __name__ == "__main__":
    unittest.main()
