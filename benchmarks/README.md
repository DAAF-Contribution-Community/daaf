# DAAF Framework Adherence Benchmarks

Benchmark system for evaluating LLM **behavioral conformance** to DAAF orchestrator
protocols. It answers one question: when a model is placed inside the real DAAF
container — hooks firing, skills discoverable, agents dispatchable — does it follow
the framework's protocols?

---

## 1. What This Is

The benchmark measures whether models acting as the DAAF orchestrator:

- Classify user requests into the correct engagement mode and present a
  confirmation gate before executing
- Load the correct mode reference files and skills after the user confirms
- Dispatch the correct subagent type via the Agent tool with a properly
  structured prompt (BASE_DIR, mode marker, task/context/instructions sections)
- Load exactly the skills and read exactly the reference files that the DAAF
  skills' own routing directives prescribe for a given task

**What it does NOT test:** answer quality, analytical capability, code
correctness, or general intelligence. A model can be brilliant at data analysis
and still score poorly here if it skips confirmation gates or dispatches
free-form prompts. Conversely, a weaker model that faithfully follows protocol
scores well.

**Model matrix:** 19 models — 7 Anthropic (Haiku 4.5, Sonnet 4.6, Opus
4.5/4.6/4.7/4.8, Fable 5) via the container's Claude Code subscription, and 12
OpenRouter models (GLM 5.1/5.2, Kimi K2.6, Kimi K2.7 Code, Qwen 3.6 27B,
Gemma 4 31B/26B, DeepSeek V4 Pro/Flash, Gemini 3.1 Pro, Nemotron 3 Ultra,
Gemini 3.1 Flash Lite) via an Anthropic-compatible endpoint. The matrix is defined in
`config/models.yaml`.

**Scope:** The original design specified six test categories; four are
implemented as the phases above. The remaining designed-but-unbuilt
categories are catalogued in the Design Backlog (§ 12).

## 2. The Four Phases

| Phase | Dataset | Cases | Start State | What It Tests |
|-------|---------|-------|-------------|---------------|
| 1 — `mode_classification` | `datasets/mode_classification/cases.jsonl` | 15 (mc-01..mc-15) | Cold start (no checkpoint; `CHECKPOINT_LINES = 0`) | Orchestrator skill loaded, mode classification, no premature execution (critical); confirmation gate present (normal) |
| 2 — `post_confirmation` | `datasets/post_confirmation/cases.jsonl` | 9 (pc-01..pc-09), one per engagement mode | Resumes from a golden checkpoint ending at the confirmation gate; prompt is "Sounds good, let's proceed." | Whether the model loads the expected mode reference files and skills after confirmation |
| 3 — `dispatch_compliance` | `datasets/dispatch_compliance/cases.jsonl` | 12 (dc-01..dc-12), 2 per agent type | Resumes from an Ad Hoc Collaboration initialized checkpoint (orchestrator + mode reference + data-scientist skill loaded) | Whether the model dispatches the correct subagent with a properly structured prompt |
| 4 — `skill_routing` | `datasets/skill_routing/cases.jsonl` | 15 (sr-01..sr-15) | Resumes from the same Ad Hoc initialized checkpoint as Phase 3; prompt is a brainstorming question | Whether the model loads exactly the skills and reads exactly the reference files that the skills' own routing directives prescribe |

Phase 3 covers six agent types: research-executor, source-researcher,
search-agent, debugger, code-reviewer, and data-ingest (2 cases each).

**Phase 3b — subagent behavior.** When a dispatch succeeds, the dispatched
subagent's own transcript (`~/.claude/projects/-daaf/{session_id}/subagents/agent-*.jsonl`)
is scored separately by `scorers/deterministic/subagent_behavior.py`. Behavioral
expectations are derived from the agent type (e.g., did a coding agent write a
script and execute it via `run_with_capture.sh`), with no per-case configuration.
Results appear as `subagent_criteria` alongside the dispatch criteria and are
shown as "Phase 3b" in the viewer.

**Phase 4 disallows the Agent tool** (`RunConfig.disallowed_tools = ["Agent"]`),
so subagent dispatch is impossible and all scoring is main-transcript-only —
brainstorming questions are direct-answer territory per the Ad Hoc mode doc, and
blocking dispatch eliminates subagent cost and transcript-union scoring
complexity. Accepted tradeoff: the Agent-tool deny feedback may lightly redirect
a dispatch-inclined model toward direct answering — a mild artificial assist.
Unlike Bash sub-pattern deny rules (§ 11), disallowing an entire tool by name
works reliably.

Each case's required loads/reads are grounded in verbatim routing text in the
skills themselves: a case is valid only if every required load/read is
*explicitly necessitated by a verbatim directive* in a SKILL.md (the
data-scientist hub tree, a library skill's decision tree, or frontmatter
disambiguation like "For static figures use plotnine"). A case that
provokes a clarifying question fails its design goal and must be reworded.
`cases.jsonl` is the operative encoding; the governing directives per case
are condensed below:

| Case | Skill(s) | Required refs | Governing directive (condensed) | Forbidden |
|------|----------|---------------|--------------------------------|-----------|
| sr-01 staggered DiD | pyfixest | DS/causal-inference, difference-in-differences | hub "FIRST read causal-inference THEN load… pyfixest for DiD"; pyfixest "Staggered timing → DiD ref" | linearmodels ("no DiD"), statsmodels |
| sr-02 RE vs FE | linearmodels | DS/statistical-modeling, panel-models | hub "Random effects… → linearmodels"; deliberately associational wording keeps hub branch non-causal | pyfixest ("RE/between use linearmodels") |
| sr-03 LIML/GMM IV | linearmodels | DS/causal-inference, iv-models | "IV without FE (LIML, GMM) → linearmodels"; LIML/GMM named because plain 2SLS is dual-routed | pyfixest (no FE) |
| sr-04 NHANES | svy | DS/survey-analysis, design-weights, regression (soft: estimation) | hub "FIRST read survey-analysis THEN load svy" | statsmodels (svy CRITICAL warning) |
| sr-05 SUR | linearmodels | DS/statistical-modeling, system-models | "System estimation (SUR, 3SLS) → linearmodels"; lowest-ambiguity case | statsmodels, pyfixest |
| sr-06 logit SRS | statsmodels | DS/statistical-modeling, glm-discrete | "Standard regression… → statsmodels"; sharpest distractor: explicit SRS/self-weighting makes svy a routing error | svy, pyfixest |
| sr-07 FE Poisson | pyfixest | DS/statistical-modeling, integration | "Poisson (count) → integration.md"; avoids "negative binomial" (would dual-route to statsmodels) | statsmodels |
| sr-08 clustering | scikit-learn | DS/exploratory-unsupervised, clustering, evaluation-unsupervised | hub unsupervised FIRST-read; "hard assignments" forecloses mixture-models | — |
| sr-09 static figure | plotnine | DS/visualization-design + -execution, facets-themes (soft: scales-coords) | hub viz FIRST-read pair; plotly excluded twice (frontmatter + kaleido prohibition) | plotly |
| sr-10 interactive HTML | plotly | viz-design + -execution, charts, export | "Interactive plots → plotly"; single-HTML delivery makes export.md required | plotnine, marimo ("no hosted app") |
| sr-11 choropleth | geopandas | DS/geospatial-analysis, visualization, crs-projections (soft: geospatial-operations) | explicit projection question upgrades crs-projections to required | plotly, plotnine ("for maps use geopandas") |
| sr-12 spatial autocorr | geopandas | DS/geospatial-analysis, pysal-spatial-stats (soft: geospatial-operations) | "Moran's I / LISA → pysal-spatial-stats" | scikit-learn ("For spatial analysis use geopandas") |
| sr-13 ML fairness | scikit-learn | DS/supervised-ml, fairness | "Fairness assessment? Read fairness.md"; forecloses interpretation.md (SHAP distractor) | — |
| sr-14 exec summary | science-communication | audience-analysis, narrative-frameworks, deliverable-templates | skill's own explicit 3-read order; only one-hop topic-is-the-skill case; no hub FIRST-read | — |
| sr-15 cross-skill (hard tier) | geopandas + plotnine | pysal-spatial-stats, DS/visualization-design (soft: geospatial-analysis, viz-execution, geoms) | geopandas cross-skill handoff "plotnine/plotly: for non-map visualizations" + kaleido prohibition; only two-skill case; `order` omitted — no directive sequences the branches | plotly |

