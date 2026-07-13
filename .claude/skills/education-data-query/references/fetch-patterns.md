# Fetch Patterns Reference

Mirror-based data fetching patterns for the Education Data Portal.

---

## Overview

All data fetching uses a **mirror-first** approach:
1. Try each mirror in priority order (defined in `mirrors.yaml`)
2. Download the dataset file using the mirror's format and URL template
3. Apply filters locally with Polars
4. Save to `data/raw/` in parquet format

**Mirror configuration is centralized in `mirrors.yaml`.** The patterns below are mirror-agnostic — they work with any mirror defined in that file. To add a new mirror, update `mirrors.yaml` and `datasets-reference.md` only.

---

## Mirror Resolution Pattern

This pattern is inlined into every Stage 5 fetch script. It tries each mirror in priority order and falls back gracefully.

### Single-File Dataset (all years in one file)

```python
import time

import polars as pl
import requests
import yaml
from pathlib import Path

# --- Rate Limiting ---
# INTENT: Prevent HTTP 429 (Too Many Requests) errors from mirrors.
# REASONING: Mirrors may rate-limit rapid successive requests. A 3-second delay
#   between fetch calls avoids triggering limits while keeping pipeline runtime
#   reasonable (most fetches are sequential anyway).
FETCH_DELAY_SECONDS = 3
_last_fetch_time = 0.0


def _rate_limit():
    """Sleep if needed to maintain minimum delay between fetch requests."""
    global _last_fetch_time
    if _last_fetch_time > 0:
        elapsed = time.time() - _last_fetch_time
        if elapsed < FETCH_DELAY_SECONDS:
            wait = FETCH_DELAY_SECONDS - elapsed
            print(f"  (rate limit: waiting {wait:.1f}s)")
            time.sleep(wait)
    _last_fetch_time = time.time()


# --- Mirror Configuration ---
# INTENT: Download dataset from the fastest available mirror.
# REASONING: Mirrors are loaded from mirrors.yaml (the single source of truth).
#   Each mirror specifies its own url_template, read_strategy, and timeout.
#   The first successful response is used; failures fall through to the next mirror.
# REFERENCE: See mirrors.yaml for mirror definitions, datasets-reference.md for paths.

# Load mirror config from mirrors.yaml (adjust path to your project)
SKILL_DIR = Path(__file__).resolve().parent  # scripts/ directory
# mirrors.yaml is in the education-data-query skill references directory.
# When used in a research project, copy this path or inline the loaded config.
MIRRORS_YAML = SKILL_DIR / "mirrors.yaml"  # Adjust path as needed


def load_mirrors(yaml_path: Path = MIRRORS_YAML) -> list[dict]:
    """Load mirror configuration from mirrors.yaml.

    Returns list of mirror dicts with: name, url_template, read_strategy, timeout.
    Mirrors are in priority order (first = highest priority).
    """
    with open(yaml_path) as f:
        config = yaml.safe_load(f)
    return config["mirrors"]


# Load mirrors at module level — tried in priority order
MIRRORS = load_mirrors()

# Dataset path: canonical path string from datasets-reference.md.
# All mirrors use the same path — only root_url and format differ.
# Example for SAIPE district poverty:
DATASET_PATH = "saipe/districts_saipe"


def fetch_from_mirrors(
    path: str,
    filters: dict | None = None,
    years: list[int] | None = None,
) -> pl.DataFrame:
    """Try each mirror in order. Return DataFrame on first success.

    Args:
        path: Canonical dataset path string from datasets-reference.md.
            All mirrors use the same path — only root_url and format differ.
            Example: "saipe/districts_saipe"
        filters: Dict of column->value(s) filters to apply locally
        years: List of years to filter to (applied as pl.col("year").is_in(years))

    Returns:
        Filtered Polars DataFrame
    """
    _rate_limit()
    last_error = None

    for mirror in MIRRORS:
        name = mirror["name"]
        strategy = mirror["read_strategy"]
        timeout = mirror["timeout"]

        # Build URL from template + canonical path
        url = mirror["url_template"].format(root_url=mirror["root_url"], path=path, format=mirror["format"])

        print(f"  Trying {name}: {url}")

        try:
            if strategy == "eager_parquet":
                # REASONING: Parquet files have embedded schema, no inference needed.
                # Polars reads HTTP URLs natively via pl.read_parquet().
                df = pl.read_parquet(url)
            elif strategy == "lazy_csv":
                # REASONING: CSV files can be 500MB+. Lazy loading streams only
                # matching rows into memory rather than loading the full file.
                # ASSUMES: CSV has standard column names matching parquet schema.
                lazy = pl.scan_csv(url, infer_schema_length=10000)
                if years:
                    lazy = lazy.filter(pl.col("year").is_in(years))
                if filters:
                    for col, val in filters.items():
                        if isinstance(val, list):
                            lazy = lazy.filter(pl.col(col).is_in(val))
                        else:
                            lazy = lazy.filter(pl.col(col) == val)
                df = lazy.collect()
                print(f"  ✓ {name}: {df.shape[0]:,} rows (after lazy filters)")
                return df
            else:
                print(f"  Skipping {name}: unknown read_strategy '{strategy}'")
                continue

            print(f"  ✓ {name}: {df.shape[0]:,} rows")

            # Apply filters for eagerly-loaded formats (parquet, etc.)
            if years:
                df = df.filter(pl.col("year").is_in(years))
            if filters:
                for col, val in filters.items():
                    if isinstance(val, list):
                        df = df.filter(pl.col(col).is_in(val))
                    else:
                        df = df.filter(pl.col(col) == val)

            print(f"  After filters: {df.shape[0]:,} rows")
            return df

        except Exception as e:
            last_error = e
            print(f"  ✗ {name} failed: {e}")
            continue

    raise RuntimeError(f"All mirrors failed. Last error: {last_error}")
```

