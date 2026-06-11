# Session Notes: Framework Development — Benchmark Bugfixes (Timeout Rescue + Viewer Keying)

**Started:** 2026-06-11
**Workspace:** /daaf/research/2026-06-11_FrameworkDev_Benchmark_Bugfixes
**Work Type:** Modify Existing (multi-file, benchmarks subsystem)

## Accomplishments

- Diagnosed user-reported scoring discrepancy (dc-08 Gemma 4 26B, session 177b5cea, set 20260609_003629):
  scoring was correct for that run (model never dispatched; derailed by pre-fix fixture-wipe bug, burned 10-turn cap)
- Found viewer transcript mis-association root cause: `generate_results_viewer_v2.py:719,737` and
  `viewer_template.html:2519,2557` key transcripts/subagent_transcripts by bare run-dir name;
  379 colliding names, 1,028 affected run instances, 22 runs inherit a wrong subagent transcript
- Found timeout data-loss root cause: `executor.py` uses `subprocess.run(timeout=)` → SIGKILL, no flush;
  Claude Code main-transcript writes are async/buffered; loss tail varies (0 → everything post-golden)
- Measured impact: 14 of 33 timed-out Phase 3 runs scored `agent_dispatched: False` despite archived
  subagent transcripts proving dispatch (worst: `_005920/dc-07_Gemma_4_31B` frozen at exactly 47 golden
  lines beside a 71KB subagent transcript)
- Verified subagent transcript first user record contains the FULL dispatched prompt (and `.meta.json`
  has `agentType`), so all 10 dispatch criteria + Phase 3b are recoverable
- Bonus: `tool_call_count` hardcoded 0 at `run_dispatch_compliance.py:144` (vestigial, misleading)

## Key Decisions (user-confirmed at Checkpoint 1, 2026-06-11)

- Scorer fallback is EVIDENCE-GATED (subagent transcript presence, keyed by per-run session UUID),
  not timeout-gated — applies to any run missing Agent records; no false-rescue path exists
- Phase 3b subagent behavior IS scored for rescued runs (changes P3b denominators deliberately)
- Rescued criteria carry provenance stamp "recovered from subagent transcript" in detail strings
- `tool_call_count`: compute properly (not drop)
- Item 5 (viewer keying fix) is HELD until user confirms — another agent is doing a viewer editorial pass
- Executor fix: SIGTERM → ~15s grace → SIGKILL ladder, with empirical flush validation

## Execution Plan

1. Dispatch A (framework-engineer): scorer fallback + rescore script (create AND run) + tool_call_count
   + README §6/§10/§12 scoring-side updates
2. Dispatch B (framework-engineer): executor graceful shutdown + flush validation + README §9/§11/§12
3. HOLD: viewer composite keying (`{result_set}/{run_dir}`) — wait for user go-ahead
4. Phase 4: 3-angle review (consistency / quality / completeness), then Checkpoint 2

## Integration Status

**Component:** benchmarks subsystem (scorers, runner, executor, rescore tooling, README)
**Checklist:** FRAMEWORK_INTEGRATION_CHECKLIST.md § modification subsection (benchmarks is
self-contained; README.md in benchmarks/ is its single source of truth and must absorb all changes)
**Completed:** 2 of 2 dispatches (A: scorer/rescore; B: executor ladder); 3-angle review complete 2026-06-11 ~03:28 UTC
**Remaining:** held viewer fix (item 5), viewer regeneration after item 5
**Fix cycle (2026-06-11 ~03:40-03:47 UTC, agent acdb54241592707ee + orchestrator):** gate tightened
to `not agent_calls` (recorded failed dispatches can no longer be overturned; verified no-op on all
83 rescued runs — zero had recorded Agent calls; dry-run determinism passed on all 24 sets);
malformed-evidence isinstance guards (fuzzed: all attack shapes skip/degrade, never raise — 512/512
archived first records conform); README § 6 accuracy (7-of-9 summaries wording, pruned-set dates
20260610→20260609 corrected, tool_call_count mixed-semantics sentence); polish (Criterion 10 comment,
runner docstring 10 criteria, rescue docstring recovery-inert wording). Focused 2-angle re-review:
PASS on all checks; one LOW residual (dict non-user first record degraded instead of skipping) fixed
directly by orchestrator (`dispatch_compliance.py` else-continue after prompt extraction) and
fuzz-verified.
**Throwaway validation sets:** deleted at user direction 2026-06-11 (README §§ 11-12 annotated)

## In Progress

- Dispatch A COMPLETE (2026-06-11 ~03:13 UTC, agent a494fe2b9cd82385d): scorer fallback
  (`dispatch_compliance.py` + `subagent_behavior.py` parameterized variant), runner wiring +
  `tool_call_count` fix, new `rescore_dispatch_timeout_rescue.py` created AND executed.
  **83 runs rescued** (not ~14 — orchestrator's earlier sweep undercounted via bad subcategory
  filter; engineer's sweep verified independently: all 83 timed-out, all gained Phase 3b, 93
  result.json + 9 summary.json rewritten, determinism gate 0 failures). Model distribution:
  Nemotron 17, Gemma-31B 14, DS-Pro 12, Kimi 10, Gemma-26B 8, Qwen 7, DS-Flash 6, GLM 5,
  Sonnet 3, Gemini-Pro 1. README §§ 3/6/9/10/11/12 updated.
