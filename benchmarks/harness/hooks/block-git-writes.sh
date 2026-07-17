#!/usr/bin/env bash
# block-git-writes.sh — env-gated PreToolUse hook that blocks git WRITE
# operations during benchmark runs.
#
# Benchmark models run via `claude -p ... --permission-mode bypassPermissions`
# (harness/executor.py), and the --disallowed-tools git patterns in
# harness/models.py are documented-ineffective: Claude Code splits compound
# commands on shell operators and checks each subcommand independently, and
# leading-* globs are prefix-anchored. Models under test have made rogue
# commits to the DAAF repository. This hook closes that gap at the hook layer,
# where the full compound command is visible as a single string.
#
# Scope gating: harness/executor.py sets DAAF_BENCHMARK_RUN=1 on the
# `claude -p` subprocess environment; every hook invocation in that run
# (including dispatched subagent sessions) inherits it. Normal DAAF sessions
# never set the variable, so this hook is an immediate no-op for them.
#
# Policy: default-deny any git invocation, with a read-only allowlist
# (status, log, diff, show, ls-files, rev-parse, bare/-v remote,
# bare/-a/--list branch, --version, help). For compound commands, EVERY git
# invocation in the string must be allowlisted or the whole command blocks.
# Unrecognized subcommands block (fail-closed).
#
# Exit codes (Claude Code PreToolUse convention):
#   0 = allow the command to proceed
#   2 = BLOCK the command (stderr message shown to the model)
#
# Hook event: PreToolUse (matcher: "Bash")
# Registered in: .claude/settings.json (user-applied registration; see
#                benchmarks/README.md § 9)

# Gate FIRST: outside benchmark runs this hook must be a near-zero-cost no-op.
[[ "${DAAF_BENCHMARK_RUN:-}" != "1" ]] && exit 0

# -e deliberately omitted: this hook inspects failures and decides exit codes
# itself (same pattern as bash-safety.sh). -E makes the ERR trap fire inside
# functions; -u and pipefail catch unbound variables and pipeline failures.
set -Euo pipefail

# Fail CLOSED: any unexpected error blocks the command. This hook protects
# repository integrity during benchmark runs — ambiguity must not allow writes.
trap 'echo "BLOCKED by benchmark git-write hook: unexpected error in safety check" >&2; exit 2' ERR

# --- Dependency check (fail-closed) ---
# Without jq, we cannot inspect the tool invocation JSON. Failing open would
# silently disable git-write protection for the entire benchmark run.
if ! command -v jq &>/dev/null; then
    echo "BLOCKED by benchmark git-write hook: jq is not installed (required for hook)" >&2
    exit 2
fi

INPUT=$(cat)

# Fail-closed on empty input: we cannot verify what would run.
if [[ -z "$INPUT" ]]; then
    echo "BLOCKED by benchmark git-write hook: empty hook input — cannot inspect command" >&2
    exit 2
fi

# Fail-closed on malformed JSON: jq exits non-zero on parse failure.
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null) || {
    echo "BLOCKED by benchmark git-write hook: malformed hook input JSON — cannot inspect command" >&2
    exit 2
}

# Only inspect Bash tool calls
if [[ "$TOOL_NAME" != "Bash" ]]; then
    exit 0
fi

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null) || {
    echo "BLOCKED by benchmark git-write hook: malformed tool_input JSON — cannot inspect command" >&2
    exit 2
}

# Normalize: collapse all whitespace (including newlines) to single spaces
NORM_CMD=$(echo "$CMD" | tr -s '[:space:]' ' ')

# ---------------------------------------------------------------------------
# block: descriptive stderr message + exit 2. The message identifies this as
# a benchmark-harness restriction (distinct from bash-safety) and tells the
# model what to do instead.
# ---------------------------------------------------------------------------
block() {
    echo "BLOCKED by benchmark git-write hook (block-git-writes.sh): $1" >&2
    echo "Git write operations are disabled during benchmark runs. Do not commit, stage, tag, branch, or otherwise modify the repository — complete your task without git and report results in your final response. Read-only git commands (status, log, diff, show, ls-files, rev-parse) remain available." >&2
    exit 2
}

