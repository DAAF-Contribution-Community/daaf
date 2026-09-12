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
- [Maintainer regression check](#maintainer-regression-check)

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
| a9 | Value-summary support and numerical validity | A numeric/string value summary has fewer than k usable observations; reduced quartiles escape below k; a supported constant is incorrectly withheld; paired support is replaced by marginal n; undefined correlations become fabricated zeros. Check all-missing, withheld, eligible constant, reduced and full shapes against `profiling-script-spec.md` |
| a10 | Cross-tab suppression is complementary and `null`-coded (T3) | Suppressed cells are `null` (not `0`); complementary suppression runs so no row/col has a lone suppressed cell; a non-converging table is fully suppressed |

a6 deserves emphasis: trace the smallest **categorical cell** and each statistic's actual usable support separately. A categorical level with count 3 is suppressed; a numeric binary mean of .003 over 1,000 usable observations is eligible. Likewise, .002 missingness over 1,000 records is not a new small-cell violation. Do not withhold whole columns based on those numerators. The support unit is records, not automatically distinct individuals; confirm that assumption with the researcher.

Also trace candidate validation and I/O: typed rounded/suppressed values must be the source of checks and both outputs; no recomputed raw statistics or hardcoded symmetry PASS. A missing required check or exception fails. Validation failure writes no report; output preflight refuses prior targets, and success is announced only after both new files finish. An I/O failure can leave a partial new pair, which must not be shared.

If any item is uncertain (not clearly safe), treat it as a failure and fix the script before the user runs it.

## (b) Internal-consistency validation of the returned report

At intake (DS-3), verify the returned report is internally coherent — the checks the outbound script also embedded (`profiling-script-spec.md` § embedded validation), re-verified on this side because the embedded `all_passed` is the user's claim, not DAAF's verification. Confirm both that the checks are present AND that they actually hold on re-computation from the report's own numbers.

| # | Check | Fails if |
|---|-------|----------|
| b1 | `report_version` accepted for this policy | New-policy acceptance requires `2.0`. Preserve `1.0` as legacy and request a corrected local rerun; never relabel its PASS as compliance. Unknown versions need schema review |
| b2 | Percentiles monotone | For any numeric column, the p1..p99 sequence is not non-decreasing |
| b3 | Category counts ≤ row count | Any level count, or the sum of a column's level counts (incl. `__OTHER__`), exceeds `row_count` |
| b4 | Missingness rates in [0,1] | Any `missing_rate` outside the unit interval |
| b5 | No sub-threshold cells present | Any **visible** count — categorical level, `__OTHER__`, or a non-`null` cross-tab cell — is in `(0, suppression_threshold)`. Walk every emitted count; `null` cross-tab cells are suppressed and skipped. A sub-threshold `__OTHER__` also fails here (the roll-in must have cleared it) |
| b6 | Correlation matrices well-formed (T3) | Non-square, non-symmetric, off-unit diagonal, or entries outside [-1,1] |
| b7 | Correlation PSD-tolerant (T3) | Smallest eigenvalue below `-eps` (mild negatives are OK — rounding; large ones signal corruption) |
| b8 | Suppression settings recorded | `settings.tier` / `settings.suppression_threshold` missing; `settings.relationship_spec` is neither `null` nor a list of pairs |
| b9 | Column blocks match roles and support | A column violates the exact `2.0` shapes in `profiling-script-spec.md`: T1 name/dtype only; T2+ numeric all-missing, withheld, eligible constant, reduced, or full with `n`; string structure also support-gated. Any released summary below k, missing support, or extra forbidden value field fails |
| b10 | Embedded validation complete and honest | Any of the seven required named checks is absent/duplicated; status/applicability/reason disagrees with released targets; applicable check is not PASS; inapplicable check is not explicitly NOT_APPLICABLE; or `all_passed` absent/false |
| b11 | Cross-tab schema/support well-formed (T3) | An unavailable entry carries cells/dimensions; an available entry lacks eligible paired n; `cells` length ≠ `rows`×`cols`; `cells_suppressed` ≠ null count; visible total exceeds n (or differs from n without suppression). A genuine zero is permitted; do not infer a zero was suppressed from the report alone |
| b12 | No lone suppressed cross-tab cell (T3) | Any row or column has exactly one `null` cell (complementary suppression failed) — unless the entry is marked `"collapsed": true` (whole table suppressed) |

Apply b2 to every **released** full/reduced grid, not just full-summary columns; constants have no grid. Require unique expected percentile keys and one finite real numeric scalar per field before monotonicity (NULL/vector compensation is invalid). Apply b3 to candidate counts, unique emitted labels, and `categorical.n`, including total equality when levels are released; missingness must agree with `nonmissing_n` after rounding. Apply b6/b7 only to `available:true` matrices, with NOT_APPLICABLE and the recorded reason for unavailable ones. Independently verify relationship availability/support shapes, pair_n dimensions and bounds, named n at least max(k,10), and associations/cross-tabs n at least k. Unavailable entries must not carry value statistics. Candidate support metadata can be checked for consistency, but intake cannot verify actual raw support or pair variances it never received.

b2, b3, b5 and b9 are load-bearing: they catch malformed or policy-ineligible released fields. A report containing a sub-threshold categorical cell or a below-support value summary is also a disclosure-control failure — flag BLOCKER and notify the user. Do not treat an ordinary rare-event numerator as that failure.

## (c) Synthetic-vs-profile validation

After generation (DS-5), compare **only available targets** within tolerance. First inventory the `2.0` shapes: all-missing/withheld distributions and unavailable relationships have **NOT_APPLICABLE** fidelity with explicit reasons, not PASS; reduced numerics have only quartile targets; supported constants have an exact shared-value target (within released rounding precision), not a fabricated distribution. Structural, type, and seed checks still apply to every column, including placeholders. Missingness remains a separately eligible target even when value summaries are withheld; inject it after marginal/relationship generation. Withheld structure must be logged as unobserved. T1 carries no marginal/missingness/relationship fidelity targets.

| # | Check | Fails if |
|---|-------|----------|
| c1 | Row count matched | `nrow(synthetic)` ≠ `report.row_count` |
| c2 | Column set + types matched | Column names/dtypes differ from the report |
| c3 | Numeric marginals within tolerance | Synthetic percentiles deviate from reported percentiles beyond tolerance (see below) |
| c4 | Categorical proportions within tolerance | Synthetic level proportions deviate from reported proportions beyond tolerance |
| c5 | `__OTHER__` preserved as a bucket | Synthetic data invented real-looking rare values instead of keeping `__OTHER__` |
| c6 | Correlations reproduced within tolerance (T3) | Synthetic correlation matrix deviates from reported beyond tolerance (looser for binary/low-cardinality — see caveats in the generation refs) |
| c7 | No fabricated hidden categories | Synthetic categories fall outside emitted levels (or the documented typed placeholder for an empty level list). Hidden real labels are unknown; QA cannot prove noncollision with values it never received |
| c8 | Identifier scaffolds typed and appropriately labeled | Generated identifiers violate declared types/available structure or use routable email domains. Withheld structure has N/A shape fidelity. Coincidental equality to an unknown real identifier cannot be checked from the profile alone |
| c9 | Missingness rate within tolerance | Synthetic per-column null rate deviates from reported rate beyond tolerance |
| c10 | Seed recorded | Generation log lacks the seed (synthetic data not reproducible) |
| c11 | Named relationship reproduced (T3) | For each `relationships.named` entry, the synthetic OLS slope of `outcome ~ predictor` deviates from the reported slope beyond tolerance (default ±10% of the reported slope; R² within ±0.10) |

c5, c7, c8 are disclosure-adjacent: they check that generation did not fabricate withheld structure and that identifier scaffolds are appropriately typed and labeled. They cannot certify noncollision with unknown real values.

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
| (b) other consistency failures (b2/b3/b4/b6/b9/b10) | **BLOCKER** — report is corrupt/untrustworthy; do not generate. A b9 released summary below minimum support is also a disclosure-control failure; notify the user |
| (b) b7 mild non-PSD | WARNING — project to nearest PD, note the perturbation |
| (c) c1/c2/c7/c8 failures | **BLOCKER** — generation bug or disclosure risk |
| (c) c3/c4/c6/c9/c11 out of tolerance | WARNING — investigate; may be an acceptable approximation limit, may be a bug |
| (b) b11/b12 cross-tab schema or lone-cell failure | **BLOCKER** — b12 is a disclosure event (a lone suppressed cell is recoverable by differencing); b11 signals a malformed/tampered report |
| (c) c10 missing seed | **BLOCKER** by default — reproducibility is the rule; the one narrow exception is the researcher-authorized T4 missing-seed path (`WORKFLOW_PHASE_DO_SYNTHETIC.md` § T4 Variant), which proceeds only with explicit gate authorization and yields a labeled "non-reproducible T4 synthetic artifact" |

Every synthetic dataset that passes carries forward the scaffold-not-substitute caveat regardless of how clean the validation is — passing validation means "structurally faithful to the profile," never "analytically valid."

## Maintainer regression check

The reusable maintainer CLI is `/daaf/scripts/check_profile_templates.py`. Run it through a **fresh captured driver**, not by capturing/executing the reusable utility or shipped assets in place. The driver invokes this CLI with `--base-dir /daaf --work-dir {PROJECT_DIR}/scripts/scratch/{fresh_run_name} --languages python r --suite all`; use a separate fresh work directory with `--suite adjudication` for the targeted follow-up cases. Capture the driver with `bash /daaf/scripts/run_with_capture.sh {absolute_driver_path}`. Inspect the current CLI before constructing the driver; it is maintained separately from the templates.

The work directory must not already exist and must be under a research project's `scripts/scratch/`. The checker uses fabricated Parquet, fresh configured asset copies, project-local TMPDIR, captured executions, source hashes, and retained result/runner logs. No raw sensitive data, network, installation, or CI changes are needed. Review actual per-case outcomes, not only the overall exit code. Never rewrite failed historical evidence.

Regression coverage must include per-field scalar/unique-name validation (NULL/vector percentile compensation and string lengths), Python optimized-mode refusal even for ordinary input, exact integer precision refusal around ±2^53 before conversion, unique reserved-category pooling (A20 + literal OTHER10 + rare3 + rare3 → A20/OTHER16 and three levels binned), paired factor zero-margin removal, and identifier unavailable-structure logging for every dtype. Keep supported 5/5,000 constants, missingness 2/1,000, and binary mean 3/1,000 as positive controls. The existing R 2×2 continuity correction remains intentional. Expected precision refusals must include a clear diagnostic and no reports; an unrelated crash is not a passing refusal test.
