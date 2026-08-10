# DAAF Framework Adherence Benchmarks

Benchmark system for evaluating LLM **behavioral conformance** to DAAF orchestrator
protocols. It answers one question: when a model is placed inside the real DAAF
container — hooks firing, skills discoverable, agents dispatchable — does it follow
the framework's protocols?

---

## 1. What This Is

> **Just want to pick a model?** This README documents the benchmark's
> internals for contributors. The user-facing guidance distilled from these
> results lives in the FAQ —
> [Which Claude model should I use?](../user_reference/07_faq_technical.md#q-which-claude-model-should-i-use)
> — and the live results page is
> [daaf.openaugments.org/bench](https://daaf.openaugments.org/bench/).

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

**Model matrix:** 36 registry entries across three explicit providers. The
matrix is defined in `config/models.yaml`; provider labels describe the measured
route, not interchangeable billing aliases.

| Provider | Entries | Route and accounting basis |
|----------|--------:|----------------------------|
| `anthropic` | 9 | Claude Code subscription route for Haiku 4.5, Sonnet 4.6/5, Opus 4.5/4.6/4.7/4.8/5, and Fable 5 |
| `openrouter` | 24 | OpenRouter's Anthropic-compatible endpoint; includes GLM, Kimi, Qwen, Gemma, DeepSeek, Gemini, Nemotron, Inkling, and GPT entries |
| `chatgpt-subscription` | 3 | Local provider shim to the deployed ChatGPT/Codex subscription backend for GPT-5.6 Luna, Terra, and Sol; included-capacity billing and separate API-equivalent accounting |

GPT-5.6 Luna, Terra, and Sol each have deliberately distinct OpenRouter and
ChatGPT-subscription entries. The OpenRouter keys are `gpt-56-luna`,
`gpt-56-terra`, and `gpt-56-sol`, with `openai/gpt-5.6-*` routing IDs; the
subscription keys append `-chatgpt` and use the corresponding bare `gpt-5.6-*`
IDs. Each subscription entry sets a 370,000-token effective input ceiling for
this ChatGPT/Codex lane. Sol's ceiling was measured on 2026-07-16; Luna and Terra
remain conservatively inferred to share the lane cap until individually measured.
Each subscription entry maps both `ANTHROPIC_DEFAULT_OPUS_MODEL` and
`ANTHROPIC_DEFAULT_SONNET_MODEL` to its own bare parent ID and deliberately omits
`CLAUDE_CODE_SUBAGENT_MODEL`, preserving semantic tier selection while keeping
both tiers model-pure. The executor removes any ambient flatten selector before
applying model-specific overrides, so entries that explicitly declare one still
retain it. Never retry an OpenRouter-prefixed slug automatically if the
deployed-path probe rejects a bare subscription slug.

The GPT-5.6 -pro slugs and GPT-5.5 Pro were tested and REMOVED from the
OpenRouter matrix (2026-07-10): the -pro variants hit hard "Prompt is too long"
errors at realistic DAAF context sizes through that endpoint (~4x inflated token
accounting against a ~200k ceiling; evidence in the models.yaml REMOVED block),
and GPT-5.5 Pro's premium API pricing made its battery not worth running. No
live ChatGPT-subscription Luna probe or behavioral run is claimed in this
document; the commands below are an authorized-style staged procedure.

**Scope:** The original design specified six test categories; four are
implemented as the phases above. The remaining designed-but-unbuilt
categories are catalogued in the Design Backlog (§ 12).

### Related suite: DAAFBench Analytics

This suite measures **behavioral conformance to orchestrator protocol**. A sibling
suite, **DAAFBench Analytics** (`analytics/`), measures an orthogonal construct:
whether the analytical *work* is correct, whether the model notices when the data or
code is deliberately wrong, and whether it discloses that to its caller — graded with
and without the DAAF agent layer (a DAAF-vs-bare arm comparison). The two share harness
machinery (executor, model pinning, fixture staging, viewer) but do not overlap in what
they score. DAAFBench Analytics is at the specification stage; see
[`analytics/SPEC.md`](analytics/SPEC.md) and [`analytics/README.md`](analytics/README.md).

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

**Phase 3 child-model purity.** Phase 3 archives one of three states:
`verified` when every model ID observed on readable child-transcript assistant
records exactly matches the requested wire ID; `failed` when any observed child
ID differs; and `unverifiable` when no child transcript or no child model field
is available. The comparison deliberately performs no alias normalization and
retains raw IDs. This is Claude-CLI child-transcript evidence, not
backend-confirmed identity. All three GPT-5.6 ChatGPT-subscription entries pin
the operative Opus and Sonnet tier aliases to the parent ID and deliberately
omit `CLAUDE_CODE_SUBAGENT_MODEL`; that configuration plus `verified` establishes
only the observable CLI boundary and does not prove what alias resolution a
private backend may perform.

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
                  └─ archive to results/{YYYYMMDD_HHMMSS}/  (PROGRESSIVE)
                       manifest.json + initial partial summary.json
                       written BEFORE the pool starts; each run's
                       runs/{case}_{model}_{rep}/ (result.json,
                       transcript.jsonl, subagents/) written as it
                       completes, with summary.json/manifest.json
                       re-rolled incrementally after every run
```

**Progressive archiving (2026-07).** Persistence is no longer all-or-nothing. The
runner creates `results/{timestamp}/` and seeds `manifest.json` plus an initial
`summary.json` (`"partial": true`, `"runs_completed": 0`) *before* the run pool
launches. Each worker writes its own `runs/{name}/result.json` (+ transcript +
`subagents/`) the moment it finishes, and the runner then recomputes and
atomically rewrites `summary.json` and `manifest.json` over the completed-so-far
set. A `try/finally` finalizer performs a last rollup that flips
`"partial": false` only when every expected run completed. Consequences: a killed
or crashed pass leaves a self-describing partial archive (never an empty one),
and the viewer can render a batch while it is still running. Rollup writes are
serialized by a module-level lock and use write-`.tmp`-then-`os.replace()` atomic
writes, so a reader never sees a half-written rollup. `--sequential` behaves
identically. Per-run artifact writes are existence-guarded, so each run's files
are written exactly once across the repeated rollups.

**Concurrency cap.** The parallel pool is
`ThreadPoolExecutor(max_workers=min(len(runs), --max-concurrent))`, capped at
`MAX_CONCURRENT_RUNS = 5` by default (was previously uncapped at `len(runs)`).
Per-run state (sandbox dir, uuid4 session ids, transcript dirs) is fully
isolated, so the cap is a resource-pressure guard, not a correctness one.
`--delay` still staggers submits independently of the cap.

**Error-class counters.** Each `result.json` carries an additive
`"error_counts": {"hook_blocks", "tool_failures", "tool_failures_unclassified"}`
object, aggregated into `summary.json`. A run's error-bearing tool results are
classified (see `scorers/deterministic/error_classification.py`) as `hook_block`
(refused by a DAAF/benchmark PreToolUse hook, permission deny, or tool-availability
policy — the framework acting as designed) vs `tool_failure` (a genuine
tool/API/environment error). Signatures were derived empirically from archived
transcripts; anything error-bearing that matches neither list is counted as
`tool_failures_unclassified` rather than silently folded into `tool_failures`.

Additionally, each entry in a run's `tool_failures` list carries a per-entry
`tool_failure_class` tag assigning a finer operational CAUSE (additive and
non-scoring; see `classify_tool_failure_class` in
`scorers/deterministic/error_classification.py`). The taxonomy is precedence-
ordered (first match wins): `policy_hook` (a DAAF/benchmark hook or permission
block — the framework acting as designed), `infra_transient` (a dropped/stalled
stream or empty-200 — a retry candidate), `capacity_limit` (prompt-too-long, a
quota refusal, or a standalone HTTP 429), `infra_config` (a ChatGPT/Codex lane
refusal of the CONFIGURED child model id), and `model_error` (everything else,
including a lane refusal naming a DIFFERENT id than the configured child — the
model mis-routing itself). The field is additive: archives written before it was
introduced simply omit it.

**Run-lifecycle watchdog.** `executor.execute_run()` no longer blocks in a single
`communicate(timeout=timeout)` call. When a runner opts in, a watchdog thread
polls the run every `--watchdog-poll` seconds (default **60s** — a longer interval
avoids constant firing across the 5 concurrent runs) and can end a run before the
900s wall-clock backstop for two reasons. Stdout is drained by a background reader
thread the whole time, because `claude -p --output-format json` emits its JSON only
at exit and a naive wait loop would deadlock once the pipe buffer fills. The 900s
timeout remains the unconditional backstop. **Backward compatibility:** with neither
watchdog feature enabled (the `RunConfig` defaults), `execute_run()` takes the
original single blocking `communicate()` path, byte-identical to the pre-watchdog
harness.

- **Score-complete early stop** (`status: "completed_early"`) — **OFF by default
  since 2026-07-29; opt-in via `--early-stop`, dispatch_compliance only.** When
  enabled, every poll runs the *real* deterministic scorers against the live
  transcripts; when every scored criterion has PASSED, the executor does **one
  confirmation poll** on the next tick and, if still all-PASS, gracefully kills
  the run (`_graceful_kill` SIGTERM→15s→SIGKILL ladder) and marks the run
  `early_stopped`. The original design rationale was a *monotone-pass fairness
  argument*: all ten dispatch criteria were believed to lock PASS at the Agent
  call and the subagent-behavior criteria at the subagent's actions, so
  terminating on all-PASS could not change the score. **That argument was
  falsified in practice (2026-07-29):** an Agent call's success actually settles
  at its *tool_result*, which lands only when the subagent finishes — the
  graceful kill can abort an in-flight dispatch, flipping its tool_result to
  `is_error=true`, causing archival scoring to fail the dispatch and (by design)
  suppressing the dispatch-recovery fallback. Observed: 4 of 59 `completed_early`
  runs scored as dispatch failures despite live all-PASS; all 59 were quarantined
  (`results/_quarantine_2026-07-29_earlystop/`) and re-run. Early stop also
  truncates usage capture (`output_tokens=None` — the kill precedes the CLI's
  final usage summary), breaking cost comparability. Hence the default flip.
  The other three phases each have a **monotone-FAIL negative criterion**
  (`no_premature_execution`, `no_forbidden_skills`, `no_tool_calls_of_type`)
  that starts PASS and can only flip to FAIL; early stop was never wired there.
  When enabled, the confirmation poll protects the subagent-transcript flush
  race (the check returns "not done" until the subagent transcript exists on
  disk and its behavior criteria pass), and a scorer exception during polling is
  swallowed as "not done" (never kills a run) and logged — but note the flush
  race is distinct from the tool_result race above, which the confirmation poll
  does NOT close. Historical `completed_early` runs count as completions for
  parity/validity purposes, subject to the quarantine above. For duration/latency
  aggregates they contribute an additive `score_complete_seconds`
  (time-to-demonstrated-compliance: launch → first all-criteria-pass, excluding
  the confirmation poll and kill tail) rather than their truncated wall clock
  (see § 8).
- **Hung-run / stall detection** (`status: "stalled"`, distinct from `timed_out`),
  wired for **all four phases**. Staleness is computed as max-recency across the
  parent transcript **and** all subagent transcripts (a parent-only monitor
  false-alarms while the parent blocks on long subagent work). A single staleness
  reading over `--stall-threshold` seconds (default **330s**) counts as one stalled
  read; **two consecutive** stalled reads (≈120s of confirmation on top of the 330s
  cutoff, at the 60s poll spacing) are required before the run is killed as
  stalled. A *first-activity* rule additionally counts a stalled read when **no**
  parent-or-subagent transcript exists at all past ~90s. The 330s threshold and the
  never-act-on-a-single-reading rule are empirically grounded in the K3 rerun
  campaign (`research/2026-07-18_FrameworkDev_DAAFBench_StaticAudit_Fable/2026-07-21_rerun-campaign_progress.md`):
  **296s of legitimate dead air** was observed on a run that then passed
  everything, so the former 240s threshold false-positives; ~330s-plus with
  consecutive confirmations is the validated cutoff.
- **Stall auto-relaunch.** A stalled rep is relaunched from a freshly wiped/staged
  sandbox up to `--stall-retries` times (default **1**). The relaunch logs the
  stall anatomy (staleness poll history, stalled-read count) and gets a new session
  id and pristine sandbox. A rep that stalls **again** after its last retry is
  recorded permanently with `status="stalled"` (no relaunch loops). Each run's
  `result.json` carries an additive `stall_relaunch_count` and a `stall_attempts`
  list (one `{attempt, stall_diagnostics}` entry per stalled attempt, including
  those that were retried away) so a run that stalled once then passed is legible
  from the archive alone rather than only in the console log. Per-run archiving and
  the error-class counters (above) run for `completed_early` and `stalled` runs
  exactly as for normal completions.
- **Lookup-error accounting.** `stall_diagnostics` carries a `lookup_errors`
  count — the number of transcript-recency lookup exceptions observed across a
  run's staleness polls. A staleness lookup that throws is treated as
  inconclusive (not as dead air), so a `lookup_errors > 0` signal marks a
  monitoring/lookup regression to investigate rather than a genuine model stall,
  keeping a lookup fault from masquerading as a stall.

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
| `harness/` | Core machinery: `executor.py` (CLI invocation), `checkpoint_manager.py` (golden cloning + sandbox lifecycle), `cost_estimator.py` (legacy and subscription accounting), `artifacts.py` (schema-v2 serialization and preflight helpers), `models.py` (dataclasses), `model_loader.py` (registry/provider env wiring), `route_provenance.py` (fail-closed ChatGPT route contract), `collector.py`, and benchmark-scoped `hooks/` (see § 9) |
| `scorers/deterministic/` | `checkpoint_adherence.py`, `dispatch_compliance.py`, `subagent_behavior.py`, `skill_routing.py` (Phase 1 is scored inline by `scripts/run_mode_classification.py` — see § 6) |
| `datasets/` | `{phase}/cases.jsonl` plus `test_fixtures/` (buggy scripts and data for debugger/code-reviewer cases) |
| `golden/` | Golden checkpoint JSONLs (see § 5) |
| `config/` | `models.yaml` — model matrix with pricing |
| `scripts/` | Phase runners, `probe_model_route.py`, `generate_goldens.py`, viewer generation sources, `refresh_golden_checkpoint.py`, `reconcile_openrouter_costs.py`, and `clean_sandbox.sh` |
| `results/` | Timestamped, self-contained result sets |
| `_sandbox/` | Per-run scratch directories (transient, gitignored) |

> **DAAFBench is not deployment smoke testing.** DAAFBench scores model
> behavioral adherence to framework protocols under controlled cases and preserves
> run evidence. `scripts/deploy_smoke/` instead verifies that a live DAAF install
> functions end-to-end in its configured provider route; it does not produce a
> behavioral-adherence score. The smoke suite reuses selected executor parsing,
> environment, and shutdown machinery, but its tiered probes and reports have a
> different purpose. Use the `daaf-deploy-smoke-testing` skill for deployment health.
> The route probe documented below belongs to DAAFBench: it is a bounded selection
> gate before behavioral cases, not a replacement for the smoke suite.

### ChatGPT-subscription deployed-path condition

`chatgpt-subscription` measures the normal deployed DAAF path: Claude Code calls
the local provider shim, `/health` reports `backend_mode=chatgpt`, and tool
sanitization remains enabled. This is a system/deployment condition, not an
isolated or raw-model condition. A result must retain that sanitizer state as
provenance; comparisons against sanitizer-off experiments require a separately
labeled condition.

The route contract fails closed before `claude -p`. It requires coherent ambient
`DAAF_PROVIDER_SHIM=openai`, `SHIM_BACKEND_MODE=chatgpt`, and local endpoint
settings, then validates a live, zero-model-cost `/health` response immediately
before a batch and again before each run. Required health facts include the
ChatGPT backend mode and production Codex backend, `sanitize_tools=true`,
readable auth storage, an `ok` status, and a nonempty shim version. Only an
explicit allowlist is archived: local endpoint origin, backend/mode, shim
version, sanitizer condition, auth-store readability, reasoning/verbosity when
available, and capture time. Credentials, raw health extras, and full
environment variables are excluded.

## 4. Quick Start

**Environment.** Anthropic models authenticate via the container's Claude Code
OAuth — nothing to configure. OpenRouter models require `OPENROUTER_BASE_URL`
and `OPENROUTER_AUTH_TOKEN`, set on the host via `environment_settings.txt` in
the `daaf-docker/` folder (injected at container startup). If these are missing,
`model_loader.py` skips all OpenRouter models with a warning rather than failing.
The ChatGPT-subscription entry uses the already deployed local provider shim and
never reads credential files. Registry loading and `--help` perform no health or
model call; the explicit preflight is where route coherence and secret-safe
`/health` provenance are checked.

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
| `--models a,b` | all | Comma-separated model keys (lowercased names from models.yaml, spaces → hyphens, dots removed: `fable-5`, `sonnet-46`, `deepseek-v4-flash-0731`). Keys come from this registry transformation, not bare model names — `sonnet`/`haiku` are not valid keys |
| `--provider X` | all | `anthropic`, `openrouter`, `chatgpt-subscription`, or `all` |
| `--test-id a,b` | all | Specific case IDs (e.g., `mc-01,mc-05`) |
| `--sequential` | off | Run one at a time instead of parallel |
| `--delay S` | 2 | Seconds between parallel launches (ThreadPoolExecutor stagger). Parallel-mode only — the sequential loop has no sleep, so this flag is a no-op with `--sequential` |
| `--max-concurrent N` | 5 | Cap on simultaneously in-flight runs (`max_workers = min(len(runs), N)`). Parallel-mode only. Independent of `--delay`, which staggers submits |
| `--timeout S` | 900 | Per-run timeout in seconds. Uniform 900s logistical cap baked into all four runners (2026-07-21 walltime redesign; formerly 120/180/300/300 per-phase). The cap is deliberately high so runs complete rather than censor — duration is now a measured axis. Pass explicitly to override; the uniform `DEFAULT_TIMEOUT_S` fallback only fires if a caller passes `timeout_override=None` programmatically |
| `--watchdog-poll S` | 60 | Watchdog poll interval in seconds — how often the executor checks transcript staleness, plus score-complete early stop when enabled via `--early-stop` (§ 3, Run-lifecycle watchdog) |
| `--stall-threshold S` | 330 | Staleness cutoff in seconds for one stalled read (K3-validated; 296s of legitimate dead air was observed on a passing run, so 240s false-positives). Two consecutive stalled reads trigger a stall kill |
| `--stall-retries N` | 1 | Times to relaunch a stalled rep from a fresh sandbox. A rep that stalls again after its last retry is recorded permanently with `status="stalled"` |
| `--early-stop` | off | **Opt IN** to score-complete early stop (`run_dispatch_compliance.py` only — the one phase where it is wired). **Default flipped OFF 2026-07-29:** the graceful kill can abort an in-flight Agent dispatch and corrupt the archived score, and it truncates usage capture (§ 3). Stall detection is independent and always runs |
| `--no-early-stop` | off | **Deprecated no-op** since the 2026-07-29 default flip (early stop is already off). Kept for command-line compatibility; overrides `--early-stop` if both are given. Still accepted-but-inert on the other three runners, where early stop was never wired |
| `--yes` / `-y` | off | Skip the runner's cost confirmation prompt |
| `--preflight-only` | off | Select models/cases and validate applicable provider routes, then exit before estimates, checkpoints, sandboxes, model execution, or result artifacts |

`run_dispatch_compliance.py` additionally accepts `--no-fixture-restore`,
which skips the pre-batch fixture restore (§ 9).

Before launching, the runner prints a per-model cost estimate and asks for
interactive confirmation when the estimate exceeds $0.50 (suppressed by `--yes`).

Typical targeted invocation:

```bash
python3 benchmarks/scripts/run_dispatch_compliance.py \
    --models fable-5 --reps 1 --sequential --delay 20 --timeout 900 --yes
```

See § 9 before launching Anthropic Phase 3 runs — they must be sequential.

### Zero-model-cost preflight

All four phase runners implement the same `--preflight-only` gate. The runner
parses arguments, loads and filters the registry and selected cases, then runs
the shared provider preflight. On success it exits before cost estimation,
checkpoint cloning, fixture restoration/staging, sandbox creation, executor
calls, or result-directory creation. It therefore consumes zero model or
subscription capacity and creates no benchmark result. On a route mismatch it
exits nonzero and still creates no result. The health request itself is a local
shim control-plane call; it is not a model request.

```bash
python3 benchmarks/scripts/run_mode_classification.py --provider chatgpt-subscription --models gpt-56-luna-chatgpt --test-id mc-01 --reps 1 --sequential --preflight-only
python3 benchmarks/scripts/run_post_confirmation.py --provider chatgpt-subscription --models gpt-56-luna-chatgpt --test-id pc-01 --reps 1 --sequential --preflight-only
python3 benchmarks/scripts/run_dispatch_compliance.py --provider chatgpt-subscription --models gpt-56-luna-chatgpt --test-id dc-01 --reps 1 --sequential --preflight-only
python3 benchmarks/scripts/run_skill_routing.py --provider chatgpt-subscription --models gpt-56-luna-chatgpt --test-id sr-01 --reps 1 --sequential --preflight-only
```

Do not confuse these commands with the model-selection probe. Preflight verifies
the declared local route and daemon health without asking the backend to accept
a model slug.

### Bounded model-route probe

The standalone probe opens one fresh session, permits at most one turn, requests
no tool work, disallows the standard built-in tools through the existing
executor, and requires `response_text.strip() == expected_text`. It accepts one
singular `--model` key only, defaults to the ChatGPT Luna entry, rejects
non-subscription providers, and never falls back to `openai/gpt-5.6-luna`.
Unless `--yes` is supplied, it warns and asks before consuming
ChatGPT-subscription capacity.

```bash
python3 benchmarks/scripts/probe_model_route.py --model gpt-56-luna-chatgpt --expect-text LUNA_PROBE_OK --yes
```

Preflight or confirmation failure creates no probe artifact. Once execution has
begun, success, mismatch, execution error, missing response, and timeout all
produce a schema-v2 `probe.json` beneath the gitignored
`results/probes/{timestamp}_{collision-suffix}/` path before the command exits.
The artifact stores the exact prompt and expected text, response comparison,
session and nullable transcript reference, secret-safe route/sanitizer
provenance, separated model-identity evidence, observed usage completeness,
actual billing treatment, API-equivalent exact/scenario fields, and the evidence
caveat.

A pass proves only that the deployed shim-plus-sanitizer path accepted the
requested bare slug and returned the exact expected response. It does **not**
prove that the private ChatGPT backend performed no internal alias resolution,
and it does not establish backend-confirmed model identity when that field is
null. It also does not prove agentic/tool compatibility; no tool work is
requested by this probe.

### Recommended staged ChatGPT Luna procedure

After implementation review and a successful zero-cost preflight, execute the
following gates **sequentially**, stopping on the criteria in § 9. This is a
recommended authorized-style procedure, not a record that these live calls have
already run:

1. Route probe: `probe_model_route.py --model gpt-56-luna-chatgpt --expect-text LUNA_PROBE_OK --yes`
2. Phase 1: `run_mode_classification.py --provider chatgpt-subscription --models gpt-56-luna-chatgpt --test-id mc-01 --reps 1 --sequential --yes`
3. Phase 2: `run_post_confirmation.py --provider chatgpt-subscription --models gpt-56-luna-chatgpt --test-id pc-01 --reps 1 --sequential --yes`
4. Phase 3: `run_dispatch_compliance.py --provider chatgpt-subscription --models gpt-56-luna-chatgpt --test-id dc-01 --reps 1 --sequential --yes`
5. Phase 4: `run_skill_routing.py --provider chatgpt-subscription --models gpt-56-luna-chatgpt --test-id sr-01 --reps 1 --sequential --yes`

Pause after the four representative behavioral cases. Do not infer a
three-repetition reliability rate from these one-run gates, and do not start a
reliability sample without a separate decision.

### Adding a New Model

Onboarding a model is: author the registry entry → verify its facts online →
prove the route before spending real capacity → run the full battery → fold the
results into the viewer. The DeepSeek V4 Flash 0731 entry (`config/models.yaml`,
added 2026-08-02) is the current worked example; read it and its neighbors before
authoring. Follow the steps in order — each gate is cheap insurance against the
next, more expensive one.

1. **Author the registry entry** in `config/models.yaml`, matching the shape of an
   existing entry of the same provider. Fields:
   - `id` — the routing slug. For OpenRouter this may carry an optional
     `:provider/quant` endpoint pin (e.g. `deepseek/deepseek-v4-flash-0731:novita/fp8`);
     the pin selects a specific serving endpoint (quantization, uptime, price). For
     Anthropic use the bare model id; for `chatgpt-subscription` use the bare
     `gpt-5.6-*` id.
   - `name` — the human label. The **selectable registry key** is derived from it by
     `model_loader.py` (`load_models`): lowercase, spaces → hyphens, dots removed
     (`"DeepSeek V4 Flash 0731"` → `deepseek-v4-flash-0731`). Confirm the derived key
     does not collide with an existing entry, and that it reads well as a `--models`
     value (§ 4 flag table). To pin an explicit key instead of deriving one, set the
     optional `key:` field (the three `chatgpt-subscription` entries do this to append
     `-chatgpt` while keeping a bare `id`).
   - `provider` — `anthropic`, `openrouter`, or `chatgpt-subscription`; controls the
     env-var wiring injected by `model_loader.py` (§ 4 Environment).
   - `cost_tier` — coarse `low`/`medium`/`high` label.
   - `pricing` — per-million-token `input` / `output`, plus `cached_input` when the
     endpoint discounts cache reads (the 0731 Novita endpoint lists one, so it is
     declared). `chatgpt-subscription` entries carry `api_equivalent_pricing` instead
     (§ 7 dual ledger), not `pricing`.
   - `env_overrides` — **child-model purity pinning** (models.yaml header, "CHILD-MODEL
     PURITY PINNING"). OpenRouter/Anthropic entries pin all three selectors
     (`ANTHROPIC_DEFAULT_OPUS_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`,
     `CLAUDE_CODE_SUBAGENT_MODEL`) to the entry's **own `id`** so dispatched children
     stay on the model under test. `chatgpt-subscription` entries deliberately pin only
     the two Opus/Sonnet aliases and omit `CLAUDE_CODE_SUBAGENT_MODEL` (its
     higher-precedence flatten would bypass semantic tier selection).

2. **Verify every factual field online** and cite it inline. Pricing, context length,
   and the endpoint pin must be checked against OpenRouter
   `GET /api/v1/models/{slug}/endpoints` (or provider docs) with a comment recording
   the source and **accessed date** — the 0731 entry's comment is the template
   (verified 2026-08-02: tag, quantization, `context_length`, uptime, and the three
   list rates). Document *why* the specific endpoint pin was chosen (quantization,
   uptime, price) when more than one endpoint serves the slug. List prices are
   **provisional until billing reconciliation** — mark them so, as the 0731 comment
   does, deferring to the 2026-06-11 reconciliation precedent on the older DeepSeek
   entries (§ 7).

3. **Set `wire_id` with discipline.** Declare `wire_id` only when the wire-observed
   `message.model` differs from the routing `id`. OpenRouter `:provider/quant` pins are
   dropped on the wire (directly observed 2026-07-24/25), so a pinned OpenRouter id
   needs a `wire_id` equal to the unpinned slug; Anthropic bare aliases *sometimes*
   resolve to dated snapshots (`claude-opus-4-5` → `-20251101`) and sometimes do not
   (`claude-opus-5` stays bare) — so wire_id must be **OBSERVED, not assumed**. When you
   have not yet observed it, mark the value `INFERRED` in a comment (as the 0731 entry
   did before its probe run) and confirm it on the first probe run below, then update the
   comment with the observing `result.json` path — the 0731 entry's now-`OBSERVED`
   comment shows the finished form. Purity comparison performs no alias normalization, so
   an inaccurate `wire_id` will read as a purity failure.

4. **Zero-cost preflight.** Run `--preflight-only` for the new key to confirm route and
   env coherence before spending anything (§ 4 Zero-model-cost preflight). For an
   OpenRouter model this validates that `OPENROUTER_*` env vars are present and the key
   filters correctly; it creates no result and makes no model call.

5. **Paid single-test wire probe.** Run one sequential 1-rep case (e.g.
   `run_dispatch_compliance.py --models <key> --test-id dc-01 --reps 1 --sequential --yes`)
   to confirm the wire_id and child-model purity on real traffic. Inspect the run's
   `observed_child_model_ids_raw` / purity state (§ 3 Phase 3 child-model purity), and if
   `wire_id` was `INFERRED`, promote the comment to `OBSERVED` with the result path.

6. **Full four-phase battery** at `--reps 3` across
   `run_mode_classification.py`, `run_post_confirmation.py`,
   `run_dispatch_compliance.py`, and `run_skill_routing.py`. OpenRouter models run in
   parallel waves at the default settings; **Anthropic Phase 3 must be sequential** (§ 9
   rate limits — this constraint is provider-specific, not universal). Per-run sandbox
   isolation and the per-batch fixture lock (§ 9) make concurrent batches safe.

7. **Rerun failed/stalled/timed-out runs** as needed. Use `build_rerun_queue.py`
   selection and the rate-limited-run replacement protocol (§ 9); raise `--timeout`
   only if a run legitimately needs longer wall-clock. Stalls auto-relaunch once
   (`--stall-retries`, § 3).

8. **Regenerate the viewer bundle** with
   `scripts/generate_results_viewer_v2.py` (§ 8) so the new model joins the leaderboard
   and cost/performance surfaces. Filenames auto-increment and never overwrite prior
   bundles.

9. **(Optional) Retire a superseded entry.** There is no schema retirement flag —
   **comment out the entry's block** in `config/models.yaml` with a dated
   `# REMOVED YYYY-MM-DD` rationale and an evidence pointer (precedent: the GPT `-pro`
   block, models.yaml ≈ § REMOVED 2026-07-10). Archived result sets remain immutable and
   rescoreable (§ 8); removing a live entry never touches its history. **If the retiree
   has corpus history**, also copy its `name` + `pricing` into the top-level
   `retired_model_pricing:` section at the bottom of `models.yaml` — the viewer prices
   historical runs from there (a commented-out entry alone silently drops the model's
   cost estimate; observed 2026-08-02).

10. **Re-sweep the registry counts and key references.** After any add or retire,
    re-derive the active-entry count (`grep -cE '^  - (id|key):' config/models.yaml` —
    entries may start with either `- id:` or `- key:`, so an `- id:`-only grep
    undercounts) and update the § 1 model-matrix numbers to match. Also update the
    key-set partition in `tests/test_chatgpt_route.py` (`PREEXISTING_MODEL_KEYS` /
    the `*_ADDITIONS` sets) — its identity assertion runs against the live registry
    and breaks on any unrecorded add or retire. A net-zero swap keeps the § 1 counts
    unchanged but still requires the test-partition update.

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
`prompt_contains_required`, `prompt_contains_any`. The three section-heading
criteria (`prompt_has_task_section`, `prompt_has_context_section`,
`prompt_has_instructions`) measure the **structural presence** of a task /
context / instructions section — NOT the use of a canonical label. The scorer
extracts markdown/bold section headings, normalizes them (strip `#`/whitespace,
casefold), and passes when any heading expresses the relevant concept keyword
(`TASK_KEYWORDS` / `CONTEXT_KEYWORDS` / `INSTRUCTION_KEYWORDS` in the scorer).
This is intentionally forgiving: framework guidance
(`ad-hoc-collaboration-mode.md`) calls the dispatch-prompt structure "a
skeleton, not a rigid template", so legitimate synonyms all pass — e.g.
`## Output format` (lowercase f), `## Return format`, `## Output requirements`,
`## Review expectations`, `## Investigation requirements`, `## Your task`,
`## User Request`, `## Known Symptoms`. The keyword sets are a strict
**widening** of the earlier exact-label lists: every prompt that passed under
the old case-sensitive literal matching still passes (regression-tested), plus
the synonyms. This replaced the earlier case-sensitive substring matching (the
`LEGACY_TASK_LABEL` / `LEGACY_CONTEXT_HEADERS` / `LEGACY_INSTRUCTION_HEADERS`
lists, retained in the scorer only to guarantee the strict-widening property),
which penalized valid variants such as `## Output format` and inflated a
spurious cross-model gap (2026-07-28 heading-normalization). The `TASK_KEYWORDS`
set also includes `request` (added 2026-07-28) so `## User Request` satisfies the
task concept.

**Zero-dispatch gate (Phase 3 caveat, 2026-07-29):** the eight `prompt_*`
criteria all evaluate the CONTENT of a dispatch prompt, so they are only
evaluable when a dispatch was ATTEMPTED. When a run has NO Agent call at all —
none recorded (succeeded or failed) and none recovered from subagent transcripts
— every `prompt_*` criterion FAILS with detail "No Agent dispatch attempt;
prompt criteria not evaluable." This closes the vacuous-pass hole where
`prompt_has_project_dir` (read-only agents), the 0-required
`prompt_contains_required`, and the unspecified `prompt_contains_any` used to
auto-pass on a zero-dispatch run. A recovered or a recorded-failed Agent call
both count as attempts (so the gate does not fire). One bounded residual remains,
analogous to the Phase 4 "Vacuous tier-2 passes" caveat below: on a
FAILED-ONLY run the prompt content is never inspected (the scorer draws prompts
only from successful/recovered calls), so those same three checks still pass
vacuously — the gate closes the total-absence hole, not the attempted-but-failed
one. The two tier1 criteria are unaffected.

**Phase 3 dispatch-recovery fallback.** When a timed-out run's main
transcript lacks the Agent tool_use record but subagent transcripts exist,
`score_dispatch_compliance()` reconstructs the dispatch from that evidence —
without attributing the missing terminal parent-side record to a particular
shutdown or write mechanism — using subagent_type from
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

### API-metered and historical providers

`config/models.yaml` defines per-million-token rates (`input`, `output`, optional
`cached_input`) for Anthropic/OpenRouter entries. Post-run cost is recomputed
from these rates via `cost_estimator.compute_cost()` because the CLI's
`total_cost_usd` uses Anthropic-internal pricing and is wrong for OpenRouter
models.

For these legacy routes, token counts prefer the CLI result's `modelUsage` block,
which aggregates the main session and subagents; plain `usage` is a
main-session-only fallback. `input_tokens` is uncached and
`cache_read_tokens` is additive. `cache_creation_tokens` are billed at 1.25×
ordinary input under the existing Anthropic/OpenRouter convention.

Pre-run estimates use per-case calibration profiles. **Phase 1–3 profiles are
stale** and underestimate subagent cases; treat them as lower bounds (§ 12).
Phase 4 profiles are provider-split because Anthropic runs are dominated by
cache reads while OpenRouter resends uncached context. OpenRouter rates were
reconciled against billing exports; historical archives are not recomputed when
rates change.

**Billing reconciliation pipeline (OpenRouter).** Observed-vs-predicted cost
calibration runs per campaign against the user-supplied OpenRouter activity
export (`openrouter_activity_YYYY-MM-DD.csv` at the benchmarks root). Lineage:
the canonical v1 script (`scripts/reconcile_openrouter_costs.py`) is **stale
for post-2026-07-27 data** (static slug exclusions); v2 (2026-07-29, Kimi
K3 / Gemini campaigns) and v3 (2026-08-02, DeepSeek V4 Flash 0731) live as
campaign-workspace scratch scripts
(`research/2026-07-18_FrameworkDev_DAAFBench_StaticAudit_Fable/scripts/scratch/19-22_billing-*-v2.py`
and
`research/2026-08-02_FrameworkDev_DAAFBench_DeepSeek0731/scripts/scratch/01-05_billing-*-v3.py`),
each consolidating all prior exports (generation_id-deduplicated, provenance
column), classifying rows kept/excluded on empirical per-slug
registration-date boundaries, and reconciling per model × campaign over
kept + covered + non-timed-out runs with a `runs_uncovered == 0` guard.
Snapshots land in `derived/` (`YYYY-MM-DD_openrouter_billing_consolidated /
_classified / _reconciliation.parquet` + `openrouter_reconciliation_YYYY-MM-DD.json`,
the file the viewer's staleness guard reads). **Correction rule:** a cell with
|obs/pred − 1| ≥ 0.26 flags the model for a `models.yaml` rate review (the
2026-06-11 precedent — corrections apply in either direction, and list-price
entries stay marked provisional until reconciled). **Dated-slug gotcha
(2026-08-02):** billing permaslugs carry full-date suffixes
(`deepseek/deepseek-v4-flash-20260731`) while registry slugs use the short
form (`-0731`); the blind date-strip regex would collide such models onto
retired undated slugs, so new dated models need an explicit permaslug →
base-slug override in the classify step.

### ChatGPT-subscription dual ledger

A ChatGPT-subscription run consumes an included/shared capacity pool, not a
separately invoiced API call. Its actual ledger therefore records
`charge_status="not_separately_billed"` and
`actual_marginal_charge_usd=null`. Null means the marginal USD charge is not
observed; it must not be rendered as `$0`, "free," or a fixed per-message cost.
The monthly subscription is not amortized across runs by default.

A separate `api_equivalent` ledger answers a counterfactual question: what the
observed token mix would cost at OpenAI's standard GPT-5.6 Luna API list prices.
The schedule is labeled **accessed 2026-07-15** because the source publishes no
page-level effective date:

| Request tier | Ordinary input | Cached input | Cache write | Output |
|--------------|---------------:|-------------:|------------:|-------:|
| At or below 272,000 request input tokens | $1.00/M | $0.10/M | $1.25/M | $6.00/M |
| Above 272,000 request input tokens | $2.00/M | $0.20/M | $2.50/M | $9.00/M |

The `>272,000` threshold applies the long-context prices to the entire request.
`output_tokens` already includes hidden reasoning tokens, so reasoning is never
added again. Cache reads and cache writes are mutually exclusive subsets of
total input for exact accounting. An exact value is emitted only when cache
categories, their inclusion semantics, and request context tier are all
observable and coherent.

The deployed shim currently exposes total input/output but not reliable cache
breakdowns or per-request context tier. In that common partial-telemetry state,
`api_equivalent.cost_usd` remains null while short- and long-context
all-ordinary-input **scenario** values are retained with assumptions and
`not_invoiced=true`. A scenario does not assert that unobserved cache activity
was zero and is not an invoice. Subscription capacity/credit fields likewise
remain null unless authoritative before/after observations exist.

Published Luna allowances are planning ranges, not guarantees: Plus and
Business list approximately 50–280 local messages per shared five-hour window,
Pro 5× lists 250–1,400, and Pro 20× lists 1,000–5,600. Local messages and cloud
tasks share capacity, weekly limits can also apply, and consumption varies with
context, reasoning, tools, retrieval, caching, and task complexity. The
published credit schedule has no universal USD-per-credit conversion. Record
throttling or observed allowance movement separately; never infer a constant
cost per message.

Sources: [OpenAI GPT-5.6 Luna model and API pricing](https://developers.openai.com/api/docs/models/gpt-5.6-luna), [OpenAI reasoning-token semantics](https://developers.openai.com/api/docs/guides/reasoning), [OpenAI prompt-cache semantics](https://developers.openai.com/api/docs/guides/prompt-caching), and [OpenAI Codex plans, limits, and credits](https://learn.chatgpt.com/docs/pricing), all pricing/limit facts accessed 2026-07-15.

## 8. Results & Viewer

**Result set layout** — every batch archives to a self-contained timestamped
folder:

```
results/{YYYYMMDD_HHMMSS}_{token}/   # {token} = 6 hex of uuid4, per-batch (older sets are bare {YYYYMMDD_HHMMSS})
├── manifest.json          # benchmark name, timestamp, DAAF git SHA,
│                          # batch_token + batch_pid (cross-batch forensics),
│                          # dirty-worktree hash, golden SHA-256 checksums,
│                          # run config (reps, parallelism, delays, timeout,
│                          # model keys), model configs, case definitions
├── summary.json           # aggregate scores + partial/runs_expected/
│                          # runs_completed self-description + aggregate
│                          # error_counts (hook_blocks/tool_failures/
│                          # tool_failures_unclassified)
│                          # + rescored_at (ISO ts, present only if rescored)
└── runs/{case}_{model}_{rep}/
    ├── result.json        # tokens, computed cost, duration, criteria results,
    │                      # error_counts (additive)
    │                      # + rescored_at / rescore_reason (present only if
    │                      #   rescored — see "Historical rescore" below)
    ├── transcript.jsonl   # full session transcript
    └── subagents/         # subagent transcripts (Phase 3)
```

The archive is written **progressively** — see § 3 (Progressive archiving): the
folder, `manifest.json`, and an initial `"partial": true` `summary.json` are
seeded before the pool starts, per-run files are written as each run completes,
and the rollups are re-rolled incrementally (atomically) after every run. All
new fields are additive: `summary.json` gains `partial` (bool), `runs_expected`,
`runs_completed`, and `error_counts`; `result.json` gains `error_counts`. Both
consumers ignore unknown keys, so these additions are format-compatible with all
existing archives.

**Artifact schema and archive policy.** New phase-run and route-probe artifacts
use additive `schema_version: 2` fields for route provenance, separated model
identity, nullable observed usage, actual billing, API-equivalent accounting,
and subscription capacity. Existing flat schema-v1 fields remain where their
semantics are valid; subscription `computed_cost_usd` is null rather than a
fabricated zero. Historical result sets are immutable as to their
provenance and measurement fields: do not migrate, recompute, or rewrite the
tokens, cost, timing, transcripts, route provenance, or schema-v1/v2 identity
fields of old archives. Readers must feature-detect schema v2 and
continue treating schema-v1 records as legacy, with absent new fields interpreted
as unavailable rather than zero. Viewer support for these fields is a separate
integration task; this policy does not claim that every current display surface
already renders them.

**Historical rescore (sanctioned criteria-correction exception).** The
immutability policy above protects measurement and provenance, not scoring
verdicts derived from an *incorrect* scorer. When a deterministic scoring bug is
fixed, the archived transcripts (which ARE immutable) can be re-scored under the
corrected criteria by `scripts/rescore_archives.py`. This rewrites ONLY the
`criteria` / `subagent_criteria` pass fields of `result.json` and the
criteria-derived rollups of `summary.json`, always additively stamped with
provenance so the rescore is auditable and never silent:

- `result.json`: `rescored_at` (ISO-8601 UTC timestamp) and `rescore_reason`
  (e.g. `"heading-normalization-2026-07-28"`).
- `summary.json`: `rescored_at` (ISO-8601 UTC timestamp).

The `rescore_reason` value defaults to the current correction id but can be set
per invocation with `--reason "<label>"` (e.g. when a later scoring fix is
applied, stamp its own id). The reason must be non-blank — a blank or
whitespace-only `--reason` is rejected up front so the provenance stamp is never
empty.

Transcripts, tokens, cost, timing, and all provenance/identity fields are never
touched. The utility defaults to `--dry-run` (report would-change counts without
writing) and only writes under `--apply`. It is scoped to dispatch_compliance
result sets (identified by the `dispatch_compliance` manifest benchmark / `dc-*`
case ids); other batteries, whose criteria are unchanged, are left untouched.
Checkpoint-line and `expected` arguments are re-derived from each set's own
golden checkpoint and manifest exactly as the runner's `score_run` does, so
rescored values are comparable to a fresh run.

In-place replacement of the archived verdicts (rather than dual legacy+v2
reporting that would preserve both the pre- and post-correction scores side by
side) was a deliberate user decision (2026-07-28): the rescored history is
accepted as the single scoring record of the benchmark, since the pre-correction
verdicts were produced by a scorer now known to be incorrect and retaining them
as a parallel ledger would invite confusion over which numbers are canonical. The
`rescored_at` / `rescore_reason` provenance stamps make the correction auditable
without a second reporting track.

**Viewer generation.** `scripts/generate_results_viewer_v2.py` produces the
viewer. The official artifact is a **multi-file bundle directory**
`daafbench_YYYY-MM-DD[suffix]/` (the hosted website build, with lazy-loaded
transcripts by default); `--single-file` emits a self-contained monolith for
offline `file://` auditing, which as of generator v3.4.0 is **transcript-lite
by default** (scores/runs/aggregates only — pass `--transcripts` for the full
inline-transcript monolith). Both are gitignored.

```bash
python3 benchmarks/scripts/generate_results_viewer_v2.py              # bundle, all result sets (lazy transcripts)
python3 benchmarks/scripts/generate_results_viewer_v2.py --no-transcripts  # bundle, index.html only (no shards)
python3 benchmarks/scripts/generate_results_viewer_v2.py \
    --results 20260609_214335 20260609_224824 --output /tmp/daafbench_view/
python3 benchmarks/scripts/generate_results_viewer_v2.py \
    --exclude-results 20260608_181352                                  # all sets except these
python3 benchmarks/scripts/generate_results_viewer_v2.py --single-file # transcript-lite offline monolith (default)
python3 benchmarks/scripts/generate_results_viewer_v2.py --single-file --transcripts  # full inline-transcript monolith
```

The **bundle** contains `index.html` (~4 MB; all run-level data and
precomputed metrics inline) plus, by default, `data/tx_{result_set}.json`
transcript shards fetched on demand by the Run Explorer. The bundle requires
http(s) serving — `fetch()` is CORS-blocked on `file://`, so a fallback message
with a `python3 -m http.server` hint appears instead. Output filenames
auto-increment (`daafbench_2026-06-18/`, `daafbench_2026-06-18a/`, etc.)
and never overwrite prior artifacts. `--exclude-results` drops named sets;
exclusions are recorded in the embedded generation parameters.

**Transcript inclusion (`--transcripts` / `--no-transcripts`, generator
v3.4.0).** This mutually exclusive flag pair controls whether the build carries
per-run transcripts at all, overriding the per-mode default in either
direction. Defaults: **bundle includes** transcripts (lazy shards — they cost
nothing until a run is opened, so the official hosted artifact keeps them);
**single-file excludes** them (the offline monolith is transcript-lite unless
you ask for the full payload). A transcript-less build embeds a `DATA` payload
carrying **neither** `transcripts` nor `transcripts_index`; the Run Explorer
feature-detects this and shows a "Transcripts not included in this build"
notice in place of each run's transcript pane — it makes no fetch attempt, so
there is no broken request or empty pane. Every other surface (scores, metrics,
cost, provenance) is unaffected. The chosen state is recorded as
`transcripts_included` in the embedded generation parameters.

**Result-set discovery (quarantine exclusion, generator v3.4.0).** Discovery
scans the children of `results/` and skips non-phase containers **explicitly**:
any child named `probes` or `removed_runs`, or any child whose name **starts
with `_`** (the operative quarantine convention is `_quarantine*`), is ignored
up front rather than relying on the implicit "lacks a `summary.json`" filter.
A kept result set may carry a `QUARANTINE_NOTE.md` at its root (added
2026-07-29 to the 8 sets whose individual run dirs were relocated to
`removed_runs`); this is inert — discovery recognizes a set solely by its
`summary.json` (enriched from `manifest.json`/`runs/`), so a stray `.md` at the
set root is never consulted.

> **Stale-bundle caveat (2026-07-28).** Viewer bundles generated *before*
> 2026-07-28 embed the pre-correction dispatch_compliance criteria (the
> case-sensitive exact-label matching, and the `TASK_KEYWORDS` set without
> `request`) inline in their precomputed metrics. They therefore display the
> old, spuriously-low DC pass rates and will not reflect the heading-
> normalization fix or the rescored archives. Regenerate any such bundle from
> the current archives (after running `rescore_archives.py --apply`) before
> using it for reporting.

**Viewer content.** The output is a single scrolling document: intro/hero,
key takeaways with a cost-performance preview, about, leaderboard, cost
vs. performance, phase deep-dives, cases & consistency, run explorer, and
provenance. The leaderboard composite is the unweighted mean of five
per-phase Perfect rates (P1, P2, P3a, P3b, P4); tier bands are derived
mechanically from gaps in composite score, with an equal-width range-quartile
fallback when the gap rule degenerates — either too few tiers on a
near-continuum, or (v3.5.0) a single tier holding more than half the ranked
models. Models lacking runs for a
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
ChatGPT-subscription models (GPT-5.6 Luna/Terra/Sol) are priced on an
explicit **`api-equivalent` counterfactual** (v3.5.0): never-invoiced GPT
API list rates from `models.yaml` `api_equivalent_pricing.short_context`,
same uncached basis, marked with an "api-equiv" badge on the leaderboard so
counterfactual figures are never mistaken for invoiced spend. Note the basis
labels (`corpus-live` / `billing-snapshot-*` / `api-equivalent`) name each
model's **token-mix provenance** — the dollar normalization is always
uncached list rates, never invoiced dollars.

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
`timed_out` flag. **Cost** averages exclude timeout-zeroed runs, with excluded
counts disclosed. **Duration/latency** aggregates apply per-status contribution
rules rather than a blanket exclusion: a normal run contributes its full
`duration_s` (timed-out runs are excluded from viewer aggregates entirely —
they are filtered at load, consistent with the viewer's timeout-blindness, so
their truncated wall time never enters the duration axis); a `completed_early`
run (early-stop watchdog — § 3) contributes its
`score_complete_seconds` when present (a *time-to-demonstrated-compliance*
measure: launch → first all-criteria-pass, excluding the confirmation poll and
kill tail — **not** full-task walltime), else is excluded; a `stalled` run is
**always excluded** (its wall time is a watchdog-killed hang, not a
task-completion measure). `completed_early` **scores count normally** in every
other aggregate — though note the 2026-07-29 finding (§ 3): the early-stop kill
can itself corrupt dispatch scores, so all 59 `completed_early` runs produced
under the on-by-default era were quarantined and re-run; early stop is now
opt-in. Runs carrying `status == "stalled"` are hung runs the watchdog
killed after auto-relaunch (§ 3); they are distinct from `timed_out` and are
selected for rerun by `build_rerun_queue.py` alongside timed-out runs (separate
per-class counts). Partial result sets (`summary.json` `"partial": true`)
are tolerated and disclosed: the generator prints each partial set with its
`runs_completed/runs_expected`, and the per-set `partial`/`runs_expected`/
`runs_completed`/`error_counts` fields flow into the provenance payload.

## 9. Operational Notes

### Stop/go criteria for staged ChatGPT Luna execution

Proceed from one gate to the next only when the current artifact is complete and
scorable. Stop before model execution if ambient route settings drift, `/health`
is unreachable or violates the fail-closed contract, the backend/mode changes,
sanitization is not enabled, auth storage is unavailable, or the requested
registry key/provider/wire ID no longer match the approved condition.

After the route probe, stop if the bare slug is rejected, the exact response
comparison fails, execution times out/errors, no scorable response or session
identifier exists, the expected transcript/modelUsage evidence is absent, or
CLI-observed identity indicates Sol, Terra, an OpenRouter-prefixed ID, or any
other mismatch. Do not try an alternative slug automatically. A null
backend-confirmed identity is an evidence limitation, not a success claim.

During behavioral staging, a valid criterion failure is benchmark data and does
not by itself invalidate the route. Stop later gates for route drift,
unscorable/missing required transcripts, provider/timeout errors, Phase 3
`failed` or `unverifiable` child-model purity, subscription throttling, or a
capacity/cap concern. Phase 3 purity must be interpreted at its documented CLI
transcript boundary; even `verified` is not proof against private backend alias
resolution. Preserve every execution-started failure artifact for audit.

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
sandbox `workspace/` (the PROJECT_DIR) alongside a BASE_DIR-level
`scripts/run_with_capture.sh`. The sandbox is thereby isomorphic to the real
repo layout, so the CLAUDE.md convention
`bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/...`
resolves: `sandbox_dir` plays BASE_DIR and `workspace/` plays PROJECT_DIR (the
prior `workspace/scripts/` location drove models of every family to construct
`{BASE_DIR}/scripts/run_with_capture.sh` → exit 127 + wasted recovery turns).
Staging happens after the wipe:
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

**Concurrent batches (separate processes) are safe.** Running two runner
invocations at once — e.g. one Anthropic-subscription terminal and one
OpenRouter terminal — no longer races. Three mechanisms cooperate:

1. **Fixture reader/writer lock (`_sandbox/.fixtures.lock`, DC runner only).**
   `restore_fixtures()` takes an exclusive `flock` (`LOCK_EX`) for its entire
   check-then-repair body, and `prepare_fixtures()` takes a shared lock
   (`LOCK_SH`) around its fixture-copy loop only. So one batch's restore
   (`git restore`/`rmtree`) can never run while another batch is mid-`copy2` of
   the same source paths, and two restores can never overlap. Acquisition
   blocks with a poll loop that warns every 30s and aborts only after 10 min.
   Acquisition happens pre-launch (before the run pool starts), so a wedged or
   oversubscribed lock that never frees within the 600s cap aborts the incoming
   batch with a clear `RuntimeError` before any run is dispatched — fail-loud,
   with no partial result set archived.
   The lock needs no stale-cleanup: `flock` is released by the kernel when the
   holding process dies (including `kill`/Ctrl-C), so a killed batch never
   strands a lock. The other three runners have no fixtures and take no lock.
2. **Read-only fixture source (DC runner only).** After each restore (or clean
   early-return), the `datasets/test_fixtures/` tree is `chmod`ed read-only
   (files `a-w`; directories keep `r-x`), lifted to writable only for the
   duration of any repair. A subject that ignores its sandbox and writes into
   `test_fixtures/` by name now fails with `EACCES` — a loud, harmless failure
   in the subject's own sandboxed run rather than silent source contamination.
   Per-run copies are `chmod u+w` after staging so runs still work with them.
   This does not create git noise: git tracks only the executable bit, not the
   write bit.
3. **Per-batch uniqueness token (all four runners).** Each invocation mints one
   short token (6 hex of `uuid4`); it is appended to both the results directory
   name (`results/{YYYYMMDD_HHMMSS}_{token}/`) and every sandbox suffix
   (`_sandbox/run_{case}_{model}_{rep}_{token}/`). Two batches starting the same
   wall-clock second, even on the same model, no longer merge results dirs or
   `rmtree` each other's live sandboxes. The token and launching PID are also
   recorded additively in `manifest.json` (`batch_token`, `batch_pid`) for
   cross-batch forensics. The **leading timestamp is preserved**, so the viewer
   (lexicographic sort, opaque dir-name identifiers) and `build_rerun_queue.py`
   (`results/*/runs/*/result.json` glob) tolerate both old (`{timestamp}`) and
   new (`{timestamp}_{token}`) directory names — neither parses the name.

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
only if the CLI outlives the grace. The grace is a precaution motivated by
observed incomplete terminal timeout transcripts; it does not establish the
CLI's transcript-write internals or prove that SIGKILL caused any missing tail.
Timeout semantics: `error = "Timed out
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
8. **Provenance pinning does not make changed inputs comparable.** Current
   manifests pin the DAAF Git SHA, the dirty-worktree diff hash, and the SHA-256
   checksum of each used golden checkpoint in `golden_checksums`. These fields
   make input changes detectable, but result sets spanning a golden change still
   require separate interpretation (§ 5).
9. **Some timeout archives lack terminal parent-side evidence.** Observed
   transcripts can end without the final parent-side Agent result or response,
   which prevents stronger causal attribution. The executor's graceful-kill
   ladder (SIGTERM → 15s grace → SIGKILL, § 9) is a precaution that allows an
   orderly shutdown interval; it does not prove an asynchronous/buffered write
   model or that SIGKILL caused any particular missing tail. The scoring-side
   dispatch-recovery fallback (§ 6) can use surviving subagent evidence.

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
- **Reconciliation snapshot (2026-08-02, v3 pipeline — § 7):**
  `derived/openrouter_reconciliation_2026-08-02.json`. Four exports
  consolidated ($1,089.37 total, conserves to the cent); all 2,755 covered
  kept runs matched (`runs_uncovered == 0`). July-campaign calibrations
  confirmed stable vs v2 — Kimi K3 obs/pred 1.087 and Gemini 3.6 Flash
  0.959 (both unflagged). New cell: DeepSeek V4 Flash 0731 obs/pred
  **0.639, flagged** — the Novita/fp8 endpoint bills ~35% below OpenRouter
  list; downward `models.yaml` rate correction pending maintainer decision
  (single small heavy-cache campaign; magnitude MEDIUM-confidence).
  GPT models: zero kept-corpus rows in the OpenRouter billing window, so no
  GPT obs/pred exists on this route (subscription-lane GPT costs are the
  `api_equivalent_pricing` counterfactual, § 7).

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
  in set `20260611_124829`. Those archives lacked terminal session metadata;
  the missing evidence does not establish whether shutdown timing, CLI write
  behavior, or another mechanism caused the absence. The executor's
  graceful-kill ladder is a precaution (§ 9, § 11 item 9), while the
  confirmation pass against `executor.py`/`collector.py` transcript-resolution
  logic remains open.
- **Gemma 4 31B kept IN by user decision:** silent stalls are
  model-attributable (18.5% rate for 31B, 9.3% for 26B — a Gemma-subfamily
  defect, not Google-family). Stalls score as failed runs. **Now mitigated:** the
  run-lifecycle watchdog (§ 3) detects hung runs (330s staleness across the
  parent + subagent transcripts, two consecutive confirmations, plus a ~90s
  first-activity rule) and auto-relaunches once (`--stall-retries`), recording a
  repeat stall as `status="stalled"`.
- **Timeout is now a uniform 900s logistical cap** across all four runners
  (2026-07-21 walltime redesign), superseding the earlier per-batch tuning
  guidance (300s mixed/OpenRouter, 150s Anthropic-only). The high cap lets
  runs complete rather than censor at the cap, so duration becomes a measured
  axis rather than a truncation threshold; historical batch percentiles
  (p99=252s, max=271s under the old 300s cap) motivated retiring the tuned
  values. The harness first-activity detector (~90s → stalled read) is now
  implemented as part of the run-lifecycle watchdog (§ 3).
- **Open follow-ups from Phase 4 routing-fix scoping:**
  (1) frontmatter description budget — svy/polars/marimo exceed the
  250-char limit documented in skill-authoring; verify which claim is
  stale. (2) "For implementation syntax" framing persists in ~12
  data-scientist reference-file headers — sweep recommended but not
  executed. (3) Maintainer note: Phase 4 criterion *emission* is hardcoded
  in the scorer; the cases' `hard_/soft_requirements` lists drive viewer
  display only.
- **Optional:** review of `data-scientist SKILL.md:353` "Tool-specific
  syntax" branch label.

## 13. AI Disclosure

The benchmark suite — harness, datasets, scorers, golden checkpoints, viewer,
and this documentation — was developed using DAAF in Framework Development
mode, with Claude performing scoping, implementation, review, and analysis
via specialist dispatches. The human researcher set scope, made all design
decisions at confirmation checkpoints, and personally applied all
safety-critical configuration (e.g., the `settings.json` hook registration).
Reported scores are produced by the deterministic criteria described in § 6,
not by human judgment of model output quality.
