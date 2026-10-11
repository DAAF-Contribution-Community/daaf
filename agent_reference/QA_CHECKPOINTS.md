# QA Checkpoints Reference

This document defines the continuous Quality Assurance checkpoint system that runs after each atomic script execution. QA checkpoints complement the existing CP1-CP4 validation system by providing independent secondary verification. Code templates are provided in both Python (Polars) and R (tidyverse/arrow).

---

## Relationship to CP1-CP4

**CP1-CP4** = Primary validation (inline, during execution)
**QA1-QA4b** = Secondary validation (parallel script, after execution)

| Aspect | CP Checkpoints (Primary) | QA Checkpoints (Secondary) |
|--------|--------------------------|---------------------------|
| **Timing** | During script execution | After script completes |
| **Executor** | research-executor (inline) | code-reviewer (parallel script) |
| **Focus** | Operation correctness | Output quality & methodology |
| **Trust Model** | Validates the operation | Validates the validation |
| **Output** | Embedded in script log | Separate QA script + report |
| **Failure Mode** | STOP execution | BLOCKER → revision request |

**Why Both?** CP checkpoints catch operational failures (data access errors, type mismatches). QA checkpoints catch logical errors (wrong approach, inadequate validation, methodology drift).

**Cross-Reference:** See `agent_reference/VALIDATION_CHECKPOINTS.md` for CP1-CP4 code templates and checkpoint classification system.

> **Data Onboarding Equivalents:** Data Onboarding Mode uses parallel naming: **CPP1-CPP4** (primary validation embedded in profiling scripts) and **QAP1-QAP4** (secondary validation by code-reviewer). CPP = "Checkpoint Profiling" and QAP = "QA Profiling." See the QAP section below and `data-onboarding-mode.md` for full definitions.

---

## QA Philosophy

QA checkpoints exist because **primary validation has a structural blind spot**: it can only check what the script author thought to check. The code-reviewer's value comes from checking what the author *didn't* think to check — the orthogonal perspective, the creative edge case, the assumption that seemed too obvious to question.

**The QA mindset is adversarial by design.** A QA checkpoint that merely re-runs the same checks as the original script adds no value. Every QA script should include at least one validation that approaches the data from a different angle than the original script.

**Passing QA means "I tried hard to find problems and couldn't" — not "I ran some checks and they passed."**

The code-reviewer applies five skeptical lenses (Counterfactual, Semantic, Boundary, Absence, Downstream) to every script and hunts for "sleeping bugs" — errors latent in the logic that don't manifest with current data but could with different inputs. See `.claude/agents/code-reviewer.md` § Review Mindset for the full framework.

---

## QA Checkpoint Overview

| Checkpoint | Stage | Focus | Triggers BLOCKER When |
|------------|-------|-------|----------------------|
| **QA1** | After fetch (Stage 5) | Raw data quality | Schema wrong, years missing, unexpected geography |
| **QA2** | After clean (Stage 6) | Cleaning correctness | Coded values remain, wrong suppression calc |
| **QA3** | After transform (Stage 7) | Transform validity | Wrong join type, aggregation error, data loss |
| **QA4a** | After analysis & viz (Stage 8) | Statistical validity | Wrong data source, incorrect aggregations, model non-convergence, scale misrepresentation |
| **QA4b** | After analysis & viz (Stage 8) | Visualization quality | Missing figures, labeling errors, accessibility issues, misleading scales |

---

## QA1: Post-Fetch Quality Assessment

**Applies To:** Stage 5 scripts (data retrieval)

**Purpose:** Verify raw data is correct for the analysis, not just that it was fetched successfully.

### Default Checks

| Check | What It Validates | BLOCKER If |
|-------|-------------------|------------|
| Schema match | Columns match Plan specification | Critical columns missing |
| Year coverage | Years match Plan's year range | Target years absent |
| Geographic scope | Correct entity granularity per domain config (e.g., state/district/school for education) | Wrong geographic unit or entity level |
| ID uniqueness | Primary keys are unique | Duplicate IDs present |
| Dataset completeness | Expected rows and fields present | Partial data fetch |

### QA1 Standard Check Script (cr1)

```python
import polars as pl

# --- Config ---
# INTENT: Declare which QA1 checks legitimately do not apply to this script.
# REASONING: A check that cannot apply must still appear in the log with a stated reason.
#            Silence is indistinguishable from a check that never ran, and that ambiguity
#            is exactly what let evidence-free PASS verdicts into QA logs.
# ASSUMES: Keys are the documented QA1 keys (schema, year_coverage, id_uniqueness — see
#          "Template Applicability Keys" below); each value is a NON-EMPTY reason string.
not_applicable = {}  # e.g. {"year_coverage": "single-year snapshot — Plan specifies no year range"}

# INTENT: Count every outcome so the QA1 verdict is derived from what actually ran.
# REASONING: A seeded `qa1_max_severity = "PASSED"` reports a pass for checks that never
#            executed. Counters cannot: an unrun check is visible in the not-verified tally.
# ASSUMES: Every check below increments exactly one counter and prints exactly one line.
qa1 = {"passed": 0, "warnings": 0, "blockers": 0, "not_verified": 0, "skipped": 0, "info": 0}

print("\n" + "=" * 60)
print("QA1: POST-FETCH QUALITY ASSESSMENT")
print("=" * 60)

# --- Validate: schema ---
# INTENT: Confirm the fetched frame carries the columns the Plan promised.
# REASONING: An absent or empty expected-column list makes "all expected columns present"
#            vacuously true (`[c for c in [] ...]` is empty), so it is reported unverified.
# ASSUMES: plan_spec["critical_columns"], when present, is a subset of expected_columns.
expected_cols = plan_spec.get("expected_columns")
if not_applicable.get("schema"):
    print(f"[SKIPPED] schema: {not_applicable['schema']}")
    qa1["skipped"] += 1
elif "schema" in not_applicable:
    print("[NOT VERIFIED] schema: declared not_applicable with an empty reason string")
    qa1["not_verified"] += 1
elif expected_cols is None or len(expected_cols) == 0:
    print("[NOT VERIFIED] schema: plan_spec['expected_columns'] is missing or empty — nothing to compare against")
    qa1["not_verified"] += 1
else:
    missing = [c for c in expected_cols if c not in df.columns]
    critical_cols = plan_spec.get("critical_columns") or []
    critical_missing = [c for c in missing if c in critical_cols]
    if critical_missing:
        print(f"[BLOCKER] schema: {len(critical_missing)} of {len(expected_cols)} expected columns missing and critical: {critical_missing}")
        qa1["blockers"] += 1
    elif missing:
        print(f"[WARNING] schema: {len(missing)} of {len(expected_cols)} expected columns missing (none critical): {missing}")
        qa1["warnings"] += 1
    else:
        print(f"[PASS] schema: all {len(expected_cols)} expected columns present ({len(df.columns)} columns in df)")
        qa1["passed"] += 1

# --- Validate: year_coverage ---
# INTENT: Confirm every year the Plan asked for is actually present in the data.
# REASONING: Both inputs can be absent — the year column may not exist in the frame and
#            plan_spec["year_range"] may be unset. Either absence makes the coverage claim
#            untestable, so it is reported unverified rather than defaulted to present.
# ASSUMES: year values are directly comparable (both ints or both strings) after unique().
year_col = plan_spec.get("year_col", "year")  # From Plan Domain Configuration
years_expected = plan_spec.get("year_range")
if not_applicable.get("year_coverage"):
    print(f"[SKIPPED] year_coverage: {not_applicable['year_coverage']}")
    qa1["skipped"] += 1
elif "year_coverage" in not_applicable:
    print("[NOT VERIFIED] year_coverage: declared not_applicable with an empty reason string")
    qa1["not_verified"] += 1
elif year_col is None or year_col not in df.columns:
    print(f"[NOT VERIFIED] year_coverage: year column '{year_col}' is not in df — coverage untestable")
    qa1["not_verified"] += 1
elif years_expected is None or len(years_expected) == 0:
    print("[NOT VERIFIED] year_coverage: plan_spec['year_range'] is missing or empty — nothing to compare against")
    qa1["not_verified"] += 1
else:
    years_present = set(df[year_col].drop_nulls().unique().to_list())
    missing_years = sorted(set(years_expected) - years_present)
    if len(missing_years) > len(years_expected) // 2:
        print(f"[BLOCKER] year_coverage: {len(missing_years)} of {len(years_expected)} expected years absent: {missing_years}")
        qa1["blockers"] += 1
    elif missing_years:
        print(f"[WARNING] year_coverage: {len(missing_years)} of {len(years_expected)} expected years absent: {missing_years}")
        qa1["warnings"] += 1
    else:
        print(f"[PASS] year_coverage: all {len(years_expected)} expected years present in '{year_col}' ({sorted(years_present)})")
        qa1["passed"] += 1

# --- Validate: id_uniqueness ---
# INTENT: Confirm the Plan's primary key actually identifies rows uniquely.
# REASONING: An unset primary_key, or one absent from the frame, means no key was tested —
#            reporting that as "all IDs unique" asserts a property nothing established.
# ASSUMES: A composite key would be declared as a list; this template handles a single column.
id_col = plan_spec.get("primary_key")
if not_applicable.get("id_uniqueness"):
    print(f"[SKIPPED] id_uniqueness: {not_applicable['id_uniqueness']}")
    qa1["skipped"] += 1
elif "id_uniqueness" in not_applicable:
    print("[NOT VERIFIED] id_uniqueness: declared not_applicable with an empty reason string")
    qa1["not_verified"] += 1
elif id_col is None:
    print("[NOT VERIFIED] id_uniqueness: plan_spec['primary_key'] is not set — no key to test")
    qa1["not_verified"] += 1
elif id_col not in df.columns:
    print(f"[BLOCKER] id_uniqueness: declared primary key '{id_col}' is absent from df ({len(df.columns)} columns)")
    qa1["blockers"] += 1
else:
    n_distinct = df[id_col].n_unique()
    n_dupe_keys = len(df.group_by(id_col).len().filter(pl.col("len") > 1))
    if n_dupe_keys > 0:
        print(f"[BLOCKER] id_uniqueness: '{id_col}' has {n_dupe_keys} duplicated key values across {len(df)} rows ({n_distinct} distinct)")
        qa1["blockers"] += 1
    else:
        print(f"[PASS] id_uniqueness: '{id_col}' has {n_distinct} distinct values over {len(df)} rows (0 duplicates)")
        qa1["passed"] += 1

# --- Data Profiling (for qa2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)
print(f"\nFirst 10 rows:\n{df.head(10)}")
print(f"\nDescriptive statistics:\n{df.describe()}")

# --- Verdict ---
# INTENT: Derive the QA1 verdict from the counters rather than asserting it.
# REASONING: NOT VERIFIED forces at least WARNING because a QA level with unverified
#            checks has not done its job; zero substantive checks is also a WARNING, not
#            a pass, so an all-skipped run can never read as clean.
# ASSUMES: `skipped` and `info` are reported but do not drive the verdict.
print(f"\nChecks: {qa1['passed']} passed, {qa1['warnings']} warnings, {qa1['blockers']} blockers, "
      f"{qa1['not_verified']} not verified, {qa1['skipped']} skipped, {qa1['info']} info")
if qa1["blockers"] > 0:
    qa1_result = "BLOCKER"
elif qa1["warnings"] > 0 or qa1["not_verified"] > 0:
    qa1_result = "WARNING"
elif qa1["passed"] == 0:
    qa1_result = "WARNING"  # nothing was actually verified
else:
    qa1_result = "PASSED"
print(f"QA1 RESULT: {qa1_result}")
print("=" * 60)
```

### QA1 Standard Check Script — R (cr1)

```r
library(dplyr)
library(arrow)

# --- Config ---
# INTENT: Declare which QA1 checks legitimately do not apply to this script.
# REASONING: A skipped check must be visible in the log with its reason; silence reads
#            identically to a check that ran and passed, which is the defect being fixed.
# ASSUMES: Names are the documented QA1 keys; every element is a non-empty reason string.
#          Indexed with [[ ]] throughout — `$` partial-matches and binds the wrong key.
not_applicable <- list()  # e.g. list(year_coverage = "single-year snapshot — no year range in Plan")

# INTENT: Count every outcome so the QA1 verdict is derived from what actually ran.
# ASSUMES: Every check below increments exactly one counter and emits exactly one line.
qa1 <- c(passed = 0L, warnings = 0L, blockers = 0L, not_verified = 0L, skipped = 0L, info = 0L)

cat("\n")
cat(strrep("=", 60), "\n")
cat("QA1: POST-FETCH QUALITY ASSESSMENT\n")
cat(strrep("=", 60), "\n")

# --- Validate: schema ---
# INTENT: Confirm the fetched frame carries the columns the Plan promised.
# REASONING: setdiff(NULL, names(df)) is length 0, so an unset expected-column list would
#            otherwise print "[PASS] All 0 expected columns present" — a vacuous claim.
# ASSUMES: plan_spec[["critical_columns"]], when present, is a subset of expected_columns.
expected_cols <- plan_spec[["expected_columns"]]
na_reason <- if ("schema" %in% names(not_applicable)) not_applicable[["schema"]] else NULL
if (!is.null(na_reason) && nzchar(na_reason)) {
  cat(sprintf("[SKIPPED] schema: %s\n", na_reason))
  qa1["skipped"] <- qa1["skipped"] + 1L
} else if ("schema" %in% names(not_applicable)) {
  cat("[NOT VERIFIED] schema: declared not_applicable with an empty reason string\n")
  qa1["not_verified"] <- qa1["not_verified"] + 1L
} else if (is.null(expected_cols) || length(expected_cols) == 0) {
  cat("[NOT VERIFIED] schema: plan_spec[['expected_columns']] is missing or empty - nothing to compare against\n")
  qa1["not_verified"] <- qa1["not_verified"] + 1L
} else {
  missing <- setdiff(expected_cols, names(df))
  critical_cols <- plan_spec[["critical_columns"]]
  if (is.null(critical_cols)) critical_cols <- character(0)
  critical_missing <- intersect(missing, critical_cols)
  if (length(critical_missing) > 0) {
    cat(sprintf("[BLOCKER] schema: %d of %d expected columns missing and critical: %s\n",
                length(critical_missing), length(expected_cols), paste(critical_missing, collapse = ", ")))
    qa1["blockers"] <- qa1["blockers"] + 1L
  } else if (length(missing) > 0) {
    cat(sprintf("[WARNING] schema: %d of %d expected columns missing (none critical): %s\n",
                length(missing), length(expected_cols), paste(missing, collapse = ", ")))
    qa1["warnings"] <- qa1["warnings"] + 1L
  } else {
    cat(sprintf("[PASS] schema: all %d expected columns present (%d columns in df)\n",
                length(expected_cols), length(names(df))))
    qa1["passed"] <- qa1["passed"] + 1L
  }
}

# --- Validate: year_coverage ---
# INTENT: Confirm every year the Plan asked for is present in the data.
# REASONING: setdiff(NULL, years_present) is also length 0, so a missing year_range would
#            otherwise pass. Both the column and the expected list must exist to test this.
# ASSUMES: year values in df and in the Plan are the same type (both numeric or both chr).
year_col <- plan_spec[["year_col"]]
if (is.null(year_col)) year_col <- "year"  # From Plan Domain Configuration
years_expected <- plan_spec[["year_range"]]
na_reason <- if ("year_coverage" %in% names(not_applicable)) not_applicable[["year_coverage"]] else NULL
if (!is.null(na_reason) && nzchar(na_reason)) {
  cat(sprintf("[SKIPPED] year_coverage: %s\n", na_reason))
  qa1["skipped"] <- qa1["skipped"] + 1L
} else if ("year_coverage" %in% names(not_applicable)) {
  cat("[NOT VERIFIED] year_coverage: declared not_applicable with an empty reason string\n")
  qa1["not_verified"] <- qa1["not_verified"] + 1L
} else if (!year_col %in% names(df)) {
  cat(sprintf("[NOT VERIFIED] year_coverage: year column '%s' is not in df - coverage untestable\n", year_col))
  qa1["not_verified"] <- qa1["not_verified"] + 1L
} else if (is.null(years_expected) || length(years_expected) == 0) {
  cat("[NOT VERIFIED] year_coverage: plan_spec[['year_range']] is missing or empty - nothing to compare against\n")
  qa1["not_verified"] <- qa1["not_verified"] + 1L
} else {
  years_present <- unique(df[[year_col]][!is.na(df[[year_col]])])
  missing_years <- setdiff(years_expected, years_present)
  if (length(missing_years) > length(years_expected) %/% 2) {
    cat(sprintf("[BLOCKER] year_coverage: %d of %d expected years absent: %s\n",
                length(missing_years), length(years_expected), paste(sort(missing_years), collapse = ", ")))
    qa1["blockers"] <- qa1["blockers"] + 1L
  } else if (length(missing_years) > 0) {
    cat(sprintf("[WARNING] year_coverage: %d of %d expected years absent: %s\n",
                length(missing_years), length(years_expected), paste(sort(missing_years), collapse = ", ")))
    qa1["warnings"] <- qa1["warnings"] + 1L
  } else {
    cat(sprintf("[PASS] year_coverage: all %d expected years present in '%s' (%s)\n",
                length(years_expected), year_col, paste(sort(years_present), collapse = ", ")))
    qa1["passed"] <- qa1["passed"] + 1L
  }
}

# --- Validate: id_uniqueness ---
# INTENT: Confirm the Plan's primary key actually identifies rows uniquely.
# REASONING: An unset key means nothing was tested (NOT VERIFIED); a declared key absent
#            from the frame is a real contradiction between Plan and data (BLOCKER).
# ASSUMES: A single-column key; composite keys need the paste()-based variant.
id_col <- plan_spec[["primary_key"]]
na_reason <- if ("id_uniqueness" %in% names(not_applicable)) not_applicable[["id_uniqueness"]] else NULL
if (!is.null(na_reason) && nzchar(na_reason)) {
  cat(sprintf("[SKIPPED] id_uniqueness: %s\n", na_reason))
  qa1["skipped"] <- qa1["skipped"] + 1L
} else if ("id_uniqueness" %in% names(not_applicable)) {
  cat("[NOT VERIFIED] id_uniqueness: declared not_applicable with an empty reason string\n")
  qa1["not_verified"] <- qa1["not_verified"] + 1L
} else if (is.null(id_col)) {
  cat("[NOT VERIFIED] id_uniqueness: plan_spec[['primary_key']] is not set - no key to test\n")
  qa1["not_verified"] <- qa1["not_verified"] + 1L
} else if (!id_col %in% names(df)) {
  cat(sprintf("[BLOCKER] id_uniqueness: declared primary key '%s' is absent from df (%d columns)\n",
              id_col, length(names(df))))
  qa1["blockers"] <- qa1["blockers"] + 1L
} else {
  n_distinct_ids <- length(unique(df[[id_col]]))
  n_dupe_keys <- sum(table(df[[id_col]]) > 1)
  if (n_dupe_keys > 0) {
    cat(sprintf("[BLOCKER] id_uniqueness: '%s' has %d duplicated key values across %d rows (%d distinct)\n",
                id_col, n_dupe_keys, nrow(df), n_distinct_ids))
    qa1["blockers"] <- qa1["blockers"] + 1L
  } else {
    cat(sprintf("[PASS] id_uniqueness: '%s' has %d distinct values over %d rows (0 duplicates)\n",
                id_col, n_distinct_ids, nrow(df)))
    qa1["passed"] <- qa1["passed"] + 1L
  }
}

# --- Data Profiling (for qa2+ decision) ---
cat("\n")
cat(strrep("=", 60), "\n")
cat("DATA PROFILING\n")
cat(strrep("=", 60), "\n")
cat("\nFirst 10 rows:\n")
print(head(df, 10))
cat("\nDescriptive statistics:\n")
print(summary(df))

# --- Verdict ---
# INTENT: Derive the QA1 verdict from the counters rather than asserting it.
# REASONING: NOT VERIFIED forces at least WARNING; zero substantive checks is a WARNING,
#            so an all-skipped or all-unverified run can never read as clean.
# ASSUMES: skipped and info are reported but do not drive the verdict.
cat(sprintf("\nChecks: %d passed, %d warnings, %d blockers, %d not verified, %d skipped, %d info\n",
            qa1[["passed"]], qa1[["warnings"]], qa1[["blockers"]],
            qa1[["not_verified"]], qa1[["skipped"]], qa1[["info"]]))
qa1_result <- if (qa1[["blockers"]] > 0) {
  "BLOCKER"
} else if (qa1[["warnings"]] > 0 || qa1[["not_verified"]] > 0) {
  "WARNING"
} else if (qa1[["passed"]] == 0) {
  "WARNING"  # nothing was actually verified
} else {
  "PASSED"
}
cat(sprintf("QA1 RESULT: %s\n", qa1_result))
cat(strrep("=", 60), "\n")
```

### QA1 Discretionary Checks

Add when appropriate:

| Check | When to Add | What It Validates |
|-------|-------------|-------------------|
| Value range | Numeric analysis | Values within expected bounds |
| Category coverage | Categorical analysis | All expected categories present |
| Cross-source consistency | Multi-source fetch | Same entities across sources |
| **Concrete trace** | **Always (at minimum 5)** — see `.claude/agents/code-reviewer.md` § Five Lenses of Skeptical Review | **Pick one entity (e.g., a specific school or state) and verify its record looks plausible** |

**Creative check prompt:** Before writing your QA1 script, ask: *"If the data access mirror returned data for the wrong geography or wrong year range, how would I detect that from the data alone?"* Design at least one check to answer that question.

### QA1 Iterative Investigation Triggers

Observations from qa1 that should trigger qa2+ investigation:

| qa1 Observation | Suggested qa2 Investigation |
|-----------------|---------------------------|
| Unexpected geography in data (states not in Plan scope) | Filter analysis: are extra states contaminating results? |
| Year distribution uneven (some years have 10x more records) | Investigate: data access issue or genuine enrollment change? |
| ID column has unexpected format variations | Trace: will downstream joins fail on format mismatch? |
| Row count far from Plan estimate (even if within tolerance) | Profile: what population is unexpectedly included/excluded? |

---

## QA2: Post-Clean Quality Assessment

**Applies To:** Stage 6 scripts (context application)

**Purpose:** Verify cleaning was done correctly, not just that cleaning operations ran.

### Default Checks

| Check | What It Validates | BLOCKER If |
|-------|-------------------|------------|
| Coded values gone | Domain-specific coded values filtered properly (e.g., -1, -2, -3 for education) | Coded values remain in analysis columns |
| Suppression calc | Rate calculated correctly | Suppression rate miscalculated |
| Filter correctness | Correct rows removed | Wrong filter criteria applied |
| Type consistency | Data types are appropriate | Analysis columns have wrong types |

### QA2 Standard Check Script (cr1)

