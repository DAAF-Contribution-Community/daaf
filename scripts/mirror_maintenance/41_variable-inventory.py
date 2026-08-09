# --- Config ---
# INTENT: Establish how to enumerate each Urban Portal endpoint's variables
#   programmatically, and build a ground-truth parquet of endpoint -> variable
#   names/labels/filter-flags/coded-values for all live catalog endpoints.
# REASONING: The live API exposes TWO metadata surfaces discovered empirically:
#   (a) api-endpoints/           -> 129 endpoint rows, keyed by endpoint_id, with
#                                   endpoint_url, var_list_id, years_available,
#                                   section, class_name, sub_topic.
#   (b) api-endpoint-varlist/    -> 2994 variable rows, keyed by endpoint_id, with
#                                   variable, label, is_filter, format, data_type,
#                                   string_length, description, and `values`
#                                   (the Portal's authoritative coded-value string).
#   Surface (b) is the authoritative programmatic variable inventory AND coded-value
#   documentation — no need to fall back to first-row field names. This single
#   join feeds scripts 42 (varlist audit), 43 (code tables), and 44 (filters).
# ASSUMES: The two cached JSON pulls (scratch/endpoint_audit_vars/*.json) are
#   complete snapshots fetched 2026-08-07 (endpoints limit=500 -> count 129;
#   varlist limit=5000 -> count 2994). endpoint_id is the shared join key and is
#   string-typed in the varlist surface, integer-typed in the endpoints surface.
import json
import polars as pl
from pathlib import Path

BASE_DIR = Path("/daaf")
PROJECT_DIR = BASE_DIR / "research/2026-08-06_FrameworkDev_MirrorV2Update"
SCRATCH = PROJECT_DIR / "scripts" / "scratch"  # not used; real scratch below
CACHE = BASE_DIR / "scripts/mirror_maintenance/scratch/endpoint_audit_vars"
OUT_DIR = PROJECT_DIR / "2026-08-07_endpoint-ground-truth"
OUT_PATH = OUT_DIR / "41_variable_inventory.parquet"
CATALOG_PATH = OUT_DIR / "41_endpoint_catalog.parquet"

# --- Load ---
# INTENT: Parse the two cached metadata JSON snapshots.
ep_raw = json.loads((CACHE / "endpoints_catalog.json").read_text())
vl_raw = json.loads((CACHE / "varlist_full.json").read_text())
print(f"api-endpoints count field: {ep_raw['count']}, rows: {len(ep_raw['results'])}")
print(f"api-endpoint-varlist count field: {vl_raw['count']}, rows: {len(vl_raw['results'])}")

# ASSUMES: pagination `next` is null for both (single-page complete pulls).
assert ep_raw["next"] is None, "endpoints catalog paginated — incomplete pull"
assert vl_raw["next"] is None, "varlist paginated — incomplete pull"

ep = pl.DataFrame(ep_raw["results"])
vl = pl.DataFrame(vl_raw["results"])
print(f"endpoints DF: {ep.shape}, cols: {ep.columns}")
print(f"varlist DF: {vl.shape}, cols: {vl.columns}")

# --- Transform ---
# INTENT: Normalize endpoint_id to a common integer type for the join.
# REASONING: varlist endpoint_id arrives as string ("1"); endpoints as int (1).
ep = ep.with_columns(pl.col("endpoint_id").cast(pl.Int64))
vl = vl.with_columns(pl.col("endpoint_id").cast(pl.Int64))

# INTENT: Keep the catalog metadata columns needed for downstream lane joins.
ep_slim = ep.select([
    "endpoint_id", "endpoint_url", "section", "class_name",
    "sub_topic", "years_available", "var_list_id",
])

# INTENT: Build the long inventory: one row per (endpoint, variable).
# REASONING: Left-join varlist onto catalog so endpoints with zero documented
#   variables surface as nulls (flags a metadata gap, not silent drop).
inventory = ep_slim.join(vl, on="endpoint_id", how="left").select([
    "endpoint_id", "endpoint_url", "class_name", "section", "sub_topic",
    "years_available", "variable", "label", "is_filter",
    "format", "data_type", "string_length", "values",
])

# --- Validate ---
n_endpoints = inventory.select("endpoint_id").n_unique()
n_with_vars = inventory.filter(pl.col("variable").is_not_null()).select("endpoint_id").n_unique()
n_var_rows = inventory.filter(pl.col("variable").is_not_null()).height
print(f"Distinct endpoints in catalog: {n_endpoints}")
print(f"Endpoints WITH >=1 variable in varlist surface: {n_with_vars}")
print(f"Total variable rows: {n_var_rows}")

