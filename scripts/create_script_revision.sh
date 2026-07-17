#!/usr/bin/env bash
# =============================================================================
# create_script_revision.sh - Create a clean revision of an executed script
# =============================================================================
#
# Usage: ./scripts/create_script_revision.sh <source_script> <destination_script>
#
# Supported languages: Python (.py), R (.R / .r)
#
# WHY THIS EXISTS
#   DAAF's immutable-versioning rule says: when a script fails, never modify it
#   in place. Create a NEW versioned copy (`_a`, `_b`, ...), apply fixes there,
#   and execute the new copy via run_with_capture.sh. A plain `cp` of an
#   already-executed script does NOT work: run_with_capture.sh appends an
#   execution-log block marked by a line matching `^# EXECUTION LOG`, and a `cp`
#   drags that marker into the copy. The wrapper then refuses to run the copy
#   (its re-run guard fires on the marker). This utility is the sanctioned
#   revision mechanism: it copies the ORIGINAL code and strips the appended
#   execution-log block, so the revision starts clean and runs.
#
# BEHAVIOR
#   1. The source must exist and be readable.
#   2. The destination must NOT already exist (immutable versioning never
#      overwrites — every version is preserved).
#   3. The source and destination must share the same extension.
#   4. If the source carries an execution log (a `^# EXECUTION LOG` line), only
#      the code ABOVE the appended log block is written to the destination (the
#      banner separator immediately above the marker and the trailing blank
#      lines the wrapper inserted are removed, so the file ends cleanly). The
#      destination is then verified to contain no `^# EXECUTION LOG` line.
#   5. If the source has NO execution log (a never-executed script), the whole
#      file is copied verbatim and an informational note is printed.
#   6. The source is never modified.
#
# The marker (`^# EXECUTION LOG`) and its banner are exactly what
# run_with_capture.sh appends; keep this utility in sync with that wrapper.
#
# Examples:
#   ./scripts/create_script_revision.sh \
#       research/.../scripts/stage5_fetch/01_fetch-ccd.py \
#       research/.../scripts/stage5_fetch/01_fetch-ccd_a.py
#   ./scripts/create_script_revision.sh 01_join.R 01_join_a.R
#
# =============================================================================

# -e: exit on error; -u: catch unset variables; -o pipefail: catch pipe failures.
set -euo pipefail

SRC="${1:-}"
DEST="${2:-}"

if [ -z "$SRC" ] || [ -z "$DEST" ]; then
    echo "Usage: $0 <source_script> <destination_script>" >&2
    echo "Example: $0 01_fetch-ccd.py 01_fetch-ccd_a.py" >&2
    exit 1
fi

# --- Source must exist and be readable ---------------------------------------
if [ ! -f "$SRC" ]; then
    echo "Error: Source script not found: $SRC" >&2
    exit 1
fi
if [ ! -r "$SRC" ]; then
    echo "Error: Source script is not readable: $SRC" >&2
    exit 1
fi

# --- Destination must NOT already exist (never overwrite a version) ----------
if [ -e "$DEST" ]; then
    echo "Error: Destination already exists: $DEST" >&2
    echo "Immutable versioning never overwrites an existing version." >&2
    echo "Choose the next unused suffix (_a, _b, _c, ...)." >&2
    exit 1
fi

# --- Source and destination must share the same extension --------------------
SRC_EXT="${SRC##*.}"
DEST_EXT="${DEST##*.}"
case "$SRC_EXT" in
    py|R|r) ;;
    *)
        echo "Error: Unsupported source extension: .$SRC_EXT" >&2
        echo "Supported: .py (Python), .R / .r (R)" >&2
        exit 1
        ;;
esac
if [ "$SRC_EXT" != "$DEST_EXT" ]; then
    echo "Error: Extension mismatch: source is .$SRC_EXT but destination is .$DEST_EXT" >&2
    echo "A revision must keep the same language/extension as its source." >&2
    exit 1
fi

# --- Strip the execution log (if present) or copy verbatim -------------------
# Write to a temp file in the DESTINATION directory first, then mv into place.
# This keeps destination creation atomic: an interrupted, failed, or rejected
# write never leaves a partially-written file at $DEST (mv is the only step that
# creates it, and mv within one filesystem is atomic). The EXIT trap removes the
# temp file on every exit path — including the marker-survival refusal below —
# and becomes a harmless no-op once the temp file has been mv'd away.
DEST_DIR=$(dirname "$DEST")
TMP_DEST=$(mktemp "${DEST_DIR}/.create_script_revision.XXXXXX")
trap 'rm -f "$TMP_DEST"' EXIT

if grep -q "^# EXECUTION LOG" "$SRC"; then
    # Source has an appended execution log. Write only the code above the log
    # block. The wrapper's block is:  <blank><blank># ===...# EXECUTION LOG...
    # so the marker line's banner separator sits at (marker-1) and the two blank
    # lines it inserted at (marker-2)/(marker-3). Emit lines strictly above the
    # separator, then drop trailing blank lines so the revision ends cleanly.
    awk '
        { line[NR] = $0 }
        /^# EXECUTION LOG/ && !found { found = 1; mrk = NR }
        END {
            hi = mrk - 2
            if (hi < 0) hi = 0
            p = 0
            for (i = 1; i <= hi; i++) {
                if (line[i] ~ /[^[:space:]]/) p = i
            }
            for (i = 1; i <= p; i++) print line[i]
        }
    ' "$SRC" > "$TMP_DEST"

    # Verify the appended log did not survive the strip.
    if grep -q "^# EXECUTION LOG" "$TMP_DEST"; then
        echo "Error: Execution-log marker still present after strip: $DEST" >&2
        echo "Refusing to leave a marker-bearing revision (run_with_capture.sh would refuse it)." >&2
        exit 1
    fi

    mv "$TMP_DEST" "$DEST"
    echo "Created revision (execution log stripped): $DEST"
else
    # No execution log: a never-executed source. Copy the whole file verbatim.
    cp "$SRC" "$TMP_DEST"
    mv "$TMP_DEST" "$DEST"
    echo "Created revision (source had no execution log; copied verbatim): $DEST"
fi

echo ""
echo "Next steps:"
echo "  1. Edit $DEST with your fixes."
echo "  2. Execute the new version:"
echo "     bash /daaf/scripts/run_with_capture.sh $DEST"
echo ""
echo "The source ($SRC) was not modified; all versions are preserved for the audit trail."

exit 0
