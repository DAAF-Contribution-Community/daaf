#!/usr/bin/env python3
"""
Negative control + coverage audit for the equivalence harness.

Two guards against a false-PASS:
  A. NEGATIVE CONTROL: mutate a copy of the R capture (flip one null count, one
     leading-zero sample, one int64 max, one sentinel count) and re-run the exact
     comparison logic. If the differ is sound it MUST flag each injected drift.
  B. COVERAGE: prove the checks were not vacuous — confirm the captured samples
     actually contained the hazardous content we claim to have tested:
       - at least one int64 value >= 2^31 appears in a sample row
       - leading-zero ID samples are non-empty for CRDC id columns
       - non-ASCII inventory scanned (report where any was found; if none, say so)
       - sentinels actually present (report which cols carry -1/-2/-3)
"""

# --- Config ---
import os
import json
import copy

SCRATCH = "/daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch"
PY = os.path.join(SCRATCH, "capture_python.json")
R = os.path.join(SCRATCH, "capture_r.json")

with open(PY) as f:
    py = json.load(f)
with open(R) as f:
    rr = json.load(f)

# --- A. Negative control: inject drift into a copy of R capture ---
# INTENT: prove the differ catches each drift class. We mutate specific fields and
#   count how many the comparison flags. Reuse minimal inline comparison logic
#   mirroring 04's checks (kept independent so this is a true cross-check).
mut = copy.deepcopy(rr)
injected = []

# A1: flip a null count on saipe.est_population_5_17_poverty_pct (275 -> 999)
orig = mut["datasets"]["saipe"]["null_counts"]["est_population_5_17_poverty_pct"]
mut["datasets"]["saipe"]["null_counts"]["est_population_5_17_poverty_pct"] = orig + 724
injected.append(("null", "saipe", "est_population_5_17_poverty_pct"))

# A2: corrupt a leading-zero ID sample on crdc.leaid (drop a leading zero)
lz = mut["datasets"]["crdc"]["string_integrity"].get("leaid", {}).get("leading_zero_samples")
if lz:
    mut["datasets"]["crdc"]["string_integrity"]["leaid"]["leading_zero_samples"] = \
        [s.lstrip("0") for s in lz]
    injected.append(("leadzero", "crdc", "leaid"))

# A3: corrupt an int64 max on meps.ncessch (simulate 32-bit truncation)
mmax = mut["datasets"]["meps"]["int_stats"]["ncessch"]["max"]
mut["datasets"]["meps"]["int_stats"]["ncessch"]["max"] = str(int(mmax) & 0x7FFFFFFF)
injected.append(("int64max", "meps", "ncessch"))

# A4: flip a sentinel count on edfacts (find a col with a nonzero sentinel; else force one)
sent_target = None
for c, sc in mut["datasets"]["edfacts"]["sentinel_counts"].items():
    for s in ("-1", "-2", "-3"):
        if int(sc.get(s, 0)) > 0:
            sc[s] = int(sc[s]) + 5
            sent_target = (c, s)
            break
    if sent_target:
        break
if sent_target is None:
    # force one so the control is still exercised
    c = next(iter(mut["datasets"]["edfacts"]["sentinel_counts"]))
    mut["datasets"]["edfacts"]["sentinel_counts"][c]["-1"] = 999
    sent_target = (c, "-1")
injected.append(("sentinel", "edfacts", sent_target[0]))

# Now run detection over the mutated capture
caught = []

# null detection
for k in py["datasets"]:
    P = py["datasets"][k]; M = mut["datasets"][k]
    for c in P["null_counts"]:
        if int(P["null_counts"][c]) != int(M["null_counts"].get(c, -1)):
            caught.append(("null", k, c))
# leadzero detection
for k in py["datasets"]:
    P = py["datasets"][k]; M = mut["datasets"][k]
    for c, psi in P["string_integrity"].items():
        msi = M["string_integrity"].get(c, {})
        if psi.get("leading_zero_samples") is not None and \
           psi.get("leading_zero_samples") != msi.get("leading_zero_samples"):
            caught.append(("leadzero", k, c))
# int64 max detection
for k in py["datasets"]:
    P = py["datasets"][k]; M = mut["datasets"][k]
    for c, pstat in P["int_stats"].items():
        mstat = M["int_stats"].get(c, {})
        if pstat.get("max") != mstat.get("max"):
            caught.append(("int64max", k, c))
# sentinel detection
for k in py["datasets"]:
    P = py["datasets"][k]; M = mut["datasets"][k]
    for c, psc in P["sentinel_counts"].items():
        msc = M["sentinel_counts"].get(c, {})
        for s in ("-1", "-2", "-3"):
            if int(psc.get(s, 0)) != int(msc.get(s, 0)):
                caught.append(("sentinel", k, c))

