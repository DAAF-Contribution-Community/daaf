#!/usr/bin/env bats
# ============================================================================
# Tests for check_workspace_invariants.sh -- live-filesystem workspace lint
# ============================================================================
# WHY THIS FILE EXISTS:
#
# check_workspace_invariants.sh is the durable, mechanical detection layer for
# workspace invariants that git cannot see (untracked scratch). It is run before
# checkpoints by agents (per CLAUDE.md § Scratch Files and the daaf-orchestrator
# framework-development-mode reference). Two incidents motivate the two invariants
# it enforces:
#
#   Invariant 1 (no unauthorized symlinks): scratch probes repeatedly left
#   symlinks with tab/newline names under scripts/scratch/, breaking real user
#   backups three times on 2026-07-14.
#
#   Invariant 2 (no repo-root leak artifacts): on 2026-07-14 a `migrate_daaf.sh`
#   dry-run run with CWD=/daaf scattered 13 zero-byte stub files plus a
#   `docker-compose.yml.pre-migrate` at the repo root; an `install.sh` dry-run in
#   the same position leaves a stray `daaf-docker/` directory. This test file is
#   the regression guard for that detection layer. See session notes at
#   research/2026-07-15_FrameworkDev_CwdLeakRootStubs/.
#
# All fixture trees live under TEST_DIR (created by common_setup, removed by
# common_teardown's `rm -rf TEST_DIR`) — the checker is pointed at them via the
# DAAF_INVARIANT_ROOT override. NO fixture ever plants a violation in the real
# /daaf. common_teardown removes symlinks along with the tree, and every fixture
# stays inside TEST_DIR, so nothing escapes.
# ============================================================================

load 'test_helper'

# Path to the script under test.
CHECKER="${REPO_ROOT}/scripts/check_workspace_invariants.sh"

setup() {
    common_setup
    export CHECKER
}

teardown() {
    common_teardown
}

# =========================================================================
# Syntax
# =========================================================================

@test "check_workspace_invariants.sh parses without errors" {
    run bash -n "$CHECKER"
    assert_success
}

# =========================================================================
# Clean tree
# =========================================================================

@test "clean tree: exit 0 and prints the OK line" {
    # TEST_DIR is empty apart from what common_setup created (nothing).
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_success
    assert_output --partial "OK: workspace invariants satisfied"
}

@test "clean tree with -q: exit 0 and OK line suppressed" {
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER" -q
    assert_success
    refute_output --partial "OK:"
}

# =========================================================================
# Invariant 1: symlinks
# =========================================================================

@test "unauthorized symlink: exit 1 and the path is listed" {
    ln -s /some/target "${TEST_DIR}/rogue_link"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "unauthorized symlink"
    assert_output --partial "rogue_link"
}

@test "allowlisted symlink: passes (allowlist prefix exempts it)" {
    # The ALLOWLIST is a hardcoded ABSOLUTE /daaf/... prefix, and find emits paths
    # rooted at DAAF_INVARIANT_ROOT — so a TEST_DIR fixture path can never begin
    # with the /daaf allowlist string, and the exemption can't be exercised via
    # the root override. The faithful check is the LIVE repo: it contains real
    # symlinks under the allowlisted syslibs_glpk subtree, and the checker must
    # pass with them all counted as allowlisted. (This reads /daaf but writes
    # nothing there — no fixture escapes TEST_DIR.)
    run bash "$CHECKER"
    assert_success
    assert_output --partial "all allowlisted or none present"
}

# =========================================================================
# Invariant 2: repo-root leak artifacts
# =========================================================================

@test "zero-byte file at root: exit 1 and listed" {
    : > "${TEST_DIR}/stub_zero.txt"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "leak artifact"
    assert_output --partial "stub_zero.txt"
}

@test "zero-byte file BELOW maxdepth 1: passes (scope check)" {
    mkdir -p "${TEST_DIR}/nested"
    : > "${TEST_DIR}/nested/deep_zero.txt"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_success
    assert_output --partial "OK: workspace invariants satisfied"
}

@test "*.pre-migrate file at root: exit 1 and listed" {
    # A NON-empty pre-migrate backup, to prove the match is on the name glob and
    # not merely on zero-size (the two predicates are ORed).
    printf 'name: daaf\n' > "${TEST_DIR}/docker-compose.yml.pre-migrate"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "leak artifact"
    assert_output --partial "docker-compose.yml.pre-migrate"
}

@test "stray daaf-docker/ dir at root: exit 1 and listed" {
    mkdir -p "${TEST_DIR}/daaf-docker"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "leak artifact"
    assert_output --partial "daaf-docker"
}

@test "non-empty regular file at root: passes (not a leak-artifact shape)" {
    # A normal, non-zero, non-.pre-migrate file at the root must NOT be flagged.
    printf 'hello\n' > "${TEST_DIR}/README.md"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_success
}

# =========================================================================
# Control-character rendering (both invariants use cat -A)
# =========================================================================

@test "filename with a control char is rendered escaped in output" {
    # A zero-byte file whose name contains a literal TAB. cat -A renders TAB as
    # ^I, so a reviewer can see the otherwise-invisible character.
    local tabname
    tabname="$(printf 'stub\tzero')"
    : > "${TEST_DIR}/${tabname}"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    # cat -A renders the embedded tab as ^I.
    assert_output --partial "stub^Izero"
}

# =========================================================================
# Both invariants violated at once: exit 1, both reported
# =========================================================================

@test "symlink + root leak together: exit 1 and both violations reported" {
    ln -s /some/target "${TEST_DIR}/rogue_link"
    : > "${TEST_DIR}/stub_zero.txt"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "unauthorized symlink"
    assert_output --partial "leak artifact"
}