# INTENT: Report endpoints that have NO varlist coverage (metadata surface gap).
no_vars = (
    ep_slim.join(vl.select("endpoint_id").unique(), on="endpoint_id", how="anti")
    .select("endpoint_id", "endpoint_url")
)
print(f"Endpoints with NO varlist rows: {no_vars.height}")
if no_vars.height:
    for row in no_vars.iter_rows(named=True):
        print(f"  NO-VARLIST: id={row['endpoint_id']} {row['endpoint_url']}")

# INTENT: Confirm coded-value string is populated for coded variables.
n_with_values = inventory.filter(
    pl.col("values").is_not_null() & (pl.col("values") != "")
).height
print(f"Variable rows carrying a `values` coded-value string: {n_with_values}")

# is_filter distribution (feeds script 44)
print("is_filter value distribution:")
print(inventory.filter(pl.col("variable").is_not_null())
      .group_by("is_filter").len().sort("len", descending=True))

assert n_endpoints == 129, f"Expected 129 catalog endpoints, got {n_endpoints}"
assert n_var_rows > 2500, "Variable inventory suspiciously small"

# --- Save ---
inventory.write_parquet(OUT_PATH)
ep.write_parquet(CATALOG_PATH)
print(f"Saved inventory: {OUT_PATH} ({inventory.shape})")
print(f"Saved catalog: {CATALOG_PATH} ({ep.shape})")

# --- Metadata surface finding (quoted evidence) ---
print("\n=== METADATA SURFACE FINDING ===")
print("Surface: https://educationdata.urban.org/api/v1/api-endpoint-varlist/")
print("Filterable by endpoint_id (verified: ?endpoint_id=1 -> 96 rows).")
print("Sample row (endpoint 1, IPEDS directory, variable 'unitid'):")
sample = vl.filter((pl.col("endpoint_id") == 1) & (pl.col("variable") == "unitid"))
print(sample.to_dicts()[0] if sample.height else "MISSING")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 15:12:17
# Command: python3 /daaf/scripts/mirror_maintenance/41_variable-inventory.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# api-endpoints count field: 129, rows: 129
# api-endpoint-varlist count field: 2994, rows: 2994
# endpoints DF: (129, 18), cols: ['endpoint_id', 'page_id', 'order', 'example_endpoint_url', 'endpoint_url', 'section', 'class_name', 'topic', 'sub_topic', 'datasource_id', 'years_available', 'description', 'var_list_id', 'stata_code', 'r_code', 'python_code', 'js_code', 'hide']
# varlist DF: (2994, 10), cols: ['endpoint_id', 'variable', 'label', 'is_filter', 'format', 'data_type', 'string_length', 'description', 'total_exist', 'values']
# Distinct endpoints in catalog: 129
# Endpoints WITH >=1 variable in varlist surface: 129
# Total variable rows: 2994
# Endpoints with NO varlist rows: 0
# Variable rows carrying a `values` coded-value string: 2994
# is_filter value distribution:
# shape: (2, 2)
# ┌───────────┬──────┐
# │ is_filter ┆ len  │
# │ ---       ┆ ---  │
# │ str       ┆ u32  │
# ╞═══════════╪══════╡
# │ None      ┆ 1635 │
# │ 1         ┆ 1359 │
# └───────────┴──────┘
# Saved inventory: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_endpoint-ground-truth/41_variable_inventory.parquet ((2994, 13))
# Saved catalog: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_endpoint-ground-truth/41_endpoint_catalog.parquet ((129, 18))
# 
# === METADATA SURFACE FINDING ===
# Surface: https://educationdata.urban.org/api/v1/api-endpoint-varlist/
# Filterable by endpoint_id (verified: ?endpoint_id=1 -> 96 rows).
# Sample row (endpoint 1, IPEDS directory, variable 'unitid'):
# {'endpoint_id': 1, 'variable': 'unitid', 'label': 'Unit ID number', 'is_filter': '1', 'format': 'numeric', 'data_type': 'integer', 'string_length': '8', 'description': 'Unique identification number of the institution in the Integrated Postsecondary Education Data System.', 'total_exist': 'None', 'values': '"-1" : "Missing/not reported","-2" : "Not applicable","-3" : "Suppressed data"'}
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
