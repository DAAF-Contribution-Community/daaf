#!/usr/bin/env bats
# ============================================================================
# Tests for check_workspace_invariants.sh -- live-filesystem workspace lint
# ============================================================================
# WHY THIS FILE EXISTS:
#
# check_workspace_invariants.sh is the durable, mechanical detection layer for
# workspace invariants that git cannot see (untracked scratch). It is run before
# checkpoints by agents (per CLAUDE.md § Scratch Files and the daaf-orchestrator
# framework-development-mode reference). Three incidents motivate the three
# invariants it enforces:
#
#   Invariant 1 (no unauthorized symlinks): scratch probes repeatedly left
#   symlinks with tab/newline names under scripts/scratch/, breaking real user
#   backups three times on 2026-07-14.
#
#   Invariant 2 (no repo-root leak artifacts): on 2026-07-14 a `migrate_daaf.sh`
#   dry-run run with CWD=/daaf scattered 13 zero-byte stub files plus a
#   `docker-compose.yml.pre-migrate` at the repo root; an `install.sh` dry-run in
#   the same position leaves a stray `daaf-docker/` directory. See session notes
#   at research/2026-07-15_FrameworkDev_CwdLeakRootStubs/.
#
#   Invariant 3 (no Windows-incompatible names): on 2026-09-30 a leftover
#   review-agent fixture whose name contained a newline aborted a real Windows
#   backup — `docker cp` stops extracting at the first name Windows cannot
#   create. The checker flags control characters, < > : " | ? * \, trailing
#   dot/space, reserved device names (with or without an extension), and
#   case-only name clashes within one directory. See
#   research/2026-09-29_FrameworkDev_BackupLongPathCount/.
#
#   --names-only runs Invariant 3 alone. The backup scripts' "could not read the
#   list of names" WARNING points users at it, including for the Claude Code
#   state volume, where Invariants 1-2 would tell them to delete legitimate
#   files (review round 9, 2026-10-01).
#
# This test file is the regression guard for that detection layer.
#
# All fixture trees live under TEST_DIR (created by common_setup, removed by
# common_teardown's `rm -rf TEST_DIR`) — the checker is pointed at them via the
# DAAF_INVARIANT_ROOT override, and DAAF_INVARIANT_ALLOWLIST exempts fixture
# symlinks, so no test needs a /daaf path to exist. NO fixture ever plants a
# violation in the real /daaf. Many fixtures here are deliberately HOSTILE
# (newline/control-char names, reserved device names, case pairs) -- exactly
# what breaks a Windows backup if left behind -- so teardown deletes the whole
# tree depth-first and then asserts it is gone. Run with TMPDIR pointed at a
# project scratch dir (never /tmp); see the shell-scripting skill's testing.md >
# TMPDIR section.
# ============================================================================

load 'test_helper'

# Path to the script under test.
CHECKER="${REPO_ROOT}/scripts/check_workspace_invariants.sh"

setup() {
    common_setup
    export CHECKER
    # An override exported in the runner's shell would change every test's
    # result; the tests that need it set it per run with `env`.
    unset DAAF_INVARIANT_ALLOWLIST
}

teardown() {
    # INTENT: guarantee no hostile-name fixture survives the test.
    # REASONING: common_teardown's `rm -rf` already removes the tree; the explicit
    #   depth-first delete plus the existence check turn a silent leftover (which
    #   would break the next Windows backup and trip this very checker on /daaf)
    #   into a loud test failure.
    # ASSUMES: TEST_DIR is the mktemp dir from common_setup (never /daaf).
    local dir="$TEST_DIR"
    if [ -n "$dir" ] && [ -d "$dir" ]; then
        find "$dir" -mindepth 1 -depth -delete
    fi
    common_teardown
    [ ! -e "$dir" ]
}

# =========================================================================
# Syntax
# =========================================================================

@test "check_workspace_invariants.sh parses without errors" {
    run bash -n "$CHECKER"
    assert_success
}

# =========================================================================
# Clean tree
# =========================================================================