```r
library(arrow)
library(dplyr)
library(readr)
library(yaml)
library(httr2)

# --- Rate Limiting ---
# INTENT: Prevent HTTP 429 (Too Many Requests) errors from mirrors.
# REASONING: Mirrors may rate-limit rapid successive requests. A 3-second delay
#   between fetch calls avoids triggering limits while keeping pipeline runtime
#   reasonable (most fetches are sequential anyway).
FETCH_DELAY_SECONDS <- 3
last_fetch_time <- 0.0

# --- Download Timeout (R only) ---
# INTENT: Prevent large mirror files from truncating mid-transfer.
# REASONING: Both arrow::read_parquet(url) and readr::read_csv(url) route their
#   HTTP transfer through R's download.file(), which enforces getOption("timeout")
#   (default 60s) on the ENTIRE transfer — not per-idle-period. Large mirror files
#   (e.g., ccd/schools_ccd_directory.parquet, ~224MB) need 150-400s at real CDN
#   throughput (~0.55-1.4 MB/s), so they truncate at ~60s with a
#   "downloaded length X != reported length Y" warning and silently fall through
#   to the next (CSV) mirror. mirrors.yaml declares timeout: 300 per mirror, but
#   the R read functions never consult it — the setting must be applied here.
#   Python (Polars/pyarrow) uses its own HTTP client and is unaffected.
options(timeout = max(600, getOption("timeout")))

rate_limit <- function() {
  if (last_fetch_time > 0) {
    elapsed <- as.numeric(Sys.time()) - last_fetch_time
    if (elapsed < FETCH_DELAY_SECONDS) {
      wait <- FETCH_DELAY_SECONDS - elapsed
      cat(sprintf("  (rate limit: waiting %.1fs)\n", wait))
      Sys.sleep(wait)
    }
  }
  last_fetch_time <<- as.numeric(Sys.time())
}

# --- Mirror Configuration ---
# INTENT: Download dataset from the fastest available mirror.
# REASONING: Mirrors are loaded from mirrors.yaml (the single source of truth).
#   Each mirror specifies its own url_template, read_strategy, and timeout.
#   The first successful response is used; failures fall through to the next mirror.
# REFERENCE: See mirrors.yaml for mirror definitions, datasets-reference.md for paths.

# Load mirror config from mirrors.yaml (adjust path to your project)
mirrors_yaml_path <- "mirrors.yaml"  # Adjust path as needed
config <- yaml::read_yaml(mirrors_yaml_path)
mirrors <- config$mirrors

# Dataset path: canonical path string from datasets-reference.md.
# All mirrors use the same path — only root_url and format differ.
# Example for SAIPE district poverty:
DATASET_PATH <- "saipe/districts_saipe"

# --- Single-File Fetch: Try each mirror in order ---
# INTENT: Try each mirror in priority order. Return data frame on first success.
# Args:
#   path: Canonical dataset path string from datasets-reference.md.
#   filters: Named list of column->value(s) filters to apply locally.
#   years: Integer vector of years to filter to.
# Returns: Filtered tibble.

rate_limit()
last_error <- NULL
# REASONING (variable name): the loop target is mirror_df, deliberately NOT df.
#   `<<-` evaluated at the top level of a script searches the package search path
#   (it skips the global environment's own frame), so `df <<- ...` finds the
#   LOCKED binding stats::df first and fails with
#   "cannot change value of locked binding for 'df'". Any loop variable whose
#   name masks an attached-package object (df, c, t, T, data, ...) breaks the
#   <<- idiom this way — use a distinctive name.
mirror_df <- NULL

for (mirror in mirrors) {
  mirror_name <- mirror$name
  strategy <- mirror$read_strategy

  # Build URL from template + canonical path
  url <- glue::glue(mirror$url_template,
                     root_url = mirror$root_url,
                     path = DATASET_PATH,
                     format = mirror$format)
  cat(sprintf("  Trying %s: %s\n", mirror_name, url))

  result <- tryCatch({
    if (strategy == "eager_parquet") {
      # REASONING: Parquet files have embedded schema, no inference needed.
      #   arrow reads HTTP URLs natively via arrow::read_parquet().
      # REASONING (view-safe read): mirror files are Polars-written; some declare
      #   string columns as `string_view` in the parquet-native schema. The R arrow
      #   binding reads these at the C++ layer but fails at Table->data.frame with
      #   "cannot handle Array of type <utf8_view>". So read as an Arrow Table
      #   (as_data_frame = FALSE tolerates view types), cast any view columns to
      #   their materialized equivalents, THEN convert. The cast is a no-op on files
      #   without view types, so this is safe for every mirror read.
      # ASSUMES: arrow::open_dataset(url) |> dplyr::collect() is NOT a valid
      #   alternative — it hits the identical utf8_view conversion error. Non-view
      #   columns (including integer IDs) pass through untouched: no leading-zero risk.
      tbl <- arrow::read_parquet(url, as_data_frame = FALSE)
      sch <- tbl$schema
      fields <- lapply(seq_len(length(sch$names)), function(i) {
        fld <- sch$field(i - 1L)                   # $field() is 0-indexed (C++ convention)
        ts  <- fld$type$ToString()
        # REASONING: check large_string_view before string_view — the former's
        #   ToString() contains the substring "string_view", so an unordered check
        #   would misclassify large_string_view as plain string_view.
        new_type <- if (grepl("large_string_view", ts, fixed = TRUE)) arrow::large_utf8()
          else if (grepl("string_view", ts, fixed = TRUE)) arrow::utf8()
          else if (grepl("binary_view", ts, fixed = TRUE)) arrow::binary()
          else fld$type
        arrow::field(fld$name, new_type)
      })
      mirror_df <<- as.data.frame(tbl$cast(arrow::schema(fields)))
    } else if (strategy == "lazy_csv") {
      # REASONING: CSV files can be large. readr handles efficiently.
      # ASSUMES: CSV has standard column names matching parquet schema.
      mirror_df <<- readr::read_csv(url, show_col_types = FALSE)
    } else {
      cat(sprintf("  Skipping %s: unknown read_strategy '%s'\n", mirror_name, strategy))
      next
    }
    cat(sprintf("  Success %s: %s rows\n", mirror_name, format(nrow(mirror_df), big.mark = ",")))
    "success"
  }, error = function(e) {
    last_error <<- e
    cat(sprintf("  Failed %s: %s\n", mirror_name, conditionMessage(e)))
    "error"
  })

  if (identical(result, "success")) break
}

if (is.null(mirror_df)) stop(paste("All mirrors failed. Last error:", conditionMessage(last_error)))

# Hand off to the conventional working name (plain <- in the global frame is
# unaffected by the stats::df masking that breaks <<- above)
df <- mirror_df

# Apply filters locally
if (!is.null(years)) {
  df <- df |> filter(year %in% years)
}
# For additional filters, apply with dplyr::filter():
# df <- df |> filter(fips == 6, charter == 1)

cat(sprintf("  After filters: %s rows\n", format(nrow(df), big.mark = ",")))
```

