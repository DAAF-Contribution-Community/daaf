# Benchmark System Session Restart

**Date:** 2026-06-09 (Session 3)
**Mode:** Framework Development
**Workspace:** /daaf/benchmarks
**Reference Plan:** /daaf/research/2026-05-01_Benchmark_Testing/Benchmark_System_Reference.md

---

## What Was Accomplished (Session 3)

### Phase 3 (dispatch_compliance) Completed — 17 models × 2-3 reps

Ran all 17 models (7 Anthropic + 10 OpenRouter) through Phase 3 dispatch compliance testing. Phase 3 tests whether models correctly dispatch subagents via the Agent tool with properly structured prompts (BASE_DIR, mode markers, task/context/instructions sections, required content).

**Anthropic models required sequential execution** due to persistent API rate limiting when running in parallel. Even with 10s delays, 34/36 runs hit HTTP 429 in the first attempt. Sequential execution (one run at a time) eliminated orchestrator-level rate limits but subagent-level rate limits persisted at ~20% of runs (inherent to the test — orchestrator and subagent compete for the same quota).

**Rate-limited run cleanup:** 12 runs across 4 Anthropic result sets were identified as TOTAL FAIL or DEGRADED due to rate limiting. Each was deleted from its original result set and re-run individually with 60s gaps. All 12 replacements dispatched correctly; 4 had genuine `prompt_has_context_section` failures (not rate-limit caused).

### Fable 5 Added and Benchmarked (All 3 Phases)

Added `claude-fable-5` to model matrix ($10/$50/$1.00 input/output/cached). Ran 2 reps across all 3 phases:

| Phase | Rep 1 | Rep 2 | Combined |
|-------|-------|-------|----------|
| Phase 1 (mode_classification) | 15/15 (100%) | 15/15 (100%) | **30/30 (100%)** |
| Phase 2 (post_confirmation) | 9/9 (100%) | 9/9 (100%) | **18/18 (100%)** |
| Phase 3 (dispatch_compliance) | 10/12 (83%) | 11/12 (92%) | **21/24 (88%)** |

Fable is the top-performing model across all phases. Only failures are `prompt_has_context_section` — contextual content is present but under different headings.

**Behavioral analysis** (2 search-agent reviews of transcripts): No test awareness detected. No gaming behavior. Dispatch prompts are substantively tailored, not templated. Subagents perform genuine error recovery. One limitation: Fable's thinking blocks are encrypted (empty string + cryptographic signature), making reasoning quality assessment structurally impossible.

### Phase 3 Results Summary (all_perfect across reps)

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

*Sonnet scores exclude 4 timed-out runs where the model never reached dispatch within 300s.

**Universal weak criterion:** `prompt_has_context_section` is the #1 failure across all models — models dispatch correctly but omit the `## Context` heading (content often present under other sections).

### Viewer Improvements

**Rep renumbering fix:** Runs from different result sets all had `rep=0`, causing the viewer's case-detail grid to show only one column. Added global rep renumbering in `generate_results_viewer.py` that assigns sequential rep numbers per `(phase, model, case_id)` tuple across all loaded result sets.

### Git Deny Pattern Investigation

**Problem:** Benchmark subagents were making git commits by evading `--disallowed-tools` patterns. The patterns `Bash(git commit *)` only match commands starting with `git commit` — models bypassed via `cd /dir && git commit`.

**Root cause:** Claude Code splits compound commands on shell operators (`&&`, `||`, `;`, `|`) and checks each subcommand independently. A deny rule blocking only one subcommand doesn't block the whole compound.

**Current state:** Added leading `*` wildcards to patterns in `harness/models.py` (e.g., `Bash(*git commit*)`), but testing confirmed these don't work — the glob matching is prefix-anchored only. The official recommendation is PreToolUse hooks for reliable blocking. Accepted as a known limitation for now.

**4 rogue commits** exist on `daaf_dev` above `d07b021` (created by benchmark subagents). User will handle cleanup.

### Ghost Result Set Cleanup

Deleted 3 stale result sets:
- `20260608_231509` — ghost (Opus 4.5 bad model ID)
- `20260608_232158` — ghost (Opus 4.5 old mc-07)
- `20260609_131854` — orphaned partial re-run

---

## Architecture Decisions (New This Session)

### 32. Sequential execution required for Anthropic Phase 3
Parallel execution of 36 Opus sessions (3 models × 12 cases) exceeds API rate limits even with 10s stagger. Sequential execution eliminates orchestrator-level rate limits. Subagent-level rate limits (~20% of runs) are inherent and non-preventable — they occur within a single run as orchestrator and subagent compete for quota.

