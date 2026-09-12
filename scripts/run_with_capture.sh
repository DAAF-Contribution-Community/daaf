#!/usr/bin/env bash
# =============================================================================
# run_with_capture.sh - Execute script with output capture and logging
# =============================================================================
#
# Usage: ./scripts/run_with_capture.sh <script_path>
#
# Supported languages: Python (.py), R (.R)
#
# This script:
# 1. Detects the script language from the file extension
# 2. Refuses to run a script that already carries an execution log
# 3. Scans the script body for runtime package-install calls (exit 3)
# 4. Creates a capture buffer NEXT TO the script (inside the project, so
#    partial output survives a fault or interruption inside the backup and
#    audit boundary)
# 5. Executes the script with the appropriate interpreter, tee-ing output
# 6. Records timestamp, duration, exit code, and CAPTURE STATUS
# 7. Appends the execution log to the script file and VERIFIES the record
#    landed (exactly one marker, closing banner present)
# 8. Returns the script's exit code -- or exit 74 when the audit record is
#    incomplete (see "Exit codes" below)
#
# Three outcomes are tracked separately and reported separately:
#   - COMPUTATION: the script's own exit code
#   - CAPTURE:     the tee into the capture buffer succeeded (stdout complete)
#   - PERSISTENCE: the execution log was appended and verified on disk
# Computation success alone is NEVER reported as "SUCCESS". A run is only a
# completed audited run when all three succeeded.
#
# Exit codes:
#   0     script exited 0 AND capture/persistence verified
#   N     script exited N (non-zero) AND capture/persistence verified
#   1     usage error, script not found, unsupported extension, or the script
#         already has an execution log (re-run refused)
#   3     pre-execution package-install scan blocked execution (no log appended)
#   74    EVIDENCE INCOMPLETE: capture buffer could not be created, the tee
#         failed, the append failed, or post-append verification failed.
#         The script's own exit code is stated in the banner. Any capture
#         buffer is RETAINED and its path printed. (74 = EX_IOERR from
#         sysexits; distinct from the reserved exit 3. A script may itself
#         exit 74, so key decisions off the EVIDENCE INCOMPLETE banner on
#         stderr, not the exit code alone.)
#   130/143  interrupted by SIGINT/SIGTERM. Normally no log has been appended
#         (script stays runnable in place); if the signal arrived after the
#         append but before verification, the banner says so and the record
#         must be treated as unverified. The capture buffer is RETAINED and
#         its path printed either way.
#
# Marker integrity: captured output lines are archived with a "# " prefix. A
# captured line that would then read exactly as the marker ("EXECUTION LOG")
# is archived with two spaces ("#  EXECUTION LOG") so script output can never
# forge a second marker (which would break the re-run guard, the revision
# utility, and post-append verification).
#
# Capture buffer: a dotfile `.<script>.capture.XXXXXX` in the script's own
# directory. Deleted after every VERIFIED run (success or script failure --
# the appended log is then the durable record). Retained only when the
# record could not be completed (exit 74 / interruption).
#
# Examples:
#   ./scripts/run_with_capture.sh scripts/stage5_fetch/01_fetch-ccd.py
#   ./scripts/run_with_capture.sh scripts/stage5_fetch/01_fetch-ccd.R
#
# =============================================================================

# -u: catch unset variables; -o pipefail: detect pipeline failures
# Deliberately omit -e: this script must capture non-zero exit codes from
# the target script it executes, not die on them.
set -uo pipefail

SCRIPT_PATH="${1:-}"

if [ -z "$SCRIPT_PATH" ]; then
    echo "Usage: $0 <script_path>" >&2
    echo "Example: $0 scripts/stage5_fetch/01_fetch-ccd.py" >&2
    exit 1
fi

if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Error: Script not found: $SCRIPT_PATH" >&2
    exit 1
fi

# Detect language from file extension
EXT="${SCRIPT_PATH##*.}"
case "$EXT" in
    py)
        INTERPRETER="python3"
        ;;
    R|r)
        INTERPRETER="Rscript"
        ;;
    *)
        echo "Error: Unsupported file extension: .$EXT" >&2
        echo "Supported: .py (Python), .R (R)" >&2
        exit 1
        ;;
