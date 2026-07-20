#!/usr/bin/env bash
# ============================================================================
# DAAF Shared Function Library
# ============================================================================
# Reusable functions for DAAF host scripts. Source this file -- do not execute
# it directly.
#
# Usage:
#   DAAF_LIB_DIR="$(cd "$(dirname "$0")" && pwd)"
#   source "${DAAF_LIB_DIR}/daaf_lib.sh"
#
# Functions provided:
#   load_daaf_settings -- export the whitelisted DAAF_* vars (four multi-instance
#                         keys + the DAAF_DEV build flag + the DAAF_BRANCH updater
#                         ref + the DAAF_DATA_VOLUME_NAME data-volume override) from
#                         environment_settings.txt
#   resolve_data_volume_name -- echo the resolved data-volume name, honoring the
#                         optional DAAF_DATA_VOLUME_NAME full-name override
#   upsert_settings_key -- insert/update a single KEY=value line in a settings
#                         file (write counterpart to load_daaf_settings)
#   setup_colors    -- populate color variables (respects NO_COLOR + non-TTY)
#   open_url        -- open a URL in the default browser (best-effort)
#   check_port      -- test whether a port is listening inside the DAAF container
#   ensure_container -- start the DAAF container if it is not already running
#
# Supports DAAF_DRY_RUN=1 for CI smoke testing without Docker.
# ============================================================================

# Guard against double-sourcing
if [ "${_DAAF_LIB_LOADED:-}" = "1" ]; then
    return 0 2>/dev/null || true
fi
_DAAF_LIB_LOADED=1

# --- Multi-Instance / Build-Flag Settings Loader ---
# Bridge environment_settings.txt -> host shell environment for the seven
# whitelisted DAAF_* variables: the four multi-instance keys
# (DAAF_PROJECT_NAME, DAAF_PORT_MARIMO, DAAF_PORT_LOGVIEWER, DAAF_PORT_VSCODE)
# plus DAAF_DEV, the opt-in BUILD flag consumed as
# `--build-arg DAAF_DEV=${DAAF_DEV:-0}` in docker-compose.yml, plus DAAF_BRANCH,
# the updater's target ref (read env-only today; whitelisting it here lets a
# value persisted in environment_settings.txt reach update_daaf.sh), plus
# DAAF_DATA_VOLUME_NAME, the optional full-name override for the research-workspace
# data volume (consumed by resolve_data_volume_name below and by the backup /
# restore tools; whitelisting it lets a value persisted in the settings file reach
# those tools and compose interpolation of the external `daaf-data` volume). The
# build flag, branch ref, and data-volume override ride the same bridge for the
# same reason: env_file feeds the container env only, while compose interpolation
# (and build args) resolve from the host shell env.
#
# WHY THIS EXISTS: environment_settings.txt is wired into docker-compose.yml as a
# service-level `env_file`, which feeds the CONTAINER environment only. Docker
# Compose *variable interpolation* (the `${DAAF_PROJECT_NAME:-daaf}` /
# `${DAAF_PORT_*:-27xx}` substitutions in docker-compose.yml) is resolved from the
# HOST shell environment and the project-folder .env file -- NOT from env_file.
# So without this bridge, setting DAAF_PROJECT_NAME in environment_settings.txt
# would change the in-container env but leave the compose project name and
# published ports at their defaults. This function reads the whitelisted keys
# from the file and exports them so compose interpolation sees them.
#
# PARSING SAFETY: we deliberately do NOT `source`/`.` the file. It holds API keys
# with arbitrary characters (quotes, $, backticks, spaces) that would be
# interpreted by the shell -- a correctness and safety hazard. We extract only the
# seven known DAAF_* keys via a line-oriented grep/sed/case scan, stripping CR for
# CRLF tolerance (matches how the rest of the codebase handles container output).
#
# PRECEDENCE: an already-set shell environment variable WINS over the file value.
# This matches Docker Compose's own precedence (shell env > .env file) so running
# `DAAF_PORT_MARIMO=3000 bash daaf.sh` overrides the file exactly as bare compose
# would. Absent file = no-op (defaults in docker-compose.yml apply).
#
# Bash 3.2 safe: no associative arrays, no mapfile, no ${var,,}.
load_daaf_settings() {
    local settings_file="${1:-./environment_settings.txt}"

    # Absent file: nothing to do -- docker-compose.yml defaults apply.
    if [ ! -f "${settings_file}" ]; then
        return 0
    fi

    local key val line
    # Read line by line (Bash 3.2: while read, not mapfile). Strip CR so CRLF
    # files (Windows-edited) parse identically to LF files.
    while IFS= read -r line || [ -n "${line}" ]; do
        line="$(printf '%s' "${line}" | tr -d '\r')"
        # Skip blanks and comments before any parsing.
        case "${line}" in
            ''|'#'*) continue ;;
        esac
        # Only lines of the form KEY=VALUE for our seven known keys.
        case "${line}" in
            DAAF_PROJECT_NAME=*|DAAF_PORT_MARIMO=*|DAAF_PORT_LOGVIEWER=*|DAAF_PORT_VSCODE=*|DAAF_DEV=*|DAAF_BRANCH=*|DAAF_DATA_VOLUME_NAME=*)
                key="${line%%=*}"
                val="${line#*=}"
                # Strip one layer of surrounding quotes if present (tolerant of
                # DAAF_PROJECT_NAME="myname" style entries).
                case "${val}" in
                    \"*\") val="${val#\"}"; val="${val%\"}" ;;
                    \'*\') val="${val#\'}"; val="${val%\'}" ;;
                esac
                # Precedence: shell env wins. Only adopt the file value when the
                # variable is currently unset OR empty in the environment.
                if [ -z "${!key:-}" ]; then
                    export "${key}=${val}"
                fi
                ;;
            *) continue ;;
        esac
    done < "${settings_file}"

    return 0
}

