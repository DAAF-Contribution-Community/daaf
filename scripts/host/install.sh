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
            # The exact-name volume list (daaf_volume_state below) succeeds and
            # lists nothing: no DAAF volume exists, so dry-run walks a fresh install.
            *"volume ls"*) return 0 ;;
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

# --- Volume existence probe (used by the existing-install check below) ---
# Prints one word for Docker volume $1: present | absent | unknown.
# `docker volume inspect` exit 0 = present. A FAILED inspect is not read as
# "absent" on its own: the exact-name list (`docker volume ls -q`, stdout only,
# whole-line match) decides, and a list that fails too is "unknown" -- the
# caller then refuses rather than risk installing over a live installation.
# No Docker error text is matched: its wording varies by Docker version, and the
# install.ps1 twin cannot read it reliably (Windows PowerShell 5.1 drops native
# stderr under SilentlyContinue), so both twins classify by exit code and stdout
# only. No pipe: under pipefail a SIGPIPE'd `printf | grep -q` can read as "no
# match". Defined before the test-mode guard so tests can source and call it.
daaf_volume_state() {
    local names nl
    if docker volume inspect "$1" >/dev/null 2>&1; then
        echo "present"
        return 0
    fi
    if ! names="$(docker volume ls -q 2>/dev/null </dev/null)"; then
        echo "unknown"
        return 0
    fi
    nl=$'\n'
    case "${nl}${names}${nl}" in
        *"${nl}$1${nl}"*) echo "present" ;;
        *) echo "absent" ;;
    esac
    return 0
}

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

# --- Bridge the install-time DAAF_* keys from environment_settings.txt ---
# ONE project-name source for the whole run. Docker Compose interpolates
# `name: ${DAAF_PROJECT_NAME:-daaf}`, the `${DAAF_PORT_*}` host ports and the
# DAAF_DEV build arg from the shell environment (or a .env file beside the
# compose file, which the installer never writes), never from
# environment_settings.txt, which feeds only the container's env_file. The
# launchers bridge these keys from the file with load_daaf_settings (daaf_lib.sh);
# the installer does the same here, BEFORE the existing-install check and before
# any compose call, so the volume the check examines, the project and ports
# Compose builds and starts, and the project named by every printed re-install
# or manual `docker compose` command are one value (see "Printed commands carry
# the project" below). (Until 2026-10-11 the file's DAAF_PROJECT_NAME only named the volume the
# check examined and was never exported, so a re-install from a named instance's
# own folder with the shell project unset checked x_daaf-data but built and
# started project 'daaf' on the default ports: reviews 42q I-2 and 43d ISSUE-1 in
# research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/reviews/.)
# Same rules as load_daaf_settings for these five whitelisted keys (that library
# is not available: this script runs standalone via `curl | bash`): never
# `source` the file (it holds API keys); only lines starting at column 0 with a
# known KEY= are read, so comments and every other line are ignored; CR stripped;
# one layer of surrounding quotes stripped; a non-empty shell value wins (a
# repeated key is adopted again only while the value is still empty); Bash 3.2
# safe. The file is read whenever it exists, with or without a docker-compose.yml
# here: the installer never overwrites an existing environment_settings.txt
# (seeding below), so every later launch from this folder uses the file's
# values, and the install must use the same ones.
# Not bridged: DAAF_BRANCH (this run's ref is already fixed in RAW_BASE above)
# and DAAF_DATA_VOLUME_NAME (see DATA_VOLUME_NAME below).
# SYNC NOTE: the key match here is a `case` glob, so it is CASE-SENSITIVE, as in
# load_daaf_settings (a lowercase "daaf_dev=1" line is ignored). The install.ps1
# twin uses -notcontains, which is case-INSENSITIVE, as Import-DaafSettingsFile
# is. Each twin matches its own platform's launcher loader; the twins differ
# from each other on purpose (review 44c N-4 / 44q NIT-3; no behaviour change).
# An existing file that cannot be opened stops the run with a plain ERROR before
# anything is downloaded (review 44q NIT-1), even when the shell already supplies
# every bridged key: the same file is the container's env_file, so the `up -d`
# below could not read it either, and stopping here is simpler and fails safe.
# The open check is daaf_lib.sh's (`true`, not `:`; see there). If the file
# becomes unreadable between this check and the read loop, `set -e` still stops
# the run there (bash's raw error line; nothing has been downloaded yet).
# BRIDGE_ADOPTED lists each key taken from the file, for the NOTE printed below.
BRIDGE_ADOPTED=""
if [ -f "${INSTALL_DIR}/environment_settings.txt" ]; then
    if ! { true < "${INSTALL_DIR}/environment_settings.txt"; } 2>/dev/null; then
        echo "ERROR: Could not read daaf-docker/environment_settings.txt. Check its"
        echo "       permissions, and close any program that has it open, then run the"
        echo "       installer again. Nothing has been downloaded or changed."
        exit 1
    fi
    while IFS= read -r _line || [ -n "${_line}" ]; do
        _line="$(printf '%s' "${_line}" | tr -d '\r')"
        case "${_line}" in
            DAAF_PROJECT_NAME=*|DAAF_PORT_MARIMO=*|DAAF_PORT_LOGVIEWER=*|DAAF_PORT_VSCODE=*|DAAF_DEV=*) ;;
            *) continue ;;
        esac
        _val="${_line#*=}"
        case "${_val}" in
            \"*\") _val="${_val#\"}"; _val="${_val%\"}" ;;
            \'*\') _val="${_val#\'}"; _val="${_val%\'}" ;;
        esac
        case "${_line}" in
            DAAF_PROJECT_NAME=*)   if [ -z "${DAAF_PROJECT_NAME:-}" ];   then export DAAF_PROJECT_NAME="${_val}"; else continue; fi ;;
            DAAF_PORT_MARIMO=*)    if [ -z "${DAAF_PORT_MARIMO:-}" ];    then export DAAF_PORT_MARIMO="${_val}"; else continue; fi ;;
            DAAF_PORT_LOGVIEWER=*) if [ -z "${DAAF_PORT_LOGVIEWER:-}" ]; then export DAAF_PORT_LOGVIEWER="${_val}"; else continue; fi ;;
            DAAF_PORT_VSCODE=*)    if [ -z "${DAAF_PORT_VSCODE:-}" ];    then export DAAF_PORT_VSCODE="${_val}"; else continue; fi ;;
            DAAF_DEV=*)            if [ -z "${DAAF_DEV:-}" ];            then export DAAF_DEV="${_val}"; else continue; fi ;;
        esac
        BRIDGE_ADOPTED="${BRIDGE_ADOPTED} ${_line%%=*}"
    done < "${INSTALL_DIR}/environment_settings.txt"