esac

# Language-aware version suffix
BASE="${SCRIPT_PATH%.${EXT}}"

# Check if script already has an execution log
if grep -q "^# EXECUTION LOG" "$SCRIPT_PATH"; then
    echo "WARNING: Script already has an execution log." >&2
    echo "If you need to re-run with fixes, create a new version:" >&2
    echo "  bash /daaf/scripts/create_script_revision.sh $SCRIPT_PATH ${BASE}_a.${EXT}" >&2
    echo "Then run the new version." >&2
    exit 1
fi

# --- Pre-execution package-install content scan ------------------------------
# The container environment is defined entirely by the Dockerfile; a package
# installed at runtime creates unreproducible drift a rebuild silently reverts
# (see CLAUDE.md § Boundaries & Safety > Runtime Package Installation). The
# bash-safety.sh §8 hook blocks command-line installs, but it CANNOT see an
# install call written INSIDE a script — the dominant path for R
# (install.packages()) and a real path for Python (os.system("pip install ...")).
# This wrapper is the only chokepoint that sees the script body, so it scans it
# before executing. Full-line comments are excluded so a commented-out example
# does not false-block; an inline TRAILING comment that contains a token IS an
# accepted false positive (rare, and erring toward blocking is the safe default
# for a reproducibility guard). Scan tokens are extension-specific: R is
# case-sensitive so its tokens match case-sensitively (fewer false positives);
# Python tokens match case-insensitively and cover the common string call forms
# (os.system/subprocess("pip install ..."), pipx/uv subcommands) and the
# subprocess-LIST forms (["pip","install",...], ["uv","add",...],
# ["pipx","install",...]). ACCEPTED RESIDUALS (Python): exotic forms are not
# decoded — a package name built by variable interpolation or string-join, an
# importlib/__import__("pip")._internal call, uv/pipx spelled via an absolute
# path or a shell-var indirection, or an install verb split across list elements
# with unusual whitespace. These mirror the shell-hook §8 residual class and are
# accepted (the hook and, for coding agents, enforce-file-first.sh remain in
# depth behind this scan).
if [ "$EXT" = "py" ]; then
    SCAN_TOKENS="pip3? install|pip3?['\"], *['\"]install|pipx (install|run)|pipx['\"], *['\"](install|run)|uv (pip install|add|sync|tool install)|uv['\"], *['\"](add|sync|pip|tool)|easy_install|conda install"
    INSTALL_HITS=$(grep -inE "$SCAN_TOKENS" "$SCRIPT_PATH" | grep -vE '^[0-9]+:[[:space:]]*#' || true)
else
    SCAN_TOKENS='install\.packages\(|update\.packages\(|remove\.packages\(|remotes::install_|devtools::install_|install_(github|gitlab|bitbucket|cran|version|local|url|git|svn|bioc|dev)\(|pak::(pak|pkg_install)\(|pkg_install\(|renv::(install|restore|update|rebuild)\(|BiocManager::install\(|biocLite\('
    INSTALL_HITS=$(grep -nE "$SCAN_TOKENS" "$SCRIPT_PATH" | grep -vE '^[0-9]+:[[:space:]]*#' || true)
fi

if [ -n "$INSTALL_HITS" ]; then
    echo "============================================================" >&2
    echo "BLOCKED: run_with_capture.sh — runtime package install detected" >&2
    echo "============================================================" >&2
    echo "Offending line(s) in $SCRIPT_PATH:" >&2
    echo "$INSTALL_HITS" >&2
    echo "" >&2
    echo "WHY: This container's environment is defined entirely by its" >&2
    echo "Dockerfile. A package installed at runtime creates unreproducible" >&2
    echo "drift that a rebuild silently reverts (see CLAUDE.md § Boundaries &" >&2
    echo "Safety > Runtime Package Installation). A script must not install" >&2
    echo "packages as a side effect of being executed." >&2
    echo "" >&2
    echo "WHAT TO DO:" >&2
    echo "  1. Remove the install call from the script." >&2
    echo "  2. If the package is genuinely missing, STOP and report to the" >&2
    echo "     orchestrator/user so it can be added to the Dockerfile (the" >&2
    echo "     user additions block near the end) and the container rebuilt:" >&2
    echo "     exit the container, then run 'bash rebuild_daaf.sh'" >&2
    echo "     ('.\\rebuild_daaf.ps1' on Windows) from the daaf-docker folder." >&2
    echo "" >&2
    echo "NOTE: NO execution log was appended — immutable script versioning has" >&2
    echo "NOT engaged. You may edit THIS script file in place and re-run it once" >&2
    echo "the install call is removed (no _a/_b version needed)." >&2
    echo "============================================================" >&2
    exit 3
