#!/usr/bin/env python3
"""
Generate a self-contained HTML viewer for DAAF benchmark results.

Reads benchmark result sets from benchmarks/results/, loads case definitions,
condenses transcripts, and produces a single HTML file with all data embedded.

Usage:
    python3 benchmarks/scripts/generate_results_viewer.py [--results TIMESTAMP...] [--output PATH]

Examples:
    # Generate viewer for all result sets
    python3 benchmarks/scripts/generate_results_viewer.py

    # Generate for specific result sets
    python3 benchmarks/scripts/generate_results_viewer.py --results 20260608_181352 20260608_181751

    # Custom output path
    python3 benchmarks/scripts/generate_results_viewer.py --output benchmarks/my_viewer.html
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
        "--output",
        default=None,
        help="Output HTML file path (default: benchmarks/viewer.html)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def resolve_paths(args):
    """Return (base_dir, results_dir, datasets_dir, output_path)."""
    # The script lives at benchmarks/scripts/generate_results_viewer.py
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

def load_result_sets(results_dir, filter_timestamps=None):
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

    for ts in timestamps:
        ts_dir = os.path.join(results_dir, ts)
        summary_path = os.path.join(ts_dir, "summary.json")

        if not os.path.isfile(summary_path):
            print(f"WARNING: No summary.json in {ts_dir}, skipping", file=sys.stderr)
            continue

        with open(summary_path, "r") as f:
            summary = json.load(f)

        phase_id, phase_label = detect_phase(summary)

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

    # Map directory names to phase IDs
    dir_to_phase = {
        "mode_classification": "mode_classification",
        "post_confirmation": "post_confirmation",
        "dispatch_compliance": "dispatch_compliance",
    }

    for dirname in sorted(os.listdir(datasets_dir)):
        cases_path = os.path.join(datasets_dir, dirname, "cases.jsonl")
        if not os.path.isfile(cases_path):
            continue

        phase = dir_to_phase.get(dirname, dirname)

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
                "reasoning_cost_multiplier": result.get("reasoning_cost_multiplier", 1.0),
                "input_tokens": result.get("input_tokens", 0),
                "output_tokens": result.get("output_tokens", 0),
                "cache_read_tokens": result.get("cache_read_tokens", 0),
                "cache_creation_tokens": result.get("cache_creation_tokens", 0),
                "duration_s": result.get("duration_s", 0),
                "error": result.get("error", None),
                "criteria": criteria,
                "subagent_criteria": subagent_criteria,
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

PHASE_ORDER = {"mode_classification": 1, "post_confirmation": 2, "dispatch_compliance": 3, "skill_routing": 4}


def build_data_bundle(result_sets, cases, runs, transcripts, subagent_transcripts,
                      model_pricing=None):
    """Assemble the complete data bundle for embedding in HTML."""
    # Sort result_sets by phase order so they always appear Phase 1, 2, 3
    sorted_result_sets = sorted(
        result_sets, key=lambda rs: PHASE_ORDER.get(rs["phase"], 99)
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator_version": "1.0.0",
        "result_sets": sorted_result_sets,
        "cases": cases,
        "runs": runs,
        "transcripts": transcripts,
        "subagent_transcripts": subagent_transcripts,
        "model_pricing": model_pricing or {},
    }


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def generate_html(data_bundle):
    """Generate a self-contained HTML file with embedded data and interactive viewer."""
    data_json = json.dumps(data_bundle, ensure_ascii=False, separators=(",", ":"))
    # Escape all '<' to prevent HTML5 parser state transitions inside <script>
    # (covers </script> termination, <!-- escape state, <script double-escape)
    data_json = data_json.replace("<", "\\u003c")
    # Strip C1 control characters (U+007F-U+009F) that json.dumps doesn't escape
    data_json = "".join(
        ch for ch in data_json
        if ord(ch) >= 0x20 or ch in "\n\r\t"
        if not (0x7F <= ord(ch) <= 0x9F)
    )

    generated_display = data_bundle["generated_at"][:19].replace("T", " ")
    num_runs = len(data_bundle["runs"])
    num_cases = len(data_bundle["cases"])
    num_transcripts = len(data_bundle["transcripts"])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DAAF Benchmark Results Viewer</title>
<style>
/* === Reset & Base === */
*{{ margin:0; padding:0; box-sizing:border-box; }}
html,body{{ height:100%; }}
body{{
  background:#0f172a; color:#f8fafc;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;
  line-height:1.5; display:flex; flex-direction:column; min-height:100vh;
}}
a{{ color:#818cf8; text-decoration:none; }}
a:hover{{ text-decoration:underline; }}
button{{ cursor:pointer; font-family:inherit; }}
code{{ font-family:'SF Mono',SFMono-Regular,Consolas,'Liberation Mono',Menlo,monospace; font-size:0.85em; }}

/* === Layout === */
.app-header{{
  background:#1e293b; border-bottom:1px solid #334155;
  padding:10px 20px; display:flex; align-items:center; justify-content:space-between;
  flex-shrink:0; z-index:100;
}}
.app-header h1{{ font-size:17px; font-weight:600; }}
.app-header .gen{{ font-size:11px; color:#64748b; }}
.filter-bar{{
  background:#1e293b; border-bottom:1px solid #334155;
  padding:8px 20px; display:flex; align-items:center; gap:8px; flex-wrap:wrap;
  flex-shrink:0;
}}
.app-body{{
  display:flex; flex:1; overflow:hidden;
}}
.nav-panel{{
  width:140px; min-width:140px; background:#1e293b; border-right:1px solid #334155;
  display:flex; flex-direction:column; padding:12px 0; flex-shrink:0;
}}
.nav-item{{
  padding:8px 20px; font-size:13px; color:#94a3b8; cursor:pointer;
  border-left:3px solid transparent; transition:background .15s;
}}
.nav-item:hover{{ background:#334155; color:#f8fafc; }}
.nav-item.active{{ color:#f8fafc; border-left-color:#6366f1; background:rgba(99,102,241,.08); font-weight:600; }}
.main-content{{
  flex:1; overflow-y:auto; padding:20px 24px;
}}
.status-bar{{
  background:#1e293b; border-top:1px solid #334155;
  padding:6px 20px; font-size:11px; color:#64748b; flex-shrink:0;
  display:flex; gap:16px;
}}

/* === Filter Bar === */
.filter-group{{ display:flex; align-items:center; gap:4px; }}
.filter-group label{{ font-size:11px; color:#64748b; text-transform:uppercase; letter-spacing:.5px; }}
.filter-select{{
  background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:4px;
  padding:4px 8px; font-size:12px; min-width:100px;
}}
.filter-select option{{ background:#1e293b; }}
.filter-input{{
  background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:4px;
  padding:4px 8px; font-size:12px; width:180px;
}}
.filter-checkbox{{
  display:flex; align-items:center; gap:4px; font-size:11px; color:#94a3b8;
  cursor:pointer; user-select:none; white-space:nowrap;
}}
.filter-checkbox input{{ cursor:pointer; }}
.filter-btn{{
  background:#334155; color:#94a3b8; border:1px solid #475569; border-radius:4px;
  padding:4px 10px; font-size:11px;
}}
.filter-btn:hover{{ background:#475569; color:#f8fafc; }}

/* === Cards & Panels === */
.card{{
  background:#1e293b; border:1px solid #334155; border-radius:8px;
  padding:16px 20px; margin-bottom:16px; overflow-x:auto;
}}
.card-header{{ font-size:14px; font-weight:600; margin-bottom:8px; }}
.card-muted{{ font-size:12px; color:#64748b; }}
.section-title{{
  font-size:13px; font-weight:600; color:#94a3b8; text-transform:uppercase;
  letter-spacing:.5px; margin:20px 0 10px;
}}

/* === Scorecard === */
.scorecard-row{{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:16px; }}
.scorecard{{
  background:#1e293b; border:1px solid #334155; border-radius:8px;
  padding:16px 20px; flex:1; min-width:200px; text-align:center;
}}
.scorecard .model-name{{ font-size:13px; font-weight:600; margin-bottom:2px; }}
.scorecard .provider{{ font-size:11px; color:#64748b; margin-bottom:8px; }}
.scorecard .big-num{{ font-size:36px; font-weight:700; line-height:1.1; }}
.scorecard .sub-stats{{ font-size:11px; color:#94a3b8; margin-top:8px; display:flex; gap:12px; justify-content:center; }}

/* === Tables === */
.data-table{{
  width:100%; border-collapse:collapse; font-size:12px;
}}
.data-table th{{
  text-align:left; padding:8px 10px; border-bottom:2px solid #334155;
  color:#94a3b8; font-weight:600; font-size:11px; text-transform:uppercase;
  letter-spacing:.3px; cursor:pointer; user-select:none; white-space:nowrap;
}}
.data-table th:hover{{ color:#f8fafc; }}
.data-table td{{
  padding:6px 10px; border-bottom:1px solid #1e293b;
}}
.data-table tr:hover td{{ background:rgba(99,102,241,.04); }}

/* === Heatmap cells === */
.hm-cell{{
  display:inline-block; padding:3px 8px; border-radius:4px; font-size:11px;
  font-weight:600; text-align:center; min-width:48px; cursor:pointer;
}}

/* === Cases View === */
.case-row{{ cursor:pointer; }}
.case-row:hover td{{ background:rgba(99,102,241,.06); }}
.case-detail{{
  display:none; background:#0f172a; border:1px solid #334155; border-radius:6px;
  padding:16px; margin:4px 0 12px; font-size:12px;
}}
.case-detail.open{{ display:block; }}
.case-prompt{{ background:#1e293b; padding:10px; border-radius:4px; margin:8px 0; white-space:pre-wrap; font-size:12px; color:#cbd5e1; }}
.req-list{{ margin:6px 0 6px 16px; }}
.req-list li{{ color:#94a3b8; margin-bottom:3px; }}
.rep-grid{{ margin-top:10px; }}
.rep-grid table{{ border-collapse:collapse; font-size:11px; }}
.rep-grid th{{ padding:4px 8px; color:#94a3b8; font-weight:600; text-align:center; border-bottom:1px solid #334155; }}
.rep-grid td{{ padding:4px 8px; text-align:center; border-bottom:1px solid #1e293b; }}
.crit-pass{{ color:#22c55e; font-weight:700; }}
.crit-fail{{ color:#ef4444; font-weight:700; }}
.crit-na{{ color:#475569; }}
.case-header-row td{{ background:#0f172a !important; border-bottom:1px solid #334155; }}
.case-header-row:hover td{{ background:#0f172a !important; }}
.rep-label{{ color:#64748b; font-size:11px; font-weight:600; white-space:nowrap; }}

/* === Costs View === */
.cost-table{{ width:100%; }}

/* === Logs View === */
.logs-layout{{ display:flex; gap:16px; height:calc(100vh - 200px); }}
.run-list-panel{{
  width:380px; min-width:300px; overflow-y:auto; border:1px solid #334155;
  border-radius:8px; background:#1e293b;
}}
.run-list-item{{
  padding:8px 12px; cursor:pointer; border-bottom:1px solid #0f172a;
  font-size:12px; display:flex; flex-wrap:wrap; gap:4px 12px;
}}
.run-list-item:hover{{ background:rgba(99,102,241,.06); }}
.run-list-item.selected{{ background:rgba(99,102,241,.12); border-left:3px solid #6366f1; }}
.run-list-item .case-label{{ font-weight:600; color:#f8fafc; }}
.run-list-item .model-label{{ color:#94a3b8; }}
.run-list-item .status-dot{{ display:inline-block; width:8px; height:8px; border-radius:50%; }}
.dot-pass{{ background:#22c55e; }}
.dot-partial{{ background:#eab308; }}
.dot-fail{{ background:#ef4444; }}
.dot-error{{ background:#64748b; }}
.run-detail-panel{{
  flex:1; overflow-y:auto; border:1px solid #334155; border-radius:8px;
  background:#1e293b; padding:16px 20px;
}}
.run-detail-panel .empty-state{{ color:#64748b; text-align:center; padding:60px 20px; font-size:13px; }}

/* Transcript */
.transcript{{ margin-top:16px; }}
.tx-msg{{ padding:6px 10px; margin-bottom:4px; border-radius:4px; font-size:12px; }}
.tx-user{{ background:rgba(99,102,241,.1); border-left:3px solid #6366f1; }}
.tx-assistant{{ background:rgba(34,197,94,.06); border-left:3px solid #22c55e; }}
.tx-tool-call{{ background:rgba(245,158,11,.08); border-left:3px solid #f59e0b; font-size:11px; }}
.tx-tool-result{{ background:rgba(100,116,139,.08); border-left:3px solid #64748b; font-size:11px; }}
.tx-system{{ background:rgba(100,116,139,.05); border-left:3px solid #475569; font-size:11px; color:#64748b; }}
.tx-role{{ font-weight:700; font-size:10px; text-transform:uppercase; letter-spacing:.5px; margin-right:6px; }}
.tx-content{{ white-space:pre-wrap; word-break:break-word; }}
.tx-toggle{{ color:#818cf8; cursor:pointer; font-size:11px; }}
.tx-toggle:hover{{ text-decoration:underline; }}
.tx-collapsed{{ max-height:40px; overflow:hidden; position:relative; }}
.tx-collapsed::after{{
  content:''; position:absolute; bottom:0; left:0; right:0; height:20px;
  background:linear-gradient(transparent,#1e293b);
}}

/* Criteria checklist */
.crit-check{{ display:flex; align-items:flex-start; gap:6px; margin-bottom:6px; font-size:12px; }}
.crit-icon{{ font-weight:700; flex-shrink:0; width:16px; text-align:center; }}
.crit-name{{ font-weight:600; color:#e2e8f0; }}
.crit-detail{{ color:#94a3b8; font-size:11px; margin-left:22px; }}

/* === Charts (SVG) === */
.chart-container{{ margin:16px 0; overflow-x:auto; }}
.chart-container svg{{ display:block; }}
.chart-container svg text{{ font-family:inherit; }}

/* === Tooltip === */
.tooltip{{
  position:fixed; background:#1e293b; border:1px solid #475569; border-radius:6px;
  padding:8px 12px; font-size:11px; color:#e2e8f0; z-index:9999;
  pointer-events:none; max-width:300px; box-shadow:0 4px 12px rgba(0,0,0,.4);
  display:none;
}}

/* === Model colors === */
.mc-0{{ color:#a5b4fc; }} .mc-1{{ color:#fcd34d; }} .mc-2{{ color:#67e8f9; }}
.mc-3{{ color:#f9a8d4; }} .mc-4{{ color:#86efac; }} .mc-5{{ color:#fca5a5; }}

/* === Utilities === */
.text-muted{{ color:#64748b; }}
.text-secondary{{ color:#94a3b8; }}
.text-sm{{ font-size:12px; }}
.text-xs{{ font-size:11px; }}
.mt-2{{ margin-top:8px; }}
.mt-4{{ margin-top:16px; }}
.mb-2{{ margin-bottom:8px; }}
.mb-4{{ margin-bottom:16px; }}
.flex{{ display:flex; }}
.gap-2{{ gap:8px; }}
.gap-4{{ gap:16px; }}
.flex-wrap{{ flex-wrap:wrap; }}
.items-center{{ align-items:center; }}
.badge{{
  display:inline-block; background:#334155; color:#e2e8f0;
  padding:1px 8px; border-radius:10px; font-size:11px; white-space:nowrap;
}}
.badge-pass{{ background:rgba(34,197,94,.2); color:#86efac; }}
.badge-fail{{ background:rgba(239,68,68,.2); color:#fca5a5; }}
.badge-error{{ background:rgba(100,116,139,.2); color:#94a3b8; }}
.empty-msg{{ color:#64748b; text-align:center; padding:40px; font-size:13px; }}
.clickable{{ cursor:pointer; }}
.clickable:hover{{ opacity:.85; }}
</style>
</head>
<body>

<!-- App Header -->
<div class="app-header">
  <div style="display:flex;align-items:baseline;gap:8px;">
    <h1>DAAF Benchmark Results</h1>
    <span style="font-size:13px;color:#94a3b8;">Viewer</span>
  </div>
  <span class="gen">Generated {generated_display} UTC</span>
</div>

<!-- Filter Bar -->
<div class="filter-bar" id="filter-bar">
  <div class="filter-group">
    <label>Phase</label>
    <select class="filter-select" id="f-phase" multiple></select>
  </div>
  <div class="filter-group">
    <label>Model</label>
    <select class="filter-select" id="f-model" multiple></select>
  </div>
  <div class="filter-group">
    <label>Category</label>
    <select class="filter-select" id="f-category" multiple></select>
  </div>
  <div class="filter-group">
    <label>Status</label>
    <select class="filter-select" id="f-status">
      <option value="">All</option>
      <option value="passed">Passed</option>
      <option value="partial">Partial</option>
      <option value="failed">Failed</option>
      <option value="errored">Errored</option>
    </select>
  </div>
  <div class="filter-group">
    <input type="text" class="filter-input" id="f-search" placeholder="Search cases...">
  </div>
  <label class="filter-checkbox"><input type="checkbox" id="f-hide-timeouts"> Hide timeouts</label>
  <button class="filter-btn" id="btn-reset-filters">Reset Filters</button>
</div>

<!-- App Body: Nav + Main -->
<div class="app-body">
  <div class="nav-panel" id="nav-panel">
    <div class="nav-item active" data-view="overview">Overview</div>
    <div class="nav-item" data-view="models">Models</div>
    <div class="nav-item" data-view="cases">Cases</div>
    <div class="nav-item" data-view="costs">Costs</div>
    <div class="nav-item" data-view="logs">Logs</div>
  </div>
  <div class="main-content" id="main-content"></div>
</div>

<!-- Status Bar -->
<div class="status-bar" id="status-bar"></div>

<!-- Tooltip -->
<div class="tooltip" id="tooltip"></div>

<!-- Data -->
<script>
const DATA = {data_json};
</script>

<script>
(function(){{
"use strict";

/* =================================================================
   STATE MANAGEMENT
   ================================================================= */

var state = {{
  view: "overview",
  filters: {{ phase:"", model:"", category:"", status:"", search:"", hideTimeouts:false }},
  selectedRunIdx: -1,
  expandedCases: {{}},
  sortCol: null,
  sortDir: 1,
  costSortCol: null,
  costSortDir: 1
}};

/* =================================================================
   HELPERS
   ================================================================= */

var MODEL_COLORS = ["#6366f1","#f59e0b","#06b6d4","#ec4899","#22c55e","#ef4444","#8b5cf6","#14b8a6"];
var MODEL_COLORS_LIGHT = ["#a5b4fc","#fcd34d","#67e8f9","#f9a8d4","#86efac","#fca5a5","#c4b5fd","#5eead4"];

function uniqueModels(){{
  var s=new Set(); DATA.runs.forEach(function(r){{ s.add(r.model); }}); return Array.from(s).sort();
}}
function uniquePhases(){{
  return DATA.result_sets.map(function(rs){{ return {{id:rs.phase,label:rs.phase_label}}; }});
}}
function uniqueCategories(){{
  var s=new Set();
  Object.values(DATA.cases).forEach(function(c){{ if(c.subcategory) s.add(c.subcategory); }});
  return Array.from(s).sort();
}}
function modelColor(m){{
  var models=uniqueModels(); var i=models.indexOf(m);
  return MODEL_COLORS[i % MODEL_COLORS.length];
}}
function modelColorLight(m){{
  var models=uniqueModels(); var i=models.indexOf(m);
  return MODEL_COLORS_LIGHT[i % MODEL_COLORS_LIGHT.length];
}}

function rateColor(rate){{
  if(rate>=0.9) return "#22c55e";
  if(rate>=0.7) return "#84cc16";
  if(rate>=0.5) return "#eab308";
  if(rate>=0.3) return "#f97316";
  return "#ef4444";
}}
function rateColorBg(rate){{
  if(rate>=0.9) return "rgba(34,197,94,.2)";
  if(rate>=0.7) return "rgba(132,204,22,.2)";
  if(rate>=0.5) return "rgba(234,179,8,.2)";
  if(rate>=0.3) return "rgba(249,115,22,.2)";
  return "rgba(239,68,68,.2)";
}}
function pct(v){{ return (v*100).toFixed(0)+"%"; }}
function dollars(v){{ return "$"+v.toFixed(3); }}
function esc(s){{ if(!s) return ""; var d=document.createElement("div"); d.textContent=s; return d.innerHTML; }}
function truncate(s,n){{ if(!s) return ""; return s.length>n ? s.substring(0,n)+"..." : s; }}
function el(id){{ return document.getElementById(id); }}
function fmt(n){{ return n.toLocaleString(); }}
function reasoningBadge(mult){{ if(!mult||mult<=1.0) return ""; return ' <span class="badge" style="background:rgba(249,115,22,.15);color:#f59e0b;font-size:10px;padding:1px 5px" title="Cost includes '+mult.toFixed(2)+'x reasoning token multiplier (empirical — see models.yaml)">'+mult.toFixed(2)+'x reasoning</span>'; }}
function modelMultiplier(model,runs){{ var r=runs.find(function(x){{ return x.model===model; }}); return r ? (r.reasoning_cost_multiplier||1.0) : 1.0; }}

/* Run status classification */
function runStatus(run){{
  if(run.error) return "errored";
  var crit=run.criteria||{{}};
  var keys=Object.keys(crit);
  if(keys.length===0) return "errored";
  var passed=keys.filter(function(k){{ return crit[k] && crit[k].passed; }}).length;
  if(passed===keys.length) return "passed";
  if(passed===0) return "failed";
  return "partial";
}}
function runPassRate(run){{
  var crit=run.criteria||{{}};
  var keys=Object.keys(crit);
  if(keys.length===0) return 0;
  var passed=keys.filter(function(k){{ return crit[k] && crit[k].passed; }}).length;
  return passed/keys.length;
}}
function allCriteriaPassed(run){{
  var crit=run.criteria||{{}};
  var keys=Object.keys(crit);
  if(keys.length===0) return false;
  return keys.every(function(k){{ return crit[k] && crit[k].passed; }});
}}

function hardCritPassRate(run){{
  var crit=run.criteria||{{}};
  var keys=Object.keys(crit).filter(function(k){{ return crit[k] && crit[k].tier==="hard"; }});
  if(keys.length===0) return -1;
  var passed=keys.filter(function(k){{ return crit[k].passed; }}).length;
  return passed/keys.length;
}}

function softCritPassRate(run){{
  var crit=run.criteria||{{}};
  var keys=Object.keys(crit).filter(function(k){{ return crit[k] && crit[k].tier==="soft"; }});
  if(keys.length===0) return -1;
  var passed=keys.filter(function(k){{ return crit[k].passed; }}).length;
  return passed/keys.length;
}}

/* Phase for a run */
function runPhase(run){{
  for(var i=0;i<DATA.result_sets.length;i++){{
    if(DATA.result_sets[i].timestamp===run.result_set) return DATA.result_sets[i].phase;
  }}
  return "unknown";
}}
function runPhaseLabel(run){{
  for(var i=0;i<DATA.result_sets.length;i++){{
    if(DATA.result_sets[i].timestamp===run.result_set) return DATA.result_sets[i].phase_label;
  }}
  return "Unknown";
}}

/* =================================================================
   EVALUATION GROUPS
   Splits Phase 3 into 3a (dispatch) and 3b (subagent) while keeping
   Phase 1 and Phase 2 as single groups.
   ================================================================= */

var evalGroups = [];
(function buildEvalGroups(){{
  var gmap={{}};
  DATA.result_sets.forEach(function(rs){{
    if(rs.phase === "dispatch_compliance" && rs.subagent_criterion_names && rs.subagent_criterion_names.length > 0){{
      var idD=rs.phase+"_dispatch";
      if(!gmap[idD]) gmap[idD]={{id:idD,phase:rs.phase,label:"Phase 3a \u2014 Dispatch Compliance",timestamps:[],criterion_names:rs.criterion_names.slice(),is_subagent:false}};
      gmap[idD].timestamps.push(rs.timestamp);
      var idS=rs.phase+"_subagent";
      if(!gmap[idS]) gmap[idS]={{id:idS,phase:rs.phase,label:"Phase 3b \u2014 Subagent Behavior",timestamps:[],criterion_names:rs.subagent_criterion_names.slice(),is_subagent:true}};
      gmap[idS].timestamps.push(rs.timestamp);
    }} else {{
      var id=rs.phase;
      if(!gmap[id]) gmap[id]={{id:id,phase:rs.phase,label:rs.phase_label,timestamps:[],criterion_names:rs.criterion_names.slice(),is_subagent:false}};
      gmap[id].timestamps.push(rs.timestamp);
    }}
  }});
  var order=["mode_classification","post_confirmation","dispatch_compliance_dispatch","dispatch_compliance_subagent"];
  order.forEach(function(id){{ if(gmap[id]) evalGroups.push(gmap[id]); }});
  Object.keys(gmap).forEach(function(id){{ if(order.indexOf(id)<0) evalGroups.push(gmap[id]); }});
}})();

function getEvalGroups(){{
  return evalGroups;
}}

/* Get the relevant criteria dict from a run for a given eval group */
function getRunCriteria(run, group){{
  if(group.is_subagent){{
    return run.subagent_criteria || {{}};
  }}
  return run.criteria || {{}};
}}

/* Pass rate for a run within a specific eval group */
function groupPassRate(run, group){{
  var crit = getRunCriteria(run, group);
  var keys = Object.keys(crit);
  if(keys.length === 0) return 0;
  var passed = keys.filter(function(k){{ return crit[k] && crit[k].passed; }}).length;
  return passed / keys.length;
}}

/* Whether all criteria passed for a run within a specific eval group */
function groupAllPassed(run, group){{
  var crit = getRunCriteria(run, group);
  var keys = Object.keys(crit);
  if(keys.length === 0) return false;
  return keys.every(function(k){{ return crit[k] && crit[k].passed; }});
}}

/* Check if a run belongs to an eval group (by matching result_set timestamp and phase) */
function runInGroup(run, group){{
  return group.timestamps.indexOf(run.result_set) >= 0 && runPhase(run) === group.phase;
}}

/* =================================================================
   FILTER LOGIC
   ================================================================= */

function filteredRuns(){{
  var f=state.filters;
  return DATA.runs.filter(function(r){{
    if(f.phase){{
      /* f.phase is now an eval group ID; find the matching group */
      var matchedGroup=null;
      for(var gi=0;gi<evalGroups.length;gi++){{
        if(evalGroups[gi].id===f.phase){{ matchedGroup=evalGroups[gi]; break; }}
      }}
      if(matchedGroup){{
        if(!runInGroup(r, matchedGroup)) return false;
      }} else {{
        /* fallback: treat as raw phase ID */
        if(runPhase(r)!==f.phase) return false;
      }}
    }}
    if(f.model && r.model!==f.model) return false;
    if(f.category){{
      var c=DATA.cases[r.case_id];
      if(!c || c.subcategory!==f.category) return false;
    }}
    if(f.status && runStatus(r)!==f.status) return false;
    if(f.search){{
      var q=f.search.toLowerCase();
      var c2=DATA.cases[r.case_id];
      var haystack=(r.case_id+" "+(c2?c2.prompt:"")).toLowerCase();
      if(haystack.indexOf(q)<0) return false;
    }}
    if(f.hideTimeouts && r.error && r.error.toLowerCase().indexOf("timed out")>=0) return false;
    return true;
  }});
}}

function initFilters(){{
  var phSel=el("f-phase");
  phSel.innerHTML='<option value="">All Phases</option>';
  getEvalGroups().forEach(function(g){{
    phSel.innerHTML+='<option value="'+g.id+'">'+esc(g.label)+'</option>';
  }});
  var mSel=el("f-model");
  mSel.innerHTML='<option value="">All Models</option>';
  uniqueModels().forEach(function(m){{
    mSel.innerHTML+='<option value="'+esc(m)+'">'+esc(m)+'</option>';
  }});
  var cSel=el("f-category");
  cSel.innerHTML='<option value="">All Categories</option>';
  uniqueCategories().forEach(function(c){{
    cSel.innerHTML+='<option value="'+esc(c)+'">'+esc(c)+'</option>';
  }});
}}

function readFilters(){{
  state.filters.phase=el("f-phase").value;
  state.filters.model=el("f-model").value;
  state.filters.category=el("f-category").value;
  state.filters.status=el("f-status").value;
  state.filters.search=el("f-search").value;
  state.filters.hideTimeouts=el("f-hide-timeouts").checked;
}}

function applyFilters(){{
  readFilters();
  updateHash();
  render();
}}

function resetFilters(){{
  el("f-phase").value="";
  el("f-model").value="";
  el("f-category").value="";
  el("f-status").value="";
  el("f-search").value="";
  el("f-hide-timeouts").checked=false;
  applyFilters();
}}

/* URL hash state — file:// safe (Chrome blocks replaceState on file:// origins) */
var isFileProto=(location.protocol==="file:");
function updateHash(){{
  var parts=[];
  parts.push("v="+state.view);
  if(state.filters.phase) parts.push("phase="+encodeURIComponent(state.filters.phase));
  if(state.filters.model) parts.push("model="+encodeURIComponent(state.filters.model));
  if(state.filters.category) parts.push("cat="+encodeURIComponent(state.filters.category));
  if(state.filters.status) parts.push("status="+state.filters.status);
  if(state.filters.search) parts.push("q="+encodeURIComponent(state.filters.search));
  if(state.filters.hideTimeouts) parts.push("ht=1");
  if(isFileProto){{ location.hash=parts.join("&"); }}
  else{{ try{{ history.replaceState(null,"","#"+parts.join("&")); }}catch(e){{ location.hash=parts.join("&"); }} }}
}}
function loadHash(){{
  var h=location.hash.replace(/^#/,"");
  if(!h) return;
  h.split("&").forEach(function(kv){{
    var p=kv.split("="); if(p.length!==2) return;
    var k=p[0],v=decodeURIComponent(p[1]);
    if(k==="v") state.view=v;
    if(k==="phase"){{ state.filters.phase=v; el("f-phase").value=v; }}
    if(k==="model"){{ state.filters.model=v; el("f-model").value=v; }}
    if(k==="cat"){{ state.filters.category=v; el("f-category").value=v; }}
    if(k==="status"){{ state.filters.status=v; el("f-status").value=v; }}
    if(k==="q"){{ state.filters.search=v; el("f-search").value=v; }}
    if(k==="ht"){{ state.filters.hideTimeouts=v==="1"; el("f-hide-timeouts").checked=v==="1"; }}
  }});
}}

/* =================================================================
   STATUS BAR
   ================================================================= */

function updateStatusBar(){{
  var runs=filteredRuns();
  var total=DATA.runs.length;
  var phases=new Set(); var models=new Set();
  runs.forEach(function(r){{ phases.add(runPhase(r)); models.add(r.model); }});
  el("status-bar").textContent="Showing "+runs.length+" of "+total+" runs | "+
    phases.size+" phase"+(phases.size!==1?"s":"")+" | "+
    models.size+" model"+(models.size!==1?"s":"");
}}

/* =================================================================
   TOOLTIP
   ================================================================= */

var tip=null;
function showTip(evt,html){{
  if(!tip) tip=el("tooltip");
  tip.innerHTML=html; tip.style.display="block";
  var x=evt.clientX+12, y=evt.clientY+12;
  if(x+300>window.innerWidth) x=evt.clientX-310;
  if(y+100>window.innerHeight) y=evt.clientY-110;
  tip.style.left=x+"px"; tip.style.top=y+"px";
}}
function hideTip(){{
  if(!tip) tip=el("tooltip");
  tip.style.display="none";
}}

/* =================================================================
   VIEW RENDERERS
   ================================================================= */

function render(){{
  var mc=el("main-content");
  updateStatusBar();
  switch(state.view){{
    case "overview": renderOverview(mc); break;
    case "models":   renderModels(mc); break;
    case "cases":    renderCases(mc); break;
    case "costs":    renderCosts(mc); break;
    case "logs":     renderLogs(mc); break;
    default: mc.innerHTML='<div class="empty-msg">Unknown view</div>';
  }}
  /* update nav */
  document.querySelectorAll(".nav-item").forEach(function(ni){{
    ni.classList.toggle("active", ni.getAttribute("data-view")===state.view);
  }});
}}

/* ----- Overview View ----- */
function renderOverview(container){{
  var runs=filteredRuns();
  var models=uniqueModels();
  /* filter models to those present in runs */
  var activeModels=[]; var modelSet=new Set();
  runs.forEach(function(r){{ modelSet.add(r.model); }});
  models.forEach(function(m){{ if(modelSet.has(m)) activeModels.push(m); }});

  /* per-model aggregate (phase-aware when filtered) */
  var activeGroup=null;
  if(state.filters.phase){{
    for(var gi=0;gi<evalGroups.length;gi++){{
      if(evalGroups[gi].id===state.filters.phase){{ activeGroup=evalGroups[gi]; break; }}
    }}
  }}
  var modelStats={{}};
  activeModels.forEach(function(m){{ modelStats[m]={{runs:0,errors:0,passed:0,total_crit:0,perfect:0,hard_passed:0,hard_total:0,soft_passed:0,soft_total:0}}; }});
  runs.forEach(function(r){{
    var ms=modelStats[r.model]; if(!ms) return;
    ms.runs++;
    if(r.error) ms.errors++;
    var crit=activeGroup ? getRunCriteria(r, activeGroup) : (r.criteria||{{}});
    if(activeGroup ? groupAllPassed(r, activeGroup) : allCriteriaPassed(r)) ms.perfect++;
    var keys=Object.keys(crit);
    ms.total_crit+=keys.length;
    ms.passed+=keys.filter(function(k){{ return crit[k]&&crit[k].passed; }}).length;
    keys.forEach(function(k){{
      if(crit[k]&&crit[k].tier==="hard"){{ ms.hard_total++; if(crit[k].passed) ms.hard_passed++; }}
      if(crit[k]&&crit[k].tier==="soft"){{ ms.soft_total++; if(crit[k].passed) ms.soft_passed++; }}
    }});
  }});

  var html='<div class="section-title">Model Scorecards</div><div class="scorecard-row">';
  activeModels.forEach(function(m){{
    var ms=modelStats[m];
    var perfectRate=ms.runs>0 ? ms.perfect/ms.runs : 0;
    var hardRate=ms.hard_total>0 ? ms.hard_passed/ms.hard_total : 0;
    var softRate=ms.soft_total>0 ? ms.soft_passed/ms.soft_total : 0;
    html+='<div class="scorecard" style="border-top:3px solid '+modelColor(m)+'">';
    html+='<div class="model-name" style="color:'+modelColorLight(m)+'">'+esc(m)+'</div>';
    html+='<div class="provider text-xs text-muted">'+esc((runs.find(function(r){{return r.model===m;}})||{{}}).provider||"")+'</div>';
    html+='<div class="big-num" style="color:'+rateColor(perfectRate)+'">'+pct(perfectRate)+'</div>';
    html+='<div class="text-xs text-muted" style="margin-top:2px">Perfect (all criteria)</div>';
    html+='<div style="display:flex;gap:16px;justify-content:center;margin-top:8px">';
    html+='<div style="text-align:center"><div style="font-size:20px;font-weight:700;color:'+rateColor(hardRate)+'">'+pct(hardRate)+'</div><div class="text-xs text-muted">Hard</div></div>';
    html+='<div style="text-align:center"><div style="font-size:20px;font-weight:700;color:'+(ms.soft_total>0?rateColor(softRate):'#475569')+'">'+(ms.soft_total>0?pct(softRate):'\u2014')+'</div><div class="text-xs text-muted">Soft</div></div>';
    html+='</div>';
    html+='<div class="sub-stats"><span>'+ms.runs+' runs</span><span>'+ms.errors+' errors</span></div>';
    html+='</div>';
  }});
  html+='</div>';

  /* Phase summary table — uses eval groups */
  var groups=getEvalGroups().filter(function(g){{
    if(!state.filters.phase) return true;
    return g.id===state.filters.phase;
  }});
  html+='<div class="section-title">Phase Summary</div>';
  html+='<div class="card"><table class="data-table"><thead><tr><th>Phase</th>';
  activeModels.forEach(function(m){{ html+='<th colspan="3" style="color:'+modelColorLight(m)+';text-align:center;border-bottom:2px solid '+modelColor(m)+'">'+esc(m)+'</th>'; }});
  html+='</tr><tr><th></th>';
  activeModels.forEach(function(){{ html+='<th class="text-xs" style="text-align:center">Perfect</th><th class="text-xs" style="text-align:center">Hard</th><th class="text-xs" style="text-align:center">Soft</th>'; }});
  html+='</tr></thead><tbody>';
  groups.forEach(function(g){{
    html+='<tr><td style="font-weight:600">'+esc(g.label)+'</td>';
    activeModels.forEach(function(m){{
      var pr=runs.filter(function(r){{ return r.model===m && runInGroup(r, g); }});
      if(pr.length===0){{ html+='<td class="text-muted">-</td><td class="text-muted">-</td><td class="text-muted">-</td>'; return; }}
      var allPass=pr.filter(function(r){{ return groupAllPassed(r, g); }}).length;
      var perfectRate=allPass/pr.length;
      var hP=0,hT=0,sP=0,sT=0;
      pr.forEach(function(r){{
        var crit=getRunCriteria(r, g);
        Object.keys(crit).forEach(function(k){{
          if(crit[k]&&crit[k].tier==="hard"){{ hT++; if(crit[k].passed) hP++; }}
          if(crit[k]&&crit[k].tier==="soft"){{ sT++; if(crit[k].passed) sP++; }}
        }});
      }});
      var hardRate=hT>0?hP/hT:0;
      var softRate=sT>0?sP/sT:0;
      html+='<td style="text-align:center"><span class="hm-cell clickable" style="background:'+rateColorBg(perfectRate)+';color:'+rateColor(perfectRate)+'" '+
        'onclick="setFilter(&#39;model&#39;,&#39;'+esc(m)+'&#39;);setFilter(&#39;phase&#39;,&#39;'+esc(g.id)+'&#39;)">'+
        pct(perfectRate)+'</span></td>';
      html+='<td style="text-align:center"><span class="hm-cell" style="background:'+rateColorBg(hardRate)+';color:'+rateColor(hardRate)+'">'+pct(hardRate)+'</span></td>';
      html+='<td style="text-align:center">'+(sT>0?'<span class="hm-cell" style="background:'+rateColorBg(softRate)+';color:'+rateColor(softRate)+'">'+pct(softRate)+'</span>':'<span class="text-muted">\u2014</span>')+'</td>';
    }});
    html+='</tr>';
  }});
  html+='</tbody></table></div>';

  /* Hero chart: grouped bar — uses eval groups */
  html+='<div class="section-title">Pass Rates by Model and Phase</div>';
  html+='<div class="card"><div class="chart-container">'+svgGroupedBar(runs,activeModels,groups)+'</div></div>';

  container.innerHTML=html;
}}

/* ----- Models View ----- */
function renderModels(container){{
  var runs=filteredRuns();
  var models=[];
  var ms=new Set(); runs.forEach(function(r){{ ms.add(r.model); }});
  uniqueModels().forEach(function(m){{ if(ms.has(m)) models.push(m); }});

  /* Collect all criteria across filtered runs, grouped by eval group */
  var groups=getEvalGroups().filter(function(g){{
    if(!state.filters.phase) return true;
    return g.id===state.filters.phase;
  }});
  var critByGroup={{}};
  groups.forEach(function(g){{ critByGroup[g.id]=new Set(); }});
  runs.forEach(function(r){{
    groups.forEach(function(g){{
      if(!runInGroup(r, g)) return;
      var crit=getRunCriteria(r, g);
      Object.keys(crit).forEach(function(k){{ critByGroup[g.id].add(k); }});
    }});
  }});

  var html='<div class="section-title">Criterion Heatmap</div>';
  html+='<div class="card"><table class="data-table"><thead><tr><th>Criterion</th><th>Tier</th>';
  models.forEach(function(m){{ html+='<th style="color:'+modelColorLight(m)+'">'+esc(m)+'</th>'; }});
  html+='</tr></thead><tbody>';

  groups.forEach(function(g){{
    var crits=Array.from(critByGroup[g.id]||[]).sort();
    if(crits.length===0) return;
    html+='<tr><td colspan="'+(models.length+2)+'" style="background:#0f172a;font-weight:600;font-size:11px;color:#64748b;padding:8px 10px;text-transform:uppercase;letter-spacing:.5px">'+esc(g.label)+'</td></tr>';
    crits.forEach(function(cr){{
      /* Determine tier from first run that has this criterion in this group */
      var tierLabel="-";
      for(var ri=0;ri<runs.length;ri++){{
        if(!runInGroup(runs[ri], g)) continue;
        var rc=getRunCriteria(runs[ri], g);
        if(rc[cr] && rc[cr].tier){{
          tierLabel=rc[cr].tier==="hard"?"H":"S";
          break;
        }}
      }}
      html+='<tr><td><code style="font-size:11px">'+esc(cr)+'</code></td>';
      html+='<td style="text-align:center;font-size:11px;font-weight:600;color:'+(tierLabel==="H"?"#f59e0b":"#06b6d4")+'">'+tierLabel+'</td>';
      models.forEach(function(m){{
        var mr=runs.filter(function(r){{
          if(r.model!==m || !runInGroup(r, g)) return false;
          var rc2=getRunCriteria(r, g);
          return rc2 && rc2[cr];
        }});
        if(mr.length===0){{ html+='<td class="text-muted">-</td>'; return; }}
        var passed=mr.filter(function(r){{ var rc3=getRunCriteria(r, g); return rc3[cr].passed; }}).length;
        var rate=passed/mr.length;
        html+='<td><span class="hm-cell clickable" style="background:'+rateColorBg(rate)+';color:'+rateColor(rate)+'" '+
          'title="'+passed+'/'+mr.length+' passed" '+
          'onmouseover="showTip(event,&#39;'+esc(cr)+': '+passed+'/'+mr.length+' passed ('+pct(rate)+')&#39;)" '+
          'onmouseout="hideTip()" '+
          'onclick="setFilter(&#39;model&#39;,&#39;'+esc(m)+'&#39;)">'+
          pct(rate)+'</span></td>';
      }});
      html+='</tr>';
    }});
  }});
  html+='</tbody></table></div>';

  container.innerHTML=html;
}}

/* ----- Cases View ----- */
function renderCases(container){{
  var runs=filteredRuns();
  var models=[];
  var ms=new Set(); runs.forEach(function(r){{ ms.add(r.model); }});
  uniqueModels().forEach(function(m){{ if(ms.has(m)) models.push(m); }});

  /* Natural numeric sort for case IDs (mc-01, mc-02 ... mc-10, mc-11) */
  function caseSort(a,b){{
    var na=parseInt(a.replace(/[^0-9]/g,""),10)||0;
    var nb=parseInt(b.replace(/[^0-9]/g,""),10)||0;
    if(a.substring(0,3)!==b.substring(0,3)) return a.localeCompare(b);
    return na-nb;
  }}

  var groups=getEvalGroups();
  /* If a phase filter is active, only show the matching group */
  if(state.filters.phase){{
    groups=groups.filter(function(g){{ return g.id===state.filters.phase; }});
  }}

  var html='<div class="section-title">Cases by Eval Phase</div>';
  var totalCases=0;

  groups.forEach(function(group){{
    /* Collect runs belonging to this eval group */
    var groupRuns=runs.filter(function(r){{ return runInGroup(r, group); }});
    if(groupRuns.length===0) return;

    /* Unique case IDs in this group, sorted naturally */
    var caseIdSet=new Set();
    groupRuns.forEach(function(r){{ caseIdSet.add(r.case_id); }});
    var caseIds=Array.from(caseIdSet).sort(caseSort);
    if(caseIds.length===0) return;
    totalCases+=caseIds.length;

    var totalCols=3+models.length;

    /* Section header */
    html+='<div class="card" style="margin-bottom:16px">';
    html+='<div class="card-header" style="display:flex;justify-content:space-between;align-items:center">';
    html+='<span style="font-weight:700">'+esc(group.label)+'</span>';
    html+='<span class="text-muted text-xs">'+caseIds.length+' cases, '+models.length+' models, '+groupRuns.length+' runs</span>';
    html+='</div>';

    /* Table */
    html+='<table class="data-table" style="margin-top:8px"><thead><tr>';
    html+='<th style="width:60px"></th><th>Criterion</th><th style="width:36px">Tier</th>';
    models.forEach(function(m){{ html+='<th style="text-align:center;color:'+modelColorLight(m)+'">'+esc(m)+'</th>'; }});
    html+='</tr></thead><tbody>';

    caseIds.forEach(function(cid){{
      var c=DATA.cases[cid]||{{}};

      /* Case header row */
      html+='<tr class="case-header-row">';
      html+='<td colspan="'+totalCols+'" style="font-weight:600;padding:10px">';
      html+='<span style="color:#f8fafc">'+esc(cid)+'</span>';
      html+='<span style="color:#64748b;font-size:11px;margin-left:8px">'+esc(truncate(c.prompt||"",100))+'</span>';
      html+='</td></tr>';

      /* Find all reps for this case across all models */
      var caseRuns=groupRuns.filter(function(r){{ return r.case_id===cid; }});
      var maxRep=0;
      caseRuns.forEach(function(r){{ if(r.rep>maxRep) maxRep=r.rep; }});

      /* Criteria list from the group definition */
      var criteria=group.criterion_names.slice().sort();

      for(var rep=0;rep<=maxRep;rep++){{
        for(var ci=0;ci<criteria.length;ci++){{
          var criterion=criteria[ci];

          /* Determine tier from any run that has this criterion */
          var tier="";
          for(var ti=0;ti<caseRuns.length;ti++){{
            var tCrit=getRunCriteria(caseRuns[ti], group);
            if(tCrit[criterion] && tCrit[criterion].tier){{
              tier=tCrit[criterion].tier==="hard"?"H":"S";
              break;
            }}
          }}

          html+='<tr>';

          /* Rep label (only on first criterion of each rep) */
          if(ci===0){{
            html+='<td class="rep-label" rowspan="'+criteria.length+'">Rep '+rep+'</td>';
          }}

          /* Criterion name */
          html+='<td><code style="font-size:11px;color:#cbd5e1">'+esc(criterion)+'</code></td>';

          /* Tier */
          html+='<td style="text-align:center;color:'+(tier==="H"?"#f59e0b":"#64748b")+';font-size:11px;font-weight:600">'+esc(tier)+'</td>';

          /* Model cells */
          models.forEach(function(m){{
            var run=null;
            for(var ri=0;ri<caseRuns.length;ri++){{
              if(caseRuns[ri].model===m && caseRuns[ri].rep===rep){{ run=caseRuns[ri]; break; }}
            }}
            if(!run){{
              html+='<td style="text-align:center;color:#475569">&mdash;</td>';
              return;
            }}
            var critData=getRunCriteria(run, group)[criterion];
            if(!critData){{
              html+='<td style="text-align:center;color:#475569">&mdash;</td>';
            }} else {{
              var passed=critData.passed;
              html+='<td style="text-align:center;cursor:pointer" onclick="event.stopPropagation();jumpToRun(&#39;'+esc(run.run_dir)+'&#39;)">';
              html+='<span class="'+(passed?"crit-pass":"crit-fail")+'">'+(passed?"&#10003;":"&#10007;")+'</span></td>';
            }}
          }});

          html+='</tr>';
        }}
      }}
    }});

    html+='</tbody></table></div>';
  }});

  if(totalCases===0) html+='<div class="empty-msg">No cases match the current filters.</div>';
  container.innerHTML=html;
}}

/* ----- Costs View ----- */
function renderCosts(container){{
  var runs=filteredRuns();
  var models=[];
  var ms=new Set(); runs.forEach(function(r){{ ms.add(r.model); }});
  uniqueModels().forEach(function(m){{ if(ms.has(m)) models.push(m); }});

  var pricing=DATA.model_pricing||{{}};

  /* Build sorted list of models by input cost (cheapest first) */
  var pricedModels=models.slice().sort(function(a,b){{
    var pa=pricing[a], pb=pricing[b];
    var ca=pa?pa.input_per_million:Infinity;
    var cb=pb?pb.input_per_million:Infinity;
    return ca-cb;
  }});

  /* Pricing table — sortable */
  var html='<div class="section-title">Model Pricing (per 1M tokens)</div>';

  /* Compute perfect rates (phase-aware) */
  var activeGroup=null;
  if(state.filters.phase){{
    for(var gi=0;gi<evalGroups.length;gi++){{
      if(evalGroups[gi].id===state.filters.phase){{ activeGroup=evalGroups[gi]; break; }}
    }}
  }}
  var perfectByModel={{}};
  models.forEach(function(m){{
    var mr=runs.filter(function(r){{ return r.model===m; }});
    if(mr.length===0){{ perfectByModel[m]=0; return; }}
    var perf=mr.filter(function(r){{ return activeGroup ? groupAllPassed(r,activeGroup) : allCriteriaPassed(r); }}).length;
    perfectByModel[m]=perf/mr.length;
  }});

  /* Build row data for sorting */
  var costRows=pricedModels.map(function(m){{
    var p=pricing[m];
    return {{
      model:m,
      perfect:perfectByModel[m]||0,
      input:p?p.input_per_million:Infinity,
      output:p?p.output_per_million:Infinity,
      cache:p?p.cached_input_per_million:Infinity
    }};
  }});

  /* Sort by active column */
  var sortKey=state.costSortCol||"input";
  var sortDir=state.costSortDir||1;
  costRows.sort(function(a,b){{
    var va=a[sortKey], vb=b[sortKey];
    if(typeof va==="string") return sortDir*va.localeCompare(vb);
    return sortDir*(va-vb);
  }});

  /* Render header with sort arrows */
  function costTh(label,key){{
    var arrow="";
    if(state.costSortCol===key) arrow=state.costSortDir===1?" \u25B2":" \u25BC";
    else if(!state.costSortCol && key==="input") arrow=" \u25B2";
    return '<th onclick="sortCosts(&#39;'+key+'&#39;)" style="cursor:pointer">'+label+arrow+'</th>';
  }}

  html+='<div class="card"><table class="data-table"><thead><tr>';
  html+=costTh("Model","model");
  html+=costTh("Perfect Rate","perfect");
  html+=costTh("Input / 1M","input");
  html+=costTh("Output / 1M","output");
  html+=costTh("Cache Read / 1M","cache");
  html+='</tr></thead><tbody>';

  costRows.forEach(function(row){{
    var m=row.model;
    var p=pricing[m];
    var tierColor="#64748b";
    if(p){{
      if(p.input_per_million>=5) tierColor="#ef4444";
      else if(p.input_per_million>=2) tierColor="#f59e0b";
      else if(p.input_per_million>=0.5) tierColor="#eab308";
      else tierColor="#22c55e";
    }}
    html+='<tr>';
    html+='<td style="font-weight:600;color:'+modelColorLight(m)+'">'+esc(m)+' <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:'+tierColor+';vertical-align:middle;margin-left:4px"></span></td>';
    var perfRate=row.perfect;
    html+='<td><span class="hm-cell" style="background:'+rateColorBg(perfRate)+';color:'+rateColor(perfRate)+'">'+pct(perfRate)+'</span></td>';
    if(p){{
      html+='<td>$'+p.input_per_million.toFixed(2)+'</td>';
      html+='<td>$'+p.output_per_million.toFixed(2)+'</td>';
      html+='<td>'+(p.cached_input_per_million>0?'$'+p.cached_input_per_million.toFixed(2):'N/A')+'</td>';
    }} else {{
      html+='<td class="text-muted">N/A</td><td class="text-muted">N/A</td><td class="text-muted">N/A</td>';
    }}
    html+='</tr>';
  }});
  html+='</tbody></table></div>';

  /* Scatter plot uses same perfect rate as the table */
  var passRates=perfectByModel;

  /* Cost vs Pass Rate scatter */
  html+='<div class="section-title">Input Cost vs. Pass Rate</div>';
  html+='<div class="card"><div class="chart-container">'+svgScatter(models,passRates,pricing)+'</div></div>';

  container.innerHTML=html;
}}

/* ----- Logs View ----- */
function renderLogs(container){{
  var runs=filteredRuns();

  var html='<div class="logs-layout">';
  /* Left: run list */
  html+='<div class="run-list-panel" id="run-list">';
  if(runs.length===0){{
    html+='<div class="empty-msg">No runs match filters</div>';
  }} else {{
    runs.forEach(function(r,i){{
      var st=runStatus(r);
      var dotMap={{passed:"dot-pass",partial:"dot-partial",failed:"dot-fail",errored:"dot-error"}};
      var dotCls=dotMap[st]||"dot-error";
      html+='<div class="run-list-item'+(state.selectedRunIdx===i?" selected":"")+'" data-ridx="'+i+'" onclick="selectRun('+i+')">';
      html+='<span class="status-dot '+dotCls+'"></span>';
      html+='<span class="case-label">'+esc(r.case_id)+'</span>';
      html+='<span class="model-label">'+esc(r.model)+'</span>';
      html+='<span class="text-xs text-muted">rep'+r.rep+'</span>';
      html+='<span class="text-xs text-muted">'+(r.duration_s||0).toFixed(0)+'s</span>';
      html+='</div>';
    }});
  }}
  html+='</div>';
  /* Right: detail */
  html+='<div class="run-detail-panel" id="run-detail">';
  if(state.selectedRunIdx>=0 && state.selectedRunIdx<runs.length){{
    html+=renderRunDetail(runs[state.selectedRunIdx]);
  }} else {{
    html+='<div class="empty-state">Select a run from the list to view details</div>';
  }}
  html+='</div>';
  html+='</div>';

  container.innerHTML=html;
}}

function renderRunDetail(r){{
  var st=runStatus(r);
  var c=DATA.cases[r.case_id]||{{}};
  var html='';
  /* Header */
  html+='<div style="display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-bottom:12px">';
  html+='<span style="font-size:16px;font-weight:700">'+esc(r.case_id)+'</span>';
  html+='<span class="badge" style="background:'+modelColor(r.model)+';color:#fff">'+esc(r.model)+'</span>';
  html+='<span class="badge">Rep '+r.rep+'</span>';
  html+='<span class="badge badge-'+(st==="passed"?"pass":(st==="errored"?"error":"fail"))+'">'+st.toUpperCase()+'</span>';
  html+='</div>';
  html+='<div class="text-xs text-muted mb-2">Session: '+esc(r.session_id||"N/A")+' | Duration: '+(r.duration_s||0).toFixed(1)+'s</div>';
  html+='<div class="text-xs text-muted mb-4">Tokens: in='+fmt(r.input_tokens||0)+' out='+fmt(r.output_tokens||0)+' cache_read='+fmt(r.cache_read_tokens||0)+' cache_create='+fmt(r.cache_creation_tokens||0)+' | Turns: '+r.turns+'</div>';
  if(r.error){{
    html+='<div class="card" style="border-color:#ef4444;margin-bottom:12px"><strong style="color:#ef4444">Error:</strong> '+esc(r.error)+'</div>';
  }}

  /* Criteria checklist */
  html+='<div class="section-title">Criteria</div>';
  var critKeys=Object.keys(r.criteria||{{}}).sort();
  critKeys.forEach(function(k){{
    var cr=r.criteria[k];
    var passed=cr&&cr.passed;
    html+='<div class="crit-check">';
    html+='<span class="crit-icon" style="color:'+(passed?"#22c55e":"#ef4444")+'">'+(passed?"&#10003;":"&#10007;")+'</span>';
    html+='<span class="crit-name">'+esc(k)+'</span>';
    html+='</div>';
    if(cr&&cr.detail) html+='<div class="crit-detail">'+esc(cr.detail)+'</div>';
  }});

  /* Subagent criteria */
  if(r.subagent_criteria){{
    var scKeys=Object.keys(r.subagent_criteria).sort();
    if(scKeys.length>0){{
      html+='<div class="section-title" style="margin-top:16px">Subagent Criteria</div>';
      scKeys.forEach(function(k){{
        var cr=r.subagent_criteria[k];
        var passed=cr&&cr.passed;
        html+='<div class="crit-check">';
        html+='<span class="crit-icon" style="color:'+(passed?"#22c55e":"#ef4444")+'">'+(passed?"&#10003;":"&#10007;")+'</span>';
        html+='<span class="crit-name">'+esc(k)+'</span>';
        html+='</div>';
        if(cr&&cr.detail) html+='<div class="crit-detail">'+esc(cr.detail)+'</div>';
      }});
    }}
  }}

  /* Transcript */
  var tx=DATA.transcripts[r.run_dir];
  if(tx && tx.length>0){{
    html+='<div class="section-title" style="margin-top:16px">Condensed Transcript ('+tx.length+' messages)</div>';
    html+='<div class="transcript">';
    tx.forEach(function(msg,mi){{
      var cls="tx-"+msg.role.replace("_","-");
      if(msg.role==="tool_call") cls="tx-tool-call";
      if(msg.role==="tool_result") cls="tx-tool-result";
      html+='<div class="tx-msg '+cls+'">';
      if(msg.role==="user"){{
        html+='<span class="tx-role" style="color:#818cf8">USER</span>';
        html+='<span class="tx-content">'+esc(truncate(msg.content,500))+'</span>';
      }} else if(msg.role==="assistant"){{
        html+='<span class="tx-role" style="color:#22c55e">ASSISTANT</span>';
        html+='<span class="tx-content">'+esc(truncate(msg.content,500))+'</span>';
      }} else if(msg.role==="tool_call"){{
        html+='<span class="tx-role" style="color:#f59e0b">TOOL</span>';
        html+='<span style="color:#fcd34d">'+esc(msg.tool||"")+'</span>';
        if(msg.args) html+=' <span class="text-muted">'+esc(truncate(msg.args,120))+'</span>';
      }} else if(msg.role==="tool_result"){{
        html+='<span class="tx-role" style="color:#64748b">RESULT</span>';
        html+='<span style="color:'+(msg.status==="error"?"#ef4444":"#94a3b8")+'">'+esc(msg.tool||"")+'</span>';
        html+=' <span class="badge badge-'+(msg.status==="error"?"fail":"pass")+'">'+esc(msg.status||"ok")+'</span>';
        if(msg.output){{
          var outId="tx-out-"+r.run_dir.replace(/[^a-zA-Z0-9]/g,"_")+"-"+mi;
          html+='<div id="'+outId+'" class="tx-collapsed" style="margin-top:4px;font-size:11px;color:#94a3b8">'+esc(msg.output)+'</div>';
          html+='<span class="tx-toggle" onclick="event.stopPropagation();var e=document.getElementById(&#39;'+outId+'&#39;);e.classList.toggle(&#39;tx-collapsed&#39;);this.textContent=e.classList.contains(&#39;tx-collapsed&#39;)?&#39;expand&#39;:&#39;collapse&#39;;">expand</span>';
        }}
      }} else if(msg.role==="system"){{
        html+='<span class="tx-role" style="color:#475569">SYSTEM</span>';
        html+='<span class="tx-content">'+esc(truncate(msg.content,200))+'</span>';
      }}
      html+='</div>';
    }});
    html+='</div>';
  }}

  /* Subagent transcripts */
  var stx=DATA.subagent_transcripts[r.run_dir];
  if(stx){{
    var saKeys=Object.keys(stx);
    if(saKeys.length>0){{
      html+='<div class="section-title" style="margin-top:16px">Subagent Transcripts ('+saKeys.length+')</div>';
      saKeys.forEach(function(saId){{
        var saMsgs=stx[saId];
        html+='<div class="card" style="margin-bottom:8px;padding:10px 14px">';
        html+='<div class="text-xs text-muted mb-2"><strong>Agent:</strong> '+esc(saId)+' ('+saMsgs.length+' messages)</div>';
        saMsgs.slice(0,30).forEach(function(msg,mi){{
          var cls="tx-"+msg.role.replace("_","-");
          if(msg.role==="tool_call") cls="tx-tool-call";
          if(msg.role==="tool_result") cls="tx-tool-result";
          html+='<div class="tx-msg '+cls+'" style="font-size:11px">';
          if(msg.role==="user"){{
            html+='<span class="tx-role" style="color:#818cf8">USER</span>'+esc(truncate(msg.content,300));
          }} else if(msg.role==="assistant"){{
            html+='<span class="tx-role" style="color:#22c55e">ASST</span>'+esc(truncate(msg.content,300));
          }} else if(msg.role==="tool_call"){{
            html+='<span class="tx-role" style="color:#f59e0b">TOOL</span><span style="color:#fcd34d">'+esc(msg.tool||"")+'</span> '+esc(truncate(msg.args,100));
          }} else if(msg.role==="tool_result"){{
            html+='<span class="tx-role" style="color:#64748b">RES</span>'+esc(msg.tool||"")+" "+esc(msg.status||"");
          }} else {{
            html+='<span class="tx-role" style="color:#475569">SYS</span>'+esc(truncate(msg.content,150));
          }}
          html+='</div>';
        }});
        if(saMsgs.length>30) html+='<div class="text-muted text-xs" style="padding:4px 10px">... '+(saMsgs.length-30)+' more messages</div>';
        html+='</div>';
      }});
    }}
  }}

  html+='<div class="text-xs text-muted mt-4">Run dir: '+esc(r.run_dir)+'</div>';

  return html;
}}

/* =================================================================
   CHART HELPERS
   ================================================================= */

function svgGroupedBar(runs,models,groups){{
  if(models.length===0||groups.length===0) return '<div class="empty-msg">No data for chart</div>';
  var subBars=3;
  var modelGap=12;
  var clusterW=subBars*12+4;
  var groupGap=24;
  var groupW=models.length*(clusterW+modelGap)+groupGap;
  var W=Math.max(700,pad_l()+groups.length*groupW+60);
  function pad_l(){{ return 50; }}
  var H=420;
  var pad={{t:30,r:20,b:160,l:50}};
  var cw=W-pad.l-pad.r, ch=H-pad.t-pad.b;
  var barW=10;

  var svg='<svg width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'">';
  /* Hatching pattern for Hard bars */
  svg+='<defs>';
  models.forEach(function(m){{
    var c=modelColor(m);
    var id=m.replace(/[^a-zA-Z0-9]/g,"_");
    svg+='<pattern id="hatch_'+id+'" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">';
    svg+='<rect width="5" height="5" fill="'+c+'" opacity="0.3"/>';
    svg+='<line x1="0" y1="0" x2="0" y2="5" stroke="'+c+'" stroke-width="2.5"/>';
    svg+='</pattern>';
  }});
  /* Legend hatching in neutral gray */
  svg+='<pattern id="hatch_legend" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">';
  svg+='<rect width="5" height="5" fill="#94a3b8" opacity="0.3"/>';
  svg+='<line x1="0" y1="0" x2="0" y2="5" stroke="#94a3b8" stroke-width="2.5"/>';
  svg+='</pattern>';
  svg+='</defs>';
  /* Y axis */
  for(var yi=0;yi<=4;yi++){{
    var yy=pad.t+ch-ch*(yi/4);
    svg+='<line x1="'+pad.l+'" y1="'+yy+'" x2="'+(W-pad.r)+'" y2="'+yy+'" stroke="#334155" stroke-width="1"/>';
    svg+='<text x="'+(pad.l-8)+'" y="'+(yy+4)+'" fill="#64748b" font-size="10" text-anchor="end">'+(yi*25)+'%</text>';
  }}

  var tierLabels=["Perfect","Hard","Soft"];
  var baseline=pad.t+ch;

  groups.forEach(function(g,gi){{
    var gx=pad.l+gi*groupW;
    models.forEach(function(m,mi){{
      var pr=runs.filter(function(r){{ return r.model===m && runInGroup(r, g); }});
      if(pr.length===0) return;
      var allPass=pr.filter(function(r){{ return groupAllPassed(r, g); }}).length;
      var perfectRate=allPass/pr.length;
      var hP=0,hT=0,sP=0,sT=0;
      pr.forEach(function(r){{
        var crit=getRunCriteria(r, g);
        Object.keys(crit).forEach(function(k){{
          if(crit[k]&&crit[k].tier==="hard"){{ hT++; if(crit[k].passed) hP++; }}
          if(crit[k]&&crit[k].tier==="soft"){{ sT++; if(crit[k].passed) sP++; }}
        }});
      }});
      var hardRate=hT>0?hP/hT:0;
      var softRate=sT>0?sP/sT:0;
      var rates=[perfectRate,hardRate,softRate];
      var cx=gx+mi*(clusterW+modelGap);
      var mc=modelColor(m);
      var mid=m.replace(/[^a-zA-Z0-9]/g,"_");
      rates.forEach(function(rate,si){{
        var bx=cx+si*(barW+2);
        var bh=ch*rate;
        var by=baseline-bh;
        var fill,op;
        if(si===0){{ fill=mc; op="0.95"; }}
        else if(si===1){{ fill="url(#hatch_"+mid+")"; op="1"; }}
        else {{ fill=mc; op="0.35"; }}
        svg+='<rect x="'+bx+'" y="'+by+'" width="'+barW+'" height="'+bh+'" fill="'+fill+'" opacity="'+op+'" rx="1">';
        svg+='<title>'+esc(m)+' / '+esc(g.label)+' / '+tierLabels[si]+': '+pct(rate)+'</title>';
        svg+='</rect>';
      }});
      /* 45-degree model label under cluster */
      var labelX=cx+clusterW/2;
      var labelY=baseline+8;
      svg+='<text x="'+labelX+'" y="'+labelY+'" fill="'+modelColorLight(m)+'" font-size="9" text-anchor="end" transform="rotate(-45,'+labelX+','+labelY+')">'+esc(m)+'</text>';
    }});
    /* Phase group label centered above model labels */
    var groupCenterX=gx+(models.length*(clusterW+modelGap)-modelGap)/2;
    var lbl=g.label.replace(/Phase \\d+[ab]? . /,"P"+g.label.match(/\\d+[ab]?/)[0]+": ");
    svg+='<text x="'+groupCenterX+'" y="'+(H-20)+'" fill="#94a3b8" font-size="11" font-weight="600" text-anchor="middle">'+esc(lbl)+'</text>';
  }});

  /* Tier texture legend (top-right) */
  var legX=W-pad.r-200, legY=pad.t;
  svg+='<rect x="'+(legX-4)+'" y="'+(legY-2)+'" width="200" height="22" rx="4" fill="#1e293b" opacity="0.8"/>';
  var tierFills=["#94a3b8","url(#hatch_legend)","#94a3b8"];
  var tierOps=["0.95","1","0.35"];
  tierLabels.forEach(function(lab,li){{
    var tx=legX+li*65;
    svg+='<rect x="'+tx+'" y="'+(legY+2)+'" width="10" height="10" fill="'+tierFills[li]+'" opacity="'+tierOps[li]+'" rx="1"/>';
    svg+='<text x="'+(tx+14)+'" y="'+(legY+11)+'" fill="#94a3b8" font-size="10">'+lab+'</text>';
  }});

  svg+='</svg>';
  return svg;
}}

function svgScatter(models,passRates,pricing){{
  /* Filter to models that have pricing data */
  var plotModels=models.filter(function(m){{ return pricing[m]; }});
  if(plotModels.length===0) return '<div class="empty-msg">No pricing data available for scatter plot</div>';
  var W=780, H=460;
  var pad={{t:30,r:140,b:50,l:60}};
  var cw=W-pad.l-pad.r, ch=H-pad.t-pad.b;

  var maxCost=0;
  plotModels.forEach(function(m){{ var c=pricing[m].input_per_million; if(c>maxCost) maxCost=c; }});
  if(maxCost===0) maxCost=1;
  maxCost*=1.15;

  var svg='<svg width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'">';
  /* Grid — major lines every 25%, minor every 10% (y) and proportional (x) */
  for(var yi=0;yi<=10;yi++){{
    var yy=pad.t+ch-ch*(yi/10);
    var major=(yi%2===0||yi===5);
    svg+='<line x1="'+pad.l+'" y1="'+yy+'" x2="'+(pad.l+cw)+'" y2="'+yy+'" stroke="'+(major?"#334155":"#1e293b")+'" stroke-width="'+(major?1:0.5)+'"/>';
    if(yi%2===0) svg+='<text x="'+(pad.l-8)+'" y="'+(yy+4)+'" fill="#64748b" font-size="9" text-anchor="end">'+(yi*10)+'%</text>';
  }}
  for(var xi=0;xi<=8;xi++){{
    var xx=pad.l+cw*(xi/8);
    var xmajor=(xi%2===0);
    svg+='<line x1="'+xx+'" y1="'+pad.t+'" x2="'+xx+'" y2="'+(H-pad.b)+'" stroke="'+(xmajor?"#334155":"#1e293b")+'" stroke-width="'+(xmajor?1:0.5)+'"/>';
    if(xmajor) svg+='<text x="'+xx+'" y="'+(H-pad.b+14)+'" fill="#64748b" font-size="9" text-anchor="middle">$'+(maxCost*xi/8).toFixed(2)+'</text>';
  }}
  /* Axis labels */
  svg+='<text x="'+(pad.l+cw/2)+'" y="'+(H-8)+'" fill="#94a3b8" font-size="10" text-anchor="middle">Input Cost per 1M Tokens (USD)</text>';
  svg+='<text x="14" y="'+(pad.t+ch/2)+'" fill="#94a3b8" font-size="10" text-anchor="middle" transform="rotate(-90,14,'+(pad.t+ch/2)+')">Pass Rate</text>';

  plotModels.forEach(function(m){{
    var p=pricing[m];
    var cost=p.input_per_million;
    var rate=passRates[m]||0;
    var cx2=pad.l+cw*(cost/maxCost);
    var cy2=pad.t+ch-ch*rate;
    var tipHtml=esc(m)+'<br>Pass Rate: <b>'+pct(rate)+'</b><br>Input: <b>$'+cost.toFixed(2)+'</b>/1M<br>Output: <b>$'+(p.output_per_million||0).toFixed(2)+'</b>/1M<br>Cache Read: <b>$'+(p.cached_input_per_million||0).toFixed(2)+'</b>/1M';
    svg+='<circle cx="'+cx2+'" cy="'+cy2+'" r="5" fill="'+modelColor(m)+'" opacity=".85" style="cursor:pointer" ';
    svg+='onmouseover="showTip(event,&#39;'+tipHtml.replace(/'/g,"&#39;")+'&#39;)" onmouseout="hideTip()">';
    svg+='<title>'+esc(m)+': '+pct(rate)+' pass, $'+cost.toFixed(2)+'/1M input</title>';
    svg+='</circle>';
    svg+='<text x="'+(cx2+9)+'" y="'+(cy2+4)+'" fill="'+modelColorLight(m)+'" font-size="9" pointer-events="none">'+esc(m)+'</text>';
  }});

  svg+='</svg>';
  return svg;
}}

/* =================================================================
   EVENT HANDLERS
   ================================================================= */

window.setFilter=function(key,val){{
  if(key==="phase"){{ el("f-phase").value=val; }}
  if(key==="model"){{ el("f-model").value=val; }}
  if(key==="category"){{ el("f-category").value=val; }}
  if(key==="status"){{ el("f-status").value=val; }}
  applyFilters();
}};

window.toggleCase=function(cid){{
  state.expandedCases[cid]=!state.expandedCases[cid];
  var d=document.getElementById("cd-"+cid);
  if(d) d.classList.toggle("open");
  /* re-render to update arrow */
  render();
}};

window.selectRun=function(idx){{
  state.selectedRunIdx=idx;
  var runs=filteredRuns();
  var detail=el("run-detail");
  if(detail && idx>=0 && idx<runs.length){{
    detail.innerHTML=renderRunDetail(runs[idx]);
  }}
  /* highlight */
  document.querySelectorAll(".run-list-item").forEach(function(item,i){{
    item.classList.toggle("selected",i===idx);
  }});
}};

window.jumpToRun=function(runDir){{
  state.view="logs";
  var runs=filteredRuns();
  for(var i=0;i<runs.length;i++){{
    if(runs[i].run_dir===runDir){{ state.selectedRunIdx=i; break; }}
  }}
  updateHash();
  render();
}};

window.sortCosts=function(key){{
  if(state.costSortCol===key){{
    state.costSortDir=state.costSortDir*-1;
  }} else {{
    state.costSortCol=key;
    state.costSortDir=1;
  }}
  render();
}};

window.showTip=showTip;
window.hideTip=hideTip;

/* =================================================================
   INITIALIZATION
   ================================================================= */

function init(){{
  initFilters();
  loadHash();

  /* Nav click handlers */
  document.querySelectorAll(".nav-item").forEach(function(ni){{
    ni.addEventListener("click",function(){{
      state.view=this.getAttribute("data-view");
      state.selectedRunIdx=-1;
      updateHash();
      render();
    }});
  }});

  /* Filter change handlers */
  ["f-phase","f-model","f-category","f-status"].forEach(function(id){{
    el(id).addEventListener("change",applyFilters);
  }});
  el("f-search").addEventListener("input",applyFilters);
  el("f-hide-timeouts").addEventListener("change",applyFilters);
  el("btn-reset-filters").addEventListener("click",resetFilters);

  /* Initial render */
  render();

  console.log("DAAF Benchmark Results Viewer initialized");
  console.log("  Result sets:",DATA.result_sets.length);
  console.log("  Cases:",Object.keys(DATA.cases).length);
  console.log("  Runs:",DATA.runs.length);
  console.log("  Transcripts:",Object.keys(DATA.transcripts).length);
}}

init();

}})();
</script>

</body>
</html>"""

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
    result_sets = load_result_sets(results_dir, args.results)
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

    # Print summary
    print_summary(data_bundle)

    # Generate HTML
    html = generate_html(data_bundle)

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
