#!/usr/bin/env python3
"""
Full-column hash comparison (Python side) for the highest-risk columns.

RATIONALE: checks C5 in 04 only sampled head5+tail5 (10 rows). Mid-file drift —
e.g. a single non-ASCII value mangled at row 150,000, or one int64 truncated deep
in the file — would slip past a 10-row sample. This script computes an
order-independent, value-exact digest over the ENTIRE column for the risk columns,
so the R counterpart (07) can prove whole-column byte/value equivalence.

Digest design (per column):
  - strings: sort unique (value, count) pairs; hash the UTF-8 bytes + counts.
    Order-independent (we sort), so R's row order need not match; value+multiplicity
    must. Byte-level: we hash raw UTF-8, so any encoding drift changes the digest.
  - integers: sort unique (value_as_decimal_string, count); hash. Exact — a 32-bit
    truncation anywhere changes a value string and thus the digest.
  - floats: EXCLUDED from hashing (float repr differs cross-language by design);
    covered instead by null/sentinel/sample-tolerance checks.

Risk columns chosen: the string_view column (saipe.district_name), all CRDC
zero-padded IDs, and the big int64 IDs (meps/edfacts ncessch*).
"""

# --- Config ---
import os
import json
import hashlib
import polars as pl

SCRATCH = "/daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch"
OUT = os.path.join(SCRATCH, "fullcol_python.json")

# (dataset_key, filename, [columns to fully hash], kind)
TARGETS = [
    ("saipe", "saipe_districts_FAILING.parquet", ["district_name"], "str"),
    ("crdc", "crdc_discipline_2017.parquet", ["crdc_id", "ncessch", "leaid"], "str"),
    ("meps", "meps_schools_WORKING.parquet", ["ncessch", "ncessch_num"], "int"),
    ("edfacts", "edfacts_grad_rates_2018.parquet", ["ncessch", "ncessch_num"], "int"),
]

def digest_str_col(series):
    # INTENT: value+multiplicity digest, order-independent, byte-exact on UTF-8.
    # REASONING: group by value (nulls -> a reserved token), sort by value, feed
    #   raw UTF-8 bytes + count to sha256. Any mangled character changes the hash.
    vc = series.value_counts()  # columns: [<name>, count]
    name = series.name
    rows = vc.sort(name, nulls_last=True).to_dicts()
    h = hashlib.sha256()
    n_null = 0
    for r in rows:
        v = r[name]; cnt = r["count"]
        if v is None:
            n_null = cnt
            h.update(b"\x00NULL\x00")
        else:
            h.update(v.encode("utf-8"))
            h.update(b"\x01")
        h.update(str(cnt).encode("ascii"))
        h.update(b"\x02")
    return h.hexdigest(), len(rows), int(n_null)

def digest_int_col(series):
    # INTENT: exact-value digest for integers rendered as decimal strings.
    vc = series.value_counts()
    name = series.name
    rows = vc.to_dicts()
    # sort by integer value (nulls last) — build (str, count) then sort by numeric
    pairs = []
    n_null = 0
    for r in rows:
        v = r[name]; cnt = r["count"]
        if v is None:
            n_null = cnt
        else:
            pairs.append((int(v), cnt))
    pairs.sort()
    h = hashlib.sha256()
    for v, cnt in pairs:
        h.update(str(v).encode("ascii")); h.update(b"\x01")
        h.update(str(cnt).encode("ascii")); h.update(b"\x02")
    if n_null:
        h.update(b"\x00NULL\x00"); h.update(str(n_null).encode("ascii"))
    return h.hexdigest(), len(pairs), int(n_null)

# --- Load + digest ---
result = {"engine": "polars", "columns": {}}
for key, fname, cols, kind in TARGETS:
    df = pl.read_parquet(os.path.join(SCRATCH, fname), columns=cols)
    print(f"\n### {key}: {cols} ({kind})")
    for c in cols:
        s = df[c]
        if kind == "str":
            dig, ndistinct, nnull = digest_str_col(s)
        else:
            dig, ndistinct, nnull = digest_int_col(s)
        result["columns"][f"{key}.{c}"] = {"digest": dig, "n_distinct": ndistinct, "n_null": nnull, "kind": kind}
        print(f"    {c:14s} digest={dig[:16]}... distinct={ndistinct} null={nnull}")

# --- Save ---
with open(OUT, "w") as f:
    json.dump(result, f, indent=1, sort_keys=True)
print(f"\nWrote {OUT}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 19:31:24
# Command: python3 /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/smoke_tests/06_python-fullcol-hash.py
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# 
# ### saipe: ['district_name'] (str)
#     district_name  digest=21c3a400c9efb340... distinct=36517 null=0
# 
# ### crdc: ['crdc_id', 'ncessch', 'leaid'] (str)
#     crdc_id        digest=6196ab3b1b441b68... distinct=97632 null=0
#     ncessch        digest=3f4c0027e2b70f2d... distinct=96570 null=81816
#     leaid          digest=5df4aee9ffffd8c9... distinct=16724 null=81816
# 
# ### meps: ['ncessch', 'ncessch_num'] (int)
#     ncessch        digest=780c1afc2aeec29c... distinct=116681 null=0
#     ncessch_num    digest=780c1afc2aeec29c... distinct=116681 null=0
# 
# ### edfacts: ['ncessch', 'ncessch_num'] (int)
#     ncessch        digest=8b41ac5fb6edefe6... distinct=22900 null=0
#     ncessch_num    digest=8b41ac5fb6edefe6... distinct=22900 null=0
# 
# Wrote /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch/fullcol_python.json
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
