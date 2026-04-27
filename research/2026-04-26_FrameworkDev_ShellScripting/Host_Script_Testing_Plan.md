# Host Script Testing Plan

**Created:** 2026-04-26
**Context:** Framework Development session — CI pipeline and testing infrastructure
**Status:** Phases 1-4 COMPLETE (Sessions 2-3). Phase 5 remains.
**Reviewed by:** 2 search-agent subagents (feasibility + cross-platform/CI architecture)

---

## Implementation Status

### Session 2 (2026-04-26) — Phase 1 + Phase 2

Committed as `5afb3ce` on branch `minor_revisions_v202`. All work passed a 3-angle review (consistency, quality, completeness).

**Completed:**

1. **Pre-Phase 1: flock portability fix** — Replaced `flock` with portable `mkdir`-based locking in `update_daaf.sh` and `migrate_daaf.sh`. Uses trap composition to chain lock cleanup with existing EXIT trap. Added `${LOCK_DIR:-}` guard in `cleanup_on_error()` for test mode safety. macOS compatibility confirmed (5/7 scripts were already bash 3.2 clean; the 2 with flock are now fixed).

2. **Phase 1: DAAF_TEST_MODE guards** — Added to all 14 scripts (7 `.sh` + 7 `.ps1`). Guard uses `return 0 2>/dev/null || exit 0` (bash) and `return` (PowerShell). Placed after function definitions, before first executable logic. Header documentation added to all 14 scripts.

3. **Phase 2: Enhanced behavioral tests** — 117 new test cases total:
   - **2A:** `update_daaf.bats` — 22 new tests (state machine helpers, handle_conflict, sync_host_scripts, check_build_changes, prompt_choice, locking/safety)
   - **2B:** `migrate_daaf.bats` — 15 new tests (container_git variants, era detection patterns, prompt_choice, locking/safety)
   - **2C:** `install.bats` — 11 new tests (installation state detection, URL construction, download failure, readiness checks)
   - **2D:** `backup_daaf.bats` — 10 new tests (suffix edge cases incl. z/exhaustion/gap-filling, disk space, size verification)
   - **2E:** Pester behavioral tests — 59 new tests across `update_daaf.Tests.ps1` (+21), `migrate_daaf.Tests.ps1` (+18), `install.Tests.ps1` (+9), `backup_daaf.Tests.ps1` (+11)

4. **Bug fix: test_helper.bash** — `MOCK_DOCKER_*` variables were not exported, making them invisible to subshells created by `run bash`. Fixed by adding `export` to all 14 mock control variables. This resolved pre-existing silent test failures.

5. **Dockerfile: testing tools** — Added `bats-core` 1.13.0 (+ bats-support 0.3.0, bats-assert 2.1.0, bats-file 0.4.0), `shellcheck` 0.10.0, and `pwsh` 7.4.15 LTS (+ Pester 5.7.1) to the container for local test execution.

6. **Bash 3.2 compatibility audit** — All 7 `.sh` scripts audited. No bash 4+ language features found (no associative arrays, mapfile, `${var,,}`, `|&`, coproc, nameref, lastpipe, or negative indexing). Only incompatibility was `flock` (now fixed).

**Suite totals:** 126 BATS + 175 Pester = **301 tests** (up from 183).

**Review corrections addressed:** #1 (function-less scripts), #2 (flock fix), #3 (guard syntax), #4 (guard placement), #7 (handle_conflict tests), #8 (ERR trap in test mode), #9 (sync_host_scripts partial failure), #10 (backup suffix gap-filling). Q4 (documentation) and Q5 (flock fix timing) also resolved.

**Open questions resolved:**
- Q1: Bash 3.2 audit complete — all clean
- Q2: Pester behavioral tests implemented (59 new cases — feasible and useful)
- Q3: Weekly frequency chosen for Docker integration tests (Phase 5)
- Q4: DAAF_TEST_MODE documented in all script headers

### Local Test Execution (New Capability)

The Dockerfile now includes all testing tools. After rebuilding the container (`bash rebuild_daaf.sh` from the host), tests can be run locally inside the container:

```bash
# BATS tests (bash lifecycle scripts)
bats tests/bash/

# Pester tests (PowerShell lifecycle scripts)
pwsh -c "Invoke-Pester -Path ./tests/powershell/ -Output Detailed"

# ShellCheck lint (static analysis)
shellcheck scripts/host/*.sh
```

Pinned versions: bats-core 1.13.0, bats-support 0.3.0, bats-assert 2.1.0, bats-file 0.4.0, shellcheck 0.10.0, pwsh 7.4.15 LTS, Pester 5.7.1. BATS helper libraries installed to `/usr/lib/bats/` (already in `test_helper.bash` search path).

### Session 3 (2026-04-27) — Phase 3 + Phase 4

**Completed:**

1. **Phase 3: Dry-run mode** — Added `DAAF_DRY_RUN=1` support to all 14 scripts (7 `.sh` + 7 `.ps1`). Uses function override approach: defines `docker()` and `curl()` shell functions that shadow native commands, intercepting all Docker/curl calls with zero changes to script bodies. Per-script mock patterns return realistic data for output-producing commands (scan output, container status, git rev-list counts) and `[DRY-RUN]` messages for fire-and-forget commands. Preflight checks (`command -v docker`, `docker info`) pass automatically since function resolution finds the override. Locking (mkdir-based) runs through without issue since it doesn't use Docker. Backup scripts have early-exit guards after disk space check to avoid file-count verification on mock data. Update scripts simulate "already up to date" state; migrate scripts simulate "already migrated" / Era 1 path.

