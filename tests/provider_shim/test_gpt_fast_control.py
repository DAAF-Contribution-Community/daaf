"""Provider-free v1.3.9 tests for route-bound GPT service-tier control."""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import io
import json
import multiprocessing
import os
import shutil
import stat
import sys
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

from ._loopback_harness import (
    MockResponsesServer,
    RealShim,
    controlled_asgi_probe,
    full_response_scenario,
    lifecycle_for_response,
    terminal_contract_scenario,
)

DAAF_ROOT = Path(__file__).resolve().parents[2]
SHIM_DIR = DAAF_ROOT / "scripts" / "provider_shim"
SCRATCH_ROOT = DAAF_ROOT / "scripts" / "scratch"
if str(SHIM_DIR) not in sys.path:
    sys.path.insert(0, str(SHIM_DIR))

import gpt_fast  # noqa: E402


def _writer_process(home: str, backend: str, enabled: bool, start: multiprocessing.Event) -> None:
    start.wait(5)
    gpt_fast.PolicyStore(home=home).write(backend, enabled)


def _terminal_fields(lines) -> dict[str, str]:
    fields = [line.fields for line in lines if line.event == "terminal"]
    if len(fields) != 1:
        raise AssertionError(f"expected one terminal lifecycle record: {fields!r}")
    return fields[0]


def _request_body(*, stream: bool = False, speed: object = ...) -> bytes:
    body: dict[str, object] = {
        "model": "gpt-fixture",
        "max_tokens": 256,
        "stream": stream,
        "messages": [{"role": "user", "content": "provider-free policy fixture"}],
    }
    if speed is not ...:
        body["speed"] = speed
    return json.dumps(body, separators=(",", ":")).encode("utf-8")


class PolicyStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
        self.home = SCRATCH_ROOT / f"gpt-fast-unit-{uuid.uuid4().hex}"
        self.home.mkdir(mode=0o700)
        self.store = gpt_fast.PolicyStore(home=self.home)

    def tearDown(self) -> None:
        if self.home.exists() or self.home.is_symlink():
            # The test owns this unique path. rmtree unlinks contained symlinks rather
            # than following them, including every deliberately unsafe fixture below.
            shutil.rmtree(self.home, ignore_errors=True)

    def _seed_raw(self, raw: bytes, *, mode: int = 0o600) -> Path:
        self.store.state_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.store.state_dir.chmod(0o700)
        self.store.state_path.write_bytes(raw)
        self.store.state_path.chmod(mode)
        return self.store.state_path

    def test_missing_default_off_and_explicit_on_off_for_both_backends(self) -> None:
        missing = self.store.read("chatgpt")
        self.assertEqual(missing.status, "missing")
        self.assertFalse(missing.enabled)
        self.assertFalse(missing.effective)
        for backend in ("chatgpt", "openai"):
            with self.subTest(backend=backend):
                enabled = self.store.write(backend, True)
                self.assertEqual(enabled.status, "ok")
                self.assertEqual(enabled.backend_mode, backend)
                self.assertTrue(enabled.enabled)
                self.assertTrue(enabled.effective)
                self.assertFalse(self.store.read("openai" if backend == "chatgpt" else "chatgpt").effective)
                disabled = self.store.write(backend, False)
                self.assertEqual(disabled.status, "ok")
                self.assertFalse(disabled.enabled)
                self.assertFalse(disabled.effective)
                self.assertEqual(
                    self.store.state_path.read_bytes(),
                    json.dumps(
                        {"version": 1, "backend_mode": backend, "enabled": False},
                        separators=(",", ":"),
                    ).encode("utf-8"),
                )

    def test_strict_schema_duplicate_trailing_and_size_checks(self) -> None:
        invalid = (
            b"[]",
            b"{}",
            b'{"version":true,"backend_mode":"chatgpt","enabled":true}',
            b'{"version":1.0,"backend_mode":"chatgpt","enabled":true}',
            b'{"version":1,"backend_mode":"CHATGPT","enabled":true}',
            b'{"version":1,"backend_mode":"chatgpt","enabled":1}',
            b'{"version":1,"backend_mode":"chatgpt","enabled":true,"extra":0}',
            b'{"version":1,"version":1,"backend_mode":"chatgpt","enabled":true}',
            b'{"version":1,"backend_mode":"chatgpt","enabled":true}junk',
            b"\xff",
            b" " * 257,
        )
        for index, raw in enumerate(invalid):
            with self.subTest(index=index):
                self._seed_raw(raw)
                snapshot = self.store.read("chatgpt")
                self.assertEqual(snapshot.status, "invalid")
                self.assertFalse(snapshot.effective)

    def test_unsafe_directory_state_and_lock_objects_fail_closed(self) -> None:
        self._seed_raw(b'{"version":1,"backend_mode":"chatgpt","enabled":true}')
        self.store.state_dir.chmod(0o755)
        self.assertEqual(self.store.read("chatgpt").status, "unsafe")
        with self.assertRaises(gpt_fast.PolicyError):
            self.store.write("chatgpt", False)
        self.store.state_dir.chmod(0o700)

        self.store.state_path.chmod(0o644)
        self.assertEqual(self.store.read("chatgpt").status, "unsafe")
        before = self.store.state_path.read_bytes()
        with self.assertRaises(gpt_fast.PolicyError):
            self.store.write("chatgpt", False)
        self.assertEqual(self.store.state_path.read_bytes(), before)

        self.store.state_path.unlink()
        target = self.home / "target.json"
        target.write_text("sentinel", encoding="utf-8")
        self.store.state_path.symlink_to(target)
        self.assertEqual(self.store.read("chatgpt").status, "unsafe")
        with self.assertRaises(gpt_fast.PolicyError):
            self.store.write("chatgpt", True)
        self.assertEqual(target.read_text(encoding="utf-8"), "sentinel")
        self.store.state_path.unlink()

        regular = self._seed_raw(b'{"version":1,"backend_mode":"chatgpt","enabled":true}')
        hardlink = self.home / "policy-hardlink"
        os.link(regular, hardlink)
        self.assertEqual(self.store.read("chatgpt").status, "unsafe")
        with self.assertRaises(gpt_fast.PolicyError):
            self.store.write("chatgpt", False)
        hardlink.unlink()
        regular.unlink()

        os.mkfifo(self.store.state_path, 0o600)
        self.assertEqual(self.store.read("chatgpt").status, "unsafe")
        with self.assertRaises(gpt_fast.PolicyError):
            self.store.write("chatgpt", True)
        self.store.state_path.unlink()

        self.store.write("chatgpt", False)
        os.link(self.store.lock_path, self.home / "lock-hardlink")
        with self.assertRaises(gpt_fast.PolicyError):
            self.store.write("chatgpt", True)

    def test_home_symlink_is_rejected_before_policy_creation(self) -> None:
        outside = SCRATCH_ROOT / f"gpt-fast-outside-{uuid.uuid4().hex}"
        outside.mkdir(mode=0o700)
        linked_home = self.home / "linked-home"
        linked_home.symlink_to(outside, target_is_directory=True)
        try:
            linked_store = gpt_fast.PolicyStore(home=linked_home)
            self.assertEqual(linked_store.read("chatgpt").status, "unsafe")
            with self.assertRaises(gpt_fast.PolicyError):
                linked_store.write("chatgpt", True)
            self.assertFalse((outside / ".claude").exists())
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_wrong_owner_metadata_fails_closed_without_chown_privilege(self) -> None:
        self.store.write("chatgpt", True)
        with mock.patch.object(gpt_fast.os, "getuid", return_value=os.getuid() + 1):
            snapshot = self.store.read("chatgpt")
            self.assertEqual(snapshot.status, "unsafe")
            self.assertFalse(snapshot.effective)

    def test_atomic_publish_fsync_and_error_cleanup(self) -> None:
        fsync_fds: list[int] = []
        store = gpt_fast.PolicyStore(home=self.home, fsync=lambda fd: fsync_fds.append(fd))
        store.write("openai", True)
        self.assertGreaterEqual(len(fsync_fds), 2)
        self.assertEqual(stat.S_IMODE(store.state_dir.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(store.state_path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(store.lock_path.stat().st_mode), 0o600)
        self.assertEqual(list(store.state_dir.glob(".gpt_fast_policy.*.tmp")), [])

        original = store.state_path.read_bytes()

        def fail_replace(_source, _target, **_kwargs):
            raise OSError("injected replace failure")

        failing = gpt_fast.PolicyStore(home=self.home, replace=fail_replace)
        with self.assertRaises(gpt_fast.PolicyError) as raised:
            failing.write("openai", False)
        self.assertNotIsInstance(
            raised.exception, gpt_fast.PolicyDurabilityUncertain
        )
        self.assertEqual(store.state_path.read_bytes(), original)
        self.assertEqual(list(store.state_dir.glob(".gpt_fast_policy.*.tmp")), [])

    def test_directory_fsync_failure_reports_visible_commit_without_temp_leak(self) -> None:
        fsync_calls = 0

        def fail_directory_fsync(_fd: int) -> None:
            nonlocal fsync_calls
            fsync_calls += 1
            if fsync_calls == 2:
                raise OSError("injected directory fsync failure")

        store = gpt_fast.PolicyStore(home=self.home, fsync=fail_directory_fsync)
        with self.assertRaises(gpt_fast.PolicyDurabilityUncertain) as raised:
            store.write("chatgpt", True)
        self.assertEqual(raised.exception.backend_mode, "chatgpt")
        self.assertTrue(raised.exception.enabled)
        self.assertEqual(fsync_calls, 2)
        visible = store.read("chatgpt")
        self.assertEqual(visible.status, "ok")
        self.assertTrue(visible.enabled)
        self.assertTrue(visible.effective)
        self.assertEqual(
            store.state_path.read_bytes(),
            b'{"version":1,"backend_mode":"chatgpt","enabled":true}',
        )
        self.assertEqual(list(store.state_dir.glob(".gpt_fast_policy.*.tmp")), [])

    def test_reconciliation_preserves_post_replace_durability_uncertainty(self) -> None:
        self.store.write("openai", True)
        fsync_calls = 0

        def fail_directory_fsync(_fd: int) -> None:
            nonlocal fsync_calls
            fsync_calls += 1
            if fsync_calls == 2:
                raise OSError("injected directory fsync failure")

        store = gpt_fast.PolicyStore(home=self.home, fsync=fail_directory_fsync)
        result = store.normalize_backend("openai", native_fast_disabled=False)
        self.assertTrue(result.changed)
        self.assertEqual(result.status, "durability_uncertain")
        self.assertEqual(result.snapshot.status, "ok")
        self.assertFalse(result.snapshot.enabled)
        self.assertFalse(result.snapshot.effective)
        self.assertEqual(list(store.state_dir.glob(".gpt_fast_policy.*.tmp")), [])

    def test_concurrent_writers_serialize_and_readers_observe_only_complete_states(self) -> None:
        self.store.write("chatgpt", False)
        start = multiprocessing.Event()
        processes = [
            multiprocessing.Process(
                target=_writer_process,
                args=(str(self.home), backend, enabled, start),
            )
            for backend, enabled in (
                ("chatgpt", True),
                ("openai", True),
                ("chatgpt", False),
                ("openai", False),
            )
        ]
        for process in processes:
            process.start()
        start.set()
        observed: list[bytes] = []
        while any(process.is_alive() for process in processes):
            try:
                observed.append(self.store.state_path.read_bytes())
            except FileNotFoundError:
                pass
        for process in processes:
            process.join(5)
            self.assertEqual(process.exitcode, 0)
        observed.append(self.store.state_path.read_bytes())
        allowed = {
            json.dumps(
                {"version": 1, "backend_mode": backend, "enabled": enabled},
                separators=(",", ":"),
            ).encode("utf-8")
            for backend in ("chatgpt", "openai")
            for enabled in (True, False)
        }
        self.assertTrue(observed)
        self.assertTrue(set(observed) <= allowed)
        self.assertEqual(self.store.read().status, "ok")

    def test_route_switch_reset_and_no_resurrection(self) -> None:
        self.store.write("chatgpt", True)
        switched = self.store.normalize_backend("openai")
        self.assertTrue(switched.changed)
        self.assertEqual(switched.status, "reset")
        self.assertEqual(switched.snapshot.backend_mode, "openai")
        self.assertFalse(switched.snapshot.enabled)
        self.store.write("openai", True)
        returned = self.store.normalize_backend("chatgpt")
        self.assertTrue(returned.changed)
        self.assertEqual(returned.snapshot.backend_mode, "chatgpt")
        self.assertFalse(returned.snapshot.enabled)
        self.assertFalse(self.store.read("chatgpt").effective)

    def test_route_boundary_reconciliation_resets_current_route_on_distinctly(self) -> None:
        self.store.write("chatgpt", True)
        reconciled = self.store.normalize_backend(
            "chatgpt", route_boundary_valid=False, native_fast_disabled=True
        )
        self.assertTrue(reconciled.changed)
        self.assertEqual(reconciled.status, "reset_route_boundary")
        self.assertEqual(reconciled.snapshot.backend_mode, "chatgpt")
        self.assertFalse(reconciled.snapshot.enabled)
        self.assertFalse(reconciled.snapshot.effective)
        persisted = self.store.read("chatgpt")
        self.assertFalse(persisted.enabled)
        self.assertFalse(persisted.effective)

    def test_native_boundary_reconciliation_resets_current_route_on(self) -> None:
        self.store.write("chatgpt", True)
        reconciled = self.store.normalize_backend(
            "chatgpt", native_fast_disabled=False
        )
        self.assertTrue(reconciled.changed)
        self.assertEqual(reconciled.status, "reset_native_boundary")
        self.assertEqual(reconciled.snapshot.backend_mode, "chatgpt")
        self.assertFalse(reconciled.snapshot.enabled)
        self.assertFalse(reconciled.snapshot.effective)
        persisted = self.store.read("chatgpt")
        self.assertFalse(persisted.enabled)
        self.assertFalse(persisted.effective)

    def test_startup_normalization_preserves_concurrent_current_route_on(self) -> None:
        self.store.write("chatgpt", True)
        original_open_lock = self.store._open_writer_lock
        normalization_has_lock = threading.Event()
        allow_normalization = threading.Event()

        def gated_lock(directory_fd: int) -> int:
            lock_fd = original_open_lock(directory_fd)
            normalization_has_lock.set()
            allow_normalization.wait(3)
            return lock_fd

        gated = gpt_fast.PolicyStore(home=self.home)
        gated._open_writer_lock = gated_lock
        result: list[gpt_fast.NormalizationResult] = []
        thread = threading.Thread(
            target=lambda: result.append(gated.normalize_backend("openai")), daemon=True
        )
        thread.start()
        self.assertTrue(normalization_has_lock.wait(3))
        on_done = threading.Event()
        writer = threading.Thread(
            target=lambda: (self.store.write("openai", True), on_done.set()), daemon=True
        )
        writer.start()
        allow_normalization.set()
        thread.join(3)
        writer.join(3)
        self.assertTrue(on_done.is_set())
        self.assertEqual(self.store.read("openai").health_dict(), {
            "status": "ok", "backend_mode": "openai", "enabled": True, "effective": True
        })

    def test_invalid_and_unsafe_state_are_not_overwritten_by_normalization(self) -> None:
        self._seed_raw(b"malformed")
        before = self.store.state_path.read_bytes()
        result = self.store.normalize_backend("openai")
        self.assertFalse(result.changed)
        self.assertEqual(result.status, "invalid")
        self.assertEqual(self.store.state_path.read_bytes(), before)
        self.store.state_path.unlink()
        target = self.home / "unsafe-target"
        target.write_text("sentinel", encoding="utf-8")
        self.store.state_path.symlink_to(target)
        result = self.store.normalize_backend("openai")
        self.assertFalse(result.changed)
        self.assertEqual(result.status, "unsafe")
        self.assertEqual(target.read_text(encoding="utf-8"), "sentinel")


class ShimStartupPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
        self.home = SCRATCH_ROOT / f"gpt-fast-startup-{uuid.uuid4().hex}"
        self.home.mkdir(mode=0o700)

    def tearDown(self) -> None:
        shutil.rmtree(self.home, ignore_errors=True)

    def _load_shim(
        self,
        backend: str | None,
        native_fast_disable: str | None = "1",
        provider_shim: str | None = "openai",
    ):
        module_name = f"gpt_fast_startup_shim_{uuid.uuid4().hex}"
        environment = {
            "HOME": str(self.home),
            "SHIM_BACKEND_BASE_URL": "http://127.0.0.1:1/v1",
            "SHIM_BACKEND_API_KEY": "FABRICATED_TEST_ONLY",
            "OPENAI_API_KEY": "FABRICATED_TEST_ONLY",
            "DAAF_QUOTA_STATE_FILE": str(self.home / "quota.json"),
            "DAAF_REASONING_CACHE_FILE": str(self.home / "reasoning.json"),
        }
        if backend is not None:
            environment["SHIM_BACKEND_MODE"] = backend
        if provider_shim is not None:
            environment["DAAF_PROVIDER_SHIM"] = provider_shim
        if native_fast_disable is not None:
            environment["CLAUDE_CODE_DISABLE_FAST_MODE"] = native_fast_disable
        with mock.patch.dict(os.environ, environment, clear=True):
            spec = importlib.util.spec_from_file_location(
                module_name, SHIM_DIR / "anthropic_openai_shim.py"
            )
            if spec is None or spec.loader is None:
                raise RuntimeError("could not load production shim")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        return module

    def test_shim_startup_resets_other_route_on_and_recreation_clears_latest(self) -> None:
        store = gpt_fast.PolicyStore(home=self.home)
        store.write("chatgpt", True)
        first = self._load_shim("openai")
        try:
            reset = store.read("openai")
            self.assertEqual(reset.status, "ok")
            self.assertEqual(reset.backend_mode, "openai")
            self.assertFalse(reset.enabled)
            first._LATEST_TERMINAL = {
                "model": "gpt-fixture",
                "requested_service_tier": "priority",
                "requested_source": "shim_global",
                "served_service_tier": "priority",
                "completed_at": "2099-01-01T00:00:00Z",
            }
            store.write("openai", True)
            second = self._load_shim("openai")
            try:
                self.assertIsNone(second._LATEST_TERMINAL)
                self.assertTrue(store.read("openai").effective)
            finally:
                asyncio.run(second._client.aclose())
        finally:
            asyncio.run(first._client.aclose())

    def test_stale_on_is_reset_for_absent_empty_case_whitespace_and_malformed_native_boundary(self) -> None:
        variants = (
            ("absent", None),
            ("empty", ""),
            ("wrong-value", "0"),
            ("wrong-case", "TRUE"),
            ("leading-space", " 1"),
            ("trailing-space", "1 "),
            ("malformed", "01"),
        )
        store = gpt_fast.PolicyStore(home=self.home)
        for label, value in variants:
            with self.subTest(case=label, value=value):
                store.write("openai", True)
                module = self._load_shim("openai", value)
                try:
                    self.assertFalse(module._GPT_FAST_NATIVE_DISABLED)
                    self.assertEqual(
                        module._GPT_FAST_STARTUP_NORMALIZATION.status,
                        "reset_native_boundary",
                    )
                    persisted = store.read("openai")
                    self.assertEqual(persisted.status, "ok")
                    self.assertFalse(persisted.enabled)
                    self.assertFalse(persisted.effective)
                    health = module._gpt_service_tier_health_block()
                    self.assertFalse(health["native_fast_disabled"])
                    self.assertFalse(health["policy"]["enabled"])
                    self.assertFalse(health["policy"]["effective"])
                    requested, source = module._requested_service_tier(
                        {}, set(), module._GPT_FAST_STORE.read("openai")
                    )
                    self.assertIsNone(requested)
                    self.assertEqual(source, "none")
                finally:
                    asyncio.run(module._client.aclose())

    def test_raw_provider_backend_pair_controls_startup_health_and_activation(self) -> None:
        invalid_cases = (
            ("absent-provider-openai", None, "openai", "openai"),
            ("case-provider-openai", "OpenAI", "openai", "openai"),
            ("space-provider-chatgpt", " openai", "chatgpt", "chatgpt"),
            ("malformed-provider-openai", "other", "openai", "openai"),
            ("absent-backend", "openai", None, "openai"),
            ("case-backend", "openai", "OPENAI", "openai"),
            ("space-backend", "openai", " chatgpt ", "chatgpt"),
            ("malformed-backend", "openai", "other", "openai"),
        )
        store = gpt_fast.PolicyStore(home=self.home)
        for label, provider, raw_backend, selected_backend in invalid_cases:
            with self.subTest(case=label):
                store.write(selected_backend, True)
                module = self._load_shim(
                    raw_backend, provider_shim=provider
                )
                try:
                    self.assertEqual(module.SHIM_BACKEND_MODE, selected_backend)
                    self.assertFalse(module._GPT_FAST_ROUTE_VALID)
                    self.assertEqual(
                        module._GPT_FAST_STARTUP_NORMALIZATION.status,
                        "reset_route_boundary",
                    )
                    persisted = store.read(selected_backend)
                    self.assertEqual(persisted.status, "ok")
                    self.assertFalse(persisted.enabled)
                    self.assertFalse(persisted.effective)
                    health = module._gpt_service_tier_health_block()
                    self.assertFalse(health["policy"]["enabled"])
                    self.assertFalse(health["policy"]["effective"])
                    requested, source = module._requested_service_tier(
                        {}, set(), module._GPT_FAST_STORE.read(None)
                    )
                    self.assertIsNone(requested)
                    self.assertEqual(source, "none")
                finally:
                    asyncio.run(module._client.aclose())

        for backend, expected_tier in (("openai", "priority"), ("chatgpt", "priority")):
            with self.subTest(case=f"exact-{backend}"):
                store.write(backend, True)
                module = self._load_shim(backend, provider_shim="openai")
                try:
                    self.assertTrue(module._GPT_FAST_ROUTE_VALID)
                    self.assertEqual(module._GPT_FAST_STARTUP_NORMALIZATION.status, "ok")
                    health = module._gpt_service_tier_health_block()
                    self.assertTrue(health["policy"]["enabled"])
                    self.assertTrue(health["policy"]["effective"])
                    requested, source = module._requested_service_tier(
                        {}, set(), module._GPT_FAST_STORE.read(backend)
                    )
                    self.assertEqual(requested, expected_tier)
                    self.assertEqual(source, "shim_global")
                finally:
                    asyncio.run(module._client.aclose())

    def test_invalid_pair_health_and_request_fail_closed_when_reset_cannot_run(self) -> None:
        store = gpt_fast.PolicyStore(home=self.home)
        store.write("openai", True)
        before = store.state_path.read_bytes()
        with mock.patch.object(
            gpt_fast.PolicyStore,
            "normalize_backend",
            side_effect=gpt_fast.PolicyError("injected normalization failure"),
        ):
            module = self._load_shim("openai", provider_shim=None)
        try:
            self.assertFalse(module._GPT_FAST_ROUTE_VALID)
            self.assertIsNone(module._GPT_FAST_STARTUP_NORMALIZATION)
            self.assertEqual(store.state_path.read_bytes(), before)
            health = module._gpt_service_tier_health_block()
            self.assertEqual(health["policy"]["status"], "ok")
            self.assertTrue(health["policy"]["enabled"])
            self.assertFalse(health["policy"]["effective"])
            snapshot = module._GPT_FAST_STORE.read(None)
            requested, source = module._requested_service_tier({}, set(), snapshot)
            self.assertIsNone(requested)
            self.assertEqual(source, "none")
        finally:
            asyncio.run(module._client.aclose())

    def test_latest_terminal_cannot_regress_when_earlier_update_finishes_late(self) -> None:
        module = self._load_shim("openai")
        earlier_started = threading.Event()
        release_earlier = threading.Event()

        class DelayedEarlier(dict):
            def get(self, key, default=None):
                if key == "service_tier":
                    earlier_started.set()
                    if not release_earlier.wait(3):
                        raise RuntimeError("timed out waiting to release earlier terminal")
                return super().get(key, default)

        errors: list[BaseException] = []

        def record_earlier() -> None:
            try:
                module._actual_speed_from_response(
                    DelayedEarlier(model="gpt-earlier", service_tier="default")
                )
            except BaseException as error:
                errors.append(error)

        thread = threading.Thread(target=record_earlier, daemon=True)
        try:
            thread.start()
            self.assertTrue(earlier_started.wait(3))
            module._actual_speed_from_response(
                {"model": "gpt-later", "service_tier": "priority"}
            )
            release_earlier.set()
            thread.join(3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(module._LATEST_TERMINAL["model"], "gpt-later")
            self.assertEqual(
                module._LATEST_TERMINAL["served_service_tier"], "priority"
            )
        finally:
            release_earlier.set()
            asyncio.run(module._client.aclose())


class CLITests(unittest.TestCase):
    def setUp(self) -> None:
        SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
        self.home = SCRATCH_ROOT / f"gpt-fast-cli-{uuid.uuid4().hex}"
        self.home.mkdir(mode=0o700)
        self.store = gpt_fast.PolicyStore(home=self.home)

    def tearDown(self) -> None:
        shutil.rmtree(self.home, ignore_errors=True)

    def _run(self, command: str, environment: dict[str, str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, environment, clear=True):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = gpt_fast.main([command], store=self.store)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_exact_route_guard_matrix_and_rejected_mutations_are_byte_identical(self) -> None:
        valid = {
            "DAAF_PROVIDER_SHIM": "openai",
            "SHIM_BACKEND_MODE": "chatgpt",
            "CLAUDE_CODE_DISABLE_FAST_MODE": "1",
        }
        self.store.write("chatgpt", False)
        before = self.store.state_path.read_bytes()
        invalid_envs = (
            {},
            {"DAAF_PROVIDER_SHIM": "OpenAI", "SHIM_BACKEND_MODE": "chatgpt"},
            {"DAAF_PROVIDER_SHIM": "openai"},
            {"DAAF_PROVIDER_SHIM": "openai", "SHIM_BACKEND_MODE": "CHATGPT"},
            {"DAAF_PROVIDER_SHIM": "openai", "SHIM_BACKEND_MODE": "other"},
        )
        for environment in invalid_envs:
            for command in ("on", "off", "status"):
                with self.subTest(environment=environment, command=command):
                    code, _stdout, stderr = self._run(command, environment)
                    self.assertEqual(code, 20)
                    self.assertIn("exact", stderr)
                    self.assertEqual(self.store.state_path.read_bytes(), before)
        code, _stdout, _stderr = self._run("on", valid)
        self.assertEqual(code, 0)

    def test_on_requires_native_disable_while_off_and_status_remain_available(self) -> None:
        route = {"DAAF_PROVIDER_SHIM": "openai", "SHIM_BACKEND_MODE": "chatgpt"}
        invalid_values = (None, "", "0", "TRUE", " 1", "1 ", "01")
        self.store.write("chatgpt", True)
        persisted_on = self.store.state_path.read_bytes()
        for value in invalid_values:
            environment = dict(route)
            if value is not None:
                environment["CLAUDE_CODE_DISABLE_FAST_MODE"] = value
            with self.subTest(value=value):
                code, _stdout, stderr = self._run("on", environment)
                self.assertEqual(code, 20)
                self.assertIn("CLAUDE_CODE_DISABLE_FAST_MODE=1", stderr)
                self.assertEqual(self.store.state_path.read_bytes(), persisted_on)
                with mock.patch.object(gpt_fast, "_bounded_health", return_value=None):
                    code, stdout, _stderr = self._run("status", environment)
                self.assertEqual(code, 0)
                self.assertIn("Persisted requested policy: ON", stdout)
                self.assertIn("Effective requested policy: OFF", stdout)
                self.assertIn("Native Claude Code Fast disabled: no", stdout)
                self.assertIn("Shim: unavailable", stdout)
                self.assertIn("Latest terminal: unknown", stdout)
        code, stdout, _stderr = self._run("off", route)
        self.assertEqual(code, 0)
        self.assertIn("OFF", stdout)

    def test_status_labels_configured_and_latest_terminal_models_separately(self) -> None:
        environment = {
            "DAAF_PROVIDER_SHIM": "openai",
            "SHIM_BACKEND_MODE": "chatgpt",
            "SHIM_PORT": "4141",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "gpt-configured",
        }
        health = {
            "service": gpt_fast.HEALTH_SERVICE_ID,
            "version": "1.3.9",
            "backend_mode": "chatgpt",
            "gpt_service_tier": {
                "backend_mode": "chatgpt",
                "requested_tier_vocabulary": "priority",
                "policy": {
                    "status": "ok",
                    "backend_mode": "chatgpt",
                    "enabled": True,
                    "effective": True,
                },
                "native_fast_disabled": True,
                "latest_terminal": {
                    "model": "gpt-terminal",
                    "requested_service_tier": "priority",
                    "requested_source": "shim_global",
                    "served_service_tier": "default",
                    "completed_at": "2099-01-01T00:00:00Z",
                },
            },
        }
        self.store.write("chatgpt", True)
        with mock.patch.object(gpt_fast, "_bounded_health", return_value=health):
            code, stdout, _stderr = self._run("status", environment)
        self.assertEqual(code, 0)
        self.assertIn("Configured model: gpt-configured", stdout)
        self.assertIn("Latest terminal: model=gpt-terminal", stdout)
        self.assertIn("requested=priority", stdout)
        self.assertIn("friendly ChatGPT Fast label", stdout)
        self.assertIn("not API Priority billing", stdout)
        self.assertIn("served=default", stdout)
        self.assertIn("not proof", stdout)

    def test_health_reader_rejects_duplicates_and_returns_only_bounded_projection(self) -> None:
        payload = {
            "service": gpt_fast.HEALTH_SERVICE_ID,
            "version": "1.3.9",
            "backend_mode": "openai",
            "backend": "file:///sensitive/unrelated/path",
            "unrelated": {"content": "must-not-be-returned"},
            "gpt_service_tier": {
                "backend_mode": "openai",
                "requested_tier_vocabulary": "priority",
                "policy": {
                    "status": "ok",
                    "backend_mode": "openai",
                    "enabled": True,
                    "effective": True,
                },
                "native_fast_disabled": True,
                "latest_terminal": {
                    "model": "gpt-terminal",
                    "requested_service_tier": "priority",
                    "requested_source": "shim_global",
                    "served_service_tier": "default",
                    "completed_at": "2099-01-01T00:00:00Z",
                },
            },
        }

        class FakeResponse:
            status = 200

            def __init__(self, raw: bytes):
                self.raw = raw

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return None

            def read(self, limit: int) -> bytes:
                self.read_limit = limit
                return self.raw[:limit]

        class FakeOpener:
            def __init__(self, raw: bytes):
                self.raw = raw

            def open(self, _request, timeout):
                self.timeout = timeout
                self.response = FakeResponse(self.raw)
                return self.response

        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        fake_opener = FakeOpener(raw)
        with mock.patch.object(
            gpt_fast.urllib.request,
            "build_opener",
            return_value=fake_opener,
        ) as build:
            bounded = gpt_fast._bounded_health("http://127.0.0.1:1/health")
        self.assertEqual(
            set(bounded),
            {"service", "version", "backend_mode", "gpt_service_tier"},
        )
        self.assertEqual(fake_opener.timeout, gpt_fast.HEALTH_TIMEOUT_SECONDS)
        self.assertEqual(
            fake_opener.response.read_limit, gpt_fast.HEALTH_BODY_LIMIT + 1
        )
        handlers = build.call_args.args
        self.assertTrue(
            any(
                isinstance(item, gpt_fast.urllib.request.ProxyHandler)
                and item.proxies == {}
                for item in handlers
            )
        )
        redirect = next(
            item for item in handlers if isinstance(item, gpt_fast._RejectRedirects)
        )
        self.assertIsNone(
            redirect.redirect_request(
                None, None, 302, "Found", {}, "http://example.invalid"
            )
        )
        serialized = json.dumps(bounded)
        self.assertNotIn("sensitive", serialized)
        self.assertNotIn("must-not-be-returned", serialized)

        with mock.patch.object(gpt_fast.urllib.request, "build_opener") as external:
            self.assertIsNone(gpt_fast._bounded_health("http://example.invalid/health"))
        external.assert_not_called()

        duplicate = raw.replace(
            b'{"service":',
            b'{"service":"duplicate","service":',
            1,
        )
        with mock.patch.object(
            gpt_fast.urllib.request,
            "build_opener",
            return_value=FakeOpener(duplicate),
        ):
            self.assertIsNone(
                gpt_fast._bounded_health("http://127.0.0.1:1/health")
            )

        oversized = b"{" + b"x" * gpt_fast.HEALTH_BODY_LIMIT
        with mock.patch.object(
            gpt_fast.urllib.request,
            "build_opener",
            return_value=FakeOpener(oversized),
        ):
            self.assertIsNone(
                gpt_fast._bounded_health("http://127.0.0.1:1/health")
            )

    def test_health_latest_terminal_requires_route_source_tier_and_real_utc_semantics(self) -> None:
        class FakeResponse:
            status = 200

            def __init__(self, raw: bytes):
                self.raw = raw

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return None

            def read(self, limit: int) -> bytes:
                self.read_limit = limit
                return self.raw[:limit]

        class FakeOpener:
            def __init__(self, raw: bytes):
                self.raw = raw

            def open(self, _request, timeout):
                return FakeResponse(self.raw)

        def bounded(payload):
            raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            with mock.patch.object(
                gpt_fast.urllib.request, "build_opener", return_value=FakeOpener(raw)
            ):
                return gpt_fast._bounded_health("http://127.0.0.1:1/health")

        for backend, expected_tier in (("chatgpt", "priority"), ("openai", "priority")):
            base = {
                "service": gpt_fast.HEALTH_SERVICE_ID,
                "version": "1.3.9",
                "backend_mode": backend,
                "gpt_service_tier": {
                    "backend_mode": backend,
                    "requested_tier_vocabulary": expected_tier,
                    "policy": {
                        "status": "ok", "backend_mode": backend,
                        "enabled": False, "effective": False,
                    },
                    "native_fast_disabled": True,
                    "latest_terminal": {
                        "model": "gpt-5.6-sol",
                        "requested_service_tier": expected_tier,
                        "requested_source": "shim_global",
                        "served_service_tier": None,
                        "completed_at": "2026-07-25T20:00:00Z",
                    },
                },
            }
            with self.subTest(backend=backend, case="valid-null-served"):
                self.assertIsNotNone(bounded(base))
            compatibility = json.loads(json.dumps(base))
            compatibility["gpt_service_tier"]["latest_terminal"][
                "served_service_tier"
            ] = "fast"
            with self.subTest(backend=backend, case="compatibility-only-served-fast"):
                self.assertIsNotNone(bounded(compatibility))
            legacy_vocabulary = json.loads(json.dumps(base))
            legacy_vocabulary["gpt_service_tier"]["requested_tier_vocabulary"] = "fast"
            with self.subTest(backend=backend, case="legacy-requested-vocabulary-fast"):
                self.assertIsNone(bounded(legacy_vocabulary))
            invalid_changes = (
                # Legacy requested `fast` is never authoritative requested vocabulary.
                ("requested_service_tier", "fast"),
                ("requested_service_tier", f" {expected_tier}"),
                ("requested_source", "Shim_Global"),
                ("requested_source", ["shim_global"]),
                ("requested_source", " shim_global"),
                ("served_service_tier", "FAST"),
                ("served_service_tier", {"tier": "fast"}),
                ("served_service_tier", "fast "),
                ("completed_at", "2026-02-30T20:00:00Z"),
                ("completed_at", "2026-07-25t20:00:00Z"),
            )
            for field, value in invalid_changes:
                payload = json.loads(json.dumps(base))
                payload["gpt_service_tier"]["latest_terminal"][field] = value
                with self.subTest(backend=backend, field=field, value=value):
                    self.assertIsNone(bounded(payload))
            for source, requested in (("none", expected_tier), ("shim_global", None)):
                payload = json.loads(json.dumps(base))
                latest = payload["gpt_service_tier"]["latest_terminal"]
                latest["requested_source"] = source
                latest["requested_service_tier"] = requested
                with self.subTest(backend=backend, source=source, requested=requested):
                    self.assertIsNone(bounded(payload))
            payload = json.loads(json.dumps(base))
            latest = payload["gpt_service_tier"]["latest_terminal"]
            latest["requested_source"] = "none"
            latest["requested_service_tier"] = None
            with self.subTest(backend=backend, case="valid-null-requested"):
                self.assertIsNotNone(bounded(payload))

    def test_cli_reports_visible_on_with_uncertain_durability_honestly(self) -> None:
        fsync_calls = 0

        def fail_directory_fsync(_fd: int) -> None:
            nonlocal fsync_calls
            fsync_calls += 1
            if fsync_calls == 2:
                raise OSError("injected directory fsync failure")

        self.store = gpt_fast.PolicyStore(
            home=self.home, fsync=fail_directory_fsync
        )
        environment = {
            "DAAF_PROVIDER_SHIM": "openai",
            "SHIM_BACKEND_MODE": "chatgpt",
            "CLAUDE_CODE_DISABLE_FAST_MODE": "1",
        }
        code, stdout, stderr = self._run("on", environment)
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("policy ON is visible", stderr)
        self.assertIn("durability is uncertain", stderr)
        self.assertIn("not rolled back", stderr)
        self.assertNotIn("could not enable", stderr)
        self.assertLess(len(stderr), 500)
        visible = self.store.read("chatgpt")
        self.assertTrue(visible.enabled)
        self.assertTrue(visible.effective)
        self.assertEqual(list(self.store.state_dir.glob(".gpt_fast_policy.*.tmp")), [])

    def test_api_on_prints_cost_warning_and_status_never_claims_served(self) -> None:
        environment = {
            "DAAF_PROVIDER_SHIM": "openai",
            "SHIM_BACKEND_MODE": "openai",
            "CLAUDE_CODE_DISABLE_FAST_MODE": "1",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "gpt-5.6-sol",
        }
        code, stdout, stderr = self._run("on", environment)
        self.assertEqual(code, 0)
        self.assertIn("Priority", stdout)
        self.assertIn("change API cost", stderr)
        with mock.patch.object(gpt_fast, "_bounded_health", return_value=None):
            code, status, _stderr = self._run("status", environment)
        self.assertEqual(code, 0)
        self.assertIn("Configured model: gpt-5.6-sol", status)
        self.assertIn("requested", status.lower())
        self.assertIn("not proof", status)
        self.assertNotIn("served Priority: yes", status)


class ShimPolicyIntegrationTests(unittest.TestCase):
    maxDiff = 16000

    def test_off_omits_and_on_adds_route_specific_tier_with_source(self) -> None:
        for backend, tier in (("openai", "priority"), ("chatgpt", "priority")):
            for enabled in (False, True):
                with self.subTest(backend=backend, enabled=enabled):
                    report = controlled_asgi_probe(
                        stream=False,
                        backend_mode=backend,
                        global_policy_enabled=enabled,
                    )
                    self.assertIsNone(report.raised)
                    self.assertEqual(report.upstream_calls, 1)
                    outbound = report.outbound_payloads[0]
                    terminal = _terminal_fields(report.lifecycle)
                    if enabled:
                        self.assertEqual(outbound["service_tier"], tier)
                        self.assertEqual(terminal["requested_service_tier"], tier)
                        self.assertEqual(
                            terminal["requested_service_tier_source"], "shim_global"
                        )
                    else:
                        self.assertNotIn("service_tier", outbound)
                        self.assertEqual(terminal["requested_service_tier"], "-")
                        self.assertEqual(
                            terminal["requested_service_tier_source"], "none"
                        )

    def test_inbound_fast_additive_precedence_and_invalid_contract_under_global_on(self) -> None:
        beta = [(b"anthropic-beta", b"fast-mode-2026-02-01")]
        for backend in ("openai", "chatgpt"):
            for enabled, expected_source in ((False, "anthropic"), (True, "both")):
                with self.subTest(backend=backend, enabled=enabled):
                    report = controlled_asgi_probe(
                        stream=False,
                        backend_mode=backend,
                        global_policy_enabled=enabled,
                        raw_request_body=_request_body(speed="fast"),
                        raw_scope_headers=beta,
                    )
                    self.assertEqual(
                        report.outbound_payloads[0]["service_tier"], "priority"
                    )
                    self.assertEqual(
                        _terminal_fields(report.lifecycle)[
                            "requested_service_tier_source"
                        ],
                        expected_source,
                    )
            invalid = controlled_asgi_probe(
                stream=False,
                backend_mode=backend,
                global_policy_enabled=True,
                raw_request_body=_request_body(speed="FAST"),
                raw_scope_headers=beta,
            )
            self.assertEqual(invalid.upstream_calls, 0)
            self.assertEqual(invalid.outbound_payloads, [])
            starts = [
                message
                for message in invalid.messages
                if message["type"] == "http.response.start"
            ]
            self.assertEqual(starts[0]["status"], 400)
            self.assertIsNone(invalid.gpt_service_tier_health["latest_terminal"])

    def test_request_snapshot_precedes_body_read_and_survives_toggle(self) -> None:
        old_off = controlled_asgi_probe(
            stream=False,
            backend_mode="openai",
            global_policy_enabled=False,
            toggle_policy_on_first_receive=True,
        )
        self.assertNotIn("service_tier", old_off.outbound_payloads[0])
        old_on = controlled_asgi_probe(
            stream=False,
            backend_mode="openai",
            global_policy_enabled=True,
            toggle_policy_on_first_receive=False,
        )
        self.assertEqual(old_on.outbound_payloads[0]["service_tier"], "priority")

    def test_retry_reuses_global_snapshot_and_identical_payload(self) -> None:
        scenario = terminal_contract_scenario(
            "global-retry",
            "response.completed",
            status="completed",
            output=[],
            usage={"input_tokens": 10, "output_tokens": 2},
            service_tier="priority",
        )
        report = controlled_asgi_probe(
            scenario=scenario,
            stream=False,
            backend_mode="openai",
            global_policy_enabled=True,
            attempt_outcomes=[503, 200],
        )
        self.assertEqual(report.upstream_calls, 2)
        self.assertEqual(report.outbound_payloads[0], report.outbound_payloads[1])
        self.assertEqual(report.outbound_payloads[0]["service_tier"], "priority")
        terminal = _terminal_fields(report.lifecycle)
        self.assertEqual(terminal["attempts"], "2")
        self.assertEqual(terminal["requested_service_tier_source"], "shim_global")

    def test_auth_and_stale_reasoning_retries_preserve_snapshotted_tier(self) -> None:
        auth = controlled_asgi_probe(
            stream=False,
            backend_mode="chatgpt",
            global_policy_enabled=True,
            lazy_401_refresh=True,
            attempt_outcomes=[401, 200],
        )
        self.assertIsNone(auth.raised)
        self.assertEqual(auth.upstream_calls, 2)
        self.assertEqual(
            [payload["service_tier"] for payload in auth.outbound_payloads],
            ["priority", "priority"],
        )
        self.assertEqual(
            _terminal_fields(auth.lifecycle)["requested_service_tier_source"],
            "shim_global",
        )

        scenario = terminal_contract_scenario(
            "stale-reasoning-tier",
            "response.completed",
            status="completed",
            output=[],
            usage={"input_tokens": 10, "output_tokens": 2},
            service_tier="priority",
        )
        scenario.stream_error_body = (
            b'{"error":{"type":"invalid_request_error",'
            b'"message":"invalid encrypted_content reasoning fixture"}}'
        )
        stale = controlled_asgi_probe(
            scenario=scenario,
            stream=False,
            backend_mode="openai",
            global_policy_enabled=True,
            inject_stale_restored_reasoning=True,
            attempt_outcomes=[400, 200],
        )
        self.assertIsNone(stale.raised)
        self.assertEqual(stale.upstream_calls, 2)
        self.assertEqual(
            [payload["service_tier"] for payload in stale.outbound_payloads],
            ["priority", "priority"],
        )
        stale_terminal = _terminal_fields(stale.lifecycle)
        self.assertEqual(stale_terminal["retry_reason"], "stale_reasoning_400")
        self.assertEqual(stale_terminal["requested_service_tier_source"], "shim_global")

    def test_strict_pair_matrix_fails_global_policy_closed_without_retry_drift(self) -> None:
        invalid_cases = (
            ("absent-provider", None, "openai", "openai"),
            ("case-provider", "OpenAI", "openai", "openai"),
            ("space-provider", " openai", "chatgpt", "chatgpt"),
            ("malformed-provider", "other", "openai", "openai"),
            ("absent-backend", "openai", None, "openai"),
            ("case-backend", "openai", "OPENAI", "openai"),
            ("space-backend", "openai", " chatgpt ", "chatgpt"),
            ("malformed-backend", "openai", "other", "openai"),
        )
        for label, provider, raw_backend, selected_backend in invalid_cases:
            with self.subTest(case=label):
                report = controlled_asgi_probe(
                    stream=False,
                    backend_mode=selected_backend,
                    provider_shim_control=provider,
                    backend_mode_control=raw_backend,
                    preexisting_global_policy_enabled=True,
                    attempt_outcomes=[503, 200],
                )
                self.assertIsNone(report.raised)
                self.assertEqual(report.upstream_calls, 2)
                self.assertEqual(report.outbound_payloads[0], report.outbound_payloads[1])
                self.assertNotIn("service_tier", report.outbound_payloads[0])
                health = report.gpt_service_tier_health
                self.assertEqual(health["policy"]["status"], "ok")
                self.assertFalse(health["policy"]["enabled"])
                self.assertFalse(health["policy"]["effective"])
                terminal = _terminal_fields(report.lifecycle)
                self.assertEqual(terminal["attempts"], "2")
                self.assertEqual(terminal["retries"], "1")
                self.assertEqual(terminal["requested_service_tier"], "-")
                self.assertEqual(terminal["requested_service_tier_source"], "none")

    def test_invalid_pair_request_and_health_fail_closed_with_persisted_on(self) -> None:
        report = controlled_asgi_probe(
            stream=False,
            backend_mode="openai",
            provider_shim_control=None,
            backend_mode_control="openai",
            global_policy_enabled=True,
        )
        self.assertIsNone(report.raised)
        self.assertNotIn("service_tier", report.outbound_payloads[0])
        health = report.gpt_service_tier_health
        self.assertEqual(health["policy"]["status"], "ok")
        self.assertTrue(health["policy"]["enabled"])
        self.assertFalse(health["policy"]["effective"])
        terminal = _terminal_fields(report.lifecycle)
        self.assertEqual(terminal["requested_service_tier"], "-")
        self.assertEqual(terminal["requested_service_tier_source"], "none")

    def test_inbound_fast_remains_independent_when_strict_pair_is_absent(self) -> None:
        beta = [(b"anthropic-beta", b"fast-mode-2026-02-01")]
        cases = (
            ("legacy-default-openai", None, None, "openai", "priority"),
            (
                "legacy-normalized-chatgpt",
                None,
                " CHATGPT ",
                "chatgpt",
                "priority",
            ),
        )
        for label, provider, raw_backend, selected_backend, tier in cases:
            with self.subTest(case=label):
                report = controlled_asgi_probe(
                    stream=False,
                    backend_mode=selected_backend,
                    provider_shim_control=provider,
                    backend_mode_control=raw_backend,
                    preexisting_global_policy_enabled=True,
                    raw_request_body=_request_body(speed="fast"),
                    raw_scope_headers=beta,
                )
                self.assertIsNone(report.raised)
                self.assertEqual(report.outbound_payloads[0]["service_tier"], tier)
                self.assertFalse(report.gpt_service_tier_health["policy"]["effective"])
                terminal = _terminal_fields(report.lifecycle)
                self.assertEqual(terminal["requested_service_tier"], tier)
                self.assertEqual(
                    terminal["requested_service_tier_source"], "anthropic"
                )

    def test_request_fails_closed_after_stale_on_with_invalid_native_boundary(self) -> None:
        variants = (None, "", "0", "TRUE", " 1", "1 ", "01")
        for value in variants:
            with self.subTest(value=value):
                # The harness intentionally inherits runner seams. Make the absent case
                # independent of the developer container's own route configuration.
                with mock.patch.dict(os.environ, {}, clear=False):
                    if value is None:
                        os.environ.pop("CLAUDE_CODE_DISABLE_FAST_MODE", None)
                    report = controlled_asgi_probe(
                        stream=False,
                        backend_mode="openai",
                        native_fast_disable=value,
                        preexisting_global_policy_enabled=True,
                    )
                self.assertIsNone(report.raised)
                self.assertEqual(report.auth_calls, 1)
                self.assertEqual(report.upstream_calls, 1)
                self.assertNotIn("service_tier", report.outbound_payloads[0])
                health = report.gpt_service_tier_health
                self.assertFalse(health["native_fast_disabled"])
                self.assertEqual(health["policy"]["status"], "ok")
                self.assertFalse(health["policy"]["enabled"])
                self.assertFalse(health["policy"]["effective"])
                terminal = _terminal_fields(report.lifecycle)
                self.assertEqual(terminal["requested_service_tier"], "-")
                self.assertEqual(
                    terminal["requested_service_tier_source"], "none"
                )

    def test_request_time_exact_route_match_is_required(self) -> None:
        # Import/startup selects openai, then a deliberately other-bound valid policy is
        # published before request acceptance. The lock-free request read must fail OFF.
        report = controlled_asgi_probe(
            stream=False,
            backend_mode="openai",
            global_policy_enabled=True,
            global_policy_backend="chatgpt",
        )
        self.assertNotIn("service_tier", report.outbound_payloads[0])

    def test_immediate_off_on_off_in_one_running_shim_and_latest_health(self) -> None:
        scenario = full_response_scenario()
        scenario.nonstream_response["service_tier"] = "priority"
        scenario.nonstream_response["model"] = "gpt-fixture-terminal"
        with MockResponsesServer(scenario) as backend:
            with RealShim(
                backend,
                "openai",
                env_overrides={"CLAUDE_CODE_DISABLE_FAST_MODE": "1"},
            ) as shim:
                assert shim.scratch_dir is not None
                store = gpt_fast.PolicyStore(home=shim.scratch_dir)
                store.write("openai", False)
                off1 = shim.post_messages(stream=False)
                store.write("openai", True)
                on = shim.post_messages(stream=False)
                on_latest = shim.get_health().json()["gpt_service_tier"]["latest_terminal"]
                self.assertEqual(on_latest["requested_service_tier"], "priority")
                self.assertEqual(on_latest["requested_source"], "shim_global")
                self.assertEqual(on_latest["served_service_tier"], "priority")
                store.write("openai", False)
                off2 = shim.post_messages(stream=False)
                self.assertEqual(
                    ["service_tier" in request.body for request in backend.responses_requests],
                    [False, True, False],
                )
                self.assertEqual(
                    backend.responses_requests[1].body["service_tier"], "priority"
                )
                self.assertEqual(
                    _terminal_fields(lifecycle_for_response(shim, on))[
                        "requested_service_tier_source"
                    ],
                    "shim_global",
                )
                health = shim.get_health().json()["gpt_service_tier"]
                self.assertEqual(
                    set(health),
                    {
                        "backend_mode",
                        "requested_tier_vocabulary",
                        "policy",
                        "native_fast_disabled",
                        "latest_terminal",
                    },
                )
                self.assertEqual(health["backend_mode"], "openai")
                self.assertEqual(health["requested_tier_vocabulary"], "priority")
                self.assertFalse(health["policy"]["effective"])
                latest = health["latest_terminal"]
                self.assertEqual(latest["model"], "gpt-fixture-terminal")
                self.assertIsNone(latest["requested_service_tier"])
                self.assertEqual(latest["requested_source"], "none")
                self.assertEqual(latest["served_service_tier"], "priority")
                self.assertRegex(latest["completed_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
                for forbidden in ("request_id", "prompt", "messages", "tools", "path", "credential"):
                    self.assertNotIn(forbidden, json.dumps(health).lower())
                self.assertEqual(off1.status, 200)
                self.assertEqual(off2.status, 200)

    def test_latest_terminal_unknown_or_malformed_served_tier_stays_null(self) -> None:
        scenario = full_response_scenario()
        scenario.nonstream_response["service_tier"] = " Priority\r\nFORGED=1"
        scenario.nonstream_response["model"] = "bad model\nforged"
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(stream=False)
                self.assertEqual(result.status, 200)
                latest = shim.get_health().json()["gpt_service_tier"]["latest_terminal"]
                self.assertIsNone(latest["model"])
                self.assertIsNone(latest["served_service_tier"])
                self.assertEqual(latest["requested_source"], "none")
                serialized = json.dumps(latest)
                self.assertNotIn("FORGED", serialized)
                self.assertNotIn("bad model", serialized)


if __name__ == "__main__":
    unittest.main()
