#!/usr/bin/env bats
# ============================================================================
# Tests for backup_daaf.sh -- DAAF Backup Utility
# ============================================================================
# Key testable logic: date-suffix versioning (a/b/c), preflight checks,
# volume existence validation.
# ============================================================================

load 'test_helper'

setup() {
    common_setup
    mock_docker
    # backup_daaf.sh does not require docker-compose.yml
}

# Re-open any chmod-000 fixture folder (the read-error tests at the end of this file)
# before the shared teardown's `rm -rf`, which cannot descend into an unreadable folder --
# this runs on pass AND on failure, so no fixture outlives its test
# (backup_twin_parity.bats pattern).
teardown() {
    chmod -R u+rwx "${TEST_DIR}" 2>/dev/null || true
    common_teardown
}

# --- Syntax ---

@test "backup_daaf.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
}

# --- Preflight: missing Docker ---

@test "backup_daaf.sh fails when docker command is not found" {
    mock_no_docker
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker"
}

# --- Preflight: Docker daemon not running ---

@test "backup_daaf.sh fails when Docker daemon is not running" {
    MOCK_DOCKER_INFO_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

# --- Preflight: volume not found ---

@test "backup_daaf.sh fails when Docker volume does not exist" {
    MOCK_DOCKER_VOLUME_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "not found"
}

# --- DAAF_NESTED behavior ---

@test "backup_daaf.sh suppresses pause trap when DAAF_NESTED=1" {
    export DAAF_NESTED=1
    MOCK_DOCKER_VOLUME_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    refute_output --partial "Press Enter"
}

# --- Date-suffix versioning logic ---

@test "backup_daaf.sh generates 'a' suffix when base backup exists" {
    # Create a directory matching today's date backup name
    local today
    today=$(date +%Y-%m-%d)
    mkdir -p "${TEST_DIR}/${today}_daaf_backup"

    # Mock volume inspect to succeed, mock docker run for scan
    # Legacy 4-line scan mock: file count, du -sk, du -sh, logical KB (the 5th
    # special-file line is optional; a missing one reads as 0)
    MOCK_DOCKER_VOLUME_EXIT=0
    MOCK_DOCKER_RUN_OUTPUT=$'100\n512\t/source\n500K\t/source\n500'
    MOCK_DOCKER_RUN_EXIT=0
    export DAAF_NESTED=1

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    # Should show the suffixed backup name
    assert_output --partial "${today}a_daaf_backup"
}

@test "backup_daaf.sh generates 'b' suffix when 'a' also exists" {
    local today
    today=$(date +%Y-%m-%d)
    mkdir -p "${TEST_DIR}/${today}_daaf_backup"
    mkdir -p "${TEST_DIR}/${today}a_daaf_backup"

    # Legacy 4-line scan mock: file count, du -sk, du -sh, logical KB (the 5th
    # special-file line is optional; a missing one reads as 0)
    MOCK_DOCKER_VOLUME_EXIT=0
    MOCK_DOCKER_RUN_OUTPUT=$'100\n512\t/source\n500K\t/source\n500'
    MOCK_DOCKER_RUN_EXIT=0
    export DAAF_NESTED=1

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output --partial "${today}b_daaf_backup"
}

# --- Banner display ---

@test "backup_daaf.sh displays the DAAF Backup banner" {
    export DAAF_NESTED=1
    MOCK_DOCKER_VOLUME_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output --partial "DAAF Backup"
}

# --- Structural: safety features present ---

@test "backup_daaf.sh contains disk space pre-check" {
    run grep -c "Insufficient disk space" "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
}

@test "backup_daaf.sh contains size-based verification" {
    run grep -c "Size verification" "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
}

@test "backup_daaf.sh uses staging + docker cp (not bind-mounted cp -a)" {
    # The copy mechanism is a STAGING container (`docker run -d`) + `docker cp` from
    # /staging -- it must invoke a quoted `docker cp "` (one for the data volume, one
    # for the Claude state volume) and must NOT use the old bind-mounted
    # `cp -a /source` busybox copy of the LIVE volume. (The `cp -a /source /staging`
    # INSIDE the staging program is a different thing -- a container-internal freeze,
    # not a host bind-mount copy -- so the anti-pattern grep targets `cp -a /source `
    # with a trailing space, which the staging program's `cp -a /source /staging`
    # would match; hence assert the staging markers positively instead.)
    run grep -c 'docker run -d' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    run grep -c 'docker cp "' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
}

# --- Executable-permission manifest ---

@test "backup_daaf.sh records the executable-permission manifest" {
    # The manifest ".daaf-permissions" is written into the backup root so a Windows
    # (NTFS) round-trip -- which loses POSIX modes -- can be undone on restore.
    run grep -c '\.daaf-permissions' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    # It is generated container-side from the volume with -perm -0100 (owner-exec).
    run grep -c 'find /source -type f -perm -0100' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
}

@test "backup_daaf.sh writes the manifest as a WARNING-not-fatal step" {
    # A manifest write failure must not fail the backup (the data is still valid).
    run grep -c 'Could not record the executable-permission manifest' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
}

# --- Symlink-safe staging ---

@test "backup_daaf.sh stages the volume to strip symlinks before docker cp" {
    # Windows `docker cp` aborts on symlinks it cannot create, silently truncating
    # the archive. Backup must stage into a throwaway container (`docker run -d`),
    # `docker wait` for it, then cp from /staging -- NOT cp the volume directly.
    run grep -c 'docker run -d' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    run grep -c 'docker wait' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    run grep -c ':/staging/\.' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
}

@test "backup_daaf.sh staging program is quote-free and writes .daaf-symlinks" {
    # The container-side staging program must contain NO embedded double quotes
    # (shared with the .ps1 twin; double quotes corrupt Windows PS 5.1 arg parsing).
    run grep -c 'find /staging -type l -exec rm -f' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    run grep -c '\.daaf-symlinks' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
}

@test "backup_daaf.sh staging program gates on tab/newline in symlink names" {
    # The gate lives INSIDE the container-side STAGE_PROGRAM, which the docker mock
    # replaces wholesale -- so its runtime behavior is verified empirically against
    # real sh in scripts/scratch/gate_test/ (CLEAN 0, TAB 3, NEWLINE 3, EMPTY 0),
    # not here. This structural test asserts the gate is PRESENT and uses the
    # newline-immune true-count idiom (`-exec printf x`) plus the octal-printf tab
    # pattern (`printf \\011`, double backslash so container sh hands printf one) fed
    # to `grep -qf` (avoids IFS word-splitting on a bare tab), and that it exits
    # nonzero via distinct markers so the fatal staging-failure path fires.
    run grep -c 'STAGE_ERR_NEWLINE' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    run grep -c 'STAGE_ERR_TAB' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    run grep -c 'exec printf x' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    run grep -c 'printf .*011' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    run grep -c 'grep -qf /tmp/tab_pat' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
}

@test "backup_daaf.sh staging gate NAMES the offending symlink(s) to STDOUT before exit 3" {
    # On a gate trip the container-side program must print the offenders to STDOUT
    # before `exit 3` (empirically verified against real sh in
    # scripts/scratch/backup_gate_probe/run_probe.sh: tab -> the matching line via
    # `grep -f` without -q; newline -> the full link_paths list, since the culprit
    # cannot be isolated from mismatched line counts). The offenders go to STDOUT, not
    # stderr: PS 5.1's native `2>&1` merge dropped the container's stderr in the field
    # (2026-07-14), so the offender list never reached the user; stdout is
    # version-agnostic. Structurally assert both branches emit a header and dump the
    # offenders, that the new lines stay quote-free, and that they do NOT redirect to
    # stderr (`>&2` must be absent from the offender-print lines).
    run grep -c 'embeds a newline' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    run grep -c 'cat /tmp/link_paths' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    run grep -c 'embed a tab' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    run grep -c 'grep -f /tmp/tab_pat /tmp/link_paths' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    # The offender-print lines inside the gate must NOT go to stderr anymore. Assert
    # the stderr-redirected forms are gone (the fragile PS 5.1 leg).
    run grep -c 'cat /tmp/link_paths >&2' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    run grep -c 'grep -f /tmp/tab_pat /tmp/link_paths >&2' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
}

@test "backup_daaf.sh relays the detached staging container log on failure" {
    # The staging container is DETACHED (`docker run -d`), so the gate's offender
    # output goes to the container LOG, not the terminal. The driver must fetch that
    # log with `docker logs` and relay it under a "Details from the staging scan"
    # header BEFORE `docker rm -f` removes the container. Both the data-volume fatal
    # path and the Claude-volume WARNING path do this.
    run grep -c 'docker logs' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    run grep -c 'Details from the staging scan' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
}

@test "backup_daaf.sh labels an empty staging log instead of silently omitting details" {
    # When the fetched staging log is empty/whitespace, the driver must print a
    # clearly labeled fallback line rather than dropping the details block -- so a
    # future stream regression (like the PS 5.1 stderr-drop that motivated moving the
    # gate to stdout) is VISIBLE, not ambiguous. Both the data-volume fatal path and
    # the Claude-volume WARNING path emit this fallback; both indent under the always-
    # printed "Details from the staging scan:" header. Assert the fallback line exists
    # on both paths (two occurrences: one 7-space indent, one 9-space indent).
    run grep -c 'no details could be retrieved from the staging container' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    # Exactly two occurrences (data-fatal + Claude-WARNING).
    run bash -c "grep -c 'no details could be retrieved from the staging container' \"${REPO_ROOT}/scripts/host/backup_daaf.sh\""
    assert_output "2"
}

@test "backup_daaf.sh fetches the staging log before removing the container" {
    # Ordering guard: on the data-volume failure path, the `docker logs` capture must
    # appear BEFORE the `docker rm -f "${STAGE_CID}"` in the same failure block --
    # otherwise the log is gone by the time it is read. Assert the STAGE_LOG capture
    # line precedes the STAGE_CID removal on the fatal path.
    local logs_line rm_line
    logs_line=$(grep -n 'STAGE_LOG=.*docker logs' "${REPO_ROOT}/scripts/host/backup_daaf.sh" | head -1 | cut -d: -f1)
    rm_line=$(grep -n '^    docker rm -f "\${STAGE_CID}"' "${REPO_ROOT}/scripts/host/backup_daaf.sh" | head -1 | cut -d: -f1)
    [ -n "${logs_line}" ]
    [ -n "${rm_line}" ]
    [ "${logs_line}" -lt "${rm_line}" ]
}

@test "backup_daaf.sh staging-failure error names the tab/newline cause and disk image" {
    # The host-side staging-failure error text must explain BOTH an exit-3 unsupported
    # character (tab/newline -- rename/remove the link) AND the Docker Desktop disk
    # image (staging transiently doubles usage on the VM's internal disk).
    run grep -c 'TAB or a NEWLINE' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    run grep -c 'Docker Desktop disk image' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
}

@test "backup_daaf.sh treats a staging failure as a fatal ERROR before any host bytes" {
    export DAAF_NESTED=1

    # Model a nonzero staging exit (`docker wait` prints "1"): the backup must abort
    # fatally with an ERROR, because nothing useful was produced.
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then echo "stagecid0000"; return 0; fi
                printf '5\n512\t/source\n500K\t/source\n500\n'
                return 0
                ;;
            wait) echo "1"; return 0 ;;
            cp)   return 0 ;;
            rm)   return 0 ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "stage the Docker volume"
}

@test "backup_daaf.sh excludes .daaf-symlinks from the copied file count" {
    export DAAF_NESTED=1
    local today
    today=$(date +%Y-%m-%d)

    # Staging + cp create one real data file AND a .daaf-symlinks manifest. The
    # scan reports 1 source file; the completion count must be 1 (manifest
    # excluded) -- with no file-count-mismatch WARNING.
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then echo "stagecid0000"; return 0; fi
                printf '1\n512\t/source\n500K\t/source\n500\n'
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                if [ -n "${dest_dir}" ]; then
                    mkdir -p "${dest_dir}"
                    touch "${dest_dir}/realfile"
                    printf 'sub/link\ttarget\n' > "${dest_dir}/.daaf-symlinks"
                fi
                return 0
                ;;
            rm) return 0 ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output --partial "1 files copied"
    refute_output --partial "file-count mismatch"
}

# --- Special-file strip (named pipes, sockets, device nodes) ---
# Windows `docker cp` creates nothing for a FIFO/device tar entry, then aborts the
# whole extraction on the follow-up timestamp call -- the same truncation class as
# the symlink abort. Field report 2026-09-29 (sibling project, variant script): a stale
# provider-shim output.fifo stopped a Windows backup, last progress reading 94%.
# Separate probe of the maintainer volume: 714 of 71,820 files sort after the first
# FIFO -- under the 1% (718) count tolerance, so a count check that applied it would
# not flag it. (The backup now verifies against the staged snapshot at zero
# tolerance; the 1% tolerance remains only on the fallback path, where the snapshot
# markers could not be read.) The staging program must
# delete them, and the scan must count them so the skip is visible.

