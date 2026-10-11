#!/usr/bin/env python3
"""Runtime regression CLI for the standalone T1-T3 privacy profilers.

Run through a fresh captured driver, not run_with_capture on this reusable tool.
Only fabricated Parquet is used. All subprocesses run through the capture wrapper
with project-local TMPDIR. Copies preserve shipped code except configuration and
explicit FAULT INJECTION blocks. Each invocation requires a new scratch directory.

Evidence/hypotheses: archived source hashes establish the tested implementation;
positive controls challenge over-suppression, negative fixtures challenge missing
support gates, candidate mutations challenge actual release validation, and I/O
faults challenge success reporting. A failed assertion is retained, never waived.
"""
import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import textwrap
import copy

CHECKS = ["column_shapes_and_support", "percentiles_monotone", "category_counts_le_rowcount",
          "missing_rate_in_unit_interval", "no_subthreshold_cells_emitted",
          "correlation_matrix_symmetric", "relationship_support_and_shape"]
GRID = ["p1", "p5", "p10", "p25", "p50", "p75", "p90", "p95", "p99"]


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def replace_once(source, old, new):
    require(source.count(old) == 1, f"Injection/config anchor count != 1: {old!r}")
    return source.replace(old, new, 1)


def run_captured(path, base, env):
    command = ["bash", str(base / "scripts/run_with_capture.sh"), str(path)]
    result = subprocess.run(command, env=env, cwd=path.parent, capture_output=True, text=True, timeout=180)
    path.with_suffix(path.suffix + ".runner.log").write_text(result.stdout + result.stderr)
    print("COMMAND", " ".join(command), "EXIT", result.returncode, flush=True)
    return result


