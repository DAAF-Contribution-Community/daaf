#!/usr/bin/env bash
# =============================================================================
# start_shim.sh — idempotent lifecycle manager for the Anthropic->OpenAI shim.
#
# The shim (anthropic_openai_shim.py) translates Anthropic Messages API calls
# from Claude Code into OpenAI Responses API calls (POST /v1/responses) to a
# configured backend.
# This script starts it, stops it, reports status, and — under --auto — silently
# no-ops unless the user has opted in via DAAF_PROVIDER_SHIM=openai.
#
# Modes:
#   --auto     Silent no-op unless DAAF_PROVIDER_SHIM=openai. If opted in,
#              start-if-not-running with a keepalive supervisor. Boot-safe:
#              never fatal, never blocks (used by the container entrypoint).
#   --start    Start the shim (with keepalive supervisor) if not already running.
#   --stop     Stop the shim and its supervisor.
#   --status   Print running/stopped + health JSON.
#
# Config (env, all optional — defaults mirror the shim's own):
#   DAAF_PROVIDER_SHIM      activation switch; must equal "openai" to auto-start
#   SHIM_PORT               default 4141
#   SHIM_BACKEND_BASE_URL   default https://api.openai.com/v1
#   SHIM_BACKEND_API_KEY    default: value of OPENAI_API_KEY
#   SHIM_STRIP_MODEL_PREFIX default ""
#   SHIM_SANITIZE_TOOLS     default "1" (enabled); strips known GPT tool-call
#                           quirks — set to 0 (and restart the shim) for
#                           DAAFBench runs of shim-routed models
#   SHIM_REASONING_EFFORT   tier 3 of the v1.2.3 effort precedence chain
#                           (per-request signal > "#<effort>" slug suffix > this
#                           env var > default "high"); sets reasoning.effort only
#                           when no per-request signal or slug suffix is present.
#                           An inbound per-request "high" is treated as unset
#                           since v1.2.3 (the client pins it for GPT slugs).
#                           Valid: none|low|medium|high|xhigh|max ("max" is
#                           gpt-5.6-only). Unset -> default "high" (the shim
#                           always sends an effort since v1.2.2)
#   SHIM_TEXT_VERBOSITY     response verbosity (v1.2.4+); the outbound request
#                           always carries text.verbosity. Valid low|medium|high;
#                           default "high" (warmth/volume, parity with DAAF's
#                           posture). Read once at startup like the flags above.
#
# Keepalive: a background supervisor restarts the shim if it exits, with a short
# sleep between restarts. A restart-storm guard stops after 10 crashes in 60s
# and logs loudly, so a misconfigured shim can't spin forever.
#
# Logging: the shim's stderr and the supervisor's own messages are appended to
#   logs/shim.log. The log dir is created on demand and is gitignored.
# =============================================================================

set -uo pipefail
# Deliberately omit -e: several paths (health probe, stale-pid cleanup) inspect
# failures and decide what to do rather than aborting. This is a lifecycle
# manager, not a safety hook — it must degrade gracefully, especially under
# --auto where it runs at container boot.

# --- Config ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SCRIPT_DIR
readonly SHIM_PY="${SCRIPT_DIR}/anthropic_openai_shim.py"
readonly LOG_DIR="${SCRIPT_DIR}/logs"
readonly LOG_FILE="${LOG_DIR}/shim.log"
readonly PID_FILE="${LOG_DIR}/shim.pid"
readonly SUP_PID_FILE="${LOG_DIR}/supervisor.pid"
# Records the supervisor's process-group id so --stop can reap the supervisor
# AND its shim child atomically (they share a session/group via setsid). A plain
# per-pid kill races the supervisor's restart loop, which can respawn a child in
# the kill window and orphan it — observed during live validation.
readonly PGID_FILE="${LOG_DIR}/pgid"
# Sentinel written by --stop, polled by the supervisor loop, so a stop can never
# race a restart.
readonly STOP_FILE="${LOG_DIR}/stop.requested"

SHIM_PORT="${SHIM_PORT:-4141}"
readonly HEALTH_URL="http://127.0.0.1:${SHIM_PORT}/health"

# Restart-storm guard.
readonly STORM_LIMIT=10      # crashes...
readonly STORM_WINDOW=60     # ...within this many seconds -> give up

# --- Helpers ---
log_line() {
    # Timestamped supervisor/manager line -> log file and stderr.
    printf '%s SUPERVISOR %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE" >&2
}

ensure_log_dir() {
    mkdir -p "$LOG_DIR" 2>/dev/null || true
}

