# DAAF Framework Adherence Benchmarks

Benchmark system for evaluating LLM **behavioral conformance** to DAAF orchestrator
protocols. It answers one question: when a model is placed inside the real DAAF
container — hooks firing, skills discoverable, agents dispatchable — does it follow
the framework's protocols?

This README is the authoritative documentation for the benchmark system. The
`SESSION_RESTART*.md` files in `archive/` are historical session notes (including
run-level provenance for the 2026-06 result sets) superseded by this document for
system-level documentation. `SESSION_NOTES.md` (the shared working-session log,
retired 2026-06-10) is likewise superseded: its durable operational knowledge has
been folded into this document and its live point-in-time status moved to § 12
"Current Status / Next Steps".

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

**Model matrix:** 17 models — 7 Anthropic (Haiku 4.5, Sonnet 4.6, Opus
4.5/4.6/4.7/4.8, Fable 5) via the container's Claude Code subscription, and 10
OpenRouter models (GLM 5.1, Kimi K2.6, Qwen 3.6 27B, Gemma 4 31B/26B, DeepSeek
V4 Pro/Flash, Gemini 3.1 Pro, Nemotron 3 Ultra, Gemini 3.1 Flash Lite) via an
Anthropic-compatible endpoint. The matrix is defined in `config/models.yaml`.

**Relationship to original design:** The system was designed in
`/daaf/research/2026-05-01_Benchmark_Testing/Benchmark_System_Reference.md`,
which specified six test categories (mode classification, skill loading,
protocol adherence, script quality, safety boundaries, golden checkpoint
protocol tests). Four phases are implemented; where this README and the design
document differ, the code (and this README) reflect current reality.
Designed-but-never-built components that remain valuable are catalogued in the
Design Backlog (§ 12) — the reference document does not need to be consulted
for "what's next" beyond the sections cited there.

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
disambiguation like "For static figures use plotnine"). Directives were
verified against skill text 2026-06-10 (pre-routing-fix wording; the
routing-norm fix — defined in § 5 — removed "for implementation
syntax"-style qualifiers without changing any routing target). A case that
provokes a clarifying question fails its design goal and must be reworded.
`cases.jsonl` is the operative encoding; the governing directives per case
are condensed below (the verbatim validated quotes live in the retired
design doc, recoverable via git history):

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
paths that routing depends on — which poisons the test (discovered in the
first Phase 4 dry run).

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
| `scorers/llm_judge/` | Unimplemented stub (see § 6) |
| `datasets/` | `{phase}/cases.jsonl` plus `test_fixtures/` (buggy scripts and data for debugger/code-reviewer cases) |
| `golden/` | Golden checkpoint JSONLs (see § 5) |
| `config/` | `models.yaml` — model matrix with pricing |
| `scripts/` | Phase runners, `generate_goldens.py`, `generate_results_viewer.py`, `rescore_skill_routing.py`, `rescore_criteria_overhaul.py`, `rescore_dispatch_timeout_rescue.py`, `refresh_golden_checkpoint.py`, utilities |
| `results/` | Timestamped, self-contained result sets |
| `_sandbox/` | Per-run scratch directories and archived transcripts (transient) |
| `archive/` | Legacy components (`runner.py`, `cost_budget.yaml`, per-case Phase 1 goldens) — see `archive/README.md` |

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
| `dispatch_compliance/ad_hoc_initialized.jsonl` | 47 | All 12 Phase 3 cases — Ad Hoc mode fully initialized (topic-free final exchange, so any task can follow). Phase 4 used this file too until 2026-06-10 (result sets through `20260610_144524`, since archived out of `results/`) |
| `skill_routing/ad_hoc_initialized.jsonl` | 47 | All 15 Phase 4 cases — content-refreshed copy of the Phase 3 golden (see Regeneration below) reflecting the 2026-06-10 routing-norm fix (the fix: reworded the data-scientist hub + ad-hoc mode doc to require loading the routed library skill whenever advice names tools — skills encode environment-specific constraints absent from memory — replacing the "for implementation syntax" framing) |
| `ad_hoc/after_confirmation.jsonl` | 19 | `run_checkpoint_comparison.py` (legacy comparison utility) |
| `bootstrap_template.jsonl` | 7 | Input to `scripts/generate_goldens.py` |

**Regeneration.** Two distinct mechanisms:

- `scripts/generate_goldens.py` builds 7-line bootstrap-style checkpoints by
  injecting each case prompt from every `datasets/*/cases.jsonl` into line 3 of
  `golden/bootstrap_template.jsonl`, writing `golden/{category}/{case_id}.jsonl`.
  This is the path for prompt-injection-style goldens (the per-case Phase 1
  goldens it once produced are now archived, since Phase 1 runs cold).
- The Phase 2 and Phase 3 goldens in use today are **captured transcripts** —
  truncated from real sessions where a model correctly executed the protocol up
  to the desired boundary. Regenerating them means re-recording a session and
  truncating it, not running the script. Scorers depend on each golden's exact
  line count (§ 6), so any change to a golden invalidates comparison with prior
  result sets.
- `scripts/refresh_golden_checkpoint.py` performs a **deterministic content
  refresh** of a captured transcript: it re-reads the files behind each
  Skill/Read tool result (and rebuilds skill-listing attachment descriptions
  from current frontmatter) and splices current contents into the payloads,
  preserving everything else byte-for-byte (record count, assistant text,
  tool_use_id pairings). Caution: Read results are stored TWICE per record
  (numbered `message.content` payload AND raw `toolUseResult.file.content`) —
  both must be refreshed or stale text silently survives in replay context.
  A second serialization trap: a Skill call's own tool_result is just
  "Launching skill: X" — the skill body arrives in a SUBSEQUENT user record
  (with frontmatter stripped), so a refresh must target that later record,
  not the tool_result itself.

**Golden staleness caveat (important for before/after experiments).** A captured
checkpoint freezes every tool-result payload — skill bodies, reference files —
at recording time. Models resuming from it see that frozen content in-context,
and in-context text dominates behavior: framework edits on disk are largely
invisible until the golden is refreshed. Discovered empirically 2026-06-10: a
routing-norm fix to the data-scientist skill produced zero behavioral change in
a 60-run spot-check replayed against the pre-fix golden (sets
`20260610_144245`/`_144524`, retained as a control condition until Session 5
archived them out of `results/` with the other pre-fresh-golden Phase 4 sets;
the finding stands as recorded), because the old
skill text was embedded in the checkpoint. Any benchmark measuring a framework
change MUST refresh (or re-record) its goldens first, and result sets spanning
a golden change are not directly comparable. On 2026-06-10 (Session 5) ALL
replayed goldens — both `ad_hoc_initialized` files, the 9 `post_confirmation`
goldens, and `ad_hoc/after_confirmation.jsonl` — plus `bootstrap_template.jsonl`
were refreshed to current framework text via `refresh_golden_checkpoint.py`
(extended that day to also rebuild skill-listing attachment descriptions, which
every golden embeds at line 5). Consequently, Phase 2 and Phase 3 result sets
recorded before this refresh are not directly comparable to later sets: the
checkpoint content changed, including embedded skill bodies and listings (the
older recordings carried listing descriptions truncated under a previous
display cap, so the refreshed checkpoints are also several KB larger).

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
`hard_requirements` → critical, otherwise normal). Vocabulary note: the
display terms "critical"/"normal" replaced the former "hard"/"soft"
(2026-06-10, docs and viewer); the underlying data keys —
`hard_requirements`, `soft_requirements`, `tier1`, `tier2` — are unchanged.

**Phase 1 criteria** (scored inline by `scripts/run_mode_classification.py`;
the separate `scorers/deterministic/mode_classification.py` module was dead
code — never invoked by the runner — and was deleted 2026-06-10, with its
keyword/pattern tables relocated into the runner):
`orchestrator_skill_loaded`, `mode_correct`, `no_premature_execution` (critical
in all cases) and `confirmation_gate_present` (normal — gate phrasing varies enough
across models that it is a protocol-detail signal, not a structural one). A
former `reasoning_present` criterion existed only in the dead scorer module
and was never scored by the live runner; it has been removed from the case
lists.

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

**Phase 3 dispatch-recovery fallback (2026-06-11).** The harness historically
SIGKILLed timed-out runs (`subprocess.run(timeout=...)`; replaced 2026-06-11
by the graceful-kill ladder, § 9), and Claude Code's main-session
transcript writes are async/buffered — so a timed-out run could lose an
unflushed transcript tail, sometimes including the very assistant record
carrying the `Agent` tool_use (worst case observed: a main transcript frozen
at exactly the 47-line golden checkpoint beside a 71KB subagent transcript,
`20260609_005920/runs/dc-07_Gemma_4_31B_0`). The scorer now recovers these:
when the main transcript contains no Agent tool_use record at all
post-checkpoint (a recorded FAILED call — `is_error=true` — suppresses
recovery: the system demonstrably processed and rejected that dispatch, and
it keeps failing; the fallback only reconstructs records lost to the kill
race) AND subagent transcripts exist for the run (`subagents/agent-{id}.jsonl` —
keyed by per-run fresh session UUIDs, so presence proves that run dispatched),
`score_dispatch_compliance()` synthesizes the dispatch from that evidence —
subagent_type from `agent-{id}.meta.json`'s `agentType`, the full dispatched
prompt from the subagent transcript's first user record — and scores ALL ten
criteria from it. The fallback is evidence-gated, not timeout-gated (it never
consults the `timed_out` flag). Every criterion scored from recovered evidence
carries a "(recovered from subagent transcript)" provenance suffix in its
detail. Phase 3b subagent behavior IS scored for recovered dispatches (the
subagent transcript is by definition present). With no evidence supplied, the
scorer's behavior is byte-identical to the pre-fallback version. The same
change replaced the dispatch runner's vestigial hardcoded `tool_call_count: 0`
with a real post-checkpoint count.

**Rescue rescore (2026-06-11).** `scripts/rescore_dispatch_timeout_rescue.py`
applied the fallback retroactively across all 24 archived dispatch_compliance
sets: 83 timed-out runs whose dispatch record was lost (concentrated in the
2026-06-09 baseline sets; every one carried archived subagent evidence) were
rescued — `agent_dispatched` +83, `correct_subagent_type` +82, 68 runs flipped
to viewer-Perfect on main criteria, 240 Phase 3b criteria entries added — and
10 further failed-dispatch runs (genuine non-dispatches) received
`tool_call_count` fixes only. 93 result.json files were rewritten in place;
summary.json was rewritten only where its content changed — 7 of the 9
touched sets. The other 2 sets received only `tool_call_count` fixes, which
don't enter summary aggregation, so their prior summaries were kept verbatim.
Note the field's resulting mixed semantics across the archive: historical
PASSED-dispatch runs retain the vestigial `tool_call_count: 0` (the rescore
recomputed it only for failed-dispatch candidates; runs after 2026-06-11 get
real counts). No-evidence recomputes were
determinism-gated and all reproduced their archives exactly. Pre-rescue
snapshots (§ 10) understate dispatch rates for slow models, and viewers
generated before the rescue embed pre-rescue data — regeneration required.

**Phase 3b criteria pruning (2026-06-10).** Four structural criteria were
REMOVED from `scorers/deterministic/subagent_behavior.py` because they passed
in essentially every run with a transcript, noising Perfect and normal rates
(the viewer's Perfect metric counts every non-info criterion, and info-tier
entries also counted toward Perfect in the v1 viewer):
`subagent_transcript_found` (when no subagent transcript exists the scorer now
emits NO subagent criteria — dispatch failure is already captured by
`agent_dispatched`), `subagent_active` (every dispatched subagent makes tool
calls), `subagent_no_code_execution` (never observed failing for the read-only
agents), and `subagent_tool_summary` (an info-tier tool-call distribution
diagnostic, not a behavioral check; its detail string was only ever console
output). The discriminating per-agent-type criteria
(`subagent_writes_script`, `subagent_uses_run_with_capture`,
`subagent_loads_data_skill`, `subagent_reads_target_script`, etc.) are
unchanged. Result sets scored before this pruning initially retained the
removed criteria in their archived `result.json` files; on 2026-06-10 all live
Phase 2 and Phase 3 result sets were rescored in place via
`scripts/rescore_criteria_overhaul.py`, which normalized the historical corpus
to the current criteria scale: the four removed Phase 3b criteria were
stripped from stored `subagent_criteria` (417 runs across 24 sets; retained
entries cross-checked against archived subagent transcripts with zero
mismatches and zero Perfect changes — the removed criteria always passed
wherever stored), and pc-07 runs gained the `skill_agent_authoring` tier2
criterion retroactively with `skill_skill_authoring` retiered tier1 → tier2
(48 runs across 8 sets; 35/48 fail the new criterion). summary.json files
were regenerated per set. The rescore surfaced two corpus caveats: five
result sets have run directories that were pruned after archival
(`20260608_221438` plus four dispatch sets — `20260609_005021`, `_134443`,
`_160029`, `_180411`; dates corrected 2026-06-11 against disk — previously
misrecorded here as `20260610_*`); their summaries now reflect what is on disk, and disk
is the source of truth whenever summary.json and `runs/` disagree. And two
timed-out Fable pc-07 runs lack archived transcripts — they received the
transcript-independent retiers but carry no `skill_agent_authoring` entry
(correct: no evidence to score).

