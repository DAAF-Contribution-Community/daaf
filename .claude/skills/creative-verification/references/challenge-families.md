# Challenge Families

The 12 challenge families of creative verification, organized over the four
**Shadish–Cook–Campbell validity types** (internal, statistical-conclusion,
construct, external; Shadish, Cook & Campbell 2002 —
https://pmc.ncbi.nlm.nih.gov/articles/PMC6182849/ ; graphical threat catalog:
https://journals.lww.com/epidem/Fulltext/2020/05000/A_Graphical_Catalog_of_Threats_to_Validity_.11.aspx).
Each family turns a *worry* into a *test* — a concrete observable that would
discriminate the focal claim from a competing explanation. This file is the
working reference for designing that test: per family you get a definition, its
validity-type tags, when to reach for it, 2–4 Python-first recipe sketches, how to
read the result, and the pitfalls that most often make a family misfire.

**How to read the recipes.** Recipes are *sketches* in DAAF's flat, sequential
script style (no functions, IAT comments, section separators), not runnable
scripts — they show the shape of the test and the decisive assertion, and assume
the executor fills in paths, column names, and validation. Every recipe honors the
container constraint: no runtime installs. Confirmed-installed libraries used below
are `polars`, `numpy`, `scipy`, `statsmodels` (0.14.6), `pyfixest` (0.60.0),
`linearmodels` (7.0), `rdrobust` (1.3.0), `plotnine`, `plotly`, `marimo`,
`marginaleffects`. Family 11 (identification-assumption) routes to
`sensitivity-statistics.md` for its computable statistics rather than duplicating
formulas here.

**The mission anchor.** The denominator is always researcher attention. A family is
worth invoking when a cheap behavioral test on an *output* buys back an expensive
line-by-line inspection the researcher would otherwise owe. Family 9
(data-lineage) is the workhorse for that goal and carries the richest recipe set.

---

## Validity-Type Map

| Validity type | What it protects | Families that stress it |
|---------------|------------------|-------------------------|
| **Statistical-conclusion** | Is there a real covariation, correctly quantified? | 1, 2, 6, 8 |
| **Internal** | Is the relationship causal within this sample? | 2, 3, 5, 6, 7, 9, 11 |
| **Construct** | Do the measures capture the intended constructs? | 1, 3, 4, 8 |
| **External** | Does it generalize beyond this sample/setting? | 10, 12 |

A family can stress more than one type; the table in SKILL.md lists each family's
primary tag(s). Use the map to check *coverage*: if every test a session has run
sits under one validity type, the other three are unexamined — say so in the
ledger's coverage map.

---

## Family 1 — Population & Denominator

**Validity:** statistical-conclusion, construct.

**Definition.** The result may be an artifact of *who is counted* — the numerator's
inclusion rule, the denominator's population-at-risk, or the unit of analysis.
"12% of schools" means something different when the denominator is all schools, all
Title I schools, or all schools that reported.

**When to use.** A rate, share, per-capita, or "X per Y" claim; any figure where the
denominator was a modeling choice; when the researcher says "it might be who's in
or out of the base."

**Recipe 1a — Denominator swap.** Recompute the headline rate under each defensible
denominator and show the spread.

```python
# --- Compute ---
# INTENT: recompute the focal rate under each plausible population-at-risk
# REASONING: if the claim is denominator-robust, all variants land near the headline
# ASSUMES: `events` numerator is fixed; only the base population changes
denoms = {
    "all_units": df,
    "reporting_only": df.filter(pl.col("reported") == 1),
    "eligible_only": df.filter(pl.col("eligible") == 1),
}
rows = []
for name, frame in denoms.items():
    rate = frame["events"].sum() / frame.height
    rows.append({"denominator": name, "rate": rate, "n_base": frame.height})
curve = pl.DataFrame(rows)
print(curve)
# INTENT: decision rule lives in the ledger — e.g. "claim holds if all variants within ±2pp"
assert curve["rate"].max() - curve["rate"].min() < 0.02, "denominator choice moves the rate materially"
```

**Recipe 1b — Unit-of-analysis shift.** Re-derive at the level the decision is
actually made (student vs. school vs. district). Aggregation level silently reweights.

```python
# INTENT: does the sign/magnitude survive when the unit matches the decision unit?
# REASONING: a district-weighted mean and a student-weighted mean answer different questions
student_level = df["outcome"].mean()
school_level = df.group_by("school_id").agg(pl.col("outcome").mean()).get_column("outcome").mean()
print({"student_weighted": student_level, "school_weighted": school_level})
```

**Interpretation.** Convergence across denominators/units *supports* the claim and
weakens "it's a base-rate artifact." Divergence usually lands as *reveals
data/process issue* (the reporting population is selective) or *weakens* (the claim
was denominator-specific and wasn't scoped that way).

**Pitfalls.** Denominators built from a *selective* reporting population smuggle in a
missingness problem — route the divergence to Family 3, don't just pick the
flattering base. Rates over tiny denominators are unstable; check `n_base`.

---

## Family 2 — Composition & Aggregation (Simpson's, weighting)

**Validity:** statistical-conclusion, internal.

**Definition.** An aggregate can reverse or vanish within subgroups (Simpson's
paradox), or be driven by a shift in *composition* rather than a change in *rates*.
Weighted and unweighted views can disagree.

**When to use.** Any pooled mean, trend, or difference; any comparison across groups
of unequal size; when a total moved but the researcher isn't sure whether rates
moved or the mix did.

**Recipe 2a — Subgroup decomposition / Simpson check.**

```python
# INTENT: check whether the pooled direction reverses within subgroups
# REASONING: Simpson's paradox — a confound correlated with both group and outcome
# ASSUMES: `subgroup` is the plausible confounder (e.g. sector, region)
pooled = df.group_by("treated").agg(pl.col("outcome").mean())
within = df.group_by(["subgroup", "treated"]).agg(pl.col("outcome").mean())
print(pooled)
print(within.sort(["subgroup", "treated"]))
# INTENT: flag if the within-subgroup sign disagrees with the pooled sign
```

**Recipe 2b — Oaxaca-style rate-vs-composition split.** Decompose a change into a
part from shifting group sizes and a part from shifting within-group rates.

```python
# INTENT: attribute the total change to composition (weights) vs. rates
# REASONING: mix-shift and rate-change are different stories with different implications
w0 = t0.group_by("g").agg(pl.col("n").sum()); r0 = t0.group_by("g").agg(pl.col("rate").mean())
w1 = t1.group_by("g").agg(pl.col("n").sum()); r1 = t1.group_by("g").agg(pl.col("rate").mean())
# composition effect: hold rates at t0, move weights to t1; rate effect: the complement
```

**Recipe 2c — Weighted vs. unweighted.** Report both; a large gap means a few heavy
units dominate.

**Interpretation.** A pooled result that *survives* decomposition weakens the
composition alternative and *supports* the claim. A reversal is a strong *weakens*
or *reveals data/process issue* result — never suppress it.

**Pitfalls.** Choosing the subgroup post hoc to produce a reversal is fishing;
pre-commit the subgroup in the ledger. Weighting by a variable on the causal path
introduces bias rather than removing it.

---

## Family 3 — Missingness & Observability (suppression, selective availability)

**Validity:** internal, construct.

**Definition.** The result may be driven by *what is missing* or *what is suppressed*
rather than by the substantive relationship. Missingness that correlates with the
outcome (MNAR) biases complete-case analysis; suppressed small cells (education-data
code `-3`) silently drop exactly the extreme observations.

**When to use.** Any dataset with suppression codes, non-response, or coverage that
varies by group/year; when the researcher worries "the gap might be because the
hard cases are missing."

**Recipe 3a — Missingness map.** Cross-tabulate missing/suppressed rates by the
groups the claim compares.

```python
# INTENT: is missingness itself correlated with the comparison axis?
# REASONING: differential missingness across groups is a competing explanation for a gap
# ASSUMES: -1 missing, -2 not-applicable, -3 suppressed (Urban Portal convention)
miss = (df.with_columns((pl.col("value") == -3).alias("suppressed"),
                        (pl.col("value") == -1).alias("missing"))
          .group_by("group").agg(pl.col("suppressed").mean(), pl.col("missing").mean()))
print(miss.sort("group"))
# INTENT: if suppression rate differs sharply across groups, the observed gap may be a coverage artifact
```

**Recipe 3b — Bounded (Manski-style) worst/best case.** Instead of assuming missing
values, bound the estimate by imputing the extremes.

```python
# INTENT: how wide is the estimate once missing units take their most/least favorable values?
# REASONING: if the bounds still exclude the null, the claim survives missingness agnostically
lo = df.with_columns(pl.when(pl.col("value") < 0).then(pl.col("floor")).otherwise(pl.col("value")).alias("v"))
hi = df.with_columns(pl.when(pl.col("value") < 0).then(pl.col("ceil")).otherwise(pl.col("value")).alias("v"))
print({"worst_case": lo["v"].mean(), "best_case": hi["v"].mean()})
```

**Recipe 3c — Complete-case vs. all-available.** Compare the estimate on rows with no
missingness against the estimate that uses every available cell.

**Interpretation.** Bounds that stay on one side of the null *support* the claim
robustly. Differential missingness lands as *reveals data/process issue*. A result
that flips between complete-case and bounded is *inconclusive* until the missingness
mechanism is understood.

**Pitfalls.** Suppressed cells rendered as zero (not as "suppressed") is a
correctness bug, not a modeling choice — see `interactive-artifact-qa.md`. Naive
mean-imputation understates uncertainty and can manufacture significance.

---

## Family 4 — Measurement & Coding (operationalization, proxy validity)

**Validity:** construct.

**Definition.** The variable may not measure the construct the claim is about.
Recoding thresholds, top/bottom coding, unit conversions, and proxy choices all move
results. "Low-income" via FRPL, via MEPS modeled poverty, and via SAIPE district
poverty are three different constructs.

**When to use.** Any derived, recoded, or proxy variable; any categorical cutpoint;
when the researcher says "the variable might not mean what we think."

**Recipe 4a — Alternate operationalization.** Rebuild the key variable a second
defensible way and re-run the headline.

```python
# INTENT: does the finding survive a different-but-defensible operationalization?
# REASONING: construct validity — if the result is proxy-specific, say so explicitly
# ASSUMES: both proxies are pre-registered in the ledger, not chosen after seeing results
df = df.with_columns(
    (pl.col("frpl_share") > 0.5).alias("low_income_frpl"),
    (pl.col("meps_poverty") > 0.2).alias("low_income_meps"),
)
for var in ["low_income_frpl", "low_income_meps"]:
    print(var, df.group_by(var).agg(pl.col("outcome").mean()))
```

**Recipe 4b — Threshold/coding stress.** Sweep the cutpoint across a defensible range
and plot the estimate — a knife-edge dependence on one arbitrary threshold is a red
flag.

**Recipe 4c — Proxy-validity cross-check.** Correlate the proxy against a known
gold-standard subset where both exist.

**Interpretation.** Stability across operationalizations *supports* construct
validity. Sensitivity to an arbitrary cutpoint *weakens* the claim or, at minimum,
scopes it to that definition. A proxy that diverges from its gold standard is
*reveals data/process issue*.

**Pitfalls.** Reporting only the operationalization that "works" is textbook forking
paths (https://atticusli.com/replication-crisis/garden-of-forking-paths/). Unit-
conversion errors (per-pupil vs. total dollars) masquerade as substantive effects.

---

## Family 5 — Temporal (windows, cohort vs. period, lag, event alignment)

**Validity:** internal.

**Definition.** The result may be an artifact of the time window, the choice between
cohort and period framing, a lag structure, or misaligned event timing.

**When to use.** Any trend, any before/after comparison, any analysis with a policy
date or event; when the researcher worries "it might be a fluke of the years we
picked."

**Recipe 5a — Window sensitivity.** Slide the start/end of the analysis window and
plot the estimate.

```python
# INTENT: does the trend/effect persist as the window boundaries move?
# REASONING: an effect that exists only for one arbitrary window is fragile
rows = []
for start in range(2012, 2018):
    sub = df.filter(pl.col("year") >= start)
    slope = np.polyfit(sub["year"].to_numpy(), sub["outcome"].to_numpy(), 1)[0]
    rows.append({"start_year": start, "slope": slope})
print(pl.DataFrame(rows))
```

**Recipe 5b — Cohort vs. period.** Recompute grouping by birth/entry cohort versus
calendar period; age–period–cohort confounds reverse conclusions.

**Recipe 5c — Lag/event-alignment placebo.** Shift the event date to a year where no
effect should exist and confirm the "effect" disappears (links to Family 7).

**Interpretation.** Persistence across windows *supports*; a single-window effect
*weakens*. An "effect" that survives a placebo shift is a *reveals data/process
issue* (the estimator is picking up something time-invariant).

**Pitfalls.** COVID-affected years (e.g., CRDC 2020-21) as ordinary panel points
distort trends. Endpoint sensitivity is easy to hide by reporting one window — sweep
it.

---

## Family 6 — Model / Specification (spec grids, influence, FE/SE choices)

**Validity:** statistical-conclusion, internal.

**Definition.** The result may not survive reasonable alternative specifications —
covariate sets, fixed-effect structures, functional forms, variance estimators, or
influential observations.

**When to use.** Any regression-based claim; whenever there were defensible modeling
forks; when the researcher worries "would it hold under a different model?"

**Recipe 6a — Specification curve (executable).** The canonical multiverse summary
(Steegen et al. 2016 —
https://sites.stat.columbia.edu/gelman/research/published/multiverse_published.pdf ;
Simonsohn/Simmons/Nelson spec-curve;
https://statmodeling.stat.columbia.edu/2024/11/12/specification-curve-analysis-and-the-multiverse/).
No package is installed — build the loop by hand; this is standard DAAF idiom.

```python
# INTENT: enumerate all defensible specs, refit, collect the focal coefficient
# REASONING: a spec curve shows how much the estimate depends on analytic choices
# ASSUMES: the spec grid is pre-committed in the ledger before running (anti-fishing)
import itertools, pyfixest as pf
controls = [["x1"], ["x1", "x2"], ["x1", "x2", "x3"]]
fe = ["", "| state", "| state + year"]
rows = []
for c, f in itertools.product(controls, fe):
    formula = f"y ~ treat + {' + '.join(c)} {f}"
    m = pf.feols(formula, data=df.to_pandas())
    rows.append({"spec": formula, "coef": m.coef()["treat"], "se": m.se()["treat"]})
curve = pl.DataFrame(rows).sort("coef")
# INTENT: summarize per interpretation-and-evidence.md contract (median, MAD, q25/q75, share same-sign & sig)
print(curve.select(pl.col("coef").median(), pl.col("coef").quantile(0.25), pl.col("coef").quantile(0.75)))
```

Summarize and plot the ranked curve + choice panel per the spec-curve contract in
`interpretation-and-evidence.md`. If the grid is large, note the multiplicity
caution (minP-type adjustment; https://arxiv.org/pdf/2401.11537) — the curve
describes fragility, it does not license cherry-picking the significant end.

**Recipe 6b — Influence diagnostics.** Refit dropping high-leverage/high-influence
observations (Cook's distance) and check the estimate's stability.

```python
# INTENT: is the result driven by a handful of influential rows?
import statsmodels.formula.api as smf
m = smf.ols("y ~ treat + x1 + x2", data=df.to_pandas()).fit()
infl = m.get_influence().cooks_distance[0]
keep = infl < (4 / len(infl))  # common 4/n rule of thumb
m2 = smf.ols("y ~ treat + x1 + x2", data=df.to_pandas()[keep]).fit()
print({"full": m.params["treat"], "trimmed": m2.params["treat"]})
```

**Recipe 6c — SE/cluster choice.** Report the coefficient under classical, robust,
and clustered SEs; significance that depends on the least-conservative SE is fragile.

**Interpretation.** A tight spec curve centered away from the null *supports* the
claim strongly. A curve straddling the null is *does not discriminate* / *weakens*.
A result driven by a few influential points is *reveals data/process issue*.

**Pitfalls.** Presenting the modal spec as "the" result hides the curve. Adding
specs until significance appears is fishing — the grid is pre-committed.

---

## Family 7 — Placebo & Falsification (negative outcomes/exposures, timing)

**Validity:** internal.

**Definition.** A valid causal design should *fail* where it ought to: a placebo
outcome (unaffected by treatment) should be null, a placebo exposure/timing should
show no effect, an impossible relationship should not appear.

**When to use.** Any causal or quasi-experimental claim where a credible negative
control exists; when the researcher worries "it might be spurious."

**Recipe 7a — Placebo outcome.** Run the identical design on an outcome the mechanism
cannot affect.

```python
# INTENT: the design should produce a null on an outcome treatment cannot move
# REASONING: a non-null placebo reveals confounding or a specification artifact
# ASSUMES: `placebo_outcome` is genuinely outside the causal mechanism
import pyfixest as pf
real = pf.feols("outcome ~ treat | unit + time", data=df.to_pandas())
placebo = pf.feols("placebo_outcome ~ treat | unit + time", data=df.to_pandas())
print({"real_effect": real.coef()["treat"], "placebo_effect": placebo.coef()["treat"]})
# INTENT: ledger pre-commit — "supports" requires real≠0 AND placebo≈0
```

**Recipe 7b — Placebo timing / in-time placebo.** Assign a fake treatment date before
the real one; an effect at the fake date impeaches parallel-trends-type assumptions.

**Recipe 7c — Permutation / randomization inference.** Shuffle the treatment label
many times to build a null distribution for the estimate.

```python
# INTENT: where does the real estimate sit in a label-shuffled null distribution?
rng = np.random.default_rng(20260806)  # seed for reproducibility
null = []
for _ in range(1000):
    perm = df.with_columns(pl.Series("treat", rng.permutation(df["treat"].to_numpy())))
    null.append(pf.feols("outcome ~ treat | unit + time", data=perm.to_pandas()).coef()["treat"])
p_perm = np.mean(np.abs(null) >= abs(real.coef()["treat"]))
print({"permutation_p": p_perm})
```

**Interpretation.** A null placebo + non-null real effect *supports* and weakens the
"spurious" alternative. A non-null placebo *weakens* the causal claim strongly. A
real estimate deep in the tail of the permutation null *supports*.

**Pitfalls.** A placebo outcome that is actually on the causal path gives false
reassurance. Set and record the RNG seed — an unseeded permutation test is not
reproducible.

---

## Family 8 — Visual-Framing (counts vs. rates, scales, uncertainty shown/hidden)

**Validity:** statistical-conclusion, construct.

**Definition.** The *chart*, not the data, may be creating the impression: counts vs.
rates, truncated axes, free vs. common scales, distribution vs. mean, uncertainty
shown vs. hidden, chart-form choice.

**When to use.** Any figure that carries a claim; when the researcher worries "the
picture might be doing the persuading."

**Recipe 8a — Reframe grid.** Render the same data as counts *and* rates, truncated
*and* zero-based axis, with *and* without CIs; put them side by side.

```python
# INTENT: does the visual impression survive defensible reframings?
# REASONING: a claim that only reads as dramatic on a truncated axis is a framing artifact
from plotnine import ggplot, aes, geom_col, geom_errorbar, scale_y_continuous
base = ggplot(agg.to_pandas(), aes("group", "rate"))
zero_based = base + geom_col() + scale_y_continuous(limits=(0, None))
with_ci = base + geom_col() + geom_errorbar(aes(ymin="lo", ymax="hi"))
# INTENT: save both; the ledger records which framing the claim relies on
```

**Recipe 8b — Lineup protocol (confirmatory visual test).** Embed the real plot among
null-generated decoys; if the researcher (or a naive viewer) can pick the real one,
the pattern is unlikely to be chance (Wickham, Cook, Hofmann & Buja 2010 —
https://vita.had.co.nz/papers/inference-infovis.pdf ; residual application:
https://arxiv.org/pdf/2308.05964). This converts an eyeballed pattern into a
calibrated test.

```python
# INTENT: generate m-1 null panels + 1 real panel in random position
# REASONING: identifying the real panel among nulls is a valid low-alpha visual test
rng = np.random.default_rng(20260806)
real_pos = rng.integers(0, 20)
panels = []
for i in range(20):
    d = df if i == real_pos else df.with_columns(pl.Series("y", rng.permutation(df["y"].to_numpy())))
    panels.append(d.with_columns(pl.lit(i).alias("panel")))
# INTENT: render 20 faceted panels; record real_pos in the ledger, reveal only after the guess
```

**Interpretation.** Impression stable across reframings *supports*; an impression that
needs a truncated axis or hidden uncertainty *weakens*. Correctly picking the real
lineup panel *supports* the pattern claim; failing to *weakens* it.

**Pitfalls.** Visual predictive/lineup checks mislead when the null model's implicit
assumptions don't match the data (https://arxiv.org/pdf/2503.01509) — state the null
model. Interactive dashboards multiply framing risk; they are exploratory interfaces,
not evidence (`interactive-artifact-qa.md`).

---

## Family 9 — Data-Lineage & Implementation (reconciliation, join-loss, duplicate keys)

**Validity:** internal (data-process).

**Definition.** The number may be *built wrong* — a bad join, a duplicate key, a lost
subset, a reconciliation that doesn't tie out — independent of any substantive
question. This is the family that most directly buys back line-by-line review: a
chunk whose output reconciles, re-derives, and joins losslessly does not need its
code read; a chunk that fails one of these does. **This is the mission's workhorse,
so it carries the richest recipe set.**

**When to use.** Always, at least once, on any headline number the researcher would
otherwise feel obligated to trace by hand. Especially after any join, aggregation,
dedup, or multi-source merge.

**Recipe 9a — Independent re-derivation.** Recompute the headline number by a
deliberately *different* path than the pipeline used, and assert equality.

```python
# INTENT: reproduce the headline from raw inputs via an independent route
# REASONING: agreement between two independent derivations is strong output-level evidence
#            that the pipeline chunk is correct WITHOUT reading its code line by line
# ASSUMES: raw source is the same immutable Parquet the pipeline consumed
raw = pl.read_parquet(f"{DATA_DIR}/raw/source.parquet")
independent = raw.filter(pl.col("year") == 2022).group_by("state").agg(pl.col("enroll").sum())
pipeline = pl.read_parquet(f"{DATA_DIR}/processed/state_enroll_2022.parquet")
joined = independent.join(pipeline, on="state", suffix="_pipe")
mism = joined.filter((pl.col("enroll") - pl.col("enroll_pipe")).abs() > 1)
assert mism.height == 0, f"{mism.height} states disagree between independent and pipeline derivation"
# INTENT: a clean assert here retires the need to review the pipeline's aggregation code
```

**Recipe 9b — Reconciliation totals.** Confirm parts sum to the whole and cross-source
totals tie out against an external published figure.

```python
# INTENT: do disaggregated cells reconcile to the reported grand total?
# REASONING: a broken filter or double-count shows up as a reconciliation gap
by_group = df.group_by("group").agg(pl.col("n").sum())
assert abs(by_group["n"].sum() - reported_total) <= tolerance, "subgroup sum != reported total"
# INTENT: also tie to an external anchor (e.g. NCES published national enrollment) where one exists
```

**Recipe 9c — Join-loss view.** Anti-join both sides of every merge to surface dropped
keys before they silently bias the result.

```python
# INTENT: quantify and characterize rows lost on each side of a join
# REASONING: an inner join that drops a nonrandom subset is a hidden sample-selection step
# ASSUMES: left = analysis frame, right = lookup being merged
left_only = left.join(right, on="id", how="anti")
right_only = right.join(left, on="id", how="anti")
print({"left_rows": left.height, "unmatched_left": left_only.height,
       "unmatched_right": right_only.height})
# INTENT: profile the unmatched set — are the dropped units systematically different?
print(left_only.group_by("sector").len())
assert left_only.height / left.height < 0.01, "join drops >1% of analysis rows; investigate before trusting"
```

**Recipe 9d — Duplicate-key stress test.** Assert the grain: keys that should be
unique are unique, and a join can't fan out rows.

```python
# INTENT: confirm the primary key is truly unique at the stated grain
# REASONING: a duplicated key silently multiplies rows on join and inflates sums
dups = df.group_by(["unitid", "year"]).len().filter(pl.col("len") > 1)
assert dups.height == 0, f"{dups.height} duplicate (unitid, year) keys — grain assumption violated"
# INTENT: post-join row-count invariant — the merge must not increase left row count
assert merged.height == left.height, "join fanned out rows; right side is not unique on the key"
```

**Recipe 9e — Source-to-report claim tracing.** For a specific sentence in the report,
walk the provenance chain back to the immutable script and raw cell that produced it,
and confirm the quoted number is the one the script emitted.

```python
# INTENT: verify the exact number in report claim C matches the script's captured output
# REASONING: numbers drift between analysis and prose (stale copy-paste, rounding)
# ASSUMES: the generating script's execution log is the source of truth (DAAF audit trail)
emitted = pl.read_parquet(f"{DATA_DIR}/processed/headline.parquet")["value"][0]
claimed = 0.124  # the number written in the report sentence under audit
assert abs(emitted - round(claimed, 3)) < 5e-4, "report claim does not match generating script output"
```

**Interpretation.** Clean re-derivation, reconciliation, lossless joins, and unique
keys together let a chunk pass *behaviorally* — record it as covered in the ledger
and reserve line-level review for chunks that *fail* one of these. A failure lands as
*reveals data/process issue* and is the trigger to escalate to granular code review
of that chunk specifically.

**Pitfalls.** Reconciling to a total that itself came from the same buggy step is
circular — the anchor must be *independent* (a different derivation path or an
external published figure). "Within rounding" tolerances that are too loose hide real
discrepancies; set the tolerance to the reporting precision. Provenance reuses DAAF's
existing script-versioning + IAT substrate — do not build a parallel provenance
system (see `agent_reference/TRIANGULATION_PROTOCOL.md`).

---

## Family 10 — Stakeholder-Perspective (skeptical reviewer, domain expert, decision-maker)

**Validity:** external (hypothesis-generating).

**Definition.** What a skeptical peer reviewer, a domain expert, an affected
community, or an operational decision-maker would ask. These questions *generate
hypotheses* to route into families 1–12; they are **not themselves evidence**.

**When to use.** At intake, to surface doubts the researcher hasn't voiced; whenever
the analysis will face an external audience.

**Recipe (not a script).** Role-play each stakeholder and enumerate their sharpest
question, then map each to a family and a discriminating test:

| Stakeholder | Characteristic question | Routes to |
|-------------|------------------------|-----------|
| Skeptical reviewer | "Isn't this just composition?" | Family 2 |
| Domain expert | "Your proxy misses charter schools." | Family 4 / Family 1 |
| Decision-maker | "Does it hold for the district I run?" | Family 12 |
| Affected community | "Whose data is suppressed here?" | Family 3 |

**Interpretation.** A stakeholder question, once tested, resolves to one of the six
statuses via its target family. Left untested, it is at most *generates new
hypothesis* — never report a stakeholder's concern as if answering it were evidence.

**Pitfalls.** The core error is treating the *articulation* of a concern as its
*resolution*. A vivid reviewer objection with no discriminating observable is a worry,
not a test (SKILL.md loop step 4).

---

## Family 11 — Identification-Assumption (sensitivity analysis for untestable premises)

**Validity:** internal.

**Definition.** Causal claims rest on assumptions that are *untestable from the data*
(no unobserved confounding, parallel trends, no manipulation, exclusion). This family
challenges them with **named, computable sensitivity statistics** — turning "challenge
the assumption" into an auditable number and threshold.

**When to use.** Any causal estimate whose credibility rests on an identification
assumption; when the researcher asks "how strong would the violation have to be to
overturn this?"

**Routing (formulas, confidence labels, and executable/flag-and-describe status all
live in `sensitivity-statistics.md` — this file does not duplicate them):**

| Assumption at risk | Statistic | Status in container |
|--------------------|-----------|---------------------|
| No unobserved confounding (regression) | Cinelli–Hazlett robustness value; E-value | Executable (closed-form) |
| No unobserved confounding (matched design) | Rosenbaum Γ | Flag-and-describe |
| Proportional selection on observ./unobserv. | Oster δ | Executable (with δ≠1 caveat) |
| Parallel trends (DiD) | Event-study + honest-DiD bounds | Event-study executable; honest-DiD flag-and-describe |
| No manipulation (RD) | McCrary/Cattaneo density | Flag-and-describe; `rdrobust` point estimate executable |
| Exclusion restriction (IV) | Overid / placebo falsification (never a "test" of exclusion) | Executable |

**Interpretation.** A robustness value or E-value larger than any plausible
confounder's strength *supports* the claim; a small one *weakens* it. Report the
number *and* the benchmark it is compared against — a bare statistic is not evidence.

**Pitfalls.** Oster δ=1 is *not* an automatic benchmark (δ can converge to any real
number absent an exogeneity assumption; https://arxiv.org/html/2504.21106). Naive DiD
pre-trend tests are low-powered and must not be read as "proof" of parallel trends
(https://arxiv.org/pdf/2510.26470). The IV exclusion restriction is untestable —
falsify via overidentification/placebo outcomes only
(https://mike-data-analysis.share.connect.posit.cloud/sec-quasi-experimental.html).
Full caveats: `sensitivity-statistics.md`.

---

## Family 12 — Generalizability / Transportability

**Validity:** external.

**Definition.** Whether the estimate transports beyond this sample, period, or
setting. Framed formally, generalization is a trial-participation / selection-into-
sample problem (Stuart; Pearl & Bareinboim; Degtiar & Rose 2021 —
https://arxiv.org/pdf/2102.11904 ;
https://projecteuclid.org/journals/statistical-science/volume-29/issue-4/External-Validity-From-Do-Calculus-to-Transportability-Across-Populations/10.1214/14-STS486.full).

**When to use.** Any claim intended to inform a population, period, or geography wider
than the estimation sample; when the researcher asks "does this hold elsewhere?"

**Recipe 12a — Sample-vs-target covariate comparison.** Compare the distribution of
effect-modifiers in the estimation sample against the target population.

```python
# INTENT: quantify how far the analysis sample is from the target on known modifiers
# REASONING: large covariate gaps on effect-modifiers cap external validity
# ASSUMES: `target` is a reference frame for the population the claim addresses
for col in ["pct_frpl", "urbanicity", "region"]:
    print(col, {"sample_mean": sample[col].mean(), "target_mean": target[col].mean()})
```

**Recipe 12b — Reweighting to the target.** Reweight the sample toward the target's
covariate profile (participation-propensity style) and re-estimate; a large shift
means the pooled estimate is sample-specific.

```python
# INTENT: does the estimate move when reweighted to the target population profile?
# REASONING: transportability — a stable reweighted estimate supports generalization
import statsmodels.formula.api as smf
# stack sample+target, model P(in-sample), form odds weights on the sample, re-estimate weighted
```

**Recipe 12c — Leave-one-group-out.** Re-estimate holding out each stratum (state,
sector) in turn; a claim that only holds with one group included does not generalize.

**Interpretation.** Stability under reweighting / leave-one-out *supports*
generalization; a large move *weakens* it or scopes the claim to the estimation
sample. Big covariate gaps with no reweighting are *inconclusive* on external
validity.

**Pitfalls.** Reweighting corrects for *observed* modifiers only — unobserved
modifiers remain a transport threat (state it). Extrapolating far outside the
sample's covariate support is unsupported regardless of reweighting.

---

## Cross-Family Notes

- **A worry without a discriminating observable is not yet a test** (SKILL.md loop
  step 4) — several families (especially 10) surface worries that must be routed to a
  family with a concrete observable before they count.
- **Pre-commit the design choice** (subgroup, denominator, threshold, spec grid,
  placebo outcome) in the ledger *before* running — every family above can be turned
  into a fishing expedition by choosing the variant that flatters the claim.
- **Record nulls and failures** with the same weight as confirmations; a coverage map
  that only shows supporting tests is a fishing expedition with good PR (SKILL.md
  Guardrails; `interpretation-and-evidence.md`).
- **Escalation to code review** is the *output* of Family 9 failures, not the default:
  the mission is to spend line-level attention only where a behavioral check failed.

## References

- Shadish, Cook & Campbell (2002), validity threat taxonomy — https://pmc.ncbi.nlm.nih.gov/articles/PMC6182849/ ; graphical catalog — https://journals.lww.com/epidem/Fulltext/2020/05000/A_Graphical_Catalog_of_Threats_to_Validity_.11.aspx
- Steegen, Tuerlinckx, Gelman & Vanpaemel (2016), Multiverse analysis — https://sites.stat.columbia.edu/gelman/research/published/multiverse_published.pdf
- Simonsohn, Simmons & Nelson, specification curve (overview) — https://statmodeling.stat.columbia.edu/2024/11/12/specification-curve-analysis-and-the-multiverse/
- minP multiplicity adjustment across specifications — https://arxiv.org/pdf/2401.11537
- Gelman & Loken (2013), Garden of Forking Paths — https://atticusli.com/replication-crisis/garden-of-forking-paths/
- Wickham, Cook, Hofmann & Buja (2010), Graphical Inference (lineup protocol) — https://vita.had.co.nz/papers/inference-infovis.pdf ; residual diagnostics application — https://arxiv.org/pdf/2308.05964
- Visual predictive checks, caution — https://arxiv.org/pdf/2503.01509
- Oster δ, benchmark caveat — https://arxiv.org/html/2504.21106
- DiD pre-trend testing, caution — https://arxiv.org/pdf/2510.26470
- RD McCrary density + covariate placebo — https://jack-fitzgerald.github.io/files/RDD_Equivalence.pdf
- IV exclusion untestable — https://mike-data-analysis.share.connect.posit.cloud/sec-quasi-experimental.html
- Degtiar & Rose (2021), generalizability/transportability review — https://arxiv.org/pdf/2102.11904 ; Pearl & Bareinboim, transportability — https://projecteuclid.org/journals/statistical-science/volume-29/issue-4/External-Validity-From-Do-Calculus-to-Transportability-Across-Populations/10.1214/14-STS486.full