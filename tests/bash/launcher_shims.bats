#!/usr/bin/env bats
# ============================================================================
# Tests for the double-click launcher shims: DAAF.command (macOS) and
# daaf.bat (Windows).
# ============================================================================
# These are thin shims over daaf.sh / daaf.ps1 (the real Control Panels), so
# the tests are deliberately static: they assert the load-bearing guards are
# present (the working-directory cd, the per-process ExecutionPolicy bypass,
# the handoff to the underlying panel) and that the committed file modes are
# correct. daaf.bat cannot be executed on this Linux host; only its content is
# checked. DAAF.command is additionally parsed with `bash -n`.
# ============================================================================

load 'test_helper'

COMMAND_SHIM="${REPO_ROOT}/scripts/host/DAAF.command"
BAT_SHIM="${REPO_ROOT}/scripts/host/daaf.bat"

# Per-task convention: any runtime fixtures live under scripts/scratch/ and are
# cleaned up by the test itself. teardown() removes this test's fixtures even if
# an assertion aborts mid-test.
teardown() {
    rm -rf "${REPO_ROOT}/scripts/scratch/launcher_shims_rt_${BATS_TEST_NUMBER:-x}" 2>/dev/null || true
}

# --- DAAF.command (macOS) ---------------------------------------------------

@test "DAAF.command parses without errors" {
    run bash -n "$COMMAND_SHIM"
    assert_success
}

@test "DAAF.command cd's into its own directory before handoff" {
    run grep -F 'cd "$(dirname "$0")"' "$COMMAND_SHIM"
    assert_success
}

@test "DAAF.command hands off to daaf.sh via exec" {
    run grep -F 'exec bash daaf.sh' "$COMMAND_SHIM"
    assert_success
}

@test "DAAF.command holds the window open on failure" {
    run grep -F 'read -r -p' "$COMMAND_SHIM"
    assert_success
}

@test "DAAF.command is committed executable (git mode 100755)" {
    run git -C "$REPO_ROOT" ls-files -s scripts/host/DAAF.command
    assert_success
    assert_output --partial "100755"
}

# Runtime end-to-end: prove the cd + `exec bash daaf.sh` handoff AND that DAAF_*
# environment variables pass through `exec` to the delegate unchanged (the HS7
# passthrough claim). We stage a temp dir containing a stub daaf.sh that echoes a
# sentinel and the inherited DAAF_DRY_RUN value, plus a copy of the real
# DAAF.command; running the shim from an unrelated CWD must cd into the fixture,
# exec the stub, and surface both the sentinel and the passed-through value.
@test "DAAF.command execs daaf.sh from its own dir and passes env through (runtime)" {
    local fixture="${REPO_ROOT}/scripts/scratch/launcher_shims_rt_${BATS_TEST_NUMBER}"
    rm -rf "$fixture"
    mkdir -p "$fixture"

    cat > "$fixture/daaf.sh" <<'STUB'
echo "STUB_DAAF_SH_REACHED cwd=$(pwd)"
echo "PASSTHROUGH=${DAAF_DRY_RUN:-unset}"
exit 0
STUB
    cp "$COMMAND_SHIM" "$fixture/DAAF.command"

    # The bats CWD is unrelated to the fixture, so the shim's own `cd "$(dirname
    # "$0")"` is what must land us in the fixture. Invoke via `bash <path>` so $0
    # is the fixture path (no exec bit needed on the copy); DAAF_DRY_RUN is set
    # in the child environment to prove passthrough across `exec`.
    run env DAAF_DRY_RUN=sentinel42 bash "$fixture/DAAF.command"

    assert_success
    assert_output --partial "STUB_DAAF_SH_REACHED"
    assert_output --partial "PASSTHROUGH=sentinel42"
    assert_output --partial "cwd=${fixture}"
}

# --- daaf.bat (Windows) -----------------------------------------------------

@test "daaf.bat changes to its own directory with cd /d %~dp0" {
    run grep -F 'cd /d "%~dp0"' "$BAT_SHIM"
    assert_success
}

@test "daaf.bat invokes PowerShell with a per-process ExecutionPolicy Bypass" {
    run grep -F 'ExecutionPolicy Bypass' "$BAT_SHIM"
    assert_success
}

@test "daaf.bat runs daaf.ps1 directly via -File (in this console)" {
    run grep -F 'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0daaf.ps1"' "$BAT_SHIM"
    assert_success
}

@test "daaf.bat holds the window open on error" {
    run grep -Fi 'pause' "$BAT_SHIM"
    assert_success
}

@test "daaf.bat is committed non-executable (git mode 100644)" {
    run git -C "$REPO_ROOT" ls-files -s scripts/host/daaf.bat
    assert_success
    assert_output --partial "100644"
}
