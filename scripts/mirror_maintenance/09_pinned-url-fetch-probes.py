# --- Config ---
# INTENT: Prove the pinned resolve URLs actually serve correct bytes by downloading a
#   stratified ~15-file sample, recomputing sha256 vs the manifest, verifying parquet
#   schema + row count, and re-proving the drift report's marquee claim (grad-rates-150
#   has ZERO full-key duplicates) directly from the LIVE repo.
# REASONING: script 08 proved the tree metadata (lfs.oid/size) matches; this script proves
#   the resolve endpoint returns those exact bytes and that the headline dedup finding
#   reproduces on freshly downloaded data.
# ASSUMES: plain HTTPS (no huggingface_hub). Pinned URL pattern
#   resolve/{REVISION}/{path}. Manifest carries shipped_sha256/bytes for all objects and
#   row_count/column_count for rebuilt/staged/grad files (null for carried-forward).
import time
import hashlib
import urllib.request
import urllib.error
import polars as pl

BASE = "/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update"
MANIFEST = f"{BASE}/mirror_v2_tree/build_manifest.parquet"
SCRATCH = f"{BASE}/scripts/scratch/remote_validation"
REPO = "brhkim/education_data_portal_mirror_2026q3"
REVISION = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
RESOLVE = f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}"

GRAD_PATH = "ipeds/colleges_ipeds_grad-rates.parquet"
# INTENT: full-key = entity (unitid, cohort_year, institution_level, subcohort, race, sex)
#   + survey year, per drift report §2. NEW mirror must have zero full-key duplicates.
FULL_KEY = ["unitid", "cohort_year", "institution_level", "subcohort", "race", "sex", "year"]

# --- Stratified sample (~15 files), smallest-per-stratum to keep download volume small ---
# REASONING: strata cover carried-forward, rebuilt-reference-schema (the 23 from run 06_c),
#   staged-2026-07-21, one xls codebook, and the mandatory grad-rates-150 file.
SAMPLE = [
    # carried-forward (manifest row_count/column_count are null -> sha256 is the anchor)
    "nacubo/colleges_nacubo_endow.parquet",
    "fsa/colleges_fsa_90_10_revenue_percentages.parquet",
    "fsa/colleges_fsa_composite_scores.parquet",
    "ccd/schools_ccd_lea_enrollment_1986.parquet",
    "ccd/schools_ccd_lea_enrollment_1987.parquet",
    # rebuilt-reference-schema (run 06_c)
    "ipeds/colleges_ipeds_student-faculty-ratio.parquet",
    "ipeds/colleges_ipeds_ay_tuition_firstprof.parquet",
    "ipeds/colleges_ipeds_py_room_board_other.parquet",
    "ipeds/colleges_ipeds_grad-rates-200pct.parquet",
    "ipeds/colleges_ipeds_fall-retention.parquet",
    # previously-staged (staged-2026-07-21 / copied_staged)
    "ipeds/colleges_ipeds_fall-enrollment-age_2022.parquet",
    "ipeds/colleges_ipeds_fall-enrollment-age_2021.parquet",
    # one xls codebook
    "ipeds/codebook_colleges_ipeds_student-faculty-ratio.xls",
    # mandatory grad-rates-150 file
    GRAD_PATH,
]

# --- Load manifest index ---
man = pl.read_parquet(MANIFEST)
man_idx = {
    r["relative_path"]: {
        "sha256": r["shipped_sha256"],
        "bytes": r["shipped_bytes"],
        "row_count": r["row_count"],
        "column_count": r["column_count"],
        "provenance": r["provenance"],
        "action": r["action"],
    }
    for r in man.iter_rows(named=True)
}
print(f"Loaded manifest: {man.shape[0]} rows. Sample size: {len(SAMPLE)}")

