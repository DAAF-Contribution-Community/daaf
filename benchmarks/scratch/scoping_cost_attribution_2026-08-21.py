# --- Config ---
# INTENT: Measure feasibility of a positively-identified battery-cost basis for
#   OpenRouter models: only billing rows attributable to in-corpus, non-timed-out
#   runs may enter the estimate. Reuse the canonical reconciler's loaders so the
#   corpus/window/attribution mechanics are IDENTICAL to production.
# REASONING: Importing the module guarantees window derivation + tol match the
#   deployed reconciler; re-implementing would risk drift.
# ASSUMES: reconcile_openrouter_costs.py is importable and its helpers are pure.
import os, sys, json, statistics
from datetime import timedelta
sys.path.insert(0, "/daaf/benchmarks/scripts")
import reconcile_openrouter_costs as R

CSV = "/daaf/benchmarks/openrouter_activity_combined_2026-08-21.csv"
TOL_S = 120
tol = timedelta(seconds=TOL_S)

# --- Load ---
models = R.load_models(R.MODELS_YAML)
by_base = {}
for m in models:
    if m.get("provider") == "openrouter":
        by_base[R.base_slug_from_model_id(m["id"])] = m

set_dirs, excluded_dirs = R.discover_set_dirs(R.RESULTS_DIR)
runs, window_sources = R.load_corpus_runs(set_dirs)
# Strip stalled fixture-only windows exactly as reconciler does
fixture_only = 0
for r in runs:
    if r["turns"] == 0 and r["error"]:
        r["start"] = r["end"] = None
        fixture_only += 1
or_runs = [r for r in runs if r["provider"] == "openrouter"]
rows = R.load_csv_rows(CSV)
work_rows = [r for r in rows if not (r["base_slug"].startswith(R.EXCLUDED_SLUG_PREFIXES))]
R.attribute_rows(work_rows, runs, TOL_S)
campaign_start = min(r["start"] for r in or_runs if r["start"])
for row in work_rows:
    row["pre_campaign"] = (not row["matched_runs"]) and row["created_at"] < campaign_start - tol

print("=== CORPUS/CSV SUMMARY ===")
print("included_sets", len(set_dirs), "excluded_no_summary", excluded_dirs)
print("total_runs", len(runs), "or_runs", len(or_runs), "fixture_only_stripped", fixture_only)
print("window_sources", window_sources)
print("csv_rows", len(rows), "work_rows(after anthropic strip)", len(work_rows))

# --- Harness timing coverage (Q3) ---
# INTENT: For OpenRouter runs, count how many have a usable [start,end] window
#   and what the window source is. duration_s present? transcript end present?
print("\n=== Q3 HARNESS TIMING COVERAGE (openrouter runs) ===")
n_or = len(or_runs)
has_window = sum(1 for r in or_runs if r["start"] is not None)
has_dur = sum(1 for r in or_runs if r["duration_s"] and r["duration_s"] > 0)
src_counts = {}
for r in or_runs:
    src_counts[r.get("window_source")] = src_counts.get(r.get("window_source"), 0) + 1
print("or_runs", n_or, "with usable window", has_window,
      "(%.1f%%)" % (100*has_window/n_or), "with duration_s>0", has_dur)
print("window_source breakdown (or_runs):", src_counts)

# --- Q2 Timestamp semantics: where does created_at fall in [start,end]? ---
# INTENT: For rows matched to EXACTLY ONE non-timed-out run, compute the
#   normalized position frac=(created_at-start)/duration. ~0 => created_at is
#   request-start; ~1 => completion. Also raw offsets to end.
print("\n=== Q2 TIMESTAMP SEMANTICS (unambiguous single-run matches) ===")
fracs = []; end_offsets = []; start_offsets = []
for row in work_rows:
    if row.get("pre_campaign"): continue
    mr = row["matched_runs"]
    if len(mr) != 1: continue
    run = runs[mr[0]]
    if run["timed_out"] or not run["duration_s"]: continue
    dur = run["duration_s"]
    frac = (row["created_at"] - run["start"]).total_seconds()/dur
    fracs.append(frac)
    end_offsets.append((run["end"] - row["created_at"]).total_seconds())
    start_offsets.append((row["created_at"] - run["start"]).total_seconds())
