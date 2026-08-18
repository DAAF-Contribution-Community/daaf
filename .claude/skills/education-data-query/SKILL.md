---
name: education-data-query
description: >-
  Downloads education datasets from configured mirror sources (parquet/CSV) with local Polars filtering, including versioned mirror vintages (revision-pinned for reproducibility). Use when writing fetch scripts, retrieving CCD, IPEDS, CRDC, SAIPE data, or pinning a fetch to a specific mirror vintage. Load after education-data-explorer — retrieval here, not discovery.
metadata:
  audience: research-coders
  domain: data-access
---

# Education Data Query

Downloads education datasets from configured mirror sources (parquet or CSV) using priority-ordered fallback, with local Polars filtering. Use when writing Stage 5 fetch scripts, downloading a specific CCD, IPEDS, CRDC, SAIPE, or other education dataset by path, discovering which files are available on a mirror, or retrieving codebook metadata. Load after using education-data-explorer to identify mirror datasets — this skill handles actual data retrieval, not dataset discovery.

Download datasets from the Education Data Portal via configured mirror sources (defined in mirrors.yaml). Mirrors are tried in priority order. All filtering is done locally with Polars. The mirror data originates from the Urban Institute Education Data Portal (EDP), which is a curation and standardization layer over original federal data sources — data has been restructured with lowercase variable names, integer-encoded categoricals, and standardized missing value codes (`-1`, `-2`, `-3`).

## What This Skill Does

- Download education datasets from configured mirrors
- Handle multiple file formats (parquet, CSV) based on mirror read_strategy
- Apply year, state, and demographic filters locally with Polars
- Discover available files via each mirror's discovery endpoint

> **Skill Provenance Note:** Each `*-data-source-*` skill includes
> a `skill-last-updated` key in its frontmatter `metadata:` block. Before fetching data,
> check this date — if it is more than a few months old, the source skill's
> documentation about column definitions, coded values, and quality patterns
> may have drifted from the current data. Consider re-running data-ingest to
> re-verify before relying on stale skill guidance for query construction.

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `mirrors.yaml` | Mirror URLs, priority, format, timeouts, metadata config | Understanding mirror configuration |
| `fetch-patterns.md` | Code patterns for mirror-based fetching | Writing Stage 5 fetch scripts |
| `datasets-reference.md` | Known dataset file paths by source | Finding the right file path for a dataset |
| `filters-reference.md` | Complete filter variables | Filtering downloaded data locally |
| `query-patterns.md` | Endpoint path structure reference | Understanding URL/path naming conventions |
| `vintage-drift.md` | Old (v0.24.0) → current (v0.26.1) mirror value/coverage drift | Sizing reproducibility impact before re-running a pre-2026q3 analysis |

## Mirror System Overview

Data is fetched by downloading files from mirrors:

```
Fetch Request (dataset, years, filters)
    → Try each mirror in priority order (per mirrors.yaml)
        → Build URL from mirror's url_template + dataset paths
        → Read using mirror's read_strategy (eager_parquet, lazy_csv, etc.)
    → If all mirrors fail: STOP and escalate
    → Save to data/raw/*.parquet
    → CP1 validation (source-agnostic)
```

### Mirror Configuration

Mirrors are defined in `./references/mirrors.yaml` with priority ordering. Each mirror specifies:
- `url_template` — how to build download URLs
- `read_strategy` — how Polars reads the format (eager_parquet, lazy_csv)
- `discovery` — how to check what files are available

See `./references/mirrors.yaml` for the full configuration and instructions on adding new mirrors.

### Mirror File Discovery

Before fetching, check the mirror discovery endpoint defined in `mirrors.yaml`. The Python patterns in `fetch-patterns.md` are **copyable inline patterns, not an importable module**. Copy `canonicalize_mirror_path()` and `discover_mirror_files()` into the Stage 5 script alongside the mirror config; do not write `from fetch_patterns import ...`.

