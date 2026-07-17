#!/usr/bin/env bats
# ============================================================================
# Tests for test_migration.sh -- DAAF Migration/Fresh-Install Test Harness
# ============================================================================
# test_migration.sh is a TRACKED, dev-only end-to-end harness (committed for CI
# unit coverage as of 203c56c, but excluded from the updater's host-script sync
# -- it drives real Docker and never ships to user hosts). These tests cover its
# PURE, docker-free logic: the tm_* helper functions, unit-testable via
# `DAAF_TEST_MODE=1 source` (the source-only guard returns before any
# execution), plus content pins for field-run regression fixes.
#
# What is intentionally NOT covered here: the docker-driven phases (install,
# migrate, update, multi-instance). Those require a live Docker daemon and are
# exercised by running the harness itself; a bats suite cannot stand in for that.
# ============================================================================

load 'test_helper'

setup() {
    common_setup
    mock_docker
    mock_curl
    # Source the harness in test mode: this defines the tm_* pure functions and
    # returns at the DAAF_TEST_MODE guard before any execution. Neutralize the
    # set -euo pipefail inherited from the harness preamble for the test body,
    # and initialize the arg-parse globals tm_parse_args writes to.
    DAAF_TEST_MODE=1 source "${REPO_ROOT}/scripts/host/test_migration.sh"
    trap - ERR
    set +eu
    RUN_ALL=0
    AUTO_MODE=0
    SKIP_MULTI_CLI=0
}

teardown() {
    common_teardown
}

# --- Syntax ---

@test "test_migration.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/test_migration.sh"
    assert_success
}

# --- tm_detect_era ---

@test "tm_detect_era maps each version to its authentic era" {
    run tm_detect_era v1.0.0
    assert_output "1"
    run tm_detect_era v2.0.0
    assert_output "2"
    run tm_detect_era v2.0.1
    assert_output "2"
    run tm_detect_era v2.1.0
    assert_output "3"
    run tm_detect_era daaf_dev
    assert_output "3"
}

# --- tm_version_ge_floor (Era-3 v2.1.0 floor, numeric not lexical) ---

@test "tm_version_ge_floor: v2.1.0 is at/above floor (rc 0)" {
    run tm_version_ge_floor v2.1.0
    [ "${status}" -eq 0 ]
}

@test "tm_version_ge_floor: v2.10.0 is above floor, not below (rc 0)" {
    # A lexical compare would wrongly sort v2.10.0 below v2.2.0; the numeric
    # encoding keeps it above the v2.1.0 floor.
    run tm_version_ge_floor v2.10.0
    [ "${status}" -eq 0 ]
}

@test "tm_version_ge_floor: v2.0.1 is below floor (rc 1)" {
    run tm_version_ge_floor v2.0.1
    [ "${status}" -eq 1 ]
}

@test "tm_version_ge_floor: a branch name is not a vX.Y.Z tag (rc 2)" {
    run tm_version_ge_floor daaf_dev
    [ "${status}" -eq 2 ]
}

# --- tm_matrix_vectors ---

@test "tm_matrix_vectors returns the default vector list" {
    run tm_matrix_vectors
    assert_output "fresh v1.0.0 v2.0.1 v2.1.0"
}

@test "tm_matrix_vectors honors DAAF_TEST_MATRIX_VERSIONS override" {
    export DAAF_TEST_MATRIX_VERSIONS="alpha beta"
    run tm_matrix_vectors
    assert_output "alpha beta"
    unset DAAF_TEST_MATRIX_VERSIONS
}

# --- tm_emit_summary / tm_parse_summary_field round-trip ---

@test "tm_emit_summary emits the fixed TEST_MIGRATION_SUMMARY grammar" {
    run tm_emit_summary v2.1.0 PASS 12 0 3
    assert_success
    assert_output "TEST_MIGRATION_SUMMARY vector=v2.1.0 status=PASS pass=12 fail=0 skip=3"
}

