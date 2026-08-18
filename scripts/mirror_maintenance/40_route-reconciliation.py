# --- Config ---
# INTENT: Reconcile 37 (live probe inventory), 38 (boundary years), 39 (doc route sweep) into the
#         regeneration source-of-truth: per doc-file classification counts (matched-and-live,
#         renamed[+mapping], dead-confirmed-404, undocumented-live), a full bidirectional route
#         mapping table (doc route -> live route | DEAD; live route -> doc route | UNDOCUMENTED),
#         and per-live-route VERIFIED year ranges (from 38 boundary probes).
# REASONING: This is the table the later regeneration pass consumes. Renames are inherently
#            inferential — for each dead doc route we compute a token-Jaccard best-candidate live
#            route (scoped to the same top-level level segment) and label it INFERRED, never observed.
# ASSUMES: 37/38/39 parquets exist. Matching used 39's normalized matched_catalog_route field.
import re
from pathlib import Path
import polars as pl

PROJECT_DIR = Path("/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update")
OUT_DIR = PROJECT_DIR / "2026-08-07_endpoint-ground-truth"
P37 = OUT_DIR / "37_live_probe_inventory.parquet"
P38 = OUT_DIR / "38_boundary_years.parquet"
P39 = OUT_DIR / "39_doc_route_sweep.parquet"
OUT_PARQUET = OUT_DIR / "40_route_reconciliation.parquet"


def normalize(route):
    r = re.sub(r"^/api/v1", "", (route or "").strip())
    r = re.sub(r"\{[^}]*\}", "{}", r)
    return r.strip("/").lower()


def tokens(route):
    # non-placeholder path tokens, dropping the /api/v1 prefix, for Jaccard similarity
    r = re.sub(r"^/api/v1", "", (route or "").strip())
    segs = [s for s in r.strip("/").split("/") if s and not (s.startswith("{") and s.endswith("}"))]
    return set(segs)


def top_level(route):
    r = re.sub(r"^/api/v1", "", (route or "").strip()).strip("/")
    return r.split("/")[0] if r else ""


# --- Load ---
# INTENT: 37 and 39 are the direct-evidence cores and are required. 38 (boundary years) is
#         OPTIONAL here — if it has not finished (slow recovering API), reconciliation still
#         delivers the full doc<->live mapping; per-route verified year ranges are then marked
#         'pending-38' instead of blocking the deliverable.
inv = pl.read_parquet(P37)
doc = pl.read_parquet(P39)
if P38.exists():
    bnd = pl.read_parquet(P38)
    has_38 = True
else:
    bnd = pl.DataFrame(schema={"endpoint_id": pl.Int64, "boundary": pl.String,
                               "year": pl.Int64, "status": pl.Int64, "count": pl.Int64})
    has_38 = False
print(f"Loaded 37={inv.height} rows, 39={doc.height} rows, 38={'present='+str(bnd.height) if has_38 else 'ABSENT(pending)'}")

live_templates = inv.select("endpoint_id", "section", "route_template", "years_available",
                            "status", "count").to_dicts()
live_norm = {normalize(r["route_template"]): r for r in live_templates}

# doc matched-normalized set (a live route is 'documented' if some doc route matched it)
doc_rows = doc.to_dicts()
matched_norms = {normalize(r["matched_catalog_route_or_null"])
                 for r in doc_rows if r["matched_catalog_route_or_null"] is not None}

# --- Build: verified year ranges per live endpoint from 38 ---
verified = {}
for r in bnd.iter_rows(named=True):
    eid = r["endpoint_id"]
    ok = (r["status"] == 200 and (r["count"] or 0) > 0)
    d = verified.setdefault(eid, {"first_ok": None, "last_ok": None,
                                  "first_year": None, "last_year": None})
    if r["boundary"] == "first":
        d["first_year"] = r["year"]
        d["first_ok"] = ok
    else:
        d["last_year"] = r["year"]
        d["last_ok"] = ok

