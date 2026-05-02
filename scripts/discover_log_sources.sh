#!/usr/bin/env bash
# discover_log_sources.sh — List available log sources for the Log Explorer
#
# Outputs one line per source in pipe-delimited format:
#   ARCHIVE|<count>              (if archive has sessions)
#   <project_path>|<count>       (for each project with logs)
#
# Called by view_logs.sh and view_logs.ps1 on the host via:
#   docker compose exec -T daaf-docker bash /daaf/scripts/discover_log_sources.sh
#
# Exit codes:
#   0 — always (empty output means no sources found)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Archive sessions
archive_dir="$REPO_ROOT/.claude/logs/sessions"
if [ -d "$archive_dir" ]; then
    count=$(find "$archive_dir" -maxdepth 1 -name "*_orchestrator.jsonl" 2>/dev/null | wc -l)
    count=$(echo "$count" | tr -d " ")
    if [ "$count" -gt 0 ]; then
        echo "ARCHIVE|$count"
    fi
fi

# Project folders with logs
for d in "$REPO_ROOT"/research/*/logs; do
    [ -d "$d" ] || continue
    count=$(find "$d" -maxdepth 1 -name "*_orchestrator.jsonl" 2>/dev/null | wc -l)
    count=$(echo "$count" | tr -d " ")
    if [ "$count" -gt 0 ]; then
        echo "$(dirname "$d")|$count"
    fi
done
