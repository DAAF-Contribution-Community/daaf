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
import json
import os
import shutil
import subprocess
import sys
import time
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
    attach_schema_version,
    build_error_artifact,
    build_run_artifact,
    child_model_purity,
    console_billing_label,
    cost_summary,
    format_coverage,
    model_manifest_entry,
    nullable_mean,
    purity_coverage,
    run_preflight,
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
)

# --- Config ---

BASE_DIR = Path("/daaf")
CASES_FILE = BASE_DIR / "benchmarks" / "datasets" / "dispatch_compliance" / "cases.jsonl"
MODELS_FILE = BASE_DIR / "benchmarks" / "config" / "models.yaml"

LAUNCH_DELAY_SECONDS = 2


# --- Load config ---

def load_test_cases(path: Path) -> list[TestCase]:
    """Load test cases from cases.jsonl."""
    return TestCase.load_from_jsonl(path)


# --- Scoring ---

def score_run(
    session_id: str,
    test_case: TestCase,
    requested_child_model_id: str,
) -> dict:
    """Score dispatch behavior and collect CLI-observed child-model evidence.

    Returns phase criteria, transcript diagnostics, and a non-scoring purity
    record. Purity is infrastructure evidence only; it does not alter any
    deterministic behavioral criterion.
    """
    # Locate child transcripts even when the parent transcript is absent: their
    # independent CLI records may still establish dispatch and model identity.
    subagent_transcripts = find_subagent_transcripts(session_id)
    purity = child_model_purity(subagent_transcripts, requested_child_model_id)

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
    }


# --- Fixture isolation ---