fi

# --- Capture buffer (project-local) ------------------------------------------
# The buffer lives NEXT TO the script, not in /tmp: /tmp is outside the backup
# and audit boundary, so a fault or interruption there would lose the only
# copy of partial output silently. RETAIN_BUFFER starts at 1 (fail-safe:
# retain) and is set to 0 only once the appended record has been verified.
SCRIPT_DIR=$(dirname "$SCRIPT_PATH")
SCRIPT_BASENAME=$(basename "$SCRIPT_PATH")
CAPTURE_BUF=""
RETAIN_BUFFER=1

# shellcheck disable=SC2329  # invoked via trap
cleanup_buffer() {
    if [ "$RETAIN_BUFFER" -eq 0 ] && [ -n "$CAPTURE_BUF" ]; then
        rm -f "$CAPTURE_BUF"
    fi
}
trap cleanup_buffer EXIT

# Interruption: append NO log (the script stays runnable in place -- no marker
# means "not yet executed" to the re-run guard), retain the buffer as the
# evidence of what had been produced, and exit with the signal's conventional
# code. Bash defers the trap until the foreground pipeline returns, so the
# buffer is quiescent when this runs.
# shellcheck disable=SC2329  # invoked via trap
on_signal() {
    local sig_name="$1" sig_num="$2"
    RETAIN_BUFFER=1
    echo "" >&2
    echo "============================================================" >&2
    echo "INTERRUPTED: run_with_capture.sh received SIG${sig_name}" >&2
    echo "============================================================" >&2
    # The signal may land after the append but before verification; say which.
    if grep -q "^# EXECUTION LOG" "$SCRIPT_PATH" 2>/dev/null; then
        echo "An execution log had ALREADY been appended before the signal arrived," >&2
        echo "but it was NOT verified. Treat this run as EVIDENCE INCOMPLETE:" >&2
        echo "immutable versioning has engaged, so create a clean revision and re-run:" >&2
        echo "  bash /daaf/scripts/create_script_revision.sh $SCRIPT_PATH ${BASE}_a.${EXT}" >&2
    else
        echo "No execution log was appended; the script remains runnable in place." >&2
    fi
    if [ -n "$CAPTURE_BUF" ] && [ -f "$CAPTURE_BUF" ]; then
        echo "Partial output retained at: $CAPTURE_BUF" >&2
    fi
    echo "============================================================" >&2
    exit $((128 + sig_num))
}
trap 'on_signal INT 2' INT
trap 'on_signal TERM 15' TERM

if ! CAPTURE_BUF=$(mktemp "${SCRIPT_DIR}/.${SCRIPT_BASENAME}.capture.XXXXXX"); then
    CAPTURE_BUF=""
    echo "============================================================" >&2
    echo "EVIDENCE INCOMPLETE: could not create capture buffer" >&2
    echo "============================================================" >&2
    echo "mktemp failed in: $SCRIPT_DIR" >&2
    echo "The script was NOT executed and no execution log was appended." >&2
    echo "Check that the script's directory is writable, then re-run." >&2
    echo "============================================================" >&2
    exit 74
fi

TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

echo "============================================================"
echo "EXECUTING: $SCRIPT_PATH"
echo "Started: $TIMESTAMP"
echo "============================================================"
echo ""

