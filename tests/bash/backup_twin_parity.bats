#!/usr/bin/env bats
# ============================================================================
# Twin-parity tests for the backup/restore container-side sh programs.
# ============================================================================
# WHY THIS FILE EXISTS
# --------------------
# The backup/restore host scripts embed sh programs that MUST stay logically
# identical across their .sh / .ps1 twins:
#
#   1. backup STAGE_PROGRAM  -- strips symlinks from a volume snapshot and writes
#      the .daaf-symlinks manifest, then deletes special files (named pipes,
#      sockets, device nodes; no manifest). In backup_daaf.sh it is a single-quoted
#      `STAGE_PROGRAM='...'` var with a `'"${SYMLINKS_MANIFEST}"'` splice; in
#      backup_daaf.ps1 it is a single-quoted `$StageProgram = @'...'@` here-string
#      that hardcodes `.daaf-symlinks`. The two RESOLVED forms are byte-identical.
#
#   2. restore SYMLINK_REPLAY -- recreates the stripped symlinks from the manifest.
#      In restore_from_backup.sh it is inlined at TWO volume-bound call sites as a
#      multi-line `busybox sh -c '...'` block (with the same manifest splice); in
#      restore_from_backup.ps1 it is ONE `$symlinkReplayScript = "..."` variable
#      (backtick-escaped `$, `; `-joined single line) reused at TWO call sites.
#      The two forms are the same command STREAM (identical after treating `;` and
#      newline as equivalent statement separators).
#
# A real twin-parity break -- a missing Claude-volume replay call in the .ps1 --
# once slipped past the text-presence (grep) tests in backup_daaf.bats /
# restore_from_backup.bats and was caught only by adversarial review. Engineers
# then rebuilt extract-and-diff verification as throwaway scratch THREE times.
# This file promotes that extraction into a permanent gate: twin drift is now a
# TEST FAILURE, not a review lottery.
#
# WHY BATS-ONLY (not also Pester): bash can read BOTH the .sh and .ps1 source
# files as plain text, so a single bats file verifies the whole cross-twin
# contract without duplicating the extraction logic in PowerShell. Pester would
# add a second, drift-prone copy of the same parsing for no additional coverage.
#
# ROBUSTNESS: programs are located by their delimiters/anchors (assignment
# markers, here-string fences, `busybox sh -c '` openers), never by hardcoded
# line numbers -- so the tests survive line drift in the host scripts.
#
# KNOWN FRAGILITY (deliberate trade-off): the extraction resolves the manifest
# splice by matching the literal `'"${SYMLINKS_MANIFEST}"'` token. Renaming that
# variable, inlining `.daaf-symlinks` directly in the .sh, or reformatting the
# splice quoting will surface here as a confusing TWIN DRIFT failure rather than
# a clean "anchor moved" message -- if you make such an edit, update the
# extraction in this file in the same change.
# ============================================================================

load 'test_helper'

setup() { common_setup; }
# Re-open any chmod-000 fixture folder (the read-error tests below) before the shared
# teardown's `rm -rf`, which cannot descend into an unreadable folder -- this runs on
# pass AND on failure, so no fixture outlives its test.
teardown() {
    chmod -R u+rwx "${TEST_DIR}" 2>/dev/null || true
    common_teardown
}

BACKUP_SH="scripts/host/backup_daaf.sh"
BACKUP_PS1="scripts/host/backup_daaf.ps1"
RESTORE_SH="scripts/host/restore_from_backup.sh"
RESTORE_PS1="scripts/host/restore_from_backup.ps1"

# ---------------------------------------------------------------------------
# Extraction helpers (self-contained; no dependency on scripts/scratch/).
# All awk bodies avoid literal single quotes (use \047) so they survive bash
# single-quoting. The manifest splice literal is '"${SYMLINKS_MANIFEST}"' with
# REAL single quotes -- resolved via a "..."-quoted sed (sed does not interpret
# \047), where the .sh script's own SYMLINKS_MANIFEST value is substituted in.
# ---------------------------------------------------------------------------

# Read the SYMLINKS_MANIFEST=".daaf-symlinks" value from a .sh script's text.
_manifest_value() {
    sed -n 's/^SYMLINKS_MANIFEST="\([^"]*\)".*/\1/p' "$1" | head -1
}