### Yearly Dataset (one file per year)

```python
def fetch_yearly_from_mirrors(
    path_template: str,
    years: list[int],
    year_placeholder: str = "{year}",
    filters: dict | None = None,
) -> pl.DataFrame:
    """Fetch yearly files and concatenate.

    For datasets split into per-year files (e.g., enrollment, assessments),
    download each year separately and concatenate.

    Args:
        path_template: Canonical path string with a year placeholder.
            The year_placeholder is substituted with each year before fetching.
            Example: "ccd/schools_ccd_enrollment_{year}"
        years: List of years to fetch
        year_placeholder: String in path_template to replace with year (default: "{year}")
        filters: Additional column filters

    Returns:
        Concatenated, filtered Polars DataFrame
    """
    frames = []

    for year in years:
        # Substitute {year} in the path template for this year
        year_path = path_template.replace(year_placeholder, str(year))

        print(f"\n  Year {year}:")

        try:
            df = fetch_from_mirrors(
                year_path,
                filters=filters,
                years=[year],  # Filter to this specific year
            )
            frames.append(df)
            print(f"    → {df.shape[0]:,} rows")
        except RuntimeError:
            print(f"    → SKIP: Year {year} not available from any mirror")

    if not frames:
        raise RuntimeError(f"No data retrieved for any year in {years}")

    result = pl.concat(frames, how="diagonal_relaxed")
    print(f"\n  Combined: {result.shape[0]:,} rows x {result.shape[1]} cols")
    return result
```

```r
# --- Yearly Dataset Fetch: one file per year, concatenated ---
# INTENT: Fetch yearly files and bind into a single data frame.
# Args:
#   path_template: Canonical path with "{year}" placeholder.
#     Example: "ccd/schools_ccd_enrollment_{year}"
#   years: Integer vector of years to fetch.
# Returns: Combined tibble across all years.
# NOTE (R download timeout): if you run this yearly block WITHOUT the single-file
#   Config block above, set the download timeout here too — download.file()'s 60s
#   default truncates large yearly files. Any large per-year file needs it:
#     options(timeout = max(600, getOption("timeout")))
#   (See the single-file Config block for the full REASONING. Python is unaffected.)

path_template <- "ccd/schools_ccd_enrollment_{year}"
years <- c(2020, 2021, 2022)

frames <- list()

for (year in years) {
  # Substitute {year} in the path template
  year_path <- gsub("\\{year\\}", as.character(year), path_template)
  cat(sprintf("\n  Year %d:\n", year))

  result <- tryCatch({
    rate_limit()
    last_error_yearly <- NULL
    year_df <- NULL

    for (mirror in mirrors) {
      url <- glue::glue(mirror$url_template,
                         root_url = mirror$root_url,
                         path = year_path,
                         format = mirror$format)
      cat(sprintf("    Trying %s: %s\n", mirror$name, url))

      year_result <- tryCatch({
        if (mirror$read_strategy == "eager_parquet") {
          # REASONING (view-safe read): same utf8_view hazard as the single-file
          #   branch above — Polars-written mirror parquet may declare string_view
          #   columns the R arrow binding cannot convert directly. Read as an Arrow
          #   Table, cast view types to materialized, then convert. No-op on files
          #   without view types. Do NOT substitute open_dataset()|>collect() (same
          #   failure). See the single-file eager_parquet branch for the annotated form.
          tbl <- arrow::read_parquet(url, as_data_frame = FALSE)
          sch <- tbl$schema
          fields <- lapply(seq_len(length(sch$names)), function(i) {
            fld <- sch$field(i - 1L)               # 0-indexed (C++ convention)
            ts  <- fld$type$ToString()
            new_type <- if (grepl("large_string_view", ts, fixed = TRUE)) arrow::large_utf8()
              else if (grepl("string_view", ts, fixed = TRUE)) arrow::utf8()
              else if (grepl("binary_view", ts, fixed = TRUE)) arrow::binary()
              else fld$type
            arrow::field(fld$name, new_type)
          })
          year_df <<- as.data.frame(tbl$cast(arrow::schema(fields)))
        } else if (mirror$read_strategy == "lazy_csv") {
          year_df <<- readr::read_csv(url, show_col_types = FALSE)
        }
        "success"
      }, error = function(e) {
        last_error_yearly <<- e
        cat(sprintf("    Failed %s: %s\n", mirror$name, conditionMessage(e)))
        "error"
      })

      if (identical(year_result, "success")) break
    }

    if (is.null(year_df)) stop("All mirrors failed")
    year_df <- year_df |> filter(year == !!year)
    cat(sprintf("    -> %s rows\n", format(nrow(year_df), big.mark = ",")))
    frames[[length(frames) + 1]] <<- year_df
    "success"
  }, error = function(e) {
    cat(sprintf("    -> SKIP: Year %d not available from any mirror\n", year))
    "skip"
  })
}

if (length(frames) == 0) stop(paste("No data retrieved for any year in", paste(years, collapse = ", ")))
result <- bind_rows(frames)
cat(sprintf("\n  Combined: %s rows x %d cols\n", format(nrow(result), big.mark = ","), ncol(result)))
```

### Large Files (100MB+), R: download-to-disk variant

For large mirror files, raising `options(timeout = ...)` (shown in the patterns
above) is sufficient — `arrow::read_parquet(url)` completes once the timeout
exceeds the transfer time (confirmed: `ccd/schools_ccd_directory.parquet`, ~224MB,
read directly from URL in ~100-285s across observed runs — CDN throughput varies
several-fold, so treat any single timing as an observation, not a guarantee).
Prefer that in-memory path when it works, since it leaves no on-disk artifact to
manage.

