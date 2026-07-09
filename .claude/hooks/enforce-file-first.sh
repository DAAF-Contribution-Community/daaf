#!/usr/bin/env bash
# enforce-file-first.sh — PreToolUse hook that blocks direct python/R execution
#
# [SESSION E STAGED PATCH — 2026-07-07]
# Staged copy for MANUAL HUMAN DEPLOYMENT. Diff vs the live hook closes two
# bypass classes found by the Session E live probe matrix, symmetrically for
# Python and R:
#   ADV11 — quote-wrapped interpreter tokens ('R' -e 'x', "python3" -c 'x'):
#           optional ["']? added around every interpreter alternation.
#   ADV12 — no-space stdin redirect (R --no-save<foo.R, python3<foo.py):
#           '<' added to every TRAIL alternation.
# Deliberately NOT addressed (documented residuals, symmetric across both
# languages): xargs-style argument injection (echo foo.R | xargs R -f),
# variable indirection (X=R; $X -e), interpreter copies under other names,
# Windows .exe suffixes (binaries absent on Linux), and quote-unaware
# boundary scanning inside string arguments (pre-existing, fail-closed
# direction only).
#
# Enforces the file-first execution protocol: all Python and R scripts must be
# executed via run_with_capture.sh, which appends an execution log to the
# script file as an immutable audit artifact. Direct `python`, `python3`,
# `Rscript`, and bare-`R` batch invocations bypass this audit trail and are
# blocked.
#
# Exception: Framework utility scripts in /daaf/scripts/ (e.g.,
# compare_execution_logs.py, normalize_project_dir.py) are standalone CLI
# tools, not pipeline scripts. They produce stdout output, not audit
# artifacts, and may be run directly.
#
# Exit codes (Claude Code PreToolUse convention):
#   0 = allow the command to proceed
#   2 = BLOCK the command (stderr message shown to the model)
#
# Scope: Registered in agent frontmatter for coding agents only
#   (research-executor, code-reviewer, debugger, data-ingest)
#   NOT registered project-wide — non-coding agents and the orchestrator
#   are not subject to this constraint.
#
# Hook event: PreToolUse (matcher: "Bash")

# Fail CLOSED: if anything unexpected goes wrong, block the command.
# This is an audit-trail enforcement hook — ambiguity must not silently allow bypass.
trap 'echo "BLOCKED by enforce-file-first hook: unexpected error in file-first check" >&2; exit 2' ERR

# --- Dependency check (fail-closed) ---
# jq is required for JSON parsing. If missing, block rather than silently allowing.
if ! command -v jq &>/dev/null; then
    echo "BLOCKED by enforce-file-first hook: jq is not installed (required for hook)" >&2
    exit 2
fi

INPUT=$(cat)

# --- Fail-closed on empty input ---
# Claude Code should always provide JSON. Empty stdin is abnormal.
if [[ -z "$INPUT" ]]; then
    echo "BLOCKED by enforce-file-first hook: received empty input (expected JSON)" >&2
    exit 2
fi

# Only inspect Bash tool calls
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null) || TOOL_NAME=""
if [[ "$TOOL_NAME" != "Bash" ]]; then
    exit 0
fi

# Extract the command string
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null) || CMD=""
if [[ -z "$CMD" ]]; then
    exit 0
fi

# ---------------------------------------------------------------------------
# Normalize the command for reliable pattern matching:
#   1. Replace newlines with semicolons (newlines are command separators in bash,
#      but tr would merge them with spaces, hiding multi-command inputs)
#   2. Collapse remaining whitespace to single spaces
# ---------------------------------------------------------------------------
NORM_CMD=$(echo "$CMD" | tr '\n' ';' | tr -s '[:space:]' ' ')

# ---------------------------------------------------------------------------
# WHITELIST: Framework utility scripts in /daaf/scripts/
#
# These are standalone CLI tools (not pipeline scripts) that produce stdout
# output rather than audit artifacts. They may be run directly by any agent.
#
# The whitelist checks for python/python3/Rscript invocations that target a
# file within the /daaf/scripts/ directory (the framework root, NOT a research
# project's scripts/ directory).
# ---------------------------------------------------------------------------
DAAF_ROOT="${CLAUDE_PROJECT_DIR:-/daaf}"
if echo "$NORM_CMD" | grep -qE "python3?[.0-9]*\s+${DAAF_ROOT}/scripts/[A-Za-z0-9_-]+\.py"; then
    exit 0
