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
LIFECYCLE_CAPABILITY_PY="${LIFECYCLE_CAPABILITY_PY:-${REPO_ROOT}/scripts/provider_shim/lifecycle_capability.py}"

setup() {
    SHIM_TEST_ROOT="${BATS_TEST_TMPDIR}/provider_shim"
    mkdir -p "$SHIM_TEST_ROOT"
    cp "$START_SHIM_SH" "${SHIM_TEST_ROOT}/start_shim.sh"
    cp "$LIFECYCLE_CAPABILITY_PY" "${SHIM_TEST_ROOT}/lifecycle_capability.py"
    chmod 0755 "${SHIM_TEST_ROOT}/start_shim.sh"
    chmod 0755 "${SHIM_TEST_ROOT}/lifecycle_capability.py"
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
                "text_verbosity": "medium",
            }
            # v1.3.0 (A1-R4): optional auth block, driven by FAKE_HEALTH_AUTH_STATE.
            auth_state = os.environ.get("FAKE_HEALTH_AUTH_STATE")
            if auth_state:
                auth = {"state": auth_state}
                days = os.environ.get("FAKE_HEALTH_AUTH_DAYS")
                if days:
                    auth["days_left"] = json.loads(days)
                if auth_state not in ("valid", "n/a"):
                    auth["recovery"] = "codex login --device-auth"
                payload["auth"] = auth
            raw = json.dumps(payload)
        body = raw.encode("utf-8")
        self.send_response(int(os.environ.get("FAKE_HEALTH_HTTP_STATUS", "200")))
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_args):
        return


if behavior == "ignore_term":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
else:
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
    unset FAKE_HEALTH_AUTH_STATE FAKE_HEALTH_AUTH_DAYS
    unset DAAF_SHIM_TEST_STOP_FAILURE DAAF_SHIM_TEST_RESULT_APPEND_FAILURE
    unset DAAF_SHIM_TEST_SIGNAL_RESULT_IN_PROGRESS DAAF_SHIM_TEST_FORCE_SETUP_FAILURE
    unset DAAF_SHIM_TEST_PRE_PID_DELAY_S DAAF_SHIM_TEST_TERMINATION_WAIT
    unset DAAF_SHIM_TEST_HANDOFF_SIGNAL DAAF_SHIM_TEST_SIGNAL_DURING_RESTORE
    unset DAAF_SHIM_TEST_AFTER_FIFO_DELAY_S DAAF_SHIM_TEST_AFTER_STREAM_DIR_DELAY_S
    unset DAAF_SHIM_TEST_AFTER_STREAM_FIFO_DELAY_S DAAF_SHIM_TEST_SIGNAL_AFTER_READY
    unset DAAF_SHIM_TEST_AFTER_PID_PUBLICATION_DELAY_S
    unset DAAF_SHIM_TEST_SIGNAL_AFTER_LOCK_RELEASE DAAF_SHIM_TEST_SIGNAL_DURING_RESULT_APPEND
    unset DAAF_SHIM_TEST_AFTER_RESTART_BEGIN_DELAY_S DAAF_SHIM_TEST_PID_DECODER_MISSING
    unset DAAF_SHIM_TEST_READY_PRESENTATION_PAD_BYTES
    unset DAAF_SHIM_TEST_PID_FAULT DAAF_SHIM_TEST_PID_RECORD_FAULT
    unset DAAF_SHIM_TEST_WORKSPACE_FAULT DAAF_SHIM_TEST_SIGNAL_DURING_PRESENTATION
    unset DAAF_SHIM_TEST_SIGNAL_AFTER_APPEND_ATTEMPT DAAF_SHIM_TEST_SIGNAL_AT_NATURAL_RETURN
    unset DAAF_SHIM_TEST_LIFECYCLE_LOCK_HOLD_S DAAF_SHIM_TEST_LOG_LOCK_HOLD_S
    unset LEGACY_STOP_GATE LEGACY_REAL_MANAGER LEGACY_SHIM_PY LEGACY_LOG_DIR
    unset LEGACY_STOP_ENTERED LEGACY_STOP_RELEASE LEGACY_STREAM_DIR
    unset PID_HELPER_WRAPPER_MODE PID_HELPER_TARGET PID_HELPER_UNCERTAINTY
    unset SHIM_BACKEND_MODE
}

teardown() {
    unset DAAF_SHIM_TEST_STOP_FAILURE DAAF_SHIM_TEST_RESULT_APPEND_FAILURE
    unset DAAF_SHIM_TEST_SIGNAL_RESULT_IN_PROGRESS DAAF_SHIM_TEST_FORCE_SETUP_FAILURE
    unset DAAF_SHIM_TEST_PRE_PID_DELAY_S DAAF_SHIM_TEST_TERMINATION_WAIT
    unset DAAF_SHIM_TEST_HANDOFF_SIGNAL DAAF_SHIM_TEST_SIGNAL_DURING_RESTORE
    unset DAAF_SHIM_TEST_AFTER_FIFO_DELAY_S DAAF_SHIM_TEST_AFTER_STREAM_DIR_DELAY_S
    unset DAAF_SHIM_TEST_AFTER_STREAM_FIFO_DELAY_S DAAF_SHIM_TEST_SIGNAL_AFTER_READY
    unset DAAF_SHIM_TEST_AFTER_PID_PUBLICATION_DELAY_S
    unset DAAF_SHIM_TEST_SIGNAL_AFTER_LOCK_RELEASE DAAF_SHIM_TEST_SIGNAL_DURING_RESULT_APPEND
    unset DAAF_SHIM_TEST_AFTER_RESTART_BEGIN_DELAY_S DAAF_SHIM_TEST_PID_DECODER_MISSING
    unset DAAF_SHIM_TEST_READY_PRESENTATION_PAD_BYTES
    unset DAAF_SHIM_TEST_PID_FAULT DAAF_SHIM_TEST_PID_RECORD_FAULT
    unset DAAF_SHIM_TEST_WORKSPACE_FAULT DAAF_SHIM_TEST_SIGNAL_DURING_PRESENTATION
    unset DAAF_SHIM_TEST_SIGNAL_AFTER_APPEND_ATTEMPT DAAF_SHIM_TEST_SIGNAL_AT_NATURAL_RETURN
    unset DAAF_SHIM_TEST_LIFECYCLE_LOCK_HOLD_S DAAF_SHIM_TEST_LOG_LOCK_HOLD_S
    unset LEGACY_STOP_GATE LEGACY_REAL_MANAGER LEGACY_SHIM_PY LEGACY_LOG_DIR
    unset LEGACY_STOP_ENTERED LEGACY_STOP_RELEASE LEGACY_STREAM_DIR
    unset PID_HELPER_WRAPPER_MODE PID_HELPER_TARGET PID_HELPER_UNCERTAINTY
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

wait_for_process_count() {
    local expected="$1" minimum="$2" attempts=0
    while [ "$attempts" -lt 100 ]; do
        [ "$(count_exact_arg_processes "$expected")" -ge "$minimum" ] && return 0
        sleep 0.05
        attempts=$((attempts + 1))
    done
    return 1
}

assert_pid_cmdline_equals() {
    local pid="$1" arg expected index=0
    local -a observed=()
    shift
    while IFS= read -r -d '' arg; do
        observed+=("$arg")
    done < "/proc/${pid}/cmdline"
    [ "${#observed[@]}" -eq "$#" ] || return 1
    for expected in "$@"; do
        [ "${observed[$index]}" = "$expected" ] || return 1
        index=$((index + 1))
    done
}

remove_lock_metadata_object() {
    local path="$1"
    if [ -d "$path" ] && [ ! -L "$path" ]; then
        rmdir "$path"
    else
        rm -f "$path"
    fi
}

remove_pid_fixture_object() {
    local path="$1"
    if [ -d "$path" ] && [ ! -L "$path" ]; then
        rmdir "$path"
    else
        rm -f "$path"
    fi
}

create_pid_fixture_object() {
    local kind="$1" path="$2" referent="$3"
    case "$kind" in
        fifo)
            mkfifo "$path"
            ;;
        symlink-fifo)
            mkfifo "$referent"
            ln -s "$referent" "$path"
            ;;
        directory)
            mkdir "$path"
            ;;
        socket)
            python3 -c 'import socket, sys; s = socket.socket(socket.AF_UNIX); s.bind(sys.argv[1]); s.close()' "$path"
            ;;
        malformed)
            printf 'not-a-pid\n' > "$path"
            ;;
        oversized)
            printf '%070d\n' 1 > "$path"
            ;;
        nul-byte)
            printf '12\0003\n' > "$path"
            ;;
        multiline)
            printf '12\n3\n' > "$path"
            ;;
        signed)
            printf '+123\n' > "$path"
            ;;
        whitespace)
            printf ' 123\n' > "$path"
            ;;
        empty)
            : > "$path"
            ;;
        *)
            return 1
            ;;
    esac
    if [ -f "$path" ] && [ ! -L "$path" ]; then
        chmod 0600 "$path"
    fi
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

install_pid_helper_wrapper() {
    local real_helper="${SHIM_TEST_ROOT}/lifecycle_capability.real.py"
    mv "${SHIM_TEST_ROOT}/lifecycle_capability.py" "$real_helper"
    cat > "${SHIM_TEST_ROOT}/lifecycle_capability.py" <<'PY'
#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.request import urlopen

real_helper = Path(__file__).with_name("lifecycle_capability.real.py")
mode = os.environ.get("PID_HELPER_WRAPPER_MODE", "")
if len(sys.argv) == 3 and sys.argv[1] == "pid-read":
    pid_path = Path(sys.argv[2])
    if mode == "trailing_empty":
        sys.stdout.write("LCAP1\tPID_READ\tABSENT\tabsent\t-\t\n")
        raise SystemExit(0)
    if mode == "invalid_when_ready" and pid_path.name == "supervisor.pid":
        try:
            port = os.environ["SHIM_PORT"]
            payload = json.load(urlopen(f"http://127.0.0.1:{port}/health", timeout=0.2))
        except Exception:
            payload = {}
        if payload.get("status") == "ok":
            sys.stdout.write("LCAP1\tPID_READ\tINVALID_CONTENT\tinjected_ready\t-\n")
            raise SystemExit(0)
    if mode == "later_uncertain" and pid_path.name == os.environ["PID_HELPER_TARGET"]:
        counter = Path(__file__).with_name(f"pid-read-{pid_path.name}.count")
        count = int(counter.read_text(encoding="ascii")) + 1 if counter.exists() else 1
        counter.write_text(str(count), encoding="ascii")
        if count > 1:
            kind = os.environ["PID_HELPER_UNCERTAINTY"]
            sys.stdout.write(f"LCAP1\tPID_READ\t{kind}\tinjected_later_read\t-\n")
            raise SystemExit(0)
result = subprocess.run([sys.executable, str(real_helper), *sys.argv[1:]], check=False)
raise SystemExit(result.returncode)
PY
    chmod 0755 "${SHIM_TEST_ROOT}/lifecycle_capability.py"
}

