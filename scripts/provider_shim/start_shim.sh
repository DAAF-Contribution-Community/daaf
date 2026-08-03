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
readonly LOG_DIR="${SCRIPT_DIR}/logs"
readonly LOG_FILE="${LOG_DIR}/shim.log"
readonly PID_FILE="${LOG_DIR}/shim.pid"
readonly SUP_PID_FILE="${LOG_DIR}/supervisor.pid"
readonly SUP_STATE_FILE="${LOG_DIR}/supervisor.state"
readonly PGID_FILE="${LOG_DIR}/pgid"
readonly STOP_FILE="${LOG_DIR}/stop.requested"
readonly QUOTA_STATE_FILE="${LOG_DIR}/quota_state.json"
readonly LOCK_DIR="${LOG_DIR}/lifecycle.lock"
readonly LOCK_OWNER_FILE="${LOCK_DIR}/owner.pid"
readonly LOG_WRITE_LOCK_DIR="${LOG_DIR}/log-write.lock"
readonly LOG_WRITE_OWNER_FILE="${LOG_WRITE_LOCK_DIR}/owner.pid"
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
if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ]; then
    storm_limit="${DAAF_SHIM_TEST_STORM_LIMIT:-$STORM_LIMIT}"
    storm_window="${DAAF_SHIM_TEST_STORM_WINDOW:-$STORM_WINDOW}"
    restart_delay="${DAAF_SHIM_TEST_RESTART_DELAY:-$RESTART_DELAY}"
    readiness_wait="${DAAF_SHIM_TEST_READINESS_WAIT:-$READINESS_WAIT}"
fi

HEALTH_JSON=""
HEALTH_REASON="not_probed"
EXPECTED_SHIM_VERSION=""
EXPECTED_BACKEND_MODE="openai"
START_FAILURE_KIND="not_started"
ACTIVE_LAUNCH_PID=""
LIFECYCLE_LOCK_HELD=0

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

acquire_log_write_lock() {
    local owner attempts=0
    while [ "$attempts" -lt 200 ]; do
        if mkdir "$LOG_WRITE_LOCK_DIR" 2>/dev/null; then
            printf '%s\n' "${BASHPID:-$$}" > "$LOG_WRITE_OWNER_FILE" || return 1
            chmod 0700 "$LOG_WRITE_LOCK_DIR" || return 1
            chmod 0600 "$LOG_WRITE_OWNER_FILE" || return 1
            return 0
        fi
        owner="$(read_pid_file "$LOG_WRITE_OWNER_FILE")" || owner=""
        if [ -z "$owner" ] || ! kill -0 "$owner" 2>/dev/null; then
            rm -f "$LOG_WRITE_OWNER_FILE" 2>/dev/null || true
            rmdir "$LOG_WRITE_LOCK_DIR" 2>/dev/null || true
        else
            sleep 0.01
        fi
        attempts=$((attempts + 1))
    done
    printf 'ERROR: timed out acquiring shim log-write lock: %s\n' \
        "$LOG_WRITE_LOCK_DIR" >&2
    return 1
}

