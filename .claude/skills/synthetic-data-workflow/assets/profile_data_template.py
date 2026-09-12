#!/usr/bin/env python3
# =============================================================================
# DISCLOSURE-CONTROLLED DATA PROFILER (Python) -- DAAF synthetic-data-workflow
# Run on YOUR machine. Raw rows stay local; review BOTH reports before sharing.
# Self-contained: numpy + pandas; parquet additionally needs pyarrow.
# Minimum-support and categorical-cell checks are NOT a privacy guarantee.
# Counts are records: establish locally whether records represent individuals.
# Flat, sequential; no DAAF imports, network calls, or raw-data output.
# =============================================================================

# --- Config (EDIT THESE) -----------------------------------------------------
INPUT_PATH             = "data.csv"
DATASET_NAME           = "dataset"
OUTPUT_DIR             = "."           # local, non-shared folder
TIER                   = 2             # 1, 2, or 3; T4 uses a different template
SUPPRESSION_THRESHOLD  = 5             # minimum usable support AND categorical cell threshold
MAX_CATEGORICAL_LEVELS = 50
RELATIONSHIP_SPEC      = []            # (outcome, predictor) or categorical pairs
# -----------------------------------------------------------------------------

# --- Config -----------------------------------------------------------------
# INTENT: assertions are release gates, so optimized Python must never run this profiler.
# REASONING: -O/-OO/PYTHONOPTIMIZE remove assert statements but would leave PASS reporting.
if not __debug__:
    raise SystemExit("VALIDATION FAILED -- optimized Python is unsupported; run without -O/-OO or PYTHONOPTIMIZE. No reports written.")

import json
import os
import re
import math
from datetime import datetime, timezone
import numpy as np
import pandas as pd

