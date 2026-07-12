#!/usr/bin/env python3
"""
Programmatic diff of the Python vs R capture JSON files -> PASS/FAIL matrix.

INTENT: consume capture_python.json and capture_r.json and, per dataset, run the
7 equivalence checks + int64 depth. Emit a dataset x check matrix and enumerate
EVERY discrepancy precisely (column, type, magnitude, which side deviates). No
eyeball comparison — this script is the arbiter.

Check taxonomy:
  C1 shape+colnames+order        C5 sample-row value equality (all cols)
  C2 per-column type mapping      C6 string integrity (NA/empty, leading zeros, non-ASCII)
  C3 null counts (exact)          C7 distinct counts on key cols
  C4 sentinel counts (exact)      I  int64 depth (downcast/precision)

Float comparison uses relative tolerance 1e-9 (abs fallback for near-zero).
Integers and strings require exact equality.
"""

# --- Config ---
import os
import json

SCRATCH = "/daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch"
PY = os.path.join(SCRATCH, "capture_python.json")
R = os.path.join(SCRATCH, "capture_r.json")
FLOAT_RTOL = 1e-9
FLOAT_ATOL = 1e-12

with open(PY) as f:
    py = json.load(f)
with open(R) as f:
    rr = json.load(f)

print(f"Python engine: {py['engine']} {py.get('polars_version')}")
print(f"R engine     : {rr['engine']} {rr.get('arrow_version')} | int64_downcast={rr.get('int64_downcast')}")

# INTENT: expected Python->R type-class mapping. Both sides emit our dtype_class
#   taxonomy (int/float/bool/str/other), so class must match exactly regardless of
#   the underlying physical representation (integer64 vs integer both -> "int").
def floats_equal(a, b):
    # a, b are string reprs from each side; parse and compare with tolerance.
    if a == "NaN" or b == "NaN":
        return a == b  # NaN matches only NaN
    fa = float(a); fb = float(b)
    if fa == fb:
        return True
    denom = max(abs(fa), abs(fb))
    if denom < FLOAT_ATOL:
        return abs(fa - fb) < FLOAT_ATOL
    return abs(fa - fb) / denom < FLOAT_RTOL

def cell_equal(pc, rc):
    # pc, rc are {"t":..,"v":..}. Compare by class.
    # REASONING: null<->null match; NaN handled in float branch. Type-class mismatch
    #   (e.g. one side int, other float) is itself a discrepancy we surface.
    pt, pv = pc["t"], pc["v"]
    rt, rv = rc["t"], rc["v"]
    if pt == "null" or rt == "null":
        return pt == rt, f"null-mismatch py={pt}:{pv} r={rt}:{rv}" if pt != rt else None
    if pt != rt:
        # int vs float is a soft mismatch worth flagging but numeric value may agree
        if {pt, rt} == {"int", "float"}:
            ok = floats_equal(str(pv), str(rv))
            return ok, None if ok else f"int/float value differ py={pv} r={rv}"
        return False, f"type-class mismatch py={pt} r={rt} (vals {pv!r}/{rv!r})"
    if pt == "float":
        ok = floats_equal(pv, rv)
        return ok, None if ok else f"float differ py={pv} r={rv}"
    if pt == "int":
        ok = str(pv) == str(rv)
        return ok, None if ok else f"int differ py={pv} r={rv}"
    if pt == "bool":
        ok = bool(pv) == bool(rv)
        return ok, None if ok else f"bool differ py={pv} r={rv}"
    # str: byte equality
    ok = pv == rv
    return ok, None if ok else f"str differ py={pv!r} r={rv!r}"

CHECKS = ["C1_shape_cols", "C2_type_map", "C3_nulls", "C4_sentinels",
          "C5_values", "C6_strings", "C7_distinct", "I_int64"]

matrix = {}
findings = []  # (severity, dataset, check, detail)
type_map_rows = []  # (dataset, column, py_dtype, py_class, r_dtype, r_class)

