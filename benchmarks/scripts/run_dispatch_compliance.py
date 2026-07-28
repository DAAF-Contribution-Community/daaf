"""Dispatch compliance benchmark with golden checkpoint scoring and run archival.

Tests whether models correctly dispatch subagents via the Agent tool when a user
requests specific tasks in Ad Hoc Collaboration mode. Each test case resumes from
a golden checkpoint where the orchestrator is fully initialized (daaf-orchestrator
loaded, ad-hoc-collaboration-mode.md read, data-scientist skill loaded), then
scores whether the model dispatches the correct subagent_type with a properly
structured prompt containing BASE_DIR, mode markers, and task-relevant content.

Scoring uses score_dispatch_compliance() from dispatch_compliance.py, which checks
all ten dispatch criteria: agent_dispatched, correct_subagent_type,
prompt_has_base_dir, prompt_has_mode_marker, prompt_has_project_dir,
prompt_has_task_section, prompt_has_context_section, prompt_has_instructions,
prompt_contains_required, and prompt_contains_any.

Results are archived to a self-contained results folder with per-run transcripts.

Usage:
    python3 benchmarks/scripts/run_dispatch_compliance.py
    python3 benchmarks/scripts/run_dispatch_compliance.py --reps 1 --models haiku,sonnet
    python3 benchmarks/scripts/run_dispatch_compliance.py --test-id dc-01,dc-07 --sequential
"""

import argparse
import concurrent.futures
import fcntl
import json
import os
import shutil
import stat
import subprocess
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/daaf")

from benchmarks.harness.models import TestCase, ModelConfig, RunConfig
from benchmarks.harness.executor import execute_run
from benchmarks.harness.checkpoint_manager import cleanup_sandbox
from benchmarks.harness.model_loader import load_models, filter_models, add_model_args
from benchmarks.harness.cost_estimator import estimate_batch_cost, format_estimate
from benchmarks.harness.artifacts import (
    add_preflight_arg,
    assert_unique_sandbox_slugs,
    attach_schema_version,
    build_error_artifact,
    build_run_artifact,
    child_model_purity,
    console_billing_label,
    cost_summary,
    format_coverage,
    is_scorable,
    manifest_provenance,
    model_manifest_entry,
    nullable_mean,
    purity_coverage,
    run_preflight,
    run_validity,
    sandbox_slug,
    validity_coverage,
)
from benchmarks.scorers.deterministic.checkpoint_adherence import (
    extract_new_tool_calls,
    find_benchmark_transcript,
    get_checkpoint_line_count,
)
from benchmarks.scorers.deterministic.dispatch_compliance import (
    score_dispatch_compliance,
)
from benchmarks.scorers.deterministic.subagent_behavior import (
    find_subagent_transcripts,
    score_subagent_behavior,
    score_subagent_behavior_from_transcripts,
)
from benchmarks.scorers.deterministic.error_classification import compute_error_counts

# --- Config ---

BASE_DIR = Path("/daaf")
CASES_FILE = BASE_DIR / "benchmarks" / "datasets" / "dispatch_compliance" / "cases.jsonl"
MODELS_FILE = BASE_DIR / "benchmarks" / "config" / "models.yaml"

LAUNCH_DELAY_SECONDS = 2
# Cap on simultaneously in-flight runs. Per-run state (sandbox dir, uuid4 session
# ids, transcript dirs) is fully isolated, so the cap is purely a resource-
# pressure guard, not a correctness one. --delay staggers submits independently.
MAX_CONCURRENT_RUNS = 5

# Serializes the progressive rollup (per-run archive write + summary/manifest
# rewrite). In the parallel path the as_completed loop already collects results
# on the main thread one at a time, but the lock makes the invariant explicit and
# keeps the finalizer safe against any future concurrent caller.
_ARCHIVE_LOCK = threading.Lock()


# --- Load config ---

def load_test_cases(path: Path) -> list[TestCase]:
    """Load test cases from cases.jsonl."""
    return TestCase.load_from_jsonl(path)


# --- Scoring ---

def score_run(
    session_id: str,
    test_case: TestCase,
    requested_child_model_id: str,
    wire_child_model_id: str = None,
) -> dict:
    """Score dispatch behavior and collect CLI-observed child-model evidence.

    Returns phase criteria, transcript diagnostics, and a non-scoring purity
    record. Purity is infrastructure evidence only; it does not alter any
    deterministic behavioral criterion.

    ``requested_child_model_id`` is the routing selector (``ModelConfig.id``);
    ``wire_child_model_id`` is the declared wire identity
    (``ModelConfig.comparison_model_id``) that transcript observations are
    compared against. Omitting the latter falls back to the routing selector,
    which is correct for every model whose wire form equals its routing id.
    """
    # Locate child transcripts even when the parent transcript is absent: their
    # independent CLI records may still establish dispatch and model identity.
    subagent_transcripts = find_subagent_transcripts(session_id)
    purity = child_model_purity(
        subagent_transcripts, requested_child_model_id, wire_child_model_id
    )

    transcript_path = find_benchmark_transcript(session_id)
    if not transcript_path:
        return {
            "criteria": [
                {
                    "name": "transcript_found",
                    "passed": False,
                    "tier": "tier1",
                    "detail": "Transcript not found for session.",
                }
            ],
            "subagent_criteria": [],
            "subagent_transcript_missing": not subagent_transcripts,
            "child_model_purity": purity,
            "transcript_path": None,
            "tool_call_count": 0,
        }

    # Get checkpoint line count from this test case's golden file
    golden_path = BASE_DIR / test_case.golden_checkpoint
    checkpoint_lines = get_checkpoint_line_count(golden_path)

    # Child transcripts serve double duty as (a) recovery evidence for a main
    # transcript tail lost on timeout and (b) Phase 3b behavior evidence.
    # They were located once above so scoring and purity inspect the same set.

    # Post-checkpoint tool calls, for the run-level tool_call_count
    tool_calls = extract_new_tool_calls(transcript_path, checkpoint_lines)

    # Score using the dispatch compliance scorer (with recovery evidence)
    criterion_results = score_dispatch_compliance(
        str(transcript_path), checkpoint_lines, test_case.expected,
        subagent_transcripts=subagent_transcripts,
    )

    # Convert CriterionResult objects to dicts for JSON serialization
    criteria_dicts = [
        {
            "name": cr.name,
            "passed": cr.passed,
            "tier": cr.tier,
            "detail": cr.detail,
        }
        for cr in criterion_results
    ]

    # Score subagent behavior if dispatch was successful
    expected_agent_type = test_case.expected.get("subagent_dispatched", "")
    agent_dispatched = any(c["passed"] for c in criteria_dicts if c["name"] == "agent_dispatched")
    subagent_criteria = []
    subagent_transcript_missing = False
    if agent_dispatched and expected_agent_type:
        # Diagnostic only: when dispatch succeeded but no subagent transcript
        # can be located, Phase 3b behavior is silently unscorable — the scorer
        # deliberately returns [] (its contract; see score_subagent_behavior).
        # Surface the gap on the console and persist a plain result.json flag.
        # NOT a criterion: it must never enter scoring or viewer Perfect.
        # Coherent with recovery by construction: a recovered dispatch implies
        # subagent_transcripts is non-empty, so the flag stays False.
        if not subagent_transcripts:
            subagent_transcript_missing = True
            print(f"WARNING: [{test_case.id}] agent_dispatched passed but "
                  f"find_subagent_transcripts() found no subagent transcript for "
                  f"session {session_id} — Phase 3b behavior unscored "
                  f"(subagent_transcript_missing=true persisted).")
        behavior_results = score_subagent_behavior(session_id, expected_agent_type)
        subagent_criteria = [
            {
                "name": cr.name,
                "passed": cr.passed,
                "tier": cr.tier,
                "detail": cr.detail,
            }
            for cr in behavior_results
        ]

    return {
        "criteria": criteria_dicts,
        "subagent_criteria": subagent_criteria,
        "subagent_transcript_missing": subagent_transcript_missing,
        "child_model_purity": purity,
        "transcript_path": str(transcript_path),
        "tool_call_count": len(tool_calls),
        # W1 (2026-07-28): expose the golden line count so the error scan can
        # skip the checkpoint prefix on the parent transcript, exactly as
        # extract_new_tool_calls does. Derived here so there is one source.
        "checkpoint_lines": checkpoint_lines,
    }