# --- Fetch + verify each sampled file ---
results = []          # per-file verdict rows
total_bytes = 0
for path in SAMPLE:
    mrec = man_idx[path]
    url = f"{RESOLVE}/{path}"
    local = f"{SCRATCH}/" + path.replace("/", "__")
    # INTENT: download with 3 retries + exponential backoff
    data = None
    last_err = None
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "daaf-mirror-validate/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            break
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_err = e
            wait = 2 ** attempt
            print(f"  {path} attempt {attempt} failed: {e!r}; backoff {wait}s")
            time.sleep(wait)
    assert data is not None, f"download failed for {path}: {last_err!r}"
    with open(local, "wb") as fh:
        fh.write(data)
    total_bytes += len(data)

    dl_sha = hashlib.sha256(data).hexdigest()
    sha_ok = dl_sha == mrec["sha256"]
    size_ok = len(data) == mrec["bytes"]

    # INTENT: for parquet objects, open the DOWNLOADED file and check schema + row count.
    schema_ok = None
    rowcount_ok = None
    actual_rows = None
    actual_cols = None
    if path.endswith(".parquet"):
        df = pl.read_parquet(local)
        actual_rows = df.height
        actual_cols = df.width
        # column_count vs manifest where recorded (null for carried-forward)
        if mrec["column_count"] is not None:
            schema_ok = actual_cols == mrec["column_count"]
        if mrec["row_count"] is not None:
            rowcount_ok = actual_rows == mrec["row_count"]
        # ASSUMES: every parquet should be non-empty
        assert actual_rows > 0, f"{path} opened with 0 rows"

    results.append({
        "path": path,
        "stratum": mrec["provenance"] + "/" + mrec["action"],
        "dl_bytes": len(data),
        "sha_ok": sha_ok,
        "size_ok": size_ok,
        "manifest_cols": mrec["column_count"],
        "actual_cols": actual_cols,
        "schema_ok": schema_ok,
        "manifest_rows": mrec["row_count"],
        "actual_rows": actual_rows,
        "rowcount_ok": rowcount_ok,
    })
    print(f"  [{'OK' if sha_ok and size_ok else 'FAIL'}] {path} "
          f"({len(data):,}B) sha_ok={sha_ok} size_ok={size_ok} "
          f"cols={actual_cols}/{mrec['column_count']} rows={actual_rows}/{mrec['row_count']}")

print(f"\nTotal downloaded: {total_bytes:,} bytes across {len(SAMPLE)} files")

# --- Validate: per-file summary + hard gates ---
print("\n=== PER-FILE VERIFICATION ===")
res_df = pl.DataFrame(results)
with pl.Config(fmt_str_lengths=70, tbl_width_chars=320, tbl_rows=30):
    print(res_df)

sha_all = all(r["sha_ok"] for r in results)
size_all = all(r["size_ok"] for r in results)
schema_all = all(r["schema_ok"] for r in results if r["schema_ok"] is not None)
rows_all = all(r["rowcount_ok"] for r in results if r["rowcount_ok"] is not None)
print(f"\nsha256 match: {sum(r['sha_ok'] for r in results)}/{len(results)}")
print(f"byte-size match: {sum(r['size_ok'] for r in results)}/{len(results)}")
n_schema = sum(1 for r in results if r["schema_ok"] is not None)
n_rows = sum(1 for r in results if r["rowcount_ok"] is not None)
print(f"schema (col_count) match where manifest recorded: {sum(1 for r in results if r['schema_ok'])}/{n_schema}")
print(f"row_count match where manifest recorded: {sum(1 for r in results if r['rowcount_ok'])}/{n_rows}")

# --- Validate: grad-rates-150 ZERO full-key duplicates (live re-proof) ---
print("\n=== GRAD-RATES-150 DEDUP RE-PROOF (live pinned repo) ===")
grad_local = f"{SCRATCH}/" + GRAD_PATH.replace("/", "__")
grad = pl.read_parquet(grad_local)
print(f"grad-rates rows: {grad.height:,} (manifest: {man_idx[GRAD_PATH]['row_count']:,})")
assert set(FULL_KEY).issubset(set(grad.columns)), f"full-key cols missing: {set(FULL_KEY)-set(grad.columns)}"
# INTENT: count rows whose full key appears more than once (full-key duplicates)
n_fullkey_dupe = grad.select(pl.struct(FULL_KEY).is_duplicated().alias("d"))["d"].sum()
# INTENT: count exact whole-row duplicates
n_wholerow_dupe = grad.is_duplicated().sum()
n_unique_keys = grad.select(FULL_KEY).unique().height
print(f"full-key columns: {FULL_KEY}")
print(f"full-key duplicate rows: {n_fullkey_dupe}")
print(f"whole-row duplicate rows: {n_wholerow_dupe}")
print(f"unique full-key combos: {n_unique_keys:,} (== rows? {n_unique_keys == grad.height})")