fi
if echo "$NORM_CMD" | grep -qE "Rscript[.0-9]*\s+${DAAF_ROOT}/scripts/[A-Za-z0-9_-]+\.R"; then
    exit 0
fi

# ---------------------------------------------------------------------------
# Detect python/python3 invoked as a command. The regex accounts for:
#
# Command boundaries (where a new command can begin):
#   ^          — start of input
#   && || ; |  — shell chain/pipe operators
#
# Command prefixes (wrappers that still execute the next argument):
#   env, exec, command, eval, nohup, nice, time, strace
#   VAR=value  — environment variable assignment prefix (PYTHONPATH=/x python ...)
#
# Python interpreter names:
#   python, python3            — standard names
#   python3.11, python3.12     — versioned interpreters (python3?[.0-9]*)
#   /usr/bin/python3           — absolute path variants
#   'python3' / "python"       — quote-wrapped interpreter (shell strips quotes
#                                 at execution; the hook must too) [SESSION E]
#
# BLOCKS:
#   python script.py                      — direct execution, no audit trail
#   python3 -c "code"                     — interactive one-liner
#   python3.11 script.py                  — versioned interpreter
#   env python script.py                  — env wrapper
#   exec python3 script.py               — exec builtin
#   PYTHONPATH=/foo python script.py      — env var prefix
#   /usr/bin/python3 script.py            — absolute path
#   'python3' script.py                   — quote-wrapped interpreter [SESSION E]
#   python3<script.py                     — no-space stdin redirect  [SESSION E]
#
# ALLOWS:
#   bash .../run_with_capture.sh script.py  — correct file-first pattern
#   python /daaf/scripts/utility.py         — whitelisted framework utility
#   pip install polars                      — package management
#   marimo run notebook.py                  — marimo runtime
#   grep python file.txt                   — python as argument, not command
#   grep "python3 -c" file.txt             — interpreter-like token inside a
#                                             string argument (no boundary)
#   ls /usr/lib/python3/dist-packages      — python in path argument
# ---------------------------------------------------------------------------

# Pattern components (composed for readability):
#   BOUNDARY: start of command or after chain operators
#   PREFIX:   optional command wrappers and env var assignments
#   PYTHON:   interpreter name (bare, versioned, or absolute path), optionally
#             wrapped in single or double quotes [SESSION E]
#   TRAIL:    followed by space, semicolon, end of string, or a no-space
#             stdin redirect '<' [SESSION E]

