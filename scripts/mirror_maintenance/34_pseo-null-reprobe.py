# --- Config ---
# INTENT: Unit 3 of doc-audit gap-fill — cleanly re-run the PSEO "no null values" claim that
#   the postsecondary audit could not test (its probe crashed on a polars DuplicateError from
#   a repeated .alias("s"), NOT a data condition). Compute per-column null counts for every
#   pseo/* parquet on the pinned mirror and verdict VERIFIED (zero nulls everywhere) /
#   CONTRADICTED (quote offending columns+counts).
# REASONING: pl.all().null_count() preserves each source column name, so there is no alias
#   collision — the exact bug that broke the prior probe is structurally avoided. Enumerate
#   pseo files via the HF tree API (authoritative) rather than guessing the year list.
# ASSUMES: pinned public repo; pseo dataset is yearly colleges_pseo_{year} (datasets-ref 240).
import polars as pl
import urllib.request, json, io, time
from collections import Counter

PIN = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
REPO = "brhkim/education_data_portal_mirror_2026q3"
BASE = f"https://huggingface.co/datasets/{REPO}/resolve/{PIN}"
TREE = f"https://huggingface.co/api/datasets/{REPO}/tree/{PIN}/pseo"

def http_json(url, retries=3):
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "daaf-audit"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except Exception as e:
            last = e; time.sleep(2 * (a + 1))
    raise last

# --- Enumerate pseo parquet files (authoritative tree listing) ---
entries = http_json(TREE)
pseo_files = sorted(e["path"] for e in entries
                    if e.get("type") == "file" and e["path"].endswith(".parquet"))
print(f"pseo parquet files found: {len(pseo_files)}")
for p in pseo_files:
    print(f"  {p}")

results = []
def rec(claim, obs, verdict):
    results.append((claim, obs, verdict)); print(f"[{verdict}] {claim} -> {obs}")

# --- Per-file null-count probe ---
grand_offenders = {}
for rel in pseo_files:
    stem = rel[:-len(".parquet")]
    try:
        lf = pl.scan_parquet(f"{BASE}/{rel}")
        # pl.all().null_count() keeps original column names => no DuplicateError
        nc = lf.select(pl.all().null_count()).collect()
        row = nc.to_dicts()[0]
        offenders = {c: n for c, n in row.items() if n and n > 0}
        total_nulls = sum(row.values())
        ncols = len(row)
        if offenders:
            grand_offenders[stem] = offenders
            rec(f"PSEO {stem}: no nulls (SKILL 'no null values')",
                f"{ncols} cols; TOTAL nulls={total_nulls}; offenders={offenders}", "CONTRADICTED")
        else:
            rec(f"PSEO {stem}: no nulls (SKILL 'no null values')",
                f"{ncols} cols; TOTAL nulls=0", "VERIFIED")
    except Exception as e:
        rec(f"PSEO {stem}: null probe", f"ERR {type(e).__name__}: {str(e)[:120]}", "UNTESTABLE")

print("\n### PSEO NULL RE-PROBE SUMMARY ###")
print(f"files probed: {len(pseo_files)}")
print(f"files with ANY null: {len(grand_offenders)}")
if grand_offenders:
    print("offending files/columns:")
    for f, o in grand_offenders.items():
        print(f"  {f}: {o}")
print("### TALLY ###")
for k, v in Counter(v for _, _, v in results).items():
    print(f"  {k}: {v}")
overall = "VERIFIED (zero nulls in all pseo files)" if not grand_offenders else "CONTRADICTED (nulls present)"
print(f"### OVERALL PSEO no-null claim: {overall} ###")
print("DONE 34")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 14:22:17
# Command: python3 /daaf/scripts/mirror_maintenance/34_pseo-null-reprobe.py
# Duration: 25s
# Exit code: 0
#
# --- STDOUT ---
# pseo parquet files found: 21
#   pseo/colleges_pseo_2001.parquet
#   pseo/colleges_pseo_2002.parquet
#   pseo/colleges_pseo_2003.parquet
#   pseo/colleges_pseo_2004.parquet
#   pseo/colleges_pseo_2005.parquet
#   pseo/colleges_pseo_2006.parquet
#   pseo/colleges_pseo_2007.parquet
#   pseo/colleges_pseo_2008.parquet
#   pseo/colleges_pseo_2009.parquet
#   pseo/colleges_pseo_2010.parquet
#   pseo/colleges_pseo_2011.parquet
#   pseo/colleges_pseo_2012.parquet
#   pseo/colleges_pseo_2013.parquet
#   pseo/colleges_pseo_2014.parquet
#   pseo/colleges_pseo_2015.parquet
#   pseo/colleges_pseo_2016.parquet
#   pseo/colleges_pseo_2017.parquet
#   pseo/colleges_pseo_2018.parquet
#   pseo/colleges_pseo_2019.parquet
#   pseo/colleges_pseo_2020.parquet
#   pseo/colleges_pseo_2021.parquet
# [VERIFIED] PSEO pseo/colleges_pseo_2001: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# [VERIFIED] PSEO pseo/colleges_pseo_2002: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# [VERIFIED] PSEO pseo/colleges_pseo_2003: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# [VERIFIED] PSEO pseo/colleges_pseo_2004: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# [VERIFIED] PSEO pseo/colleges_pseo_2005: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# [VERIFIED] PSEO pseo/colleges_pseo_2006: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# [VERIFIED] PSEO pseo/colleges_pseo_2007: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# [VERIFIED] PSEO pseo/colleges_pseo_2008: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# [VERIFIED] PSEO pseo/colleges_pseo_2009: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# [VERIFIED] PSEO pseo/colleges_pseo_2010: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# [VERIFIED] PSEO pseo/colleges_pseo_2011: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# [VERIFIED] PSEO pseo/colleges_pseo_2012: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# [VERIFIED] PSEO pseo/colleges_pseo_2013: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# [VERIFIED] PSEO pseo/colleges_pseo_2014: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# [VERIFIED] PSEO pseo/colleges_pseo_2015: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# [VERIFIED] PSEO pseo/colleges_pseo_2016: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# [VERIFIED] PSEO pseo/colleges_pseo_2017: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# [VERIFIED] PSEO pseo/colleges_pseo_2018: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# [VERIFIED] PSEO pseo/colleges_pseo_2019: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# [VERIFIED] PSEO pseo/colleges_pseo_2020: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# [VERIFIED] PSEO pseo/colleges_pseo_2021: no nulls (SKILL 'no null values') -> 18 cols; TOTAL nulls=0
# 
# ### PSEO NULL RE-PROBE SUMMARY ###
# files probed: 21
# files with ANY null: 0
# ### TALLY ###
#   VERIFIED: 21
# ### OVERALL PSEO no-null claim: VERIFIED (zero nulls in all pseo files) ###
# DONE 34
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
