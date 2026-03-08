#!/bin/bash
# md-outline.sh — Extract heading outline with line numbers from Markdown files
#
# Usage: bash .claude/scripts/md-outline.sh <file.md>
#
# Outputs ATX headings (#–######) with their line numbers, plus a single
# [frontmatter] entry if YAML frontmatter is present. Correctly skips
# headings inside fenced code blocks (``` and ~~~).
#
# Designed for agent workflows: run this first to see document structure,
# then use Read with offset/limit to fetch only the sections you need.

set -euo pipefail

if [[ $# -lt 1 || "$1" == "-h" || "$1" == "--help" ]]; then
    echo "Usage: bash $(basename "$0") <file.md>"
    echo ""
    echo "Extract a heading outline with line numbers from a Markdown file."
    exit 1
fi

FILE="$1"

if [[ ! -f "$FILE" ]]; then
    echo "Error: file not found: $FILE" >&2
    exit 1
fi

awk '
BEGIN {
    state = "NORMAL"
    fence_char = ""
    fence_count = 0
    fm_start = 0
}

# --- Frontmatter detection (only valid at very start of file) ---
state == "NORMAL" && NR <= 2 && /^---[[:space:]]*$/ {
    state = "FRONTMATTER"
    fm_start = NR
    next
}

state == "FRONTMATTER" && /^---[[:space:]]*$/ {
    printf "%3d-%d:  [frontmatter]\n", fm_start, NR
    state = "NORMAL"
    next
}

state == "FRONTMATTER" { next }

# --- Fenced code block open (backticks or tildes) ---
state == "NORMAL" && /^```/ {
    # Count the backticks
    match($0, /^`+/)
    fence_count = RLENGTH
    fence_char = "`"
    state = "FENCED"
    next
}

state == "NORMAL" && /^~~~/ {
    match($0, /^~+/)
    fence_count = RLENGTH
    fence_char = "~"
    state = "FENCED"
    next
}

# --- Fenced code block close ---
state == "FENCED" && fence_char == "`" && /^`+[[:space:]]*$/ {
    match($0, /^`+/)
    if (RLENGTH >= fence_count) {
        state = "NORMAL"
        fence_char = ""
        fence_count = 0
    }
    next
}

state == "FENCED" && fence_char == "~" && /^~+[[:space:]]*$/ {
    match($0, /^~+/)
    if (RLENGTH >= fence_count) {
        state = "NORMAL"
        fence_char = ""
        fence_count = 0
    }
    next
}

state == "FENCED" { next }

# --- ATX headings (only in NORMAL state) ---
# Note: avoid {1,6} interval expression — mawk does not support it.
# Instead, match any leading #, count them, and verify 1-6 + trailing space.
state == "NORMAL" && /^#/ {
    match($0, /^#+/)
    level = RLENGTH
    if (level >= 1 && level <= 6 && substr($0, level + 1, 1) == " ") {
        printf "%4d:  %s\n", NR, $0
    }
}
' "$FILE"