# --- Execute -----------------------------------------------------------------
# Timing in integer seconds (avoids bc dependency and macOS date +%N
# incompatibility). Both pipeline statuses are read: [0] is the script's own
# exit code (COMPUTATION), [1] is tee's (CAPTURE). Under the old single-status
# read a failed tee left a truncated buffer that was then archived as if it
# were the complete output.
START_TIME=$(date +%s)
"$INTERPRETER" "$SCRIPT_PATH" 2>&1 | tee "$CAPTURE_BUF"
PIPE_STATUS=("${PIPESTATUS[@]}")
END_TIME=$(date +%s)
EXIT_CODE="${PIPE_STATUS[0]}"
TEE_STATUS="${PIPE_STATUS[1]}"
DURATION=$((END_TIME - START_TIME))

# CAPTURE_OK is the boolean the success path keys on; CAPTURE_STATUS is the
# human/record text (which may carry a qualifier on a COMPLETE capture).
if [ "$TEE_STATUS" -eq 0 ] && [ -r "$CAPTURE_BUF" ]; then
    CAPTURE_OK=1
    CAPTURE_STATUS="COMPLETE"
    # NUL bytes cannot survive the shell string used to build the log block;
    # say so in the record rather than silently archiving a lossy copy. The
    # capture itself succeeded (the buffer is exact), so this stays a verified
    # run; the qualifier is disclosure, not a failure.
    NUL_COUNT=$(tr -cd '\000' < "$CAPTURE_BUF" | wc -c | tr -d ' ')
    if [ "$NUL_COUNT" -gt 0 ]; then
        CAPTURE_STATUS="COMPLETE (${NUL_COUNT} NUL byte(s) in output were stripped from the archived STDOUT)"
    fi
else
    CAPTURE_OK=0
    CAPTURE_STATUS="INCOMPLETE (tee exit ${TEE_STATUS})"
fi

echo ""
echo "============================================================"
echo "EXECUTION COMPLETE"
echo "Exit code: $EXIT_CODE"
echo "Duration: ${DURATION}s"
echo "Capture: $CAPTURE_STATUS"
echo "============================================================"

# --- Persist -----------------------------------------------------------------
# Every step that can fail is checked, and the record is verified on disk
# afterward. PERSIST_FAIL holds the first failure reason (empty = none).
echo ""
echo "Appending execution log to script..."
PERSIST_FAIL=""

# Pre-append re-check of the marker. A concurrent duplicate invocation of the
# same script passes the guard at the top and would append a second block;
# re-checking here narrows that window without any locking, and the
# post-append count below catches what slips through.
MARKER_COUNT=$(grep -c "^# EXECUTION LOG" "$SCRIPT_PATH")
if [ "$MARKER_COUNT" -ne 0 ]; then
    PERSIST_FAIL="an execution log appeared on the script during this run (marker count ${MARKER_COUNT}); a concurrent duplicate invocation is the likely cause"
fi

if [ -z "$PERSIST_FAIL" ]; then
    # Comment-prefix the captured output. Done as a checked step (not inside a
    # heredoc substitution, where a sed failure was invisible). The second
    # expression neutralizes a captured line that would otherwise read exactly
    # as the marker: script output must never forge "# EXECUTION LOG".
    if ! COMMENTED_OUTPUT=$(sed -e 's/^/# /' -e 's/^# EXECUTION LOG/#  EXECUTION LOG/' "$CAPTURE_BUF" 2>/dev/null); then
        PERSIST_FAIL="could not read/format the capture buffer (sed failed)"
    elif [ -z "$COMMENTED_OUTPUT" ]; then
        COMMENTED_OUTPUT="# (no output)"
    fi
fi

BANNER="# ============================================================================="
if [ -z "$PERSIST_FAIL" ]; then
    LOG_BLOCK=$(printf '%s\n' \
        "" \
        "" \
        "$BANNER" \
        "# EXECUTION LOG" \
        "$BANNER" \
        "#" \
        "# Executed: $TIMESTAMP" \
        "# Command: $INTERPRETER $SCRIPT_PATH" \
        "# Duration: ${DURATION}s" \
        "# Exit code: $EXIT_CODE" \
        "# Capture: $CAPTURE_STATUS" \
        "#" \
        "# --- STDOUT ---" \
        "$COMMENTED_OUTPUT" \
        "#" \
        "# --- STDERR ---" \
        "# (captured in STDOUT above via 2>&1)" \
        "#" \
        "$BANNER")
    if ! printf '%s\n' "$LOG_BLOCK" >> "$SCRIPT_PATH"; then
        PERSIST_FAIL="append to $SCRIPT_PATH failed (write error or permission denied)"
    fi