```python
# Self-contained discovery probe for the configured primary mirror. The full
# copyable helper in fetch-patterns.md adds pagination, validation, and codebooks.
import requests
import yaml
from pathlib import Path

config_path = Path("/daaf/.claude/skills/education-data-query/references/mirrors.yaml")
with config_path.open(encoding="utf-8") as config_file:
    mirror = yaml.safe_load(config_file)["mirrors"][0]
# Pin discovery to the mirror's vintage: resolve the tree url_template with the
# configured revision (falls back to a static url for an unversioned mirror).
discovery = mirror["discovery"]
revision = str((mirror.get("vintage") or {}).get("hf_revision", "main"))
discovery_url = (
    discovery["url_template"].format(revision=revision)
    if discovery.get("url_template") else discovery["url"]
)
response = requests.get(discovery_url, timeout=30)
response.raise_for_status()
entries = response.json()
if isinstance(entries, dict):
    entries = entries["results"]
raw_paths = [entry[mirror["discovery"].get("file_path_key", "path")] for entry in entries
             if entry.get("type") == "file"]
data_paths = [path[:-8] for path in raw_paths if path.lower().endswith(".parquet")]
assert all(not path.lower().endswith((".csv", ".parquet", ".xls")) for path in data_paths)
print(f"Available canonical data paths: {len(data_paths)}")
```

```r
# Generic discovery — works with any mirror that supports it
# See fetch-patterns.md for the full inline R discovery pattern
# Check primary mirror
mirror <- mirrors[[1]]
discovery <- mirror$discovery
if (!is.null(discovery) && discovery$method == "http_json") {
  # Pin discovery to the mirror's vintage: substitute the revision into the tree
  # url_template (fall back to a static url for an unversioned mirror).
  revision <- if (!is.null(mirror$vintage$hf_revision)) as.character(mirror$vintage$hf_revision) else "main"
  discovery_url <- if (!is.null(discovery$url_template)) gsub("{revision}", revision, discovery$url_template, fixed = TRUE) else discovery$url
  resp <- httr2::request(discovery_url) |> httr2::req_timeout(30) |> httr2::req_perform()
  raw <- httr2::resp_body_json(resp)
  entries <- if (!is.null(raw$results)) raw$results else raw
  cat(sprintf("Available files: %d\n", length(entries)))
}
```

This eliminates guessing — if the file exists in a mirror, use it; if not, fall through to the next.

## Mirror Versioning & Reproducibility

The Hugging Face mirror is **versioned by vintage**. A *vintage* is a dated snapshot of the Education Data Portal captured into one HF dataset repo; a *revision* is the HF git ref (branch, tag, or commit SHA) that pins requests to one immutable state of that repo. In `mirrors.yaml` this is one `vintage:` block per mirror — `portal_version`, `collected`, and `hf_revision` — and the fetch helpers thread `hf_revision` into every URL (data, codebook, and discovery) via `build_mirror_url()` / `mirror_revision()`. You do not build these URLs by hand; use the patterns in `./references/fetch-patterns.md`.

**Pin by default.** The current mirror snapshots Portal **v0.26.1** (repo `brhkim/education_data_portal_mirror_2026q3`). Once its commit SHA is pinned in `mirrors.yaml` (`vintage.hf_revision`), every fetch resolves to those exact bytes, so a rerun of a Stage 5 script downloads identical data.

**Why this matters (silent drift).** The Portal revises historical values between releases *without schema changes* — e.g., Portal 0.26.1 retroactively corrected IPEDS Graduation Rates 150% for 1996-2023. An unpinned mirror (revision `main`) can therefore serve silently different numbers to the same script run months apart, with no error and no column change to signal it. Pinning to an immutable revision is what makes a project's fetches byte-reproducible.

**Citation version rule.** Cite data using the Portal version of the vintage you fetched — v0.26.1 for this mirror. See `education-data-context` for the full Portal citation format; the version number in the citation must match the mirrored Portal version.

**Reproducing a pre-2026q3 analysis (old frozen vintage).** The predecessor mirror — Portal **v0.24.0**, repo `brhkim/education_data_portal_mirror`, collected 2026-02-07 — is **frozen** (retained indefinitely for reproducibility, not deleted). To rerun an analysis built against it, point the fetch at the predecessor instead of the current mirror: resolve URLs against `https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/{revision}/{path}.parquet` (and cite Portal v0.24.0). The predecessor's coordinates live in the `vintage.predecessor` block of `mirrors.yaml`.