start_exact_role_shim_fixture() {
    python3 "${SHIM_TEST_ROOT}/anthropic_openai_shim.py" >/dev/null 2>&1 &
    VICTIM_PID=$!
    export VICTIM_PID
    wait_for_process_count "${SHIM_TEST_ROOT}/anthropic_openai_shim.py" 1
}

start_exact_role_supervisor_fixture() {
    local stream_dir="${LOG_DIR}/shim.stream.REGRESSION"
    local token="W1|shim.stream.REGRESSION|0123456789abcdef0123456789abcdef|0|0|0|0|0|0|0|0"
    python3 -c 'import os, sys; os.execv("/usr/bin/yes", ["bash", sys.argv[1], "__supervise", sys.argv[2], sys.argv[3]])' \
        "$MANAGER" "$stream_dir" "$token" >/dev/null &
    VICTIM_PID=$!
    export VICTIM_PID
    wait_for_process_count "$MANAGER" 1
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

start_legacy_four_field_supervisor() {
    mkdir -p "$LOG_DIR"
    local current_manager="${SHIM_TEST_ROOT}/start_shim.current"
    local legacy_stream_dir="${LOG_DIR}/shim.stream.A1b2C3d4E5"
    mv "$MANAGER" "$current_manager"
    cat > "$MANAGER" <<'SH'
#!/usr/bin/env bash
set -uo pipefail

if [ "${1:-}" = "__supervise" ]; then
    printf '%s\n' "$$" > "${LEGACY_LOG_DIR}/supervisor.pid"
    printf '%s\n' "$$" > "${LEGACY_LOG_DIR}/pgid"
    chmod 0600 "${LEGACY_LOG_DIR}/supervisor.pid" "${LEGACY_LOG_DIR}/pgid"
    python3 "$LEGACY_SHIM_PY" >/dev/null 2>&1 &
    child_pid=$!
    printf '%s\n' "$child_pid" > "${LEGACY_LOG_DIR}/shim.pid"
    chmod 0600 "${LEGACY_LOG_DIR}/shim.pid"
    stop_legacy_supervisor() {
        if [ "${LEGACY_STOP_GATE:-0}" = "1" ]; then
            printf 'entered\n' > "$LEGACY_STOP_ENTERED"
            while [ ! -e "$LEGACY_STOP_RELEASE" ]; do
                sleep 0.01
            done
        fi
        kill -TERM "$child_pid" 2>/dev/null || true
        wait "$child_pid" 2>/dev/null || true
        exit 0
    }
    trap stop_legacy_supervisor INT TERM
    printf 'ready\n' > "${LEGACY_STREAM_DIR}/legacy.ready"
    wait "$child_pid"
    exit $?
fi

exec "$LEGACY_REAL_MANAGER" "$@"
SH
    chmod 0755 "$MANAGER"
    mkdir "$legacy_stream_dir"
    chmod 0700 "$legacy_stream_dir"
    export LEGACY_REAL_MANAGER="$current_manager"
    export LEGACY_SHIM_PY="${SHIM_TEST_ROOT}/anthropic_openai_shim.py"
    export LEGACY_LOG_DIR="$LOG_DIR"
    export LEGACY_STREAM_DIR="$legacy_stream_dir"
    export LEGACY_STOP_ENTERED="${SHIM_TEST_ROOT}/legacy.stop.entered"
    export LEGACY_STOP_RELEASE="${SHIM_TEST_ROOT}/legacy.stop.release"
    setsid bash "$MANAGER" __supervise "$legacy_stream_dir" \
        > "${SHIM_TEST_ROOT}/legacy-supervisor.out" 2>&1 &
    DIRECT_SUPERVISOR_PID=$!
    export DIRECT_SUPERVISOR_PID
    if ! wait_for_file "${legacy_stream_dir}/legacy.ready"; then
        while IFS= read -r line; do
            printf '%s\n' "$line" >&3
        done < "${SHIM_TEST_ROOT}/legacy-supervisor.out"
        return 1
    fi
    wait_for_file "${LOG_DIR}/supervisor.pid"
    wait_for_file "${LOG_DIR}/shim.pid"
    assert_pid_cmdline_equals "$DIRECT_SUPERVISOR_PID" bash "$MANAGER" \
        __supervise "$legacy_stream_dir"
    mv "$current_manager" "$MANAGER"
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

@test "status reads every hostile supervisor pid target boundedly" {
    mkdir -p "$LOG_DIR"
    local kind pid_path="${LOG_DIR}/supervisor.pid"
    local referent="${SHIM_TEST_ROOT}/pid-referent"

    for kind in fifo symlink-fifo directory socket malformed oversized; do
        create_pid_fixture_object "$kind" "$pid_path" "$referent"
        run timeout 3 "$MANAGER" --status
        case "$kind" in
            malformed|oversized)
                assert_success
                assert_output "STATUS: stopped"
                ;;
            *)
                assert_failure
                assert_output --partial "STATUS: unavailable"
                ;;
        esac
        remove_pid_fixture_object "$pid_path"
        remove_pid_fixture_object "$referent"
    done
}

@test "status and stop fail closed for each missing PID decoder dependency" {
    mkdir -p "$LOG_DIR"
    printf '424242\n' > "${LOG_DIR}/supervisor.pid"
    printf 'running preserved-marker\n' > "${LOG_DIR}/supervisor.state"
    local dependency action

    for dependency in stat od awk; do
        export DAAF_SHIM_TEST_PID_DECODER_MISSING="$dependency"
        for action in --status --stop; do
            run timeout 3 "$MANAGER" "$action"
            assert_failure
            assert_output --partial "PID"
            assert_output --partial "unavailable"
            [ "$(< "${LOG_DIR}/supervisor.pid")" = "424242" ]
            grep -Fx 'running preserved-marker' "${LOG_DIR}/supervisor.state"
            [ ! -e "${LOG_DIR}/stop.requested" ]
        done
    done
}

@test "present but crashing PID capability helper makes status and stop preserve evidence" {
    mkdir -p "$LOG_DIR"
    printf '424242\n' > "${LOG_DIR}/supervisor.pid"
    printf '424242\n' > "${LOG_DIR}/pgid"
    chmod 0600 "${LOG_DIR}/supervisor.pid" "${LOG_DIR}/pgid"
    printf 'running preserved-marker\n' > "${LOG_DIR}/supervisor.state"
    export DAAF_SHIM_TEST_PID_FAULT=helper_crash
    local action action_output

    for action in --status --stop; do
        run timeout 3 "$MANAGER" "$action"
        action_output="$output"
        assert_failure
        if [ "$action" = "--status" ]; then
            [[ "$action_output" == *"PID"* ]]
        fi
        [ "$(< "${LOG_DIR}/supervisor.pid")" = "424242" ]
        [ "$(< "${LOG_DIR}/pgid")" = "424242" ]
        grep -Fx 'running preserved-marker' "${LOG_DIR}/supervisor.state"
        [ ! -e "${LOG_DIR}/stop.requested" ]
    done
}

@test "binary multiline oversized and non-decimal pid files are rejected while a valid pid works" {
    mkdir -p "$LOG_DIR"
    local kind pid_path="${LOG_DIR}/supervisor.pid"
    local referent="${SHIM_TEST_ROOT}/pid-referent"

    for kind in nul-byte oversized multiline signed whitespace empty; do
        create_pid_fixture_object "$kind" "$pid_path" "$referent"
        run timeout 3 "$MANAGER" --status
        assert_success
        assert_output "STATUS: stopped"
        remove_pid_fixture_object "$pid_path"
    done

    run "$MANAGER" --start
    assert_manager_success
    wait_for_file "$pid_path"
    run timeout 3 "$MANAGER" --status
    assert_success
    assert_output --partial "STATUS: running and strictly ready"
}

@test "stop treats every hostile pid target as invalid without blocking" {
    mkdir -p "$LOG_DIR"
    local kind pid_path="${LOG_DIR}/supervisor.pid"
    local referent="${SHIM_TEST_ROOT}/pid-referent"

    for kind in fifo symlink-fifo directory socket malformed oversized; do
        create_pid_fixture_object "$kind" "$pid_path" "$referent"
        run timeout 3 "$MANAGER" --stop
        [ "$status" -ne 124 ]
        case "$kind" in
            malformed|oversized) assert_success ;;
            *) assert_failure ;;
        esac
        refute_output --partial "timed out"
        remove_pid_fixture_object "$pid_path"
        remove_pid_fixture_object "$referent"
    done
}

@test "start restart and auto reject special pid targets boundedly" {
    mkdir -p "$LOG_DIR"
    local action kind pid_path="${LOG_DIR}/supervisor.pid"
    local referent="${SHIM_TEST_ROOT}/pid-referent"

    for action in --start --restart --auto; do
        for kind in fifo symlink-fifo directory socket; do
            [ "$action" != "--auto" ] || export DAAF_PROVIDER_SHIM=openai
            create_pid_fixture_object "$kind" "$pid_path" "$referent"
            run timeout 3 "$MANAGER" "$action"
            [ "$status" -ne 124 ]
            if [ "$action" = "--auto" ]; then
                assert_success
            else
                assert_failure
            fi
            remove_pid_fixture_object "$pid_path"
            remove_pid_fixture_object "$referent"
        done
    done
}

