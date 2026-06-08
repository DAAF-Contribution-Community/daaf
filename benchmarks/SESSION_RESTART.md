# Benchmark System Session Restart

**Date:** 2026-06-08
**Mode:** Framework Development
**Workspace:** /daaf/benchmarks
**Reference Plan:** /daaf/research/2026-05-01_Benchmark_Testing/Benchmark_System_Reference.md

---

## What Was Accomplished This Session

### Git Cleanup
Removed 15 agent-generated test artifacts (4,162 lines) that were committed during benchmark runs before `--disallowed-tools` was added. Committed all legitimate prior-session work (subagent behavior scorer, permission fixes, fixture isolation, SESSION_RESTART.md).

### Tier 1: Tool Call Failure Diagnostics + Timeout Recovery + Infrastructure Propagation

**Executor improvements (`harness/executor.py`):**
- Refactored JSON parsing into composable helpers (`_parse_json_output`, `_extract_tool_failures`, `_find_recent_session_id`)
- Tool failures extracted from JSON output by cross-referencing `tool_use` IDs with failed `tool_result` blocks — captures tool name + error content text (handles both string and list content formats)
- Timeout recovery: parses partial stdout from `TimeoutExpired` exception; searches filesystem for session_id on cold-start timeouts
- New `tool_failures` field on `RunResult` (in `models.py`)

**Transcript parser improvements (`checkpoint_adherence.py`):**
- `extract_new_tool_calls()` now captures `error_content` text from `tool_result` blocks, not just the `is_error` boolean
- This feeds into scorer detail messages for better debugging

**Scoring accuracy fixes:**
- `dispatch_compliance.py`: All 6 criteria now filter Agent calls by `succeeded=True` — failed dispatches no longer count as adherence
- `checkpoint_adherence.py`: `subagent_dispatched` scoring also filters by `succeeded=True`
- Retry-resilient: fail-then-succeed pattern correctly passes (tested with mock transcripts)
- Diagnostic detail distinguishes "never attempted" from "attempted but failed"

**Runner propagation (all 3 runners):**
- `tool_failures` flows through: per-run console output (first 5 with tool name + truncated content), `result.json`, and `summary.json` (total count, affected runs, breakdown by tool name)
- Phase 1 (`run_mode_classification.py`): Now attempts scoring on timeout if session_id recovered (matching Phase 2/3 behavior)
- Phase 2 (`run_post_confirmation.py`): Already consistent — inherited `bypassPermissions` from `RunConfig` defaults
- Legacy `run_checkpoint_comparison.py`: Left as-is (superseded by phase-specific runners)

### Dispatch Prompt Structural Criteria (4 new)

Added 4 new tier2 scoring criteria to `dispatch_compliance.py` based on the Standard Agent Prompt Structure defined in `ad-hoc-collaboration-mode.md`:
- `prompt_has_project_dir`: checks for "PROJECT_DIR"
- `prompt_has_task_section`: checks for "## Task"
- `prompt_has_context_section`: checks for "## Context"
- `prompt_has_instructions`: checks for "## Instructions"

Also removed redundant `BASE_DIR` from `prompt_contains` in all 12 test cases (already checked independently by `prompt_has_base_dir`). Added exact skill names to `prompt_contains_required` for source-researcher cases (dc-03: `education-data-source-ipeds`, dc-04: `education-data-source-ccd`).

Updated `soft_requirements` in all 12 test cases. Scorer now evaluates **10 criteria** per dispatch (up from 6).

**Haiku validation (run 20260608_152111, 12 runs):**

| Criterion | Haiku Pass Rate | Notes |
|-----------|:-:|---|
| agent_dispatched | 11/12 (92%) | Baseline dispatch |
| correct_subagent_type | 11/12 (92%) | |
| prompt_has_base_dir | 11/12 (92%) | |
| prompt_has_mode_marker | 11/12 (92%) | |
| prompt_has_project_dir | 7/12 (58%) | New — significant gap |
| prompt_has_task_section | 11/12 (92%) | New |
| prompt_has_context_section | 7/12 (58%) | New — weak |
| prompt_has_instructions | 4/12 (33%) | New — weakest |
| prompt_contains_required | 10/12 (83%) | |
| prompt_contains_any | 11/12 (92%) | |
| **All 10 criteria** | **2/12 (17%)** | Down from prior ~67% |