```python
import polars as pl

# --- Config ---
# INTENT: Declare which QA2 checks legitimately do not apply to this script.
# ASSUMES: Keys are the documented QA2 keys (coded_values, suppression, column_types);
#          each value is a NON-EMPTY reason string.
not_applicable = {}  # e.g. {"suppression": "CCD directory file carries no suppression code"}

# INTENT: Count every outcome so the QA2 verdict is derived from what actually ran.
qa2 = {"passed": 0, "warnings": 0, "blockers": 0, "not_verified": 0, "skipped": 0, "info": 0}

print("\n" + "=" * 60)
print("QA2: POST-CLEAN QUALITY ASSESSMENT")
print("=" * 60)

# --- Validate: coded_values ---
# INTENT: Confirm domain coded-missing sentinels were removed from the analysis columns.
# REASONING: `all()` over an empty generator is True, so an empty column list or an empty
#            coded-value vocabulary would print "no coded values remain" having inspected
#            nothing. Both emptiness cases are reported as unverified instead.
# ASSUMES: coded_missing_values maps to the Plan's "Coded Missing Values" Domain
#          Configuration field (education default: [-1, -2, -3]).
print("\nCoded Values Check:")
numeric_columns = plan_spec.get("numeric_columns")
coded_missing_values = plan_spec.get("coded_missing_values", [-1, -2, -3])
if not_applicable.get("coded_values"):
    print(f"[SKIPPED] coded_values: {not_applicable['coded_values']}")
    qa2["skipped"] += 1
elif "coded_values" in not_applicable:
    print("[NOT VERIFIED] coded_values: declared not_applicable with an empty reason string")
    qa2["not_verified"] += 1
elif numeric_columns is None or len(numeric_columns) == 0:
    print("[NOT VERIFIED] coded_values: plan_spec['numeric_columns'] is missing or empty — no columns to scan")
    qa2["not_verified"] += 1
elif coded_missing_values is None or len(coded_missing_values) == 0:
    print("[NOT VERIFIED] coded_values: plan_spec['coded_missing_values'] is empty — no sentinel vocabulary to scan for")
    qa2["not_verified"] += 1
else:
    for col in numeric_columns:
        if col not in df.columns:
            print(f"[BLOCKER] coded_values '{col}': column named in plan_spec['numeric_columns'] is absent from df")
            qa2["blockers"] += 1
            continue
        hits = {code: int((df[col] == code).sum()) for code in coded_missing_values}
        remaining = {code: n for code, n in hits.items() if n > 0}
        if remaining:
            print(f"[BLOCKER] coded_values '{col}': {sum(remaining.values())} rows still carry sentinels {remaining} (of {len(df)} rows)")
            qa2["blockers"] += 1
        else:
            print(f"[PASS] coded_values '{col}': 0 of {len(df)} rows match any of {list(coded_missing_values)}")
            qa2["passed"] += 1

# --- Validate: suppression ---
# INTENT: Recompute the COLUMN-level suppression rate from the raw frame and compare it
#         against the rate the Plan reports.
# REASONING: The prior version divided rows-dropped by rows-raw — a frame-level attrition
#            figure printed under a per-column label, identical for every column and 0
#            whenever suppression is handled by nulling in place (the DAAF-normal path).
#            The numerator here is the count of the domain suppression sentinel in
#            raw_df[col]; the denominator is that column's row count. `0.0` is a valid
#            reported rate, so presence is tested with `is None`, never truthiness.
# ASSUMES: Suppression is encoded as plan_spec["suppression_code"] in the RAW frame and
#          nulled (not row-dropped) during cleaning; if your domain drops rows instead,
#          change the numerator and say so in the printed line.
print("\nSuppression Rate Verification:")
suppression_columns = plan_spec.get("suppression_columns")
suppression_code = plan_spec.get("suppression_code")
reported_rates = plan_spec.get("reported_suppression_rate") or {}
if not_applicable.get("suppression"):
    print(f"[SKIPPED] suppression: {not_applicable['suppression']}")
    qa2["skipped"] += 1
elif "suppression" in not_applicable:
    print("[NOT VERIFIED] suppression: declared not_applicable with an empty reason string")
    qa2["not_verified"] += 1
elif suppression_columns is None or len(suppression_columns) == 0:
    print("[NOT VERIFIED] suppression: plan_spec['suppression_columns'] is missing or empty — no columns to recompute")
    qa2["not_verified"] += 1
elif suppression_code is None:
    print("[NOT VERIFIED] suppression: plan_spec['suppression_code'] is not set — the rate cannot be recomputed (declare not_applicable if this domain has no suppression code)")
    qa2["not_verified"] += 1
else:
    for col in suppression_columns:
        if col not in raw_df.columns:
            print(f"[BLOCKER] suppression '{col}': column is absent from raw_df — rate not recomputable")
            qa2["blockers"] += 1
            continue
        denom = raw_df.height
        if denom == 0:
            print(f"[NOT VERIFIED] suppression '{col}': raw_df is empty (0 rows) — rate undefined")
            qa2["not_verified"] += 1
            continue
        raw_supp = int((raw_df[col] == suppression_code).sum())
        actual_rate = raw_supp / denom
        reported_rate = reported_rates.get(col)
        if reported_rate is None:
            print(f"[NOT VERIFIED] suppression '{col}': plan_spec['reported_suppression_rate'] has no entry — recomputed {actual_rate:.1%} ({raw_supp}/{denom} == {suppression_code}) with nothing to compare against")
            qa2["not_verified"] += 1
        elif abs(actual_rate - reported_rate) > 0.05:
            print(f"[BLOCKER] suppression '{col}': reported {reported_rate:.1%} != recomputed {actual_rate:.1%} ({raw_supp}/{denom} == {suppression_code})")
            qa2["blockers"] += 1
        else:
            print(f"[PASS] suppression '{col}': reported {reported_rate:.1%} == recomputed {actual_rate:.1%} (n={raw_supp}/{denom} == {suppression_code})")
            qa2["passed"] += 1

# --- Validate: column_types ---
# INTENT: Confirm each column the Plan typed actually carries that dtype after cleaning.
# REASONING: A column named in the type spec but absent from the frame produced no line at
#            all before — the Plan and the data disagree, which is a BLOCKER, not silence.
# ASSUMES: expected_type strings match Polars' str(dtype) spelling (e.g. "Int64", "Float64").
print("\nType Validation:")
type_spec = plan_spec.get("column_types")
if not_applicable.get("column_types"):
    print(f"[SKIPPED] column_types: {not_applicable['column_types']}")
    qa2["skipped"] += 1
elif "column_types" in not_applicable:
    print("[NOT VERIFIED] column_types: declared not_applicable with an empty reason string")
    qa2["not_verified"] += 1
elif type_spec is None or len(type_spec) == 0:
    print("[NOT VERIFIED] column_types: plan_spec['column_types'] is missing or empty — no types declared")
    qa2["not_verified"] += 1
else:
    for col, expected_type in type_spec.items():
        if col not in df.columns:
            print(f"[BLOCKER] column_types '{col}': column named in plan_spec['column_types'] is absent from df")
            qa2["blockers"] += 1
        elif str(df[col].dtype) != expected_type:
            print(f"[WARNING] column_types '{col}': expected {expected_type}, observed {df[col].dtype}")
            qa2["warnings"] += 1
        else:
            print(f"[PASS] column_types '{col}': observed dtype {df[col].dtype} == expected {expected_type}")
            qa2["passed"] += 1

# --- Data Profiling (for qa2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)
print(f"\nFirst 10 rows:\n{df.head(10)}")
print(f"\nDescriptive statistics:\n{df.describe()}")

# --- Verdict ---
# INTENT: Derive the QA2 verdict from the counters rather than asserting it.
print(f"\nChecks: {qa2['passed']} passed, {qa2['warnings']} warnings, {qa2['blockers']} blockers, "
      f"{qa2['not_verified']} not verified, {qa2['skipped']} skipped, {qa2['info']} info")
if qa2["blockers"] > 0:
    qa2_result = "BLOCKER"
elif qa2["warnings"] > 0 or qa2["not_verified"] > 0:
    qa2_result = "WARNING"
elif qa2["passed"] == 0:
    qa2_result = "WARNING"  # nothing was actually verified
else:
    qa2_result = "PASSED"
print(f"QA2 RESULT: {qa2_result}")
print("=" * 60)
```

### QA2 Standard Check Script — R (cr1)

```r
library(dplyr)
library(arrow)

# --- Config ---
# INTENT: Declare which QA2 checks legitimately do not apply to this script.
# ASSUMES: Names are the documented QA2 keys; each element is a non-empty reason string.
not_applicable <- list()  # e.g. list(suppression = "CCD directory file carries no suppression code")

# INTENT: Count every outcome so the QA2 verdict is derived from what actually ran.
qa2 <- c(passed = 0L, warnings = 0L, blockers = 0L, not_verified = 0L, skipped = 0L, info = 0L)

cat("\n")
cat(strrep("=", 60), "\n")
cat("QA2: POST-CLEAN QUALITY ASSESSMENT\n")
cat(strrep("=", 60), "\n")

# --- Validate: coded_values ---
# INTENT: Confirm domain coded-missing sentinels were removed from the analysis columns.
# REASONING: all(logical(0)) is TRUE, so an empty column list or empty sentinel vocabulary
#            would print "no coded values remain" having inspected nothing. length() is
#            guarded before any sum() so an empty vocabulary cannot masquerade as a clean run.
# ASSUMES: coded_missing_values maps to the Plan's "Coded Missing Values" Domain
#          Configuration field (education default: c(-1, -2, -3)).
cat("\nCoded Values Check:\n")
numeric_columns <- plan_spec[["numeric_columns"]]
coded_missing_values <- plan_spec[["coded_missing_values"]]
if (is.null(coded_missing_values)) coded_missing_values <- c(-1, -2, -3)
na_reason <- if ("coded_values" %in% names(not_applicable)) not_applicable[["coded_values"]] else NULL
if (!is.null(na_reason) && nzchar(na_reason)) {
  cat(sprintf("[SKIPPED] coded_values: %s\n", na_reason))
  qa2["skipped"] <- qa2["skipped"] + 1L
} else if ("coded_values" %in% names(not_applicable)) {
  cat("[NOT VERIFIED] coded_values: declared not_applicable with an empty reason string\n")
  qa2["not_verified"] <- qa2["not_verified"] + 1L
} else if (is.null(numeric_columns) || length(numeric_columns) == 0) {
  cat("[NOT VERIFIED] coded_values: plan_spec[['numeric_columns']] is missing or empty - no columns to scan\n")
  qa2["not_verified"] <- qa2["not_verified"] + 1L
} else if (length(coded_missing_values) == 0) {
  cat("[NOT VERIFIED] coded_values: plan_spec[['coded_missing_values']] is empty - no sentinel vocabulary to scan for\n")
  qa2["not_verified"] <- qa2["not_verified"] + 1L
} else {
  for (col in numeric_columns) {
    if (!col %in% names(df)) {
      cat(sprintf("[BLOCKER] coded_values '%s': column named in plan_spec[['numeric_columns']] is absent from df\n", col))
      qa2["blockers"] <- qa2["blockers"] + 1L
      next
    }
    hits <- sapply(coded_missing_values, function(code) sum(df[[col]] == code, na.rm = TRUE))
    if (sum(hits) > 0) {
      present <- coded_missing_values[hits > 0]
      cat(sprintf("[BLOCKER] coded_values '%s': %d rows still carry sentinels %s (of %d rows)\n",
                  col, sum(hits), paste(present, collapse = ", "), nrow(df)))
      qa2["blockers"] <- qa2["blockers"] + 1L
    } else {
      cat(sprintf("[PASS] coded_values '%s': 0 of %d rows match any of %s\n",
                  col, nrow(df), paste(coded_missing_values, collapse = ", ")))
      qa2["passed"] <- qa2["passed"] + 1L
    }
  }
}

# --- Validate: suppression ---
# INTENT: Recompute the COLUMN-level suppression rate from raw_df and compare it against
#         the rate the Plan reports.
# REASONING: The prior version divided rows-dropped by rows-raw - a frame-level attrition
#            figure printed under a per-column label, identical for every column and 0
#            whenever suppression is handled by nulling in place. The numerator here counts
#            the domain sentinel in raw_df[[col]]; the denominator is that column's length.
#            is.null() (not truthiness) admits a legitimate reported rate of 0.
# ASSUMES: Suppression is encoded as plan_spec[["suppression_code"]] in the RAW frame and
#          nulled (not row-dropped) during cleaning; a row-dropping domain needs a different
#          numerator, and the printed line must say so.
cat("\nSuppression Rate Verification:\n")
suppression_columns <- plan_spec[["suppression_columns"]]
suppression_code <- plan_spec[["suppression_code"]]
reported_rates <- plan_spec[["reported_suppression_rate"]]
if (is.null(reported_rates)) reported_rates <- list()
na_reason <- if ("suppression" %in% names(not_applicable)) not_applicable[["suppression"]] else NULL
if (!is.null(na_reason) && nzchar(na_reason)) {
  cat(sprintf("[SKIPPED] suppression: %s\n", na_reason))
  qa2["skipped"] <- qa2["skipped"] + 1L
} else if ("suppression" %in% names(not_applicable)) {
  cat("[NOT VERIFIED] suppression: declared not_applicable with an empty reason string\n")
  qa2["not_verified"] <- qa2["not_verified"] + 1L
} else if (is.null(suppression_columns) || length(suppression_columns) == 0) {
  cat("[NOT VERIFIED] suppression: plan_spec[['suppression_columns']] is missing or empty - no columns to recompute\n")
  qa2["not_verified"] <- qa2["not_verified"] + 1L
} else if (is.null(suppression_code)) {
  cat("[NOT VERIFIED] suppression: plan_spec[['suppression_code']] is not set - rate not recomputable (declare not_applicable if this domain has no suppression code)\n")
  qa2["not_verified"] <- qa2["not_verified"] + 1L
} else {
  for (col in suppression_columns) {
    if (!col %in% names(raw_df)) {
      cat(sprintf("[BLOCKER] suppression '%s': column is absent from raw_df - rate not recomputable\n", col))
      qa2["blockers"] <- qa2["blockers"] + 1L
      next
    }
    denom <- length(raw_df[[col]])
    if (denom == 0) {
      cat(sprintf("[NOT VERIFIED] suppression '%s': raw_df is empty (0 rows) - rate undefined\n", col))
      qa2["not_verified"] <- qa2["not_verified"] + 1L
      next
    }
    raw_supp <- sum(raw_df[[col]] == suppression_code, na.rm = TRUE)
    actual_rate <- raw_supp / denom
    reported_rate <- reported_rates[[col]]
    if (is.null(reported_rate) || (length(reported_rate) == 1 && is.na(reported_rate))) {
      cat(sprintf("[NOT VERIFIED] suppression '%s': no reported_suppression_rate entry - recomputed %.1f%% (%d/%d == %s) with nothing to compare against\n",
                  col, actual_rate * 100, raw_supp, denom, as.character(suppression_code)))
      qa2["not_verified"] <- qa2["not_verified"] + 1L
    } else if (abs(actual_rate - reported_rate) > 0.05) {
      cat(sprintf("[BLOCKER] suppression '%s': reported %.1f%% != recomputed %.1f%% (%d/%d == %s)\n",
                  col, reported_rate * 100, actual_rate * 100, raw_supp, denom, as.character(suppression_code)))
      qa2["blockers"] <- qa2["blockers"] + 1L
    } else {
      cat(sprintf("[PASS] suppression '%s': reported %.1f%% == recomputed %.1f%% (n=%d/%d == %s)\n",
                  col, reported_rate * 100, actual_rate * 100, raw_supp, denom, as.character(suppression_code)))
      qa2["passed"] <- qa2["passed"] + 1L
    }
  }
}

# --- Validate: column_types ---
# INTENT: Confirm each column the Plan typed carries that class after cleaning.
# REASONING: A column named in the type spec but absent from the frame produced no line at
#            all before - the Plan and the data disagree, which is a BLOCKER, not silence.
# ASSUMES: expected_type strings match class(x)[1] spelling (e.g. "numeric", "character").
cat("\nType Validation:\n")
type_spec <- plan_spec[["column_types"]]
na_reason <- if ("column_types" %in% names(not_applicable)) not_applicable[["column_types"]] else NULL
if (!is.null(na_reason) && nzchar(na_reason)) {
  cat(sprintf("[SKIPPED] column_types: %s\n", na_reason))
  qa2["skipped"] <- qa2["skipped"] + 1L
} else if ("column_types" %in% names(not_applicable)) {
  cat("[NOT VERIFIED] column_types: declared not_applicable with an empty reason string\n")
  qa2["not_verified"] <- qa2["not_verified"] + 1L
} else if (is.null(type_spec) || length(type_spec) == 0) {
  cat("[NOT VERIFIED] column_types: plan_spec[['column_types']] is missing or empty - no types declared\n")
  qa2["not_verified"] <- qa2["not_verified"] + 1L
} else {
  for (col in names(type_spec)) {
    if (!col %in% names(df)) {
      cat(sprintf("[BLOCKER] column_types '%s': column named in plan_spec[['column_types']] is absent from df\n", col))
      qa2["blockers"] <- qa2["blockers"] + 1L
    } else {
      actual_type <- class(df[[col]])[1]
      expected_type <- type_spec[[col]]
      if (!identical(actual_type, expected_type)) {
        cat(sprintf("[WARNING] column_types '%s': expected %s, observed %s\n", col, expected_type, actual_type))
        qa2["warnings"] <- qa2["warnings"] + 1L
      } else {
        cat(sprintf("[PASS] column_types '%s': observed class %s == expected %s\n", col, actual_type, expected_type))
        qa2["passed"] <- qa2["passed"] + 1L
      }
    }
  }
}

# --- Data Profiling (for qa2+ decision) ---
cat("\n")
cat(strrep("=", 60), "\n")
cat("DATA PROFILING\n")
cat(strrep("=", 60), "\n")
cat("\nFirst 10 rows:\n")
print(head(df, 10))
cat("\nDescriptive statistics:\n")
print(summary(df))

# --- Verdict ---
# INTENT: Derive the QA2 verdict from the counters rather than asserting it.
cat(sprintf("\nChecks: %d passed, %d warnings, %d blockers, %d not verified, %d skipped, %d info\n",
            qa2[["passed"]], qa2[["warnings"]], qa2[["blockers"]],
            qa2[["not_verified"]], qa2[["skipped"]], qa2[["info"]]))
qa2_result <- if (qa2[["blockers"]] > 0) {
  "BLOCKER"
} else if (qa2[["warnings"]] > 0 || qa2[["not_verified"]] > 0) {
  "WARNING"
} else if (qa2[["passed"]] == 0) {
  "WARNING"  # nothing was actually verified
} else {
  "PASSED"
}
cat(sprintf("QA2 RESULT: %s\n", qa2_result))
cat(strrep("=", 60), "\n")
```

### QA2 Discretionary Checks

| Check | When to Add | What It Validates |
|-------|-------------|-------------------|
| Distribution comparison | Statistical analysis | Pre/post distributions similar |
| Outlier retention | Outlier-sensitive analysis | Correct outlier handling |
| Null pattern | Complex null logic | Nulls handled per specification |
| **Complement inspection** | **Always (at minimum 5)** — see `.claude/agents/code-reviewer.md` § Five Lenses of Skeptical Review | **Examine what was REMOVED by cleaning — do the removed rows look like what you'd expect?** |

**Creative check prompt:** Before writing your QA2 script, ask: *"If the cleaning logic had an off-by-one error in the filter condition (e.g., `>= -1` instead of `== -1`), what would the symptom look like in the cleaned data?"* Design at least one check to catch that class of error.

### QA2 Iterative Investigation Triggers

Observations from qa1 that should trigger qa2+ investigation:

| qa1 Observation | Suggested qa2 Investigation |
|-----------------|---------------------------|
| Coded value removal affected >20% of rows for a column | Profile removed rows: is a specific subgroup disproportionately affected? |
| Suppression rate varies widely across states | Investigate: does suppression pattern correlate with state reporting practices? |
| Type casting changed value distributions | Verify: are boundary values (min/max) preserved correctly after cast? |
| Null pattern is non-random (clustered by year or state) | Analyze: could missing data pattern bias the analysis conclusions? |

---

## QA3: Post-Transform Quality Assessment

**Applies To:** Stage 7 scripts (EDA and transformation)

**Purpose:** Verify transformations produced correct results, not just that they executed.

### Default Checks

| Check | What It Validates | BLOCKER If |
|-------|-------------------|------------|
| Join cardinality | Expected 1:1, 1:many, many:1 | Unexpected fan-out or data loss |
| Aggregation correctness | Sums, means, counts correct | Aggregation logic error |
| Row preservation | Expected row change | >90% unexpected data loss |
| Column creation | New columns calculated correctly | Derived columns have wrong values |
| No surprise nulls | Expected nulls only | Unexpected nulls introduced |

### QA3 Standard Check Script (cr1)

```python
import polars as pl

# --- Config ---
# INTENT: Declare which QA3 checks legitimately do not apply to this script.
# ASSUMES: Keys are the documented QA3 keys (join_cardinality, aggregation,
#          row_preservation, unexpected_nulls); each value is a NON-EMPTY reason string.
not_applicable = {}  # e.g. {"join_cardinality": "this step reshapes one frame — no join performed"}

# INTENT: Count every outcome so the QA3 verdict is derived from what actually ran.
qa3 = {"passed": 0, "warnings": 0, "blockers": 0, "not_verified": 0, "skipped": 0, "info": 0}

# INTENT: Enumerate every configuration string the template knows how to evaluate.
# REASONING: An unrecognized value must be a BLOCKER, not a fall-through — the old `==
#            "1:1"` chain printed a header and no verdict for "1:many" or a typo.
KNOWN_CARDINALITIES = ("1:1", "1:many", "many:1", "many:many")
KNOWN_JOIN_TYPES = ("inner", "left", "right", "outer", "full", "semi", "anti")
KNOWN_AGG_FUNCS = ("sum", "mean", "count", "median", "min", "max")

print("\n" + "=" * 60)
print("QA3: POST-TRANSFORM QUALITY ASSESSMENT")
print("=" * 60)

# --- Validate: join_cardinality ---
# INTENT: Bound the output row count by what the declared cardinality and join type allow.
# REASONING: The ceiling depends on BOTH the cardinality and the join type (an outer join
#            legitimately exceeds max(left, right)); many:many is not bounded by row counts
#            at all, so that pair is reported unverified rather than silently accepted.
# ASSUMES: source_dfs["left"] / ["right"] are the pre-join frames and df is the join result.
print("\nJoin Cardinality:")
join_spec = transform_spec.get("join")
if not_applicable.get("join_cardinality"):
    print(f"[SKIPPED] join_cardinality: {not_applicable['join_cardinality']}")
    qa3["skipped"] += 1
elif "join_cardinality" in not_applicable:
    print("[NOT VERIFIED] join_cardinality: declared not_applicable with an empty reason string")
    qa3["not_verified"] += 1
elif join_spec is None:
    print("[NOT VERIFIED] join_cardinality: transform_spec has no 'join' entry — declare not_applicable if this step performs no join")
    qa3["not_verified"] += 1
else:
    expected_cardinality = join_spec.get("expected_cardinality")
    join_type = join_spec.get("join_type")
    left_df = source_dfs.get("left")
    right_df = source_dfs.get("right")
    if left_df is None or right_df is None:
        side = "left" if left_df is None else "right"
        print(f"[NOT VERIFIED] join_cardinality: source_dfs['{side}'] is missing — row-count bound not computable")
        qa3["not_verified"] += 1
    elif expected_cardinality not in KNOWN_CARDINALITIES:
        print(f"[BLOCKER] join_cardinality: unrecognized expected_cardinality {expected_cardinality!r} (known: {list(KNOWN_CARDINALITIES)})")
        qa3["blockers"] += 1
    elif join_type not in KNOWN_JOIN_TYPES:
        print(f"[BLOCKER] join_cardinality: unrecognized join_type {join_type!r} (known: {list(KNOWN_JOIN_TYPES)})")
        qa3["blockers"] += 1
    else:
        n_out, n_left, n_right = len(df), len(left_df), len(right_df)
        if join_type in ("semi", "anti"):
            ceiling = n_left  # filtering joins never emit more than the left frame
        elif expected_cardinality == "1:1":
            ceiling = n_left + n_right if join_type in ("outer", "full") else max(n_left, n_right)
        elif expected_cardinality == "1:many":
            ceiling = n_right + (n_left if join_type in ("outer", "full") else 0)
        elif expected_cardinality == "many:1":
            ceiling = n_left + (n_right if join_type in ("outer", "full") else 0)
        else:  # many:many
            ceiling = None
        if ceiling is None:
            print(f"[NOT VERIFIED] join_cardinality: '{expected_cardinality}' with join_type '{join_type}' — row counts cannot bound many:many fan-out; test key duplication on both sides directly")
            qa3["not_verified"] += 1
        elif n_out > ceiling * 1.05:
            print(f"[BLOCKER] join_cardinality: fan-out beyond '{expected_cardinality}'/'{join_type}' — {n_out} output rows exceed the {ceiling} ceiling (left={n_left}, right={n_right})")
            qa3["blockers"] += 1
        else:
            print(f"[PASS] join_cardinality: {n_out} output rows within the {ceiling} ceiling for '{expected_cardinality}'/'{join_type}' (left={n_left}, right={n_right})")
            qa3["passed"] += 1

# --- Validate: aggregation ---
# INTENT: Recompute one group's aggregate from the source frame and compare it to the output.
# REASONING: Only "sum" was dispatched before, so mean/count/median configs ran no check at
#            all. The tolerance base is abs()-ed because a negative source value inverted
#            the comparison, and source == 0 is separated out because a 1% tolerance on 0
#            makes every nonzero result look acceptable.
# ASSUMES: source_dfs["input"] is the pre-aggregation frame; the sampled group is the first
#          non-null group value in sort order, so the spot-check is deterministic.
print("\nAggregation Spot-Check:")
agg_spec = transform_spec.get("aggregation")
if not_applicable.get("aggregation"):
    print(f"[SKIPPED] aggregation: {not_applicable['aggregation']}")
    qa3["skipped"] += 1
elif "aggregation" in not_applicable:
    print("[NOT VERIFIED] aggregation: declared not_applicable with an empty reason string")
    qa3["not_verified"] += 1
elif agg_spec is None:
    print("[NOT VERIFIED] aggregation: transform_spec has no 'aggregation' entry — declare not_applicable if this step aggregates nothing")
    qa3["not_verified"] += 1
else:
    group_col = agg_spec.get("group_by")
    agg_col = agg_spec.get("column")
    agg_func = agg_spec.get("function")
    source_input = source_dfs.get("input")
    if source_input is None:
        print("[NOT VERIFIED] aggregation: source_dfs['input'] is missing — nothing to recompute from")
        qa3["not_verified"] += 1
    elif agg_func not in KNOWN_AGG_FUNCS:
        print(f"[BLOCKER] aggregation: unrecognized function {agg_func!r} (known: {list(KNOWN_AGG_FUNCS)})")
        qa3["blockers"] += 1
    elif group_col not in df.columns or agg_col not in df.columns:
        absent = [c for c in (group_col, agg_col) if c not in df.columns]
        print(f"[BLOCKER] aggregation: column(s) {absent} named in transform_spec are absent from the output frame")
        qa3["blockers"] += 1
    elif group_col not in source_input.columns or agg_col not in source_input.columns:
        absent = [c for c in (group_col, agg_col) if c not in source_input.columns]
        print(f"[BLOCKER] aggregation: column(s) {absent} are absent from source_dfs['input']")
        qa3["blockers"] += 1
    else:
        groups = df[group_col].drop_nulls().unique().sort()
        if len(groups) == 0:
            print(f"[NOT VERIFIED] aggregation: '{group_col}' has no non-null values in the output frame — no group to spot-check")
            qa3["not_verified"] += 1
        else:
            sample_group = groups[0]
            src = source_input.filter(pl.col(group_col) == sample_group)
            out = df.filter(pl.col(group_col) == sample_group)
            if agg_func == "sum":
                source_val, result_val = src[agg_col].sum(), out[agg_col].sum()
            elif agg_func == "mean":
                source_val, result_val = src[agg_col].mean(), out[agg_col].mean()
            elif agg_func == "count":
                source_val, result_val = float(len(src)), float(out[agg_col].sum())
            elif agg_func == "median":
                source_val, result_val = src[agg_col].median(), out[agg_col].median()
            elif agg_func == "min":
                source_val, result_val = src[agg_col].min(), out[agg_col].min()
            else:  # max
                source_val, result_val = src[agg_col].max(), out[agg_col].max()
            if source_val is None or result_val is None:
                print(f"[NOT VERIFIED] aggregation '{agg_func}' on '{agg_col}' (group {sample_group!r}): source or result is null — comparison undefined")
                qa3["not_verified"] += 1
            elif source_val == 0 and result_val != 0:
                print(f"[BLOCKER] aggregation '{agg_func}' on '{agg_col}' (group {sample_group!r}): source={source_val}, result={result_val} — nonzero result from a zero source")
                qa3["blockers"] += 1
            elif source_val == 0:
                print(f"[PASS] aggregation '{agg_func}' on '{agg_col}' (group {sample_group!r}): source=0 == result=0")
                qa3["passed"] += 1
            elif abs(source_val - result_val) > 0.01 * abs(source_val):
                print(f"[BLOCKER] aggregation '{agg_func}' on '{agg_col}' (group {sample_group!r}): source={source_val}, result={result_val}, diff={abs(source_val - result_val)} > 1% tolerance")
                qa3["blockers"] += 1
            else:
                print(f"[PASS] aggregation '{agg_func}' on '{agg_col}' (group {sample_group!r}): source={source_val} == result={result_val} within 1% ({abs(source_val - result_val)})")
                qa3["passed"] += 1

