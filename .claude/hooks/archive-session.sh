#!/usr/bin/env bash
# Claude Code Session Archiver
# Archives complete session transcripts on session end
#
# This hook reads the full JSONL transcript (which includes ALL assistant
# responses, tool calls, and results) and converts it to readable Markdown.
#
# Performance: Uses a single jq invocation per JSONL file. The jq program
# processes each top-level JSON object in the JSONL stream independently,
# converting the entire transcript in one process spawn.
#
# Subagent archiving: Discovers subagent transcripts directly from Claude
# Code's raw file hierarchy ({session-uuid}/subagents/), reading agent
# metadata from .meta.json files alongside each transcript. This replaces
# the previous registry-based approach and works for both normal archiving
# and crash recovery (where no registry would exist).
#
# Idempotency: Uses file-size comparison to skip sessions that have already
# been archived with the same or more content. If the source transcript has
# grown (e.g., a concurrent session was prematurely archived by recovery),
# the old archive is replaced with the complete version.
#
# Timestamp derivation: For recovered sessions (reason="recovered"), the
# archive timestamp is derived from the last entry in the JSONL transcript
# rather than the current wall clock. This ensures recovered archives sort
# chronologically by when the session actually ran, not when recovery
# discovered them. Normal SessionEnd archiving uses wall clock as before.
#
# Archive naming convention:
#   {date}_{time}_{session-short}_orchestrator.jsonl   -- main session transcript
#   {date}_{time}_{session-short}_orchestrator.md      -- human-readable rendering
#   {date}_{time}_{session-short}_subagent_{agent-id-short}.jsonl -- subagent transcripts
#   {date}_{time}_{session-short}_subagent_{agent-id-short}.md   -- subagent human-readable rendering

# Fail OPEN: archival is observability-only, not a security gate.
# A malformed JSONL line should produce a gap in the archive, not kill it entirely.
trap '' ERR

# Read JSON input from stdin
INPUT=$(cat)

