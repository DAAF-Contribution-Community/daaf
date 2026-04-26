# Script Bug Fixes Plan

**Created:** 2026-04-26
**Last Updated:** 2026-04-26
**Status:** Pending — verified all items still open as of 2026-04-26
**Context:** Discovered during shell-scripting skill authoring (Framework Development mode)
**Reference skill:** `shell-scripting` (load for standards and patterns)

---

## Execution Strategy

Fixes are organized into three waves by dependency and risk level. Each wave should be completed and manually tested before starting the next.

| Wave | Items | Theme | Files Touched |
|------|-------|-------|---------------|
| **Wave 1** | P1, P3, P6 | Quick safety and consistency fixes (isolated, low risk) | 4 files |
| **Wave 2** | P4, P5, H1, H2 | Preamble and error handling improvements | 5 files |
| **Wave 3** | P2 | Readiness loop stderr capture (6 files, coordinated change) | 6 files |

---

## Wave 1: Quick Safety and Consistency Fixes

### P1: bash-safety.sh fails OPEN when jq is missing [CRITICAL]

**File:** `.claude/hooks/bash-safety.sh`
**Issue:** When `jq` is not installed, `TOOL_NAME` extraction silently falls through to `exit 0`, allowing all commands through without safety inspection. The primary security hook can be completely bypassed.
**Root cause:** Lines 28-30 use `jq ... 2>/dev/null || TOOL_NAME=""`, which swallows the jq-missing error and makes `TOOL_NAME` empty. The `!= "Bash"` check then evaluates true, and the script exits 0 (allow).

**Fix:** Add an explicit `jq` existence check before `INPUT=$(cat)`, failing closed with exit 2. Use the known-good pattern from `enforce-file-first.sh` lines 29-34:

```bash
# --- Dependency check (fail-closed) ---
if ! command -v jq &>/dev/null; then
    echo "BLOCKED by bash-safety hook: jq is not installed (required for hook)" >&2
    exit 2
fi
```

**Verification:** Remove `jq` from PATH temporarily, run a Bash tool call, confirm it is blocked (exit 2) rather than allowed (exit 0).

---

### P3: view_logs.sh/.ps1 — no exit code check on docker compose exec [MEDIUM]

**Files:** `view_logs.sh` (~line 60), `view_logs.ps1` (~lines 72-74)

**Issue (.sh):** Bare `docker compose exec daaf-docker bash /daaf/scripts/generate_log_viewer.sh --archive` with no exit code check. If the inner script fails, the user sees no error.

**Issue (.ps1):** `$ErrorActionPreference` is set to `SilentlyContinue` around the call, and there is no `$LASTEXITCODE` check afterward.

**Fix (.sh):**
```bash
if ! docker compose exec daaf-docker bash /daaf/scripts/generate_log_viewer.sh --archive; then
    echo "" >&2
    echo "ERROR: Failed to generate log viewer." >&2
    echo "  The container may not be running, or there may be no session logs to display." >&2
fi
```

**Fix (.ps1):**
```powershell
$savedEAP = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
docker compose exec daaf-docker bash /daaf/scripts/generate_log_viewer.sh --archive
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Failed to generate log viewer." -ForegroundColor Red
    Write-Host "  The container may not be running, or there may be no session logs to display." -ForegroundColor Red
}
```

**Verification:** Stop the container, run `view_logs`, confirm error message appears.

---

### P6: Wording inconsistency in Docker-not-installed messages [LOW]

**Files:** `view_logs.sh` (~line 33), `view_logs.ps1` (~line 36)

**Issue:** `view_logs.sh` says `"Docker is not installed or not in your PATH."` while every other script uses the longer, more helpful form.

**Fix:** Replace with the standard wording used across all other scripts:
```
"Docker is either not installed or not configured properly in your system PATH to allow it to be used from Terminal."
```

Apply to both `.sh` and `.ps1` versions.

**Verification:** Visual inspection of the message text.

---

## Wave 2: Preamble and Error Handling Improvements

### P4: run_with_capture.sh — missing set flags and bc dependency [HIGH]

**File:** `scripts/run_with_capture.sh`

**Issue (a):** Line 19 has only `set -o pipefail` — missing both `-e` and `-u`. This means:
- Unset variables silently expand to empty strings (no `-u`)
- If any command between Python execution and log append fails (e.g., permissions on `cat >>`), the script continues silently (no `-e`)

**Issue (b):** Line 58 uses `bc` for duration calculation with no dependency check. If `bc` is missing, duration is empty/errored.