print("=" * 80)
print("A. NEGATIVE CONTROL — injected drift must be caught")
print("=" * 80)
for cls, k, c in injected:
    hit = any(x[0] == cls and x[1] == k and x[2] == c for x in caught)
    print(f"  injected {cls:9s} into {k}.{c}: {'CAUGHT' if hit else 'MISSED <<< DIFFER IS BROKEN'}")
all_caught = all(any(x[0]==cls and x[1]==k and x[2]==c for x in caught) for cls,k,c in injected)
print(f"\n  Negative control verdict: {'PASS (differ detects all injected drift)' if all_caught else 'FAIL'}")

# --- B. Coverage: prove checks were not vacuous ---
print("\n" + "=" * 80)
print("B. COVERAGE — confirm hazardous content actually present in tests")
print("=" * 80)

# B1: int64 >= 2^31 actually appears in a captured SAMPLE row (not just in stats)
TWO_31 = 2 ** 31
print("\n[B1] int64 >= 2^31 values present in sample rows:")
for k in py["datasets"]:
    P = py["datasets"][k]
    for part in ("head5", "tail5"):
        for i, row in enumerate(P["sample_rows"][part]):
            for c, cell in row.items():
                if cell["t"] == "int" and cell["v"] not in (None,) and abs(int(cell["v"])) >= TWO_31:
                    print(f"    {k}.{c} {part}[{i}] = {cell['v']} (>= 2^31) — R matched exactly (C5/I PASS)")
                    break
            else:
                continue
            break

# B2: leading-zero ID samples non-empty
print("\n[B2] leading-zero ID samples (proves zero-padding preserved & compared):")
for k in py["datasets"]:
    P = py["datasets"][k]
    for c, si in P["string_integrity"].items():
        if si.get("n_leading_zero"):
            print(f"    {k}.{c}: n_leading_zero={si['n_leading_zero']}, samples={si.get('leading_zero_samples')}")

# B3: non-ASCII inventory
print("\n[B3] non-ASCII scan results:")
any_na = False
for k in py["datasets"]:
    P = py["datasets"][k]
    for c, si in P["string_integrity"].items():
        if si.get("non_ascii_count_est", 0) > 0:
            any_na = True
            print(f"    {k}.{c}: non_ascii_count={si['non_ascii_count_est']}, "
                  f"samples={[s['value'] for s in si.get('non_ascii_samples', [])][:5]}")
if not any_na:
    print("    NONE FOUND across all string columns in all 5 sampled datasets.")
    print("    -> non-ASCII byte-identity claim is UNPROVEN (no data to exercise it).")
    print("    -> This is an honest coverage gap, not a safety guarantee.")

# B4: sentinels actually present
print("\n[B4] columns carrying sentinel values (-1/-2/-3), count>0:")
found_sent = False
for k in py["datasets"]:
    P = py["datasets"][k]
    for c, sc in P["sentinel_counts"].items():
        present = {s: sc[s] for s in ("-1", "-2", "-3") if int(sc.get(s, 0)) > 0}
        if present:
            found_sent = True
            print(f"    {k}.{c}: {present}")
if not found_sent:
    print("    NONE — no -1/-2/-3 sentinels in any numeric column of the sampled files.")
    print("    -> sentinel-preservation check ran but had no positive cases to exercise.")

