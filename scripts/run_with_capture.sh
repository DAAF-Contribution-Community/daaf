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
# 3. Scans the script body for runtime package-install calls, for
#    environment-secret prints, and for the Literature Review commands that
#    record a researcher's decision (any of them refuses with exit 3)
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
#   3     pre-execution content scan blocked execution -- a package-install
#         call, an environment-secret print, or a researcher-decision command
#         (no log appended)
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

# Next unused revision name, printed in every "create a revision" command
# below so an agent can copy it as is. Revisions add one letter: 02_src.py ->
# 02_src_a.py -> 02_src_b.py (CLAUDE.md § Versioning & Naming). One trailing
# `_<letter>` is stripped to find the sequence's root, so a logged 02_src_a.py
# continues at 02_src_b.py. The root file is not required to exist: a
# Reproducibility copy 01_x_repro_a.py continues at 01_x_repro_b.py with no
# 01_x_repro.py beside it. Then the first letter whose file does not exist is
# taken, because create_script_revision.sh refuses an existing destination. A
# script whose own name ends in `_<letter>` gets a sibling name, never the
# name of an existing file.
BASE="${SCRIPT_PATH%.${EXT}}"
REV_ROOT="$BASE"
if [[ "$BASE" =~ _[a-z]$ ]]; then
    REV_ROOT="${BASE%_?}"
fi
NEXT_REVISION=""
for rev_letter in {a..z}; do
    if [ ! -e "${REV_ROOT}_${rev_letter}.${EXT}" ]; then
        NEXT_REVISION="${REV_ROOT}_${rev_letter}.${EXT}"
        break
    fi
done
if [ -z "$NEXT_REVISION" ]; then
    NEXT_REVISION="${REV_ROOT}_<next unused letter>.${EXT}"
fi

