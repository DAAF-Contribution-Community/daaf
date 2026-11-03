#!/usr/bin/env bats
# ============================================================================
# Whitelist-parity tests for the DAAF_* settings whitelist across all host
# scripts (the .sh case-arms and the .ps1 $known arrays).
# ============================================================================
# WHY THIS FILE EXISTS
# --------------------
# The environment_settings.txt -> host-env bridge is duplicated across the
# daaf_lib.{sh,ps1} canonical loaders plus an inline copy in every standalone
# lifecycle/launcher script that does NOT source the library (9 committed pairs
# + 2 optional dev-workspace pairs, enumerated below). Every copy hardcodes the
# SAME whitelist of DAAF_* keys:
#
#     DAAF_BRANCH DAAF_DATA_VOLUME_NAME DAAF_DEV DAAF_PORT_LOGVIEWER
#     DAAF_PORT_MARIMO DAAF_PORT_VSCODE DAAF_PROJECT_NAME
#
# If one copy drifts (a key added to the library but not propagated to a
# launcher, or vice versa), a second install's project name / published ports /
# build flag / updater branch ref silently fails to take effect in whichever
# script lags -- exactly the class of bug that is invisible in a normal run and
# only surfaces as "my port override did nothing when I launched via view_logs".
# This gate turns whitelist drift into a TEST FAILURE instead of a field report.
#
# WHY BATS-ONLY (not also Pester): bash reads BOTH the .sh and .ps1 source files
# as plain text, so one bats file verifies the whole cross-language contract
# without duplicating the extraction in PowerShell (same rationale as
# backup_twin_parity.bats).
#
# EXTRACTION DESIGN (verified against the live tree):
#   * .sh copies: the whitelist is a pipe-joined case pattern
#       `DAAF_PROJECT_NAME=*|DAAF_PORT_MARIMO=*|...)`. We anchor on the REQUIRED
#       `DAAF_PROJECT_NAME=*|` (note the trailing pipe). install.sh has a
#       pattern of the same shape, but it is never compared with the canonical
#       set: it is a documented partial with its own pinned set (section (e)).
#   * .ps1 copies: the whitelist is a `$known = @('DAAF_...', ...)` array
#       (install.ps1's partial list is a `$bridgeKeys = @(...)` array instead).
#   * The keys are compared as a sorted, de-duplicated newline list, so pattern
#     ORDER never matters -- only set membership.
#
# ROBUSTNESS: files are located by name and the whitelist by its syntactic
# marker (case-arm pipe / `$known = @(`), never by line number, so the tests
# survive line drift. The canonical set is ALSO pinned to a literal sorted list
# (test (d)) so that both libraries drifting together in lockstep still fails.
# ============================================================================

load 'test_helper'

setup() { common_setup; }
teardown() { common_teardown; }

# The standalone .sh / .ps1 inline copies (daaf_lib is the canonical source,
# tested separately as the reference; install is the documented partial).
SETTINGS_COPIES=(
    backup_daaf
    restore_from_backup
    run_daaf
    run_vscode
    update_daaf
    view_logs
    view_notebooks
    view_quarto
    rebuild_daaf
)

# OPTIONAL copies: dev-workspace scripts that exist locally but are not yet
# committed/published (no tracked file references them). They carry the same
# inline whitelist and MUST stay in parity WHEN PRESENT, but a checkout without
# them (e.g. CI on the public repo) must not fail. If one of these is ever
# committed, promote it to SETTINGS_COPIES above.
OPTIONAL_COPIES=(
    nuke_daaf
    run_daaf_dev
)

# The canonical whitelist, pinned as a literal sorted list (test (d) anchor).
# Sorted with LC_ALL=C so the pin is deterministic regardless of locale.
canonical_expected() {
    LC_ALL=C sort -u <<'KEYS'
DAAF_BRANCH
DAAF_DATA_VOLUME_NAME
DAAF_DEV
DAAF_PORT_LOGVIEWER
DAAF_PORT_MARIMO
DAAF_PORT_VSCODE
DAAF_PROJECT_NAME
KEYS
}

# --- Extraction helpers ---------------------------------------------------
# .sh whitelist: the pipe-joined case pattern. The `DAAF_PROJECT_NAME=\*\|`
# prefilter requires a trailing pipe, excluding install.sh's pipeless arm.
extract_sh_whitelist() {
    grep -E 'DAAF_PROJECT_NAME=\*\|' "$1" \
        | grep -oE 'DAAF_[A-Z_]+=\*' \
        | sed 's/=\*$//' \
        | LC_ALL=C sort -u
}