# --- Data Volume Name Resolver ---
# Echo the Docker volume name that holds the DAAF research workspace (/daaf),
# honoring the optional DAAF_DATA_VOLUME_NAME full-name override.
#
# PRECEDENCE (printed to stdout, captured by callers via `$(resolve_data_volume_name)`):
#   1. DAAF_DATA_VOLUME_NAME, when set non-empty -> used VERBATIM as the full
#      volume name (no project prefix is added). This is the escape hatch for
#      pointing two installs at ONE shared workspace volume; it must match the
#      `name:` under the external `daaf-data` block in docker-compose.yml.
#   2. Otherwise "${DAAF_PROJECT_NAME:-daaf}_daaf-data" -- the Compose-prefixed
#      default. So an UNSET DAAF_DATA_VOLUME_NAME is byte-for-byte identical to the
#      historical hardcoded derivation, and a second instance with
#      DAAF_PROJECT_NAME=daaf2 still owns "daaf2_daaf-data".
# A set-but-EMPTY DAAF_DATA_VOLUME_NAME falls through to the derived default (the
# `:-` test treats empty and unset alike), matching how load_daaf_settings adopts
# a whitelisted key only when it is non-empty.
#
# The claude-config volume is deliberately NOT resolved here: per-install auth
# isolation is by design, so it keeps its project-prefixed default everywhere and
# has no analogous override.
#
# Callers that need a value persisted in environment_settings.txt to win should
# `load_daaf_settings` first (which bridges DAAF_DATA_VOLUME_NAME into the shell
# env), then call this. Bash 3.2 safe: pure parameter expansion, no arrays.
resolve_data_volume_name() {
    printf '%s\n' "${DAAF_DATA_VOLUME_NAME:-${DAAF_PROJECT_NAME:-daaf}_daaf-data}"
}