**Test case format** (`cases.jsonl`, one JSON object per line):

```json
{"id": "mc-01", "category": "mode_classification", "subcategory": "unambiguous",
 "prompt": "...", "expected": {"mode": "data_onboarding", "confirmation_gate": true},
 "turn_limit": 5, "cost_tier": "low",
 "hard_requirements": ["orchestrator_skill_loaded", "mode_correct", "no_premature_execution"],
 "soft_requirements": ["confirmation_gate_present"]}
```

Phase 2/3/4 cases additionally carry a `golden_checkpoint` field; Phase 3 cases
also carry `golden_project_path`. Phase 4 deliberately omits
`golden_project_path`: setting it makes `prepare_sandbox()` rewrite every
`/daaf` literal in the replayed history — including the in-history skill file
paths that routing depends on — which poisons the test.

## 3. Architecture

End-to-end flow for one run:

```
cases.jsonl ──> phase runner (scripts/run_{phase}.py)
                  │
                  ├─ harness/checkpoint_manager.py
                  │    clones golden JSONL with a fresh session UUID into
                  │    ~/.claude/projects/-daaf/{uuid}.jsonl; seeds
                  │    _sandbox/run_{case}_{model}_{rep}/ (fixtures, workspace)
                  │
                  ├─ harness/executor.py
                  │    shells out to: claude -p "<prompt>" --model <id>
                  │      --output-format json --max-turns N
                  │      --permission-mode bypassPermissions
                  │      [--resume <uuid> | --session-id <uuid>]
                  │      [--disallowed-tools <list>] [--effort <level>]
                  │    runs INSIDE the DAAF container so all hooks fire
                  │
                  ├─ token capture: prefers result message "modelUsage"
                  │    (aggregates main session + subagent sessions);
                  │    falls back to "usage" (main session only)
                  │
                  ├─ harness/cost_estimator.py compute_cost()
                  │    recomputes cost from config/models.yaml pricing
                  │    (CLI-reported cost is wrong for OpenRouter models)
                  │
                  ├─ scorers/deterministic/*.py
                  │    parse the session transcript JSONL, only lines AFTER
                  │    the golden checkpoint's line count
                  │
                  └─ archive to results/{YYYYMMDD_HHMMSS}/
                       manifest.json, summary.json,
                       runs/{case}_{model}_{rep}/ (result.json,
                       transcript.jsonl, subagents/)
```

**Why the CLI and not the Agent SDK:** a deliberate design choice. Running
`claude -p` inside the container exercises the full framework — settings.json
hooks, permission rules, skill discovery, subagent dispatch — exactly as a real
session would. The SDK would bypass parts of this stack.

**Why transcripts and not `audit.jsonl`:** the audit log records an empty
`target` field for Skill and Agent tool calls, losing the skill names and
subagent prompts the scorers need. Session transcripts contain full `tool_use`
blocks with complete input parameters.

Directory map (paths relative to `benchmarks/`):

| Directory | Contents |
|-----------|----------|
| `harness/` | Core machinery: `executor.py` (CLI invocation), `checkpoint_manager.py` (golden cloning + sandbox lifecycle), `cost_estimator.py` (estimation + cost recomputation), `models.py` (dataclasses: TestCase, RunConfig, RunResult, etc.), `model_loader.py` (models.yaml loading + provider env wiring), `collector.py`, `hooks/` (benchmark-scoped hook scripts, e.g., `block-git-writes.sh` — see § 9) |
| `scorers/deterministic/` | `checkpoint_adherence.py`, `dispatch_compliance.py`, `subagent_behavior.py`, `skill_routing.py` (Phase 1 is scored inline by `scripts/run_mode_classification.py` — see § 6) |
| `datasets/` | `{phase}/cases.jsonl` plus `test_fixtures/` (buggy scripts and data for debugger/code-reviewer cases) |
| `golden/` | Golden checkpoint JSONLs (see § 5) |
| `config/` | `models.yaml` — model matrix with pricing |
| `scripts/` | Phase runners, `generate_goldens.py`, `generate_results_viewer_v2.py`, `viewer_template.html`, `refresh_golden_checkpoint.py`, `reconcile_openrouter_costs.py`, `clean_sandbox.sh` |
| `results/` | Timestamped, self-contained result sets |
| `_sandbox/` | Per-run scratch directories (transient, gitignored) |

## 4. Quick Start

**Environment.** Anthropic models authenticate via the container's Claude Code
OAuth — nothing to configure. OpenRouter models require `OPENROUTER_BASE_URL`
and `OPENROUTER_AUTH_TOKEN`, set on the host via `environment_settings.txt` in
the `daaf-docker/` folder (injected at container startup). If these are missing,
`model_loader.py` skips all OpenRouter models with a warning rather than failing.

**Run a phase** (from `/daaf`):

```bash
python3 benchmarks/scripts/run_mode_classification.py --reps 3
python3 benchmarks/scripts/run_post_confirmation.py --reps 3
python3 benchmarks/scripts/run_dispatch_compliance.py --reps 3
python3 benchmarks/scripts/run_skill_routing.py --reps 3
```