# Extract backup_daaf.sh's STAGE_PROGRAM with the manifest splice resolved (the same
# anchors tests/bash/backup_twin_parity.bats uses; that file proves the .ps1 twin is
# byte-identical, so exercising this one covers both).
_extract_stage_program() {
    local f="${REPO_ROOT}/scripts/host/backup_daaf.sh" m
    m="$(sed -n 's/^SYMLINKS_MANIFEST="\([^"]*\)".*/\1/p' "${f}" | head -1)"
    sed "s/'\"\${SYMLINKS_MANIFEST}\"'/${m}/g" "${f}" \
    | awk '
        BEGIN { inp=0 }
        inp==0 && /^STAGE_PROGRAM=/ {
            inp=1; line=$0; sub(/^STAGE_PROGRAM=./, "", line); print line; next
        }
        inp==1 {
            if ($0 ~ /\047$/) { line=$0; sub(/.$/, "", line); print line; exit }
            print $0
        }
    '
}

# Relocate the program's absolute container paths (/source, /staging, /tmp/) under a
# per-test root so it can run under the local sh. Two-phase: tokenize, ASSERT no
# absolute path survived (so a missed rewrite can never write to the real /tmp), then
# substitute the root. Writes the runnable program to "$1/program.sh".
_relocate_stage_program() {
    local root="$1"
    _extract_stage_program \
        | sed -e 's|/tmp/|__CTMP__/|g' -e 's|/source|__SRC__|g' -e 's|/staging|__STG__|g' \
        > "${root}/tokenized.sh"
    [ -s "${root}/tokenized.sh" ] || { echo "FAIL: STAGE_PROGRAM extraction empty"; return 1; }
    if grep -qE '/tmp/|/source|/staging' "${root}/tokenized.sh"; then
        echo "FAIL: an absolute container path survived relocation:"
        grep -nE '/tmp/|/source|/staging' "${root}/tokenized.sh"
        return 1
    fi
    sed -e "s|__CTMP__|${root}/ctmp|g" -e "s|__SRC__|${root}/source|g" -e "s|__STG__|${root}/staging|g" \
        "${root}/tokenized.sh" > "${root}/program.sh"
}

@test "backup_daaf.sh staging program strips named pipes, sockets, and device nodes" {
    # The strip must follow the symlink strip inside STAGE_PROGRAM, group all four
    # types so -exec binds to each, and stay quote-free (PS 5.1 twin parity).
    run grep -cF 'find /staging \( -type p -o -type s -o -type b -o -type c \) -exec rm -f {} +' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output "1"
    # It directly follows the symlink strip, and only the seven-line snapshot-count
    # block (success path only) comes after it: the count, then the markers -- or,
    # when the count hit read errors, STAGED_COUNT_ERRORS instead (review round 2, F1).
    run _extract_stage_program
    assert_success
    [ "${lines[${#lines[@]}-8]}" = 'find /staging \( -type p -o -type s -o -type b -o -type c \) -exec rm -f {} +' ]
    [ "${lines[${#lines[@]}-9]}" = 'find /staging -type l -exec rm -f {} +' ]
    [ "${lines[${#lines[@]}-6]}" = 'if test -s /tmp/count_err; then' ]
    [ "${lines[${#lines[@]}-5]}" = 'echo STAGED_COUNT_ERRORS=$(grep -c ^ /tmp/count_err)' ]
    [ "${lines[${#lines[@]}-4]}" = 'else' ]
    [ "${lines[${#lines[@]}-3]}" = 'echo STAGED_FILES=${counts% *}' ]
    [ "${lines[${#lines[@]}-2]}" = 'echo STAGED_KB=${counts#* }' ]
    [ "${lines[${#lines[@]}-1]}" = 'fi' ]
}

# --- Snapshot count + zero-tolerance verification (2026-09-29) ---
# The staging program ends by printing STAGED_FILES/STAGED_KB for the frozen staged
# tree (root manifest excluded). The driver reads them via `docker logs` and verifies
# the copy against them at ZERO tolerance; missing/garbage markers fall back to the
# live-volume scan with the old 1% tolerance and a Note.

@test "backup: staging program (run under local sh) prints snapshot count markers excluding the root manifest" {
    # Behavioral: 3 regular files (one nested file is itself NAMED .daaf-symlinks --
    # only the ROOT manifest is excluded, matching the host-side predicate), a
    # symlink and a FIFO (stripped, so not counted). Sizes 1000+2000+100 bytes ->
    # int(3100/1024) = 3 KB. A stray ROOT .daaf-permissions (restore's failed
    # permission replay can leave one in the volume) and a root .daaf-claude-config
    # subtree are excluded too, exactly as the host-side counts exclude them -- a
    # one-sided exclusion was a false zero-tolerance mismatch (review I1).
    local root="${TEST_DIR}/stagetest"
    mkdir -p "${root}/source/sub" "${root}/source/.daaf-claude-config" "${root}/ctmp"
    head -c 1000 /dev/zero > "${root}/source/a.bin"
    head -c 2000 /dev/zero > "${root}/source/sub/b.bin"
    head -c 100 /dev/zero > "${root}/source/sub/.daaf-symlinks"
    printf 'scripts/run.sh\n' > "${root}/source/.daaf-permissions"
    : > "${root}/source/.daaf-claude-config/c.json"
    ln -s a.bin "${root}/source/link-to-a"
    mkfifo "${root}/source/sub/output.fifo"
    _relocate_stage_program "${root}"

    run sh "${root}/program.sh"
    assert_success
    assert_output --partial "STAGED_FILES=3"
    assert_output --partial "STAGED_KB=3"
    # The root manifest exists in the staged tree but was not counted.
    [ -f "${root}/staging/.daaf-symlinks" ]
}

@test "backup: staging program prints 0 counts (not empty values) for a volume with no regular files" {
    local root="${TEST_DIR}/stagetest"
    mkdir -p "${root}/source/emptydir" "${root}/ctmp"
    _relocate_stage_program "${root}"
    run sh "${root}/program.sh"
    assert_success
    assert_output "$(printf 'STAGED_FILES=0\nSTAGED_KB=0')"
}

@test "backup: snapshot count program stays quote-free (escaped awk, no single or double quotes)" {
    run _extract_stage_program
    assert_success
    local block
    block="$(printf '%s\n' "${lines[@]}" | tail -n 7)"
    [[ "${block}" != *"'"* ]]
    [[ "${block}" != *'"'* ]]
    [[ "${block}" == *'awk \{n++\;s+=\$1\}\ END\ \{print\ n+0,int\(s/1024\)\}'* ]]
}

# Shared mock: STAGE_LOG_TEXT is what `docker logs` prints after a clean staging run
# (printf format; "__FAIL__" makes `docker logs` exit 1). CP_FILES files land in the
# backup. Logical KB 0 in the scan and STAGED_KB=0 keep the size check neutral.
_mock_snapshot_docker() {
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then echo "stagecid0000"; return 0; fi
                printf '%s\n512\t/source\n500K\t/source\n0\n' "${SCAN_COUNT}"
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            logs)
                if [ "${STAGE_LOG_TEXT}" = "__FAIL__" ]; then return 1; fi
                # shellcheck disable=SC2059 -- the test deliberately passes a printf format
                printf "${STAGE_LOG_TEXT}"
                return 0
                ;;
            cp)
                local dest_dir="" i=0
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                case "${dest_dir}" in *daaf-claude-config*) return 0 ;; esac
                mkdir -p "${dest_dir}"
                while [ "${i}" -lt "${CP_FILES}" ]; do touch "${dest_dir}/file${i}"; i=$((i + 1)); done
                touch "${dest_dir}/.daaf-symlinks"
                # CP_SLEEP (seconds) keeps the background copy "running" after its files
                # land, so the 3-second progress loop prints at least one line.
                sleep "${CP_SLEEP:-0}"
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker
}

@test "backup: the copy-progress count excludes the root manifest like the snapshot (no N+1 / N)" {
    # Field 2026-10-01 (.ps1 twin; this loop had the same count): the progress line read
    # "73848 / 73847 files" because it counted the root .daaf-symlinks manifest, which
    # the snapshot excludes. The fake copy lands 2 files + the manifest, then sleeps so
    # the progress loop runs while the copy is still going.
    export DAAF_NESTED=1 SCAN_COUNT=2 CP_FILES=2 CP_SLEEP=5 STAGE_LOG_TEXT='STAGED_FILES=2\nSTAGED_KB=0\n'
    _mock_snapshot_docker
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    refute_output --partial "Progress: 3 / 2"
    # The loop's own line AND the final line both read 2 / 2 (non-vacuous: the loop ran).
    [ "$(grep -o 'Progress: 2 / 2 files (100%)' <<< "${output}" | wc -l)" -ge 2 ]
    assert_output --partial "Backup complete!"
}

@test "backup: markers match the copy -> Snapshot line, plain banner, no fallback note" {
    export DAAF_NESTED=1 SCAN_COUNT=2 CP_FILES=2 STAGE_LOG_TEXT='STAGED_FILES=2\nSTAGED_KB=0\n'
    _mock_snapshot_docker
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "Snapshot: 2 files."
    refute_output --partial "Could not read the snapshot"
    refute_output --partial "file-count mismatch"
    assert_output --partial "Backup complete!"
}

@test "backup: zero tolerance -- a 1-file shortfall against the snapshot warns (the 1% floor would hide it)" {
    # Snapshot 3, copy lands 2. On the fallback path the tolerance floors to 1, so a
    # diff of 1 passes silently (see the clamp test at the end of this file); against
    # the snapshot it must warn and latch WITH WARNINGS, without being fatal (the copy
    # exit is 0). A shortfall against the exact snapshot is a PROVEN loss, so the
    # wording says so plainly (review I2) instead of "may be incomplete".
    export DAAF_NESTED=1 SCAN_COUNT=3 CP_FILES=2 STAGE_LOG_TEXT='STAGED_FILES=3\nSTAGED_KB=0\n'
    _mock_snapshot_docker
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "file-count mismatch"
    assert_output --partial "Snapshot: 3 files, Backup: 2 files (difference: 1)"
    assert_output --partial "1 file(s) from the snapshot are missing from this backup. Do not rely on it."
    assert_output --partial "re-running will not fix"
    refute_output --partial "may be incomplete"
    assert_output --partial "Backup completed WITH WARNINGS"
}

@test "backup: zero tolerance -- an EXTRA file against the snapshot warns, but as extras, not a loss" {
    export DAAF_NESTED=1 SCAN_COUNT=2 CP_FILES=3 STAGE_LOG_TEXT='STAGED_FILES=2\nSTAGED_KB=0\n'
    _mock_snapshot_docker
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "Snapshot: 2 files, Backup: 3 files (difference: 1)"
    assert_output --partial "files that are not in the snapshot"
    assert_output --partial "The DAAF data itself appears complete."
    refute_output --partial "missing from this backup"
    refute_output --partial "may be incomplete"
    assert_output --partial "Backup completed WITH WARNINGS"
}

@test "backup: zero tolerance -- a KB mismatch with EQUAL counts says the contents differ" {
    # 2 empty files land (0 KB); the snapshot claims 5 KB for the same 2 files.
    export DAAF_NESTED=1 SCAN_COUNT=2 CP_FILES=2 STAGE_LOG_TEXT='STAGED_FILES=2\nSTAGED_KB=5\n'
    _mock_snapshot_docker
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    refute_output --partial "file-count mismatch"
    assert_output --partial "WARNING: Backup size mismatch."
    assert_output --partial "Snapshot: 5 KB, Backup: 0 KB (difference: 5 KB)"
    assert_output --partial "the file contents differ in size from the"
    refute_output --partial "may be incomplete"
    assert_output --partial "Backup completed WITH WARNINGS"
}

@test "backup: fallback path keeps the 'may be incomplete' wording (1% tolerance)" {
    # No readable markers -> expected = live scan (100); 2 files land, far past the
    # 1% tolerance. The scan can drift, so the wording stays hedged.
    export DAAF_NESTED=1 SCAN_COUNT=100 CP_FILES=2 STAGE_LOG_TEXT=''
    _mock_snapshot_docker
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "Source: 100 files, Backup: 2 files (difference: 98)"
    assert_output --partial "The backup may be incomplete. Consider re-running."
    refute_output --partial "missing from this backup"
}

@test "backup: a copied file whose NAME holds a newline counts once (matches the stat-based snapshot)" {
    # The snapshot counts one `stat` line per file; the host count counts one NUL per
    # file (`-print0`). A line count would see this file twice and trip the
    # zero-tolerance check.
    export DAAF_NESTED=1
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info|volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then echo "stagecid0000"; return 0; fi
                printf '2\n512\t/source\n500K\t/source\n0\n'
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            logs) printf 'STAGED_FILES=2\nSTAGED_KB=0\n'; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                case "${dest_dir}" in *daaf-claude-config*) return 0 ;; esac
                mkdir -p "${dest_dir}"
                touch "${dest_dir}/file1" "${dest_dir}/name"$'\n'"with-newline" "${dest_dir}/.daaf-symlinks"
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "Progress: 2 / 2 files (100%)"
    refute_output --partial "file-count mismatch"
    assert_output --partial "Backup complete!"
}

@test "backup: the Claude-state count excludes only the subfolder's ROOT manifest" {
    # Root-relative like the data-volume count and the .ps1 twin: a nested file that
    # is merely NAMED .daaf-symlinks is Claude state and counts.
    export DAAF_NESTED=1
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info|volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then echo "stagecid0000"; return 0; fi
                printf '1\n512\t/source\n500K\t/source\n0\n'
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            logs) printf 'STAGED_FILES=1\nSTAGED_KB=0\n'; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                mkdir -p "${dest_dir}/sub"
                # A stray ROOT .daaf-permissions in the Claude subfolder is excluded too,
                # like the staged count's predicate (review round 2, F5i).
                case "${dest_dir}" in
                    *daaf-claude-config*) touch "${dest_dir}/c1" "${dest_dir}/sub/.daaf-symlinks" "${dest_dir}/.daaf-symlinks" "${dest_dir}/.daaf-permissions" ;;
                    *) touch "${dest_dir}/file1" "${dest_dir}/.daaf-symlinks" ;;
                esac
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "Claude Code state backed up (2 files)."
}

@test "backup: snapshot differing from the live scan is explained and becomes the target" {
    # Scan saw 5 (live volume), the frozen snapshot holds 2, the copy lands 2: the
    # snapshot is what was backed up, so this is a clean run.
    export DAAF_NESTED=1 SCAN_COUNT=5 CP_FILES=2 STAGE_LOG_TEXT='STAGED_FILES=2\nSTAGED_KB=0\n'
    _mock_snapshot_docker
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "Snapshot: 2 files (3 fewer than the scan"
    assert_output --partial "Progress: 2 / 2 files (100%)"
    refute_output --partial "file-count mismatch"
    assert_output --partial "Backup complete!"
}

@test "backup: missing, garbage, partial, or unreadable markers fall back to the scan with a Note" {
    # Each case falls back to the scan count (2) with the 1% tolerance (floor 1), so
    # a copy of 3 files (diff 1) is tolerated exactly as before -- and a Note says so.
    export DAAF_NESTED=1 SCAN_COUNT=2 CP_FILES=3
    _mock_snapshot_docker
    local log
    for log in '' 'STAGED_FILES=abc\nSTAGED_KB=0\n' 'STAGED_FILES=3\n' ' STAGED_FILES=3x\nSTAGED_KB=0\n' 'STAGED_FILES=-3\nSTAGED_KB=0\n' '__FAIL__'; do
        export STAGE_LOG_TEXT="${log}"
        run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
        echo "case log = [${log}]"
        assert_success
        assert_output --partial "Could not read the snapshot's file count"
        refute_output --partial "Snapshot:"
        refute_output --partial "file-count mismatch"
        refute_output --partial "integer expression"
        assert_output --partial "Backup complete!"
    done
}

@test "backup: the copied-file count excludes only ROOT metadata (nested same-name files count)" {
    # The host count mirrors the staged count's root-relative predicates, so a file
    # NAMED .daaf-symlinks deeper in the tree is data and must be counted.
    export DAAF_NESTED=1
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info|volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then echo "stagecid0000"; return 0; fi
                printf '2\n512\t/source\n500K\t/source\n0\n'
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            logs) printf 'STAGED_FILES=2\nSTAGED_KB=0\n'; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                case "${dest_dir}" in *daaf-claude-config*) return 0 ;; esac
                mkdir -p "${dest_dir}/sub"
                touch "${dest_dir}/file1" "${dest_dir}/sub/.daaf-symlinks" "${dest_dir}/.daaf-symlinks"
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "Progress: 2 / 2 files (100%)"
    refute_output --partial "file-count mismatch"
}