# Check if script already has an execution log
if grep -q "^# EXECUTION LOG" "$SCRIPT_PATH"; then
    echo "BLOCKED: This script was not run. It already has an execution log, which" >&2
    echo "stays as the record of that run." >&2
    echo "Detail: run_with_capture.sh — re-run refused (execution log present)" >&2
    echo "To run a fixed version, create a revision, apply your fixes to it, and run it:" >&2
    echo "  bash /daaf/scripts/create_script_revision.sh $SCRIPT_PATH $NEXT_REVISION" >&2
    echo "  bash /daaf/scripts/run_with_capture.sh $NEXT_REVISION" >&2
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
# for a reproducibility guard). All three scans run grep with -a (treat the
# file as text): without it, a single NUL byte anywhere in the script makes GNU
# grep classify the file as binary and print no matching lines, and the scans
# would silently pass. Scan tokens are extension-specific: R is
# case-sensitive so its tokens match case-sensitively (fewer false positives);
# Python tokens match case-insensitively and cover package installs AND
# removals, in the common string call forms (os.system/subprocess("pip install
# ..."), shlex.split("uv pip uninstall ...")) and the subprocess-LIST forms
# (["pip","uninstall",...], [sys.executable,"-m","pip","install",...],
# ["uv","pip","sync",...], ["uv","remove",...], ["pipx","install",...],
# ["conda","remove",...]). In the pip and uv list forms, quoted flag elements
# (`"-q"`, `"--quiet"`) between the command and its verb are skipped, as §8
# skips `-` options (["uv","pip","-q","sync",...], ["pip","-q","install",...]).
# Mutating verbs, close to the bash-safety.sh §8 lists (§8 also has pipx runpip
# and conda update/create; this scan adds uv tool uninstall|upgrade): pip/pip3
# install|uninstall (this also catches `python -m pip ...` and `uv pip
# install|uninstall`), pipx install|uninstall|run, uv pip
# install|uninstall|sync (sync can remove packages), uv add|remove|sync, uv
# tool install|uninstall|upgrade|run, easy_install, conda
# install|remove|uninstall. Read-only uv pip subcommands (compile, list,
# freeze, show, tree, check) are deliberately NOT tokens, in string or list
# form; the list form ["uv","tool",...] stays refused for every subcommand.
# ACCEPTED FALSE POSITIVE (Python, fail-closed): a line whose string literal
# merely HOLDS install-command text it never runs (e.g. a test fixture holding a
# Dockerfile `RUN uv pip install ...` line) is refused, because a line grep
# cannot tell a literal from a call. Workaround: keep such text in a non-.py
# data file the script reads.
# ACCEPTED RESIDUALS (Python): exotic forms are not decoded — a verb or
# command built by interpolation, concatenation or join ("uv pip " +
# "install"), an importlib/__import__("pip")._internal call, uv/pipx spelled
# via an absolute path or a shell-var indirection, a versioned pip3.N, a
# list verb held in a variable (["uv","pip",verb]), list concatenation
# (["uv","pip"] + ["install", ...]), a flag whose value is a separate element
# before the verb (["uv","pip","--python","3.12","install"]), or a list whose
# elements sit on separate lines or have unusual whitespace. Forms
# §8 blocks at the command line but this scan does not token (uvx, `uv run
# --with`, `python -m ensurepip`, conda update/create and conda env
# update/create) are residuals too. Nothing else catches these forms inside a
# script body: bash-safety.sh §8 and enforce-file-first.sh check only the Bash
# command line.
if [ "$EXT" = "py" ]; then
    # The Python SCAN_TOKENS is the four PY_*_TOKENS alternations joined with
    # `|`; PY_LIST_FLAGS (zero or more quoted `-...` list elements) is spliced
    # into the pip and uv list terms.
    PY_LIST_FLAGS="(['\"], *['\"]-[^'\"]*)*"
    PY_PIP_TOKENS="pip3? (install|uninstall)|pip3?${PY_LIST_FLAGS}['\"], *['\"](install|uninstall)"
    PY_PIPX_TOKENS="pipx (install|uninstall|run)|pipx['\"], *['\"](install|uninstall|run)"
    PY_UV_TOKENS="uv (pip (install|uninstall|sync)|add|remove|sync|tool (install|uninstall|upgrade|run))|uv${PY_LIST_FLAGS}['\"], *['\"]pip${PY_LIST_FLAGS}['\"], *['\"](install|uninstall|sync)|uv${PY_LIST_FLAGS}['\"], *['\"](add|remove|sync|tool)"
    PY_OTHER_TOKENS="easy_install|conda (install|remove|uninstall)|conda['\"], *['\"](install|remove|uninstall)"
    SCAN_TOKENS="${PY_PIP_TOKENS}|${PY_PIPX_TOKENS}|${PY_UV_TOKENS}|${PY_OTHER_TOKENS}"
    INSTALL_HITS=$(grep -ainE "$SCAN_TOKENS" "$SCRIPT_PATH" | grep -vE '^[0-9]+:[[:space:]]*#' || true)
else
    SCAN_TOKENS='install\.packages\(|update\.packages\(|remove\.packages\(|remotes::install_|devtools::install_|install_(github|gitlab|bitbucket|cran|version|local|url|git|svn|bioc|dev)\(|pak::(pak|pkg_install)\(|pkg_install\(|renv::(install|restore|update|rebuild)\(|BiocManager::install\(|biocLite\('
    INSTALL_HITS=$(grep -anE "$SCAN_TOKENS" "$SCRIPT_PATH" | grep -vE '^[0-9]+:[[:space:]]*#' || true)
fi

