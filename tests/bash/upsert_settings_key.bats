#!/usr/bin/env bats
# ============================================================================
# Unit tests for upsert_settings_key (daaf_lib.sh)
# ============================================================================
# upsert_settings_key is the WRITE counterpart to load_daaf_settings: it inserts
# or updates a single KEY=value line in a dotenv-style settings file, preserving
# comments, key order, and layout. These tests exercise the three placement
# rules (append / activate-commented-example / replace), the if-absent guard,
# value edge cases, the dry-run no-write contract, and one-time backup behavior.
#
# The PowerShell twin Set-DaafSettingsKey is covered by
# tests/powershell/Set-DaafSettingsKey.Tests.ps1 with a parallel battery.
# ============================================================================

load 'test_helper'

setup() {
    common_setup
    unset _DAAF_LIB_LOADED
    source "${REPO_ROOT}/scripts/host/daaf_lib.sh"
}

teardown() {
    common_teardown
}

# =========================================================================
# Syntax
# =========================================================================

@test "daaf_lib.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/daaf_lib.sh"
    assert_success
}

# =========================================================================
# Placement rule 3 -- append at end under a dated provenance comment
# =========================================================================

@test "upsert: fresh key appends under a dated provenance comment" {
    printf 'DAAF_PORT_MARIMO=2718\n' > "${TEST_DIR}/s.txt"
    run upsert_settings_key "${TEST_DIR}/s.txt" DAAF_BRANCH main
    assert_success
    assert_output --partial "appended (new)"
    # The new active line is present.
    run grep -Fx 'DAAF_BRANCH=main' "${TEST_DIR}/s.txt"
    assert_success
    # A dated provenance comment (# Added by DAAF on YYYY-MM-DD) is present.
    run grep -qE '^# Added by DAAF on [0-9]{4}-[0-9]{2}-[0-9]{2}$' "${TEST_DIR}/s.txt"
    assert_success
    # The provenance comment sits directly ABOVE the new key.
    run awk '/^# Added by DAAF on /{c=NR} /^DAAF_BRANCH=main$/{a=NR} END{exit !(a==c+1)}' "${TEST_DIR}/s.txt"
    assert_success
}

# =========================================================================
# Placement rule 2 -- insert directly below a commented example
# =========================================================================

@test "upsert: activating a commented example inserts directly below it (adjacency)" {
    printf 'FOO=bar\n#DAAF_BRANCH=\nBAZ=qux\n' > "${TEST_DIR}/s.txt"
    run upsert_settings_key "${TEST_DIR}/s.txt" DAAF_BRANCH dev
    assert_success
    assert_output --partial "inserted below commented example"
    # Adjacency: the active line is the line IMMEDIATELY after the #DAAF_BRANCH= line.
    run awk '/^#DAAF_BRANCH=/{c=NR} /^DAAF_BRANCH=dev$/{a=NR} END{exit !(a==c+1)}' "${TEST_DIR}/s.txt"
    assert_success
    # The trailing content line is untouched and still present after the insert.
    run grep -Fx 'BAZ=qux' "${TEST_DIR}/s.txt"
    assert_success
}

@test "upsert: activates a '# KEY=' commented example with a leading space too" {
    printf '# DAAF_BRANCH=example\n' > "${TEST_DIR}/s.txt"
    run upsert_settings_key "${TEST_DIR}/s.txt" DAAF_BRANCH dev
    assert_success
    assert_output --partial "inserted below commented example"
    run awk '/^# DAAF_BRANCH=/{c=NR} /^DAAF_BRANCH=dev$/{a=NR} END{exit !(a==c+1)}' "${TEST_DIR}/s.txt"
    assert_success
}

# =========================================================================
# if-absent guard -- active key present, file left byte-identical
# =========================================================================

@test "upsert: if-absent skips when an active key already exists (file byte-identical)" {
    printf 'DAAF_BRANCH=main\nFOO=bar\n' > "${TEST_DIR}/s.txt"
    local before after
    before="$(cksum < "${TEST_DIR}/s.txt")"
    run upsert_settings_key "${TEST_DIR}/s.txt" DAAF_BRANCH other
    assert_success
    assert_output --partial "skipped (exists)"
    after="$(cksum < "${TEST_DIR}/s.txt")"
    [ "${before}" = "${after}" ]
}

# =========================================================================
# Placement rule 1 (replace) -- rewrite value in place, preserve position
# =========================================================================

@test "upsert: replace mode rewrites the value in place, preserving position" {
    printf 'A=1\nDAAF_BRANCH=old\nB=2\n' > "${TEST_DIR}/s.txt"
    run upsert_settings_key "${TEST_DIR}/s.txt" DAAF_BRANCH new replace
    assert_success
    assert_output --partial "replaced"
    # Old value gone.
    run grep -q 'DAAF_BRANCH=old' "${TEST_DIR}/s.txt"
    assert_failure
    # New value at the SAME position (line 2 of 3), surrounding lines intact.
    run sed -n '1p' "${TEST_DIR}/s.txt"
    assert_output 'A=1'
    run sed -n '2p' "${TEST_DIR}/s.txt"
    assert_output 'DAAF_BRANCH=new'
    run sed -n '3p' "${TEST_DIR}/s.txt"
    assert_output 'B=2'
}

@test "upsert: replace on an unchanged value is a no-op (reports unchanged)" {
    printf 'DAAF_BRANCH=main\n' > "${TEST_DIR}/s.txt"
    local before after
    before="$(cksum < "${TEST_DIR}/s.txt")"
    run upsert_settings_key "${TEST_DIR}/s.txt" DAAF_BRANCH main replace
    assert_success
    assert_output --partial "unchanged"
    after="$(cksum < "${TEST_DIR}/s.txt")"
    [ "${before}" = "${after}" ]
}