**Which numbers actually changed (old v0.24.0 → current v0.26.1).** Before re-running a pre-2026q3 analysis, consult `./references/vintage-drift.md` — it maps exactly which datasets and years moved between the two vintages, how much of each change is a real data revision versus a cosmetic missing-code re-encoding, and the full grad-rates-150% dedup+revaluation story. Use it to size the reproducibility impact of a mirror change before deciding what must be re-executed.

## Decision Trees

### "How should I get this data?"

```
What dataset do you need?
├─ Know the exact file path?
│   └─ Use fetch_from_mirrors() with that path → ./references/fetch-patterns.md
├─ Know the source but not the exact filename?
│   └─ Check ./references/datasets-reference.md for known paths
├─ Not sure what's available?
│   └─ Query mirror discovery endpoint to list all files → ./references/fetch-patterns.md
├─ Need a codebook or metadata file?
│   └─ Check codebook column in ./references/datasets-reference.md → get_codebook_url() in ./references/fetch-patterns.md
└─ Dataset not in any mirror?
    └─ STOP and escalate — dataset may need to be added to mirror
```

### "Is my dataset a single file or yearly files?"

```
Check datasets-reference.md:
├─ Type = "Single" → One file with all years
│   └─ Use fetch_from_mirrors() → filter years locally
└─ Type = "Yearly" → One file per year
    └─ Use fetch_yearly_from_mirrors() → concatenate results
```

### "How do I filter results?"

All filtering is done locally with Polars after download:

```python
# By state
df = df.filter(pl.col("fips") == 6)  # California

# By year
df = df.filter(pl.col("year").is_in([2020, 2021, 2022]))

# By school type
df = df.filter(pl.col("charter") == 1)

# Multiple filters
df = df.filter(
    (pl.col("fips") == 6) &
    (pl.col("charter") == 1) &
    (pl.col("school_level") == 3)
)
```

```r
# By state
df <- df |> filter(fips == 6)  # California

# By year
df <- df |> filter(year %in% c(2020, 2021, 2022))

# By school type
df <- df |> filter(charter == 1)

# Multiple filters
df <- df |> filter(fips == 6, charter == 1, school_level == 3)
```

## Dataset Path Structure

All mirrors use the same **extensionless data canonical path**. Discovery strips exactly one terminal `.csv` or `.parquet` before returning a data key, and each mirror appends its own format extension via `url_template`. Codebook canonical paths are also extensionless, but are a distinct `codebook` kind: discovery strips exactly one terminal `.xls`, and metadata URL templates append `.xls`. Reject extension-bearing inputs rather than constructing doubled extensions.

```
{source}/{filename}
```

| Component | Description | Examples |
|-----------|-------------|----------|
| `source` | Data source | `ccd`, `ipeds`, `crdc`, `saipe`, `edfacts` |
| `filename` | Dataset file | `schools_ccd_directory`, `districts_saipe` |

Example paths:
- `saipe/districts_saipe` (SAIPE district poverty)
- `ccd/schools_ccd_directory` (CCD school directory)
- `ccd/schools_ccd_enrollment_2022` (CCD enrollment, yearly)

See `./references/datasets-reference.md` for the complete file path listing.

## Format Handling

Format-specific read behavior is driven by each mirror's `read_strategy` field (see `mirrors.yaml`):

### `eager_parquet`
```python
df = pl.read_parquet(url)  # Polars reads HTTP URLs natively
```

