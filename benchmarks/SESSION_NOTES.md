# Session Notes: Framework Development — Benchmarks Cleanup + README

**Started:** 2026-06-09 (Session 4)
**Workspace:** /daaf/benchmarks
**Work Type:** Multi-Component (folder cleanup + new documentation)

## Accomplishments

- Commit `chore(benchmarks): remove leaked benchmark test artifacts from git tracking` —
  git rm of `research/2026-06-09_AdHoc_Session/`, `research/2026-06-09_AdHoc_Synthetic_DiD_Panel/`,
  and 2 tracked files inside `benchmarks/_sandbox/run_dc-01_Gemini_3.1_Pro_0/`. Deletion
  commits chosen over reverts (user decision — branch will be squash-merged).
- Restored contaminated debugger fixtures via `git restore`:
  `datasets/test_fixtures/debugger/join_type_mismatch.py`, `silent_data_loss.py`
- Deleted: 12 stale `viewer_2026-06-0*.html` (~76MB; kept `viewer.html`, `_09e`, `_09g`),
  fixture run artifacts (`*_a.py`, `workspace/`, `cr/`, `adhoc_*`, `01_diag-*`, `02_diag-*`,
  `*_FIXED*`, `debugger/scripts/`), `scripts/diag_token_accounting.py`, `scripts/test_git_deny.py`,
  `scripts/calibrate_reasoning_multipliers.py`, `VIEWER_PLAN.md`, `openrouter-activity-*.csv`
- Commit `chore(benchmarks): archive legacy components...` — created `benchmarks/archive/`
  with README; `git mv` of `harness/runner.py`, `config/cost_budget.yaml`,
  `golden/mode_classification/` → `archive/golden_mode_classification/`;
  `git rm scripts/rescore_subagent_behavior.py`
- Commit `feat(benchmarks): Session 3 — Fable 5 support...` — session work (models.yaml,
  harness, runners, cases.jsonl, .gitignore, SESSION_RESTART*.md, generate_results_viewer.py)
  plus docstring fix in `run_mode_classification.py` (cold-start, not bootstrap checkpoint)
- Created `/daaf/benchmarks/README.md` (429 lines, 12 sections) via framework-engineer —
  supersedes SESSION_RESTART files as system documentation

## Key Decisions

- Deletion commits over reverts for rogue subagent commits (squash-merge PR planned)
- `viewer.html` stays untracked but NOT gitignored (user declined .gitignore changes)
- One-off scripts deleted outright; unused-but-coherent legacy code archived with README
- `rm -r` operations left to user by preference: `__pycache__` dirs (5) and `_sandbox/` purge

## Phase 4 Review Outcomes (all resolved)

- Consistency: `run_benchmark.sh` still invoked archived `harness.runner` → moved to
  `archive/` with README row. All README paths/CLI/counts verified against code.
- Quality: README overstated `prompt_has_context_section` strictness — scorer already
  accepts 7 heading variants (`dispatch_compliance.py:223-247`) yet it remains the #1
  failure. Corrected §6/§10/§12; added Fable-vs-Gemini tiering rationale and
  cache-write-cost caveat in §7.
- Completeness: README initially uncommitted → committed. Fixtures verified pristine
  (their `EXECUTION OUTPUT` blocks are canonical content, present in d07b021).

## Post-Review Cleanup (user-executed, verified)

- 77 benchmark-leaked folders deleted from `/daaf/research/` (all 2026-06-dated +
  `title1-did-analysis`); 8 genuine projects remain (2026-03-29, 2026-03-30,
  2026-05-01 ×2, 2026-05-10 ×2, 2026-05-13, 2026-05-14)
- All `__pycache__` dirs deleted

## Open Items

- `_sandbox/` purge deferred by user. Analysis: 253MB of 263MB is `_sandbox/transcripts/`
  (Phase 3 archive-before-cleanup staging). Viewer reads ONLY `results/`; every kept run's
  transcripts are duplicated in `results/.../runs/{run}/`. Unique content lost on purge:
  transcripts of already-deleted result sets + workspace file artifacts (9.7MB). Safe to
  purge whenever; user may keep until after PR squash-merge.
- Note: future Phase 2/3 runs will re-leak `research/` folders (e.g., the ad_hoc golden
  checkpoint references workspace `title1-did-analysis`) until sandbox redirection or
  pre/post-run cleanup is implemented — related to the fixture-cleanup bookmark below.

## Bookmark (user-requested)

Add pre-run fixture cleanup/restore to `run_dispatch_compliance.py` so debugger/code-reviewer
fixtures reset before each launch. Recorded in README § Future Work.

## Restart Prompt (Session 5)

> Launch framework development mode. We're continuing work on the DAAF benchmark system
> at `/daaf/benchmarks`. Read `/daaf/benchmarks/README.md` for system documentation and
> `/daaf/benchmarks/SESSION_NOTES.md` for Session 4 state (cleanup + README authoring,
> complete). Candidate priorities from README § 12 Future Work: (1) pre-run fixture
> cleanup in run_dispatch_compliance.py, (2) scorer improvements (confirmation-gate
> clarifying-question patterns; content-based context detection), (3) complete Fable 5 +
> Anthropic Phase 3 to 3 reps (sequential), (4) recalibrate cost estimation profiles,
> (5) PreToolUse git-blocking hook. The priority for this session is [STATE YOUR PRIORITY].

## AI Disclosure

This session used DAAF (Data Analyst Augmentation Framework) in Framework Development mode.
DAAF contributed to: folder inventory and leak detection, git cleanup execution, archive
organization, README authoring with code-verified facts, and multi-angle review. The
researcher directed all scope decisions and approved all deletions and commits.