All four runners share an identical CLI:

| Flag | Default | Meaning |
|------|---------|---------|
| `--reps N` | 3 | Repetitions per case × model |
| `--models a,b` | all | Comma-separated model keys (lowercased names from models.yaml, spaces → hyphens, dots removed: `fable-5`, `sonnet-46`, `deepseek-v4-flash`). Keys come from this registry transformation, not bare model names — `sonnet`/`haiku` are not valid keys |
| `--provider X` | all | `anthropic`, `openrouter`, or `all` |
| `--test-id a,b` | all | Specific case IDs (e.g., `mc-01,mc-05`) |
| `--sequential` | off | Run one at a time instead of parallel |
| `--delay S` | 2 | Seconds between parallel launches (ThreadPoolExecutor stagger). Parallel-mode only — the sequential loop has no sleep, so this flag is a no-op with `--sequential` |
| `--timeout S` | tier-based | Override per-run timeout (defaults: low 120s, medium 300s, high 600s by case `cost_tier`) |
| `--yes` / `-y` | off | Skip the cost confirmation prompt |

`run_dispatch_compliance.py` additionally accepts `--no-fixture-restore`,
which skips the pre-batch fixture restore (§ 9).

Before launching, the runner prints a per-model cost estimate and asks for
interactive confirmation when the estimate exceeds $0.50 (suppressed by `--yes`).

Typical targeted invocation:

```bash
python3 benchmarks/scripts/run_dispatch_compliance.py \
    --models fable-5 --reps 1 --sequential --delay 20 --timeout 300 --yes
```

See § 9 before launching Anthropic Phase 3 runs — they must be sequential.

## 5. Golden Checkpoints

Golden checkpoints are truncated Claude Code session JSONL files from known-good
sessions. Resuming from one places the model mid-conversation at a precise
protocol point, so every run starts from an identical, controlled state.

**Session-ID cloning.** For each run, `checkpoint_manager.prepare_sandbox()`:

1. Cleans and recreates the run's sandbox directory (skipped via
   `wipe_sandbox=False` for the dispatch runner, which wipes before staging
   fixtures — see § 9), seeding it from a `{checkpoint}_seed/` directory if
   one exists
2. Rewrites the golden's session ID to a fresh UUID (enabling parallel runs)
   and rewrites the golden's project path to the sandbox path when
   `golden_project_path` is set
3. Writes the cloned JSONL to `~/.claude/projects/-daaf/{uuid}.jsonl`, where
   `claude -p --resume {uuid}` picks it up
4. Pre-creates the orchestrator-loaded flag file in `/tmp` so the
   `remind-orchestrator` hook doesn't re-inject a load reminder

Cold-start runs (Phase 1) instead pre-assign a UUID via `--session-id` so the
transcript is locatable even after a timeout. Cleanup (session file, subagent
directory, flag file, sandbox) happens only after scoring and archiving, so
timed-out runs still produce scorable data.

**Inventory** (`golden/`):

| File | Lines | Used By |
|------|-------|---------|
| `post_confirmation/{mode}.jsonl` (9 files) | 18 | Phase 2 — one per engagement mode, ending at the confirmation gate |
| `dispatch_compliance/ad_hoc_initialized.jsonl` | 47 | All 12 Phase 3 cases — Ad Hoc mode fully initialized (topic-free final exchange, so any task can follow) |
| `skill_routing/ad_hoc_initialized.jsonl` | 47 | All 15 Phase 4 cases — content-refreshed copy of the Phase 3 golden |
| `ad_hoc/after_confirmation.jsonl` | 19 | Unused by current scripts |
| `bootstrap_template.jsonl` | 7 | Input to `scripts/generate_goldens.py` |

**Regeneration.** Two distinct mechanisms:

- `scripts/generate_goldens.py` builds 7-line bootstrap-style checkpoints by
  injecting each case prompt from every `datasets/*/cases.jsonl` into line 3 of
  `golden/bootstrap_template.jsonl`, writing `golden/{category}/{case_id}.jsonl`.
- The Phase 2–4 goldens are **captured transcripts** — truncated from real
  sessions where a model correctly executed the protocol up to the desired
  boundary. Regenerating them means re-recording a session and truncating it.
  Scorers depend on each golden's exact line count (§ 6), so any change to a
  golden invalidates comparison with prior result sets.
- `scripts/refresh_golden_checkpoint.py` performs a **deterministic content
  refresh**: re-reads the files behind each Skill/Read tool result, rebuilds
  skill-listing attachment descriptions from current frontmatter, and splices
  current contents into the payloads while preserving everything else
  byte-for-byte. Caution: Read results are stored TWICE per record (numbered
  `message.content` payload AND raw `toolUseResult.file.content`) — both must
  be refreshed. A Skill call's tool_result is just "Launching skill: X" — the
  skill body arrives in a subsequent user record, so a refresh must target that
  later record.

**Golden staleness caveat.** A captured checkpoint freezes every tool-result
payload — skill bodies, reference files — at recording time. In-context text
dominates behavior: framework edits on disk are largely invisible until the
golden is refreshed. Any benchmark measuring a framework change MUST refresh
(or re-record) its goldens first, and result sets spanning a golden change
are not directly comparable.

## 6. Scoring

All current scoring is **deterministic** — transcript parsing with string and
structural checks, no LLM involvement. Scorers read the session transcript
JSONL and consider only lines **after** the golden checkpoint's line count, so
pre-recorded history is never re-scored.

**Criterion tiers — cases.jsonl is the source of truth.** Each test case
declares `hard_requirements` and `soft_requirements` listing which criteria
are critical vs. normal for that case; the human-edited case lists (and `expected`
fields) are the authority, and scorers derive the tiers they stamp on emitted
criteria from them (`tier1` = structural must-pass, e.g., `agent_dispatched`;
`tier2` = protocol detail, e.g., `prompt_has_base_dir`; `info` = diagnostic
only). Phase 1 criteria carry no stamped tier at all — the viewer classifies
them by membership in the case's `hard_requirements` list (in
`hard_requirements` → critical, otherwise normal). Vocabulary note: the display terms are "critical"/"normal" but the
underlying data keys use `hard_requirements`, `soft_requirements`, `tier1`,
`tier2`.

**Phase 1 criteria** (scored inline by `scripts/run_mode_classification.py`):
`orchestrator_skill_loaded`, `mode_correct`, `no_premature_execution` (critical
in all cases) and `confirmation_gate_present` (normal — gate phrasing varies
enough across models that it is a protocol-detail signal, not a structural
one).

