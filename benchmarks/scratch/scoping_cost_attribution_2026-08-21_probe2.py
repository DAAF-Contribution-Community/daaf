# --- Config ---
# INTENT: Verify (a) whether ANY billing row matches a timed-out run window,
#   (b) whether any covered run index is timed_out, (c) orphan-row volume and
#   whether quarantine/out-of-corpus runs can contaminate billed_tokens.
# REASONING: Confirms the maintainer's premise about timed-out contamination
#   empirically and quantifies the true contamination channel (orphans).
# ASSUMES: same loaders as production reconciler.
import os, sys, json
from datetime import timedelta
sys.path.insert(0, "/daaf/benchmarks/scripts")
import reconcile_openrouter_costs as R
CSV="/daaf/benchmarks/openrouter_activity_combined_2026-08-21.csv"; TOL_S=120
tol=timedelta(seconds=TOL_S)

# --- Load ---
models=R.load_models(R.MODELS_YAML)
by_base={R.base_slug_from_model_id(m["id"]):m for m in models if m.get("provider")=="openrouter"}
set_dirs,excluded_dirs=R.discover_set_dirs(R.RESULTS_DIR)
runs,_=R.load_corpus_runs(set_dirs)
for r in runs:
    if r["turns"]==0 and r["error"]: r["start"]=r["end"]=None
or_runs=[r for r in runs if r["provider"]=="openrouter"]
rows=R.load_csv_rows(CSV)
work=[r for r in rows if not r["base_slug"].startswith(R.EXCLUDED_SLUG_PREFIXES)]
R.attribute_rows(work,runs,TOL_S)
campaign_start=min(r["start"] for r in or_runs if r["start"])
for row in work:
    row["pre_campaign"]=(not row["matched_runs"]) and row["created_at"]<campaign_start-tol

# --- Probe: timed-out run coverage ---
rows_touch_to=0; rows_to_only=0; cov_to_idx=set(); cov_all_idx=set()
for row in work:
    if row.get("pre_campaign"): continue
    mr=row["matched_runs"]
    if not mr: continue
    for i in mr: cov_all_idx.add(i)
    to_flags=[runs[i]["timed_out"] for i in mr]
    if any(to_flags): rows_touch_to+=1
    if to_flags and all(to_flags): rows_to_only+=1
    for i in mr:
        if runs[i]["timed_out"]: cov_to_idx.add(i)
n_to_runs=sum(1 for r in or_runs if r["timed_out"])
print("=== TIMED-OUT COVERAGE PROBE ===")
print("openrouter timed_out runs:", n_to_runs)
print("attributed rows touching >=1 timed-out run:", rows_touch_to)
print("attributed rows matching ONLY timed-out run(s):", rows_to_only)
print("distinct timed-out run indices that captured >=1 row:", len(cov_to_idx))
print("distinct covered run indices total:", len(cov_all_idx))

# --- Probe: why? sample a few timed-out runs' windows vs row availability ---
to_runs=[r for r in or_runs if r["timed_out"]][:5]
print("\nSample timed-out runs (window + same-slug rows inside window):")
for r in to_runs:
    base=R.base_slug_from_model_id(r["model_id"])
    if r["start"] is None:
        print("  ",r["run_dir"],"NO WINDOW (fixture stripped?)"); continue
    inside=sum(1 for row in work if row["base_slug"]==base and r["start"]-tol<=row["created_at"]<=r["end"]+tol)
    print("  %-40s dur=%.0f start=%s end=%s rows_inside=%d"%(r["run_dir"][:40],r["duration_s"],r["start"],r["end"],inside))

# --- Probe: orphans + quarantine contamination ---
orphans=[r for r in work if not r["matched_runs"] and not r.get("pre_campaign")]
print("\n=== ORPHAN / OUT-OF-CORPUS PROBE ===")
print("post-campaign orphan rows:", len(orphans), "orphan $%.2f"%sum(r["cost_total"] for r in orphans))
# Are quarantine dirs in corpus? (excluded_dirs shows them). Their runs are NOT
# in runs[], so their generations cannot attribute -> they become orphans.
print("excluded (non-corpus) dirs:", excluded_dirs)
# orphan by slug top
bys={}
for r in orphans:
    s=r["base_slug"].split("/")[-1]; bys.setdefault(s,[0,0.0]); bys[s][0]+=1; bys[s][1]+=r["cost_total"]
for s,(n,c) in sorted(bys.items(),key=lambda kv:-kv[1][1])[:12]:
    print("  %-34s %5d rows  $%7.2f"%(s,n,c))


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-21 16:07:17
# Command: python3 /daaf/benchmarks/scratch/scoping_cost_attribution_2026-08-21_probe2.py
# Duration: 2s
# Exit code: 0
#
# --- STDOUT ---
# === TIMED-OUT COVERAGE PROBE ===
# openrouter timed_out runs: 401
# attributed rows touching >=1 timed-out run: 0
# attributed rows matching ONLY timed-out run(s): 0
# distinct timed-out run indices that captured >=1 row: 0
# distinct covered run indices total: 3834
# 
# Sample timed-out runs (window + same-slug rows inside window):
#    mc-08_Gemma_4_31B_0 NO WINDOW (fixture stripped?)
#    mc-11_Gemma_4_31B_0 NO WINDOW (fixture stripped?)
#    mc-04_Nemotron_3_Ultra_2 NO WINDOW (fixture stripped?)
#    mc-06_DeepSeek_V4_Pro_1 NO WINDOW (fixture stripped?)
#    mc-06_DeepSeek_V4_Pro_2 NO WINDOW (fixture stripped?)
# 
# === ORPHAN / OUT-OF-CORPUS PROBE ===
# post-campaign orphan rows: 2340 orphan $117.11
# excluded (non-corpus) dirs: ['_quarantine_2026-07-18', '_quarantine_2026-07-24', '_quarantine_2026-07-29_earlystop', '_quarantine_2026-07-29_instantexit', '_quarantine_2026-07-29_opus45spendlimit', '_quarantine_2026-07-29_overreps', '_quarantine_2026-07-29_solunusable', 'probes']
#   kimi-k3                              863 rows  $  64.00
#   nemotron-3-ultra-550b-a55b           330 rows  $   8.76
#   glm-5.2                              146 rows  $   7.96
#   kimi-k2.7-code                       244 rows  $   7.20
#   qwen3.8-2.4t-a95b                    119 rows  $   4.96
#   gemini-3.1-pro-preview                35 rows  $   4.61
#   glm-5.1                               67 rows  $   4.09
#   qwen3.8-27b                           54 rows  $   3.94
#   deepseek-v4-pro                       46 rows  $   3.72
#   kimi-k2.6                             66 rows  $   2.63
#   deepseek-v4-flash                    161 rows  $   1.28
#   gemini-3.1-flash-lite                 89 rows  $   1.26
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
