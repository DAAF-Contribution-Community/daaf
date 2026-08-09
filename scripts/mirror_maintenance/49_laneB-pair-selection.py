#!/usr/bin/env python3
# =============================================================================
# 49_laneB-pair-selection.py  (Lane B EXPANSION — mechanical pair selection)
# =============================================================================
# INTENT: Mechanically select mirror<->live-API 1:1 endpoint<->file pairs for the
#   expanded Lane B parity battery (target ~70 endpoint-year count comparisons +
#   ~30 deep value slices). Drive selection from the wave-4 GROUND TRUTH so the
#   pairs and years are chosen by verified fact, not guesswork:
#     * 37_live_probe_inventory.parquet  -> 129 live 200-routes: route_template,
#       years_available, mid_year, live count@mid_year, fields (live column list).
#     * mirror_v2_tree/ (byte-identical to HF pinned 497/497; see wave-2) -> the
#       mirror files to pair against, read with column projection.
#   The file<->endpoint naming convention (+ its documented renames) is codified
#   from education-data-query/references/datasets-reference.md.
#
# METHOD (per live 200-route):
#   1. Parse route_template /api/v1/{level}/{source}/{topic..}/{year}/.
#   2. Classify CLEAN 1:1 iff the ONLY placeholder is {year} AND it is the final
#      path segment (no trailing disaggregation segments like /race/ or {grade}).
#      REASONING: a 1:1 endpoint yields one row per entity per year, so the mirror
#      row count filtered to that year is directly comparable to the API `count`.
#      Disaggregated/multi-placeholder routes need adaptive grain filters (handled
#      by the proven script-20 approach, out of scope for the clean expansion set).
#   3. Resolve the mirror parquet file via {level->prefix} x {topic variants +
#      curated alias} candidates, accepting the first that EXISTS on disk and
#      carries a `year` column (so it is per-year queryable). ASSUMES the tree is
#      the shipped mirror (proven byte-identical), so on-disk existence == mirror
#      membership.
#   4. Pick a primary entity key from the file schema (unitid|ncessch|leaid|
#      crdc_id) for the value-slice alignment; record it.
#   5. Parse years_available into concrete years; choose up to 3 SWEEP years
#      (earliest-available, mid_year, most-recent-available) intersected with
#      availability, and one SLICE year (prefer mid_year) for the deep value slice.
#
# OUTPUT: 49_laneB_pairs.parquet (one row per matched clean 1:1 pair) + an audit
#   print of matched vs unmatched clean-1:1 routes (unmatched => a rename the alias
#   table does not yet cover; reported verbatim, never silently dropped).
#
# Read-only (local parquet + one ground-truth parquet). No network here. No /tmp.
# File-first via run_with_capture.sh.
# =============================================================================

# --- Config ---
import re
import polars as pl
from pathlib import Path

BASE_DIR = Path("/daaf")
PROJECT_DIR = BASE_DIR / "research" / "2026-08-06_FrameworkDev_MirrorV2Update"
TREE_DIR = PROJECT_DIR / "mirror_v2_tree"
GT_DIR = PROJECT_DIR / "2026-08-07_endpoint-ground-truth"
OUT_DIR = PROJECT_DIR / "2026-08-07_urban-fidelity"
OUT_DIR.mkdir(parents=True, exist_ok=True)
IN_INV = GT_DIR / "37_live_probe_inventory.parquet"
OUT_PAIRS = OUT_DIR / "49_laneB_pairs.parquet"

# level path segment -> mirror filename prefix candidates (school-districts uses both)
LEVEL_PREFIX = {
    "college-university": ["colleges"],
    "schools": ["schools"],
    "school-districts": ["school-districts", "districts"],
}

