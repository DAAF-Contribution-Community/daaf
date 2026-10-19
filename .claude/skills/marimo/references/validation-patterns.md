# Validation Patterns for Data Analysis

This reference provides patterns for rigorous, step-by-step validation in marimo notebooks for data science workflows.

## Core Principle: Transform-Validate Pairs

**Every transformation cell MUST be followed by a validation cell.** This ensures:
- Immediate detection of unexpected behavior
- Clear audit trail of changes
- Prevents error accumulation
- Enables checkpoint-based recovery

Three marimo rules shape every cell below:

- **A cell displays only its last expression.** A cell that should show something ends with it: every transform cell in Patterns 1-5 ends with its heading and every validation cell with its report, and `mo.stop()` comes before that closing expression (see Final Check Cell). A cell that ends with an assignment, like the transform cells in the Complete Transform-Validate Sequence, displays nothing.
- **A variable may be defined in only one cell.** A name the next cell reads is specific to its step, and a value used only inside its own cell carries a `_` prefix (see Example: Complete Transform-Validate Sequence).
- **`mo.stop()` halts its own cell and every cell that reads a name that cell defines, directly or through other cells; every other cell still runs.** marimo then shows "This cell wasn't run because an ancestor was stopped with `mo.stop`" on the skipped cells. In Patterns 1-5 the gate stops the validation cell, its report, and any cell that reads the validation's metrics (`row_duplication`, `all_high_schools`, ...). It does not stop the next transformation, which reads the transform cell's output (`df_joined`), not anything the validation cell defines. To make a check gate the next step, hand the checked frame on under a new name after the gate and have the next step read that name (Example: Complete Transform-Validate Sequence does this). Since marimo 0.20, a cell that depends on several stopped cells runs only once all of them are unblocked.

## Setup Cell

Every example below assumes one setup cell at the top of the notebook, and no other cell imports these names again. An import defines a name, so a second `import marimo as mo` in another cell is the MB002 multiple-definitions error.

```python
import marimo as mo
import polars as pl
```

## Pattern 1: Basic Transform-Validate Pair

### Cell N: Transform
```python
# Capture pre-state
pre_shape_hs = df.shape
pre_sample_ids_hs = df.select("ncessch").sample(5, seed=42).to_series().to_list()
pre_sample_hs = df.filter(pl.col("ncessch").is_in(pre_sample_ids_hs))

# Execute transformation
df_high_schools = df.filter(pl.col("school_level") == 3)

# The cell's last expression is what it displays
mo.md("## Transform: Filter to high schools")
```

### Cell N+1: Validate (REQUIRED)
````python
# Capture post-state
_post_shape = df_high_schools.shape
_post_sample = df_high_schools.filter(pl.col("ncessch").is_in(pre_sample_ids_hs))

# Calculate metrics
row_retention = (_post_shape[0] / pre_shape_hs[0]) * 100 if pre_shape_hs[0] > 0 else 0
col_retention = (_post_shape[1] / pre_shape_hs[1]) * 100 if pre_shape_hs[1] > 0 else 0

# Check invariants
all_high_schools = (df_high_schools["school_level"] == 3).all()

# Report, heading included
_report = mo.md(f"""
## Validation: Filter to high schools

**Transformation:** Filter to high schools (school_level == 3)

**Pre-state:** {pre_shape_hs[0]:,} rows × {pre_shape_hs[1]} cols  
**Post-state:** {_post_shape[0]:,} rows × {_post_shape[1]} cols  
**Row retention:** {row_retention:.1f}%  
**Column retention:** {col_retention:.1f}%

**Sample comparison:**
```
Before: {pre_sample_hs.shape[0]} records
After: {_post_sample.shape[0]} records
```

**Invariant checks:**
- All rows have school_level == 3: {all_high_schools} {'✅' if all_high_schools else '❌'}

{'✅ **Validation PASSED**' if all_high_schools else '❌ **Validation FAILED**'}
""")

# Gate: on failure, stop dependent cells and show the reason with the report
mo.stop(
    not all_high_schools,
    mo.vstack([
        mo.md("🛑 **STOP:** Validation failed. Non-high-school records found after filter."),
        _report,
    ]),
)

_report
````

