#!/usr/bin/env bash
# ============================================================================
# DAAF Shared Function Library
# ============================================================================
# Reusable functions for DAAF host scripts. Source this file — do not execute
# it directly.
#
# Usage:
#   DAAF_LIB_DIR="$(cd "$(dirname "$0")" && pwd)"
#   source "${DAAF_LIB_DIR}/daaf_lib.sh"
#
# Functions provided:
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

# --- Color Setup ---
# Populate global color variables for terminal output.
# Respects NO_COLOR (https://no-color.org/) and non-TTY contexts.
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
# Always returns 0 — failure to open is never fatal.
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

    # No opener available — silent fallback
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

    # In dry-run mode, consult MOCK_PORT_RESPONSES instead of Docker
    if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
        if echo "${MOCK_PORT_RESPONSES:-}" | grep -q "${port}:yes"; then
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
# Sets CONTAINER_RUNNING=true on success, false on failure.
ensure_container() {
    # In dry-run mode, just pretend the container is running
    if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
        CONTAINER_RUNNING=true
        return 0
    fi

    local running
    running=$(docker compose ps --status running --format '{{.Name}}' 2>/dev/null | grep -c "daaf-docker" || true)

    if [ "${running}" -gt 0 ]; then
        CONTAINER_RUNNING=true
        return 0
    fi

    # Attempt to start the container
    if docker compose up -d 2>/dev/null; then
        CONTAINER_RUNNING=true
        return 0
    fi

    CONTAINER_RUNNING=false
    return 1
}
