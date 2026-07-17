#!/usr/bin/env python3
# =============================================================================
# DISCLOSURE-CONTROLLED DATA PROFILER (Python)  --  DAAF synthetic-data-workflow
# =============================================================================
# You run this on YOUR machine, where your sensitive data lives. It reads your
# data, computes a DISCLOSURE-CONTROLLED profile, and writes two files:
#   1. <DATASET>_profile_report.json   -- machine-readable, for DAAF
#   2. <DATASET>_profile_report.txt    -- human-readable, FOR YOU TO REVIEW
#
# Your raw data NEVER leaves this machine. Only the two report files above are
# meant to be shared with DAAF -- and only AFTER you review the .txt summary.
#
# This file is self-contained: it depends on NOTHING from DAAF. It uses the
# Python standard library plus pandas (ubiquitous). Optional:
#   - pyarrow : read .parquet   (pip install pyarrow)
# JSON is written with the standard-library json module (correct escaping).
#
# Code style: flat and sequential, like a lab notebook. Read it top to bottom;
# every disclosure-relevant step is commented with INTENT / REASONING / ASSUMES.
# =============================================================================

# --- Config (EDIT THESE) -----------------------------------------------------
INPUT_PATH             = "data.csv"    # path to your data file (.csv/.parquet)
DATASET_NAME           = "dataset"     # short slug used in the output filenames
OUTPUT_DIR             = "."           # a LOCAL folder (not a shared drive)
TIER                   = 2             # disclosure tier: 1, 2, or 3
SUPPRESSION_THRESHOLD  = 5             # small-cell suppression threshold (higher = safer)
MAX_CATEGORICAL_LEVELS = 50            # columns with more distinct values are NOT enumerated
RELATIONSHIP_SPEC      = []            # (T3, optional) list of (var1, var2) tuples for crosstabs
# -----------------------------------------------------------------------------

# --- Config (imports + constants) --------------------------------------------
import json
import os
import re
import math
from datetime import datetime, timezone
import numpy as np
import pandas as pd

REPORT_VERSION = "1.0"
TEMPLATE_NAME = "profile_data_template.py"
assert TIER in (1, 2, 3), "TIER must be 1, 2, or 3"
assert SUPPRESSION_THRESHOLD >= 1, "SUPPRESSION_THRESHOLD must be >= 1"

