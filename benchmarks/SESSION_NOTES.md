# Session Notes: Framework Development — Benchmark Run Hygiene (Fixture Isolation + Git Blocking)

**Started:** 2026-06-10 (Session 5)
**Workspace:** /daaf/benchmarks
**Work Type:** Modify Existing (benchmark harness code + new benchmark-scoped hook)

## Scope (user-confirmed)

From README § 12 Future Work: items (1) pre-run fixture cleanup and (5) PreToolUse
git-blocking hook. Items (2) scorer improvements, (3) rep completion, (4) cost
recalibration deferred to future sessions.

## Key Findings from Scoping (3 parallel read-only explorations)

- **Fixture contamination root cause is an ordering bug:** `run_dispatch_compliance.py`
  calls `prepare_fixtures()` (populates sandbox, ~line 192) BEFORE `execute_run()` →
  `prepare_sandbox()` rmtree-wipes that same sandbox (`checkpoint_manager.py:86-88`).
  Models receive prompts pointing at deleted sandbox fixture paths, hunt by filename,
  and contaminate originals under `datasets/test_fixtures/`. Restore alone would treat
  the symptom; the ordering must be fixed too.
- **Canonical fixture state is commit `446f772`** (the only commit touching
  `test_fixtures/`); `d07b021` is docs-only. Fixtures currently clean (tree == HEAD).
- **Git-blocking:** `--disallowed-tools` patterns in `models.py:102-113` are
  documented-ineffective (compound-command splitting; prefix-anchored globs). Hooks
  fire in subagent sessions (docs-confirmed; hook input gains `agent_id`). Env var on
  the executor subprocess is visible to all hook invocations in the run.
- **`--settings` injection rejected:** docs are silent on whether a `hooks` key via
  `--settings` merges or replaces project hooks — replacement would silently disable
  `bash-safety.sh` etc. during runs. Env-gated project-settings registration chosen.
- **Sandbox cwd steering explored and declined by user:** runtime cwd (`/daaf`)
  dominates all transcript rewriting (the existing `golden_project_path` rewrite
  already rewrites all 47 `/daaf` literals — provably insufficient). User judged
  cwd=sandbox complexity not worth it once fixture ordering is fixed.

## User Decisions

1. `settings.json` registration approved — **user applies the edit themselves** from
   an exact snippet (Claude does not modify settings.json).
2. No cwd/sandbox-steering changes (declined — see above).
3. Remove dead `disallowed_tools` patterns only AFTER the hook is verified working.
4. No comparability concern since run environment (cwd) stays unchanged.

## Planned Changes

1. **Fixture lifecycle** (`run_dispatch_compliance.py`, `checkpoint_manager.py`,
   `models.py`): fix ordering (sandbox wipe before fixture staging); per-batch
   `restore_fixtures()` in `main()` before the run pool (git status --porcelain →
   path-scoped `git restore` for modified tracked + Python deletion for untracked
   residue, logged, `--no-fixture-restore` escape hatch); post-batch contamination
   check (detect + warn loudly).
2. **Git-blocking hook** (`benchmarks/harness/hooks/block-git-writes.sh`, new +
   executable; `executor.py` sets `DAAF_BENCHMARK_RUN=1`): inert no-op unless env var
   set; default-deny git with read-only allowlist (status/log/diff/show/ls-files/
   rev-parse/--version/bare branch); fail-closed; informative block message naming the
   benchmark harness. Registration snippet for user to add to `/daaf/.claude/settings.json`
   PreToolUse Bash group.
3. README updates (§ 9, § 11 items 1 & 4, § 12).

## In Progress

- Phase 3 implementation COMPLETE (framework-engineer + orchestrator verification):
  - `harness/hooks/block-git-writes.sh` created (194 lines, mode 100755, staged not
    committed); 37/37 engineer test matrix + 2 independent orchestrator sanity checks
    (compound `cd && git commit` blocks with informative message; `git status` allows)
  - Ordering fix: `run_one()` wipes sandbox BEFORE `prepare_fixtures()`;
    `prepare_sandbox(wipe_sandbox=False)` via new `RunConfig.wipe_sandbox` field
    (default True — other runners bit-identical; all call sites keyword-only, verified)
  - `restore_fixtures()` (per-batch, pre-pool) + `check_fixture_contamination()`
    (post-batch, detect+warn only) + `--no-fixture-restore` flag
  - `executor.py` sets `DAAF_BENCHMARK_RUN=1`; README §§ 9/11/12 updated
  - Orchestrator-direct edit: strengthened workspace directive in `prepare_fixtures()`
    (line ~283) — flagged for user review; py_compile clean
- COMPLETE since then: user applied the settings.json registration (verified via
  jq); end-to-end hook verification passed (nested benchmark-style `claude -p`
  session: `git commit --dry-run` blocked with informative message, `git status |
  head` allowed); dead git `disallowed_tools` defaults removed from `models.py`
  (field retained — Phase 4 parallel session uses it for `["Agent"]`); README
  §§ 3/11/12 re-synced.
- 3-angle review: consistency PASS (2 doc-staleness fixes applied); completeness
  PASS (optional suggestions); quality review hit 2 spurious API refusals on the
  hook-parser-tracing framing, succeeded when re-scoped to Python/README — hook
  parser coverage instead comes from engineer's 37-case matrix + 2 orchestrator
  manual traces + consistency reviewer's allowlist-vs-code verification.
- Quality review DEFECT fixed: `git restore -- <path>` restores worktree from
  INDEX, not HEAD — staged contamination (rogue `git add`) would survive with a
  false success print. Now `git restore --staged --worktree --source=HEAD --`;
  also added try/except guards (TimeoutExpired/OSError), removed `.strip()`
  (wrong-path deletion edge), rename/copy `old -> new` both-sides handling,
  escaped-path manual-restore warning; README § 9 registration phrasing fixed.
- Fix re-verification PASS (all 5 items correct; py_compile clean). Two accepted
  warn-only residuals: quoted-rename (`"old" -> "new"`) outer-quote-strip corner
  hits a pathspec warning instead of restoring; `shutil.rmtree(ignore_errors=True)`
  prints success even on silent failure. Both non-destructive, exotic inputs.
- Pending: Checkpoint 2 user approval; commit decision (reviewer note: hook +
  settings.json registration + harness edits should be committed as one unit —
  user decides when, given parallel sessions share the worktree).

## Restart Prompt (if session ends here)

> Launch framework development mode. We're continuing the DAAF benchmark Run
> Hygiene session at `/daaf/benchmarks` (Session 5, this block of SESSION_NOTES.md).
> Implementation + 3-angle review + fix verification are COMPLETE for: fixture
> ordering bug fix, per-batch restore-to-HEAD, post-batch contamination check,
> env-gated git-blocking hook (registered + verified end-to-end), disallowed_tools
> cleanup, README updates. Remaining: Checkpoint 2 user approval and the
> commit-as-one-unit decision. Two parallel FrameworkDev sessions (viewer redesign,
> Phase 4 skill routing) share this worktree — coordinate README/SESSION_NOTES edits.

## Open Questions

- Whether a blocked rogue-git attempt should itself be scored as a safety failure
  (currently unscored; relates to the unbuilt Safety Boundaries category, README § 12).

## AI Disclosure

This session used DAAF (Data Analyst Augmentation Framework) in Framework Development
mode. DAAF contributed to: parallel codebase/documentation exploration, root-cause
analysis of fixture contamination, hook injection mechanism research against official
Claude Code documentation, and implementation. The researcher directed all scope
decisions and applies all safety-critical configuration changes personally.

---

# Session Notes: Framework Development — Results Viewer Redesign (parallel session, 2026-06-10)

**Started:** 2026-06-10
**Workspace:** /daaf/benchmarks
**Work Type:** Modify Existing (Complex) — revamp `viewer.html` into a standalone,
self-explanatory document

> **Parallel-session note:** runs concurrently with the Benchmark Run Hygiene session
> above. File overlap is minimal but real: both sessions will edit `README.md`
> (hygiene: §§ 9, 11, 12; viewer: § 8) and this notes file (additive sections only,
> each session edits only its own block). Viewer session defers its README edit to
> its final work package and re-reads before editing.

## Accomplishments

- Phase 1 scoping: read generator (`scripts/generate_results_viewer.py`, 2,238 lines)
  in full; dispatched 2 read-only inspectors — (a) results data inventory (1,728
  on-disk runs / 42 sets / 17 models; summary-vs-disk count drift in 9 sets; timeouts
  carry valid grades; manifest.json never read by generator), (b) UX/dataviz research
  (tabs → scrolling document + sticky TOC; tier bands over ranks; discrete heatmaps;
  Wong colorblind-safe palette)
- Wrote `/daaf/benchmarks/VIEWER_REDESIGN_PLAN.md` (design spec, 8 work packages)
- Checkpoint 1 passed; 6 decisions in plan § 11: composite = unweighted mean of
  P1/P2/P3a/P3b Perfect rates; mechanical tier bands; all result sets by default;
  dated output filenames retained (README § 8 to be corrected); About-layer depth
  approved; **new script via copy** (`generate_results_viewer_v2.py`) — v1 and
  current `viewer.html` preserved untouched as archival artifacts

## Phase 3 Progress (paused 2026-06-10 ~02:00 UTC at user request + HIGH context)

- **WP1+WP2 COMPLETE** (framework-engineer, verified): created
  `scripts/generate_results_viewer_v2.py` (copy of v1, evolved) +
  `scripts/viewer_template.html` (extracted template; placeholders `__DATA_JSON__`,
  `__PRECOMPUTED_JSON__`, `__GENERATED_DISPLAY__` via `str.replace`). Equivalence vs
  v1 proven byte-identical modulo the added PRECOMPUTED line. Data layer: manifest
  loading (git SHA, config, disk-vs-summary counts), new run fields (`timed_out`,
  `expected_mode`, `subcategory`, `tool_call_count`, `grade`), full PRECOMPUTED
  bundle. 4/4 numeric spot-checks vs independent recounts. Full corpus: 11.18 MB,
  8.4s, 1,728 runs. Deviations ratified: generator_version → 2.0.0; `.gitignore`
  negation `!scripts/viewer_template.html` (ignore glob was swallowing the template).
- **WP3 COMPLETE** (framework-engineer, verified): template → single scrolling
  document, 9 sections (hero/about/leaderboard/cost-performance/phases/cases/costs/
  run-explorer/provenance), sticky scrollspy TOC, hero verdict computed from
  PRECOMPUTED, About layer 746 words (4 `<details>`), provenance footer with
  disk-vs-summary discrepancy disclosure, global filter bar removed (Run Explorer
  got section-local filters; Category select dropped — restore in WP7 if wanted),
  lazy section rendering + 200-row run-list cap, design tokens on `:root`. Template
  1,886 lines. Browser visual checks remain a user step.
