# Phase 4 Plan — Skill Loading & Reference Routing (`skill_routing`)

**Status:** APPROVED — design confirmed by user 2026-06-10 (§ 9 decisions recorded; Agent tool disallowed per user direction). Amended 2026-06-10 post-dry-run-2: `no_spurious_skill_reload` criterion removed (§ 9 decision 6).
**Date:** 2026-06-10
**Origin:** Design Backlog "Skill Loading test category" (README § 12; Reference § 7.3),
re-scoped per user direction: 15 brainstorming prompts scored on whether the model
loads exactly the skills and reads exactly the reference files that the skills' own
routing directives prescribe.

---

## 1. What Phase 4 Tests

A model resumes from the existing Ad Hoc Collaboration golden checkpoint and receives
one precise brainstorming question. The question contains enough fabricated detail
that no clarifying question is needed, and is constructed so the routing text inside
the DAAF skills makes one specific set of Skill loads and reference Reads objectively
correct. Scoring is fully deterministic: transcript parsing for `Skill` and `Read`
tool_use blocks.

**What makes a case valid:** every required load/read must be *explicitly necessitated
by verbatim routing text* in a SKILL.md (the data-scientist hub tree, a library skill's
decision tree, or frontmatter disambiguation like "For static figures use plotnine").
Each case below quotes its ground-truth directives.

**Excluded skills** (per user direction): skill-authoring, agent-authoring,
shell-scripting, stata-python-translation, r-python-translation, all education-data-*
skills, education-data-query/explorer. **In scope:** data-scientist (hub),
statsmodels, pyfixest, linearmodels, svy, scikit-learn, polars, geopandas, plotly,
plotnine, marimo, science-communication. (polars and marimo ended up reserve-only —
see § 7.)

---

## 2. Mechanics (verified against current code)

### 2.1 Golden checkpoint — reuse Phase 3's, unchanged

`benchmarks/golden/dispatch_compliance/ad_hoc_initialized.jsonl` (47 lines). Verified
contents — exactly 3 tool_use blocks:

| Line | Tool | Input |
|------|------|-------|
| 9 | Skill | `daaf-orchestrator` |
| 31 | Read | `.../references/ad-hoc-collaboration-mode.md` |
| 36 | Skill | `data-scientist` |

The final exchange is generic ("I'm ready to go. What's the first task?"), with **no
workspace and no topic context** — any brainstorming topic can follow naturally.
Cases reference this golden by its existing path (no copy): duplicating it would
create a second line-count dependency for zero benefit.

**In-context state cases may assume:** daaf-orchestrator skill, ad-hoc mode reference,
data-scientist skill (the routing hub). Therefore:
- `data-scientist` need not be re-loaded by the main session (it is already in
  context from the checkpoint). This is no longer scored: the
  `no_spurious_skill_reload` criterion was removed 2026-06-10 (§ 9 decision 6)
- Reads of `data-scientist/references/*.md` **are** scoreable expectations (the hub's
  "FIRST read X THEN load Y" directives are in context from the checkpoint)

### 2.2 Expected model behavior — main transcript is primary

`ad-hoc-collaboration-mode.md` (lines 127-135, 160) directs the orchestrator to
**respond directly** to brainstorming/methodology questions, loading the relevant
skill directly when it can answer from it (line 97), erring "toward responding
directly first." So required loads/reads normally appear in the main transcript.

**Agent tool disallowed (user decision, 2026-06-10):** Phase 4 runs pass `Agent`
via `disallowed_tools`, so subagent dispatch is impossible and **all scoring is
main-transcript-only.** Rationale: brainstorming questions are direct-answer
territory per the mode doc anyway; blocking dispatch eliminates subagent
cost/rate-limit hassle and transcript-union scoring complexity. Accepted tradeoff:
the deny feedback may lightly redirect a dispatch-inclined model toward direct
answering — a mild artificial assist. Note: unlike the ineffective Bash
sub-pattern deny rules (README § 11, Limitation 1), disallowing an entire tool by
name works reliably.

### 2.3 Detection surface (verified shapes)

- Main transcript: `assistant` records → `message.content[].tool_use` with
  `{"name":"Skill","input":{"skill":"pyfixest"}}` and
  `{"name":"Read","input":{"file_path":"..."}}`; success cross-referenced via
  `tool_result` blocks by `tool_use_id`.