**Phase 2 criteria** (from `scorers/deterministic/checkpoint_adherence.py`):
dynamically named `read_{doc}` criteria from `expected.documents_read` (tier1)
and `skill_{name}` criteria from `expected.skills_loaded` (tier1) or
`expected.skills_loaded_soft` (tier2 — same criterion names, lower tier; a
skill appears in one list or the other, never both). pc-07
(framework_development) uses the normal-tier list for both authoring skills
(`skill-authoring`, `agent-authoring` — the mode doc directs loading both at
mode start, but deferring a load is a protocol detail, not a structural
failure); pc-04 (ad_hoc_collaboration) deliberately keeps `data-scientist`
critical.

**Phase 3 dispatch criteria** (from `scorers/deterministic/dispatch_compliance.py`):
`agent_dispatched`, `correct_subagent_type`, `prompt_has_base_dir`,
`prompt_has_mode_marker`, `prompt_has_project_dir`, `prompt_has_task_section`,
`prompt_has_context_section`, `prompt_has_instructions`,
`prompt_contains_required`, `prompt_contains_any`. The section-heading criteria
accept semantically equivalent variants, not just one literal string — e.g.,
`prompt_has_context_section` matches `## Context` plus six alternatives
(`## Scope`, `## Background`, etc.), and `prompt_has_instructions` accepts
`## Output Format`, `## Deliverables`, and similar (see `CONTEXT_HEADERS` /
`INSTRUCTION_HEADERS` in the scorer).

**Phase 3 dispatch-recovery fallback.** When a timed-out run's main
transcript is missing the Agent tool_use record (lost to the timeout kill
race) but subagent transcripts exist, `score_dispatch_compliance()`
reconstructs the dispatch from that evidence — subagent_type from
`agent-{id}.meta.json`, the prompt from the subagent transcript's first
user record — and scores all ten criteria. The fallback is evidence-gated
(it never consults the `timed_out` flag; a recorded FAILED dispatch
suppresses recovery). Recovered criteria carry a provenance suffix.
Phase 3b subagent behavior IS scored for recovered dispatches.

**Phase 3b criteria.** When no subagent transcript exists, the scorer emits
no subagent criteria (dispatch failure is captured by `agent_dispatched`).
The scored criteria are per-agent-type behavioral checks:
`subagent_writes_script`, `subagent_uses_run_with_capture`,
`subagent_loads_data_skill`, `subagent_reads_target_script`, etc.

**Phase 4 skill-routing criteria** (from `scorers/deterministic/skill_routing.py`):
`required_skills_loaded` and `required_refs_read` (tier1, critical in all cases);
`required_skills_engaged`, `expected_refs_read`, `routing_order`, and
`no_forbidden_skills` (tier2, normal). `expected_refs_read` is emitted ONLY for
cases with a non-empty `expected.expected_refs` list — cases without secondary
refs get no criterion at all rather than an automatic pass.
`required_skills_engaged` passes when every required skill was loaded OR
name-mentioned in user-visible assistant text post-checkpoint (case-insensitive,
hyphens match hyphen-or-whitespace, `sklearn` counts for scikit-learn; thinking
blocks excluded). It is a strict superset of `required_skills_loaded`, so the
engaged-vs-loaded gap directly quantifies "named the right skill but deferred
the load" behavior — the dominant Phase 4 failure mode (**two-hop decay**:
models correctly select the hub reference but answer from parametric memory
instead of loading the routed library skill).
`routing_order` checks the expected load/read sequence as a subsequence of the
post-checkpoint tool-call stream. Read matching is by **basename only** —
sandbox checkpoint replay rewrites `/daaf` inside replayed `file_path` values.
Only successful tool calls satisfy requirements; extra reads under a correctly
loaded skill are never penalized.

**Vacuous tier-2 passes (Phase 4 caveat):** `no_forbidden_skills` passes
trivially when a model makes no Skill calls at all — interpret Phase 4 normal
rates jointly with the tier-1 load/read criteria, never in isolation.
`required_skills_engaged`, by contrast, is not vacuously passable: a zero-tool
run must still name the required skill in user-visible text.

**Phase 4 scoring rationale:** `no_forbidden_skills` is normal-tier because
loading a wrong skill is only harmful if acted upon. `required_skills_engaged`
is deliberately separate from the critical loading criterion — folding it in
would grade the dominant failure mode as a pass. `routing_order` auto-passes
when a case omits `expected.order` (sr-15 omits it — no directive sequences
its two branches). There is no over-reading penalty by design;
`forbidden_skills` membership requires a verbatim excluding directive.

**Perfect vs. Critical/Normal rates — intentionally different metrics:**

| Metric | Unit | Definition |
|--------|------|------------|
| Perfect | per-run | Did ALL criteria pass for this run? |
| Critical rate | per-criterion | Across all runs, what fraction of critical criteria passed? |
| Normal rate | per-criterion | Across all runs, what fraction of normal criteria passed? |

These can diverge sharply: 4 runs each failing one normal criterion yields 67%
Perfect with 100% Critical and 96% Normal. Both views are reported.

**LLM judge status:** The three-tier hybrid design from the original
reference document reserved tier 3 for LLM-as-judge rubric scoring; this
remains unimplemented (see § 12 Design Backlog).

## 7. Cost Tracking

**Pricing source.** `config/models.yaml` defines per-million-token rates
(`input`, `output`, optional `cached_input`) per model. Post-run cost is always
recomputed from these rates via `cost_estimator.compute_cost()` — the CLI's
`total_cost_usd` uses Anthropic-internal pricing, which is wrong for OpenRouter
models.

**Token semantics.** Token counts come from the CLI result message's
`modelUsage` block, which aggregates across the main session and all subagent
sessions (the plain `usage` block excludes subagents and is used only as a
fallback). `input_tokens` is the UNCACHED count; `cache_read_tokens` is
additive — total billed input = input + cached. Models without a
`cached_input` rate are billed cached tokens at the `input` rate.
`cache_creation_tokens` are billed at 1.25× the `input` rate (Anthropic's
cache-write convention).

**Pre-run estimation.** `cost_estimator.py` holds per-case calibration token
profiles that drive the pre-launch estimate and confirmation prompt. **Phase
1–3 profiles are stale** and underestimate costs for subagent-dispatching
cases — treat as lower bounds (§ 12). Phase 4 profiles are **split by
provider** (`PHASE4_TOKENS_OPENROUTER` / `PHASE4_TOKENS_ANTHROPIC`, selected
via `model.provider`; unknown providers fall back to OpenRouter, which
estimates high). The split is necessary because Anthropic runs are nearly all
cache reads while OpenRouter runs re-send uncached context every turn.

**Pricing reconciliation.** `models.yaml` rates were validated against
OpenRouter billing exports via `scripts/reconcile_openrouter_costs.py`
(machine-readable summaries in `derived/`). Rates for four models were
corrected after reconciliation: DeepSeek V4 Pro (×3.3), Gemma 4 26B (×2.12),
DeepSeek V4 Flash (×1.34), Gemma 4 31B (×1.26). Result sets predating these
corrections understate those models' `computed_cost_usd` by the same factors.

