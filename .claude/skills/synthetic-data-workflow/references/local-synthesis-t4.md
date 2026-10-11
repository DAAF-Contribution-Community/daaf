# Local High-Fidelity Synthesis (T4)

The T4 tier: instead of DAAF generating synthetic data from a profile, the **user runs a data-fitted synthesizer locally**, inside their own environment, on the real data — and only the resulting synthetic *rows* cross the boundary. This buys higher fidelity than a profile can carry (real joint structure, learned conditional relationships, missingness patterns), while the real data and the fitted model never leave the user's machine. R (`synthpop`) is the flagship; Python (`SDV`) is the equivalent.

## Contents

- [When to escalate to T4](#when-to-escalate-to-t4)
- [The boundary rule for T4](#the-boundary-rule-for-t4)
- [synthpop (R, flagship)](#synthpop-r-flagship)
- [SDV (Python)](#sdv-python)
- [What crosses vs. what stays](#what-crosses-vs-what-stays)
- [Consuming T4 output on the DAAF side](#consuming-t4-output-on-the-daaf-side)
- [Why not synthcity / CTGAN by default](#why-not-synthcity--ctgan-by-default)

## When to escalate to T4

T1-T3 profile-based synthesis is structurally valid but marginals-and-pairwise at best. Escalate to T4 only when the code being developed needs synthetic data faithful enough to trust *intermediate diagnostics* — e.g., a multi-stage pipeline whose middle stages depend on realistic joint structure, or a model whose dry-run is only informative if higher-order relationships hold approximately. Escalate on demonstrated need, not by default: T4 requires the user to install and run a synthesizer, and it still does not lift the finalize-against-real-data doctrine (Census SIPP Synthetic Beta: even synthesized rows are "synthetic," not "gold standard" — a cell near 10 in synthetic may be smaller in real).

## The boundary rule for T4

Two things stay local, always:

1. **The real data** — obviously.
2. **The fitted model object** — less obvious but equally critical. A fitted synthesizer (a CART ensemble in synthpop, a fitted copula in SDV) can memorize and regenerate real records; the model artifact is as sensitive as the data itself. The templates write **only** the synthetic rows and a generation log, and are commented loudly that the real data and the fitted model must never be shared.

Only synthetic rows plus a generation log cross the boundary. **Parquet is the preferred exchange format**; CSV is a permitted fallback only when the local environment lacks `arrow`/`pyarrow`. A CSV hand-off is an **audited boundary exception** — see § Consuming T4 output for the mandatory convert-to-Parquet-and-manifest first action that keeps the in-container Parquet-only rule intact.

## synthpop (R, flagship)

`synthpop` (ESRC SYLLS project) is the agency-grade, light-dependency choice. `syn()` uses **CART by default** with conditional/sequential specification that respects logical constraints and missing-data patterns, and ships its own utility comparison (`compare.synds`) and disclosure-risk tooling (`synthetic-data-research.md` §2).

The `assets/synthesize_local_template.R` template (the user runs this locally):
- Reads the user's real data.
- Fits `syn()` (CART) with a recorded seed.
- Computes **one aggregate utility statistic** (overall `S_pMSE` via `utility.gen()`), length- and type-guarded, degrading to `unavailable` rather than to any fallback that would print a comparison.
- Does **not** capture `compare.synds()` output. `compare()` renders **per-variable, per-level and per-bin summaries of the REAL data** (marginal tables, frequency counts, histograms); writing that into a file labelled "shareable" would release real marginals at T4. The user may run `compare(syn_obj, real)` **interactively on their own machine** to judge fidelity — that output is real-data disclosure and must never be written to the log or shared.
- Writes **only** `synthetic` rows (Parquet preferred; CSV fallback if `arrow` is unavailable) + a generation log (seed, synthpop version, row count, and the single aggregate statistic).
- Refuses to run when any output target already exists (exclusive-creation preflight), so a rerun cannot silently overwrite a previously shared export.
- Loud header comments: the real data object and the fitted `syn` object must NOT be shared — only the synthetic output file.

```r
# INTENT: fit CART synthesis locally and emit ONLY synthetic rows.
# ASSUMES: this runs in the USER's environment on real data; nothing here touches DAAF.
library(synthpop)
set.seed(20260715L)
real <- read.csv(INPUT_PATH)                 # real data — never leaves this machine
syn_obj <- syn(real, seed = 20260715L)       # fitted model — never leaves this machine
gen <- utility.gen(syn_obj, real)            # ONE aggregate statistic; gen$S_pMSE is shareable
# NOT captured: compare(syn_obj, real) renders REAL-data per-level marginals. Run it
# interactively here if you want to judge fidelity; never write it to the log or share it.
write.csv(syn_obj$syn, OUTPUT_SYNTHETIC_PATH, row.names = FALSE)  # ONLY this file is shareable
```

## SDV (Python)

SDV `GaussianCopulaSynthesizer` is the Python equivalent — fast, interpretable, robust on small data (`synthetic-data-research.md` §2). The `assets/synthesize_local_template.py` template:
- Builds SDV `Metadata` from the real data, fits `GaussianCopulaSynthesizer`.
- Samples synthetic rows.
- Optionally runs SDV's `evaluate_quality` for an **aggregate** quality score only; per-column quality breakdowns carry real-data marginals and must not be written to the shareable log.
- Refuses to run under optimized Python (`-O`/`-OO`/`PYTHONOPTIMIZE`), because `assert`-based checks vanish there while the log would still report success.
- Writes **only** synthetic rows + a generation log; loud comments that real data and the fitted synthesizer must not be shared.

```python
# INTENT: fit a Gaussian copula locally and emit ONLY synthetic rows.
# ASSUMES: runs in the USER's environment on real data; nothing here touches DAAF.
from sdv.metadata import Metadata
from sdv.single_table import GaussianCopulaSynthesizer
import numpy as np
np.random.seed(20260715)
real = pd.read_csv(INPUT_PATH)               # real data — never leaves this machine
md = Metadata.detect_from_dataframe(real)
synth = GaussianCopulaSynthesizer(md)
synth.fit(real)                              # fitted model — never leaves this machine
synthetic = synth.sample(num_rows=len(real))
synthetic.to_csv(OUTPUT_SYNTHETIC_PATH, index=False)  # ONLY this file is shareable
```

`enforce_min_max_values` clamps to real ranges — note that this is a mild disclosure of the real min/max through the synthetic extremes; if the user's threat model cares, set it to `False`.

## What crosses vs. what stays

| Artifact | Crosses the boundary? |
|----------|------------------------|
| Synthetic rows (Parquet preferred; CSV = audited-exception fallback, converted to Parquet + manifested on receipt) | Yes |
| Generation log (seed, versions, row count, ONE aggregate utility statistic) | Yes |
| Per-variable / per-level utility or comparison output (`compare.synds()`, per-variable `utility.gen()`) | **Never** — it renders real-data marginals |
| Real data | **Never** |
| Fitted model object (`syn` object / fitted synthesizer) | **Never** |
| Real min/max (if `enforce_min_max_values=True` leaks them via extremes) | User's choice — flag it |

## Consuming T4 output on the DAAF side

T4 synthetic rows arrive as an actual dataset (not a profile). DAAF treats them like any synthetic dataset:
- **Boundary format (audited exception).** If the rows arrived as CSV (the fallback for a local environment without Arrow/PyArrow), the **first in-container action converts the CSV to Parquet and writes an exchange manifest** (a JSON sidecar named `{converted_filename}_exchange_manifest.json`) beside the converted file — original filename, source format, row/column counts, file hash, and conversion timestamp — after which all subsequent work uses only the converted Parquet. Parquet arrivals are imported directly. This is what keeps a boundary CSV consistent with the framework's in-container Parquet-only rule (Parquet-only, with one audited exception at the T4 local-exchange boundary).
- They still carry synthetic provenance — the skill records `synthetic-local-t4` (vs. `synthetic-profile-tN`) and the same scaffold-not-substitute notice. If the user could not supply a synthesis seed and the researcher authorized the missing-seed exception at the gate, the artifact is labeled a **"non-reproducible T4 synthetic artifact"** in both its provenance and the skill's Synthetic Data Notice (see `WORKFLOW_PHASE_DO_SYNTHETIC.md` § T4 Variant). The authorization is recorded in STATE.md and reaches CPS-GEN as the `seed_exception` config key, which surfaces as `[WARNING] seed_recorded: tier 4 import with no recorded seed — researcher-authorized non-reproducible T4 exception (authorization recorded in STATE)` (verdict `PASSED WITH WARNINGS`), never as a silent pass.
- **Synthetic-vs-profile validation depends on whether a profile report also crossed.** DS-5 at T4 is import plus validation, hosted by `scripts/synth_generate/01_import-synthetic.{py,R}`. **With a profile report** (the user also ran the profiler and the report cleared intake), the CPS-GEN block (routed from `validation-checks.md`) is embedded at the end of that script and runs in full — there is no lighter mode — with config `tier = 4` (the report's own `settings.tier` decides which blocks are expected) and `seed` taken from the user's generation log; QAS-C then reviews against the report. **Without a profile report**, CPS-GEN is not run: STATE records its row as `EXEMPT (T4, no profile report)`, and QAS-C validates against the user's declared metadata (row count, column set/types, declared marginals). Running CPS-GEN with no report path is not a way to get there — every report-dependent check is NOT VERIFIED and the verdict is FAILED.
- Either way, the disclosure-safety concern shifts to confirming the user shared only synthetic rows — spot-check for anything that looks like a memorized real record (exact-duplicate rows, implausibly unique identifier values) and flag if found.
- Findings are still never final on T4 data — re-run against real data inside the user's environment.

## Why not synthcity / CTGAN by default

`synthcity` (van der Schaar Lab) has a large generator arsenal (CTGAN, TVAE, PrivBayes, DP-GAN, PATEGAN, diffusion) but a heavy deep-learning dependency footprint and does **not handle missing data** (must impute first with HyperImpute) — a poor fit for a lightweight user-run local script (`synthetic-data-research.md` §2). CTGAN specifically risks training instability and mode collapse. Reserve these for users who explicitly want them and understand the tradeoffs; `synthpop` (R) is the far lighter, agency-proven default, and SDV `GaussianCopulaSynthesizer` (Python) is the light default on that side.
