# Benchmark System Session Restart

**Date:** 2026-06-08
**Mode:** Framework Development
**Workspace:** /daaf/benchmarks
**Reference Plan:** /daaf/research/2026-05-01_Benchmark_Testing/Benchmark_System_Reference.md

---

## What Was Accomplished This Session

### Phase 3: Dispatch Compliance (cross-model run complete, subagent scoring added)

**What it tests:** When a user requests a specific task in Ad Hoc Collaboration mode, does the orchestrator (1) dispatch the correct subagent type via the Agent tool, and (2) construct a proper dispatch prompt with BASE_DIR, mode markers, and task-relevant content?

**Cross-model benchmark run (run 20260608_115024, 36 runs, $4.66):**

| Model | Dispatch Rate | All-Criteria | Avg Cost |
|-------|--------------|-------------|----------|
| Opus 4.6 | 10/12 (83%) | 10/12 (83%) | $0.135 |
| Sonnet 4.6 | 9/12 (75%) | 9/12 (75%) | $0.093 |
| Haiku 4.5 | 9/12 (75%) | 8/12 (67%) | $0.160 |

Failure patterns by agent type:
- **source-researcher**: 6/6 perfect — all models dispatch correctly
- **search-agent**: 6/6 dispatch (Haiku misses mode marker on dc-05 only)
- **debugger**: 5/6 — Opus fails dc-08 (timeout/sunk-cost pattern)
- **code-reviewer**: 3/6 — dc-10 hardest case (only Haiku passes)
- **research-executor**: 4/6 — Haiku handles directly instead of dispatching
- **data-ingest**: 4/6 — Haiku (dc-11) and Sonnet (dc-12) handle directly

**Root cause analysis: `dontAsk` permission mode was sabotaging results.**
All orchestrator-level Bash calls (mkdir, etc.) were auto-denied in `dontAsk` mode regardless of the settings.json allow list. Models that tried workspace setup before dispatching burned 30-60s on denied operations, then hit the 180s timeout. Transcript analysis confirmed Opus dc-08's thinking explicitly said "Let me set up workspace first" → 7 denied mkdir calls → recovery → Read file → timeout before dispatch.

**Permission fix applied:** Changed default from `dontAsk` to `bypassPermissions` in `harness/models.py`. Safety hooks (`bash-safety.sh`) still block dangerous commands.

**Haiku validation run (run 20260608_122641, 12 runs, $2.44):**
With `bypassPermissions`: Haiku went from 8/12 → **11/12** (91.7%). Only dc-02 (research-executor) remains as a genuine failure. The permission fix resolved 2 of 3 Haiku failures.

### Subagent Behavior Scoring (new capability)

Built and integrated a subagent behavior scorer that examines what dispatched subagents actually DO by parsing their separate transcript files.

**Scorer:** `scorers/deterministic/subagent_behavior.py`
- Finds subagent transcripts at `_sandbox/transcripts/{session_id}/subagents/`
- Extracts all tool calls from subagent JSONL transcripts
- Applies agent-type-specific behavioral criteria (6 agent types defined)
- Returns CriterionResult objects like the dispatch compliance scorer

**Per-agent-type behavioral criteria:**

| Agent Type | Tier 1 Checks | Tier 2 Checks |
|-----------|---------------|---------------|
| research-executor | active, writes .py script | uses run_with_capture |
| source-researcher | active, loads data source skill | min 3 tool calls |
| search-agent | active, uses Grep/Glob/Read/WebSearch | min 3 tool calls |
| debugger | active, reads problem script | min 2 tool calls |
| code-reviewer | active, reads target script | min 2 tool calls |
| data-ingest | active, references data file | min 2 tool calls |

**False negative fix:** Initial `reads_file` check only looked at Read tool calls. Data-ingest subagent accessed CSV via Bash (e.g., `wc -l books.csv`), not Read. Added `references_file` check that searches across Read file_path, Write file_path, Bash command, and Edit file_path.

**Rescoring results (28 dispatched runs from 20260608_115024):** 28/28 pass all subagent behavior criteria after the false negative fix. Every dispatched subagent correctly loads skills, reads target files, and follows its execution protocol.

**Standalone rescoring script:** `scripts/rescore_subagent_behavior.py` can rescore existing results post-hoc without re-running the benchmark.

