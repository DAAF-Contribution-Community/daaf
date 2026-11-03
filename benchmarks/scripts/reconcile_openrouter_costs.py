#!/usr/bin/env python3
"""Reconcile the OpenRouter billing export against the benchmark results corpus.

Phase A (feasibility + calibration) of observed-cost integration:
  1. Build per-run time windows from transcript.jsonl timestamps
     (end = last stamped line; start = end - duration_s, because transcripts
     are seeded with fixture history whose first-line timestamps predate the
     run -- identical fixture stamps appear across unrelated sessions).
  2. Attribute billing rows to (model, run window) and report coverage.
  3. Calibrate harness computed_cost_usd vs billed cost_total per model.
  4. Summarize Anthropic per-run cost/tokens from result.json (incl. Fable
     thinking-token concealment check).
  5. Prototype "token hunger" multipliers vs Opus 4.8 and the corpus median,
     plus a published-blend-predicted cost decomposition.

Corpus inclusion matches generate_results_viewer_v2.py: every directory in
benchmarks/results/ (non-dot) containing summary.json; runs are run dirs with
a result.json. The latest viewer generation used no --exclude-results, so no
set-level exclusions are applied here.

Usage:
    python3 benchmarks/scripts/reconcile_openrouter_costs.py \
        [--csv PATH] [--tolerance-s 120] [--output PATH]

Prints a full report to stdout and writes a machine-readable JSON summary
(default: benchmarks/derived/openrouter_reconciliation_{TODAY}.json — dated at
run time so a rerun never overwrites a prior dated snapshot).
"""

import argparse
import csv
import json
import os
import re
import statistics
import sys
from datetime import datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
MODELS_YAML = os.path.join(BASE_DIR, "config", "models.yaml")
DEFAULT_CSV = os.path.join(BASE_DIR, "openrouter_activity_2026-06-11.csv")
# Default output is dated with TODAY's date so successive reconciliations never
# overwrite a prior dated snapshot (2026-08-10: the former hardcoded
# ..._2026-06-11.json default silently clobbered the June historical file).
DEFAULT_OUT = os.path.join(
    BASE_DIR, "derived",
    "openrouter_reconciliation_%s.json"
    % datetime.now(timezone.utc).strftime("%Y-%m-%d"))

# Known non-benchmark spend on this API key (user-confirmed):
#   - anthropic/* rows (probe tests)
#   - early GLM 5.1 preliminary tests are detected dynamically: GLM rows
#     timestamped before the first GLM corpus run window are flagged
#     "pre-campaign" and excluded from calibration.
#   - gemini-3.5-flash preliminary testing is likewise handled dynamically
#     (see below), NOT by a static base-slug exclusion.
#
# 2026-08-11: the former static exclusion of google/gemini-3.5-flash was
# REMOVED. It became a REGISTERED campaign model on 2026-07-27 (see
# config/models.yaml) and now has corpus runs; blanket-excluding it silently
# dropped its billed spend from the reconciliation snapshot (and thus from the
# viewer's battery-cost table). Its genuine pre-registration prelim spend is
# already caught by the dynamic pre-campaign detector (rows before the first
# corpus run window), so no static exclusion is needed.
EXCLUDED_SLUG_PREFIXES = ("anthropic/",)
EXCLUDED_BASE_SLUGS = ()

# Permaslug -> registry-base-slug overrides for the "dated-slug gotcha"
# (README § Billing reconciliation pipeline > "Dated-slug gotcha"): OpenRouter
# billing permaslugs carry a full-date suffix (`...-20260731`) while the
# registry (config/models.yaml) uses a short-form slug (`...-0731`). The generic
# `-20YYMMDD$` strip in base_slug_from_permaslug() would map the dated permaslug
# onto the undated base, which (a) matches no active registry entry for a
# short-form model and (b) collides with the retired undated revision's own
# permaslug. Each dated model therefore needs an explicit override so its billed
# rows attribute to the correct models.yaml entry.
# 2026-08-11: DeepSeek V4 Flash 0731 — billing permaslug
# `deepseek/deepseek-v4-flash-20260731` must map to registry base
# `deepseek/deepseek-v4-flash-0731` (the generic strip yields
# `deepseek/deepseek-v4-flash`, which matches no active entry — the undated
# Flash was retired 2026-08-02 — and would collide with the retired revision's
# permaslug `deepseek/deepseek-v4-flash-20260423`).
# 2026-08-12: DeepSeek V4 Pro 0813 — billing permaslug
# `deepseek/deepseek-v4-pro-20260813` must map to registry base
# `deepseek/deepseek-v4-pro-0813`. Sharper failure mode than the Flash case:
# the generic strip yields `deepseek/deepseek-v4-pro`, which IS an active
# registry entry (the undated Pro was deliberately kept for side-by-side
# comparison), so without this override the 0813 revision's billed rows
# silently attribute to the undated Pro and contaminate a live model's
# calibration ratio (observed 2026-08-12: 1,082 rows misattributed before
# this override landed).
PERMASLUG_BASE_OVERRIDES = {
    "deepseek/deepseek-v4-flash-20260731": "deepseek/deepseek-v4-flash-0731",
    "deepseek/deepseek-v4-pro-20260813": "deepseek/deepseek-v4-pro-0813",
}

