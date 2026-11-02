#!/usr/bin/env bats
# ============================================================================
# Tests for adjudicator-read-scope.sh -- agent-scoped PreToolUse read guard
# ============================================================================
# Contract (from the hook header): while the citation-adjudicator runs, the
# only tool call allowed is a Read of a bundle file:
#   - an absolute path that is already canonical (`realpath -m -s` and
#     `realpath -m` both return it unchanged: no `..`, `.`, `//`, trailing
#     slash or symlink anywhere along it);
#   - under <DAAF root>/research/, at
#     <project...>/data/adjudication_bundles/<batch_id>.json, where <batch_id>
#     follows lit_corpus's BATCH_ID_RE ^[a-z0-9][a-z0-9_-]{0,31}$;
#   - naming an existing regular file.
# Everything else is denied: any other path, any tool other than Read, and any
# input or environment the hook cannot check.
#
# Scope: registered in the FRONTMATTER of citation-adjudicator only, matcher ""
# (every tool), NOT project-wide in settings.json. A call whose agent_type
# names a different agent is allowed untouched; a call with no agent_type is
# checked like an adjudicator call.
#
# Failure posture: fail-CLOSED. Every deny goes out three ways at once: a JSON
# permissionDecision "deny" on stdout, a "BLOCKED by adjudicator-read-scope
# hook" line on stderr, and exit 2 (which blocks even if the JSON were
# malformed). Allow = exit 0 with no output.
#
# Fixtures: a fake DAAF root under TEST_DIR (CLAUDE_PROJECT_DIR points at it),
# holding a real bundle, a prompt file, a dot-file, a directory named like a
# bundle, two symlinks and a bundle-shaped file outside research/. teardown's
# `rm -rf TEST_DIR` removes them all; rm never follows a symlink.
#
# SCRIPT UNDER TEST is parameterized for pre-deployment testing of a draft:
#   ADJUDICATOR_READ_SCOPE_SH=/path/to/draft.sh bats adjudicator_read_scope.bats
# ============================================================================

load 'test_helper'

ADJUDICATOR_READ_SCOPE_SH="${ADJUDICATOR_READ_SCOPE_SH:-${REPO_ROOT}/.claude/hooks/adjudicator-read-scope.sh}"
ADJ_AGENT_FILE="${REPO_ROOT}/.claude/agents/citation-adjudicator.md"
# Absolute, so `env -i PATH=<stripped folder>` cases can still start bash.
BASH_BIN="$(command -v bash)"

setup() {
    common_setup
    export ADJUDICATOR_READ_SCOPE_SH
    # The fixture root must itself be canonical: the hook refuses any path
    # that passes through a symlink, so a symlinked TMPDIR would deny the
    # real bundle too.
    ROOT="$(realpath "${TEST_DIR}")/root"
    BDIR="${ROOT}/research/proj/data/adjudication_bundles"
    BUNDLE="${BDIR}/b01.json"
    mkdir -p "${BDIR}"
    printf '{"schema_version": "lit-adjudication-bundle-v1"}\n' > "${BUNDLE}"
    printf 'DAAF citation second check.\n' > "${BDIR}/b01_prompt.txt"
    printf '{}\n' > "${BDIR}/.hidden.json"
    mkdir "${BDIR}/b03.json"
    printf 'x\n' > "${ROOT}/CLAUDE.md"
    ln -s "${ROOT}/CLAUDE.md" "${BDIR}/b02.json"
    ln -s "${ROOT}/research/proj" "${ROOT}/research/linkproj"
    mkdir -p "${ROOT}/scripts/scratch/p/data/adjudication_bundles"
    printf '{}\n' > "${ROOT}/scripts/scratch/p/data/adjudication_bundles/b01.json"
    export ROOT BDIR BUNDLE
    export CLAUDE_PROJECT_DIR="${ROOT}"
}

teardown() {
    common_teardown
}

# --- Fixture helpers ---