release_log_write_lock() {
    rm -f "$LOG_WRITE_OWNER_FILE" 2>/dev/null || true
    rmdir "$LOG_WRITE_LOCK_DIR" 2>/dev/null || true
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

manager_log_line() {
    # Foreground manager events append once and remain visible to their caller.
    local record
    record="$(printf '%s MANAGER %s' "$(date -u '+%Y-%m-%d %H:%M:%S')" "$*")"
    append_log_record "$record" || return 1
    printf '%s\n' "$record" >&2
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

read_pid_file() {
    local path="$1" value
    value="$(awk 'NR == 1 { print; exit }' "$path" 2>/dev/null)"
    is_decimal_pid "$value" || return 1
    printf '%s' "$value"
}

pid_has_exact_arg() {
    local pid="$1" expected="$2" arg
    [ -r "/proc/${pid}/cmdline" ] || return 1
    while IFS= read -r -d '' arg; do
        [ "$arg" = "$expected" ] && return 0
    done < "/proc/${pid}/cmdline"
    return 1
}

pid_is_supervisor() {
    local pid="$1"
    is_decimal_pid "$pid" || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    pid_has_exact_arg "$pid" "$SHIM_PY" && return 1
    pid_has_exact_arg "$pid" "${BASH_SOURCE[0]}" || return 1
    pid_has_exact_arg "$pid" "__supervise"
}

pid_is_shim() {
    local pid="$1"
    is_decimal_pid "$pid" || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    pid_has_exact_arg "$pid" "$SHIM_PY"
}

supervisor_running() {
    local sp
    sp="$(read_pid_file "$SUP_PID_FILE")" || return 1
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

terminate_verified_pid() {
    local role="$1" pid="$2" waited=0
    case "$role" in
        supervisor) pid_is_supervisor "$pid" || return 1 ;;
        shim) pid_is_shim "$pid" || return 1 ;;
        *) return 1 ;;
    esac
    kill -TERM "$pid" 2>/dev/null || true
    while [ "$waited" -lt 5 ]; do
        if [ "$role" = "supervisor" ]; then
            pid_is_supervisor "$pid" || return 0
        else
            pid_is_shim "$pid" || return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done
    if [ "$role" = "supervisor" ]; then
        pid_is_supervisor "$pid" && kill -KILL "$pid" 2>/dev/null || true
    else
        pid_is_shim "$pid" && kill -KILL "$pid" 2>/dev/null || true
    fi
    return 0
}

# --- Lifecycle lock ---------------------------------------------------------
acquire_lifecycle_lock() {
    local wait_mode="${1:-wait}" owner attempts=0
    ensure_log_dir || return 1
    state_targets_are_safe || return 1

    # Public lifecycle actions serialize by waiting for the current live owner.
    # This lock is deliberately acquired only by outer action wrappers; helpers
    # with a _locked suffix never recurse into this non-reentrant lock.
    # Sixty seconds exceeds the manager's five-second stop plus 15-second
    # readiness budget while remaining bounded if an owner is wedged.
    while [ "$attempts" -lt 6000 ]; do
        if mkdir "$LOCK_DIR" 2>/dev/null; then
            LIFECYCLE_LOCK_HELD=1
            trap release_lifecycle_lock EXIT
            trap 'exit 130' INT TERM HUP
            if ! printf '%s\n' "$$" > "$LOCK_OWNER_FILE"; then
                release_lifecycle_lock
                return 1
            fi
            if ! chmod 0700 "$LOCK_DIR" || ! chmod 0600 "$LOCK_OWNER_FILE"; then
                release_lifecycle_lock
                return 1
            fi
            return 0
        fi

        owner="$(read_pid_file "$LOCK_OWNER_FILE")" || owner=""
        if [ -z "$owner" ] || ! kill -0 "$owner" 2>/dev/null; then
            # A dead/malformed owner means a prior manager died while holding the
            # lock. Remove only the known owner file and empty lock directory.
            rm -f "$LOCK_OWNER_FILE" 2>/dev/null || true
            rmdir "$LOCK_DIR" 2>/dev/null || true
        else
            if [ "$wait_mode" = "no_wait" ]; then
                printf 'ERROR: another shim lifecycle action is active (pid %s).\n' "$owner" >&2
                printf '  Fix: let it finish; boot will continue and a later health check can retry.\n' >&2
                return 1
            fi
            sleep 0.01
        fi
        attempts=$((attempts + 1))
    done

    printf 'ERROR: timed out acquiring shim lifecycle lock: %s\n' "$LOCK_DIR" >&2
    printf '  Fix: wait for the active lifecycle action to finish, then retry.\n' >&2
    return 1
}

release_lifecycle_lock() {
    local owner=""
    if [ "$LIFECYCLE_LOCK_HELD" -eq 1 ]; then
        owner="$(read_pid_file "$LOCK_OWNER_FILE")" || owner=""
        if [ "$owner" = "$$" ]; then
            rm -f "$LOCK_OWNER_FILE" 2>/dev/null || true
            rmdir "$LOCK_DIR" 2>/dev/null || true
        fi
        LIFECYCLE_LOCK_HELD=0
    fi
    trap - EXIT INT TERM HUP
}