# Fast path: no standalone "git" word anywhere — nothing to inspect
if ! echo "$NORM_CMD" | grep -qE '\bgit\b'; then
    exit 0
fi

# Compound-command handling: split on shell operators so EVERY git invocation
# is checked — `cd /tmp && git commit` must not evade inspection. Operators
# inside quoted strings also split; that can only cause a false BLOCK
# (fail-closed), never a false allow.
SEGMENTS=$(echo "$NORM_CMD" | sed -E 's/(&&|\|\||;|\|)/\n/g')

while IFS= read -r SEG; do
    # Segments without a git word need no inspection
    if ! echo "$SEG" | grep -qE '\bgit\b'; then
        continue
    fi

    # Take from the first standalone "git" token to the end of the segment.
    # This drops env-var assignment prefixes (VAR=1 git push) and absolute
    # paths (/usr/bin/git push) while keeping the git arguments intact.
    GIT_PART=$(echo "$SEG" | grep -oE '\bgit\b.*' | head -n 1) \
        || block "could not parse the git invocation in: $SEG"

    read -r -a TOKENS <<< "$GIT_PART"

    if [[ "${TOKENS[0]}" != "git" ]]; then
        # e.g. git-lfs, git-anything — not plain git; default-deny.
        block "unrecognized git-prefixed invocation: ${TOKENS[0]}"
    fi

    # Walk global options to find the subcommand. Any global option we do not
    # explicitly recognize becomes the "subcommand" and falls through to the
    # default-deny branch below (fail-closed).
    idx=1
    SUBCMD=""
    ntok=${#TOKENS[@]}
    while [[ $idx -lt $ntok ]]; do
        tok="${TOKENS[$idx]}"
        case "$tok" in
            -C|-c)
                # Global options that consume a value: git -C <path>, git -c k=v
                idx=$((idx + 2))
                ;;
            --no-pager)
                idx=$((idx + 1))
                ;;
            --version)
                SUBCMD="--version"
                break
                ;;
            --help)
                SUBCMD="help"
                break
                ;;
            *)
                SUBCMD="$tok"
                break
                ;;
        esac
    done

    case "$SUBCMD" in
        "")
            # Bare `git` (or only recognized global options): prints usage,
            # cannot write — allow.
            continue
            ;;
        status|log|diff|show|ls-files|rev-parse|help|--version)
            # Read-only subcommands — allowed with any arguments.
            continue
            ;;
        remote)
            # Read-only only when bare or -v/--verbose; add/remove/set-url
            # modify remote configuration.
            for arg in "${TOKENS[@]:$((idx + 1))}"; do
                case "$arg" in
                    -v|--verbose) ;;
                    *) block "'git remote ${arg}' can modify remote configuration; only bare 'git remote' or 'git remote -v' are permitted" ;;
                esac
            done
            continue
            ;;
        branch)
            # Read-only only when bare, -a, or --list; -d/-D/-m/name creation
            # all mutate branch state.
            for arg in "${TOKENS[@]:$((idx + 1))}"; do
                case "$arg" in
                    -a|--list) ;;
                    *) block "'git branch ${arg}' can create, rename, or delete branches; only bare 'git branch', 'git branch -a', or 'git branch --list' are permitted" ;;
                esac
            done
            continue
            ;;
        *)
            # Default-deny: everything not explicitly allowlisted blocks,
            # including unrecognized subcommands (fail-closed).
            block "'git ${SUBCMD}' is not on the read-only allowlist"
            ;;
    esac
done <<< "$SEGMENTS"

# ---------------------------------------------------------------------------
# Every git invocation in the command was read-only — allow
# ---------------------------------------------------------------------------
exit 0