- `scorers/deterministic/checkpoint_adherence.py` already implements:
  `extract_new_tool_calls()` (post-checkpoint slicing, ordered, success-flagged) and
  basename-matched `documents_read` / membership-matched `skills_loaded` criteria.
- `scorers/deterministic/subagent_behavior.py`'s subagent-transcript machinery is
  **not needed** — with Agent disallowed (§ 2.2), no subagent transcripts exist.
- **Path-mangling hazard (verified):** sandbox checkpoint replay string-rewrites
  `/daaf` inside replayed `file_path` values. All Read matching must be by
  **basename**, never full path. Basenames in §5 are unique within their skill, and
  the skill-membership requirement comes from the paired Skill-load criterion, so
  basename matching does not create cross-skill false positives. (One exception
  handled explicitly: `visualization.md` exists in geopandas — required only in
  geopandas cases where the geopandas Skill load is also required. No in-scope skill
  has a colliding `visualization.md`.)

### 2.4 New components

| Artifact | Source template | Notes |
|----------|----------------|-------|
| `datasets/skill_routing/cases.jsonl` | Phase 2/3 case format | 15 cases (§ 5), schema in § 4 |
| `scorers/deterministic/skill_routing.py` | thin module | Reuses `extract_new_tool_calls` (checkpoint_adherence); main-transcript-only; implements § 3 criteria |
| `scripts/run_skill_routing.py` | `run_dispatch_compliance.py` shell | Strip `prepare_fixtures()` entirely (no fixtures); keep checkpoint validation, sandbox/RunConfig/execute_run, score-even-on-timeout, manifest/summary/viewer-compatible archiving (subagent archival may remain as a no-op safeguard). Set `RunConfig.disallowed_tools = ["Agent"]` (replaces the default git Bash patterns, which are ineffective anyway — README § 11.1). `score_run()` calls the new scorer. Benchmark key: `skill_routing` |
| `harness/cost_estimator.py` | edit | Add `PHASE4_TOKENS` + `CALIBRATION["skill_routing"]`. Initial profile: clone the Phase 2 per-case shape but expect heavier reads — seed with pc-04 (ad-hoc) values ×1.5 as placeholder; recalibrate after first real batch (flagged stale in-code, consistent with README § 7 caveat) |
| Viewer | `generate_results_viewer.py` | Criterion names are collected dynamically; verify the phase filter picks up the new category label ("Phase 4"), likely a small label-map addition |
| README | § 2/3/5/6 updates | After implementation, not before |

Runner CLI, parallelism, cost-confirmation, and archive layout: identical to the
other runners. OpenRouter parallel waves fine; Anthropic sequential per README § 9.
`turn_limit`: 12, `cost_tier`: `medium` for all cases (multi-read direct answers;
no heavy execution).

---

## 3. Scoring Design

### 3.1 Criteria

All criteria evaluate the **main transcript only**, post-checkpoint (Agent tool is
disallowed, § 2.2 — no subagent transcripts exist).

| Criterion | Tier | Definition |
|-----------|------|------------|
| `required_skills_loaded` | tier1 | Every skill in `expected.required_skills` has ≥1 successful Skill call |
| `required_refs_read` | tier1 | Every basename in `expected.required_refs` has ≥1 successful Read |
| `expected_refs_read` | tier2 | Every basename in `expected.expected_refs` (secondary set) read |
| `routing_order` | tier2 | `expected.order` is an ordered list of `["read", basename]` / `["skill", name]` items; passes if it appears as a subsequence of the post-checkpoint tool-call stream. Tests "FIRST read X THEN load Y" |
| `no_forbidden_skills` | tier2 | No successful Skill call for any name in `expected.forbidden_skills` (the skills the routing text explicitly rules out) |

Per-case: `hard_requirements = ["required_skills_loaded", "required_refs_read"]`,
`soft_requirements = ["expected_refs_read", "routing_order",
"no_forbidden_skills"]` — uniform across all 15 cases.

### 3.2 Global scoring policies

1. **quickstart.md / gotchas.md always allowed, never required.** Library skills'
   "Reading Order" sections prepend quickstart.md; a brainstorming agent may
   reasonably skip or include it. Reads of any file under a *correctly loaded*
   skill's references/ are never penalized.
