#!/usr/bin/env bash
# =============================================================================
# start_shim.sh — idempotent lifecycle manager for the Anthropic->OpenAI shim.
#
# The shim (anthropic_openai_shim.py) translates Anthropic Messages API calls
# from Claude Code into OpenAI Responses API calls (POST /v1/responses) to a
# configured backend. This manager starts it, atomically restarts it, stops it,
# reports status, rotates its local log, and supervises unexpected exits.
#
# Modes:
#   --auto     Silent no-op unless DAAF_PROVIDER_SHIM=openai. If opted in,
#              start-if-not-running with a keepalive supervisor. Boot-safe:
#              never fatal and never blocks container startup indefinitely.
#   --start    Start the shim (with keepalive supervisor) if not already running.
#   --restart  Under one lifecycle lock: stop any identity-verified generation,
#              wait for exit, launch one replacement, and require strict readiness.
#   --stop     Stop the shim and its supervisor.
#   --status   Print running/stopped + strictly validated health JSON. A stop
#              caused by the supervisor giving up after a restart storm is
#              reported distinctly (with timestamp) via the supervisor.state file.
#   --help     Print public action usage.
#
# Config (env, all optional — defaults mirror the shim's own):
#   DAAF_PROVIDER_SHIM      activation switch; must equal "openai" to auto-start
#   SHIM_PORT               default 4141
#   CLAUDE_CODE_DISABLE_FAST_MODE
#                           REQUIRED as exact `CLAUDE_CODE_DISABLE_FAST_MODE=1` on
#                           GPT provider-shim installations/routes. This is Claude
#                           Code's supported native `/fast` disable/hide control.
#                           Control the shim-native route tier with:
#                             bash /daaf/scripts/provider_shim/gpt_fast.sh {on|off|status}
#                           Both exact backends request canonical wire
#                           `service_tier:"priority"` when ON. ChatGPT calls this Fast
#                           under plan/credit semantics; OpenAI API calls it Priority
#                           under API Priority billing/cost semantics. Setting changes
#                           require container recreation and a new Claude session,
#                           not a daemon restart or image rebuild. In-container DAAF
#                           code does not mutate the private host configuration.
#   SHIM_BACKEND_MODE       backend lane selector: exact "openai" for the API-key
#                           provider-shim route, or exact "chatgpt" for the
#                           ChatGPT-subscription Codex route. The legacy shim process
#                           still normalizes case/whitespace and defaults/falls back to
#                           "openai", but route detection and the GPT service-tier
#                           controller deliberately require an explicit exact token.
#   SHIM_BACKEND_BASE_URL   default is mode-conditional: openai ->
#                           https://api.openai.com/v1; chatgpt ->
#                           https://chatgpt.com/backend-api/codex. Explicit value
#                           overrides either default.
#   SHIM_BACKEND_API_KEY    default: value of OPENAI_API_KEY (openai mode only;
#                           ignored in chatgpt mode)
#   CODEX_HOME              (chatgpt mode) directory holding auth.json, the codex
#                           OAuth token store (mode 0600). Compose sets it to
#                           /home/appuser/.claude/codex-daaf. As of v1.3.0 the shim
#                           only READS this store; codex is the single writer and
#                           performs any token refresh (see SHIM_CODEX_BIN).
#   SHIM_CODEX_BIN          (chatgpt mode) codex binary the shim spawns to delegate
#                           token refresh (`codex login status`). Default "codex"
#                           (on PATH in the DAAF image). v1.3.0.
#   SHIM_CODEX_TIMEOUT_S    (chatgpt mode) wall-clock bound (float seconds) on the
#                           delegated `codex login status` subprocess. Default 30;
#                           an unparseable value falls back to 30. v1.3.0.
#   SHIM_STRIP_MODEL_PREFIX default ""
#   SHIM_SANITIZE_TOOLS     default "1" (enabled); set to 0 and restart for
#                           DAAFBench runs of shim-routed models
#   SHIM_REASONING_EFFORT   tier 3 of the effort precedence chain (per-request
#                           signal > "#<effort>" slug suffix > env > high)
#   SHIM_TEXT_VERBOSITY     low|medium|high; default medium
#
# Keepalive: the supervisor restarts the shim after an unexpected exit. A guard
# stops after 10 crashes in 60 seconds so a broken configuration cannot spin.
# On every lifecycle transition the supervisor records its phase
# (running|gave_up_storm|stopped) in logs/supervisor.state next to the PID file,
# so a storm give-up stays visible to --status instead of looking like a clean
# stop. The state file carries the PID file's safety conventions (symlink
# refusal, mode 0600, atomic write, cleanup on stop).
#
# Logging: shim stderr and supervisor records share logs/shim.log. Supervisor
# records are emitted once to stderr; the supervisor's single outer redirect is
# the only writer, avoiding the historical tee + redirect duplicate. Before a
# new supervisor starts, a >25 MiB log rotates to shim.log.1 with five retained
# generations. The 25 MiB / five-generation policy is fixed deliberately: the
# observed 12.7 MiB over nine days remains comfortably below one generation,
# while worst-case retained supervisor history stays bounded near 150 MiB.
# Rotation is serialized with lifecycle start/restart/stop, rejects symlink/non-regular
# targets, and creates the replacement log (0600) before the first new record.
# =============================================================================

set -uo pipefail
umask 077
# Deliberately omit -e: health probes, stale-state cleanup, and process teardown
# inspect failures and choose an explicit recovery path. --auto must degrade
# gracefully rather than aborting container boot.

# --- Config -----------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SCRIPT_DIR
readonly SHIM_PY="${SCRIPT_DIR}/anthropic_openai_shim.py"
readonly LIFECYCLE_CAPABILITY_PY="${SCRIPT_DIR}/lifecycle_capability.py"
readonly LOG_DIR="${SCRIPT_DIR}/logs"
readonly LOG_FILE="${LOG_DIR}/shim.log"
readonly PID_FILE="${LOG_DIR}/shim.pid"
readonly SUP_PID_FILE="${LOG_DIR}/supervisor.pid"
readonly SUP_STATE_FILE="${LOG_DIR}/supervisor.state"
readonly PGID_FILE="${LOG_DIR}/pgid"
readonly STOP_FILE="${LOG_DIR}/stop.requested"
readonly QUOTA_STATE_FILE="${LOG_DIR}/quota_state.json"
readonly LOCK_DIR="${LOG_DIR}/lifecycle.lock"
readonly LOG_WRITE_LOCK_DIR="${LOG_DIR}/log-write.lock"
readonly SHIM_SERVICE_ID="daaf-anthropic-openai-shim"

SHIM_PORT="${SHIM_PORT:-4141}"
readonly SHIM_PORT
readonly HEALTH_URL="http://127.0.0.1:${SHIM_PORT}/health"

readonly LOG_MAX_BYTES=26214400  # 25 MiB; rotate only when strictly greater.
readonly LOG_GENERATIONS=5
readonly STORM_LIMIT=10
readonly STORM_WINDOW=60
readonly RESTART_DELAY=2
readonly READINESS_WAIT=15

# Test-only timing controls are intentionally outside the SHIM_* user-config
# namespace and activate only when the isolated Bats harness opts in. Production
# always uses the fixed policy above.
storm_limit="$STORM_LIMIT"
storm_window="$STORM_WINDOW"
restart_delay="$RESTART_DELAY"
readiness_wait="$READINESS_WAIT"
termination_wait=5
if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ]; then
    storm_limit="${DAAF_SHIM_TEST_STORM_LIMIT:-$STORM_LIMIT}"
    storm_window="${DAAF_SHIM_TEST_STORM_WINDOW:-$STORM_WINDOW}"
    restart_delay="${DAAF_SHIM_TEST_RESTART_DELAY:-$RESTART_DELAY}"
    readiness_wait="${DAAF_SHIM_TEST_READINESS_WAIT:-$READINESS_WAIT}"
    termination_wait="${DAAF_SHIM_TEST_TERMINATION_WAIT:-5}"
fi

HEALTH_JSON=""
HEALTH_REASON="not_probed"
EXPECTED_SHIM_VERSION=""
EXPECTED_BACKEND_MODE="openai"
START_FAILURE_KIND="not_started"
ACTIVE_LAUNCH_PID=""
ACTIVE_LAUNCH_STREAM_DIR=""
ACTIVE_LAUNCH_STREAM_FD=""
ACTIVE_LAUNCH_WORKSPACE_TOKEN=""
START_SIGNAL_QUEUED=""
LIFECYCLE_LOCK_HELD=0
LIFECYCLE_LOCK_FD=""
LOG_WRITE_LOCK_FD=""
VALIDATED_STATE_GATE=0
START_INTERRUPT_KIND="explicit"
CAPABILITY_OUTPUT=""

# --- Filesystem and logging helpers -----------------------------------------
path_is_safe_file_target() {
    # Missing is safe; an existing target must be a regular, non-symlink file.
    local target="$1"
    [ ! -L "$target" ] || return 1
    [ ! -e "$target" ] || [ -f "$target" ]
}

ensure_log_dir() {
    if [ -L "$LOG_DIR" ]; then
        printf 'ERROR: shim log directory is a symlink: %s\n' "$LOG_DIR" >&2
        printf '  Fix: replace it with a real directory owned by the container user.\n' >&2
        return 1
    fi
    if [ -e "$LOG_DIR" ] && [ ! -d "$LOG_DIR" ]; then
        printf 'ERROR: shim log path exists but is not a directory: %s\n' "$LOG_DIR" >&2
        printf '  Fix: move that object aside and recreate a private directory.\n' >&2
        return 1
    fi
    mkdir -p "$LOG_DIR" || return 1
    chmod 0700 "$LOG_DIR" || return 1
    return 0
}

state_targets_are_safe() {
    # quota_state.json is a shim-written state file that lives in this same LOG_DIR
    # (install-shared, read by any install's statusline), so it belongs in the
    # symlink/non-regular hijack checklist alongside the other named state targets.
    # The reasoning-cache file is deliberately NOT covered here: it lives under
    # $HOME/.claude/provider_shim/, outside start_shim's domain — the shim owns that
    # path and its atomic publish uses os.replace, which does not dereference a
    # destination symlink (rename(2) replaces the symlink entry itself).
    local target generation
    for target in "$LOG_FILE" "$PID_FILE" "$SUP_PID_FILE" "$SUP_STATE_FILE" "$PGID_FILE" "$STOP_FILE" "$QUOTA_STATE_FILE"; do
        if ! path_is_safe_file_target "$target"; then
            printf 'ERROR: refusing unsafe shim state target: %s\n' "$target" >&2
            printf '  Fix: remove the symlink/non-regular object and retry.\n' >&2
            return 1
        fi
    done
    generation=1
    while [ "$generation" -le "$LOG_GENERATIONS" ]; do
        target="${LOG_FILE}.${generation}"
        if ! path_is_safe_file_target "$target"; then
            printf 'ERROR: refusing unsafe shim log-generation target: %s\n' "$target" >&2
            printf '  Fix: remove the symlink/non-regular object and retry.\n' >&2
            return 1
        fi
        generation=$((generation + 1))
    done
    if [ -L "$LOCK_DIR" ] || { [ -e "$LOCK_DIR" ] && [ ! -d "$LOCK_DIR" ]; }; then
        printf 'ERROR: refusing unsafe shim lifecycle-lock target: %s\n' "$LOCK_DIR" >&2
        printf '  Fix: remove the symlink/non-directory object and retry.\n' >&2
        return 1
    fi
    if [ -L "$LOG_WRITE_LOCK_DIR" ] || {
        [ -e "$LOG_WRITE_LOCK_DIR" ] && [ ! -d "$LOG_WRITE_LOCK_DIR" ]
    }; then
        printf 'ERROR: refusing unsafe shim log-write-lock target: %s\n' \
            "$LOG_WRITE_LOCK_DIR" >&2
        printf '  Fix: remove the symlink/non-directory object and retry.\n' >&2
        return 1
    fi
    return 0
}

