#!/usr/bin/env bash
set -Eeuo pipefail
# apply_bash_safety_c.sh — install (or roll back) the harmonized bash-safety.sh
# revision _c: the section-10 accidental-environment-disclosure guard (Track B,
# 2026-10-03) on top of the live hook. A SINGLE-hook installer, modelled on
# research/2026-09-24_FrameworkDev_ClaudeCode_Upgrade_2.1.281/hook_patches/
# apply_hook_patches_c.sh.
#
# REVISION _c (2026-10-03, SafetyHookHardening session, Track B).
#   - PATCH source is bash-safety.sh.harmonized_c.proposed in this workspace:
#     B1's section 10 (ENV_DISCLOSURE_GUARD, four categories A-D) plus the 0a/0c
#     disclosure accumulator, and B3's one measured ENVIRON-boundary tightening.
#   - BASE = the live hook's sha256 as of 2026-10-03 (= the harmonized _a body,
#     the base B1/B3 drafted against). PATCHED = the _c draft's sha256.
#   - The 4 category-A/C data-token false positives (an env-disclosure token
#     inside a quoted grep/jq/python argument) and the pipe / `2>`-redirect sink
#     exclusions are ACCEPTED residuals, documented in the _c header; this
#     installer makes no further hook change (user decision 2026-10-03).
#   - Rollback restores the BASE content from the content-addressed backup.
#     Git is NOT a rollback route: the working tree may not hold the BASE body.
#   - If the live hook is not at BASE (already _c, or drifted), the apply path
#     either skips (already _c) or refuses (exit 20, nothing written).
#
# WHO RUNS THIS: the user, via a `!`-prefixed command in Claude Code (which
# bypasses the PreToolUse hooks). .claude/hooks/ is deny-protected, so agents
# cannot and must not run this script against it.
#
#   ! bash /daaf/research/2026-09-18_FrameworkDev_SafetyHookHardening/apply_bash_safety_c.sh --dry-run
#   ! bash /daaf/research/2026-09-18_FrameworkDev_SafetyHookHardening/apply_bash_safety_c.sh
#   ! bash /daaf/research/2026-09-18_FrameworkDev_SafetyHookHardening/apply_bash_safety_c.sh --rollback
#
# SAFETY PROPERTIES
#   - Drift refusal: the live hook must hash to the sha256 recorded when the
#     patch was drafted (BASE) or to the patched copy (PATCHED, already
#     applied). Any other content, or a missing hook, refuses the run before
#     anything is written (exit 20).
#   - Bundle integrity: the patched copy must hash to its recorded sha256, so a
#     draft edited after the tests ran cannot be installed silently.
#   - Idempotent: a hook already in the target state is skipped; running twice
#     is a no-op the second time.
#   - Backup: before the hook is replaced, its BASE content is saved as
#     <backup-dir>/bash-safety.sh.<first 12 hex of BASE sha>.bak
#     (content-addressed, so a re-run never overwrites a good backup).
#   - Atomic install: the file is written to a temporary name in the hooks
#     directory with mode 755 and then renamed over the hook, so the hook is
#     never observed half-written.
#   - Verification: after installing, the hook's sha256 and mode (755) are
#     re-checked and the installed hook is parsed with `bash -n`.
#
# OPTIONS
#   --dry-run    Report what would happen; write nothing.
#   --rollback   Restore the BASE content from the backup (the hook must
#                currently be in the PATCHED state; the backup is sha-verified).
#   -h, --help   Show usage.
#
# ENVIRONMENT (testing only; defaults are the real locations)
#   DAAF_HOOKS_DIR        hooks directory to patch   (default /daaf/.claude/hooks)
#   DAAF_HOOK_BACKUP_DIR  backup directory           (default <WS>/live_backup_2026-10-03)
#
# EXIT CODES
#   0  success (including "nothing to do")
#   1  usage error or unexpected failure
#   20 refused: the live hook drifted, the hook/backup is missing, or the
#      patched copy no longer matches its recorded sha256
#   30 a required command is missing

# --- Config ---
WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly WS_DIR
readonly PATCH_SRC="${WS_DIR}/bash-safety.sh.harmonized_c.proposed"
readonly HOOKS_DIR="${DAAF_HOOKS_DIR:-/daaf/.claude/hooks}"
readonly BACKUP_DIR="${DAAF_HOOK_BACKUP_DIR:-${WS_DIR}/live_backup_2026-10-03}"
readonly REPO_DIR="/daaf"
readonly HOOK_NAME="bash-safety.sh"

# Manifest. BASE = sha256 of the live hook this patch replaces (= the harmonized
# _a body the section-10 work was drafted against). PATCHED = sha256 of the _c
# draft in this workspace.
readonly BASE_SHA="b1beba9fe3b2afc9b5e881b43c76c89c60a13656cd078d7313dbd715fe87b497"
readonly PATCHED_SHA="f234a53f25473931e2c0ef9514840ad7a627d7d16b3928d991ab482bdba16f03"

