#!/usr/bin/env python3
"""Compare original and reproduced artifacts with bounded direct evidence.

Supported modes:

``parquet``
    Read both files with Polars; compare schema, shape, null counts, and supported
    scalar values. Rows are compared as occurrence-aware multisets. Integers,
    strings, booleans, and temporal values are exact; floats use 1e-6 relative
    tolerance with no absolute tolerance.

``exact``
    Compare regular files by byte size and SHA-256. This establishes byte
    identity only, not format-specific semantics.

``auto`` (default)
    Infer Parquet only when both suffixes are ``.parquet``; infer exact-byte mode
    only for two files with the same non-excluded suffix. Ambiguous or excluded
    artifact classes require a different RV evidence path.

Exit codes:
    0  MATCH
    1  DIVERGED
    2  Invalid invocation or unsupported comparison class
    3  NOT DIRECTLY VERIFIED because evidence is missing, unreadable, unsupported,
       exceeds a pre-materialization input bound, or exceeds the bounded
       order-independent float-comparison work limit

This helper is read-only. It does not compare figure visuals, execution logs, or
persisted model semantics. Nested/opaque Parquet values and any floating column
containing NaN are reported as limitations rather than silently matched. Parquet
files are bounded by compressed byte size and metadata row count before Polars
materializes their contents or Python row tuples.
"""

import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
import math
import os
from pathlib import Path

try:
    import polars as pl
except ImportError:
    pl = None

try:
    import pyarrow.parquet as pq
except ImportError:
    pq = None


EXIT_MATCH = 0
EXIT_DIVERGED = 1
EXIT_INVALID = 2
EXIT_NOT_VERIFIED = 3
RELATIVE_TOLERANCE = 1e-6
ABSOLUTE_TOLERANCE = 0.0
DEFAULT_MAX_PAIR_COMPARISONS = 1_000_000
DEFAULT_MAX_INPUT_BYTES = 536_870_912
DEFAULT_MAX_ROWS = 1_000_000

EXCLUDED_SUFFIXES = {
    ".png": "figure visuals",
    ".jpg": "figure visuals",
    ".jpeg": "figure visuals",
    ".gif": "figure visuals",
    ".svg": "figure visuals",
    ".pdf": "rendered documents or figures",
    ".log": "execution logs",
    ".rds": "persisted model/table semantics",
    ".rda": "persisted model/table semantics",
    ".rdata": "persisted model/table semantics",
    ".qs": "persisted model/table semantics",
    ".pkl": "persisted model semantics",
    ".pickle": "persisted model semantics",
    ".joblib": "persisted model semantics",
    ".model": "persisted model semantics",
    ".onnx": "persisted model semantics",
    ".pt": "persisted model semantics",
    ".pth": "persisted model semantics",
    ".keras": "persisted model semantics",
    ".h5": "persisted model semantics",
    ".hdf5": "persisted model semantics",
    ".cbm": "persisted model semantics",
    ".bst": "persisted model semantics",
}

SUPPORTED_PARQUET_DESCRIPTION = (
    "Scalar integer, float, string, boolean, Date, Datetime, Time, Duration, "
    "and all-null columns. Nested, object-like, decimal, binary, categorical, "
    "enum, and other unlisted dtypes are not directly verified."
)
SCOPE_LIMITATION = (
    "This helper does not compare figure visuals, execution logs, or persisted "
    "model semantics; those require separate RV evidence paths."
)


def add_dimension(dimensions, name, assessment, evidence):
    """Append one stable comparison dimension."""
    dimensions.append(
        {
            "dimension": name,
            "assessment": assessment,
            "evidence": evidence,
        }
    )