# --- Color Setup ---
# Populate global color variables for terminal output.
# Respects NO_COLOR (https://no-color.org/) and non-TTY contexts.
#
# shellcheck disable=SC2034  # color vars are consumed by the SOURCING script
# (daaf.sh reads ${GREEN}/${YELLOW}/${CYAN}/${BOLD}/${DIM}/${RESET}); this
# directive spans the whole function so both the default-empty block and the
# tput block are covered. ${RED} completes the standard palette for parity even
# though no caller reads it yet -- keeping the palette symmetric avoids a silent
# empty-string trap if an error path later references it.
setup_colors() {
    # Default: no colors
    RED=""
    GREEN=""
    YELLOW=""
    CYAN=""
    BOLD=""
    DIM=""
    RESET=""

    # Bail out if NO_COLOR is set (any value)
    if [ -n "${NO_COLOR:-}" ]; then
        return 0
    fi

    # Bail out if stdout is not a TTY
    if [ ! -t 1 ]; then
        return 0
    fi

    # Bail out if tput is not available
    if ! command -v tput >/dev/null 2>&1; then
        return 0
    fi

    # Set colors via tput (fail gracefully on any error)
    RED="$(tput setaf 1 2>/dev/null || true)"
    GREEN="$(tput setaf 2 2>/dev/null || true)"
    YELLOW="$(tput setaf 3 2>/dev/null || true)"
    CYAN="$(tput setaf 6 2>/dev/null || true)"
    BOLD="$(tput bold 2>/dev/null || true)"
    DIM="$(tput dim 2>/dev/null || true)"
    RESET="$(tput sgr0 2>/dev/null || true)"
}

# --- Browser Open ---
# Open a URL in the default browser. Best-effort convenience function.
# Always returns 0 -- failure to open is never fatal.
open_url() {
    local url="${1:?open_url requires a URL argument}"

    # Skip actual open in dry-run mode
    if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
        return 0
    fi

    # macOS
    if command -v open >/dev/null 2>&1; then
        open "${url}" >/dev/null 2>&1 || true
        return 0
    fi

    # WSL (Windows Subsystem for Linux)
    if [ -f /proc/version ] && grep -qi "microsoft" /proc/version 2>/dev/null; then
        if command -v wslview >/dev/null 2>&1; then
            wslview "${url}" >/dev/null 2>&1 || true
            return 0
        fi
    fi

    # Linux (X11/Wayland)
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "${url}" >/dev/null 2>&1 || true
        return 0
    fi

    # No opener available -- silent fallback
    return 0
}

# --- Port Check ---
# Check if a service is listening on a port inside the DAAF container.
# Returns 0 if listening, 1 otherwise.
#
# The probe reads /proc/net/tcp{,6} directly rather than shelling out to `ss`:
# the `ss` binary (iproute2) is NOT installed in the DAAF image, so the old
# iproute2-based probe always failed silently and check_port always returned 1.
# The /proc/net/tcp approach needs no extra binary and matches the pattern
# already proven in generate_log_viewer.sh and launch_code_server.sh. In that
# file, column 2 is "local_address" formatted as HEXIP:HEXPORT and column 4 is
# the socket state, where 0A means LISTEN. We match the listening port by its
# uppercase 4-hex-digit representation.
check_port() {
    local port="${1:?check_port requires a port number}"

    # In dry-run mode, consult DAAF_MOCK_PORTS instead of Docker
    if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
        if echo "${DAAF_MOCK_PORTS:-}" | grep -q "${port}:yes"; then
            return 0
        fi
        return 1
    fi

    # Query the container via /proc/net/tcp (fail-safe: assume not listening on
    # error). The remote script is passed fully single-quoted (so awk internals
    # and $1/$0 stay literal in the container shell); the port is passed as a
    # positional argument after the `bash -c '...' _ "$port"` sentinel, which
    # avoids brittle host-vs-remote quote interleaving. The awk END{exit !found}
    # idiom sets the exec exit code so the outer `if` reflects listening state.
    local probe='
        port="$1"
        ph=$(printf "%04X" "$port")
        awk -v ph="$ph" '\''$2 ~ ":"ph"$" && $4 == "0A" {found=1} END {exit !found}'\'' \
            /proc/net/tcp /proc/net/tcp6 2>/dev/null
    '
    if docker compose exec -T daaf-docker bash -c "$probe" _ "$port" </dev/null 2>/dev/null; then
        return 0
    fi

    return 1
}

# --- Container Check ---
# Ensure the DAAF container is running, starting it if necessary.
# Returns 0 when the container is running (already up or just started), 1 on
# failure. Callers gate on the return code (`if ! ensure_container; then ...`);
# there is no exported status variable (the PowerShell twin Confirm-DaafContainer
# likewise returns a boolean rather than setting a flag).
ensure_container() {
    # In dry-run mode, just pretend the container is running
    if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
        return 0
    fi

    # `docker compose ps -q daaf-docker` prints the container ID of the RUNNING
    # daaf-docker service (compose v2 lists running containers by default);
    # empty output means not running. This is derived from the compose project
    # rather than matching a hardcoded name, so it tracks DAAF_PROJECT_NAME.
    local cid
    cid=$(docker compose ps -q daaf-docker 2>/dev/null || true)

    if [ -n "${cid}" ]; then
        return 0
    fi

    # Attempt to start the container
    if docker compose up -d 2>/dev/null; then
        return 0
    fi

    return 1
}