### Prescriptive Subagent Behavior Specs

Replaced generic "min N tool calls" tier2 checks with specific behavioral assertions derived from analysis of 64 subagent transcripts across all agent types.

| Agent Type | Old Tier 2 | New Tier 2 |
|-----------|-----------|-----------|
| research-executor | uses run_with_capture | writes to `scripts/adhoc/`; uses run_with_capture |
| source-researcher | min 3 tool calls | reads >= 2 skill reference files; no code execution |
| search-agent | min 3 tool calls | reads >= 3 skill files; no code execution |
| debugger | min 2 tool calls | writes diagnostic to `debug/` dir; uses run_with_capture |
| code-reviewer | min 2 tool calls | writes CR script to `scripts/cr/`; uses run_with_capture |
| data-ingest | min 2 tool calls | writes profiling script (.py); uses run_with_capture |

New check functions: `writes_to_dir`, `reads_min_matching`, `no_code_execution`. Total: 24 behavioral specs across 6 agent types (up from 18).

### Fixture Infrastructure Fix

Copied `run_with_capture.sh` into sandbox workspace during fixture preparation. Subagents treat the sandbox as BASE_DIR and look for `{workspace}/scripts/run_with_capture.sh` — without a copy, they either fail or fall back to direct python execution (blocked by enforce-file-first hook). This was an artificial failure inflating error rates.

---

## Key Architecture Decisions (Cumulative)

### Prior session decisions (1-14, still valid)
1. Transcript-based scoring (not audit.jsonl)
2. Cold starts for mode classification, golden checkpoints for post-confirmation
3. Golden checkpoint design principles
4. Timeout-resilient scoring (preserve session_id on timeout)
5. Turn limit as cost control
6. `disableAllHooks` for direct agent testing
7. `skills:` frontmatter auto-loads in real dispatch but NOT in `claude -p --agent`
8. Ad Hoc mode as dispatch test vehicle
9. Explicit dispatch prompts (testing dispatch quality, not trigger detection)
10. `bypassPermissions` + `--disallowed-tools` for benchmark runs
11. Subagent behavior scored from separate transcript files
12. Fixture isolation via sandbox copies
13. `.gitignore` for benchmark artifacts
14. `references_file` check type for cross-tool file access

### New decisions this session

#### 15. Tool failure extraction from JSON output
Tool failures are extracted by building a `tool_use_id → tool_name` map from assistant messages, then scanning user messages for `tool_result` blocks with `is_error=True`. The `content` field is handled polymorphically (string or list of text blocks). Failures stored on `RunResult.tool_failures` and propagated through all output layers.

#### 16. Timeout session_id recovery via filesystem
For cold-start runs (no checkpoint session_id), the executor searches `~/.claude/projects/-daaf/` for `.jsonl` files modified after the run's start time. Returns the most recent match's stem as session_id. This allows scoring of timed-out cold-start runs.

#### 17. "Credit requires success" scoring principle
Positive criteria (did you do X?) filter by `succeeded=True`. Negative criteria (did you avoid X?) catch all attempts regardless of outcome. Applied consistently across `dispatch_compliance.py` and `checkpoint_adherence.py`.

#### 18. Structural prompt criteria from framework templates
The ad-hoc-collaboration-mode.md Standard Agent Prompt Structure requires `PROJECT_DIR`, `## Task`, `## Context`, and `## Instructions` sections. These are now scored as tier2 criteria, providing prompt quality differentiation between models.

#### 19. Prescriptive subagent behavior from transcript analysis
Behavioral specs derived empirically from 64 subagent transcripts. Each agent type has specific artifact and protocol checks instead of generic tool call counts. Read-only agents (source-researcher, search-agent) have `no_code_execution` assertions.

#### 20. run_with_capture.sh copied into sandbox workspace
Subagents treat the workspace as BASE_DIR and construct `{workspace}/scripts/run_with_capture.sh`. Copying the real script into the sandbox eliminates artificial path-not-found failures.

