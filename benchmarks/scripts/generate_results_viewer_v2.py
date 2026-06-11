#!/usr/bin/env python3
"""
Generate a self-contained HTML viewer for DAAF benchmark results (v2).

Reads benchmark result sets from benchmarks/results/, loads case definitions
and per-set manifests, condenses transcripts, computes derived metrics
(per-model per-phase aggregates, composite scores and tier bands under both
the Perfect and Critical-only metrics, consistency, per-case difficulty,
callouts, published-pricing formulations with per-basis/per-metric
efficiency frontiers, estimated battery costs from observed token mixes
(see the "Battery-cost metric" dev guide above PHASE_MAP), per-model
timeout rates, provenance), and produces a single HTML file with all data
embedded.

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
#      (defined next to EVAL_GROUP_ORDER). The composite currently has five
#      approved components (P1, P2, P3a, P3b, P4 — user decision 2026-06-10,
#      superseding the original four-component pin; design record: README § 8);
#      adding a component changes leaderboard/tier semantics and requires explicit
#      user approval plus updates to the About-layer scoring prose in
#      viewer_template.html and README.md §§ 6/8. By default a new phase
#      stays OUT of the composite until that approval happens.
#   4. Template prose + JS registries: the About layer's "The benchmark
#      phases" collapsible in viewer_template.html enumerates phases in
#      hand-written prose — add an entry for the new phase. ALSO register the
#      phase in the template's JS lookup maps: GROUP_SHORT (~L939, short
#      labels), PD_EXPLAINERS (~L1762, deep-dive explainer prose), the
#      eval-group `order` array inside buildEvalGroups() (~L929) so the new
#      group sorts canonically instead of falling to the unordered tail, AND
#      the About-table case-count wiring: a `phaseSpan` entry (~L1252)
#      mapping the phase_id to an `ab-pX-cases` span id, plus the matching
#      table row in the "The benchmark phases" collapsible (~L514).
#      Omitting these caused the missing Phase 4 (skill_routing) explainer.
#      (Template edits, not handled in this script; line anchors drift as
#      the template evolves — grep for the identifier names.) Cost vs.
#      Performance bases and the Costs Detail phase scope are built
#      dynamically from the eval groups — no registration needed there.
#   5. Dataset dir: name datasets/<phase_id>/ to match the phase_id so
#      load_cases() attaches case definitions (it falls back to the dirname).
#   6. Regenerate and spot-check the new eval group's k/n in the sanity
#      report and the deep-dive heatmap before publishing.
#
# Public-prose registries in the template (maintenance guide, added v2.6.0
# with the public-audience evolution of the viewer):
#   - CRIT_LABELS (viewer_template.html JS, next to KNOWN_SCORER_CAVEATS):
#     maps snake_case criterion ids to plain-language labels used in headline
#     prose (hero verdict, deep-dive callouts and the global finding, the
#     leaderboard Dispatch tooltip). Forensic surfaces (run explorer, rotated
#     heatmap column headers) keep raw names; heatmap header tooltips append
#     the label. When a new criterion enters the corpus, add a label entry —
#     unlabeled criteria fall back to the snake_case name with underscores
#     replaced by spaces (critLabel()).
#   - Key Takeaways (#takeaways section in the template): DATED hand-written
#     editorial prose whose figures are injected into kt-* spans by
#     fillTakeaways() at init from PRECOMPUTED (composite, composite_hard,
#     per_model_phase, consistency, cost.battery — relative ratios only
#     since v2.8.1 — tier_rule, and
#     timeout_by_model built below). Injected numbers track the data
#     automatically; the qualitative claims do NOT — when the corpus changes
#     materially, rewrite the prose and update the date badge. Spans default
#     to an em dash, and a model absent from the corpus leaves its spans
#     dashed rather than erroring.
#   - Adding a new top-level prose section (the #takeaways recipe): section
#     scaffold in <main>, TOC link in nav#toc-rail, id in SECTION_IDS, and a
#     deliberate decision on the content-visibility CSS rule (above-the-fold
#     static sections stay out — see the CSS comment at the top of the
#     template); register in sectionRenderers only if JS-rendered.
#   - Substitution order in generate_html() is load-bearing: the small
#     controlled placeholders are filled first, __DATA_JSON__ last, so
#     transcript content can never be treated as a placeholder.
#
# Battery-cost metric (added v2.8.0, dev guide):
#   - New data dependency: benchmarks/derived/openrouter_reconciliation_*.json
#     (latest by filename), produced by scripts/reconcile_openrouter_costs.py
#     from an OpenRouter billing export. It supplies each OpenRouter model's
#     BILLED token mix (prompt/completion per covered run) — the harness's own
#     token counts are Anthropic-tokenizer approximations, not the billing
#     meter, and must not be used for OpenRouter dollar figures. If the file
#     is absent the generator warns and omits OpenRouter battery costs
#     (Anthropic battery costs still compute — fail soft, never fail build).
#   - Metric definition (uncached basis, user-approved 2026-06-11):
#     est_cost_per_run = (input_side x price_input + output_side x
#     price_output) / 1e6 at current models.yaml list rates with NO cache
#     discounts, using each model's own observed per-run token mix.
#     Anthropic input_side = input + cache_read + cache_creation tokens, all
#     at full input rate (uncached counterfactual), aggregated LIVE from
#     corpus result.json in load_runs(); OpenRouter input_side/output_side =
#     billed prompt/completion tokens per covered run from the reconciliation
#     JSON (reasoning tokens are included in completion). battery cost =
#     est_cost_per_run x battery_size, where battery_size = number of
#     distinct case_ids across the loaded corpus (51 on the 2026-06-11
#     corpus: 15 mc + 9 pc + 12 dc + 15 sr — NOT runs/reps, which are uneven
#     across providers).
#   - Staleness guard: the reconciliation JSON is a dated billing snapshot.
#     At generation time each OpenRouter model's current corpus run count is
#     compared against the JSON's recorded n_runs; mismatches print a console
#     WARNING (and set stale=true on the embedded entry) but never fail the
#     build. When OpenRouter runs are added to the corpus, re-run
#     reconcile_openrouter_costs.py with a fresh billing export.
#   - Embedding: PRECOMPUTED.cost.battery (per-model est_cost_per_run,
#     est_battery_cost, tokens_per_run, token/cost multipliers vs the
#     reference model, basis tag, staleness fields). "battery" is also a
#     price formulation on cost.models entries + cost.frontiers, so the Cost
#     vs. Performance scatter can use the relative battery cost as its x-axis
#     (template: COST_FORMS registry + renderCostsDetail battery table).
#     Per-model timed-out shares are NOT duplicated here — the template reads
#     them from PRECOMPUTED.timeout_by_model.
#   - Presentation (v2.8.1, user decision): all user-facing battery surfaces
#     (Costs Detail table, the Cost vs. Performance battery axis, the Key
#     Takeaways cost claims) display RELATIVE multipliers vs the reference
#     model (Opus 4.8 = 1.0x), never dollar amounts — exact dollars would
#     imply false precision. The embedded PRECOMPUTED values stay in dollars
#     (est_cost_per_run, est_battery_cost); the template normalizes at render
#     time (fmtMult, renderCostPerf batScale, renderCostsDetail multiplier
#     column, fillTakeaways battery ratios). The console battery table below
#     keeps dollars — it is a maintainer sanity surface, not user-facing.
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
    """Load all result.json files for each result set.

    Returns (runs, anth_token_totals). anth_token_totals aggregates raw
    token counts per Anthropic-provider model — {model: {n, input, output,
    cache_read, cache_creation}} — for the battery-cost metric (see the
    "Battery-cost metric" dev guide above PHASE_MAP). Aggregated here, in
    the same pass that reads every result.json, so per-run token counts
    still are NOT embedded in the data bundle (see the comment on the run
    dict below); only per-model means reach the viewer. Anthropic counts
    come from the provider's own usage meter, so they are billing-grade;
    OpenRouter counts are Anthropic-tokenizer approximations and are
    deliberately NOT aggregated here — OpenRouter battery costs come from
    the billing reconciliation JSON instead.
    """
    runs = []
    anth_token_totals = {}

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
                # Per-run computed cost and token counts are deliberately NOT
                # embedded: OpenRouter token accounting does not align with the
                # harness's usage logging (the Anthropic-compatible endpoint
                # reports Anthropic-tokenizer counts, not each model's own
                # billing meter), so token-derived dollar figures were
                # unreliable and all spend tracking was removed from the
                # viewer. Only published $/Mtok pricing is displayed.
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

            # Battery-cost token aggregation (Anthropic provider only; see
            # docstring). Timed-out runs zero their token fields, so they
            # are included in n and depress the mean — disclosed in the
            # viewer via timeout_by_model.
            if run["provider"] == "anthropic":
                agg = anth_token_totals.setdefault(run["model"], {
                    "n": 0, "input": 0, "output": 0,
                    "cache_read": 0, "cache_creation": 0,
                })
                agg["n"] += 1
                agg["input"] += result.get("input_tokens", 0) or 0
                agg["output"] += result.get("output_tokens", 0) or 0
                agg["cache_read"] += result.get("cache_read_tokens", 0) or 0
                agg["cache_creation"] += (
                    result.get("cache_creation_tokens", 0) or 0)

    return runs, anth_token_totals


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
        transcripts: dict keyed by "{result_set}/{run_dir}" -> condensed message list
        subagent_transcripts: dict keyed by "{result_set}/{run_dir}" -> dict of
            agent_id -> messages

    Keying (v2.7.0 fix): both dicts are namespaced by result set because run
    directory names (e.g. "dc-08_Gemma_4_26B_0") are only unique WITHIN a
    result set. Bare run_dir keys silently overwrote main transcripts across
    sets (last-loaded set won) and displayed another set's subagent transcript
    on same-named runs (482 colliding names / 1,339 transcript-bearing run
    instances on the 2026-06-11 52-set corpus; the composite keying recovered
    857 main transcripts that bare keys had been dropping). The template's
    lookups in renderRunDetail()
    mirror this composite key exactly (DATA.transcripts[r.result_set+"/"+
    r.run_dir]); the two sides must stay in lockstep.
    """
    transcripts = {}
    subagent_transcripts = {}

    for run in runs:
        ts = run["result_set"]
        run_dir = run["run_dir"]
        run_path = os.path.join(results_dir, ts, "runs", run_dir)
        # Composite key: run_dir alone collides across result sets (see
        # docstring) — must match the template's lookup key construction
        key = f"{ts}/{run_dir}"

        # Main transcript
        transcript_path = os.path.join(run_path, "transcript.jsonl")
        condensed = condense_transcript(transcript_path)
        if condensed:
            transcripts[key] = condensed

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
                subagent_transcripts[key] = agent_transcripts

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
# OpenRouter billing reconciliation loading (battery-cost metric)
# ---------------------------------------------------------------------------