# A PreToolUse payload. $1 tool_name, $2 file_path, $3 agent_type (default
# citation-adjudicator). Case strings live INSIDE the suite, never on the
# invoking command line, so the live hooks never vet the test corpus.
_payload() {
    jq -nc --arg t "$1" --arg p "$2" --arg a "${3-citation-adjudicator}" '{
        "hook_event_name": "PreToolUse",
        "tool_name": $t,
        "agent_type": $a,
        "agent_id": "a0123456789abcdef",
        "tool_input": {"file_path": $p}
    }'
}

# Run the hook on stdin; stdout and stderr are kept apart because the deny
# contract puts JSON on one and the BLOCKED line on the other. Sets HOOK_RC,
# HOOK_OUT and HOOK_ERR. Extra arguments are a command prefix (e.g. env -i).
_hook() {
    HOOK_OUT="$("$@" "${BASH_BIN}" "${ADJUDICATOR_READ_SCOPE_SH}" 2>"${TEST_DIR}/stderr")" && HOOK_RC=0 || HOOK_RC=$?
    HOOK_ERR="$(cat "${TEST_DIR}/stderr")"
}

_read() {
    _hook < <(_payload Read "$1")
}

_assert_allow() {
    if [ "${HOOK_RC}" -ne 0 ] || [ -n "${HOOK_OUT}" ] || [ -n "${HOOK_ERR}" ]; then
        echo "want allow (exit 0, no output); got exit ${HOOK_RC}"
        echo "stdout: ${HOOK_OUT}"
        echo "stderr: ${HOOK_ERR}"
        return 1
    fi
}

# Deny = exit 2 AND exactly one JSON object on stdout carrying a PreToolUse
# deny with a non-empty reason AND the BLOCKED line on stderr.
_assert_deny() {
    if [ "${HOOK_RC}" -ne 2 ]; then
        echo "want exit 2; got ${HOOK_RC}"
        echo "stdout: ${HOOK_OUT}"
        echo "stderr: ${HOOK_ERR}"
        return 1
    fi
    [ -n "${HOOK_OUT}" ] || { echo "deny printed no JSON"; return 1; }
    printf '%s' "${HOOK_OUT}" | jq -e -s 'length == 1
        and .[0].hookSpecificOutput.hookEventName == "PreToolUse"
        and .[0].hookSpecificOutput.permissionDecision == "deny"
        and (.[0].hookSpecificOutput.permissionDecisionReason | length > 0)' >/dev/null \
        || { echo "stdout is not one PreToolUse deny object: ${HOOK_OUT}"; return 1; }
    case "${HOOK_ERR}" in
        "BLOCKED by adjudicator-read-scope hook"*) ;;
        *) echo "stderr lacks the BLOCKED line: ${HOOK_ERR}"; return 1 ;;
    esac
}

# A PATH folder for the dependency cases. $1 folder name, then the tools to
# link into it.
_bin() {
    local dir="${TEST_DIR}/$1" tool
    shift
    mkdir -p "${dir}"
    for tool in "$@"; do
        ln -s "$(command -v "${tool}")" "${dir}/${tool}"
    done
    printf '%s' "${dir}"
}

# =========================================================================
# Syntax
# =========================================================================

@test "adjudicator-read-scope.sh parses without errors" {
    run bash -n "${ADJUDICATOR_READ_SCOPE_SH}"
    assert_success
}

# =========================================================================
# Allowed: the bundle, and other agents' calls
# =========================================================================

@test "bundle path (allowed shape, exists): allow" {
    _read "${BUNDLE}"
    _assert_allow
}

@test "bundle path with offset/limit: allow" {
    _hook < <(jq -nc --arg p "${BUNDLE}" '{"tool_name":"Read","agent_type":"citation-adjudicator","agent_id":"a1","tool_input":{"file_path":$p,"offset":200,"limit":400}}')
    _assert_allow
}

@test "other agent_type (paper-reader) reading a project file: allow untouched" {
    _hook < <(_payload Read "${ROOT}/CLAUDE.md" paper-reader)
    _assert_allow
}

# =========================================================================
# Denied: paths that are not in plain form
# =========================================================================

@test "'..' escaping to /etc/passwd: deny" {
    _read "${BDIR}/../../../../../../../../../../etc/passwd"
    _assert_deny
}

@test "'..' that returns to the bundle: deny" {
    _read "${BDIR}/../adjudication_bundles/b01.json"
    _assert_deny
}

