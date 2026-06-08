# Benchmark System Session Restart

**Date:** 2026-06-08
**Mode:** Framework Development
**Workspace:** /daaf/benchmarks
**Reference Plan:** /daaf/research/2026-05-01_Benchmark_Testing/Benchmark_System_Reference.md

---

## What Was Accomplished This Session

### OpenRouter Integration + Model Matrix Expansion

**New file: `harness/model_loader.py`:**
- Centralized model loading from `models.yaml`, replacing duplicated `load_models_from_yaml()` across 3 runners
- Provider-specific env var resolution: maps `OPENROUTER_BASE_URL` + `OPENROUTER_AUTH_TOKEN` → Claude CLI env vars
- Gracefully skips OpenRouter models when env vars are missing
- CLI filtering: `--models` (by key) and `--provider` (anthropic/openrouter/all)

**`config/models.yaml` expanded to 14 models:**
- 3 Anthropic: Haiku 4.5, Sonnet 4.6, Opus 4.6
- 11 OpenRouter: GLM 5.1, Kimi K2.6, Qwen 3.6 27B, Gemma 4 31B/26B, DeepSeek V4 Pro/Flash, Gemini 3.1 Pro/Flash Lite, Gemini 3.5 Flash, Nemotron 3 Ultra
- Each model has `pricing:` block with input/output rates from OpenRouter `/api/v1/models` API (pulled 2026-06-08)
- Fixed Kimi model ID: `kimi-k2.6` → `moonshotai/kimi-k2.6`

### Token Capture + Accurate Cost Computation

**Problem discovered:** The Claude CLI's `total_cost_usd` uses Anthropic-internal pricing for ALL models, making it 20-50x wrong for OpenRouter models. DeepSeek V4 Flash CLI-reported $105 for 108 runs; real OpenRouter billing was ~$2.

**Solution:**
- `_extract_token_usage()` in `executor.py` captures `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_creation_tokens` from the CLI's result message `usage` block (falls back to `modelUsage`)
- Token fields added to `RunResult` dataclass and propagated through all 3 runners
- `PricingConfig` dataclass in `models.py` with `estimate_cost()` method
- All runners now compute and display `computed_cost_usd` (tokens × model pricing) instead of CLI's `total_cost_usd`

**Key semantic discovery:** CLI's `input_tokens` is the UNCACHED count. `cache_read_input_tokens` is additive. Total billed input = input_tokens + cache_read_tokens. Initial code double-subtracted; fixed.

**Validation:** Computed costs within 2-9% of actual OpenRouter billing (tested against 3 models).

### Pre-Run Cost Estimation

**New file: `harness/cost_estimator.py`:**
- Stores calibrated token profiles (avg input/output/cached tokens per case) from real benchmark runs
- `estimate_batch_cost()` multiplies token profiles × model pricing for pre-run estimates
- `compute_cost()` computes actual cost from a completed RunResult
- `format_estimate()` for human-readable display
- All 3 runners display estimate before launching, with `Proceed? [y/N]` confirmation (>$0.50 threshold)
- `--yes`/`-y` flag skips confirmation for scripted/CI runs

**Calibration data:** Collected from Haiku 4.5, DeepSeek V4 Flash, and Gemini 3.1 Flash Lite (3 reps each across all 3 phases, averaged across models).

---

## Key Architecture Decisions (Cumulative)

### Prior session decisions (1-20, still valid)
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
15. Tool failure extraction from JSON output
16. Timeout session_id recovery via filesystem
17. "Credit requires success" scoring principle
18. Structural prompt criteria from framework templates
19. Prescriptive subagent behavior from transcript analysis
20. run_with_capture.sh copied into sandbox workspace

### New decisions this session

#### 21. OpenRouter env var wiring via provider abstraction
`model_loader.py` maps provider names to env var specs. For OpenRouter: `ANTHROPIC_BASE_URL` ← `OPENROUTER_BASE_URL`, `ANTHROPIC_AUTH_TOKEN` ← `OPENROUTER_AUTH_TOKEN`, `ANTHROPIC_API_KEY` ← "" (blank). Resolved at load time; models with missing env vars are skipped with a warning.

