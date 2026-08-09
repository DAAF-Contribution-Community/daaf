# --- Config ---
# INTENT: Parse the per-endpoint variable tables documented in the three
#   explorer reference files and compare each documented endpoint's variable
#   list against the live Portal varlist (from script 41). Flag
#   DOCUMENTED-NOT-PRESENT and PRESENT-NOT-DOCUMENTED per matched endpoint.
# REASONING: The live api-endpoint-varlist surface (script 41) is authoritative
#   for which variables an endpoint actually exposes. Comparing our doc tables
#   against it isolates variable-level drift, independent of the route-name/year
#   drift the concurrent lane (scripts 37-40) covers.
# ASSUMES: Doc format is stable: each endpoint is introduced by a line
#   `**Endpoint**: `/path/{year}/`` and its variables are backtick-wrapped tokens
#   in the first column of the following `| Variable | Description |` table, up to
#   the next `**Endpoint**:` or `###`/`##` heading. Live endpoint_url carries a
#   `/api/v1` prefix that documented paths omit.
import re
import json
import polars as pl
from pathlib import Path

BASE_DIR = Path("/daaf")
PROJECT_DIR = BASE_DIR / "research/2026-08-06_FrameworkDev_MirrorV2Update"
REF_DIR = BASE_DIR / ".claude/skills/education-data-explorer/references"
OUT_DIR = PROJECT_DIR / "2026-08-07_endpoint-ground-truth"
INV_PATH = OUT_DIR / "41_variable_inventory.parquet"
OUT_PATH = OUT_DIR / "42_varlist_audit.parquet"

DOC_FILES = {
    "colleges": REF_DIR / "colleges-endpoints.md",
    "districts": REF_DIR / "districts-endpoints.md",
    "schools": REF_DIR / "schools-endpoints.md",
}

# --- Load ---
inv = pl.read_parquet(INV_PATH)
print(f"Inventory: {inv.shape}")

# INTENT: Build live endpoint_url -> set(variables) and a normalized-path lookup.
# REASONING: Normalize by stripping /api/v1, lowercasing, trimming slashes, and
#   collapsing every {placeholder} to {} so year/grade/etc. path segments match
#   regardless of the specific placeholder name used in docs vs catalog.
def norm_path(p):
    p = p.strip().lower()
    p = re.sub(r"^/?api/v1", "", p)
    p = re.sub(r"\{[^}]*\}", "{}", p)
    p = p.strip("/")
    return p

live_vars = {}   # norm_path -> set(variable)
live_url_by_norm = {}
for row in inv.filter(pl.col("variable").is_not_null()).iter_rows(named=True):
    n = norm_path(row["endpoint_url"])
    live_vars.setdefault(n, set()).add(row["variable"].lower())
    live_url_by_norm[n] = row["endpoint_url"]
print(f"Live normalized endpoints with variables: {len(live_vars)}")

# --- Transform: parse documented endpoint variable tables ---
# INTENT: Split each doc file into endpoint blocks and extract variable tokens.
EP_RE = re.compile(r"\*\*Endpoint\*\*:\s*`([^`]+)`")
# variable token = first backticked token on a markdown table row beginning with `|`
VAR_ROW_RE = re.compile(r"^\|\s*`([a-zA-Z0-9_]+)`\s*\|")

audit_rows = []
parse_counts = {}
for level, path in DOC_FILES.items():
    text = path.read_text()
    lines = text.splitlines()
    # Find endpoint anchor line indices
    anchors = []  # (line_idx, documented_path)
    for i, ln in enumerate(lines):
        m = EP_RE.search(ln)
        if m:
            anchors.append((i, m.group(1)))
    parse_counts[level] = len(anchors)
    # For each anchor, collect variable tokens until the next anchor line
    for a_idx, (start, doc_path) in enumerate(anchors):
        end = anchors[a_idx + 1][0] if a_idx + 1 < len(anchors) else len(lines)
        block = lines[start:end]
        doc_vars = set()
        for bl in block:
            vm = VAR_ROW_RE.match(bl.strip())
            if vm:
                doc_vars.add(vm.group(1).lower())
        n = norm_path(doc_path)
        matched = n in live_vars
        if matched:
            lv = live_vars[n]
            documented_not_present = sorted(doc_vars - lv)
            present_not_documented = sorted(lv - doc_vars)
        else:
            documented_not_present = []
            present_not_documented = []
        audit_rows.append({
            "level": level,
            "doc_path": doc_path,
            "norm_path": n,
            "route_matched_live": matched,
            "n_doc_vars": len(doc_vars),
            "n_live_vars": len(live_vars.get(n, set())),
            "n_documented_not_present": len(documented_not_present),
            "n_present_not_documented": len(present_not_documented),
            "documented_not_present": ", ".join(documented_not_present),
            "present_not_documented": ", ".join(present_not_documented),
        })

audit = pl.DataFrame(audit_rows)

# --- Validate ---
print("\nDocumented endpoint-block extraction counts (per file):")
for lvl, c in parse_counts.items():
    print(f"  {lvl}: {c} endpoint blocks parsed")

n_matched = audit.filter(pl.col("route_matched_live")).height
n_unmatched = audit.filter(~pl.col("route_matched_live")).height
print(f"\nDocumented endpoint blocks: {audit.height}")
print(f"  Route-matched live (variable comparison performed): {n_matched}")
print(f"  Route NOT matched live (DEAD/renamed — lane 37-40): {n_unmatched}")

