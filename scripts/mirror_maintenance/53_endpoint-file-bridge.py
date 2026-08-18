# --- Config ---
# INTENT: Build the endpoint<->mirror-file bridge table: map every Urban api-downloads
#         endpoint_id to its deduped canonical mirror keys (data + codebook), join to the
#         endpoint catalog (route + years), and validate every bridged DATA key against the
#         PINNED Hugging Face mirror tree. Report coverage in BOTH directions.
# REASONING: This bridge is the mechanical join layer a mirror-first skill rewrite needs — it
#            lets the dictionary generator (script 54) cite the exact mirror parquet path(s)
#            backing each endpoint route, and it surfaces endpoint<->object gaps explicitly.
# ASSUMES: The archived July api-downloads manifest is the api-downloads response (verified:
#          carries the exact raw columns id/endpoint_id/sort_order/file_dir/file_name/
#          file_label/file_size/hide). It is a 2026-07-21 snapshot; the pinned mirror (v2,
#          Portal 0.26.1) was built 2026-08-06, so a small snapshot-drift gap is expected and
#          is precisely what the bidirectional coverage report captures.
import polars as pl
import json
import signal
import urllib.request
from pathlib import Path

# --- Provenance: archived api-downloads manifest (NO live pull needed) ---
# Probes that located the archived copy (quoted in the execution report):
#   find /daaf/research/2026-07-21_FrameworkDev_EducationPortalSkills/ -iname '*manifest*'
#     -> .../catalog/2026-07-21_urban-download-manifest.parquet
# Schema check confirmed the raw api-downloads columns are present (id, endpoint_id,
# sort_order, file_dir, file_name, file_label, file_size, hide) plus precomputed enrichment.
MANIFEST_PATH = "/daaf/research/2026-07-21_FrameworkDev_EducationPortalSkills/2026-07-21_education-portal-mirror-staging/catalog/2026-07-21_urban-download-manifest.parquet"
MANIFEST_PROVENANCE = "archived (2026-07-21 api-downloads snapshot); no live pull performed"

GT = "/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_endpoint-ground-truth"
CATALOG_PATH = f"{GT}/41_endpoint_catalog.parquet"

OUT_DIR = Path("/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-08_dictionary-generation")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = OUT_DIR / "53_endpoint_file_bridge.parquet"

HF_REVISION = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
HF_TREE_URL = f"https://huggingface.co/api/datasets/brhkim/education_data_portal_mirror_2026q3/tree/{HF_REVISION}?recursive=true"

# --- Load ---
man = pl.read_parquet(MANIFEST_PATH)
cat = pl.read_parquet(CATALOG_PATH)
print(f"Loaded manifest: {man.shape[0]} rows x {man.shape[1]} cols  [{MANIFEST_PROVENANCE}]")
print(f"Loaded catalog:  {cat.shape[0]} rows x {cat.shape[1]} cols")

# --- Transform: derive canonical keys per mirrors.yaml algorithm ---
# INTENT: canonical_key = "{file_dir}/{file_name minus ONE terminal .csv (data) or .xls (codebook)}"
# REASONING: mirrors.yaml unified path model: extensionless "{source}/{filename}" is the
#            mirror-agnostic key; the HF mirror appends .parquet (data) / .xls (codebook).
# ASSUMES: file_name always ends in .csv (data) or .xls (codebook); any other suffix is flagged.
man = man.with_columns(
    pl.when(pl.col("file_name").str.ends_with(".csv"))
      .then(pl.col("file_name").str.slice(0, pl.col("file_name").str.len_chars() - 4))
      .when(pl.col("file_name").str.ends_with(".xls"))
      .then(pl.col("file_name").str.slice(0, pl.col("file_name").str.len_chars() - 4))
      .otherwise(pl.col("file_name"))
      .alias("_stem"),
    pl.when(pl.col("file_name").str.ends_with(".csv")).then(pl.lit("data"))
      .when(pl.col("file_name").str.ends_with(".xls")).then(pl.lit("codebook"))
      .otherwise(pl.lit("OTHER")).alias("kind"),
)
man = man.with_columns((pl.col("file_dir") + "/" + pl.col("_stem")).alias("canonical_key"))