```r
# R only — raise the download timeout BEFORE reading. arrow::read_parquet(url)
# transfers via download.file(), which caps the whole transfer at getOption("timeout")
# (default 60s); large mirror files (e.g. ccd/schools_ccd_directory, ~224MB) truncate
# at ~60s and silently fall through to the next mirror (the CSV fallback, in the
# default configuration). Python is unaffected.
options(timeout = max(600, getOption("timeout")))
# View-safe parquet read: arrow reads HTTP URLs natively, but mirror files are
# Polars-written and some declare string columns as `string_view` — the R arrow
# binding cannot convert those to R vectors directly (fails at Table->data.frame
# with "cannot handle Array of type <utf8_view>"). Read as an Arrow Table first,
# cast any view types to their materialized equivalents, THEN convert. This cast
# is a no-op on files without view types, so it is safe to use for every read.
tbl <- arrow::read_parquet(url, as_data_frame = FALSE)   # C++ read tolerates view types
sch <- tbl$schema
fields <- lapply(seq_len(length(sch$names)), function(i) {
  fld <- sch$field(i - 1L)                                # $field() is 0-indexed (C++ convention)
  ts  <- fld$type$ToString()
  # Check large_string_view before string_view: the former's ToString() contains
  # the substring "string_view", so an unordered check would misclassify it.
  new_type <- if (grepl("large_string_view", ts, fixed = TRUE)) arrow::large_utf8()
    else if (grepl("string_view", ts, fixed = TRUE)) arrow::utf8()
    else if (grepl("binary_view", ts, fixed = TRUE)) arrow::binary()
    else fld$type
  arrow::field(fld$name, new_type)
})
df <- as.data.frame(tbl$cast(arrow::schema(fields)))     # cast view->materialized, then convert
# Do NOT reach for arrow::open_dataset(url) |> dplyr::collect() as a workaround —
# it hits the same utf8_view conversion error. Non-view columns (including integer
# IDs) pass through untouched, so there is no leading-zero or coercion risk.
# See ./references/fetch-patterns.md for the full loop-integrated version.
```

### `lazy_csv`
```python
# Always use lazy loading for large files
df = (
    pl.scan_csv(url, infer_schema_length=10000)
    .filter(pl.col("year").is_in(YEARS))
    .filter(pl.col("fips") == STATE_FIPS)
    .collect()
)
```

```r
# R only — raise the download timeout BEFORE reading. readr::read_csv(url)
# transfers via download.file() exactly like the parquet read (60s default cap),
# and CSV mirror files reach 500MB+.
options(timeout = max(600, getOption("timeout")))
# Read CSV then filter (R reads eagerly; arrow handles large files efficiently)
df <- readr::read_csv(url, show_col_types = FALSE) |>
  filter(year %in% YEARS) |>
  filter(fips == STATE_FIPS)
```

See `./references/fetch-patterns.md` for complete code patterns.

## Portal Integer Encoding

**CRITICAL:** The Portal uses integer codes, not string labels. This affects filtering and interpretation.

### Demographic Variable Encodings

| Variable | Integer Values | NOT These Strings |
|----------|----------------|-------------------|
| Race | 1-7, 99 (total) | WH, BL, HI, AS, etc. |
| Sex | 1 (Male), 2 (Female), 3 (Another gender, IPEDS 2022+), 4 (Unknown gender, IPEDS 2022+), 9 (Unknown), 99 (Total) | M, F |
| Grade | -1 to 13, 99 (total) | PK, KG, 01, etc. |

### Grade Encoding (SEMANTIC TRAP!)

| Value | Meaning | URL Path Equivalent |
|-------|---------|---------------------|
| -1 | Pre-K (**NOT missing!**) | `grade-pk` |
| 0 | Kindergarten | `grade-k` |
| 1-12 | Grades 1-12 | `grade-1` to `grade-12` |
| 99 | Total | `grade-99` |

```python
# WRONG - filters out Pre-K students!
df = df.filter(pl.col("grade") >= 0)

# RIGHT - Pre-K students have grade = -1
pre_k = df.filter(pl.col("grade") == -1)
total = df.filter(pl.col("grade") == 99)
```

```r
# WRONG - filters out Pre-K students!
df <- df |> filter(grade >= 0)

# RIGHT - Pre-K students have grade = -1
pre_k <- df |> filter(grade == -1)
total <- df |> filter(grade == 99)
```

### Variable Names Are Lowercase

Portal variable names are lowercase:
- `enrollment` not `MEMBER`
- `grade` not `GRADE`
- `fips` not `FIPS`

