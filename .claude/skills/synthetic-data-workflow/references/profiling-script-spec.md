# Profiling Script Specification

The contract for the disclosure-controlled profiling script the user runs locally (DS-1 preparation, DS-2 user run) and the canonical JSON schema of the report it returns (DS-3 intake). The measurement inventory is derived from the Data Onboarding profiling measurement inventory (see `WORKFLOW_PHASE_DO_PROFILING.md` § Part Details — scripts 01-09), filtered per disclosure tier so that only tier-permitted, suppression-applied statistics ever leave the user's machine.

## Contents

- [Design constraints for the outbound script](#design-constraints)
- [Config block (what the user edits)](#config-block)
- [Measurement inventory by tier](#measurement-inventory)
- [Canonical JSON report schema](#json-schema)
- [The plain-text review summary](#txt-summary)
- [Embedded validation checks](#embedded-validation)
- [Derivation from Data Onboarding scripts 01-09](#derivation)

## Design constraints for the outbound script {#design-constraints}

This script runs where DAAF cannot reach and touches the real sensitive data. It must be trustworthy on inspection by a non-programmer researcher, and it must be incapable of emitting anything the chosen tier forbids.

- **Zero DAAF dependency.** No sourcing of DAAF files, no DAAF paths, no network calls. A single self-contained file the user can read top-to-bottom and run with a standard interpreter.
- **Flat, sequential, auditable.** DAAF code style (no function definitions; `# --- Config ---`, `# --- Load ---`, `# --- Profile ---`, `# --- Validate ---`, `# --- Summary ---` section separators; inline `stopifnot()`/`assert` validation). Every disclosure-relevant computation carries IAT comments (`# INTENT:` / `# REASONING:` / `# ASSUMES:`) so a reviewer can see *why* each statistic is safe at the chosen tier. The one sanctioned deviation from "no config at top": a clearly marked `# --- Config (EDIT THESE) ---` block, preferred over argparse/commandArgs so a non-programmer can configure it by editing obvious variables.
- **Suppression on by default.** At T2+, the script cannot be configured to emit raw min/max, example values, sub-threshold cells, or identifier values. Suppression is structural, not a flag the user might forget.
- **Dual output.** A machine-readable JSON report (`{dataset}_profile_report.json`) and a human-readable plain-text summary (`{dataset}_profile_report.txt`). The user reviews the `.txt` before sharing either file.
- **Loud final review block.** The script ends by printing a prominent block instructing the user to REVIEW THE `.txt` BEFORE SHARING and enumerating what to check.
- **Base-first dependencies.** R: base R for CSV; optional `arrow` (parquet) and `haven` (Stata/SPSS/SAS) behind graceful "install if needed" guards. Python: stdlib + pandas (ubiquitous); optional `pyarrow` for parquet, documented. Hand-rolled JSON emission is acceptable in base R to avoid a jsonlite dependency; Python uses stdlib `json`.

## Config block (what the user edits) {#config-block}

The `# --- Config (EDIT THESE) ---` block exposes exactly these knobs:

| Variable | Meaning | Default |
|----------|---------|---------|
| `INPUT_PATH` | Path to the user's data file (CSV / parquet / Stata) | — (user sets) |
| `DATASET_NAME` | Short slug used in output filenames and the report | — (user sets) |
| `OUTPUT_DIR` | Where to write the JSON + txt (a local, non-shared folder) | current dir |
| `TIER` | Disclosure tier: 1, 2, or 3 (T4 uses the synthesis template, not this one) | 2 |
| `SUPPRESSION_THRESHOLD` | Small-cell suppression threshold | 5 |
| `RELATIONSHIP_SPEC` | (T3 only, optional) list of `[var1, var2]` pairs. Each pair is auto-routed: both columns full-summary numeric → a named `[outcome_y, predictor_x]` relationship (OLS + correlations); otherwise → a suppressed categorical cross-tab | empty |
| `MAX_CATEGORICAL_LEVELS` | Columns with more distinct values than this are treated as high-cardinality (identifier-like or free-text), not enumerated | 50 |

`TIER` and `SUPPRESSION_THRESHOLD` are recorded verbatim in the report so downstream validation applies the same rules.

## Measurement inventory by tier {#measurement-inventory}

Cumulative — each tier includes all rows marked for lower tiers.

| Measurement | T1 | T2 | T3 | Suppression applied |
|-------------|----|----|----|---------------------|
| Column names | ✓ | ✓ | ✓ | — |
| Column dtypes | ✓ | ✓ | ✓ | — |
| Row count (grand total) | ✓ | ✓ | ✓ | — |
| Per-column null/missingness rate | | ✓ | ✓ | rate only, never row indices |
| Distinct-value count (cardinality) | | ✓ | ✓ | count only |
| Uniqueness ratio + identifier flag | | ✓ | ✓ | flag only; triggers structure-only |
| Categorical levels + counts | | ✓ | ✓ | small cells suppressed; rare→`__OTHER__` |
| Numeric percentiles p1..p99 | | ✓ | ✓ | percentiles replace min/max |
| Numeric mean + SD | | ✓ | ✓ | — |
| String length stats (min/mean/max length) | | ✓ | ✓ | length, never value |
| String pattern flags (email/phone/date/id/free-text) | | ✓ | ✓ | boolean flags, never example |
| Pearson + Spearman correlation matrices | | | ✓ | numeric columns only |
| Cramér's V (categorical pairs) | | | ✓ | — |
| Named numeric~numeric summary (Pearson/Spearman + OLS slope/intercept/R²) | | | ✓* | aggregate coefficients; n<max(threshold,10) or zero-variance predictor omitted |
| Two-way cross-tabs (categorical pairs) | | | ✓* | primary + iterative complementary suppression; suppressed cells emitted as `null` |

`*` = only when `RELATIONSHIP_SPEC` is provided.

**T1 columns carry only `name` and `dtype`** — no `role`, `missing_rate`, `n_distinct`, `uniqueness_ratio`, or `is_identifier`. All of those are per-column statistics T1 forbids; `role` in particular is withheld because it is *derived* from uniqueness + identifier detection, so emitting it would leak a T1-forbidden distributional fact. T1 generation needs only name + dtype (see `generation-patterns-r.md` § T1 skeleton).

**Numeric columns degrade defensively** at T2+ to avoid small-n and constant-column leakage:

| Condition | Emitted numeric block | Why |
|-----------|-----------------------|-----|
| All-missing (non-null n = 0) | `{"n": 0, "all_missing": true}` | No statistics are computable; also avoids a `quantile([])` crash |
| Near-constant (1 distinct non-null value, or SD = 0) | `{"near_constant": true, "n": <n>}` | Mean/percentiles would disclose the exact single value |
| Small-n (non-null n < max(threshold, 10)) | `{"small_n": true, "n": <n>, "percentiles": {p25, p50, p75}}` | p1/p99 approximate the true min/max at small n (outlier disclosure); mean/SD withheld |
| Full (otherwise) | `{"mean", "sd", "percentiles": {p1..p99}}` | The ordinary case |

Only **full-summary** numeric columns enter the correlation matrix and are eligible as named-relationship variables — degraded columns carry no usable variance/percentile grid.

## Canonical JSON report schema {#json-schema}

Versioned via `report_version` so intake code can evolve. Current version: `"1.0"`. Structure:

```json
{
  "report_version": "1.0",
  "dataset_name": "clients_2025",
  "generated_utc": "2026-07-15T15:00:00Z",
  "generator": {
    "language": "R",
    "template": "profile_data_template.R",
    "template_version": "1.0"
  },
  "settings": {
    "tier": 2,
    "suppression_threshold": 5,
    "max_categorical_levels": 50,
    "relationship_spec": null
  },
  "_note": "The block below shows a T3 example for the relationships schema; at T1/T2 the relationships key is null or omitted, and relationship_spec is a list of pairs (not null) when set — e.g. [[\"score\", \"age\"], [\"region\", \"segment\"]].",
  "dataset": {
    "row_count": 4820,
    "column_count": 11
  },
  "columns": [
    {
      "name": "age",
      "dtype": "integer",
      "role": "numeric",
      "missing_rate": 0.012,
      "n_distinct": 71,
      "uniqueness_ratio": 0.0147,
      "is_identifier": false,
      "numeric": {
        "mean": 41.3, "sd": 12.8,
        "percentiles": {
          "p1": 19, "p5": 22, "p10": 25, "p25": 31, "p50": 40,
          "p75": 51, "p90": 59, "p95": 64, "p99": 71
        }
      }
    },
    {
      "name": "region",
      "dtype": "string",
      "role": "categorical",
      "missing_rate": 0.0,
      "n_distinct": 6,
      "uniqueness_ratio": 0.0012,
      "is_identifier": false,
      "categorical": {
        "n_levels_binned": 2,
        "levels": [
          {"value": "North", "count": 1810},
          {"value": "South", "count": 1502},
          {"value": "East", "count": 980},
          {"value": "West", "count": 521},
          {"value": "__OTHER__", "count": 7}
        ]
      }
    },
    {
      "name": "client_email",
      "dtype": "string",
      "role": "identifier",
      "missing_rate": 0.0,
      "n_distinct": 4820,
      "uniqueness_ratio": 1.0,
      "is_identifier": true,
      "string_structure": {
        "length_min": 11, "length_mean": 22.4, "length_max": 41,
        "pattern_flags": {"email": true, "phone": false, "date": false,
                          "id": false, "free_text": false}
      }
    }
  ],
  "relationships": {
    "pearson": {"columns": ["age", "income"], "matrix": [[1.0, 0.34], [0.34, 1.0]]},
    "spearman": {"columns": ["age", "income"], "matrix": [[1.0, 0.31], [0.31, 1.0]]},
    "cramers_v": [{"pair": ["region", "segment"], "v": 0.22}],
    "named": [
      {"outcome": "score", "predictor": "age",
       "pearson": 0.41, "spearman": 0.39,
       "ols": {"intercept": 52.3, "slope": 0.34, "r_squared": 0.17}, "n": 4780}
    ],
    "crosstabs": [
      {"pair": ["region", "segment"], "rows": 3, "cols": 3,
       "cells": [null, null, 500, null, null, 300, 250, 180, 90],
       "cells_suppressed": 4}
    ]
  },
  "validation": {
    "checks": [
      {"name": "percentiles_monotone", "status": "PASS"},
      {"name": "category_counts_le_rowcount", "status": "PASS"},
      {"name": "missing_rate_in_unit_interval", "status": "PASS"},
      {"name": "no_subthreshold_cells_emitted", "status": "PASS"},
      {"name": "correlation_matrix_symmetric", "status": "PASS"}
    ],
    "all_passed": true
  }
}
```

Schema notes:
- **T1 columns** carry only `{"name", "dtype"}`. `role` and every statistic field appear at T2+ only.
- `role` is one of `numeric`, `categorical`, `identifier`, `string` (non-identifier free/other text). Exactly one of the `numeric` / `categorical` / `string_structure` blocks is present per column, matching `role`.
- The `numeric` block has four shapes (see the "Numeric columns degrade defensively" table above): full (`mean` + `sd` + `percentiles` p1..p99), `small_n` (quartiles only), `near_constant` (value withheld), and `all_missing`.
- `settings.relationship_spec` is a **list of `[var1, var2]` pairs** when `RELATIONSHIP_SPEC` is set, else `null` — not an integer count.
- The `relationships` block is present only at T3 (at T1/T2 it is `null` or omitted). `named` and `crosstabs` are populated only when `RELATIONSHIP_SPEC` is set.
- **`named`** entries are numeric~numeric relationships: `{"outcome", "predictor", "pearson", "spearman", "ols": {"intercept", "slope", "r_squared"}, "n"}`. A `RELATIONSHIP_SPEC` pair is routed to `named` when both columns are full-summary numerics (pair = `[outcome_y, predictor_x]`, fitting `y ~ x`); otherwise it is routed to `crosstabs`.
- **`crosstabs`** entries are `{"pair", "rows", "cols", "cells", "cells_suppressed"}`. `cells` is a **row-major flat array of length `rows`×`cols`**; a suppressed cell is JSON **`null`** (never `0` — a suppressed cell must be distinguishable from a true zero). `cells_suppressed` is the count of null cells. Suppression is primary (small nonzero cells) plus iterative complementary suppression; if complementary suppression cannot converge within 10 iterations the whole table is suppressed (all cells `null`) and the entry additionally carries `"collapsed": true`.
- Correlation matrices are stored with an explicit `columns` order so the matrix indices are interpretable.
- `__OTHER__` is the reserved binned-category label; intake and generation code treat it as an aggregate, not a real level. Its count is always ≥ the suppression threshold: a sub-threshold `__OTHER__` residual is folded further (the smallest retained levels are rolled in) until it clears the threshold, or the whole column is suppressed if it cannot.
- Identifier columns never carry a `numeric` or `categorical` values block — only `string_structure` (or, for numeric-encoded IDs, a minimal structure block with length/uniqueness and no percentiles).

## The plain-text review summary {#txt-summary}

`{dataset}_profile_report.txt` is the human disclosure-review artifact — the thing the user actually reads before sharing. It restates the JSON in prose and tables a non-programmer can scan, and it foregrounds anything disclosure-relevant:

- Header: dataset name, tier, suppression threshold, row/column counts, generation timestamp.
- A per-column section: name, type, role, missingness, and the tier-permitted statistics — formatted, not raw JSON.
- An explicit **"What was suppressed"** section: how many categorical levels were binned, which columns were flagged as identifiers and given structure-only treatment, confirmation that no min/max or example values appear.
- The embedded validation results (all checks and pass/fail).
- A closing **REVIEW BEFORE SHARING** block enumerating: confirm no column *name* itself is disclosive; confirm the identifier flags caught every real identifier; confirm the tier matches what you intend to share; the JSON and this txt are the only files to share — nothing else.

## Embedded validation checks {#embedded-validation}

The script validates its own output before writing, and embeds the results in both outputs (`validation` block in JSON; a section in txt). These are the same internal-consistency checks the DS-3 intake re-verifies (`validation-checks.md` QA(b)) — embedding them lets the user see pass/fail locally and lets intake confirm they were run:

- `percentiles_monotone` — for every numeric column, p1 ≤ p5 ≤ ... ≤ p99.
- `category_counts_le_rowcount` — every categorical level count (and their sum, including `__OTHER__`) ≤ row count.
- `missing_rate_in_unit_interval` — every missingness rate in [0,1].
- `no_subthreshold_cells_emitted` — no emitted categorical/cross-tab cell has count in (0, threshold).
- `correlation_matrix_symmetric` — (T3) matrices square, symmetric, unit diagonal.

`all_passed` is the AND of every check. If it is false, the txt tells the user not to share and to report the failure back to DAAF.

## Derivation from Data Onboarding scripts 01-09 {#derivation}

The measurement inventory is the mechanical (non-LLM) subset of Data Onboarding profiling, filtered for disclosure (derived from the Data Onboarding profiling measurement inventory — see `WORKFLOW_PHASE_DO_PROFILING.md` § Part Details):

| Onboarding script | Contributes | Disclosure filter applied |
|-------------------|-------------|---------------------------|
| 02 structural-profile | row/col counts, dtypes, column order | kept as-is (T1) |
| 03 column-profile | nulls, uniques, uniqueness ratio, numeric summaries, string lengths, pattern detection, identifier flags | min/max dropped → percentiles; top-N value counts → suppressed levels; identifier flag → structure-only |
| 04 distribution-analysis | percentiles, skew/kurtosis | percentiles kept; raw extremes dropped |
| 08 correlation-dependency | Pearson/Spearman, Cramér's V | kept at T3 only |
| 09 quality-anomaly | missingness summary | rate kept; row-level anomaly listings dropped |

Scripts 10-11 (semantic interpretation, doc reconciliation) are **interpretive** and are performed *inside* DAAF at DS-4 against the returned report — not by the outbound script. The outbound script emits only mechanical measurements; interpretation happens on this side of the boundary.
