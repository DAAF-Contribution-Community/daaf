#!/usr/bin/env bash
# =============================================================================
# daaf-entrypoint.sh — container ENTRYPOINT wrapper.
#
# COPY'd into the image at /usr/local/bin/daaf-entrypoint.sh and set as the
# Docker ENTRYPOINT, immediately before CMD ["bash"]. Its only jobs are:
#   1. Best-effort auto-start of the provider shim (opt-in via DAAF_PROVIDER_SHIM,
#      handled entirely inside start_shim.sh --auto).
#   2. exec the container's CMD (bash) so the container behaves exactly as before
#      for every user who has not opted into the shim.
#
# CRITICAL boot-safety constraints:
#   * /daaf is a NAMED VOLUME that shadows the image copy at runtime, so the
#     start_shim.sh path may be absent, empty, or broken. Every reference to it
#     is guarded; nothing here may abort the container's startup.
#   * No `set -e`: a failing shim launch must never stop `exec "$@"` from running.
#   * `set -u` is safe because we default every variable we read.
# =============================================================================

set -u
# Deliberately NO `set -e` and NO `set -o pipefail`: boot must always reach
# `exec "$@"`. The shim is a convenience; its failure is non-fatal by design.

readonly SHIM_MANAGER="/daaf/scripts/provider_shim/start_shim.sh"

# Best-effort shim auto-start. Guard on existence AND executability so a shadowed
# or partially-synced /daaf volume can never break boot. start_shim.sh --auto is
# itself a silent no-op unless DAAF_PROVIDER_SHIM=openai, so this is inert for
# users who have not opted in.
if [ -x "$SHIM_MANAGER" ]; then
    # Never let a shim failure propagate: capture and ignore any non-zero exit.
    if ! "$SHIM_MANAGER" --auto; then
        echo "daaf-entrypoint: provider shim --auto returned non-zero; continuing boot." >&2
    fi
fi

# Hand off to the container's command (CMD ["bash"] by default). `exec` replaces
# this process so signals and TTY behave exactly as an un-wrapped container.
exec "$@"