fi

# --- The target project, derived once, normalized as Docker Compose does ---
# Shell value, else the settings file (bridged above), else "daaf". Everything
# below (the volume checked, every compose call, every printed re-install or
# manual `docker compose` command) uses this value.
# Docker Compose does not use the top-level `name:` verbatim: compose-go's loader
# (loader/loader.go, NormalizeProjectName) lowercases it, keeps only [a-z0-9_-],
# and trims leading '_' and '-' (source quoted from compose-go main, fetched
# 2026-10-11, in review 44q ISSUE-1:
# research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/reviews/44q_quality_review.md).
# So `Work`, `work ` or `x # mine` name the project "work" / "work" / "xmine",
# and the volume "work_daaf-data". The installer computes the same name here and
# uses it for the check, for every printed command, and as the DAAF_PROJECT_NAME
# exported to Compose (which then normalizes an already-normal name to itself,
# so this is equivalent and keeps the environment consistent). That the Compose
# versions DAAF supports (Docker 25+) normalize the same way is an inference
# from that source, not verified per version. ASCII and locale-safe (LC_ALL=C;
# Bash 3.2 has no ${v,,}). A non-ASCII letter is dropped here; Go's Unicode
# lowercasing maps a few (e.g. the Kelvin sign) to ASCII letters it would keep.
# A value that normalizes to nothing (e.g. "___" or "@@") is refused before
# anything is downloaded: what Compose does then is not something to rely on.
# The value is not otherwise validated (review F-b, deferred).
# SYNC NOTE: same rule, messages and NOTE in install.ps1.
PROJECT_NAME_GIVEN="${DAAF_PROJECT_NAME:-}"
INSTALL_TARGET_PROJECT="daaf"
if [ -n "${PROJECT_NAME_GIVEN}" ]; then
    INSTALL_TARGET_PROJECT="$(printf '%s' "${PROJECT_NAME_GIVEN}" | LC_ALL=C tr 'A-Z' 'a-z' | LC_ALL=C tr -cd 'a-z0-9_-')"
    # Trim the leading run of '_' and '-' (the inner expansion is that run).
    INSTALL_TARGET_PROJECT="${INSTALL_TARGET_PROJECT#"${INSTALL_TARGET_PROJECT%%[!_-]*}"}"
    if [ -z "${INSTALL_TARGET_PROJECT}" ]; then
        echo "ERROR: DAAF_PROJECT_NAME='${PROJECT_NAME_GIVEN}' cannot be used as a Docker Compose"
        echo "       project name. A project name may use lowercase letters, digits, '-'"
        echo "       and '_', and must start with a letter or digit."
        case " ${BRIDGE_ADOPTED} " in
            *" DAAF_PROJECT_NAME "*) echo "       (This value was read from daaf-docker/environment_settings.txt.)" ;;
        esac
        echo "       Nothing has been downloaded or changed."
        exit 1
    fi
