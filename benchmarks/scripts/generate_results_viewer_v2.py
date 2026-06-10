#!/usr/bin/env python3
"""
Generate a self-contained HTML viewer for DAAF benchmark results (v2).

Reads benchmark result sets from benchmarks/results/, loads case definitions
and per-set manifests, condenses transcripts, computes derived metrics
(per-model per-phase aggregates, composite scores, tier bands, consistency,
per-case difficulty, callouts, cost summaries, provenance), and produces a
single HTML file with all data embedded.

The HTML/CSS/JS lives in the sibling template file viewer_template.html;
this script is data preparation + placeholder substitution. v1
(generate_results_viewer.py) is preserved untouched as a historical artifact.

Usage:
    python3 benchmarks/scripts/generate_results_viewer_v2.py [--results TIMESTAMP...] [--exclude-results TIMESTAMP...] [--output PATH]

Examples:
    # Generate viewer for all result sets
    python3 benchmarks/scripts/generate_results_viewer_v2.py

    # Generate for specific result sets
    python3 benchmarks/scripts/generate_results_viewer_v2.py --results 20260608_181352 20260608_181751

    # Custom output path
    python3 benchmarks/scripts/generate_results_viewer_v2.py --output benchmarks/my_viewer.html
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import yaml


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate DAAF benchmark results HTML viewer"
    )
    parser.add_argument(
        "--results",
        nargs="*",
        default=None,
        help="Timestamps of result sets to include (default: all in results/)",
    )
    parser.add_argument(
        "--exclude-results",
        nargs="*",
        default=None,
        help="Timestamps of result sets to skip at load time (complement to "
             "--results; applied after inclusion filtering). Exclusions are "
             "recorded in the embedded generation_params for provenance.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output HTML file path (default: auto-named dated file in "
             "benchmarks/, e.g. viewer_YYYY-MM-DDa.html, with the letter "
             "suffix auto-incrementing to avoid overwriting earlier "
             "same-day outputs)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def resolve_paths(args):
    """Return (base_dir, results_dir, datasets_dir, output_path)."""
    # The script lives at benchmarks/scripts/generate_results_viewer_v2.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)  # benchmarks/
    results_dir = os.path.join(base_dir, "results")
    datasets_dir = os.path.join(base_dir, "datasets")

    if args.output:
        output_path = args.output
    else:
        # Auto-generate dated filename with incrementing suffix
        date_str = datetime.now().strftime("%Y-%m-%d")
        suffix = 'a'
        while os.path.exists(os.path.join(base_dir, f"viewer_{date_str}{suffix}.html")):
            suffix = chr(ord(suffix) + 1)
        output_path = os.path.join(base_dir, f"viewer_{date_str}{suffix}.html")

    return base_dir, results_dir, datasets_dir, output_path


# ---------------------------------------------------------------------------
# Phase detection
#
# Adding a new benchmark phase (developer guide):
#   1. Marker: add ONE criterion name unique to the new phase to PHASE_MAP,
#      mapped to (phase_id, label). Markers are matched by exact name against
#      the set of criterion names found in a result set's summary.json (see
#      detect_phase); pick a criterion that appears in every run of the new
#      phase and in no other phase.
#   2. Ordering + label: add the phase_id to PHASE_ORDER (result-set /
#      provenance sort) and to EVAL_GROUP_ORDER (eval-group display order).
#      The label set here flows automatically to the eval group, deep-dive
#      heatmap, per-group callouts, run explorer, and provenance.
#   3. Composite membership: DECIDE whether the new phase joins COMPOSITE_GIDS
#      (defined next to EVAL_GROUP_ORDER). The leaderboard composite is pinned
#      to the four approved components (P1, P2, P3a, P3b — plan § 11.1);
#      adding a component changes leaderboard/tier semantics and requires
#      updating the About-layer scoring prose in viewer_template.html and
#      README.md § 6. By default a new phase stays OUT of the composite.
#   4. Template prose + JS registries: the About layer's "The benchmark
#      phases" collapsible in viewer_template.html enumerates phases in
#      hand-written prose — add an entry for the new phase. ALSO register the
#      phase in the template's JS lookup maps: GROUP_SHORT (~L890, short
#      labels) and PD_EXPLAINERS (~L1555, deep-dive explainer prose).
#      Omitting these caused the missing Phase 4 (skill_routing) explainer.
#      (Template edits, not handled in this script.)
#   5. Dataset dir: name datasets/<phase_id>/ to match the phase_id so
#      load_cases() attaches case definitions (it falls back to the dirname).
#   6. Regenerate and spot-check the new eval group's k/n in the sanity
#      report and the deep-dive heatmap before publishing.
# ---------------------------------------------------------------------------

PHASE_MAP = {
    "orchestrator_skill_loaded": ("mode_classification", "Phase 1 \u2014 Mode Classification"),
    "read_data_onboarding_mode": ("post_confirmation", "Phase 2 \u2014 Post-Confirmation"),
    "agent_dispatched": ("dispatch_compliance", "Phase 3 \u2014 Dispatch Compliance"),
    "required_skills_loaded": ("skill_routing", "Phase 4 \u2014 Skill Routing"),
}


def detect_phase(summary):
    """Detect benchmark phase from criterion names in summary.json."""
    # Collect all criterion names from by_model
    criterion_names = set()
    for model_data in summary.get("by_model", {}).values():
        criterion_names.update(model_data.get("criteria", {}).keys())

    # Remove synthetic "all_criteria" before matching
    criterion_names.discard("all_criteria")

    for marker, (phase_id, phase_label) in PHASE_MAP.items():
        if marker in criterion_names:
            return phase_id, phase_label

    # Fallback: Phase 2 criteria all start with "read_" or "skill_"
    if any(c.startswith("read_") or c.startswith("skill_") for c in criterion_names):
        return "post_confirmation", "Phase 2 \u2014 Post-Confirmation"

    return "unknown", "Unknown Phase"


# ---------------------------------------------------------------------------
# Criteria normalization
# ---------------------------------------------------------------------------

def normalize_criteria(criteria_raw):
    """Normalize criteria from array format to dict keyed by name.

    Phase 1 result.json stores criteria as a dict (already correct).
    Phase 2 and Phase 3 result.json store criteria as an array of objects.
    """
    if isinstance(criteria_raw, dict):
        return criteria_raw
    if isinstance(criteria_raw, list):
        result = {}
        for entry in criteria_raw:
            name = entry.get("name", "unknown")
            result[name] = entry
        return result
    return {}


# ---------------------------------------------------------------------------
# Result set loading
# ---------------------------------------------------------------------------

def load_result_sets(results_dir, filter_timestamps=None, exclude_timestamps=None):
    """Discover and load all result set directories."""
    result_sets = []

    if not os.path.isdir(results_dir):
        print(f"ERROR: Results directory not found: {results_dir}", file=sys.stderr)
        return result_sets

    # Discover result set directories
    all_timestamps = sorted([
        d for d in os.listdir(results_dir)
        if os.path.isdir(os.path.join(results_dir, d))
        and not d.startswith(".")
    ])

    if filter_timestamps:
        timestamps = [t for t in all_timestamps if t in filter_timestamps]
        missing = set(filter_timestamps) - set(timestamps)
        if missing:
            print(f"WARNING: Result sets not found: {missing}", file=sys.stderr)
    else:
        timestamps = all_timestamps

    # Exclusion filter (--exclude-results): applied after inclusion so the
    # two flags compose predictably. Useful for dropping known-contaminated
    # sets without enumerating every other set via --results.
    if exclude_timestamps:
        exclude_set = set(exclude_timestamps)
        not_on_disk = exclude_set - set(all_timestamps)
        if not_on_disk:
            print(f"WARNING: --exclude-results sets not found: {sorted(not_on_disk)}",
                  file=sys.stderr)
        excluded_here = [t for t in timestamps if t in exclude_set]
        if excluded_here:
            print(f"Excluding result sets: {', '.join(excluded_here)}")
        timestamps = [t for t in timestamps if t not in exclude_set]

    for ts in timestamps:
        ts_dir = os.path.join(results_dir, ts)
        summary_path = os.path.join(ts_dir, "summary.json")

        if not os.path.isfile(summary_path):
            print(f"WARNING: No summary.json in {ts_dir}, skipping", file=sys.stderr)
            continue

        with open(summary_path, "r") as f:
            summary = json.load(f)

        phase_id, phase_label = detect_phase(summary)

        # Load manifest.json (run provenance: git SHA + run configuration).
        # Handled gracefully: a missing or unreadable manifest yields None
        # fields rather than a failure, since older/partial result sets may
        # lack one.
        daaf_git_sha = None
        manifest_config = None
        manifest_path = os.path.join(ts_dir, "manifest.json")
        if os.path.isfile(manifest_path):
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
                sha = manifest.get("daaf_git_sha")
                # Short SHA (12 chars) is unambiguous at this repo's scale
                daaf_git_sha = sha[:12] if sha else None
                cfg = manifest.get("config", {})
                manifest_config = {
                    "reps": cfg.get("reps"),
                    "parallel": cfg.get("parallel"),
                    "launch_delay_s": cfg.get("launch_delay_s"),
                    "timeout_override": cfg.get("timeout_override"),
                    "test_ids": cfg.get("test_ids"),
                    "model_keys": cfg.get("model_keys"),
                }
            except (json.JSONDecodeError, OSError) as exc:
                print(f"WARNING: Could not read manifest in {ts_dir}: {exc}",
                      file=sys.stderr)
        else:
            print(f"WARNING: No manifest.json in {ts_dir}", file=sys.stderr)

        # Count run directories actually on disk (those with a result.json).
        # summary.json run counts are known to disagree with on-disk run dirs
        # in some sets; run-level data is ground truth, summary totals are
        # kept only for provenance/discrepancy disclosure.
        disk_run_count = 0
        runs_dir = os.path.join(ts_dir, "runs")
        if os.path.isdir(runs_dir):
            for run_dirname in os.listdir(runs_dir):
                if os.path.isfile(os.path.join(runs_dir, run_dirname, "result.json")):
                    disk_run_count += 1

        # Extract model names from summary
        models = sorted(summary.get("by_model", {}).keys())

        # Extract criterion names (excluding 'all_criteria' meta-criterion)
        criterion_names = set()
        for model_data in summary.get("by_model", {}).values():
            for cname in model_data.get("criteria", {}).keys():
                if cname != "all_criteria":
                    criterion_names.add(cname)
        criterion_names = sorted(criterion_names)

        # Extract subagent criterion names if present
        subagent_criterion_names = []
        if "subagent_behavior" in summary:
            subagent_criterion_names = summary["subagent_behavior"].get(
                "criterion_names", []
            )

        result_set = {
            "timestamp": ts,
            "phase": phase_id,
            "phase_label": phase_label,
            "total_runs": summary.get("total_runs", 0),
            "errored_runs": summary.get("errored_runs", 0),
            "total_cost_usd": round(summary.get("total_cost_usd", 0), 3),
            "wall_time_s": round(summary.get("wall_time_s", 0), 1),
            "models": models,
            "criterion_names": criterion_names,
            "subagent_criterion_names": subagent_criterion_names,
            # Provenance (manifest + on-disk ground truth)
            "daaf_git_sha": daaf_git_sha,
            "config": manifest_config,
            "disk_run_count": disk_run_count,
            "summary_total_runs": summary.get("total_runs", 0),
        }
        result_sets.append(result_set)

    return result_sets


# ---------------------------------------------------------------------------
# Case definitions loading
# ---------------------------------------------------------------------------

def load_cases(datasets_dir):
    """Load case definitions from all datasets/*/cases.jsonl files."""
    cases = {}

    if not os.path.isdir(datasets_dir):
        print(f"WARNING: Datasets directory not found: {datasets_dir}", file=sys.stderr)
        return cases

    for dirname in sorted(os.listdir(datasets_dir)):
        cases_path = os.path.join(datasets_dir, dirname, "cases.jsonl")
        if not os.path.isfile(cases_path):
            continue

        # Dataset directory names ARE the phase IDs (see developer guide
        # step 5 above) — no mapping table needed.
        phase = dirname

        with open(cases_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                case = json.loads(line)
                case_id = case.get("id", "unknown")
                case["phase"] = phase
                cases[case_id] = case

    return cases


# ---------------------------------------------------------------------------
# Run loading
# ---------------------------------------------------------------------------

def _classify_tier(crit_name, crit_entry, case):
    """Classify a criterion as 'hard' or 'soft'.

    - If the criterion entry already has a 'tier' field (Phase 2/3), map it:
        tier1 -> hard, tier2 -> soft, info -> None (skip)
    - Otherwise (Phase 1), look up the case's hard_requirements list.
        Present in hard_requirements -> hard, otherwise -> soft.
        If no hard_requirements list exists, default to hard.
    """
    raw_tier = crit_entry.get("tier") if isinstance(crit_entry, dict) else None
    if raw_tier is not None:
        tier_map = {"tier1": "hard", "tier2": "soft", "info": None}
        return tier_map.get(raw_tier, "hard")

    # No explicit tier — use the case's hard_requirements list
    if case is None:
        return "hard"
    hard_reqs = case.get("hard_requirements", None)
    if hard_reqs is None:
        return "hard"
    return "hard" if crit_name in hard_reqs else "soft"


def _enrich_criteria_with_tiers(criteria, case):
    """Add a 'tier' field to each criterion entry in-place."""
    for crit_name, entry in criteria.items():
        if not isinstance(entry, dict):
            entry = {"passed": bool(entry)}
            criteria[crit_name] = entry
        tier = _classify_tier(crit_name, entry, case)
        if tier is None:
            # 'info' tier — keep but mark as info so JS can ignore
            entry["tier"] = "info"
        else:
            entry["tier"] = tier


def compute_grade(criteria):
    """Compute the grade status of a criteria dict.

    Status taxonomy (orthogonal to the timed_out flag — timed-out runs are
    often fully graded and must never be treated as ungraded):
      perfect  — all criteria passed
      partial  — some, but not all, criteria passed
      failed   — no criteria passed
      ungraded — no criteria present

    All criterion entries are counted (matching the Perfect-rate semantics of
    the v1 viewer's allCriteriaPassed/runStatus); no info-tier criteria exist
    in the current corpus.
    """
    if not criteria:
        return "ungraded"
    total = len(criteria)
    passed = sum(
        1 for entry in criteria.values()
        if isinstance(entry, dict) and entry.get("passed")
    )
    if passed == total:
        return "perfect"
    if passed == 0:
        return "failed"
    return "partial"


def load_runs(results_dir, result_sets, cases):
    """Load all result.json files for each result set."""
    runs = []

    for rs in result_sets:
        ts = rs["timestamp"]
        runs_dir = os.path.join(results_dir, ts, "runs")

        if not os.path.isdir(runs_dir):
            print(f"WARNING: No runs directory in {ts}", file=sys.stderr)
            continue

        for run_dirname in sorted(os.listdir(runs_dir)):
            result_path = os.path.join(runs_dir, run_dirname, "result.json")
            if not os.path.isfile(result_path):
                continue

            with open(result_path, "r") as f:
                result = json.load(f)

            case_id = result.get("case_id", "")
            case = cases.get(case_id)

            # Normalize criteria
            criteria = normalize_criteria(result.get("criteria", {}))
            _enrich_criteria_with_tiers(criteria, case)

            # Normalize subagent_criteria (Phase 3 only)
            subagent_criteria = None
            if "subagent_criteria" in result and result["subagent_criteria"]:
                subagent_criteria = normalize_criteria(result["subagent_criteria"])
                # Subagent criteria default to soft unless explicit tier
                for sc_name, sc_entry in subagent_criteria.items():
                    if not isinstance(sc_entry, dict):
                        sc_entry = {"passed": bool(sc_entry)}
                        subagent_criteria[sc_name] = sc_entry
                    raw_tier = sc_entry.get("tier")
                    if raw_tier:
                        tier_map = {"tier1": "hard", "tier2": "soft", "info": "info"}
                        sc_entry["tier"] = tier_map.get(raw_tier, "soft")
                    else:
                        sc_entry["tier"] = "soft"

            run = {
                "result_set": ts,
                "case_id": case_id,
                "model": result.get("model", ""),
                "model_id": result.get("model_id", ""),
                "provider": result.get("provider", ""),
                "rep": result.get("rep", 0),
                "session_id": result.get("session_id", ""),
                "turns": result.get("turns", 0),
                "computed_cost_usd": result.get("computed_cost_usd", 0),
                # Defensive read: this field is absent from all current
                # result.json files; the 1.0 default is kept deliberately so
                # the reasoning-multiplier badge logic keeps working if the
                # harness ever emits it again.
                "reasoning_cost_multiplier": result.get("reasoning_cost_multiplier", 1.0),
                "input_tokens": result.get("input_tokens", 0),
                "output_tokens": result.get("output_tokens", 0),
                "cache_read_tokens": result.get("cache_read_tokens", 0),
                "cache_creation_tokens": result.get("cache_creation_tokens", 0),
                "duration_s": result.get("duration_s", 0),
                "error": result.get("error", None),
                # Explicit flag from the harness — never string-match `error`
                # to detect timeouts. Timed-out runs are usually still graded.
                "timed_out": bool(result.get("timed_out", False)),
                # Phase 1 only (None elsewhere)
                "expected_mode": result.get("expected_mode"),
                # Phase 2/3 only (None elsewhere)
                "subcategory": result.get("subcategory"),
                # Phase 2/3 only (None on Phase 1 result.json)
                "tool_call_count": result.get("tool_call_count"),
                # Grade status computed from main criteria; orthogonal to
                # timed_out (see compute_grade)
                "grade": compute_grade(criteria),
                "criteria": criteria,
                "subagent_criteria": subagent_criteria,
                # Carried through in full, including each entry's `content`
                # string — surfaced in the run detail view
                "tool_failures": result.get("tool_failures", []),
                "run_dir": run_dirname,
            }
            runs.append(run)

    return runs


# ---------------------------------------------------------------------------
# Transcript condensation
# ---------------------------------------------------------------------------

def _strip_nonprintable(text):
    """Remove non-printable characters that break HTML/JS embedding.

    Transcript content can contain raw binary data (e.g., corrupted tool output)
    with control characters (U+007F-U+009F, U+0000-U+0008, etc.) that json.dumps
    does not escape. These literal bytes in <script> blocks break browser parsing.
    """
    return "".join(ch for ch in text if ch >= " " or ch in "\n\r\t")


def _truncate_content(text, max_chars=2000):
    """Truncate content to max_chars, adding a truncation marker if needed."""
    text = _strip_nonprintable(text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [truncated, {len(text):,} chars total]"


def _is_system_injected(text):
    """Detect system-injected content (skill loads, system reminders).

    These appear as user text blocks but are actually framework content
    injected by the harness. They are huge (40KB+) and not diagnostic.
    """
    prefixes = (
        "Base directory for this skill:",
        "<system-reminder>",
        "Contents of /",
    )
    for prefix in prefixes:
        if text.strip().startswith(prefix):
            return True
    return False


def condense_transcript(jsonl_path):
    """Parse a transcript.jsonl and extract a condensed conversation view.

    Returns a list of message dicts with roles:
      user, assistant, tool_call, tool_result

    Content is truncated to keep condensed transcripts under ~10KB each:
      - User/assistant text: max 2000 chars
      - System-injected content (skills, reminders): max 200 chars
      - Tool call args: max 200 chars
      - Tool result output: max 500 chars
    """
    messages = []

    if not os.path.isfile(jsonl_path):
        return messages

    with open(jsonl_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            entry_type = entry.get("type", "")

            # Skip non-conversation entries
            if entry_type in ("queue-operation", "attachment", "last-prompt",
                              "deferred_tools_delta", "skill_listing"):
                continue

            if entry_type == "user":
                msg = entry.get("message", {})
                content = msg.get("content", "")

                if isinstance(content, str):
                    # Simple text user message
                    text = content.strip()
                    if text:
                        if _is_system_injected(text):
                            messages.append({
                                "role": "system",
                                "content": _truncate_content(text, 200),
                            })
                        else:
                            messages.append({
                                "role": "user",
                                "content": _truncate_content(text),
                            })
                elif isinstance(content, list):
                    # Content blocks — may contain tool_result blocks
                    for block in content:
                        block_type = block.get("type", "")
                        if block_type == "tool_result":
                            tool_use_id = block.get("tool_use_id", "")
                            block_content = block.get("content", "")
                            # Determine status from is_error field or content
                            is_error = block.get("is_error", False)
                            status = "error" if is_error else "success"
                            output = _strip_nonprintable(str(block_content)[:500]) if block_content else ""
                            # Try to find the tool name from a previous tool_call
                            tool_name = _find_tool_name(messages, tool_use_id)
                            messages.append({
                                "role": "tool_result",
                                "tool": tool_name or tool_use_id[:20],
                                "status": status,
                                "output": output,
                            })
                        elif block_type == "text":
                            text = block.get("text", "").strip()
                            if text:
                                if _is_system_injected(text):
                                    messages.append({
                                        "role": "system",
                                        "content": _truncate_content(text, 200),
                                    })
                                else:
                                    messages.append({
                                        "role": "user",
                                        "content": _truncate_content(text),
                                    })

            elif entry_type == "assistant":
                msg = entry.get("message", {})
                content = msg.get("content", [])

                if isinstance(content, list):
                    text_parts = []
                    for block in content:
                        block_type = block.get("type", "")
                        if block_type == "text":
                            text_parts.append(block.get("text", ""))
                        elif block_type == "tool_use":
                            # Emit any accumulated text first
                            if text_parts:
                                combined = "\n".join(text_parts).strip()
                                if combined:
                                    messages.append({
                                        "role": "assistant",
                                        "content": _truncate_content(combined),
                                    })
                                text_parts = []
                            # Emit tool call
                            tool_name = block.get("name", "unknown")
                            tool_id = block.get("id", "")
                            tool_input = block.get("input", {})
                            args_str = json.dumps(tool_input) if tool_input else ""
                            messages.append({
                                "role": "tool_call",
                                "tool": tool_name,
                                "tool_id": tool_id,
                                "args": _strip_nonprintable(args_str[:200]),
                            })
                        # Skip thinking, redacted_thinking blocks

                    # Emit remaining text
                    if text_parts:
                        combined = "\n".join(text_parts).strip()
                        if combined:
                            messages.append({
                                "role": "assistant",
                                "content": _truncate_content(combined),
                            })

                elif isinstance(content, str):
                    text = content.strip()
                    if text:
                        messages.append({
                            "role": "assistant",
                            "content": _truncate_content(text),
                        })

    return messages


def _find_tool_name(messages, tool_use_id):
    """Look backwards through messages for a tool_call with matching tool_id."""
    if not tool_use_id:
        return None
    for msg in reversed(messages):
        if msg.get("role") == "tool_call" and msg.get("tool_id") == tool_use_id:
            return msg.get("tool")
    return None


def load_transcripts(results_dir, runs):
    """Condense transcripts for all runs.

    Returns:
        transcripts: dict keyed by run_dir -> condensed message list
        subagent_transcripts: dict keyed by run_dir -> dict of agent_id -> messages
    """
    transcripts = {}
    subagent_transcripts = {}

    for run in runs:
        ts = run["result_set"]
        run_dir = run["run_dir"]
        run_path = os.path.join(results_dir, ts, "runs", run_dir)

        # Main transcript
        transcript_path = os.path.join(run_path, "transcript.jsonl")
        condensed = condense_transcript(transcript_path)
        if condensed:
            transcripts[run_dir] = condensed

        # Subagent transcripts (Phase 3)
        # Cap string values at 200 chars — subagent transcripts can contain
        # corrupted binary data (e.g., garbled tool output from failed runs)
        # that breaks HTML/JS embedding regardless of escaping
        subagent_dir = os.path.join(run_path, "subagents")
        if os.path.isdir(subagent_dir):
            agent_transcripts = {}
            for fname in sorted(os.listdir(subagent_dir)):
                if fname.endswith(".jsonl"):
                    agent_id = fname.replace(".jsonl", "")
                    agent_path = os.path.join(subagent_dir, fname)
                    agent_condensed = condense_transcript(agent_path)
                    if agent_condensed:
                        agent_transcripts[agent_id] = agent_condensed

            if agent_transcripts:
                subagent_transcripts[run_dir] = agent_transcripts

    return transcripts, subagent_transcripts


# ---------------------------------------------------------------------------
# Model pricing loading
# ---------------------------------------------------------------------------

def load_model_pricing(base_dir):
    """Load per-token pricing from config/models.yaml.

    Returns a dict keyed by model name (matching run.model) with per-million
    token rates for input, output, and cached_input.
    """
    config_path = os.path.join(base_dir, "config", "models.yaml")
    if not os.path.isfile(config_path):
        print(f"WARNING: models.yaml not found at {config_path}", file=sys.stderr)
        return {}

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    pricing = {}
    for entry in config.get("models", []):
        name = entry.get("name")
        if not name:
            continue
        p = entry.get("pricing", {})
        if not p:
            continue
        pricing[name] = {
            "input_per_million": round(p.get("input", 0), 4),
            "output_per_million": round(p.get("output", 0), 4),
            "cached_input_per_million": round(p.get("cached_input", 0), 4),
        }
    return pricing


# ---------------------------------------------------------------------------
# Data bundle assembly
# ---------------------------------------------------------------------------

PHASE_ORDER = {"mode_classification": 1, "post_confirmation": 2,
               "dispatch_compliance": 3, "skill_routing": 4}


def build_data_bundle(result_sets, cases, runs, transcripts, subagent_transcripts,
                      model_pricing=None):
    """Assemble the complete data bundle for embedding in HTML."""
    # Sort result_sets by phase order so they always appear Phase 1, 2, 3, 4
    sorted_result_sets = sorted(
        result_sets, key=lambda rs: PHASE_ORDER.get(rs["phase"], 99)
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator_version": "2.1.0",
        "result_sets": sorted_result_sets,
        "cases": cases,
        "runs": runs,
        "transcripts": transcripts,
        "subagent_transcripts": subagent_transcripts,
        "model_pricing": model_pricing or {},
    }


# ---------------------------------------------------------------------------
# Precomputed metrics
#
# All aggregates below are derived from loaded run-level data (run dirs are
# ground truth; summary.json totals are used only for provenance disclosure).
# Headline numbers are computed here in Python and embedded as PRECOMPUTED so
# that prose, charts, and tables in the viewer cannot drift apart; the JS
# still computes section-local filtered views from the runs array.
# ---------------------------------------------------------------------------

# Canonical eval-group order: P1, P2, P3a (dispatch), P3b (subagent), P4
EVAL_GROUP_ORDER = [
    "mode_classification",
    "post_confirmation",
    "dispatch_compliance_dispatch",
    "dispatch_compliance_subagent",
    "skill_routing",
]

# Composite scoring is PINNED to the four approved components (P1, P2, P3a,
# P3b — unweighted mean of Perfect rates; plan § 11.1, resolved decision 1).
# Other phases (e.g., skill_routing) get their own labeled eval group,
# per_model_phase cells, and per-group callouts, but never enter the
# composite, tiers, or the global weakest-criterion callout unless they are
# deliberately added here (see "Adding a new benchmark phase" above PHASE_MAP
# — joining the composite changes leaderboard semantics and requires prose
# updates in viewer_template.html and README.md § 6).
COMPOSITE_GIDS = [
    "mode_classification",
    "post_confirmation",
    "dispatch_compliance_dispatch",
    "dispatch_compliance_subagent",
]

# Tier banding rule (mechanical and reproducible by design — see
# VIEWER_REDESIGN_PLAN.md § 11 decision 2). Two deterministic stages:
#
#   Primary (gap rule): walking the composite ranking in descending order, a
#   new tier starts wherever the gap to the previous model's composite is
#   >= TIER_GAP_THRESHOLD (5 percentage points).
#
#   Fallback (range quartiles): if the gap rule yields fewer than
#   TIER_MIN_TIERS tiers across a corpus of >= TIER_FALLBACK_MIN_MODELS
#   models — which happens on the real corpus, where the largest observed
#   composite gap is ~6.8 points at the original 8-point threshold and the
#   scores form a near-continuum — models are instead banded by which
#   quarter of the composite range [min, max] their score falls in
#   (equal-width bands; empty bands are skipped so tier labels stay
#   contiguous T1, T2, ...).
#
# The applied method is recorded in PRECOMPUTED["tier_rule"] so the viewer's
# leaderboard prose can disclose which rule produced the bands on this corpus.
TIER_GAP_THRESHOLD = 0.05
TIER_MIN_TIERS = 3
TIER_FALLBACK_MIN_MODELS = 12


def build_eval_groups(result_sets):
    """Build eval groups, mirroring the viewer JS buildEvalGroups() split.

    Phase 1 and Phase 2 are single groups. Phase 3 result sets that carry
    subagent criterion names contribute their runs to BOTH a dispatch group
    (3a — scored on run['criteria']) and a subagent group (3b — scored on
    run['subagent_criteria']). The eval-group semantics here must stay in
    lockstep with the template JS so precomputed and JS-derived numbers agree.
    """
    gmap = {}
    for rs in result_sets:
        if rs["phase"] == "dispatch_compliance" and rs.get("subagent_criterion_names"):
            gid = "dispatch_compliance_dispatch"
            if gid not in gmap:
                gmap[gid] = {
                    "id": gid, "phase": rs["phase"],
                    "label": "Phase 3a \u2014 Dispatch Compliance",
                    "timestamps": [], "is_subagent": False,
                    "criterion_names": list(rs["criterion_names"]),
                }
            gmap[gid]["timestamps"].append(rs["timestamp"])
            gid = "dispatch_compliance_subagent"
            if gid not in gmap:
                gmap[gid] = {
                    "id": gid, "phase": rs["phase"],
                    "label": "Phase 3b \u2014 Subagent Behavior",
                    "timestamps": [], "is_subagent": True,
                    "criterion_names": list(rs["subagent_criterion_names"]),
                }
            gmap[gid]["timestamps"].append(rs["timestamp"])
        else:
            gid = rs["phase"]
            if gid not in gmap:
                gmap[gid] = {
                    "id": gid, "phase": rs["phase"],
                    "label": rs["phase_label"],
                    "timestamps": [], "is_subagent": False,
                    "criterion_names": list(rs["criterion_names"]),
                }
            gmap[gid]["timestamps"].append(rs["timestamp"])

    ordered = [gmap[gid] for gid in EVAL_GROUP_ORDER if gid in gmap]
    ordered += [g for gid, g in gmap.items() if gid not in EVAL_GROUP_ORDER]
    return ordered


def run_group_criteria(run, group):
    """Return the criteria dict a run is scored on within an eval group."""
    if group["is_subagent"]:
        return run.get("subagent_criteria") or {}
    return run.get("criteria") or {}


def build_precomputed(result_sets, cases, runs, generation_params):
    """Compute the derived-metrics bundle embedded as PRECOMPUTED."""
    groups = build_eval_groups(result_sets)
    group_ts = {g["id"]: set(g["timestamps"]) for g in groups}
    models = sorted({r["model"] for r in runs})
    phase_lookup = {rs["timestamp"]: rs["phase"] for rs in result_sets}

    def rnd(x, digits=4):
        return None if x is None else round(x, digits)

    # --- per_model_phase: model x eval group aggregates ---
    per_model_phase = {}
    for model in models:
        per_model_phase[model] = {}
        for g in groups:
            gid = g["id"]
            gruns = [r for r in runs
                     if r["model"] == model and r["result_set"] in group_ts[gid]]
            if not gruns:
                continue
            n_runs = len(gruns)
            n_graded = 0
            perfect_count = 0
            hard_passed = hard_total = soft_passed = soft_total = 0
            dispatch_passed = dispatch_total = 0
            for r in gruns:
                crit = run_group_criteria(r, g)
                if crit:
                    n_graded += 1
                # Perfect requires at least one criterion present and all
                # passed — mirrors the JS groupAllPassed(): runs with no
                # criteria in this group count toward n_runs but can never
                # be perfect (matters for 3b, where some Phase 3 runs have
                # no subagent criteria)
                if compute_grade(crit) == "perfect":
                    perfect_count += 1
                for name, entry in crit.items():
                    if not isinstance(entry, dict):
                        continue
                    tier = entry.get("tier")
                    if tier == "hard":
                        hard_total += 1
                        if entry.get("passed"):
                            hard_passed += 1
                    elif tier == "soft":
                        soft_total += 1
                        if entry.get("passed"):
                            soft_passed += 1
                    if gid == "dispatch_compliance_dispatch" and name == "agent_dispatched":
                        dispatch_total += 1
                        if entry.get("passed"):
                            dispatch_passed += 1
            cell = {
                "n_runs": n_runs,
                "n_graded": n_graded,
                "perfect_count": perfect_count,
                "perfect_rate": rnd(perfect_count / n_runs),
                "hard_passed": hard_passed,
                "hard_total": hard_total,
                "soft_passed": soft_passed,
                "soft_total": soft_total,
            }
            if gid == "dispatch_compliance_dispatch":
                cell["dispatch_passed"] = dispatch_passed
                cell["dispatch_total"] = dispatch_total
                cell["dispatch_rate"] = rnd(
                    dispatch_passed / dispatch_total) if dispatch_total else None
            per_model_phase[model][gid] = cell

    # --- composite: unweighted mean of available per-group perfect rates ---
    # P1, P2, P3a, P3b are four equal components (resolved decision 1) —
    # pinned via COMPOSITE_GIDS so non-composite eval groups (e.g.,
    # skill_routing) never enter scores, components, or partial-data flags.
    # Models missing a component get the mean over available components and a
    # partial_data flag, relative to the composite components present in this
    # corpus (components_missing likewise refers only to composite gids).
    corpus_components = [gid for gid in COMPOSITE_GIDS
                         if any(g["id"] == gid for g in groups)]
    composite = {}
    for model in models:
        comps = {}
        n_total = 0
        for gid in corpus_components:
            cell = per_model_phase.get(model, {}).get(gid)
            if cell is None:
                continue
            comps[gid] = cell["perfect_rate"]
            n_total += cell["n_runs"]
        if not comps:
            continue
        score = sum(comps.values()) / len(comps)
        composite[model] = {
            "score": rnd(score),
            "components": comps,
            "components_present": list(comps.keys()),
            "components_missing": [gid for gid in corpus_components
                                   if gid not in comps],
            "n_total": n_total,
            "partial_data": len(comps) < len(corpus_components),
        }

    # --- tiers: mechanical banding on composite (gap rule + quartile fallback) ---
    # Stage 1 (gap rule): sort by composite descending; start a new tier where
    # the gap to the previous model's composite is >= TIER_GAP_THRESHOLD.
    ranked = sorted(composite.items(), key=lambda kv: (-kv[1]["score"], kv[0]))
    tiers = []
    prev_score = None
    for model, entry in ranked:
        if prev_score is None or (prev_score - entry["score"]) >= TIER_GAP_THRESHOLD:
            tiers.append({"label": "T" + str(len(tiers) + 1), "models": []})
        tiers[-1]["models"].append(model)
        entry["tier"] = tiers[-1]["label"]
        prev_score = entry["score"]
    tier_rule = {"method": "gap", "gap_threshold": TIER_GAP_THRESHOLD}
    # Stage 2 (fallback): on a large corpus whose composites form a
    # near-continuum, the gap rule degenerates to a single band. If it
    # produced fewer than TIER_MIN_TIERS tiers across >=
    # TIER_FALLBACK_MIN_MODELS models, band instead by which quarter of the
    # composite range [min, max] each score falls in. Walking the descending
    # ranking, band indices are non-decreasing, so a band change starts a new
    # tier; empty bands are skipped and labels stay contiguous.
    if len(ranked) >= TIER_FALLBACK_MIN_MODELS and len(tiers) < TIER_MIN_TIERS:
        hi = ranked[0][1]["score"]
        lo = ranked[-1][1]["score"]
        span = hi - lo
        if span > 0:
            tiers = []
            prev_band = None
            for model, entry in ranked:
                # band 0 = top quarter of the range ... band 3 = bottom quarter
                band = min(3, int((hi - entry["score"]) / span * 4))
                if prev_band is None or band != prev_band:
                    tiers.append({"label": "T" + str(len(tiers) + 1), "models": []})
                    prev_band = band
                tiers[-1]["models"].append(model)
                entry["tier"] = tiers[-1]["label"]
            tier_rule = {"method": "range_quartiles",
                         "gap_threshold": TIER_GAP_THRESHOLD}

    # --- consistency: pass^k over (phase, case) cells with >= 2 reps ---
    # A cell is all-perfect when every rep of that (model, phase, case) has
    # grade == "perfect" (main-criteria grade; raw phase, matching the rep
    # renumbering key in main()).
    # Deliberately spans ALL loaded runs, including non-composite phases —
    # consistency is an all-runs reliability measure, not pinned to COMPOSITE_GIDS.
    consistency = {}
    for model in models:
        cells = {}
        for r in runs:
            if r["model"] != model:
                continue
            key = (phase_lookup.get(r["result_set"], ""), r["case_id"])
            cells.setdefault(key, []).append(r["grade"])
        multi = {k: v for k, v in cells.items() if len(v) >= 2}
        all_perfect = sum(
            1 for grades in multi.values()
            if all(gr == "perfect" for gr in grades)
        )
        consistency[model] = {
            "cells_total": len(multi),
            "cells_all_perfect": all_perfect,
            "rate": rnd(all_perfect / len(multi)) if multi else None,
        }

    # --- per_case: cross-model difficulty ---
    per_case = {}
    case_runs = {}
    for r in runs:
        case_runs.setdefault(r["case_id"], []).append(r)
    for case_id, cruns in sorted(case_runs.items()):
        case = cases.get(case_id, {})
        subcategory = case.get("subcategory")
        if subcategory is None:
            # Fall back to the field carried on Phase 2/3 result.json
            subcategory = next(
                (r["subcategory"] for r in cruns if r.get("subcategory")), None)
        perfect_count = sum(1 for r in cruns if r["grade"] == "perfect")
        per_case[case_id] = {
            "phase": phase_lookup.get(cruns[0]["result_set"], ""),
            "subcategory": subcategory,
            "n_runs": len(cruns),
            "n_models": len({r["model"] for r in cruns}),
            "perfect_count": perfect_count,
            "perfect_rate": rnd(perfect_count / len(cruns)),
        }

    # --- callouts: weakest criterion + top model per eval group ---
    callouts = {"groups": {}, "global_weakest": None}
    global_weakest = None
    for g in groups:
        gid = g["id"]
        gruns = [r for r in runs if r["result_set"] in group_ts[gid]]
        crit_agg = {}
        for r in gruns:
            for name, entry in run_group_criteria(r, g).items():
                if not isinstance(entry, dict):
                    continue
                agg = crit_agg.setdefault(name, {"passed": 0, "total": 0})
                agg["total"] += 1
                if entry.get("passed"):
                    agg["passed"] += 1
        weakest = None
        for name, agg in crit_agg.items():
            rate = agg["passed"] / agg["total"]
            # Deterministic tie-breaks: lowest rate, then largest n, then name
            key = (rate, -agg["total"], name)
            if weakest is None or key < weakest[0]:
                weakest = (key, {
                    "name": name,
                    "passed": agg["passed"],
                    "total": agg["total"],
                    "rate": rnd(rate),
                })
        top_model = None
        for model in models:
            cell = per_model_phase.get(model, {}).get(gid)
            if cell is None:
                continue
            key = (-cell["perfect_rate"], -cell["n_runs"], model)
            if top_model is None or key < top_model[0]:
                top_model = (key, {
                    "model": model,
                    "perfect_rate": cell["perfect_rate"],
                    "n_runs": cell["n_runs"],
                })
        callouts["groups"][gid] = {
            "label": g["label"],
            "weakest_criterion": weakest[1] if weakest else None,
            "top_model": top_model[1] if top_model else None,
        }
        # global_weakest (hero verdict + #phases finding) is restricted to
        # composite groups so a single experimental phase cannot hijack the
        # document's headline finding; callouts["groups"] above still covers
        # every eval group, including non-composite ones.
        if weakest is not None and gid in COMPOSITE_GIDS:
            if global_weakest is None or weakest[0] < global_weakest[0]:
                global_weakest = (weakest[0],
                                  dict(weakest[1], group=gid, group_label=g["label"]))
    if global_weakest is not None:
        callouts["global_weakest"] = global_weakest[1]

    # --- cost: per-model spend/duration, excluding zeroed timeout runs ---
    # Timed-out runs have zeroed cost/tokens, which pollutes averages; they
    # are excluded from avg cost and avg duration (excluded_count disclosed
    # for footnotes). Totals still include them — they contribute zero.
    cost = {"per_model": {}, "total_spend_usd": 0.0}
    total_spend = 0.0
    for model in models:
        mruns = [r for r in runs if r["model"] == model]
        excluded = [r for r in mruns
                    if r["timed_out"] and r["computed_cost_usd"] == 0]
        included = [r for r in mruns
                    if not (r["timed_out"] and r["computed_cost_usd"] == 0)]
        model_total = sum(r["computed_cost_usd"] for r in mruns)
        total_spend += model_total
        cost["per_model"][model] = {
            "n_runs": len(mruns),
            "n_included": len(included),
            "excluded_count": len(excluded),
            "avg_cost_usd": rnd(
                sum(r["computed_cost_usd"] for r in included) / len(included)
            ) if included else None,
            "avg_duration_s": rnd(
                sum(r["duration_s"] for r in included) / len(included), 1
            ) if included else None,
            "total_cost_usd": rnd(model_total, 2),
            "tokens": {
                "input_tokens": sum(r["input_tokens"] for r in mruns),
                "output_tokens": sum(r["output_tokens"] for r in mruns),
                "cache_read_tokens": sum(r["cache_read_tokens"] for r in mruns),
                "cache_creation_tokens": sum(r["cache_creation_tokens"] for r in mruns),
            },
        }
    cost["total_spend_usd"] = rnd(total_spend, 2)

    # --- efficiency frontier: Pareto set on (avg cost asc, composite desc) ---
    # Computed over models that have both an avg cost and a composite score.
    # Walking points sorted by (cost asc, composite desc, name asc) and
    # keeping strict composite improvements yields the frontier staircase
    # deterministically: a model is kept iff no cheaper-or-equal model has an
    # equal-or-higher composite. Precomputed here (not in JS) so the scatter
    # annotation, the leaderboard prose, and the sanity report cannot drift.
    frontier_pts = []
    for model in models:
        cm = cost["per_model"][model]
        comp_entry = composite.get(model)
        if cm["avg_cost_usd"] is None or comp_entry is None:
            continue
        frontier_pts.append((cm["avg_cost_usd"], -comp_entry["score"], model))
    frontier_pts.sort()
    frontier = []
    best_score = None
    for avg_cost, neg_score, model in frontier_pts:
        score = -neg_score
        if best_score is None or score > best_score:
            frontier.append({
                "model": model,
                "avg_cost_usd": avg_cost,
                "composite": score,
            })
            best_score = score
    cost["frontier"] = frontier

    # --- provenance: per result set, manifest + disk-vs-summary disclosure ---
    provenance = []
    for rs in sorted(result_sets,
                     key=lambda x: (PHASE_ORDER.get(x["phase"], 99), x["timestamp"])):
        provenance.append({
            "timestamp": rs["timestamp"],
            "phase": rs["phase"],
            "phase_label": rs["phase_label"],
            "daaf_git_sha": rs.get("daaf_git_sha"),
            "config": rs.get("config"),
            "disk_run_count": rs.get("disk_run_count", 0),
            "summary_total_runs": rs.get("summary_total_runs", 0),
            "run_count_discrepancy":
                rs.get("disk_run_count", 0) != rs.get("summary_total_runs", 0),
        })

    # --- totals ---
    totals = {
        "total_runs": len(runs),
        "n_models": len(models),
        "n_cases": len(case_runs),
        "n_result_sets": len(result_sets),
        "n_timed_out": sum(1 for r in runs if r["timed_out"]),
        "total_spend_usd": rnd(total_spend, 2),
        "generation_params": generation_params,
    }

    return {
        "eval_groups": [
            {k: g[k] for k in ("id", "phase", "label", "timestamps",
                               "is_subagent", "criterion_names")}
            for g in groups
        ],
        "per_model_phase": per_model_phase,
        "composite": composite,
        "tiers": tiers,
        "tier_rule": tier_rule,
        "consistency": consistency,
        "per_case": per_case,
        "callouts": callouts,
        "cost": cost,
        "provenance": provenance,
        "totals": totals,
    }


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def escape_embedded_json(obj):
    """Serialize an object for embedding inside a <script> block.

    The escaping here is byte-identical to v1's logic -- these are hard-won
    safeguards; do not simplify:
    - Escape all '<' to prevent HTML5 parser state transitions inside <script>
      (covers </script> termination, <!-- escape state, <script double-escape)
    - Strip C1 control characters (U+007F-U+009F) that json.dumps does not
      escape; literal C1 bytes in <script> blocks break browser parsing
    """
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    text = text.replace("<", "\\u003c")
    text = "".join(
        ch for ch in text
        if ord(ch) >= 0x20 or ch in "\n\r\t"
        if not (0x7F <= ord(ch) <= 0x9F)
    )
    return text


def generate_html(data_bundle, precomputed):
    """Generate a self-contained HTML file by filling the sibling template.

    The HTML/CSS/JS lives in viewer_template.html next to this script.
    Dynamic content is substituted via str.replace() on unique placeholder
    tokens -- NOT str.format(), because the template is full of literal
    CSS/JS braces that str.format() would misinterpret as fields.

    Substitution order matters: the fully-controlled small placeholders are
    filled first; the data bundle (which embeds arbitrary transcript content
    that could in principle contain placeholder-like text) is substituted
    last, so loaded content can never be treated as a placeholder.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, "viewer_template.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    generated_display = data_bundle["generated_at"][:19].replace("T", " ")
    data_json = escape_embedded_json(data_bundle)
    precomputed_json = escape_embedded_json(precomputed)

    html = html.replace("__GENERATED_DISPLAY__", generated_display)
    html = html.replace("__PRECOMPUTED_JSON__", precomputed_json)
    html = html.replace("__DATA_JSON__", data_json)

    return html


# ---------------------------------------------------------------------------
# Print summary
# ---------------------------------------------------------------------------

def print_summary(data_bundle):
    """Print a summary of what was loaded."""
    print("\n=== DAAF Benchmark Results Viewer Generator ===\n")

    for rs in data_bundle["result_sets"]:
        err_pct = (
            f" ({rs['errored_runs']/rs['total_runs']*100:.0f}%)"
            if rs["total_runs"] > 0
            else ""
        )
        print(f"  {rs['phase_label']}")
        print(f"    Timestamp:  {rs['timestamp']}")
        print(f"    Runs:       {rs['total_runs']} ({rs['errored_runs']} errored{err_pct})")
        print(f"    Models:     {', '.join(rs['models'])}")
        print(f"    Cost:       ${rs['total_cost_usd']:.2f}")
        print(f"    Criteria:   {len(rs['criterion_names'])} dispatch + "
              f"{len(rs.get('subagent_criterion_names', []))} subagent")
        print()

    total_runs = len(data_bundle["runs"])
    total_transcripts = len(data_bundle["transcripts"])
    total_subagent = sum(len(v) for v in data_bundle["subagent_transcripts"].values())
    total_cases = len(data_bundle["cases"])
    total_cost = sum(rs["total_cost_usd"] for rs in data_bundle["result_sets"])

    print(f"  Totals:")
    print(f"    Result sets:           {len(data_bundle['result_sets'])}")
    print(f"    Runs loaded:           {total_runs}")
    print(f"    Cases loaded:          {total_cases}")
    print(f"    Transcripts condensed: {total_transcripts}")
    print(f"    Subagent transcripts:  {total_subagent}")
    print(f"    Total cost:            ${total_cost:.2f}")
    print()


def print_precomputed_report(precomputed):
    """Print a sanity report of the precomputed metrics bundle."""
    print("=== Precomputed Metrics Sanity Report ===\n")

    print("  Runs per eval group:")
    pmp = precomputed["per_model_phase"]
    for g in precomputed["eval_groups"]:
        gid = g["id"]
        n = sum(cells[gid]["n_runs"] for cells in pmp.values() if gid in cells)
        perfect = sum(cells[gid]["perfect_count"]
                      for cells in pmp.values() if gid in cells)
        print(f"    {g['label']}: {n} runs, {perfect} perfect")
    print()

    rule = precomputed.get("tier_rule", {})
    print(f"  Tier rule applied: {rule.get('method', '?')} "
          f"(gap threshold {rule.get('gap_threshold', '?')}) -> "
          f"{len(precomputed['tiers'])} tiers")
    print("  Composite leaderboard (tier | model | composite | components | n):")
    comp = precomputed["composite"]
    ranked = sorted(comp.items(), key=lambda kv: (-kv[1]["score"], kv[0]))
    for model, entry in ranked:
        comps = " ".join(
            f"{gid.split('_')[-1][:4]}={entry['components'][gid]:.2f}"
            for gid in entry["components_present"]
        )
        partial = " [partial]" if entry["partial_data"] else ""
        print(f"    {entry['tier']:>3} | {model:<22} | {entry['score']:.3f} | "
              f"{comps} | n={entry['n_total']}{partial}")
    print()

    print("  Efficiency frontier (cost asc | model | avg $/run | composite):")
    for pt in precomputed["cost"].get("frontier", []):
        print(f"    {pt['model']:<22} | ${pt['avg_cost_usd']:.4f} | "
              f"{pt['composite']:.3f}")
    print()

    cost = precomputed["cost"]
    totals = precomputed["totals"]
    n_disc = sum(1 for p in precomputed["provenance"] if p["run_count_discrepancy"])
    gw = precomputed["callouts"]["global_weakest"]
    print(f"  Total runs: {totals['total_runs']} "
          f"({totals['n_timed_out']} timed out) | "
          f"models: {totals['n_models']} | cases: {totals['n_cases']} | "
          f"sets: {totals['n_result_sets']} ({n_disc} with run-count discrepancy)")
    print(f"  Total spend: ${cost['total_spend_usd']:.2f}")
    excluded = (totals.get("generation_params") or {}).get("results_excluded") or []
    if excluded:
        print(f"  Excluded result sets (--exclude-results): {', '.join(excluded)}")
    if gw:
        print(f"  Weakest criterion overall: {gw['name']} "
              f"({gw['passed']}/{gw['total']} = {gw['rate']:.0%}, "
              f"{gw['group_label']})")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    base_dir, results_dir, datasets_dir, output_path = resolve_paths(args)

    print(f"Results dir: {results_dir}")
    print(f"Datasets dir: {datasets_dir}")
    print(f"Output: {output_path}")

    # Load data
    result_sets = load_result_sets(results_dir, args.results, args.exclude_results)
    if not result_sets:
        print("ERROR: No result sets found.", file=sys.stderr)
        sys.exit(1)

    cases = load_cases(datasets_dir)
    runs = load_runs(results_dir, result_sets, cases)

    # Renumber reps globally: runs from different result sets for the same
    # (phase, model, case_id) all have rep=0. Assign sequential rep numbers
    # so the viewer can display multiple reps in separate columns.
    from collections import defaultdict
    rep_counters = defaultdict(int)
    phase_lookup = {rs["timestamp"]: rs["phase"] for rs in result_sets}
    for run in runs:
        phase = phase_lookup.get(run["result_set"], "")
        key = (phase, run["model"], run["case_id"])
        run["rep"] = rep_counters[key]
        rep_counters[key] += 1

    transcripts, subagent_transcripts = load_transcripts(results_dir, runs)
    model_pricing = load_model_pricing(base_dir)

    # Build bundle
    data_bundle = build_data_bundle(
        result_sets, cases, runs, transcripts, subagent_transcripts,
        model_pricing=model_pricing,
    )

    # Precomputed metrics (embedded as PRECOMPUTED alongside DATA)
    generation_params = {
        "results_filter": args.results if args.results else "all",
        "results_excluded": args.exclude_results if args.exclude_results else [],
        "generated_at": data_bundle["generated_at"],
        "generator_version": data_bundle["generator_version"],
    }
    precomputed = build_precomputed(result_sets, cases, runs, generation_params)

    # Print summaries
    print_summary(data_bundle)
    print_precomputed_report(precomputed)

    # Generate HTML
    html = generate_html(data_bundle, precomputed)

    # Write output
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  Output written: {output_path}")
    print(f"  File size: {file_size_mb:.2f} MB")
    print(f"  Done.\n")


if __name__ == "__main__":
    main()
