#!/bin/bash
# Claude Code Session Archiver
# Archives complete session transcripts on session end
#
# This hook reads the full JSONL transcript (which includes ALL assistant
# responses, tool calls, and results) and converts it to readable Markdown.

# Fail OPEN: archival is observability-only, not a security gate.
# A malformed JSONL line should produce a gap in the archive, not kill it entirely.
trap '' ERR

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

        # Process each line of the JSONL
        while IFS= read -r line; do
            # Skip empty lines
            [ -z "$line" ] && continue

            # Extract message info
            ROLE=$(echo "$line" | jq -r '.message.role // empty' 2>/dev/null) || { continue; }
            TIMESTAMP_MSG=$(echo "$line" | jq -r '.timestamp // empty')

            # Skip if no role (metadata, progress, file-history-snapshot lines)
            [ -z "$ROLE" ] && continue

            # Format timestamp
            if [ -n "$TIMESTAMP_MSG" ]; then
                TIME_DISPLAY=$(echo "$TIMESTAMP_MSG" | cut -d'T' -f2 | cut -d'.' -f1)
            else
                TIME_DISPLAY=""
            fi

            # Track entry type for separator logic
            ENTRY_TYPE=""

            if [ "$ROLE" = "user" ]; then
                # Detect tool_result entries (API sends tool results as role=user)
                CONTENT_TYPE=$(echo "$line" | jq -r '.message.content | type' 2>/dev/null)
                HAS_TOOL_RESULT="false"
                if [ "$CONTENT_TYPE" = "array" ]; then
                    TR_COUNT=$(echo "$line" | jq '[.message.content[] | select(.type == "tool_result")] | length' 2>/dev/null)
                    [ "${TR_COUNT:-0}" -gt 0 ] 2>/dev/null && HAS_TOOL_RESULT="true"
                fi

                if [ "$HAS_TOOL_RESULT" = "true" ]; then
                    ENTRY_TYPE="tool_result"
                    # Render tool results compactly (not as "User" message)
                    echo "$line" | jq -c '.message.content[] | select(.type == "tool_result")' 2>/dev/null | while IFS= read -r tr; do
                        [ -z "$tr" ] && continue
                        IS_ERROR=$(echo "$tr" | jq -r '.is_error // false')
                        RESULT_CONTENT=$(echo "$tr" | jq -r '
                            if (.content | type) == "string" then .content
                            elif (.content | type) == "array" then
                                ([.content[] | select(.type == "text") | .text] | join("\n"))
                            else "" end
                        ' 2>/dev/null)
                        RESULT_LEN=${#RESULT_CONTENT}

                        if [ "$IS_ERROR" = "true" ]; then
                            echo "### ⚠️ Tool Error"
                        else
                            echo "### 📋 Tool Result"
                        fi
                        echo ""
                        if [ -n "$RESULT_CONTENT" ]; then
                            echo '```'
                            echo "$RESULT_CONTENT" | head -c 1000
                            if [ "$RESULT_LEN" -gt 1000 ]; then
                                echo ""
                                echo "... (truncated, ${RESULT_LEN} chars total)"
                            fi
                            echo '```'
                        else
                            echo "*(empty result)*"
                        fi
                        echo ""
                    done
                else
                    ENTRY_TYPE="user"
                    echo "## 👤 User"
                    [ -n "$TIME_DISPLAY" ] && echo "**Time:** $TIME_DISPLAY"
                    echo ""

                    # Extract text content
                    if [ "$CONTENT_TYPE" = "string" ]; then
                        USER_TEXT=$(echo "$line" | jq -r '.message.content // empty' 2>/dev/null)
                        [ -n "$USER_TEXT" ] && echo "$USER_TEXT"
                    elif [ "$CONTENT_TYPE" = "array" ]; then
                        echo "$line" | jq -r '.message.content[] | select(.type == "text") | .text // empty' 2>/dev/null | while IFS= read -r text; do
                            [ -n "$text" ] && echo "$text"
                        done
                    fi
                    echo ""
                fi

            elif [ "$ROLE" = "assistant" ]; then
                ENTRY_TYPE="assistant"
                echo "## 🤖 Assistant"
                [ -n "$TIME_DISPLAY" ] && echo "**Time:** $TIME_DISPLAY"
                echo ""

                # Extract thinking blocks (extended thinking)
                THINKING=$(echo "$line" | jq -r '[.message.content[] | select(.type == "thinking") | .thinking] | join("\n")' 2>/dev/null)
                if [ -n "$THINKING" ]; then
                    THINK_LEN=${#THINKING}
                    echo "<details>"
                    echo "<summary>💭 Thinking (${THINK_LEN} chars)</summary>"
                    echo ""
                    echo "$THINKING" | head -c 2000
                    if [ "$THINK_LEN" -gt 2000 ]; then
                        echo ""
                        echo "*(truncated, ${THINK_LEN} chars total)*"
                    fi
                    echo ""
                    echo "</details>"
                    echo ""
                fi

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

            # Section separator — tool results flow without separator to group
            # visually with the preceding tool call
            if [ "$ENTRY_TYPE" = "user" ] || [ "$ENTRY_TYPE" = "assistant" ]; then
                echo "---"
                echo ""
            fi

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