# --- Keepalive supervisor ---------------------------------------------------
run_supervisor() {
    ensure_log_dir || exit 1
    state_targets_are_safe || exit 1
    printf '%s\n' "$$" > "$SUP_PID_FILE" || exit 1
    chmod 0600 "$SUP_PID_FILE" || exit 1

    local pgid child_pid logger_pid log_pipe window_start crashes rc now gave_up_storm
    pgid="$(ps -o pgid= -p "$$" 2>/dev/null | tr -d ' ')"
    if [ "$pgid" = "$$" ]; then
        printf '%s\n' "$pgid" > "$PGID_FILE" || exit 1
        chmod 0600 "$PGID_FILE" || exit 1
    else
        # nohup fallback may share the caller's process group. Never record or kill
        # that broad group; verified per-pid teardown is safer.
        rm -f "$PGID_FILE" 2>/dev/null || true
        log_line "process-group isolation unavailable; using verified per-pid stop"
    fi

    rm -f "$STOP_FILE" 2>/dev/null || true
    child_pid=""
    logger_pid=""
    gave_up_storm=0
    log_pipe="${LOG_DIR}/shim.stream.$$"
    if [ -e "$log_pipe" ] || [ -L "$log_pipe" ]; then
        printf 'ERROR: refusing existing shim log-stream target: %s\n' "$log_pipe" >&2
        exit 1
    fi
    mkfifo "$log_pipe" || exit 1
    chmod 0600 "$log_pipe" || exit 1

    cleanup_supervisor() {
        if [ -n "$child_pid" ] && pid_is_shim "$child_pid"; then
            kill -TERM "$child_pid" 2>/dev/null || true
        fi
        if [ -n "$logger_pid" ] && kill -0 "$logger_pid" 2>/dev/null; then
            kill -TERM "$logger_pid" 2>/dev/null || true
            wait "$logger_pid" 2>/dev/null || true
        fi
        rm -f "$log_pipe" "$PID_FILE" "$SUP_PID_FILE" "$PGID_FILE" 2>/dev/null || true
        # A storm give-up already recorded gave_up_storm and must persist so
        # --status can report it distinctly; every other exit is a clean stop.
        if [ "$gave_up_storm" -eq 0 ]; then
            write_supervisor_state stopped || true
        fi
        log_line "supervisor exiting" || true
    }
    stop_supervisor_signal() {
        trap - INT TERM
        exit 0
    }
    trap cleanup_supervisor EXIT
    trap stop_supervisor_signal INT TERM

    window_start="$(date +%s)"
    crashes=0
    write_supervisor_state running || true
    log_line "starting shim on port ${SHIM_PORT} backend_mode=${EXPECTED_BACKEND_MODE} version=${EXPECTED_SHIM_VERSION} (keepalive on)"

    while true; do
        if [ -f "$STOP_FILE" ]; then
            log_line "stop requested; supervisor loop ending"
            exit 0
        fi

        write_stream_to_log < "$log_pipe" &
        logger_pid=$!
        python3 "$SHIM_PY" > "$log_pipe" 2>&1 &
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
    local stopped=0 failed=0 pgid sp pp waited

    # Sentinel first: the supervisor checks it before every launch and sleep tick.
    : > "$STOP_FILE" || return 2
    chmod 0600 "$STOP_FILE" 2>/dev/null || true

    sp="$(read_pid_file "$SUP_PID_FILE")" || sp=""
    pp="$(read_pid_file "$PID_FILE")" || pp=""
    pgid="$(read_pid_file "$PGID_FILE")" || pgid=""

    # Deterministic failure injection is confined to explicitly isolated tests.
    if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ "${DAAF_SHIM_TEST_STOP_FAILURE:-0}" = "1" ] && \
        { { [ -n "$sp" ] && pid_is_supervisor "$sp"; } || \
          { [ -n "$pp" ] && pid_is_shim "$pp"; }; }; then
        return 2
    fi

    if [ -n "$sp" ] && [ -n "$pgid" ] && process_group_is_owned "$pgid" "$sp"; then
        kill -TERM "-${pgid}" 2>/dev/null || true
        stopped=1
        waited=0
        while [ "$waited" -lt 5 ]; do
            if ! pid_is_supervisor "$sp" && { [ -z "$pp" ] || ! pid_is_shim "$pp"; }; then
                break
            fi
            sleep 1
            waited=$((waited + 1))
        done
        if pid_is_supervisor "$sp" && process_group_is_owned "$pgid" "$sp"; then
            kill -KILL "-${pgid}" 2>/dev/null || true
        fi
    fi

    # Missing/no-setsid PGID and stale-file cases use exact cmdline identity. A PID
    # recycled by an unrelated process is never signalled.
    if [ -n "$pp" ] && pid_is_shim "$pp"; then
        terminate_verified_pid shim "$pp" || true
        stopped=1
    fi
    if [ -n "$sp" ] && pid_is_supervisor "$sp"; then
        terminate_verified_pid supervisor "$sp" || true
        stopped=1
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
    if [ ! -f "$SHIM_PY" ] || [ -L "$SHIM_PY" ]; then
        printf 'ERROR: shim source is missing or unsafe: %s\n' "$SHIM_PY" >&2
        printf '  Fix: restore the provider_shim directory from the DAAF repository.\n' >&2
        return 1
    fi
    local dependency
    for dependency in python3 curl jq ps awk wc; do
        if ! command -v "$dependency" >/dev/null 2>&1; then
            printf 'ERROR: required shim-manager dependency is unavailable: %s\n' "$dependency" >&2
            printf '  Fix: rebuild from the current DAAF Dockerfile.\n' >&2
            return 1
        fi
    done
    load_expected_contract
}