@test "'//' in the path: deny" {
    _read "${ROOT}/research/proj//data/adjudication_bundles/b01.json"
    _assert_deny
}

@test "symlinked bundle file pointing at a project file: deny" {
    _read "${BDIR}/b02.json"
    _assert_deny
    [[ "${HOOK_ERR}" == *"symlink"* ]]
}

@test "symlinked project folder whose target is the real bundle: deny" {
    _read "${ROOT}/research/linkproj/data/adjudication_bundles/b01.json"
    _assert_deny
    [[ "${HOOK_ERR}" == *"symlink"* ]]
}

@test "relative path: deny" {
    _read "research/proj/data/adjudication_bundles/b01.json"
    _assert_deny
    [[ "${HOOK_ERR}" == *"not absolute"* ]]
}

@test "trailing newline in file_path: deny" {
    _read "${BUNDLE}"$'\n'
    _assert_deny
}

# =========================================================================
# Denied: files in or near the bundles folder that are not a bundle
# =========================================================================

@test "prompt file beside the bundle (_prompt.txt): deny" {
    _read "${BDIR}/b01_prompt.txt"
    _assert_deny
}

@test "dot-file .json in the bundles folder: deny" {
    _read "${BDIR}/.hidden.json"
    _assert_deny
}

@test "directory named b03.json: deny" {
    _read "${BDIR}/b03.json"
    _assert_deny
}

@test "bundle-shaped but missing (b99.json): deny" {
    _read "${BDIR}/b99.json"
    _assert_deny
    [[ "${HOOK_ERR}" == *"no such bundle file"* ]]
}

# =========================================================================
# Denied: files outside the research folder
# =========================================================================

@test "file outside the DAAF root (/etc/passwd): deny" {
    _read "/etc/passwd"
    _assert_deny
}

@test "/tmp path with bundle shape: deny" {
    _read "/tmp/x/data/adjudication_bundles/b01.json"
    _assert_deny
}

@test "existing bundle-shaped file outside research/ (scripts/scratch): deny" {
    _read "${ROOT}/scripts/scratch/p/data/adjudication_bundles/b01.json"
    _assert_deny
    [[ "${HOOK_ERR}" == *"outside the DAAF research folder"* ]]
}

@test "project file outside the bundles folder (CLAUDE.md): deny" {
    _read "${ROOT}/CLAUDE.md"
    _assert_deny
}

@test "default DAAF root (no CLAUDE_PROJECT_DIR): /daaf/CLAUDE.md is denied" {
    _hook env -u CLAUDE_PROJECT_DIR < <(_payload Read "/daaf/CLAUDE.md")
    _assert_deny
    [[ "${HOOK_ERR}" == *"outside the DAAF research folder"* ]]
}

@test "deny reason opens with a plain sentence naming the blocked read" {
    _read "${ROOT}/CLAUDE.md"
    _assert_deny
    # The path in the reason is sanitized and cut at 200 characters, so only
    # the sentence frame is pinned.
    printf '%s' "${HOOK_OUT}" | jq -e --arg lead "The reference checker's read of /" \
        '.hookSpecificOutput.permissionDecisionReason | startswith($lead) and contains(" was blocked: ")' >/dev/null
}

@test "double quote and backslash in the path: deny, and the deny JSON stays valid" {
    _read '/daaf/research/x"y\z.json'
    _assert_deny
}

# =========================================================================
# Denied: malformed or unexpected input
# =========================================================================

@test "missing file_path: deny" {
    _hook <<<'{"tool_name":"Read","agent_type":"citation-adjudicator","agent_id":"a1","tool_input":{}}'
    _assert_deny
}

@test "file_path not a string: deny" {
    _hook <<<'{"tool_name":"Read","agent_type":"citation-adjudicator","agent_id":"a1","tool_input":{"file_path":42}}'
    _assert_deny
}

@test "missing tool_input: deny" {
    _hook <<<'{"tool_name":"Read","agent_type":"citation-adjudicator","agent_id":"a1"}'
    _assert_deny
}