# VALIDATE derivation against the manifest's own precomputed columns (independent cross-check).
assert man.filter(pl.col("canonical_key") != pl.col("canonical_object_key")).height == 0, \
    "Derived canonical_key disagrees with precomputed canonical_object_key"
assert man.filter(pl.col("kind") != pl.col("object_kind")).height == 0, \
    "Derived kind disagrees with precomputed object_kind"
assert man.filter(pl.col("kind") == "OTHER").height == 0, "Unexpected file extension (not .csv/.xls)"
print("Canonical-key derivation matches precomputed columns exactly (0 mismatches).")

# --- Unique object inventory (dedupe exact file_dir/file_name identities) ---
# INTENT: the mirror OBJECT count is per-object, not per-presentation-row.
objects = man.unique(subset=["file_dir", "file_name"])
n_obj_data = objects.filter(pl.col("kind") == "data").height
n_obj_cb = objects.filter(pl.col("kind") == "codebook").height
print(f"Presentation rows {man.height} -> unique objects {objects.height} "
      f"({n_obj_data} data + {n_obj_cb} codebook)")

# --- Bridge grain: distinct (endpoint_id, canonical_key, kind) pairs ---
# REASONING: a mirror object can be listed under >1 endpoint (many-to-many presentation);
#            the bridge preserves every endpoint<->object linkage, so grain is the pair,
#            NOT the object. Collapse only exact duplicate presentation rows of the same pair.
bridge = man.select(["endpoint_id", "canonical_key", "kind", "file_dir", "file_name",
                     "year_shard"]).unique(subset=["endpoint_id", "canonical_key"])
# How many endpoints does each canonical_key map to? (many-to-many diagnostic)
key_fanout = bridge.group_by("canonical_key").agg(pl.col("endpoint_id").n_unique().alias("n_endpoints"))
multi = key_fanout.filter(pl.col("n_endpoints") > 1)
print(f"Bridge (endpoint_id x canonical_key) pairs: {bridge.height}")
print(f"Canonical keys mapped to >1 endpoint: {multi.height}")

# --- Join to endpoint catalog (route + years_available) ---
# INTENT: attach the live-verified route template and year coverage to each bridged pair.
# ASSUMES: endpoint_id is the shared key across manifest, catalog, and variable inventory
#          (verified: all three use ids 1..135, 129 unique).
cat_slim = cat.select([
    "endpoint_id",
    pl.col("endpoint_url").alias("route"),
    "years_available",
    "class_name",
    "section",
])
bridged = bridge.join(cat_slim, on="endpoint_id", how="left")
assert bridged.filter(pl.col("route").is_null()).height == 0, \
    "Some bridged endpoint_id did not join to the catalog"

# --- Live validation against PINNED HF mirror tree (read-only GET, 25s SIGALRM) ---
def _timeout(signum, frame):
    raise TimeoutError("HF tree GET exceeded 25s wall clock")

tree_entries = None
tree_err = None
signal.signal(signal.SIGALRM, _timeout)
signal.alarm(25)
try:
    req = urllib.request.Request(HF_TREE_URL, headers={"User-Agent": "daaf-mirror-maintenance/53"})
    with urllib.request.urlopen(req) as resp:
        raw = resp.read().decode("utf-8")
    tree_entries = json.loads(raw)
finally:
    signal.alarm(0)

print(f"\nHF tree GET: {HF_TREE_URL}")
print(f"HF tree returned {len(tree_entries)} entries at revision {HF_REVISION[:12]}")
if len(tree_entries) >= 1000:
    print("WARNING: >=1000 entries — HF tree API may have paginated; results may be truncated.")

# Partition tree paths into parquet data keys, xls codebook keys, and other objects.
mirror_parquet_keys = set()
mirror_xls_keys = set()
mirror_other = []
for e in tree_entries:
    p = e.get("path", "")
    if e.get("type") != "file":
        continue
    if p.endswith(".parquet"):
        mirror_parquet_keys.add(p[:-len(".parquet")])
    elif p.endswith(".xls"):
        mirror_xls_keys.add(p[:-len(".xls")])
    else:
        mirror_other.append(p)