MODE="apply"
DRY_RUN=0
TMP_TARGET=""

# --- Cleanup (registered before any file is written) ---
cleanup() {
    if [ -n "$TMP_TARGET" ] && [ -e "$TMP_TARGET" ]; then
        rm -f "$TMP_TARGET"
    fi
}
trap cleanup EXIT
trap 'echo "ERROR: apply_bash_safety_c.sh failed at line $LINENO (command: $BASH_COMMAND)." >&2; echo "  Fix: the install is an atomic rename, so the hook is not half-written. Re-run with --dry-run to see the current state." >&2' ERR

# --- Helpers ---
usage() {
    cat <<'USAGE'
Usage: bash apply_bash_safety_c.sh [--dry-run] [--rollback]

Checks the live /daaf/.claude/hooks/bash-safety.sh and installs the section-10
revision _c from bash-safety.sh.harmonized_c.proposed (or, with --rollback,
restores the pre-patch content from the content-addressed backup).
The live hook must be at the recorded BASE sha (or already at _c).
Run it as a `!`-prefixed command in Claude Code. Use --dry-run first.
USAGE
}

sha_of() {
    local out
    out="$(sha256sum "$1")"
    printf '%s' "${out%% *}"
}

# Install $1 over $2 atomically with mode 755.
install_atomic() {
    local src="$1" dst="$2"
    TMP_TARGET="${dst}.apply-tmp.$$"
    install -m 755 "$src" "$TMP_TARGET"
    mv -f "$TMP_TARGET" "$dst"
    TMP_TARGET=""
}

# --- Arguments ---
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --rollback) MODE="rollback" ;;
        -h|--help) usage; exit 0 ;;
        *)
            echo "ERROR: unknown argument: $arg" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [ "$DRY_RUN" -eq 1 ]; then
    echo "=== DRY RUN (${MODE}): nothing will be written ==="
else
    echo "=== ${MODE^^} ==="
fi
echo "hooks dir : ${HOOKS_DIR}"
echo "backups   : ${BACKUP_DIR}"

# --- [1/6] Preflight ---
echo "[1/6] Checking prerequisites..."
missing=()
for cmd in sha256sum install mv stat bash; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        missing+=("$cmd")
    fi
done
if [ "${#missing[@]}" -gt 0 ]; then
    echo "ERROR: missing required commands: ${missing[*]}" >&2
    echo "  Fix: these ship with coreutils in the DAAF image; rebuild the container if they are absent." >&2
    exit 30
fi
if [ ! -d "$HOOKS_DIR" ]; then
    echo "ERROR: hooks directory not found: ${HOOKS_DIR}" >&2
    echo "  Fix: run this inside the DAAF container (the path is /daaf/.claude/hooks)." >&2
    exit 20
fi

# --- [2/6] Bundle integrity ---
echo "[2/6] Verifying the patched copy matches the recorded sha256..."
if [ ! -f "$PATCH_SRC" ]; then
    echo "ERROR: patched copy missing: ${PATCH_SRC}" >&2
    echo "  Fix: restore bash-safety.sh.harmonized_c.proposed in the session workspace." >&2
    exit 20
fi
src_got="$(sha_of "$PATCH_SRC")"
if [ "$src_got" != "$PATCHED_SHA" ]; then
    echo "ERROR: ${PATCH_SRC} changed after the patch was drafted and tested." >&2
    echo "  expected ${PATCHED_SHA}" >&2
    echo "  found    ${src_got}" >&2
    echo "  Fix: do not install an untested copy. Ask the framework engineer to re-run the suites and regenerate this manifest." >&2
    exit 20
fi
echo "  ok  ${HOOK_NAME} (patched copy)"

# --- [3/6] Classify the live hook (no writes yet) ---
echo "[3/6] Checking the live hook against the recorded sha256..."
LIVE="${HOOKS_DIR}/${HOOK_NAME}"
STATE="DRIFT"
if [ ! -f "$LIVE" ]; then
    STATE="MISSING"
else
    cur="$(sha_of "$LIVE")"
    if [ "$cur" = "$BASE_SHA" ]; then
        STATE="BASE"
    elif [ "$cur" = "$PATCHED_SHA" ]; then
        STATE="PATCHED"
    else
        STATE="DRIFT"
    fi
fi
refuse=0
case "${MODE}:${STATE}" in
    apply:BASE)        echo "  apply     ${HOOK_NAME} (pre-patch content, as drafted against)" ;;
    apply:PATCHED)     echo "  skip      ${HOOK_NAME} (already patched)" ;;
    rollback:PATCHED)  echo "  restore   ${HOOK_NAME} (patched; will restore pre-patch content)" ;;
    rollback:BASE)     echo "  skip      ${HOOK_NAME} (already pre-patch content)" ;;
    *)
        echo "  REFUSE    ${HOOK_NAME} (${STATE}: matches neither the recorded pre-patch nor the patched sha256)" >&2
        refuse=1
        ;;
