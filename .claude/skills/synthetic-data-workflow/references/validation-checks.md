# Validation Checks

The three-part QA model for the privacy-preserving synthetic-data workflow. Because the real data never enters the container, DAAF cannot recompute statistics against the source file (the usual Data Onboarding QA move). QA is restructured into three independent checks, each guarding a different failure mode:

- **(a) Disclosure-safety review** of the OUTBOUND profiling script — before the user runs it.
- **(b) Internal-consistency validation** of the RETURNED report — at intake (DS-3).
- **(c) Synthetic-vs-profile validation** of the GENERATED data — after generation (DS-5).

## Contents

- [(a) Disclosure-safety review of the outbound script](#a-disclosure-safety-review-of-the-outbound-script)
- [(b) Internal-consistency validation of the returned report](#b-internal-consistency-validation-of-the-returned-report)
- [(c) Synthetic-vs-profile validation](#c-synthetic-vs-profile-validation)
- [Tolerances](#tolerances)
- [Severity mapping](#severity-mapping)

## (a) Disclosure-safety review of the outbound script

**The single most important control in this workflow.** A disclosure leak is irreversible once the report is shared — so a *possible* leak is a BLOCKER, never a WARNING. Reviewed by code-reviewer against the chosen tier's forbidden-emissions list (`disclosure-tiers.md` § forbidden-emissions). This runs on the *configured script*, before the user executes it.

Checklist:

| # | Check | Fails if |
|---|-------|----------|
| a1 | No raw min/max in any code path (T2+) | Any `min()`/`max()` of a value column reaches an emitted field |
| a2 | No example values emitted (T2+) | Any category/string value other than through the suppressed-level or `__OTHER__` path reaches output; any "head"/"sample"/"first rows" emission |
| a3 | Suppression is unconditional at T2+ | Any code path emits a categorical/cross-tab cell without the `< threshold` suppression gate |
| a4 | Identifier columns get structure-only | Any column flagged identifier emits values, percentiles, or category lists |
| a5 | Tier gate is correct | Relationship/cross-tab emission code is reachable at T1/T2; any statistic above the configured tier can be produced |
| a6 | Edge cases can't leak | All-null column, single-row group, single distinct value, an identifier that slips the >95% heuristic — none produces a forbidden emission |
| a7 | No raw-data side channel | No write of the input rows anywhere; no debug print of `df`; no path that copies the source file |
| a8 | Binning cannot leave a sub-threshold `__OTHER__` | The roll-in loop is present: a residual `__OTHER__ < threshold` folds in the smallest retained levels (or fully suppresses the column). A bare `__OTHER__ = sum(binned)` with no roll-in is a leak |
| a9 | Small-n / near-constant / all-missing numerics degrade | A numeric column with n < max(threshold,10) emits quartiles only; a single-distinct or SD=0 column withholds its value; an all-missing column emits no statistics (and does not crash `quantile([])`) |
| a10 | Cross-tab suppression is complementary and `null`-coded (T3) | Suppressed cells are `null` (not `0`); complementary suppression runs so no row/col has a lone suppressed cell; a non-converging table is fully suppressed |

a6 deserves emphasis: the common leak is not the main path but the edge case — a column with two distinct values where one has count 3 must suppress that cell even though the column "looks" safe. Trace every emission for the smallest-cell case.

If any item is uncertain (not clearly safe), treat it as a failure and fix the script before the user runs it.

## (b) Internal-consistency validation of the returned report

At intake (DS-3), verify the returned report is internally coherent — the checks the outbound script also embedded (`profiling-script-spec.md` § embedded validation), re-verified on this side because the embedded `all_passed` is the user's claim, not DAAF's verification. Confirm both that the checks are present AND that they actually hold on re-computation from the report's own numbers.

| # | Check | Fails if |
|---|-------|----------|
| b1 | `report_version` recognized | Version not in the supported set (schema may have drifted) |
| b2 | Percentiles monotone | For any numeric column, the p1..p99 sequence is not non-decreasing |
| b3 | Category counts ≤ row count | Any level count, or the sum of a column's level counts (incl. `__OTHER__`), exceeds `row_count` |
| b4 | Missingness rates in [0,1] | Any `missing_rate` outside the unit interval |
| b5 | No sub-threshold cells present | Any **visible** count — categorical level, `__OTHER__`, or a non-`null` cross-tab cell — is in `(0, suppression_threshold)`. Walk every emitted count; `null` cross-tab cells are suppressed and skipped. A sub-threshold `__OTHER__` also fails here (the roll-in must have cleared it) |
| b6 | Correlation matrices well-formed (T3) | Non-square, non-symmetric, off-unit diagonal, or entries outside [-1,1] |
| b7 | Correlation PSD-tolerant (T3) | Smallest eigenvalue below `-eps` (mild negatives are OK — rounding; large ones signal corruption) |
| b8 | Suppression settings recorded | `settings.tier` / `settings.suppression_threshold` missing; `settings.relationship_spec` is neither `null` nor a list of pairs |
| b9 | Column blocks match roles | A column's present stat block doesn't match its `role`. **T1**: column is exactly `{name, dtype}` (any extra field is a leak). **T2+ numeric**: exactly one of the four shapes — full (`mean`+`sd`+`percentiles` p1..p99), `small_n` (quartiles+`n`), `near_constant` (`n` only), `all_missing` (`n:0`) |
| b10 | Embedded validation present and passing | `validation.all_passed` absent or false |
| b11 | Cross-tab schema well-formed (T3) | `cells` length ≠ `rows`×`cols`; a suppressed cell is `0` instead of `null`; `cells_suppressed` ≠ the count of `null` cells |
| b12 | No lone suppressed cross-tab cell (T3) | Any row or column has exactly one `null` cell (complementary suppression failed) — unless the entry is marked `"collapsed": true` (whole table suppressed) |

b2, b3, b5 are the load-bearing consistency checks: they catch a report that was hand-edited, truncated, or produced by a tampered script. A report that fails b5 (a small cell slipped through) is *also* a disclosure event — flag it as BLOCKER and tell the user their shared report contains a sub-threshold cell.

## (c) Synthetic-vs-profile validation

After generation (DS-5), verify the synthetic data faithfully reflects the profile — within tolerance, because profile-based synthesis is approximate by design.

| # | Check | Fails if |
|---|-------|----------|
| c1 | Row count matched | `nrow(synthetic)` ≠ `report.row_count` |
| c2 | Column set + types matched | Column names/dtypes differ from the report |
| c3 | Numeric marginals within tolerance | Synthetic percentiles deviate from reported percentiles beyond tolerance (see below) |
| c4 | Categorical proportions within tolerance | Synthetic level proportions deviate from reported proportions beyond tolerance |
| c5 | `__OTHER__` preserved as a bucket | Synthetic data invented real-looking rare values instead of keeping `__OTHER__` |
| c6 | Correlations reproduced within tolerance (T3) | Synthetic correlation matrix deviates from reported beyond tolerance (looser for binary/low-cardinality — see caveats in the generation refs) |
| c7 | Suppressed categories absent | Any synthetic categorical value equals a level the profile suppressed (impossible if generation only draws from emitted levels — this is a guard against generation bugs) |
| c8 | Identifiers structurally shaped, value-free | Synthetic identifier values resemble anything real, or collide with a routable domain/format |
| c9 | Missingness rate within tolerance | Synthetic per-column null rate deviates from reported rate beyond tolerance |
| c10 | Seed recorded | Generation log lacks the seed (synthetic data not reproducible) |
| c11 | Named relationship reproduced (T3) | For each `relationships.named` entry, the synthetic OLS slope of `outcome ~ predictor` deviates from the reported slope beyond tolerance (default ±10% of the reported slope; R² within ±0.10) |

c5, c7, c8 are disclosure-adjacent: they confirm generation did not *fabricate* withheld structure or produce anything resembling a real identifier.

## Tolerances

Profile-based synthesis is approximate; tolerances make "within reason" concrete. These are defaults — tighten or loosen per the use case and record the choice.

| Quantity | Default tolerance |
|----------|-------------------|
| Numeric percentiles (c3) | each reproduced percentile within ±5% of the reported value's range span, or ±0.1·IQR, whichever is larger |
| Categorical proportions (c4) | each level proportion within ±0.02 absolute (2 percentage points) |
| Correlation coefficients — continuous (c6) | within ±0.10 of the reported coefficient |
| Correlation coefficients — binary/low-cardinality (c6) | within ±0.20 (Gaussian copula recovers these less faithfully) |
| Missingness rate (c9) | within ±0.01 absolute |
| Named relationship slope (c11) | within ±10% of the reported slope; R² within ±0.10 |
| Correlation PSD tolerance (b7) | smallest eigenvalue ≥ −1e-6 |

## Severity mapping

| Finding | Severity |
|---------|----------|
| Any (a) disclosure-safety failure or uncertainty | **BLOCKER** — fix before the user runs the script |
| (b) b5 sub-threshold cell present in a shared report | **BLOCKER** — a disclosure event; notify the user |
| (b) other consistency failures (b2/b3/b4/b6/b9) | **BLOCKER** — report is corrupt/untrustworthy; do not generate from it |
| (b) b7 mild non-PSD | WARNING — project to nearest PD, note the perturbation |
| (c) c1/c2/c7/c8 failures | **BLOCKER** — generation bug or disclosure risk |
| (c) c3/c4/c6/c9/c11 out of tolerance | WARNING — investigate; may be an acceptable approximation limit, may be a bug |
| (b) b11/b12 cross-tab schema or lone-cell failure | **BLOCKER** — b12 is a disclosure event (a lone suppressed cell is recoverable by differencing); b11 signals a malformed/tampered report |
| (c) c10 missing seed | **BLOCKER** by default — reproducibility is the rule; the one narrow exception is the researcher-authorized T4 missing-seed path (`WORKFLOW_PHASE_DO_SYNTHETIC.md` § T4 Variant), which proceeds only with explicit gate authorization and yields a labeled "non-reproducible T4 synthetic artifact" |

Every synthetic dataset that passes carries forward the scaffold-not-substitute caveat regardless of how clean the validation is — passing validation means "structurally faithful to the profile," never "analytically valid."
