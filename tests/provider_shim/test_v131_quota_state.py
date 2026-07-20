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
"""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import tempfile
import time
import unittest
import uuid
from pathlib import Path

import httpx

from ._loopback_harness import PRODUCTION_SHIM


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


if __name__ == "__main__":
    unittest.main()