#### 22. Pricing from OpenRouter API, not web scraping
Web-scraped pricing from model pages was 20-50% off actual billing. The `/api/v1/models` endpoint returns exact per-token rates. Rates are stored in `models.yaml` (pulled once, not dynamic) with a date comment for staleness tracking.

#### 23. computed_cost_usd replaces CLI cost_usd
CLI's `total_cost_usd` is authoritative only for Anthropic direct subscription. For OpenRouter (and for consistency), all runners now compute cost from tokens × pricing. The field in result.json and summary.json is `computed_cost_usd`.

#### 24. Token-based cost estimation replaces ratio scaling
Initial estimator used Sonnet dollar-cost ratios to scale for other models — was 15-50x wrong because OpenRouter models generate wildly different token volumes. Replaced with calibrated per-case token profiles (avg input/output/cached) multiplied by each model's actual per-token pricing.

#### 25. input_tokens from CLI is uncached
The Claude CLI's usage block: `input_tokens` = uncached input count, `cache_read_input_tokens` = cached input count (additive). Total billed = input_tokens + cache_read_input_tokens. This differs from how some APIs report (where input_tokens includes cached).

---

## Key Behavioral Findings (Cumulative)

### Prior session findings (still valid)
- Haiku's "shortcutting" pattern
- Skill tool vs. Read tool preference
- Relevance vs. compliance tension
- Adversarial test cases as differentiator
- Opus handles simple tasks directly instead of dispatching
- The "sunk cost" dispatch skip
- Context-first vs task-first dispatch templates
- Data-ingest agent/mode conflation
- CWD affects project discovery
- Permission system inflates failure rates
- Claude Code permission modes are coarser than expected
- The "read before dispatch" pattern is universal and rational
- Subagent behavior is uniformly correct once dispatched
- Model-specific dispatch strategies visible in tool call distributions
- Structural prompt sections are the key differentiator
- Tool failures are predominantly infrastructure artifacts
- Debugger behavioral deviation: fix vs. diagnostic
- Code-reviewer sometimes executes fixtures

### New findings this session

#### OpenRouter models are dramatically more verbose
DeepSeek V4 Flash and Gemini 3.1 Flash Lite generate 65-70k input tokens for Phase 1 runs vs Sonnet's ~5k tokens for the same prompts. This appears to be tokenizer differences (more tokens per word) and/or different system prompt handling. Output tokens are comparable (~500-800 across models).

#### Gemini 3.1 Flash Lite struggles with mode classification
40% all-criteria pass rate on Phase 1. Gets orchestrator_skill right (100%) but mode_correct (42%) and confirm_gate (53%) are weak. data_lookup cases are hardest.

#### DeepSeek V4 Flash excels at post-confirmation protocol
27/27 perfect score on Phase 2 — reads correct mode reference and loads correct skills every time. Better than Haiku (89%) on this task.

#### OpenRouter models handle dispatch compliance reasonably well
DeepSeek V4 Flash: 53% all-10-criteria pass rate on Phase 3 (vs Haiku 22%). Gemini 3.1 Flash Lite dispatches correctly every time (36/36) but has structural prompt gaps.

---

## Complete File Inventory (Updated)

### Harness (core execution engine)
- `harness/models.py` — Dataclasses (PricingConfig, ModelConfig with pricing, RunResult with token fields)
- `harness/executor.py` — Single test execution (with _extract_token_usage)
- `harness/model_loader.py` — Shared model loading, provider env wiring, CLI filtering (NEW)
- `harness/cost_estimator.py` — Token-based cost estimation and computation (NEW)
- `harness/collector.py` — Transcript reading (mostly legacy)
- `harness/checkpoint_manager.py` — Golden checkpoint cloning