**Integration into runner:** `run_dispatch_compliance.py` now:
- Imports and calls `score_subagent_behavior()` after dispatch scoring
- Prints subagent criteria inline with dispatch results
- Includes `subagent_criteria` in per-run result.json
- Copies subagent transcripts to results directory
- Shows subagent behavior summary table in console output
- Includes `subagent_behavior` section in summary.json

### Bug Fix: NameError in score_run

The initial integration had `expected.get(...)` instead of `test_case.expected.get(...)` in `score_run()`. This caused all 72 runs in the first `bypassPermissions` run to fail with `NameError`. Fixed immediately.

---

## Key Architecture Decisions (Cumulative)

### Prior session decisions (still valid)
1. Transcript-based scoring (not audit.jsonl)
2. Cold starts for mode classification, golden checkpoints for post-confirmation
3. Golden checkpoint design principles (real transcripts, domain-ambiguous prompts)
4. Timeout-resilient scoring (preserve session_id on timeout)
5. Turn limit as cost control
6. `disableAllHooks` for direct agent testing
7. `skills:` frontmatter auto-loads in real dispatch but NOT in `claude -p --agent`
8. Ad Hoc mode as dispatch test vehicle
9. Explicit dispatch prompts (testing dispatch quality, not trigger detection)

### New decisions this session

#### 10. `bypassPermissions` + `--disallowed-tools` for benchmark runs
Empirical testing revealed Claude Code's permission modes:
- `dontAsk`: blanket deny ALL Bash/Write/Edit — completely ignores settings.json allow list
- `default`: respects allow list but has additional directory sandbox restrictions that block mkdir even within the project directory
- `bypassPermissions`: only mode where DAAF subagents can fully function

Solution: `bypassPermissions` for full DAAF workflow functionality, combined with `--disallowed-tools "Bash(git commit *)" "Bash(git add *)" "Bash(git push *)"` to prevent subagents from committing to the repo. The disallowed-tools flag was empirically confirmed to work WITH bypassPermissions. Implemented in `harness/models.py` (RunConfig.disallowed_tools default) and `harness/executor.py` (passed to CLI).

#### 11. Subagent behavior scored from separate transcript files
Subagent tool calls are NOT in the parent transcript — only the Agent tool_use (prompt) and tool_result (final response) appear in the parent. The subagent's actual tool calls live in separate JSONL files at `~/.claude/projects/-daaf/{session_id}/subagents/agent-{id}.jsonl`. The scorer uses these files, not the parent transcript. The `.meta.json` files alongside them contain `agentType` and `description`.

#### 12. Fixture isolation via sandbox copies
Test fixtures (debugger scripts, code-reviewer scripts, data files) are copied into `{sandbox_dir}/fixtures/` before each run, and the test prompt is rewritten with the sandbox path. This prevents subagents from mutating the original fixtures (e.g., `run_with_capture.sh` appending output to the script file). Filenames stay the same so `expected.prompt_contains` scoring works unchanged. Implemented in `run_dispatch_compliance.py` as `prepare_fixtures()`.

#### 13. `.gitignore` for benchmark artifacts
Added `benchmarks/.gitignore` covering `_sandbox/`, `results/`, `research/`, and subagent-created files in `datasets/test_fixtures/`. Also added `research/*_AdHoc_*/` to root `.gitignore` for benchmark-created research directories that leak out of the sandbox.

#### 14. `references_file` check type for cross-tool file access
Agents can access data files through multiple tools — Read for direct reading, Bash for `wc -l`, `head`, or script execution. The `references_file` check searches across Read file_path, Write file_path, Edit file_path, and Bash command fields. More robust than `reads_file` which only checks Read calls.

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

### New findings this session

#### Permission system inflates failure rates
With `dontAsk` mode, 0/14 orchestrator Bash calls succeeded across all sessions. Models that tried workspace setup (Opus: 7-8 mkdir calls per run) burned 30-60s on denied operations. The `bypassPermissions` fix changed Haiku from 8/12 → 11/12. The prior session's `dontAsk` results likely understated all models' true dispatch capability.

#### Claude Code permission modes are coarser than expected
`dontAsk` is a blanket deny — it does NOT consult the settings.json allow list. `default` mode consults the allow list but has an additional directory sandbox that blocks operations even within the project directory. Only `bypassPermissions` allows full DAAF workflow functionality. The `--disallowed-tools` CLI flag DOES work with `bypassPermissions`, providing targeted deny capability. This was empirically confirmed with controlled tests.

