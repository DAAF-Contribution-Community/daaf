#!/usr/bin/env bash
# recover-session-logs.sh -- SessionStart hook: activity logging + crash recovery
#
# Replaces the previous inline SessionStart command. Performs:
#   1. Original work: mkdir -p + activity.log append
#   2. Background recovery: reconciles Claude Code's raw transcript storage
#      against DAAF's archive directory, archiving any missed sessions
#
# Recovery approach:
#   - Derives the Claude Code transcript directory from the current session's
#     transcript_path (a common field available in all hook events)
#   - Builds an index of already-archived session IDs with their file sizes
#   - Scans for raw transcripts newer than the last recovery timestamp
#   - For each unarchived (or grown) transcript, pipes a synthesized JSON
#     payload to archive-session.sh, reusing all existing archiving logic
#   - archive-session.sh's idempotency guard handles concurrent sessions:
#     if a session is still running and its transcript grows, the next
#     archive invocation (SessionEnd or recovery) will re-archive it
#
# Also processes stale pending log collection markers left by
# collect_session_logs.sh if archive-session.sh didn't process them
# (e.g., the session that wrote the marker crashed before SessionEnd).
#
# Performance:
#   - Timestamp-gated: only processes transcripts modified since last recovery
#   - Index-based matching: O(n+m) via bash associative array, not O(n*m) globs
#   - Background execution: recovery runs in a detached subprocess so session
#     startup is never blocked (foreground work completes in <1s)
#
# Exit codes:
#   0 = always (observability hook, must never block session start)
#
# Hook event: SessionStart (matcher: "")
# Registered in: .claude/settings.json

# Fail OPEN: session start is observability, not a security gate
trap '' ERR

INPUT=$(cat)

