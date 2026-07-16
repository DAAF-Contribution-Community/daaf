#!/usr/bin/env python3
"""
Compare metrics present in two appended execution logs (original vs reproduced).

Extracts only structured metrics that the scripts printed into execution logs appended
by run_with_capture.sh, then reports log-level matches, mismatches, and divergences.
Recognized evidence includes exit codes, emitted row/column counts, checkpoints,
selected statistics, assertions, warnings, and errors. Row, column, and statistic
metrics are aligned by normalized metric identity and stable log context; values are
never used to decide which metrics correspond. Duplicate row, column, or statistic
identities require stable context, while duplicate dedicated exit-code identities or
checkpoint IDs always make the evidence inconclusive.

This utility does not inspect artifact files and is not a Parquet schema/content,
persisted model/table, or figure comparator. A CONSISTENT result applies only to the
metrics found in both logs.

Exit statuses:
    0  CONSISTENT log evidence
    1  DIVERGED log evidence
    2  Invalid invocation or an input read/parse failure
    3  INCOMPLETE (missing log) or INCONCLUSIVE evidence

This is an optional standalone CLI helper used during RV-2 (Reproducibility
Verification). It does NOT depend on polars/pandas — standard library only.

Usage:
    python compare_execution_logs.py <original_script> <reproduced_script>

Both arguments may be `.py` or `.R` script paths with execution logs appended in
the '# EXECUTION LOG' format produced by run_with_capture.sh.
"""

import argparse
import math
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Log extraction
# ---------------------------------------------------------------------------

def extract_execution_log(script_path):
    """Read a script file and return the execution log section as a list of lines.

    The log is everything after the '# EXECUTION LOG' marker, with comment
    prefixes ('# ') stripped to recover the original output text.
    Returns (log_lines, found) where found indicates whether a log was present.
    """
    text = Path(script_path).read_text()

    # Require a dedicated marker line. Mentions of '# EXECUTION LOG' inside
    # source strings or prose are not appended logs.
    marker = re.search(r'^# EXECUTION LOG\s*$', text, re.MULTILINE)
    if marker is None:
        return [], False

    raw_lines = text[marker.end():].split('\n')
    clean_lines = []
    for line in raw_lines:
        if line.startswith('# '):
            clean_lines.append(line[2:])
        elif line.startswith('#'):
            clean_lines.append(line[1:])
        else:
            clean_lines.append(line)

    return clean_lines, True


# ---------------------------------------------------------------------------
# Metric extractors
# ---------------------------------------------------------------------------

