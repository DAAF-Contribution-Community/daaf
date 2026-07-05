# Session Notes: Framework Development — Statusline (context-bar) Upgrade

**Started:** 2026-07-05
**Workspace:** /daaf/research/2026-07-05_FrameworkDev_StatuslineUpgrade
**Work Type:** Modify Existing (`.claude/scripts/context-bar.sh` + `.claude/settings.json` statusline config; possible new companion script)

## Accomplishments

- Phase 1 scoping complete: 3 parallel read-only explorations (payload/subagent-reactivity, community UX patterns, DAAF integration landscape)
- Full findings persisted to `preliminary_notes/`:
  - `2026-07-05_scoping_statusline-payload-subagent-reactivity.md`
  - `2026-07-05_scoping_community-statusline-ux-patterns.md`
  - `2026-07-05_scoping_daaf-integration-landscape.md`

## Key Decisions

- **Subagent-reactivity verdict (HIGH confidence, binary-verified on CC 2.1.187):** the main statusline CANNOT react to the currently viewed subagent — no focused-agent field exists in the payload. The native path for per-subagent display is the separate `subagentStatusLine` setting (agent-panel row bodies, receives `tasks` array with per-subagent id/name/type/status/tokenCount). Main-bar subagent visibility is possible only via filesystem scan of `<session>/subagents/agent-*.jsonl` (+ `.meta.json` for agentType) or hook-written caches.
- Hook-assisted option (modifying `context-reporter.sh`) touches `.claude/hooks/` — deny-ruled, requires explicit user permission; transcript-scan option avoids this.
- Awaiting Checkpoint 1 user selection of improvement scope.

## Integration Status

**Component:** `.claude/scripts/context-bar.sh` (modified), `.claude/scripts/subagent-bar.sh` (NEW), `.claude/settings.json` (subagentStatusLine block added)
**Checklist:** FRAMEWORK_INTEGRATION_CHECKLIST.md — § 5 H1b, H5 (adapted), CC2, CC3, CC6, CC7 all done per framework-engineer; § 6 N/A (in-container scripts)
**Phase 3:** COMPLETED (framework-engineer, 2026-07-05). Both scripts 100755 in git index. 9/9 test fixtures pass; minimal-payload output byte-identical to original; OpenRouter override verified end-to-end. Fixtures in `test_fixtures/`.
**Known follow-ups for review:** shellcheck unavailable in container (manual static pass requested); `rate_limits.*.resets_at` wire format not binary-verified (both epoch+ISO handled defensively)
**Constraints from scoping (must preserve):**
- Bare-integer format of `/tmp/claude-ctx-window-${session_id}` (consumed by context-reporter.sh)
- OpenRouter override block (lines 49-89) — logged design decision
- Transcript-parsing parity with context-reporter.sh (isSidechain/isApiErrorMessage filters, 3-field token sum)
- Fail-open behavior (no `set -e`), exit 0 on all paths
- Executable bit 100755 (`git update-index --chmod=+x` after edits)
- Fix stale `color-preview.sh` comment (line 4) while editing

## Phase 4 Review & Fixes (COMPLETE)

- 3-angle review (consistency/quality/completeness): 0 BLOCKERs. Warnings addressed by orchestrator post-Checkpoint-2 (user approved "apply all three" + CLAUDE.md rows):
  1. `now_epoch` integer guard added before countdown arithmetic (context-bar.sh ~line 246-256) — closes the only path that could leak a bash error into the bar
  2. Consolidated-jq comment corrected (`// empty` → `// ""` for cwd/transcript_path/model_id)
  3. Shebang harmonized to `#!/usr/bin/env bash`
  4. CLAUDE.md Defense-in-Depth table: two new Statusline rows (main bar + agent panel) — user explicitly approved CLAUDE.md edit
- All four fixes independently re-verified PASS (quality reviewer resumed via SendMessage, HIGH confidence)
- Reviewer note resolved: "changes already committed" was a misread — changes were staged, not committed. Nothing committed this session.
- Known theoretical residual (accepted): `rate_limits.*.resets_at` wire format not binary-verified; both epoch+ISO handled, garbage omitted gracefully. Confirm visually on a live Pro/Max session.

## Final State (superseded by "COMMITTED" below — kept for history)