print(f"Mirror tree: {len(mirror_parquet_keys)} parquet + {len(mirror_xls_keys)} xls "
      f"+ {len(mirror_other)} other ({mirror_other})")

# --- CP: bidirectional coverage ---
bridged_data_keys = set(bridged.filter(pl.col("kind") == "data")["canonical_key"].to_list())
bridged_cb_keys = set(bridged.filter(pl.col("kind") == "codebook")["canonical_key"].to_list())

# (a) every bridged DATA key must resolve to an existing mirror .parquet
data_keys_missing_in_mirror = sorted(bridged_data_keys - mirror_parquet_keys)
# (b) mirror data parquets with NO endpoint bridge
mirror_data_no_endpoint = sorted(mirror_parquet_keys - bridged_data_keys)
# (c) endpoints (from full 129 catalog) with NO bridged DATA file
endpoints_with_data = set(bridged.filter(pl.col("kind") == "data")["endpoint_id"].to_list())
all_endpoints = set(cat["endpoint_id"].to_list())
endpoints_no_data = sorted(all_endpoints - endpoints_with_data)
endpoints_no_data_routes = (cat.filter(pl.col("endpoint_id").is_in(endpoints_no_data))
                            .select(["endpoint_id", "endpoint_url"]).to_dicts())

print("\n--- CP: BIDIRECTIONAL COVERAGE ---")
print(f"Bridged DATA keys: {len(bridged_data_keys)} | Bridged CODEBOOK keys: {len(bridged_cb_keys)}")
print(f"(a) bridged DATA keys NOT resolving in mirror parquet tree: {len(data_keys_missing_in_mirror)}")
print(f"    {data_keys_missing_in_mirror}")
print(f"(b) mirror DATA parquets with NO endpoint bridge: {len(mirror_data_no_endpoint)}")
print(f"    {mirror_data_no_endpoint}")
print(f"(c) catalog endpoints with NO bridged DATA file: {len(endpoints_no_data)}")
print(f"    {endpoints_no_data_routes}")

# HARD assertion: the task requires every bridged data key to resolve in the pinned mirror.
assert len(data_keys_missing_in_mirror) == 0, \
    f"{len(data_keys_missing_in_mirror)} bridged data keys absent from pinned mirror: {data_keys_missing_in_mirror}"

# Expected-object sanity (per task): 406 parquet + 91 xls + 3 aux = 500.
n_aux = len(mirror_other)
total_objects = len(mirror_parquet_keys) + len(mirror_xls_keys) + n_aux
print(f"\nMirror object accounting: {len(mirror_parquet_keys)} parquet + {len(mirror_xls_keys)} "
      f"xls + {n_aux} aux = {total_objects} (task expected 500)")

# --- Assemble output: one row per (endpoint_id, canonical_key) + flagged unbridged rows ---
# Bridged rows (endpoint present, file present)
out_bridged = bridged.with_columns([
    pl.lit("bridged").alias("bridge_status"),
    pl.col("canonical_key").is_in(mirror_parquet_keys).alias("in_mirror_parquet"),
    pl.col("canonical_key").is_in(mirror_xls_keys).alias("in_mirror_xls"),
])

# Flagged: mirror data parquet with no endpoint (kind=data, endpoint_id null)
if mirror_data_no_endpoint:
    out_unbridged_files = pl.DataFrame({
        "endpoint_id": [None] * len(mirror_data_no_endpoint),
        "canonical_key": mirror_data_no_endpoint,
        "kind": ["data"] * len(mirror_data_no_endpoint),
        "file_dir": [k.split("/")[0] for k in mirror_data_no_endpoint],
        "file_name": [None] * len(mirror_data_no_endpoint),
        "year_shard": [None] * len(mirror_data_no_endpoint),
        "route": [None] * len(mirror_data_no_endpoint),
        "years_available": [None] * len(mirror_data_no_endpoint),
        "class_name": [None] * len(mirror_data_no_endpoint),
        "section": [None] * len(mirror_data_no_endpoint),
        "bridge_status": ["file_no_endpoint"] * len(mirror_data_no_endpoint),
        "in_mirror_parquet": [True] * len(mirror_data_no_endpoint),
        "in_mirror_xls": [False] * len(mirror_data_no_endpoint),
    }, schema_overrides={"endpoint_id": pl.Int64, "file_name": pl.Utf8, "year_shard": pl.Int64,
                         "route": pl.Utf8, "years_available": pl.Utf8, "class_name": pl.Utf8,
                         "section": pl.Utf8})
