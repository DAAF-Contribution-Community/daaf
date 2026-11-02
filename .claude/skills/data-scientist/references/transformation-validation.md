# Transformation Validation

Patterns and techniques for validating data transformations. NEVER assume a transformation worked correctly.

## Contents

- [Before/After Validation Pattern](#beforeafter-validation-pattern)
- [Row Count Validation](#row-count-validation)
- [Join Validation](#join-validation)
- [Aggregation Validation](#aggregation-validation)
- [Sample-Based Verification](#sample-based-verification)
- [Schema Validation (Keep It Simple)](#schema-validation-keep-it-simple)
- [Common Errors and Detection](#common-errors-and-detection)

## Before/After Validation Pattern

**Every transformation should follow this pattern:**

**Python:**
```python
import polars as pl

# ============================================================
# STEP 1: Document pre-transformation state
# ============================================================
pre_shape = df.shape
pre_columns = df.columns.copy()
pre_sample = df.sample(10, seed=42)  # Reproducible sample

# Record relevant aggregates for validation
pre_row_count = len(df)
pre_null_counts = {col: df[col].null_count() for col in df.columns}

# For aggregations, record sums of additive metrics
pre_total = df.select(pl.col("amount").sum()).item() if "amount" in df.columns else None

# ============================================================
# STEP 2: Perform transformation (with comments)
# ============================================================
# INTENT: [State what you're trying to accomplish]
# EXPECTED: [State expected changes - row count, columns, etc.]
# INVARIANTS: [State what should NOT change]

result = df.filter(pl.col("status") == "active")

# ============================================================
# STEP 3: Validate post-transformation state
# ============================================================
post_shape = result.shape
post_columns = result.columns

# Basic shape validation
print(f"Shape change: {pre_shape} -> {post_shape}")
print(f"Row change: {pre_row_count} -> {len(result)} ({len(result) - pre_row_count:+d})")
print(f"Column change: {len(pre_columns)} -> {len(post_columns)}")

# Verify columns preserved/changed as expected
added_cols = set(post_columns) - set(pre_columns)
removed_cols = set(pre_columns) - set(post_columns)
if added_cols:
    print(f"Columns added: {added_cols}")
if removed_cols:
    print(f"Columns removed: {removed_cols}")

# Sample comparison
sample_ids = pre_sample["id"].to_list()[:5]
print(f"\nSample before:\n{pre_sample.filter(pl.col('id').is_in(sample_ids))}")
print(f"\nSample after (if present):\n{result.filter(pl.col('id').is_in(sample_ids))}")
```

**R:**
```r
library(dplyr)
library(arrow)

# ============================================================
# STEP 1: Document pre-transformation state
# ============================================================
pre_shape <- dim(df)
pre_columns <- names(df)
set.seed(42)
pre_sample <- df |> slice_sample(n = 10)

# Record relevant aggregates for validation
pre_row_count <- nrow(df)
pre_null_counts <- sapply(df, \(x) sum(is.na(x)))

# For aggregations, record sums of additive metrics
pre_total <- if ("amount" %in% names(df)) sum(df$amount, na.rm = TRUE) else NULL

# ============================================================
# STEP 2: Perform transformation (with comments)
# ============================================================
# INTENT: [State what you're trying to accomplish]
# EXPECTED: [State expected changes - row count, columns, etc.]
# INVARIANTS: [State what should NOT change]

result <- df |> filter(status == "active")

# ============================================================
# STEP 3: Validate post-transformation state
# ============================================================
post_shape <- dim(result)
post_columns <- names(result)

# Basic shape validation
cat(sprintf("Shape change: %s -> %s\n",
            paste(pre_shape, collapse = " x "), paste(post_shape, collapse = " x ")))
cat(sprintf("Row change: %d -> %d (%+d)\n", pre_row_count, nrow(result), nrow(result) - pre_row_count))
cat(sprintf("Column change: %d -> %d\n", length(pre_columns), length(post_columns)))

# Verify columns preserved/changed as expected
added_cols <- setdiff(post_columns, pre_columns)
removed_cols <- setdiff(pre_columns, post_columns)
if (length(added_cols) > 0) cat("Columns added:", paste(added_cols, collapse = ", "), "\n")
if (length(removed_cols) > 0) cat("Columns removed:", paste(removed_cols, collapse = ", "), "\n")

# Sample comparison
sample_ids <- pre_sample$id[1:5]
cat("\nSample before:\n")
print(pre_sample |> filter(id %in% sample_ids))
cat("\nSample after (if present):\n")
print(result |> filter(id %in% sample_ids))
```

## Row Count Validation

Different operations have different expected row count behaviors:

| Operation | Expected Row Count Change |
|-----------|---------------------------|
| Filter | Decrease (or stay same if no matches filtered) |
| Select | Same |
| With_columns | Same |
| Join (inner) | ≤ left count if right keys are unique; a repeated matching right key can push it above both inputs |
| Join (left) | = left count if right keys are unique; more if a matching right key repeats |
| Join (outer) | ≥ max(left, right) |
| Group_by.agg | = number of unique groups |
| Concat (vertical) | = sum of input row counts |
| Unique/Distinct | ≤ original count |
| Explode | ≥ original count |

### Validation Pattern

**Python:**
```python
# Validate row count change
change = post_count - pre_count
pct_change = (change / pre_count * 100) if pre_count > 0 else 0
print(f"Row count: {pre_count:,} → {post_count:,} ({change:+,}, {pct_change:+.1f}%)")
if expected_change == "decrease" and change > 0:
    print("WARNING: Expected decrease but rows increased!")
```

**R:**
```r
# Validate row count change
change <- post_count - pre_count
pct_change <- if (pre_count > 0) change / pre_count * 100 else 0
cat(sprintf("Row count: %s -> %s (%+d, %+.1f%%)\n",
            format(pre_count, big.mark = ","), format(post_count, big.mark = ","),
            change, pct_change))
if (expected_change == "decrease" && change > 0) {
  cat("WARNING: Expected decrease but rows increased!\n")
}
```

## Join Validation

Joins are a common source of subtle bugs. Always validate.

### Pre-Join Checks

**Python:**
```python
# Pre-join checks
for key in join_keys:
    left_type = left_df[key].dtype
    right_type = right_df[key].dtype
    if left_type != right_type:
        print(f"WARNING: Type mismatch for '{key}': {left_type} vs {right_type}")

    left_unique = left_df[key].n_unique()
    right_unique = right_df[key].n_unique()
    left_nulls = left_df[key].null_count()
    right_nulls = right_df[key].null_count()
    print(f"Key '{key}': left={left_unique:,} unique ({left_nulls} nulls), right={right_unique:,} unique ({right_nulls} nulls)")

left_keys_set = set(left_df[join_keys[0]].unique().to_list())
right_keys_set = set(right_df[join_keys[0]].unique().to_list())
overlap = len(left_keys_set & right_keys_set)
print(f"Key overlap: {overlap:,} ({overlap/len(left_keys_set):.1%} of left, {overlap/len(right_keys_set):.1%} of right)")
```

**R:**
```r
# Pre-join checks
for (key in join_keys) {
  left_type <- class(left_df[[key]])
  right_type <- class(right_df[[key]])
  if (!identical(left_type, right_type)) {
    cat(sprintf("WARNING: Type mismatch for '%s': %s vs %s\n", key, left_type, right_type))
  }

  left_unique <- n_distinct(left_df[[key]])
  right_unique <- n_distinct(right_df[[key]])
  left_nulls <- sum(is.na(left_df[[key]]))
  right_nulls <- sum(is.na(right_df[[key]]))
  cat(sprintf("Key '%s': left=%s unique (%d nulls), right=%s unique (%d nulls)\n",
              key, format(left_unique, big.mark = ","), left_nulls,
              format(right_unique, big.mark = ","), right_nulls))
}

left_keys_set <- unique(left_df[[join_keys[1]]])
right_keys_set <- unique(right_df[[join_keys[1]]])
overlap <- length(intersect(left_keys_set, right_keys_set))
cat(sprintf("Key overlap: %s (%.1f%% of left, %.1f%% of right)\n",
            format(overlap, big.mark = ","),
            overlap / length(left_keys_set) * 100,
            overlap / length(right_keys_set) * 100))
```

### Post-Join Validation

**Python:**
```python
# Post-join validation
left_count = len(left_df)
right_count = len(right_df)
result_count = len(result_df)
print(f"Post-join shape: {result_df.shape}")
print(f"Left: {left_count:,}, Right: {right_count:,}, Result: {result_count:,}")

# Fan-out: a repeated right key duplicates every left row it matches, even when the
# result stays smaller than the right table. Or let polars enforce it:
# left_df.join(right_df, on=join_keys, how="left", validate="m:1")
right_dup_rows = right_df.select(join_keys).is_duplicated().sum()
if right_dup_rows > 0:
    print(f"WARNING: {right_dup_rows:,} right rows share a join key — each matching left row is duplicated (fan-out)")
if join_type == "left" and result_count != left_count:
    print(f"WARNING: left join changed the row count ({left_count:,} -> {result_count:,})")

if result_count > max(left_count, right_count):
    print(f"WARNING: Result has more rows than either input — possible many-to-many duplication!")

# For left joins, verify all left keys are present
if join_type == "left":
    left_keys_set = set(left_df[join_keys[0]].unique().to_list())
    result_keys_set = set(result_df[join_keys[0]].unique().to_list())
    missing = left_keys_set - result_keys_set
    if missing:
        print(f"WARNING: {len(missing)} left keys missing from result!")

# Check for new nulls introduced by the join
result_nulls = result_df.null_count()
print(f"Result null counts:\n{result_nulls}")
```

**R:**
```r
# Post-join validation
left_count <- nrow(left_df)
right_count <- nrow(right_df)
result_count <- nrow(result_df)
cat(sprintf("Post-join shape: %d x %d\n", result_count, ncol(result_df)))
cat(sprintf("Left: %s, Right: %s, Result: %s\n",
            format(left_count, big.mark = ","), format(right_count, big.mark = ","),
            format(result_count, big.mark = ",")))

# Fan-out: a repeated right key duplicates every left row it matches, even when the
# result stays smaller than the right table. Or let dplyr enforce it:
# left_join(left_df, right_df, by = join_keys, relationship = "many-to-one")
right_keys_df <- right_df[join_keys]
right_dup_rows <- sum(duplicated(right_keys_df) | duplicated(right_keys_df, fromLast = TRUE))
if (right_dup_rows > 0) {
  cat(sprintf("WARNING: %s right rows share a join key -- each matching left row is duplicated (fan-out)\n",
              format(right_dup_rows, big.mark = ",")))
}
if (join_type == "left" && result_count != left_count) {
  cat(sprintf("WARNING: left join changed the row count (%s -> %s)\n",
              format(left_count, big.mark = ","), format(result_count, big.mark = ",")))
}

if (result_count > max(left_count, right_count)) {
  cat("WARNING: Result has more rows than either input -- possible many-to-many duplication!\n")
}

# For left joins, verify all left keys are present
if (join_type == "left") {
  left_keys_set <- unique(left_df[[join_keys[1]]])
  result_keys_set <- unique(result_df[[join_keys[1]]])
  missing <- setdiff(left_keys_set, result_keys_set)
  if (length(missing) > 0) {
    cat(sprintf("WARNING: %d left keys missing from result!\n", length(missing)))
  }
}

# Check for new nulls introduced by the join
result_nulls <- sapply(result_df, \(x) sum(is.na(x)))
cat("Result null counts:\n")
print(result_nulls[result_nulls > 0])
```

### Using Join Indicators

**Python:**
```python
# Join with match indicator (Polars doesn't have pandas-style indicator)
right_with_marker = right_df.with_columns(pl.lit(True).alias("_right_matched"))
result = left_df.join(right_with_marker, on=on, how="left")
result = result.with_columns(pl.col("_right_matched").fill_null(False))

matched = result.filter(pl.col("_right_matched")).height
unmatched = result.filter(~pl.col("_right_matched")).height
print(f"Matched: {matched:,}, Unmatched: {unmatched:,}")
```

**R:**
```r
# Join with match indicator
right_with_marker <- right_df |> mutate(.right_matched = TRUE)
result <- left_df |> left_join(right_with_marker, by = on)
result <- result |> mutate(.right_matched = coalesce(.right_matched, FALSE))

matched <- sum(result$.right_matched)
unmatched <- sum(!result$.right_matched)
cat(sprintf("Matched: %s, Unmatched: %s\n",
            format(matched, big.mark = ","), format(unmatched, big.mark = ",")))
```

## Aggregation Validation

### Sum Conservation

For additive metrics, the total should be preserved (or explainably different).

**Python:**
```python
# Validate aggregation preserves sum
pre_sum = pre_df[sum_column].sum()
post_sum = post_df[sum_column].sum()
diff = abs(pre_sum - post_sum)
print(f"Sum of '{sum_column}': {pre_sum:,.2f} → {post_sum:,.2f} (diff: {diff:,.2f})")
# Relative tolerance: regrouping float additions changes the last bits, so a fixed 1e-6
# false-alarms on large totals; scale by the sum of absolute values (signs may cancel)
tol = 1e-12 * max(1.0, pre_df[sum_column].abs().sum())
assert diff <= tol, f"STOP: Sum changed during aggregation by {diff}"
```

**R:**
```r
# Validate aggregation preserves sum
pre_sum <- sum(pre_df[[sum_column]], na.rm = TRUE)
post_sum <- sum(post_df[[sum_column]], na.rm = TRUE)
diff_val <- abs(pre_sum - post_sum)
cat(sprintf("Sum of '%s': %s -> %s (diff: %s)\n",
            sum_column, format(pre_sum, big.mark = ",", nsmall = 2),
            format(post_sum, big.mark = ",", nsmall = 2),
            format(diff_val, big.mark = ",", nsmall = 2)))
# Relative tolerance: regrouping float additions changes the last bits, so a fixed 1e-6
# false-alarms on large totals; scale by the sum of absolute values (signs may cancel)
tol <- 1e-12 * max(1, sum(abs(pre_df[[sum_column]]), na.rm = TRUE))
stopifnot("STOP: Sum changed during aggregation" = diff_val <= tol)
```

### Group Count Validation

**Python:**
```python
# Validate group counts
expected_groups = pre_df.select(group_columns).n_unique()
actual_groups = len(post_df)
print(f"Group count: expected {expected_groups:,} unique combinations, got {actual_groups:,} rows")
assert expected_groups == actual_groups, f"STOP: Group count mismatch ({expected_groups} vs {actual_groups})"
```

**R:**
```r
# Validate group counts
expected_groups <- pre_df |> distinct(across(all_of(group_columns))) |> nrow()
actual_groups <- nrow(post_df)
cat(sprintf("Group count: expected %s unique combinations, got %s rows\n",
            format(expected_groups, big.mark = ","), format(actual_groups, big.mark = ",")))
stopifnot("STOP: Group count mismatch" = expected_groups == actual_groups)
```

### Row Accounting

**Python:**
```python
# Validate row accounting — all rows accounted for in aggregation
pre_count = len(pre_df)
# Include pl.len().alias("n_rows") in the aggregation that produced post_df
total_accounted = post_df["n_rows"].sum()
print(f"Row accounting: {pre_count:,} original rows, {total_accounted:,} accounted for in groups")
assert pre_count == total_accounted, f"STOP: {pre_count - total_accounted} rows unaccounted for!"
```

**R:**
```r
# Validate row accounting -- all rows accounted for in aggregation
pre_count <- nrow(pre_df)
total_accounted <- sum(post_df$n_rows)  # add n_rows = n() to the summarise() that built post_df
cat(sprintf("Row accounting: %s original rows, %s accounted for in groups\n",
            format(pre_count, big.mark = ","), format(total_accounted, big.mark = ",")))
stopifnot("STOP: Rows unaccounted for" = pre_count == total_accounted)
```

## Sample-Based Verification

Manual spot-checking catches errors that automated checks miss.

### Selecting Representative Samples

**Python:**
```python
# Select a diverse verification sample
random_sample = df.sample(5, seed=42)
edge_sample = pl.concat([df.head(2), df.tail(2)])
null_cols = [col for col in df.columns if df[col].null_count() > 0]
null_sample = df.filter(pl.col(null_cols[0]).is_null()).head(2) if null_cols else df.clear()
sample = pl.concat([random_sample, edge_sample, null_sample]).unique().head(10)
print(f"Verification sample: {len(sample)} rows")
print(sample)
```

**R:**
```r
# Select a diverse verification sample
set.seed(42)
random_sample <- df |> slice_sample(n = 5)
edge_sample <- bind_rows(df |> slice_head(n = 2), df |> slice_tail(n = 2))
null_cols <- names(df)[sapply(df, \(x) any(is.na(x)))]
null_sample <- if (length(null_cols) > 0) {
  df |> filter(is.na(.data[[null_cols[1]]])) |> slice_head(n = 2)
} else {
  tibble()
}
sample_df <- bind_rows(random_sample, edge_sample, null_sample) |> distinct() |> slice_head(n = 10)
cat(sprintf("Verification sample: %d rows\n", nrow(sample_df)))
print(sample_df)
```

### Manual Verification Template

**Python:**
```python
# Template for manual verification
print("=== Manual Verification ===")
print("For each sample row, verify:")
print("1. Input values are as expected")
print("2. Transformation logic was applied correctly")
print("3. Output values are correct")
print()

sample = pre_df.sample(5, seed=42)
sample_ids = sample["id"].to_list()

print("BEFORE transformation:")
print(pre_df.filter(pl.col("id").is_in(sample_ids)))

print("\nAFTER transformation:")
print(result.filter(pl.col("id").is_in(sample_ids)))

print("\nManual check: Do the transformations look correct? (Y/N)")
```

**R:**
```r
# Template for manual verification
cat("=== Manual Verification ===\n")
cat("For each sample row, verify:\n")
cat("1. Input values are as expected\n")
cat("2. Transformation logic was applied correctly\n")
cat("3. Output values are correct\n\n")

set.seed(42)
sample_df <- pre_df |> slice_sample(n = 5)
sample_ids <- sample_df$id

cat("BEFORE transformation:\n")
print(pre_df |> filter(id %in% sample_ids))

cat("\nAFTER transformation:\n")
print(result |> filter(id %in% sample_ids))

cat("\nManual check: Do the transformations look correct? (Y/N)\n")
```

### Schema Validation (Keep It Simple)

For one-and-done scripts, validate schemas inline:

**Python:**
```python
# Check required columns exist
required = ["id", "amount", "category"]
missing = [c for c in required if c not in df.columns]
assert not missing, f"Missing columns: {missing}"

# Check types
assert df["id"].dtype == pl.Int64, f"Expected Int64, got {df['id'].dtype}"
```

**R:**
```r
# Check required columns exist
required <- c("id", "amount", "category")
missing <- setdiff(required, names(df))
stopifnot("Missing columns" = length(missing) == 0)

# Check types
stopifnot("Expected integer for id" = is.integer(df$id))
```

> **Tool note (Pandera):** the Python `pandera` library offers declarative DataFrame
> schema validation, but it is **not installed** in the DAAF environment, and no
> equivalent R schema-validation package is installed either. The supported route in
> both languages is the inline pattern shown above (`assert` in Python,
> `stopifnot()` in R) — consistent with DAAF's sequential-script code style.

## Common Errors and Detection

### Silent Type Coercion

**Python:**
```python
# Problem: Type conversion can silently create nulls or lose precision
pre_null_count = df["column"].null_count()

# Float -> Int casts truncate silently (1.7 -> 1) and create no nulls: count changed values first
if df["column"].dtype.is_float():
    n_truncated = df.select(
        (pl.col("column") != pl.col("column").cast(pl.Int64, strict=False).cast(pl.Float64)).sum()
    ).item()
    if n_truncated > 0:
        print(f"WARNING: Casting to Int64 will truncate {n_truncated} non-integer values!")

# strict=False turns unparseable values into nulls (the default strict=True raises instead)
df = df.with_columns(pl.col("column").cast(pl.Int64, strict=False))

post_null_count = df["column"].null_count()
new_nulls = post_null_count - pre_null_count

if new_nulls > 0:
    print(f"WARNING: Type coercion created {new_nulls} new null values!")
```

**R:**
```r
# Problem: Type conversion can silently create NAs or lose precision
pre_na_count <- sum(is.na(df$column))

# Double -> integer conversion truncates silently (1.7 -> 1) and creates no NA: count changed values first
if (is.double(df$column)) {
  n_truncated <- sum(df$column != trunc(df$column), na.rm = TRUE)
  if (n_truncated > 0) {
    cat(sprintf("WARNING: Converting to integer will truncate %d non-integer values!\n", n_truncated))
  }
}

# This might silently introduce NAs (e.g., as.integer("abc") -> NA)
df <- df |> mutate(column = as.integer(column))

post_na_count <- sum(is.na(df$column))
new_nas <- post_na_count - pre_na_count

if (new_nas > 0) {
  cat(sprintf("WARNING: Type coercion created %d new NA values!\n", new_nas))
}
```

### Filter Returning Empty

**Python:**
```python
# Problem: Filter conditions might match nothing
result = df.filter(pl.col("status") == "active")

if len(result) == 0:
    print("WARNING: Filter returned no rows!")
    print("Check if filter condition is correct.")
    print(f"Unique values in 'status': {df['status'].unique().to_list()}")
```

**R:**
```r
# Problem: Filter conditions might match nothing
result <- df |> filter(status == "active")

if (nrow(result) == 0) {
  cat("WARNING: Filter returned no rows!\n")
  cat("Check if filter condition is correct.\n")
  cat("Unique values in 'status':", paste(unique(df$status), collapse = ", "), "\n")
}
```

### Join Key Type Mismatch

**Python:**
```python
# Check join key types match (polars raises on Int vs String and upcasts compatible numeric
# types; the silent case is same-dtype formatting, e.g. '01' vs '1', which the key-overlap
# line in Pre-Join Checks catches)
for key in join_keys:
    left_type = left_df[key].dtype
    right_type = right_df[key].dtype
    if left_type != right_type:
        print(f"WARNING: Type mismatch for '{key}': {left_type} vs {right_type} — align the key types before joining")
```

**R:**
```r
# Check join key types match (dplyr errors on incompatible types and matches integer with
# double; the silent case is same-type formatting, e.g. "01" vs "1", which the key-overlap
# line in Pre-Join Checks catches)
for (key in join_keys) {
  left_type <- class(left_df[[key]])
  right_type <- class(right_df[[key]])
  if (!identical(left_type, right_type)) {
    cat(sprintf("WARNING: Type mismatch for '%s': %s vs %s -- align the key types before joining\n",
                key, left_type, right_type))
  }
}
```

### Off-by-One in Group Operations

**Python:**
```python
# Problem: Joins do not match null keys by default (group_by keeps them as a group)
null_key_rows = df.filter(pl.col("group_key").is_null())
if len(null_key_rows) > 0:
    print(f"WARNING: {len(null_key_rows)} rows have null group keys")
    print("They form their own null group in group_by and match nothing in a join!")
```

**R:**
```r
# Problem: group_by keeps NA as a group and joins match NA by default (na_matches = "na");
# check NA keys explicitly
null_key_rows <- df |> filter(is.na(group_key))
if (nrow(null_key_rows) > 0) {
  cat(sprintf("WARNING: %d rows have NA group keys\n", nrow(null_key_rows)))
  cat("They form their own NA group in group_by and match other NA keys in a join!\n")
}
```

### Accidental Column Overwrite

**Python:**
```python
# Problem: with_columns can silently overwrite existing columns
existing_cols = set(df.columns)
new_col_names = ["calculated_value", "status"]  # Ops we're adding

overlap = existing_cols & set(new_col_names)
if overlap:
    print(f"WARNING: These columns will be overwritten: {overlap}")
    print("Is this intentional?")
```

**R:**
```r
# Problem: mutate can silently overwrite existing columns
existing_cols <- names(df)
new_col_names <- c("calculated_value", "status")  # Columns we're adding

overlap <- intersect(existing_cols, new_col_names)
if (length(overlap) > 0) {
  cat("WARNING: These columns will be overwritten:", paste(overlap, collapse = ", "), "\n")
  cat("Is this intentional?\n")
}
```

## Validation Checklist

Use this checklist for ANY transformation:

### Before

- [ ] Documented pre-transformation shape
- [ ] Saved reproducible sample for comparison
- [ ] Recorded relevant aggregates (sums, counts)
- [ ] Stated what SHOULD change
- [ ] Stated what should NOT change
- [ ] Checked input data types match expectations

### After

- [ ] Verified shape change matches expectations
- [ ] Compared sample records before/after
- [ ] Validated invariants (sums preserved, etc.)
- [ ] Checked for unintended new nulls
- [ ] Checked for unintended duplicates
- [ ] Verified column types in output
- [ ] Documented what was validated and results
