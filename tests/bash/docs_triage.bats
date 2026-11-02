#!/usr/bin/env bats
# ============================================================================
# Tests for tests/lint/docs-triage.sh -- the documentation triage lint
# ============================================================================
# The lint scans a git repository named with --root, so each test builds a
# tiny fixture repository under BATS_TEST_TMPDIR (bats removes it after the
# test) and never touches the real tree. The fixture holds:
#   README.md      a maintainer workspace path (family A, tier 1) and an
#                  example project path that must NOT be flagged
#   docs/guide.md  a maintainer-local tool name (family A, tier 6)
#   tests/lint/docs-triage-allowlist.tsv  written per test when needed
# Only tracked files are scanned unless --untracked is given.
# ============================================================================

load 'test_helper'

LINT="${REPO_ROOT}/tests/lint/docs-triage.sh"

# Commits the fixture's files to its own git repository (git add is enough:
# the lint reads the index and working tree, not commits).
make_fixture() {
    FIX="${BATS_TEST_TMPDIR}/fixture"
    mkdir -p "${FIX}/docs" "${FIX}/tests/lint"
    git -C "${FIX}" init -q
    printf '%s\n' \
        'See research/2026-09-29_FrameworkDev_Example/notes.md for details.' \
        'Projects live in folders such as research/2026-01-24_School_Analysis/.' \
        > "${FIX}/README.md"
    printf '%s\n' 'Run nuke_daaf.sh to clean up.' > "${FIX}/docs/guide.md"
    git -C "${FIX}" add README.md docs/guide.md
}

# Writes the fixture allowlist from tab-separated rows given as arguments and
# tracks it.
write_allowlist() {
    : > "${FIX}/tests/lint/docs-triage-allowlist.tsv"
    printf '%s\n' "# fixture allowlist" >> "${FIX}/tests/lint/docs-triage-allowlist.tsv"
    for row in "$@"; do
        printf '%s\n' "${row}" >> "${FIX}/tests/lint/docs-triage-allowlist.tsv"
    done
    git -C "${FIX}" add tests/lint/docs-triage-allowlist.tsv
}

setup() {
    make_fixture
    export LINT FIX
}

@test "a family A workspace path is reported in tier 1 and the scan exits 0" {
    run bash "${LINT}" --root "${FIX}" --family A
    assert_success
    assert_output --partial "== Tier 1: user docs =="
    assert_output --partial "README.md:1: See research/2026-09-29_FrameworkDev_Example/notes.md"
    assert_output --partial "docs/guide.md:1: Run nuke_daaf.sh"
}

@test "an example project path is not a family A hit" {
    run bash "${LINT}" --root "${FIX}" --family A
    assert_success
    refute_output --partial "README.md:2:"
}

@test "the default run exits 0 even with hits in every scanned family" {
    run bash "${LINT}" --root "${FIX}"
    assert_success
    assert_output --partial "Total"
}

@test "an allowlisted hit is suppressed and counted" {
    write_allowlist "docs/guide.md	A	nuke_daaf	fixture: tool name allowed here"
    run bash "${LINT}" --root "${FIX}"
    assert_success
    refute_output --partial "docs/guide.md:1:"
    assert_output --partial "Allowlisted hits (suppressed): 1"
    assert_output --partial "README.md:1:"
}

@test "a whole-file allowlist entry with family * suppresses every hit in the file" {
    write_allowlist "docs/*	*	*	fixture: whole folder"
    run bash "${LINT}" --root "${FIX}"
    assert_success
    refute_output --partial "docs/guide.md:1:"
    assert_output --partial "Stale allowlist entries (match nothing; remove or fix them): 0"
}

@test "an allowlist entry that matches nothing is reported as stale" {
    write_allowlist \
        "docs/guide.md	A	nuke_daaf	fixture: matches" \
        "nothing/*.md	A	*	fixture: matches nothing"
    run bash "${LINT}" --root "${FIX}"
    assert_success
    assert_output --partial "Stale allowlist entries (match nothing; remove or fix them): 1"
    assert_output --partial "line 3: nothing/*.md | A | *"
}

@test "--strict exits 1 when a family A hit is not allowlisted" {
    run bash "${LINT}" --root "${FIX}" --strict
    assert_failure 1
    assert_output --partial "Strict mode: 2 non-allowlisted A/E hit(s)"
}