2. **Allowed ≠ expected.** Each case documents an `allowed_refs` list (plausible
   extras) purely for human auditability; the scorer ignores it. There is no
   "too many reads" penalty — over-reading is a quality issue, not a routing error,
   and penalizing it deterministically would punish thoroughness.
3. **Forbidden = explicitly ruled out in routing text only.** A skill goes in
   `forbidden_skills` only when a verbatim directive excludes it for this task
   (e.g., "linearmodels has no DiD"; "For static figures use plotnine" + the
   kaleido prohibition). Merely-unnecessary skills are not forbidden.
4. **Basename matching** for all Reads (§ 2.3 hazard).
5. **Success-only:** failed tool calls (missing file, etc.) never satisfy a
   requirement.

---

## 4. cases.jsonl Schema

```json
{"id": "sr-01", "category": "skill_routing", "subcategory": "causal_staggered_did",
 "prompt": "<full text from § 5>",
 "expected": {
   "required_skills": ["pyfixest"],
   "required_refs": ["causal-inference.md", "difference-in-differences.md"],
   "expected_refs": [],
   "order": [["read", "causal-inference.md"], ["skill", "pyfixest"],
             ["read", "difference-in-differences.md"]],
   "forbidden_skills": ["linearmodels", "statsmodels"]},
 "golden_checkpoint": "benchmarks/golden/dispatch_compliance/ad_hoc_initialized.jsonl",
 "turn_limit": 12, "cost_tier": "medium",
 "hard_requirements": ["required_skills_loaded", "required_refs_read"],
 "soft_requirements": ["expected_refs_read", "routing_order",
                       "no_forbidden_skills"]}
```

**No `golden_project_path` (amended 2026-06-10):** Phase 4 cases deliberately
omit this field. Setting it makes `prepare_sandbox()` rewrite every `/daaf`
literal in the replayed history — including the in-history skill file paths
that routing depends on — which poisons the test (discovered in dry-run 1).

---

## 5. The 15 Test Cases

Path shorthand: `DS/` = `data-scientist/references/`; library refs belong to the
required skill unless prefixed. All ground-truth quotes are verbatim from current
SKILL.md files (verified 2026-06-10).

---

### sr-01 — `causal_staggered_did` (pyfixest)

**Prompt:**
> I want to brainstorm a causal analysis. 24 states adopted a tutoring mandate in different years between 2014 and 2019, and I have a district-year panel of about 12,000 districts spanning 2010–2022 with standardized math scores. I'm specifically worried about bias from staggered adoption under the classic two-way fixed effects setup. Help me think through which modern DiD estimators to consider and what diagnostics I should plan for.

| Field | Value |
|---|---|
| required_skills | `pyfixest` |
| required_refs | `DS/causal-inference.md`, `difference-in-differences.md` |
| expected_refs | — |
| order | read causal-inference.md → skill pyfixest → read difference-in-differences.md |
| allowed | quickstart.md, fixed-effects.md, advanced-inference.md |
| forbidden_skills | `linearmodels`, `statsmodels` |

**Ground truth:** Hub: "Causal / quasi-experimental analysis — FIRST read
./references/causal-inference.md THEN load appropriate library skill (pyfixest for
DiD/IV/FE…)". pyfixest: "Staggered treatment timing →
./references/difference-in-differences.md". Exclusions: linearmodels "FE + DiD →
pyfixest (linearmodels has no DiD)"; statsmodels "For FE/DiD use pyfixest."

---

### sr-02 — `panel_re_vs_fe` (linearmodels)

**Prompt:**
> Help me brainstorm a panel modeling approach. I have a balanced panel of 600 hospitals over 8 years, and the key regressor of interest is ownership type, which is time-invariant — so a fixed-effects model would absorb it entirely. I want to think through the association between ownership and patient outcomes using random effects, and ideally estimate both RE and FE and compare them formally before choosing.

| Field | Value |
|---|---|
| required_skills | `linearmodels` |
| required_refs | `DS/statistical-modeling.md`, `panel-models.md` |
| expected_refs | — |
| order | read statistical-modeling.md → skill linearmodels → read panel-models.md |
| allowed | quickstart.md, covariance-inference.md, gotchas.md |
| forbidden_skills | `pyfixest` |

