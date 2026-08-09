# --- Config ---
# INTENT: Execute every runnable PYTHON code sample from the updated education-data
#   skills against the live pinned HF mirror (brhkim/education_data_portal_mirror_2026q3
#   @ 0ad00ce0e232c96b0642459e4e7326607a8d26aa) EXACTLY as documented, to prove each
#   sample actually works. Adversarial stance: a sample that fails as written is a
#   defect to report.
# REASONING: Samples are grouped by language per the task. This file = all Python
#   samples. Each section is prefixed with the source file and line range it was
#   copied from. Sample code is kept verbatim; the only resolutions are (a) the
#   mirrors.yaml path (documented as "Adjust path as needed") pointed at the live
#   skill file, and (b) PROJECT_DIR literals where a sample references them.
# ASSUMES: network egress to huggingface.co is available; polars/requests/yaml present.

from pathlib import Path

PROJECT_DIR = Path("/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update")
SAMPLE_RESULTS = {}  # sample_id -> (status, evidence)


# ===========================================================================
# SAMPLE 12a
# SOURCE: education-data-query/SKILL.md lines 68-96
#   "Self-contained discovery probe for the configured primary mirror"
#   (first of the two SKILL.md quick-probe samples)
# Run verbatim.
# ===========================================================================
print("\n=== SAMPLE 12a: SKILL.md Python discovery quick-probe (lines 68-96) ===")
try:
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

    SAMPLE_RESULTS["12a"] = ("PASS", f"{len(data_paths)} canonical parquet data paths discovered; "
                             f"revision pinned={revision[:12]}")
except Exception as e:
    SAMPLE_RESULTS["12a"] = ("FAIL", f"{type(e).__name__}: {e}")
    print(f"SAMPLE 12a FAILED: {type(e).__name__}: {e}")