fi
# One NOTE when anything was taken from the settings file (review 44q
# SUGGESTION-3), listing each adopted key with a non-empty value, plus the
# normalization sentence when the name changed. Nothing is printed when neither
# applies (a fresh install, or a settings file with the bridged keys commented
# out, as the template ships them), so the default output does not change.
SETTINGS_NOTE_KEYS=""
for _k in DAAF_PROJECT_NAME DAAF_PORT_MARIMO DAAF_PORT_LOGVIEWER DAAF_PORT_VSCODE DAAF_DEV; do
    case " ${BRIDGE_ADOPTED} " in
        *" ${_k} "*) ;;
        *) continue ;;
    esac
    if [ -n "${!_k:-}" ]; then SETTINGS_NOTE_KEYS="${SETTINGS_NOTE_KEYS} ${_k}"; fi
done
PROJECT_NAME_NOTE=""
if [ -n "${PROJECT_NAME_GIVEN}" ] && [ "${PROJECT_NAME_GIVEN}" != "${INSTALL_TARGET_PROJECT}" ]; then
    PROJECT_NAME_NOTE="Docker Compose uses the project name '${INSTALL_TARGET_PROJECT}' for '${PROJECT_NAME_GIVEN}'."
fi
if [ -n "${SETTINGS_NOTE_KEYS}" ]; then
    echo "NOTE: Using these settings from daaf-docker/environment_settings.txt:"
    for _k in ${SETTINGS_NOTE_KEYS}; do
        echo "        ${_k}=${!_k}"
    done
    if [ -n "${PROJECT_NAME_NOTE}" ]; then echo "      ${PROJECT_NAME_NOTE}"; fi
    echo ""
elif [ -n "${PROJECT_NAME_NOTE}" ]; then
    echo "NOTE: ${PROJECT_NAME_NOTE}"
    echo ""
fi
if [ -n "${PROJECT_NAME_GIVEN}" ]; then
    export DAAF_PROJECT_NAME="${INSTALL_TARGET_PROJECT}"
fi

# --- Printed commands carry the project (review 44q ISSUE-2) ---
# The manual `docker compose ...` commands and the "re-run this installer" texts
# printed on failure run in the USER's shell, where a project taken from
# environment_settings.txt (or given as a one-shot prefix) is not set: a bare
# `docker compose` there resolves to project 'daaf' and could exec into, or
# recreate, the default installation. So, for any project other than 'daaf':
#   - every printed compose command carries `-p <project>` (it overrides `name:`);
#   - the `up -d` retry, which (re)creates the container, also carries the ports
#     this run used, as a same-line prefix. (Not `bash run_daaf.sh`: a first
#     install that failed before seeding has no settings file to load.) The
#     ports prefix is printed whenever a port is set, also for project 'daaf';
#   - every "re-run this installer" text names DAAF_PROJECT_NAME=<project>, as
#     the DAAF_FORCE_REINSTALL hints below do (FORCE_RERUN_ENV).
# For project 'daaf' with no ports set, every line is byte-identical to before
# (CI and scripts/host/test_migration.* grep this output).
# SYNC NOTE: install.ps1 prints the same commands in PowerShell form.
COMPOSE_P_FLAG=""
RERUN_PROJECT_PREFIX=""
RETRY_FORCE_TEXT="set DAAF_FORCE_REINSTALL=1 if prompted"
if [ "${INSTALL_TARGET_PROJECT}" != "daaf" ]; then
    COMPOSE_P_FLAG="-p ${INSTALL_TARGET_PROJECT} "
    RERUN_PROJECT_PREFIX="DAAF_PROJECT_NAME=${INSTALL_TARGET_PROJECT} "
    RETRY_FORCE_TEXT="set DAAF_PROJECT_NAME=${INSTALL_TARGET_PROJECT}, and DAAF_FORCE_REINSTALL=1 if prompted"