if fracs:
    fracs_s = sorted(fracs)
    def pct(a,p): return a[int(p*(len(a)-1))]
    print("n unambiguous non-TO pairs:", len(fracs))
    print("frac (created-start)/dur  p10/p50/p90: %.2f / %.2f / %.2f" % (pct(fracs_s,.1),pct(fracs_s,.5),pct(fracs_s,.9)))
    print("  mean frac %.2f  (0=start-time, 1=completion-time)" % (sum(fracs)/len(fracs)))
    eo=sorted(end_offsets); so=sorted(start_offsets)
    print("end-created_at (s) p10/p50/p90: %.0f / %.0f / %.0f" % (pct(eo,.1),pct(eo,.5),pct(eo,.9)))
    print("created_at-start (s) p10/p50/p90: %.0f / %.0f / %.0f" % (pct(so,.1),pct(so,.5),pct(so,.9)))

# --- Q4 + Q6 Per-model coverage under strict vs clean-set ---
# INTENT: For each model compute, over post-campaign rows:
#   current basis: attr rows billed_tokens/n_covered_runs (viewer logic)
#   strict: rows with exactly one match to an in-corpus non-timed-out run
#   clean-set: rows whose ENTIRE candidate set is in-corpus non-timed-out runs
# ASSUMES: all matched_runs indices are in-corpus (they are; runs_by_base only
#   holds corpus openrouter runs). "in-corpus non-timed-out" = not timed_out.
print("\n=== Q4/Q6 PER-MODEL COVERAGE ===")
hdr = ("%-22s %5s %6s | cur$/run  strict$/run clean$/run | rowsAttr strictRows cleanRows | "
       "covRuns strictCov cleanCov | TOrows$ ")
print(hdr % ("model","runs","TO",))
results = {}
for base, mcfg in sorted(by_base.items(), key=lambda kv: kv[1]["name"]):
    name = mcfg["name"]
    mrows = [r for r in work_rows if r["base_slug"] == base and not r.get("pre_campaign")]
    if not mrows: continue
    attr = [r for r in mrows if r["matched_runs"]]
    m_all_runs = [r for r in or_runs if R.base_slug_from_model_id(r["model_id"]) == base]
    n_run = len(m_all_runs); n_to = sum(1 for r in m_all_runs if r["timed_out"])
    # current viewer basis
    covered_idx = sorted({i for r in attr for i in r["matched_runs"]})
    b_prompt = sum(r["tokens_prompt"] for r in attr)
    b_compl = sum(r["tokens_completion"] for r in attr)
    n_cov = len(covered_idx)
    pr = mcfg["pricing"]
    cur_cpr = ((b_prompt/n_cov)*pr["input"] + (b_compl/n_cov)*pr["output"])/1e6 if n_cov else None
    # cost attributed to timed-out runs among covered (contamination via TO)
    to_rows = [r for r in attr if all(runs[i]["timed_out"] for i in r["matched_runs"])]
    to_cost = sum(r["cost_total"] for r in to_rows)
    # STRICT: row matched to exactly one non-TO run
    strict_rows = [r for r in attr if len(r["matched_runs"])==1 and not runs[r["matched_runs"][0]]["timed_out"]]
    s_prompt = sum(r["tokens_prompt"] for r in strict_rows)
    s_compl = sum(r["tokens_completion"] for r in strict_rows)
    s_cov = len({r["matched_runs"][0] for r in strict_rows})
    strict_cpr = ((s_prompt/s_cov)*pr["input"]+(s_compl/s_cov)*pr["output"])/1e6 if s_cov else None
    # CLEAN-SET: entire candidate set non-TO (>=1 candidate), ambiguity allowed
    clean_rows = [r for r in attr if all(not runs[i]["timed_out"] for i in r["matched_runs"])]
    c_prompt = sum(r["tokens_prompt"] for r in clean_rows)
    c_compl = sum(r["tokens_completion"] for r in clean_rows)
    c_cov = len({i for r in clean_rows for i in r["matched_runs"]})
    clean_cpr = ((c_prompt/c_cov)*pr["input"]+(c_compl/c_cov)*pr["output"])/1e6 if c_cov else None
    n_nonto = n_run - n_to
    def f(x): return ("%.4f"%x) if x is not None else "  --  "
    print("%-22s %5d %6d | %s  %s  %s | %7d %9d %9d | %6d/%-3d %4d/%-3d %4d/%-3d | $%.2f" % (
        name[:22], n_run, n_to, f(cur_cpr), f(strict_cpr), f(clean_cpr),
        len(attr), len(strict_rows), len(clean_rows),
        n_cov, n_nonto, s_cov, n_nonto, c_cov, n_nonto, to_cost))
    results[name] = dict(n_run=n_run,n_to=n_to,cur_cpr=cur_cpr,strict_cpr=strict_cpr,
        clean_cpr=clean_cpr,rows_attr=len(attr),strict_rows=len(strict_rows),
        clean_rows=len(clean_rows),n_cov=n_cov,s_cov=s_cov,c_cov=c_cov,
        n_nonto=n_nonto,to_cost=to_cost,tot_rows=len(mrows),
        strict_row_share=len(strict_rows)/len(attr) if attr else 0,
        clean_row_share=len(clean_rows)/len(attr) if attr else 0)