@test "typed PID infrastructure faults fail closed across every public action" {
    mkdir -p "$LOG_DIR"
    sleep 30 &
    VICTIM_PID=$!
    export VICTIM_PID
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/shim.pid"
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/supervisor.pid"
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/pgid"
    chmod 0600 "${LOG_DIR}/shim.pid" "${LOG_DIR}/supervisor.pid" "${LOG_DIR}/pgid"
    export DAAF_PROVIDER_SHIM=openai
    local action expected_status

    for action in --status --stop --start --restart --auto; do
        for fault in open fd_identity helper_crash malformed_output; do
            export DAAF_SHIM_TEST_PID_FAULT="$fault"
            run timeout 8 "$MANAGER" "$action"
            expected_status=1
            [ "$action" = "--restart" ] && expected_status=41
            [ "$action" = "--auto" ] && expected_status=0
            [ "$status" -eq "$expected_status" ]
            kill -0 "$VICTIM_PID"
            grep -Fx "$VICTIM_PID" "${LOG_DIR}/shim.pid"
            grep -Fx "$VICTIM_PID" "${LOG_DIR}/supervisor.pid"
            grep -Fx "$VICTIM_PID" "${LOG_DIR}/pgid"
            [ ! -e "${LOG_DIR}/stop.requested" ]
            [ ! -e "${LOG_FILE}.1" ]
            [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
        done
    done

    unset DAAF_SHIM_TEST_PID_FAULT
    run timeout 3 "$MANAGER" __rotate_logs
    assert_success
}

@test "regression 3 status preserves later hostile supervisor evidence" {
    mkdir -p "$LOG_DIR"
    start_exact_role_supervisor_fixture
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/supervisor.pid"
    chmod 0600 "${LOG_DIR}/supervisor.pid"
    install_pid_helper_wrapper
    export PID_HELPER_WRAPPER_MODE=later_uncertain
    export PID_HELPER_TARGET=supervisor.pid
    export PID_HELPER_UNCERTAINTY=HOSTILE_OBJECT

    run timeout 8 "$MANAGER" --status

    assert_failure
    assert_output --partial "STATUS: unavailable"
    kill -0 "$VICTIM_PID"
    grep -Fx "$VICTIM_PID" "${LOG_DIR}/supervisor.pid"
    [ ! -e "${LOG_DIR}/stop.requested" ]
}

@test "regression 3 start preserves later infrastructure supervisor evidence without launch" {
    mkdir -p "$LOG_DIR"
    start_exact_role_supervisor_fixture
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/supervisor.pid"
    chmod 0600 "${LOG_DIR}/supervisor.pid"
    install_pid_helper_wrapper
    export PID_HELPER_WRAPPER_MODE=later_uncertain
    export PID_HELPER_TARGET=supervisor.pid
    export PID_HELPER_UNCERTAINTY=INFRASTRUCTURE_ERROR

    run timeout 8 "$MANAGER" --start

    assert_failure
    kill -0 "$VICTIM_PID"
    grep -Fx "$VICTIM_PID" "${LOG_DIR}/supervisor.pid"
    [ ! -e "${LOG_DIR}/stop.requested" ]
    [ ! -e "${LOG_FILE}.1" ]
    [ "$(find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -name 'shim.stream.*' | wc -l)" -eq 0 ]
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
}

@test "regression 3 auto preserves later hostile supervisor evidence without launch" {
    export DAAF_PROVIDER_SHIM=openai
    mkdir -p "$LOG_DIR"
    start_exact_role_supervisor_fixture
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/supervisor.pid"
    chmod 0600 "${LOG_DIR}/supervisor.pid"
    install_pid_helper_wrapper
    export PID_HELPER_WRAPPER_MODE=later_uncertain
    export PID_HELPER_TARGET=supervisor.pid
    export PID_HELPER_UNCERTAINTY=HOSTILE_OBJECT

    run timeout 8 "$MANAGER" --auto

    assert_success
    assert_output --partial "SHIM_AUTO_FAILURE status=failed reason=pid_evidence"
    kill -0 "$VICTIM_PID"
    grep -Fx "$VICTIM_PID" "${LOG_DIR}/supervisor.pid"
    [ ! -e "${LOG_DIR}/stop.requested" ]
    [ ! -e "${LOG_FILE}.1" ]
    [ "$(find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -name 'shim.stream.*' | wc -l)" -eq 0 ]
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
}

@test "regression 3 stop removes neither sentinel nor shim evidence after later infrastructure read" {
    mkdir -p "$LOG_DIR"
    start_exact_role_shim_fixture
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/shim.pid"
    chmod 0600 "${LOG_DIR}/shim.pid"
    install_pid_helper_wrapper
    export PID_HELPER_WRAPPER_MODE=later_uncertain
    export PID_HELPER_TARGET=shim.pid
    export PID_HELPER_UNCERTAINTY=INFRASTRUCTURE_ERROR

    run timeout 8 "$MANAGER" --stop

    assert_failure
    kill -0 "$VICTIM_PID"
    grep -Fx "$VICTIM_PID" "${LOG_DIR}/shim.pid"
    [ ! -e "${LOG_DIR}/stop.requested" ]
}

@test "regression 7 helper records with trailing empty TAB fields are rejected" {
    mkdir -p "$LOG_DIR"
    install_pid_helper_wrapper
    export PID_HELPER_WRAPPER_MODE=trailing_empty

    run timeout 8 "$MANAGER" --status

    assert_failure
    assert_output --partial "STATUS: unavailable"
    [ ! -e "${LOG_DIR}/stop.requested" ]
}

@test "new lifecycle seams are inert unless test mode is exactly one" {
    export DAAF_SHIM_TEST_PID_FAULT=open
    export DAAF_SHIM_TEST_WORKSPACE_FAULT=create
    export DAAF_SHIM_TEST_SIGNAL_DURING_PRESENTATION=TERM
    export DAAF_SHIM_TEST_SIGNAL_AFTER_APPEND_ATTEMPT=TERM
    export DAAF_SHIM_TEST_SIGNAL_AT_NATURAL_RETURN=TERM
    export DAAF_SHIM_TEST_READY_PRESENTATION_PAD_BYTES=1048576
    unset DAAF_SHIM_TEST_MODE

    run timeout 15 "$MANAGER" --restart

    assert_manager_success
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=ready' "$LOG_FILE")" -eq 1 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=failed' "$LOG_FILE" || true)" -eq 0 ]
    wait_for_ready
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

@test "readiness renders an expiring auth warning naming the recovery command" {
    export SHIM_BACKEND_MODE=chatgpt
    export FAKE_HEALTH_BACKEND_MODE=chatgpt
    export FAKE_HEALTH_AUTH_STATE=expiring
    export FAKE_HEALTH_AUTH_DAYS=1.5
    run "$MANAGER" --start
    assert_manager_success
    assert_output --partial "strictly ready"
    assert_output --partial "ChatGPT subscription auth expires in 1.5 days"
    assert_output --partial "codex login --device-auth"
    # The same line is surfaced by --status.
    run "$MANAGER" --status
    assert_success
    assert_output --partial "expires in 1.5 days"
    assert_output --partial "codex login --device-auth"
}

@test "readiness renders a dead auth warning for expired absent and unreadable" {
    export SHIM_BACKEND_MODE=chatgpt
    export FAKE_HEALTH_BACKEND_MODE=chatgpt
    export FAKE_HEALTH_AUTH_STATE=expired
    run "$MANAGER" --start
    assert_manager_success
    assert_output --partial "ChatGPT subscription auth is dead (expired)"
    assert_output --partial "codex login --device-auth"
}

@test "a valid auth state prints an informational line without a warning" {
    export SHIM_BACKEND_MODE=chatgpt
    export FAKE_HEALTH_BACKEND_MODE=chatgpt
    export FAKE_HEALTH_AUTH_STATE=valid
    export FAKE_HEALTH_AUTH_DAYS=280
    run "$MANAGER" --start
    assert_manager_success
    run "$MANAGER" --status
    assert_success
    assert_output --partial "ChatGPT subscription auth is valid (expires in 280 days)"
    refute_output --partial "codex login --device-auth"
    refute_output --partial "is dead"
}

@test "the openai lane emits no auth line" {
    export SHIM_BACKEND_MODE=openai
    export FAKE_HEALTH_AUTH_STATE=n/a
    run "$MANAGER" --start
    assert_manager_success
    run "$MANAGER" --status
    assert_success
    refute_output --partial "ChatGPT subscription auth"
    refute_output --partial "codex login --device-auth"
}

@test "auth line sanitizes an injecting days value into a bounded token" {
    export SHIM_BACKEND_MODE=chatgpt
    # A /health body whose auth.days_left carries an embedded newline + shell
    # metacharacters (a forged-line / injection attempt). print_auth_line strips it
    # to the bounded [0-9.-] token before output (the D4 injection convention), so no
    # forged line and no metacharacters reach the terminal. The `\n` is a JSON string
    # escape that jq -r decodes to a real newline in the shell value.
    export FAKE_HEALTH_RAW='{"service":"daaf-anthropic-openai-shim","status":"ok","version":"1.2.12","backend_mode":"chatgpt","backend":"x","codex_home_present":true,"sanitize_tools":true,"reasoning_effort":null,"text_verbosity":"high","auth":{"state":"expiring","days_left":"2\nFORGED: fake auth line rm -rf slash"}}'
    # Drive the readiness path (not --status, which additionally dumps the raw HEALTH
    # JSON): the only auth output here is print_auth_line's own sanitized line.
    run "$MANAGER" --start
    assert_manager_success
    assert_output --partial "expires in 2"
    refute_output --partial "FORGED"
    refute_output --partial "rm -rf"
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
    assert_output --partial "SHIM_AUTO_FAILURE status=failed reason=strict_readiness"
    [ "$(grep -c 'MANAGER SHIM_AUTO_FAILURE status=failed reason=strict_readiness' "$LOG_FILE")" -eq 1 ]
}

@test "auto persists a specific preflight classification" {
    export DAAF_PROVIDER_SHIM=openai
    mv "${SHIM_TEST_ROOT}/anthropic_openai_shim.py" \
        "${SHIM_TEST_ROOT}/anthropic_openai_shim.py.missing"

    run "$MANAGER" --auto

    assert_success
    assert_output --partial "SHIM_AUTO_FAILURE status=failed reason=preflight"
    [ "$(grep -c 'MANAGER SHIM_AUTO_FAILURE status=failed reason=preflight' "$LOG_FILE")" -eq 1 ]
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
    [ ! -e "${LOG_DIR}/shim.pid" ]
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
    assert_output --partial "SHIM_AUTO_FAILURE status=failed reason=lifecycle_lock"
    [ "$(grep -c 'MANAGER SHIM_AUTO_FAILURE status=failed reason=lifecycle_lock' "$LOG_FILE")" -eq 1 ]
    [ $((after - before)) -lt 3 ]
    wait "$restart_pid"
    wait_for_ready
}

@test "stale legacy PID-derived FIFO does not prevent startup and is preserved" {
    mkdir -p "$LOG_DIR"
    local legacy_fifo="${LOG_DIR}/shim.stream.39"
    mkfifo "$legacy_fifo"

    run "$MANAGER" --start

    assert_manager_success
    wait_for_ready
    [ -p "$legacy_fifo" ]
    [ "$(find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -name 'shim.stream.*' | wc -l)" -eq 1 ]
}

@test "per-supervisor stream directory is private unique and removed after stop" {
    mkdir -p "$LOG_DIR"
    local reserved_stream_dir="${LOG_DIR}/shim.stream.AAAAAAAAAA"
    mkdir "$reserved_stream_dir"
    chmod 0700 "$reserved_stream_dir"
    printf 'foreign-owner-marker\n' > "${reserved_stream_dir}/marker"

    run "$MANAGER" --start
    assert_manager_success
    wait_for_file "${LOG_DIR}/supervisor.pid"
    local active_stream_dir
    active_stream_dir="$(find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d \
        -name 'shim.stream.*' ! -path "$reserved_stream_dir" -print -quit)"
    [ -n "$active_stream_dir" ]
    [ "$active_stream_dir" != "$reserved_stream_dir" ]
    [ "$(stat -c '%a' "$active_stream_dir")" = "700" ]
    [ -p "${active_stream_dir}/output.fifo" ]
    [ "$(stat -c '%a' "${active_stream_dir}/output.fifo")" = "600" ]

    run "$MANAGER" --stop
    assert_success
    [ ! -e "$active_stream_dir" ]
    grep -Fx 'foreign-owner-marker' "${reserved_stream_dir}/marker"
}

@test "forced supervisor setup failure is classified and leaves no state artifacts" {
    export DAAF_PROVIDER_SHIM=openai
    export DAAF_SHIM_TEST_FORCE_SETUP_FAILURE=after_state_write

    run "$MANAGER" --auto

    assert_success
    assert_output --partial "SHIM_AUTO_FAILURE status=failed reason=launch_setup"
    grep -F "SUPERVISOR_SETUP_FAILURE status=failed reason=setup_finalize" "$LOG_FILE"
    [ "$(grep -c 'MANAGER SHIM_AUTO_FAILURE status=failed reason=launch_setup' "$LOG_FILE")" -eq 1 ]
    [ "$(find "$LOG_DIR" -mindepth 1 -maxdepth 1 -name 'shim.stream.*' | wc -l)" -eq 0 ]
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
    [ ! -e "${LOG_DIR}/shim.pid" ]
    [ ! -e "${LOG_DIR}/pgid" ]
    [ ! -e "${LOG_DIR}/supervisor.state" ]
    [ ! -e "${LOG_DIR}/stop.requested" ]
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    [ "$(count_exact_arg_processes "$MANAGER")" -eq 0 ]
}

@test "interrupted explicit start cleans the pre-pid launch before stop can return" {
    export DAAF_SHIM_TEST_PRE_PID_DELAY_S=3
    export DAAF_SHIM_TEST_READINESS_WAIT=10
    local manager_pid manager_rc=0

    "$MANAGER" --start > "${SHIM_TEST_ROOT}/start-interrupt.out" 2>&1 &
    manager_pid=$!
    wait_for_process_count "$MANAGER" 2
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
    kill -TERM "$manager_pid"
    wait "$manager_pid" || manager_rc=$?

    [ "$manager_rc" -eq 130 ]
    grep -F "SHIM_START_INTERRUPTED status=interrupted kind=explicit signal=TERM" \
        "${SHIM_TEST_ROOT}/start-interrupt.out"
    run "$MANAGER" --stop
    assert_success
    assert_output --partial "Shim was not running"
    sleep 3.2
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    [ "$(count_exact_arg_processes "$MANAGER")" -eq 0 ]
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
    [ ! -e "${LOG_DIR}/shim.pid" ]
}

@test "interrupted auto start cleans the pre-pid launch and remains boot-safe" {
    export DAAF_PROVIDER_SHIM=openai
    export DAAF_SHIM_TEST_PRE_PID_DELAY_S=3
    export DAAF_SHIM_TEST_READINESS_WAIT=10
    local manager_pid manager_rc=0

    "$MANAGER" --auto > "${SHIM_TEST_ROOT}/auto-interrupt.out" 2>&1 &
    manager_pid=$!
    wait_for_process_count "$MANAGER" 2
    kill -TERM "$manager_pid"
    wait "$manager_pid" || manager_rc=$?

    [ "$manager_rc" -eq 0 ]
    grep -F "SHIM_START_INTERRUPTED status=interrupted kind=auto signal=TERM" \
        "${SHIM_TEST_ROOT}/auto-interrupt.out"
    sleep 3.2
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    [ "$(count_exact_arg_processes "$MANAGER")" -eq 0 ]
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
    [ ! -e "${LOG_DIR}/shim.pid" ]
}

@test "queued handoff signal makes explicit start exit 130 without an orphan" {
    export DAAF_SHIM_TEST_HANDOFF_SIGNAL=TERM

    run timeout 15 "$MANAGER" --start

    [ "$status" -eq 130 ]
    assert_output --partial "SHIM_START_INTERRUPTED status=interrupted kind=explicit signal=TERM"
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    [ "$(count_exact_arg_processes "$MANAGER")" -eq 0 ]
    [ "$(find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -name 'shim.stream.*' | wc -l)" -eq 0 ]
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
    [ ! -e "${LOG_DIR}/shim.pid" ]
}

@test "queued handoff signal keeps auto boot-safe without an orphan" {
    export DAAF_PROVIDER_SHIM=openai
    export DAAF_SHIM_TEST_HANDOFF_SIGNAL=TERM

    run timeout 15 "$MANAGER" --auto

    assert_success
    assert_output --partial "SHIM_START_INTERRUPTED status=interrupted kind=auto signal=TERM"
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    [ "$(count_exact_arg_processes "$MANAGER")" -eq 0 ]
    [ "$(find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -name 'shim.stream.*' | wc -l)" -eq 0 ]
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
    [ ! -e "${LOG_DIR}/shim.pid" ]
}

@test "queued handoff signal preserves restart exit 130 and failure record" {
    export DAAF_SHIM_TEST_HANDOFF_SIGNAL=TERM

    run timeout 15 "$MANAGER" --restart

    [ "$status" -eq 130 ]
    assert_output --partial "SHIM_RESTART_RESULT status=failed stage=interrupt reason=signal_TERM exit_code=130"
    refute_output --partial "SHIM_RESTART_RESULT status=ready"
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    [ "$(count_exact_arg_processes "$MANAGER")" -eq 0 ]
    [ "$(find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -name 'shim.stream.*' | wc -l)" -eq 0 ]
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
    [ ! -e "${LOG_DIR}/shim.pid" ]
}

@test "signal after atomic stream workspace allocation reclaims the workspace" {
    export DAAF_SHIM_TEST_AFTER_STREAM_DIR_DELAY_S=10
    local manager_pid manager_rc=0 stream_dir

    "$MANAGER" --start > "${SHIM_TEST_ROOT}/stream-dir-interrupt.out" 2>&1 &
    manager_pid=$!
    wait_for_file "${SHIM_TEST_ROOT}/test.stream.dir.ready"
    stream_dir="$(< "${SHIM_TEST_ROOT}/test.stream.dir.ready")"
    [ -d "$stream_dir" ]
    [ -p "${stream_dir}/output.fifo" ]
    kill -TERM "$manager_pid"
    wait "$manager_pid" || manager_rc=$?

    [ "$manager_rc" -eq 130 ]
    [ ! -e "$stream_dir" ]
    [ "$(find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -name 'shim.stream.*' | wc -l)" -eq 0 ]
}

@test "signal after stream FIFO creation reclaims the partial workspace" {
    export DAAF_SHIM_TEST_AFTER_STREAM_FIFO_DELAY_S=10
    local manager_pid manager_rc=0 fifo stream_dir

    "$MANAGER" --start > "${SHIM_TEST_ROOT}/stream-fifo-interrupt.out" 2>&1 &
    manager_pid=$!
    wait_for_file "${SHIM_TEST_ROOT}/test.stream.manager-fifo.ready"
    fifo="$(< "${SHIM_TEST_ROOT}/test.stream.manager-fifo.ready")"
    stream_dir="${fifo%/output.fifo}"
    [ -p "$fifo" ]
    kill -TERM "$manager_pid"
    wait "$manager_pid" || manager_rc=$?

    [ "$manager_rc" -eq 130 ]
    [ ! -e "$stream_dir" ]
    [ "$(find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -name 'shim.stream.*' | wc -l)" -eq 0 ]
}

@test "signal during queued-handler restoration is replayed exactly once" {
    export DAAF_SHIM_TEST_SIGNAL_DURING_RESTORE=after_int

    run timeout 15 "$MANAGER" --start

    [ "$status" -eq 130 ]
    assert_output --partial "SHIM_START_INTERRUPTED status=interrupted kind=explicit signal=TERM"
    [ "$(grep -c 'MANAGER SHIM_START_INTERRUPTED status=interrupted' "$LOG_FILE")" -eq 1 ]
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    [ "$(count_exact_arg_processes "$MANAGER")" -eq 0 ]
    [ "$(find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -name 'shim.stream.*' | wc -l)" -eq 0 ]
}

@test "foreground manager reclaims stream workspace after pre-publication supervisor SIGKILL" {
    export DAAF_SHIM_TEST_AFTER_FIFO_DELAY_S=10
    export DAAF_SHIM_TEST_READINESS_WAIT=10
    local manager_pid manager_rc=0 supervisor_pid stream_dir

    "$MANAGER" --start > "${SHIM_TEST_ROOT}/setup-kill.out" 2>&1 &
    manager_pid=$!
    wait_for_file "${SHIM_TEST_ROOT}/test.stream.fifo.ready"
    supervisor_pid="$(< "${SHIM_TEST_ROOT}/test.stream.fifo.ready")"
    stream_dir="$(find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -name 'shim.stream.*' -print -quit)"
    [ -n "$stream_dir" ]
    [ -p "${stream_dir}/output.fifo" ]
    [ ! -e "${LOG_DIR}/supervisor.pid" ]

    kill -KILL "$supervisor_pid"
    wait "$manager_pid" || manager_rc=$?

    [ "$manager_rc" -ne 0 ]
    [ "$manager_rc" -ne 137 ]
    [ ! -e "$stream_dir" ]
    [ "$(find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -name 'shim.stream.*' | wc -l)" -eq 0 ]
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    [ "$(count_exact_arg_processes "$MANAGER")" -eq 0 ]
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
    [ ! -e "${LOG_DIR}/shim.pid" ]
    [ ! -e "${LOG_DIR}/pgid" ]
    [ ! -e "${LOG_DIR}/stop.requested" ]
}

@test "foreground manager reclaims published unready workspace after exact supervisor SIGKILL" {
    export DAAF_SHIM_TEST_AFTER_PID_PUBLICATION_DELAY_S=10
    export DAAF_SHIM_TEST_READINESS_WAIT=10
    local manager_pid manager_rc=0 supervisor_pid stream_dir

    "$MANAGER" --start > "${SHIM_TEST_ROOT}/published-setup-kill.out" 2>&1 &
    manager_pid=$!
    wait_for_file "${SHIM_TEST_ROOT}/test.stream.pid-published.ready"
    supervisor_pid="$(< "${SHIM_TEST_ROOT}/test.stream.pid-published.ready")"
    [ "$(< "${LOG_DIR}/supervisor.pid")" = "$supervisor_pid" ]
    stream_dir="$(find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -name 'shim.stream.*' -print -quit)"
    [ -n "$stream_dir" ]
    [ -p "${stream_dir}/output.fifo" ]

    kill -KILL "$supervisor_pid"
    wait "$manager_pid" || manager_rc=$?

    [ "$manager_rc" -ne 0 ]
    [ "$manager_rc" -ne 137 ]
    grep -F 'SHIM_READINESS_FAILURE status=failed' "${SHIM_TEST_ROOT}/published-setup-kill.out"
    [ ! -e "$stream_dir" ]
    [ "$(find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -name 'shim.stream.*' | wc -l)" -eq 0 ]
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    [ "$(count_exact_arg_processes "$MANAGER")" -eq 0 ]
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
    [ ! -e "${LOG_DIR}/shim.pid" ]
    [ ! -e "${LOG_DIR}/pgid" ]
    [ ! -e "${LOG_DIR}/supervisor.state" ]
    [ ! -e "${LOG_DIR}/stop.requested" ]
}

@test "inode workspace cleanup removes renamed original and preserves replacement after published death" {
    export DAAF_SHIM_TEST_AFTER_PID_PUBLICATION_DELAY_S=10
    export DAAF_SHIM_TEST_READINESS_WAIT=10
    local manager_pid manager_rc=0 supervisor_pid original renamed replacement

    "$MANAGER" --start > "${SHIM_TEST_ROOT}/workspace-substitution.out" 2>&1 &
    manager_pid=$!
    wait_for_file "${SHIM_TEST_ROOT}/test.stream.pid-published.ready"
    supervisor_pid="$(< "${SHIM_TEST_ROOT}/test.stream.pid-published.ready")"
    original="$(find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -name 'shim.stream.*' -print -quit)"
    [ -n "$original" ]
    renamed="${original}.renamed"
    replacement="$original"
    mv "$original" "$renamed"
    mkdir "$replacement"
    chmod 0700 "$replacement"
    printf 'replacement\n' > "${replacement}/.owner"
    chmod 0600 "${replacement}/.owner"
    mkfifo "${replacement}/output.fifo"
    chmod 0600 "${replacement}/output.fifo"

    kill -KILL "$supervisor_pid"
    wait "$manager_pid" || manager_rc=$?

    [ "$manager_rc" -ne 0 ]
    [ ! -e "$renamed" ]
    [ -d "$replacement" ]
    grep -Fx 'replacement' "${replacement}/.owner"
    [ -p "${replacement}/output.fifo" ]
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
    [ ! -e "${LOG_DIR}/shim.pid" ]
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
}

@test "regression 6 TERM-to-KILL escalation rejects exact-argv PID reuse by start time" {
    local harness="${SHIM_TEST_ROOT}/start-time-escalation-harness.sh"
    awk '/^ACTION=/{exit} {print}' "$MANAGER" > "$harness"
    cat >> "$harness" <<'SH'
TOKEN_STATE=111
MARKER="${SCRIPT_DIR}/unexpected.kill"
termination_wait=1
process_start_token() {
    printf '%s' "$TOKEN_STATE"
}
pid_has_verified_role() {
    return 0
}
kill() {
    case "$1" in
        -TERM) TOKEN_STATE=222; return 0 ;;
        -KILL) : > "$MARKER"; return 0 ;;
        -0) return 0 ;;
        *) return 0 ;;
    esac
}
sleep() {
    return 0
}
terminate_verified_pid shim 424242 || true
[ ! -e "$MARKER" ]
SH
    chmod 0755 "$harness"

    run "$harness"

    assert_success
    [ ! -e "${SHIM_TEST_ROOT}/unexpected.kill" ]
}

