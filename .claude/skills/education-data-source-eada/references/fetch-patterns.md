# EADA Data Access

EADA data is fetched from mirrors via the `education-data-query` skill.

## Mirror Path

| Dataset | Path |
|---------|------|
| Institutional Characteristics | `college-university/eada/institutional-characteristics/colleges_eada_inst_characteristics.parquet` |

## Example Fetch

```python
import polars as pl

# Fetch EADA institutional data via unified mirror system
DATASET_PATH = "eada/colleges_eada_inst_characteristics"
df = fetch_from_mirrors(DATASET_PATH)

# Filter by year and state
df = df.filter(
    (pl.col("year") == 2021) &
    (pl.col("fips") == 6)  # California
)
```

## Available Years

2002-2021 (institutional characteristics)

## Key Columns

The Portal uses different column names than EADA documentation. Key mappings:

| Category | Portal Columns |
|----------|---------------|
| Participation | `undup_athpartic_men`, `undup_athpartic_women`, `athpartic_men`, `athpartic_women` |
| Coaching | `men_fthdcoach_male`, `women_fthdcoach_fem`, `men_ftasstcoach_male`, etc. |
| Salaries | `hdcoach_salary_men`, `hdcoach_salary_women` |
| Expenses | `ath_exp_men`, `ath_exp_women`, `ath_opexp_perpart_men`, `ath_opexp_perpart_women` |
| Revenues | `ath_rev_men`, `ath_rev_women` |
| Student Aid | `ath_stuaid_men`, `ath_stuaid_women` |

See `variable-definitions.md` for complete column documentation.

## Missing Values

EADA data uses `null` for missing values, not coded values (-1, -2, -3).

```python
# Filter for valid data
valid = df.filter(pl.col("ath_exp_men").is_not_null())
```
