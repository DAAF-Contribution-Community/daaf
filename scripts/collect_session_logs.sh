#!/usr/bin/env bash
# collect_session_logs.sh — Collect session transcripts relevant to a DAAF project
#
# Searches global session archives (.claude/logs/sessions/) for references to a
# specific project folder, then copies matching JSONL + MD transcript pairs into
# the project's logs/ directory.
#
# Usage:
#   bash /daaf/scripts/collect_session_logs.sh /daaf/research/YYYY-MM-DD_Title
#
# Design:
#   - Session-grouped matching: greps only orchestrator (*_orchestrator.jsonl)
#     archives for the project BASENAME, then collects ALL archives from each
#     matching session (orchestrator + subagents) via session-short ID glob.
#     This ensures subagent transcripts are collected even if they don't
#     individually mention the project directory (e.g., search-agent exploring
#     framework files, source-researcher that never touches project paths).
#   - Uses the project folder BASENAME as the search term (not the full path),
#     so results are stable even if the repo root path changes.
#   - Idempotent: skips files already present in the destination.
#   - Retrospective: intended to run at project completion (or near-completion)
#     to gather all session transcripts that touched project files.
#
# Exit codes:
#   0 — success (including when no sessions matched)
#   1 — usage error or invalid project path

set -euo pipefail

# --- Validate arguments ---

if [ $# -ne 1 ]; then
    echo "Usage: bash $0 <project_path>"
    echo "Example: bash $0 /daaf/research/2026-01-24_School_Poverty_Analysis"
    exit 1
fi

PROJECT_PATH="$1"

if [ ! -d "$PROJECT_PATH" ]; then
    echo "ERROR: Project directory does not exist: $PROJECT_PATH"
    exit 1
fi

# --- Resolve paths ---

# DAAF repo root: two levels up from this script (scripts/ -> repo root)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SESSIONS_DIR="$REPO_ROOT/.claude/logs/sessions"

if [ ! -d "$SESSIONS_DIR" ]; then
    echo "WARNING: No session archive directory found at $SESSIONS_DIR"
    echo "No sessions to collect."
    exit 0
fi

# Use folder basename as search term (stable across different repo root paths)
PROJECT_BASENAME="$(basename "$PROJECT_PATH")"
DEST_DIR="$PROJECT_PATH/logs"

echo "=== DAAF Session Log Collection ==="
echo "Project:    $PROJECT_BASENAME"
echo "Source:     $SESSIONS_DIR"
echo "Dest:       $DEST_DIR"
echo ""

# --- Search for matching sessions ---

# Search ONLY orchestrator transcripts for the project basename, then collect
# all archives (orchestrator + subagents) from each matching session by
# session-short ID.  This mirrors the session-grouped approach used by
# archive-session.sh and recover-session-logs.sh, ensuring subagent transcripts
# are collected even if they don't individually contain the project basename
# (e.g., search-agent exploring framework files, source-researcher that never
# touches project directories).
MATCHING_SESSIONS=()
while IFS= read -r orch_path; do
    short=$(basename "$orch_path" | sed 's/.*_\([a-f0-9]\{8\}\)_orchestrator\.jsonl/\1/')
    [[ "$short" =~ ^[a-f0-9]{8}$ ]] && MATCHING_SESSIONS+=("$short")
done < <(grep -rl --include="*_orchestrator.jsonl" "$PROJECT_BASENAME" "$SESSIONS_DIR" 2>/dev/null || true)

if [ ${#MATCHING_SESSIONS[@]} -eq 0 ]; then
    echo "No sessions found referencing '$PROJECT_BASENAME'."
    echo "This is expected if the project had no file operations yet (e.g., Phase 1 only)."
    exit 0
fi

echo "Found ${#MATCHING_SESSIONS[@]} session(s) referencing this project."
echo ""

# --- Copy matching sessions ---

mkdir -p "$DEST_DIR"

COPIED=0
SKIPPED=0
TOTAL_SIZE=0

for session_short in "${MATCHING_SESSIONS[@]}"; do
    # Glob all archives from this session (orchestrator + subagents, JSONL + MD)
    for src in "$SESSIONS_DIR"/*_${session_short}_*.jsonl "$SESSIONS_DIR"/*_${session_short}_*.md; do
        [ -f "$src" ] || continue
        filename="$(basename "$src")"

        if [ -f "$DEST_DIR/$filename" ]; then
            SKIPPED=$((SKIPPED + 1))
        else
            cp "$src" "$DEST_DIR/$filename"
            COPIED=$((COPIED + 1))
            size=$(stat -c%s "$src" 2>/dev/null || stat -f%z "$src" 2>/dev/null || echo 0)
            TOTAL_SIZE=$((TOTAL_SIZE + size))
        fi
    done
done

# --- Summary ---

# Convert total size to human-readable
if [ $TOTAL_SIZE -gt 1048576 ]; then
    SIZE_HR="$((TOTAL_SIZE / 1048576)) MB"
elif [ $TOTAL_SIZE -gt 1024 ]; then
    SIZE_HR="$((TOTAL_SIZE / 1024)) KB"
else
    SIZE_HR="$TOTAL_SIZE bytes"
fi

echo "--- Summary ---"
echo "Sessions matched:  ${#MATCHING_SESSIONS[@]}"
echo "Files copied:      $COPIED"
echo "Files skipped:     $SKIPPED (already present)"
echo "Total size copied: $SIZE_HR"
echo "Destination:       $DEST_DIR/"
echo ""

# List copied files
if [ $COPIED -gt 0 ] || [ $SKIPPED -gt 0 ]; then
    echo "Session logs in project:"
    ls -lh "$DEST_DIR"/*.jsonl "$DEST_DIR"/*.md 2>/dev/null | while read -r line; do
        echo "  $line"
    done
fi

# --- Write pending log collection marker for deferred archiving ---
# The current session's archive won't exist yet (SessionEnd hasn't fired).
# Record a marker so archive-session.sh can copy the archive to this project
# when the session ends. If the session crashes, recover-session-logs.sh
# processes stale markers on the next session start.
PENDING_FILE="$REPO_ROOT/.claude/logs/pending_log_collection.jsonl"
jq -n -c \
    --arg pp "$PROJECT_PATH" \
    --arg pb "$PROJECT_BASENAME" \
    --arg ts "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
    '{project_path: $pp, project_basename: $pb, requested_at: $ts}' \
    >> "$PENDING_FILE" 2>/dev/null

echo ""
echo "Pending collection marker written for deferred archiving."
echo "The current session's transcript will be collected when the session ends."