2. **Phase 4: Cross-platform smoke CI** — Added Job 8 (`smoke-tests`) to `ci-scripts.yml`. Matrix: ubuntu-latest, macos-latest, windows-latest. Bash dry-run on Linux/macOS (skipped on Windows), PowerShell 7 dry-run on all 3 platforms, Windows PowerShell 5.1 dry-run on Windows only. `fail-fast: false` so all 3 OS report independently.

3. **Dry-run smoke tests** — 31 new tests (17 BATS + 14 Pester) across all 14 test files. Each script verified to complete with exit 0 under `DAAF_DRY_RUN=1`, with assertions on meaningful output (e.g., "Already up to date", "Rebuild complete", `[DRY-RUN]` markers).

4. **Bug fix: migrate_daaf.ps1 array indexing** — When `docker ps -a` returns exactly one container name, PowerShell unwraps the single-element array to a scalar string. `$AllContainersList[0]` then indexes into the string's characters, and `.Trim()` fails because `[char]` lacks that method. Fixed by wrapping the pipeline in `@()` to force array context.

5. **Shell-scripting skill update** — Added two PowerShell gotchas to `gotchas.md`: (a) `$LASTEXITCODE` starts as `$null`, not 0 — mock functions must set `$global:LASTEXITCODE = 0` explicitly; (b) single-element pipeline array unwrapping — always wrap in `@()` when indexing output.

**Suite totals:** 142 BATS + 190 Pester = **332 tests** (up from 301).

**Review:** 3-angle review (consistency, quality, completeness) passed. Minor findings: cosmetic section ordering difference between 2 PS scripts and their bash counterparts (non-functional); testing plan status needed updating (done).

### Remaining (Future Sessions)

| Phase | Status | Depends On | Notes |
|-------|--------|------------|-------|
| Phase 5 (Docker Integration Tests) | Not started | Independent | ci-integration.yml, weekly schedule + dispatch + release tags. Add Docker cleanup step. |

### Learnings

- **Subshell variable isolation in BATS:** `call_count` variables inside `$()` command substitutions are invisible to the parent shell. Use argument-pattern matching (`case "$*"`) instead of call counting for docker mocks.
- **Mock variable export:** BATS `run bash "$script"` creates a subshell — mock control variables must be `export`ed to propagate.
- **ERR trap in test mode:** Scripts with ERR traps fire them when tests source the script. Tests must `trap - ERR; set +eu` after sourcing to neutralize the sourced script's safety settings.
- **Windows native-command argument passing:** Embedded `"` characters in strings passed to native executables (e.g., `docker.exe`) on Windows get mangled by the C runtime's `CommandLineToArgvW` parser, causing silent argument truncation. Neither PSScriptAnalyzer (which only understands PowerShell syntax) nor the Pester structural tests (which pattern-match the source text) caught this — it only manifests at runtime on Windows with a real Docker daemon. Phase 5 Integration Tests (currently Linux-only) would not catch this either. Mitigation: added a structural regression test to `backup_daaf.Tests.ps1` that checks the Docker scan command avoids the known-bad pattern, and documented the gotcha in the `shell-scripting` skill's `gotchas.md`. A future Phase 5 expansion to include a Windows runner with Docker would provide the strongest coverage, but Windows Docker-in-Docker on GitHub Actions is complex.
- **Function override for dry-run mocking:** Defining `docker()` as a shell function that shadows the native `docker` binary is far less invasive than search-and-replacing every call site with `docker_cmd`. Bash resolves functions before PATH lookups, so `command -v docker` also finds the function — preflight checks pass automatically with no explicit bypass needed. Same principle works in PowerShell (function resolution precedes native command resolution).
- **PowerShell `$LASTEXITCODE` starts as `$null`:** Before any native command runs, `$LASTEXITCODE` is `$null`, not 0. Checks like `$LASTEXITCODE -ne 0` evaluate `$null -ne 0` as `$true`, causing false failures. Guard with `$LASTEXITCODE -and $LASTEXITCODE -ne 0` or set `$global:LASTEXITCODE = 0` in mock functions.
- **PowerShell single-element pipeline array unwrapping:** When a pipeline returns exactly one object, PowerShell unwraps it to a scalar. `$result[0]` then indexes into the string's characters, not array elements. Always wrap in `@()` when indexing: `$result = @(docker ps --format '{{.Names}}')`.
- **Dry-run stub file cleanup:** The `migrate_daaf.ps1` dry-run mock creates stub script files in the CWD (for downstream `& .\backup_daaf.ps1` calls). These are left behind after local testing and must be manually cleaned up. CI runners are ephemeral so this is only a local testing concern.

---

## Session 1 Context

This plan was produced during a prior Framework Development session that accomplished the following (all committed on branch `minor_revisions_v202`):

1. **Created the `shell-scripting` skill** (`.claude/skills/shell-scripting/`) — DAAF coding standards for Bash and PowerShell scripts, with 5 reference files covering bash standards, PowerShell standards, error handling, testing (BATS/Pester/CI), and cross-platform gotchas.