open_stable_lock_directory() {
    # Lock directories are permanent rendezvous inodes: managers never remove them.
    # flock owns exclusion in the kernel and releases automatically on process death,
    # eliminating stale-owner reclamation and its unavoidable delete/takeover race.
    local lock_dir="$1" label="$2" fd proc_fd path_identity fd_identity dependency
    OPENED_LOCK_FD=""
    for dependency in flock stat; do
        if ! command -v "$dependency" >/dev/null 2>&1; then
            printf 'ERROR: required shim-manager dependency is unavailable: %s\n' \
                "$dependency" >&2
            printf '  Fix: rebuild from the current DAAF Dockerfile.\n' >&2
            return 1
        fi
    done
    if [ -L "$lock_dir" ] || { [ -e "$lock_dir" ] && [ ! -d "$lock_dir" ]; }; then
        printf 'ERROR: refusing unsafe shim %s-lock target: %s\n' "$label" "$lock_dir" >&2
        printf '  Fix: remove the symlink/non-directory object and retry.\n' >&2
        return 1
    fi
    if [ ! -d "$lock_dir" ]; then
        mkdir "$lock_dir" 2>/dev/null || {
            # Another manager may have won creation; accept only its real directory.
            [ ! -L "$lock_dir" ] && [ -d "$lock_dir" ] || return 1
        }
    fi
    chmod 0700 "$lock_dir" || return 1
    exec {fd}<"$lock_dir" || return 1
    proc_fd="/proc/${BASHPID:-$$}/fd/${fd}"
    if [ ! -d "$proc_fd" ] || [ -L "$lock_dir" ] || [ ! -d "$lock_dir" ]; then
        exec {fd}<&-
        return 1
    fi
    fd_identity="$(stat -Lc '%d:%i' "$proc_fd" 2>/dev/null)" || fd_identity=""
    path_identity="$(stat -Lc '%d:%i' "$lock_dir" 2>/dev/null)" || path_identity=""
    if [ -z "$fd_identity" ] || [ "$fd_identity" != "$path_identity" ]; then
        exec {fd}<&-
        printf 'ERROR: shim %s-lock target changed during acquisition: %s\n' \
            "$label" "$lock_dir" >&2
        return 1
    fi
    OPENED_LOCK_FD="$fd"
    return 0
}

acquire_log_write_lock() {
    local fd
    open_stable_lock_directory "$LOG_WRITE_LOCK_DIR" log-write || return 1
    fd="$OPENED_LOCK_FD"
    if ! flock -w 2 "$fd"; then
        exec {fd}<&-
        printf 'ERROR: timed out acquiring shim log-write lock: %s\n' \
            "$LOG_WRITE_LOCK_DIR" >&2
        return 1
    fi
    LOG_WRITE_LOCK_FD="$fd"
    if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ -n "${DAAF_SHIM_TEST_LOG_LOCK_HOLD_S:-}" ]; then
        printf '%s\n' "$$" > "${SCRIPT_DIR}/test.log-write.locked"
        (
            exec {fd}<&-
            exec sleep "$DAAF_SHIM_TEST_LOG_LOCK_HOLD_S"
        )
    fi
    return 0
}

release_log_write_lock() {
    local fd="$LOG_WRITE_LOCK_FD"
    if is_decimal_pid "$fd"; then
        flock -u "$fd" 2>/dev/null || true
        exec {fd}<&-
    fi
    LOG_WRITE_LOCK_FD=""
}

# --- Supervisor state file (lifecycle status honesty) -----------------------
write_supervisor_state() {
    # Record the supervisor's lifecycle phase (running|gave_up_storm|stopped) so
    # --status can distinguish a storm give-up from a clean stop or a never-started
    # daemon. Written by the supervisor directly — like the PID files it also
    # writes, and unlike the log records, it is not serialized under the
    # log-write lock; the lifecycle lock already serializes the manager actions
    # that would race with it. It carries the same safety conventions as the PID
    # file: symlink/non-regular refusal before any write, mode 0600, and an atomic
    # rename so --status never observes a half-written record.
    #
    # Shared-workspace note: in shared-workspace deployments two containers may
    # share /daaf, including this state directory, so supervisor.state — exactly
    # like the PID file today — is install-shared, not per-container; docs advise
    # running one active pipeline at a time.
    local phase="$1" record tmp
    case "$phase" in
        running|gave_up_storm|stopped) ;;
        *) return 1 ;;
    esac
    path_is_safe_file_target "$SUP_STATE_FILE" || return 1
    tmp="${SUP_STATE_FILE}.tmp.${BASHPID:-$$}"
    path_is_safe_file_target "$tmp" || return 1
    record="$(printf '%s %s' "$phase" "$(date -u '+%Y-%m-%d %H:%M:%S')")"
    printf '%s\n' "$record" > "$tmp" || { rm -f "$tmp" 2>/dev/null || true; return 1; }
    chmod 0600 "$tmp" 2>/dev/null || true
    # Atomic replace: SUP_STATE_FILE was preflighted as a non-symlink, so mv
    # cannot be redirected through a planted link.
    mv "$tmp" "$SUP_STATE_FILE" || { rm -f "$tmp" 2>/dev/null || true; return 1; }
    return 0
}

read_supervisor_state() {
    # Emit "phase<TAB>timestamp" for a valid, non-symlink state file, or fail
    # quietly. Only the three known phase tokens are honored; anything else (a
    # truncated or garbage file) is treated as absent so --status falls back to
    # plain "stopped" rather than trusting an unrecognized record.
    local line phase rest
    path_is_safe_file_target "$SUP_STATE_FILE" || return 1
    [ -f "$SUP_STATE_FILE" ] || return 1
    line="$(awk 'NR == 1 { print; exit }' "$SUP_STATE_FILE" 2>/dev/null)" || return 1
    phase="${line%% *}"
    rest="${line#* }"
    case "$phase" in
        running|gave_up_storm|stopped) ;;
        *) return 1 ;;
    esac
    [ "$rest" != "$line" ] || rest=""
    printf '%s\t%s' "$phase" "$rest"
}

append_log_record() {
    local record="$1" rc=0
    acquire_log_write_lock || return 1
    state_targets_are_safe || rc=1
    if [ "$rc" -eq 0 ]; then
        if [ ! -e "$LOG_FILE" ]; then
            : > "$LOG_FILE" || rc=1
            [ "$rc" -ne 0 ] || chmod 0600 "$LOG_FILE" || rc=1
        fi
    fi
    if [ "$rc" -eq 0 ] && [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ "${DAAF_SHIM_TEST_RESULT_APPEND_FAILURE:-0}" = "1" ]; then
        case "$record" in
            *' MANAGER SHIM_RESTART_RESULT '*) rc=1 ;;
        esac
    fi
    if [ "$rc" -eq 0 ]; then
        printf '%s\n' "$record" >> "$LOG_FILE" || rc=1
    fi
    if [ "$rc" -eq 0 ] && [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ "${DAAF_SHIM_TEST_SIGNAL_DURING_RESULT_APPEND:-0}" = "1" ] && \
        [ "${RESTART_RESULT_STATE:-NONE}" = "APPENDING" ]; then
        case "$record" in
            *' MANAGER SHIM_RESTART_RESULT '*)
                DAAF_SHIM_TEST_SIGNAL_DURING_RESULT_APPEND=0
                kill -TERM "$$"
                ;;
        esac
    fi
    release_log_write_lock
    return "$rc"
}

log_line() {
    # Every supervisor event has one authoritative append. A separate terminal
    # write occurs only when stderr is an interactive TTY; it never feeds back
    # through the log writer and therefore cannot duplicate the stored record.
    local record
    record="$(printf '%s SUPERVISOR %s' "$(date -u '+%Y-%m-%d %H:%M:%S')" "$*")"
    append_log_record "$record" || return 1
    [ -t 2 ] && printf '%s\n' "$record" >&2
    return 0
}

process_start_token() {
    local pid="$1" token
    [ -r "/proc/${pid}/stat" ] || return 1
    token="$(awk '{ print $22 }' "/proc/${pid}/stat" 2>/dev/null)" || return 1
    case "$token" in
        ''|*[!0-9]*) return 1 ;;
    esac
    printf '%s' "$token"
}

presentation_child_matches() {
    local pid="$1" token="$2" observed
    is_decimal_pid "$pid" || return 1
    observed="$(process_start_token "$pid")" || return 1
    [ "$observed" = "$token" ]
}

cleanup_presentation_children() {
    local writer_pid="$1" writer_token="$2" timer_pid="$3" timer_token="$4"
    local waited=0
    if presentation_child_matches "$writer_pid" "$writer_token"; then
        kill -TERM "$writer_pid" 2>/dev/null || true
        while presentation_child_matches "$writer_pid" "$writer_token" && \
            [ "$waited" -lt 5 ]; do
            sleep 0.01
            waited=$((waited + 1))
        done
        presentation_child_matches "$writer_pid" "$writer_token" && \
            kill -KILL "$writer_pid" 2>/dev/null || true
    fi
    wait "$writer_pid" 2>/dev/null || true
    if presentation_child_matches "$timer_pid" "$timer_token"; then
        kill -TERM "$timer_pid" 2>/dev/null || true
    fi
    wait "$timer_pid" 2>/dev/null || true
}

best_effort_stderr_line() {
    # Presentation children are parent-owned capabilities. Every path (normal,
    # timeout, queued signal, or error) identity-verifies, terminates if needed,
    # and reaps both direct children before returning.
    local message="$1" writer_pid writer_token timer_pid timer_token fd
    (
        trap - EXIT INT TERM HUP
        trap '' PIPE
        for fd in "$LIFECYCLE_LOCK_FD" "$LOG_WRITE_LOCK_FD"; do
            if is_decimal_pid "$fd"; then
                exec {fd}<&-
            fi
        done
        if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
            is_decimal_pid "${DAAF_SHIM_TEST_READY_PRESENTATION_PAD_BYTES:-}" && \
            [[ "$message" == *'SHIM_RESTART_RESULT status=ready'* ]]; then
            printf '%*s' "$DAAF_SHIM_TEST_READY_PRESENTATION_PAD_BYTES" '' >&2 || true
        fi
        printf '%s\n' "$message" >&2 || true
    ) &
    writer_pid=$!
    writer_token="$(process_start_token "$writer_pid")" || writer_token="invalid"
    (
        trap - EXIT INT TERM HUP
        for fd in "$LIFECYCLE_LOCK_FD" "$LOG_WRITE_LOCK_FD"; do
            if is_decimal_pid "$fd"; then
                exec {fd}<&-
            fi
        done
        sleep 0.2
        if presentation_child_matches "$writer_pid" "$writer_token"; then
            kill -TERM "$writer_pid" 2>/dev/null || exit 0
            sleep 0.05
            presentation_child_matches "$writer_pid" "$writer_token" && \
                kill -KILL "$writer_pid" 2>/dev/null || true
        fi
    ) >/dev/null 2>&1 &
    timer_pid=$!
    timer_token="$(process_start_token "$timer_pid")" || timer_token="invalid"
    if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ -n "${DAAF_SHIM_TEST_SIGNAL_DURING_PRESENTATION:-}" ] && \
        [[ "$message" == *'SHIM_RESTART_RESULT status=ready'* ]]; then
        printf '%s %s\n' "$writer_pid" "$timer_pid" > "${SCRIPT_DIR}/test.presentation.children"
        case "$DAAF_SHIM_TEST_SIGNAL_DURING_PRESENTATION" in
            INT|TERM|HUP) kill "-${DAAF_SHIM_TEST_SIGNAL_DURING_PRESENTATION}" "$$" ;;
        esac
    fi
    wait "$writer_pid" 2>/dev/null || true
    cleanup_presentation_children "$writer_pid" "$writer_token" "$timer_pid" "$timer_token"
    return 0
}

manager_log_line() {
    # Foreground manager events append once. The append outcome is authoritative;
    # terminal presentation is deliberately best-effort and cannot change it.
    local record
    record="$(printf '%s MANAGER %s' "$(date -u '+%Y-%m-%d %H:%M:%S')" "$*")"
    append_log_record "$record" || return 1
    best_effort_stderr_line "$record"
    return 0
}

write_stream_to_log() {
    # Preserve Python's structured records byte-for-byte while serializing each
    # physical line through the same append lock as supervisor/manager records.
    local line
    while IFS= read -r line || [ -n "$line" ]; do
        append_log_record "$line" || return 1
    done
}

