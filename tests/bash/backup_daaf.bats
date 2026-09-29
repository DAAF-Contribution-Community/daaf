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

teardown() {
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
# FIFO -- under the 1% (718) count tolerance, so the count check alone would not
# flag it. The staging program must
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
    # It is the program's LAST line, directly after the symlink strip.
    run _extract_stage_program
    assert_success
    [ "${lines[${#lines[@]}-1]}" = 'find /staging \( -type p -o -type s -o -type b -o -type c \) -exec rm -f {} +' ]
    [ "${lines[${#lines[@]}-2]}" = 'find /staging -type l -exec rm -f {} +' ]
}

@test "backup_daaf.sh scan counts special files as an appended 5th line" {
    # The count is appended AFTER the four existing scan values so their line-index
    # parsing contract is unchanged, and it uses the same four types the strip deletes.
    run grep -cF '&& find /source \( -type p -o -type s -o -type b -o -type c \) | wc -l' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output "1"
    run grep -cF "SPECIAL_FILES=\$(echo \"\${SCAN_OUTPUT}\" | sed -n '5p'" "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output "1"
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
                    touch "${dest_dir}/file1" "${dest_dir}/file2"
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
    assert_output --partial "Backup complete!"
    refute_output --partial "WITH WARNINGS"
}

@test "backup: volume scan outputs unexpected format triggers error" {
    export DAAF_NESTED=1
    MOCK_DOCKER_VOLUME_EXIT=0

    # Custom docker mock: scan returns garbage output
    docker() {
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
    # "claude-config" substring in the volume mount argument.
    docker() {
        printf '%s\n' "$*" >> "${TEST_DIR}/docker_calls.log"
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                if [ "${2:-}" = "-d" ]; then
                    if printf '%s' "$*" | grep -q 'claude-config'; then
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