2. **Built a 7-job CI pipeline** (`.github/workflows/ci-scripts.yml`) — ShellCheck lint, PSScriptAnalyzer lint (Linux pwsh 7 + Windows PS 5.1), hygiene checks (executable bits, LF endings, script pair parity), BATS tests, Pester tests, and DAAF convention lint. PSScriptAnalyzer config lives at `.github/linters/PSScriptAnalyzerSettings.psd1`.

3. **Created test infrastructure** (`tests/`) — 7 BATS test files + shared helper with Docker mocking (60+ tests), 7 Pester test files + shared helper (111+ tests), and a custom DAAF convention lint script. Added ShellCheck to `.pre-commit-config.yaml`.

4. **Applied safety fixes** to lifecycle scripts — concurrent-run locking (flock/mutex) on migrate_daaf and update_daaf, SHA quoting in sh -c strings, verbose git for error-sensitive operations, disk space pre-check and size-based backup verification, cp -a parity fix, JSON injection fix in recover-session-logs.sh.

5. **Moved all 14 lifecycle scripts** from repo root to `scripts/host/` — updated all internal cross-references (GitHub raw download URLs, container sync paths), CI workflow, test files, and documentation. Root directory went from 30 items to 16.

**This plan** covers the testing phases: making the lifecycle scripts deeply testable via test mode guards, enhanced mock tests, dry-run mode, cross-platform smoke tests, and Docker integration tests. Read the "Review Findings & Revisions" section first — it contains critical corrections to the original plan body below.

---

## Review Findings & Revisions (2026-04-26)

The plan was reviewed by two independent agents. Key corrections incorporated below:

### Critical Corrections

1. **5 of 7 scripts have NO functions (install, backup, rebuild, run, view_logs).** The `DAAF_TEST_MODE` guard is only useful for `update_daaf` and `migrate_daaf`, which define testable helper functions. The other 5 scripts are entirely inline logic. **Revised approach:** Phase 2 unit tests apply only to update_daaf and migrate_daaf. The function-less scripts are tested via Phase 3 dry-run + Phase 5 integration only. Phase 2C (install tests) and 2D (backup tests) are reclassified as dry-run behavioral tests under Phase 3.

2. **`flock` is Linux-only — will fail on macOS.** The concurrent-run locking added to update_daaf.sh and migrate_daaf.sh uses `flock`, which is not available on macOS. **Fix:** Add a platform-aware locking wrapper that uses `flock` on Linux and `shlock` or mkdir-based locking on macOS. Alternatively, the dry-run mode must skip the locking block entirely. This is a **blocker for Phase 4 macOS smoke tests**.

3. **Guard must use `return 0 2>/dev/null || exit 0`** (not `|| true`). The `|| true` variant silently continues execution if the script is run directly (not sourced), defeating the purpose. `|| exit 0` safely exits in both contexts.

4. **Guard placement: between last function definition and the `flock` block.** The plan must explicitly state this to prevent the guard from being placed after the lock, which would create side-effect lock files during testing.

5. **Dry-run mode needs TWO categories of Docker command wrappers:**
   - **Fire-and-forget** (`docker compose up`, `docker cp`, `curl`): print `[DRY-RUN]` and return 0
   - **Output-producing** (`docker compose ps`, `docker run ... find | wc -l`, `docker exec ... git rev-list`): return realistic mock output, not just a dry-run message. Scripts that parse Docker output will break if they receive `[DRY-RUN]` text instead of expected formats.

6. **Dry-run must also bypass preflight checks.** `command -v docker` and `docker info` gates run before any wrapped command. On CI runners without Docker (macOS), these will fail. The preflight section needs a dry-run check: `if [ "${DAAF_DRY_RUN:-}" != "1" ]; then ... fi`

### Additional Test Cases Identified

7. **`handle_conflict()` in update_daaf is untested.** This ~107-line function handles merge conflict resolution, interactive Claude Code launch, conflict file detection, and abort command construction. It is the highest-risk user interaction point and must be added to Phase 2A.

8. **ERR trap fires during test mode.** Both update_daaf and migrate_daaf register ERR traps before the test mode guard. If mocked functions return non-zero, the trap fires with alarming error messages. Tests must unregister the trap after sourcing: `trap - ERR`

9. **`sync_host_scripts` partial failure.** The function's `docker cp ... 2>/dev/null` silently swallows per-file copy failures. Add a test for partial sync (some files succeed, some fail).

10. **Backup suffix gap-filling behavior.** When lettered backups have gaps (a exists, b deleted, c exists), the script finds the first available slot. Add a test confirming this behavior.

### CI Architecture Corrections

11. **Integration workflow should also trigger on release tags:** `push: tags: ['v*']` ensures every release is validated end-to-end.

12. **Add Docker cleanup to integration workflow:** `docker compose down -v --rmi local` as a final `if: always()` step.

13. **`windows-latest` now points to Windows Server 2025.** PowerShell 5.1 has a known `Invoke-WebRequest` NonInteractive mode issue on recent images. Consider pinning to `windows-2022` if PS 5.1 tests prove flaky.