REFERENCE_MODEL = "Opus 4.8"  # hunger-multiplier reference


# ---------------------------------------------------------------------------
# Model config
# ---------------------------------------------------------------------------

def load_models(path):
    """Parse models.yaml -> list of {id, name, provider, pricing}.

    Uses PyYAML when available; otherwise a minimal line parser sufficient
    for this file's flat structure.
    """
    try:
        import yaml
        with open(path) as f:
            doc = yaml.safe_load(f)
        return doc["models"]
    except ImportError:
        models = []
        cur = None
        in_pricing = False
        with open(path) as f:
            for raw in f:
                line = raw.rstrip("\n")
                stripped = line.strip()
                if stripped.startswith("#") or not stripped:
                    continue
                if stripped.startswith("- id:"):
                    cur = {"pricing": {}}
                    models.append(cur)
                    cur["id"] = stripped.split(":", 1)[1].strip().strip('"')
                    in_pricing = False
                elif cur is not None:
                    if stripped.startswith("pricing:"):
                        in_pricing = True
                    elif in_pricing and ":" in stripped:
                        k, v = stripped.split(":", 1)
                        try:
                            cur["pricing"][k.strip()] = float(v.strip())
                        except ValueError:
                            in_pricing = False
                    if stripped.startswith("name:"):
                        cur["name"] = stripped.split(":", 1)[1].strip().strip('"')
                        in_pricing = False
                    elif stripped.startswith("provider:"):
                        cur["provider"] = stripped.split(":", 1)[1].strip()
                        in_pricing = False
        return models


def base_slug_from_model_id(model_id):
    """Corpus model_id -> base slug ('z-ai/glm-5.1:atlas-cloud/fp8' -> 'z-ai/glm-5.1')."""
    return model_id.split(":", 1)[0]


def base_slug_from_permaslug(slug):
    """CSV model_permaslug -> base slug ('z-ai/glm-5.1-20260406' -> 'z-ai/glm-5.1').

    Dated-slug overrides (see PERMASLUG_BASE_OVERRIDES) win over the generic
    date-strip so short-form registry revisions (e.g. `-0731`) attribute
    correctly instead of collapsing onto the undated base.
    """
    if slug in PERMASLUG_BASE_OVERRIDES:
        return PERMASLUG_BASE_OVERRIDES[slug]
    return re.sub(r"-20\d{6}$", "", slug)


# ---------------------------------------------------------------------------
# Corpus loading
# ---------------------------------------------------------------------------

def discover_set_dirs(results_dir):
    """Replicate the viewer's set inclusion rule (summary.json present)."""
    included, excluded = [], []
    for d in sorted(os.listdir(results_dir)):
        p = os.path.join(results_dir, d)
        if not os.path.isdir(p) or d.startswith("."):
            continue
        if os.path.isfile(os.path.join(p, "summary.json")):
            included.append(d)
        else:
            excluded.append(d)
    return included, excluded


def transcript_end_timestamp(path):
    """Last top-level 'timestamp' in a transcript.jsonl, parsing from the end.

    Transcripts are seeded with fixture history, so the FIRST timestamps can
    predate the run by days; the LAST stamped line is the true session end.
    """
    try:
        with open(path, "rb") as f:
            lines = f.read().splitlines()
    except OSError:
        return None
    for raw in reversed(lines):
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        ts = obj.get("timestamp")
        if ts:
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                continue
    return None


