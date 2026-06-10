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
| 1 — `mode_classification` | `datasets/mode_classification/cases.jsonl` | 15 (mc-01..mc-15) | Cold start (no checkpoint; `CHECKPOINT_LINES = 0`) | Orchestrator skill loaded, mode classification, no premature execution (hard); confirmation gate present (soft) |
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
complexity. Each case's required loads/reads are grounded in verbatim routing
text quoted from the skills themselves; the full design spec with per-case
ground-truth quotes is `PHASE4_SKILL_ROUTING_PLAN.md`.

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
| `scripts/` | Phase runners, `generate_goldens.py`, `generate_results_viewer.py`, `rescore_skill_routing.py`, `rescore_criteria_overhaul.py`, `refresh_golden_checkpoint.py`, utilities |
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
| `--models a,b` | all | Comma-separated model keys (lowercased names from models.yaml, spaces → hyphens, dots removed: `fable-5`, `sonnet-46`, `deepseek-v4-flash`) |
| `--provider X` | all | `anthropic`, `openrouter`, or `all` |
| `--test-id a,b` | all | Specific case IDs (e.g., `mc-01,mc-05`) |
| `--sequential` | off | Run one at a time instead of parallel |
| `--delay S` | 2 | Seconds between parallel launches (ThreadPoolExecutor stagger) |
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
| `skill_routing/ad_hoc_initialized.jsonl` | 47 | All 15 Phase 4 cases — content-refreshed copy of the Phase 3 golden (see Regeneration below) reflecting the 2026-06-10 routing-norm fix |
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
are hard vs. soft for that case; the human-edited case lists (and `expected`
fields) are the authority, and scorers derive the tiers they stamp on emitted
criteria from them (`tier1` = structural must-pass, e.g., `agent_dispatched`;
`tier2` = protocol detail, e.g., `prompt_has_base_dir`; `info` = diagnostic
only). Phase 1 criteria carry no stamped tier at all — the viewer classifies
them by membership in the case's `hard_requirements` list (in
`hard_requirements` → hard, otherwise soft).

**Phase 1 criteria** (scored inline by `scripts/run_mode_classification.py`;
the separate `scorers/deterministic/mode_classification.py` module was dead
code — never invoked by the runner — and was deleted 2026-06-10, with its
keyword/pattern tables relocated into the runner):
`orchestrator_skill_loaded`, `mode_correct`, `no_premature_execution` (hard in
all cases) and `confirmation_gate_present` (soft — gate phrasing varies enough
across models that it is a protocol-detail signal, not a structural one). A
former `reasoning_present` criterion existed only in the dead scorer module
and was never scored by the live runner; it has been removed from the case
lists.

**Phase 2 criteria** (from `scorers/deterministic/checkpoint_adherence.py`):
dynamically named `read_{doc}` criteria from `expected.documents_read` (tier1)
and `skill_{name}` criteria from `expected.skills_loaded` (tier1) or
`expected.skills_loaded_soft` (tier2 — same criterion names, softer tier; a
skill appears in one list or the other, never both). pc-07
(framework_development) uses the soft list for both authoring skills
(`skill-authoring`, `agent-authoring` — the mode doc directs loading both at
mode start, but deferring a load is a protocol detail, not a structural
failure); pc-04 (ad_hoc_collaboration) deliberately keeps `data-scientist`
hard.

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

**Phase 3b criteria pruning (2026-06-10).** Four structural criteria were
REMOVED from `scorers/deterministic/subagent_behavior.py` because they passed
in essentially every run with a transcript, noising Perfect and soft rates
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
were regenerated per set.

**Phase 4 skill-routing criteria** (from `scorers/deterministic/skill_routing.py`):
`required_skills_loaded` and `required_refs_read` (tier1, hard in all cases);
`required_skills_engaged`, `expected_refs_read`, `routing_order`, and
`no_forbidden_skills` (tier2, soft). `required_skills_engaged` (added
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

**Vacuous tier-2 passes (Phase 4 caveat):** `no_forbidden_skills` passes
trivially when a model makes no Skill calls at all. In the 2026-06-10 dry run,
models that ignored routing entirely (answering from parametric memory) still
passed it 75/75 — interpret Phase 4 soft rates jointly with the tier-1
load/read criteria, never in isolation. (A former criterion,
`no_spurious_skill_reload`, was removed for exactly this vacuousness — see
`PHASE4_SKILL_ROUTING_PLAN.md` § 9.) `required_skills_engaged`, by contrast,
is not vacuously passable: a zero-tool run must still name the required skill
in user-visible text, and observed per-model rates span 3/15 to 14/15.

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
profiles (average input/output/cached per case) that drive the pre-launch
estimate and confirmation prompt. **The Phase 1–3 profiles are stale:** they
were collected 2026-06-08 (Haiku 4.5, DeepSeek V4 Flash, Gemini 3.1 Flash
Lite) before the `modelUsage` fix and reflect main-session-only tokens, so
they underestimate costs for subagent-dispatching cases (all of Phase 3).
Treat those pre-run estimates as lower bounds until recalibrated (§ 12). The
Phase 4 profile is post-fix (recalibrated 2026-06-10 from the dry-run batch)
but likely underestimates stronger models: the calibration models mostly
answered without tool use, while full multi-reference routing runs heavier.

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
OpenRouter at 3. Note: this snapshot predates the 2026-06-10 criteria rescore
(`rescore_criteria_overhaul.py`), which retroactively changed pc-07 rates in
the archived result sets.

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
  already specified; complements the planned PreToolUse git-blocking hook.
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