- `.claude/scripts/subagent-bar.sh` — NEW (100755, staged)
- `.claude/scripts/context-bar.sh` — modified + polished (100755, staged)
- `.claude/settings.json` — subagentStatusLine block (unstaged)
- `/daaf/CLAUDE.md` — 2 Defense-in-Depth rows (unstaged)
- NOT committed — awaiting user's commit decision
- settings.json is read at startup: subagent panel rows appear after next session restart

## COMMITTED (2026-07-05, user-approved)

Commit `21be317` "feat(statusline): agent panel with per-model context windows" — 20 files: both scripts (subagent-bar.sh created 100755), settings.json, CLAUDE.md, this workspace (session notes, 3 scoping notes, 11 test fixtures, context-reporter.sh.proposed). Committed with explicit pathspecs to avoid sweeping in a parallel session's staged `scripts/host/backup_daaf.sh` / `restore_from_backup.sh` changes.

**Outstanding after commit:**
1. USER ACTION — install the hook fix: `cp /daaf/research/2026-07-05_FrameworkDev_StatuslineUpgrade/context-reporter.sh.proposed /daaf/.claude/hooks/context-reporter.sh` (takes effect immediately — hook scripts are executed fresh per invocation; only settings.json registration needs a restart). Until installed, CLAUDE.md's Context Reporting Hook row describes post-install behavior.
2. The upgrade-review checklist additions live in the still-untracked `research/2026-06-18_FrameworkDev_ClaudeCode_Upgrade/` folder — working tree only, to be committed with that workspace.
3. Confirm `rate_limits.*.resets_at` wire format visually on a live Pro/Max session (accepted residual from Phase 4).

## Iteration 2 (user adjustments after live use) — PARTIAL, session ended at HIGH context

User requested 4 adjustments after seeing the statusline live:
1. **DONE** — Effort level moved into the model segment: "Fable 5 (high)" (model_disp variable; standalone ⚙ segment and C_WARM color removed)
2. **DONE** — Removed "(lower session context use enhances performance)" from both ctx strings AND the plain_output length template (kept in sync)
3. **DONE** — Rate-limit segment now renders "Plan usage: 5h:42%(2h10m) 7d:13%(3d4h)": gray "Plan usage:" prefix; new `fmt_reset()` helper (epoch+ISO, now_epoch guarded, (NdNh) for ≥1 day else (NhNm)); countdown now shown for BOTH windows whenever resets_at parses (previously 5h-only at ≥70%); added rl_7d_reset to the consolidated jq (11 fields now)
4. **NOT DONE — needs fresh session** — subagent-bar.sh rows render wrong data. User observed: `◯ local_agent (running) · 37001 · 0 ░░░░░ 0%` — our 5-segment bar renders but tokens parse as 0, and identity shows generic "local_agent". The live payload schema clearly differs from the docs-derived assumption (id/name/type/status/tokenCount). TEMPORARY DIAGNOSTIC added to subagent-bar.sh (~line 61): dumps raw payload to `/tmp/claude-subagent-bar-last-payload.json` on every invocation. Not yet captured (no subagent ran after the edit).

Both scripts pass `bash -n`; both re-staged (index matches working tree). Iteration-2 changes NOT yet subagent-reviewed (deferred to next session's Phase 4 pass). Nothing committed.

## Iteration 2 completion (same session — user authorized continuing to 50% context)

Item 4 (subagent-bar rows) DIAGNOSED AND FIXED:
- Live payload captured to /tmp/claude-subagent-bar-last-payload.json via temporary diagnostic (since removed in the rewrite). Ground truth: task fields are id/type/name/status/description/label/startTime/tokenCount/tokenSamples/cwd; `name` ABSENT for anonymous Agent dispatches; type="local_agent" generically; top level includes session_id + transcript_path + columns.
- ROOT CAUSE: tab is IFS *whitespace* in bash — consecutive tabs collapse, so the empty `name` field shifted status/tokenCount left (tokens→0, "local_agent (running)" mislabel). FIX: records joined with ASCII unit separator via jq `join("")` + `IFS=$'\x1f'` (non-whitespace IFS preserves empty fields). Same latent bug fixed in context-bar.sh's consolidated read.
- subagent-bar.sh REWRITTEN: row = "{agentType} · {label≤40} · {Nk} {5-seg bar} {pct}%" (+"[status]" when != running); agentType resolved from subagents/agent-<id>.meta.json sidecar (fail-open); content REPLACES the entire native row (binary-verified {id,content} Zod contract); verified against the captured payload → renders "search-agent · Verify real subagentStatusLine schema · 95k ░░░░░ 9%".
- Binary investigation notes: status values running/pending/stopped/killed/failed; native fallback row = "name · description · tokenCount"; emitting nothing keeps native rendering.
- fmt_reset gained a ms-epoch guard (13+ digits → /1000).
- Verification: all 9 fixtures exit 0; cb_a/cb_c/cb_d/cb_e visual checks pass; 2-angle re-review (quality + consistency search-agents) — 9/9 invariants PASS, no BLOCKERs. Accepted LOW-severity notes: byte-slice label truncation with multibyte labels; set -u present in subagent-bar (matches context-reporter convention) but absent in context-bar; emoji byte-width inflation in plain_output max_len (pre-existing).
- Known tooling quirk (recurring Learning Signal): sandboxed `grep` via Bash returns empty in this container — use the Grep tool or Read instead.
- Both scripts staged, 100755, NOT committed.

## Iteration 3 (per-subagent model + accurate window) — COMPLETE (fresh session, 2026-07-05; see "Iteration 3 completion" below)

User confirmed: show each subagent's model in its panel row AND fix the window denominator (was using the session's 1M for all rows; a Sonnet subagent at 95k showed 9% instead of its true ~47%).