@test "supervisor escalates a TERM-resistant child before removing pid evidence" {
    export FAKE_SHIM_BEHAVIOR=ignore_term
    export DAAF_SHIM_TEST_TERMINATION_WAIT=1
    run "$MANAGER" --start
    assert_manager_success
    wait_for_file "${LOG_DIR}/supervisor.pid"
    wait_for_file "${LOG_DIR}/shim.pid"
    local sp pp
    sp="$(< "${LOG_DIR}/supervisor.pid")"
    pp="$(< "${LOG_DIR}/shim.pid")"

    kill -TERM "$sp"
    wait_for_dead "$sp"
    wait_for_dead "$pp"

    [ ! -e "${LOG_DIR}/shim.pid" ]
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
    ! grep -F "SUPERVISOR_TEARDOWN_FAILURE" "$LOG_FILE"
}

@test "lifecycle flock serializes holders and auto-releases after process death" {
    export DAAF_SHIM_TEST_LIFECYCLE_LOCK_HOLD_S=1
    local first_pid second_pid dead_holder
    "$MANAGER" __rotate_logs > "${SHIM_TEST_ROOT}/lock-first.out" 2>&1 &
    first_pid=$!
    wait_for_file "${SHIM_TEST_ROOT}/test.lifecycle.locked"
    [ "$(< "${SHIM_TEST_ROOT}/test.lifecycle.locked")" = "$first_pid" ]
    "$MANAGER" __rotate_logs > "${SHIM_TEST_ROOT}/lock-second.out" 2>&1 &
    second_pid=$!
    sleep 0.2
    kill -0 "$first_pid"
    kill -0 "$second_pid"
    # The second holder cannot enter and overwrite the marker while first owns flock.
    [ "$(< "${SHIM_TEST_ROOT}/test.lifecycle.locked")" = "$first_pid" ]
    wait "$first_pid"
    wait "$second_pid"

    rm -f "${SHIM_TEST_ROOT}/test.lifecycle.locked"
    export DAAF_SHIM_TEST_LIFECYCLE_LOCK_HOLD_S=10
    "$MANAGER" __rotate_logs > "${SHIM_TEST_ROOT}/lock-death.out" 2>&1 &
    dead_holder=$!
    wait_for_file "${SHIM_TEST_ROOT}/test.lifecycle.locked"
    kill -KILL "$dead_holder"
    wait "$dead_holder" 2>/dev/null || true
    unset DAAF_SHIM_TEST_LIFECYCLE_LOCK_HOLD_S

    run timeout 3 "$MANAGER" __rotate_logs
    assert_success
    [ -d "${LOG_DIR}/lifecycle.lock" ]
    [ "$(stat -c '%a' "${LOG_DIR}/lifecycle.lock")" = "700" ]
}