rotate_log_if_needed_unlocked() {
    ensure_log_dir || return 1
    state_targets_are_safe || return 1

    if [ ! -e "$LOG_FILE" ]; then
        : > "$LOG_FILE" || return 1
        chmod 0600 "$LOG_FILE" || return 1
        return 0
    fi

    local size generation previous
    size="$(wc -c < "$LOG_FILE" 2>/dev/null)" || return 1
    case "$size" in
        ''|*[!0-9]*)
            printf 'ERROR: could not determine shim log size safely: %s\n' "$LOG_FILE" >&2
            return 1
            ;;
    esac

    if [ "$size" -le "$LOG_MAX_BYTES" ]; then
        chmod 0600 "$LOG_FILE" || return 1
        return 0
    fi

    # All targets were preflighted before mutation. Descending renames preserve
    # generations deterministically; the oldest regular file is removed first.
    if [ -e "${LOG_FILE}.${LOG_GENERATIONS}" ]; then
        rm -f "${LOG_FILE}.${LOG_GENERATIONS}" || return 1
    fi
    generation="$LOG_GENERATIONS"
    while [ "$generation" -gt 1 ]; do
        previous=$((generation - 1))
        if [ -e "${LOG_FILE}.${previous}" ]; then
            mv "${LOG_FILE}.${previous}" "${LOG_FILE}.${generation}" || return 1
            chmod 0600 "${LOG_FILE}.${generation}" || return 1
        fi
        generation=$((generation - 1))
    done
    mv "$LOG_FILE" "${LOG_FILE}.1" || return 1
    chmod 0600 "${LOG_FILE}.1" || return 1
    : > "$LOG_FILE" || return 1
    chmod 0600 "$LOG_FILE" || return 1
    return 0
}

rotate_log_if_needed() {
    local rc
    acquire_log_write_lock || return 1
    rotate_log_if_needed_unlocked
    rc=$?
    release_log_write_lock
    return "$rc"
}

# --- Configuration and health helpers --------------------------------------
source_shim_version() {
    local version
    version="$(awk -F'"' '/^SHIM_VERSION = "/ { print $2; exit }' "$SHIM_PY" 2>/dev/null)"
    case "$version" in
        ''|*[!0-9A-Za-z._+-]*) return 1 ;;
    esac
    printf '%s' "$version"
}

resolve_backend_mode() {
    local raw normalized
    raw="${SHIM_BACKEND_MODE:-openai}"
    # Match the shim's practical startup semantics: trim surrounding whitespace,
    # lowercase, accept the two known values, otherwise fall back to openai.
    normalized="${raw#"${raw%%[![:space:]]*}"}"
    normalized="${normalized%"${normalized##*[![:space:]]}"}"
    normalized="$(printf '%s' "$normalized" | tr '[:upper:]' '[:lower:]')"
    case "$normalized" in
        openai|chatgpt) EXPECTED_BACKEND_MODE="$normalized" ;;
        *) EXPECTED_BACKEND_MODE="openai" ;;
    esac
}

load_expected_contract() {
    EXPECTED_SHIM_VERSION="$(source_shim_version)" || {
        printf 'ERROR: could not derive SHIM_VERSION from %s.\n' "$SHIM_PY" >&2
        printf '  Fix: restore the provider-shim source file and retry.\n' >&2
        return 1
    }
    resolve_backend_mode
    return 0
}

probe_health() {
    HEALTH_JSON=""
    HEALTH_REASON="unreachable"
    local response http_status out
    response="$(curl -sS --max-time 2 --write-out $'\n%{http_code}' \
        "$HEALTH_URL" 2>/dev/null)"
    http_status="${response##*$'\n'}"
    case "$http_status" in
        [0-9][0-9][0-9]) ;;
        *) return 1 ;;
    esac
    if [ "$http_status" = "000" ]; then
        return 1
    fi
    if [ "$http_status" != "200" ]; then
        HEALTH_REASON="http_status_${http_status}"
        return 1
    fi
    # Any received 200 is reachable. Validate only its captured body and never
    # expose that body in diagnostics, even if curl reported a transfer anomaly.
    out="${response%$'\n'*}"
    HEALTH_JSON="$out"

    if ! printf '%s' "$out" | jq -e 'type == "object"' >/dev/null 2>&1; then
        HEALTH_REASON="malformed_json"
        return 1
    fi
    if ! printf '%s' "$out" | jq -e --arg service "$SHIM_SERVICE_ID" \
        '.service == $service and .status == "ok"' >/dev/null 2>&1; then
        HEALTH_REASON="wrong_identity_or_status"
        return 1
    fi
    if ! printf '%s' "$out" | jq -e --arg version "$EXPECTED_SHIM_VERSION" \
        '.version == $version' >/dev/null 2>&1; then
        HEALTH_REASON="version_mismatch"
        return 1
    fi
    if ! printf '%s' "$out" | jq -e --arg mode "$EXPECTED_BACKEND_MODE" \
        '.backend_mode == $mode' >/dev/null 2>&1; then
        HEALTH_REASON="backend_mode_mismatch"
        return 1
    fi
    HEALTH_REASON="ready"
    return 0
}

is_healthy() {
    probe_health >/dev/null
}

emit_readiness_failure() {
    printf 'SHIM_READINESS_FAILURE status=failed reason=%s expected_service=%s expected_version=%s expected_backend_mode=%s port=%s\n' \
        "$HEALTH_REASON" "$SHIM_SERVICE_ID" "${EXPECTED_SHIM_VERSION:--}" \
        "$EXPECTED_BACKEND_MODE" "$SHIM_PORT" >&2
}

# A1-R6a (v1.3.0): surface the /health auth block's validity as a human-readable line
# so an expiring/dead ChatGPT subscription is visible BEFORE work starts (and via
# --status). Reads the auth block already captured in HEALTH_JSON by probe_health — no
# extra request. Prints nothing when the block is absent or "n/a" (the openai API-key
# lane does not use the codex OAuth store). Both fields are sanitized to bounded,
# single-line tokens (the D4 injection convention, mirroring do_auto's `observed`)
# before reaching the terminal: they originate from our own /health but are DERIVED
# from the on-disk token store, so they are treated as untrusted for output.
print_auth_line() {
    command -v jq >/dev/null 2>&1 || return 0
    [ -n "$HEALTH_JSON" ] || return 0
    local state days
    state="$(printf '%s' "$HEALTH_JSON" | jq -r '.auth.state // empty' 2>/dev/null \
        | tr -cd 'a-z/' | cut -c1-16)"
    [ -n "$state" ] && [ "$state" != "n/a" ] || return 0
    days="$(printf '%s' "$HEALTH_JSON" | jq -r '.auth.days_left // empty' 2>/dev/null \
        | tr -cd '0-9.-' | cut -c1-16)"
    case "$state" in
        valid)
            printf 'AUTH: ChatGPT subscription auth is valid (expires in %s days).\n' \
                "${days:-?}" >&2
            ;;
        expiring)
            printf 'WARNING: ChatGPT subscription auth expires in %s days. Run `codex login --device-auth` inside the container to re-authenticate before it lapses.\n' \
                "${days:-?}" >&2
            ;;
        expired|absent|unreadable)
            printf 'WARNING: ChatGPT subscription auth is dead (%s) — run `codex login --device-auth` inside the container to re-authenticate.\n' \
                "$state" >&2
            ;;
        *)
            printf 'AUTH: ChatGPT subscription auth state: %s.\n' "$state" >&2
            ;;
    esac
}

# --- Process identity helpers ----------------------------------------------
is_decimal_pid() {
    case "${1:-}" in
        ''|*[!0-9]*) return 1 ;;
        *) [ "$1" -gt 1 ] 2>/dev/null ;;
    esac
}

PID_EVIDENCE_KIND="INFRASTRUCTURE_ERROR"
PID_EVIDENCE_REASON="not_read"
PID_EVIDENCE_VALUE="-"
PID_ACTION_UNCERTAIN=0
PID_ACTION_FAILURE=""
PID_ACTION_SUP_PID=""
PID_ACTION_SHIM_PID=""
PID_ACTION_PGID=""
PID_ACTION_SUP_ROLE="absent"
PID_ACTION_SHIM_ROLE="absent"

pid_reader_dependencies_available() {
    if ! command -v python3 >/dev/null 2>&1; then
        printf 'ERROR: required shim PID capability dependency is unavailable: python3\n' >&2
        printf '  Fix: rebuild from the current DAAF Dockerfile. PID evidence was preserved.\n' >&2
        return 1
    fi
    if [ ! -f "$LIFECYCLE_CAPABILITY_PY" ] || [ -L "$LIFECYCLE_CAPABILITY_PY" ]; then
        printf 'ERROR: shim lifecycle capability helper is missing or unsafe: %s\n' \
            "$LIFECYCLE_CAPABILITY_PY" >&2
        printf '  Fix: restore the provider_shim directory. PID evidence was preserved.\n' >&2
        return 1
    fi
    if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ -n "${DAAF_SHIM_TEST_PID_DECODER_MISSING:-}" ]; then
        printf 'ERROR: required shim PID capability dependency is unavailable: %s\n' \
            "$DAAF_SHIM_TEST_PID_DECODER_MISSING" >&2
        return 1
    fi
    return 0
}

run_lifecycle_capability() {
    # Preserve the helper's final newline by appending an out-of-schema sentinel
    # inside the command substitution. The accepted wire record is byte-exact:
    # five nonempty TAB-separated fields followed by exactly one LF.
    local captured marker=$'\034' rc record without_tabs tab_count
    CAPABILITY_OUTPUT=""
    captured="$(python3 "$LIFECYCLE_CAPABILITY_PY" "$@" 2>/dev/null; \
        printf '%s%s' "$marker" "$?")"
    rc="${captured##*"$marker"}"
    record="${captured%"$marker"*}"
    case "$rc" in
        ''|*[!0-9]*) return 1 ;;
    esac
    [ "$rc" -eq 0 ] || return 1
    case "$record" in
        *$'\r'*) return 1 ;;
        *$'\n') ;;
        *) return 1 ;;
    esac
    record="${record%$'\n'}"
    case "$record" in
        ''|*$'\n'*|$'\t'*|*$'\t'|*$'\t\t'*) return 1 ;;
    esac
    without_tabs="${record//$'\t'/}"
    tab_count=$((${#record} - ${#without_tabs}))
    [ "$tab_count" -eq 4 ] || return 1
    CAPABILITY_OUTPUT="$record"
    return 0
}

read_pid_evidence() {
    # The helper owns no-follow/nonblocking open and identity validation. Bash
    # validates its complete fixed schema and treats every execution/parse anomaly
    # as infrastructure uncertainty without exposing hostile raw file content.
    local path="$1" output="" schema operation kind reason value
    PID_EVIDENCE_KIND="INFRASTRUCTURE_ERROR"
    PID_EVIDENCE_REASON="helper_unavailable"
    PID_EVIDENCE_VALUE="-"
    if ! pid_reader_dependencies_available >/dev/null; then
        PID_ACTION_UNCERTAIN=1
        PID_ACTION_FAILURE="infrastructure"
        return 2
    fi
    if ! run_lifecycle_capability pid-read "$path"; then
        PID_EVIDENCE_REASON="helper_exit_or_malformed_schema"
        PID_ACTION_UNCERTAIN=1
        PID_ACTION_FAILURE="infrastructure"
        return 2
    fi
    output="$CAPABILITY_OUTPUT"
    IFS=$'\t' read -r schema operation kind reason value <<< "$output"
    if [ "$schema" != "LCAP1" ] || [ "$operation" != "PID_READ" ] || \
        [ -z "${reason:-}" ] || [ -z "${value:-}" ]; then
        PID_EVIDENCE_REASON="malformed_schema"
        PID_ACTION_UNCERTAIN=1
        PID_ACTION_FAILURE="infrastructure"
        return 2
    fi
    case "$kind" in
        ABSENT|VALID|INVALID_CONTENT|HOSTILE_OBJECT|INFRASTRUCTURE_ERROR) ;;
        *)
            PID_EVIDENCE_REASON="malformed_enum"
            PID_ACTION_UNCERTAIN=1
            PID_ACTION_FAILURE="infrastructure"
            return 2
            ;;
    esac
    case "$reason" in
        *[!A-Za-z0-9_.-]*|'')
            PID_EVIDENCE_REASON="malformed_reason"
            PID_ACTION_UNCERTAIN=1
            PID_ACTION_FAILURE="infrastructure"
            return 2
            ;;
    esac
    if [ "$kind" = "VALID" ]; then
        if ! is_decimal_pid "$value"; then
            PID_EVIDENCE_REASON="malformed_value"
            PID_ACTION_UNCERTAIN=1
            PID_ACTION_FAILURE="infrastructure"
            return 2
        fi
    elif [ "$value" != "-" ]; then
        PID_EVIDENCE_REASON="malformed_value"
        PID_ACTION_UNCERTAIN=1
        PID_ACTION_FAILURE="infrastructure"
        return 2
    fi
    PID_EVIDENCE_KIND="$kind"
    PID_EVIDENCE_REASON="$reason"
    PID_EVIDENCE_VALUE="$value"
    if [ "$kind" = "HOSTILE_OBJECT" ]; then
        PID_ACTION_UNCERTAIN=1
        PID_ACTION_FAILURE="hostile_object"
    elif [ "$kind" = "INFRASTRUCTURE_ERROR" ]; then
        PID_ACTION_UNCERTAIN=1
        PID_ACTION_FAILURE="infrastructure"
        return 2
    fi
    return 0
}