def load_reconciliation(base_dir):
    """Load the latest OpenRouter billing reconciliation JSON, if present.

    Discovers benchmarks/derived/openrouter_reconciliation_*.json and takes
    the latest by filename (dated names sort chronologically). Supplies the
    BILLED per-run token mix for OpenRouter models — see the "Battery-cost
    metric" dev guide above PHASE_MAP. Fail-soft by design: a missing or
    unreadable file prints a WARNING and returns None, and the generator
    then omits OpenRouter battery costs rather than failing the build.

    Returns the parsed dict with two derived fields attached:
    "_snapshot_date" (parsed from the filename) and "_path".
    """
    import glob as _glob
    pattern = os.path.join(base_dir, "derived", "openrouter_reconciliation_*.json")
    candidates = sorted(_glob.glob(pattern))
    if not candidates:
        print("WARNING: no derived/openrouter_reconciliation_*.json found; "
              "OpenRouter battery costs will be omitted "
              "(run scripts/reconcile_openrouter_costs.py to produce one)",
              file=sys.stderr)
        return None
    path = candidates[-1]
    try:
        with open(path, "r") as f:
            recon = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"WARNING: could not read reconciliation JSON {path}: {exc}; "
              "OpenRouter battery costs will be omitted", file=sys.stderr)
        return None
    fname = os.path.basename(path)
    recon["_snapshot_date"] = (
        fname.replace("openrouter_reconciliation_", "").replace(".json", ""))
    recon["_path"] = path
    print(f"Reconciliation snapshot: {path} "
          f"(billing snapshot dated {recon['_snapshot_date']})")
    return recon


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
        "generator_version": "2.8.1",
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

