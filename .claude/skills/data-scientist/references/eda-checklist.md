# EDA Checklist

Detailed procedures for exploratory data analysis. Follow these checks BEFORE performing any analysis or transformation.

## Contents

- [Initial Data Inspection](#initial-data-inspection)
- [Missing Value Analysis](#missing-value-analysis)
- [Distribution Analysis](#distribution-analysis)
- [Outlier Detection](#outlier-detection)
- [Uniqueness and Cardinality](#uniqueness-and-cardinality)
- [Correlation Analysis](#correlation-analysis)
- [Automated Profiling Tools](#automated-profiling-tools)

## Initial Data Inspection

Run these checks immediately after loading ANY new dataset.

### Basic Shape and Structure

**Python:**
```python
import polars as pl

# Load data
df = pl.read_csv("data.csv")

# Basic inspection
print(f"Shape: {df.shape[0]} rows x {df.shape[1]} columns")
print(f"Columns: {df.columns}")
print(f"Memory usage: {df.estimated_size() / 1024 / 1024:.2f} MB")
```

**R:**
```r
library(readr)
library(dplyr)

# Load data
df <- read_csv("data.csv")

# Basic inspection
cat(sprintf("Shape: %d rows x %d columns\n", nrow(df), ncol(df)))
cat("Columns:", paste(names(df), collapse = ", "), "\n")
cat(sprintf("Memory usage: %.2f MB\n", object.size(df) / 1024 / 1024))
```

### Data Types

**Python:**
```python
# Check types - look for unexpected types
print("Data types:")
for col in df.columns:
    print(f"  {col}: {df[col].dtype}")

# Common issues to look for:
# - Dates stored as strings
# - Numbers stored as strings (often due to formatting or special values)
# - Mixed types (will show as Object/String)
```

**R:**
```r
# Check types - look for unexpected types
cat("Data types:\n")
for (col in names(df)) {
  cat(sprintf("  %s: %s\n", col, class(df[[col]])))
}

# Common issues to look for:
# - Dates stored as character
# - Numbers stored as character (often due to formatting or special values)
# - Mixed types (will show as character)
```

### Preview Data

**Python:**
```python
# Multiple views to catch different issues
print("First 5 rows:")
print(df.head())

print("\nLast 5 rows:")  # Often reveals truncation or footer issues
print(df.tail())

print("\nRandom sample:")  # Avoids bias from sorted data
print(df.sample(5, seed=42))
```

**R:**
```r
# Multiple views to catch different issues
cat("First 5 rows:\n")
print(head(df, 5))

cat("\nLast 5 rows:\n")  # Often reveals truncation or footer issues
print(tail(df, 5))

cat("\nRandom sample:\n")  # Avoids bias from sorted data
set.seed(42)
print(df |> slice_sample(n = 5))
```

### Column Name Issues

**Python:**
```python
# Check for problematic column names
for col in df.columns:
    issues = []
    if col != col.strip():
        issues.append("leading/trailing whitespace")
    if col != col.lower():
        issues.append("mixed case")
    if " " in col:
        issues.append("contains spaces")
    if issues:
        print(f"Column '{col}': {', '.join(issues)}")
```

**R:**
```r
# Check for problematic column names
for (col in names(df)) {
  issues <- c()
  if (col != trimws(col)) issues <- c(issues, "leading/trailing whitespace")
  if (col != tolower(col)) issues <- c(issues, "mixed case")
  if (grepl(" ", col)) issues <- c(issues, "contains spaces")
  if (length(issues) > 0) {
    cat(sprintf("Column '%s': %s\n", col, paste(issues, collapse = ", ")))
  }
}
```

## Missing Value Analysis

Understanding missingness patterns is CRITICAL. Different patterns require different handling.

### Count and Percentage

**Python:**
```python
# Missing value summary
null_counts = df.null_count()
null_pcts = (df.null_count() / len(df) * 100)

print("Missing values:")
for col in df.columns:
    count = null_counts[col].item()
    pct = null_pcts[col].item()
    if count > 0:
        print(f"  {col}: {count} ({pct:.1f}%)")
```

**R:**
```r
# Missing value summary
cat("Missing values:\n")
for (col in names(df)) {
  count <- sum(is.na(df[[col]]))
  pct <- count / nrow(df) * 100
  if (count > 0) {
    cat(sprintf("  %s: %d (%.1f%%)\n", col, count, pct))
  }
}
```

### Patterns of Missingness

Three types of missingness (important for handling strategy):

| Pattern | Description | Detection | Handling |
|---------|-------------|-----------|----------|
| **MCAR** | Missing Completely At Random | Missingness unrelated to any data | Safe to drop or impute |
| **MAR** | Missing At Random | Missingness depends on observed data | Impute using related columns |
| **MNAR** | Missing Not At Random | Missingness depends on unobserved data | Requires domain knowledge |

**Python:**
```python
# Visual inspection of missingness patterns
# Look for: columns that are always missing together

# Check if missingness correlates across columns
missing_cols = [col for col in df.columns if df[col].null_count().item() > 0]
if len(missing_cols) > 1:
    # Create missingness indicator DataFrame
    missing_indicators = df.select([
        pl.col(col).is_null().alias(f"{col}_missing")
        for col in missing_cols
    ])
    # Correlation of missingness patterns
    print("Missingness correlation (high = missing together):")
    # Examine cross-tabulations of missingness
```

**R:**
```r
# Visual inspection of missingness patterns
# Look for: columns that are always missing together

# Check if missingness correlates across columns
missing_cols <- names(df)[sapply(df, \(x) any(is.na(x)))]
if (length(missing_cols) > 1) {
  # Create missingness indicator data frame
  missing_indicators <- df |>
    select(all_of(missing_cols)) |>
    mutate(across(everything(), is.na))
  # Correlation of missingness patterns
  cat("Missingness correlation (high = missing together):\n")
  print(cor(missing_indicators))
}
```

### Special Missing Value Codes

Data often uses special values instead of null:

**Python:**
```python
# Common special values to check for
special_values = ["", "N/A", "NA", "n/a", "null", "NULL", "None", "-", "--", ".", "?", "-999", "9999"]

for col in df.select(pl.col(pl.String)).columns:
    value_counts = df[col].value_counts()
    for sv in special_values:
        count = value_counts.filter(pl.col(col) == sv)
        if len(count) > 0:
            print(f"Column '{col}' has {count[0, 'count']} instances of '{sv}'")
```

**R:**
```r
# Common special values to check for
special_values <- c("", "N/A", "NA", "n/a", "null", "NULL", "None", "-", "--", ".", "?", "-999", "9999")

char_cols <- names(df)[sapply(df, is.character)]
for (col in char_cols) {
  for (sv in special_values) {
    count <- sum(df[[col]] == sv, na.rm = TRUE)
    if (count > 0) {
      cat(sprintf("Column '%s' has %d instances of '%s'\n", col, count, sv))
    }
  }
}
```

## Distribution Analysis

### Numerical Columns

**Python:**
```python
# Summary statistics
print(df.describe())

# For each numerical column, check:
for col in df.select(pl.col(pl.NUMERIC_DTYPES)).columns:
    stats = df.select([
        pl.col(col).min().alias("min"),
        pl.col(col).quantile(0.25).alias("q25"),
        pl.col(col).median().alias("median"),
        pl.col(col).mean().alias("mean"),
        pl.col(col).quantile(0.75).alias("q75"),
        pl.col(col).max().alias("max"),
        pl.col(col).std().alias("std"),
        pl.col(col).skew().alias("skew"),
    ])
    print(f"\n{col}:")
    print(stats)
    
    # Red flags:
    # - Large difference between mean and median (skewness)
    # - Min or max far from quartiles (outliers)
    # - Std = 0 (constant column)
```

**R:**
```r
# Summary statistics
print(summary(df))

# For each numerical column, check:
num_cols <- names(df)[sapply(df, is.numeric)]
for (col in num_cols) {
  vals <- df[[col]]
  cat(sprintf("\n%s:\n", col))
  cat(sprintf("  min: %s, q25: %s, median: %s, mean: %s, q75: %s, max: %s, sd: %s, skew: %s\n",
              format(min(vals, na.rm = TRUE), big.mark = ","),
              format(quantile(vals, 0.25, na.rm = TRUE), big.mark = ","),
              format(median(vals, na.rm = TRUE), big.mark = ","),
              format(mean(vals, na.rm = TRUE), big.mark = ","),
              format(quantile(vals, 0.75, na.rm = TRUE), big.mark = ","),
              format(max(vals, na.rm = TRUE), big.mark = ","),
              format(sd(vals, na.rm = TRUE), big.mark = ","),
              format(moments::skewness(vals, na.rm = TRUE), digits = 3)))

  # Red flags:
  # - Large difference between mean and median (skewness)
  # - Min or max far from quartiles (outliers)
  # - Std = 0 (constant column)
}
```

### Categorical Columns

**Python:**
```python
# For each string/categorical column
for col in df.select(pl.col(pl.String)).columns:
    n_unique = df[col].n_unique()
    total = len(df)
    
    print(f"\n{col}:")
    print(f"  Unique values: {n_unique} ({n_unique/total*100:.1f}% of rows)")
    
    # Show top values
    print("  Top values:")
    print(df[col].value_counts().head(10))
    
    # Red flags:
    # - Very high cardinality (might be an ID column)
    # - Single value (constant column)
    # - Many low-frequency values (potential data quality issues)
```

**R:**
```r
# For each character/categorical column
char_cols <- names(df)[sapply(df, is.character)]
for (col in char_cols) {
  n_unique <- n_distinct(df[[col]])
  total <- nrow(df)

  cat(sprintf("\n%s:\n", col))
  cat(sprintf("  Unique values: %d (%.1f%% of rows)\n", n_unique, n_unique / total * 100))

  # Show top values
  cat("  Top values:\n")
  print(df |> count(.data[[col]], sort = TRUE) |> head(10))

  # Red flags:
  # - Very high cardinality (might be an ID column)
  # - Single value (constant column)
  # - Many low-frequency values (potential data quality issues)
}
```

### Date/Time Columns

**Python:**
```python
# For datetime columns
for col in df.select(pl.col(pl.TEMPORAL_DTYPES)).columns:
    print(f"\n{col}:")
    print(f"  Min: {df[col].min()}")
    print(f"  Max: {df[col].max()}")
    print(f"  Range: {df[col].max() - df[col].min()}")
    
    # Check for gaps in time series
    # Check for future dates (often errors)
    # Check for very old dates (often errors)
```

**R:**
```r
# For date/datetime columns
date_cols <- names(df)[sapply(df, \(x) inherits(x, c("Date", "POSIXct", "POSIXlt")))]
for (col in date_cols) {
  cat(sprintf("\n%s:\n", col))
  cat(sprintf("  Min: %s\n", min(df[[col]], na.rm = TRUE)))
  cat(sprintf("  Max: %s\n", max(df[[col]], na.rm = TRUE)))
  cat(sprintf("  Range: %s\n", difftime(max(df[[col]], na.rm = TRUE),
                                         min(df[[col]], na.rm = TRUE))))

  # Check for gaps in time series
  # Check for future dates (often errors)
  # Check for very old dates (often errors)
}
```

## Outlier Detection

### IQR Method

**Python:**
```python
# Detect outliers using IQR method
q1 = df[col].quantile(0.25)
q3 = df[col].quantile(0.75)
iqr = q3 - q1
lower_bound = q1 - 1.5 * iqr
upper_bound = q3 + 1.5 * iqr
outliers = df.filter((pl.col(col) < lower_bound) | (pl.col(col) > upper_bound))
print(f"'{col}': IQR bounds [{lower_bound:.2f}, {upper_bound:.2f}], {len(outliers)} outliers ({len(outliers)/len(df)*100:.1f}%)")
```

**R:**
```r
# Detect outliers using IQR method
q1 <- quantile(df[[col]], 0.25, na.rm = TRUE)
q3 <- quantile(df[[col]], 0.75, na.rm = TRUE)
iqr_val <- q3 - q1
lower_bound <- q1 - 1.5 * iqr_val
upper_bound <- q3 + 1.5 * iqr_val
outliers <- df |> filter(.data[[col]] < lower_bound | .data[[col]] > upper_bound)
cat(sprintf("'%s': IQR bounds [%.2f, %.2f], %d outliers (%.1f%%)\n",
            col, lower_bound, upper_bound, nrow(outliers), nrow(outliers) / nrow(df) * 100))
```

### Z-Score Method

**Python:**
```python
# Detect outliers using z-score method
mean = df[col].mean()
std = df[col].std()
threshold = 3.0
outliers = df.filter(((pl.col(col) - mean) / std).abs() > threshold)
print(f"'{col}': mean={mean:.2f}, std={std:.2f}, {len(outliers)} outliers with |z| > {threshold} ({len(outliers)/len(df)*100:.1f}%)")
```

**R:**
```r
# Detect outliers using z-score method
col_mean <- mean(df[[col]], na.rm = TRUE)
col_sd <- sd(df[[col]], na.rm = TRUE)
threshold <- 3.0
outliers <- df |> filter(abs((.data[[col]] - col_mean) / col_sd) > threshold)
cat(sprintf("'%s': mean=%.2f, sd=%.2f, %d outliers with |z| > %.1f (%.1f%%)\n",
            col, col_mean, col_sd, nrow(outliers), threshold, nrow(outliers) / nrow(df) * 100))
```

### Important: Investigate Before Removing

**NEVER automatically remove outliers.** Always:
1. Examine outlier records in full
2. Understand WHY they're outliers
3. Consult domain experts if available
4. Document decision and rationale

**Python:**
```python
# Examine outliers in context
outliers = detect_outliers_iqr(df, "amount")
if len(outliers) > 0:
    print("\nOutlier records (examine these!):")
    print(outliers.head(10))
```

**R:**
```r
# Examine outliers in context (using IQR method from above)
if (nrow(outliers) > 0) {
  cat("\nOutlier records (examine these!):\n")
  print(head(outliers, 10))
}
```

## Uniqueness and Cardinality

### Identifying Granularity

The most important question: **What does each row represent?**

**Python:**
```python
# Check if columns uniquely identify rows
unique_count = df.select(cols).n_unique()
is_unique = unique_count == len(df)
print(f"Columns {cols}: {unique_count:,} unique / {len(df):,} total → {'unique key' if is_unique else 'NOT unique'}")
```

**R:**
```r
# Check if columns uniquely identify rows
unique_count <- df |> distinct(across(all_of(cols))) |> nrow()
is_unique <- unique_count == nrow(df)
cat(sprintf("Columns [%s]: %s unique / %s total -> %s\n",
            paste(cols, collapse = ", "),
            format(unique_count, big.mark = ","), format(nrow(df), big.mark = ","),
            if (is_unique) "unique key" else "NOT unique"))
```

Test various candidate key combinations:

**Python:**
```python
for cols in [["id"], ["user_id"], ["user_id", "date"], ["user_id", "product_id", "timestamp"]]:
    unique_count = df.select(cols).n_unique()
    is_unique = unique_count == len(df)
    print(f"Columns {cols}: {unique_count:,} unique / {len(df):,} total → {'unique key' if is_unique else 'NOT unique'}")
```

**R:**
```r
candidate_keys <- list(c("id"), c("user_id"), c("user_id", "date"), c("user_id", "product_id", "timestamp"))
for (cols in candidate_keys) {
  unique_count <- df |> distinct(across(all_of(cols))) |> nrow()
  is_unique <- unique_count == nrow(df)
  cat(sprintf("Columns [%s]: %s unique / %s total -> %s\n",
              paste(cols, collapse = ", "),
              format(unique_count, big.mark = ","), format(nrow(df), big.mark = ","),
              if (is_unique) "unique key" else "NOT unique"))
}
```

### Duplicate Detection

**Python:**
```python
# Check for exact duplicate rows
n_duplicates = len(df) - len(df.unique())
print(f"Exact duplicate rows: {n_duplicates}")

# If duplicates exist, examine them
if n_duplicates > 0:
    # Find duplicate rows
    dup_counts = df.group_by(df.columns).len().filter(pl.col("len") > 1)
    print(f"\nDuplicate patterns ({len(dup_counts)} groups):")
    print(dup_counts.head(10))
```

**R:**
```r
# Check for exact duplicate rows
n_duplicates <- nrow(df) - nrow(distinct(df))
cat(sprintf("Exact duplicate rows: %d\n", n_duplicates))

# If duplicates exist, examine them
if (n_duplicates > 0) {
  dup_counts <- df |> group_by(across(everything())) |> summarise(n = n(), .groups = "drop") |> filter(n > 1)
  cat(sprintf("\nDuplicate patterns (%d groups):\n", nrow(dup_counts)))
  print(head(dup_counts, 10))
}
```

### Cardinality Analysis

| Cardinality Level | Typical Use | Example |
|-------------------|-------------|---------|
| 1 (constant) | Often useless, remove | All values are "USA" |
| Very low (2-10) | Binary/categorical | Gender, Status |
| Low (10-100) | Categorical | Category, Region |
| Medium (100-10k) | High-cardinality categorical | City, Product |
| High (>10k or unique) | ID column or free text | User ID, Comments |

**Python:**
```python
# Cardinality summary
print("Cardinality analysis:")
for col in df.columns:
    n_unique = df[col].n_unique()
    pct_unique = n_unique / len(df) * 100
    
    if n_unique == 1:
        category = "CONSTANT (consider removing)"
    elif n_unique == 2:
        category = "Binary"
    elif n_unique <= 10:
        category = "Low cardinality"
    elif n_unique <= 100:
        category = "Medium cardinality"
    elif pct_unique > 90:
        category = "HIGH (possible ID column)"
    else:
        category = "High cardinality"
    
    print(f"  {col}: {n_unique} unique ({pct_unique:.1f}%) - {category}")
```

**R:**
```r
# Cardinality summary
cat("Cardinality analysis:\n")
for (col in names(df)) {
  n_unique <- n_distinct(df[[col]])
  pct_unique <- n_unique / nrow(df) * 100

  category <- if (n_unique == 1) {
    "CONSTANT (consider removing)"
  } else if (n_unique == 2) {
    "Binary"
  } else if (n_unique <= 10) {
    "Low cardinality"
  } else if (n_unique <= 100) {
    "Medium cardinality"
  } else if (pct_unique > 90) {
    "HIGH (possible ID column)"
  } else {
    "High cardinality"
  }

  cat(sprintf("  %s: %d unique (%.1f%%) - %s\n", col, n_unique, pct_unique, category))
}
```

## Correlation Analysis

### Numerical Correlations

**Python:**
```python
# Pearson correlation for numerical columns
numeric_cols = df.select(pl.col(pl.NUMERIC_DTYPES)).columns
if len(numeric_cols) > 1:
    # Polars correlation
    corr_matrix = df.select(numeric_cols).corr()
    print("Correlation matrix:")
    print(corr_matrix)
    
    # Flag high correlations (potential multicollinearity)
    # Threshold typically 0.7-0.9
    threshold = 0.7
    print(f"\nHighly correlated pairs (|r| > {threshold}):")
    # ... extract pairs above threshold
```

**R:**
```r
# Pearson correlation for numerical columns
num_cols <- names(df)[sapply(df, is.numeric)]
if (length(num_cols) > 1) {
  corr_matrix <- cor(df |> select(all_of(num_cols)), use = "pairwise.complete.obs")
  cat("Correlation matrix:\n")
  print(round(corr_matrix, 3))

  # Flag high correlations (potential multicollinearity)
  threshold <- 0.7
  cat(sprintf("\nHighly correlated pairs (|r| > %.1f):\n", threshold))
  # Extract upper triangle pairs above threshold
  for (i in seq_len(ncol(corr_matrix) - 1)) {
    for (j in (i + 1):ncol(corr_matrix)) {
      if (abs(corr_matrix[i, j]) > threshold) {
        cat(sprintf("  %s - %s: %.3f\n", num_cols[i], num_cols[j], corr_matrix[i, j]))
      }
    }
  }
}
```

### Categorical Associations

For categorical columns, examine cross-tabulations:

**Python:**
```python
# Cross-tabulation
ct = df.group_by([col1, col2]).len().pivot(on=col2, index=col1, values="len").fill_null(0)
print(ct)
```

**R:**
```r
# Cross-tabulation
ct <- table(df[[col1]], df[[col2]])
print(ct)
```

## Automated Profiling Tools

For comprehensive automated profiling:

### ydata-profiling (formerly pandas-profiling)

**Python:**
```python
# Requires: pip install ydata-profiling
from ydata_profiling import ProfileReport

# Note: Requires pandas DataFrame
profile = ProfileReport(df.to_pandas(), title="Data Profile", explorative=True)
profile.to_file("data_profile.html")

# For large datasets, use minimal mode
profile = ProfileReport(df.to_pandas(), minimal=True)
```

**R:**
```r
# Requires: install.packages("skimr")
library(skimr)

# skimr provides a comprehensive profiling summary
skim(df)

# For HTML report output, use DataExplorer
# install.packages("DataExplorer")
# DataExplorer::create_report(df, output_file = "data_profile.html")
```

### Manual Profiling Summary

If automated tools unavailable, generate this summary:

**Python:**
```python
# Generate a quick profile summary
print(f"Shape: {df.shape}")
print(f"Columns: {df.columns}")
for col in df.columns:
    dtype = df[col].dtype
    nulls = df[col].null_count()
    uniques = df[col].n_unique()
    print(f"  {col}: {dtype}, {nulls} nulls, {uniques} unique")
print(f"\nNumeric summary:\n{df.select(pl.col(pl.NUMERIC_DTYPES)).describe()}")
```

**R:**
```r
# Generate a quick profile summary
cat(sprintf("Shape: %d x %d\n", nrow(df), ncol(df)))
cat("Columns:", paste(names(df), collapse = ", "), "\n")
for (col in names(df)) {
  dtype <- class(df[[col]])
  nulls <- sum(is.na(df[[col]]))
  uniques <- n_distinct(df[[col]])
  cat(sprintf("  %s: %s, %d NAs, %d unique\n", col, dtype, nulls, uniques))
}
cat("\nNumeric summary:\n")
print(summary(df |> select(where(is.numeric))))
```

## Red Flags Checklist

After completing EDA, check for these red flags:

- [ ] **High missingness** (>10%) in critical columns
- [ ] **Unexpected data types** (dates as strings, numbers as strings)
- [ ] **Constant columns** (only one unique value)
- [ ] **Near-constant columns** (one value dominates 99%+)
- [ ] **Unexpected duplicates** (should be unique but isn't)
- [ ] **Extreme outliers** (values orders of magnitude different)
- [ ] **Future dates** (often data entry errors)
- [ ] **Negative values** where only positive expected
- [ ] **High cardinality** where low expected (possible ID column mixed in)
- [ ] **Low cardinality** where high expected (possible data truncation)
- [ ] **Suspicious value distributions** (too perfect, too uniform)
- [ ] **Inconsistent encodings** (same thing represented differently)