if [ -n "$INSTALL_HITS" ]; then
    echo "============================================================" >&2
    echo "BLOCKED: This script was not run. It installs, updates or removes" >&2
    echo "packages, which DAAF does only through the Dockerfile." >&2
    echo "Detail: run_with_capture.sh — runtime package install detected" >&2
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
    echo "  2. If the package is genuinely missing, STOP and report it to the" >&2
    echo "     orchestrator/user. To add it: put it in /daaf/Dockerfile (the" >&2
    echo "     user additions block near the end), exit the container, then" >&2
    echo "     choose 10) Rebuild Container in the DAAF Control Panel, or run" >&2
    echo "     'bash rebuild_daaf.sh' ('.\\rebuild_daaf.ps1' on Windows) from" >&2
    echo "     the daaf-docker folder." >&2
    echo "" >&2
    echo "NOTE: NO execution log was appended — immutable script versioning has" >&2
    echo "NOT engaged. You may edit THIS script file in place and re-run it once" >&2
    echo "the install call is removed (no _a/_b version needed)." >&2
    echo "============================================================" >&2
    exit 3
fi

# --- Pre-execution environment-secret print scan ------------------------------
# Everything a script prints is appended, permanently, to the script file as
# its execution log (and from there into backups and session archives). The
# container environment holds the user's real API keys, so a script that
# prints the environment -- typically a session "helpfully" dumping env vars
# while debugging -- writes secret values into a permanent audit artifact.
# Like the install scan above, this wrapper is the only chokepoint that sees
# the script BODY before it runs, so it refuses the obvious dump shapes on the
# same terms: exit 3, NO log appended, script editable in place, full-line
# comments excluded (an inline trailing comment IS an accepted false positive).
#
# SCOPE: catches the obvious, ACCIDENTAL dump -- it is not an adversarial
# control. All patterns match case-insensitively, deliberately erring toward
# blocking: Linux environment variable names ARE case-sensitive, but a
# lowercase `db_password` is as credential-like as `DB_PASSWORD`, and a
# case-folded function token only ever adds refusals. The refusal names the
# line NUMBER and category only, never the line text, so a hardcoded literal
# on the line is never echoed.
# DELIBERATE NON-MATCHES (narrowed on purpose, pinned as allow-controls in
# tests/bash/run_with_capture.bats): a credential read into a variable or a
# request header/body (`json.dumps({"api_key": os.environ[...]})`); presence
# and size checks (`"X" in os.environ`, `len(os.environ)`); environment copies
# handed to a subprocess (`os.environ.copy()`, `dict(os.environ, ...)`,
# `["env", "FOO=1", cmd]`); `json.dump` to a file; and `os.environ.items()` /
# `.values()` unless the same line also has an output sink (print/pprint/
# logging/logger/sys.std*.write/json.dumps) or is a `for ... in` loop header
# over them -- so the env-SCRUBBING idiom `{k: v for k, v in
# os.environ.items() if not k.endswith("_API_KEY")}`, which builds a child
# environment with the keys removed, runs.
# ACCEPTED RESIDUALS (documented, deliberately not chased with fragile
# regexes): a two-step leak (`key = os.environ[...]` or `vals =
# list(os.environ.values())` then `print(...)`) -- needs data-flow analysis;
# a lookup whose name is held in a variable or built by string ops; a print
# call split across lines; `from os import environ` / bare `getenv(` aliases;
# R `Sys.getenv(c(...))` vectors and auto-printing wrapped forms such as
# `(key <- Sys.getenv(...))`; env dumps written to a FILE rather than stdout;
# shell dumps spelled other than the forms below (e.g. `env -0`,
# `set -o posix; set`, absolute paths); logging libraries other than
# logging/logger. A line mentioning an allowlisted name in quotes is exempt
# from the credential-lookup category as a whole.
#
# SECRET-NAME-VOCAB v1 — keep identical in: output-scanner.sh, audit-log.sh, run_with_capture.sh
SECRET_NAME_VOCAB="KEY KEYS APIKEY TOKEN TOKENS SECRET SECRETS PASS PASSWORD PASSWD PASSPHRASE CREDENTIAL CREDENTIALS CREDS AUTH COOKIE COOKIES SESSION DSN PAT"
SECRET_NAME_ALLOWLIST="SSH_AUTH_SOCK DBUS_SESSION_BUS_ADDRESS SESSION_MANAGER XDG_SESSION_ID XDG_SESSION_TYPE XDG_SESSION_CLASS XDG_SESSION_DESKTOP CLAUDE_CODE_SESSION_ID"
# A NAME is credential-named when one of its underscore-delimited segments is
# in the vocabulary. Q matches either quote character around a literal name.
Q="[\"']"
SECRET_NAME_RE="([A-Za-z0-9]+_)*(${SECRET_NAME_VOCAB// /|})(_[A-Za-z0-9]+)*"
SECRET_ALLOW_RE="${Q}(${SECRET_NAME_ALLOWLIST// /|})${Q}"

