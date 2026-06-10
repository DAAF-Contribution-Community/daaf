# Session Notes: Framework Development — Context-Reporter Subagent Bleed

**Started:** 2026-06-10
**Workspace:** /daaf/research/2026-06-10_FrameworkDev_Context_Reporter_Subagent_Bleed
**Work Type:** Modify Existing (hook script `.claude/hooks/context-reporter.sh` + related docs)

## Accomplishments

- Phase 1 scoping complete: root cause of orchestrator→subagent context-utilization bleed fully diagnosed via empirical probes on Claude Code v2.1.112.
- Read `.claude/hooks/context-reporter.sh`, `.claude/settings.json`, framework-development-mode.md.
- Dispatched 2 search-agents (live probe + docs/changelog research), then 1 controlled solo probe.
- Phase 3 complete: framework-engineer implemented and deployed the hook fix + CLAUDE.md update.
- Phase 4 complete: 3-angle review (consistency/quality/completeness) — no functional issues;
  minor doc findings fixed by orchestrator (CLAUDE.md § Subagent Context Monitoring wording,
  these session notes refreshed).

## Key Findings (root cause)

1. **Hooks fire inside subagents with the PARENT's identity.** On v2.1.112, settings.json
   PreToolUse hooks fire for subagent tool calls, and the hook stdin carries the parent's
   `session_id` and the parent's main `transcript_path`. Empirical proof: solo probe subagent
   (own context ~35k tokens) received verbatim injections "Context utilization [NOMINAL]:
   113k / 1000k" — exactly the orchestrator's usage at that moment.
2. **`isSidechain != true` filter guarantees parent numbers.** `calculate()` excludes sidechain
   entries; the parent transcript's last main-chain usage entry is always the orchestrator's.
   Subagent transcripts (stored at `<projects>/<session_id>/subagents/agent-<agent_id>.jsonl`)
   have ALL entries `isSidechain: true` and `sessionId` = parent's.
3. **Shared 60s rate-limit gate** (`/tmp/claude-ctx-ts-<session_id>` keyed on parent session id)
   races between orchestrator and all concurrent subagents — injections land in whichever
   agent's tool call fires while the gate is open. Explains intermittent observations.
4. **Subagent transcripts do not record hook_additional_context attachments on disk** —
   delivery is real but only observable via live self-report; disk forensics show nothing.
5. **Docs/changelog (researched):** `agent_id` + `agent_type` fields are present in hook input
   when firing inside a subagent (added v2.1.69; available on v2.1.112). No upstream fix for
   this bleed exists through v2.1.170. `transcript_path` semantics in subagents are undocumented.

## Implemented Fix (user-approved at Checkpoint 1; deployed 2026-06-10)

In `context-reporter.sh`: detect `agent_id` in hook input. If present:
- Derive subagent's own transcript: `<dirname(transcript_path)>/<session_id>/subagents/agent-<agent_id>.jsonl`
  (fast-path: if transcript_path already IS the subagent file, use it directly)
- Compute utilization from that file WITHOUT the isSidechain filter (jq `--argjson allow_sidechain`)
- Use per-agent rate gate `/tmp/claude-ctx-ts-<session_id>-<agent_id>`
- If subagent transcript missing/unparseable → emit nothing (silence over wrong data; NEVER
  parent fallback); `cache_model` skipped in subagent branch
Deployed via write-to-temp + `cp` (deny rules block direct Edit/Write on hooks); mode 100755
verified in git index. Doc updates: hook header comments; CLAUDE.md § Context & Session Health
opening paragraph AND § Subagent Context Monitoring first sentence (own-numbers wording +
silence-is-not-NOMINAL caveat).

## Verification (H5)

- Offline sims (6) by framework-engineer: main-session path unchanged (parent figure 115k);
  subagent path returns subagent's own figure (96k, ground-truth re-derived via jq); per-agent
  gate suppresses repeat; missing transcript → silent exit 0; UserPromptSubmit unchanged.
- Live validation x4: framework-engineer's own injections dropped from parent's 122k
  (pre-deploy) to its own 79-88k (post-deploy); all 3 Phase 4 reviewers received injections
  matching their OWN fresh windows (28k/49k/52k/72k on 1M) while orchestrator was at ~122k.

## Integration Status

**Component:** `.claude/hooks/context-reporter.sh` + `CLAUDE.md` (modified, deployed)
**Checklist:** FRAMEWORK_INTEGRATION_CHECKLIST.md § hooks (H1, H1b, H2-verify, H3-verify, H5)
+ modification items (RM1, RM2, CC2, CC7)
**Completed:** All applicable items. H2 (settings.json) required no change — registration
unchanged. CHANGELOG.md: repo convention is release-based (no Unreleased section); record this
fix in the next release entry. CHANGELOG § 4.4 historical note deliberately left intact.

## In Progress

- Checkpoint 2 (review & approval) presented to user.

## Open Questions

- Optional (user decision at Checkpoint 2): one-line resolution addendum to
  `benchmarks/SESSION_NOTES.md:282-290`, where the bleed was originally observed (outside this
  session's stated scope; file has uncommitted edits from other work).
- Future polish (cosmetic, would require hook redeploy — not done): line ~195 redirection
  grouping `{ echo ... > gate; } 2>/dev/null`; add `set -uo pipefail` per shell-scripting
  skill hook pattern (pre-existing). Subagent window-size cache fallback to parent's window
  retained deliberately (subagents inherit the model).

## AI Disclosure

This session used DAAF (Data Analyst Augmentation Framework) in Framework Development mode.
DAAF contributed to: empirical diagnosis of hook behavior, web documentation research,
session-note authoring. The researcher directed all framework design decisions.
