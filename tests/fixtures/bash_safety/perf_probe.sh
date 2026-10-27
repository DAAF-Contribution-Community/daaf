#!/usr/bin/env bash
# perf_probe.sh -- timing guard for the bash-safety.sh PreToolUse hook (AD61).
#
# Usage: bash tests/fixtures/bash_safety/perf_probe.sh [HOOK_PATH]
#   HOOK_PATH defaults to <repo>/.claude/hooks/bash-safety.sh, resolved from
#   this file's own location, so it works in any checkout (CI, fresh clone).
#   Pass a staged draft's path to time the draft instead; keep a
#   bash-safety.site.sh beside the draft (without it the hook blocks every
#   command, and this probe's benign control fails).
# Called by: tests/bash/bash_safety.bats (perf AD61) and
#            scripts/test_safety_hooks.sh (PERF AD61).
#
# Why: settings.json gives the hook a 5 s timeout, and a TIMED-OUT command hook
# lets the tool call CONTINUE (Anthropic hooks docs) -- so a slow hook is a
# silent allow. This builds a ~20 kB command with 300 quoted spans and 20
# heredocs and asserts the hook returns in under 2 s.
#
# Provenance: copied 2026-09-26 from perf_probe_2026-09-18.sh in the
# 2026-09-18 Safety Hook Hardening framework-development workspace (which is
# git-excluded, so suites calling it there FAILED on a fresh clone / in CI).
# Changes from the original: hook path defaults repo-relative instead of to a
# workspace draft; strict preamble; the hook file must exist and must exit 0
# or 2 (a missing or crashing hook used to "pass" by returning fast); a benign
# control command must be ALLOWED first (2026-10-27, as in perf_gate.sh: a hook
# that blocks every command at once used to "pass" the same way).
#
# Exit: 0 = PERF PASS, 1 = PERF FAIL (slow, missing hook, unexpected rc, or a
# benign control command not allowed).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
HOOK="${1:-${REPO_ROOT}/.claude/hooks/bash-safety.sh}"

if [[ ! -f "$HOOK" ]]; then
    echo "PERF FAIL: hook not found: ${HOOK}" >&2
    exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
    echo "PERF FAIL: jq is required to build the hook's JSON envelope" >&2
    exit 1
fi

# Control: a benign command must be ALLOWED (rc=0). Without it, a hook that
# blocks EVERY command at once -- e.g. a draft bash-safety.sh tested without its
# bash-safety.site.sh beside it, which fails closed by design -- would return
# rc=2 fast and pass the timing check below without measuring anything.
json=$(jq -cn --arg c "echo perf-probe-control" '{tool_name:"Bash",tool_input:{command:$c}}')
rc=0
printf '%s' "$json" | bash "$HOOK" >/dev/null 2>&1 || rc=$?
printf 'control rc=%s\n' "$rc"
if [[ $rc -ne 0 ]]; then
    printf 'PERF FAIL: benign control command returned rc=%s (expected 0 = ALLOW); is bash-safety.site.sh beside the hook?\n' "$rc"
    exit 1
fi

# The prose in the heredoc bodies mentions dangerous verbs on purpose (heredoc
# classification must not be quadratic); it is assembled here, never typed on
# a command line the live hooks would vet.
cmd="echo start"
i=0
while [[ $i -lt 300 ]]; do
    cmd="${cmd} 'span number ${i} of prose padded out to widen the command string'"
    i=$((i + 1))
done
i=0
while [[ $i -lt 20 ]]; do
    cmd="${cmd}"$'\n'"cat <<'EOF' > notes${i}.md"$'\n'"prose line mentioning sudo and rm -rf / here"$'\n'"EOF"
    i=$((i + 1))
done
printf 'command bytes: %s\n' "${#cmd}"

json=$(jq -cn --arg c "$cmd" '{tool_name:"Bash",tool_input:{command:$c}}')
rc=0
start=$(date +%s%N)
printf '%s' "$json" | bash "$HOOK" >/dev/null 2>&1 || rc=$?
end=$(date +%s%N)
ms=$(( (end - start) / 1000000 ))
printf 'hook rc=%s elapsed_ms=%s\n' "$rc" "$ms"

if [[ $rc -ne 0 && $rc -ne 2 ]]; then
    echo "PERF FAIL: hook exited rc=${rc} (expected 0 or 2; the hook did not run to a verdict)"
    exit 1
fi
if [[ $ms -gt 2000 ]]; then
    echo "PERF FAIL: hook took ${ms} ms (> 2000 ms budget; settings.json timeout is 5 s and a timed-out hook ALLOWS)"
    exit 1
fi
echo "PERF PASS"