@test "log-write flock serializes records and auto-releases after process death" {
    export DAAF_PROVIDER_SHIM=not-openai
    export DAAF_SHIM_TEST_LOG_LOCK_HOLD_S=1
    local first_pid second_pid dead_holder
    "$MANAGER" --auto > "${SHIM_TEST_ROOT}/log-lock-first.out" 2>&1 &
    first_pid=$!
    wait_for_file "${SHIM_TEST_ROOT}/test.log-write.locked"
    [ "$(< "${SHIM_TEST_ROOT}/test.log-write.locked")" = "$first_pid" ]
    "$MANAGER" --auto > "${SHIM_TEST_ROOT}/log-lock-second.out" 2>&1 &
    second_pid=$!
    sleep 0.2
    kill -0 "$first_pid"
    kill -0 "$second_pid"
    # The second append cannot enter and overwrite the marker during first's hold.
    [ "$(< "${SHIM_TEST_ROOT}/test.log-write.locked")" = "$first_pid" ]
    wait "$first_pid"
    wait "$second_pid"

    rm -f "${SHIM_TEST_ROOT}/test.log-write.locked"
    export DAAF_SHIM_TEST_LOG_LOCK_HOLD_S=10
    "$MANAGER" --auto > "${SHIM_TEST_ROOT}/log-lock-death.out" 2>&1 &
    dead_holder=$!
    wait_for_file "${SHIM_TEST_ROOT}/test.log-write.locked"
    kill -KILL "$dead_holder"
    wait "$dead_holder" 2>/dev/null || true
    unset DAAF_SHIM_TEST_LOG_LOCK_HOLD_S

    run timeout 3 "$MANAGER" --auto
    assert_success
    [ -d "${LOG_DIR}/log-write.lock" ]
    [ "$(stat -c '%a' "${LOG_DIR}/log-write.lock")" = "700" ]
}

