#!/usr/bin/env bats
# ============================================================================
# Focused tests for compare_reproduction_artifacts.py -- RV artifact evidence
# ============================================================================

load 'test_helper'

setup() {
    ORIGINAL_DIR="$(pwd)"
    TEST_WORKSPACE="${REPO_ROOT}/scripts/scratch/compare-reproduction-artifacts-${BATS_TEST_NUMBER:-0}-$$"
    FIXTURES="${TEST_WORKSPACE}/fixtures"
    UTILITY="${REPO_ROOT}/scripts/compare_reproduction_artifacts.py"
    FIXTURE_BUILDER="${REPO_ROOT}/tests/bash/rv_artifact_fixture_builder.py"
    mkdir -p "${FIXTURES}"
    python3 "${FIXTURE_BUILDER}" "${FIXTURES}"
    cd "${TEST_WORKSPACE}" || return 1
    export ORIGINAL_DIR TEST_WORKSPACE FIXTURES UTILITY FIXTURE_BUILDER
}

teardown() {
    cd "${ORIGINAL_DIR}" || true
    chmod -R u+rwX "${TEST_WORKSPACE}" 2>/dev/null || true
    rm -rf "${TEST_WORKSPACE}"
}

@test "exact mode infers safely and reports size and SHA-256 match or divergence" {
    printf '%s\n' 'stable exact artifact' > "${FIXTURES}/original.txt"
    cp "${FIXTURES}/original.txt" "${FIXTURES}/reproduced.txt"
    local original_before reproduced_before
    original_before="$(sha256sum "${FIXTURES}/original.txt")"
    reproduced_before="$(sha256sum "${FIXTURES}/reproduced.txt")"

    run python3 "${UTILITY}" "${FIXTURES}/original.txt" "${FIXTURES}/reproduced.txt"

    [ "${status}" -eq 0 ]
    [[ "${output}" == *'"mode": "exact"'* ]]
    [[ "${output}" == *'"overall": "MATCH"'* ]]
    [[ "${output}" == *'"dimension": "size_bytes"'* ]]
    [[ "${output}" == *'"dimension": "sha256"'* ]]
    local report_json="${output}"
    run jq -e '.overall == "MATCH" and .mode == "exact" and .exit_code == 0' <<< "${report_json}"
    [ "${status}" -eq 0 ]
    [ "$(sha256sum "${FIXTURES}/original.txt")" = "${original_before}" ]
    [ "$(sha256sum "${FIXTURES}/reproduced.txt")" = "${reproduced_before}" ]

    printf '%s\n' 'changed exact artifact' > "${FIXTURES}/reproduced.txt"
    run python3 "${UTILITY}" "${FIXTURES}/original.txt" "${FIXTURES}/reproduced.txt" --mode exact

    [ "${status}" -eq 1 ]
    [[ "${output}" == *'"overall": "DIVERGED"'* ]]
    [[ "${output}" == *'"assessment": "DIVERGED"'* ]]
}

@test "explicit --mode parquet compares supported Parquet content as a match" {
    run python3 "${UTILITY}" \
        "${FIXTURES}/base.parquet" "${FIXTURES}/base_copy.parquet" --mode parquet

    [ "${status}" -eq 0 ]
    [[ "${output}" == *'"mode": "parquet"'* ]]
    [[ "${output}" == *'"overall": "MATCH"'* ]]
    [[ "${output}" == *'"dimension": "schema_columns_and_dtypes"'* ]]
    local report_json="${output}"
    run jq -e '
        .mode == "parquet" and .overall == "MATCH" and
        ([.dimensions[] | select(.dimension == "mode_selection")][0] |
            .evidence.requested == "parquet" and .evidence.selected == "parquet")
    ' <<< "${report_json}"
    [ "${status}" -eq 0 ]
}

@test "auto mode with mismatched artifact suffixes is an invalid invocation" {
    printf '%s\n' 'plain text artifact' > "${FIXTURES}/mismatch.txt"

    run python3 "${UTILITY}" "${FIXTURES}/base.parquet" "${FIXTURES}/mismatch.txt"

    [ "${status}" -eq 2 ]
    [[ "${output}" == *'"overall": "NOT DIRECTLY VERIFIED"'* ]]
    [[ "${output}" == *'"dimension": "mode_selection"'* ]]
    [[ "${output}" == *"Auto mode requires two .parquet files or matching file suffixes"* ]]
    local report_json="${output}"
    run jq -e '.exit_code == 2 and .mode == "auto"' <<< "${report_json}"
    [ "${status}" -eq 0 ]
}