The four-backtick fence around this cell (and around Pattern 5's validation cell) keeps the triple-backtick lines inside its f-string from closing the code block early. marimo renders those inner lines as a code block in the report.

## Pattern 2: Multi-Condition Filter Validation

### Cell N: Transform
```python
# Pre-state
pre_shape_ca = df.shape
pre_states_ca = df.select("fips").unique().to_series().to_list()
pre_years_ca = df.select("year").unique().to_series().to_list()

# Transform
df_ca_hs_2020 = df.filter(
    (pl.col("fips") == 6) &  # California
    (pl.col("year") == 2020) &
    (pl.col("school_level") == 3)  # High school
)

mo.md("## Transform: Filter to California public high schools in 2020")
```

### Cell N+1: Validate
```python
# Post-state
post_states = df_ca_hs_2020.select("fips").unique().to_series().to_list()
post_years = df_ca_hs_2020.select("year").unique().to_series().to_list()
post_levels = df_ca_hs_2020.select("school_level").unique().to_series().to_list()

# Invariant checks
correct_state = post_states == [6]
correct_year = post_years == [2020]
correct_level = post_levels == [3]

_all_checks = correct_state and correct_year and correct_level

_report = mo.md(f"""
## Validation: Multi-condition filter

**Transformation:** Filter to CA public high schools in 2020

**Row change:** {pre_shape_ca[0]:,} → {df_ca_hs_2020.shape[0]:,} ({df_ca_hs_2020.shape[0]/pre_shape_ca[0]*100:.1f}% retained)

**Unique values check:**
- States: {pre_states_ca[:5]}... → {post_states} {'✅' if correct_state else '❌'}
- Years: {pre_years_ca} → {post_years} {'✅' if correct_year else '❌'}
- Levels: {post_levels} {'✅' if correct_level else '❌'}

{'✅ **Validation PASSED**' if _all_checks else '❌ **Validation FAILED**'}
""")

mo.stop(
    not _all_checks,
    mo.vstack([
        mo.md("🛑 **STOP:** Filter validation failed. Check unique values below."),
        _report,
    ]),
)

_report
```

## Pattern 3: Join Validation

### Cell N: Transform (Join)
```python
# Pre-state
pre_left_shape = df_schools.shape
pre_right_shape = df_meps.shape
pre_left_ids = set(df_schools["ncessch"].unique().to_list())
pre_right_ids = set(df_meps["ncessch"].unique().to_list())

# Transform
df_joined = df_schools.join(df_meps, on="ncessch", how="left")

mo.md("## Transform: Join schools with MEPS poverty data")
```

### Cell N+1: Validate
```python
# Post-state
_post_shape = df_joined.shape
post_ids = set(df_joined["ncessch"].unique().to_list())

# Join metrics
expected_rows = pre_left_shape[0]  # Left join preserves left rows
actual_rows = _post_shape[0]
row_duplication = actual_rows / expected_rows if expected_rows > 0 else 0

# Check for unexpected duplication
no_unexpected_duplication = row_duplication <= 1.01  # Allow 1% margin

# Check ID preservation
ids_preserved = pre_left_ids == post_ids

# Check for new missing values
pre_null_count = df_schools.null_count().sum_horizontal()[0]
post_null_count = df_joined.select(df_schools.columns).null_count().sum_horizontal()[0]
nulls_preserved = pre_null_count == post_null_count

_report = mo.md(f"""
## Validation: Join

**Transformation:** Left join schools with MEPS data

**Row counts:**
- Left (schools): {pre_left_shape[0]:,}
- Right (MEPS): {pre_right_shape[0]:,}
- Result: {_post_shape[0]:,}
- Duplication ratio: {row_duplication:.2f} {'✅' if no_unexpected_duplication else '❌ WARNING'}

**ID preservation:**
- IDs preserved: {ids_preserved} {'✅' if ids_preserved else '❌'}
- Missing from result: {len(pre_left_ids - post_ids)}
- Added to result: {len(post_ids - pre_left_ids)}

**Null counts (original columns only):**
- Before: {pre_null_count:,}
- After: {post_null_count:,}
- Preserved: {nulls_preserved} {'✅' if nulls_preserved else '❌'}

**Match rate:** {len(pre_left_ids & pre_right_ids) / len(pre_left_ids) * 100:.1f}% of schools matched
""")

mo.stop(
    not (no_unexpected_duplication and ids_preserved),
    mo.vstack([
        mo.md("🛑 **STOP:** Join validation failed. Check for duplicate keys or ID loss."),
        _report,
    ]),
)

_report
```

## Pattern 4: Aggregation Validation

### Cell N: Transform (Aggregation)
```python
# Pre-state
pre_total_enrollment = df.select(pl.col("enrollment").sum())[0, 0]
pre_row_count = df.shape[0]
pre_state_count = df.select("fips").n_unique()

# Transform
df_agg = df.group_by("fips").agg([
    pl.col("enrollment").sum().alias("total_enrollment"),
    pl.len().alias("school_count")
])

mo.md("## Transform: Aggregate enrollment by state")
```

### Cell N+1: Validate
```python
# Post-state
post_total_enrollment = df_agg.select(pl.col("total_enrollment").sum())[0, 0]
post_row_count = df_agg.shape[0]

# Invariant checks
enrollment_preserved = abs(pre_total_enrollment - post_total_enrollment) < 0.01  # Float precision
correct_state_count = post_row_count == pre_state_count
row_count_decreased = post_row_count < pre_row_count

_all_checks = enrollment_preserved and correct_state_count and row_count_decreased

_report = mo.md(f"""
## Validation: Aggregation

**Transformation:** Aggregate by state (fips)

**Row count change:** {pre_row_count:,} → {post_row_count:,} {'✅' if row_count_decreased else '❌'}

**Enrollment totals:**
- Before: {pre_total_enrollment:,.0f}
- After: {post_total_enrollment:,.0f}
- Difference: {abs(pre_total_enrollment - post_total_enrollment):,.0f}
- Preserved: {enrollment_preserved} {'✅' if enrollment_preserved else '❌'}

**State count:**
- Expected: {pre_state_count}
- Actual: {post_row_count}
- Match: {correct_state_count} {'✅' if correct_state_count else '❌'}

{'✅ **Validation PASSED**' if _all_checks else '❌ **Validation FAILED**'}
""")

mo.stop(
    not _all_checks,
    mo.vstack([
        mo.md("🛑 **STOP:** Aggregation validation failed. Check invariants below."),
        _report,
    ]),
)

_report
```

## Pattern 5: Column Transformation Validation

### Cell N: Transform (Create derived column)
```python
# Pre-state
pre_shape_ratio = df.shape
pre_sample_ids_ratio = df.select("ncessch").sample(5, seed=42).to_series().to_list()
pre_sample_ratio = df.filter(pl.col("ncessch").is_in(pre_sample_ids_ratio)).select(["ncessch", "students", "teachers"])

# Transform
df_with_ratio = df.with_columns(
    (pl.col("students") / pl.col("teachers")).alias("student_teacher_ratio")
)

mo.md("## Transform: Calculate students per teacher ratio")
```

### Cell N+1: Validate
````python
# Post-state
_post_sample = df_with_ratio.filter(pl.col("ncessch").is_in(pre_sample_ids_ratio)).select(["ncessch", "students", "teachers", "student_teacher_ratio"])

# Invariant checks
shape_preserved = df_with_ratio.shape[0] == pre_shape_ratio[0]
col_count_increased = df_with_ratio.shape[1] == pre_shape_ratio[1] + 1
new_col_exists = "student_teacher_ratio" in df_with_ratio.columns

# Manual calculation check on sample
manual_check = (
    _post_sample.with_columns(
        (pl.col("students") / pl.col("teachers")).alias("manual_ratio")
    )
    .select(
        ((pl.col("student_teacher_ratio") - pl.col("manual_ratio")).abs() < 0.01).all()
    )[0, 0]
)

_all_checks = shape_preserved and col_count_increased and new_col_exists and manual_check

_report = mo.md(f"""
## Validation: Derived column

**Transformation:** Add student_teacher_ratio column

**Shape changes:**
- Rows: {pre_shape_ratio[0]:,} → {df_with_ratio.shape[0]:,} {'✅' if shape_preserved else '❌'}
- Columns: {pre_shape_ratio[1]} → {df_with_ratio.shape[1]} {'✅' if col_count_increased else '❌'}

**New column:** {new_col_exists} {'✅' if new_col_exists else '❌'}

**Sample verification:**
```
{_post_sample}
```

**Manual calculation check:** {manual_check} {'✅' if manual_check else '❌'}

{'✅ **Validation PASSED**' if _all_checks else '❌ **Validation FAILED**'}
""")

mo.stop(
    not _all_checks,
    mo.vstack([
        mo.md("🛑 **STOP:** Derived column validation failed."),
        _report,
    ]),
)

_report
````

## Pattern 6: Validation State Tracker

For complex notebooks with many transformations, track validation state:

### Cell: Initialize Tracker
```python
# Track which validations have passed (mo comes from the Setup Cell)
validation_log = {
    "fetch_validated": False,
    "coded_values_filtered": False,
    "state_filter_validated": False,
    "join_validated": False,
    "aggregation_validated": False
}

mo.md("## Validation Tracker")
```

### After Each Validation Cell
```python
# In each validation cell, after its mo.stop() gate (so only a passing
# check is recorded) and before the closing report expression (so the
# report stays the cell's displayed output), update the tracker
validation_log["state_filter_validated"] = True
```

### Final Check Cell
```python
incomplete = [k for k, v in validation_log.items() if not v]

# marimo displays only a cell's last, unnested expression: a mo.md() left
# inside if/else is never shown (lint rule MR002, branch-expression, flags it
# when the branch ends the cell), and neither is a mo.md() heading placed
# before other statements. So build the whole status, heading included, in
# both branches and end the cell with it.
if incomplete:
    _items = "\n".join(f"- {item}" for item in incomplete)
    status = mo.md(
        "## Overall Validation Status\n\n"
        "🛑 **STOP:** Complete all validations before proceeding to analysis.\n\n"
        f"⚠️ **Incomplete validations:**\n\n{_items}"
    )
else:
    status = mo.md("## Overall Validation Status\n\n✅ **All validations complete**")

# Gate: stop dependent cells and show the incomplete list as the reason
mo.stop(len(incomplete) > 0, status)

status
```

### Put the Final Check Cell Last

The tracker is updated by mutation (`validation_log[...] = True`), and marimo does not track mutations: a cell that only sets a key in `validation_log` does not define `validation_log`, so the Final Check Cell depends on the Initialize Tracker cell alone. marimo runs cells that do not depend on each other in the order they appear in the notebook file. Two consequences follow:

- **Place the Final Check Cell after every validation cell in the file.** Placed above a validation cell, it runs first and lists that validation as incomplete even when the validation passes. On a full run with the final cell last (for example `marimo export html`), the status is correct.
- **In the editor, re-running one validation cell does not re-run the Final Check Cell.** Re-run the final cell yourself (or restart the kernel and run all) before relying on its status.

### Variant: Pass Flags (Status Follows Edits)

When the status has to stay current while you edit, replace the dictionary with one flag per validation cell, defined after that cell's gate:

```python
# In each validation cell, after its mo.stop() gate and before the closing
# report expression. The flag exists only when the check passed.
state_filter_ok = True
```

```python
# Final Check Cell: reading every flag makes this cell run after each
# validation cell, wherever it sits in the file, and re-run with it
_passed = [fetch_ok, state_filter_ok, join_ok]
mo.md(f"## Overall Validation Status\n\n✅ **All {len(_passed)} validations complete**")
```

The trade-off: when any validation stops, this cell is skipped with marimo's "ancestor was stopped" notice instead of listing which validations are incomplete. The stopped validation cell shows the reason itself.

## Anti-Patterns (DO NOT DO)

### ❌ Bad: Multiple Transforms Without Validation
```python
# DON'T DO THIS
df = df.filter(pl.col("state") == "CA")
df = df.with_columns((pl.col("a") * 2).alias("b"))
df = df.join(other_df, on="id")
df = df.group_by("category").agg(pl.sum("value"))
# No validation until the end - errors accumulate!
```

### ❌ Bad: Validation Without mo.stop()
```python
# DON'T DO THIS
mo.md(f"Rows: {df.shape[0]}")  # Just showing the number
# No check if the number is reasonable
# Notebook continues even if something is wrong
```

### ❌ Bad: No Pre-State Capture
```python
# DON'T DO THIS
df_filtered = df.filter(pl.col("year") == 2020)
# Can't compare before/after without pre-state
```

### ✅ Good: One Transform, One Validation
```python
# Transform
pre_shape_year_filter = df.shape
df_year_filtered = df.filter(pl.col("year") == 2020)

# Validate immediately in next cell: gate first, then end with the report
_post_shape = df_year_filtered.shape
mo.stop(_post_shape[0] == 0, mo.md("🛑 **STOP:** Empty result!"))
mo.md(f"Pre: {pre_shape_year_filter}, Post: {_post_shape}")
```

## Integration with Checkpoints

These patterns implement the 4 validation checkpoints from the full pipeline workflow:

| Checkpoint | Pattern | When |
|------------|---------|------|
| **CP1: Post-Fetch** | Basic Transform-Validate | After API data retrieval |
| **CP2: Post-Cleaning** | Multi-Condition Filter | After removing coded values |
| **CP3: Post-Transformation** | Join/Aggregation patterns | After each transform |
| **CP4: Post-Analysis & Visualization** | Validation State Tracker | End of Stage 8 — covers both Stage 8.1 analysis results (CP4.1 outputs valid, CP4.2 critical nulls, CP4.4 correct data source) and Stage 8.2 figures (CP4.3) |

## Best Practices Summary

1. **Always pair:** Transform cell → Validation cell
2. **Always capture:** Pre-state before transforming
3. **Always compare:** Pre vs. post metrics
4. **Always check:** Invariants that should be preserved
5. **Always stop:** Use `mo.stop()` if validation fails, and have the next step read a name the validation cell defines so the stop holds it back
6. **Always report:** Clear markdown with metrics and emoji status
7. **Never batch:** Max 1-2 operations per transform cell

## Example: Complete Transform-Validate Sequence

Each name is defined in exactly one cell. Two cells that define the same variable are a breaking error (lint rule MB002, multiple-definitions): `marimo check` reports it and `marimo run` refuses to start the notebook. When the notebook is executed anyway (for example by `marimo export html`), both defining cells fail with a multiple-definition error and a cell that reads the name fails because the name is not defined, while unrelated cells still run. A pre-state that the next cell reads therefore gets a step-specific name; a value used only inside its own cell can take a `_` prefix, which keeps it local to that cell.

Each validation cell ends its gate by handing the checked frame on under a new name (`df_2020_checked`, `df_ca_checked`), and the next step reads that name. That dependency is what lets `mo.stop()` hold back the next step: a step that read `df_2020` directly would run even when the year check failed.

```python
# Cell 1: Load data
df = pl.read_parquet("data.parquet")
mo.md(f"Loaded {df.shape[0]:,} rows")

# Cell 2: Transform - Filter year
pre_shape_year = df.shape
df_2020 = df.filter(pl.col("year") == 2020)

# Cell 3: Validate - Filter year, then hand the checked frame on
_post_shape = df_2020.shape
year_check = df_2020["year"].unique().to_list() == [2020]
mo.stop(not year_check, "Year validation failed")
df_2020_checked = df_2020
mo.md(f"Rows: {pre_shape_year[0]:,} → {_post_shape[0]:,}, Year correct: {year_check} {'✅' if year_check else '❌'}")

# Cell 4: Transform - Filter state (reads the checked frame, so Cell 3 gates it)
pre_shape_state = df_2020_checked.shape
df_ca = df_2020_checked.filter(pl.col("fips") == 6)

# Cell 5: Validate - Filter state, then hand the checked frame on
_post_shape = df_ca.shape
state_check = df_ca["fips"].unique().to_list() == [6]
mo.stop(not state_check, "State validation failed")
df_ca_checked = df_ca
mo.md(f"Rows: {pre_shape_state[0]:,} → {_post_shape[0]:,}, State correct: {state_check} {'✅' if state_check else '❌'}")

# Cell 6: Analysis (runs only after both validations pass)
result = df_ca_checked.group_by("district").agg(pl.sum("enrollment"))
mo.ui.table(result)
```

Each transformation is discrete and validated, and each validation gates the next step because the next step reads the name the validation hands on.
