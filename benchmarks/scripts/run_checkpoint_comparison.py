"""Parallel golden checkpoint benchmark with rich diagnostic output.

Runs multiple model×effort configurations concurrently with staggered launches.
Outputs structured JSON results suitable for future browser-based viewing.

Usage:
    python3 benchmarks/scripts/run_checkpoint_comparison.py
    python3 benchmarks/scripts/run_checkpoint_comparison.py --reps 1 --models haiku,sonnet
"""

import argparse
import concurrent.futures
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/daaf")

from benchmarks.harness.models import TestCase, ModelConfig, RunConfig
from benchmarks.harness.executor import execute_run
from benchmarks.harness.collector import get_audit_log_position
from benchmarks.scorers.deterministic.checkpoint_adherence import (
    extract_new_tool_calls,
    find_benchmark_transcript,
    get_checkpoint_line_count,
)

# --- Config ---

GOLDEN_CHECKPOINT = "benchmarks/golden/ad_hoc/after_confirmation.jsonl"
CHECKPOINT_LINES = get_checkpoint_line_count(Path("/daaf") / GOLDEN_CHECKPOINT)

TEST_CASE = TestCase(
    id="gc-ah-test",
    category="golden_checkpoint",
    subcategory="ad_hoc",
    prompt="Sounds good, lets go.",
    expected={
        "documents_read": ["ad-hoc-collaboration-mode.md", "statistical-modeling.md"],
        "skills_loaded": ["data-scientist"],
    },
    golden_checkpoint=GOLDEN_CHECKPOINT,
    turn_limit=10,
    cost_tier="medium",
    hard_requirements=["documents_read", "skills_loaded"],
)

ALL_MODELS = {
    # --- Anthropic (direct) ---
    "haiku": ModelConfig(id="claude-haiku-4-5-20251001", name="Haiku 4.5"),
    "sonnet-low": ModelConfig(id="claude-sonnet-4-6", name="Sonnet 4.6 low", effort_level="low"),
    "sonnet-high": ModelConfig(id="claude-sonnet-4-6", name="Sonnet 4.6 high", effort_level="high"),
    "sonnet-max": ModelConfig(id="claude-sonnet-4-6", name="Sonnet 4.6 max", effort_level="max"),
    "opus-45": ModelConfig(id="claude-opus-4-5", name="Opus 4.5"),
    "opus-46-low": ModelConfig(id="claude-opus-4-6", name="Opus 4.6 low", effort_level="low"),
    "opus-46-medium": ModelConfig(id="claude-opus-4-6", name="Opus 4.6 medium", effort_level="medium"),
    "opus-46-high": ModelConfig(id="claude-opus-4-6", name="Opus 4.6 high", effort_level="high"),
    "opus-46-max": ModelConfig(id="claude-opus-4-6", name="Opus 4.6 max", effort_level="max"),
    "opus-47-low": ModelConfig(id="claude-opus-4-7", name="Opus 4.7 low", effort_level="low"),
    "opus-47-medium": ModelConfig(id="claude-opus-4-7", name="Opus 4.7 medium", effort_level="medium"),
    "opus-47-high": ModelConfig(id="claude-opus-4-7", name="Opus 4.7 high", effort_level="high"),
    "opus-47-xhigh": ModelConfig(id="claude-opus-4-7", name="Opus 4.7 xhigh", effort_level="xhigh"),
    "opus-47-max": ModelConfig(id="claude-opus-4-7", name="Opus 4.7 max", effort_level="max"),
    # --- OpenRouter models (no effort_level — Anthropic-specific) ---
    "glm-5.1": ModelConfig(id="z-ai/glm-5.1:atlas-cloud/fp8", name="GLM 5.1"),
    "kimi-k2.6": ModelConfig(id="kimi-k2.6:siliconflow/fp8", name="Kimi K2.6"),
    #"qwen3.6-35b": ModelConfig(id="qwen/qwen3.6-35b-a3b", name="Qwen 3.6 35B"),
    "qwen3.6-27b": ModelConfig(id="qwen/qwen3.6-27b:venice/fp8", name="Qwen 3.6 27B"),
    "gemma-4-31b": ModelConfig(id="google/gemma-4-31b-it:venice/bf16", name="Gemma 4 31B"),
    "gemma-4-26b": ModelConfig(id="google/gemma-4-26b-a4b-it:novita/bf16", name="Gemma 4 26B"),
    "dsv4-pro": ModelConfig(id="deepseek/deepseek-v4-pro:atlas-cloud/fp8", name="DeepSeek V4 Pro"),
    "dsv4-flash": ModelConfig(id="deepseek/deepseek-v4-flash:atlas-cloud/fp8", name="DeepSeek V4 Flash"),
    "gemini-3.1-pro": ModelConfig(id="google/gemini-3.1-pro-preview:google-vertex", name="Gemini 3.1 Pro"),
}

LAUNCH_DELAY_SECONDS = 2


# --- Run + diagnose ---

