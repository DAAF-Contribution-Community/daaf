#!/usr/bin/env bats
# =============================================================================
# Deterministic lifecycle tests for scripts/provider_shim/start_shim.sh.
#
# Every test stages the manager and a fabricated loopback-only shim under
# BATS_TEST_TMPDIR. The production process, source, state files, and shim.log are
# never touched. teardown stops only the staged manager's identity-verified pids,
# removes any symlink fixture, and deletes the isolated directory.
# =============================================================================

load 'test_helper'

START_SHIM_SH="${START_SHIM_SH:-${REPO_ROOT}/scripts/provider_shim/start_shim.sh}"

setup() {
    SHIM_TEST_ROOT="${BATS_TEST_TMPDIR}/provider_shim"
    mkdir -p "$SHIM_TEST_ROOT"
    cp "$START_SHIM_SH" "${SHIM_TEST_ROOT}/start_shim.sh"
    chmod 0755 "${SHIM_TEST_ROOT}/start_shim.sh"
    MANAGER="${SHIM_TEST_ROOT}/start_shim.sh"
    LOG_DIR="${SHIM_TEST_ROOT}/logs"
    LOG_FILE="${LOG_DIR}/shim.log"

    cat > "${SHIM_TEST_ROOT}/anthropic_openai_shim.py" <<'PY'
#!/usr/bin/env python3
SHIM_VERSION = "1.2.12"

import json
import os
import signal
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

behavior = os.environ.get("FAKE_SHIM_BEHAVIOR", "serve")
if behavior == "crash":
    raise SystemExit(int(os.environ.get("FAKE_SHIM_CRASH_CODE", "42")))
time.sleep(float(os.environ.get("FAKE_SHIM_START_DELAY", "0")))

stopping = False


def stop_server(_signum, _frame):
    global stopping
    stopping = True


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return
        raw = os.environ.get("FAKE_HEALTH_RAW")
        if raw is None:
            mode = os.environ.get("FAKE_HEALTH_BACKEND_MODE", os.environ.get("SHIM_BACKEND_MODE", "openai"))
            payload = {
                "service": os.environ.get("FAKE_HEALTH_SERVICE", "daaf-anthropic-openai-shim"),
                "status": os.environ.get("FAKE_HEALTH_STATUS", "ok"),
                "version": os.environ.get("FAKE_HEALTH_VERSION", SHIM_VERSION),
                "backend_mode": mode,
                "backend": "https://example.invalid/v1",
                "codex_home_present": True,
                "sanitize_tools": True,
                "reasoning_effort": None,
                "text_verbosity": "high",
            }
            raw = json.dumps(payload)
        body = raw.encode("utf-8")
        self.send_response(int(os.environ.get("FAKE_HEALTH_HTTP_STATUS", "200")))
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_args):
        return


signal.signal(signal.SIGTERM, stop_server)
signal.signal(signal.SIGINT, stop_server)
server = HTTPServer(("127.0.0.1", int(os.environ.get("SHIM_PORT", "4141"))), Handler)
server.timeout = 0.05
while not stopping:
    server.handle_request()
server.server_close()
PY
    chmod 0755 "${SHIM_TEST_ROOT}/anthropic_openai_shim.py"

    SHIM_PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"
    export SHIM_PORT
    export DAAF_SHIM_TEST_MODE=1
    export DAAF_SHIM_TEST_READINESS_WAIT=5
    export DAAF_SHIM_TEST_RESTART_DELAY=0.2
    export DAAF_SHIM_TEST_STORM_LIMIT=4
    export DAAF_SHIM_TEST_STORM_WINDOW=60
    export START_SHIM_SH MANAGER LOG_DIR LOG_FILE
    unset FAKE_SHIM_BEHAVIOR FAKE_SHIM_CRASH_CODE FAKE_SHIM_START_DELAY FAKE_HEALTH_RAW
    unset FAKE_HEALTH_SERVICE FAKE_HEALTH_STATUS FAKE_HEALTH_VERSION
    unset FAKE_HEALTH_BACKEND_MODE FAKE_HEALTH_HTTP_STATUS DAAF_SHIM_TEST_NO_SETSID
    unset DAAF_SHIM_TEST_STOP_FAILURE DAAF_SHIM_TEST_RESULT_APPEND_FAILURE
    unset DAAF_SHIM_TEST_SIGNAL_RESULT_IN_PROGRESS SHIM_BACKEND_MODE
}