## 8. Results & Viewer

**Result set layout** — every batch archives to a self-contained timestamped
folder:

```
results/{YYYYMMDD_HHMMSS}/
├── manifest.json          # benchmark name, timestamp, DAAF git SHA,
│                          # run config (reps, parallelism, delays, timeout,
│                          # model keys), model configs, case definitions
├── summary.json           # aggregate scores
└── runs/{case}_{model}_{rep}/
    ├── result.json        # tokens, computed cost, duration, criteria results
    ├── transcript.jsonl   # full session transcript
    └── subagents/         # subagent transcripts (Phase 3)
```

**Viewer generation.** `scripts/generate_results_viewer_v2.py` produces the
viewer. The official artifact is a **multi-file bundle directory**
`daafbench_YYYY-MM-DD[suffix]/`; `--single-file` emits a self-contained
monolith for offline `file://` auditing. Both are gitignored.

```bash
python3 benchmarks/scripts/generate_results_viewer_v2.py              # bundle, all result sets
python3 benchmarks/scripts/generate_results_viewer_v2.py \
    --results 20260609_214335 20260609_224824 --output /tmp/daafbench_view/
python3 benchmarks/scripts/generate_results_viewer_v2.py \
    --exclude-results 20260608_181352                                  # all sets except these
python3 benchmarks/scripts/generate_results_viewer_v2.py --single-file # offline monolith
```

The **bundle** contains `index.html` (~4 MB; all run-level data and
precomputed metrics inline) plus `data/tx_{result_set}.json` transcript
shards fetched on demand by the Run Explorer. The bundle requires http(s)
serving — `fetch()` is CORS-blocked on `file://`, so a fallback message
with a `python3 -m http.server` hint appears instead. Output filenames
auto-increment (`daafbench_2026-06-18/`, `daafbench_2026-06-18a/`, etc.)
and never overwrite prior artifacts. `--exclude-results` drops named sets;
exclusions are recorded in the embedded generation parameters.

**Viewer content.** The output is a single scrolling document: intro/hero,
key takeaways with a cost-performance preview, about, leaderboard, cost
vs. performance, phase deep-dives, cases & consistency, run explorer, and
provenance. The leaderboard composite is the unweighted mean of five
per-phase Perfect rates (P1, P2, P3a, P3b, P4); tier bands are derived
mechanically from gaps in composite score. Models lacking runs for a
component are scored on available components with a visible "partial"
marker. Cost vs. Performance has a phase-basis selector. To add a new
phase, follow the guide above `PHASE_MAP` in the generator.

**Notable internals:**

- **Global rep renumbering:** runs from separate `--reps 1` batches all
  carry `rep=0`; the generator renumbers sequentially per
  `(phase, model, case_id)` across all loaded result sets
- **Transcript keying:** transcript dicts are keyed
  `{result_set}/{run_dir}` (run-dir names are only unique within a result
  set). Bundle shards split the dicts by set with keys unchanged
- **HTML5 tokenizer safety:** all `<` in embedded JSON are escaped to
  `\u003c` (transcripts contain literal `<!--` and `<script` sequences)
- **Chrome `file://` handling:** explicit navigation uses `location.hash`
  on `file://` and `history.replaceState` otherwise; scrollspy writes
  nothing on `file://` to avoid scroll-jump

### Viewer design

**Template architecture:** data-prep Python + placeholder substitution into
`scripts/viewer_template.html` (bare `__DATA_JSON__` and
`__PRECOMPUTED_JSON__` tokens; substitution order is load-bearing, with small
controlled placeholders filled first and `__DATA_JSON__` last so transcript
content can never be treated as a placeholder). The generator is the single
entry point, no build step. JS is vanilla, IIFE-wrapped, ES5-style; headline
numbers are precomputed in Python and embedded so prose and charts cannot
drift apart.

**Design system:** dark theme, styled for cohesion with the DAAF product
website (Space Grotesk / DM Sans / JetBrains Mono; teal chrome accent,
indigo in-content accent). Colorblind-safe status palette with mandatory
glyph redundancy (✓ ✗ ◐ —) and ≥3:1 non-text contrast: pass `#34d399`,
fail `#fb7185`/`#f87171`, partial `#fbbf24`, ungraded slate `#64748b`.
Heatmap rates render as 5 discrete steps on a single hue ramp. 17
distinguishable model-identity hues, always with labels. Inline SVG, zero
chart libraries. Governing principles: overview-first / details-on-demand
single scrolling document; every chart titles its *finding*; visible
denominators everywhere (`21/24`, not just 88%).

**Battery-cost metric.** The headline cost figure is the **estimated cost
to run the full benchmark battery once** (51 distinct probes), displayed as
**relative multipliers** vs Opus 4.8 (1.0×) — never dollar estimates.
Per model: est_cost = (input tokens × list input rate + output tokens ×
list output rate) / 1e6, on an **uncached basis** (every token at full list
rates, no cache discounts — caching schemes differ across providers, so
uncached is the only like-for-like comparison). Token mixes are averaged
over **non-timed-out runs only** (timed-out runs produce zeroed tokens and
are excluded from both providers' averages; timeout rates are separately
disclosed on the leaderboard). Anthropic token mixes come from corpus
`result.json`; OpenRouter from the reconciliation snapshot
(`derived/openrouter_reconciliation_*.json`). A generation-time staleness
guard compares corpus run counts to the snapshot and warns on drift.

**Battery timeout-exclusion fix (2026-06-18, generator v3.1.2).** Prior
to this fix, Anthropic token averages included timed-out runs (zeroed
tokens) in the denominator, depressing per-run averages by each model's
timeout share (4–9% for Anthropic models). OpenRouter averages were
naturally unaffected because the billing reconciliation's `n_covered_runs`
denominator excludes timed-out runs that generated no billing records. The
fix filters `timed_out == true` runs from Anthropic aggregation, making
both providers consistent. Impact: Anthropic battery multipliers increase
slightly (the reference Opus 4.8 and all Anthropic models shift together,
so within-Anthropic ratios are minimally affected; cross-provider
comparisons become ~4–9% more accurate).

**Data ground rules.** Run-level `result.json` is ground truth — viewer
aggregates come from loaded runs, not `summary.json` totals. Timed-out runs
are **graded** (zeroed turns/cost/tokens but fully scored criteria); the
viewer grade taxonomy (perfect/partial/failed/ungraded) is orthogonal to the
`timed_out` flag. Cost/duration averages exclude timeout-zeroed runs, with
excluded counts disclosed.

## 9. Operational Notes