---

## Key Behavioral Findings (Cumulative)

### Prior session findings (still valid)
- Haiku's "shortcutting" pattern
- Skill tool vs. Read tool preference
- Relevance vs. compliance tension
- Adversarial test cases as differentiator
- Opus handles simple tasks directly instead of dispatching (with implicit prompts)
- The "sunk cost" dispatch skip
- Context-first vs task-first dispatch templates
- Data-ingest agent/mode conflation
- CWD affects project discovery
- Permission system inflates failure rates
- Claude Code permission modes are coarser than expected
- The "read before dispatch" pattern is universal and rational
- Subagent behavior is uniformly correct once dispatched
- Model-specific dispatch strategies visible in tool call distributions

### New findings this session

#### Structural prompt sections are the key differentiator
With 10 dispatch criteria, Haiku's all-criteria rate dropped from ~67% (6 criteria) to 17% (10 criteria). The weakest areas are `## Instructions` (33%), `## Context` (58%), and `PROJECT_DIR` (58%). BASE_DIR, mode marker, and dispatch type remain strong (92%). This suggests models know WHAT to dispatch but don't consistently structure HOW.

#### Tool failures are predominantly infrastructure artifacts
39 tool failures in a 12-run Haiku batch — mostly `run_with_capture.sh` not found (fixed) and `enforce-file-first` hook blocks (consequence of the path issue). After the sandbox fix, genuine tool failures should be much rarer.

#### Debugger behavioral deviation: fix vs. diagnostic
Haiku's debugger (dc-07) wrote `join_type_mismatch_fixed.py` to `scripts/adhoc/` instead of a diagnostic script to `scripts/debug/`. It produced a fix rather than a diagnostic — a real behavioral deviation that the prescriptive `writes_to_dir("debug/|diag")` check correctly catches.

#### Code-reviewer sometimes executes fixtures
Haiku's code-reviewer (dc-10) attempted to execute `enrollment_trends.py` through `run_with_capture.sh` — a pre-executed fixture it should only review. This is a genuine behavioral error: the code-reviewer should read and analyze, not re-execute.

---

## Complete File Inventory (Updated)

### Harness (core execution engine)
- `harness/models.py` — Dataclasses (updated: `tool_failures` field on RunResult)
- `harness/executor.py` — Single test execution (updated: refactored JSON parsing, tool failure extraction, timeout recovery)
- `harness/collector.py` — Transcript reading (mostly legacy)
- `harness/checkpoint_manager.py` — Golden checkpoint cloning

### Scorers
- `scorers/deterministic/mode_classification.py` — Phase 1 scorer (unchanged)
- `scorers/deterministic/checkpoint_adherence.py` — Phase 2 scorer (updated: error_content capture, succeeded filtering on subagent_dispatched)
- `scorers/deterministic/dispatch_compliance.py` — Phase 3 scorer (updated: 10 criteria, succeeded filtering)
- `scorers/deterministic/subagent_behavior.py` — Subagent behavior scorer (updated: 24 prescriptive specs, 3 new check functions)
- `scorers/llm_judge/__init__.py` — Empty placeholder

### Phase-specific runners
- `scripts/run_mode_classification.py` — Phase 1 (updated: tool_failures, timeout scoring alignment)
- `scripts/run_post_confirmation.py` — Phase 2 (updated: tool_failures)
- `scripts/run_dispatch_compliance.py` — Phase 3 (updated: tool_failures, run_with_capture sandbox copy, structural criteria in soft_requirements)
- `scripts/rescore_subagent_behavior.py` — Post-hoc subagent rescoring

### Datasets
- `datasets/mode_classification/cases.jsonl` — 15 Phase 1 test cases (unchanged)
- `datasets/post_confirmation/cases.jsonl` — 9 Phase 2 test cases (unchanged)
- `datasets/dispatch_compliance/cases.jsonl` — 12 Phase 3 test cases (updated: 10 criteria, skill names, soft_requirements)