**Ground truth:** Hub: "Random effects, between, first difference, Fama-MacBeth →
Load `linearmodels` skill". linearmodels: "Random effects (GLS) → linearmodels
RandomEffects → ./references/panel-models.md"; "FE vs RE comparison → linearmodels
(run both, compare) → ./references/panel-models.md". Exclusion: pyfixest "For panel
RE/between use linearmodels." Wording is deliberately associational ("association
between") to keep the hub branch at statistical-modeling, not causal-inference.

---

### sr-03 — `iv_liml_gmm` (linearmodels)

**Prompt:**
> I'm brainstorming a returns-to-schooling IV analysis: a single cross-section of roughly 330,000 adults, quarter-of-birth supplying three instruments for one endogenous schooling variable, and no fixed effects anywhere in the design. Because of weak-instrument concerns I specifically want to think through LIML and GMM-IV estimators rather than plain 2SLS, along with the first-stage and overidentification diagnostics I should report.

| Field | Value |
|---|---|
| required_skills | `linearmodels` |
| required_refs | `DS/causal-inference.md`, `iv-models.md` |
| expected_refs | — |
| order | read causal-inference.md → skill linearmodels → read iv-models.md |
| allowed | quickstart.md, covariance-inference.md |
| forbidden_skills | `pyfixest` |

**Ground truth:** Hub: "(…linearmodels for panel RE/IV-GMM…)" under the causal
FIRST-read branch, and "IV without FE (LIML, GMM) → Load `linearmodels` skill".
linearmodels: "LIML / k-class (better finite-sample) → linearmodels IVLIML →
./references/iv-models.md"; "GMM-IV (efficient, overidentified) → linearmodels
IVGMM → ./references/iv-models.md". The prompt names LIML/GMM explicitly because
plain 2SLS is genuinely dual-routed ("linearmodels IV2SLS or pyfixest") — naming
them is what makes pyfixest objectively wrong here ("FE + IV combined → pyfixest"
does not apply; no FE).

---

### sr-04 — `complex_survey` (svy)

**Prompt:**
> Help me think through analyzing NHANES 2017–2018 MEC exam data, about 9,200 respondents. I need obesity prevalence by income group first, and then a survey-weighted logistic regression for obesity risk. I already have the design variables ready: stratum (sdmvstra), PSU (sdmvpsu), and the MEC exam weight (wtmec2yr). What should I be careful about in setting this up?

| Field | Value |
|---|---|
| required_skills | `svy` |
| required_refs | `DS/survey-analysis.md`, `design-weights.md`, `regression.md` |
| expected_refs | `estimation.md` |
| order | read survey-analysis.md → skill svy |
| allowed | — (svy has only 3 reference files) |
| forbidden_skills | `statsmodels` |

**Ground truth:** Hub: "FIRST read ./references/survey-analysis.md (methodology,
pitfalls, weight selection) THEN load `svy` skill for implementation syntax —
Survey-weighted descriptive statistics → svy estimation.md; Survey-weighted
regression (OLS, logistic, Poisson) → svy regression.md; Survey design setup /
replicate weights → svy design-weights.md". Exclusion: svy frontmatter "statsmodels
WLS and pyfixest clustered SEs are NOT substitutes for proper survey-weighted
analysis." `estimation.md` is soft (prevalence = descriptive branch) — a model that
treats the regression as the core task and skips it is imperfect but not wrong.

---

### sr-05 — `system_sur` (linearmodels)

**Prompt:**
> I'd like to brainstorm jointly modeling district spending in three categories — instruction, support services, and capital — as three separate equations over the same ~14,000 districts in a single year. The error terms are surely correlated across the three equations for a given district. Help me think through a seemingly-unrelated-regressions setup versus just estimating the equations separately.

| Field | Value |
|---|---|
| required_skills | `linearmodels` |
| required_refs | `DS/statistical-modeling.md`, `system-models.md` |
| expected_refs | — |
| order | read statistical-modeling.md → skill linearmodels → read system-models.md |
| allowed | quickstart.md |
| forbidden_skills | `statsmodels`, `pyfixest` |

**Ground truth:** Hub: "System estimation (SUR, 3SLS) → Load `linearmodels` skill".
linearmodels: "Multiple equations, correlated errors → SUR →
./references/system-models.md". Lowest-ambiguity case in the suite: SUR appears in
exactly one in-scope skill; neither statsmodels nor pyfixest offers it.

---

### sr-06 — `glm_marginal_effects` (statsmodels)

