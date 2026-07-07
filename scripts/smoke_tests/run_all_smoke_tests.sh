#!/usr/bin/env bash
# scripts/smoke_tests/run_all_smoke_tests.sh
# Executes all R skill smoke tests and the Python import smoke, then reports results.
#
# The smoke_*.R glob below intentionally matches _a/_b/... revision files. Those
# are immutable-versioning artifacts (per CLAUDE.md: a failed script keeps its
# appended execution log; fixes go into a new _a/_b copy). The revision-detection
# logic in the loop keeps only the latest revision of each skill so superseded
# copies are skipped rather than re-run.

SMOKE_DIR="$(dirname "$0")"
BASE_DIR="$(cd "$SMOKE_DIR/../.." && pwd)"
CAPTURE="$BASE_DIR/scripts/run_with_capture.sh"
# pipefail so `<test> | tail` reports the test's exit status, not tail's —
# without it a failing smoke would be counted PASS. Applies to both loops below.
set -o pipefail
PASSED=0
FAILED=0
SKIPPED=0
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

    output=$(bash "$CAPTURE" "$test_script" 2>&1)
    rc=$?
    echo "$output" | tail -5
    if [ $rc -eq 0 ]; then
        PASSED=$((PASSED + 1))
        echo "RESULT: PASS"
    elif echo "$output" | grep -q "already has an execution log"; then
        # Immutable-versioning re-run guard (run_with_capture.sh): a script with
        # an appended log is an audit artifact and cannot be re-executed in
        # place. That is not a test failure — copy to a new _a/_b revision to
        # obtain a fresh run.
        SKIPPED=$((SKIPPED + 1))
        echo "RESULT: SKIP (already logged; create a new revision to re-run)"
    else
        FAILED=$((FAILED + 1))
        FAILURES="$FAILURES $skill_name"
        echo "RESULT: FAIL"
    fi
    echo ""
done

# Python import-smoke tests. These are single-version .py files (not R skill
# smokes), so no revision handling applies. Invoked via python3 directly — the
# file-first run_with_capture.sh wrapper is for pipeline audit-trail scripts,
# not for this test-harness invocation. The glob may not match any files; the
# nullglob guard below prevents running the literal pattern in that case.
shopt -s nullglob
for py_script in "$SMOKE_DIR"/smoke_*.py; do
    py_name=$(basename "$py_script" .py | sed 's/smoke_//')
    echo "--- Running smoke test: $py_name (python) ---"
    if python3 "$py_script" 2>&1 | tail -5; then
        PASSED=$((PASSED + 1))
        echo "RESULT: PASS"
    else
        FAILED=$((FAILED + 1))
        FAILURES="$FAILURES $py_name"
        echo "RESULT: FAIL"
    fi
    echo ""
done
shopt -u nullglob

echo "================================="
echo "SMOKE TEST RESULTS"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo "Skipped (already logged): $SKIPPED"
if [ $FAILED -gt 0 ]; then
    echo "Failures:$FAILURES"
    exit 1
fi
echo "All executed smoke tests passed."