@test "tm_parse_summary_field round-trips every field" {
    line="TEST_MIGRATION_SUMMARY vector=v2.0.1 status=FAIL pass=9 fail=2 skip=1"
    run tm_parse_summary_field "${line}" vector
    assert_output "v2.0.1"
    run tm_parse_summary_field "${line}" status
    assert_output "FAIL"
    run tm_parse_summary_field "${line}" pass
    assert_output "9"
    run tm_parse_summary_field "${line}" fail
    assert_output "2"
    run tm_parse_summary_field "${line}" skip
    assert_output "1"
}

@test "tm_emit_summary output parses back to its inputs" {
    emitted="$(tm_emit_summary fresh PASS 20 0 5)"
    run tm_parse_summary_field "${emitted}" vector
    assert_output "fresh"
    run tm_parse_summary_field "${emitted}" status
    assert_output "PASS"
    run tm_parse_summary_field "${emitted}" pass
    assert_output "20"
    run tm_parse_summary_field "${emitted}" skip
    assert_output "5"
}

# --- tm_classify_status ---

@test "tm_classify_status: work never reached => INFRA" {
    run tm_classify_status false 0
    assert_output "INFRA"
}

@test "tm_classify_status: work reached with failures => FAIL" {
    run tm_classify_status true 2
    assert_output "FAIL"
}

@test "tm_classify_status: work reached, zero failures => PASS" {
    run tm_classify_status true 0
    assert_output "PASS"
}

@test "tm_classify_status: not-reached wins even with zero failures" {
    run tm_classify_status false 0
    assert_output "INFRA"
}

# --- tm_matrix_verdict (reconciles parsed status against the child exit code) ---

@test "tm_matrix_verdict: PASS with rc 0 => vector passes (rc 0)" {
    run tm_matrix_verdict PASS 0
    [ "${status}" -eq 0 ]
}

@test "tm_matrix_verdict: PASS with a nonzero rc => vector fails (rc 1)" {
    # The reconciliation fix: a summary line can report PASS while the child
    # process exited nonzero -- that must fail the vector, not pass it.
    run tm_matrix_verdict PASS 1
    [ "${status}" -eq 1 ]
}

@test "tm_matrix_verdict: FAIL status fails even with a zero rc" {
    run tm_matrix_verdict FAIL 0
    [ "${status}" -eq 1 ]
}

@test "tm_matrix_verdict: INFRA status fails" {
    run tm_matrix_verdict INFRA 0
    [ "${status}" -eq 1 ]
}

@test "tm_matrix_verdict: an UNKNOWN(rc=N) placeholder fails" {
    run tm_matrix_verdict "UNKNOWN(rc=5)" 5
    [ "${status}" -eq 1 ]
}

@test "tm_matrix_verdict: rc defaults to 0 when omitted (PASS passes)" {
    run tm_matrix_verdict PASS
    [ "${status}" -eq 0 ]
}

# --- tm_parse_args (sets globals; must be called directly, not via `run`) ---

@test "tm_parse_args: --all sets RUN_ALL and implies AUTO_MODE" {
    tm_parse_args --all
    [ "${RUN_ALL}" = "1" ]
    [ "${AUTO_MODE}" = "1" ]
    [ "${SKIP_MULTI_CLI}" = "0" ]
}

@test "tm_parse_args: --auto sets AUTO_MODE only" {
    tm_parse_args --auto
    [ "${RUN_ALL}" = "0" ]
    [ "${AUTO_MODE}" = "1" ]
    [ "${SKIP_MULTI_CLI}" = "0" ]
}

@test "tm_parse_args: --skip-multi-instance sets SKIP_MULTI_CLI only" {
    tm_parse_args --skip-multi-instance
    [ "${RUN_ALL}" = "0" ]
    [ "${AUTO_MODE}" = "0" ]
    [ "${SKIP_MULTI_CLI}" = "1" ]
}

@test "tm_parse_args: combined flags accumulate" {
    tm_parse_args --auto --skip-multi-instance
    [ "${RUN_ALL}" = "0" ]
    [ "${AUTO_MODE}" = "1" ]
    [ "${SKIP_MULTI_CLI}" = "1" ]
}