@test "--strict exits 0 when every family A hit is allowlisted" {
    # The allowlist quotes the tool name, so it needs its own entry (as the
    # real allowlist has).
    write_allowlist \
        "docs/guide.md	A	nuke_daaf	fixture" \
        "README.md	A	FrameworkDev_Example	fixture" \
        "tests/lint/docs-triage-allowlist.tsv	*	*	fixture"
    run bash "${LINT}" --root "${FIX}" --strict
    assert_success
    assert_output --partial "Strict mode: 0 non-allowlisted A/E hit(s)"
}

@test "--format tsv prints a header and five tab-separated columns" {
    run bash "${LINT}" --root "${FIX}" --family A --format tsv
    assert_success
    [ "${lines[0]}" = "$(printf 'tier\tfamily\tfile\tline\ttext')" ]
    [ "${lines[1]}" = "$(printf '1\tA\tREADME.md\t1\tSee research/2026-09-29_FrameworkDev_Example/notes.md for details.')" ]
    for line in "${lines[@]}"; do
        [ "$(printf '%s' "${line}" | awk -F '\t' '{ print NF }')" -eq 5 ]
    done
}

@test "--tier limits the listing and the summary to the chosen tiers" {
    run bash "${LINT}" --root "${FIX}" --family A --tier 6
    assert_success
    assert_output --partial "docs/guide.md:1:"
    refute_output --partial "README.md:1:"
}

@test "family E is skipped with a note when .git/info/exclude has no patterns" {
    run bash "${LINT}" --root "${FIX}" --family E
    assert_success
    assert_output --partial "family E skipped"
}

@test "family E reports a path hidden by .git/info/exclude but not one hidden by .gitignore" {
    printf '%s\n' 'private/' >> "${FIX}/.git/info/exclude"
    printf '%s\n' 'runtime/' > "${FIX}/.gitignore"
    printf '%s\n' 'Notes are in private/plan.md and logs in runtime/log.txt.' > "${FIX}/docs/paths.md"
    git -C "${FIX}" add .gitignore docs/paths.md
    run bash "${LINT}" --root "${FIX}" --family E --format tsv
    assert_success
    assert_output --partial "$(printf 'E\tdocs/paths.md\t1\t')"
    [ "${#lines[@]}" -eq 2 ]
}

@test "an untracked file is scanned only with --untracked" {
    printf '%s\n' 'This page is maintainer-only.' > "${FIX}/docs/new.md"
    run bash "${LINT}" --root "${FIX}" --family A
    assert_success
    refute_output --partial "docs/new.md"
    run bash "${LINT}" --root "${FIX}" --family A --untracked
    assert_success
    assert_output --partial "docs/new.md:1: This page is maintainer-only."
}

@test "--untracked still scans a tracked file that an ignore rule also matches" {
    printf '%s\n' 'settings*.txt' > "${FIX}/.gitignore"
    printf '%s\n' 'This line is not shipped.' > "${FIX}/settings_example.txt"
    git -C "${FIX}" add .gitignore
    git -C "${FIX}" add -f settings_example.txt
    run bash "${LINT}" --root "${FIX}" --family A --untracked
    assert_success
    assert_output --partial "settings_example.txt:1: This line is not shipped."
}

@test "an unknown option exits 2" {
    run bash "${LINT}" --root "${FIX}" --bogus
    assert_failure 2
    assert_output --partial "unknown argument"
}

@test "--family '*' scans every family and still checks the allowlist for stale entries" {
    # Run from the fixture so an unquoted glob would expand to its file names.
    cd "${FIX}"
    run bash "${LINT}" --root "${FIX}" --family '*'
    assert_success
    refute_output --partial "unknown family"
    assert_output --partial "Families: A,B,C,D,E"
    assert_output --partial "Stale allowlist entries (match nothing; remove or fix them): 0"
}

@test "a * inside a --family list, or as a tier, exits 2 without expanding to file names" {
    cd "${FIX}"
    run bash "${LINT}" --root "${FIX}" --family 'A,*'
    assert_failure 2
    assert_output --partial "unknown family '*'"
    run bash "${LINT}" --root "${FIX}" --tier '*'
    assert_failure 2
    assert_output --partial "unknown tier '*'"
}