teardown() {
    unset DAAF_SHIM_TEST_STOP_FAILURE DAAF_SHIM_TEST_RESULT_APPEND_FAILURE
    unset DAAF_SHIM_TEST_SIGNAL_RESULT_IN_PROGRESS
    if [ -x "${MANAGER:-}" ]; then
        "$MANAGER" --stop >/dev/null 2>&1 || true
    fi
    if [ -n "${EXTERNAL_SERVER_PID:-}" ]; then
        kill "$EXTERNAL_SERVER_PID" 2>/dev/null || true
        wait "$EXTERNAL_SERVER_PID" 2>/dev/null || true
    fi
    if [ -n "${VICTIM_PID:-}" ]; then
        kill "$VICTIM_PID" 2>/dev/null || true
        wait "$VICTIM_PID" 2>/dev/null || true
    fi
    if [ -n "${DIRECT_SUPERVISOR_PID:-}" ]; then
        kill "$DIRECT_SUPERVISOR_PID" 2>/dev/null || true
        wait "$DIRECT_SUPERVISOR_PID" 2>/dev/null || true
    fi
    find "${SHIM_TEST_ROOT:-${BATS_TEST_TMPDIR}}" -type l -delete 2>/dev/null || true
    rm -rf "${SHIM_TEST_ROOT:-${BATS_TEST_TMPDIR}/provider_shim}"
}

wait_for_file() {
    local path="$1" attempts=0
    while [ "$attempts" -lt 100 ]; do
        [ -s "$path" ] && return 0
        sleep 0.05
        attempts=$((attempts + 1))
    done
    return 1
}

wait_for_log_text() {
    local text="$1" attempts=0
    while [ "$attempts" -lt 100 ]; do
        if [ -f "$LOG_FILE" ] && grep -F "$text" "$LOG_FILE" >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.05
        attempts=$((attempts + 1))
    done
    return 1
}

wait_for_dead() {
    local pid="$1" attempts=0
    while [ "$attempts" -lt 100 ]; do
        kill -0 "$pid" 2>/dev/null || return 0
        sleep 0.05
        attempts=$((attempts + 1))
    done
    return 1
}

wait_for_ready() {
    local attempts=0
    while [ "$attempts" -lt 100 ]; do
        if curl -fsS --max-time 1 "http://127.0.0.1:${SHIM_PORT}/health" 2>/dev/null | \
            jq -e '.service == "daaf-anthropic-openai-shim" and .status == "ok"' \
                >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.05
        attempts=$((attempts + 1))
    done
    return 1
}

count_exact_arg_processes() {
    local expected="$1" path arg found count=0
    for path in /proc/[0-9]*/cmdline; do
        [ -r "$path" ] || continue
        found=0
        while IFS= read -r -d '' arg; do
            if [ "$arg" = "$expected" ]; then
                found=1
                break
            fi
        done < "$path"
        [ "$found" -eq 0 ] || count=$((count + 1))
    done
    printf '%s\n' "$count"
}

assert_manager_success() {
    if [ "$status" -ne 0 ] && [ -f "$LOG_FILE" ]; then
        printf '%s\n' '--- isolated lifecycle log ---' >&3
        while IFS= read -r line; do
            printf '%s\n' "$line" >&3
        done < "$LOG_FILE"
    fi
    assert_success
}