# --- Q6 contamination: rows matched ONLY to timed-out runs, plus orphan rows ---
print("\n=== Q6 CONTAMINATION FOCUS (TO-only matched rows currently in billed_tokens) ===")
for name in ["Qwen 3.8 27B","Qwen 3.8 2.4T A95B","GLM 5.3"]:
    if name in results:
        r=results[name]
        print("%-22s TO-only-row $%.2f  (of model, n_run=%d n_to=%d)  strict_row_share=%.1f%% clean_row_share=%.1f%%"%(
            name, r["to_cost"], r["n_run"], r["n_to"], 100*r["strict_row_share"], 100*r["clean_row_share"]))

# --- Save ---
outp = "/daaf/benchmarks/scratch/scoping_cost_attribution_2026-08-21_results.json"
with open(outp,"w") as f: json.dump(results,f,indent=1,default=str)
print("\nwrote", outp)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-21 16:05:51
# Command: python3 /daaf/benchmarks/scratch/scoping_cost_attribution_2026-08-21.py
# Duration: 3s
# Exit code: 0
#
# --- STDOUT ---
# === CORPUS/CSV SUMMARY ===
# included_sets 407 excluded_no_summary ['_quarantine_2026-07-18', '_quarantine_2026-07-24', '_quarantine_2026-07-29_earlystop', '_quarantine_2026-07-29_instantexit', '_quarantine_2026-07-29_opus45spendlimit', '_quarantine_2026-07-29_overreps', '_quarantine_2026-07-29_solunusable', 'probes']
# total_runs 6178 or_runs 4241 fixture_only_stripped 501
# window_sources {'transcript': 6177, 'mtime_fallback': 1, 'none': 0}
# csv_rows 39450 work_rows(after anthropic strip) 39422
# 
# === Q3 HARNESS TIMING COVERAGE (openrouter runs) ===
# or_runs 4241 with usable window 3840 (90.5%) with duration_s>0 4241
# window_source breakdown (or_runs): {'transcript': 4240, 'mtime_fallback': 1}
# 
# === Q2 TIMESTAMP SEMANTICS (unambiguous single-run matches) ===
# n unambiguous non-TO pairs: 3607
# frac (created-start)/dur  p10/p50/p90: 0.10 / 0.46 / 0.88
#   mean frac 0.51  (0=start-time, 1=completion-time)
# end-created_at (s) p10/p50/p90: 11 / 191 / 528
# created_at-start (s) p10/p50/p90: 6 / 175 / 551
# 
# === Q4/Q6 PER-MODEL COVERAGE ===
# model                   runs     TO | cur$/run  strict$/run clean$/run | rowsAttr strictRows cleanRows | covRuns strictCov cleanCov | TOrows$ 
# DeepSeek V4 Flash 0731   154      0 | 0.0667  0.1495  0.0667 |    1164       188      1164 |    154/154   15/154  154/154 | $0.00
# DeepSeek V4 Pro          194     41 | 0.7712  0.9276  0.7712 |    1397       154      1397 |    153/153   17/153  153/153 | $0.00
# DeepSeek V4 Pro 0813     156      2 | 0.1981  0.8844  0.1981 |    1082        50      1082 |    152/154    2/154  152/154 | $0.00
# GLM 5.1                  174     21 | 0.4615  0.4755  0.4615 |    1290       108      1290 |    153/153   16/153  153/153 | $0.00
# GLM 5.2                  165     12 | 0.4923  0.9945  0.4923 |     990       222       990 |    153/153   16/153  153/153 | $0.00
# GLM 5.3                  160      4 | 1.2059  0.9661  1.2059 |    1868        36      1868 |    156/156    4/156  156/156 | $0.00
# GPT-5.6 Sol                0      0 |   --      --      --   |       0         0         0 |      0/0      0/0      0/0   | $0.00
# Gemini 2.5 Pro           153      0 | 0.6629  0.3663  0.6629 |     733       112       733 |    153/153   41/153  153/153 | $0.00
# Gemini 3.1 Flash Lite    153      0 | 0.0541    --    0.0541 |     756         0       756 |    153/153    0/153  153/153 | $0.00
# Gemini 3.1 Pro           155      2 | 0.7339  1.3820  0.7339 |    1056        19      1056 |    153/153    3/153  153/153 | $0.00
# Gemini 3.5 Flash         153      0 | 1.7229  0.9477  1.7229 |    1473       282      1473 |    153/153   45/153  153/153 | $0.00
# Gemini 3.5 Flash Lite    153      0 | 0.0976  0.0690  0.0976 |     625       108       625 |    153/153   40/153  153/153 | $0.00
# Gemini 3.6 Flash         153      0 | 0.7001  0.5435  0.7001 |     931       179       931 |    153/153   40/153  153/153 | $0.00
# Gemma 4 26B              176     23 | 0.0461  0.0642  0.0461 |    1180       169      1180 |    153/153   19/153  153/153 | $0.00
# Gemma 4 31B              223     70 | 0.0415  0.0203  0.0415 |     857        11       857 |    153/153    4/153  153/153 | $0.00
# Grok 4.6                 155      1 | 1.4640  2.8841  1.4640 |    1493        66      1493 |    154/154    3/154  154/154 | $0.00
# Inkling                  153      0 | 0.2817    --    0.2817 |    1550         0      1550 |    153/153    0/153  153/153 | $0.00
# Inkling Small            153      0 | 0.1341  0.1446  0.1341 |    1756        13      1756 |    153/153    1/153  153/153 | $0.00
# Kimi K2.6                184     31 | 0.2501  0.4993  0.2501 |    1129       163      1129 |    153/153   12/153  153/153 | $0.00
# Kimi K2.7 Code           178     25 | 0.3545  0.5775  0.3545 |    1142       224      1142 |    153/153   22/153  153/153 | $0.00
# Kimi K3                  212     59 | 1.4952  2.2917  1.4952 |    1221       669      1221 |    153/153   60/153  153/153 | $0.00
# Nemotron 3 Ultra         190     37 | 0.2522  0.0726  0.2522 |    1275         2      1275 |    153/153    1/153  153/153 | $0.00
# Qwen 3.6 27B             176     23 | 0.1817  0.4425  0.1817 |    1565       187      1565 |    153/153   11/153  153/153 | $0.00
# Qwen 3.8 2.4T A95B       175     14 | 1.6964  4.5794  1.6964 |    1853       170      1853 |    157/161    7/161  157/161 | $0.00
# Qwen 3.8 27B             175     21 | 0.5724  1.4877  0.5724 |    2262       330      2262 |    154/154   11/154  154/154 | $0.00
# 
# === Q6 CONTAMINATION FOCUS (TO-only matched rows currently in billed_tokens) ===
# Qwen 3.8 27B           TO-only-row $0.00  (of model, n_run=175 n_to=21)  strict_row_share=14.6% clean_row_share=100.0%
# Qwen 3.8 2.4T A95B     TO-only-row $0.00  (of model, n_run=175 n_to=14)  strict_row_share=9.2% clean_row_share=100.0%
# GLM 5.3                TO-only-row $0.00  (of model, n_run=160 n_to=4)  strict_row_share=1.9% clean_row_share=100.0%
# 
# wrote /daaf/benchmarks/scratch/scoping_cost_attribution_2026-08-21_results.json
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