@test "backup_daaf.sh scan counts special files as an appended 5th line" {
    # The count is appended AFTER the four existing scan values so their line-index
    # parsing contract is unchanged, and it uses the same four types the strip deletes.
    run grep -cF '&& find /source \( -type p -o -type s -o -type b -o -type c \) | wc -l' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output "1"
    run grep -cF "SPECIAL_FILES=\$(echo \"\${SCAN_OUTPUT}\" | sed -n '5p'" "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output "1"
}

@test "backup_daaf.sh scan program emits EXACTLY 5 lines (the .ps1 twin owns reserved line 6)" {
    # The scan's line order is an append-only contract shared with the .ps1 twin,
    # which appends a Windows-only long-path count as line 6. This twin must not emit
    # a 6th line (it would collide with that slot) -- run the REAL program under the
    # local sh against a fixture, with /source relocated.
    local f="${REPO_ROOT}/scripts/host/backup_daaf.sh" src="${TEST_DIR}/scansrc"
    mkdir -p "${src}/sub"
    printf 'alpha\n' > "${src}/a.txt"
    printf 'beta\n' > "${src}/sub/b.txt"
    mkfifo "${src}/sub/p.fifo"
    local prog
    prog="$(sed -n "s/^SCAN_OUTPUT=\$(docker run --rm -v \"\${VOLUME_NAME}:\/source:ro\" \"\${BUSYBOX_IMAGE}\" sh -c '\(.*\)') || {\$/\1/p" "${f}")"
    [ -n "${prog}" ] || { echo "FAIL: scan program not found in backup_daaf.sh"; return 1; }
    run sh -c "${prog//\/source/${src}}"
    assert_success
    [ "${#lines[@]}" -eq 5 ] || { echo "expected 5 lines, got ${#lines[@]}:"; printf '%s\n' "${lines[@]}"; return 1; }
    [ "${lines[0]}" = "2" ]
    [ "${lines[4]}" = "1" ]
}

@test "backup_daaf.sh scan counts files and KB with the SNAPSHOT predicate (root metadata excluded, newline name once)" {
    # Review round 2 (F5f): the scan used `find /source -type f | wc -l` with no
    # exclusions, so a stray root .daaf-permissions showed up as "N fewer than the
    # scan -- the live volume changed" drift, and a newline name counted twice. Lines 1
    # and 4 now come from the snapshot count's own predicate and `stat` line count.
    local f="${REPO_ROOT}/scripts/host/backup_daaf.sh" src="${TEST_DIR}/scansrc"
    mkdir -p "${src}/sub" "${src}/.daaf-claude-config"
    head -c 1000 /dev/zero > "${src}/a.bin"
    head -c 2000 /dev/zero > "${src}/sub/b.bin"
    head -c 100 /dev/zero > "${src}/sub/.daaf-permissions"
    : > "${src}/sub/name"$'\n'"with-newline"
    printf 'scripts/run.sh\n' > "${src}/.daaf-permissions"
    : > "${src}/.daaf-symlinks"
    head -c 5000 /dev/zero > "${src}/.daaf-claude-config/c.json"
    local prog
    prog="$(sed -n "s/^SCAN_OUTPUT=\$(docker run --rm -v \"\${VOLUME_NAME}:\/source:ro\" \"\${BUSYBOX_IMAGE}\" sh -c '\(.*\)') || {\$/\1/p" "${f}")"
    [ -n "${prog}" ] || { echo "FAIL: scan program not found in backup_daaf.sh"; return 1; }
    run sh -c "${prog//\/source/${src}}"
    assert_success
    [ "${#lines[@]}" -eq 5 ]
    # a.bin, sub/b.bin, sub/.daaf-permissions (nested = data), the newline name.
    [ "${lines[0]}" = "4" ] || { echo "line 1 = [${lines[0]}]"; return 1; }
    # 1000 + 2000 + 100 + 0 bytes -> int(3100/1024) = 3 KB.
    [ "${lines[3]}" = "3" ] || { echo "line 4 = [${lines[3]}]"; return 1; }
}

@test "backup_daaf.sh prints the resolved Source volume next to the Backup name" {
    # Review round 2 (F4): a user diffed a backup against the wrong install's volume
    # because nothing said which volume was backed up. Default, DAAF_PROJECT_NAME, and
    # the DAAF_DATA_VOLUME_NAME override (which wins) must all show the resolved name.
    run env -u DAAF_PROJECT_NAME -u DAAF_DATA_VOLUME_NAME DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "Source volume: daaf_daaf-data"
    run env -u DAAF_DATA_VOLUME_NAME DAAF_PROJECT_NAME=daaf2 DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "Source volume: daaf2_daaf-data"
    run env DAAF_PROJECT_NAME=daaf2 DAAF_DATA_VOLUME_NAME=gpt_sub_daaf-data DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "Source volume: gpt_sub_daaf-data"
    refute_output --partial "daaf2_daaf-data"
    # It sits directly under the Backup name line.
    local i
    for i in "${!lines[@]}"; do
        if [[ "${lines[$i]}" == "Backup name: "* ]]; then
            [ "${lines[$((i + 1))]}" = "Source volume: gpt_sub_daaf-data" ]
            return 0
        fi
    done
    echo "Backup name line not found"; return 1
}

@test "backup_daaf.sh host-side NUL counts run tr in the C locale (macOS multibyte tr)" {
    # Review round 2 (F5b): macOS `tr` in a UTF-8 locale can fail with "Illegal byte
    # sequence" on a non-UTF-8 byte in a name. Every `-print0 | tr -dc` count must use
    # LC_ALL=C (the data-volume count and the Claude-state count).
    run grep -c -- "-print0 | LC_ALL=C tr -dc '\\\\000' | wc -c" "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output "1"
    run grep -c -- "| tr -dc '\\\\000'" "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output "0"
}

@test "backup: staging program (run under local sh) removes a FIFO, a socket, and a symlink, keeps regular files" {
    # Behavioral: run the REAL extracted STAGE_PROGRAM (relocated under TEST_DIR)
    # against a tree holding a FIFO, a UNIX socket, and a symlink -- two special-file
    # types, so a strip narrowed to `-type p` alone fails here. NOTE: this runs under
    # the local POSIX sh + coreutils/findutils, not busybox (not installed here); the
    # predicates used (-type p/s/b/c, \( \), -o, -exec {} +) are POSIX find. Device
    # nodes need root to create and are not fixtured. All fixture objects live under
    # TEST_DIR, which common_teardown removes on pass AND on failure.
    command -v python3 > /dev/null 2>&1 || skip "python3 needed to create the UNIX-socket fixture"
    local root="${TEST_DIR}/stagetest"
    mkdir -p "${root}/source/sub" "${root}/ctmp"
    printf 'alpha\n' > "${root}/source/a.txt"
    printf 'beta\n' > "${root}/source/sub/b.txt"
    ln -s a.txt "${root}/source/link-to-a"
    mkfifo "${root}/source/sub/output.fifo"
    # Bind (and leave) a UNIX socket file; the process exits, the socket inode stays.
    # chdir + relative name: AF_UNIX paths are capped at ~108 bytes, and TEST_DIR can
    # be deeper than that (e.g. under a project-scratch TMPDIR).
    python3 -c "import os,socket,sys; os.chdir(sys.argv[1]); socket.socket(socket.AF_UNIX).bind(sys.argv[2])" "${root}/source/sub" rendezvous.sock
    [ -S "${root}/source/sub/rendezvous.sock" ]
    _relocate_stage_program "${root}"

    run sh "${root}/program.sh"
    assert_success

    # No FIFO, no socket, and no symlink survive into the staged tree...
    run find "${root}/staging" -type p
    assert_output ""
    run find "${root}/staging" -type s
    assert_output ""
    run find "${root}/staging" -type l
    assert_output ""
    # ...regular files do, with content intact...
    run cat "${root}/staging/a.txt"
    assert_output "alpha"
    run cat "${root}/staging/sub/b.txt"
    assert_output "beta"
    # ...and only the symlink is recorded in the manifest (the FIFO is not).
    run cat "${root}/staging/.daaf-symlinks"
    assert_output "$(printf './link-to-a\ta.txt')"
}

@test "backup: staging program succeeds under set -e when no symlinks or special files exist" {
    # With zero matches, neither strip `find` runs rm, and both exit 0 -- so the
    # `set -e` program must still succeed and leave the regular files in place.
    local root="${TEST_DIR}/stagetest"
    mkdir -p "${root}/source/sub" "${root}/ctmp"
    printf 'alpha\n' > "${root}/source/a.txt"
    printf 'beta\n' > "${root}/source/sub/b.txt"
    _relocate_stage_program "${root}"

    run sh "${root}/program.sh"
    assert_success
    run find "${root}/staging" -type f -name '*.txt'
    assert_output --partial "a.txt"
    assert_output --partial "sub/b.txt"
    # Manifest exists and is empty (no symlinks).
    [ -f "${root}/staging/.daaf-symlinks" ]
    [ ! -s "${root}/staging/.daaf-symlinks" ]
}

@test "backup: prints a skip note when the scan counts special files" {
    export DAAF_NESTED=1
    # 5th scan line = 3 special files. The note appears; it is informational (the
    # banner stays plain -- stale FIFOs are expected, not a backup defect).
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then echo "stagecid0000"; return 0; fi
                printf '2\n512\t/source\n500K\t/source\n0\n3\n'
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                if [ -n "${dest_dir}" ]; then
                    mkdir -p "${dest_dir}"
                    touch "${dest_dir}/file1" "${dest_dir}/file2" "${dest_dir}/.daaf-symlinks"
                fi
                return 0
                ;;
            rm) return 0 ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "Note: skipping 3 named pipe/socket/device file(s) -- runtime-only, not backed up."
    assert_output --partial "Backup complete!"
    refute_output --partial "WITH WARNINGS"
}

@test "backup: no skip note for a zero, missing (4-line scan), or non-numeric 5th line" {
    export DAAF_NESTED=1
    # A 5th line of 0 prints nothing; a 4-line scan (no 5th line, e.g. an older mock)
    # and a non-numeric 5th line both read as 0 via the `case` sanitisation. All three
    # must complete cleanly to the plain banner. Without the sanitisation, `[ "" -gt 0 ]`
    # / `[ abc -gt 0 ]` print "integer expression expected" (and the `if` merely reads
    # false) -- so the refute on that text is what makes this test catch its removal.
    # SCAN_LINE5 drives the mock: "__NONE__" omits the 5th line entirely.
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then echo "stagecid0000"; return 0; fi
                printf '2\n512\t/source\n500K\t/source\n0\n'
                if [ "${SCAN_LINE5}" != "__NONE__" ]; then printf '%s\n' "${SCAN_LINE5}"; fi
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                if [ -n "${dest_dir}" ]; then
                    mkdir -p "${dest_dir}"
                    touch "${dest_dir}/file1" "${dest_dir}/file2" "${dest_dir}/.daaf-symlinks"
                fi
                return 0
                ;;
            rm) return 0 ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    local line5
    for line5 in 0 __NONE__ abc; do
        # Later cases land in suffixed folders (a, b) -- irrelevant to these assertions.
        export SCAN_LINE5="${line5}"
        run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
        echo "case 5th line = ${line5}"
        assert_success
        refute_output --partial "Note: skipping"
        refute_output --partial "integer expression"
        assert_output --partial "Found 2 files to copy"
        assert_output --partial "Backup complete!"
    done
}

@test "backup_daaf.sh: dry-run shows the special-file skip note from the 5-line scan mock" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "Note: skipping 2 named pipe/socket/device file(s) -- runtime-only, not backed up."
}

# --- Date-suffix versioning edge cases ---

@test "backup: suffix picks first available letter sequentially" {
    # Create base and 'a' -- script should pick 'b' (next in sequence)
    local today
    today=$(date +%Y-%m-%d)
    mkdir -p "${TEST_DIR}/${today}_daaf_backup"
    mkdir -p "${TEST_DIR}/${today}a_daaf_backup"
    # Also create 'c' to prove the script picks 'b' (first gap), not 'd'
    mkdir -p "${TEST_DIR}/${today}c_daaf_backup"

    MOCK_DOCKER_VOLUME_EXIT=0
    MOCK_DOCKER_RUN_OUTPUT=$'100\n512\t/source\n500K\t/source\n500'
    MOCK_DOCKER_RUN_EXIT=0
    export DAAF_NESTED=1

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output --partial "${today}b_daaf_backup"
}

@test "backup: 26th backup of the day reaches suffix 'z'" {
    local today
    today=$(date +%Y-%m-%d)
    # Create base backup
    mkdir -p "${TEST_DIR}/${today}_daaf_backup"
    # Create suffixes a through y (25 directories)
    for i in $(seq 0 24); do
        suffix=$(printf "\\$(printf '%03o' $((97 + i)))")
        mkdir -p "${TEST_DIR}/${today}${suffix}_daaf_backup"
    done

    MOCK_DOCKER_VOLUME_EXIT=0
    MOCK_DOCKER_RUN_OUTPUT=$'100\n512\t/source\n500K\t/source\n500'
    MOCK_DOCKER_RUN_EXIT=0
    export DAAF_NESTED=1

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output --partial "${today}z_daaf_backup"
}

@test "backup: errors when all 26 suffixes are exhausted" {
    local today
    today=$(date +%Y-%m-%d)
    # Create base backup
    mkdir -p "${TEST_DIR}/${today}_daaf_backup"
    # Create all 26 suffixed directories (a through z)
    for i in $(seq 0 25); do
        suffix=$(printf "\\$(printf '%03o' $((97 + i)))")
        mkdir -p "${TEST_DIR}/${today}${suffix}_daaf_backup"
    done

    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    assert_output --partial "Too many backups"
}

# --- Disk space checks ---

@test "backup: fails when disk space is insufficient" {
    # Mock df to report very little available space
    df() {
        if [ "$1" = "-P" ]; then
            printf "Filesystem     1024-blocks    Used Available Capacity Mounted on\n"
            printf "/dev/sda1       100000000 99999990       10 100%% /\n"
        else
            builtin command df "$@"
        fi
    }
    export -f df

    MOCK_DOCKER_VOLUME_EXIT=0
    # Report volume size as 10000 KB (10 MB) -- much larger than 10 bytes available
    MOCK_DOCKER_RUN_OUTPUT=$'100\n10000\t/source\n10M\t/source\n9800'
    MOCK_DOCKER_RUN_EXIT=0
    export DAAF_NESTED=1

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    assert_output --partial "Insufficient disk space"
}

@test "backup: reports required vs available space on disk space failure" {
    df() {
        if [ "$1" = "-P" ]; then
            printf "Filesystem     1024-blocks    Used Available Capacity Mounted on\n"
            printf "/dev/sda1       100000000 99999990       10 100%% /\n"
        else
            builtin command df "$@"
        fi
    }
    export -f df

    MOCK_DOCKER_VOLUME_EXIT=0
    MOCK_DOCKER_RUN_OUTPUT=$'100\n10000\t/source\n10M\t/source\n9800'
    MOCK_DOCKER_RUN_EXIT=0
    export DAAF_NESTED=1

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    # Should report both required and available MB values
    assert_output --partial "Required:"
    assert_output --partial "Available:"
}

