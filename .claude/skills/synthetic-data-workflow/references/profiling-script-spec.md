# Profiling Script Specification

The contract for the disclosure-controlled script the user runs locally (DS-1 preparation, DS-2 user run) and its returned report (DS-3 intake). The measurement inventory derives from `WORKFLOW_PHASE_DO_PROFILING.md` scripts 01–09, filtered by tier and support. **Current report contract: `2.0`.** This is a minimum-support/categorical-cell safeguard, not a guarantee against reconstruction or auxiliary-information attacks. Human release review remains required.

## Contents

- [Design constraints for the outbound script](#design-constraints-for-the-outbound-script)
- [Config block (what the user edits)](#config-block-what-the-user-edits)
- [Measurement inventory by tier](#measurement-inventory-by-tier)
- [Canonical JSON report schema](#canonical-json-report-schema)
- [The plain-text review summary](#the-plain-text-review-summary)
- [Embedded validation checks](#embedded-validation-checks)
- [Derivation from Data Onboarding scripts 01-09](#derivation-from-data-onboarding-scripts-01-09)

## Design constraints for the outbound script

- **Zero DAAF dependency:** one local file, no DAAF paths/imports, no network calls, no raw-row outputs.
- **Flat, sequential, auditable:** inline checks and IAT comments; no helper functions or serializer package requirement. The editable Config block is for non-programmers. Python must run **without `-O`, `-OO`, or `PYTHONOPTIMIZE`**: an explicit non-assert startup guard refuses optimized mode before loading data or writing reports, because optimization removes the assertion-based release checks.
- **Numeric precision boundary:** these standalone T2/T3 assets refuse finite numeric input with absolute magnitude **at least `2^53` (9,007,199,254,740,992)** before double conversion, with a local precision/range diagnostic and no reports. Python tests native integers exactly; R tests native `integer64` through exact decimal text before coercion. The inclusive boundary also refuses already-double values at the point where neighboring integers may have been rounded by the reader. This is a computational limitation, not suppression for large sample size or constant values. It applies to numeric-encoded IDs too; T1 stays schema-only. Use a separately reviewed precision-safe local profiling path, not a lossy cast or an altered-value report. No new package is required.
- **Gate before calculating value summaries:** count actual usable observations first. Support means contributing **records**, not distinct values, positive outcomes, or the missing numerator. `settings.support_unit: "record"` records the implementation's unit. The researcher must establish whether one record represents one intended contributor; repeated visits are not verified distinct people. There is no identity-resolution system here.
- **Preserve ordinary metadata:** missingness uses all rows as its denominator; cardinality/uniqueness remain metadata. A missingness rate of .002 over 1,000 records and a numeric binary mean of .003 over 1,000 usable records are permitted under this policy. Do not suppress entire columns for rare missingness/positive counts. Categorical cells retain their separate threshold rule.
- **Suppression is structural:** below-support value summaries cannot fall back to quartiles, means, length summaries, or categorical encodings. Eligible constants are not automatically suppressed.
- **Typed release candidate:** both assets build rounded/suppressed typed objects, validate those objects, then serialize them. R uses explicit schema-specific base-R emission, not a general serializer or jsonlite dependency. Python uses stdlib JSON with nonfinite output forbidden.
- **Dual output and failure handling:** JSON and TXT describe the same candidate; the TXT embeds the exact candidate after plain-language review instructions. No reports are written on validation failure. Refuse existing targets before processing and use exclusive creation when writing. Announce success only after both writes finish. An I/O failure may leave a partial new pair: explicitly do not share it; retry in a fresh output folder. Existing reports are not overwritten.
- **Base-first dependencies:** Python uses NumPy/pandas and an optional parquet reader (pyarrow). R uses base CSV input, optional arrow for parquet and haven for Stata/SPSS/SAS. Dependency-needed messages are plain text, not installation commands. These templates run outside DAAF; in-container tests use configured copies and the capture protocol.

## Config block (what the user edits)

| Variable | Meaning | Default |
|----------|---------|---------|
| `INPUT_PATH` | Local input: Python CSV/parquet; R CSV/parquet/Stata/SPSS/SAS | `data.csv` |
| `DATASET_NAME` | Filename slug: letters, digits, underscore, hyphen | `dataset` |
| `OUTPUT_DIR` | Existing local, non-shared folder; targets must not exist | `.` |
| `TIER` | 1, 2, or 3; T4 uses a separate template | 2 |
| `SUPPRESSION_THRESHOLD` | Positive integer minimum usable support and categorical cell threshold | 5 |
| `RELATIONSHIP_SPEC` | Optional pairs: numeric roles route to named `outcome ~ predictor`; categorical roles to cross-tabs; other combinations unavailable | empty |
| `MAX_CATEGORICAL_LEVELS` | Larger string cardinalities are not enumerated | 50 |

Settings also record derived `full_summary_cutoff: max(threshold,10)` and fixed `support_unit: "record"`. No additional editable knobs are required.

## Measurement inventory by tier

| Measurement | T1 | T2 | T3 | Release rule |
|-------------|----|----|----|--------------|
| Column names/dtypes; total row/column counts | Yes | Yes | Yes | Review schema names for sensitivity |
| Missingness, nonmissing count, cardinality, uniqueness, identifier flag/role | No | Yes | Yes | Ordinary metadata; missingness denominator = all records |
| Categorical levels/counts | No | Yes | Yes | Cell suppression, `__OTHER__` pooling and complementary roll-in |
| Numeric values/moments/percentiles | No | Yes | Yes | Shapes below, based on finite usable observations |
| String/identifier lengths and pattern flags | No | Yes | Yes | Nonmissing support at least threshold; otherwise explicit withheld block |
| Pearson/Spearman matrices | No | No | Yes | Full nonconstant numeric marginals; every pair adequately supported and numerically defined |
| Cramér's V | No | No | Yes | Paired nonmissing support at least threshold; nondegenerate table |
| Named numeric relationships | No | No | Optional | Full nonconstant marginals, finite complete cases at least cutoff, nonzero pair variances |
| Categorical cross-tabs | No | No | Optional | Complete-case support at least threshold, plus existing cell suppression |

**T1 columns are exactly `{name,dtype}`.** No role, support counts, rates, cardinalities, or value summaries are included per column. Empty input still fails before profiling.

## Canonical JSON report schema

Top-level fields remain `report_version`, `dataset_name`, `generated_utc`, `generator`, `settings`, `dataset`, `columns`, `validation`, and (T3 only) `relationships`. Both `report_version` and `generator.template_version` are `"2.0"`. `dataset` carries `row_count` and `column_count`. `settings.relationship_spec` is a list of two-name arrays or `null`.

**Legacy `1.0`:** retain the original file and version as historical evidence. Its old PASS does not establish compliance with this policy. Request a corrected local `2.0` rerun for new-policy acceptance; do not relabel or patch a legacy report into compliance. Unknown versions are rejected pending schema review.

### Column metadata

At T2+, every column has `name`, `dtype` (`integer`, `double`, `string`), `role` (`numeric`, `categorical`, `identifier`, `string`), `missing_rate`, **`nonmissing_n`**, `n_distinct`, `uniqueness_ratio`, `is_identifier`, and exactly one role-specific block. `missing_rate` must agree with `(row_count - nonmissing_n)/row_count` within six-decimal rounding tolerance. Numeric support can be below `nonmissing_n` because infinities are not usable numerical observations. NaN/null are missing. Identifiers carry only `string_structure`, never a numeric/categorical values block.

### Numeric shapes (branch in this order)

Let `k = suppression_threshold`, `f = max(k,10)`, and `n` be **finite usable** observations. All numeric shapes include `n`.

| Condition | Exact numeric keys / example | Consumer action |
|-----------|-----------------------------|-----------------|
| No nonmissing values | `{"n":0,"all_missing":true}` | Typed all-null column; distribution fidelity N/A |
| No finite values, but nonmissing values exist | `{"n":0,"withheld":true,"reason":"no_finite_values"}` | Typed placeholder; finite distribution unobserved |
| `0 < n < k` | `{"n":4,"withheld":true,"reason":"insufficient_support"}` | No value fields; typed placeholder, distribution unobserved |
| `n >= k`, exactly constant | `{"n":5,"constant":true,"value":7,"mean":7,"sd":0}` | Generate supported shared value faithfully; no copula |
| `k <= n < f`, nonconstant | `{"n":6,"small_n":true,"percentiles":{"p25":2,"p50":3,"p75":4}}` | Quartile interpolation only; mean/SD/tails unavailable |
| `n >= f`, nonconstant | `{n,mean,sd,percentiles:{p1,p5,p10,p25,p50,p75,p90,p95,p99}}` | Full marginal interpolation/moment targets |

The constant shape deliberately permits its supported value and mean below the full-summary cutoff; sample SD is `null` at `n=1` (possible only with `k=1`), otherwise zero. Constants have no percentile block. Four identical observations are withheld at default k; five or 5,000 identical observations are eligible constants. Equality is tested on usable values, not rounded SD. A nonconstant full summary may have SD rounded to zero: do not infer an exact constant from that alone. Numeric outputs are rounded to six decimal places.

### Categorical and string structure

- `categorical` is exactly `{n,n_levels_binned,levels:[{value,count},...]}`. Here `n = nonmissing_n`. Visible counts are positive integers at least k. If `n >= k`, their sum equals n; if `n < k`, `levels` is empty. `__OTHER__` is reserved for pooled levels. If the input contains that literal label, its records join the pool (even if its own count is at least k), and the source level is included in `n_levels_binned`; it is never emitted as a second literal level. For A×20, literal `__OTHER__`×10, and two rare levels×3, release A×20 and one `__OTHER__`×16 with `n_levels_binned:3`. Emitted labels must be unique. A sub-threshold residual rolls in the smallest retained levels until eligible, or all levels are suppressed. Do not invent the hidden labels.
- `string_structure` with `n >= k` is `{n,length_min,length_mean,length_max,pattern_flags:{email,phone,date,id,free_text}}`; length mean is rounded to three decimals, flags are booleans. With `n < k` it is exactly `{n,withheld:true,reason}` with reason `all_missing` at zero or `insufficient_support` otherwise. Lengths/flags are absent, not zeros. Metadata identifier heuristics do not certify that every identifier was found.

### Relationships

T3 always includes `pearson`, `spearman`, `cramers_v`, `named`, `crosstabs`. The last three are arrays (possibly empty). Numeric pairs are never rerouted to cross-tabs merely because their summaries were withheld. Mixed-role/identifier/string requested pairs are explicitly unavailable cross-tab entries rather than value-enumeration fallbacks.

- **Correlation available block:** `{available:true,columns:[...],pair_n:[[...]],matrix:[[...]]}`. `columns` lists only full-summary nonconstant marginals in report order. `pair_n` is a square symmetric matrix of finite paired support, with marginal finite n on its diagonal. Every pair needs at least `max(k,2)` and nonzero variances on that pair's complete cases. The released matrix must be square, finite, symmetric, bounded in [-1,1], and unit-diagonal.
- **Correlation unavailable block:** `{available:false,columns:[...],pair_n:[[...]],matrix:[],reason}`. `pair_n` retains the candidate column order/support (empty if no eligible columns). Reasons: `fewer_than_two_eligible_columns`, `insufficient_pair_support`, `zero_pair_variance`, `nonfinite_correlation`. One ineligible pair makes the entire matrix unavailable; this intentionally avoids nullable-cell imputation complexity or fabricated zero correlations. Other marginal/relationship blocks remain usable. No raw pair values or row membership is emitted.
- **Cramér's V available:** `{pair:[a,b],n,available:true,v}`. n counts nonmissing pairs. R removes zero margins left by unused factor levels after complete-case filtering, before checking dimensions/calculating the statistic; its requested cross-tab path removes the same zero margins. No contributing records are removed. Below k: unavailable with `insufficient_support`; a one-level table: `degenerate_table`. No v is emitted in either case. Existing method convention is retained: Python uses uncorrected Pearson chi-square; R's `chisq.test` retains its default continuity correction for 2×2 tables. This pre-existing numerical difference is not a support-policy difference.
- **Named available:** `{outcome,predictor,n,available:true,pearson,spearman,ols:{intercept,slope,r_squared}}`. Require full nonconstant marginals, `n >= f`, finite complete pairs, and nonzero pair variances for both variables. Unavailable entry contains only `{outcome,predictor,n,available:false,reason}`; reasons are `insufficient_support`, `ineligible_marginal`, `zero_pair_variance`.
- **Cross-tab available:** `{pair,n,available:true,rows,cols,cells,cells_suppressed}`; optional `collapsed:true`. `cells` is row-major, length rows×cols. A hidden cell is **null**, never zero. Keep primary suppression of positive cells below k and iterative complementary suppression; if a lone hidden cell remains after ten iterations, hide the whole table and mark `collapsed:true`. Unavailable entries contain only `{pair,n,available:false,reason}`, with `ineligible_roles` or `insufficient_support`. No dimensions/cells accompany unavailable entries. Visible totals may be below n with suppression; they must equal n with no hidden cells.

No new group-mean family is introduced. Any future group summary would need its own actual group support gate. These controls do not implement a general privacy-composition solver.

## The plain-text review summary

`{dataset}_profile_report.txt` contains plain-language guidance followed by the **exact release candidate** as readable JSON. This intentionally replaces an independently calculated prose summary: human and machine copies cannot silently disagree about withheld values, category labels, or relationship availability. Review the entire candidate, including names, actual surviving category labels, identifiers, relationships, tier/threshold, and every check. Share only authorized reports; neither automated PASS nor a supported constant is a universal assurance against individual disclosure.

## Embedded validation checks

Exactly these seven named checks are required. Each emits `{name,status,applicable,reason}`; status is `PASS`, `FAIL`, or `NOT_APPLICABLE`.

| Check | Scope |
|-------|-------|
| `column_shapes_and_support` | Always applicable: version/settings, schema, T1 restrictions, numeric/string shape and support, finite values and valid constant/reduced/full branches |
| `percentiles_monotone` | Every released reduced/full percentile grid, in probability order; N/A if none |
| `category_counts_le_rowcount` | Candidate category levels, integer counts, supported totals; N/A if no categorical blocks |
| `missing_rate_in_unit_interval` | T2+ finite rates and nonmissing-count agreement; T1 N/A |
| `no_subthreshold_cells_emitted` | All visible categorical/cross-tab candidate counts; N/A if none |
| `correlation_matrix_symmetric` | Actual released matrices: shape, finiteness, symmetry, diagonal, bounds; N/A if no available matrix |
| `relationship_support_and_shape` | T3 availability markers, paired support, dimensions, named/association fields, cross-tab totals/null/complementary suppression; T1/T2 N/A |

Every emitted percentile must have a unique expected key and exactly one finite, nonmissing real numeric scalar value before checking order. Aggregate `unlist()` length is not sufficient: a NULL field plus a two-element neighbor can compensate. The same scalar principle applies to string length summaries, model coefficients, and visible cross-tab cells. N/A uses an explicit no-target/tier/unavailable reason, not a claim that absent statistics passed inspection. Block-level unavailable reasons provide the specific cause. `all_passed` requires the **complete required set**, every applicable check PASS, and every inapplicable check explicitly N/A with a reason. Missing checks and exceptions fail; no output is approved/written on validation failure. Validation examines the rounded candidate, never fresh raw statistics as a stand-in. DS-3 additionally evaluates PSD tolerance before generation; indefinite but otherwise valid pairwise matrices may require a documented approximation.

Intake can verify reported support and fields agree; it cannot independently verify the underlying raw support or pair variances from a report alone. Independent fabricated-data execution tests must exercise both assets, mutate candidates before validation, parse R JSON independently, and verify both output files and failure behavior.

## Derivation from Data Onboarding scripts 01-09

| Onboarding script | Contributes | Disclosure filter |
|-------------------|-------------|-------------------|
| 02 structural-profile | row/column counts, dtypes, order | T1 schema |
| 03 column-profile | nulls, uniques, numeric summaries, string lengths/patterns, identifiers | Support-gated value summaries; cell suppression; identifier structure only |
| 04 distribution-analysis | percentile shapes | Supported grids, no raw numeric extremes |
| 08 correlation-dependency | Pearson/Spearman, Cramér's V | T3, actual paired support and numerical validity |
| 09 quality-anomaly | missingness | Rates only, no row-level anomaly listings |

Scripts 10–11 (semantic interpretation/doc reconciliation) remain interpretive DS-4 work inside DAAF against the report, not raw data.