**Prompt:**
> Help me brainstorm a model for whether households take up a new state benefit. I have one cross-sectional simple random sample of about 8,000 households — self-weighting design, no clustering or stratification to worry about. The outcome is binary, predictors are a mix of continuous and categorical, there's no panel structure and no fixed effects, and I'd like to think through reporting marginal effects rather than odds ratios.

| Field | Value |
|---|---|
| required_skills | `statsmodels` |
| required_refs | `DS/statistical-modeling.md`, `glm-discrete.md` |
| expected_refs | — |
| order | read statistical-modeling.md → skill statsmodels → read glm-discrete.md |
| allowed | quickstart.md, diagnostics.md, hypothesis-testing.md |
| forbidden_skills | `svy`, `pyfixest` |

**Ground truth:** Hub: "Standard regression (OLS, logistic, GLM) → Load
`statsmodels` skill". statsmodels references: logit/probit/marginal effects →
`glm-discrete.md` (Topic Index). Exclusions: the svy boundary cuts the other way
here — svy is for *complex* probability surveys; the prompt's explicit
"simple random sample, self-weighting, no clustering or stratification" makes svy
loading a routing error. pyfixest excluded by "no fixed effects" + statsmodels'
"Need fixed effects? → Use pyfixest instead" (inverse). This is the suite's sharpest
distractor test: the word "sample/survey-adjacent" context must not trigger svy.

---

### sr-07 — `count_fe_poisson` (pyfixest)

**Prompt:**
> Brainstorm with me how to model annual counts of disciplinary incidents across roughly 90,000 schools for 2015–2022, with school and year fixed effects. The counts have lots of zeros and look overdispersed relative to a simple Poisson. I want to think through estimator choice for count outcomes in a fixed-effects setting and what robustness checks make sense.

| Field | Value |
|---|---|
| required_skills | `pyfixest` |
| required_refs | `DS/statistical-modeling.md`, `integration.md` |
| expected_refs | — |
| order | read statistical-modeling.md → skill pyfixest → read integration.md |
| allowed | quickstart.md, fixed-effects.md, gotchas.md |
| forbidden_skills | `statsmodels` |

**Ground truth:** Hub: "Fixed effects, IV with FE, or DiD → Load `pyfixest` skill".
pyfixest: "Poisson (count data) → ./references/integration.md". Exclusion:
statsmodels "Need fixed effects? → Use pyfixest instead (faster FE absorption)".
The prompt deliberately avoids the phrase "negative binomial" (which routes to
statsmodels `glm-discrete.md` and would create genuine ambiguity).

---

### sr-08 — `clustering_typology` (scikit-learn)

**Prompt:**
> Help me brainstorm building a typology of about 5,000 school districts from 12 finance and demographic indicators. I don't know how many groups exist, I want hard group assignments rather than probabilistic ones, and I'll need to defend cluster validity to reviewers. I also plan to use the resulting cluster labels as a variable in a follow-up regression, which I hear has pitfalls.

| Field | Value |
|---|---|
| required_skills | `scikit-learn` |
| required_refs | `DS/exploratory-unsupervised.md`, `clustering.md`, `evaluation-unsupervised.md` |
| expected_refs | — |
| order | read exploratory-unsupervised.md → skill scikit-learn → read clustering.md |
| allowed | preprocessing.md, quickstart.md, gotchas.md |
| forbidden_skills | — |

**Ground truth:** Hub: "Unsupervised analysis … FIRST read
./references/exploratory-unsupervised.md THEN load `scikit-learn` skill … Clustering
→ clustering.md, evaluation-unsupervised.md". scikit-learn: "Clustering task? Read
`clustering.md`, then `evaluation-unsupervised.md`". "Hard assignments" forecloses
`mixture-models.md` (soft assignments); the classify-analyze clause re-cites
exploratory-unsupervised.md ("The Classify-Analyze Problem"), reinforcing rather than
diverging. No forbidden skill — there is no plausibly-wrong *skill*, only wrong refs.

---

### sr-09 — `static_publication_figure` (plotnine)

**Prompt:**
> I have a polished parquet file of district poverty rates from 2010–2022 by census region. Help me think through a faceted small-multiples trend figure for a print journal manuscript — static output around 300 dpi, one panel per region, colorblind-safe palette. I want to reason about the design before any code gets written.