# --- Settings-File Key Upsert ---
# Insert or update a single KEY=value line in a dotenv-style settings file
# (environment_settings.txt), preserving comments, key order, and surrounding
# layout. This is the WRITE counterpart to load_daaf_settings (which only reads).
#
# Usage:
#   upsert_settings_key <file> <key> <value> [mode] [backup_suffix]
#     mode:          "if-absent" (default) writes only when no active KEY= line
#                    exists; "replace" rewrites an existing active line's value.
#     backup_suffix: optional; when given (e.g. ".pre-update") a one-time backup
#                    copy <file><suffix> is made before the first write, and only
#                    if it does not already exist.
#
# Placement rules (git-config-style conservative default):
#   1. Active `KEY=` line present:
#        - if-absent -> leave untouched, report "skipped (exists)".
#        - replace   -> rewrite that line's value in place (position preserved;
#                       the surrounding comment lines are untouched).
#   2. No active line but a commented example (`#KEY=` / `# KEY=`, first match)
#      present -> insert the active line directly below the commented example.
#   3. Key absent entirely -> append at end under a dated provenance comment.
#
# ATOMICITY / ENCODING: writes to a temp file in the SAME directory (so the
# rename is atomic on one filesystem) then `mv -f`; the temp is a `cp -p` clone
# of the original so the file MODE is preserved without a non-portable `stat`.
# Output is LF-terminated and never carries a BOM; CR is stripped on read for
# CRLF-tolerance, so a Windows-edited file is normalized to LF.
#
# DRY-RUN: when DAAF_DRY_RUN=1, print the intended action and the exact line that
# WOULD be written, and touch nothing on disk (no temp, no backup, no rename) --
# satisfies FRAMEWORK_INTEGRATION_CHECKLIST item HSM5.
#
# Bash 3.2 safe: indexed arrays only (no mapfile / declare -A / ${var,,} /
# negative subscripts); portable date/cp; no GNU-only flags. Note: an inline
# trailing `# comment` on an active line being REPLACED is not preserved (the
# whole active line is rewritten) -- DAAF settings files never inline-comment
# active keys, and Compose's strict parser discourages it, so this is a
# documented, intentional limitation rather than a supported case.
#
# DUPLICATE KEYS (replace mode): "replace" updates the FIRST active `KEY=` line
# and assumes a single active occurrence per key. A settings file should never
# hold two active lines for the same key: Docker Compose's env_file ingestion is
# last-wins while DAAF's own loader (load_daaf_settings) is first-wins, so a
# duplicate already means the container and the host scripts would disagree on the
# value. If a file was hand-edited to contain duplicates, replace mode rewrites
# only the first and leaves later ones stale -- deduplicate the file by hand
# rather than relying on this function to reconcile it.
#
# SYMLINKED TARGET: the same-directory temp + atomic rename REPLACES the settings
# path with a freshly written regular file. If <file> is a symlink, the rename
# swaps the symlink itself for a regular file and the original link target is left
# untouched (stale) -- a symlinked environment_settings.txt is therefore not
# supported; point the tools at a real file.
upsert_settings_key() {
    local file key value mode backup_suffix
    file="${1:?upsert_settings_key requires a file path}"
    key="${2:?upsert_settings_key requires a key}"
    value="${3-}"
    mode="${4:-if-absent}"
    backup_suffix="${5:-}"

    if [ ! -f "${file}" ]; then
        echo "upsert_settings_key: ERROR: file not found: ${file}" >&2
        return 1
    fi

    # Read the file into an indexed array (Bash 3.2: while-read, not mapfile).
    # Strip a trailing CR so CRLF-edited files parse and rewrite as LF.
    local -a lines=()
    local _l
    while IFS= read -r _l || [ -n "${_l}" ]; do
        _l="${_l%$'\r'}"
        lines+=("${_l}")
    done < "${file}"

    # Locate the first active `KEY=` line and the first commented example.
    local active_idx=-1 comment_idx=-1 i line stripped
    for (( i=0; i<${#lines[@]}; i++ )); do
        line="${lines[$i]}"
        if [ "${active_idx}" -lt 0 ]; then
            case "${line}" in
                "${key}="*) active_idx=$i ;;
            esac
        fi
        if [ "${comment_idx}" -lt 0 ]; then
            case "${line}" in
                '#'*)
                    stripped="${line#\#}"
                    # Trim leading whitespace (Bash 3.2 safe parameter expansion).
                    stripped="${stripped#"${stripped%%[![:space:]]*}"}"
                    case "${stripped}" in
                        "${key}="*) comment_idx=$i ;;
                    esac
                    ;;
            esac
        fi
    done

    local new_line="${key}=${value}"
    local action=""
    local -a out=()

    if [ "${active_idx}" -ge 0 ]; then
        if [ "${mode}" != "replace" ]; then
            echo "upsert_settings_key: ${key} skipped (exists)"
            return 0
        fi
        if [ "${lines[$active_idx]}" = "${new_line}" ]; then
            echo "upsert_settings_key: ${key} unchanged (value already present)"
            return 0
        fi
        for (( i=0; i<${#lines[@]}; i++ )); do
            if [ "${i}" -eq "${active_idx}" ]; then
                out+=("${new_line}")
            else
                out+=("${lines[$i]}")
            fi
        done
        action="replaced"
    elif [ "${comment_idx}" -ge 0 ]; then
        for (( i=0; i<${#lines[@]}; i++ )); do
            out+=("${lines[$i]}")
            if [ "${i}" -eq "${comment_idx}" ]; then
                out+=("${new_line}")
            fi
        done
        action="inserted below commented example"
    else
        for (( i=0; i<${#lines[@]}; i++ )); do
            out+=("${lines[$i]}")
        done
        # Blank separator only when the file does not already end with one.
        if [ "${#out[@]}" -gt 0 ] && [ -n "${out[$(( ${#out[@]} - 1 ))]}" ]; then
            out+=("")
        fi
        out+=("# Added by DAAF on $(date +%Y-%m-%d)")
        out+=("${new_line}")
        action="appended (new)"
    fi

    # DRY-RUN: describe the write and touch nothing (HSM5).
    if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
        echo "[DRY-RUN] upsert_settings_key would write ${file}: ${action}"
        echo "[DRY-RUN]   line: ${new_line}"
        return 0
    fi

    # One-time backup (only when a suffix was given and no backup exists yet).
    if [ -n "${backup_suffix}" ] && [ ! -f "${file}${backup_suffix}" ]; then
        if ! cp -p "${file}" "${file}${backup_suffix}"; then
            echo "upsert_settings_key: ERROR: backup failed: ${file}${backup_suffix}" >&2
            return 1
        fi
    fi

    # Build the LF-terminated payload (one trailing LF, never a BOM).
    local payload="" ln
    for ln in "${out[@]}"; do
        payload="${payload}${ln}"$'\n'
    done

    # Atomic write: same-dir temp cloned for mode via cp -p, overwritten, then
    # renamed over the original. The temp is removed explicitly on any failure
    # (no global EXIT trap, so a caller's own trap is never clobbered).
    local dir tmp
    dir="$(dirname "${file}")"
    tmp="${dir}/.daaf_upsert.$$.${RANDOM}"
    if ! cp -p "${file}" "${tmp}"; then
        echo "upsert_settings_key: ERROR: could not create temp file in ${dir}" >&2
        rm -f "${tmp}"
        return 1
    fi
    if ! printf '%s' "${payload}" > "${tmp}"; then
        echo "upsert_settings_key: ERROR: write failed: ${tmp}" >&2
        rm -f "${tmp}"
        return 1
    fi
    if ! mv -f "${tmp}" "${file}"; then
        echo "upsert_settings_key: ERROR: rename failed: ${tmp} -> ${file}" >&2
        rm -f "${tmp}"
        return 1
    fi

    echo "upsert_settings_key: ${key} ${action}"
    return 0
}