When you want a **resumable, progress-aware** download instead — for very large
files (>~100MB) or flaky links where a mid-transfer failure is costly — download
to disk with `curl::multi_download()` and then do a view-safe local read. Unlike
`download.file()`, `curl::multi_download()` streams to disk, resumes partial
transfers, and does not depend on `getOption("timeout")` (it uses libcurl's own
connect/low-speed timeouts).

```r
library(arrow)
library(curl)

# --- Config ---
# INTENT: Fetch a large mirror parquet file to disk, resumably, then read it.
# REASONING: curl::multi_download() streams to disk and resumes partial transfers,
#   so a dropped connection does not restart from zero. It bypasses R's
#   download.file() 60s timeout entirely (uses libcurl connect/low-speed timeouts).
# ASSUMES: DATASET_PATH and the huggingface root_url resolve to a real parquet URL;
#   cache_dir is inside the project (never /tmp — outside the backup/audit boundary).
DATASET_PATH <- "ccd/schools_ccd_directory"
root_url <- "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main"
url <- sprintf("%s/%s.parquet", root_url, DATASET_PATH)

cache_dir <- file.path(PROJECT_DIR, "scripts", "scratch")   # inside project; NOT /tmp
dir.create(cache_dir, recursive = TRUE, showWarnings = FALSE)
dest <- file.path(cache_dir, paste0(gsub("/", "_", DATASET_PATH), ".parquet"))

# --- Download (resumable) ---
dl <- curl::multi_download(url, dest, resume = TRUE)
# REASONING: multi_download() returns a status frame rather than throwing on HTTP
#   errors, so validate explicitly. status_code 200 == fresh full transfer;
#   206 == a resume completed. Both are byte-complete successes.
stopifnot(isTRUE(dl$success), dl$status_code %in% c(200L, 206L))
cat(sprintf("  Downloaded %s to %s\n",
            format(file.info(dest)$size, big.mark = ","), dest))

# --- View-safe local read ---
# REASONING: identical view-safe cast as the URL read — mirror files are
#   Polars-written and may declare string_view columns the R arrow binding cannot
#   convert directly. The cast is a no-op on plain-string files, so it is safe here.
tbl <- arrow::read_parquet(dest, as_data_frame = FALSE)
sch <- tbl$schema
fields <- lapply(seq_len(length(sch$names)), function(i) {
  fld <- sch$field(i - 1L)                                # 0-indexed (C++ convention)
  ts  <- fld$type$ToString()
  new_type <- if (grepl("large_string_view", ts, fixed = TRUE)) arrow::large_utf8()
    else if (grepl("string_view", ts, fixed = TRUE)) arrow::utf8()
    else if (grepl("binary_view", ts, fixed = TRUE)) arrow::binary()
    else fld$type
  arrow::field(fld$name, new_type)
})
df <- as.data.frame(tbl$cast(arrow::schema(fields)))

# --- Validate ---
# INTENT: confirm the download succeeded and the file reads fully.
# REASONING: dl$success + status 200/206 above guard the transfer, and parquet
#   stores its footer at END of file — so a successful arrow read of dest is
#   itself strong evidence the file is not truncated. For strict byte-level
#   verification, HEAD the URL for content-length and compare to
#   file.info(dest)$size before reading.
stopifnot(nrow(df) > 0)
cat(sprintf("  Read %s rows x %d cols\n", format(nrow(df), big.mark = ","), ncol(df)))
# Optional: delete the artifact once loaded to avoid retaining a large scratch file.
# file.remove(dest)
```

---

## Mirror Discovery

Use mirror discovery to check what files are currently available before attempting a fetch. The discovery method for each mirror is defined in `mirrors.yaml`.

### Generic Discovery Function

```python
import requests

def discover_mirror_files(mirror_config: dict) -> list[str] | None:
    """Query a mirror's discovery endpoint to list available files.

    Args:
        mirror_config: A single mirror entry from mirrors.yaml, including
            its 'discovery' section.

    Returns:
        List of file paths available in the mirror, or None if discovery
        is not supported (e.g., method is 'known_complete').
    """
    discovery = mirror_config.get("discovery", {})
    method = discovery.get("method")

    if method == "http_json":
        url = discovery["url"]
        file_filter = discovery.get("file_filter", "*")

        response = requests.get(url, timeout=30)
        response.raise_for_status()
        raw = response.json()

        # Handle paginated response envelopes (e.g., Urban CSV returns
        # {"count": N, "results": [...]} instead of a flat list).
        if isinstance(raw, dict) and "results" in raw:
            entries = raw["results"]
        elif isinstance(raw, list):
            entries = raw
        else:
            print(f"  Unexpected discovery response type: {type(raw)}")
            return None

        # Handle response format differences between mirrors.
        # Some mirrors return separate dir + name fields; others use a single path field.
        # The keys are configured in mirrors.yaml's discovery section.
        file_dir_key = discovery.get("file_dir_key")
        file_name_key = discovery.get("file_name_key")
        path_key = discovery.get("file_path_key", "path")

        if file_dir_key and file_name_key:
            # Construct paths from separate dir + name fields
            paths = [
                f"{e[file_dir_key]}/{e[file_name_key]}"
                for e in entries
                if isinstance(e, dict) and e.get("hide", 0) == 0
            ]
        else:
            # Single path field
            paths = [e[path_key] for e in entries if isinstance(e, dict) and e.get("type") == "file"]

        # Apply file_filter if specified (simple suffix matching)
        if file_filter != "*":
            suffix = file_filter.lstrip("*")
            paths = [p for p in paths if p.endswith(suffix)]

        return paths

    elif method == "known_complete":
        # This mirror has complete coverage — all datasets in
        # datasets-reference.md are available. No query needed.
        return None

    else:
        print(f"  Unknown discovery method: {method}")
        return None


# Usage example:
# Check if a specific dataset is available in the primary mirror
# mirror = MIRRORS[0]  # highest priority
# files = discover_mirror_files(mirror)
# if files is not None:
#     target = "saipe/districts_saipe.parquet"
#     if target in files:
#         print("Available in primary mirror")
#     else:
#         print("Not in primary mirror — will fall through to next")
```