@test "tm_parse_args: unknown tokens are ignored (env-driven child invocation)" {
    tm_parse_args
    [ "${RUN_ALL}" = "0" ]
    [ "${AUTO_MODE}" = "0" ]
    [ "${SKIP_MULTI_CLI}" = "0" ]
    tm_parse_args --nonsense positional
    [ "${RUN_ALL}" = "0" ]
    [ "${AUTO_MODE}" = "0" ]
    [ "${SKIP_MULTI_CLI}" = "0" ]
}

# --- tm_conflict_autoresolvable (round-5 conflict-journey eligibility) ---
# Eligible ONLY when a merge is in progress (MERGE_HEAD non-empty) AND the
# unmerged set is EXACTLY CLAUDE.md. Everything else fails loudly.

@test "tm_conflict_autoresolvable: MERGE_HEAD + exactly CLAUDE.md => eligible (rc 0)" {
    run tm_conflict_autoresolvable "abc123def456" "CLAUDE.md"
    [ "${status}" -eq 0 ]
}

@test "tm_conflict_autoresolvable: tolerates trailing CR/whitespace on both inputs" {
    # container_git strips \r, but the helper re-normalizes so a stray CR or
    # surrounding whitespace on either capture cannot flip the decision.
    run tm_conflict_autoresolvable $'abc123\r' $'  CLAUDE.md \r'
    [ "${status}" -eq 0 ]
}

@test "tm_conflict_autoresolvable: empty MERGE_HEAD => not eligible (rc 1)" {
    # No merge in progress (a nonzero update exit for some OTHER reason).
    run tm_conflict_autoresolvable "" "CLAUDE.md"
    [ "${status}" -eq 1 ]
    run tm_conflict_autoresolvable $'  \r' "CLAUDE.md"
    [ "${status}" -eq 1 ]
}

@test "tm_conflict_autoresolvable: multi-file unmerged set => not eligible (rc 1)" {
    # A conflict that spans CLAUDE.md AND another file is not auto-resolvable.
    run tm_conflict_autoresolvable "abc123" $'CLAUDE.md\nDockerfile'
    [ "${status}" -eq 1 ]
}

@test "tm_conflict_autoresolvable: wrong single file => not eligible (rc 1)" {
    # A Dockerfile-only (Class B(i)) conflict must fail loudly, not auto-resolve.
    run tm_conflict_autoresolvable "abc123" "Dockerfile"
    [ "${status}" -eq 1 ]
}

@test "tm_conflict_autoresolvable: MERGE_HEAD present but empty unmerged set => not eligible (rc 1)" {
    run tm_conflict_autoresolvable "abc123" ""
    [ "${status}" -eq 1 ]
}

# --- Field-run 4 regression pins (2026-07-17) ---
# Content pins for fixes whose absence caused real field failures. The
# docker-driven phases cannot execute under bats, so these pin the load-bearing
# lines instead: reverting a fix breaks the corresponding pin by construction.

@test "pin: driven update is branch-faithful (DAAF_BRANCH on ALL update drives)" {
    # Without DAAF_BRANCH the updater auto-detects main and merges GitHub
    # origin/main instead of the branch under test -- field run 4 never got the
    # noble Dockerfile, so no rebuild was exercised and the noble check failed.
    # THREE branch-faithful drives now: the first drive, the conflict-journey
    # resume re-drive (round 5), and the self-update two-run second drive.
    run grep -cF 'DAAF_BRANCH="${MIGRATION_BRANCH}" DAAF_NESTED=1 bash "${HOST_DIR}/update_daaf.sh"' "${REPO_ROOT}/scripts/host/test_migration.sh"
    assert_success
    [ "${output}" -eq 3 ]
}