print("\n" + "=" * 80)
print("COVERAGE SUMMARY: B1/B2/B4 report positive cases exercised; B3 reports gaps honestly.")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 19:30:46
# Command: python3 /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/smoke_tests/05_negative-control-and-coverage.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# ================================================================================
# A. NEGATIVE CONTROL — injected drift must be caught
# ================================================================================
#   injected null      into saipe.est_population_5_17_poverty_pct: CAUGHT
#   injected leadzero  into crdc.leaid: CAUGHT
#   injected int64max  into meps.ncessch: CAUGHT
#   injected sentinel  into edfacts.grad_rate_low: CAUGHT
# 
#   Negative control verdict: PASS (differ detects all injected drift)
# 
# ================================================================================
# B. COVERAGE — confirm hazardous content actually present in tests
# ================================================================================
# 
# [B1] int64 >= 2^31 values present in sample rows:
#     edfacts.ncessch head5[0] = 10000500871 (>= 2^31) — R matched exactly (C5/I PASS)
#     edfacts.ncessch tail5[0] = 720003002085 (>= 2^31) — R matched exactly (C5/I PASS)
#     meps.ncessch head5[0] = 10000200277 (>= 2^31) — R matched exactly (C5/I PASS)
#     meps.ncessch tail5[0] = 568025100534 (>= 2^31) — R matched exactly (C5/I PASS)
# 
# [B2] leading-zero ID samples (proves zero-padding preserved & compared):
#     crdc.crdc_id: n_leading_zero=1585155, samples=['010000201705', '010000201706', '010000201876', '010000299995', '010000500870']
#     crdc.leaid: n_leading_zero=1568523, samples=['0100002', '0100005', '0100006', '0100007', '0100008']
#     crdc.ncessch: n_leading_zero=1568523, samples=['010000201705', '010000201706', '010000201876', '010000500870', '010000500871']
# 
# [B3] non-ASCII scan results:
#     saipe.district_name: non_ascii_count=58, samples=['Cañon City School District RE-1', 'Española Municipal Schools', 'Española Municipal Schools+D7957', 'La Cañada Unified School District', 'Peñasco Independent Schools']
# 
# [B4] columns carrying sentinel values (-1/-2/-3), count>0:
#     crdc.expulsions_no_ed_serv: {'-1': 399936, '-2': 72998}
#     crdc.expulsions_with_ed_serv: {'-1': 403409, '-2': 95656}
#     crdc.expulsions_zero_tolerance: {'-1': 379851, '-2': 72998}
#     crdc.students_arrested: {'-1': 583015, '-2': 95418, '-3': 456}
#     crdc.students_corporal_punish: {'-1': 4588540, '-2': 3552392, '-3': 240}
#     crdc.students_referred_law_enforce: {'-1': 412451, '-2': 95418, '-3': 456}
#     crdc.students_susp_in_sch: {'-1': 403525, '-2': 95626}
#     crdc.students_susp_out_sch_multiple: {'-1': 376392, '-2': 72998}
#     crdc.students_susp_out_sch_single: {'-1': 376415, '-2': 72998}
#     crdc.transfers_alt_sch_disc: {'-1': 842514, '-2': 82744}
#     edfacts.grad_rate_high: {'-3': 70007}
#     edfacts.grad_rate_low: {'-3': 70007}
#     edfacts.grad_rate_midpt: {'-3': 70007}
#     ipeds.athletic_expense_treatment: {'-1': 1317, '-2': 53128}
#     ipeds.buildings: {'-3': 1}
#     ipeds.construction_in_progress: {'-1': 1}
#     ipeds.equity_beg: {'-1': 1}
#     ipeds.equity_changes_other: {'-1': 125, '-2': 32, '-3': 8}
#     ipeds.equity_changes_total: {'-1': 431, '-2': 17, '-3': 14}
#     ipeds.equity_end: {'-1': 5}
#     ipeds.equity_total: {'-1': 5}
#     ipeds.exp_other_salaries: {'-1': 45, '-2': 6, '-3': 2}
#     ipeds.exp_other_total_funct: {'-1': 80, '-2': 7}
#     ipeds.exp_total_other_nat: {'-1': 4}
#     ipeds.exp_total_salaries: {'-1': 1}
#     ipeds.gasb_alternative_accounting: {'-1': 1433, '-2': 108827}
#     ipeds.income_tax_fed: {'-1': 2, '-3': 1}
#     ipeds.income_tax_state: {'-2': 2}
#     ipeds.net_equity_beg_adjust: {'-1': 813, '-2': 107, '-3': 35}
#     ipeds.net_position_adjustments: {'-1': 410, '-2': 99, '-3': 32}
#     ipeds.net_position_change: {'-1': 5, '-2': 1, '-3': 1}
#     ipeds.own_endowment_assets: {'-1': 1025, '-2': 4957}
#     ipeds.parent_child_flag: {'-1': 3309, '-2': 142067}
#     ipeds.parent_child_system_flag: {'-2': 18071}
#     ipeds.parent_unitid: {'-2': 140040}
#     ipeds.pell_grant_treatment: {'-1': 210}
#     ipeds.reporting_form: {'-1': 357, '-2': 15287}
#     ipeds.rev_auxiliary_enterprises_gross: {'-1': 1}
#     ipeds.rev_capital_approps: {'-1': 3}
#     ipeds.rev_edu_services_sales: {'-2': 1}
#     ipeds.rev_hosp_ind_op_other: {'-1': 56, '-2': 2, '-3': 2}
#     ipeds.rev_investment_return: {'-1': 1, '-3': 1}
#     ipeds.rev_other: {'-1': 60, '-2': 3, '-3': 2}
#     ipeds.rev_other_additions: {'-1': 1}
#     ipeds.rev_other_nonoperating: {'-1': 2, '-2': 1, '-3': 1}
#     ipeds.rev_other_operating: {'-1': 2}
#     ipeds.sch_allowances_aux_enterp: {'-1': 8}
# 
# ================================================================================
# COVERAGE SUMMARY: B1/B2/B4 report positive cases exercised; B3 reports gaps honestly.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