start_external_fixture() {
    python3 "${SHIM_TEST_ROOT}/anthropic_openai_shim.py" >/dev/null 2>&1 &
    EXTERNAL_SERVER_PID=$!
    export EXTERNAL_SERVER_PID
    local attempts=0 http_status
    while [ "$attempts" -lt 100 ]; do
        http_status="$(curl -sS --max-time 1 --output /dev/null --write-out '%{http_code}' \
            "http://127.0.0.1:${SHIM_PORT}/health" 2>/dev/null)" || http_status="000"
        case "$http_status" in
            [0-9][0-9][0-9]) [ "$http_status" = "000" ] || return 0 ;;
        esac
        sleep 0.05
        attempts=$((attempts + 1))
    done
    return 1
}

# --- Syntax and deterministic rotation --------------------------------------

@test "start_shim.sh parses without errors" {
    run bash -n "$MANAGER"
    assert_success
}

@test "usage and help recognize restart as a public action" {
    run "$MANAGER" --help
    assert_success
    assert_output --partial "--restart"
    run "$MANAGER" --unknown
    assert_failure
    assert_output --partial "--restart"
}

@test "missing log is created private without rotation" {
    run "$MANAGER" __rotate_logs
    assert_success
    [ -f "$LOG_FILE" ]
    [ "$(stat -c '%a' "$LOG_FILE")" = "600" ]
    [ ! -e "${LOG_FILE}.1" ]
}

@test "existing log at exact 25 MiB boundary does not rotate" {
    mkdir -p "$LOG_DIR"
    truncate -s 26214400 "$LOG_FILE"
    run "$MANAGER" __rotate_logs
    assert_success
    [ "$(wc -c < "$LOG_FILE")" -eq 26214400 ]
    [ ! -e "${LOG_FILE}.1" ]
    [ "$(stat -c '%a' "$LOG_FILE")" = "600" ]
}

@test "log one byte over boundary rotates before creating private replacement" {
    mkdir -p "$LOG_DIR"
    truncate -s 26214401 "$LOG_FILE"
    chmod 0644 "$LOG_FILE"
    run "$MANAGER" __rotate_logs
    assert_success
    [ "$(wc -c < "$LOG_FILE")" -eq 0 ]
    [ "$(wc -c < "${LOG_FILE}.1")" -eq 26214401 ]
    [ "$(stat -c '%a' "$LOG_FILE")" = "600" ]
    [ "$(stat -c '%a' "${LOG_FILE}.1")" = "600" ]
}

@test "over-boundary start rotates before preserving the supervisor first record" {
    mkdir -p "$LOG_DIR"
    truncate -s 26214401 "$LOG_FILE"
    run "$MANAGER" --start
    assert_manager_success
    grep -F "SUPERVISOR starting shim" "$LOG_FILE"
    [ "$(wc -c < "${LOG_FILE}.1")" -eq 26214401 ]
    run "$MANAGER" --stop
    assert_success
}

@test "rotation retains exactly five descending generations" {
    mkdir -p "$LOG_DIR"
    truncate -s 26214401 "$LOG_FILE"
    printf 'old-1\n' > "${LOG_FILE}.1"
    printf 'old-2\n' > "${LOG_FILE}.2"
    printf 'old-3\n' > "${LOG_FILE}.3"
    printf 'old-4\n' > "${LOG_FILE}.4"
    printf 'old-5-discard\n' > "${LOG_FILE}.5"
    run "$MANAGER" __rotate_logs
    assert_success
    grep -Fx 'old-1' "${LOG_FILE}.2"
    grep -Fx 'old-2' "${LOG_FILE}.3"
    grep -Fx 'old-3' "${LOG_FILE}.4"
    grep -Fx 'old-4' "${LOG_FILE}.5"
    ! grep -R -F 'old-5-discard' "$LOG_DIR" >/dev/null 2>&1
    [ ! -e "${LOG_FILE}.6" ]
}

@test "unsafe symlink log target is rejected without touching its referent" {
    mkdir -p "$LOG_DIR"
    local referent="${SHIM_TEST_ROOT}/outside.log"
    printf 'referent-unchanged\n' > "$referent"
    ln -s "$referent" "$LOG_FILE"
    run "$MANAGER" __rotate_logs
    assert_failure
    assert_output --partial "refusing unsafe shim state target"
    grep -Fx 'referent-unchanged' "$referent"
    [ -L "$LOG_FILE" ]
}