# .ps1 whitelist: the `$known = @(...)` array line.
extract_ps1_whitelist() {
    grep -E '\$known = @\(' "$1" \
        | grep -oE 'DAAF_[A-Z_]+' \
        | LC_ALL=C sort -u
}

# The installer's bridged set (section (e)): the launcher whitelist minus
# DAAF_BRANCH and DAAF_DATA_VOLUME_NAME, pinned as a literal sorted list.
install_bridge_expected() {
    LC_ALL=C sort -u <<'KEYS'
DAAF_DEV
DAAF_PORT_LOGVIEWER
DAAF_PORT_MARIMO
DAAF_PORT_VSCODE
DAAF_PROJECT_NAME
KEYS
}

# install.sh: EVERY `DAAF_...=*` case pattern in the file (the pipe-joined
# filter arm and the per-key adopt arms), so a key added to any arm is seen.
extract_install_sh_keys() {
    grep -oE 'DAAF_[A-Z_]+=\*' "$1" \
        | sed 's/=\*$//' \
        | LC_ALL=C sort -u
}

# install.ps1: the `$bridgeKeys = @(...)` array line (the -notcontains filter).
extract_install_ps1_keys() {
    grep -E '\$bridgeKeys = @\(' "$1" \
        | grep -oE 'DAAF_[A-Z_]+' \
        | LC_ALL=C sort -u
}

# The .ps1 filter line that applies $bridgeKeys. The array pin above reads only the
# literal, so a filter widened in place (`($bridgeKeys + 'DAAF_BRANCH') -notcontains`)
# would pass it (47d SUGGESTION-2); this exact line is pinned to occur once.
INSTALL_PS1_FILTER_LINE='if ($bridgeKeys -notcontains $key) { continue }'

# The settings NOTE key lists (review 44q SUGGESTION-3): which adopted keys the
# installer echoes back. install.sh: the `for _k in ...; do` line right after
# `SETTINGS_NOTE_KEYS=""` (other `for _k in` loops list other key sets, so the
# anchor is the assignment). install.ps1: the `$SettingsNoteKeys = @(@(...)` line.
extract_install_sh_note_keys() {
    awk 'prev == "SETTINGS_NOTE_KEYS=\"\"" && /^for _k in / { print } { prev = $0 }' "$1" \
        | grep -oE 'DAAF_[A-Z_]+' \
        | LC_ALL=C sort -u
}
extract_install_ps1_note_keys() {
    grep -E '^\$SettingsNoteKeys = @\(@\(' "$1" \
        | grep -oE 'DAAF_[A-Z_]+' \
        | LC_ALL=C sort -u
}

DAAF_LIB_SH="${REPO_ROOT}/scripts/host/daaf_lib.sh"
DAAF_LIB_PS1="${REPO_ROOT}/scripts/host/daaf_lib.ps1"
INSTALL_SH="${REPO_ROOT}/scripts/host/install.sh"
INSTALL_PS1="${REPO_ROOT}/scripts/host/install.ps1"

# ===========================================================================
# (d) Canonical sets are EXACTLY the pinned literal 7 keys (both languages).
# Placed first: if the extraction returns empty or wrong, every set-equality
# test below would pass vacuously, so this pin is the anti-vacuity anchor.
# ===========================================================================

@test "parity: daaf_lib.sh canonical whitelist is exactly the pinned 7 keys" {
    local got want
    got="$(extract_sh_whitelist "${DAAF_LIB_SH}")"
    want="$(canonical_expected)"
    [ "${got}" = "${want}" ] || {
        echo "CANONICAL DRIFT: daaf_lib.sh whitelist != pinned 7 keys"
        echo "-- extracted:"; echo "${got}"
        echo "-- pinned:";    echo "${want}"
        return 1
    }
}

@test "parity: daaf_lib.ps1 canonical whitelist is exactly the pinned 7 keys" {
    local got want
    got="$(extract_ps1_whitelist "${DAAF_LIB_PS1}")"
    want="$(canonical_expected)"
    [ "${got}" = "${want}" ] || {
        echo "CANONICAL DRIFT: daaf_lib.ps1 \$known != pinned 7 keys"
        echo "-- extracted:"; echo "${got}"
        echo "-- pinned:";    echo "${want}"
        return 1
    }
}