@test "missing and unreadable artifacts return NOT DIRECTLY VERIFIED" {
    printf '%s\n' 'present' > "${FIXTURES}/present.bin"

    run python3 "${UTILITY}" "${FIXTURES}/missing.bin" "${FIXTURES}/present.bin" --mode exact

    [ "${status}" -eq 3 ]
    [[ "${output}" == *'"overall": "NOT DIRECTLY VERIFIED"'* ]]
    [[ "${output}" == *'"exists": false'* ]]
    [[ "${output}" == *"missing evidence is never a match"* ]]

    printf '%s\n' 'unreadable' > "${FIXTURES}/unreadable.bin"
    chmod 000 "${FIXTURES}/unreadable.bin"
    run python3 "${UTILITY}" "${FIXTURES}/unreadable.bin" "${FIXTURES}/present.bin" --mode exact

    [ "${status}" -eq 3 ]
    [[ "${output}" == *'"overall": "NOT DIRECTLY VERIFIED"'* ]]
    [[ "${output}" == *'"readable": false'* ]]
}

@test "Parquet match covers supported scalar types and row-order-only differences" {
    run python3 "${UTILITY}" "${FIXTURES}/base.parquet" "${FIXTURES}/base_copy.parquet"

    [ "${status}" -eq 0 ]
    [[ "${output}" == *'"mode": "parquet"'* ]]
    [[ "${output}" == *'"overall": "MATCH"'* ]]
    [[ "${output}" == *'"dimension": "schema_columns_and_dtypes"'* ]]
    [[ "${output}" == *'"dimension": "null_counts"'* ]]
    [[ "${output}" == *'"comparison": "order-independent occurrence-aware row multiset"'* ]]

    run python3 "${UTILITY}" "${FIXTURES}/base.parquet" "${FIXTURES}/base_reordered.parquet"

    [ "${status}" -eq 0 ]
    [[ "${output}" == *'"overall": "MATCH"'* ]]
    [[ "${output}" == *'"float_relative_tolerance": 1e-06'* ]]
}

@test "float relative tolerance accepts below and rejects above the 1e-6 boundary" {
    run python3 "${UTILITY}" "${FIXTURES}/float_original.parquet" "${FIXTURES}/float_within.parquet"

    [ "${status}" -eq 0 ]
    [[ "${output}" == *'"overall": "MATCH"'* ]]
    [[ "${output}" == *'"float_relative_tolerance": 1e-06'* ]]
    [[ "${output}" == *'"float_absolute_tolerance": 0.0'* ]]

    run python3 "${UTILITY}" "${FIXTURES}/float_original.parquet" "${FIXTURES}/float_outside.parquet"

    [ "${status}" -eq 1 ]
    [[ "${output}" == *'"overall": "DIVERGED"'* ]]
    [[ "${output}" == *"no complete occurrence-aware matching within float tolerance"* ]]

    # This pair requires an augmenting path: the first original row can match
    # either reproduced row, while the second can match only the first.
    run python3 "${UTILITY}" "${FIXTURES}/float_ambiguous_original.parquet" "${FIXTURES}/float_ambiguous_reproduced.parquet"

    [ "${status}" -eq 0 ]
    [[ "${output}" == *'"overall": "MATCH"'* ]]
}

@test "schema null-count and exact scalar value differences each diverge" {
    run python3 "${UTILITY}" "${FIXTURES}/schema_original.parquet" "${FIXTURES}/schema_different.parquet"

    [ "${status}" -eq 1 ]
    [[ "${output}" == *'"overall": "DIVERGED"'* ]]
    [[ "${output}" == *'"dimension": "schema_columns_and_dtypes"'* ]]
    [[ "${output}" == *'"assessment": "DIVERGED"'* ]]

    run python3 "${UTILITY}" "${FIXTURES}/schema_order_original.parquet" "${FIXTURES}/schema_order_swapped.parquet"

    [ "${status}" -eq 1 ]
    [[ "${output}" == *'"overall": "DIVERGED"'* ]]
    [[ "${output}" == *'"column_order_is_significant": true'* ]]

    run python3 "${UTILITY}" "${FIXTURES}/null_original.parquet" "${FIXTURES}/null_different.parquet"

    [ "${status}" -eq 1 ]
    [[ "${output}" == *'"dimension": "null_counts"'* ]]
    [[ "${output}" == *'"original": {'* ]]
    [[ "${output}" == *'"reproduced": {'* ]]

    run python3 "${UTILITY}" "${FIXTURES}/value_original.parquet" "${FIXTURES}/value_different.parquet"

    [ "${status}" -eq 1 ]
    [[ "${output}" == *'"overall": "DIVERGED"'* ]]
    [[ "${output}" == *'"comparison": "order-independent exact row multiset"'* ]]
    [[ "${output}" == *'"original_count": 1'* ]]
    [[ "${output}" == *'"reproduced_count": 0'* ]]
}