```r
# --- Mirror Discovery: check what files are available ---
# INTENT: Query a mirror's discovery endpoint to list available files.
# Returns character vector of file paths, or NULL if discovery not supported.

mirror <- mirrors[[1]]
discovery <- mirror$discovery

if (!is.null(discovery) && discovery$method == "http_json") {
  resp <- httr2::request(discovery$url) |>
    httr2::req_timeout(30) |>
    httr2::req_perform()
  raw <- httr2::resp_body_json(resp)

  # Handle paginated response envelopes
  entries <- if (!is.null(raw$results)) raw$results else raw

  # Extract paths based on mirror's discovery config
  file_dir_key <- discovery$file_dir_key
  file_name_key <- discovery$file_name_key

  if (!is.null(file_dir_key) && !is.null(file_name_key)) {
    # Construct paths from separate dir + name fields
    paths <- vapply(entries, function(e) {
      if (!is.null(e$hide) && e$hide != 0) return(NA_character_)
      paste0(e[[file_dir_key]], "/", e[[file_name_key]])
    }, character(1))
    paths <- paths[!is.na(paths)]
  } else {
    # Single path field
    path_key <- if (!is.null(discovery$file_path_key)) discovery$file_path_key else "path"
    paths <- vapply(entries, function(e) {
      if (!is.null(e$type) && e$type != "file") return(NA_character_)
      e[[path_key]]
    }, character(1))
    paths <- paths[!is.na(paths)]
  }

  # Apply file_filter if specified
  file_filter <- discovery$file_filter
  if (!is.null(file_filter) && file_filter != "*") {
    suffix <- sub("^\\*", "", file_filter)
    paths <- paths[grepl(paste0(suffix, "$"), paths)]
  }

  cat(sprintf("  Available files: %d\n", length(paths)))
} else if (!is.null(discovery) && discovery$method == "known_complete") {
  cat("  Mirror has complete coverage — no query needed\n")
  paths <- NULL
}

# Usage example:
# target <- "saipe/districts_saipe.parquet"
# if (!is.null(paths) && target %in% paths) {
#   cat("Available in primary mirror\n")
# }
```

---

## Metadata File References

Codebook and metadata files are available alongside data files in both mirrors. These are `.xls` files that document variable definitions, coded values, and data structure. Per the Truth Hierarchy below, codebooks rank **second** — below the actual data but above archived skill docs. They are not ingested into the analysis pipeline as data, but agents can download and read them programmatically to resolve ambiguities.

### Truth Hierarchy

When interpreting data values and resolving discrepancies between sources, apply this priority:

| Priority | Source | Rationale |
|----------|--------|-----------|
| 1 (highest) | **Actual data file** (parquet) | What you observe IS the truth |
| 2 | **Live codebook/metadata** (.xls in mirror) | Official documentation; may lag behind data |
| 3 (lowest) | **Archived skill docs** (variable-definitions.md) | Summarized; convenient but may drift |

- When skill docs contradict observed data → trust the data, flag the discrepancy
- When codebook contradicts observed data → trust the data, but investigate (codebook may describe a different year)
- When skill docs contradict codebook → trust the codebook, update skill docs

### When to Reference Codebooks

| Stage | Use Case |
|-------|----------|
| Stage 3 (Source Deep-Dive) | Verify variable definitions and coded values against authoritative codebook |
| Stage 6 (Context Application) | Resolve coded value ambiguities by consulting codebook |
| Data Onboarding | Reconcile observed data against codebook documentation |
| Discrepancy Investigation | When skill docs and observed data disagree, check codebook as tiebreaker |

### get_codebook_url()

Look up the codebook path from the `codebook` column in `datasets-reference.md`, then construct the full URL using the mirror's metadata configuration.

```python
def get_codebook_url(
    codebook_path: str,
    mirrors: list[dict] | None = None,
    yaml_path: Path | None = None,
) -> str:
    """Construct a codebook URL from a datasets-reference.md codebook path.

    Args:
        codebook_path: Canonical codebook path from datasets-reference.md codebook column.
            Example: "saipe/codebook_districts_saipe"
        mirrors: Pre-loaded mirror configs. If None, loads from yaml_path.
        yaml_path: Path to mirrors.yaml. If None, uses default.

    Returns:
        Full URL to the codebook file on the first mirror that has metadata config.
    """
    if mirrors is None:
        mirrors = load_mirrors(yaml_path or MIRRORS_YAML)

    for mirror in mirrors:
        meta = mirror.get("metadata")
        if not meta:
            continue

        fmt = meta["formats"][0]  # e.g., "xls"
        template = meta["url_template"]
        root_url = mirror["root_url"]

        # All mirrors resolve codebook the same way using the canonical path
        url = template.format(root_url=root_url, path=codebook_path, format=fmt)

        return url

    raise ValueError("No mirror with metadata configuration found")


# Usage:
# url = get_codebook_url("saipe/codebook_districts_saipe")
# → "{root_url}/saipe/codebook_districts_saipe.xls" (from first mirror with metadata config)
```

```r
# --- get_codebook_url: construct codebook URL from canonical path ---
# INTENT: Build a codebook download URL from a datasets-reference.md codebook path.
# Args:
#   codebook_path: Canonical codebook path (e.g., "saipe/codebook_districts_saipe")
# Returns: Full URL string to the codebook .xls file.

codebook_path <- "saipe/codebook_districts_saipe"

codebook_url <- NULL
for (mirror in mirrors) {
  meta <- mirror$metadata
  if (is.null(meta)) next

  fmt <- meta$formats[[1]]  # e.g., "xls"
  codebook_url <- glue::glue(meta$url_template,
                              root_url = mirror$root_url,
                              path = codebook_path,
                              format = fmt)
  break
}
if (is.null(codebook_url)) stop("No mirror with metadata configuration found")
cat(sprintf("Codebook URL: %s\n", codebook_url))

# Usage:
# codebook_url  # e.g., "{root_url}/saipe/codebook_districts_saipe.xls"
```

