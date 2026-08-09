# --- Config ---
# INTENT: Mechanically render one variable-dictionary markdown file per source (14 expected)
#         from the Portal varlist (41_variable_inventory) joined through the endpoint<->file
#         bridge (script 53). Organize each file by dataset family (year-collapsed mirror file
#         family), collapsing disaggregation-route duplicates so each variable appears once per
#         family, with the canonical mirror path and contributing endpoint routes cited.
# REASONING: A mirror-first skill rewrite needs a generated, regenerable variable reference tied
#            to concrete mirror parquet paths — not hand-maintained tables that silently drift.
# ASSUMES: Each endpoint maps to exactly ONE year-collapsed data family (verified in prep:
#          0 endpoints span >1 family; 0 families span >1 source), so the 2994 varlist rows
#          partition cleanly into family sections. Values strings are preserved verbatim
#          (only whitespace-normalized + pipe-escaped) — no code:label invention.
import polars as pl
import re
from pathlib import Path
from datetime import date

BRIDGE = "/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-08_dictionary-generation/53_endpoint_file_bridge.parquet"
GT = "/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_endpoint-ground-truth"
VAR_PATH = f"{GT}/41_variable_inventory.parquet"

OUT_DIR = Path("/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-08_dictionary-generation/generated")
OUT_DIR.mkdir(parents=True, exist_ok=True)

HF_REVISION = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
GEN_DATE = date.today().isoformat()
SELF = "/daaf/scripts/mirror_maintenance/54_generate-variable-dictionaries.py"

EXPECTED_SOURCES = ["ccd", "crdc", "csafety", "eada", "edfacts", "fsa", "ipeds",
                    "meps", "nacubo", "nccs", "nhgis", "pseo", "saipe", "scorecard"]

# --- Load ---
bridge = pl.read_parquet(BRIDGE)
var = pl.read_parquet(VAR_PATH)
print(f"Loaded bridge: {bridge.shape}, var inventory: {var.shape}")

# --- Transform: year-collapse to family_key ---
# INTENT: family_key = canonical mirror path with the year token replaced by {year}.
# REASONING: yearly shards (schools_ccd_enrollment_1986..2022) are one dataset family; the
#            {year} placeholder is the mirror-agnostic path the skill will cite.
# ASSUMES: a year token is a 4-digit 19xx/20xx bounded by '_' (verified: 0 collapse misses).
def collapse(key):
    if key is None:
        return None
    return re.sub(r'_(19|20)\d{2}(?=$|_)', '_{year}', key)

# endpoint-linked data rows only (exclude file_no_endpoint / codebook rows)
bd = bridge.filter(
    (pl.col("kind") == "data") & pl.col("endpoint_id").is_not_null()
).with_columns(
    pl.col("canonical_key").map_elements(collapse, return_dtype=pl.Utf8).alias("family_key")
).with_columns(
    pl.col("family_key").str.split("/").list.first().alias("source")
)

# endpoint -> family map (must be 1:1)
ep_fam = bd.select(["endpoint_id", "family_key", "source", "route"]).unique()
assert ep_fam.select(["endpoint_id"]).n_unique() == ep_fam.select(["endpoint_id", "family_key"]).n_unique(), \
    "endpoint maps to >1 family_key"

# family -> concrete validated canonical keys (for path listing + validation)
fam_keys = bd.group_by("family_key").agg([
    pl.col("canonical_key").n_unique().alias("n_mirror_files"),
    pl.col("in_mirror_parquet").any().alias("any_validated_key"),  # from script 53 validation
])
# VALIDATE: every family cites >=1 canonical key that passed script 53's mirror validation
assert fam_keys.filter(~pl.col("any_validated_key")).height == 0, \
    "A family has no mirror-validated canonical key"
print(f"Families: {fam_keys.height} (all cite >=1 mirror-validated canonical key)")

# family -> contributing endpoint routes
fam_routes = bd.group_by("family_key").agg(
    pl.col("route").unique().sort().alias("routes")
)