keys = list(py["datasets"].keys())
for k in keys:
    P = py["datasets"][k]
    if k not in rr["datasets"]:
        matrix[k] = {c: "FAIL" for c in CHECKS}
        findings.append(("BLOCKER", k, "C1_shape_cols", "dataset missing from R capture"))
        continue
    Rd = rr["datasets"][k]
    row = {c: "PASS" for c in CHECKS}

    # C1: shape + column names + order
    if P["shape"] != Rd["shape"]:
        row["C1_shape_cols"] = "FAIL"
        findings.append(("BLOCKER", k, "C1_shape_cols", f"shape py={P['shape']} r={Rd['shape']}"))
    if P["columns"] != Rd["columns"]:
        row["C1_shape_cols"] = "FAIL"
        # find first difference
        detail = f"column names/order differ; py[:5]={P['columns'][:5]} r[:5]={Rd['columns'][:5]}"
        findings.append(("BLOCKER", k, "C1_shape_cols", detail))

    # C2: per-column type-class mapping (must be identical class)
    for c in P["columns"]:
        if c not in Rd["dtype_class"]:
            continue
        pcls = P["dtype_class"][c]; rcls = Rd["dtype_class"][c]
        pdt = P["dtypes"][c]; rdt = Rd["dtypes"][c]
        type_map_rows.append((k, c, pdt, pcls, rdt, rcls))
        if pcls != rcls:
            row["C2_type_map"] = "FAIL"
            findings.append(("WARNING", k, "C2_type_map",
                             f"col '{c}': class py={pcls}({pdt}) r={rcls}({rdt})"))

    # C3: null counts exact
    for c in P["columns"]:
        if c in Rd["null_counts"]:
            if int(P["null_counts"][c]) != int(Rd["null_counts"][c]):
                row["C3_nulls"] = "FAIL"
                findings.append(("BLOCKER", k, "C3_nulls",
                                 f"col '{c}': nulls py={P['null_counts'][c]} r={Rd['null_counts'][c]}"))

    # C4: sentinel counts exact (only cols present in both)
    for c, psc in P["sentinel_counts"].items():
        rsc = Rd["sentinel_counts"].get(c)
        if rsc is None:
            # column numeric on one side only -> caught by C2; note here too
            row["C4_sentinels"] = "FAIL"
            findings.append(("WARNING", k, "C4_sentinels", f"col '{c}': sentinel set missing on R side"))
            continue
        for s in ["-1", "-2", "-3"]:
            pv = int(psc.get(s, 0)); rv = int(rsc.get(s, 0))
            if pv != rv:
                row["C4_sentinels"] = "FAIL"
                findings.append(("BLOCKER", k, "C4_sentinels",
                                 f"col '{c}' sentinel {s}: py={pv} r={rv}"))

    # C5: sample-row value equality (head5 + tail5, all cols)
    for part in ["head5", "tail5"]:
        pr = P["sample_rows"][part]; rrows = Rd["sample_rows"][part]
        if len(pr) != len(rrows):
            row["C5_values"] = "FAIL"
            findings.append(("BLOCKER", k, "C5_values", f"{part} row count py={len(pr)} r={len(rrows)}"))
            continue
        for i, (prow, rrow) in enumerate(zip(pr, rrows)):
            for c in P["columns"]:
                if c not in rrow:
                    continue
                ok, det = cell_equal(prow[c], rrow[c])
                if not ok:
                    row["C5_values"] = "FAIL"
                    findings.append(("BLOCKER", k, "C5_values", f"{part}[{i}] col '{c}': {det}"))

    # C6: string integrity
    for c, psi in P["string_integrity"].items():
        rsi = Rd["string_integrity"].get(c)
        if rsi is None:
            row["C6_strings"] = "FAIL"
            findings.append(("WARNING", k, "C6_strings", f"col '{c}': not a string col on R side"))
            continue
        if int(psi["n_null"]) != int(rsi["n_null"]):
            row["C6_strings"] = "FAIL"
            findings.append(("BLOCKER", k, "C6_strings", f"col '{c}': n_null py={psi['n_null']} r={rsi['n_null']}"))
        if int(psi["n_empty"]) != int(rsi["n_empty"]):
            row["C6_strings"] = "FAIL"
            findings.append(("BLOCKER", k, "C6_strings", f"col '{c}': n_empty py={psi['n_empty']} r={rsi['n_empty']}"))
        if "n_leading_zero" in psi and "n_leading_zero" in rsi:
            if int(psi["n_leading_zero"]) != int(rsi["n_leading_zero"]):
                row["C6_strings"] = "FAIL"
                findings.append(("BLOCKER", k, "C6_strings",
                                 f"col '{c}': n_leading_zero py={psi['n_leading_zero']} r={rsi['n_leading_zero']}"))
            if psi.get("leading_zero_samples") != rsi.get("leading_zero_samples"):
                row["C6_strings"] = "FAIL"
                findings.append(("BLOCKER", k, "C6_strings",
                                 f"col '{c}': leading_zero_samples differ py={psi.get('leading_zero_samples')} r={rsi.get('leading_zero_samples')}"))
        # non-ASCII
        if int(psi.get("non_ascii_count_est", 0)) != int(rsi.get("non_ascii_count_est", 0)):
            row["C6_strings"] = "FAIL"
            findings.append(("BLOCKER", k, "C6_strings",
                             f"col '{c}': non_ascii_count py={psi.get('non_ascii_count_est')} r={rsi.get('non_ascii_count_est')}"))
        # byte-level: compare non-ascii sample values + codepoints
        pna = {s["value"]: s["codepoints"] for s in psi.get("non_ascii_samples", [])}
        rna = {s["value"]: s["codepoints"] for s in rsi.get("non_ascii_samples", [])}
        if pna != rna:
            row["C6_strings"] = "FAIL"
            findings.append(("BLOCKER", k, "C6_strings",
                             f"col '{c}': non-ASCII byte content differs py={pna} r={rna}"))

    # C7: distinct counts on key cols
    for c, pv in P["distinct_counts"].items():
        rv = Rd["distinct_counts"].get(c)
        if rv is None:
            row["C7_distinct"] = "FAIL"
            findings.append(("WARNING", k, "C7_distinct", f"col '{c}': distinct count missing on R side"))
            continue
        if int(pv) != int(rv):
            row["C7_distinct"] = "FAIL"
            findings.append(("BLOCKER", k, "C7_distinct", f"col '{c}': distinct py={pv} r={rv}"))

    # I: int64 depth — min/max exact match + downcast/precision documentation
    for c, pstat in P["int_stats"].items():
        rstat = Rd["int_stats"].get(c)
        if rstat is None:
            # column integer on py side but not int on R side (or vice versa)
            row["I_int64"] = "FAIL"
            findings.append(("WARNING", k, "I_int64", f"col '{c}': int on py, not int-class on R"))
            continue
        # exact min/max string comparison (precision loss would show here)
        if pstat.get("min") != rstat.get("min") or pstat.get("max") != rstat.get("max"):
            row["I_int64"] = "FAIL"
            findings.append(("BLOCKER", k, "I_int64",
                             f"col '{c}': min/max differ py=[{pstat.get('min')},{pstat.get('max')}] "
                             f"r=[{rstat.get('min')},{rstat.get('max')}]"))
        if bool(pstat.get("exceeds_2_31")) != bool(rstat.get("exceeds_2_31")):
            row["I_int64"] = "FAIL"
            findings.append(("WARNING", k, "I_int64",
                             f"col '{c}': exceeds_2_31 disagreement py={pstat.get('exceeds_2_31')} r={rstat.get('exceeds_2_31')}"))

    matrix[k] = row

