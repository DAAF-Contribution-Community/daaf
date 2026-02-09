#!/bin/bash
set -euo pipefail

SEED_DIR="/home/appuser/daaf-seed"
WORK_DIR="/daaf"

# ── Volume seeding ──────────────────────────────────────
# On first run (empty volume), copy the full repo from the
# in-image clone. On subsequent runs, skip — the volume
# already has the user's working state.
if [ -z "$(ls -A "$WORK_DIR" 2>/dev/null)" ]; then
    echo "[daaf] First run — seeding project files into volume..."
    cp -a "$SEED_DIR"/. "$WORK_DIR"/
    echo "[daaf] Ready. $(git -C "$WORK_DIR" log --oneline -1 2>/dev/null || true)"
else
    echo "[daaf] Volume already populated."
    echo "[daaf] HEAD: $(git -C "$WORK_DIR" log --oneline -1 2>/dev/null || true)"
fi

# Ensure git trusts the volume directory
git config --global --get-all safe.directory 2>/dev/null | grep -qxF "$WORK_DIR" \
    || git config --global --add safe.directory "$WORK_DIR"

exec "$@"
