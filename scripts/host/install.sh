#!/usr/bin/env bash
# ============================================================================
# DAAF One-Line Installer (macOS / Linux)
# ============================================================================
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/install.sh | bash
#
# What this script does:
#   1. Creates a minimal build directory (~5 KB)
#   2. Downloads the Dockerfile, docker-compose.yml, and convenience scripts
#   3. Builds the Docker image (Python, data science stack, Claude Code)
#   4. Clones the full DAAF repository into the Docker volume
#   5. Prints instructions for first launch
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - Internet connection
#
# Supports DAAF_TEST_MODE=1 for test framework sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

set -euo pipefail

# Interactivity detection: use /dev/tty instead of stdin (fd 0).
# When users run `curl ... | bash`, stdin is the pipe -- but the user's
# terminal is still available at /dev/tty. CI environments lack a real
# terminal entirely.
#
# DAAF_NESTED is separate: it suppresses the exit prompt (so nested
# scripts don't double-pause) but does NOT suppress interactive prompts.
IS_INTERACTIVE=false
if [ -z "${CI:-}" ] && [ -c /dev/tty ] && [ -t 1 ]; then
    IS_INTERACTIVE=true
fi

# Pause before exit so the user can review output.
# Suppressed by DAAF_NESTED (to avoid double-pause when called from
# another script like test_migration.sh).
if [ "${IS_INTERACTIVE}" = "true" ] && [ -z "${DAAF_NESTED:-}" ]; then
    trap 'echo ""; read -r -p "Press Enter to continue: " < /dev/tty' EXIT
fi

# --- Configuration ---
REPO="DAAF-Contribution-Community/daaf"
BRANCH="${DAAF_BRANCH:-main}"
RAW_BASE="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
INSTALL_DIR="$(pwd)/daaf-docker"

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate external commands (Docker, curl) for CI
# cross-platform smoke testing without a Docker daemon.
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    # Match patterns are space/flag-anchored so they cannot collide with the
    # random mktemp INSTALL_DIR path embedded in "$*". The former
    # *"compose"*"up"* / *"compose"*"build"* substring forms were functionally
    # immune here (every real arm returns 0), but are hardened to the same
    # path-proof style used in tests/bash/install.bats and daaf.bats for
    # consistency and future-proofing (a "$*" containing "up" or "build" in its
    # temp path can no longer route to the wrong arm).
    docker() {
        case "$*" in
            "info") return 0 ;;
            *"volume inspect"*) return 1 ;;
            *"buildx inspect"*) return 1 ;;
            *"buildx create"*) return 0 ;;
            *" build --progress"*) return 0 ;;
            *" up -d"*) return 0 ;;
            *"exec -T daaf-docker true"*) return 0 ;;
            *"git clone"*) return 0 ;;
            *"bash -c"*) return 0 ;;
            *"test -f /daaf/CLAUDE.md"*) return 0 ;;
            *)
                echo "[DRY-RUN] docker $*" >&2
                return 0
                ;;
        esac
    }
    curl() {
        # Dry-run is fully non-writing: print the [DRY-RUN] line and succeed
        # WITHOUT creating any files or directories. The former mock touched an
        # empty stub for each -o target, which (with INSTALL_DIR under the
        # caller's CWD) leaked zero-byte stubs on disk. The mkdir + explicit
        # chmod sites below are gated so the full flow still walks end-to-end.
        echo "[DRY-RUN] curl $*" >&2
        return 0
    }
fi