# --- Validate: row_preservation ---
# INTENT: Compare the output row count against the Plan's expectation.
# REASONING: `if expected_rows:` treated 0 as unset, silently skipping the check. 0 is a
#            legitimate expectation and gets its own branch; None means untested.
# ASSUMES: expected_rows is a count, not a rate.
print("\nRow Preservation:")
expected_rows = transform_spec.get("expected_rows")
if not_applicable.get("row_preservation"):
    print(f"[SKIPPED] row_preservation: {not_applicable['row_preservation']}")
    qa3["skipped"] += 1
elif "row_preservation" in not_applicable:
    print("[NOT VERIFIED] row_preservation: declared not_applicable with an empty reason string")
    qa3["not_verified"] += 1
elif expected_rows is None:
    print("[NOT VERIFIED] row_preservation: transform_spec['expected_rows'] is not set — deviation untestable")
    qa3["not_verified"] += 1
elif isinstance(expected_rows, bool) or not isinstance(expected_rows, (int, float)):
    print(f"[BLOCKER] row_preservation: expected_rows {expected_rows!r} is not a numeric row count")
    qa3["blockers"] += 1
elif expected_rows == 0:
    if len(df) == 0:
        print("[PASS] row_preservation: expected 0 rows, observed 0 rows")
        qa3["passed"] += 1
    else:
        print(f"[BLOCKER] row_preservation: expected 0 rows, observed {len(df):,}")
        qa3["blockers"] += 1
else:
    row_diff = abs(len(df) - expected_rows) / expected_rows
    if row_diff > 0.5:
        print(f"[BLOCKER] row_preservation: expected ~{expected_rows:,}, observed {len(df):,} ({row_diff:.1%} deviation)")
        qa3["blockers"] += 1
    elif row_diff > 0.1:
        print(f"[WARNING] row_preservation: expected ~{expected_rows:,}, observed {len(df):,} ({row_diff:.1%} deviation)")
        qa3["warnings"] += 1
    else:
        print(f"[PASS] row_preservation: observed {len(df):,} rows vs expected ~{expected_rows:,} ({row_diff:.1%} deviation)")
        qa3["passed"] += 1

# --- Validate: unexpected_nulls ---
# INTENT: Confirm the columns declared null-free actually are.
# REASONING: A column named in no_null_columns but absent from the frame produced no line
#            before — an absent column cannot be null-free, so it is a BLOCKER.
# ASSUMES: no_null_columns lists post-transform output columns.
print("\nUnexpected Nulls:")
no_null_cols = transform_spec.get("no_null_columns")
if not_applicable.get("unexpected_nulls"):
    print(f"[SKIPPED] unexpected_nulls: {not_applicable['unexpected_nulls']}")
    qa3["skipped"] += 1
elif "unexpected_nulls" in not_applicable:
    print("[NOT VERIFIED] unexpected_nulls: declared not_applicable with an empty reason string")
    qa3["not_verified"] += 1
elif no_null_cols is None or len(no_null_cols) == 0:
    print("[NOT VERIFIED] unexpected_nulls: transform_spec['no_null_columns'] is missing or empty — no columns declared null-free")
    qa3["not_verified"] += 1
else:
    for col in no_null_cols:
        if col not in df.columns:
            print(f"[BLOCKER] unexpected_nulls '{col}': column declared null-free is absent from df")
            qa3["blockers"] += 1
            continue
        null_count = df[col].null_count()
        if null_count > 0:
            print(f"[BLOCKER] unexpected_nulls '{col}': {null_count} of {len(df)} rows are null")
            qa3["blockers"] += 1
        else:
            print(f"[PASS] unexpected_nulls '{col}': 0 nulls over {len(df)} rows")
            qa3["passed"] += 1

# --- Data Profiling (for qa2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)
print(f"\nFirst 10 rows:\n{df.head(10)}")
print(f"\nDescriptive statistics:\n{df.describe()}")

# --- Verdict ---
# INTENT: Derive the QA3 verdict from the counters rather than asserting it.
print(f"\nChecks: {qa3['passed']} passed, {qa3['warnings']} warnings, {qa3['blockers']} blockers, "
      f"{qa3['not_verified']} not verified, {qa3['skipped']} skipped, {qa3['info']} info")
if qa3["blockers"] > 0:
    qa3_result = "BLOCKER"
elif qa3["warnings"] > 0 or qa3["not_verified"] > 0:
    qa3_result = "WARNING"
elif qa3["passed"] == 0:
    qa3_result = "WARNING"  # nothing was actually verified
else:
    qa3_result = "PASSED"
print(f"QA3 RESULT: {qa3_result}")
print("=" * 60)
```

### QA3 Standard Check Script — R (cr1)

```r
library(dplyr)
library(arrow)

# --- Config ---
# INTENT: Declare which QA3 checks legitimately do not apply to this script.
# ASSUMES: Names are the documented QA3 keys; each element is a non-empty reason string.
not_applicable <- list()  # e.g. list(join_cardinality = "this step reshapes one frame - no join")

# INTENT: Count every outcome so the QA3 verdict is derived from what actually ran.
qa3 <- c(passed = 0L, warnings = 0L, blockers = 0L, not_verified = 0L, skipped = 0L, info = 0L)

# INTENT: Enumerate every configuration string the template knows how to evaluate.
# REASONING: An unrecognized value is a BLOCKER, not a fall-through.
KNOWN_CARDINALITIES <- c("1:1", "1:many", "many:1", "many:many")
KNOWN_JOIN_TYPES <- c("inner", "left", "right", "outer", "full", "semi", "anti")
KNOWN_AGG_FUNCS <- c("sum", "mean", "count", "median", "min", "max")

cat("\n")
cat(strrep("=", 60), "\n")
cat("QA3: POST-TRANSFORM QUALITY ASSESSMENT\n")
cat(strrep("=", 60), "\n")

# --- Validate: join_cardinality ---
# INTENT: Bound the output row count by what the declared cardinality and join type allow.
# REASONING: The ceiling depends on BOTH the cardinality and the join type; many:many is
#            not bounded by row counts at all, so that pair reports NOT VERIFIED.
# ASSUMES: source_dfs[["left"]] / [["right"]] are the pre-join frames, df is the result.
cat("\nJoin Cardinality:\n")
join_spec <- transform_spec[["join"]]
na_reason <- if ("join_cardinality" %in% names(not_applicable)) not_applicable[["join_cardinality"]] else NULL
if (!is.null(na_reason) && nzchar(na_reason)) {
  cat(sprintf("[SKIPPED] join_cardinality: %s\n", na_reason))
  qa3["skipped"] <- qa3["skipped"] + 1L
} else if ("join_cardinality" %in% names(not_applicable)) {
  cat("[NOT VERIFIED] join_cardinality: declared not_applicable with an empty reason string\n")
  qa3["not_verified"] <- qa3["not_verified"] + 1L
} else if (is.null(join_spec)) {
  cat("[NOT VERIFIED] join_cardinality: transform_spec has no 'join' entry - declare not_applicable if this step performs no join\n")
  qa3["not_verified"] <- qa3["not_verified"] + 1L
} else {
  expected_cardinality <- join_spec[["expected_cardinality"]]
  join_type <- join_spec[["join_type"]]
  left_df <- source_dfs[["left"]]
  right_df <- source_dfs[["right"]]
  if (is.null(left_df) || is.null(right_df)) {
    side <- if (is.null(left_df)) "left" else "right"
    cat(sprintf("[NOT VERIFIED] join_cardinality: source_dfs[['%s']] is missing - row-count bound not computable\n", side))
    qa3["not_verified"] <- qa3["not_verified"] + 1L
  } else if (is.null(expected_cardinality) || !expected_cardinality %in% KNOWN_CARDINALITIES) {
    cat(sprintf("[BLOCKER] join_cardinality: unrecognized expected_cardinality '%s' (known: %s)\n",
                if (is.null(expected_cardinality)) "NULL" else as.character(expected_cardinality),
                paste(KNOWN_CARDINALITIES, collapse = ", ")))
    qa3["blockers"] <- qa3["blockers"] + 1L
  } else if (is.null(join_type) || !join_type %in% KNOWN_JOIN_TYPES) {
    cat(sprintf("[BLOCKER] join_cardinality: unrecognized join_type '%s' (known: %s)\n",
                if (is.null(join_type)) "NULL" else as.character(join_type),
                paste(KNOWN_JOIN_TYPES, collapse = ", ")))
    qa3["blockers"] <- qa3["blockers"] + 1L
  } else {
    n_out <- nrow(df); n_left <- nrow(left_df); n_right <- nrow(right_df)
    ceiling_rows <- if (join_type %in% c("semi", "anti")) {
      n_left  # filtering joins never emit more than the left frame
    } else if (expected_cardinality == "1:1") {
      if (join_type %in% c("outer", "full")) n_left + n_right else max(n_left, n_right)
    } else if (expected_cardinality == "1:many") {
      n_right + (if (join_type %in% c("outer", "full")) n_left else 0)
    } else if (expected_cardinality == "many:1") {
      n_left + (if (join_type %in% c("outer", "full")) n_right else 0)
    } else {
      NULL  # many:many
    }
    if (is.null(ceiling_rows)) {
      cat(sprintf("[NOT VERIFIED] join_cardinality: '%s' with join_type '%s' - row counts cannot bound many:many fan-out; test key duplication on both sides directly\n",
                  expected_cardinality, join_type))
      qa3["not_verified"] <- qa3["not_verified"] + 1L
    } else if (n_out > ceiling_rows * 1.05) {
      cat(sprintf("[BLOCKER] join_cardinality: fan-out beyond '%s'/'%s' - %d output rows exceed the %d ceiling (left=%d, right=%d)\n",
                  expected_cardinality, join_type, n_out, ceiling_rows, n_left, n_right))
      qa3["blockers"] <- qa3["blockers"] + 1L
    } else {
      cat(sprintf("[PASS] join_cardinality: %d output rows within the %d ceiling for '%s'/'%s' (left=%d, right=%d)\n",
                  n_out, ceiling_rows, expected_cardinality, join_type, n_left, n_right))
      qa3["passed"] <- qa3["passed"] + 1L
    }
  }
}

# --- Validate: aggregation ---
# INTENT: Recompute one group's aggregate from the source frame and compare to the output.
# REASONING: Only "sum" was dispatched before, so mean/count/median configs ran no check.
#            The tolerance base is abs()-ed, and source == 0 gets explicit branches because
#            a 1% tolerance on 0 accepts any result.
# ASSUMES: source_dfs[["input"]] is the pre-aggregation frame; the sampled group is the
#          first non-NA group value in sort order, making the spot-check deterministic.
cat("\nAggregation Spot-Check:\n")
agg_spec <- transform_spec[["aggregation"]]
na_reason <- if ("aggregation" %in% names(not_applicable)) not_applicable[["aggregation"]] else NULL
if (!is.null(na_reason) && nzchar(na_reason)) {
  cat(sprintf("[SKIPPED] aggregation: %s\n", na_reason))
  qa3["skipped"] <- qa3["skipped"] + 1L
} else if ("aggregation" %in% names(not_applicable)) {
  cat("[NOT VERIFIED] aggregation: declared not_applicable with an empty reason string\n")
  qa3["not_verified"] <- qa3["not_verified"] + 1L
} else if (is.null(agg_spec)) {
  cat("[NOT VERIFIED] aggregation: transform_spec has no 'aggregation' entry - declare not_applicable if this step aggregates nothing\n")
  qa3["not_verified"] <- qa3["not_verified"] + 1L
} else {
  group_col <- agg_spec[["group_by"]]
  agg_col <- agg_spec[["column"]]
  agg_func <- agg_spec[["function"]]
  source_input <- source_dfs[["input"]]
  if (is.null(source_input)) {
    cat("[NOT VERIFIED] aggregation: source_dfs[['input']] is missing - nothing to recompute from\n")
    qa3["not_verified"] <- qa3["not_verified"] + 1L
  } else if (is.null(agg_func) || !agg_func %in% KNOWN_AGG_FUNCS) {
    cat(sprintf("[BLOCKER] aggregation: unrecognized function '%s' (known: %s)\n",
                if (is.null(agg_func)) "NULL" else as.character(agg_func),
                paste(KNOWN_AGG_FUNCS, collapse = ", ")))
    qa3["blockers"] <- qa3["blockers"] + 1L
  } else if (is.null(group_col) || is.null(agg_col) ||
             !all(c(group_col, agg_col) %in% names(df)) ||
             !all(c(group_col, agg_col) %in% names(source_input))) {
    cat("[BLOCKER] aggregation: group_by/column named in transform_spec are absent from df or source_dfs[['input']]\n")
    qa3["blockers"] <- qa3["blockers"] + 1L
  } else {
    groups <- sort(unique(df[[group_col]][!is.na(df[[group_col]])]))
    if (length(groups) == 0) {
      cat(sprintf("[NOT VERIFIED] aggregation: '%s' has no non-NA values in the output frame - no group to spot-check\n", group_col))
      qa3["not_verified"] <- qa3["not_verified"] + 1L
    } else {
      sample_group <- groups[1]
      src_vals <- source_input[[agg_col]][source_input[[group_col]] == sample_group]
      out_vals <- df[[agg_col]][df[[group_col]] == sample_group]
      src_vals <- src_vals[!is.na(src_vals)]
      out_vals <- out_vals[!is.na(out_vals)]
      if (agg_func == "count") {
        source_val <- length(src_vals)
        result_val <- if (length(out_vals) > 0) sum(out_vals) else NA_real_
      } else if (length(src_vals) == 0 || length(out_vals) == 0) {
        source_val <- NA_real_
        result_val <- NA_real_
      } else if (agg_func == "sum") {
        source_val <- sum(src_vals); result_val <- sum(out_vals)
      } else if (agg_func == "mean") {
        source_val <- mean(src_vals); result_val <- mean(out_vals)
      } else if (agg_func == "median") {
        source_val <- median(src_vals); result_val <- median(out_vals)
      } else if (agg_func == "min") {
        source_val <- min(src_vals); result_val <- min(out_vals)
      } else {
        source_val <- max(src_vals); result_val <- max(out_vals)
      }
      if (is.na(source_val) || is.na(result_val)) {
        cat(sprintf("[NOT VERIFIED] aggregation '%s' on '%s' (group %s): source or result is NA - comparison undefined\n",
                    agg_func, agg_col, as.character(sample_group)))
        qa3["not_verified"] <- qa3["not_verified"] + 1L
      } else if (source_val == 0 && result_val != 0) {
        cat(sprintf("[BLOCKER] aggregation '%s' on '%s' (group %s): source=0, result=%s - nonzero result from a zero source\n",
                    agg_func, agg_col, as.character(sample_group), format(result_val)))
        qa3["blockers"] <- qa3["blockers"] + 1L
      } else if (source_val == 0) {
        cat(sprintf("[PASS] aggregation '%s' on '%s' (group %s): source=0 == result=0\n",
                    agg_func, agg_col, as.character(sample_group)))
        qa3["passed"] <- qa3["passed"] + 1L
      } else if (abs(source_val - result_val) > 0.01 * abs(source_val)) {
        cat(sprintf("[BLOCKER] aggregation '%s' on '%s' (group %s): source=%s, result=%s, diff=%s > 1%% tolerance\n",
                    agg_func, agg_col, as.character(sample_group), format(source_val),
                    format(result_val), format(abs(source_val - result_val))))
        qa3["blockers"] <- qa3["blockers"] + 1L
      } else {
        cat(sprintf("[PASS] aggregation '%s' on '%s' (group %s): source=%s == result=%s within 1%% (%s)\n",
                    agg_func, agg_col, as.character(sample_group), format(source_val),
                    format(result_val), format(abs(source_val - result_val))))
        qa3["passed"] <- qa3["passed"] + 1L
      }
    }
  }
}

# --- Validate: row_preservation ---
# INTENT: Compare the output row count against the Plan's expectation.
# REASONING: expected_rows of 0 is legitimate and gets its own branch (the Python sibling
#            silently skipped it; R divided by zero and produced Inf). NULL means untested.
# ASSUMES: expected_rows is a single numeric row count, not a rate.
cat("\nRow Preservation:\n")
expected_rows <- transform_spec[["expected_rows"]]
na_reason <- if ("row_preservation" %in% names(not_applicable)) not_applicable[["row_preservation"]] else NULL
if (!is.null(na_reason) && nzchar(na_reason)) {
  cat(sprintf("[SKIPPED] row_preservation: %s\n", na_reason))
  qa3["skipped"] <- qa3["skipped"] + 1L
} else if ("row_preservation" %in% names(not_applicable)) {
  cat("[NOT VERIFIED] row_preservation: declared not_applicable with an empty reason string\n")
  qa3["not_verified"] <- qa3["not_verified"] + 1L
} else if (is.null(expected_rows) || length(expected_rows) != 1 || is.na(expected_rows)) {
  cat("[NOT VERIFIED] row_preservation: transform_spec[['expected_rows']] is unset or NA - deviation untestable\n")
  qa3["not_verified"] <- qa3["not_verified"] + 1L
} else if (!is.numeric(expected_rows)) {
  cat(sprintf("[BLOCKER] row_preservation: expected_rows '%s' is not a numeric row count\n", as.character(expected_rows)))
  qa3["blockers"] <- qa3["blockers"] + 1L
} else if (expected_rows == 0) {
  if (nrow(df) == 0) {
    cat("[PASS] row_preservation: expected 0 rows, observed 0 rows\n")
    qa3["passed"] <- qa3["passed"] + 1L
  } else {
    cat(sprintf("[BLOCKER] row_preservation: expected 0 rows, observed %s\n", format(nrow(df), big.mark = ",")))
    qa3["blockers"] <- qa3["blockers"] + 1L
  }
} else {
  row_diff <- abs(nrow(df) - expected_rows) / expected_rows
  if (row_diff > 0.5) {
    cat(sprintf("[BLOCKER] row_preservation: expected ~%s, observed %s (%.1f%% deviation)\n",
                format(expected_rows, big.mark = ","), format(nrow(df), big.mark = ","), row_diff * 100))
    qa3["blockers"] <- qa3["blockers"] + 1L
  } else if (row_diff > 0.1) {
    cat(sprintf("[WARNING] row_preservation: expected ~%s, observed %s (%.1f%% deviation)\n",
                format(expected_rows, big.mark = ","), format(nrow(df), big.mark = ","), row_diff * 100))
    qa3["warnings"] <- qa3["warnings"] + 1L
  } else {
    cat(sprintf("[PASS] row_preservation: observed %s rows vs expected ~%s (%.1f%% deviation)\n",
                format(nrow(df), big.mark = ","), format(expected_rows, big.mark = ","), row_diff * 100))
    qa3["passed"] <- qa3["passed"] + 1L
  }
}

# --- Validate: unexpected_nulls ---
# INTENT: Confirm the columns declared null-free actually are.
# REASONING: A column named in no_null_columns but absent from the frame produced no line
#            before - an absent column cannot be null-free, so it is a BLOCKER.
# ASSUMES: no_null_columns lists post-transform output columns.
cat("\nUnexpected Nulls:\n")
no_null_cols <- transform_spec[["no_null_columns"]]
na_reason <- if ("unexpected_nulls" %in% names(not_applicable)) not_applicable[["unexpected_nulls"]] else NULL
if (!is.null(na_reason) && nzchar(na_reason)) {
  cat(sprintf("[SKIPPED] unexpected_nulls: %s\n", na_reason))
  qa3["skipped"] <- qa3["skipped"] + 1L
} else if ("unexpected_nulls" %in% names(not_applicable)) {
  cat("[NOT VERIFIED] unexpected_nulls: declared not_applicable with an empty reason string\n")
  qa3["not_verified"] <- qa3["not_verified"] + 1L
} else if (is.null(no_null_cols) || length(no_null_cols) == 0) {
  cat("[NOT VERIFIED] unexpected_nulls: transform_spec[['no_null_columns']] is missing or empty - no columns declared null-free\n")
  qa3["not_verified"] <- qa3["not_verified"] + 1L
} else {
  for (col in no_null_cols) {
    if (!col %in% names(df)) {
      cat(sprintf("[BLOCKER] unexpected_nulls '%s': column declared null-free is absent from df\n", col))
      qa3["blockers"] <- qa3["blockers"] + 1L
      next
    }
    null_count <- sum(is.na(df[[col]]))
    if (null_count > 0) {
      cat(sprintf("[BLOCKER] unexpected_nulls '%s': %d of %d rows are NA\n", col, null_count, nrow(df)))
      qa3["blockers"] <- qa3["blockers"] + 1L
    } else {
      cat(sprintf("[PASS] unexpected_nulls '%s': 0 NAs over %d rows\n", col, nrow(df)))
      qa3["passed"] <- qa3["passed"] + 1L
    }
  }
}

# --- Data Profiling (for qa2+ decision) ---
cat("\n")
cat(strrep("=", 60), "\n")
cat("DATA PROFILING\n")
cat(strrep("=", 60), "\n")
cat("\nFirst 10 rows:\n")
print(head(df, 10))
cat("\nDescriptive statistics:\n")
print(summary(df))

# --- Verdict ---
# INTENT: Derive the QA3 verdict from the counters rather than asserting it.
cat(sprintf("\nChecks: %d passed, %d warnings, %d blockers, %d not verified, %d skipped, %d info\n",
            qa3[["passed"]], qa3[["warnings"]], qa3[["blockers"]],
            qa3[["not_verified"]], qa3[["skipped"]], qa3[["info"]]))
qa3_result <- if (qa3[["blockers"]] > 0) {
  "BLOCKER"
} else if (qa3[["warnings"]] > 0 || qa3[["not_verified"]] > 0) {
  "WARNING"
} else if (qa3[["passed"]] == 0) {
  "WARNING"  # nothing was actually verified
} else {
  "PASSED"
}
cat(sprintf("QA3 RESULT: %s\n", qa3_result))
cat(strrep("=", 60), "\n")
```

### QA3 Discretionary Checks

| Check | When to Add | What It Validates |
|-------|-------------|-------------------|
| Statistical tests | Distribution-critical | K-S test for distribution preservation |
| Business logic | Complex derivations | Derived values match business rules |
| Cross-validation | Multiple sources | Results consistent across methods |
| Temporal consistency | Time-series | No impossible date sequences |
| **Concrete trace** | **Always (at minimum 5)** — see `.claude/agents/code-reviewer.md` § Five Lenses of Skeptical Review | **Pick one entity and verify its journey through the transformation end-to-end** |

**Creative check prompt:** Before writing your QA3 script, ask: *"If this transformation had a subtle bug that affected 5% of records, what would the symptom look like in the output data? How would I detect it?"* Design at least one check to answer that question.

### QA3 Iterative Investigation Triggers

Observations from qa1 that should trigger qa2+ investigation:

| qa1 Observation | Suggested qa2 Investigation |
|-----------------|---------------------------|
| Join match rate < 80% | Profile non-matching keys: is there a systematic pattern (state, year, school type)? |
| Aggregation changed distribution shape significantly | Verify: are outlier groups driving the change? Is the aggregation logic correct? |
| Derived column has unexpected null rate | Trace: which input columns contribute nulls? Is the derivation formula correct? |
| Row count after transformation differs >10% from Plan estimate | Investigate: which filter or join step caused the unexpected change? |

---

## QA4a: Post-Analysis Statistical Validity

**Applies To:** Stage 8 scripts (statistical analysis and visualization)

**Purpose:** Verify data is represented accurately, statistical analyses are correct, and no misrepresentation occurs.

### Default Checks

| Check | What It Validates | BLOCKER If |
|-------|-------------------|------------|
| Data source accuracy | Correct dataset used | Figure/analysis uses wrong data file |
| Aggregation correctness | Calculations match script logic | Aggregated values don't match source data |
| Model convergence | Statistical models converged (if applicable) | Non-convergence without documentation |
| Assumption validation | Model assumptions checked (if applicable) | Critical assumptions violated without discussion |
| Coefficient reasonableness | Effect sizes plausible (if applicable) | Coefficients contradict domain knowledge |
| Robustness consistency | Alternative specs agree (if applicable) | Primary result reverses in robustness check |
| Axis scale appropriateness | Scales don't distort relationships | Y-axis truncation misleads interpretation |
| Statistical representation | Visual encoding matches data semantics | Bar chart for continuous data, pie chart for >7 categories |

### QA4a cra1 Script Template

```python
import polars as pl
from pathlib import Path

# --- Config ---
# INTENT: Declare which QA4a checks legitimately do not apply to this script.
# ASSUMES: Keys are the documented QA4a keys (data_source, aggregation, model_convergence,
#          assumptions, robustness); each value is a NON-EMPTY reason string.
not_applicable = {}  # e.g. {"model_convergence": "descriptive script — no model is estimated"}

# INTENT: Count every outcome so the QA4a verdict is derived from what actually ran.
qa4a = {"passed": 0, "warnings": 0, "blockers": 0, "not_verified": 0, "skipped": 0, "info": 0}

KNOWN_AGG_FUNCS = ("sum", "mean", "count", "median", "min", "max")
KNOWN_SIGNS = (-1, 0, 1)  # documented sign encoding: negative / null / positive

print("\n" + "=" * 60)
print("QA4a: POST-ANALYSIS STATISTICAL VALIDITY")
print("=" * 60)

# --- Validate: data_source ---
# INTENT: Confirm the analysed script actually loads the dataset the Plan names.
# REASONING: `"" in text` is True, so an empty data_source string passed unconditionally.
#            Comments are stripped before matching because a path mentioned only in a
#            comment is documentation, not a load.
# ASSUMES: `#` starts a comment; a `#` inside a string literal will truncate that line for
#          matching purposes, which can only make this check stricter, never laxer.
print("\nData Source Check:")
expected_data_source = plan_spec.get("data_source")
script_path = Path(script_spec["script_path"]) if script_spec.get("script_path") else None
if not_applicable.get("data_source"):
    print(f"[SKIPPED] data_source: {not_applicable['data_source']}")
    qa4a["skipped"] += 1
elif "data_source" in not_applicable:
    print("[NOT VERIFIED] data_source: declared not_applicable with an empty reason string")
    qa4a["not_verified"] += 1
elif expected_data_source is None or len(str(expected_data_source).strip()) == 0:
    print("[NOT VERIFIED] data_source: plan_spec['data_source'] is missing or empty — no path to search for")
    qa4a["not_verified"] += 1
elif script_path is None or not script_path.exists():
    print(f"[NOT VERIFIED] data_source: script_spec['script_path'] ({script_path}) does not exist — cannot inspect")
    qa4a["not_verified"] += 1
