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
# Nothing to declare: the profiler marks a check not applicable itself, with a fixed reason.
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
# INTENT: refuse a pair that names one column twice, or a pair listed twice, before anything is written.
# REASONING: one pair tabulated twice can be suppressed differently each time, and the two tables
# combined recover cells that each one hides. Messages name pair positions (1-based), never values.
spec_problems = []
for j, p in enumerate(RELATIONSHIP_SPEC):
    if p[0] == p[1]:
        spec_problems.append("pair " + str(j + 1) + " names one column twice")
    for i in range(j):
        if list(RELATIONSHIP_SPEC[i]) == list(p):
            spec_problems.append("pair " + str(j + 1) + " repeats pair " + str(i + 1))
assert len(spec_problems) == 0, "Invalid relationship spec: " + "; ".join(spec_problems)
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
        # Order: count descending, ties by code-point label order, so the level the roll-in
        # below pools is the same in Python and R (not first-occurrence or locale order).
        vc = sorted(((str(k), int(v)) for k, v in s_nn.value_counts().items()), key=lambda kv: (-kv[1], kv[0]))
        # The literal reserved label joins the pool even when its own count is large.
        # This emits one unambiguous bucket; n_levels_binned includes that source level.
        keep = [(k, v) for k, v in vc if v >= SUPPRESSION_THRESHOLD and k != "__OTHER__"]
        other = sum(v for k, v in vc if v < SUPPRESSION_THRESHOLD or k == "__OTHER__")
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
# INTENT: refuse a reversed repeat ([b, a] after [a, b]) now that roles are known; nothing is written yet.
# REASONING: two numeric columns in both orders are two different regressions (y ~ x and x ~ y)
# and release no cells, so only that case may stay; any other reversed pair repeats one table.
for j, p in enumerate(RELATIONSHIP_SPEC):
    for i in range(j):
        if list(RELATIONSHIP_SPEC[i]) == [p[1], p[0]] and not all(col_roles[c] == "numeric" for c in p):
            spec_problems.append("pair " + str(j + 1) + " reverses pair " + str(i + 1) + "; only two numeric columns may be listed in both orders")