def inspect_report(report, frame, tier, threshold):
    """Independent expectations derive from fabricated input, not asset internals."""
    import numpy as np
    require(report["report_version"] == "2.0", "Wrong report version")
    require(report["generator"]["template_version"] == "2.0", "Wrong template version")
    require(report["settings"]["support_unit"] == "record", "Wrong support unit")
    require(report["settings"]["full_summary_cutoff"] == max(threshold, 10), "Wrong cutoff")
    require(report["dataset"] == {"row_count": frame.height, "column_count": frame.width}, "Wrong dataset shape")
    require([c["name"] for c in report["columns"]] == frame.columns, "Wrong column order/names")
    require(("relationships" in report) == (tier == 3), "Wrong relationship tier")
    for c in report["columns"]:
        if tier == 1:
            require(set(c) == {"name", "dtype"}, "T1 leaks marginal fields")
            continue
        raw = frame[c["name"]].to_list()
        nn = sum(v is not None and not (isinstance(v, float) and math.isnan(v)) for v in raw)
        require(c["nonmissing_n"] == nn, f"{c['name']}: wrong nonmissing count")
        require(abs(c["missing_rate"] - (len(raw) - nn) / len(raw)) <= 0.00000051, "Wrong missingness")
        if "numeric" in c:
            b = c["numeric"]
            vals = [v for v in raw if v is not None and math.isfinite(v)]
            n = len(vals)
            require(b["n"] == n, f"{c['name']}: finite support != {n}")
            if nn == 0:
                require(b == {"n": 0, "all_missing": True}, "Wrong all-missing block")
            elif n < threshold:
                require(b == {"n": n, "withheld": True, "reason": "no_finite_values" if n == 0 else "insufficient_support"}, f"Unsupported value fields: {b}")
            elif len(set(vals)) == 1:
                require(set(b) == {"n", "constant", "value", "mean", "sd"} and b["constant"] is True, "Eligible constant suppressed")
                require(b["value"] == b["mean"] == round(vals[0], 6), "Wrong constant value")
                require(b["sd"] == (0 if n > 1 else None), "Wrong constant SD/null")
            else:
                reduced = n < max(threshold, 10)
                keys = ["p25", "p50", "p75"] if reduced else GRID
                expected_keys = {"n", "small_n", "percentiles"} if reduced else {"n", "mean", "sd", "percentiles"}
                require(set(b) == expected_keys, "Wrong reduced/full block")
                require(set(b["percentiles"]) == set(keys), "Wrong percentile grid")
                expected = np.quantile(vals, [int(k[1:]) / 100 for k in keys])
                require(np.allclose([b["percentiles"][k] for k in keys], expected, atol=0.00000051, rtol=0), "Wrong percentiles")
                if not reduced:
                    require(abs(b["mean"] - np.mean(vals)) <= 0.00000051, "Wrong/over-suppressed mean")
                    require(abs(b["sd"] - np.std(vals, ddof=1)) <= 0.00000051, "Wrong SD")
        elif "categorical" in c:
            b = c["categorical"]
            require(b["n"] == nn, "Wrong category support")
            counts = [v["count"] for v in b["levels"]]
            require(all(type(v) is int and v >= threshold for v in counts), "Small categorical cell leaked")
            require(sum(counts) == (nn if nn >= threshold else 0), "Wrong category totals")
        else:
            b = c["string_structure"]
            require(b["n"] == nn, "Wrong string support")
            if nn < threshold:
                require(set(b) == {"n", "withheld", "reason"} and b["withheld"], "Below-support string values leaked")
            else:
                require("length_mean" in b and "pattern_flags" in b, "Eligible string withheld")
    rel = report.get("relationships", {})
    if tier == 3:
        by_name = {c["name"]: c for c in report["columns"]}
        for key in ("pearson", "spearman"):
            b = rel[key]
            names = b["columns"]
            require(isinstance(names, list) and isinstance(b["pair_n"], list), "JSON arrays lost")
            require(len(b["pair_n"]) == len(names), "Wrong pair_n dimension")
            for i, a in enumerate(names):
                for j, d in enumerate(names):
                    pair = [(x, y) for x, y in zip(frame[a], frame[d]) if x is not None and y is not None and math.isfinite(x) and math.isfinite(y)]
                    require(b["pair_n"][i][j] == len(pair), "Wrong actual paired support")
            if b["available"]:
                m = np.asarray(b["matrix"])
                require(m.shape == (len(names), len(names)) and len(names) >= 2, "Wrong matrix shape")
                require(np.isfinite(m).all() and np.allclose(m, m.T) and np.allclose(np.diag(m), 1) and (abs(m) <= 1).all(), "Invalid matrix")
                require(np.min(b["pair_n"]) >= max(threshold, 2), "Unsupported matrix")
            else:
                require(b["matrix"] == [] and b["reason"], "Unavailable matrix carries values")
        for kind in ("named", "cramers_v", "crosstabs"):
            require(isinstance(rel[kind], list), "Relationship collection not array")
            for b in rel[kind]:
                pair = [b["outcome"], b["predictor"]] if kind == "named" else b["pair"]
                actual = sum(x is not None and y is not None and (kind != "named" or (math.isfinite(x) and math.isfinite(y))) for x, y in zip(frame[pair[0]], frame[pair[1]]))
                require(b["n"] == actual, "Wrong named/association/cell support")
                if kind == "named":
                    # INTENT: a regression is released only when each complement group (finite in one
                    # column, not the other) is empty or at least threshold; the reason vocabulary
                    # includes small_complement_group. Group sizes are recomputed from the frame.
                    groups = [sum(v is not None and math.isfinite(v) for v in frame[c]) - actual for c in pair]
                    small = any(0 < g < threshold for g in groups)
                    if b["available"]:
                        require(not small, "Named regression released with a complement group below threshold")
                    else:
                        require(b["reason"] in ("insufficient_support", "ineligible_marginal", "small_complement_group", "zero_pair_variance"), f"Unknown named reason {b['reason']}")
                        require((b["reason"] == "small_complement_group") <= small, "small_complement_group without a small group")
                if not b["available"]:
                    require(set(b) == ({"outcome", "predictor", "n", "available", "reason"} if kind == "named" else {"pair", "n", "available", "reason"}), "Unavailable relationship leaks values")
                    continue
                require(actual >= (max(threshold, 10) if kind == "named" else threshold), "Unsupported relationship")
                if kind == "crosstabs":
                    require(len(b["cells"]) == b["rows"] * b["cols"], "Wrong cells length")
                    mask = np.array([v is None for v in b["cells"]]).reshape(b["rows"], b["cols"])
                    require(int(mask.sum()) == b["cells_suppressed"], "Wrong hidden-cell count")
                    require(all(v is None or v == 0 or v >= threshold for v in b["cells"]), "Small cross-tab cell leaked")
                    require(mask.all() if b.get("collapsed") else not ((mask.sum(0) == 1).any() or (mask.sum(1) == 1).any()), "Lone suppressed cell")
                    # INTENT: the table sits on the RELEASED categories of its pair columns.
                    # REASONING: independent tabulation from the fabricated frame -- every source
                    # level the categorical block pools maps to one __OTHER__ row/column; kept labels
                    # in code-point order, pooled category last, zero rows/cols kept. A pooled level
                    # with a row of its own could be subtracted from __OTHER__ to recover its count.
                    # ASSUMES: categorical fixture values are strings; nulls are excluded pairwise.
                    released = [[l["value"] for l in by_name[c]["categorical"]["levels"]] for c in pair]
                    require([b["rows"], b["cols"]] == [len(v) for v in released], "Cross-tab dimensions differ from the released level counts")
                    kept = [sorted(v for v in r if v != "__OTHER__") for r in released]
                    cats = [k + (["__OTHER__"] if "__OTHER__" in r else []) for k, r in zip(kept, released)]
                    tally = {}
                    for x, y in zip(frame[pair[0]], frame[pair[1]]):
                        if x is None or y is None:
                            continue
                        key = (x if x in kept[0] else "__OTHER__", y if y in kept[1] else "__OTHER__")
                        tally[key] = tally.get(key, 0) + 1
                    expected_cells = [tally.get((cats[0][k // b["cols"]], cats[1][k % b["cols"]]), 0) for k in range(b["rows"] * b["cols"])]
                    require(all(v is None or v == e for v, e in zip(b["cells"], expected_cells)), "Visible cross-tab cell differs from the released-category tabulation")
                    # INTENT: no hidden cell may be pinned exactly by the row/column totals.
                    # REASONING: independent of the templates' graph walk -- linear algebra on the
                    # margin equations. Hidden cell h is determined iff the unit vector e_h lies in
                    # the row space of the (rows + cols) x hidden incidence matrix.
                    # ASSUMES: every margin is known (worst case); a fully collapsed entry is exempt.
                    # INTENT: no missing-partner count below threshold may be pinned by the released
                    # totals beyond what the released counts alone fix (the all-hidden baseline).
                    # REASONING: independent of the templates' graph walk -- the extended table adds a
                    # column-variable-missing column and a row-variable-missing row; its totals are
                    # released (level counts, row_count - nonmissing_n) and its corner is derivable. The
                    # unknowns are the hidden core cells plus every missing-partner cell (a missing line
                    # summing to zero is known zeros); a missing-partner cell is determined iff its unit
                    # vector lies in the row space of the extended incidence matrix. The baseline repeats
                    # the test with every core cell unknown. Truth counts come from the fabricated frame.
                    # ASSUMES: missing means null in the fabricated frame, as nonmissing_n counts it.
                    nonnull = [sum(v is not None for v in frame[c]) for c in pair]
                    residual = [nonnull[0] - b["n"], nonnull[1] - b["n"]]
                    if max(residual) > 0:
                        mapped = [[None if v is None else (v if v in kept[t] else "__OTHER__") for v in frame[pair[t]]] for t in (0, 1)]
                        ext = ([("col", i) for i in range(b["rows"])] if residual[0] > 0 else []) + ([("row", j) for j in range(b["cols"])] if residual[1] > 0 else [])
                        # `line` (never `kind`): rebinding the enclosing loop's `kind` here would make
                        # every later cross-tab entry skip the `kind == "crosstabs"` inspection.
                        truth = [sum(1 for x, y in zip(*mapped) if x == cats[0][i] and y is None) if line == "col" else
                                 sum(1 for x, y in zip(*mapped) if x is None and y == cats[1][i]) for line, i in ext]
                        determined = []
                        for baseline in (False, True):
                            unknown = [k for k in range(b["rows"] * b["cols"]) if baseline or b["cells"][k] is None]
                            incidence = np.zeros((b["rows"] + b["cols"] + 2, len(unknown) + len(ext)))
                            for h, k in enumerate(unknown):
                                incidence[k // b["cols"], h] = incidence[b["rows"] + 1 + k % b["cols"], h] = 1
                            for h, (line, i) in enumerate(ext):
                                if line == "col":
                                    incidence[i, len(unknown) + h] = incidence[b["rows"] + b["cols"] + 1, len(unknown) + h] = 1
                                else:
                                    incidence[b["rows"], len(unknown) + h] = incidence[b["rows"] + 1 + i, len(unknown) + h] = 1
                            base_rank = np.linalg.matrix_rank(incidence)
                            flags = []
                            for h in range(len(ext)):
                                unit = np.zeros((1, incidence.shape[1]))
                                unit[0, len(unknown) + h] = 1
                                flags.append(np.linalg.matrix_rank(np.vstack([incidence, unit])) == base_rank)
                            determined.append(flags)
                        for h, (line, i) in enumerate(ext):
                            require(not (0 < truth[h] < threshold and determined[0][h] and not determined[1][h]),
                                    f"Missing-partner {line} cell {i} below threshold is recoverable from the released totals")
                    if not b.get("collapsed"):
                        hidden = [(k // b["cols"], k % b["cols"]) for k, v in enumerate(b["cells"]) if v is None]
                        if hidden:
                            incidence = np.zeros((b["rows"] + b["cols"], len(hidden)))
                            for h, (i, j) in enumerate(hidden):
                                incidence[i, h] = incidence[b["rows"] + j, h] = 1
                            base_rank = np.linalg.matrix_rank(incidence)
                            for h in range(len(hidden)):
                                unit = np.zeros((1, len(hidden)))
                                unit[0, h] = 1
                                require(np.linalg.matrix_rank(np.vstack([incidence, unit])) > base_rank,
                                        f"Hidden cross-tab cell {hidden[h]} recoverable from the row and column totals")
    checks = report["validation"]["checks"]
    require([c["name"] for c in checks] == CHECKS, "Missing/duplicate required checks")
    require(report["validation"]["all_passed"] is True, "Embedded validation failed")
    cols = report["columns"]
    # INTENT: model the expected outcome per check per fixture across the FOUR-state wire
    # enum (PASS | FAIL | NOT_APPLICABLE | NOT_VERIFIED), not the old two-state model.
    # REASONING: the previous model encoded the automatic not-applicable behaviour that was itself
    # the defect, so rerunning it could never detect the defect it was meant to gate.
    # ASSUMES: a structural skip (report declares zero blocks of the relevant kind) is
    # NOT_APPLICABLE with a counted reason; a MISSING required input is NOT_VERIFIED.
    has_grid = any("percentiles" in c.get("numeric", {}) for c in cols)
    has_categorical_role = any(c.get("role") == "categorical" for c in cols)
    has_matrix = any(rel.get(k, {}).get("available", False) for k in ("pearson", "spearman"))
    expected_status = {
        "column_shapes_and_support": "PASS",
        "percentiles_monotone": "PASS" if has_grid else "NOT_APPLICABLE",
        "category_counts_le_rowcount": "PASS" if has_categorical_role else "NOT_APPLICABLE",
        "missing_rate_in_unit_interval": "PASS" if tier >= 2 else "NOT_APPLICABLE",
        # Disclosure sweep: a report with zero categorical/crosstab blocks is an
        # evidence-bearing "0 of 0 declared blocks" PASS, never NOT_APPLICABLE and never
        # a vacuous all([]) success. The profiler has no N/A form for it at any tier.
        "no_subthreshold_cells_emitted": "PASS",
        "correlation_matrix_symmetric": "PASS" if has_matrix else "NOT_APPLICABLE",
        "relationship_support_and_shape": "PASS" if tier == 3 else "NOT_APPLICABLE",
    }
    for c in checks:
        require(c["status"] in ("PASS", "FAIL", "NOT_APPLICABLE", "NOT_VERIFIED"), f"Status outside the wire enum: {c}")
        require(isinstance(c["reason"], str) and len(c["reason"]) > 0, f"Check carries no reason: {c}")
        expected = expected_status[c["name"]]
        require(c["status"] == expected, f"Dishonest applicability: {c} (expected {expected})")
        require(c["applicable"] is (expected != "NOT_APPLICABLE"), f"applicable disagrees with status: {c}")


def build_fixtures():
    import polars as pl
    # INTENT: explicit typed fabricated values separate support from distinctness.
    # REASONING: include eligible controls, not just examples expected to suppress.
    # ASSUMES: each row is one fabricated contributor; no real observations exist.
    fixtures = []
    for threshold in (5, 1, 7, 12):
        supports = sorted(set([0, 1, 4, 5, 6, 9, 10, threshold - 1, threshold, threshold + 1, max(threshold, 10)]))
        data = {}
        for n in supports:
            data[f"support_{n}"] = pl.Series([913456.25 + i * 2 for i in range(n)] + [None] * (30 - n), dtype=pl.Float64)
            data[f"constant_{n}"] = pl.Series([923456.25] * n + [None] * (30 - n), dtype=pl.Float64)
        fixtures.append((f"boundary_k{threshold}", pl.DataFrame(data), 2, threshold, [], None))
    fixtures.append(("isolated_four", pl.DataFrame({"x": [933451.25, 933452.25, 933453.25, 933454.25]}), 3, 5, [], None))
    fixtures.append(("isolated_constant_four", pl.DataFrame({"x": [943456.25] * 4}), 3, 5, [], None))
    fixtures.append(("constant5000", pl.DataFrame({"constant": [723456.25] * 5000}), 3, 5, [], None))
    fixtures.append(("rare_controls", pl.DataFrame({"binary": [1] * 3 + [0] * 997, "missing_two": list(range(998)) + [None] * 2,
        "observed_two": pl.Series([813456.25, 813457.25] + [None] * 998, dtype=pl.Float64)}), 2, 5, [], None))
    fixtures.append(("nonfinite", pl.DataFrame({"no_finite": pl.Series([float('inf'), -float('inf'), float('nan'), None] * 5),
        "finite_four": pl.Series([823451.25, 823452.25, 823453.25, 823454.25] + [float('inf')] * 16),
        "finite_ten": pl.Series([i + .25 for i in range(10)] + [float('inf')] * 10)}), 2, 5, [], None))
    dense = pl.DataFrame({"x": [i * .2 for i in range(120)], "y": [i * .7 + (i % 7) for i in range(120)],
        "constant": [11.25] * 120, "group": ["A"] * 60 + ["B"] * 60, "sector": ["X", "Y"] * 60})
    fixtures.append(("dense_t3", dense, 3, 5, [["y", "x"], ["group", "sector"], ["constant", "x"]], None))
    # INTENT: numeric-only profile drives the literal copula/named snippets with a constant control.
    # REASONING: avoid rewriting example loops for unrelated categorical generation.
    # ASSUMES: selecting known columns preserves the 120 fabricated records.
    dense_numeric = dense.select("x", "y", "constant")
    require(dense_numeric.shape == (120, 3), "Numeric generation fixture shape")
    fixtures.append(("dense_numeric_t3", dense_numeric, 3, 5, [["y", "x"], ["constant", "x"]], None))
    fixtures.append(("paired_four", pl.DataFrame({"x": pl.Series(list(range(10)) + [None] * 6, dtype=pl.Float64),
        "y": pl.Series([None] * 6 + list(range(10)), dtype=pl.Float64)}), 3, 5, [["y", "x"]], "insufficient_pair_support"))
    fixtures.append(("pair_zero_variance", pl.DataFrame({"x": pl.Series([3.] * 5 + list(range(5)) + [None] * 5, dtype=pl.Float64),
        "y": pl.Series(list(range(5)) + [None] * 5 + list(range(5)), dtype=pl.Float64)}), 3, 5, [["y", "x"]], "zero_pair_variance"))
    fixtures.append(("categorical_pool", pl.DataFrame({"group": ["A"] * 20 + ["B"] * 5 + ["rare"]}), 2, 5, [], None))
    fixtures.append(("categorical_cells", pl.DataFrame({"group": ["A"] * 11 + ["B"] * 20, "sector": ["X"] + ["Y"] * 10 + ["X"] * 10 + ["Y"] * 10}), 3, 5, [["group", "sector"]], None))
    # INTENT: genuine bridge shape -- primary hidden cells form two cycles joined by ONE cell
    # (row 1, column 2), which the lone-cell rule misses and margin differencing recovers.
    # REASONING: this 4x4 table is the counterexample a review recovered exactly from released
    # totals; the profilers must now hide one more cell (or collapse) and both must agree.
    bridge_table = [[2, 3, 10, 12], [1, 4, 2, 15], [11, 13, 3, 1], [9, 8, 4, 2]]
    fixtures.append(("bridge_4x4", pl.DataFrame({
        "cat_a": [f"a{i}" for i in range(4) for j in range(4) for _ in range(bridge_table[i][j])],
        "cat_b": [f"b{j}" for i in range(4) for j in range(4) for _ in range(bridge_table[i][j])]}), 3, 5, [["cat_a", "cat_b"]], None))
    # INTENT: collapse branch -- the bridge (row 0, column 2) joins two hidden 2x2 cycles, but
    # every visible cell that could close a cycle through it is a structural zero, which stays
    # visible; with no joining non-zero cell the whole table must collapse (all null).
    collapse_table = [[3, 2, 4, 0], [2, 3, 0, 0], [0, 0, 3, 2], [0, 0, 2, 3]]
    fixtures.append(("bridge_collapse", pl.DataFrame({
        "cat_a": [f"a{i}" for i in range(4) for j in range(4) for _ in range(collapse_table[i][j])],
        "cat_b": [f"b{j}" for i in range(4) for j in range(4) for _ in range(collapse_table[i][j])]}), 3, 5, [["cat_a", "cat_b"]], None))
    # INTENT: pooled-level rows -- g pools p1 (6, rolled in) and p2 (2) into __OTHER__ (8). Tabulated on
    # raw source levels, p1's row [6, 0] would be fully visible and __OTHER__ - 6 would recover p2's 2.
    # REASONING: on the released categories the table is rows A, B, C, __OTHER__ x cols W, X, Y; C and
    # W are released levels with no pair-complete record, so they stay as rows/columns of zeros.
    # ASSUMES: code-point label order ("W" < "X" < "Y"; "A" < "B" < "C"), pooled category last.
    g = ["A"] * 30 + ["B"] * 20 + ["C"] * 7 + ["p1"] * 6 + ["p2"] * 2 + [None] * 6
    h = ["X", "Y"] * 15 + ["X", "Y"] * 10 + [None] * 7 + ["X"] * 6 + ["X"] * 2 + ["W"] * 6
    fixtures.append(("pooled_level_rows", pl.DataFrame({"g": g, "h": h}), 3, 5, [["g", "h"]], None))
    # INTENT: label order -- mixed case, non-ASCII and a tie. Released cross-tab rows/columns follow
    # code-point order in both languages (not locale collation), and of the two levels tied at 6 the
    # roll-in pools the one later in code-point order ("y"), keeping "x", in both languages.
    # Every mixed x side cell is >= 8, so nothing is hidden and the visible cells pin the full order.
    mixed = ["a"] * 20 + ["B"] * 18 + ["b"] * 16 + ["é"] * 22 + ["Z"] * 24
    fixtures.append(("label_order", pl.DataFrame({
        "mixed": mixed + [None] * 23,
        "side": [["x", "Y"][i % 2] for i in range(100)] + [None] * 23,
        "ties": [None] * 100 + ["y"] * 6 + ["x"] * 6 + ["r"] * 2 + ["w"] * 9}), 3, 5, [["mixed", "side"]], None))
    # INTENT: missing-partner cells. Twin tables on one core [[2,3,10],[3,2,10],[10,10,10]]: complete,
    # it releases the four primary cells hidden as a cycle and row a2 fully visible (the core rule
    # alone, unchanged). With two extra a2 records whose cat_b is missing, that visible row would give
    # the missing-partner count (2) as a2's released count minus the row sum, so the repair hides
    # (row 2, column 0) to join a2 to the hidden cycle and then (row 2, column 1) for the core rule.
    # REASONING: pins the documented order and tie-break (smallest joining non-zero cell, first in
    # row-major order), plus the no-change property on the complete twin.
    mp = [[2, 3, 10], [3, 2, 10], [10, 10, 10]]
    mp_a = [f"a{i}" for i in range(3) for j in range(3) for _ in range(mp[i][j])]
    mp_b = [f"b{j}" for i in range(3) for j in range(3) for _ in range(mp[i][j])]
    fixtures.append(("missing_partner_complete_twin", pl.DataFrame({"cat_a": mp_a, "cat_b": mp_b}), 3, 5, [["cat_a", "cat_b"]], None))
    fixtures.append(("missing_partner_repair", pl.DataFrame({"cat_a": mp_a + ["a2", "a2"], "cat_b": pl.Series(mp_b + [None, None], dtype=pl.String)}), 3, 5, [["cat_a", "cat_b"]], None))
    # INTENT: a fully visible table whose only small count is a missing-partner count (a1 with cat_b
    # missing, 2 records) has no hidden cell to join it to. Instead of collapsing, the count gets the
    # primary-cell treatment: hide a1's smallest non-zero cell (row 1, column 1) = 9, then
    # complementary steps hide (1, 0), (2, 0) and (2, 1), leaving row 0 visible and rows 1-2 hidden.
    # REASONING: pins the no-joining-cell fallback, its tie-break and its complementary re-run.
    fv = [[10, 12], [11, 9], [8, 10]]
    fv_a = [f"a{i}" for i in range(3) for j in range(2) for _ in range(fv[i][j])] + ["a1", "a1"]
    fv_b = [f"b{j}" for i in range(3) for j in range(2) for _ in range(fv[i][j])] + [None, None]
    fixtures.append(("missing_partner_no_join",pl.DataFrame({"cat_a": fv_a, "cat_b": pl.Series(fv_b, dtype=pl.String)}), 3, 5, [["cat_a", "cat_b"]], None))
    # INTENT: the column-side mirror of the fallback -- the table transposed, with the only small
    # count a missing-ROW cell (2 records with cat_a missing in column b1), so the exposed line is a
    # core column. The fallback hides b1's smallest non-zero cell (row 1, column 1) = 9; the
    # complementary pass then hides (1, 2) = 10 for row 1, and (0, 1) and (0, 2) for columns 1-2.
    # REASONING: pins the "own core column for a missing-row cell" branch and its tie-break.
    fc = [[10, 11, 8], [12, 9, 10]]
    fc_a = [f"a{i}" for i in range(2) for j in range(3) for _ in range(fc[i][j])] + [None, None]
    fc_b = [f"b{j}" for i in range(2) for j in range(3) for _ in range(fc[i][j])] + ["b1", "b1"]
    fixtures.append(("missing_partner_no_join_column", pl.DataFrame({"cat_a": pl.Series(fc_a, dtype=pl.String), "cat_b": fc_b}), 3, 5, [["cat_a", "cat_b"]], None))
    # INTENT: several cross-tabs in ONE report, each with a missing-partner line: cat_a is missing on
    # 3 records and cat_c on 2, so [cat_a, cat_b], [cat_a, cat_c] and [cat_b, cat_c] all carry a
    # non-zero residual. The last pair repeats the no-join table above on cat_b x cat_c.
    # REASONING: inspect_report once rebound its relationship-kind loop variable inside the first
    # cross-tab's missing-line loop, so every later entry silently skipped inspection. main() replays
    # a leak in the LAST entry and requires the inspection to reject it.
    mb = [f"b{i}" for i in range(3) for j in range(2) for _ in range(fv[i][j])] + ["b1", "b1"]
    mc = [f"c{j}" for i in range(3) for j in range(2) for _ in range(fv[i][j])] + [None, None]
    ma = [None if k % 20 == 7 else f"a{k % 2}" for k in range(len(mb))]
    fixtures.append(("multi_crosstab_missing_lines", pl.DataFrame({"cat_a": pl.Series(ma, dtype=pl.String), "cat_b": mb, "cat_c": pl.Series(mc, dtype=pl.String)}),
                     3, 5, [["cat_a", "cat_b"], ["cat_a", "cat_c"], ["cat_b", "cat_c"]], None))
    # INTENT: regression complement groups. Two records lack y, so x's complement group is 2 (1..k-1):
    # both orders must be unavailable with small_complement_group. Five records lacking y (= k) keep
    # both regressions available.
    gx = [i * 0.5 for i in range(120)]
    gy2 = [None if i in (3, 50) else v * 0.7 + (i % 7) for i, v in enumerate(gx)]
    gy5 = [None if i in (3, 17, 50, 71, 99) else v * 0.7 + (i % 7) for i, v in enumerate(gx)]
    fixtures.append(("named_small_group", pl.DataFrame({"x": gx, "y": pl.Series(gy2, dtype=pl.Float64)}), 3, 5, [["y", "x"], ["x", "y"]], None))
    fixtures.append(("named_group_at_k", pl.DataFrame({"x": gx, "y": pl.Series(gy5, dtype=pl.Float64)}), 3, 5, [["y", "x"], ["x", "y"]], None))
    fixtures.append(("categorical_pair_four", pl.DataFrame({"group": ["A", "B"] * 5 + [None] * 6, "sector": [None] * 6 + ["X", "Y"] * 5}), 3, 5, [["group", "sector"]], None))
    fixtures.append(("categorical_underk", pl.DataFrame({"group": ["A"] * 4 + [None] * 16}), 2, 5, [], None))
    fixtures.append(("escaping", pl.DataFrame({'quoted"\\\t\n雪': ['a"b\\c\t\n雪'] * 10 + ['\x01edge\r'] * 10}), 2, 5, [], None))
    fixtures.append(("strings", pl.DataFrame({"client_id": ['not-shared'] * 4 + [None] * 16, "email": ['name@example.invalid'] * 20}), 2, 5, [], None))
    fixtures.append(("tier1", dense, 1, 5, [], None))
    fixtures.append(("empty", pl.DataFrame({"x": pl.Series([], dtype=pl.Float64)}), 2, 5, [], None))
    return fixtures


def configure(source, language, fixture, folder, tier, threshold, spec):
    values = {"INPUT_PATH": json.dumps(str(fixture)), "DATASET_NAME": '"fixture"', "OUTPUT_DIR": json.dumps(str(folder)),
              "TIER": str(tier), "SUPPRESSION_THRESHOLD": str(threshold)}
    values["RELATIONSHIP_SPEC"] = repr(spec) if language == "python" else "list(" + ", ".join("c(" + ", ".join(json.dumps(v) for v in p) + ")" for p in spec) + ")"
    for key, value in values.items():
        pattern = rf"(?m)^{key}\s*{'=' if language == 'python' else '<-'}[^\n]*$"
        source, count = re.subn(pattern, lambda m: f"{key} {'=' if language == 'python' else '<-'} {value}", source, count=1)
        require(count == 1, f"Missing config {key}")
    return source


def mutate(source, language, mutation):
    # INTENT: corrupt only candidate fields before the shipped validation, one fault per run.
    # REASONING: a replacement validator would not test the product's safety gate.
    # ASSUMES: fixture positions are x/y/constant/group/sector for dense, sparse column first otherwise.
    py = {
        "underk_value": 'report["columns"][0]["numeric"]["mean"] = 923456.25',
        "invalid_rate": 'report["columns"][0]["missing_rate"] = 1.5',
        "invalid_count": 'report["columns"][3]["categorical"]["levels"][0]["count"] = 99999',
        "unordered_grid": 'report["columns"][0]["numeric"]["percentiles"]["p25"] = 99999',
        "invalid_matrix": 'report["relationships"]["pearson"]["matrix"][0][1] = 2.0',
        "missing_check": 'checks.pop()',
        "second_write": 'os.mkdir(txt_path)',
        # Scan completeness: a declared categorical column whose block cannot be reached.
        "missing_categorical_block": 'del report["columns"][3]["categorical"]',
        # A crosstab entry carrying cells_suppressed but no cells must never PASS.
        "crosstab_cells_removed": 'del report["relationships"]["crosstabs"][0]["cells"]',
        # An empty/absent reason is NOT VERIFIED, never a silent pass.
        "empty_reason": 'checks[0]["reason"] = ""',
        # Bridge: re-show the extra cell the repair hid (bridge_4x4 fixture), leaving no lone
        # hidden cell but a bridge at (row 1, column 2) that the totals pin exactly.
        "bridge_restored": 'report["relationships"]["crosstabs"][0]["cells"][13] = 8\nreport["relationships"]["crosstabs"][0]["cells_suppressed"] -= 1',
        # A row of zeros beyond the released categories: totals, nulls and the bridge sweep all
        # still hold, so only the rows-equal-released-levels assertion can catch it.
        "crosstab_extra_row": 'report["relationships"]["crosstabs"][0]["cells"] += [0] * report["relationships"]["crosstabs"][0]["cols"]\nreport["relationships"]["crosstabs"][0]["rows"] += 1',
        # A second entry on the same pair (two tables of one pair can be combined).
        "crosstab_duplicated": 'report["relationships"]["crosstabs"].append(dict(report["relationships"]["crosstabs"][0]))',
        # Re-show the two cells the missing-partner repair hid (missing_partner_repair fixture): the
        # core cycle stays bridge-free, but row a2 is fully visible again and its missing-partner count
        # is pinned -- only the missing-partner sweep can catch it.
        "missing_partner_restored": 'report["relationships"]["crosstabs"][0]["cells"][6] = 10\nreport["relationships"]["crosstabs"][0]["cells"][7] = 10\nreport["relationships"]["crosstabs"][0]["cells_suppressed"] -= 2',
        # Release a regression whose complement group is 2 records (named_small_group fixture).
        "named_group_released": 'del report["relationships"]["named"][0]["reason"]\nreport["relationships"]["named"][0].update(available=True, pearson=0.5, spearman=0.5, ols={"intercept": 0.0, "slope": 1.0, "r_squared": 0.25})',
    }
    r = {
        "underk_value": 'report$columns[[1]]$numeric$mean <- 923456.25',
        "invalid_rate": 'report$columns[[1]]$missing_rate <- 1.5',
        "invalid_count": 'report$columns[[4]]$categorical$levels[[1]]$count <- 99999',
        "unordered_grid": 'report$columns[[1]]$numeric$percentiles$p25 <- 99999',
        "invalid_matrix": 'report$relationships$pearson$matrix[1, 2] <- 2',
        "missing_check": 'checks <- checks[-length(checks)]',
        "second_write": 'dir.create(txt_path)',
        "missing_categorical_block": 'report$columns[[4]]$categorical <- NULL',
        "crosstab_cells_removed": 'report$relationships$crosstabs[[1]]$cells <- NULL',
        "empty_reason": 'checks[[1]]$reason <- NULL',
        "bridge_restored": 'report$relationships$crosstabs[[1]]$cells[[14]] <- 8\nreport$relationships$crosstabs[[1]]$cells_suppressed <- report$relationships$crosstabs[[1]]$cells_suppressed - 1',
        "crosstab_extra_row": 'report$relationships$crosstabs[[1]]$cells <- c(report$relationships$crosstabs[[1]]$cells, as.list(rep(0, report$relationships$crosstabs[[1]]$cols)))\nreport$relationships$crosstabs[[1]]$rows <- report$relationships$crosstabs[[1]]$rows + 1',
        "crosstab_duplicated": 'report$relationships$crosstabs[[length(report$relationships$crosstabs) + 1]] <- report$relationships$crosstabs[[1]]',
        "missing_partner_restored": 'report$relationships$crosstabs[[1]]$cells[[7]] <- 10\nreport$relationships$crosstabs[[1]]$cells[[8]] <- 10\nreport$relationships$crosstabs[[1]]$cells_suppressed <- report$relationships$crosstabs[[1]]$cells_suppressed - 2',
        "named_group_released": 'report$relationships$named[[1]]$reason <- NULL\nreport$relationships$named[[1]]$available <- TRUE\nreport$relationships$named[[1]]$pearson <- 0.5\nreport$relationships$named[[1]]$spearman <- 0.5\nreport$relationships$named[[1]]$ols <- list(intercept = 0, slope = 1, r_squared = 0.25)',
    }
    statement = (py if language == "python" else r)[mutation]
    marker = '# --- Validate ---------------------------------------------------------------'
    if mutation in ("missing_check", "empty_reason"):
        marker = '# INTENT: completeness is required,'
        start = source.index(marker)
        marker = source[start:source.index('\n', start)]
    elif mutation == "second_write":
        marker = '    with open(txt_path, "x", encoding="utf-8") as f:' if language == "python" else '  txt_con <- file(txt_path, open = "wx", encoding = "UTF-8")'
    indent = "    " if mutation == "second_write" and language == "python" else "  " if mutation == "second_write" else ""
    notice = 'print("FAULT_INJECTION_APPLIED")' if language == "python" else 'cat("FAULT_INJECTION_APPLIED\\n")'
    insert = indent + '# FAULT INJECTION: ' + mutation + '\n' + indent + statement + '\n' + indent + notice + '\n'
    return replace_once(source, marker, insert + marker)


def compare_parity(a, b):
    # INTENT: compare support/shape semantics while retaining the documented R 2x2 V difference.
    # REASONING: serialization whitespace, timestamps, generators and tie order are irrelevant.
    import copy
    a, b = copy.deepcopy(a), copy.deepcopy(b)
    for obj in (a, b):
        obj.pop("generated_utc")
        obj.pop("generator")
        for c in obj["columns"]:
            if "categorical" in c:
                c["categorical"]["levels"].sort(key=lambda v: (v["value"], v["count"]))
        for entry in obj.get("relationships", {}).get("cramers_v", []):
            entry.pop("v", None)
    require(a == b, "Python/R support, shapes, metadata or values differ")


def generation_source(base, language, report_path, output, tier3=False):
    doc = base / f'.claude/skills/synthetic-data-workflow/references/generation-patterns-{language}.md'
    blocks = re.findall(r'```(?:python|r)\n(.*?)```', doc.read_text(), re.S)
    require(len(blocks) >= 8, "Generation examples missing")
    config = blocks[0].replace('"clients_2025_profile_report.json"', json.dumps(str(report_path)))
    # INTENT: inline literal documentation snippets into one file with necessary loop bindings.
    # REASONING: test shipped example statements rather than reimplementing their generators.
    # ASSUMES: fixture is numeric-only, so unrelated categorical/identifier generation is out of scope here.
    if language == "python":
        body = config + '\nfidelity_by_name = {}\n'
        body += 'for col in report["columns"]:\n' + textwrap.indent(blocks[1] + '\nfidelity_by_name[col["name"]] = fidelity\n', '    ')
        if tier3:
            body += '\n' + blocks[2] + '\n' + blocks[3]
        body += '\nfor col in report["columns"]:\n' + textwrap.indent(blocks[-2], '    ')
        body += '\n# INTENT: verify nullable types, missingness, constants and unavailable fidelity.\n'
        body += '''for col in report["columns"]:
    b = col["numeric"]
    values = syn[col["name"]]
    assert str(values.dtype) == ("Int64" if col["dtype"] == "integer" else "Float64")
    assert values.isna().sum() == round(col["missing_rate"] * n)
    if b.get("constant"):
        assert (values.dropna() == b["value"]).all()
    if b.get("withheld") or b.get("all_missing"):
        assert fidelity_by_name[col["name"]].startswith("NOT_APPLICABLE")
    else:
        assert fidelity_by_name[col["name"]].startswith("AVAILABLE")
'''
        body += f'\nsyn.to_parquet({json.dumps(str(output))})\nprint("GENERATION_VERIFIED seed=20260715")\n'
    else:
        body = config + '\nfidelity_by_name <- list()\n'
        body += 'for (i in seq_along(report$columns)) {\n' + blocks[1] + '\nfidelity_by_name[[col$name]] <- fidelity\n}\n'
        if tier3:
            body += blocks[2] + '\n' + blocks[3]
        body += '\nfor (i in seq_along(report$columns)) {\ncolname <- report$columns[[i]]$name\n' + blocks[-2] + '\n}\n'
        body += '''# INTENT: verify types, missingness, constants and unavailable fidelity.
for (col in report$columns) {
  b <- col$numeric
  values <- syn[[col$name]]
  stopifnot(typeof(values) == if (col$dtype == "integer") "integer" else "double")
  stopifnot(sum(is.na(values)) == round(col$missing_rate * n))
  if (isTRUE(b$constant)) stopifnot(all(values[!is.na(values)] == b$value))
  if (isTRUE(b$withheld) || isTRUE(b$all_missing)) {
    stopifnot(startsWith(fidelity_by_name[[col$name]], "NOT_APPLICABLE"))
  } else stopifnot(startsWith(fidelity_by_name[[col$name]], "AVAILABLE"))
}
'''
        body += f'\nwrite_parquet(syn, {json.dumps(str(output))})\ncat("GENERATION_VERIFIED seed=20260715\\n")\n'
    return '# Generated from literal generation-patterns snippets; bindings only.\n' + body


def adjudicate_claims(base, work, env, sources, languages, results):
    """Bounded follow-up: characterize five static claims and one consumer branch.

    Acceptance failures remain failures even when they confirm a diagnostic claim.
    No corrective production mutation is applied. A separate source snapshot and
    explicit per-case exit/parse/approval state preserve the adverse evidence.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq
    import pandas as pd
    observations = []
    fixture_data = {
        'reduced': pa.table({'amount': [1., 2., 3., 4., 5., 6.]}),
        'full': pa.table({'amount': [float(i) for i in range(20)]}),
        'underk': pa.table({'amount': [923456.25] * 4 + [None] * 6}),
        'large_constant': pa.table({'amount_cents': pa.array([9007199254740993] * 5, type=pa.int64())}),
        'large_neighbors': pa.table({'amount_cents': pa.array([9007199254740992, 9007199254740993] * 3, type=pa.int64())}),
        'positive_boundary': pa.table({'amount_cents': pa.array([2**53] * 5, type=pa.int64())}),
        'negative_boundary': pa.table({'amount_cents': pa.array([-2**53] * 5, type=pa.int64())}),
        'negative_beyond': pa.table({'amount_cents': pa.array([-2**53 - 1] * 5, type=pa.int64())}),
        'positive_below': pa.table({'amount_cents': pa.array([2**53 - 1] * 5, type=pa.int64())}),
        'negative_below': pa.table({'amount_cents': pa.array([-2**53 + 1] * 5, type=pa.int64())}),
        'float_positive_boundary': pa.table({'amount': [float(2**53)] * 5}),
        'float_negative_boundary': pa.table({'amount': [-float(2**53)] * 5}),
        'literal_other': pa.table({'group': ['A'] * 20 + ['__OTHER__'] * 10 + ['rare1'] * 3 + ['rare2'] * 3}),
        'identifier': pa.table({'client_id': pa.array([11, 12, 13, 14] + [None] * 6, type=pa.int64())}),
    }
    # INTENT: preserve dictionary encoding to test actual R factor behavior, not an injected class.
    # REASONING: C is observed globally but absent among complete pairs; its retained table row is zero.
    # ASSUMES: Arrow may map dictionary input to factors; an explicit reader probe decides that fact.
    values = ['A'] * 10 + ['B'] * 10 + ['C'] * 5
    other = ['X'] * 8 + ['Y'] * 2 + ['X'] * 2 + ['Y'] * 8 + [None] * 5
    fixture_data['factor_pairs'] = pa.table({'group': pa.array(values).dictionary_encode(), 'sector': pa.array(other).dictionary_encode()})
    fixture_data['character_pairs'] = pa.table({'group': values, 'sector': other})
    for name, table in fixture_data.items():
        path = work / f'{name}.parquet'
        pq.write_table(table, path)
        require(pq.read_table(path).equals(table), f'Fabricated fixture changed: {name}')
        print('ADJ_FIXTURE', name, 'rows', table.num_rows, 'schema', table.schema, flush=True)

    # INTENT: inspect exact reader representations without changing any asset execution path.
    # REASONING: loss at the reader differs from loss caused by the profiler's numeric conversion.
    # ASSUMES: only fabricated fields are printed, and subprocess TMPDIR remains project-local.
    for language in languages:
        ext = 'py' if language == 'python' else 'R'
        probe = work / f'representation_probe.{ext}'
        if language == 'python':
            probe.write_text('import pandas as pd\n' +
                '\n'.join(f'df = pd.read_parquet({json.dumps(str(work / (name + ".parquet")))})\nprint({name!r}, df.dtypes.astype(str).to_dict(), df.iloc[:, 0].tolist())' for name in ('large_constant', 'large_neighbors', 'factor_pairs')) + '\n')
        else:
            probe.write_text('# INTENT: observe actual Arrow types and paired factor levels.\n' +
                '\n'.join(f'df <- as.data.frame(arrow::read_parquet({json.dumps(str(work / (name + ".parquet")))}))\ncat({json.dumps(name)}, "class=", class(df[[1]]), "typeof=", typeof(df[[1]]), "values=", as.character(df[[1]]), "\\n")' for name in ('large_constant', 'large_neighbors', 'factor_pairs')) +
                '\ncat("FACTOR_PRESERVED", is.factor(df$group), "\\n")\nok <- complete.cases(df)\nprint(table(df$group[ok], df$sector[ok]))\n')
        r = run_captured(probe, base, env)
        print(r.stdout + r.stderr)
        results.append({'name': f'{language}/representation_probe', 'passed': r.returncode == 0, 'detail': str(probe)})

    cases = []
    if 'r' in languages:
        cases.append(('r', 'percentile_components', 'reduced', 2, [], 'component_shape', False))
        cases.append(('r', 'nested_mean', 'full', 2, [], 'nested_mean', False))
    if 'python' in languages:
        cases.extend([
            ('python', 'ordinary_optimized', 'underk', 2, [], None, True),
            ('python', 'underk_normal_control', 'underk', 2, [], 'underk_value', False),
            ('python', 'underk_optimized', 'underk', 2, [], 'underk_value', True),
        ])
    for language in languages:
        for name in ('large_constant', 'large_neighbors', 'literal_other', 'positive_boundary', 'negative_boundary', 'negative_beyond', 'positive_below', 'negative_below', 'float_positive_boundary', 'float_negative_boundary'):
            cases.append((language, name, name, 2, [], None, False))
        cases.append((language, 'large_tier1', 'large_constant', 1, [], None, False))
        for name in ('factor_pairs', 'character_pairs'):
            cases.append((language, name, name, 3, [['group', 'sector']], None, False))
        cases.append((language, 'identifier_profile', 'identifier', 2, [], None, False))
    identifier_reports = {}
    for language, name, fixture, tier, spec, mutation, optimize in cases:
        folder = work / f'{language}_{name}'
        folder.mkdir()
        ext = 'py' if language == 'python' else 'R'
        path = folder / f'profile.{ext}'
        source = configure(sources[language], language, work / f'{fixture}.parquet', folder, tier, 5, spec)
        if mutation == 'component_shape':
            marker = '# --- Validate ---------------------------------------------------------------'
            injection = '# FAULT INJECTION: malformed scalar percentile components with aggregate length three.\nreport$columns[[1]]$numeric$percentiles <- list(p25 = NULL, p50 = c(1, 2), p75 = 3)\ncat("FAULT_INJECTION_APPLIED\\n")\n'
            source = replace_once(source, marker, injection + marker)
        elif mutation == 'nested_mean':
            marker = '# --- Validate ---------------------------------------------------------------'
            source = replace_once(source, marker, '# FAULT INJECTION: nested moment instead of scalar.\nreport$columns[[1]]$numeric$mean <- list(9.5)\ncat("FAULT_INJECTION_APPLIED\\n")\n' + marker)
        elif mutation:
            source = mutate(source, language, mutation)
        path.write_text(source)
        child_env = env.copy()
        child_env.pop('PYTHONOPTIMIZE', None)
        if optimize:
            child_env['PYTHONOPTIMIZE'] = '1'
        result = run_captured(path, base, child_env)
        jp, tp = folder / 'fixture_profile_report.json', folder / 'fixture_profile_report.txt'
        text = jp.read_text() if jp.exists() else ''
        report, parse_error = None, None
        try:
            if text:
                report = json.loads(text)
        except json.JSONDecodeError as exc:
            parse_error = str(exc)
        observed = {'case': f'{language}/{name}', 'exit': result.returncode, 'optimized_subprocess': optimize,
                    'json_exists': jp.exists(), 'txt_exists': tp.exists(), 'json_parse': bool(report),
                    'json_parse_error': parse_error,
                    'all_passed': report['validation']['all_passed'] if report else bool(re.search(r'"all_passed"\s*:\s*true', text)),
                    'success_message': 'Wrote BOTH reports' in result.stdout,
                    'report_columns': report['columns'] if report else None,
                    'relationships': report.get('relationships') if report else None,
                    'log': str(path.with_suffix(path.suffix + '.runner.log'))}
        # INTENT: compare each observation against the desired behaviour, not against the allegation.
        # REASONING: characterizing a defect successfully does not make product acceptance pass.
        # ASSUMES: generic unrelated failures do not count as a supported precision diagnostic.
        passed = False
        if optimize:
            # Documented startup refusal supersedes candidate execution in optimized mode.
            passed = result.returncode != 0 and not jp.exists() and not tp.exists() and 'optimized Python is unsupported' in (result.stdout + result.stderr) and 'Wrote BOTH reports' not in result.stdout
        elif mutation:
            passed = result.returncode != 0 and not jp.exists() and not tp.exists() and 'VALIDATION FAILED' in result.stdout
        elif name == 'large_tier1':
            passed = result.returncode == 0 and bool(report) and report['columns'] == [{'name': 'amount_cents', 'dtype': 'integer'}]
        elif fixture in ('large_constant', 'large_neighbors', 'positive_boundary', 'negative_boundary', 'negative_beyond', 'float_positive_boundary', 'float_negative_boundary'):
            passed = result.returncode != 0 and not jp.exists() and not tp.exists() and 'Unsupported numeric precision/range' in (result.stdout + result.stderr) and 'Wrote BOTH reports' not in result.stdout
        elif fixture in ('positive_below', 'negative_below'):
            expected = 2**53 - 1 if fixture == 'positive_below' else -2**53 + 1
            b = report['columns'][0].get('numeric', {}) if report else {}
            passed = result.returncode == 0 and bool(report) and b.get('constant') is True and b.get('value') == expected and b.get('mean') == expected and b.get('sd') == 0
        elif fixture == 'literal_other':
            block = report['columns'][0]['categorical'] if report else {}
            levels = block.get('levels', [])
            labels = [b['value'] for b in levels]
            passed = result.returncode == 0 and bool(report) and len(labels) == len(set(labels)) and sorted((b['value'], b['count']) for b in levels) == [('A', 20), ('__OTHER__', 16)] and block.get('n_levels_binned') == 3
        elif fixture in ('factor_pairs', 'character_pairs'):
            passed = bool(report) and result.returncode == 0 and report['relationships']['cramers_v'][0]['available'] is True
        elif fixture == 'identifier':
            passed = bool(report) and report['columns'][0]['dtype'] == 'integer' and report['columns'][0]['string_structure'] == {'n': 4, 'withheld': True, 'reason': 'insufficient_support'}
            if passed:
                identifier_reports[language] = jp
        observed['acceptance_passed'] = bool(passed)
        observations.append(observed)
        results.append({'name': f'{language}/{name}', 'passed': bool(passed), 'detail': str(path)})
        print('ADJ_OBSERVATION', json.dumps(observed), flush=True)
        if mutation and parse_error:
            print('MALFORMED_JSON_TEXT', text, flush=True)

    # INTENT: execute the literal identifier generation snippet, including its own logging branch.
    # REASONING: dtype correctness must not hide missing NOT_APPLICABLE structure fidelity.
    # ASSUMES: positive missingness is eligible; it is not suppressed for a small numerator.
    for language, report_path in identifier_reports.items():
        folder = work / f'{language}_identifier_generation'
        folder.mkdir()
        doc = base / f'.claude/skills/synthetic-data-workflow/references/generation-patterns-{language}.md'
        blocks = re.findall(r'```(?:python|r)\n(.*?)```', doc.read_text(), re.S)
        config = blocks[0].replace('"clients_2025_profile_report.json"', json.dumps(str(report_path)))
        identifier = next(b for b in blocks if 'Synthesize identifier columns structurally' in b or 'Synthesize an email-shaped identifier' in b)
        output = folder / 'synthetic.parquet'
        if language == 'python':
            body = config + '\ncol = report["columns"][0]\n' + identifier + '\n' + blocks[-2]
            body += '\nprint("TYPE", str(syn["client_id"].dtype), "MISSING", int(syn["client_id"].isna().sum()))\nassert str(syn["client_id"].dtype) == "Int64"\nassert syn["client_id"].isna().sum() == 6\n'
            body += f'syn.to_parquet({json.dumps(str(output))})\n'
            ext = 'py'
        else:
            body = config + '\ni <- 1\ncolname <- "client_id"\n' + identifier + '\n' + blocks[-2]
            body += '\ncat("TYPE", typeof(syn$client_id), "MISSING", sum(is.na(syn$client_id)), "\\n")\nstopifnot(typeof(syn$client_id) == "integer", sum(is.na(syn$client_id)) == 6)\n'
            body += f'arrow::write_parquet(syn, {json.dumps(str(output))})\n'
            ext = 'R'
        path = folder / f'generate.{ext}'
        path.write_text('# Literal documentation snippets with configuration/bindings only.\n' + body)
        result = run_captured(path, base, env)
        logging_ok = 'NOT_APPLICABLE' in result.stdout and 'unobserved' in result.stdout
        obs = {'case': f'{language}/identifier_generation', 'exit': result.returncode, 'parquet_exists': output.exists(),
               'unobserved_structure_logged': logging_ok, 'stdout': result.stdout}
        observations.append(obs)
        results.append({'name': f'{language}/identifier_generation_types_missingness', 'passed': result.returncode == 0 and output.exists(), 'detail': str(path)})
        results.append({'name': f'{language}/identifier_generation_unobserved_log', 'passed': logging_ok, 'detail': str(path)})
        print('ADJ_OBSERVATION', json.dumps(obs), flush=True)
    passed = sum(bool(r['passed']) for r in results)
    failed = len(results) - passed
    summary = {'passed': passed, 'failed': failed, 'results': results, 'observations': observations}
    (work / 'results.json').write_text(json.dumps(summary, indent=2) + '\n')
    (work / 'inventory.json').write_text(json.dumps([str(p) for p in sorted(work.rglob('*')) if p.is_file()], indent=2) + '\n')
    print(f'ADJUDICATION_SUMMARY total={len(results)} passed={passed} failed={failed}', flush=True)
    return int(failed > 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-dir', type=Path, default=Path('/daaf'))
    parser.add_argument('--work-dir', type=Path, required=True, help='New directory under research/.../scripts/scratch/')
    parser.add_argument('--languages', nargs='+', choices=['python', 'r'], default=['python', 'r'])
    parser.add_argument('--suite', choices=['all', 'profiles', 'generation', 'adjudication'], default='all')
    args = parser.parse_args()
    base, work = args.base_dir.resolve(), args.work_dir.resolve()
    require(work.is_relative_to(base / 'research') and '/scripts/scratch/' in str(work), 'Use project scratch only')
    require(not work.exists(), 'Choose a fresh work directory; executed artifacts are immutable')
    work.mkdir(parents=True)
    temp = work / 'tmp'
    temp.mkdir()
    env = os.environ.copy()
    env.update(TMPDIR=str(temp), TMP=str(temp), TEMP=str(temp), PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    os.environ.update(TMPDIR=str(temp), TMP=str(temp), TEMP=str(temp))
    (work / 'utility_snapshot.py').write_bytes(Path(__file__).read_bytes())
    import polars as pl
    import pyarrow as pa
    import pyarrow.parquet as pq
    results = []
    reports = {}
    source_by_language = {}
    print('VERSIONS Python', sys.version.split()[0], 'Polars', pl.__version__, 'PyArrow', pa.__version__, flush=True)
    for language in args.languages:
        ext = 'py' if language == 'python' else 'R'
        asset = base / f'.claude/skills/synthetic-data-workflow/assets/profile_data_template.{ext}'
        source_by_language[language] = asset.read_text()
        print('ASSET', asset, 'SHA256', hashlib.sha256(asset.read_bytes()).hexdigest())
    # INTENT: collect dependency evidence before attributing runtime failures to the assets.
    for language in args.languages:
        ext = 'py' if language == 'python' else 'R'
        probe = work / f'dependencies.{ext}'
        probe.write_text('import numpy, pandas, pyarrow, scipy\nprint("DEPENDENCIES_OK", numpy.__version__, pandas.__version__, pyarrow.__version__, scipy.__version__)\n' if language == 'python' else
                         'cat(R.version.string, "\\n")\nfor (p in c("arrow", "jsonlite", "simstudy")) { cat(p, requireNamespace(p, quietly=TRUE), "\\n") }\nstopifnot(requireNamespace("arrow", quietly=TRUE))\n')
        r = run_captured(probe, base, env)
        print(r.stdout + r.stderr)
        results.append({'name': f'{language}/dependencies', 'passed': r.returncode == 0, 'detail': str(probe)})
    if args.suite == 'adjudication':
        return adjudicate_claims(base, work, env, source_by_language, args.languages, results)
    # INTENT: the profilers take no researcher declarations, so no template may carry a
    # user-editable `not_applicable` setting (or code reading one).
    # REASONING: a typed reason would be written verbatim into validation.checks[].reason --
    # a free-text channel across the disclosure boundary. Any occurrence of the identifier
    # is a reintroduced setting; prose saying "not applicable" is not matched.
    for language in args.languages:
        hits = [i + 1 for i, line in enumerate(source_by_language[language].splitlines()) if re.search(r'\bnot_applicable\b', line)]
        results.append({'name': f'{language}/no_declaration_setting', 'passed': len(hits) == 0,
                        'detail': 'no not_applicable identifier in the template' if not hits else f'not_applicable on template lines {hits}'})
    # INTENT: read CPS-INTAKE's accepted NOT_APPLICABLE reason forms from its live Python fence.
    # REASONING: the assertion must track the intake gate itself, not a copy that can drift.
    # ASSUMES: the fence assigns `cpsi_na_reason_forms` as one literal dict closed by a "}" line.
    vc_text = (base / 'agent_reference/VALIDATION_CHECKPOINTS.md').read_text(encoding='utf-8')
    forms_start = vc_text.index('cpsi_na_reason_forms = {')
    forms_end = vc_text.index('\n}\n', forms_start) + 2
    intake_na_forms = ast.literal_eval(vc_text[forms_start + len('cpsi_na_reason_forms = '):forms_end])
    require(set(intake_na_forms) < set(CHECKS), 'CPS-INTAKE reason forms name an unknown check')
    fixtures = build_fixtures()
    for name, frame, tier, threshold, spec, reason in fixtures:
        fixture = work / f'{name}.parquet'
        # INTENT: materialize portable Arrow strings, not view types, for the cross-language suite.
        # REASONING: avoid confusing R Arrow's view-type conversion with this support repair.
        # ASSUMES: fabricated frames have flat primitive schemas.
        table = frame.to_arrow()
        schema = pa.schema([pa.field(f.name, pa.string() if pa.types.is_large_string(f.type) or pa.types.is_string_view(f.type) else f.type) for f in table.schema])
        pq.write_table(table.cast(schema), fixture)
        require(pl.read_parquet(fixture).shape == frame.shape, 'Fixture roundtrip shape failed')
        print('FIXTURE', name, 'shape', frame.shape, 'schema', str(frame.schema), 'nulls', frame.null_count().row(0))
        for language in args.languages:
            ext = 'py' if language == 'python' else 'R'
            folder = work / f'{language}_{name}'
            folder.mkdir()
            path = folder / f'profile.{ext}'
            source = configure(source_by_language[language], language, fixture, folder, tier, threshold, spec)
            path.write_text(source)
            result = run_captured(path, base, env)
            jp, tp = folder / 'fixture_profile_report.json', folder / 'fixture_profile_report.txt'
            try:
                if name == 'empty':
                    require(result.returncode != 0 and not jp.exists() and not tp.exists(), 'Empty input accepted')
                else:
                    require(result.returncode == 0, f'Asset failed: {path.with_suffix(path.suffix + ".runner.log")}')
                    require(jp.exists() and tp.exists() and 'Wrote BOTH reports' in result.stdout, 'No dual-output success')
                    # The count line and the derived verdict must be on stdout, and the
                    # verdict must agree with all_passed (true here, so PASSED).
                    require('Checks: ' in result.stdout, 'No Checks: count line on stdout')
                    require('PROFILE VALIDATION: PASSED' in result.stdout, 'No derived PASSED verdict on an accepted candidate')
                    require('PROFILE VALIDATION: FAILED' not in result.stdout, 'Accepted candidate also reported FAILED')
                    report = json.loads(jp.read_text())
                    txt = tp.read_text()
                    txt_json, _ = json.JSONDecoder().raw_decode(txt.split('EXACT RELEASE CANDIDATE (same fields and values as JSON):', 1)[1].lstrip())
                    require(txt_json == report, 'TXT/JSON release differs')
                    inspect_report(report, frame, tier, threshold)
                    if reason:
                        require(report['relationships']['pearson'].get('reason') == reason, 'Expected pairwise unavailability missing')
                    if name == 'dense_t3':
                        require(report['relationships']['pearson']['available'] and report['relationships']['named'][0]['available'], 'Dense eligible relationship suppressed')
                    if name == 'categorical_pair_four':
                        require(not report['relationships']['cramers_v'][0]['available'] and not report['relationships']['crosstabs'][0]['available'], 'Sparse categorical relationship released')
                    if name == 'rare_controls':
                        c = {c['name']: c for c in report['columns']}
                        require(c['binary']['numeric']['mean'] == .003 and c['missing_two']['missing_rate'] == .002, 'Rare numerator over-suppressed')
                    if name.startswith('isolated_'):
                        released_text = jp.read_text() + txt + result.stdout + result.stderr
                        require('93345' not in released_text and '943456' not in released_text, 'Below-k value appeared in JSON/TXT/console')
                    if name == 'categorical_pool':
                        levels = report['columns'][0]['categorical']['levels']
                        require(sorted((b['value'], b['count']) for b in levels) == [('A', 20), ('__OTHER__', 6)], 'Complementary rare-level roll-in failed')
                    if name == 'bridge_4x4':
                        # INTENT: pin the documented tie-break -- the smallest visible non-zero cell
                        # joining the bridge's two sides is (row 3, column 1) = 8 -- and replay the
                        # review's differencing attack, which must no longer return the true 2.
                        ct = report['relationships']['crosstabs'][0]
                        primary = {0, 1, 4, 5, 6, 10, 11, 14, 15}
                        require(ct.get('collapsed') is not True and ct['cells_suppressed'] == 10, 'Bridge table not repaired by one extra cell')
                        require({k for k, v in enumerate(ct['cells']) if v is None} == primary | {13}, 'Bridge repair hid an unexpected cell')
                        levels = {c['name']: {l['value']: l['count'] for l in c['categorical']['levels']} for c in report['columns']}
                        grid = [[0 if v is None else v for v in ct['cells'][i * 4:(i + 1) * 4]] for i in range(4)]
                        row_hidden = [levels['cat_a'][f'a{i}'] - sum(grid[i]) for i in range(4)]
                        col_hidden = [levels['cat_b'][f'b{j}'] - sum(grid[i][j] for i in range(4)) for j in range(4)]
                        require(row_hidden[0] + row_hidden[1] - col_hidden[0] - col_hidden[1] != 2, 'Review differencing attack still recovers the bridge cell')
                    if name == 'pooled_level_rows':
                        # Rows A, B, C, __OTHER__ x columns W, X, Y; no row for p1 or p2. The released
                        # __OTHER__ row equals the released pooled count, so differencing isolates nothing.
                        ct = report['relationships']['crosstabs'][0]
                        levels = {c['name']: [(l['value'], l['count']) for l in c['categorical']['levels']] for c in report['columns']}
                        require(levels['g'] == [('A', 30), ('B', 20), ('C', 7), ('__OTHER__', 8)] and levels['h'] == [('X', 33), ('Y', 25), ('W', 6)], 'Unexpected released levels for the pooled-row fixture')
                        require([ct['rows'], ct['cols']] == [4, 3], 'Pooled source levels got rows of their own')
                        require(ct['cells'] == [0, 15, 15, 0, 10, 10, 0, 0, 0, 0, 8, 0] and ct['cells_suppressed'] == 0, 'Cross-tab not on released categories in code-point order with zero rows/columns kept')
                    if name == 'label_order':
                        # Tie-break: the roll-in pools "y" (later in code-point order), keeping "x".
                        ties = next(c for c in report['columns'] if c['name'] == 'ties')['categorical']
                        require([(l['value'], l['count']) for l in ties['levels']] == [('w', 9), ('x', 6), ('__OTHER__', 8)], 'Tied levels not ordered by code point before roll-in')
                        ct = report['relationships']['crosstabs'][0]
                        require([ct['rows'], ct['cols']] == [5, 2] and ct['cells_suppressed'] == 0, 'Label-order cross-tab shape or suppression changed')
                    if name.startswith('missing_partner_'):
                        ct = report['relationships']['crosstabs'][0]
                        expected = {'missing_partner_complete_twin': ([None, None, 10, None, None, 10, 10, 10, 10], 4, False),
                                    'missing_partner_repair': ([None, None, 10, None, None, 10, None, None, 10], 6, False),
                                    # No joining cell: the exposed a1 count gets the primary-cell treatment
                                    # (hide a1's smallest non-zero cell, then complementary steps), not a collapse.
                                    'missing_partner_no_join': ([10, 12, None, None, None, None], 4, False),
                                    # Column side: the exposed line is core column 1, so the fallback
                                    # starts there; the release is the transpose of the row-side pin.
                                    'missing_partner_no_join_column': ([10, None, None, 12, None, None], 4, False)}[name]
                        require((ct['cells'], ct['cells_suppressed'], ct.get('collapsed') is True) == expected, f'Missing-partner fixture released {ct["cells"]}')
                    if name == 'multi_crosstab_missing_lines':
                        # INTENT: every entry carries a missing-partner line, so the fixture keeps
                        # exercising inspection beyond the first such entry.
                        cts = report['relationships']['crosstabs']
                        by_name = {c['name']: c for c in report['columns']}
                        require(len(cts) == 3 and all(e['available'] for e in cts), 'Multi-cross-tab fixture lost an entry')
                        require(all(max(by_name[p]['nonmissing_n'] - e['n'] for p in e['pair']) > 0 for e in cts), 'A cross-tab entry has no missing-partner line')
                        # INTENT: replay a leak in the LAST entry -- its hidden cells re-shown at their
                        # true values (all >= threshold) leave the 2 records of b1 lacking cat_c pinned
                        # by the released totals -- and require the inspection to reject it.
                        # REASONING: a relationship-kind loop variable rebound by an earlier entry's
                        # missing-line loop would skip this entry and accept the leak.
                        # ASSUMES: neither column of the last pair pools a level (asserted).
                        tampered = copy.deepcopy(report)
                        last = tampered['relationships']['crosstabs'][-1]
                        cats = [sorted(l['value'] for l in by_name[p]['categorical']['levels']) for p in last['pair']]
                        require('__OTHER__' not in cats[0] + cats[1], 'Last multi-cross-tab pair pools a level')
                        last['cells'] = [sum(1 for x, y in zip(frame[last['pair'][0]], frame[last['pair'][1]]) if x == cats[0][k // last['cols']] and y == cats[1][k % last['cols']])
                                         for k in range(last['rows'] * last['cols'])]
                        last['cells_suppressed'] = 0
                        last.pop('collapsed', None)
                        rejected = None
                        try:
                            inspect_report(tampered, frame, tier, threshold)
                        except AssertionError as inspection_exc:
                            rejected = str(inspection_exc)
                        require(rejected is not None and rejected.startswith('Missing-partner'), f'Inspection accepted a missing-partner leak in the last cross-tab entry: {rejected}')
                    if name in ('named_small_group', 'named_group_at_k'):
                        named = report['relationships']['named']
                        want = [(False, 'small_complement_group')] * 2 if name == 'named_small_group' else [(True, None)] * 2
                        require([(e['available'], e.get('reason')) for e in named] == want, f'Complement-group gate gave {named}')
                    if name == 'bridge_collapse':
                        ct = report['relationships']['crosstabs'][0]
                        require(ct.get('collapsed') is True and ct['cells_suppressed'] == 16 and all(v is None for v in ct['cells']), 'Unrepairable bridge table not collapsed')
                    if name == 'boundary_k5':
                        require('923456.25' in jp.read_text(), 'Eligible constant positive control absent')
                        # Below-k blocks checked structurally; exact support metadata is allowed.
                    reports[(language, name)] = report
                results.append({'name': f'{language}/{name}', 'passed': True, 'detail': str(path)})
                print('PASS', language, name, flush=True)
            except Exception as exc:
                results.append({'name': f'{language}/{name}', 'passed': False, 'detail': str(exc)})
                print('FAIL', language, name, str(exc), flush=True)
    # INTENT: every embedded reason in every accepted report is in CPS-INTAKE's vocabulary:
    # PASS carries exactly `candidate_fields_checked`; NOT_APPLICABLE fully matches one of
    # the intake's fixed forms for that check (none exist for the disclosure sweep).
    # REASONING: with no declaration setting, every N/A is the profiler's own; a reason
    # outside the forms would fail intake and mean the template emits free text.
    for language in args.languages:
        n_reports, n_na, outside = 0, 0, []
        for (lang, name), report in sorted(reports.items()):
            if lang != language:
                continue
            n_reports += 1
            for c in report['validation']['checks']:
                if c['status'] == 'NOT_APPLICABLE':
                    n_na += 1
                    if not any(re.fullmatch(form, c['reason']) for form in intake_na_forms.get(c['name'], ())):
                        outside.append(f"{name}:{c['name']}")
                elif c['status'] != 'PASS' or c['reason'] != 'candidate_fields_checked':
                    outside.append(f"{name}:{c['name']}")
        results.append({'name': f'{language}/embedded_reasons_in_intake_vocabulary', 'passed': n_reports > 0 and n_na > 0 and not outside,
                        'detail': f'{n_reports} reports, {n_na} NOT_APPLICABLE reasons matched to CPS-INTAKE forms' if not outside else f'outside the vocabulary: {outside}'})
    if args.suite != 'generation':
        dense = next(f for f in fixtures if f[0] == 'dense_t3')
        for language in args.languages:
            ext = 'py' if language == 'python' else 'R'
            # INTENT: the outcome-vocabulary negative fixtures sit alongside the original faults;
            # each asserts the EXPECTED per-check outcome line, not merely a nonzero exit code.
            expected_outcome_line = {
                'missing_categorical_block': '[FAIL] no_subthreshold_cells_emitted:',
                'crosstab_cells_removed': '[FAIL] no_subthreshold_cells_emitted:',
                'empty_reason': '[NOT VERIFIED] column_shapes_and_support:',
                'bridge_restored': '[FAIL] no_subthreshold_cells_emitted:',
                'crosstab_extra_row': '[FAIL] relationship_support_and_shape:',
                'crosstab_duplicated': '[FAIL] relationship_support_and_shape:',
                'missing_partner_restored': '[FAIL] no_subthreshold_cells_emitted:',
                'named_group_released': '[FAIL] relationship_support_and_shape:',
            }
            # Position-only failure text for the missing-partner and complement-group faults, and the
            # check each one must leave passing (isolating the assertion that catches it).
            isolated = {
                'missing_partner_restored': ('missing-partner cell at row index 2 is recoverable from the released totals', '[PASS] relationship_support_and_shape'),
                'named_group_released': ('named entry (y ~ x): a complement group is below threshold', '[PASS] no_subthreshold_cells_emitted'),
            }
            # Exact failure text (pair and entry index only, no values) for the cross-tab placement faults.
            expected_message = {
                'crosstab_extra_row': 'crosstab entry 0 (group x sector): rows x cols differ from the released level counts of its pair columns',
                'crosstab_duplicated': 'crosstab entry 1: repeats the pair of an earlier entry',
            }
            for mutation in ('underk_value', 'invalid_rate', 'invalid_count', 'unordered_grid', 'invalid_matrix', 'missing_check', 'second_write', 'existing_json', 'existing_txt',
                             'missing_categorical_block', 'crosstab_cells_removed', 'empty_reason', 'bridge_restored', 'crosstab_extra_row', 'crosstab_duplicated',
                             'missing_partner_restored', 'named_group_released'):
                folder = work / f'{language}_fault_{mutation}'
                folder.mkdir()
                fixture = work / 'dense_t3.parquet'
                spec = dense[4]
                if mutation == 'underk_value':
                    fixture = work / 'underk_fault.parquet'
                    spec = []
                    if not fixture.exists():
                        pl.DataFrame({'sparse': [923456.25] * 4 + [None] * 16}).write_parquet(fixture)
                elif mutation == 'bridge_restored':
                    fixture = work / 'bridge_4x4.parquet'
                    spec = [['cat_a', 'cat_b']]
                elif mutation == 'missing_partner_restored':
                    fixture = work / 'missing_partner_repair.parquet'
                    spec = [['cat_a', 'cat_b']]
                elif mutation == 'named_group_released':
                    fixture = work / 'named_small_group.parquet'
                    spec = [['y', 'x'], ['x', 'y']]
                source = configure(source_by_language[language], language, fixture, folder, 3 if mutation != 'underk_value' else 2, 5, spec)
                if not mutation.startswith('existing'):
                    source = mutate(source, language, mutation)
                sentinel = None
                if mutation.startswith('existing'):
                    sentinel = folder / ('fixture_profile_report.json' if mutation == 'existing_json' else 'fixture_profile_report.txt')
                    sentinel.write_bytes(b'EXISTING_REPORT_BYTES\n')
                path = folder / f'profile.{ext}'
                path.write_text(source)
                result = run_captured(path, base, env)
                output = result.stdout + result.stderr
                try:
                    require(result.returncode != 0 and 'Wrote BOTH reports' not in output, 'Fault accepted or false success')
                    jp, tp = folder / 'fixture_profile_report.json', folder / 'fixture_profile_report.txt'
                    if sentinel:
                        require(sentinel.read_bytes() == b'EXISTING_REPORT_BYTES\n', 'Existing report changed')
                        require(not (tp if mutation == 'existing_json' else jp).exists(), 'Other target written after refusal')
                    else:
                        require('FAULT_INJECTION_APPLIED' in output, 'Failure before mutation reached')
                        if mutation == 'second_write':
                            require(jp.is_file() and tp.is_dir() and 'OUTPUT FAILED' in output, 'Second-write failure not diagnosed')
                        else:
                            require(not jp.exists() and not tp.exists() and 'VALIDATION FAILED' in output, 'Candidate failure leaked output or missed validation')
                            # Stdout must carry the count line and a verdict consistent with
                            # all_passed; a false candidate can never print PASSED.
                            require('Checks: ' in output, 'No Checks: count line on stdout')
                            require('PROFILE VALIDATION: FAILED' in output, 'No derived FAILED verdict on a rejected candidate')
                            require('PROFILE VALIDATION: PASSED' not in output, 'Rejected candidate reported a PASSED verdict')
                            if mutation in expected_outcome_line:
                                require(expected_outcome_line[mutation] in output, f'Missing expected outcome line: {expected_outcome_line[mutation]!r}')
                            if mutation in ('missing_categorical_block', 'crosstab_cells_removed', 'bridge_restored'):
                                require('[PASS] no_subthreshold_cells_emitted' not in output, 'Disclosure sweep passed on an incomplete scan')
                            if mutation == 'bridge_restored':
                                require('hidden cell at row index 1, column index 2 is recoverable from the released totals' in output, 'Bridge FAIL does not name the bridge position')
                                require('[PASS] relationship_support_and_shape' in output, 'Bridge fault should pass the lone-cell rule, isolating the bridge sweep')
                            if mutation in isolated:
                                require(isolated[mutation][0] in output, f'Missing expected failure text: {isolated[mutation][0]!r}')
                                require(isolated[mutation][1] in output, f'Fault not isolated: {isolated[mutation][1]!r} absent')
                            if mutation in expected_message:
                                require(expected_message[mutation] in output, f'Missing expected failure text: {expected_message[mutation]!r}')
                                require('[PASS] no_subthreshold_cells_emitted' in output, 'Placement fault should pass the disclosure sweep, isolating the placement assertion')
                    results.append({'name': f'{language}/fault_{mutation}', 'passed': True, 'detail': str(path)})
                    print('PASS', language, 'fault', mutation, flush=True)
                except Exception as exc:
                    results.append({'name': f'{language}/fault_{mutation}', 'passed': False, 'detail': str(exc)})
                    print('FAIL', language, 'fault', mutation, str(exc), flush=True)
            # INTENT: RELATIONSHIP_SPEC refusal -- a self-pair, an exact repeat, or a reversed repeat
            # of a non-numeric pair stops the profiler before any file is written; a reversed pair
            # of two numeric columns is two regressions (y ~ x, x ~ y) and is accepted.
            # REASONING: two differently suppressed tables of one pair can be combined to recover
            # cells, so the spec itself is refused rather than either table being trusted.
            # ASSUMES: dense_t3 has numeric x, y and categorical group, sector; messages name positions only.
            spec_cases = [
                ('spec_self_pair', [['group', 'group']], 'Invalid relationship spec: pair 1 names one column twice'),
                ('spec_repeated_pair', [['group', 'sector'], ['group', 'sector']], 'Invalid relationship spec: pair 2 repeats pair 1'),
                ('spec_reversed_categorical', [['group', 'sector'], ['sector', 'group']], 'Invalid relationship spec: pair 2 reverses pair 1; only two numeric columns may be listed in both orders'),
                ('spec_reversed_numeric', [['y', 'x'], ['x', 'y']], None),
            ]
            for case, spec, message in spec_cases:
                folder = work / f'{language}_{case}'
                folder.mkdir()
                path = folder / f'profile.{ext}'
                path.write_text(configure(source_by_language[language], language, work / 'dense_t3.parquet', folder, 3, 5, spec))
                result = run_captured(path, base, env)
                output = result.stdout + result.stderr
                jp, tp = folder / 'fixture_profile_report.json', folder / 'fixture_profile_report.txt'
                try:
                    if message is None:
                        require(result.returncode == 0 and jp.exists() and tp.exists() and 'PROFILE VALIDATION: PASSED' in result.stdout, 'Reversed numeric pair refused or failed')
                        named = json.loads(jp.read_text())['relationships']['named']
                        require([(e['outcome'], e['predictor'], e['available']) for e in named] == [('y', 'x', True), ('x', 'y', True)], 'Reversed numeric pair not released as two regressions')
                    else:
                        require(result.returncode != 0 and not jp.exists() and not tp.exists() and 'Wrote BOTH reports' not in output, 'Invalid spec accepted or a report written')
                        require(message in output, f'Missing refusal message: {message!r}')
                    results.append({'name': f'{language}/{case}', 'passed': True, 'detail': str(path)})
                    print('PASS', language, case, flush=True)
                except Exception as exc:
                    results.append({'name': f'{language}/{case}', 'passed': False, 'detail': str(exc)})
                    print('FAIL', language, case, str(exc), flush=True)
    if set(args.languages) == {'python', 'r'}:
        for name, *_ in fixtures:
            if ('python', name) not in reports or ('r', name) not in reports:
                continue
            try:
                compare_parity(reports[('python', name)], reports[('r', name)])
                results.append({'name': 'parity/' + name, 'passed': True, 'detail': 'Support, shape, values; Cramers V correction excluded'})
            except Exception as exc:
                results.append({'name': 'parity/' + name, 'passed': False, 'detail': str(exc)})
    if args.suite != 'profiles':
        for language in args.languages:
            for name in ('boundary_k5', 'boundary_k1', 'rare_controls', 'dense_numeric_t3', 'paired_four', 'constant5000'):
                if (language, name) not in reports:
                    results.append({'name': f'{language}/generate_{name}', 'passed': False, 'detail': 'Required profiler output unavailable'})
                    continue
                folder = work / f'{language}_generation_{name}'
                folder.mkdir()
                outputs = []
                for repeat in (1, 2):
                    ext = 'py' if language == 'python' else 'R'
                    path = folder / f'generate_{repeat}.{ext}'
                    output = folder / f'synthetic_{repeat}.parquet'
                    report_path = work / f'{language}_{name}/fixture_profile_report.json'
                    path.write_text(generation_source(base, language, report_path, output, tier3=reports[(language, name)]['settings']['tier'] == 3))
                    result = run_captured(path, base, env)
                    outputs.append(output)
                    passed = result.returncode == 0 and output.exists() and 'GENERATION_VERIFIED' in result.stdout
                    results.append({'name': f'{language}/generate_{name}_{repeat}', 'passed': passed, 'detail': str(path)})
                passed = all(p.exists() for p in outputs) and pl.read_parquet(outputs[0]).equals(pl.read_parquet(outputs[1]))
                results.append({'name': f'{language}/seed_{name}', 'passed': passed, 'detail': 'Repeated same seed gives identical frame'})
        # INTENT: verify actual example version guards reject legacy inputs without altering them.
        # REASONING: an old embedded PASS must never be silently relabeled as new-policy compliance.
        # ASSUMES: this fabricated legacy-shaped control exercises the version gate, not all 1.0 semantics.
        for language in args.languages:
            if (language, 'boundary_k5') not in reports:
                continue
            folder = work / f'{language}_legacy_generation'
            folder.mkdir()
            legacy = copy.deepcopy(reports[(language, 'boundary_k5')])
            legacy['report_version'] = '1.0'
            legacy['generator']['template_version'] = '1.0'
            report_path = folder / 'legacy_original.json'
            report_path.write_text(json.dumps(legacy, indent=2))
            original_bytes = report_path.read_bytes()
            output = folder / 'must_not_exist.parquet'
            ext = 'py' if language == 'python' else 'R'
            path = folder / f'generate_legacy.{ext}'
            path.write_text(generation_source(base, language, report_path, output))
            result = run_captured(path, base, env)
            passed = result.returncode != 0 and not output.exists() and report_path.read_bytes() == original_bytes and 'report_version' in (result.stdout + result.stderr)
            results.append({'name': f'{language}/legacy_generation_rejected', 'passed': passed, 'detail': str(path)})
            frame = next(f[1] for f in fixtures if f[0] == 'boundary_k5')
            try:
                inspect_report(legacy, frame, 2, 5)
                rejected = False
            except AssertionError as exc:
                rejected = str(exc) == 'Wrong report version'
            results.append({'name': f'{language}/legacy_intake_rejected', 'passed': rejected, 'detail': 'Independent report-version checker in this tool rejects 1.0; no standalone DS-3 implementation is exercised'})
    # --- Summary ---
    # INTENT: derive completion from recorded outcomes, preserve failures and inventory.
    for r in results:
        print(('PASS' if r['passed'] else 'FAIL'), r['name'], r['detail'])
    passed = sum(r['passed'] for r in results)
    failed = len(results) - passed
    print(f'REGRESSION_SUMMARY total={len(results)} passed={passed} failed={failed}', flush=True)
    (work / 'results.json').write_text(json.dumps({'passed': passed, 'failed': failed, 'results': results}, indent=2) + '\n')
    (work / 'inventory.json').write_text(json.dumps([str(p) for p in sorted(work.rglob('*')) if p.is_file()], indent=2) + '\n')
    print('RESULT_LOG', work / 'results.json')
    return int(failed > 0)


if __name__ == '__main__':
    raise SystemExit(main())
