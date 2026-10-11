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
#      multi-line `"${BUSYBOX_IMAGE}" sh -c '...'` block (with the same manifest splice); in
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
# markers, here-string fences, `"${BUSYBOX_IMAGE}" sh -c '` openers), never by hardcoded
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
# The replay block is the `"${BUSYBOX_IMAGE}" sh -c '` (the pinned helper image, fix
# pass #26; it was a bare `busybox` before) whose first body line is `set -ef`
# (distinguishing it from the `set -e` permissions replay and the `rm -rf` clear).
# Terminator: the trimmed line that STARTS with a single quote (i.e. `'; then`).
extract_restore_sh() {
    local f="$1" m
    m="$(_manifest_value "${f}")"
    sed "s|/dest/'\"\${SYMLINKS_MANIFEST}\"'|/dest/${m}|g" "${f}" \
    | awk '
        BEGIN { inp=0; started=0 }
        inp==0 && /"[$][{]BUSYBOX_IMAGE[}]" sh -c \047$/ { inp=1; started=0; next }
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

    [ -s "${TEST_DIR}/r_sh.txt" ] || { echo "FAIL: restore .sh replay extraction empty -- '\"\${BUSYBOX_IMAGE}\" sh -c' + 'set -ef' block not found"; return 1; }
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
    # A replay call site is a `"${BUSYBOX_IMAGE}" sh -c '` block whose first body line
    # is `set -ef` (the replay marker) -- distinct from the `set -e` permissions
    # replay and the `rm -rf` volume-clear blocks. Count via a 1-line lookahead.
    local n
    n="$(grep -A1 '"[$]{BUSYBOX_IMAGE}" sh -c '"'"'$' "${REPO_ROOT}/${RESTORE_SH}" | grep -c 'set -ef')"
    [ "${n}" -eq 2 ] || { echo "FAIL: restore_from_backup.sh has ${n} symlink-replay call sites, expected 2 (data volume + Claude volume). A missing Claude-volume replay is the historical twin-parity break."; return 1; }
}

@test "twin-parity: restore .ps1 invokes \$symlinkReplayScript at exactly 2 call sites" {
    local n
    n="$(grep -c 'sh -c \$symlinkReplayScript' "${REPO_ROOT}/${RESTORE_PS1}")"
    [ "${n}" -eq 2 ] || { echo "FAIL: restore_from_backup.ps1 invokes \$symlinkReplayScript ${n} time(s), expected 2 (data volume + Claude volume). A missing Claude-volume replay is the historical twin-parity break."; return 1; }
}

@test "twin-parity: each restore .sh replay site binds a distinct volume (data + Claude)" {
    # The two `set -ef` replay sites must mount ${TEMP_VOLUME_NAME} and
    # ${CLAUDE_TEMP_VOLUME_NAME} respectively -- proving both volumes get their
    # symlinks replayed, not the same volume twice. Copy-then-swap (2026-10-01): the
    # replays run on the TEMPORARY copies, before the swap, so they bind the temp names.
    local data_sites claude_sites
    data_sites="$(grep -A1 '"${TEMP_VOLUME_NAME}:/dest" "[$]{BUSYBOX_IMAGE}" sh -c '"'"'$' "${REPO_ROOT}/${RESTORE_SH}" | grep -c 'set -ef')"
    claude_sites="$(grep -A1 '"${CLAUDE_TEMP_VOLUME_NAME}:/dest" "[$]{BUSYBOX_IMAGE}" sh -c '"'"'$' "${REPO_ROOT}/${RESTORE_SH}" | grep -c 'set -ef')"
    [ "${data_sites}" -eq 1 ] || { echo "FAIL: expected exactly 1 data-volume (\${TEMP_VOLUME_NAME}) replay site, found ${data_sites}"; return 1; }
    [ "${claude_sites}" -eq 1 ] || { echo "FAIL: expected exactly 1 Claude-volume (\${CLAUDE_TEMP_VOLUME_NAME}) replay site, found ${claude_sites}"; return 1; }
    # No replay may bind a LIVE volume (`docker run` lines only; the swap mounts live).
    # Any image word ([^ ]+), so this absence check cannot pass just because the image
    # text changed (it was a bare `busybox` before fix pass #26).
    run grep -cE -- '-v "\$\{(CLAUDE_)?VOLUME_NAME\}:/dest" [^ ]+ sh -c .$' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "0"
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
    # Copy-then-swap (2026-10-01): the per-CID `${CID:-}` reaps are gone. Every
    # prepare-phase helper is created with the restore label, and a reaper removes
    # every container carrying it (exact `--filter label=` match) before a temp volume
    # is removed -- so a CID printed by a create that then failed is reaped too.
    # .sh: labelled helper create, the reaper, and its call in the temp cleanup.
    run grep -cF 'if ! CID="$(docker create --label "${RESTORE_LABEL}=${VOLUME_NAME}" -v "${TEMP_VOLUME_NAME}:/dest" "${BUSYBOX_IMAGE}")"; then' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run grep -cF 'docker ps -aq --filter "label=${RESTORE_LABEL}=${lbl}" 2>/dev/null | while IFS= read -r id; do' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run grep -cF 'if [ -n "${id}" ]; then docker rm -f "${id}" > /dev/null 2>&1 || true; fi' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    # The whole function body (it grew in review round 2: the reap now sits in the
    # not-careful branch -- SF2 -- further down than a fixed `grep -A` window).
    run awk '/^_restore_remove_temps\(\) \{$/{f=1} f; f && /^\}$/{exit}' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output --partial '_restore_reap_helpers'
    # .ps1: the same labelled create, the reaper, its call in the cleanup, and the
    # inline reap of the captured $Cid right after the copy.
    run grep -cF '$cidLines = @(docker create --label "$RestoreLabel=$VolumeName" -v "${TempVolumeName}:/dest" $BusyboxImage 2>$null)' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "1"
    # Review round 2: the reap reads the IDs from STDOUT only (the split helper), so a
    # stderr line is never taken for a container ID.
    run grep -cF "Invoke-DaafRestoreDockerSplit -DockerArgs @('ps', '-aq', '--filter', \"label=\$RestoreLabel=\$lbl\")" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "1"
    run awk '/^function Invoke-DaafRestoreTempCleanup \{$/{f=1} f; f && /^\}$/{exit}' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output --partial 'Invoke-DaafRestoreHelperReap'
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
# A pipeline's status is its LAST command's (awk): busybox ash supports `set -o pipefail`
# (ASH_BASH_COMPAT, default y; source-read, not executed under busybox), but these
# programs do not turn it on, so a `find` read error used to be silent: review round 2 reproduced,
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
    sh_prog="$(sed -n "s/^VERIFY_OUTPUT=\"\$(docker run --rm -v \"\${VOLUME_NAME}:\/dest:ro\" \"\${BUSYBOX_IMAGE}\" sh -c '\([^']*\)'.*/\1/p" "${REPO_ROOT}/${RESTORE_SH}")"
    ps_prog="$(sed -n "s/^\$VerifyOutput = @(docker run --rm -v \"\${VolumeName}:\/dest:ro\" \$BusyboxImage sh -c '\([^']*\)'.*/\1/p" "${REPO_ROOT}/${RESTORE_PS1}")"
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
# fails here. The latch assignments are pinned by count: 6 in the .sh, 7 in the
# .ps1, whose extra latch is the LOWER-BOUND scan count (the .sh refuses such a
# backup instead). Adding a success-path WARNING means adding its latch and
# updating these counts (and the .ps1 count in restore_from_backup.Tests.ps1).
# Copy-then-swap (2026-10-01) changed the SET but not the counts: the two Claude
# clear/restore WARNINGs became fatal ERRORs (decision D2), and two latched WARNINGs
# were added (free space that could not be checked; a temp copy that could not be
# removed after a verified restore). Review round 1 (dispatch #7) removed one latch
# from each twin: the post-restore "File count mismatch" WARNING (1% tolerance against
# the backup count) became an exact comparison with the checked temp copy's count,
# whose failure is the after-swap ERROR path (7 -> 6 in the .sh, 8 -> 7 in the .ps1).
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
    [ "$(grep -c . "${TEST_DIR}/w_sh.txt")" -ge 7 ] || { echo "FAIL: too few WARNING lines extracted from the .sh"; cat "${TEST_DIR}/w_sh.txt"; return 1; }
    grep -qF 'WARNING: Could not verify the restored file count: Docker hit <v> read error(s)' "${TEST_DIR}/w_sh.txt" || { echo "FAIL: variable normalization did not apply"; return 1; }
    run diff "${TEST_DIR}/w_sh.txt" "${TEST_DIR}/w_ps1.txt"
    if [ "${status}" -ne 0 ]; then
        echo "DRIFT: the restore twins' WARNING messages differ"
        echo "${output}"
    fi
    assert_success
}