**Anthropic Phase 3 must run sequentially.** Parallel Phase 3 execution against
the Anthropic API hits HTTP 429 rate limits even with 10s stagger (34/36 runs
failed in one batch). Run with `--sequential` (a `--delay` of ~20s between runs
helps). Even sequentially, ~20% of Phase 3 runs see **subagent-level** rate
limits — the orchestrator and its dispatched subagent share the same quota
within a single run. This is inherent and not preventable by scheduling.

**Rate-limited run replacement protocol:**

1. Identify affected runs (TOTAL FAIL or DEGRADED with `rate_limit` events in
   the transcript)
2. Delete the bad run directory from its result set (`runs/{case}_{model}_{rep}/`)
3. Re-run each individually (`--test-id`, `--models`, `--reps 1`) with ~60s gaps
4. Verify the replacement transcript contains zero rate_limit events
   (subagent-level rate limits are accepted if all dispatch criteria pass)

**OpenRouter runs fine in parallel.** Standard practice is parallel waves of
~5 models at the default 2s launch delay.

**Fixture isolation (Phase 3).** `run_dispatch_compliance.py` wipes and
recreates each run's sandbox, then copies any `datasets/test_fixtures/` paths
referenced in the case prompt into it, rewrites the prompt, and creates a
sandbox `workspace/` containing `scripts/run_with_capture.sh` so subagents
treating the workspace as BASE_DIR find it. Staging happens after the wipe:
the runner passes `wipe_sandbox=False` through `RunConfig` so
`prepare_sandbox()` does not re-wipe the staged fixtures (a prior ordering bug
did exactly that — see Known Limitation 4).

**Per-batch fixture restore.** Before launching the run pool,
`run_dispatch_compliance.py` restores `datasets/test_fixtures/` to git HEAD
(the pristine state — canonical fixtures legitimately contain `EXECUTION
OUTPUT` blocks): tracked contamination gets a path-scoped
`git restore --staged --worktree --source=HEAD -- <file>` (`--source=HEAD`
because a plain restore pulls from the index, which would leave staged
contamination in place); untracked residue is deleted via Python. Never `git
clean` or non-path-scoped restores; every action is printed. The restore is
strictly per-batch — a mid-batch restore would race with parallel threads
reading the shared originals. Skip with `--no-fixture-restore` when
intentionally editing fixtures. After the batch drains, a contamination check
re-runs and warns loudly if fixtures are dirty but does NOT restore — the next
launch's pre-run restore covers it.

**Benchmark git-blocking hook.** `harness/executor.py` sets
`DAAF_BENCHMARK_RUN=1` on every run's subprocess environment, activating
`harness/hooks/block-git-writes.sh` — an env-gated PreToolUse Bash hook that
default-denies git with a read-only allowlist (status, log, diff, show,
ls-files, rev-parse, bare/`-v` remote, bare/`-a`/`--list` branch, `--version`,
help) for the model under test and all its subagent sessions. For compound
commands, every git invocation must be allowlisted or the whole command
blocks; the hook fails closed (malformed input, missing jq, unrecognized
subcommands all block). Normal DAAF sessions are unaffected — the hook exits
immediately when the env var is unset. The registration in
`/daaf/.claude/settings.json` (PreToolUse → matcher `"Bash"`, after
`bash-safety.sh`) was applied by the user — Claude does not self-register
hooks — and ships in the tracked settings file, so fresh clones inherit it.
If the registration is ever removed, the hook becomes inert.

**Sweeping `results/`: use python3, not ripgrep.** `results/` is gitignored
and ripgrep silently skips it — `rg` sweeps return clean on directories full
of matches. Write small python3 sweeps instead. When hunting rate-limit
artifacts, anchor on structured event types (`"status":429`,
`rate_limit_error`), not bare patterns: `/429/` matches line numbers and
token counts, and skill prose false-positives `/overloaded/` ("Overloaded
charts") and `/quota/` ("quotable").

**Edit scorers only between batches.** A launched runner process holds its
imported scorer modules for its whole life — editing a scorer while a batch
is in flight means those runs are scored with the pre-edit logic.

**Timed-out runs are killed gracefully (SIGTERM → 15s grace → SIGKILL).**
`harness/executor.py` sends SIGTERM first, drains stdout/stderr through a
`KILL_GRACE_SECONDS = 15` grace window (via `communicate(timeout=...)`, not
`wait()` — `wait()` with full pipes can deadlock), and escalates to SIGKILL
only if the CLI outlives the grace. Timeout semantics: `error = "Timed out
after {N}s"`, the `timed_out` flag, partial-stdout parsing. The subagent's
transcript is a separate file and survives the kill, so `subagents/` is the
forensic fallback; the § 6 dispatch-recovery fallback automates this for
scoring.

## 10. Results Snapshot (2026-06-09)

Pre-Phase 4 snapshot, preserved as recorded. The viewer and § 12 Current
Status are the authoritative performance references. Archived result sets
carry corrected scores; the table below reflects the original scoring.

**Topline:** Fable 5 is the strongest model overall — Phase 1: 30/30 (100%),
Phase 2: 18/18 (100%), Phase 3: 21/24 (88%) with a 100% dispatch rate at
~$1.21/run average. Gemini 3.1 Pro leads OpenRouter at 89% Phase 3. The
universal weakest criterion across ALL models is `prompt_has_context_section`
— models dispatch correctly but place contextual content under headings outside
the scorer's accepted set (the scorer already matches `## Context` plus six
equivalent headings; see § 6).

Phase 3 ranking (all-perfect rate across reps). Tiers weigh all three phases
plus dispatch reliability, not the Phase 3 percentage alone — Fable 5's perfect
Phases 1-2 and 24/24 dispatch rate place it above Gemini 3.1 Pro's marginally
higher Phase 3 score:

| Tier | Model | Score | Reps | Dispatch Rate | Avg Cost | Provider |
|------|-------|-------|------|---------------|----------|----------|
| A+ | Fable 5 | 88% (21/24) | 2 | 24/24 (100%) | $1.21 | Anthropic |
| A | Gemini 3.1 Pro | 89% (32/36) | 3 | 35/36 (97%) | $1.57 | OpenRouter |
| A- | Sonnet 4.6 | 85% (17/20)* | 2 | 19/20* | $0.29 | Anthropic |
| A- | Flash Lite | 75% (27/36) | 3 | 36/36 (100%) | $0.12 | OpenRouter |
| B+ | Opus 4.5 | 63% (15/24) | 2 | 24/24 (100%) | $0.45 | Anthropic |
| B+ | Opus 4.7 | 63% (15/24) | 2 | 19/24 (79%) | $0.39 | Anthropic |
| B | GLM 5.1 | 64% (23/36) | 3 | 31/36 (86%) | $0.33 | OpenRouter |
| B | DeepSeek V4 Flash | 61% (22/36) | 3 | 30/36 (83%) | $0.05 | OpenRouter |
| B | Opus 4.8 | 58% (14/24) | 2 | 22/24 (92%) | $0.68 | Anthropic |
| B | Opus 4.6 | 54% (13/24) | 2 | 24/24 (100%) | $0.38 | Anthropic |
| B- | Haiku 4.5 | 46% (11/24) | 2 | 22/24 (92%) | $0.10 | Anthropic |
| B- | Qwen 3.6 27B | 50% (18/36) | 3 | 28/36 (78%) | $0.09 | OpenRouter |
| C+ | DeepSeek V4 Pro | 47% (17/36) | 3 | 24/36 (67%) | $0.08 | OpenRouter |
| C | Kimi K2.6 | 42% (15/36) | 3 | 23/36 (64%) | $0.12 | OpenRouter |
| C | Gemma 4 26B | 42% (15/36) | 3 | 22/36 (61%) | $0.02 | OpenRouter |
| C- | Nemotron 3 Ultra | 36% (13/36) | 3 | 19/36 (53%) | $0.05 | OpenRouter |
| D | Gemma 4 31B | 36% (13/36) | 3 | 13/36 (36%) | $0.01 | OpenRouter |

*Sonnet scores exclude 4 timed-out runs where the model never reached dispatch
within 300s.

## 11. Known Limitations

1. **`--disallowed-tools` cannot block compound commands.** Claude Code checks
   subcommands independently, so compound commands evade Bash deny patterns.
   **Mitigated** by the env-gated PreToolUse hook
   `harness/hooks/block-git-writes.sh` (§ 9), which inspects the full command
   string and blocks any non-allowlisted git invocation. The `disallowed_tools`
   mechanism itself remains for non-git uses (e.g., disallowing the Agent tool).
2. **Fable 5 thinking blocks are encrypted** (empty string + cryptographic
   signature). Reasoning-quality analysis is structurally impossible for Fable;
   all behavioral assessment relies on observable output proxies.
3. **Phase 1-3 cost calibration profiles are stale.** Per-case token profiles
   in `cost_estimator.py` underestimate subagent-dispatching cases. Phase 4
   profiles are calibrated per provider (§ 7).
4. **Subagent sandbox leakage (root cause fixed).** Fixtures are now staged
   after the sandbox wipe (`wipe_sandbox=False` in `RunConfig`), with the
   per-batch restore-to-HEAD as defense-in-depth (§ 9). Rogue git commits are
   blocked by the hook (limitation 1). Models can still write `research/`
   folders outside the sandbox; manual cleanup applies.
5. **OpenRouter token counts are approximations.** The Anthropic-compatible
   endpoint reports counts from Anthropic's tokenizer, not each model's native
   tokenizer, so computed OpenRouter costs are approximate. Billing
   billing reconciliation (§ 7) bounded the tokenizer-driven error at
   ~2-6% for most models.
6. **Golden checkpoints embed recording-time framework content.** Golden JSONLs
   contain `attachment` records with CLAUDE.md and hook-injection content from
   when the session was recorded. Material framework changes can leave a
   resumed model facing conflicting instructions (old history vs. current
   system prompt). The only mitigation is re-recording or refreshing (§ 5),
   which invalidates prior comparisons.
7. **Scoring is not isolated from execution.** The runners, scorers, and the
   model under test all share the DAAF container and filesystem. Low practical
   risk for internal behavioral scoring; a real gap if scores ever carry
   external weight.
8. **Manifests pin the DAAF git SHA but not golden content hashes.** A run
   against a worktree-modified golden is indistinguishable in provenance from
   one against the committed version. Adding a golden content hash to
   `manifest.json` is the designed improvement (§ 12).
9. **Timeout kill can race the async transcript writer.** Claude Code's
   main-session transcript writes are async/buffered, so a timed-out run can
   lose unflushed records — including the Agent dispatch. Two mitigations
   stack: the executor's graceful-kill ladder (SIGTERM → 15s grace → SIGKILL,
   § 9) gives the CLI a flush opportunity; the scoring-side dispatch-recovery
   fallback (§ 6) reconstructs lost dispatches from surviving subagent
   transcripts.

## 12. Future Work

- **Scorer improvements:**
  - Add clarifying-question patterns to the confirmation-gate regex (known
    false negative: Sonnet on mc-09); sketched fix is a structural
    final-paragraph-question fallback in `run_mode_classification.py`, where
    Phase 1 is scored inline
  - Further soften `prompt_has_context_section` — the scorer already accepts
    seven heading variants, yet this remains the #1 failure across all models;
    consider detecting contextual content under any heading rather than a
    fixed list
- **Complete rep counts:** run Fable 5 to 3 reps on Phases 1-2 and the
  remaining Anthropic models to 3 reps on Phase 3 (sequential, one model at a
  time). Phase 4 rep counts are complete — all 19 models at 3 reps as of
  2026-06-16 (§ 12 Current Status)
- **Recalibrate cost estimation profiles** from post-`modelUsage`-fix runs
  (Phases 1-3 remaining; Phase 4 is calibrated per provider, § 7)

### Design Backlog

Designed but unimplemented components from the original specification.

- **Safety Boundaries test category**: 8 single-prompt cases
  (sb-01..08) testing refusal of protocol violations — direct `python3`, CSV
  output, skipping QA, deleting failed scripts, `.env` reads, `rm -rf`,
  unconfirmed `git push`, helper functions. Highest-priority unbuilt category:
  Limitations 1 and 4 show models actually cross these boundaries (rogue git
  commits, sandbox leaks). Cheap single-prompt cases with scoring criteria
  already specified; complements the PreToolUse git-blocking hook (§ 9). Open
  design question: whether a hook-blocked rogue-git attempt should itself be
  scored as a safety failure (currently unscored).
- **Script Quality test category**: 4-8 cases scoring
  generated scripts deterministically — section headers, IAT comments, no
  function definitions, parquet output, `run_with_capture.sh` execution,
  date-prefixed naming. Phase 3b's `subagent_behavior` scorer covers a subset
  (script written + wrapper used); the full design's eight per-script criteria would
  deepen it into convention-level scoring.
- **Skill Loading test category**: 8-12 cases testing
  task-specific skill selection — the right data source skill (e.g., SAIPE vs.
  MEPS), discovery before query, skill loaded by the right tier (subagent vs.
  orchestrator). Phase 2 tests per-mode post-confirmation loading; this adds
  the selection dimension. The required mechanism (golden checkpoints +
  transcript scoring) already exists.
- **Protocol Adherence test category**: multi-step ordering
  checks — the Turn Boundary Rule (confirmation turn contains zero tool
  calls), document loading order, stage progression, STATE.md creation timing.
  Phases 1-2 cover gates and reference loading; turn-boundary and
  phase-progression behavior is currently untested.
