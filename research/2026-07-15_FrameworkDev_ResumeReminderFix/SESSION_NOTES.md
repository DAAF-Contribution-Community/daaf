# Session Notes: Framework Development — Resume Reminder Fix

**Started:** 2026-07-15
**Workspace:** /daaf/research/2026-07-15_FrameworkDev_ResumeReminderFix
**Work Type:** Modify Existing (two hook scripts)

## Problem

The orchestrator-loading reminder (`remind-orchestrator.sh`, UserPromptSubmit)
re-fires on the first prompt of every session resumed after a container
rebuild/restart, causing a redundant re-load of the daaf-orchestrator skill
(~10-15k tokens) into a context that already contains it.

## Root Cause (established with evidence)

- The "skill already loaded" flag lived at `/tmp/claude-daaf-orchestrator-<session_id>`.
- Session transcripts live in `~/.claude` (claude-config volume) and survive
  container rebuilds; `/tmp` does not. Observed: container PID 1 started
  2026-07-15 02:19:19; the burst of resumed-session reminders followed at
  02:20-02:23. (`uptime -s` is misleading in WSL2 — it reports host VM boot,
  not container start; `ps -o lstart= -p 1` gives container start.)
- Official Claude Code docs confirm plain `--resume`/`--continue` REUSES the
  original session_id (the `--fork-session` flag exists to opt out of reuse):
  https://code.claude.com/docs/en/cli-reference. So the flag-key logic was
  correct; only the flag's storage lifetime was wrong.
- Verified via activity.log: sessions 38ce9f1a/175671c6/506f6514/5ad10168
  each show two "Session started" entries with the SAME id (original + resume).

## Key Decisions

- **Fix chosen:** relocate the flag to `~/.claude/daaf-state/orchestrator-loaded-<session_id>`
  (user's proposal), rather than the alternative transcript-grep fallback.
  Persistent flag matches the lifetime of the fact being cached; simpler diff.
- **Scope expansion reviewed:** full inventory of `/tmp` hook state found six
  cache families; only the orchestrator flag caches a transcript-lifetime
  fact. The other five (claude-model-*, claude-ctx-window-*,
  claude-subagent-model-*, claude-ctx-ts-*, claude-or-models-*) are
  session-runtime facts that regenerate within seconds and BENEFIT from
  rebuild-wipe as free cache invalidation (e.g., a persisted model cache
  could serve a stale model to enforce-model-ceiling after the user changes
  ANTHROPIC_MODEL between rebuilds). Principle documented in hook headers:
  match cache storage to the lifetime of the fact it caches.
- **Pruning:** writer hook prunes flags older than 30 days (matches Claude
  Code default transcript retention, cleanupPeriodDays). Early prune is
  harmless (one extra reminder on next resume of that session).
- **No settings.json change needed** — same two hooks, same registrations.

## Accomplishments

- Drafted revised hooks (ShellCheck-clean, `shellcheck -x -S warning` passed):
  - `drafts/remind-orchestrator.sh` — flag path moved to daaf-state; header
    documents rationale + cache-lifetime placement principle
  - `drafts/flag-orchestrator-loaded.sh` — same path; mkdir -p; 30-day prune
- Functional tests executed against drafts (all passed):
  1. Simulated skill-load event → flag created in `~/.claude/daaf-state/` ✓
  2. Reminder suppressed when flag exists (no output) ✓
  3. Reminder fires when flag missing ✓
  4. 40-day-backdated flag pruned on next write; fresh flags retained ✓
  - Test flags removed after verification.

## In Progress

- COMPLETE: user deployed both hooks (2026-07-15 ~11:39 UTC); orchestrator
  verified byte-identical to drafts (empty diffs), git mode 100755 both, and
  live-session flags migrated to `~/.claude/daaf-state/` (4 flags present).
- COMPLETE: Phase 4 review — 2 subagents (Consistency + Completeness) both
  returned PROCEED with no blockers. Minor items: (1) optional CLAUDE.md
  pointer documenting the daaf-state persistent-flag convention; (2)
  FRAMEWORK_INTEGRATION_CHECKLIST.md § 5 lacks a "Modifying an Existing Hook"
  subsection (learning signal); (3) `cleanupPeriodDays` default claim in hook
  headers to be web-verified (harmless if wrong — early prune is benign).
- COMPLETE: user approved both optional follow-ups; orchestrator applied them
  directly (Simple-tier edits):
  - ~~CLAUDE.md § Provenance Boundary bullet~~ — REVERSED at user direction
    (2026-07-15 ~11:52 UTC): the cache-placement convention is framework-dev
    guidance, not universal always-loaded doctrine, so it was relocated to
    FRAMEWORK_INTEGRATION_CHECKLIST.md § 5 (blockquote note before the
    "Modifying an Existing Hook" subsection). CLAUDE.md verified cleanly
    reverted: `git diff --stat CLAUDE.md` → empty; grep "Cache placement
    principle" → 0 hits in CLAUDE.md, 1 in the checklist
  - `agent_reference/FRAMEWORK_INTEGRATION_CHECKLIST.md` § 5 — new
    "Modifying an Existing Hook" subsection (HM1-HM7) codifying the
    draft-test-deploy pattern; plus reviewer-identified alignment fix to
    H1's failure-posture wording (was blanket "fail-closed"; now
    distinguishes safety gates from fail-open observability hooks)
- COMPLETE: iteration-2 review (Consistency + Completeness) — both PROCEED,
  no issues; all cited paths, flag patterns, and /tmp cache examples verified
  against the deployed hooks. `cleanupPeriodDays` 30-day default confirmed
  against official Claude Code settings docs.
- COMPLETE: user approved final state and requested commit. Committed as
  a single pathspec-scoped commit on `daaf_dev_R2` (6 files: 2 deployed
  hooks, checklist, workspace drafts + notes), leaving other sessions'
  working-tree changes untouched. Session complete.

## Open Questions

- None currently.

## AI Disclosure

This session used DAAF (Data Analyst Augmentation Framework) in Framework
Development mode. DAAF contributed to: root-cause diagnosis (hook mechanism
tracing, container/volume lifetime evidence, official Claude Code
documentation verification via a web-capable research agent), /tmp state
inventory and relocation analysis, hook script drafting, and functional
testing. The researcher directed all design decisions (including the
persistent-flag approach) and applies all hook changes personally.
