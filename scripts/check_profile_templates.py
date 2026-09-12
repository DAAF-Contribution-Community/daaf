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
    checks = report["validation"]["checks"]
    require([c["name"] for c in checks] == CHECKS, "Missing/duplicate required checks")
    require(report["validation"]["all_passed"] is True, "Embedded validation failed")
    cols = report["columns"]
    applicable = [True, any("percentiles" in c.get("numeric", {}) for c in cols), any("categorical" in c for c in cols), tier >= 2,
                  any(c.get("categorical", {}).get("levels", []) for c in cols) or any(any(v is not None for v in b.get("cells", [])) for b in rel.get("crosstabs", [])),
                  any(rel.get(k, {}).get("available", False) for k in ("pearson", "spearman")), tier == 3]
    for c, expected in zip(checks, applicable):
        require(c["applicable"] is bool(expected) and c["reason"] and c["status"] == ("PASS" if expected else "NOT_APPLICABLE"), f"Dishonest applicability: {c}")


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
    }
    r = {
        "underk_value": 'report$columns[[1]]$numeric$mean <- 923456.25',
        "invalid_rate": 'report$columns[[1]]$missing_rate <- 1.5',
        "invalid_count": 'report$columns[[4]]$categorical$levels[[1]]$count <- 99999',
        "unordered_grid": 'report$columns[[1]]$numeric$percentiles$p25 <- 99999',
        "invalid_matrix": 'report$relationships$pearson$matrix[1, 2] <- 2',
        "missing_check": 'checks <- checks[-length(checks)]',
        "second_write": 'dir.create(txt_path)',
    }
    statement = (py if language == "python" else r)[mutation]
    marker = '# --- Validate ---------------------------------------------------------------'
    if mutation == "missing_check":
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
        # INTENT: compare each observation against the desired contract, not against the allegation.
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
                    if name == 'boundary_k5':
                        require('923456.25' in jp.read_text(), 'Eligible constant positive control absent')
                        # Below-k blocks checked structurally; exact support metadata is allowed.
                    reports[(language, name)] = report
                results.append({'name': f'{language}/{name}', 'passed': True, 'detail': str(path)})
                print('PASS', language, name, flush=True)
            except Exception as exc:
                results.append({'name': f'{language}/{name}', 'passed': False, 'detail': str(exc)})
                print('FAIL', language, name, str(exc), flush=True)
    if args.suite != 'generation':
        dense = next(f for f in fixtures if f[0] == 'dense_t3')
        for language in args.languages:
            ext = 'py' if language == 'python' else 'R'
            for mutation in ('underk_value', 'invalid_rate', 'invalid_count', 'unordered_grid', 'invalid_matrix', 'missing_check', 'second_write', 'existing_json', 'existing_txt'):
                folder = work / f'{language}_fault_{mutation}'
                folder.mkdir()
                fixture = work / 'dense_t3.parquet'
                if mutation == 'underk_value':
                    fixture = work / 'underk_fault.parquet'
                    if not fixture.exists():
                        pl.DataFrame({'sparse': [923456.25] * 4 + [None] * 16}).write_parquet(fixture)
                source = configure(source_by_language[language], language, fixture, folder, 3 if mutation != 'underk_value' else 2, 5, dense[4] if mutation != 'underk_value' else [])
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
                    results.append({'name': f'{language}/fault_{mutation}', 'passed': True, 'detail': str(path)})
                    print('PASS', language, 'fault', mutation, flush=True)
                except Exception as exc:
                    results.append({'name': f'{language}/fault_{mutation}', 'passed': False, 'detail': str(exc)})
                    print('FAIL', language, 'fault', mutation, str(exc), flush=True)
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
            results.append({'name': f'{language}/legacy_intake_rejected', 'passed': rejected, 'detail': 'Independent regression contract checker rejects 1.0; no standalone DS-3 implementation is exercised'})
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