fi
UP_PORTS_PREFIX=""
for _k in DAAF_PORT_MARIMO DAAF_PORT_LOGVIEWER DAAF_PORT_VSCODE; do
    if [ -n "${!_k:-}" ]; then UP_PORTS_PREFIX="${UP_PORTS_PREFIX}${_k}=${!_k} "; fi
done
# The data volume of THIS folder's install (checked when a docker-compose.yml is
# here): "<project>_daaf-data", or DAAF_DATA_VOLUME_NAME from the SHELL
# environment, a verbatim full volume name (the shared-workspace escape hatch,
# unchanged). A DAAF_DATA_VOLUME_NAME in environment_settings.txt is deliberately
# not read: step [2/4] re-downloads docker-compose.yml with its shared-volume
# block commented out, so this run always mounts and writes "<project>_daaf-data",
# and a file value could only point the check AWAY from that volume (a file
# naming a missing volume would turn the case-1 WARNING into the case-3 NOTE and
# re-install over "<project>_daaf-data" without a prompt). The shell override
# keeps its earlier behaviour.
DATA_VOLUME_NAME="${DAAF_DATA_VOLUME_NAME:-${INSTALL_TARGET_PROJECT}_daaf-data}"

# --- Existing-install decision (must not depend on the install folder) ---
# The data volume this run would mount -- recreating its container (`up -d`) and
# copying a fresh clone over its framework files and git history -- is named by
# the Compose PROJECT, not by this folder. Before 2026-10-06 the check ran only
# when THIS folder held a docker-compose.yml, so running the installer from a
# different folder with the same project name silently took over the existing
# install (review B-1, research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/
# reviews/32q_quality_safety_review.md). Four cases:
#   1. volume present, compose file here  -> this folder's install: WARNING, exit 1
#                                            unless DAAF_FORCE_REINSTALL=1 (unchanged)
#   2. volume present, no compose file    -> an install made from ANOTHER folder:
#                                            refuse, exit 1, before anything is
#                                            downloaded or built (FORCE honoured)
#   3. volume absent,  compose file here  -> earlier attempt incomplete: NOTE (unchanged)
#   4. volume absent,  no compose file    -> fresh install (unchanged)
# A volume that could not be checked ("unknown", see daaf_volume_state) is never
# read as absent: refuse unless DAAF_FORCE_REINSTALL=1. (The preflight above only
# proves the daemon answered `docker info` a moment ago; it does not make every
# later inspect failure a "not found".)
# Which volume is checked (INSTALL_TARGET_PROJECT is the one project derived
# and normalized above, already exported for Compose whenever a project was given
# in the shell or in environment_settings.txt):
#   - compose file here: DATA_VOLUME_NAME (the project's volume, or the shell
#     DAAF_DATA_VOLUME_NAME override, as before).
#   - no compose file: the volume THIS run will create and write,
#     "${INSTALL_TARGET_PROJECT}_daaf-data". (Compose also reads a .env file
#     beside the compose file; a stray .env in a folder with no compose file is
#     not considered; the installer never writes one.) DAAF_DATA_VOLUME_NAME is
#     deliberately NOT used here: the downloaded compose file's shared-volume
#     block is commented out, so a fresh install always writes its own project
#     volume, and the documented shared-workspace setup (installation guide,
#     "Sharing One Research Workspace Across Two Installs", Step 3) installs a
#     second copy from a new folder with DAAF_DATA_VOLUME_NAME naming install #1's
#     EXISTING volume -- that must not be refused.
# FORCE escape in case 2: DAAF_FORCE_REINSTALL means "I accept that the
# framework files and git history in the existing volume are overwritten", which
# is the same consequence whichever folder runs the installer; and re-installing
# from a NEW folder is the installer's only recovery path when the original
# daaf-docker folder was deleted or lost (research/ is preserved either way).
if [ -f "${INSTALL_DIR}/docker-compose.yml" ]; then
    CHECK_VOLUME_NAME="${DATA_VOLUME_NAME}"