health_json() {
    # Print the health JSON to stdout, or nothing. Returns 0 iff healthy.
    local out
    out="$(curl -fsS --max-time 2 "$HEALTH_URL" 2>/dev/null)" || return 1
    printf '%s' "$out"
    return 0
}

is_healthy() {
    curl -fsS --max-time 2 "$HEALTH_URL" >/dev/null 2>&1
}

supervisor_running() {
    # 0 iff a live supervisor process is recorded and still alive.
    [ -f "$SUP_PID_FILE" ] || return 1
    local sp
    sp="$(cat "$SUP_PID_FILE" 2>/dev/null || true)"
    [ -n "$sp" ] || return 1
    kill -0 "$sp" 2>/dev/null
}

# --- Keepalive supervisor -----------------------------------------------------
# Runs in the background (invoked as: this_script __supervise). Loops: launch
# the shim, wait for it, restart on exit, honoring the storm guard. Writes the
# shim's PID to PID_FILE each cycle and its own PID to SUP_PID_FILE.
run_supervisor() {
    ensure_log_dir
    echo "$$" > "$SUP_PID_FILE"
    # Record our process-group id. When launched via `setsid` the supervisor is a
    # group leader, so its PGID == its PID and the shim child inherits the group.
    # --stop signals the whole group by this id.
    local pgid
    pgid="$(ps -o pgid= -p "$$" 2>/dev/null | tr -d ' ')"
    [ -n "$pgid" ] && echo "$pgid" > "$PGID_FILE"

    # A stop sentinel lets --stop tell the supervisor to quit WITHOUT racing the
    # restart loop: the loop checks for it before every (re)launch and sleep tick.
    rm -f "$STOP_FILE" 2>/dev/null || true

    # Clean up the shim child on supervisor termination.
    local child_pid=""
    cleanup_sup() {
        if [ -n "$child_pid" ]; then
            kill "$child_pid" 2>/dev/null || true
        fi
        rm -f "$PID_FILE" "$SUP_PID_FILE" "$PGID_FILE" 2>/dev/null || true
        log_line "supervisor exiting"
    }
    trap cleanup_sup EXIT INT TERM

    local window_start crashes
    window_start="$(date +%s)"
    crashes=0

    log_line "starting shim on port ${SHIM_PORT} (backend from env; keepalive on)"
    while true; do
        # Honor a stop request that arrived before (re)launch.
        if [ -f "$STOP_FILE" ]; then
            log_line "stop requested; supervisor loop ending"
            exit 0
        fi
        # Launch the shim; its stderr (structured logs) appends to the log file.
        python3 "$SHIM_PY" >>"$LOG_FILE" 2>&1 &
        child_pid=$!
        echo "$child_pid" > "$PID_FILE"
        wait "$child_pid"
        local rc=$?
        child_pid=""

        # If a stop was requested while the shim ran, do not restart.
        if [ -f "$STOP_FILE" ]; then
            log_line "stop requested; not restarting shim"
            exit 0
        fi

        # Storm guard: count crashes within a rolling window.
        local now
        now="$(date +%s)"
        if [ $((now - window_start)) -gt "$STORM_WINDOW" ]; then
            window_start="$now"
            crashes=0
        fi
        crashes=$((crashes + 1))
        log_line "shim exited rc=${rc} (crash ${crashes}/${STORM_LIMIT} in ${STORM_WINDOW}s window)"
        if [ "$crashes" -ge "$STORM_LIMIT" ]; then
            log_line "RESTART STORM: ${STORM_LIMIT} crashes in ${STORM_WINDOW}s — giving up. Check config (SHIM_BACKEND_API_KEY, SHIM_PORT) and ${LOG_FILE}."
            exit 1
        fi
        sleep 2
    done
}