@test "backup: passes disk space check when sufficient space available" {
    df() {
        if [ "$1" = "-P" ]; then
            printf "Filesystem     1024-blocks    Used Available Capacity Mounted on\n"
            printf "/dev/sda1       100000000 50000000 50000000  50%% /\n"
        else
            builtin command df "$@"
        fi
    }
    export -f df

    MOCK_DOCKER_VOLUME_EXIT=0
    # Small volume (512 KB) -- plenty of space
    MOCK_DOCKER_RUN_OUTPUT=$'100\n512\t/source\n500K\t/source\n500'
    MOCK_DOCKER_RUN_EXIT=0
    export DAAF_NESTED=1

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    # Should pass the disk space check (no "Insufficient" error)
    refute_output --partial "Insufficient disk space"
}

# --- Integrity verification: size mismatch ---

@test "backup: warns when backup size differs from source by more than 1 percent" {
    export DAAF_NESTED=1

    # Custom docker mock: scan reports 9800 logical KB source; the `docker cp` from
    # the staging container creates a small file in the destination dir so
    # FILE_COUNT > 0 and size verification triggers. The backup file is ~1 KB vs
    # 9800 KB source -- well beyond 1% tolerance. The copy path is now
    # `docker run -d` (staging) + `docker wait` + `docker cp`, so the mock models
    # staging launch (returns a CID), wait (exit 0), and cp.
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then
                    # Staging launch -- emit a CID for `docker wait`/`docker cp`.
                    echo "stagecid0000"
                    return 0
                fi
                # `run --rm` scan call: file count, du -sk, du -sh, logical KB
                printf '10\n10000\t/source\n10M\t/source\n9800\n'
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            cp)
                # `docker cp <cid>:/staging/. <dest>/` -- the destination is the
                # last positional arg. Create a file there so the backup is non-empty.
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                if [ -n "${dest_dir}" ]; then
                    mkdir -p "${dest_dir}"
                    # ~1 KB file (far less than 9800 KB source)
                    dd if=/dev/zero of="${dest_dir}/mock_file" bs=1024 count=1 2>/dev/null
                fi
                return 0
                ;;
            rm) return 0 ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output --partial "WARNING"
    assert_output --partial "size mismatch"
}

# --- File count verification ---

@test "backup: reports file count in output on success" {
    export DAAF_NESTED=1

    # Custom docker mock: staging (`run -d` -> CID, `wait` -> 0) then `docker cp`
    # creates files so FILE_COUNT > 0.
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then echo "stagecid0000"; return 0; fi
                printf '5\n512\t/source\n500K\t/source\n500\n'
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                if [ -n "${dest_dir}" ]; then
                    mkdir -p "${dest_dir}"
                    touch "${dest_dir}/file1" "${dest_dir}/file2"
                fi
                return 0
                ;;
            rm) return 0 ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output --partial "files copied"
}

# --- Core behavior ---

@test "backup: creates backup directory with date-based name" {
    export DAAF_NESTED=1
    local today
    today=$(date +%Y-%m-%d)

    # Custom docker mock: staging (`run -d` -> CID, `wait` -> 0) then `docker cp`
    # creates a file so the script reaches success.
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then echo "stagecid0000"; return 0; fi
                printf '5\n512\t/source\n500K\t/source\n500\n'
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                if [ -n "${dest_dir}" ]; then
                    mkdir -p "${dest_dir}"
                    touch "${dest_dir}/file1"
                fi
                return 0
                ;;
            rm) return 0 ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output --partial "${today}_daaf_backup"
    assert_output --partial "Backup complete"
}

@test "backup: writes .daaf-permissions manifest listing exec files on success" {
    export DAAF_NESTED=1
    local today
    today=$(date +%Y-%m-%d)

    # Custom docker mock: staging (`run -d` -> CID, `wait` -> 0) then `docker cp`
    # creates files; the permissions-manifest `docker run --rm ... find /source
    # -perm -0100` call is distinguished from the scan `docker run --rm ... wc -l`
    # call by the "-perm" substring, and returns two exec paths under /source
    # (which the script strips to volume-relative before writing).
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then echo "stagecid0000"; return 0; fi
                local args_str="$*"
                if [[ "${args_str}" == *"-perm -0100"* ]]; then
                    # Manifest generation: two exec files (absolute /source paths).
                    printf '/source/scripts/run.sh\n/source/hook.sh\n'
                else
                    # Scan: file count, du -sk, du -sh, logical KB
                    printf '5\n512\t/source\n500K\t/source\n500\n'
                fi
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                if [ -n "${dest_dir}" ]; then
                    mkdir -p "${dest_dir}"
                    touch "${dest_dir}/file1"
                fi
                return 0
                ;;
            rm) return 0 ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output --partial "Recorded"
    assert_output --partial "executable-permission manifest"
    # The manifest file exists in the backup root with volume-relative paths.
    run test -f "${TEST_DIR}/${today}_daaf_backup/.daaf-permissions"
    assert_success
    run cat "${TEST_DIR}/${today}_daaf_backup/.daaf-permissions"
    assert_output --partial "scripts/run.sh"
    assert_output --partial "hook.sh"
    refute_output --partial "/source/"
}

@test "backup: manifest preserves exec paths containing spaces verbatim" {
    export DAAF_NESTED=1
    local today
    today=$(date +%Y-%m-%d)

    # An exec file whose path contains spaces must survive the "/source/"-prefix strip
    # intact -- the `printf | sed | grep` manifest pipeline is whitespace-safe because
    # it operates line-by-line, not token-by-token. The manifest-generation `docker run
    # ... find -perm -0100` call is distinguished from the scan call by the "-perm"
    # substring; the data copy creates a file so FILE_COUNT > 0 and the script succeeds.
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then echo "stagecid0000"; return 0; fi
                local args_str="$*"
                if [[ "${args_str}" == *"-perm -0100"* ]]; then
                    # One exec path with spaces in a directory component.
                    printf '/source/research/path with spaces/run.sh\n'
                else
                    printf '5\n512\t/source\n500K\t/source\n500\n'
                fi
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                if [ -n "${dest_dir}" ]; then
                    mkdir -p "${dest_dir}"
                    touch "${dest_dir}/file1"
                fi
                return 0
                ;;
            rm) return 0 ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    # The manifest must contain the "/source/"-stripped path VERBATIM, spaces intact.
    run cat "${TEST_DIR}/${today}_daaf_backup/.daaf-permissions"
    assert_output --partial "research/path with spaces/run.sh"
    refute_output --partial "/source/"
}

@test "backup: scan failure exits with error" {
    MOCK_DOCKER_VOLUME_EXIT=0
    # docker run for scanning fails
    MOCK_DOCKER_RUN_EXIT=1
    MOCK_DOCKER_RUN_OUTPUT=""
    export DAAF_NESTED=1

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Could not scan"
}

# =========================================================================
# Dry-run mode
# =========================================================================

@test "backup_daaf.sh: dry-run completes successfully" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
}

@test "backup_daaf.sh: dry-run produces DRY-RUN markers" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/backup_daaf.sh" 2>&1
    assert_success
    assert_output --partial "[DRY-RUN]"
}

@test "backup_daaf.sh: dry-run shows backup summary" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/backup_daaf.sh" 2>&1
    assert_success
    assert_output --partial "Would create backup at"
}

# =========================================================================
# --- Error paths ---
# =========================================================================

@test "backup: copy failure with zero files exits with error" {
    export DAAF_NESTED=1

    # Custom docker mock: staging succeeds (`run -d` -> CID, `wait` -> 0), scan
    # succeeds, the `docker cp` copy fails (non-zero exit) and creates no files.
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then echo "stagecid0000"; return 0; fi
                # Scan output: file count, du -sk, du -sh, logical KB
                printf '50\n512\t/source\n500K\t/source\n500\n'
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            cp)     return 1 ;;
            rm)     return 0 ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
}

@test "backup: copy reports non-zero exit but full file count shows Note (not error) and latches WITH WARNINGS" {
    export DAAF_NESTED=1

    # Regression anchor for the Note path: a nonzero `docker cp` exit is NOT fatal
    # when the full expected file count still landed (no shortfall). The scan reports
    # 3 files and the mock copies exactly 3 -- so the corroborated short-copy fatal
    # branch (nonzero exit AND count short) does NOT fire; execution falls through to
    # the informational Note, which LATCHES the warnings banner: the copy itself
    # flagged a problem, so "Backup complete!" would overstate the run. Exit stays 0.
    # Only the DATA copy fails: the Claude-state copy (destination under
    # .daaf-claude-config) succeeds, and the size check is skipped (logical KB 0), so
    # the Note is the ONLY warning source -- the banner assertion below then fails if
    # the Note branch stops setting HAD_WARNINGS.
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then echo "stagecid0000"; return 0; fi
                # Permission-manifest scan: no exec files.
                case "$*" in *"-perm -0100"*) return 0 ;; esac
                # Scan output -- 3 files, matching the 3 the copy creates below;
                # logical KB 0 skips the size check.
                printf '3\n512\t/source\n500K\t/source\n0\n'
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                case "${dest_dir}" in
                    *.daaf-claude-config)
                        # Claude-state copy succeeds (no warning from that block).
                        mkdir -p "${dest_dir}"
                        touch "${dest_dir}/claude1"
                        return 0
                        ;;
                esac
                if [ -n "${dest_dir}" ]; then
                    mkdir -p "${dest_dir}"
                    touch "${dest_dir}/file1" "${dest_dir}/file2" "${dest_dir}/file3"
                fi
                # Non-zero exit, but the full count still landed
                return 1
                ;;
            rm) return 0 ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    # Succeeds (full count copied) and notes the warnings -- NOT the fatal error.
    assert_success
    assert_output --partial "Note: File copy reported warnings (exit code 1); 3 of 3 expected files were transferred."
    refute_output --partial "must not be relied on"
    refute_output --partial "Failed to back up the Claude Code state volume"
    refute_output --partial "file-count mismatch"
    assert_output --partial "Backup completed WITH WARNINGS -- verify before relying on it"
    refute_output --partial "Backup complete!"
}

@test "backup: non-zero copy exit with short file count is a fatal error" {
    export DAAF_NESTED=1

    # Corroborated short copy: the `docker cp` copy returns non-zero AND fewer files
    # land (2) than the scan counted (5). The two signals agree the backup is
    # truncated, so the script must abort fatally, naming the partial folder and
    # telling the user to delete it -- not pass it off as usable.
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then echo "stagecid0000"; return 0; fi
                # Scan reports 5 files; the copy below lands only 2.
                printf '5\n512\t/source\n500K\t/source\n500\n'
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                if [ -n "${dest_dir}" ]; then
                    mkdir -p "${dest_dir}"
                    touch "${dest_dir}/file1" "${dest_dir}/file2"
                fi
                # Non-zero exit with a short count -> fatal
                return 1
                ;;
            rm) return 0 ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "only 2 of 5 expected files were copied"
    assert_output --partial "must not be relied on"
    # Names the partial backup folder so the user can delete it.
    assert_output --partial "Location:"
    assert_output --partial "_daaf_backup"
}

@test "backup: zero-exit short file count warns (not fatal) and banner notes warnings" {
    export DAAF_NESTED=1

    # A clean ZERO copy exit that still lands too few files must NOT be fatal (the
    # fatal branch requires a corroborating nonzero exit). It is a WARNING: the scan
    # reports 100 files, the copy lands 2, the exit is 0. The file-count-mismatch
    # WARNING fires and the completion banner reads WITH WARNINGS, but the script
    # still exits 0 and never prints the fatal short-copy error. Logical KB is 0 so
    # the size check is skipped, isolating the file-count signal.
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then echo "stagecid0000"; return 0; fi
                # 100 files, logical KB 0 (skips size verification)
                printf '100\n512\t/source\n500K\t/source\n0\n'
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                if [ -n "${dest_dir}" ]; then
                    mkdir -p "${dest_dir}"
                    touch "${dest_dir}/file1" "${dest_dir}/file2"
                fi
                return 0
                ;;
            rm) return 0 ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "file-count mismatch"
    assert_output --partial "Backup completed WITH WARNINGS -- verify before relying on it"
    refute_output --partial "must not be relied on"
}

@test "backup: completion banner reads plain 'Backup complete!' on a clean run" {
    export DAAF_NESTED=1

    # A fully clean run -- full file count, no size drift (logical KB 0 skips the
    # size check), Claude state and permission manifest both succeed -- must print
    # the plain "Backup complete!" banner and NOT the WITH-WARNINGS variant.
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then echo "stagecid0000"; return 0; fi
                # 2 files, logical KB 0 (skips size verification)
                printf '2\n512\t/source\n500K\t/source\n0\n'
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                if [ -n "${dest_dir}" ]; then
                    mkdir -p "${dest_dir}"
                    touch "${dest_dir}/file1" "${dest_dir}/file2" "${dest_dir}/.daaf-symlinks"
                fi
                return 0
                ;;
            rm) return 0 ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "Backup complete!"
    refute_output --partial "WITH WARNINGS"
}

@test "backup: volume scan outputs unexpected format triggers error" {
    export DAAF_NESTED=1
    MOCK_DOCKER_VOLUME_EXIT=0

    # Custom docker mock: scan returns garbage output
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                # Return unexpected format
                printf 'unexpected_garbage_output\n'
                return 1
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
}

# =========================================================================
# --- Helper-container reap on staging launch failure ---
# =========================================================================
# `docker run -d` can fail AFTER creating the container (Created/Exited) while
# still printing its CID to stdout, which the command substitution captures. The
# launch guards must reap that captured CID (docker rm -f <cid>) so a launch
# failure does not leak a helper container. These mocks log every docker call to a
# file so the reap can be asserted after `run` (the DOCKER_CALLS array does not
# survive bats's `run` subshell). Each test would FAIL against the pre-fix code
# (main branch: no reap before exit 1; Claude branch: `|| CLAUDE_STAGE_CID=""`
# blanked the CID before any cleanup).

@test "backup: main staging launch failure reaps the captured helper container" {
    export DAAF_NESTED=1

    # The data-volume `docker run -d` prints a CID but exits nonzero. The error
    # branch must run `docker rm -f stagecid0000` before `exit 1`.
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        printf '%s\n' "$*" >> "${TEST_DIR}/docker_calls.log"
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then echo "stagecid0000"; return 1; fi
                printf '5\n512\t/source\n500K\t/source\n500\n'
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            cp)   return 0 ;;
            logs) echo ""; return 0 ;;
            rm)   return 0 ;;
            *)    return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    assert_output --partial "Could not start the staging container"
    # The captured CID must have been reaped in the error branch.
    run grep -F 'rm -f stagecid0000' "${TEST_DIR}/docker_calls.log"
    assert_success
}