# Curated route-topic -> mirror-file-topic renames (from datasets-reference.md naming
# notes + observed route/file slug differences). REASONING: several Urban API route
# slugs differ from the mirror file `path` topic token; these are the documented cases.
# Key is the route topic slug (segments joined by '-'); value is the file topic token.
TOPIC_ALIAS = {
    "enrollment-full-time-equivalent": "enrollment-fte",
    "academic-libraries": "academic_libraries",
    "graduation-rates": "grad-rates",
    "graduation-rates-200": "grad-rates-200pct",
    "graduation-rates-pell": "grad-rates-pell",
    "enrollment-headcount": "headcount",
    "fall-enrollment-residence": "fall-res",
    "instructional-staff-salaries": "salaries_is",
    "noninstructional-staff-salaries": "salaries_nis",
    "academic-year-room-board-other": "ay_room_board_other",
    "academic-year-tuition-and-fees": "ay_tuition_fees",
    "academic-year-tuition": "ay_tuition_fees",
    "prior-year-room-board-other": "py_room_board_other",
    "prior-year-tuition-cip": "py_tuition_cip",
    "prior-year-tuition-by-cip-code": "py_tuition_cip",
    "institutional-characteristics_scorecard": "inst_characteristics",
    # scorecard
    "default": "repayment_fsa",
    "repayment": "repayment_nslds",
    # fsa
    "financial-responsibility": "composite_scores",
    "90-10-revenue": "90_10_revenue_percentages",
    "campus-based-volume": "campus_based_volume",
    # nccs / nacubo / eada / csafety
    "nccs": "nccs_all",
    "endowments": "nacubo_endow",
    "hate-crimes": "hate_crimes",
}

# Primary entity key candidates, in preference order, by level.
KEY_BY_LEVEL = {
    "college-university": ["unitid"],
    "schools": ["ncessch", "crdc_id"],
    "school-districts": ["leaid"],
}
ID_CANDIDATES = ["unitid", "ncessch", "leaid", "crdc_id"]


def parse_years(s):
    # INTENT: expand an Urban years_available string ("1986&ndash;2024", "1980,
    #   1984&ndash;2024", non-contiguous lists) into a sorted concrete year list.
    if s is None:
        return []
    t = (s.replace("&ndash;", "-").replace("&#8211;", "-")
          .replace("–", "-").replace("—", "-").replace("‒", "-").replace("‐", "-"))
    years = set()
    for tok in t.split(","):
        nums = re.findall(r"\d{4}", tok)
        if len(nums) >= 2:
            a, b = int(nums[0]), int(nums[1])
            if a <= b:
                years.update(range(a, b + 1))
        elif len(nums) == 1:
            years.add(int(nums[0]))
    return sorted(years)


def classify_route(route_template):
    # INTENT: return (is_clean_1to1, level, source, topic_slug). CLEAN 1:1 means the
    #   only {placeholder} is {year} and it is the final segment.
    parts = route_template.strip("/").split("/")
    # strip leading api/v1
    if parts[:2] == ["api", "v1"]:
        parts = parts[2:]
    if len(parts) < 3:
        return (False, None, None, None)
    level, source = parts[0], parts[1]
    rest = parts[2:]
    placeholders = [p for p in rest if p.startswith("{") and p.endswith("}")]
    # clean iff exactly one placeholder, it is {year}, and it is the last segment
    if placeholders != ["{year}"] or rest[-1] != "{year}":
        return (False, level, source, "-".join([r for r in rest if not r.startswith("{")]))
    topic_segs = [r for r in rest[:-1] if not (r.startswith("{") and r.endswith("}"))]
    topic_slug = "-".join(topic_segs)  # may be "" (e.g. saipe)
    return (True, level, source, topic_slug)


def resolve_mirror_file(level, source, topic_slug):
    # INTENT: find the mirror parquet for (level, source, topic). Try prefix x
    #   {topic variants + alias}; accept first existing file that has a `year` column.
    prefixes = LEVEL_PREFIX.get(level, [])
    variants = []
    for base in [topic_slug, TOPIC_ALIAS.get(topic_slug, None),
                 TOPIC_ALIAS.get(f"{topic_slug}_scorecard", None) if source == "scorecard" else None]:
        if base is None:
            continue
        variants.append(base)
        variants.append(base.replace("-", "_"))
        variants.append(base.replace("_", "-"))
    # de-dup preserve order
    seen = set()
    variants = [v for v in variants if not (v in seen or seen.add(v))]
    src_dir = TREE_DIR / source
    for prefix in prefixes:
        for tv in variants:
            if tv == "":
                cand = f"{source}/{prefix}_{source}.parquet"
            else:
                cand = f"{source}/{prefix}_{source}_{tv}.parquet"
            fp = TREE_DIR / cand
            if fp.exists():
                try:
                    names = pl.scan_parquet(fp).collect_schema().names()
                except Exception:
                    continue
                if "year" in [n.lower() for n in names]:
                    return cand, [n.lower() for n in names]
    return None, None


