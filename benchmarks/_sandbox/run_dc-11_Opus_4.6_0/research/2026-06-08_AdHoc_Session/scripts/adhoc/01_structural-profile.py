#!/usr/bin/env python3
"""
Ad Hoc Profiling: Structural profile of Goodreads books dataset.

Task: structural-profile
Purpose: Light structural profiling -- shape, column inventory, missing values,
         basic distributions, granularity assessment, and data quality flags.
Input: /daaf/benchmarks/datasets/test_fixtures/data_ingest/books.csv
Output: Console profiling report (no output file -- exploratory only)
"""

import polars as pl
from pathlib import Path
import os

# --- Config ---
PROJECT_DIR = Path("/daaf/benchmarks/_sandbox/run_dc-11_Opus_4.6_0/research/2026-06-08_AdHoc_Session")
DATA_PATH = Path("/daaf/benchmarks/datasets/test_fixtures/data_ingest/books.csv")

print("=" * 70)
print("STRUCTURAL PROFILE: Goodreads Books Dataset")
print("=" * 70)

# --- File metadata ---
file_size_bytes = os.path.getsize(DATA_PATH)
file_size_mb = file_size_bytes / (1024 * 1024)
print(f"\nFile: {DATA_PATH}")
print(f"File size: {file_size_bytes:,} bytes ({file_size_mb:.2f} MB)")

# --- Load ---
# INTENT: Load CSV with liberal schema inference to capture actual file state.
# REASONING: Using infer_schema_length=10000 to get stable type inference across
# the full file. The CSV has potential issues (leading spaces in column names
# observed in preview), so we load permissively first.
# ASSUMES: File is comma-delimited, UTF-8 encoded.
df = pl.read_csv(DATA_PATH, infer_schema_length=10000, truncate_ragged_lines=True)
print(f"\nLoaded: {df.shape[0]:,} rows x {df.shape[1]} columns")
print(f"Memory estimate: {df.estimated_size() / (1024 * 1024):.2f} MB")

# --- Section 1: Column Inventory ---
print("\n" + "=" * 70)
print("SECTION 1: COLUMN INVENTORY")
print("=" * 70)

# Check for whitespace in column names (data quality flag)
raw_col_names = df.columns
whitespace_cols = [c for c in raw_col_names if c != c.strip() or "  " in c]
if whitespace_cols:
    print(f"\n[QUALITY FLAG] Columns with irregular whitespace: {whitespace_cols}")
    # INTENT: Strip whitespace from column names for cleaner profiling output.
    # REASONING: The CSV has leading spaces in column names (observed: '  num_pages').
    # We rename for display/analysis but document the original names.
    rename_map = {c: c.strip() for c in raw_col_names}
    df = df.rename(rename_map)
    print(f"  Renamed to: {[rename_map[c] for c in whitespace_cols if c != rename_map[c]]}")

print(f"\n{'#':<4} {'Column':<25} {'Polars Type':<15} {'Nulls':>8} {'Null%':>8} {'Unique':>8}")
print("-" * 72)

for i, col in enumerate(df.columns):
    dtype = str(df[col].dtype)
    null_count = df[col].null_count()
    null_pct = null_count / len(df) * 100
    unique_count = df[col].n_unique()
    print(f"{i+1:<4} {col:<25} {dtype:<15} {null_count:>8,} {null_pct:>7.1f}% {unique_count:>8,}")

# --- Section 2: Sample Data ---
print("\n" + "=" * 70)
print("SECTION 2: SAMPLE DATA (first 5 rows)")
print("=" * 70)
print(df.head(5))

print("\n--- Last 3 rows ---")
print(df.tail(3))

# --- Section 3: Missing Value Analysis ---
print("\n" + "=" * 70)
print("SECTION 3: MISSING VALUE ANALYSIS")
print("=" * 70)

total_cells = len(df) * len(df.columns)
total_nulls = sum(df[col].null_count() for col in df.columns)
print(f"\nTotal cells: {total_cells:,}")
print(f"Total null cells: {total_nulls:,} ({total_nulls / total_cells * 100:.2f}%)")

# Per-column missing value detail (only columns with any nulls)
cols_with_nulls = []
for col in df.columns:
    nc = df[col].null_count()
    if nc > 0:
        cols_with_nulls.append((col, nc, nc / len(df) * 100))

if cols_with_nulls:
    print(f"\nColumns with missing values ({len(cols_with_nulls)}):")
    print(f"  {'Column':<25} {'Null Count':>12} {'Null %':>10}")
    print(f"  {'-'*50}")
    for col, nc, pct in sorted(cols_with_nulls, key=lambda x: -x[1]):
        print(f"  {col:<25} {nc:>12,} {pct:>9.2f}%")
else:
    print("\nNo columns with null values detected.")