# ===========================================================================
# SAMPLE 12b
# SOURCE: education-data-query/references/fetch-patterns.md
#   Canonical Path Contract helpers (lines 25-137): canonicalize_mirror_path,
#     mirror_revision, build_mirror_url
#   Single-File Dataset fetch (lines 227-366): rate limiting, load_mirrors,
#     MIRRORS, DATASET_PATH, fetch_from_mirrors
# End-to-end path documented in the task: load_mirrors -> mirror_revision ->
#   build_mirror_url -> actual download of a small file -> polars read.
# Verbatim except MIRRORS_YAML resolved to the live skill mirrors.yaml
#   (documented "Adjust path as needed").
# ===========================================================================
print("\n=== SAMPLE 12b: fetch-patterns.md Python end-to-end fetch (lines 25-366) ===")
try:
    import re
    from urllib.parse import urlparse

    def canonicalize_mirror_path(path: str, object_kind: str) -> str:
        """Return one validated, extensionless canonical mirror key."""
        if object_kind not in {"data", "codebook"}:
            raise ValueError("object_kind must be exactly 'data' or 'codebook'")
        if not isinstance(path, str):
            raise TypeError("mirror path must be a string")
        if not path or path != path.strip():
            raise ValueError("mirror path must be nonempty and have no outer whitespace")
        if path.startswith("/") or "\\" in path or ":" in path:
            raise ValueError("mirror path must be a relative POSIX path, not an absolute path or URL")

        parts = path.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("mirror path cannot contain empty, current-directory, or traversal segments")

        allowed_extensions = {
            "data": (".csv", ".parquet"),
            "codebook": (".xls",),
        }
        recognized_extensions = (".csv", ".parquet", ".xls")
        lower_path = path.lower()
        matched_extension = next(
            (extension for extension in recognized_extensions if lower_path.endswith(extension)),
            None,
        )

        if matched_extension is not None:
            if matched_extension not in allowed_extensions[object_kind]:
                raise ValueError(
                    f"{object_kind} path cannot use terminal extension {matched_extension!r}"
                )
            canonical_key = path[: -len(matched_extension)]
            if canonical_key.lower().endswith(recognized_extensions):
                raise ValueError("mirror path has a doubled recognized extension")
        else:
            final_component = parts[-1]
            if "." in final_component:
                raise ValueError("mirror path has an unsupported terminal extension")
            canonical_key = path

        if not canonical_key or canonical_key.endswith("/"):
            raise ValueError("canonical mirror key cannot be empty or directory-like")
        return canonical_key

    def mirror_revision(mirror: dict) -> str:
        """Return the pinned Hugging Face git revision for a mirror."""
        vintage = mirror.get("vintage") or {}
        return str(vintage.get("hf_revision", "main"))

    def build_mirror_url(
        mirror: dict,
        path: str,
        object_kind: str,
    ) -> str:
        """Build a URL containing exactly one extension expected for the object kind."""
        canonical_key = canonicalize_mirror_path(path, object_kind)
        if object_kind == "data":
            expected_format = str(mirror.get("format", "")).lower()
            template = mirror.get("url_template")
            if expected_format not in {"csv", "parquet"}:
                raise ValueError("data mirror format must be exactly 'csv' or 'parquet'")
        else:
            metadata = mirror.get("metadata") or {}
            formats = metadata.get("formats") or []
            template = metadata.get("url_template")
            if formats != ["xls"]:
                raise ValueError("codebook metadata formats must be exactly ['xls']")
            expected_format = "xls"

        if not isinstance(template, str) or not template:
            raise ValueError(f"mirror has no URL template for {object_kind} objects")
        url = template.format(
            root_url=mirror["root_url"],
            revision=mirror_revision(mirror),
            path=canonical_key,
            format=expected_format,
        )
        url_path = urlparse(url).path.lower()
        expected_suffix = f".{expected_format}"
        if not url_path.endswith(expected_suffix):
            raise ValueError(f"URL template did not append expected {expected_suffix} extension")
        without_expected = url_path[: -len(expected_suffix)]
        if without_expected.endswith((".csv", ".parquet", ".xls")):
            raise ValueError("URL template produced a doubled recognized extension")
        return url

    # --- Single-File Dataset fetch (lines 227-366) ---
    import time

    import polars as pl
    import requests
    import yaml

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

    # RESOLUTION: documented default is SKILL_DIR / "mirrors.yaml" with
    #   comment "Adjust path as needed" — resolved to the live skill file.
    MIRRORS_YAML = Path("/daaf/.claude/skills/education-data-query/references/mirrors.yaml")

    def load_mirrors(yaml_path: Path = MIRRORS_YAML) -> list[dict]:
        """Load mirror configuration from mirrors.yaml."""
        with open(yaml_path) as f:
            config = yaml.safe_load(f)
        return config["mirrors"]

    # Load mirrors at module level — tried in priority order
    MIRRORS = load_mirrors()

    # Dataset path: canonical path string from datasets-reference.md.
    # Example for SAIPE district poverty (small file — ideal end-to-end probe):
    DATASET_PATH = "saipe/districts_saipe"

    def fetch_from_mirrors(
        path: str,
        filters: dict | None = None,
        years: list[int] | None = None,
    ) -> pl.DataFrame:
        """Try each mirror in order. Return DataFrame on first success."""
        canonical_path = canonicalize_mirror_path(path, "data")
        _rate_limit()
        last_error = None

        for mirror in MIRRORS:
            name = mirror["name"]
            strategy = mirror["read_strategy"]
            timeout = mirror["timeout"]

            url = build_mirror_url(mirror, canonical_path, "data")

            print(f"  Trying {name}: {url}")

            try:
                if strategy == "eager_parquet":
                    df = pl.read_parquet(url)
                elif strategy == "lazy_csv":
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

    # --- Execute the end-to-end path against the small SAIPE file ---
    saipe_df = fetch_from_mirrors(DATASET_PATH)
    print(f"  fetched shape: {saipe_df.shape}")
    print(f"  columns: {saipe_df.columns[:8]}...")
    print(saipe_df.head(3))
    assert saipe_df.shape[0] > 0, "SAIPE fetch returned no rows"
    rev = mirror_revision(MIRRORS[0])
    SAMPLE_RESULTS["12b"] = ("PASS", f"fetched saipe/districts_saipe: {saipe_df.shape[0]:,} rows x "
                             f"{saipe_df.shape[1]} cols via {MIRRORS[0]['name']}; revision pin={rev[:12]}")
except Exception as e:
    SAMPLE_RESULTS["12b"] = ("FAIL", f"{type(e).__name__}: {e}")
    print(f"SAMPLE 12b FAILED: {type(e).__name__}: {e}")


