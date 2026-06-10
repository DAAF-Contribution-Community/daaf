# DAAF Framework Adherence Benchmarks

Benchmark system for evaluating LLM **behavioral conformance** to DAAF orchestrator
protocols. It answers one question: when a model is placed inside the real DAAF
container — hooks firing, skills discoverable, agents dispatchable — does it follow
the framework's protocols?

This README is the authoritative documentation for the benchmark system. The
`SESSION_RESTART*.md` files in `archive/` are historical session notes (including
run-level provenance for the 2026-06 result sets) superseded by this document for
system-level documentation; `SESSION_NOTES.md` tracks the current session.

---

## 1. What This Is

The benchmark measures whether models acting as the DAAF orchestrator:

- Classify user requests into the correct engagement mode and present a
  confirmation gate before executing
- Load the correct mode reference files and skills after the user confirms
- Dispatch the correct subagent type via the Agent tool with a properly
  structured prompt (BASE_DIR, mode marker, task/context/instructions sections)

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
protocol tests). Three phases are implemented; where this README and the design
document differ, the code (and this README) reflect current reality.

## 2. The Three Phases

| Phase | Dataset | Cases | Start State | What It Tests |
|-------|---------|-------|-------------|---------------|
| 1 — `mode_classification` | `datasets/mode_classification/cases.jsonl` | 15 (mc-01..mc-15) | Cold start (no checkpoint; `CHECKPOINT_LINES = 0`) | Mode classification, confirmation gate present, no premature execution, reasoning quality |
| 2 — `post_confirmation` | `datasets/post_confirmation/cases.jsonl` | 9 (pc-01..pc-09), one per engagement mode | Resumes from a golden checkpoint ending at the confirmation gate; prompt is "Sounds good, let's proceed." | Whether the model loads the expected mode reference files and skills after confirmation |
| 3 — `dispatch_compliance` | `datasets/dispatch_compliance/cases.jsonl` | 12 (dc-01..dc-12), 2 per agent type | Resumes from an Ad Hoc Collaboration initialized checkpoint (orchestrator + mode reference + data-scientist skill loaded) | Whether the model dispatches the correct subagent with a properly structured prompt |

Phase 3 covers six agent types: research-executor, source-researcher,
search-agent, debugger, code-reviewer, and data-ingest (2 cases each).

**Phase 3b — subagent behavior.** When a dispatch succeeds, the dispatched
subagent's own transcript (`~/.claude/projects/-daaf/{session_id}/subagents/agent-*.jsonl`)
is scored separately by `scorers/deterministic/subagent_behavior.py`. Behavioral
expectations are derived from the agent type (e.g., did a coding agent write a
script and execute it via `run_with_capture.sh`), with no per-case configuration.
Results appear as `subagent_criteria` alongside the dispatch criteria and are
shown as "Phase 3b" in the viewer.

**Test case format** (`cases.jsonl`, one JSON object per line):

```json
{"id": "mc-01", "category": "mode_classification", "subcategory": "unambiguous",
 "prompt": "...", "expected": {"mode": "data_onboarding", "confirmation_gate": true},
 "turn_limit": 5, "cost_tier": "low",
 "hard_requirements": ["mode_correct", "confirmation_gate_present", "no_premature_execution"],
 "soft_requirements": ["reasoning_present"]}
```

Phase 2/3 cases additionally carry `golden_checkpoint` (and, for Phase 3,
`golden_project_path`) fields.

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
                  │      [--disallowed-tools <git patterns>] [--effort <level>]
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
| `harness/` | Core machinery: `executor.py` (CLI invocation), `checkpoint_manager.py` (golden cloning + sandbox lifecycle), `cost_estimator.py` (estimation + cost recomputation), `models.py` (dataclasses: TestCase, RunConfig, RunResult, etc.), `model_loader.py` (models.yaml loading + provider env wiring), `collector.py` |
| `scorers/deterministic/` | `mode_classification.py`, `checkpoint_adherence.py`, `dispatch_compliance.py`, `subagent_behavior.py` |
| `scorers/llm_judge/` | Unimplemented stub (see § 6) |
| `datasets/` | `{phase}/cases.jsonl` plus `test_fixtures/` (buggy scripts and data for debugger/code-reviewer cases) |
| `golden/` | Golden checkpoint JSONLs (see § 5) |
| `config/` | `models.yaml` — model matrix with pricing |
| `scripts/` | Phase runners, `generate_goldens.py`, `generate_results_viewer.py`, utilities |
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
```

All three runners share an identical CLI:

| Flag | Default | Meaning |
|------|---------|---------|
| `--reps N` | 3 | Repetitions per case × model |
| `--models a,b` | all | Comma-separated model keys (lowercased names from models.yaml, spaces → hyphens, dots removed: `fable-5`, `sonnet-46`, `deepseek-v4-flash`) |
| `--provider X` | all | `anthropic`, `openrouter`, or `all` |
| `--test-id a,b` | all | Specific case IDs (e.g., `mc-01,mc-05`) |
| `--sequential` | off | Run one at a time instead of parallel |
| `--delay S` | 2 | Seconds between parallel launches (ThreadPoolExecutor stagger) |
| `--timeout S` | tier-based | Override per-run timeout (defaults: low 120s, medium 300s, high 600s by case `cost_tier`) |
| `--yes` / `-y` | off | Skip the cost confirmation prompt |

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

1. Cleans and recreates the run's sandbox directory, seeding it from a
   `{checkpoint}_seed/` directory if one exists
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
| `dispatch_compliance/ad_hoc_initialized.jsonl` | 47 | All 12 Phase 3 cases — Ad Hoc mode fully initialized |
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

## 6. Scoring

All current scoring is **deterministic** — transcript parsing with string and
structural checks, no LLM involvement. Scorers read the session transcript
JSONL and consider only lines **after** the golden checkpoint's line count, so
pre-recorded history is never re-scored.

**Criterion tiers.** Each criterion carries a tier (`tier1` = structural
must-pass, e.g., `agent_dispatched`, `correct_subagent_type`; `tier2` =
protocol detail, e.g., `prompt_has_base_dir`, `prompt_has_context_section`).
Independently, each test case declares `hard_requirements` and
`soft_requirements` listing which criteria are hard vs. soft for that case.

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

**Perfect vs. Hard/Soft rates — intentionally different metrics:**

| Metric | Unit | Definition |
|--------|------|------------|
| Perfect | per-run | Did ALL criteria pass for this run? |
| Hard rate | per-criterion | Across all runs, what fraction of hard criteria passed? |
| Soft rate | per-criterion | Across all runs, what fraction of soft criteria passed? |

These can diverge sharply: 4 runs each failing one soft criterion yields 67%
Perfect with 100% Hard and 96% Soft. Both views are reported.

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
`cache_creation_tokens` are captured in results but excluded from
`compute_cost()`, so cache-write costs are not reflected in computed totals.

**Pre-run estimation.** `cost_estimator.py` holds per-case calibration token
profiles (average input/output/cached per case, collected 2026-06-08 from
Haiku 4.5, DeepSeek V4 Flash, and Gemini 3.1 Flash Lite). These drive the
pre-launch estimate and confirmation prompt. **The profiles are stale:** they
were collected before the `modelUsage` fix and reflect main-session-only
tokens, so they underestimate costs for subagent-dispatching cases (all of
Phase 3). Treat pre-run estimates as lower bounds until recalibrated (§ 12).

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

**Viewer generation:**

```bash
python3 benchmarks/scripts/generate_results_viewer.py                 # all result sets
python3 benchmarks/scripts/generate_results_viewer.py \
    --results 20260609_214335 20260609_224824 --output /tmp/view.html