read_pid_file() {
    read_pid_evidence "$1" || return $?
    [ "$PID_EVIDENCE_KIND" = "VALID" ] || return 1
    printf '%s' "$PID_EVIDENCE_VALUE"
}

PID_INSPECTION_FAILURE=""
pid_evidence_inspection_safe() {
    local target rc
    PID_INSPECTION_FAILURE=""
    for target in "$SUP_PID_FILE" "$PID_FILE" "$PGID_FILE"; do
        read_pid_evidence "$target"
        rc=$?
        if [ "$rc" -eq 2 ]; then
            PID_INSPECTION_FAILURE="infrastructure"
            return 2
        fi
        if [ "$PID_EVIDENCE_KIND" = "HOSTILE_OBJECT" ]; then
            PID_INSPECTION_FAILURE="hostile_object"
            return 3
        fi
    done
    return 0
}

pid_evidence_decoder_is_reliable() {
    pid_evidence_inspection_safe
}

begin_pid_action() {
    PID_ACTION_UNCERTAIN=0
    PID_ACTION_FAILURE=""
    PID_ACTION_SUP_PID=""
    PID_ACTION_SHIM_PID=""
    PID_ACTION_PGID=""
    PID_ACTION_SUP_ROLE="absent"
    PID_ACTION_SHIM_ROLE="absent"
}

adjudicate_pid_roles() {
    local target rc value kind
    PID_ACTION_SUP_PID=""
    PID_ACTION_SHIM_PID=""
    PID_ACTION_PGID=""
    PID_ACTION_SUP_ROLE="absent"
    PID_ACTION_SHIM_ROLE="absent"
    for target in "$SUP_PID_FILE" "$PID_FILE" "$PGID_FILE"; do
        read_pid_evidence "$target"
        rc=$?
        kind="$PID_EVIDENCE_KIND"
        value="$PID_EVIDENCE_VALUE"
        [ "$rc" -ne 2 ] || return 2
        [ "$kind" != "HOSTILE_OBJECT" ] || return 3
        case "$target" in
            "$SUP_PID_FILE")
                if [ "$kind" = "VALID" ]; then
                    PID_ACTION_SUP_PID="$value"
                    if pid_is_supervisor "$value"; then
                        PID_ACTION_SUP_ROLE="exact"
                    else
                        PID_ACTION_SUP_ROLE="unrecognized"
                    fi
                fi
                ;;
            "$PID_FILE")
                if [ "$kind" = "VALID" ]; then
                    PID_ACTION_SHIM_PID="$value"
                    if pid_is_shim "$value"; then
                        PID_ACTION_SHIM_ROLE="exact"
                    else
                        PID_ACTION_SHIM_ROLE="unrecognized"
                    fi
                fi
                ;;
            "$PGID_FILE")
                [ "$kind" != "VALID" ] || PID_ACTION_PGID="$value"
                ;;
        esac
    done
    [ "$PID_ACTION_UNCERTAIN" -eq 0 ] || return 2
    return 0
}

pid_action_has_unmanaged_shim() {
    [ "$PID_ACTION_SHIM_ROLE" = "exact" ] && [ "$PID_ACTION_SUP_ROLE" != "exact" ]
}

