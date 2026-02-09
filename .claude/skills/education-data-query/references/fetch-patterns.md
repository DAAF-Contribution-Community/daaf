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
import polars as pl
import requests
import yaml
from pathlib import Path

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
DATASET_PATH = "saipe/geography_saipe"


def fetch_from_mirrors(
    path: str,
    filters: dict | None = None,
    years: list[int] | None = None,
) -> pl.DataFrame:
    """Try each mirror in order. Return DataFrame on first success.

    Args:
        path: Canonical dataset path string from datasets-reference.md.
            All mirrors use the same path — only root_url and format differ.
            Example: "saipe/geography_saipe"
        filters: Dict of column->value(s) filters to apply locally
        years: List of years to filter to (applied as pl.col("year").is_in(years))

    Returns:
        Filtered Polars DataFrame
    """
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
        entries = response.json()

        # Handle response format differences between mirrors.
        # HuggingFace: objects have "path" and "type" fields.
        # Urban CSV:   objects have "file_dir" and "file_name" fields.
        file_dir_key = discovery.get("file_dir_key")
        file_name_key = discovery.get("file_name_key")
        path_key = discovery.get("file_path_key", "path")

        if file_dir_key and file_name_key:
            # Construct paths from separate dir + name fields (e.g., Urban CSV)
            paths = [
                f"{e[file_dir_key]}/{e[file_name_key]}"
                for e in entries
                if e.get("hide", 0) == 0
            ]
        else:
            # Single path field (e.g., HuggingFace)
            paths = [e[path_key] for e in entries if e.get("type") == "file"]

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
#     target = "saipe/geography_saipe.parquet"
#     if target in files:
#         print("Available in primary mirror")
#     else:
#         print("Not in primary mirror — will fall through to next")
```

---

## Metadata File References

Codebook and metadata files are available alongside data files in both mirrors. These are `.xls` files for human reference — not parsed programmatically by the pipeline.

### Truth Hierarchy

When interpreting data values and resolving discrepancies between sources, apply this priority:

| Priority | Source | Rationale |
|----------|--------|-----------|
| 1 (highest) | **Actual data file** (parquet) | What you observe IS the truth |
| 2 | **Live codebook/metadata** (.xls in mirror) | Authoritative documentation; may lag behind data |
| 3 (lowest) | **Archived skill docs** (variable-definitions.md) | Summarized; convenient but may drift |

- When skill docs contradict observed data → trust the data, flag the discrepancy
- When codebook contradicts observed data → trust the data, but investigate (codebook may describe a different year)
- When skill docs contradict codebook → trust the codebook, update skill docs

### When to Reference Codebooks

| Stage | Use Case |
|-------|----------|
| Stage 3 (Source Deep-Dive) | Verify variable definitions and coded values against authoritative codebook |
| Stage 6 (Context Application) | Resolve coded value ambiguities by consulting codebook |
| Data Ingest | Reconcile observed data against codebook documentation |
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
# → "https://huggingface.co/.../saipe/codebook_districts_saipe.xls"
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

### `lazy_csv` (e.g., CSV files)
- Use `pl.scan_csv(url, infer_schema_length=10000)` for lazy loading
- Set `infer_schema_length=10000` to avoid type inference errors on large files
- Apply filters in the lazy frame before `.collect()` to minimize memory
- Large files (500MB+) — always use lazy loading, never `pl.read_csv()` directly

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| HTTP 404 | File not in this mirror | Fall through to next mirror |
| Timeout | Large file or slow connection | Increase timeout; fall through |
| Schema mismatch | CSV column types differ from parquet | Use `infer_schema_length=10000` |
| Empty DataFrame | Filters too restrictive | Check filter values; verify year availability |
| All mirrors failed | Dataset not available in any mirror | STOP and escalate to user |

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