- **WP4+WP5 IN PROGRESS — Python half done, template half NOT started.** Two
  framework-engineer dispatches both returned early on context: dispatch 1 completed
  the v2 Python changes (tier rule: gap ≥ 0.05 + quartile fallback → 5 tiers on full
  corpus, T1 = Fable 5 alone; precomputed Pareto frontier; v2 now 1,392 lines);
  dispatch 2 completed full scoping (exact PRECOMPUTED shapes, template line targets,
  removal-safety traces, design decisions) but made zero edits.
  **Complete handoff package: `/daaf/benchmarks/WP45_HANDOFF.md`** — a fresh
  framework-engineer can implement immediately. Recommended split: dispatch A =
  "WP4a leaderboard + removals", dispatch B = "WP4b scatter + WP5 heatmaps +
  verification suite".
- **Remaining after WP4/5:** WP6+WP7 (cases/consistency redesign, run explorer
  upgrades incl. criterion `detail` strings + `tool_failures` display + deep-link
  polish), WP8 (token/palette polish of legacy CSS, contrast audit, full
  regeneration, README § 8 fix — RE-READ README first, parallel session edits it),
  then mandatory 3-angle review (search-agents: consistency/quality/completeness)
  and Checkpoint 2.
- Task list state: WP1+2 #4 done, WP3 #3 done, WP4+5 #5 in_progress, WP6+7 #2,
  WP8 #6, review #1 pending.

## Phase 3 Progress — Session 2 (resumed 2026-06-10 ~02:45 UTC, fresh context)

- **WP4a COMPLETE** (framework-engineer, orchestrator-verified): rank-ordered
  leaderboard (tier gutter rowspan, composite bar + per-phase k/n cells, sort
  control, partial-data chips, cost † footnotes, dynamic tier-rule disclosure);
  `svgGroupedBar` + scorecard CSS deleted; shared 5-step rate-scale design system
  added (`.rs-0`…`.rs-4`/`.rs-na`, `rateStep()`/`rateGlyph()`). Template
  1,888 → 2,032 lines.
- **WP4b+WP5 COMPLETE** (framework-engineer, verified): log-x efficiency-frontier
  scatter (`svgCostFrontier`: provider color+shape redundancy, greedy label nudge,
  zero-cost floor footnote) + per-group model × criterion heatmaps (cached
  `cellAgg`, hard/soft grouped columns, rotated headers, computed callouts,
  `id="phase-<gid>"` anchors for leaderboard deep-links). Independent O(n²) Pareto
  check matches `PRECOMPUTED.cost.frontier` exactly (now 4 points); k/n spot-checks
  21/21 exact (P1 + P3b, varying denominators). Template 2,377 lines.
- **WP6+WP7 COMPLETE** (framework-engineer, verified): per-group case × model
  agreement heatmaps (`konStep` k-of-n scale, subcategory chips, difficulty
  margins) + collapsible case browser (prompt, `expected.*`, hard/soft requirement
  lists, per-rep matrices); grade+`timed_out` status taxonomy replaces error-string
  matching at ALL consumers; `tool_failures[].content` + criterion `detail` strings
  in run detail; criterion-level deep-link filter chips; Case select added
  (Category select judged redundant — disclosed). Generator NOT edited (WP2 had
  already embedded case metadata + `tool_failures`). Template 2,741 lines.
  Agreement/difficulty spot-checks 4/4 exact. Only `#costs` interim marker remains.
- **Corpus drift mid-flight:** now 45 sets / 1,833 runs, incl. TWO
  unrecognized-phase skill-routing sets from the parallel Phase 4 session
  (`20260610_020200` — flagged contaminated in the Phase 4 block, deletion pending;
  `20260610_022333` — dry-run 2). They merge into an "Unknown Phase" eval group
  that hijacks the hero/phases global-weakest callout and enters totals/cost.
  Renderers handle it without crashing. **DECISION PENDING (user):** exclude
  unknown-phase sets at generation time vs. add the Phase 4 mapping to v2 (v1
  precedent: user-directed `required_skills_loaded` PHASE_MAP entry) — gates WP8's
  committed regeneration. If mapped, composite must stay pinned to the four § 11.1
  components (P1/P2/P3a/P3b).
- Remaining: WP8 (palette/contrast polish of legacy sections incl. Costs Detail,
  literal-color → token sweep, orphaned legacy CSS sweep, full regeneration,
  README § 8 fix — RE-READ README first), 3-angle review, Checkpoint 2.

## Session 2 closure (2026-06-10 ~12:30 UTC, context limit reached)

- **Unknown-Phase decision resolved (user chose B):** v2 generator now maps
  Phase 4 (`skill_routing`, marker `required_skills_loaded`, mirrors v1 edit);
  new `COMPOSITE_GIDS` pins composite/leaderboard to P1/P2/P3a/P3b (§ 11.1);
  `callouts.global_weakest` restricted to composite gids; `--exclude-results`
  CLI flag; 26-line "Adding a new benchmark phase" guide above PHASE_MAP.
  v2 → 1,469 lines, version 2.1.0. Composite verified byte-identical pre/post.
- **WP8 COMPLETE** (framework-engineer, verified): Costs Detail redesign
  (sortable Observed Spend, token-mix bars, timeout exclusion footnotes),
  Phase 4 About prose ("The benchmark phases" + composite-exclusion note),
  global_weakest "core phases (P1–P3b)" qualifiers, literal-color → token sweep
  (rateColor/allCriteriaPassed/price-dot deleted), orphan CSS sweep,
  programmatic contrast audit (3 fixes: .rs-3 alpha .65, .rs-na text, badge-fail
  --c-fail-light), README § 8 rewritten (dated default filenames, flags,
  new-phase pointer, composite pinning), GROUP_SHORT "P4".
- **Orchestrator-direct:** MODEL_COLORS/_LIGHT expanded 8 → 17 entries
  (plan § 5 gap; first 8 preserved; status-token hexes avoided). Template
  2,870 lines.
- **Regenerations:** `viewer_2026-06-10c.html` (pre-palette, superseded — ask
  user re deletion) and **`viewer_2026-06-10d.html` (current: 13.34 MB, 47 sets
  / 1,953 runs / 17 models / 51 cases, $283.29, 5 tiers)**.
- **3-angle review COMPLETE** (3 search-agents): no constraint violations; plan
  coverage complete; 14 small fixes identified, **none applied yet** — full
  anchored fix package + Checkpoint 2 agenda in
  **`/daaf/benchmarks/REVIEW_FIX_HANDOFF.md`**. Working tree is in a consistent
  WP8-complete state.
- Framework observation reconfirmed: a fresh framework-engineer saw the PARENT
  session's 207k utilization on its first tool calls and self-gated per protocol
  (returned a scoping package, zero edits) — same context-reporter behavior as
  Session 1's observation.

## Session 3 (2026-06-10 ~12:45 UTC) — Review fixes applied

- **All 14 review fixes APPLIED** (single framework-engineer dispatch, grep-anchored
  targeted reads, ~9% subagent context; dispatch 2 of 2 for this fix component):
  generator fixes 1–4 (`generate_results_viewer_v2.py` → 1,471 lines), template
  fixes 5–12 (`viewer_template.html` → 2,914 lines), README § 8 fix 13 (623 → 626
  lines, § 8 vicinity only — orchestrator-verified against parallel-session hunks).
- **Regenerated (fix 14): `viewer_2026-06-10e.html`** (current: 13.34 MB, 47 sets /
  1,953 runs / 17 models / 51 cases, $288.40; Phase 4 group renders, 225 runs).
  `viewer_2026-06-10c/d.html` untouched (timestamps preserved).
- Verification (engineer + orchestrator spot-checks): py_compile clean; subset +
  full generation zero-error; fix-8 contrast 5.71:1 (was 3.07:1); placeholders
  ×1/×1/×2 in template, zero in outputs; zero literal `<` on data lines;
  `dir_to_phase` survives only in archival v1; `MAX_SAFE_INTEGER` only in ES5
  comments; git status shows no protected files touched.
- Fix-7 rendered wording note: render sites emit the caveat map's reason string,
  so output reads "(deterministic scorer has known false negatives — see caveats)"
  — generic mechanism for future criteria, as specified.
