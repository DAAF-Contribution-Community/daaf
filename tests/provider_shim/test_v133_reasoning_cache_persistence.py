"""Deterministic contracts for the v1.3.3 reasoning-cache persistence layer (A2).

The in-memory ``_REASONING_CACHE`` (an LRU ``OrderedDict`` keyed by ``call_id`` ->
reasoning item WITH its opaque ``encrypted_content`` blob) is module-global and, before
v1.3.3, was lost on every restart — a restart mid-session then replayed the tool history
WITHOUT its reasoning items (graceful misses, but degraded model context for the rest of
a long tool loop). v1.3.3 persists a bounded newest-first snapshot on each cache mutation
and restores it at module import, so reasoning continuity survives a restart.

Precedent: the write path mirrors ``_write_quota_state`` exactly (atomic mkstemp +
os.replace, 0600, whole-body fail-open) and the ``DAAF_REASONING_CACHE_FILE`` seam mirrors
``DAAF_QUOTA_STATE_FILE`` (resolved at module import). The one NEW hazard restore
introduces over quota_state (which is write-only) is that a seam file written by one
in-process shim load would be RESTORED into a later fresh in-process load — the harness
neutralizes this by unlinking the runner-default seam before each in-process fresh load
(``_purge_in_process_reasoning_cache_seam``) and by giving each spawned RealShim its own
per-instance scratch seam. Tests here that load the module in-process always pin a UNIQUE
per-test seam so their import-time restore is hermetic.

Design note (A2-R4, amended): the production default path is HOME-derived
(``$HOME/.claude/provider_shim/reasoning_cache.json``) — deliberately OUTSIDE the /daaf
repo tree, on the per-container claude-config volume — because reasoning blobs are
relatively private and must not sit in a shareable/committable directory. quota_state.json
(scrubbed operational telemetry) stays in the repo's logs/ dir; only the content-bearing
artifact moves.

Tests (design § 6):

1. Spawned shim writes the seam file after a reasoning+tool response: exists, 0600, shape
   valid, entries ordered.
2. Restart-restore end-to-end (the money test): RealShim #1 completes a reasoning+tool
   turn -> shutdown; RealShim #2 pointed at the SAME seam file -> turn-2 replay -> the
   reasoning item is injected immediately before its function_call, terminal
   reasoning_cache_miss=0.
3. Missing/corrupt file -> clean start, miss=1, no raise (fail-open).
4. Stale file (captured_at older than the 30-day sanity ceiling) -> not restored.
5. Restore preserves LRU order; restored entries evict in correct order.
6. Entry-count and byte bounds keep the NEWEST entries.
7. Non-pollution guards for the production HOME default path (spawned + in-process
   variants, retry-once bracket + non-vacuity, mirroring test_v131_quota_state.py).
8. LRU eviction/cap unit test for the in-memory cache (pre-existing coverage gap).
9. Out-of-process path-derivation probe: seam wins; default derives from HOME.
"""

from __future__ import annotations

import importlib.util
import json
import os
import site
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

from ._loopback_harness import (
    PRODUCTION_SHIM,
    READ_TOOL,
    MockResponsesServer,
    RealShim,
    _nonstream_response,
    controlled_asgi_probe,
    full_response_scenario,
    lifecycle_for_response,
    parse_typed_sse,
)


def _load_shim_module(seam_path: Path):
    """Import a fresh production shim in-process, pinning DAAF_REASONING_CACHE_FILE to
    ``seam_path`` for the duration of the load so the module's import-time restore reads
    exactly that file (or nothing, if absent) — never a leaked runner-default seam."""
    module_name = f"provider_shim_reasoning_probe_{uuid.uuid4().hex}"
    with mock.patch.dict(
        os.environ, {"DAAF_REASONING_CACHE_FILE": str(seam_path)}
    ):
        spec = importlib.util.spec_from_file_location(module_name, PRODUCTION_SHIM)
        if spec is None or spec.loader is None:
            raise RuntimeError("could not load production shim for reasoning-cache probe")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