@test "backup: Claude staging launch failure preserves and reaps the captured CID (WARNING, not fatal)" {
    export DAAF_NESTED=1

    # Data-volume backup succeeds; the Claude-volume `docker run -d` prints a CID but
    # exits nonzero. The fix keeps the captured CID (not `|| CLAUDE_STAGE_CID=""`) so
    # the end-of-block `docker rm -f claudestagecid` reaps it. Claude failure stays a
    # WARNING; the script still completes (the data backup is valid). Logical KB 0
    # skips the size check. The `run -d` arm distinguishes the two volumes by the
    # "claude-config" substring in the volume mount argument ($4, the -v value) --
    # not in the whole argument list, because the staging program text itself names
    # the ".daaf-claude-config" folder in its count exclusions.
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        printf '%s\n' "$*" >> "${TEST_DIR}/docker_calls.log"
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then
                    if printf '%s' "${4:-}" | grep -q 'claude-config'; then
                        echo "claudestagecid"; return 1
                    fi
                    echo "stagecid0000"; return 0
                fi
                printf '2\n512\t/source\n500K\t/source\n0\n'
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                if [ -n "${dest_dir}" ]; then
                    mkdir -p "${dest_dir}"
                    touch "${dest_dir}/file1" "${dest_dir}/file2"
                fi
                return 0
                ;;
            logs) echo ""; return 0 ;;
            rm)   return 0 ;;
            *)    return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "Failed to back up the Claude Code state volume"
    # The captured Claude CID must be reaped -- proving it was NOT blanked before cleanup.
    run grep -F 'rm -f claudestagecid' "${TEST_DIR}/docker_calls.log"
    assert_success
}

@test "backup: file-count tolerance floors to 1 for a small backup (clamp parity with PS)" {
    export DAAF_NESTED=1

    # For <100 files, TOTAL_FILES/100 truncates to 0; the clamp raises it to 1 so a
    # 1-file difference is tolerated (parity with the PS [math]::Max(1, ...) floor).
    # Scan reports 2 files; the data copy lands 3 files (diff = 1). With the clamp the
    # difference is within tolerance -> NO file-count-mismatch WARNING. Without the
    # clamp (tolerance 0) a diff of 1 would warn. Logical KB 0 skips the size check,
    # isolating the count signal.
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then echo "stagecid0000"; return 0; fi
                printf '2\n512\t/source\n500K\t/source\n0\n'
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                if [ -n "${dest_dir}" ]; then
                    mkdir -p "${dest_dir}"
                    touch "${dest_dir}/file1" "${dest_dir}/file2" "${dest_dir}/file3"
                fi
                return 0
                ;;
            rm) return 0 ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    refute_output --partial "file-count mismatch"
}

# =========================================================================
# --- FU1: a host read error makes the backup-folder count a LOWER BOUND ---
# =========================================================================
# _daaf_tree_count captures find's stderr with the count (count on the last line);
# any error line, a nonzero pipefail status, or a non-numeric last line makes the
# count a lower bound: shown as "N+", a WARNING that latches WITH WARNINGS, never
# "may be empty", never the corroborated fatal, and "could not be verified" (exit 1)
# when the lower bound is 0. The mock copy puts LOCKED_FILES files into a "locked"
# subfolder and chmods it 000 (teardown re-opens it); root reads through mode 000,
# so these skip there. NO_MANIFEST=1 omits the root .daaf-symlinks (FU4).
_mock_locked_copy_docker() {
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then echo "stagecid0000"; return 0; fi
                case "$*" in *"-perm -0100"*) return 0 ;; esac
                printf '%s\n512\t/source\n500K\t/source\n0\n' "${SCAN_COUNT}"
                return 0
                ;;
            wait) echo "0"; return 0 ;;
            logs)
                # shellcheck disable=SC2059 -- the test deliberately passes a printf format
                printf "${STAGE_LOG_TEXT}"
                return 0
                ;;
            cp)
                local dest_dir="" i=0
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                case "${dest_dir}" in *daaf-claude-config*) return 0 ;; esac
                mkdir -p "${dest_dir}"
                while [ "${i}" -lt "${CP_FILES}" ]; do touch "${dest_dir}/file${i}"; i=$((i + 1)); done
                if [ "${LOCKED_FILES:-0}" -gt 0 ]; then
                    mkdir -p "${dest_dir}/locked"
                    i=0
                    while [ "${i}" -lt "${LOCKED_FILES}" ]; do touch "${dest_dir}/locked/hidden${i}"; i=$((i + 1)); done
                    chmod 000 "${dest_dir}/locked"
                fi
                if [ "${NO_MANIFEST:-0}" != "1" ]; then touch "${dest_dir}/.daaf-symlinks"; fi
                return "${CP_EXIT:-0}"
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker
}

@test "backup FU1: an unreadable subfolder makes the count 'N+' with a WARNING and the WITH WARNINGS banner" {
    [ "$(id -u)" -ne 0 ] || skip "root can read a chmod-000 folder"
    # Snapshot 3 = 2 readable + 1 in the locked folder. Exit 0 (not fatal).
    export DAAF_NESTED=1 SCAN_COUNT=3 CP_FILES=2 LOCKED_FILES=1 STAGE_LOG_TEXT='STAGED_FILES=3\nSTAGED_KB=0\n'
    _mock_locked_copy_docker
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "WARNING: Could not read 1 folder(s) or file(s) in the backup folder, so the count"
    assert_output --partial "below is a LOWER BOUND (2+ files): the backup may be complete, but this"
    assert_output --partial "run could not prove it. Check that your user account can read every folder in it."
    assert_output --partial "First error: find:"
    assert_output --partial "Progress: 2+ / 3 files"
    # The mismatch label bounds the difference one way: a shortfall is "up to" it.
    assert_output --partial "Snapshot: 3 files, Backup: 2+ files (difference: up to 1; the backup count is a lower bound)"
    assert_output --partial "Some folders could not be read, so this run cannot tell whether these files"
    refute_output --partial "missing from this backup"
    refute_output --partial "may be empty"
    assert_output --partial "Backup completed WITH WARNINGS -- verify before relying on it"
    assert_output --partial "Files:    2+ files copied"
    refute_output --partial "Backup complete!"
}

@test "backup FU1: a lower-bound count ABOVE the snapshot is labelled 'at least'" {
    [ "$(id -u)" -ne 0 ] || skip "root can read a chmod-000 folder"
    # 2 readable files already exceed the 1-file snapshot, and more are unreadable.
    export DAAF_NESTED=1 SCAN_COUNT=1 CP_FILES=2 LOCKED_FILES=1 STAGE_LOG_TEXT='STAGED_FILES=1\nSTAGED_KB=0\n'
    _mock_locked_copy_docker
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "Snapshot: 1 files, Backup: 2+ files (difference: at least 1; the backup count is a lower bound)"
    assert_output --partial "Backup completed WITH WARNINGS"
}

@test "backup FU1: a lower bound of 0 says 'could not be verified' and exits 1 -- never 'may be empty'" {
    [ "$(id -u)" -ne 0 ] || skip "root can read a chmod-000 folder"
    # Every data file is inside the locked folder, so nothing can be counted: the
    # count is 0 AND a lower bound. The copy exit is 0.
    export DAAF_NESTED=1 SCAN_COUNT=2 CP_FILES=0 LOCKED_FILES=2 STAGE_LOG_TEXT='STAGED_FILES=2\nSTAGED_KB=0\n'
    _mock_locked_copy_docker
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure 1
    assert_output --partial "ERROR: The backup could not be verified: the backup folder could not be read, so no"
    assert_output --partial "files could be counted. This does not show the backup is empty, but do not"
    assert_output --partial "rely on it. Check that your user account can read the backup folder, then"
    assert_output --partial "re-run the backup."
    refute_output --partial "may be empty"
    refute_output --partial "0 files were copied"
    refute_output --partial "The file copy also reported an error"
    refute_output --partial "Backup complete!"
    refute_output --partial "Backup completed WITH WARNINGS"
}

@test "backup FU1: a zero lower bound with a nonzero copy exit also names the copy error (still exit 1)" {
    [ "$(id -u)" -ne 0 ] || skip "root can read a chmod-000 folder"
    export DAAF_NESTED=1 SCAN_COUNT=2 CP_FILES=0 LOCKED_FILES=2 CP_EXIT=1 STAGE_LOG_TEXT='STAGED_FILES=2\nSTAGED_KB=0\n'
    _mock_locked_copy_docker
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure 1
    assert_output --partial "ERROR: The backup could not be verified"
    assert_output --partial "The file copy also reported an error (exit code 1)."
    refute_output --partial "may be empty"
    refute_output --partial "ERROR: Backup failed"
}

@test "backup FU1: a nonzero copy exit with a SHORT lower-bound count is a WARNING, not the fatal ERROR" {
    [ "$(id -u)" -ne 0 ] || skip "root can read a chmod-000 folder"
    # Copy exit 1 and 2+ of 3: the corroborated short-copy branch would be fatal on an
    # exact count, but a lower bound is not a second signal (the "missing" file may
    # only be unreadable), so it is downgraded to a latched WARNING with exit 0.
    export DAAF_NESTED=1 SCAN_COUNT=3 CP_FILES=2 LOCKED_FILES=1 CP_EXIT=1 STAGE_LOG_TEXT='STAGED_FILES=3\nSTAGED_KB=0\n'
    _mock_locked_copy_docker
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "WARNING: The file copy reported an error (exit code 1), and only 2+ of 3"
    assert_output --partial "expected files could be counted. That count is a lower bound (some folders could not"
    refute_output --partial "ERROR: Backup failed"
    refute_output --partial "must not be relied on"
    refute_output --partial "may be empty"
    assert_output --partial "Backup completed WITH WARNINGS -- verify before relying on it"
}

@test "backup FU1: SELF-TEST -- the same copy with the folder readable is a clean exact count" {
    # Control for the tests above: LOCKED_FILES=0 lands the same 3 files readable.
    export DAAF_NESTED=1 SCAN_COUNT=3 CP_FILES=3 LOCKED_FILES=0 STAGE_LOG_TEXT='STAGED_FILES=3\nSTAGED_KB=0\n'
    _mock_locked_copy_docker
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    refute_output --partial "LOWER BOUND"
    refute_output --partial "2+"
    assert_output --partial "Files:    3 files copied"
    assert_output --partial "Backup complete!"
}

# =========================================================================
# --- FU4: the root .daaf-symlinks manifest must be in the copy ---
# =========================================================================
@test "backup FU4: a copy missing the root .daaf-symlinks warns, latches WITH WARNINGS, says re-run" {
    # Counts match the snapshot exactly (the count excludes the manifest), so the
    # missing manifest is the ONLY warning source.
    export DAAF_NESTED=1 SCAN_COUNT=2 CP_FILES=2 LOCKED_FILES=0 NO_MANIFEST=1 STAGE_LOG_TEXT='STAGED_FILES=2\nSTAGED_KB=0\n'
    _mock_locked_copy_docker
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "WARNING: The backup folder is missing its .daaf-symlinks file (every backup writes one),"
    assert_output --partial "so the copy did not finish cleanly."
    assert_output --partial "Re-run the backup; restoring this one would not recreate symbolic links."
    refute_output --partial "file-count mismatch"
    assert_output --partial "Backup completed WITH WARNINGS -- verify before relying on it"
    refute_output --partial "Backup complete!"
}

# =========================================================================
# UNCREATABLE NAMES (2026-09-30): the staging step that removes names Windows cannot
# create (DAAF_STAGE_NAMES=win, passed ONLY by backup_daaf.ps1) or lists case-only
# clashes (casewarn, this twin on macOS). Field failure: Windows `docker cp` (Docker
# Client 29.1.3) aborted at a file named `name<LF>nl` and dropped 1,399 of 73,785
# files. These run the REAL extracted STAGE_PROGRAM under the local sh (dash + GNU
# find/awk/tr/sort here, not busybox -- not installed) against fixtures holding hostile
# names. Every fixture lives under TEST_DIR, which the teardown removes on pass AND on
# failure (rm -rf handles every name used here).
# =========================================================================

# Build a source tree with one of every class the win step must remove, look-alikes it
# must keep, and symlinks inside and outside a removed folder.
_names_fixture() {
    local s="$1/source"
    mkdir -p "${s}/sub" "${s}/bad:dir/deep" "$1/ctmp"
    printf 'keep\n' > "${s}/normal.txt"
    : > "${s}/.hidden"
    : > "${s}/..twodots"
    : > "${s}/com0"
    : > "${s}/console"
    : > "${s}/nulx"
    : > "${s}/name"$'\n'"nl"
    : > "${s}/tab"$'\t'"name"
    : > "${s}/cr"$'\r'"name"
    : > "${s}/a<b"
    : > "${s}/a>b"
    : > "${s}/c:d"
    : > "${s}/q\"x"
    : > "${s}/p|x"
    : > "${s}/w?x"
    : > "${s}/s*x"
    : > "${s}/back\\slash"
    : > "${s}/trail."
    : > "${s}/trail "
    : > "${s}/sub/CON"
    : > "${s}/sub/nul.txt"
    : > "${s}/sub/Com1.log"
    : > "${s}/sub/lpt9"
    : > "${s}/sub/PRN.tar.gz"
    : > "${s}/sub/aux"
    : > "${s}/sub/COM"$'\xc2\xb9'
    : > "${s}/sub/lpt"$'\xc2\xb3'".x"
    : > "${s}/sub/conin\$"
    : > "${s}/sub/CONOUT\$.txt"
    : > "${s}/bad:dir/f1"
    : > "${s}/bad:dir/deep/f2"
    ln -s f1 "${s}/bad:dir/inner-link"
    ln -s ../normal.txt "${s}/sub/link:colon"
}

@test "backup names (win): every uncreatable class is removed, listed, and counted; look-alikes and outside symlinks stay" {
    local root="${TEST_DIR}/names"
    _names_fixture "${root}"
    _relocate_stage_program "${root}"
    run env DAAF_STAGE_NAMES=win sh "${root}/program.sh"
    assert_success
    # 24 top-level entries removed (23 files + the folder bad:dir, which takes its two
    # files and its symlink with it): 25 regular files in total.
    assert_output --partial "STAGED_STRIPPED_NAMES=24"
    assert_output --partial "STAGED_STRIPPED_FILES=25"
    # Kept: normal.txt .hidden ..twodots com0 console nulx -> 6 files.
    assert_output --partial "STAGED_FILES=6"
    # Every listed path follows the fixed prefix; control bytes are shown as "?".
    local tab=$'\t'
    assert_output --partial "STAGE_STRIP_NAME${tab}./name?nl"
    assert_output --partial "STAGE_STRIP_NAME${tab}./tab?name"
    assert_output --partial "STAGE_STRIP_NAME${tab}./cr?name"
    assert_output --partial "STAGE_STRIP_NAME${tab}./bad:dir"
    assert_output --partial "STAGE_STRIP_NAME${tab}./q\"x"
    assert_output --partial "STAGE_STRIP_NAME${tab}./back\\slash"
    assert_output --partial "STAGE_STRIP_NAME${tab}./trail "
    assert_output --partial "STAGE_STRIP_NAME${tab}./sub/COM"$'\xc2\xb9'
    assert_output --partial "STAGE_STRIP_NAME${tab}./sub/CONOUT\$.txt"
    # -prune: the removed folder's children are not listed separately.
    refute_output --partial "bad:dir/f1"
    # Nothing but the look-alikes, the kept folders, and the outside symlink remains.
    run bash -c "cd '${root}/staging' && LC_ALL=C find . -mindepth 1 ! -name .daaf-symlinks | LC_ALL=C sort | tr '\n' ' '"
    assert_output "./..twodots ./.hidden ./com0 ./console ./normal.txt ./nulx ./sub "
    # The outside symlink went to the manifest as before; the one inside the removed
    # folder never did (restore's replay would otherwise fail on a missing parent).
    run cat "${root}/staging/.daaf-symlinks"
    assert_output "$(printf './sub/link:colon\t../normal.txt')"
}