# --- Join variables to families in varlist order ---
# INTENT: attach family + source to every varlist row via its endpoint_id (1:1 to family).
var = var.with_row_index("varlist_idx")
vf = var.join(ep_fam.select(["endpoint_id", "family_key", "source"]), on="endpoint_id", how="left")
assert vf.filter(pl.col("family_key").is_null()).height == 0, "varlist row without a family"

# --- Collapse disaggregation duplicates: one row per (family_key, variable) ---
# REASONING: disaggregation routes (e.g. .../enrollment/{year}/race/ vs .../sex/) repeat the
#            same variables; keep the FIRST occurrence in varlist order (deterministic).
# ASSUMES: within (family,variable) label/type/values are consistent (verified: only 3 label
#          and 1 filter micro-conflicts across 2235 groups; min-varlist_idx resolves them).
ROWS_IN = vf.height
vf_sorted = vf.sort("varlist_idx")
rendered = vf_sorted.unique(subset=["family_key", "variable"], keep="first", maintain_order=True)
ROWS_OUT = rendered.height
print(f"DEDUPE: varlist rows in {ROWS_IN} -> unique (family,variable) out {ROWS_OUT}")

# --- Markdown escaping helper ---
def esc(s):
    if s is None:
        return ""
    s = str(s).replace("\r", " ").replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s.replace("|", "\\|")

def clean_type(s):
    return "" if s is None else str(s).strip()

def filter_flag(s):
    # is_filter is the string "1" for filterable vars; "None"/null otherwise.
    return "yes" if (s is not None and str(s).strip() == "1") else "no"

# Precompute per-family metadata dicts
routes_map = {r["family_key"]: r["routes"] for r in fam_routes.to_dicts()}
nfiles_map = {r["family_key"]: r["n_mirror_files"] for r in fam_keys.to_dicts()}

# --- Render one file per source ---
line_counts = {}
rendered_row_tally = 0
for source in EXPECTED_SOURCES:
    sub = rendered.filter(pl.col("source") == source)
    assert sub.height > 0, f"Source {source} has zero rendered rows"
    families = sorted(sub["family_key"].unique().to_list())

    lines = []
    # Header block: HTML comment + visible prose
    lines.append(f"<!-- MECHANICALLY GENERATED by {SELF} on {GEN_DATE}")
    lines.append(f"     from the Portal varlist captured 2026-08-07 at Portal v0.26.1 — the same")
    lines.append(f"     vintage as the pinned mirror (revision {HF_REVISION}).")
    lines.append(f"     Do not hand-edit; regenerate at the next mirror vintage. -->")
    lines.append("")
    lines.append(f"# Variable Dictionary — `{source}`")
    lines.append("")
    lines.append(f"**MECHANICALLY GENERATED** by `{SELF}` on {GEN_DATE} from the Portal varlist "
                 f"captured 2026-08-07 at Portal v0.26.1 — the same vintage as the pinned mirror "
                 f"(revision `{HF_REVISION}`). Do not hand-edit; regenerate at the next mirror vintage.")
    lines.append("")
    lines.append(f"> Caveat: the `urban_csv` fallback mirror is unpinned; these facts are "
                 f"guaranteed for the pinned Hugging Face vintage only.")
    lines.append("")
    lines.append(f"Source `{source}`: {len(families)} dataset famil"
                 f"{'y' if len(families)==1 else 'ies'}, {sub.height} unique variables.")
    lines.append("")

    for fam in families:
        fam_rows = sub.filter(pl.col("family_key") == fam).sort("varlist_idx")
        rendered_row_tally += fam_rows.height
        routes = routes_map.get(fam, [])
        nfiles = nfiles_map.get(fam, 0)
        # {year} placeholder path already embedded in fam if yearly
        lines.append(f"## `{fam}`")
        lines.append("")
        lines.append(f"- **Canonical mirror path:** `{fam}.parquet` "
                     f"({nfiles} mirror file{'s' if nfiles != 1 else ''})")
        route_cites = ", ".join(f"`{esc(r)}`" for r in routes)
        lines.append(f"- **Contributing endpoint route(s):** {route_cites}")
        lines.append("")
        lines.append("| variable | label | type | filter? | coded values |")
        lines.append("|---|---|---|---|---|")
        for r in fam_rows.to_dicts():
            lines.append(
                f"| `{esc(r['variable'])}` | {esc(r['label'])} | {clean_type(r['data_type'])} "
                f"| {filter_flag(r['is_filter'])} | {esc(r['values'])} |"
            )
        lines.append("")

    content = "\n".join(lines).rstrip() + "\n"
    out_path = OUT_DIR / f"variable-dictionary-{source}.md"
    out_path.write_text(content)
    line_counts[source] = content.count("\n")