# backup STAGE_PROGRAM from backup_daaf.sh (splice resolved, closing quote stripped)
extract_backup_sh() {
    local f="$1" m
    m="$(_manifest_value "${f}")"
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

# backup $StageProgram here-string body from backup_daaf.ps1
extract_backup_ps1() {
    awk '
        BEGIN { inp=0 }
        inp==0 && /\$StageProgram *= *@\047$/ { inp=1; next }
        inp==1 && /^\047@$/ { exit }
        inp==1 { print $0 }
    ' "$1"
}

# restore SYMLINK_REPLAY from restore_from_backup.sh (first replay call site).
# The replay block is the `busybox sh -c '` whose first body line is `set -ef`
# (distinguishing it from the `set -e` permissions replay and the `rm -rf` clear).
# Terminator: the trimmed line that STARTS with a single quote (i.e. `'; then`).
extract_restore_sh() {
    local f="$1" m
    m="$(_manifest_value "${f}")"
    sed "s|/dest/'\"\${SYMLINKS_MANIFEST}\"'|/dest/${m}|g" "${f}" \
    | awk '
        BEGIN { inp=0; started=0 }
        inp==0 && /busybox sh -c \047$/ { inp=1; started=0; next }
        inp==1 {
            body=$0; sub(/^[[:space:]]+/, "", body)
            if (started==0) {
                if (body == "set -ef") { started=1 } else { inp=0; next }
            }
            if (body ~ /^\047/) { exit }
            print body
        }
    '
}

# restore $symlinkReplayScript from restore_from_backup.ps1 (backtick-$ unescaped,
# manifest interpolation resolved). Left in its native '; '-joined single-line form;
# canonicalization (below) reconciles that against the .sh multi-line form.
extract_restore_ps1() {
    local f="$1" m
    m="$(sed -n 's/^\$SymlinksManifest *= *"\([^"]*\)".*/\1/p' "${f}" | head -1)"
    [ -z "${m}" ] && m=".daaf-symlinks"
    sed -n 's/^\$symlinkReplayScript *= *"\(.*\)"$/\1/p' "${f}" \
    | sed 's/`\$/\$/g' \
    | sed "s/\$SymlinksManifest/${m}/g"
}

# Canonical statement stream: treat ';' and newline as EQUIVALENT separators,
# collapse whitespace runs, trim. Proves two programs are the same command stream
# irrespective of multi-line vs '; '-joined layout.
# ASSUMES: no ';' occurs inside a quoted literal anywhere in the replay stream --
# true by construction today (the only quoted literals are octal printf format
# strings; manifest data flows through variables, never source literals). If a
# literal path or ;-bearing string is ever inlined, this mapping could mask a
# real divergence -- revisit the canonicalization then.
canon() { tr ';\n' '  ' | sed 's/[[:space:]]\{1,\}/ /g; s/^ //; s/ $//'; }

# Count double-quote characters in a stream (must be 0 for Windows PS 5.1 parity).
dquote_count() { tr -cd '"' | wc -c | tr -d '[:space:]'; }

# ===========================================================================
# 1. BACKUP STAGE_PROGRAM: byte-identical across twins
# ===========================================================================

@test "twin-parity: backup STAGE_PROGRAM is byte-identical (.sh resolved == .ps1 here-string)" {
    extract_backup_sh  "${REPO_ROOT}/${BACKUP_SH}"  > "${TEST_DIR}/b_sh.txt"
    extract_backup_ps1 "${REPO_ROOT}/${BACKUP_PS1}" > "${TEST_DIR}/b_ps1.txt"

    # Both must be non-empty (extraction anchors matched).
    [ -s "${TEST_DIR}/b_sh.txt" ] || { echo "FAIL: backup .sh STAGE_PROGRAM extraction empty -- anchor STAGE_PROGRAM=' not found"; return 1; }
    [ -s "${TEST_DIR}/b_ps1.txt" ] || { echo "FAIL: backup .ps1 \$StageProgram here-string extraction empty -- anchor @' not found"; return 1; }

    run diff "${TEST_DIR}/b_sh.txt" "${TEST_DIR}/b_ps1.txt"
    if [ "${status}" -ne 0 ]; then
        echo "TWIN DRIFT: backup STAGE_PROGRAM differs between backup_daaf.sh and backup_daaf.ps1"
        echo "  (< = .sh resolved form, > = .ps1 here-string body)"
        echo "${output}"
    fi
    assert_success
}

@test "twin-parity: backup STAGE_PROGRAM contains zero double-quote chars (both twins)" {
    extract_backup_sh  "${REPO_ROOT}/${BACKUP_SH}"  > "${TEST_DIR}/b_sh.txt"
    extract_backup_ps1 "${REPO_ROOT}/${BACKUP_PS1}" > "${TEST_DIR}/b_ps1.txt"

    local n_sh n_ps1
    n_sh="$(dquote_count < "${TEST_DIR}/b_sh.txt")"
    n_ps1="$(dquote_count < "${TEST_DIR}/b_ps1.txt")"
    [ "${n_sh}" -eq 0 ] || { echo "FAIL: backup .sh STAGE_PROGRAM has ${n_sh} double-quote(s) -- corrupts Windows PS 5.1 arg parsing"; return 1; }
    [ "${n_ps1}" -eq 0 ] || { echo "FAIL: backup .ps1 \$StageProgram has ${n_ps1} double-quote(s) -- corrupts Windows PS 5.1 arg parsing"; return 1; }
}

# ===========================================================================
# 2. RESTORE SYMLINK_REPLAY: same command stream across twins
# ===========================================================================

@test "twin-parity: restore SYMLINK_REPLAY is the same command stream (.sh multi-line == .ps1 joined)" {
    extract_restore_sh  "${REPO_ROOT}/${RESTORE_SH}"  | canon > "${TEST_DIR}/r_sh.txt"
    extract_restore_ps1 "${REPO_ROOT}/${RESTORE_PS1}" | canon > "${TEST_DIR}/r_ps1.txt"

    [ -s "${TEST_DIR}/r_sh.txt" ] || { echo "FAIL: restore .sh replay extraction empty -- 'busybox sh -c' + 'set -ef' block not found"; return 1; }
    [ -s "${TEST_DIR}/r_ps1.txt" ] || { echo "FAIL: restore .ps1 \$symlinkReplayScript extraction empty -- assignment not found"; return 1; }

    run diff "${TEST_DIR}/r_sh.txt" "${TEST_DIR}/r_ps1.txt"
    if [ "${status}" -ne 0 ]; then
        echo "TWIN DRIFT: restore SYMLINK_REPLAY differs between restore_from_backup.sh and restore_from_backup.ps1"
        echo "  (canonical form: ';' and newline treated as equivalent separators)"
        echo "  (< = .sh inlined replay, > = .ps1 \$symlinkReplayScript)"
        echo "${output}"
    fi
    assert_success
}

@test "twin-parity: restore SYMLINK_REPLAY contains zero double-quote chars (both twins)" {
    extract_restore_sh  "${REPO_ROOT}/${RESTORE_SH}"  > "${TEST_DIR}/r_sh.txt"
    extract_restore_ps1 "${REPO_ROOT}/${RESTORE_PS1}" > "${TEST_DIR}/r_ps1.txt"

    local n_sh n_ps1
    n_sh="$(dquote_count < "${TEST_DIR}/r_sh.txt")"
    n_ps1="$(dquote_count < "${TEST_DIR}/r_ps1.txt")"
    [ "${n_sh}" -eq 0 ] || { echo "FAIL: restore .sh replay has ${n_sh} double-quote(s) -- corrupts Windows PS 5.1 arg parsing"; return 1; }
    [ "${n_ps1}" -eq 0 ] || { echo "FAIL: restore .ps1 replay has ${n_ps1} double-quote(s) -- corrupts Windows PS 5.1 arg parsing"; return 1; }
}

# ===========================================================================
# 3. RESTORE SYMLINK_REPLAY: invoked at exactly 2 volume-bound call sites / twin
# ===========================================================================
# This is the assertion that would have caught the historical break (a missing
# Claude-volume replay call in the .ps1). Each twin must invoke the replay against
# BOTH the data volume AND the Claude state volume.

@test "twin-parity: restore .sh invokes the replay at exactly 2 volume-bound call sites" {
    # A replay call site is a `busybox sh -c '` block whose first body line is
    # `set -ef` (the replay marker) -- distinct from the `set -e` permissions
    # replay and the `rm -rf` volume-clear blocks. Count via a 1-line lookahead.
    local n
    n="$(grep -A1 "busybox sh -c '\$" "${REPO_ROOT}/${RESTORE_SH}" | grep -c 'set -ef')"
    [ "${n}" -eq 2 ] || { echo "FAIL: restore_from_backup.sh has ${n} symlink-replay call sites, expected 2 (data volume + Claude volume). A missing Claude-volume replay is the historical twin-parity break."; return 1; }
}

@test "twin-parity: restore .ps1 invokes \$symlinkReplayScript at exactly 2 call sites" {
    local n
    n="$(grep -c 'sh -c \$symlinkReplayScript' "${REPO_ROOT}/${RESTORE_PS1}")"
    [ "${n}" -eq 2 ] || { echo "FAIL: restore_from_backup.ps1 invokes \$symlinkReplayScript ${n} time(s), expected 2 (data volume + Claude volume). A missing Claude-volume replay is the historical twin-parity break."; return 1; }
}

@test "twin-parity: each restore .sh replay site binds a distinct volume (data + Claude)" {
    # The two `set -ef` replay sites must mount ${VOLUME_NAME} and
    # ${CLAUDE_VOLUME_NAME} respectively -- proving both volumes get their
    # symlinks replayed, not the same volume twice.
    local data_sites claude_sites
    data_sites="$(grep -A1 '"${VOLUME_NAME}:/dest" busybox sh -c '"'"'$' "${REPO_ROOT}/${RESTORE_SH}" | grep -c 'set -ef')"
    claude_sites="$(grep -A1 '"${CLAUDE_VOLUME_NAME}:/dest" busybox sh -c '"'"'$' "${REPO_ROOT}/${RESTORE_SH}" | grep -c 'set -ef')"
    [ "${data_sites}" -eq 1 ] || { echo "FAIL: expected exactly 1 data-volume (\${VOLUME_NAME}) replay site, found ${data_sites}"; return 1; }
    [ "${claude_sites}" -eq 1 ] || { echo "FAIL: expected exactly 1 Claude-volume (\${CLAUDE_VOLUME_NAME}) replay site, found ${claude_sites}"; return 1; }
}

# ===========================================================================
# 4. SELF-TEST: the extraction+diff logic actually DETECTS drift
# ===========================================================================
# A parity test that cannot fail is worthless. Build a synthetic diverged .ps1
# here-string fixture (a one-token perturbation of the real .ps1) IN THE TEST
# TEMP DIR and confirm the extractor+diff flags it. The real host scripts are
# never modified.

@test "twin-parity SELF-TEST: extractor+diff flags a perturbed backup twin" {
    # Copy the real .ps1 into the temp dir and perturb ONE line of its
    # StageProgram here-string body.
    cp "${REPO_ROOT}/${BACKUP_PS1}" "${TEST_DIR}/perturbed.ps1"
    # Append an INJECTED_DRIFT token to the strip line. Use @ as the sed delimiter
    # (the payload has no @) and add the token as a trailing argument, not a shell
    # comment, so no '#' appears in the sed expression.
    sed -i 's@^find /staging -type l -exec rm -f {} +$@find /staging -type l INJECTED_DRIFT -exec rm -f {} +@' "${TEST_DIR}/perturbed.ps1"

    extract_backup_sh  "${REPO_ROOT}/${BACKUP_SH}" > "${TEST_DIR}/ref_sh.txt"
    extract_backup_ps1 "${TEST_DIR}/perturbed.ps1" > "${TEST_DIR}/drift_ps1.txt"

    # The perturbation must actually have landed (guards against the anchor
    # silently not matching, which would make this self-test vacuous).
    run grep -c 'INJECTED_DRIFT' "${TEST_DIR}/drift_ps1.txt"
    assert_output "1"

    # The diff MUST now report a difference (nonzero status).
    run diff "${TEST_DIR}/ref_sh.txt" "${TEST_DIR}/drift_ps1.txt"
    assert_failure
}

@test "twin-parity SELF-TEST: extractor+diff flags a perturbed restore twin" {
    # Perturb the .ps1 $symlinkReplayScript (add a token to the chown), confirm
    # the canonical-stream comparison flags it.
    cp "${REPO_ROOT}/${RESTORE_PS1}" "${TEST_DIR}/perturbed_restore.ps1"
    sed -i 's#chown -h 1000:1000 /dest/`\$p;#chown -h 1000:1000 -v /dest/`$p;#' "${TEST_DIR}/perturbed_restore.ps1"

    extract_restore_sh  "${REPO_ROOT}/${RESTORE_SH}"      | canon > "${TEST_DIR}/ref_r_sh.txt"
    extract_restore_ps1 "${TEST_DIR}/perturbed_restore.ps1" | canon > "${TEST_DIR}/drift_r_ps1.txt"

    # Confirm the perturbation landed.
    run grep -c 'chown -h 1000:1000 -v' "${TEST_DIR}/drift_r_ps1.txt"
    assert_output "1"

    run diff "${TEST_DIR}/ref_r_sh.txt" "${TEST_DIR}/drift_r_ps1.txt"
    assert_failure
}

# ===========================================================================
# 5. HOST-SIDE LAUNCH-FAILURE REAP: both twins reap a captured staging CID
# ===========================================================================
# A `docker run -d` can fail AFTER creating the container (Created/Exited) while
# still printing its CID. Both twins must reap that captured CID on a launch
# failure rather than leaking a helper container. This is a host-side control-flow
# parity concern the container-program diffs above do not cover -- the historical
# gap where the .ps1 already reaped but the .sh did not.

@test "twin-parity: both backup twins reap the captured MAIN staging CID on a launch failure" {
    # .sh main launch: the `if ! STAGE_CID="$(docker run -d ...)"` error branch reaps
    # the captured CID before `exit 1` (also used by the traps -- presence suffices).
    run grep -F 'docker rm -f "${STAGE_CID:-}"' "${REPO_ROOT}/${BACKUP_SH}"
    assert_success
    # .ps1 main launch: the stage-start guard reaps $StageCid when the launch failed.
    run grep -F 'docker rm -f $StageCid' "${REPO_ROOT}/${BACKUP_PS1}"
    assert_success
}

@test "twin-parity: both backup twins preserve + reap the CLAUDE staging CID (no blanking)" {
    # .sh: the launch OUTCOME is captured in a separate flag so the CID stays intact
    # for the end-of-block reap. The old `|| CLAUDE_STAGE_CID=""` blanked the CID
    # before any cleanup could run and MUST be gone.
    run grep -F 'CLAUDE_STAGE_START_OK=1' "${REPO_ROOT}/${BACKUP_SH}"
    assert_success
    run grep -F 'docker rm -f "${CLAUDE_STAGE_CID}"' "${REPO_ROOT}/${BACKUP_SH}"
    assert_success
    # The fixed launch uses an `if CLAUDE_STAGE_CID="$(docker run -d ...)"` guard. The
    # buggy version was a `CLAUDE_STAGE_CID="$(...)" || CLAUDE_STAGE_CID=""` one-liner
    # with NO leading `if ` -- so this positive assertion discriminates fix from bug.
    # (A negative grep for the old `|| CLAUDE_STAGE_CID=""` idiom would false-match the
    # explanatory comment that documents the historical pattern.)
    run grep -F 'if CLAUDE_STAGE_CID="$(docker run -d' "${REPO_ROOT}/${BACKUP_SH}"
    assert_success
    # .ps1: the finally block reaps $ClaudeStageCid on every exit path.
    run grep -F 'docker rm -f $ClaudeStageCid' "${REPO_ROOT}/${BACKUP_PS1}"
    assert_success
}

# ===========================================================================
# 6. RESTORE-PAIR LAUNCH-FAILURE REAP: both twins reap a captured create CID
# ===========================================================================
# Same host-side control-flow parity concern as section 5, applied to the restore
# pair's `docker create` helper-container guards. `docker create` is single-phase
# so a fail-with-CID is near-theoretical, but the .ps1 twin already reaps the CID in
# a try/finally at BOTH volumes, so the .sh must match: reap the captured CID on a
# create failure rather than leaking a helper container. These are source-anchor
# pins (fix-specific, comment-safe positive anchors), complementing the behavioral
# reap tests in restore_from_backup.bats.

@test "twin-parity: both restore twins reap the captured MAIN helper CID on a create failure" {
    # .sh main guard: the `${CID:-}` reap form must appear EXACTLY twice -- once in
    # the INT/TERM trap and once in the `if ! CID="$(docker create ...)"` error branch
    # (the fix). Pre-fix the trap alone gave a single occurrence, so a bare presence
    # grep would not discriminate; the count of 2 is fix-specific. (The cp-failure and
    # post-copy cleanups use the unguarded `${CID}` form, so they are not counted.)
    local n
    n="$(grep -cF 'docker rm -f "${CID:-}"' "${REPO_ROOT}/${RESTORE_SH}")"
    [ "${n}" -eq 2 ] || { echo "FAIL: restore_from_backup.sh has ${n} \${CID:-} reap sites, expected 2 (INT/TERM trap + create-failure error branch). A missing error-branch reap leaks the helper container."; return 1; }
    # .ps1 main guard: the try/finally reaps $Cid on every exit path (incl. a create
    # that failed after emitting a CID).
    run grep -F 'docker rm -f $Cid' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_success
}

@test "twin-parity: both restore twins preserve + reap the CLAUDE helper CID (no blanking)" {
    # .sh: the create OUTCOME is captured in a separate flag so the CID stays intact
    # for the end-of-block reap. The old `|| CLAUDE_CID=""` blanked the CID before any
    # cleanup could run and MUST be gone.
    run grep -F 'CLAUDE_CREATE_OK=1' "${REPO_ROOT}/${RESTORE_SH}"
    assert_success
    run grep -F 'docker rm -f "${CLAUDE_CID}"' "${REPO_ROOT}/${RESTORE_SH}"
    assert_success
    # The fixed guard uses an `if CLAUDE_CID="$(docker create ...)"` form. The buggy
    # version was a `CLAUDE_CID="$(...)" || CLAUDE_CID=""` one-liner with NO leading
    # `if ` -- so this positive assertion discriminates fix from bug. (A negative grep
    # for the old `|| CLAUDE_CID=""` idiom would false-match the explanatory comment
    # that documents the historical pattern.)
    run grep -F 'if CLAUDE_CID="$(docker create' "${REPO_ROOT}/${RESTORE_SH}"
    assert_success
    # .ps1: the finally block reaps $ClaudeCid on every exit path.
    run grep -F 'docker rm -f $ClaudeCid' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_success
}

# ===========================================================================
# 7. BACKUP-FOLDER COUNT PROGRAM: byte-identical in backup_daaf.ps1 + restore .ps1
# ===========================================================================
# Both Windows scripts count a backup folder CONTAINER-SIDE (busybox through a
# read-only bind mount) with the same $BackupCountProgram here-string: backup to
# verify the copy against the staged snapshot, restore to count the selected backup
# before comparing it with the post-restore volume. PowerShell 5.1 Get-ChildItem
# undercounted long paths in the field (2026-09-29: 72,834 vs 73,021), which is why
# neither script uses it as the authoritative count. The two programs must stay
# identical so the backup report, the restore scan, and the post-restore check agree.
# (The .sh twins count with host `find`, which has no path-length limit, so they
# carry no such program.)

extract_count_ps1() {
    awk '
        BEGIN { inp=0 }
        inp==0 && /\$BackupCountProgram *= *@\047$/ { inp=1; next }
        inp==1 && /^\047@$/ { exit }
        inp==1 { print $0 }
    ' "$1"
}

# Make an extracted container program runnable under the local sh: point its `cd /b`
# at a fixture folder ($2) and relocate its container /tmp/ writes (the count's
# /tmp/count_err) under TEST_DIR, so a test run never writes to the real /tmp.
# Reads the program on stdin. The /tmp/ rewrite runs FIRST, on the program text only:
# TEST_DIR itself may sit under a directory named tmp (a project-scratch TMPDIR).
_localize_count_program() {
    mkdir -p "${TEST_DIR}/ctmp"
    sed -e "s#/tmp/#${TEST_DIR}/ctmp/#g" -e "s#^cd /b\$#cd \"$1\"#"
}

# Count container-absolute /tmp/ paths left in a localized program (must be 0). A
# container path follows a space or `>`; a relocated TEST_DIR path does not.
_container_tmp_refs() { grep -cE '(^|[ >])/tmp/' "$1" || true; }

@test "twin-parity: backup-folder count program is byte-identical (backup .ps1 == restore .ps1)" {
    extract_count_ps1 "${REPO_ROOT}/${BACKUP_PS1}"  > "${TEST_DIR}/c_backup.txt"
    extract_count_ps1 "${REPO_ROOT}/${RESTORE_PS1}" > "${TEST_DIR}/c_restore.txt"
    [ -s "${TEST_DIR}/c_backup.txt" ] || { echo "FAIL: backup .ps1 \$BackupCountProgram extraction empty"; return 1; }
    [ -s "${TEST_DIR}/c_restore.txt" ] || { echo "FAIL: restore .ps1 \$BackupCountProgram extraction empty"; return 1; }
    run diff "${TEST_DIR}/c_backup.txt" "${TEST_DIR}/c_restore.txt"
    if [ "${status}" -ne 0 ]; then
        echo "DRIFT: \$BackupCountProgram differs between backup_daaf.ps1 and restore_from_backup.ps1"
        echo "${output}"
    fi
    assert_success
}

@test "twin-parity: backup-folder count program is quote-free and counts correctly under sh" {
    extract_count_ps1 "${REPO_ROOT}/${BACKUP_PS1}" > "${TEST_DIR}/c.txt"
    [ "$(dquote_count < "${TEST_DIR}/c.txt")" -eq 0 ]
    run grep -c "'" "${TEST_DIR}/c.txt"
    assert_output "0"
    # Run it (local sh + awk here -- dash/mawk in the dev image -- not busybox; same
    # predicates) against a fixture: the root manifests and the Claude subtree are
    # excluded, a NESTED same-name file is data, and a name holding a newline counts
    # ONCE (one `stat` line per file). 1000 + 2000 + 100 + 24 bytes -> 3 KB. The root
    # manifest is visible, so the sentinel reads 1.
    local b="${TEST_DIR}/bk"
    mkdir -p "${b}/sub" "${b}/.daaf-claude-config/deep"
    head -c 1000 /dev/zero > "${b}/a.bin"
    head -c 2000 /dev/zero > "${b}/sub/b.bin"
    head -c 100 /dev/zero > "${b}/sub/.daaf-symlinks"
    head -c 24 /dev/zero > "${b}/sub/name"$'\n'"with-newline"
    : > "${b}/.daaf-symlinks"
    : > "${b}/.daaf-permissions"
    : > "${b}/.daaf-claude-config/deep/c.json"
    _localize_count_program "${b}" < "${TEST_DIR}/c.txt" > "${TEST_DIR}/c_run.sh"
    run _container_tmp_refs "${TEST_DIR}/c_run.sh"
    assert_output "0"
    run sh "${TEST_DIR}/c_run.sh"
    assert_success
    assert_output "$(printf 'BACKUP_FILES=4\nBACKUP_KB=3\nBACKUP_SENTINEL=1')"
}

@test "twin-parity: count program on an EMPTY folder prints 0 counts and BACKUP_SENTINEL=0 (empty bind mount)" {
    # Docker Desktop can present an empty folder for a bind mount of some locations
    # (docker/for-win#14271). The program must still print parseable markers (0, not
    # an empty value) and a 0 sentinel, so the backup routes to its PowerShell
    # fallback instead of reporting "0 files copied".
    extract_count_ps1 "${REPO_ROOT}/${BACKUP_PS1}" > "${TEST_DIR}/c.txt"
    mkdir -p "${TEST_DIR}/empty"
    _localize_count_program "${TEST_DIR}/empty" < "${TEST_DIR}/c.txt" > "${TEST_DIR}/c_run.sh"
    run sh "${TEST_DIR}/c_run.sh"
    assert_success
    assert_output "$(printf 'BACKUP_FILES=0\nBACKUP_KB=0\nBACKUP_SENTINEL=0')"
}

# ===========================================================================
# 7b. READ ERRORS make a count UNAVAILABLE, never a short "exact" count (F1, round 2)
# ===========================================================================
# A pipeline's status is its LAST command's (awk), and busybox's pipefail default is
# unverified, so a `find` read error used to be silent: review round 2 reproduced,
# under dash, a program that printed a short BACKUP_FILES with BACKUP_SENTINEL=1 and
# exit 0 -- which the backup trusted as EXACT (false "missing files", even the fatal
# short-copy branch). Both counts now send the count's stderr to /tmp/count_err and
# print *_COUNT_ERRORS=<n> INSTEAD of the markers when it is non-empty. These run the
# REAL programs under dash (busybox is not installed here; same POSIX constructs)
# against a fixture with a chmod-000 subfolder. Root reads through 000, so skip there.

_run_shell() { if command -v dash > /dev/null 2>&1; then echo dash; else echo sh; fi; }

@test "twin-parity: a find read error makes the backup-folder count UNAVAILABLE (no BACKUP_FILES, exit 0)" {
    [ "$(id -u)" -ne 0 ] || skip "root can read a chmod-000 folder"
    extract_count_ps1 "${REPO_ROOT}/${BACKUP_PS1}" > "${TEST_DIR}/c.txt"
    local b="${TEST_DIR}/bk_err"
    mkdir -p "${b}/locked"
    head -c 10 /dev/zero > "${b}/a.bin"
    head -c 10 /dev/zero > "${b}/locked/hidden.bin"
    : > "${b}/.daaf-symlinks"
    chmod 000 "${b}/locked"
    _localize_count_program "${b}" < "${TEST_DIR}/c.txt" > "${TEST_DIR}/c_run.sh"
    run "$(_run_shell)" "${TEST_DIR}/c_run.sh"
    chmod 755 "${b}/locked"
    assert_success
    assert_output --partial "BACKUP_COUNT_ERRORS=1"
    assert_output --partial "BACKUP_SENTINEL=1"
    refute_output --partial "BACKUP_FILES="
    refute_output --partial "BACKUP_KB="
}

@test "twin-parity: a find read error in the SNAPSHOT count prints STAGED_COUNT_ERRORS and does not fail staging" {
    [ "$(id -u)" -ne 0 ] || skip "root can read a chmod-000 folder"
    # The staging program's count block (from `counts=` to the end), run under
    # `set -e` like the real program: it must exit 0 (an unreadable count must never
    # fail the staging step) and withhold the markers so the backup falls back.
    extract_backup_ps1 "${REPO_ROOT}/${BACKUP_PS1}" > "${TEST_DIR}/stage.txt"
    local t="${TEST_DIR}/stage_err"
    mkdir -p "${t}/locked" "${TEST_DIR}/ctmp"
    printf 'data\n' > "${t}/file.txt"
    printf 'x\n' > "${t}/locked/hidden.txt"
    chmod 000 "${t}/locked"
    { printf 'set -e\ncd "%s"\n' "${t}"; sed -n '/^counts=\$(find /,$p' "${TEST_DIR}/stage.txt" | sed "s#/tmp/#${TEST_DIR}/ctmp/#g"; } \
        > "${TEST_DIR}/stage_run.sh"
    run _container_tmp_refs "${TEST_DIR}/stage_run.sh"
    assert_output "0"
    run "$(_run_shell)" "${TEST_DIR}/stage_run.sh"
    chmod 755 "${t}/locked"
    assert_success
    assert_output --partial "STAGED_COUNT_ERRORS=1"
    refute_output --partial "STAGED_FILES="
    refute_output --partial "STAGED_KB="
}

@test "twin-parity: SELF-TEST -- the same fixture made readable prints exact markers (the error path is what changed)" {
    extract_count_ps1 "${REPO_ROOT}/${BACKUP_PS1}" > "${TEST_DIR}/c.txt"
    local b="${TEST_DIR}/bk_ok"
    mkdir -p "${b}/locked"
    head -c 10 /dev/zero > "${b}/a.bin"
    head -c 10 /dev/zero > "${b}/locked/hidden.bin"
    : > "${b}/.daaf-symlinks"
    _localize_count_program "${b}" < "${TEST_DIR}/c.txt" > "${TEST_DIR}/c_run.sh"
    run "$(_run_shell)" "${TEST_DIR}/c_run.sh"
    assert_success
    assert_output "$(printf 'BACKUP_FILES=2\nBACKUP_KB=0\nBACKUP_SENTINEL=1')"
}

# ===========================================================================
# 8. STAGED COUNT vs BACKUP-FOLDER COUNT: identical predicate (I1, 2026-09-29)
# ===========================================================================
# The zero-tolerance check compares the staging program's STAGED_FILES/STAGED_KB with
# the backup-folder count. If the two `find` predicates exclude different root paths,
# a stray root file on one side only is a FALSE mismatch -- reproduced in review with
# a leftover root .daaf-permissions (restore's failed permission replay leaves one in
# the volume): STAGED_FILES=2 vs BACKUP_FILES=1. Pin the predicates as identical, and
# prove the behavior on exactly that fixture.

# The `counts=$(find ...)` line of a program (the single-pass count).
_counts_line() { grep '^counts=\$(find ' "$1"; }

@test "twin-parity: staged count and backup-folder count use the SAME find predicate and awk" {
    extract_backup_ps1 "${REPO_ROOT}/${BACKUP_PS1}" > "${TEST_DIR}/stage.txt"
    extract_count_ps1  "${REPO_ROOT}/${BACKUP_PS1}" > "${TEST_DIR}/count.txt"
    run _counts_line "${TEST_DIR}/stage.txt"
    assert_success
    local stage_line="${output}"
    run _counts_line "${TEST_DIR}/count.txt"
    assert_success
    [ "${stage_line}" = "${output}" ] || { echo "PREDICATE DRIFT:"; echo " stage: ${stage_line}"; echo " count: ${output}"; return 1; }
    # And it excludes all three root paths, and captures the count's stderr (F1).
    [[ "${stage_line}" == *'! -path ./.daaf-symlinks ! -path ./.daaf-permissions ! -path ./.daaf-claude-config/\*'* ]]
    [[ "${stage_line}" == *'-exec stat -c %s {} + 2>/tmp/count_err | awk '* ]]
    # Both programs withhold their markers when that file is non-empty.
    run grep -cxF 'if test -s /tmp/count_err; then' "${TEST_DIR}/stage.txt"
    assert_output "1"
    run grep -cxF 'if test -s /tmp/count_err; then' "${TEST_DIR}/count.txt"
    assert_output "1"
}

# The [0]/[3] segment of the source scan uses the snapshot count's predicate in BOTH
# backup twins (F5f): otherwise the "Snapshot: N files (M fewer than the scan ...)"
# line misreports a predicate gap (a stray root .daaf-permissions) as live drift.
_SCAN_PRED='find . -type f ! -path ./.daaf-symlinks ! -path ./.daaf-permissions ! -path ./.daaf-claude-config/\* -exec stat -c %s {} +'

@test "twin-parity: the source scan's file/KB count uses the snapshot predicate in both backup twins" {
    local ps_line sh_line stage_pred
    ps_line="$(grep '^\$ScanOutput = docker run' "${REPO_ROOT}/${BACKUP_PS1}")"
    sh_line="$(grep '^SCAN_OUTPUT=\$(docker run' "${REPO_ROOT}/${BACKUP_SH}")"
    [ -n "${ps_line}" ]
    [ -n "${sh_line}" ]
    [[ "${ps_line}" == *"cd /source && c="*"${_SCAN_PRED} | awk "* ]] || { echo "PS1 scan predicate drift: ${ps_line}"; return 1; }
    [[ "${sh_line}" == *"cd /source && c="*"${_SCAN_PRED} | awk "* ]] || { echo "SH scan predicate drift: ${sh_line}"; return 1; }
    # ...and it is the snapshot count's own predicate.
    extract_backup_ps1 "${REPO_ROOT}/${BACKUP_PS1}" > "${TEST_DIR}/stage.txt"
    stage_pred="$(_counts_line "${TEST_DIR}/stage.txt")"
    [[ "${stage_pred}" == *"${_SCAN_PRED} 2>/tmp/count_err"* ]] || { echo "snapshot predicate drift: ${stage_pred}"; return 1; }
}

# The post-restore volume count (F5h) uses the same root exclusions and one-line-per-
# file counting in both restore twins, textually identical.
@test "twin-parity: the post-restore volume count program is identical in both restore twins" {
    local sh_prog ps_prog
    sh_prog="$(sed -n "s/^VERIFY_OUTPUT=\"\$(docker run --rm -v \"\${VOLUME_NAME}:\/dest:ro\" busybox sh -c '\([^']*\)'.*/\1/p" "${REPO_ROOT}/${RESTORE_SH}")"
    ps_prog="$(sed -n "s/^\$VerifyOutput = @(docker run --rm -v \"\${VolumeName}:\/dest:ro\" busybox sh -c '\([^']*\)'.*/\1/p" "${REPO_ROOT}/${RESTORE_PS1}")"
    [ -n "${sh_prog}" ] || { echo "FAIL: restore .sh verify program not found"; return 1; }
    [ "${sh_prog}" = "${ps_prog}" ] || { echo "DRIFT:"; echo " sh:  ${sh_prog}"; echo " ps1: ${ps_prog}"; return 1; }
    [[ "${sh_prog}" == 'set -e; : > /tmp/count_err; n=$(find /dest -type f ! -path /dest/.daaf-symlinks ! -path /dest/.daaf-permissions ! -path /dest/.daaf-claude-config/\* -exec stat -c %s {} + 2>/tmp/count_err | wc -l); if test -s /tmp/count_err; then echo RESTORED_COUNT_ERRORS=$(grep -c ^ /tmp/count_err); else echo RESTORED_FILES=$((n)); fi' ]]
    # Quote-free (Windows PS 5.1 argv) and not ending in a backslash.
    [ "$(printf '%s' "${sh_prog}" | dquote_count)" -eq 0 ]
    [[ "${sh_prog}" != *'\' ]]
    # Behavior under the local sh (relocated /dest and container /tmp/): root manifests +
    # Claude subtree excluded, a nested same-name file counts, a newline name counts once.
    local d="${TEST_DIR}/dest" prog
    mkdir -p "${d}/sub" "${d}/.daaf-claude-config" "${TEST_DIR}/ctmp"
    : > "${d}/a"
    : > "${d}/sub/.daaf-permissions"
    : > "${d}/sub/name"$'\n'"nl"
    : > "${d}/.daaf-symlinks"
    : > "${d}/.daaf-permissions"
    : > "${d}/.daaf-claude-config/c"
    prog="${sh_prog//\/tmp\//${TEST_DIR}/ctmp/}"
    prog="${prog//\/dest/${d}}"
    run "$(_run_shell)" -c "${prog}"
    assert_success
    assert_output "RESTORED_FILES=3"
    # FU2: a read error inside the count makes it UNAVAILABLE (error marker, exit 0),
    # never a short "exact" RESTORED_FILES.
    if [ "$(id -u)" -ne 0 ]; then
        mkdir -p "${d}/locked"
        : > "${d}/locked/hidden"
        chmod 000 "${d}/locked"
        run "$(_run_shell)" -c "${prog}"
        chmod 755 "${d}/locked"
        assert_success
        assert_output "RESTORED_COUNT_ERRORS=1"
    fi
}

@test "twin-parity: a leftover ROOT .daaf-permissions in the volume gives STAGED == BACKUP counts" {
    # Snapshot side: the staging program's count lines, run over a staged tree whose
    # volume content included a stray root .daaf-permissions. Backup side: the count
    # program over the copied folder (same tree + the root manifest).
    extract_backup_ps1 "${REPO_ROOT}/${BACKUP_PS1}" > "${TEST_DIR}/stage.txt"
    extract_count_ps1  "${REPO_ROOT}/${BACKUP_PS1}" > "${TEST_DIR}/count.txt"
    local t="${TEST_DIR}/tree"
    mkdir -p "${t}/sub"
    printf 'data\n' > "${t}/sub/file.txt"
    printf 'scripts/run.sh\n' > "${t}/.daaf-permissions"
    : > "${t}/.daaf-symlinks"
    mkdir -p "${TEST_DIR}/ctmp"
    # The count block runs from `counts=` to the end of the program; its container
    # /tmp/ writes are relocated under TEST_DIR (never the real /tmp).
    { printf 'set -e\ncd "%s"\n' "${t}"; sed -n '/^counts=\$(find /,$p' "${TEST_DIR}/stage.txt" | sed "s#/tmp/#${TEST_DIR}/ctmp/#g"; } \
        > "${TEST_DIR}/stage_run.sh"
    run _container_tmp_refs "${TEST_DIR}/stage_run.sh"
    assert_output "0"
    run sh "${TEST_DIR}/stage_run.sh"
    assert_success
    assert_output "$(printf 'STAGED_FILES=1\nSTAGED_KB=0')"
    _localize_count_program "${t}" < "${TEST_DIR}/count.txt" > "${TEST_DIR}/count_run.sh"
    run sh "${TEST_DIR}/count_run.sh"
    assert_success
    assert_output --partial "BACKUP_FILES=1"
}

# ===========================================================================
# 9. HOST COUNT FUNCTION: _daaf_tree_count is byte-identical in both .sh scripts
# ===========================================================================
# backup_daaf.sh and restore_from_backup.sh each carry _daaf_tree_count (the host
# `find` count whose captured stderr turns a read error into a LOWER BOUND). Restore
# once held a hand-trimmed copy (no mode parameter, no "kb" branch, the two manifest
# `! -path` exclusions in swapped order) under a "Same function as" comment; it is
# now a textually identical copy, and this pin keeps it so. The function is located
# by its exact `_daaf_tree_count() {` opener and the first column-0 `}` after it.

extract_tree_count() {
    awk '
        BEGIN { inf=0 }
        inf==0 && /^_daaf_tree_count\(\) \{$/ { inf=1 }
        inf==1 { print $0 }
        inf==1 && /^\}$/ { exit }
    ' "$1"
}

@test "twin-parity: _daaf_tree_count is byte-identical (backup_daaf.sh == restore_from_backup.sh)" {
    # Exactly one definition per script, so the extraction cannot pick a stale copy.
    run grep -c '^_daaf_tree_count() {$' "${REPO_ROOT}/${BACKUP_SH}"
    assert_output "1"
    run grep -c '^_daaf_tree_count() {$' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    extract_tree_count "${REPO_ROOT}/${BACKUP_SH}"  > "${TEST_DIR}/tc_backup.txt"
    extract_tree_count "${REPO_ROOT}/${RESTORE_SH}" > "${TEST_DIR}/tc_restore.txt"
    # Non-trivial extraction: opener to closer, with both count branches inside.
    [ "$(head -n 1 "${TEST_DIR}/tc_backup.txt")" = '_daaf_tree_count() {' ] || { echo "FAIL: backup opener not extracted"; return 1; }
    [ "$(tail -n 1 "${TEST_DIR}/tc_backup.txt")" = '}' ] || { echo "FAIL: backup closer not extracted"; return 1; }
    grep -q -- '-print0 | LC_ALL=C tr' "${TEST_DIR}/tc_backup.txt" || { echo "FAIL: files branch missing from extraction"; return 1; }
    grep -q -- '-exec ls -ln {} +' "${TEST_DIR}/tc_backup.txt" || { echo "FAIL: kb branch missing from extraction"; return 1; }
    run diff "${TEST_DIR}/tc_backup.txt" "${TEST_DIR}/tc_restore.txt"
    if [ "${status}" -ne 0 ]; then
        echo "DRIFT: _daaf_tree_count differs between backup_daaf.sh and restore_from_backup.sh"
        echo "${output}"
    fi
    assert_success
}

@test "twin-parity: restore_from_backup.sh calls _daaf_tree_count with an explicit mode (set -u safe)" {
    # The shared function reads "$2" under `set -u`; a one-argument call would abort.
    run grep -nE '_daaf_tree_count "[^"]*"[[:space:]]*$' "${REPO_ROOT}/${RESTORE_SH}"
    assert_failure
    run grep -cE '^[[:space:]]*_daaf_tree_count "[^"]*" files$' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "2"
}

@test "twin-parity SELF-TEST: extractor+diff flags a perturbed _daaf_tree_count" {
    # Re-create the historical drift (the two manifest exclusions swapped) in a temp copy.
    sed 's#! -path "./${SYMLINKS_MANIFEST}" ! -path "./${PERMISSIONS_MANIFEST}"#! -path "./${PERMISSIONS_MANIFEST}" ! -path "./${SYMLINKS_MANIFEST}"#' \
        "${REPO_ROOT}/${RESTORE_SH}" > "${TEST_DIR}/restore_drift.sh"
    run cmp -s "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/restore_drift.sh"
    assert_failure
    extract_tree_count "${REPO_ROOT}/${BACKUP_SH}"      > "${TEST_DIR}/ref.txt"
    extract_tree_count "${TEST_DIR}/restore_drift.sh"   > "${TEST_DIR}/drift.txt"
    run diff "${TEST_DIR}/ref.txt" "${TEST_DIR}/drift.txt"
    assert_failure
}

# ===========================================================================
# 10. RESTORE COMPLETION BANNER: same banners, same WARNING set, pinned latches
# ===========================================================================
# Both restore twins latch a WITH WARNINGS completion banner (HAD_WARNINGS /
# $HadWarnings), mirroring the backup twins. The banner strings must be identical,
# and so must the set of WARNING messages the twins can print (first lines, with
# variable references normalized to <v>), so a WARNING added to one twin only
# fails here. The latch assignments are pinned by count: 7 in the .sh, 8 in the
# .ps1, whose extra latch is the LOWER-BOUND scan count (the .sh refuses such a
# backup instead). Adding a success-path WARNING means adding its latch and
# updating these counts (and the .ps1 count in restore_from_backup.Tests.ps1).
# Lines are matched with grep -E + sed (no GNU-only `\|`), so busybox also works.

_restore_banners() {
    grep -E '^[[:space:]]*(echo|Write-Host) "  Restore complete' "$1" \
    | sed 's/^[^"]*"\([^"]*\)".*/\1/'
}

_restore_warning_set() {
    grep -E '^[[:space:]]*(echo|Write-Host) "WARNING: ' "$1" \
    | sed -e 's/^[^"]*"\(WARNING: [^"]*\)".*/\1/' \
          -e 's/\${[A-Za-z_][A-Za-z_0-9]*}/<v>/g' \
          -e 's/\$[A-Za-z_][A-Za-z_0-9]*/<v>/g' \
    | LC_ALL=C sort -u
}

@test "twin-parity: both restore twins print the same completion banners" {
    local expected
    expected="$(printf '%s\n%s' '  Restore completed WITH WARNINGS -- verify before relying on it' '  Restore complete!')"
    run _restore_banners "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "${expected}"
    run _restore_banners "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "${expected}"
    # Same wording pattern as the backup twins' latched banner.
    run grep -cF '"  Backup completed WITH WARNINGS -- verify before relying on it"' "${REPO_ROOT}/${BACKUP_SH}" "${REPO_ROOT}/${BACKUP_PS1}"
    assert_output --partial "backup_daaf.sh:1"
    assert_output --partial "backup_daaf.ps1:1"
}

@test "twin-parity: both restore twins can print the same set of WARNING messages" {
    _restore_warning_set "${REPO_ROOT}/${RESTORE_SH}"  > "${TEST_DIR}/w_sh.txt"
    _restore_warning_set "${REPO_ROOT}/${RESTORE_PS1}" > "${TEST_DIR}/w_ps1.txt"
    # Non-trivial extraction (the two variable-bearing messages normalized alike).
    [ "$(grep -c . "${TEST_DIR}/w_sh.txt")" -ge 8 ] || { echo "FAIL: too few WARNING lines extracted from the .sh"; cat "${TEST_DIR}/w_sh.txt"; return 1; }
    grep -qF 'WARNING: Could not verify the restored file count: Docker hit <v> read error(s)' "${TEST_DIR}/w_sh.txt" || { echo "FAIL: variable normalization did not apply"; return 1; }
    run diff "${TEST_DIR}/w_sh.txt" "${TEST_DIR}/w_ps1.txt"
    if [ "${status}" -ne 0 ]; then
        echo "DRIFT: the restore twins' WARNING messages differ"
        echo "${output}"
    fi
    assert_success
}

@test "twin-parity: restore latch sites are pinned (7 in .sh, 8 in .ps1 incl. the lower-bound scan)" {
    run grep -c '^[[:space:]]*HAD_WARNINGS=0$' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run grep -c '^[[:space:]]*HAD_WARNINGS=1$' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "7"
    run grep -c '^[[:space:]]*\$HadWarnings = \$false$' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "1"
    run grep -c '^[[:space:]]*\$HadWarnings = \$true$' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "8"
    # The .ps1-only latch sits in the lower-bound branch of the scan.
    run grep -A 12 -F '$TotalFilesIsLowerBound = $true' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output --partial '$HadWarnings = $true'
}

@test "twin-parity SELF-TEST: the WARNING-set diff flags a WARNING present in one restore twin only" {
    # Drop one WARNING line from a temp copy of the .ps1; the sets must then differ.
    grep -vF 'WARNING: Could not fully replay Claude state symlinks.' "${REPO_ROOT}/${RESTORE_PS1}" > "${TEST_DIR}/restore_drift.ps1"
    run cmp -s "${REPO_ROOT}/${RESTORE_PS1}" "${TEST_DIR}/restore_drift.ps1"
    assert_failure
    _restore_warning_set "${REPO_ROOT}/${RESTORE_SH}"   > "${TEST_DIR}/w_ref.txt"
    _restore_warning_set "${TEST_DIR}/restore_drift.ps1" > "${TEST_DIR}/w_drift.txt"
    run diff "${TEST_DIR}/w_ref.txt" "${TEST_DIR}/w_drift.txt"
    assert_failure
}

# ===========================================================================
# 11. BUSYBOX: no batched `-exec ... {} +` inside `\( ... \)` in container programs
# ===========================================================================
# busybox `find` runs the FINAL batch of an `-exec ... {} +` only for actions at the
# TOP level of the expression: flush_exec_plus() in findutils/find.c walks the
# top-level OR branches (G.actions) and never descends into a `\( \)` subexpression
# (ACTF(paren) keeps its own ap->subexpr). A batched -exec inside parentheses
# therefore never runs for the last -- usually the only -- batch, silently: Alpine
# aports MR !75008 ("this didn't output anything but should output a":
# `busybox find a \( -exec echo {} + \)`). GNU find flushes it, so the dev image's
# dash + GNU tests cannot see the bug. Review round 7 found exactly this in the
# staging program's case-clash listing (which would have listed nothing on Windows).
# This guard reads the container programs as text: every logical line (backslash
# continuations joined, comment lines skipped) is split on whitespace, `\(` / `\)`
# tokens track depth, and a `{}` `+` token pair at depth > 0 is an offender.
# `-exec ... \;` inside parentheses is fine (not batched) and is not flagged.
# Scope: every scripts/host file that mentions busybox (found by grep, so a new one is
# covered automatically) -- backup, restore, migrate and test_migration, both twins --
# plus the extracted staging programs. Programs that run in the DAAF container itself
# (`docker compose exec ... sh -c`) use GNU find and are out of scope.
# KNOWN BLIND SPOTS (text matching, not a shell parser): a quoted paren (`'('`, `"("`
# or `'\('`), a `\(` / `\)` glued to the next token (`\(-type`), `{}` glued to `+`
# (`{}+`), a program assembled at run time from variables or string pieces, and a
# find command continued onto the next line with PowerShell's backtick (only a
# trailing backslash is joined, so the parts are read as separate lines) are not
# seen. Write container find programs with the separate `\(` ... `\)` and
# `{} +` tokens used throughout these scripts so the guard can read them.

# Print "<file>:<line>: <logical line>" for every offender; empty output = clean.
_exec_plus_in_parens() {
    awk '
        {
            line = $0; start = FNR
            while (line ~ /\\$/ && (getline nxt) > 0) { sub(/\\$/, "", line); line = line " " nxt }
            if (line ~ /^[[:space:]]*#/) next
            n = split(line, tok, /[[:space:]]+/)
            depth = 0; prev = ""
            for (i = 1; i <= n; i++) {
                t = tok[i]
                if (t == "\\(") depth++
                else if (t == "\\)") { if (depth > 0) depth-- }
                else if (depth > 0 && t == "+" && prev == "{}") { print FILENAME ":" start ": " line; break }
                prev = t
            }
        }
    ' "$@"
}

@test "twin-parity: no batched -exec {} + inside \\( \\) in STAGE_PROGRAM or any host script that runs busybox" {
    extract_backup_sh  "${REPO_ROOT}/${BACKUP_SH}"  > "${TEST_DIR}/b_sh.txt"
    extract_backup_ps1 "${REPO_ROOT}/${BACKUP_PS1}" > "${TEST_DIR}/b_ps1.txt"
    # Non-vacuous: the programs hold batched -exec actions and parenthesized groups.
    grep -qF -- '-exec printf %s\\011d\\n {} +' "${TEST_DIR}/b_sh.txt" || { echo "FAIL: case listing not found in the extracted STAGE_PROGRAM"; return 1; }
    grep -qF -- '\( -type p -o -type s -o -type b -o -type c \) -exec rm -f {} +' "${TEST_DIR}/b_sh.txt" || { echo "FAIL: special-file strip not found"; return 1; }
    # Every host script that runs a busybox program (polish 2026-10-01: migrate and
    # test_migration joined backup/restore). The known eight must all be in the list.
    local f busybox_files=()
    while IFS= read -r f; do busybox_files+=("${f}"); done < <(grep -l busybox "${REPO_ROOT}"/scripts/host/*.sh "${REPO_ROOT}"/scripts/host/*.ps1 | LC_ALL=C sort)
    for f in backup_daaf.sh backup_daaf.ps1 restore_from_backup.sh restore_from_backup.ps1 \
        migrate_daaf.sh migrate_daaf.ps1 test_migration.sh test_migration.ps1; do
        printf '%s\n' "${busybox_files[@]}" | grep -qxF "${REPO_ROOT}/scripts/host/${f}" \
            || { echo "FAIL: ${f} not in the busybox scan list"; return 1; }
    done
    run _exec_plus_in_parens "${TEST_DIR}/b_sh.txt" "${TEST_DIR}/b_ps1.txt" "${busybox_files[@]}"
    assert_success
    if [ -n "${output}" ]; then
        echo "BUSYBOX HAZARD: a batched -exec ... {} + inside \\( \\) never runs its last batch under busybox find:"
        echo "${output}"
        return 1
    fi
}

@test "twin-parity SELF-TEST: the busybox guard flags the OLD case-listing construct and the MR !75008 repro" {
    local line old
    line="$(grep -F -- '-exec printf %s\\011d\\n {} +' "${REPO_ROOT}/${BACKUP_SH}")"
    [ -n "${line}" ] || { echo "FAIL: current case-listing line not found"; return 1; }
    # Rebuild the pre-fix line (review round 7): the two branches grouped in \( \).
    old="${line/ -type d / \\( -type d }"
    old="${old/-o ! -path \$C -type f/-o -type f}"
    old="${old/ | sort/ \\) | sort}"
    [ "${old}" = 'find . -mindepth 1 ! -path $C \( -type d -exec printf %s\\011d\\n {} + -o -type f -exec printf %s\\011f\\n {} + \) | sort > /tmp/case_sorted' ] \
        || { echo "FAIL: could not rebuild the old construct:"; echo "${old}"; return 1; }
    # Mutate a copy of the real script back to the old line: the guard must fail on it.
    TGT="${line}" NEW="${old}" awk '$0 == ENVIRON["TGT"] { print ENVIRON["NEW"]; next } { print }' \
        "${REPO_ROOT}/${BACKUP_SH}" > "${TEST_DIR}/backup_mutant.sh"
    run cmp -s "${REPO_ROOT}/${BACKUP_SH}" "${TEST_DIR}/backup_mutant.sh"
    assert_failure
    run _exec_plus_in_parens "${TEST_DIR}/backup_mutant.sh"
    assert_output --partial 'backup_mutant.sh:'
    assert_output --partial '\( -type d -exec printf'
    [ "${#lines[@]}" -eq 1 ]
    # The upstream repro, one spread over a continuation, and the clean shapes.
    printf '%s\n' 'find a \( -exec echo {} + \)' \
        'find . \( -name x -o \' '-name y -exec rm {} + \)' \
        'find /staging \( -type p -o -type c \) -exec rm -f {} +' \
        'find . \( -type l -exec readlink {} \; \)' \
        '# comment: find a \( -exec echo {} + \)' > "${TEST_DIR}/shapes.txt"
    run _exec_plus_in_parens "${TEST_DIR}/shapes.txt"
    [ "${#lines[@]}" -eq 2 ] || { echo "expected exactly 2 offenders, got:"; echo "${output}"; return 1; }
    [[ "${lines[0]}" == *'shapes.txt:1: find a \( -exec echo {} + \)' ]]
    [[ "${lines[1]}" == *'shapes.txt:2: find . \( -name x -o  -name y -exec rm {} + \)' ]]
}
