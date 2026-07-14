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
#      the .daaf-symlinks manifest. In backup_daaf.sh it is a single-quoted
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
teardown() { common_teardown; }

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