@test "family D reports Data Onboarding codes but not the Current Population Survey" {
    printf '%s\n' \
        'The CPS is a monthly survey.' \
        'Gate GDI-3 passed; QAS-B and CPS-INTAKE ran before GDS-2.' \
        >> "${FIX}/README.md"
    git -C "${FIX}" add README.md
    run bash "${LINT}" --root "${FIX}" --family D --format tsv
    assert_success
    refute_output --partial "$(printf 'README.md\t3\t')"
    assert_output --partial "$(printf 'README.md\t4\t')"
}

@test "family D reports PSU written out as Phase Status Update in a user-facing file" {
    mkdir -p "${FIX}/user_reference"
    printf '%s\n' 'The next Phase Status Update lists what is done.' > "${FIX}/user_reference/guide.md"
    git -C "${FIX}" add user_reference/guide.md
    run bash "${LINT}" --root "${FIX}" --family D --format tsv
    assert_success
    assert_output --partial "$(printf '1\tD\tuser_reference/guide.md\t1\t')"
}

# The placeholder and Literature Review tests below append lines 3-6 to the
# fixture README.md (a family D file): the first three must be reported, the
# last must not.

@test "family D reports Stage placeholders but not a Stage Name column" {
    printf '%s\n' \
        'Currently at Stage [N] ([Stage Name]).' \
        'Re-entry at Stage [N.N] or Stage [DI-N].' \
        'Fill in Stage N here.' \
        'The Stage Name column and Stage [name of the step] stay plain.' \
        >> "${FIX}/README.md"
    git -C "${FIX}" add README.md
    run bash "${LINT}" --root "${FIX}" --family D --format tsv
    assert_success
    assert_output --partial "$(printf 'README.md\t3\t')"
    assert_output --partial "$(printf 'README.md\t4\t')"
    assert_output --partial "$(printf 'README.md\t5\t')"
    refute_output --partial "$(printf 'README.md\t6\t')"
}

@test "family D reports mode-code placeholders but not a word after the hyphen" {
    printf '%s\n' \
        'Record DI-[N] here.' \
        'Record [DI-N] or DS-N here.' \
        'Record [LR-n] here.' \
        'The DI-Net and LR-new labels stay plain.' \
        >> "${FIX}/README.md"
    git -C "${FIX}" add README.md
    run bash "${LINT}" --root "${FIX}" --family D --format tsv
    assert_success
    assert_output --partial "$(printf 'README.md\t3\t')"
    assert_output --partial "$(printf 'README.md\t4\t')"
    assert_output --partial "$(printf 'README.md\t5\t')"
    refute_output --partial "$(printf 'README.md\t6\t')"
}

@test "family D reports checkpoint placeholders but not other braced names" {
    printf '%s\n' \
        'Decided at [CP-x].' \
        'Read the `CP{n} VALIDATION:` line.' \
        'Read the `QA{n} RESULT:` line and QAP[N].' \
        'Folders such as QA{version}/ and CP{name}/ stay plain.' \
        >> "${FIX}/README.md"
    git -C "${FIX}" add README.md
    run bash "${LINT}" --root "${FIX}" --family D --format tsv
    assert_success
    assert_output --partial "$(printf 'README.md\t3\t')"
    assert_output --partial "$(printf 'README.md\t4\t')"
    assert_output --partial "$(printf 'README.md\t5\t')"
    refute_output --partial "$(printf 'README.md\t6\t')"
}

@test "family D reports Literature Review stage codes but not LR look-alikes" {
    printf '%s\n' \
        'Next: LR-2, then LR-3b.' \
        "At LR-7Q or LR-4' the memo is checked." \
        'Stage list: LR-0 to LR-8, LR-5a, LR-8Q.' \
        'The LR-test statistic and code HLR-1 stay plain.' \
        >> "${FIX}/README.md"
    git -C "${FIX}" add README.md
    run bash "${LINT}" --root "${FIX}" --family D --format tsv
    assert_success
    assert_output --partial "$(printf 'README.md\t3\t')"
    assert_output --partial "$(printf 'README.md\t4\t')"
    assert_output --partial "$(printf 'README.md\t5\t')"
    refute_output --partial "$(printf 'README.md\t6\t')"
}