# Parse session metadata from JSON input
mapfile -t _meta < <(
    printf '%s' "$INPUT" | jq -r '
        (.session_id // "unknown"),
        (.transcript_path // ""),
        (.cwd // "unknown")
    ' 2>/dev/null
)
SESSION_ID="${_meta[0]:-unknown}"
TRANSCRIPT_PATH="${_meta[1]:-}"
CWD="${_meta[2]:-unknown}"

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
LOG_DIR="$PROJECT_DIR/.claude/logs"
ARCHIVE_DIR="$LOG_DIR/sessions"

# --- Section 1: Original SessionStart work ---
mkdir -p "$LOG_DIR"
mkdir -p "$ARCHIVE_DIR"
DAAF_VERSION=$(git -C "$PROJECT_DIR" describe --always --dirty 2>/dev/null || echo "unknown")
echo "Session started: $(date '+%Y-%m-%d %H:%M:%S') | DAAF: $DAAF_VERSION | Session: ${SESSION_ID:0:8}" >> "$LOG_DIR/activity.log"

# --- Section 2: Background recovery ---
# Only attempt recovery if we have a transcript_path to derive the source directory
if [ -n "$TRANSCRIPT_PATH" ]; then
    CURRENT_SHORT="${SESSION_ID:0:8}"

    (
        TRANSCRIPT_DIR=$(dirname "$TRANSCRIPT_PATH")

        # Bail if transcript directory doesn't exist
        [ -d "$TRANSCRIPT_DIR" ] || exit 0

        # Build index of already-archived session shorts with their file sizes
        # This is a single directory read -- O(m) where m = archived sessions
        declare -A ARCHIVED_SIZE
        for f in "$ARCHIVE_DIR"/*_orchestrator.jsonl; do
            [ -f "$f" ] || continue
            short=$(basename "$f" | sed 's/.*_\([a-f0-9]\{8\}\)_orchestrator\.jsonl/\1/')
            [ -n "$short" ] || continue
            ARCHIVED_SIZE["$short"]=$(stat -c%s "$f" 2>/dev/null || echo 0)
        done

        # Timestamp-gated scan: only process transcripts newer than last recovery
        LAST_RECOVERY="$LOG_DIR/.last_recovery"
        FIND_ARGS=(-maxdepth 1 -name "*.jsonl")
        [ -f "$LAST_RECOVERY" ] && FIND_ARGS+=(-newer "$LAST_RECOVERY")

        RECOVERED=0
        SKIPPED=0

        while IFS= read -r raw; do
            [ -f "$raw" ] || continue
            uuid=$(basename "$raw" .jsonl)
            short="${uuid:0:8}"

            # Skip the current session -- it just started
            [ "$short" = "$CURRENT_SHORT" ] && continue

            RAW_SIZE=$(stat -c%s "$raw" 2>/dev/null || echo 0)

            # Skip if already archived with same or larger size
            if [ -n "${ARCHIVED_SIZE[$short]+x}" ]; then
                if [ "$RAW_SIZE" -le "${ARCHIVED_SIZE[$short]}" ] 2>/dev/null; then
                    SKIPPED=$((SKIPPED + 1))
                    continue
                fi
            fi

            # Archive this session by piping synthesized JSON to archive-session.sh
            # archive-session.sh's own idempotency guard provides a second safety net
            jq -n \
                --arg session_id "$uuid" \
                --arg transcript_path "$raw" \
                --arg cwd "$PROJECT_DIR" \
                --arg reason "recovered" \
                '{"session_id": $session_id, "transcript_path": $transcript_path, "cwd": $cwd, "reason": $reason}' \
                | "$PROJECT_DIR/.claude/hooks/archive-session.sh" 2>/dev/null

            RECOVERED=$((RECOVERED + 1))
        done < <(find "$TRANSCRIPT_DIR" "${FIND_ARGS[@]}" 2>/dev/null)

        # Update recovery timestamp
        touch "$LAST_RECOVERY"

        # Log recovery activity
        if [ $RECOVERED -gt 0 ]; then
            echo "$(date '+%Y-%m-%d %H:%M:%S') RECOVERY: archived $RECOVERED session(s), skipped $SKIPPED" >> "$LOG_DIR/activity.log"
        fi

        # --- Process stale pending log collection markers ---
        PENDING_FILE="$LOG_DIR/pending_log_collection.jsonl"
        if [ -f "$PENDING_FILE" ]; then
            PENDING_TMP="${PENDING_FILE}.recovery.$$"
            if mv "$PENDING_FILE" "$PENDING_TMP" 2>/dev/null; then
                while IFS= read -r entry; do
                    [ -z "$entry" ] && continue
                    P_BASENAME=$(printf '%s' "$entry" | jq -r '.project_basename // empty' 2>/dev/null)
                    P_PATH=$(printf '%s' "$entry" | jq -r '.project_path // empty' 2>/dev/null)
                    [ -z "$P_BASENAME" ] || [ -z "$P_PATH" ] || [ ! -d "$P_PATH" ] && continue

                    DEST="$P_PATH/logs"
                    mkdir -p "$DEST"

                    # Search all archived orchestrator transcripts for this project
                    for arc in "$ARCHIVE_DIR"/*_orchestrator.jsonl; do
                        [ -f "$arc" ] || continue
                        if grep -q -- "$P_BASENAME" "$arc" 2>/dev/null; then
                            arc_short=$(basename "$arc" | sed 's/.*_\([a-f0-9]\{8\}\)_orchestrator\.jsonl/\1/')
                            for src in "$ARCHIVE_DIR"/*_${arc_short}_*.jsonl "$ARCHIVE_DIR"/*_${arc_short}_*.md; do
                                [ -f "$src" ] || continue
                                tgt="$DEST/$(basename "$src")"
                                [ -f "$tgt" ] || cp "$src" "$tgt" 2>/dev/null
                            done
                        fi
                    done
                done < "$PENDING_TMP"
                rm -f "$PENDING_TMP" 2>/dev/null
            fi
        fi

    ) </dev/null >/dev/null 2>&1 &
    disown
fi

exit 0