else
    CHECK_VOLUME_NAME="${INSTALL_TARGET_PROJECT}_daaf-data"
fi
CHECK_VOLUME_STATE="$(daaf_volume_state "${CHECK_VOLUME_NAME}")"
# The DAAF_FORCE_REINSTALL re-run hints in the refusals below (case 1, case 2,
# "could not check") must re-target the SAME project. For any project other than
# the default, the hint names DAAF_PROJECT_NAME on the same line as the FORCE
# flag: a re-run from a new terminal, or with a one-shot prefix instead of an
# `export`, would otherwise fall back to project 'daaf' and could take over that
# installation instead (review 42q I-1; the install.ps1 twin does the same). It
# names INSTALL_TARGET_PROJECT, so a project taken from environment_settings.txt
# is carried too (review 43d ISSUE-1).
FORCE_RERUN_ENV="DAAF_FORCE_REINSTALL=1"
if [ "${INSTALL_TARGET_PROJECT}" != "daaf" ]; then
    FORCE_RERUN_ENV="DAAF_PROJECT_NAME=${INSTALL_TARGET_PROJECT} ${FORCE_RERUN_ENV}"
fi

if [ "${CHECK_VOLUME_STATE}" = "unknown" ]; then
    if [ "${DAAF_FORCE_REINSTALL:-}" = "1" ]; then
        echo "NOTE: Could not check whether Docker volume '${CHECK_VOLUME_NAME}' already exists."
        echo "      Proceeding anyway (DAAF_FORCE_REINSTALL=1)."
        echo ""
    else
        echo "ERROR: Could not check whether a DAAF installation already exists (Docker"
        echo "       could not inspect or list its volumes; looking for '${CHECK_VOLUME_NAME}')."
        echo "       Nothing has been downloaded or changed. Make sure Docker Desktop is"
        echo "       running, then run the installer again."
        echo ""
        echo "To skip this check and install anyway, set DAAF_FORCE_REINSTALL=1:"
        echo "  ${FORCE_RERUN_ENV} bash -c \"\$(curl -fsSL ${RAW_BASE}/scripts/host/install.sh)\""
        echo ""
        exit 1
    fi
elif [ -f "${INSTALL_DIR}/docker-compose.yml" ]; then
    if [ "${CHECK_VOLUME_STATE}" = "present" ]; then
        # Volume exists -- this is a completed or substantially completed installation
        if [ "${DAAF_FORCE_REINSTALL:-}" = "1" ]; then
            echo "NOTE: Existing installation detected. Proceeding with re-install (DAAF_FORCE_REINSTALL=1)."
            echo ""
        else
            echo "WARNING: An existing DAAF installation was detected."
            echo "         (Docker volume '${CHECK_VOLUME_NAME}', project '${INSTALL_TARGET_PROJECT}')"
            # Review 44q SUGGESTION-2: a folder whose first install failed before
            # seeding has a compose file but no settings file, so a retry from a
            # new terminal falls back to the shell's project. Say so plainly.
            # SYNC NOTE: same lines in install.ps1.
            if [ ! -f "${INSTALL_DIR}/environment_settings.txt" ]; then
                echo "         This folder has no environment_settings.txt, so the project name comes"
                echo "         from your shell (default 'daaf'). If you meant to install a separate"
                echo "         copy here, set DAAF_PROJECT_NAME (and its ports) again first."
            fi
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
            echo "  ${FORCE_RERUN_ENV} bash -c \"\$(curl -fsSL ${RAW_BASE}/scripts/host/install.sh)\""
            echo ""
            exit 1
        fi
    else
        echo "NOTE: A previous install attempt was detected but appears incomplete."
        echo "      Proceeding with a fresh install."
        echo ""
    fi