@test "clean tree: exit 0 and prints the OK line" {
    # TEST_DIR is empty apart from what common_setup created (nothing).
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_success
    assert_output --partial "OK: workspace invariants satisfied"
    assert_output --partial "none Windows-uncreatable or case-clashing"
}

@test "clean tree with -q: exit 0 and OK line suppressed" {
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER" -q
    assert_success
    refute_output --partial "OK:"
}

# =========================================================================
# Invariant 1: symlinks
# =========================================================================

@test "unauthorized symlink: exit 1 and the path is listed" {
    ln -s /some/target "${TEST_DIR}/rogue_link"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "unauthorized symlink"
    assert_output --partial "rogue_link"
}

# --- Symlink allowlist: built-in block and the DAAF_INVARIANT_ALLOWLIST override ---
# No test here needs the real allowlisted folder to exist, so every test runs on
# every runner (CI included) and none skips. The built-in entries are absolute
# DAAF dev-container paths, and find reports fixture paths under TEST_DIR, so a
# fixture can never start with a built-in entry. The tests therefore use:
#   - DAAF_INVARIANT_ALLOWLIST on the real checker, to exempt a fixture prefix;
#   - a static read of the real ALLOWLIST block, to pin its content;
#   - a copy of the checker whose built-in block names a fixture prefix (see
#     _checker_with_builtin), only to show that an UNSET variable uses the
#     built-in block and a SET one ignores it.
# A live-/daaf check of the real entries is not needed here: the Checkpoint 2
# gate (`bash scripts/check_workspace_invariants.sh` on /daaf) reports any
# symlink under a mistyped entry.

# The ALLOWLIST entries of a checker script, one per line, read from its
# readonly ALLOWLIST=( ... ) block.
_allowlist_entries() {
    sed -n '/^readonly ALLOWLIST=(/,/^)/p' "$1" | sed -nE 's/^[[:space:]]*"([^"]+)".*$/\1/p'
}

# _checker_with_builtin <prefix>: write a copy of the checker to TEST_DIR (the
# real script is never modified) whose built-in ALLOWLIST block holds only
# <prefix>, check that the rewrite landed, and print the copy's path.
_checker_with_builtin() {
    local prefix="$1" copy="${TEST_DIR}/checker_copy.sh"
    awk -v p="$prefix" '
        /^readonly ALLOWLIST=\(/ { print; print "    \"" p "\""; skip = 1; next }
        skip && /^\)/ { skip = 0 }
        !skip { print }
    ' "$CHECKER" > "$copy"
    # Guard against a vacuous copy (a renamed or one-line block).
    if [ "$(_allowlist_entries "$copy")" != "$prefix" ]; then
        echo "ALLOWLIST rewrite did not land in ${copy}" >&2
        return 1
    fi
    printf '%s\n' "$copy"
}