### Test fixtures (unchanged)
- `datasets/test_fixtures/debugger/join_type_mismatch.py`
- `datasets/test_fixtures/debugger/silent_data_loss.py`
- `datasets/test_fixtures/code_reviewer/frpl_poverty_rates.py`
- `datasets/test_fixtures/code_reviewer/enrollment_trends.py`
- `datasets/test_fixtures/data_ingest/books.csv`
- `datasets/test_fixtures/data_ingest/messy_students.csv`

### Golden checkpoints
- `golden/mode_classification/mc-{01..15}.jsonl` — Phase 1 (unchanged)
- `golden/post_confirmation/{mode}.jsonl` — Phase 2 (unchanged)
- `golden/dispatch_compliance/ad_hoc_initialized.jsonl` — Phase 3 (unchanged)

### Config
- `config/models.yaml` — Model matrix (3 Anthropic models)

### Results (gitignored, on disk)
- `results/20260608_115024/` — Phase 3 cross-model: dontAsk mode (36 runs, $4.66)
- `results/20260608_122641/` — Phase 3 Haiku: bypassPermissions (12 runs, $2.44, 11/12)
- `results/20260608_135349/` — Phase 3 Haiku: new structural criteria, 2 reps (24 runs, $4.71)
- `results/20260608_152111/` — Phase 3 Haiku: prescriptive subagent specs, 1 rep (12 runs, $3.10)

---

## Next Session: Planned Work

### 1. Validation Run: All Models with All Fixes
Run Opus, Sonnet, and Haiku with the complete updated scoring (10 dispatch criteria, 24 subagent behavior specs, tool failure capture, run_with_capture sandbox fix):
```bash
python3 benchmarks/scripts/run_dispatch_compliance.py --reps 3 --timeout 500
```
Expected: 108 runs (12 cases x 3 models x 3 reps). This is the first clean cross-model run with the full scoring suite. Compare structural prompt criteria across models — hypothesis: Opus > Sonnet > Haiku on `## Context`, `## Instructions`, `PROJECT_DIR`.

### 2. OpenRouter Integration + Model Matrix
The old `scripts/run_checkpoint_comparison.py` already has 8 OpenRouter models configured (GLM 5.1, Kimi K2.6, Qwen 3.6, Gemma 4, DeepSeek V4, Gemini 3.1 Pro). OpenRouter integration is via environment variables: `ANTHROPIC_BASE_URL=https://openrouter.ai/api`, `ANTHROPIC_AUTH_TOKEN=key`, `ANTHROPIC_API_KEY=` (blank). These go in `ModelConfig.env_overrides` — the executor already passes `env.update(model.env_overrides)`. Consolidate the old script's model list into `config/models.yaml` with an `openrouter` section. Requires `OPENROUTER_API_KEY` in environment.

### 3. Exam-Style Knowledge Tests (from prior plan)
Create a separate test category that asks models framework knowledge questions without requiring execution:
- "What subagent type should be dispatched for Stage 5 data fetch?"
- "What are the required sections in a research-executor dispatch prompt?"
- "According to the data-scientist routing tree, what library handles panel random effects?"
Deterministic scoring against known-correct answers. Very cheap (~$0.02/run), broad coverage.

### 4. HTML Results Viewer (from prior plan)
Browser-based viewer for `results/{timestamp}/summary.json` with drill-down to individual runs.

### 5. Rescore Prior Runs with Updated Criteria
The `rescore_subagent_behavior.py` script can rescore existing results post-hoc. Run it against prior results (20260608_115024 cross-model run) to see how the new prescriptive specs would have scored without re-running the benchmark. Need to verify subagent transcripts are available in those older result directories.

---

## Restart Prompt

To resume this work, start a new session and paste:

> Launch framework development mode. We're continuing work on the DAAF benchmark system at `/daaf/benchmarks`. Read `/daaf/benchmarks/SESSION_RESTART.md` for the complete state of what was built, architecture decisions, and next steps. The priorities for this session are detailed in the "Next Session: Planned Work" section. Start by reading the restart file and assessing what to tackle first. Come back to me when you've read and thought things through, but do not start any work