# --- Fixture isolation ---

FIXTURE_PREFIX = "/daaf/benchmarks/datasets/test_fixtures/"

# All per-run sandboxes live under this root. prepare_run_sandbox() refuses to
# wipe anything outside it, so the destructive rmtree can never reach a real
# project directory under /daaf/research/ or the repo root (B1 safety).
SANDBOX_ROOT = "/daaf/benchmarks/_sandbox"

# Cross-process reader/writer lock on the fixture surface. Deliberately lives
# under SANDBOX_ROOT (NOT inside datasets/test_fixtures/) so the lockfile is
# never itself a fixture path that restore/contamination checks would see.
FIXTURE_LOCK_PATH = f"{SANDBOX_ROOT}/.fixtures.lock"
_FIXTURE_LOCK_TIMEOUT_S = 600          # hard cap: abort a wait longer than 10 min
_FIXTURE_LOCK_WARN_EVERY_S = 30        # warn on the console every 30s while waiting


@contextmanager
def _fixture_lock(lock_type, label):
    """Hold an flock() reader/writer lock on the fixture surface for the block.

    ``lock_type`` is ``fcntl.LOCK_EX`` (restore = writer: excludes all other
    holders) or ``fcntl.LOCK_SH`` (prepare-copy = reader: coexists with other
    readers, excludes the writer). This is what makes concurrent runner
    PROCESSES safe: the in-process guarantee that restore runs strictly
    pre-pool does nothing across two separate `python run_dispatch_compliance.py`
    invocations, so batch B's restore (git restore / rmtree) could otherwise
    race batch A's in-flight shutil.copy2 reads of the same source paths.

    Blocking acquire via a non-blocking poll loop: warns every 30s while another
    batch holds the lock and aborts (RuntimeError) only after 10 minutes, so a
    genuinely wedged peer surfaces instead of hanging forever.

    No stale-lock cleanup exists BY DESIGN: flock() locks are released by the
    kernel automatically when the holding fd is closed OR the holding process
    dies (including SIGKILL). Users routinely Ctrl-C / kill batches, so any
    manual lockfile-reaping scheme would risk deleting a live lock; relying on
    kernel release is both simpler and correct.
    """
    Path(FIXTURE_LOCK_PATH).parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(FIXTURE_LOCK_PATH, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        start = time.time()
        last_warn = 0.0
        while True:
            try:
                fcntl.flock(fd, lock_type | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                waited = time.time() - start
                if waited > _FIXTURE_LOCK_TIMEOUT_S:
                    raise RuntimeError(
                        f"Timed out after {_FIXTURE_LOCK_TIMEOUT_S}s waiting for the "
                        f"fixture {label} lock ({FIXTURE_LOCK_PATH}); another batch "
                        f"appears wedged. Aborting this operation."
                    )
                if waited - last_warn >= _FIXTURE_LOCK_WARN_EVERY_S:
                    print(f"Waiting for fixture {label} lock "
                          f"({int(waited)}s elapsed; another batch holds it)...")
                    sys.stdout.flush()
                    last_warn = waited
                time.sleep(1.0)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _set_fixture_tree_writable(writable: bool) -> None:
    """Toggle write permission across the fixture SOURCE tree (defense-in-depth).

    Read-only (``writable=False``) is the resting state asserted after every
    successful restore (or clean early-return): files lose all write bits (a-w)
    and directories lose write while keeping r-x — traversable but refusing new
    entries. A benchmark subject that ignores its sandbox and writes into
    datasets/test_fixtures/ BY NAME now fails with EACCES rather than silently
    contaminating the source (the two historical incident classes this hardens
    against). restore_fixtures() flips the tree writable only for the duration
    of any actual repair work, then re-asserts read-only.

    Note this does NOT create git contamination: git tracks only the executable
    bit, not the write bit, so `git status` never sees an a-w chmod on a regular
    file. Best-effort: chmod failures are warned, not raised, so a hardening
    hiccup never aborts a batch.
    """
    root = Path(FIXTURE_PREFIX)
    if not root.exists():
        return
    targets = [root]
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            targets.append(Path(dirpath) / name)
    for p in targets:
        try:
            mode = p.stat().st_mode
            if writable:
                p.chmod(mode | stat.S_IWUSR)
            else:
                p.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        except OSError as e:
            print(f"  WARNING: could not chmod fixture path {p} ({e}).")


def prepare_run_sandbox(sandbox_dir: str) -> Path:
    """Wipe and recreate a per-run sandbox so no prior-run artifacts survive (B1).

    Repetition safety: each run starts from an empty sandbox, so a repeated run
    of the same case cannot see files a prior run wrote. The wipe is hard-guarded
    to SANDBOX_ROOT — a sandbox_dir resolving outside it raises ValueError rather
    than risking a legitimate /daaf/research/ project directory.
    """
    sandbox_path = Path(sandbox_dir)
    resolved = str(sandbox_path.resolve())
    if resolved != SANDBOX_ROOT and not resolved.startswith(SANDBOX_ROOT + "/"):
        raise ValueError(
            f"Refusing to wipe non-sandbox path: {sandbox_path} "
            f"(must be under {SANDBOX_ROOT})"
        )
    if sandbox_path.exists():
        shutil.rmtree(sandbox_path)
    sandbox_path.mkdir(parents=True, exist_ok=True)
    return sandbox_path


def _fixture_status_entries() -> list[str] | None:
    """Return `git status --porcelain` entries for test_fixtures/, or None on
    git failure (a warning is printed; callers treat None as 'cannot check').

    Mirrors the subprocess pattern of get_git_sha().
    """
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--", FIXTURE_PREFIX],
            capture_output=True,
            text=True,
            timeout=30,
            cwd="/daaf",
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"WARNING: could not check fixture status ({e}); skipping fixture check.")
        return None
    if proc.returncode != 0:
        print(f"WARNING: git status failed for fixtures (exit {proc.returncode}): "
              f"{proc.stderr.strip()}")
        return None
    return [line for line in proc.stdout.splitlines() if line.strip()]


def restore_fixtures() -> None:
    """Restore datasets/test_fixtures/ to pristine git HEAD state.

    Pristine fixture state is defined as git HEAD: the canonical fixtures
    legitimately CONTAIN appended EXECUTION OUTPUT blocks, so restore-to-HEAD
    (not log-stripping) is the correct semantic. Tracked contamination gets a
    path-scoped `git restore --staged --worktree --source=HEAD -- <file>` —
    --source=HEAD because plain `git restore` restores the worktree from the
    INDEX, so staged contamination (rogue `git add`) would survive and the
    worktree would be "restored" to the contaminated index copy. Untracked
    residue is deleted via Python. This function NEVER invokes `git clean`,
    `git checkout .`, or any non-path-scoped restore. Every action taken is
    printed (audit trail).

    Must be called per-batch, BEFORE the run pool launches: all parallel run
    threads read the shared originals at launch, so a mid-batch restore would
    race with their shutil.copy2 reads.

    The ENTIRE body runs under an exclusive (LOCK_EX) fixture lock so the
    check-then-repair is atomic across concurrent runner processes: a peer
    batch's shared-lock copy loop cannot read a source path mid-repair, and two
    batches cannot repair simultaneously. On completion the source tree is left
    read-only (defense-in-depth); any repair work temporarily re-enables writes.
    """
    with _fixture_lock(fcntl.LOCK_EX, "restore"):
        _restore_fixtures_locked()


def _restore_fixtures_locked() -> None:
    entries = _fixture_status_entries()
    if entries is None:
        return
    if not entries:
        print(f"Fixtures clean: {FIXTURE_PREFIX} matches git HEAD — no restore needed.")
        # Re-assert the read-only resting state even on the clean path so a tree
        # left writable by an older harness (or a fresh checkout) gets hardened.
        _set_fixture_tree_writable(False)
        return

    # Repair mutates the source tree (git restore writes, untracked deletes need
    # writable parent dirs), so lift the read-only hardening for the repair only.
    _set_fixture_tree_writable(True)
    try:
        _restore_fixtures_repair(entries)
    finally:
        _set_fixture_tree_writable(False)


def _restore_fixtures_repair(entries: list[str]) -> None:
    print(f"Restoring {len(entries)} contaminated fixture path(s) to git HEAD:")
    for entry in entries:
        status = entry[:2]
        # No .strip(): splitlines() already removed newlines, and stripping a
        # path with genuine trailing whitespace could redirect the deletion
        # below onto a different (clean) file.
        rel_path = entry[3:]
        # Porcelain quotes paths containing special characters
        if rel_path.startswith('"') and rel_path.endswith('"'):
            rel_path = rel_path[1:-1]
        if status == "??":
            abs_path = Path("/daaf") / rel_path
            # Untracked residue from a contaminated run — delete via Python
            # (never `git clean`). Porcelain reports untracked dirs with a
            # trailing slash.
            if rel_path.endswith("/") or abs_path.is_dir():
                shutil.rmtree(abs_path, ignore_errors=True)
                print(f"  [deleted untracked dir]  {abs_path}")
            elif abs_path.exists():
                try:
                    os.remove(abs_path)
                    print(f"  [deleted untracked file] {abs_path}")
                except OSError as e:
                    print(f"  WARNING: could not delete {abs_path} ({e}); "
                          f"remove manually.")
            elif "\\" in rel_path:
                # Porcelain C-escapes special characters inside quoted paths;
                # we don't unescape, so existence checks are unreliable here.
                print(f"  WARNING: escaped path reported by git — restore "
                      f"manually: {entry!r}")
            else:
                print(f"  [already gone]           {abs_path}")
        else:
            # Tracked contamination — path-scoped restore only. Rename/copy
            # entries ('R '/'C ') report 'old -> new'; restore both sides.
            paths = rel_path.split(" -> ") if status[0] in "RC" else [rel_path]
            for p in paths:
                if p.startswith('"') and p.endswith('"'):
                    p = p[1:-1]
                # --source=HEAD --staged --worktree: plain `git restore`
                # restores worktree from the INDEX, which would leave staged
                # contamination in place (and print a false success).
                try:
                    proc = subprocess.run(
                        ["git", "restore", "--staged", "--worktree",
                         "--source=HEAD", "--", p],
                        capture_output=True,
                        text=True,
                        timeout=30,
                        cwd="/daaf",
                    )
                except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                    print(f"  WARNING: git restore errored for {p} ({e}); "
                          f"restore manually.")
                    continue
                if proc.returncode == 0:
                    print(f"  [restored to HEAD]       /daaf/{p}  (was: {status!r})")
                else:
                    print(f"  WARNING: git restore failed for {p}: "
                          f"{proc.stderr.strip()}")


def check_fixture_contamination() -> None:
    """Post-batch contamination check: detect and warn loudly, never restore.

    Restoration is deliberately deferred to the NEXT launch's pre-batch
    restore_fixtures() — post-batch auto-restore was rejected as needlessly
    destructive (it could erase evidence useful for debugging a leaky run).
    """
    entries = _fixture_status_entries()
    if not entries:  # None (git failure, already warned) or clean
        return
    bar = "!" * 100
    print(f"\n{bar}")
    print("WARNING: FIXTURE CONTAMINATION DETECTED AFTER THIS BATCH")
    print(f"The following paths under {FIXTURE_PREFIX} no longer match git HEAD:")
    for entry in entries:
        print(f"  {entry}")
    print("No automatic restore is performed post-batch (detect + warn only).")
    print("These paths will be auto-restored to git HEAD at the next benchmark "
          "launch, or restore manually now with a path-scoped "
          "'git restore --staged --worktree --source=HEAD -- <path>' (tracked) "
          "/ delete (untracked).")
    print(bar)


def prepare_fixtures(test_case: TestCase, sandbox_dir: str) -> TestCase:
    """Copy any referenced fixtures into the sandbox and add workspace containment.

    Two responsibilities, now both applied to EVERY case (B1):

    1. Fixture copying (conditional): when the prompt references paths under
       test_fixtures/, each is copied to {sandbox_dir}/fixtures/{subdir}/{file}
       and the prompt is rewritten so originals are never touched by subagents.
    2. Workspace containment (unconditional): every case — fixture-bearing or not
       — gets a {sandbox_dir}/workspace/ (the PROJECT_DIR) plus a BASE_DIR-level
       {sandbox_dir}/scripts/run_with_capture.sh (isomorphic to the real repo, so
       the CLAUDE.md `{BASE_DIR}/scripts/run_with_capture.sh` convention resolves)
       and a prompt instruction directing all model/subagent writes into the
       per-run sandbox. Previously non-fixture cases (dc-01..dc-06) received no
       containment instruction, so a dispatched subagent could write a real
       /daaf/research/ project (the 2026-07-16 dc-01 MonteCarlo leak). Applying
       the same instruction fixture cases already carried closes that vector for
       all cases, uniformly across models.

    The instruction is appended to the CASE prompt (harness input), not to the
    model's Agent-dispatch prompt (which the scorer reads), so no scored
    criterion, requirement list, or expected field is affected.
    """
    import re
    import copy

    pattern = re.escape(FIXTURE_PREFIX) + r"[^\s\"')]+"
    matches = re.findall(pattern, test_case.prompt)

    fixtures_dir = Path(sandbox_dir) / "fixtures"
    modified_prompt = test_case.prompt

    # Hold a SHARED (reader) lock around the fixture-copy portion ONLY: it must
    # exclude a peer batch's exclusive restore (git restore / rmtree) from
    # mutating a source path mid-copy, but must coexist with other batches'
    # copy loops. The lock is scoped to the copies, not the whole run, so live
    # runs never serialize on it. Non-fixture cases (no matches) skip it.
    if matches:
        with _fixture_lock(fcntl.LOCK_SH, "copy"):
            for orig_path in matches:
                src = Path(orig_path)
                if not src.exists():
                    continue
                rel = src.relative_to(Path(FIXTURE_PREFIX).parent)
                dest = fixtures_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                # copy2 preserves mode, so a read-only source yields a read-only
                # copy; restore u+w so the run can work with its own copy.
                try:
                    dest.chmod(dest.stat().st_mode | stat.S_IWUSR)
                except OSError as e:
                    print(f"  WARNING: could not chmod fixture copy {dest} ({e}).")
                modified_prompt = modified_prompt.replace(orig_path, str(dest))

    workspace_dir = Path(sandbox_dir) / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # Copy run_with_capture.sh to the BASE_DIR-level scripts/ dir so the sandbox
    # is isomorphic to the real repo layout: CLAUDE.md's canonical invocation is
    # `bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/...`, so
    # sandbox_dir plays BASE_DIR and workspace_dir plays PROJECT_DIR. Models of
    # every family read that convention and construct {BASE_DIR}/scripts/... — the
    # prior workspace/scripts/ location produced exit 127 + wasted recovery turns.
    rwc_src = Path("/daaf/scripts/run_with_capture.sh")
    if rwc_src.exists():
        rwc_dest = Path(sandbox_dir) / "scripts" / "run_with_capture.sh"
        rwc_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(rwc_src, rwc_dest)
        # copy2 preserves mode; ensure the sandbox copy is writable + executable
        # (the source may be tracked read-only, and the wrapper must run).
        try:
            rwc_dest.chmod(rwc_dest.stat().st_mode | stat.S_IWUSR | stat.S_IXUSR)
        except OSError as e:
            print(f"  WARNING: could not chmod wrapper copy {rwc_dest} ({e}).")

    modified_prompt += (
        f" Use {workspace_dir} as the project workspace and {sandbox_dir} as the"
        f" base directory (the script-execution wrapper is at"
        f" {sandbox_dir}/scripts/run_with_capture.sh): every file or folder you"
        f" or your subagents create must live under {sandbox_dir} — do not create"
        f" scripts, outputs, or research project folders anywhere else in the"
        f" repository."
    )

    tc = copy.deepcopy(test_case)
    tc.prompt = modified_prompt
    return tc


# --- Early-stop scoring callback ---

def _build_early_stop_check(test_case: TestCase):
    """Build the executor's early_stop_check closure for one dispatch case.

    Returns a callable (session_id) -> bool that runs the REAL deterministic
    scorers against the live transcripts and returns True only when every scored
    criterion — the 10 dispatch criteria AND, when a subagent dispatch is
    expected, the subagent-behavior criteria — has PASSED.

    Why early stop is score-neutral here (the monotone-pass fairness argument):
    every dispatch criterion locks PASS on first observation (it settles at the
    Agent call) and the subagent-behavior criteria settle at the subagent's
    actions; none can be voided by later activity. So killing the run the moment
    all criteria pass cannot change the score — it only reclaims the dead wall
    time a model would otherwise spend continuing after the gradeable behavior
    is already on disk. (This is NOT true of the other three phases, whose
    negative criteria — no_premature_execution / no_forbidden_skills /
    no_tool_calls_of_type — start PASS and can only flip to FAIL; early-stopping
    those would unfairly lock in a not-yet-violated negative, so they get stall
    detection only.)

    Flush-race protection: when a subagent dispatch is expected, the check
    returns False until the subagent transcript exists on disk AND its behavior
    criteria pass. Combined with the executor's one-poll confirmation grace, this
    guarantees the dispatch-recovery fallback has the subagent's records before
    any truncation.

    Exception safety: any scorer error is swallowed and reported as "not done"
    (return False) — a scorer crash must never kill a run mid-flight. The
    executor also guards this, so protection is belt-and-suspenders.
    """
    expected_agent_type = test_case.expected.get("subagent_dispatched", "")
    golden_path = BASE_DIR / test_case.golden_checkpoint

    def _check(session_id: str) -> bool:
        try:
            transcript_path = find_benchmark_transcript(session_id)
            if not transcript_path:
                return False
            checkpoint_lines = get_checkpoint_line_count(golden_path)
            subagent_transcripts = find_subagent_transcripts(session_id)

            dispatch_results = score_dispatch_compliance(
                str(transcript_path), checkpoint_lines, test_case.expected,
                subagent_transcripts=subagent_transcripts,
            )
            if not dispatch_results or not all(cr.passed for cr in dispatch_results):
                return False

            # When a subagent dispatch is expected, require the subagent
            # transcript on disk and all its behavior criteria passing before
            # declaring done (protects the flush race + Phase 3b fairness).
            if expected_agent_type:
                if not subagent_transcripts:
                    return False
                behavior = score_subagent_behavior_from_transcripts(
                    subagent_transcripts, expected_agent_type
                )
                if not behavior or not all(cr.passed for cr in behavior):
                    return False
            return True
        except Exception as e:
            print(
                f"WARNING: [{test_case.id}] early_stop_check raised "
                f"{type(e).__name__}: {e}; not early-stopping."
            )
            return False

    return _check


# --- Run + diagnose ---

def run_one(test_case: TestCase, model: ModelConfig, rep: int,
            sandbox_suffix: str, timeout_override=None,
            watchdog_poll=60, stall_threshold=330, stall_retries=1,
            enable_early_stop=True):
    """Execute a single benchmark run with checkpoint scoring.

    Run-lifecycle watchdog (Dispatch B): the executor polls every
    ``watchdog_poll`` seconds, stopping early when all criteria pass (score
    complete) and killing a hung run whose transcripts go quiet for
    >``stall_threshold`` seconds across consecutive polls. A stalled run is
    relaunched from a fresh sandbox up to ``stall_retries`` times (default 1); a
    run that stalls again after its last retry is recorded permanently as
    ``status="stalled"``. Set ``enable_early_stop=False`` to disable early stop.
    """
    sandbox_dir = f"{SANDBOX_ROOT}/run_{sandbox_suffix}"
    early_stop_check = _build_early_stop_check(test_case) if enable_early_stop else None

    attempt = 0
    # Accumulate each stalled attempt's diagnostics so a run that stalled once
    # then passed is legible from the archive alone (previously console-only).
    # Carried onto the FINAL result.json as an additive stall_attempts field.
    stall_attempts = []
    while True:
        # Wipe and recreate the sandbox BEFORE staging fixtures, and tell
        # execute_run() -> prepare_sandbox() not to wipe it again
        # (wipe_sandbox=False). Previously fixtures were staged first and
        # prepare_sandbox()'s rmtree deleted them — at model launch the rewritten
        # prompt pointed at nonexistent sandbox paths, so models hunted the files
        # by name and contaminated the originals under datasets/test_fixtures/.
        # The wipe is hard-guarded to SANDBOX_ROOT (B1 repetition safety); a fresh
        # sandbox per run means a repeated run never sees a prior run's artifacts.
        # On a stall relaunch this also gives the retry a pristine sandbox.
        prepare_run_sandbox(sandbox_dir)

        sandboxed_case = prepare_fixtures(test_case, sandbox_dir)

        config = RunConfig(
            test_case=sandboxed_case,
            model=model,
            run_index=rep,
            sandbox_dir=sandbox_dir,
            wipe_sandbox=False,
            timeout_override=timeout_override,
            early_stop_check=early_stop_check,
            watchdog_poll_seconds=watchdog_poll,
            stall_detection=True,
            stall_threshold_seconds=stall_threshold,
        )

        start = time.time()
        result = execute_run(config)
        elapsed = time.time() - start

        if getattr(result, "stalled", False):
            stall_attempts.append({
                "attempt": attempt,
                "stall_diagnostics": dict(result.stall_diagnostics or {}),
            })
        if getattr(result, "stalled", False) and attempt < stall_retries:
            print(
                f"STALL [{test_case.id} | {model.name} | rep {rep}] attempt "
                f"{attempt + 1}: {result.stall_diagnostics}; wiping sandbox and "
                f"relaunching (retry {attempt + 1}/{stall_retries})."
            )
            # Release the checkpoint sandbox from the stalled attempt before the
            # relaunch stages a fresh one under the same session bookkeeping.
            if test_case.golden_checkpoint and result.session_id:
                cleanup_sandbox(result.session_id)
            attempt += 1
            continue
        break

    stall_relaunch_count = attempt

    # Always attempt scoring if we have a session_id — even for timed-out runs,
    # the live session file may contain partial but scorable transcript data.
    if result.session_id:
        time.sleep(1)
        # Routing stays pinned to model.id (executor.py passes it to
        # `claude --model`); only the purity COMPARISON target uses the
        # declared wire identity.
        scored = score_run(
            result.session_id, test_case, model.id, model.comparison_model_id
        )
    else:
        scored = {
            "criteria": [
                {
                    "name": "run_completed",
                    "passed": False,
                    "tier": "tier1",
                    "detail": f"No session ID: {result.error}",
                }
            ],
            "subagent_criteria": [],
            "subagent_transcript_missing": True,
            "child_model_purity": child_model_purity(
                [], model.id, model.comparison_model_id
            ),
            "transcript_path": None,
            "tool_call_count": 0,
        }

    # Archive transcript + subagent transcripts BEFORE cleanup deletes them
    archived_transcript = None
    if result.session_id:
        transcript_src = scored.get("transcript_path")
        if transcript_src and Path(transcript_src).exists():
            archive_dir = Path(f"{SANDBOX_ROOT}/transcripts/{result.session_id}")
            archive_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(transcript_src, archive_dir / "transcript.jsonl")
            archived_transcript = str(archive_dir / "transcript.jsonl")
            subagent_dir = Path.home() / ".claude" / "projects" / "-daaf" / result.session_id / "subagents"
            if subagent_dir.exists():
                shutil.copytree(subagent_dir, archive_dir / "subagents", dirs_exist_ok=True)

    # Classify error-bearing tool results (parent + archived subagent
    # transcripts) into hook-block vs genuine-failure buckets before cleanup
    # removes the live transcripts. Additive diagnostic only.
    subagent_transcripts = []
    if archived_transcript:
        sub_dir = Path(archived_transcript).parent / "subagents"
        if sub_dir.exists():
            subagent_transcripts = list(sub_dir.rglob("*.jsonl"))
    # Fix 4 (2026-07-28): scan the parent transcript directly instead of
    # relying on result.tool_failures. The executor extracts tool_failures
    # only on the normal completion path — timeout/stalled/early-stopped runs
    # return before that extraction (executor.py :229/:249), leaving the
    # parent side undercounted. Scanning the archived parent transcript with
    # the same _iter_transcript_error_contents used for subagents closes the
    # gap. tool_failures is passed empty so parent errors are counted once:
    # the transcript scan REPLACES, not augments, the tool_failures-derived
    # counts (no double-count).
    # W1 (2026-07-28): the parent transcript carries the prepended golden
    # checkpoint prefix, so its scan skips the first checkpoint_lines lines
    # (mirroring extract_new_tool_calls); subagent transcripts have no prefix
    # and are scanned in full. Note: this scan sees FULL untruncated content
    # over the WHOLE post-checkpoint transcript, unlike the legacy 500-char-
    # truncated result.tool_failures path, so bucket classifications can differ
    # from pre-2026-07-28 runs.
    parent_skip_lines = scored.get("checkpoint_lines", 0)
    error_counts = compute_error_counts(
        [],
        subagent_transcripts=subagent_transcripts,
        parent_transcript=archived_transcript,
        parent_skip_lines=parent_skip_lines,
    )

    # Clean up checkpoint sandbox AFTER archiving
    if test_case.golden_checkpoint:
        cleanup_sandbox(result.session_id)

    return build_run_artifact(
        model,
        result,
        phase_fields={
            "case_id": test_case.id,
            "subcategory": test_case.subcategory,
            "rep": rep,
            "criteria": scored["criteria"],
            "error_counts": error_counts,
            "subagent_criteria": scored.get("subagent_criteria", []),
            "subagent_transcript_missing": scored.get(
                "subagent_transcript_missing", False
            ),
            "child_model_purity": scored["child_model_purity"],
            # B2: purity gate verdict. failed purity -> invalid (excluded from
            # score rollups, never deleted); verified/unverifiable -> valid.
            "validity": run_validity(
                {"child_model_purity": scored["child_model_purity"]}
            ),
            "transcript_path": archived_transcript or scored.get("transcript_path"),
            "tool_call_count": scored.get("tool_call_count", 0),
            "stall_relaunch_count": stall_relaunch_count,
            "stall_attempts": stall_attempts,
        },
        duration_s=elapsed,
    )


def _error_result(test_case: TestCase, model: ModelConfig, rep: int, error_msg: str):
    """Build a safe result dict for a run that failed before returning data."""
    criteria = [
        {
            "name": "run_completed",
            "passed": False,
            "tier": "tier1",
            "detail": f"Exception: {error_msg}",
        }
    ]
    return build_error_artifact(
        model,
        test_case.id,
        rep,
        error_msg,
        phase_fields={
            "subcategory": test_case.subcategory,
            "criteria": criteria,
            "error_counts": {
                "hook_blocks": 0,
                "tool_failures": 0,
                "tool_failures_unclassified": 0,
            },
            "subagent_criteria": [],
            "subagent_transcript_missing": True,
            "child_model_purity": child_model_purity(
                [], model.id, model.comparison_model_id
            ),
            # An unverifiable-purity error run stays valid (scored) per B2.
            "validity": run_validity(
                {
                    "child_model_purity": child_model_purity(
                        [], model.id, model.comparison_model_id
                    )
                }
            ),
            "transcript_path": None,
            "tool_call_count": 0,
        },
    )


# --- Archival ---

def get_git_sha() -> str:
    """Get the current DAAF git commit SHA."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd="/daaf",
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return "unknown"


def _write_json_atomic(path: Path, obj) -> None:
    """Write JSON to a sibling .tmp then os.replace() over the target.

    Atomicity matters for the progressive rollup: a reader (or a kill) never sees
    a half-written summary.json/manifest.json — the file either holds the prior
    complete rollup or the new complete one.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


def archive_results(all_results: list[dict], models: list[ModelConfig],
                    test_cases: list[TestCase], args, wall_time: float,
                    output_dir: Path = None, partial: bool = False,
                    expected_n: int = None, git_sha: str = None,
                    batch_token: str = None, batch_pid: int = None) -> Path:
    """Archive run results, transcripts, and rollups to a timestamped folder.

    Progressive by design (2026-07 redesign): called once before the pool with
    ``all_results=[]`` to create the folder and seed manifest.json + an initial
    ``partial`` summary.json, then re-invoked after every completed run over the
    completed-so-far set, and finally once more with ``partial=False`` when all
    runs finished. Per-run artifact writes are existence-guarded so re-invocation
    is cheap (each run's files are written exactly once); manifest/summary are
    recomputed and atomically rewritten each call. The whole body runs under
    ``_ARCHIVE_LOCK`` so concurrent callers cannot interleave writes.
    """
    with _ARCHIVE_LOCK:
        return _archive_results_locked(
            all_results, models, test_cases, args, wall_time,
            output_dir, partial, expected_n, git_sha, batch_token, batch_pid,
        )


def _archive_results_locked(all_results, models, test_cases, args, wall_time,
                            output_dir, partial, expected_n, git_sha,
                            batch_token=None, batch_pid=None) -> Path:
    if output_dir is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        # Cross-process uniqueness: two batches starting the same wall-clock
        # second would otherwise collide on results/{timestamp} and cross-write
        # each other's manifest/summary. The short token disambiguates while the
        # LEADING timestamp stays intact so viewer/rerun-queue lexicographic
        # ordering and glob discovery are unaffected.
        tok = batch_token or uuid.uuid4().hex[:6]
        output_dir = BASE_DIR / "benchmarks" / "results" / f"{timestamp}_{tok}"
    output_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    if git_sha is None:
        git_sha = get_git_sha()

    # --- Write manifest.json ---
    manifest = attach_schema_version({
        "benchmark": "dispatch_compliance",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "daaf_git_sha": git_sha,
        # Cross-batch forensics: the per-batch uniqueness token (also the results
        # dir-name suffix and sandbox-suffix tail) and the launching process PID.
        "batch_token": batch_token or output_dir.name.rsplit("_", 1)[-1],
        "batch_pid": batch_pid if batch_pid is not None else os.getpid(),
        **manifest_provenance(
            golden_checkpoints=[tc.golden_checkpoint for tc in test_cases],
            run_records=all_results,
        ),
        "config": {
            "reps": args.reps,
            "parallel": not args.sequential,
            "launch_delay_s": args.delay,
            "timeout_override": args.timeout,
            "test_ids": args.test_id.split(",") if args.test_id else "all",
            "model_keys": args.models.split(",") if args.models else "all",
        },
        "models": [model_manifest_entry(m) for m in models],
        "cases": [
            {
                "id": tc.id,
                "subcategory": tc.subcategory,
                "golden_checkpoint": tc.golden_checkpoint,
                "expected": tc.expected,
            }
            for tc in test_cases
        ],
    })
    _write_json_atomic(output_dir / "manifest.json", manifest)

    # --- Write per-run results and copy transcripts (existence-guarded) ---
    # Each run's artifacts are immutable once written, so re-invocation across
    # progressive rollups writes each run exactly once (the result.json guard).
    for r in all_results:
        run_name = f"{r['case_id']}_{r['model'].replace(' ', '_')}_{r['rep']}"
        run_dir = runs_dir / run_name
        if (run_dir / "result.json").exists():
            continue
        run_dir.mkdir(parents=True, exist_ok=True)

        # Write every flat, Phase-3/3b, purity, and schema-v2 field. Transcript
        # content is copied separately below rather than embedded in result.json.
        result_data = {
            key: value for key, value in r.items()
            if key != "transcript_path"
        }
        _write_json_atomic(run_dir / "result.json", result_data)

        # Copy subagent transcripts if available
        if r.get("session_id"):
            sandbox_subagents = Path(f"{SANDBOX_ROOT}/transcripts/{r['session_id']}/subagents")
            if sandbox_subagents.exists():
                shutil.copytree(sandbox_subagents, run_dir / "subagents", dirs_exist_ok=True)

        # Copy transcript if available
        transcript_src = r.get("transcript_path")
        if transcript_src and Path(transcript_src).exists():
            shutil.copy2(transcript_src, run_dir / "transcript.jsonl")

    # --- Collect all unique criterion names across all runs ---
    all_criterion_names = []
    seen_criteria = set()
    for r in all_results:
        for crit in r.get("criteria", []):
            name = crit["name"]
            if name not in seen_criteria:
                all_criterion_names.append(name)
                seen_criteria.add(name)

    # --- Write summary.json ---
    batch_cost = cost_summary(all_results)
    total_cost = batch_cost["total_cost_usd"]
    errored = sum(1 for r in all_results if r.get("error"))

    # Per-model pass rates. B2: purity-failed (invalid) runs are excluded from
    # score rollups but retained everywhere else — purity_coverage and
    # validity_coverage below are computed over ALL rows for full disclosure.
    model_summaries = {}
    for model in models:
        rows = [r for r in all_results if r["model"] == model.name]
        if not rows:
            continue
        scored_rows = [r for r in rows if is_scorable(r)]
        rates = {}
        for crit_name in all_criterion_names:
            passed = sum(
                1 for r in scored_rows
                if any(c["name"] == crit_name and c["passed"] for c in r.get("criteria", []))
            )
            total = sum(
                1 for r in scored_rows
                if any(c["name"] == crit_name for c in r.get("criteria", []))
            )
            if total > 0:
                rates[crit_name] = {"passed": passed, "total": total, "rate": passed / total}
        # All criteria pass rate (valid runs only)
        all_pass = sum(
            1 for r in scored_rows
            if all(c["passed"] for c in r.get("criteria", []))
            and len(r.get("criteria", [])) > 0
        )
        scored_n = len(scored_rows)
        rates["all_criteria"] = {
            "passed": all_pass,
            "total": scored_n,
            "rate": all_pass / scored_n if scored_n else 0.0,
        }
        model_cost = cost_summary(rows)
        model_summaries[model.name] = {
            "criteria": rates,
            "avg_cost_usd": model_cost["avg_cost_usd"],
            "accounting_coverage": model_cost["accounting_coverage"],
            "purity_coverage": purity_coverage(rows),
            "validity_coverage": validity_coverage(rows),
        }

    # Per-case pass rates (B2: invalid runs excluded from score rollups)
    case_summaries = {}
    for tc in test_cases:
        rows = [r for r in all_results if r["case_id"] == tc.id]
        if not rows:
            continue
        scored_rows = [r for r in rows if is_scorable(r)]
        rates = {}
        for crit_name in all_criterion_names:
            passed = sum(
                1 for r in scored_rows
                if any(c["name"] == crit_name and c["passed"] for c in r.get("criteria", []))
            )
            total = sum(
                1 for r in scored_rows
                if any(c["name"] == crit_name for c in r.get("criteria", []))
            )
            if total > 0:
                rates[crit_name] = {"passed": passed, "total": total, "rate": passed / total}
        all_pass = sum(
            1 for r in scored_rows
            if all(c["passed"] for c in r.get("criteria", []))
            and len(r.get("criteria", [])) > 0
        )
        scored_n = len(scored_rows)
        rates["all_criteria"] = {
            "passed": all_pass,
            "total": scored_n,
            "rate": all_pass / scored_n if scored_n else 0.0,
        }
        case_summaries[tc.id] = {
            "subcategory": tc.subcategory,
            "criteria": rates,
            "validity_coverage": validity_coverage(rows),
        }

    # --- Subagent behavior summary ---
    all_sub_criterion_names = []
    seen_sub = set()
    for r in all_results:
        for sc in r.get("subagent_criteria", []):
            if sc["tier"] == "info":
                continue
            name = sc["name"]
            if name not in seen_sub:
                all_sub_criterion_names.append(name)
                seen_sub.add(name)

    subagent_by_model = {}
    for model in models:
        rows = [r for r in all_results if r["model"] == model.name and r.get("subagent_criteria")]
        if not rows:
            continue
        rates = {}
        for crit_name in all_sub_criterion_names:
            passed = sum(
                1 for r in rows
                if any(c["name"] == crit_name and c["passed"] for c in r.get("subagent_criteria", []))
            )
            total = sum(
                1 for r in rows
                if any(c["name"] == crit_name for c in r.get("subagent_criteria", []))
            )
            if total > 0:
                rates[crit_name] = {"passed": passed, "total": total, "rate": passed / total}
        subagent_by_model[model.name] = {"criteria": rates, "runs_with_subagent": len(rows)}

    total_tool_failures = sum(len(r.get("tool_failures", [])) for r in all_results)
    runs_with_failures = sum(1 for r in all_results if r.get("tool_failures"))
    tool_failure_by_name = {}
    for r in all_results:
        for tf in r.get("tool_failures", []):
            name = tf.get("tool_name", "unknown")
            tool_failure_by_name[name] = tool_failure_by_name.get(name, 0) + 1

    # Aggregate the per-run hook-block vs tool-failure diagnostic counters.
    error_counts_total = {
        "hook_blocks": 0,
        "tool_failures": 0,
        "tool_failures_unclassified": 0,
    }
    for r in all_results:
        ec = r.get("error_counts") or {}
        for key in error_counts_total:
            error_counts_total[key] += ec.get(key, 0)

    runs_completed = len(all_results)
    summary = attach_schema_version({
        "total_runs": runs_completed,
        # Additive self-description so a crashed/partial pass is legible without
        # re-deriving from the runs/ directory.
        "partial": partial,
        "runs_expected": expected_n if expected_n is not None else runs_completed,
        "runs_completed": runs_completed,
        "total_cost_usd": total_cost,
        "accounting_coverage": batch_cost["accounting_coverage"],
        "purity_coverage": purity_coverage(all_results),
        "validity_coverage": validity_coverage(all_results),
        "wall_time_s": round(wall_time, 1),
        "errored_runs": errored,
        "tool_failures": {
            "total": total_tool_failures,
            "runs_affected": runs_with_failures,
            "by_tool": tool_failure_by_name,
        },
        "error_counts": error_counts_total,
        "criterion_names": all_criterion_names,
        "by_model": model_summaries,
        "by_case": case_summaries,
        "subagent_behavior": {
            "criterion_names": all_sub_criterion_names,
            "by_model": subagent_by_model,
        },
    })
    _write_json_atomic(output_dir / "summary.json", summary)

    return output_dir


# --- Console output ---

def print_run_result(r: dict):
    """Print criterion results for a single run."""
    criteria = r.get("criteria", [])

    print(f"\n--- {r['case_id']} | {r['subcategory']} | {r['model']} rep {r['rep']} ---")

    # Print each criterion inline
    crit_strs = []
    for crit in criteria:
        status = "PASS" if crit["passed"] else "FAIL"
        crit_strs.append(f"{crit['name']}={status}")
    if crit_strs:
        print(f"  {' | '.join(crit_strs)}")

    print(
        f"  Turns: {r['turns']} | Billing: {console_billing_label(r)} "
        f"| Duration: {r['duration_s']}s | Tool calls: {r['tool_call_count']}"
    )
    purity = r.get("child_model_purity", {})
    print(
        f"  Child model purity: {purity.get('purity_status', 'unverifiable')} "
        f"(CLI transcript-observed model slug only; not backend-confirmed, "
        f"and never a provider/quant pin check)"
    )
    # Surface filtered placeholders live: they are excluded from the tally, so
    # the console is the only place an operator would otherwise not see them.
    markers = purity.get("observed_non_model_markers") or []
    if markers:
        print(
            f"  Non-model markers observed (excluded from purity tally): "
            f"{', '.join(markers)}"
        )

    if r.get("error"):
        print(f"  ERROR: {r['error']}")

    tool_failures = r.get("tool_failures", [])
    if tool_failures:
        print(f"  Tool failures ({len(tool_failures)}):")
        for tf in tool_failures[:5]:
            print(f"    {tf.get('tool_name', '?')}: {tf.get('content', '')[:120]}")

    # Print detail for any failures
    for crit in criteria:
        if not crit.get("passed", False):
            print(f"  [{crit['name']}] {crit.get('detail', 'no detail')}")

    # Print subagent behavior results if present
    subagent_criteria = r.get("subagent_criteria", [])
    if subagent_criteria:
        sub_strs = []
        for sc in subagent_criteria:
            if sc["tier"] == "info":
                continue
            status = "PASS" if sc["passed"] else "FAIL"
            sub_strs.append(f"{sc['name']}={status}")
        if sub_strs:
            print(f"  Subagent: {' | '.join(sub_strs)}")
        for sc in subagent_criteria:
            if not sc.get("passed", False) and sc["tier"] != "info":
                print(f"  [sub:{sc['name']}] {sc.get('detail', 'no detail')}")
        for sc in subagent_criteria:
            if sc["tier"] == "info":
                print(f"  [info] {sc.get('detail', '')}")


def print_summary(all_results: list[dict], models: list[ModelConfig],
                  test_cases: list[TestCase], wall_time: float):
    """Print summary tables to console."""

    # Collect all unique criterion names in order of first appearance
    all_criterion_names = []
    seen = set()
    for r in all_results:
        for crit in r.get("criteria", []):
            name = crit["name"]
            if name not in seen:
                all_criterion_names.append(name)
                seen.add(name)

    # --- Summary by model ---
    print(f"\n{'='*100}")
    print("SUMMARY BY MODEL")
    print(f"{'='*100}")

    # Build header dynamically from criterion names
    # Truncate criterion names to 14 chars for column display
    short_names = [n[:14] for n in all_criterion_names]
    header = f"{'Model':<20}"
    for sn in short_names:
        header += f" | {sn:<14}"
    header += f" | {'all':<8} | {'avg$':<8}"
    print(header)
    print("-" * len(header))

    for model in models:
        rows = [r for r in all_results if r["model"] == model.name]
        if not rows:
            continue
        # B2: mirror archive_results — invalid (purity-failed) runs are excluded
        # from console score rollups so the console agrees with summary.json.
        # The cost ledger still spans ALL rows for full disclosure.
        scored_rows = [r for r in rows if is_scorable(r)]
        n = len(scored_rows)
        invalid_n = len(rows) - n
        line = f"{model.name:<20}"
        for crit_name in all_criterion_names:
            passed = sum(
                1 for r in scored_rows
                if any(c["name"] == crit_name and c["passed"] for c in r.get("criteria", []))
            )
            applicable = sum(
                1 for r in scored_rows
                if any(c["name"] == crit_name for c in r.get("criteria", []))
            )
            if applicable > 0:
                line += f" | {passed}/{applicable:<12}"
            else:
                line += f" | {'n/a':<14}"
        all_pass = sum(
            1 for r in scored_rows
            if all(c["passed"] for c in r.get("criteria", []))
            and len(r.get("criteria", [])) > 0
        )
        avg_cost = nullable_mean(r["computed_cost_usd"] for r in rows)
        avg_label = f"${avg_cost:.3f}" if avg_cost is not None else "included"
        line += f" | {all_pass}/{n:<6} | {avg_label}"
        if invalid_n:
            line += f"  [excluded {invalid_n} invalid]"
        print(line)

    # --- Summary by case (mode) ---
    if len(test_cases) > 1:
        print(f"\n{'='*100}")
        print("SUMMARY BY MODE")
        print(f"{'='*100}")

        header = f"{'Case':<8} | {'Mode':<30}"
        for sn in short_names:
            header += f" | {sn:<14}"
        header += f" | {'all':<8}"
        print(header)
        print("-" * len(header))

        for tc in test_cases:
            rows = [r for r in all_results if r["case_id"] == tc.id]
            if not rows:
                continue
            # B2: same invalid-run exclusion as the per-model table above.
            scored_rows = [r for r in rows if is_scorable(r)]
            n = len(scored_rows)
            invalid_n = len(rows) - n
            line = f"{tc.id:<8} | {tc.subcategory:<30}"
            for crit_name in all_criterion_names:
                passed = sum(
                    1 for r in scored_rows
                    if any(c["name"] == crit_name and c["passed"] for c in r.get("criteria", []))
                )
                applicable = sum(
                    1 for r in scored_rows
                    if any(c["name"] == crit_name for c in r.get("criteria", []))
                )
                if applicable > 0:
                    line += f" | {passed}/{applicable:<12}"
                else:
                    line += f" | {'n/a':<14}"
            all_pass = sum(
                1 for r in scored_rows
                if all(c["passed"] for c in r.get("criteria", []))
                and len(r.get("criteria", [])) > 0
            )
            line += f" | {all_pass}/{n:<6}"
            if invalid_n:
                line += f"  [excluded {invalid_n} invalid]"
            print(line)

    # --- Subagent behavior summary ---
    runs_with_sub = [r for r in all_results if r.get("subagent_criteria")]
    if runs_with_sub:
        sub_crit_names = []
        sub_seen = set()
        for r in runs_with_sub:
            for sc in r.get("subagent_criteria", []):
                if sc["tier"] == "info":
                    continue
                if sc["name"] not in sub_seen:
                    sub_crit_names.append(sc["name"])
                    sub_seen.add(sc["name"])

        print(f"\n{'='*100}")
        print(f"SUBAGENT BEHAVIOR ({len(runs_with_sub)} runs with dispatch)")
        print(f"{'='*100}")

        sub_short = [n[:20] for n in sub_crit_names]
        header = f"{'Model':<20}"
        for sn in sub_short:
            header += f" | {sn:<20}"
        print(header)
        print("-" * len(header))

        for model in models:
            rows = [r for r in runs_with_sub if r["model"] == model.name]
            if not rows:
                continue
            line = f"{model.name:<20}"
            for crit_name in sub_crit_names:
                passed = sum(
                    1 for r in rows
                    if any(c["name"] == crit_name and c["passed"] for c in r.get("subagent_criteria", []))
                )
                applicable = sum(
                    1 for r in rows
                    if any(c["name"] == crit_name for c in r.get("subagent_criteria", []))
                )
                if applicable > 0:
                    line += f" | {passed}/{applicable:<18}"
                else:
                    line += f" | {'n/a':<20}"
            print(line)

    batch_cost = cost_summary(all_results)
    total_cost = batch_cost["total_cost_usd"]
    total_label = f"${total_cost:.2f}" if total_cost is not None else "cost unavailable"
    errored = sum(1 for r in all_results if r.get("error"))
    error_note = f" ({errored} errored/timed-out)" if errored else ""
    total_tool_failures = sum(len(r.get("tool_failures", [])) for r in all_results)
    tf_note = f" | {total_tool_failures} tool failures" if total_tool_failures else ""
    coverage = format_coverage(batch_cost["accounting_coverage"])
    purity = purity_coverage(all_results)
    purity_label = ", ".join(f"{key}={value}" for key, value in purity.items())
    print(
        f"\nTotal: {len(all_results)} runs{error_note} | {total_label} "
        f"| accounting: {coverage} | purity: {purity_label} "
        f"| {wall_time:.0f}s wall time{tf_note}"
    )


# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="Dispatch compliance benchmark runner")
    parser.add_argument("--reps", type=int, default=3,
                        help="Number of repetitions per case x model (default: 3)")
    add_model_args(parser)
    parser.add_argument("--test-id", type=str, default=None,
                        help="Comma-separated test case IDs to run (default: all)")
    parser.add_argument("--sequential", action="store_true",
                        help="Run sequentially instead of parallel")
    parser.add_argument("--delay", type=float, default=LAUNCH_DELAY_SECONDS,
                        help="Seconds between parallel launches (default: 2)")
    parser.add_argument("--max-concurrent", type=int, default=MAX_CONCURRENT_RUNS,
                        help=f"Max simultaneously in-flight runs "
                             f"(default: {MAX_CONCURRENT_RUNS}). Caps the thread "
                             f"pool; --delay still staggers submits")
    parser.add_argument("--timeout", type=int, default=900,
                        help="Per-run timeout in seconds. Uniform 900s logistical "
                             "cap (2026-07-21 walltime redesign; formerly "
                             "120/180/300/300 per-phase). High cap so runs complete "
                             "rather than censor; duration is now the measured axis")
    parser.add_argument("--watchdog-poll", type=int, default=60,
                        help="Watchdog poll interval in seconds (default: 60). "
                             "How often the executor checks for score-complete "
                             "early stop and transcript staleness")
    parser.add_argument("--stall-threshold", type=int, default=330,
                        help="Staleness cutoff in seconds for one stalled read "
                             "(default: 330; K3-validated — 296s of legitimate "
                             "dead air was observed on a passing run, so 240s "
                             "false-positives). Two consecutive stalled reads "
                             "trigger a stall kill")
    parser.add_argument("--stall-retries", type=int, default=1,
                        help="Times to relaunch a stalled rep from a fresh "
                             "sandbox (default: 1). A rep that stalls again after "
                             "its last retry is recorded permanently as stalled")
    parser.add_argument("--no-early-stop", action="store_true",
                        help="Disable score-complete early stop (escape hatch). "
                             "Stall detection still runs; runs execute to natural "
                             "completion or the wall-clock timeout")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip cost confirmation prompt")
    parser.add_argument("--no-fixture-restore", action="store_true",
                        help="Skip the pre-batch restore of datasets/test_fixtures/ "
                             "to git HEAD (escape hatch for intentional in-progress "
                             "fixture edits)")
    add_preflight_arg(parser)
    args = parser.parse_args()

    # Load and filter models
    all_models = load_models(MODELS_FILE)
    model_keys = args.models.split(",") if args.models else None
    models = filter_models(all_models, model_keys=model_keys, provider=args.provider)
    if not models:
        print("ERROR: No valid models selected.")
        sys.exit(1)

    # W2 (2026-07-28): fail fast on any sandbox-slug collision across the
    # selected models before any run launches — colliding slugs would share a
    # _sandbox/run_* directory and cross-contaminate fixtures/transcripts.
    assert_unique_sandbox_slugs(models)

    # Load test cases
    all_cases = load_test_cases(CASES_FILE)

    if args.test_id:
        test_ids = {t.strip() for t in args.test_id.split(",")}
        test_cases = [tc for tc in all_cases if tc.id in test_ids]
        if not test_cases:
            print(f"ERROR: No test cases matched IDs: {test_ids}")
            print(f"Available: {', '.join(tc.id for tc in all_cases)}")
            sys.exit(1)
    else:
        test_cases = all_cases

    # Batch route validation is the first action after model/case selection.
    # The preflight-only branch returns before fixture restoration, checkpoint
    # inspection, sandbox work, estimates, run-list/executor calls, or archives.
    if run_preflight(models, preflight_only=args.preflight_only):
        return

    # Validate golden checkpoints exist for all selected cases
    missing_checkpoints = []
    for tc in test_cases:
        if not tc.golden_checkpoint:
            missing_checkpoints.append(f"{tc.id}: no golden_checkpoint field")
        else:
            golden_path = BASE_DIR / tc.golden_checkpoint
            if not golden_path.exists():
                missing_checkpoints.append(f"{tc.id}: {golden_path} not found")
    if missing_checkpoints:
        print("ERROR: Missing golden checkpoints:")
        for msg in missing_checkpoints:
            print(f"  {msg}")
        sys.exit(1)

    total_runs = len(test_cases) * len(models) * args.reps
    print(f"Dispatch Compliance Benchmark")
    print(f"Cases: {len(test_cases)} | Models: {', '.join(m.name for m in models)}")
    print(f"Reps: {args.reps} | Total runs: {total_runs}")
    mode_str = "sequential" if args.sequential else f"parallel (delay={args.delay}s)"
    timeout_str = f" | timeout={args.timeout}s" if args.timeout else ""
    print(f"Mode: {mode_str}{timeout_str}")

    # Print checkpoint info
    print(f"\nGolden checkpoint:")
    golden_path = BASE_DIR / test_cases[0].golden_checkpoint
    line_count = get_checkpoint_line_count(golden_path)
    print(f"  {test_cases[0].golden_checkpoint}: {line_count} lines")
    print(f"\nExpected dispatches:")
    for tc in test_cases:
        expected_agent = tc.expected.get("subagent_dispatched", "?")
        print(f"  {tc.id} ({tc.subcategory}): -> {expected_agent}")

    case_ids = [tc.id for tc in test_cases] if args.test_id else None
    est = estimate_batch_cost(models, "dispatch_compliance", case_ids=case_ids, reps=args.reps)
    print(f"\n{format_estimate(est)}\n")

    if not args.yes and est["total"] > 0.50:
        confirm = input("Proceed? [y/N] ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    # Per-batch fixture restore: contamination from prior batches is reset to
    # git HEAD before any run thread copies the shared originals (see
    # restore_fixtures docstring for why this must never run mid-batch).
    if args.no_fixture_restore:
        print("Skipping fixture restore (--no-fixture-restore).")
    else:
        restore_fixtures()

    print(f"{'='*100}")
    sys.stdout.flush()

    # Per-batch uniqueness token (cross-process safety): one short token per
    # runner invocation, reused for BOTH the results dir-name suffix and every
    # sandbox suffix so concurrent batches never collide on results/ dirs or
    # _sandbox/run_ dirs, even when running the same model at the same second.
    batch_token = uuid.uuid4().hex[:6]
    batch_pid = os.getpid()

    # Build run list: case x model x rep
    runs = []
    for tc in test_cases:
        for model in models:
            for rep in range(args.reps):
                suffix = f"{tc.id}_{sandbox_slug(model.name)}_{rep}_{batch_token}"
                runs.append((tc, model, rep, suffix))

    all_results = []
    expected_n = len(runs)
    git_sha = get_git_sha()
    start_time = time.time()

    # Create the results folder and seed manifest.json + an initial partial
    # summary.json BEFORE any run launches, so a killed pass still leaves a
    # self-describing (partial) archive.
    output_dir = archive_results(
        [], models, test_cases, args, 0.0,
        output_dir=None, partial=True, expected_n=expected_n, git_sha=git_sha,
        batch_token=batch_token, batch_pid=batch_pid,
    )
    print(f"Progressive archive: {output_dir}")
    sys.stdout.flush()

    try:
        if args.sequential:
            for tc, model, rep, suffix in runs:
                try:
                    r = run_one(
                        tc, model, rep, suffix, timeout_override=args.timeout,
                        watchdog_poll=args.watchdog_poll,
                        stall_threshold=args.stall_threshold,
                        stall_retries=args.stall_retries,
                        enable_early_stop=not args.no_early_stop,
                    )
                except Exception as e:
                    r = _error_result(tc, model, rep, f"{type(e).__name__}: {e}")
                all_results.append(r)
                print_run_result(r)
                # Progressive per-run archive + incremental rollup.
                archive_results(
                    all_results, models, test_cases, args,
                    time.time() - start_time, output_dir=output_dir,
                    partial=True, expected_n=expected_n, git_sha=git_sha,
                    batch_token=batch_token, batch_pid=batch_pid,
                )
                sys.stdout.flush()
        else:
            max_workers = min(len(runs), args.max_concurrent)
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {}
                for i, (tc, model, rep, suffix) in enumerate(runs):
                    future = pool.submit(
                        run_one, tc, model, rep, suffix,
                        timeout_override=args.timeout,
                        watchdog_poll=args.watchdog_poll,
                        stall_threshold=args.stall_threshold,
                        stall_retries=args.stall_retries,
                        enable_early_stop=not args.no_early_stop,
                    )
                    futures[future] = (tc, model, rep)
                    if i < len(runs) - 1:
                        time.sleep(args.delay)

                for future in concurrent.futures.as_completed(futures):
                    tc, model, rep = futures[future]
                    try:
                        r = future.result()
                    except Exception as e:
                        r = _error_result(tc, model, rep, f"{type(e).__name__}: {e}")
                    all_results.append(r)
                    print_run_result(r)
                    # Progressive per-run archive + incremental rollup.
                    archive_results(
                        all_results, models, test_cases, args,
                        time.time() - start_time, output_dir=output_dir,
                        partial=True, expected_n=expected_n, git_sha=git_sha,
                        batch_token=batch_token, batch_pid=batch_pid,
                    )
                    sys.stdout.flush()
    finally:
        # Final rollup runs even on KeyboardInterrupt/exception: partial=False
        # only when every expected run completed.
        wall_time = time.time() - start_time
        all_done = len(all_results) == expected_n
        archive_results(
            all_results, models, test_cases, args, wall_time,
            output_dir=output_dir, partial=not all_done,
            expected_n=expected_n, git_sha=git_sha,
            batch_token=batch_token, batch_pid=batch_pid,
        )

    # Sort results by case order, then model order, then rep
    case_order = {tc.id: i for i, tc in enumerate(test_cases)}
    model_order = {m.name: i for i, m in enumerate(models)}
    all_results.sort(key=lambda r: (case_order.get(r["case_id"], 99), model_order.get(r["model"], 99), r["rep"]))

    # Print summary
    print_summary(all_results, models, test_cases, wall_time)

    print(f"\nResults archived to: {output_dir}")

    # Post-batch contamination check (detect + warn only — never restores).
    # Printed last so the warning is the final, most visible console output.
    check_fixture_contamination()


if __name__ == "__main__":
    main()