See `./references/filters-reference.md` for complete encoding tables.

## Common FIPS Codes

| Code | State | Code | State | Code | State |
|------|-------|------|-------|------|-------|
| 1 | Alabama | 17 | Illinois | 36 | New York |
| 2 | Alaska | 18 | Indiana | 37 | North Carolina |
| 4 | Arizona | 19 | Iowa | 39 | Ohio |
| 5 | Arkansas | 20 | Kansas | 40 | Oklahoma |
| 6 | California | 21 | Kentucky | 41 | Oregon |
| 8 | Colorado | 22 | Louisiana | 42 | Pennsylvania |
| 9 | Connecticut | 24 | Maryland | 44 | Rhode Island |
| 10 | Delaware | 25 | Massachusetts | 45 | South Carolina |
| 11 | DC | 26 | Michigan | 47 | Tennessee |
| 12 | Florida | 27 | Minnesota | 48 | Texas |
| 13 | Georgia | 29 | Missouri | 49 | Utah |
| 15 | Hawaii | 32 | Nevada | 51 | Virginia |
| 16 | Idaho | 34 | New Jersey | 53 | Washington |

See `./references/filters-reference.md` for complete list.

## Cross-References

- **Discover datasets:** Load `education-data-explorer` skill to route a question to mirror files and variables
- **Interpret data:** Load `education-data-context` skill after fetching for variable meanings and caveats
- **Deep source understanding:** Load `education-data-source-*` skills for comprehensive methodology

### Data Source Skills Quick Reference

| Source | Skill | Key Fetch Considerations |
|--------|-------|--------------------------|
| CCD | `education-data-source-ccd` | Use grade-99 for totals; FRPL affected by CEP |
| CRDC | `education-data-source-crdc` | Biennial only; 2015+ for complete coverage; CSV requires force-string + pad-and-assert on ID cols (ncessch→12, leaid→7, crdc_id) — see fetch-patterns.md "Zero-padded ID columns" |
| EDFacts | `education-data-source-edfacts` | Use `_midpt` vars; states not comparable; CSV fallback needs force-string + `str_pad`/`zfill` + width-assert on ncessch/leaid (2019 ships already-truncated IDs) |
| IPEDS | `education-data-source-ipeds` | GRS limited to first-time full-time |
| Scorecard | `education-data-source-scorecard` | High suppression; Title IV recipients only |
| SAIPE | `education-data-source-saipe` | Model estimates; population not enrollment; `leaid` is Int64 (pad→7 + assert before joins); `_poverty_pct` is a 0-1 proportion, not 0-100% |
| FSA | `education-data-source-fsa` | Federal aid only; 1-3 year lag |
| MEPS | `education-data-source-meps` | Better than FRPL for cross-state |
| PSEO | `education-data-source-pseo` | Experimental; check state coverage |

## Topic Index

| Topic | Location |
|-------|----------|
| Mirror configuration | `./references/mirrors.yaml` |
| Vintage drift (v0.24.0 → v0.26.1) | `./references/vintage-drift.md` |
| Fetch code patterns | `./references/fetch-patterns.md` |
| Dataset file paths | `./references/datasets-reference.md` |
| URL/path naming conventions | `./references/query-patterns.md` |
| Filter variables | `./references/filters-reference.md` |
| Codebook/metadata URLs | `./references/datasets-reference.md` (codebook column), `./references/fetch-patterns.md` (get_codebook_url) |
| FIPS codes | This file, `./references/filters-reference.md` |
| CCD source details | `education-data-source-ccd` skill |
| CRDC source details | `education-data-source-crdc` skill |
| EDFacts source details | `education-data-source-edfacts` skill |
| IPEDS source details | `education-data-source-ipeds` skill |
| Scorecard source details | `education-data-source-scorecard` skill |
| SAIPE source details | `education-data-source-saipe` skill |
| FSA source details | `education-data-source-fsa` skill |
| MEPS source details | `education-data-source-meps` skill |
| NHGIS source details | `education-data-source-nhgis` skill |