# Record one category's hits as "line N: category" -- line numbers only; the
# matched text stays inside this function and is never printed. The third
# argument, when set, is an ERE whose matching lines are exempted.
SECRET_HITS=""
add_secret_hits() {
    local category="$1" regex="$2" exempt="${3:-}" matches ln _rest
    matches=$(grep -ainE "$regex" "$SCRIPT_PATH" | grep -vE '^[0-9]+:[[:space:]]*#' || true)
    if [ -n "$exempt" ] && [ -n "$matches" ]; then
        matches=$(printf '%s\n' "$matches" | grep -viE "$exempt" || true)
    fi
    [ -z "$matches" ] && return 0
    while IFS=: read -r ln _rest; do
        SECRET_HITS="${SECRET_HITS}  line ${ln}: ${category}"$'\n'
    done < <(printf '%s\n' "$matches")
}

# Shared shell-dump shape (both languages): the command string (or first list
# element) is exactly `env`, `set`, or `export -p` -- optionally piped -- and
# the call then closes or moves to a keyword argument (so `["env", "FOO=1",
# "cmd"]`, which RUNS cmd with a modified environment, is not flagged); or it
# starts with `printenv`, which only ever prints.
SHELL_DUMP_RE="${Q}((env|set|export -p)([[:space:]]*\|[^\"']*)?${Q}[[:space:]]*([])]|,[[:space:]]*[a-z_.]+[[:space:]]*=)|printenv\b)"

if [ "$EXT" = "py" ]; then
    PY_SINK="\b(print|pprint|logging\.[a-z_]+|logger\.[a-z_]+|sys\.std(out|err)\.write)\("
    # Whole mapping: os.environ (optionally wrapped in dict/str/repr, or as a
    # later argument / f-string field) passed straight to a sink or json.dumps,
    # NOT followed by a subscript or method (os.environ["HOME"] stays allowed).
    add_secret_hits "whole environment printed or serialized" \
        "\b(print|pprint|logging\.[a-z_]+|logger\.[a-z_]+|sys\.std(out|err)\.write|json\.dumps)\(([^)]*[,{][[:space:]]*)?((dict|str|repr)\([[:space:]]*)?os\.environ([^.[A-Za-z0-9_]|\.copy\(\)|$)"
    # Only with an output sink earlier on the same line, or as a `for ... in`
    # loop header (whose body typically prints); a comprehension that FILTERS
    # the environment (env scrubbing) is allowed -- see DELIBERATE NON-MATCHES.
    add_secret_hits "environment values iterated (os.environ.items/values)" \
        "\b(print|pprint|logging\.[a-z_]+|logger\.[a-z_]+|sys\.std(out|err)\.write|json\.dumps)\(.*os\.environ\.(items|values)\(|^[[:space:]]*(async[[:space:]]+)?for[[:space:]].*[[:space:]]in[[:space:]]+((sorted|list|tuple|enumerate)\([[:space:]]*)?os\.environ\.(items|values)\([[:space:]]*\)[[:space:]]*\)?[[:space:]]*:"
    add_secret_hits "credential-named variable printed or logged" \
        "${PY_SINK}.*(os\.environ\[|os\.environ\.get\(|os\.getenv\()[[:space:]]*${Q}${SECRET_NAME_RE}${Q}" \
        "$SECRET_ALLOW_RE"
    add_secret_hits "shell command that dumps the environment" \
        "\b(os\.(system|popen)|subprocess\.[a-z_]+)\([[:space:]]*\[?[[:space:]]*${SHELL_DUMP_RE}"