def pick_key(level, file_names):
    prefs = KEY_BY_LEVEL.get(level, []) + ID_CANDIDATES
    for k in prefs:
        if k in file_names:
            return k
    return None


# --- Load ground-truth live inventory ---
inv = pl.read_parquet(IN_INV).filter(pl.col("status") == 200)
print(f"Loaded live inventory: {inv.height} routes (status==200)")

pairs = []
unmatched = []
disagg_skipped = 0
for r in inv.iter_rows(named=True):
    rt = r["route_template"]
    is_clean, level, source, topic = classify_route(rt)
    if not is_clean:
        disagg_skipped += 1
        continue
    mrel, fnames = resolve_mirror_file(level, source, topic)
    yrs = parse_years(r["years_available"])
    if mrel is None:
        unmatched.append({"route_template": rt, "level": level, "source": source,
                          "topic": topic, "years": f"{min(yrs) if yrs else '?'}-{max(yrs) if yrs else '?'}"})
        continue
    key = pick_key(level, fnames)
    mid = r["mid_year"]
    # sweep years: earliest, mid, most-recent (intersect availability), unique, <=3
    sweep = []
    if yrs:
        for cand in [yrs[0], mid if mid in yrs else None, yrs[-1]]:
            if cand is not None and cand not in sweep:
                sweep.append(cand)
    if not sweep and mid is not None:
        sweep = [mid]
    slice_year = mid if (mid in yrs) else (yrs[-1] if yrs else mid)
    pairs.append({
        "label": f"{source}_{(topic or 'base').replace('-', '_')}",
        "route_template": rt,
        "level": level, "source": source, "topic": topic,
        "mirror_rel": mrel, "key_col": key,
        "mid_year": mid, "live_count_mid": r["count"],
        "n_years_available": len(yrs),
        "year_min": yrs[0] if yrs else None, "year_max": yrs[-1] if yrs else None,
        "sweep_years": sweep, "slice_year": slice_year,
        "n_live_fields": len(r["fields"]) if r["fields"] is not None else None,
    })

pdf = pl.from_dicts(pairs)
# Guard against accidental dup mirror files (two routes -> same file): keep first, note dups
dup_files = (pdf.group_by("mirror_rel").len().filter(pl.col("len") > 1))
print(f"\nCLEAN 1:1 matched pairs: {pdf.height}")
print(f"disagg/multi-placeholder routes skipped: {disagg_skipped}")
print(f"UNMATCHED clean-1:1 routes (rename not in alias table): {len(unmatched)}")

# --- Validate ---
assert pdf.height > 0, "No pairs matched — check alias table / tree path"
assert pdf["mirror_rel"].null_count() == 0, "Null mirror_rel among matched pairs"
n_no_key = pdf.filter(pl.col("key_col").is_null()).height
print(f"pairs with no resolvable entity key (slice will be count-only): {n_no_key}")

# total planned count comparisons = sum of sweep-year list lengths
total_counts = int(pdf.select(pl.col("sweep_years").list.len().sum()).item())
print(f"planned count comparisons (sum of sweep years): {total_counts}")
print(f"planned value slices (one per pair with a key): {pdf.filter(pl.col('key_col').is_not_null()).height}")

# --- Save ---
pdf.write_parquet(OUT_PAIRS)
print(f"\nSaved pairs -> {OUT_PAIRS}")