else:
    out_unbridged_files = out_bridged.head(0)

# Flagged: endpoint with no bridged data file (endpoint present, file null)
if endpoints_no_data:
    ep_rows = cat.filter(pl.col("endpoint_id").is_in(endpoints_no_data)).select([
        "endpoint_id",
        pl.lit(None, dtype=pl.Utf8).alias("canonical_key"),
        pl.lit(None, dtype=pl.Utf8).alias("kind"),
        pl.lit(None, dtype=pl.Utf8).alias("file_dir"),
        pl.lit(None, dtype=pl.Utf8).alias("file_name"),
        pl.lit(None, dtype=pl.Int64).alias("year_shard"),
        pl.col("endpoint_url").alias("route"),
        "years_available",
        "class_name",
        "section",
        pl.lit("endpoint_no_data_file").alias("bridge_status"),
        pl.lit(False).alias("in_mirror_parquet"),
        pl.lit(False).alias("in_mirror_xls"),
    ])
else:
    ep_rows = out_bridged.head(0)

out = pl.concat([out_bridged.select(sorted(out_bridged.columns)),
                 out_unbridged_files.select(sorted(out_unbridged_files.columns)),
                 ep_rows.select(sorted(ep_rows.columns))], how="vertical_relaxed")

# --- Validate output ---
assert out.height == out_bridged.height + out_unbridged_files.height + ep_rows.height
print(f"\nOutput rows: {out.height} "
      f"(bridged {out_bridged.height} + file_no_endpoint {out_unbridged_files.height} "
      f"+ endpoint_no_data {ep_rows.height})")
print("bridge_status counts:", out["bridge_status"].value_counts().to_dicts())

# --- Save ---
out.write_parquet(OUT_PATH)
print(f"Saved bridge to: {OUT_PATH}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-08 22:18:44
# Command: python3 /daaf/scripts/mirror_maintenance/53_endpoint-file-bridge.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# Loaded manifest: 958 rows x 23 cols  [archived (2026-07-21 api-downloads snapshot); no live pull performed]
# Loaded catalog:  129 rows x 18 cols
# Canonical-key derivation matches precomputed columns exactly (0 mismatches).
# Presentation rows 958 -> unique objects 495 (404 data + 91 codebook)
# Bridge (endpoint_id x canonical_key) pairs: 942
# Canonical keys mapped to >1 endpoint: 172
# 
# HF tree GET: https://huggingface.co/api/datasets/brhkim/education_data_portal_mirror_2026q3/tree/0ad00ce0e232c96b0642459e4e7326607a8d26aa?recursive=true
# HF tree returned 514 entries at revision 0ad00ce0e232
# Mirror tree: 407 parquet + 91 xls + 2 other (['.gitattributes', 'README.md'])
# 
# --- CP: BIDIRECTIONAL COVERAGE ---
# Bridged DATA keys: 404 | Bridged CODEBOOK keys: 91
# (a) bridged DATA keys NOT resolving in mirror parquet tree: 0
#     []
# (b) mirror DATA parquets with NO endpoint bridge: 3
#     ['build_manifest', 'ipeds/colleges_ipeds_completions-2digcip_2023', 'ipeds/colleges_ipeds_completions-6digcip_2023']
# (c) catalog endpoints with NO bridged DATA file: 0
#     []
# 
# Mirror object accounting: 407 parquet + 91 xls + 2 aux = 500 (task expected 500)
# 
# Output rows: 945 (bridged 942 + file_no_endpoint 3 + endpoint_no_data 0)
# bridge_status counts: [{'bridge_status': 'bridged', 'count': 942}, {'bridge_status': 'file_no_endpoint', 'count': 3}]
# Saved bridge to: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-08_dictionary-generation/53_endpoint_file_bridge.parquet
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