@test "twin-parity: restore latch sites are pinned (6 in .sh, 7 in .ps1 incl. the lower-bound scan)" {
    run grep -c '^[[:space:]]*HAD_WARNINGS=0$' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run grep -c '^[[:space:]]*HAD_WARNINGS=1$' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "6"
    run grep -c '^[[:space:]]*\$HadWarnings = \$false$' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "1"
    run grep -c '^[[:space:]]*\$HadWarnings = \$true$' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "7"
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

# ===========================================================================
# 12. RESTORE COPY-THEN-SWAP: the three container programs (2026-10-01)
# ===========================================================================
# restore_from_backup.{sh,ps1} copy the backup into a TEMPORARY volume, check it, and
# only after the RESTORE confirmation replace the live volume inside Docker. Three
# quote-free one-line programs drive that, defined once per twin as single-quoted
# assignments (`NAME='...'` in the .sh, `$Name = '...'` in the .ps1):
#   SPACE_PROGRAM / $SpaceProgram           free space + live/temp sizes (AVAIL_KB, ...)
#   SWAP_PROGRAM / $SwapProgram             clear live, cp -a temp -> live, drop marker
#   SWAP_VERIFY_PROGRAM / $SwapVerifyProgram  compare both trees (SWAP_VERIFY=MATCH)
# They must be byte-identical across the twins and contain no `"` (Windows PS 5.1
# native-argument rule). The swap must ignore INT/TERM/HUP from its first command
# (`sh -c` as PID 1 still catches SIGINT, which would stop it after `rm` and before
# `cp`, leaving live EMPTY) and every swap call must run with --sig-proxy=false.
# The programs are also RUN below under the local sh -- dash + GNU coreutils/findutils;
# busybox is NOT installed in this image, so busybox-only behavior (applet flags, the
# paren-`-exec +` flush, section 11) is covered by text pins and a host probe, not here.

_restore_prog_sh()  { sed -n "s/^$2='\(.*\)'\$/\1/p" "$1"; }
_restore_prog_ps1() { sed -n "s/^\\\$$2 = '\(.*\)'\$/\1/p" "$1"; }
_RESTORE_PROGS="SPACE_PROGRAM:SpaceProgram SWAP_PROGRAM:SwapProgram SWAP_VERIFY_PROGRAM:SwapVerifyProgram"

# Exit 0 when all three programs are defined exactly once per twin, non-empty and
# byte-identical; otherwise print the drift and exit 1. ($1 = .sh, $2 = .ps1)
_restore_progs_identical() {
    local pair s p rc=0
    for pair in ${_RESTORE_PROGS}; do
        if [ "$(grep -c "^${pair%%:*}='" "$1")" -ne 1 ]; then echo "DRIFT ${pair%%:*}: not defined exactly once in the .sh"; rc=1; fi
        if [ "$(grep -c "^\\\$${pair##*:} = '" "$2")" -ne 1 ]; then echo "DRIFT \$${pair##*:}: not defined exactly once in the .ps1"; rc=1; fi
        s="$(_restore_prog_sh "$1" "${pair%%:*}")"
        p="$(_restore_prog_ps1 "$2" "${pair##*:}")"
        if [ -z "${s}" ] || [ "${s}" != "${p}" ]; then
            echo "DRIFT ${pair}:"; echo " sh:  ${s}"; echo " ps1: ${p}"; rc=1
        fi
    done
    return "${rc}"
}

# Exit 0 when both twins' swap program starts with the INT/TERM/HUP trap and every
# swap invocation (data + Claude) carries --sig-proxy=false. ($1 = .sh, $2 = .ps1)
_swap_program_guarded() {
    local rc=0 n m
    if [[ "$(_restore_prog_sh "$1" SWAP_PROGRAM)" != 'trap : INT TERM HUP; '* ]]; then echo "sh SWAP_PROGRAM does not start with 'trap : INT TERM HUP; '"; rc=1; fi
    if [[ "$(_restore_prog_ps1 "$2" SwapProgram)" != 'trap : INT TERM HUP; '* ]]; then echo "ps1 \$SwapProgram does not start with 'trap : INT TERM HUP; '"; rc=1; fi
    n="$(grep -c 'sh -c "${SWAP_PROGRAM}"' "$1")"
    m="$(grep 'sh -c "${SWAP_PROGRAM}"' "$1" | grep -c -- 'docker run --rm --sig-proxy=false --name ')"
    if [ "${n}" -ne 2 ] || [ "${m}" -ne 2 ]; then echo "sh: ${n} swap call(s), ${m} with --sig-proxy=false (expected 2 and 2)"; rc=1; fi
    n="$(grep -c "'sh', '-c', \$SwapProgram)" "$2")"
    m="$(grep "'sh', '-c', \$SwapProgram)" "$2" | grep -c "@('run', '--rm', '--sig-proxy=false', '--name', ")"
    if [ "${n}" -ne 2 ] || [ "${m}" -ne 2 ]; then echo "ps1: ${n} swap call(s), ${m} with --sig-proxy=false (expected 2 and 2)"; rc=1; fi
    return "${rc}"
}

@test "twin-parity: the three copy-then-swap programs are byte-identical across the restore twins" {
    run _restore_progs_identical "${REPO_ROOT}/${RESTORE_SH}" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_success
    assert_output ""
}

@test "twin-parity: the three copy-then-swap programs contain zero double quotes and no single quote" {
    local pair
    for pair in ${_RESTORE_PROGS}; do
        _restore_prog_sh "${REPO_ROOT}/${RESTORE_SH}" "${pair%%:*}" > "${TEST_DIR}/p.txt"
        [ -s "${TEST_DIR}/p.txt" ]
        run dquote_count < "${TEST_DIR}/p.txt"
        assert_output "0"
        run grep -c "'" "${TEST_DIR}/p.txt"
        assert_output "0"
    done
}

@test "twin-parity: the swap program ignores INT/TERM/HUP and every swap call has --sig-proxy=false" {
    run _swap_program_guarded "${REPO_ROOT}/${RESTORE_SH}" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_success
    assert_output ""
}

@test "twin-parity SELF-TEST: the program-identity and swap-guard pins flag perturbed twins" {
    # (a) one token changed in the .ps1 swap program: identity must fail.
    sed "s#^\(\$SwapProgram = .*\)cp -a /src/. /dest/#\1cp -R /src/. /dest/#" "${REPO_ROOT}/${RESTORE_PS1}" > "${TEST_DIR}/drift.ps1"
    run grep -c 'cp -R /src/. /dest/' "${TEST_DIR}/drift.ps1"
    assert_output "1"
    run _restore_progs_identical "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/drift.ps1"
    assert_failure
    assert_output --partial "DRIFT SWAP_PROGRAM:SwapProgram"
    # (b) the trap removed from BOTH twins (identity still holds): the guard must fail.
    sed 's#^SWAP_PROGRAM='"'"'trap : INT TERM HUP; #SWAP_PROGRAM='"'"'#' "${REPO_ROOT}/${RESTORE_SH}" > "${TEST_DIR}/notrap.sh"
    sed "s#^\$SwapProgram = 'trap : INT TERM HUP; #\$SwapProgram = '#" "${REPO_ROOT}/${RESTORE_PS1}" > "${TEST_DIR}/notrap.ps1"
    run _restore_progs_identical "${TEST_DIR}/notrap.sh" "${TEST_DIR}/notrap.ps1"
    assert_success
    run _swap_program_guarded "${TEST_DIR}/notrap.sh" "${TEST_DIR}/notrap.ps1"
    assert_failure
    assert_output --partial "does not start with"
    # (c) --sig-proxy=false dropped from the .sh Claude swap call only.
    sed 's#--sig-proxy=false --name "${CLAUDE_SWAP_CONTAINER_NAME}"#--name "${CLAUDE_SWAP_CONTAINER_NAME}"#' "${REPO_ROOT}/${RESTORE_SH}" > "${TEST_DIR}/noproxy.sh"
    run cmp -s "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/noproxy.sh"
    assert_failure
    run _swap_program_guarded "${TEST_DIR}/noproxy.sh" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_failure
    assert_output --partial "sh: 2 swap call(s), 1 with --sig-proxy=false"
}

@test "twin-parity: the temp-copy check runs the SAME count program (same find predicate) as the post-restore check" {
    local sh_live sh_temp ps_live ps_temp pred_live pred_temp
    sh_live="$(sed -n "s/^VERIFY_OUTPUT=\"\$(docker run --rm -v \"\${VOLUME_NAME}:\/dest:ro\" \"\${BUSYBOX_IMAGE}\" sh -c '\([^']*\)'.*/\1/p" "${REPO_ROOT}/${RESTORE_SH}")"
    sh_temp="$(sed -n "s/^TEMP_VERIFY_OUTPUT=\"\$(docker run --rm --label \"\${RESTORE_LABEL}=\${VOLUME_NAME}\" -v \"\${TEMP_VOLUME_NAME}:\/dest:ro\" \"\${BUSYBOX_IMAGE}\" sh -c '\([^']*\)'.*/\1/p" "${REPO_ROOT}/${RESTORE_SH}")"
    ps_live="$(sed -n "s/^\$VerifyOutput = @(docker run --rm -v \"\${VolumeName}:\/dest:ro\" \$BusyboxImage sh -c '\([^']*\)'.*/\1/p" "${REPO_ROOT}/${RESTORE_PS1}")"
    ps_temp="$(sed -n "s/^ *\$TempVerifyOutput = @(docker run --rm --label \"\$RestoreLabel=\$VolumeName\" -v \"\${TempVolumeName}:\/dest:ro\" \$BusyboxImage sh -c '\([^']*\)'.*/\1/p" "${REPO_ROOT}/${RESTORE_PS1}")"
    [ -n "${sh_live}" ]
    [ -n "${sh_temp}" ]
    [ "${sh_temp}" = "${sh_live}" ] || { echo "DRIFT .sh temp vs live:"; echo " ${sh_temp}"; echo " ${sh_live}"; return 1; }
    [ "${ps_temp}" = "${ps_live}" ] || { echo "DRIFT .ps1 temp vs live:"; echo " ${ps_temp}"; echo " ${ps_live}"; return 1; }
    [ "${ps_temp}" = "${sh_temp}" ] || { echo "DRIFT temp .sh vs .ps1"; return 1; }
    # The find predicate itself, named explicitly.
    pred_live="$(printf '%s' "${sh_live}" | sed 's/.*n=\$(\(find [^|]*\)|.*/\1/')"
    pred_temp="$(printf '%s' "${sh_temp}" | sed 's/.*n=\$(\(find [^|]*\)|.*/\1/')"
    [ "${pred_temp}" = "${pred_live}" ]
    [[ "${pred_temp}" == 'find /dest -type f ! -path /dest/.daaf-symlinks ! -path /dest/.daaf-permissions ! -path /dest/.daaf-claude-config/\* -exec stat -c %s {} + 2>/tmp/count_err '* ]]
}

@test "twin-parity: both restore twins derive the same temp/swap names, label and state marker" {
    run grep -cxF 'TEMP_VOLUME_NAME="${VOLUME_NAME}-restore-tmp"' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run grep -cxF 'CLAUDE_TEMP_VOLUME_NAME="${CLAUDE_VOLUME_NAME}-restore-tmp"' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run grep -cxF 'SWAP_CONTAINER_NAME="${VOLUME_NAME}-restore-swap"' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run grep -cxF 'CLAUDE_SWAP_CONTAINER_NAME="${CLAUDE_VOLUME_NAME}-restore-swap"' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run grep -cxF 'RESTORE_LABEL="org.daaf.restore-tmp-for"' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run grep -cxF 'SWAP_MARKER=".daaf-restore-swap-started"' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run grep -cxF '$TempVolumeName = "${VolumeName}-restore-tmp"' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "1"
    run grep -cxF '$ClaudeTempVolumeName = "${ClaudeVolumeName}-restore-tmp"' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "1"
    run grep -cxF '$SwapContainerName = "${VolumeName}-restore-swap"' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "1"
    run grep -cxF '$ClaudeSwapContainerName = "${ClaudeVolumeName}-restore-swap"' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "1"
    run grep -cxF '$RestoreLabel = "org.daaf.restore-tmp-for"' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "1"
    run grep -cxF '$SwapMarker = ".daaf-restore-swap-started"' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "1"
    # The marker is a literal inside the shared programs (SYNC NOTE in both twins).
    _restore_prog_sh "${REPO_ROOT}/${RESTORE_SH}" SWAP_PROGRAM > "${TEST_DIR}/swap.txt"
    run grep -c 'rm -f /dest/.daaf-restore-swap-started$' "${TEST_DIR}/swap.txt"
    assert_output "1"
}

# Point an extracted restore program at a fixture ($1): container /tmp/ -> $1/ctmp/,
# /src and /dest -> $1/src and $1/dest, `cd /$t` -> `cd $1/$t`. The /tmp/ rewrite runs
# first, on the program text only (TEST_DIR may sit under a folder named tmp).
_localize_restore_prog() {
    mkdir -p "$1/ctmp"
    sed -e "s#/tmp/#$1/ctmp/#g" -e "s# /src# $1/src#g" -e "s# /dest# $1/dest#g" -e "s#cd /\\\$t#cd $1/\$t#"
}

# The fixture: every kind of entry the swap must carry (dotfile, symlink, executable,
# a name with spaces, a nested EMPTY folder) plus the state marker in the temp copy and
# an old file in the live copy. All under TEST_DIR (teardown removes it, symlink too).
_make_swap_fixture() {
    local f="$1"
    mkdir -p "${f}/src/sub/empty" "${f}/dest/old"
    printf 'a\n' > "${f}/src/top.txt"
    printf '#!/bin/sh\n' > "${f}/src/sub/run.sh"
    chmod 755 "${f}/src/sub/run.sh"
    printf 'x\n' > "${f}/src/.dot"
    printf 'y\n' > "${f}/src/sub/name with spaces"
    ln -s top.txt "${f}/src/link.txt"
    : > "${f}/src/.daaf-restore-swap-started"
    printf 'old\n' > "${f}/dest/old/keep"
}

@test "twin-parity: SWAP_PROGRAM run under sh replaces the live tree with the temp copy and drops the marker" {
    local f="${TEST_DIR}/sw"
    _make_swap_fixture "${f}"
    _restore_prog_sh "${REPO_ROOT}/${RESTORE_SH}" SWAP_PROGRAM | _localize_restore_prog "${f}" > "${TEST_DIR}/swap_run.sh"
    run grep -cE '(^|[ >])/(src|dest|tmp)(/|[ ;]|$)' "${TEST_DIR}/swap_run.sh"
    assert_output "0"
    run "$(_run_shell)" "${TEST_DIR}/swap_run.sh"
    assert_success
    run ls -A "${f}/dest"
    assert_output "$(printf '%s\n' .dot link.txt sub top.txt)"
    [ -x "${f}/dest/sub/run.sh" ]
    [ -L "${f}/dest/link.txt" ]
    run readlink "${f}/dest/link.txt"
    assert_output "top.txt"
    [ -d "${f}/dest/sub/empty" ]
    [ -f "${f}/dest/sub/name with spaces" ]
    [ ! -e "${f}/dest/old" ]
    [ ! -e "${f}/dest/.daaf-restore-swap-started" ]
    # The temp copy is left as it was (the marker stays there: leftover evidence).
    [ -e "${f}/src/.daaf-restore-swap-started" ]
}

@test "twin-parity: SWAP_VERIFY_PROGRAM run under sh prints MATCH after the swap and MISMATCH after a change" {
    local f="${TEST_DIR}/sv" prog
    _make_swap_fixture "${f}"
    _restore_prog_sh "${REPO_ROOT}/${RESTORE_SH}" SWAP_PROGRAM | _localize_restore_prog "${f}" > "${TEST_DIR}/swap_run.sh"
    _restore_prog_sh "${REPO_ROOT}/${RESTORE_SH}" SWAP_VERIFY_PROGRAM | _localize_restore_prog "${f}" > "${TEST_DIR}/verify_run.sh"
    run grep -cE '(^|[ >])/(src|dest|tmp)(/|[ ;]|$)' "${TEST_DIR}/verify_run.sh"
    assert_output "0"
    run "$(_run_shell)" "${TEST_DIR}/swap_run.sh"
    assert_success
    # 8 entries per side: 5 non-directories (.dot, link.txt, top.txt, sub/run.sh,
    # sub/name with spaces), 2 directories below the root (sub, sub/empty), 1 link
    # target; the root folder and the marker are left out.
    run "$(_run_shell)" "${TEST_DIR}/verify_run.sh"
    assert_success
    assert_output "$(printf '%s\n' SWAP_VERIFY=MATCH SWAP_VERIFY_ENTRIES=8:8)"
    # A mode change, a size change and a link-target change each MISMATCH. (An owner
    # change needs root here; it lands in the same %u:%g columns as the mode.)
    chmod 600 "${f}/dest/sub/run.sh"
    run "$(_run_shell)" "${TEST_DIR}/verify_run.sh"
    assert_output --partial "SWAP_VERIFY=MISMATCH"
    chmod 755 "${f}/dest/sub/run.sh"
    printf 'more\n' >> "${f}/dest/top.txt"
    run "$(_run_shell)" "${TEST_DIR}/verify_run.sh"
    assert_output --partial "SWAP_VERIFY=MISMATCH"
    printf 'a\n' > "${f}/dest/top.txt"
    ln -sfn sub "${f}/dest/link.txt"
    run "$(_run_shell)" "${TEST_DIR}/verify_run.sh"
    assert_output --partial "SWAP_VERIFY=MISMATCH"
    ln -sfn top.txt "${f}/dest/link.txt"
    run "$(_run_shell)" "${TEST_DIR}/verify_run.sh"
    assert_output "$(printf '%s\n' SWAP_VERIFY=MATCH SWAP_VERIFY_ENTRIES=8:8)"
    # A listing that hits a read error is neither MATCH nor MISMATCH.
    if [ "$(id -u)" -ne 0 ]; then
        chmod 000 "${f}/dest/sub/empty"
        run "$(_run_shell)" "${TEST_DIR}/verify_run.sh"
        chmod 755 "${f}/dest/sub/empty"
        assert_output --partial "SWAP_VERIFY_ERRORS="
        refute_output --partial "SWAP_VERIFY=MATCH"
    fi
}

@test "twin-parity: SPACE_PROGRAM run under sh prints AVAIL_KB and LIVE_KB, plus SRC_KB only when /src is mounted" {
    local f="${TEST_DIR}/sp" live_kb src_kb
    mkdir -p "${f}/dest" "${f}/src"
    head -c 50000 /dev/zero > "${f}/dest/a.bin"
    head -c 90000 /dev/zero > "${f}/src/b.bin"
    live_kb="$(du -sk "${f}/dest" | awk '{print $1}')"
    src_kb="$(du -sk "${f}/src" | awk '{print $1}')"
    _restore_prog_sh "${REPO_ROOT}/${RESTORE_SH}" SPACE_PROGRAM | _localize_restore_prog "${f}" > "${TEST_DIR}/space_run.sh"
    run grep -cE '(^|[ >])/(src|dest|tmp)(/|[ ;]|$)' "${TEST_DIR}/space_run.sh"
    assert_output "0"
    run "$(_run_shell)" "${TEST_DIR}/space_run.sh"
    assert_success
    [ "${#lines[@]}" -eq 3 ]
    [[ "${lines[0]}" =~ ^AVAIL_KB=[0-9]+$ ]]
    [ "${lines[1]}" = "LIVE_KB=${live_kb}" ]
    [ "${lines[2]}" = "SRC_KB=${src_kb}" ]
    # Without a /src mount (the first check), no SRC_KB line.
    mv "${f}/src" "${f}/src_off"
    run "$(_run_shell)" "${TEST_DIR}/space_run.sh"
    assert_success
    [ "${#lines[@]}" -eq 2 ]
    [ "${lines[1]}" = "LIVE_KB=${live_kb}" ]
    refute_output --partial "SRC_KB="
}

# ===========================================================================
# Swap-time running-container re-check (2026-10-01, dispatch #6)
# ===========================================================================
# Right after RESTORE and before the state marker and the swaps, both restore twins
# re-run `docker ps --filter volume=<live> --filter volume=<claude>`. Two rules, the
# same in both twins: (a) container names come from STDOUT only (the .ps1 once read
# them through `2>&1`, so a failing `docker ps` listed its own error text as a
# "container"); (b) a FAILED `docker ps` is "could not check", never "nothing is
# running" (the .sh once ignored the failure with `|| true` and swapped anyway): it
# refuses with the same three ERROR lines, removes the temp volumes, exit 1.
# Behaviour is tested in restore_from_backup.bats / restore_from_backup.Tests.ps1;
# these pins hold the twins' text and structure together.

# The refusal's ERROR lines from one twin (first quoted string per line, variable
# references normalized to <v>, like _restore_warning_set).
_could_not_check_msg() {
    grep -A 2 -F 'ERROR: Could not check whether DAAF is running' "$1" \
    | sed -e 's/^[^"]*"\([^"]*\)".*/\1/' \
          -e 's/\${[A-Za-z_][A-Za-z_0-9]*}/<v>/g' \
          -e 's/\$[A-Za-z_][A-Za-z_0-9]*/<v>/g'
}

# Exit 0 (no output) when both twins' re-check reads stdout only and refuses on a
# failed `docker ps`. ($1 = .sh, $2 = .ps1)
_swap_recheck_guarded() {
    local rc=0 l
    l="$(grep -F 'RUNNING_NOW="$(docker ps --filter ' "$1")"
    if [ "$(printf '%s\n' "${l}" | grep -c .)" -ne 1 ]; then
        echo "sh: expected exactly one swap-time docker ps re-check"; rc=1
    elif [[ "${l}" != *' 2>/dev/null)" || RUNNING_NOW_EXIT=$?' ]]; then
        echo "sh: the re-check must read stdout only and capture its exit code (no || true)"; rc=1
    fi
    grep -qxF 'if [ "${RUNNING_NOW_EXIT}" -ne 0 ]; then' "$1" || { echo "sh: no refusal on a failed docker ps"; rc=1; }
    l="$(grep -F '$runningNowLines = @(docker ps --filter ' "$2")"
    if [ "$(printf '%s\n' "${l}" | grep -c .)" -ne 1 ]; then
        echo "ps1: expected exactly one swap-time docker ps re-check"; rc=1
    elif [[ "${l}" != *' 2>$null)' ]]; then
        echo "ps1: the re-check must read stdout only (2>\$null, never 2>&1)"; rc=1
    fi
    grep -qF '$runningNowExit = $LASTEXITCODE' "$2" || { echo "ps1: the re-check's exit code is not captured"; rc=1; }
    grep -qF 'if ($runningNowExit -ne 0) {' "$2" || { echo "ps1: no refusal on a failed docker ps"; rc=1; }
    return "${rc}"
}

@test "twin-parity: both restore twins refuse with the same text when docker ps fails (startup, then swap time)" {
    # 2026-10-02: the STARTUP running-container check refuses a failed `docker ps` too
    # (first block; nothing has been created yet); the swap-time re-check is the second.
    local expected
    expected="$(printf '%s\n' \
        'ERROR: Could not check whether DAAF is running (docker ps failed, exit <v>),' \
        '       so the restore cannot start safely. This restore has not changed anything.' \
        '       Make sure Docker Desktop is running, then run the restore again.' \
        '--' \
        'ERROR: Could not check whether DAAF is running (docker ps failed, exit <v>),' \
        '       so your data cannot be replaced safely. Make sure Docker Desktop is running,' \
        '       then run the restore again.')"
    run _could_not_check_msg "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "${expected}"
    run _could_not_check_msg "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "${expected}"
}

@test "twin-parity: the swap-time re-check reads names from stdout only and refuses on a failed docker ps (both twins)" {
    run _swap_recheck_guarded "${REPO_ROOT}/${RESTORE_SH}" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_success
    assert_output ""
}

@test "twin-parity SELF-TEST: the re-check guard flags an ignored failure (.sh) and a merged stderr (.ps1)" {
    sed 's#2>/dev/null)" || RUNNING_NOW_EXIT=\$?#2>/dev/null || true)"#' "${REPO_ROOT}/${RESTORE_SH}" > "${TEST_DIR}/ignore.sh"
    run cmp -s "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/ignore.sh"
    assert_failure
    run _swap_recheck_guarded "${TEST_DIR}/ignore.sh" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_failure
    assert_output --partial "sh: the re-check must read stdout only and capture its exit code"
    sed 's#^\(.*\$runningNowLines = @(docker ps .*\) 2>\$null)$#\1 2>\&1)#' "${REPO_ROOT}/${RESTORE_PS1}" > "${TEST_DIR}/merge.ps1"
    run cmp -s "${REPO_ROOT}/${RESTORE_PS1}" "${TEST_DIR}/merge.ps1"
    assert_failure
    run _swap_recheck_guarded "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/merge.ps1"
    assert_failure
    assert_output --partial "ps1: the re-check must read stdout only"
}

# The STARTUP running-container check (2026-10-02): the same two rules as the swap-time
# re-check -- names from STDOUT only, and a FAILED `docker ps` refuses (exit 1, before
# anything is created). Exit 0 (no output) when both twins hold. ($1 = .sh, $2 = .ps1)
_startup_check_guarded() {
    local rc=0 l
    l="$(grep -F 'RUNNING_CONTAINERS="$(docker ps --filter ' "$1")"
    if [ "$(printf '%s\n' "${l}" | grep -c .)" -ne 1 ]; then
        echo "sh: expected exactly one startup docker ps check"; rc=1
    elif [[ "${l}" != *' 2>/dev/null)" || RUNNING_CONTAINERS_EXIT=$?' ]]; then
        echo "sh: the startup check must read stdout only and capture its exit code (no || true)"; rc=1
    fi
    grep -qxF 'if [ "${RUNNING_CONTAINERS_EXIT}" -ne 0 ]; then' "$1" || { echo "sh: no startup refusal on a failed docker ps"; rc=1; }
    l="$(grep -F '$RunningContainers = @(docker ps --filter ' "$2")"
    if [ "$(printf '%s\n' "${l}" | grep -c .)" -ne 1 ]; then
        echo "ps1: expected exactly one startup docker ps check"; rc=1
    elif [[ "${l}" != *' 2>$null)' ]]; then
        echo "ps1: the startup check must read stdout only (2>\$null, never 2>&1)"; rc=1
    fi
    grep -qF '$runningContainersExit = $LASTEXITCODE' "$2" || { echo "ps1: the startup check's exit code is not captured"; rc=1; }
    grep -qF 'if ($runningContainersExit -ne 0) {' "$2" || { echo "ps1: no startup refusal on a failed docker ps"; rc=1; }
    return "${rc}"
}

@test "twin-parity: the startup running-container check reads names from stdout only and refuses on a failed docker ps (both twins)" {
    run _startup_check_guarded "${REPO_ROOT}/${RESTORE_SH}" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_success
    assert_output ""
}

@test "twin-parity SELF-TEST: the startup guard flags an ignored failure (.sh) and an unread exit code (.ps1)" {
    sed 's#2>/dev/null)" || RUNNING_CONTAINERS_EXIT=\$?#2>/dev/null || true)"#' "${REPO_ROOT}/${RESTORE_SH}" > "${TEST_DIR}/ignore.sh"
    run cmp -s "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/ignore.sh"
    assert_failure
    run _startup_check_guarded "${TEST_DIR}/ignore.sh" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_failure
    assert_output --partial "sh: the startup check must read stdout only and capture its exit code"
    sed '/^\$runningContainersExit = \$LASTEXITCODE$/d' "${REPO_ROOT}/${RESTORE_PS1}" > "${TEST_DIR}/noexit.ps1"
    run cmp -s "${REPO_ROOT}/${RESTORE_PS1}" "${TEST_DIR}/noexit.ps1"
    assert_failure
    run _startup_check_guarded "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/noexit.ps1"
    assert_failure
    assert_output --partial "ps1: the startup check's exit code is not captured"
}

# The backup twins' closing hint describes the restore as it now works (copy into a
# temporary volume, check, replace only after confirmation), identically in both.
@test "twin-parity: both backup twins describe the copy-then-swap restore in the same closing text" {
    local l
    for l in 'The restore script lets you pick which backup to restore from. It first' \
             'copies the backup into a temporary Docker volume and checks it there; only' \
             'after you confirm does it replace your current DAAF data.'; do
        run grep -cxF "echo \"${l}\"" "${REPO_ROOT}/${BACKUP_SH}"
        assert_output "1"
        run grep -cxF "Write-Host \"${l}\"" "${REPO_ROOT}/${BACKUP_PS1}"
        assert_output "1"
    done
    # The pre-copy-then-swap wording is gone from both.
    run grep -lF 'clearing the volume before copying' "${REPO_ROOT}/${BACKUP_SH}" "${REPO_ROOT}/${BACKUP_PS1}"
    assert_failure
}

# ===========================================================================
# 13. REVIEW ROUND 1 (dispatch #7): the swap only ever uses THIS run's checked copy
# ===========================================================================
# The REAL changed programs, run under the local sh (dash + GNU; busybox is not
# installed here -- see the host probe doc) against self-cleaning fixtures in TEST_DIR.

@test "twin-parity B1: SWAP_PROGRAM erases NOTHING when /src lacks the state marker (exit 3, live untouched)" {
    # Review round 2 (S1): exit 3 -- a code nothing else in the program uses -- so the
    # host can tell "nothing was replaced" from a failed rm/cp (exit 1).
    local f="${TEST_DIR}/nm"
    _make_swap_fixture "${f}"
    rm -f "${f}/src/.daaf-restore-swap-started"
    _restore_prog_sh "${REPO_ROOT}/${RESTORE_SH}" SWAP_PROGRAM | _localize_restore_prog "${f}" > "${TEST_DIR}/swap_run.sh"
    run "$(_run_shell)" "${TEST_DIR}/swap_run.sh"
    assert_failure 3
    run cat "${f}/dest/old/keep"
    assert_output "old"
    [ ! -e "${f}/dest/top.txt" ]
}

@test "twin-parity B1: SWAP_PROGRAM against an EMPTY /src (a vanished temp re-created empty) leaves live untouched (exit 3)" {
    local f="${TEST_DIR}/em"
    mkdir -p "${f}/src" "${f}/dest/old"
    printf 'old\n' > "${f}/dest/old/keep"
    _restore_prog_sh "${REPO_ROOT}/${RESTORE_SH}" SWAP_PROGRAM | _localize_restore_prog "${f}" > "${TEST_DIR}/swap_run.sh"
    run "$(_run_shell)" "${TEST_DIR}/swap_run.sh"
    assert_failure 3
    run cat "${f}/dest/old/keep"
    assert_output "old"
}

@test "twin-parity B1: SWAP_VERIFY_PROGRAM on two EMPTY trees prints MATCH with ENTRIES 0:0 (what the host must reject)" {
    local f="${TEST_DIR}/ee"
    mkdir -p "${f}/src" "${f}/dest"
    _restore_prog_sh "${REPO_ROOT}/${RESTORE_SH}" SWAP_VERIFY_PROGRAM | _localize_restore_prog "${f}" > "${TEST_DIR}/verify_run.sh"
    run "$(_run_shell)" "${TEST_DIR}/verify_run.sh"
    assert_success
    assert_output "$(printf '%s\n' SWAP_VERIFY=MATCH SWAP_VERIFY_ENTRIES=0:0)"
}

@test "twin-parity B1: both twins require SWAP_VERIFY_ENTRIES n:n, and n > 0 for the data volume" {
    run grep -cF "if ! _restore_swap_checked \"\${SWAP_VERIFY_OUTPUT}\" nonempty; then" "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run grep -cF "if ! _restore_swap_checked \"\${SWAP_VERIFY_OUTPUT}\"; then" "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run grep -cF "if (-not (Test-DaafRestoreSwapChecked -Lines \$swapCheck -NonEmpty)) {" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "1"
    run grep -cF "if (-not (Test-DaafRestoreSwapChecked -Lines \$swapCheck)) {" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "1"
    # The old MATCH-only checks are gone.
    run grep -c "grep -qx 'SWAP_VERIFY=MATCH'" "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "0"
}

@test "twin-parity B1: SWAP_VERIFY_PROGRAM reports a list that could not be written (failed sort) as an ERROR, never MATCH" {
    local f="${TEST_DIR}/sf"
    _make_swap_fixture "${f}"
    mkdir -p "${TEST_DIR}/shim"
    printf '#!/bin/sh\necho "sort: write failed: No space left on device" >&2\nexit 2\n' > "${TEST_DIR}/shim/sort"
    chmod +x "${TEST_DIR}/shim/sort"
    _restore_prog_sh "${REPO_ROOT}/${RESTORE_SH}" SWAP_VERIFY_PROGRAM | _localize_restore_prog "${f}" > "${TEST_DIR}/verify_run.sh"
    run env PATH="${TEST_DIR}/shim:${PATH}" "$(_run_shell)" "${TEST_DIR}/verify_run.sh"
    assert_output --partial "SWAP_VERIFY_ERRORS="
    refute_output --partial "SWAP_VERIFY=MATCH"
    # Both failed list writes were recorded in the program's error file (the listing
    # commands' own broken-pipe errors land there too, so the total varies).
    run grep -cx 'LIST_FAILED_src' "${f}/ctmp/err"
    assert_output "1"
    run grep -cx 'LIST_FAILED_dest' "${f}/ctmp/err"
    assert_output "1"
}

@test "twin-parity B1: both twins create temp volumes with the per-run identity label and re-check it" {
    run grep -cF 'RESTORE_RUN_LABEL="org.daaf.restore-run"' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run grep -cF '$RestoreRunLabel = "org.daaf.restore-run"' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "1"
    run grep -cF -- '--label "${RESTORE_RUN_LABEL}=${RESTORE_RUN_ID}"' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "2"
    run grep -cF "'--label', \"\$RestoreRunLabel=\$RestoreRunId\"" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "2"
    # `{{.Labels}}` passes Windows PowerShell 5.1 unchanged: no space, no quote.
    run grep -cF "docker volume inspect --format '{{.Labels}}'" "${REPO_ROOT}/${RESTORE_SH}" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output --partial "restore_from_backup.sh:1"
    assert_output --partial "restore_from_backup.ps1:1"
}

@test "twin-parity I3/S3: both twins print the same new plain-language lines" {
    local l
    for l in 'This restore did not change anything, but your DAAF data may still be' \
             'incomplete from the earlier restore. Run the restore again to finish it.' \
             'If another restore window is still open, answer n.' \
             '       If this keeps happening, restart Docker Desktop and try again.' \
             '       Close any other restore window, then run this restore again.' \
             '       something else while this restore was running -- for example, a restore' \
             '       started in another window. It was not used, and nothing was removed.' \
             '       and was created by this restore, so it was left as it is (it may belong to'; do
        run grep -cF "${l}" "${REPO_ROOT}/${RESTORE_SH}"
        [ "${output}" -ge 1 ]
        run grep -cF "${l}" "${REPO_ROOT}/${RESTORE_PS1}"
        [ "${output}" -ge 1 ]
    done
}

# Review round 3 (2026-10-01). I-1: ONLY the swap program's own exit 3 is "nothing was
# replaced" -- Docker's 125 can follow a daemon restart mid-swap, after the rm ran --
# so neither twin's code (comments aside) treats 125 specially any more. S-a: the
# Claude-after-data text says the old login may be gone once the Claude swap ran.
# S-c: the careful-cleanup flag is set before the swap-started flag is cleared.
@test "twin-parity round 3 (I-1): both twins classify ONLY data-swap exit 3 as 'nothing replaced'; no code line mentions 125" {
    run grep -cxF 'if [ "${SWAP_EXIT}" -eq 3 ]; then' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run grep -cxF '        if ($swapExit -eq 3) {' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "1"
    run grep -cE '^[[:space:]]*[^#[:space:]].*125' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "0"
    run grep -cE '^[[:space:]]*[^#[:space:]].*125' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "0"
}

@test "twin-parity round 3 (S-a): both twins print the same 'old login may be gone' lines, keyed on the Claude swap having run" {
    local l
    for l in '       login and session history were not restored."' \
             '       Your previous Claude Code login may also be gone now; running the restore again"' \
             "       puts the backup's login and history back.\"" \
             '       The checked copy of the backup is"'; do
        run grep -cF "${l}" "${REPO_ROOT}/${RESTORE_SH}"
        assert_output "1"
        run grep -cF "${l}" "${REPO_ROOT}/${RESTORE_PS1}"
        assert_output "1"
    done
    # Set from the Claude swap's exit (anything but 3), in both twins.
    run grep -cxF '    if [ "${SWAP_EXIT}" -ne 3 ]; then CLAUDE_SWAP_RAN=1; fi' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run grep -cxF '            if ($swapExit -ne 3) { $ClaudeSwapRan = $true }' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "1"
}

@test "twin-parity round 3 (S-c): the .ps1 sets the careful-cleanup flag BEFORE it clears the swap-started flag (as the .sh)" {
    run bash -c "grep -A 2 -xF '        if (\$swapExit -eq 3) {' '${REPO_ROOT}/${RESTORE_PS1}' | tail -n 2"
    assert_output "$(printf '%s\n' '            $TempCleanupCareful = $true' '            $SwapStarted = $false')"
    run bash -c "sed -n '/^_restore_fail_swap_not_run() {\$/,/^}\$/p' '${REPO_ROOT}/${RESTORE_SH}' | sed -n '2,3p'"
    assert_output "$(printf '%s\n' '    TEMP_CLEANUP_CAREFUL=1' '    SWAP_STARTED=0')"
}

# ===========================================================================
# 14. FIELD TEST 2026-10-05 (fix pass #18): D1 holders, D3 wording
# ===========================================================================
# D1: a never-started (Created) container that still referenced a temp volume blocked
# its removal (it does not go away on its own while Docker keeps running; a Docker
# restart is expected to remove it -- moby restore(), inference). Both twins now list a
# temp's holders (`docker ps -a --filter
# volume=<temp> --format '{{.ID}} {{.State}}'`, stdout only), remove created / exited /
# dead ones with a PLAIN `docker rm <id>` (never -f), then the volume; any other state
# refuses, and a failed list is "could not check". D3: a Ctrl+C during the Claude Code
# swap names the Claude state. Pinned here: every new user-visible string (strings 1-7
# of the fix-pass-18 report) VERBATIM in both twins, the D1 argv shape, the check-before-
# removal order on the leftover path, and the D3 flag's place. (D2 is .ps1-only: Pester.)
# Behaviour: restore_from_backup.bats ("D1:" / "D3:") and restore_from_backup.Tests.ps1.
# The latch pins above (6 / 7) are unchanged by this pass: the new reason and hint lines
# extend the existing temp-removal WARNING, they add no latch.

# A function's body: .sh `name() {` ... `}`; .ps1 `function Name {` ... `}`.
_fn_body_sh()  { sed -n "/^$2() {\$/,/^}\$/p" "$1"; }
_fn_body_ps1() { sed -n "/^function $2 {\$/,/^}\$/p" "$1"; }

# The message text of a function body (stdin): the first "..." string after each echo /
# Write-Host, variable references ($(...), ${...}, $name, $1) normalized to <v>.
_msg_text() {
    grep -E '(echo|Write-Host) "' \
    | sed -E -e 's/.*(echo|Write-Host) "([^"]*)".*/\2/' \
             -e 's/\$\([^)]*\)/<v>/g' \
             -e 's/\$\{[A-Za-z_0-9]*\}/<v>/g' \
             -e 's/\$[A-Za-z_][A-Za-z_0-9]*/<v>/g' \
             -e 's/\$[0-9]/<v>/g'
}

# The new user-visible strings, each a fragment that must occur in BOTH twins' source
# (fix-pass-18 report strings 1-7; a variable part ends the fragment).
_D1_D3_STRINGS=(
    'The temporary copy could not be removed."'
    'To free the space it uses, run:"'
    'Something is still using it; another restore may still be running."'
    'Could not check what is using it (docker ps failed, exit '
    'Docker said: '
    '  docker volume rm '
    'If Docker says it is in use, first run"'
    '  docker ps -a'
    'and remove each container it lists with docker rm <ID>, then try again."'
    '         Your DAAF data was restored. To free the space it uses, run:"'
    'ERROR: Could not remove the temporary copy left by the earlier restore."'
    '       Docker said: '
    'ERROR: Something is still using the temporary copy left by the earlier restore"'
    "'), so it was not removed. Another restore may\""
    '       still be running."'
    '       Wait a few minutes and close any other restore window, then run this"'
    'ERROR: Could not check what is using the temporary copy left by the earlier"'
    '; docker ps failed, exit '
    '), so it was not removed."'
    '       Make sure Docker Desktop is running, then run this restore again."'
    'Restore interrupted while the Claude Code state (login and session history) was being replaced."'
    'Your project files (DAAF data) were already replaced and checked."'
)

# Exit 0 (no output) when every string above occurs in both twins and the replaced
# texts are gone from both. ($1 = .sh, $2 = .ps1)
_d1_d3_strings_pinned() {
    local rc=0 s f
    for s in "${_D1_D3_STRINGS[@]}"; do
        for f in "$1" "$2"; do
            grep -qF -- "${s}" "${f}" || { echo "MISSING in ${f##*/}: ${s}"; rc=1; }
        done
    done
    for f in "$1" "$2"; do
        # The old two-line kept-temp text, and the restart line of the leftover-removal
        # failure: the running-swap refusal's line is now the only unwrapped copy (exactly
        # one; the inspect refusal keeps the restart advice too, wrapped over two lines).
        if grep -qF 'The temporary copy could not be removed. To free' "${f}"; then echo "OLD kept-temp text in ${f##*/}"; rc=1; fi
        [ "$(grep -cF 'If this keeps happening, restart Docker Desktop and try again."' "${f}")" -eq 1 ] || { echo "restart line count != 1 in ${f##*/}"; rc=1; }
    done
    return "${rc}"
}

@test "twin-parity D1/D3: every new user-visible string is present VERBATIM in both restore twins; the replaced texts are gone" {
    run _d1_d3_strings_pinned "${REPO_ROOT}/${RESTORE_SH}" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_success
    assert_output ""
}

@test "twin-parity D1: the refusal, kept-temp and hint helpers print the same text in both twins (normalized)" {
    local pair sh ps1 n
    for pair in _restore_leftover_refusal:Write-DaafRestoreLeftoverRefusal \
                _restore_kept_temp_hint:Write-DaafRestoreKeptTempHint \
                _restore_remove_hint:Write-DaafRestoreRemoveHint; do
        sh="${pair%%:*}"; ps1="${pair#*:}"
        _fn_body_sh "${REPO_ROOT}/${RESTORE_SH}" "${sh}" | _msg_text > "${TEST_DIR}/m_sh.txt"
        _fn_body_ps1 "${REPO_ROOT}/${RESTORE_PS1}" "${ps1}" | _msg_text > "${TEST_DIR}/m_ps1.txt"
        n="$(grep -c . "${TEST_DIR}/m_sh.txt" || true)"
        [ "${n}" -ge 3 ] || { echo "FAIL: ${sh}: too few message lines extracted (${n})"; return 1; }
        # The ONE known source difference: the .sh carries the filters' leading space in
        # the variable (`-a${filters}`), the .ps1 in the template (`-a $filters`, the
        # filters joined with ' '); both print `docker ps -a --filter volume=<t1>[ --filter
        # volume=<t2>]`. That line is compared through the per-twin pins below.
        run diff <(grep -v '  docker ps -a' "${TEST_DIR}/m_sh.txt") <(grep -v '  docker ps -a' "${TEST_DIR}/m_ps1.txt")
        if [ "${status}" -ne 0 ]; then echo "DRIFT in ${sh} / ${ps1}:"; echo "${output}"; fi
        assert_success
    done
    run grep -cxF '    for tv in $2; do filters="${filters} --filter volume=${tv}"; done' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run grep -cxF '    echo "${1}  docker ps -a${filters}"' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run grep -cxF "    \$filters = @(@(\$Volumes -split ' ' | Where-Object { \$_ -ne '' }) | ForEach-Object { \"--filter volume=\$_\" }) -join ' '" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "1"
    run grep -cxF '    Write-Host "$Lead  docker ps -a $filters"' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "1"
}

@test "twin-parity D1: every message site uses the shared hint helpers (cancel, leftover failure, kept temp, final WARNING)" {
    local l
    for l in '_restore_remove_hint "" "${LEFTOVER_VOLUMES}"' \
             '_restore_remove_hint "       " "${LEFTOVER_VOLUMES}" >&2' \
             '_restore_remove_hint "$1" "$(_restore_kept_temps)"' \
             '_restore_remove_hint "         " "${KEPT_TEMPS}" >&2' \
             'if [ -n "${LEFTOVER_SAID}" ]; then echo "       Docker said: ${LEFTOVER_SAID}" >&2; fi' \
             'while IFS= read -r NOTE_LINE; do echo "         ${NOTE_LINE}" >&2; done <<EOF'; do
        run grep -cF -- "${l}" "${REPO_ROOT}/${RESTORE_SH}"
        assert_output "1"
    done
    for l in "Write-DaafRestoreRemoveHint -Lead '' -Volumes (\$LeftoverVolumes -join ' ')" \
             "Write-DaafRestoreRemoveHint -Lead '       ' -Volumes (\$LeftoverVolumes -join ' ')" \
             'Write-DaafRestoreRemoveHint -Lead $Lead -Volumes (Get-DaafRestoreKeptTempList)' \
             "Write-DaafRestoreRemoveHint -Lead '         ' -Volumes \$KeptTemps" \
             "if (\$LeftoverSaid -ne '') { Write-Host \"       Docker said: \$LeftoverSaid\" }" \
             'foreach ($noteLine in $TempRemoveNote) { Write-Host "         $noteLine" }'; do
        run grep -cF -- "${l}" "${REPO_ROOT}/${RESTORE_PS1}"
        assert_output "1"
    done
    # The kept-temp block replaced the old two lines at every site: .sh 1 at indent 7
    # (_restore_fail_before_swap) + 3 unindented (interrupt, EXIT handler, cancel); .ps1 1
    # + 2 (its finally covers both the interrupt and the unexpected exit; cancel).
    run grep -cF '_restore_kept_temp_hint "       " >&2' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run grep -cF '_restore_kept_temp_hint ""' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "3"
    run grep -cF "Write-DaafRestoreKeptTempHint -Lead '       '" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "1"
    run grep -cF "Write-DaafRestoreKeptTempHint -Lead ''" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "2"
}

# Exit 0 (no output) when both twins' removal helper has the D1 shape. ($1 = .sh, $2 = .ps1)
_d1_argv_guarded() {
    local rc=0 b
    b="$(_fn_body_sh "$1" _restore_remove_volume)"
    [ -n "${b}" ] || { echo "sh: _restore_remove_volume not found"; return 1; }
    # The holder list (exit code captured, never `|| true`) and its stderr re-read.
    [ "$(printf '%s\n' "${b}" | grep -cF "docker ps -a --filter \"volume=\$1\" --format '{{.ID}} {{.State}}'")" -eq 2 ] || { echo "sh: expected the holder list twice (list + stderr re-read)"; rc=1; }
    printf '%s\n' "${b}" | grep -qF -- "--format '{{.ID}} {{.State}}' 2>/dev/null)\" || status=\$?" || { echo "sh: the holder list must read stdout only and capture its exit code"; rc=1; }
    printf '%s\n' "${b}" | grep -qxF '            return 3' || { echo "sh: a failed list must return 3 (could not check)"; rc=1; }
    printf '%s\n' "${b}" | grep -qxF '                created|exited|dead) ids="${ids:+${ids} }${id}" ;;' || { echo "sh: only created|exited|dead may be removable"; rc=1; }
    printf '%s\n' "${b}" | grep -qxF '                *) return 2 ;;' || { echo "sh: any other state must be busy (2)"; rc=1; }
    [ "$(printf '%s\n' "${b}" | grep -cF 'docker rm "${id}"')" -eq 1 ] || { echo "sh: expected one plain docker rm of a holder"; rc=1; }
    if printf '%s\n' "${b}" | grep -qE 'rm -f|--force'; then echo "sh: a holder must never be force-removed"; rc=1; fi
    printf '%s\n' "${b}" | grep -qxF '    if [ "${2:-}" != careful ]; then' || { echo "sh: careful mode must skip the holders"; rc=1; }
    printf '%s\n' "${b}" | grep -qxF '    if [ "$1" != "${TEMP_VOLUME_NAME}" ] && [ "$1" != "${CLAUDE_TEMP_VOLUME_NAME}" ]; then return 1; fi' || { echo "sh: no temp-name guard"; rc=1; }
    # Every temp-volume removal in the script goes through the helper.
    [ "$(grep -cE '^[^#]*docker volume rm "' "$1")" -eq 1 ] || { echo "sh: a docker volume rm outside _restore_remove_volume"; rc=1; }
    b="$(_fn_body_ps1 "$2" Invoke-DaafRestoreVolumeRemoval)"
    [ -n "${b}" ] || { echo "ps1: Invoke-DaafRestoreVolumeRemoval not found"; return 1; }
    printf '%s\n' "${b}" | grep -qF "Invoke-DaafRestoreDockerSplit -DockerArgs @('ps', '-a', '--filter', \"volume=\$Name\", '--format', '{{.ID}} {{.State}}')" || { echo "ps1: the holder list argv"; rc=1; }
    printf '%s\n' "${b}" | grep -qF 'foreach ($line in $holders.Out) {' || { echo "ps1: holders must come from stdout (Out) only"; rc=1; }
    printf '%s\n' "${b}" | grep -qF "return [pscustomobject]@{ Result = 'listfailed';" || { echo "ps1: a failed list must be listfailed"; rc=1; }
    printf '%s\n' "${b}" | grep -qF "if (@('created', 'exited', 'dead') -notcontains \$state) {" || { echo "ps1: only created|exited|dead may be removable"; rc=1; }
    [ "$(printf '%s\n' "${b}" | grep -cF "Invoke-DaafRestoreDockerSplit -DockerArgs @('rm', \$id)")" -eq 1 ] || { echo "ps1: expected one plain docker rm of a holder"; rc=1; }
    if printf '%s\n' "${b}" | grep -qE "'-f'|--force"; then echo "ps1: a holder must never be force-removed"; rc=1; fi
    printf '%s\n' "${b}" | grep -qF 'if (-not $KeepHolders) {' || { echo "ps1: careful mode must skip the holders"; rc=1; }
    printf '%s\n' "${b}" | grep -qF 'if (@($TempVolumeName, $ClaudeTempVolumeName) -cnotcontains $Name) {' || { echo "ps1: no temp-name guard"; rc=1; }
    [ "$(grep -cF "@('volume', 'rm'," "$2")" -eq 1 ] || { echo "ps1: a volume rm outside Invoke-DaafRestoreVolumeRemoval"; rc=1; }
    # Careful cleanup is wired to both temps in both twins.
    [ "$(grep -cF '_restore_remove_volume "${TEMP_VOLUME_NAME}" "${rm_mode}"' "$1")" -eq 1 ] && [ "$(grep -cF '_restore_remove_volume "${CLAUDE_TEMP_VOLUME_NAME}" "${rm_mode}"' "$1")" -eq 1 ] && grep -qxF '        rm_mode=careful' "$1" || { echo "sh: careful cleanup not wired to both temps"; rc=1; }
    [ "$(grep -cF -- '-KeepHolders:$script:TempCleanupCareful' "$2")" -eq 2 ] || { echo "ps1: careful cleanup not wired to both temps"; rc=1; }
    return "${rc}"
}

@test "twin-parity D1: both twins list holders with ps -a --filter volume= '{{.ID}} {{.State}}' and remove only stopped ones with a PLAIN rm" {
    run _d1_argv_guarded "${REPO_ROOT}/${RESTORE_SH}" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_success
    assert_output ""
}

# The line numbers of the leftover path's check pass, label reap and swap-container rm
# in one twin must increase in that order. ($1 = file, $2..$4 = the three exact lines)
_in_order() {
    local a b c
    a="$(grep -nxF -- "$2" "$1" | cut -d: -f1)"
    b="$(grep -nxF -- "$3" "$1" | cut -d: -f1)"
    c="$(grep -nF -- "$4" "$1" | cut -d: -f1)"
    [ "$(printf '%s\n' "${a}" | grep -c .)" -eq 1 ] && [ "$(printf '%s\n' "${b}" | grep -c .)" -eq 1 ] && [ "$(printf '%s\n' "${c}" | grep -c .)" -eq 1 ] || { echo "anchor not unique in ${1##*/}: ${a}/${b}/${c}"; return 1; }
    [ "${a}" -lt "${b}" ] && [ "${b}" -lt "${c}" ] || { echo "order in ${1##*/}: check ${a}, reap ${b}, rm ${c}"; return 1; }
}

@test "twin-parity D1: on the leftover path both twins check every holder BEFORE the label reap and the swap-container rm" {
    run _in_order "${REPO_ROOT}/${RESTORE_SH}" \
        '        _restore_remove_volume "${tv}" check || RM_STATUS=$?' \
        '    _restore_reap_helpers' \
        'RM_SAID="$(docker rm "${sc}" 2>&1 > /dev/null)"'
    assert_success
    # The check pass refuses at once (nothing removed) on busy or a failed list.
    run grep -cxF '        if [ "${RM_STATUS}" -ne 0 ]; then _restore_leftover_refusal "${tv}" "${RM_STATUS}"; fi' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run _in_order "${REPO_ROOT}/${RESTORE_PS1}" \
        '        $leftoverCheck = Invoke-DaafRestoreVolumeRemoval -Name $tv -CheckOnly' \
        '    Invoke-DaafRestoreHelperReap' \
        "\$scRemoval = Invoke-DaafRestoreDockerSplit -DockerArgs @('rm', \$sc)"
    assert_success
}

# Review round 6 (R5): the leftover swap containers -- found NOT running before an
# unbounded y/n wait -- are removed with a PLAIN `docker rm` in both twins (the daemon
# refuses a running one without -f, so another window's swap started meanwhile under the
# same name survives); a failed removal skips the volume removal; and the manual hint
# prints the same plain command. Fix round 8 (delta review of round 7, ISSUE 1): in both
# twins a "No such container" failure of that rm (the container vanished meanwhile)
# counts as removed, through the shared not-found classifier, as the FIRST statement
# of the failure branch. Exit 0 (no output) when both twins have that shape.
# ($1 = .sh, $2 = .ps1)
_r5_swap_rm_plain() {
    local rc=0
    [ "$(grep -cF 'RM_SAID="$(docker rm "${sc}" 2>&1 > /dev/null)"' "$1")" -eq 1 ] || { echo "sh: expected one plain docker rm of a leftover swap container"; rc=1; }
    grep -A1 -F 'if ! RM_SAID="$(docker rm "${sc}" 2>&1 > /dev/null)"; then' "$1" | grep -qxF '            if _restore_is_not_found "${RM_SAID}"; then continue; fi' || { echo "sh: a vanished leftover swap container (No such container) must count as removed"; rc=1; }
    [ "$(grep -A2 -F "\$scRemoval = Invoke-DaafRestoreDockerSplit -DockerArgs @('rm', \$sc)" "$2" | sed -n '2,3p')" = "$(printf '%s\n' '        if ($scRemoval.Exit -ne 0) {' '            if (Test-DaafRestoreNotFound -Lines $scRemoval.Err) { continue }')" ] || { echo "ps1: a vanished leftover swap container (No such container) must count as removed"; rc=1; }
    if grep -E '^[^#]*docker rm (-f|--force) "\$\{sc\}"' "$1" > /dev/null; then echo "sh: a leftover swap container must never be force-removed"; rc=1; fi
    grep -qxF '    if [ "${LEFTOVER_FAILED}" -eq 0 ]; then' "$1" || { echo "sh: a failed swap-container rm must skip the volume removal"; rc=1; }
    [ "$(grep -cF 'echo "         docker rm ${LEFTOVER_CONTAINERS}" >&2' "$1")" -eq 1 ] || { echo "sh: the leftover-failure hint must print a plain docker rm"; rc=1; }
    [ "$(grep -cF "Invoke-DaafRestoreDockerSplit -DockerArgs @('rm', \$sc)" "$2")" -eq 1 ] || { echo "ps1: expected one plain docker rm of a leftover swap container"; rc=1; }
    if grep -E "^[^#]*@\('rm', '(-f|--force)', \\\$sc\)" "$2" > /dev/null; then echo "ps1: a leftover swap container must never be force-removed"; rc=1; fi
    grep -qxF '    if (-not $LeftoverFailed) {' "$2" || { echo "ps1: a failed swap-container rm must skip the volume removal"; rc=1; }
    [ "$(grep -cF "Write-Host \"         docker rm \$(\$LeftoverContainers -join ' ')\"" "$2")" -eq 1 ] || { echo "ps1: the leftover-failure hint must print a plain docker rm"; rc=1; }
    # No forced removal hint is printed anywhere in either twin.
    if grep -E '^[^#]*(echo|Write-Host) "[^"]*docker rm -f' "$1" "$2" > /dev/null; then echo "a printed 'docker rm -f' hint remains"; rc=1; fi
    return "${rc}"
}

@test "twin-parity R5: both twins remove a leftover swap container with a PLAIN docker rm, count a vanished one as removed, skip the volumes when it fails, and print a plain hint" {
    run _r5_swap_rm_plain "${REPO_ROOT}/${RESTORE_SH}" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_success
    assert_output ""
}

@test "twin-parity R5 SELF-TEST: the pin flags a forced swap-container rm (either twin) and a forced hint" {
    sed 's/RM_SAID="\$(docker rm "\${sc}"/RM_SAID="$(docker rm -f "${sc}"/' "${REPO_ROOT}/${RESTORE_SH}" > "${TEST_DIR}/r5force.sh"
    run cmp -s "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/r5force.sh"
    assert_failure
    run _r5_swap_rm_plain "${TEST_DIR}/r5force.sh" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_failure
    assert_output --partial "sh: a leftover swap container must never be force-removed"
    sed "s/@('rm', \\\$sc)/@('rm', '-f', \$sc)/" "${REPO_ROOT}/${RESTORE_PS1}" > "${TEST_DIR}/r5force.ps1"
    run cmp -s "${REPO_ROOT}/${RESTORE_PS1}" "${TEST_DIR}/r5force.ps1"
    assert_failure
    run _r5_swap_rm_plain "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/r5force.ps1"
    assert_failure
    assert_output --partial "ps1: a leftover swap container must never be force-removed"
    sed 's/echo "         docker rm \${LEFTOVER_CONTAINERS}"/echo "         docker rm -f ${LEFTOVER_CONTAINERS}"/' "${REPO_ROOT}/${RESTORE_SH}" > "${TEST_DIR}/r5hint.sh"
    run cmp -s "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/r5hint.sh"
    assert_failure
    run _r5_swap_rm_plain "${TEST_DIR}/r5hint.sh" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_failure
    assert_output --partial "a printed 'docker rm -f' hint remains"
}

@test "twin-parity R8 SELF-TEST: the pin flags a twin that no longer counts a vanished swap container as removed" {
    grep -vxF '            if _restore_is_not_found "${RM_SAID}"; then continue; fi' "${REPO_ROOT}/${RESTORE_SH}" > "${TEST_DIR}/r8gone.sh" || true
    run cmp -s "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/r8gone.sh"
    assert_failure
    run _r5_swap_rm_plain "${TEST_DIR}/r8gone.sh" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_failure
    assert_output "sh: a vanished leftover swap container (No such container) must count as removed"
    grep -vxF '            if (Test-DaafRestoreNotFound -Lines $scRemoval.Err) { continue }' "${REPO_ROOT}/${RESTORE_PS1}" > "${TEST_DIR}/r8gone.ps1" || true
    run cmp -s "${REPO_ROOT}/${RESTORE_PS1}" "${TEST_DIR}/r8gone.ps1"
    assert_failure
    run _r5_swap_rm_plain "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/r8gone.ps1"
    assert_failure
    assert_output "ps1: a vanished leftover swap container (No such container) must count as removed"
}

@test "twin-parity D3: both twins set the Claude-phase flag once, after the data swap's check and before 'Replacing the Claude Code state...'" {
    run _in_order "${REPO_ROOT}/${RESTORE_SH}" \
        'if ! _restore_swap_checked "${SWAP_VERIFY_OUTPUT}" nonempty; then' \
        '    CLAUDE_SWAP_PHASE=1' \
        'echo "Replacing the Claude Code state..."'
    assert_success
    run grep -cE '^[[:space:]]*CLAUDE_SWAP_PHASE=1$' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run grep -cxF '        if [ "${CLAUDE_SWAP_PHASE}" -eq 1 ]; then' "${REPO_ROOT}/${RESTORE_SH}"
    assert_output "1"
    run _in_order "${REPO_ROOT}/${RESTORE_PS1}" \
        '        if (-not (Test-DaafRestoreSwapChecked -Lines $swapCheck -NonEmpty)) {' \
        '            $ClaudeSwapPhase = $true' \
        'Write-Host "Replacing the Claude Code state..."'
    assert_success
    run grep -cE '^[[:space:]]*\$ClaudeSwapPhase = \$true$' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "1"
    run grep -cxF '            if ($ClaudeSwapPhase) {' "${REPO_ROOT}/${RESTORE_PS1}"
    assert_output "1"
}

@test "twin-parity SELF-TEST: the D1/D3 pins flag a reworded string, a forced holder rm, a live state taken as stopped, and a moved flag" {
    # (a) one twin's new string reworded
    sed 's/another restore may still be running\./another restore may be running./' "${REPO_ROOT}/${RESTORE_PS1}" > "${TEST_DIR}/word.ps1"
    run cmp -s "${REPO_ROOT}/${RESTORE_PS1}" "${TEST_DIR}/word.ps1"
    assert_failure
    run _d1_d3_strings_pinned "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/word.ps1"
    assert_failure
    assert_output --partial "MISSING in word.ps1: Something is still using it; another restore may still be running."
    # (b) a holder force-removed (.sh)
    sed 's/said="\$(docker rm "\${id}"/said="$(docker rm -f "${id}"/' "${REPO_ROOT}/${RESTORE_SH}" > "${TEST_DIR}/force.sh"
    run cmp -s "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/force.sh"
    assert_failure
    run _d1_argv_guarded "${TEST_DIR}/force.sh" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_failure
    assert_output --partial "sh: a holder must never be force-removed"
    # (c) a running holder taken as removable (.ps1)
    sed "s/@('created', 'exited', 'dead') -notcontains/@('created', 'exited', 'dead', 'running') -notcontains/" "${REPO_ROOT}/${RESTORE_PS1}" > "${TEST_DIR}/live.ps1"
    run cmp -s "${REPO_ROOT}/${RESTORE_PS1}" "${TEST_DIR}/live.ps1"
    assert_failure
    run _d1_argv_guarded "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/live.ps1"
    assert_failure
    assert_output --partial "ps1: only created|exited|dead may be removable"
    # (d) the D3 flag set too late (after the Claude swap message) in the .sh
    awk '/^    CLAUDE_SWAP_PHASE=1$/ { held = $0; next } { print } /echo "Replacing the Claude Code state..."/ && held != "" { print held; held = "" }' "${REPO_ROOT}/${RESTORE_SH}" > "${TEST_DIR}/late.sh"
    run cmp -s "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/late.sh"
    assert_failure
    run _in_order "${TEST_DIR}/late.sh" \
        'if ! _restore_swap_checked "${SWAP_VERIFY_OUTPUT}" nonempty; then' \
        '    CLAUDE_SWAP_PHASE=1' \
        'echo "Replacing the Claude Code state..."'
    assert_failure
}

# ===========================================================================
# 15. TASK #36 (review 32q, I-3): a temp created just before a Ctrl+C
# ===========================================================================
# Both twins record a temp's create ATTEMPT right before its `docker volume create` and
# close it right after the created flag; the cleanup adopts a still-open attempt ONLY
# when the volume carries this run's identity label (.sh _restore_adopt_attempted_temps
# / .ps1 Resolve-DaafRestoreAttemptedTemp), and the new-temp check's refusal closes the
# attempt first. Pinned here: the flag set/clear sites, the helper bodies and their
# place in the cleanup, the refusal close, and the two .ps1 SYNC NOTEs -- by STRUCTURE
# where the twins legitimately differ (the .sh closes the refused attempt inside
# _restore_check_new_temp, the .ps1 at both call sites; the .sh also adopts from its
# EXIT handler, the .ps1 finally covers every exit). Behaviour: restore_from_backup.bats
# ("32q I-3:") and restore_from_backup.Tests.ps1.

# The line BEFORE each code (non-comment) line of file $1 containing fixed string $2.
_i3_line_before() {
    awk -v s="$2" 'index($0, s) && $0 !~ /^[[:space:]]*#/ { print prev } { prev = $0 }' "$1"
}

# The line AFTER each line of file $1 that is exactly $2.
_i3_line_after() {
    awk -v s="$2" 'hit { print; hit = 0 } $0 == s { hit = 1 }' "$1"
}

# The comment lines directly above the first line of file $1 that is exactly $2.
_i3_comment_above() {
    awk -v s="$2" '$0 == s { printf "%s", buf; exit } /^[[:space:]]*#/ { buf = buf $0 "\n"; next } { buf = "" }' "$1"
}

# Exit 0 (no output) when both twins have the task #36 shape. ($1 = .sh, $2 = .ps1)
_i3_attempt_guarded() {
    local rc=0 b
    # --- .sh: set right before each create, cleared right after each created flag ---
    [ "$(_i3_line_before "$1" 'docker volume create')" = "$(printf '%s\n' 'TEMP_CREATE_ATTEMPTED=1' '    CLAUDE_TEMP_CREATE_ATTEMPTED=1')" ] || { echo "sh: each temp's attempt flag must be set on the line right before its docker volume create"; rc=1; }
    [ "$(_i3_line_after "$1" 'TEMP_CREATED=1')" = 'TEMP_CREATE_ATTEMPTED=0' ] || { echo "sh: TEMP_CREATE_ATTEMPTED=0 must follow TEMP_CREATED=1"; rc=1; }
    [ "$(_i3_line_after "$1" '    CLAUDE_TEMP_CREATED=1')" = '    CLAUDE_TEMP_CREATE_ATTEMPTED=0' ] || { echo "sh: CLAUDE_TEMP_CREATE_ATTEMPTED=0 must follow CLAUDE_TEMP_CREATED=1"; rc=1; }
    [ "$(grep -cE '^[[:space:]]*(CLAUDE_)?TEMP_CREATE_ATTEMPTED=1$' "$1")" -eq 2 ] || { echo "sh: expected exactly two attempt-flag sets"; rc=1; }
    # --- .sh: the helper (identity-gated, both temps, both flags cleared) ---
    b="$(_fn_body_sh "$1" _restore_adopt_attempted_temps)"
    [ "${b}" = "$(printf '%s\n' \
        '_restore_adopt_attempted_temps() {' \
        '    if [ "${TEMP_CREATE_ATTEMPTED}" -eq 1 ] && [ "${TEMP_CREATED}" -eq 0 ] && _restore_temp_is_ours "${TEMP_VOLUME_NAME}"; then TEMP_CREATED=1; fi' \
        '    TEMP_CREATE_ATTEMPTED=0' \
        '    if [ "${CLAUDE_TEMP_CREATE_ATTEMPTED}" -eq 1 ] && [ "${CLAUDE_TEMP_CREATED}" -eq 0 ] && _restore_temp_is_ours "${CLAUDE_TEMP_VOLUME_NAME}"; then CLAUDE_TEMP_CREATED=1; fi' \
        '    CLAUDE_TEMP_CREATE_ATTEMPTED=0' \
        '}')" ] || { echo "sh: _restore_adopt_attempted_temps must adopt each open attempt only through _restore_temp_is_ours and clear both flags"; rc=1; }
    # --- .sh: called in the cleanup after the swap-started guard and the note reset,
    # before the careful branch; and from the EXIT handler (no cleanup tried yet) ---
    b="$(_fn_body_sh "$1" _restore_remove_temps | grep -nxF \
        -e '    if [ "${SWAP_STARTED}" -eq 1 ] && [ "${1:-}" != "final" ]; then return 0; fi' \
        -e '    TEMP_REMOVE_NOTE=""' \
        -e '    _restore_adopt_attempted_temps' \
        -e '    if [ "${TEMP_CLEANUP_CAREFUL}" -eq 1 ]; then' | cut -d: -f2-)"
    [ "${b}" = "$(printf '%s\n' \
        '    if [ "${SWAP_STARTED}" -eq 1 ] && [ "${1:-}" != "final" ]; then return 0; fi' \
        '    TEMP_REMOVE_NOTE=""' \
        '    _restore_adopt_attempted_temps' \
        '    if [ "${TEMP_CLEANUP_CAREFUL}" -eq 1 ]; then')" ] || { echo "sh: _restore_remove_temps must call _restore_adopt_attempted_temps once, after its note reset and before the careful branch"; rc=1; }
    _fn_body_sh "$1" _restore_on_exit | grep -A1 -xF '    if [ "${SWAP_STARTED}" -eq 0 ] && [ "${TEMP_CLEANUP_TRIED}" -eq 0 ]; then _restore_adopt_attempted_temps; fi' | tail -n 1 | grep -qF '&& [ -n "$(_restore_kept_temps)" ]; then' || { echo "sh: the EXIT handler must adopt open attempts right before it looks for kept temps"; rc=1; }
    [ "$(grep -E '^[[:space:]]*[^#[:space:]]' "$1" | grep -cF '_restore_adopt_attempted_temps')" -eq 3 ] ||{ echo "sh: expected the helper definition plus exactly two calls (cleanup, EXIT handler)"; rc=1; }
    # --- .sh: the refusal closes the attempt, after the verdict and before its cleanup ---
    b="$(_fn_body_sh "$1" _restore_check_new_temp | grep -nxF \
        -e '    if [ "${status}" -eq 0 ] && [ -z "${listing}" ] && _restore_temp_is_ours "$1"; then return 0; fi' \
        -e '    if [ "$1" = "${TEMP_VOLUME_NAME}" ]; then TEMP_CREATE_ATTEMPTED=0; else CLAUDE_TEMP_CREATE_ATTEMPTED=0; fi' \
        -e "    _restore_fail_before_swap \"ERROR: Could not confirm that the new temporary Docker volume '\$1' is empty\" \\" | cut -d: -f2-)"
    [ "${b}" = "$(printf '%s\n' \
        '    if [ "${status}" -eq 0 ] && [ -z "${listing}" ] && _restore_temp_is_ours "$1"; then return 0; fi' \
        '    if [ "$1" = "${TEMP_VOLUME_NAME}" ]; then TEMP_CREATE_ATTEMPTED=0; else CLAUDE_TEMP_CREATE_ATTEMPTED=0; fi' \
        "    _restore_fail_before_swap \"ERROR: Could not confirm that the new temporary Docker volume '\$1' is empty\" \\")" ] || { echo "sh: _restore_check_new_temp must close the attempt of the temp it refuses, after its verdict and before _restore_fail_before_swap"; rc=1; }
    # --- .ps1: the same set/clear sites ---
    [ "$(_i3_line_before "$2" "@('volume', 'create',")" = "$(printf '%s\n' '        $TempCreateAttempted = $true' '            $ClaudeTempCreateAttempted = $true')" ] || { echo "ps1: each temp's attempt flag must be set on the line right before its volume create"; rc=1; }
    [ "$(_i3_line_after "$2" '        $TempCreated = $true')" = '        $TempCreateAttempted = $false' ] || { echo "ps1: \$TempCreateAttempted = \$false must follow \$TempCreated = \$true"; rc=1; }
    [ "$(_i3_line_after "$2" '            $ClaudeTempCreated = $true')" = '            $ClaudeTempCreateAttempted = $false' ] || { echo "ps1: \$ClaudeTempCreateAttempted = \$false must follow \$ClaudeTempCreated = \$true"; rc=1; }
    [ "$(grep -cE '^[[:space:]]*\$(Claude)?TempCreateAttempted = \$true$' "$2")" -eq 2 ] || { echo "ps1: expected exactly two attempt-flag sets"; rc=1; }
    # --- .ps1: the helper and its ONE caller, the cleanup (which the finally runs) ---
    b="$(_fn_body_ps1 "$2" Resolve-DaafRestoreAttemptedTemp)"
    [ "${b}" = "$(printf '%s\n' \
        'function Resolve-DaafRestoreAttemptedTemp {' \
        '    [CmdletBinding()]' \
        '    param()' \
        '    if ($script:TempCreateAttempted -and -not $script:TempCreated -and (Test-DaafRestoreTempIdentity -Name $TempVolumeName)) { $script:TempCreated = $true }' \
        '    $script:TempCreateAttempted = $false' \
        '    if ($script:ClaudeTempCreateAttempted -and -not $script:ClaudeTempCreated -and (Test-DaafRestoreTempIdentity -Name $ClaudeTempVolumeName)) { $script:ClaudeTempCreated = $true }' \
        '    $script:ClaudeTempCreateAttempted = $false' \
        '}')" ] || { echo "ps1: Resolve-DaafRestoreAttemptedTemp must adopt each open attempt only through Test-DaafRestoreTempIdentity and clear both flags"; rc=1; }
    b="$(_fn_body_ps1 "$2" Invoke-DaafRestoreTempCleanup | grep -nxF \
        -e '    if ($script:SwapStarted -and -not $Final) { return }' \
        -e '    $script:TempRemoveNote = @()' \
        -e '    Resolve-DaafRestoreAttemptedTemp' \
        -e '    if ($script:TempCleanupCareful) {' | cut -d: -f2-)"
    [ "${b}" = "$(printf '%s\n' \
        '    if ($script:SwapStarted -and -not $Final) { return }' \
        '    $script:TempRemoveNote = @()' \
        '    Resolve-DaafRestoreAttemptedTemp' \
        '    if ($script:TempCleanupCareful) {')" ] || { echo "ps1: Invoke-DaafRestoreTempCleanup must call Resolve-DaafRestoreAttemptedTemp once, after its note reset and before the careful branch"; rc=1; }
    [ "$(grep -E '^[[:space:]]*[^#[:space:]]' "$2" | grep -cF 'Resolve-DaafRestoreAttemptedTemp')" -eq 2 ] ||{ echo "ps1: expected the helper definition plus exactly one call (the cleanup)"; rc=1; }
    grep -qxF '    if (-not $SwapStarted -and $null -eq $ChangedTemp) { Invoke-DaafRestoreTempCleanup }' "$2" || { echo "ps1: the finally must run Invoke-DaafRestoreTempCleanup before any swap"; rc=1; }
    # --- .ps1: both refusal sites close the attempt as their FIRST statement ---
    [ "$(grep -cE '^[[:space:]]*if \(-not \(Test-DaafRestoreNewTemp ' "$2")" -eq 2 ] || { echo "ps1: expected exactly two new-temp check sites"; rc=1; }
    grep -qF 'if (-not (Test-DaafRestoreNewTemp -Name $TempVolumeName -Live $VolumeName)) { $TempCreateAttempted = $false; $PrepFail = ' "$2" || { echo "ps1: the data refusal must close its attempt first"; rc=1; }
    grep -qF 'if (-not (Test-DaafRestoreNewTemp -Name $ClaudeTempVolumeName -Live $ClaudeVolumeName)) { $ClaudeTempCreateAttempted = $false; $PrepFail = ' "$2" || { echo "ps1: the Claude refusal must close its attempt first"; rc=1; }
    # --- the two .ps1 SYNC NOTEs: present, attached to their construct, naming the .sh
    # counterpart (whose shape is pinned above) ---
    b="$(_i3_comment_above "$2" 'function Resolve-DaafRestoreAttemptedTemp {')"
    printf '%s\n' "${b}" | grep -q '^# SYNC NOTE: the \.sh twin also calls it from its EXIT handler' || { echo "ps1: the SYNC NOTE on the .sh EXIT-handler call must sit right above Resolve-DaafRestoreAttemptedTemp"; rc=1; }
    printf '%s\n' "${b}" | grep -qF "finally's Invoke-DaafRestoreTempCleanup covers every exit from the try." || { echo "ps1: that SYNC NOTE must say the finally's cleanup covers every exit"; rc=1; }
    printf '%s\n' "${b}" | sed -E 's/^[[:space:]]*# ?//' | tr '\n' ' ' | grep -qF "The .sh twin's _restore_adopt_attempted_temps." || { echo "ps1: Resolve-DaafRestoreAttemptedTemp must name its .sh twin"; rc=1; }
    b="$(_i3_comment_above "$2" "$(grep -F 'if (-not (Test-DaafRestoreNewTemp -Name $TempVolumeName ' "$2" | head -n 1)")"
    printf '%s' "${b}" | sed -E 's/^[[:space:]]*# ?//' | tr '\n' ' ' | grep -qF '(SYNC NOTE: the .sh twin closes it inside _restore_check_new_temp, whose refusal also runs the cleanup and exits.)' || { echo "ps1: the SYNC NOTE on the .sh refusal close must sit right above the data refusal"; rc=1; }
    return "${rc}"
}

@test "twin-parity 32q I-3: both twins open a temp's create attempt right before the create, close it after the created flag or on a refusal, and adopt it only by identity" {
    run _i3_attempt_guarded "${REPO_ROOT}/${RESTORE_SH}" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_success
    assert_output ""
}

@test "twin-parity 32q I-3 SELF-TEST: the pin flags a moved set, a missing clear, a dropped adoption or identity gate, an open refusal, and a lost SYNC NOTE (or its .sh counterpart)" {
    local f
    # (a) .sh: the data set moved below the create (just before the check)
    awk '$0 == "TEMP_CREATE_ATTEMPTED=1" { next } $0 == "_restore_check_new_temp \"${TEMP_VOLUME_NAME}\" \"${VOLUME_NAME}\"" { print "TEMP_CREATE_ATTEMPTED=1" } { print }' "${REPO_ROOT}/${RESTORE_SH}" > "${TEST_DIR}/a.sh"
    # (b) .ps1: the Claude clear removed
    grep -vxF '            $ClaudeTempCreateAttempted = $false' "${REPO_ROOT}/${RESTORE_PS1}" > "${TEST_DIR}/b.ps1" || true
    # (c) .sh: the adoption dropped from the cleanup
    grep -vxF '    _restore_adopt_attempted_temps' "${REPO_ROOT}/${RESTORE_SH}" > "${TEST_DIR}/c.sh" || true
    # (d) .ps1: the Claude refusal no longer closes its attempt
    sed 's/ { \$ClaudeTempCreateAttempted = \$false; \$PrepFail = / { $PrepFail = /' "${REPO_ROOT}/${RESTORE_PS1}" > "${TEST_DIR}/d.ps1"
    # (e) .ps1: the EXIT-handler SYNC NOTE removed
    grep -vF '# SYNC NOTE: the .sh twin also calls it from its EXIT handler' "${REPO_ROOT}/${RESTORE_PS1}" > "${TEST_DIR}/e.ps1" || true
    # (f) .sh: the EXIT handler no longer adopts (that SYNC NOTE's counterpart is gone)
    grep -vxF '    if [ "${SWAP_STARTED}" -eq 0 ] && [ "${TEMP_CLEANUP_TRIED}" -eq 0 ]; then _restore_adopt_attempted_temps; fi' "${REPO_ROOT}/${RESTORE_SH}" > "${TEST_DIR}/f.sh" || true
    # (g) .ps1: the data adoption without the identity gate
    sed 's/ -and -not \$script:TempCreated -and (Test-DaafRestoreTempIdentity -Name \$TempVolumeName)) / -and -not $script:TempCreated) /' "${REPO_ROOT}/${RESTORE_PS1}" > "${TEST_DIR}/g.ps1"
    # (h) .sh: the refusal close removed
    grep -vxF '    if [ "$1" = "${TEMP_VOLUME_NAME}" ]; then TEMP_CREATE_ATTEMPTED=0; else CLAUDE_TEMP_CREATE_ATTEMPTED=0; fi' "${REPO_ROOT}/${RESTORE_SH}" > "${TEST_DIR}/h.sh" || true
    for f in a.sh c.sh f.sh h.sh; do
        run cmp -s "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/${f}"
        assert_failure
    done
    for f in b.ps1 d.ps1 e.ps1 g.ps1; do
        run cmp -s "${REPO_ROOT}/${RESTORE_PS1}" "${TEST_DIR}/${f}"
        assert_failure
    done
    run _i3_attempt_guarded "${TEST_DIR}/a.sh" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_failure
    assert_output "sh: each temp's attempt flag must be set on the line right before its docker volume create"
    run _i3_attempt_guarded "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/b.ps1"
    assert_failure
    assert_output "ps1: \$ClaudeTempCreateAttempted = \$false must follow \$ClaudeTempCreated = \$true"
    run _i3_attempt_guarded "${TEST_DIR}/c.sh" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_failure
    assert_output --partial "sh: _restore_remove_temps must call _restore_adopt_attempted_temps once"
    run _i3_attempt_guarded "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/d.ps1"
    assert_failure
    assert_output "ps1: the Claude refusal must close its attempt first"
    run _i3_attempt_guarded "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/e.ps1"
    assert_failure
    assert_output --partial "ps1: the SYNC NOTE on the .sh EXIT-handler call must sit right above Resolve-DaafRestoreAttemptedTemp"
    run _i3_attempt_guarded "${TEST_DIR}/f.sh" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_failure
    assert_output --partial "sh: the EXIT handler must adopt open attempts right before it looks for kept temps"
    run _i3_attempt_guarded "${REPO_ROOT}/${RESTORE_SH}" "${TEST_DIR}/g.ps1"
    assert_failure
    assert_output "ps1: Resolve-DaafRestoreAttemptedTemp must adopt each open attempt only through Test-DaafRestoreTempIdentity and clear both flags"
    run _i3_attempt_guarded "${TEST_DIR}/h.sh" "${REPO_ROOT}/${RESTORE_PS1}"
    assert_failure
    assert_output "sh: _restore_check_new_temp must close the attempt of the temp it refuses, after its verdict and before _restore_fail_before_swap"
}

# ===========================================================================
# F1 (fix pass #26): pinned helper image, version/image checks, PS hardening
# ===========================================================================
# research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/scoping/04_F1_compat_audit.md:
# the untagged `busybox` moved to the untested 1.38.0, so ONE digest-pinned string lives
# in 7 places (the BUSYBOX_IMAGE / $BusyboxImage constant of backup, restore and migrate
# .sh + .ps1, and docker-compose.yml's daaf-init image:). The backup/restore twins share
# a startup Docker version check and a helper-image check whose user-facing text must be
# verbatim identical (script name varied), and both Windows twins carry the PowerShell 7
# hardening line and an edition guard that runs before any docker call. The bats runtime
# tests exercise the .sh twins; these source pins are what cover the .ps1 twins here.

MIGRATE_SH="scripts/host/migrate_daaf.sh"
MIGRATE_PS1="scripts/host/migrate_daaf.ps1"
COMPOSE_YML="docker-compose.yml"

# "<place> <value>" for every definition of the pinned string under root $1 (one line
# per definition, so a duplicate constant shows up as an extra line).
_busybox_pin_places() {
    local root="$1" f
    for f in "${BACKUP_SH}" "${RESTORE_SH}" "${MIGRATE_SH}"; do
        sed -n "s|^BUSYBOX_IMAGE='\([^']*\)'\$|${f} \1|p" "${root}/${f}"
    done
    for f in "${BACKUP_PS1}" "${RESTORE_PS1}" "${MIGRATE_PS1}"; do
        sed -n "s|^\$BusyboxImage = '\([^']*\)'\$|${f} \1|p" "${root}/${f}"
    done
    # The daaf-init service's image: (up to the next service or top-level key).
    awk '/^  daaf-init:[[:space:]]*$/ { s = 1; next }
         s && /^  ?[^ #]/ { exit }
         s && /^    image:/ { print "docker-compose.yml(daaf-init) " $2; exit }' "${root}/${COMPOSE_YML}"
}

# The pin check under root $1: exactly 7 definitions, one distinct string, equal to the
# tested DAAF_BUSYBOX_PIN (test_helper.bash), shaped busybox:X.Y.Z@sha256:<64 hex>.
_check_busybox_pin() {
    local places n distinct
    places="$(_busybox_pin_places "$1")"
    n="$(printf '%s\n' "${places}" | grep -c .)" || true
    if [ "${n}" -ne 7 ]; then echo "FAIL: expected 7 pinned-image definitions, found ${n}:"; printf '%s\n' "${places}"; return 1; fi
    distinct="$(printf '%s\n' "${places}" | awk '{ print $2 }' | LC_ALL=C sort -u)"
    if [ "$(printf '%s\n' "${distinct}" | grep -c .)" -ne 1 ]; then
        echo "FAIL: the pinned busybox string differs between places:"; printf '%s\n' "${places}"; return 1
    fi
    if [ "${distinct}" != "${DAAF_BUSYBOX_PIN}" ]; then
        echo "FAIL: the pin ${distinct} is not the tested ${DAAF_BUSYBOX_PIN} (a deliberate change updates tests/bash/test_helper.bash too)"; return 1
    fi
    [[ "${distinct}" =~ ^busybox:[0-9]+\.[0-9]+\.[0-9]+@sha256:[0-9a-f]{64}$ ]] || { echo "FAIL: ${distinct} is not name:tag@sha256:<64 hex>"; return 1; }
}

@test "F1 pin: ONE digest-pinned busybox string, identical in all 7 places (3 .sh + 3 .ps1 constants + compose daaf-init)" {
    run _busybox_pin_places "${REPO_ROOT}"
    printf '%s\n' "${output}"
    run _check_busybox_pin "${REPO_ROOT}"
    assert_success
}

@test "F1 pin: no other busybox reference -- every image use goes through the constant (all 6 scripts, compose)" {
    local f
    # Non-comment lines that name busybox, minus the constant itself and the user-facing
    # "helper image busybox" text: a bare `busybox` image argument (e.g. one reverted
    # call site in a .ps1, which no bats run exercises) shows up here.
    for f in "${BACKUP_SH}" "${BACKUP_PS1}" "${RESTORE_SH}" "${RESTORE_PS1}" "${MIGRATE_SH}" "${MIGRATE_PS1}"; do
        run bash -c "grep -n 'busybox' '${REPO_ROOT}/${f}' | grep -vE '^[0-9]+:[[:space:]]*#' | grep -v \"^[0-9]*:BUSYBOX_IMAGE='\" | grep -v \"^[0-9]*:\\\$BusyboxImage = '\" | grep -vF 'helper image busybox'"
        echo "file=${f}"
        assert_output ""
    done
    # Each script really routes its docker calls through the constant (non-vacuous).
    run grep -c '"${BUSYBOX_IMAGE}"' "${REPO_ROOT}/${MIGRATE_SH}"
    [ "${output}" -ge 1 ]
    run grep -c ' \$BusyboxImage[ ,)]' "${REPO_ROOT}/${MIGRATE_PS1}"
    [ "${output}" -ge 1 ]
    # compose: no service runs another busybox.
    run bash -c "grep -nE '^[[:space:]]*image:[[:space:]]*busybox' '${REPO_ROOT}/${COMPOSE_YML}' | grep -vF -- '${DAAF_BUSYBOX_PIN}'"
    assert_output ""
}

@test "F1 pin SELF-TEST: a digest changed in any ONE of the 7 places, a duplicate constant, or a consistently changed pin all FAIL the check" {
    local target f root="${TEST_DIR}/pin" digest bad
    digest="${DAAF_BUSYBOX_PIN#*@sha256:}"
    # Same length, last hex digit changed.
    case "${digest}" in *0) bad="${digest%?}1" ;; *) bad="${digest%?}0" ;; esac
    for target in "${BACKUP_SH}" "${BACKUP_PS1}" "${RESTORE_SH}" "${RESTORE_PS1}" "${MIGRATE_SH}" "${MIGRATE_PS1}" "${COMPOSE_YML}"; do
        rm -rf "${root}"
        mkdir -p "${root}/scripts/host"
        for f in "${BACKUP_SH}" "${BACKUP_PS1}" "${RESTORE_SH}" "${RESTORE_PS1}" "${MIGRATE_SH}" "${MIGRATE_PS1}" "${COMPOSE_YML}"; do
            cp "${REPO_ROOT}/${f}" "${root}/${f}"
        done
        # The unperturbed copy passes (so a failure below is the perturbation's).
        run _check_busybox_pin "${root}"
        assert_success
        sed -i "s/${digest}/${bad}/" "${root}/${target}"
        run grep -c "${bad}" "${root}/${target}"
        assert_output "1"
        run _check_busybox_pin "${root}"
        echo "perturbed=${target}"
        assert_failure
        assert_output --partial "differs between places"
    done
    # A second definition of the constant in one script: 8 definitions.
    rm -rf "${root}"
    mkdir -p "${root}/scripts/host"
    for f in "${BACKUP_SH}" "${BACKUP_PS1}" "${RESTORE_SH}" "${RESTORE_PS1}" "${MIGRATE_SH}" "${MIGRATE_PS1}" "${COMPOSE_YML}"; do
        cp "${REPO_ROOT}/${f}" "${root}/${f}"
    done
    printf "BUSYBOX_IMAGE='%s'\n" "${DAAF_BUSYBOX_PIN}" >> "${root}/${RESTORE_SH}"
    run _check_busybox_pin "${root}"
    assert_failure
    assert_output --partial "expected 7 pinned-image definitions, found 8"
    # All 7 changed together (a consistent re-pin) still fails against the tested pin.
    for f in "${BACKUP_SH}" "${BACKUP_PS1}" "${RESTORE_SH}" "${RESTORE_PS1}" "${MIGRATE_SH}" "${MIGRATE_PS1}" "${COMPOSE_YML}"; do
        cp "${REPO_ROOT}/${f}" "${root}/${f}"
        sed -i "s/${digest}/${bad}/" "${root}/${f}"
    done
    run _check_busybox_pin "${root}"
    assert_failure
    assert_output --partial "is not the tested"
}

# The two F1 blocks of a backup/restore twin ($1): the version check (its heading up to
# the volume check) and the image check (its heading up to the next `# --- ` heading),
# comment lines dropped.
_f1_blocks() {
    awk '
        /^# --- Docker version check/ { blk = 1 }
        blk == 1 && /docker volume inspect/ { blk = 0 }
        /^# --- Helper image check/ { blk = 2; print; next }
        blk == 2 && /^# --- / { blk = 0 }
        blk { print }
    ' "$1" | grep -v '^[[:space:]]*#'
}

# The user-facing lines of those blocks, in order: every echo "..." / Write-Host "..."
# literal, minus the .ps1's `Write-Host "$_"` (it relays docker pull's own progress, which
# the .sh shows through fd 3). Variables become placeholders: <C>/<S> the client/Engine
# version as read, <C?>/<S?> the same with the "unknown" fallback (.sh ${X:-unknown},
# .ps1 $dockerClientShown), <SAID> Docker's last stderr line. $2 = "name" also replaces
# "the backup" / "the restore" with "the <SCRIPT>" (the one allowed difference).
_f1_messages() {
    _f1_blocks "$1" \
    | sed -n -e 's/^.*echo "\([^"]*\)".*$/\1/p' -e 's/^.*Write-Host "\([^"]*\)".*$/\1/p' \
    | grep -vxF '$_' \
    | sed -e 's/\${DOCKER_CLIENT_VERSION:-unknown}/<C?>/g' -e 's/\${DOCKER_SERVER_VERSION:-unknown}/<S?>/g' \
          -e 's/\${DOCKER_CLIENT_VERSION}/<C>/g' -e 's/\${DOCKER_SERVER_VERSION}/<S>/g' -e 's/\${BUSYBOX_PULL_SAID}/<SAID>/g' \
          -e 's/\$dockerClientShown/<C?>/g' -e 's/\$dockerServerShown/<S?>/g' \
          -e 's/\$DockerClientVersion/<C>/g' -e 's/\$DockerServerVersion/<S>/g' -e 's/\$pullSaid/<SAID>/g' \
    | if [ "${2:-}" = name ]; then sed -e 's/\([Tt]he\) \(backup\|restore\)\b/\1 <SCRIPT>/g'; else cat; fi
}

@test "F1 twins: the version-check and image-check messages are verbatim identical in all four backup/restore twins (script name varied)" {
    local f
    for f in "${BACKUP_SH}" "${BACKUP_PS1}" "${RESTORE_SH}" "${RESTORE_PS1}"; do
        _f1_messages "${REPO_ROOT}/${f}" > "${TEST_DIR}/$(basename "${f}").msg"
        _f1_messages "${REPO_ROOT}/${f}" name > "${TEST_DIR}/$(basename "${f}").named"
    done
    # Non-vacuous: every message of both blocks was found (8 + 7 lines, blanks included;
    # the Podman line is review fix round 9's).
    run grep -c '' "${TEST_DIR}/restore_from_backup.sh.msg"
    assert_output "15"
    run cat "${TEST_DIR}/restore_from_backup.sh.msg"
    assert_output --partial 'ERROR: This Docker version is too old for the restore (Docker client <C?>, Docker Engine <S?>).'
    assert_output --partial "$(printf '%s\n' \
        '       (Docker Desktop 4.27.1 or newer). Update Docker, then run the restore again.' \
        '       (Docker Desktop or Docker Engine is required; Podman is not supported.)' \
        '       Nothing was changed.')"
    assert_output --partial 'NOTE: The restore has not been tested with this Docker version (Docker client <C>, Docker Engine <S>; tested: 29). Continuing.'
    assert_output --partial '       Docker said: <SAID>'
    # .sh == .ps1 per script, exactly.
    run diff "${TEST_DIR}/backup_daaf.sh.msg" "${TEST_DIR}/backup_daaf.ps1.msg"
    assert_success
    run diff "${TEST_DIR}/restore_from_backup.sh.msg" "${TEST_DIR}/restore_from_backup.ps1.msg"
    assert_success
    # backup == restore once the script name is varied.
    run diff "${TEST_DIR}/backup_daaf.sh.named" "${TEST_DIR}/restore_from_backup.sh.named"
    assert_success
    run grep -c 'restore' "${TEST_DIR}/restore_from_backup.sh.named"
    assert_output "0"
}

@test "F1 twins: the same thresholds (refuse < 25, NOTE != 29), the same docker version format, and inspect/pull of the constant in all four twins" {
    local f
    for f in "${BACKUP_SH}" "${BACKUP_PS1}" "${RESTORE_SH}" "${RESTORE_PS1}"; do
        _f1_blocks "${REPO_ROOT}/${f}" > "${TEST_DIR}/blocks"
        echo "file=${f}"
        run grep -c -- '-lt 25' "${TEST_DIR}/blocks"
        assert_output "1"
        run grep -c -- '-ne 29' "${TEST_DIR}/blocks"
        assert_output "1"
        run grep -cF "docker version --format '{{.Client.Version}} {{.Server.Version}}'" "${TEST_DIR}/blocks"
        assert_output "1"
        case "${f}" in
            *.sh)
                run grep -cF 'docker image inspect "${BUSYBOX_IMAGE}" > /dev/null 2>&1' "${TEST_DIR}/blocks"
                assert_output "1"
                run grep -cF 'docker pull "${BUSYBOX_IMAGE}" 2>&1 1>&3 3>&-' "${TEST_DIR}/blocks"
                assert_output "1"
                ;;
            *.ps1)
                run grep -cF '$null = docker image inspect $BusyboxImage 2>&1' "${TEST_DIR}/blocks"
                assert_output "1"
                run grep -cF '$pullAll = @(docker pull $BusyboxImage 2>&1 | ForEach-Object {' "${TEST_DIR}/blocks"
                assert_output "1"
                ;;
        esac
    done
}

# The `docker info` failure branch of twin $1 (review fix round 9, ISSUE 1): from the
# "not running" line to the branch's own exit (`exit 1` / `Wait-AndExit 1`), comments
# dropped.
_f1_info_branch() {
    awk '
        /ERROR: Docker Desktop does not seem to be running/ { on = 1 }
        on { print }
        on && /^[[:space:]]*(exit 1|Wait-AndExit 1)[[:space:]]*$/ { exit }
    ' "$1" | grep -v '^[[:space:]]*#'
}

# Its user-facing lines, in order, the client version as <C>; $2 = "name" also replaces
# "the backup" / "the restore" with "the <SCRIPT>" (the one allowed difference).
_f1_info_messages() {
    _f1_info_branch "$1" \
    | sed -n -e 's/^.*echo "\([^"]*\)".*$/\1/p' -e 's/^.*Write-Host "\([^"]*\)".*$/\1/p' \
    | sed -e 's/\${DOCKER_INFO_FAIL_CLIENT}/<C>/g' -e 's/\$infoFailClient/<C>/g' \
    | if [ "${2:-}" = name ]; then sed -e 's/\([Tt]he\) \(backup\|restore\)\b/\1 <SCRIPT>/g'; else cat; fi
}

@test "F1 twins: the docker-info failure branch's old-Engine hint is verbatim identical in all four twins (script name varied), with the same rule" {
    local f
    for f in "${BACKUP_SH}" "${BACKUP_PS1}" "${RESTORE_SH}" "${RESTORE_PS1}"; do
        _f1_info_messages "${REPO_ROOT}/${f}" > "${TEST_DIR}/$(basename "${f}").imsg"
        _f1_info_messages "${REPO_ROOT}/${f}" name > "${TEST_DIR}/$(basename "${f}").inamed"
        _f1_info_branch "${REPO_ROOT}/${f}" > "${TEST_DIR}/branch"
        echo "file=${f}"
        # The same read (stdout only) and the same rule: client major >= 25 (exactly one
        # comparison), the Engine's version empty or unparsable.
        run grep -cF "docker version --format '{{.Client.Version}} {{.Server.Version}}'" "${TEST_DIR}/branch"
        assert_output "1"
        run grep -c -- '-ge 25' "${TEST_DIR}/branch"
        assert_output "1"
        case "${f}" in
            *.sh)
                run grep -cF '2>/dev/null' "${TEST_DIR}/branch"
                assert_output "1"
                run grep -cF "''|*[!0-9]*|??????*)" "${TEST_DIR}/branch"
                assert_output "2"
                ;;
            *.ps1)
                run grep -cF '2>$null' "${TEST_DIR}/branch"
                assert_output "1"
                run grep -cF -- "\$infoFailServer -notmatch '^\\d{1,5}(\\.|\$)'" "${TEST_DIR}/branch"
                assert_output "1"
                ;;
        esac
    done
    # Exactly the "not running" line plus the two hint lines (non-vacuous).
    run cat "${TEST_DIR}/restore_from_backup.sh.imsg"
    assert_output "$(printf '%s\n' \
        'ERROR: Docker Desktop does not seem to be running. Please start it and try again.' \
        '       If Docker is running, its Docker Engine may be older than 25.0 (Docker client <C>).' \
        '       The restore needs Docker 25.0 or newer (Docker Desktop 4.27.1 or newer).')"
    # .sh == .ps1 per script, exactly.
    run diff "${TEST_DIR}/backup_daaf.sh.imsg" "${TEST_DIR}/backup_daaf.ps1.imsg"
    assert_success
    run diff "${TEST_DIR}/restore_from_backup.sh.imsg" "${TEST_DIR}/restore_from_backup.ps1.imsg"
    assert_success
    # backup == restore once the script name is varied.
    run diff "${TEST_DIR}/backup_daaf.sh.inamed" "${TEST_DIR}/restore_from_backup.sh.inamed"
    assert_success
    run grep -c 'restore' "${TEST_DIR}/restore_from_backup.sh.inamed"
    assert_output "0"
}

# Line of the edition guard in .ps1 $1, and the first line OUTSIDE a function body and
# the DAAF_DRY_RUN mock block (both top-level blocks closed by a column-0 `}`) that runs
# docker; prints "<guard line> <docker line> <docker line text>".
_ps1_guard_and_first_docker() {
    local guard
    guard="$(grep -nxF "if (\$PSVersionTable.PSEdition -eq 'Core' -and -not \$IsWindows -and \$env:DAAF_DRY_RUN -ne '1' -and \$env:DAAF_TEST_ALLOW_CORE_NONWINDOWS -ne '1') {" "$1" | cut -d: -f1)"
    awk -v g="${guard}" '
        /^(function |if \(\$env:DAAF_DRY_RUN )/ { skip = 1 }
        skip { if (/^}/) skip = 0; next }
        /^[[:space:]]*#/ { next }
        /(^|[^A-Za-z0-9_-])docker [a-z]/ { print g, NR, $0; exit }
    ' "$1"
}

@test "F1 PowerShell: both backup and restore .ps1 set \$PSNativeCommandUseErrorActionPreference = \$false and carry the edition guard (exact text)" {
    local f op sh
    for f in "${BACKUP_PS1}" "${RESTORE_PS1}"; do
        case "${f}" in *backup_daaf*) op=backup; sh=backup_daaf.sh ;; *) op=restore; sh=restore_from_backup.sh ;; esac
        echo "file=${f}"
        run grep -cxF '$PSNativeCommandUseErrorActionPreference = $false' "${REPO_ROOT}/${f}"
        assert_output "1"
        # The guard: PSEdition is tested BEFORE $IsWindows (5.1 has no $IsWindows; -and
        # short-circuits on 'Desktop'), with the dry-run and test-only bypasses.
        run grep -A4 -xF "if (\$PSVersionTable.PSEdition -eq 'Core' -and -not \$IsWindows -and \$env:DAAF_DRY_RUN -ne '1' -and \$env:DAAF_TEST_ALLOW_CORE_NONWINDOWS -ne '1') {" "${REPO_ROOT}/${f}"
        assert_output "$(printf '%s\n' \
            "if (\$PSVersionTable.PSEdition -eq 'Core' -and -not \$IsWindows -and \$env:DAAF_DRY_RUN -ne '1' -and \$env:DAAF_TEST_ALLOW_CORE_NONWINDOWS -ne '1') {" \
            "    Write-Host \"ERROR: This PowerShell script is for Windows. On macOS or Linux, run the ${op} with:\" -ForegroundColor Red" \
            "    Write-Host \"         bash ${sh}\"" \
            '    Write-Host "       Nothing was changed."' \
            '    Wait-AndExit 1')"
    done
}

@test "F1 PowerShell: the edition guard (and the native-command line) come BEFORE the first docker call in both .ps1 twins" {
    local f g d pl
    for f in "${BACKUP_PS1}" "${RESTORE_PS1}"; do
        run _ps1_guard_and_first_docker "${REPO_ROOT}/${f}"
        echo "file=${f} -> ${output}"
        read -r g d _ <<< "${output}"
        [ -n "${g}" ]
        [ -n "${d}" ]
        [ "${g}" -lt "${d}" ]
        # The first docker call is the daemon check.
        [[ "${output}" == *'$null = docker info 2>&1' ]]
        pl="$(grep -nxF '$PSNativeCommandUseErrorActionPreference = $false' "${REPO_ROOT}/${f}" | cut -d: -f1)"
        [ "${pl}" -lt "${d}" ]
    done
}

@test "F1 PowerShell SELF-TEST: a docker call placed above the edition guard is caught" {
    local g
    cp "${REPO_ROOT}/${RESTORE_PS1}" "${TEST_DIR}/moved.ps1"
    g="$(grep -nF "if (\$PSVersionTable.PSEdition -eq 'Core'" "${TEST_DIR}/moved.ps1" | cut -d: -f1)"
    sed -i "${g}i \$null = docker version 2>&1" "${TEST_DIR}/moved.ps1"
    run _ps1_guard_and_first_docker "${TEST_DIR}/moved.ps1"
    local gl dl
    read -r gl dl _ <<< "${output}"
    [ "${dl}" -lt "${gl}" ]
}
