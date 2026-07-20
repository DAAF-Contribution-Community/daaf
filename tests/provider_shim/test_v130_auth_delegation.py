"""v1.3.0 (Tier 3 A1) — ChatGPT-lane auth delegation to the codex CLI.

The shim no longer refreshes ChatGPT OAuth tokens itself. It READS
``$CODEX_HOME/auth.json``, and when the access_token is near expiry (proactive) or
a backend 401 rejects it (reactive), it DELEGATES the refresh to the codex CLI by
spawning ``codex login status`` and then re-reading auth.json — judging success
ONLY by the re-read result, never by the subprocess's exit code or output. Codex is
the single writer; the shim never writes auth.json.

These are in-process unit contracts: each test imports a fresh copy of the
production shim module under a controlled environment (chatgpt mode, an isolated
CODEX_HOME, and SHIM_CODEX_BIN pointed at the fake-codex stub), then drives the auth
primitives directly. The env patch stays live across the async calls so the codex
subprocess the shim spawns inherits CODEX_HOME + FAKE_CODEX_MODE. No network, no real
credentials, no real codex binary is involved.

Coverage:
- proactive trigger refreshes a near-expiry token (and a valid token does not spawn);
- reactive 401 refresh returns the fresh token;
- an unrecoverable refresh (codex no-op on an expired token) raises an error whose
  message literally contains ``codex login --device-auth``;
- the codex binary missing, and codex hanging past SHIM_CODEX_TIMEOUT_S, both surface
  the actionable error rather than crashing or hanging;
- single-flight: concurrent refreshes spawn codex exactly once;
- an absent or unreadable auth.json surfaces the actionable error.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import shutil
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

from ._loopback_harness import (
    FAKE_CODEX_BIN,
    PRODUCTION_SHIM,
    SCRATCH_ROOT,
    _make_fake_jwt,
)

RECOVERY_COMMAND = "codex login --device-auth"
FAKE_OPENAI_KEY = "sk-FAKE_PROVIDER_SHIM_AUTHTEST_000000000000"


def _load_fresh_shim():
    """Import a pristine copy of the production shim under the current environment."""

    module_name = f"provider_shim_authtest_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, PRODUCTION_SHIM)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load production shim for auth-delegation test")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AuthDelegationTest(unittest.TestCase):
    def setUp(self) -> None:
        SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
        self.codex_home = SCRATCH_ROOT / f"provider-shim-authtest-{uuid.uuid4().hex}"
        self.codex_home.mkdir(mode=0o700)
        self.auth_path = self.codex_home / "auth.json"

    def tearDown(self) -> None:
        # Restore readability so an unreadable-store test can still be cleaned up.
        if self.auth_path.exists():
            try:
                self.auth_path.chmod(0o600)
            except OSError:
                pass
        if self.codex_home.exists():
            shutil.rmtree(self.codex_home, ignore_errors=True)

    # --- helpers ---

    def _seed_auth(self, exp_offset_s: int) -> str:
        """Write an auth.json whose access_token expires `exp_offset_s` from now."""

        token = _make_fake_jwt(int(time.time()) + exp_offset_s)
        auth = {
            "OPENAI_API_KEY": FAKE_OPENAI_KEY,
            "auth_mode": "chatgpt",
            "last_refresh": "2099-01-01T00:00:00.000000000Z",
            "tokens": {
                "access_token": token,
                "account_id": "acct_authtest",
                "id_token": "FAKE_ID_TOKEN",
                "refresh_token": "FAKE_REFRESH_TOKEN",
            },
        }
        self.auth_path.write_text(json.dumps(auth), encoding="utf-8")
        self.auth_path.chmod(0o600)
        return token

    def _disk_token(self):
        auth = json.loads(self.auth_path.read_text(encoding="utf-8"))
        return (auth.get("tokens") or {}).get("access_token")

    def _codex_call_count(self) -> int:
        marker = self.codex_home / ".codex_calls"
        if not marker.exists():
            return 0
        return len(
            [line for line in marker.read_text(encoding="utf-8").splitlines() if line]
        )

    def _env(self, *, mode="noop", timeout=None, codex_bin=None):
        env = {
            "SHIM_BACKEND_MODE": "chatgpt",
            "SHIM_BACKEND_BASE_URL": "http://127.0.0.1:1",
            "OPENAI_API_KEY": FAKE_OPENAI_KEY,
            "CODEX_HOME": str(self.codex_home),
            "SHIM_CODEX_BIN": codex_bin if codex_bin is not None else str(FAKE_CODEX_BIN),
            "FAKE_CODEX_MODE": mode,
        }
        if timeout is not None:
            env["SHIM_CODEX_TIMEOUT_S"] = str(timeout)
        return env

    # --- proactive path ---

    def test_proactive_trigger_refreshes_near_expiry_token(self) -> None:
        seeded = self._seed_auth(exp_offset_s=60)  # inside the 5-min margin
        with mock.patch.dict(os.environ, self._env(mode="refresh-success"), clear=False):
            module = _load_fresh_shim()
            returned = asyncio.run(module._get_access_token())
        fresh = self._disk_token()
        self.assertNotEqual(fresh, seeded, "codex should have rewritten the token")
        self.assertEqual(returned, fresh, "shim must return the freshly re-read token")
        self.assertEqual(self._codex_call_count(), 1, "codex must be invoked exactly once")

    def test_proactive_valid_token_does_not_spawn_codex(self) -> None:
        seeded = self._seed_auth(exp_offset_s=365 * 86400)  # far future
        with mock.patch.dict(os.environ, self._env(mode="refresh-success"), clear=False):
            module = _load_fresh_shim()
            returned = asyncio.run(module._get_access_token())
        self.assertEqual(returned, seeded, "a comfortably-valid token is returned as-is")
        self.assertEqual(self._codex_call_count(), 0, "no refresh should be delegated")

    # --- reactive (401) path ---

    def test_reactive_401_refresh_returns_fresh_token(self) -> None:
        seeded = self._seed_auth(exp_offset_s=365 * 86400)  # exp-valid but rejected
        with mock.patch.dict(os.environ, self._env(mode="refresh-success"), clear=False):
            module = _load_fresh_shim()
            returned = asyncio.run(
                module._get_access_token(force_refresh=True, rejected_token=seeded)
            )
        fresh = self._disk_token()
        self.assertNotEqual(fresh, seeded)
        self.assertEqual(returned, fresh)
        self.assertEqual(self._codex_call_count(), 1)

    def test_reactive_401_unrecoverable_raises_actionable_error(self) -> None:
        # Expired on disk + codex that cannot refresh (no-op) -> the re-read is still
        # invalid, so delegated refresh fails with the actionable recovery command.
        seeded = self._seed_auth(exp_offset_s=-3600)
        with mock.patch.dict(os.environ, self._env(mode="noop"), clear=False):
            module = _load_fresh_shim()
            with self.assertRaises(RuntimeError) as ctx:
                asyncio.run(
                    module._get_access_token(force_refresh=True, rejected_token=seeded)
                )
        self.assertIn(RECOVERY_COMMAND, str(ctx.exception))
        self.assertEqual(self._codex_call_count(), 1)

    def test_reactive_401_codex_not_logged_in_raises_actionable_error(self) -> None:
        seeded = self._seed_auth(exp_offset_s=-3600)
        with mock.patch.dict(os.environ, self._env(mode="not-logged-in"), clear=False):
            module = _load_fresh_shim()
            with self.assertRaises(RuntimeError) as ctx:
                asyncio.run(
                    module._get_access_token(force_refresh=True, rejected_token=seeded)
                )
        self.assertIn(RECOVERY_COMMAND, str(ctx.exception))

    # --- resilience: missing binary, timeout ---

    def test_codex_binary_missing_surfaces_actionable_error(self) -> None:
        self._seed_auth(exp_offset_s=-3600)
        missing = str(self.codex_home / "nonexistent-codex-binary")
        with mock.patch.dict(
            os.environ, self._env(mode="noop", codex_bin=missing), clear=False
        ):
            module = _load_fresh_shim()
            with self.assertRaises(RuntimeError) as ctx:
                asyncio.run(module.delegated_refresh())
        self.assertIn(RECOVERY_COMMAND, str(ctx.exception))

    def test_codex_hang_is_killed_and_surfaces_actionable_error(self) -> None:
        self._seed_auth(exp_offset_s=-3600)
        with mock.patch.dict(
            os.environ, self._env(mode="hang", timeout=0.5), clear=False
        ):
            module = _load_fresh_shim()
            self.assertEqual(module.SHIM_CODEX_TIMEOUT_S, 0.5)
            start = time.monotonic()
            with self.assertRaises(RuntimeError) as ctx:
                asyncio.run(module.delegated_refresh())
            elapsed = time.monotonic() - start
        self.assertIn(RECOVERY_COMMAND, str(ctx.exception))
        # Bounded by the timeout knob, not the stub's 3600s sleep.
        self.assertLess(elapsed, 20.0, "hung codex must be killed near the timeout")

    def test_timeout_env_unparseable_falls_back_to_default(self) -> None:
        self._seed_auth(exp_offset_s=365 * 86400)
        env = self._env(mode="noop")
        env["SHIM_CODEX_TIMEOUT_S"] = "not-a-number"
        with mock.patch.dict(os.environ, env, clear=False):
            module = _load_fresh_shim()
            self.assertEqual(module.SHIM_CODEX_TIMEOUT_S, 30.0)

    # --- single-flight ---

    def test_single_flight_concurrent_refreshes_spawn_codex_once(self) -> None:
        self._seed_auth(exp_offset_s=60)  # near expiry -> all callers want a refresh

        async def _race(module):
            return await asyncio.gather(
                *[module.delegated_refresh() for _ in range(8)]
            )

        with mock.patch.dict(os.environ, self._env(mode="refresh-success"), clear=False):
            module = _load_fresh_shim()
            results = asyncio.run(_race(module))
        fresh = self._disk_token()
        self.assertTrue(all(token == fresh for token in results))
        self.assertEqual(
            self._codex_call_count(), 1, "single-flight must spawn codex exactly once"
        )

    # --- absent / unreadable store ---

    def test_auth_json_absent_surfaces_actionable_error(self) -> None:
        # No auth.json is written at all.
        with mock.patch.dict(os.environ, self._env(mode="refresh-success"), clear=False):
            module = _load_fresh_shim()
            with self.assertRaises(RuntimeError) as ctx:
                asyncio.run(module._get_access_token())
        self.assertIn(RECOVERY_COMMAND, str(ctx.exception))

    def test_auth_json_unreadable_surfaces_actionable_error(self) -> None:
        self._seed_auth(exp_offset_s=365 * 86400)
        self.auth_path.chmod(0o000)
        with mock.patch.dict(os.environ, self._env(mode="refresh-success"), clear=False):
            module = _load_fresh_shim()
            with self.assertRaises(RuntimeError) as ctx:
                asyncio.run(module._get_access_token())
        self.assertIn(RECOVERY_COMMAND, str(ctx.exception))

    # --- invariant: the recovery command is always in the canonical message ---

    def test_relogin_message_contains_recovery_command(self) -> None:
        with mock.patch.dict(os.environ, self._env(mode="noop"), clear=False):
            module = _load_fresh_shim()
            self.assertIn(RECOVERY_COMMAND, module._RELOGIN_MSG)


if __name__ == "__main__":
    unittest.main()