#### The "read before dispatch" pattern is universal and rational
All four timeout-FAIL cases (dc-08 Opus, dc-09 Sonnet, dc-10 Sonnet, dc-10 Opus) showed the same thinking pattern: "Let me first read the script to understand what it does, so I can provide proper context in the agent prompt." This is smart behavior — a dispatch prompt WITH file context is genuinely higher quality. The 180s timeout penalizes it, not because the behavior is wrong, but because checkpoint resume + Read large file + generate Agent call exceeds the budget.

#### Subagent behavior is uniformly correct once dispatched
28/28 dispatched subagents passed all behavioral criteria. Every agent type correctly loaded skills, read target files, and followed execution protocols. Dispatch quality (correct type + good prompt) correlates perfectly with downstream subagent behavior — there are zero cases of "correct dispatch, broken subagent."

#### Model-specific dispatch strategies visible in tool call distributions
- **research-executor subagents**: Bash-heavy (10-15 calls for script execution)
- **source-researcher subagents**: Read-heavy (4-7 Read calls, 1-2 Skill calls)
- **search-agent subagents**: Glob+Read heavy (Opus: 22 tool calls; Haiku: 7 with more Skill calls)
- **debugger subagents**: Bash+Write (diagnostic scripts, 7-19 Bash calls)
- **code-reviewer subagents**: Bash+Read (QA scripts, 6-11 tool calls)
- **data-ingest subagents**: Bash-heavy (profiling scripts, 9-17 Bash calls)

---

## Complete File Inventory (Updated)

### Harness (core execution engine)
- `harness/models.py` — Dataclasses (updated: permission_mode default → `bypassPermissions`)
- `harness/executor.py` — Single test execution
- `harness/collector.py` — Transcript reading (mostly legacy)
- `harness/checkpoint_manager.py` — Golden checkpoint cloning
- `harness/runner.py` — Original runner (superseded)

### Scorers
- `scorers/deterministic/mode_classification.py` — Phase 1 scorer (unchanged)
- `scorers/deterministic/checkpoint_adherence.py` — Phase 2 scorer (unchanged)
- `scorers/deterministic/dispatch_compliance.py` — Phase 3 scorer (6 dispatch criteria)
- `scorers/deterministic/subagent_behavior.py` — **NEW** Subagent behavior scorer (6 agent types)
- `scorers/llm_judge/__init__.py` — Empty placeholder

### Phase-specific runners
- `scripts/run_mode_classification.py` — Phase 1 (unchanged)
- `scripts/run_post_confirmation.py` — Phase 2 (unchanged)
- `scripts/run_dispatch_compliance.py` — Phase 3 (updated: subagent scoring, fixture isolation)
- `scripts/rescore_subagent_behavior.py` — **NEW** Post-hoc subagent rescoring

### Datasets
- `datasets/mode_classification/cases.jsonl` — 15 Phase 1 test cases (unchanged)
- `datasets/post_confirmation/cases.jsonl` — 9 Phase 2 test cases (unchanged)
- `datasets/dispatch_compliance/cases.jsonl` — 12 Phase 3 test cases (unchanged)

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
- `golden/dispatch_compliance/ad_hoc_initialized.jsonl` — Phase 3 (47 lines, Opus 4.6)

### Results
- `results/20260607_213620/` — Phase 1 full run (135 runs, $10.88)
- `results/20260607_223957/` — Phase 2 full run (81 runs, $16.47)
- `results/20260608_015645/` — Phase 3 smoke test: Haiku on dc-01 (1 run, $0.09)
- `results/20260608_020526/` — Phase 3 smoke test: Opus on 6 cases (6 runs, $5.11)
- `results/20260608_022212/` — Phase 3 validation: Opus 6/6 with explicit prompts (6 runs)
- `results/20260608_115024/` — Phase 3 cross-model: dontAsk mode (36 runs, $4.66) — includes rescored subagent behavior
- `results/20260608_122224/` — Phase 3 broken run: NameError bug (72 runs, all failed)
- `results/20260608_122641/` — Phase 3 Haiku validation: bypassPermissions (12 runs, $2.44, 11/12)

---

## Next Session: Planned Work

