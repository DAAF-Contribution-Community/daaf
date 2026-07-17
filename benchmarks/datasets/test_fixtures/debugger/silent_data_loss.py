"""
Test fixture: Silent data loss from string-based academic year filtering.
Simulates a subtle bug where filtering enrollment records by academic year
using lexicographic string comparison silently drops valid rows because
"YYYY-YY" formatted years sort differently than plain "YYYY" years.
"""
import polars as pl
import random
import os

# --- Config ---
# INTENT: Filter enrollment data to the post-policy window (2019 onward)
# REASONING: Federal accountability change took effect in 2019; need 2019-2022 data
PROJECT_DIR = "/tmp/daaf_test_silent"
OUTPUT_PATH = f"{PROJECT_DIR}/filtered_enrollment.parquet"
CUTOFF_YEAR = "2019"

# --- Load ---
# INTENT: Build synthetic school enrollment dataset spanning 8 academic years
# ASSUMES: Each school contributes one record per academic year
random.seed(42)

schools = [f"S{i:04d}" for i in range(1, 63)]  # 62 schools
# REASONING: CCD source data uses "YYYY-YY" academic year format for all years,
#   but upstream cleaning script converted recent years to plain "YYYY"
year_labels = {
    2015: "2014-15",
    2016: "2015-16",
    2017: "2016-17",
    2018: "2017-18",
    2019: "2018-19",
    2020: "2019-20",
    2021: "2021",
    2022: "2022",
}

rows = []
for school in schools:
    for cal_year, year_str in year_labels.items():
        rows.append({
            "ncessch": school,
            "year": year_str,
            "enrollment": random.randint(150, 900),
            "frl_count": random.randint(20, 400),
        })

enrollment_df = pl.DataFrame(rows)
print(f"Total records loaded: {enrollment_df.shape[0]}")
print(f"Unique year values: {sorted(enrollment_df['year'].unique().to_list())}")

# --- Transform ---
# INTENT: Keep only records from 2019 onward for policy impact analysis
# ASSUMES: Comparing year column against "2019" correctly selects post-policy years
filtered_df = enrollment_df.filter(
    pl.col("year") >= CUTOFF_YEAR
)

# --- Validate ---
print(f"Records after filtering year >= '{CUTOFF_YEAR}': {filtered_df.shape[0]}")
expected_years = 4  # 2019, 2020, 2021, 2022
actual_years = sorted(filtered_df["year"].unique().to_list())
print(f"Years retained: {actual_years}")
print(f"Expected {len(schools) * expected_years} rows ({expected_years} years x {len(schools)} schools), got {filtered_df.shape[0]}")

# --- Save ---
os.makedirs(PROJECT_DIR, exist_ok=True)
filtered_df.write_parquet(OUTPUT_PATH)
print(f"Saved filtered data to {OUTPUT_PATH}")

# EXECUTION OUTPUT:
# Total records loaded: 496
# Unique year values: ['2014-15', '2015-16', '2016-17', '2017-18', '2018-19', '2019-20', '2021', '2022']
# Records after filtering year >= '2019': 186
# Years retained: ['2019-20', '2021', '2022']
# Expected 248 rows (4 years x 62 schools), got 186
# Saved filtered data to /tmp/daaf_test_silent/filtered_enrollment.parquet
