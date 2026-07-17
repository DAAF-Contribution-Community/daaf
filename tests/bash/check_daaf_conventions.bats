#!/usr/bin/env bats
# ============================================================================
# Self-test for tests/lint/check-daaf-conventions.sh -- ASCII purity check
# ============================================================================
# WHY THIS FILE EXISTS:
#
# check-daaf-conventions.sh gained an "ASCII purity" section (check 6): every
# file under scripts/host/ must contain only printable ASCII plus tab/LF/CR.
# Host-facing files are downloaded raw to user machines (.sh / .ps1) or
# round-tripped through Windows PowerShell 5.1 read/write cycles (the settings
# template), where a single non-ASCII byte (em-dash, smart quote, NBSP) is what
# a bare PS 5.1 Get-Content mojibakes. This suite locks in that gate: a clean
# tree passes, a non-ASCII byte in a .sh OR a .txt is flagged, and tab/LF/CR
# stay allowed.
#
# The lint accepts a repo-root argument (`bash check-daaf-conventions.sh <root>`),
# so these tests point it at a purpose-built minimal fixture tree in TEST_DIR --
# no git dependency, no mutation of the real repo. The fixture host script is
# well-formed for EVERY lint section (valid shebang + preamble, references
# DAAF_NESTED, has an [N/M] indicator, no Bash-4.x constructs), so a clean fixture
# exits 0 and only an intentional non-ASCII byte flips it to exit 1 -- isolating
# the ASCII check as the variable under test.
# ============================================================================

load 'test_helper'

LINT="${REPO_ROOT}/tests/lint/check-daaf-conventions.sh"

# Write a well-formed, pure-ASCII host script fixture into the fake repo's
# scripts/host/ dir. Passes preamble, DAAF_NESTED, progress, and Bash-3.2 checks
# so the ONLY thing that can fail the lint is the ASCII content under test.
write_clean_host_script() {
    printf '%s\n' \
        '#!/usr/bin/env bash' \
        'set -euo pipefail' \
        '# [1/1] fixture host script; references DAAF_NESTED for the lint' \
        'echo "ok"' \
        > "${FAKE_ROOT}/scripts/host/fixture.sh"
}

setup() {
    common_setup
    FAKE_ROOT="${TEST_DIR}/fakerepo"
    mkdir -p "${FAKE_ROOT}/scripts/host"
    write_clean_host_script
    export LINT FAKE_ROOT
}

teardown() {
    common_teardown
}

# =========================================================================
# Positive: a pure-ASCII host tree passes
# =========================================================================

@test "ASCII check: pure-ASCII host tree passes (exit 0)" {
    run bash "${LINT}" "${FAKE_ROOT}"
    assert_success
    assert_output --partial "pure ASCII"
}

# =========================================================================
# Negative: a non-ASCII byte in a .sh file is flagged
# =========================================================================

@test "ASCII check: em-dash in a host .sh is flagged (exit 1)" {
    emdash="$(printf '\xe2\x80\x94')"
    # Rewrite the fixture with a UTF-8 em-dash embedded in a comment. Every other
    # lint invariant is still satisfied, so ONLY the ASCII check can fail here.
    {
        printf '%s\n' '#!/usr/bin/env bash'
        printf '%s\n' 'set -euo pipefail'
        printf '# [1/1] fixture with an em-dash %s here; DAAF_NESTED\n' "${emdash}"
        printf '%s\n' 'echo "ok"'
    } > "${FAKE_ROOT}/scripts/host/fixture.sh"

    run bash "${LINT}" "${FAKE_ROOT}"
    assert_failure
    assert_output --partial "non-ASCII byte"
    assert_output --partial "fixture.sh"
}

# =========================================================================
# Negative: a non-ASCII byte in a NON-script host file (.txt) is flagged too
# =========================================================================

@test "ASCII check: non-ASCII byte in a host .txt is flagged (all files, not just scripts)" {
    nbsp="$(printf '\xc2\xa0')"
    printf 'a template line with a non-breaking space%shere\n' "${nbsp}" \
        > "${FAKE_ROOT}/scripts/host/example.txt"

    run bash "${LINT}" "${FAKE_ROOT}"
    assert_failure
    assert_output --partial "example.txt"
    assert_output --partial "non-ASCII byte"
}

# =========================================================================
# Allowance: tab characters do NOT trip the check
# =========================================================================

@test "ASCII check: tab characters are allowed (not flagged)" {
    # A tab (0x09) inside an otherwise-ASCII host file must pass -- the check
    # allows tab/LF/CR alongside printable ASCII.
    {
        printf '%s\n' '#!/usr/bin/env bash'
        printf '%s\n' 'set -euo pipefail'
        printf '# [1/1]\tindented-with-tab comment; DAAF_NESTED\n'
        printf '%s\n' 'echo "ok"'
    } > "${FAKE_ROOT}/scripts/host/fixture.sh"

    run bash "${LINT}" "${FAKE_ROOT}"
    assert_success
    assert_output --partial "pure ASCII"
}

# =========================================================================
# Negative: a NUL byte in a host file is flagged (binary-mode false negative)
# =========================================================================