@test "non-regular owner metadata is ignored by both flock paths without blocking" {
    export DAAF_PROVIDER_SHIM=openai
    start_external_fixture
    mkdir -p "${LOG_DIR}/lifecycle.lock" "${LOG_DIR}/log-write.lock"
    local kind lifecycle_owner="${LOG_DIR}/lifecycle.lock/owner.pid"
    local log_owner="${LOG_DIR}/log-write.lock/owner.pid"
    local lifecycle_referent="${SHIM_TEST_ROOT}/lifecycle-owner-referent"
    local log_referent="${SHIM_TEST_ROOT}/log-owner-referent"
    printf 'lifecycle-unchanged\n' > "$lifecycle_referent"
    printf 'log-unchanged\n' > "$log_referent"

    for kind in fifo symlink directory; do
        case "$kind" in
            fifo)
                mkfifo "$lifecycle_owner" "$log_owner"
                ;;
            symlink)
                ln -s "$lifecycle_referent" "$lifecycle_owner"
                ln -s "$log_referent" "$log_owner"
                ;;
            directory)
                mkdir "$lifecycle_owner" "$log_owner"
                ;;
        esac

        run timeout 3 "$MANAGER" --auto
        assert_success
        assert_output --partial "SHIM_AUTO_READY status=ready"
        run timeout 3 "$MANAGER" __rotate_logs
        assert_success
        grep -Fx 'lifecycle-unchanged' "$lifecycle_referent"
        grep -Fx 'log-unchanged' "$log_referent"

        remove_lock_metadata_object "$lifecycle_owner"
        remove_lock_metadata_object "$log_owner"
    done
}

@test "rejected symlink log directory emits stderr-only setup diagnostics" {
    local foreign_dir="${SHIM_TEST_ROOT}/foreign-logs"
    mkdir "$foreign_dir"
    ln -s "$foreign_dir" "$LOG_DIR"

    run timeout 3 "$MANAGER" __supervise

    assert_failure
    assert_output --partial "shim log directory is a symlink"
    assert_output --partial "persistence=skipped_unvalidated_state"
    [ "$(find "$foreign_dir" -mindepth 1 -maxdepth 1 | wc -l)" -eq 0 ]
    [ ! -e "${foreign_dir}/shim.log" ]
    [ ! -e "${foreign_dir}/supervisor.state" ]
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
    chmod 0600 "${LOG_DIR}/shim.pid" "${LOG_DIR}/supervisor.pid" "${LOG_DIR}/pgid"

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
    assert_output --partial "record_persisted=unknown"
    refute_output --partial "record_persisted=no"
    [ "$(grep -c 'MANAGER SHIM_RESTART_BEGIN status=begin' "$LOG_FILE")" -eq 1 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT' "$LOG_FILE" || true)" -eq 0 ]
}

@test "regression 4 append failure overrides unmanaged-ready restart exit with 43" {
    export DAAF_SHIM_TEST_RESULT_APPEND_FAILURE=1
    start_external_fixture

    run timeout 15 "$MANAGER" --restart

    [ "$status" -eq 43 ] || {
        printf 'expected restart exit 43, observed %s\n' "$status" >&3
        false
    }
    assert_output --partial "stage=record reason=manager_log_write exit_code=43"
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT' "$LOG_FILE" || true)" -eq 0 ]
    kill -0 "$EXTERNAL_SERVER_PID"
}

@test "regression 4 append failure overrides stop-result restart exit with 43" {
    run "$MANAGER" --start
    assert_manager_success
    export DAAF_SHIM_TEST_STOP_FAILURE=1
    export DAAF_SHIM_TEST_RESULT_APPEND_FAILURE=1

    run timeout 15 "$MANAGER" --restart

    [ "$status" -eq 43 ] || {
        printf 'expected restart exit 43, observed %s\n' "$status" >&3
        false
    }
    assert_output --partial "stage=record reason=manager_log_write exit_code=43"
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT' "$LOG_FILE" || true)" -eq 0 ]
}

@test "regression 4 append failure overrides launch-result restart exit with 43" {
    export FAKE_SHIM_BEHAVIOR=crash
    export DAAF_SHIM_TEST_STORM_LIMIT=2
    export DAAF_SHIM_TEST_RESTART_DELAY=0.05
    export DAAF_SHIM_TEST_READINESS_WAIT=3
    export DAAF_SHIM_TEST_RESULT_APPEND_FAILURE=1

    run timeout 15 "$MANAGER" --restart

    [ "$status" -eq 43 ] || {
        printf 'expected restart exit 43, observed %s\n' "$status" >&3
        false
    }
    assert_output --partial "stage=record reason=manager_log_write exit_code=43"
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT' "$LOG_FILE" || true)" -eq 0 ]
}

@test "regression 4 append failure overrides readiness-result restart exit with 43" {
    export FAKE_HEALTH_STATUS=starting
    export DAAF_SHIM_TEST_READINESS_WAIT=2
    export DAAF_SHIM_TEST_RESULT_APPEND_FAILURE=1

    run timeout 15 "$MANAGER" --restart

    [ "$status" -eq 43 ] || {
        printf 'expected restart exit 43, observed %s\n' "$status" >&3
        false
    }
    assert_output --partial "stage=record reason=manager_log_write exit_code=43"
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT' "$LOG_FILE" || true)" -eq 0 ]
}

@test "regression 4 append failure overrides invalid-supervisor result exit with 43" {
    install_pid_helper_wrapper
    export PID_HELPER_WRAPPER_MODE=invalid_when_ready
    export DAAF_SHIM_TEST_RESULT_APPEND_FAILURE=1

    run timeout 15 "$MANAGER" --restart

    [ "$status" -eq 43 ] || {
        printf 'expected restart exit 43, observed %s\n' "$status" >&3
        false
    }
    assert_output --partial "stage=record reason=manager_log_write exit_code=43"
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT' "$LOG_FILE" || true)" -eq 0 ]
}

@test "restart commits durable READY when stderr is already closed" {
    local manager_rc=0

    "$MANAGER" --restart > "${SHIM_TEST_ROOT}/restart-closed-stderr.out" 2>&- || manager_rc=$?

    [ "$manager_rc" -eq 0 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=ready' "$LOG_FILE")" -eq 1 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=failed' "$LOG_FILE" || true)" -eq 0 ]
    wait_for_ready
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 1 ]
    run timeout 3 "$MANAGER" __rotate_logs
    assert_success
}

@test "restart survives stderr consumer closing after begin before READY" {
    export DAAF_SHIM_TEST_AFTER_RESTART_BEGIN_DELAY_S=0.3
    local manager_pid manager_rc=0

    "$MANAGER" --restart > "${SHIM_TEST_ROOT}/restart-closing-consumer.out" \
        2> >(awk '/SHIM_RESTART_BEGIN/{exit}') &
    manager_pid=$!
    wait "$manager_pid" || manager_rc=$?

    [ "$manager_rc" -eq 0 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=ready' "$LOG_FILE")" -eq 1 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=failed' "$LOG_FILE" || true)" -eq 0 ]
    wait_for_ready
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 1 ]
    run timeout 3 "$MANAGER" __rotate_logs
    assert_success
}

@test "restart commits READY when stderr consumer remains open but does not read" {
    export DAAF_SHIM_TEST_READY_PRESENTATION_PAD_BYTES=1048576
    local manager_rc=0

    timeout 15 "$MANAGER" --restart > "${SHIM_TEST_ROOT}/restart-full-stderr.out" \
        2> >(sleep 2) || manager_rc=$?

    [ "$manager_rc" -eq 0 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=ready' "$LOG_FILE")" -eq 1 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=failed' "$LOG_FILE" || true)" -eq 0 ]
    wait_for_ready
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 1 ]
    run timeout 3 "$MANAGER" __rotate_logs
    assert_success
}

@test "committed signal under full stderr reaps the bounded presentation children" {
    export DAAF_SHIM_TEST_READY_PRESENTATION_PAD_BYTES=1048576
    export DAAF_SHIM_TEST_SIGNAL_DURING_PRESENTATION=TERM
    local manager_rc=0 writer_pid timer_pid

    timeout 15 "$MANAGER" --restart > "${SHIM_TEST_ROOT}/restart-presentation-signal.out" \
        2> >(sleep 2) || manager_rc=$?

    [ "$manager_rc" -eq 0 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=ready' "$LOG_FILE")" -eq 1 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=failed' "$LOG_FILE" || true)" -eq 0 ]
    wait_for_file "${SHIM_TEST_ROOT}/test.presentation.children"
    read -r writer_pid timer_pid < "${SHIM_TEST_ROOT}/test.presentation.children"
    ! kill -0 "$writer_pid" 2>/dev/null
    ! kill -0 "$timer_pid" 2>/dev/null
    wait_for_ready
    run timeout 3 "$MANAGER" __rotate_logs
    assert_success
}