14. **Bash 3.2 on macOS is confirmed** (Apple has not updated past 3.2.57 due to GPLv3). Scripts correctly avoid bash 4+ features (no associative arrays, no mapfile), but `set -u` with empty arrays needs auditing.

15. **BATS is NOT pre-installed on macos-latest** — requires `brew install bats-core` or `bats-core/bats-action`. Current CI correctly runs BATS only on ubuntu-latest.

### Revised Phase Structure

```
Phase 1 (Test Mode Guards)     ─── update_daaf + migrate_daaf ONLY (2 scripts × 2 languages = 4 files)
    │
    ├── Phase 2 (Enhanced Mocks) ── update_daaf + migrate_daaf behavioral tests only
    │                                (~37 BATS cases + ~32 Pester cases)
    │
    └── Phase 3 (Dry-Run Mode)  ── ALL 14 scripts; includes install/backup/rebuild behavioral tests
            │                       Two wrapper categories: fire-and-forget vs output-producing
            │                       Must bypass preflight checks + locking
            │
            └── Phase 4 (Smoke CI) ── Must resolve flock-on-macOS before enabling macOS runner
                                      Add as Job 8 in ci-scripts.yml (not separate workflow)

Phase 5 (Integration Tests)    ── ci-integration.yml; trigger on schedule + dispatch + release tags
                                   Add Docker cleanup step; 30-min timeout is adequate
```

### Open Questions Updated

- **Q1 resolved:** macOS bash 3.2 is confirmed. Audit `set -u` + empty array patterns before Phase 4.
- **Q2 revised:** Pester behavioral tests are feasible for update_daaf.ps1 and migrate_daaf.ps1 (which have functions). For function-less scripts, structural + smoke testing is sufficient.
- **Q5 (new):** Should we fix the flock-on-macOS issue *before* this plan (as a safety fix), or as part of Phase 3 (dry-run would bypass it anyway)? Recommendation: fix it now since macOS users could encounter it in normal usage, not just CI.

---

## Goal

Reduce the surface area of uncertainty about how the 14 host-side lifecycle scripts (.sh/.ps1) will behave on real user machines across Windows, macOS, and Linux. These scripts are the primary user-facing interface to DAAF — if install, update, or migrate fails on a user's machine, the entire framework is inaccessible.

## Current State

### What Exists

- **7 BATS test files** (`tests/bash/*.bats`) covering syntax validation, preflight mocking (missing Docker, daemon not running), DAAF_NESTED behavior, and some structural checks
- **7 Pester test files** (`tests/powershell/*.Tests.ps1`) covering syntax validation and structural content verification (no behavioral testing)
- **Shared test helpers** (`test_helper.bash`, `TestHelper.ps1`) with Docker mock infrastructure
- **CI workflow** (`ci-scripts.yml`) with 8 jobs: ShellCheck, PSScriptAnalyzer (Linux + Windows), hygiene checks, BATS tests, Pester tests, DAAF conventions lint, cross-platform dry-run smoke tests
- **Safety fixes applied:** concurrent-run locking (flock/mutex), SHA quoting, verbose git for error-sensitive ops, backup disk space + integrity checks, cp -a parity fix

### What's Missing

The current tests verify that scripts **load** correctly and **detect missing prerequisites**, but do not test the **behavioral logic** that runs after preflights pass. The untested surface area includes:

| Script | Untested Critical Logic |
|--------|------------------------|
| **install.sh/ps1** | Download success/failure handling, partial download recovery, existing installation detection paths (fresh vs incomplete vs force-reinstall), container readiness wait loop, CLAUDE.md verification |
| **update_daaf.sh/ps1** | The entire state machine: ahead/behind/dirty/diverged detection, merge vs rebase path selection, conflict resolution flow, stash create/restore, backup branch management, host script sync (`sync_host_scripts`), build change detection (`check_build_changes`) |
| **migrate_daaf.sh/ps1** | Era 1 vs Era 2 detection, graft candidate search and matching, backup-before-migrate flow, idempotency marker check, the entire 400+ line migration sequence |
| **backup_daaf.sh/ps1** | Date-suffix generation edge cases (26th backup overflow), disk space pre-check logic, size-based verification logic, actual copy integrity |
| **rebuild_daaf.sh/ps1** | File hash comparison logic, docker cp correctness, pre-rebuild backup creation |
| **run_daaf.sh/ps1** | Already-running container detection, custom command passthrough, CLAUDE.md verification failure path |
| **view_logs.sh/ps1** | Container start attempt, log viewer invocation chain |

### Why Current Tests Can't Cover This

The scripts are **monolithic** — they execute their entire logic on load. When BATS runs `bash script.sh`, the script immediately starts calling Docker, downloading files, etc. There is no way to source the script to test individual functions without triggering execution. This is the fundamental blocker.

---

## Implementation Plan

### Phase 1: Test Mode Guards

**Goal:** Make scripts testable by adding a guard that prevents execution when sourced for testing.

**Effort:** Low (3-4 lines per script, 14 files)

**What to add to each .sh script:**

```bash
# --- Test Mode Guard ---
# When sourced for testing, define functions but skip execution.
# Usage: DAAF_TEST_MODE=1 source ./scripts/host/install.sh
if [ "${DAAF_TEST_MODE:-}" = "1" ]; then
    return 0 2>/dev/null || true
fi
```