# ===========================================================================
# (c) Cross-language: the .sh canonical set == the .ps1 canonical set.
# ===========================================================================

@test "parity: daaf_lib.sh and daaf_lib.ps1 canonical whitelists match (cross-language)" {
    local sh_set ps1_set
    sh_set="$(extract_sh_whitelist "${DAAF_LIB_SH}")"
    ps1_set="$(extract_ps1_whitelist "${DAAF_LIB_PS1}")"
    [ "${sh_set}" = "${ps1_set}" ] || {
        echo "CROSS-LANGUAGE DRIFT: daaf_lib.sh whitelist != daaf_lib.ps1 whitelist"
        echo "-- .sh:";  echo "${sh_set}"
        echo "-- .ps1:"; echo "${ps1_set}"
        return 1
    }
}

# ===========================================================================
# (a) Every .sh inline copy matches the daaf_lib.sh canonical set.
# ===========================================================================

@test "parity: each .sh inline whitelist copy matches the daaf_lib.sh canonical set" {
    local canon; canon="$(extract_sh_whitelist "${DAAF_LIB_SH}")"
    local name f got
    for name in "${SETTINGS_COPIES[@]}"; do
        f="${REPO_ROOT}/scripts/host/${name}.sh"
        [ -f "${f}" ] || { echo "MISSING: ${f}"; return 1; }
        got="$(extract_sh_whitelist "${f}")"
        [ "${got}" = "${canon}" ] || {
            echo "WHITELIST DRIFT: ${name}.sh case-arm != daaf_lib.sh canonical set"
            echo "-- ${name}.sh:"; echo "${got}"
            echo "-- canonical:";  echo "${canon}"
            return 1
        }
    done
    # Optional dev-workspace copies: parity enforced only when present.
    for name in "${OPTIONAL_COPIES[@]}"; do
        f="${REPO_ROOT}/scripts/host/${name}.sh"
        [ -f "${f}" ] || continue
        got="$(extract_sh_whitelist "${f}")"
        [ "${got}" = "${canon}" ] || {
            echo "WHITELIST DRIFT (optional copy): ${name}.sh != daaf_lib.sh canonical set"
            echo "-- ${name}.sh:"; echo "${got}"
            echo "-- canonical:";  echo "${canon}"
            return 1
        }
    done
}

# ===========================================================================
# (b) Every .ps1 inline copy matches the daaf_lib.ps1 canonical set.
# ===========================================================================

@test "parity: each .ps1 inline whitelist copy matches the daaf_lib.ps1 canonical set" {
    local canon; canon="$(extract_ps1_whitelist "${DAAF_LIB_PS1}")"
    local name f got
    for name in "${SETTINGS_COPIES[@]}"; do
        f="${REPO_ROOT}/scripts/host/${name}.ps1"
        [ -f "${f}" ] || { echo "MISSING: ${f}"; return 1; }
        got="$(extract_ps1_whitelist "${f}")"
        [ "${got}" = "${canon}" ] || {
            echo "WHITELIST DRIFT: ${name}.ps1 \$known != daaf_lib.ps1 canonical set"
            echo "-- ${name}.ps1:"; echo "${got}"
            echo "-- canonical:";   echo "${canon}"
            return 1
        }
    done
    # Optional dev-workspace copies: parity enforced only when present.
    for name in "${OPTIONAL_COPIES[@]}"; do
        f="${REPO_ROOT}/scripts/host/${name}.ps1"
        [ -f "${f}" ] || continue
        got="$(extract_ps1_whitelist "${f}")"
        [ "${got}" = "${canon}" ] || {
            echo "WHITELIST DRIFT (optional copy): ${name}.ps1 \$known != daaf_lib.ps1 canonical set"
            echo "-- ${name}.ps1:"; echo "${got}"
            echo "-- canonical:";   echo "${canon}"
            return 1
        }
    done
}