**Fix (a):** Change preamble to `set -euo pipefail`. Review the script for any commands that intentionally fail (they'll need `|| true` or `if !` guards). The Python script execution on line ~35 already captures its exit code explicitly, so that path should be compatible.

**Fix (b):** Replace `bc`-based floating-point duration with bash integer arithmetic:
```bash
# Replace date +%s.%N with date +%s (integer seconds)
START_TIME=$(date +%s)
# ... python execution ...
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
```
This eliminates the `bc` dependency entirely. Losing sub-second precision is acceptable for execution logs.

**Verification:** Run a script through `run_with_capture.sh` in a container without `bc` installed. Confirm duration is recorded as integer seconds.

---

### P5: update_daaf.ps1 — stderr discarded on git fetch [MEDIUM]

**File:** `update_daaf.ps1` (~line 566)

**Issue:** The `Compose-Git-Null` function (lines 121-130) discards all output including stderr via `2>&1 | Out-Null`. When `git fetch` fails, the actual error message (auth failure, network timeout, DNS resolution) is lost. The user gets a generic "Failed to fetch" with guessed causes instead of the real error.

**Fix:** Create a new function variant or modify the fetch call to capture stderr:
```powershell
# Instead of Compose-Git-Null, capture output for the fetch specifically:
$fetchOutput = docker compose exec -T daaf-docker git -C /daaf fetch $UpstreamRemote 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to fetch from $UpstreamRemote" -ForegroundColor Red
    Write-Host "  Git reported: $fetchOutput" -ForegroundColor Red
    # ... existing recovery guidance ...
}
```

**Verification:** Temporarily use a non-existent remote name, run update, confirm the actual git error message is displayed.

---

### H1: Hook scripts — shebang inconsistency [LOW]

**Files:** `.claude/hooks/context-reporter.sh`, `.claude/hooks/audit-log.sh` (and likely others)

**Issue:** These hooks use `#!/bin/bash` instead of the skill-standard `#!/usr/bin/env bash`. The `env` form is more portable (finds bash via PATH rather than assuming `/bin/bash`).

**Fix:** Update shebang to `#!/usr/bin/env bash` in all hook scripts that currently use `#!/bin/bash`. Grep for the pattern across `.claude/hooks/`:
```bash
grep -l '#!/bin/bash' .claude/hooks/*.sh
```

**Verification:** `head -1` on each hook file after the fix.

---

### H2: Hook scripts — missing set -u [LOW]

**Files:** `.claude/hooks/context-reporter.sh`, `.claude/hooks/audit-log.sh`

**Issue:** These hooks have no `set -u` (nounset). While they intentionally omit `set -e` (they must never block tool execution), `set -u` would catch typos in variable names without affecting the fail-open behavior.

**Fix:** Add `set -u` to both scripts (NOT `set -e` — these hooks must exit 0 on all error paths). Use `${VAR:-}` for any intentionally optional variables.

**Verification:** Run a tool call, confirm the hooks still exit 0 successfully. Check that no unset variable warnings appear in the hook stderr.

---

## Wave 3: Readiness Loop Stderr Capture (Coordinated)

### P2: Container readiness loops swallow stderr [HIGH]

**Files (all 6):**
| Shell | File | Approximate Location |
|-------|------|---------------------|
| Bash | `install.sh` | ~line 130 |
| Bash | `rebuild_daaf.sh` | ~line 153 |
| Bash | `update_daaf.sh` | ~line 384 |
| PS1 | `install.ps1` | ~line 152 |
| PS1 | `rebuild_daaf.ps1` | ~line 178 |
| PS1 | `update_daaf.ps1` | ~line 450 |

**Issue:** All six readiness loops use `2>/dev/null` (sh) or `2>&1 | Out-Null` (ps1). If the container is in a crash loop, fails to start, or has a configuration error, the user sees only "Container did not become ready within 60 seconds" with zero diagnostic information.

**Fix pattern (.sh):**
```bash
READY_LOG=$(mktemp)
trap 'rm -f "$READY_LOG"' EXIT  # (merge with existing EXIT trap if present)

elapsed=0
until docker compose exec -T daaf-docker true </dev/null 2>>"$READY_LOG"; do
    elapsed=$((elapsed + 2))
    if [ "$elapsed" -ge 60 ]; then
        echo ""
        echo "ERROR: Container did not become ready within 60 seconds." >&2
        echo "  Docker reported:" >&2
        tail -5 "$READY_LOG" | sed 's/^/    /' >&2
        echo "" >&2
        echo "  Try: docker compose logs daaf-docker" >&2
        rm -f "$READY_LOG"
        exit 12
    fi
    sleep 2
done
rm -f "$READY_LOG"
```

**Fix pattern (.ps1):**
```powershell
$readyLog = [System.IO.Path]::GetTempFileName()
try {
    $elapsed = 0
    while ($elapsed -lt 60) {
        docker compose exec -T daaf-docker true 2>> $readyLog
        if ($LASTEXITCODE -eq 0) { break }
        Start-Sleep -Seconds 2
        $elapsed += 2
    }
    if ($elapsed -ge 60) {
        Write-Host ""
        Write-Host "ERROR: Container did not become ready within 60 seconds." -ForegroundColor Red
        Write-Host "  Docker reported:" -ForegroundColor Red
        Get-Content $readyLog -Tail 5 | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        Write-Host ""
        Write-Host "  Try: docker compose logs daaf-docker" -ForegroundColor Yellow
        exit 12
    }
} finally {
    Remove-Item $readyLog -ErrorAction SilentlyContinue
}
```

**Why Wave 3:** This is the most complex change — it touches 6 files with a coordinated pattern. Each file's readiness loop has slightly different surrounding context (existing traps, variable names, progress step numbers). Implementing it last means the simpler fixes have already been tested and committed, reducing risk.

**Verification:** Stop Docker daemon, run `install.sh`, confirm the timeout message includes actual Docker error output (e.g., "Cannot connect to the Docker daemon"). Then start the daemon but break the container (e.g., bad entrypoint), confirm the readiness timeout shows container-specific errors.

---

## Execution Notes

- All fixes should follow patterns codified in the `shell-scripting` skill (load it before starting)
- After each wave, set `chmod +x` on any modified `.sh` files and verify with `git ls-files -s`
- Test each wave manually on both platforms before committing:
  - macOS/Linux for `.sh` scripts
  - Windows for `.ps1` scripts
- Commit each wave separately with a descriptive message
- The `run_with_capture.sh` fix (P4) affects the audit trail — test with a sample Python script to ensure execution logs are still appended correctly
