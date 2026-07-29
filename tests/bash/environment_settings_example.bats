#!/usr/bin/env bats
# ============================================================================
# Structural lint for scripts/host/environment_settings_example.txt
# ============================================================================
# WHY THIS FILE EXISTS:
#
# environment_settings_example.txt is the annotated template users copy to
# environment_settings.txt. It is consumed by TWO strict, line-oriented parsers:
# Docker Compose's env_file ingestion (into the container) and DAAF's own host-
# script settings loader (_daaf_load_settings in update_daaf.sh / daaf_lib.sh,
# for the DAAF_* host-bridged keys). Both break on a BOM, on CRLF, on an indented
# KEY=value, or on an inline "# ..." comment after a value. The file also follows
# a deliberate navigability convention (a header block, a CONTENTS map, two-tier
# banners with lifecycle tags, and a prose-vs-actionable delineation) that a
# reviewer cannot eyeball at scale.
#
# This lint enforces the machine-checkable invariants of that convention so a
# future edit cannot silently reintroduce a parser hazard or drift the CONTENTS
# map out of sync with the section banners. See the design record at
# research/2026-07-12_FrameworkDev_InstallSettingsSeeding/.
#
# Assertions:
#   (a) no UTF-8 BOM (first 3 bytes)
#   (b) LF-only line endings (no CR bytes)
#   (c) every line is empty, starts with '#', or is a column-0 KEY=value
#       (nothing indented, no stray non-comment content)
#   (d) the "#KEY=value" convention holds: no "# KEY=value" prose-form key lines
#       (hash-SPACE-key) that would activate to a valid assignment
#   (e) CONTENTS entries correspond 1:1 (number + title, in order) with the
#       "# ====" numbered section banners
#   (f) the 7 host-bridged keys each appear at least once as an example key line
#
# This test reads the real file (read-only); it never writes to it.
# ============================================================================

load 'test_helper'

EXAMPLE_FILE="${REPO_ROOT}/scripts/host/environment_settings_example.txt"

setup() {
    common_setup
    export EXAMPLE_FILE
}

teardown() {
    common_teardown
}

# =========================================================================
# Existence
# =========================================================================

@test "environment_settings_example.txt exists" {
    [ -f "${EXAMPLE_FILE}" ]
}

# =========================================================================
# (a) No UTF-8 BOM
# =========================================================================

@test "(a) file has no UTF-8 BOM" {
    # The BOM is the three bytes EF BB BF. Read the first three bytes as octal
    # and assert they are not the BOM sequence (357 273 277).
    run od -An -tu1 -N3 "${EXAMPLE_FILE}"
    assert_success
    # od prints the three decimal byte values; the BOM would be "239 187 191".
    refute_output --partial "239 187 191"
}

# =========================================================================
# (b) LF-only (no carriage returns)
# =========================================================================

@test "(b) file contains no CR bytes (LF-only line endings)" {
    # Count carriage-return (0x0D) bytes; must be zero.
    cr_count="$(tr -cd '\r' < "${EXAMPLE_FILE}" | wc -c | tr -d ' ')"
    [ "${cr_count}" -eq 0 ]
}

# =========================================================================
# (c) Every line is empty, a comment, or a column-0 KEY=value
# =========================================================================

@test "(c) every line is empty, a comment, or an unindented KEY=value" {
    # Any line that is NOT blank, NOT a comment (first char '#'), and NOT a
    # column-0 KEY= assignment is a structural violation (e.g. an indented key,
    # or stray prose without a leading '#').
    run awk '
        /^$/            { next }             # blank
        /^#/            { next }             # comment (indentation allowed AFTER #)
        /^[A-Za-z_][A-Za-z0-9_]*=/ { next }  # column-0 KEY=value
        { print NR": "$0; bad++ }
        END { exit (bad>0) }
    ' "${EXAMPLE_FILE}"
    assert_success
}

# =========================================================================
# (d) #KEY=value convention: no "# KEY=value" prose-form key lines
# =========================================================================