FIXTURE_PREFIX = "/daaf/benchmarks/datasets/test_fixtures/"


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
    """
    entries = _fixture_status_entries()
    if entries is None:
        return
    if not entries:
        print(f"Fixtures clean: {FIXTURE_PREFIX} matches git HEAD — no restore needed.")
        return

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
    """Copy referenced test fixtures into the sandbox and rewrite the prompt.

    Scans the prompt for paths under test_fixtures/, copies each file to
    {sandbox_dir}/fixtures/{subdir}/{filename}, and returns a modified
    TestCase with updated paths. Originals are never touched by subagents.
    """
    import re
    import copy

    pattern = re.escape(FIXTURE_PREFIX) + r"[^\s\"')]+"
    matches = re.findall(pattern, test_case.prompt)

    if not matches:
        return test_case

    fixtures_dir = Path(sandbox_dir) / "fixtures"
    modified_prompt = test_case.prompt

    for orig_path in matches:
        src = Path(orig_path)
        if not src.exists():
            continue
        rel = src.relative_to(Path(FIXTURE_PREFIX).parent)
        dest = fixtures_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        modified_prompt = modified_prompt.replace(orig_path, str(dest))

    workspace_dir = Path(sandbox_dir) / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # Copy run_with_capture.sh so subagents find it at the expected relative path.
    # Subagents treat the workspace as BASE_DIR and look for scripts/run_with_capture.sh there.
    rwc_src = Path("/daaf/scripts/run_with_capture.sh")
    if rwc_src.exists():
        rwc_dest = workspace_dir / "scripts" / "run_with_capture.sh"
        rwc_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(rwc_src, rwc_dest)

    modified_prompt += (
        f" Use {workspace_dir} as the project workspace: every file or folder you"
        f" or your subagents create must live under {sandbox_dir} — do not create"
        f" scripts, outputs, or research project folders anywhere else in the"
        f" repository."
    )

    tc = copy.deepcopy(test_case)
    tc.prompt = modified_prompt
    return tc


# --- Run + diagnose ---

def run_one(test_case: TestCase, model: ModelConfig, rep: int,
            sandbox_suffix: str, timeout_override=None):
    """Execute a single benchmark run with checkpoint scoring."""
    sandbox_dir = f"/daaf/benchmarks/_sandbox/run_{sandbox_suffix}"

    # Wipe and recreate the sandbox BEFORE staging fixtures, and tell
    # execute_run() -> prepare_sandbox() not to wipe it again
    # (wipe_sandbox=False). Previously fixtures were staged first and
    # prepare_sandbox()'s rmtree deleted them — at model launch the rewritten
    # prompt pointed at nonexistent sandbox paths, so models hunted the files
    # by name and contaminated the originals under datasets/test_fixtures/.
    sandbox_path = Path(sandbox_dir)
    if sandbox_path.exists():
        shutil.rmtree(sandbox_path)
    sandbox_path.mkdir(parents=True, exist_ok=True)

    sandboxed_case = prepare_fixtures(test_case, sandbox_dir)

    config = RunConfig(
        test_case=sandboxed_case,
        model=model,
        run_index=rep,
        sandbox_dir=sandbox_dir,
        wipe_sandbox=False,
        timeout_override=timeout_override,
    )

    start = time.time()
    result = execute_run(config)
    elapsed = time.time() - start

    # Always attempt scoring if we have a session_id — even for timed-out runs,
    # the live session file may contain partial but scorable transcript data.
    if result.session_id:
        time.sleep(1)
        scored = score_run(result.session_id, test_case, model.id)
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
            "child_model_purity": child_model_purity([], model.id),
            "transcript_path": None,
            "tool_call_count": 0,
        }

    # Archive transcript + subagent transcripts BEFORE cleanup deletes them
    archived_transcript = None
    if result.session_id:
        transcript_src = scored.get("transcript_path")
        if transcript_src and Path(transcript_src).exists():
            archive_dir = Path(f"/daaf/benchmarks/_sandbox/transcripts/{result.session_id}")
            archive_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(transcript_src, archive_dir / "transcript.jsonl")
            archived_transcript = str(archive_dir / "transcript.jsonl")
            subagent_dir = Path.home() / ".claude" / "projects" / "-daaf" / result.session_id / "subagents"
            if subagent_dir.exists():
                shutil.copytree(subagent_dir, archive_dir / "subagents", dirs_exist_ok=True)

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
            "subagent_criteria": scored.get("subagent_criteria", []),
            "subagent_transcript_missing": scored.get(
                "subagent_transcript_missing", False
            ),
            "child_model_purity": scored["child_model_purity"],
            "transcript_path": archived_transcript or scored.get("transcript_path"),
            "tool_call_count": scored.get("tool_call_count", 0),
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
            "subagent_criteria": [],
            "subagent_transcript_missing": True,
            "child_model_purity": child_model_purity([], model.id),
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


def archive_results(all_results: list[dict], models: list[ModelConfig],
                    test_cases: list[TestCase], args, wall_time: float) -> Path:
    """Archive all run results, transcripts, and summary to a timestamped folder."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = BASE_DIR / "benchmarks" / "results" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    git_sha = get_git_sha()

    # --- Write manifest.json ---
    manifest = attach_schema_version({
        "benchmark": "dispatch_compliance",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "daaf_git_sha": git_sha,
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
    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    # --- Write per-run results and copy transcripts ---
    for r in all_results:
        run_name = f"{r['case_id']}_{r['model'].replace(' ', '_')}_{r['rep']}"
        run_dir = runs_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)

        # Write every flat, Phase-3/3b, purity, and schema-v2 field. Transcript
        # content is copied separately below rather than embedded in result.json.
        result_data = {
            key: value for key, value in r.items()
            if key != "transcript_path"
        }
        with open(run_dir / "result.json", "w") as f:
            json.dump(result_data, f, indent=2)

        # Copy subagent transcripts if available
        if r.get("session_id"):
            sandbox_subagents = Path(f"/daaf/benchmarks/_sandbox/transcripts/{r['session_id']}/subagents")
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

    # Per-model pass rates
    model_summaries = {}
    for model in models:
        rows = [r for r in all_results if r["model"] == model.name]
        if not rows:
            continue
        rates = {}
        for crit_name in all_criterion_names:
            passed = sum(
                1 for r in rows
                if any(c["name"] == crit_name and c["passed"] for c in r.get("criteria", []))
            )
            total = sum(
                1 for r in rows
                if any(c["name"] == crit_name for c in r.get("criteria", []))
            )
            if total > 0:
                rates[crit_name] = {"passed": passed, "total": total, "rate": passed / total}
        # All criteria pass rate
        all_pass = sum(
            1 for r in rows
            if all(c["passed"] for c in r.get("criteria", []))
            and len(r.get("criteria", [])) > 0
        )
        rates["all_criteria"] = {"passed": all_pass, "total": len(rows), "rate": all_pass / len(rows)}
        model_cost = cost_summary(rows)
        model_summaries[model.name] = {
            "criteria": rates,
            "avg_cost_usd": model_cost["avg_cost_usd"],
            "accounting_coverage": model_cost["accounting_coverage"],
            "purity_coverage": purity_coverage(rows),
        }

    # Per-case pass rates
    case_summaries = {}
    for tc in test_cases:
        rows = [r for r in all_results if r["case_id"] == tc.id]
        if not rows:
            continue
        rates = {}
        for crit_name in all_criterion_names:
            passed = sum(
                1 for r in rows
                if any(c["name"] == crit_name and c["passed"] for c in r.get("criteria", []))
            )
            total = sum(
                1 for r in rows
                if any(c["name"] == crit_name for c in r.get("criteria", []))
            )
            if total > 0:
                rates[crit_name] = {"passed": passed, "total": total, "rate": passed / total}
        all_pass = sum(
            1 for r in rows
            if all(c["passed"] for c in r.get("criteria", []))
            and len(r.get("criteria", [])) > 0
        )
        rates["all_criteria"] = {"passed": all_pass, "total": len(rows), "rate": all_pass / len(rows)}
        case_summaries[tc.id] = {
            "subcategory": tc.subcategory,
            "criteria": rates,
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

    summary = attach_schema_version({
        "total_runs": len(all_results),
        "total_cost_usd": total_cost,
        "accounting_coverage": batch_cost["accounting_coverage"],
        "purity_coverage": purity_coverage(all_results),
        "wall_time_s": round(wall_time, 1),
        "errored_runs": errored,
        "tool_failures": {
            "total": total_tool_failures,
            "runs_affected": runs_with_failures,
            "by_tool": tool_failure_by_name,
        },
        "criterion_names": all_criterion_names,
        "by_model": model_summaries,
        "by_case": case_summaries,
        "subagent_behavior": {
            "criterion_names": all_sub_criterion_names,
            "by_model": subagent_by_model,
        },
    })
    with open(output_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

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
        f"(CLI transcript-observed; not backend-confirmed)"
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
        n = len(rows)
        line = f"{model.name:<20}"
        for crit_name in all_criterion_names:
            passed = sum(
                1 for r in rows
                if any(c["name"] == crit_name and c["passed"] for c in r.get("criteria", []))
            )
            applicable = sum(
                1 for r in rows
                if any(c["name"] == crit_name for c in r.get("criteria", []))
            )
            if applicable > 0:
                line += f" | {passed}/{applicable:<12}"
            else:
                line += f" | {'n/a':<14}"
        all_pass = sum(
            1 for r in rows
            if all(c["passed"] for c in r.get("criteria", []))
            and len(r.get("criteria", [])) > 0
        )
        avg_cost = nullable_mean(r["computed_cost_usd"] for r in rows)
        avg_label = f"${avg_cost:.3f}" if avg_cost is not None else "included"
        line += f" | {all_pass}/{n:<6} | {avg_label}"
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
            n = len(rows)
            line = f"{tc.id:<8} | {tc.subcategory:<30}"
            for crit_name in all_criterion_names:
                passed = sum(
                    1 for r in rows
                    if any(c["name"] == crit_name and c["passed"] for c in r.get("criteria", []))
                )
                applicable = sum(
                    1 for r in rows
                    if any(c["name"] == crit_name for c in r.get("criteria", []))
                )
                if applicable > 0:
                    line += f" | {passed}/{applicable:<12}"
                else:
                    line += f" | {'n/a':<14}"
            all_pass = sum(
                1 for r in rows
                if all(c["passed"] for c in r.get("criteria", []))
                and len(r.get("criteria", [])) > 0
            )
            line += f" | {all_pass}/{n:<6}"
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
    parser.add_argument("--timeout", type=int, default=300,
                        help="Per-run timeout in seconds (Phase 3 default: 300; "
                             "standardized 2026-07-10, replacing cost-tier defaults)")
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

    # Build run list: case x model x rep
    runs = []
    for tc in test_cases:
        for model in models:
            for rep in range(args.reps):
                suffix = f"{tc.id}_{model.name.replace(' ', '_')}_{rep}"
                runs.append((tc, model, rep, suffix))

    all_results = []
    start_time = time.time()

    if args.sequential:
        for tc, model, rep, suffix in runs:
            try:
                r = run_one(tc, model, rep, suffix, timeout_override=args.timeout)
            except Exception as e:
                r = _error_result(tc, model, rep, f"{type(e).__name__}: {e}")
            all_results.append(r)
            print_run_result(r)
            sys.stdout.flush()
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(runs)) as pool:
            futures = {}
            for i, (tc, model, rep, suffix) in enumerate(runs):
                future = pool.submit(run_one, tc, model, rep, suffix, timeout_override=args.timeout)
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
                sys.stdout.flush()

    wall_time = time.time() - start_time

    # Sort results by case order, then model order, then rep
    case_order = {tc.id: i for i, tc in enumerate(test_cases)}
    model_order = {m.name: i for i, m in enumerate(models)}
    all_results.sort(key=lambda r: (case_order.get(r["case_id"], 99), model_order.get(r["model"], 99), r["rep"]))

    # Print summary
    print_summary(all_results, models, test_cases, wall_time)

    # Archive results
    output_dir = archive_results(all_results, models, test_cases, args, wall_time)
    print(f"\nResults archived to: {output_dir}")

    # Post-batch contamination check (detect + warn only — never restores).
    # Printed last so the warning is the final, most visible console output.
    check_fixture_contamination()


if __name__ == "__main__":
    main()