@test "duplicate rows are compared as occurrences without deduplication" {
    run python3 "${UTILITY}" "${FIXTURES}/duplicates_original.parquet" "${FIXTURES}/duplicates_reordered.parquet"

    [ "${status}" -eq 0 ]
    [[ "${output}" == *'"overall": "MATCH"'* ]]
    [[ "${output}" == *'"dimension": "duplicate_rows"'* ]]
    [[ "${output}" == *'"multiplicity_preserved_by_value_comparison": true'* ]]
    [[ "${output}" == *'"original": 1'* ]]
    [[ "${output}" == *'"reproduced": 1'* ]]

    run python3 "${UTILITY}" "${FIXTURES}/duplicates_original.parquet" "${FIXTURES}/duplicates_different.parquet"

    [ "${status}" -eq 1 ]
    [[ "${output}" == *'"overall": "DIVERGED"'* ]]
    [[ "${output}" == *"row multiplicity differs"* ]]
    local mismatch_json="${output}"
    run jq -e '
        ([.dimensions[] | select(.dimension == "duplicate_rows")][0].assessment == "DIVERGED") and
        ([.dimensions[] | select(.dimension == "values_order_independent")][0].assessment == "DIVERGED")
    ' <<< "${mismatch_json}"
    [ "${status}" -eq 0 ]
}

@test "exact-key cardinality mismatch diverges before an overflowing tolerant pair limit" {
    run python3 "${UTILITY}" \
        "${FIXTURES}/cardinality_overflow_original.parquet" \
        "${FIXTURES}/cardinality_overflow_reproduced.parquet" \
        --max-pair-comparisons 10

    [ "${status}" -eq 1 ]
    local report_json="${output}"
    run jq -e '
        .overall == "DIVERGED" and
        ([.dimensions[] | select(.dimension == "values_order_independent")][0] |
            .assessment == "DIVERGED" and
            .evidence.exact_key_cardinalities_equal == false and
            .evidence.pair_comparisons_required == 800 and
            .evidence.max_pair_comparisons == 10) and
        ([.dimensions[] | select(.dimension == "duplicate_rows")][0].assessment == "DIVERGED")
    ' <<< "${report_json}"
    [ "${status}" -eq 0 ]
}

@test "nested values and NaN semantics are explicit NOT DIRECTLY VERIFIED limitations" {
    run python3 "${UTILITY}" "${FIXTURES}/nested_original.parquet" "${FIXTURES}/nested_reproduced.parquet"

    [ "${status}" -eq 3 ]
    [[ "${output}" == *'"overall": "NOT DIRECTLY VERIFIED"'* ]]
    [[ "${output}" == *'"items": "List(Int64)"'* ]]
    [[ "${output}" == *"Unsupported Parquet dtypes were detected"* ]]

    run python3 "${UTILITY}" "${FIXTURES}/nan_original.parquet" "${FIXTURES}/nan_reproduced.parquet"

    [ "${status}" -eq 3 ]
    [[ "${output}" == *'"overall": "NOT DIRECTLY VERIFIED"'* ]]
    [[ "${output}" == *"Any NaN presence prevents a content MATCH claim"* ]]
    [[ "${output}" == *"NaN equivalence and row matching are not silently assumed"* ]]
}