elif [ "${CHECK_VOLUME_STATE}" = "present" ]; then
    # Case 2: the volume exists, but this folder has no docker-compose.yml.
    if [ "${DAAF_FORCE_REINSTALL:-}" = "1" ]; then
        echo "NOTE: An existing DAAF installation using Docker volume '${CHECK_VOLUME_NAME}' (project '${INSTALL_TARGET_PROJECT}')"
        echo "      was detected, probably installed from another folder. Proceeding with"
        echo "      re-install from this folder (DAAF_FORCE_REINSTALL=1)."
        echo ""
    else
        # The second-copy example (reviews 42q I-4, 43d NIT-2) must never repeat
        # the refused project's name, and must not reuse ports the refused install
        # likely holds. The installation guide's own second-instance examples
        # (daaf-personal, and daaf-gpt for a shared workspace) use 2818-2820, so
        # any refused project other than 'daaf' gets other ports. Deterministic:
        #   refused 'daaf'      -> daaf-personal 2818-2820 (the guide's example; the
        #                          default install holds 2718-2720)
        #   refused 'daaf-work' -> daaf-lab      3018-3020 (daaf-work likely holds
        #                          2918-2920, taken from this very example)
        #   any other project   -> daaf-work     2918-2920
        # Each step is a further offset of 100, as in the guide, and neither
        # 2918-2920 nor 3018-3020 is used as an example there. The refused
        # project's own ports are not consulted: in case 2 that install lives in
        # another folder, so they are not reliably known here.
        # SYNC NOTE: same table in install.ps1.
        EXAMPLE_PROJECT="daaf-work"
        EXAMPLE_PORT_MARIMO=2918
        EXAMPLE_PORT_LOGVIEWER=2919
        EXAMPLE_PORT_VSCODE=2920
        if [ "${INSTALL_TARGET_PROJECT}" = "daaf" ]; then
            EXAMPLE_PROJECT="daaf-personal"
            EXAMPLE_PORT_MARIMO=2818
            EXAMPLE_PORT_LOGVIEWER=2819
            EXAMPLE_PORT_VSCODE=2820
        elif [ "${INSTALL_TARGET_PROJECT}" = "daaf-work" ]; then
            EXAMPLE_PROJECT="daaf-lab"
            EXAMPLE_PORT_MARIMO=3018
            EXAMPLE_PORT_LOGVIEWER=3019
            EXAMPLE_PORT_VSCODE=3020
        fi
        echo "WARNING: A DAAF installation using Docker volume '${CHECK_VOLUME_NAME}' (project '${INSTALL_TARGET_PROJECT}')"
        echo "already exists, probably installed from another folder, or its daaf-docker"
        echo "folder was moved or deleted. This folder has no docker-compose.yml, so it is"
        echo "not (or is no longer) that installation's folder:"
        echo "  ${INSTALL_DIR}"
        echo ""
        echo "Installing here would take over that installation: it would recreate its"
        echo "container and overwrite its framework files (CLAUDE.md, skills, agents,"
        echo "templates) and local git history. Its research data would NOT be deleted."
        echo "Nothing has been downloaded or changed."
        echo ""
        echo "To update that installation instead (recommended -- preserves local changes),"
        echo "go to the daaf-docker folder you installed it in and run:"
        echo "  bash update_daaf.sh"
        echo ""
        echo "To install a SEPARATE second copy of DAAF here, choose a project name other"
        echo "than '${INSTALL_TARGET_PROJECT}' and three free ports, then run the installer again, e.g.:"
        echo "  export DAAF_PROJECT_NAME=${EXAMPLE_PROJECT}"
        echo "  export DAAF_PORT_MARIMO=${EXAMPLE_PORT_MARIMO}"
        echo "  export DAAF_PORT_LOGVIEWER=${EXAMPLE_PORT_LOGVIEWER}"
        echo "  export DAAF_PORT_VSCODE=${EXAMPLE_PORT_VSCODE}"
        echo "  curl -fsSL ${RAW_BASE}/scripts/host/install.sh | bash"
        echo "See \"Running multiple DAAF instances\" in the installation guide:"
        echo "  https://github.com/${REPO}/blob/${BRANCH}/user_reference/01_installation_and_quickstart.md#running-multiple-daaf-instances"
        echo ""
        echo "To deliberately re-install over that installation from this folder, set"
        echo "DAAF_FORCE_REINSTALL=1 (a backup is strongly recommended first):"
        echo "  ${FORCE_RERUN_ENV} bash -c \"\$(curl -fsSL ${RAW_BASE}/scripts/host/install.sh)\""
        echo ""
        exit 1
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