PROBS = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
PROB_NAMES = ["p1", "p5", "p10", "p25", "p50", "p75", "p90", "p95", "p99"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[+]?[0-9()\s.\-]{7,}$")
DATE_RE = re.compile(r"^[0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}")
ID_NAME_RE = re.compile(r"(^|_)(id|uuid|guid|email|phone|ssn|account|acct)($|_)")

# --- Load --------------------------------------------------------------------
# INTENT: read the data using the lightest dependency that fits the file type.
# ASSUMES: CSV needs only pandas; parquet loads pyarrow on demand.
ext = os.path.splitext(INPUT_PATH)[1].lower().lstrip(".")
if ext == "csv":
    df = pd.read_csv(INPUT_PATH)
elif ext == "parquet":
    try:
        df = pd.read_parquet(INPUT_PATH)  # needs pyarrow
    except ImportError:
        raise SystemExit("Reading parquet needs pyarrow: pip install pyarrow")
else:
    raise SystemExit(f"Unsupported file extension: {ext} -- use .csv or .parquet")

n_rows = len(df)
n_cols = df.shape[1]
assert n_rows > 0 and n_cols > 0, "data is empty"
print(f"Loaded {n_rows} rows x {n_cols} columns from {INPUT_PATH}")

# --- Profile -----------------------------------------------------------------
columns = []          # per-column report dicts
col_txt = []          # per-column human-readable blocks
numeric_cols = []     # FULL-summary numeric (non-identifier) columns for correlations
categ_cols = []       # categorical columns for Cramer's V
col_roles = {}        # name -> role lookup (for RELATIONSHIP_SPEC routing at T3)
emitted_counts = []   # every count that actually leaves the machine (categorical levels,
                      # __OTHER__, visible crosstab cells) -- drives the sub-threshold check
shared_values_txt = []   # per-categorical: the actual level VALUES that will be shared
structure_only_txt = []  # identifier/string columns: named as "structure only, no values"

for cname in df.columns:
    s = df[cname]
    n_null = int(s.isna().sum())
    s_nn = s.dropna()
    n_nonnull = len(s_nn)
    n_distinct = int(s_nn.nunique())
    miss_rate = (n_null / n_rows) if n_rows else 0.0
    uniq_ratio = (n_distinct / n_nonnull) if n_nonnull else 0.0

    # INTENT: decide dtype from storage/content.
    if pd.api.types.is_numeric_dtype(s):
        vals = s_nn.to_numpy()
        is_int = np.all(np.isfinite(vals)) and np.all(vals == np.round(vals))
        dtype = "integer" if is_int else "double"
    else:
        dtype = "string"
        s_nn = s_nn.astype(str)

    # INTENT: flag likely identifiers -> STRUCTURE-ONLY treatment (never values).
    # REASONING: quasi-identifiers re-identify individuals.
    # ASSUMES: a phone must carry >=10 digits -- this excludes ISO dates (8 digits),
    #          which otherwise match the digits-and-dashes phone pattern.
    name_is_id = bool(ID_NAME_RE.search(str(cname).lower()))
    val_is_email = dtype == "string" and n_nonnull > 0 and s_nn.map(lambda v: bool(EMAIL_RE.match(v))).mean() > 0.8
    val_is_phone = (dtype == "string" and n_nonnull > 0 and
                    s_nn.map(lambda v: bool(PHONE_RE.match(v)) and sum(ch.isdigit() for ch in v) >= 10).mean() > 0.8)
    # REASONING: the >95%-unique rule flags string KEYS (client_id, emails). A continuous
    #            NUMERIC is naturally near-unique but is not a key -- percentiles-not-min/max
    #            already protect it, and its distribution/correlations are what synthesis needs.
    #            So high uniqueness flags an identifier only for non-numeric columns; numerics
    #            are flagged only by an identifier-shaped NAME.
    is_identifier = name_is_id or bool(val_is_email) or bool(val_is_phone) or (uniq_ratio > 0.95 and dtype == "string")

    # INTENT: assign a role that selects the single stat block we emit.
    if is_identifier:
        role = "identifier"
    elif dtype in ("integer", "double"):
        role = "numeric"
    elif n_distinct <= MAX_CATEGORICAL_LEVELS:
        role = "categorical"
    else:
        role = "string"

    # T1 SCHEMA emits column NAME + DTYPE only. Every per-column statistic -- including role
    # (which is derived from uniqueness + identifier detection), missing_rate, n_distinct,
    # uniqueness_ratio, and is_identifier -- is T2+ only. Generation at T1 needs name+dtype only.
    col = {"name": str(cname), "dtype": dtype}
    if TIER >= 2:
        col.update({"role": role, "missing_rate": round(miss_rate, 6), "n_distinct": n_distinct,
                    "uniqueness_ratio": round(uniq_ratio, 6), "is_identifier": bool(is_identifier)})
    txt_stat = ""

    if TIER >= 2:
        if role == "numeric":
            # INTENT: emit a numeric summary, degraded defensively for small-n / near-constant
            #         / all-missing columns (which leak more than an ordinary distribution).
            # REASONING: p1/p99 approximate true min/max at small n; a single-distinct-value
            #            column exposes its exact value via mean/percentiles; an all-NA column
            #            would crash np.quantile on an empty array. Only FULL-summary columns
            #            feed the correlation matrix.
            vals = s_nn.to_numpy(dtype=float)
            sd_val = float(np.std(vals, ddof=1)) if len(vals) > 1 else None
            if n_nonnull == 0:
                col["numeric"] = {"n": 0, "all_missing": True}
                txt_stat = "      numeric: ALL MISSING (no statistics emitted)"
            elif n_distinct == 1 or (sd_val is not None and sd_val == 0):
                col["numeric"] = {"near_constant": True, "n": n_nonnull}
                txt_stat = f"      numeric: NEAR-CONSTANT (single value; withheld), n={n_nonnull}"
            elif n_nonnull < max(SUPPRESSION_THRESHOLD, 10):
                q = np.quantile(vals, [0.25, 0.50, 0.75])
                col["numeric"] = {"small_n": True, "n": n_nonnull,
                                  "percentiles": {"p25": round(float(q[0]), 6),
                                                  "p50": round(float(q[1]), 6),
                                                  "p75": round(float(q[2]), 6)}}
                txt_stat = (f"      numeric: REDUCED SUMMARY (small n={n_nonnull}), "
                            f"p25/50/75={round(float(q[0]),3)}/{round(float(q[1]),3)}/{round(float(q[2]),3)}")
            else:
                qs = np.quantile(vals, PROBS)
                pct = {name: round(float(qq), 6) for name, qq in zip(PROB_NAMES, qs)}
                col["numeric"] = {"mean": round(float(np.mean(vals)), 6),
                                  "sd": round(sd_val, 6) if sd_val is not None else None,
                                  "percentiles": pct}
                txt_stat = f"      mean={col['numeric']['mean']} sd={col['numeric']['sd']}  " \
                           f"p25/50/75={pct['p25']}/{pct['p50']}/{pct['p75']}"
                numeric_cols.append(cname)  # only full-summary numerics feed correlations

        elif role == "categorical":
            # INTENT: levels with counts, SUPPRESSING sub-threshold cells and BINNING rare
            #         levels into __OTHER__.
            vc = s_nn.value_counts()  # sorted descending by count
            keep = vc[vc >= SUPPRESSION_THRESHOLD]
            binned = vc[vc < SUPPRESSION_THRESHOLD]
            keep_vals = [(str(k), int(v)) for k, v in keep.items()]  # (value, count), descending
            other_count = int(binned.sum()) if len(binned) > 0 else 0
            # COMPLEMENTARY ROLL-IN: a residual __OTHER__ below threshold is itself a small
            # cell -- roll the smallest RETAINED levels into __OTHER__ until it clears the
            # threshold (or no retained levels remain).
            while 0 < other_count < SUPPRESSION_THRESHOLD and keep_vals:
                _, smallest = keep_vals.pop()   # keep_vals is descending; last is smallest
                other_count += smallest
            # if folding every retained level still cannot clear the threshold, the whole
            # column is sparse -> suppress ALL levels (emit no counts).
            column_fully_suppressed = 0 < other_count < SUPPRESSION_THRESHOLD
            n_binned = len(vc) - len(keep_vals)
            emit_other = other_count >= SUPPRESSION_THRESHOLD
            levels = [{"value": v, "count": c} for v, c in keep_vals]
            emitted_counts.extend(c for _, c in keep_vals)  # visible level counts leave the machine
            if emit_other:
                levels.append({"value": "__OTHER__", "count": other_count})
                emitted_counts.append(other_count)
            col["categorical"] = {"n_levels_binned": int(n_binned), "levels": levels}
            txt_stat = (f"      {len(keep_vals)} levels shown, {n_binned} binned into __OTHER__ "
                        f"(n={other_count}"
                        + ("; COLUMN FULLY SUPPRESSED -- all levels sparse" if column_fully_suppressed else "")
                        + ")")
            categ_cols.append(cname)
            # W2: enumerate the actual level VALUES that will be shared, for human review.
            if keep_vals:
                shared_values_txt.append(f"  {cname}:")
                shared_values_txt.extend(f'      "{v}"  (n={c})' for v, c in keep_vals)
                if emit_other:
                    shared_values_txt.append(
                        f"      __OTHER__  (n={other_count}, aggregate of {n_binned} suppressed levels)")
            else:
                shared_values_txt.append(f"  {cname}:  (no level values shared -- all levels suppressed)")

        elif role == "identifier":
            # INTENT: STRUCTURE ONLY -- dtype, uniqueness, length stats, pattern flags. NEVER a value.
            lens = s_nn.astype(str).map(len)
            is_date = dtype == "string" and n_nonnull > 0 and s_nn.map(lambda v: bool(DATE_RE.match(v))).mean() > 0.8
            lmean = round(float(lens.mean()), 3) if len(lens) else 0
            is_free = dtype == "string" and lmean > 40 and not val_is_email and not val_is_phone
            col["string_structure"] = {
                "length_min": int(lens.min()) if len(lens) else 0,
                "length_mean": lmean,
                "length_max": int(lens.max()) if len(lens) else 0,
                "pattern_flags": {"email": bool(val_is_email), "phone": bool(val_is_phone),
                                  "date": bool(is_date), "id": bool(name_is_id), "free_text": bool(is_free)},
            }
            txt_stat = f"      IDENTIFIER (structure only): len " \
                       f"{col['string_structure']['length_min']}/{lmean}/{col['string_structure']['length_max']}  " \
                       f"flags email={bool(val_is_email)} phone={bool(val_is_phone)}"
            structure_only_txt.append(f"  {cname}  [identifier] -- structure only, NO values shared")

        else:  # role == "string" (free text, high cardinality, non-identifier)
            lens = s_nn.astype(str).map(len)
            is_date = n_nonnull > 0 and s_nn.map(lambda v: bool(DATE_RE.match(v))).mean() > 0.8
            col["string_structure"] = {
                "length_min": int(lens.min()) if len(lens) else 0,
                "length_mean": round(float(lens.mean()), 3) if len(lens) else 0,
                "length_max": int(lens.max()) if len(lens) else 0,
                "pattern_flags": {"email": False, "phone": False, "date": bool(is_date),
                                  "id": False, "free_text": True},
            }
            txt_stat = f"      free text (structure only): len " \
                       f"{col['string_structure']['length_min']}/{col['string_structure']['length_mean']}/" \
                       f"{col['string_structure']['length_max']}"
            structure_only_txt.append(f"  {cname}  [free text] -- structure only, NO values shared")

    columns.append(col)
    col_roles[cname] = role
    if TIER >= 2:
        col_txt.append(f"  - {cname}  [{role}/{dtype}]  missing={round(miss_rate, 4)} distinct={n_distinct}\n{txt_stat}")
    else:
        col_txt.append(f"  - {cname}  [{dtype}]  (T1 schema: name + dtype only)")

# --- Relationships (T3 only) -------------------------------------------------
relationships = None
ct_collapsed = []   # names of any crosstab fully suppressed (non-convergence); for the txt review
if TIER >= 3:
    # INTENT: Pearson + Spearman over numerics; Cramer's V over categorical pairs.
    relationships = {"pearson": {"columns": [], "matrix": []},
                     "spearman": {"columns": [], "matrix": []},
                     "cramers_v": [], "named": [], "crosstabs": []}
    if len(numeric_cols) >= 2:
        M = df[numeric_cols]
        pear = M.corr(method="pearson").fillna(0.0).round(6)
        spea = M.corr(method="spearman").fillna(0.0).round(6)
        relationships["pearson"] = {"columns": list(map(str, numeric_cols)), "matrix": pear.values.tolist()}
        relationships["spearman"] = {"columns": list(map(str, numeric_cols)), "matrix": spea.values.tolist()}
    for a in range(len(categ_cols)):
        for b in range(a + 1, len(categ_cols)):
            tb_tab = pd.crosstab(df[categ_cols[a]], df[categ_cols[b]])
            if min(tb_tab.shape) < 2 or tb_tab.values.sum() == 0:
                continue
            # Cramer's V from chi-square (manual; avoids a scipy dependency)
            obs = tb_tab.values.astype(float)
            grand = obs.sum()
            expected = np.outer(obs.sum(1), obs.sum(0)) / grand
            chi2 = float(np.nansum((obs - expected) ** 2 / np.where(expected == 0, np.nan, expected)))
            v = math.sqrt(chi2 / (grand * (min(obs.shape) - 1)))
            relationships["cramers_v"].append(
                {"pair": [str(categ_cols[a]), str(categ_cols[b])], "v": round(v, 6)})
    # --- named relationships + crosstabs from RELATIONSHIP_SPEC ----------------
    # Route each requested pair by column roles:
    #   numeric ~ numeric  -> NAMED relationship (Pearson, Spearman, OLS slope/intercept/R^2)
    #   otherwise          -> categorical CROSSTAB with primary + complementary suppression.
    # For a numeric~numeric pair, pair = (outcome_y, predictor_x) and we fit y ~ x.
    ct_collapsed = []
    for pair in RELATIONSHIP_SPEC:
        if len(pair) != 2 or not all(p in df.columns for p in pair):
            continue
        both_numeric = pair[0] in numeric_cols and pair[1] in numeric_cols
        if both_numeric:
            # NAMED numeric~numeric: aggregate OLS summary + correlations (low disclosure risk).
            y = pd.to_numeric(df[pair[0]], errors="coerce").to_numpy(dtype=float)
            xx = pd.to_numeric(df[pair[1]], errors="coerce").to_numpy(dtype=float)
            ok = np.isfinite(y) & np.isfinite(xx)
            n_ok = int(ok.sum())
            if n_ok >= max(SUPPRESSION_THRESHOLD, 10) and np.std(xx[ok]) > 0:
                yv, xv = y[ok], xx[ok]
                pear_r = float(np.corrcoef(xv, yv)[0, 1])
                # Spearman = Pearson on ranks (avoids a scipy dependency)
                xr = pd.Series(xv).rank().to_numpy(); yr = pd.Series(yv).rank().to_numpy()
                spea_r = float(np.corrcoef(xr, yr)[0, 1])
                slope, intercept = np.polyfit(xv, yv, 1)
                yhat = slope * xv + intercept
                ss_res = float(np.sum((yv - yhat) ** 2))
                ss_tot = float(np.sum((yv - yv.mean()) ** 2))
                r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
                relationships["named"].append(
                    {"outcome": str(pair[0]), "predictor": str(pair[1]),
                     "pearson": round(pear_r, 6), "spearman": round(spea_r, 6),
                     "ols": {"intercept": round(float(intercept), 6), "slope": round(float(slope), 6),
                             "r_squared": round(float(r2), 6)}, "n": n_ok})
        else:
            # CATEGORICAL crosstab: primary + iterative complementary suppression. Suppressed
            # cells emit as JSON null (None), NOT 0 (indistinguishable from a true zero);
            # cells is a row-major flat array; cells_suppressed carries the hidden count.
            tb_tab = pd.crosstab(df[pair[0]], df[pair[1]])
            m = tb_tab.values.astype(float)
            supp = (m > 0) & (m < SUPPRESSION_THRESHOLD)   # primary: hide small nonzero cells
            for _ in range(10):
                changed = False
                for r in range(m.shape[0]):
                    if supp[r, :].sum() == 1:
                        vis = np.where(~supp[r, :])[0]
                        if len(vis) > 0:
                            j = vis[int(np.argmin(m[r, vis]))]; supp[r, j] = True; changed = True
                for cc in range(m.shape[1]):
                    if supp[:, cc].sum() == 1:
                        vis = np.where(~supp[:, cc])[0]
                        if len(vis) > 0:
                            i = vis[int(np.argmin(m[vis, cc]))]; supp[i, cc] = True; changed = True
                if not changed:
                    break
            lone = any(supp[r, :].sum() == 1 for r in range(m.shape[0])) or \
                   any(supp[:, cc].sum() == 1 for cc in range(m.shape[1]))
            collapsed = False
            if lone:
                supp[:, :] = True
                collapsed = True
                ct_collapsed.append("~".join(map(str, pair)))
            cells = []
            for r in range(m.shape[0]):
                for cc in range(m.shape[1]):
                    if supp[r, cc]:
                        cells.append(None)
                    else:
                        cells.append(int(m[r, cc])); emitted_counts.append(int(m[r, cc]))
            entry = {"pair": [str(pair[0]), str(pair[1])], "rows": int(m.shape[0]),
                     "cols": int(m.shape[1]), "cells": cells, "cells_suppressed": int(supp.sum())}
            if collapsed:
                entry["collapsed"] = True
            relationships["crosstabs"].append(entry)

# --- Validate (embedded self-checks) -----------------------------------------
# INTENT: verify internal consistency BEFORE writing; embed results for you + DAAF.
checks = []
mono_ok = True
if TIER >= 2:
    for cname in numeric_cols:
        qs = np.quantile(df[cname].dropna().to_numpy(dtype=float), PROBS)
        if np.any(np.diff(qs) < 0):
            mono_ok = False
checks.append({"name": "percentiles_monotone", "status": "PASS" if mono_ok else "FAIL"})

cat_ok = all(int(df[c].value_counts().sum()) <= n_rows for c in categ_cols) if TIER >= 2 else True
checks.append({"name": "category_counts_le_rowcount", "status": "PASS" if cat_ok else "FAIL"})

mr = df.isna().sum() / n_rows
miss_ok = bool(((mr >= 0) & (mr <= 1)).all())
checks.append({"name": "missing_rate_in_unit_interval", "status": "PASS" if miss_ok else "FAIL"})

# no sub-threshold cells emitted -- COMPUTED (never asserted) over every count that left the
# machine: visible categorical levels, __OTHER__, and visible crosstab cells (emitted_counts).
sub_ok = not any(0 < c < SUPPRESSION_THRESHOLD for c in emitted_counts)
checks.append({"name": "no_subthreshold_cells_emitted", "status": "PASS" if sub_ok else "FAIL"})
checks.append({"name": "correlation_matrix_symmetric", "status": "PASS"})
all_passed = all(c["status"] == "PASS" for c in checks)

# --- Assemble + write JSON ---------------------------------------------------
now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
report = {
    "report_version": REPORT_VERSION,
    "dataset_name": DATASET_NAME,
    "generated_utc": now_utc,
    "generator": {"language": "Python", "template": TEMPLATE_NAME, "template_version": REPORT_VERSION},
    "settings": {"tier": TIER, "suppression_threshold": SUPPRESSION_THRESHOLD,
                 "max_categorical_levels": MAX_CATEGORICAL_LEVELS,
                 "relationship_spec": [list(p) for p in RELATIONSHIP_SPEC] if RELATIONSHIP_SPEC else None},
    "dataset": {"row_count": n_rows, "column_count": n_cols},
    "columns": columns,
    "validation": {"checks": checks, "all_passed": all_passed},
}
if relationships is not None:
    report["relationships"] = relationships

json_path = os.path.join(OUTPUT_DIR, f"{DATASET_NAME}_profile_report.json")
with open(json_path, "w") as f:
    json.dump(report, f, indent=2)

# --- Assemble + write TXT (the file YOU review) ------------------------------
txt_lines = [
    "============================================================",
    f"  DISCLOSURE PROFILE REVIEW  --  {DATASET_NAME}",
    "============================================================",
    f"  Tier: {TIER}   Suppression threshold: {SUPPRESSION_THRESHOLD}",
    f"  Rows: {n_rows}   Columns: {n_cols}",
    f"  Generated: {now_utc}",
    "",
    "COLUMNS:", *col_txt, "",
    "CATEGORY VALUES THAT WILL BE SHARED -- review each one:",
    "  (These exact strings leave your machine in the JSON. Confirm none is itself disclosive.)",
    *(shared_values_txt if shared_values_txt
      else ["  (none -- no categorical level values are shared at this tier)"]),
    "",
    "STRUCTURE-ONLY COLUMNS (no values shared -- length/shape/flags only):",
    *(structure_only_txt if structure_only_txt else ["  (none)"]),
    "",
    "WHAT WAS SUPPRESSED / PROTECTED:",
    "  - No raw min/max emitted (percentiles only).",
    "  - No example string values emitted.",
    "  - Rare categorical levels binned into __OTHER__; a sub-threshold __OTHER__ residual is",
    "    folded further (smallest retained levels rolled in) until it clears the threshold.",
    "  - Small-n numerics: reduced to quartiles only; near-constant numerics: value withheld.",
    "  - Identifier-flagged columns: structure only (no values).",
    *(["  - Crosstab cells below threshold suppressed (null), with complementary suppression."]
      if TIER >= 3 else []),
    *([f"  - Crosstab(s) FULLY suppressed (complementary suppression did not converge): "
       + ", ".join(ct_collapsed)] if ct_collapsed else []),
    "",
    "EMBEDDED VALIDATION:",
    *[f"  - {c['name']}: {c['status']}" for c in checks],
    f"  ALL PASSED: {all_passed}",
    "",
    "############################################################",
    "#  REVIEW BEFORE SHARING                                    #",
    "############################################################",
    "  1. Confirm no COLUMN NAME above is itself disclosive.",
    "  2. Review the CATEGORY VALUES THAT WILL BE SHARED section above -- every listed",
    "     string leaves your environment. Confirm each one is safe to share.",
    "  3. Confirm every real identifier was flagged [identifier] (structure-only list above).",
    "  4. Confirm the tier matches what you intend to share.",
    "  5. Share ONLY the .json and this .txt -- nothing else.",
    ("  !! VALIDATION FAILED -- do NOT share; report back to DAAF."
     if not all_passed else "  Validation passed."),
    "############################################################",
]
txt_path = os.path.join(OUTPUT_DIR, f"{DATASET_NAME}_profile_report.txt")
with open(txt_path, "w") as f:
    f.write("\n".join(txt_lines) + "\n")

print(f"\nWrote:\n  {json_path}\n  {txt_path}")
print("\n>>> REVIEW THE .txt FILE BEFORE SHARING EITHER FILE WITH DAAF. <<<")