@test "family D reports Literature Review checkpoint codes but not code page CP-1252" {
    printf '%s\n' \
        'Open checkpoint: CP-K.' \
        'Show the plan again (CP-1).' \
        'Then CP-S, CP-A, CP-R, CP-G or CP-F.' \
        'Files in code page CP-1252 and a CP-Z label stay plain.' \
        >> "${FIX}/README.md"
    git -C "${FIX}" add README.md
    run bash "${LINT}" --root "${FIX}" --family D --format tsv
    assert_success
    assert_output --partial "$(printf 'README.md\t3\t')"
    assert_output --partial "$(printf 'README.md\t4\t')"
    assert_output --partial "$(printf 'README.md\t5\t')"
    refute_output --partial "$(printf 'README.md\t6\t')"
}

@test "the restart prompts in the Full Pipeline and Data Onboarding STATE templates carry no family D code" {
    # The real templates are copied into the fixture, which has no allowlist, so
    # an allowlist fragment such as "Stage " or "DI-" cannot hide a hit here.
    # The block runs from the "### User Restart Prompt" heading to the line
    # before the next heading: the lead-in, the prompt and the orchestrator note.
    mkdir -p "${FIX}/agent_reference"
    for name in STATE_TEMPLATE.md STATE_TEMPLATE_ONBOARDING.md; do
        cp "${REPO_ROOT}/agent_reference/${name}" "${FIX}/agent_reference/${name}"
        git -C "${FIX}" add "agent_reference/${name}"
    done
    run bash "${LINT}" --root "${FIX}" --family D --format tsv
    assert_success
    printf '%s\n' "${output}" > "${BATS_TEST_TMPDIR}/family_d.tsv"
    for name in STATE_TEMPLATE.md STATE_TEMPLATE_ONBOARDING.md; do
        file="agent_reference/${name}"
        read -r start end < <(awk '
            /^### User Restart Prompt[[:space:]]*$/ { s = NR; next }
            s && !e && /^#+ / { e = NR - 1 }
            END { if (s && !e) e = NR; print s + 0, e + 0 }
        ' "${FIX}/${file}")
        echo "${file}: restart-prompt block lines ${start}-${end}"
        [ "${start}" -gt 0 ]
        [ "${end}" -gt "${start}" ]
        # The block holds the quoted prompt the user pastes.
        prompts="$(awk -v s="${start}" -v e="${end}" 'NR >= s && NR <= e && /^> / { n++ } END { print n + 0 }' "${FIX}/${file}")"
        [ "${prompts}" -ge 1 ]
        # The scan read the file: its agent-facing fields have family D hits.
        total="$(awk -F '\t' -v f="${file}" '$3 == f { n++ } END { print n + 0 }' "${BATS_TEST_TMPDIR}/family_d.tsv")"
        [ "${total}" -gt 0 ]
        inside="$(awk -F '\t' -v f="${file}" -v s="${start}" -v e="${end}" '$3 == f && $4 + 0 >= s && $4 + 0 <= e' "${BATS_TEST_TMPDIR}/family_d.tsv")"
        if [ -n "${inside}" ]; then
            echo "family D hits inside the restart-prompt block of ${file}:"
            printf '%s\n' "${inside}"
            return 1
        fi
    done
}

@test "family C skips a dated line that names an external tool but reports a DAAF-internal date" {
    printf '%s\n' \
        'Embedding is verified against Quarto 1.10.18 (2026-11-01).' \
        'moby daemon/list.go matches the name filter exactly (read 2026-10-05).' \
        'The check ran only on fresh installs until 2026-10-02.' \
        >> "${FIX}/README.md"
    git -C "${FIX}" add README.md
    run bash "${LINT}" --root "${FIX}" --family C --format tsv
    assert_success
    refute_output --partial "$(printf 'README.md\t3\t')"
    refute_output --partial "$(printf 'README.md\t4\t')"
    assert_output --partial "$(printf 'README.md\t5\t')"
}

@test "a directory outside any git work tree exits 2" {
    mkdir -p "${BATS_TEST_TMPDIR}/plain"
    # The ceiling stops git from finding an enclosing repository, since TMPDIR
    # may itself sit inside a checkout.
    run env GIT_CEILING_DIRECTORIES="${BATS_TEST_TMPDIR}" bash "${LINT}" --root "${BATS_TEST_TMPDIR}/plain"
    assert_failure 2
    assert_output --partial "not inside a git work tree"
}
