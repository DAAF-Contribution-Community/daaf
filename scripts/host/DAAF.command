#!/bin/bash
# ============================================================================
# DAAF Launcher (macOS) -- double-clickable shim for the Control Panel
# ============================================================================
# WHAT THIS IS:
#   A thin double-click launcher for macOS. When you double-click this file in
#   Finder, macOS opens Terminal and runs it. All it does is change into its own
#   folder (your daaf-docker folder) and hand off to daaf.sh -- the real DAAF
#   Control Panel. It adds no logic of its own beyond that handoff.
#
# WHY IT IS SAFE TO DOUBLE-CLICK:
#   It runs no privileged commands, installs nothing, and touches no files. It
#   only launches the Control Panel you would otherwise start by typing
#   `bash daaf.sh` in a terminal. You can open it in any text editor to verify.
#
# WHY THE `cd` IS REQUIRED:
#   Every DAAF host script expects docker-compose.yml in the CURRENT directory.
#   A double-clicked .command does not reliably start in its own folder, so the
#   first real action is `cd` into this file's directory ($0's dirname) so the
#   Control Panel's preflight finds docker-compose.yml.
#
# PORTABILITY:
#   Targets the macOS system bash at /bin/bash (frozen at 3.2.57), so it avoids
#   all Bash 4.x-only constructs. No Homebrew or newer bash is needed.
#
# NOTE: This shim deliberately does NOT reproduce daaf.sh's own error/pause
#   traps -- daaf.sh already keeps its window open on failure. The only pause
#   here is a fallback for the narrow case where daaf.sh cannot be launched at
#   all (missing file, or exec failure).
#
# WHY NO DAAF_NESTED / DAAF_DRY_RUN HANDLING:
#   Those variables are consumed by daaf.sh (and the scripts it delegates to),
#   not here. As a pure passthrough shim, this launcher `exec`s daaf.sh, and any
#   DAAF_* variables in the environment are inherited across `exec` unchanged, so
#   the delegate sees them intact. There is nothing for this shim to forward.
#
# The universal fallback works everywhere: open a terminal in this folder and
# run `bash daaf.sh` directly.
# ============================================================================

# `set -u` only (no -e / pipefail): this shim's two guards (cd, daaf.sh presence)
# handle their own failures explicitly and must fall through to `exec bash
# daaf.sh`, which owns all error handling from that point on. -e/pipefail here
# would risk aborting before the handoff on a benign non-zero status.
set -u

# --- Move into this launcher's own directory (the daaf-docker folder) ---
# BSD-safe dirname of $0; quote to tolerate spaces in the install path.
cd "$(dirname "$0")" || {
    echo "ERROR: Could not change into the DAAF folder." >&2
    echo "Open a terminal in your daaf-docker folder and run: bash daaf.sh" >&2
    read -r -p "Press Enter to close... " _ || true
    exit 1
}

# --- Verify the Control Panel is present before handing off ---
if [ ! -f "daaf.sh" ]; then
    echo "ERROR: daaf.sh was not found next to this launcher." >&2
    echo "This launcher must live in your daaf-docker folder alongside daaf.sh." >&2
    echo "If it is missing, re-run the installer or your update to restore it." >&2
    read -r -p "Press Enter to close... " _ || true
    exit 1
fi

# --- Hand off to the real Control Panel ---
# `exec` replaces this process with daaf.sh so the interactive menu owns the
# terminal directly (preserving the TTY that Claude Code's launch path needs).
# daaf.sh installs its own pause-on-error trap, so nothing more is needed here.
exec bash daaf.sh

# Reached only if `exec` itself failed to start bash/daaf.sh.
echo "ERROR: Failed to launch daaf.sh." >&2
read -r -p "Press Enter to close... " _ || true
exit 1
