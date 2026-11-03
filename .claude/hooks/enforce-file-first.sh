#!/usr/bin/env bash
# enforce-file-first.sh — PreToolUse hook that blocks direct python/R execution
#
# Enforces the file-first execution protocol: all Python and R scripts must be
# executed via run_with_capture.sh, which appends an execution log to the
# script file as an immutable audit artifact. Direct `python`, `python3`,
# `Rscript`, and bare-`R` batch invocations bypass this audit trail and are
# blocked.
#
# Covered in both languages: quote-wrapped interpreter names ('R' -e x,
# "python3" -c x; the shell strips the quotes, so the patterns allow an
# optional quote around every interpreter name, cases ADV11) and a no-space
# stdin redirect (R --no-save<f.R, python3<f.py; `<` is a TRAIL character,
# cases ADV12). Not covered, in both languages: arguments built by xargs
# (echo f.R | xargs R -f), variable indirection (X=R; $X -e), copies of an
# interpreter under another name, Windows .exe suffixes (no such binaries on
# Linux), and interpreter-like tokens inside quoted string arguments, where
# the boundary scan is not quote-aware (this errs toward blocking).
#
# Exception: framework utility scripts in /daaf/scripts/ (e.g.,
# compare_execution_logs.py, normalize_project_dir.py) are standalone CLI
# tools, not pipeline scripts. They produce stdout output, not audit
# artifacts, and may be run directly. The WHITELIST block below states
# exactly which commands that covers.
#
# Fail-closed input: the hook BLOCKS (exit 2) when jq is missing, when stdin
# is empty, and when stdin is not exactly one JSON object (unparseable text,
# a bare scalar or array, whitespace only, or several concatenated JSON
# values). Without the single-object gate, malformed stdin makes every
# `jq -r` fail, TOOL_NAME resolves to "", and the non-Bash gate allows the
# call; a concatenated payload (a benign object followed by a Bash one)
# yields a multi-line TOOL_NAME that is not "Bash" either.
#
# Exit codes (Claude Code PreToolUse convention):
#   0 = allow the command to proceed
#   2 = BLOCK the command (stderr message shown to the model)
#
# Scope: Registered in agent frontmatter for all agents with shell access
#
# Hook event: PreToolUse (matcher: "Bash")

# Fail CLOSED: if anything unexpected goes wrong, block the command.
# This is an audit-trail enforcement hook — ambiguity must not silently allow bypass.
trap 'echo "BLOCKED by enforce-file-first hook: unexpected error in file-first check. The hook failed while checking this command, so the command was not run. Try the call again, in a simpler form if you can; if this keeps happening, tell the user, because the hook may need repair." >&2; exit 2' ERR

# --- Dependency check (fail-closed) ---
# jq is required for JSON parsing. If missing, block rather than silently allowing.
if ! command -v jq &>/dev/null; then
    echo "BLOCKED by enforce-file-first hook: jq is not installed (required for hook). This container is missing a standard tool, so every Bash command is blocked. Ask the user to rebuild the container: choose 10) Rebuild Container in the DAAF Control Panel." >&2
    exit 2
fi

INPUT=$(cat)

# --- Fail-closed on empty input ---
# Claude Code should always provide JSON. Empty stdin is abnormal.
if [[ -z "$INPUT" ]]; then
    echo "BLOCKED by enforce-file-first hook: received empty input (expected JSON). The problem is in the hook's input, not in your command. Try the call again; if this keeps happening, tell the user." >&2
    exit 2
fi