**Placement:** After all function definitions, before the first line of executable logic (i.e., before the first preflight check or Docker command). This means all functions defined above the guard are available to BATS tests, but the script's main execution flow is skipped.

**What to add to each .ps1 script:**

```powershell
# --- Test Mode Guard ---
# When dot-sourced for testing, define functions but skip execution.
# Usage: $env:DAAF_TEST_MODE = "1"; . ./scripts/host/install.ps1
if ($env:DAAF_TEST_MODE -eq "1") {
    return
}
```

**Placement:** Same principle — after function definitions, before main execution.

#### Per-Script Guard Placement

| Script | Functions Defined Before Guard | Guard Goes Before (First Executable Line) |
|--------|-------------------------------|-------------------------------------------|
| **install.sh** | `Pause-For-User` equivalent (trap) | The `docker-compose.yml` existence check |
| **install.ps1** | `Pause-For-User` | The `Test-Path docker-compose.yml` check |
| **update_daaf.sh** | `prompt_choice`, `sync_host_scripts`, `check_build_changes`, `finish_update`, ERR trap | The "Checking prerequisites" banner |
| **update_daaf.ps1** | `Pause-And-Exit`, `Prompt-Choice`, `Compose-Git`, `Compose-Git-Verbose`, `Compose-Git-Null`, `Sync-HostScripts`, `Check-BuildChanges`, `Finish-Update`, `Handle-Conflict`, trap | The "Checking prerequisites" banner |
| **migrate_daaf.sh** | `prompt_choice`, `container_git`, `container_git_verbose`, `container_exec` | The Docker prerequisite checks |
| **migrate_daaf.ps1** | `Pause-For-User`, `Prompt-Choice`, `Container-Git`, `Container-Git-Verbose`, `Container-Exec`, `Container-Shell`, `Container-Shell-Verbose`, trap | The Docker prerequisite checks |
| **backup_daaf.sh** | Pause trap | The compose file existence check |
| **backup_daaf.ps1** | `Pause-And-Exit` | The compose file existence check |
| **rebuild_daaf.sh** | Pause trap | The compose file existence check |
| **rebuild_daaf.ps1** | `Pause-And-Exit` | The compose file existence check |
| **run_daaf.sh** | Pause trap | The compose file existence check |
| **run_daaf.ps1** | `Pause-And-Exit` | The compose file existence check |
| **view_logs.sh** | Pause trap | The compose file existence check |
| **view_logs.ps1** | `Pause-And-Exit` | The compose file existence check |

#### Verification

After adding guards, verify:
1. `DAAF_TEST_MODE=1 bash -c 'source scripts/host/update_daaf.sh && type sync_host_scripts'` succeeds (function is defined)
2. `bash scripts/host/update_daaf.sh` still works normally (guard is skipped when not sourced)
3. Same for PowerShell: `$env:DAAF_TEST_MODE = "1"; . scripts/host/update_daaf.ps1; Get-Command Sync-HostScripts` succeeds

---

### Phase 2: Enhanced Mock Tests

**Goal:** Write behavioral tests for the critical decision logic in update, migrate, and install.

**Effort:** Medium (50-70 new test cases across 6 files)

**Depends on:** Phase 1 (test mode guards must be in place)

#### 2A. update_daaf State Machine Tests

**File:** `tests/bash/update_daaf.bats` (extend existing)

The update script's state machine is the most complex logic in DAAF's lifecycle scripts. It detects the relationship between the local and remote branches and chooses a strategy. The key decision variables are:

- `BEHIND` — number of commits behind remote (from `git rev-list HEAD..origin/main --count`)
- `AHEAD` — number of commits ahead of remote (from `git rev-list origin/main..HEAD --count`)
- `DIRTY_COUNT` — number of uncommitted changes (from `git status --porcelain`)
- `ON_DEFAULT_BRANCH` — whether the user is on the expected branch

**State matrix to test:**

| State | BEHIND | AHEAD | DIRTY | Expected Behavior |
|-------|--------|-------|-------|-------------------|
| Up to date | 0 | 0 | 0 | "Already up to date" message, exit 0 |
| Clean fast-forward | >0 | 0 | 0 | `git pull --ff-only`, sync host scripts |
| Dirty fast-forward | >0 | 0 | >0 | Stash → pull --ff-only → stash pop |
| Ahead only | 0 | >0 | 0 | "Your branch is ahead" message, offer sync |
| Clean diverged | >0 | >0 | 0 | Offer merge or squash-rebase |
| Dirty diverged | >0 | >0 | >0 | Stash → offer merge/rebase → stash pop |
| Non-default branch | any | any | any | Warning about non-default branch |

**Test implementation approach:**

```bash
@test "update: clean fast-forward pulls and syncs" {
    # Source script in test mode
    DAAF_TEST_MODE=1 source "$REPO_ROOT/scripts/host/update_daaf.sh"

    # Mock container_git to return specific rev-list counts
    container_git() {
        case "$*" in
            *"rev-list HEAD..origin/main --count"*) echo "3" ;;
            *"rev-list origin/main..HEAD --count"*) echo "0" ;;
            *"status --porcelain"*) echo "" ;;
            *"symbolic-ref --short HEAD"*) echo "main" ;;
            *) echo "" ;;
        esac
    }
    export -f container_git

    # ... test the decision logic
}
```