def extract_diagnostics(session_id, checkpoint_lines):
    """Extract rich diagnostics from a session transcript."""
    transcript_path = find_benchmark_transcript(session_id)
    if not transcript_path:
        return {"error": "transcript not found", "references": [], "assistant_messages": []}

    tool_calls = extract_new_tool_calls(transcript_path, checkpoint_lines)

    references = []
    failed_reads = []
    for tc in tool_calls:
        succeeded = tc.get("succeeded", True)
        if tc["name"] == "Skill" and tc["skill"]:
            references.append({"type": "skill", "name": tc["skill"], "succeeded": succeeded})
        elif tc["name"] == "Read" and tc["file_path"]:
            entry = {"type": "read", "path": tc["file_path"].split("/")[-1], "succeeded": succeeded}
            if succeeded:
                references.append(entry)
            else:
                failed_reads.append({"path": tc["file_path"], "succeeded": False})

    assistant_messages = []
    with open(transcript_path) as f:
        lines = f.readlines()
    for line in lines[checkpoint_lines:]:
        try:
            record = json.loads(line.strip())
            if record.get("type") == "assistant":
                for block in record.get("message", {}).get("content", []):
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text and text != "No response requested.":
                            assistant_messages.append(text[:300])
        except json.JSONDecodeError:
            continue

    checks = {
        "mode_ref": any(r["type"] == "read" and r["path"] == "ad-hoc-collaboration-mode.md" and r.get("succeeded", True) for r in references),
        "ds_skill": any(r["type"] == "skill" and r["name"] == "data-scientist" and r.get("succeeded", True) for r in references),
        "stat_ref": any(r["type"] == "read" and r["path"] == "statistical-modeling.md" and r.get("succeeded", True) for r in references),
    }

    return {
        "references": references,
        "failed_reads": failed_reads,
        "assistant_messages": assistant_messages,
        "checks": checks,
        "tool_call_count": len(tool_calls),
    }


def run_one(model, rep, sandbox_suffix, timeout_override=None):
    """Execute a single benchmark run with diagnostics."""
    sandbox_dir = f"/daaf/benchmarks/_sandbox/run_{sandbox_suffix}"
    config = RunConfig(
        test_case=TEST_CASE,
        model=model,
        run_index=rep,
        sandbox_dir=sandbox_dir,
        timeout_override=timeout_override,
    )

    start = time.time()
    result = execute_run(config)
    elapsed = time.time() - start

    # Skip diagnostics when the run failed — no transcript to inspect
    if result.error or not result.session_id:
        diag = {"checks": {}, "references": [], "failed_reads": [], "assistant_messages": [], "tool_call_count": 0}
    else:
        time.sleep(1)
        diag = extract_diagnostics(result.session_id, CHECKPOINT_LINES)

    return {
        "model": model.name,
        "model_id": model.id,
        "effort_level": model.effort_level or "default",
        "rep": rep,
        "session_id": result.session_id,
        "turns": result.total_turns,
        "cost_usd": result.total_cost_usd,
        "duration_s": round(elapsed, 1),
        "error": result.error,
        "checks": diag.get("checks", {}),
        "references_loaded": diag.get("references", []),
        "failed_reads": diag.get("failed_reads", []),
        "assistant_previews": diag.get("assistant_messages", []),
        "tool_call_count": diag.get("tool_call_count", 0),
    }


def _error_result(model, rep, error_msg):
    """Build a safe result dict for a run that failed before returning data."""
    return {
        "model": model.name,
        "model_id": model.id,
        "effort_level": model.effort_level or "default",
        "rep": rep,
        "session_id": "",
        "turns": 0,
        "cost_usd": 0.0,
        "duration_s": 0.0,
        "error": error_msg,
        "checks": {},
        "references_loaded": [],
        "failed_reads": [],
        "assistant_previews": [],
        "tool_call_count": 0,
    }


# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="Golden checkpoint benchmark comparison")
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--models", type=str, default=None,
                        help="Comma-separated model keys: haiku,sonnet-low,sonnet-high,opus-low,opus-high")
    parser.add_argument("--sequential", action="store_true", help="Run sequentially instead of parallel")
    parser.add_argument("--delay", type=float, default=LAUNCH_DELAY_SECONDS,
                        help="Seconds between parallel launches (default: 2)")
    parser.add_argument("--timeout", type=int, default=None,
                        help="Override per-run timeout in seconds (default: cost-tier based)")
    args = parser.parse_args()

    if args.models:
        model_keys = [k.strip() for k in args.models.split(",")]
        models = [ALL_MODELS[k] for k in model_keys if k in ALL_MODELS]
    else:
        models = list(ALL_MODELS.values())

    total_runs = len(models) * args.reps
    print(f"Golden Checkpoint Benchmark: gc-ah-test")
    print(f"Models: {', '.join(m.name for m in models)}")
    print(f"Reps: {args.reps} | Total runs: {total_runs}")
    mode_str = 'sequential' if args.sequential else f'parallel (delay={args.delay}s)'
    timeout_str = f" | timeout={args.timeout}s" if args.timeout else ""
    print(f"Mode: {mode_str}{timeout_str}")
    print(f"{'='*70}")
    sys.stdout.flush()

    # Build run list
    runs = []
    for model in models:
        for rep in range(args.reps):
            suffix = f"{model.name.replace(' ', '_')}_{rep}"
            runs.append((model, rep, suffix))

    all_results = []
    start_time = time.time()

    if args.sequential:
        for model, rep, suffix in runs:
            try:
                r = run_one(model, rep, suffix, timeout_override=args.timeout)
            except Exception as e:
                r = _error_result(model, rep, f"{type(e).__name__}: {e}")
            all_results.append(r)
            print_run_result(r)
            sys.stdout.flush()
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(runs)) as pool:
            futures = {}
            for i, (model, rep, suffix) in enumerate(runs):
                future = pool.submit(run_one, model, rep, suffix, timeout_override=args.timeout)
                futures[future] = (model, rep)
                if i < len(runs) - 1:
                    time.sleep(args.delay)

            for future in concurrent.futures.as_completed(futures):
                model, rep = futures[future]
                try:
                    r = future.result()
                except Exception as e:
                    r = _error_result(model, rep, f"{type(e).__name__}: {e}")
                all_results.append(r)
                print_run_result(r)
                sys.stdout.flush()

    wall_time = time.time() - start_time

    # Sort results by model order then rep
    model_order = {m.name: i for i, m in enumerate(models)}
    all_results.sort(key=lambda r: (model_order.get(r["model"], 99), r["rep"]))

    # Print summary table
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"{'Model':<22} | {'mode_ref':<10} | {'ds_skill':<10} | {'stat_ref':<10} | {'all_3':<8} | {'avg$':<8}")
    print("-" * 80)

    for model in models:
        rows = [r for r in all_results if r["model"] == model.name]
        if not rows:
            continue
        mr = sum(1 for r in rows if r["checks"].get("mode_ref"))
        ds = sum(1 for r in rows if r["checks"].get("ds_skill"))
        sr = sum(1 for r in rows if r["checks"].get("stat_ref"))
        a3 = sum(1 for r in rows if all(r["checks"].get(k) for k in ["mode_ref", "ds_skill", "stat_ref"]))
        avg_cost = sum(r["cost_usd"] for r in rows) / len(rows)
        print(f"{model.name:<22} | {mr}/{len(rows):<8} | {ds}/{len(rows):<8} | {sr}/{len(rows):<8} | {a3}/{len(rows):<6} | ${avg_cost:.3f}")

    total_cost = sum(r["cost_usd"] for r in all_results)
    errored = sum(1 for r in all_results if r.get("error"))
    error_note = f" ({errored} errored/timed-out)" if errored else ""
    print(f"\nTotal: {len(all_results)} runs{error_note} | ${total_cost:.2f} | {wall_time:.0f}s wall time")

    # Write structured JSON output
    output_dir = Path("/daaf/benchmarks/results") / datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)

    output = {
        "benchmark": "gc-ah-test",
        "golden_checkpoint": GOLDEN_CHECKPOINT,
        "checkpoint_lines": CHECKPOINT_LINES,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "reps": args.reps,
            "parallel": not args.sequential,
            "launch_delay_s": args.delay,
        },
        "summary": {
            "total_runs": len(all_results),
            "total_cost_usd": total_cost,
            "wall_time_s": round(wall_time, 1),
        },
        "models": [
            {
                "name": model.name,
                "id": model.id,
                "effort_level": model.effort_level or "default",
            }
            for model in models
        ],
        "runs": all_results,
    }

    output_file = output_dir / "benchmark_results.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults written to: {output_file}")


def print_run_result(r):
    """Print rich diagnostic output for a single run."""
    checks = r.get("checks", {})
    mr = "PASS" if checks.get("mode_ref") else "FAIL"
    ds = "PASS" if checks.get("ds_skill") else "FAIL"
    sr = "PASS" if checks.get("stat_ref") else "FAIL"

    print(f"\n--- {r['model']} rep {r['rep']} ---")
    print(f"  Checks: mode_ref={mr} | ds_skill={ds} | stat_ref={sr}")
    print(f"  Turns: {r['turns']} | Cost: ${r['cost_usd']:.3f} | Duration: {r['duration_s']}s")

    if r.get("error"):
        print(f"  ERROR: {r['error']}")

    refs = r.get("references_loaded", [])
    if refs:
        ref_strs = [f"{'[S]' if ref['type']=='skill' else '[R]'} {ref.get('name') or ref.get('path')}" for ref in refs]
        print(f"  References ({len(refs)}): {' → '.join(ref_strs)}")
    else:
        print(f"  References: (none)")

    failed = r.get("failed_reads", [])
    if failed:
        for fr in failed:
            print(f"  FAILED READ: {fr['path']}")

    previews = r.get("assistant_previews", [])
    if previews:
        first = previews[0][:150].replace("\n", " ")
        print(f"  Response preview: {first}...")


if __name__ == "__main__":
    main()