do_start_locked() {
    local launch_kind="${1:-explicit}" waited=0 spawned=0 supervisor_pid=""
    START_FAILURE_KIND="launch"
    ACTIVE_LAUNCH_PID=""

    preflight_start_contract || return 1

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
    if supervisor_running; then
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

    if command -v setsid >/dev/null 2>&1 && [ "${DAAF_SHIM_TEST_NO_SETSID:-0}" != "1" ]; then
        setsid "${BASH_SOURCE[0]}" __supervise >/dev/null 2>&1 &
    else
        nohup "${BASH_SOURCE[0]}" __supervise >/dev/null 2>&1 &
    fi
    supervisor_pid=$!
    ACTIVE_LAUNCH_PID="$supervisor_pid"
    spawned=1
    disown 2>/dev/null || true

    while [ "$waited" -lt "$readiness_wait" ]; do
        if is_healthy; then
            START_FAILURE_KIND="none"
            ACTIVE_LAUNCH_PID=""
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
        sleep 1
        waited=$((waited + 1))
    done

    if [ "$HEALTH_REASON" = "unreachable" ] && ! supervisor_running; then
        START_FAILURE_KIND="launch"
    else
        START_FAILURE_KIND="readiness"
    fi
    printf 'WARNING: shim failed strict readiness within %ss. Check %s.\n' \
        "$readiness_wait" "$LOG_FILE" >&2
    emit_readiness_failure
    if [ "$launch_kind" != "auto" ] && [ "$spawned" -eq 1 ]; then
        stop_processes_locked >/dev/null 2>&1 || true
    fi
    ACTIVE_LAUNCH_PID=""
    return 1
}

do_start() {
    local launch_kind="${1:-explicit}" rc
    if [ "$launch_kind" = "auto" ]; then
        acquire_lifecycle_lock no_wait || return 1
    else
        acquire_lifecycle_lock wait || return 1
    fi
    do_start_locked "$launch_kind"
    rc=$?
    release_lifecycle_lock
    return "$rc"
}

