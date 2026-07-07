# IPEDS Institution Identifiers

Understanding UNITID, OPEID, and tracking institutions over time.

## Contents

- [Identifier Types](#identifier-types)
- [UNITID](#unitid)
- [OPEID](#opeid)
- [Linking UNITID and OPEID](#linking-unitid-and-opeid)
- [Institutional Changes](#institutional-changes)
- [Tracking Institutions Over Time](#tracking-institutions-over-time)
- [Linking to Other Data Sources](#linking-to-other-data-sources)
- [Common Issues](#common-issues)

## Identifier Types

IPEDS uses two main institutional identifiers:

| ID Type | Assigned By | Primary Use | Format |
|---------|-------------|-------------|--------|
| UNITID | NCES | IPEDS reporting | 6-digit integer |
| OPEID | Dept of Education | Title IV administration | 8-character string |

### Key Differences

| Aspect | UNITID | OPEID |
|--------|--------|-------|
| Granularity | Each IPEDS reporting unit | Institution + branches |
| Stability | Changes with major restructuring | More stable |
| Branch handling | Separate UNITIDs possible | Same OPEID6, different suffix |
| Other data sources | IPEDS, some Scorecard | FSA, NSLDS, College Scorecard |

## UNITID

### Definition

**UNITID** is a unique 6-digit identifier assigned by NCES to each institution reporting to IPEDS.

### Characteristics

| Characteristic | Description |
|----------------|-------------|
| Uniqueness | One UNITID per IPEDS reporting unit |
| Persistence | Remains same unless major change |
| Assignment | NCES assigns when institution enters IPEDS |
| Format | 6-digit integer (e.g., 110635) |

### When UNITID Changes

UNITID may change when:
- Institution merges with another
- Institution closes and reopens
- Major restructuring of multi-campus system
- Change in reporting structure (e.g., branches become separate)

### When UNITID Stays Same

UNITID typically remains the same when:
- Institution changes name
- Institution changes address
- Institution changes sector (public to private)
- Institution changes control (nonprofit to for-profit)
- Gradual programmatic changes

### Examples

```python
# Single UNITID
unitid = 110635  # UC Berkeley

# Multi-campus system - each campus has own UNITID
ucla = 110662
ucsd = 110680
ucsf = 110699

# But may share some system-level characteristics
```

```r
# Single UNITID
unitid <- 110635  # UC Berkeley

# Multi-campus system - each campus has own UNITID
ucla <- 110662
ucsd <- 110680
ucsf <- 110699

# But may share some system-level characteristics
```

## OPEID

### Definition

**OPEID** is the Office of Postsecondary Education Identifier used for federal student aid administration.

### Structure

| Component | Description | Example |
|-----------|-------------|---------|
| OPEID6 | First 6 characters - main institution | 001312 |
| OPEID8 | Full 8 characters - includes branch | 00131200 |
| Branch suffix | Last 2 characters | 00 = main, 01+ = branches |

### OPEID6 vs OPEID8

```python
# Main campus
opeid8 = "00131200"  # Main campus
opeid6 = "001312"    # Institution family

# Branch campuses share OPEID6
branch1 = "00131201"  # opeid6 = "001312"
branch2 = "00131202"  # opeid6 = "001312"
```

```r
# Main campus
opeid8 <- "00131200"  # Main campus
opeid6 <- "001312"    # Institution family

# Branch campuses share OPEID6
branch1 <- "00131201"  # opeid6 = "001312"
branch2 <- "00131202"  # opeid6 = "001312"
```

### OPEID Characteristics

| Characteristic | Description |
|----------------|-------------|
| Assignment | Dept of Education Office of FSA |
| Purpose | Title IV eligibility and administration |
| Branch handling | Same OPEID6, different suffixes |
| Stability | Generally stable, changes with ownership |

## Linking UNITID and OPEID

### Relationship

- One UNITID may have one OPEID (most common)
- Multiple UNITIDs may share one OPEID6 (branches)
- Rare: UNITID without OPEID (non-Title IV)

### Crosswalk

IPEDS provides OPEID in the Institutional Characteristics (IC) survey.

```python
import polars as pl

# Load IPEDS directory (contains both unitid and opeid)
directory = pl.read_parquet("data/raw/ipeds_directory.parquet")

# Crosswalk columns
unitid = directory["unitid"]
opeid = directory["opeid"]

# Link to other data (e.g., Scorecard)
scorecard = pl.read_parquet("data/raw/scorecard_earnings.parquet")
merged = directory.join(scorecard, on="unitid")
```

```r
library(arrow)
library(dplyr)

# Load IPEDS directory (contains both unitid and opeid)
directory <- read_parquet("data/raw/ipeds_directory.parquet")

# Crosswalk columns
unitid <- directory$unitid
opeid <- directory$opeid

# Link to other data (e.g., Scorecard)
scorecard <- read_parquet("data/raw/scorecard_earnings.parquet")
merged <- directory |> inner_join(scorecard, by = "unitid")
```

### Complications

| Scenario | Issue |
|----------|-------|
| Branch campuses | May have separate UNITIDs but same OPEID6 |
| System reporting | May aggregate differently |
| Institutional changes | IDs may change at different times |
| Historical data | Crosswalk may not work for old data |

## Institutional Changes

### Types of Changes

| Change Type | UNITID Impact | OPEID Impact |
|-------------|---------------|--------------|
| Name change | No change | No change |
| Address change | No change | No change |
| Sector change | May change | Usually no change |
| Control change | May change | Usually changes |
| Merger | New UNITID for merged entity | New OPEID usually |
| Acquisition | May get new UNITID | New OPEID usually |
| Closure | UNITID discontinued | OPEID discontinued |
| Reopening | New UNITID | New OPEID |
| Branch becoming independent | New UNITID | New OPEID |

### Tracking Sector Changes

Institutions sometimes change sector:

| Direction | Example | Frequency |
|-----------|---------|-----------|
| For-profit to nonprofit | Conversion to avoid scrutiny | Increasing |
| Private to public | State takeover | Rare |
| Public to private | Privatization | Very rare |

**Important**: Sector changes affect finance data comparability (GASB to FASB).

### Institutional Closure Tracking

| Portal Variable | Description |
|-----------------|-------------|
| `inst_category` | Institution status category |
| `year_deleted` | Year institution closed |
| `currently_active_ipeds` | Currently active flag |
| `date_closed` | Close date (string) |
| `inst_status` | Institution status |

> **Note:** NCES raw files use `INSTCAT`, `DEATHYR`, `CYACTIVE`. The Portal uses the descriptive names shown above.

```python
import polars as pl

# Filter to active institutions
active = df.filter(pl.col("currently_active_ipeds") == 1)

# Find closures
closed = df.filter(pl.col("year_deleted").is_not_null())
```

```r
library(dplyr)

# Filter to active institutions
active <- df |> filter(currently_active_ipeds == 1)

# Find closures
closed <- df |> filter(!is.na(year_deleted))
```

## Tracking Institutions Over Time

### Time Series Analysis Challenges

| Challenge | Mitigation |
|-----------|------------|
| UNITID changes | Check for mergers, closures |
| Sector changes | Note in analysis, may affect data |
| Program changes | May affect enrollment, completions |
| Data revisions | Use consistent data vintage |

### Best Practices

1. **Check institution status** each year
   ```python
   # Verify institution was active in analysis years
   active_years = df.filter(pl.col("currently_active_ipeds") == 1).select("year").unique()
   ```

   ```r
   # Verify institution was active in analysis years
   active_years <- df |> filter(currently_active_ipeds == 1) |> distinct(year)
   ```

2. **Look for discontinuities**
   ```python
   # Large year-over-year changes may indicate issues
   yoy_change = df.with_columns(
       (pl.col("enrollment") / pl.col("enrollment").shift(1) - 1).alias("change")
   )
   suspicious = yoy_change.filter(pl.col("change").abs() > 0.5)
   ```

   ```r
   # Large year-over-year changes may indicate issues
   yoy_change <- df |> mutate(change = enrollment / lag(enrollment) - 1)
   suspicious <- yoy_change |> filter(abs(change) > 0.5)
   ```

3. **Use institution history files**
   - IPEDS provides institutional history
   - Check for mergers, name changes

4. **Document exclusions**
   ```python
   # Exclude institutions with status changes
   analysis_sample = df.filter(
       pl.col("status_change_flag") == 0
   )
   print(f"Excluded {original_n - analysis_sample.height} institutions")
   ```

   ```r
   # Exclude institutions with status changes
   analysis_sample <- df |> filter(status_change_flag == 0)
   cat("Excluded", original_n - nrow(analysis_sample), "institutions\n")
   ```

### Merger Handling

When institutions merge:
- Old UNITIDs discontinued
- New UNITID created for merged entity
- Historical data under old UNITIDs

**Options for analysis**:
1. Exclude merged institutions
2. Sum pre-merger data (if appropriate)
3. Analyze as separate entities pre-merger

```python
# Example: Identify merged institutions
mergers = history.filter(pl.col("merge_flag") == 1)

# Option 1: Exclude
clean_data = data.filter(~pl.col("unitid").is_in(mergers["unitid"]))

# Option 2: Flag for separate handling
data = data.with_columns(
    pl.col("unitid").is_in(mergers["unitid"]).alias("merger_involved")
)
```

```r
# Example: Identify merged institutions
mergers <- history |> filter(merge_flag == 1)

# Option 1: Exclude
clean_data <- data |> filter(!unitid %in% mergers$unitid)

# Option 2: Flag for separate handling
data <- data |> mutate(merger_involved = unitid %in% mergers$unitid)
```

## Linking to Other Data Sources

### College Scorecard

| Link Field | Notes |
|------------|-------|
| UNITID | Primary link, same as IPEDS |
| OPEID | Also available in Scorecard |

```python
import polars as pl

# Both IPEDS and Scorecard use UNITID
ipeds = pl.read_parquet("data/raw/ipeds_directory.parquet")
scorecard = pl.read_parquet("data/raw/scorecard_earnings.parquet")

merged = ipeds.join(scorecard, on="unitid", how="left")

# Check for missing matches
missing = merged.filter(pl.col("scorecard_field").is_null())
```

```r
library(arrow)
library(dplyr)

# Both IPEDS and Scorecard use UNITID
ipeds <- read_parquet("data/raw/ipeds_directory.parquet")
scorecard <- read_parquet("data/raw/scorecard_earnings.parquet")

merged <- ipeds |> left_join(scorecard, by = "unitid")

# Check for missing matches
missing <- merged |> filter(is.na(scorecard_field))
```

### Federal Student Aid (FSA) Data

| Link Field | Notes |
|------------|-------|
| OPEID | Primary link for FSA |
| OPEID6 | Institution family level |

```python
import polars as pl

# FSA data uses OPEID
fsa_data = pl.read_parquet("data/raw/fsa_grants.parquet")

# Link through OPEID
merged = ipeds.join(fsa_data, on="opeid", how="left")

# Or at institution family level
merged = ipeds.with_columns(
    pl.col("opeid").str.slice(0, 6).alias("opeid6")
).join(fsa_data, on="opeid6", how="left")
```

```r
library(arrow)
library(dplyr)
library(stringr)

# FSA data uses OPEID
fsa_data <- read_parquet("data/raw/fsa_grants.parquet")

# Link through OPEID
merged <- ipeds |> left_join(fsa_data, by = "opeid")

# Or at institution family level
merged <- ipeds |>
  mutate(opeid6 = str_sub(opeid, 1, 6)) |>
  left_join(fsa_data, by = "opeid6")
```

### State Longitudinal Data Systems

State data may use:
- State-specific IDs
- UNITID
- OPEID
- Institution name (risky)

**Recommendation**: Obtain crosswalk from state agency.

### BLS/Census Data

| Source | Common Link |
|--------|------------|
| QCEW | Requires geographic matching |
| ACS | FIPS codes for geography |
| BLS OES | CIP to SOC crosswalk |

## Common Issues

### Issue 1: Missing OPEID

Some institutions don't have OPEID:
- Non-Title IV institutions
- New institutions pending approval
- Some specialized institutions

```python
# Check for missing OPEIDs
missing_opeid = df.filter(pl.col("opeid").is_null())
```

```r
# Check for missing OPEIDs
missing_opeid <- df |> filter(is.na(opeid))
```

### Issue 2: OPEID Format Inconsistencies

| Format | Example | Issue |
|--------|---------|-------|
| With leading zeros | 00131200 | Correct |
| Without leading zeros | 131200 | May fail joins |
| With hyphens | 001312-00 | Need to clean |

```python
# Standardize OPEID format
df = df.with_columns(
    pl.col("opeid").str.replace("-", "").str.zfill(8).alias("opeid_clean")
)
```

```r
# Standardize OPEID format
df <- df |> mutate(opeid_clean = str_pad(str_remove(opeid, "-"), 8, pad = "0"))
```

### Issue 3: Branch Campus Aggregation

For some analysis, want institution-level data not branch-level.

```python
# Aggregate to OPEID6 level
institution_level = branch_data.group_by("opeid6").agg([
    pl.col("enrollment").sum(),
    pl.col("completions").sum()
])
```

```r
# Aggregate to OPEID6 level
institution_level <- branch_data |>
  group_by(opeid6) |>
  summarise(enrollment = sum(enrollment), completions = sum(completions))
```

### Issue 4: Duplicate UNITID in Merged Data

When merging across years or sources:

```python
# Check for duplicates
duplicates = merged.group_by("unitid").count().filter(pl.col("count") > 1)

if duplicates.height > 0:
    print(f"Warning: {duplicates.height} duplicate UNITIDs found")
```

```r
# Check for duplicates
duplicates <- merged |> count(unitid) |> filter(n > 1)

if (nrow(duplicates) > 0) {
  cat("Warning:", nrow(duplicates), "duplicate UNITIDs found\n")
}
```

### Issue 5: Historical UNITID Changes

Old UNITIDs may not exist in new data and vice versa.

```python
# Find institutions not in both years
in_2020 = set(data_2020["unitid"])
in_2023 = set(data_2023["unitid"])

added = in_2023 - in_2020
removed = in_2020 - in_2023

print(f"Added: {len(added)}, Removed: {len(removed)}")
```

```r
# Find institutions not in both years
in_2020 <- unique(data_2020$unitid)
in_2023 <- unique(data_2023$unitid)

added <- setdiff(in_2023, in_2020)
removed <- setdiff(in_2020, in_2023)

cat("Added:", length(added), ", Removed:", length(removed), "\n")
```

## Variable Reference

### Identifier Variables

| Variable | Description |
|----------|-------------|
| `unitid` | IPEDS institution identifier |
| `opeid` | 8-digit OPEID |
| `opeflag` | OPEID status flag |

### Status Variables

| Portal Variable | NCES Name | Description |
|-----------------|-----------|-------------|
| `currently_active_ipeds` | `CYACTIVE` | Currently active |
| `inst_category` | `INSTCAT` | Institutional category |
| `year_deleted` | `DEATHYR` | Year closed |
| `date_closed` | `CLOSEDAT` | Close date |
| `inst_status` | — | Institution status |

### Name and Location

| Portal Variable | NCES Name | Description |
|-----------------|-----------|-------------|
| `inst_name` | `INSTNM` | Institution name |
| `inst_alias` | `IALIAS` | Institution alias/former name |
| `address` | `ADDR` | Street address |
| `city` | `CITY` | City |
| `state_abbr` | `STABBR` | State abbreviation |
| `zip` | `ZIP` | ZIP code |
| `fips` | `FIPS` | State FIPS code |
| `county_name` | `COUNTYNM` | County name |
| `longitude` | `LONGITUD` | Longitude |
| `latitude` | `LATITUDE` | Latitude |