### fetch_codebook()

Download a codebook `.xls` file from a mirror to a local cache directory. Returns the local file path. Skips download if the file already exists locally (session-level caching).

```python
import httpx
from pathlib import Path


def fetch_codebook(
    codebook_path: str,
    cache_dir: Path | str = Path("data/codebooks"),
    mirrors: list[dict] | None = None,
    yaml_path: Path | None = None,
    timeout: int = 60,
) -> Path:
    """Download a codebook .xls file from a mirror to a local cache.

    Args:
        codebook_path: Canonical codebook path from datasets-reference.md codebook column.
            Example: "saipe/codebook_districts_saipe"
        cache_dir: Local directory for cached codebook files.
        mirrors: Pre-loaded mirror configs. If None, loads from yaml_path.
        yaml_path: Path to mirrors.yaml. If None, uses default.
        timeout: HTTP request timeout in seconds.

    Returns:
        Path to the downloaded .xls file.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Derive local filename from the canonical path (flatten source/filename → filename.xls)
    local_name = codebook_path.replace("/", "_") + ".xls"
    local_path = cache_dir / local_name

    if local_path.exists():
        print(f"  Codebook cached: {local_path}")
        return local_path

    if mirrors is None:
        mirrors = load_mirrors(yaml_path or MIRRORS_YAML)

    # Try each mirror with metadata config
    last_error = None
    for mirror in mirrors:
        meta = mirror.get("metadata")
        if not meta:
            continue

        fmt = meta["formats"][0]  # e.g., "xls"
        template = meta["url_template"]
        root_url = mirror["root_url"]
        url = template.format(root_url=root_url, path=codebook_path, format=fmt)

        print(f"  Fetching codebook from {mirror['name']}: {url}")

        try:
            _rate_limit()
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.get(url)
                resp.raise_for_status()

            local_path.write_bytes(resp.content)
            print(f"  ✓ Saved: {local_path} ({len(resp.content):,} bytes)")
            return local_path

        except Exception as e:
            last_error = e
            print(f"  ✗ {mirror['name']} failed: {e}")
            continue

    raise RuntimeError(
        f"All mirrors failed for codebook '{codebook_path}'. Last error: {last_error}"
    )


# Usage:
# path = fetch_codebook("saipe/codebook_districts_saipe")
# → downloads to data/codebooks/saipe_codebook_districts_saipe.xls
```

```r
# --- fetch_codebook: download codebook .xls to local cache ---
# INTENT: Download a codebook .xls file from a mirror to a local cache directory.
# Returns the local file path. Skips download if file already exists (session cache).
# Args:
#   codebook_path: Canonical codebook path (e.g., "saipe/codebook_districts_saipe")
#   cache_dir: Local directory for cached codebook files.

codebook_path <- "saipe/codebook_districts_saipe"
cache_dir <- "data/codebooks"
dir.create(cache_dir, recursive = TRUE, showWarnings = FALSE)

# Derive local filename from canonical path
local_name <- paste0(gsub("/", "_", codebook_path), ".xls")
local_path <- file.path(cache_dir, local_name)

if (file.exists(local_path)) {
  cat(sprintf("  Codebook cached: %s\n", local_path))
} else {
  last_error_cb <- NULL
  downloaded <- FALSE

  for (mirror in mirrors) {
    meta <- mirror$metadata
    if (is.null(meta)) next

    fmt <- meta$formats[[1]]
    url <- glue::glue(meta$url_template,
                       root_url = mirror$root_url,
                       path = codebook_path,
                       format = fmt)
    cat(sprintf("  Fetching codebook from %s: %s\n", mirror$name, url))

    result_cb <- tryCatch({
      rate_limit()
      resp <- httr2::request(url) |>
        httr2::req_timeout(60) |>
        httr2::req_perform()
      writeBin(httr2::resp_body_raw(resp), local_path)
      cat(sprintf("  Saved: %s (%s bytes)\n", local_path,
                  format(file.size(local_path), big.mark = ",")))
      downloaded <<- TRUE
      "success"
    }, error = function(e) {
      last_error_cb <<- e
      cat(sprintf("  Failed %s: %s\n", mirror$name, conditionMessage(e)))
      "error"
    })

    if (identical(result_cb, "success")) break
  }

  if (!downloaded) {
    stop(paste("All mirrors failed for codebook. Last error:",
               conditionMessage(last_error_cb)))
  }
}

# Usage:
# local_path  # e.g., "data/codebooks/saipe_codebook_districts_saipe.xls"
```

### read_codebook()

Download (if needed) and read a codebook into a dict of DataFrames, one per sheet. This is the primary entry point for agents that need to inspect codebook contents.

```python
import polars as pl


def read_codebook(
    codebook_path: str,
    cache_dir: Path | str = Path("data/codebooks"),
    mirrors: list[dict] | None = None,
    yaml_path: Path | None = None,
) -> dict[str, pl.DataFrame]:
    """Download and read a codebook .xls file. Returns {sheet_name: DataFrame}.

    Combines fetch_codebook() + sheet reading into a single call.
    Uses openpyxl for .xlsx and xlrd for .xls files.

    Args:
        codebook_path: Canonical codebook path from datasets-reference.md codebook column.
            Example: "saipe/codebook_districts_saipe"
        cache_dir: Local directory for cached codebook files.
        mirrors: Pre-loaded mirror configs. If None, loads from yaml_path.
        yaml_path: Path to mirrors.yaml. If None, uses default.

    Returns:
        Dict mapping sheet names to Polars DataFrames.
    """
    local_path = fetch_codebook(
        codebook_path, cache_dir=cache_dir, mirrors=mirrors, yaml_path=yaml_path
    )

    # Read all sheets — try xlrd first (.xls), fall back to openpyxl (.xlsx)
    import pandas as pd

    try:
        sheets = pd.read_excel(local_path, sheet_name=None, engine="xlrd")
    except Exception:
        sheets = pd.read_excel(local_path, sheet_name=None, engine="openpyxl")

    # Convert pandas DataFrames to Polars
    result = {}
    for name, pdf in sheets.items():
        result[name] = pl.from_pandas(pdf)

    sheet_summary = ", ".join(
        f"{name} ({df.shape[0]}×{df.shape[1]})" for name, df in result.items()
    )
    print(f"  Codebook sheets: {sheet_summary}")

    return result


# Usage:
# sheets = read_codebook("saipe/codebook_districts_saipe")
# for name, df in sheets.items():
#     print(f"\n--- {name} ---")
#     print(df.head())
```