# Extract session info -- single jq call for all 4 fields
mapfile -t _meta < <(
    printf '%s' "$INPUT" | jq -r '
        (.session_id // "unknown"),
        (.transcript_path // ""),
        (.cwd // "unknown"),
        (.reason // "unknown")
    ' 2>/dev/null
)
SESSION_ID="${_meta[0]:-unknown}"
TRANSCRIPT_PATH="${_meta[1]:-}"
CWD="${_meta[2]:-unknown}"
REASON="${_meta[3]:-unknown}"

# Get project directory
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
ARCHIVE_DIR="$PROJECT_DIR/.claude/logs/sessions"
mkdir -p "$ARCHIVE_DIR"

# Timestamp for archive
TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')
SESSION_SHORT="${SESSION_ID:0:8}"

# For recovered sessions, derive timestamp from the transcript's last entry
# rather than the current wall clock, so archives sort chronologically by
# when the session actually ran (not when recovery discovered it).
if [ "$REASON" = "recovered" ] && [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
    LAST_TS=$(jq -r '.timestamp // empty' "$TRANSCRIPT_PATH" 2>/dev/null | tail -1)
    if [ -n "$LAST_TS" ]; then
        # Convert ISO timestamp (2026-04-05T14:39:58.123Z) to archive format (2026-04-05_14-39-58)
        # Strip fractional seconds and trailing Z separately to handle both
        # "...58.123Z" and "...58Z" (no fractional seconds) correctly
        RECOVERED_TS=$(echo "$LAST_TS" | sed 's/T/_/; s/\.[0-9]*//; s/Z$//; s/:/-/g')
        [ -n "$RECOVERED_TS" ] && TIMESTAMP="$RECOVERED_TS"
    fi
fi

# Archive filename stem -- orchestrator role suffix
STEM="${TIMESTAMP}_${SESSION_SHORT}_orchestrator"

# --- Idempotency: skip if already archived with same or more content ---
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
    EXISTING_ARCHIVE=$(ls "$ARCHIVE_DIR"/*_${SESSION_SHORT}_orchestrator.jsonl 2>/dev/null | head -1)
    if [ -n "$EXISTING_ARCHIVE" ] && [ -f "$EXISTING_ARCHIVE" ]; then
        SOURCE_SIZE=$(stat -c%s "$TRANSCRIPT_PATH" 2>/dev/null || stat -f%z "$TRANSCRIPT_PATH" 2>/dev/null || echo 0)
        EXISTING_SIZE=$(stat -c%s "$EXISTING_ARCHIVE" 2>/dev/null || stat -f%z "$EXISTING_ARCHIVE" 2>/dev/null || echo 0)
        if [ "$SOURCE_SIZE" -le "$EXISTING_SIZE" ] 2>/dev/null; then
            echo "Session $SESSION_SHORT already archived (${EXISTING_SIZE} bytes), skipping."
            # Still process pending log collection before exiting
            PENDING_FILE="$PROJECT_DIR/.claude/logs/pending_log_collection.jsonl"
            if [ -f "$PENDING_FILE" ]; then
                PENDING_TMP="${PENDING_FILE}.processing.$$"
                if mv "$PENDING_FILE" "$PENDING_TMP" 2>/dev/null; then
                    # Re-derive the existing archive paths for pending collection
                    JSONL_ARCHIVE="$EXISTING_ARCHIVE"
                    while IFS= read -r entry; do
                        [ -z "$entry" ] && continue
                        P_BASENAME=$(printf '%s' "$entry" | jq -r '.project_basename // empty' 2>/dev/null)
                        P_PATH=$(printf '%s' "$entry" | jq -r '.project_path // empty' 2>/dev/null)
                        [ -z "$P_BASENAME" ] || [ -z "$P_PATH" ] || [ ! -d "$P_PATH" ] && continue
                        if grep -q -- "$P_BASENAME" "$JSONL_ARCHIVE" 2>/dev/null; then
                            DEST="$P_PATH/logs"
                            mkdir -p "$DEST"
                            for src in "$ARCHIVE_DIR"/*_${SESSION_SHORT}_*.jsonl "$ARCHIVE_DIR"/*_${SESSION_SHORT}_*.md; do
                                [ -f "$src" ] || continue
                                tgt="$DEST/$(basename "$src")"
                                [ -f "$tgt" ] || cp "$src" "$tgt" 2>/dev/null
                            done
                        fi
                    done < "$PENDING_TMP"
                    rm -f "$PENDING_TMP" 2>/dev/null
                fi
            fi
            exit 0
        fi
        # Source is larger -- remove stale archive set before re-archiving
        OLD_STEM=$(basename "$EXISTING_ARCHIVE" .jsonl)
        rm -f "$ARCHIVE_DIR/${OLD_STEM}.jsonl" "$ARCHIVE_DIR/${OLD_STEM}.md" 2>/dev/null
        rm -f "$ARCHIVE_DIR"/*_${SESSION_SHORT}_subagent_*.jsonl "$ARCHIVE_DIR"/*_${SESSION_SHORT}_subagent_*.md 2>/dev/null
    fi
fi

# Extract provenance metadata before archiving
DAAF_VERSION=$(git -C "$PROJECT_DIR" describe --always --dirty 2>/dev/null || echo "unknown")
MODEL="unknown"
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
    MODEL=$(jq -r 'select(.message.model) | .message.model' "$TRANSCRIPT_PATH" 2>/dev/null | head -1)
    [ -z "$MODEL" ] && MODEL="unknown"
fi

# Archive paths
JSONL_ARCHIVE="$ARCHIVE_DIR/${STEM}.jsonl"
MD_ARCHIVE="$ARCHIVE_DIR/${STEM}.md"

# Copy the original JSONL transcript if it exists
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
    cp "$TRANSCRIPT_PATH" "$JSONL_ARCHIVE"

    # Write jq formatting program to temp file (created once, reused per line)
    JQ_PROG=$(mktemp)
    cleanup() { rm -f "$JQ_PROG"; }
    trap cleanup EXIT

    cat > "$JQ_PROG" << 'JQEOF'
# --- Helper functions ---

# Truncate with ellipsis (tool results, tool inputs)
def trunc(n):
  if length > n then
    length as $full |
    .[:n] + "\n... (truncated, \($full) chars total)"
  else . end;

# Truncate with italic notice (thinking blocks)
def trunc_italic(n):
  if length > n then
    length as $full |
    .[:n] + "\n*(truncated, \($full) chars total)*"
  else . end;

# Extract HH:MM:SS from ISO timestamp
def time_display:
  if . and . != "" and . != null then
    (split("T") | if length > 1 then .[1] | split(".")[0] else "" end)
  else "" end;

# Render a single tool_result block
def render_tool_result:
  (if .is_error == true then "### ⚠️ Tool Error" else "### 📋 Tool Result" end) +
  "\n\n" +
  (
    (.content |
      if type == "string" then .
      elif type == "array" then
        [.[] | select(.type == "text") | .text] | join("\n")
      else "" end
    ) as $rc |
    if ($rc | length) > 0 then
      "```\n" + ($rc | trunc(1000)) + "\n```"
    else "*(empty result)*" end
  ) + "\n";

# Render a single tool_use block with type-specific formatting
def render_tool_use:
  "### 🔧 Tool: \(.name // "unknown")\n\n" +
  (
    if .name == "Bash" then
      "```bash\n" + ((.input.command // "") | trunc(1000)) + "\n```"
    elif (.name == "Edit") or (.name == "Write") then
      "**File:** `\(.input.file_path // "")`"
    elif .name == "Read" then
      "**File:** `\(.input.file_path // "")`"
    elif .name == "Task" then
      "**Type:** \(.input.subagent_type // "")  \n**Task:** \(.input.description // "")"
    else
      "```json\n" + ((.input | tojson) | trunc(500)) + "\n```"
    end
  ) + "\n";

# --- Main entry point (processes one JSONL line) ---

(.message.role // "") as $role |
(.timestamp // "" | time_display) as $time |

if $role == "" then empty

elif $role == "user" then
  (.message.content | type) as $ctype |
  (if $ctype == "array" then
    ([.message.content[] | select(.type == "tool_result")] | length) > 0
  else false end) as $has_tr |

  if $has_tr then
    # Tool results -- compact rendering, no separator
    ([.message.content[] | select(.type == "tool_result") | render_tool_result]
      | join("\n"))
  else
    # Real user message -- with separator
    "## 👤 User\n" +
    (if $time != "" then "**Time:** \($time)\n" else "" end) +
    "\n" +
    (if $ctype == "string" then
       (.message.content // "")
     elif $ctype == "array" then
       ([.message.content[] | select(.type == "text") | .text // ""] | join("\n"))
     else "" end) +
    "\n\n---\n"
  end

elif $role == "assistant" then
  (if (.message.content | type) == "array" then .message.content else [] end) as $blocks |

  "## 🤖 Assistant\n" +
  (if $time != "" then "**Time:** \($time)\n" else "" end) +
  "\n" +

  # Thinking blocks (collapsible, truncated)
  ([$blocks[] | select(.type == "thinking") | .thinking] | join("\n") |
    if length > 0 then
      length as $len |
      "<details>\n<summary>💭 Thinking (\($len) chars)</summary>\n\n" +
      trunc_italic(2000) +
      "\n\n</details>\n\n"
    else "" end) +

  # Text content
  ([$blocks[] | select(.type == "text") | .text // ""] | join("\n") |
    if length > 0 then . + "\n\n" else "" end) +

  # Tool uses
  ([$blocks[] | select(.type == "tool_use") | render_tool_use] | join("\n")) +

  # Token usage
  (if .message.usage != null then
    (.message.usage.input_tokens // 0) as $in |
    (.message.usage.output_tokens // 0) as $out |
    if ($in > 0) or ($out > 0) then
      "*Tokens: in=\($in), out=\($out)*\n\n"
    else "" end
  else "" end) +

  "---\n"

else empty end
JQEOF

    # Convert JSONL to Markdown for human readability
    {
        echo "# Claude Code Session Log"
        echo ""
        echo "**Session ID:** $SESSION_ID"
        echo "**Date:** $(date '+%Y-%m-%d %H:%M:%S')"
        echo "**Directory:** $CWD"
        echo "**DAAF Version:** $DAAF_VERSION"
        echo "**Model:** $MODEL"
        echo "**End Reason:** $REASON"
        echo ""
        echo "---"
        echo ""

        # Process entire JSONL in a single jq invocation
        jq -r -f "$JQ_PROG" "$JSONL_ARCHIVE" 2>/dev/null

        # --- Subagent Activity Section ---
        # Discover subagents from Claude Code's raw file hierarchy
        TRANSCRIPT_DIR=$(dirname "$TRANSCRIPT_PATH")
        SA_DIR="$TRANSCRIPT_DIR/${SESSION_ID}/subagents"

        if [ -d "$SA_DIR" ]; then
            # Collect subagent JSONL files
            SA_JSONL_FILES=()
            for f in "$SA_DIR"/agent-*.jsonl; do
                [ -f "$f" ] && SA_JSONL_FILES+=("$f")
            done

            if [ ${#SA_JSONL_FILES[@]} -gt 0 ]; then
                SUBAGENT_COUNT=${#SA_JSONL_FILES[@]}

                echo ""
                echo "## 🤖 Subagent Activity"
                echo ""
                echo "**Subagents dispatched:** $SUBAGENT_COUNT"
                echo ""
                echo "| Agent Type | Agent ID | Timestamp | Duration | Tool Uses | Archive |"
                echo "|---|---|---|---|---|---|"

                # Build summary table and copy transcripts
                for SA_JSONL in "${SA_JSONL_FILES[@]}"; do
                    # Extract agent ID from filename: agent-{id}.jsonl -> {id}
                    SA_FILENAME=$(basename "$SA_JSONL")
                    SA_ID="${SA_FILENAME#agent-}"
                    SA_ID="${SA_ID%.jsonl}"
                    SA_ID_SHORT="${SA_ID:0:8}"

                    # Read agent type from .meta.json
                    SA_META="${SA_JSONL%.jsonl}.meta.json"
                    if [ -f "$SA_META" ]; then
                        SA_TYPE=$(jq -r '.agentType // "unknown"' "$SA_META" 2>/dev/null)
                    else
                        SA_TYPE="unknown"
                    fi

                    # Extract metrics from transcript in a single jq invocation
                    mapfile -t _sa_metrics < <(
                        jq -s '
                            def tool_count: [.[].message.content[]? | select(.type == "tool_use")] | length;
                            def first_ts: [.[].timestamp // null | select(. != null)] | first // "";
                            def last_ts: [.[].timestamp // null | select(. != null)] | last // "";
                            (tool_count | tostring),
                            first_ts,
                            last_ts
                        ' "$SA_JSONL" 2>/dev/null
                    )
                    SA_TOOLS="${_sa_metrics[0]:-0}"
                    SA_FIRST_TS="${_sa_metrics[1]:-}"
                    SA_LAST_TS="${_sa_metrics[2]:-}"

                    # Compute duration from timestamp difference
                    SA_DUR=0
                    if [ -n "$SA_FIRST_TS" ] && [ -n "$SA_LAST_TS" ] && [ "$SA_FIRST_TS" != "$SA_LAST_TS" ]; then
                        FIRST_EPOCH=$(date -d "$SA_FIRST_TS" '+%s' 2>/dev/null || echo 0)
                        LAST_EPOCH=$(date -d "$SA_LAST_TS" '+%s' 2>/dev/null || echo 0)
                        if [ "$FIRST_EPOCH" -gt 0 ] && [ "$LAST_EPOCH" -gt 0 ] 2>/dev/null; then
                            SA_DUR=$(( (LAST_EPOCH - FIRST_EPOCH) * 1000 ))
                        fi
                    fi

                    # Format duration as human-readable
                    if [ "$SA_DUR" -gt 60000 ] 2>/dev/null; then
                        DUR_HR="$((SA_DUR / 60000))m $((SA_DUR % 60000 / 1000))s"
                    elif [ "$SA_DUR" -gt 0 ] 2>/dev/null; then
                        DUR_HR="$((SA_DUR / 1000))s"
                    else
                        DUR_HR="—"
                    fi

                    # Copy subagent transcript to archive
                    SA_ARCHIVE_NAME="${TIMESTAMP}_${SESSION_SHORT}_subagent_${SA_ID_SHORT}.jsonl"
                    cp "$SA_JSONL" "$ARCHIVE_DIR/$SA_ARCHIVE_NAME" 2>/dev/null
                    ARCHIVE_REF="\`$SA_ARCHIVE_NAME\`"

                    # Generate human-readable MD for subagent transcript
                    # Uses a subshell so stdout goes to the subagent MD file,
                    # not to the parent block's orchestrator MD redirect.
                    SA_MD_ARCHIVE_NAME="${TIMESTAMP}_${SESSION_SHORT}_subagent_${SA_ID_SHORT}.md"
                    (
                        echo "# Subagent Session Log"
                        echo ""
                        echo "**Agent Type:** $SA_TYPE"
                        echo "**Agent ID:** $SA_ID"
                        echo "**Parent Session:** $SESSION_SHORT"
                        echo "**Date:** $(date '+%Y-%m-%d %H:%M:%S')"
                        echo "**DAAF Version:** $DAAF_VERSION"
                        echo ""
                        echo "---"
                        echo ""

                        jq -r -f "$JQ_PROG" "$ARCHIVE_DIR/$SA_ARCHIVE_NAME" 2>/dev/null

                        echo ""
                        echo "## 📊 Subagent Summary"
                        echo ""
                        echo "**Total messages:** $(wc -l < "$ARCHIVE_DIR/$SA_ARCHIVE_NAME")"
                        echo "**Agent Type:** $SA_TYPE"
                        echo "**Archive:** \`$SA_ARCHIVE_NAME\`"
                    ) > "$ARCHIVE_DIR/$SA_MD_ARCHIVE_NAME" 2>/dev/null

                    # Extract time portion from last timestamp
                    SA_TIME=$(echo "$SA_LAST_TS" | sed 's/.*T//' | sed 's/\..*//' | sed 's/Z$//')

                    echo "| $SA_TYPE | $SA_ID_SHORT | $SA_TIME | $DUR_HR | $SA_TOOLS | $ARCHIVE_REF |"
                done

                echo ""

                # Subagent summaries (last_message excerpts)
                for SA_JSONL in "${SA_JSONL_FILES[@]}"; do
                    SA_FILENAME=$(basename "$SA_JSONL")
                    SA_ID="${SA_FILENAME#agent-}"
                    SA_ID="${SA_ID%.jsonl}"
                    SA_ID_SHORT="${SA_ID:0:8}"

                    SA_META="${SA_JSONL%.jsonl}.meta.json"
                    if [ -f "$SA_META" ]; then
                        SA_TYPE=$(jq -r '.agentType // "unknown"' "$SA_META" 2>/dev/null)
                    else
                        SA_TYPE="unknown"
                    fi

                    # Extract last assistant message text
                    SA_MSG=$(jq -r 'select(.message.role == "assistant") | [.message.content[]? | select(.type == "text") | .text // ""] | join(" ")' "$SA_JSONL" 2>/dev/null | tail -1 | tr '\n' ' ')

                    if [ -n "$SA_MSG" ]; then
                        echo "### $SA_TYPE ($SA_ID_SHORT)"
                        echo ""
                        echo "> ${SA_MSG:0:300}"
                        if [ ${#SA_MSG} -gt 300 ]; then
                            echo "> *(truncated -- see full transcript)*"
                        fi
                        echo ""
                    fi
                done
            fi
        fi

        echo ""
        echo "## 📊 Session Summary"
        echo ""
        echo "**Total messages:** $(wc -l < "$JSONL_ARCHIVE")"
        echo "**Model:** $MODEL"
        echo "**DAAF Version:** $DAAF_VERSION"
        echo "**Archive:** \`$JSONL_ARCHIVE\`"


        echo ""
        echo "*Archive completed: $(date '+%Y-%m-%d %H:%M:%S')*"

    } > "$MD_ARCHIVE"

    echo "Session archived: $MD_ARCHIVE"
else
    echo "No transcript found at: $TRANSCRIPT_PATH"
fi

# --- Process pending log collection requests ---
PENDING_FILE="$PROJECT_DIR/.claude/logs/pending_log_collection.jsonl"
if [ -f "$PENDING_FILE" ]; then
    # Atomic move to prevent TOCTOU race with concurrent appenders
    PENDING_TMP="${PENDING_FILE}.processing.$$"
    if mv "$PENDING_FILE" "$PENDING_TMP" 2>/dev/null; then
        while IFS= read -r entry; do
            [ -z "$entry" ] && continue
            P_BASENAME=$(printf '%s' "$entry" | jq -r '.project_basename // empty' 2>/dev/null)
            P_PATH=$(printf '%s' "$entry" | jq -r '.project_path // empty' 2>/dev/null)
            [ -z "$P_BASENAME" ] || [ -z "$P_PATH" ] || [ ! -d "$P_PATH" ] && continue
            # Check if the just-archived transcript references this project
            if [ -f "$JSONL_ARCHIVE" ] && grep -q -- "$P_BASENAME" "$JSONL_ARCHIVE" 2>/dev/null; then
                DEST="$P_PATH/logs"
                mkdir -p "$DEST"
                # Copy orchestrator + subagent archives (idempotent -- skip existing)
                for src in "$ARCHIVE_DIR"/*_${SESSION_SHORT}_*.jsonl "$ARCHIVE_DIR"/*_${SESSION_SHORT}_*.md; do
                    [ -f "$src" ] || continue
                    tgt="$DEST/$(basename "$src")"
                    [ -f "$tgt" ] || cp "$src" "$tgt" 2>/dev/null
                done
            fi
        done < "$PENDING_TMP"
        rm -f "$PENDING_TMP" 2>/dev/null
    fi
fi

exit 0