def normalize_metric_text(text):
    """Normalize a metric label/context without using its numeric value."""
    normalized = text.casefold().replace('²', '2')
    normalized = re.sub(r'[_-]+', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized.strip(' :|[]()')


def normalize_stat_name(name):
    """Collapse spelling variants of a statistic into one metric identity."""
    normalized = normalize_metric_text(name).replace('.', '')
    aliases = {
        'r2': 'r squared',
        'r squared': 'r squared',
        'adj r squared': 'adjusted r squared',
        'p value': 'p value',
    }
    return aliases.get(normalized, normalized)


def metric_context(line, value_spans):
    """Return stable line context with recognized metric values removed."""
    context = line
    for start, end in sorted(value_spans, reverse=True):
        context = context[:start] + '<value>' + context[end:]
    return normalize_metric_text(context)


def extract_exit_codes(lines):
    """Return every dedicated ``Exit code: N`` identity in the log."""
    results = []
    for line in lines:
        match = re.fullmatch(r'\s*Exit code:\s*(\d+)\s*', line, re.IGNORECASE)
        if match:
            results.append(int(match.group(1)))
    return results


def extract_row_counts(lines):
    """Extract row counts as (identity, context, display, value) tuples."""
    results = []
    patterns = [
        # shape: (N, M); both values are removed from stable context.
        (r'shape:\s*\((\d[\d,]*)\s*,\s*(\d[\d,]*)\)', 'shape rows', 1),
        # Row count: N  /  rows: N  /  Rows: N
        (r'(?:Row count|rows?|row_count):\s*(\d[\d,]*)', 'row count', 1),
        # len(df) = N
        (r'len\(df\)\s*=\s*(\d[\d,]*)', 'len(df)', 1),
        # N rows
        (r'(?<![=\d])(\d[\d,]*)\s+rows?\b', 'N rows', 1),
    ]
    seen_spans = set()
    for line_number, line in enumerate(lines):
        for pattern, identity, value_group in patterns:
            for match in re.finditer(pattern, line, re.IGNORECASE):
                value_span = match.span(value_group)
                span_key = (line_number, value_span[0], value_span[1])
                if span_key in seen_spans:
                    continue
                seen_spans.add(span_key)
                value = int(match.group(value_group).replace(',', ''))
                context_spans = [
                    match.span(group)
                    for group in range(1, (match.lastindex or 0) + 1)
                ]
                context = metric_context(line, context_spans)
                results.append((normalize_metric_text(identity), context,
                                line.strip()[:80], value))
    return results


def extract_column_counts(lines):
    """Extract column counts as (identity, context, display, value) tuples."""
    results = []
    patterns = [
        # shape: (N, M); both values are removed from stable context.
        (r'shape:\s*\((\d[\d,]*)\s*,\s*(\d[\d,]*)\)', 'shape columns', 2),
        # columns: N  /  col count: N
        (r'(?:columns?|col count|column_count|n_cols):\s*(\d[\d,]*)',
         'column count', 1),
    ]
    seen_spans = set()
    for line_number, line in enumerate(lines):
        for pattern, identity, value_group in patterns:
            for match in re.finditer(pattern, line, re.IGNORECASE):
                value_span = match.span(value_group)
                span_key = (line_number, value_span[0], value_span[1])
                if span_key in seen_spans:
                    continue
                seen_spans.add(span_key)
                value = int(match.group(value_group).replace(',', ''))
                context_spans = [
                    match.span(group)
                    for group in range(1, (match.lastindex or 0) + 1)
                ]
                context = metric_context(line, context_spans)
                results.append((normalize_metric_text(identity), context,
                                line.strip()[:80], value))
    return results


def extract_checkpoints(lines):
    """Extract checkpoint pass/fail results.

    Returns list of (checkpoint_id, result) tuples.
    """
    results = []
    for line in lines:
        # Lines like: CP1 PASSED, CP1 VALIDATION: PASSED, CP4: PASSED,
        # CP4 VALIDATION: PASSED WITH WARNINGS
        m = re.search(r'\b(CP\d+[a-z]?)\b.*?(PASS(?:ED)?|FAIL(?:ED)?)', line, re.IGNORECASE)
        if m:
            # Normalize "PASSED WITH WARNINGS" to PASSED (the WITH WARNINGS
            # part is after the captured group and doesn't change the status)
            status = 'PASSED' if m.group(2).upper().startswith('PASS') else 'FAILED'
            results.append((m.group(1).upper(), status))
            continue
        # Lines starting with # CP or containing PASS/FAIL with a label
        m = re.search(r'((?:QA|Checkpoint|Check)\s*\S+)\s*[:.]\s*(PASS(?:ED)?|FAIL(?:ED)?)', line, re.IGNORECASE)
        if m:
            checkpoint_id = re.sub(r'\s+', ' ', m.group(1).strip()).upper()
            status = 'PASSED' if m.group(2).upper().startswith('PASS') else 'FAILED'
            results.append((checkpoint_id, status))
    return results


def extract_key_statistics(lines):
    """Extract statistics as (identity, context, display, value) tuples."""
    results = []
    stat_labels = [
        'mean', 'median', 'std', 'min', 'max', 'count', 'sum',
        'correlation', 'r_squared', 'r-squared', 'adj. r-squared',
        'adjusted r-squared', 'r²', 'r2', 'p-value', 'p_value',
        'rmse', 'mae', 'mse', 'variance', 'skewness', 'kurtosis',
        'coefficient', 'intercept', 'slope',
    ]
    # Prefer longer labels so "r2" cannot consume part of a longer spelling.
    label_pattern = '|'.join(
        re.escape(label) for label in sorted(stat_labels, key=len, reverse=True)
    )
    pattern = re.compile(
        r'(?:^|[\s(])(' + label_pattern
        + r')\s*[:=]\s*([+-]?\d+\.?\d*(?:[eE][+-]?\d+)?)',
        re.IGNORECASE,
    )

    for line in lines:
        matches = list(pattern.finditer(line))
        value_spans = [match.span(2) for match in matches]
        context = metric_context(line, value_spans)
        for match in matches:
            try:
                value = float(match.group(2))
            except ValueError:
                continue
            identity = normalize_stat_name(match.group(1))
            results.append((identity, context, identity, value))

    return results


def extract_assertions(lines):
    """Count assertion passes and failures in the log.

    run_with_capture.sh captures stdout/stderr, so assertion failures show as
    tracebacks with 'AssertionError'. Passed assertions leave no trace in output
    unless the script prints confirmation (e.g., 'assert ... PASSED' or
    'All N assertions passed').

    Returns (passed_count, failed_count).
    """
    passed = 0
    failed = 0

    for line in lines:
        # Count AssertionError occurrences (Python's actual exception name)
        if re.search(r'\bAssertionError\b', line):
            failed += 1

        # Explicit pass messages: "N assertions passed", "assertions passed"
        m = re.search(r'(\d+)\s+assert(?:ion)?s?\s+passed', line, re.IGNORECASE)
        if m:
            passed += int(m.group(1))
        elif re.search(r'assert(?:ion)?s?\s+passed', line, re.IGNORECASE):
            passed += 1

        # Also: "N checks passed", "N validations passed"
        m2 = re.search(r'(\d+)\s+(?:checks?|validations?)\s+passed', line, re.IGNORECASE)
        if m2:
            passed += int(m2.group(1))

    return passed, failed


def extract_errors_warnings(lines):
    """Extract lines containing errors or warnings.

    Returns list of stripped lines.
    """
    results = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Match Error, Warning, Exception — but skip benign patterns
        if re.search(r'\b(Error|Warning|Exception)\b', stripped):
            # Skip lines that are just reporting "0 errors" or similar
            if re.search(r'\b0\s+(errors?|warnings?)\b', stripped, re.IGNORECASE):
                continue
            # Skip lines that are part of column names or labels
            if stripped.startswith('|') or stripped.startswith('+'):
                continue
            results.append(stripped)
    return results


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

def floats_match(a, b, rel_tol=1e-6):
    """Check if two floats match within relative tolerance."""
    # Handle NaN: two NaNs are considered matching
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        if math.isnan(a) or math.isnan(b):
            return False
    # Handle infinities: identical infinities match
    if a == b:
        return True
    if a == 0 or b == 0:
        return abs(a - b) < rel_tol
    return abs(a - b) / max(abs(a), abs(b)) < rel_tol


def compare_value_lists(orig_list, repro_list, is_float=False, rel_tol=1e-6):
    """Align metric tuples by identity and context, never by numeric value.

    Inputs contain (identity, context, display, value) tuples. A unique identity
    maps directly even if its line moves. Repeated identities map only when each
    occurrence has distinct stable context on both sides; otherwise the identity
    is returned as ambiguous instead of being positionally paired.
    """
    results = []
    ambiguities = []
    orig_by_identity = {}
    repro_by_identity = {}

    for metric in orig_list:
        orig_by_identity.setdefault(metric[0], []).append(metric)
    for metric in repro_list:
        repro_by_identity.setdefault(metric[0], []).append(metric)

    identities = list(dict.fromkeys(
        [metric[0] for metric in orig_list] + [metric[0] for metric in repro_list]
    ))

    def values_match(original, reproduced):
        if is_float:
            return floats_match(original, reproduced, rel_tol)
        return original == reproduced

    for identity in identities:
        original_metrics = orig_by_identity.get(identity, [])
        reproduced_metrics = repro_by_identity.get(identity, [])

        if len(original_metrics) <= 1 and len(reproduced_metrics) <= 1:
            original = original_metrics[0] if original_metrics else None
            reproduced = reproduced_metrics[0] if reproduced_metrics else None
            if (original is not None and reproduced is not None
                    and original[1] == reproduced[1]):
                matched = values_match(original[3], reproduced[3])
                results.append((identity, 0, original[2], original[3],
                                reproduced[3], matched, 'identity + context'))
            else:
                if original is not None:
                    occurrence = 1 if reproduced is not None else 0
                    results.append((identity, occurrence, original[2], original[3],
                                    '(missing)', False, 'identity + context'))
                if reproduced is not None:
                    occurrence = 2 if original is not None else 0
                    results.append((identity, occurrence, reproduced[2],
                                    '(missing)', reproduced[3], False,
                                    'identity + context'))
            continue

        original_contexts = [metric[1] for metric in original_metrics]
        reproduced_contexts = [metric[1] for metric in reproduced_metrics]
        if (len(set(original_contexts)) != len(original_contexts)
                or len(set(reproduced_contexts)) != len(reproduced_contexts)):
            ambiguities.append(
                f'{identity}: duplicate identity lacks distinct stable context '
                f'(original occurrences={len(original_metrics)}, '
                f'reproduced occurrences={len(reproduced_metrics)})'
            )
            continue

        original_by_context = {metric[1]: metric for metric in original_metrics}
        reproduced_by_context = {metric[1]: metric for metric in reproduced_metrics}
        contexts = list(dict.fromkeys(original_contexts + reproduced_contexts))
        for occurrence, context in enumerate(contexts, start=1):
            original = original_by_context.get(context)
            reproduced = reproduced_by_context.get(context)
            display = original[2] if original else reproduced[2]
            original_value = original[3] if original else '(missing)'
            reproduced_value = reproduced[3] if reproduced else '(missing)'
            matched = (
                original is not None
                and reproduced is not None
                and values_match(original_value, reproduced_value)
            )
            results.append((identity, occurrence, display, original_value,
                            reproduced_value, matched, 'identity + context'))

    matched = sum(1 for result in results if result[5])
    mismatched = len(results) - matched
    return results, len(results), matched, mismatched, ambiguities


# ---------------------------------------------------------------------------
# Report formatter
# ---------------------------------------------------------------------------

def format_report(orig_path, repro_path, orig_lines, repro_lines,
                  orig_found, repro_found):
    """Build the comparison report and return (report, base_verdict)."""
    output = []
    total_metrics = 0
    total_matches = 0
    total_mismatches = 0
    total_ambiguities = 0
    blocking_identity_ambiguities = 0

    output.append('=== Execution Log Comparison ===')
    output.append(f'Original:   {orig_path}')
    output.append(f'Reproduced: {repro_path}')
    output.append('Scope: appended execution-log metrics only; output artifacts were not compared.')
    output.append('')

    if not orig_found:
        output.append('WARNING: No execution log found in original script.')
    if not repro_found:
        output.append('WARNING: No execution log found in reproduced script.')
    if not orig_found or not repro_found:
        output.append('')
        output.append('=== SUMMARY ===')
        output.append('Metrics compared: 0')
        output.append('Matches: 0')
        output.append('Mismatches: 0')
        output.append('Ambiguities: 0')
        output.append('Overall: INCOMPLETE (missing execution log)')
        return '\n'.join(output), 'INCOMPLETE'

    # --- Exit Codes ---
    orig_exits = extract_exit_codes(orig_lines)
    repro_exits = extract_exit_codes(repro_lines)
    output.append('--- Exit Codes ---')
    if len(orig_exits) > 1 or len(repro_exits) > 1:
        orig_occurrence_word = (
            'occurrence' if len(orig_exits) == 1 else 'occurrences'
        )
        repro_occurrence_word = (
            'occurrence' if len(repro_exits) == 1 else 'occurrences'
        )
        orig_display = (
            f'{orig_exits} ({len(orig_exits)} {orig_occurrence_word})'
            if orig_exits else '(not found)'
        )
        repro_display = (
            f'{repro_exits} ({len(repro_exits)} {repro_occurrence_word})'
            if repro_exits else '(not found)'
        )
        output.append(f'Original:   {orig_display}')
        output.append(f'Reproduced: {repro_display}')
        output.append(
            'AMBIGUOUS: duplicate dedicated exit-code identity; '
            'no occurrence was selected.'
        )
        total_ambiguities += 1
        blocking_identity_ambiguities += 1
    else:
        orig_exit = orig_exits[0] if orig_exits else None
        repro_exit = repro_exits[0] if repro_exits else None
        output.append(
            f'Original:   {orig_exit if orig_exit is not None else "(not found)"}'
        )
        output.append(
            f'Reproduced: {repro_exit if repro_exit is not None else "(not found)"}'
        )
        if orig_exit is not None and repro_exit is not None:
            match = orig_exit == repro_exit
            output.append(f'Match: {"YES" if match else "NO"}')
            total_metrics += 1
            if match:
                total_matches += 1
            else:
                total_mismatches += 1
        else:
            output.append('Match: N/A (exit code not found in one or both logs)')
    output.append('')

    # --- Row Counts ---
    orig_rows = extract_row_counts(orig_lines)
    repro_rows = extract_row_counts(repro_lines)
    output.append('--- Row Counts ---')
    if orig_rows or repro_rows:
        results, n, m, mm, ambiguities = compare_value_lists(orig_rows, repro_rows)
        for identity, occurrence, label, o_val, r_val, matched, alignment in results:
            status = 'YES' if matched else 'NO'
            suffix = f' [occurrence {occurrence}]' if occurrence else ''
            output.append(f'  {label}{suffix}')
            output.append(f'    Identity: {identity}; aligned by {alignment}')
            output.append(f'    Original: {o_val}  Reproduced: {r_val}  Match: {status}')
        for ambiguity in ambiguities:
            output.append(f'  AMBIGUOUS: {ambiguity}')
        total_metrics += n
        total_matches += m
        total_mismatches += mm
        total_ambiguities += len(ambiguities)
    else:
        output.append('  (no row counts found)')
    output.append('')

    # --- Column Counts ---
    orig_cols = extract_column_counts(orig_lines)
    repro_cols = extract_column_counts(repro_lines)
    output.append('--- Column Counts ---')
    if orig_cols or repro_cols:
        results, n, m, mm, ambiguities = compare_value_lists(orig_cols, repro_cols)
        for identity, occurrence, label, o_val, r_val, matched, alignment in results:
            status = 'YES' if matched else 'NO'
            suffix = f' [occurrence {occurrence}]' if occurrence else ''
            output.append(f'  {label}{suffix}')
            output.append(f'    Identity: {identity}; aligned by {alignment}')
            output.append(f'    Original: {o_val}  Reproduced: {r_val}  Match: {status}')
        for ambiguity in ambiguities:
            output.append(f'  AMBIGUOUS: {ambiguity}')
        total_metrics += n
        total_matches += m
        total_mismatches += mm
        total_ambiguities += len(ambiguities)
    else:
        output.append('  (no column counts found)')
    output.append('')

    # --- Checkpoints ---
    orig_cps = extract_checkpoints(orig_lines)
    repro_cps = extract_checkpoints(repro_lines)
    output.append('--- Checkpoints ---')
    if orig_cps or repro_cps:
        orig_cp_groups = {}
        repro_cp_groups = {}
        for checkpoint_id, result in orig_cps:
            orig_cp_groups.setdefault(checkpoint_id, []).append(result)
        for checkpoint_id, result in repro_cps:
            repro_cp_groups.setdefault(checkpoint_id, []).append(result)
        all_ids = list(dict.fromkeys(
            [cp_id for cp_id, _ in orig_cps] + [cp_id for cp_id, _ in repro_cps]
        ))
        for cp_id in all_ids:
            original_results = orig_cp_groups.get(cp_id, [])
            reproduced_results = repro_cp_groups.get(cp_id, [])
            if len(original_results) > 1 or len(reproduced_results) > 1:
                original_occurrence_word = (
                    'occurrence' if len(original_results) == 1 else 'occurrences'
                )
                reproduced_occurrence_word = (
                    'occurrence' if len(reproduced_results) == 1 else 'occurrences'
                )
                original_display = (
                    f'[{", ".join(original_results)}] '
                    f'({len(original_results)} {original_occurrence_word})'
                    if original_results else '(not found)'
                )
                reproduced_display = (
                    f'[{", ".join(reproduced_results)}] '
                    f'({len(reproduced_results)} {reproduced_occurrence_word})'
                    if reproduced_results else '(not found)'
                )
                output.append(
                    f'  {cp_id}: AMBIGUOUS duplicate checkpoint ID; '
                    f'Original={original_display}; Reproduced={reproduced_display}; '
                    'no occurrence was selected.'
                )
                total_ambiguities += 1
                blocking_identity_ambiguities += 1
                continue

            original_result = (
                original_results[0] if original_results else '(not found)'
            )
            reproduced_result = (
                reproduced_results[0] if reproduced_results else '(not found)'
            )
            matched = original_result == reproduced_result
            status = 'YES' if matched else 'NO'
            output.append(
                f'  {cp_id}: Original={original_result}  '
                f'Reproduced={reproduced_result}  Match: {status}'
            )
            total_metrics += 1
            if matched:
                total_matches += 1
            else:
                total_mismatches += 1
    else:
        output.append('  (no checkpoints found)')
    output.append('')

    # --- Key Statistics ---
    orig_stats = extract_key_statistics(orig_lines)
    repro_stats = extract_key_statistics(repro_lines)
    output.append('--- Key Statistics ---')
    if orig_stats or repro_stats:
        results, n, m, mm, ambiguities = compare_value_lists(
            orig_stats, repro_stats, is_float=True, rel_tol=1e-6,
        )
        for identity, occurrence, label, o_val, r_val, matched, alignment in results:
            status = 'YES' if matched else 'NO'
            suffix = f' [occurrence {occurrence}]' if occurrence else ''
            output.append(
                f'  {label}{suffix}: Original={o_val}  Reproduced={r_val}  '
                f'Within tolerance: {status}'
            )
            output.append(f'    Aligned by: {alignment}; identity={identity}')
        for ambiguity in ambiguities:
            output.append(f'  AMBIGUOUS: {ambiguity}')
        output.append('  Tolerance: 1e-6 relative')
        total_metrics += n
        total_matches += m
        total_mismatches += mm
        total_ambiguities += len(ambiguities)
    else:
        output.append('  (no key statistics found)')
    output.append('')

    # --- Assertions ---
    orig_passed, orig_failed = extract_assertions(orig_lines)
    repro_passed, repro_failed = extract_assertions(repro_lines)
    output.append('--- Assertions ---')
    output.append(f'Original:   {orig_passed} passed, {orig_failed} failed')
    output.append(f'Reproduced: {repro_passed} passed, {repro_failed} failed')
    if orig_passed > 0 or repro_passed > 0 or orig_failed > 0 or repro_failed > 0:
        passed_match = (orig_passed == repro_passed)
        failed_match = (orig_failed == repro_failed)
        overall_match = passed_match and failed_match
        output.append(f'Match: {"YES" if overall_match else "NO"}')
        total_metrics += 1
        if overall_match:
            total_matches += 1
        else:
            total_mismatches += 1
    output.append('')

    # --- Errors/Warnings ---
    orig_errors = extract_errors_warnings(orig_lines)
    repro_errors = extract_errors_warnings(repro_lines)
    output.append('--- Errors/Warnings ---')
    if not orig_errors and not repro_errors:
        output.append('  (none in either log)')
    else:
        if orig_errors:
            output.append('  Original:')
            for e in orig_errors:
                output.append(f'    {e}')
        else:
            output.append('  Original: (none)')
        if repro_errors:
            output.append('  Reproduced:')
            for e in repro_errors:
                output.append(f'    {e}')
        else:
            output.append('  Reproduced: (none)')
        # Count as a metric: same set of errors/warnings?
        match = (sorted(orig_errors) == sorted(repro_errors))
        output.append(f'  Match: {"YES" if match else "NO"}')
        total_metrics += 1
        if match:
            total_matches += 1
        else:
            total_mismatches += 1
    output.append('')

    # --- SUMMARY ---
    output.append('=== SUMMARY ===')
    output.append(f'Metrics compared: {total_metrics}')
    output.append(f'Matches: {total_matches}')
    output.append(f'Mismatches: {total_mismatches}')
    output.append(f'Ambiguities: {total_ambiguities}')
    if blocking_identity_ambiguities > 0:
        verdict = 'INCONCLUSIVE'
        verdict_detail = 'INCONCLUSIVE (ambiguous duplicate exit/checkpoint identities)'
    elif total_mismatches > 0:
        verdict = 'DIVERGED'
        verdict_detail = verdict
    elif total_ambiguities > 0:
        verdict = 'INCONCLUSIVE'
        verdict_detail = 'INCONCLUSIVE (ambiguous duplicate metric identities)'
    elif total_metrics == 0:
        verdict = 'INCONCLUSIVE'
        verdict_detail = 'INCONCLUSIVE (no comparable metrics found)'
    else:
        verdict = 'CONSISTENT'
        verdict_detail = verdict
    output.append(f'Overall: {verdict_detail}')

    return '\n'.join(output), verdict


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            'Compare normalized metrics printed into appended execution logs from '
            'two .py or .R scripts. This compares log evidence only; it does not '
            'compare output artifacts.'
        ),
        epilog=(
            'Exit statuses:\n'
            '  0=CONSISTENT; 1=DIVERGED;\n'
            '  2=invalid invocation or input read/parse failure;\n'
            '  3=INCOMPLETE or INCONCLUSIVE evidence.\n'
            'A status of 0 describes execution-log metrics only, never artifact '
            'equivalence.'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'original', help='Path to original .py or .R script with execution log',
    )
    parser.add_argument(
        'reproduced', help='Path to reproduced .py or .R script with execution log',
    )
    args = parser.parse_args()

    orig_path = Path(args.original)
    repro_path = Path(args.reproduced)

    if not orig_path.is_file():
        print(f'Error: Original script is not a readable file: {orig_path}',
              file=sys.stderr)
        sys.exit(2)
    if not repro_path.is_file():
        print(f'Error: Reproduced script is not a readable file: {repro_path}',
              file=sys.stderr)
        sys.exit(2)

    try:
        orig_lines, orig_found = extract_execution_log(orig_path)
    except (OSError, UnicodeError) as error:
        print(f'Error: Could not read/parse original script {orig_path}: {error}',
              file=sys.stderr)
        sys.exit(2)
    try:
        repro_lines, repro_found = extract_execution_log(repro_path)
    except (OSError, UnicodeError) as error:
        print(f'Error: Could not read/parse reproduced script {repro_path}: {error}',
              file=sys.stderr)
        sys.exit(2)

    report, verdict = format_report(
        str(orig_path), str(repro_path),
        orig_lines, repro_lines,
        orig_found, repro_found,
    )
    print(report)

    exit_statuses = {
        'CONSISTENT': 0,
        'DIVERGED': 1,
        'INCOMPLETE': 3,
        'INCONCLUSIVE': 3,
    }
    sys.exit(exit_statuses[verdict])


if __name__ == '__main__':
    main()
