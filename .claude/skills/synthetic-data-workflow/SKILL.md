---
name: synthetic-data-workflow
description: >-
  Privacy-preserving workflow for building synthetic datasets and data source skills when raw data must never enter the DAAF container. The user profiles their sensitive data locally with a disclosure-controlled script; only a summary profile report crosses the boundary; DAAF builds a synthetic dataset and skill from the report alone. Use whenever data is sensitive, proprietary, PII-bearing, HIPAA/FERPA-governed, held in a secure enclave, or the user says the data cannot leave their environment, they cannot upload it, or asks to profile it locally. Covers a four-tier disclosure ladder (T1 schema, T2 marginals, T3 relationships, T4 local high-fidelity synthesis), profile-only generation with simstudy (R) / NumPy-SciPy copulas (Python), and three-part QA (disclosure-safety, report consistency, synthetic-vs-profile validation). Not for synthetic control, the causal-inference method; for that see data-scientist. Synthetic data here is a code-development scaffold, not an analytic substitute.
metadata:
  audience: any-agent
  domain: research-methodology
---

# Synthetic Data Workflow

Privacy-preserving methodology for the case where raw data cannot enter the DAAF container. The user runs a disclosure-controlled profiling script on their own machine (inside their secure enclave, their laptop, wherever the sensitive data lives), reviews the human-readable summary it produces, and hands DAAF only that summary — a JSON profile report plus a plain-text review copy. DAAF then constructs a seeded synthetic dataset whose structure and (tier-permitting) marginals and relationships match the report, and authors a data source skill carrying explicit synthetic-provenance metadata. This skill provides the doctrine, the disclosure ladder, the profiling-report specification, the generation patterns (R-first, Python second), the local high-fidelity synthesis option, and the validation model. It is domain-agnostic infrastructure, not tied to any dataset. Triggers include sensitive/proprietary/PII data, secure enclaves, "data can't leave my environment," local profiling, and disclosure control. It is emphatically **not** the synthetic *control* method (a causal-inference estimator) — that lives in `data-scientist` (`references/causal-synth.md`).

## The Cardinal Doctrine — Read First

**Synthetic data is a code-development scaffold, not an analytic substitute.** A synthetic dataset built from a profile is *structurally* valid (right columns, right types, plausible-looking values, approximately right marginals) but *statistically* invalid (the joint distribution, conditional relationships, tail behavior, and missingness mechanism are approximations at best and fabrications at worst). Its purpose is to let DAAF and the user develop, debug, and dry-run analysis code against something shaped like the real data — never to produce findings.

This is settled practice at statistical agencies, not a DAAF invention:

- **CMS DE-SynPUF** (the Medicare synthetic claims file) is distributed explicitly "for development and testing," with the standing warning that "univariate statistics and regression coefficients ... will be biased" — it is for building pipelines, not drawing conclusions (research: `synthetic-data-research.md` §3).
- **OpenSAFELY dummy data** runs the *same analysis command* against fake data locally and real data inside the enclave; its dummy data is deliberately "cleaner than real" — it will not reproduce impossible values, real missingness, or true comorbidity structure (same source).

The operational consequence, which must be stated in every synthetic-data skill and every report built this way: **all findings must be finalized by re-running the vetted analysis code against the real data, inside the environment where the real data lives.** Results computed on synthetic data are provisional scaffolding and nothing more. When a user starts treating synthetic numbers as answers, stop and re-anchor them to this doctrine.

## When This Workflow Applies

```
Does raw data need to stay out of the container?
├─ No — user can bring the data in
│   └─ Use standard Data Onboarding (data-ingest profiles the real file in-container)
├─ Yes — sensitive / proprietary / PII / enclave / "can't leave my environment"
│   └─ THIS workflow:
│       1. DAAF prepares a disclosure-controlled profiling script (assets/ templates)
│       2. User runs it locally, reviews the .txt summary, returns the JSON report
│       3. DAAF validates the report, interprets it, generates synthetic data,
│          validates synthetic-vs-profile, and authors a synthetic-provenance skill
└─ User wants higher fidelity than a profile can carry
    └─ T4: user runs a local synthesizer (synthpop / SDV) inside their environment;
       only synthetic ROWS cross the boundary — never the real data or the fitted model
```

## Workflow Stages