# Composite scoring is PINNED to the five approved components (P1, P2, P3a,
# P3b, P4 — unweighted mean of Perfect rates). The original four-component
# pin (design record: README § 8, decision 1) was superseded by user decision
# 2026-06-10 adding skill_routing (P4); see README §§ 8/12.
# Future phases get their own labeled eval group, per_model_phase cells, and
# per-group callouts, but never enter the composite, tiers, or the global
# weakest-criterion callout unless they are deliberately added here (see
# "Adding a new benchmark phase" above PHASE_MAP — joining the composite
# changes leaderboard semantics and requires prose updates in
# viewer_template.html and README.md §§ 6/8). Models lacking runs for a
# component score the mean over their available components and carry a
# partial_data flag (disclosed in the leaderboard and hero verdict) —
# mirroring the cost-perf omitted-model disclosure pattern.
COMPOSITE_GIDS = [
    "mode_classification",
    "post_confirmation",
    "dispatch_compliance_dispatch",
    "dispatch_compliance_subagent",
    "skill_routing",
]

# Tier banding rule (mechanical and reproducible by design — see
# design record: README § 8, decision 2). Two deterministic stages:
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


def build_precomputed(result_sets, cases, runs, generation_params,
                      model_pricing=None, anth_token_totals=None,
                      reconciliation=None):
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
            hard_pass_count = 0
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
                # Hard-pass (leaderboard "Critical-only" metric) mirrors Perfect
                # but over hard-tier criteria only: at least one criterion
                # present AND every hard-tier criterion passed. A graded run
                # whose group has no hard-tier criteria passes vacuously, so
                # the hard-pass set always contains the perfect set
                # (hard_rate >= perfect_rate by construction).
                hard_run_ok = bool(crit)
                for name, entry in crit.items():
                    if not isinstance(entry, dict):
                        continue
                    tier = entry.get("tier")
                    if tier == "hard":
                        hard_total += 1
                        if entry.get("passed"):
                            hard_passed += 1
                        else:
                            hard_run_ok = False
                    elif tier == "soft":
                        soft_total += 1
                        if entry.get("passed"):
                            soft_passed += 1
                    if gid == "dispatch_compliance_dispatch" and name == "agent_dispatched":
                        dispatch_total += 1
                        if entry.get("passed"):
                            dispatch_passed += 1
                if hard_run_ok:
                    hard_pass_count += 1
            cell = {
                "n_runs": n_runs,
                "n_graded": n_graded,
                "perfect_count": perfect_count,
                "perfect_rate": rnd(perfect_count / n_runs),
                "hard_pass_count": hard_pass_count,
                "hard_rate": rnd(hard_pass_count / n_runs),
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
    # P1, P2, P3a, P3b, P4 are five equal components (user decision
    # 2026-06-10, superseding resolved decision 1's four-component pin) —
    # pinned via COMPOSITE_GIDS so non-composite eval groups never enter
    # scores, components, or partial-data flags.
    # Models missing a component get the mean over available components and a
    # partial_data flag, relative to the composite components present in this
    # corpus (components_missing likewise refers only to composite gids).
    corpus_components = [gid for gid in COMPOSITE_GIDS
                         if any(g["id"] == gid for g in groups)]

    def build_composite_from(rate_field):
        # Single code path shared by the Perfect metric
        # (rate_field="perfect_rate") and the Critical-only metric
        # (rate_field="hard_rate") so the composite construction cannot
        # drift between the two leaderboard metrics. Output shape is
        # identical for both.
        out = {}
        for model in models:
            comps = {}
            n_total = 0
            for gid in corpus_components:
                cell = per_model_phase.get(model, {}).get(gid)
                if cell is None:
                    continue
                comps[gid] = cell[rate_field]
                n_total += cell["n_runs"]
            if not comps:
                continue
            score = sum(comps.values()) / len(comps)
            out[model] = {
                "score": rnd(score),
                "components": comps,
                "components_present": list(comps.keys()),
                "components_missing": [gid for gid in corpus_components
                                       if gid not in comps],
                "n_total": n_total,
                "partial_data": len(comps) < len(corpus_components),
            }
        return out

    composite = build_composite_from("perfect_rate")
    composite_hard = build_composite_from("hard_rate")

    # --- tiers: mechanical banding on composite (gap rule + quartile fallback) ---
    # Factored into one helper so the IDENTICAL rule produces both the
    # Perfect-metric tiers and the Critical-only-metric tiers — the banding
    # logic cannot drift between the two leaderboard metrics.
    def compute_tiers_for(composite_dict):
        # Stage 1 (gap rule): sort by composite descending; start a new tier
        # where the gap to the previous model's composite is >=
        # TIER_GAP_THRESHOLD. Annotates entry["tier"] in place.
        ranked = sorted(composite_dict.items(),
                        key=lambda kv: (-kv[1]["score"], kv[0]))
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
        # TIER_FALLBACK_MIN_MODELS models, band instead by which quarter of
        # the composite range [min, max] each score falls in. Walking the
        # descending ranking, band indices are non-decreasing, so a band
        # change starts a new tier; empty bands are skipped and labels stay
        # contiguous.
        if len(ranked) >= TIER_FALLBACK_MIN_MODELS and len(tiers) < TIER_MIN_TIERS:
            hi = ranked[0][1]["score"]
            lo = ranked[-1][1]["score"]
            span = hi - lo
            if span > 0:
                tiers = []
                prev_band = None
                for model, entry in ranked:
                    # band 0 = top quarter of the range ... band 3 = bottom
                    band = min(3, int((hi - entry["score"]) / span * 4))
                    if prev_band is None or band != prev_band:
                        tiers.append({"label": "T" + str(len(tiers) + 1),
                                      "models": []})
                        prev_band = band
                    tiers[-1]["models"].append(model)
                    entry["tier"] = tiers[-1]["label"]
                tier_rule = {"method": "range_quartiles",
                             "gap_threshold": TIER_GAP_THRESHOLD}
        return tiers, tier_rule

    tiers, tier_rule = compute_tiers_for(composite)
    tiers_hard, tier_rule_hard = compute_tiers_for(composite_hard)

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

    # --- cost: published $/Mtok pricing formulations (NO observed spend) ---
    # Observed token-derived spend was removed entirely: OpenRouter token
    # accounting does not align with the harness's usage logging (the
    # Anthropic-compatible endpoint reports Anthropic-tokenizer counts, not
    # each model's own billing meter), so computed dollar figures were
    # unreliable. Instead, three published-pricing formulations are
    # precomputed per model from config/models.yaml rates:
    #   blend31 -- (3 x input + output) / 4 (Artificial Analysis convention)
    #   input   -- input $/Mtok
    #   output  -- output $/Mtok
    pricing = model_pricing or {}
    cost = {"models": [], "frontiers": {}}
    price_by_model = {}
    for model in models:
        p = pricing.get(model)
        if not p:
            continue
        inp = p.get("input_per_million")
        outp = p.get("output_per_million")
        if inp is None or outp is None:
            continue
        entry = {
            "key": model,
            "input": rnd(inp),
            "output": rnd(outp),
            "blend31": rnd((3 * inp + outp) / 4),
            # Filled by the battery block below (est. $ to run the full
            # battery once); None for models lacking battery data — the
            # frontier walk and the scatter both skip None prices.
            "battery": None,
        }
        cost["models"].append(entry)
        price_by_model[model] = entry

    # --- cost.battery: estimated cost per benchmark battery (v2.8.0) ---
    # Uncached basis (user-approved 2026-06-11): every token priced at the
    # current models.yaml list input/output rates with NO cache discounts,
    # using each model's own observed per-run token mix — directly comparable
    # across providers regardless of caching regime. Anthropic token mixes
    # are aggregated live from corpus result.json (anth_token_totals, billing-
    # grade usage meter; input side = input + cache_read + cache_creation,
    # ALL at full input rate — the uncached counterfactual). OpenRouter token
    # mixes come from the billing reconciliation snapshot (billed prompt /
    # completion per covered run; the harness's OpenRouter token counts are
    # tokenizer approximations and are never used for dollars). Full metric
    # definition + staleness-guard rationale: "Battery-cost metric" dev guide
    # above PHASE_MAP. Per-model timed-out shares live in timeout_by_model —
    # referenced by the template, not duplicated here.
    BATTERY_REFERENCE_MODEL = "Opus 4.8"
    battery_size = len(case_runs)  # distinct case_ids in the loaded corpus
    snapshot_date = (reconciliation or {}).get("_snapshot_date")
    battery_models = {}

    for model, agg in (anth_token_totals or {}).items():
        pm = price_by_model.get(model)
        n = agg.get("n", 0)
        if pm is None or n == 0:
            continue
        input_side = (agg["input"] + agg["cache_read"]
                      + agg["cache_creation"]) / n
        output_side = agg["output"] / n
        per_run = (input_side * pm["input"] + output_side * pm["output"]) / 1e6
        battery_models[model] = {
            "est_cost_per_run": rnd(per_run),
            "est_battery_cost": rnd(per_run * battery_size, 2),
            "tokens_per_run": round(input_side + output_side),
            "n_runs": n,
            "basis": "corpus-live",
        }

    if reconciliation:
        corpus_runs_by_model = {}
        for r in runs:
            corpus_runs_by_model[r["model"]] = \
                corpus_runs_by_model.get(r["model"], 0) + 1
        for model, rec in reconciliation.get("openrouter_models", {}).items():
            pm = price_by_model.get(model)
            n_cov = rec.get("n_covered_runs") or 0
            bt = rec.get("billed_tokens") or {}
            if pm is None or n_cov == 0:
                continue
            input_side = bt.get("prompt", 0) / n_cov
            output_side = bt.get("completion", 0) / n_cov
            per_run = (input_side * pm["input"]
                       + output_side * pm["output"]) / 1e6
            # Staleness guard: the snapshot's run universe vs the corpus
            # being embedded right now. WARN, never fail (dev guide).
            snapshot_n = rec.get("n_runs")
            corpus_n = corpus_runs_by_model.get(model, 0)
            stale = snapshot_n is not None and snapshot_n != corpus_n
            if stale:
                print(f"WARNING: battery-cost staleness — {model}: corpus has "
                      f"{corpus_n} runs but the billing snapshot "
                      f"({snapshot_date}) recorded {snapshot_n}; its token "
                      f"mix predates the newer runs. Re-run "
                      f"reconcile_openrouter_costs.py with a fresh billing "
                      f"export.", file=sys.stderr)
            battery_models[model] = {
                "est_cost_per_run": rnd(per_run),
                "est_battery_cost": rnd(per_run * battery_size, 2),
                "tokens_per_run": round(input_side + output_side),
                "n_runs": corpus_n,
                "basis": "billing-snapshot-" + (snapshot_date or "unknown"),
                "snapshot_n_runs": snapshot_n,
                "stale": stale,
            }

    ref_entry = battery_models.get(BATTERY_REFERENCE_MODEL)
    for model, b in battery_models.items():
        if ref_entry and ref_entry["tokens_per_run"]:
            b["token_multiplier_vs_ref"] = rnd(
                b["tokens_per_run"] / ref_entry["tokens_per_run"], 3)
        else:
            b["token_multiplier_vs_ref"] = None
        if ref_entry and ref_entry["est_cost_per_run"]:
            b["cost_multiplier_vs_ref"] = rnd(
                b["est_cost_per_run"] / ref_entry["est_cost_per_run"], 3)
        else:
            b["cost_multiplier_vs_ref"] = None
        pm = price_by_model.get(model)
        if pm is not None:
            pm["battery"] = b["est_battery_cost"]

    cost["battery"] = {
        "battery_size": battery_size,
        "reference_model": BATTERY_REFERENCE_MODEL,
        "snapshot_date": snapshot_date,
        "models": battery_models,
    }

    # --- cost-perf y-value matrix: perf_values[basis][metric][model] ---
    # Performance bases for the Cost vs. Performance scatter: "composite"
    # plus EVERY eval group gid — composite components (P1, P2, P3a, P3b)
    # AND non-composite groups (e.g., skill_routing/P4), so the scatter can
    # be filtered to any single phase group. Non-composite phases may have
    # partial model coverage mid-baseline; models lacking data for a basis
    # are simply absent from that basis's dict, and the template omits them
    # from that view and footnotes the count — partial-coverage frontiers
    # are disclosed, never silent. Metrics: "perfect" (all criteria pass)
    # and "hard" (all hard-tier criteria pass).
    perf_bases = ["composite"] + [g["id"] for g in groups]
    comp_by_metric = {"perfect": composite, "hard": composite_hard}
    rate_field_by_metric = {"perfect": "perfect_rate", "hard": "hard_rate"}
    perf_values = {}
    for basis in perf_bases:
        perf_values[basis] = {}
        for metric in ("perfect", "hard"):
            vals = {}
            for model in models:
                if basis == "composite":
                    comp_entry = comp_by_metric[metric].get(model)
                    if comp_entry is None:
                        continue
                    vals[model] = comp_entry["score"]
                else:
                    cell = per_model_phase.get(model, {}).get(basis)
                    if cell is None:
                        continue
                    vals[model] = cell[rate_field_by_metric[metric]]
            perf_values[basis][metric] = vals
    cost["perf_values"] = perf_values

    # --- efficiency frontiers: Pareto set on (price asc, score desc) ---
    # One frontier per (price formulation x perf basis x metric) combination,
    # keyed frontiers[price_form][perf_basis][metric], over models that have
    # both a published price and a score under that basis/metric. Walking
    # points sorted by (price asc, score desc, name asc) and keeping strict
    # score improvements yields the frontier staircase deterministically: a
    # model is kept iff no cheaper-or-equal model has an equal-or-higher
    # score. Precomputed here (not in JS) so the scatter annotation, the
    # section prose, and the sanity report cannot drift.
    # "battery" joined as a fourth price formulation (v2.8.0) so the Cost vs.
    # Performance scatter can plot est. $ per battery; models without battery
    # data carry battery=None and are skipped by the None/<=0 guard below.
    for form in ("blend31", "input", "output", "battery"):
        cost["frontiers"][form] = {}
        for basis in perf_bases:
            cost["frontiers"][form][basis] = {}
            for metric in ("perfect", "hard"):
                frontier_pts = []
                for model, score_val in perf_values[basis][metric].items():
                    pm = price_by_model.get(model)
                    if pm is None:
                        continue
                    price = pm[form]
                    if price is None or price <= 0:
                        continue
                    frontier_pts.append((price, -score_val, model))
                frontier_pts.sort()
                frontier = []
                best_score = None
                for price, neg_score, model in frontier_pts:
                    score = -neg_score
                    if best_score is None or score > best_score:
                        frontier.append({
                            "model": model,
                            "price": price,
                            "score": score,
                        })
                        best_score = score
                cost["frontiers"][form][basis][metric] = frontier

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

    # --- timeout_by_model: per-model timed-out run rates ---
    # Basis: the harness's explicit timed_out flag over ALL of a model's
    # loaded runs (all phases pooled). This flag covers genuine wall-clock
    # timeouts AND silent stalls that ran out the clock — a broader measure
    # than any transcript-level stall forensics (e.g., README's silent-stall
    # figures); prose citing these rates must name this basis. Precomputed
    # here (not hand-copied) so the Key Takeaways section's reliability
    # claims cannot drift from the data.
    timeout_by_model = {}
    for model in models:
        mruns = [r for r in runs if r["model"] == model]
        n_to = sum(1 for r in mruns if r["timed_out"])
        timeout_by_model[model] = {
            "n_runs": len(mruns),
            "n_timed_out": n_to,
            "rate": rnd(n_to / len(mruns)) if mruns else None,
        }

    # --- totals ---
    totals = {
        "total_runs": len(runs),
        "n_models": len(models),
        "n_cases": len(case_runs),
        "n_result_sets": len(result_sets),
        "n_timed_out": sum(1 for r in runs if r["timed_out"]),
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
        "composite_hard": composite_hard,
        "tiers": tiers,
        "tiers_hard": tiers_hard,
        "tier_rule": tier_rule,
        "tier_rule_hard": tier_rule_hard,
        "consistency": consistency,
        "per_case": per_case,
        "callouts": callouts,
        "cost": cost,
        "timeout_by_model": timeout_by_model,
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
    rule_h = precomputed.get("tier_rule_hard", {})
    print(f"  Critical-metric tier rule: {rule_h.get('method', '?')} -> "
          f"{len(precomputed.get('tiers_hard', []))} tiers over "
          f"{len(precomputed.get('composite_hard', {}))} models")
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

    print("  Efficiency frontier, blended 3:1 pricing, composite/perfect "
          "(price asc | model | $/Mtok | score):")
    blend_frontiers = precomputed["cost"].get("frontiers", {}).get("blend31", {})
    for pt in blend_frontiers.get("composite", {}).get("perfect", []):
        print(f"    {pt['model']:<22} | ${pt['price']:.2f}/Mtok | "
              f"{pt['score']:.3f}")
    print()

    battery = precomputed["cost"].get("battery") or {}
    bat_models = battery.get("models") or {}
    if bat_models:
        print(f"  Estimated cost per benchmark battery "
              f"({battery.get('battery_size')} probes; uncached basis, "
              f"current list rates; x vs {battery.get('reference_model')}):")
        ranked_bat = sorted(bat_models.items(),
                            key=lambda kv: -(kv[1]["est_battery_cost"] or 0))
        for model, b in ranked_bat:
            mult = b.get("cost_multiplier_vs_ref")
            mult_s = f"{mult:5.2f}x" if mult is not None else "    -"
            stale_s = " [STALE snapshot]" if b.get("stale") else ""
            print(f"    {model:<22} | ${b['est_battery_cost']:8.2f} | "
                  f"{mult_s} | {b['basis']}{stale_s}")
        print()

    totals = precomputed["totals"]
    n_disc = sum(1 for p in precomputed["provenance"] if p["run_count_discrepancy"])
    gw = precomputed["callouts"]["global_weakest"]
    print(f"  Total runs: {totals['total_runs']} "
          f"({totals['n_timed_out']} timed out) | "
          f"models: {totals['n_models']} | cases: {totals['n_cases']} | "
          f"sets: {totals['n_result_sets']} ({n_disc} with run-count discrepancy)")
    print(f"  Pricing loaded for {len(precomputed['cost'].get('models', []))} models "
          f"(published $/Mtok; observed spend tracking removed)")
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
    runs, anth_token_totals = load_runs(results_dir, result_sets, cases)

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
    reconciliation = load_reconciliation(base_dir)

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
    precomputed = build_precomputed(result_sets, cases, runs, generation_params,
                                    model_pricing=model_pricing,
                                    anth_token_totals=anth_token_totals,
                                    reconciliation=reconciliation)

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
