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

## In Progress

- Phase 4: 3-angle review pass (Consistency / Quality / Completeness) of README + cleanup
- Then Checkpoint 2 presentation to user

## Open Items for User

- Purge `_sandbox/` contents manually (263MB, regenerable)
- Delete 5 `__pycache__` dirs (regenerable)
- ~75 untracked benchmark-leaked project folders in `/daaf/research/` (dated 2026-06-08/09:
  AdHoc_*, College_Selectivity reproductions, `title1-did-analysis`) — NOT yet addressed;
  outside approved benchmarks scope. Genuine projects to PRESERVE: 2026-03-29, 2026-03-30,
  2026-05-01 (×2), 2026-05-10 (×2), 2026-05-13, 2026-05-14 folders.

## Bookmark (user-requested)

Add pre-run fixture cleanup/restore to `run_dispatch_compliance.py` so debugger/code-reviewer
fixtures reset before each launch. Recorded in README § Future Work.

## AI Disclosure

This session used DAAF (Data Analyst Augmentation Framework) in Framework Development mode.
DAAF contributed to: folder inventory and leak detection, git cleanup execution, archive
organization, README authoring with code-verified facts, and multi-angle review. The
researcher directed all scope decisions and approved all deletions and commits.