| Field | Value |
|---|---|
| required_skills | `plotnine` |
| required_refs | `DS/visualization-design.md`, `DS/visualization-execution.md`, `facets-themes.md` |
| expected_refs | `scales-coords.md` |
| order | read visualization-design.md → skill plotnine → read facets-themes.md |
| allowed | geoms.md, quickstart.md |
| forbidden_skills | `plotly` |

**Ground truth:** Hub: "Data visualization (any kind) → Stage 8.2 — FIRST read
visualization reference files below: ./references/visualization-design.md … and
./references/visualization-execution.md … THEN load the tool-specific skill: Static
plots → Load `plotnine` skill", reinforced by "Visualization loading order matters."
plotnine: faceting/themes → `facets-themes.md`; palettes → `scales-coords.md` (soft,
triggered by "colorblind-safe"). Exclusions (two independent): plotly frontmatter
"For static figures use plotnine" and plotly SKILL.md "Static image export (PNG/SVG/
PDF) is NOT available in DAAF — kaleido is not installed… Use plotnine for static
figures."

---

### sr-10 — `interactive_html` (plotly)

**Prompt:**
> My program officers want to explore college-level Pell grant trends themselves — hovering for institution details and zooming into time ranges. Help me brainstorm a single self-contained HTML file I can email them. There's no print version needed, and I don't want a hosted app or notebook — just one file they double-click.

| Field | Value |
|---|---|
| required_skills | `plotly` |
| required_refs | `DS/visualization-design.md`, `DS/visualization-execution.md`, `charts.md`, `export.md` |
| expected_refs | — |
| order | read visualization-design.md → skill plotly → read charts.md |
| allowed | styling.md, quickstart.md, gotchas.md |
| forbidden_skills | `plotnine`, `marimo` |

**Ground truth:** Hub: "Interactive plots → Load `plotly` skill" (after the same
FIRST-read pair as sr-09). plotly frontmatter: "Use when interactivity (hover/zoom)
is needed. For static figures use plotnine"; "Interactive HTML →
./references/export.md" makes `export.md` required given the explicit
single-HTML-file delivery. Exclusions: plotnine (static-only counterpart); marimo
foreclosed by "I don't want a hosted app or notebook."

---

### sr-11 — `choropleth_projection` (geopandas)

**Prompt:**
> Help me think through a static county-level choropleth of chronic absenteeism rates for the continental United States, destined for a printed report. I specifically want to reason about the classification scheme — quantiles versus natural breaks — and about choosing an appropriate projection for a national map.

| Field | Value |
|---|---|
| required_skills | `geopandas` |
| required_refs | `DS/geospatial-analysis.md`, `visualization.md`, `crs-projections.md` |
| expected_refs | `DS/geospatial-operations.md` |
| order | read geospatial-analysis.md → skill geopandas → read visualization.md |
| allowed | quickstart.md, data-io.md, gotchas.md |
| forbidden_skills | `plotly`, `plotnine` |

**Ground truth:** Hub: "Geospatial / spatial analysis (any kind) → FIRST read
methodology reference files: ./references/geospatial-analysis.md …
./references/geospatial-operations.md … THEN load `geopandas` skill". geopandas:
"Making maps? Read `visualization.md` (relies on `crs-projections.md` for projection
choices)" — the prompt's explicit projection question makes `crs-projections.md`
required, not just allowed. Exclusions: plotly frontmatter "for GIS use geopandas";
plotnine frontmatter "for maps use geopandas". `geospatial-operations.md` is soft:
the hub lists both methodology files, but this task involves no spatial operations.

---

### sr-12 — `spatial_autocorrelation` (geopandas)

**Prompt:**
> I suspect school poverty clusters geographically across the ~2,900 census tracts in my state. Brainstorm with me how I'd test for spatial autocorrelation globally, then find local hot spots and cold spots — and what interpretation pitfalls like MAUP I should watch for when I write this up.

| Field | Value |
|---|---|
| required_skills | `geopandas` |
| required_refs | `DS/geospatial-analysis.md`, `pysal-spatial-stats.md` |
| expected_refs | `DS/geospatial-operations.md` |
| order | read geospatial-analysis.md → skill geopandas → read pysal-spatial-stats.md |
| allowed | crs-projections.md, visualization.md, quickstart.md |
| forbidden_skills | `scikit-learn` |

