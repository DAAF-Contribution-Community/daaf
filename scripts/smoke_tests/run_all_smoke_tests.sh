#!/usr/bin/env bash
# scripts/smoke_tests/run_all_smoke_tests.sh
# Executes all R skill smoke tests and reports results

SMOKE_DIR="$(dirname "$0")"
BASE_DIR="$(cd "$SMOKE_DIR/../.." && pwd)"
CAPTURE="$BASE_DIR/scripts/run_with_capture.sh"
PASSED=0
FAILED=0
FAILURES=""

for test_script in "$SMOKE_DIR"/smoke_*.R; do
    basename_noext=$(basename "$test_script" .R)

    # Revision detection: a file is a revision only if it ends in _[a-z] AND
    # the presumed original (with that suffix stripped) actually exists.
    # This prevents skill names containing _r (plotly_r, survey_r) from being
    # misidentified as revisions.
    is_revision=false
    if [[ "$basename_noext" =~ _[a-z]$ ]]; then
        base="${basename_noext%_[a-z]}"
        suffix="${basename_noext##*_}"
        if [ -f "$SMOKE_DIR/${base}.R" ]; then
            is_revision=true
        fi
    fi

    if [ "$is_revision" = true ]; then
        # This is a revision — check if a later revision supersedes it
        next_suffix=$(echo "$suffix" | tr 'a-y' 'b-z')
        if [ -f "$SMOKE_DIR/${base}_${next_suffix}.R" ]; then
            echo "--- Skipping $basename_noext (superseded by ${base}_${next_suffix}) ---"
            continue
        fi
        skill_name=$(echo "$base" | sed 's/smoke_//')
        echo "--- Running smoke test: $skill_name (revision $suffix) ---"
    else
        # Original or non-revision file — skip if a revision exists
        for rev in "$SMOKE_DIR/${basename_noext}_"[a-z].R; do
            if [ -f "$rev" ]; then
                echo "--- Skipping $basename_noext (superseded by $(basename "$rev" .R)) ---"
                continue 2
            fi
        done
        skill_name=$(echo "$basename_noext" | sed 's/smoke_//')
        echo "--- Running smoke test: $skill_name ---"
    fi

    if bash "$CAPTURE" "$test_script" 2>&1 | tail -5; then
        PASSED=$((PASSED + 1))
        echo "RESULT: PASS"
    else
        FAILED=$((FAILED + 1))
        FAILURES="$FAILURES $skill_name"
        echo "RESULT: FAIL"
    fi
    echo ""
done

echo "================================="
echo "SMOKE TEST RESULTS"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
if [ $FAILED -gt 0 ]; then
    echo "Failures:$FAILURES"
    exit 1
fi
echo "All smoke tests passed."