@test "(d) no hash-space-key prose lines that look like activatable assignments" {
    # Actionable example keys must be written "#KEY=value" (hash immediately
    # followed by the key). A "# KEY=value" line (hash, space, key, '=') would
    # look activatable but leave a stray leading space when uncommented and
    # breaks the "delete one character to activate" contract. Flag any such line.
    # Prose that mentions a key mid-sentence, or an indented illustrative command
    # (two or more spaces after '#'), does not match this pattern.
    run grep -nE '^# [A-Za-z_][A-Za-z0-9_]*=' "${EXAMPLE_FILE}"
    # grep exits 1 when there are no matches — which is what we want.
    assert_failure
}

@test "(d) at least one activatable #KEY=value example is present" {
    # Sanity floor: the file is a template, so column-0 "#KEY=" examples must
    # exist (guards against a refactor that accidentally deletes every example).
    run grep -cE '^#[A-Za-z_][A-Za-z0-9_]*=' "${EXAMPLE_FILE}"
    assert_success
    [ "${output}" -ge 30 ]
}

@test "(d) no active (uncommented) keys ship by default" {
    # Safe-by-default: the shipped template must set nothing. Every key is a
    # commented "#KEY=" example; zero column-0 "KEY=" assignments.
    run grep -cE '^[A-Za-z_][A-Za-z0-9_]*=' "${EXAMPLE_FILE}"
    # grep -c prints 0 and exits 1 when there are no matches.
    [ "${output}" -eq 0 ]
}

# =========================================================================
# (e) CONTENTS map <-> section banners are 1:1 (number + title, in order)
# =========================================================================

@test "(e) CONTENTS entries match the numbered section banners 1:1" {
    # TOC entries are written "#   [N] Title ...... (lifecycle)" (three spaces
    # after '#'). Section banners are a "# [N] Title  (lifecycle)" title line
    # (one space after '#') sitting between two "# ====" rule lines. Normalize
    # both to "N:Title" (strip the bracket, dotted leaders, and the trailing
    # "(...)" lifecycle tag) and compare the ordered lists.
    normalize='
        function norm(s,   t, p) {
            sub(/^#[ ]+/, "", s)           # drop "#" and leading spaces
            match(s, /^\[[0-9]+\]/)        # "[N]"
            t = substr(s, RSTART, RLENGTH)
            gsub(/[][]/, "", t)            # -> N
            p = substr(s, RLENGTH + 1)     # text after "[N]"
            sub(/\(.*/, "", p)             # cut trailing lifecycle "(...)"
            gsub(/\./, "", p)              # remove dotted leaders
            gsub(/^[ ]+|[ ]+$/, "", p)     # trim
            return t ":" p
        }'

    toc="$(awk "${normalize}"'
        /^#   \[[0-9]+\]/ { print norm($0) }
    ' "${EXAMPLE_FILE}")"

    banners="$(awk "${normalize}"'
        prev ~ /^# =+$/ && /^# \[[0-9]+\]/ { print norm($0) }
        { prev = $0 }
    ' "${EXAMPLE_FILE}")"

    # Neither list may be empty.
    [ -n "${toc}" ]
    [ -n "${banners}" ]

    # Ordered, exact equality between the two normalized lists.
    [ "${toc}" = "${banners}" ]
}

@test "(e) there are exactly six numbered sections" {
    run grep -cE '^# \[[0-9]+\] ' "${EXAMPLE_FILE}"
    assert_success
    [ "${output}" -eq 6 ]
}

# =========================================================================
# (f) The seven host-bridged keys each appear as an example key line
# =========================================================================

@test "(f) each host-bridged key appears as a #KEY= example line" {
    for key in DAAF_PROJECT_NAME DAAF_PORT_MARIMO DAAF_PORT_LOGVIEWER \
               DAAF_PORT_VSCODE DAAF_DEV DAAF_BRANCH DAAF_DATA_VOLUME_NAME; do
        run grep -qE "^#${key}=" "${EXAMPLE_FILE}"
        if [ "${status}" -ne 0 ]; then
            echo "missing host-bridged example key: #${key}="
            return 1
        fi
    done
}