@test "ASCII check: a NUL byte in a host .txt is flagged (not silently binary-skipped)" {
    # GNU grep treats a NUL-containing file as binary: without -a it prints
    # "binary file matches" to stderr (discarded) and nothing to stdout, so the
    # file would silently PASS. This is exactly the UTF-16-mangled PS 5.1 Out-File
    # scenario the ASCII gate exists to catch, so a NUL must FAIL. This test fails
    # against the pre-fix `-nE` grep and passes only with `-anE` -- locking -a in.
    printf 'abc\x00def\n' > "${FAKE_ROOT}/scripts/host/example.txt"

    run bash "${LINT}" "${FAKE_ROOT}"
    assert_failure
    assert_output --partial "example.txt"
    assert_output --partial "non-ASCII byte"
}

# =========================================================================
# Allowance: CR (CRLF line endings) do NOT trip the check
# =========================================================================

@test "ASCII check: CRLF line endings are allowed (CR not flagged)" {
    # CR (0x0D) is in the allowed set alongside tab/LF. A pure-ASCII host file with
    # Windows CRLF line endings must PASS -- locking the banner's "CR allowed"
    # promise so a future edit narrowing the allowed set can't silently break it.
    # Use a .txt host file (not a .sh) so this exercises ONLY the ASCII check: a
    # CRLF .sh would trip section 1's exact-match shebang check on the trailing CR,
    # which is a preamble concern, not the ASCII purity gate under test. The clean
    # default fixture.sh remains in place to satisfy the other lint sections.
    printf 'line one\r\nline two\r\n' > "${FAKE_ROOT}/scripts/host/example.txt"

    run bash "${LINT}" "${FAKE_ROOT}"
    assert_success
    assert_output --partial "example.txt: pure ASCII"
}

# =========================================================================
# grep -q pipefail-inversion check (section 9)
# =========================================================================
# Section 9 flags `| grep -q` fed by a LIVE producer (the pipefail-inversion
# hazard) while exempting the capture-then-grep idiom (echo/printf of an
# already-captured value). These tests lock in: the safe idiom passes, a live
# producer is flagged, a `||` logical-OR is NOT misflagged as a pipeline, and
# the real host tree carries no unsafe pipeline.

@test "grep -q check: a safe capture-then-grep (echo | grep -q) passes" {
    # The sanctioned idiom -- echo of a captured value into grep -q -- must PASS.
    # Every other lint invariant is satisfied so section 9 is the sole variable.
    {
        printf '%s\n' '#!/usr/bin/env bash'
        printf '%s\n' 'set -euo pipefail'
        printf '%s\n' '# [1/1] fixture; references DAAF_NESTED for the lint'
        printf '%s\n' 'val="a b c"'
        printf '%s\n' 'if echo "${val}" | grep -q "b"; then echo "ok"; fi'
    } > "${FAKE_ROOT}/scripts/host/fixture.sh"

    run bash "${LINT}" "${FAKE_ROOT}"
    assert_success
    assert_output --partial "no unsafe '| grep -q' pipelines"
}

@test "grep -q check: a live command piped into grep -q is flagged (exit 1)" {
    # Piping a LIVE producer (git log) straight into grep -q is the pipefail-
    # inversion hazard: grep -q exits early, git dies of SIGPIPE, pipefail
    # inverts the result. Only section 9 can fail here.
    {
        printf '%s\n' '#!/usr/bin/env bash'
        printf '%s\n' 'set -euo pipefail'
        printf '%s\n' '# [1/1] fixture; references DAAF_NESTED for the lint'
        printf '%s\n' 'if git log --oneline | grep -q "abc123"; then echo "found"; fi'
    } > "${FAKE_ROOT}/scripts/host/fixture.sh"

    run bash "${LINT}" "${FAKE_ROOT}"
    assert_failure
    assert_output --partial "pipefail-inversion hazard"
    assert_output --partial "fixture.sh"
}

@test "grep -q check: a || logical-OR of two file greps is not misflagged" {
    # `grep -qf a b || grep -qf a c` contains a `||`, not a pipe into grep -- the
    # producer-adjacency guard ([^|]\|) must not misread it as a pipeline. This is
    # the exact backup_daaf.sh idiom that a naive `\| grep -q` regex false-flags.
    {
        printf '%s\n' '#!/usr/bin/env bash'
        printf '%s\n' 'set -euo pipefail'
        printf '%s\n' '# [1/1] fixture; references DAAF_NESTED for the lint'
        printf '%s\n' 'if grep -qf /dev/null /dev/null || grep -qf /dev/null /dev/null; then echo "ok"; fi'
    } > "${FAKE_ROOT}/scripts/host/fixture.sh"

    run bash "${LINT}" "${FAKE_ROOT}"
    assert_success
    assert_output --partial "no unsafe '| grep -q' pipelines"
}

@test "grep -q check: the real scripts/host tree carries no unsafe pipeline" {
    # Prove the LIVE tree passes the new rule. Assert on the section-9 PASS line
    # and the absence of any hazard flag (not overall exit) so an unrelated future
    # lint failure cannot mask -- or be mistaken for -- a section-9 regression.
    run bash "${LINT}" "${REPO_ROOT}"
    assert_output --partial "migrate_daaf.sh: no unsafe '| grep -q' pipelines"
    refute_output --partial "pipefail-inversion hazard"
}