pl.Config.set_tbl_rows(80)
pl.Config.set_fmt_str_lengths(70)
pl.Config.set_tbl_width_chars(300)
print("\n=== MATCHED PAIRS ===")
print(pdf.select("label", "level", "source", "mirror_rel", "key_col", "sweep_years", "slice_year", "live_count_mid"))

if dup_files.height:
    print("\n=== NOTE: mirror files matched by >1 route (dedupe review) ===")
    print(dup_files)

print("\n=== UNMATCHED CLEAN-1:1 ROUTES (verbatim; need alias) ===")
for u in unmatched:
    print(f"  {u['route_template']}  [level={u['level']} source={u['source']} topic={u['topic']} yrs={u['years']}]")

print("\nPAIR SELECTION COMPLETE")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-08 19:26:32
# Command: python3 /daaf/scripts/mirror_maintenance/49_laneB-pair-selection.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# Loaded live inventory: 129 routes (status==200)
# 
# CLEAN 1:1 matched pairs: 37
# disagg/multi-placeholder routes skipped: 64
# UNMATCHED clean-1:1 routes (rename not in alias table): 28
# pairs with no resolvable entity key (slice will be count-only): 0
# planned count comparisons (sum of sweep years): 108
# planned value slices (one per pair with a key): 37
# 
# Saved pairs -> /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_urban-fidelity/49_laneB_pairs.parquet
# 
# === MATCHED PAIRS ===
# shape: (37, 8)
# ┌─────────────────────────────────────────┬────────────────────┬───────────┬────────────────────────────────────────────────────────────┬─────────┬────────────────────┬────────────┬────────────────┐
# │ label                                   ┆ level              ┆ source    ┆ mirror_rel                                                 ┆ key_col ┆ sweep_years        ┆ slice_year ┆ live_count_mid │
# │ ---                                     ┆ ---                ┆ ---       ┆ ---                                                        ┆ ---     ┆ ---                ┆ ---        ┆ ---            │
# │ str                                     ┆ str                ┆ str       ┆ str                                                        ┆ str     ┆ list[i64]          ┆ i64        ┆ i64            │
# ╞═════════════════════════════════════════╪════════════════════╪═══════════╪════════════════════════════════════════════════════════════╪═════════╪════════════════════╪════════════╪════════════════╡
# │ ipeds_directory                         ┆ college-university ┆ ipeds     ┆ ipeds/colleges_ipeds_directory.parquet                     ┆ unitid  ┆ [1980, 2004, 2024] ┆ 2004       ┆ 6916           │
# │ ccd_directory                           ┆ schools            ┆ ccd       ┆ ccd/schools_ccd_directory.parquet                          ┆ ncessch ┆ [1986, 2005, 2024] ┆ 2005       ┆ 102454         │
# │ ipeds_institutional_characteristics     ┆ college-university ┆ ipeds     ┆ ipeds/colleges_ipeds_institutional-characteristics.parquet ┆ unitid  ┆ [1980, 2004, 2024] ┆ 2004       ┆ 6916           │
# │ ipeds_admissions_enrollment             ┆ college-university ┆ ipeds     ┆ ipeds/colleges_ipeds_admissions-enrollment.parquet         ┆ unitid  ┆ [2001, 2013, 2024] ┆ 2013       ┆ 6780           │
# │ ipeds_admissions_requirements           ┆ college-university ┆ ipeds     ┆ ipeds/colleges_ipeds_admissions-requirements.parquet       ┆ unitid  ┆ [1990, 2006, 2022] ┆ 2006       ┆ 7052           │
# │ ipeds_academic_year_tuition             ┆ college-university ┆ ipeds     ┆ ipeds/colleges_ipeds_ay_tuition_fees.parquet               ┆ unitid  ┆ [1986, 2005, 2023] ┆ 2005       ┆ 18504          │
# │ ccd_finance                             ┆ school-districts   ┆ ccd       ┆ ccd/districts_ccd_finance.parquet                          ┆ leaid   ┆ [1991, 2007, 2020] ┆ 2007       ┆ 16453          │
# │ ipeds_academic_year_room_board_other    ┆ college-university ┆ ipeds     ┆ ipeds/colleges_ipeds_ay_room_board_other.parquet           ┆ unitid  ┆ [1999, 2011, 2023] ┆ 2011       ┆ 12881          │
# │ saipe_base                              ┆ school-districts   ┆ saipe     ┆ saipe/districts_saipe.parquet                              ┆ leaid   ┆ [1995, 2011, 2024] ┆ 2011       ┆ 13545          │
# │ ipeds_fall_retention                    ┆ college-university ┆ ipeds     ┆ ipeds/colleges_ipeds_fall-retention.parquet                ┆ unitid  ┆ [2003, 2014, 2024] ┆ 2014       ┆ 14100          │
# │ ipeds_finance                           ┆ college-university ┆ ipeds     ┆ ipeds/colleges_ipeds_finance.parquet                       ┆ unitid  ┆ [1979, 2000, 2017] ┆ 2000       ┆ 9769           │
# │ ipeds_student_faculty_ratio             ┆ college-university ┆ ipeds     ┆ ipeds/colleges_ipeds_student-faculty-ratio.parquet         ┆ unitid  ┆ [2009, 2017, 2024] ┆ 2017       ┆ 6371           │
# │ ipeds_sfa_grants_and_net_price          ┆ college-university ┆ ipeds     ┆ ipeds/colleges_ipeds_sfa_grants_and_net_price.parquet      ┆ unitid  ┆ [2008, 2015, 2021] ┆ 2015       ┆ 42215          │
# │ ipeds_sfa_by_living_arrangement         ┆ college-university ┆ ipeds     ┆ ipeds/colleges_ipeds_sfa_by_living_arrangement.parquet     ┆ unitid  ┆ [2008, 2015, 2021] ┆ 2015       ┆ 51988          │
# │ ipeds_sfa_by_tuition_type               ┆ college-university ┆ ipeds     ┆ ipeds/colleges_ipeds_sfa_by_tuition_type.parquet           ┆ unitid  ┆ [1999, 2010, 2021] ┆ 2010       ┆ 14985          │
# │ ipeds_sfa_ftft                          ┆ college-university ┆ ipeds     ┆ ipeds/colleges_ipeds_sfa_ftft.parquet                      ┆ unitid  ┆ [1999, 2010, 2021] ┆ 2010       ┆ 75284          │
# │ ipeds_grad_rates                        ┆ college-university ┆ ipeds     ┆ ipeds/colleges_ipeds_grad-rates.parquet                    ┆ unitid  ┆ [1996, 2010, 2023] ┆ 2010       ┆ 233463         │
# │ ipeds_grad_rates_200pct                 ┆ college-university ┆ ipeds     ┆ ipeds/colleges_ipeds_grad-rates-200pct.parquet             ┆ unitid  ┆ [2007, 2015, 2023] ┆ 2015       ┆ 5652           │
# │ ipeds_grad_rates_pell                   ┆ college-university ┆ ipeds     ┆ ipeds/colleges_ipeds_grad-rates-pell.parquet               ┆ unitid  ┆ [2015, 2019, 2023] ┆ 2019       ┆ 40300          │
# │ ipeds_outcome_measures                  ┆ college-university ┆ ipeds     ┆ ipeds/colleges_ipeds_outcome-measures.parquet              ┆ unitid  ┆ [2015, 2018, 2021] ┆ 2018       ┆ 89756          │
# │ ipeds_completers                        ┆ college-university ┆ ipeds     ┆ ipeds/colleges_ipeds_completers.parquet                    ┆ unitid  ┆ [2011, 2016, 2021] ┆ 2016       ┆ 202620         │
# │ ipeds_academic_libraries                ┆ college-university ┆ ipeds     ┆ ipeds/colleges_ipeds_academic_libraries.parquet            ┆ unitid  ┆ [2013, 2018, 2023] ┆ 2018       ┆ 3834           │
# │ scorecard_institutional_characteristics ┆ college-university ┆ scorecard ┆ scorecard/colleges_scorecard_inst_characteristics.parquet  ┆ unitid  ┆ [1996, 2008, 2020] ┆ 2008       ┆ 7055           │
# │ scorecard_earnings                      ┆ college-university ┆ scorecard ┆ scorecard/colleges_scorecard_earnings.parquet              ┆ unitid  ┆ [2003, 2009, 2018] ┆ 2009       ┆ 19661          │
# │ scorecard_default                       ┆ college-university ┆ scorecard ┆ scorecard/colleges_scorecard_repayment_fsa.parquet         ┆ unitid  ┆ [1996, 2008, 2020] ┆ 2008       ┆ 6574           │
# │ scorecard_repayment                     ┆ college-university ┆ scorecard ┆ scorecard/colleges_scorecard_repayment_nslds.parquet       ┆ unitid  ┆ [2007, 2012, 2016] ┆ 2012       ┆ 20191          │
# │ crdc_offenses                           ┆ schools            ┆ crdc      ┆ crdc/schools_crdc_offenses.parquet                         ┆ ncessch ┆ [2015, 2020, 2021] ┆ 2020       ┆ 97575          │
# │ fsa_financial_responsibility            ┆ college-university ┆ fsa       ┆ fsa/colleges_fsa_composite_scores.parquet                  ┆ unitid  ┆ [2006, 2011, 2016] ┆ 2011       ┆ 3401           │
# │ fsa_grants                              ┆ college-university ┆ fsa       ┆ fsa/colleges_fsa_grants.parquet                            ┆ unitid  ┆ [1999, 2010, 2021] ┆ 2010       ┆ 27665          │
# │ crdc_credit_recovery                    ┆ schools            ┆ crdc      ┆ crdc/schools_crdc_credit_recovery.parquet                  ┆ ncessch ┆ [2015, 2017]       ┆ 2017       ┆ 97632          │
# │ fsa_loans                               ┆ college-university ┆ fsa       ┆ fsa/colleges_fsa_loans.parquet                             ┆ unitid  ┆ [1999, 2010, 2021] ┆ 2010       ┆ 73724          │
# │ fsa_campus_based_volume                 ┆ college-university ┆ fsa       ┆ fsa/colleges_fsa_campus_based_volume.parquet               ┆ unitid  ┆ [2001, 2011, 2021] ┆ 2011       ┆ 12318          │
# │ fsa_90_10_revenue_percentages           ┆ college-university ┆ fsa       ┆ fsa/colleges_fsa_90_10_revenue_percentages.parquet         ┆ unitid  ┆ [2014, 2018, 2021] ┆ 2018       ┆ 1671           │
# │ crdc_offerings                          ┆ schools            ┆ crdc      ┆ crdc/schools_crdc_offerings.parquet                        ┆ ncessch ┆ [2011, 2017, 2021] ┆ 2017       ┆ 97632          │
# │ crdc_covid_indicators                   ┆ schools            ┆ crdc      ┆ crdc/schools_crdc_covid_indicators.parquet                 ┆ ncessch ┆ [2020, 2021]       ┆ 2021       ┆ 98010          │
# │ crdc_internet_access                    ┆ schools            ┆ crdc      ┆ crdc/schools_crdc_internet_access.parquet                  ┆ ncessch ┆ [2020, 2021]       ┆ 2021       ┆ 98010          │
# │ meps_base                               ┆ schools            ┆ meps      ┆ meps/schools_meps.parquet                                  ┆ ncessch ┆ [2009, 2016, 2022] ┆ 2016       ┆ 96153          │
# └─────────────────────────────────────────┴────────────────────┴───────────┴────────────────────────────────────────────────────────────┴─────────┴────────────────────┴────────────┴────────────────┘
# 
# === UNMATCHED CLEAN-1:1 ROUTES (verbatim; need alias) ===
#   /api/v1/school-districts/ccd/directory/{year}/  [level=school-districts source=ccd topic=directory yrs=1986-2024]
#   /api/v1/college-university/ipeds/academic-year-tuition-prof-program/{year}/  [level=college-university source=ipeds topic=academic-year-tuition-prof-program yrs=1986-2023]
#   /api/v1/schools/crdc/directory/{year}/  [level=schools source=crdc topic=directory yrs=2011-2021]
#   /api/v1/college-university/ipeds/program-year-tuition-cip/{year}/  [level=college-university source=ipeds topic=program-year-tuition-cip yrs=1987-2023]
#   /api/v1/college-university/ipeds/program-year-room-board-other/{year}/  [level=college-university source=ipeds topic=program-year-room-board-other yrs=1999-2023]
#   /api/v1/school-districts/edfacts/grad-rates/{year}/  [level=school-districts source=edfacts topic=grad-rates yrs=2010-2019]
#   /api/v1/schools/crdc/discipline-instances/{year}/  [level=schools source=crdc topic=discipline-instances yrs=2015-2021]
#   /api/v1/college-university/ipeds/sfa-all-undergraduates/{year}/  [level=college-university source=ipeds topic=sfa-all-undergraduates yrs=2007-2021]
#   /api/v1/college-university/ipeds/completions-cip-2/{year}/  [level=college-university source=ipeds topic=completions-cip-2 yrs=1991-2022]
#   /api/v1/college-university/ipeds/completions-cip-6/{year}/  [level=college-university source=ipeds topic=completions-cip-6 yrs=1983-2023]
#   /api/v1/college-university/ipeds/salaries-instructional-staff/{year}/  [level=college-university source=ipeds topic=salaries-instructional-staff yrs=1980-2024]
#   /api/v1/college-university/ipeds/salaries-noninstructional-staff/{year}/  [level=college-university source=ipeds topic=salaries-noninstructional-staff yrs=2012-2024]
#   /api/v1/schools/crdc/teachers-staff/{year}/  [level=schools source=crdc topic=teachers-staff yrs=2011-2021]
#   /api/v1/college-university/nhgis/census-1990/{year}/  [level=college-university source=nhgis topic=census-1990 yrs=1980-2023]
#   /api/v1/college-university/nhgis/census-2000/{year}/  [level=college-university source=nhgis topic=census-2000 yrs=1980-2023]
#   /api/v1/college-university/nhgis/census-2010/{year}/  [level=college-university source=nhgis topic=census-2010 yrs=1980-2023]
#   /api/v1/college-university/nhgis/census-2020/{year}/  [level=college-university source=nhgis topic=census-2020 yrs=1980-2023]
#   /api/v1/college-university/nacubo/endowments/{year}/  [level=college-university source=nacubo topic=endowments yrs=2012-2022]
#   /api/v1/college-university/nccs/990-forms/{year}/  [level=college-university source=nccs topic=990-forms yrs=1993-2016]
#   /api/v1/schools/crdc/school-finance/{year}/  [level=schools source=crdc topic=school-finance yrs=2011-2017]
#   /api/v1/college-university/eada/institutional-characteristics/{year}/  [level=college-university source=eada topic=institutional-characteristics yrs=2002-2021]
#   /api/v1/college-university/campus-crime/hate-crimes/{year}/  [level=college-university source=campus-crime topic=hate-crimes yrs=2005-2021]
#   /api/v1/college-university/pseo/earnings-and-flows/{year}/  [level=college-university source=pseo topic=earnings-and-flows yrs=2001-2021]
#   /api/v1/schools/edfacts/grad-rates/{year}/  [level=schools source=edfacts topic=grad-rates yrs=2010-2019]
#   /api/v1/schools/nhgis/census-1990/{year}/  [level=schools source=nhgis topic=census-1990 yrs=1986-2023]
#   /api/v1/schools/nhgis/census-2000/{year}/  [level=schools source=nhgis topic=census-2000 yrs=1986-2023]
#   /api/v1/schools/nhgis/census-2010/{year}/  [level=schools source=nhgis topic=census-2010 yrs=1986-2023]
#   /api/v1/schools/nhgis/census-2020/{year}/  [level=schools source=nhgis topic=census-2020 yrs=1986-2023]
# 
# PAIR SELECTION COMPLETE
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