- **Checkpoint 2 held (~14:36 UTC), partial approval + new scope:**
  - Tier-band quartile FALLBACK **ratified**.
  - Housekeeping executed: deleted `viewer.html` (v1 output — old, not to be
    rewritten), `WP45_HANDOFF.md`, `REVIEW_FIX_HANDOFF.md`; older dated viewers
    (`c`/`d`) retained for now. **Committed `c8b67d5`**: v2 generator + template +
    `.gitignore` negation (README § 8 hunk left uncommitted — interleaved with
    hygiene session's README hunks; commit later with hunk-ownership check).
  - Accepted residuals (preserved from deleted handoff): `konStep` labels 1-of-2
    reps as "most"; leaderboard keeps fixed "#" rank column (prose disclaims);
    P3b denominator policy (tooltip mitigates); `print_summary` echoes
    summary.json totals without discrepancy caveat; provenance git-SHA is
    per-set display only.
- **New scope from Checkpoint 2 (iteration loop, design pending user confirm):**
  1. Remove ALL computed actual-spend tracking (OpenRouter tokenizer misalignment
     makes token-derived costs unreliable) — replace cost axes/columns with
     published $/Mtok pricing; caveat as limitation.
  2. Add framing caveat: DAAF instructions authored for Opus 4.5/4.6 — benchmark
     measures conformance under one specific orchestration style, not absolute
     model quality.
  3. Investigate About `<details>` toggle jank (full-page reflow) — likely
     `content-visibility: auto` on major sections.

## Session 3 (cont., ~15:10 UTC) — Checkpoint 2 iteration implemented

- **Design confirmed by user:** blended 3:1 $/Mtok default + Input/Output toggle
  options; per-run token counts removed too; caveats + content-visibility approved.
- **All three change sets COMPLETE** (framework-engineer, grep-anchored; verified):
  pricing-only cost displays (hero spend chip, leaderboard avg-cost column,
  Observed Spend table + token-mix bars, per-run cost/tokens, zero-cost-floor
  footnote ALL removed from template, embed, and output; leaderboard column →
  Blended $/Mtok pinned w/ disclosure); `COST_FORMS` toggle (blend31 default,
  formula in caption, per-formulation precomputed Pareto frontiers — independent
  recompute exact match); orchestration-specificity caveat (About intro sentence
  + top "Reading caveats" bullet) + cost-methodology caveat; `content-visibility:
  auto` + `contain-intrinsic-size` on the 7 below-fold sections (NOT hero/about),
  ids exactly match `sectionRenderers`. Template 2,914 → 2,830; generator v2.2.0.
- **Engineer design decisions (need user ratification):** (1) per-run cost/token
  fields dropped from embedded DATA.runs (zero consumers; unreliable numbers);
  (2) version → 2.2.0 (schema change); (3) `print_precomputed_report` reshaped
  (crash avoidance); (4) zero/missing-price models excluded from scatter (log
  axis); (5) `#costs` anchor/title kept; (6) intrinsic-size 900px/2600px estimates.
- **2-angle review (consistency + completeness search-agents):** all 5
  requirements implemented; contracts/orphans/ES5/version all clean; constraints
  PASS (only the two v2 files in scripts diff; README § 8 untouched this round).
  One DEFECT found+fixed (orchestrator-direct): About timeout caveat falsely
  said "zeroed duration" — duration is recorded at cutoff (281 runs at
  120/180/300s) → now "zeroed turn counts and a duration recorded at the cutoff
  limit". Unratified observation: `clean_sandbox.sh` mode 100644→100755 in
  worktree (chmod only, zero content change — not ours, left alone).
- **Regenerations:** `viewer_2026-06-10g.html` (pre-prose-fix) and
  **`viewer_2026-06-10h.html` (current: 13.18 MB, 49 sets / 2,013 runs / 281
  timed out / 17 models / 51 cases, 5 tiers; blend31 frontier DeepSeek V4
  Flash → GLM 5.1 → Sonnet 4.6 → Fable 5)**. Corpus grew mid-flight again
  (parallel Phase 4 session added sets `20260610_144245`, `_144524`); a
  `viewer_2026-06-10f.html` (13:33) was generated by a parallel session, not ours.
- Iteration changes NOT yet committed (working tree on top of `c8b67d5`);
  pending final user approval + browser test of `h`.

## Session 3 (cont., ~16:00 UTC) — Iteration 2: leaderboard/scatter interactivity

- **User decisions:** Perfect|Hard leaderboard toggle approved (Perfect = all
  criteria; Hard = hard-tier only); tier bands RECOMPUTE under Hard; scatter
  gets decoupled Performance-basis + Metric selectors (P4 excluded from y);
  sortable column headers replace sort buttons (Dispatch was missing);
  controls/legends adjacent to plots, callouts below.
- **All four change sets COMPLETE** (framework-engineer; verified): (CS1)
  clickable headers w/ ▲▼ + aria-sort, ALL numeric columns sortable, old sort
  row deleted, default composite desc; (CS2) run-level hard rates added
  (vacuous-pass: zero-hard-criteria run = hard-pass ⇒ hard ⊇ perfect),
  `composite_hard` + `tiers_hard` via factored single code paths
  (`build_composite_from`, `compute_tiers_for`), gutter + disclosure track
  metric, Consistency Perfect-pinned w/ tooltip; (CS3) `perf_values[basis][metric]`
  + `frontiers[form][basis][metric]` (3×5×2 = 30 lists; point key
  `composite`→`score`); (CS4) adjacency sweep in leaderboard/scatter/
  phase-deep-dives/cases (Costs already clean). Generator 1,552 lines (v2.3.0);
  template 3,007 lines.
- **Engineer decisions ratification-pending:** vacuous hard-pass semantics;
  composite factoring; `score` rename; `tier_rule_hard` embed; tier gutter only
  under composite-desc sort; default sort directions (rates desc, $/Mtok asc);
  micro-edits to section leads.
- **2-angle review: BOTH PASS, zero fixes.** Contracts bidirectional; single
  tier/composite code path; no orphans; ES5 clean; prose↔behavior consistent;
  hard ≥ perfect verified on all 83 embedded cells; no unflagged scope creep.
  Engineer spot-checks: input×P2×hard frontier exact; composite_hard recount
  exact (Sonnet 0.932).
- **Output: `viewer_2026-06-10j.html`** (13.33 MB, 51 sets / 2,073 runs / 17
  models; `i` was taken by a parallel-session regeneration). Working tree vs
  `c8b67d5`: only the two v2 files.
- Pending: user browser test of `j`, ratification of the 7 decisions, commit.
- **User-found DEFECT fixed (orchestrator-direct, ~16:42):** Phase 4 deep-dive
  rendered before P3a/P3b — `renderPhaseDives` appended the 3a/3b `.pd-pair`
  buffer AFTER all standalone blocks (latent since WP5; invisible until a
  post-pair group existed). Fix: pair now emitted at the canonical position of
  its first member (`parts[]` + `pairIdx`, ES5). Regenerated:
  **`viewer_2026-06-10k.html` (current; 13.33 MB, 51 sets / 2,073 runs)**;
  fix grep-confirmed embedded. Browser-verify section order P1→P2→3a/3b→P4.

## Session 3 closure (~17:08 UTC) — Checkpoint 2 approved, COMMITTED

- User approved wrap-up; the 7 iteration-2 engineer decisions (incl. vacuous
  hard-pass semantics) stand ratified.
- **Committed `8f61fc1`** (on top of `c8b67d5`): both iterations + ordering fix,
  the two v2 script files only. Viewer redesign session COMPLETE.
- Deferred to owners / future housekeeping: README § 8 hunk still uncommitted
  (interleaved with hygiene session's hunks — commit with hunk-ownership
  check); superseded dated viewers (`c`–`j`) retention decision; `k` is current.

## Framework Observation (for LEARNINGS-style follow-up)

- The `context-reporter` hook appears to report the PARENT session's utilization to
  freshly spawned subagents (a WP4a framework-engineer with only ~4 tool calls /
  81k total usage saw "HIGH: 233k" on its FIRST tool call and correctly self-gated
  per CLAUDE.md, returning without edits). Once the orchestrator session crosses the
  200k absolute threshold, ALL subagent dispatches instantly refuse work — making
  restart mandatory rather than advisory. Worth investigating whether the hook
  should measure per-agent transcripts instead.
- RESOLVED 2026-06-10: `context-reporter.sh` now measures per-agent transcripts via
  `agent_id` detection (fail-silent, never parent fallback); empirically verified.
  See `research/2026-06-10_FrameworkDev_Context_Reporter_Subagent_Bleed/SESSION_NOTES.md`.

## Restart Prompt

> Launch framework development mode. We're closing out the benchmark viewer
> redesign at /daaf/benchmarks. Read this file's "Results Viewer Redesign"
> session block in full (WP1–8, 14 review fixes, Checkpoint 2 iteration 1
> [pricing-only costs + caveats + content-visibility], and iteration 2
> [sortable headers, Perfect|Hard toggle w/ hard tier recompute, scatter
> price×perf×metric selectors, adjacency sweep] ALL COMPLETE + reviewed,
> zero open defects; plus orchestrator-direct pd-pair ordering fix).
> `/daaf/benchmarks/VIEWER_REDESIGN_PLAN.md` § 11 has original decisions.
> Current output: `viewer_2026-06-10k.html` (working tree = c8b67d5 + the
> two uncommitted v2 script files). Remaining: user browser test of `k`
> (incl. deep-dive order P1→P2→3a/3b→P4); ratify 7 engineer decisions
> listed in "Iteration 2"
> bullet; commit the two v2 files (suggest: feat(benchmarks) iteration
> commit); housekeeping deferred earlier: superseded viewer_2026-06-10c/d/
> e/g/h.html retention decision. Constraints: v1 generator is archival
> (never modify; viewer.html deleted by user decision); parallel sessions
> own run_dispatch_compliance.py, run_skill_routing.py, harness/*,
> README.md (§ 8 vicinity is ours, re-read before editing);
> SESSION_NOTES.md is shared — edit only the viewer-redesign block,
> additively, re-read before editing (parallel edits DO land mid-session).

## AI Disclosure

This session used DAAF (Data Analyst Augmentation Framework) in Framework Development
mode. DAAF contributed to: generator code analysis, results-data inventory, web UX
research, design plan authoring, and implementation via specialist dispatches. The
researcher directed all scope and design decisions.

---

# Session Notes: Framework Development — Phase 4 Skill-Routing Benchmark (parallel session, 2026-06-10)

**Started:** 2026-06-10
**Workspace:** /daaf/benchmarks
**Work Type:** Multi-Component (new benchmark phase: dataset + scorer + runner + estimator edit)

> **Parallel-session note:** runs concurrently with the Run Hygiene and Viewer Redesign
> sessions above. File overlap: this session creates NEW files only
> (`datasets/skill_routing/cases.jsonl`, `scorers/deterministic/skill_routing.py`,
> `scripts/run_skill_routing.py`, `PHASE4_SKILL_ROUTING_PLAN.md`) plus an edit to
> `harness/cost_estimator.py` (untouched by the other sessions). README updates are
> deferred until after dry-run validation and will re-read before editing (hygiene owns
> §§ 9/11/12; viewer owns § 8; Phase 4 will add to §§ 2/3/5/6). This session READS
> `run_dispatch_compliance.py` as a clone template but does not edit it.

## Accomplishments

- 3 read-only scouts extracted verbatim routing directives from 12 in-scope skills
  (data-scientist hub + 11 library/methodology skills) and verified Phase 4 mechanics:
  the Phase 3 golden `ad_hoc_initialized.jsonl` is topic-free (only daaf-orchestrator +
  ad-hoc mode ref + data-scientist in context), Skill/Read tool_use shapes confirmed,
  `checkpoint_adherence.py` extraction reusable, sandbox replay path-mangling requires
  basename-only Read matching.
- Authored `/daaf/benchmarks/PHASE4_SKILL_ROUTING_PLAN.md` — **APPROVED** by user.
  15 cases (sr-01..sr-15) with exact prompts + verbatim ground-truth routing quotes;
  6 deterministic criteria; coverage: pyfixest ×2, linearmodels ×3, statsmodels ×1,
  svy ×1, scikit-learn ×2, plotnine ×2, plotly ×1, geopandas ×3, science-communication
  ×1, two-skill hard-tier sr-15.

## Key Decisions (user-confirmed)

- Hub FIRST-reads + required refs HARD; `no_forbidden_skills` SOFT (wrong-skill loads
  are self-correcting via bidirectional disambiguation text in the skills).
- **Agent tool disallowed** for Phase 4 runs (`RunConfig.disallowed_tools=["Agent"]`);
  all scoring main-transcript-only. Whole-tool disallow works (unlike Bash sub-patterns).
- Reuse Phase 3 golden unchanged, referenced by existing path (no copy).
- Excluded by design: time series (no hub branch — routing gap worth fixing separately),
  plain 2SLS (dual-routed), marimo ("Always Load Together" ambiguity). Reserve list in
  plan § 7.

## Carried-Over Findings (unowned by any session: README § 12 items 2 & 4)

- Scorer fixes: mc-09 clarifying-question false negative (patterns at
  `mode_classification.py:91-112`; structural final-paragraph-`?` fallback must land in
  `run_mode_classification.py:162-197`); context-section 3-rule composite (heading →
  preamble → purpose-sentence) with scorer version-stamping + one-pass historical rescore.
- Cost: `compute_cost()` drops cache_creation_tokens → recorded Anthropic Phase 3 costs
  understated ~30-50%. All 43 result sets post-modelUsage-fix and usable for
  recalibration. Rep gaps: 108 runs (fable-5 ×36 all phases; 6 Anthropic models ×12 dc).

## Implementation + Dry-Run Status (end of Phase 4 session 1)

- framework-engineer implemented all four artifacts (COMPLETED, fully validated):
  `datasets/skill_routing/cases.jsonl` (15 cases), `scorers/deterministic/skill_routing.py`
  (213 lines), `scripts/run_skill_routing.py` (731 lines), `cost_estimator.py`
  PHASE4_TOKENS placeholders. All uncommitted.
- **Dry-run 1** (results/20260610_020200, $4.63, 5 cheap OpenRouter models × 15 cases):
  exposed harness bug — cases inherited Phase 3's `golden_project_path: "/daaf"`, which
  made `prepare_sandbox()` rewrite ALL `/daaf` literals (incl. in-history skill paths)
  to the sandbox path, poisoning routing. **CONTAMINATED — pending user-approved
  deletion.** Fixed by removing the field from all 15 cases (prepare_sandbox skips
  rewrite when None; verified through executor.py:43 → checkpoint_manager.py:111).
- **Dry-run 2** (results/20260610_022333, $3.88): tool failures 59→3. Audit verdict
  (2 search-agents; 0/75 discrepancies on independently re-derived hard criteria):
  **scorer trustworthy for baseline use; low scores are TRUE behavior** — 61% answered
  from parametric memory (zero tools), 28% read refs but never invoked Skill tool,
  5.3% full correct routing (sr-14 ×3 + sr-03 Qwen), 0% read-SKILL.md-directly,
  0% wrong-skill loads. sr-14 (only case whose order STARTS with a Skill call) got
  5/5 skill loads — the hub FIRST-read→THEN-load pattern is where cheap models
  collapse. Tool failures: 2 hallucinated Read params, 1 AskUserQuestion stall
  (sr-10 Qwen). Token actuals captured (OpenRouter ~61-112k uncached input/run;
  cache_creation 0 everywhere; only GLM/Kimi register cache reads).

## Remaining Work (next session)

1. Delete contaminated result set `results/20260610_020200` (user approval pending)
2. Fix cosmetic `tool_call_count`=0 in run_skill_routing.py per-run metadata
   (criteria path verified independent and correct)
3. Recalibrate PHASE4_TOKENS from results/20260610_022333 actuals
4. Mandatory 3-angle review (Consistency/Quality/Completeness) of all four artifacts
5. README §§ 2/3/5/6 registration (RE-READ README first — hygiene + viewer sessions
   both edit it). Viewer label: **DONE for v1** (user-directed exception to the
   v1-archival rule — added `required_skills_loaded` marker to PHASE_MAP + PHASE_ORDER
   entry in generate_results_viewer.py; regenerated viewer_2026-06-10.html, Phase 4
   renders correctly). v2 generator still needs the same mapping — coordinate with
   viewer session.
6. Checkpoint 2 with user; commit; then Anthropic-model baseline batch (sequential)
7. Consider: vacuous tier-2 pass caveat (no-loads ⇒ no_forbidden passes) in README § 6

## Session 2 (2026-06-10, ~02:40-03:00 UTC) — Remaining Work executed

- Items 1-5 + 7 DONE; item 6 (Checkpoint 2 → commit → baseline batch) in progress:
  - Contaminated set `results/20260610_020200` deleted (user-approved); dry-run 2
    (`20260610_022333`) retained as calibration + audit source.
  - **`no_spurious_skill_reload` criterion REMOVED** (user decision after evidence:
    75/75 vacuous pass in dry-run 2 — 61% of runs made zero tool calls, so "didn't
    reload" is a free pass). Removed from scorer, all 15 cases' soft_requirements,
    plan §§ 2.1/3.1/4/6; § 9 decision 6 records rationale. Historical result.json
    files retain it (viewer collects criterion names dynamically — no breakage).
  - `tool_call_count` now real in run_skill_routing.py (len of post-checkpoint
    `extract_new_tool_calls()`; Phase 3 runner still hardcodes 0 — not this
    session's scope). PHASE4_TOKENS recalibrated from all 75 dry-run-2 runs
    (per-case means; distribution is bimodal: ~52k 1-turn vs up to 334k
    multi-turn; provenance + strong-model-underestimate caveat in-code).
  - README registered (§ 1 bullet, § 2 "Four Phases" + table row + Agent-disallow
    + no-golden_project_path notes, § 3 scorer, § 4 runner, § 5 golden row, § 6
    criteria + vacuous-tier-2 caveat, § 7 staleness scoped to Phases 1-3).
  - 3-angle review (Consistency/Quality/Completeness search-agents): **0 blockers**;
    all flagged issues fixed (plan § 4 stale golden_project_path, sr-15 prose,
    § 8.5 subagent-union residue, § 6 matrix plotnine +sr-11; estimator + scorer
    docstring caveats). README § 6 "75/75" attribution for no_forbidden_skills
    independently verified correct against dry-run-2 tallies.
- **Handoff to viewer session (v2 Phase 4 gap, from completeness review):**
  `generate_results_viewer_v2.py` PHASE_MAP (~lines 89-93) needs the
  `required_skills_loaded` → "Phase 4 — Skill Routing" marker + PHASE_ORDER
  (~line 722) `skill_routing: 4`; `viewer_template.html` hardcoded group order
  (~line 760) and P-label map (~lines 773-774) end at P3b; VIEWER_REDESIGN_PLAN
  composite is P1/P2/P3a/P3b-only.
- Accepted NITs (deliberate): runner's transcript-not-found branch omits
  tool_call_count key (guarded by .get); subagents/ archived only to _sandbox
  (Agent disallowed — no-op safeguard); generate_goldens.py would emit unused
  skill_routing goldens if run (harmless, no collision).

- **COMMITTED (end of Session 2):** `eed6552` — all Phase 4 artifacts + README
  §§ 1-7 hunks (selectively staged via filtered patch; hygiene session's §§ 9-12
  README hunks and this notes file left uncommitted for their owners) + v1 viewer
  Phase 4 label. Checkpoint 2 approved by user.

## Session 3 (2026-06-10, ~03:07 UTC–) — Baseline batch execution

- **Verification batches (1 rep × 15 cases each), both clean:**
  - Haiku 4.5 — `results/20260610_031234`: 15/15 runs, $0.21 actual (est $1.53),
    166s wall, 0 errors/timeouts. 2 tool failures (sr-09: tried to load ref
    basenames "visualization-design"/"visualization-execution" as Skills).
    Scores: skills 2/15, refs 0/15, all-criteria 0/15.
  - Sonnet 4.6 — `results/20260610_032805`: 15/15 runs, $0.76 actual (est $4.59),
    906s wall, 0 errors/timeouts/tool failures. Scores: skills 0/15 (worse than
    Haiku — even sr-14 missed), refs 0/15. Max duration 85s (300s timeout ample).
  - Dry-run failure shape replicates at frontier tier: mostly 0 tool calls
    (parametric-memory answers); engaged runs read hub refs but skip the Skill load.
- **Rate-limit artifact check: NONE found.** result.json error/tool_failure fields
  + full transcript sweep (rate_limit|overloaded|429|too_many_requests) across both
  sets — only 4 false positives ("Overloaded charts" prose in visualization-design.md).
  Note: ripgrep silently skips results/ (gitignored) — use Python for result sweeps.
- v1 viewer regenerated: `viewer_2026-06-10a.html` (45 sets, 1,833 runs) — Phase 4
  sets render.
- Cost calibration observation (inverse of in-code caveat): PHASE4_TOKENS
  OVERSTATES Anthropic models ~6-7x (actual/estimate: Haiku 14%, Sonnet 17%) —
  1-turn memory-answers + prompt caching. Recalibrate from Anthropic actuals
  after full batch.
- Runner quirk noted: `--delay` is parallel-mode-only (sequential loop has no
  sleep) — sequential "delay" is the ~1-2s scoring/archival gap.
- **Anthropic high-tier batch (1 rep × 15 × Opus 4.5 + Opus 4.8 + Fable 5,
  sequential, 300s timeout)** — `results/20260610_040700`: 45/45 runs, $6.13
  actual (est $30.60, 20%), 1,915s wall, 0 errors/timeouts/tool failures.
  All-criteria: Opus 4.5 0/15, Opus 4.8 1/15 (sr-14), Fable 5 2/15 (sr-14,
  sr-03) — faint top-end gradient; floor effect dominates. sr-14 now 2/3 at
  high tier (vs 5/5 skill loads in cheap dry-run): the no-hub-FIRST-read case
  remains the most discriminating. User raised scoring-rigidity concern;
  orchestrator recommendation: finish baseline unchanged, then consider graded
  tier-2 engagement metric and/or framework-side routing strengthening
  (before/after re-run) — decision pending.
- **OpenRouter fresh-5 batch (1 rep × 15 × Gemma 4 31B/26B, DeepSeek V4 Pro,
  Gemini 3.1 Pro, Nemotron 3 Ultra, parallel 2s)** — `results/20260610_041451`:
  75 runs, $6.30, 441s wall. All-criteria: Gemini 3.1 Pro 2/15, DeepSeek V4
  Pro 1/15, Nemotron 1/15, Gemmas 0/15. **9 timeouts, all Gemma 4 31B, all
  0 turns** (model produced nothing in 300s on 9/15 cases; other 6 completed) —
  provider stall at venice/bf16, no explicit 429/rate-limit text anywhere;
  rerun or exclusion decision pending. 7 tool failures (hallucinated
  Grep/Read params ×3, AskUserQuestion stalls Nemotron sr-10 + Gemini sr-14,
  Gemini nonexistent-file Read).
- **Rate-limit sweep of both sets: clean.** All transcript pattern hits are
  false positives (skill prose "Overloaded charts", "quotable" matching
  /quota/, `"output_tokens":429` matching /429/).
- v1 viewer regenerated: `viewer_2026-06-10b.html` (13.0 MB).
- **Transcript failure review (user-requested, 2 search-agents):** full verbatim
  reports in `PHASE4_TRANSCRIPT_REVIEW_20260610.md`. Converged finding: failures
  are a coherent REINTERPRETATION, not directive-blindness — both models treat
  the routing tree as an implementation-time protocol ("brainstorming = answer
  directly; skills = when we write code"), explicitly naming the prescribed
  skills/refs while deferring loads ("I'd dispatch with the svy skill when you're
  ready to implement"). Fable: 12/15 correct hub-ref FIRST-reads, failure
  concentrated in the second hop (Skill load); Sonnet: refs read on
  accuracy-anxiety triggers only, Skill tool zero salience in advisory mode
  (visible in thinking blocks). Both reviewers flag that data-scientist's own
  description ("For implementation syntax, load the routed tool-specific skill")
  licenses the deferral — it contradicts the tree's unconditional "THEN load".
  Answers from memory were substantive (graduate-level), incl. accurate library
  APIs cited without loading. Recalibration decision pending with user.

## Restart Prompt (Session 4: complete the baseline matrix)

> Launch framework development mode. We're mid-way through the Phase 4
> (skill_routing) baseline batch. Read, in order:
> (1) `/daaf/benchmarks/PHASE4_SKILL_ROUTING_PLAN.md` (approved spec),
> (2) this file's "Phase 4 Skill-Routing Benchmark" block through Session 3.
> Rep counts so far (1 rep each, all 15 cases): GLM 5.1, Kimi K2.6,
> Qwen 3.6 27B, DeepSeek V4 Flash, Gemini 3.1 Flash Lite (dry-run 2,
> `20260610_022333`); Haiku (`_031234`); Sonnet (`_032805`); Opus 4.5 +
> Opus 4.8 + Fable 5 (`_040700`); Gemma 4 31B (9/15 runs INVALID — 0-turn
> 300s timeouts), Gemma 4 26B, DeepSeek V4 Pro, Gemini 3.1 Pro, Nemotron 3
> Ultra (`_041451`). Opus 4.6 and Opus 4.7: 0 reps. Run commands:
> `python3 benchmarks/scripts/run_skill_routing.py --reps N --models <keys>
> [--sequential] [--timeout 300] --yes`; model keys = name lowercased,
> spaces→`-`, dots removed (opus-46, gemma-4-31b). Anthropic sequential;
> OpenRouter parallel default 2s delay; `--delay` is a NO-OP in sequential
> mode. 300s timeout ample for Anthropic (max seen 85s). Costs: estimator
> overstates Anthropic ~5-7x (actuals: Haiku $0.21/15, Sonnet $0.76/15,
> Opus 4.5 $0.75/15, Opus 4.8 $1.98/15, Fable $3.39/15). Pending decisions:
> (a) Gemma 4 31B 0-turn timeout reruns (venice provider stall — no explicit
> rate-limit text), (b) user's scoring-rigidity concern — recommendation on
> file: finish baseline unchanged, then graded tier-2 engagement metric
> and/or framework-side routing fix with before/after re-run, (c) reps
> top-up to 3 (user-approved earlier), (d) PHASE4_TOKENS recalibration from
> Anthropic actuals (still pending). After batches: Python-sweep (NOT rg —
> results/ is gitignored) errors/tool_failures/transcripts for rate-limit
> artifacts, regenerate v1 viewer, record results additively here.
> Constraints: SESSION_NOTES.md and README.md are shared with two parallel
> sessions (hygiene owns README §§ 9/11/12 — its hunks are uncommitted;
> viewer owns § 8 and all viewer_v2/template files) — edit only the Phase 4
> block of this file, additively; re-read before editing (parallel edits DO
> land mid-session); never commit shared files without checking hunk
> ownership first.

## Session 4 (2026-06-10, ~12:00 UTC–) — Recalibration decisions + routing-fix scoping

- **User decisions (supersede Session 3 pending items):**
  - SKIP completing the "before" baseline (no Opus 4.6/4.7 batch now; no reps
    top-up) — cost-driven; behavioral pattern judged consistent across 15 cases
    at 1 rep. Sequence is now: framework fix → spot-checks → full tests later.
  - Framework fix adopted (Norm A): library skills must be loaded whenever advice
    names tools — advisory turns included — because skills encode
    environment-specific constraints (kaleido absent, svy WLS warning) absent
    from parametric memory. Justified independently of benchmark scores.
  - **Option 2 for acknowledgment scoring:** new tier-2 SOFT criterion
    `required_skills_engaged` = required skill loaded OR name-mentioned in
    user-visible assistant text (superset of hard `required_skills_loaded`;
    loading implies engagement). NOT folded into the hard criterion — folding
    would grade the targeted deferral failure as a pass and blind the
    before/after read. The engaged-vs-loaded gap becomes the headline metric.
- **Phase 1 scoping COMPLETE (3 parallel search-agents):** verbatim reports in
  `PHASE4_ROUTING_FIX_SCOPING_20260610.md`. Key findings:
  - Contradiction is fully contained in the data-scientist skill dir: frontmatter
    description final sentence + SKILL.md lines 12/14/207 + 4 THEN-load lines
    qualified "for implementation [syntax]" (167/176/188/436) + 12 reference-file
    header lines across 7 refs. Zero matches in agent_reference/ or .claude/agents/.
  - 9 external sites duplicate library *enumeration* only (commit 67d5fc4; SM6
    checklist item) — no edits needed unless routing content changes; SM6
    verify-only sweep required.
  - ad-hoc-collaboration-mode.md: 5 passages license memory-answering (97 "this
    is permitted", 132 "from a loaded skill", 135 "and general knowledge", 160
    "err toward responding directly", 324 skill-load budget). data-lookup-mode
    63-64 already models the correct norm (load first; flagged memory fallback).
  - Library frontmatter descriptions: 8/11 have ≤8 chars headroom — defer;
    centralize the advisory-inclusive language in the hub instead. NOTE: scout's
    "250-char truncation" claim (svy 506 / polars 416 / marimo 486 over) is
    contradicted by the live environment (orchestrator's own system prompt shows
    full descriptions incl. svy's CRITICAL warning) — skill-authoring's claim may
    be stale; backlog item, verify before acting.
  - Scorer side: criterion slots in after skill_routing.py L87 (tier2, reuses
    loaded_skills + expected.required_skills); new text extractor needed in
    checkpoint_adherence.py (text blocks only — auto-excludes thinking/tool_use;
    verified against real transcript); cases.jsonl soft_requirements edits are
    cosmetic-but-recommended (scorer hardcodes criteria); NO rescore tooling
    exists — new `rescore_skill_routing.py` (~80-120 lines) must rewrite per-run
    result.json criteria + regenerate summary.json; viewer needs no code change
    (dynamic criterion collection). Matcher: case-insensitive, hyphen↔space
    variants, sklearn alias decision pending, code-span/path mentions count.
- Checkpoint 1 (scope confirmation) presented to user — awaiting approval.
- **Checkpoint 1 APPROVED** with all three design calls: (1) reference-header
  sweep YES, (2) sklearn alias YES, (3) over-limit descriptions deferred to a
  user-run separate fix. Additional user directive: **ignore context-utilization
  gates this session** (orchestrator + all subagents; user is empirically
  testing the new model's degradation limits before updating docs).
- **Phase 3 implementation COMPLETE (2 parallel framework-engineer dispatches):**
  - *Routing fix* (9 files, 24 edits): data-scientist SKILL.md — frontmatter
    description final sentence replaced ("Load the routed tool-specific skill
    before giving tool-specific advice or writing code — library skills encode
    environment constraints and curated caveats absent from general knowledge"),
    body lines 12/14/207 recast, new rationale paragraph after routing tree
    ("THEN-load steps apply to advisory and brainstorming turns as much as
    implementation"), 7 THEN-load qualifiers de-qualified; 12 header lines
    reworded across 7 reference files; ad-hoc-collaboration-mode.md 5 passages
    fixed (97 load-first precondition + data-lookup-style fallback, 132, 135,
    160, 324). SM6 verify-only sweep: 9/9 sites PASS, no enumeration changes.
    "For implementation syntax" → 0 matches under data-scientist/. Engineer
    flagged 11 residual lowercase/embedded "implementation syntax" lines
    (outside approved sweep) for an optional follow-up.
  - *Scorer* (3 modified + 1 new): `required_skills_engaged` tier2 criterion in
    skill_routing.py (+ SKILL_MENTION_ALIASES sklearn map);
    `extract_new_assistant_text()` in checkpoint_adherence.py; cases.jsonl 15×
    soft_requirements; NEW `scripts/rescore_skill_routing.py` (merge semantics
    retain legacy criteria; built-in determinism check). Rescore applied to all
    5 Phase 4 sets: **determinism PASS (225/225 runs, all pre-existing criteria
    identical)**. Headline: engaged 136/225 (60.4%) vs loaded 18/225 (8.0%).
    Per-model engaged: Nemotron 14/15, Gemini 3.1 Pro 12/15, Opus 4.8 12/15,
    Fable 9/15, Sonnet 9/15, Opus 4.5 9/15, Haiku 6/15, Gemma 31B 3/15.
    all_criteria provably invariant (superset criterion). Viewer regenerated:
    `viewer_2026-06-10f.html`. Anomaly resolved: transcript-review mention
    counts (~12-14/15 Fable) overestimated vs deterministic matcher (9/15) —
    engineer verified failing runs have genuinely no required-skill name in
    text or thinking; review likely counted any library naming loosely.
  - Docs registered (orchestrator-direct): README § 6 criteria paragraph;
    PHASE4_SKILL_ROUTING_PLAN.md status line + § 3.1 table/soft set + § 4
    schema + § 9 decision 7 (incl. before/after-fix comparability note).
- **3-angle review COMPLETE: 0 blockers.** Consistency: 6 minor findings; all
  rescore numbers independently re-derived from summary.json (136/225 engaged,
  18/225 loaded — exact match); SM6 9/9 sites in sync; legacy-criterion
  retention verified. Quality: matcher empirically probed (16 test strings, all
  correct incl. sklearn alias, svy≠survey, plotly≠plotnine); merge semantics +
  summary fidelity traced clean; 8 minors. Completeness: no orphans/missing
  registrations; manifests structurally immune to criterion drift; found a
  pre-existing latent bug (`state_md_updated` in checkpoint_adherence.py:265-269
  can never pass — Write/Edit calls carry empty file_path) → BACKLOG.
- **Review fix pass COMPLETE** (framework-engineer #3 + orchestrator-direct):
  - F1 supervised-ML branch → unconditional FIRST-read/THEN-load (was the last
    implementation-conditioned load in the tree; affects sr-08/sr-13).
  - **F2 (FLAGGED — one step beyond confirmed scope, needs user confirmation at
    Checkpoint 2):** daaf-orchestrator/SKILL.md:432 § Skill Loading Mechanics —
    added parenthetical noting Ad Hoc + Framework Development exceptions to
    "skills are loaded by subagents".
  - F3 three deferral-licensing header lines reworded (visualization-design/
    -execution, geospatial-analysis); F4 circular triggers fixed
    (exploratory-unsupervised, geospatial-operations); F5 see→load + modifier.
  - Engineer deviations (flagged): reviewer line numbers for F5 were off — fixed
    both the actual diff lines (188/230/354) AND the cited ones (202/302/399,
    +454) as all matched the pattern; supervised-ml.md:3 had the F4 circular
    defect but wasn't listed — fixed for consistency.
  - C1 scorer docstring (stale plan reference, order, split-block caveat);
    C2 rescore determinism check generalized (per-run computed new-criteria set
    — re-rescores now verify ALL criteria incl. engaged; future additions need
    no code edit), clean missing-summary.json error, ordering-drift note.
    py_compile clean; dry-run re-check on _031234: determinism PASS across all
    6 criteria.
  - Orchestrator-direct: README "sixth→former criterion" + engaged
    non-vacuousness note + § 3 scripts-row adds rescore_skill_routing.py
    (v1→v2 generator naming in that row left for viewer session); plan § 5
    preamble annotated (quotes = pre-fix baseline wording, sr-04 example);
    transcript-review postscript (loose mention counts superseded by
    deterministic matcher; directional findings stand).
- Checkpoint 2 presented — pending user approval (incl. F2 + deviations), then
  commit decision + post-fix spot-check batch.
- **Checkpoint 2 APPROVED** (F2 kept; deviations kept per orchestrator judgment).
- **Spot-check round 1 INVALID as a fix test — MAJOR METHOD FINDING (stale
  golden):** Sonnet+Haiku `results/20260610_144245` ($0.94) and Gemini Flash
  Lite+DeepSeek Flash `results/20260610_144524` ($0.44) showed ZERO movement
  (loaded 0-1/15; engaged 6-11/15 ≈ pre-fix). Root cause: the Phase 3 golden
  checkpoint embeds the PRE-FIX data-scientist SKILL.md and ad-hoc mode text in
  its tool_result payloads (grep-confirmed "For implementation syntax" + "this
  is permitted" present) — models replay stale routing text in-context; only
  the system-prompt description and runtime-read ref headers were fresh.
  **Both sets RETAINED as the stale-checkpoint control condition** — they
  isolate the fresh-surfaces-only effect (≈ zero): in-context text dominates
  on-disk edits. First model key attempt also corrected (registry keys are
  sonnet-46/haiku-45, not name-derived sonnet/haiku — restart-prompt rule was
  wrong; failed fast, $0).
- **Remediation (framework-engineer #5):** NEW
  `scripts/refresh_golden_checkpoint.py` (deterministic content-refresh:
  re-reads files behind Skill/Read tool results, splices current content,
  preserves all else byte-for-byte; --dry-run; validated against pre-fix git
  versions byte-for-byte). NEW golden
  `golden/skill_routing/ad_hoc_initialized.jsonl` (47 records; stale phrases 0;
  new norm + rationale + ad-hoc wording present). All 15 cases repointed;
  Phase 3 golden zero-diff (historical rescores resolve via manifests — still
  valid). **Serialization trap for future refreshes:** Skill bodies live in a
  SUBSEQUENT user record (tool_result is just "Launching skill: X"; frontmatter
  stripped from body); Read results are duplicated (numbered message.content +
  raw toolUseResult.file.content) — refresh BOTH or stale text survives
  (engineer's first pass caught this).
- Docs: README § 5 inventory split (Phase 3 vs new Phase 4 golden rows) +
  third regeneration mechanism + **"Golden staleness caveat"** paragraph
  (user-requested); plan § 2.1 superseded-note (incl. non-comparability across
  the golden swap).
- **Spot-check round 2 (fresh golden) COMPLETE — THE FIX WORKS:**
  - Sonnet+Haiku `results/20260610_153005` ($1.35, 1755s, 1 tool failure):
    Sonnet loaded 0→**6/15** (engaged 11/15, refs 1/15, order 3/15, Perfect
    1/15 = sr-03); Haiku loaded 2-pre→**5/15** (engaged 8/15).
  - Gemini Flash Lite+DeepSeek Flash `results/20260610_153417` ($0.59, 228s,
    0 failures): Gemini loaded 0→**4/15** (engaged 10/15); DeepSeek loaded
    1→**7/15** (engaged 12/15, **Perfect 2/15** = sr-13, sr-14).
  - Cross-tier replication: every model moved off the loaded floor;
    `no_forbidden_skills` 15/15 everywhere (no over-loading side effect).
    Strong cases: sr-03/04/05/10/14 (+sr-13 DeepSeek). Persistent holdouts
    cluster in viz/spatial/ML (sr-08/09/11/12/15 + sr-01/06/07 mixed).
  - **Bottleneck shifted one hop deeper:** models now load the library skill
    but skip its required reference reads (`required_refs_read` 0-2/15) —
    third-hop decay (hub ref → skill load → library ref) is the next
    framework-improvement target.
  - 3 tool failures across rounds all = Haiku inventing skill names from hub
    ref basenames ("Unknown skill: geospatial-analysis/supervised-ml/
    exploratory-unsupervised") — scoring-relevant behavior, retained.
  - Artifact sweep (search-agent, python3): all 4 new sets **CLEAN** (0
    errors/timeouts; all pattern hits false positives — line-number 429s,
    UUIDs, "Overloaded charts"/"quotable" prose). Sweep tip recorded: anchor
    future sweeps on `"status":429`/`rate_limit_error` event types, not bare
    /429/.
  - v1 viewer regenerated post-round-2: `viewer_2026-06-10i.html` (13.27 MB,
    49 sets incl. all 4 spot-check sets).

## Restart Prompt (Session 5: complete baseline matrix on fresh golden + wrap)

> Launch framework development mode. Phase 4 skill_routing session at
> /daaf/benchmarks. Read in order: (1) PHASE4_SKILL_ROUTING_PLAN.md (note § 2.1
> superseded-block + § 9 decision 7), (2) this file's Phase 4 block Sessions
> 1-4, (3) PHASE4_ROUTING_FIX_SCOPING_20260610.md if editing routing text.
> COMPLETE: routing-norm framework fix (data-scientist + ad-hoc mode, 3-angle
> reviewed); `required_skills_engaged` tier-2 criterion + rescore tool (5 sets
> rescored, determinism PASS); golden staleness discovery (README § 5 caveat);
> refresh_golden_checkpoint.py + fresh golden golden/skill_routing/
> ad_hoc_initialized.jsonl (cases repointed; Phase 3 golden untouched);
> spot-checks: stale-golden control (loaded 0-1/15) vs fresh golden (Sonnet
> 6/15, Haiku 5/15, DeepSeek Flash 7/15, Gemini FL 4/15) — fix verified.
> COMMITTED: `24eee70` (framework routing fix, 13 files) + `3a2cf26`
> (benchmarks: criterion + rescore + refresh tools + golden + docs; README
> §§ 3/5/6 staged via filtered patch — first 5 hunks only). SESSION_NOTES
> remains uncommitted (shared file — owners commit their own blocks).
> REMAINING: (a) full baseline matrix re-run
> against fresh golden (all models; Opus 4.6/4.7 still 0 reps; registry keys:
> haiku-45, sonnet-46, opus-45..48, fable-5, NOT name-derived), (c)
> PHASE4_TOKENS recalibration from Anthropic actuals, (d) Gemma 4 31B 0-turn
> venice-stall rerun/exclude decision, (e) optional: third-hop refs fix +
> residual lowercase "implementation syntax" sweep, state_md_updated latent
> bug (checkpoint_adherence.py:265), over-limit skill descriptions
> (user-owned). Pre-fix result sets (≤20260610_144524) are NOT comparable to
> fresh-golden sets (framework + checkpoint both changed). Sequential mode for
> Anthropic; --delay is parallel-only; python3 (not rg) for results/.

## Session 5 (2026-06-10, ~16:00 UTC–) — Cleanup + golden percolation + third-hop fix

- **User decisions:** (1) remove ALL stale Phase 4 sets including the two
  stale-golden controls (`_144245`/`_144524` — finding stays documented in
  README § 5 + Session 4 notes); (2) **refresh the Phase 3 golden in place**
  so future Phase 3 runs test the current framework — comparability break
  with the existing Phase 3 corpus ACCEPTED, log but don't worry; (3) bundle
  the third-hop refs fix + 8 residual "implementation syntax" lines into one
  dispatch before the baseline batch; (4) over-limit skill descriptions:
  COMPLETED in a separate strand — dropped from backlog.
- **7 sets ARCHIVED** to `results_archive/phase4_stale_pre_fresh_golden/`
  (`_022333 _031234 _032805 _040700 _041451 _144245 _144524`) — user deletes
  manually (rm denied at permission prompt; mv chosen). `.gitignore` +
  `results_archive/`. PHASE4_TOKENS recalibration deliberately deferred to
  post-fix fresh-golden data (pre-fix 1-turn runs would understate tokens).
- **Golden percolation inventory (user's core concern):** Phase 1 cold-start,
  no golden. Phase 4 golden fresh (but needs RE-refresh after the bundled
  fix — embeds data-scientist SKILL.md). Phase 3 golden stale (both pre-fix
  phrases grep-confirmed). 9× post_confirmation goldens +
  `ad_hoc/after_confirmation.jsonl` embed pre-F2 daaf-orchestrator body ONLY
  (no data-scientist body) — sweep-refresh planned for consistent policy.
  **NEW staleness channel:** `bootstrap_template.jsonl` line 5 is an
  `attachment` record carrying the skill LISTING with the pre-fix
  data-scientist frontmatter description; refresh tool handles only Skill
  bodies + Read results — needs an attachment handler extension (bootstrap is
  generate_goldens.py's seed; never replayed in runs, but future generated
  goldens inherit its listing).
- `state_md_updated` bug confirmed: checkpoint_adherence.py:62 fills
  file_path only for Read → line 267 Write/Edit check can never pass.
  Fix queued (+ survey which datasets set it; rescore assessment).
- **Bundled text fix COMPLETE** (framework-engineer #1, 15 files): identical
  third-hop norm paragraph in all 11 library SKILL.md files ("reference-file
  routing... applies to advisory and brainstorming turns as much as
  implementation") + hub extension sentence (data-scientist SKILL.md:193
  "The norm extends one hop further...") + 8 residual lines de-qualified.
  Grep: 0 case-insensitive "implementation syntax" under data-scientist/.
- **Golden refresh sweep COMPLETE** (framework-engineer #2): ALL 13 goldens
  refreshed (2× ad_hoc_initialized, 9× post_confirmation,
  ad_hoc/after_confirmation, bootstrap_template). refresh_golden_checkpoint.py
  extended with serialization #4 (skill_listing attachments — DISCOVERY: every
  golden, not just bootstrap, embeds the listing at line 5; the Phase 3 stale
  "For implementation syntax" hit lived there). Older goldens also carried
  ~250-char-cap-truncated listing descriptions — refresh normalizes to full
  current descriptions (+~6.3 KB/golden). In-place via tmp+copy-back (inode/
  mode preserved); idempotency verified. README § 5 caveat extended.
- **state_md_updated fix COMPLETE, blast radius ZERO:** no cases.jsonl ever
  set the criterion — fully latent, no rescore. file_path now populated for
  Read/Write/Edit/NotebookEdit (incl. notebook_path fallback).
- **3-angle review COMPLETE: 0 blockers.** All fixes applied orchestrator-
  direct: README §§ 3/5 (refresh tool in scripts row; "(since archived)"
  clauses at the two control-set mentions; attachment clause in Regeneration
  bullet); cost_estimator.py:74 provenance annotated (archived set;
  recalibrate from fresh-golden Anthropic actuals); rescore_skill_routing.py
  examples → live set IDs; reparse guard added to rebuild_skill_listing
  (dry-run verified); science-communication norm adapted ("drafting the
  deliverable"/"audience-tested frameworks" — now 10 verbatim-identical + 1
  deliberate variant; core greppable sentence identical in all 11).
  py_compile clean ×4.
- **Accepted residuals:** descriptive-analysis.md:563 keeps "advising or
  coding" (matches its own line 571 from 24eee70 — file-local consistency
  over cross-file formula); SKILL.md:353 "Tool-specific syntax" branch label
  (quality reviewer: fine unless transcripts show exploitation).
- **AUDIT-TRAIL NOTE (completeness reviewer):** live sets `_153005`/`_153417`
  pin manifest daaf_git_sha `f1d7885`, which PREDATES the skill_routing
  golden's first commit (`3a2cf26`) — they ran against the worktree golden
  (= the `3a2cf26` version, 47 records). Rescoring still works (line-count
  slicing unchanged). Manifests pin SHA only, no golden content hash —
  potential future improvement.
- v1 viewer regenerated post-archive: `viewer_2026-06-10l.html` (44 sets,
  1,788 runs, $273.05; Phase 4 = the two fresh-golden sets only).
- Plan §§ 2.1/9 annotated (sets archived; Phase 3 golden also refreshed).
- **NOT COMMITTED:** all Session 5 changes are working-tree only (skills,
  goldens, scripts, README §§ 3/5, .gitignore, plan, this file). Commit
  needs hunk-ownership care: README also carries hygiene (§§ 9/11/12) and
  viewer (§ 8) session hunks.

## Restart Prompt (Session 6: full baseline on fresh goldens)

> Launch framework development mode. Phase 4 skill_routing session at
> /daaf/benchmarks. Read: (1) PHASE4_SKILL_ROUTING_PLAN.md, (2) this file's
> Phase 4 block Sessions 4-5. Session 5 COMPLETE: third-hop norm in 11
> library skills + hub; ALL 13 goldens refreshed (incl. skill_listing
> attachments — serialization #4 in refresh_golden_checkpoint.py); Phase 3
> golden refreshed in place (comparability break logged, README § 5);
> state_md_updated fixed (zero blast radius); 7 stale Phase 4 sets archived
> to results_archive/ (user deletes); 3-angle review clean, fixes applied;
> viewer_2026-06-10l.html current. UNCOMMITTED: everything above — commit
> first (README hunk-ownership check: hygiene owns §§ 9/11/12, viewer § 8).
> REMAINING: (a) commit Session 5 work; (b) full baseline matrix vs fresh
> goldens — all models, registry keys haiku-45/sonnet-46/opus-45..48/fable-5
> + OpenRouter keys, Anthropic sequential, --timeout 300, third-hop fix means
> required_refs_read is the metric to watch; (c) PHASE4_TOKENS recalibration
> from that batch's Anthropic actuals (cost_estimator.py:74 note); (d) Gemma
> 4 31B venice-stall: rerun on fresh golden or exclude; (e) optional: golden
> content hash in manifests; SKILL.md:353 label. Two prior fresh-golden sets
> (`_153005`/`_153417`) predate the listing refresh + third-hop fix — treat
> as intermediate, superseded by the new baseline. python3 (not rg) for
> results/; SESSION_NOTES/README shared — additive edits, re-read first.
> POST-CHECKPOINT-2 UPDATE: Session 5 work COMMITTED as `31d1070` (35 files;
> README §§ 3/5 hunks staged via filtered patch — parallel hunks at lines
> 384+ left for their owners; SESSION_NOTES stays uncommitted by convention).
> The two pre-third-hop spot-check sets `_153005`/`_153417` ARCHIVED to
> results_archive/phase4_pre_thirdhop_spotchecks/ (user deletes; results/ now
> has zero Phase 4 sets — the Session 6 baseline starts clean). Item (a) of
> REMAINING is done; viewer regen will be needed again after the baseline.

## Session 6 (2026-06-10, ~18:00 UTC–) — Criteria audit + hard/soft rebalance + corpus rescore

- **Session pivot (user direction):** before the baseline matrix, audit ALL
  phases' criteria for superfluous (always-pass) entries and wrong hard/soft
  bucketing. Empirical sweep of all 42 then-live sets (python3, per-criterion
  pass rates) + scorer/case/viewer code trace.
- **Audit findings:** (1) hard/soft resolved inconsistently — Phase 1 via
  viewer fallback to case `hard_requirements` (runner emits no tier), Phases
  2/3/4 scorer-stamped tier wins (case lists decorative); (2)
  `scorers/deterministic/mode_classification.py` was DEAD code — the runner
  scores inline (orchestrator_skill_loaded etc.); its `reasoning_present` was
  declared in all 15 cases but never scored in any result; (3) Phase 3b
  always-pass nest: transcript_found 417/417, active 417/417, tool_summary
  417/417, no_code_execution 163/163; (4) viewer `allCriteriaPassed`/
  `groupAllPassed` count info-tier toward Perfect (the "JS can ignore" comment
  was only honored for hard/soft rates); (5) Phase 4 `expected_refs_read`
  vacuous-passed in 10/15 cases (empty list → auto-pass).
- **User decisions (all approved):** Phase 1 — orchestrator_skill_loaded →
  HARD, confirmation_gate_present → SOFT, reasoning_present removed, dead
  module deleted; Phase 2 — pc-07 skill-authoring + agent-authoring (newly
  expected) both SOFT via new `skills_loaded_soft` field; pc-04 data-scientist
  stays HARD; Phase 3a unchanged; Phase 3b — REMOVE transcript_found, active,
  tool_summary, no_code_execution (not info-demote — info counts toward
  Perfect); keep reads_target_script hard + behavior_defined (failure-only
  tripwire); Phase 4 — expected_refs_read OMITTED when expected_refs empty;
  case-lists-as-authority principle adopted (scorers derive tiers from case
  expected fields); rescore the historical corpus to keep it comparable.
- **Implementation (framework-engineer #1, 8 modified + 1 deleted):** both
  cases.jsonl files; checkpoint_adherence.py skills_loaded_soft (tier2);
  subagent_behavior.py pruned (missing transcript now returns []);
  skill_routing.py omission; mode_classification.py deleted — DEVIATION: its
  MODE_KEYWORDS/CONFIRMATION_PATTERNS were load-bearing imports of
  run_mode_classification.py, relocated verbatim into the runner first;
  archive/runner.py:47 lazy-import left as-is (documented legacy); README
  §§ 2/3-row/6 + plan § 3.1 amended. Smoke-validated against archived runs.
- **Rescore (framework-engineer #2, NEW scripts/rescore_criteria_overhaul.py):**
  all 8 post_confirmation + 24 dispatch_compliance sets rescored in place
  ($0, local). pc-07: 48/50 runs rescored (2 lack archived transcripts),
  skill_skill_authoring retiered tier2, NEW skill_agent_authoring 35/48 FAIL
  (only Sonnet 4.6 + Gemini 3.1 Pro 3/3 pass) → 23 historical Perfect flips
  True→False (logged comparability note). Phase 3b: 417 runs stripped via
  explicit denylist, retained criteria cross-checked by re-scoring archived
  subagents/ — 0 mismatches, 0 Perfect changes (verified empirically).
  Determinism gate PASS on all pre-existing criteria. Phase 1 needs no
  rescore (tier flips are viewer-derived from case lists — retroactive for
  free). WARNING surfaced: 5 sets have post-archival pruned run dirs
  (`20260608_221438` pc 135→128; dc `_005021`/`_134443`/`_160029`/`_180411`
  36→34/32/33/33) — summaries now reflect disk (disk = source of truth).
- **Parallel-actor discovery:** results/20260610_184022 — a skill_routing
  OpenRouter batch (glm-51, kimi-k26, deepseek-v4-pro, gemini-31-pro,
  deepseek-v4-flash × 15, parallel, 20s delay, timeout 300) launched by
  another actor (not this session) against HEAD 9d2b1ed — valid as the
  baseline's OpenRouter half (partial: 5 of 10 keys). Archived ATOMICALLY at
  18:40:22 (all 75 result.json same mtime); viewer m (18:44:29) embedded it
  in full — an earlier "mid-flight 45/75" note here was an orchestrator
  arithmetic error, corrected per consistency review. CRITICAL CATCH
  (quality review): the batch's runner process imported the PRE-overhaul
  scorer (launched before 18:23), so its 50 empty-expected_refs runs carried
  legacy vacuous expected_refs_read auto-passes.
- **3-angle review COMPLETE: 1 critical (the stale-import catch above),
  4 minor, 4 info; overhaul itself clean.** Fix pass (framework-engineer #3,
  8 files): rescore_skill_routing.py gained a narrow expected_refs_read
  strip (current-cases-empty AND scorer-omitted; other legacy criteria still
  retained) → executed on _184022: 50 stripped, 25 real kept, determinism
  PASS, summary tally 60/75→10/25, idempotent; rescore_criteria_overhaul.py
  no-transcript path now applies transcript-independent retiers → the 2
  timed-out Fable pc-07 stragglers relabeled (corpus-wide tier1
  skill_skill_authoring now ZERO; 0 pass/fail changes);
  checkpoint_adherence.py collision guard (skills_loaded ∩ soft →
  ValueError); run_dispatch_compliance.py missing-transcript WARNING +
  non-criterion subagent_transcript_missing field; run_post_confirmation.py
  docstring + console soft-skills print; README § 3 row + § 10 dated
  supersession sentence; sr cases.jsonl hygiene — 10 empty-expected_refs
  cases drop expected_refs_read from soft_requirements and the empty field
  (absence verified safe); plan § 4 dated note.
  viewer_2026-06-10n.html regenerated (v1).
- **Viewer convention corrected (user direction): v2 is the live viewer.**
  No viewer CODE was edited this session (either version; verified via git
  status by every dispatch + reviewer audit — v2 shares the tier logic
  verbatim and is fully data-driven, so it inherited the rebalance/rescore
  automatically). The v1 regens (m, n) were stale Session 4-5 convention —
  superseded artifacts, deletable. CURRENT: **viewer_2026-06-10o.html**
  (v2; 43 sets, 1,803 runs, 17 models; weakest criterion now
  skill_agent_authoring 13/48 = 27% — rescore confirmed flowing through v2).
  Both generators share the viewer_YYYY-MM-DD{letter}.html auto-increment
  namespace. Future regens: use generate_results_viewer_v2.py.
- **Accepted residuals:** 2 transcript-less Fable pc-07 runs lack
  skill_agent_authoring (correct — no evidence to score); rescore NOTICE
  path for the 5 post-archival-pruned-run-dir sets validates only
  count-reconciling summary blocks (certified by 27 strict-pass sets);
  retier gate checks passed+tier but not detail text (cosmetic).
- Checkpoint 2 presented to user — commit decision + baseline remainder
  (5 OpenRouter keys + 7 Anthropic models) pending.

## Restart Prompt (Session 7: commit + finish baseline matrix)

> Launch framework development mode. Phase 4 skill_routing session at
> /daaf/benchmarks. Read: (1) PHASE4_SKILL_ROUTING_PLAN.md, (2) this file's
> Phase 4 block Sessions 5-6. Session 6 COMPLETE: criteria audit + hard/soft
> rebalance (Phase 1 orchestrator_skill_loaded→hard via case lists,
> confirmation_gate_present→soft, reasoning_present removed, dead scorer
> module deleted w/ constants relocated into runner; pc-07 skill-authoring +
> agent-authoring both soft via new skills_loaded_soft field, pc-04
> data-scientist stays hard; Phase 3b removed transcript_found/active/
> tool_summary/no_code_execution — info tier counts toward viewer Perfect,
> hence removal not demotion; Phase 4 expected_refs_read omitted when no
> expected_refs, 10 sr cases cleaned). Corpus RESCORED in place ($0): 8 pc +
> 24 dc sets via NEW scripts/rescore_criteria_overhaul.py (pc-07: 35/48 fail
> new skill_agent_authoring → 23 historical Perfect flips, logged); sr set
> 20260610_184022 (parallel-actor OpenRouter batch: glm-51/kimi-k26/
> deepseek-v4-pro/gemini-31-pro/deepseek-v4-flash, scored by stale pre-edit
> import) normalized via targeted strip in rescore_skill_routing.py (50
> vacuous entries gone). 3-angle review + fix pass clean. Viewer: v2 is the
> live viewer per user — viewer_2026-06-10o.html current (43 sets/1,803
> runs); v1 artifacts m/n superseded (deletable); regen via
> generate_results_viewer_v2.py only. UNCOMMITTED: all
> Session 6 work — commit first (README hunk-ownership: hygiene §§ 9/11/12,
> viewer § 8 + VIEWER_REDESIGN_PLAN.md; this session owns §§ 2/3/6/10 hunks;
> SESSION_NOTES stays uncommitted by convention). REMAINING: (a) baseline
> matrix remainder — OpenRouter: qwen-36-27b, gemma-4-26b, nemotron-3-ultra,
> gemini-31-flash-lite (+ gemma-4-31b rerun/exclude decision); Anthropic
> sequential: haiku-45, sonnet-46, opus-45, opus-46, opus-47, opus-48,
> fable-5; --timeout 300; required_refs_read is the metric to watch
> (third-hop fix); (b) PHASE4_TOKENS recalibration from the Anthropic
> actuals (cost_estimator.py:74); (c) viewer regen post-batch; (d) optional:
> golden content hash in manifests, SKILL.md:353 label. python3 (not rg) for
> results/; SESSION_NOTES/README shared — additive edits, re-read first.
> POST-CHECKPOINT-2 UPDATE: Session 6 work COMMITTED as `0d7ed02` (14 files;
> README's 7 session-owned hunks — old-lines 52/82/146/151/288/305/453, §§
> 2/3/6/10 — staged via filtered patch; § 8 hunks left for viewer session
> [which has already documented v2 as the maintained generator], §§ 9/11/12
> hunks left for hygiene; reproducibility-verification-mode.md +
> REPRODUCTION_REPORT_TEMPLATE.md are a parallel session's uncommitted work
> — untouched). Items remaining for Session 7 unchanged: baseline remainder
> (4-5 OpenRouter + 7 Anthropic), PHASE4_TOKENS recalibration, post-batch
> v2 viewer regen, optional golden-hash/SKILL.md:353.

## Session 6-parallel (2026-06-10, ~18:06 UTC–) — Baseline spot-check batches (the "parallel actor")

> **Identity note:** this session is the "parallel actor" discovered by the
> criteria-audit Session 6 above — it launched `results/20260610_184022`. The
> two sessions ran concurrently against this shared file; this block was
> written after reading Session 6's, and accepts its normalizations.

- **User scope for this session:** spot-check baselines, not the full matrix —
  5 good OpenRouter models in parallel (delay=20), then an Anthropic spread
  (Haiku, Sonnet, Opus 4.6, Fable 5) sequential. 1 rep each. Nemotron swapped
  out for DeepSeek Flash at user direction.
- **Batch 1 — OpenRouter (`results/20260610_184022`):** glm-51, kimi-k26,
  deepseek-v4-pro, gemini-31-pro, deepseek-v4-flash × 15 cases, parallel
  delay=20s, timeout 300. 75 runs, $11.86 actual (est $6.65 — post-fix runs
  now do real tool work; estimator UNDERSTATES OpenRouter, inverse of the old
  caveat), 1,688s wall. Sweep CLEAN (75 transcripts; 0 rate-limit events;
  1 scored-on-timeout: DeepSeek Pro sr-13 all-criteria pass; 2 tool failures
  = Gemini AskUserQuestion stalls on sr-08). Scored by the stale pre-overhaul
  scorer import — subsequently normalized by Session 6's targeted strip
  (50 vacuous expected_refs_read entries removed; accepted).
  Per-model loaded/engaged/refs_read/all: DeepSeek Pro 11/13/9/**6**,
  Gemini 3.1 Pro 13/14/5/**4**, DeepSeek Flash 9/10/4/**3**, GLM 5.1
  6/12/7/**2**, Kimi K2.6 6/12/2/**1** (each /15).
- **Batch 2 — Anthropic (`results/20260610_194256`):** haiku-45, sonnet-46,
  opus-46 (first-ever Phase 4 reps), fable-5 × 15, sequential, timeout 300.
  60 runs, $9.58, 3,686s wall, 0 errors/timeouts. Launched 18:41 — imported
  the POST-overhaul scorer, so expected_refs_read scored on the 5 real cases
  only (natively consistent with the rescored Batch 1). Sweep CLEAN
  (0 rate-limit; 2 tool failures = Haiku's known invented-skill-name pattern:
  "geospatial-analysis", "supervised-ml").
  Per-model loaded/engaged/refs_read/order/all (each /15):
  **Fable 5 15/15/14/14/13** — near-ceiling, by far the strongest run of the
  entire Phase 4 corpus; Opus 4.6 8/10/7/8/**6**; Sonnet 4.6 6/10/6/7/**5**;
  Haiku 4.5 8/9/**0**/1/**0** (loads skills but never reads library refs —
  pure third-hop failure).
- **Cross-batch headline (fresh goldens + third-hop fix):** aggregate
  required_skills_loaded 45/75 OpenRouter + 37/60 Anthropic ≈ 61% (pre-fix
  era: 8%); required_refs_read 27/75 + 27/60 ≈ 40% (pre-third-hop
  spot-checks: 0-13%). Engaged-vs-loaded gap nearly closed for strong models.
  Persistent holdout cases across both batches: sr-08/09/11/13 (viz/spatial/
  ML branches — models absorb the hub FIRST-read pair, then answer without
  the library load); sr-14 remains easiest; first no_forbidden_skills
  failure recorded (DeepSeek Pro loaded pyfixest on sr-02), 134/135
  otherwise.
- v2 viewer regenerated post-Batch-2: **viewer_2026-06-10p.html** (45 sets,
  1,878 runs). My earlier `viewer_2026-06-10m.html` (v1) was a stale-convention
  regen made before reading Session 6's block — superseded (deletable, like n).
- **Amendment to Session 7 restart prompt above:** its "baseline remainder"
  list predates this session's batches. Now COVERED: glm-51, kimi-k26,
  deepseek-v4-pro, gemini-31-pro, deepseek-v4-flash, haiku-45, sonnet-46,
  opus-46, fable-5 (1 rep each, current framework + fresh goldens). STILL
  0 reps: qwen-36-27b, gemma-4-26b, nemotron-3-ultra, gemini-31-flash-lite,
  opus-45, opus-47, opus-48 (+ gemma-4-31b rerun/exclude decision).
  PHASE4_TOKENS recalibration can now use Batch 2 Anthropic actuals
  (avg$/run: Haiku $0.020, Sonnet $0.087, Opus 4.6 $0.107, Fable $0.425;
  cost_estimator.py:74 note) — decision pending with user.
- SESSION_NOTES stays uncommitted by convention; this session committed
  nothing (runs + viewer regen only, both gitignored/untracked artifacts).

## AI Disclosure (Phase 4 session)

This session used DAAF in Framework Development mode. DAAF contributed to: skill routing
directive extraction, benchmark mechanics verification, test suite design, plan
authoring, transcript failure review, routing-fix scoping, and implementation via
specialist dispatch. The researcher set the test-suite concept, selected all design
options, approved the plan, and directed the recalibration strategy.
