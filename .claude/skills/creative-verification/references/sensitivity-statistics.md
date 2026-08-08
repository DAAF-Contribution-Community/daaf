# Sensitivity Statistics

The catalog of **named, computable sensitivity statistics** that turn "challenge the
identification assumption" (challenge Family 11) and "challenge external validity"
(Family 12) into an auditable number with a threshold, rather than prose. Each entry
states what the statistic quantifies, the formula where it is verified (with an
honest confidence label on that verification), an **executable** closed-form Python
recipe where the container supports one, or a **flag-and-describe** treatment where
no installed route exists, and the misuse caveats that most often invalidate the
number.

**Container reality (OBSERVED, `uv pip list` / `Rscript installed.packages()` snapshot,
2026-08-06).** DAAF prohibits runtime installs, so this catalog is split by what the
container can actually run. Installed and usable: `statsmodels` 0.14.6, `pyfixest`
0.60.0, `linearmodels` 7.0, `rdrobust` 1.3.0, `scipy`, `numpy`, `polars`, `plotnine`,
`marginaleffects`. **Not installed on either lane:** `sensemakr`/`PySensemakr`,
`evalue`/`EValue`, `specr`/`specification_curve`, `HonestDiD`/`diff-diff`, `rddensity`,
`rbounds`, `doubleml`, `econml`, `dowhy`. The R lane is equally unequipped for these
specific packages — a flag-and-describe method cannot be rescued by switching to R.
For any flag-and-describe method the remediation is a **Dockerfile addition** (user
additions block, fast rebuild) proposed to the maintainer, not a runtime install and
not a speculative reimplementation.

**Evidence-grading of the formulas below.** Per DAAF's evidence-graded reporting: a
formula labeled **primary-source-verified** was read in full text and quoted; one
labeled **secondary-corroborated** is a widely-reproduced result confirmed across
independent secondary sources but not quoted from the paywalled primary; one labeled
**inference / verify-before-relying** was not verified against primary text and must
be cross-checked before a result depends on it. These labels are load-bearing — carry
them into any report that uses the statistic.

---

## Quick Catalog

| Statistic | Challenges | Container status | Formula confidence |
|-----------|-----------|------------------|--------------------|
| E-value | Unobserved confounding (RR scale) | Executable (RR closed-form) | RR form secondary-corroborated; OR/HR/continuous verify-before-relying |
| Cinelli–Hazlett robustness value (RV_q) | Unobserved confounding (regression) | Executable (closed-form from t, df) | Primary-source-verified |
| Rosenbaum Γ | Hidden bias in matched designs | Flag-and-describe | N/A (no installed route) |
| Oster δ | Proportional selection on unobservables | Executable (needs 3 regressions + R²_max) | Formula standard; δ=1 benchmark caveat |
| DiD pre-trends / honest-DiD | Parallel trends | Event-study executable; honest-DiD flag-and-describe | Event-study standard; honest bounds flag |
| McCrary / Cattaneo density | No manipulation (RD) | Flag-and-describe (`rddensity` absent); `rdrobust` estimate executable | N/A |
| IV falsification | Exclusion restriction (untestable) | Executable (overid / placebo) | N/A — exclusion is never "tested" |
| Transportability checks | External validity | Executable (reweighting) | Method standard |

---

## E-value