@test "unsafe symlink generation is rejected before current log mutation" {
    mkdir -p "$LOG_DIR"
    truncate -s 26214401 "$LOG_FILE"
    local referent="${SHIM_TEST_ROOT}/generation-referent.log"
    printf 'generation-referent\n' > "$referent"
    ln -s "$referent" "${LOG_FILE}.3"
    run "$MANAGER" __rotate_logs
    assert_failure
    [ "$(wc -c < "$LOG_FILE")" -eq 26214401 ]
    grep -Fx 'generation-referent' "$referent"
}

# --- Strict readiness -------------------------------------------------------

@test "cleanly stopped status exits zero without launching a process" {
    run "$MANAGER" --status
    assert_success
    assert_output "STATUS: stopped"
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    [ "$(count_exact_arg_processes "$MANAGER")" -eq 0 ]
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
    [ ! -e "${LOG_DIR}/shim.pid" ]
}

@test "strict readiness accepts exact identity version normalized mode and status" {
    export SHIM_BACKEND_MODE=' ChatGPT '
    export FAKE_HEALTH_BACKEND_MODE=chatgpt
    run "$MANAGER" --start
    assert_manager_success
    assert_output --partial "strictly ready"
    run "$MANAGER" --status
    assert_success
    assert_output --partial '"service": "daaf-anthropic-openai-shim"'
    assert_output --partial '"version": "1.2.12"'
    assert_output --partial '"backend_mode": "chatgpt"'
}

@test "non-200 health response is reachable unexpected and blocks manager launch" {
    export FAKE_HEALTH_HTTP_STATUS=404
    start_external_fixture

    run "$MANAGER" --start

    assert_failure
    assert_output --partial "port ${SHIM_PORT} answered /health"
    assert_output --partial "reason=http_status_404"
    refute_output --partial "reason=unreachable"
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 1 ]
    [ "$(count_exact_arg_processes "$MANAGER")" -eq 0 ]
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
    [ ! -e "${LOG_DIR}/shim.pid" ]
}

@test "malformed JSON wrong identity wrong version and wrong mode are rejected" {
    local name
    for name in malformed identity version mode; do
        unset FAKE_HEALTH_RAW FAKE_HEALTH_SERVICE FAKE_HEALTH_VERSION FAKE_HEALTH_BACKEND_MODE
        case "$name" in
            malformed) export FAKE_HEALTH_RAW='{not-json' ;;
            identity) export FAKE_HEALTH_SERVICE='unrelated-service' ;;
            version) export FAKE_HEALTH_VERSION='1.2.11' ;;
            mode) export FAKE_HEALTH_BACKEND_MODE='chatgpt' ;;
        esac
        start_external_fixture
        run "$MANAGER" --start
        assert_failure
        assert_output --partial "SHIM_READINESS_FAILURE status=failed"
        case "$name" in
            malformed) assert_output --partial "reason=malformed_json" ;;
            identity) assert_output --partial "reason=wrong_identity_or_status" ;;
            version) assert_output --partial "reason=version_mismatch" ;;
            mode) assert_output --partial "reason=backend_mode_mismatch" ;;
        esac
        kill "$EXTERNAL_SERVER_PID" 2>/dev/null || true
        wait "$EXTERNAL_SERVER_PID" 2>/dev/null || true
        EXTERNAL_SERVER_PID=""
    done
}

@test "auto remains boot-nonfatal but emits machine-readable readiness failure" {
    export DAAF_PROVIDER_SHIM=openai
    export FAKE_HEALTH_SERVICE=unrelated-service
    start_external_fixture
    run "$MANAGER" --auto
    assert_success
    assert_output --partial "SHIM_READINESS_FAILURE status=failed"
    assert_output --partial "SHIM_AUTO_FAILURE status=failed"
    [ "$(grep -c 'MANAGER SHIM_AUTO_FAILURE status=failed' "$LOG_FILE")" -eq 1 ]
}