# --- Fail-closed on malformed input ---
# Claude Code always sends exactly one JSON object. Anything else (non-JSON
# text, a scalar/array, whitespace only, concatenated values) is abnormal and
# must not reach the `!= "Bash"` allow gate below, where a failed parse would
# read as "not a Bash call" and ALLOW. `-s` slurps every value on stdin so the
# count can be checked; jq exits non-zero on a parse error or a false result.
if ! printf '%s' "$INPUT" | jq -e -s 'length == 1 and (.[0] | type == "object")' >/dev/null 2>&1; then
    echo "BLOCKED by enforce-file-first hook: stdin is not a single JSON object (malformed hook input). The problem is in the hook's input, not in your command. Try the call again; if this keeps happening, tell the user." >&2
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
# output rather than audit artifacts.
#
# Allowed: `python`, `python3` or `Rscript` (a version suffix such as
# python3.12 included), then whitespace, then the path of a `.py` / `.R` file
# directly in ${CLAUDE_PROJECT_DIR:-/daaf}/scripts/: not in a subfolder of it
# (scripts/deploy_smoke/x.py is blocked), not in a research project's
# scripts/ folder, and with nothing between the interpreter and the path
# (`python3 -u /daaf/scripts/x.py` is blocked). The test is a substring match
# over the whole normalized command, and a match allows the whole command
# before any other check runs.
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
#                                 at execution; the hook must too)
#
# BLOCKS:
#   python script.py                      — direct execution, no audit trail
#   python3 -c "code"                     — interactive one-liner
#   python3.11 script.py                  — versioned interpreter
#   env python script.py                  — env wrapper
#   exec python3 script.py               — exec builtin
#   PYTHONPATH=/foo python script.py      — env var prefix
#   /usr/bin/python3 script.py            — absolute path
#   'python3' script.py                   — quote-wrapped interpreter
#   python3<script.py                     — no-space stdin redirect
#
# ALLOWS:
#   bash .../run_with_capture.sh script.py  — correct file-first pattern
#   python /daaf/scripts/utility.py         — whitelisted framework utility
#   pip list                                — package inspection
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
#             wrapped in single or double quotes
#   TRAIL:    followed by space, semicolon, end of string, or a no-space
#             stdin redirect '<'

PATTERN='(^|&&|\|\||;|\|)\s*'               # BOUNDARY
PATTERN+='([A-Za-z_][A-Za-z0-9_]*=[^ ]+ )*'  # PREFIX: zero or more VAR=val assignments
PATTERN+='(env|exec|command|eval|nohup|nice|time|strace)?\s*'  # PREFIX: optional wrapper
PATTERN+='["'\'']?(python3?[.0-9]*|[^ ]*\/python3?[.0-9]*)["'\'']?'  # PYTHON interpreter (quotes optional)
PATTERN+='(\s|;|$|<)'                        # TRAIL (incl. no-space stdin redirect)

if echo "$NORM_CMD" | grep -qE "$PATTERN"; then
    cat >&2 <<'EOF'
BLOCKED by enforce-file-first hook: Direct python execution violates the file-first protocol: write the code to a script file and run it with run_with_capture.sh.

All Python scripts must be executed via run_with_capture.sh:
  bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/{script}.py

This ensures execution output is captured and appended to the script file
as an immutable audit trail. See agent_reference/SCRIPT_EXECUTION_REFERENCE.md
for details.

If you need to write a quick check, write it as a script file first,
then execute it through the capture wrapper.

If this was a search, not a run (for example grep -E 'a|python3 x'), the hook
read the | inside the pattern as a pipe: pass each alternative as its own -e
pattern instead (grep -n -e 'a' -e 'python3 x').

Exception: a script directly in /daaf/scripts/ (not in a subfolder) may be
run directly, with its path right after the interpreter
(e.g., python3 /daaf/scripts/compare_execution_logs.py ...).
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
#   /usr/bin/Rscript            — absolute path variants
#   R                          — bare interpreter: batch-capable via
#                                 `R -e`, `R -f`, `R CMD BATCH`, and
#                                 input-redirection flags (--no-save, --vanilla, ...)
#   /usr/local/bin/R            — absolute path variant of bare R
#   'R' / "Rscript"            — quote-wrapped interpreter (shell strips quotes
#                                 at execution; the hook must too)
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
#   'R' -e 'code'                         — quote-wrapped interpreter
#   R --no-save<script.R                  — no-space redirected batch
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
BLOCKED by enforce-file-first hook: Direct R execution violates the file-first protocol: write the code to a script file and run it with run_with_capture.sh.

All R scripts must be executed via run_with_capture.sh:
  bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/{script}.R

This applies to ALL R batch entry points: Rscript, `R -e`, `R -f`,
`R CMD BATCH`, and redirected `R --no-save` / `R --vanilla` invocations.

This ensures execution output is captured and appended to the script file
as an immutable audit trail. See agent_reference/SCRIPT_EXECUTION_REFERENCE.md
for details.

If you need to write a quick check, write it as a script file first,
then execute it through the capture wrapper.

If this was a search, not a run (for example grep -E 'a|Rscript x'), the hook
read the | inside the pattern as a pipe: pass each alternative as its own -e
pattern instead (grep -n -e 'a' -e 'Rscript x').

Exception: a script directly in /daaf/scripts/ (not in a subfolder) may be
run directly, with its path right after the interpreter
(e.g., Rscript /daaf/scripts/decompile_notebook.R ...).
EOF
    exit 2
fi

# ---------------------------------------------------------------------------
# All checks passed — allow the command
# ---------------------------------------------------------------------------
exit 0