# --- Validate ---
# 1) exactly 14 files, all non-empty
written = sorted(OUT_DIR.glob("variable-dictionary-*.md"))
assert len(written) == 14, f"Expected 14 files, got {len(written)}"
for p in written:
    assert p.stat().st_size > 0, f"Empty file: {p}"
# 2) every rendered (family,variable) row landed in exactly one file section
assert rendered_row_tally == ROWS_OUT, \
    f"Rendered {rendered_row_tally} rows != {ROWS_OUT} unique (family,variable)"
# 3) every one of the 2994 varlist rows is represented in exactly one family section:
#    each varlist row's (family_key, variable) is present in the rendered set.
rendered_pairs = set(zip(rendered["family_key"].to_list(), rendered["variable"].to_list()))
vf_pairs = list(zip(vf["family_key"].to_list(), vf["variable"].to_list()))
missing = [p for p in vf_pairs if p not in rendered_pairs]
assert len(missing) == 0, f"{len(missing)} varlist rows not represented in any family section"
print(f"VALIDATION: all {ROWS_IN} varlist rows represented in exactly one family section.")
print(f"VALIDATION: 14 files written, all non-empty.")

# --- Summary ---
print("\n--- PER-FILE SUMMARY (source: unique_vars, families, md_lines) ---")
for source in EXPECTED_SOURCES:
    nfam = rendered.filter(pl.col("source") == source)["family_key"].n_unique()
    nvar = rendered.filter(pl.col("source") == source).height
    print(f"  {source:10s}: {nvar:4d} vars | {nfam:2d} families | {line_counts[source]:4d} lines")
print(f"\nDedupe accounting: {ROWS_IN} varlist rows in -> {ROWS_OUT} unique variable x family out")
print(f"Output dir: {OUT_DIR}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-08 22:22:05
# Command: python3 /daaf/scripts/mirror_maintenance/54_generate-variable-dictionaries.py
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# Loaded bridge: (945, 13), var inventory: (2994, 13)
# Families: 85 (all cite >=1 mirror-validated canonical key)
# DEDUPE: varlist rows in 2994 -> unique (family,variable) out 2235
# VALIDATION: all 2994 varlist rows represented in exactly one family section.
# VALIDATION: 14 files written, all non-empty.
# 
# --- PER-FILE SUMMARY (source: unique_vars, families, md_lines) ---
#   ccd       :  300 vars |  5 families |  352 lines
#   crdc      :  397 vars | 24 families |  601 lines
#   csafety   :   13 vars |  1 families |   33 lines
#   eada      :  165 vars |  1 families |  185 lines
#   edfacts   :   82 vars |  4 families |  126 lines
#   fsa       :   63 vars |  5 families |  115 lines
#   ipeds     :  753 vars | 32 families | 1021 lines
#   meps      :   11 vars |  1 families |   31 lines
#   nacubo    :    7 vars |  1 families |   27 lines
#   nccs      :  161 vars |  1 families |  181 lines
#   nhgis     :   87 vars |  2 families |  115 lines
#   pseo      :   18 vars |  1 families |   38 lines
#   saipe     :   10 vars |  1 families |   30 lines
#   scorecard :  168 vars |  6 families |  228 lines
# 
# Dedupe accounting: 2994 varlist rows in -> 2235 unique variable x family out
# Output dir: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-08_dictionary-generation/generated
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