# --- Public actions -----------------------------------------------------------
do_start() {
    ensure_log_dir

    if [ ! -f "$SHIM_PY" ]; then
        echo "ERROR: shim not found at ${SHIM_PY}" >&2
        echo "  Fix: ensure the provider_shim directory is intact." >&2
        return 1
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        echo "ERROR: python3 not found on PATH; cannot start shim." >&2
        return 1
    fi

    # Idempotency: already healthy? Nothing to do.
    if is_healthy; then
        echo "Shim already running and healthy on port ${SHIM_PORT}." >&2
        return 0
    fi
    # Supervisor alive but not yet healthy (still booting)? Leave it.
    if supervisor_running; then
        echo "Shim supervisor already running (pid $(cat "$SUP_PID_FILE" 2>/dev/null))." >&2
        return 0
    fi

    # Clean any stale pidfiles/sentinel from a prior crash or stop.
    rm -f "$PID_FILE" "$SUP_PID_FILE" "$PGID_FILE" "$STOP_FILE" 2>/dev/null || true

    # Launch the supervisor in its OWN session/process-group via setsid, fully
    # detached so it survives this shell returning. Being a group leader lets
    # --stop reap the supervisor and its shim child together by process group,
    # which is what closes the orphan-child race a plain per-pid kill leaves open.
    if command -v setsid >/dev/null 2>&1; then
        setsid "${BASH_SOURCE[0]}" __supervise >>"$LOG_FILE" 2>&1 &
    else
        # Fallback: nohup + disown. --stop still works via the recorded PGID,
        # which the supervisor derives from its own `ps` lookup either way.
        nohup "${BASH_SOURCE[0]}" __supervise >>"$LOG_FILE" 2>&1 &
    fi
    disown 2>/dev/null || true

    # Wait (bounded) for health.
    local waited=0
    while [ "$waited" -lt 15 ]; do
        if is_healthy; then
            echo "Shim started and healthy on port ${SHIM_PORT}." >&2
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done
    echo "WARNING: shim did not report healthy within 15s. Check ${LOG_FILE}." >&2
    return 1
}

do_stop() {
    local stopped=0

    # 1. Raise the stop sentinel FIRST so the supervisor's restart loop will not
    #    respawn a child while we tear things down (closes the observed race).
    ensure_log_dir
    : > "$STOP_FILE" 2>/dev/null || true

    # 2. Signal the whole process group if we recorded one. `kill -- -PGID`
    #    delivers to every member (supervisor + shim child + any sleep), so the
    #    child cannot outlive the supervisor.
    local pgid
    pgid="$(cat "$PGID_FILE" 2>/dev/null || true)"
    if [ -n "$pgid" ] && kill -0 "-${pgid}" 2>/dev/null; then
        kill -TERM "-${pgid}" 2>/dev/null || true
        stopped=1
        # Give the group a moment to exit, then escalate if anything survives.
        local waited=0
        while [ "$waited" -lt 5 ]; do
            if ! kill -0 "-${pgid}" 2>/dev/null; then
                break
            fi
            sleep 1
            waited=$((waited + 1))
        done
        if kill -0 "-${pgid}" 2>/dev/null; then
            kill -KILL "-${pgid}" 2>/dev/null || true
        fi
    fi

    # 3. Fallback / belt-and-suspenders: also target the recorded individual pids
    #    in case the PGID file is missing (e.g. setsid unavailable at start).
    local sp pp
    sp="$(cat "$SUP_PID_FILE" 2>/dev/null || true)"
    if [ -n "$sp" ] && kill -0 "$sp" 2>/dev/null; then
        kill -TERM "$sp" 2>/dev/null || true
        stopped=1
    fi
    pp="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "$pp" ] && kill -0 "$pp" 2>/dev/null; then
        kill -TERM "$pp" 2>/dev/null || true
        stopped=1
    fi

    rm -f "$PID_FILE" "$SUP_PID_FILE" "$PGID_FILE" "$STOP_FILE" 2>/dev/null || true

    if [ "$stopped" -eq 1 ]; then
        echo "Shim stopped." >&2
    else
        echo "Shim was not running." >&2
    fi
    return 0
}

do_status() {
    if is_healthy; then
        echo "STATUS: running (port ${SHIM_PORT})"
        echo "HEALTH: $(health_json)"
        return 0
    fi
    if supervisor_running; then
        echo "STATUS: supervisor up but shim not yet healthy (port ${SHIM_PORT})"
        return 0
    fi
    echo "STATUS: stopped"
    return 0
}

do_auto() {
    # Silent no-op unless the user opted in. This is the container-boot path, so
    # it must never be noisy or fatal.
    if [ "${DAAF_PROVIDER_SHIM:-}" != "openai" ]; then
        # Not opted in — exit silently, success.
        exit 0
    fi
    ensure_log_dir
    log_line "--auto: DAAF_PROVIDER_SHIM=openai detected; ensuring shim is running."
    # start-if-not-running; swallow failures so boot always proceeds.
    do_start || log_line "--auto: do_start reported non-zero; continuing boot anyway."
    exit 0
}

# --- Dispatch ---
ACTION="${1:-}"
case "$ACTION" in
    __supervise)
        run_supervisor
        ;;
    --auto)
        do_auto
        ;;
    --start)
        do_start
        ;;
    --stop)
        do_stop
        ;;
    --status)
        do_status
        ;;
    *)
        echo "Usage: $(basename "${BASH_SOURCE[0]}") {--auto|--start|--stop|--status}" >&2
        exit 1
        ;;
esac