**Full test case list (~22 cases):**

```
# --- State machine: branch relationship detection ---
@test "update: detects up-to-date state (behind=0, ahead=0)"
@test "update: detects fast-forward state (behind>0, ahead=0)"
@test "update: detects ahead-only state (behind=0, ahead>0)"
@test "update: detects diverged state (behind>0, ahead>0)"
@test "update: detects dirty working tree"
@test "update: detects non-default branch"

# --- State machine: action selection ---
@test "update: fast-forward uses git pull --ff-only"
@test "update: dirty fast-forward stashes before pull"
@test "update: dirty fast-forward restores stash after pull"
@test "update: diverged offers merge option"
@test "update: diverged offers squash-rebase option"
@test "update: ahead-only offers sync without pull"

# --- Helper functions ---
@test "update: sync_host_scripts detects changed files via git diff"
@test "update: sync_host_scripts copies only changed files"
@test "update: sync_host_scripts uses basename for host destination"
@test "update: check_build_changes detects Dockerfile modifications"
@test "update: check_build_changes detects docker-compose.yml modifications"
@test "update: finish_update calls sync and check_build_changes"
@test "update: prompt_choice accepts 'y' input"
@test "update: prompt_choice accepts 'n' input"

# --- Safety ---
@test "update: backup branch created before merge"
@test "update: locking prevents concurrent execution"
```

#### 2B. migrate_daaf Era Detection Tests

**File:** `tests/bash/migrate_daaf.bats` (extend existing)

The migrate script must identify which "era" the installation came from:
- **Era 1:** ZIP download — no `.git` directory or no remote configured
- **Era 2:** `git clone` — has remote but needs graft to upstream history

**Test implementation approach:** Source script in test mode, mock `container_git` and `container_exec` to return specific outputs, then test the era detection logic.

**Full test case list (~15 cases):**

```
# --- Era detection ---
@test "migrate: detects Era 1 (no git remote configured)"
@test "migrate: detects Era 2 (git remote exists, needs graft)"
@test "migrate: detects already-migrated (idempotency marker tag exists)"
@test "migrate: handles corrupted volume (no .git directory)"
@test "migrate: handles empty volume"

# --- Graft candidate search ---
@test "migrate: finds matching commit by blob tree comparison"
@test "migrate: handles no matching commit gracefully"
@test "migrate: correctly skips non-matching candidates"
@test "migrate: uses verbose git for error-sensitive operations"

# --- Helper functions ---
@test "migrate: container_git suppresses stderr"
@test "migrate: container_git_verbose preserves stderr"
@test "migrate: container_exec runs commands in container"
@test "migrate: prompt_choice handles user input"

# --- Safety ---
@test "migrate: backup runs before any destructive operation"
@test "migrate: locking prevents concurrent execution"
```

#### 2C. install Path Selection Tests

**File:** `tests/bash/install.bats` (extend existing)

**Full test case list (~12 cases):**

```
# --- Installation state detection ---
@test "install: fresh install (no compose file, no volume)"
@test "install: existing complete install detected (compose file + volume)"
@test "install: incomplete install detected (compose file, no volume)"
@test "install: force-reinstall bypasses existing check"

# --- Download and URL construction ---
@test "install: default branch is 'main'"
@test "install: DAAF_BRANCH overrides default branch"
@test "install: all 7 download URLs use scripts/host/ prefix"
@test "install: download failure exits non-zero"

# --- Container readiness ---
@test "install: readiness wait retries up to max attempts"
@test "install: readiness wait succeeds when CLAUDE.md found"
@test "install: readiness wait times out after 30 retries"

# --- Safety ---
@test "install: does not overwrite existing installation without force flag"
```

#### 2D. backup Edge Case Tests

**File:** `tests/bash/backup_daaf.bats` (extend existing)

**Full test case list (~10 cases):**

```
# --- Date-suffix generation ---
@test "backup: first backup of the day gets suffix 'a'"
@test "backup: second backup of the day gets suffix 'b'"
@test "backup: 26th backup reaches 'z' and errors gracefully"
@test "backup: suffix skips existing directories"

# --- Disk space ---
@test "backup: fails when disk space is insufficient"
@test "backup: passes with exactly 10% buffer available"
@test "backup: reports required vs available space on failure"

# --- Integrity verification ---
@test "backup: warns when backup size differs from source by >1%"
@test "backup: passes when sizes match within 1% tolerance"
@test "backup: file count check still runs alongside size check"
```

#### 2E. Pester Behavioral Tests (Parallel to BATS)

For each set of BATS tests above, write parallel Pester tests that cover the same logic in the .ps1 versions. The structure mirrors the BATS approach:

```powershell
Describe "update_daaf.ps1 state machine" {
    BeforeAll {
        $env:DAAF_TEST_MODE = "1"
        . "$PSScriptRoot/../../scripts/host/update_daaf.ps1"
    }

    AfterAll {
        Remove-Item Env:DAAF_TEST_MODE
    }

    Context "Branch relationship detection" {
        It "detects up-to-date state" {
            # Mock Compose-Git to return specific counts
            function Compose-Git {
                param([Parameter(ValueFromRemainingArguments)]$Args)
                switch -Wildcard ("$Args") {
                    "*rev-list HEAD..origin/main --count*" { "0" }
                    "*rev-list origin/main..HEAD --count*" { "0" }
                }
            }
            # Test detection logic...
        }
    }
}
```