**Phase 4 skill-routing criteria** (from `scorers/deterministic/skill_routing.py`):
`required_skills_loaded` and `required_refs_read` (tier1, critical in all cases);
`required_skills_engaged`, `expected_refs_read`, `routing_order`, and
`no_forbidden_skills` (tier2, normal). `expected_refs_read` is emitted ONLY for
cases with a non-empty `expected.expected_refs` list (since 2026-06-10) —
cases without secondary refs get no criterion at all rather than an automatic
pass, so it never dilutes Perfect/normal rates. `required_skills_engaged` (added
2026-06-10) passes when every required skill was loaded OR name-mentioned in
user-visible assistant text post-checkpoint (case-insensitive, hyphens match
hyphen-or-whitespace, `sklearn` counts for scikit-learn; thinking blocks
excluded). It is a strict superset of `required_skills_loaded`, so the
engaged-vs-loaded gap directly quantifies "named the right skill but deferred
the load" behavior — the dominant Phase 4 failure mode. Historical Phase 4
result sets were rescored in place via `scripts/rescore_skill_routing.py`
(merge semantics: legacy criteria such as dry-run 2's `no_spurious_skill_reload`
are retained).
`routing_order` checks the expected load/read sequence as a subsequence of the
post-checkpoint tool-call stream (tests the hub's "FIRST read X THEN load Y"
directives). Read matching is by **basename only** — sandbox checkpoint replay
rewrites `/daaf` inside replayed `file_path` values, so full paths are
unreliable; basenames are unique within each case's required skill. Only
successful tool calls satisfy requirements. `quickstart.md`/`gotchas.md` and
other extra reads under a correctly loaded skill are never penalized —
over-reading is a quality issue, not a routing error.