# INTENT: Blocks with zero documented variables likely indicate a table-format
#   the parser missed — surface them so the extraction isn't silently thin.
zero_var_blocks = audit.filter(pl.col("n_doc_vars") == 0)
print(f"Blocks with 0 extracted doc vars: {zero_var_blocks.height}")
for r in zero_var_blocks.iter_rows(named=True):
    print(f"  ZERO-VARS: [{r['level']}] {r['doc_path']}")

assert audit.height > 100, "Too few endpoint blocks parsed — format assumption broke"

# --- Save ---
audit.write_parquet(OUT_PATH)
print(f"\nSaved: {OUT_PATH} ({audit.shape})")

# --- Findings: matched endpoints with variable discrepancies ---
print("\n=== MATCHED ENDPOINTS WITH VARIABLE DISCREPANCIES ===")
disc = audit.filter(
    pl.col("route_matched_live")
    & ((pl.col("n_documented_not_present") > 0) | (pl.col("n_present_not_documented") > 0))
).sort("n_documented_not_present", descending=True)
print(f"Matched endpoints with >=1 discrepancy: {disc.height} / {n_matched}")
for r in disc.iter_rows(named=True):
    print(f"\n[{r['level']}] {r['doc_path']}")
    print(f"   doc_vars={r['n_doc_vars']} live_vars={r['n_live_vars']}")
    if r["documented_not_present"]:
        print(f"   DOCUMENTED-NOT-PRESENT ({r['n_documented_not_present']}): {r['documented_not_present']}")
    if r["present_not_documented"]:
        print(f"   PRESENT-NOT-DOCUMENTED ({r['n_present_not_documented']}): {r['present_not_documented']}")

# INTENT: Summary tally of clean matched endpoints (doc vars all present, no
#   material omissions) for the report.
clean = audit.filter(
    pl.col("route_matched_live")
    & (pl.col("n_documented_not_present") == 0)
)
print(f"\nMatched endpoints with NO documented-not-present var (doc vars all live): {clean.height}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 15:13:10
# Command: python3 /daaf/scripts/mirror_maintenance/42_varlist-audit.py
# Duration: 1s
# Exit code: 1
#
# --- STDOUT ---
# Inventory: (2994, 13)
# Live normalized endpoints with variables: 129
# 
# Documented endpoint-block extraction counts (per file):
#   colleges: 49 endpoint blocks parsed
#   districts: 12 endpoint blocks parsed
#   schools: 22 endpoint blocks parsed
# 
# Documented endpoint blocks: 83
#   Route-matched live (variable comparison performed): 51
#   Route NOT matched live (DEAD/renamed — lane 37-40): 32
# Blocks with 0 extracted doc vars: 26
#   ZERO-VARS: [colleges] /college-university/ipeds/student-charges-academic-year/{year}/{level}/
#   ZERO-VARS: [colleges] /college-university/ipeds/student-charges-program-year/{year}/
#   ZERO-VARS: [colleges] /college-university/ipeds/student-charges-program-year/{year}/program/
#   ZERO-VARS: [colleges] /college-university/ipeds/fall-enrollment/{year}/{level}/race/
#   ZERO-VARS: [colleges] /college-university/ipeds/fall-enrollment/{year}/{level}/sex/
#   ZERO-VARS: [colleges] /college-university/ipeds/fall-enrollment/{year}/{level}/race/sex/
#   ZERO-VARS: [colleges] /college-university/ipeds/fall-enrollment-age/{year}/
#   ZERO-VARS: [colleges] /college-university/ipeds/sfa-by-income/{year}/
#   ZERO-VARS: [colleges] /college-university/ipeds/sfa-by-living-arrangement/{year}/
#   ZERO-VARS: [colleges] /college-university/ipeds/sfa-by-tuition-status/{year}/
#   ZERO-VARS: [colleges] /college-university/ipeds/graduation-rates/{year}/race/
#   ZERO-VARS: [colleges] /college-university/ipeds/graduation-rates/{year}/sex/
#   ZERO-VARS: [colleges] /college-university/ipeds/grad-rates-200pct/{year}/
#   ZERO-VARS: [colleges] /college-university/ipeds/completions-cip/{year}/race/
#   ZERO-VARS: [colleges] /college-university/ipeds/completions-cip/{year}/sex/
#   ZERO-VARS: [colleges] /college-university/ipeds/completions-cip/{year}/race/sex/
#   ZERO-VARS: [colleges] /college-university/scorecard/completion-by-income/{year}/
#   ZERO-VARS: [colleges] /college-university/nccs/{year}/
#   ZERO-VARS: [colleges] /college-university/pseo/{year}/
#   ZERO-VARS: [districts] /school-districts/ccd/enrollment/{year}/{grade}/race/sex/
#   ZERO-VARS: [schools] /schools/ccd/enrollment/{year}/{grade}/race/sex/
#   ZERO-VARS: [schools] /schools/edfacts/assessments/{year}/{grade}/race/
#   ZERO-VARS: [schools] /schools/edfacts/assessments/{year}/{grade}/sex/
#   ZERO-VARS: [schools] /schools/nhgis/census-1990/{year}/
#   ZERO-VARS: [schools] /schools/nhgis/census-2000/{year}/
#   ZERO-VARS: [schools] /schools/nhgis/census-2010/{year}/
# Traceback (most recent call last):
#   File "/daaf/scripts/mirror_maintenance/42_varlist-audit.py", line 125, in <module>
#     assert audit.height > 100, "Too few endpoint blocks parsed — format assumption broke"
#            ^^^^^^^^^^^^^^^^^^
# AssertionError: Too few endpoint blocks parsed — format assumption broke
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