@test "pin: Era-3 tag normalization completes refspec, origin/main, and tracking" {
    # The tag-pinned replay clone lacks the origin/main ref a real
    # `clone -b main` install had; without these three commands migrate's
    # set-upstream fails and the tracking checks FAIL (field run 4, v2.1.0).
    run grep -cF 'git -C /daaf remote set-branches origin main' "${REPO_ROOT}/scripts/host/test_migration.sh"
    assert_success
    [ "${output}" -ge 1 ]
    run grep -cF 'git -C /daaf fetch --depth 1 origin main' "${REPO_ROOT}/scripts/host/test_migration.sh"
    assert_success
    [ "${output}" -ge 1 ]
    run grep -cF 'git -C /daaf branch --set-upstream-to=origin/main main' "${REPO_ROOT}/scripts/host/test_migration.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "pin: Class D comparison exempts the sanctioned DAAF_BRANCH persist" {
    # The driven update runs with env-origin DAAF_BRANCH (branch fidelity),
    # and update_daaf INTENTIONALLY persists that choice into
    # environment_settings.txt -- both Class D cksum sites must therefore
    # filter the active DAAF_BRANCH line, or the sanctioned write reads as
    # fixture loss (quality-review finding, field-run-4 fix pass).
    run grep -cF "grep -v '^DAAF_BRANCH='" "${REPO_ROOT}/scripts/host/test_migration.sh"
    assert_success
    [ "${output}" -eq 2 ]
}