**Ground truth:** Hub geospatial FIRST-read (as sr-11). geopandas: "Test for spatial
autocorrelation (Moran's I) → ./references/pysal-spatial-stats.md"; "Find hot spots /
cold spots (LISA) → ./references/pysal-spatial-stats.md"; "Methodology guidance
(interpretation, MAUP) → data-scientist skill: geospatial-analysis.md". Exclusion:
scikit-learn "For spatial analysis, use `geopandas`" (hot spots ≠ k-means).

---

### sr-13 — `ml_fairness` (scikit-learn)

**Prompt:**
> We've trained a gradient-boosted classifier that predicts student dropout risk, and it's headed for deployment next term. Help me brainstorm how to assess whether it's fair across race and gender subgroups — which group-level metrics to compute and what mitigation options exist if we find disparities. We don't need help explaining individual predictions.

| Field | Value |
|---|---|
| required_skills | `scikit-learn` |
| required_refs | `DS/supervised-ml.md`, `fairness.md` |
| expected_refs | — |
| order | read supervised-ml.md → skill scikit-learn → read fairness.md |
| allowed | evaluation-supervised.md, quickstart.md |
| forbidden_skills | — |

**Ground truth:** Hub: "Fairness assessment → Read supervised-ml.md 'Fairness' +
scikit-learn fairness.md". scikit-learn: "Fairness assessment? Read `fairness.md`,
then check `supervised-ml.md` in data-scientist skill for conceptual framework".
The closing sentence forecloses `interpretation.md` (SHAP) — the main wrong-ref
distractor; no plausibly-wrong skill exists, so no forbidden list.

---

### sr-14 — `executive_summary` (science-communication)

**Prompt:**
> Our 40-page enrollment-decline analysis is finished and reviewed. Help me brainstorm a one-page executive summary for the university's board of trustees — they're non-technical, they want the recommendation up front, and the supporting evidence afterward. I want to think through structure and framing, not data analysis.

| Field | Value |
|---|---|
| required_skills | `science-communication` |
| required_refs | `audience-analysis.md`, `narrative-frameworks.md`, `deliverable-templates.md` |
| expected_refs | — |
| order | skill science-communication → read audience-analysis.md → read narrative-frameworks.md → read deliverable-templates.md |
| allowed | plain-language.md, communication-review.md |
| forbidden_skills | — |

**Ground truth:** Hub: "Communicating to non-technical audiences → Load
`science-communication` skill" (note: no hub FIRST-read for this branch — the
ordering starts at the Skill load). science-communication: "Writing a report or
brief? Start with `audience-analysis.md`, then `narrative-frameworks.md`, then
`deliverable-templates.md`"; trees: "Executives or board members →
audience-analysis.md", "Need to deliver a recommendation quickly → Pyramid Principle
→ narrative-frameworks.md", "One-page summary for decision makers → Executive
summary → deliverable-templates.md". This is the only case scoring a 3-read ordered
sequence — the skill's own reading order is explicit, making it fair ground truth.

---

### sr-15 — `cross_skill_spatial_pub` (geopandas + plotnine) — hard tier

**Prompt:**
> We've estimated a spatial-lag model of neighborhood effects on student outcomes, and now I need to plan the paper's two key exhibits: a LISA cluster map of the neighborhood effect, and a static coefficient plot of the model estimates suitable for print. Help me think through both deliverables and how to produce them.

| Field | Value |
|---|---|
| required_skills | `geopandas`, `plotnine` |
| required_refs | `pysal-spatial-stats.md`, `DS/visualization-design.md` |
| expected_refs | `DS/geospatial-analysis.md`, `DS/visualization-execution.md`, `geoms.md` |
| order | — (omitted: no directive prescribes cross-branch sequencing) |
| allowed | visualization.md (geopandas), crs-projections.md, facets-themes.md |
| forbidden_skills | `plotly` |

**Ground truth:** geopandas: "Spatial regression (lag, error, Durbin) →
./references/pysal-spatial-stats.md"; "LISA cluster map →
./references/pysal-spatial-stats.md"; cross-skill handoff: "**plotnine / plotly**:
For non-map visualizations of spatial analysis results (coefficient plots,
distributions)" — combined with "static … for print" + the kaleido prohibition,
plotnine is the only correct chart skill. Hub viz FIRST-read applies to the
coefficient-plot half (visualization-design.md required; execution soft). This case
intentionally requires **two** library skill loads. The `order` key is omitted
from its expected block because no directive sequences the two branches — the
`routing_order` criterion itself remains in the (uniform) soft set and passes
automatically when `order` is absent.

