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
#     DAAF_BRANCH DAAF_DEV DAAF_PORT_LOGVIEWER DAAF_PORT_MARIMO
#     DAAF_PORT_VSCODE DAAF_PROJECT_NAME
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
#       `DAAF_PROJECT_NAME=*|` (note the trailing pipe): this deliberately
#       EXCLUDES install.sh's lone `DAAF_PROJECT_NAME=*)` bespoke arm, which has
#       no pipe (install.sh is a documented partial -- see the deviation test).
#   * .ps1 copies: the whitelist is a `$known = @('DAAF_...', ...)` array.
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

# install.sh bespoke arms: any `DAAF_...=*` case pattern (both the lone
# DAAF_PROJECT_NAME=*) arm and the DAAF_DEV=*) arm).
extract_install_sh_keys() {
    grep -oE 'DAAF_[A-Z_]+=\*' "$1" \
        | sed 's/=\*$//' \
        | LC_ALL=C sort -u
}

# install.ps1 bespoke arms: the `-match '^\s*DAAF_...'` regex arms.
extract_install_ps1_keys() {
    grep -E "match .*DAAF_" "$1" \
        | grep -oE 'DAAF_[A-Z_]+' \
        | LC_ALL=C sort -u
}

DAAF_LIB_SH="${REPO_ROOT}/scripts/host/daaf_lib.sh"
DAAF_LIB_PS1="${REPO_ROOT}/scripts/host/daaf_lib.ps1"
INSTALL_SH="${REPO_ROOT}/scripts/host/install.sh"
INSTALL_PS1="${REPO_ROOT}/scripts/host/install.ps1"

# ===========================================================================
# (d) Canonical sets are EXACTLY the pinned literal 6 keys (both languages).
# Placed first: if the extraction returns empty or wrong, every set-equality
# test below would pass vacuously, so this pin is the anti-vacuity anchor.
# ===========================================================================

@test "parity: daaf_lib.sh canonical whitelist is exactly the pinned 6 keys" {
    local got want
    got="$(extract_sh_whitelist "${DAAF_LIB_SH}")"
    want="$(canonical_expected)"
    [ "${got}" = "${want}" ] || {
        echo "CANONICAL DRIFT: daaf_lib.sh whitelist != pinned 6 keys"
        echo "-- extracted:"; echo "${got}"
        echo "-- pinned:";    echo "${want}"
        return 1
    }
}

@test "parity: daaf_lib.ps1 canonical whitelist is exactly the pinned 6 keys" {
    local got want
    got="$(extract_ps1_whitelist "${DAAF_LIB_PS1}")"
    want="$(canonical_expected)"
    [ "${got}" = "${want}" ] || {
        echo "CANONICAL DRIFT: daaf_lib.ps1 \$known != pinned 6 keys"
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
# install.{sh,ps1} do not carry the full whitelist: at install time the settings
# file is usually absent, and the installer only needs DAAF_PROJECT_NAME (to
# derive the data-volume name) and DAAF_DEV (to forward the build flag). Their
# parsing arms are therefore bespoke, NOT the shared pattern. This test pins that
# deviation to exactly {DAAF_DEV, DAAF_PROJECT_NAME} so that a well-meaning
# "let's make install consistent too" edit that silently converts them to the
# full 6-key whitelist TRIPS here and forces a deliberate decision + a matching
# update to this allowlist.

@test "deviation: install.sh parses exactly {DAAF_DEV, DAAF_PROJECT_NAME}" {
    local got want
    got="$(extract_install_sh_keys "${INSTALL_SH}")"
    want="$(printf '%s\n' DAAF_DEV DAAF_PROJECT_NAME)"
    [ "${got}" = "${want}" ] || {
        echo "install.sh deviation changed: expected only the 2 bespoke keys."
        echo "-- extracted:"; echo "${got}"
        echo "-- allowlist:"; echo "${want}"
        echo "If this was intentional, update this deviation test AND confirm the"
        echo "installer really needs the added key at install time (file usually absent)."
        return 1
    }
}

@test "deviation: install.ps1 parses exactly {DAAF_DEV, DAAF_PROJECT_NAME}" {
    local got want
    got="$(extract_install_ps1_keys "${INSTALL_PS1}")"
    want="$(printf '%s\n' DAAF_DEV DAAF_PROJECT_NAME)"
    [ "${got}" = "${want}" ] || {
        echo "install.ps1 deviation changed: expected only the 2 bespoke keys."
        echo "-- extracted:"; echo "${got}"
        echo "-- allowlist:"; echo "${want}"
        return 1
    }
}

# ===========================================================================
# (f) SELF-TEST: the extractor + comparison actually DETECTS drift.
# A parity test that cannot fail is worthless. Copy a real script into the test
# temp dir, perturb its whitelist by one key, and confirm the comparison flags
# it. The real host scripts are never modified.
# ===========================================================================

@test "parity SELF-TEST: perturbing a .sh copy's whitelist trips the comparison" {
    cp "${REPO_ROOT}/scripts/host/backup_daaf.sh" "${TEST_DIR}/perturbed.sh"
    # Drop DAAF_BRANCH from the case-arm (a one-key regression).
    sed -i 's/|DAAF_DEV=\*|DAAF_BRANCH=\*)/|DAAF_DEV=*)/' "${TEST_DIR}/perturbed.sh"

    local canon perturbed
    canon="$(extract_sh_whitelist "${DAAF_LIB_SH}")"
    perturbed="$(extract_sh_whitelist "${TEST_DIR}/perturbed.sh")"

    # The perturbation must have landed (guard against a vacuous self-test).
    [ "${perturbed}" != "${canon}" ] || {
        echo "SELF-TEST VACUOUS: perturbation did not change the extracted set"
        echo "${perturbed}"
        return 1
    }
    # And specifically DAAF_BRANCH must be the key that disappeared.
    if echo "${perturbed}" | grep -qx 'DAAF_BRANCH'; then
        echo "SELF-TEST: perturbation failed to remove DAAF_BRANCH (sed anchor stale?)"
        return 1
    fi
}

@test "parity SELF-TEST: perturbing a .ps1 copy's whitelist trips the comparison" {
    cp "${REPO_ROOT}/scripts/host/backup_daaf.ps1" "${TEST_DIR}/perturbed.ps1"
    # Drop DAAF_BRANCH from the $known array.
    sed -i "s/, 'DAAF_DEV', 'DAAF_BRANCH')/, 'DAAF_DEV')/" "${TEST_DIR}/perturbed.ps1"

    local canon perturbed
    canon="$(extract_ps1_whitelist "${DAAF_LIB_PS1}")"
    perturbed="$(extract_ps1_whitelist "${TEST_DIR}/perturbed.ps1")"

    [ "${perturbed}" != "${canon}" ] || {
        echo "SELF-TEST VACUOUS: perturbation did not change the extracted set"
        echo "${perturbed}"
        return 1
    }
    if echo "${perturbed}" | grep -qx 'DAAF_BRANCH'; then
        echo "SELF-TEST: perturbation failed to remove DAAF_BRANCH (sed anchor stale?)"
        return 1
    fi
}
