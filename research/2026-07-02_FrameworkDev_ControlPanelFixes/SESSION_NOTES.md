# Session Notes: Framework Development — Control Panel (daaf.sh) Fixes & Update Pathway Hardening

**Started:** 2026-07-02
**Workspace:** /daaf/research/2026-07-02_FrameworkDev_ControlPanelFixes
**Work Type:** Multi-Component (Modify Existing: host scripts, update scripts, tests, docs, shell-scripting skill)

## Background

User field-tested v2.1.0 → daaf_dev update on macOS (fresh v2.1.0 install, `DAAF_BRANCH=daaf_dev`, ran update script). Failures observed:
1. daaf.sh/daaf_lib.sh never copied to host by update script (manual `docker cp` required)
2. VS Code and log viewer menu options don't work
3. Backup completes but crashes at end: `daaf.sh: line 134: backup_dirs: bad array subscript`; daaf.sh then fails on every startup

## Accomplishments

- Phase 1 scoping complete: 3 parallel read-only explorations (daaf.sh static analysis; update pathway forensics; launchers/tests/docs survey)
- Full findings persisted in `preliminary_notes/`:
  - `2026-07-02_scoping_daafsh-static-analysis.md`
  - `2026-07-02_scoping_update-pathway.md`
  - `2026-07-02_scoping_launchers-tests-docs.md`