# --- Build: Direction A — doc route -> live | DEAD | LIVE-UNCATALOGED (+inferred rename) ---
records = []
per_file = {}
for r in doc_rows:
    fname = r["doc_file"]
    droute = r["doc_route"]
    pf = per_file.setdefault(fname, {"matched": 0, "dead404": 0, "live_uncataloged": 0, "other": 0})
    if r["matched_catalog_route_or_null"] is not None:
        cls = "MATCHED-LIVE"
        target = r["matched_catalog_route_or_null"]
        pf["matched"] += 1
    elif r["status"] == 404:
        cls = "DEAD-404"
        pf["dead404"] += 1
        # INFERRED rename candidate: highest Jaccard among live routes sharing top-level segment
        tl = top_level(droute)
        dtok = tokens(droute)
        best, best_score = None, 0.0
        for lr in live_templates:
            if top_level(lr["route_template"]) != tl:
                continue
            ltok = tokens(lr["route_template"])
            if not dtok or not ltok:
                continue
            j = len(dtok & ltok) / len(dtok | ltok)
            if j > best_score:
                best, best_score = lr["route_template"], j
        target = f"INFERRED-RENAME:{best} (jaccard={best_score:.2f})" if best else "DEAD-no-candidate"
    elif r["status"] == 200:
        cls = "LIVE-UNCATALOGED"
        target = f"WORKS(count={r['count']})"
        pf["live_uncataloged"] += 1
    else:
        cls = "OTHER"
        target = f"status={r['status']}"
        pf["other"] += 1
    records.append({
        "direction": "doc->live", "doc_file": fname, "doc_route": droute,
        "classification": cls, "target": target,
        "probed_url": r["probed_url"], "status": r["status"],
    })

# --- Build: Direction B — live route -> doc | UNDOCUMENTED (+verified year range) ---
for lr in live_templates:
    norm = normalize(lr["route_template"])
    documented = norm in matched_norms
    eid = lr["endpoint_id"]
    v = verified.get(eid, {})
    vr = "verified=pending-38" if not has_38 else ""
    if v:
        fy, ly = v.get("first_year"), v.get("last_year")
        fok, lok = v.get("first_ok"), v.get("last_ok")
        vr = f"verified[{fy}:{'OK' if fok else 'FAIL'} .. {ly}:{'OK' if lok else 'FAIL'}]"
    records.append({
        "direction": "live->doc",
        "doc_file": "",
        "doc_route": (lr["route_template"] if documented else "UNDOCUMENTED"),
        "classification": "DOCUMENTED-LIVE" if documented else "UNDOCUMENTED-LIVE",
        "target": lr["route_template"],
        "probed_url": f"advertised={lr['years_available']} {vr}",
        "status": lr["status"],
    })

# --- Save ---
df = pl.DataFrame(records)
df.write_parquet(OUT_PARQUET)
print(f"Saved: {OUT_PARQUET}  shape={df.shape}")

# --- Validate + Summary ---
assert df.height > 0, "Empty reconciliation"
n_undoc = sum(1 for r in records if r["classification"] == "UNDOCUMENTED-LIVE")
n_doclive = sum(1 for r in records if r["classification"] == "DOCUMENTED-LIVE")
print(f"VALIDATION: rows={df.height} PASS")
print("\n=== PER DOC FILE CLASSIFICATION ===")
for fname, pf in per_file.items():
    print(f"  {fname}: matched-live={pf['matched']}  dead-404={pf['dead404']}  "
          f"live-uncataloged={pf['live_uncataloged']}  other={pf['other']}")
print(f"\nLIVE routes documented: {n_doclive}")
print(f"LIVE routes UNDOCUMENTED (present-not-documented): {n_undoc}")

print("\n=== DOC->LIVE MAPPING (dead + renamed + uncataloged) ===")
for r in records:
    if r["direction"] == "doc->live" and r["classification"] != "MATCHED-LIVE":
        print(f"  [{r['doc_file']}] {r['doc_route']}  =>  {r['classification']}: {r['target']}")

