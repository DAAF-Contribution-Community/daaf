# Validation Checks

The QA model for the privacy-preserving synthetic-data workflow. Because the real data never enters the container, DAAF cannot recompute statistics against the source file (the usual Data Onboarding QA move). Validation is restructured into three independent review checkpoints, each guarding a different failure mode, plus two in-script validators that halt on failure:

- **(a) Disclosure-safety review** of the OUTBOUND profiling/synthesizer script — before the user runs it → **QAS-A** (DS-1).
- **(b) Internal-consistency validation** of the RETURNED report — at intake → **CPS-INTAKE** (script) + **QAS-B** (review), DS-3.
- **(c) Synthetic-vs-profile validation** of the GENERATED data — after generation → **CPS-GEN** (script) + **QAS-C** (review), DS-5.

## Contents

- [Where the checks are defined](#where-the-checks-are-defined)
- [The a/b/c letters and the canonical keys](#the-abc-letters-and-the-canonical-keys)
- [Skill-local detail: forbidden emissions and tier specifics](#skill-local-detail-forbidden-emissions-and-tier-specifics)
- [Tolerances](#tolerances)
- [Maintainer regression check](#maintainer-regression-check)

## Where the checks are defined

**The check tables live in one place.** The per-check definitions — every check's stable key, what it validates, its BLOCKER condition, and the per-check statement of what is *not applicable* (`[SKIPPED]`) versus *not verifiable* (`[NOT VERIFIED]`) — are canonical in `agent_reference/QA_CHECKPOINTS.md` § Synthetic-Path QA Checkpoints (QAS-A, QAS-B, QAS-C). Read them there and use those keys verbatim. Do not paraphrase them here and do not re-derive them from memory: the whole value of the checkpoint is that its keys, outcome tokens, count line, and verdict are identical across every synthetic-path project. The severity overrides that make this path stricter than every other one are canonical in the same file, § QAS Severity Overrides (Synthetic Path).

| Checkpoint | Family | Where it runs | Verdict line | Canonical definition |
|------------|--------|---------------|--------------|----------------------|
| **QAS-A** (a-checks) | review | code-reviewer, DS-1 | `QAS-A RESULT: PASSED \| BLOCKER` (WARNING is not a legal QAS-A verdict) | `QA_CHECKPOINTS.md` § Synthetic-Path QA Checkpoints > QAS-A |
| **CPS-INTAKE** | script-halting | container script, DS-3 | `CPS-INTAKE VALIDATION: PASSED \| PASSED WITH WARNINGS \| FAILED` | `agent_reference/VALIDATION_CHECKPOINTS.md` § Synthetic-Path Validation Checkpoints > CPS-INTAKE: Profile Report Intake Validation (DS-3) |
| **QAS-B** (b-checks) | review | code-reviewer, DS-3 | `QAS-B RESULT: PASSED \| WARNING \| BLOCKER` | `QA_CHECKPOINTS.md` § Synthetic-Path QA Checkpoints > QAS-B |
| **CPS-GEN** | script-halting | container script, DS-5 | `CPS-GEN VALIDATION: PASSED \| PASSED WITH WARNINGS \| FAILED` | `VALIDATION_CHECKPOINTS.md` § Synthetic-Path Validation Checkpoints > CPS-GEN: Synthetic Generation Validation (DS-5) |
| **QAS-C** (c-checks) | review | code-reviewer, DS-5 | `QAS-C RESULT: PASSED \| WARNING \| BLOCKER` | `QA_CHECKPOINTS.md` § Synthetic-Path QA Checkpoints > QAS-C |

**The script blocks are copied, never rewritten.** DS-3's intake validator and DS-5's generation validator are shipped code blocks. Copy the `# --- CPS-INTAKE Validation ---` / `# --- CPS-GEN Validation ---` block (Python and R) verbatim from `agent_reference/VALIDATION_CHECKPOINTS.md` § Synthetic-Path Validation Checkpoints into the script's `# --- Validate ---` section, and assign its config stanza in `# --- Config ---`. `WORKFLOW_PHASE_DO_SYNTHETIC.md` supplies the stanza and the stage-specific guidance; the block itself is maintained only in `VALIDATION_CHECKPOINTS.md`.

**The user-side script validators are separate.** The profiler embedded in `assets/profile_data_template.{py,R}` prints its own `Checks: {passed} passed, {warning} warnings, {failed} failed, {not_verified} not verified, {skipped} skipped` line followed by `PROFILE VALIDATION: PASSED | PASSED WITH WARNINGS | FAILED`; the T4 synthesizer in `assets/synthesize_local_template.{py,R}` prints the same count line followed by `SYNTHESIS VALIDATION: …`. In the JSON report, `validation.checks[].status` takes the wire enum `PASS | FAIL | NOT_APPLICABLE | NOT_VERIFIED`. Those are the user's claims about their own run; QAS-B re-derives them from the report's own numbers rather than trusting `all_passed`.

## The a/b/c letters and the canonical keys

The historical a1-a11 (a11 new this revision) / b1-b12 / c1-c11 letters survive as labels in the canonical tables, but the **stable check key** (`no_subthreshold_cells`, `other_bucket_preserved`, …) is what a script emits and what a `not_applicable` mapping is keyed by. QAS-A gained **a11** (`t4_log_aggregate_only`): the T4 shareable synthesis log contains no per-variable utility or comparison output, only an aggregate statistic. CPS-INTAKE and CPS-GEN implement the computable subset of the b- and c-checks under their own key lists, documented in the Usage Notes of their `VALIDATION_CHECKPOINTS.md` section.

Three rules from the canonical overrides are worth restating because they bind every author of a synthetic-path script:

- **Non-declarable keys.** No `not_applicable` entry may exist for any QAS-A key, for QAS-B `no_subthreshold_cells` / `crosstab_schema_wellformed` / `no_lone_suppressed_cell`, or for QAS-C `other_bucket_preserved` / `no_fabricated_categories` / `identifier_scaffolds_typed_value_free`. Declaring one is itself the finding. The CPS blocks enforce the same rule (with `[FAIL]`) over their own non-declarable sets, which are not a key-for-key copy of these six — CPS-GEN, for one, also makes `seed_recorded` non-declarable; read those sets from `agent_reference/VALIDATION_CHECKPOINTS.md` § CPS Usage Notes.
- **Aggregate-only evidence.** A `[PASS]` on a disclosure check carries counts and the threshold, never a cell value, a minimum, or a level label with its count.
- **`[NOT VERIFIED]` escalates here.** Any not-verified item in QAS-A is a BLOCKER, as is a not-verified item on the six per-check keys above. On this path an unproven-safe emission path is an unsafe one.

## Skill-local detail: forbidden emissions and tier specifics

QAS-A is reviewed against the chosen tier's **forbidden-emissions list** in `disclosure-tiers.md` § The forbidden-emissions list (for disclosure-safety review), which is the authority for *what* may not cross the boundary at each tier; QA_CHECKPOINTS.md is the authority for *how* the review is counted and reported. T4 adds one item to that list: per-variable utility or comparison output (`compare()` / `utility.gen` marginal tables, frequency counts, histograms) must never reach the shareable synthesis log — see `local-synthesis-t4.md`.

Tier-specific and support-specific nuances the canonical tables assume but do not teach:

- **Trace the smallest categorical cell and each statistic's usable support separately.** A categorical level with count 3 is suppressed; a numeric binary mean of .003 over 1,000 usable observations is eligible, and .002 missingness over 1,000 records is not a small-cell violation. Do not withhold whole columns on those numerators. The support unit is records, not automatically distinct individuals — confirm that assumption with the researcher.
- **Trace candidate validation and I/O, not just the statistics.** Typed rounded/suppressed values must be the source of both the embedded checks and both output files; no recomputed raw statistics, no hardcoded symmetry PASS. A validation failure writes no report; the output preflight refuses prior targets; success is announced only after both new files finish. An I/O failure can leave a partial new pair, which must not be shared.
- **Report `2.0` shapes.** Apply percentile monotonicity to every *released* full/reduced grid (constants have no grid); require unique expected percentile keys and one finite real scalar per field. Apply category-count checks to candidate counts, unique emitted labels, and `categorical.n`, including total equality when levels are released; missingness must agree with `nonmissing_n` after rounding. Apply the correlation checks only to `available:true` matrices, declaring unavailable ones with the report's own recorded reason. Unavailable entries must not carry value statistics. Intake can check candidate support metadata for consistency but can never verify raw support or pair variances it never received.
- **Generation-side inventory before comparison.** All-missing/withheld distributions and unavailable relationships have NOT_APPLICABLE fidelity with explicit reasons, never a fabricated PASS; reduced numerics carry only quartile targets; a supported constant has an exact shared-value target within released rounding precision. Structural, type, and seed checks apply to every column including typed placeholders. Missingness stays a separately eligible target even where value summaries are withheld — inject it after marginal/relationship generation. T1 carries no marginal/missingness/relationship fidelity targets.

Every synthetic dataset that passes carries forward the scaffold-not-substitute caveat regardless of how clean the validation is — passing validation means "structurally faithful to the profile," never "analytically valid."

## Tolerances

Profile-based synthesis is approximate; tolerances make "within reason" concrete. These are the defaults the canonical QAS-C and CPS-GEN definitions refer to as § Tolerances — tighten or loosen per the use case and record the choice in the script's config stanza.

| Quantity | Default tolerance |
|----------|-------------------|
| Numeric percentiles (c3) | relative tolerance of 0.10 on each reproduced percentile against the reported value, with a floor of 1.0 absolute for values near zero — the shipped CPS-GEN `numeric_tolerance` default |
| Categorical proportions (c4) | each level proportion within ±0.02 absolute (2 percentage points) |
| Correlation coefficients (c6) | within ±0.10 of the reported coefficient, for every released pair — the shipped CPS-GEN `correlation_tolerance` default, the only correlation band the block applies |
| Correlation coefficients — binary/low-cardinality pairs (c6, **QAS-C reviewer allowance only**) | the reviewer may accept up to ±0.20 (Gaussian copula recovers these less faithfully). CPS-GEN does not apply this band: such a pair outside ±0.10 is still a CPS-GEN `[WARNING]`, which QAS-C explains under the allowance |
| Missingness rate (c9) | within ±0.01 absolute |
| Named relationship slope (c11) | within ±10% of the reported slope; R² within ±0.10 |
| Correlation PSD tolerance (b7) | smallest eigenvalue ≥ −1e-6 |

The numeric row states what the shipped CPS-GEN block actually computes. The older wording — "±5% of the reported value's range span, or ±0.1·IQR, whichever is larger" — is **retired**: it was never implemented, and a span/IQR rule cannot be evaluated from a report that releases no range. A project that needs a tighter bound sets `numeric_tolerance` in the CPS-GEN config stanza (and records why); the three other `*_tolerance` scalars in that stanza correspond to the categorical row, the first correlation row, and the missingness row above. The binary/low-cardinality correlation row has **no** config scalar and no CPS-GEN counterpart: it is a reviewer allowance applied in QAS-C, never a second tolerance inside the block.

## Maintainer regression check

The reusable maintainer CLI is `/daaf/scripts/check_profile_templates.py`. Run it through a **fresh captured driver**, not by capturing/executing the reusable utility or shipped assets in place. The driver invokes this CLI with `--base-dir /daaf --work-dir {PROJECT_DIR}/scripts/scratch/{fresh_run_name} --languages python r --suite all`; use a separate fresh work directory with `--suite adjudication` for the targeted follow-up cases. Capture the driver with `bash /daaf/scripts/run_with_capture.sh {absolute_driver_path}`. Inspect the current CLI before constructing the driver; it is maintained separately from the templates.

The checker now adjudicates each embedded check against the **four-state expectation model** — `PASS | FAIL | NOT_APPLICABLE | NOT_VERIFIED`, the same wire enum the report carries (`check_profile_templates.py` § `inspect_report`) — and models the expected status per check per fixture, so a fixture that releases no numeric columns expects the profiler's own fixed-reason skip rather than a silent pass. It also asserts that stdout carries the `Checks:` count line and a `PROFILE VALIDATION:` verdict, and that the verdict is `FAILED` whenever `all_passed` is false. Read the case count off the run's own `REGRESSION_SUMMARY total=N passed=N failed=0` line (N was 130 when the four-state model landed) rather than assuming a fixed number, and review actual per-case outcomes, not only the overall exit code.

The work directory must not already exist and must be under a research project's `scripts/scratch/`. The checker uses fabricated Parquet, fresh configured asset copies, project-local TMPDIR, captured executions, source hashes, and retained result/runner logs. No raw sensitive data, network, installation, or CI changes are needed. Never rewrite failed historical evidence.

Regression coverage must include per-field scalar/unique-name validation (NULL/vector percentile compensation and string lengths), Python optimized-mode refusal even for ordinary input, exact integer precision refusal around ±2^53 before conversion, unique reserved-category pooling (A20 + literal OTHER10 + rare3 + rare3 → A20/OTHER16 and three levels binned), paired factor zero-margin removal, identifier unavailable-structure logging for every dtype, and the disclosure-safety negative fixtures (a categorical column whose categorical block is missing must FAIL scan completeness; an entry carrying `cells_suppressed` without `cells` must never PASS; a check with an empty reason is NOT_VERIFIED and `all_passed` false), plus two declaration-free assertions: neither template carries a researcher `not_applicable` setting, and every embedded reason in every accepted report is in CPS-INTAKE's vocabulary (`candidate_fields_checked` for PASS, one of the intake's fixed forms for NOT_APPLICABLE). Keep supported 5/5,000 constants, missingness 2/1,000, and binary mean 3/1,000 as positive controls. The existing R 2×2 continuity correction remains intentional. Expected precision refusals must include a clear diagnostic and no reports; an unrelated crash is not a passing refusal test.