else:
    script_text = script_path.read_text()
    code_lines = [ln.split("#", 1)[0] for ln in script_text.splitlines()]
    code_text = "\n".join(code_lines)
    hit_lines = [i + 1 for i, ln in enumerate(code_lines) if expected_data_source in ln]
    if len(hit_lines) == 0 and expected_data_source in script_text:
        print(f"[BLOCKER] data_source: '{expected_data_source}' appears only in comments of {script_path.name} — no code line loads it")
        qa4a["blockers"] += 1
    elif len(hit_lines) == 0:
        print(f"[BLOCKER] data_source: '{expected_data_source}' does not appear anywhere in {script_path.name}")
        qa4a["blockers"] += 1
    elif "data/raw/" in code_text and "data/processed/" not in code_text:
        print(f"[WARNING] data_source: '{expected_data_source}' found on line(s) {hit_lines}, but the script reads data/raw/ and never data/processed/")
        qa4a["warnings"] += 1
    else:
        print(f"[PASS] data_source: '{expected_data_source}' found on {len(hit_lines)} non-comment line(s) of {script_path.name} (first: line {hit_lines[0]})")
        qa4a["passed"] += 1

# --- Validate: aggregation ---
# INTENT: Recompute one group's aggregate from the source frame and compare to the output.
# REASONING: The old guard `... and source_val != 0` short-circuited, so a zero source with
#            a nonzero result PASSED. Zero source now has explicit branches, and the
#            function is dispatched rather than assumed to be a sum.
# ASSUMES: source_df is the pre-analysis frame; the sampled group is the first non-null
#          group value in sort order, so the spot-check is deterministic across runs.
print("\nAggregation Spot-Check:")
agg_spec = plan_spec.get("aggregation")
if not_applicable.get("aggregation"):
    print(f"[SKIPPED] aggregation: {not_applicable['aggregation']}")
    qa4a["skipped"] += 1
elif "aggregation" in not_applicable:
    print("[NOT VERIFIED] aggregation: declared not_applicable with an empty reason string")
    qa4a["not_verified"] += 1
elif agg_spec is None:
    print("[NOT VERIFIED] aggregation: plan_spec has no 'aggregation' entry — declare not_applicable if this script aggregates nothing")
    qa4a["not_verified"] += 1
else:
    group_col = agg_spec.get("group_by")
    agg_col = agg_spec.get("column")
    agg_func = agg_spec.get("function", "sum")
    if agg_func not in KNOWN_AGG_FUNCS:
        print(f"[BLOCKER] aggregation: unrecognized function {agg_func!r} (known: {list(KNOWN_AGG_FUNCS)})")
        qa4a["blockers"] += 1
    elif group_col not in df.columns or agg_col not in df.columns or \
            group_col not in source_df.columns or agg_col not in source_df.columns:
        print(f"[BLOCKER] aggregation: '{group_col}' / '{agg_col}' are not present in both df and source_df")
        qa4a["blockers"] += 1
    else:
        groups = df[group_col].drop_nulls().unique().sort()
        if len(groups) == 0:
            print(f"[NOT VERIFIED] aggregation: '{group_col}' has no non-null values — no group to spot-check")
            qa4a["not_verified"] += 1
        else:
            sample_group = groups[0]
            src = source_df.filter(pl.col(group_col) == sample_group)
            out = df.filter(pl.col(group_col) == sample_group)
            if agg_func == "sum":
                source_val, result_val = src[agg_col].sum(), out[agg_col].sum()
            elif agg_func == "mean":
                source_val, result_val = src[agg_col].mean(), out[agg_col].mean()
            elif agg_func == "count":
                source_val, result_val = float(len(src)), float(out[agg_col].sum())
            elif agg_func == "median":
                source_val, result_val = src[agg_col].median(), out[agg_col].median()
            elif agg_func == "min":
                source_val, result_val = src[agg_col].min(), out[agg_col].min()
            else:  # max
                source_val, result_val = src[agg_col].max(), out[agg_col].max()
            if source_val is None or result_val is None:
                print(f"[NOT VERIFIED] aggregation '{agg_func}' on '{agg_col}' (group {sample_group!r}): source or result is null — comparison undefined")
                qa4a["not_verified"] += 1
            elif source_val == 0 and result_val != 0:
                print(f"[BLOCKER] aggregation '{agg_func}' on '{agg_col}' (group {sample_group!r}): source=0, result={result_val} — nonzero result from a zero source")
                qa4a["blockers"] += 1
            elif source_val == 0:
                print(f"[PASS] aggregation '{agg_func}' on '{agg_col}' (group {sample_group!r}): source=0 == result=0")
                qa4a["passed"] += 1
            elif abs(source_val - result_val) > 0.01 * abs(source_val):
                print(f"[BLOCKER] aggregation '{agg_func}' on '{agg_col}' (group {sample_group!r}): source={source_val}, result={result_val}, diff={abs(source_val - result_val)} > 1% tolerance")
                qa4a["blockers"] += 1
            else:
                print(f"[PASS] aggregation '{agg_func}' on '{agg_col}' (group {sample_group!r}): source={source_val} == result={result_val} within 1% ({abs(source_val - result_val)})")
                qa4a["passed"] += 1

# --- Validate: model_convergence ---
# INTENT: Confirm the estimator reported convergence.
# REASONING: `None is False` is False, so an absent 'converged' key fell to the else branch
#            and printed "Model converged successfully" on no evidence whatsoever. Absence
#            and non-boolean values are now NOT VERIFIED, and a PASS names the flag's source.
# ASSUMES: 'converged' is a real boolean written by the estimator, not a hand-set string.
print("\nModel Convergence Check:")
model_results = plan_spec.get("model_results")
if not_applicable.get("model_convergence"):
    print(f"[SKIPPED] model_convergence: {not_applicable['model_convergence']}")
    qa4a["skipped"] += 1
elif "model_convergence" in not_applicable:
    print("[NOT VERIFIED] model_convergence: declared not_applicable with an empty reason string")
    qa4a["not_verified"] += 1
elif model_results is None:
    print("[NOT VERIFIED] model_convergence: plan_spec has no 'model_results' — declare not_applicable if this script estimates no model")
    qa4a["not_verified"] += 1
elif not isinstance(model_results, dict):
    print(f"[NOT VERIFIED] model_convergence: plan_spec['model_results'] is {type(model_results).__name__}, not a mapping")
    qa4a["not_verified"] += 1
elif "converged" not in model_results:
    print("[NOT VERIFIED] model_convergence: model_results has no 'converged' key — no convergence evidence exists")
    qa4a["not_verified"] += 1
elif not isinstance(model_results["converged"], bool):
    print(f"[NOT VERIFIED] model_convergence: 'converged' is {model_results['converged']!r} ({type(model_results['converged']).__name__}), not a boolean")
    qa4a["not_verified"] += 1
elif model_results["converged"] is False and not model_results.get("convergence_documented"):
    print("[BLOCKER] model_convergence: converged=False and convergence_documented is not set")
    qa4a["blockers"] += 1
elif model_results["converged"] is False:
    print("[WARNING] model_convergence: converged=False, documented in the script")
    qa4a["warnings"] += 1
else:
    print(f"[PASS] model_convergence: converged=True as reported by {model_results.get('estimator', 'plan_spec[model_results]')}")
    qa4a["passed"] += 1

# --- Validate: assumptions ---
# INTENT: Confirm each declared model assumption was actually tested, and the result recorded.
# REASONING: `violated` defaulted to False, so an assumption with only `checked: True` and
#            no test result printed "holds". A PASS now requires a named test/statistic;
#            without one there is no evidence, only a self-report.
# ASSUMES: Each assumption dict may carry 'test' (or 'evidence') naming what was run.
print("\nAssumption Validation:")
assumptions = plan_spec.get("assumptions")
if not_applicable.get("assumptions"):
    print(f"[SKIPPED] assumptions: {not_applicable['assumptions']}")
    qa4a["skipped"] += 1
elif "assumptions" in not_applicable:
    print("[NOT VERIFIED] assumptions: declared not_applicable with an empty reason string")
    qa4a["not_verified"] += 1
elif assumptions is None or len(assumptions) == 0:
    print("[NOT VERIFIED] assumptions: plan_spec['assumptions'] is missing or empty — no assumptions declared to test")
    qa4a["not_verified"] += 1
else:
    for assumption in assumptions:
        name = assumption.get("name", "<unnamed>")
        checked = assumption.get("checked")
        violated = assumption.get("violated")
        discussed = assumption.get("discussed", False)
        evidence = assumption.get("test") or assumption.get("evidence")
        if not isinstance(checked, bool):
            print(f"[NOT VERIFIED] assumptions '{name}': 'checked' is {checked!r}, not a boolean")
            qa4a["not_verified"] += 1
        elif checked is False:
            print(f"[WARNING] assumptions '{name}': checked=False — assumption was never tested")
            qa4a["warnings"] += 1
        elif not isinstance(violated, bool):
            print(f"[NOT VERIFIED] assumptions '{name}': checked=True but 'violated' is {violated!r}, not a boolean — no test result recorded")
            qa4a["not_verified"] += 1
        elif violated and not discussed:
            print(f"[BLOCKER] assumptions '{name}': violated=True and discussed=False")
            qa4a["blockers"] += 1
        elif violated:
            print(f"[WARNING] assumptions '{name}': violated=True, discussed in the script (test: {evidence or 'unnamed'})")
            qa4a["warnings"] += 1
        elif evidence is None or len(str(evidence).strip()) == 0:
            print(f"[NOT VERIFIED] assumptions '{name}': reported as checked and not violated, but no test or statistic is named — self-report only")
            qa4a["not_verified"] += 1
        else:
            print(f"[PASS] assumptions '{name}': checked=True, violated=False per {evidence}")
            qa4a["passed"] += 1

# --- Validate: robustness ---
# INTENT: Confirm the primary and alternative specifications agree in direction.
# REASONING: `if primary_sign and alt_sign and ...` treated absent signs AND a legitimate
#            sign of 0 as falsy, so both fell to the PASS branch. Both signs must now be
#            present and in the documented encoding, and 0 is a real, comparable value.
# ASSUMES: Signs are encoded as -1 / 0 / +1; magnitudes, when supplied, are point estimates.
print("\nRobustness Consistency:")
robustness_checks = plan_spec.get("robustness_checks")
if not_applicable.get("robustness"):
    print(f"[SKIPPED] robustness: {not_applicable['robustness']}")
    qa4a["skipped"] += 1
elif "robustness" in not_applicable:
    print("[NOT VERIFIED] robustness: declared not_applicable with an empty reason string")
    qa4a["not_verified"] += 1
elif robustness_checks is None or len(robustness_checks) == 0:
    print("[NOT VERIFIED] robustness: plan_spec['robustness_checks'] is missing or empty — no alternative specifications declared")
    qa4a["not_verified"] += 1
else:
    for rob_check in robustness_checks:
        name = rob_check.get("name", "<unnamed>")
        primary_sign = rob_check.get("primary_sign")
        alt_sign = rob_check.get("alt_sign")
        primary_est = rob_check.get("primary_estimate")
        alt_est = rob_check.get("alt_estimate")
        mags = f", estimates primary={primary_est}, alt={alt_est}" if primary_est is not None or alt_est is not None else ""
        absent = [k for k, v in (("primary_sign", primary_sign), ("alt_sign", alt_sign)) if v is None]
        bad = [k for k, v in (("primary_sign", primary_sign), ("alt_sign", alt_sign))
               if v is not None and (isinstance(v, bool) or v not in KNOWN_SIGNS)]
        if absent:
            print(f"[NOT VERIFIED] robustness '{name}': {absent} absent — direction agreement untestable")
            qa4a["not_verified"] += 1
        elif bad:
            print(f"[BLOCKER] robustness '{name}': {bad} outside the documented sign encoding {list(KNOWN_SIGNS)} (primary={primary_sign!r}, alt={alt_sign!r})")
            qa4a["blockers"] += 1
        elif primary_sign != 0 and alt_sign != 0 and primary_sign != alt_sign:
            print(f"[BLOCKER] robustness '{name}': sign reversal — primary={primary_sign}, alt={alt_sign}{mags}")
            qa4a["blockers"] += 1
        elif primary_sign != alt_sign:
            print(f"[WARNING] robustness '{name}': direction changes to/from null — primary={primary_sign}, alt={alt_sign}{mags}")
            qa4a["warnings"] += 1
        else:
            print(f"[PASS] robustness '{name}': primary={primary_sign} == alt={alt_sign}{mags}")
            qa4a["passed"] += 1

# --- Data Profiling (for cra2+ decision) ---
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)
print(f"\nFirst 10 rows:\n{df.head(10)}")
print(f"\nDescriptive statistics:\n{df.describe()}")

# --- Verdict ---
# INTENT: Derive the QA4a verdict from the counters rather than asserting it.
print(f"\nChecks: {qa4a['passed']} passed, {qa4a['warnings']} warnings, {qa4a['blockers']} blockers, "
      f"{qa4a['not_verified']} not verified, {qa4a['skipped']} skipped, {qa4a['info']} info")
if qa4a["blockers"] > 0:
    qa4a_result = "BLOCKER"
elif qa4a["warnings"] > 0 or qa4a["not_verified"] > 0:
    qa4a_result = "WARNING"
elif qa4a["passed"] == 0:
    qa4a_result = "WARNING"  # nothing was actually verified
else:
    qa4a_result = "PASSED"
print(f"QA4a RESULT: {qa4a_result}")
print("=" * 60)
```

### QA4a cra1 Script Template — R

```r
library(dplyr)
library(arrow)

# --- Config ---
# INTENT: Declare which QA4a checks legitimately do not apply to this script.
# ASSUMES: Names are the documented QA4a keys; each element is a non-empty reason string.
#          plan_spec is indexed with [[ ]] throughout: `$` partial-matches, so
#          list(converged_flag = FALSE)$converged silently binds the wrong field.
not_applicable <- list()  # e.g. list(model_convergence = "descriptive script - no model estimated")

# INTENT: Count every outcome so the QA4a verdict is derived from what actually ran.
qa4a <- c(passed = 0L, warnings = 0L, blockers = 0L, not_verified = 0L, skipped = 0L, info = 0L)

KNOWN_AGG_FUNCS <- c("sum", "mean", "count", "median", "min", "max")
KNOWN_SIGNS <- c(-1, 0, 1)  # documented sign encoding: negative / null / positive

cat("\n")
cat(strrep("=", 60), "\n")
cat("QA4a: POST-ANALYSIS STATISTICAL VALIDITY\n")
cat(strrep("=", 60), "\n")

# --- Validate: data_source ---
# INTENT: Confirm the analysed script actually loads the dataset the Plan names.
# REASONING: grepl("", x) is TRUE for every x, so an empty data_source passed
#            unconditionally. Comments are stripped before matching because a path
#            mentioned only in a comment is documentation, not a load.
# ASSUMES: `#` starts a comment; a `#` inside a string literal truncates that line for
#          matching, which can only make this check stricter, never laxer.
cat("\nData Source Check:\n")
expected_data_source <- plan_spec[["data_source"]]
script_path <- script_spec[["script_path"]]
na_reason <- if ("data_source" %in% names(not_applicable)) not_applicable[["data_source"]] else NULL
if (!is.null(na_reason) && nzchar(na_reason)) {
  cat(sprintf("[SKIPPED] data_source: %s\n", na_reason))
  qa4a["skipped"] <- qa4a["skipped"] + 1L
} else if ("data_source" %in% names(not_applicable)) {
  cat("[NOT VERIFIED] data_source: declared not_applicable with an empty reason string\n")
  qa4a["not_verified"] <- qa4a["not_verified"] + 1L
} else if (is.null(expected_data_source) || !nzchar(trimws(expected_data_source))) {
  cat("[NOT VERIFIED] data_source: plan_spec[['data_source']] is missing or empty - no path to search for\n")
  qa4a["not_verified"] <- qa4a["not_verified"] + 1L
} else if (is.null(script_path) || !file.exists(script_path)) {
  cat(sprintf("[NOT VERIFIED] data_source: script_spec[['script_path']] (%s) does not exist - cannot inspect\n",
              if (is.null(script_path)) "NULL" else script_path))
  qa4a["not_verified"] <- qa4a["not_verified"] + 1L
} else {
  raw_lines <- readLines(script_path, warn = FALSE)
  code_lines <- sub("#.*$", "", raw_lines)
  code_text <- paste(code_lines, collapse = "\n")
  hit_lines <- which(grepl(expected_data_source, code_lines, fixed = TRUE))
  in_raw <- any(grepl(expected_data_source, raw_lines, fixed = TRUE))
  if (length(hit_lines) == 0 && in_raw) {
    cat(sprintf("[BLOCKER] data_source: '%s' appears only in comments of %s - no code line loads it\n",
                expected_data_source, basename(script_path)))
    qa4a["blockers"] <- qa4a["blockers"] + 1L
  } else if (length(hit_lines) == 0) {
    cat(sprintf("[BLOCKER] data_source: '%s' does not appear anywhere in %s\n",
                expected_data_source, basename(script_path)))
    qa4a["blockers"] <- qa4a["blockers"] + 1L
  } else if (grepl("data/raw/", code_text, fixed = TRUE) && !grepl("data/processed/", code_text, fixed = TRUE)) {
    cat(sprintf("[WARNING] data_source: '%s' found on line(s) %s, but the script reads data/raw/ and never data/processed/\n",
                expected_data_source, paste(hit_lines, collapse = ", ")))
    qa4a["warnings"] <- qa4a["warnings"] + 1L
  } else {
    cat(sprintf("[PASS] data_source: '%s' found on %d non-comment line(s) of %s (first: line %d)\n",
                expected_data_source, length(hit_lines), basename(script_path), hit_lines[1]))
    qa4a["passed"] <- qa4a["passed"] + 1L
  }
}

# --- Validate: aggregation ---
# INTENT: Recompute one group's aggregate from source_df and compare it to the output.
# REASONING: The old guard `&& source_val != 0` short-circuited, so a zero source with a
#            nonzero result PASSED. Zero source now has explicit branches, and the
#            function is dispatched rather than assumed to be a sum.
# ASSUMES: The sampled group is the first non-NA group value in sort order (deterministic).
cat("\nAggregation Spot-Check:\n")
agg_spec <- plan_spec[["aggregation"]]
na_reason <- if ("aggregation" %in% names(not_applicable)) not_applicable[["aggregation"]] else NULL
if (!is.null(na_reason) && nzchar(na_reason)) {
  cat(sprintf("[SKIPPED] aggregation: %s\n", na_reason))
  qa4a["skipped"] <- qa4a["skipped"] + 1L
} else if ("aggregation" %in% names(not_applicable)) {
  cat("[NOT VERIFIED] aggregation: declared not_applicable with an empty reason string\n")
  qa4a["not_verified"] <- qa4a["not_verified"] + 1L
} else if (is.null(agg_spec)) {
  cat("[NOT VERIFIED] aggregation: plan_spec has no 'aggregation' entry - declare not_applicable if this script aggregates nothing\n")
  qa4a["not_verified"] <- qa4a["not_verified"] + 1L
} else {
  group_col <- agg_spec[["group_by"]]
  agg_col <- agg_spec[["column"]]
  agg_func <- agg_spec[["function"]]
  if (is.null(agg_func)) agg_func <- "sum"
  if (!agg_func %in% KNOWN_AGG_FUNCS) {
    cat(sprintf("[BLOCKER] aggregation: unrecognized function '%s' (known: %s)\n",
                as.character(agg_func), paste(KNOWN_AGG_FUNCS, collapse = ", ")))
    qa4a["blockers"] <- qa4a["blockers"] + 1L
  } else if (is.null(group_col) || is.null(agg_col) ||
             !all(c(group_col, agg_col) %in% names(df)) ||
             !all(c(group_col, agg_col) %in% names(source_df))) {
    cat("[BLOCKER] aggregation: group_by/column named in plan_spec are absent from df or source_df\n")
    qa4a["blockers"] <- qa4a["blockers"] + 1L
  } else {
    groups <- sort(unique(df[[group_col]][!is.na(df[[group_col]])]))
    if (length(groups) == 0) {
      cat(sprintf("[NOT VERIFIED] aggregation: '%s' has no non-NA values - no group to spot-check\n", group_col))
      qa4a["not_verified"] <- qa4a["not_verified"] + 1L
    } else {
      sample_group <- groups[1]
      src_vals <- source_df[[agg_col]][source_df[[group_col]] == sample_group]
      out_vals <- df[[agg_col]][df[[group_col]] == sample_group]
      src_vals <- src_vals[!is.na(src_vals)]
      out_vals <- out_vals[!is.na(out_vals)]
      if (agg_func == "count") {
        source_val <- length(src_vals)
        result_val <- if (length(out_vals) > 0) sum(out_vals) else NA_real_
      } else if (length(src_vals) == 0 || length(out_vals) == 0) {
        source_val <- NA_real_; result_val <- NA_real_
      } else if (agg_func == "sum") {
        source_val <- sum(src_vals); result_val <- sum(out_vals)
      } else if (agg_func == "mean") {
        source_val <- mean(src_vals); result_val <- mean(out_vals)
      } else if (agg_func == "median") {
        source_val <- median(src_vals); result_val <- median(out_vals)
      } else if (agg_func == "min") {
        source_val <- min(src_vals); result_val <- min(out_vals)
      } else {
        source_val <- max(src_vals); result_val <- max(out_vals)
      }
      if (is.na(source_val) || is.na(result_val)) {
        cat(sprintf("[NOT VERIFIED] aggregation '%s' on '%s' (group %s): source or result is NA - comparison undefined\n",
                    agg_func, agg_col, as.character(sample_group)))
        qa4a["not_verified"] <- qa4a["not_verified"] + 1L
      } else if (source_val == 0 && result_val != 0) {
        cat(sprintf("[BLOCKER] aggregation '%s' on '%s' (group %s): source=0, result=%s - nonzero result from a zero source\n",
                    agg_func, agg_col, as.character(sample_group), format(result_val)))
        qa4a["blockers"] <- qa4a["blockers"] + 1L
      } else if (source_val == 0) {
        cat(sprintf("[PASS] aggregation '%s' on '%s' (group %s): source=0 == result=0\n",
                    agg_func, agg_col, as.character(sample_group)))
        qa4a["passed"] <- qa4a["passed"] + 1L
      } else if (abs(source_val - result_val) > 0.01 * abs(source_val)) {
        cat(sprintf("[BLOCKER] aggregation '%s' on '%s' (group %s): source=%s, result=%s, diff=%s > 1%% tolerance\n",
                    agg_func, agg_col, as.character(sample_group), format(source_val),
                    format(result_val), format(abs(source_val - result_val))))
        qa4a["blockers"] <- qa4a["blockers"] + 1L
      } else {
        cat(sprintf("[PASS] aggregation '%s' on '%s' (group %s): source=%s == result=%s within 1%% (%s)\n",
                    agg_func, agg_col, as.character(sample_group), format(source_val),
                    format(result_val), format(abs(source_val - result_val))))
        qa4a["passed"] <- qa4a["passed"] + 1L
      }
    }
  }
}

# --- Validate: model_convergence ---
# INTENT: Confirm the estimator reported convergence.
# REASONING: identical(NULL, FALSE) is FALSE, so an absent 'converged' field fell to the
#            else branch and printed "Model converged successfully" on no evidence. Absence
#            and non-logical values are now NOT VERIFIED, and a PASS names the flag's source.
# ASSUMES: 'converged' is a real logical written by the estimator, not a string.
cat("\nModel Convergence Check:\n")
model_results <- plan_spec[["model_results"]]
converged <- if (is.list(model_results)) model_results[["converged"]] else NULL
na_reason <- if ("model_convergence" %in% names(not_applicable)) not_applicable[["model_convergence"]] else NULL
if (!is.null(na_reason) && nzchar(na_reason)) {
  cat(sprintf("[SKIPPED] model_convergence: %s\n", na_reason))
  qa4a["skipped"] <- qa4a["skipped"] + 1L
} else if ("model_convergence" %in% names(not_applicable)) {
  cat("[NOT VERIFIED] model_convergence: declared not_applicable with an empty reason string\n")
  qa4a["not_verified"] <- qa4a["not_verified"] + 1L
} else if (is.null(model_results)) {
  cat("[NOT VERIFIED] model_convergence: plan_spec has no 'model_results' - declare not_applicable if this script estimates no model\n")
  qa4a["not_verified"] <- qa4a["not_verified"] + 1L
} else if (!is.list(model_results)) {
  cat(sprintf("[NOT VERIFIED] model_convergence: plan_spec[['model_results']] is %s, not a list\n", class(model_results)[1]))
  qa4a["not_verified"] <- qa4a["not_verified"] + 1L
} else if (is.null(converged)) {
  cat("[NOT VERIFIED] model_convergence: model_results has no 'converged' element - no convergence evidence exists\n")
  qa4a["not_verified"] <- qa4a["not_verified"] + 1L
} else if (!is.logical(converged) || length(converged) != 1 || is.na(converged)) {
  cat(sprintf("[NOT VERIFIED] model_convergence: 'converged' is %s (%s), not a single non-NA logical\n",
              paste(as.character(converged), collapse = ", "), class(converged)[1]))
  qa4a["not_verified"] <- qa4a["not_verified"] + 1L
} else if (isFALSE(converged) && !isTRUE(model_results[["convergence_documented"]])) {
  cat("[BLOCKER] model_convergence: converged=FALSE and convergence_documented is not set\n")
  qa4a["blockers"] <- qa4a["blockers"] + 1L
} else if (isFALSE(converged)) {
  cat("[WARNING] model_convergence: converged=FALSE, documented in the script\n")
  qa4a["warnings"] <- qa4a["warnings"] + 1L
} else {
  estimator <- model_results[["estimator"]]
  if (is.null(estimator)) estimator <- "plan_spec[['model_results']]"
  cat(sprintf("[PASS] model_convergence: converged=TRUE as reported by %s\n", estimator))
  qa4a["passed"] <- qa4a["passed"] + 1L
}

