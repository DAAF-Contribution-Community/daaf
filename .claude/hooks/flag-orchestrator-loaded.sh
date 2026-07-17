#!/usr/bin/env bash
# flag-orchestrator-loaded.sh — Set flag when daaf-orchestrator skill loads
#
# Hook: PostToolUse (matcher: "Skill")
#
# After the Skill tool completes, checks if the skill was daaf-orchestrator.
# If so, writes a session-scoped flag file that remind-orchestrator.sh checks
# to stop issuing reminders.
#
# Flag location — persistent home volume, NOT /tmp (changed 2026-07-15):
#   See remind-orchestrator.sh header for the full rationale. Short version:
#   transcripts (~/.claude, claude-config volume) survive container rebuilds
#   and resumed sessions reuse their original session_id, so the "skill
#   already loaded" flag must survive rebuilds too. The old /tmp flag was
#   wiped by every rebuild, causing a redundant skill re-load on the first
#   prompt of every resumed session.
#
# Housekeeping: flags older than 30 days are pruned at write time (i.e., once
# per session, when the skill loads — negligible cost). 30 days matches Claude
# Code's default transcript retention (cleanupPeriodDays): a session whose
# transcript has been cleaned up can no longer be resumed, so its flag is dead
# weight. A pruned-too-early flag is harmless — the reminder simply fires once
# more on that session's next resume.
#
# Exit codes:
#   0 = always (never block tool execution)

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "default"' 2>/dev/null) || SESSION_ID="default"
SKILL_NAME=$(echo "$INPUT" | jq -r '.tool_input.skill // empty' 2>/dev/null) || SKILL_NAME=""

STATE_DIR="${HOME}/.claude/daaf-state"

if [[ "$SKILL_NAME" == "daaf-orchestrator" ]]; then
    mkdir -p "$STATE_DIR" 2>/dev/null
    touch "${STATE_DIR}/orchestrator-loaded-${SESSION_ID}"
    # Prune stale flags (see Housekeeping above). -maxdepth 1 keeps this
    # scoped to the state dir itself; pattern-anchored so nothing else in
    # daaf-state is ever touched.
    find "$STATE_DIR" -maxdepth 1 -name 'orchestrator-loaded-*' -type f -mtime +30 -delete 2>/dev/null
fi

exit 0