@test "pin: Era-1 verify failure surfaces raw git stderr + ownership probes" {
    # container_git discards stderr, which hid the v1.0.0 INFRA diagnosis
    # (suspected modern-git dubious-ownership refusal). The failure path must
    # print the raw git error and the /daaf ownership.
    run grep -cF 'Raw git probe output' "${REPO_ROOT}/scripts/host/test_migration.sh"
    assert_success
    [ "${output}" -ge 1 ]
    run grep -cF 'ls -ldn /daaf /daaf/.git' "${REPO_ROOT}/scripts/host/test_migration.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- Field-run 5 regression pins (2026-07-17) ---
# The conflict -> resolve -> resume journey: a nonzero first driven update whose
# unmerged set is exactly CLAUDE.md is not a FAIL -- the harness simulates the
# guided resolution and re-drives the resumable updater, scoring the whole journey.

@test "pin: eligible conflict is resolved via checkout --theirs + re-append + commit" {
    # The simulated resolution mirrors what a real user does: take upstream's
    # CLAUDE.md, re-preserve the planted Class C prose, commit with the frozen
    # message the updater's resume path keys nothing on but the audit reads.
    run grep -cF 'container_git checkout --theirs -- CLAUDE.md' "${REPO_ROOT}/scripts/host/test_migration.sh"
    assert_success
    [ "${output}" -ge 1 ]
    run grep -cF 'Resolved merge conflicts from DAAF update (harness-simulated guided resolution)' "${REPO_ROOT}/scripts/host/test_migration.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "pin: conflict journey is scored by its own check, and the first exit is not failed" {
    # The resumed run carries the journey check; the eligibility gate routes the
    # first nonzero exit into an observe_note, never a bare FAIL.
    run grep -cF 'Update conflict journey completed (conflict -> resolved -> resumed update exit' "${REPO_ROOT}/scripts/host/test_migration.sh"
    assert_success
    [ "${output}" -eq 2 ]
    run grep -cF 'tm_conflict_autoresolvable "${MERGE_HEAD}" "${UNMERGED}"' "${REPO_ROOT}/scripts/host/test_migration.sh"
    assert_success
    [ "${output}" -eq 1 ]
}

@test "pin: mid-merge state is captured, not live-grepped (lint 9)" {
    # capture-then-test: MERGE_HEAD + the unmerged set are captured into vars and
    # passed to the pure eligibility helper, never piped into a live grep -q.
    run grep -cF 'container_git rev-parse -q --verify MERGE_HEAD' "${REPO_ROOT}/scripts/host/test_migration.sh"
    assert_success
    [ "${output}" -ge 1 ]
    run grep -cF 'container_git diff --name-only --diff-filter=U' "${REPO_ROOT}/scripts/host/test_migration.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- Field-run 5 finding 3b pins (git safe.directory exemption window) ---
# The harness's OWN pre-migrate old-container git ops (phase 3 era-verify, phase
# 4/5 fixture plants) hit modern git's dubious-ownership fatal on the root-owned
# Era-1 (v1.0.0) payload. A guarded safe.directory exemption is OPENED before the
# first such op and CLOSED before migrate runs -- but only if the harness added
# it -- so migrate's own section-4b fix is still exercised end-to-end. Docker-
# driven, so these pin the load-bearing source ordering/guards.

@test "pin: safe.directory window opens before the first phase-3 old-container git op" {
    local sh="${REPO_ROOT}/scripts/host/test_migration.sh"
    local p3 add_ln firstgit
    p3=$(grep -n 'Verify Era ${TEST_ERA} state' "${sh}" | head -1 | cut -d: -f1)
    add_ln=$(grep -n 'container_exec git config --global --add safe.directory /daaf' "${sh}" | head -1 | cut -d: -f1)
    # The first container_git call site strictly AFTER the phase-3 header (the OPEN
    # block itself uses container_exec, not container_git, so it never matches).
    firstgit=$(grep -n 'container_git ' "${sh}" | awk -F: -v p="${p3}" '$1>p {print $1; exit}')
    [ -n "${p3}" ]
    [ -n "${add_ln}" ]
    [ -n "${firstgit}" ]
    [ "${add_ln}" -gt "${p3}" ]
    [ "${add_ln}" -lt "${firstgit}" ]
}

@test "pin: safe.directory window closes before migrate is invoked" {
    local sh="${REPO_ROOT}/scripts/host/test_migration.sh"
    local add_ln unset_ln migrate_ln
    add_ln=$(grep -n 'container_exec git config --global --add safe.directory /daaf' "${sh}" | head -1 | cut -d: -f1)
    unset_ln=$(grep -n 'container_exec git config --global --unset-all safe.directory' "${sh}" | head -1 | cut -d: -f1)
    migrate_ln=$(grep -n 'bash migrate_daaf.sh 2>&1 | tee' "${sh}" | head -1 | cut -d: -f1)
    [ -n "${unset_ln}" ]
    [ -n "${migrate_ln}" ]
    [ "${add_ln}" -lt "${unset_ln}" ]
    [ "${unset_ln}" -lt "${migrate_ln}" ]
}

@test "pin: safe.directory window close only removes what the harness added" {
    local sh="${REPO_ROOT}/scripts/host/test_migration.sh"
    # The close is gated on HARNESS_ADDED_SAFE_DIR, so a pre-existing exemption is
    # left intact; removal is targeted (value regex ^/daaf$) so other entries stay.
    run grep -cF 'if [ "${HARNESS_ADDED_SAFE_DIR}" = "true" ]; then' "${sh}"
    assert_success
    [ "${output}" -eq 1 ]
    run grep -cF "container_exec git config --global --unset-all safe.directory '^/daaf\$'" "${sh}"
    assert_success
    [ "${output}" -eq 1 ]
}

@test "pin: safe.directory window open uses a capture-then-test guard (lint 9) + byte-identical notes" {
    local sh="${REPO_ROOT}/scripts/host/test_migration.sh"
    # get-all captured into a var, then echo-of-captured-var into grep -qx (the
    # sanctioned lint-9 form), never a live-producer pipe into grep -q.
    run grep -cF 'SAFE_DIR_PRE=$(container_exec git config --global --get-all safe.directory' "${sh}"
    assert_success
    [ "${output}" -eq 1 ]
    run grep -cF "echo \"\${SAFE_DIR_PRE}\" | grep -qx '/daaf'" "${sh}"
    assert_success
    [ "${output}" -eq 1 ]
    # observe_note prose is byte-identical to the .ps1 twin (open + close).
    run grep -cF 'Git safe.directory exemption window OPENED (harness added /daaf)' "${sh}"
    assert_success
    [ "${output}" -eq 1 ]
    run grep -cF 'Git safe.directory exemption window CLOSED (harness removed its /daaf entry)' "${sh}"
    assert_success
    [ "${output}" -eq 1 ]
}