---

## 6. Coverage Matrix

| Skill | Required in | Forbidden in (distractor role) |
|---|---|---|
| pyfixest | sr-01, sr-07 | sr-02, sr-03, sr-05, sr-06 |
| linearmodels | sr-02, sr-03, sr-05 | sr-01 |
| statsmodels | sr-06 | sr-01, sr-04, sr-05, sr-07 |
| svy | sr-04 | sr-06 |
| scikit-learn | sr-08, sr-13 | sr-12 |
| plotnine | sr-09, sr-15 | sr-10, sr-11 |
| plotly | sr-10 | sr-09, sr-11, sr-15 |
| geopandas | sr-11, sr-12, sr-15 | — |
| science-communication | sr-14 | — |
| data-scientist (hub refs) | 14 of 15 cases | reload discouraged but unscored (criterion removed 2026-06-10) |

Hub references exercised: causal-inference, statistical-modeling, survey-analysis,
exploratory-unsupervised, supervised-ml, visualization-design, visualization-execution,
geospatial-analysis (+geospatial-operations soft).

---

## 7. Deliberately Excluded Scenario Types (reserve list)

| Scenario | Why excluded |
|---|---|
| Time series (ARIMA/VAR → statsmodels) | The data-scientist hub tree has **no time-series branch**; routing is reachable only via statsmodels' own frontmatter — ambiguous at the hub level |
| Plain 2SLS without FE | Genuinely dual-routed: "linearmodels IV2SLS or pyfixest" — no objectively correct skill |
| Few-clusters wild bootstrap (pyfixest advanced-inference.md) | Strong case, cut for slot economics in favor of sr-06's statsmodels/svy distractor test; first candidate if the suite grows |
| polars larger-than-memory → performance.md | Clean routing but a poor fit for brainstorming framing (it's an implementation question) |
| marimo app | "Always Load Together: data-scientist … polars" directive creates irreducible load-set ambiguity |
| Bayesian / survival | Hub routes both to "escalate to orchestrator" — interesting *refusal* test but not a routing test; candidate for a future Safety/Protocol category |

---

## 8. Implementation Sequence

1. `datasets/skill_routing/cases.jsonl` — encode § 5 (mechanical transcription)
2. `scorers/deterministic/skill_routing.py` — § 3 criteria over reused extractors
3. `scripts/run_skill_routing.py` — clone runner shell, no fixtures
4. `cost_estimator.py` — `skill_routing` calibration key (placeholder profile)
5. **Dry-run validation:** 2-3 cases × 2 models (one Anthropic, one cheap OpenRouter),
   1 rep — audit every criterion result against the raw transcript by hand before
   authoring is considered done. Specifically check: basename collisions, ordering
   subsequence logic, and whether any prompt provokes clarifying questions (a case
   that triggers clarification fails its design goal and gets reworded).
   (Original text also listed "subagent-union behavior" — superseded by the
   Agent-disallow decision, § 2.2: no subagent transcripts exist)
6. Viewer label + README §§ 2, 3, 5, 6 updates
7. Full baseline batch (model set and reps: user decision)

## 9. Design Decisions (resolved by user, 2026-06-10)

1. **Hard-requirement strictness:** KEEP HARD. Hub FIRST-reads and required refs
   remain tier1/hard — they are the most explicit directives in the system.
2. **`no_forbidden_skills` severity:** KEEP SOFT. User rationale: loading the wrong
   skill is only harmful if acted upon, and in some cases the wrong skill's own
   disambiguation text tells the agent what it needs to know (the bidirectional
   exclusions are themselves informative).
3. **Case count per skill:** Accepted as drafted (3 linearmodels / 3 geopandas vs
   1 each for svy, statsmodels, plotly, science-communication).
4. **sr-15 hard tier:** KEEP the two-skill case.
5. **Agent tool:** DISALLOWED for all Phase 4 runs (added decision — see § 2.2).
6. **`no_spurious_skill_reload` REMOVED** (2026-06-10, post-dry-run-2, user
   decision): passed 75/75 with zero discrimination; vacuously satisfied because
   models that fail routing mostly make zero Skill calls. Removed from scorer,
   cases, and schema. Historical dry-run results retain the criterion in their
   result.json files.
