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
by_name = {c["name"]: c for c in report["columns"]}  # also used by T2/T3 snippets

# --- Generate (T1 skeleton) ---
# INTENT: one correctly-typed placeholder column per reported column.
# ASSUMES: T1 carries no values; placeholders are intentionally non-informative.
assert report["report_version"] == "2.0", "Preserve legacy report; request corrected local rerun"
_dtype_default = {"integer": 0, "double": 0.0, "string": ""}
syn = pd.DataFrame({
    col["name"]: [_dtype_default.get(col["dtype"], None)] * n
    for col in report["columns"]
})
assert len(syn) == n, "row count must match profile"
```

## T2: marginals

First classify each `2.0` numeric shape; then draw eligible nonconstants independently over the available percentile grid and categoricals from supported proportions. Generate supported constants faithfully; withheld distributions use typed placeholders and explicit unobserved-fidelity status, while preserving their separately reported missingness. The grid may contain only quartiles. Legacy `1.0` reports are preserved, not relabeled: request a corrected local rerun before accepting this policy. For T1, value/missingness/relationship fidelity is NOT_APPLICABLE; structural/type/seed checks still apply.

```python
# --- Generate one numeric column (all 2.0 shapes; col is the selected column) ---
# INTENT: branch BEFORE using percentiles or missingness; absent targets stay unobserved.
# REASONING: a withheld distribution is not zero-valued evidence; constants are evidence.
# ASSUMES: DS-3 already validated the 2.0 schema and support counts.
assert report["report_version"] == "2.0", "Preserve legacy report; request a corrected local rerun"
num = col["numeric"]
if num.get("all_missing"):
    vals = np.full(n, np.nan)
    fidelity = "NOT_APPLICABLE: all-missing distribution"
elif num.get("withheld"):
    vals = np.zeros(n)  # typed scaffold, NOT an estimated value or distribution
    fidelity = "NOT_APPLICABLE: unobserved distribution (" + num["reason"] + ")"
elif num.get("constant"):
    vals = np.full(n, num["value"], dtype=float)
    fidelity = "AVAILABLE: supported constant target"
else:
    p = num["percentiles"]
    keys = ("p25", "p50", "p75") if num.get("small_n") else ("p1", "p5", "p10", "p25", "p50", "p75", "p90", "p95", "p99")
    probs = np.array([int(k[1:]) / 100 for k in keys])
    knots = np.array([p[k] for k in keys])
    vals = np.interp(rng.random(n), probs, knots)
    fidelity = "AVAILABLE: released percentile targets only"
# Pandas nullable integer dtype belongs to pd.array, NOT NumPy astype("Int64").
syn[col["name"]] = pd.array(np.round(vals), dtype="Int64") if col["dtype"] == "integer" else pd.array(vals, dtype="Float64")
print(col["name"], fidelity)  # record in generation log; AVAILABLE is not a QA PASS
# Independently apply the reported missingness recipe below, including to placeholders.
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
# Generate ALL marginals via the shape-aware T2 recipe first. Overwrite only eligible
# correlated marginals here; inject missingness AFTER this block.
by_name = {c["name"]: c for c in report["columns"]}
probs = np.array([.01, .05, .10, .25, .50, .75, .90, .95, .99])
block = report.get("relationships", {}).get("pearson")
if not block or not block["available"]:
    print("NOT_APPLICABLE: correlation target", block["reason"] if block else "not released")
else:
    # Constants, withheld, reduced, and all-missing columns are not matrix inputs.
    num_cols = block["columns"]
    assert all(set(by_name[c]["numeric"]) == {"n", "mean", "sd", "percentiles"} for c in num_cols)
    corr = np.array(block["matrix"], dtype=float)
    try:
        L = cholesky(corr)
    except LinAlgError:
        w, V = np.linalg.eigh((corr + corr.T) / 2)
        corr = V @ np.diag(np.clip(w, 1e-8, None)) @ V.T
        d = np.sqrt(np.diag(corr))
        corr = corr / np.outer(d, d)
        L = cholesky(corr)
        print("Generation approximation: correlation matrix projected to positive definite")
    z = rng.standard_normal((n, len(num_cols))) @ L.T
    for j, cname in enumerate(num_cols):
        pc = by_name[cname]["numeric"]["percentiles"]
        knots = np.array([pc[k] for k in ("p1","p5","p10","p25","p50","p75","p90","p95","p99")])
        vals = np.interp(norm.cdf(z[:, j]), probs, knots)
        syn[cname] = pd.array(np.round(vals), dtype="Int64") if by_name[cname]["dtype"] == "integer" else pd.array(vals, dtype="Float64")
```

### Named numeric~numeric relationships (`relationships.named`)

When the report carries an **available** named relationship, honor the linear structure directly: generate the predictor from its marginal, then `outcome = intercept + slope·predictor + N(0, residual SD)`, with the residual SD backed out of R².

```python
# --- Honor a named linear relationship (inline; no helper functions) ---
for rel in report.get("relationships", {}).get("named", []):
    if not rel["available"]:
        print("NOT_APPLICABLE: named relationship", rel["reason"])
        continue
    # Use generated marginals BEFORE missingness injection.
    x_pred = syn[rel["predictor"]].to_numpy(dtype=float)
    col = by_name[rel["outcome"]]
    sd_y = col["numeric"]["sd"]
    resid_sd = np.sqrt(max(1.0 - rel["ols"]["r_squared"], 0.0)) * sd_y
    vals = rel["ols"]["intercept"] + rel["ols"]["slope"] * x_pred + rng.normal(0, resid_sd, n)
    syn[rel["outcome"]] = pd.array(np.round(vals), dtype="Int64") if col["dtype"] == "integer" else pd.array(vals, dtype="Float64")
