# Disclosure Tiers

The four-tier disclosure ladder that governs what may cross the DAAF container boundary in the privacy-preserving synthetic-data workflow. Each tier is a strict superset of the tier below it: T2 emits everything T1 does plus marginals, T3 emits everything T2 does plus relationships, T4 is a different mechanism (local synthesis) layered on top.

## Contents

- [Governing principle: minimize the residual](#governing-principle)
- [T1 — Schema](#t1-schema)
- [T2 — Marginals (default)](#t2-marginals-default)
- [T3 — Relationships](#t3-relationships)
- [T4 — Local high-fidelity synthesis](#t4-local-high-fidelity-synthesis)
- [Suppression rules (shared across T2+)](#suppression-rules)
- [Choosing a tier](#choosing-a-tier)
- [The forbidden-emissions list (for disclosure-safety review)](#forbidden-emissions-list)
- [Grounding in disclosure-control practice](#grounding)

## Governing principle: minimize the residual {#governing-principle}

The Five Safes framework (Ritchie/ONS) treats "safe data" as a **residual** — you strip only as much information as the other safeguards force you to. Applied here: pick the *lowest* tier that still lets the intended code-development work proceed. A pipeline that only needs to compile and run against correctly-typed columns needs T1. A pipeline whose logic branches on category values or numeric thresholds needs T2. A pipeline being dry-run for plausible model behavior (coefficient signs, join fan-out, correlation-driven feature engineering) needs T3. Only when the user needs synthetic data faithful enough to trust intermediate diagnostics do they escalate to T4 — and even then, per the cardinal doctrine, findings are never final until re-run on real data.

Higher tiers carry more re-identification risk. Every additional statistic is a constraint on the real data, and constraints combine: primary suppression alone is insufficient because values can be recovered from marginal totals or by differencing across queries (UK Data Service SDC handbook; NCES SPWP22). That is why the tiers are cumulative and why suppression is applied consistently, not ad hoc.

## T1 — Schema {#t1-schema}

**Emits:** column names, column dtypes (as detected by the profiler), and the total row count. Nothing else. Each column object is exactly `{name, dtype}`.

**Forbids:** every value, every summary statistic, every count beyond the single grand total row count, any per-column distributional information. This includes `missing_rate`, `n_distinct`, `uniqueness_ratio`, `is_identifier`, and even `role` — `role` is *derived* from uniqueness + identifier detection, so emitting it would leak a per-column distributional fact (a column typed `role: "identifier"` would betray that it is near-unique). T1 generation needs only name + dtype, so nothing is lost by withholding role here.

**When appropriate:** the analysis code only needs the *shape* of the data — correct column names to reference, correct types to write transformations against, an approximate scale for performance planning. A schema is enough to write and syntax-check most of a pipeline's plumbing.

**Re-identification risk:** minimal. Column names can occasionally leak sensitive structure (e.g., a column literally named `hiv_status`), so the `.txt` review still asks the user to confirm the schema itself is shareable, but no record-level information is present.

## T2 — Marginals (default) {#t2-marginals-default}

The default tier. Emits everything in T1, plus per-column univariate summaries with suppression applied.

**Categorical columns emit:**
- The list of levels **with counts**, but with **small-cell suppression**: any level whose count is below the suppression threshold (default 5, user-configurable) is removed from the explicit list.
- **Rare-category binning:** suppressed/rare levels are collapsed into a single `__OTHER__` bucket carrying the aggregate count of all binned levels (so the total is preserved without exposing any individual small level).
- The count of distinct levels (cardinality) and the number of levels binned.

**Numeric columns emit** (full-summary case):
- Percentiles at p1, p5, p10, p25, p50, p75, p90, p95, p99.
- Mean and standard deviation.
- **NO raw min and max** — these are outlier-disclosure risks (a single extreme value can identify a record). The p1/p99 percentiles stand in for the tails; the SDC handbook's guidance to "prefer median, quartiles, percentiles to mean/SD/min/max" for extreme data is the basis.

Two guards degrade the numeric summary when the ordinary case would leak more than it appears to:
- **Small-n guard.** If a numeric column has fewer than max(`SUPPRESSION_THRESHOLD`, 10) non-missing values, it emits **only p25/p50/p75 + n** (flagged "reduced summary"), with **no p1/p99** (at small n the extreme percentiles approximate the true min/max — the same outlier-disclosure risk min/max carry) and **no mean/SD**.
- **Near-constant guard.** If a numeric column has a single distinct non-missing value (or SD = 0), it emits **only `{near_constant: true, n}`** — the value itself is withheld, because a mean or percentile of a constant column *is* that value.
- An all-missing numeric emits `{n: 0, all_missing: true}` — there is nothing to summarize.

**All columns emit:**
- Missingness rate (fraction null in [0,1]).

**String columns additionally emit:**
- Length statistics (min/mean/max **length**, not min/max value).
- Pattern flags (looks like email / phone / date / ID / free-text) as booleans — **never an example value**.

**Identifier columns** get **structure-only** treatment: dtype, uniqueness ratio, and length statistics only. No values, no percentiles of the underlying encoding. The flagging rule is deliberately asymmetric to avoid crippling legitimate analytic variables:
- A **string** column that is >95% unique is flagged (it is a key — `client_id`, an email).
- A **continuous numeric** column that is near-unique is **not** flagged by uniqueness alone — it is a measurement (income, a test score), not a key, and the percentiles-not-min/max treatment already protects it. Flagging it would needlessly withhold exactly the distribution and correlations synthesis needs.
- **Any** column (numeric or string) whose **name** matches an identifier pattern (`*_id`, `uuid`, `account`, `ssn`, `email`, `phone`) or whose **values** match an email/phone pattern is flagged regardless of type. (Phone detection requires ≥10 digits so ISO dates, which are digit-and-dash shaped, are not mistaken for phones.)

**Forbids:** raw min/max, any example string value, any category count below the suppression threshold, any identifier value, any joint/bivariate information.

## T3 — Relationships {#t3-relationships}

Emits everything in T2, plus bivariate structure. This is what lets synthetic data reproduce approximate relationships (correlated numerics, associated categoricals), which matters when the code being developed depends on those relationships (feature engineering, join behavior, model dry-runs).

**Numeric–numeric:** Pearson and Spearman correlation matrices over the numeric columns. Correlation coefficients are ratios, not counts, and carry low disclosure risk on their own — but they are still constraints, so they only appear at T3.

**Categorical–categorical:** Cramér's V for pairs of categorical columns (a symmetric association measure in [0,1]).

**Optional named relationships:** if the user specifies an outcome and predictors (via `RELATIONSHIP_SPEC`), a compact summary of the outcome~predictor relationship (e.g., group means of the outcome by predictor level, or a simple coefficient vector) — with the same small-cell suppression applied to any group whose n is below threshold.

**Cross-tabs:** two-way cross-tabulations for specified categorical pairs, with **cell suppression** — any cell below the threshold is suppressed, and (because differencing can recover a single suppressed cell from margins) suppression is applied so that no row or column has exactly one suppressed cell where possible; when a lone small cell would otherwise be recoverable, an additional (complementary) cell is suppressed. See `validation-checks.md` for the consistency this must satisfy.

**Forbids:** all T2 forbiddens, plus any unsuppressed small cross-tab cell.

## T4 — Local high-fidelity synthesis {#t4-local-high-fidelity-synthesis}

A different mechanism, not just more statistics. At T1-T3 the profile crosses the boundary and DAAF generates synthetic data *from the profile*. At T4 the **user runs a data-fitted synthesizer locally**, inside their own environment, on the real data — and only the resulting **synthetic rows** cross the boundary.

**What the user runs:** `synthpop` (R, CART synthesis — the flagship: agency-grade, light dependencies, handles missingness patterns) or SDV `GaussianCopulaSynthesizer` (Python). Templates: `assets/synthesize_local_template.R` / `.py`. Detail in `local-synthesis-t4.md`.

**What crosses the boundary:** a synthetic parquet (or CSV) of generated rows, plus a generation log (seed, library versions, the synthesizer's own utility comparison summary). 

**What NEVER crosses the boundary:** the real data, and — critically — **the fitted model object**. A fitted synthesizer can memorize and regenerate real records; the model artifact is as sensitive as the data. The templates write only the synthetic output and are commented loudly to this effect.

**Framing (from Census SIPP Synthetic Beta):** even T4 synthetic rows are "synthetic," not "gold standard." A cell near 10 in the synthetic data may be smaller in the real data. T4 buys higher fidelity for code development; it does not lift the finalize-against-real-data requirement.

## Suppression rules (shared across T2+) {#suppression-rules}

| Rule | Behavior | Rationale |
|------|----------|-----------|
| Small-cell suppression | Categorical levels and cross-tab cells with count < `SUPPRESSION_THRESHOLD` (default 5) are removed from explicit output | Standard SDC threshold rule; a small cell can identify individuals |
| Rare-category binning + roll-in | Suppressed categorical levels collapse into `__OTHER__` with aggregate count; if that `__OTHER__` residual is itself below threshold, the smallest *retained* levels are rolled in until it clears the threshold (or the whole column is suppressed) | A sub-threshold `__OTHER__` is itself a small cell — binning must not create a new one |
| No raw min/max | Numeric tails represented by p1/p99 percentiles only | Min/max are outlier-disclosure risks |
| Small-n / near-constant numeric guards | < max(threshold, 10) non-missing → quartiles only, no tails/mean/SD; single distinct value or SD = 0 → value withheld entirely | At small n the tail percentiles approach the real min/max; a constant column's mean *is* its value |
| No example values | String/categorical example values never emitted | Values can be direct identifiers (names, free text) |
| Identifier structure-only | >95%-unique *string* columns, name/value-pattern-matched columns (any type) get dtype/uniqueness/length only; continuous numerics are NOT flagged by uniqueness alone | Quasi-identifiers combine to re-identify (gender+ZIP+DOB → 87% of US population); numerics stay usable because percentiles-not-min/max already protect them |
| Complementary suppression | In a cross-tab, while any row or column has exactly one suppressed cell, the smallest visible cell in that row/column is also suppressed (iterated to a fixed point, cap 10; if it cannot converge the whole table is suppressed). Suppressed cells are emitted as `null`, never `0` | Primary suppression alone is defeated by differencing against margins; `null` (vs `0`) keeps a suppressed cell distinguishable from a true zero |

The threshold is user-configurable because agencies differ (5 is common; some use 10). Higher is safer. It is recorded in the report so downstream validation knows the rule that was applied.

## Choosing a tier {#choosing-a-tier}

```
What does the code being developed actually need?
├─ Just correct column names and types (plumbing, schema-driven code)
│   └─ T1 Schema
├─ Code branches on category values or numeric thresholds; needs realistic
│   marginal shapes to exercise those branches
│   └─ T2 Marginals (the default — start here unless T1 clearly suffices)
├─ Code depends on relationships: correlated features, categorical associations,
│   join fan-out, model dry-runs where coefficient signs/magnitudes matter
│   └─ T3 Relationships
└─ Needs synthetic data faithful enough to trust intermediate diagnostics, and
    the user can run a synthesizer inside their environment
    └─ T4 Local high-fidelity synthesis
```

Escalate one tier at a time, and only on demonstrated need — every step up adds disclosure risk. Document the chosen tier and why in the skill's Synthetic Data Notice.

## The forbidden-emissions list (for disclosure-safety review) {#forbidden-emissions-list}

The disclosure-safety review (QA check (a) in `validation-checks.md`) verifies the configured profiling script cannot emit, at the chosen tier, anything on this list:

| At tier | Must NOT appear in the report |
|---------|-------------------------------|
| T1 | Any value, any statistic, any count except the grand total row count |
| T2 | Raw min/max; example string/categorical values; any category count < threshold; identifier values; any correlation/cross-tab/bivariate figure |
| T3 | (T2 list except correlations/cross-tabs, which are now permitted) plus any unsuppressed cross-tab cell < threshold; any example value; any identifier value; raw min/max |
| T4 | The real data; the fitted model object; anything other than synthetic rows + generation log |

If the script *could* emit any forbidden item — even in an edge case (all-null column, single-row group, an identifier that slipped the >95% heuristic) — that is a BLOCKER, because a disclosure leak is irreversible once the report is shared.

## Grounding in disclosure-control practice {#grounding}

Every rule above traces to established practice, documented with sources in `synthetic-data-research.md` §3:

- **Five Safes** (Ritchie/ONS): safe data is a residual — the minimize-the-tier principle.
- **Small-cell suppression** at threshold 5 (sometimes 10); **primary suppression is insufficient** without complementary/secondary suppression — UK Data Service SDC handbook, NCES SPWP22, PMC review.
- **Prefer percentiles to min/max** for extreme data; min/max and outliers are disclosure risks — SDC handbook.
- **Access tiering** (PUF > SUF > enclave) and the SIPP Synthetic Beta tiered model (Synthetic → Completed → Gold Standard) — the conceptual model for T1→T4.
- **Quasi-identifier re-identification** (gender+ZIP+DOB) — the basis for identifier structure-only treatment.