# --- VERDICT ---
print("\n=== VERDICT ===")
checks = {
    "all_sha256_match": sha_all,
    "all_size_match": size_all,
    "all_schema_match(where recorded)": schema_all,
    "all_rowcount_match(where recorded)": rows_all,
    "grad_rows==manifest": grad.height == man_idx[GRAD_PATH]["row_count"],
    "grad_zero_fullkey_dupes": n_fullkey_dupe == 0,
    "grad_zero_wholerow_dupes": n_wholerow_dupe == 0,
    "grad_uniquekeys==rows": n_unique_keys == grad.height,
}
for name, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
all_pass = all(checks.values())
print(f"\nSCRIPT 09 OVERALL: {'PASS' if all_pass else 'FAIL'}")
assert all_pass, f"Pinned-URL probes FAILED: {[k for k,v in checks.items() if not v]}"
print("Pinned URLs serve faithful bytes; grad-rates-150 marquee dedup claim reproduced.")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 13:11:23
# Command: python3 /daaf/scripts/mirror_maintenance/09_pinned-url-fetch-probes.py
# Duration: 10s
# Exit code: 0
#
# --- STDOUT ---
# Loaded manifest: 497 rows. Sample size: 14
#   [OK] nacubo/colleges_nacubo_endow.parquet (162,491B) sha_ok=True size_ok=True cols=7/None rows=8197/None
#   [OK] fsa/colleges_fsa_90_10_revenue_percentages.parquet (254,280B) sha_ok=True size_ok=True cols=8/None rows=13821/None
#   [OK] fsa/colleges_fsa_composite_scores.parquet (274,206B) sha_ok=True size_ok=True cols=8/None rows=37589/None
#   [OK] ccd/schools_ccd_lea_enrollment_1986.parquet (392,475B) sha_ok=True size_ok=True cols=7/None rows=195134/None
#   [OK] ccd/schools_ccd_lea_enrollment_1987.parquet (491,289B) sha_ok=True size_ok=True cols=7/None rows=259526/None
#   [OK] ipeds/colleges_ipeds_student-faculty-ratio.parquet (142,902B) sha_ok=True size_ok=True cols=4/4 rows=102371/102371
#   [OK] ipeds/colleges_ipeds_ay_tuition_firstprof.parquet (333,233B) sha_ok=True size_ok=True cols=8/8 rows=50802/50802
#   [OK] ipeds/colleges_ipeds_py_room_board_other.parquet (533,054B) sha_ok=True size_ok=True cols=6/6 rows=108932/108932
#   [OK] ipeds/colleges_ipeds_grad-rates-200pct.parquet (1,243,241B) sha_ok=True size_ok=True cols=17/17 rows=93088/93088
#   [OK] ipeds/colleges_ipeds_fall-retention.parquet (1,300,581B) sha_ok=True size_ok=True cols=10/10 rows=278296/278296
#   [OK] ipeds/colleges_ipeds_fall-enrollment-age_2022.parquet (819,617B) sha_ok=True size_ok=True cols=9/9 rows=588150/588150
#   [OK] ipeds/colleges_ipeds_fall-enrollment-age_2021.parquet (1,421,252B) sha_ok=True size_ok=True cols=9/9 rows=1204011/1204011
#   [OK] ipeds/codebook_colleges_ipeds_student-faculty-ratio.xls (14,848B) sha_ok=True size_ok=True cols=None/None rows=None/None
#   [OK] ipeds/colleges_ipeds_grad-rates.parquet (31,968,148B) sha_ok=True size_ok=True cols=18/18 rows=6141988/6141988
# 
# Total downloaded: 39,351,617 bytes across 14 files
# 
# === PER-FILE VERIFICATION ===
# shape: (14, 11)
# ┌─────────────────────────────────────────────────────────┬────────────────────────────────────────────────────────┬──────────┬────────┬───┬───────────┬───────────────┬─────────────┬─────────────┐
# │ path                                                    ┆ stratum                                                ┆ dl_bytes ┆ sha_ok ┆ … ┆ schema_ok ┆ manifest_rows ┆ actual_rows ┆ rowcount_ok │
# │ ---                                                     ┆ ---                                                    ┆ ---      ┆ ---    ┆   ┆ ---       ┆ ---           ┆ ---         ┆ ---         │
# │ str                                                     ┆ str                                                    ┆ i64      ┆ bool   ┆   ┆ bool      ┆ i64           ┆ i64         ┆ bool        │
# ╞═════════════════════════════════════════════════════════╪════════════════════════════════════════════════════════╪══════════╪════════╪═══╪═══════════╪═══════════════╪═════════════╪═════════════╡
# │ nacubo/colleges_nacubo_endow.parquet                    ┆ carried-forward/downloaded                             ┆ 162491   ┆ true   ┆ … ┆ null      ┆ null          ┆ 8197        ┆ null        │
# │ fsa/colleges_fsa_90_10_revenue_percentages.parquet      ┆ carried-forward/downloaded                             ┆ 254280   ┆ true   ┆ … ┆ null      ┆ null          ┆ 13821       ┆ null        │
# │ fsa/colleges_fsa_composite_scores.parquet               ┆ carried-forward/downloaded                             ┆ 274206   ┆ true   ┆ … ┆ null      ┆ null          ┆ 37589       ┆ null        │
# │ ccd/schools_ccd_lea_enrollment_1986.parquet             ┆ carried-forward/downloaded                             ┆ 392475   ┆ true   ┆ … ┆ null      ┆ null          ┆ 195134      ┆ null        │
# │ ccd/schools_ccd_lea_enrollment_1987.parquet             ┆ carried-forward/downloaded                             ┆ 491289   ┆ true   ┆ … ┆ null      ┆ null          ┆ 259526      ┆ null        │
# │ ipeds/colleges_ipeds_student-faculty-ratio.parquet      ┆ fetched-2026-08-06/rebuilt-reference-schema-2026-08-06 ┆ 142902   ┆ true   ┆ … ┆ true      ┆ 102371        ┆ 102371      ┆ true        │
# │ ipeds/colleges_ipeds_ay_tuition_firstprof.parquet       ┆ fetched-2026-08-06/rebuilt-reference-schema-2026-08-06 ┆ 333233   ┆ true   ┆ … ┆ true      ┆ 50802         ┆ 50802       ┆ true        │
# │ ipeds/colleges_ipeds_py_room_board_other.parquet        ┆ fetched-2026-08-06/rebuilt-reference-schema-2026-08-06 ┆ 533054   ┆ true   ┆ … ┆ true      ┆ 108932        ┆ 108932      ┆ true        │
# │ ipeds/colleges_ipeds_grad-rates-200pct.parquet          ┆ fetched-2026-08-06/rebuilt-reference-schema-2026-08-06 ┆ 1243241  ┆ true   ┆ … ┆ true      ┆ 93088         ┆ 93088       ┆ true        │
# │ ipeds/colleges_ipeds_fall-retention.parquet             ┆ fetched-2026-08-06/rebuilt-reference-schema-2026-08-06 ┆ 1300581  ┆ true   ┆ … ┆ true      ┆ 278296        ┆ 278296      ┆ true        │
# │ ipeds/colleges_ipeds_fall-enrollment-age_2022.parquet   ┆ staged-2026-07-21/copied_staged                        ┆ 819617   ┆ true   ┆ … ┆ true      ┆ 588150        ┆ 588150      ┆ true        │
# │ ipeds/colleges_ipeds_fall-enrollment-age_2021.parquet   ┆ staged-2026-07-21/copied_staged                        ┆ 1421252  ┆ true   ┆ … ┆ true      ┆ 1204011       ┆ 1204011     ┆ true        │
# │ ipeds/codebook_colleges_ipeds_student-faculty-ratio.xls ┆ carried-forward/downloaded                             ┆ 14848    ┆ true   ┆ … ┆ null      ┆ null          ┆ null        ┆ null        │
# │ ipeds/colleges_ipeds_grad-rates.parquet                 ┆ fetched-2026-08-06/rebuilt-reference-schema-2026-08-06 ┆ 31968148 ┆ true   ┆ … ┆ true      ┆ 6141988       ┆ 6141988     ┆ true        │
# └─────────────────────────────────────────────────────────┴────────────────────────────────────────────────────────┴──────────┴────────┴───┴───────────┴───────────────┴─────────────┴─────────────┘
# 
# sha256 match: 14/14
# byte-size match: 14/14
# schema (col_count) match where manifest recorded: 8/8
# row_count match where manifest recorded: 8/8
# 
# === GRAD-RATES-150 DEDUP RE-PROOF (live pinned repo) ===
# grad-rates rows: 6,141,988 (manifest: 6,141,988)
# full-key columns: ['unitid', 'cohort_year', 'institution_level', 'subcohort', 'race', 'sex', 'year']
# full-key duplicate rows: 0
# whole-row duplicate rows: 0
# unique full-key combos: 6,141,988 (== rows? True)
# 
# === VERDICT ===
#   [PASS] all_sha256_match
#   [PASS] all_size_match
#   [PASS] all_schema_match(where recorded)
#   [PASS] all_rowcount_match(where recorded)
#   [PASS] grad_rows==manifest
#   [PASS] grad_zero_fullkey_dupes
#   [PASS] grad_zero_wholerow_dupes
#   [PASS] grad_uniquekeys==rows
# 
# SCRIPT 09 OVERALL: PASS
# Pinned URLs serve faithful bytes; grad-rates-150 marquee dedup claim reproduced.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