### 33. Rate-limited run replacement protocol
Delete bad run from original result set, re-run individually with 60s gaps, verify replacement has zero rate_limit events in main transcript. Subagent-level rate limits in replacements are accepted if run passes all dispatch criteria.

### 34. Global rep renumbering in viewer generator
When `--reps 1` is used across multiple batches, all runs have `rep=0`. The viewer generator now renumbers reps globally by counting `(phase, model, case_id)` occurrences across all loaded result sets.

### 35. `--disallowed-tools` cannot block compound commands
Claude Code splits on `&&`/`;`/`|` and checks each subcommand. Leading `*` wildcards don't work. PreToolUse hooks are the recommended alternative. Accepted as known limitation — 4 rogue commits reached `daaf_dev`.

### 36. Fable 5 pricing: $10/$50/$1.00
Most expensive model in the matrix (2× Opus pricing). `cached_input: 1.00` uses the cache hit rate. Cost is dominated by cache creation tokens (130k-550k per orchestrator turn), not output verbosity.

### 37. Fable 5 thinking blocks are encrypted
Empty string + cryptographic signature. Test awareness and reasoning quality analysis are structurally impossible. All behavioral assessment must rely on observable output proxies.

---

## Current Model Matrix: 17 models (7 Anthropic + 10 OpenRouter)

**Anthropic:** Haiku 4.5, Sonnet 4.6, Opus 4.5, Opus 4.6, Opus 4.7, Opus 4.8, Fable 5
**OpenRouter:** GLM 5.1, Kimi K2.6, Qwen 3.6 27B, Gemma 4 31B, Gemma 4 26B, DeepSeek V4 Pro, DeepSeek V4 Flash, Gemini 3.1 Pro, Nemotron 3 Ultra, Gemini 3.1 Flash Lite

---

## Result Sets on Disk

### Phase 1 (mode_classification)
| Result Set | Models | Runs | Notes |
|-----------|--------|------|-------|
| `20260608_214251` | Haiku, Sonnet, Opus 4.6/4.7/4.8 | 210 | mc-07 deleted, replaced |
| `20260608_215330` | GLM, Kimi, Qwen, Gemma 31B/26B | 210 | mc-07 deleted, replaced |
| `20260608_220708` | DS Pro/Flash, Gemini Pro, Nemotron, Flash Lite | 210 | mc-07 deleted, replaced |
| `20260608_234751` | Haiku, Sonnet, Opus 4.5 mc-07 rerun | 6 | Opus 4.5 deleted (old ID) |
| `20260608_235104` | Opus 4.6/4.7/4.8 mc-07 rerun | 9 | Clean |
| `20260608_235520` | GLM, Kimi, Qwen, Gemma 31B/26B mc-07 rerun | 15 | Clean |
| `20260609_000011` | DS Pro/Flash, Gemini Pro, Nemotron, Flash Lite mc-07 | 15 | Clean |
| `20260609_001212` | Opus 4.5 full rerun | 45 | Clean |
| `20260609_202049` | Fable 5 rep 1 | 15 | Clean |
| `20260609_214917` | Fable 5 rep 2 | 15 | Clean |

### Phase 2 (post_confirmation)
| Result Set | Models | Runs | Notes |
|-----------|--------|------|-------|
| `20260608_221438` | Haiku, Sonnet, Opus 4.6/4.7/4.8 | 128 | Rate-limited runs deleted, replaced |
| `20260608_222445` | GLM, Kimi, Qwen, Gemma 31B/26B | 135 | Clean |
| `20260608_223408` | DS Pro/Flash, Gemini Pro, Nemotron, Flash Lite | 135 | Clean |
| `20260608_232257` | Opus 4.5 | 27 | Clean |
| `20260608_233457` | Opus 4.8 pc-09 rerun | 1 | Clean |
| `20260608_233906` | Opus 4.7+4.8 pc-06 rerun | 6 | Clean |
| `20260609_203258` | Fable 5 rep 1 | 9 | Clean |
| `20260609_215903` | Fable 5 rep 2 | 9 | Clean |