# =========================================================================
# Value edge cases -- spaces, quotes, and '=' inside the value
# =========================================================================

@test "upsert: preserves a value with spaces, quotes, and = signs" {
    printf 'DAAF_BRANCH=main\n' > "${TEST_DIR}/s.txt"
    run upsert_settings_key "${TEST_DIR}/s.txt" DAAF_PROJECT_NAME 'a b="c=d"'
    assert_success
    # The value round-trips byte-for-byte on its own line (=> only the first '='
    # splits key from value; the rest of the value is untouched).
    run grep -Fx 'DAAF_PROJECT_NAME=a b="c=d"' "${TEST_DIR}/s.txt"
    assert_success
    # No stray CR was introduced (LF-only output).
    run grep -qU $'\r' "${TEST_DIR}/s.txt"
    assert_failure
}

# =========================================================================
# Dry-run -- describes the write, touches nothing on disk
# =========================================================================

@test "upsert: dry-run describes the write but touches nothing on disk" {
    printf 'FOO=bar\n' > "${TEST_DIR}/s.txt"
    local before after
    before="$(cksum < "${TEST_DIR}/s.txt")"
    export DAAF_DRY_RUN=1
    run upsert_settings_key "${TEST_DIR}/s.txt" DAAF_BRANCH main
    unset DAAF_DRY_RUN
    assert_success
    assert_output --partial "[DRY-RUN]"
    assert_output --partial "DAAF_BRANCH=main"
    after="$(cksum < "${TEST_DIR}/s.txt")"
    [ "${before}" = "${after}" ]
    # No temp or backup artifacts were left behind.
    run bash -c "ls -a '${TEST_DIR}' | grep -c '.daaf_upsert' || true"
    assert_output "0"
}

# =========================================================================
# Backup -- one-time creation, never overwritten on a later call
# =========================================================================

@test "upsert: backup suffix creates a one-time backup, not overwritten on 2nd call" {
    printf 'DAAF_BRANCH=v1\n' > "${TEST_DIR}/s.txt"
    # First replace with a backup suffix -> the backup captures the ORIGINAL (v1).
    run upsert_settings_key "${TEST_DIR}/s.txt" DAAF_BRANCH v2 replace .bak
    assert_success
    [ -f "${TEST_DIR}/s.txt.bak" ]
    run grep -Fx 'DAAF_BRANCH=v1' "${TEST_DIR}/s.txt.bak"
    assert_success
    # Second replace with the same suffix -> the backup must STILL hold v1, not v2.
    run upsert_settings_key "${TEST_DIR}/s.txt" DAAF_BRANCH v3 replace .bak
    assert_success
    run grep -Fx 'DAAF_BRANCH=v1' "${TEST_DIR}/s.txt.bak"
    assert_success
    run grep -q 'DAAF_BRANCH=v2' "${TEST_DIR}/s.txt.bak"
    assert_failure
    # The live file did advance to v3.
    run grep -Fx 'DAAF_BRANCH=v3' "${TEST_DIR}/s.txt"
    assert_success
}

# =========================================================================
# Documented limitation -- duplicate active keys (replace hits the FIRST)
# =========================================================================

@test "upsert: replace updates the FIRST active occurrence when a key is duplicated (single-occurrence assumption)" {
    # A settings file should never contain two active lines for the same key, but
    # if one was hand-created, replace mode updates the FIRST occurrence and leaves
    # later ones stale. This locks the documented behavior (Compose env_file is
    # last-wins, DAAF's loader is first-wins -- neither reconciles a duplicate).
    printf 'DAAF_BRANCH=first\nFOO=bar\nDAAF_BRANCH=second\n' > "${TEST_DIR}/s.txt"
    run upsert_settings_key "${TEST_DIR}/s.txt" DAAF_BRANCH new replace
    assert_success
    assert_output --partial "replaced"
    # First occurrence rewritten in place...
    run sed -n '1p' "${TEST_DIR}/s.txt"
    assert_output 'DAAF_BRANCH=new'
    # ...the later duplicate is left untouched (stale).
    run sed -n '3p' "${TEST_DIR}/s.txt"
    assert_output 'DAAF_BRANCH=second'
}

# =========================================================================
# Documented limitation -- symlinked target is replaced, link target stays stale
# =========================================================================

@test "upsert: replacing through a symlink swaps the link for a regular file, leaving the target stale (symlink unsupported)" {
    # The same-directory temp + atomic rename replaces the settings PATH with a
    # regular file. When the path is a symlink, the link itself is replaced and the
    # original target is left untouched -- a symlinked environment_settings.txt is
    # unsupported. Lock the current behavior so a future change to it is deliberate.
    printf 'DAAF_BRANCH=old\n' > "${TEST_DIR}/target.txt"
    ln -s "${TEST_DIR}/target.txt" "${TEST_DIR}/link.txt"
    run upsert_settings_key "${TEST_DIR}/link.txt" DAAF_BRANCH new replace
    assert_success
    # The link path is now a REGULAR file (no longer a symlink) holding the new value.
    [ ! -L "${TEST_DIR}/link.txt" ]
    [ -f "${TEST_DIR}/link.txt" ]
    run grep -Fx 'DAAF_BRANCH=new' "${TEST_DIR}/link.txt"
    assert_success
    # The original target is untouched (stale) -- still the old value.
    run grep -Fx 'DAAF_BRANCH=old' "${TEST_DIR}/target.txt"
    assert_success
}

# =========================================================================
# Error path -- missing file
# =========================================================================

@test "upsert: returns an error when the target file does not exist" {
    run upsert_settings_key "${TEST_DIR}/nonexistent.txt" DAAF_BRANCH main
    assert_failure
    assert_output --partial "file not found"
}