PATTERN='(^|&&|\|\||;|\|)\s*'               # BOUNDARY
PATTERN+='([A-Za-z_][A-Za-z0-9_]*=[^ ]+ )*'  # PREFIX: zero or more VAR=val assignments
PATTERN+='(env|exec|command|eval|nohup|nice|time|strace)?\s*'  # PREFIX: optional wrapper
PATTERN+='["'\'']?(python3?[.0-9]*|[^ ]*\/python3?[.0-9]*)["'\'']?'  # PYTHON interpreter (quotes optional)
PATTERN+='(\s|;|$|<)'                        # TRAIL (incl. no-space stdin redirect)

if echo "$NORM_CMD" | grep -qE "$PATTERN"; then
    cat >&2 <<'EOF'
BLOCKED by enforce-file-first hook: Direct python execution violates the file-first protocol.

All Python scripts must be executed via run_with_capture.sh:
  bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/{script}.py

This ensures execution output is captured and appended to the script file
as an immutable audit trail. See SCRIPT_EXECUTION_REFERENCE.md for details.

Exception: Framework utility scripts in /daaf/scripts/ may be run directly
(e.g., python /daaf/scripts/compare_execution_logs.py ...).

If you need to write a quick check, write it as a script file first,
then execute it through the capture wrapper.
EOF
    exit 2
fi

# ---------------------------------------------------------------------------
# Detect R execution invoked as a command. Same philosophy as Python detection:
# block direct execution, require run_with_capture.sh wrapper.
#
# R interpreter entry points (BOTH must be covered — R ships two batch-capable
# binaries):
#   Rscript                    — standard non-interactive script runner
#   Rscript.exe                — Windows variant (unlikely but defensive)
#   /usr/bin/Rscript            — absolute path variants
#   R                          — bare interpreter: batch-capable via
#                                 `R -e`, `R -f`, `R CMD BATCH`, and
#                                 input-redirection flags (--no-save, --vanilla, ...)
#   /usr/local/bin/R            — absolute path variant of bare R
#   'R' / "Rscript"            — quote-wrapped interpreter (shell strips quotes
#                                 at execution; the hook must too) [SESSION E]
#
# The bare-R alternative requires the SAME boundary structure as Rscript
# (start/chain-operator boundary, optional env-assignment + wrapper prefix)
# and then `R` followed by whitespace and a batch-execution flag. Requiring
# the flag prevents false positives on `R` as an ordinary argument
# (`grep R file`, `git log -R`, `FOO=R bash x`) and leaves harmless probes
# (`R --version`, `R --help`, `R RHOME`) unblocked.
#
# BLOCKS:
#   Rscript script.R                      — direct execution, no audit trail
#   Rscript -e "code"                     — interactive one-liner
#   env Rscript script.R                  — env wrapper
#   /usr/bin/Rscript script.R             — absolute path
#   R_LIBS=/foo Rscript script.R          — env var prefix
#   R -e 'code'                           — bare-R one-liner
#   R -f script.R                         — bare-R script file
#   R CMD BATCH script.R                  — batch execution (and other R CMD tools)
#   R --no-save < script.R                — redirected batch execution
#   R --vanilla < script.R                — redirected batch execution
#   /usr/local/bin/R -e 'code'            — absolute-path bare R
#   'R' -e 'code'                         — quote-wrapped interpreter [SESSION E]
#   R --no-save<script.R                  — no-space redirected batch [SESSION E]
#
# ALLOWS:
#   bash .../run_with_capture.sh script.R  — correct file-first pattern
#   Rscript /daaf/scripts/utility.R        — whitelisted framework utility
#   grep Rscript file.txt                 — Rscript as argument, not command
#   grep R file.txt                       — R as argument, not command
#   grep "R -e" notes.md                  — interpreter-like token inside a
#                                            string argument (no boundary)
#   git log -R                            — R inside another command's flag
#   FOO=R bash x                          — R as env var value
#   R --version                           — harmless interpreter probe
#   install.packages("sf")               — not an R invocation
# ---------------------------------------------------------------------------

RPATTERN='(^|&&|\|\||;|\|)\s*'               # BOUNDARY
RPATTERN+='([A-Za-z_][A-Za-z0-9_]*=[^ ]+ )*'  # PREFIX: zero or more VAR=val assignments
RPATTERN+='(env|exec|command|eval|nohup|nice|time|strace)?\s*'  # PREFIX: optional wrapper
RPATTERN+='(["'\'']?(Rscript[.0-9]*|[^ ]*\/Rscript[.0-9]*)["'\'']?(\s|;|$|<)'    # Rscript interpreter (quotes optional) + TRAIL
RPATTERN+='|["'\'']?(R|[^ ]*\/R)["'\'']?\s+(CMD|-e|-f|--no-save|--vanilla|--no-restore|--no-echo|--slave|--silent|--quiet|-q|--no-init-file|--no-environ|--no-site-file)(\s|;|$|<))'  # bare R (quotes optional) + batch flag + TRAIL

if echo "$NORM_CMD" | grep -qE "$RPATTERN"; then
    cat >&2 <<'EOF'
BLOCKED by enforce-file-first hook: Direct R execution violates the file-first protocol.

All R scripts must be executed via run_with_capture.sh:
  bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/{script}.R

This applies to ALL R batch entry points: Rscript, `R -e`, `R -f`,
`R CMD BATCH`, and redirected `R --no-save` / `R --vanilla` invocations.

This ensures execution output is captured and appended to the script file
as an immutable audit trail. See SCRIPT_EXECUTION_REFERENCE.md for details.

Exception: Framework utility scripts in /daaf/scripts/ may be run directly
(e.g., Rscript /daaf/scripts/utility.R ...).

If you need to write a quick check, write it as a script file first,
then execute it through the capture wrapper.
EOF
    exit 2
fi

# ---------------------------------------------------------------------------
# All checks passed — allow the command
# ---------------------------------------------------------------------------
exit 0