@test "malformed JSON: deny" {
    _hook <<<'{"tool_name": "Read", "tool_input": {"file_path": '
    _assert_deny
}

@test "empty stdin: deny" {
    _hook < /dev/null
    _assert_deny
}

@test "two concatenated objects (bundle read + CLAUDE.md read): deny" {
    _hook < <(_payload Read "${BUNDLE}"; _payload Read "${ROOT}/CLAUDE.md")
    _assert_deny
}

@test "tool other than Read (Grep) by the adjudicator: deny" {
    _hook < <(jq -nc --arg d "${BDIR}" '{"tool_name":"Grep","agent_type":"citation-adjudicator","agent_id":"a1","tool_input":{"pattern":"x","path":$d}}')
    _assert_deny
    [[ "${HOOK_ERR}" == *"only the Read tool"* ]]
}

@test "tool other than Read (Write) by the adjudicator: deny" {
    _hook < <(_payload Write "${BUNDLE}")
    _assert_deny
}

@test "tool_name 'Read' plus newline: deny" {
    _hook < <(_payload $'Read\n' "${BUNDLE}")
    _assert_deny
}

@test "no agent_type (main thread) reading a project file: deny" {
    _hook < <(jq -nc --arg p "${ROOT}/CLAUDE.md" '{"tool_name":"Read","tool_input":{"file_path":$p}}')
    _assert_deny
}

# =========================================================================
# Denied: environments the hook cannot check (fail-closed)
# =========================================================================

@test "jq missing from PATH (bundle path): deny without jq" {
    local payload bindir
    payload="$(_payload Read "${BUNDLE}")"
    bindir="$(_bin nojq_bin cat realpath)"
    _hook env -i PATH="${bindir}" CLAUDE_PROJECT_DIR="${ROOT}" <<<"${payload}"
    # The hook builds its deny JSON without jq; the suite's own jq checks it.
    _assert_deny
    [[ "${HOOK_ERR}" == *"because jq, which the read-scope check needs, is not installed"* ]]
}

@test "realpath fails (bundle path): the ERR trap denies" {
    local payload bindir
    payload="$(_payload Read "${BUNDLE}")"
    bindir="$(_bin badrp_bin cat jq)"
    printf '#!/bin/sh\nexit 1\n' > "${bindir}/realpath"
    chmod +x "${bindir}/realpath"
    _hook env -i PATH="${bindir}" CLAUDE_PROJECT_DIR="${ROOT}" <<<"${payload}"
    _assert_deny
    [[ "${HOOK_ERR}" == *"unexpected error in the read-scope check (fail-closed)"* ]]
}

@test "CLAUDE_PROJECT_DIR=/ (a root of / would open everything): deny" {
    _hook env CLAUDE_PROJECT_DIR=/ < <(_payload Read "${BUNDLE}")
    _assert_deny
}

# =========================================================================
# Registration: agent-scoped, citation-adjudicator only
# =========================================================================

@test "registered in citation-adjudicator.md frontmatter with matcher \"\" (every tool)" {
    # Frontmatter = the lines between the first two '---' lines.
    run awk 'NR == 1 && /^---$/ { inside = 1; next } inside && /^---$/ { exit } inside { print }' "${ADJ_AGENT_FILE}"
    assert_success
    [[ "${output}" == *'command: "$CLAUDE_PROJECT_DIR/.claude/hooks/adjudicator-read-scope.sh"'* ]] || false
    [[ "${output}" == *'- matcher: ""'* ]] || false
    [[ "${output}" == *'PreToolUse:'* ]]
}

@test "registered by no other agent" {
    # The command: anchor skips prose that only names the hook (agents/README.md).
    run grep -l -E 'command:.*adjudicator-read-scope\.sh' "${REPO_ROOT}"/.claude/agents/*.md
    assert_success
    [ "${#lines[@]}" -eq 1 ]
    [ "${lines[0]}" = "${ADJ_AGENT_FILE}" ]
}

@test "NOT registered project-wide in settings.json" {
    run grep -c "adjudicator-read-scope" "${REPO_ROOT}/.claude/settings.json"
    # grep -c prints 0 and exits 1 when there are no matches
    [ "$output" = "0" ]
}
