# --- Config ---
# INTENT: Post-re-pin verification of the daafbench_2026-08-21e bundle:
#         confirm Qwen 3.8 27B's battery cost reflects the new Alibaba rates,
#         Qwen 2.4T and GLM 5.3 are unchanged, and efficiency-frontier
#         membership did not change (prose claim protection).
# REASONING: Rate change 0.45/3.20 -> 0.575/3.45 should raise 27B's battery
#         estimate ~27% (input-dominated mix). Frontier must remain the six
#         ratified models or the T2 prose is stale again.
# ASSUMES: Same PRECOMPUTED embedding as prior bundles.
import json
import re

BUNDLE = "/daaf/benchmarks/daafbench_2026-08-21e/index.html"
PRIOR = {"Qwen 3.8 27B": 29.19, "Qwen 3.8 2.4T A95B": 86.52, "GLM 5.3": 61.5}

# --- Load ---
html = open(BUNDLE, encoding="utf-8").read()
m = re.search(r"PRECOMPUTED\s*=\s*(\{.*?\});\s*\n", html, re.DOTALL)
assert m, "PRECOMPUTED not found"
pre = json.loads(m.group(1))

# --- Profile ---
bat = pre["cost"]["battery"]["models"]
print("battery estimates (prior -> new):")
for name, old in PRIOR.items():
    b = bat[name]
    print(f"  {name:22s} ${old} -> ${b['est_battery_cost']} "
          f"(mult {b['cost_multiplier_vs_ref']}x, basis {b['basis']})")

frontier = [d["model"] for d in pre["cost"]["frontiers"]["battery"]["composite"]["perfect"]]
print("\nfrontier:", frontier)

t1 = pre["tiers"][0]["models"]
print("T1:", t1)

# registry rates as loaded
cm = {d["key"]: d for d in pre["cost"]["models"]}
print("\nloaded list rates: 27B", cm["Qwen 3.8 27B"]["input"], "/",
      cm["Qwen 3.8 27B"]["output"], "| 2.4T", cm["Qwen 3.8 2.4T A95B"]["input"],
      "/", cm["Qwen 3.8 2.4T A95B"]["output"])

# --- Validate ---
EXPECT_FRONTIER = ["Gemma 4 31B", "GPT-5.6 Luna (ChatGPT Subscription)",
                   "Sonnet 5", "GLM 5.3", "Grok 4.6", "Fable 5"]
assert frontier == EXPECT_FRONTIER, f"FRONTIER CHANGED: {frontier}"
assert cm["Qwen 3.8 27B"]["input"] == 0.575, "27B input rate not picked up"
assert bat["Qwen 3.8 2.4T A95B"]["est_battery_cost"] == 86.52, "2.4T changed unexpectedly"
assert bat["GLM 5.3"]["est_battery_cost"] == 61.5, "GLM changed unexpectedly"
assert bat["Qwen 3.8 27B"]["est_battery_cost"] > 29.19, "27B did not rise"
print("\nOK: rates picked up, 27B risen as expected, 2.4T/GLM unchanged, "
      "frontier membership UNCHANGED (T2 prose remains valid)")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-21 18:00:28
# Command: python3 /daaf/benchmarks/scratch/verify_repin_surfaces_2026-08-21.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# battery estimates (prior -> new):
#   Qwen 3.8 27B           $29.19 -> $36.46 (mult 0.32x, basis billing-snapshot-2026-08-21)
#   Qwen 3.8 2.4T A95B     $86.52 -> $86.52 (mult 0.759x, basis billing-snapshot-2026-08-21)
#   GLM 5.3                $61.5 -> $61.5 (mult 0.539x, basis billing-snapshot-2026-08-21)
# 
# frontier: ['Gemma 4 31B', 'GPT-5.6 Luna (ChatGPT Subscription)', 'Sonnet 5', 'GLM 5.3', 'Grok 4.6', 'Fable 5']
# T1: ['Fable 5', 'Opus 5', 'Grok 4.6', 'GPT-5.6 Sol (ChatGPT Subscription)', 'GLM 5.3', 'Qwen 3.8 2.4T A95B', 'Kimi K3', 'Sonnet 5']
# 
# loaded list rates: 27B 0.575 / 3.45 | 2.4T 2.0 / 6.0
# 
# OK: rates picked up, 27B risen as expected, 2.4T/GLM unchanged, frontier membership UNCHANGED (T2 prose remains valid)
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
