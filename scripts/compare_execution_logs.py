#!/usr/bin/env python3
"""
Compare execution logs from two script files (original vs reproduced).

Extracts structured metrics from the execution logs appended by run_with_capture.sh
and produces a comparison report highlighting matches, mismatches, and any divergences.

This is a standalone CLI utility used during RV-2 (Reproducibility Verification).
It does NOT depend on polars/pandas — standard library only.

Usage:
    python compare_execution_logs.py <original_script> <reproduced_script>

Both arguments are paths to Python scripts with execution logs appended
(the '# EXECUTION LOG' format produced by run_with_capture.sh).
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

    # Find the execution log marker
    markers = [
        '# =============================================================================\n# EXECUTION LOG',
        '# EXECUTION LOG',
    ]

    log_section = None
    for marker in markers:
        if marker in text:
            log_section = text.split(marker, 1)[1]
            break

    if log_section is None:
        return [], False

    raw_lines = log_section.split('\n')
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

def extract_exit_code(lines):
    """Look for 'Exit code: N' and return the integer, or None."""
    for line in lines:
        m = re.search(r'Exit code:\s*(\d+)', line, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None


def extract_row_counts(lines):
    """Extract row-count-like numbers from log lines.

    Returns list of (label, value) tuples.
    """
    results = []
    patterns = [
        # shape: (N, M)
        (r'shape:\s*\((\d[\d,]*)\s*,\s*\d', 'shape rows'),
        # Row count: N  /  rows: N  /  Rows: N
        (r'(?:Row count|rows?|Rows?|row_count):\s*(\d[\d,]*)', 'row count'),
        # len(df) = N
        (r'len\(df\)\s*=\s*(\d[\d,]*)', 'len(df)'),
        # N rows
        (r'(\d[\d,]*)\s+rows?\b', 'N rows'),
    ]
    seen = set()
    for line in lines:
        for pattern, label in patterns:
            for m in re.finditer(pattern, line, re.IGNORECASE):
                val_str = m.group(1).replace(',', '')
                val = int(val_str)
                # Use label + context for dedup
                context = line.strip()[:60]
                key = (label, val, context)
                if key not in seen:
                    seen.add(key)
                    results.append((context, val))
    return results


def extract_column_counts(lines):
    """Extract column-count-like numbers from log lines.

    Returns list of (label, value) tuples.
    """
    results = []
    patterns = [
        # shape: (N, M)
        (r'shape:\s*\(\d[\d,]*\s*,\s*(\d[\d,]*)\)', 'shape cols'),
        # columns: N  /  col count: N
        (r'(?:columns?|col count|column_count|n_cols):\s*(\d[\d,]*)', 'col count'),
    ]
    seen = set()
    for line in lines:
        for pattern, label in patterns:
            for m in re.finditer(pattern, line, re.IGNORECASE):
                val_str = m.group(1).replace(',', '')
                val = int(val_str)
                context = line.strip()[:60]
                key = (label, val, context)
                if key not in seen:
                    seen.add(key)
                    results.append((context, val))
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
            results.append((m.group(1).upper(), m.group(2).upper()))
            continue
        # Lines starting with # CP or containing PASS/FAIL with a label
        m = re.search(r'((?:QA|Checkpoint|Check)\s*\S+)\s*[:.]\s*(PASS(?:ED)?|FAIL(?:ED)?)', line, re.IGNORECASE)
        if m:
            results.append((m.group(1).strip(), m.group(2).upper()))
    return results


def extract_key_statistics(lines):
    """Extract numeric statistics from common patterns.

    Returns list of (stat_name, float_value) tuples.
    """
    results = []
    stat_labels = [
        'mean', 'median', 'std', 'min', 'max', 'count', 'sum',
        'correlation', 'r_squared', 'r-squared', 'adj. r-squared',
        'adjusted r-squared', 'r²', 'r2', 'p-value', 'p_value',
        'rmse', 'mae', 'mse', 'variance', 'skewness', 'kurtosis',
        'coefficient', 'intercept', 'slope',
    ]
    # Build a pattern that matches "label: number" or "label = number"
    label_pattern = '|'.join(re.escape(l) for l in stat_labels)
    pattern = re.compile(
        r'(?:^|[\s(])(' + label_pattern + r')\s*[:=]\s*([+-]?\d+\.?\d*(?:[eE][+-]?\d+)?)',
        re.IGNORECASE
    )

    for line in lines:
        for m in pattern.finditer(line):
            name = m.group(1).lower().strip()
            try:
                val = float(m.group(2))
                results.append((name, val))
            except ValueError:
                pass

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
    """Compare two lists of (label, value) tuples by positional alignment.

    Returns list of (label, orig_val, repro_val, match_bool) tuples and
    counts of (total, matched, mismatched).
    """
    results = []
    max_len = max(len(orig_list), len(repro_list))

    for idx in range(max_len):
        if idx < len(orig_list) and idx < len(repro_list):
            o_label, o_val = orig_list[idx]
            r_label, r_val = repro_list[idx]
            if is_float:
                match = floats_match(o_val, r_val, rel_tol)
            else:
                match = (o_val == r_val)
            # Use the original label for display
            results.append((o_label, o_val, r_val, match))
        elif idx < len(orig_list):
            o_label, o_val = orig_list[idx]
            results.append((o_label, o_val, '(missing)', False))
        else:
            r_label, r_val = repro_list[idx]
            results.append((r_label, '(missing)', r_val, False))

    matched = sum(1 for _, _, _, m in results if m)
    mismatched = len(results) - matched
    return results, len(results), matched, mismatched


# ---------------------------------------------------------------------------
# Report formatter
# ---------------------------------------------------------------------------

def format_report(orig_path, repro_path, orig_lines, repro_lines,
                  orig_found, repro_found):
    """Build the full comparison report string."""
    output = []
    total_metrics = 0
    total_matches = 0
    total_mismatches = 0

    output.append('=== Execution Log Comparison ===')
    output.append(f'Original:   {orig_path}')
    output.append(f'Reproduced: {repro_path}')
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
        output.append('Overall: INCOMPLETE (missing execution log)')
        return '\n'.join(output)

    # --- Exit Codes ---
    orig_exit = extract_exit_code(orig_lines)
    repro_exit = extract_exit_code(repro_lines)
    output.append('--- Exit Codes ---')
    output.append(f'Original:   {orig_exit if orig_exit is not None else "(not found)"}')
    output.append(f'Reproduced: {repro_exit if repro_exit is not None else "(not found)"}')
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
        results, n, m, mm = compare_value_lists(orig_rows, repro_rows)
        for label, o_val, r_val, matched in results:
            status = 'YES' if matched else 'NO'
            output.append(f'  {label}')
            output.append(f'    Original: {o_val}  Reproduced: {r_val}  Match: {status}')
        total_metrics += n
        total_matches += m
        total_mismatches += mm
    else:
        output.append('  (no row counts found)')
    output.append('')

    # --- Column Counts ---
    orig_cols = extract_column_counts(orig_lines)
    repro_cols = extract_column_counts(repro_lines)
    output.append('--- Column Counts ---')
    if orig_cols or repro_cols:
        results, n, m, mm = compare_value_lists(orig_cols, repro_cols)
        for label, o_val, r_val, matched in results:
            status = 'YES' if matched else 'NO'
            output.append(f'  {label}')
            output.append(f'    Original: {o_val}  Reproduced: {r_val}  Match: {status}')
        total_metrics += n
        total_matches += m
        total_mismatches += mm
    else:
        output.append('  (no column counts found)')
    output.append('')

    # --- Checkpoints ---
    orig_cps = extract_checkpoints(orig_lines)
    repro_cps = extract_checkpoints(repro_lines)
    output.append('--- Checkpoints ---')
    if orig_cps or repro_cps:
        # Match by checkpoint ID
        orig_cp_dict = {cp_id: result for cp_id, result in orig_cps}
        repro_cp_dict = {cp_id: result for cp_id, result in repro_cps}
        all_ids = list(dict.fromkeys(
            [cp_id for cp_id, _ in orig_cps] + [cp_id for cp_id, _ in repro_cps]
        ))
        for cp_id in all_ids:
            o_result = orig_cp_dict.get(cp_id, '(not found)')
            r_result = repro_cp_dict.get(cp_id, '(not found)')
            matched = o_result == r_result
            status = 'YES' if matched else 'NO'
            output.append(f'  {cp_id}: Original={o_result}  Reproduced={r_result}  Match: {status}')
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
        results, n, m, mm = compare_value_lists(orig_stats, repro_stats,
                                                 is_float=True, rel_tol=1e-6)
        for label, o_val, r_val, matched in results:
            status = 'YES' if matched else 'NO'
            output.append(f'  {label}: Original={o_val}  Reproduced={r_val}  Within tolerance: {status}')
        output.append(f'  Tolerance: 1e-6 relative')
        total_metrics += n
        total_matches += m
        total_mismatches += mm
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
    if total_metrics == 0:
        verdict = 'INCONCLUSIVE (no comparable metrics found)'
    elif total_mismatches == 0:
        verdict = 'CONSISTENT'
    else:
        verdict = 'DIVERGED'
    output.append(f'Overall: {verdict}')

    return '\n'.join(output)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Compare execution logs from two script files (original vs reproduced).'
    )
    parser.add_argument('original', help='Path to original script with execution log')
    parser.add_argument('reproduced', help='Path to reproduced script with execution log')
    args = parser.parse_args()

    orig_path = Path(args.original)
    repro_path = Path(args.reproduced)

    if not orig_path.exists():
        print(f'Error: Original script not found: {orig_path}', file=sys.stderr)
        sys.exit(1)
    if not repro_path.exists():
        print(f'Error: Reproduced script not found: {repro_path}', file=sys.stderr)
        sys.exit(1)

    orig_lines, orig_found = extract_execution_log(orig_path)
    repro_lines, repro_found = extract_execution_log(repro_path)

    report = format_report(
        str(orig_path), str(repro_path),
        orig_lines, repro_lines,
        orig_found, repro_found,
    )
    print(report)

    # Exit with code 1 if there are mismatches, 0 if consistent/inconclusive
    # This lets callers use the exit code to detect divergence
    if 'DIVERGED' in report.split('\n')[-1]:
        sys.exit(1)


if __name__ == '__main__':
    main()