This skill is the knowledge layer for a sub-workflow of Data Onboarding (stage wiring and orchestration live in the mode reference — dispatch 2). The stages the knowledge supports:

| Stage | Name | Who acts | This skill's role |
|-------|------|----------|-------------------|
| DS-1 | Script Preparation | DAAF (research-executor) | Configure a profiling-script template for the user's file/tier — see `profiling-script-spec.md`, `assets/profile_data_template.*` |
| DS-2 | User Local Run | **User (outside container)** | User edits the Config block, runs the script, reviews the `.txt` summary, returns the JSON |
| DS-3 | Report Intake & Validation | DAAF (code-reviewer) | Internal-consistency checks on the returned report — see `validation-checks.md` QA(b) |
| DS-4 | Interpretation | DAAF (data-ingest) | Read the report as a data dictionary; draft skill sections |
| DS-5 | Synthetic Generation & Validation | DAAF (research-executor + code-reviewer) | Generate seeded synthetic parquet, then validate synthetic-vs-profile — `generation-patterns-r.md` / `-python.md`, `validation-checks.md` QA(c) |
| — | rejoin DI-7 / DI-8 | DAAF | Author the skill with synthetic-provenance metadata (template wiring is dispatch 3) |

## The Four-Tier Disclosure Ladder

Each tier is a strict superset of the one below. The user picks the *lowest* tier that still lets the intended code development proceed — the Five Safes principle that "safe data" is a residual: remove only as much protection as the task requires you to keep (research §3). Full tier definitions, exactly what each emits and forbids, and the suppression rules are in `disclosure-tiers.md`.

| Tier | Name | What crosses the boundary | Never crosses |
|------|------|---------------------------|---------------|
| **T1** | Schema | Column names, dtypes, row count | Any values, any statistics |
| **T2** | Marginals (default) | Per-column: categorical levels with small-cell suppression (threshold default 5) + rare-category binning (a sub-threshold `__OTHER__` is folded further); numeric percentiles (p1..p99) + mean/SD — degraded to quartiles-only for small-n and value-withheld for near-constant columns; missingness rates; string-length stats + pattern flags | Raw min/max, example string values, small-cell counts, identifier values |
| **T3** | Relationships | Everything in T2 + Pearson/Spearman correlation matrices (numeric), Cramér's V (categorical pairs), named numeric~numeric summaries (OLS slope/intercept/R² + correlations), cross-tabs with primary + complementary cell suppression (suppressed cells emitted as `null`) | Same forbiddens as T2, plus unsuppressed cross-tab cells |
| **T4** | Local high-fidelity synthesis | Only synthetic *rows*, generated locally by synthpop (R) / SDV (Python) fit on the real data inside the user's environment | The real data AND the fitted model artifacts — both stay local |

**Suppression is ON by default at T2 and above.** Small cells (below the threshold) are suppressed; rare categorical levels are binned to `__OTHER__`; only percentiles are emitted (never raw min/max, an outlier-disclosure risk per the UK Data Service SDC handbook); example string values are never emitted; columns flagged as likely identifiers get structure-only treatment — dtype, uniqueness, length stats, never values. Identifier flagging is deliberately asymmetric: a high-uniqueness *string* column (a key like `client_id` or an email) is flagged, but a high-uniqueness *continuous numeric* is not flagged by uniqueness alone — it is a measurement, not a key, and percentiles-not-min/max already protect it; numerics are flagged only by an identifier-shaped name (`*_id`, `account`, `ssn`). Values matching email/phone/ID patterns flag a column regardless of type.

## Generation: Profile-Only vs Data-Fitted

The boundary that makes this workflow safe maps onto a clean library split (research §1-2):

- **Profile-only generators** build FROM declarations alone — marginal parameters plus a correlation matrix — with no microdata. These run *inside* DAAF on the returned report. **R (flagship): `simstudy`** (Gaussian copula via `genCorGen`/`addCorGen` from marginals + a correlation matrix; `fabricatr` noted for hierarchical/nested structure). **Python: hand-written NumPy/SciPy Gaussian-copula code** plus `Faker` for identifier-shaped columns. **SDV is deliberately NOT used for profile-only generation** — its synthesizers `fit()` on real rows, which DAAF never has.
- **Data-fitted synthesizers** learn from real microdata and therefore only ever run *locally, inside the user's environment* (T4). **R: `synthpop`** (CART synthesis, agency-grade, light dependencies — the flagship local option). **Python: SDV `GaussianCopulaSynthesizer`.** Only their synthetic output crosses the boundary.