### 1. Tool Call Failure Diagnostics (IMMEDIATE)
Audit all runners and scorers to ensure tool call failures (permission denials, hook blocks, execution errors) are properly captured, logged, and surfaced in all outputs. Currently, `dontAsk` denials return `is_error: True` with empty content — these silent failures made debugging the permission issue harder than necessary. Specific items:
- Ensure `result.json` captures tool call error messages (not just `is_error` boolean)
- Add a `tool_failures` section to per-run output showing denied/failed tool calls with their error text
- Surface tool failure counts in the console summary and `summary.json`
- Verify the transcript parsing extracts error content from `tool_result` blocks (the `content` field may be a list of text blocks, not a plain string)
- Check that timed-out runs still capture whatever tool calls occurred before timeout (Bug 1: turns=0 and cost=$0.00 for timeouts)

### 2. Propagate Infrastructure Fixes to Phase 1 and Phase 2 Runners (IMMEDIATE)
This session's changes to the executor and harness (`bypassPermissions`, `--disallowed-tools`, fixture isolation) were developed against the Phase 3 dispatch compliance runner. Review and propagate appropriate changes to:
- `scripts/run_mode_classification.py` (Phase 1): Does it need `bypassPermissions`? It tests cold-start classification — models may not call Bash, but the permission mode should be consistent. Check if `disallowed_tools` applies.
- `scripts/run_post_confirmation.py` (Phase 2): Tests post-confirmation protocol steps. Models load skills and read files but may also call Bash. Apply same permission and git-blocking config.
- `scripts/run_checkpoint_comparison.py` (legacy): The older runner with OpenRouter model definitions. Decide whether to update it with the new infrastructure or deprecate it in favor of the phase-specific runners.
- `harness/executor.py`: The `disallowed_tools` and `permission_mode` defaults in `RunConfig` now apply to ALL runners since they share the harness. Verify this is appropriate for Phase 1/2 (it should be, but confirm no regressions).
- Fixture isolation: Only needed for Phase 3 (the only phase with test fixtures). Phase 1/2 don't reference external files in prompts.

### 3. Full Cross-Model Run with All Fixes
Haiku validated at 11/12 with `bypassPermissions`. The runner now includes fixture isolation, workspace containment, git-commit blocking via `--disallowed-tools`, and subagent behavior scoring. Run all 3 models:
```bash
python3 benchmarks/scripts/run_dispatch_compliance.py --reps 3 --timeout 180
```
Expected: 108 runs (12 cases x 3 models x 3 reps). Compare against the dontAsk baseline (run 20260608_115024). Verify: (1) fixture originals untouched after run, (2) no new git commits, (3) subagent behavior scores populated, (4) workspace output lands in sandbox.

### 4. Exam-Style Knowledge Tests (from prior plan item 3)
Create a separate test category that asks models framework knowledge questions without requiring execution:
- "What subagent type should be dispatched for Stage 5 data fetch?"
- "What are the required sections in a research-executor dispatch prompt?"
- "According to the data-scientist routing tree, what library handles panel random effects?"
Deterministic scoring against known-correct answers. Very cheap (~$0.02/run), broad coverage.

### 5. Bug Fix: Timed-Out Runs Report turns=0 and cost=$0.00 (from prior Bug 1)
The timeout exception path in executor.py can't parse stdout. Fix: after timeout, read the live transcript to extract turn count, or parse the partial stdout. Low priority since scoring works correctly despite the reporting gap. Consider folding this into item 1 (tool call failure diagnostics).

### 6. OpenRouter Integration + Model Matrix
The old `scripts/run_checkpoint_comparison.py` already has 8 OpenRouter models configured (GLM 5.1, Kimi K2.6, Qwen 3.6, Gemma 4, DeepSeek V4, Gemini 3.1 Pro) plus 14 Anthropic variants with effort levels. OpenRouter integration is via environment variables: `ANTHROPIC_BASE_URL=https://openrouter.ai/api`, `ANTHROPIC_AUTH_TOKEN=key`, `ANTHROPIC_API_KEY=` (blank). These go in `ModelConfig.env_overrides` — the executor already passes `env.update(model.env_overrides)`. Consolidate the old script's model list into `config/models.yaml`.

### 7. HTML Results Viewer (from prior plan)
Browser-based viewer for `results/{timestamp}/summary.json` with drill-down to individual runs.

---

## Restart Prompt

To resume this work, start a new session and paste:

> Launch framework development mode. We're continuing work on the DAAF benchmark system at `/daaf/benchmarks`. Read `/daaf/benchmarks/SESSION_RESTART.md` for the complete state of what was built, architecture decisions, and next steps. The priorities for this session are detailed in the "Next Session: Planned Work" section. Start by reading the restart file and assessing what to tackle first.