@test "backup names (win): markers stay LAST and a hostile name cannot spoof one" {
    local root="${TEST_DIR}/spoof"
    mkdir -p "${root}/source" "${root}/ctmp"
    : > "${root}/source/ok.txt"
    : > "${root}/source/x"$'\n'"STAGED_FILES=999"
    : > "${root}/source/y"$'\r'"STAGED_KB=999"
    _relocate_stage_program "${root}"
    run env DAAF_STAGE_NAMES=win sh "${root}/program.sh"
    assert_success
    # The real markers are the last lines, and no line of the log is a forged marker.
    [ "${lines[${#lines[@]}-2]}" = "STAGED_FILES=1" ]
    [ "${lines[${#lines[@]}-1]}" = "STAGED_KB=0" ]
    local log="${output}"
    run grep -cxE 'STAGED_(FILES|KB)=999' <<< "${log}"
    assert_output "0"
    # And the host-side parse (anchored, last match wins, CR removed) reads the truth.
    run bash -c "printf '%s\n' \"\$1\" | tr -d '\r' | sed -n 's/^STAGED_FILES=\([0-9][0-9]*\)\$/\1/p' | tail -n 1" _ "${log}"
    assert_output "1"
}

@test "backup names (win): case clashes -- file+file and file+folder keep the FIRST in byte order; folder+folder is listed and its clashing children resolved" {
    local root="${TEST_DIR}/case"
    local s="${root}/source"
    mkdir -p "${s}/CDIR" "${s}/cdir" "${s}/fD" "${s}/dF" "${root}/ctmp"
    printf 'upper\n' > "${s}/MF1"
    printf 'lower\n' > "${s}/mf1"
    : > "${s}/CDIR/x"
    : > "${s}/cdir/X"
    : > "${s}/cdir/y"
    : > "${s}/Fd"
    : > "${s}/fD/inner"
    : > "${s}/dF/in2"
    : > "${s}/df"
    _relocate_stage_program "${root}"
    run env DAAF_STAGE_NAMES=win sh "${root}/program.sh"
    assert_success
    local tab=$'\t'
    assert_output --partial "STAGE_CASE_FILE${tab}./mf1${tab}./MF1"
    assert_output --partial "STAGE_CASE_FILE${tab}./cdir/X${tab}./CDIR/x"
    assert_output --partial "STAGE_CASE_FILE${tab}./fD${tab}./Fd"
    assert_output --partial "STAGE_CASE_FILE${tab}./df${tab}./dF"
    assert_output --partial "STAGE_CASE_DIR${tab}./cdir${tab}./CDIR"
    # 4 entries removed: mf1, cdir/X, the folder fD (with inner), the file df.
    assert_output --partial "STAGED_STRIPPED_NAMES=4"
    assert_output --partial "STAGED_STRIPPED_FILES=4"
    assert_output --partial "STAGED_FILES=5"
    # The first in byte order survives with its own content; folder pairs both stay.
    run cat "${root}/staging/MF1"
    assert_output "upper"
    [ ! -e "${root}/staging/mf1" ]
    [ -f "${root}/staging/CDIR/x" ]
    [ -f "${root}/staging/cdir/y" ]
    [ ! -e "${root}/staging/cdir/X" ]
    [ -f "${root}/staging/Fd" ]
    [ ! -e "${root}/staging/fD" ]
    [ -d "${root}/staging/dF" ]
    [ ! -e "${root}/staging/df" ]
}

@test "backup names (casewarn): case clashes are LISTED only -- nothing removed, Windows-only names kept" {
    local root="${TEST_DIR}/cw"
    _names_fixture "${root}"
    printf 'upper\n' > "${root}/source/MF1"
    printf 'lower\n' > "${root}/source/mf1"
    _relocate_stage_program "${root}"
    run env DAAF_STAGE_NAMES=casewarn sh "${root}/program.sh"
    assert_success
    assert_output --partial "STAGE_CASE_FILE"$'\t'"./mf1"$'\t'"./MF1"
    refute_output --partial "STAGE_STRIP_NAME"
    refute_output --partial "STAGED_STRIPPED_"
    # Nothing was removed: every regular file (33, incl. MF1/mf1) is in the snapshot.
    assert_output --partial "STAGED_FILES=33"
    [ -f "${root}/staging/mf1" ]
    [ -f "${root}/staging/c:d" ]
    [ -f "${root}/staging/name"$'\n'"nl" ]
}

@test "backup names (switch off): unset or empty DAAF_STAGE_NAMES removes and lists nothing (macOS/Linux names are legal)" {
    local root="${TEST_DIR}/off" mode
    for mode in unset empty; do
        rm -rf "${root}"
        _names_fixture "${root}"
        : > "${root}/source/MF1"
        : > "${root}/source/mf1"
        _relocate_stage_program "${root}"
        if [ "${mode}" = unset ]; then
            run env -u DAAF_STAGE_NAMES sh "${root}/program.sh"
        else
            run env DAAF_STAGE_NAMES= sh "${root}/program.sh"
        fi
        echo "case: ${mode}"
        assert_success
        # Exactly the two snapshot markers, as before this step existed.
        assert_output "$(printf 'STAGED_FILES=33\nSTAGED_KB=0')"
        [ -f "${root}/staging/c:d" ]
        [ -f "${root}/staging/sub/CON" ]
        [ -f "${root}/staging/bad:dir/deep/f2" ]
    done
}

@test "backup names (win): a TAB-named symlink still hits the fatal gate (exit 3) -- symlinks are never removed by the name step" {
    local root="${TEST_DIR}/tabl"
    mkdir -p "${root}/source" "${root}/ctmp"
    : > "${root}/source/t.txt"
    ln -s t.txt "${root}/source/bad"$'\t'"link"
    _relocate_stage_program "${root}"
    run env DAAF_STAGE_NAMES=win sh "${root}/program.sh"
    [ "${status}" -eq 3 ]
    assert_output --partial "STAGE_ERR_TAB"
    refute_output --partial "STAGE_STRIP_NAME"
}

@test "backup names: the step sits after cd /staging and before the symlink manifest (pinned tail unchanged)" {
    run _extract_stage_program
    assert_success
    [ "${lines[2]}" = 'cd /staging' ]
    [ "${lines[3]}" = 'if [ ${DAAF_STAGE_NAMES:-0} = win ] || [ ${DAAF_STAGE_NAMES:-0} = casewarn ]; then' ]
    local i manifest_idx=-1 step_end=-1
    for i in "${!lines[@]}"; do
        [ "${lines[$i]}" = 'find . -type l > /tmp/link_paths' ] && manifest_idx="${i}"
        [ "${lines[$i]}" = 'echo STAGED_STRIPPED_FILES=$((before - after))' ] && step_end="${i}"
    done
    [ "${step_end}" -gt 3 ]
    [ "${manifest_idx}" -gt "${step_end}" ]
    # The removal only runs in win mode, and it never touches a symlink itself.
    run grep -c -- '-prune -print0 -exec rm -rf {} + > /tmp/name_list' <(_extract_stage_program)
    assert_output "1"
    run grep -c -- 'find . -mindepth 1 ! -type l ' <(_extract_stage_program)
    assert_output "1"
}

# Mock for the host-side name handling: records every `docker run -d` argument list in
# RUN_D_ARGS_FILE, returns a distinct CID for the Claude volume, and serves DATA_LOG /
# CLAUDE_LOG (printf formats) from `docker logs <cid>`. CP_EXIT / CLAUDE_CP_EXIT set the
# data / Claude `docker cp` exit status (default 0); CLAUDE_WAIT sets the Claude
# staging status `docker wait` prints (default 0).
_mock_names_docker() {
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then
                    printf '%s\n' "$*" >> "${RUN_D_ARGS_FILE}"
                    case "${4:-}" in *claude-config*) echo "claudecid" ;; *) echo "datacid" ;; esac
                    return 0
                fi
                printf '%s\n512\t/source\n500K\t/source\n0\n' "${SCAN_COUNT}"
                return 0
                ;;
            wait) case "$2" in claudecid) echo "${CLAUDE_WAIT:-0}" ;; *) echo "0" ;; esac; return 0 ;;
            logs)
                # shellcheck disable=SC2059 -- the test deliberately passes printf formats
                case "$2" in claudecid) printf "${CLAUDE_LOG}" ;; *) printf "${DATA_LOG}" ;; esac
                return 0
                ;;
            cp)
                local dest_dir="" i=0
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                mkdir -p "${dest_dir}"
                case "${dest_dir}" in *daaf-claude-config*) touch "${dest_dir}/c1"; return "${CLAUDE_CP_EXIT:-0}" ;; esac
                while [ "${i}" -lt "${CP_FILES}" ]; do touch "${dest_dir}/file${i}"; i=$((i + 1)); done
                touch "${dest_dir}/.daaf-symlinks"
                return "${CP_EXIT:-0}"
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker
}

@test "backup names (.sh host): Linux passes an EMPTY switch, macOS passes casewarn, and this twin never passes win" {
    export DAAF_NESTED=1 SCAN_COUNT=2 CP_FILES=2 RUN_D_ARGS_FILE="${TEST_DIR}/run_d_args"
    export DATA_LOG='STAGED_FILES=2\nSTAGED_KB=0\n' CLAUDE_LOG='STAGED_FILES=1\nSTAGED_KB=0\n'
    _mock_names_docker
    uname() { echo Linux; }
    export -f uname
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    # Both staging launches (data + Claude) carry the switch AFTER the -v, value empty.
    run grep -c -- "-d -v [^ ]*:/source:ro -e DAAF_STAGE_NAMES= ${DAAF_BUSYBOX_PIN_RE} sh -c" "${RUN_D_ARGS_FILE}"
    assert_output "2"
    rm -f "${RUN_D_ARGS_FILE}"
    uname() { echo Darwin; }
    export -f uname
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "Backup complete!"
    run grep -c -- "-d -v [^ ]*:/source:ro -e DAAF_STAGE_NAMES=casewarn ${DAAF_BUSYBOX_PIN_RE} sh -c" "${RUN_D_ARGS_FILE}"
    assert_output "2"
    # D1: removal is Windows-only -- the .sh twin has no way to request it.
    run grep -c 'DAAF_STAGE_NAMES=win' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output "0"
}

@test "backup names (.sh host, macOS): listed case clashes print a WARNING per volume, latch WITH WARNINGS, exit 0" {
    export DAAF_NESTED=1 SCAN_COUNT=2 CP_FILES=2 RUN_D_ARGS_FILE="${TEST_DIR}/run_d_args"
    export DATA_LOG='STAGE_CASE_FILE\t./a/mf1\t./a/MF1\nSTAGE_CASE_DIR\t./cdir\t./CDIR\nSTAGED_FILES=2\nSTAGED_KB=0\n'
    export CLAUDE_LOG='STAGE_CASE_FILE\t./s/x\t./s/X\nSTAGED_FILES=1\nSTAGED_KB=0\n'
    _mock_names_docker
    uname() { echo Darwin; }
    export -f uname
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "WARNING: 2 path(s) in the Docker volume are the same as another path except for upper/lower"
    assert_output --partial "         case (like ./Data/x and ./data/x). This Mac's disk most likely treats each pair as ONE"
    assert_output --partial "           ./a/mf1   (same as ./a/MF1 except for upper/lower case)"
    assert_output --partial "           ./cdir   (same as ./CDIR except for upper/lower case)"
    assert_output --partial "WARNING: 1 path(s) in the Claude Code state volume are the same as another path except for upper/lower"
    assert_output --partial "Rename one name of each pair inside DAAF, then back up again."
    # Nothing was removed, so the counts are exact and not blamed on anything.
    assert_output --partial "Snapshot: 2 files."
    refute_output --partial "file-count mismatch"
    assert_output --partial "Backup completed WITH WARNINGS -- verify before relying on it"
    # The same clash lines on Linux are never reported (the step does not run there;
    # this proves the report is tied to the mode, not to stray log text).
    uname() { echo Linux; }
    export -f uname
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    refute_output --partial "the same as another path except for upper/lower"
    assert_output --partial "Backup complete!"
}

@test "backup names (.sh host): the report caps its list at 20 entries with 'and N more'" {
    export DAAF_NESTED=1 SCAN_COUNT=2 CP_FILES=2 RUN_D_ARGS_FILE="${TEST_DIR}/run_d_args" CLAUDE_LOG=''
    local i log=''
    for i in $(seq 1 23); do log="${log}STAGE_CASE_FILE\\t./n${i}\\t./N${i}\\n"; done
    export DATA_LOG="${log}STAGED_FILES=2\\nSTAGED_KB=0\\n"
    _mock_names_docker
    uname() { echo Darwin; }
    export -f uname
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "WARNING: 23 path(s) in the Docker volume"
    assert_output --partial "./n20   (same as ./N20"
    refute_output --partial "./n21   (same as"
    assert_output --partial "           ... and 3 more"
}

@test "backup names (.sh host): stripped files are subtracted before the Snapshot line blames live-volume change" {
    export DAAF_NESTED=1 CP_FILES=2 RUN_D_ARGS_FILE="${TEST_DIR}/run_d_args" CLAUDE_LOG=''
    _mock_names_docker
    uname() { echo Linux; }
    export -f uname
    # Scan 5 = snapshot 2 + 3 stripped: no live change, so no "live volume changed".
    export SCAN_COUNT=5 DATA_LOG='STAGED_STRIPPED_NAMES=1\nSTAGED_STRIPPED_FILES=3\nSTAGED_FILES=2\nSTAGED_KB=0\n'
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "Snapshot: 2 files (3 more left out because their names cannot be"
    refute_output --partial "live volume changed"
    refute_output --partial "file-count mismatch"
    # Scan 6 = snapshot 2 + 3 stripped + 1 file that vanished before the snapshot.
    export SCAN_COUNT=6
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "Apart from those, the snapshot has 1 fewer files than the scan -- the live"
}