# Also check for empty strings in string columns (a different kind of missing)
print("\n--- Empty string check (string columns) ---")
for col in df.columns:
    if df[col].dtype == pl.String:
        empty_count = (df[col] == "").sum()
        if empty_count > 0:
            print(f"  {col}: {empty_count:,} empty strings ({empty_count / len(df) * 100:.2f}%)")

# --- Section 4: Numeric Column Distributions ---
print("\n" + "=" * 70)
print("SECTION 4: NUMERIC COLUMN DISTRIBUTIONS")
print("=" * 70)

numeric_cols = [col for col in df.columns if df[col].dtype in (pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.Float32, pl.Float64)]

if numeric_cols:
    for col in numeric_cols:
        series = df[col].drop_nulls()
        if len(series) == 0:
            print(f"\n  {col}: ALL NULL -- skipped")
            continue

        print(f"\n  {col} ({df[col].dtype}, {df[col].null_count()} nulls)")
        print(f"    Count:    {len(series):,}")
        print(f"    Min:      {series.min()}")
        print(f"    Max:      {series.max()}")
        print(f"    Mean:     {series.mean():.4f}")
        print(f"    Median:   {series.median():.4f}")
        print(f"    Std dev:  {series.std():.4f}")

        # Percentiles
        q_vals = [0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99]
        pcts = series.quantile(0.01), series.quantile(0.05), series.quantile(0.25), series.quantile(0.50), series.quantile(0.75), series.quantile(0.95), series.quantile(0.99)
        print(f"    Percentiles: p1={pcts[0]}, p5={pcts[1]}, p25={pcts[2]}, p50={pcts[3]}, p75={pcts[4]}, p95={pcts[5]}, p99={pcts[6]}")

        # Check for suspicious values
        if series.min() < 0:
            neg_count = (series < 0).sum()
            print(f"    [FLAG] Negative values: {neg_count:,}")

        if series.min() == 0:
            zero_count = (series == 0).sum()
            print(f"    [NOTE] Zero values: {zero_count:,}")

        # Check for potential sentinel values
        for sentinel in [999, 9999, -1, -2, -9, -99]:
            sentinel_count = (series == sentinel).sum()
            if sentinel_count > 0:
                print(f"    [FLAG] Potential sentinel value {sentinel}: {sentinel_count:,} occurrences")
else:
    print("  No numeric columns detected.")

# --- Section 5: String/Categorical Column Distributions ---
print("\n" + "=" * 70)
print("SECTION 5: STRING/CATEGORICAL COLUMN DISTRIBUTIONS")
print("=" * 70)

string_cols = [col for col in df.columns if df[col].dtype == pl.String]

for col in string_cols:
    series = df[col].drop_nulls()
    n_unique = series.n_unique()

    print(f"\n  {col} (String, {df[col].null_count()} nulls, {n_unique:,} unique values)")

    # String length stats
    if len(series) > 0:
        lengths = series.str.len_chars()
        print(f"    String length: min={lengths.min()}, max={lengths.max()}, mean={lengths.mean():.1f}")

    # Top values for columns with fewer than 50 unique values (categorical-like)
    if n_unique <= 50:
        print(f"    --- Full value distribution ({n_unique} values) ---")
        vc = series.value_counts().sort("count", descending=True)
        for row in vc.iter_rows():
            val, cnt = row
            pct = cnt / len(df) * 100
            print(f"      {str(val):<40} {cnt:>6,} ({pct:>5.1f}%)")
    else:
        # Show top 15 for high-cardinality columns
        print(f"    --- Top 15 values (of {n_unique:,}) ---")
        vc = series.value_counts().sort("count", descending=True).head(15)
        for row in vc.iter_rows():
            val, cnt = row
            pct = cnt / len(df) * 100
            display_val = str(val)[:60]
            print(f"      {display_val:<62} {cnt:>6,} ({pct:>5.1f}%)")

# --- Section 6: Granularity Assessment ---
print("\n" + "=" * 70)
print("SECTION 6: GRANULARITY ASSESSMENT (Candidate Keys)")
print("=" * 70)

n_rows = len(df)
print(f"\nTotal rows: {n_rows:,}")

# INTENT: Test candidate key columns for uniqueness to determine data grain.
# REASONING: bookID is the obvious candidate. Also test isbn and isbn13 as
# alternative identifiers. Composite keys tested if singles fail.