do_stop() {
    local stop_rc
    ensure_log_dir || return 1
    state_targets_are_safe || return 1
    acquire_lifecycle_lock || return 1
    stop_processes_locked
    stop_rc=$?
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
RESTART_RESULT_WRITE_IN_PROGRESS=0
RESTART_RESULT_WRITTEN=0
RESTART_OLD_SUPERVISOR_PID="-"
RESTART_OLD_SHIM_PID="-"

emit_restart_result_locked() {
    local status="$1" stage="$2" reason="$3" exit_code="$4" new_supervisor_pid="${5:--}"
    local record
    [ "$RESTART_RESULT_WRITTEN" -eq 0 ] || return 0
    if [ "$RESTART_RESULT_WRITE_IN_PROGRESS" -eq 1 ]; then
        printf 'SHIM_RESTART_RESULT status=failed stage=record reason=write_interrupted exit_code=130 old_supervisor_pid=%s old_shim_pid=%s new_supervisor_pid=%s port=%s record_persisted=unknown\n' \
            "$RESTART_OLD_SUPERVISOR_PID" "$RESTART_OLD_SHIM_PID" \
            "$new_supervisor_pid" "$SHIM_PORT" >&2
        return 1
    fi

    record="SHIM_RESTART_RESULT status=${status} stage=${stage} reason=${reason} exit_code=${exit_code} old_supervisor_pid=${RESTART_OLD_SUPERVISOR_PID} old_shim_pid=${RESTART_OLD_SHIM_PID} new_supervisor_pid=${new_supervisor_pid} port=${SHIM_PORT}"
    RESTART_RESULT_WRITE_IN_PROGRESS=1
    if [ "${DAAF_SHIM_TEST_MODE:-0}" = "1" ] && \
        [ "${DAAF_SHIM_TEST_SIGNAL_RESULT_IN_PROGRESS:-0}" = "1" ]; then
        DAAF_SHIM_TEST_SIGNAL_RESULT_IN_PROGRESS=0
        kill -TERM "$$"
    fi
    if ! manager_log_line "$record"; then
        RESTART_RESULT_WRITE_IN_PROGRESS=0
        printf 'SHIM_RESTART_RESULT status=failed stage=record reason=manager_log_write exit_code=43 old_supervisor_pid=%s old_shim_pid=%s new_supervisor_pid=%s port=%s record_persisted=no\n' \
            "$RESTART_OLD_SUPERVISOR_PID" "$RESTART_OLD_SHIM_PID" \
            "$new_supervisor_pid" "$SHIM_PORT" >&2
        return 1
    fi
    RESTART_RESULT_WRITE_IN_PROGRESS=0
    RESTART_RESULT_WRITTEN=1
    return 0
}

handle_restart_interrupt() {
    local signal_name="$1" launch_waited=0 interrupted_during_write=0
    trap - INT TERM HUP
    RESTART_PHASE="interrupted_${RESTART_PHASE}"
    if [ "$RESTART_RESULT_WRITE_IN_PROGRESS" -eq 1 ]; then
        interrupted_during_write=1
        printf 'SHIM_RESTART_RESULT status=failed stage=record reason=write_interrupted exit_code=130 old_supervisor_pid=%s old_shim_pid=%s new_supervisor_pid=- port=%s record_persisted=unknown\n' \
            "$RESTART_OLD_SUPERVISOR_PID" "$RESTART_OLD_SHIM_PID" "$SHIM_PORT" >&2
    fi
    # Once an atomic restart has begun, interruption never leaves a newly launched
    # unverified generation behind. The direct launch PID closes the short window
    # before supervisor.pid is written; cmdline verification still precedes signal.
    while [ -n "$ACTIVE_LAUNCH_PID" ] && kill -0 "$ACTIVE_LAUNCH_PID" 2>/dev/null && \
        ! pid_is_supervisor "$ACTIVE_LAUNCH_PID" && [ "$launch_waited" -lt 100 ]; do
        sleep 0.01
        launch_waited=$((launch_waited + 1))
    done
    if [ -n "$ACTIVE_LAUNCH_PID" ] && pid_is_supervisor "$ACTIVE_LAUNCH_PID"; then
        terminate_verified_pid supervisor "$ACTIVE_LAUNCH_PID" || true
    fi
    stop_processes_locked >/dev/null 2>&1 || true
    if [ "$interrupted_during_write" -eq 0 ]; then
        emit_restart_result_locked failed interrupt "signal_${signal_name}" 130 - || true
    fi
    release_lifecycle_lock
    exit 130
}

do_restart() {
    local prior="stopped" stop_rc start_rc new_supervisor_pid="-"

    ensure_log_dir || return 43
    state_targets_are_safe || return 43
    acquire_lifecycle_lock || return 43
    preflight_start_contract || {
        manager_log_line "SHIM_RESTART_BEGIN status=begin prior=unknown old_supervisor_pid=- old_shim_pid=- port=${SHIM_PORT}" || true
        emit_restart_result_locked failed launch launch_preflight_failed 41 - || true
        release_lifecycle_lock
        return 41
    }

    RESTART_PHASE="inspect"
    RESTART_RESULT_WRITE_IN_PROGRESS=0
    RESTART_RESULT_WRITTEN=0
    RESTART_OLD_SUPERVISOR_PID="$(read_pid_file "$SUP_PID_FILE")" || \
        RESTART_OLD_SUPERVISOR_PID="-"
    RESTART_OLD_SHIM_PID="$(read_pid_file "$PID_FILE")" || RESTART_OLD_SHIM_PID="-"

    if is_healthy; then
        prior="running_ready"
    elif supervisor_running; then
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

    trap 'handle_restart_interrupt INT' INT
    trap 'handle_restart_interrupt TERM' TERM
    trap 'handle_restart_interrupt HUP' HUP

    # A healthy endpoint without manager-owned process identity must never be
    # signalled or mistaken for a generation this manager may replace.
    if [ "$prior" = "running_ready" ] && \
        [ "$RESTART_OLD_SUPERVISOR_PID" = "-" ] && \
        [ "$RESTART_OLD_SHIM_PID" = "-" ]; then
        emit_restart_result_locked failed stop unmanaged_ready_service 40 - || true
        release_lifecycle_lock
        return 40
    fi

    RESTART_PHASE="stop"
    stop_processes_locked
    stop_rc=$?
    case "$stop_rc" in
        0|3)
            ;;
        *)
            emit_restart_result_locked failed stop termination_failed 40 - || true
            release_lifecycle_lock
            return 40
            ;;
    esac

    RESTART_PHASE="launch"
    do_start_locked restart
    start_rc=$?
    if [ "$start_rc" -ne 0 ]; then
        stop_processes_locked >/dev/null 2>&1 || true
        if [ "$START_FAILURE_KIND" = "launch" ]; then
            emit_restart_result_locked failed launch launch_failed 41 - || true
            release_lifecycle_lock
            return 41
        fi
        emit_restart_result_locked failed readiness strict_readiness_failed 42 - || true
        release_lifecycle_lock
        return 42
    fi

    RESTART_PHASE="verify"
    if ! probe_health; then
        emit_readiness_failure
        stop_processes_locked >/dev/null 2>&1 || true
        emit_restart_result_locked failed readiness strict_readiness_failed 42 - || true
        release_lifecycle_lock
        return 42
    fi

    new_supervisor_pid="$(read_pid_file "$SUP_PID_FILE")" || new_supervisor_pid="-"
    if [ "$new_supervisor_pid" = "-" ] || ! pid_is_supervisor "$new_supervisor_pid" || \
        { [ "$RESTART_OLD_SUPERVISOR_PID" != "-" ] && \
          [ "$new_supervisor_pid" = "$RESTART_OLD_SUPERVISOR_PID" ]; }; then
        stop_processes_locked >/dev/null 2>&1 || true
        emit_restart_result_locked failed readiness supervisor_identity_invalid 42 \
            "$new_supervisor_pid" || true
        release_lifecycle_lock
        return 42
    fi

    RESTART_PHASE="ready"
    if ! emit_restart_result_locked ready readiness ready 0 "$new_supervisor_pid"; then
        release_lifecycle_lock
        return 43
    fi
    release_lifecycle_lock
    printf 'Shim restarted and strictly ready on port %s.\n' "$SHIM_PORT" >&2
    return 0
}

do_status() {
    if ! command -v curl >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then
        printf 'STATUS: unavailable (curl and jq are required for strict readiness)\n'
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
    if supervisor_running; then
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
    local requested="${DAAF_PROVIDER_SHIM:-}" observed
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
        printf 'SHIM_AUTO_FAILURE status=failed reason=unsafe_log_directory\n' >&2
        exit 0
    }
    if ! do_start auto; then
        manager_log_line "SHIM_AUTO_FAILURE status=failed reason=start_or_readiness_check continuing_boot=y" || \
            printf 'SHIM_AUTO_FAILURE status=failed reason=manager_log_write continuing_boot=y\n' >&2
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
        run_supervisor
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