assert len(spec_problems) == 0, "Invalid relationship spec: " + "; ".join(spec_problems)

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
            # INTENT: release a regression only when each column's complement group -- records with
            # that column finite but the other not -- is empty or holds at least k records.
            # REASONING: the released mean of x describes the numeric block's n_x records; the fitted
            # line pins the mean of x over the n pair-complete records (via the released mean of y,
            # or via the reversed regression), so n_x * mean_x - n * that mean recovers the mean of
            # the n_x - n records lacking y. A group of 1 to k-1 records would leak its mean.
            # ASSUMES: the numeric block's n (finite values) is the population its mean describes.
            # Order: the gates decidable from released counts (insufficient_support,
            # ineligible_marginal, small_complement_group), then value-dependent zero_pair_variance.
            complement = [next(c for c in columns if c["name"] == name)["numeric"]["n"] - n for name in pair]
            if n < FULL_CUTOFF:
                entry["reason"] = "insufficient_support"
            elif not all(c in numeric_cols for c in pair):
                entry["reason"] = "ineligible_marginal"
            elif any(0 < g < SUPPRESSION_THRESHOLD for g in complement):
                entry["reason"] = "small_complement_group"
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
                # INTENT: tabulate on each column's RELEASED categories, not its raw source levels.
                # REASONING: if a level pooled into __OTHER__ kept a row of its own, a fully visible
                # row could be subtracted from the released __OTHER__ count and isolate a rare
                # level. So every pooled source level (a literal "__OTHER__" label included) maps to
                # ONE pooled category. Order: kept labels in code-point order, then the pooled
                # category last; reindexing to that full set keeps a released level with no
                # pair-complete record as a row/column of structural zeros, so rows and cols always
                # equal the released level counts. Cramer's V above still uses the full table.
                # ASSUMES: a column with a pooled source level always releases __OTHER__ (pair
                # support >= k implies the pool reached k); the assertion below enforces it.
                categories = []
                mapped = []
                totals = []          # released level count per category, in category order
                nonmissing = []      # each pair column's nonmissing_n (null/NA excluded)
                for cname in pair:
                    released = [l["value"] for l in next(c for c in columns if c["name"] == cname)["categorical"]["levels"]]
                    kept = sorted(v for v in released if v != "__OTHER__")
                    categories.append(kept + (["__OTHER__"] if "__OTHER__" in released else []))
                    level_counts = {l["value"]: l["count"] for l in next(c for c in columns if c["name"] == cname)["categorical"]["levels"]}
                    totals.append([level_counts[v] for v in categories[-1]])
                    nonmissing.append(next(c for c in columns if c["name"] == cname)["nonmissing_n"])
                    values = df.loc[ok, cname].astype(str)
                    values = values.where(values.isin(kept), "__OTHER__")
                    assert values.isin(categories[-1]).all(), "Cross-tab category mapping is incomplete"
                    mapped.append(values.rename("row" if len(mapped) == 0 else "col"))
                m = pd.crosstab(mapped[0], mapped[1]).reindex(index=categories[0], columns=categories[1], fill_value=0).to_numpy(dtype=int)
                assert int(m.sum()) == n, "Cross-tab does not account for every pair-complete record"
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
                # INTENT: no hidden cell may be exactly recoverable from the row/column totals.
                # REASONING: read hidden cells as edges of a graph whose vertices are the table's
                # rows and columns. Differencing the totals pins a hidden cell exactly iff its edge
                # is a BRIDGE (lies on no cycle); a lone hidden cell is only the degree-1 case, so
                # two hidden cycles joined by one cell pass the rule above yet leak that cell.
                # ASSUMES: every row/column total is known (worst case); interval bounds from
                # non-negativity are out of scope. Python and R follow the same rule exactly.
                n_r, n_c = m.shape
                # INTENT: no missing-partner count below k may be pinned by the released totals either.
                # REASONING: a record whose partner column is missing is outside this table but inside
                # the categorical blocks' counts. Extend the table by a "partner missing" column (this
                # row's category, column variable missing) and a "partner missing" row (row variable
                # missing, this column's category). Every total of the extended table is released (level
                # counts, row_count - nonmissing_n), and so is the both-missing corner: corner =
                # row_missing + col_missing - (row_count - n). So the extended table's hidden cells --
                # hidden core cells plus every missing-partner cell -- are edges of the same row/column
                # graph with one extra vertex for the missing row and one for the missing column; the
                # corner is known, not an edge. A missing-partner line whose cells sum to zero is a line
                # of known zeros and adds no edge, so with no missing value in either column nothing
                # below changes. The BASELINE is what the released counts reveal with every core cell
                # hidden: the core is then one connected block, so a missing-partner cell is a bridge
                # only when its line has a single partner (the missing column of a one-row table, the
                # missing row of a one-column table). Released n and missing counts already fix those
                # cells, no cell suppression can reach them, and they are exempt. Every other
                # missing-partner cell with 0 < count < k must not be a bridge.
                # ASSUMES: missing means null/NA, exactly as nonmissing_n counts it.
                ext_col = [totals[0][i] - int(m[i, :].sum()) for i in range(n_r)]   # row category i, column variable missing
                ext_row = [totals[1][j] - int(m[:, j].sum()) for j in range(n_c)]   # row variable missing, column category j
                assert min(ext_col + ext_row) >= 0 and sum(ext_col) == nonmissing[0] - n and sum(ext_row) == nonmissing[1] - n, "Missing-partner counts do not reconcile with nonmissing_n"
                miss_row, miss_col = n_r + n_c, n_r + n_c + 1
                ext_edges = []       # (row-side vertex, column-side vertex, count, exempt), extended row-major order
                if sum(ext_col) > 0:
                    ext_edges += [(i, miss_col, ext_col[i], n_r == 1) for i in range(n_r)]
                if sum(ext_row) > 0:
                    ext_edges += [(miss_row, n_r + j, ext_row[j], n_c == 1) for j in range(n_c)]
                # One deterministic loop serves both rules. Each step takes the FIRST violation: a
                # core bridge in row-major order (hidden core cells, core totals treated as known),
                # else the first non-exempt missing-partner cell with 0 < count < k that is a bridge of
                # the extended graph, in extended row-major order (partner-missing column cells for
                # rows 0..rows-1, then partner-missing row cells for columns 0..cols-1). It splits that
                # graph without the bridge into the bridge row's side and the bridge column's side and
                # hides the smallest visible NON-ZERO core cell joining the two sides (ties: first in
                # row-major order), which puts the bridge on a cycle. Zeros are structural and stay
                # visible. Each joining step puts the bridge it targets on a cycle.
                # (A missing-partner cell with no joining cell gets the primary-cell treatment
                # described below.) Every step hides at least one more cell, so rows x cols + rows +
                # cols + 2 iterations always suffice; if a core bridge has no joining cell, a lone
                # hidden cell remains, or the bound is reached, the whole table collapses, which
                # leaves exactly the baseline. With no missing-partner edge the loop is the core
                # rule alone, step for step.
                bridge_free = False
                for _ in range(n_r * n_c + n_r + n_c + 2):
                    if lone:
                        break
                    bridge = None
                    for r in range(n_r):
                        for c in range(n_c):
                            if bridge is not None or not supp[r, c]:
                                continue
                            # Component labels of the hidden-cell graph WITHOUT cell (r, c);
                            # vertex i < n_r is row i, vertex n_r + j is column j; a label is
                            # the smallest vertex of its component, so traversal order is moot.
                            label = [-1] * (n_r + n_c)
                            for start in range(n_r + n_c):
                                if label[start] >= 0:
                                    continue
                                label[start] = start
                                stack = [start]
                                while len(stack) > 0:
                                    vertex = stack.pop()
                                    if vertex < n_r:
                                        nbrs = [n_r + int(j) for j in np.flatnonzero(supp[vertex, :]) if not (vertex == r and int(j) == c)]
                                    else:
                                        nbrs = [int(i) for i in np.flatnonzero(supp[:, vertex - n_r]) if not (int(i) == r and vertex - n_r == c)]
                                    for w in nbrs:
                                        if label[w] < 0:
                                            label[w] = start
                                            stack.append(w)
                            if label[r] != label[n_r + c]:
                                bridge = (r, n_r + c, label, False)
                    if bridge is None and len(ext_edges) > 0:
                        # Extended graph: vertices 0..n_r-1 rows, n_r..n_r+n_c-1 columns, then the
                        # missing row and the missing column; edges are the hidden core cells, then the
                        # missing-partner cells. Each candidate is tested by dropping its own edge.
                        edges = [(i, n_r + j) for i in range(n_r) for j in range(n_c) if supp[i, j]] + [(u, w) for u, w, _, _ in ext_edges]
                        adjacency = [[] for _ in range(n_r + n_c + 2)]
                        for edge_index, (u, w) in enumerate(edges):
                            adjacency[u].append((w, edge_index))
                            adjacency[w].append((u, edge_index))
                        for ext_index, (u, w, count, exempt) in enumerate(ext_edges):
                            if bridge is not None or exempt or not (0 < count < SUPPRESSION_THRESHOLD):
                                continue
                            skip = len(edges) - len(ext_edges) + ext_index
                            label = [-1] * (n_r + n_c + 2)
                            for start in range(n_r + n_c + 2):
                                if label[start] >= 0:
                                    continue
                                label[start] = start
                                stack = [start]
                                while len(stack) > 0:
                                    vertex = stack.pop()
                                    for neighbor, edge_index in adjacency[vertex]:
                                        if edge_index != skip and label[neighbor] < 0:
                                            label[neighbor] = start
                                            stack.append(neighbor)
                            if label[u] != label[w]:
                                bridge = (u, w, label, True)
                    if bridge is None:
                        bridge_free = True
                        break
                    side_row, side_col, label = bridge[2][bridge[0]], bridge[2][bridge[1]], bridge[2]
                    best = None
                    for i in range(n_r):
                        for j in range(n_c):
                            joins = (label[i] == side_row and label[n_r + j] == side_col) or (label[i] == side_col and label[n_r + j] == side_row)
                            if joins and not supp[i, j] and m[i, j] > 0 and (best is None or m[i, j] < m[best[0], best[1]]):
                                best = (i, j)
                    if best is None and bridge[3]:
                        # INTENT: no joining cell for an exposed missing-partner cell (typically its row
                        # or column has no hidden core cell) -- treat it like a primary cell instead of
                        # collapsing: hide the smallest visible NON-ZERO core cell on its own row (partner-
                        # missing column) or column (partner-missing row), first in order on ties, then
                        # re-run complementary suppression on non-zero cells (a hidden cell alone in its
                        # row/column gets the smallest visible non-zero partner, first index on ties), up
                        # to ten passes. The loop then re-checks both rules. Zeros stay visible.
                        line_hidden = False
                        if bridge[1] == miss_col:
                            vis = np.where(~supp[bridge[0], :] & (m[bridge[0], :] > 0))[0]
                            if len(vis):
                                supp[bridge[0], vis[np.argmin(m[bridge[0], vis])]] = True
                                line_hidden = True
                        else:
                            vis = np.where(~supp[:, bridge[1] - n_r] & (m[:, bridge[1] - n_r] > 0))[0]
                            if len(vis):
                                supp[vis[np.argmin(m[vis, bridge[1] - n_r])], bridge[1] - n_r] = True
                                line_hidden = True
                        if line_hidden:
                            for rerun in range(10):
                                changed = False
                                for r in range(n_r):
                                    vis = np.where(~supp[r, :] & (m[r, :] > 0))[0]
                                    if supp[r, :].sum() == 1 and len(vis):
                                        supp[r, vis[np.argmin(m[r, vis])]] = True
                                        changed = True
                                for c in range(n_c):
                                    vis = np.where(~supp[:, c] & (m[:, c] > 0))[0]
                                    if supp[:, c].sum() == 1 and len(vis):
                                        supp[vis[np.argmin(m[vis, c])], c] = True
                                        changed = True
                                if not changed:
                                    break
                            lone = bool(np.any(supp.sum(0) == 1) or np.any(supp.sum(1) == 1))
                            continue
                    if best is None:
                        break
                    supp[best[0], best[1]] = True
                collapse = lone or not bridge_free
                if collapse:
                    supp[:, :] = True
                cells = [None if hidden else int(value) for value, hidden in zip(m.flat, supp.flat)]
                entry.update(available=True, rows=m.shape[0], cols=m.shape[1], cells=cells,
                             cells_suppressed=int(supp.sum()))
                if collapse:
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
# INTENT: no researcher declarations. A check is NOT_APPLICABLE only where the candidate has
# no target for it, and its reason is one of the fixed forms below -- never free text, which
# would cross the boundary. The disclosure sweep has no such form: it always runs.
# Wire status enum: PASS | FAIL | NOT_APPLICABLE | NOT_VERIFIED. The stdout token for
# NOT_APPLICABLE is [SKIPPED]; a skipped check is never silent.
status_tokens = {"PASS": "[PASS]", "FAIL": "[FAIL]", "NOT_APPLICABLE": "[SKIPPED]", "NOT_VERIFIED": "[NOT VERIFIED]"}
counter_keys = {"PASS": "passed", "FAIL": "failed", "NOT_APPLICABLE": "skipped", "NOT_VERIFIED": "not_verified"}
checks = []
check_details = {}
for check_name in required_checks:
    status = "PASS"
    applicable = True
    reason = "candidate_fields_checked"
    detail = ""
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
            shape_column = None
            try:
                for c in cols:
                    shape_column = c.get("name")
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
            except Exception as shape_exc:
                # INTENT: a shape/support failure must name the offending COLUMN, not just a class.
                raise AssertionError("column '" + str(shape_column) + "' " + type(shape_exc).__name__ + ": " + str(shape_exc))
            detail = str(len(cols)) + " columns checked for shape and support at tier " + str(tier)
        elif check_name == "percentiles_monotone":
            # INTENT: enumerate the DECLARED numeric columns, then the grids they release.
            # REASONING: an absent grid on a column that declares role numeric is missing
            # evidence (NOT VERIFIED), while a report that releases no grids at all is a
            # structural fact this line states with its own counts.
            numeric_columns = [c for c in cols if c.get("role") == "numeric"]
            grids = []
            for c in numeric_columns:
                b = c.get("numeric")
                if b is None or not isinstance(b, dict):
                    status = "NOT_VERIFIED"
                    reason = "column '" + str(c.get("name")) + "' declares role numeric with no numeric block"
                    break
                if "percentiles" in b:
                    grids.append((c.get("name"), b["percentiles"]))
            if status == "PASS" and len(numeric_columns) == 0:
                status, applicable = "NOT_APPLICABLE", False
                reason = "report declares 0 numeric columns at tier " + str(tier)
            elif status == "PASS" and len(grids) == 0:
                status, applicable = "NOT_APPLICABLE", False
                reason = "0 of " + str(len(numeric_columns)) + " numeric columns release a percentile grid"
            elif status == "PASS":
                n_values = 0
                for cname, b in grids:
                    assert isinstance(b, dict), "column '" + str(cname) + "': percentile grid is not a mapping"
                    values = [b[k] for k in PROB_NAMES if k in b]
                    assert len(values) == len(b), "column '" + str(cname) + "': unrecognized percentile key"
                    assert len(values) > 0, "column '" + str(cname) + "': percentile grid is empty"
                    assert all(math.isfinite(v) for v in values), "column '" + str(cname) + "': non-finite percentile"
                    assert all(x <= y for x, y in zip(values, values[1:])), "column '" + str(cname) + "': percentile grid is not non-decreasing"
                    n_values += len(values)
                detail = str(len(grids)) + " columns x " + str(n_values) + " percentiles checked, all finite and non-decreasing"
        elif check_name == "category_counts_le_rowcount":
            categorical_columns = [c for c in cols if c.get("role") == "categorical"]
            blocks = []
            for c in categorical_columns:
                b = c.get("categorical")
                if b is None or not isinstance(b, dict):
                    status = "NOT_VERIFIED"
                    reason = "column '" + str(c.get("name")) + "' declares role categorical with no categorical block"
                    break
                blocks.append((c.get("name"), b))
            if status == "PASS" and len(blocks) == 0:
                status, applicable = "NOT_APPLICABLE", False
                reason = "report declares 0 categorical columns at tier " + str(tier)
            elif status == "PASS":
                n_levels = 0
                for cname, b in blocks:
                    assert set(b) == {"n", "n_levels_binned", "levels"}, "column '" + str(cname) + "': categorical block keys"
                    assert type(b["n_levels_binned"]) is int and b["n_levels_binned"] >= 0, "column '" + str(cname) + "': n_levels_binned"
                    counts = [l["count"] for l in b["levels"]]
                    assert all(type(v) is int and v >= threshold for v in counts), "column '" + str(cname) + "': released level below threshold"
                    assert sum(counts) <= b["n"] <= rows, "column '" + str(cname) + "': released counts exceed support or row count"
                    assert sum(counts) == (b["n"] if b["n"] >= threshold else 0), "column '" + str(cname) + "': released counts do not reconcile with support"
                    assert all(set(l) == {"value", "count"} and isinstance(l["value"], str) for l in b["levels"]), "column '" + str(cname) + "': level entry shape"
                    labels = [l["value"] for l in b["levels"]]
                    assert len(labels) == len(set(labels)), "column '" + str(cname) + "': duplicate released category labels"
                    n_levels += len(labels)
                detail = str(len(blocks)) + " columns x " + str(n_levels) + " released levels checked against row count " + str(rows)
        elif check_name == "missing_rate_in_unit_interval":
            if tier < 2:
                status, applicable = "NOT_APPLICABLE", False
                reason = "tier 1 releases name and dtype only"
            else:
                for c in cols:
                    cname = c.get("name")
                    rate = c.get("missing_rate")
                    assert rate is not None, "column '" + str(cname) + "': missing_rate absent"
                    assert type(rate) is float or type(rate) is int, "column '" + str(cname) + "': missing_rate is not a real number"
                    assert math.isfinite(rate), "column '" + str(cname) + "': missing_rate is not finite"
                    assert 0 <= rate <= 1, "column '" + str(cname) + "': missing_rate outside the unit interval"
                    assert abs(rate - (rows - c["nonmissing_n"]) / rows) <= .00000051, "column '" + str(cname) + "': missing_rate disagrees with nonmissing_n"
                detail = str(len(cols)) + " columns checked, every rate in [0, 1] and consistent with nonmissing_n"
        elif check_name == "no_subthreshold_cells_emitted":
            # INTENT: scan COMPLETENESS is itself the check -- a block we failed to reach is a FAIL.
            # REASONING: an empty sweep list is indistinguishable from a clean sweep, so the
            # blocks scanned are counted and reconciled against the blocks the report declares.
            # ASSUMES: evidence stays aggregate; no cell value, minimum, or per-level count is printed.
            declared_blocks = 0
            scanned_blocks = 0
            visible_cells = 0
            hidden_checked = 0
            ext_checked = 0
            unreachable = []
            for c in cols:
                if c.get("role") != "categorical":
                    continue
                declared_blocks += 1
                b = c.get("categorical")
                if b is None or not isinstance(b, dict) or "levels" not in b:
                    unreachable.append("column:" + str(c.get("name")))
                    continue
                scanned_blocks += 1
                for l in b["levels"]:
                    v = l["count"]
                    assert type(v) is int and (v == 0 or v >= threshold), "column '" + str(c.get("name")) + "': released level below threshold"
                    visible_cells += 1
            if tier == 3 and (rels is None or "crosstabs" not in rels):
                status = "NOT_VERIFIED"
                reason = "crosstab collection absent at tier 3; the sweep could not be completed"
            elif rels is not None and "crosstabs" in rels:
                for b in rels["crosstabs"]:
                    declared_blocks += 1
                    if b.get("available") is not True:
                        # An unavailable block must carry no cells at all; cells here would be a release.
                        assert "cells" not in b, "crosstab " + str(b.get("pair")) + ": unavailable block carries cells"
                        scanned_blocks += 1
                        continue
                    if "cells" not in b:
                        unreachable.append("crosstab:" + str(b.get("pair")))
                        continue
                    scanned_blocks += 1
                    hidden_positions = []
                    for position, v in enumerate(b["cells"]):
                        if v is None:
                            hidden_positions.append(position)
                            continue
                        assert type(v) is int and (v == 0 or v >= threshold), "crosstab " + str(b.get("pair")) + " cell position " + str(position) + ": below threshold"
                        visible_cells += 1
                    # INTENT: a hidden cell the released totals pin exactly is an emitted cell.
                    # REASONING: with hidden cells as edges of the row/column graph, differencing
                    # the totals recovers exactly the bridge edges (cells on no cycle). Each hidden
                    # cell is tested by removing it and asking whether its row still reaches its
                    # column through other hidden cells.
                    # ASSUMES: every margin is known (worst case); a collapsed entry whose cells are
                    # all null releases no visible cell and is exempt. A FAIL names positions only.
                    n_r, n_c = b.get("rows"), b.get("cols")
                    assert type(n_r) is int and type(n_c) is int and n_r > 0 and n_c > 0 and n_r * n_c == len(b["cells"]), "crosstab " + str(b.get("pair")) + ": rows x cols does not match the released cells"
                    if len(hidden_positions) > 0 and not (b.get("collapsed") is True and len(hidden_positions) == n_r * n_c):
                        hidden_grid = np.zeros((n_r, n_c), dtype=bool)
                        for position in hidden_positions:
                            hidden_grid[position // n_c, position % n_c] = True
                        for position in hidden_positions:
                            hr, hc = position // n_c, position % n_c
                            label = [-1] * (n_r + n_c)
                            for start in range(n_r + n_c):
                                if label[start] >= 0:
                                    continue
                                label[start] = start
                                stack = [start]
                                while len(stack) > 0:
                                    vertex = stack.pop()
                                    if vertex < n_r:
                                        nbrs = [n_r + int(j) for j in np.flatnonzero(hidden_grid[vertex, :]) if not (vertex == hr and int(j) == hc)]
                                    else:
                                        nbrs = [int(i) for i in np.flatnonzero(hidden_grid[:, vertex - n_r]) if not (int(i) == hr and vertex - n_r == hc)]
                                    for w in nbrs:
                                        if label[w] < 0:
                                            label[w] = start
                                            stack.append(w)
                            assert label[hr] == label[n_r + hc], ("crosstab " + str(b.get("pair")) + ": hidden cell at row index " + str(hr) +
                                                                  ", column index " + str(hc) + " is recoverable from the released totals")
                            hidden_checked += 1
                    # INTENT: no missing-partner count below threshold is pinned by the released totals,
                    # beyond the baseline the released counts fix on their own.
                    # REASONING: rebuilt from released facts only -- level counts, nonmissing_n,
                    # row_count, entry n and visible cells -- as an analyst would. The extended table adds
                    # a partner-missing column and row; the both-missing corner is known from released
                    # counts. A missing-partner cell that is a bridge of the extended graph is the only
                    # hidden cell crossing the cut around its side, so its count is the totals of the rows
                    # on that side, minus the totals of the columns on that side, minus the known cells
                    # leaving the side, plus the known cells entering it. Exempt (baseline): the missing
                    # column of a one-row table and the missing row of a one-column table.
                    # ASSUMES: a FAIL names the row or column index only, never a count. Without the pair
                    # columns' released categories the sweep cannot run, and that is a FAIL.
                    nonmissing = [by_name[name]["nonmissing_n"] for name in b["pair"]]
                    residual = [nonmissing[0] - b["n"], nonmissing[1] - b["n"]]
                    assert min(residual) >= 0, "crosstab " + str(b.get("pair")) + ": entry n exceeds a pair column's nonmissing_n"
                    if max(residual) > 0:
                        totals = []
                        for name in b["pair"]:
                            level_counts = {l["value"]: l["count"] for l in by_name[name]["categorical"]["levels"]}
                            kept = sorted(v for v in level_counts if v != "__OTHER__")
                            totals.append([level_counts[v] for v in kept + (["__OTHER__"] if "__OTHER__" in level_counts else [])])
                        assert [len(totals[0]), len(totals[1])] == [n_r, n_c], "crosstab " + str(b.get("pair")) + ": rows x cols differ from the released categories; the missing-partner sweep could not run"
                        miss_row, miss_col = n_r + n_c, n_r + n_c + 1
                        row_vertices = list(range(n_r)) + [miss_row]
                        col_vertices = list(range(n_r, n_r + n_c)) + [miss_col]
                        row_total = totals[0] + [rows - nonmissing[0]]
                        col_total = totals[1] + [rows - nonmissing[1]]
                        corner = (rows - nonmissing[0]) + (rows - nonmissing[1]) - (rows - b["n"])
                        known = [(position // n_c, n_r + position % n_c, v) for position, v in enumerate(b["cells"]) if v is not None] + [(miss_row, miss_col, corner)]
                        ext_cells = (([(i, miss_col, n_r == 1) for i in range(n_r)] if residual[0] > 0 else []) +
                                     ([(miss_row, n_r + j, n_c == 1) for j in range(n_c)] if residual[1] > 0 else []))
                        edges = [(position // n_c, n_r + position % n_c) for position in hidden_positions] + [(u, w) for u, w, _ in ext_cells]
                        adjacency = [[] for _ in range(n_r + n_c + 2)]
                        for edge_index, (u, w) in enumerate(edges):
                            adjacency[u].append((w, edge_index))
                            adjacency[w].append((u, edge_index))
                        for ext_index, (u, w, exempt) in enumerate(ext_cells):
                            if exempt:
                                continue
                            skip = len(hidden_positions) + ext_index
                            label = [-1] * (n_r + n_c + 2)
                            for start in range(n_r + n_c + 2):
                                if label[start] >= 0:
                                    continue
                                label[start] = start
                                stack = [start]
                                while len(stack) > 0:
                                    vertex = stack.pop()
                                    for neighbor, edge_index in adjacency[vertex]:
                                        if edge_index != skip and label[neighbor] < 0:
                                            label[neighbor] = start
                                            stack.append(neighbor)
                            ext_checked += 1
                            if label[u] == label[w]:
                                continue
                            in_side = [label[vertex] == label[u] for vertex in range(n_r + n_c + 2)]
                            value = (sum(t for t, vertex in zip(row_total, row_vertices) if in_side[vertex]) -
                                     sum(t for t, vertex in zip(col_total, col_vertices) if in_side[vertex]))
                            for r_vertex, c_vertex, v in known:
                                if in_side[r_vertex] and not in_side[c_vertex]:
                                    value -= v
                                elif in_side[c_vertex] and not in_side[r_vertex]:
                                    value += v
                            assert not (0 < value < threshold), ("crosstab " + str(b.get("pair")) + ": missing-partner cell at " +
                                                                 ("row index " + str(u) if w == miss_col else "column index " + str(w - n_r)) +
                                                                 " is recoverable from the released totals")
            if status == "PASS" and len(unreachable) > 0:
                status = "FAIL"
                reason = "scanned " + str(scanned_blocks) + " of " + str(declared_blocks) + " declared blocks; unreachable: " + ", ".join(unreachable)
            elif status == "PASS":
                detail = (str(scanned_blocks) + " of " + str(declared_blocks) + " declared blocks scanned, " +
                          str(visible_cells) + " visible cells, all >= threshold " + str(threshold) + "; " +
                          str(hidden_checked) + " hidden cross-tab cells checked, none recoverable from the row and column totals; " +
                          str(ext_checked) + " missing-partner cells checked, none below threshold recoverable from the released totals")
        elif check_name == "correlation_matrix_symmetric":
            if tier != 3:
                status, applicable = "NOT_APPLICABLE", False
                reason = "tier " + str(tier) + " releases no correlations"
            elif rels is None or "pearson" not in rels or "spearman" not in rels:
                status = "NOT_VERIFIED"
                reason = "pearson/spearman block absent at tier 3"
            else:
                released = [k for k in ("pearson", "spearman") if rels[k].get("available") is True]
                if len(released) == 0:
                    status, applicable = "NOT_APPLICABLE", False
                    reason = "0 of 2 correlation blocks released (" + str(rels["pearson"].get("reason", "no reason stated")) + ")"
                else:
                    max_asymmetry = 0.0
                    shapes = []
                    for k in released:
                        b = rels[k]
                        m = np.array(b["matrix"], dtype=float)
                        dim = len(b["columns"])
                        assert dim >= 2 and m.shape == (dim, dim) and np.isfinite(m).all(), k + ": matrix shape or finiteness"
                        assert np.allclose(m, m.T, atol=1e-6, rtol=0), k + ": matrix is not symmetric"
                        assert np.allclose(np.diag(m), 1, atol=1e-6, rtol=0), k + ": diagonal is not 1"
                        assert (np.abs(m) <= 1).all(), k + ": correlation outside [-1, 1]"
                        max_asymmetry = max(max_asymmetry, float(np.abs(m - m.T).max()))
                        shapes.append(k + " " + str(dim) + "x" + str(dim))
                    detail = ", ".join(shapes) + "; max asymmetry " + format(max_asymmetry, ".2e") + " <= 1e-06 tolerance"
        else:
            if tier != 3:
                status, applicable = "NOT_APPLICABLE", False
                reason = "tier " + str(tier) + " releases no relationships"
            elif rels is None:
                status = "NOT_VERIFIED"
                reason = "relationships block absent at tier 3"
            else:
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
                            assert set(b) == base | {"reason"} and b["reason"] in ("insufficient_support", "ineligible_marginal", "small_complement_group", "zero_pair_variance", "ineligible_roles", "degenerate_table")
                            continue
                        assert b["n"] >= (cutoff if kind == "named" else threshold)
                        if kind == "named":
                            assert set(b) == base | {"pearson", "spearman", "ols"} and all(c in eligible for c in pair)
                            assert all(b["n"] <= by_name[c]["numeric"]["n"] for c in pair)
                            # Complement groups (finite in one column, not the other) are 0 or >= threshold.
                            assert all(by_name[c]["numeric"]["n"] - b["n"] == 0 or by_name[c]["numeric"]["n"] - b["n"] >= threshold for c in pair), \
                                "named entry (" + str(pair[0]) + " ~ " + str(pair[1]) + "): a complement group is below threshold"
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
                # INTENT: each cross-tab sits on its own pair and on the released categories.
                # REASONING: a second table of one pair can be suppressed differently and combined
                # with the first; a row or column for a pooled source level can be subtracted from
                # __OTHER__. Rows/cols equal to the released level counts rule the latter out.
                # Messages name the entry index (0-based, as in the JSON) and column names only.
                for entry_index, b in enumerate(rels["crosstabs"]):
                    pair = b["pair"]
                    assert pair[0] != pair[1], "crosstab entry " + str(entry_index) + ": pair names one column twice"
                    assert all(set(rels["crosstabs"][i]["pair"]) != set(pair) for i in range(entry_index)), "crosstab entry " + str(entry_index) + ": repeats the pair of an earlier entry"
                    if b["available"] is True:
                        level_counts = [len(by_name[c].get("categorical", {}).get("levels", [])) for c in pair]
                        assert [b["rows"], b["cols"]] == level_counts, ("crosstab entry " + str(entry_index) + " (" + pair[0] + " x " + pair[1] +
                                                                        "): rows x cols differ from the released level counts of its pair columns")
                entries = len(rels["named"]) + len(rels["cramers_v"]) + len(rels["crosstabs"])
                detail = "2 correlation blocks + " + str(entries) + " relationship entries checked for support and shape"
    except Exception as exc:
        # INTENT: a FAIL names the failing field/column and what was observed, not just a class.
        # A bare `assert cond` carries no message, so str(exc) is empty and splitlines() is
        # []; the reason must stay non-empty or the aggregation would downgrade it to
        # NOT VERIFIED and lose the fact that a check actually ran and actually failed.
        status, applicable = "FAIL", True
        exc_lines = str(exc).splitlines()
        exc_text = exc_lines[0][:300] if len(exc_lines) > 0 else "assertion failed without a message"
        reason = type(exc).__name__ + ": " + exc_text
    if status == "PASS" and len(detail) == 0:
        detail = reason
    check_details[check_name] = detail if len(detail) > 0 else reason
    checks.append({"name": check_name, "status": status, "applicable": applicable, "reason": reason})
# INTENT: completeness is required, not vacuous all([]); exceptions cannot become N/A.
# REASONING: counters derive the verdict, so a check that never ran cannot be absorbed
# into a silent pass -- NOT VERIFIED and a short checks list both force FAILED.
profile = {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}
for c in checks:
    if not (type(c["reason"]) is str and len(c["reason"]) > 0):
        c["status"], c["applicable"], c["reason"] = "NOT_VERIFIED", True, "check carries an empty reason"
        check_details[c["name"]] = c["reason"]
    if c["status"] not in status_tokens:
        c["status"], c["applicable"] = "NOT_VERIFIED", True
        c["reason"] = "unrecognized validation status"
        check_details[c["name"]] = c["reason"]
    profile[counter_keys[c["status"]]] += 1
    print(status_tokens[c["status"]] + " " + c["name"] + ": " + check_details.get(c["name"], c["reason"]))
all_passed = (profile["failed"] == 0 and profile["not_verified"] == 0 and
              [c["name"] for c in checks] == required_checks)
print("Checks: {passed} passed, {warning} warnings, {failed} failed, "
      "{not_verified} not verified, {skipped} skipped".format(**profile))
if (profile["failed"] > 0 or profile["not_verified"] > 0 or not all_passed or
        profile["passed"] + profile["warning"] + profile["failed"] == 0):
    profile_verdict = "FAILED"
elif profile["warning"] > 0:
    profile_verdict = "PASSED WITH WARNINGS"
else:
    profile_verdict = "PASSED"
print("PROFILE VALIDATION: " + profile_verdict)
report["validation"] = {"checks": checks, "all_passed": all_passed}
if not all_passed:
    print("VALIDATION FAILED -- no reports written; do not share. Failed checks:")
    unresolved = [c["name"] for c in checks if c["status"] in ("FAIL", "NOT_VERIFIED")]
    print(", ".join(unresolved) if len(unresolved) > 0 else "(required checks missing from the validation list)")
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