**What it quantifies.** The minimum strength of association — on the risk-ratio scale —
that an unmeasured confounder would need with *both* the treatment and the outcome to
fully explain away an observed association (VanderWeele & Ding 2017 —
https://www.acpjournals.org/doi/10.7326/M17-1485 ; Stata/R `EValue` package —
https://journals.sagepub.com/doi/10.1177/1536867X20909696). A large E-value means only
a strong confounder could overturn the result; an E-value near 1 means a weak one
could.

**Formula.** For a risk ratio RR ≥ 1:

```
E = RR + sqrt(RR * (RR - 1))
```

For RR < 1, invert first (RR' = 1/RR) and apply the same form. Apply it to the point
estimate and, separately, to the confidence-limit nearer the null to get the E-value
for the bound.

> **Confidence: secondary-corroborated.** The RR closed form above is corroborated
> across multiple independent secondary sources but was **not** verified against the
> paywalled Annals of Internal Medicine primary text (the DOI returned HTTP 403). It
> is a well-known, widely-reproduced result. The OR / HR / continuous-outcome
> conversions (rare-outcome approximation, hazard-ratio and standardized-mean-
> difference transforms in VanderWeele & Ding 2017 Table 2) are **inference /
> verify-before-relying** — confirm each conversion constant against VanderWeele &
> Ding 2017 Table 2 before a result depends on it.

**Executable recipe (RR scale only).**

```python
# INTENT: compute the E-value for a risk-ratio estimate and its near-null CI bound
# REASONING: quantifies how strong an unmeasured confounder must be to nullify the finding
# ASSUMES: `rr` and `rr_bound` are risk ratios; for RR<1, invert before calling
# CONFIDENCE: RR closed form is secondary-corroborated (primary text paywalled)
import numpy as np
def _evalue(rr):
    rr = 1.0 / rr if rr < 1 else rr
    return rr + np.sqrt(rr * (rr - 1.0))
rr, rr_bound = 1.8, 1.3
print({"evalue_point": _evalue(rr), "evalue_bound": _evalue(rr_bound)})
# INTENT: interpret against a benchmark — is a confounder this strong plausible here?
```

(The one helper `def` above is illustrative for the formula only; in a real DAAF
script inline the two lines of arithmetic rather than defining a function, per the
flat-script code style.)

**Misuse caveats.** The E-value is a *threshold*, not a probability the result is
confounded — it says nothing about whether such a confounder exists, only how strong
it would have to be; always pair it with a substantive benchmark. Do **not** apply the
RR formula directly to an odds ratio or hazard ratio without the documented
conversion — treating an OR as an RR overstates the E-value for common outcomes.

---

## Cinelli–Hazlett Robustness Value (RV_q)

**What it quantifies.** In an omitted-variable-bias framework based on partial R², the
robustness value RV_q is the strength of confounding — as a share of residual
variance it would need to explain in *both* treatment and outcome — required to reduce
the estimated effect by 100·q percent (Cinelli & Hazlett 2020, *Making Sense of
Sensitivity* — https://carloscinelli.com/files/Cinelli%20and%20Hazlett%20(2020)%20-%20Making%20Sense%20of%20Sensitivity.pdf).
Unlike the E-value it makes no assumption on the functional form of treatment
assignment or the confounder's distribution, and it is computable from a standard
regression table.

**Formula (primary-source-verified — full-text read and quoted, Eq. 18).**

```
RV_q = (1/2) * ( sqrt(f_q**4 + 4 * f_q**2) - f_q**2 )
where f_q = q * |f_{Y~D|X}|  and  f_{Y~D|X} = |t| / sqrt(df)
```

Here `t` is the treatment coefficient's t-statistic and `df` its residual degrees of
freedom — nothing else is needed. The α-adjusted variant (Eq. 20) substitutes
`f_{q,α} = f_q − t*_{α,df−1}/sqrt(df−1)` for `f_q`.

**Executable recipe (closed-form from any statsmodels/pyfixest fit).**

```python
# INTENT: compute the Cinelli-Hazlett robustness value from a regression t-stat and df
# REASONING: RV_q says how strong confounding must be to shrink the effect by q*100%
# ASSUMES: model is a fitted OLS with a treatment coefficient; q=1 -> effect to zero
# CONFIDENCE: formula primary-source-verified (Cinelli & Hazlett 2020, Eq. 18, quoted)
import numpy as np, statsmodels.formula.api as smf
m = smf.ols("y ~ treat + x1 + x2", data=df.to_pandas()).fit()
t = m.tvalues["treat"]
dof = int(m.df_resid)
q = 1.0
f_q = q * abs(t) / np.sqrt(dof)
rv_q = 0.5 * (np.sqrt(f_q**4 + 4 * f_q**2) - f_q**2)
print({"t": t, "df": dof, "RV_q": rv_q})
# INTENT: RV_q near 1 => only near-total confounding overturns it (robust);
#         RV_q near 0 => trivial confounding suffices (fragile)
```

**Misuse caveats.** RV_q assumes the *same* partial-R² strength on treatment and
outcome (the "equal confounding" benchmark); a confounder much stronger on one side
can overturn the result at a lower RV — report benchmark bounds against observed
covariates (the paper's `bound_label` idea) rather than RV_q alone. It bounds bias
from omitted *confounders*, not from measurement error or selection.

---

## Rosenbaum Γ (gamma)

**What it quantifies.** In a matched observational design, the magnitude of departure
from random assignment — expressed as Γ, the maximum odds-ratio by which two matched
units could differ in treatment odds due to an unobserved covariate — at which the
result's significance is lost (https://academic.oup.com/biometrics/article/80/4/ujae106/7821107).
Γ = 1 is random assignment; the reported number is the smallest Γ that breaks
significance.

**Container status: flag-and-describe.** No `rbounds` (R) or Python equivalent is
installed, and implementing the Γ-sensitivity search over the Wilcoxon signed-rank
null distribution from scratch in `scipy` is algorithmically non-trivial and high-
authoring-risk. **Do not reimplement speculatively.** Describe the method, cite it,
report the matched design's vulnerability qualitatively, and recommend a Dockerfile
addition (`rbounds` via the R lane, or a vetted Python port) to the maintainer as a
follow-up.

> Absence note: the Python-package absence is inference from web search, not a PyPI-
> index probe; the in-container absence of `rbounds` on the R lane is OBSERVED via
> `installed.packages()`.

**Misuse caveats.** Γ is defined for *matched* designs — it is not a general-purpose
confounding bound for arbitrary regressions. A design significant only to Γ ≈ 1.1 is
extremely fragile to hidden bias; report the number, not just "significant."

---

## Oster δ (delta)

**What it quantifies.** Under proportional selection — the assumption that selection on
unobservables is proportional to selection on observables — δ is the degree of that
proportionality required to drive the treatment effect to zero, given an assumption
about the R² a hypothetical regression on *all* confounders would reach (R²_max).
δ > 1 means unobservables would have to matter *more* than observables to nullify the
effect (https://arxiv.org/html/2504.21106).

**Container status: executable** (three OLS fits + arithmetic; no special package).
Requires the uncontrolled and controlled coefficients/R² and a chosen R²_max
(Oster suggests R²_max = min(1.3·R²_controlled, 1) as one convention).

```python
# INTENT: compute Oster's delta for proportional selection
# REASONING: delta is how much stronger selection on unobservables must be to zero the effect
# ASSUMES: short = treatment-only model, full = treatment + controls; Rmax chosen explicitly
# CONFIDENCE: coefficient-movement formula is standard; the delta=1 BENCHMARK is NOT automatic
import statsmodels.formula.api as smf
short = smf.ols("y ~ treat", data=df.to_pandas()).fit()
full = smf.ols("y ~ treat + x1 + x2", data=df.to_pandas()).fit()
b0, r0 = short.params["treat"], short.rsquared
b1, r1 = full.params["treat"], full.rsquared
r_max = min(1.3 * r1, 1.0)
# Oster (2019) approximation for beta*=0:
delta = (b1 * (r1 - r0)) / ((b0 - b1) * (r_max - r1) - b1 * (r1 - r0) + 1e-12)
print({"beta_full": b1, "R2_full": r1, "R2_max": r_max, "delta_for_zero_effect": delta})
```

**Misuse caveats — the central trap.** δ = 1 is **not** an automatic "equal selection"
benchmark: absent an exogeneity assumption δ can converge to any real number, so
reporting "δ > 1, therefore robust" without justifying R²_max and the proportionality
premise is misuse (https://arxiv.org/html/2504.21106). Always report the R²_max used
and its rationale; show sensitivity of δ to R²_max. δ is a coefficient-stability
heuristic, not a proof of unconfoundedness.

---

## DiD Pre-Trends and Honest-DiD

**What it quantifies.** For difference-in-differences, the credibility of the parallel-
trends assumption. Two tools: an **event-study** plot of pre-period lead coefficients
(should be near zero), and **honest-DiD** (Rambachan & Roth) sensitivity bounds that
ask how large a post-period parallel-trends violation could be, disciplined by the
observed pre-trend, before the effect loses significance.

**Container status.** Event-study is **executable** via `pyfixest` (`sunab` /
interacted leads-and-lags, Sun–Abraham for staggered adoption). Honest-DiD is
**flag-and-describe**: `HonestDiD` (R) and `diff-diff` (Python) are both absent, and
the underlying optimization over convex restriction sets is non-trivial — do not
reimplement.

```python
# INTENT: estimate an event-study to inspect pre-trend leads before any DiD claim
# REASONING: near-zero, non-trending leads are necessary (not sufficient) for parallel trends
# ASSUMES: `rel_time` is event-time centered at -1; Sun-Abraham handles staggered timing
import pyfixest as pf
m = pf.feols("y ~ sunab(cohort, period) | unit + period", data=df.to_pandas())
m.iplot()  # INTENT: visual inspection of leads/lags; save the figure to the workspace
# FLAG-AND-DESCRIBE: for formal honest-DiD bounds (Rambachan-Roth), no installed route;
#   describe the pre-trend magnitude qualitatively, cite the method, recommend a Dockerfile add.
```

**Misuse caveats.** Naive pre-trend significance tests are **low-powered, biased, and
under-cover** — a non-significant pre-trend is *not* proof of parallel trends, and
conditioning the analysis on passing a pre-test induces its own distortions
(https://arxiv.org/pdf/2510.26470). Report the pre-trend as an event-study picture
plus honest-DiD-style reasoning, never as a pass/fail pre-test.

---

## McCrary / Cattaneo Density (RD manipulation)

**What it quantifies.** For regression discontinuity, whether units *manipulated* their
position around the cutoff — tested as a discontinuity in the density of the running
variable at the threshold (a placebo test on the running-variable density), followed
by covariate-as-placebo-outcome falsification
(https://jack-fitzgerald.github.io/files/RDD_Equivalence.pdf).

**Container status.** The formal density/manipulation test (`rddensity`,
Cattaneo/Jansson/Ma/Masini) is **not installed** (OBSERVED). `rdrobust` 1.3.0 **is**
installed but implements RD *point estimation*, not the density test. Two options: (a)
flag as missing tooling and recommend a `rddensity` Dockerfile addition; (b) a manual
local-polynomial density comparison in `scipy`/`statsmodels`, which is a materially
less rigorous approximation than Cattaneo's estimator — if used, label it as an
approximation, not the McCrary/Cattaneo test.

```python
# INTENT: RD point estimate is executable; the manipulation DENSITY test is not
# REASONING: separate what the container can do rigorously from what it cannot
from rdrobust import rdrobust
res = rdrobust(y=df["outcome"].to_numpy(), x=df["running"].to_numpy(), c=cutoff)
print(res)  # point estimation only
# FLAG-AND-DESCRIBE: density/manipulation test needs `rddensity` (absent). Recommend Dockerfile add;
#   optionally report a coarse histogram-density comparison as a labeled approximation, not the test.
```

**Misuse caveats.** A passed density test does not prove no manipulation — pair it with
covariate-placebo falsification. `rdrobust`'s `rdplot()` is reported to fail in 1.3.0 (read-only
array bug) — this claim is unverified in this container, so probe it before relying on
it, or plot RD binned means manually. Reporting a home-rolled density comparison
as "the McCrary test" overstates rigor.

---

## IV Falsification

**What it quantifies.** For instrumental variables, indirect evidence on the exclusion
restriction — which is **fundamentally untestable**. Available falsifications:
overidentification tests (with more instruments than endogenous regressors), placebo-
outcome checks (the instrument should not affect an outcome it can only reach through
the treatment), and balance of the instrument across pre-determined covariates
(https://mike-data-analysis.share.connect.posit.cloud/sec-quasi-experimental.html).

**Container status: executable** via `linearmodels` (`IV2SLS`, Sargan/Wooldridge overid
where overidentified).

```python
# INTENT: run falsification checks around an IV design (never a "test" of exclusion)
# REASONING: exclusion is untestable; overid + placebo outcomes are the only leverage
from linearmodels.iv import IV2SLS
m = IV2SLS.from_formula("y ~ 1 + [treat ~ z1 + z2] + x1", data=df.to_pandas()).fit()
print(m.sargan)  # overidentification test (only informative if overidentified AND instruments valid jointly)
# INTENT: placebo — instrument should NOT predict an outcome outside the causal channel
```

**Misuse caveats.** Never describe the exclusion restriction as "tested" — overid tests
assume at least one instrument is valid and can pass while all are invalid. A placebo
that runs through the treatment channel gives false comfort.

---

## Transportability Checks

**What it quantifies.** How far an estimate generalizes to a target population, framed
as a selection-into-sample / trial-participation problem: compare effect-modifier
distributions between sample and target, then reweight the sample to the target and
re-estimate (Degtiar & Rose 2021 — https://arxiv.org/pdf/2102.11904 ; Pearl &
Bareinboim selection-diagram transport —
https://projecteuclid.org/journals/statistical-science/volume-29/issue-4/External-Validity-From-Do-Calculus-to-Transportability-Across-Populations/10.1214/14-STS486.full).

**Container status: executable** (participation-propensity reweighting via
`statsmodels` + `polars`). Recipes 12a–12c in `challenge-families.md` implement the
sample-vs-target comparison, reweighting, and leave-one-group-out.

**Misuse caveats.** Reweighting corrects only for *observed* effect-modifiers;
unobserved modifiers remain a transport threat and must be stated. Extrapolation beyond
the sample's covariate support is unsupported regardless of reweighting.

---

## Reporting Sensitivity Statistics

Every sensitivity statistic reported must carry: (1) the number; (2) the **benchmark**
it is compared against (an observed covariate's strength, a plausible confounder, the
target population) — a bare statistic is not evidence; (3) its **formula-confidence
label** from this file (primary-source-verified / secondary-corroborated /
verify-before-relying); and (4) for flag-and-describe methods, an explicit statement
that the container could not compute it and the Dockerfile-addition path. Per DAAF's
evidence-graded reporting, a sensitivity result is *observed* only when the generating
script and its output are quoted or linked (`interpretation-and-evidence.md`).

## References

- VanderWeele & Ding (2017), E-value — https://www.acpjournals.org/doi/10.7326/M17-1485 ; `EValue` package — https://journals.sagepub.com/doi/10.1177/1536867X20909696
- Cinelli & Hazlett (2020), *Making Sense of Sensitivity* (robustness value) — https://carloscinelli.com/files/Cinelli%20and%20Hazlett%20(2020)%20-%20Making%20Sense%20of%20Sensitivity.pdf
- Rosenbaum bounds (Γ) — https://academic.oup.com/biometrics/article/80/4/ujae106/7821107
- Oster δ, benchmark caveat — https://arxiv.org/html/2504.21106
- DiD pre-trend testing, caution — https://arxiv.org/pdf/2510.26470
- RD manipulation (McCrary/Cattaneo) + covariate placebo — https://jack-fitzgerald.github.io/files/RDD_Equivalence.pdf
- IV exclusion untestable, falsification only — https://mike-data-analysis.share.connect.posit.cloud/sec-quasi-experimental.html
- Degtiar & Rose (2021), generalizability/transportability review — https://arxiv.org/pdf/2102.11904 ; Pearl & Bareinboim transportability — https://projecteuclid.org/journals/statistical-science/volume-29/issue-4/External-Validity-From-Do-Calculus-to-Transportability-Across-Populations/10.1214/14-STS486.full