print("\n=== UNDOCUMENTED-LIVE ROUTES (present, no doc entry) ===")
for r in records:
    if r["classification"] == "UNDOCUMENTED-LIVE":
        print(f"  {r['target']}  |  {r['probed_url']}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 16:31:21
# Command: python3 /daaf/scripts/mirror_maintenance/40_route-reconciliation.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# Loaded 37=129 rows, 39=83 rows, 38=ABSENT(pending)
# Saved: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_endpoint-ground-truth/40_route_reconciliation.parquet  shape=(212, 7)
# VALIDATION: rows=212 PASS
# 
# === PER DOC FILE CLASSIFICATION ===
#   colleges-endpoints.md: matched-live=19  dead-404=26  live-uncataloged=4  other=0
#   districts-endpoints.md: matched-live=12  dead-404=0  live-uncataloged=0  other=0
#   schools-endpoints.md: matched-live=20  dead-404=2  live-uncataloged=0  other=0
# 
# LIVE routes documented: 51
# LIVE routes UNDOCUMENTED (present-not-documented): 78
# 
# === DOC->LIVE MAPPING (dead + renamed + uncataloged) ===
#   [colleges-endpoints.md] /college-university/ipeds/student-charges-academic-year/{year}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/ipeds/directory/{year}/ (jaccard=0.50)
#   [colleges-endpoints.md] /college-university/ipeds/student-charges-academic-year/{year}/{level}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/ipeds/directory/{year}/ (jaccard=0.50)
#   [colleges-endpoints.md] /college-university/ipeds/student-charges-academic-year/{year}/living-arrangement/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/ipeds/directory/{year}/ (jaccard=0.40)
#   [colleges-endpoints.md] /college-university/ipeds/student-charges-program-year/{year}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/ipeds/directory/{year}/ (jaccard=0.50)
#   [colleges-endpoints.md] /college-university/ipeds/student-charges-program-year/{year}/program/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/ipeds/directory/{year}/ (jaccard=0.40)
#   [colleges-endpoints.md] /college-university/ipeds/enrollment-full-time-equivalent/{year}/  =>  LIVE-UNCATALOGED: WORKS(count=20355)
#   [colleges-endpoints.md] /college-university/ipeds/enrollment-headcount/{year}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/ipeds/enrollment-headcount/{year}/{level_of_study}/ (jaccard=1.00)
#   [colleges-endpoints.md] /college-university/ipeds/fall-enrollment/{year}/{level}/  =>  LIVE-UNCATALOGED: WORKS(count=556500)
#   [colleges-endpoints.md] /college-university/ipeds/fall-enrollment/{year}/{level}/race/  =>  LIVE-UNCATALOGED: WORKS(count=556500)
#   [colleges-endpoints.md] /college-university/ipeds/fall-enrollment/{year}/{level}/sex/  =>  LIVE-UNCATALOGED: WORKS(count=556500)
#   [colleges-endpoints.md] /college-university/ipeds/fall-enrollment-age/{year}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/ipeds/directory/{year}/ (jaccard=0.50)
#   [colleges-endpoints.md] /college-university/ipeds/libraries/{year}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/ipeds/directory/{year}/ (jaccard=0.50)
#   [colleges-endpoints.md] /college-university/ipeds/salaries/{year}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/ipeds/directory/{year}/ (jaccard=0.50)
#   [colleges-endpoints.md] /college-university/ipeds/sfa-by-income/{year}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/ipeds/directory/{year}/ (jaccard=0.50)
#   [colleges-endpoints.md] /college-university/ipeds/sfa-by-tuition-status/{year}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/ipeds/directory/{year}/ (jaccard=0.50)
#   [colleges-endpoints.md] /college-university/ipeds/net-price-by-income/{year}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/ipeds/directory/{year}/ (jaccard=0.50)
#   [colleges-endpoints.md] /college-university/ipeds/graduation-rates/{year}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/ipeds/directory/{year}/ (jaccard=0.50)
#   [colleges-endpoints.md] /college-university/ipeds/graduation-rates/{year}/race/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/ipeds/fall-enrollment/{year}/{level_of_study}/race/sex/ (jaccard=0.50)
#   [colleges-endpoints.md] /college-university/ipeds/graduation-rates/{year}/sex/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/ipeds/fall-enrollment/{year}/{level_of_study}/race/sex/ (jaccard=0.50)
#   [colleges-endpoints.md] /college-university/ipeds/completions-cip/{year}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/ipeds/directory/{year}/ (jaccard=0.50)
#   [colleges-endpoints.md] /college-university/ipeds/completions-cip/{year}/race/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/ipeds/fall-enrollment/{year}/{level_of_study}/race/sex/ (jaccard=0.50)
#   [colleges-endpoints.md] /college-university/ipeds/completions-cip/{year}/sex/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/ipeds/fall-enrollment/{year}/{level_of_study}/race/sex/ (jaccard=0.50)
#   [colleges-endpoints.md] /college-university/ipeds/completions-cip/{year}/race/sex/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/ipeds/fall-enrollment/{year}/{level_of_study}/race/sex/ (jaccard=0.67)
#   [colleges-endpoints.md] /college-university/scorecard/student-characteristics/{year}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/scorecard/student-characteristics/{year}/aid-applicants/ (jaccard=0.75)
#   [colleges-endpoints.md] /college-university/scorecard/completion-by-income/{year}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/scorecard/institutional-characteristics/{year}/ (jaccard=0.50)
#   [colleges-endpoints.md] /college-university/fsa/campus-based/{year}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/fsa/financial-responsibility/{year}/ (jaccard=0.50)
#   [colleges-endpoints.md] /college-university/fsa/ninety-ten/{year}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/fsa/financial-responsibility/{year}/ (jaccard=0.50)
#   [colleges-endpoints.md] /college-university/nccs/{year}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/nccs/990-forms/{year}/ (jaccard=0.67)
#   [colleges-endpoints.md] /college-university/eada/{year}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/eada/institutional-characteristics/{year}/ (jaccard=0.67)
#   [colleges-endpoints.md] /college-university/pseo/{year}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/college-university/pseo/earnings-and-flows/{year}/ (jaccard=0.67)
#   [schools-endpoints.md] /schools/crdc/finance/{year}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/schools/crdc/directory/{year}/ (jaccard=0.50)
#   [schools-endpoints.md] /schools/crdc/covid/{year}/  =>  DEAD-404: INFERRED-RENAME:/api/v1/schools/crdc/directory/{year}/ (jaccard=0.50)
# 
# === UNDOCUMENTED-LIVE ROUTES (present, no doc entry) ===
#   /api/v1/college-university/ipeds/academic-year-tuition/{year}/  |  advertised=1986&ndash;2023 verified=pending-38
#   /api/v1/college-university/ipeds/academic-year-tuition-prof-program/{year}/  |  advertised=1986&ndash;2008, 2010&ndash;2023 verified=pending-38
#   /api/v1/college-university/ipeds/academic-year-room-board-other/{year}/  |  advertised=1999&ndash;2023 verified=pending-38
#   /api/v1/schools/crdc/enrollment/{year}/race/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/college-university/ipeds/program-year-tuition-cip/{year}/  |  advertised=1987&ndash;2023 verified=pending-38
#   /api/v1/schools/crdc/enrollment/{year}/disability/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/college-university/ipeds/program-year-room-board-other/{year}/  |  advertised=1999&ndash;2023 verified=pending-38
#   /api/v1/schools/crdc/enrollment/{year}/lep/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/college-university/ipeds/enrollment-full-time-equivalent/{year}/{level_of_study}/  |  advertised=1997&ndash;2023 verified=pending-38
#   /api/v1/schools/crdc/discipline-instances/{year}/  |  advertised=2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/schools/crdc/discipline/{year}/disability/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/schools/crdc/discipline/{year}/disability/race/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/college-university/ipeds/fall-enrollment/{year}/{level_of_study}/age/sex/  |  advertised=1991, 1993, 1995, 1997, and 1999&ndash;2024 verified=pending-38
#   /api/v1/schools/crdc/discipline/{year}/disability/lep/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/schools/crdc/harassment-or-bullying/{year}/allegations/  |  advertised=2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/college-university/ipeds/fall-enrollment/{year}/residence/  |  advertised=1986, 1988, 1992, 1994, 1996, 1998, 2000&ndash;2024 verified=pending-38
#   /api/v1/college-university/ipeds/enrollment-headcount/{year}/{level_of_study}/  |  advertised=1996&ndash;2021 verified=pending-38
#   /api/v1/schools/crdc/harassment-or-bullying/{year}/race/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/college-university/ipeds/fall-retention/{year}/  |  advertised=2003&ndash;2024 verified=pending-38
#   /api/v1/schools/crdc/harassment-or-bullying/{year}/disability/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/schools/crdc/harassment-or-bullying/{year}/lep/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/schools/crdc/chronic-absenteeism/{year}/race/sex/  |  advertised=2013, 2015, 2017, 2020, 2021, 2022 verified=pending-38
#   /api/v1/college-university/ipeds/sfa-grants-and-net-price/{year}/  |  advertised=2008&ndash;2021 verified=pending-38
#   /api/v1/schools/crdc/chronic-absenteeism/{year}/disability/sex/  |  advertised=2013, 2015, 2017, 2020, 2021, 2022 verified=pending-38
#   /api/v1/schools/crdc/chronic-absenteeism/{year}/lep/sex/  |  advertised=2013, 2015, 2017, 2020, 2021, 2022 verified=pending-38
#   /api/v1/schools/crdc/restraint-and-seclusion/{year}/instances/  |  advertised=2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/college-university/ipeds/sfa-by-tuition-type/{year}/  |  advertised=1999&ndash;2021 verified=pending-38
#   /api/v1/schools/crdc/restraint-and-seclusion/{year}/disability/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/schools/crdc/restraint-and-seclusion/{year}/disability/race/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/college-university/ipeds/sfa-ftft/{year}/  |  advertised=1999&ndash;2021 verified=pending-38
#   /api/v1/college-university/ipeds/grad-rates/{year}/  |  advertised=1996&ndash;2023 verified=pending-38
#   /api/v1/schools/crdc/restraint-and-seclusion/{year}/disability/lep/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/schools/crdc/ap-ib-enrollment/{year}/race/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/college-university/ipeds/grad-rates-pell/{year}/  |  advertised=2015&ndash;2023 verified=pending-38
#   /api/v1/schools/crdc/ap-ib-enrollment/{year}/disability/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/college-university/ipeds/outcome-measures/{year}/  |  advertised=2015&ndash;2021 verified=pending-38
#   /api/v1/schools/crdc/ap-ib-enrollment/{year}/lep/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/college-university/ipeds/completers/{year}/  |  advertised=2011&ndash;2021 verified=pending-38
#   /api/v1/schools/crdc/ap-exams/{year}/race/sex/  |  advertised=2011, 2013, 2015, 2017 verified=pending-38
#   /api/v1/college-university/ipeds/completions-cip-2/{year}/  |  advertised=1991&ndash;2022 verified=pending-38
#   /api/v1/schools/crdc/ap-exams/{year}/disability/sex/  |  advertised=2011, 2013, 2015, 2017 verified=pending-38
#   /api/v1/college-university/ipeds/completions-cip-6/{year}/  |  advertised=1983&ndash;2023 verified=pending-38
#   /api/v1/schools/crdc/ap-exams/{year}/lep/sex/  |  advertised=2011, 2013, 2015, 2017 verified=pending-38
#   /api/v1/college-university/ipeds/academic-libraries/{year}/  |  advertised=2013&ndash;2023 verified=pending-38
#   /api/v1/schools/crdc/sat-act-participation/{year}/race/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/schools/crdc/sat-act-participation/{year}/disability/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/college-university/ipeds/salaries-instructional-staff/{year}/  |  advertised=1980, 1984, 1985, 1987, 1989&ndash;1999, 2001&ndash;2024 verified=pending-38
#   /api/v1/schools/crdc/sat-act-participation/{year}/lep/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/college-university/ipeds/salaries-noninstructional-staff/{year}/  |  advertised=2012&ndash;2024 verified=pending-38
#   /api/v1/college-university/scorecard/student-characteristics/{year}/aid-applicants/  |  advertised=1997&ndash;2016 verified=pending-38
#   /api/v1/schools/crdc/math-and-science/{year}/race/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/college-university/scorecard/student-characteristics/{year}/home-neighborhood/  |  advertised=1997&ndash;2016 verified=pending-38
#   /api/v1/schools/crdc/math-and-science/{year}/disability/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/schools/crdc/math-and-science/{year}/lep/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/schools/crdc/algebra1/{year}/race/sex  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/schools/crdc/algebra1/{year}/disability/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/college-university/nhgis/census-1990/{year}/  |  advertised=1980, 1984&ndash;2023 verified=pending-38
#   /api/v1/schools/crdc/algebra1/{year}/lep/sex/  |  advertised=2011, 2013, 2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/college-university/nhgis/census-2000/{year}/  |  advertised=1980, 1984&ndash;2023 verified=pending-38
#   /api/v1/college-university/nhgis/census-2010/{year}/  |  advertised=1980, 1984&ndash;2023 verified=pending-38
#   /api/v1/schools/crdc/dual-enrollment/{year}/race/sex  |  advertised=2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/schools/crdc/dual-enrollment/{year}/disability/sex  |  advertised=2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/college-university/nhgis/census-2020/{year}/  |  advertised=1980, 1984&ndash;2023 verified=pending-38
#   /api/v1/schools/crdc/dual-enrollment/{year}/lep/sex  |  advertised=2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/schools/crdc/credit-recovery/{year}/  |  advertised=2015, 2017 verified=pending-38
#   /api/v1/schools/crdc/suspensions-days/{year}/race/sex  |  advertised=2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/college-university/fsa/campus-based-volume/{year}/  |  advertised=2001&ndash;2021 verified=pending-38
#   /api/v1/schools/crdc/suspensions-days/{year}/disability/sex  |  advertised=2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/college-university/fsa/90-10-revenue-percentages/{year}/  |  advertised=2014&ndash;2021 verified=pending-38
#   /api/v1/schools/crdc/suspensions-days/{year}/lep/sex  |  advertised=2015, 2017, 2020, 2021 verified=pending-38
#   /api/v1/college-university/nccs/990-forms/{year}/  |  advertised=1993&ndash;2016 verified=pending-38
#   /api/v1/schools/crdc/school-finance/{year}/  |  advertised=2011, 2013, 2015, 2017 verified=pending-38
#   /api/v1/schools/crdc/retention/{year}/{grade}/race/sex  |  advertised=2011, 2013, 2015, 2017, 2020 verified=pending-38
#   /api/v1/college-university/eada/institutional-characteristics/{year}/  |  advertised=2002&ndash;2021 verified=pending-38
#   /api/v1/schools/crdc/retention/{year}/{grade}/disability/sex  |  advertised=2011, 2013, 2015, 2017 verified=pending-38
#   /api/v1/schools/crdc/retention/{year}/{grade}/lep/sex  |  advertised=2011, 2013, 2015, 2017 verified=pending-38
#   /api/v1/college-university/pseo/earnings-and-flows/{year}/  |  advertised=2001&ndash;2021 verified=pending-38
#   /api/v1/schools/crdc/covid-indicators/{year}/  |  advertised=2020, 2021 verified=pending-38
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