else
    add_secret_hits "all environment variables requested (Sys.getenv with no name)" \
        "Sys\.getenv\([[:space:]]*(\)|names[[:space:]]*=|unset[[:space:]]*=)"
    add_secret_hits "credential-named variable printed" \
        "\b(print|cat|message|writeLines)\(.*Sys\.getenv\([[:space:]]*(x[[:space:]]*=[[:space:]]*)?${Q}${SECRET_NAME_RE}${Q}" \
        "$SECRET_ALLOW_RE"
    # Rscript auto-prints a visible top-level value, so a line that is ONLY a
    # credential lookup prints the secret without any print() call.
    add_secret_hits "credential-named variable auto-printed (bare top-level lookup)" \
        "^[[:space:]]*Sys\.getenv\([[:space:]]*(x[[:space:]]*=[[:space:]]*)?${Q}${SECRET_NAME_RE}${Q}[^)]*\)[[:space:]]*;?[[:space:]]*(#.*)?$" \
        "$SECRET_ALLOW_RE"
    add_secret_hits "shell command that dumps the environment" \
        "\bsystem2?\([[:space:]]*(command[[:space:]]*=[[:space:]]*)?${SHELL_DUMP_RE}"
fi

if [ -n "$SECRET_HITS" ]; then
    echo "============================================================" >&2
    echo "BLOCKED: This script was not run. It appears to print environment" >&2
    echo "variables, which can hold your API keys, into its permanent execution log." >&2
    echo "Detail: run_with_capture.sh — environment-secret print detected" >&2
    echo "============================================================" >&2
    echo "Offending line(s) in $SCRIPT_PATH (line text withheld):" >&2
    printf '%s' "$SECRET_HITS" >&2
    echo "" >&2
    echo "WHY: Everything a script prints is appended permanently to the script" >&2
    echo "file as its execution log. This container's environment holds real" >&2
    echo "API keys and credentials, so printing environment variables would" >&2
    echo "write secret values into that permanent audit record (and from there" >&2
    echo "into backups and session archives)." >&2
    echo "" >&2
    echo "WHAT TO DO:" >&2
    echo "  1. Read the credential into a variable and pass it to the API --" >&2
    echo "     never print, log, or serialize it:" >&2
    echo "       Python: api_key = os.environ[\"X_API_KEY\"]   # then use api_key" >&2
    echo "       R:      key <- Sys.getenv(\"X_API_KEY\")       # then use key" >&2
    echo "  2. To confirm a credential is configured, print its PRESENCE, not" >&2
    echo "     its value:" >&2
    echo "       Python: print(\"X_API_KEY\" in os.environ)" >&2
    echo "       R:      has_key <- nzchar(Sys.getenv(\"X_API_KEY\"))   then  cat(has_key)" >&2
    echo "  3. Never dump the whole environment (os.environ, Sys.getenv()," >&2
    echo "     env/printenv) from a script." >&2
    echo "" >&2
    echo "NOTE: NO execution log was appended — immutable script versioning has" >&2
    echo "NOT engaged. You may edit THIS script file in place and re-run it once" >&2
    echo "the flagged line(s) are removed (no _a/_b version needed)." >&2
    echo "============================================================" >&2
    exit 3
fi