REPORT_VERSION = "2.0"
TEMPLATE_NAME = "profile_data_template.py"
assert TIER in (1, 2, 3), "TIER must be 1, 2, or 3"
assert type(SUPPRESSION_THRESHOLD) is int and SUPPRESSION_THRESHOLD >= 1
assert type(MAX_CATEGORICAL_LEVELS) is int and MAX_CATEGORICAL_LEVELS >= 1
assert re.fullmatch(r"[A-Za-z0-9_-]+", DATASET_NAME), "Use a short filename slug"
FULL_CUTOFF = max(SUPPRESSION_THRESHOLD, 10)
PROBS = [.01, .05, .10, .25, .50, .75, .90, .95, .99]
PROB_NAMES = ["p1", "p5", "p10", "p25", "p50", "p75", "p90", "p95", "p99"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[+]?[0-9()\s.\-]{7,}$")
DATE_RE = re.compile(r"^[0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}")
ID_NAME_RE = re.compile(r"(^|_)(id|uuid|guid|email|phone|ssn|account|acct)($|_)")
json_path = os.path.join(OUTPUT_DIR, f"{DATASET_NAME}_profile_report.json")
txt_path = os.path.join(OUTPUT_DIR, f"{DATASET_NAME}_profile_report.txt")
# INTENT: preserve prior reports; REASONING: a rerun must not erase review evidence.
assert os.path.isdir(OUTPUT_DIR), "OUTPUT_DIR must already exist"
assert not any(os.path.lexists(p) for p in (json_path, txt_path)), "Reports exist; choose a fresh output folder"

# --- Load -------------------------------------------------------------------
# INTENT: load locally without printing rows; ASSUMES: optional readers already exist.
ext = os.path.splitext(INPUT_PATH)[1].lower()
if ext == ".csv":
    df = pd.read_csv(INPUT_PATH)
elif ext == ".parquet":
    try:
        df = pd.read_parquet(INPUT_PATH)
    except ImportError:
        raise SystemExit("Reading parquet needs the pyarrow dependency")
else:
    raise SystemExit("Unsupported extension; use .csv or .parquet")
n_rows, n_cols = df.shape
assert n_rows > 0 and n_cols > 0, "data is empty"
assert df.columns.is_unique, "Column names must be unique"
assert all(isinstance(c, str) for c in df.columns), "Column names must be strings"
assert all(len(p) == 2 and all(c in df.columns for c in p) for p in RELATIONSHIP_SPEC), "Invalid relationship spec"
print(f"Loaded {n_rows} rows x {n_cols} columns. No raw values printed.")

# --- Profile ----------------------------------------------------------------
columns = []
numeric_cols = []                 # full, nonconstant marginals only
categ_cols = []
col_roles = {}
for cname in df.columns:
    s = df[cname]
    s_nn = s.dropna()
    n_nonnull = len(s_nn)
    n_distinct = int(s_nn.nunique())
    miss_rate = round((n_rows - n_nonnull) / n_rows, 6)
    uniq_ratio = n_distinct / n_nonnull if n_nonnull else 0.0
    if pd.api.types.is_numeric_dtype(s):
        # INTENT: refuse precision-unsupported input before converting native integers.
        # REASONING: float conversion can change large constants or merge distinct neighbors.
        # ASSUMES: T1 has no value release; T2+ refuses magnitude >= 2^53 in this double path.
        if TIER >= 2:
            if pd.api.types.is_integer_dtype(s):
                precision_unsupported = any(abs(int(v)) >= 2**53 for v in s_nn)
            else:
                precision_unsupported = any(np.isfinite(v) and abs(v) >= 2**53 for v in s_nn)
            if precision_unsupported:
                raise SystemExit("Unsupported numeric precision/range: magnitude >= 2^53. No reports written; obtain a reviewed local precision-safe profiling path.")
        vals = s_nn.to_numpy(dtype=float)
        dtype = "integer" if np.all(np.isfinite(vals)) and np.all(vals == np.round(vals)) else "double"
    else:
        dtype = "string"
        s_nn = s_nn.astype(str)
    # INTENT: identifier heuristics select structure-only treatment, not privacy certification.
    # ASSUMES: numeric measurements may be unique; uniqueness alone flags only strings.
    name_is_id = bool(ID_NAME_RE.search(cname.lower()))
    val_is_email = dtype == "string" and n_nonnull > 0 and s_nn.map(lambda v: bool(EMAIL_RE.match(v))).mean() > .8
    val_is_phone = (dtype == "string" and n_nonnull > 0 and
                    s_nn.map(lambda v: bool(PHONE_RE.match(v)) and sum(ch.isdigit() for ch in v) >= 10).mean() > .8)
    is_identifier = name_is_id or bool(val_is_email) or bool(val_is_phone) or (uniq_ratio > .95 and dtype == "string")
    role = "identifier" if is_identifier else "numeric" if dtype != "string" else "categorical" if n_distinct <= MAX_CATEGORICAL_LEVELS else "string"
    col_roles[cname] = role
    col = {"name": cname, "dtype": dtype}
    if TIER == 1:
        columns.append(col)        # T1 remains strictly name/dtype only
        continue
    # Missingness denominator is ALL records, not the missing numerator. Cardinality stays.
    col.update(role=role, missing_rate=miss_rate, nonmissing_n=n_nonnull,
               n_distinct=n_distinct, uniqueness_ratio=round(uniq_ratio, 6), is_identifier=bool(is_identifier))
    if role == "numeric":
        # INTENT: count finite contributors BEFORE computing value summaries.
        # REASONING: four identical values are unsupported; 5,000 identical values are supported.
        # ASSUMES: a record is the intended contribution unit; no identity deduplication here.
        vals = s_nn.to_numpy(dtype=float)
        vals = vals[np.isfinite(vals)]
        n = len(vals)
        if n_nonnull == 0:
            num = {"n": 0, "all_missing": True}
        elif n < SUPPRESSION_THRESHOLD:
            num = {"n": n, "withheld": True,
                   "reason": "no_finite_values" if n == 0 else "insufficient_support"}
        elif np.all(vals == vals[0]):
            value = round(float(vals[0]), 6)
            num = {"n": n, "constant": True, "value": value, "mean": value,
                   "sd": 0.0 if n > 1 else None}
        elif n < FULL_CUTOFF:
            q = np.quantile(vals, [.25, .50, .75])
            num = {"n": n, "small_n": True,
                   "percentiles": dict(zip(["p25", "p50", "p75"], [round(float(v), 6) for v in q]))}
        else:
            q = np.quantile(vals, PROBS)
            num = {"n": n, "mean": round(float(np.mean(vals)), 6),
                   "sd": round(float(np.std(vals, ddof=1)), 6),
                   "percentiles": dict(zip(PROB_NAMES, [round(float(v), 6) for v in q]))}
            numeric_cols.append(cname)
        col["numeric"] = num
    elif role == "categorical":
        # INTENT: preserve primary binning and complementary roll-in of rare levels.
        # REASONING: the __OTHER__ aggregate must not itself be a small visible cell.
        vc = s_nn.value_counts()
        # The literal reserved label joins the pool even when its own count is large.
        # This emits one unambiguous bucket; n_levels_binned includes that source level.
        keep = [(str(k), int(v)) for k, v in vc.items() if v >= SUPPRESSION_THRESHOLD and str(k) != "__OTHER__"]
        other = sum(int(v) for k, v in vc.items() if v < SUPPRESSION_THRESHOLD or str(k) == "__OTHER__")
        while 0 < other < SUPPRESSION_THRESHOLD and keep:
            _, smallest = keep.pop()
            other += smallest
        levels = [{"value": v, "count": c} for v, c in keep]
        if other >= SUPPRESSION_THRESHOLD:
            levels.append({"value": "__OTHER__", "count": other})
        col["categorical"] = {"n": n_nonnull, "n_levels_binned": len(vc) - len(keep), "levels": levels}
        categ_cols.append(cname)
    else:
        # INTENT: lengths and pattern summaries also require actual nonmissing support.
        # REASONING: structure-only does not exempt a statistic from the support floor.
        if n_nonnull < SUPPRESSION_THRESHOLD:
            struct = {"n": n_nonnull, "withheld": True,
                      "reason": "all_missing" if n_nonnull == 0 else "insufficient_support"}
        else:
            lens = s_nn.astype(str).map(len)
            lmean = round(float(lens.mean()), 3)
            is_date = dtype == "string" and s_nn.map(lambda v: bool(DATE_RE.match(v))).mean() > .8
            struct = {"n": n_nonnull, "length_min": int(lens.min()), "length_mean": lmean,
                      "length_max": int(lens.max()),
                      "pattern_flags": {"email": bool(val_is_email), "phone": bool(val_is_phone),
                                        "date": bool(is_date), "id": name_is_id,
                                        "free_text": bool(role == "string" or (dtype == "string" and lmean > 40 and not val_is_email and not val_is_phone))}}
        col["string_structure"] = struct
    columns.append(col)

# --- Relationships ----------------------------------------------------------
relationships = None
if TIER == 3:
    relationships = {"cramers_v": [], "named": [], "crosstabs": []}
    # INTENT: gate each pair on finite COMPLETE pairs, not marginal sample sizes.
    # REASONING: whole-block unavailability avoids invented zero or imputed correlations.
    size = len(numeric_cols)
    pair_n = np.zeros((size, size), dtype=int)
    pear = np.eye(size)
    spea = np.eye(size)
    reason = "fewer_than_two_eligible_columns" if size < 2 else None
    for a in range(size):
        for b in range(a, size):
            x = df[numeric_cols[a]].to_numpy(dtype=float, na_value=np.nan)
            y = df[numeric_cols[b]].to_numpy(dtype=float, na_value=np.nan)
            ok = np.isfinite(x) & np.isfinite(y)
            n = int(ok.sum())
            pair_n[a, b] = pair_n[b, a] = n
            if n < max(SUPPRESSION_THRESHOLD, 2):
                reason = reason or "insufficient_pair_support"
                continue
            if np.std(x[ok]) == 0 or np.std(y[ok]) == 0:
                reason = reason or "zero_pair_variance"
                continue
            p = float(np.corrcoef(x[ok], y[ok])[0, 1])
            r = float(np.corrcoef(pd.Series(x[ok]).rank(), pd.Series(y[ok]).rank())[0, 1])
            if not np.isfinite([p, r]).all():
                reason = reason or "nonfinite_correlation"
                continue
            pear[a, b] = pear[b, a] = round(p, 6)
            spea[a, b] = spea[b, a] = round(r, 6)
    for key, matrix in (("pearson", pear), ("spearman", spea)):
        block = {"available": reason is None, "columns": numeric_cols.copy(),
                 "pair_n": pair_n.tolist(), "matrix": matrix.tolist() if reason is None else []}
        if reason is not None:
            block["reason"] = reason
        relationships[key] = block
    for a in range(len(categ_cols)):
        for b in range(a + 1, len(categ_cols)):
            pair = [categ_cols[a], categ_cols[b]]
            ok = df[pair].notna().all(axis=1)
            n = int(ok.sum())
            entry = {"pair": pair, "n": n, "available": False}
            if n < SUPPRESSION_THRESHOLD:
                entry["reason"] = "insufficient_support"
            else:
                obs = pd.crosstab(df.loc[ok, pair[0]], df.loc[ok, pair[1]]).to_numpy(dtype=float)
                if min(obs.shape) < 2:
                    entry["reason"] = "degenerate_table"
                else:
                    expected = np.outer(obs.sum(1), obs.sum(0)) / n
                    v = math.sqrt(float(np.sum((obs - expected) ** 2 / expected)) / (n * (min(obs.shape) - 1)))
                    entry.update(available=True, v=round(v, 6))
            relationships["cramers_v"].append(entry)
    for pair in RELATIONSHIP_SPEC:
        both_numeric = all(col_roles[c] == "numeric" for c in pair)
        if both_numeric:
            y = df[pair[0]].to_numpy(dtype=float, na_value=np.nan)
            x = df[pair[1]].to_numpy(dtype=float, na_value=np.nan)
            ok = np.isfinite(x) & np.isfinite(y)
            n = int(ok.sum())
            entry = {"outcome": pair[0], "predictor": pair[1], "n": n, "available": False}
            if n < FULL_CUTOFF:
                entry["reason"] = "insufficient_support"
            elif not all(c in numeric_cols for c in pair):
                entry["reason"] = "ineligible_marginal"
            elif np.std(x[ok]) == 0 or np.std(y[ok]) == 0:
                entry["reason"] = "zero_pair_variance"
            else:
                xv, yv = x[ok], y[ok]
                slope, intercept = np.polyfit(xv, yv, 1)
                r2 = 1 - float(np.sum((yv - (slope * xv + intercept)) ** 2)) / float(np.sum((yv - yv.mean()) ** 2))
                entry.update(available=True, pearson=round(float(np.corrcoef(xv, yv)[0, 1]), 6),
                             spearman=round(float(np.corrcoef(pd.Series(xv).rank(), pd.Series(yv).rank())[0, 1]), 6),
                             ols={"intercept": round(float(intercept), 6), "slope": round(float(slope), 6), "r_squared": round(r2, 6)})
            relationships["named"].append(entry)
        else:
            # INTENT: no categorical fallback for identifiers, strings, or mixed numeric pairs.
            # REASONING: a rejected numeric summary must not escape as exact value cells.
            ok = df[list(pair)].notna().all(axis=1)
            n = int(ok.sum())
            entry = {"pair": list(pair), "n": n, "available": False}
            if not all(col_roles[c] == "categorical" for c in pair):
                entry["reason"] = "ineligible_roles"
            elif n < SUPPRESSION_THRESHOLD:
                entry["reason"] = "insufficient_support"
            else:
                m = pd.crosstab(df.loc[ok, pair[0]], df.loc[ok, pair[1]]).to_numpy(dtype=int)
                supp = (m > 0) & (m < SUPPRESSION_THRESHOLD)
                for _ in range(10):
                    changed = False
                    for r in range(m.shape[0]):
                        if supp[r, :].sum() == 1:
                            vis = np.where(~supp[r, :])[0]
                            if len(vis):
                                supp[r, vis[np.argmin(m[r, vis])]] = True
                                changed = True
                    for c in range(m.shape[1]):
                        if supp[:, c].sum() == 1:
                            vis = np.where(~supp[:, c])[0]
                            if len(vis):
                                supp[vis[np.argmin(m[vis, c])], c] = True
                                changed = True
                    if not changed:
                        break
                lone = bool(np.any(supp.sum(0) == 1) or np.any(supp.sum(1) == 1))
                if lone:
                    supp[:, :] = True
                cells = [None if hidden else int(value) for value, hidden in zip(m.flat, supp.flat)]
                entry.update(available=True, rows=m.shape[0], cols=m.shape[1], cells=cells,
                             cells_suppressed=int(supp.sum()))
                if lone:
                    entry["collapsed"] = True
            relationships["crosstabs"].append(entry)

# --- Candidate --------------------------------------------------------------
# INTENT: the typed, rounded, suppressed candidate is the ONLY validation/output source.
report = {"report_version": REPORT_VERSION, "dataset_name": DATASET_NAME,
          "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
          "generator": {"language": "Python", "template": TEMPLATE_NAME, "template_version": REPORT_VERSION},
          "settings": {"tier": TIER, "suppression_threshold": SUPPRESSION_THRESHOLD,
                       "max_categorical_levels": MAX_CATEGORICAL_LEVELS,
                       "relationship_spec": [list(p) for p in RELATIONSHIP_SPEC] or None,
                       "support_unit": "record", "full_summary_cutoff": FULL_CUTOFF},
          "dataset": {"row_count": n_rows, "column_count": n_cols}, "columns": columns}
if relationships is not None:
    report["relationships"] = relationships

# --- Validate ---------------------------------------------------------------
# No raw-data recomputation here: malformed/mutated release fields must fail themselves.
required_checks = ["column_shapes_and_support", "percentiles_monotone", "category_counts_le_rowcount",
                   "missing_rate_in_unit_interval", "no_subthreshold_cells_emitted",
                   "correlation_matrix_symmetric", "relationship_support_and_shape"]
checks = []
for check_name in required_checks:
    applicable = True
    reason = "candidate_fields_checked"
    try:
        cols = report["columns"]
        rows = report["dataset"]["row_count"]
        tier = report["settings"]["tier"]
        threshold = report["settings"]["suppression_threshold"]
        cutoff = max(threshold, 10)
        by_name = {c["name"]: c for c in cols}
        rels = report.get("relationships")
        if check_name == "column_shapes_and_support":
            assert report["report_version"] == "2.0" and tier in (1, 2, 3)
            assert set(report) == {"report_version", "dataset_name", "generated_utc", "generator", "settings", "dataset", "columns"} | ({"relationships"} if tier == 3 else set())
            assert set(report["dataset"]) == {"row_count", "column_count"}
            assert set(report["settings"]) == {"tier", "suppression_threshold", "max_categorical_levels", "relationship_spec", "support_unit", "full_summary_cutoff"}
            assert type(rows) is int and rows > 0 and len(cols) == report["dataset"]["column_count"]
            assert len(by_name) == len(cols) and type(threshold) is int and threshold >= 1
            assert report["settings"]["full_summary_cutoff"] == cutoff
            assert report["settings"]["support_unit"] == "record"
            assert (rels is not None) == (tier == 3)
            for c in cols:
                assert c["dtype"] in ("integer", "double", "string")
                if tier == 1:
                    assert set(c) == {"name", "dtype"}
                    continue
                nn = c["nonmissing_n"]
                assert type(nn) is int and 0 <= nn <= rows
                assert type(c["n_distinct"]) is int and 0 <= c["n_distinct"] <= nn
                assert math.isfinite(c["uniqueness_ratio"]) and 0 <= c["uniqueness_ratio"] <= 1
                key = {"numeric": "numeric", "categorical": "categorical", "identifier": "string_structure", "string": "string_structure"}[c["role"]]
                assert set(c) == {"name", "dtype", "role", "missing_rate", "nonmissing_n", "n_distinct", "uniqueness_ratio", "is_identifier", key}
                b = c[key]
                assert type(b["n"]) is int and 0 <= b["n"] <= nn
                if key != "numeric":
                    assert b["n"] == nn
                if key == "numeric":
                    n = b["n"]
                    if b.get("all_missing") is True:
                        assert set(b) == {"n", "all_missing"} and n == nn == 0
                    elif b.get("withheld") is True:
                        assert set(b) == {"n", "withheld", "reason"} and nn > 0 and n < threshold
                        assert b["reason"] == ("no_finite_values" if n == 0 else "insufficient_support")
                    elif b.get("constant") is True:
                        assert set(b) == {"n", "constant", "value", "mean", "sd"} and n >= threshold
                        assert math.isfinite(b["value"]) and b["mean"] == b["value"]
                        assert b["sd"] == (0 if n > 1 else None)
                    elif b.get("small_n") is True:
                        assert set(b) == {"n", "small_n", "percentiles"} and threshold <= n < cutoff
                        assert set(b["percentiles"]) == {"p25", "p50", "p75"}
                    else:
                        assert set(b) == {"n", "mean", "sd", "percentiles"} and n >= cutoff
                        assert math.isfinite(b["mean"]) and math.isfinite(b["sd"]) and b["sd"] >= 0
                        assert set(b["percentiles"]) == set(PROB_NAMES)
                elif key == "string_structure":
                    if b.get("withheld") is True:
                        assert set(b) == {"n", "withheld", "reason"} and nn < threshold
                        assert b["reason"] == ("all_missing" if nn == 0 else "insufficient_support")
                    else:
                        assert set(b) == {"n", "length_min", "length_mean", "length_max", "pattern_flags"} and nn >= threshold
                        assert all(math.isfinite(b[k]) for k in ("length_min", "length_mean", "length_max"))
                        assert 0 <= b["length_min"] <= b["length_mean"] <= b["length_max"]
                        assert set(b["pattern_flags"]) == {"email", "phone", "date", "id", "free_text"}
                        assert all(type(v) is bool for v in b["pattern_flags"].values())
        elif check_name == "percentiles_monotone":
            blocks = [c["numeric"]["percentiles"] for c in cols if "percentiles" in c.get("numeric", {})]
            applicable = bool(blocks)
            for b in blocks:
                values = [b[k] for k in PROB_NAMES if k in b]
                assert all(math.isfinite(v) for v in values) and all(x <= y for x, y in zip(values, values[1:]))
        elif check_name == "category_counts_le_rowcount":
            blocks = [c["categorical"] for c in cols if "categorical" in c]
            applicable = bool(blocks)
            for b in blocks:
                assert set(b) == {"n", "n_levels_binned", "levels"}
                assert type(b["n_levels_binned"]) is int and b["n_levels_binned"] >= 0
                counts = [l["count"] for l in b["levels"]]
                assert all(type(v) is int and v >= threshold for v in counts)
                assert sum(counts) <= b["n"] <= rows
                assert sum(counts) == (b["n"] if b["n"] >= threshold else 0)
                assert all(set(l) == {"value", "count"} and isinstance(l["value"], str) for l in b["levels"])
                labels = [l["value"] for l in b["levels"]]
                assert len(labels) == len(set(labels)), "Duplicate released category labels"
        elif check_name == "missing_rate_in_unit_interval":
            applicable = tier >= 2
            if applicable:
                for c in cols:
                    rate = c["missing_rate"]
                    assert math.isfinite(rate) and 0 <= rate <= 1
                    assert abs(rate - (rows - c["nonmissing_n"]) / rows) <= .00000051
        elif check_name == "no_subthreshold_cells_emitted":
            counts = [l["count"] for c in cols for l in c.get("categorical", {}).get("levels", [])]
            if rels:
                counts += [v for b in rels["crosstabs"] for v in b.get("cells", []) if v is not None]
            applicable = bool(counts)
            assert all(type(v) is int and (v == 0 or v >= threshold) for v in counts)
        elif check_name == "correlation_matrix_symmetric":
            blocks = [rels[k] for k in ("pearson", "spearman") if rels and rels[k]["available"]]
            applicable = bool(blocks)
            for b in blocks:
                m = np.array(b["matrix"], dtype=float)
                dim = len(b["columns"])
                assert dim >= 2 and m.shape == (dim, dim) and np.isfinite(m).all()
                assert np.allclose(m, m.T, atol=1e-6, rtol=0) and np.allclose(np.diag(m), 1, atol=1e-6, rtol=0)
                assert (np.abs(m) <= 1).all()
        else:
            applicable = tier == 3
            if applicable:
                assert set(rels) == {"pearson", "spearman", "named", "cramers_v", "crosstabs"}
                eligible = [c["name"] for c in cols if set(c.get("numeric", {})) == {"n", "mean", "sd", "percentiles"}]
                for key in ("pearson", "spearman"):
                    b = rels[key]
                    assert type(b["available"]) is bool and b["columns"] == eligible
                    dim = len(b["columns"])
                    pn = np.array(b["pair_n"])
                    assert (pn.shape == (dim, dim)) if dim else b["pair_n"] == []
                    if dim:
                        assert np.issubdtype(pn.dtype, np.integer) and (pn >= 0).all() and np.array_equal(pn, pn.T)
                        for i, name in enumerate(b["columns"]):
                            assert pn[i, i] == by_name[name]["numeric"]["n"]
                            assert (pn[i, :] <= pn[i, i]).all()
                    if b["available"]:
                        assert set(b) == {"available", "columns", "pair_n", "matrix"}
                        assert dim >= 2 and (pn >= max(threshold, 2)).all()
                    else:
                        assert set(b) == {"available", "columns", "pair_n", "matrix", "reason"}
                        assert b["matrix"] == [] and b["reason"] in ("fewer_than_two_eligible_columns", "insufficient_pair_support", "zero_pair_variance", "nonfinite_correlation")
                for kind in ("named", "cramers_v", "crosstabs"):
                    for b in rels[kind]:
                        assert type(b["available"]) is bool and type(b["n"]) is int and 0 <= b["n"] <= rows
                        pair = [b["outcome"], b["predictor"]] if kind == "named" else b["pair"]
                        assert len(pair) == 2 and all(c in by_name for c in pair)
                        assert all(b["n"] <= by_name[c]["nonmissing_n"] for c in pair)
                        base = {"outcome", "predictor", "n", "available"} if kind == "named" else {"pair", "n", "available"}
                        if not b["available"]:
                            assert set(b) == base | {"reason"} and b["reason"] in ("insufficient_support", "ineligible_marginal", "zero_pair_variance", "ineligible_roles", "degenerate_table")
                            continue
                        assert b["n"] >= (cutoff if kind == "named" else threshold)
                        if kind == "named":
                            assert set(b) == base | {"pearson", "spearman", "ols"} and all(c in eligible for c in pair)
                            assert all(b["n"] <= by_name[c]["numeric"]["n"] for c in pair)
                            assert set(b["ols"]) == {"intercept", "slope", "r_squared"}
                            assert all(math.isfinite(v) for v in b["ols"].values())
                            assert all(math.isfinite(b[k]) and abs(b[k]) <= 1 for k in ("pearson", "spearman"))
                            assert 0 <= b["ols"]["r_squared"] <= 1
                        elif kind == "cramers_v":
                            assert set(b) == base | {"v"} and all(by_name[c]["role"] == "categorical" for c in pair)
                            assert math.isfinite(b["v"]) and 0 <= b["v"] <= 1
                        else:
                            assert all(by_name[c]["role"] == "categorical" for c in pair)
                            assert set(b) == base | {"rows", "cols", "cells", "cells_suppressed"} | ({"collapsed"} if "collapsed" in b else set())
                            assert type(b["rows"]) is int and type(b["cols"]) is int and b["rows"] > 0 and b["cols"] > 0
                            assert len(b["cells"]) == b["rows"] * b["cols"]
                            mask = np.array([v is None for v in b["cells"]]).reshape(b["rows"], b["cols"])
                            assert int(mask.sum()) == b["cells_suppressed"]
                            total = sum(v for v in b["cells"] if v is not None)
                            assert total <= b["n"] and (mask.any() or total == b["n"])
                            if b.get("collapsed") is True:
                                assert mask.all()
                            else:
                                assert not np.any(mask.sum(0) == 1) and not np.any(mask.sum(1) == 1)
        status = "PASS" if applicable else "NOT_APPLICABLE"
        if not applicable:
            reason = "no_released_targets_at_this_tier_or_block_unavailable"
    except Exception as exc:
        status, applicable, reason = "FAIL", True, "candidate_validation_error_" + type(exc).__name__
    checks.append({"name": check_name, "status": status, "applicable": applicable, "reason": reason})
# INTENT: completeness is required, not vacuous all([]); exceptions cannot become N/A.
all_passed = ([c["name"] for c in checks] == required_checks and
              all(c["reason"] and ((c["applicable"] and c["status"] == "PASS") or
                  (not c["applicable"] and c["status"] == "NOT_APPLICABLE")) for c in checks))
report["validation"] = {"checks": checks, "all_passed": all_passed}
if not all_passed:
    print("VALIDATION FAILED -- no reports written; do not share. Failed checks:")
    print(", ".join(c["name"] for c in checks if c["status"] == "FAIL"))
    raise SystemExit(1)

# --- Summary / Save ---------------------------------------------------------
# TXT includes the exact candidate, not an independently maintained raw-data summary.
json_text = json.dumps(report, indent=2, allow_nan=False)
txt_text = "\n".join([
    "DISCLOSURE PROFILE REVIEW -- REVIEW BEFORE SHARING",
    "Counts are records, not verified distinct individuals. Confirm the contribution unit locally.",
    "Below-threshold numeric/string summaries are withheld. Eligible constants are shared.",
    "Missingness uses all records; rare numerators do not alone veto supported rates/means.",
    "Rare categories are pooled; visible cross-tab cells are suppression-checked; null means hidden.",
    "Unavailable relationships carry reasons, not invented zero correlations.",
    "These checks do not guarantee protection from reconstruction or auxiliary-information attacks.",
    "Review ALL column names, CATEGORY level VALUES, structure flags and relationships below.",
    "Confirm real identifiers were detected, the tier/threshold are appropriate, and release is authorized.",
    "EXACT RELEASE CANDIDATE (same fields and values as JSON):", json_text,
    "REVIEW BEFORE SHARING either report. Share no raw rows or fitted models.",
    "Synthetic generation from this report is a code scaffold, never research findings.", ""])
# Exclusive creation also refuses a target that appeared after preflight. If either write fails,
# any partial new pair is NOT approved for sharing; prior targets are never overwritten.
try:
    with open(json_path, "x", encoding="utf-8") as f:
        f.write(json_text + "\n")
    with open(txt_path, "x", encoding="utf-8") as f:
        f.write(txt_text)
except OSError:
    raise SystemExit("OUTPUT FAILED -- do not share any partial report pair; use a fresh folder for retry")
print(f"Wrote BOTH reports:\n  {json_path}\n  {txt_path}")
print("REVIEW THE .txt AND .json BEFORE SHARING EITHER FILE WITH DAAF.")
