#!/bin/bash
# Claude Code Session Archiver
# Archives complete session transcripts on session end
#
# This hook reads the full JSONL transcript (which includes ALL assistant
# responses, tool calls, and results) and converts it to readable Markdown.

set -e

# Read JSON input from stdin
INPUT=$(cat)

# Extract session info
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"')
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // ""')
CWD=$(echo "$INPUT" | jq -r '.cwd // "unknown"')
REASON=$(echo "$INPUT" | jq -r '.reason // "unknown"')

# Get project directory
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
ARCHIVE_DIR="$PROJECT_DIR/.claude/logs/sessions"
mkdir -p "$ARCHIVE_DIR"

# Timestamp for archive
TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')
SESSION_SHORT="${SESSION_ID:0:8}"

# Archive paths
JSONL_ARCHIVE="$ARCHIVE_DIR/${TIMESTAMP}_${SESSION_SHORT}.jsonl"
MD_ARCHIVE="$ARCHIVE_DIR/${TIMESTAMP}_${SESSION_SHORT}.md"

# Copy the original JSONL transcript if it exists
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
    cp "$TRANSCRIPT_PATH" "$JSONL_ARCHIVE"

    # Convert JSONL to Markdown for human readability
    {
        echo "# Claude Code Session Log"
        echo ""
        echo "**Session ID:** $SESSION_ID"
        echo "**Date:** $(date '+%Y-%m-%d %H:%M:%S')"
        echo "**Directory:** $CWD"
        echo "**End Reason:** $REASON"
        echo ""
        echo "---"
        echo ""

        # Process each line of the JSONL
        while IFS= read -r line; do
            # Skip empty lines
            [ -z "$line" ] && continue

            # Extract message info
            ROLE=$(echo "$line" | jq -r '.message.role // empty')
            TIMESTAMP_MSG=$(echo "$line" | jq -r '.timestamp // empty')

            # Skip if no role (might be metadata line)
            [ -z "$ROLE" ] && continue

            # Format timestamp
            if [ -n "$TIMESTAMP_MSG" ]; then
                TIME_DISPLAY=$(echo "$TIMESTAMP_MSG" | cut -d'T' -f2 | cut -d'.' -f1)
            else
                TIME_DISPLAY=""
            fi

            if [ "$ROLE" = "user" ]; then
                echo "## 👤 User"
                [ -n "$TIME_DISPLAY" ] && echo "**Time:** $TIME_DISPLAY"
                echo ""

                # Extract text content
                echo "$line" | jq -r '.message.content[] | select(.type == "text") | .text // empty' 2>/dev/null | while IFS= read -r text; do
                    [ -n "$text" ] && echo "$text"
                done
                echo ""

            elif [ "$ROLE" = "assistant" ]; then
                echo "## 🤖 Assistant"
                [ -n "$TIME_DISPLAY" ] && echo "**Time:** $TIME_DISPLAY"
                echo ""

                # Extract text content
                TEXT_CONTENT=$(echo "$line" | jq -r '.message.content[] | select(.type == "text") | .text // empty' 2>/dev/null)
                if [ -n "$TEXT_CONTENT" ]; then
                    echo "$TEXT_CONTENT"
                    echo ""
                fi

                # Extract tool uses
                echo "$line" | jq -c '.message.content[] | select(.type == "tool_use")' 2>/dev/null | while IFS= read -r tool; do
                    [ -z "$tool" ] && continue
                    TOOL_NAME=$(echo "$tool" | jq -r '.name // "unknown"')
                    echo "### 🔧 Tool: $TOOL_NAME"
                    echo ""

                    # Show relevant tool input based on tool type
                    case "$TOOL_NAME" in
                        Bash)
                            CMD=$(echo "$tool" | jq -r '.input.command // ""' | head -c 1000)
                            echo '```bash'
                            echo "$CMD"
                            echo '```'
                            ;;
                        Edit|Write)
                            FILE=$(echo "$tool" | jq -r '.input.file_path // ""')
                            echo "**File:** \`$FILE\`"
                            ;;
                        Read)
                            FILE=$(echo "$tool" | jq -r '.input.file_path // ""')
                            echo "**File:** \`$FILE\`"
                            ;;
                        Task)
                            DESC=$(echo "$tool" | jq -r '.input.description // ""')
                            TYPE=$(echo "$tool" | jq -r '.input.subagent_type // ""')
                            echo "**Type:** $TYPE  "
                            echo "**Task:** $DESC"
                            ;;
                        *)
                            echo '```json'
                            echo "$tool" | jq -r '.input' 2>/dev/null | head -c 500
                            echo '```'
                            ;;
                    esac
                    echo ""
                done

                # Show token usage if available
                USAGE=$(echo "$line" | jq -r '.message.usage // empty')
                if [ -n "$USAGE" ] && [ "$USAGE" != "null" ]; then
                    INPUT_TOKENS=$(echo "$line" | jq -r '.message.usage.input_tokens // 0')
                    OUTPUT_TOKENS=$(echo "$line" | jq -r '.message.usage.output_tokens // 0')
                    if [ "$INPUT_TOKENS" != "0" ] || [ "$OUTPUT_TOKENS" != "0" ]; then
                        echo "*Tokens: in=$INPUT_TOKENS, out=$OUTPUT_TOKENS*"
                        echo ""
                    fi
                fi
            fi

            echo "---"
            echo ""

        done < "$JSONL_ARCHIVE"

        echo ""
        echo "## 📊 Session Summary"
        echo ""
        echo "**Total messages:** $(wc -l < "$JSONL_ARCHIVE")"
        echo "**Archive:** \`$JSONL_ARCHIVE\`"

    } > "$MD_ARCHIVE"

    echo "Session archived: $MD_ARCHIVE"
else
    echo "No transcript found at: $TRANSCRIPT_PATH"
fi

exit 0