- Dispatch B COMPLETE (2026-06-11 ~03:23 UTC, agent aec7cb1b11f623534): `executor.py` Popen +
  `_graceful_kill()` ladder (SIGTERM → `KILL_GRACE_SECONDS=15` grace via communicate → SIGKILL);
  timeout-branch error-ordering fix (set "Timed out" AFTER partial-stdout parse so runners'
  substring-based `timed_out` derivation can't be corrupted); defensive child reaping. README
  §§ 6/9/11/12 updated. Validation: 2 throwaway sets `20260611_031838` (20s — didn't time out,
  Haiku finished in 14.4s) and `20260611_031913` (10s — kill path exercised: CLI exited ~0.1s
  after SIGTERM, clean 15-line transcript, scored). HONEST CAVEAT: flush improvement over SIGKILL
  not positively demonstrated (kill landed mid-generation, no buffered tail pending); historical
  loss was a race. Scoring-side recovery (Dispatch A) remains the backstop. Engineer recommends
  checking the next organic Phase 3 batch's timed-out transcripts before closing § 11 item 9.
  Throwaway sets awaiting user keep/delete decision.
- Item 5 COMPLETE (2026-06-11 ~11:04 UTC, agent a81d986d6ce26a77a, user-released): composite
  `{result_set}/{run_dir}` transcript keys in generator (`load_transcripts`, v2.6.0→2.7.0) + template
  (lines 2971/3010); regenerated `viewer_2026-06-11i.html` (52 sets, 2,493 runs); verified: +857
  transcripts recovered from key collisions (482 colliding names / 1,339 transcript-bearing instances
  — larger than orchestrator's pre-pass estimate), subagent misattribution fixed (only `_005920`
  composite carries the dc-08 Gemma 26B subagent transcript), 83 rescued runs visible with provenance.
  NOTE: concurrent viewer session had already regenerated post-rescue (`_11f`-`_11h`), so `_11i`'s
  delta is the keying fix. README § 8 keying bullet + § 12 viewer-current updated by engineer.
  BACKLOG (engineer recommendation): deep-link/`jumpToRun` still match bare run-dir names
  (first-match-across-sets); display-only mis-highlight; fix = namespaced anchor with legacy fallback.
- Fable dark-run replacement (2026-06-11 ~12:48 UTC): 4 transcript-less pc-03/pc-07 runs moved to
  `removed_runs/` in sets 20260609_203258/_215903 (provenance notes written); replaced by 4 fresh
  runs at 300s in set `20260611_124829` — 4/4 all-criteria pass; pc-07 rep 0 organically timed out
  under the new ladder and STILL archived a fully scored transcript (first organic ladder evidence,
  confounded by 120s→300s ceiling change). README § 12 bullet updated.
- DeepSeek timeout mini-report delivered (orchestrator sweep): DS Pro P2 52% / P3 64% timeout rates
  (corpus: 16% / 36%), 12 of 23 P3 timeouts rescued; DS Flash P3 33%, 6 of 12 rescued.
- Viewer regeneration must follow item 5 (rescued scores not yet in any viewer HTML)

## Open Questions

- None blocking; viewer fix timing awaits user confirmation

## Key File/Line References

- `benchmarks/scorers/deterministic/dispatch_compliance.py` — fallback insertion point
  (`score_dispatch_compliance`, agent_calls extraction)
- `benchmarks/scorers/deterministic/subagent_behavior.py` — `find_subagent_transcripts` (live-path
  based; rescore needs archived-path variant)
- `benchmarks/scripts/run_dispatch_compliance.py:144` (`tool_call_count: 0`), `:738` (console echo)
- `benchmarks/scripts/rescore_criteria_overhaul.py`, `rescore_skill_routing.py` — rescore precedents
  (in-place result.json rewrite, summary.json regeneration, merge semantics)
- Archived evidence layout: `results/{set}/runs/{run}/subagents/agent-*.jsonl` + `agent-*.meta.json`
  (meta: `{"agentType": ..., "description": ...}`; first user record of jsonl = dispatched prompt)
- Affected-run sweep criterion: phase-3 result.json with agent_dispatched failed + subagents/ dir present

## AI Disclosure

This session used DAAF (Data Analyst Augmentation Framework) in Framework Development mode. DAAF
contributed to: bug diagnosis (viewer keying collision, SIGKILL transcript loss, vestigial field),
impact quantification across archived result sets, fix scoping, artifact authoring via specialist
dispatches, and cross-file consistency review. The researcher directed all design decisions and
approved scope at checkpoints.