pid_cmdline_matches_role() {
    # Role identity is positional, not unordered membership. A process merely
    # mentioning one of our paths in an unrelated argument can never be signalled.
    local role="$1" pid="$2" arg executable stream_dir suffix token pipe_free pipe_count
    local token_version token_basename token_nonce identity_field
    local token_parent_dev token_parent_ino token_dir_dev token_dir_ino
    local token_fifo_dev token_fifo_ino token_owner_dev token_owner_ino
    local -a argv=() identity_fields=()
    [ -r "/proc/${pid}/cmdline" ] || return 1
    while IFS= read -r -d '' arg; do
        argv+=("$arg")
    done < "/proc/${pid}/cmdline"
    [ "${#argv[@]}" -gt 0 ] || return 1
    executable="${argv[0]##*/}"
    case "$role" in
        supervisor)
            case "$executable" in
                bash|bash[0-9]*) ;;
                *) return 1 ;;
            esac
            [ "${#argv[@]}" -eq 3 ] || [ "${#argv[@]}" -eq 4 ] || \
                [ "${#argv[@]}" -eq 5 ] || return 1
            [ "${argv[1]}" = "${BASH_SOURCE[0]}" ] || return 1
            [ "${argv[2]}" = "__supervise" ] || return 1
            if [ "${#argv[@]}" -ge 4 ]; then
                stream_dir="${argv[3]}"
                suffix="${stream_dir#"${LOG_DIR}/shim.stream."}"
                [ "$suffix" != "$stream_dir" ] || return 1
                case "$suffix" in
                    ''|*/*) return 1 ;;
                esac
            fi
            if [ "${#argv[@]}" -eq 4 ]; then
                # v1.3.15 exposed only its exact mktemp stream basename in argv.
                # Keep this transition proof bounded to that legacy 10-character
                # alphanumeric contract; it does not imply a workspace capability.
                [[ "$suffix" =~ ^[A-Za-z0-9]{10}$ ]] || return 1
            elif [ "${#argv[@]}" -eq 5 ]; then
                token="${argv[4]}"
                pipe_free="${token//|/}"
                pipe_count=$((${#token} - ${#pipe_free}))
                [ "$pipe_count" -eq 10 ] || return 1
                IFS='|' read -r token_version token_basename token_nonce \
                    token_parent_dev token_parent_ino token_dir_dev token_dir_ino \
                    token_fifo_dev token_fifo_ino token_owner_dev token_owner_ino <<< "$token"
                [ "$token_version" = "W1" ] || return 1
                [ "$token_basename" = "shim.stream.${suffix}" ] || return 1
                [[ "$token_nonce" =~ ^[0-9a-f]{32}$ ]] || return 1
                identity_fields=(
                    "$token_parent_dev" "$token_parent_ino"
                    "$token_dir_dev" "$token_dir_ino"
                    "$token_fifo_dev" "$token_fifo_ino"
                    "$token_owner_dev" "$token_owner_ino"
                )
                for identity_field in "${identity_fields[@]}"; do
                    [[ "$identity_field" =~ ^[0-9]+$ ]] || return 1
                done
            fi
            ;;
        shim)
            case "$executable" in
                python|python[0-9]|python[0-9].[0-9]*) ;;
                *) return 1 ;;
            esac
            [ "${#argv[@]}" -eq 2 ] || return 1
            [ "${argv[1]}" = "$SHIM_PY" ] || return 1
            ;;
        *)
            return 1
            ;;
    esac
    return 0
}

pid_is_supervisor() {
    local pid="$1"
    is_decimal_pid "$pid" || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    pid_cmdline_matches_role supervisor "$pid"
}

pid_is_shim() {
    local pid="$1"
    is_decimal_pid "$pid" || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    pid_cmdline_matches_role shim "$pid"
}

supervisor_running() {
    local rc sp
    read_pid_evidence "$SUP_PID_FILE"
    rc=$?
    [ "$rc" -eq 0 ] || return "$rc"
    [ "$PID_EVIDENCE_KIND" = "VALID" ] || return 1
    sp="$PID_EVIDENCE_VALUE"
    pid_is_supervisor "$sp"
}

process_group_is_owned() {
    local pgid="$1" supervisor_pid="$2" actual
    is_decimal_pid "$pgid" || return 1
    [ "$pgid" = "$supervisor_pid" ] || return 1
    pid_is_supervisor "$supervisor_pid" || return 1
    actual="$(ps -o pgid= -p "$supervisor_pid" 2>/dev/null | tr -d ' ')"
    [ "$actual" = "$pgid" ]
}

pid_has_verified_role() {
    local role="$1" pid="$2"
    case "$role" in
        supervisor) pid_is_supervisor "$pid" ;;
        shim) pid_is_shim "$pid" ;;
        *) return 1 ;;
    esac
}

finish_verified_pid_after_term() {
    local role="$1" pid="$2" start_token="$3" waited=0 wait_limit observed_token
    wait_limit=$((termination_wait * 10))
    while [ "$waited" -lt "$wait_limit" ]; do
        kill -0 "$pid" 2>/dev/null || return 0
        pid_has_verified_role "$role" "$pid" || return 0
        observed_token="$(process_start_token "$pid")" || return 1
        [ "$observed_token" = "$start_token" ] || return 0
        sleep 0.1
        waited=$((waited + 1))
    done
    kill -0 "$pid" 2>/dev/null || return 0
    pid_has_verified_role "$role" "$pid" || return 0
    observed_token="$(process_start_token "$pid")" || return 1
    [ "$observed_token" = "$start_token" ] || return 0
    kill -KILL "$pid" 2>/dev/null || true
    waited=0
    while [ "$waited" -lt 20 ]; do
        kill -0 "$pid" 2>/dev/null || return 0
        pid_has_verified_role "$role" "$pid" || return 0
        observed_token="$(process_start_token "$pid")" || return 1
        [ "$observed_token" = "$start_token" ] || return 0
        sleep 0.05
        waited=$((waited + 1))
    done
    return 1
}

terminate_verified_pid() {
    # Capture the Linux process-instance token before TERM. KILL is permitted only
    # if PID, exact argv role, and /proc start time still identify that instance.
    local role="$1" pid="$2" start_token
    pid_has_verified_role "$role" "$pid" || return 1
    start_token="$(process_start_token "$pid")" || return 1
    kill -TERM "$pid" 2>/dev/null || true
    finish_verified_pid_after_term "$role" "$pid" "$start_token"
}

# --- Lifecycle lock ---------------------------------------------------------
acquire_lifecycle_lock() {
    local wait_mode="${1:-wait}" fd
    ensure_log_dir || return 1
    state_targets_are_safe || return 1
    open_stable_lock_directory "$LOCK_DIR" lifecycle || return 1
    fd="$OPENED_LOCK_FD"

    # Public actions lock one permanent directory inode. The descriptor is the
    # ownership token: no PID metadata is consulted, and process death releases it.
    if [ "$wait_mode" = "no_wait" ]; then
        if ! flock -n "$fd"; then
            exec {fd}<&-
            printf 'ERROR: another shim lifecycle action is active.\n' >&2
            printf '  Fix: let it finish; boot will continue and a later health check can retry.\n' >&2
            return 1
        fi
    elif ! flock -w 60 "$fd"; then
        exec {fd}<&-
        printf 'ERROR: timed out acquiring shim lifecycle lock: %s\n' "$LOCK_DIR" >&2
        printf '  Fix: wait for the active lifecycle action to finish, then retry.\n' >&2
        return 1
    fi

    LIFECYCLE_LOCK_FD="$fd"
    LIFECYCLE_LOCK_HELD=1
    trap release_lifecycle_lock EXIT
    if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ -n "${DAAF_SHIM_TEST_LIFECYCLE_LOCK_HOLD_S:-}" ]; then
        printf '%s\n' "$$" > "${SCRIPT_DIR}/test.lifecycle.locked"
        (
            exec {fd}<&-
            exec sleep "$DAAF_SHIM_TEST_LIFECYCLE_LOCK_HOLD_S"
        )
    fi
    return 0
}

release_lifecycle_lock() {
    local fd="$LIFECYCLE_LOCK_FD"
    if [ "$LIFECYCLE_LOCK_HELD" -eq 1 ] && is_decimal_pid "$fd"; then
        flock -u "$fd" 2>/dev/null || true
        exec {fd}<&-
    fi
    LIFECYCLE_LOCK_FD=""
    LIFECYCLE_LOCK_HELD=0
    trap - EXIT
}

install_lifecycle_signal_handlers() {
    trap 'queue_start_handoff_signal INT' INT
    trap 'queue_start_handoff_signal TERM' TERM
    trap 'queue_start_handoff_signal HUP' HUP
}

lifecycle_signal_checkpoint() {
    local queued_signal="$START_SIGNAL_QUEUED"
    [ -n "$queued_signal" ] || return 0
    if [ "$START_INTERRUPT_KIND" = "restart" ]; then
        handle_restart_interrupt "$queued_signal"
    else
        handle_start_interrupt "$queued_signal"
    fi
}

# --- Private launch stream workspace ---------------------------------------
parse_workspace_record() {
    local expected_operation="$1" output="$2"
    local schema operation outcome reason value
    WORKSPACE_OUTCOME="ERROR"
    WORKSPACE_REASON="malformed_schema"
    WORKSPACE_VALUE="-"
    IFS=$'\t' read -r schema operation outcome reason value <<< "$output"
    [ "$schema" = "LCAP1" ] && [ "$operation" = "$expected_operation" ] && \
        [ -n "${outcome:-}" ] && [ -n "${reason:-}" ] && \
        [ -n "${value:-}" ] || return 1
    case "$reason" in
        *[!A-Za-z0-9_.-]*|'') return 1 ;;
    esac
    WORKSPACE_OUTCOME="$outcome"
    WORKSPACE_REASON="$reason"
    WORKSPACE_VALUE="$value"
    return 0
}

allocate_launch_stream_workspace() {
    local output="" basename fifo fd
    ACTIVE_LAUNCH_STREAM_DIR=""
    ACTIVE_LAUNCH_STREAM_FD=""
    ACTIVE_LAUNCH_WORKSPACE_TOKEN=""
    run_lifecycle_capability workspace-create "$LOG_DIR" || return 1
    output="$CAPABILITY_OUTPUT"
    parse_workspace_record WORKSPACE_CREATE "$output" || return 1
    [ "$WORKSPACE_OUTCOME" = "READY" ] && [ "$WORKSPACE_REASON" = "created" ] && \
        [ "$WORKSPACE_VALUE" != "-" ] || return 1
    basename="${WORKSPACE_VALUE#W1|}"
    basename="${basename%%|*}"
    case "$basename" in
        shim.stream.*) ;;
        *) return 1 ;;
    esac
    ACTIVE_LAUNCH_STREAM_DIR="${LOG_DIR}/${basename}"
    ACTIVE_LAUNCH_WORKSPACE_TOKEN="$WORKSPACE_VALUE"
    fifo="${ACTIVE_LAUNCH_STREAM_DIR}/output.fifo"
    if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ -n "${DAAF_SHIM_TEST_AFTER_STREAM_DIR_DELAY_S:-}" ]; then
        printf '%s\n' "$ACTIVE_LAUNCH_STREAM_DIR" > "${SCRIPT_DIR}/test.stream.dir.ready"
        sleep "$DAAF_SHIM_TEST_AFTER_STREAM_DIR_DELAY_S"
    fi
    if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ -n "${DAAF_SHIM_TEST_AFTER_STREAM_FIFO_DELAY_S:-}" ]; then
        printf '%s\n' "$fifo" > "${SCRIPT_DIR}/test.stream.manager-fifo.ready"
        sleep "$DAAF_SHIM_TEST_AFTER_STREAM_FIFO_DELAY_S"
    fi
    if ! exec {fd}<>"$fifo"; then
        release_launch_stream_workspace 1
        return 1
    fi
    ACTIVE_LAUNCH_STREAM_FD="$fd"
    return 0
}

release_launch_stream_anchor() {
    local fd="$ACTIVE_LAUNCH_STREAM_FD"
    if is_decimal_pid "$fd"; then
        exec {fd}>&-
    fi
    ACTIVE_LAUNCH_STREAM_FD=""
}

clean_workspace_capability() {
    local token="$1" output=""
    [ -n "$token" ] || return 0
    run_lifecycle_capability workspace-clean "$LOG_DIR" "$token" || return 1
    output="$CAPABILITY_OUTPUT"
    parse_workspace_record WORKSPACE_CLEAN "$output" || return 1
    [ "$WORKSPACE_OUTCOME" = "CLEANED" ] || return 1
    return 0
}

release_launch_stream_workspace() {
    local remove_owned="${1:-0}" token="$ACTIVE_LAUNCH_WORKSPACE_TOKEN"
    release_launch_stream_anchor
    if [ "$remove_owned" -eq 1 ] && [ -n "$token" ]; then
        clean_workspace_capability "$token" || return 1
    fi
    ACTIVE_LAUNCH_STREAM_DIR=""
    ACTIVE_LAUNCH_WORKSPACE_TOKEN=""
    return 0
}

# --- Keepalive supervisor ---------------------------------------------------
run_supervisor() {
    local inherited_stream_dir="${1:-}" inherited_workspace_token="${2:-}"
    local pgid child_pid logger_pid stream_dir log_pipe workspace_token token_tail token_basename
    local window_start crashes rc now
    local gave_up_storm setup_complete setup_failure_reason sup_pid_written pgid_written
    local child_termination_failed
    child_pid=""
    logger_pid=""
    stream_dir="$inherited_stream_dir"
    workspace_token="$inherited_workspace_token"
    log_pipe=""
    gave_up_storm=0
    setup_complete=0
    setup_failure_reason="not_started"
    sup_pid_written=0
    pgid_written=0
    child_termination_failed=0

    cleanup_supervisor() {
        if [ -n "$child_pid" ] && pid_is_shim "$child_pid"; then
            if ! terminate_verified_pid shim "$child_pid"; then
                child_termination_failed=1
            fi
        fi
        if [ -n "$logger_pid" ] && kill -0 "$logger_pid" 2>/dev/null; then
            kill -TERM "$logger_pid" 2>/dev/null || true
            wait "$logger_pid" 2>/dev/null || true
        fi
        # The shared inode capability identifies this generation even if its old
        # path is replaced or the original directory is renamed under LOG_DIR.
        if [ -n "$workspace_token" ]; then
            if ! clean_workspace_capability "$workspace_token"; then
                log_line "SUPERVISOR_WORKSPACE_CLEANUP status=failed reason=capability_validation" || true
            fi
        fi
        if [ "$setup_complete" -eq 1 ] && [ "$child_termination_failed" -eq 0 ]; then
            rm -f "$PID_FILE" 2>/dev/null || true
        fi
        if [ "$sup_pid_written" -eq 1 ]; then
            rm -f "$SUP_PID_FILE" 2>/dev/null || true
        fi
        if [ "$pgid_written" -eq 1 ]; then
            rm -f "$PGID_FILE" 2>/dev/null || true
        fi
        if [ "$VALIDATED_STATE_GATE" -eq 1 ]; then
            if [ "$setup_complete" -eq 0 ] && \
                [ "$setup_failure_reason" != "not_started" ]; then
                log_line "SUPERVISOR_SETUP_FAILURE status=failed reason=${setup_failure_reason}" || true
            fi
            if [ "$child_termination_failed" -eq 1 ]; then
                log_line "SUPERVISOR_TEARDOWN_FAILURE status=failed reason=child_termination_unverified child_pid=${child_pid} pid_evidence=retained" || true
            fi
            # A storm give-up already recorded gave_up_storm and must persist so
            # --status can report it distinctly; every other exit is a clean stop.
            if [ "$setup_complete" -eq 1 ] && [ "$gave_up_storm" -eq 0 ] && \
                [ "$child_termination_failed" -eq 0 ]; then
                write_supervisor_state stopped || true
            fi
            log_line "supervisor exiting" || true
        else
            if [ "$setup_failure_reason" != "not_started" ]; then
                printf 'SUPERVISOR_SETUP_FAILURE status=failed reason=%s persistence=skipped_unvalidated_state\n' \
                    "$setup_failure_reason" >&2
            fi
            printf 'SUPERVISOR_EXIT status=exited persistence=skipped_unvalidated_state\n' >&2
        fi
    }
    stop_supervisor_signal() {
        trap - INT TERM
        exit 0
    }
    # Register ownership-safe cleanup before the first setup operation. Any
    # failure below removes only state and stream paths created by this process.
    trap cleanup_supervisor EXIT
    trap stop_supervisor_signal INT TERM

    setup_failure_reason="log_directory"
    ensure_log_dir || exit 1
    setup_failure_reason="unsafe_state_target"
    state_targets_are_safe || exit 1
    VALIDATED_STATE_GATE=1

    if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ -n "${DAAF_SHIM_TEST_PRE_PID_DELAY_S:-}" ]; then
        printf 'SUPERVISOR_TEST_DELAY phase=pre_pid seconds=%s\n' \
            "$DAAF_SHIM_TEST_PRE_PID_DELAY_S" >&2
        sleep "$DAAF_SHIM_TEST_PRE_PID_DELAY_S"
    fi

    setup_failure_reason="stream_directory_allocation"
    if [ -n "$stream_dir" ]; then
        [ -n "$workspace_token" ] || exit 1
        case "$workspace_token" in
            W1\|shim.stream.*) ;;
            *) exit 1 ;;
        esac
        token_tail="${workspace_token#W1|}"
        token_basename="${token_tail%%|*}"
        [ "$stream_dir" = "${LOG_DIR}/${token_basename}" ] || exit 1
        log_pipe="${stream_dir}/output.fifo"
        [ ! -L "$stream_dir" ] && [ -d "$stream_dir" ] && \
            [ ! -L "$log_pipe" ] && [ -p "$log_pipe" ] && \
            [ -f "${stream_dir}/.owner" ] || exit 1
    else
        # Direct/internal supervisor invocations use the same helper capability.
        allocate_launch_stream_workspace || exit 1
        stream_dir="$ACTIVE_LAUNCH_STREAM_DIR"
        workspace_token="$ACTIVE_LAUNCH_WORKSPACE_TOKEN"
        log_pipe="${stream_dir}/output.fifo"
        release_launch_stream_anchor
    fi

    if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ -n "${DAAF_SHIM_TEST_AFTER_FIFO_DELAY_S:-}" ]; then
        printf '%s\n' "$$" > "${SCRIPT_DIR}/test.stream.fifo.ready"
        sleep "$DAAF_SHIM_TEST_AFTER_FIFO_DELAY_S"
    fi

    setup_failure_reason="supervisor_pid_write"
    # Mark ownership before redirection so even a partial/failed write is removed.
    sup_pid_written=1
    printf '%s\n' "$$" > "$SUP_PID_FILE" || exit 1
    chmod 0600 "$SUP_PID_FILE" || exit 1

    setup_failure_reason="process_group_write"
    pgid="$(ps -o pgid= -p "$$" 2>/dev/null | tr -d ' ')"
    if [ "$pgid" = "$$" ]; then
        # Mark ownership before redirection so even a partial/failed write is removed.
        pgid_written=1
        printf '%s\n' "$pgid" > "$PGID_FILE" || exit 1
        chmod 0600 "$PGID_FILE" || exit 1
    else
        # nohup fallback may share the caller's process group. Never record or kill
        # that broad group; verified per-pid teardown is safer.
        rm -f "$PGID_FILE" 2>/dev/null || true
        log_line "process-group isolation unavailable; using verified per-pid stop"
    fi

    setup_failure_reason="setup_finalize"
    if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ -n "${DAAF_SHIM_TEST_AFTER_PID_PUBLICATION_DELAY_S:-}" ]; then
        printf '%s\n' "$$" > "${SCRIPT_DIR}/test.stream.pid-published.ready"
        sleep "$DAAF_SHIM_TEST_AFTER_PID_PUBLICATION_DELAY_S"
    fi
    if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ "${DAAF_SHIM_TEST_FORCE_SETUP_FAILURE:-}" = "after_state_write" ]; then
        exit 1
    fi

    setup_failure_reason="stop_sentinel_cleanup"
    rm -f "$STOP_FILE" 2>/dev/null || true
    setup_complete=1
    setup_failure_reason="none"

    window_start="$(date +%s)"
    crashes=0
    write_supervisor_state running || true
    log_line "starting shim on port ${SHIM_PORT} backend_mode=${EXPECTED_BACKEND_MODE} version=${EXPECTED_SHIM_VERSION} (keepalive on)"

    while true; do
        if [ -f "$STOP_FILE" ]; then
            log_line "stop requested; supervisor loop ending"
            exit 0
        fi

        (
            trap - INT TERM HUP PIPE
            write_stream_to_log < "$log_pipe"
        ) &
        logger_pid=$!
        (
            trap - INT TERM HUP PIPE
            exec python3 "$SHIM_PY"
        ) > "$log_pipe" 2>&1 &
        child_pid=$!
        printf '%s\n' "$child_pid" > "$PID_FILE"
        chmod 0600 "$PID_FILE" 2>/dev/null || true
        wait "$child_pid"
        rc=$?
        child_pid=""
        wait "$logger_pid" 2>/dev/null || true
        logger_pid=""
        rm -f "$PID_FILE" 2>/dev/null || true

        if [ -f "$STOP_FILE" ]; then
            log_line "stop requested; not restarting shim"
            exit 0
        fi

        now="$(date +%s)"
        if [ $((now - window_start)) -gt "$storm_window" ]; then
            window_start="$now"
            crashes=0
        fi
        crashes=$((crashes + 1))
        log_line "shim exited rc=${rc} (crash ${crashes}/${storm_limit} in ${storm_window}s window)"
        if [ "$crashes" -ge "$storm_limit" ]; then
            # Record the give-up transition and mark it so cleanup_supervisor
            # preserves (rather than overwrites) this terminal state for --status.
            gave_up_storm=1
            write_supervisor_state gave_up_storm || true
            log_line "RESTART_STORM crashes=${crashes} window_s=${storm_window} action=give_up log=${LOG_FILE}"
            exit 1
        fi

        # Sleep in short, sentinel-aware ticks so --stop does not wait for the full
        # restart delay. TERM also interrupts the sleep and exits via the trap.
        local slept=0
        while [ "$slept" -lt 20 ]; do
            [ -f "$STOP_FILE" ] && break
            sleep "$(awk -v delay="$restart_delay" 'BEGIN { printf "%.3f", delay / 20 }')"
            slept=$((slept + 1))
        done
    done
}

# --- Stop implementation (caller holds lifecycle lock) ---------------------
stop_processes_locked() {
    local stopped=0 failed=0 pgid sp pp sp_start_token="" pp_start_token=""

    # Classify all evidence and exact argv roles before the first mutation. The
    # second typed pass catches a non-cooperating same-UID substitution between
    # inspection and action; once uncertainty is observed it poisons the action.
    pid_evidence_decoder_is_reliable || return 4
    adjudicate_pid_roles || return 4
    [ "$PID_ACTION_UNCERTAIN" -eq 0 ] || return 4
    sp="$PID_ACTION_SUP_PID"
    pp="$PID_ACTION_SHIM_PID"
    pgid="$PID_ACTION_PGID"
    if [ "$PID_ACTION_SUP_ROLE" = "exact" ]; then
        sp_start_token="$(process_start_token "$sp")" || return 4
    fi
    if [ "$PID_ACTION_SHIM_ROLE" = "exact" ]; then
        pp_start_token="$(process_start_token "$pp")" || return 4
    fi

    # Sentinel first only after the complete snapshot and process-instance tokens
    # are safe.
    : > "$STOP_FILE" || return 2
    chmod 0600 "$STOP_FILE" 2>/dev/null || true

    # Deterministic failure injection is confined to explicitly isolated tests.
    if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ "${DAAF_SHIM_TEST_STOP_FAILURE:-0}" = "1" ] && \
        { { [ -n "$sp" ] && pid_is_supervisor "$sp"; } || \
          { [ -n "$pp" ] && pid_is_shim "$pp"; }; }; then
        return 2
    fi

    # Teardown is deliberately per-process even when a private PGID is recorded.
    # Group escalation cannot bind every member to a process-instance token; exact
    # per-PID TERM/KILL preserves the start-time guarantee for the serving shim.
    if [ -n "$pgid" ] && [ -n "$sp" ]; then
        process_group_is_owned "$pgid" "$sp" >/dev/null 2>&1 || true
    fi

    # Every signal uses exact cmdline identity plus Linux process start time. A PID
    # recycled by any replacement process is never KILLed.
    if [ -n "$sp_start_token" ] && pid_is_supervisor "$sp"; then
        kill -TERM "$sp" 2>/dev/null || true
        stopped=1
    fi
    if [ -n "$pp_start_token" ] && pid_is_shim "$pp"; then
        kill -TERM "$pp" 2>/dev/null || true
        stopped=1
    fi
    if [ -n "$sp_start_token" ]; then
        finish_verified_pid_after_term supervisor "$sp" "$sp_start_token" || true
    fi
    if [ -n "$pp_start_token" ]; then
        finish_verified_pid_after_term shim "$pp" "$pp_start_token" || true
    fi

    # A stop is successful only after every originally verified identity is gone.
    # Preserve the sentinel and pid evidence on failure so a restart cannot launch
    # a second generation while the first may still be live.
    if [ -n "$pp" ] && pid_is_shim "$pp"; then
        failed=1
    fi
    if [ -n "$sp" ] && pid_is_supervisor "$sp"; then
        failed=1
    fi
    if [ "$failed" -eq 1 ]; then
        return 2
    fi

    rm -f "$PID_FILE" "$SUP_PID_FILE" "$SUP_STATE_FILE" "$PGID_FILE" "$STOP_FILE" 2>/dev/null || return 2
    if [ "$stopped" -eq 1 ]; then
        return 0
    fi
    return 3
}

# --- Public actions ---------------------------------------------------------
preflight_start_contract() {
    local action_kind="${1:-explicit}"
    if [ ! -f "$SHIM_PY" ] || [ -L "$SHIM_PY" ]; then
        printf 'ERROR: shim source is missing or unsafe: %s\n' "$SHIM_PY" >&2
        printf '  Fix: restore the provider_shim directory from the DAAF repository.\n' >&2
        return 1
    fi
    local dependency
    for dependency in python3 curl jq ps awk wc od mktemp flock stat id; do
        if ! command -v "$dependency" >/dev/null 2>&1; then
            printf 'ERROR: required shim-manager dependency is unavailable: %s\n' "$dependency" >&2
            printf '  Fix: rebuild from the current DAAF Dockerfile.\n' >&2
            return 1
        fi
    done
    if ! pid_evidence_decoder_is_reliable || ! adjudicate_pid_roles; then
        printf 'ERROR: shim PID evidence is unsafe or could not be classified (reason=%s); state was preserved.\n' \
            "$PID_EVIDENCE_REASON" >&2
        return 1
    fi
    if pid_action_has_unmanaged_shim && [ "$action_kind" != "restart" ]; then
        PID_ACTION_FAILURE="unmanaged_shim"
        printf 'ERROR: exact-role shim PID lacks a verified supervisor; state was preserved.\n' >&2
        printf '  Fix: inspect the preserved PID evidence and stop that exact process before retrying.\n' >&2
        return 1
    fi
    load_expected_contract
}

queue_start_handoff_signal() {
    # Keep only the first pending lifecycle signal. One known signal is sufficient
    # to preserve the action's documented interruption result, and cleanup exits.
    [ -n "$START_SIGNAL_QUEUED" ] || START_SIGNAL_QUEUED="$1"
}

dispatch_queued_start_signal() {
    lifecycle_signal_checkpoint
}

restore_start_signal_handler() {
    # Queue-only handlers remain installed through natural shell exit. Test-only
    # injection exercises the installation boundary without putting work in a trap.
    install_lifecycle_signal_handlers
    if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ "${DAAF_SHIM_TEST_SIGNAL_DURING_RESTORE:-}" = "after_int" ]; then
        DAAF_SHIM_TEST_SIGNAL_DURING_RESTORE=""
        kill -TERM "$$"
    fi
    lifecycle_signal_checkpoint
}

do_start_locked() {
    local launch_kind="${1:-explicit}" waited=0 spawned=0 supervisor_pid=""
    local supervisor_is_running=0
    START_FAILURE_KIND="preflight"
    ACTIVE_LAUNCH_PID=""
    ACTIVE_LAUNCH_STREAM_DIR=""
    ACTIVE_LAUNCH_STREAM_FD=""
    ACTIVE_LAUNCH_WORKSPACE_TOKEN=""
    if [ "$launch_kind" != "restart" ]; then
        START_SIGNAL_QUEUED=""
    fi

    if ! preflight_start_contract "$launch_kind"; then
        if [ "$PID_INSPECTION_FAILURE" = "infrastructure" ] || \
            [ "$PID_ACTION_FAILURE" = "infrastructure" ]; then
            START_FAILURE_KIND="pid_evidence_infrastructure"
        elif [ -n "$PID_ACTION_FAILURE" ] || [ -n "$PID_INSPECTION_FAILURE" ]; then
            START_FAILURE_KIND="pid_evidence"
        fi
        return 1
    fi
    START_FAILURE_KIND="launch"

    printf 'Shim backend mode: %s.\n' "$EXPECTED_BACKEND_MODE" >&2
    if [ "$EXPECTED_BACKEND_MODE" = "chatgpt" ]; then
        if [ -z "${CODEX_HOME:-}" ]; then
            printf 'WARNING: SHIM_BACKEND_MODE=chatgpt but CODEX_HOME is unset.\n' >&2
            printf '  Fix: set CODEX_HOME and run codex login --device-auth.\n' >&2
        elif [ ! -r "${CODEX_HOME}/auth.json" ]; then
            printf 'WARNING: chatgpt auth store is missing/unreadable at $CODEX_HOME/auth.json.\n' >&2
            printf '  Fix: run codex login --device-auth inside the container.\n' >&2
        else
            printf 'chatgpt auth store present at $CODEX_HOME/auth.json.\n' >&2
        fi
    fi

    if is_healthy; then
        START_FAILURE_KIND="none"
        printf 'Shim already running and strictly ready on port %s.\n' "$SHIM_PORT" >&2
        print_auth_line
        return 0
    fi
    if [ "$PID_ACTION_SUP_ROLE" = "exact" ]; then
        START_FAILURE_KIND="readiness"
        printf 'WARNING: shim supervisor is running but strict readiness failed.\n' >&2
        emit_readiness_failure
        return 1
    fi
    # If another HTTP service answered /health, do not start a crash loop against
    # its occupied port. Only an unreachable endpoint is eligible for launch.
    if [ "$HEALTH_REASON" != "unreachable" ]; then
        START_FAILURE_KIND="readiness"
        printf 'ERROR: port %s answered /health but not with this shim contract.\n' "$SHIM_PORT" >&2
        emit_readiness_failure
        return 1
    fi

    rm -f "$PID_FILE" "$SUP_PID_FILE" "$SUP_STATE_FILE" "$PGID_FILE" "$STOP_FILE" 2>/dev/null || true
    rotate_log_if_needed || return 1

    allocate_launch_stream_workspace || return 1

    # The detached generation must not inherit foreground-only descriptors. The
    # stream workspace path is passed as an argv capability; its descriptor and
    # lifecycle lock stay solely with the manager across the launch handoff.
    local launch_lock_fd="$LIFECYCLE_LOCK_FD"
    local launch_stream_fd="$ACTIVE_LAUNCH_STREAM_FD"
    local launch_stream_dir="$ACTIVE_LAUNCH_STREAM_DIR"
    local launch_workspace_token="$ACTIVE_LAUNCH_WORKSPACE_TOKEN"
    local handoff_signal="${DAAF_SHIM_TEST_HANDOFF_SIGNAL:-}"
    if [ "${DAAF_SHIM_TEST_MODE:-0}" != "1" ]; then
        handoff_signal=""
    else
        case "$handoff_signal" in
            ''|INT|TERM|HUP) ;;
            *) release_launch_stream_workspace 1; return 1 ;;
        esac
    fi
    trap 'queue_start_handoff_signal INT' INT
    trap 'queue_start_handoff_signal TERM' TERM
    trap 'queue_start_handoff_signal HUP' HUP
    if command -v setsid >/dev/null 2>&1 && \
        { [ "${DAAF_SHIM_TEST_MODE:-0}" != "1" ] || \
          [ "${DAAF_SHIM_TEST_NO_SETSID:-0}" != "1" ]; }; then
        (
            exec {launch_lock_fd}<&-
            exec {launch_stream_fd}>&-
            trap - PIPE
            exec setsid "${BASH_SOURCE[0]}" __supervise "$launch_stream_dir" "$launch_workspace_token"
        ) >/dev/null 2>&1 &
    else
        (
            exec {launch_lock_fd}<&-
            exec {launch_stream_fd}>&-
            trap - PIPE
            exec nohup "${BASH_SOURCE[0]}" __supervise "$launch_stream_dir" "$launch_workspace_token"
        ) >/dev/null 2>&1 &
    fi
    if [ -n "$handoff_signal" ]; then
        kill "-${handoff_signal}" "$$"
    fi
    supervisor_pid=$!
    ACTIVE_LAUNCH_PID="$supervisor_pid"
    spawned=1
    restore_start_signal_handler
    disown 2>/dev/null || true

    while [ "$waited" -lt "$readiness_wait" ]; do
        lifecycle_signal_checkpoint
        # PID publication transfers setup ownership to the supervisor. Until that
        # exact identity is visible, retain the FIFO anchor and workspace path so
        # pre-publication death remains recoverable by this foreground manager.
        if [ -n "$ACTIVE_LAUNCH_STREAM_FD" ] && supervisor_running; then
            # Publication permits closing the FIFO anchor, but the manager retains
            # the exact private path until strict readiness transfers cleanup fully.
            release_launch_stream_anchor
        fi
        if [ "$PID_ACTION_UNCERTAIN" -eq 1 ]; then
            START_FAILURE_KIND="pid_evidence_infrastructure"
            release_launch_stream_workspace 0
            ACTIVE_LAUNCH_PID=""
            return 1
        fi
        if is_healthy; then
            START_FAILURE_KIND="none"
            ACTIVE_LAUNCH_PID=""
            release_launch_stream_workspace 0
            printf 'Shim started and strictly ready on port %s.\n' "$SHIM_PORT" >&2
            print_auth_line
            return 0
        fi
        # The detached process needs a scheduling turn to create supervisor.pid.
        # Keep waiting while the exact PID returned by the launch is alive; once
        # the pidfile exists, supervisor_running adds the cmdline identity check.
        if ! supervisor_running && ! kill -0 "$supervisor_pid" 2>/dev/null; then
            break
        fi
        if [ "$PID_ACTION_UNCERTAIN" -eq 1 ]; then
            START_FAILURE_KIND="pid_evidence_infrastructure"
            release_launch_stream_workspace 0
            ACTIVE_LAUNCH_PID=""
            return 1
        fi
        sleep 1
        waited=$((waited + 1))
    done

    supervisor_is_running=0
    supervisor_running && supervisor_is_running=1
    if [ "$PID_ACTION_UNCERTAIN" -eq 1 ]; then
        START_FAILURE_KIND="pid_evidence_infrastructure"
        release_launch_stream_workspace 0
        ACTIVE_LAUNCH_PID=""
        return 1
    fi
    if [ "$HEALTH_REASON" = "unreachable" ] && [ "$supervisor_is_running" -eq 0 ]; then
        START_FAILURE_KIND="launch"
        # If the exact launched supervisor died after publishing state, its SIGKILL
        # bypassed EXIT cleanup. Reclaim the now-stale manager-owned evidence while
        # this action still owns the lifecycle lock; never infer or signal a PID.
        if [ "$spawned" -eq 1 ] && ! kill -0 "$supervisor_pid" 2>/dev/null; then
            stop_processes_locked >/dev/null 2>&1 || true
        fi
    else
        START_FAILURE_KIND="readiness"
    fi
    printf 'WARNING: shim failed strict readiness within %ss. Check %s.\n' \
        "$readiness_wait" "$LOG_FILE" >&2
    emit_readiness_failure
    if [ "$launch_kind" != "auto" ] && [ "$spawned" -eq 1 ]; then
        stop_processes_locked >/dev/null 2>&1 || true
    fi
    if [ "$spawned" -eq 1 ] && ! kill -0 "$supervisor_pid" 2>/dev/null && \
        [ "$supervisor_is_running" -eq 0 ]; then
        release_launch_stream_workspace 1
    else
        release_launch_stream_workspace 0
    fi
    ACTIVE_LAUNCH_PID=""
    return 1
}

handle_start_interrupt() {
    local signal_name="$1" launch_pid="$ACTIVE_LAUNCH_PID" exit_code=130 launch_waited=0
    # Once acquired, the lifecycle descriptor remains locked throughout cleanup.
    # Before acquisition there is no launch owned by this action and nothing to stop.
    if [ "$LIFECYCLE_LOCK_HELD" -eq 1 ]; then
        # The direct PID closes the pre-publication window; pidfiles close later ones.
        # Give the just-forked Bash wrapper a bounded turn to exec __supervise so
        # exact cmdline identity can be established before any signal is sent.
        while [ -n "$launch_pid" ] && kill -0 "$launch_pid" 2>/dev/null && \
            ! pid_is_supervisor "$launch_pid" && [ "$launch_waited" -lt 100 ]; do
            sleep 0.01
            launch_waited=$((launch_waited + 1))
        done
        if [ -n "$launch_pid" ] && pid_is_supervisor "$launch_pid"; then
            terminate_verified_pid supervisor "$launch_pid" || true
        fi
        stop_processes_locked >/dev/null 2>&1 || true
    fi
    # This manager allocated and retained the path before launch, so it can
    # reclaim a dead pre-publication supervisor's private transport without
    # trusting any on-disk owner metadata.
    release_launch_stream_workspace 1
    if [ "$START_INTERRUPT_KIND" = "auto" ]; then
        exit_code=0
    fi
    if [ "$VALIDATED_STATE_GATE" -eq 1 ]; then
        manager_log_line "SHIM_START_INTERRUPTED status=interrupted kind=${START_INTERRUPT_KIND} signal=${signal_name} cleanup=attempted exit_code=${exit_code}" || \
            printf 'SHIM_START_INTERRUPTED status=interrupted kind=%s signal=%s cleanup=attempted exit_code=%s record_persisted=no\n' \
                "$START_INTERRUPT_KIND" "$signal_name" "$exit_code" >&2
    else
        printf 'SHIM_START_INTERRUPTED status=interrupted kind=%s signal=%s cleanup=attempted exit_code=%s persistence=skipped_unvalidated_state\n' \
            "$START_INTERRUPT_KIND" "$signal_name" "$exit_code" >&2
    fi
    release_lifecycle_lock
    exit "$exit_code"
}

do_start() {
    local launch_kind="${1:-explicit}" rc
    begin_pid_action
    START_FAILURE_KIND="preflight"
    ensure_log_dir || return 1
    state_targets_are_safe || return 1
    VALIDATED_STATE_GATE=1
    START_FAILURE_KIND="lifecycle_lock"
    START_INTERRUPT_KIND="$launch_kind"
    START_SIGNAL_QUEUED=""
    install_lifecycle_signal_handlers
    if [ "$launch_kind" = "auto" ]; then
        acquire_lifecycle_lock no_wait || return 1
    else
        acquire_lifecycle_lock wait || return 1
    fi
    lifecycle_signal_checkpoint
    do_start_locked "$launch_kind"
    rc=$?
    lifecycle_signal_checkpoint
    release_lifecycle_lock
    lifecycle_signal_checkpoint
    return "$rc"
}

do_stop() {
    local stop_rc
    begin_pid_action
    ensure_log_dir || return 1
    state_targets_are_safe || return 1
    if ! pid_reader_dependencies_available; then
        printf 'ERROR: shim stop unavailable because PID evidence could not be decoded safely.\n' >&2
        return 1
    fi
    acquire_lifecycle_lock || return 1
    if stop_processes_locked; then
        stop_rc=0
    else
        stop_rc=$?
    fi
    release_lifecycle_lock
    case "$stop_rc" in
        0)
            printf 'Shim stopped.\n' >&2
            return 0
            ;;
        3)
            printf 'Shim was not running.\n' >&2
            return 0
            ;;
        4)
            printf 'ERROR: shim stop unavailable because PID evidence could not be decoded safely.\n' >&2
            printf '  Fix: restore python3 and lifecycle_capability.py, then retry --stop. State evidence was preserved.\n' >&2
            return 1
            ;;
        *)
            printf 'ERROR: shim stop did not terminate every verified process.\n' >&2
            printf '  Fix: inspect %s and retry --stop before starting another generation.\n' \
                "$LOG_FILE" >&2
            return 1
            ;;
    esac
}

# Restart exit codes are intentionally distinct for automation:
# 40 stop failure, 41 launch failure, 42 strict-readiness failure,
# 43 manager-record failure, and 130 interruption.
RESTART_PHASE="not_started"
RESTART_RESULT_STATE="NONE"
RESTART_COMMITTED_EXIT=43
RESTART_OLD_SUPERVISOR_PID="-"
RESTART_OLD_SHIM_PID="-"

commit_restart_result_locked() {
    local payload="$1" intended_exit="$2" record diagnostic append_rc=0
    case "$RESTART_RESULT_STATE" in
        NONE|PREPARING) ;;
        COMMITTED) return 0 ;;
        APPENDING|APPEND_FAILED) return 1 ;;
        *) RESTART_RESULT_STATE="APPEND_FAILED"; return 1 ;;
    esac
    RESTART_RESULT_STATE="PREPARING"
    if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ "${DAAF_SHIM_TEST_SIGNAL_RESULT_IN_PROGRESS:-0}" = "1" ]; then
        DAAF_SHIM_TEST_SIGNAL_RESULT_IN_PROGRESS=0
        kill -TERM "$$"
    fi
    # A pre-append signal is settled by mainline cleanup before this operation is
    # retried once with the interrupt payload. No append has begun at this state.
    [ -z "$START_SIGNAL_QUEUED" ] || return 2
    RESTART_RESULT_STATE="APPENDING"
    record="$(printf '%s MANAGER %s' "$(date -u '+%Y-%m-%d %H:%M:%S')" "$payload")"
    append_log_record "$record" || append_rc=$?
    if [ "$append_rc" -eq 0 ]; then
        RESTART_COMMITTED_EXIT="$intended_exit"
        RESTART_RESULT_STATE="COMMITTED"
    else
        RESTART_COMMITTED_EXIT=43
        RESTART_RESULT_STATE="APPEND_FAILED"
    fi
    if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ -n "${DAAF_SHIM_TEST_SIGNAL_AFTER_APPEND_ATTEMPT:-}" ]; then
        case "$DAAF_SHIM_TEST_SIGNAL_AFTER_APPEND_ATTEMPT" in
            INT|TERM|HUP)
                kill "-${DAAF_SHIM_TEST_SIGNAL_AFTER_APPEND_ATTEMPT}" "$$"
                ;;
        esac
    fi
    if [ "$RESTART_RESULT_STATE" = "COMMITTED" ]; then
        best_effort_stderr_line "$record"
        return 0
    fi
    diagnostic="SHIM_RESTART_RESULT status=failed stage=record reason=manager_log_write exit_code=43 old_supervisor_pid=${RESTART_OLD_SUPERVISOR_PID} old_shim_pid=${RESTART_OLD_SHIM_PID} new_supervisor_pid=- port=${SHIM_PORT} record_persisted=unknown"
    best_effort_stderr_line "$diagnostic"
    return 1
}

emit_restart_result_locked() {
    local status="$1" stage="$2" reason="$3" exit_code="$4" new_supervisor_pid="${5:--}"
    local payload rc=0
    payload="SHIM_RESTART_RESULT status=${status} stage=${stage} reason=${reason} exit_code=${exit_code} old_supervisor_pid=${RESTART_OLD_SUPERVISOR_PID} old_shim_pid=${RESTART_OLD_SHIM_PID} new_supervisor_pid=${new_supervisor_pid} port=${SHIM_PORT}"
    commit_restart_result_locked "$payload" "$exit_code" || rc=$?
    if [ "$rc" -eq 2 ] || [ -n "$START_SIGNAL_QUEUED" ]; then
        lifecycle_signal_checkpoint
    fi
    return "$rc"
}

handle_restart_interrupt() {
    local signal_name="$1" launch_waited=0
    if [ "$RESTART_RESULT_STATE" = "COMMITTED" ]; then
        release_lifecycle_lock
        exit "$RESTART_COMMITTED_EXIT"
    fi
    if [ "$RESTART_RESULT_STATE" = "APPEND_FAILED" ]; then
        stop_processes_locked >/dev/null 2>&1 || true
        release_launch_stream_workspace 1 || true
        release_lifecycle_lock
        exit 43
    fi
    RESTART_PHASE="interrupted_${RESTART_PHASE}"
    while [ -n "$ACTIVE_LAUNCH_PID" ] && kill -0 "$ACTIVE_LAUNCH_PID" 2>/dev/null && \
        ! pid_is_supervisor "$ACTIVE_LAUNCH_PID" && [ "$launch_waited" -lt 100 ]; do
        sleep 0.01
        launch_waited=$((launch_waited + 1))
    done
    if [ -n "$ACTIVE_LAUNCH_PID" ] && pid_is_supervisor "$ACTIVE_LAUNCH_PID"; then
        terminate_verified_pid supervisor "$ACTIVE_LAUNCH_PID" || true
    fi
    stop_processes_locked >/dev/null 2>&1 || true
    release_launch_stream_workspace 1 || true
    START_SIGNAL_QUEUED=""
    if ! emit_restart_result_locked failed interrupt "signal_${signal_name}" 130 -; then
        release_lifecycle_lock
        exit 43
    fi
    release_lifecycle_lock
    exit 130
}

do_restart() {
    local prior="stopped" stop_rc start_rc new_supervisor_pid="-"

    begin_pid_action
    # The foreground restart manager treats stderr as best-effort presentation.
    # INT/TERM/HUP are queue-only from entry through natural shell exit.
    trap '' PIPE
    START_INTERRUPT_KIND="restart"
    START_SIGNAL_QUEUED=""
    install_lifecycle_signal_handlers
    ensure_log_dir || return 43
    state_targets_are_safe || return 43
    acquire_lifecycle_lock || return 43
    lifecycle_signal_checkpoint
    preflight_start_contract restart || {
        manager_log_line "SHIM_RESTART_BEGIN status=begin prior=unknown old_supervisor_pid=- old_shim_pid=- port=${SHIM_PORT}" || true
        if ! emit_restart_result_locked failed launch launch_preflight_failed 41 -; then
            release_lifecycle_lock
            return 43
        fi
        release_lifecycle_lock
        return 41
    }

    RESTART_PHASE="inspect"
    RESTART_RESULT_STATE="NONE"
    RESTART_COMMITTED_EXIT=43
    RESTART_OLD_SUPERVISOR_PID="${PID_ACTION_SUP_PID:--}"
    RESTART_OLD_SHIM_PID="${PID_ACTION_SHIM_PID:--}"

    if is_healthy; then
        prior="running_ready"
    elif [ "$PID_ACTION_SUP_ROLE" = "exact" ]; then
        prior="running_unready"
    elif [ "$HEALTH_REASON" != "unreachable" ]; then
        prior="unexpected_service"
    fi

    if ! manager_log_line "SHIM_RESTART_BEGIN status=begin prior=${prior} old_supervisor_pid=${RESTART_OLD_SUPERVISOR_PID} old_shim_pid=${RESTART_OLD_SHIM_PID} port=${SHIM_PORT}"; then
        printf 'SHIM_RESTART_RESULT status=failed stage=record reason=manager_log_write exit_code=43 old_supervisor_pid=%s old_shim_pid=%s new_supervisor_pid=- port=%s record_persisted=no\n' \
            "$RESTART_OLD_SUPERVISOR_PID" "$RESTART_OLD_SHIM_PID" "$SHIM_PORT" >&2
        release_lifecycle_lock
        return 43
    fi
    if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ -n "${DAAF_SHIM_TEST_AFTER_RESTART_BEGIN_DELAY_S:-}" ]; then
        sleep "$DAAF_SHIM_TEST_AFTER_RESTART_BEGIN_DELAY_S"
    fi

    install_lifecycle_signal_handlers
    lifecycle_signal_checkpoint

    # A healthy endpoint without manager-owned process identity must never be
    # signalled or mistaken for a generation this manager may replace.
    if [ "$prior" = "running_ready" ] && \
        [ "$RESTART_OLD_SUPERVISOR_PID" = "-" ] && \
        [ "$RESTART_OLD_SHIM_PID" = "-" ]; then
        if ! emit_restart_result_locked failed stop unmanaged_ready_service 40 -; then
            release_lifecycle_lock
            return 43
        fi
        release_lifecycle_lock
        return 40
    fi

    RESTART_PHASE="stop"
    if stop_processes_locked; then
        stop_rc=0
    else
        stop_rc=$?
    fi
    case "$stop_rc" in
        0|3)
            ;;
        *)
            if ! emit_restart_result_locked failed stop termination_failed 40 -; then
                release_lifecycle_lock
                return 43
            fi
            release_lifecycle_lock
            return 40
            ;;
    esac
    lifecycle_signal_checkpoint

    RESTART_PHASE="launch"
    START_INTERRUPT_KIND="restart"
    do_start_locked restart
    start_rc=$?
    if [ "$start_rc" -ne 0 ]; then
        stop_processes_locked >/dev/null 2>&1 || true
        if [ "$START_FAILURE_KIND" = "launch" ]; then
            if ! emit_restart_result_locked failed launch launch_failed 41 -; then
                release_lifecycle_lock
                return 43
            fi
            release_lifecycle_lock
            return 41
        fi
        if ! emit_restart_result_locked failed readiness strict_readiness_failed 42 -; then
            release_lifecycle_lock
            return 43
        fi
        release_lifecycle_lock
        return 42
    fi

    RESTART_PHASE="verify"
    if ! probe_health; then
        emit_readiness_failure
        stop_processes_locked >/dev/null 2>&1 || true
        if ! emit_restart_result_locked failed readiness strict_readiness_failed 42 -; then
            release_lifecycle_lock
            return 43
        fi
        release_lifecycle_lock
        return 42
    fi

    new_supervisor_pid="$(read_pid_file "$SUP_PID_FILE")" || new_supervisor_pid="-"
    if [ "$new_supervisor_pid" = "-" ] || ! pid_is_supervisor "$new_supervisor_pid" || \
        { [ "$RESTART_OLD_SUPERVISOR_PID" != "-" ] && \
          [ "$new_supervisor_pid" = "$RESTART_OLD_SUPERVISOR_PID" ]; }; then
        stop_processes_locked >/dev/null 2>&1 || true
        if ! emit_restart_result_locked failed readiness supervisor_identity_invalid 42 \
            "$new_supervisor_pid"; then
            release_lifecycle_lock
            return 43
        fi
        release_lifecycle_lock
        return 42
    fi

    RESTART_PHASE="ready"
    # Queue interrupts while the durable READY record crosses its commit boundary.
    # The queue is replayed pre-commit on append failure and post-commit otherwise.
    START_SIGNAL_QUEUED=""
    trap 'queue_start_handoff_signal INT' INT
    trap 'queue_start_handoff_signal TERM' TERM
    trap 'queue_start_handoff_signal HUP' HUP
    if ! emit_restart_result_locked ready readiness ready 0 "$new_supervisor_pid"; then
        stop_processes_locked >/dev/null 2>&1 || true
        release_launch_stream_workspace 1 || true
        restore_start_signal_handler
        release_lifecycle_lock
        return 43
    fi
    # Durable READY is the commit boundary: from here the committed state and exit
    # govern, even if a signal is queued during the remaining epilogue.
    if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ "${DAAF_SHIM_TEST_SIGNAL_AFTER_READY:-0}" = "1" ]; then
        DAAF_SHIM_TEST_SIGNAL_AFTER_READY=0
        kill -TERM "$$"
    fi
    restore_start_signal_handler
    release_lifecycle_lock
    if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ "${DAAF_SHIM_TEST_SIGNAL_AFTER_LOCK_RELEASE:-0}" = "1" ]; then
        DAAF_SHIM_TEST_SIGNAL_AFTER_LOCK_RELEASE=0
        kill -TERM "$$"
    fi
    lifecycle_signal_checkpoint
    best_effort_stderr_line "Shim restarted and strictly ready on port ${SHIM_PORT}."
    lifecycle_signal_checkpoint
    if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ -n "${DAAF_SHIM_TEST_SIGNAL_AT_NATURAL_RETURN:-}" ]; then
        case "$DAAF_SHIM_TEST_SIGNAL_AT_NATURAL_RETURN" in
            INT|TERM|HUP) kill "-${DAAF_SHIM_TEST_SIGNAL_AT_NATURAL_RETURN}" "$$" ;;
        esac
    fi
    lifecycle_signal_checkpoint
    return "$RESTART_COMMITTED_EXIT"
}

do_status() {
    begin_pid_action
    if ! command -v curl >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then
        printf 'STATUS: unavailable (curl and jq are required for strict readiness)\n'
        return 1
    fi
    if ! pid_evidence_decoder_is_reliable || ! adjudicate_pid_roles; then
        printf 'STATUS: unavailable (PID evidence decoder failed; state preserved)\n'
        return 1
    fi
    if pid_action_has_unmanaged_shim; then
        printf 'STATUS: unavailable (exact-role shim PID lacks a verified supervisor; state preserved)\n'
        return 1
    fi
    if [ ! -f "$SHIM_PY" ] || ! load_expected_contract; then
        printf 'STATUS: unavailable (shim source/version contract missing)\n'
        return 1
    fi
    if is_healthy; then
        printf 'STATUS: running and strictly ready (port %s)\n' "$SHIM_PORT"
        printf 'HEALTH: %s\n' "$HEALTH_JSON"
        print_auth_line
        return 0
    fi
    if [ "$PID_ACTION_SUP_ROLE" = "exact" ]; then
        printf 'STATUS: supervisor up but shim not strictly ready (port %s)\n' "$SHIM_PORT"
        emit_readiness_failure
        return 1
    fi
    if [ "$HEALTH_REASON" != "unreachable" ]; then
        printf 'STATUS: unexpected service on shim port %s\n' "$SHIM_PORT"
        emit_readiness_failure
        return 1
    fi
    # A supervisor that exhausted its restart-storm budget exits and removes its
    # PID files, leaving a state otherwise indistinguishable from "never started".
    # The persisted supervisor.state record makes that terminal condition visible.
    local state_line state_phase state_ts
    state_line="$(read_supervisor_state)" || state_line=""
    if [ -n "$state_line" ]; then
        state_phase="${state_line%%$'\t'*}"
        state_ts="${state_line#*$'\t'}"
        if [ "$state_phase" = "gave_up_storm" ]; then
            printf 'STATUS: stopped (supervisor gave up after restart storm at %s)\n' \
                "${state_ts:-unknown}"
            return 0
        fi
    fi
    printf 'STATUS: stopped\n'
    return 0
}

do_auto() {
    local requested="${DAAF_PROVIDER_SHIM:-}" observed auto_reason
    # Empty/unset stays a silent no-op: the shim is opt-in and must not announce
    # itself on every boot where it was never requested.
    if [ -z "$requested" ]; then
        exit 0
    fi
    # An unrecognized non-empty value is almost always a config footgun (e.g. a
    # user who set the switch to a lane label like "chatgpt"). Make it visible
    # instead of silently not starting, but still exit 0 so a misconfiguration
    # never blocks container startup. ensure_log_dir runs first so the MANAGER
    # record is never lost to the early return the old code took before it.
    if [ "$requested" != "openai" ]; then
        # Sanitize the observed value to a bounded single-line token before it
        # reaches the grep-stable log format or the terminal: it is user-supplied
        # and could otherwise inject a newline/space and forge a second record.
        observed="$(printf '%s' "$requested" | tr -c 'A-Za-z0-9._-' '_' | cut -c1-64)"
        if ensure_log_dir; then
            manager_log_line "SHIM_AUTO_SKIPPED status=skipped reason=unrecognized_provider_shim observed=${observed} accepted=openai continuing_boot=y" || \
                printf 'SHIM_AUTO_SKIPPED status=skipped reason=unrecognized_provider_shim observed=%s accepted=openai continuing_boot=y\n' "$observed" >&2
        fi
        printf 'WARNING: DAAF_PROVIDER_SHIM=%s is not a recognized shim auto-start value; the only accepted value is "openai". Leaving the shim stopped and continuing boot.\n' \
            "$observed" >&2
        exit 0
    fi
    ensure_log_dir || {
        printf 'SHIM_AUTO_FAILURE status=failed reason=preflight continuing_boot=y\n' >&2
        exit 0
    }
    if ! do_start auto; then
        case "$START_FAILURE_KIND" in
            lifecycle_lock) auto_reason="lifecycle_lock" ;;
            preflight) auto_reason="preflight" ;;
            pid_evidence_infrastructure) auto_reason="pid_evidence_infrastructure" ;;
            pid_evidence) auto_reason="pid_evidence" ;;
            readiness) auto_reason="strict_readiness" ;;
            launch) auto_reason="launch_setup" ;;
            *) auto_reason="launch_setup" ;;
        esac
        manager_log_line "SHIM_AUTO_FAILURE status=failed reason=${auto_reason} continuing_boot=y" || \
            printf 'SHIM_AUTO_FAILURE status=failed reason=%s continuing_boot=y record_persisted=no\n' \
                "$auto_reason" >&2
    else
        manager_log_line "SHIM_AUTO_READY status=ready continuing_boot=y" || \
            printf 'SHIM_AUTO_FAILURE status=failed reason=manager_log_write continuing_boot=y\n' >&2
    fi
    exit 0
}

# --- Internal deterministic-test action ------------------------------------
do_rotate_only() {
    acquire_lifecycle_lock || return 1
    rotate_log_if_needed
    local rc=$?
    release_lifecycle_lock
    return "$rc"
}

# --- Dispatch ---------------------------------------------------------------
print_usage() {
    printf 'Usage: %s {--auto|--start|--restart|--stop|--status|--help}\n' \
        "$(basename "${BASH_SOURCE[0]}")"
}

ACTION="${1:-}"
case "$ACTION" in
    __supervise)
        load_expected_contract || exit 1
        run_supervisor "${2:-}" "${3:-}"
        ;;
    __rotate_logs)
        do_rotate_only
        ;;
    --auto)
        do_auto
        ;;
    --start)
        do_start explicit
        ;;
    --restart)
        do_restart
        ;;
    --stop)
        do_stop
        ;;
    --status)
        do_status
        ;;
    --help|-h)
        print_usage
        ;;
    *)
        print_usage >&2
        exit 1
        ;;
esac