def emit_report(overall, exit_code, mode, original, reproduced, dimensions, limitations):
    """Print deterministic JSON output and return the selected exit code."""
    report = {
        "utility": "compare_reproduction_artifacts",
        "overall": overall,
        "exit_code": exit_code,
        "mode": mode,
        "inputs": {
            "original": str(original),
            "reproduced": str(reproduced),
        },
        "dimensions": dimensions,
        "limitations": limitations,
        "scope_limitation": SCOPE_LIMITATION,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return exit_code


def infer_mode(requested_mode, original, reproduced):
    """Return (mode, error) using deliberately narrow auto-inference rules."""
    original_suffix = original.suffix.lower()
    reproduced_suffix = reproduced.suffix.lower()

    excluded = []
    for label, suffix in (("original", original_suffix), ("reproduced", reproduced_suffix)):
        if suffix in EXCLUDED_SUFFIXES:
            excluded.append(f"{label} {suffix}: {EXCLUDED_SUFFIXES[suffix]}")
    if excluded:
        return None, (
            "Artifact class is outside this helper's scope ("
            + "; ".join(excluded)
            + "). Use the separate RV evidence path for that class."
        )

    if requested_mode != "auto":
        return requested_mode, None

    if original_suffix == ".parquet" and reproduced_suffix == ".parquet":
        return "parquet", None
    if original_suffix == reproduced_suffix:
        return "exact", None
    return None, (
        "Auto mode requires two .parquet files or matching file suffixes. "
        "Select --mode exact explicitly only when byte identity is the intended evidence."
    )


def path_evidence(path):
    """Collect non-mutating existence/readability evidence for one artifact path."""
    exists = path.exists()
    is_file = path.is_file() if exists else False
    readable = is_file and os.access(path, os.R_OK)
    return {
        "path": str(path),
        "exists": exists,
        "regular_file": is_file,
        "readable": readable,
    }


def sha256_file(path):
    """Return a streaming SHA-256 digest for a regular file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def null_counts(frame):
    """Return scalar null counts in source column order."""
    raw = frame.null_count().to_dict(as_series=False)
    return {name: values[0] for name, values in raw.items()}


def classify_dtype(dtype):
    """Classify one Polars dtype for the documented scalar comparison contract."""
    if dtype == pl.Null:
        return "exact"
    if dtype.is_integer() or dtype == pl.String or dtype == pl.Boolean:
        return "exact"
    if dtype.is_float():
        return "float"
    if dtype.is_temporal():
        return "exact"
    return "unsupported"


def count_nan_values(frame):
    """Count NaN values per floating column, excluding nulls."""
    counts = {}
    for name, dtype in frame.schema.items():
        if dtype.is_float():
            counts[name] = frame.get_column(name).is_nan().sum()
    return counts


def exact_duplicate_occurrences(rows):
    """Count occurrences beyond the first for exactly identical supported rows."""
    counts = Counter(rows)
    return sum(count - 1 for count in counts.values() if count > 1)


def bounded_repr(value, max_characters=500):
    """Return bounded diagnostic evidence for a potentially large scalar row/key."""
    rendered = repr(value)
    if len(rendered) <= max_characters:
        return rendered
    return rendered[:max_characters] + f"... <truncated {len(rendered) - max_characters} chars>"


def float_values_match(left, right):
    """Compare nullable float scalars under the fixed RV relative tolerance."""
    if left is None or right is None:
        return left is None and right is None
    return math.isclose(
        left,
        right,
        rel_tol=RELATIVE_TOLERANCE,
        abs_tol=ABSOLUTE_TOLERANCE,
    )


def float_tuples_match(left, right):
    """Compare all floating positions in two rows."""
    return all(float_values_match(a, b) for a, b in zip(left, right))


def complete_float_matching(edges, original_count):
    """Return whether an iterative bipartite matching covers every original row."""
    matched_reproduced = {}
    matched_original = {}
    for start_original in range(original_count):
        queue = deque([start_original])
        visited_original = {start_original}
        visited_reproduced = set()
        parent_reproduced = {}
        free_reproduced = None

        while queue and free_reproduced is None:
            original_index = queue.popleft()
            for reproduced_index in edges[original_index]:
                if reproduced_index in visited_reproduced:
                    continue
                visited_reproduced.add(reproduced_index)
                parent_reproduced[reproduced_index] = original_index
                prior_original = matched_reproduced.get(reproduced_index)
                if prior_original is None:
                    free_reproduced = reproduced_index
                    break
                if prior_original not in visited_original:
                    visited_original.add(prior_original)
                    queue.append(prior_original)

        if free_reproduced is None:
            return False

        reproduced_index = free_reproduced
        while reproduced_index is not None:
            original_index = parent_reproduced[reproduced_index]
            previous_reproduced = matched_original.get(original_index)
            matched_reproduced[reproduced_index] = original_index
            matched_original[original_index] = reproduced_index
            if previous_reproduced is not None:
                del matched_reproduced[previous_reproduced]
            reproduced_index = previous_reproduced

    return True


def compare_supported_rows(original_frame, reproduced_frame, max_pair_comparisons):
    """Compare materialized supported rows as occurrence-aware multisets."""
    rows_original = original_frame.rows()
    rows_reproduced = reproduced_frame.rows()
    float_indices = [
        index
        for index, dtype in enumerate(original_frame.dtypes)
        if dtype.is_float()
    ]
    exact_indices = [
        index for index in range(original_frame.width) if index not in float_indices
    ]

    duplicate_evidence = {
        "definition": "exact duplicate occurrences beyond each row's first occurrence",
        "original": exact_duplicate_occurrences(rows_original),
        "reproduced": exact_duplicate_occurrences(rows_reproduced),
        "multiplicity_preserved_by_value_comparison": None,
    }

    if not float_indices:
        original_counts = Counter(rows_original)
        reproduced_counts = Counter(rows_reproduced)
        matched = original_counts == reproduced_counts
        differing_rows = sorted(
            (
                row
                for row in set(original_counts) | set(reproduced_counts)
                if original_counts.get(row, 0) != reproduced_counts.get(row, 0)
            ),
            key=repr,
        )
        mismatch_groups = [
            {
                "row_repr": bounded_repr(row),
                "original_count": original_counts.get(row, 0),
                "reproduced_count": reproduced_counts.get(row, 0),
            }
            for row in differing_rows[:10]
        ]
        assessment = "MATCH" if matched else "DIVERGED"
        duplicate_evidence["multiplicity_preserved_by_value_comparison"] = matched
        return {
            "assessment": assessment,
            "evidence": {
                "comparison": "order-independent exact row multiset",
                "rows_original": len(rows_original),
                "rows_reproduced": len(rows_reproduced),
                "mismatch_groups_shown": mismatch_groups,
                "mismatch_groups_truncated": len(differing_rows) > 10,
            },
            "duplicate_assessment": assessment,
            "duplicates": duplicate_evidence,
            "limitation": None,
        }

    grouped_original = defaultdict(list)
    grouped_reproduced = defaultdict(list)
    for row in rows_original:
        exact_key = tuple(row[index] for index in exact_indices)
        grouped_original[exact_key].append(tuple(row[index] for index in float_indices))
    for row in rows_reproduced:
        exact_key = tuple(row[index] for index in exact_indices)
        grouped_reproduced[exact_key].append(tuple(row[index] for index in float_indices))

    original_keys = set(grouped_original)
    reproduced_keys = set(grouped_reproduced)
    exact_keys = original_keys | reproduced_keys
    pair_comparisons_required = sum(
        len(grouped_original[key]) * len(grouped_reproduced[key])
        for key in exact_keys
    )

    key_mismatches = []
    for key in sorted(exact_keys, key=repr):
        original_count = len(grouped_original[key])
        reproduced_count = len(grouped_reproduced[key])
        if original_count != reproduced_count:
            key_mismatches.append(
                {
                    "exact_key_repr": bounded_repr(key),
                    "original_count": original_count,
                    "reproduced_count": reproduced_count,
                    "reason": "row multiplicity differs",
                }
            )

    if original_keys != reproduced_keys or key_mismatches:
        duplicate_evidence["multiplicity_preserved_by_value_comparison"] = False
        return {
            "assessment": "DIVERGED",
            "evidence": {
                "comparison": "order-independent occurrence-aware row multiset",
                "float_relative_tolerance": RELATIVE_TOLERANCE,
                "float_absolute_tolerance": ABSOLUTE_TOLERANCE,
                "exact_key_sets_equal": original_keys == reproduced_keys,
                "exact_key_cardinalities_equal": not key_mismatches,
                "pair_comparisons_required": pair_comparisons_required,
                "max_pair_comparisons": max_pair_comparisons,
                "mismatch_groups_shown": key_mismatches[:10],
                "mismatch_groups_truncated": len(key_mismatches) > 10,
            },
            "duplicate_assessment": "DIVERGED",
            "duplicates": duplicate_evidence,
            "limitation": None,
        }

    if pair_comparisons_required > max_pair_comparisons:
        return {
            "assessment": "NOT DIRECTLY VERIFIED",
            "evidence": {
                "comparison": "order-independent tolerant row multiset",
                "exact_key_sets_equal": True,
                "exact_key_cardinalities_equal": True,
                "pair_comparisons_required": pair_comparisons_required,
                "max_pair_comparisons": max_pair_comparisons,
            },
            "duplicate_assessment": "NOT DIRECTLY VERIFIED",
            "duplicates": duplicate_evidence,
            "limitation": (
                "Order-independent float comparison exceeded the bounded pair-work "
                "limit; tolerant row multiplicity was not directly verified."
            ),
        }

    mismatch_groups = []
    for key in sorted(exact_keys, key=repr):
        original_floats = grouped_original[key]
        reproduced_floats = grouped_reproduced[key]
        edges = {}
        for original_index, original_values in enumerate(original_floats):
            edges[original_index] = [
                reproduced_index
                for reproduced_index, reproduced_values in enumerate(reproduced_floats)
                if float_tuples_match(original_values, reproduced_values)
            ]

        if not complete_float_matching(edges, len(original_floats)):
            mismatch_groups.append(
                {
                    "exact_key_repr": bounded_repr(key),
                    "original_count": len(original_floats),
                    "reproduced_count": len(reproduced_floats),
                    "reason": "no complete occurrence-aware matching within float tolerance",
                }
            )

    matched = not mismatch_groups
    assessment = "MATCH" if matched else "DIVERGED"
    duplicate_evidence["multiplicity_preserved_by_value_comparison"] = matched
    return {
        "assessment": assessment,
        "evidence": {
            "comparison": "order-independent occurrence-aware row multiset",
            "float_relative_tolerance": RELATIVE_TOLERANCE,
            "float_absolute_tolerance": ABSOLUTE_TOLERANCE,
            "exact_key_sets_equal": True,
            "exact_key_cardinalities_equal": True,
            "pair_comparisons_required": pair_comparisons_required,
            "max_pair_comparisons": max_pair_comparisons,
            "mismatch_groups_shown": mismatch_groups[:10],
            "mismatch_groups_truncated": len(mismatch_groups) > 10,
        },
        "duplicate_assessment": assessment,
        "duplicates": duplicate_evidence,
        "limitation": None,
    }


def compare_exact(original, reproduced, dimensions, limitations):
    """Compare two readable regular files by size and SHA-256."""
    try:
        original_size = original.stat().st_size
        reproduced_size = reproduced.stat().st_size
        original_hash = sha256_file(original)
        reproduced_hash = sha256_file(reproduced)
    except OSError as exc:
        add_dimension(
            dimensions,
            "readability",
            "NOT DIRECTLY VERIFIED",
            {"error": str(exc)},
        )
        limitations.append("One or both exact-byte artifacts could not be fully read.")
        return "NOT DIRECTLY VERIFIED", EXIT_NOT_VERIFIED

    size_match = original_size == reproduced_size
    hash_match = original_hash == reproduced_hash
    add_dimension(
        dimensions,
        "size_bytes",
        "MATCH" if size_match else "DIVERGED",
        {"original": original_size, "reproduced": reproduced_size},
    )
    add_dimension(
        dimensions,
        "sha256",
        "MATCH" if hash_match else "DIVERGED",
        {"original": original_hash, "reproduced": reproduced_hash},
    )
    limitations.append(
        "Exact mode establishes byte identity only; it does not verify format-specific semantics."
    )

    if size_match and hash_match:
        return "MATCH", EXIT_MATCH
    return "DIVERGED", EXIT_DIVERGED


def inspect_parquet_metadata(path):
    """Read schema and row-group metadata without materializing column values."""
    metadata = pq.read_metadata(path)
    schema = pl.read_parquet_schema(path)
    return {
        "schema": schema,
        "row_count": metadata.num_rows,
        "column_count": len(schema),
        "physical_leaf_column_count": metadata.num_columns,
        "row_group_count": metadata.num_row_groups,
    }


def compare_parquet(
    original,
    reproduced,
    dimensions,
    limitations,
    max_pair_comparisons,
    max_input_bytes,
    max_rows,
):
    """Compare Parquet files after bounded metadata-only preflight checks."""
    missing_dependencies = []
    if pl is None:
        missing_dependencies.append("polars")
    if pq is None:
        missing_dependencies.append("pyarrow")
    if missing_dependencies:
        add_dimension(
            dimensions,
            "dependency",
            "NOT DIRECTLY VERIFIED",
            {"required": missing_dependencies, "available": False},
        )
        limitations.append(
            "Required Parquet metadata dependencies are unavailable, so evidence was not read."
        )
        return "NOT DIRECTLY VERIFIED", EXIT_NOT_VERIFIED

    input_sizes = {}
    size_errors = {}
    for label, path in (("original", original), ("reproduced", reproduced)):
        try:
            input_sizes[label] = path.stat().st_size
        except OSError as exc:
            size_errors[label] = f"{type(exc).__name__}: {exc}"
    if size_errors:
        add_dimension(
            dimensions,
            "parquet_preflight",
            "NOT DIRECTLY VERIFIED",
            {"file_size_errors": size_errors},
        )
        limitations.append("One or both Parquet file sizes could not be inspected.")
        return "NOT DIRECTLY VERIFIED", EXIT_NOT_VERIFIED

    byte_limit_exceeded = {
        label: size
        for label, size in input_sizes.items()
        if size > max_input_bytes
    }
    if byte_limit_exceeded:
        add_dimension(
            dimensions,
            "parquet_materialization_bounds",
            "NOT DIRECTLY VERIFIED",
            {
                "file_bytes": input_sizes,
                "max_input_bytes_per_file": max_input_bytes,
                "exceeded_by": byte_limit_exceeded,
                "full_materialization_attempted": False,
            },
        )
        limitations.append(
            "At least one Parquet input exceeded --max-input-bytes; metadata and values "
            "were not materialized."
        )
        return "NOT DIRECTLY VERIFIED", EXIT_NOT_VERIFIED

    metadata = {}
    metadata_errors = {}
    for label, path in (("original", original), ("reproduced", reproduced)):
        try:
            metadata[label] = inspect_parquet_metadata(path)
        except Exception as exc:
            metadata_errors[label] = f"{type(exc).__name__}: {exc}"
    if metadata_errors:
        add_dimension(
            dimensions,
            "parquet_readability",
            "NOT DIRECTLY VERIFIED",
            {
                "original": (
                    "METADATA READABLE"
                    if "original" in metadata
                    else metadata_errors.get("original")
                ),
                "reproduced": (
                    "METADATA READABLE"
                    if "reproduced" in metadata
                    else metadata_errors.get("reproduced")
                ),
                "full_materialization_attempted": False,
            },
        )
        limitations.append("One or both paths could not be read as Parquet metadata.")
        return "NOT DIRECTLY VERIFIED", EXIT_NOT_VERIFIED

    metadata_evidence = {
        label: {
            "file_bytes": input_sizes[label],
            "row_count": details["row_count"],
            "column_count": details["column_count"],
            "physical_leaf_column_count": details["physical_leaf_column_count"],
            "row_group_count": details["row_group_count"],
        }
        for label, details in metadata.items()
    }
    row_limit_exceeded = {
        label: details["row_count"]
        for label, details in metadata.items()
        if details["row_count"] > max_rows
    }
    if row_limit_exceeded:
        add_dimension(
            dimensions,
            "parquet_materialization_bounds",
            "NOT DIRECTLY VERIFIED",
            {
                "inputs": metadata_evidence,
                "max_input_bytes_per_file": max_input_bytes,
                "max_rows_per_file": max_rows,
                "row_limit_exceeded_by": row_limit_exceeded,
                "full_materialization_attempted": False,
            },
        )
        limitations.append(
            "At least one Parquet input exceeded --max-rows; values were not materialized."
        )
        return "NOT DIRECTLY VERIFIED", EXIT_NOT_VERIFIED

    add_dimension(
        dimensions,
        "parquet_materialization_bounds",
        "MATCH",
        {
            "inputs": metadata_evidence,
            "max_input_bytes_per_file": max_input_bytes,
            "max_rows_per_file": max_rows,
            "full_materialization_permitted": True,
        },
    )

    original_schema = [
        {"name": name, "dtype": str(dtype)}
        for name, dtype in metadata["original"]["schema"].items()
    ]
    reproduced_schema = [
        {"name": name, "dtype": str(dtype)}
        for name, dtype in metadata["reproduced"]["schema"].items()
    ]
    schema_match = original_schema == reproduced_schema
    row_count_match = (
        metadata["original"]["row_count"] == metadata["reproduced"]["row_count"]
    )
    column_count_match = (
        metadata["original"]["column_count"]
        == metadata["reproduced"]["column_count"]
    )
    add_dimension(
        dimensions,
        "parquet_readability",
        "MATCH",
        {
            "original": "METADATA READABLE",
            "reproduced": "METADATA READABLE",
            "polars_version": pl.__version__,
            "metadata_reader": "pyarrow.parquet",
        },
    )
    add_dimension(
        dimensions,
        "schema_columns_and_dtypes",
        "MATCH" if schema_match else "DIVERGED",
        {
            "original": original_schema,
            "reproduced": reproduced_schema,
            "column_order_is_significant": True,
        },
    )
    add_dimension(
        dimensions,
        "row_count",
        "MATCH" if row_count_match else "DIVERGED",
        {
            "original": metadata["original"]["row_count"],
            "reproduced": metadata["reproduced"]["row_count"],
            "source": "Parquet metadata",
        },
    )
    add_dimension(
        dimensions,
        "column_count",
        "MATCH" if column_count_match else "DIVERGED",
        {
            "original": metadata["original"]["column_count"],
            "reproduced": metadata["reproduced"]["column_count"],
            "source": "Parquet metadata",
        },
    )

    unsupported = {
        label: {
            name: str(dtype)
            for name, dtype in details["schema"].items()
            if classify_dtype(dtype) == "unsupported"
        }
        for label, details in metadata.items()
    }
    unsupported_present = bool(unsupported["original"] or unsupported["reproduced"])
    add_dimension(
        dimensions,
        "dtype_support",
        "NOT DIRECTLY VERIFIED" if unsupported_present else "MATCH",
        {
            "unsupported": unsupported,
            "supported_contract": SUPPORTED_PARQUET_DESCRIPTION,
        },
    )
    if unsupported_present:
        limitations.append(
            "Unsupported Parquet dtypes were detected; their values were not compared."
        )

    prerequisite_match = schema_match and row_count_match and column_count_match
    if not prerequisite_match or unsupported_present:
        reason = "Value comparison prerequisites were not met."
        add_dimension(
            dimensions,
            "null_counts",
            "NOT DIRECTLY VERIFIED",
            {"reason": reason},
        )
        add_dimension(
            dimensions,
            "nan_semantics",
            "NOT DIRECTLY VERIFIED",
            {"reason": reason},
        )
        add_dimension(
            dimensions,
            "duplicate_rows",
            "NOT DIRECTLY VERIFIED",
            {"reason": reason},
        )
        add_dimension(
            dimensions,
            "values_order_independent",
            "NOT DIRECTLY VERIFIED",
            {
                "reason": reason,
                "row_order_policy": "order-independent when comparison is feasible",
            },
        )
        if not prerequisite_match:
            limitations.append(
                "Full row values were not materialized because schema or shape differs; "
                "the metadata-established structural divergence remains dispositive."
            )
        assessments = [dimension["assessment"] for dimension in dimensions]
        if "DIVERGED" in assessments:
            return "DIVERGED", EXIT_DIVERGED
        return "NOT DIRECTLY VERIFIED", EXIT_NOT_VERIFIED

    frames = {}
    materialization_errors = {}
    for label, path in (("original", original), ("reproduced", reproduced)):
        try:
            frames[label] = pl.read_parquet(path)
        except Exception as exc:
            materialization_errors[label] = f"{type(exc).__name__}: {exc}"
    if materialization_errors:
        add_dimension(
            dimensions,
            "parquet_materialization",
            "NOT DIRECTLY VERIFIED",
            {
                "original": (
                    "MATERIALIZED"
                    if "original" in frames
                    else materialization_errors.get("original")
                ),
                "reproduced": (
                    "MATERIALIZED"
                    if "reproduced" in frames
                    else materialization_errors.get("reproduced")
                ),
            },
        )
        limitations.append("One or both Parquet inputs could not be fully materialized.")
        return "NOT DIRECTLY VERIFIED", EXIT_NOT_VERIFIED

    original_frame = frames["original"]
    reproduced_frame = frames["reproduced"]
    add_dimension(
        dimensions,
        "parquet_materialization",
        "MATCH",
        {
            "original_rows": original_frame.height,
            "reproduced_rows": reproduced_frame.height,
        },
    )

    original_nulls = null_counts(original_frame)
    reproduced_nulls = null_counts(reproduced_frame)
    null_match = original_nulls == reproduced_nulls
    add_dimension(
        dimensions,
        "null_counts",
        "MATCH" if null_match else "DIVERGED",
        {"original": original_nulls, "reproduced": reproduced_nulls},
    )

    original_nan_counts = count_nan_values(original_frame)
    reproduced_nan_counts = count_nan_values(reproduced_frame)
    nan_present = any(original_nan_counts.values()) or any(reproduced_nan_counts.values())
    nan_counts_match = original_nan_counts == reproduced_nan_counts
    if nan_present:
        nan_assessment = "NOT DIRECTLY VERIFIED" if nan_counts_match else "DIVERGED"
        limitations.append(
            "NaN values were detected. NaN equivalence and row matching are not silently assumed."
        )
    else:
        nan_assessment = "MATCH"
    add_dimension(
        dimensions,
        "nan_semantics",
        nan_assessment,
        {
            "original_nan_counts": original_nan_counts,
            "reproduced_nan_counts": reproduced_nan_counts,
            "policy": "Any NaN presence prevents a content MATCH claim.",
        },
    )

    if nan_present:
        add_dimension(
            dimensions,
            "duplicate_rows",
            "NOT DIRECTLY VERIFIED",
            {"reason": "NaN policy prevents occurrence-aware row matching."},
        )
        add_dimension(
            dimensions,
            "values_order_independent",
            "NOT DIRECTLY VERIFIED",
            {"reason": "NaN policy prevents occurrence-aware row matching."},
        )
    else:
        row_result = compare_supported_rows(
            original_frame,
            reproduced_frame,
            max_pair_comparisons,
        )
        add_dimension(
            dimensions,
            "duplicate_rows",
            row_result["duplicate_assessment"],
            row_result["duplicates"],
        )
        add_dimension(
            dimensions,
            "values_order_independent",
            row_result["assessment"],
            row_result["evidence"],
        )
        if row_result["limitation"]:
            limitations.append(row_result["limitation"])

    assessments = [dimension["assessment"] for dimension in dimensions]
    if "DIVERGED" in assessments:
        return "DIVERGED", EXIT_DIVERGED
    if "NOT DIRECTLY VERIFIED" in assessments:
        return "NOT DIRECTLY VERIFIED", EXIT_NOT_VERIFIED
    return "MATCH", EXIT_MATCH


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Read-only comparison of original and reproduced Parquet artifacts or "
            "exact-byte files, with JSON evidence and bounded limitations."
        ),
        epilog=(
            "Exit codes: 0=MATCH, 1=DIVERGED, 2=invalid/unsupported invocation, "
            "3=NOT DIRECTLY VERIFIED. Figures, logs, and persisted model semantics "
            "are outside this helper's scope."
        ),
    )
    parser.add_argument("original", help="Path to the original artifact")
    parser.add_argument("reproduced", help="Path to the reproduced artifact")
    parser.add_argument(
        "--mode",
        choices=("auto", "parquet", "exact"),
        default="auto",
        help="Comparison mode; default: safely infer from both suffixes",
    )
    parser.add_argument(
        "--max-pair-comparisons",
        type=int,
        default=DEFAULT_MAX_PAIR_COMPARISONS,
        help=(
            "Maximum candidate row pairs for order-independent tolerant float matching "
            f"(default: {DEFAULT_MAX_PAIR_COMPARISONS})"
        ),
    )
    parser.add_argument(
        "--max-input-bytes",
        type=int,
        default=DEFAULT_MAX_INPUT_BYTES,
        help=(
            "Maximum compressed bytes per Parquet input before metadata/value "
            f"materialization (default: {DEFAULT_MAX_INPUT_BYTES})"
        ),
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=DEFAULT_MAX_ROWS,
        help=(
            "Maximum Parquet metadata row count per input before value materialization "
            f"(default: {DEFAULT_MAX_ROWS})"
        ),
    )
    args = parser.parse_args()

    original = Path(args.original).resolve(strict=False)
    reproduced = Path(args.reproduced).resolve(strict=False)
    dimensions = []
    limitations = []

    invalid_limits = {
        name: value
        for name, value in (
            ("--max-pair-comparisons", args.max_pair_comparisons),
            ("--max-input-bytes", args.max_input_bytes),
            ("--max-rows", args.max_rows),
        )
        if value < 1
    }
    if invalid_limits:
        add_dimension(
            dimensions,
            "invocation",
            "NOT DIRECTLY VERIFIED",
            {
                "error": "Comparison limits must each be at least 1",
                "invalid": invalid_limits,
            },
        )
        return emit_report(
            "NOT DIRECTLY VERIFIED",
            EXIT_INVALID,
            args.mode,
            original,
            reproduced,
            dimensions,
            limitations,
        )

    mode, mode_error = infer_mode(args.mode, original, reproduced)
    if mode_error:
        add_dimension(
            dimensions,
            "mode_selection",
            "NOT DIRECTLY VERIFIED",
            {"requested": args.mode, "error": mode_error},
        )
        return emit_report(
            "NOT DIRECTLY VERIFIED",
            EXIT_INVALID,
            args.mode,
            original,
            reproduced,
            dimensions,
            limitations,
        )

    add_dimension(
        dimensions,
        "mode_selection",
        "MATCH",
        {"requested": args.mode, "selected": mode},
    )

    original_path_evidence = path_evidence(original)
    reproduced_path_evidence = path_evidence(reproduced)
    paths_available = (
        original_path_evidence["exists"]
        and original_path_evidence["regular_file"]
        and original_path_evidence["readable"]
        and reproduced_path_evidence["exists"]
        and reproduced_path_evidence["regular_file"]
        and reproduced_path_evidence["readable"]
    )
    add_dimension(
        dimensions,
        "path_availability",
        "MATCH" if paths_available else "NOT DIRECTLY VERIFIED",
        {
            "original": original_path_evidence,
            "reproduced": reproduced_path_evidence,
        },
    )
    if not paths_available:
        limitations.append(
            "Both artifacts must exist as readable regular files; missing evidence is never a match."
        )
        return emit_report(
            "NOT DIRECTLY VERIFIED",
            EXIT_NOT_VERIFIED,
            mode,
            original,
            reproduced,
            dimensions,
            limitations,
        )

    if mode == "exact":
        overall, exit_code = compare_exact(
            original,
            reproduced,
            dimensions,
            limitations,
        )
    else:
        overall, exit_code = compare_parquet(
            original,
            reproduced,
            dimensions,
            limitations,
            args.max_pair_comparisons,
            args.max_input_bytes,
            args.max_rows,
        )

    return emit_report(
        overall,
        exit_code,
        mode,
        original,
        reproduced,
        dimensions,
        limitations,
    )


if __name__ == "__main__":
    raise SystemExit(main())