def load_corpus_runs(set_dirs):
    """Load every run's result.json + derived [start, end] window (UTC)."""
    runs = []
    window_sources = {"transcript": 0, "mtime_fallback": 0, "none": 0}
    for ts_dir in set_dirs:
        runs_dir = os.path.join(RESULTS_DIR, ts_dir, "runs")
        if not os.path.isdir(runs_dir):
            continue
        for run_dirname in sorted(os.listdir(runs_dir)):
            rp = os.path.join(runs_dir, run_dirname, "result.json")
            if not os.path.isfile(rp):
                continue
            with open(rp) as f:
                r = json.load(f)
            duration = float(r.get("duration_s") or 0.0)
            end = transcript_end_timestamp(
                os.path.join(runs_dir, run_dirname, "transcript.jsonl"))
            if end is not None:
                source = "transcript"
            else:
                # Fallback: result.json mtime ~ run completion. Unreliable
                # for rescored/copied sets; counted and reported.
                end = datetime.fromtimestamp(os.path.getmtime(rp),
                                             tz=timezone.utc)
                source = "mtime_fallback"
            window_sources[source] += 1
            start = end - timedelta(seconds=duration) if end else None
            runs.append({
                "set": ts_dir,
                "run_dir": run_dirname,
                "case_id": r.get("case_id", ""),
                "model": r.get("model", ""),
                "model_id": r.get("model_id", ""),
                "provider": r.get("provider", ""),
                "computed_cost_usd": float(r.get("computed_cost_usd") or 0.0),
                "input_tokens": int(r.get("input_tokens") or 0),
                "output_tokens": int(r.get("output_tokens") or 0),
                "cache_read_tokens": int(r.get("cache_read_tokens") or 0),
                "cache_creation_tokens": int(r.get("cache_creation_tokens") or 0),
                "duration_s": duration,
                "turns": r.get("turns", 0),
                "error": r.get("error"),
                "timed_out": bool(r.get("timed_out", False)),
                "start": start,
                "end": end,
                "window_source": source,
            })
    return runs, window_sources


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------

def fnum(v):
    return float(v) if v not in (None, "") else 0.0


def fint(v):
    return int(v) if v not in (None, "") else 0


def assistant_char_volume(path):
    """Total characters of assistant-message content in a transcript.

    Used for the Fable thinking-token check: if a model's logged
    output_tokens include concealed (non-displayed) reasoning, its visible
    chars-per-output-token will be markedly lower than sibling models.
    """
    total = 0
    try:
        with open(path) as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") != "assistant":
                    continue
                msg = obj.get("message") or {}
                total += len(json.dumps(msg.get("content", "")))
    except OSError:
        pass
    return total


def load_csv_rows(path):
    """Load billing rows; created_at parsed as UTC (verified empirically)."""
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            ts_raw = r["created_at"]
            fmt = "%Y-%m-%d %H:%M:%S.%f" if "." in ts_raw else "%Y-%m-%d %H:%M:%S"
            created = datetime.strptime(ts_raw, fmt).replace(tzinfo=timezone.utc)
            rows.append({
                "created_at": created,
                "cost_total": fnum(r["cost_total"]),
                "cost_cache": fnum(r["cost_cache"]),
                "tokens_prompt": fint(r["tokens_prompt"]),
                "tokens_completion": fint(r["tokens_completion"]),
                "tokens_reasoning": fint(r["tokens_reasoning"]),
                "tokens_cached": fint(r["tokens_cached"]),
                "permaslug": r["model_permaslug"],
                "base_slug": base_slug_from_permaslug(r["model_permaslug"]),
                "cancelled": r["cancelled"] == "true",
                "finish_reason": r["finish_reason_normalized"],
            })
    return rows


# ---------------------------------------------------------------------------
# Timezone offset verification
# ---------------------------------------------------------------------------

def verify_tz_offset(rows, runs, base_slug, tol_s):
    """Attribution-rate-by-candidate-offset scan for one model.

    If CSV created_at is UTC (assumed), offset 0 should maximize the share of
    that model's rows landing inside run windows.
    """
    model_rows = [r for r in rows if r["base_slug"] == base_slug]
    model_runs = [r for r in runs
                  if base_slug_from_model_id(r["model_id"]) == base_slug
                  and r["start"] is not None]
    windows = [(r["start"] - timedelta(seconds=tol_s),
                r["end"] + timedelta(seconds=tol_s)) for r in model_runs]
    results = {}
    for off_h in range(-12, 13):
        off = timedelta(hours=off_h)
        hits = sum(1 for row in model_rows
                   if any(lo <= row["created_at"] + off <= hi
                          for lo, hi in windows))
        results[off_h] = hits / len(model_rows) if model_rows else 0.0
    best = max(results, key=lambda k: results[k])
    return best, results


# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------

def attribute_rows(rows, runs, tol_s):
    """Assign billing rows to same-model run windows (+/- tolerance).

    Returns per-row match info: list of matching run indices (model-level
    attribution counts a row matched if >= 1 window contains it; rows
    matching exactly one window also get run-level attribution).
    """
    tol = timedelta(seconds=tol_s)
    runs_by_base = {}
    for i, r in enumerate(runs):
        if r["provider"] != "openrouter" or r["start"] is None:
            continue
        # Timed-out runs carry no gradeable signal and are excluded from every
        # display surface, so their billing must never enter the attributed
        # token/cost pools that feed the battery-cost basis. On the 2026-08-21
        # corpus this exclusion is a numeric no-op (every timed-out run is a
        # 0-turn fixture-stalled record whose window is already stripped, so
        # it captures zero rows — verified 2026-08-21, scoping probe), but a
        # future timed-out run WITH real turns would have a live transcript
        # window and would silently leak billing into the basis. This guard
        # makes the clean-set invariant structural instead of emergent.
        if r.get("timed_out"):
            continue
        runs_by_base.setdefault(
            base_slug_from_model_id(r["model_id"]), []).append(i)

    for row in rows:
        row["matched_runs"] = []
        idxs = runs_by_base.get(row["base_slug"], [])
        t = row["created_at"]
        for i in idxs:
            if runs[i]["start"] - tol <= t <= runs[i]["end"] + tol:
                row["matched_runs"].append(i)
    return runs_by_base