esac
if [ "$refuse" -ne 0 ]; then
    echo "ERROR: refusing to ${MODE}: the live hook drifted since the patch was drafted, or is missing. Nothing was written." >&2
    echo "  Fix: revision _c expects the live hook at BASE sha ${BASE_SHA:0:12}. Inspect drift with 'git -C ${REPO_DIR} diff -- .claude/hooks/${HOOK_NAME}', then ask the framework engineer to re-draft the patch against the current hook." >&2
    exit 20
fi

# In rollback mode a sha-verified backup is required.
BAK="${BACKUP_DIR}/${HOOK_NAME}.${BASE_SHA:0:12}.bak"
if [ "$MODE" = "rollback" ] && [ "$STATE" = "PATCHED" ]; then
    if [ ! -f "$BAK" ] || [ "$(sha_of "$BAK")" != "$BASE_SHA" ]; then
        echo "ERROR: no verified backup for ${HOOK_NAME} (expected ${BAK})." >&2
        echo "  Fix: the pre-patch content is the harmonized _a body; check 'sha256sum' of a known-good copy equals ${BASE_SHA}, then copy it with 'cp -p'. Do NOT use git: the working tree may not hold the BASE body." >&2
        exit 20
    fi
fi

# --- [4/6] Back up and install ---
echo "[4/6] ${MODE^} ..."
changed=0
if [ "$MODE" = "apply" ] && [ "$STATE" = "BASE" ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "  would back up ${LIVE} -> ${BAK}"
        echo "  would install ${PATCH_SRC} -> ${LIVE} (mode 755)"
    else
        mkdir -p "$BACKUP_DIR"
        if [ -f "$BAK" ] && [ "$(sha_of "$BAK")" = "$BASE_SHA" ]; then
            echo "  backup exists  ${BAK}"
        else
            cp -p "$LIVE" "$BAK"
            echo "  backed up      ${BAK}"
        fi
        install_atomic "$PATCH_SRC" "$LIVE"
        got="$(sha_of "$LIVE")"
        mode="$(stat -c '%a' "$LIVE")"
        if [ "$got" != "$PATCHED_SHA" ] || [ "$mode" != "755" ]; then
            echo "ERROR: post-install check failed for ${LIVE} (sha ${got}, mode ${mode})." >&2
            echo "  Fix: re-run this script; the drift check will report the hook's state." >&2
            exit 1
        fi
        echo "  installed      ${LIVE} (sha verified, mode ${mode})"
        changed=1
    fi
elif [ "$MODE" = "rollback" ] && [ "$STATE" = "PATCHED" ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "  would restore ${BAK} -> ${LIVE} (mode 755)"
    else
        install_atomic "$BAK" "$LIVE"
        got="$(sha_of "$LIVE")"
        mode="$(stat -c '%a' "$LIVE")"
        if [ "$got" != "$BASE_SHA" ] || [ "$mode" != "755" ]; then
            echo "ERROR: post-rollback check failed for ${LIVE} (sha ${got}, mode ${mode})." >&2
            echo "  Fix: re-run this script; the drift check will report the hook's state." >&2
            exit 1
        fi
        echo "  restored       ${LIVE} (sha verified, mode ${mode})"
        changed=1
    fi
fi
if [ "$changed" -eq 0 ] && [ "$DRY_RUN" -eq 0 ]; then
    echo "  nothing to do: the hook is already in the ${MODE} target state"
fi

# --- [5/6] Syntax check ---
echo "[5/6] Parsing the hook with bash -n..."
if [ "$DRY_RUN" -eq 1 ]; then
    if [ "$MODE" = "apply" ]; then
        target="$PATCH_SRC"
    elif [ "$STATE" = "PATCHED" ]; then
        target="$BAK"
    else
        target="$LIVE"
    fi
else
    target="$LIVE"
fi
if bash -n "$target"; then
    echo "  ok  bash -n ${target}"
else
    echo "ERROR: bash -n failed for ${target}." >&2
    echo "  Fix: roll back with --rollback and report the failure to the framework engineer." >&2
    exit 1
fi

# --- [6/6] Next steps ---
echo "[6/6] Next steps"
if [ "$HOOKS_DIR" = "${REPO_DIR}/.claude/hooks" ] && command -v git >/dev/null 2>&1; then
    echo "  Git index mode (should read 100755):"
    echo "    $(git -C "$REPO_DIR" ls-files -s -- ".claude/hooks/${HOOK_NAME}")"
fi
cat <<'NEXT'
  Run the regression suites against the installed hook (all should pass):
    bash /daaf/scripts/test_safety_hooks.sh
    BASH_SAFETY_SH=/daaf/.claude/hooks/bash-safety.sh bats /daaf/tests/bash/bash_safety.bats
NEXT
echo "Done."