# --- PASS/FAIL matrix ---
print("\n" + "=" * 90)
print("PASS/FAIL MATRIX (dataset x check)")
print("=" * 90)
hdr = f"{'dataset':10s} " + " ".join(f"{c.split('_')[0]:>5s}" for c in CHECKS)
print(hdr)
for k in keys:
    cells = " ".join(f"{('P' if matrix[k][c]=='PASS' else 'F'):>5s}" for c in CHECKS)
    print(f"{k:10s} {cells}")
print("\nLegend: C1=shape/cols C2=type-map C3=nulls C4=sentinels C5=values C6=strings C7=distinct I=int64")

# --- int64 depth report ---
print("\n" + "=" * 90)
print("INT64 DEPTH REPORT")
print("=" * 90)
for k in keys:
    P = py["datasets"][k]; Rd = rr["datasets"].get(k, {})
    for c, pstat in P["int_stats"].items():
        rstat = Rd.get("int_stats", {}).get(c, {})
        ge = pstat.get("exceeds_2_31")
        r_i64 = rstat.get("r_is_integer64")
        # only print notable ones: >=2^31 OR integer64 on R side
        if ge or r_i64:
            match = "EXACT-MATCH" if (pstat.get("min")==rstat.get("min") and pstat.get("max")==rstat.get("max")) else "MISMATCH"
            print(f"  {k}.{c}: py_dtype={pstat.get('dtype')} max={pstat.get('max')} "
                  f">=2^31={ge} | R integer64={r_i64} R_dtype={rstat.get('dtype')} | min/max {match}")