# --- Validate: assumptions ---
# INTENT: Confirm each declared model assumption was tested and the result recorded.
# REASONING: isTRUE(NULL) is FALSE, so `violated` defaulting to FALSE meant an assumption
#            with only checked=TRUE printed "holds". A PASS now requires a named test.
# ASSUMES: Each assumption list may carry 'test' (or 'evidence') naming what was run.
cat("\nAssumption Validation:\n")
assumptions <- plan_spec[["assumptions"]]
na_reason <- if ("assumptions" %in% names(not_applicable)) not_applicable[["assumptions"]] else NULL
if (!is.null(na_reason) && nzchar(na_reason)) {
  cat(sprintf("[SKIPPED] assumptions: %s\n", na_reason))
  qa4a["skipped"] <- qa4a["skipped"] + 1L
} else if ("assumptions" %in% names(not_applicable)) {
  cat("[NOT VERIFIED] assumptions: declared not_applicable with an empty reason string\n")
  qa4a["not_verified"] <- qa4a["not_verified"] + 1L
} else if (is.null(assumptions) || length(assumptions) == 0) {
  cat("[NOT VERIFIED] assumptions: plan_spec[['assumptions']] is missing or empty - no assumptions declared to test\n")
  qa4a["not_verified"] <- qa4a["not_verified"] + 1L
} else {
  for (assumption in assumptions) {
    name <- assumption[["name"]]
    if (is.null(name)) name <- "<unnamed>"
    checked <- assumption[["checked"]]
    violated <- assumption[["violated"]]
    discussed <- isTRUE(assumption[["discussed"]])
    evidence <- assumption[["test"]]
    if (is.null(evidence)) evidence <- assumption[["evidence"]]
    if (!is.logical(checked) || length(checked) != 1 || is.na(checked)) {
      cat(sprintf("[NOT VERIFIED] assumptions '%s': 'checked' is not a single non-NA logical\n", name))
      qa4a["not_verified"] <- qa4a["not_verified"] + 1L
    } else if (isFALSE(checked)) {
      cat(sprintf("[WARNING] assumptions '%s': checked=FALSE - assumption was never tested\n", name))
      qa4a["warnings"] <- qa4a["warnings"] + 1L
    } else if (!is.logical(violated) || length(violated) != 1 || is.na(violated)) {
      cat(sprintf("[NOT VERIFIED] assumptions '%s': checked=TRUE but 'violated' is not a single non-NA logical - no test result recorded\n", name))
      qa4a["not_verified"] <- qa4a["not_verified"] + 1L
    } else if (isTRUE(violated) && !discussed) {
      cat(sprintf("[BLOCKER] assumptions '%s': violated=TRUE and discussed=FALSE\n", name))
      qa4a["blockers"] <- qa4a["blockers"] + 1L
    } else if (isTRUE(violated)) {
      cat(sprintf("[WARNING] assumptions '%s': violated=TRUE, discussed in the script (test: %s)\n",
                  name, if (is.null(evidence)) "unnamed" else evidence))
      qa4a["warnings"] <- qa4a["warnings"] + 1L
    } else if (is.null(evidence) || !nzchar(trimws(as.character(evidence)))) {
      cat(sprintf("[NOT VERIFIED] assumptions '%s': reported as checked and not violated, but no test or statistic is named - self-report only\n", name))
      qa4a["not_verified"] <- qa4a["not_verified"] + 1L
    } else {
      cat(sprintf("[PASS] assumptions '%s': checked=TRUE, violated=FALSE per %s\n", name, evidence))
      qa4a["passed"] <- qa4a["passed"] + 1L
    }
  }
}

# --- Validate: robustness ---
# INTENT: Confirm the primary and alternative specifications agree in direction.
# REASONING: !is.null() alone let an absent pair fall through to PASS, and NA signs aborted
#            the whole script at `if (NA)`. NA and absence are now handled before any
#            comparison, and 0 is a real, comparable sign value.
# ASSUMES: Signs are encoded as -1 / 0 / +1; magnitudes, when supplied, are point estimates.
cat("\nRobustness Consistency:\n")
robustness_checks <- plan_spec[["robustness_checks"]]
na_reason <- if ("robustness" %in% names(not_applicable)) not_applicable[["robustness"]] else NULL
if (!is.null(na_reason) && nzchar(na_reason)) {
  cat(sprintf("[SKIPPED] robustness: %s\n", na_reason))
  qa4a["skipped"] <- qa4a["skipped"] + 1L
} else if ("robustness" %in% names(not_applicable)) {
  cat("[NOT VERIFIED] robustness: declared not_applicable with an empty reason string\n")
  qa4a["not_verified"] <- qa4a["not_verified"] + 1L
} else if (is.null(robustness_checks) || length(robustness_checks) == 0) {
  cat("[NOT VERIFIED] robustness: plan_spec[['robustness_checks']] is missing or empty - no alternative specifications declared\n")
  qa4a["not_verified"] <- qa4a["not_verified"] + 1L
} else {
  for (rob_check in robustness_checks) {
    name <- rob_check[["name"]]
    if (is.null(name)) name <- "<unnamed>"
    primary_sign <- rob_check[["primary_sign"]]
    alt_sign <- rob_check[["alt_sign"]]
    primary_est <- rob_check[["primary_estimate"]]
    alt_est <- rob_check[["alt_estimate"]]
    mags <- if (!is.null(primary_est) || !is.null(alt_est)) {
      sprintf(", estimates primary=%s, alt=%s",
              if (is.null(primary_est)) "NA" else format(primary_est),
              if (is.null(alt_est)) "NA" else format(alt_est))
    } else ""
    p_missing <- is.null(primary_sign) || length(primary_sign) != 1 || is.na(primary_sign)
    a_missing <- is.null(alt_sign) || length(alt_sign) != 1 || is.na(alt_sign)
    if (p_missing || a_missing) {
      absent <- c(if (p_missing) "primary_sign", if (a_missing) "alt_sign")
      cat(sprintf("[NOT VERIFIED] robustness '%s': %s absent or NA - direction agreement untestable\n",
                  name, paste(absent, collapse = ", ")))
      qa4a["not_verified"] <- qa4a["not_verified"] + 1L
    } else if (!primary_sign %in% KNOWN_SIGNS || !alt_sign %in% KNOWN_SIGNS) {
      cat(sprintf("[BLOCKER] robustness '%s': signs outside the documented encoding (-1, 0, 1) - primary=%s, alt=%s\n",
                  name, as.character(primary_sign), as.character(alt_sign)))
      qa4a["blockers"] <- qa4a["blockers"] + 1L
    } else if (primary_sign != 0 && alt_sign != 0 && primary_sign != alt_sign) {
      cat(sprintf("[BLOCKER] robustness '%s': sign reversal - primary=%s, alt=%s%s\n",
                  name, as.character(primary_sign), as.character(alt_sign), mags))
      qa4a["blockers"] <- qa4a["blockers"] + 1L
    } else if (primary_sign != alt_sign) {
      cat(sprintf("[WARNING] robustness '%s': direction changes to/from null - primary=%s, alt=%s%s\n",
                  name, as.character(primary_sign), as.character(alt_sign), mags))
      qa4a["warnings"] <- qa4a["warnings"] + 1L
    } else {
      cat(sprintf("[PASS] robustness '%s': primary=%s == alt=%s%s\n",
                  name, as.character(primary_sign), as.character(alt_sign), mags))
      qa4a["passed"] <- qa4a["passed"] + 1L
    }
  }
}

# --- Data Profiling (for cra2+ decision) ---
cat("\n")
cat(strrep("=", 60), "\n")
cat("DATA PROFILING\n")
cat(strrep("=", 60), "\n")
cat("\nFirst 10 rows:\n")
print(head(df, 10))
cat("\nDescriptive statistics:\n")
print(summary(df))

# --- Verdict ---
# INTENT: Derive the QA4a verdict from the counters rather than asserting it.
cat(sprintf("\nChecks: %d passed, %d warnings, %d blockers, %d not verified, %d skipped, %d info\n",
            qa4a[["passed"]], qa4a[["warnings"]], qa4a[["blockers"]],
            qa4a[["not_verified"]], qa4a[["skipped"]], qa4a[["info"]]))
qa4a_result <- if (qa4a[["blockers"]] > 0) {
  "BLOCKER"
} else if (qa4a[["warnings"]] > 0 || qa4a[["not_verified"]] > 0) {
  "WARNING"
} else if (qa4a[["passed"]] == 0) {
  "WARNING"  # nothing was actually verified
} else {
  "PASSED"
}
cat(sprintf("QA4a RESULT: %s\n", qa4a_result))
cat(strrep("=", 60), "\n")
```

### QA4a Discretionary Checks

| Check | When to Add | What It Validates |
|-------|-------------|-------------------|
| Effect size plausibility | Regression/causal analysis | Estimated effects within domain-reasonable bounds |
| Sample size adequacy | Statistical tests | Sufficient N for claimed significance |
| Multiple comparison adjustment | Multiple hypotheses tested | p-values adjusted appropriately |
| Outlier influence | Regression analysis | Results not driven by a few extreme observations |
| **Concrete trace** | **Always (at minimum 5)** — see `.claude/agents/code-reviewer.md` § Five Lenses of Skeptical Review | **Pick one data point and verify its representation in the analysis output is accurate** |

**Creative check prompt:** Before writing your QA4a script, ask: *"If the script used the wrong column for a key calculation, or aggregated at the wrong level, how would the output differ from correct output?"* Design at least one check to catch that class of error.

### QA4a Iterative Investigation Triggers

Observations from cra1 that should trigger cra2+ investigation:

| cra1 Observation | Suggested cra2 Investigation |
|-----------------|---------------------------|
| Aggregated totals don't match source data sums | Trace: which group(s) account for the discrepancy? Is a filter being applied incorrectly? |
| Model coefficients have unexpected signs | Investigate: is there multicollinearity, omitted variable bias, or data coding error? |
| Effect sizes implausibly large or small | Profile: are outliers driving the result? Does winsorization change the conclusion? |
| Robustness check shows marginal consistency | Deeper analysis: how sensitive is the result to specification choices? |

---

## QA4b: Post-Analysis Visualization Quality

**Applies To:** Stage 8 scripts (visualization)

**Purpose:** Verify visualizations are complete, labeled, accessible, visually coherent, and publication-ready.

### Default Checks

| Check | What It Validates | BLOCKER If |
|-------|-------------------|------------|
| File existence | All planned figures created | Required figures missing |
| File size | Figures have content | File size < 10KB (likely empty) |
| Title/labels | All axes labeled with units, descriptive title | Missing titles or axis labels |
| Colorblind-safe palette | Accessible color scheme used | Color-only encoding without texture/shape |
| COVID period annotation | Years 2020-2022 flagged visually (if present) | COVID years present but not annotated |
| Legend clarity | Legend present if needed, labels interpretable | Legend missing when required |
| Resolution | Exported at appropriate DPI | DPI <150 for print-intended figures |
| Misleading scales | Y-axis starts at 0 for bar charts | Truncated axis distorts interpretation |

### QA4b crb1 Script Template

```python
from pathlib import Path
import re

# --- Config ---
# INTENT: Declare which QA4b checks legitimately do not apply to this script.
# ASSUMES: Keys are the documented QA4b keys (figures, axis_labels, title,
#          covid_annotation, resolution); each value is a NON-EMPTY reason string.
not_applicable = {}  # e.g. {"covid_annotation": "cross-sectional figure — no time axis"}

# INTENT: Count every outcome so the QA4b verdict is derived from what actually ran.
qa4b = {"passed": 0, "warnings": 0, "blockers": 0, "not_verified": 0, "skipped": 0, "info": 0}

COVID_YEARS = (2020, 2021, 2022)

print("\n" + "=" * 60)
print("QA4b: POST-ANALYSIS VISUALIZATION QUALITY")
print("=" * 60)

# --- Load: script text (shared by the text-pattern checks below) ---
# INTENT: Read the visualization script once; several checks inspect its text.
# ASSUMES: script_spec["script_path"] points at the script that produced the figures.
script_path = Path(script_spec["script_path"]) if script_spec.get("script_path") else None
script_text = script_path.read_text() if script_path is not None and script_path.exists() else None

# --- Validate: figures ---
# INTENT: Confirm every figure the task promised exists and is non-trivial in size.
# REASONING: An absent expected_figures list defaulted to [], so the loop never ran and the
#            verdict was PASSED with no figure inventory. An empty inventory is unverified,
#            not clean.
# ASSUMES: output_dir / "figures" is where the script writes; size < 10 KB implies empty.
print("\nFigure Existence and Size:")
expected_figures = viz_spec.get("expected_figures")
if not_applicable.get("figures"):
    print(f"[SKIPPED] figures: {not_applicable['figures']}")
    qa4b["skipped"] += 1
elif "figures" in not_applicable:
    print("[NOT VERIFIED] figures: declared not_applicable with an empty reason string")
    qa4b["not_verified"] += 1
elif expected_figures is None or len(expected_figures) == 0:
    print("[NOT VERIFIED] figures: viz_spec['expected_figures'] is missing or empty — no figure inventory to check against")
    qa4b["not_verified"] += 1
else:
    for fig_name in expected_figures:
        fig_path = output_dir / "figures" / fig_name
        if not fig_path.exists():
            print(f"[BLOCKER] figures '{fig_name}': not found at {fig_path}")
            qa4b["blockers"] += 1
            continue
        size_kb = fig_path.stat().st_size / 1024
        if size_kb < 10:
            print(f"[WARNING] figures '{fig_name}': {size_kb:.1f} KB — below the 10 KB non-empty threshold")
            qa4b["warnings"] += 1
        else:
            print(f"[PASS] figures '{fig_name}': exists, {size_kb:.1f} KB (>= 10 KB)")
            qa4b["passed"] += 1

# --- Validate: axis_labels (text pattern — weak evidence) ---
# INTENT: Look for axis-label calls in the script source.
# REASONING: This is a TEXT PATTERN over source code, not an inspection of the rendered
#            figure: a match inside a comment or a string literal counts, and labs(x="")
#            matches while labelling nothing. It therefore cannot carry a BLOCKER or a
#            PASS — a hit is INFO, a miss is WARNING, and the reviewer reads the PNG.
# ASSUMES: The script uses plotnine/ggplot2/matplotlib label idioms.
print("\nTitle/Label Check:")
if not_applicable.get("axis_labels"):
    print(f"[SKIPPED] axis_labels: {not_applicable['axis_labels']}")
    qa4b["skipped"] += 1
elif "axis_labels" in not_applicable:
    print("[NOT VERIFIED] axis_labels: declared not_applicable with an empty reason string")
    qa4b["not_verified"] += 1
elif script_text is None:
    print(f"[NOT VERIFIED] axis_labels: script at {script_path} is unreadable — no text to inspect")
    qa4b["not_verified"] += 1
else:
    has_xlabel = bool(re.search(r'(xlab|xlabel|labs\(.*x\s*=|axis_title_x)', script_text))
    has_ylabel = bool(re.search(r'(ylab|ylabel|labs\(.*y\s*=|axis_title_y)', script_text))
    if not has_xlabel or not has_ylabel:
        absent = [ax for ax, ok in (("x", has_xlabel), ("y", has_ylabel)) if not ok]
        print(f"[WARNING] axis_labels: no text pattern for {absent} axis label(s) in the script source — inspect the rendered figure via Read")
        qa4b["warnings"] += 1
    else:
        print("[INFO] axis_labels: text pattern for both x and y labels found in the script source (weak evidence — a comment or an empty label string also matches; confirm via Read)")
        qa4b["info"] += 1

# --- Validate: title (text pattern — weak evidence) ---
if not_applicable.get("title"):
    print(f"[SKIPPED] title: {not_applicable['title']}")
    qa4b["skipped"] += 1
elif "title" in not_applicable:
    print("[NOT VERIFIED] title: declared not_applicable with an empty reason string")
    qa4b["not_verified"] += 1
elif script_text is None:
    print(f"[NOT VERIFIED] title: script at {script_path} is unreadable — no text to inspect")
    qa4b["not_verified"] += 1
elif not bool(re.search(r'(ggtitle|title\s*=|labs\(.*title)', script_text)):
    print("[WARNING] title: no title text pattern found in the script source")
    qa4b["warnings"] += 1
else:
    print("[INFO] title: title text pattern found in the script source (weak evidence — confirm via Read)")
    qa4b["info"] += 1

# --- Validate: covid_annotation ---
# INTENT: If the plotted data actually spans 2020-2022, require a visual annotation.
# REASONING: The claim "no COVID years in data range" is a DATA FACT and was previously
#            read off a config default (`viz_spec.get("covid_years_present", False)`) — a
#            missing key asserted a property of the data with nothing inspected. It is now
#            computed from the plotted frame. The annotation half remains a text pattern,
#            so a hit is INFO rather than PASS.
# ASSUMES: df is the frame that was plotted and carries the year column.
print("\nCOVID Annotation Check:")
year_col = viz_spec.get("year_col", "year")
if not_applicable.get("covid_annotation"):
    print(f"[SKIPPED] covid_annotation: {not_applicable['covid_annotation']}")
    qa4b["skipped"] += 1
elif "covid_annotation" in not_applicable:
    print("[NOT VERIFIED] covid_annotation: declared not_applicable with an empty reason string")
    qa4b["not_verified"] += 1
elif year_col not in df.columns:
    print(f"[NOT VERIFIED] covid_annotation: year column '{year_col}' is not in the plotted frame — COVID-year presence not computable from the data")
    qa4b["not_verified"] += 1
else:
    years_present = set(df[year_col].drop_nulls().unique().to_list())
    overlap = sorted(set(COVID_YEARS) & years_present)
    if len(overlap) == 0:
        print(f"[PASS] covid_annotation: no COVID years in the plotted data (checked {list(COVID_YEARS)} against {len(years_present)} observed years) — annotation not required")
        qa4b["passed"] += 1
    elif script_text is None:
        print(f"[NOT VERIFIED] covid_annotation: COVID years {overlap} present in the data but the script is unreadable — annotation not checkable")
        qa4b["not_verified"] += 1
    elif not bool(re.search(r'(covid|pandemic|2020.*2022|annotate|vline|geom_rect)', script_text, re.IGNORECASE)):
        print(f"[BLOCKER] covid_annotation: COVID years {overlap} present in the plotted data and no annotation text pattern found in the script source")
        qa4b["blockers"] += 1
    else:
        print(f"[INFO] covid_annotation: COVID years {overlap} present and an annotation text pattern was found in the script source (weak evidence — confirm the annotation is on the figure via Read)")
        qa4b["info"] += 1

# --- Validate: resolution ---
# INTENT: Confirm an explicit export DPI adequate for print.
# ASSUMES: DPI is set literally in the script (dpi=300); a computed value is not detectable.
print("\nResolution Check:")
if not_applicable.get("resolution"):
    print(f"[SKIPPED] resolution: {not_applicable['resolution']}")
    qa4b["skipped"] += 1
elif "resolution" in not_applicable:
    print("[NOT VERIFIED] resolution: declared not_applicable with an empty reason string")
    qa4b["not_verified"] += 1
elif script_text is None:
    print(f"[NOT VERIFIED] resolution: script at {script_path} is unreadable — no text to inspect")
    qa4b["not_verified"] += 1
else:
    dpi_match = re.search(r'dpi\s*=\s*(\d+)', script_text)
    if dpi_match is None:
        print("[WARNING] resolution: no explicit 'dpi=' literal found in the script source")
        qa4b["warnings"] += 1
    elif int(dpi_match.group(1)) < 150:
        print(f"[WARNING] resolution: dpi={int(dpi_match.group(1))} declared in the script source — below the 150 print threshold")
        qa4b["warnings"] += 1
    else:
        print(f"[PASS] resolution: dpi={int(dpi_match.group(1))} declared in the script source (>= 150)")
        qa4b["passed"] += 1

# --- Data Profiling (for crb2+ decision) ---
print("\n" + "=" * 60)
print("FIGURES DIRECTORY LISTING")
print("=" * 60)
figures_dir = output_dir / "figures"
if figures_dir.exists():
    for f in sorted(figures_dir.iterdir()):
        print(f"  {f.name} ({f.stat().st_size / 1024:.1f} KB)")
else:
    print(f"  (no figures directory at {figures_dir})")

# --- Verdict ---
# INTENT: Derive the QA4b verdict from the counters rather than asserting it.
# REASONING: INFO lines are reported but do not count as verification, so a run whose only
#            positive signals are text-pattern INFO hits lands on WARNING, not PASSED.
print(f"\nChecks: {qa4b['passed']} passed, {qa4b['warnings']} warnings, {qa4b['blockers']} blockers, "
      f"{qa4b['not_verified']} not verified, {qa4b['skipped']} skipped, {qa4b['info']} info")
if qa4b["blockers"] > 0:
    qa4b_result = "BLOCKER"
elif qa4b["warnings"] > 0 or qa4b["not_verified"] > 0:
    qa4b_result = "WARNING"
elif qa4b["passed"] == 0:
    qa4b_result = "WARNING"  # nothing was actually verified
else:
    qa4b_result = "PASSED"
print(f"QA4b RESULT: {qa4b_result}")
print("=" * 60)
```

### QA4b crb1 Script Template — R

```r
# --- Config ---
# INTENT: Declare which QA4b checks legitimately do not apply to this script.
# ASSUMES: Names are the documented QA4b keys; each element is a non-empty reason string.
not_applicable <- list()  # e.g. list(covid_annotation = "cross-sectional figure - no time axis")

# INTENT: Count every outcome so the QA4b verdict is derived from what actually ran.
qa4b <- c(passed = 0L, warnings = 0L, blockers = 0L, not_verified = 0L, skipped = 0L, info = 0L)

COVID_YEARS <- c(2020, 2021, 2022)

cat("\n")
cat(strrep("=", 60), "\n")
cat("QA4b: POST-ANALYSIS VISUALIZATION QUALITY\n")
cat(strrep("=", 60), "\n")

# --- Load: script text (shared by the text-pattern checks below) ---
script_path <- script_spec[["script_path"]]
script_text <- if (!is.null(script_path) && file.exists(script_path)) {
  paste(readLines(script_path, warn = FALSE), collapse = "\n")
} else {
  NULL
}

# --- Validate: figures ---
# INTENT: Confirm every figure the task promised exists and is non-trivial in size.
# REASONING: An absent expected_figures list became character(0), so the loop never ran and
#            the verdict was PASSED with no figure inventory. An empty inventory is
#            unverified, not clean.
# ASSUMES: file.path(output_dir, "figures") is where the script writes; < 10 KB means empty.
cat("\nFigure Existence and Size:\n")
expected_figures <- viz_spec[["expected_figures"]]
na_reason <- if ("figures" %in% names(not_applicable)) not_applicable[["figures"]] else NULL
if (!is.null(na_reason) && nzchar(na_reason)) {
  cat(sprintf("[SKIPPED] figures: %s\n", na_reason))
  qa4b["skipped"] <- qa4b["skipped"] + 1L
} else if ("figures" %in% names(not_applicable)) {
  cat("[NOT VERIFIED] figures: declared not_applicable with an empty reason string\n")
  qa4b["not_verified"] <- qa4b["not_verified"] + 1L
} else if (is.null(expected_figures) || length(expected_figures) == 0) {
  cat("[NOT VERIFIED] figures: viz_spec[['expected_figures']] is missing or empty - no figure inventory to check against\n")
  qa4b["not_verified"] <- qa4b["not_verified"] + 1L
} else {
  for (fig_name in expected_figures) {
    fig_path <- file.path(output_dir, "figures", fig_name)
    if (!file.exists(fig_path)) {
      cat(sprintf("[BLOCKER] figures '%s': not found at %s\n", fig_name, fig_path))
      qa4b["blockers"] <- qa4b["blockers"] + 1L
      next
    }
    size_kb <- file.info(fig_path)$size / 1024
    if (size_kb < 10) {
      cat(sprintf("[WARNING] figures '%s': %.1f KB - below the 10 KB non-empty threshold\n", fig_name, size_kb))
      qa4b["warnings"] <- qa4b["warnings"] + 1L
    } else {
      cat(sprintf("[PASS] figures '%s': exists, %.1f KB (>= 10 KB)\n", fig_name, size_kb))
      qa4b["passed"] <- qa4b["passed"] + 1L
    }
  }
}

# --- Validate: axis_labels (text pattern - weak evidence) ---
# INTENT: Look for axis-label calls in the script source.
# REASONING: This is a TEXT PATTERN over source code, not an inspection of the rendered
#            figure, so it cannot carry a BLOCKER or a PASS. scale_x/scale_y are dropped
#            from the accepting pattern: scale_x_continuous() with no name= argument sets
#            no label, yet it made the old pattern match and report labels present.
# ASSUMES: The script uses ggplot2 label idioms (xlab/ylab/labs).
cat("\nTitle/Label Check:\n")
na_reason <- if ("axis_labels" %in% names(not_applicable)) not_applicable[["axis_labels"]] else NULL
if (!is.null(na_reason) && nzchar(na_reason)) {
  cat(sprintf("[SKIPPED] axis_labels: %s\n", na_reason))
  qa4b["skipped"] <- qa4b["skipped"] + 1L
} else if ("axis_labels" %in% names(not_applicable)) {
  cat("[NOT VERIFIED] axis_labels: declared not_applicable with an empty reason string\n")
  qa4b["not_verified"] <- qa4b["not_verified"] + 1L
} else if (is.null(script_text)) {
  cat("[NOT VERIFIED] axis_labels: script is unreadable - no text to inspect\n")
  qa4b["not_verified"] <- qa4b["not_verified"] + 1L
} else {
  has_xlabel <- grepl("(xlab|labs\\(.*x\\s*=)", script_text)
  has_ylabel <- grepl("(ylab|labs\\(.*y\\s*=)", script_text)
  if (!has_xlabel || !has_ylabel) {
    absent <- c(if (!has_xlabel) "x", if (!has_ylabel) "y")
    cat(sprintf("[WARNING] axis_labels: no text pattern for %s axis label(s) in the script source - inspect the rendered figure via Read\n",
                paste(absent, collapse = ", ")))
    qa4b["warnings"] <- qa4b["warnings"] + 1L
  } else {
    cat("[INFO] axis_labels: text pattern for both x and y labels found in the script source (weak evidence - a comment or an empty label string also matches; confirm via Read)\n")
    qa4b["info"] <- qa4b["info"] + 1L
  }
}

