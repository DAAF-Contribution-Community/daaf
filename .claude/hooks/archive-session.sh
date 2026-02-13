#!/bin/bash                                                                                                                                 
# Claude Code Session Archiver                                                                             
# Archives complete session transcripts on session end                                                                                      
#                                                                                                          
# This hook reads the full JSONL transcript (which includes ALL assistant                                                                   
# responses, tool calls, and results) and converts it to readable Markdown.                                                                 
#                                                                                                                                           
# Performance: Uses a single jq invocation per JSONL line via a precompiled
# jq program file (vs 10-15 spawns per line in the naive approach). Maintains
# streaming line-by-line processing for fail-open resilience.

# Fail OPEN: archival is observability-only, not a security gate.
# A malformed JSONL line should produce a gap in the archive, not kill it entirely.
trap '' ERR

# Read JSON input from stdin
INPUT=$(cat)

# Extract session info — single jq call for all 4 fields
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

# Extract provenance metadata before archiving
DAAF_VERSION=$(git -C "$PROJECT_DIR" describe --always --dirty 2>/dev/null || echo "unknown")
MODEL="unknown"
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
    MODEL=$(jq -r 'select(.message.model) | .message.model' "$TRANSCRIPT_PATH" 2>/dev/null | head -1)
    [ -z "$MODEL" ] && MODEL="unknown"
fi

# Archive paths
JSONL_ARCHIVE="$ARCHIVE_DIR/${TIMESTAMP}_${SESSION_SHORT}.jsonl"
MD_ARCHIVE="$ARCHIVE_DIR/${TIMESTAMP}_${SESSION_SHORT}.md"

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
    # Tool results — compact rendering, no separator
    ([.message.content[] | select(.type == "tool_result") | render_tool_result]
      | join("\n"))
  else
    # Real user message — with separator
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

        # Process each line — ONE jq call per line using precompiled program
        while IFS= read -r line; do
            [ -z "$line" ] && continue
            printf '%s\n' "$line" | jq -r -f "$JQ_PROG" 2>/dev/null \
                || echo "*(skipped malformed entry)*"
        done < "$JSONL_ARCHIVE"

        echo ""
        echo "## 📊 Session Summary"
        echo ""
        echo "**Total messages:** $(wc -l < "$JSONL_ARCHIVE")"
        echo "**Model:** $MODEL"
        echo "**DAAF Version:** $DAAF_VERSION"
        echo "**Archive:** \`$JSONL_ARCHIVE\`"

    } > "$MD_ARCHIVE"

    echo "Session archived: $MD_ARCHIVE"
else
    echo "No transcript found at: $TRANSCRIPT_PATH"
fi

exit 0