# --- observed type-mapping table (unique class pairs) ---
print("\n" + "=" * 90)
print("OBSERVED PYTHON->R TYPE MAPPING (unique dtype pairs)")
print("=" * 90)
seen = {}
for (k, c, pdt, pcls, rdt, rcls) in type_map_rows:
    key = (pdt, rdt)
    seen.setdefault(key, []).append(f"{k}.{c}")
for (pdt, rdt), examples in sorted(seen.items()):
    print(f"  py:{pdt:12s} -> R:{rdt:20s}  (n={len(examples)}, e.g. {examples[0]})")

# --- findings ---
print("\n" + "=" * 90)
print(f"FINDINGS ({len(findings)} total)")
print("=" * 90)
for sev in ["BLOCKER", "WARNING", "INFO"]:
    subset = [f for f in findings if f[0] == sev]
    print(f"\n[{sev}] {len(subset)}")
    for (_, ds, chk, det) in subset[:80]:
        print(f"  {ds}/{chk}: {det}")

# --- overall verdict ---
n_fail = sum(1 for k in keys for c in CHECKS if matrix[k][c] == "FAIL")
n_blocker = sum(1 for f in findings if f[0] == "BLOCKER")
print("\n" + "=" * 90)
print(f"OVERALL: {len(keys)} datasets x {len(CHECKS)} checks; {n_fail} failing cells; {n_blocker} BLOCKER findings")
print("VERDICT:", "PASS (equivalent)" if n_blocker == 0 else "DRIFT DETECTED — see BLOCKER findings")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 19:29:53
# Command: python3 /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/smoke_tests/04_compare-captures.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# Python engine: polars 1.38.1
# R engine     : arrow_r 23.0.1.2 | int64_downcast=unset_default_true
# 
# ==========================================================================================
# PASS/FAIL MATRIX (dataset x check)
# ==========================================================================================
# dataset       C1    C2    C3    C4    C5    C6    C7     I
# crdc           P     P     P     P     P     P     P     P
# edfacts        P     P     P     P     P     P     P     P
# ipeds          P     P     P     P     P     P     P     P
# meps           P     P     P     P     P     P     P     P
# saipe          P     P     P     P     P     P     P     P
# 
# Legend: C1=shape/cols C2=type-map C3=nulls C4=sentinels C5=values C6=strings C7=distinct I=int64
# 
# ==========================================================================================
# INT64 DEPTH REPORT
# ==========================================================================================
#   edfacts.ncessch: py_dtype=Int64 max=720003002085 >=2^31=True | R integer64=True R_dtype=integer64 | min/max EXACT-MATCH
#   edfacts.ncessch_num: py_dtype=Int64 max=720003002085 >=2^31=True | R integer64=True R_dtype=integer64 | min/max EXACT-MATCH
#   meps.ncessch: py_dtype=Int64 max=568025600581 >=2^31=True | R integer64=True R_dtype=integer64 | min/max EXACT-MATCH
#   meps.ncessch_num: py_dtype=Int64 max=568025600581 >=2^31=True | R integer64=True R_dtype=integer64 | min/max EXACT-MATCH
# 
# ==========================================================================================
# OBSERVED PYTHON->R TYPE MAPPING (unique dtype pairs)
# ==========================================================================================
#   py:Float64      -> R:numeric               (n=133, e.g. crdc.transfers_alt_sch_disc)
#   py:Int64        -> R:integer               (n=56, e.g. crdc.year)
#   py:Int64        -> R:integer64             (n=4, e.g. edfacts.ncessch_num)
#   py:String       -> R:character             (n=7, e.g. crdc.crdc_id)
# 
# ==========================================================================================
# FINDINGS (0 total)
# ==========================================================================================
# 
# [BLOCKER] 0
# 
# [WARNING] 0
# 
# [INFO] 0
# 
# ==========================================================================================
# OVERALL: 5 datasets x 8 checks; 0 failing cells; 0 BLOCKER findings
# VERDICT: PASS (equivalent)
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