# Test single-column candidates
single_candidates = ["bookID", "isbn", "isbn13", "title"]
for col in single_candidates:
    if col in df.columns:
        n_unique = df[col].n_unique()
        null_count = df[col].null_count()
        is_unique = n_unique == n_rows
        print(f"\n  {col}:")
        print(f"    Unique values: {n_unique:,} / {n_rows:,} rows")
        print(f"    Nulls: {null_count:,}")
        print(f"    Is unique key? {'YES' if is_unique else 'NO'}")

        if not is_unique and n_unique < n_rows:
            # Show duplicate values
            dup_count = n_rows - n_unique
            print(f"    Duplicate entries: {dup_count:,}")

            # Show sample duplicates
            if df[col].dtype == pl.String:
                dupes = (
                    df.group_by(col)
                    .len()
                    .filter(pl.col("len") > 1)
                    .sort("len", descending=True)
                    .head(5)
                )
            else:
                dupes = (
                    df.group_by(col)
                    .len()
                    .filter(pl.col("len") > 1)
                    .sort("len", descending=True)
                    .head(5)
                )
            print(f"    Top duplicate values:")
            for row in dupes.iter_rows():
                val, cnt = row
                print(f"      {val}: {cnt} rows")

# Test composite candidates if needed
print("\n  --- Composite key tests ---")
composite_candidates = [
    ["title", "authors"],
    ["isbn", "isbn13"],
    ["bookID", "title"],
]
for combo in composite_candidates:
    if all(c in df.columns for c in combo):
        n_unique = df.select(combo).n_unique()
        is_unique = n_unique == n_rows
        print(f"  {combo}: {n_unique:,} unique / {n_rows:,} rows -> {'UNIQUE' if is_unique else 'NOT UNIQUE'}")

# --- Section 7: Data Quality Flags ---
print("\n" + "=" * 70)
print("SECTION 7: DATA QUALITY FLAGS")
print("=" * 70)

# 7.1: Duplicate row check
n_unique_rows = df.n_unique()
n_dup_rows = n_rows - n_unique_rows
print(f"\n  7.1 Duplicate rows: {n_dup_rows:,} exact duplicates found")

# 7.2: Check for completely empty rows (all null)
null_per_row = df.with_row_index().select(
    "index",
    pl.sum_horizontal([pl.col(c).is_null() for c in df.columns]).alias("null_count")
)
all_null_rows = null_per_row.filter(pl.col("null_count") == len(df.columns)).shape[0]
print(f"  7.2 Completely empty rows: {all_null_rows:,}")

# 7.3: Encoding/character issues in string columns
print(f"\n  7.3 Encoding checks:")
for col in string_cols:
    series = df[col].drop_nulls()
    if len(series) == 0:
        continue
    # Check for potential encoding artifacts (common ones)
    # INTENT: Detect encoding issues that would affect downstream text processing.
    # REASONING: CSV files from web sources often have mixed encodings.
    suspicious_patterns = 0
    for pattern in ["\x00", "\ufffd", "Ã", "â€"]:
        count = series.str.contains(pattern, literal=True).sum()
        if count > 0:
            suspicious_patterns += count
            print(f"    {col}: {count:,} rows contain potential encoding artifact '{pattern}'")
    if suspicious_patterns == 0 and col == string_cols[0]:
        print(f"    No encoding artifacts detected in string columns.")

# 7.4: Consistency checks for specific columns
print(f"\n  7.4 Data consistency checks:")

# Check rating range (should be 0-5 for Goodreads)
if "average_rating" in df.columns:
    ratings = df["average_rating"].drop_nulls()
    if ratings.dtype in (pl.Float32, pl.Float64, pl.Int64):
        out_of_range = ((ratings < 0) | (ratings > 5)).sum()
        print(f"    average_rating range: [{ratings.min()}, {ratings.max()}] -- out of [0,5] range: {out_of_range:,}")

# Check num_pages for unreasonable values
if "num_pages" in df.columns:
    pages = df["num_pages"].drop_nulls()
    if pages.dtype in (pl.Int64, pl.Float64):
        zero_pages = (pages == 0).sum()
        huge_pages = (pages > 5000).sum()
        print(f"    num_pages: zeros={zero_pages:,}, >5000 pages={huge_pages:,}")

# Check ratings_count and text_reviews_count for zeros
if "ratings_count" in df.columns:
    rc = df["ratings_count"].drop_nulls()
    if rc.dtype in (pl.Int64, pl.Float64):
        zero_ratings = (rc == 0).sum()
        print(f"    ratings_count: zeros={zero_ratings:,}")

# Check publication_date format consistency
if "publication_date" in df.columns:
    dates = df["publication_date"].drop_nulls()
    if dates.dtype == pl.String:
        # Sample some dates to check format
        sample_dates = dates.head(20).to_list()
        print(f"    publication_date: sample format = {sample_dates[:5]}")
        # Check for dates that don't match M/D/YYYY pattern
        has_slash = dates.str.contains("/").sum()
        has_dash = dates.str.contains("-").sum()
        print(f"    publication_date: rows with '/': {has_slash:,}, rows with '-': {has_dash:,}")

