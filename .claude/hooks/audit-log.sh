#!/bin/bash
# audit-log.sh — PostToolUse hook that logs every tool invocation
#
# Creates an append-only JSONL audit trail at .claude/logs/audit.jsonl.
# Each entry records: timestamp, session ID, tool name, and a summary of
# what was targeted (command for Bash, file path for Read/Write/Edit, etc.).
#
# This is invaluable for:
#   - Post-session review by instructors or supervisors
#   - Debugging what went wrong if something breaks
#   - Accountability in shared environments
#
# Exit codes:
#   0 = always (PostToolUse hooks must never block execution)
#
# Hook event: PostToolUse (matcher: "")
# Registered in: .claude/settings.json

INPUT=$(cat)

# Parse fields from the hook JSON
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"' 2>/dev/null) || TOOL_NAME="unknown"
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"' 2>/dev/null) || SESSION_ID="unknown"
TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

# DAAF version (git commit hash)
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
DAAF_VERSION=$(git -C "$PROJECT_DIR" describe --always --dirty 2>/dev/null || echo "unknown")

# Model (from context-reporter cache, populated after first assistant response)
MODEL_CACHE="/tmp/claude-model-${SESSION_ID}"
MODEL=$(cat "$MODEL_CACHE" 2>/dev/null || echo "unknown")

# Extract a human-readable target depending on the tool type
case "$TOOL_NAME" in
    Bash)
        TARGET=$(echo "$INPUT" | jq -r '.tool_input.command // "" | .[0:200]' 2>/dev/null) || TARGET=""
        ;;
    Read|Write|Edit)
        TARGET=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""' 2>/dev/null) || TARGET=""
        ;;
    Glob)
        TARGET=$(echo "$INPUT" | jq -r '.tool_input.pattern // ""' 2>/dev/null) || TARGET=""
        ;;
    Grep)
        TARGET=$(echo "$INPUT" | jq -r '.tool_input.pattern // ""' 2>/dev/null) || TARGET=""
        ;;
    Task)
        TARGET=$(echo "$INPUT" | jq -r '.tool_input.description // ""' 2>/dev/null) || TARGET=""
        ;;
    WebFetch)
        TARGET=$(echo "$INPUT" | jq -r '.tool_input.url // ""' 2>/dev/null) || TARGET=""
        ;;
    *)
        TARGET=""
        ;;
esac

# Determine log directory relative to project root
if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then
    LOG_DIR="$CLAUDE_PROJECT_DIR/.claude/logs"
else
    # Fallback: use script's own location to find project root
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    LOG_DIR="$(dirname "$SCRIPT_DIR")/logs"
fi

mkdir -p "$LOG_DIR" 2>/dev/null

# Append a JSON line to the audit log
LOG_FILE="$LOG_DIR/audit.jsonl"
jq -n -c \
    --arg ts "$TIMESTAMP" \
    --arg sid "$SESSION_ID" \
    --arg tool "$TOOL_NAME" \
    --arg target "$TARGET" \
    --arg ver "$DAAF_VERSION" \
    --arg model "$MODEL" \
    '{timestamp: $ts, session_id: $sid, tool: $tool, target: $target, daaf_version: $ver, model: $model}' \
    >> "$LOG_FILE" 2>/dev/null

exit 0