```

This reproduces the reported slope/intercept within tolerance. Categorical associations (Cramér's V) are weaker constraints; reproduce categoricals from marginals, and when a named categorical association matters, bias the linked draw. Exact joint reproduction is not the goal; structural validity for code development is.

## Categorical generation and `__OTHER__`

```python
# --- Generate a categorical column from suppressed level proportions ---
# INTENT: reproduce category frequencies; __OTHER__ stays an explicit aggregate bucket.
cat = col["categorical"]
levels = [l["value"] for l in cat["levels"]]
assert len(levels) == len(set(levels)), "Duplicate released category labels"
counts = np.array([l["count"] for l in cat["levels"]], dtype=float)
if levels:
    syn[col["name"]] = pd.array(rng.choice(levels, size=n, p=counts / counts.sum()), dtype="string")
else:
    syn[col["name"]] = pd.array([""] * n, dtype="string")
    print(col["name"], "NOT_APPLICABLE: unobserved categorical distribution")
```

Keep `__OTHER__` a literal synthetic aggregate — do not invent fake rare values. The profiler merges any original level literally named `__OTHER__` into this same pool and includes it in `n_levels_binned`; it is not separately recoverable. Require unique reported labels before drawing, so duplicate bucket entries cannot silently become separate probabilities. A fully-suppressed categorical column (`levels == []`) carries no marginal; synthesize a constant placeholder and note the column was withheld.

Check `available` before reading any cross-tab fields: `available:false` has only pair/n/reason, with no association fidelity target. When an available crosstab informs the draw, its `cells` array uses **`None`/`null` for suppressed cells**, never `0`: a `None` means "withheld/unknown" and must be skipped, while a real `0` means a genuine empty combination. A crosstab with `"collapsed": true` was fully suppressed — no association signal.

## Identifier columns with Faker

Identifier columns arrive value-free. Synthesize right-shaped fake values from the pattern flags and length stats — `Faker` is seedable and locale-aware for identifier-shaped fields (`synthetic-data-research.md` §1).

```python
# --- Synthesize identifier columns structurally with Faker ---
# INTENT: right-shaped-but-fake identifiers; REASONING: real values never crossed the boundary.
from faker import Faker
fake = Faker()
Faker.seed(20260715)                        # seed Faker for reproducibility

struct = col["string_structure"]
# Availability logging is independent of dtype: numeric identifiers also lose structure.
if struct.get("withheld"):
    print(col["name"], "NOT_APPLICABLE: unobserved identifier structure")
if col["dtype"] in ("integer", "double"):
    # Structure-only numeric ID: preserve type, not an invented numeric marginal.
    syn[col["name"]] = pd.array(np.arange(n), dtype="Int64" if col["dtype"] == "integer" else "Float64")
elif struct.get("withheld"):
    syn[col["name"]] = pd.array([""] * n, dtype="string")
else:
    flags = struct["pattern_flags"]
    if flags["email"]:
        vals = [f"user{i:06d}@example.invalid" for i in range(n)]
    elif flags["phone"]:
        vals = [fake.numerify("###-###-####") for _ in range(n)]
    else:
        vals = [fake.lexify("?" * round(struct["length_mean"])) for _ in range(n)]
    syn[col["name"]] = pd.array(vals, dtype="string")
```

Use reserved non-routable domains (`example.invalid`) for email-shaped scaffolds. Numeric IDs and random phone/string placeholders can coincidentally match real values; this workflow cannot certify noncollision without raw data. Do not interpret structural placeholders as observed identifiers.

## Free-text `role: "string"` columns

A `role: "string"` column (high-cardinality free text, non-identifier) arrives value-free — length stats + pattern flags only. Generate right-shaped fake strings from the length stats; never reconstruct real content.

```python
# --- Synthesize a free-text (role "string") column from length stats only ---
# INTENT: right-shaped fake strings; REASONING: no real values crossed the boundary.
struct = by_name[cname]["string_structure"]
if struct.get("withheld"):
    syn[cname] = pd.array([""] * n, dtype="string")
    print(cname, "NOT_APPLICABLE: unobserved string structure")
else:
    L = round(struct["length_mean"])
    syn[cname] = pd.array([fake.lexify("?" * L) for _ in range(n)], dtype="string")
```

If the `date` pattern flag is set, emit ISO-shaped fake dates instead so downstream date parsing still exercises.

## Missingness

```python
# --- Inject missingness at the reported rate ---
# ASSUMES: MCAR — the profile carries a rate, not a mechanism. Real missingness is often systematic;
#          a known fidelity limitation of profile-based synthesis (state it in the skill notice).
# Run only at T2+ and after shape-aware marginal/relationship generation.
# Keep this eligible target even for a withheld value summary; numerator rarity is not a veto.
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