**VERIFIED FACTS (binary-extracted from CC 2.1.187, 2026-07-05; full agent return in this session's transcript):**
- CC provisions windows via `cai()`: `[1m]` suffix → 1M; natively-1M models (fable-5, mythos-5, opus-4-7, opus-4-8 on firstParty) → 1M; ALL OTHERS → 200,000 (`Fxt`), incl. sonnet-4-6 and haiku-4-5. `CLAUDE_CODE_MAX_CONTEXT_TOKENS` env overrides. Feature-flag `kelp_forest_sonnet` could raise sonnet (not observed).
- A `sonnet` subagent dispatched from this fable[1m] session gets **200k** (alias resolution appends no [1m]; `LNa` promotes only opus). Empirical corroboration: max observed subagent input tokens — sonnet 144,568 (<200k); opus-4-8 258,181 and fable 285,610 (>200k, proving native 1M).
- Auto-compact fires at ~window − outputReserve − 13,000 (≈182-187k for a 200k window).
- Subagent transcripts carry `.message.model` on assistant entries (bare id, [1m] stripped) — same source context-reporter.sh cache_model() uses.
- Models API (`client.models.retrieve` → `max_input_tokens`) reports the MODEL max (sonnet-4-6 = 1M!), NOT what CC provisions — wrong denominator; do not use it for this.

**DONE (staged? NO — working tree only, unstaged since last git add):**
- subagent-bar.sh: header comment notes model-from-transcript; top-level `session_model` read from `/tmp/claude-model-${session_id}` (read-only, cache written by context-reporter.sh). Both additive, no behavior change yet.

**REMAINING (fully specified — apply to subagent-bar.sh):**
1. In the render loop, after the `tokens` normalization and BEFORE `pct=$((tokens * 100 / max_context))`, insert:
   - Read task model: `task_model=$(tail -n 50 "${subagents_dir}/agent-${id}.jsonl" 2>/dev/null | jq -rs '[.[] | .message.model // empty] | last // empty' 2>/dev/null)` (guard subagents_dir/file existence; default "").
   - `row_window="$max_context"` (session window default — covers same-model subagents + alternative providers). If `task_model` non-empty AND != `session_model`: case-map — `*fable-5*|*mythos-5*|*opus-4-7*|*opus-4-8*|*\[1m\]*` → 1000000; else 200000. Then honor `CLAUDE_CODE_MAX_CONTEXT_TOKENS` if integer. Final integer guard → 200000.
   - Comment MUST carry provenance: "mapping verified against installed CC 2.1.187 binary, 2026-07-05; re-verify after Claude Code upgrades" (skill-information-awareness).
2. Change `pct` denominator from `max_context` to `row_window`. Leave `used_k` absolute thresholds untouched (window-independent by design).
3. Model display: `[[ -n "$task_model" ]] && agent_disp+=" (${task_model#claude-})"` before content assembly → rows like `search-agent (sonnet-4-6) · desc · 95k ██▄░░ 47%`.
4. Test: `bash subagent-bar.sh < /tmp/claude-subagent-bar-last-payload.json` (payload may need regenerating by dispatching any subagent) — expect sonnet task at 95k → 47% ELEVATED amber. Run sb_* fixtures + garbage (exit 0). `bash -n`. `git add` both scripts (context-bar.sh also has unstaged iteration-2 polish? NO — context-bar.sh staged current as of iteration-2 end; only subagent-bar.sh diverges).
5. 2-angle review (fresh search-agents; prior reviewer transcripts likely archived), SESSION_NOTES update, checkpoint, offer commit of the whole statusline upgrade.
6. Follow-up recommendation to surface at checkpoint: context-reporter.sh has the SAME session-window assumption for subagent measurements (hook = ask-first territory); and add "re-verify model→window mapping" to the CC upgrade-review checklist.

## Iteration 3 completion (fresh session, 2026-07-05)

All 6 REMAINING items executed exactly as specified:
- subagent-bar.sh render loop: `task_model` read via `tail -n 50 agent-<id>.jsonl | jq -rs '[.[] | .message.model // empty] | last // empty'` (existence-guarded, default ""); `row_window` defaults to session `max_context`, remapped only when task_model non-empty AND != session_model (case-map `*fable-5*|*mythos-5*|*opus-4-7*|*opus-4-8*|*\[1m\]*` → 1000000, else 200000; `CLAUDE_CODE_MAX_CONTEXT_TOKENS` integer override honored in-branch; final positive-integer guard → 200000). Provenance comment in place ("verified against installed CC 2.1.187 binary, 2026-07-05; re-verify after Claude Code upgrades").
- `pct` denominator switched `max_context` → `row_window`; `used_k` absolute thresholds untouched (window-independent by design).
- Model display: `agent_disp+=" (${task_model#claude-})"` when task_model non-empty.
- Verification: `bash -n` clean; captured live payload (sonnet-4-6 subagent at 95,121 tokens from this fable-5 1M session) renders `search-agent (sonnet-4-6) · Verify real subagentStatusLine schema · 95k ██░░░ 47%` in ELEVATED amber — exactly the predicted fix (was 9% NOMINAL green against 1M). All 9 run_exit_checks.sh checks exit 0. sb_a_varied visual check: transcript-less fixture tasks fall back to session window with no model suffix — byte-compatible behavior with iteration 2.
- 2-angle review (fresh search-agents, both HIGH confidence, 0 BLOCKERs):
  - Quality: 6 PASS, 1 WARNING (per-row `tail|jq` = 2 forks/row per ~300ms refresh; fine at DAAF-typical 1-4 concurrent agents; optional future optimization: cache model per subagent in `/tmp/claude-model-<session>-<id>` since a subagent's model never changes), 1 NOTE (model-read uses `last` vs cache_model()'s `head -1` — intentional, same `.message.model` source).
  - Consistency: all 6 checks PASS; cache read-only contracts intact; context-bar.sh invariants (OpenRouter block, bare-integer write, \x1f jq read, fail-open) untouched; thresholds identical across subagent-bar.sh and context-reporter.sh. Two doc NOTEs: (a) header lacked env-override mention — FIXED post-review (2-line header comment, re-`bash -n`, re-staged); (b) CLAUDE.md Defense-in-Depth agent-panel row now truthful-but-incomplete (no mention of per-row model display / per-model window) — deferred to user at checkpoint (CLAUDE.md = ask-first).
- Both scripts staged, 100755 in index, NOT committed. context-bar.sh unchanged this iteration (staged state from iteration 2 intact).

**Surfaced at checkpoint (follow-up recommendations, not yet actioned):**
1. context-reporter.sh has the SAME session-window assumption for subagent measurements — hook edit = ask-first territory.
2. Add "re-verify model→window mapping" to the CC upgrade-review checklist.
3. Optional: per-subagent model cache to eliminate repeated `tail|jq` forks (quality reviewer's WARNING).
4. Optional: extend CLAUDE.md agent-panel row wording for the two new features.

## Follow-ups executed (same session, user-approved: "go ahead with those follow-ups and then let's commit")

1. **context-reporter.sh per-subagent window correction — STAGED as `context-reporter.sh.proposed`, NOT installed.** Direct writes to `.claude/hooks/` are permission-denied (`Edit/Write(.claude/hooks/*)` deny rules), and the `cp` install attempt was denied at the permission prompt. The .proposed file (in this workspace) is fully verified: `bash -n` clean; diff vs live hook = exactly 2 comment updates + correction block + MAX_CONTEXT integer guard; smoke-tested live — subagent-fired call on the real sonnet transcript now reports "[ELEVATED]: 96k / 200k tokens (48%)" (was 9% NOMINAL against 1M), main-session path byte-identical in behavior, cache file written correctly. **INSTALL: `cp /daaf/research/2026-07-05_FrameworkDev_StatuslineUpgrade/context-reporter.sh.proposed /daaf/.claude/hooks/context-reporter.sh`** (user runs it, e.g. via `!` prefix; mode stays 100755 since cp preserves destination mode).
2. **Shared per-subagent model cache** `/tmp/claude-subagent-model-<session>-<id>`: written on first successful transcript read, read thereafter — eliminates the per-refresh `tail|jq` forks (quality reviewer's WARNING). Implemented identically in subagent-bar.sh (live) and the .proposed hook; either may write first; cache written only on non-empty read. Distinct prefix — nothing globs `claude-model-*` (verified: audit-log.sh, enforce-model-ceiling.sh use exact paths).
3. **CC upgrade-review checklist** (2026-07-02 addendum § 6): statusline item extended to cover the agent panel; new item "re-verify the model→window provisioning mapping" with the current mapping + provenance. NOTE: that addendum lives in the still-untracked 2026-06-18_FrameworkDev_ClaudeCode_Upgrade folder — edit is in the working tree, not part of the statusline commit.
4. **CLAUDE.md Defense-in-Depth rows** (user-approved): Context Reporting Hook row + Statusline (agent panel) row now describe per-model windows, model display, and the shared cache. The hook row describes post-install behavior — accurate once the .proposed is applied.

2-angle review of the follow-up delta (fresh search-agents, both HIGH confidence, 0 BLOCKERs): quality — all 6 checks PASS (set -u safety, 60s gate + no-parent-fallback guarantees untouched, main-session byte-equivalent, torn-write analysis: sub-PIPE_BUF atomic + identical values + non-empty guards = fail-open, MAX_CONTEXT guard strictly safer); consistency — contracts identical across scripts, CLAUDE.md rows accurate, namespace safe, live hook confirmed unchanged. Accepted notes: subagent-bar's "shared with context-reporter.sh" comment is forward-looking until the .proposed is installed.

## RESTART PROMPT (iteration 3 — COMPLETED; kept for history)

"Framework dev mode: resume the statusline upgrade at research/2026-07-05_FrameworkDev_StatuslineUpgrade/ — read SESSION_NOTES.md § Iteration 3 fully; execute its REMAINING list exactly (all facts pre-verified; do not re-investigate). Constraints: preserve \x1f field joining, fail-open/exit-0, read-only use of /tmp/claude-ctx-window-* and /tmp/claude-model-* caches, bare-integer cache contract, OpenRouter block in context-bar.sh."

## OLDER RESTART PROMPT (superseded — iteration 2 completed in-session; kept for history)

"Framework dev mode: resume the statusline upgrade at research/2026-07-05_FrameworkDev_StatuslineUpgrade/ — read SESSION_NOTES.md fully first. Remaining work: (a) diagnose and fix subagent-bar.sh row rendering — dispatch any small read-only subagent to make Claude Code invoke the script, then read /tmp/claude-subagent-bar-last-payload.json to learn the REAL tasks schema (observed symptom: tokens parse 0, identity shows 'local_agent'; likely different field names than id/name/type/status/tokenCount, and Claude Code natively prefixes rows with 'name (status) · tokens' so consider rendering only the bar+pct to avoid duplication); fix the jq extraction accordingly; then REMOVE the temporary diagnostic block (~line 61); (b) run the Phase 4 review pass over iteration-2 changes to context-bar.sh (effort-in-model, note removal, Plan-usage segment with fmt_reset) plus the subagent-bar fix; (c) checkpoint with the user, then offer to commit. Constraints: preserve bare-integer /tmp/claude-ctx-window-* write, OpenRouter block, transcript-parity filters, fail-open/exit-0. Scripts are staged, uncommitted, both 100755."

## AI Disclosure

This session used DAAF (Data Analyst Augmentation Framework) in Framework
Development mode. DAAF contributed to: framework state scoping (parallel
read-only exploration), online research of Claude Code statusline capabilities
and community patterns, and (pending) artifact authoring with integration
checklist execution and cross-file consistency review.
The researcher directed all framework design decisions and approved all changes.