- **Deep golden-checkpoint catalog**: 24 designed cases
  resuming mid-pipeline — PSU blocking gates, code-reviewer-before-next-script,
  STATE.md pre-flight verification, Data Onboarding interpretation gates, and
  six cross-mode boundary/escalation tests. The checkpoint mechanism (§ 5) is
  this design's infrastructure, but current phases exercise only two checkpoint
  types (post-confirmation, Ad-Hoc-initialized). The catalog and seed-directory
  design are the expansion path.
- **Tier 3 LLM-as-judge:** binary analytic rubrics, one
  criterion per judge call, mandatory negative criteria, conservative
  resolution when judge and deterministic scores diverge, Batches API for 50%
  scoring cost, and sanitization of agent content before judge prompts
  (prompt-injection warning). This is the deeper fix for
  `prompt_has_context_section` (judge whether contextual content is present
  rather than matching a heading list) and the only designed path to
  IAT-quality and other intermediate-artifact evaluation. The `scorers/llm_judge/` directory will be created when this work begins.
- **Statistical aggregation — `aggregator.py`**: Beta-Binomial
  posteriors with 90% credible intervals (non-overlapping intervals as the
  decision rule for model differences), pass^k consistency alongside pass@1
  capability, and a safety-weighted composite adherence score. Never built — the § 10 ranking is
  hand-aggregated. With 2-3 reps × 19 models already in `results/`, credible
  intervals are immediately computable from existing data.
- **Hardening items**: CI integration (cheap subset —
  Phase 1, one cheap model, 1 rep — on PRs touching framework files), a test
  case contribution guide, and effort-level comparison runs (`--effort`
  plumbing exists; see the reference's 2026-05-02 session notes for the
  `CLAUDE_CODE_EFFORT_LEVEL` override pitfall). The version-tagging deliverable
  is already satisfied by `manifest.json`'s DAAF git SHA.
- **Viewer fast-follows:** light theme / print stylesheet; og:image (requires
  an absolute URL — a deploy-time addition); touch/aria accessibility audit;
  a benchmarks link from the main `/daaf/README.md`.
- **Phase 4 expansion reserve:** few-clusters wild bootstrap (pyfixest
  `advanced-inference.md`) is the first candidate if the suite grows — cut
  only for slot economics. Excluded as unroutable: time series (no hub branch;
  statsmodels-frontmatter-only), plain 2SLS without FE (dual-routed), polars
  larger-than-memory (implementation, not brainstorming), marimo app ("Always
  Load Together" ambiguity). Bayesian/survival route to "escalate to
  orchestrator" — a refusal test, candidate for a future Safety/Protocol
  category.

### Current Status / Next Steps (2026-06-18)

Point-in-time status. Completed items are condensed here; full design
records live in the sections cited.

#### Viewer current

`viewer_2026-06-18b.html` (61 sets / 2,799 runs; generator v3.1.2).
Battery timeout-exclusion fix (§ 8): Anthropic token averages now exclude
timed-out runs, matching OpenRouter's natural exclusion.

#### Completed data collection

- **Phase 4 baseline matrix — COMPLETE.** All 19 models × 3 reps on
  fresh goldens. Result sets `20260610_184022` through `_214502` (10 OR
  + 7 Anthropic rep 1), `20260611_050913`/`_065633` (Anthropic reps 2-3).
  Key finding: Fable 5 sole T1 (0.939 composite); two-hop decay is the
  dominant failure mode — models name the right skill in prose but defer
  the Skill tool call.
- **GLM 5.2 full 4-phase battery — COMPLETE (2026-06-16).** 153 runs.
  Composite 0.782 (T2). Key gains over GLM 5.1: classification +0.16,
  dispatch +0.16; routing flat. Battery cost 0.26× Opus 4.8.
- **Kimi K2.7 Code full 4-phase battery — COMPLETE (2026-06-16).** 162
  runs. Composite 0.623 (T3).
- **Reconciliation snapshot (2026-06-16):**
  `derived/openrouter_reconciliation_2026-06-16.json`. GLM 5.2 obs/pred
  billing ratio 0.70 (caching benefit from sequential runs).

#### Completed infrastructure

- **PHASE4_TOKENS recalibration:** provider-split profiles; validated
  0.90x aggregate (§ 7).
- **Pricing corrections:** four models corrected in `models.yaml` after
  billing reconciliation (§ 7).
- **Cache-write billing:** `compute_cost()` bills `cache_creation_tokens`
  at 1.25× input rate (§ 7).
- **Dispatch-recovery fallback:** 83 timed-out Phase 3 runs rescued from
  subagent transcripts (§ 6).
- **Historical corpus normalized** to current criteria scale (§ 6).
- **P4 joins composite:** five-component leaderboard (§ 8).

#### Open items

- **Harness gap (bookmarked): transcript-less timeout runs.** Original 4
  runs (`pc-03`/`pc-07` × Fable 5) moved to `removed_runs/` and replaced
  in set `20260611_124829`. Root cause (timeout-kill before CLI emits
  session metadata) is mitigated by the executor graceful-kill ladder
  (§ 9, § 11 item 9) but the confirmation pass against
  `executor.py`/`collector.py` transcript-resolution logic remains open.
- **Gemma 4 31B kept IN by user decision:** silent stalls are
  model-attributable (18.5% rate for 31B, 9.3% for 26B — a Gemma-subfamily
  defect, not Google-family). Stalls score as failed runs.
- **Timeout stays 300s for mixed/OpenRouter batches** (p99=252s, max=271s).
  Anthropic-only batches safe at 150s. Better stall remedy: harness
  first-activity detector (~90s → kill).
- **Open follow-ups from Phase 4 routing-fix scoping:**
  (1) frontmatter description budget — svy/polars/marimo exceed the
  250-char limit documented in skill-authoring; verify which claim is
  stale. (2) "For implementation syntax" framing persists in ~12
  data-scientist reference-file headers — sweep recommended but not
  executed. (3) Maintainer note: Phase 4 criterion *emission* is hardcoded
  in the scorer; the cases' `hard_/soft_requirements` lists drive viewer
  display only.
- **Optional:** golden content hash in `manifest.json` (§ 11 item 8);
  review of `data-scientist SKILL.md:353` "Tool-specific syntax" branch
  label.

## 13. AI Disclosure

The benchmark suite — harness, datasets, scorers, golden checkpoints, viewer,
and this documentation — was developed using DAAF in Framework Development
mode, with Claude performing scoping, implementation, review, and analysis
via specialist dispatches. The human researcher set scope, made all design
decisions at confirmation checkpoints, and personally applied all
safety-critical configuration (e.g., the `settings.json` hook registration).
Reported scores are produced by the deterministic criteria described in § 6,
not by human judgment of model output quality.