# --- Test Mode Guard ---
# When sourced for testing, define functions but skip execution.
# Usage: DAAF_TEST_MODE=1 source scripts/host/install.sh
if [ "${DAAF_TEST_MODE:-}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi

echo ""
echo "=========================================="
echo "  DAAF Installer"
echo "=========================================="
echo ""
echo "Branch: ${BRANCH}"
echo ""

# --- Preflight checks ---
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is either not installed or not configured properly in your system PATH to allow it to be used from Terminal."
    echo "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "ERROR: Docker Desktop does not seem to be running. Please start Docker Desktop on your computer and try again."
    exit 1
fi

# --- Check for existing installation ---
# Derive the project-prefixed data volume name so multi-instance installs
# (DAAF_PROJECT_NAME set) are detected correctly. The value comes from the shell
# environment first, else DAAF_PROJECT_NAME in the existing install's
# environment_settings.txt, else the "daaf" default (byte-for-byte identical to
# the former hardcoded "daaf_daaf-data"). Parse only that one key (never `source`
# -- the file holds API keys); shell env wins; CR stripped; Bash 3.2 safe.
INSTALL_PROJECT_NAME="${DAAF_PROJECT_NAME:-}"
if [ -z "${INSTALL_PROJECT_NAME}" ] && [ -f "${INSTALL_DIR}/environment_settings.txt" ]; then
    while IFS= read -r _line || [ -n "${_line}" ]; do
        _line="$(printf '%s' "${_line}" | tr -d '\r')"
        case "${_line}" in
            DAAF_PROJECT_NAME=*)
                INSTALL_PROJECT_NAME="${_line#*=}"
                case "${INSTALL_PROJECT_NAME}" in
                    \"*\") INSTALL_PROJECT_NAME="${INSTALL_PROJECT_NAME#\"}"; INSTALL_PROJECT_NAME="${INSTALL_PROJECT_NAME%\"}" ;;
                    \'*\') INSTALL_PROJECT_NAME="${INSTALL_PROJECT_NAME#\'}"; INSTALL_PROJECT_NAME="${INSTALL_PROJECT_NAME%\'}" ;;
                esac
                break
                ;;
        esac
    done < "${INSTALL_DIR}/environment_settings.txt"
fi
DATA_VOLUME_NAME="${INSTALL_PROJECT_NAME:-daaf}_daaf-data"

# --- Bridge the DAAF_DEV build flag into the environment ---
# Unlike DAAF_PROJECT_NAME above (only needed locally to derive the volume name;
# the compose project name comes from the file's `name:` key), the build flag
# must be EXPORTED so `docker compose build` below sees it and forwards it as
# `--build-arg DAAF_DEV=${DAAF_DEV:-0}`. Parse only that one key from the
# just-downloaded environment_settings.txt (never `source` -- the file holds API
# keys); shell env wins; CR stripped; Bash 3.2 safe. Absent file / absent key =
# the flag stays unset, so its build arg defaults to 0 (standard build).
if [ -z "${DAAF_DEV:-}" ] && [ -f "${INSTALL_DIR}/environment_settings.txt" ]; then
    while IFS= read -r _line || [ -n "${_line}" ]; do
        _line="$(printf '%s' "${_line}" | tr -d '\r')"
        case "${_line}" in
            DAAF_DEV=*)
                _dev_val="${_line#*=}"
                case "${_dev_val}" in
                    \"*\") _dev_val="${_dev_val#\"}"; _dev_val="${_dev_val%\"}" ;;
                    \'*\') _dev_val="${_dev_val#\'}"; _dev_val="${_dev_val%\'}" ;;
                esac
                export DAAF_DEV="${_dev_val}"
                break
                ;;
        esac
    done < "${INSTALL_DIR}/environment_settings.txt"
fi

if [ -f "${INSTALL_DIR}/docker-compose.yml" ]; then
    if docker volume inspect "${DATA_VOLUME_NAME}" &>/dev/null; then
        # Volume exists -- this is a completed or substantially completed installation
        if [ "${DAAF_FORCE_REINSTALL:-}" = "1" ]; then
            echo "NOTE: Existing installation detected. Proceeding with re-install (DAAF_FORCE_REINSTALL=1)."
            echo ""
        else
            echo "WARNING: An existing DAAF installation was detected."
            echo ""
            echo "Re-running the installer will overwrite framework files (CLAUDE.md, skills,"
            echo "agents, templates) and local git history. Your research data will NOT be"
            echo "deleted, but a backup is strongly recommended."
            echo ""
            echo "To update DAAF instead (recommended -- preserves local changes):"
            echo "  cd ${INSTALL_DIR}"
            echo "  bash update_daaf.sh"
            echo ""
            echo "To force a fresh re-install, set DAAF_FORCE_REINSTALL=1:"
            echo "  DAAF_FORCE_REINSTALL=1 bash -c \"\$(curl -fsSL ${RAW_BASE}/scripts/host/install.sh)\""
            echo ""
            exit 1
        fi
    else
        echo "NOTE: A previous install attempt was detected but appears incomplete."
        echo "      Proceeding with a fresh install."
        echo ""
    fi
fi

# --- Create minimal build directory ---
echo "[1/4] Creating initial directory for installation files at ${INSTALL_DIR} ..."
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    echo "[DRY-RUN] Would create install directory: ${INSTALL_DIR}"
else
    mkdir -p "${INSTALL_DIR}"
fi

# --- Download build-context and utility files ---
echo "[2/4] Downloading installation files ..."
if ! curl -fsSL "${RAW_BASE}/Dockerfile"                          -o "${INSTALL_DIR}/Dockerfile" ||
   ! curl -fsSL "${RAW_BASE}/docker-compose.yml"                   -o "${INSTALL_DIR}/docker-compose.yml" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/daaf.sh"                 -o "${INSTALL_DIR}/daaf.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/daaf_lib.sh"             -o "${INSTALL_DIR}/daaf_lib.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/run_daaf.sh"             -o "${INSTALL_DIR}/run_daaf.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/backup_daaf.sh"          -o "${INSTALL_DIR}/backup_daaf.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/restore_from_backup.sh"  -o "${INSTALL_DIR}/restore_from_backup.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/rebuild_daaf.sh"         -o "${INSTALL_DIR}/rebuild_daaf.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/update_daaf.sh"          -o "${INSTALL_DIR}/update_daaf.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/view_logs.sh"            -o "${INSTALL_DIR}/view_logs.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/view_notebooks.sh"      -o "${INSTALL_DIR}/view_notebooks.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/view_quarto.sh"          -o "${INSTALL_DIR}/view_quarto.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/run_vscode.sh"           -o "${INSTALL_DIR}/run_vscode.sh" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/environment_settings_example.txt" -o "${INSTALL_DIR}/environment_settings_example.txt" ||
   ! curl -fsSL "${RAW_BASE}/scripts/host/README.txt"                      -o "${INSTALL_DIR}/README.txt"; then
    echo ""
    echo "ERROR: Failed to download installation files from branch '${BRANCH}'."
    echo "Please verify that the branch name is correct and that you have an internet connection."
    echo "You can check available branches at: https://github.com/${REPO}/branches"
    exit 1
fi
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    # Dry-run downloaded nothing (the curl mock no longer writes stubs), so there
    # are no files to chmod; an unguarded chmod on the missing explicit paths
    # would hard-fail under `set -e`.
    echo "[DRY-RUN] Would make downloaded host scripts executable (chmod +x)"
else
    chmod +x "${INSTALL_DIR}/daaf.sh" "${INSTALL_DIR}/daaf_lib.sh" "${INSTALL_DIR}/run_daaf.sh" "${INSTALL_DIR}/backup_daaf.sh" "${INSTALL_DIR}/restore_from_backup.sh" "${INSTALL_DIR}/rebuild_daaf.sh" "${INSTALL_DIR}/update_daaf.sh" "${INSTALL_DIR}/view_logs.sh" "${INSTALL_DIR}/view_notebooks.sh" "${INSTALL_DIR}/view_quarto.sh" "${INSTALL_DIR}/run_vscode.sh"
fi

# --- Apple Silicon (arm64) build-time notice ---
# On the Ubuntu noble base, arm64 gets P3M pre-built R binaries (same as x86_64),
# so Apple Silicon no longer compiles R packages from source. The first build is
# still a sizable one-time download, but there is no arm64-specific source-compile
# penalty. A brief heads-up keeps the quiet download/install phase from looking
# like a hang.
DAAF_ARCH="$(uname -m 2>/dev/null || echo unknown)"
if [ "${DAAF_ARCH}" = "arm64" ] || [ "${DAAF_ARCH}" = "aarch64" ]; then
    echo ""
    echo "NOTE: arm64 detected (Apple Silicon or other ARM64 host). The first build"
    echo "      downloads a large stack of Python and R packages, so it takes a while"
    echo "      with some quiet stretches -- this is normal, not a hang. arm64 now"
    echo "      installs pre-built R binaries (no source compilation)."
    echo ""
fi

# --- Optional diagnostic builder (DAAF_DIAG_BUILD=1) ---
# BuildKit clips each step's log output (by size AND by rate), and Docker
# Desktop's DEFAULT builder does not let those limits be raised. The only
# mechanism is a custom docker-container builder with larger
# BUILDKIT_STEP_LOG_MAX_SIZE / _MAX_SPEED, selected via BUILDX_BUILDER. That
# builder has real costs (separate build cache; the built image must be loaded
# back into the Docker image store), so it is opt-in only. Fail-open: any failure
# creating/inspecting it falls back to the default builder.
DIAG_BUILDER_SELECTED=0
if [ "${DAAF_DIAG_BUILD:-}" = "1" ]; then
    if docker buildx inspect daaf-diag-builder >/dev/null 2>&1; then
        DIAG_BUILDER_SELECTED=1
        echo "NOTE: Reusing existing diagnostic buildx builder 'daaf-diag-builder' (raised step-log limits)."
    elif docker buildx create --name daaf-diag-builder --driver docker-container \
            --driver-opt env.BUILDKIT_STEP_LOG_MAX_SIZE=16777216 \
            --driver-opt env.BUILDKIT_STEP_LOG_MAX_SPEED=10485760 >/dev/null 2>&1; then
        DIAG_BUILDER_SELECTED=1
        echo "NOTE: Created diagnostic buildx builder 'daaf-diag-builder' (raised step-log limits)."
    else
        echo "NOTE: DAAF_DIAG_BUILD=1 set, but the diagnostic buildx builder could not be"
        echo "      created. Falling back to the default builder (build logs may be clipped)."
    fi
    if [ "${DIAG_BUILDER_SELECTED}" = "1" ]; then
        echo "      This build uses a separate build cache (slower first run); the image is"
        echo "      loaded back into Docker when the build completes."
        echo ""
    fi
fi

# --- Build the Docker image ---
echo "[3/4] Building Docker image (this may take a few minutes on first run since there are a lot of Python libraries to install)..."
# Project name is set declaratively via the top-level "name: daaf" key in
# docker-compose.yml -- no need to set COMPOSE_PROJECT_NAME here.
# Build and start are split into two commands so that --progress plain can be
# applied to the build step (where it is universally supported) without relying
# on `docker compose up --progress`, which is rejected as "unknown flag" on
# Docker Compose versions prior to ~v2.27.
#
# The BUILDX_BUILDER prefix is applied ONLY on the diagnostic path. On the normal
# path the command must NOT reference BUILDX_BUILDER at all: setting it to the
# empty string still EXPORTS it (set-but-empty, not unset), which relies on
# undocumented docker empty==default semantics and would clobber a user's own
# pre-exported BUILDX_BUILDER. Two explicit branches avoid that.
# `set -e` is active: capture the exit code with `|| BUILD_EXIT=$?` so a non-zero
# build does not abort the script before the error message below can print.
BUILD_EXIT=0
if [ "${DIAG_BUILDER_SELECTED}" = "1" ]; then
    BUILDX_BUILDER="daaf-diag-builder" docker compose -f "${INSTALL_DIR}/docker-compose.yml" build --progress plain || BUILD_EXIT=$?
else
    docker compose -f "${INSTALL_DIR}/docker-compose.yml" build --progress plain || BUILD_EXIT=$?
fi
if [ "${BUILD_EXIT}" -ne 0 ]; then
    echo ""
    echo "ERROR: Docker image build failed. Check the output above for details."
    echo "You can safely re-run this installer to retry (set DAAF_FORCE_REINSTALL=1 if prompted)."
    echo "If the output above contains a line like '[output clipped, log limit 2MiB reached]'"
    echo "(the exact limit varies by Docker version), re-run with DAAF_DIAG_BUILD=1 for"
    echo "unclipped build logs:"
    echo "  DAAF_DIAG_BUILD=1 bash -c \"\$(curl -fsSL ${RAW_BASE}/scripts/host/install.sh)\""
    exit 1
fi
echo "Starting container..."
if ! docker compose -f "${INSTALL_DIR}/docker-compose.yml" up -d; then
    echo ""
    echo "ERROR: Failed to start the Docker container after build. Check the output above for details."
    echo "You can safely re-run this installer to retry (set DAAF_FORCE_REINSTALL=1 if prompted)."
    exit 1
fi

# --- Wait for container to be ready ---
echo "      Waiting for container to be ready ..."
RETRIES=0
MAX_RETRIES=30
READY_LOG=$(mktemp)
until docker compose -f "${INSTALL_DIR}/docker-compose.yml" exec -T daaf-docker true </dev/null 2>>"$READY_LOG"; do
    RETRIES=$((RETRIES + 1))
    if [ "${RETRIES}" -ge "${MAX_RETRIES}" ]; then
        echo "ERROR: Container did not become ready within 60 seconds." >&2
        if [ -s "$READY_LOG" ]; then
            echo "  Docker reported:" >&2
            tail -5 "$READY_LOG" | sed 's/^/    /' >&2
            echo "" >&2
        fi
        echo "Check Docker Desktop for errors, then retry with:" >&2
        echo "  docker compose -f ${INSTALL_DIR}/docker-compose.yml up -d" >&2
        rm -f "$READY_LOG"
        exit 1
    fi
    sleep 2
done
rm -f "$READY_LOG"

# --- Clone the full repository into the Docker volume ---
echo "[4/4] Cloning DAAF repository files into the Docker container ..."

# On reinstall, remove the existing .git directory first.  Git pack files are
# mode 444 (read-only by design) which prevents cp -a from overwriting them.
# The research/ folder is preserved -- only framework files are replaced.
docker compose -f "${INSTALL_DIR}/docker-compose.yml" exec -T daaf-docker \
    bash -c 'rm -rf /daaf/.git /daaf/.pre-commit-config.yaml /daaf/.gitignore /daaf/.claudeignore 2>/dev/null; true' </dev/null \
    || true

if ! docker compose -f "${INSTALL_DIR}/docker-compose.yml" exec -T daaf-docker \
    git clone --depth 1 -b "${BRANCH}" "https://github.com/${REPO}.git" /tmp/daaf-clone </dev/null; then
    echo ""
    echo "ERROR: Failed to clone the DAAF repository."
    echo "The Docker image was built successfully, but the repository could not be downloaded."
    echo "Check your internet connection and retry with:"
    echo "  docker compose -f ${INSTALL_DIR}/docker-compose.yml exec -T daaf-docker \\"
    echo "    git clone --depth 1 -b ${BRANCH} https://github.com/${REPO}.git /tmp/daaf-clone"
    echo "  docker compose -f ${INSTALL_DIR}/docker-compose.yml exec -T daaf-docker \\"
    echo "    bash -c 'cp -a /tmp/daaf-clone/. /daaf/ && rm -rf /tmp/daaf-clone'"
    echo "You can also safely re-run this installer to retry from scratch (set DAAF_FORCE_REINSTALL=1 if prompted)."
    exit 1
fi

if ! docker compose -f "${INSTALL_DIR}/docker-compose.yml" exec -T daaf-docker \
    bash -c 'cp -a /tmp/daaf-clone/. /daaf/ && rm -rf /tmp/daaf-clone' </dev/null; then
    echo ""
    echo "ERROR: Failed to copy repository files into the container."
    echo "The clone succeeded, but copying to /daaf/ failed (possibly a permissions issue)."
    echo "You can retry manually with:"
    echo "  docker compose -f ${INSTALL_DIR}/docker-compose.yml exec -T daaf-docker \\"
    echo "    bash -c 'cp -a /tmp/daaf-clone/. /daaf/ && rm -rf /tmp/daaf-clone'"
    echo "You can also safely re-run this installer to retry from scratch (set DAAF_FORCE_REINSTALL=1 if prompted)."
    exit 1
fi

# --- Verify DAAF files are present ---
if ! docker compose -f "${INSTALL_DIR}/docker-compose.yml" exec -T daaf-docker \
    test -f /daaf/CLAUDE.md </dev/null 2>/dev/null; then
    echo ""
    echo "WARNING: Installation may be incomplete -- /daaf/CLAUDE.md was not found in the container."
    echo "The Docker image was built, but the repository files may not have copied correctly."
    echo "You can try cloning manually inside the container:"
    echo "  cd ${INSTALL_DIR}"
    echo "  docker compose exec daaf-docker bash"
    echo "  git clone --depth 1 -b ${BRANCH} https://github.com/${REPO}.git /tmp/daaf-clone"
    echo "  cp -a /tmp/daaf-clone/. /daaf/ && rm -rf /tmp/daaf-clone"
    exit 1
fi

# --- Settings-File Key Upsert (inlined from daaf_lib.sh) ---
# Insert/update a single KEY=value line in the seeded environment_settings.txt.
# This is an INLINE COPY of daaf_lib.sh upsert_settings_key: the installer is a
# deliberately standalone `curl | bash` script that does not source daaf_lib
# (mirroring its existing inline settings parsers above), so the write helper is
# carried inline for the same reason. Semantics, placement rules, atomicity,
# encoding, DRY-RUN gating and Bash 3.2 safety are identical to the library
# version -- see daaf_lib.sh for the full annotation.
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

    local -a lines=()
    local _l
    while IFS= read -r _l || [ -n "${_l}" ]; do
        _l="${_l%$'\r'}"
        lines+=("${_l}")
    done < "${file}"

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
        if [ "${#out[@]}" -gt 0 ] && [ -n "${out[$(( ${#out[@]} - 1 ))]}" ]; then
            out+=("")
        fi
        out+=("# Added by DAAF on $(date +%Y-%m-%d)")
        out+=("${new_line}")
        action="appended (new)"
    fi

    if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
        echo "[DRY-RUN] upsert_settings_key would write ${file}: ${action}"
        echo "[DRY-RUN]   line: ${new_line}"
        return 0
    fi

    if [ -n "${backup_suffix}" ] && [ ! -f "${file}${backup_suffix}" ]; then
        if ! cp -p "${file}" "${file}${backup_suffix}"; then
            echo "upsert_settings_key: ERROR: backup failed: ${file}${backup_suffix}" >&2
            return 1
        fi
    fi

    local payload="" ln
    for ln in "${out[@]}"; do
        payload="${payload}${ln}"$'\n'
    done

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

# --- Seed environment_settings.txt from process-env DAAF_* variables ---
# A fresh install can carry the user's DAAF_* choices (project name, ports, dev
# flag, branch) straight into a new environment_settings.txt so future launches
# and updates pick them up without re-exporting. We copy the just-downloaded
# example template and upsert each seedable key that is present (non-empty) in
# the process environment. Binding rules:
#   - Never overwrite an existing environment_settings.txt: a reinstall preserves
#     the user's real API keys; env vars are then used for THIS install only.
#   - Never fail the install: every mutation is composed under `if` so a seeding
#     failure (set -e is active) degrades to a printed manual-fallback note.
#   - Never persist a DAAF_BRANCH that is a version tag: a persisted tag would
#     break every future update (see update_daaf.sh). Tag-vs-branch is detected
#     from the container clone -- `git clone -b <ref>` leaves HEAD on a symbolic
#     ref for a branch and detached for a tag, so `symbolic-ref -q HEAD` is a
#     cheap, local (no-network) discriminator. If DAAF_BRANCH is unset it is
#     simply not seeded.
#   - Always print an outcome note (keys seeded / file preserved / seeding failed
#     with manual instructions).
#   - Fully DAAF_DRY_RUN gated: prints intent and touches nothing (HSM5).
SEED_SRC="${INSTALL_DIR}/environment_settings_example.txt"
SEED_DST="${INSTALL_DIR}/environment_settings.txt"

if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    echo ""
    echo "[DRY-RUN] Would seed ${SEED_DST} from process-env DAAF_* variables (if absent, never overwriting an existing file)."
elif [ -f "${SEED_DST}" ]; then
    echo ""
    echo "NOTE: An existing environment_settings.txt was found and left untouched."
    echo "      Any DAAF_* environment variables you set were used for THIS install"
    echo "      only; your existing settings file was preserved."
elif [ ! -f "${SEED_SRC}" ]; then
    echo ""
    echo "NOTE: Could not seed environment_settings.txt (the example template was"
    echo "      not found). To configure settings manually:"
    echo "        cd ${INSTALL_DIR}"
    echo "        cp environment_settings_example.txt environment_settings.txt"
    echo "        # then edit environment_settings.txt with your keys and settings"
else
    # Determine whether DAAF_BRANCH (if set) is a branch or a version tag.
    # Three outcomes are distinguished so a docker-exec failure is never
    # misreported as "is a tag" (a false tag claim + a silently dropped seed):
    #   1. exec healthy + attached HEAD (symbolic-ref succeeds) -> branch, seed
    #   2. exec healthy + detached HEAD (symbolic-ref fails)    -> tag, skip w/ note
    #   3. exec/probe failure (health probe fails)             -> cannot verify, skip
    # A cheap health probe (`git rev-parse HEAD`) runs first over the SAME exec
    # path; only if it succeeds is a subsequent symbolic-ref failure trusted as
    # "detached HEAD = tag". Both probes are local (no network) and this whole
    # else-arm is skipped under DAAF_DRY_RUN, so it stays dry-run inert.
    SEED_BRANCH_OK=0
    SEED_BRANCH_SKIP_TAG=0
    SEED_BRANCH_UNVERIFIED=0
    if [ -n "${DAAF_BRANCH:-}" ]; then
        if docker compose -f "${INSTALL_DIR}/docker-compose.yml" exec -T daaf-docker \
            git -C /daaf rev-parse HEAD </dev/null >/dev/null 2>&1; then
            if docker compose -f "${INSTALL_DIR}/docker-compose.yml" exec -T daaf-docker \
                git -C /daaf symbolic-ref -q HEAD </dev/null >/dev/null 2>&1; then
                SEED_BRANCH_OK=1
            else
                SEED_BRANCH_SKIP_TAG=1
            fi
        else
            SEED_BRANCH_UNVERIFIED=1
        fi
    fi

    SEED_OK=1
    SEED_KEYS=""
    if cp "${SEED_SRC}" "${SEED_DST}"; then
        for _k in DAAF_PROJECT_NAME DAAF_PORT_MARIMO DAAF_PORT_LOGVIEWER DAAF_PORT_VSCODE DAAF_DEV DAAF_BRANCH; do
            _v="${!_k:-}"
            [ -n "${_v}" ] || continue
            if [ "${_k}" = "DAAF_BRANCH" ] && [ "${SEED_BRANCH_OK}" != "1" ]; then
                continue
            fi
            if upsert_settings_key "${SEED_DST}" "${_k}" "${_v}" "if-absent" >/dev/null 2>&1; then
                SEED_KEYS="${SEED_KEYS} ${_k}"
            else
                SEED_OK=0
            fi
        done
    else
        SEED_OK=0
    fi

    echo ""
    if [ "${SEED_OK}" = "1" ]; then
        if [ -n "${SEED_KEYS}" ]; then
            echo "NOTE: Created environment_settings.txt and seeded these values from your"
            echo "      environment:${SEED_KEYS}"
        else
            echo "NOTE: Created environment_settings.txt from the template (no DAAF_* values"
            echo "      were set in your environment to seed)."
        fi
        if [ "${SEED_BRANCH_SKIP_TAG}" = "1" ]; then
            echo "      DAAF_BRANCH was NOT seeded because '${DAAF_BRANCH}' is a version tag;"
            echo "      persisting a tag would break future updates. Ongoing updates track the"
            echo "      default branch. Edit environment_settings.txt to pin a branch if desired."
        fi
        if [ "${SEED_BRANCH_UNVERIFIED}" = "1" ]; then
            echo "      DAAF_BRANCH was NOT seeded: could not verify whether '${DAAF_BRANCH}' is"
            echo "      a branch (the container clone was not reachable). Add DAAF_BRANCH to"
            echo "      environment_settings.txt manually if desired."
        fi
        echo "      Review it and add any data source API keys before your next launch."
    else
        echo "NOTE: Automatic settings seeding did not fully complete, so your other"
        echo "      installation steps finished but environment_settings.txt may be absent"
        echo "      or partial. To configure it manually:"
        echo "        cd ${INSTALL_DIR}"
        echo "        cp environment_settings_example.txt environment_settings.txt"
        echo "        # then edit environment_settings.txt with your keys and settings"
    fi
fi

echo ""
echo "=========================================="
echo "  Installation complete!"
echo "=========================================="
echo ""
echo "To start using DAAF:"
echo ""
echo "  1. Navigate to the install directory and launch the DAAF Control Panel:"
echo "     cd ${INSTALL_DIR}"
echo "     bash daaf.sh"
echo ""
echo "     The Control Panel provides a status dashboard, service management,"
echo "     and all DAAF operations in one place."
echo ""
echo "  2. On first launch, you'll be asked to authenticate with your Anthropic account."
echo ""
echo "  3. Configure Claude Code (required):"
echo "     - Type /config and set:"
echo "         Auto-compact  -> False"
echo "         Verbose output -> True"
echo "     - Press ESC to return to the chat"
echo ""
echo "Available scripts (in ${INSTALL_DIR}):"
echo "  bash daaf.sh                    DAAF Control Panel (recommended)"
echo "  bash run_daaf.sh               Launch Claude Code directly"
echo "  bash run_daaf.sh bash          Enter the container shell"
echo "  bash backup_daaf.sh            Back up the Docker volume to a dated folder"
echo "  bash restore_from_backup.sh    Restore from a backup"
echo "  bash update_daaf.sh            Check for and apply DAAF updates"
echo "  bash rebuild_daaf.sh           Copy build files from container and rebuild image"
echo "  bash view_logs.sh              Browse session logs in your browser"
echo "  bash view_notebooks.sh         Browse and edit marimo notebooks in your browser"
echo "  bash view_quarto.sh            Render and view Quarto notebooks in your browser"
echo "  bash run_vscode.sh             Open VS Code in your browser (code-server)"
echo ""
echo "To set up data source API keys (optional):"
echo "  cp environment_settings_example.txt environment_settings.txt   Copy the template"
echo "  Edit environment_settings.txt with your keys, then restart with: bash run_daaf.sh"
echo ""
echo "Manual alternative (if you prefer individual commands):"
echo "  docker compose exec daaf-docker bash   # enter the container"
echo "  claude                                  # launch Claude Code"
echo ""
echo "For day-to-day usage and more, see:"
echo "  https://github.com/${REPO}/blob/${BRANCH}/user_reference/01_installation_and_quickstart.md"
echo ""
echo "Keep this directory -- it contains the Dockerfile needed for rebuilds."
echo ""
echo "To get started using any of those scripts, enter the install directory first:"
echo "  cd daaf-docker"
echo ""
