# Generation Patterns — Python

Python equivalents of the R generation patterns (`generation-patterns-r.md` is the flagship — read it first for the full rationale). This constructs a seeded synthetic dataset *from a profile report alone* using hand-written NumPy/SciPy Gaussian-copula code plus `Faker` for identifier-shaped columns. Input is the returned JSON report (`profiling-script-spec.md`), never real data.

## Contents

- [Why not SDV here](#why-not-sdv-here)
- [The generation recipe](#the-generation-recipe)
- [T1: schema-only skeleton](#t1-schema-only-skeleton)
- [T2: marginals](#t2-marginals)
- [T3: relationships via copula](#t3-relationships-via-copula)
- [Categorical generation and __OTHER__](#categorical-generation-and-__other__)
- [Identifier columns with Faker](#identifier-columns-with-faker)
- [Missingness](#missingness)
- [Seeding and output](#seeding-and-output)
- [Caveats](#caveats)

## Why not SDV here

SDV's synthesizers `fit()` on real rows — DAAF never has them (`synthetic-data-research.md` §1). For profile-only generation on the DAAF side of the boundary, use plain NumPy/SciPy: a Gaussian copula is a few lines and needs only a correlation matrix and marginal quantiles, both of which the report provides. SDV `GaussianCopulaSynthesizer` belongs to the T4 *local* path (`local-synthesis-t4.md`), run by the user on real data inside their environment.

## The generation recipe

Same seven steps as the R path: read report → draw correlated normals (T3) or independent uniforms (T2) → map each margin to its target via the percentile grid → draw categoricals from suppressed proportions → synthesize identifiers structurally → inject missingness at the reported rate → validate and write seeded parquet to `data/synthetic/`.

## T1: schema-only skeleton

```python
# --- Config ---
import json
import numpy as np
import pandas as pd

rng = np.random.default_rng(20260715)  # INTENT: seeded reproducible synthesis

with open("clients_2025_profile_report.json") as f:
    report = json.load(f)
n = report["dataset"]["row_count"]

# --- Generate (T1 skeleton) ---
# INTENT: one correctly-typed placeholder column per reported column.
# ASSUMES: T1 carries no values; placeholders are intentionally non-informative.
_dtype_default = {"integer": 0, "double": 0.0, "string": ""}
syn = pd.DataFrame({
    col["name"]: [_dtype_default.get(col["dtype"], None)] * n
    for col in report["columns"]
})
assert len(syn) == n, "row count must match profile"
```

## T2: marginals

Draw each numeric independently by inverse-transform sampling over the reported percentile grid; draw each categorical from its (suppressed) proportions.

```python
# --- Generate one numeric column from reported percentiles (T2) ---
# INTENT: reproduce marginal shape via the percentile grid as an empirical quantile function.
# REASONING: min/max are withheld at T2+; percentiles are the disclosure-safe shape descriptor.
p = col["numeric"]["percentiles"]
probs = np.array([.01, .05, .10, .25, .50, .75, .90, .95, .99])
knots = np.array([p["p1"], p["p5"], p["p10"], p["p25"], p["p50"],
                  p["p75"], p["p90"], p["p95"], p["p99"]])
u = rng.random(n)
vals = np.interp(u, probs, knots)          # inverse-transform via linear interpolation
if col["dtype"] == "integer":
    vals = np.round(vals).astype("Int64")
syn[col["name"]] = vals
```

## T3: relationships via copula

Draw correlated standard normals with the reported Pearson matrix (a Gaussian copula), apply the probability integral transform, then map each margin to its target percentiles.

The snippet below is **illustrative — inline it** (DAAF's sequential style avoids helper functions like `percentiles_for`; pull the knots inline as shown):

```python
# --- Generate correlated numerics (T3) ---
from scipy.stats import norm
from numpy.linalg import cholesky, LinAlgError

# INTENT: draw standard-normal variates carrying the reported correlation, then map each
#         margin to its reported percentile shape via the PIT.
# ASSUMES: reported correlation matrix is valid; if not PSD, project before Cholesky (see caveats).
# NOTE: only FULL-summary numerics appear in the matrix (small_n / near_constant / all_missing
#       numerics are excluded), so every column here has a full p1..p99 grid.
by_name = {c["name"]: c for c in report["columns"]}
probs = np.array([.01, .05, .10, .25, .50, .75, .90, .95, .99])
num_cols = report["relationships"]["pearson"]["columns"]
corr = np.array(report["relationships"]["pearson"]["matrix"], dtype=float)
try:
    L = cholesky(corr)
except LinAlgError:
    # nearest-PD projection: symmetrize eigenvalues to non-negative, then re-Cholesky
    w, V = np.linalg.eigh((corr + corr.T) / 2)
    corr = V @ np.diag(np.clip(w, 1e-8, None)) @ V.T
    d = np.sqrt(np.diag(corr))
    corr = corr / np.outer(d, d)           # renormalize to unit diagonal
    L = cholesky(corr)

z = rng.standard_normal((n, len(num_cols))) @ L.T
for j, cname in enumerate(num_cols):
    u_j = norm.cdf(z[:, j])                 # probability integral transform to uniform
    pc = by_name[cname]["numeric"]["percentiles"]        # inline: pull that column's knots
    knots = np.array([pc[k] for k in ("p1","p5","p10","p25","p50","p75","p90","p95","p99")])
    syn[cname] = np.interp(u_j, probs, knots)
```

### Named numeric~numeric relationships (`relationships.named`)

When the report carries a named relationship, honor the linear structure directly: generate the predictor from its marginal, then `outcome = intercept + slope·predictor + N(0, residual SD)`, with the residual SD backed out of R².

```python
# --- Honor a named linear relationship (inline; no helper functions) ---
rel = report["relationships"]["named"][0]                # {outcome, predictor, ols:{...}}
# ... x_pred generated from the predictor's percentile marginal above ...
sd_y = by_name[rel["outcome"]]["numeric"]["sd"]
resid_sd = np.sqrt(max(1.0 - rel["ols"]["r_squared"], 0.0)) * sd_y   # residual SD from R^2
syn[rel["outcome"]] = rel["ols"]["intercept"] + rel["ols"]["slope"] * x_pred + rng.normal(0, resid_sd, n)
```

This reproduces the reported slope/intercept within tolerance. Categorical associations (Cramér's V) are weaker constraints; reproduce categoricals from marginals, and when a named categorical association matters, bias the linked draw. Exact joint reproduction is not the goal; structural validity for code development is.

## Categorical generation and `__OTHER__`

```python
# --- Generate a categorical column from suppressed level proportions ---
# INTENT: reproduce category frequencies; __OTHER__ stays an explicit aggregate bucket.
cat = col["categorical"]
levels = [l["value"] for l in cat["levels"]]
counts = np.array([l["count"] for l in cat["levels"]], dtype=float)
syn[col["name"]] = rng.choice(levels, size=n, p=counts / counts.sum())
```

Keep `__OTHER__` a literal synthetic level — do not invent fake rare values, which would fabricate structure the profile deliberately withheld. A fully-suppressed categorical column (`levels == []`) carries no marginal; synthesize a constant placeholder and note the column was withheld.

When a crosstab informs the draw, its `cells` array uses **`None`/`null` for suppressed cells**, never `0`: a `None` means "withheld/unknown" and must be skipped, while a real `0` means a genuine empty combination. A crosstab with `"collapsed": true` was fully suppressed — no association signal.

## Identifier columns with Faker

Identifier columns arrive value-free. Synthesize right-shaped fake values from the pattern flags and length stats — `Faker` is seedable and locale-aware for identifier-shaped fields (`synthetic-data-research.md` §1).

```python
# --- Synthesize identifier columns structurally with Faker ---
# INTENT: right-shaped-but-fake identifiers; REASONING: real values never crossed the boundary.
from faker import Faker
fake = Faker()
Faker.seed(20260715)                        # seed Faker for reproducibility

struct = col["string_structure"]
flags = struct["pattern_flags"]
if flags["email"]:
    syn[col["name"]] = [f"user{i:06d}@example.invalid" for i in range(n)]
elif flags["phone"]:
    syn[col["name"]] = [fake.numerify("###-###-####") for _ in range(n)]
else:
    L = round(struct["length_mean"])
    syn[col["name"]] = [fake.lexify("?" * L) for _ in range(n)]
```

Use reserved non-routable forms (`example.invalid`) so synthetic identifiers cannot collide with real ones.

## Free-text `role: "string"` columns

A `role: "string"` column (high-cardinality free text, non-identifier) arrives value-free — length stats + pattern flags only. Generate right-shaped fake strings from the length stats; never reconstruct real content.

```python
# --- Synthesize a free-text (role "string") column from length stats only ---
# INTENT: right-shaped fake strings; REASONING: no real values crossed the boundary.
L = round(by_name[cname]["string_structure"]["length_mean"])
syn[cname] = [fake.lexify("?" * L) for _ in range(n)]     # or rng-drawn alphanumerics
```

If the `date` pattern flag is set, emit ISO-shaped fake dates instead so downstream date parsing still exercises.

## Missingness

```python
# --- Inject missingness at the reported rate ---
# ASSUMES: MCAR — the profile carries a rate, not a mechanism. Real missingness is often systematic;
#          a known fidelity limitation of profile-based synthesis (state it in the skill notice).
rate = col["missing_rate"]
if rate > 0:
    idx = rng.choice(n, size=round(rate * n), replace=False)
    syn.loc[idx, col["name"]] = pd.NA
```

## Seeding and output

- **Always** construct the RNG with a recorded integer seed (`np.random.default_rng(seed)`) and seed Faker; record both in the generation log.
- Write parquet to `data/synthetic/` (create on first use), named per DAAF conventions.
- Generation log records: source report path + `report_version`, seed(s), tier, library versions, synthetic-vs-profile validation results.

```python
# --- Save ---
import os
os.makedirs("data/synthetic", exist_ok=True)
syn.to_parquet("data/synthetic/2026-07-15_clients_synthetic.parquet")
print(f"Seed: 20260715 | rows: {len(syn)} | tier: {report['settings']['tier']}")
```

## Caveats

- **Binary/low-cardinality correlation** recovers less faithfully through a Gaussian copula than continuous correlation — validate the achieved correlation and report the gap rather than forcing it (parallels the simstudy binary caveat).
- **Non-PSD correlation matrices** from suppressed profiles are handled by the eigenvalue-clip projection shown above; note it slightly perturbs the targets — the validation tolerance in `validation-checks.md` accounts for it.
- **Do not fabricate withheld structure.** Suppressed detail stays absent in the synthetic data; fabricated detail is worse than absence because it looks trustworthy.
- Polars is DAAF's default DataFrame library, but a small synthesis script that builds columns and writes one parquet is a reasonable pandas use; if the surrounding pipeline is Polars-native, convert at the write step (`pl.from_pandas(syn).write_parquet(...)`).