# ===========================================================================
# (e) DEVIATION ALLOWLIST: install.sh / install.ps1 are DELIBERATELY partial.
# ===========================================================================
# install.{sh,ps1} do not carry the full whitelist. Since the 2026-10-11 bridge
# (F-a; reviews 42q I-2, 43d ISSUE-1, 44q), the installer reads the five keys
# Docker Compose interpolates at build/up time from environment_settings.txt:
# DAAF_PROJECT_NAME (project and data-volume name), the three DAAF_PORT_* (host
# ports) and DAAF_DEV (build flag). It DELIBERATELY does not bridge:
#   * DAAF_BRANCH: the ref of the running installer is already fixed (RAW_BASE /
#     $Branch) before the file could be read;
#   * DAAF_DATA_VOLUME_NAME: the run always mounts "<project>_daaf-data" (the
#     re-downloaded compose file has its shared-volume block commented out), so a
#     file value could only point the existing-install check AWAY from that volume
#     (see DATA_VOLUME_NAME in install.sh). A SHELL value is still honoured.
# Their parsing arms are bespoke (the .sh filter + adopt arms, the .ps1
# $bridgeKeys array), NOT the shared pattern. These tests pin that deviation to
# exactly the five keys, so that adding DAAF_BRANCH / DAAF_DATA_VOLUME_NAME (a
# "let's make install consistent too" edit) or dropping a key TRIPS here and
# forces a deliberate decision plus a matching update to this allowlist. The same
# five keys are also pinned in the .ps1 filter line that applies $bridgeKeys and in
# both installers' settings NOTE lists (47d SUGGESTION-2).

@test "deviation: install.sh bridges exactly the 5 install-time keys (no DAAF_BRANCH/DAAF_DATA_VOLUME_NAME)" {
    local got arm want
    got="$(extract_install_sh_keys "${INSTALL_SH}")"
    arm="$(extract_sh_whitelist "${INSTALL_SH}")"
    want="$(install_bridge_expected)"
    [ "${got}" = "${want}" ] || {
        echo "install.sh deviation changed: expected exactly the 5 bridged keys in its case arms."
        echo "-- extracted:"; echo "${got}"
        echo "-- allowlist:"; echo "${want}"
        echo "If this was intentional, update this deviation test AND confirm the"
        echo "installer really needs the changed key at install time."
        return 1
    }
    # The pipe-joined filter arm alone must also carry all five (an adopt arm
    # whose key the filter drops would be dead code).
    [ "${arm}" = "${want}" ] || {
        echo "install.sh filter arm != the 5 bridged keys"
        echo "-- filter arm:"; echo "${arm}"
        echo "-- allowlist:";  echo "${want}"
        return 1
    }
}

@test "deviation: install.ps1 bridges exactly the 5 install-time keys (no DAAF_BRANCH/DAAF_DATA_VOLUME_NAME)" {
    local got want
    got="$(extract_install_ps1_keys "${INSTALL_PS1}")"
    want="$(install_bridge_expected)"
    [ "${got}" = "${want}" ] || {
        echo "install.ps1 deviation changed: expected exactly the 5 bridged keys in \$bridgeKeys."
        echo "-- extracted:"; echo "${got}"
        echo "-- allowlist:"; echo "${want}"
        return 1
    }
    # The array is applied by exactly one unmodified filter line, and $bridgeKeys is
    # used nowhere else (a widened filter or a `$bridgeKeys += ...` line would let a
    # key the array pin cannot see through).
    local n
    n="$(grep -cF "${INSTALL_PS1_FILTER_LINE}" "${INSTALL_PS1}" || true)"
    [ "${n}" -eq 1 ] || { echo "install.ps1: '${INSTALL_PS1_FILTER_LINE}' found ${n} time(s), expected 1"; return 1; }
    n="$(grep -c 'bridgeKeys' "${INSTALL_PS1}" || true)"
    [ "${n}" -eq 2 ] || {
        echo "install.ps1: \$bridgeKeys on ${n} line(s), expected 2 (the array and its filter):"
        grep -n 'bridgeKeys' "${INSTALL_PS1}"
        return 1
    }
}