@test "restart append failure with closed stderr returns 43 without false commit" {
    export DAAF_SHIM_TEST_RESULT_APPEND_FAILURE=1
    local manager_rc=0

    "$MANAGER" --restart > "${SHIM_TEST_ROOT}/restart-append-failure-closed.out" 2>&- || manager_rc=$?

    [ "$manager_rc" -eq 43 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT' "$LOG_FILE" || true)" -eq 0 ]
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    [ ! -s "${LOG_DIR}/supervisor.pid" ]
    [ ! -s "${LOG_DIR}/shim.pid" ]
    run timeout 3 "$MANAGER" __rotate_logs
    assert_success
}

@test "signal before restart result append commits one interrupt result" {
    export DAAF_SHIM_TEST_SIGNAL_RESULT_IN_PROGRESS=1

    run timeout 15 "$MANAGER" --restart

    [ "$status" -eq 130 ]
    assert_output --partial "SHIM_RESTART_RESULT status=failed stage=interrupt reason=signal_TERM exit_code=130"
    refute_output --partial "write_interrupted"
    refute_output --partial "record_persisted=unknown"
    [ "$(grep -c 'MANAGER SHIM_RESTART_BEGIN status=begin' "$LOG_FILE")" -eq 1 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=failed stage=interrupt' "$LOG_FILE")" -eq 1 ]
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    [ "$(count_exact_arg_processes "$MANAGER")" -eq 0 ]
    [ ! -s "${LOG_DIR}/supervisor.pid" ]
    [ ! -s "${LOG_DIR}/shim.pid" ]
}

@test "signal after successful failure-result append preserves the original committed result" {
    export DAAF_SHIM_TEST_SIGNAL_DURING_RESULT_APPEND=1
    export FAKE_SHIM_BEHAVIOR=crash
    export DAAF_SHIM_TEST_STORM_LIMIT=2
    export DAAF_SHIM_TEST_RESTART_DELAY=0.05
    export DAAF_SHIM_TEST_READINESS_WAIT=3

    run timeout 15 "$MANAGER" --restart

    [ "$status" -eq 41 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=failed stage=launch reason=launch_failed exit_code=41' "$LOG_FILE")" -eq 1 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT' "$LOG_FILE")" -eq 1 ]
    refute_output --partial "record_persisted=unknown"
    refute_output --partial "stage=interrupt"
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    [ "$(count_exact_arg_processes "$MANAGER")" -eq 0 ]
}

@test "append failure plus queued post-attempt signal is never retried" {
    export DAAF_SHIM_TEST_RESULT_APPEND_FAILURE=1
    export DAAF_SHIM_TEST_SIGNAL_AFTER_APPEND_ATTEMPT=TERM

    run timeout 15 "$MANAGER" --restart

    [ "$status" -eq 43 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT' "$LOG_FILE" || true)" -eq 0 ]
    refute_output --partial "stage=interrupt"
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    [ ! -s "${LOG_DIR}/supervisor.pid" ]
    [ ! -s "${LOG_DIR}/shim.pid" ]
    run timeout 3 "$MANAGER" __rotate_logs
    assert_success
}

@test "interrupt after durable READY preserves the committed generation and result" {
    export DAAF_SHIM_TEST_SIGNAL_AFTER_READY=1

    run timeout 15 "$MANAGER" --restart

    assert_success
    assert_output --partial "SHIM_RESTART_RESULT status=ready stage=readiness reason=ready exit_code=0"
    refute_output --partial "SHIM_RESTART_RESULT status=failed"
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=ready' "$LOG_FILE")" -eq 1 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=failed' "$LOG_FILE" || true)" -eq 0 ]
    wait_for_ready
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 1 ]
    run timeout 3 "$MANAGER" --status
    assert_success
    assert_output --partial "STATUS: running and strictly ready"
}

@test "signal after durable READY and lock release exits committed success" {
    export DAAF_SHIM_TEST_SIGNAL_AFTER_LOCK_RELEASE=1

    run timeout 15 "$MANAGER" --restart

    assert_success
    assert_output --partial "SHIM_RESTART_RESULT status=ready stage=readiness reason=ready exit_code=0"
    refute_output --partial "SHIM_RESTART_RESULT status=failed"
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=ready' "$LOG_FILE")" -eq 1 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=failed' "$LOG_FILE" || true)" -eq 0 ]
    wait_for_ready
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 1 ]
    run timeout 3 "$MANAGER" __rotate_logs
    assert_success
}

@test "signal at the final natural-return boundary keeps committed exit and result" {
    export DAAF_SHIM_TEST_READY_PRESENTATION_PAD_BYTES=1048576
    export DAAF_SHIM_TEST_SIGNAL_AT_NATURAL_RETURN=TERM

    run timeout 15 "$MANAGER" --restart

    assert_success
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT status=ready stage=readiness reason=ready exit_code=0' "$LOG_FILE")" -eq 1 ]
    [ "$(grep -c 'MANAGER SHIM_RESTART_RESULT' "$LOG_FILE")" -eq 1 ]
    wait_for_ready
    run timeout 3 "$MANAGER" __rotate_logs
    assert_success
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

@test "legacy four-field supervisor is ownership-verified and stopped without an orphan" {
    start_legacy_four_field_supervisor
    local old_sp old_pp
    old_sp="$(< "${LOG_DIR}/supervisor.pid")"
    old_pp="$(< "${LOG_DIR}/shim.pid")"
    [ "$old_sp" = "$DIRECT_SUPERVISOR_PID" ]

    run "$MANAGER" --stop

    assert_success
    assert_output --partial "Shim stopped"
    wait_for_dead "$old_sp"
    wait_for_dead "$old_pp"
    DIRECT_SUPERVISOR_PID=""
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    [ "$(count_exact_arg_processes "$MANAGER")" -eq 0 ]
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
    [ ! -e "${LOG_DIR}/shim.pid" ]
    [ ! -e "${LOG_DIR}/pgid" ]
}

@test "restart waits for legacy four-field teardown before launching one replacement" {
    export LEGACY_STOP_GATE=1
    start_legacy_four_field_supervisor
    local old_sp old_pp restart_pid restart_rc=0 new_sp new_pp
    old_sp="$(< "${LOG_DIR}/supervisor.pid")"
    old_pp="$(< "${LOG_DIR}/shim.pid")"

    "$MANAGER" --restart > "${SHIM_TEST_ROOT}/legacy-restart.out" 2>&1 &
    restart_pid=$!
    wait_for_file "$LEGACY_STOP_ENTERED"
    kill -0 "$old_sp"
    wait_for_dead "$old_pp"
    kill -0 "$restart_pid"
    [ "$(< "${LOG_DIR}/supervisor.pid")" = "$old_sp" ]
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    ! grep -F "SHIM_RESTART_RESULT status=ready" \
        "${SHIM_TEST_ROOT}/legacy-restart.out" >/dev/null 2>&1

    : > "$LEGACY_STOP_RELEASE"
    wait "$restart_pid" || restart_rc=$?

    [ "$restart_rc" -eq 0 ]
    grep -F "SHIM_RESTART_RESULT status=ready stage=readiness reason=ready exit_code=0" \
        "${SHIM_TEST_ROOT}/legacy-restart.out"
    new_sp="$(< "${LOG_DIR}/supervisor.pid")"
    new_pp="$(< "${LOG_DIR}/shim.pid")"
    [ "$new_sp" != "$old_sp" ]
    [ "$new_pp" != "$old_pp" ]
    wait_for_dead "$old_sp"
    wait_for_dead "$old_pp"
    wait_for_ready
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 1 ]
    kill -0 "$new_sp"
    DIRECT_SUPERVISOR_PID=""
}

@test "four-field lookalike with legacy tokens in wrong positions is never signalled" {
    mkdir -p "$LOG_DIR"
    local legacy_stream_dir="${LOG_DIR}/shim.stream.A1b2C3d4E5"
    python3 -c 'import os, sys; os.execv("/usr/bin/yes", ["bash", sys.argv[1], sys.argv[2], "__supervise"])' \
        "$MANAGER" "$legacy_stream_dir" >/dev/null &
    VICTIM_PID=$!
    export VICTIM_PID
    wait_for_process_count "$MANAGER" 1
    assert_pid_cmdline_equals "$VICTIM_PID" bash "$MANAGER" \
        "$legacy_stream_dir" __supervise
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/supervisor.pid"
    chmod 0600 "${LOG_DIR}/supervisor.pid"

    run "$MANAGER" --stop

    assert_success
    assert_output --partial "was not running"
    kill -0 "$VICTIM_PID"
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
}

@test "stale PID and PGID files never signal an unrelated live process" {
    mkdir -p "$LOG_DIR"
    sleep 30 &
    VICTIM_PID=$!
    export VICTIM_PID
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/shim.pid"
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/supervisor.pid"
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/pgid"
    chmod 0600 "${LOG_DIR}/shim.pid" "${LOG_DIR}/supervisor.pid" "${LOG_DIR}/pgid"
    run "$MANAGER" --stop
    assert_success
    assert_output --partial "was not running"
    kill -0 "$VICTIM_PID"
    [ ! -e "${LOG_DIR}/shim.pid" ]
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
    [ ! -e "${LOG_DIR}/pgid" ]
}

@test "deceptive shim argv mentioning the source out of position is never signalled" {
    mkdir -p "$LOG_DIR"
    bash -c 'while :; do sleep 1; done' decoy "$SHIM_TEST_ROOT/anthropic_openai_shim.py" &
    VICTIM_PID=$!
    export VICTIM_PID
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/shim.pid"
    chmod 0600 "${LOG_DIR}/shim.pid"

    run "$MANAGER" --stop

    assert_success
    assert_output --partial "was not running"
    kill -0 "$VICTIM_PID"
}

@test "deceptive supervisor argv mentioning manager and role out of position is never signalled" {
    mkdir -p "$LOG_DIR"
    bash -c 'while :; do sleep 1; done' decoy "$MANAGER" __supervise &
    VICTIM_PID=$!
    export VICTIM_PID
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/supervisor.pid"
    chmod 0600 "${LOG_DIR}/supervisor.pid"

    run "$MANAGER" --stop

    assert_success
    assert_output --partial "was not running"
    kill -0 "$VICTIM_PID"
}

@test "current capability-bearing five-field supervisor remains ownership-verified" {
    run "$MANAGER" --start
    assert_manager_success
    wait_for_file "${LOG_DIR}/supervisor.pid"
    wait_for_file "${LOG_DIR}/shim.pid"
    local sp pp arg stream_basename
    local -a supervisor_argv=()
    sp="$(< "${LOG_DIR}/supervisor.pid")"
    pp="$(< "${LOG_DIR}/shim.pid")"
    while IFS= read -r -d '' arg; do
        supervisor_argv+=("$arg")
    done < "/proc/${sp}/cmdline"
    [ "${#supervisor_argv[@]}" -eq 5 ]
    case "${supervisor_argv[0]##*/}" in
        bash|bash[0-9]*) ;;
        *) false ;;
    esac
    [ "${supervisor_argv[1]}" = "$MANAGER" ]
    [ "${supervisor_argv[2]}" = "__supervise" ]
    [[ "${supervisor_argv[3]}" == "${LOG_DIR}/shim.stream."* ]]
    stream_basename="${supervisor_argv[3]##*/}"
    [[ "${supervisor_argv[4]}" == W1\|"${stream_basename}"\|* ]]

    run "$MANAGER" --stop

    assert_success
    wait_for_dead "$sp"
    wait_for_dead "$pp"
}