# --- Pre-execution researcher-decision scan -----------------------------------
# Four Literature Review commands record a researcher's own decision, bound to
# the researcher's words quoted verbatim: `lit_corpus adjudications
# record-human` (a citation decision), `lit_corpus adjudications
# untested-checker` (accepting, or withdrawing, a reference checker DAAF has
# not tested), `lit_verify settle ... --decision` (the researcher's comparison
# of readings with the PDF pages) and `lit_verify vision-override` (the
# researcher's choice for a PDF reader DAAF has not tested). The
# orchestrator runs each as its own Bash call after the researcher replies,
# and settings.json ask rules make that call prompt, so the researcher
# approves the command that shows their words. Called from a script, the
# command runs in a subprocess no permission rule sees, so this scan refuses
# the script on the same terms as the scans above: exit 3, NO log appended,
# script editable in place, full-line comments excluded. Both languages get
# the same case-sensitive rules (the CLIs take these words as written):
#   - record-human and untested-checker: any line holding the token
#     `record-human` or `untested-checker`, whether it reaches lit_corpus
#     through the .sh wrapper, the .py module or an imported module's
#     main([...]), in a command string, a list
#     (["adjudications", "record-human", ...]) or a variable. Neither needs
#     the tool's name on another line: both tokens are lit_corpus's own
#     subcommand names and occur in no other DAAF command, so a script that
#     reaches lit_corpus through a variable is caught too. A Python name
#     such as untested_checker (underscore) is not the token and runs.
#   - settle: the script names lit_verify on some line (wrapper, module or
#     import), one line holds the word `settle`, and one line holds a
#     decision flag: `--decision`, `--decision=...`, or any shorter prefix
#     down to `--d`, which argparse expands to --decision for settle. The
#     three may sit on different lines, so a list split across lines is
#     caught. `settle --list` passes no decision flag and runs.
#   - vision-override: the script names lit_verify on some line (as for
#     settle) and one line holds the word `vision-override`. Every level
#     (check, accept, withdraw) records a decision, so no flag is needed.
#     `lit_verify route --reader-model` records none and runs.
# ACCEPTED FALSE POSITIVES (fail-closed, as for the install scan): a string
# literal, docstring or inline trailing comment that holds these words
# without running them, such as a printed hint quoting the command or a
# MANIFEST filter on the command name "adjudications record-human".
# Workaround: keep such text in a data file the script reads.
# ACCEPTED RESIDUALS: a command name or flag built by concatenation or
# interpolation ("record-" + "human", or a flag made from a dict key), a
# script that imports a module and calls its internal functions directly
# (lit_corpus.cmd_adj_record_human(...), lit_corpus.cmd_adj_untested(...),
# lit_verify.run_settle(...), lit_verify.run_vision_override(...)), which
# pass the decision as a value rather than a command word or flag, a settle
# or vision-override call in a script that never names lit_verify, and a
# call made by another program the script runs. The ask rules and the
# orchestrator's instructions remain behind this scan.
DECISION_COMMENT_RE='^[0-9]+:[[:space:]]*#'
DECISION_HITS=$(grep -anE 'record-human|untested-checker' "$SCRIPT_PATH" | grep -vE "$DECISION_COMMENT_RE" || true)
LIT_VERIFY_LINES=$(grep -anE 'lit_verify' "$SCRIPT_PATH" | grep -vE "$DECISION_COMMENT_RE" || true)
if [ -n "$LIT_VERIFY_LINES" ]; then
    SETTLE_LINES=$(grep -anE '(^|[^A-Za-z0-9_-])settle([^A-Za-z0-9_-]|$)' "$SCRIPT_PATH" | grep -vE "$DECISION_COMMENT_RE" || true)
    DECISION_FLAG_LINES=$(grep -anE '(^|[^A-Za-z0-9_-])--d(e(c(i(s(i(o(n)?)?)?)?)?)?)?([^A-Za-z0-9_-]|$)' "$SCRIPT_PATH" | grep -vE "$DECISION_COMMENT_RE" || true)
    if [ -n "$SETTLE_LINES" ] && [ -n "$DECISION_FLAG_LINES" ]; then
        DECISION_HITS=$(printf '%s\n' "$DECISION_HITS" "$SETTLE_LINES" "$DECISION_FLAG_LINES" | grep -v '^$' | sort -t: -k1,1n -u)
    fi
    OVERRIDE_LINES=$(grep -anE '(^|[^A-Za-z0-9_-])vision-override([^A-Za-z0-9_-]|$)' "$SCRIPT_PATH" | grep -vE "$DECISION_COMMENT_RE" || true)
    if [ -n "$OVERRIDE_LINES" ]; then
        DECISION_HITS=$(printf '%s\n' "$DECISION_HITS" "$OVERRIDE_LINES" | grep -v '^$' | sort -t: -k1,1n -u)
    fi