@test "auto remains nonblocking while a restart owns the lifecycle lock" {
    run "$MANAGER" --start
    assert_manager_success
    export DAAF_PROVIDER_SHIM=openai
    export FAKE_SHIM_START_DELAY=5
    export DAAF_SHIM_TEST_READINESS_WAIT=10
    local restart_pid before after

    "$MANAGER" --restart > "${SHIM_TEST_ROOT}/restart-for-auto.out" 2>&1 &
    restart_pid=$!
    wait_for_log_text "MANAGER SHIM_RESTART_BEGIN status=begin"
    before="$(date +%s)"
    run "$MANAGER" --auto
    after="$(date +%s)"

    assert_success
    assert_output --partial "SHIM_AUTO_FAILURE status=failed"
    [ $((after - before)) -lt 3 ]
    wait "$restart_pid"
    wait_for_ready
}

# --- Process identity, idempotency, restart, and stop -----------------------

@test "restart replaces a running-ready generation and passes strict readiness" {
    run "$MANAGER" --start
    assert_manager_success
    local old_sp old_pp new_sp new_pp
    old_sp="$(< "${LOG_DIR}/supervisor.pid")"
    old_pp="$(< "${LOG_DIR}/shim.pid")"

    run "$MANAGER" --restart
    assert_manager_success
    assert_output --partial "SHIM_RESTART_BEGIN status=begin prior=running_ready"
    assert_output --partial "SHIM_RESTART_RESULT status=ready stage=readiness reason=ready exit_code=0"
    assert_output --partial "Shim restarted and strictly ready"
    new_sp="$(< "${LOG_DIR}/supervisor.pid")"
    new_pp="$(< "${LOG_DIR}/shim.pid")"
    [ "$old_sp" != "$new_sp" ]
    [ "$old_pp" != "$new_pp" ]
    wait_for_dead "$old_sp"
    wait_for_dead "$old_pp"
    wait_for_ready
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 1 ]
}

@test "restart starts a stopped daemon and passes strict readiness" {
    run "$MANAGER" --restart
    assert_manager_success
    assert_output --partial "SHIM_RESTART_BEGIN status=begin prior=stopped"
    assert_output --partial "SHIM_RESTART_RESULT status=ready"
    wait_for_ready
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 1 ]
}

@test "restart recovers stale state without signaling an unrelated process" {
    mkdir -p "$LOG_DIR"
    sleep 30 &
    VICTIM_PID=$!
    export VICTIM_PID
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/shim.pid"
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/supervisor.pid"
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/pgid"

    run "$MANAGER" --restart
    assert_manager_success
    kill -0 "$VICTIM_PID"
    wait_for_ready
    [ "$(< "${LOG_DIR}/supervisor.pid")" != "$VICTIM_PID" ]
    [ "$(< "${LOG_DIR}/shim.pid")" != "$VICTIM_PID" ]
}

@test "restart stop failure is explicit and never emits false readiness" {
    run "$MANAGER" --start
    assert_manager_success
    local old_sp old_pp
    old_sp="$(< "${LOG_DIR}/supervisor.pid")"
    old_pp="$(< "${LOG_DIR}/shim.pid")"
    export DAAF_SHIM_TEST_STOP_FAILURE=1

    run "$MANAGER" --restart
    [ "$status" -eq 40 ]
    assert_output --partial "SHIM_RESTART_RESULT status=failed stage=stop reason=termination_failed exit_code=40"
    refute_output --partial "SHIM_RESTART_RESULT status=ready"
    kill -0 "$old_sp"
    kill -0 "$old_pp"
    [ "$(grep -c 'MANAGER SHIM_RESTART_BEGIN status=begin' "$LOG_FILE")" -eq 1 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=failed stage=stop' "$LOG_FILE")" -eq 1 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=ready' "$LOG_FILE" || true)" -eq 0 ]
}

