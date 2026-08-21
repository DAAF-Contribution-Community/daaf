# --- Config ---
# INTENT: Verify the structural timed-out attribution guard added to
#         reconcile_openrouter_costs.py is a numeric no-op on the 2026-08-21
#         corpus by diffing the battery-basis-feeding fields between the
#         production reconciliation JSON and the post-guard re-run.
# REASONING: The scoping probe predicted exact equality (timed-out runs
#         capture zero rows already); this diff is the acceptance test.
# ASSUMES: Both JSONs share the model_summaries/openrouter_models schema.
import json

OLD = "/daaf/benchmarks/derived/openrouter_reconciliation_2026-08-21.json"
NEW = "/daaf/benchmarks/scratch/reconciliation_postguard_2026-08-21.json"

# --- Load ---
old = json.load(open(OLD))
new = json.load(open(NEW))
o = old.get("openrouter_models") or old.get("model_summaries")
n = new.get("openrouter_models") or new.get("model_summaries")
print(f"models: old={len(o)} new={len(n)}")

# --- Validate ---
# INTENT: exact equality on every field the generator's battery basis reads
#         (billed_tokens, n_covered_runs) plus headline attribution totals.
FIELDS = ["billed_tokens", "n_covered_runs", "n_runs", "n_timed_out",
          "billed_cost_attributed", "rows_attributed"]
diffs = 0
for name in sorted(set(o) | set(n)):
    a, b = o.get(name), n.get(name)
    if a is None or b is None:
        print(f"MODEL SET DIFF: {name} old={a is not None} new={b is not None}")
        diffs += 1
        continue
    for f in FIELDS:
        if a.get(f) != b.get(f):
            print(f"DIFF {name}.{f}: old={a.get(f)} new={b.get(f)}")
            diffs += 1
print(f"\nfield diffs: {diffs}")
assert diffs == 0, "guard changed battery-basis numbers — NOT a no-op"
print("OK: structural guard is a numeric no-op on the battery basis")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-21 16:19:26
# Command: python3 /daaf/benchmarks/scratch/diff_reconciliation_guard_2026-08-21.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# models: old=25 new=25
# 
# field diffs: 0
# OK: structural guard is a numeric no-op on the battery basis
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