```r
# --- read_codebook: download (if needed) and read codebook into named list of data frames ---
# INTENT: Download and read a codebook .xls file. Returns named list of tibbles, one per sheet.
# Requires the readxl package.
# Assumes fetch_codebook R block above has already run and local_path is set.

library(readxl)

sheet_names <- readxl::excel_sheets(local_path)
sheets <- setNames(
  lapply(sheet_names, function(s) readxl::read_excel(local_path, sheet = s)),
  sheet_names
)

sheet_summary <- paste(
  vapply(names(sheets), function(nm) {
    sprintf("%s (%dx%d)", nm, nrow(sheets[[nm]]), ncol(sheets[[nm]]))
  }, character(1)),
  collapse = ", "
)
cat(sprintf("  Codebook sheets: %s\n", sheet_summary))

# Usage:
# for (nm in names(sheets)) {
#   cat(sprintf("\n--- %s ---\n", nm))
#   print(head(sheets[[nm]]))
# }
```

---

## Format Handling

Format-specific read behavior is driven by the mirror's `read_strategy` field in `mirrors.yaml`:

### `eager_parquet` (e.g., parquet files)
- Direct read with `pl.read_parquet(url)` — Polars handles HTTP natively
- Schema is embedded in the file (no inference needed)
- Columnar format: efficient for column-subset reads
- Compressed: typically 3-10x smaller than CSV
- Filters applied after loading into memory
- **R only — view-safe parquet read required:** The mirror files are Polars-written,
  and some declare string columns as `string_view` in the parquet-native schema
  (confirmed: `saipe/districts_saipe`, `edfacts/schools_edfacts_grad_rates_2015..2019`).
  The R `arrow` binding reads these at the C++ layer but fails at the
  Table->data.frame step with `cannot handle Array of type <utf8_view>`. Use the
  view-safe read pattern shown in the R mirror-loop `eager_parquet` branch above:
  read as an Arrow Table (`as_data_frame = FALSE`), cast any view columns to their
  materialized types, then convert. The cast is a no-op on plain-string files
  (e.g., `meps/schools_meps`), so it is safe for every read. **Do not** substitute
  `arrow::open_dataset(url) |> dplyr::collect()` — it hits the same error. Python
  (Polars/pyarrow) is unaffected.
- **R only — large-file download timeout:** `arrow::read_parquet(url)` routes its
  transfer through R's `download.file()`, which caps the ENTIRE transfer at
  `getOption("timeout")` (default 60s). Large mirror files (e.g.,
  `ccd/schools_ccd_directory.parquet`, ~224MB) truncate at ~60s with a
  `downloaded length X != reported length Y` warning and silently fall through to
  the next mirror in priority order (the CSV fallback, in the default
  configuration). Raise the timeout before the mirror loop:
  `options(timeout = max(600, getOption("timeout")))`. For very large or flaky
  transfers, prefer the download-to-disk variant (`curl::multi_download()`) in the
  Mirror Resolution section. Python (Polars/pyarrow) is unaffected.