@test "deviation: the installer's settings NOTE lists (install.sh and install.ps1) name exactly the 5 bridged keys" {
    local f got want
    want="$(install_bridge_expected)"
    [ "$(grep -cxF 'SETTINGS_NOTE_KEYS=""' "${INSTALL_SH}")" -eq 1 ] || { echo "install.sh: SETTINGS_NOTE_KEYS=\"\" anchor not found exactly once"; return 1; }
    [ "$(grep -cE '^\$SettingsNoteKeys = @\(@\(' "${INSTALL_PS1}")" -eq 1 ] || { echo "install.ps1: \$SettingsNoteKeys anchor not found exactly once"; return 1; }
    for f in sh ps1; do
        if [ "${f}" = sh ]; then got="$(extract_install_sh_note_keys "${INSTALL_SH}")"; else got="$(extract_install_ps1_note_keys "${INSTALL_PS1}")"; fi
        [ "${got}" = "${want}" ] || {
            echo "install.${f} NOTE key list != the 5 bridged keys"
            echo "-- extracted:"; echo "${got}"
            echo "-- allowlist:"; echo "${want}"
            return 1
        }
    done
}

@test "deviation: the installer's bridged set is the canonical whitelist minus {DAAF_BRANCH, DAAF_DATA_VOLUME_NAME}" {
    local missing extra
    # Keys in the canonical set but not bridged: exactly the two documented ones.
    missing="$(LC_ALL=C comm -23 <(canonical_expected) <(install_bridge_expected))"
    [ "${missing}" = "$(printf '%s\n' DAAF_BRANCH DAAF_DATA_VOLUME_NAME)" ] || {
        echo "UNEXPLAINED GAP: canonical keys not bridged by the installer:"; echo "${missing}"
        return 1
    }
    # And the installer bridges nothing the launchers do not.
    extra="$(LC_ALL=C comm -13 <(canonical_expected) <(install_bridge_expected))"
    [ -z "${extra}" ] || { echo "installer bridges non-whitelisted keys:"; echo "${extra}"; return 1; }
}

# ===========================================================================
# (f) SELF-TEST: the extractor + comparison actually DETECTS drift.
# A parity test that cannot fail is worthless. Copy a real script into the test
# temp dir, perturb its whitelist by one key, and confirm the comparison flags
# it. The real host scripts are never modified.
# ===========================================================================

@test "parity SELF-TEST: perturbing a .sh copy's whitelist trips the comparison" {
    cp "${REPO_ROOT}/scripts/host/backup_daaf.sh" "${TEST_DIR}/perturbed.sh"
    # Drop the terminal DAAF_DATA_VOLUME_NAME from the case-arm (a one-key regression).
    sed -i 's/|DAAF_BRANCH=\*|DAAF_DATA_VOLUME_NAME=\*)/|DAAF_BRANCH=*)/' "${TEST_DIR}/perturbed.sh"

    local canon perturbed
    canon="$(extract_sh_whitelist "${DAAF_LIB_SH}")"
    perturbed="$(extract_sh_whitelist "${TEST_DIR}/perturbed.sh")"

    # The perturbation must have landed (guard against a vacuous self-test).
    [ "${perturbed}" != "${canon}" ] || {
        echo "SELF-TEST VACUOUS: perturbation did not change the extracted set"
        echo "${perturbed}"
        return 1
    }
    # And specifically DAAF_DATA_VOLUME_NAME must be the key that disappeared.
    if echo "${perturbed}" | grep -qx 'DAAF_DATA_VOLUME_NAME'; then
        echo "SELF-TEST: perturbation failed to remove DAAF_DATA_VOLUME_NAME (sed anchor stale?)"
        return 1
    fi
}

@test "parity SELF-TEST: perturbing a .ps1 copy's whitelist trips the comparison" {
    cp "${REPO_ROOT}/scripts/host/backup_daaf.ps1" "${TEST_DIR}/perturbed.ps1"
    # Drop the terminal DAAF_DATA_VOLUME_NAME from the $known array.
    sed -i "s/, 'DAAF_BRANCH', 'DAAF_DATA_VOLUME_NAME')/, 'DAAF_BRANCH')/" "${TEST_DIR}/perturbed.ps1"

    local canon perturbed
    canon="$(extract_ps1_whitelist "${DAAF_LIB_PS1}")"
    perturbed="$(extract_ps1_whitelist "${TEST_DIR}/perturbed.ps1")"

    [ "${perturbed}" != "${canon}" ] || {
        echo "SELF-TEST VACUOUS: perturbation did not change the extracted set"
        echo "${perturbed}"
        return 1
    }
    if echo "${perturbed}" | grep -qx 'DAAF_DATA_VOLUME_NAME'; then
        echo "SELF-TEST: perturbation failed to remove DAAF_DATA_VOLUME_NAME (sed anchor stale?)"
        return 1
    fi
}