# --- Validate: title (text pattern - weak evidence) ---
na_reason <- if ("title" %in% names(not_applicable)) not_applicable[["title"]] else NULL
if (!is.null(na_reason) && nzchar(na_reason)) {
  cat(sprintf("[SKIPPED] title: %s\n", na_reason))
  qa4b["skipped"] <- qa4b["skipped"] + 1L
} else if ("title" %in% names(not_applicable)) {
  cat("[NOT VERIFIED] title: declared not_applicable with an empty reason string\n")
  qa4b["not_verified"] <- qa4b["not_verified"] + 1L
} else if (is.null(script_text)) {
  cat("[NOT VERIFIED] title: script is unreadable - no text to inspect\n")
  qa4b["not_verified"] <- qa4b["not_verified"] + 1L
} else if (!grepl("(ggtitle|labs\\(.*title)", script_text)) {
  cat("[WARNING] title: no title text pattern found in the script source\n")
  qa4b["warnings"] <- qa4b["warnings"] + 1L
} else {
  cat("[INFO] title: title text pattern found in the script source (weak evidence - confirm via Read)\n")
  qa4b["info"] <- qa4b["info"] + 1L
}

# --- Validate: covid_annotation ---
# INTENT: If the plotted data actually spans 2020-2022, require a visual annotation.
# REASONING: "No COVID years in data range" is a DATA FACT and was read off a config
#            default (isTRUE(NULL) is FALSE), asserting a property of the data with nothing
#            inspected. It is now computed from the plotted frame; the annotation half
#            stays a text pattern, so a hit is INFO rather than PASS.
# ASSUMES: df is the frame that was plotted and carries the year column.
cat("\nCOVID Annotation Check:\n")
year_col <- viz_spec[["year_col"]]
if (is.null(year_col)) year_col <- "year"
na_reason <- if ("covid_annotation" %in% names(not_applicable)) not_applicable[["covid_annotation"]] else NULL
if (!is.null(na_reason) && nzchar(na_reason)) {
  cat(sprintf("[SKIPPED] covid_annotation: %s\n", na_reason))
  qa4b["skipped"] <- qa4b["skipped"] + 1L
} else if ("covid_annotation" %in% names(not_applicable)) {
  cat("[NOT VERIFIED] covid_annotation: declared not_applicable with an empty reason string\n")
  qa4b["not_verified"] <- qa4b["not_verified"] + 1L
} else if (!year_col %in% names(df)) {
  cat(sprintf("[NOT VERIFIED] covid_annotation: year column '%s' is not in the plotted frame - COVID-year presence not computable from the data\n", year_col))
  qa4b["not_verified"] <- qa4b["not_verified"] + 1L
} else {
  years_present <- unique(df[[year_col]][!is.na(df[[year_col]])])
  overlap <- sort(intersect(COVID_YEARS, years_present))
  if (length(overlap) == 0) {
    cat(sprintf("[PASS] covid_annotation: no COVID years in the plotted data (checked 2020, 2021, 2022 against %d observed years) - annotation not required\n",
                length(years_present)))
    qa4b["passed"] <- qa4b["passed"] + 1L
  } else if (is.null(script_text)) {
    cat(sprintf("[NOT VERIFIED] covid_annotation: COVID years %s present in the data but the script is unreadable - annotation not checkable\n",
                paste(overlap, collapse = ", ")))
    qa4b["not_verified"] <- qa4b["not_verified"] + 1L
  } else if (!grepl("(covid|pandemic|2020.*2022|annotate|geom_vline|geom_rect)", script_text, ignore.case = TRUE)) {
    cat(sprintf("[BLOCKER] covid_annotation: COVID years %s present in the plotted data and no annotation text pattern found in the script source\n",
                paste(overlap, collapse = ", ")))
    qa4b["blockers"] <- qa4b["blockers"] + 1L
  } else {
    cat(sprintf("[INFO] covid_annotation: COVID years %s present and an annotation text pattern was found in the script source (weak evidence - confirm via Read)\n",
                paste(overlap, collapse = ", ")))
    qa4b["info"] <- qa4b["info"] + 1L
  }
}

# --- Validate: resolution ---
# INTENT: Confirm an explicit export DPI adequate for print.
# ASSUMES: DPI is set literally in the script (dpi = 300); a computed value is undetectable.
cat("\nResolution Check:\n")
na_reason <- if ("resolution" %in% names(not_applicable)) not_applicable[["resolution"]] else NULL
if (!is.null(na_reason) && nzchar(na_reason)) {
  cat(sprintf("[SKIPPED] resolution: %s\n", na_reason))
  qa4b["skipped"] <- qa4b["skipped"] + 1L
} else if ("resolution" %in% names(not_applicable)) {
  cat("[NOT VERIFIED] resolution: declared not_applicable with an empty reason string\n")
  qa4b["not_verified"] <- qa4b["not_verified"] + 1L
} else if (is.null(script_text)) {
  cat("[NOT VERIFIED] resolution: script is unreadable - no text to inspect\n")
  qa4b["not_verified"] <- qa4b["not_verified"] + 1L
} else {
  dpi_match <- regmatches(script_text, regexpr("dpi\\s*=\\s*[0-9]+", script_text))
  if (length(dpi_match) == 0) {
    cat("[WARNING] resolution: no explicit 'dpi =' literal found in the script source\n")
    qa4b["warnings"] <- qa4b["warnings"] + 1L
  } else {
    dpi <- as.integer(gsub("[^0-9]", "", dpi_match[1]))
    if (dpi < 150) {
      cat(sprintf("[WARNING] resolution: dpi=%d declared in the script source - below the 150 print threshold\n", dpi))
      qa4b["warnings"] <- qa4b["warnings"] + 1L
    } else {
      cat(sprintf("[PASS] resolution: dpi=%d declared in the script source (>= 150)\n", dpi))
      qa4b["passed"] <- qa4b["passed"] + 1L
    }
  }
}

# --- Figures Directory Listing ---
cat("\n")
cat(strrep("=", 60), "\n")
cat("FIGURES DIRECTORY LISTING\n")
cat(strrep("=", 60), "\n")
figures_dir_path <- file.path(output_dir, "figures")
if (dir.exists(figures_dir_path)) {
  files <- list.files(figures_dir_path, full.names = TRUE)
  for (f in sort(files)) {
    cat(sprintf("  %s (%.1f KB)\n", basename(f), file.info(f)$size / 1024))
  }
} else {
  cat(sprintf("  (no figures directory at %s)\n", figures_dir_path))
}

# --- Verdict ---
# INTENT: Derive the QA4b verdict from the counters rather than asserting it.
# REASONING: INFO lines are reported but do not count as verification, so a run whose only
#            positive signals are text-pattern INFO hits lands on WARNING, not PASSED.
cat(sprintf("\nChecks: %d passed, %d warnings, %d blockers, %d not verified, %d skipped, %d info\n",
            qa4b[["passed"]], qa4b[["warnings"]], qa4b[["blockers"]],
            qa4b[["not_verified"]], qa4b[["skipped"]], qa4b[["info"]]))
qa4b_result <- if (qa4b[["blockers"]] > 0) {
  "BLOCKER"
} else if (qa4b[["warnings"]] > 0 || qa4b[["not_verified"]] > 0) {
  "WARNING"
} else if (qa4b[["passed"]] == 0) {
  "WARNING"  # nothing was actually verified
} else {
  "PASSED"
}
cat(sprintf("QA4b RESULT: %s\n", qa4b_result))
cat(strrep("=", 60), "\n")
```

### QA4b Discretionary Checks

| Check | When to Add | What It Validates |
|-------|-------------|-------------------|
| Aspect ratio | Publication submission | Figure dimensions meet requirements |
| Font size | Presentation figures | Text readable at intended display size |
| Annotation accuracy | Annotated plots | Annotation text matches data values |
| Multi-panel consistency | Faceted plots | Consistent scales across panels |
| **Visual trace** | **Always (at minimum 5)** — see `.claude/agents/code-reviewer.md` § Five Lenses of Skeptical Review | **Use the Read tool to visually inspect each generated PNG file.** Additionally, pick one data point and verify programmatically that it appears in the correct position in the figure |

**Creative check prompt:** Before writing your QA4b script, ask: *"If a figure were missing its legend, had truncated axes, or used a color scheme indistinguishable to colorblind readers, how would I detect that programmatically and visually (via the **Read tool** on the PNG output)?"* Design at least one check to catch that class of error.

### QA4b Iterative Investigation Triggers

Observations from crb1 that should trigger crb2+ investigation:

| crb1 Observation | Suggested crb2 Investigation |
|-----------------|---------------------------|
| Figure file size varies wildly across expected figures | Investigate: are some figures blank or truncated? |
| Script has no explicit DPI or size settings | Verify: do output figures meet minimum resolution? |
| Color palette not from known accessible set | Test: verify redundant encoding (shape/linetype) present |
| COVID years in data but annotation only on some figures | Audit: which figures include COVID years and which lack annotation? |

---

## Template Applicability Keys (`not_applicable`)

Every template's `# --- Config ---` region declares one mapping:

```python
not_applicable = {}  # e.g. {"suppression": "CCD directory file carries no suppression code"}
```
```r
not_applicable <- list()  # e.g. list(suppression = "CCD directory file carries no suppression code")
```

Before running, each check tests its key in that mapping:

1. Key present with a non-empty reason → `[SKIPPED] <key>: <reason>`, counted as skipped.
2. Key present with an empty reason → `[NOT VERIFIED] <key>: declared not_applicable with an empty reason string`. A reason is mandatory; an unexplained skip is indistinguishable from a silent one.
3. Key absent, required inputs missing → `[NOT VERIFIED] <key>: <what is missing>`.
4. Otherwise the check runs and emits `[PASS]` / `[WARNING]` / `[BLOCKER]` / `[INFO]` carrying its observed numbers.

The keys are stable and per-template:

| Template | Keys |
|----------|------|
| QA1 | `schema`, `year_coverage`, `id_uniqueness` |
| QA2 | `coded_values`, `suppression`, `column_types` |
| QA3 | `join_cardinality`, `aggregation`, `row_preservation`, `unexpected_nulls` |
| QA4a | `data_source`, `aggregation`, `model_convergence`, `assumptions`, `robustness` |
| QA4b | `figures`, `axis_labels`, `title`, `covid_annotation`, `resolution` |

Discretionary checks you add should follow the same pattern with their own snake_case key, documented in the QA script's header comment.

**Configuration values the templates recognize.** Unrecognized configuration strings are a BLOCKER with the offending value quoted — never a fall-through, and never NOT VERIFIED, because the configuration was present and wrong rather than absent.

| Field | Recognized values |
|-------|-------------------|
| `expected_cardinality` | `1:1`, `1:many`, `many:1`, `many:many` |
| `join_type` | `inner`, `left`, `right`, `outer`, `full`, `semi`, `anti` |
| aggregation `function` | `sum`, `mean`, `count`, `median`, `min`, `max` |
| `primary_sign` / `alt_sign` | `-1`, `0`, `+1` |

---

## Severity Classification Rules

Every QA check emits exactly one line beginning with one of six tokens. Nothing else in a QA script starts a line with `[`. Per-check lines never contain a `QA{n}` identifier — that string is reserved for the verdict line, and log comparators key on it.

| Token | Meaning |
|-------|---------|
| `[PASS]` | The check ran on real inputs and the claimed condition held. **The line carries the observed evidence** — counts, rates, values compared (e.g. `[PASS] suppression 'x': reported 50.0% == recomputed 50.0% (n=2/4 == -3)`). A PASS without its numbers is not a PASS. |
| `[WARNING]` | The check ran; a non-fatal deviation was observed. Carries the numbers. |
| `[BLOCKER]` | The check ran; a revision-required condition was observed. Also the outcome for any unrecognized configuration value. |
| `[NOT VERIFIED]` | The check **could not run** — a required input was missing, empty, `None`/`NULL`/`NA`, or of the wrong type — and the check was not declared not applicable. The line names exactly what was missing. |
| `[SKIPPED]` | The check was declared not applicable in the template's `not_applicable` mapping, and the line prints the declared reason. Counted, never silent. |
| `[INFO]` | Observational only, or a positive result resting on weak evidence (a text pattern over script source rather than an inspection of data or output). Does not affect the verdict. |

### Count Line and Verdict

Every template prints a count line immediately before its verdict, and derives the verdict from the counters:

```
Checks: {passed} passed, {warnings} warnings, {blockers} blockers, {not_verified} not verified, {skipped} skipped, {info} info
QA2 RESULT: PASSED | WARNING | BLOCKER
```

- `BLOCKER` if `blockers > 0`.
- Else `WARNING` if `warnings > 0` **or `not_verified > 0`** — a QA level with unverified checks has not done its job.
- Else `PASSED`.
- A run with zero substantive checks (`passed == 0`) is `WARNING`, not `PASSED`, with the count line showing `0 passed`. An all-skipped run can never read as clean.

`PASSED | WARNING | BLOCKER` are the only three verdict strings, and they map directly onto the status the code-reviewer reports to the orchestrator.

### Escalation Rule for NOT VERIFIED

The template default for a NOT VERIFIED check is WARNING. **The reviewer escalates it to BLOCKER when the Plan explicitly promised the missing input** — for example, the Plan lists `model_results` for a Stage 8 task but the field is absent, so convergence could not be checked at all. That case falls under the BLOCKER criterion "Validation Inadequate" below: a check that could not run cannot catch the corruption it exists to catch. The reviewer makes this call and records the reasoning in the QA report; the script does not make it automatically, because the script cannot read the Plan's intent.

### QAS Severity Overrides (Synthetic Path)

The synthetic path's disclosure-safety checkpoints override the WARNING default above. These overrides **escalate only** — they never lower a severity the general rules would assign. They apply to the checkpoints defined in § Synthetic-Path QA Checkpoints (QAS-A, QAS-B, QAS-C) and to their script-halting counterparts CPS-INTAKE / CPS-GEN in `agent_reference/VALIDATION_CHECKPOINTS.md`.

| Override | Rule | Why |
|----------|------|-----|
| **QAS-A escalation** | Any `[NOT VERIFIED]` in a1-a11 ⇒ `QAS-A RESULT: BLOCKER`, not WARNING. `WARNING` is not a legal QAS-A verdict at all | An emission path the reviewer could not trace is an unproven-safe path, and a disclosure leak is irreversible once the report is shared. "Probably fine" does not pass this gate |
| **Per-check escalation** | Any `[NOT VERIFIED]` on QAS-B `no_subthreshold_cells` / `crosstab_schema_wellformed` / `no_lone_suppressed_cell`, or on QAS-C `other_bucket_preserved` / `no_fabricated_categories` / `identifier_scaffolds_typed_value_free` ⇒ `BLOCKER` for that checkpoint | These are the checks that stand between a released report and a disclosure event. An incomplete sweep over them is indistinguishable from a sweep that would have found something |
| **Non-declarable keys** | No `not_applicable` entry may exist for any QAS-A key, for the three QAS-B keys above, or for the three QAS-C keys above. A declaration is itself `[BLOCKER] <key>: declared not_applicable — …` (review family) or `[FAIL]` (script family), quoting the offending key, and the check still runs | Otherwise the strongest control in the workflow can be switched off by a config line, with the log reading as a counted, reasoned skip |
| **Aggregate-only evidence** | A `[PASS]` on a disclosure check carries counts of things examined and the threshold — e.g. `[PASS] no_subthreshold_cells: 12 categorical blocks + 3 crosstab blocks scanned, 148 visible cells, all >= threshold 5`. It never prints a cell value, a minimum, a level label with its count, or a per-level line. A `[FAIL]` names the column / block / cell position only. `[INFO]` on this path carries tier, threshold, and shape facts only | The general PASS-carries-its-numbers rule is satisfied by aggregates. Printing *which* number was smallest is itself a release, so the evidence requirement and the disclosure requirement are reconciled by counting rather than by quoting |
| **Scan completeness is a check** | A sweep check enumerates its blocks explicitly, counts blocks scanned, and cross-checks that count against the number the report declares. Mismatch ⇒ `[FAIL] …: scanned N of M declared blocks — the sweep is incomplete`. Zero declared blocks ⇒ an evidence-bearing `[PASS]`, never not-applicable — CPS-INTAKE prints `[PASS] no_released_count_below_threshold: 0 of 0 declared blocks scanned (0 categorical + 0 cross-tab), 0 visible cells examined, all >= effective threshold G (declared d, approved e)` | A sweep that silently examined nothing is the exact defect these templates exist to eliminate; "nothing to scan" must be established, not assumed |

### BLOCKER (Revision Required)

A finding is BLOCKER severity when:

1. **Data Correctness Compromised**
   - Wrong data is being used (wrong years, wrong geography, wrong columns)
   - Transformations produce incorrect results
   - Joins have unexpected cardinality

2. **Methodology Violated**
   - Implementation contradicts Plan specification
   - Critical cleaning steps skipped or wrong
   - Business logic errors in calculations

3. **Validation Inadequate**
   - Code could pass despite data corruption
   - Critical checks missing entirely
   - STOP conditions not implemented

4. **Output Invalid**
   - Missing required outputs
   - Outputs contain clearly wrong data
   - Stub/placeholder code detected

### WARNING (Document and Proceed)

A finding is WARNING severity when:

1. **Quality Concern (Not Correctness)**
   - Suboptimal approach that still works
   - Edge cases not explicitly handled (but unlikely)
   - Validation could be more robust

2. **Minor Deviation**
   - Slight methodology variation (acceptable)
   - Row counts differ from expectation (within tolerance)
   - Performance could be improved

3. **Documentation Gap (IAT Compliance)**
   - Missing INTENT comments on transformations
   - Missing REASONING comments on non-obvious choices
   - Assumptions not explicitly stated (missing ASSUMES comments)
   - Section preambles absent
   - Magic numbers without explanation
   - See `agent_reference/INLINE_AUDIT_TRAIL.md` for the full standard

### INFO (Log Only)

A finding is INFO severity when:

1. **Suggestions for Improvement**
   - Code could be cleaner
   - Better approaches exist
   - Optimization opportunities

2. **Observations**
   - Interesting data patterns
   - Potential future enhancements
   - Style preferences

3. **Weak-Evidence Positives**
   - A text pattern matched in script source (axis labels, title, annotation calls)
   - Anything a comment or an empty string literal could satisfy
   - These are reported so the reviewer knows to confirm visually, but they never count as verification

### PASS (Verified, With Evidence)

A finding is PASS severity when:

1. **The check ran on real inputs** — the configuration was present, the columns existed, the frames were non-empty
2. **The claimed condition held** — and the line prints the numbers that establish it: counts compared, rates recomputed, values matched, thresholds and observed values both shown

A PASS that names no numbers is a defect, not a finding. "All checks passed" is an absence of findings; "reported 50.0% == recomputed 50.0% (n=2/4)" is a finding.

### NOT VERIFIED (Evidence Unavailable)

A finding is NOT VERIFIED severity when:

1. **A required input was absent, empty, null, or the wrong type** — and the check was not declared not applicable
2. **The line names exactly what was missing** — the config key, the column, the frame, the field

NOT VERIFIED is not a failure of the code under review; it is a failure of the *check* to obtain evidence. It forces the QA verdict to at least WARNING, and escalates to BLOCKER when the Plan promised the missing input (see the escalation rule above).

### SKIPPED (Declared Not Applicable)

A finding is SKIPPED severity when:

1. **The check's key appears in the template's `not_applicable` mapping with a non-empty reason** — for example, a directory file that carries no suppression code
2. **The reason is printed** — a skip whose rationale is not in the log is indistinguishable from a check that silently never ran

SKIPPED does not affect the verdict, but it is counted and visible, so a reviewer can see how much of the checkpoint was declared away.

---

## QA Script Directory Structure

```
scripts/
├── stage5_fetch/
│   └── 01_fetch-ccd.py
├── stage6_clean/
│   └── 01_clean-ccd.py
├── stage7_transform/
│   └── 01_join-data.py
├── stage8_analysis/
│   ├── 01_regression-analysis.py
│   └── 02_enrollment-plot.py
├── cr/                              # Code-review scripts directory (iterative)
│   ├── stage5_01_cr1.py             # QA1 for Stage 5, Step 01 (standard + profiling)
│   ├── stage5_01_cr2.py             # QA2: Investigated year coverage anomaly
│   ├── stage6_01_cr1.py             # QA1 for Stage 6, Step 01
│   ├── stage7_01_cr1.py             # QA1 for Stage 7, Step 01
│   ├── stage7_01_cr2.py             # QA2: Investigated join non-matches
│   ├── stage7_01_cr3.py             # QA3: Traced 10 entities end-to-end
│   ├── stage8_01_cra1.py            # QA4a (statistical validity) for Stage 8, Step 01
│   └── stage8_02_crb1.py            # QA4b (visualization quality) for Stage 8, Step 02
└── debug/
    └── ...
```

### Naming Convention

**Standard pattern (Stages 5-7):** `stage{N}_{step:02d}_cr{iteration}.py` (`.R` for R projects)

| Component | Description | Example |
|-----------|-------------|---------|
| `stage{N}` | Stage number (5, 6, 7) | `stage7` |
| `{step}` | Step number from reviewed script | `01`, `02` |
| `_cr{iteration}` | QA script suffix with iteration number (1-5) | `_cr1`, `_cr2` |

**Stage 8 pattern (split QA):** `stage8_{step:02d}_cr{a|b}{iteration}.py` (`.R` for R projects)

| Component | Description | Example |
|-----------|-------------|---------|
| `stage8` | Stage 8 (analysis & visualization) | `stage8` |
| `{step}` | Step number from reviewed script | `01`, `02` |
| `_cra{iteration}` | QA4a (statistical validity) suffix | `_cra1`, `_cra2` |
| `_crb{iteration}` | QA4b (visualization quality) suffix | `_crb1`, `_crb2` |

**Examples:**
- Script `01_fetch-ccd.py` in Stage 5 → `stage5_01_cr1.py` (first iteration), `stage5_01_cr2.py` (if needed)
- Script `02_aggregate.py` in Stage 7 → `stage7_02_cr1.py`
- Script `01_regression-analysis.py` in Stage 8 → `stage8_01_cra1.py` (QA4a), `stage8_01_crb1.py` (QA4b)

**Data Onboarding profiling QA naming:** For the profiling QA naming convention (`profile_{phase}_cr{N}.py`), see `.claude/skills/daaf-orchestrator/references/data-onboarding-mode.md` and the QAP Script Naming Convention section within this document.

---

## QA Report Format

QA checkpoint results follow this conceptual schema. The actual output to the orchestrator uses Markdown format (see the code-reviewer invocation template in `full-pipeline-mode.md`). This YAML schema documents the logical structure. Per-check `status` values are the same six tokens the templates emit (§ Severity Classification Rules), so the report and the execution log use one vocabulary — every check in the log appears here, including the ones that could not run.

```yaml
qa_report:
  script_reviewed: "scripts/stage7_transform/01_join-data.py"
  qa_script: "scripts/cr/stage7_01_cr1.py"
  result: "BLOCKER"        # the QA{n} RESULT line: PASSED | WARNING | BLOCKER
  counts:                  # mirrors the template's count line
    passed: 1
    warnings: 1
    blockers: 1
    not_verified: 1
    skipped: 1
    info: 0

  checks:
    - name: "join_cardinality"
      status: "BLOCKER"
      message: "Fan-out beyond 1:1/inner"
      evidence: "150,000 output rows exceed the 100,000 ceiling (left=100,000, right=98,412)"

    - name: "schema"
      status: "PASS"
      message: "All expected columns present"
      evidence: "12 of 12 expected columns present (14 columns in df)"

    - name: "row_preservation"
      status: "WARNING"
      message: "Row count deviates from the Plan estimate"
      evidence: "expected ~100,000, observed 112,300 (12.3% deviation)"

    - name: "aggregation"
      status: "NOT_VERIFIED"
      message: "source_dfs['input'] is missing — nothing to recompute from"
      evidence: null                     # by definition: no evidence was obtainable
      escalated: false                   # true when the Plan promised the missing input
      escalation_rationale: null

    - name: "unexpected_nulls"
      status: "SKIPPED"
      message: "no columns are declared null-free for this reshape step"
      evidence: null
      declared_reason: "no columns are declared null-free for this reshape step"

  issues:
    blockers:
      - check: "join_cardinality"
        description: "Fan-out detected in 1:1 join"
        suggested_fix: "Check for duplicate keys in right table"

    warnings:
      - check: "row_preservation"
        description: "Row count deviates from the Plan estimate"
        recommendation: "Confirm which filter or join step changed the count"

    not_verified:
      - check: "aggregation"
        missing_input: "source_dfs['input']"
        recommendation: "Supply the pre-aggregation frame and re-run the QA script"

    info: []

  recommendation: "REVISION_REQUIRED"  # or "PROCEED" or "ESCALATE"
```

**`status` values:** `PASS`, `WARNING`, `BLOCKER`, `NOT_VERIFIED`, `SKIPPED`, `INFO` (underscore in YAML, space in the log line). `FAIL` and `WARN` are not part of this vocabulary — `FAIL` belongs to the script-halting CP family in `VALIDATION_CHECKPOINTS.md`, and `WARN` is retired.

**`result` values:** `PASSED`, `WARNING`, `BLOCKER` — derived from `counts` exactly as the template derives its verdict line, never asserted independently.

---

## Integration with Stage 10

Stage 10 aggregates all QA findings from Stages 5-8:

### QA Summary for Stage 10

```markdown
## QA Summary Report

### Execution Overview
| Stage | Scripts | QA Reviews | BLOCKERs Found | BLOCKERs Resolved |
|-------|---------|------------|----------------|-------------------|
| 5     | 2       | 2          | 0              | N/A               |
| 6     | 2       | 2          | 0              | N/A               |
| 7     | 3       | 3          | 2              | 2 (via revision)  |
| 8     | 1       | 1          | 0              | N/A               |

### Resolved BLOCKERs
| Script | Issue | Resolution | Revision Count |
|--------|-------|------------|----------------|
| 01_join-data.py | Fan-out join | Fixed duplicate keys | 2 |

### Outstanding WARNINGs
| Script | Warning | Assessment | Documentation |
|--------|---------|------------|---------------|
| 01_clean-ccd.py | 38% suppression | Acceptable | Added to limitations |

### INFO Items
| Script | Observation |
|--------|-------------|
| 01_fetch-ccd.py | Could parallelize data access calls |
```

---

## QA Checkpoint STOP Conditions

QA checkpoints can trigger STOP conditions that prevent proceeding:

| Condition | Checkpoint | Action |
|-----------|------------|--------|
| BLOCKER after 2 revision scripts (_a.py, _b.py) | Any | STOP, escalate to user |
| Methodology violation | Any | STOP, escalate immediately |
| Data corruption detected | QA3 | STOP, invoke debugger |
| Statistical misrepresentation detected | QA4a | STOP, revision required |
| Missing critical figures | QA4b | STOP, revision required |
| QA script execution fails | Any | STOP, investigate |

---

## Profiling QA Checkpoints (QAP1-QAP4)

> **Mode:** These checkpoints apply to Data Onboarding Mode only. They are the profiling equivalent of QA1-QA4b. See `.claude/skills/daaf-orchestrator/references/data-onboarding-mode.md` for complete profiling protocol details.

### QAP Overview

| Checkpoint | Part | Focus | BLOCKER When |
|------------|------|-------|-------------|
| QAP1 | A (Structural) | Load fidelity, schema accuracy | Wrong delimiter/encoding, type inference errors, row/column count mismatch |
| QAP2 | B (Statistical) | Statistical characterization | Distribution claims wrong, temporal breaks missed, coverage gaps undetected |
| QAP3 | C (Relational) | Relationship discovery | Key uniqueness misidentified, dependencies missed, anomalies uncatalogued |
| QAP4 | D (Interpretation) | Semantic accuracy | Interpretations stated as facts (missing [PRELIMINARY]), reconciliation gaps |

The "BLOCKER When" column states only the failure condition. It is not the whole outcome space: a check whose BLOCKER condition did not fire has *not* necessarily passed — it may have been unable to run. Each checkpoint's Default Checks table below therefore states, per check, what makes it not applicable (declared with a reason ⇒ `[SKIPPED]`) versus not verifiable (input absent, conditional script not run ⇒ `[NOT VERIFIED]`), and the verdict is derived from the counts rather than from the absence of BLOCKERs.

### QAP1: Post-Structural (Part A)

**Trigger:** After scripts 01-03 complete and CPP1 reports `PASSED` or `PASSED WITH WARNINGS`.

**Default Checks:** (key = the `not_applicable` key; every check emits exactly one line on every path)

| Check | Key | Validates | BLOCKER If | Not Applicable (`[SKIPPED]`) | Not Verifiable (`[NOT VERIFIED]`) |
|-------|-----|-----------|------------|------------------------------|-----------------------------------|
| Re-load verification | `reload` | Load with alternative parameters produces same data | Row/column counts differ across methods | The format admits exactly one load path (e.g. a single-schema Parquet file) — declare with that reason | No alternative load parameterization was attempted, or script 01 recorded no canonical load pattern to vary |
| Sample row spot-check | `sample_rows` | Random rows match raw file inspection | Values corrupted or truncated | Raw file is not human-inspectable (binary columnar format) — declare with that reason | The raw file is unavailable to the reviewer, or the loaded frame has zero rows |
| Encoding verification | `encoding` | No mojibake or replacement characters | Non-ASCII characters corrupted | Source is a typed binary format with no text encoding (Parquet, Feather) — declare with that reason | No string/character columns exist in the frame, so nothing was scanned |
| Schema stability | `schema_stability` | Re-running type inference produces same types | Types change between runs | Schema is declared by the format, not inferred (Parquet, Stata) — declare with that reason | Type inference was not re-run, or script 02 recorded no schema to compare against |
| Column coverage | `column_coverage` | Every column appears in profile output | Any column missing from profile | Never — this check applies to every profiling run | The script 03 column-profile artifact is missing or empty, so there is no profile inventory to compare against the schema |

### QAP2: Post-Statistical (Part B)

**Trigger:** After scripts 04-06 (conditional) complete and CPP2 reports `PASSED` or `PASSED WITH WARNINGS`.

**Default Checks:** (scripts 05 and 06 are conditional — a check bound to a script that did not run is `[SKIPPED]` when the condition was evaluated and recorded, `[NOT VERIFIED]` when it was not)

| Check | Key | Validates | BLOCKER If | Not Applicable (`[SKIPPED]`) | Not Verifiable (`[NOT VERIFIED]`) |
|-------|-----|-----------|------------|------------------------------|-----------------------------------|
| Independent stat verification | `stat_recompute` | Recompute mean/median for random columns | Independently computed stat differs from the profiled value | No numeric columns in the dataset — declare with that reason | Script 04's distribution artifact is missing, or the recomputation source frame is unavailable |
| Distribution label accuracy | `distribution_labels` | Distribution claims pass appropriate tests | "Normal" claim fails normality test at p < 0.01 | Profile makes no distributional claims (all columns categorical) — declare with that reason | A distribution label is present but the underlying column is absent, all-null, or has n below the test's minimum |
| Outlier boundary reasonableness | `outlier_fences` | IQR fences are sensible | Fences exclude >20% of data without explanation | Outlier detection was not performed because no continuous columns exist — declare with that reason | Fence values are absent from the profile, or the column they refer to is missing from the frame |
| Temporal break detection | `temporal_breaks` | Obvious structural breaks are flagged | Dramatic year-to-year changes missed | Script 05 did not run because Part A found no time column, and that determination is recorded — declare with that reason | Script 05's condition was never evaluated or its output is missing; or a time column exists but the coverage artifact does not |
| Coverage completeness | `coverage_completeness` | Entity/geographic coverage is assessed against a known universe | Identifiers are present, a known universe is available, and coverage was not checked | Script 06 did not run because Part A found no entity/geographic identifier, and that determination is recorded — declare with that reason | Identifiers are present but no known universe (reference roster, expected entity count) is available to compare against — say which universe is missing. This is the case that previously read as PASS |

### QAP3: Post-Relational (Part C)

**Trigger:** After scripts 07-09 (conditional) complete and CPP3 reports `PASSED` or `PASSED WITH WARNINGS`.

**Default Checks:** (scripts 07b and 08 are conditional — see the not-applicable/not-verified columns)

| Check | Key | Validates | BLOCKER If | Not Applicable (`[SKIPPED]`) | Not Verifiable (`[NOT VERIFIED]`) |
|-------|-----|-----------|------------|------------------------------|-----------------------------------|
| Key uniqueness counter-check | `key_uniqueness` | Claimed keys tested independently | Claimed unique key has duplicates | Script 07 claimed no unique or composite key, and that determination is recorded — declare with that reason | Script 07's key claim exists but the named column(s) are absent from the frame, or the frame itself is unavailable |
| Dependency verification | `dependencies` | Functional dependencies are real | Counter-examples exist for a claimed A->B dependency | No functional dependencies were claimed — declare with that reason | A dependency was claimed but one of its columns is missing, or the claim names no columns to test |
| Anomaly catalog completeness | `anomaly_catalog` | All major anomalies found | Known pattern (duplicates, coded values) present but uncatalogued | Never — every profiling run produces a catalog, even if only INFO entries | Script 09's anomaly catalog artifact is missing or unreadable, so completeness cannot be assessed |
| Cross-column consistency | `cross_column_consistency` | Consistency rules are complete | Obvious logical constraint violated but not flagged | The frame has a single substantive column, so no cross-column rule is possible — declare with that reason | No consistency rules were recorded and none could be derived from the profile, so nothing was tested |
| Coded value scan completeness | `coded_value_scan` | Standard sentinels checked | Numeric columns not scanned for -1, -2, -3, -9, -99, -999 | No numeric columns exist — declare with that reason | The sentinel vocabulary is empty, or the scan artifact is missing (an empty vocabulary scanned nothing and must not read as clean) |
| Cross-file linkage verification (HIERARCHICAL only) | `cross_file_linkage` | Key cardinality, coverage, orphan counts, join simulation | Cardinality claimed 1:M but data shows M:M; key type mismatch across files not detected; join simulation not performed | File structure is SINGLE or HORIZONTAL, so script 07b does not apply — declare with that reason | File structure is HIERARCHICAL but script 07b did not run, its output is missing, or the schema map naming the cross-file keys is absent |

### QAP4: Post-Interpretation (Part D)

**Trigger:** After scripts 10-11 (conditional) complete and CPP4 reports `PASSED` or `PASSED WITH WARNINGS`.

**Default Checks:** (script 11 runs only when documentation was provided)

| Check | Key | Validates | BLOCKER If | Not Applicable (`[SKIPPED]`) | Not Verifiable (`[NOT VERIFIED]`) |
|-------|-----|-----------|------------|------------------------------|-----------------------------------|
| PRELIMINARY marking | `preliminary_marking` | All interpretations hedged | Any interpretation stated as fact without a [PRELIMINARY] marker | Never — any interpretation output is subject to this check | Script 10's interpretation artifact is missing or contains zero entries, so no text was scanned |
| Documentation coverage | `doc_coverage` | All documented claims checked against data | Documented column present but not reconciled | No documentation was provided for this source, so script 11 does not apply — declare with that reason (this is the common case, and it must appear in the log as a counted skip, not as a pass) | Documentation was provided but script 11 did not run, its output is missing, or the documentation could not be parsed into claims |
| Discrepancy evidence | `discrepancy_evidence` | Every discrepancy has actual-vs-documented values | Discrepancy noted without showing evidence | No documentation was provided, so no discrepancies can exist — declare with that reason | Script 11 ran but its discrepancy list is absent; a discrepancy list that exists and is empty is a real PASS with `n=0` on the line |
| Interpretation completeness | `interpretation_completeness` | All columns with non-trivial semantics have an interpretation entry | Column with identifiable meaning has no interpretation | Never — every profiled column is in scope | The schema inventory or the interpretation artifact is missing, so the two cannot be compared |

### QAP Severity Classification

Profiling QA uses the same six-token vocabulary as analysis QA (§ Severity Classification Rules), the same count line, and the same derived verdict:

- **PASS:** The check ran on real inputs and the claimed condition held — with the observed numbers on the line
- **WARNING:** Quality concern or minor gap that should be documented but does not block progression
- **BLOCKER:** Data characterization is incorrect, profiling methodology violated, output is unreliable, or a configuration value is unrecognized
- **NOT VERIFIED:** The check could not run because a required input (a column, a profile artifact, a config key) was missing, empty, or the wrong type — the line names what was missing
- **SKIPPED:** The check was declared not applicable in the profiling script's `not_applicable` mapping, with the reason printed
- **INFO:** Observation, suggestion, or a positive result resting on weak evidence

The two tokens that did not exist before — NOT VERIFIED and SKIPPED — are what make the QAP tables above honest. Previously each check defined only its BLOCKER condition, so a check that could not run raised no BLOCKER and the checkpoint recorded PASSED over it: coverage completeness with no known universe available, documentation coverage with no documentation, any QAP2/QAP3 check bound to a conditional script (05, 06, 07b, 08) that never ran. Those cases are now `[NOT VERIFIED]` or, when the profiling agent declares them with a reason, `[SKIPPED]` — either way counted and visible in the count line.

### QAP Applicability Declarations

The profiling QA script's `# --- Config ---` region carries the same `not_applicable` mapping as the analysis QA templates (§ Template Applicability Keys), using the keys in the QAP tables above:

```python
not_applicable = {}  # e.g. {"doc_coverage": "No documentation was provided for this source"}
```
```r
not_applicable <- list()  # e.g. list(doc_coverage = "No documentation was provided for this source")
```

Resolution order per check is identical: declared with a non-empty reason → `[SKIPPED] <key>: <reason>`; declared with an empty reason → `[NOT VERIFIED]`; inputs missing → `[NOT VERIFIED] <key>: <what is missing>`; otherwise run the check and print its numbers. A check is never omitted from the log. Where a table's "Not Applicable" cell reads *Never*, that key belongs in `not_applicable` only with an explicit reviewer rationale — the default for those checks is to run or to report NOT VERIFIED.

### QAP Count Line and Verdict

Every QAP review prints a count line immediately before its verdict, and derives the verdict from the counters:

```
Checks: {passed} passed, {warnings} warnings, {blockers} blockers, {not_verified} not verified, {skipped} skipped, {info} info
QAP3 RESULT: PASSED | WARNING | BLOCKER
```

- `BLOCKER` if `blockers > 0`.
- Else `WARNING` if `warnings > 0` **or `not_verified > 0`** — a profiling checkpoint with unverified checks has not characterized the data it claims to have characterized.
- Else `PASSED`.
- A run with zero substantive checks (`passed == 0`) is `WARNING`, not `PASSED`, with the count line showing `0 passed`. An all-skipped part can never read as clean.

`PASSED | WARNING | BLOCKER` are the only three verdict strings, and they are what the reviewer reports to the orchestrator and what the orchestrator records in STATE.md — with the counts, so a recorded PASSED can be read against how much actually ran.

**Escalation rule.** The default for a NOT VERIFIED check is WARNING. The reviewer escalates to BLOCKER when the profiling protocol explicitly promised the missing input — the file structure was classified HIERARCHICAL so script 07b was required, or documentation was supplied so script 11 was required, or Part A found a time column so script 05 was required. In those cases the input was owed and its absence is a gap in the profiling itself, falling under the "Validation Inadequate" BLOCKER criterion. The reviewer makes the call and records the reasoning in the QA report.

**Relationship to CPP.** CPP{n} is the script-halting family and prints `CPP{n} VALIDATION: PASSED | PASSED WITH WARNINGS | FAILED`, where NOT VERIFIED forces FAILED and the script raises. QAP{n} is the review-severity family above, where NOT VERIFIED forces at least WARNING and nothing halts. A part's gate reads both: see `agent_reference/VALIDATION_CHECKPOINTS.md` § Profiling Validation Checkpoints for the CPP side and `.claude/skills/daaf-orchestrator/references/data-onboarding-mode.md` for the gate criteria.

> **Note:** The QAP1-QAP4 check tables above are agent checklists, not full script templates — this document carries no per-check QAP code, only the `not_applicable` config shape above. The code-reviewer writes each profiling QA script following the QA1-QA4b template patterns (accumulator counters, one line per check, derived verdict) with the QAP keys from the tables above. The in-script profiling checkpoints are separate and live in `agent_reference/VALIDATION_CHECKPOINTS.md` (CPP1-CPP4, CPP-SKILL).

### QAP Script Naming Convention

```
scripts/cr/
  profile_structural_cr{N}.py     # QAP1 review scripts
  profile_statistical_cr{N}.py    # QAP2 review scripts
  profile_relational_cr{N}.py     # QAP3 review scripts
  profile_interpretation_cr{N}.py # QAP4 review scripts
```

(`.R` in place of `.py` for R projects — the pattern is otherwise identical.)

---

## Synthetic-Path QA Checkpoints (QAS-A, QAS-B, QAS-C)

> **Mode:** These checkpoints apply to Data Onboarding Mode's **synthetic (privacy-preserving) path** only — the branch taken when the raw data must never enter the container. They replace QAP1-QAP4, which cannot run here because there is no source file to recompute against. See `.claude/skills/daaf-orchestrator/references/WORKFLOW_PHASE_DO_SYNTHETIC.md` for the stage protocol and `.claude/skills/synthetic-data-workflow/references/validation-checks.md` for the skill-local detail (forbidden emissions per tier, tolerances, maintainer regression check).

### QAS Overview

| Checkpoint | Stage | Reviews | Verdict line | BLOCKER when |
|------------|-------|---------|--------------|--------------|
| QAS-A | DS-1 (before the user runs the script) | Disclosure-safety of the **outbound** profiling/synthesizer script | `QAS-A RESULT: PASSED \| BLOCKER` | Any forbidden emission is reachable at the chosen tier — or any check could not be verified |
| QAS-B | DS-3 (report intake) | Internal consistency of the **returned** profile report | `QAS-B RESULT: PASSED \| WARNING \| BLOCKER` | Report corrupt; a sub-threshold cell was released; a hidden count is recoverable by differencing (a categorical or cross-tab residual that does not reconcile with its `n`); or the report exceeds the approved tier ceiling or falls below the approved threshold |
| QAS-C | DS-5 (post-generation) | Fidelity of the **generated** synthetic data to the profile | `QAS-C RESULT: PASSED \| WARNING \| BLOCKER` | Generation bug or disclosure-adjacent fabrication |

These are the review-severity family. Their script-halting counterparts — **CPS-INTAKE** (the DS-3 intake validator) and **CPS-GEN** (the DS-5 generation validator) — are shipped code blocks in `agent_reference/VALIDATION_CHECKPOINTS.md` § Synthetic-Path Validation Checkpoints. QAS-B reviews CPS-INTAKE's script and re-derives its conclusions; QAS-C does the same for CPS-GEN. A gate reads both.

**Why this path needs its own severity overrides.** On every other path a check that could not run is a WARNING, because the reviewer can go back to the data and re-run it. Here the irreversible event has already happened or is about to: once a report crosses the boundary it cannot be recalled. An emission path the reviewer could not trace is therefore not an open question — it is an unproven-safe path, and unproven-safe is unsafe. The overrides in § QAS Severity Overrides below escalate NOT VERIFIED on the disclosure-critical checks; they never weaken the general rules in § Severity Classification Rules.

### QAS-A: Disclosure-Safety Review (DS-1)

**Trigger:** After research-executor has customized the outbound script (profiler at T1-T3, or the local synthesizer at T4) and before the script is handed to the user.

**Default Checks:** (key = the stable check key; every check emits exactly one line on every path. **QAS-A carries no `not_applicable` mapping** — see the Not Applicable column.)