@test "Parquet byte and row limits stop before full materialization" {
    run python3 "${UTILITY}" --help

    [ "${status}" -eq 0 ]
    [[ "${output}" == *"--max-input-bytes"* ]]
    [[ "${output}" == *"default: 536870912"* ]]
    [[ "${output}" == *"--max-rows"* ]]
    [[ "${output}" == *"default: 1000000"* ]]

    run python3 "${UTILITY}" \
        "${FIXTURES}/base.parquet" \
        "${FIXTURES}/base_copy.parquet" \
        --max-input-bytes 1

    [ "${status}" -eq 3 ]
    local byte_json="${output}"
    run jq -e '
        .overall == "NOT DIRECTLY VERIFIED" and .exit_code == 3 and
        ([.dimensions[] | select(.dimension == "parquet_materialization_bounds")][0] |
            .assessment == "NOT DIRECTLY VERIFIED" and
            .evidence.max_input_bytes_per_file == 1 and
            .evidence.full_materialization_attempted == false) and
        ([.dimensions[] | select(.dimension == "parquet_materialization")] | length == 0)
    ' <<< "${byte_json}"
    [ "${status}" -eq 0 ]

    run python3 "${UTILITY}" \
        "${FIXTURES}/base.parquet" \
        "${FIXTURES}/base_copy.parquet" \
        --max-rows 2

    [ "${status}" -eq 3 ]
    local row_json="${output}"
    run jq -e '
        .overall == "NOT DIRECTLY VERIFIED" and .exit_code == 3 and
        ([.dimensions[] | select(.dimension == "parquet_materialization_bounds")][0] |
            .assessment == "NOT DIRECTLY VERIFIED" and
            .evidence.max_rows_per_file == 2 and
            .evidence.inputs.original.row_count == 3 and
            .evidence.inputs.reproduced.row_count == 3 and
            .evidence.full_materialization_attempted == false) and
        ([.dimensions[] | select(.dimension == "parquet_materialization")] | length == 0)
    ' <<< "${row_json}"
    [ "${status}" -eq 0 ]
}

@test "invalid Parquet bounded-work overflow and excluded figures do not claim matches" {
    printf '%s\n' 'not parquet bytes' > "${FIXTURES}/invalid.parquet"
    run python3 "${UTILITY}" "${FIXTURES}/invalid.parquet" "${FIXTURES}/base.parquet"

    [ "${status}" -eq 3 ]
    [[ "${output}" == *'"overall": "NOT DIRECTLY VERIFIED"'* ]]
    [[ "${output}" == *'"dimension": "parquet_readability"'* ]]
    [[ "${output}" == *"could not be read as Parquet"* ]]

    run python3 "${UTILITY}" "${FIXTURES}/base.parquet" "${FIXTURES}/base_copy.parquet" --max-pair-comparisons 1

    [ "${status}" -eq 3 ]
    [[ "${output}" == *'"overall": "NOT DIRECTLY VERIFIED"'* ]]
    [[ "${output}" == *"exceeded the bounded pair-work limit"* ]]
    local bounded_json="${output}"
    run jq -e '
        ([.dimensions[] | select(.dimension == "values_order_independent")][0].assessment == "NOT DIRECTLY VERIFIED") and
        ([.dimensions[] | select(.dimension == "duplicate_rows")][0] |
            .assessment == "NOT DIRECTLY VERIFIED" and
            .evidence.multiplicity_preserved_by_value_comparison == null)
    ' <<< "${bounded_json}"
    [ "${status}" -eq 0 ]

    printf '%s\n' 'not a real image' > "${FIXTURES}/original.png"
    cp "${FIXTURES}/original.png" "${FIXTURES}/reproduced.png"
    run python3 "${UTILITY}" "${FIXTURES}/original.png" "${FIXTURES}/reproduced.png"

    [ "${status}" -eq 2 ]
    [[ "${output}" == *'"overall": "NOT DIRECTLY VERIFIED"'* ]]
    [[ "${output}" == *"figure visuals"* ]]
    [[ "${output}" == *"separate RV evidence path"* ]]

    printf '%s\n' 'opaque model bytes' > "${FIXTURES}/original.onnx"
    cp "${FIXTURES}/original.onnx" "${FIXTURES}/reproduced.onnx"
    run python3 "${UTILITY}" "${FIXTURES}/original.onnx" "${FIXTURES}/reproduced.onnx" --mode exact

    [ "${status}" -eq 2 ]
    [[ "${output}" == *'"overall": "NOT DIRECTLY VERIFIED"'* ]]
    [[ "${output}" == *"persisted model semantics"* ]]
}