**Estimated Pester test counts:**
- update_daaf.Tests.ps1: ~20 additional tests
- migrate_daaf.Tests.ps1: ~12 additional tests
- install.Tests.ps1: ~10 additional tests
- backup_daaf.Tests.ps1: ~8 additional tests

---

### Phase 3: Dry-Run Mode

**Goal:** Enable cross-platform smoke testing without Docker by adding a `DAAF_DRY_RUN` mode.

**Effort:** Medium (modify all 14 scripts)

**Depends on:** Phase 1 (can be done in parallel with Phase 2)

#### Design

When `DAAF_DRY_RUN=1` is set, scripts print what they would do instead of executing destructive operations. This is different from `DAAF_TEST_MODE`:

| Variable | Purpose | Who Uses It |
|----------|---------|-------------|
| `DAAF_TEST_MODE` | Source script without executing; for BATS/Pester function-level tests | Test framework |
| `DAAF_DRY_RUN` | Execute the script's logic but print instead of running Docker/curl/git | CI smoke tests, user verification |

#### Implementation Pattern (Bash)

```bash
# Wrapper for Docker commands
docker_cmd() {
    if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
        echo "[DRY-RUN] docker $*"
        return 0
    fi
    docker "$@"
}

# Wrapper for curl/download commands
download_cmd() {
    if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
        echo "[DRY-RUN] Would download: $2"  # $2 is the URL
        return 0
    fi
    curl "$@"
}
```

Replace direct `docker` and `curl` calls with `docker_cmd` and `download_cmd` throughout each script.

#### Implementation Pattern (PowerShell)

```powershell
function Invoke-DockerCmd {
    param([Parameter(ValueFromRemainingArguments)]$Arguments)
    if ($env:DAAF_DRY_RUN -eq "1") {
        Write-Host "[DRY-RUN] docker $($Arguments -join ' ')"
        return
    }
    & docker @Arguments
}
```

#### What Dry-Run Tests Verify

- Script loads and runs its full logic path without crashing
- All variable references resolve (no typos, no unset variables)
- Control flow reaches the expected endpoints
- Cross-platform syntax compatibility (bash 3.2 on macOS, PS 5.1 on Windows)
- Correct URL construction for downloads
- Correct path construction for Docker operations

---

### Phase 4: Cross-Platform Smoke CI Job

**Goal:** Run dry-run smoke tests on all three OS platforms in CI.

**Effort:** Low (add one job to ci-scripts.yml)

**Depends on:** Phase 3 (dry-run mode must be in place)

#### CI Workflow Addition

```yaml
# ---------------------------------------------------------------------------
# Job 8: Cross-platform smoke tests (dry-run, no Docker needed)
# ---------------------------------------------------------------------------
smoke-tests:
  name: Smoke Tests (${{ matrix.os }})
  runs-on: ${{ matrix.os }}
  strategy:
    fail-fast: false
    matrix:
      os: [ubuntu-latest, macos-latest, windows-latest]
  steps:
    - name: Checkout repository
      uses: actions/checkout@v4

    # Bash smoke tests (skip on windows — Git Bash is unreliable for complex scripts)
    - name: Smoke test .sh scripts (dry-run)
      if: matrix.os != 'windows-latest'
      run: |
        for script in scripts/host/*.sh; do
          echo "=== Smoke testing: $script ==="
          DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "$script" || {
            echo "FAILED: $script"
            exit 1
          }
        done

    # PowerShell smoke tests (all platforms — pwsh is available everywhere)
    - name: Smoke test .ps1 scripts (dry-run)
      shell: pwsh
      run: |
        foreach ($script in Get-ChildItem scripts/host/*.ps1) {
          Write-Host "=== Smoke testing: $($script.Name) ==="
          $env:DAAF_DRY_RUN = "1"
          $env:DAAF_NESTED = "1"
          & $script.FullName
          if ($LASTEXITCODE -ne 0) {
            Write-Host "FAILED: $($script.Name)"
            exit 1
          }
        }

    # Windows PowerShell 5.1 smoke test (windows only)
    - name: Smoke test .ps1 scripts on Windows PS 5.1 (dry-run)
      if: matrix.os == 'windows-latest'
      shell: powershell
      run: |
        foreach ($script in Get-ChildItem scripts/host/*.ps1) {
          Write-Host "=== Smoke testing (PS 5.1): $($script.Name) ==="
          $env:DAAF_DRY_RUN = "1"
          $env:DAAF_NESTED = "1"
          & $script.FullName
          if ($LASTEXITCODE -ne 0) {
            Write-Host "FAILED: $($script.Name)"
            exit 1
          }
        }
```

#### What This Matrix Catches

| Platform | Bash Version | PowerShell Version | Key Risks |
|----------|-------------|-------------------|-----------|
| ubuntu-latest | 5.x | pwsh 7.x | Baseline — should always pass |
| macos-latest | **3.2** (Apple-shipped) | pwsh 7.x | Bash 3.2 lacks associative arrays, mapfile, ${var,,}. Most common cross-platform failure point. |
| windows-latest | N/A (skip .sh) | **5.1** + pwsh 7.x | PS 5.1 $ErrorActionPreference quirks, alias differences, path separator issues |