- **Phase 3 authoring complete** (3 parallel framework-engineer dispatches on Opus, all COMPLETED):
  - **Track A (control panel):** `scripts/host/daaf.sh` (L134 3.2-safe subscript; /proc/net/tcp dashboard probe + stop-services inode→PID; VS Code password display; ensure_container in handlers 2/3/4; run_delegate guards for backup/restore/update/rebuild; ERR/EXIT diagnostic trap; stderr surfaced on launches; notebooks parity; log-viewer selected-source start; dry-run mock updates; BASH_SOURCE lib sourcing; test-mode guard relocation), `scripts/host/daaf_lib.sh` (check_port /proc/net/tcp rewrite), `scripts/generate_log_viewer.sh` (actionable empty-archive errors), `tests/bash/daaf.bats` (+12 regression tests, 5 pre-existing broken tests repaired — suite previously couldn't load functions at all under Bats 1.13), `tests/bash/daaf_lib.bats` (+3). 80/80 bats green. Live-container verification of probes (real listeners). NOTE: discovered pre-existing "coverage that wasn't" — bats guard returned before function definitions.
  - **Track B (update pathway):** `scripts/host/update_daaf.sh` + `update_daaf.ps1` sync redesign (ls-files-derived list at new HEAD; tier A existence-heal + tier B changed-file copy; heal runs on both "already up to date" early exits; self-update re-run notice; per-file copy-failure reporting with docker cp hint; no auto re-exec), `tests/bash/update_daaf.bats` (55/55 green), `tests/powershell/update_daaf.Tests.ps1` (9 Pester tests — NOT runtime-verified, no pwsh in container; CI windows runner will exercise). All 4 install/migrate download lists verified complete — no changes needed.
  - **Track C (process hardening):** `.github/workflows/ci-scripts.yml` (daaf.sh in macOS smoke with seeded backup dir + /bin/bash; new bats-bash32 job = syntax + DAAF_DRY_RUN smoke under bash:3.2 image; stale coverage comment fixed; 8→9 jobs), `tests/lint/check-daaf-conventions.sh` (Bash-4.x banned-construct check, validated in failing+passing states), `shell-scripting` skill (host-script portability standard in references/bash-standards.md; SKILL.md topic index; testing.md matrix reconciled), `agent_reference/FRAMEWORK_INTEGRATION_CHECKLIST.md` (new §6 host-facing scripts HS1-HS11/HSM1-HSM4; Cross-Cutting renumbered §7), `.claude/skills/agent-authoring/SKILL.md` (§6→§7 stale ref), `user_reference/01_installation_and_quickstart.md` (bash 3.2 note, log-explorer archive dependency, updater re-run expectation). README.md needed no edit.
- **Orchestrator direct fixes:** `tests/lint/check-daaf-conventions.sh` — error-handling regex now accepts `set -Eeuo` variants; `*_lib.sh` sourced libraries exempted from strict-mode preamble and DAAF_NESTED lifecycle checks (libraries must not set caller shell options; no exit traps). Conventions lint now 0 failures / 16 pre-existing warnings.

## Root Causes Identified (all HIGH confidence unless noted)

1. **Startup crash:** `daaf.sh:134` `${backup_dirs[-1]}` — negative array subscript is Bash 4.3+; macOS `/bin/bash` is 3.2.57. Guarded by "backup dir exists" → fires only after first backup, then on every menu draw (`gather_status` at L618-619). `set -euo pipefail` (L21) + no ERR/EXIT trap → hard abort. Ironically introduced by a Phase 4 review "standards compliance" fix in the original MenuWrapper session.
2. **`ss` missing from container image:** `check_port` (daaf_lib.sh:115), dashboard (daaf.sh:110-111), stop-services (daaf.sh:531-538) all run `ss -tlnp` in-container with stderr suppressed; Dockerfile never installs iproute2. check_port always returns 1 → dashboard always "not running", readiness polls always time out, browser opens before server ready, Stop Web Services is a silent no-op. Container-side launchers already use the correct `/proc/net/tcp` pattern (generate_log_viewer.sh:190-211).
3. **VS Code password never displayed:** launch_code_server.sh prints password (default `daaf`) to stdout only; daaf.sh:335-336 runs it detached with all output discarded → login page with no password.
4. **Log viewer archive-dependence:** daaf.sh:440-442 starts server with `--archive`; generate_log_viewer.sh:127-145 exits 1 if archive empty even when user selected a project source; failure invisible (detached + stderr discarded).
5. **Update chicken-and-egg:** v2.1.0 `sync_host_scripts` uses hardcoded pathspec (v2.1.0 lines 404-418) lacking daaf.sh/daaf_lib.sh; no self-update re-exec; "already up to date" early exit (L901-908) skips sync entirely, so re-runs can never catch up — files added in commit X are permanently missed by users updating across X. Same flaw in update_daaf.ps1 `Sync-HostScript` (506-526). Mechanism unchanged on daaf_dev (only +2 pathspec lines).
6. **Fragility:** `ensure_container` exists (daaf_lib.sh:125-148) but never called; unguarded child-script calls under `set -e` kill the menu on any child failure; no EXIT/ERR trap.
7. **Test/CI blind spots:** bats runs under Bash 5 on ubuntu only (crash line WAS covered by daaf.bats:183-201 — wrong environment); macOS smoke job (ci-scripts.yml:230-327) claims to catch Bash 3.2 issues but omits daaf.sh; shellcheck cannot catch version-gated constructs; no launcher bats tests despite Plan requiring them.
8. **Docs/skill gaps:** README + user_reference recommend daaf.sh as primary entry point (currently crashes on macOS after first backup); shell-scripting skill has NO Bash 3.2 / host-script portability standard.

## Key Decisions

- **Checkpoint 1 CONFIRMED (2026-07-02).** User approved scope + approach, treating design review as covered. Two additions to scope:
  - Restore-from-backup crashes daaf.sh ungracefully when no backup folders exist (likely unguarded child exit under `set -e` — verify during authoring)
  - View Notebooks option has same failure as VS Code/log viewer (third consumer of broken `check_port`)
- check_port fix via `/proc/net/tcp` pattern (no image rebuild required) — confirmed
- Update fix design (user asked for sequencing guarantee): derive sync list from post-update repo HEAD (`git ls-files scripts/host/`, platform-filtered); copy files missing on host unconditionally; run existence-heal sync even on "already up to date" path; print prominent "updater was updated — re-run to complete host tool sync" notice when update_daaf.sh/.ps1 is among synced files. Two-run recovery for v2.1.0 users; same-run delivery for all future additions. NO auto re-exec (lock/trap/stash interactions too risky).
- CI workflow edits (.github/workflows/ci-scripts.yml) **explicitly authorized by user**; if permission hooks block, fall back to patch file in workspace
- User directive: run Agent dispatches on Opus (not Fable) for routine authoring/review work

## Integration Status

**Component:** 15 files modified across control panel, update pathway, CI, linter, skills, checklist, docs (see Accomplishments)
**Checklist:** modification subsections executed per track (SM/RM/H1b/CC items reported done by all three dispatches); new §6 added for future host scripts
**Completed:** All applicable items per the three framework-engineer reports; executable bits verified 100755 on modified .sh files

## In Progress

- **Phase 4 review COMPLETE** (3 parallel read-only reviewers: consistency [Sonnet], quality [Opus], completeness [Sonnet]). Pre-review gate: full bash suite 388/388 green (scratchpad bats-core: /tmp/.../scratchpad/bats-core/bin/bats); conventions lint 0 failures. Verdicts: NO BLOCKERS anywhere. Completeness: all 26 scoped fix-points landed with line evidence; exec bits 100755; no orphans/debris. Pester runs on windows-latest via ci-scripts.yml `pester-tests` job (verified).
- **FIX ROUND COMPLETE (user approved; Sonnet framework-engineer dispatch).** All six items done: (1) notice wording fixed in update_daaf.sh:573 AND update_daaf.ps1:633 (same mismatch found in PS1); (2) testing.md CI snippets replaced with accurate stdin-drive + seeded-backup patterns; (3) PS1 tier-A append made conditional on Copy-HostScript success — tier-B append had the same bug, also fixed; (4) SYNC_COPY_FAILED consumed with closing summary in .sh, $syncCopyFailed added + summary in .ps1; (5) tmpdir cleanup already existed (daaf.sh:177) — no change; (6) password source-of-truth comment added. Tests after fixes: update_daaf.bats 55/55, daaf.bats 65/65, lint 0 failures, exec bits 100755. Original item list for reference:
  1. `update_daaf.sh:573` — self-update notice quotes `'Already up to date.'`; script actually prints `"Already up to date!"` (and docs quote the `!` form at user_reference/01:463). Change notice quote to match (`!`).
  2. `.claude/skills/shell-scripting/references/testing.md:404-428` — illustrative CI snippet outdated: plain smoke loop would hang on daaf.sh (needs `printf 'q\n' |` stdin-drive + seeded backup dir, per real ci-scripts.yml). Fix snippet or mark illustrative pointing to ci-scripts.yml as authoritative. Prose at :447-449 already accurate.
  3. `update_daaf.ps1` tier-A loop (~:560s) — `$copied += $scriptName` runs unconditionally even when `Copy-HostScript` fails; Bash only marks on success (so PS tier B won't retry a failed tier-A copy). Fix: `if (Copy-HostScript $repoPath) { $copied += $scriptName }`.
  4. `update_daaf.sh:417,498` — `SYNC_COPY_FAILED` flag set but never read. Consume it: closing summary line ("Some scripts could not be synced — see warnings above") when true; mirror equivalent in update_daaf.ps1 (has no flag at all).
  5. `daaf.sh:102` (gather_status) — `mktemp -d` tmpdir leaked on every menu redraw; add cleanup at end of function (INFO but block already touched this session).
  6. (Optional polish) `daaf.sh` handle_vscode — add comment noting password default `daaf` mirrors launch_code_server.sh:31 source of truth.
- **Deferred/not addressed (surfaced to user, acceptable):** `grep -c "daaf-docker"` substring false-positive (minor, pre-existing, also in run_vscode.sh/view_logs.sh — future cleanup); CONTAINER_NAME hardcoding in docker cp (pre-existing); stop-services child-process survival (pre-existing minor); PowerShell runtime verification (CI windows pester-tests will exercise).
- After fix round: re-run `update_daaf.bats` + `daaf.bats` (+ lint), verify PS edit statically, then final user approval + commit decision.
- **FINAL GATE PASSED (2026-07-02 16:56 UTC):** full bash suite 388/388 (exit 0, only non-ok line is the `1..388` plan), conventions lint 0 failures. Session work complete; awaiting user commit decision.
- **User host recovery note (this specific user):** their Mac has a manually-copied PRE-FIX daaf.sh. The existence-heal won't overwrite existing files, and their v2.1.0 updater's run 1 consumes the commit range without syncing daaf.sh (not in old pathspec). One-time manual copy of fixed daaf.sh + daaf_lib.sh needed after commit: `docker cp daaf-daaf-docker-1:/daaf/scripts/host/daaf.sh ./daaf.sh` and same for daaf_lib.sh. Fresh v2.1.0 users without manual copies self-heal fully via the two-run sequence.

## Restart Prompt (if session must resume fresh)

Resume Framework Development mode for the DAAF Control Panel fix session. Read
`/daaf/research/2026-07-02_FrameworkDev_ControlPanelFixes/SESSION_NOTES.md` in full —
Phases 1-4 are complete (all changes uncommitted in working tree; `git status` lists them),
no blockers, and the only remaining work is the six-item fix round under "PENDING FIX ROUND"
above, followed by test re-runs (bats binary at the scratchpad path noted above, or
re-bootstrap bats-core), and Checkpoint 2 final approval with the user. The three scoping
reports are in `preliminary_notes/`. User has approved CI workflow edits and prefers
Agent dispatches on Opus/Sonnet rather than Fable.

## Post-Commit Addendum (2026-07-02, after b3690cd pushed by user)

- Field verification: fresh v2.1.0 → daaf_dev two-run sequence WORKS (user confirmed daaf.sh arrived on run 2). Transition caveat: run 1 (old updater) gives no re-run cue — changelog must carry the "run update twice from v2.1.x" instruction.
- **README round (uncommitted):** created `scripts/host/README.txt` (host-folder orientation; daaf.sh as entry point); wired into install.sh/.ps1, migrate_daaf.sh/.ps1, and BOTH updater platform filters (txt files don't match `*.sh`/`*.ps1` — required explicit filter add); tests updated (update_daaf.bats 56/56, install.bats 30/30, migrate_daaf.bats 51/51, lint 0). Refined checklist HS6 to document the novel-file-type filter exception discovered in this exercise.
- **Future work backlog (user-endorsed, not yet scoped):**
  1. Container-name derivation (`docker compose ps -q daaf-docker` → ID) replacing hardcoded `daaf-daaf-docker-1` in update_daaf.sh docker cp, rebuild_daaf.sh, and `grep -c "daaf-docker"` checks → also enables multi-instance installs (per-folder compose projects; verify no explicit volume `name:` in docker-compose.yml; parameterize published ports 2718/2719/2720 via env with unchanged defaults; daaf.sh + launchers read same vars). Bundle with/after the daaf.ps1 session.
  2. Drift warning in updater heal pass: warn (never overwrite) when host copy differs from repo copy.
  3. Clearer stash-pop conflict guidance in updater output (Dockerfile/compose customization path) routing to User Support conflict walkthrough.
  4. Changelog entry: two-run update from v2.1.x; pre-v2.1.0 users take the migrate path.

## Open Questions

- Include CI workflow changes in scope (safety boundary requires explicit user approval)?
- Update-fix flavor: full-directory copy (B) vs manifest (C) — recommendation is B-style derived-from-new-HEAD list with missing-file healing
- User's immediate host recovery: move `*_daaf_backup` dir out of `daaf-docker/` (workaround), then manual `docker cp` of fixed scripts once landed

## AI Disclosure

This session used DAAF (Data Analyst Augmentation Framework) in Framework
Development mode. DAAF contributed to: root-cause diagnosis via parallel
read-only exploration, portability auditing, update-pathway forensics, and
(pending) fix authoring with integration checklist execution and multi-angle
review. The researcher directed all framework design decisions and approved
all changes.