@test "regression 1 malformed five-field supervisor capability is never ownership evidence" {
    mkdir -p "$LOG_DIR"
    local stream_dir="${LOG_DIR}/shim.stream.MALFORMED"
    python3 -c 'import os, sys; os.execv("/usr/bin/yes", ["bash", sys.argv[1], "__supervise", sys.argv[2], sys.argv[3]])' \
        "$MANAGER" "$stream_dir" "W1|shim.stream.MALFORMED|junk" >/dev/null &
    VICTIM_PID=$!
    export VICTIM_PID
    wait_for_process_count "$MANAGER" 1
    assert_pid_cmdline_equals "$VICTIM_PID" bash "$MANAGER" __supervise \
        "$stream_dir" "W1|shim.stream.MALFORMED|junk"
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/supervisor.pid"
    chmod 0600 "${LOG_DIR}/supervisor.pid"

    run "$MANAGER" --stop

    assert_success
    assert_output --partial "was not running"
    kill -0 "$VICTIM_PID"
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
}

@test "regression 2 status adjudicates exact-role shim evidence before health" {
    export FAKE_SHIM_START_DELAY=30
    mkdir -p "$LOG_DIR"
    start_exact_role_shim_fixture
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/shim.pid"
    chmod 0600 "${LOG_DIR}/shim.pid"

    run timeout 8 "$MANAGER" --status

    assert_failure
    refute_output --partial "STATUS: stopped"
    kill -0 "$VICTIM_PID"
    grep -Fx "$VICTIM_PID" "${LOG_DIR}/shim.pid"
}

@test "regression 2 start preserves exact-role shim evidence and never allocates launch" {
    export FAKE_SHIM_START_DELAY=30
    export DAAF_SHIM_TEST_READINESS_WAIT=1
    mkdir -p "$LOG_DIR"
    start_exact_role_shim_fixture
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/shim.pid"
    chmod 0600 "${LOG_DIR}/shim.pid"

    run timeout 8 "$MANAGER" --start

    assert_failure
    kill -0 "$VICTIM_PID"
    grep -Fx "$VICTIM_PID" "${LOG_DIR}/shim.pid"
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
    [ ! -e "${LOG_DIR}/stop.requested" ]
    [ "$(find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -name 'shim.stream.*' | wc -l)" -eq 0 ]
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 1 ]
}

@test "regression 2 auto preserves exact-role shim evidence and never allocates launch" {
    export FAKE_SHIM_START_DELAY=30
    export DAAF_SHIM_TEST_READINESS_WAIT=1
    export DAAF_PROVIDER_SHIM=openai
    mkdir -p "$LOG_DIR"
    start_exact_role_shim_fixture
    printf '%s\n' "$VICTIM_PID" > "${LOG_DIR}/shim.pid"
    chmod 0600 "${LOG_DIR}/shim.pid"

    run timeout 8 "$MANAGER" --auto

    assert_success
    assert_output --partial "SHIM_AUTO_FAILURE"
    kill -0 "$VICTIM_PID"
    grep -Fx "$VICTIM_PID" "${LOG_DIR}/shim.pid"
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
    [ ! -e "${LOG_DIR}/stop.requested" ]
    [ "$(find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -name 'shim.stream.*' | wc -l)" -eq 0 ]
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 1 ]
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

@test "no-setsid control is ignored in production mode and honored in test mode" {
    export DAAF_SHIM_TEST_NO_SETSID=1
    unset DAAF_SHIM_TEST_MODE

    run "$MANAGER" --start
    assert_manager_success
    wait_for_file "${LOG_DIR}/pgid"
    run "$MANAGER" --stop
    assert_success

    export DAAF_SHIM_TEST_MODE=1
    run "$MANAGER" --start
    assert_manager_success
    wait_for_file "${LOG_DIR}/supervisor.pid"
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

# --- D3: lifecycle status honesty (supervisor.state) ------------------------

@test "status reports a restart-storm give-up distinctly from a clean stop" {
    # Drive the supervisor directly (as at boot via --auto), so no foreground
    # manager is watching to run its post-failure cleanup. This is the scenario
    # the give-up marker exists for: a detached supervisor that exhausts its
    # storm budget long after launch, with nobody to observe the failure live.
    export FAKE_SHIM_BEHAVIOR=crash
    export FAKE_SHIM_CRASH_CODE=42
    export DAAF_SHIM_TEST_STORM_LIMIT=3
    export DAAF_SHIM_TEST_RESTART_DELAY=0.05
    mkdir -p "$LOG_DIR"
    setsid "$MANAGER" __supervise >> "$LOG_FILE" 2>&1 &
    DIRECT_SUPERVISOR_PID=$!
    export DIRECT_SUPERVISOR_PID
    wait_for_log_text "RESTART_STORM"
    wait_for_log_text "supervisor exiting"
    wait_for_dead "$DIRECT_SUPERVISOR_PID"
    DIRECT_SUPERVISOR_PID=""

    # The give-up record persists after the supervisor exits and removes its pids.
    run cat "${LOG_DIR}/supervisor.state"
    assert_output --partial "gave_up_storm"
    [ ! -s "${LOG_DIR}/supervisor.pid" ]

    run "$MANAGER" --status
    assert_success
    assert_output --partial "STATUS: stopped (supervisor gave up after restart storm at "
}

@test "supervisor.state records running across start and restart and is cleaned on stop" {
    run "$MANAGER" --start
    assert_manager_success
    wait_for_file "${LOG_DIR}/supervisor.state"
    run cat "${LOG_DIR}/supervisor.state"
    assert_output --partial "running"
    [ "$(stat -c '%a' "${LOG_DIR}/supervisor.state")" = "600" ]

    run "$MANAGER" --restart
    assert_manager_success
    wait_for_ready
    [ -f "${LOG_DIR}/supervisor.state" ]
    run cat "${LOG_DIR}/supervisor.state"
    assert_output --partial "running"

    run "$MANAGER" --stop
    assert_success
    [ ! -e "${LOG_DIR}/supervisor.state" ]

    # A clean stop is indistinguishable from never-started: plain "stopped".
    run "$MANAGER" --status
    assert_success
    assert_output "STATUS: stopped"
}

@test "unsafe symlink supervisor.state target is rejected by lifecycle preflight" {
    mkdir -p "$LOG_DIR"
    local referent="${SHIM_TEST_ROOT}/state-referent"
    printf 'state-referent-unchanged\n' > "$referent"
    ln -s "$referent" "${LOG_DIR}/supervisor.state"
    run "$MANAGER" __rotate_logs
    assert_failure
    assert_output --partial "refusing unsafe shim state target"
    grep -Fx 'state-referent-unchanged' "$referent"
    [ -L "${LOG_DIR}/supervisor.state" ]
}

@test "unsafe symlink quota_state.json target is rejected by lifecycle preflight" {
    # v1.3.3 (A2-R7): quota_state.json — a shim-written install-shared state file —
    # is now in state_targets_are_safe()'s hijack checklist. A symlink must be
    # refused without touching its referent.
    mkdir -p "$LOG_DIR"
    local referent="${SHIM_TEST_ROOT}/quota-referent"
    printf 'quota-referent-unchanged\n' > "$referent"
    ln -s "$referent" "${LOG_DIR}/quota_state.json"
    run "$MANAGER" __rotate_logs
    assert_failure
    assert_output --partial "refusing unsafe shim state target"
    grep -Fx 'quota-referent-unchanged' "$referent"
    [ -L "${LOG_DIR}/quota_state.json" ]
}

@test "non-regular quota_state.json target is rejected by lifecycle preflight" {
    # The named-target check refuses any existing non-regular file, not just
    # symlinks; a directory planted at the quota_state.json path is rejected.
    mkdir -p "$LOG_DIR"
    mkdir "${LOG_DIR}/quota_state.json"
    run "$MANAGER" __rotate_logs
    assert_failure
    assert_output --partial "refusing unsafe shim state target"
    [ -d "${LOG_DIR}/quota_state.json" ]
}

# --- D4: --auto config footgun ----------------------------------------------

@test "auto warns and stays boot-safe on an unrecognized DAAF_PROVIDER_SHIM value" {
    export DAAF_PROVIDER_SHIM=chatgpt
    run "$MANAGER" --auto
    assert_success
    assert_output --partial "WARNING: DAAF_PROVIDER_SHIM=chatgpt is not a recognized"
    assert_output --partial 'accepted value is "openai"'
    assert_output --partial "SHIM_AUTO_SKIPPED status=skipped reason=unrecognized_provider_shim observed=chatgpt accepted=openai"
    [ "$(grep -c 'MANAGER SHIM_AUTO_SKIPPED status=skipped' "$LOG_FILE")" -eq 1 ]
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
    [ ! -e "${LOG_DIR}/supervisor.pid" ]
}

@test "auto sanitizes an injecting DAAF_PROVIDER_SHIM value into a single log token" {
    export DAAF_PROVIDER_SHIM='chatgpt bogus'
    run "$MANAGER" --auto
    assert_success
    # The space is neutralized so the value cannot forge a second log field.
    assert_output --partial "observed=chatgpt_bogus accepted=openai"
    [ "$(grep -c 'MANAGER SHIM_AUTO_SKIPPED status=skipped' "$LOG_FILE")" -eq 1 ]
}

@test "auto is a silent no-op when DAAF_PROVIDER_SHIM is unset" {
    unset DAAF_PROVIDER_SHIM
    run "$MANAGER" --auto
    assert_success
    assert_output ""
    [ ! -e "$LOG_FILE" ]
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
}

@test "auto is a silent no-op when DAAF_PROVIDER_SHIM is empty" {
    export DAAF_PROVIDER_SHIM=""
    run "$MANAGER" --auto
    assert_success
    assert_output ""
    [ ! -e "$LOG_FILE" ]
    [ "$(count_exact_arg_processes "${SHIM_TEST_ROOT}/anthropic_openai_shim.py")" -eq 0 ]
}