# --- Review round 7: adversarial names + report placement ---------------------------
# Fixtures are built under TEST_DIR (removed by the teardown on pass AND failure); no
# fixture name reaches the workspace outside it.

@test "backup names (win, adversarial): leading dash, spaces, %s, a TAB folder with children, a hostile folder hiding a clash, a forged-marker newline name" {
    local root="${TEST_DIR}/adv" tab=$'\t'
    local s="${root}/source"
    mkdir -p "${s}/sp ace" "${s}/tab${tab}dir/sub" "${s}/bad|dir" "${root}/ctmp"
    printf 'upper\n' > "${s}/-LEAD"
    printf 'lower\n' > "${s}/-lead"
    : > "${s}/sp ace/My File"
    : > "${s}/sp ace/my file"
    : > "${s}/PCT%sX"
    : > "${s}/pct%sX"
    : > "${s}/only%s%d"
    : > "${s}/tab${tab}dir/c1"
    : > "${s}/tab${tab}dir/sub/c2"
    : > "${s}/bad|dir/X"
    : > "${s}/bad|dir/x"
    : > "${s}/x"$'\n'"STAGE_CASE_FILE${tab}evil${tab}EVIL"
    _relocate_stage_program "${root}"
    run env DAAF_STAGE_NAMES=win sh "${root}/program.sh"
    assert_success
    # Case clashes: the byte-order first survives (upper case sorts first).
    assert_output --partial "STAGE_CASE_FILE${tab}./-lead${tab}./-LEAD"
    assert_output --partial "STAGE_CASE_FILE${tab}./sp ace/my file${tab}./sp ace/My File"
    assert_output --partial "STAGE_CASE_FILE${tab}./pct%sX${tab}./PCT%sX"
    # Hostile names: the TAB folder and the | folder go with their children (-prune:
    # the children are not listed, and the clash inside bad|dir is never reported);
    # the newline name is ONE line under the fixed prefix, control bytes shown as ?.
    assert_output --partial "STAGE_STRIP_NAME${tab}./tab?dir"
    assert_output --partial "STAGE_STRIP_NAME${tab}./bad|dir"
    assert_output --partial "STAGE_STRIP_NAME${tab}./x?STAGE_CASE_FILE?evil?EVIL"
    refute_output --partial "c1"
    refute_output --partial "bad|dir/"
    # No forged line: nothing starts with the case prefix and names the evil paths.
    run grep -c "^STAGE_CASE_FILE${tab}evil" <<< "${output}"
    assert_output "0"
    # 6 entries removed (3 hostile + 3 clash losers) holding 8 regular files; 4 kept.
    run cat "${root}/staging/-LEAD"
    assert_output "upper"
    [ ! -e "${root}/staging/-lead" ]
    [ -f "${root}/staging/sp ace/My File" ]
    [ ! -e "${root}/staging/sp ace/my file" ]
    [ -f "${root}/staging/PCT%sX" ]
    [ ! -e "${root}/staging/pct%sX" ]
    [ -f "${root}/staging/only%s%d" ]
    [ ! -e "${root}/staging/tab${tab}dir" ]
    [ ! -e "${root}/staging/bad|dir" ]
    run bash -c "cd '${root}/staging' && LC_ALL=C find . -type f ! -name .daaf-symlinks | LC_ALL=C sort | tr '\n' '|'"
    assert_output "./-LEAD|./PCT%sX|./only%s%d|./sp ace/My File|"
}

@test "backup names (win, adversarial): marker counts for the adversarial fixture" {
    local root="${TEST_DIR}/advc" tab=$'\t'
    local s="${root}/source"
    mkdir -p "${s}/sp ace" "${s}/tab${tab}dir/sub" "${s}/bad|dir" "${root}/ctmp"
    : > "${s}/-LEAD"; : > "${s}/-lead"
    : > "${s}/sp ace/My File"; : > "${s}/sp ace/my file"
    : > "${s}/PCT%sX"; : > "${s}/pct%sX"; : > "${s}/only%s%d"
    : > "${s}/tab${tab}dir/c1"; : > "${s}/tab${tab}dir/sub/c2"
    : > "${s}/bad|dir/X"; : > "${s}/bad|dir/x"
    : > "${s}/x"$'\n'"STAGE_CASE_FILE${tab}evil${tab}EVIL"
    _relocate_stage_program "${root}"
    run env DAAF_STAGE_NAMES=win sh "${root}/program.sh"
    assert_success
    assert_output --partial "STAGED_STRIPPED_NAMES=6"
    assert_output --partial "STAGED_STRIPPED_FILES=8"
    [ "${lines[${#lines[@]}-2]}" = "STAGED_FILES=4" ]
    [ "${lines[${#lines[@]}-1]}" = "STAGED_KB=0" ]
}

@test "backup names (casewarn, adversarial): backslash, dash and %s clashes are LISTED verbatim; control-byte paths are never listed; nothing removed" {
    local root="${TEST_DIR}/advw" tab=$'\t'
    local s="${root}/source"
    mkdir -p "${s}/tab${tab}dir" "${root}/ctmp"
    : > "${s}/BACK\\slash"
    : > "${s}/back\\slash"
    : > "${s}/-LEAD"
    : > "${s}/-lead"
    : > "${s}/PCT%sX"
    : > "${s}/pct%sX"
    : > "${s}/tab${tab}dir/A"
    : > "${s}/tab${tab}dir/a"
    : > "${s}/x"$'\n'"STAGE_CASE_FILE${tab}evil${tab}EVIL"
    _relocate_stage_program "${root}"
    run env DAAF_STAGE_NAMES=casewarn sh "${root}/program.sh"
    assert_success
    assert_output --partial "STAGE_CASE_FILE${tab}./back\\slash${tab}./BACK\\slash"
    assert_output --partial "STAGE_CASE_FILE${tab}./-lead${tab}./-LEAD"
    assert_output --partial "STAGE_CASE_FILE${tab}./pct%sX${tab}./PCT%sX"
    # A clash under a control-byte path cannot be listed unambiguously, so it is left
    # out of the list (the zero-tolerance count still reports any loss); the forged
    # marker inside a newline name never becomes a line of its own.
    refute_output --partial "tab"
    refute_output --partial "evil"
    refute_output --partial "STAGE_STRIP_NAME"
    refute_output --partial "STAGED_STRIPPED_"
    [ "$(grep -c "^STAGE_CASE_" <<< "${output}")" -eq 3 ]
    # Nothing removed: all 9 regular files are in the snapshot.
    [ "${lines[${#lines[@]}-2]}" = "STAGED_FILES=9" ]
    [ -f "${root}/staging/back\\slash" ]
    [ -f "${root}/staging/-lead" ]
    [ -f "${root}/staging/tab${tab}dir/a" ]
}

@test "backup names (.sh host, macOS): a backslash path from the staging log is reported verbatim" {
    export DAAF_NESTED=1 SCAN_COUNT=2 CP_FILES=2 RUN_D_ARGS_FILE="${TEST_DIR}/run_d_args" CLAUDE_LOG=''
    # DATA_LOG is a printf format: \\ prints one backslash.
    export DATA_LOG='STAGE_CASE_FILE\t./back\\slash\t./BACK\\slash\nSTAGED_FILES=2\nSTAGED_KB=0\n'
    _mock_names_docker
    uname() { echo Darwin; }
    export -f uname
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial '           ./back\slash   (same as ./BACK\slash except for upper/lower case)'
}

@test "backup names (.sh host, macOS): the case list prints BEFORE a fatal short-copy exit, exactly once (review round 7)" {
    export DAAF_NESTED=1 SCAN_COUNT=3 CP_FILES=2 CP_EXIT=1 RUN_D_ARGS_FILE="${TEST_DIR}/run_d_args" CLAUDE_LOG=''
    export DATA_LOG='STAGE_CASE_FILE\t./fD\t./Fd\nSTAGED_FILES=3\nSTAGED_KB=0\n'
    _mock_names_docker
    uname() { echo Darwin; }
    export -f uname
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    assert_output --partial "ERROR: Backup failed (exit code 1); only 2 of 3 expected files were copied."
    local warn="WARNING: 1 path(s) in the Docker volume are the same as another path except for upper/lower"
    [ "$(grep -cF "${warn}" <<< "${output}")" -eq 1 ]
    assert_output --partial "           ./fD   (same as ./Fd except for upper/lower case)"
    # Order: the list comes before the fatal ERROR.
    local w e
    w="$(grep -nF "${warn}" <<< "${output}" | cut -d: -f1)"
    e="$(grep -nF "ERROR: Backup failed" <<< "${output}" | cut -d: -f1)"
    [ "${w}" -lt "${e}" ]
}

@test "backup names (.sh host, macOS): the case list prints BEFORE the zero-files fatal exit too" {
    export DAAF_NESTED=1 SCAN_COUNT=1 CP_FILES=0 CP_EXIT=1 RUN_D_ARGS_FILE="${TEST_DIR}/run_d_args" CLAUDE_LOG=''
    export DATA_LOG='STAGE_CASE_FILE\t./fD\t./Fd\nSTAGED_FILES=1\nSTAGED_KB=0\n'
    _mock_names_docker
    uname() { echo Darwin; }
    export -f uname
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    local warn="WARNING: 1 path(s) in the Docker volume are the same as another path except for upper/lower"
    [ "$(grep -cF "${warn}" <<< "${output}")" -eq 1 ]
    local w e
    w="$(grep -nF "${warn}" <<< "${output}" | cut -d: -f1)"
    e="$(grep -nF "ERROR: Backup failed (exit code 1)" <<< "${output}" | cut -d: -f1)"
    [ -n "${e}" ]
    [ "${w}" -lt "${e}" ]
}

@test "backup names (.sh host, macOS): a FAILED Claude copy still prints that volume's case list, once" {
    export DAAF_NESTED=1 SCAN_COUNT=2 CP_FILES=2 CLAUDE_CP_EXIT=1 RUN_D_ARGS_FILE="${TEST_DIR}/run_d_args"
    export DATA_LOG='STAGED_FILES=2\nSTAGED_KB=0\n'
    export CLAUDE_LOG='STAGE_CASE_FILE\t./s/x\t./s/X\nSTAGED_FILES=1\nSTAGED_KB=0\n'
    _mock_names_docker
    uname() { echo Darwin; }
    export -f uname
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "WARNING: Failed to back up the Claude Code state volume."
    local warn="WARNING: 1 path(s) in the Claude Code state volume are the same as another path except for upper/lower"
    [ "$(grep -cF "${warn}" <<< "${output}")" -eq 1 ]
    assert_output --partial "           ./s/x   (same as ./s/X except for upper/lower case)"
    assert_output --partial "Backup completed WITH WARNINGS -- verify before relying on it"
}

# --- Polish 2026-10-01 (g): an unreadable macOS case list is not silent -------------

@test "backup names (.sh host, macOS): a data-volume log without its final marker warns that the case list could not be read" {
    export DAAF_NESTED=1 SCAN_COUNT=2 CP_FILES=2 RUN_D_ARGS_FILE="${TEST_DIR}/run_d_args"
    export DATA_LOG='' CLAUDE_LOG='STAGED_FILES=1\nSTAGED_KB=0\n'
    _mock_names_docker
    uname() { echo Darwin; }
    export -f uname
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "WARNING: Could not read the list of paths in the Docker volume that differ only in upper/lower"
    assert_output --partial "         case, so such pairs may be in this backup without being named here (this Mac's"
    assert_output --partial "         comes back, list such names inside DAAF with:"
    assert_output --partial "           bash scripts/check_workspace_invariants.sh --names-only"
    refute_output --partial "DAAF_INVARIANT_ROOT"
    refute_output --partial "Could not read the list of paths in the Claude Code state volume"
    assert_output --partial "Backup completed WITH WARNINGS -- verify before relying on it"
    # A log that ends in STAGED_COUNT_ERRORS (the count hit read errors) WAS read to its
    # end: no list warning, and its case lines are still reported.
    export DATA_LOG='STAGE_CASE_FILE\t./a\t./A\nSTAGED_COUNT_ERRORS=1\n'
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    refute_output --partial "Could not read the list of paths"
    assert_output --partial "           ./a   (same as ./A except for upper/lower case)"
    # Linux: the step does not run, so the same unreadable log never warns.
    uname() { echo Linux; }
    export -f uname
    export DATA_LOG='' CLAUDE_LOG=''
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    refute_output --partial "Could not read the list of paths"
}

@test "backup names (.sh host, macOS): an unreadable Claude-volume case list warns with the DAAF_INVARIANT_ROOT hint; a failed Claude staging does not" {
    export DAAF_NESTED=1 SCAN_COUNT=2 CP_FILES=2 RUN_D_ARGS_FILE="${TEST_DIR}/run_d_args"
    export DATA_LOG='STAGED_FILES=2\nSTAGED_KB=0\n' CLAUDE_LOG=''
    _mock_names_docker
    uname() { echo Darwin; }
    export -f uname
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "WARNING: Could not read the list of paths in the Claude Code state volume that differ only in upper/lower"
    assert_output --partial "           DAAF_INVARIANT_ROOT=/home/appuser/.claude bash scripts/check_workspace_invariants.sh --names-only"
    # --names-only runs only the names check, so the old "read only its names part /
    # do not delete" caveat is gone (review round 9).
    refute_output --partial "read only its"
    # The hinted path is the Claude volume's mount point in docker-compose.yml.
    run grep -cF -- '- daaf-claude-config:/home/appuser/.claude' "${REPO_ROOT}/docker-compose.yml"
    assert_output "1"
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    refute_output --partial "Could not read the list of paths in the Docker volume"
    assert_output --partial "Claude Code state backed up"
    assert_output --partial "Backup completed WITH WARNINGS -- verify before relying on it"
    # A FAILED Claude staging never printed its marker; its own WARNING covers it.
    export CLAUDE_WAIT=3
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "WARNING: Failed to back up the Claude Code state volume."
    refute_output --partial "Could not read the list of paths"
}