@test "built-in allowlist: the real ALLOWLIST block holds exactly the R Support GLPK prefix (static; the folder need not exist)" {
    # Pinned on purpose: widening an exemption to a safety gate should have to
    # touch this test too. Every entry must be absolute and end in /, the form
    # the override's header recommends (the / keeps it from matching a sibling).
    run _allowlist_entries "$CHECKER"
    assert_success
    assert_output "/daaf/research/2026-07-06_FrameworkDev_R_Support/scripts/scratch/syslibs_glpk/"
    local entry
    while IFS= read -r entry; do
        [[ "$entry" == /*/ ]] || { echo "ALLOWLIST entry is not absolute and /-terminated: ${entry}"; return 1; }
    done < <(printf '%s\n' "$output")
}

@test "built-in allowlist: with DAAF_INVARIANT_ALLOWLIST unset, the built-in block exempts its prefix and nothing else (no NOTE)" {
    local root="${TEST_DIR}/root" copy
    copy="$(_checker_with_builtin "${root}/builtin/")"
    mkdir -p "${root}/builtin/lib" "${root}/builtin_not"
    printf 'x\n' > "${root}/builtin/lib/libglpk.so.40.3.1"
    ln -s libglpk.so.40.3.1 "${root}/builtin/lib/libglpk.so.40"
    run env DAAF_INVARIANT_ROOT="$root" bash "$copy"
    assert_success
    # The whole output is the unchanged OK line: no NOTE, nothing else.
    assert_output "OK: workspace invariants satisfied (1 symlink(s) checked, all allowlisted or none present; 0 repo-root leak candidate(s) checked, all allowlisted or none present; 5 name(s) checked, none Windows-uncreatable or case-clashing)."
    # A sibling whose name merely STARTS with the prefix text, minus its slash, is
    # not exempt; the report keeps its original advice wording.
    ln -s /some/target "${root}/builtin_not/rogue_link"
    run env DAAF_INVARIANT_ROOT="$root" bash "$copy"
    assert_failure
    assert_output --partial "(1 of 2 symlink(s) are not on the allowlist)"
    assert_output --partial "${root}/builtin_not/rogue_link"
    refute_output --partial "libglpk.so.40"
    assert_output --partial "       ALLOWLIST block at the top of this script."
    refute_output --partial "DAAF_INVARIANT_ALLOWLIST"
}

@test "DAAF_INVARIANT_ALLOWLIST: a symlink under its prefix passes and a sibling outside it is flagged (real checker)" {
    local root="${TEST_DIR}/root"
    mkdir -p "${root}/allowed/lib" "${root}/allowed_not"
    printf 'x\n' > "${root}/allowed/lib/libglpk.so.40.3.1"
    ln -s libglpk.so.40.3.1 "${root}/allowed/lib/libglpk.so.40"
    run env DAAF_INVARIANT_ROOT="$root" DAAF_INVARIANT_ALLOWLIST="${root}/allowed/" bash "$CHECKER"
    assert_success
    assert_output --partial "NOTE: DAAF_INVARIANT_ALLOWLIST is set, so its 1 prefix(es) replace the built-in symlink allowlist for this run."
    assert_output --partial "OK: workspace invariants satisfied (1 symlink(s) checked"
    ln -s /some/target "${root}/allowed_not/rogue_link"
    run env DAAF_INVARIANT_ROOT="$root" DAAF_INVARIANT_ALLOWLIST="${root}/allowed/" bash "$CHECKER"
    assert_failure
    assert_output --partial "(1 of 2 symlink(s) are not on the allowlist)"
    assert_output --partial "${root}/allowed_not/rogue_link"
    refute_output --partial "libglpk.so.40"
    assert_output --partial "used the DAAF_INVARIANT_ALLOWLIST override, not the ALLOWLIST block."
    # Non-vacuous: without the variable the same tree flags both links.
    run env DAAF_INVARIANT_ROOT="$root" bash "$CHECKER"
    assert_failure
    assert_output --partial "(2 of 2 symlink(s) are not on the allowlist)"
    refute_output --partial "NOTE:"
}

@test "DAAF_INVARIANT_ALLOWLIST replaces the built-in list (does not extend it)" {
    local root="${TEST_DIR}/root" copy
    copy="$(_checker_with_builtin "${root}/builtin/")"
    mkdir -p "${root}/builtin" "${root}/override"
    ln -s /some/target "${root}/builtin/link_b"
    ln -s /some/target "${root}/override/link_o"
    # Unset: the built-in prefix exempts link_b only.
    run env DAAF_INVARIANT_ROOT="$root" bash "$copy"
    assert_failure
    assert_output --partial "(1 of 2 symlink(s) are not on the allowlist)"
    assert_output --partial "${root}/override/link_o"
    refute_output --partial "link_b"
    # Set: ONLY the override exempts; the built-in prefix no longer does.
    run env DAAF_INVARIANT_ROOT="$root" DAAF_INVARIANT_ALLOWLIST="${root}/override/" bash "$copy"
    assert_failure
    assert_output --partial "its 1 prefix(es) replace"
    assert_output --partial "(1 of 2 symlink(s) are not on the allowlist)"
    assert_output --partial "${root}/builtin/link_b"
    refute_output --partial "link_o"
}

@test "DAAF_INVARIANT_ALLOWLIST set but empty or blank: no prefix, every symlink flagged (never the built-in list, never allow-all)" {
    local root="${TEST_DIR}/root" copy value
    copy="$(_checker_with_builtin "${root}/builtin/")"
    mkdir -p "${root}/builtin" "${root}/other"
    ln -s /some/target "${root}/builtin/link_b"
    ln -s /some/target "${root}/other/link_x"
    for value in "" $'\n' $'\n\n'; do
        run env DAAF_INVARIANT_ROOT="$root" DAAF_INVARIANT_ALLOWLIST="$value" bash "$copy"
        assert_failure
        assert_output --partial "NOTE: DAAF_INVARIANT_ALLOWLIST is set, so its 0 prefix(es) replace the built-in symlink allowlist for this run."
        assert_output --partial "(2 of 2 symlink(s) are not on the allowlist)"
        assert_output --partial "${root}/builtin/link_b"
        assert_output --partial "${root}/other/link_x"
        refute_output --partial "WORKSPACE INVARIANT ERROR"
    done
    # Contrast: unset uses the built-in block, which exempts link_b.
    run env DAAF_INVARIANT_ROOT="$root" bash "$copy"
    assert_failure
    assert_output --partial "(1 of 2 symlink(s) are not on the allowlist)"
}

@test "DAAF_INVARIANT_ALLOWLIST: a relative entry is refused with exit 1 before any walk (also with --names-only)" {
    local root="${TEST_DIR}/root" value
    mkdir -p "${root}/allowed" "${root}/sub"
    ln -s /some/target "${root}/rogue_link"
    printf 'x\n' > "${root}/sub/nul.txt"
    for value in "allowed/" "./allowed/" " ${root}/allowed/" "$(printf '%s\n' "${root}/allowed/" "rel/")"; do
        run env DAAF_INVARIANT_ROOT="$root" DAAF_INVARIANT_ALLOWLIST="$value" bash "$CHECKER"
        assert_failure
        assert_output --partial "WORKSPACE INVARIANT ERROR: every DAAF_INVARIANT_ALLOWLIST entry must be an absolute path (start with /)."
        assert_output --partial "Nothing was checked."
        # Nothing was walked: no report, no NOTE, no OK line.
        refute_output --partial "VIOLATION"
        refute_output --partial "NOTE:"
        refute_output --partial "OK:"
    done
    # The refused entry is shown, with cat -A marking its end.
    run env DAAF_INVARIANT_ROOT="$root" DAAF_INVARIANT_ALLOWLIST="allowed/" bash "$CHECKER"
    assert_output --partial "Relative entry (control characters shown escaped): allowed/\$"
    run env DAAF_INVARIANT_ROOT="$root" DAAF_INVARIANT_ALLOWLIST="allowed/" bash "$CHECKER" --names-only
    assert_failure
    assert_output --partial "WORKSPACE INVARIANT ERROR: every DAAF_INVARIANT_ALLOWLIST entry must be an absolute path"
    refute_output --partial "nul.txt"
}

@test "DAAF_INVARIANT_ALLOWLIST: an entry covering the whole checked folder is refused (/, ROOT/, ROOT, a prefix of ROOT)" {
    local root="${TEST_DIR}/root" value
    mkdir -p "${root}/allowed"
    ln -s /some/target "${root}/rogue_link"
    for value in "/" "${root}/" "${root}" "${root%/*}/" "$(printf '%s\n' "${root}/allowed/" "/")"; do
        run env DAAF_INVARIANT_ROOT="$root" DAAF_INVARIANT_ALLOWLIST="$value" bash "$CHECKER" -q
        assert_failure
        assert_output --partial "WORKSPACE INVARIANT ERROR: a DAAF_INVARIANT_ALLOWLIST entry would exempt the whole checked folder"
        assert_output --partial "Nothing was checked."
        refute_output --partial "NOTE:"
    done
    # A narrower entry inside ROOT is still accepted, and the rogue link is still flagged.
    run env DAAF_INVARIANT_ROOT="$root" DAAF_INVARIANT_ALLOWLIST="${root}/allowed/" bash "$CHECKER"
    assert_failure
    assert_output --partial "(1 of 1 symlink(s) are not on the allowlist)"
}

@test "DAAF_INVARIANT_ALLOWLIST: newline-separated entries; spaces are kept and glob characters are literal" {
    local root="${TEST_DIR}/root"
    mkdir -p "${root}/with space" "${root}/second" "${root}/abc"
    ln -s /some/target "${root}/with space/link_1"
    ln -s /some/target "${root}/second/link_2"
    ln -s /some/target "${root}/abc/link_3"
    run env DAAF_INVARIANT_ROOT="$root" \
        DAAF_INVARIANT_ALLOWLIST="$(printf '%s\n' "${root}/with space/" "${root}/second/" "${root}/a*/")" \
        bash "$CHECKER"
    assert_failure
    assert_output --partial "its 3 prefix(es) replace"
    # "a*/" is literal text, not a wildcard, so abc/link_3 is still flagged.
    assert_output --partial "(1 of 3 symlink(s) are not on the allowlist)"
    assert_output --partial "${root}/abc/link_3"
    refute_output --partial "link_1"
    refute_output --partial "link_2"
}

@test "DAAF_INVARIANT_ALLOWLIST: the NOTE prints even with -q; --names-only prints none" {
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" DAAF_INVARIANT_ALLOWLIST="${TEST_DIR}/x/" bash "$CHECKER" -q
    assert_success
    assert_output "NOTE: DAAF_INVARIANT_ALLOWLIST is set, so its 1 prefix(es) replace the built-in symlink allowlist for this run."
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" DAAF_INVARIANT_ALLOWLIST="${TEST_DIR}/x/" bash "$CHECKER" --names-only
    assert_success
    assert_output "OK: Windows name check passed under ${TEST_DIR} (0 name(s) checked, none Windows-uncreatable or case-clashing)."
}

@test "DAAF_INVARIANT_ALLOWLIST unset: the default output is unchanged (exact OK line, original advice, no NOTE)" {
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_success
    assert_output "OK: workspace invariants satisfied (0 symlink(s) checked, all allowlisted or none present; 0 repo-root leak candidate(s) checked, all allowlisted or none present; 0 name(s) checked, none Windows-uncreatable or case-clashing)."
    ln -s /some/target "${TEST_DIR}/rogue_link"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "       Symlinks are allowed only under an allowlisted prefix; see the"
    assert_output --partial "       ALLOWLIST block at the top of this script."
    refute_output --partial "DAAF_INVARIANT_ALLOWLIST"
    refute_output --partial "NOTE:"
}

# =========================================================================
# Invariant 2: repo-root leak artifacts
# =========================================================================

@test "zero-byte file at root: exit 1 and listed" {
    : > "${TEST_DIR}/stub_zero.txt"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "leak artifact"
    assert_output --partial "stub_zero.txt"
}

@test "zero-byte file BELOW maxdepth 1: passes (scope check)" {
    mkdir -p "${TEST_DIR}/nested"
    : > "${TEST_DIR}/nested/deep_zero.txt"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_success
    assert_output --partial "OK: workspace invariants satisfied"
}

@test "*.pre-migrate file at root: exit 1 and listed" {
    # A NON-empty pre-migrate backup, to prove the match is on the name glob and
    # not merely on zero-size (the two predicates are ORed).
    printf 'name: daaf\n' > "${TEST_DIR}/docker-compose.yml.pre-migrate"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "leak artifact"
    assert_output --partial "docker-compose.yml.pre-migrate"
}

@test "stray daaf-docker/ dir at root: exit 1 and listed" {
    mkdir -p "${TEST_DIR}/daaf-docker"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "leak artifact"
    assert_output --partial "daaf-docker"
}

@test "non-empty regular file at root: passes (not a leak-artifact shape)" {
    # A normal, non-zero, non-.pre-migrate file at the root must NOT be flagged.
    printf 'hello\n' > "${TEST_DIR}/README.md"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_success
}

# =========================================================================
# Control-character rendering (both invariants use cat -A)
# =========================================================================

@test "filename with a control char is rendered escaped in output" {
    # A zero-byte file whose name contains a literal TAB. cat -A renders TAB as
    # ^I, so a reviewer can see the otherwise-invisible character.
    local tabname
    tabname="$(printf 'stub\tzero')"
    : > "${TEST_DIR}/${tabname}"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    # cat -A renders the embedded tab as ^I.
    assert_output --partial "stub^Izero"
}

# =========================================================================
# Both invariants violated at once: exit 1, both reported
# =========================================================================

@test "symlink + root leak together: exit 1 and both violations reported" {
    ln -s /some/target "${TEST_DIR}/rogue_link"
    : > "${TEST_DIR}/stub_zero.txt"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "unauthorized symlink"
    assert_output --partial "leak artifact"
}

# =========================================================================
# Invariant 3: Windows-incompatible names (uncreatable names + case clashes)
# =========================================================================
# Fixtures are nested one level down (under sub/) and non-empty so Invariant 2
# (root-level zero-byte stubs) cannot fire and muddy the assertion.

@test "newline in a name: exit 1, flagged as control character, rendered escaped" {
    mkdir -p "${TEST_DIR}/sub"
    printf 'x\n' > "${TEST_DIR}/sub/$(printf 'name\nnl')"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "Windows-incompatible name(s)"
    assert_output --partial "these names break Windows backups (docker cp aborts)"
    assert_output --partial "1 name(s) Windows cannot create and 0 case-only clash pair(s)"
    # cat -A marks the embedded newline as "$" + line break, so the name spans
    # two output lines: ".../sub/name$" then "nl$".
    assert_output --partial "[control character] ${TEST_DIR}/sub/name\$"
    assert_output --partial "nl\$"
}

@test "control chars 0x01 and 0x1F flagged; DEL 0x7F is not" {
    mkdir -p "${TEST_DIR}/sub"
    printf 'x\n' > "${TEST_DIR}/sub/$(printf 'a\001b')"
    printf 'x\n' > "${TEST_DIR}/sub/$(printf 'c\037d')"
    printf 'x\n' > "${TEST_DIR}/sub/$(printf 'del\177')"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "2 name(s) Windows cannot create"
    assert_output --partial "a^Ab"
    assert_output --partial "c^_d"
    refute_output --partial "del^?"
}

@test "each reserved character < > : \" | ? * \\ is flagged" {
    mkdir -p "${TEST_DIR}/sub"
    local c
    for c in '<' '>' ':' '"' '|' '?' '*' '\'; do
        printf 'x\n' > "${TEST_DIR}/sub/a${c}b"
    done
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "8 name(s) Windows cannot create"
    assert_output --partial "[reserved character] ${TEST_DIR}/sub/a<b"
    assert_output --partial "[reserved character] ${TEST_DIR}/sub/a\\b"
    assert_output --partial "[reserved character] ${TEST_DIR}/sub/a*b"
}

@test "trailing dot and trailing space flagged (file and dir); leading dot is not" {
    mkdir -p "${TEST_DIR}/sub/dotdir." "${TEST_DIR}/sub/.hidden"
    printf 'x\n' > "${TEST_DIR}/sub/trail."
    printf 'x\n' > "${TEST_DIR}/sub/trail "
    printf 'x\n' > "${TEST_DIR}/sub/..x"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "3 name(s) Windows cannot create"
    assert_output --partial "[trailing dot or space] ${TEST_DIR}/sub/dotdir."
    assert_output --partial "[trailing dot or space] ${TEST_DIR}/sub/trail "
    refute_output --partial ".hidden"
    refute_output --partial "..x"
}

@test "reserved device names flagged case-insensitively, with and without extension" {
    mkdir -p "${TEST_DIR}/sub" "${TEST_DIR}/sub/conout\$"
    local n
    for n in CON prn Aux nul.txt Nul.tar.gz COM1 com9 LPT1 lpt9 \
             "$(printf 'COM\302\271')" "$(printf 'lpt\302\263.log')" 'CONIN$'; do
        printf 'x\n' > "${TEST_DIR}/sub/${n}"
    done
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    # 12 files + the conout$ directory.
    assert_output --partial "13 name(s) Windows cannot create"
    assert_output --partial "[reserved device name] ${TEST_DIR}/sub/Nul.tar.gz"
    assert_output --partial "[reserved device name] ${TEST_DIR}/sub/conout\$"
    # cat -A renders the UTF-8 superscript-1 bytes (\302\271) as M-BM-9.
    assert_output --partial "[reserved device name] ${TEST_DIR}/sub/COMM-BM-9"
}

@test "a name hitting two classes lists both reasons" {
    mkdir -p "${TEST_DIR}/sub"
    printf 'x\n' > "${TEST_DIR}/sub/CON."
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "[trailing dot or space, reserved device name] ${TEST_DIR}/sub/CON."
}

@test "near-miss names are NOT flagged (COM0, LPT0, com10, CONSOLE, 'CON foo', CONx, .con)" {
    mkdir -p "${TEST_DIR}/sub"
    local n
    for n in COM0 LPT0 com10 CONSOLE 'CON foo' CONx .con 'a[b]' 'a^b' 'a-b!' 'x.y.z'; do
        printf 'x\n' > "${TEST_DIR}/sub/${n}"
    done
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_success
    assert_output --partial "none Windows-uncreatable or case-clashing"
}

@test "case clashes: file/file, dir/dir, and file/dir pairs are each reported with types" {
    mkdir -p "${TEST_DIR}/ff" "${TEST_DIR}/dd/CDIR" "${TEST_DIR}/dd/cdir" "${TEST_DIR}/fd/Mixed"
    printf 'x\n' > "${TEST_DIR}/ff/MF1"
    printf 'x\n' > "${TEST_DIR}/ff/mf1"
    printf 'x\n' > "${TEST_DIR}/fd/mixed"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "0 name(s) Windows cannot create and 3 case-only clash pair(s)"
    assert_output --partial "Case-only clashes in one directory"
    # find order within a directory is not guaranteed, so assert each member
    # with its type rather than one fixed pair ordering.
    assert_output --partial "${TEST_DIR}/ff/MF1 (file)"
    assert_output --partial "${TEST_DIR}/ff/mf1 (file)"
    assert_output --partial "${TEST_DIR}/dd/CDIR (dir)"
    assert_output --partial "${TEST_DIR}/dd/cdir (dir)"
    assert_output --partial "${TEST_DIR}/fd/Mixed (dir)"
    assert_output --partial "${TEST_DIR}/fd/mixed (file)"
}

@test "case clash: children of a clashing dir pair are not re-reported" {
    mkdir -p "${TEST_DIR}/sub/CDIR" "${TEST_DIR}/sub/cdir"
    printf 'x\n' > "${TEST_DIR}/sub/CDIR/x"
    printf 'x\n' > "${TEST_DIR}/sub/cdir/x"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "1 case-only clash pair(s)"
}

@test "case-equal names in DIFFERENT directories are not a clash" {
    mkdir -p "${TEST_DIR}/a" "${TEST_DIR}/b"
    printf 'x\n' > "${TEST_DIR}/a/Readme"
    printf 'x\n' > "${TEST_DIR}/b/readme"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_success
}

@test "hostile DIRECTORY name with a newline: only the directory is flagged, not its child" {
    local d
    d="${TEST_DIR}/sub/$(printf 'bad\ndir')"
    mkdir -p "$d"
    printf 'x\n' > "${d}/child.txt"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "1 name(s) Windows cannot create"
    refute_output --partial "child.txt"
}

@test ".git internals are excluded (hostile names and case pairs under .git pass)" {
    mkdir -p "${TEST_DIR}/.git/objects" "${TEST_DIR}/nested/.git"
    printf 'x\n' > "${TEST_DIR}/.git/objects/CON"
    printf 'x\n' > "${TEST_DIR}/.git/objects/$(printf 'a\nb')"
    printf 'x\n' > "${TEST_DIR}/.git/objects/Pack"
    printf 'x\n' > "${TEST_DIR}/.git/objects/pack"
    printf 'x\n' > "${TEST_DIR}/nested/.git/nul.txt"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_success
    assert_output --partial "none Windows-uncreatable or case-clashing"
}

@test ".claude/logs is NOT excluded (hostile name there is flagged)" {
    mkdir -p "${TEST_DIR}/.claude/logs"
    printf 'x\n' > "${TEST_DIR}/.claude/logs/aux.log"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "[reserved device name] ${TEST_DIR}/.claude/logs/aux.log"
}

@test "-q with a Windows-name violation: exit 1 and the violation still prints" {
    mkdir -p "${TEST_DIR}/sub"
    printf 'x\n' > "${TEST_DIR}/sub/nul"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER" -q
    assert_failure
    assert_output --partial "Windows-incompatible name(s)"
    refute_output --partial "OK:"
}

@test "hostile-named symlink is reported by both Invariant 1 and Invariant 3" {
    ln -s /some/target "${TEST_DIR}/$(printf 'link\tname')"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "unauthorized symlink"
    assert_output --partial "[control character] ${TEST_DIR}/link^Iname"
}

# =========================================================================
# --names-only: Invariant 3 alone (the backup scripts' "could not read the
# list of names" hint runs it, including on the Claude Code state volume,
# where Invariants 1-2 would flag legitimate files -- review round 9)
# =========================================================================

@test "--names-only: symlink + root stub + hostile name -> only the name is reported" {
    ln -s /some/target "${TEST_DIR}/rogue_link"
    : > "${TEST_DIR}/stub_zero.txt"
    mkdir -p "${TEST_DIR}/sub"
    printf 'x\n' > "${TEST_DIR}/sub/nul.txt"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER" --names-only
    assert_failure
    assert_output --partial "Windows-incompatible name(s) found under ${TEST_DIR}"
    assert_output --partial "[reserved device name] ${TEST_DIR}/sub/nul.txt"
    refute_output --partial "unauthorized symlink"
    refute_output --partial "leak artifact"
    refute_output --partial "rogue_link"
    refute_output --partial "stub_zero.txt"
    # Neutral advice replaces the DAAF-development "leaked" guess.
    assert_output --partial "Rename or remove them inside DAAF, then back up again."
    refute_output --partial "A test fixture or scratch probe likely leaked them."
    # Non-vacuous: the same tree without the flag reports all three invariants
    # and keeps the original wording.
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER"
    assert_failure
    assert_output --partial "unauthorized symlink"
    assert_output --partial "leak artifact"
    assert_output --partial "A test fixture or scratch probe likely leaked them."
    refute_output --partial "Rename or remove them inside DAAF"
}

@test "--names-only: a tree with only a symlink and a root stub passes with the names-only OK line" {
    ln -s /some/target "${TEST_DIR}/rogue_link"
    : > "${TEST_DIR}/stub_zero.txt"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER" --names-only
    assert_success
    assert_output "OK: Windows name check passed under ${TEST_DIR} (2 name(s) checked, none Windows-uncreatable or case-clashing)."
}

@test "--names-only combines with -q in either order" {
    ln -s /some/target "${TEST_DIR}/rogue_link"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER" --names-only -q
    assert_success
    assert_output ""
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER" -q --names-only
    assert_success
    assert_output ""
    # -q still prints a names violation, and still skips Invariant 1.
    mkdir -p "${TEST_DIR}/sub"
    printf 'x\n' > "${TEST_DIR}/sub/A"
    printf 'x\n' > "${TEST_DIR}/sub/a"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER" -q --names-only
    assert_failure
    assert_output --partial "0 name(s) Windows cannot create and 1 case-only clash pair(s)"
    refute_output --partial "unauthorized symlink"
    refute_output --partial "OK:"
}

@test "unknown argument: usage (listing --names-only) and exit 1, also after a valid flag" {
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER" --bogus
    assert_failure
    assert_output --partial "Usage: bash"
    assert_output --partial "[-q] [--names-only]"
    refute_output --partial "OK:"
    run env DAAF_INVARIANT_ROOT="$TEST_DIR" bash "$CHECKER" --names-only --bogus
    assert_failure
    assert_output --partial "Usage: bash"
    refute_output --partial "OK:"
}