# --- macOS-only: double-click launcher (DAAF.command) ---
# Only macOS ships a double-click launcher. Finder runs a .command file in
# Terminal, and it needs the executable bit to launch (setting it here means the
# installer-placed copy is never blocked -- it never traverses a browser download
# and so carries no quarantine attribute). Linux desktop environments handle
# double-clicked scripts inconsistently, so no launcher is shipped there; Linux
# users launch via `bash daaf.sh` from a terminal (documented in the quickstart).
# Non-fatal: a download failure emits a prominent diagnostic WARNING (with the
# curl exit code, the URL attempted, and the branch) but never aborts the
# install -- the launcher is a convenience, and update_daaf.sh can heal it later.
if [ "$(uname -s 2>/dev/null)" = "Darwin" ]; then
    if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
        echo "[DRY-RUN] Would download and chmod +x the macOS launcher (DAAF.command)"
    else
        # Capture curl's exit code explicitly. The `|| rc=$?` keeps the failure
        # from tripping `set -e` (equivalent to the old `elif` safety) while
        # letting us report the exact code in the diagnostic below.
        DAAF_CMD_URL="${RAW_BASE}/scripts/host/DAAF.command"
        DAAF_CMD_RC=0
        curl -fsSL "${DAAF_CMD_URL}" -o "${INSTALL_DIR}/DAAF.command" || DAAF_CMD_RC=$?
        if [ "${DAAF_CMD_RC}" -eq 0 ]; then
            chmod +x "${INSTALL_DIR}/DAAF.command"
        else
            # A failed curl can leave a partial or zero-byte file behind; remove
            # it so a broken launcher can't shadow a later heal by update_daaf.sh.
            rm -f "${INSTALL_DIR}/DAAF.command"
            echo ""
            echo "WARNING: Could not download the macOS double-click launcher (DAAF.command)."
            echo "         curl exit code: ${DAAF_CMD_RC}"
            echo "         URL attempted:  ${DAAF_CMD_URL}"
            echo "         Branch:         ${BRANCH}"
            echo "         This is non-fatal -- the rest of the install continues."
            echo "         The launcher can be delivered later by running: bash update_daaf.sh"
            echo "         (its existence-heal copies missing host files). In the meantime you"
            echo "         can always launch DAAF from a terminal with: bash daaf.sh"
        fi
    fi
fi

# --- Icon asset (daaf.ico) ---
# The DAAF icon ships on every platform so the installed file set matches what
# update_daaf.sh syncs (its platform filter whitelists daaf.ico on Unix too).
# Today only Windows uses it (the DAAF.lnk shortcut created by install.ps1); on
# macOS/Linux it is a small inert asset kept for install/update parity.
# Non-fatal: a download failure degrades to a note, never aborts the install.
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    echo "[DRY-RUN] Would download the DAAF icon (daaf.ico)"
elif ! curl -fsSL "${RAW_BASE}/scripts/host/daaf.ico" -o "${INSTALL_DIR}/daaf.ico"; then
    echo "NOTE: Could not download the DAAF icon (daaf.ico); continuing without it."
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
# Project name is set declaratively via the top-level
# `name: ${DAAF_PROJECT_NAME:-daaf}` key in docker-compose.yml -- no need to set
# COMPOSE_PROJECT_NAME here. DAAF_PROJECT_NAME (and the DAAF_PORT_* / DAAF_DEV
# keys) are already in the environment: the user's own values, or the ones the
# bridge above exported from environment_settings.txt (the project name in its
# normalized form, see "The target project" above).
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
    echo "You can safely re-run this installer to retry (${RETRY_FORCE_TEXT})."
    echo "If the output above contains a line like '[output clipped, log limit 2MiB reached]'"
    echo "(the exact limit varies by Docker version), re-run with DAAF_DIAG_BUILD=1 for"
    echo "unclipped build logs:"
    echo "  ${RERUN_PROJECT_PREFIX}DAAF_DIAG_BUILD=1 bash -c \"\$(curl -fsSL ${RAW_BASE}/scripts/host/install.sh)\""
    exit 1
fi
echo "Starting container..."
if ! docker compose -f "${INSTALL_DIR}/docker-compose.yml" up -d; then
    echo ""
    echo "ERROR: Failed to start the Docker container after build. Check the output above for details."
    echo "You can safely re-run this installer to retry (${RETRY_FORCE_TEXT})."
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
        echo "  ${UP_PORTS_PREFIX}docker compose ${COMPOSE_P_FLAG}-f ${INSTALL_DIR}/docker-compose.yml up -d" >&2
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
    echo "  docker compose ${COMPOSE_P_FLAG}-f ${INSTALL_DIR}/docker-compose.yml exec -T daaf-docker \\"
    echo "    git clone --depth 1 -b ${BRANCH} https://github.com/${REPO}.git /tmp/daaf-clone"
    echo "  docker compose ${COMPOSE_P_FLAG}-f ${INSTALL_DIR}/docker-compose.yml exec -T daaf-docker \\"
    echo "    bash -c 'cp -a /tmp/daaf-clone/. /daaf/ && rm -rf /tmp/daaf-clone'"
    echo "You can also safely re-run this installer to retry from scratch (${RETRY_FORCE_TEXT})."
    exit 1