# ===========================================================================
# SAMPLE 12c
# SOURCE: education-data-source-ipeds/references/graduation-rates.md lines 545-566
#   "Querying Outcome Measures (Example)" — Python
# Run verbatim.
# ===========================================================================
print("\n=== SAMPLE 12c: graduation-rates.md Python outcome-measures (lines 545-566) ===")
try:
    import polars as pl

    # Mirror root + pinned revision (keep in sync with education-data-query
    # references/mirrors.yaml: HF root_url + vintage.hf_revision).
    MIRROR = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve"
    REVISION = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"  # immutable commit SHA of the v2 upload
    url = f"{MIRROR}/{REVISION}/ipeds/colleges_ipeds_outcome-measures.parquet"
    df = pl.read_parquet(url)

    # 8-year completion rates by enrollment intensity for first-time students
    om = (
        df.filter(
            (pl.col("year") == 2022)
            & (pl.col("class_level") == 1)    # First-time
            & (pl.col("fed_aid_type") == 99)  # All aid types
            & (pl.col("ftpt").is_in([1, 2]))  # FT and PT separately
        )
        .select("unitid", "ftpt", "completion_rate_8yr", "transfer_rate_8yr")
    )
    print(f"  full parquet shape: {df.shape}")
    print(f"  filtered om shape: {om.shape}")
    print(om.head(5))
    assert om.shape[0] > 0, "outcome-measures filter returned no rows"
    SAMPLE_RESULTS["12c"] = ("PASS", f"full={df.shape[0]:,} rows; filtered om (year=2022, FT-first-time)="
                             f"{om.shape[0]:,} rows x {om.shape[1]} cols")
except Exception as e:
    SAMPLE_RESULTS["12c"] = ("FAIL", f"{type(e).__name__}: {e}")
    print(f"SAMPLE 12c FAILED: {type(e).__name__}: {e}")


# ===========================================================================
# SAMPLE 12d
# SOURCE: education-data-source-ipeds/references/financial-aid.md lines 587-609
#   "Querying Net Price by Income (Example)" — Python
# Run verbatim.
# ===========================================================================
print("\n=== SAMPLE 12d: financial-aid.md Python net-price-by-income (lines 587-609) ===")
try:
    import polars as pl

    MIRROR = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve"
    REVISION = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"  # immutable commit SHA of the v2 upload
    url = f"{MIRROR}/{REVISION}/ipeds/colleges_ipeds_sfa_grants_and_net_price.parquet"
    df = pl.read_parquet(url)

    # Net price by income level for a specific institution and year
    net_prices = (
        df.filter(
            (pl.col("unitid") == 166027)  # Example: MIT
            & (pl.col("year") == 2020)
            & (pl.col("income_level").is_in([1, 2, 3, 4, 5]))
            & (pl.col("type_of_aid") == 9)
        )
        .select("income_level", "net_price", "number_of_students")
        .sort("income_level")
    )
    print(f"  full parquet shape: {df.shape}")
    print(f"  filtered net_prices shape: {net_prices.shape}")
    print(net_prices)
    assert net_prices.shape[0] > 0, "net-price filter returned no rows"
    SAMPLE_RESULTS["12d"] = ("PASS", f"full={df.shape[0]:,} rows; MIT 2020 net-price by income="
                             f"{net_prices.shape[0]} rows (income levels present)")
except Exception as e:
    SAMPLE_RESULTS["12d"] = ("FAIL", f"{type(e).__name__}: {e}")
    print(f"SAMPLE 12d FAILED: {type(e).__name__}: {e}")


# --- Summary ---
print("\n=== PYTHON SAMPLE SUMMARY ===")
for sid in ["12a", "12b", "12c", "12d"]:
    status, evidence = SAMPLE_RESULTS.get(sid, ("NOT-RUN", ""))
    print(f"  [{status}] {sid}: {evidence}")