@test "backup names: the .sh case report sits before both fatal exits; the Claude report after its if/else (structure pin)" {
    local f="${REPO_ROOT}/scripts/host/backup_daaf.sh" call prog zero fatal
    call="$(grep -nF '_daaf_case_report "${STAGE_DONE_LOG}" "Docker volume"' "${f}" | cut -d: -f1)"
    prog="$(grep -nF 'printf "\r  Progress: %s / %d files (%d%%)   \n"' "${f}" | cut -d: -f1)"
    zero="$(grep -nxF 'if [ "${FILE_COUNT}" -eq 0 ]; then' "${f}" | cut -d: -f1)"
    fatal="$(grep -n '^# --- Corroborated short-copy check (fatal) ---' "${f}" | cut -d: -f1)"
    [ -n "${call}" ]
    [ -n "${prog}" ]
    [ -n "${zero}" ]
    [ -n "${fatal}" ]
    [ "$(grep -c '_daaf_case_report "' "${f}")" -eq 2 ]
    [ "${prog}" -lt "${call}" ]
    [ "${call}" -lt "${zero}" ]
    [ "${call}" -lt "${fatal}" ]
    local ccall valid
    ccall="$(grep -nF '_daaf_case_report "${CLAUDE_STAGE_DONE_LOG}"' "${f}" | cut -d: -f1)"
    valid="$(grep -n 'The data volume backup above is still valid' "${f}" | cut -d: -f1)"
    [ "${ccall}" -gt "${valid}" ]
}

# =========================================================================
# --- Fix pass #26 (F1 compatibility): version check, helper image check, pin ---
# =========================================================================
# Right after `docker info` the backup reads `docker version` and refuses (exit 1,
# nothing created) when the client or Engine major is below 25 or cannot be read; any
# major other than the tested 29 prints a NOTE and continues (no WARNING latch). After
# the volume check it makes sure the PINNED helper image is present (`docker pull` when
# `image inspect` fails; refuse when the pull fails) -- before the backup folder is
# created and before the scan. Every docker mock here delegates those calls to
# test_helper's mock_docker_shared_arms; MOCK_DOCKER_ARGV_LOG records every call's argv.
# The clean-run fixture is _mock_snapshot_docker with matching markers (see above).

_f1_backup_clean_env() {
    export DAAF_NESTED=1 SCAN_COUNT=2 CP_FILES=2 STAGE_LOG_TEXT='STAGED_FILES=2\nSTAGED_KB=0\n'
    export MOCK_DOCKER_ARGV_LOG="${TEST_DIR}/argv.log"
    : > "${MOCK_DOCKER_ARGV_LOG}"
    _mock_snapshot_docker
}

# No backup folder was created in the working directory (TEST_DIR).
_f1_no_backup_folder() {
    local d
    for d in "${TEST_DIR}"/*_daaf_backup; do
        if [ -e "${d}" ]; then echo "unexpected backup folder: ${d}"; return 1; fi
    done
}

# The backup's version-refusal block for client $1 / Engine $2 ($3 = "old" | "read").
_f1_backup_version_refusal() {
    local first
    if [ "$3" = old ]; then
        first="ERROR: This Docker version is too old for the backup (Docker client $1, Docker Engine $2)."
    else
        first="ERROR: Could not read the Docker version (Docker client $1, Docker Engine $2)."
    fi
    printf '%s\n' "${first}" \
        '       The backup needs Docker 25.0 or newer, for both the Docker client and Docker Engine' \
        '       (Docker Desktop 4.27.1 or newer). Update Docker, then run the backup again.' \
        '       (Docker Desktop or Docker Engine is required; Podman is not supported.)' \
        '       Nothing was changed.'
}

@test "F1 version (backup): 29.x prints no NOTE; another major >= 25 prints the NOTE once and the backup completes cleanly" {
    local c v note
    for c in \
        "29.1.3 29.1.3|" \
        $'WARNING: a notice line\n29.0.0 29.4.1\n|' \
        "25.0.2 29.1.3|NOTE: The backup has not been tested with this Docker version (Docker client 25.0.2, Docker Engine 29.1.3; tested: 29). Continuing." \
        "30.0.0 30.0.0|NOTE: The backup has not been tested with this Docker version (Docker client 30.0.0, Docker Engine 30.0.0; tested: 29). Continuing."; do
        v="${c%%|*}"
        note="${c#*|}"
        rm -rf "${TEST_DIR:?}"/*_daaf_backup
        _f1_backup_clean_env
        export MOCK_DOCKER_VERSION="${v}"
        run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
        echo "case version=[${v}]"
        assert_success
        assert_output --partial "Backup complete!"
        refute_output --partial "WITH WARNINGS"
        refute_output --partial "ERROR:"
        if [ -z "${note}" ]; then
            refute_output --partial "NOTE: The backup has not been tested"
        else
            assert_output --partial "${note}"
            [ "$(grep -c 'NOTE: The backup has not been tested' <<< "${output}")" -eq 1 ]
        fi
    done
}

@test "F1 version (backup): below 25 or unreadable refuses, exit 1, the exact ERROR lines on stderr, NO docker call after info + version, no folder" {
    local c v kind shown
    # "<docker version stdout>|<old|read>|<client shown> <Engine shown>"
    for c in "24.0.7 29.1.3|old|24.0.7 29.1.3" "29.1.3 24.0.7|old|29.1.3 24.0.7" "|read|unknown unknown" "29.1.3|read|29.1.3 unknown" "abc def|read|abc def"; do
        v="${c%%|*}"
        kind="${c#*|}"; kind="${kind%%|*}"
        shown="${c##*|}"
        _f1_backup_clean_env
        export MOCK_DOCKER_VERSION="${v}"
        run bash -c 'bash "'"${REPO_ROOT}"'/scripts/host/backup_daaf.sh" 2>&1 > /dev/null'
        echo "case version=[${v}]"
        assert_failure 1
        assert_output "$(_f1_backup_version_refusal "${shown% *}" "${shown#* }" "${kind}")"
        run mock_docker_argv_show "${MOCK_DOCKER_ARGV_LOG}"
        assert_output "$(printf '%s\n' '[info]' '[version] [--format] [{{.Client.Version}} {{.Server.Version}}]')"
        _f1_no_backup_folder
    done
}

# Review fix round 9 (ISSUE 1): the old-Engine hint in the `docker info` failure branch
# (see restore_from_backup.bats, "F1 info hint"). The backup prints its "not running"
# line on STDOUT, and the hint follows it there. Client $1.
_f1_backup_info_hint() {
    printf '%s\n' \
        "       If Docker is running, its Docker Engine may be older than 25.0 (Docker client $1)." \
        '       The backup needs Docker 25.0 or newer (Docker Desktop 4.27.1 or newer).'
}

@test "F1 info hint (backup): docker info fails, client >= 25 and an empty or unparsable Engine -> the 'not running' line plus the old-Engine hint (stdout), exit 1, nothing after info + version, no folder" {
    export DAAF_NESTED=1 MOCK_DOCKER_INFO_EXIT=1 MOCK_DOCKER_ARGV_LOG="${TEST_DIR}/argv.log"
    local c v exitc client
    # "<docker version stdout>|<its exit>|<client shown>"
    for c in "29.1.3|1|29.1.3" "29.1.3 |1|29.1.3" "25.0.0 abc|0|25.0.0" $'WARNING: a notice\n30.0.1|1|30.0.1' "29.1.3 v24.0.7|1|29.1.3"; do
        v="${c%%|*}"
        exitc="${c#*|}"; exitc="${exitc%%|*}"
        client="${c##*|}"
        export MOCK_DOCKER_VERSION="${v}" MOCK_DOCKER_VERSION_EXIT="${exitc}"
        : > "${MOCK_DOCKER_ARGV_LOG}"
        # stdout only, its last 3 lines (the banner is above them); stderr must be empty.
        run bash -c 'bash "'"${REPO_ROOT}"'/scripts/host/backup_daaf.sh" < /dev/null 2> "'"${TEST_DIR}"'/stderr.txt" | tail -n 3; exit "${PIPESTATUS[0]}"'
        echo "case version=[${v}] exit=${exitc}"
        assert_failure 1
        assert_output "$(printf '%s\n' 'ERROR: Docker Desktop does not seem to be running. Please start it and try again.'; _f1_backup_info_hint "${client}")"
        [ ! -s "${TEST_DIR}/stderr.txt" ]
        run mock_docker_argv_show "${MOCK_DOCKER_ARGV_LOG}"
        assert_output "$(printf '%s\n' '[info]' '[version] [--format] [{{.Client.Version}} {{.Server.Version}}]')"
        _f1_no_backup_folder
    done
}

@test "F1 info hint (backup): docker info fails and the client is below 25, unparsable or absent, or the Engine version reads -> ONLY the unchanged 'not running' line, exit 1" {
    export DAAF_NESTED=1 MOCK_DOCKER_INFO_EXIT=1 MOCK_DOCKER_ARGV_LOG="${TEST_DIR}/argv.log"
    local c v exitc
    for c in "24.0.7|1" "|1" "abc|1" "v29.1.3|1" "123456.0|1" "29.1.3 29.1.3|0" "29.1.3 24.0.7|0"; do
        v="${c%%|*}"
        exitc="${c#*|}"
        export MOCK_DOCKER_VERSION="${v}" MOCK_DOCKER_VERSION_EXIT="${exitc}"
        : > "${MOCK_DOCKER_ARGV_LOG}"
        run bash -c 'bash "'"${REPO_ROOT}"'/scripts/host/backup_daaf.sh" < /dev/null 2>&1 | tail -n 2; exit "${PIPESTATUS[0]}"'
        echo "case version=[${v}] exit=${exitc}"
        assert_failure 1
        # The line before the ERROR is the banner's blank line: nothing else was printed.
        assert_output "$(printf '%s\n' '' 'ERROR: Docker Desktop does not seem to be running. Please start it and try again.')"
        refute_output --partial "If Docker is running"
        run mock_docker_argv_show "${MOCK_DOCKER_ARGV_LOG}"
        assert_output "$(printf '%s\n' '[info]' '[version] [--format] [{{.Client.Version}} {{.Server.Version}}]')"
    done
}

@test "F1 image (backup): present -> inspected by the pinned name after the volume check, never pulled; missing -> pulled before the scan, then the backup completes" {
    _f1_backup_clean_env
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    refute_output --partial "Downloading the small helper image"
    run bash -c "mock_docker_argv_show '${MOCK_DOCKER_ARGV_LOG}' | head -n 4"
    [ "${lines[0]}" = '[info]' ]
    [ "${lines[1]}" = '[version] [--format] [{{.Client.Version}} {{.Server.Version}}]' ]
    # The volume name follows the compose project name (DAAF_PROJECT_NAME / the repo's
    # docker-compose.yml), so only its shape is pinned here.
    [[ "${lines[2]}" =~ ^\[volume\]\ \[inspect\]\ \[[^\ ]+daaf-data\]$ ]]
    [ "${lines[3]}" = "[image] [inspect] [${DAAF_BUSYBOX_PIN}]" ]
    run grep -c '^pull' "${MOCK_DOCKER_ARGV_LOG}"
    assert_output "0"

    rm -rf "${TEST_DIR:?}"/*_daaf_backup
    _f1_backup_clean_env
    export MOCK_DOCKER_IMAGE_INSPECT_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "$(printf '%s\n' \
        'Downloading the small helper image busybox that the backup needs...' \
        '1.37.0: Pulling from library/busybox' \
        "Status: Downloaded newer image for ${DAAF_BUSYBOX_PIN}")"
    assert_output --partial "Backup complete!"
    # The pull is the 5th call; every `run` (scan, staging, manifest) comes after it.
    run bash -c "mock_docker_argv_show '${MOCK_DOCKER_ARGV_LOG}' | grep -n -e '^\[pull\]' -e '^\[run\]' | head -n 2"
    [ "${lines[0]}" = "5:[pull] [${DAAF_BUSYBOX_PIN}]" ]
    [[ "${lines[1]}" == *":[run] "* ]]
    run grep -c '^pull' "${MOCK_DOCKER_ARGV_LOG}"
    assert_output "1"
}

@test "F1 image (backup): a failed pull refuses, exit 1, with Docker's last line and 'Nothing was changed.'; no folder, no scan, no container" {
    local said
    _f1_backup_clean_env
    export MOCK_DOCKER_IMAGE_INSPECT_EXIT=1 MOCK_DOCKER_PULL_EXIT=1
    export MOCK_DOCKER_PULL_STDERR=$'Using default tag: noise\n  Error response from daemon: Get "https://registry-1.docker.io/v2/": net/http: TLS handshake timeout  \n\n'
    said='Error response from daemon: Get "https://registry-1.docker.io/v2/": net/http: TLS handshake timeout'
    run bash -c 'bash "'"${REPO_ROOT}"'/scripts/host/backup_daaf.sh" 2>&1 > /dev/null'
    assert_failure 1
    assert_output "$(printf '%s\n' '' \
        'ERROR: The backup needs the small helper image busybox and could not download it.' \
        '       Check the internet connection and that Docker Desktop is running, then run the backup again.' \
        "       Docker said: ${said}" \
        '       Nothing was changed.')"
    # Exactly five calls, ending with the failed pull (volume name: see the test above).
    run mock_docker_argv_show "${MOCK_DOCKER_ARGV_LOG}"
    [ "${#lines[@]}" -eq 5 ]
    [ "${lines[0]}" = '[info]' ]
    [ "${lines[1]}" = '[version] [--format] [{{.Client.Version}} {{.Server.Version}}]' ]
    [[ "${lines[2]}" =~ ^\[volume\]\ \[inspect\]\ \[[^\ ]+daaf-data\]$ ]]
    [ "${lines[3]}" = "[image] [inspect] [${DAAF_BUSYBOX_PIN}]" ]
    [ "${lines[4]}" = "[pull] [${DAAF_BUSYBOX_PIN}]" ]
    _f1_no_backup_folder
    # Nothing on Docker's stderr: no "Docker said:" line.
    _f1_backup_clean_env
    export MOCK_DOCKER_PULL_STDERR=""
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure 1
    assert_output --partial "$(printf '%s\n' \
        'Downloading the small helper image busybox that the backup needs...' '' \
        'ERROR: The backup needs the small helper image busybox and could not download it.' \
        '       Check the internet connection and that Docker Desktop is running, then run the backup again.' \
        '       Nothing was changed.')"
    refute_output --partial "Docker said:"
    refute_output --partial "Scanning Docker volume"
    _f1_no_backup_folder
}

@test "F1 pin (backup): every docker run image argument is the pinned busybox digest, never a bare busybox (full backup with Claude state)" {
    _f1_backup_clean_env
    export MOCK_DOCKER_IMAGE_INSPECT_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    assert_output --partial "Backup complete!"
    run mock_docker_argv_images "${MOCK_DOCKER_ARGV_LOG}"
    echo "run calls: ${#lines[@]}"
    # Scan, data staging, Claude staging, executable-permission manifest.
    [ "${#lines[@]}" -ge 4 ]
    run bash -c "mock_docker_argv_images '${MOCK_DOCKER_ARGV_LOG}' | grep -vxF -- '${DAAF_BUSYBOX_PIN}'"
    assert_output ""
    run awk -F '\037' -v pin="${DAAF_BUSYBOX_PIN}" '{ for (i = 1; i < NF; i++) if ($i ~ /^busybox([:@]|$)/ && $i != pin) print }' "${MOCK_DOCKER_ARGV_LOG}"
    assert_output ""
    # Both staging launches really ran (data + Claude), so all four run sites were hit.
    run grep -c "^run"$'\037'"-d"$'\037' "${MOCK_DOCKER_ARGV_LOG}"
    assert_output "2"
    run grep -c "^pull"$'\037'"${DAAF_BUSYBOX_PIN}"$'\037'"\$" "${MOCK_DOCKER_ARGV_LOG}"
    assert_output "1"
}