fi

# Post-append verification: the record must exist exactly once and be complete
# (closing banner is the last line -- a partial write, e.g. disk full, fails
# this). This is what turns "the append command ran" into "the record exists".
if [ -z "$PERSIST_FAIL" ]; then
    MARKER_COUNT=$(grep -c "^# EXECUTION LOG" "$SCRIPT_PATH")
    LAST_LINE=$(tail -n 1 "$SCRIPT_PATH")
    if [ "$MARKER_COUNT" -ne 1 ]; then
        PERSIST_FAIL="post-append verification failed: expected exactly 1 execution-log marker, found ${MARKER_COUNT}"
    elif [ "$LAST_LINE" != "$BANNER" ]; then
        PERSIST_FAIL="post-append verification failed: closing banner is not the last line (partial write?)"
    elif ! grep -q "^# Exit code: ${EXIT_CODE}$" "$SCRIPT_PATH"; then
        PERSIST_FAIL="post-append verification failed: exit-code line missing from the record"
    fi
fi

# --- Report ------------------------------------------------------------------
if [ -z "$PERSIST_FAIL" ] && [ "$CAPTURE_OK" -eq 1 ]; then
    # Fully audited run: the appended log is the durable record; the buffer
    # has done its job.
    RETAIN_BUFFER=0
    echo "Execution log appended to: $SCRIPT_PATH"
    if [ "$EXIT_CODE" -eq 0 ]; then
        echo ""
        echo "SUCCESS: Script passed."
    else
        echo ""
        echo "FAILED: Script returned exit code $EXIT_CODE"
        echo ""
        echo "Next steps:"
        echo "  1. Review the execution log appended to the script"
        echo "  2. Create a clean revision (strips the appended execution log):"
        echo "     bash /daaf/scripts/create_script_revision.sh $SCRIPT_PATH ${BASE}_a.${EXT}"
        echo "  3. Apply fixes to the new version"
        echo "  4. Run the new version:"
        echo "     bash /daaf/scripts/run_with_capture.sh ${BASE}_a.${EXT}"
    fi
    exit "$EXIT_CODE"
fi

# Evidence incomplete: computation may have succeeded, but the audit record
# did not. Never report SUCCESS; never delete the buffer; say exactly which
# outcome failed and where the evidence is.
RETAIN_BUFFER=1
echo "" >&2
echo "============================================================" >&2
echo "EVIDENCE INCOMPLETE: audited run NOT completed" >&2
echo "============================================================" >&2
echo "Computation: script exited $EXIT_CODE" >&2
echo "Capture:     $CAPTURE_STATUS" >&2
if [ -n "$PERSIST_FAIL" ]; then
    echo "Persistence: FAILED — $PERSIST_FAIL" >&2
else
    echo "Persistence: log appended and verified (but its Capture line reads: $CAPTURE_STATUS)" >&2
fi
echo "" >&2
echo "Capture buffer retained at: $CAPTURE_BUF" >&2
echo "" >&2
echo "WHAT THIS MEANS: the script's outputs (data files, figures) may be" >&2
echo "valid, but this run cannot be accepted as an audited run because its" >&2
echo "execution record is incomplete. Do not report it as SUCCESS." >&2
echo "" >&2
echo "WHAT TO DO:" >&2
if [ -n "$PERSIST_FAIL" ] && ! grep -q "^# EXECUTION LOG" "$SCRIPT_PATH"; then
    echo "  - No execution log was appended, so the script is still editable and" >&2
    echo "    runnable IN PLACE once the cause (see Persistence above) is fixed." >&2
else
    echo "  - An execution log IS present on the script (immutable versioning has" >&2
    echo "    engaged). Create a clean revision and re-run it:" >&2
    echo "    bash /daaf/scripts/create_script_revision.sh $SCRIPT_PATH ${BASE}_a.${EXT}" >&2
fi
echo "  - Keep the retained capture buffer as failure evidence; report the" >&2
echo "    exit-74 outcome and this banner to the orchestrator/user." >&2
echo "============================================================" >&2
exit 74