fi

if ! docker compose -f "${INSTALL_DIR}/docker-compose.yml" exec -T daaf-docker \
    bash -c 'cp -a /tmp/daaf-clone/. /daaf/ && rm -rf /tmp/daaf-clone' </dev/null; then
    echo ""
    echo "ERROR: Failed to copy repository files into the container."
    echo "The clone succeeded, but copying to /daaf/ failed (possibly a permissions issue)."
    echo "You can retry manually with:"
    echo "  docker compose ${COMPOSE_P_FLAG}-f ${INSTALL_DIR}/docker-compose.yml exec -T daaf-docker \\"
    echo "    bash -c 'cp -a /tmp/daaf-clone/. /daaf/ && rm -rf /tmp/daaf-clone'"
    echo "You can also safely re-run this installer to retry from scratch (${RETRY_FORCE_TEXT})."
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
    echo "  docker compose ${COMPOSE_P_FLAG}exec daaf-docker bash"
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
#     Values the bridge near the top adopted from that file are never written
#     back: the bridge reads the file only when it exists, and then this step
#     takes the "left untouched" branch.
#   - DAAF_PROJECT_NAME is seeded in the normalized form the derivation near the
#     top exported (e.g. "work" for "Work"), not as typed: backup_daaf.sh,
#     restore_from_backup.sh and daaf_lib.sh derive volume names from the raw
#     value ("${DAAF_PROJECT_NAME:-daaf}_daaf-data"), so a seeded "Work" would
#     point them at "Work_daaf-data" while Compose created "work_daaf-data".
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
        for _k in DAAF_PROJECT_NAME DAAF_PORT_MARIMO DAAF_PORT_LOGVIEWER DAAF_PORT_VSCODE DAAF_DEV DAAF_BRANCH DAAF_DATA_VOLUME_NAME; do
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

        # Recreate the container so the newly created environment_settings.txt takes
        # effect. docker-compose.yml injects it via `env_file`, which is applied at
        # container CREATION -- and this container was created (up -d above) BEFORE
        # the seeder wrote the file, so without a recreate the seeded settings are
        # not injected AND run_daaf's "modified since container started" freshness
        # NOTE would fire on the very next launch of a fresh install. --force-recreate
        # is deliberate: an all-commented seeded file resolves to an empty compose env
        # and would NOT trigger config-hash recreate on its own, leaving the warning
        # armed. Reached only in the SEED_OK path (the file was actually created) and
        # never under DAAF_DRY_RUN (that hits the dry-run branch above). The just-cloned
        # repo lives in the daaf-data NAMED VOLUME, so recreating cannot lose it.
        # Non-fatal: `if !` keeps set -e from aborting; on failure print the same
        # down/relaunch guidance run_daaf gives and continue (never fail the install).
        echo ""
        echo "NOTE: Restarting the container to apply your seeded settings..."
        if ! docker compose -f "${INSTALL_DIR}/docker-compose.yml" up -d --force-recreate; then
            echo "NOTE: Could not restart the container to apply the seeded settings. They"
            echo "      were written to environment_settings.txt but will not take effect"
            echo "      until you recreate the container. Close all DAAF sessions, then run:"
            echo "        cd ${INSTALL_DIR}"
            echo "        docker compose ${COMPOSE_P_FLAG}down"
            echo "        bash run_daaf.sh"
        fi
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
if [ "$(uname -s 2>/dev/null)" = "Darwin" ]; then
    echo ""
    echo "     Or, to skip the terminal: double-click DAAF.command in ${INSTALL_DIR}"
    echo "     from Finder to open the Control Panel."
fi
echo ""
echo "  2. On first launch, you'll be asked to authenticate with your Anthropic account."
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
echo "  docker compose ${COMPOSE_P_FLAG}exec daaf-docker bash   # enter the container"
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