### Phase 3 (dispatch_compliance)
| Result Set | Models | Runs | Notes |
|-----------|--------|------|-------|
| `20260609_003629` | Wave C rep 1 (GLM, Kimi, Qwen, Gemma ×2) | 60 | Clean |
| `20260609_004353` | Wave D rep 1 (DS Pro/Flash, Gemini Pro, Nemotron, Flash Lite) | 60 | Clean |
| `20260609_005021` | Wave A rep 1 (Haiku, Sonnet, Opus 4.5) | 34 | 2 runs deleted (rate-limit), replaced |
| `20260609_005920` | Wave C rep 2 | 60 | Clean |
| `20260609_010631` | Wave D rep 2 | 60 | Clean |
| `20260609_011346` | Wave C rep 3 | 60 | Clean |
| `20260609_012055` | Wave D rep 3 | 60 | Clean |
| `20260609_134443` | Wave B rep 1 (Opus 4.6/4.7/4.8) sequential | 33 | 3 runs deleted (rate-limit), replaced |
| `20260609_160029` | Wave A rep 2 sequential | 33 | 3 runs deleted (rate-limit), replaced |
| `20260609_180411` | Wave B rep 2 sequential | 33 | 3 runs deleted (rate-limit), replaced |
| `20260609_182101` | Replacement: dc-08 Sonnet | 1 | Clean |
| `20260609_182702` | Replacement: dc-11 Sonnet | 1 | Clean |
| `20260609_183139` | Replacement: dc-02 Opus 4.8 | 1 | Clean |
| `20260609_183605` | Replacement: dc-08 Opus 4.6 | 1 | Clean |
| `20260609_184206` | Replacement: dc-11 Opus 4.6 | 1 | Clean |
| `20260609_184808` | Replacement: dc-11 Opus 4.8 | 1 | Clean |
| `20260609_185040` | Replacement: dc-06 Haiku | 1 | Clean |
| `20260609_185557` | Replacement: dc-11 Opus 4.5 | 1 | Clean |
| `20260609_190158` | Replacement: dc-11 Sonnet | 1 | Clean |
| `20260609_190608` | Replacement: dc-02 Opus 4.6 | 1 | Clean |
| `20260609_191205` | Replacement: dc-11 Opus 4.6 | 1 | Clean |
| `20260609_191806` | Replacement: dc-12 Opus 4.6 | 1 | Clean |
| `20260609_214335` | Fable 5 rep 1 | 12 | 3 subagent-level rl, all recovered |
| `20260609_224824` | Fable 5 rep 2 | 12 | 3 subagent-level rl, all recovered |

---

## Rep Counts by Model

| Model | Phase 1 | Phase 2 | Phase 3 | Provider |
|-------|---------|---------|---------|----------|
| Haiku 4.5 | 3 reps (45) | 3 reps (27) | 2 reps (24) | Anthropic |
| Sonnet 4.6 | 3 reps (45) | 3 reps (27) | 2 reps (~22)* | Anthropic |
| Opus 4.5 | 3 reps (45) | 3 reps (27) | 2 reps (24) | Anthropic |
| Opus 4.6 | 3 reps (45) | 3 reps (27) | 2 reps (24) | Anthropic |
| Opus 4.7 | 3 reps (45) | 3 reps (27) | 2 reps (24) | Anthropic |
| Opus 4.8 | 3 reps (45) | 3 reps (27) | 2 reps (24) | Anthropic |
| Fable 5 | 2 reps (30) | 2 reps (18) | 2 reps (24) | Anthropic |
| All OpenRouter | 3 reps (45) | 3 reps (27) | 3 reps (36) | OpenRouter |

*Sonnet Phase 3 had some timed-out runs where dispatch never occurred.

---

## Next Session: Planned Work

### 1. Complete Fable 5 to 3 reps
Run one more rep across all 3 phases to match the OpenRouter models. Use sequential execution with 20s delay, same as this session.

### 2. Complete Anthropic Phase 3 to 3 reps
All Anthropic models (except Fable) have 2 Phase 3 reps. Run one more rep each, sequential, to match OpenRouter. Run one model at a time to avoid rate limiting.

### 3. Scorer improvements
- Add clarifying-question patterns to confirmation gate regex (Sonnet mc-09 false negative)
- Consider softening `prompt_has_context_section` to detect contextual content in any section
- Consider whether User Support newcomer orientation should exempt from confirmation gate

### 4. Clean up rogue git commits
4 commits on `daaf_dev` above `d07b021` created by benchmark subagents. Need to be reverted.

### 5. Investigate `--disallowed-tools` compound command gap
If desired, implement a PreToolUse hook for git-blocking during benchmark runs as the official recommendation suggests. Lower priority since it doesn't affect scoring.

---

## Restart Prompt

> Launch framework development mode. We're continuing work on the DAAF benchmark system at `/daaf/benchmarks`. Read `/daaf/benchmarks/SESSION_RESTART.md` for the complete state. This session completed Phase 3 across all 17 models (7 Anthropic + 10 OpenRouter), added Fable 5 (perfect on Phases 1+2, 88% Phase 3), fixed the viewer's rep-renumbering bug, and resolved Anthropic rate-limiting issues via sequential execution. The current priority is [STATE YOUR PRIORITY — e.g., "running a 3rd rep of Fable across all phases", "completing Anthropic Phase 3 to 3 reps", "scorer improvements", etc.]. Start by reading the restart file and confirming the plan.