fi

if [ -n "$DECISION_HITS" ]; then
    echo "============================================================" >&2
    echo "BLOCKED: This script was not run. It appears to run a command that" >&2
    echo "records a researcher's own decision, and only the orchestrator runs" >&2
    echo "those, after the researcher has replied." >&2
    echo "Detail: run_with_capture.sh — researcher decision command detected" >&2
    echo "============================================================" >&2
    echo "Offending line(s) in $SCRIPT_PATH:" >&2
    echo "$DECISION_HITS" >&2
    echo "" >&2
    echo "WHY: The orchestrator runs such a command as its own Bash call, so the" >&2
    echo "permission prompt shows the researcher their words before anything is" >&2
    echo "recorded. A script would skip that prompt. The scan reads lines, so it" >&2
    echo "cannot tell a call from text that only quotes the command. The" >&2
    echo "commands: lit_corpus adjudications record-human (a citation decision)," >&2
    echo "lit_corpus adjudications untested-checker (the researcher's choice about" >&2
    echo "an AI reference check DAAF has not tested), lit_verify settle with" >&2
    echo "--decision (the researcher's check of numbers the AI read from page" >&2
    echo "images against the PDF pages) and lit_verify vision-override (the" >&2
    echo "researcher's choice for an AI PDF reader DAAF has not tested)." >&2
    echo "" >&2
    echo "WHAT TO DO:" >&2
    echo "  1. If the script runs the command, remove the call. The orchestrator" >&2
    echo "     runs it itself, at the prompt, with the researcher's words quoted" >&2
    echo "     verbatim." >&2
    echo "  2. If a cited line only quotes the command (a printed hint, a filter" >&2
    echo "     on a MANIFEST row), move that text into a data file the script" >&2
    echo "     reads." >&2
    echo "  3. 'lit_verify settle --list' and 'lit_verify route --reader-model'" >&2
    echo "     record no decision and may stay in a script (a script that names" >&2
    echo "     lit_verify must not also hold the word vision-override). To test" >&2
    echo "     the recording commands, run their selftests" >&2
    echo "     (lit_corpus.sh selftest <SCRATCH_DIR>, lit_verify.sh selftest" >&2
    echo "     <SCRATCH_DIR>)." >&2
    echo "" >&2
    echo "NOTE: NO execution log was appended — immutable script versioning has" >&2
    echo "NOT engaged. You may edit THIS script file in place and re-run it once" >&2
    echo "the cited lines are changed (no _a/_b version needed)." >&2
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
        echo "  bash /daaf/scripts/create_script_revision.sh $SCRIPT_PATH $NEXT_REVISION" >&2
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
# exit code (COMPUTATION), [1] is tee's (CAPTURE). A failed tee leaves a
# truncated buffer, which must not be archived as the complete output.
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
        echo "     bash /daaf/scripts/create_script_revision.sh $SCRIPT_PATH $NEXT_REVISION"
        echo "  3. Apply fixes to the new version"
        echo "  4. Run the new version:"
        echo "     bash /daaf/scripts/run_with_capture.sh $NEXT_REVISION"
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
    echo "    bash /daaf/scripts/create_script_revision.sh $SCRIPT_PATH $NEXT_REVISION" >&2
fi
echo "  - Keep the retained capture buffer as failure evidence; report the" >&2
echo "    exit-74 outcome and this banner to the orchestrator/user." >&2
echo "============================================================" >&2
exit 74