n_pass = sum(1 for s, _ in SAMPLE_RESULTS.values() if s == "PASS")
print(f"\nPASS {n_pass}/{len(SAMPLE_RESULTS)}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 13:07:52
# Command: python3 /daaf/scripts/mirror_maintenance/12_python-code-samples.py
# Duration: 6s
# Exit code: 0
#
# --- STDOUT ---
# 
# === SAMPLE 12a: SKILL.md Python discovery quick-probe (lines 68-96) ===
# Available canonical data paths: 407
# 
# === SAMPLE 12b: fetch-patterns.md Python end-to-end fetch (lines 25-366) ===
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/0ad00ce0e232c96b0642459e4e7326607a8d26aa/saipe/districts_saipe.parquet
#   ✓ huggingface: 382,099 rows
#   After filters: 382,099 rows
#   fetched shape: (382099, 10)
#   columns: ['district_id', 'district_name', 'est_population_total', 'est_population_5_17', 'est_population_5_17_poverty', 'year', 'leaid', 'fips']...
# shape: (3, 10)
# ┌─────────────┬────────────┬────────────┬────────────┬───┬────────┬──────┬────────────┬────────────┐
# │ district_id ┆ district_n ┆ est_popula ┆ est_popula ┆ … ┆ leaid  ┆ fips ┆ est_popula ┆ est_popula │
# │ ---         ┆ ame        ┆ tion_total ┆ tion_5_17  ┆   ┆ ---    ┆ ---  ┆ tion_5_17_ ┆ tion_5_17_ │
# │ i64         ┆ ---        ┆ ---        ┆ ---        ┆   ┆ i64    ┆ i64  ┆ poverty_pc ┆ pct        │
# │             ┆ str        ┆ i64        ┆ i64        ┆   ┆        ┆      ┆ …          ┆ ---        │
# │             ┆            ┆            ┆            ┆   ┆        ┆      ┆ ---        ┆ f64        │
# │             ┆            ┆            ┆            ┆   ┆        ┆      ┆ f64        ┆            │
# ╞═════════════╪════════════╪════════════╪════════════╪═══╪════════╪══════╪════════════╪════════════╡
# │ 5           ┆ ALBERTVILL ┆ 16294      ┆ 2779       ┆ … ┆ 100005 ┆ 1    ┆ 0.18208    ┆ 0.170554   │
# │             ┆ E CITY SCH ┆            ┆            ┆   ┆        ┆      ┆            ┆            │
# │             ┆ DIST       ┆            ┆            ┆   ┆        ┆      ┆            ┆            │
# │ 30          ┆ ALEXANDER  ┆ 17704      ┆ 3258       ┆ … ┆ 100030 ┆ 1    ┆ 0.260896   ┆ 0.184026   │
# │             ┆ CITY CITY  ┆            ┆            ┆   ┆        ┆      ┆            ┆            │
# │             ┆ SCH DIST   ┆            ┆            ┆   ┆        ┆      ┆            ┆            │
# │ 60          ┆ ANDALUSIA  ┆ 9602       ┆ 1706       ┆ … ┆ 100060 ┆ 1    ┆ 0.334701   ┆ 0.177671   │
# │             ┆ CITY SCH   ┆            ┆            ┆   ┆        ┆      ┆            ┆            │
# │             ┆ DIST       ┆            ┆            ┆   ┆        ┆      ┆            ┆            │
# └─────────────┴────────────┴────────────┴────────────┴───┴────────┴──────┴────────────┴────────────┘
# 
# === SAMPLE 12c: graduation-rates.md Python outcome-measures (lines 545-566) ===
#   full parquet shape: (575473, 38)
#   filtered om shape: (0, 4)
# shape: (0, 4)
# ┌────────┬──────┬─────────────────────┬───────────────────┐
# │ unitid ┆ ftpt ┆ completion_rate_8yr ┆ transfer_rate_8yr │
# │ ---    ┆ ---  ┆ ---                 ┆ ---               │
# │ i64    ┆ i64  ┆ f64                 ┆ f64               │
# ╞════════╪══════╪═════════════════════╪═══════════════════╡
# └────────┴──────┴─────────────────────┴───────────────────┘
# SAMPLE 12c FAILED: AssertionError: outcome-measures filter returned no rows
# 
# === SAMPLE 12d: financial-aid.md Python net-price-by-income (lines 587-609) ===
#   full parquet shape: (597920, 15)
#   filtered net_prices shape: (5, 3)
# shape: (5, 3)
# ┌──────────────┬───────────┬────────────────────┐
# │ income_level ┆ net_price ┆ number_of_students │
# │ ---          ┆ ---       ┆ ---                │
# │ i64          ┆ i64       ┆ i64                │
# ╞══════════════╪═══════════╪════════════════════╡
# │ 1            ┆ 1754      ┆ 67                 │
# │ 2            ┆ -273      ┆ 90                 │
# │ 3            ┆ 538       ┆ 109                │
# │ 4            ┆ 10912     ┆ 32                 │
# │ 5            ┆ 48113     ┆ 99                 │
# └──────────────┴───────────┴────────────────────┘
# 
# === PYTHON SAMPLE SUMMARY ===
#   [PASS] 12a: 407 canonical parquet data paths discovered; revision pinned=0ad00ce0e232
#   [PASS] 12b: fetched saipe/districts_saipe: 382,099 rows x 10 cols via huggingface; revision pin=0ad00ce0e232
#   [FAIL] 12c: AssertionError: outcome-measures filter returned no rows
#   [PASS] 12d: full=597,920 rows; MIT 2020 net-price by income=5 rows (income levels present)
# 
# PASS 3/4
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
