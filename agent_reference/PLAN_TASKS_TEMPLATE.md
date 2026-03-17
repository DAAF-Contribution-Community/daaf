---
# Plan Tasks Frontmatter
# This YAML block contains machine-readable metadata linking to the parent Plan

parent_plan: "research/YYYY-MM-DD_[Title]/YYYY-MM-DD_[Title]_Plan.md"
title: "[Analysis Title]"
date: "YYYY-MM-DD"
version: ""                           # Empty for original, "a", "b", etc. for revisions
total_tasks: 0                        # Total task count (populated by data-planner)
total_waves: 0                        # Total wave count (populated by data-planner)
---

# [Analysis Title] - Executable Task Sequence

> **Parent Plan:** `research/YYYY-MM-DD_[Title]/YYYY-MM-DD_[Title]_Plan.md`
>
> This file contains the machine-readable executable task sequence for the analysis.
> It is a companion to Plan.md, which contains the strategic specification.
>
> **Immutability:** Both Plan.md and this file are frozen after Stage 4.5 (Plan Validation).

## Task Index

| Step | Task Name | Wave | Stage | Script Path | Depends On |
|------|-----------|------|-------|-------------|------------|
| 1.1 | fetch-ccd-schools | 1 | 5 | `scripts/stage5_fetch/01_fetch-ccd.py` | — |
| 1.2 | fetch-meps-poverty | 1 | 5 | `scripts/stage5_fetch/02_fetch-meps.py` | — |
| 2.1 | clean-ccd | 2 | 6 | `scripts/stage6_clean/01_clean-ccd.py` | 1.1 |
| 2.2 | clean-meps | 2 | 6 | `scripts/stage6_clean/02_clean-meps.py` | 1.2 |
| 3.1 | join-ccd-meps | 3 | 7 | `scripts/stage7_transform/01_join-data.py` | 2.1, 2.2 |

*(Replace with actual tasks for your analysis.)*

---

## Executable Task Sequence

### Wave 1: Data Acquisition (Parallel)

### Task 1.1: fetch-ccd-schools [Stage 5]

<task name="fetch-ccd-schools" type="auto" wave="1">
  <depends_on>none</depends_on>
  <skill>education-data-query</skill>
  <agent>research-executor</agent>
  <files>
    <output>data/raw/YYYY-MM-DD_ccd_schools.parquet</output>
  </files>
  <action>
    1. Load education-data-query skill
    2. Use mirror fetch pattern (see skill's fetch-patterns.md):
       - Dataset Paths: {dataset_paths}  (from datasets-reference.md)
       - File type: {single | yearly}
    3. Apply local filters with Polars:
       - Years: pl.col("year").is_in([year list])
       - Filters: [filter parameters as Polars expressions]
    4. Save to parquet format
    5. Run CP1 validation
  </action>
  <verify>
    - Row count: [min]-[max] expected
    - Required columns present: [list]
    - Years present: [list]
    - Null rate < 10% for critical fields
    - Mirror used logged in script output
  </verify>
  <done>CP1 PASSED, files saved to data/raw/</done>
</task>

### Task 1.2: fetch-meps-poverty [Stage 5]

<task name="fetch-meps-poverty" type="auto" wave="1">
  <depends_on>none</depends_on>
  <skill>education-data-query</skill>
  <agent>research-executor</agent>
  <files>
    <output>data/raw/YYYY-MM-DD_meps_poverty.parquet</output>
  </files>
  <action>
    1. Load education-data-query skill
    2. Use mirror fetch pattern for MEPS poverty data
    3. Apply local filters with Polars
    4. Save to parquet format
    5. Run CP1 validation
  </action>
  <verify>
    - Row count: [expected]
    - Join key (ncessch) present
    - Years match CCD fetch
  </verify>
  <done>CP1 PASSED, files saved to data/raw/</done>
</task>

### Wave 2: Data Cleaning (Parallel, depends on Wave 1)

### Task 2.1: clean-ccd [Stage 6]

<task name="clean-ccd" type="auto" wave="2">
  <depends_on>fetch-ccd-schools</depends_on>
  <skill>education-data-context</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/raw/YYYY-MM-DD_ccd_schools.parquet</input>
    <output>data/processed/YYYY-MM-DD_ccd_clean.parquet</output>
  </files>
  <action>
    1. Load education-data-context skill
    2. Load raw data from input file
    3. Filter coded values:
       - Remove rows where [variable] == -1 (missing)
       - Remove rows where [variable] == -2 (not applicable)
       - Remove rows where [variable] == -3 (suppressed)
       *(Coded values above are education domain defaults — replace with values from Domain Configuration.)*
    4. Calculate suppression rate for key variable
    5. Generate citation text
    6. Save to parquet format
    7. Run CP2 validation
  </action>
  <verify>
    - Suppression rate < 50%
    - No coded missing values (per Domain Configuration) remain
    - Data loss < 90%
    - Citation text complete
  </verify>
  <done>CP2 PASSED, files saved to data/processed/</done>
</task>

### Wave 3: Transformation (Sequential, depends on Wave 2)

### Task 3.1: join-ccd-meps [Stage 7]

<task name="join-ccd-meps" type="auto" wave="3">
  <depends_on>clean-ccd, clean-meps</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <cardinality>1:1</cardinality>
  <files>
    <input>data/processed/YYYY-MM-DD_ccd_clean.parquet</input>
    <input>data/processed/YYYY-MM-DD_meps_clean.parquet</input>
    <output>data/processed/YYYY-MM-DD_analysis.parquet</output>
  </files>
  <action>
    1. Load both skills
    2. Load both input files
    3. Capture pre-state (row counts, key overlap)
    4. Perform inner join on ncessch
    5. Validate cardinality (1:1 expected)
    6. Check for fan-out or data loss
    7. Save result
    8. Run CP3 validation
  </action>
  <verify>
    - Join key overlap: > 90%
    - No fan-out (result rows ≤ left rows)
    - Data loss < 50%
    - No unexpected nulls in joined columns
  </verify>
  <done>CP3 PASSED (join validation), file saved</done>
</task>