@test "restart launch failure after stop is explicit and leaves no orphan" {
    run "$MANAGER" --start
    assert_manager_success
    local old_sp old_pp
    old_sp="$(< "${LOG_DIR}/supervisor.pid")"
    old_pp="$(< "${LOG_DIR}/shim.pid")"
    export FAKE_SHIM_BEHAVIOR=crash
    export DAAF_SHIM_TEST_STORM_LIMIT=2
    export DAAF_SHIM_TEST_RESTART_DELAY=0.05
    export DAAF_SHIM_TEST_READINESS_WAIT=3

    run "$MANAGER" --restart
    [ "$status" -eq 41 ]
    assert_output --partial "SHIM_RESTART_RESULT status=failed stage=launch reason=launch_failed exit_code=41"
    refute_output --partial "SHIM_RESTART_RESULT status=ready"
    wait_for_dead "$old_sp"
    wait_for_dead "$old_pp"
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    [ "$(count_exact_arg_processes "$MANAGER")" -eq 0 ]
    [ ! -s "${LOG_DIR}/supervisor.pid" ]
    [ ! -s "${LOG_DIR}/shim.pid" ]
}

@test "restart readiness failure after stop is explicit and leaves no orphan" {
    run "$MANAGER" --start
    assert_manager_success
    export FAKE_HEALTH_STATUS=starting
    export DAAF_SHIM_TEST_READINESS_WAIT=3

    run "$MANAGER" --restart
    [ "$status" -eq 42 ]
    assert_output --partial "SHIM_RESTART_RESULT status=failed stage=readiness reason=strict_readiness_failed exit_code=42"
    refute_output --partial "SHIM_RESTART_RESULT status=ready"
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    [ "$(count_exact_arg_processes "$MANAGER")" -eq 0 ]
    [ ! -s "${LOG_DIR}/supervisor.pid" ]
    [ ! -s "${LOG_DIR}/shim.pid" ]
}