---

### Phase 5: Docker Integration Tests (Nightly)

**Goal:** End-to-end testing with real Docker to verify the full lifecycle.

**Effort:** Medium (new workflow file, careful Docker setup)

**Depends on:** Phases 1-4 are not prerequisites; this is independent

#### Design Considerations

- Runs on a **schedule** (nightly), not on every push — Docker tests are slow (~5-10 min) and can be flaky
- Uses `ubuntu-latest` only (Docker is pre-installed)
- Tests the full lifecycle: install → run → update → backup → rebuild
- Each step verifies postconditions before proceeding
- Requires network access (downloads from GitHub)

#### New Workflow File: `.github/workflows/ci-integration.yml`

```yaml
name: CI - Integration Tests (Nightly)

on:
  schedule:
    - cron: '0 6 * * *'  # 6 AM UTC daily
  workflow_dispatch: {}   # Manual trigger for debugging

permissions:
  contents: read

jobs:
  lifecycle-test:
    name: Full Lifecycle Test
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Install DAAF
        run: bash scripts/host/install.sh
        env:
          DAAF_NESTED: "1"

      - name: Verify container is running
        run: docker compose ps | grep -q "running"

      - name: Verify CLAUDE.md exists in container
        run: docker compose exec -T daaf-docker test -f /daaf/CLAUDE.md

      - name: Run DAAF (quick command)
        run: bash scripts/host/run_daaf.sh echo "DAAF is working"
        env:
          DAAF_NESTED: "1"

      - name: Backup DAAF
        run: bash scripts/host/backup_daaf.sh
        env:
          DAAF_NESTED: "1"

      - name: Verify backup exists
        run: ls -la daaf-backups/

      - name: Update DAAF (should be no-op on fresh install)
        run: bash scripts/host/update_daaf.sh
        env:
          DAAF_NESTED: "1"

      - name: Rebuild DAAF
        run: bash scripts/host/rebuild_daaf.sh
        env:
          DAAF_NESTED: "1"

      - name: Verify container still running after rebuild
        run: docker compose ps | grep -q "running"

      - name: Final CLAUDE.md verification
        run: docker compose exec -T daaf-docker test -f /daaf/CLAUDE.md
```

#### What This Catches That Unit Tests Cannot

- Docker Compose version compatibility on GitHub runners
- Actual download integrity from raw.githubusercontent.com
- Real container startup timing and readiness detection
- Volume persistence across rebuild cycles
- Interaction between scripts (backup before update, sync after update)

---

## Priority and Sequencing

```
Phase 1 (Test Mode Guards)     ─── ✓ DONE (Session 2, 2026-04-26)
    │
    ├── Phase 2 (Enhanced Mocks) ── ✓ DONE (Session 2, 2026-04-26)
    │
    └── Phase 3 (Dry-Run Mode)  ── ✓ DONE (Session 3, 2026-04-27)
            │
            └── Phase 4 (Smoke CI) ── ✓ DONE (Session 3, 2026-04-27)

Phase 5 (Integration Tests)    ── MEDIUM EFFORT, INSURANCE ────→ End-to-end confidence
                                   (independent — can start anytime)
```

**Session plan:**
- **Session 2 (done):** Phase 1 + Phase 2 + flock fix + bash 3.2 audit + Dockerfile testing tools
- **Session 3 (done):** Phase 3 + Phase 4 (dry-run mode + cross-platform CI) + 2 gotchas added to skill
- **Session 4:** Phase 5 (integration tests) + any fixes from Phase 4 findings

## Files Modified By This Plan

| Phase | Files Created | Files Modified |
|-------|--------------|----------------|
| Phase 1 | None | 14 scripts in `scripts/host/` (add guard) |
| Phase 2 | None | 8 test files in `tests/bash/` and `tests/powershell/` (extend) |
| Phase 3 | None | 14 scripts in `scripts/host/` (add dry-run wrappers), 14 test files (add dry-run tests), `gotchas.md` (+2 entries) |
| Phase 4 | None | `.github/workflows/ci-scripts.yml` (add smoke job) |
| Phase 5 | `.github/workflows/ci-integration.yml` | None |

## Success Criteria

After all 5 phases:
- Every decision branch in update_daaf's state machine has a test
- Era detection in migrate_daaf has a test for each era type + edge cases
- All scripts pass dry-run smoke tests on ubuntu, macOS, and Windows
- A nightly CI run verifies the full install → run → update → backup → rebuild cycle with real Docker
- No script can be modified without the corresponding test suite catching behavioral regressions

## Open Questions for Session Start

All original open questions have been resolved across Sessions 2-3:

1. **Bash 3.2 compatibility:** ✓ Resolved (Session 2). Full audit complete — all 7 scripts clean. Only incompatibility was `flock` (replaced with portable `mkdir`-based locking).
2. **Pester behavioral tests:** ✓ Resolved (Session 2). 59 Pester behavioral tests implemented. Function scoping handled via dot-sourcing with `DAAF_TEST_MODE`.
3. **Docker integration test frequency:** ✓ Resolved (Session 2). Weekly chosen for Phase 5.
4. **Test mode guard documentation:** ✓ Resolved (Session 2). Documented in all 14 script headers.