### Scorers
- `scorers/deterministic/mode_classification.py` — Phase 1 scorer
- `scorers/deterministic/checkpoint_adherence.py` — Phase 2 scorer
- `scorers/deterministic/dispatch_compliance.py` — Phase 3 scorer (10 criteria)
- `scorers/deterministic/subagent_behavior.py` — Subagent behavior scorer (24 prescriptive specs)
- `scorers/llm_judge/__init__.py` — Empty placeholder

### Phase-specific runners
- `scripts/run_mode_classification.py` — Phase 1 (with computed_cost_usd, token capture, cost estimation)
- `scripts/run_post_confirmation.py` — Phase 2 (same updates)
- `scripts/run_dispatch_compliance.py` — Phase 3 (same updates)
- `scripts/rescore_subagent_behavior.py` — Post-hoc subagent rescoring

### Datasets
- `datasets/mode_classification/cases.jsonl` — 15 Phase 1 test cases
- `datasets/post_confirmation/cases.jsonl` — 9 Phase 2 test cases
- `datasets/dispatch_compliance/cases.jsonl` — 12 Phase 3 test cases (10 criteria each)

### Test fixtures
- `datasets/test_fixtures/debugger/join_type_mismatch.py`
- `datasets/test_fixtures/debugger/silent_data_loss.py`
- `datasets/test_fixtures/code_reviewer/frpl_poverty_rates.py`
- `datasets/test_fixtures/code_reviewer/enrollment_trends.py`
- `datasets/test_fixtures/data_ingest/books.csv`
- `datasets/test_fixtures/data_ingest/messy_students.csv`

### Golden checkpoints
- `golden/mode_classification/mc-{01..15}.jsonl` — Phase 1
- `golden/post_confirmation/{mode}.jsonl` — Phase 2
- `golden/dispatch_compliance/ad_hoc_initialized.jsonl` — Phase 3

### Config
- `config/models.yaml` — Model matrix (14 models: 3 Anthropic + 11 OpenRouter, with pricing)

### Results (gitignored, on disk)
- Clean runs in progress: Sonnet 4.6, GLM 5.1, Gemini 3.5 Flash (3 reps × 3 phases = 324 runs)
- All prior results cleared

---

## Next Session: Planned Work

### 1. HTML Results Viewer (PRIMARY)
Browser-based viewer for `results/{timestamp}/summary.json` with:
- Run selector: pick result sets by timestamp, see metadata (models, phases, reps)
- Model comparison table: pass rates by criterion across models
- Drill-down to individual runs: token counts, cost, duration, criterion pass/fail with detail text
- Subagent behavior breakdown (Phase 3)
- Cost summary: per-model, per-phase, total
- The clean runs from this session (Sonnet 4.6, GLM 5.1, Gemini 3.5 Flash, 3 reps each) provide the data to build and test against

### 2. Exam-Style Knowledge Tests
Separate test category — framework knowledge questions without execution:
- "What subagent type should be dispatched for Stage 5 data fetch?"
- "What are the required sections in a research-executor dispatch prompt?"
Deterministic scoring against known-correct answers. Very cheap (~$0.02/run).

### 3. Validation Run: All Anthropic Models
Run Opus, Sonnet, and Haiku with the complete updated system (computed costs, token capture, 10 dispatch criteria, 24 subagent behavior specs). First clean Anthropic-only baseline.

### 4. Rescore Prior Runs
The `rescore_subagent_behavior.py` script can rescore existing results post-hoc. Not applicable now (prior results cleared), but useful after accumulating new runs.

---

## Restart Prompt

To resume this work, start a new session and paste:

> Launch framework development mode. We're continuing work on the DAAF benchmark system at `/daaf/benchmarks`. Read `/daaf/benchmarks/SESSION_RESTART.md` for the complete state of what was built, architecture decisions, and next steps. The priority for this session is building the HTML results viewer (item 1 in "Next Session: Planned Work"). There should be clean benchmark results in `benchmarks/results/` from 3 models (Sonnet 4.6, GLM 5.1, Gemini 3.5 Flash) × 3 reps across all 3 phases — use those as the data source to build and test the viewer. Start by reading the restart file and examining the result directory structure, then come back to me with a plan before starting work.