# 7.5: ISBN validation
print(f"\n  7.5 ISBN checks:")
if "isbn" in df.columns:
    isbn_series = df["isbn"].drop_nulls()
    if isbn_series.dtype == pl.String:
        isbn_lengths = isbn_series.str.len_chars().value_counts().sort("len_chars")
        print(f"    isbn string length distribution:")
        for row in isbn_lengths.iter_rows():
            length, cnt = row
            print(f"      length {length}: {cnt:,} values")

if "isbn13" in df.columns:
    isbn13_series = df["isbn13"].drop_nulls()
    isbn13_dtype = isbn13_series.dtype
    print(f"    isbn13 stored as: {isbn13_dtype}")
    if isbn13_dtype in (pl.Int64, pl.Float64):
        # Check if values look like 13-digit ISBNs
        min_val = isbn13_series.min()
        max_val = isbn13_series.max()
        print(f"    isbn13 range: [{min_val}, {max_val}]")
        # Check for values that don't start with 978 or 979
        as_str = isbn13_series.cast(pl.Int64).cast(pl.String)
        starts_978 = as_str.str.starts_with("978").sum()
        starts_979 = as_str.str.starts_with("979").sum()
        other = len(as_str) - starts_978 - starts_979
        print(f"    isbn13 prefix: 978={starts_978:,}, 979={starts_979:,}, other={other:,}")

# 7.6: bookID sequence check
if "bookID" in df.columns:
    bid = df["bookID"].drop_nulls()
    if bid.dtype == pl.Int64:
        print(f"\n  7.6 bookID sequence:")
        print(f"    Range: [{bid.min()}, {bid.max()}]")
        print(f"    Count: {len(bid):,}")
        expected_if_sequential = bid.max() - bid.min() + 1
        print(f"    Expected if sequential: {expected_if_sequential:,}")
        print(f"    Gaps: {expected_if_sequential - len(bid):,} missing IDs (non-sequential)")

# --- Summary ---
print("\n" + "=" * 70)
print("PROFILING COMPLETE")
print("=" * 70)
print(f"\nDataset: Goodreads Books")
print(f"Shape: {df.shape[0]:,} rows x {df.shape[1]} columns")
print(f"File size: {file_size_mb:.2f} MB")
print(f"Memory: {df.estimated_size() / (1024 * 1024):.2f} MB")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-06-08 02:21:53
# Command: python3 /daaf/benchmarks/_sandbox/run_dc-11_Opus_4.6_0/research/2026-06-08_AdHoc_Session/scripts/adhoc/01_structural-profile.py
# Duration: 0s
# Exit code: 1
#
# --- STDOUT ---
# ======================================================================
# STRUCTURAL PROFILE: Goodreads Books Dataset
# ======================================================================
# 
# File: /daaf/benchmarks/datasets/test_fixtures/data_ingest/books.csv
# File size: 1,559,650 bytes (1.49 MB)
# Traceback (most recent call last):
#   File "/daaf/benchmarks/_sandbox/run_dc-11_Opus_4.6_0/research/2026-06-08_AdHoc_Session/scripts/adhoc/01_structural-profile.py", line 36, in <module>
#     df = pl.read_csv(DATA_PATH, infer_schema_length=10000, truncate_ragged_lines=True)
#          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/_utils/deprecation.py", line 128, in wrapper
#     return function(*args, **kwargs)
#            ^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/_utils/deprecation.py", line 128, in wrapper
#     return function(*args, **kwargs)
#            ^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/_utils/deprecation.py", line 128, in wrapper
#     return function(*args, **kwargs)
#            ^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/io/csv/functions.py", line 560, in read_csv
#     df = _read_csv_impl(
#          ^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/site-packages/polars/io/csv/functions.py", line 708, in _read_csv_impl
#     pydf = PyDataFrame.read_csv(
#            ^^^^^^^^^^^^^^^^^^^^^
# polars.exceptions.ComputeError: could not parse `"Why Are All The Black Kids Sitting Together in the Cafeteria?": A Psychologist Explains the Development of Racial Identity` as dtype `str` at column 'title' (column number 2)
# 
# The current offset in the file is 3043 bytes.
# 
# You might want to try:
# - increasing `infer_schema_length` (e.g. `infer_schema_length=10000`),
# - specifying correct dtype with the `schema_overrides` argument
# - setting `ignore_errors` to `True`,
# - adding `"Why Are All The Black Kids Sitting Together in the Cafeteria?": A Psychologist Explains the Development of Racial Identity` to the `null_values` list.
# 
# Original error: ```invalid csv file
# 
# Field `"Why Are All The Black Kids Sitting Together in the Cafeteria?": A Psychologist Explains the Development of Racial Identity` is not properly escaped.```
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