```

Produces a self-contained HTML file (default `benchmarks/viewer.html`, ~11 MB)
embedding all selected result sets including full transcripts. It works opened
directly from disk (`file://`). Tabs: Overview, Models, Cases, Costs,
Transcripts, with phase filters including 3a (dispatch) and 3b (subagent
behavior). Notable internals:

- **Global rep renumbering:** runs from separate `--reps 1` batches all carry
  `rep=0`; the generator renumbers sequentially per `(phase, model, case_id)`
  across all loaded result sets
- **HTML5 tokenizer safety:** all `<` in the embedded JSON are escaped to
  `\u003c`. Transcripts contain literal `<!--` and `<script` sequences that
  otherwise flip the HTML5 parser into escaped-script states and break rendering
- **Chrome `file://` handling:** hash state uses direct `location.hash`
  assignment instead of `history.replaceState`, which Chrome restricts on
  `file://` URLs

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

**Fixture isolation (Phase 3).** `run_dispatch_compliance.py` copies any
`datasets/test_fixtures/` paths referenced in a case prompt into the run's
sandbox and rewrites the prompt, and creates a sandbox `workspace/` containing
`scripts/run_with_capture.sh` so subagents treating the workspace as BASE_DIR
find it. Originals should never be touched — but see Known Limitation 4.

## 10. Results Snapshot (2026-06-09)

Point-in-time results as of 2026-06-09. Rep counts: Phases 1 and 2 — 3 reps
for most models, Fable 5 at 2 reps; Phase 3 — Anthropic models at 2 reps,
OpenRouter at 3.

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
   deny patterns. Leading `*` wildcards (as currently written in
   `harness/models.py`) do not work either — glob matching is prefix-anchored.
   The recommended fix is a PreToolUse hook; accepted limitation for now.
2. **Fable 5 thinking blocks are encrypted** (empty string + cryptographic
   signature). Reasoning-quality analysis is structurally impossible for Fable;
   all behavioral assessment relies on observable output proxies.
3. **Cost calibration profiles are stale.** The per-case token profiles in
   `harness/cost_estimator.py` predate the `modelUsage` fix and reflect
   main-session-only tokens, underestimating subagent-dispatching cases (§ 7).
4. **Subagents leak artifacts outside the sandbox.** Despite fixture copying,
   benchmark subagents have contaminated original fixtures (appended execution
   logs under `datasets/test_fixtures/`), created rogue `research/` project
   folders, and made rogue git commits (see limitation 1). Manual cleanup has
   been required; see § 12 for the planned pre-run fixture restore.
5. **OpenRouter token counts are approximations.** The Anthropic-compatible
   endpoint reports counts from Anthropic's tokenizer, not each model's native
   tokenizer, so computed OpenRouter costs are approximate.

## 12. Future Work

- **Pre-run fixture cleanup/restore in `run_dispatch_compliance.py`:** reset
  debugger and code-reviewer fixtures from pristine copies before each launch.
  Two contaminated fixtures had to be restored by hand on 2026-06-09; this
  should be automatic.
- **Scorer improvements:**
  - Add clarifying-question patterns to the confirmation-gate regex (known
    false negative: Sonnet on mc-09)
  - Further soften `prompt_has_context_section` — the scorer already accepts
    seven heading variants, yet this remains the #1 failure across all models;
    consider detecting contextual content under any heading rather than a
    fixed list
- **Complete rep counts:** run Fable 5 to 3 reps on all phases and the
  remaining Anthropic models to 3 reps on Phase 3 (sequential, one model at a
  time)
- **Recalibrate cost estimation profiles** from post-`modelUsage`-fix runs
- **PreToolUse git-blocking hook** for benchmark runs, replacing the
  ineffective `--disallowed-tools` patterns