Routing detail, worked examples, and caveats (e.g. simstudy recovers Poisson correlation more faithfully than binary; synthcity/CTGAN are heavier and reserved for users who explicitly want them) live in `generation-patterns-r.md`, `generation-patterns-python.md`, and `local-synthesis-t4.md`. **All generation is seeded for reproducibility**, and synthetic parquet is written to `data/synthetic/` within the research project.

## QA Model — Three Independent Checks

Because the real data never enters the container, the usual Data Onboarding QA move (recompute statistics against the source file) is impossible here. QA is restructured into three checks, specified in full in `validation-checks.md`:

1. **Disclosure-safety review of the OUTBOUND script (before the user runs it).** Does the configured profiling script emit anything the chosen tier forbids? This is the highest-stakes check — a leak here is irreversible once the report is shared. Reviewed by code-reviewer against the tier's forbidden-emissions list.
2. **Internal-consistency validation of the RETURNED report.** Percentiles monotone non-decreasing; category counts consistent with the row count and the suppression rule; correlation matrices symmetric with unit diagonal and PSD-tolerant; missingness rates in [0,1]; embedded validation-check results present and passing.
3. **Synthetic-vs-profile validation of GENERATED data.** Marginals within tolerance of the profile; correlations reproduced within tolerance; suppressed categories absent; row count matched; identifier columns structurally shaped but value-free.

## Reference Files

Load on demand — these are thorough by design (Level 3 loading; token cost only when read).

| File | Read when |
|------|-----------|
| `references/disclosure-tiers.md` | Choosing or explaining a tier; deciding what a tier may emit; setting the suppression threshold |
| `references/profiling-script-spec.md` | Preparing a profiling script (DS-1); the canonical JSON report schema (`report_version`, tier, suppression settings, per-column blocks, relationships block, embedded validation results) |
| `references/generation-patterns-r.md` | Writing R generation code (DS-5) — simstudy copula from a profile, fabricatr for hierarchy |
| `references/generation-patterns-python.md` | Writing Python generation code (DS-5) — NumPy/SciPy copula, Faker identifiers |
| `references/local-synthesis-t4.md` | Preparing the T4 local synthesizer templates (synthpop / SDV) the user runs in their environment |
| `references/validation-checks.md` | Any of the three QA checks — disclosure-safety, report consistency, synthetic-vs-profile |
| `references/synthetic-data-research.md` | Grounding evidence — the library split (§1-2), disclosure-control practice (§3), and failure modes (§4) the workflow rests on; cited throughout for source URLs |

## Asset Templates

Self-contained, zero-DAAF-dependency scripts the user runs where DAAF cannot reach. Copy and configure — never execute the shipped asset in place (execution logs would pollute the pristine template).

| Asset | Purpose |
|-------|---------|
| `assets/profile_data_template.R` | Disclosure-controlled profiler (R, flagship) — base R for CSV, optional arrow/haven; tier-parameterized; emits JSON + `.txt` review summary |
| `assets/profile_data_template.py` | Disclosure-controlled profiler (Python) — stdlib + pandas, optional pyarrow; same tier/config/dual-output design |
| `assets/synthesize_local_template.R` | T4 local high-fidelity synthesis (R) — synthpop CART, emits only synthetic rows + a generation log |
| `assets/synthesize_local_template.py` | T4 local high-fidelity synthesis (Python) — SDV GaussianCopula, same discipline |

## Boundaries

- **Never** ask the user to send raw data, raw extracts, unsuppressed cross-tabs, example values, or the fitted synthesis model. If a request would require any of these, stop and re-scope to a tier that does not.
- **Never** present synthetic-data results as findings. Every deliverable built on synthetic data carries the scaffold-not-substitute caveat and the "finalize against real data" requirement.
- **Always** have the user review the `.txt` summary before they share the JSON report — the human disclosure review is a required gate, not a formality.
- **Always** seed generation and record the seed for reproducibility.
- The disclosure-safety review of the outbound script is the single most important control in this workflow — treat a possible leak as a BLOCKER, never a WARNING.