@test "restart result append failure exits 43 without a false persisted record" {
    export DAAF_SHIM_TEST_RESULT_APPEND_FAILURE=1

    run "$MANAGER" --restart

    [ "$status" -eq 43 ]
    assert_output --partial "SHIM_RESTART_RESULT status=failed stage=record reason=manager_log_write exit_code=43"
    assert_output --partial "record_persisted=no"
    refute_output --partial "record_persisted=unknown"
    [ "$(grep -c 'MANAGER SHIM_RESTART_BEGIN status=begin' "$LOG_FILE")" -eq 1 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT' "$LOG_FILE" || true)" -eq 0 ]
}

@test "signal during restart result persistence exits 130 without deadlock or orphan" {
    export DAAF_SHIM_TEST_SIGNAL_RESULT_IN_PROGRESS=1

    run timeout 15 "$MANAGER" --restart

    [ "$status" -eq 130 ]
    assert_output --partial "SHIM_RESTART_RESULT status=failed stage=record reason=write_interrupted exit_code=130"
    assert_output --partial "record_persisted=unknown"
    refute_output --partial "record_persisted=no"
    [ "$(grep -c 'MANAGER SHIM_RESTART_BEGIN status=begin' "$LOG_FILE")" -eq 1 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT' "$LOG_FILE" || true)" -eq 0 ]
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    [ "$(count_exact_arg_processes "$MANAGER")" -eq 0 ]
    [ ! -s "${LOG_DIR}/supervisor.pid" ]
    [ ! -s "${LOG_DIR}/shim.pid" ]
}

@test "interrupted restart never emits success and leaves a truthful stopped state" {
    run "$MANAGER" --start
    assert_manager_success
    local old_sp old_pp restart_pid restart_rc=0
    old_sp="$(< "${LOG_DIR}/supervisor.pid")"
    old_pp="$(< "${LOG_DIR}/shim.pid")"
    export FAKE_SHIM_START_DELAY=10
    export DAAF_SHIM_TEST_READINESS_WAIT=20

    "$MANAGER" --restart > "${SHIM_TEST_ROOT}/restart-interrupt.out" 2>&1 &
    restart_pid=$!
    wait_for_log_text "MANAGER SHIM_RESTART_BEGIN status=begin"
    wait_for_dead "$old_sp"
    wait_for_dead "$old_pp"
    kill -TERM "$restart_pid"
    wait "$restart_pid" || restart_rc=$?

    [ "$restart_rc" -eq 130 ]
    grep -F "SHIM_RESTART_RESULT status=failed stage=interrupt reason=signal_TERM exit_code=130" \
        "${SHIM_TEST_ROOT}/restart-interrupt.out"
    ! grep -F "SHIM_RESTART_RESULT status=ready" "${SHIM_TEST_ROOT}/restart-interrupt.out"
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    [ ! -s "${LOG_DIR}/supervisor.pid" ]
    [ ! -s "${LOG_DIR}/shim.pid" ]
}

@test "restart records are exactly once and supervisor records are not duplicated" {
    run "$MANAGER" --start
    assert_manager_success
    run "$MANAGER" --restart
    assert_manager_success
    [ "$(grep -c 'MANAGER SHIM_RESTART_BEGIN status=begin' "$LOG_FILE")" -eq 1 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=ready' "$LOG_FILE")" -eq 1 ]
    [ "$(grep -c 'SUPERVISOR starting shim' "$LOG_FILE")" -eq 2 ]
    [ "$(grep -c 'SUPERVISOR supervisor exiting' "$LOG_FILE")" -eq 1 ]
}

@test "concurrent restart and start serialize without duplicate daemons" {
    run "$MANAGER" --start
    assert_manager_success
    export FAKE_SHIM_START_DELAY=0.5
    local restart_pid start_pid

    "$MANAGER" --restart > "${SHIM_TEST_ROOT}/restart.out" 2>&1 &
    restart_pid=$!
    wait_for_log_text "MANAGER SHIM_RESTART_BEGIN status=begin"
    "$MANAGER" --start > "${SHIM_TEST_ROOT}/start.out" 2>&1 &
    start_pid=$!
    wait "$restart_pid"
    wait "$start_pid"

    wait_for_ready
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 1 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=ready' "$LOG_FILE")" -eq 1 ]
    grep -F "Shim already running and strictly ready" "${SHIM_TEST_ROOT}/start.out"
}

@test "concurrent restarts serialize without duplicate daemons" {
    run "$MANAGER" --start
    assert_manager_success
    export FAKE_SHIM_START_DELAY=0.5
    local first_pid second_pid

    "$MANAGER" --restart > "${SHIM_TEST_ROOT}/restart-first.out" 2>&1 &
    first_pid=$!
    wait_for_log_text "MANAGER SHIM_RESTART_BEGIN status=begin"
    "$MANAGER" --restart > "${SHIM_TEST_ROOT}/restart-second.out" 2>&1 &
    second_pid=$!
    wait "$first_pid"
    wait "$second_pid"

    wait_for_ready
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 1 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_BEGIN status=begin' "$LOG_FILE")" -eq 2 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=ready' "$LOG_FILE")" -eq 2 ]
    [ "$(grep -c 'SUPERVISOR starting shim' "$LOG_FILE")" -eq 3 ]
}

@test "stale PID and PGID files never signal an unrelated live process" {
    mkdir -p "$LOG_DIR"
    sleep 30 &
    VICTIM_PID=$!
    export VICTIM_PID
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/shim.pid"
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/supervisor.pid"
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/pgid"
    run "$MANAGER" --stop
    assert_success
    assert_output --partial "was not running"
    kill -0 "$VICTIM_PID"
    [ ! -e "${LOG_DIR}/shim.pid" ]
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
    [ ! -e "${LOG_DIR}/pgid" ]
}

@test "duplicate starts preserve one supervisor and one start record" {
    run "$MANAGER" --start
    assert_success
    wait_for_file "${LOG_DIR}/supervisor.pid"
    local first second
    first="$(< "${LOG_DIR}/supervisor.pid")"
    run "$MANAGER" --start
    assert_success
    second="$(< "${LOG_DIR}/supervisor.pid")"
    [ "$first" = "$second" ]
    [ "$(grep -c 'SUPERVISOR starting shim' "$LOG_FILE")" -eq 1 ]
}

@test "supervisor records are single-write rather than tee-duplicated" {
    run "$MANAGER" --start
    assert_success
    run "$MANAGER" --stop
    assert_success
    [ "$(grep -c 'SUPERVISOR starting shim' "$LOG_FILE")" -eq 1 ]
    [ "$(grep -c 'SUPERVISOR supervisor exiting' "$LOG_FILE")" -eq 1 ]
}

@test "crash storm stops after deterministic limit and leaves no live supervisor" {
    export FAKE_SHIM_BEHAVIOR=crash
    export FAKE_SHIM_CRASH_CODE=42
    export DAAF_SHIM_TEST_STORM_LIMIT=3
    export DAAF_SHIM_TEST_RESTART_DELAY=0.05
    export DAAF_SHIM_TEST_READINESS_WAIT=3
    run "$MANAGER" --start
    assert_failure
    wait_for_log_text "RESTART_STORM"
    [ "$(grep -c 'shim exited rc=42' "$LOG_FILE")" -eq 3 ]
    grep -F 'RESTART_STORM crashes=3' "$LOG_FILE"
    [ ! -s "${LOG_DIR}/supervisor.pid" ]
}

@test "stop interrupts supervisor restart sleep promptly" {
    export FAKE_SHIM_BEHAVIOR=crash
    export DAAF_SHIM_TEST_RESTART_DELAY=20
    mkdir -p "$LOG_DIR"
    setsid "$MANAGER" __supervise >> "$LOG_FILE" 2>&1 &
    DIRECT_SUPERVISOR_PID=$!
    export DIRECT_SUPERVISOR_PID
    wait_for_log_text "shim exited rc=42"
    local before after
    before="$(date +%s)"
    run "$MANAGER" --stop
    assert_success
    after="$(date +%s)"
    [ $((after - before)) -lt 5 ]
    wait_for_dead "$DIRECT_SUPERVISOR_PID"
    DIRECT_SUPERVISOR_PID=""
}

@test "stop leaves no supervisor or shim child orphan" {
    run "$MANAGER" --start
    assert_success
    wait_for_file "${LOG_DIR}/supervisor.pid"
    wait_for_file "${LOG_DIR}/shim.pid"
    local sp pp
    sp="$(< "${LOG_DIR}/supervisor.pid")"
    pp="$(< "${LOG_DIR}/shim.pid")"
    run "$MANAGER" --stop
    assert_success
    wait_for_dead "$sp"
    wait_for_dead "$pp"
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
    [ ! -e "${LOG_DIR}/shim.pid" ]
    [ ! -e "${LOG_DIR}/pgid" ]
}

@test "no-setsid fallback restarts safely without a broad PGID" {
    export DAAF_SHIM_TEST_NO_SETSID=1
    run "$MANAGER" --start
    assert_success
    wait_for_file "${LOG_DIR}/supervisor.pid"
    wait_for_file "${LOG_DIR}/shim.pid"
    local old_sp old_pp new_sp new_pp
    old_sp="$(< "${LOG_DIR}/supervisor.pid")"
    old_pp="$(< "${LOG_DIR}/shim.pid")"
    [ ! -e "${LOG_DIR}/pgid" ]

    run "$MANAGER" --restart
    assert_manager_success
    new_sp="$(< "${LOG_DIR}/supervisor.pid")"
    new_pp="$(< "${LOG_DIR}/shim.pid")"
    [ "$old_sp" != "$new_sp" ]
    [ "$old_pp" != "$new_pp" ]
    [ ! -e "${LOG_DIR}/pgid" ]
    wait_for_dead "$old_sp"
    wait_for_dead "$old_pp"

    run "$MANAGER" --stop
    assert_success
    wait_for_dead "$new_sp"
    wait_for_dead "$new_pp"
    [ "$(grep -c 'process-group isolation unavailable' "$LOG_FILE")" -eq 2 ]
}