Baseline transcript review (2026-06-10; Fable 5 + Sonnet 4.6, 30 runs)
established the dominant failure behind `required_skills_engaged` as **two-hop
decay**: hub-reference selection was near-100% correct, but models
reinterpreted "THEN load the library skill" as an implementation-time
protocol — naming the correct skill in prose while answering from parametric
memory. Reference reads were accuracy-anxiety-driven, not directive-driven;
zero-tool runs were substantive, not lazy. This motivated both
`required_skills_engaged` and the framework-side routing-norm fix (defined in
§ 5; the pre-fix data-scientist description "For implementation syntax, load
the routed tool-specific skill" itself licensed the deferral). Informal mention-counts in
the review (~13/15) overstate vs the deterministic matcher (9/15).

**Vacuous tier-2 passes (Phase 4 caveat):** `no_forbidden_skills` passes
trivially when a model makes no Skill calls at all. In the 2026-06-10 dry run,
models that ignored routing entirely (answering from parametric memory) still
passed it 75/75 — interpret Phase 4 normal rates jointly with the tier-1
load/read criteria, never in isolation. (A former criterion,
`no_spurious_skill_reload`, was removed 2026-06-10 for exactly this
vacuousness: it passed 75/75 in dry runs with zero discrimination — models
that fail routing mostly make zero Skill calls. Removed from scorer, cases,
and schema; dry-run result.json files retain it.)
`required_skills_engaged`, by contrast,
is not vacuously passable: a zero-tool run must still name the required skill
in user-visible text, and observed per-model rates span 3/15 to 14/15.

**Phase 4 scoring rationale:** `no_forbidden_skills` is deliberately
normal-tier: loading a wrong skill is only harmful if acted upon, and the
excluding directive in the wrong skill is itself informative.
`required_skills_engaged` is deliberately NOT folded into the critical loading
criterion — that would grade the targeted failure mode as a pass, blind the
post-fix delta, and mix prose-matching into a tool-call criterion. (Pre-fix
rescore, since-archived sets: engaged 136/225 = 60.4% vs loaded 18/225 = 8.0%
— numbers survive only in this record.) `routing_order` auto-passes when a
case omits `expected.order` (intentional; sr-15 omits it — no directive
sequences its two branches). "Allowed ≠ expected": per-case `allowed_refs`
audit lists are ignored by the scorer — by design there is no over-reading
penalty. `forbidden_skills` membership requires a verbatim excluding
directive; merely-unnecessary skills are never forbidden.

**Perfect vs. Critical/Normal rates — intentionally different metrics:**

| Metric | Unit | Definition |
|--------|------|------------|
| Perfect | per-run | Did ALL criteria pass for this run? |
| Critical rate | per-criterion | Across all runs, what fraction of critical criteria passed? |
| Normal rate | per-criterion | Across all runs, what fraction of normal criteria passed? |

These can diverge sharply: 4 runs each failing one normal criterion yields 67%
Perfect with 100% Critical and 96% Normal. Both views are reported.

**LLM judge status:** `scorers/llm_judge/` is an **unimplemented stub**
(contains only `__init__.py`). The three-tier hybrid design from the original
reference document reserved tier 3 for LLM-as-judge rubric scoring; nothing in
the current system invokes it.

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
`cache_creation_tokens` were historically captured in results but excluded
from `compute_cost()`; as of 2026-06-11 they are billed at 1.25× the `input`
rate (Anthropic's cache-write convention — § 8 cost methodology addendum).
The omission understated Anthropic-side computed costs ~3× against the full
convention (cache-write spend dominates subagent-heavy runs). The fix applies
to future runs only — archived `result.json` values are immutable and not
recomputed.

**Pre-run estimation.** `cost_estimator.py` holds per-case calibration token
profiles (average input/output/cached per case) that drive the pre-launch
estimate and confirmation prompt. **The Phase 1–3 profiles are stale:** they
were collected 2026-06-08 (Haiku 4.5, DeepSeek V4 Flash, Gemini 3.1 Flash
Lite) before the `modelUsage` fix and reflect main-session-only tokens, so
they underestimate costs for subagent-dispatching cases (all of Phase 3).
Treat those pre-run estimates as lower bounds until recalibrated (§ 12). The
Phase 4 profiles were recalibrated 2026-06-10 from all eight fresh-golden
baseline sets (520 usable runs; 35 error/timeout/stall runs excluded) and are
**split by provider** (`PHASE4_TOKENS_OPENROUTER` / `PHASE4_TOKENS_ANTHROPIC`,
selected via `model.provider`; unknown providers fall back to the OpenRouter
profile, which estimates high). The split is necessary because the billing
regimes do not mix: Anthropic runs are nearly all cache reads (billed ~10% of
input price) with ~0 uncached input, while OpenRouter runs re-send uncached
context every turn — a single blended profile over-estimated Anthropic models
3.3-8.4x. Validated against the same actuals at 0.90x aggregate, 0.90-0.91x
per provider (`_sandbox/validate_phase4_estimator_a.py`); residual per-model
scatter (~0.7-1.7x) is inherent to per-case calibration — heavy models run
above the profile, light ones below.

**Pricing correction (2026-06-10).** Reconciling computed costs against the
OpenRouter billing export (`openrouter_activity_2026-06-10.csv`, which covers
the strong-five rep-1 batch 18:12-18:35; analysis in
`_sandbox/analyze_openrouter_activity.py`) confirmed computed costs within
~2-6% of billed for Gemini 3.1 Pro, GLM 5.1, Kimi K2.6, and DeepSeek V4
Flash — but exposed **DeepSeek V4 Pro billing at ~3.3x the configured rates**.
`config/models.yaml` was corrected ($0.435/$0.87 → $1.44/$2.88 per M, implied
from billed totals). Result sets archived before the fix (2026-06-10 and
earlier) understate DS Pro `computed_cost_usd` — and therefore its viewer
cost displays and cost-efficiency standing — by ~3.3x; stored values are not
retroactively recomputed (archived results are immutable).

**Pricing corrections (2026-06-11).** The fuller billing reconciliation of
2026-06-11 (§ 8 cost methodology addendum) exposed the same error class in
three more models; `config/models.yaml` rates were multiplied by the observed
obs/pred billing factors: Gemma 4 26B ×2.12 ($0.06/$0.33 → $0.127/$0.700),
DeepSeek V4 Flash ×1.34 ($0.0983/$0.1966 → $0.132/$0.263), Gemma 4 31B ×1.26
($0.12/$0.36 → $0.151/$0.454). As with DS Pro, archived result sets
understate those models' computed costs by the same factors.

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

**Viewer generation.** `scripts/generate_results_viewer_v2.py` is the
maintained generator; v1 (`generate_results_viewer.py`) remains in the repo
as archival code, never modified. The `viewer.html` artifact v1 once produced
was deleted (2026-06-10 housekeeping, user decision). Since generator v3.0.0
the **official artifact is a multi-file bundle directory**
`daafbench_YYYY-MM-DD[suffix]/`; `--single-file` still emits the dated
`viewer_YYYY-MM-DD{letter}.html` monolith for offline auditing. Both are
untracked (gitignored via the `daafbench_*/` and `viewer_*.html` patterns
in `benchmarks/.gitignore`).

```bash
python3 benchmarks/scripts/generate_results_viewer_v2.py              # bundle, all result sets
python3 benchmarks/scripts/generate_results_viewer_v2.py \
    --results 20260609_214335 20260609_224824 --output /tmp/daafbench_view/
python3 benchmarks/scripts/generate_results_viewer_v2.py \
    --exclude-results 20260608_181352                                  # all sets except these
python3 benchmarks/scripts/generate_results_viewer_v2.py --single-file # offline monolith
```

By default (generator v3.0.0) this produces a **multi-file bundle
directory**: `index.html` — the full report shell with all run-level data
and precomputed metrics inline (~4 MB on the 2026-06 corpus) — plus
`data/tx_{result_set}.json`, one transcript shard per result set, fetched
on demand when a run is opened in the Run Explorer (condensed transcripts
were ~85% of the monolith's bytes; lazy-loading them cut the initial
payload from ~25 MB to ~4 MB). The bundle **requires http(s) serving** —
`fetch()` of sibling files is CORS-blocked on `file://` origins, so a
bundle opened from disk shows a visible fallback message in the transcript
panel (with a `python3 -m http.server` hint) rather than failing silently.
For offline / `file://` auditing, `--single-file` emits the pre-3.0
self-contained monolith embedding full inline transcripts; it works opened
directly from disk. When `--output` is omitted, both modes write **dated,
auto-incrementing names** in `benchmarks/` —
`daafbench_YYYY-MM-DD{,a,b,...}/` for bundles,
`viewer_YYYY-MM-DD{a,b,...}.html` for single-file — which is intentional:
each regeneration is a new versioned artifact (matching the framework's
no-in-place-modification convention) and never overwrites a prior one.
Historical v1 outputs interleave with v2's single-file lettering in the
shared `viewer_YYYY-MM-DD{letter}.html` namespace. `--exclude-results`
drops named sets while keeping everything else (useful for
known-contaminated sets without enumerating the rest via `--results`);
exclusions are recorded in the embedded generation parameters for
provenance (which also record the output mode since v3.0.0).

The output is a single scrolling document of nine TOC sections (intro/hero,
key takeaways — with a compact cost-performance preview in their flow —
about, leaderboard, cost vs. performance, phase deep-dives, cases &
consistency, run explorer, provenance; the verdict callout, costs-detail,
and next-steps sections were removed in the 2026-06-12 user fine-tuning
round, below). The leaderboard composite and tier bands span all five
approved components with equal weight (P1, P2, P3a, P3b, P4 — P4
user-approved 2026-06-10, joined the composite 2026-06-11, superseding the
original four-component pin); a
model lacking runs for a component is scored on its available components and
carries a visible "partial" marker naming what's missing. Any new phase
reports as its own labeled group throughout the viewer until it is
deliberately added to the composite. Cost vs. Performance has a phase-basis
selector (Composite + each phase group) and Costs Detail a perfect-rate
phase-scope toggle, so per-phase value comparisons don't require regeneration.
To add a new benchmark phase to the viewer, follow the "Adding a
new benchmark phase" guide in the comment block above `PHASE_MAP` in
`scripts/generate_results_viewer_v2.py`. Notable internals:

- **Global rep renumbering:** runs from separate `--reps 1` batches all carry
  `rep=0`; the generator renumbers sequentially per `(phase, model, case_id)`
  across all loaded result sets
- **Transcript keying (generator v2.7.0 fix, 2026-06-11):** the embedded
  `transcripts` and `subagent_transcripts` dicts are keyed
  `{result_set}/{run_dir}`, mirrored exactly by the template's run-detail
  lookups. Run-dir names (e.g. `dc-08_Gemma_4_26B_0`) are only unique within
  a result set — bare-name keys silently overwrote 857 main transcripts
  (482 colliding names across 1,339 transcript-bearing run instances on the
  52-set corpus) and displayed another set's subagent transcript on
  same-named runs. Bundle artifacts (v3.0.0) ship the same dicts split into
  per-set shards with the keys unchanged in full composite form, so the
  template's lookup code is identical in both modes
- **HTML5 tokenizer safety:** all `<` in the embedded JSON are escaped to
  `\u003c`. Transcripts contain literal `<!--` and `<script` sequences that
  otherwise flip the HTML5 parser into escaped-script states and break rendering
- **Chrome `file://` handling:** explicit navigation (nav links, deep-link
  jumps) writes the hash via `location.hash` on `file://` (Chrome restricts
  `history.replaceState` there) and via `history.replaceState` otherwise.
  The scrollspy only ever writes via `history.replaceState` — and writes
  nothing on `file://` — since assigning `location.hash` during scroll would
  scroll-jump

### Viewer design record

Durable record of the 2026-06-10 viewer redesign (absorbed from the retired
redesign plan document); code comments in the generator and template cite
this subsection as "design record: README § 8".

**Design decisions (viewer redesign Checkpoint 1, 2026-06-10):** (1) Composite
= unweighted mean of per-phase Perfect rates, originally four equal components
(P1, P2, P3a, P3b) — superseded 2026-06-11 when P4 joined as a fifth equal
component (see above / § 12). (2) Tier bands derived mechanically from gaps in
composite score (reproducible rule, documented in the generator's tier-banding
comment block). (3) All result sets embedded by default. (4) Dated
auto-incrementing output filenames are intentional (above). (5) About layer:
plain-language, DAAF-aware tone, ~600–900 words across collapsibles.
(6) Archival approach for the v1 generator (user decision; details at the
top of this section).

**Accepted residuals (viewer redesign Checkpoint 2, 2026-06-10) — reviewed,
no fix planned:** (1) `konStep` labels 1-of-2 reps as "most" in the case ×
model agreement heatmaps — a smallest-denominator labeling quirk; exact k/n
stays visible in the cell. (2) The leaderboard keeps a fixed "#" rank column
despite the tier-bands-over-false-precision principle; adjacent prose
disclaims strict-ordering precision. (3) P3b heatmap cells carry varying
denominators (subagent-criterion applicability varies by case subcategory);
tooltip k/n mitigates misreading. (4) The generator's `print_summary` echoes
`summary.json` totals without the disk-vs-summary discrepancy caveat the
rendered provenance footer carries. (5) Provenance git SHA is per-set display
only — no cross-set SHA grouping or comparison.

**Data realities the viewer encodes (2026-06-10 inventory):** run-level
`result.json` is ground truth — `summary.json` run counts disagreed with
on-disk run dirs in 9 of 42 sets at redesign time (67 phantom runs); all
viewer aggregates come from loaded runs, summary totals are provenance-only,
and disk-vs-summary discrepancies are displayed (not hidden) in the provenance
footer. Timed-out runs are **graded**: every on-disk `error` is a timeout
string; such runs have zeroed turns/cost/tokens but fully scored criteria. The
viewer status taxonomy is therefore grade (perfect/partial/failed/ungraded)
orthogonal to the `timed_out` flag — no string-matching on `error` — and
cost/duration averages exclude timeout-zeroed runs, with excluded counts
disclosed in footnotes. `reasoning_cost_multiplier` appears in no
`result.json`; the badge logic reads it defensively.

**Template architecture:** v2 is data-prep Python + placeholder substitution
into `scripts/viewer_template.html` (bare `__DATA_JSON__` and
`__PRECOMPUTED_JSON__` tokens — as in `const DATA = __DATA_JSON__;` — plus
small prose slots; substitution order is load-bearing, with the small
controlled placeholders filled first and `__DATA_JSON__` last so transcript
content can never be treated as a placeholder). Extracted from v1's
single f-string because `{{ }}` escaping across ~1,400 lines of CSS/JS bred
subtle bugs, blocked editor syntax support, and made diffs noisy. The default
output is the multi-file bundle since v3.0.0 (index.html + per-set transcript
shards; `--single-file` keeps a fully self-contained monolith for offline
audit); either way the generator is the single entry
point, no build step. JS is vanilla, IIFE-wrapped, ES5-style; headline numbers
are precomputed in Python and embedded so prose and charts cannot drift apart.

**Design system:** dark theme. Colorblind-safe status palette with mandatory
glyph redundancy (✓ ✗ ◐ —) and ≥3:1 non-text contrast: pass `#34d399`, fail
`#fb7185`/`#f87171`, partial `#fbbf24`, ungraded slate `#64748b`; timeout is a
distinct glyph marker, never a color of its own. Heatmap rates render as 5
discrete steps on a single hue ramp (never a continuous red→green ramp). 17
distinguishable model-identity hues, never hue alone (always label
points/rows). Inline SVG, zero chart libraries. Governing principles:
overview-first/details-on-demand single scrolling document (no global filter
bar — each section owns its controls); every chart titles its *finding*,
computed at render time; 1–3 sentences of "how to read this" per section;
visible denominators everywhere (`21/24`, not just 88%).

**Public-audience evolution (2026-06-11, generator v2.6.0):** the viewer was
reworked for public consumption (project-website hosting), evolving the
single existing viewer rather than forking a public variant.

1. *Audience inversion* — all prose rewritten for readers unfamiliar with
   DAAF; generalist hero framing ("How well do different AI models handle
   the complexities of rigorous research workflows?"). The user explicitly
   rejected a Mind/Body/Instructions conceptual device as overcomplicating.
2. *Key Takeaways section* (new; sits between Verdict and About) — a dated
   editorial ("Editorial takeaways — June 2026 corpus") with six
   maintainer-interpretation claims (five after the user's 2026-06-12
   frontmatter consolidation) whose figures are span-injected from
   PRECOMPUTED at render time (`kt-*` spans filled by `fillTakeaways()` —
   31 originally, 29 after the battery re-adjudication below, 23 after the
   2026-06-12 e099982 repair pass (§ 12);
   a new `timeout_by_model` precompute feeds the timeout claims), so
   regeneration cannot orphan the numbers. The qualitative claims do NOT
   track the data — when the corpus changes materially, rewrite the prose
   and update the date badge. That rewrite rule fired the same day: after
   the 2026-06-11 dispatch-recovery rescue rescore shifted the corpus, a
   delta re-adjudication of all six claims reframed T4 around DeepSeek V4
   Pro leading an open-weight pack that now crowds the frontier tier (with
   a DS Pro timeout-rate caveat), retired T2's "4.7 drops a tier" sentence,
   and confirmed T1/T3/T5/T6 unchanged. *Second re-adjudication
   (2026-06-11, vs the `_11j` corpus + battery metric, generator v2.8.1):*
   all takeaway cost claims moved from blended $/Mtok to the battery
   basis, displayed as **relative multipliers/ratios vs Opus 4.8 — never
   dollars** (user decision: exact dollar figures imply false precision).
   T1 held; T2 got a light body rewrite (the dip is now a two-release
   slide; 4.8 is the only Opus in the second tier); T3 recast as a
   battery-percentage claim (Sonnet ≈ 41% of Opus 4.8's battery); T4
   reframed control-not-price (its "crowd the frontier tier" claim
   tier-broke and the battery basis erased the price story — DS Pro ≈
   0.8× Sonnet's battery); T5's "on the order of 1/100 of frontier cost"
   clause retired and "astonishingly" softened to "strikingly" (battery
   ratios: 1/7 of GLM, 1/31 of Opus 4.8); T6's weakest-point claim
   corrected from mode classification to P4 skill routing (new
   `kt-t6-qwenp4` span); and the kt-foot retired the stale "single
   repetition on Phase 4" caveat (every model now has 45 P4 runs) and
   gained the relative-multiplier basis + drift caveat with an injected
   battery size (`kt-foot-bat`). Net span wiring: 31 → 29 `kt-*` spans.
3. *"Two bars" concept* — Perfect ("everything exactly right") vs.
   Critical-only ("will it generally work") promoted to an always-visible
   About block, with all echo sites aligned to that vocabulary.
4. *CRIT_LABELS* — a 45-entry plain-language criterion label map in the
   template; the raw snake_case ids are always shown alongside the label for
   traceability (the Run Explorer stays raw).
5. *Head metadata for web hosting* — title, meta description,
   OpenGraph/Twitter tags with a `REPLACE-WITH-FINAL-URL` og:url placeholder
   for the deploy step, inline SVG favicon, and a noscript notice. og:image
   is deliberately deferred to the user's external deploy infrastructure (it
   must be an absolute URL on the host).
6. `#takeaways` is deliberately excluded from the `content-visibility:auto`
   rule — it is a static above-the-fold prose section with no JS renderer;
   the CSS comment at the top of the template documents the exclusion.
7. *Hosting/deployment boundary* — stable public filename, compression, and
   upload are handled by the user's separate website deploy infrastructure,
   out of framework scope. An http(s) retest is needed post-deploy because
   four code paths differ between `file://` and http(s): explicit-nav hash
   writes, scrollspy `replaceState` writes, `content-visibility` anchor
   rendering, and (since v3.0.0) transcript fetch-on-demand — including the
   fetch-failure fallback message and the `&run=` deep-link path, where the
   transcript pops into the already-scrolled-to run panel when its shard
   arrives.

**Accepted residuals (public-audience evolution, 2026-06-11) — reviewed, no
fix planned:** (1) the "expects:" badge in the Run Explorer still shows raw
engagement-mode ids — no display-name mapping for modes exists in the
template. (2) JS syntax was structurally verified via python; no node syntax
check was run — the user's browser visual check covers it.

**Cost methodology evolution (2026-06-11, generator v2.8.0):** a full
reconciliation of OpenRouter billing against the results corpus
(`scripts/reconcile_openrouter_costs.py`; machine-readable summary in
`derived/openrouter_reconciliation_2026-06-11.json`; findings in
`research/2026-06-11_FrameworkDev_ViewerPublic/preliminary_notes/`)
established that token appetite varies only ~0.67–1.26× vs Opus 4.8 — the
huge cost-per-run divergence across the corpus is overwhelmingly price, not
volume — and that list price × the *billed* token mix predicts actual
OpenRouter billing within ~3% for 7 of 10 models, while the harness's own
token counts (Anthropic-tokenizer approximations) do not. Changes that
followed, all user-approved:

1. *Battery-cost metric* — the Costs Detail headline is now the **estimated
   cost to run the full benchmark battery once** (51 distinct probes on this
   corpus: 15 mc + 9 pc + 12 dc + 15 sr; derived from the corpus at
   generation time, never hardcoded — note the Anthropic models' 141 runs
   are uneven reps over those 51 cases, not 47×3). Per model:
   est_cost_per_run = (input-side tokens × list input rate + output-side
   tokens × list output rate) / 1e6, on an **uncached basis** — every token
   at full list input/output rates, no cache discounts. Rationale: caching
   schemes differ wildly across providers (Anthropic runs are ~95% cache
   reads/writes; OpenRouter prompt caching effectively never materialized in
   billing), so the uncached counterfactual is the only basis that compares
   providers like-for-like (for the record: real cached usage runs far
   cheaper — Opus 4.8's battery ≈ $32 under Anthropic's caching convention
   vs ≈ $81 uncached). *Presentation (generator v2.8.1, user decision):*
   the takeaways and all user-facing cost surfaces display the battery
   metric as **relative multipliers** (Opus 4.8 = 1.0×), not dollar
   estimates — exact dollar figures would imply false precision; the
   dollar values stay embedded in PRECOMPUTED, only presentation changed,
   and the cached-vs-uncached dollar disclosure was retired from the
   viewer with it (superseded by a relative-drift caveat: multipliers
   shift as providers reprice tokens and as caching mechanics interact
   with model behavior). Token mixes: Anthropic models
   live from corpus `result.json` (input + cache_read + cache_creation on
   the input side); OpenRouter models from the reconciliation snapshot's
   billed prompt/completion per covered run. A generation-time **staleness
   guard** compares each OpenRouter model's corpus run count to the
   snapshot's recorded `n_runs` and warns (never fails) on drift. "Battery"
   is also a fourth price formulation in Cost vs. Performance (since
   v3.1.0 the *first* of three — the blended 3:1 form was retired and
   battery became the headline cost figure page-wide; see the dated
   "Battery multiplier promoted" addendum below). Caveat
   (disclosed in the viewer): high-timeout models' figures are
   truncation-depressed.
2. *Rate corrections* — Gemma 4 26B / DeepSeek V4 Flash / Gemma 4 31B
   published rates understated actual billing (obs/pred 2.12 / 1.34 / 1.26);
   corrected in `models.yaml` (§ 7 Pricing corrections).
3. *Harness cache-write fix* — `compute_cost()` now bills
   `cache_creation_tokens` at 1.25× input (§ 7 Token semantics); future runs
   only.
4. *New data dependency* — the generator discovers the latest
   `derived/openrouter_reconciliation_*.json` (fail-soft: warns and omits
   OpenRouter battery costs if absent). Maintenance guide: the
   "Battery-cost metric" dev-guide comment above `PHASE_MAP` in the
   generator.

**Multi-file bundle architecture (2026-06-12, generator v3.0.0):** the
official artifact became a bundle directory for website hosting (user
decision; transcripts + subagent transcripts were 84.6% of the 25 MB
monolith and are read only by the Run Explorer's `renderRunDetail`).
`index.html` keeps `DATA.runs` and everything else inline (every section
computes from runs) and replaces the two transcript dicts with a
`transcripts_index` (`{result_set: {file, n_main, n_subagent}}`); per-set
shards `data/tx_{result_set}.json` carry only that set's entries under the
unchanged composite keys (median ~275 KB / max ~1.2 MB per shard). The
template feature-detects the artifact shape on `DATA.transcripts` presence:
single-file renders transcripts synchronously exactly as before; bundles
render a loading placeholder and fill it when the shard arrives, with a
memoized per-set shard cache, a stale-click token so a late shard never
renders into another run's panel, and a visible fetch-failure fallback
(with the `python3 -m http.server` hint on `file://`). `file://` support is
deliberately dropped for bundles; `--single-file` is the offline audit
path. Maintenance guide: the "Bundle architecture" dev-guide comment above
`PHASE_MAP` in the generator.

**Battery multiplier promoted to the headline cost figure; blended $/Mtok
retired (2026-06-12, generator v3.1.0):** the battery-cost multiplier
(estimated cost to run the full battery once, × Opus 4.8 = 1.0×, never
dollars) is now the headline cost figure on *every* surface, and the
blended 3:1 price formulation (`blend31`, the Artificial Analysis
convention) was removed entirely. Rationale (user decision): the vast
majority of benchmark cost came from input tokens, so a 3:1 in/out blend
was misleading; raw input/output $/Mtok stay as secondary detail only.
Changes: the leaderboard cost column re-pointed from `blend31` to the
battery multiplier (header "Battery cost (× Opus 4.8)"; em-dash idiom for
models without battery data; the staleness guard's ⚠ now propagates to the
leaderboard cell tooltip — previously it surfaced only in Costs Detail);
the Cost vs. Performance scatter defaults to the battery basis (battery
ordered first in `COST_FORMS` so the array-index-0 fallback agrees), with
input/output as secondary toggles and the section lead rewritten
multiplier-first; the About cost caveat reordered multiplier-first. Schema
change (hence the minor version bump): `blend31` removed from
`PRECOMPUTED.cost.models[]` entries and from `cost.frontiers` (battery now
first of three forms); the sanity report prints the battery frontier
instead of the blended one. Costs Detail and Key Takeaways needed no
changes — already multiplier-led since v2.8.1.

**Tone percolation, "DAAFBench: Orchestration" suite naming, and hero chips
redesign (2026-06-12; template prose + generator dev-guide comments only —
no generator code change, no version bump):** the maintainer's voice (colon-
first elaboration, the "basically: …" decoder pattern, honest hedging,
plain-label-first jargon policy) and the DAAF website's framing language were
percolated through all remaining viewer prose, per the voice guide and
35-surface percolation map in
`research/2026-06-11_FrameworkDev_ViewerPublic/preliminary_notes/2026-06-12_scoping_voice-percolation.md`.

(a) *Suite naming* — the page now presents itself as **"DAAFBench:
Orchestration"**, part A of a planned pair whose companion suite will test
analytic competency (explicit decision-making inside analytic code and
data-cleaning steps, via adversarial examples, known-good code, and
deterministically verifiable outputs). Carried in the title/og/twitter meta
(also resolving the pre-existing title-vs-og wording mismatch by unifying on
one title), the TOC rail title, one sanctioned two-sentence hero insertion,
a new About intro, and the closing CTA. About h2 and TOC label renamed
"About This Benchmark" → "About DAAFBench".
(b) *Full rewrites* — leaderboard section lead (intuition-first decoders for
composite / tier bands / denominators); Cost-vs-Performance lead (voice
restructure only; factual content unchanged from the v3.1.0 multiplier-first
rewrite); all five `PD_EXPLAINERS` entries (two-register failure-mode-first
structure kept; the skill-routing entry adopts the website's "fuzzy general
knowledge" vs curated-context vocabulary).
(c) *Moderate passes* — two-bars primer (criterion decoder), benchmark-phases
table framing (anatomy-style plain-question intro; composite-governance note
de-internalized to "newest component, added in June 2026"), how-scoring-works
(deterministic-scorer decoder), Phase Deep-Dives / Cases & Consistency
("probabilistic" decoder) / Costs Detail leads, `lbTierRuleText` ("no
judgment calls"), hero verdict (decoder voice). Light touches: `models.yaml`
dropped from the CvP secondary-basis footnote; DAAFBench naming at first
reference per section. Forensic surfaces (Run Explorer detail, Provenance,
GRADE_TIP, heatmap headers) deliberately untouched.
(d) *Hero chips redesign* — the chip row and verdict hoisted ABOVE the four
hero paragraphs (anatomy-page orientation-first pattern), and chip content
redesigned for zero-context readers: "N AI models tested / N archived test
runs / N distinct test scenarios / 100% of scores trace to a real run"
(replacing the jargon chips Models / Runs / Cases / Phases).
(e) *Outbound links + attribution* — DAAF site + GitHub repo links restored
in the new About intro; a new lean closing CTA section `#next-steps` (TOC +
`SECTION_IDS` registered, static prose, no renderer, deliberately outside the
content-visibility rule) links daaf.openaugments.org, the anatomy deep-dive
("See how a DAAF analysis actually works"), and the GitHub repo, with the
Open Augments attribution in the site's own register ("built by researchers,
for researchers"; public-good framing). All URLs verified against the website
subset. The glossary's orchestrator entry gained the site's "lab manager"
gloss.
(f) *Sanctioned voice-anchor edits (the only two)* — the hero pair-naming
insertion (item a) and takeaway 1's metric clarifier ("leads the scoreboard
at **a Perfect average score of**", matching takeaway 3's vocabulary — it
previously named no metric). All other hero/takeaway prose is byte-identical;
the 23-span contract is unchanged.
(g) *Housekeeping* — the two stale "1,700+ run corpus" internal JS comments
made corpus-neutral; generator dev-guide anchors refreshed (GROUP_SHORT
~L1279, PD_EXPLAINERS ~L2322, buildEvalGroups order ~L1269, phaseSpan ~L1772,
phases table ~L689) and a suite-naming/hero-orientation maintenance note
added to the public-prose registries guide.

**Site-cohesion styling (2026-06-12; template-only — no generator code
change, no version bump):** the viewer was restyled to be visually cohesive
with the DAAF product website (it ships alongside the site as the Learn >
"Choosing Your Model (DAAFBench)" page) — a token swap + fonts + chrome +
selected component idioms, deliberately NOT a full restyle.

1. *Tokens + fonts* — the template `:root` surfaces/text/borders were
   remapped to the site's values (`#0a0f1c`/`#111827`/`#151d2e` + hover/
   active surfaces; `#f0f4f8`/`#b0bcc8`/`#7b8da0` text; white-alpha
   borders), with `--accent-teal`/`--accent-mint`, `--nav-height`, and
   `--ease-out-expo` added and the site's radii scale (14px cards / 10px
   buttons & callouts / 999px pills / 8px pre) applied through the existing
   var-routed rules. Fonts mirror the site's Google Fonts loading exactly
   (preconnect pair + one css2 link, `display=swap`): Space Grotesk for
   h1/h2/h3, section labels, eyebrows, and nav; DM Sans for body/UI;
   JetBrains Mono for code/mono surfaces with the old SF Mono stack kept as
   fallback — single-file/offline use falls back gracefully to system fonts
   when Google Fonts is unreachable. **Accent split (user decision):** teal
   `#22d3a8` is chrome only (gradient strip, topbar, prose links, TOC/nav
   active states, eyebrows, decorative callout gradients) so accent never
   reads as pass-green `#34d399`; indigo `#6366f1` remains the in-content
   interactive accent (buttons, selected runs, hover tints, code chips).
   The audited status palette hues are untouched.
2. *Topbar + footer chrome* — the site's 3px fixed gradient strip, sticky
   88px nav (brand wordmark SVG, See How It Works + Learn dropdowns —
   Learn carrying this page's own active "Choosing Your Model (DAAFBench)"
   entry — Get Started CTA, GitHub icon), and the Open Augments site footer
   were ported verbatim, with nav element selectors scoped to
   `nav.site-nav` so they can never touch the viewer's `<nav
   class="toc-rail">`. Hrefs follow the anatomy page's relative-path model
   (`../daaf-product/…`; the deploy script rewrites for production). The
   site's minimal nav JS (mobile toggle, dropdown blur/focus fixes, mobile
   dropdown expand) is ported in a self-contained IIFE introducing zero
   globals; the viewer's scrollspy stays authoritative for the TOC rail.
3. *Geometry rework* — the scrollspy's hardcoded 120px offset is now
   nav-height-aware (`NAV_SPY_OFFSET`, read once from `--nav-height` + 3px
   strip + 30px margin), `scroll-padding-top` became
   `calc(var(--nav-height) + 3px + 14px)`, and the TOC rail tops at
   `calc(var(--nav-height) + 3px)` so hash jumps and active-state detection
   work under the sticky bar.
4. *Component idioms (from the anatomy page)* — hero chips →
   `.summary-badge` treatment (mono teal value, uppercase display label,
   teal→indigo gradient top border, hover lift; the teal is decorative —
   chips are corpus counts, not pass/fail); `.verdict`/`.pd-callout` →
   gradient-border callout (teal→indigo left bar, gradient-tinted bg, 10px
   radius); uppercase teal eyebrow labels above nine section h2s;
   provider/subcategory chips and badges → 999px pills; criterion/run-dir
   `<code>` → mono chips on the indigo idiom (deliberately not teal — they
   sit next to pass/fail rates); selected run-list item → glowing
   left-accent card state (indigo); cards → `#151d2e` at 14px; h1 keyword →
   `gradient-text`; case prompts/tool outputs → mono panel treatment
   (tool-output divs gained a stable `tx-out` class because `.tx-collapsed`
   is removed on expand). P1–P4 phase-cascade coloring was evaluated and
   skipped (would require data-phase plumbing through the JS renderers —
   not cheap). Also a deliberate skip: the `.two-bars` block keeps its
   indigo left bar — it was not in the scoped gradient-border callout list.
5. *JS hex sweep + WP8 contrast re-audit* — all hardcoded old-token hexes
   in JS-generated markup were routed through the new tokens
   (`var(--…)` in inline styles; matching literals where SVG `fill`
   attributes require: axis/label text `#b0bcc8`, frontier ring `#f0f4f8`,
   gridlines moved to white-alpha borders since the old `#1e293b` lines
   vanished against the new card bg). Deliberate survivors: the audited
   status ramp and its `rgba(52,211,153,…)` frontier/annotation greens, the
   amber warning tints `#f59e0b`/`#fcd34d`, `MODEL_COLORS`/
   `MODEL_COLORS_LIGHT` (data colors — re-checked as distinguishable on the
   darker surfaces), the model-badge `#fff`, and the site's own literal
   gradients/logo SVG. The WP8 contrast audit was re-run against the new
   surfaces (floors 4.5:1 text / 3:1 UI): every pair passes with alphas
   unchanged — the darker surfaces raise most ratios (worst case `.rs-3`
   4.71:1 vs ~5.0 pre-remap; `.rs-na` 7.74:1; full measurements recorded in
   the template's WP8 re-audit comment at the `.rs-*` rules).
   `contain-intrinsic-size` values were sanity-checked and left unchanged —
   the global 1.5 line-height and font sizes were deliberately NOT moved to
   the site's 1.7, so type metrics are near-identical (live re-verify stays
   on the post-deploy retest list). Verified by sanity bundle regeneration:
   index.html 3.75 MB (+0.03 MB for the chrome), zero-orphan span check,
   nav/footer present exactly once, all `var()` references defined.


**User fine-tuning round (2026-06-12; template prose/JS + generator dev-guide
comments only — no generator code change, no version bump):** eleven
user-approved items from the visual review of `viewer_2026-06-12a.html`.

1. *Intro restructure* — the hero is now h1 + date + stat chips + the user's
   hero ¶1 only (TOC label "Verdict" → "Intro"); hero ¶¶2–4 moved **verbatim**
   to the top of About (the `hero-models`/`hero-runs` live-count spans and
   their build-time `__HERO_MODELS__`/`__HERO_RUNS__` substitution travel
   with them), ahead of the existing About intro, whose Wave-3 ¶1 was trimmed
   to its one non-duplicative sentence (mechanical scoring) so the
   companion-suite framing is stated exactly once, in the user's own words.
   The computed verdict callout (`#hero-verdict` + its renderHero prose and
   `.verdict` CSS) was removed entirely; a new compact **cost-performance
   preview** (`#cvp-preview`, battery basis / composite Perfect, reduced
   height, hover-only interactivity, one-line caption linking the full
   chart) sits after the takeaways — same `costPerfData`/`svgCostFrontier`
   code path as the full chart, rendered at init, deliberately absent from
   the TOC/`SECTION_IDS`/content-visibility machinery.
2. *Takeaway headline de-dup* — T1 "genuinely in a class of its own" →
   "simply in a class of its own" (T2 keeps "genuinely worse"); no other
   takeaway text changed.
3. *Leaderboard Timed-out column* — per-model timed-out share from
   `PRECOMPUTED.timeout_by_model` (runs basis, 1-decimal percent + k/n,
   em-dash idiom, sortable with worst-first default direction, deliberately
   NOT on the pass-green `.rs-*` ramp), with a tooltip + lb-foot clause
   naming the `timed_out`-flag basis (wall-clock timeouts AND silent stalls
   that ran out the clock; timed-out runs are still graded).
4. *Costs Detail section removed* (fully duplicative of CvP + leaderboard):
   the battery-multiplier canonical definition + disclosures survive
   condensed as an unconditional CvP footnote (`batteryDisclosureHtml()` —
   uncached basis, billing-export vs corpus-live token-mix sources, ⚠
   staleness meaning, reprice/caching drift, never-dollars, timeout
   depression); the published list-price table survives as a compact
   `<details>` collapsible beneath the CvP chart (`pricingDetailsHtml()`,
   input-ascending, non-sorting); every `#costs`/"Costs Detail" reference
   re-pointed to Cost vs. Performance; `renderCostsDetail` + its phase-scope
   and sort handlers + state deleted. The generator's `cost.battery`/
   `cost.models` precompute is untouched.
5. *#next-steps removed* — its CTA links live on in the hero ¶1 / About
   intro and the site footer carries the Open Augments attribution (the W3
   tone-percolation record above stands as history).
6. *kt-foot removed* — its small/uneven-reps imprecision point merged into
   the About "Denominators are small and uneven" caveat and its battery
   definition + drift sentence into the About cost caveat, which now hosts
   the `kt-foot-bat` battery-size span. **Span contract: still 23 `kt-*`
   setters — 22 spans in `#takeaways` + `kt-foot-bat` in the About Key
   Caveats.**
7. *CvP responsiveness* — the scatter (and the preview) now scales to its
   container (`viewBox` + `width:100%`/`height:auto`, `max-width` capped at
   the designed size); no resize re-render is needed because all positions
   are computed in viewBox coordinates. Leaderboard/heatmaps are tables and
   were confirmed out of scope.
8. *CvP double-tooltip fix* — the native `<title>` children on plot points
   (which overlapped the custom tooltip) were removed; the custom tooltip is
   authoritative. No other chart code emitted native tooltips.
9. *TOC first-click landing fix* — on the first explicit nav (TOC click or
   load-time deep link) the JS now renders every section and adds
   `body.nav-rendered`, which un-skips `content-visibility` document-wide so
   the document lays out at true heights once; the scroll then runs after a
   double-rAF against final geometry (previously the first click scrolled
   toward `contain-intrinsic-size` estimates and landed short). **Stays on
   the http(s) post-deploy retest list.**

Verified by single-file regeneration (`viewer_2026-06-12b.html`, for the
user's next `file://` review; official bundle regeneration deferred until
his approval): zero unsubstituted tokens, bidirectional 23-span check, 9
sections = TOC = `SECTION_IDS`, zero live `#costs`/"Costs Detail"/
next-steps stragglers, timed-out rates present for all 17 models, preview
block before `#about`, no native `<title>` tooltips on CvP points.

*Fine-tuning round 2 (2026-06-12; template prose/JS + generator dev-guide
comments only — no version bump):* the hero prose became a single user
"TLDR:" paragraph (the former hero ¶1's first sentence verbatim, links
intact, plus a new user-supplied DAAFBench: Orchestration framing
sentence), with the "layers together" remainder of the former ¶1 moved
verbatim to the top of About ahead of the orchestration explainer (About
now opens with four moved user paragraphs); `#cvp-preview` moved from
after `#takeaways` to between the hero and `#takeaways` (still
init-rendered, still outside the TOC/`SECTION_IDS`/content-visibility
machinery — it now scrollspy-reads as part of `#hero`); and the
leaderboard and CvP footnote prose (the `lb-foot` paragraphs and the
`cp-foot` paragraphs incl. `batteryDisclosureHtml()`) collapsed into
closed-by-default `<details class="foot-details">` "Details" expanders
whose bodies read at regular body size in `--text-2` rather than the tiny
`--text-3` footnote treatment (content unchanged; the `cp-pricing`
list-price collapsible stays its own sibling expander beneath the CvP
Details block; `prov-foot` and the `cp-foot` inside `cp-pricing` keep the
small idiom). Verified on `viewer_2026-06-12d.html`.

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
imported scorer modules for its whole life — a batch in flight (or launched
just before) a scorer edit scores with the pre-edit logic. Observed
2026-06-10: set `20260610_184022` was scored by a pre-overhaul import and
carried legacy vacuous criteria until a post-hoc rescore normalized it. The
rescore tools (`rescore_skill_routing.py`, `rescore_criteria_overhaul.py`,
`rescore_dispatch_timeout_rescue.py`) are the recovery path when this happens.

**Timed-out runs are killed gracefully (SIGTERM → 15s grace → SIGKILL).**
Until 2026-06-11 the executor's `subprocess.run(timeout=...)` killed timed-out
runs with SIGKILL, and the CLI's main-session transcript writes are
async/buffered — the final records (including Agent tool_use blocks) could be
lost even though everything earlier persisted. `harness/executor.py` now sends
SIGTERM first, drains stdout/stderr through a `KILL_GRACE_SECONDS = 15` grace
window (via `communicate(timeout=...)`, not `wait()` — `wait()` with full
pipes can deadlock while the CLI writes during its flush), and escalates to
SIGKILL only if the CLI outlives the grace. Observed in the 2026-06-11
validation run: the CLI exits ~0.1s after SIGTERM, well inside the window.
Timeout semantics are unchanged (`error = "Timed out after {N}s"`, the
`timed_out` flag, partial-stdout parsing). See § 11 item 9 for the validation
evidence and the honest limits of what one run proves. The dispatched
subagent's transcript is a separate file and survives the kill either way, so
a run dir's `subagents/` folder remains the forensic fallback for
reconstructing what a killed run actually did; the § 6 dispatch-recovery
fallback automates this for scoring.

## 10. Results Snapshot (2026-06-09)

Point-in-time results as of 2026-06-09. Rep counts: Phases 1 and 2 — 3 reps
for most models, Fable 5 at 2 reps; Phase 3 — Anthropic models at 2 reps,
OpenRouter at 3. Note: this snapshot predates the 2026-06-10 criteria rescore
(`rescore_criteria_overhaul.py`), which retroactively changed pc-07 rates in
the archived result sets. It also predates Phase 4 and the five-component
composite (§ 8) — its tiering and weakest-criterion claims describe the
P1-P3 corpus only; see § 12 for current composite results. A further caveat
(2026-06-11): the snapshot also predates the dispatch-recovery rescue rescore
(§ 6), which retroactively rescued 83 timed-out Phase 3 runs whose Agent
dispatch record was lost to the timeout SIGKILL — the dispatch rates and
Phase 3 scores below substantially understate the slow models that timed out
most often (Nemotron 3 Ultra, DeepSeek V4 Pro, Kimi K2.6, and both Gemmas
were most affected). The archived result sets now carry the corrected scores;
this table is preserved as recorded.

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

1. **`--disallowed-tools` cannot block compound commands.** Claude Code splits
   commands on shell operators (`&&`, `||`, `;`, `|`) and checks each
   subcommand independently, so `cd x && git commit` evades `Bash(git commit *)`
   deny patterns. Leading `*` wildcards (as formerly written in
   `harness/models.py`) do not work either — glob matching is prefix-anchored.
   **Resolved (2026-06-10)** by the env-gated PreToolUse hook
   `harness/hooks/block-git-writes.sh` (§ 9), which inspects the full command
   string (compound commands cannot evade it) and blocks any non-allowlisted
   git invocation. Registered in `.claude/settings.json` and verified
   end-to-end (nested benchmark-style session: `git commit` blocked,
   `git status` allowed). The dead git patterns were removed from
   `harness/models.py`; the `disallowed_tools` mechanism itself remains for
   non-git uses (e.g., disallowing the Agent tool).
2. **Fable 5 thinking blocks are encrypted** (empty string + cryptographic
   signature). Reasoning-quality analysis is structurally impossible for Fable;
   all behavioral assessment relies on observable output proxies.
3. **Phase 1-3 cost calibration profiles are stale.** Those per-case token
   profiles in `harness/cost_estimator.py` predate the `modelUsage` fix and
   reflect main-session-only tokens, underestimating subagent-dispatching
   cases. Phase 4 profiles were recalibrated per provider 2026-06-10 (§ 7).
4. **Subagents leaked artifacts outside the sandbox (root cause fixed
   2026-06-10).** Fixture contamination was an ordering bug: the dispatch
   runner staged fixtures into the sandbox BEFORE `prepare_sandbox()`
   rmtree-wiped that same sandbox, so at model launch the rewritten prompt
   pointed at deleted paths — models hunted the files by name and modified the
   originals under `datasets/test_fixtures/`. Fixed by wiping before staging
   (`wipe_sandbox=False` threaded through `RunConfig`), with the per-batch
   restore-to-HEAD as defense-in-depth and a post-batch contamination warning
   (§ 9). Rogue git commits are addressed by the git-blocking hook
   (limitation 1). Rogue `research/` project folders remain possible — models
   can still write outside the sandbox workspace; manual cleanup applies
   there.
5. **OpenRouter token counts are approximations.** The Anthropic-compatible
   endpoint reports counts from Anthropic's tokenizer, not each model's native
   tokenizer, so computed OpenRouter costs are approximate. Billing
   reconciliation (2026-06-10, § 7) bounded the tokenizer-driven error at
   ~2-6% for the strong-five models; the larger DeepSeek V4 Pro discrepancy
   was a pricing-config error (fixed in `models.yaml`; archived sets retain
   ~3.3x-understated DS Pro costs).
6. **Golden checkpoints embed recording-time framework content.** Golden JSONLs
   contain `attachment` records with CLAUDE.md and hook-injection content from
   when the session was recorded. Material framework changes can leave a
   resumed model facing conflicting instructions (old history vs. current
   system prompt). Carried from Reference § 11; the only mitigation is
   re-recording, which invalidates prior comparisons (§ 5).
7. **Scoring is not isolated from execution.** The original design (Reference
   § 2.1, § 6.3) required scorers to run outside the agent's environment, after
   UC Berkeley showed major agent benchmarks are exploitable wherever the agent
   can write state the evaluator reads. Currently the runners, scorers, and the
   model under test all share the DAAF container and filesystem. Low practical
   risk for internal behavioral scoring; a real gap if scores ever carry
   external weight.
8. **Manifests pin the DAAF git SHA but not golden content hashes.** A run
   executed against a worktree-modified golden is indistinguishable in
   provenance from one against the committed version (observed: the first
   fresh-golden Phase 4 sets pinned a SHA predating the golden's first
   commit — they ran against the identical worktree copy, so scoring was
   unaffected, but the manifest cannot prove it). Adding a golden content
   hash to `manifest.json` is the designed improvement (§ 12).
9. **Timeout SIGKILL races the async transcript writer (mitigated on both
   sides 2026-06-11).** The original `subprocess.run(timeout=...)` SIGKILLed
   timed-out runs while Claude Code's main-session transcript writes are
   async/buffered, so a killed run could lose an unflushed transcript tail —
   up to and including the assistant record carrying the `Agent` tool_use
   (observed: a main transcript frozen at exactly the 47-line golden
   checkpoint beside a 71KB subagent transcript). Two mitigations now stack.
   Scoring side (2026-06-11): the evidence-gated dispatch-recovery fallback
   and rescue rescore (§ 6) reconstruct lost dispatches from the surviving
   subagent transcripts. Executor side (2026-06-11): a graceful-kill ladder —
   SIGTERM → 15s grace window → SIGKILL (`KILL_GRACE_SECONDS` in
   `harness/executor.py`, § 9) — gives the CLI a flush opportunity before the
   hard kill. Validation evidence (one deliberate 10s-timeout run, mc-01 ×
   Haiku 4.5, throwaway set `20260611_031913`, since deleted — user decision;
   findings survive only in this record): the CLI exited ~0.1s after
   SIGTERM (never reaching SIGKILL), and the archived 15-line main transcript
   extended well past the injected prompt — assistant thinking, the `Skill`
   tool_use, and its tool_result, with a cleanly parseable final line — vs.
   the SIGKILL-loss signature of a transcript frozen at the prompt/checkpoint.
   Honest caveat: that run's last timestamped record predated the kill by
   ~6.4s (the model was mid-generation of its next turn, which no kill
   strategy can preserve — incomplete turns are never written), so the single
   run proves the ladder works mechanically but cannot positively demonstrate
   improved tail-flushing over SIGKILL; SIGKILL-era timed-out transcripts also
   end on complete lines, so the historical loss was a race, not a constant.
   Whether the ladder eliminates the race will only be confirmed by future
   organically timed-out runs. The scoring-side recovery (§ 6) remains the
   backstop for lost dispatch records either way.

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
  time). Phase 4 rep counts are complete — all 17 models at 3 reps as of
  2026-06-11 (§ 12 Current Status)
- **Recalibrate cost estimation profiles** from post-`modelUsage`-fix runs
  (Phases 1-3 remaining; Phase 4 recalibrated per provider 2026-06-10, § 7)

### Design Backlog (from the original reference)

The original design document —
`/daaf/research/2026-05-01_Benchmark_Testing/Benchmark_System_Reference.md` —
specifies components that were designed but never implemented. Its research,
architecture, and session-history sections are superseded by this README; the
items below are the still-valuable remainder.

- **Safety Boundaries test category** (Reference § 7.6): 8 single-prompt cases
  (sb-01..08) testing refusal of protocol violations — direct `python3`, CSV
  output, skipping QA, deleting failed scripts, `.env` reads, `rm -rf`,
  unconfirmed `git push`, helper functions. Highest-priority unbuilt category:
  Limitations 1 and 4 show models actually cross these boundaries (rogue git
  commits, sandbox leaks). Cheap single-prompt cases with scoring criteria
  already specified; complements the PreToolUse git-blocking hook (§ 9). Open
  design question: whether a hook-blocked rogue-git attempt should itself be
  scored as a safety failure (currently unscored).
- **Script Quality test category** (Reference § 7.5): 4-8 cases scoring
  generated scripts deterministically — section headers, IAT comments, no
  function definitions, parquet output, `run_with_capture.sh` execution,
  date-prefixed naming. Phase 3b's `subagent_behavior` scorer covers a subset
  (script written + wrapper used); § 7.5's eight per-script criteria would
  deepen it into convention-level scoring.
- **Skill Loading test category** (Reference § 7.3): 8-12 cases testing
  task-specific skill selection — the right data source skill (e.g., SAIPE vs.
  MEPS), discovery before query, skill loaded by the right tier (subagent vs.
  orchestrator). Phase 2 tests per-mode post-confirmation loading; this adds
  the selection dimension. The required mechanism (golden checkpoints +
  transcript scoring) already exists.
- **Protocol Adherence test category** (Reference § 7.4): multi-step ordering
  checks — the Turn Boundary Rule (confirmation turn contains zero tool
  calls), document loading order, stage progression, STATE.md creation timing.
  Phases 1-2 cover gates and reference loading; turn-boundary and
  phase-progression behavior is currently untested.
- **Deep golden-checkpoint catalog** (Reference § 7.7): 24 designed cases
  resuming mid-pipeline — PSU blocking gates, code-reviewer-before-next-script,
  STATE.md pre-flight verification, Data Onboarding interpretation gates, and
  six cross-mode boundary/escalation tests. The checkpoint mechanism (§ 5) is
  this design's infrastructure, but current phases exercise only two checkpoint
  types (post-confirmation, Ad-Hoc-initialized). The catalog and seed-directory
  design (Reference § 6.5) are the expansion path.
- **Tier 3 LLM-as-judge** (Reference § 8.3; rubric principles § 4.1, hybrid
  stack § 4.4, intermediate-artifact gap § 4.5): binary analytic rubrics, one
  criterion per judge call, mandatory negative criteria, conservative
  resolution when judge and deterministic scores diverge, Batches API for 50%
  scoring cost, and sanitization of agent content before judge prompts
  (prompt-injection warning, Reference § 2.1). This is the deeper fix for
  `prompt_has_context_section` (judge whether contextual content is present
  rather than matching a heading list) and the only designed path to
  IAT-quality and other intermediate-artifact evaluation. `scorers/llm_judge/`
  is the empty stub awaiting `judge.py` + `rubrics.yaml`.
- **Statistical aggregation — `aggregator.py`** (Reference § 9): Beta-Binomial
  posteriors with 90% credible intervals (non-overlapping intervals as the
  decision rule for model differences), pass^k consistency alongside pass@1
  capability, a safety-weighted composite adherence score (§ 9.4), and a
  report format (§ 9.5). Never built — the § 10 ranking above is
  hand-aggregated. With 2-3 reps × 17 models already in `results/`, credible
  intervals are immediately computable from existing data.
- **Hardening items** (Reference § 10, Phase 5): CI integration (cheap subset —
  Phase 1, one cheap model, 1 rep — on PRs touching framework files), a test
  case contribution guide, and effort-level comparison runs (`--effort`
  plumbing exists; see the reference's 2026-05-02 session notes for the
  `CLAUDE_CODE_EFFORT_LEVEL` override pitfall). The version-tagging deliverable
  is already satisfied by `manifest.json`'s DAAF git SHA.
- **Viewer fast-follows:** light theme / print stylesheet — deferred from the
  2026-06-10 viewer redesign as possible fast-follows, deferral reconfirmed
  2026-06-11 (§ 8 design record); og:image (requires an absolute URL, so it
  is a deploy-time addition) — deferred from the 2026-06-11 public-audience
  evolution, as were a touch/aria accessibility audit and responsive rework
  (trivial-only mobile fixes were applied) and a benchmarks link from the
  main `/daaf/README.md` (out of scope for now, user decision).
- **Phase 4 expansion reserve:** few-clusters wild bootstrap (pyfixest
  `advanced-inference.md`) is the first candidate if the suite grows — cut
  only for slot economics. Excluded as unroutable: time series (no hub branch;
  statsmodels-frontmatter-only), plain 2SLS without FE (dual-routed), polars
  larger-than-memory (implementation, not brainstorming), marimo app ("Always
  Load Together" ambiguity). Bayesian/survival route to "escalate to
  orchestrator" — a refusal test, candidate for a future Safety/Protocol
  category.

### Current Status / Next Steps (2026-06-11, updated ~07:00 UTC)

Point-in-time status; supersedes the retired `SESSION_NOTES.md` restart
prompts. Once these items land, fold the outcomes into the sections above
and update or remove this subsection.

- **Phase 4 baseline matrix (fresh goldens) — COMPLETE, now at 3 reps for
  ALL 17 models.** Originally 10 OpenRouter models × 3 reps + 7 Anthropic
  models × 1 rep, all on the post-third-hop framework and fresh goldens;
  Anthropic rep completion landed 2026-06-11 (next bullet). Fresh-golden sets in `results/` (all swept
  clean: 0 rate-limit events anywhere; python3-verified): `20260610_184022`
  (OR strong-five rep 1: glm-51, kimi-k26, deepseek-v4-pro, gemini-31-pro,
  deepseek-v4-flash — normalized post-hoc, § 9), `_194256` (Anthropic:
  haiku-45, sonnet-46, opus-46, fable-5; **Fable 5 near-ceiling: 15/15
  loaded, 14/15 refs_read, 13/15 all-criteria; Haiku pure third-hop failure:
  8/15 loaded, 0/15 refs_read**), `_201039` (OR second-five rep 1:
  qwen-36-27b, gemma-4-26b, nemotron-3-ultra, gemini-31-flash-lite,
  gemma-4-31b), `_203038` + `_203935` (strong-five reps 2-3), `_205051` +
  `_210215` (second-five reps 2-3; Gemma 31B stalled 10/15 and 14/15),
  `_214502` (Anthropic Opus 4.8/4.5/4.7 sequential, 0 errors: **Opus 4.8
  12/15 loaded, 8/15 refs_read, 6/15 all — clear top-end gradient 4.5 → 4.8
  → Fable**). Top open-weight routers across reps: DeepSeek V4 Pro and
  Qwen 3.6 27B (5-6/15 all-criteria); Kimi most rep-volatile (5-9/15
  loaded).
- **Phase 4 Anthropic rep completion — COMPLETE (2026-06-11, ~05:09 and
  ~06:56 UTC).** Two additional sequential 1-rep rounds, all 7 Anthropic
  models × 15 cases each, 300s timeout, same worktree scorer and goldens as
  the rep-1 baseline: `20260611_050913` (105 runs, $16.27, 6181s) and
  `20260611_065633` (105 runs, $16.91, 6404s). Both swept clean
  (python3-verified): 0 rate-limit events, 0 missing transcripts, 0
  timeouts. All Anthropic models now at 3 Phase 4 reps. Findings replicate
  the rep-1 gradient: Fable 5 12/15 all-criteria in both rounds (13-15/15
  loaded); Opus 4.8 7-8/15 all; Opus 4.7 names skills near-perfectly
  (14-15/15 engaged) but loads only 9-11/15 — two-hop decay persists
  post-routing-fix; Haiku 4.5 floor confirmed (0-1/15 all, 0-1/15
  refs_read). Hardest cases across all 7 models: sr-10 (0/7 refs both
  rounds), sr-11 (0/7 all both rounds), sr-08 (1/7 all both rounds);
  sr-14 remains the easy one-hop case (6-7/7). Composite effects on the
  full 52-set corpus (supersedes the smaller-corpus effects noted in the
  P4-joins-composite bullet below): Sonnet 4.6 rises to T2 (0.829), Opus
  4.8 T2 (0.796), Haiku 4.5 sits T4 (P4 perfect 0.02), Fable 5 sole T1
  (0.939); global weakest criterion is now `skill_agent_authoring`
  (13/48 = 27%, P2), displacing `expected_refs_read`.
- **Viewer cost-plot phase filter — RESOLVED (2026-06-10 viewer session).**
  Cost vs. Performance now has a phase basis selector (Composite + P1-P4;
  perf values/frontiers precomputed per group, dynamic for future phases) and
  Costs Detail gained a "Perfect-rate scope" phase toggle. Same session:
  template group-order array gained `skill_routing` (the one real Phase 4
  wiring gap — P4 had rendered via unordered-tail fallback), and all
  user-visible severity labels renamed Hard→**Critical** / Soft→**Normal**
  (viewer + README §§ 2/6; data keys `hard_requirements`/`tier1`/etc.
  unchanged). Generator v2.4.0.
- **Harness gap (bookmarked): transcript-less timeout runs.** 4 runs
  (`pc-03`/`pc-07` × Fable 5 in `20260609_203258` and `20260609_215903` —
  the two sets with the short 120s pc-timeout) were flagged timed-out with NO
  transcript.jsonl archived. Update 2026-06-11 (~12:48 UTC, user decision):
  those 4 runs were moved out of scoring into each set's `removed_runs/`
  (provenance README.txt alongside; the viewer loads `runs/` only) and
  replaced by fresh fable-5 pc-03/pc-07 runs at the corpus-standard 300s
  timeout in set `20260611_124829` — all 4 replacements pass all criteria
  (4/4). One replacement (pc-07 rep 0) organically timed out at 300s under
  the new graceful-kill ladder and still archived a fully scored transcript
  (3/3 criteria PASS, 6 tool calls visible) — the first organic post-ladder
  timeout, supportive evidence the flush race is closed, though confounded
  with the ceiling change (120s → 300s gives the CLI more time to write
  early records regardless of kill signal). Original working hypothesis: timeout-kill lands before
  the CLI emits session metadata, so the collector has no session ID to
  resolve (slowest model × tightest ceiling × heaviest cases). Confirmation
  pass = read `harness/executor.py`/`collector.py` transcript-resolution
  logic against one of those run dirs. Related fix candidates: write
  transcript on timeout; first-activity stall detector (below). Update
  2026-06-11: the related Phase 3 manifestation — transcripts PRESENT but
  truncated mid-flush by the timeout SIGKILL, losing the Agent tool_use
  record — is now resolved on the scoring side (§ 6 dispatch-recovery
  fallback + `rescore_dispatch_timeout_rescue.py`; 83 runs rescued, § 11
  item 9). Update 2026-06-11 (~03:25 UTC): the executor graceful-kill ladder
  has landed (SIGTERM → 15s grace → SIGKILL; § 9, § 11 item 9), validated
  mechanically with one deliberate 10s-timeout run — the throwaway validation
  sets `20260611_031838` (completed under its 20s timeout, no kill) and
  `20260611_031913` (timed out; transcript archived past the prompt) were
  deleted at user direction 2026-06-11 (findings recorded in § 11 item 9).
  The ladder may also help the
  transcript-less manifestation (a SIGTERM'd CLI gets a chance to create/
  flush the transcript before dying), but that is unverified — the
  confirmation pass against `executor.py`/`collector.py`
  transcript-resolution logic remains open. The post-rescue viewer
  regeneration has landed (`viewer_2026-06-11g.html` — see the
  viewer-current bullet below).
- **Gemma 4 31B kept IN by user decision:** silent stalls are documented
  model-attributable failures, not artifacts to exclude — forensic sweep of
  Phases 1-3 (full corpus, transcript-level) found 18.5% silent-stall rate
  for 31B and 9.3% for 26B across *different* provider pins, vs ≤1% for
  Gemini models and ~1-3% ambient elsewhere: a Gemma-subfamily defect, not
  Google-family or single-endpoint. 31B reproduced 10/15 zero-turn 300s
  stalls in each fresh batch. Stalls score as failed runs.
- **Timeout stays 300s for mixed/OpenRouter batches** (runtime analysis of
  199 completed fresh runs: p99=252s, max=271s; the slow tail is OpenRouter
  per-turn latency ~2x Anthropic, not work volume). Anthropic-only batches
  are safe at 150s (max observed 129s). Better stall remedy than tighter
  ceilings: harness first-activity detector (no event by ~90s → kill) —
  candidate § 12 backlog item. Harness artifact to know: timeouts zero
  `turns`/`output_tokens` in result.json, so stall analysis requires
  transcript-level reconstruction.
- **PHASE4_TOKENS recalibration — RESOLVED (2026-06-10), provider-split.**
  Calibrated from all eight fresh sets (520 usable runs); split into
  `PHASE4_TOKENS_OPENROUTER`/`_ANTHROPIC` after a blended profile
  over-estimated Anthropic 3.3-8.4x (caching-regime mismatch). Validated
  0.90x aggregate, 0.90-0.91x per provider (§ 7; scripts in `_sandbox/`).
  Same session: **DeepSeek V4 Pro pricing corrected** in `models.yaml`
  ($0.435/$0.87 → $1.44/$2.88) via billing-export reconciliation — archived
  sets understate DS Pro costs ~3.3x (§ 7 Pricing correction).
- **Public-audience viewer evolution — RESOLVED (2026-06-11 session,
  generator v2.5.0 → v2.6.0).** The viewer was reworked for public
  consumption on the project website: full audience inversion of the prose,
  a new dated Key Takeaways editorial section (figures span-injected from a
  new `timeout_by_model`-extended PRECOMPUTED), an always-visible
  Perfect-vs-Critical "two bars" About block, a 45-entry plain-language
  criterion label map (CRIT_LABELS), and head metadata for web hosting
  (og:url placeholder pending deploy). Full record: § 8 design record,
  "Public-audience evolution" addendum. Deployment (stable filename,
  compression, upload, og:image) stays in the user's website infrastructure;
  an http(s) retest is needed post-deploy.
- **Battery-cost metric + pricing foundation fixes — RESOLVED (2026-06-11,
  generator v2.7.0 → v2.8.0 → v2.8.1).** Full record:
  § 8 "Cost methodology evolution" addendum. New data dependency: the
  generator now reads the latest `derived/openrouter_reconciliation_*.json`
  (fail-soft if absent; staleness guard warns when OpenRouter corpus run
  counts drift from the snapshot — currently 153 = 153 for all 10, no
  warnings). `models.yaml` rates corrected for Gemma 4 26B (×2.12),
  DeepSeek V4 Flash (×1.34), Gemma 4 31B (×1.26); harness `compute_cost()`
  now bills cache writes at 1.25× input (future runs only). Verified by
  sanity regeneration first; the official regeneration landed as
  `viewer_2026-06-11j.html` — the first dated viewer carrying battery costs
  and the corrected rates. The Key Takeaways **cost-ratio re-adjudication**
  the rate corrections forced (corrected DS Flash rates shifted
  `kt-t5-glmx` 1/12 → 1/9 and `kt-t5-opusx` 1/81 → 1/61 on the blended
  basis, breaking T5's hand-written "on the order of 1/100 of frontier
  cost" sentence; the original prediction that kt-t4-ratio and the T3
  spans were unaffected was overtaken — those claims moved to the battery
  basis too) was resolved the same day by moving all takeaway cost claims
  to the battery metric, displayed as relative multipliers vs Opus 4.8
  rather than dollars (generator **v2.8.1**, presentation-only bump; § 8
  addenda: design record item 2 second re-adjudication + cost-methodology
  presentation note), regenerated as `viewer_2026-06-11k.html`.
- **Viewer e099982 repair pass — RESOLVED (2026-06-12; template + dev-guide
  comments only, no generator code change, no version bump).** The user's
  hand edit of the hero and Key Takeaways (commit e099982) deleted spans
  that `renderHero` and `fillAboutCounts` still wrote to, crashing both at
  init (hero chips/verdict never rendered; the surviving `ab-*` counts froze
  as em dashes). Repairs: hero "17 models" / "1,700 repetitions" re-injected
  as live `hero-models`/`hero-runs` spans filled by `renderHero` from
  `PRECOMPUTED.totals` (static text = previous generation's figures, not an
  em dash); dead `ab-models`/`ab-runs` writes deleted; `kt-t4-dsflash` fill
  added; the 11 orphaned `fillTakeaways` writes pruned; takeaway 2's garbled
  Critical-only sentence repaired with four injected `kt-t2-o4Xh` spans from
  `composite_hard` (claim direction verified: Opus 4.7's Critical-only dip,
  8.5 pts vs the best of 4.5/4.6, exceeds its Perfect-composite dip of
  4.9 pts); takeaway 5's stale `kt-t6-*` ids renumbered `kt-t5-*` in
  lockstep with their setters; orphaned `.kt-badge`/`.kt-disclaimer` CSS
  removed; typo/entity fixes in the user-voice prose; Key Caveats `<details>`
  gained `id="caveats"` and the kt-foot reference now links `#about`.
  **Span contract now 23 `kt-*` spans** (was 29); generator dev-guide
  comment block refreshed (span contract count, date-lives-in-the-h2 rule,
  template anchor re-points incl. PD_EXPLAINERS ~L1762 → ~L2211). Verified
  by sanity regeneration: bidirectional span check zero orphans both
  directions; all 32 kt/hero/ab injection values non-null on the 53-set
  corpus.
- **Viewer multi-file bundle architecture — RESOLVED (2026-06-12, generator
  v3.0.0).** The official viewer artifact is now a bundle directory with a
  new naming convention, `daafbench_YYYY-MM-DD[suffix]/` (letter suffix
  auto-increments when the candidate exists — the no-overwrite convention
  carried over from the dated single files): `index.html` (~4 MB; DATA
  minus transcripts, plus a `transcripts_index`) and per-result-set
  transcript shards `data/tx_{result_set}.json` fetched on demand by the
  Run Explorer (memoized shard cache, stale-click guard, visible
  fetch-failure fallback). `--single-file [PATH]` retains the ~25 MB
  monolith under the `viewer_YYYY-MM-DD{letter}.html` naming as the
  offline/`file://` audit path; `file://` support is explicitly dropped for
  bundles (sibling-file `fetch()` is CORS-blocked on `file://` — the
  fallback message carries a `python3 -m http.server` hint).
  `benchmarks/.gitignore` gained the `daafbench_*/` companion pattern.
  Full record: § 8 "Multi-file bundle architecture" addendum; the http(s)
  post-deploy retest list grew from three to four items (§ 8
  public-audience evolution item 7). The first bundle artifact is
  `daafbench_2026-06-12a/` (2026-06-12 official regeneration, generator
  v3.1.1 — see "Viewer current" below); `viewer_2026-06-11k.html` remains
  the last monolith-only official artifact.
- **Battery multiplier promoted to headline cost figure / blend31 removed —
  RESOLVED (2026-06-12, generator v3.1.0).** The blended 3:1 $/Mtok
  formulation was retired everywhere (user rationale: benchmark cost was
  dominated by input tokens, making a 3:1 in/out blend misleading) and the
  battery-cost multiplier (× Opus 4.8 = 1.0×) became the headline cost
  figure page-wide: leaderboard cost column re-pointed (with ⚠ staleness
  propagation to its tooltip), scatter default price basis now battery
  (input/output remain as secondary toggles), About caveat and section
  leads reordered multiplier-first. Schema change: `blend31` removed from
  `PRECOMPUTED.cost.models[]` and `cost.frontiers` (battery first); sanity
  report prints the battery frontier. Full record: § 8 "Battery multiplier
  promoted" addendum. Verified by sanity regeneration (bundle +
  `--single-file`); lands in the next official artifact.
- **Tone percolation + "DAAFBench: Orchestration" naming + hero chips
  redesign — RESOLVED (2026-06-12; template prose + generator dev-guide
  comments only, no version bump).** The maintainer's voice and website
  framing percolated through all remaining viewer prose: suite named
  "DAAFBench: Orchestration" (title/meta/TOC/hero/About/CTA, with the
  planned analytic-competency companion suite framed as the complementary
  half); full rewrites of the leaderboard lead, CvP lead (voice-only), and
  all five PD_EXPLAINERS; moderate passes per the percolation map; hero
  chips hoisted above the prose and redesigned to zero-context facts; About
  intro restored DAAF/GitHub links; new static `#next-steps` closing CTA
  (TOC + SECTION_IDS registered) with Open Augments attribution; glossary
  lab-manager gloss; exactly two sanctioned voice-anchor edits (hero
  pair-naming insertion; takeaway 1 "a Perfect average score of"
  clarifier); stale "1,700+" JS comments neutralized; dev-guide anchors
  refreshed. Full record: § 8 "Tone percolation" addendum. Verified by
  sanity bundle regeneration + bidirectional span check (zero orphans;
  23-span contract unchanged); lands in the next official artifact.
- **Site-cohesion styling — RESOLVED (2026-06-12; template-only, no
  generator change, no version bump).** The viewer adopted the DAAF product
  site's design tokens, Google Fonts (Space Grotesk / DM Sans / JetBrains
  Mono), 3px gradient strip + sticky topbar (with the Learn dropdown's
  active "Choosing Your Model (DAAFBench)" entry), Open Augments footer,
  and selected anatomy-page component idioms; teal is chrome-only and the
  audited status palette hues are untouched (WP8 contrast re-audit against
  the new surfaces: all floors pass, alphas unchanged). Scrollspy offset /
  scroll-padding / TOC-rail top are now `--nav-height`-aware. Full record:
  § 8 "Site-cohesion styling" addendum. Verified by sanity bundle
  regeneration (index.html 3.75 MB, +0.03 MB); lands in the next official
  artifact. **The post-deploy visual check now additionally covers: topbar
  dropdown open/close (desktop hover + mobile tap), the mobile hamburger
  toggle, the hoisted hero chips' badge treatment, the site footer, and
  Google Fonts loading (plus the graceful system-font fallback when
  offline).**
- **Viewer user fine-tuning round — IMPLEMENTED, pending user review
  (2026-06-12; template + generator dev-guide comments + this README, no
  generator code change, no version bump).** Eleven user-approved items
  from his visual review of the `2026-06-12a` artifact: verdict callout
  removed and the intro restructured (hero = h1 + chips + ¶1; hero ¶¶2–4
  moved verbatim to the top of About; TOC label "Intro"); a compact
  cost-performance preview after the takeaways (same chart code path);
  T1 headline de-dup ("simply"); a sortable leaderboard Timed-out column
  from `timeout_by_model`; the Costs Detail section removed (battery
  definition condensed into an unconditional CvP footnote; list-price
  table relocated as a CvP collapsible; all references re-pointed);
  `#next-steps` removed; kt-foot folded into the About caveats
  (`kt-foot-bat` moved there; span contract still 23 setters = 22 in
  #takeaways + 1 in About); CvP scatter + preview made responsive
  (viewBox scaling, no re-render needed); native `<title>` point tooltips
  removed; TOC first-click landing fixed via first-nav full render +
  `body.nav-rendered` content-visibility un-skip (http(s) retest item).
  Full record: § 8 "User fine-tuning round" addendum. Review artifact:
  `viewer_2026-06-12b.html` (single-file, for the user's next `file://`
  pass); the official **bundle regeneration is deferred** until his
  approval.
- **Viewer fine-tuning round 2 (2026-06-12; template prose/JS + generator
  dev-guide comments only — no version bump):** hero reduced to a single
  user "TLDR:" paragraph (former ¶1 first sentence + new user DAAFBench
  framing sentence, verbatim); the "layers together" remainder moved
  verbatim to the top of About; `#cvp-preview` moved above `#takeaways`
  (scrollspy-reads as part of `#hero`); leaderboard + CvP footnotes
  collapsed into closed-by-default "Details" expanders at regular body
  size (`cp-pricing` stays a sibling expander; other footnote surfaces
  unchanged). Full record: § 8 fine-tuning addendum, round-2 paragraph.
  Review artifact: `viewer_2026-06-12d.html` (single-file).
- **Viewer current:** `daafbench_2026-06-12b/` (generator v3.1.1; 53 sets /
  2,493 runs; 2026-06-12, user-approved for deploy) — adds the fine-tuning
  rounds 1-2 (Verdict removal, Intro TOC label, timed-out leaderboard
  column, responsive CvP chart + native-tooltip removal, TOC first-click
  render fix, next-steps + Costs Detail section removals w/ disclosure
  relocation, TLDR hero + preview-above-takeaways restructure, footnote
  Details expanders), the website-deploy compat edits (canonical
  `daaf.openaugments.org/bench/`, short "Choosing Your Model" nav label),
  and the user's final manual prose touches. Supersedes
  `daafbench_2026-06-12a/` (first official bundle
  artifact; generator v3.1.1; 53 sets / 2,493 runs; 2026-06-12) — carried
  everything since `_11k`: the v3.0.0 bundle architecture, the v3.1.0
  battery-multiplier headline promotion, the 2026-06-12 user hero/takeaways
  edit + e099982 repair pass (23-span contract), the tone-percolation and
  site-cohesion template passes, and the 2026-06-12 post-review fix pass
  cycle 1 (T2 dip sentence, leaderboard component naming, entity sweep,
  phrasing dedupes, plus v3.1.1's build-time `__HERO_MODELS__`/
  `__HERO_RUNS__` substitution so the hero's static fallback counts can no
  longer go stale) — superseded before deploy. That bundle superseded
  `viewer_2026-06-11k.html` (generator v2.8.1; 53 sets /
  2,493 runs; battery-cost surfaces converted to relative multipliers vs
  Opus 4.8 — Costs Detail table, Cost vs. Performance battery axis
  normalized so Opus 4.8 = 1.0×, disclosure rewrites — plus the second Key
  Takeaways re-adjudication, 29 `kt-*` spans; § 8 addenda; the last
  monolith-only official artifact), which superseded `_11j` (v2.8.0; 53 sets / 2,493 runs; first
  dated viewer with battery costs and the corrected rates, but its takeaway
  prose and dollar-based battery display predated the re-adjudication and
  the multiplier decision), which superseded
  `_11i` (v2.6.0 → v2.7.0;
  same 52-set / 2,493-run corpus as `_11h`; transcript-keying collision fix —
  § 8 notable internals: composite `{result_set}/{run_dir}` transcript keys
  recovered 857 previously-overwritten main transcripts, 2,489 now embedded
  vs `_11h`'s 1,632, and ended cross-set subagent-transcript misattribution,
  500 subagent entries vs 201; leaderboard/composite figures unchanged from
  `_11h`; its takeaway sentences were still those adjudicated on the 50-set
  corpus — resolved by the second re-adjudication above), which superseded
  `_11h` (v2.6.0; 52 sets / 2,493 runs; added the two Anthropic
  Phase 4 rep-completion sets `20260611_050913`/`_065633`; bare run-dir
  transcript keys), which superseded
  `_11g` (v2.6.0; 50 sets / 2,283 runs; five-component
  composite; embedded the post-rescue corpus
  (dispatch-recovery rescue rescore, § 6) AND the post-rescue
  re-adjudicated Key Takeaways (T4 reframed around DeepSeek V4 Pro
  leading the open-weight pack into the frontier tier, with a DS Pro
  timeout-rate caveat; T2's tier-drop sentence retired; T1/T3/T5/T6
  unchanged — § 8 addendum item 2)), which had superseded
  `_11e` (pre-rescue scores) and `_11f` (post-rescue scores
  but pre-re-adjudication takeaway prose, generated before the two
  throwaway graceful-kill validation sets were deleted), which had
  superseded `_11d.html`/v2.5.0, `_10s.html`/v2.4.0, and intermediates
  `_11a`-`_11c` (`_11c` differed only in doc-consolidation comment
  repoints, rendered output identical, while a review pass caught stale
  four-component prose in the leaderboard lead, hero verdict, and P4
  deep-dive explainer that shipped into `_11a`/`_11b`). Earlier dated
  viewers superseded — retention/deletion is pending housekeeping (user
  decision; user deletes).
- **P4 joined the leaderboard composite + tier bands — RESOLVED (2026-06-11
  session; user-approved 2026-06-10).** `skill_routing` added to
  `COMPOSITE_GIDS` (generator v2.5.0); composite is now the unweighted mean
  of five components. Models lacking a component score on their available
  components with the leaderboard "partial" disclosure chip (existing
  mechanism; on the current corpus all 17 models have all five components,
  so no partial markers appear). Effects (point-in-time on the 2026-06-11
  pre-rep-completion corpus — composite figures superseded by the Phase 4
  Anthropic rep-completion bullet above): the tier **gap rule** now yields
  5 tiers natively (quartile fallback no longer triggers); Fable 5 is sole
  T1 (0.948); Haiku 4.5 drops to T3 (P4 perfect rate 0.00); global weakest
  criterion is now `expected_refs_read` (25%, P4). Same dispatch: § 8 pin
  sentence rewritten (+ phase-filter mention), redesign-plan decision 1
  superseded + its addendum rewritten + header version note (that plan doc
  was later absorbed and deleted — see the consolidation bullet below),
  generator
  docstring/console "Hard"→"Critical" labels, dev-guide anchors fixed +
  `phaseSpan`/`ab-pX-cases` registration step added, template tooltip
  double-space fixed.
- **Transient docs consolidated — RESOLVED (2026-06-11 session).** This
  README is now the single source of truth: `VIEWER_REDESIGN_PLAN.md`,
  `PHASE4_SKILL_ROUTING_PLAN.md`, `PHASE4_ROUTING_FIX_SCOPING_20260610.md`,
  and `PHASE4_TRANSCRIPT_REVIEW_20260610.md` were absorbed (durable content
  → § 2 per-case ground-truth table + agent-disallow tradeoff, § 5
  routing-fix gloss, § 6 Phase 4 scoring rationale + two-hop-decay record,
  § 8 "Viewer design record" subsection, § 12 expansion-reserve/fast-follow/
  open-follow-up bullets) and deleted (user decision, absorb-then-delete).
  All code/doc citations repointed to README sections (generator, template,
  `run_skill_routing.py`, `scorers/deterministic/skill_routing.py`);
  `archive/` and `research/2026-05-01_Benchmark_Testing/
  Benchmark_System_Reference.md` deliberately untouched.
- **Open follow-ups from the Phase 4 routing-fix scoping (2026-06-10):**
  (1) frontmatter description budget — svy (506 ch), polars (416), marimo
  (486) exceed the 250-char limit documented in skill-authoring, yet the live
  environment shows full descriptions; verify which claim is stale before
  fixing. (2) "For implementation syntax" framing persists in ~12
  data-scientist reference-file headers (descriptive-analysis.md:3,571;
  statistical-modeling.md:3; causal-inference.md:5-6; survey-analysis.md:7;
  exploratory-unsupervised.md:3,261; supervised-ml.md:3,188,230,354;
  geospatial-operations.md:5) — the Session 4 fix targeted SKILL.md + the
  mode doc; this sweep was recommended but not executed. Pairs with the
  data-scientist SKILL.md:353 residual in the "Optional" bullet below.
  (3) Maintainer note: Phase 4 criterion
  *emission* is hardcoded in the scorer; the cases' `hard_/soft_requirements`
  lists drive viewer display only and must stay synchronized but do not drive
  scoring.
- **Optional:** golden content hash in `manifest.json` (§ 11 item 8); review
  of the data-scientist `SKILL.md:353` "Tool-specific syntax" branch label
  (accepted residual unless transcripts show models exploiting it).

## 13. AI Disclosure

The benchmark suite — harness, datasets, scorers, golden checkpoints, viewer,
and this documentation — was developed using DAAF in Framework Development
mode, with Claude performing scoping, implementation, review, and analysis
via specialist dispatches. The human researcher set scope, made all design
decisions at confirmation checkpoints, and personally applied all
safety-critical configuration (e.g., the `settings.json` hook registration).
Reported scores are produced by the deterministic criteria described in § 6,
not by human judgment of model output quality.