def cluster_times(times, gap_s=600):
    """Group sorted datetimes into clusters separated by > gap_s."""
    if not times:
        return []
    times = sorted(times)
    clusters = [[times[0]]]
    for t in times[1:]:
        if (t - clusters[-1][-1]).total_seconds() > gap_s:
            clusters.append([t])
        else:
            clusters[-1].append(t)
    return clusters


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------

def fmt_money(x):
    return f"${x:,.2f}"


def per_mtok(cost, tokens):
    return cost / tokens * 1e6 if tokens else 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", default=DEFAULT_CSV)
    ap.add_argument("--tolerance-s", type=int, default=120,
                    help="Window tolerance in seconds (default 120: covers "
                         "billing-meter clock skew plus generations that "
                         "complete after the final transcript stamp; "
                         "generation_time_ms reaches ~100s in the export)")
    ap.add_argument("--output", default=DEFAULT_OUT)
    args = ap.parse_args()

    models = load_models(MODELS_YAML)
    by_base = {}
    by_name = {}
    for m in models:
        by_name[m["name"]] = m
        if m.get("provider") == "openrouter":
            by_base[base_slug_from_model_id(m["id"])] = m

    # --- corpus ---
    set_dirs, excluded_dirs = discover_set_dirs(RESULTS_DIR)
    print(f"Corpus inclusion rule (matches viewer): dirs with summary.json")
    print(f"  included sets: {len(set_dirs)}   excluded (no summary.json): "
          f"{excluded_dirs or 'none'}")
    runs, window_sources = load_corpus_runs(set_dirs)
    print(f"  runs loaded: {len(runs)}   window sources: {window_sources}")

    # Stalled runs (0 turns + error) never issued a model request; their
    # transcripts contain only seeded fixture history, so the derived window
    # reflects the FIXTURE's recording time, not the run. Strip their windows
    # so they cannot capture billing rows or distort the campaign start.
    fixture_only = 0
    for r in runs:
        if r["turns"] == 0 and r["error"]:
            r["start"] = r["end"] = None
            r["window_source"] = "fixture_only_stalled"
            fixture_only += 1
    print(f"  stalled fixture-only windows stripped: {fixture_only}")

    or_runs = [r for r in runs if r["provider"] == "openrouter"]
    an_runs = [r for r in runs if r["provider"] == "anthropic"]
    print(f"  openrouter runs: {len(or_runs)}   anthropic runs: {len(an_runs)}")

    # --- billing rows ---
    rows = load_csv_rows(args.csv)
    span = (min(r["created_at"] for r in rows),
            max(r["created_at"] for r in rows))
    print(f"\nBilling rows: {len(rows)}   span: {span[0]} .. {span[1]} "
          f"(parsed as UTC)")

    # Static exclusions (user-confirmed non-benchmark spend)
    def is_static_excluded(row):
        return (row["base_slug"] in EXCLUDED_BASE_SLUGS
                or row["base_slug"].startswith(EXCLUDED_SLUG_PREFIXES))

    static_excl = [r for r in rows if is_static_excluded(r)]
    work_rows = [r for r in rows if not is_static_excluded(r)]
    print(f"Static exclusions: {len(static_excl)} rows, "
          f"{fmt_money(sum(r['cost_total'] for r in static_excl))} "
          f"(anthropic probes; gemini-3.5-flash prelim now handled dynamically)")

    unknown = sorted({r["base_slug"] for r in work_rows} - set(by_base))
    if unknown:
        print(f"WARNING: CSV slugs with no corpus model: {unknown}")

    # --- timezone verification ---
    tz_slug = "google/gemini-3.1-pro-preview"
    best_off, scan = verify_tz_offset(work_rows, runs, tz_slug,
                                      args.tolerance_s)
    print(f"\nTimezone scan ({tz_slug}, hourly offsets -12..+12):")
    top = sorted(scan.items(), key=lambda kv: -kv[1])[:3]
    for off, frac in top:
        print(f"  offset {off:+d}h -> {frac:.1%} rows attributed")
    print(f"  best offset: {best_off:+d}h "
          f"({'UTC assumption CONFIRMED' if best_off == 0 else 'UNEXPECTED'})")

    # --- attribution ---
    attribute_rows(work_rows, runs, args.tolerance_s)

    # Pre-campaign detection: the benchmark campaign begins with the first
    # corpus run window (first set 20260608_214251). Unmatched rows before
    # that point are preliminary testing (user-confirmed: early GLM 5.1
    # prelim runs; same logic covers the other models' prelim spend in the
    # 06-08 16:26-20:10 clusters, all of which predate the first set).
    campaign_start = min(r["start"] for r in or_runs if r["start"])
    dyn_excl = []
    for row in work_rows:
        if (not row["matched_runs"]
                and row["created_at"] < campaign_start
                - timedelta(seconds=args.tolerance_s)):
            row["pre_campaign"] = True
            dyn_excl.append(row)
    by_slug_excl = {}
    for r in dyn_excl:
        s = r["base_slug"].split("/")[-1]
        by_slug_excl.setdefault(s, [0, 0.0])
        by_slug_excl[s][0] += 1
        by_slug_excl[s][1] += r["cost_total"]
    print(f"\nPre-campaign rows (unmatched, before first corpus run window "
          f"{campaign_start}): {len(dyn_excl)} rows, "
          f"{fmt_money(sum(r['cost_total'] for r in dyn_excl))}")
    for s, (n, c) in sorted(by_slug_excl.items(), key=lambda kv: -kv[1][1]):
        print(f"    {s:<30} {n:>5} rows  ${c:>7.2f}")

    # --- per-model attribution & calibration ---
    print("\n" + "=" * 100)
    print("ATTRIBUTION COVERAGE + CALIBRATION (per OpenRouter model)")
    print("=" * 100)
    header = (f"{'Model':<20} {'rows':>6} {'attr%':>7} {'$total':>9} "
              f"{'attr$%':>7} {'billed$':>9} {'harness$':>9} {'ratio':>7} "
              f"{'real$/Mtok':>10}")
    print(header)
    print("-" * len(header))

    model_summaries = {}
    orphan_all = []
    for base, mcfg in sorted(by_base.items(), key=lambda kv: kv[1]["name"]):
        mrows = [r for r in work_rows if r["base_slug"] == base
                 and not r.get("pre_campaign")]
        attr = [r for r in mrows if r["matched_runs"]]
        orph = [r for r in mrows if not r["matched_runs"]]
        orphan_all.extend(orph)
        if not mrows:
            continue
        tot_cost = sum(r["cost_total"] for r in mrows)
        attr_cost = sum(r["cost_total"] for r in attr)

        # Harness side: runs of this model that received >= 1 attributed row
        covered_idx = sorted({i for r in attr for i in r["matched_runs"]})
        covered = [runs[i] for i in covered_idx]
        m_all_runs = [r for r in or_runs
                      if base_slug_from_model_id(r["model_id"]) == base]
        harness_cost_cov = sum(r["computed_cost_usd"] for r in covered)
        harness_cost_all = sum(r["computed_cost_usd"] for r in m_all_runs)

        b_prompt = sum(r["tokens_prompt"] for r in attr)
        b_compl = sum(r["tokens_completion"] for r in attr)
        b_reason = sum(r["tokens_reasoning"] for r in attr)
        b_cached = sum(r["tokens_cached"] for r in attr)
        b_total = b_prompt + b_compl  # reasoning is a subset of completion
        h_in = sum(r["input_tokens"] for r in covered)
        h_out = sum(r["output_tokens"] for r in covered)
        h_cr = sum(r["cache_read_tokens"] for r in covered)
        h_cc = sum(r["cache_creation_tokens"] for r in covered)

        ratio = attr_cost / harness_cost_cov if harness_cost_cov else 0.0
        realized = per_mtok(attr_cost, b_total)
        n_run = len(m_all_runs)
        n_cov = len(covered)
        n_to = sum(1 for r in m_all_runs if r["timed_out"])

        # Published-blend-predicted cost from the model's own billed mix
        pr = mcfg["pricing"]
        pred_cost = (b_prompt * pr["input"] + b_compl * pr["output"]) / 1e6

        # Run-level (unambiguous) billed costs for timeout split
        run_billed = {}
        for r in attr:
            if len(r["matched_runs"]) == 1:
                run_billed.setdefault(r["matched_runs"][0], 0.0)
                run_billed[r["matched_runs"][0]] += r["cost_total"]
        unamb_rows = sum(1 for r in attr if len(r["matched_runs"]) == 1)
        nto_billed = [c for i, c in run_billed.items()
                      if not runs[i]["timed_out"]]

        print(f"{mcfg['name']:<20} {len(mrows):>6} "
              f"{len(attr)/len(mrows):>6.1%} {tot_cost:>9.2f} "
              f"{attr_cost/tot_cost if tot_cost else 0:>6.1%} "
              f"{attr_cost:>9.2f} {harness_cost_cov:>9.2f} {ratio:>7.2f} "
              f"{realized:>10.2f}")

        model_summaries[mcfg["name"]] = {
            "base_slug": base,
            "csv_rows": len(mrows),
            "rows_attributed": len(attr),
            "rows_attributed_pct": len(attr) / len(mrows) if mrows else 0,
            "csv_cost_total": tot_cost,
            "billed_cost_attributed": attr_cost,
            "billed_cost_attributed_pct": attr_cost / tot_cost if tot_cost else 0,
            "harness_cost_covered_runs": harness_cost_cov,
            "harness_cost_all_runs": harness_cost_all,
            "billed_over_harness_ratio": ratio,
            "billed_tokens": {"prompt": b_prompt, "completion": b_compl,
                              "reasoning": b_reason, "cached": b_cached,
                              "total": b_total},
            "harness_tokens": {"input": h_in, "output": h_out,
                               "cache_read": h_cr, "cache_creation": h_cc,
                               "total": h_in + h_out + h_cr + h_cc},
            "realized_usd_per_mtok": realized,
            "published_blend_predicted_cost": pred_cost,
            "n_runs": n_run, "n_covered_runs": n_cov, "n_timed_out": n_to,
            "billed_cost_per_covered_run": attr_cost / n_cov if n_cov else 0,
            "billed_cost_per_run_all": attr_cost / n_run if n_run else 0,
            "billed_tokens_per_covered_run": b_total / n_cov if n_cov else 0,
            "unambiguous_rows": unamb_rows,
            "unambiguous_rows_pct": unamb_rows / len(attr) if attr else 0,
            "billed_cost_per_run_nontimeout_unambiguous":
                statistics.mean(nto_billed) if nto_billed else None,
            "n_unambiguous_nontimeout_runs": len(nto_billed),
        }

    # --- orphan characterization ---
    print(f"\nOrphan (unattributed, post-campaign) rows: {len(orphan_all)}, "
          f"{fmt_money(sum(r['cost_total'] for r in orphan_all))}")
    orphan_clusters = []
    for cl in cluster_times([r["created_at"] for r in orphan_all]):
        lo, hi = cl[0], cl[-1]
        cl_rows = [r for r in orphan_all if lo <= r["created_at"] <= hi]
        cost = sum(r["cost_total"] for r in cl_rows)
        slugs = sorted({r["base_slug"].split("/")[-1] for r in cl_rows})
        orphan_clusters.append({
            "start": lo.isoformat(), "end": hi.isoformat(),
            "rows": len(cl_rows), "cost": round(cost, 2), "models": slugs})
    big = sorted(orphan_clusters, key=lambda c: -c["cost"])[:12]
    for c in big:
        print(f"  {c['start'][:19]} .. {c['end'][11:19]}  rows={c['rows']:>4} "
              f"cost=${c['cost']:>7.2f}  models={','.join(c['models'])}")

    # --- Anthropic per-run table + Fable check ---
    print("\n" + "=" * 100)
    print("ANTHROPIC PER-RUN COST/TOKENS (from result.json)")
    print("=" * 100)
    an_by_model = {}
    for r in an_runs:
        an_by_model.setdefault(r["model"], []).append(r)

    # Visible assistant-output volume (for the Fable thinking-token check)
    an_chars = {}
    for name, rs in an_by_model.items():
        an_chars[name] = sum(
            assistant_char_volume(os.path.join(
                RESULTS_DIR, r["set"], "runs", r["run_dir"],
                "transcript.jsonl"))
            for r in rs)

    hdr = (f"{'Model':<12} {'runs':>5} {'$/run':>8} {'in/run':>8} "
           f"{'out/run':>9} {'cread/run':>10} {'ccre/run':>10} "
           f"{'tok/run':>10} {'out tok/s':>9} {'dur/run':>8} "
           f"{'vis ch/otok':>11}")
    print(hdr)
    print("-" * len(hdr))
    anthropic_summaries = {}
    for name in sorted(an_by_model):
        rs = an_by_model[name]
        n = len(rs)
        cost = sum(r["computed_cost_usd"] for r in rs)
        i_t = sum(r["input_tokens"] for r in rs)
        o_t = sum(r["output_tokens"] for r in rs)
        cr = sum(r["cache_read_tokens"] for r in rs)
        cc = sum(r["cache_creation_tokens"] for r in rs)
        dur = sum(r["duration_s"] for r in rs)
        tok = i_t + o_t + cr + cc
        nto = [r for r in rs if not r["timed_out"]]
        ch_per_otok = an_chars[name] / o_t if o_t else 0
        print(f"{name:<12} {n:>5} {cost/n:>8.3f} {i_t/n:>8.0f} {o_t/n:>9.0f} "
              f"{cr/n:>10.0f} {cc/n:>10.0f} {tok/n:>10.0f} "
              f"{o_t/dur if dur else 0:>9.1f} {dur/n:>8.0f} "
              f"{ch_per_otok:>11.2f}")
        anthropic_summaries[name] = {
            "n_runs": n, "n_timed_out": n - len(nto),
            "cost_per_run": cost / n,
            "cost_per_run_nontimeout":
                (sum(r["computed_cost_usd"] for r in nto) / len(nto)
                 if nto else None),
            "tokens_per_run": {"input": i_t / n, "output": o_t / n,
                               "cache_read": cr / n, "cache_creation": cc / n,
                               "total": tok / n},
            "output_tokens_per_second": o_t / dur if dur else 0,
            "duration_per_run_s": dur / n,
            "visible_chars_per_output_token": ch_per_otok,
        }

    # Cost-provenance check: the harness formula (cost_estimator.py /
    # PricingConfig.estimate_cost) is
    #     input*p_in + output*p_out + cache_read*p_cached
    # and IGNORES cache_creation_tokens. Recompute both ways:
    #   harness formula  -> ratio ~1.0 confirms computed_cost_usd is derived
    #                       from logged tokens (so concealed Fable thinking
    #                       tokens, absent from the log, are also absent from
    #                       the cost), and
    #   full Anthropic convention (cache_creation at 1.25x input) -> shows
    #                       how much true Anthropic billing is understated.
    print("\nAnthropic cost provenance: recomputed from logged tokens vs computed_cost_usd")
    print(f"  {'Model':<12} {'logged$':>9} {'harness-formula$':>16} {'ratio':>6} "
          f"{'full-conv$':>10} {'ratio':>6}")
    fable_checks = {}
    for name in sorted(an_by_model):
        pr = by_name.get(name, {}).get("pricing")
        if not pr:
            continue
        rs = an_by_model[name]
        harness_f = sum(
            (r["input_tokens"] * pr["input"]
             + r["output_tokens"] * pr["output"]
             + r["cache_read_tokens"] * pr.get("cached_input", pr["input"])) / 1e6
            for r in rs)
        full_conv = harness_f + sum(
            r["cache_creation_tokens"] * pr["input"] * 1.25 / 1e6 for r in rs)
        logged = sum(r["computed_cost_usd"] for r in rs)
        fable_checks[name] = {
            "logged": logged,
            "harness_formula_recompute": harness_f,
            "logged_over_harness_formula": logged / harness_f if harness_f else None,
            "full_convention_recompute": full_conv,
            "logged_over_full_convention": logged / full_conv if full_conv else None,
        }
        print(f"  {name:<12} {logged:>9.2f} {harness_f:>16.2f} "
              f"{logged/harness_f if harness_f else 0:>6.3f} {full_conv:>10.2f} "
              f"{logged/full_conv if full_conv else 0:>6.3f}")

    # --- token-hunger multipliers ---
    print("\n" + "=" * 100)
    print("TOKEN-HUNGER MULTIPLIER PROTOTYPE")
    print("=" * 100)
    # Reference: Opus 4.8 (Anthropic billing-meter equivalent =
    # input + output + cache_read + cache_creation per run)
    ref = anthropic_summaries.get(REFERENCE_MODEL)
    if not ref:
        print(f"ERROR: reference model {REFERENCE_MODEL} missing")
        sys.exit(1)
    ref_tok = ref["tokens_per_run"]["total"]
    ref_cost = ref["cost_per_run"]

    tok_per_run_all = {}
    cost_per_run_all = {}
    for name, s in anthropic_summaries.items():
        tok_per_run_all[name] = s["tokens_per_run"]["total"]
        cost_per_run_all[name] = s["cost_per_run"]
    for name, s in model_summaries.items():
        if s["n_covered_runs"]:
            tok_per_run_all[name] = s["billed_tokens_per_covered_run"]
            cost_per_run_all[name] = s["billed_cost_per_covered_run"]
    corpus_median_tok = statistics.median(tok_per_run_all.values())

    hdr = (f"{'Model':<20} {'tok/run':>10} {'xOpus4.8':>9} {'xMedian':>8} "
           f"{'$/run':>8} {'x$Opus':>7} {'pred$/run':>9} {'obs/pred':>8} "
           f"{'TO%':>5}")
    print(hdr)
    print("-" * len(hdr))
    hunger = {}
    ordered = (sorted(anthropic_summaries) +
               sorted(n for n in model_summaries
                      if model_summaries[n]["n_covered_runs"]))
    for name in ordered:
        tok = tok_per_run_all.get(name)
        cpr = cost_per_run_all.get(name)
        if tok is None:
            continue
        if name in model_summaries:
            s = model_summaries[name]
            pred = (s["published_blend_predicted_cost"] / s["n_covered_runs"]
                    if s["n_covered_runs"] else None)
            to_share = s["n_timed_out"] / s["n_runs"] if s["n_runs"] else 0
        else:
            s = anthropic_summaries[name]
            pred = None  # computed cost IS published-price-derived
            to_share = (s["n_timed_out"] / s["n_runs"]) if s["n_runs"] else 0
        hunger[name] = {
            "tokens_per_run": tok,
            "vs_opus48_tokens": tok / ref_tok,
            "vs_corpus_median_tokens": tok / corpus_median_tok,
            "cost_per_run": cpr,
            "vs_opus48_cost": cpr / ref_cost,
            "published_blend_predicted_cost_per_run": pred,
            "observed_over_predicted": (cpr / pred if pred else None),
            "timed_out_share": to_share,
        }
        print(f"{name:<20} {tok:>10.0f} {tok/ref_tok:>9.2f} "
              f"{tok/corpus_median_tok:>8.2f} {cpr:>8.3f} "
              f"{cpr/ref_cost:>7.2f} "
              f"{pred if pred is not None else float('nan'):>9.3f} "
              f"{(cpr/pred) if pred else float('nan'):>8.2f} {to_share:>5.1%}")
    print(f"\nReference: {REFERENCE_MODEL} = {ref_tok:,.0f} tok/run, "
          f"{fmt_money(ref_cost)}/run; corpus median = "
          f"{corpus_median_tok:,.0f} tok/run")
    print("OpenRouter $/run uses billed (attributed) spend over covered "
          "runs; Anthropic uses harness computed cost (published rates).")

    # Non-timeout cost-per-run split.
    # For OpenRouter models the billed export cannot be split by run reliably
    # (concurrent same-model runs make row->run assignment ambiguous), so the
    # primary split uses harness computed cost (consistent within-model),
    # scaled by the model's billed/harness calibration ratio to estimate the
    # billed-equivalent. The raw unambiguous-row billed split is reported in
    # the JSON but is biased (covers only non-concurrent runs).
    print("\nCost per run: all runs vs non-timed-out only")
    print(f"  {'Model':<20} {'all':>8} {'non-TO':>8}  basis")
    nto_split = {}
    for name in ordered:
        if name in anthropic_summaries:
            s = anthropic_summaries[name]
            allc, ntoc = s["cost_per_run"], s["cost_per_run_nontimeout"]
            basis = "harness computed (= published rates)"
        else:
            s = model_summaries[name]
            m_runs = [r for r in or_runs
                      if base_slug_from_model_id(r["model_id"])
                      == s["base_slug"]]
            nto_runs = [r for r in m_runs if not r["timed_out"]]
            h_all = (sum(r["computed_cost_usd"] for r in m_runs)
                     / len(m_runs) if m_runs else 0)
            h_nto = (sum(r["computed_cost_usd"] for r in nto_runs)
                     / len(nto_runs) if nto_runs else None)
            ratio = s["billed_over_harness_ratio"]
            allc = h_all * ratio
            ntoc = h_nto * ratio if h_nto is not None else None
            s["harness_cost_per_run_all"] = h_all
            s["harness_cost_per_run_nontimeout"] = h_nto
            basis = "harness x billed/harness calibration ratio"
        nto_split[name] = {"all": allc, "non_timeout": ntoc, "basis": basis}
        print(f"  {name:<20} {allc:>8.3f} "
              f"{ntoc if ntoc is not None else float('nan'):>8.3f}  {basis}")

    # --- JSON output ---
    out = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "csv": args.csv,
        "tolerance_s": args.tolerance_s,
        "corpus": {
            "included_sets": len(set_dirs),
            "excluded_dirs_no_summary": excluded_dirs,
            "total_runs": len(runs),
            "openrouter_runs": len(or_runs),
            "anthropic_runs": len(an_runs),
            "window_sources": window_sources,
        },
        "csv_span_utc": [span[0].isoformat(), span[1].isoformat()],
        "tz_offset_scan_best_h": best_off,
        "static_exclusions": {
            "rows": len(static_excl),
            "cost": sum(r["cost_total"] for r in static_excl)},
        "pre_campaign_exclusions": {
            "campaign_start_utc": campaign_start.isoformat(),
            "rows": len(dyn_excl),
            "cost": sum(r["cost_total"] for r in dyn_excl),
            "by_model": {s: {"rows": n, "cost": round(c, 2)}
                         for s, (n, c) in by_slug_excl.items()}},
        "orphans": {
            "rows": len(orphan_all),
            "cost": sum(r["cost_total"] for r in orphan_all),
            "clusters": orphan_clusters},
        "openrouter_models": model_summaries,
        "anthropic_models": anthropic_summaries,
        "fable_cost_recompute_check": fable_checks,
        "token_hunger": hunger,
        "cost_per_run_timeout_split": nto_split,
        "reference_model": REFERENCE_MODEL,
        "corpus_median_tokens_per_run": corpus_median_tok,
    }
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nJSON summary written: {args.output}")


if __name__ == "__main__":
    main()