| Check | Key | Validates | BLOCKER If | Not Applicable (`[SKIPPED]`) | Not Verifiable (`[NOT VERIFIED]`) |
|-------|-----|-----------|------------|------------------------------|-----------------------------------|
| a1 No raw min/max (T2+) | `no_raw_min_max` | No `min()`/`max()` of a value column reaches an emitted field | Any raw extremum is emitted | **Never declarable** | The emission path could not be traced to a terminal write — record which path and treat as BLOCKER |
| a2 No example values (T2+) | `no_example_values` | No category/string value escapes except via the suppressed-level or `__OTHER__` path | Any head/sample/first-rows emission, or any unsuppressed label | **Never declarable** | A value's route to output could not be followed — BLOCKER |
| a3 Suppression unconditional (T2+) | `unconditional_suppression` | Every categorical / cross-tab cell passes the `< threshold` gate | Any path emits a cell without the gate | **Never declarable** | A branch's gate coverage could not be established — BLOCKER |
| a4 Identifier columns structure-only | `identifier_structure_only` | Identifier-flagged columns emit dtype/uniqueness/length only | Any identifier column emits values, percentiles, or level lists | **Never declarable** | The identifier-flagging branch could not be exercised or read — BLOCKER |
| a5 Tier gate correct | `tier_gate_correct` | No statistic above the configured tier is producible | Relationship/cross-tab code is reachable at T1/T2 | **Never declarable** | The tier constant's effect on a branch could not be determined — BLOCKER |
| a6 Edge cases cannot leak | `edge_cases_cannot_leak` | All-null column, single-row group, single distinct value, identifier slipping the >95% heuristic | Any edge case produces a forbidden emission | **Never declarable** | An edge case could not be traced or probed — BLOCKER (the common leak is the edge case, not the main path) |
| a7 No raw-data side channel | `no_raw_side_channel` | No write of input rows, no debug print of `df`, no copy of the source file | Any side channel exists | **Never declarable** | A write target could not be resolved — BLOCKER |
| a8 `__OTHER__` roll-in present | `other_bucket_rollin` | A residual sub-threshold `__OTHER__` folds in the smallest retained levels (or the column is fully suppressed) | A bare `__OTHER__ = sum(binned)` with no roll-in | **Never declarable** | The roll-in loop's termination could not be established — BLOCKER |
| a9 Value-summary support and validity | `value_summary_support` | `2.0` support gates: below-k withheld, eligible constants shared, reduced grids quartiles-only, all-missing carries no values, paired support real | A released summary is below minimum support, or an undefined correlation is fabricated as zero | **Never declarable** | A shape branch could not be checked against `profiling-script-spec.md` — BLOCKER |
| a10 Cross-tab suppression complementary (T3) | `crosstab_complementary_suppression` | Suppressed cells are `null` (never `0`); complementary suppression is **bridge-free**: with every row and column total treated as released, no hidden cell is exactly recoverable from its own table together with those totals by differencing. Read the hidden cells as edges between their row and column; no hidden cell may be a bridge (an edge on no cycle of hidden cells). A lone hidden cell, the only one in its row or column, is the simplest bridge, and a hidden cell joining two otherwise separate groups of hidden cells is the case a lone-cell loop misses. The bridge step never hides a zero (the earlier complementary step can). A table that cannot be made bridge-free, or whose suppression loop does not converge, is fully suppressed and marked `collapsed`. The table is built on the **released categories**: levels the categorical block pools into `__OTHER__` form one pooled row or column, so no pooled level gets a row or column of its own, and an available table's `rows`/`cols` equal the pair columns' released level counts. The suppression loop also covers **missing-partner counts**: a categorical block counts every record with a value, a cross-tab only the records with both values, so a level's count minus its cross-tab row is the number of records with that level whose partner is missing. No below-threshold non-zero missing-partner count may become recoverable because of that cross-tab's released cells, read with the released totals; the script hides more cells or collapses the table to prevent it, and changes nothing when neither pair column has missing values. Missing-partner counts revealed by released `n` and missing counts alone (for example a column with a single released category) and the count of records missing both values are accepted residuals, not findings. **Named-regression gate:** a named regression is fitted on pair-complete records, so with the released marginal means it would reveal the mean of x over the few records lacking y; an entry is released only when each complement group (records with one of the pair's values but not the other) is empty or at least the threshold, otherwise it is unavailable with reason `small_complement_group`. The script refuses, before writing anything, a `RELATIONSHIP_SPEC` with a self-pair or a repeated pair. A reversed pair of two numeric columns stays allowed: it is a second regression and releases no cells, and its regressions face the same complement-group gate. *Reviewer awareness, not a BLOCKER condition:* at T3 the script also releases Cramér's V for every supported categorical pair, computed on the full table (unpooled, unsuppressed) and rounded to 6 decimals. Combined with the released category counts, it can let a determined analyst reconstruct small cross-tab cells, including for pairs with no released cross-tab, and it can undo `__OTHER__` pooling, recovering the rare pooled levels' counts and how they spread across the partner column (their labels stay unknown). Bridge-free suppression does not cover this channel. It is the accepted T3 residual risk (`disclosure-tiers.md` § T3), which the researcher is told about at PSU-DS1. *Also reviewer awareness, not a BLOCKER condition:* every protection above holds for one release at a time (one cross-tab, or one regression, together with the released totals), and the self-pair and repeated-pair refusal compares column names. The **linked-release residuals** fall outside it: several cross-tabs sharing a column whose partners are missing on the same or overlapping records can jointly pin a small missing-partner count; several named regressions sharing a column whose pair-complete records differ by a few records reveal that column's mean over those records; and two encodings of one variable (a code column and its label column) paired with the same partner give two differently suppressed copies of one table. No validator detects them; they are an accepted T3 limitation (`disclosure-tiers.md` § T3, *Linked-release residuals (accepted)*), not findings. **Spec review note:** read the configured `RELATIONSHIP_SPEC` for obviously overlapping pairs (one column listed with several partners, or in several regressions) and for two columns that look like encodings of one variable paired with the same partner. Raise any you see in the review's notes to the researcher (outside the per-check lines, so a10 still emits exactly one outcome line and the note does not change the verdict) naming the pair positions (keep each column in few pairs, drop one of the two encodings before profiling, or consider T2 if many overlapping relationships are needed), never as a BLOCKER | Any lone suppressed cell survives; any hidden cell is still a bridge when the script emits the table, including a script with a lone-cell loop but no bridge step; a suppressed cell is coded `0`; a level pooled into `__OTHER__` can get its own cross-tab row or column (subtracting it from `__OTHER__` recovers a rare count); the script accepts a self-pair or a repeated pair other than a reversed numeric pair (two differently suppressed tables of one pair can be combined to recover cells); the script lacks the missing-partner rule (its loop protects only the hidden core cells, so a level count minus a visible cross-tab row can leave a small non-zero missing-partner count recoverable); or the script can release an available named regression whose complement group is non-empty and below the threshold | **Never declarable** — at T1/T2 the check still runs and reports `[PASS] …: 0 cross-tab emission paths reachable at tier {t}` | The suppression loop's convergence, or the bridge step's termination, could not be established — BLOCKER |
| a11 T4 shareable log is aggregate-only | `t4_log_aggregate_only` | The T4 shareable synthesis log contains no per-variable utility or comparison output — only an aggregate statistic | Any `compare()` / `utility.gen` per-variable output (marginal tables, frequency counts, histograms) reaches the shareable log | **Never declarable** — at T1-T3 the check still runs and reports `[PASS] …: no T4 synthesizer in scope, 0 shareable logs written` | The library's printed/returned content could not be established (e.g. `synthpop` unavailable) — record `[NOT VERIFIED]`, apply the conservative aggregate-only fix anyway, and treat as BLOCKER |

**a11 in one sentence:** the T4 shareable synthesis log contains no per-variable utility or comparison output; only an aggregate statistic.

### QAS-B: Report Internal-Consistency Review (DS-3)

**Trigger:** After the returned report is in `data/profile_report/` and the CPS-INTAKE validator script has run.

**Default Checks:** (the reviewer re-derives these from the report's own numbers — never from the report's embedded `all_passed`, which is the user's claim, not DAAF's verification)

| Check | Key | Validates | BLOCKER If | Not Applicable (`[SKIPPED]`) | Not Verifiable (`[NOT VERIFIED]`) |
|-------|-----|-----------|------------|------------------------------|-----------------------------------|
| b1 Report version accepted | `report_version_accepted` | `report_version == "2.0"` for new-policy acceptance | Version is legacy `1.0` relabelled as compliant, or an unknown version accepted without schema review | Never — every report has a version | The field is absent from the report |
| b2 Percentiles monotone | `percentiles_monotone` | Every released reduced/full grid is non-decreasing in probability order | Any released grid is out of order | The tier released no percentile grids — declare with that reason | No numeric block carries percentiles and the tier says it should have |
| b3 Category counts ≤ row count | `category_counts_le_rowcount` | Every level count, and each column's level total, is ≤ `row_count` (the exact reconciliation of a level total against the block's `n` and `nonmissing_n` is b5's disclosure finding) | Any count or total exceeds `row_count` | The report declares no categorical columns — declare with that reason | `row_count` is absent, so no comparison basis exists |
| b4 Missingness in [0,1] | `missing_rate_in_unit_interval` | Every `missing_rate` is a finite real in the unit interval and agrees with `nonmissing_n` | Any rate outside [0,1] or disagreeing with `nonmissing_n` beyond rounding | T1 releases no rates — declare with that reason | A rate is present but non-numeric, so the interval test could not run |
| b5 No sub-threshold cells | `no_subthreshold_cells` | No **visible** count is sub-threshold — neither a categorical level or `__OTHER__` count below the effective threshold (including 0), nor a cross-tab cell that is negative or in `(0, effective threshold)`; a visible cross-tab `0` is a legitimate structural zero. The effective threshold is `max(declared, approved)`: the report's `settings.suppression_threshold` and the approved threshold recorded in STATE.md § Synthetic Path Tracking (**Suppression Threshold**, set at PSU-DS1). A report that declares more than was approved is held to its stricter value; one that declares less is b8's finding. Every categorical block also reconciles, so no hidden count is recoverable by differencing: its `n` is a whole number equal to its column's `nonmissing_n`; when `n` is below the effective threshold no level is released; otherwise its level counts (`__OTHER__` included) sum to exactly `n` | Any visible count is sub-threshold, or a categorical block does not reconcile — no whole-number `n` and `nonmissing_n`, `n` ≠ `nonmissing_n`, levels released below the threshold, or level counts that do not sum to `n` (the residual is a count anyone can recover by subtraction; CPS-INTAKE's `no_released_count_below_threshold` fails the same report). **Both are disclosure events** — notify the user. A sweep that covers fewer blocks than the report declares (scan shortfall) is also `[BLOCKER]`, mirroring CPS-INTAKE's `[FAIL] no_released_count_below_threshold: scanned N of M declared blocks — the sweep is incomplete` | **Never declarable** (§ QAS Severity Overrides) | The declared or approved threshold is missing, so the sweep has no gate to test against. A declared block the sweep did not reach is not this: it is the scan-shortfall `[BLOCKER]` finding, never `[NOT VERIFIED]`. **`[NOT VERIFIED]` here is a BLOCKER** |
| b6 Correlation matrices well-formed (T3) | `correlation_matrix_wellformed` | Available matrices are square, symmetric, unit-diagonal, entries in [-1,1] | Any released matrix violates one of those | Tier < 3, or every matrix is `available:false` with a recorded reason — declare with that reason | Tier is 3 and the `pearson` block is absent entirely |
| b7 Correlation PSD-tolerant (T3) | `correlation_psd_tolerant` | Smallest eigenvalue ≥ `-1e-6` | Large negative eigenvalue (corruption). Mild negatives are **WARNING** — project to nearest PD and note the perturbation | Tier < 3, or no available matrix — declare with that reason | The eigendecomposition could not be computed on the released matrix |
| b8 Suppression settings recorded | `suppression_settings_recorded` | `settings.tier` and `settings.suppression_threshold` present; `settings.tier` ≤ the approved tier recorded in STATE.md § Synthetic Path Tracking (**Disclosure Tier**, set at PSU-DS1; at T4, the **T4 Companion Profile Tier** approved for the companion profiler run); `settings.suppression_threshold` ≥ the approved threshold recorded in the same section (**Suppression Threshold**, set at PSU-DS1); `settings.relationship_spec` is `null` or a list of pairs; no `relationships` block carrying content (anything other than absent, `null`, or an empty object or array) when the approved tier or `settings.tier` is below 3 | Either setting missing, `relationship_spec` is neither shape, the report's `settings.tier` exceeds the approved tier (the profiler released blocks the researcher did not approve — CPS-INTAKE's `no_released_count_below_threshold` fails the same report), the report releases a `relationships` block below tier 3 (relationships are a tier-3 release — CPS-INTAKE fails the same report), or the report's threshold is below the approved one (the profiler ran with a weaker gate than the researcher approved). The last three are **also disclosure events**: request a corrected local re-run at the approved settings, and never raise the approved tier or lower the approved threshold to match the report | Never — every report carries settings | The `settings` object itself is absent, or STATE.md records no approved tier or threshold to compare against |
| b9 Column blocks match role and support | `column_blocks_match_role_and_support` | Each column matches the exact `2.0` shape for its role and support level, on the same support bands CPS-INTAKE enforces in its support gate (owned by `no_released_count_below_threshold`; bands from `profiling-script-spec.md` § Numeric shapes, § Categorical and string structure, § Relationships). With G the effective threshold (as in b5) and f the full-summary cutoff (`settings.full_summary_cutoff`, max(k, 10)), where `n` is the block's own support: a numeric block is `all_missing` or `withheld` (`no_finite_values`) at n = 0, `withheld` (`insufficient_support`) at 0 < n < G, `constant` only at n ≥ G, `small_n` (quartiles only) only at G ≤ n < f, and the full summary only at n ≥ f and n ≥ G; a full `string_structure` (string or identifier column) needs n ≥ G, otherwise the withheld shape; an available named relationship needs n ≥ f, and each of its complement groups (records with one of the pair's values but not the other: each pair column's numeric-block `n` minus the entry's pair-complete `n`) must be 0 or ≥ G, otherwise the entry is `available: false` with reason `small_complement_group`; an available Cramér's V needs n ≥ G. The complement-group gate is judged one regression at a time. Several named regressions that share a column, whose pair-complete records differ by only a few records, can together reveal that column's mean over those records; that is an accepted T3 linked-release residual (`disclosure-tiers.md` § T3, *Linked-release residuals (accepted)*), not a finding | Any released summary below its required support — a numeric shape richer than its `n` allows, a full `string_structure` below G, an available named relationship or Cramér's V below its minimum, or an available named relationship with a non-empty complement group below G (the regression plus the released marginal mean reveals the mean over those few records). That is **also a disclosure event** (CPS-INTAKE's support gate fails the same report): notify the user and request a corrected local re-run. Also BLOCKER: missing support, or an extra forbidden value field | T1 columns are exactly `{name,dtype}` — declare with that reason | The `columns` array is absent or empty |
| b10 Embedded validation complete and honest | `embedded_validation_complete` | All seven required named checks present, non-duplicated, each with a non-empty reason; applicable checks PASS; inapplicable ones explicitly NOT_APPLICABLE; `all_passed` true. Every reason is one of the profiler's own fixed forms: `candidate_fields_checked` on a PASS, and on a NOT_APPLICABLE one of the no-target / tier / unavailable forms CPS-INTAKE accepts (`agent_reference/VALIDATION_CHECKPOINTS.md` § CPS Usage Notes, `no_raw_value_shaped_fields` rule 5). The profilers take no researcher declarations, so no reason is ever free text | Any required check absent or duplicated, a status/applicability disagreement, or `all_passed` absent/false. Also BLOCKER: any reason outside the profiler's fixed forms — the profilers have no declaration setting, so such a reason means a modified template or a hand-edited report (CPS-INTAKE `[FAIL] no_raw_value_shaped_fields: validation.checks[<i>].reason is outside the spec vocabulary`) | Never — the embedded check set is required at every tier | The `validation` object is absent or is not a list of check records |
| b11 Cross-tab schema well-formed (T3) | `crosstab_schema_wellformed` | `relationships.crosstabs` is an array of objects; every available entry has positive whole-number `rows` and `cols` and a `cells` array; `cells` length = `rows`×`cols`; suppressed cells are `null`; `cells_suppressed` equals the `null` count; unavailable entries carry no dimensions; every available entry carries a whole-number `n`, its visible cells never sum past `n`, and an entry with no `null` cell sums to exactly `n`. A visible `0` is a legitimate structural zero, not a finding in itself: a hidden cell mis-coded as `0` surfaces here as a `cells_suppressed` that disagrees with the `null` count | Any of those fails — signals a malformed or tampered report. A cell sum that does not reconcile with `n` (past it, or short of it with no hidden cell), or an entry with no whole-number `n` to reconcile against, is `[BLOCKER]` and **also a disclosure event**: `n` minus the visible sum is a count recoverable by differencing (CPS-INTAKE's `crosstab_schema_and_suppression` fails the same report). A structurally malformed entry is this finding, never a gap in evidence: an available entry with no positive whole-number `rows`/`cols` and `cells` array is `[BLOCKER]` because its grid cannot be reshaped, mirroring CPS-INTAKE's `[FAIL] crosstab_schema_and_suppression: entry <label> has no positive integer rows/cols with a cells array — the grid cannot be reshaped` | **Never declarable** (§ QAS Severity Overrides) — at tier < 3 the check runs and reports `[PASS] …: 0 cross-tab entries declared at tier {t}` | Reserved for evidence the reviewer could not obtain — the report file is absent or did not parse, so no entry could be examined. A malformed entry the reviewer *can* read is the BLOCKER finding, not this. **`[NOT VERIFIED]` here is a BLOCKER** |
| b12 No recoverable suppressed cross-tab cell (T3) | `no_lone_suppressed_cell` | The key keeps its original name for stability; the check covers every recoverable cell, not only lone ones. No hidden cell is recoverable from its own entry together with the released row and column totals. Read each entry's `null` cells as edges between their row and column: no such edge may be a **bridge**, meaning an edge on no cycle of hidden cells. The lone suppressed cell, the only `null` in its row or column, is the simplest bridge. A `null` cell joining two otherwise separate groups of hidden cells is a bridge even though every row and column holds two or more `null`s. The exemption applies only when the entry is `"collapsed": true` **and every one of its cells is `null`**, so it covers only a fully hidden grid. Every entry also sits on the released categories and on its own pair. No entry pairs a column with itself, and no two entries share an unordered pair. Each available entry's `rows` and `cols` equal the number of released levels in its pair columns' categorical blocks, because levels pooled into `__OTHER__` form one pooled row or column and never get rows or columns of their own. **Missing-partner counts** are covered too: a cross-tab counts only records with both values, while each categorical block counts every record with a value, so a level's released count minus its cross-tab row total is the number of records with that level whose partner is missing. Re-derive these from the released totals (level counts, `nonmissing_n`, `row_count`, the entry's `n`) and confirm the entry's own released cells make no below-threshold non-zero one recoverable. Counts that released `n` and missing counts reveal on their own, with no released cell involved (for example a column with a single released category), and the count of records missing both values (derivable from the pair `n`) are accepted residuals, not findings. *Reviewer awareness, not a BLOCKER condition:* the report's Cramér's V values are computed on the full table (unpooled, unsuppressed) and rounded to 6 decimals. Combined with the released category counts, they can let a determined analyst reconstruct small cross-tab cells, including for pairs with no cross-tab entry, and undo `__OTHER__` pooling, recovering the rare pooled levels' counts and how they spread across the partner column (their labels stay unknown). This check does not cover that channel. It is the accepted T3 residual risk (`.claude/skills/synthetic-data-workflow/references/disclosure-tiers.md` § T3), so do not raise it as a finding. *Also reviewer awareness, not a BLOCKER condition:* the check judges each entry on its own, and the one-entry-per-pair rule compares column names. Entries read together can still disclose: several cross-tabs sharing a column whose partners are missing on the same or overlapping records can jointly pin a small missing-partner count, and two entries on two encodings of one variable (a code column and its label column) with the same partner are two differently suppressed copies of one table. These are accepted T3 linked-release residuals (same file, § T3, *Linked-release residuals (accepted)*) that no validator detects, so do not raise them as findings | Any lone suppressed cell or other bridge survives. **Also a disclosure event**: the cell is recoverable exactly by differencing against the margins (CPS-INTAKE `[FAIL] crosstab_schema_and_suppression: entry <label> leaves a lone hidden cell in row index <i> — recoverable by differencing`, the same form for a column, or `… leaves hidden cell at row index <i>, column index <j> recoverable from the released totals`). Also `[BLOCKER]` and the same kind of disclosure event: the released cells make a below-threshold non-zero missing-partner count recoverable (CPS-INTAKE's `crosstab_schema_and_suppression` fails the entry, naming only the entry and the missing-partner cell's row or column index, never the value); an entry that pairs a column with itself; a second entry on the same unordered pair, since two differently suppressed tables of one pair can be combined to recover cells; or an available entry whose `rows`/`cols` differ from its pair columns' released level counts, or whose pair column has no categorical block. A pooled level with a visible row or column of its own, subtracted from `__OTHER__`, recovers a rare count. CPS-INTAKE's `crosstab_schema_and_suppression` fails the same report. The fix is a local re-run of the current shipped profiler template, with only its config block edited. Where the report repeated a pair, that config needs a corrected `RELATIONSHIP_SPEC`. An entry marked `"collapsed": true` that still releases a visible cell is `[BLOCKER]` and the same disclosure event: the flag would otherwise switch off the lone-cell and bridge scan while recoverable cells stay released (CPS-INTAKE `[FAIL] crosstab_schema_and_suppression: entry <index> is marked collapsed but still releases visible cells`). An available entry whose grid cannot be reshaped to `rows`×`cols` is also `[BLOCKER]` here: the lone-cell and bridge scan cannot clear it, and the malformation is b11's finding (CPS-INTAKE `[FAIL] crosstab_schema_and_suppression: … the grid cannot be reshaped`) | **Never declarable** (§ QAS Severity Overrides) — at tier < 3 the check runs and reports `[PASS] …: 0 cross-tab entries declared at tier {t}` | Reserved for evidence the reviewer could not obtain — the report file is absent or did not parse, so no grid could be examined. An unreshapeable grid is the BLOCKER finding, not this. **`[NOT VERIFIED]` here is a BLOCKER** |

### QAS-C: Synthetic-vs-Profile Review (DS-5)

**Trigger:** After the synthetic parquet is written to `data/synthetic/` and the CPS-GEN validator script has run — or, at T4 with no profile report, after the import, with CPS-GEN recorded `EXEMPT (T4, no profile report)` (see **At T4** below the table).

**Default Checks:** (compare **only available targets**; a withheld distribution or an unavailable relationship is `[SKIPPED]` with the report's own recorded reason, never a fabricated PASS)

| Check | Key | Validates | BLOCKER If | Not Applicable (`[SKIPPED]`) | Not Verifiable (`[NOT VERIFIED]`) |
|-------|-----|-----------|------------|------------------------------|-----------------------------------|
| c1 Row count matched | `row_count_matched` (QAS-C key; CPS-GEN's counterpart is `row_count_matches`) | `nrow(synthetic) == report.row_count` | The counts differ | Never — every generation has a row target | The synthetic file could not be read, or `row_count` is absent |
| c2 Column set and types matched | `column_set_and_types` (QAS-C key; CPS-GEN's counterpart is `column_set_and_dtypes`) | Column names and dtypes match the report | Any name or dtype differs | Never — structural fidelity applies at every tier including T1 | The report declares no columns, or the parquet schema could not be read |
| c3 Numeric marginals within tolerance | `numeric_marginals_within_tolerance` | Reproduced percentiles within § Tolerances of the reported values | — (out of tolerance is **WARNING**) | The report released no numeric distribution targets (all withheld/all-missing, or T1) — declare with that reason | A target exists but the synthetic column is absent or entirely null; or the released grids yielded zero comparable percentiles (a check that compared nothing is never a PASS) |
| c4 Categorical proportions within tolerance | `categorical_proportions_within_tolerance` | Level proportions within ±0.02 absolute | — (out of tolerance is **WARNING**) | The report released no categorical level targets — declare with that reason | A target exists but the synthetic column is absent; or the released level sets yielded zero comparable proportions (a check that compared nothing is never a PASS) |
| c5 `__OTHER__` preserved as a bucket | `other_bucket_preserved` | The pooled bucket survives as a bucket; generation did not invent real-looking rare values in its place | The bucket was replaced by invented values | **Never declarable** (§ QAS Severity Overrides) — with no `__OTHER__` in the report the check runs and reports `[PASS] …: 0 pooled buckets declared, 0 invented levels` | The synthetic level inventory could not be built. **`[NOT VERIFIED]` here is a BLOCKER** |
| c6 Correlations within tolerance (T3) | `correlations_within_tolerance` | Synthetic correlation matrix within ±0.10 per released pair — CPS-GEN's single `correlation_tolerance`. A pair involving a binary/low-cardinality column may be accepted up to ±0.20 as a **QAS-C reviewer allowance only**: CPS-GEN does not apply that band and still reports such a pair as `[WARNING]`; the review cites the allowance when it explains that warning | — (out of tolerance is **WARNING**) | The report's tier (at T4, its own `settings.tier`) is < 3, or the matrix is `available:false` — declare with that reason | Tier is 3 but the report carries no `pearson` block (missing evidence, not a declared absence — CPS-GEN emits `[NOT VERIFIED] correlations_within_tolerance`); an available matrix yielded zero comparable pairs (a check that compared nothing is never a PASS); or the synthetic columns cannot support a recomputation |
| c7 No fabricated hidden categories | `no_fabricated_categories` | Every non-null synthetic category falls inside the emitted levels. A column whose level list is empty may carry only the literal `__OTHER__` (when its `n_levels_binned > 0`, every source level was pooled) or null; null is no fabricated category, but an all-null column may cost a `missingness_within_tolerance` WARNING (c9) against its reported missing rate | Any synthetic level lies outside the released set (`""` included) | **Never declarable** (§ QAS Severity Overrides) | The released level set could not be assembled. **`[NOT VERIFIED]` here is a BLOCKER** |
| c8 Identifier scaffolds typed and value-free | `identifier_scaffolds_typed_value_free` | Generated identifiers match declared types and available structure, use non-routable email domains, and carry no released value | Any identifier violates its declared type/structure or uses a routable domain | **Never declarable** (§ QAS Severity Overrides) — with no identifier columns the check runs and reports `[PASS] …: 0 identifier columns declared` | The identifier column set could not be resolved. **`[NOT VERIFIED]` here is a BLOCKER** |
| c9 Missingness within tolerance | `missingness_within_tolerance` | Per-column null rate within ±0.01 of the reported rate | — (out of tolerance is **WARNING**) | T1 carries no missingness targets — declare with that reason | A rate target exists but the synthetic column is absent |
| c10 Seed recorded | `seed_recorded` | The generation log carries the seed (at T4, the seed from the user's generation log) | The seed is absent and the T4 exception below is not in force; or CPS-GEN's `seed_exception` is set at tier 1–3, or alongside `seed` (both are CPS-GEN `[FAIL]`s). **BLOCKER by default** — the sole carve-out is the researcher-authorized T4 missing-seed path (`WORKFLOW_PHASE_DO_SYNTHETIC.md` § T4 Variant): tier 4, `seed` unset, `seed_exception` set, and the authorization recorded in STATE.md § Synthetic Path Tracking > T4 Missing-Seed Exception. That case is a **WARNING**, mirroring CPS-GEN's `[WARNING] seed_recorded: tier 4 import with no recorded seed — researcher-authorized non-reproducible T4 exception (authorization recorded in STATE)`. The orchestrator obtains the authorization from the researcher; the reviewer confirms it is recorded and never grants it | Never — reproducibility is required at every tier | The generation log could not be read |
| c11 Named relationship reproduced (T3) | `named_relationship_reproduced` | Synthetic OLS slope of `outcome ~ predictor` within ±10% of the reported slope; R² within ±0.10 | — (out of tolerance is **WARNING**) | Tier < 3, or `relationships.named` is empty / all `available:false` — declare with that reason | A named entry is available but the synthetic columns cannot support the regression |

**At T4 (user-run local synthesis).** DS-5 imports the user's synthetic rows with `scripts/synth_generate/01_import-synthetic.{py,R}`. **With a profile report**, CPS-GEN is embedded at the end of that script and runs in full with `tier = 4` (the report's own `settings.tier` governs which blocks are expected), and QAS-C reviews it and the report as above. **Without a profile report**, CPS-GEN is not run and STATE records its row as `EXEMPT (T4, no profile report)`; QAS-C then validates against the user's declared metadata (row count, column set/types, declared marginals) and applies c10 to the user's generation log. Treat an `EXEMPT` CPS-GEN row as a **BLOCKER** at tier 1–3 or when a profile report did cross — a report present means CPS-GEN runs. A CPS-GEN run with `report_path` unset is not an exemption: its `[NOT VERIFIED]` lines force `FAILED`.

### QAS Applicability Declarations

QAS-B and QAS-C review scripts carry the same `not_applicable` mapping as every other review template (§ Template Applicability Keys), keyed by the stable keys in the tables above:

```python
not_applicable = {}  # e.g. {"correlation_matrix_wellformed": "tier 2 — the report releases no correlations"}
```
```r
not_applicable <- list()  # e.g. list(correlation_matrix_wellformed = "tier 2 — the report releases no correlations")
```

**QAS-A has no `not_applicable` mapping at all.** Every a-check runs on every QAS-A review. Where a tier makes a check vacuous (no cross-tab paths at T2, no synthesizer at T1-T3), the check still runs and emits an evidence-bearing `[PASS]` stating the zero — `0 cross-tab emission paths reachable at tier 2` — because "there was nothing to check" is itself a finding the reviewer must establish rather than assume.

**Non-declarable keys (disclosure-safety overrides).** No `not_applicable` entry may exist for any QAS-A key (a1-a11), for QAS-B `no_subthreshold_cells`, `crosstab_schema_wellformed`, `no_lone_suppressed_cell`, or for QAS-C `other_bucket_preserved`, `no_fabricated_categories`, `identifier_scaffolds_typed_value_free`. **Declaring one of these keys is itself the finding:** the review emits `[BLOCKER] <key>: declared not_applicable — disclosure-safety checks may never be declared not applicable`, quoting the offending key, and the check still runs. The script-halting counterparts (CPS-INTAKE, CPS-GEN) enforce the equivalent rule with `[FAIL]` in place of `[BLOCKER]`, but under their own key names and not over an identical set: the CPS keys cover the union of the behaviours these review keys name, so their non-declarable sets are drawn from the CPS check lists rather than mapped key-for-key, and CPS-GEN additionally treats `seed_recorded` as non-declarable, which has no QAS-C counterpart in the list above. Read the authoritative CPS non-declarable lists from `agent_reference/VALIDATION_CHECKPOINTS.md` § CPS Usage Notes rather than mapping them off this paragraph.

### QAS Count Line and Verdict

Every QAS review prints a count line immediately before its verdict, and derives the verdict from the counters:

```
Checks: {passed} passed, {warnings} warnings, {blockers} blockers, {not_verified} not verified, {skipped} skipped, {info} info
QAS-B RESULT: PASSED | WARNING | BLOCKER
```

- **QAS-B and QAS-C:** `BLOCKER` if `blockers > 0`; else `WARNING` if `warnings > 0` or `not_verified > 0`; else `PASSED`. A run with zero substantive checks (`passed == 0`) is `WARNING`.
- **QAS-A:** `BLOCKER` if `blockers > 0` **or `not_verified > 0`** (§ QAS Severity Overrides); else `PASSED`. A run with zero substantive checks is `BLOCKER`, not `WARNING`. **`WARNING` is not a legal QAS-A verdict** — the count line still reports a `warnings` column so the shape is uniform across the family, but any finding severe enough to warrant a warning on this checkpoint is a BLOCKER, because an uncertain disclosure path is an unsafe one.
- The count line keeps the `not_applicable`-free QAS-A honest: an all-zero `skipped` column is what a reviewer should see, and a nonzero one is a contract violation.

Identifiers `QAS-A`, `QAS-B`, `QAS-C` contain no `QA\d` substring, so they are safe against the log comparator's checkpoint-verdict heuristic. As everywhere else, no checkpoint identifier appears on a per-check line.

### QAS Script Naming Convention

```
scripts/cr/
  qas_b_report-consistency.py     # QAS-B review scripts (append _cr{N} for revisions)
  qas_c_synthetic-validation.py   # QAS-C review scripts
```

(`.R` in place of `.py` for R projects.) QAS-A produces no script — it is a static review of the outbound script, optionally supported by a synthetic-toy-input probe under `scripts/scratch/`.

> **Note:** The QAS-A/B/C check tables above are agent checklists, not script templates — this document carries no per-check QAS code, only the `not_applicable` config shape above. The code-reviewer writes each QAS script following the QA1-QA4b template patterns (accumulator counters, one line per check, derived verdict) with the QAS keys from the tables. The in-script synthetic-path checkpoints are separate and live in `agent_reference/VALIDATION_CHECKPOINTS.md` (CPS-INTAKE, CPS-GEN).

---

## Anti-Patterns

**DO NOT skip QA for "simple" scripts.** Even simple fetch or filter operations can produce surprising results. Every Stage 5-8 script gets a QA checkpoint.

**DO NOT conflate CP and QA failures.** A script can pass CP3 but fail QA3 if the validation was inadequate. QA catches what CP misses.

**DO NOT create QA-of-QA loops.** QA scripts themselves don't need secondary review. If a QA script fails, debug the QA script or the original script, not both recursively.

**DO NOT treat all BLOCKERs the same.** Methodology BLOCKERs escalate immediately. Technical BLOCKERs get revision attempts.

**DO NOT proceed with unresolved BLOCKERs.** The entire point of QA is to catch issues early. Proceeding with known BLOCKERs defeats the purpose.

**DO NOT write QA scripts that only re-run the original script's checks.** QA value comes from orthogonal validation — checking from a different angle. If your QA script duplicates the original's checks with no additions, you've added audit trail but not safety.

**DO NOT issue PASSED without articulating WHY.** "All checks passed" is not a QA finding — it's an absence of findings. A proper PASSED includes reasoning: what you looked for, what alternative failure modes you considered, and why you're confident the code is correct. (Script-author-facing counterpart: `VALIDATION_CHECKPOINTS.md` § Validation Integrity Anti-Patterns, "Hard-Coded PASS Verdicts" — derive, never assert.)

**DO NOT emit PASS without evidence.** A `[PASS]` line whose condition is vacuously true — `all()` over an empty list, `setdiff(NULL, x)`, `"" in text`, `None is False`, a comparison whose guard short-circuited on a falsy `0` — asserts a property nothing established. Every PASS line carries the numbers that establish it: the counts compared, the rate recomputed, the threshold and the observed value. If the inputs to a check are absent, the honest outcome is `[NOT VERIFIED]` naming exactly what was missing, never a pass. This is the defect class the templates in this document were rebuilt to eliminate; do not reintroduce it in the discretionary checks you add.

**DO NOT silently skip a check.** A check that produces no output when its configuration is absent is invisible in the log and invisible in the verdict — the reviewer reads a clean run and cannot tell that half the checkpoint never executed. Every check emits exactly one line on every path: `[SKIPPED]` with a declared reason when it is genuinely not applicable, `[NOT VERIFIED]` when its inputs are missing, otherwise a real outcome. `continue`, `next`, and empty `if` bodies that produce no line are the mechanism of the silent skip; count and print instead.