def _reasoning(item_id: str) -> dict[str, object]:
    """A minimal, well-shaped reasoning item carrying an opaque encrypted_content blob."""
    return {
        "type": "reasoning",
        "id": item_id,
        "status": "completed",
        "summary": [],
        "encrypted_content": f"ENC_{item_id}",
    }


def _seam_payload(pairs, captured_at=None) -> dict[str, object]:
    """Build a persisted-file payload from (call_id, item) pairs in oldest->newest order."""
    return {
        "captured_at": int(time.time()) if captured_at is None else int(captured_at),
        "entries": [[cid, item] for cid, item in pairs],
    }


def _tool_use_replay_messages(call_id: str):
    """A two-message turn whose assistant tool_use references ``call_id`` (so the shim's
    re-injection path looks the reasoning item up in the restored cache) followed by its
    user tool_result."""
    return [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": call_id,
                    "name": "Read",
                    "input": {"file_path": "/daaf/README.md"},
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": call_id,
                    "content": "replay result",
                }
            ],
        },
    ]


class ReasoningCacheWriteAndRestoreTests(unittest.TestCase):
    """Tests 1-6, 8: write shape, restart-restore, fail-open, staleness, bounds, LRU."""

    maxDiff = 12000

    def _fresh_module(self, *, existing_payload=None):
        """Load a fresh in-process shim against a unique per-test seam. If
        ``existing_payload`` is given it is written to the seam BEFORE the load so the
        module restores it at import; otherwise the seam is absent and the module starts
        cold. Returns (module, seam_path)."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        seam_path = Path(tmp.name) / "reasoning_cache.json"
        if existing_payload is not None:
            seam_path.write_text(
                json.dumps(existing_payload), encoding="utf-8"
            )
        return _load_shim_module(seam_path), seam_path

    # --- Test 1: spawned shim writes the seam file after a reasoning+tool response ---
    def test_spawned_shim_writes_seam_file_after_reasoning_tool_response(self) -> None:
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                # __enter__ seams DAAF_REASONING_CACHE_FILE to this instance's scratch dir.
                seam_path = Path(shim.child_env["DAAF_REASONING_CACHE_FILE"])
                self.assertEqual(seam_path, shim.scratch_dir / "reasoning_cache.json")

                result = shim.post_messages(stream=False, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                # The write fires synchronously inside the non-stream translation, so it
                # has certainly landed by the time the 200 body is in hand; drain the
                # lifecycle log for good measure.
                lifecycle_for_response(shim, result)

                self.assertTrue(
                    seam_path.exists(), "reasoning cache was not persisted to the seam"
                )
                # Same telemetry-hygiene contract as quota_state: 0600.
                self.assertEqual(
                    stat.S_IMODE(os.stat(seam_path).st_mode), 0o600
                )
                payload = json.loads(seam_path.read_text(encoding="utf-8"))
                self.assertIsInstance(payload["captured_at"], int)
                entries = payload["entries"]
                self.assertIsInstance(entries, list)
                self.assertGreaterEqual(len(entries), 1)
                # The fixture pairs reasoning rs_full with function_call call_full_fixture.
                by_call = {cid: item for cid, item in entries}
                self.assertIn("call_full_fixture", by_call)
                self.assertEqual(
                    by_call["call_full_fixture"]["encrypted_content"], "ENC_rs_full"
                )
                self.assertEqual(by_call["call_full_fixture"]["type"], "reasoning")
                # No temp sibling left behind after the atomic publish.
                siblings = sorted(seam_path.parent.glob("reasoning_cache.*.tmp"))
                self.assertEqual(siblings, [])

    # --- Test 2: restart-restore end-to-end (the money test) ---
    def test_restart_restore_end_to_end_replays_reasoning(self) -> None:
        # A shared seam OUTSIDE either RealShim's scratch dir so it survives shim #1's
        # __exit__ (which rmtrees only that instance's scratch).
        shared_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(shared_tmp.cleanup)
        shared_seam = Path(shared_tmp.name) / "reasoning_cache.json"

        # Turn 1: shim #1 completes a reasoning+tool turn -> persists to the shared seam.
        scenario1 = full_response_scenario()
        with MockResponsesServer(scenario1) as backend1:
            with RealShim(
                backend1,
                "openai",
                env_overrides={"DAAF_REASONING_CACHE_FILE": str(shared_seam)},
            ) as shim1:
                first = shim1.post_messages(stream=False, tools=[READ_TOOL])
                self.assertEqual(first.status, 200, first.text)
                first_content = first.json()["content"]
                lifecycle_for_response(shim1, first)
        # shim #1 is now shut down; the persisted snapshot must survive.
        self.assertTrue(
            shared_seam.exists(), "shim #1 did not persist a snapshot to the shared seam"
        )

        # Turn 2: shim #2 (fresh process, SAME seam) restores at import and replays.
        scenario2 = full_response_scenario()
        scenario2.nonstream_responses = [
            _nonstream_response("resp_replay_followup", [])
        ]
        with MockResponsesServer(scenario2) as backend2:
            with RealShim(
                backend2,
                "openai",
                env_overrides={"DAAF_REASONING_CACHE_FILE": str(shared_seam)},
            ) as shim2:
                # /health reports the restore (counts only).
                health = shim2.get_health().json()
                self.assertIn("reasoning_cache", health)
                self.assertGreaterEqual(health["reasoning_cache"]["restored"], 1)
                self.assertGreaterEqual(health["reasoning_cache"]["entries"], 1)

                replay = shim2.post_messages(
                    stream=False,
                    tools=[READ_TOOL],
                    messages=[
                        {"role": "assistant", "content": first_content},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "call_full_fixture",
                                    "content": "paired result",
                                }
                            ],
                        },
                    ],
                )
                self.assertEqual(replay.status, 200, replay.text)

                # The outgoing backend request must carry the restored reasoning item
                # immediately BEFORE its function_call (the pinned before-call ordering).
                replay_request = backend2.responses_requests[-1].body
                replay_input = replay_request["input"]
                function_at = next(
                    index
                    for index, item in enumerate(replay_input)
                    if item.get("type") == "function_call"
                    and item.get("call_id") == "call_full_fixture"
                )
                self.assertGreater(function_at, 0)
                injected = replay_input[function_at - 1]
                self.assertEqual(injected.get("type"), "reasoning")
                self.assertEqual(injected.get("encrypted_content"), "ENC_rs_full")

                # Terminal telemetry: the restored entry produced a HIT, not a miss.
                replay_lifecycle = lifecycle_for_response(shim2, replay)
                terminal = next(
                    line for line in replay_lifecycle if line.event == "terminal"
                )
                self.assertEqual(terminal.fields["reasoning_cache_miss"], "0")

    # --- Test 3: missing / corrupt file -> clean start, miss=1, no raise ---
    def test_missing_file_starts_cold(self) -> None:
        module, seam_path = self._fresh_module()  # seam absent
        self.assertFalse(seam_path.exists())
        self.assertEqual(module._REASONING_CACHE_RESTORED, 0)
        self.assertEqual(len(module._REASONING_CACHE), 0)

    def test_corrupt_file_starts_cold_without_raising(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        seam_path = Path(tmp.name) / "reasoning_cache.json"
        seam_path.write_text("{ this is not valid json ]", encoding="utf-8")
        # Must not raise on import; restore silently yields nothing.
        module = _load_shim_module(seam_path)
        self.assertEqual(module._REASONING_CACHE_RESTORED, 0)
        self.assertEqual(len(module._REASONING_CACHE), 0)

    def test_uncached_replay_counts_a_miss_with_corrupt_file(self) -> None:
        # End-to-end fail-open: a spawned shim pointed at a corrupt seam starts cold, and a
        # replay referencing an uncached call_id degrades gracefully (miss=1, 200, no raise).
        corrupt_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(corrupt_tmp.cleanup)
        corrupt_seam = Path(corrupt_tmp.name) / "reasoning_cache.json"
        corrupt_seam.write_text("<<not json>>", encoding="utf-8")

        scenario = full_response_scenario()
        scenario.nonstream_responses = [
            _nonstream_response("resp_uncached_followup", [])
        ]
        with MockResponsesServer(scenario) as backend:
            with RealShim(
                backend,
                "openai",
                env_overrides={"DAAF_REASONING_CACHE_FILE": str(corrupt_seam)},
            ) as shim:
                health = shim.get_health().json()
                self.assertEqual(health["reasoning_cache"]["restored"], 0)

                result = shim.post_messages(
                    stream=False,
                    tools=[READ_TOOL],
                    messages=_tool_use_replay_messages("call_never_cached"),
                )
                self.assertEqual(result.status, 200, result.text)
                lifecycle = lifecycle_for_response(shim, result)
                terminal = next(
                    line for line in lifecycle if line.event == "terminal"
                )
                self.assertEqual(terminal.fields["reasoning_cache_miss"], "1")

    # --- Test 4: stale file -> not restored ---
    def test_stale_file_is_not_restored(self) -> None:
        # captured_at older than the 30-day sanity ceiling.
        stale_captured_at = int(time.time()) - (2_592_000 + 100_000)
        payload = _seam_payload(
            [("call_stale", _reasoning("rs_stale"))], captured_at=stale_captured_at
        )
        module, _ = self._fresh_module(existing_payload=payload)
        self.assertEqual(module._REASONING_CACHE_RESTORED, 0)
        self.assertEqual(len(module._REASONING_CACHE), 0)

    def test_future_timestamp_is_not_restored(self) -> None:
        # A captured_at in the future (clock skew / tampering) is rejected too.
        future_captured_at = int(time.time()) + 100_000
        payload = _seam_payload(
            [("call_future", _reasoning("rs_future"))], captured_at=future_captured_at
        )
        module, _ = self._fresh_module(existing_payload=payload)
        self.assertEqual(module._REASONING_CACHE_RESTORED, 0)
        self.assertEqual(len(module._REASONING_CACHE), 0)

    # --- Test 5: restore preserves LRU order; restored entries evict in correct order ---
    def test_restore_preserves_lru_order_and_eviction(self) -> None:
        pairs = [(f"call_{i}", _reasoning(f"rs_{i}")) for i in range(3)]
        module, _ = self._fresh_module(existing_payload=_seam_payload(pairs))
        self.assertEqual(module._REASONING_CACHE_RESTORED, 3)
        # File order is oldest->newest, so the cache keys land in that exact order.
        self.assertEqual(
            list(module._REASONING_CACHE.keys()),
            ["call_0", "call_1", "call_2"],
        )
        # Lower the cap and add one more: the genuinely-oldest (call_0) must evict first,
        # proving restore reconstructed the LRU order (not an arbitrary dict order).
        module._REASONING_CACHE_CAP = 3
        module._cache_reasoning("call_3", _reasoning("rs_3"))
        self.assertEqual(
            list(module._REASONING_CACHE.keys()),
            ["call_1", "call_2", "call_3"],
        )

    # --- Test 6: entry-count and byte bounds keep the newest entries ---
    def test_entry_count_bound_keeps_newest(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        seam_path = Path(tmp.name) / "reasoning_cache.json"
        module = _load_shim_module(seam_path)  # cold start
        total = module._REASONING_PERSIST_MAX_ENTRIES + 44  # cap-symbolic: MAX_ENTRIES + 44
        for i in range(total):
            module._cache_reasoning(f"call_{i}", _reasoning(f"rs_{i}"))
        module._write_reasoning_cache_state()

        payload = json.loads(seam_path.read_text(encoding="utf-8"))
        entries = payload["entries"]
        self.assertEqual(len(entries), module._REASONING_PERSIST_MAX_ENTRIES)
        call_ids = [cid for cid, _ in entries]
        # The retained window is the NEWEST cap entries, in oldest->newest order.
        first_kept = total - module._REASONING_PERSIST_MAX_ENTRIES
        self.assertEqual(call_ids[0], f"call_{first_kept}")
        self.assertEqual(call_ids[-1], f"call_{total - 1}")

    def test_byte_bound_keeps_newest(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        seam_path = Path(tmp.name) / "reasoning_cache.json"
        module = _load_shim_module(seam_path)  # cold start
        # Ten entries, each carrying a sizeable opaque blob.
        blob = "X" * 400
        for i in range(10):
            module._cache_reasoning(
                f"call_{i}",
                {"type": "reasoning", "id": f"rs_{i}", "encrypted_content": blob},
            )
        # Shrink the byte cap so only a handful of the newest entries fit.
        module._REASONING_PERSIST_MAX_BYTES = 1500
        module._write_reasoning_cache_state()

        payload = json.loads(seam_path.read_text(encoding="utf-8"))
        entries = payload["entries"]
        self.assertGreaterEqual(len(entries), 1)
        self.assertLess(len(entries), 10)  # the byte cap really did bind
        call_ids = [cid for cid, _ in entries]
        # Whatever survived is a contiguous NEWEST suffix, ending at the most recent.
        self.assertEqual(call_ids[-1], "call_9")
        kept = len(entries)
        expected = [f"call_{i}" for i in range(10 - kept, 10)]
        self.assertEqual(call_ids, expected)
        # And the serialized file is within the cap.
        self.assertLessEqual(
            len(seam_path.read_bytes()), module._REASONING_PERSIST_MAX_BYTES
        )

    # --- A2 review fold-in: oversized on-disk file -> restore skipped (pre-read size guard) ---
    def test_oversized_file_is_not_restored(self) -> None:
        # A well-formed but oversized file (> the persist byte cap) must be skipped by the
        # pre-read size guard: WITHOUT the guard this single fat entry would restore fine;
        # WITH it, restore is skipped, the cache stays empty, and import does not raise.
        # The oversized blob is derived from the cap SYMBOLICALLY (cold-load precedent, same
        # pattern as test_restored_count_clamped_to_cache_cap below) so a future cap resize
        # keeps the test valid without an edit.
        cold_module, _ = self._fresh_module()  # cold load only to read the persist byte cap
        big_blob = "X" * (cold_module._REASONING_PERSIST_MAX_BYTES + 200_000)  # over the cap
        payload = _seam_payload(
            [(
                "call_big",
                {"type": "reasoning", "id": "rs_big", "encrypted_content": big_blob},
            )]
        )
        module, seam_path = self._fresh_module(existing_payload=payload)
        # Sanity: the fixture genuinely exceeds the cap (else the test would be vacuous).
        self.assertGreater(
            seam_path.stat().st_size, module._REASONING_PERSIST_MAX_BYTES
        )
        # Fail-open skip: nothing restored, cache empty, no exception raised on import.
        self.assertEqual(module._REASONING_CACHE_RESTORED, 0)
        self.assertEqual(len(module._REASONING_CACHE), 0)

    # --- A2 review fold-in: >cap file -> /health `restored` is clamped to resident count ---
    def test_restored_count_clamped_to_cache_cap(self) -> None:
        # A hand-tampered file with MORE entries than the in-memory cap would, without the
        # clamp, make restore return its raw insert count while the cache only holds
        # _REASONING_CACHE_CAP entries — overstating /health.reasoning_cache.restored (the
        # /health block surfaces _REASONING_CACHE_RESTORED verbatim). The clamp reports the
        # resident count instead.
        cold_module, _ = self._fresh_module()  # cold load only to read the cap constant
        cap = cold_module._REASONING_CACHE_CAP
        over = cap + 5
        pairs = [
            (f"call_{i}", {"type": "reasoning", "id": f"rs_{i}", "encrypted_content": "E"})
            for i in range(over)
        ]
        module, _ = self._fresh_module(existing_payload=_seam_payload(pairs))
        # Every pair inserts (returns True) but the oldest evict at the cap, so `over` entries
        # were inserted while the cache holds exactly `cap`. The reported count is clamped to
        # the resident size and so never exceeds the cap.
        self.assertEqual(len(module._REASONING_CACHE), cap)
        self.assertLessEqual(module._REASONING_CACHE_RESTORED, cap)
        self.assertEqual(module._REASONING_CACHE_RESTORED, cap)

    # --- Test 8: in-memory LRU eviction / cap unit test (pre-existing coverage gap) ---
    def test_in_memory_lru_eviction_and_cap(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        seam_path = Path(tmp.name) / "reasoning_cache.json"
        module = _load_shim_module(seam_path)  # cold start
        module._REASONING_CACHE_CAP = 3
        for i in range(5):
            self.assertTrue(
                module._cache_reasoning(f"call_{i}", _reasoning(f"rs_{i}"))
            )
        # Cap enforced; the three most-recent survive, oldest-two evicted.
        self.assertEqual(len(module._REASONING_CACHE), 3)
        self.assertEqual(
            list(module._REASONING_CACHE.keys()),
            ["call_2", "call_3", "call_4"],
        )
        # A refresh of an existing key moves it to most-recent (LRU touch).
        module._cache_reasoning("call_3", _reasoning("rs_3b"))
        self.assertEqual(
            list(module._REASONING_CACHE.keys()),
            ["call_2", "call_4", "call_3"],
        )
        # A no-op reject (empty call_id / non-dict item) returns False and mutates nothing.
        self.assertFalse(module._cache_reasoning("", _reasoning("rs_x")))
        self.assertFalse(module._cache_reasoning("call_z", "not-a-dict"))
        self.assertEqual(len(module._REASONING_CACHE), 3)


# The production HOME-default reasoning-cache file the shim would write when NOT seamed.
# The suite must never create or modify it. "absent-stays-absent" is a valid bracket on a
# container that runs no shim.
_PRODUCTION_DEFAULT_CACHE = (
    Path(os.path.expanduser("~")) / ".claude" / "provider_shim" / "reasoning_cache.json"
)


def _stat_snapshot(path: Path):
    """Return (st_mtime_ns, raw bytes) for path, or None if it does not exist."""
    try:
        return (path.stat().st_mtime_ns, path.read_bytes())
    except FileNotFoundError:
        return None


# Out-of-process probe: import the production shim by file and print the two module-level
# reasoning-cache path constants as JSON. Importing only evaluates the constant/def bodies
# and the import-time restore (a READ of an absent/other file) — it never calls the writer,
# so the probe creates no reasoning-cache file. HOME is set explicitly by the caller so the
# default derivation is pinned to a controlled directory.
_PATH_PROBE = (
    "import importlib.util, json, sys\n"
    "spec = importlib.util.spec_from_file_location('shim_reasoning_path_probe', sys.argv[1])\n"
    "m = importlib.util.module_from_spec(spec)\n"
    "spec.loader.exec_module(m)\n"
    "print(json.dumps({'dir': m._REASONING_CACHE_DIR, 'path': m._REASONING_CACHE_PATH}))\n"
)


class ReasoningCacheNonPollutionAndPathTests(unittest.TestCase):
    """Tests 7 and 9: production HOME-default non-pollution + path derivation."""

    maxDiff = 12000

    def _run_path_probe(self, extra_env, home=None):
        # Inherit the runner env (so DAAF_QUOTA_STATE_FILE stays seamed to scratch and the
        # module imports cleanly) but strip DAAF_REASONING_CACHE_FILE so default derivation
        # is exercised unless the caller sets it back via extra_env.
        env = {k: v for k, v in os.environ.items() if k != "DAAF_REASONING_CACHE_FILE"}
        if home is not None:
            env["HOME"] = home
        env.update(extra_env)
        # Python derives the pip --user site-packages dir from HOME at interpreter
        # startup, so overriding HOME above silently drops per-user-installed deps
        # (httpx on GitHub runners) off the child's sys.path and the shim import dies
        # before the probe prints. Pass the REAL user-site (computed under the real
        # HOME, here in the parent) through PYTHONPATH: the shim derives its cache
        # path from HOME, not PYTHONPATH, so the derivation assertion is unaffected.
        env["PYTHONPATH"] = os.pathsep.join(
            filter(None, [site.getusersitepackages(), env.get("PYTHONPATH", "")])
        )
        completed = subprocess.run(
            [sys.executable, "-c", _PATH_PROBE, str(PRODUCTION_SHIM)],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout.strip())

    # --- Test 7 (spawned): a spawned reasoning+tool turn never touches the HOME default ---
    def test_spawned_shim_does_not_touch_production_default(self) -> None:
        dirty = True
        for _attempt in range(2):
            before = _stat_snapshot(_PRODUCTION_DEFAULT_CACHE)
            scenario = full_response_scenario()
            with MockResponsesServer(scenario) as backend:
                with RealShim(backend, "openai") as shim:
                    result = shim.post_messages(stream=False, tools=[READ_TOOL])
                    self.assertEqual(result.status, 200, result.text)
                    lifecycle_for_response(shim, result)
                    # Non-vacuity: the shim really did persist (to its per-instance seam),
                    # so a clean production bracket is not merely a write-that-never-happened.
                    seam_path = Path(shim.child_env["DAAF_REASONING_CACHE_FILE"])
                    self.assertTrue(seam_path.exists())
            after = _stat_snapshot(_PRODUCTION_DEFAULT_CACHE)
            if before == after:
                dirty = False
                break
        self.assertFalse(
            dirty, "spawned shim polluted the production HOME-default reasoning_cache.json"
        )

    # --- Test 7 (in-process): a fresh in-process load never touches the HOME default ---
    def test_in_process_probe_does_not_touch_production_default(self) -> None:
        seam_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(seam_tmp.cleanup)
        seam_path = Path(seam_tmp.name) / "reasoning_cache.json"

        dirty = True
        for _attempt in range(2):
            before = _stat_snapshot(_PRODUCTION_DEFAULT_CACHE)
            # A per-test seam carries into the freshly loaded module exactly as the runner
            # default would; the probe drives a streaming reasoning+tool turn so the real
            # populate -> _write_reasoning_cache_state path runs against the seam.
            with mock.patch.dict(
                os.environ, {"DAAF_REASONING_CACHE_FILE": str(seam_path)}
            ):
                controlled_asgi_probe(scenario=full_response_scenario(), stream=True)
            after = _stat_snapshot(_PRODUCTION_DEFAULT_CACHE)
            if before == after:
                dirty = False
                break
        self.assertFalse(
            dirty,
            "in-process probe polluted the production HOME-default reasoning_cache.json",
        )
        # Non-vacuity: the probe genuinely persisted to the per-test seam.
        self.assertTrue(
            seam_path.exists(),
            "in-process probe did not drive a reasoning-cache write to the per-test seam",
        )
        payload = json.loads(seam_path.read_text(encoding="utf-8"))
        self.assertIsInstance(payload["captured_at"], int)
        self.assertIn("call_full_fixture", {cid for cid, _ in payload["entries"]})

    # --- Test 9: out-of-process path derivation (seam wins; default derives from HOME) ---
    def test_seam_env_redirects_module_cache_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            seam = str(Path(tmp) / "redirected_reasoning.json")
            got = self._run_path_probe({"DAAF_REASONING_CACHE_FILE": seam})
            self.assertEqual(got["path"], seam)
            self.assertEqual(got["dir"], str(Path(tmp)))

    def test_default_path_derives_from_home_without_seam(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            expected_dir = Path(home) / ".claude" / "provider_shim"
            for extra_env in ({}, {"DAAF_REASONING_CACHE_FILE": ""}):
                with self.subTest(extra_env=extra_env):
                    got = self._run_path_probe(extra_env, home=home)
                    self.assertEqual(got["dir"], str(expected_dir))
                    self.assertEqual(
                        got["path"], str(expected_dir / "reasoning_cache.json")
                    )


if __name__ == "__main__":
    unittest.main()