### `lazy_csv` (e.g., CSV files)
- Use `pl.scan_csv(url, infer_schema_length=10000)` for lazy loading
- Set `infer_schema_length=10000` to avoid type inference errors on large files
- Apply filters in the lazy frame before `.collect()` to minimize memory
- Large files (500MB+) — always use lazy loading, never `pl.read_csv()` directly
- **Zero-padded ID columns (CRDC, EDFacts, SAIPE) — general principle:** Portal ID columns (`ncessch`→12 chars, `leaid`→7 chars, and CRDC's `crdc_id`) are zero-padded strings whose leading zeros carry state-FIPS identity (FIPS 01-09 states: AL, AK, AZ, AR, CA, CO, CT — ~19% of school rows). CSV type inference reads them as Int64 and silently drops the leading zeros, splitting the join key for those states. Parquet reads preserve types automatically, so this only bites CSV-fallback reads. **Two defenses are needed, not one:** (1) force-string on read, AND (2) pad-and-assert *after* read. Force-string alone is insufficient because a source file can ship an ID that is *already* truncated — see the EDFacts 2019 note below — in which case `col_character()`/`schema_overrides` faithfully preserve a value that is already wrong. Only pad-to-width plus a width assertion recovers and verifies these.
- **EDFacts 2019 truncated-ID trap (field-confirmed, HIGH impact):** In a native R-mode pipeline run, 2019 EDFacts grad-rate CSVs delivered 11-character `ncessch` for single-digit-FIPS states (1/2/4/5/6/8/9), versus 12-character in 2015-2018 — the source file itself had already lost the leading zero. Forcing string on read did **not** restore it (there was nothing to restore; the character was gone from the file). The working fix was `str_pad(ncessch, 12)` / `str_pad(leaid, 7)` immediately after each CSV read, before any bind/join, plus `stopifnot(nchar == 12/7)` (R) or an `assert` on `.str.len_chars()` (Python) to catch the failure loudly. In that run this repaired 43,223 short IDs, all localized to 2019. Treat force-string + pad + width-assert as the standard CSV-fallback ID recipe for EDFacts and SAIPE, not just CRDC.
- **Force-string on read (Python, Polars):** `schema_overrides={"ncessch": pl.Utf8, "leaid": pl.Utf8}` — add `"crdc_id": pl.Utf8` for CRDC datasets. This is defense (1).
- **Pad-and-assert after read (Python, Polars):** defense (2) — recovers already-truncated IDs and fails loudly if a width is unexpected:
  ```python
  # INTENT: enforce canonical zero-padded ID widths after CSV fallback read.
  # REASONING: force-string preserves what the file holds, but 2019 EDFacts ships
  #   already-truncated ncessch (11-char) for single-digit-FIPS states; only
  #   pad-to-width recovers them. ncessch=12, leaid=7.
  # ASSUMES: ids are strings (defense 1 applied); a value longer than target width
  #   is a genuine anomaly, not a pad candidate.
  df = df.with_columns(
      pl.col("ncessch").cast(pl.Utf8).str.zfill(12),
      pl.col("leaid").cast(pl.Utf8).str.zfill(7),
  )
  assert (df["ncessch"].str.len_chars() == 12).all(), "ncessch width != 12 after pad"
  assert (df["leaid"].str.len_chars() == 7).all(), "leaid width != 7 after pad"
  ```
- **Force-string on read (R, readr):** `col_types = readr::cols(ncessch = readr::col_character(), leaid = readr::col_character())` — add `crdc_id = readr::col_character()` for CRDC. This is defense (1).
- **Pad-and-assert after read (R, readr/stringr):** defense (2):
  ```r
  # INTENT: enforce canonical zero-padded ID widths after CSV fallback read.
  # REASONING: col_character() preserves what the file holds, but 2019 EDFacts ships
  #   already-truncated ncessch (11-char) for single-digit-FIPS states; only
  #   str_pad recovers them. ncessch=12, leaid=7.
  # ASSUMES: ids are character (defense 1 applied); a value wider than the target is
  #   a genuine anomaly, not a pad candidate.
  library(stringr)
  df <- df |>
    mutate(
      ncessch = str_pad(ncessch, 12, pad = "0"),
      leaid   = str_pad(leaid, 7, pad = "0")
    )
  stopifnot(all(nchar(df$ncessch) == 12), all(nchar(df$leaid) == 7))
  ```
- **Per-source specifics:** CRDC also has `crdc_id` (force-string; not an FIPS-padded key). EDFacts is the confirmed truncated-ID case (2019 grad rates). SAIPE's `leaid` is Int64 in the Portal even in parquet — a numeric read lost leading zeros for 14.6% of rows in the field run — so SAIPE needs `leaid`→7 pad-and-assert before any school→district join. See `education-data-source-crdc`, `education-data-source-edfacts`, and `education-data-source-saipe` skills for source-level detail.
- **R only — large-file download timeout:** `readr::read_csv(url)` routes its transfer through `download.file()` exactly like the parquet read, so the same 60s `getOption("timeout")` cap truncates large CSVs (these files reach 500MB+). Apply the same `options(timeout = max(600, getOption("timeout")))` before reading — see the `eager_parquet` bullet above.

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| HTTP 404 | File not in this mirror | Fall through to next mirror |
| Timeout | Large file or slow connection | Increase timeout; fall through. **R only:** both read strategies route through `download.file()`, capped at `getOption("timeout")` (default 60s) — raise it with `options(timeout = max(600, getOption("timeout")))` before the loop, or use `curl::multi_download()` for very large files. A silent truncation shows as `downloaded length X != reported length Y`. |
| Schema mismatch | CSV column types differ from parquet | Use `infer_schema_length=10000` |
| Empty DataFrame | Filters too restrictive | Check filter values; verify year availability |
| All mirrors failed | Dataset not available in any mirror | STOP and escalate to user |
| Codebook read error (xlrd) | `.xls` format not readable by xlrd | Auto-falls back to openpyxl engine |
| Codebook read error (both) | Corrupt or non-Excel file served | Check URL manually; try alternate mirror |
| Codebook empty sheets | Codebook has no data rows | Likely a metadata-only file; inspect raw `.xls` |

---

## Portal Integer Encoding Notes

**CRITICAL:** The Portal uses integer codes, not string labels. When filtering downloaded data:

### Demographic Variables

| Variable | Integer Values | NOT These Strings |
|----------|----------------|-------------------|
| Race | 1-7, 99 (total) | WH, BL, HI, AS |
| Sex | 1 (Male), 2 (Female), 99 | M, F |
| Grade | -1 to 13, 99 (total) | PK, KG, 01 |

### Grade Encoding (SEMANTIC TRAP!)

```python
# WRONG - filters out Pre-K students!
df = df.filter(pl.col("grade") >= 0)

# RIGHT - grade=-1 is Pre-K, NOT missing data
pre_k = df.filter(pl.col("grade") == -1)
k_12 = df.filter(pl.col("grade").is_between(0, 12))
total = df.filter(pl.col("grade") == 99)
```

```r
# WRONG - filters out Pre-K students!
df <- df |> filter(grade >= 0)

# RIGHT - grade=-1 is Pre-K, NOT missing data
pre_k <- df |> filter(grade == -1)
k_12 <- df |> filter(between(grade, 0, 12))
total <- df |> filter(grade == 99)
```

### Variable Names Are Lowercase

Portal variable names are lowercase:
- `enrollment` not `MEMBER`
- `grade` not `GRADE`
- `fips` not `FIPS`

---

## IAT Documentation for Fetch Scripts

Every fetch script must include these IAT comments:

```python
# --- Mirror Resolution ---
# INTENT: Download {dataset_name} from the fastest available mirror.
# REASONING: Mirrors are tried in priority order per mirrors.yaml config.
#   Format-specific read strategy is driven by each mirror's read_strategy field.
# ASSUMES: Mirror URLs are current and accessible; each mirror uses the same canonical
#   path with its own root_url and format.
#   Year/filter columns exist in the dataset with expected names.
#   Portal uses integer encoding: grade=-1 is Pre-K (NOT missing), race=1-7, sex=1-2.
# REFERENCE: mirrors.yaml for mirror config, datasets-reference.md for canonical paths.
```

```r
# --- Mirror Resolution ---
# INTENT: Download {dataset_name} from the fastest available mirror.
# REASONING: Mirrors are tried in priority order per mirrors.yaml config.
#   Format-specific read strategy is driven by each mirror's read_strategy field.
# ASSUMES: Mirror URLs are current and accessible; each mirror uses the same canonical
#   path with its own root_url and format.
#   Year/filter columns exist in the dataset with expected names.
#   Portal uses integer encoding: grade=-1 is Pre-K (NOT missing), race=1-7, sex=1-2.
# REFERENCE: mirrors.yaml for mirror config, datasets-reference.md for canonical paths.
```
