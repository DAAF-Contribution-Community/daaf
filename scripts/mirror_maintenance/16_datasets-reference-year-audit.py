# --- Config ---
# INTENT: Re-prove every datasets-reference.md year range that was UPDATED this
#         session (per `git diff`) against the LIVE pinned mirror, plus verify the
#         14 per-source authoritative ranges on their anchor files.
# REASONING: The prior session verified against LOCAL build artifacts; the mirror is
#            now live at brhkim/education_data_portal_mirror_2026q3. Adversarial
#            stance: fetch the actual `year` column from live content and compare to
#            the documented min/max. Skill file under test:
#            .claude/skills/education-data-query/references/datasets-reference.md
# ASSUMES: read-only public repo pinned at commit 0ad00ce...; column-projection over
#          HTTP (scan_parquet.select("year")) never downloads whole files.
import polars as pl
import time

PIN = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
BASE = f"https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/{PIN}"

# --- SINGLE-FILE probes: (label, rel_path, doc_min, doc_max, origin) ---
# origin: CHANGED = row edited this session; ANCHOR = per-source authoritative range.
single_probes = [
    # CHANGED single-file rows (datasets-reference.md diff)
    ("SAIPE Poverty",                 "saipe/districts_saipe",                        1995, 2024, "CHANGED+ANCHOR(saipe)"),
    ("IPEDS Graduation Rates(150%)",  "ipeds/colleges_ipeds_grad-rates",              1996, 2022, "CHANGED"),
    ("IPEDS Academic Libraries",      "ipeds/colleges_ipeds_academic_libraries",      2013, 2023, "CHANGED"),
    ("IPEDS AY Room Board Other",     "ipeds/colleges_ipeds_ay_room_board_other",     1999, 2023, "CHANGED"),
    ("IPEDS AY Tuition and Fees",     "ipeds/colleges_ipeds_ay_tuition_fees",         1986, 2023, "CHANGED"),
    ("IPEDS AY Tuition FirstProf",    "ipeds/colleges_ipeds_ay_tuition_firstprof",    1986, 2023, "CHANGED"),
    ("IPEDS Completers",              "ipeds/colleges_ipeds_completers",              2011, 2021, "CHANGED"),
    ("IPEDS Fall Enroll Residence",   "ipeds/colleges_ipeds_fall-res",                1986, 2024, "CHANGED"),
    ("IPEDS Fall Retention",          "ipeds/colleges_ipeds_fall-retention",          2003, 2024, "CHANGED"),
    ("IPEDS Grad Rates 200pct",       "ipeds/colleges_ipeds_grad-rates-200pct",       2007, 2023, "CHANGED"),
    ("IPEDS Grad Rates Pell",         "ipeds/colleges_ipeds_grad-rates-pell",         2015, 2023, "CHANGED"),
    ("IPEDS Inst Characteristics",    "ipeds/colleges_ipeds_institutional-characteristics", 1980, 2024, "CHANGED"),
    ("IPEDS Instr Staff Salaries",    "ipeds/colleges_ipeds_salaries_is",             1980, 2024, "CHANGED"),
    ("IPEDS Noninstr Staff Salaries", "ipeds/colleges_ipeds_salaries_nis",            2012, 2024, "CHANGED"),
    ("IPEDS PY Room Board Other",     "ipeds/colleges_ipeds_py_room_board_other",     1999, 2023, "CHANGED"),
    ("IPEDS PY Tuition CIP",          "ipeds/colleges_ipeds_py_tuition_cip",          1987, 2023, "CHANGED"),
    ("IPEDS Student-Faculty Ratio",   "ipeds/colleges_ipeds_student-faculty-ratio",   2009, 2024, "CHANGED"),
    # ANCHOR-only single-file per-source authoritative ranges
    ("CSAFETY Hate Crimes",           "csafety/colleges_csafety_hate_crimes",         2005, 2021, "ANCHOR(csafety)"),
    ("EADA Inst Characteristics",     "eada/colleges_eada_inst_characteristics",      2002, 2021, "ANCHOR(eada)"),
    ("FSA Grants",                    "fsa/colleges_fsa_grants",                      1999, 2021, "ANCHOR(fsa)"),
    ("IPEDS Directory",               "ipeds/colleges_ipeds_directory",               1979, 2024, "ANCHOR(ipeds)"),
    ("MEPS Poverty",                  "meps/schools_meps",                            2009, 2022, "ANCHOR(meps)"),
    ("NACUBO Endowments",             "nacubo/colleges_nacubo_endow",                 2012, 2022, "ANCHOR(nacubo)"),
    ("NCCS 990",                      "nccs/colleges_nccs_all",                       1993, 2016, "ANCHOR(nccs)"),
    ("NHGIS colleges geog 2020",      "nhgis/colleges_nhgis_geog_2020",               1980, 2023, "ANCHOR(nhgis)"),
    ("Scorecard Default",             "scorecard/colleges_scorecard_repayment_fsa",   1996, 2020, "ANCHOR(scorecard)"),
]

# --- YEARLY boundary probes: (label, path_template, boundary_years, origin) ---
# For yearly datasets the documented range is encoded in filenames; we prove content
# by scanning the boundary-year files' `year` columns (expect each == its year).
yearly_probes = [
    ("CCD District Enrollment", "ccd/schools_ccd_lea_enrollment_{y}", [1986, 2024], "CHANGED+ANCHOR(ccd)"),
    ("CCD School Enrollment",   "ccd/schools_ccd_enrollment_{y}",     [1986, 2024], "CHANGED+ANCHOR(ccd)"),
    ("IPEDS Completions 2dig",  "ipeds/colleges_ipeds_completions-2digcip_{y}", [1991, 2023], "CHANGED"),
    ("IPEDS Completions 6dig",  "ipeds/colleges_ipeds_completions-6digcip_{y}", [1983, 2023], "CHANGED"),
    ("IPEDS Fall Enroll Age",   "ipeds/colleges_ipeds_fall-enrollment-age_{y}", [1991, 2024], "CHANGED"),
    ("IPEDS Fall Enroll Race",  "ipeds/colleges_ipeds_fall-enrollment-race_{y}", [1986, 2024], "CHANGED"),
    ("CRDC Enrollment (min)",   "crdc/schools_crdc_enrollment_k12_{y}", [2011], "ANCHOR(crdc:min)"),
    ("CRDC ChronicAbsent (max)","crdc/schools_crdc_chronic_absenteeism_{y}", [2022], "ANCHOR(crdc:max)"),
    ("EDFacts Assessments",     "edfacts/schools_edfacts_assessments_{y}", [2009, 2020], "ANCHOR(edfacts)"),
    ("PSEO Earnings/Flows",     "pseo/colleges_pseo_{y}", [2001, 2021], "ANCHOR(pseo)"),
]

# --- Probe: single-file year ranges ---
results = []
for label, rel, dmin, dmax, origin in single_probes:
    url = f"{BASE}/{rel}.parquet"
    obs_min = obs_max = ndist = None
    err = None
    for attempt in range(3):
        try:
            lf = pl.scan_parquet(url)
            # INTENT: project ONLY the year column over HTTP — never download the file.
            yrs = lf.select("year").unique().collect()["year"].drop_nulls().to_list()
            obs_min, obs_max, ndist = int(min(yrs)), int(max(yrs)), len(yrs)
            break
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:160]}"
            time.sleep(3)
    if obs_min is None:
        verdict = "UNTESTABLE"
    else:
        verdict = "VERIFIED" if (obs_min == dmin and obs_max == dmax) else "CONTRADICTED"
    results.append({"kind": "single", "label": label, "origin": origin,
                    "doc": f"{dmin}-{dmax}", "obs": f"{obs_min}-{obs_max}" if obs_min else "ERR",
                    "ndistinct": ndist, "verdict": verdict, "err": err})
    print(f"[{verdict:12}] {label:32} doc={dmin}-{dmax}  obs={obs_min}-{obs_max}  ndist={ndist}  ({origin})")
    if err and obs_min is None:
        print(f"             ERR: {err}")

# --- Probe: yearly boundary files ---
for label, tmpl, byears, origin in yearly_probes:
    for y in byears:
        url = f"{BASE}/{tmpl.format(y=y)}.parquet"
        obs = None
        err = None
        for attempt in range(3):
            try:
                lf = pl.scan_parquet(url)
                vals = lf.select("year").unique().collect()["year"].drop_nulls().to_list()
                obs = sorted(int(v) for v in vals)
                break
            except Exception as e:
                err = f"{type(e).__name__}: {str(e)[:160]}"
                time.sleep(3)
        if obs is None:
            verdict = "UNTESTABLE"
        else:
            # ASSUMES: a per-year file's year column should contain exactly its filename year.
            verdict = "VERIFIED" if obs == [y] else ("CONTRADICTED" if y not in obs else "VERIFIED*")
        results.append({"kind": "yearly", "label": f"{label} [{y}]", "origin": origin,
                        "doc": str(y), "obs": str(obs) if obs is not None else "ERR",
                        "ndistinct": (len(obs) if obs else None), "verdict": verdict, "err": err})
        print(f"[{verdict:12}] {label:26} file-year={y}  obs-years={obs}  ({origin})")
        if err and obs is None:
            print(f"             ERR: {err}")

# --- Validate / Summary ---
res_df = pl.DataFrame(results)
print("\n--- VERDICT TALLY ---")
print(res_df.group_by("verdict").len().sort("verdict"))
contradicted = res_df.filter(pl.col("verdict") == "CONTRADICTED")
untestable = res_df.filter(pl.col("verdict") == "UNTESTABLE")
print(f"\nCONTRADICTED: {contradicted.height}")
if contradicted.height:
    print(contradicted.select("label", "origin", "doc", "obs"))
print(f"UNTESTABLE: {untestable.height}")
if untestable.height:
    print(untestable.select("label", "origin", "err"))

# --- Save ---
OUT = "/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_skill-spotcheck/16_year-audit-results.parquet"
res_df.write_parquet(OUT)
print(f"\nSaved: {OUT}  ({res_df.height} probes)")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 13:08:02
# Command: python3 /daaf/scripts/mirror_maintenance/16_datasets-reference-year-audit.py
# Duration: 57s
# Exit code: 0
#
# --- STDOUT ---
# [VERIFIED    ] SAIPE Poverty                    doc=1995-2024  obs=1995-2024  ndist=28  (CHANGED+ANCHOR(saipe))
# [CONTRADICTED] IPEDS Graduation Rates(150%)     doc=1996-2022  obs=1996-2023  ndist=28  (CHANGED)
# [VERIFIED    ] IPEDS Academic Libraries         doc=2013-2023  obs=2013-2023  ndist=11  (CHANGED)
# [VERIFIED    ] IPEDS AY Room Board Other        doc=1999-2023  obs=1999-2023  ndist=25  (CHANGED)
# [VERIFIED    ] IPEDS AY Tuition and Fees        doc=1986-2023  obs=1986-2023  ndist=38  (CHANGED)
# [VERIFIED    ] IPEDS AY Tuition FirstProf       doc=1986-2023  obs=1986-2023  ndist=37  (CHANGED)
# [VERIFIED    ] IPEDS Completers                 doc=2011-2021  obs=2011-2021  ndist=11  (CHANGED)
# [VERIFIED    ] IPEDS Fall Enroll Residence      doc=1986-2024  obs=1986-2024  ndist=31  (CHANGED)
# [VERIFIED    ] IPEDS Fall Retention             doc=2003-2024  obs=2003-2024  ndist=22  (CHANGED)
# [VERIFIED    ] IPEDS Grad Rates 200pct          doc=2007-2023  obs=2007-2023  ndist=17  (CHANGED)
# [VERIFIED    ] IPEDS Grad Rates Pell            doc=2015-2023  obs=2015-2023  ndist=9  (CHANGED)
# [VERIFIED    ] IPEDS Inst Characteristics       doc=1980-2024  obs=1980-2024  ndist=42  (CHANGED)
# [VERIFIED    ] IPEDS Instr Staff Salaries       doc=1980-2024  obs=1980-2024  ndist=39  (CHANGED)
# [VERIFIED    ] IPEDS Noninstr Staff Salaries    doc=2012-2024  obs=2012-2024  ndist=13  (CHANGED)
# [VERIFIED    ] IPEDS PY Room Board Other        doc=1999-2023  obs=1999-2023  ndist=25  (CHANGED)
# [VERIFIED    ] IPEDS PY Tuition CIP             doc=1987-2023  obs=1987-2023  ndist=37  (CHANGED)
# [VERIFIED    ] IPEDS Student-Faculty Ratio      doc=2009-2024  obs=2009-2024  ndist=16  (CHANGED)
# [VERIFIED    ] CSAFETY Hate Crimes              doc=2005-2021  obs=2005-2021  ndist=17  (ANCHOR(csafety))
# [VERIFIED    ] EADA Inst Characteristics        doc=2002-2021  obs=2002-2021  ndist=20  (ANCHOR(eada))
# [VERIFIED    ] FSA Grants                       doc=1999-2021  obs=1999-2021  ndist=23  (ANCHOR(fsa))
# [CONTRADICTED] IPEDS Directory                  doc=1979-2024  obs=1980-2024  ndist=42  (ANCHOR(ipeds))
# [VERIFIED    ] MEPS Poverty                     doc=2009-2022  obs=2009-2022  ndist=14  (ANCHOR(meps))
# [VERIFIED    ] NACUBO Endowments                doc=2012-2022  obs=2012-2022  ndist=11  (ANCHOR(nacubo))
# [VERIFIED    ] NCCS 990                         doc=1993-2016  obs=1993-2016  ndist=24  (ANCHOR(nccs))
# [VERIFIED    ] NHGIS colleges geog 2020         doc=1980-2023  obs=1980-2023  ndist=41  (ANCHOR(nhgis))
# [VERIFIED    ] Scorecard Default                doc=1996-2020  obs=1996-2020  ndist=25  (ANCHOR(scorecard))
# [VERIFIED    ] CCD District Enrollment    file-year=1986  obs-years=[1986]  (CHANGED+ANCHOR(ccd))
# [VERIFIED    ] CCD District Enrollment    file-year=2024  obs-years=[2024]  (CHANGED+ANCHOR(ccd))
# [VERIFIED    ] CCD School Enrollment      file-year=1986  obs-years=[1986]  (CHANGED+ANCHOR(ccd))
# [VERIFIED    ] CCD School Enrollment      file-year=2024  obs-years=[2024]  (CHANGED+ANCHOR(ccd))
# [VERIFIED    ] IPEDS Completions 2dig     file-year=1991  obs-years=[1991]  (CHANGED)
# [VERIFIED    ] IPEDS Completions 2dig     file-year=2023  obs-years=[2023]  (CHANGED)
# [VERIFIED    ] IPEDS Completions 6dig     file-year=1983  obs-years=[1983]  (CHANGED)
# [VERIFIED    ] IPEDS Completions 6dig     file-year=2023  obs-years=[2023]  (CHANGED)
# [VERIFIED    ] IPEDS Fall Enroll Age      file-year=1991  obs-years=[1991]  (CHANGED)
# [VERIFIED    ] IPEDS Fall Enroll Age      file-year=2024  obs-years=[2024]  (CHANGED)
# [VERIFIED    ] IPEDS Fall Enroll Race     file-year=1986  obs-years=[1986]  (CHANGED)
# [VERIFIED    ] IPEDS Fall Enroll Race     file-year=2024  obs-years=[2024]  (CHANGED)
# [VERIFIED    ] CRDC Enrollment (min)      file-year=2011  obs-years=[2011]  (ANCHOR(crdc:min))
# [VERIFIED    ] CRDC ChronicAbsent (max)   file-year=2022  obs-years=[2022]  (ANCHOR(crdc:max))
# [VERIFIED    ] EDFacts Assessments        file-year=2009  obs-years=[2009]  (ANCHOR(edfacts))
# [VERIFIED    ] EDFacts Assessments        file-year=2020  obs-years=[2020]  (ANCHOR(edfacts))
# [VERIFIED    ] PSEO Earnings/Flows        file-year=2001  obs-years=[2001]  (ANCHOR(pseo))
# [VERIFIED    ] PSEO Earnings/Flows        file-year=2021  obs-years=[2021]  (ANCHOR(pseo))
# 
# --- VERDICT TALLY ---
# shape: (2, 2)
# ┌──────────────┬─────┐
# │ verdict      ┆ len │
# │ ---          ┆ --- │
# │ str          ┆ u32 │
# ╞══════════════╪═════╡
# │ CONTRADICTED ┆ 2   │
# │ VERIFIED     ┆ 42  │
# └──────────────┴─────┘
# 
# CONTRADICTED: 2
# shape: (2, 4)
# ┌──────────────────────────────┬───────────────┬───────────┬───────────┐
# │ label                        ┆ origin        ┆ doc       ┆ obs       │
# │ ---                          ┆ ---           ┆ ---       ┆ ---       │
# │ str                          ┆ str           ┆ str       ┆ str       │
# ╞══════════════════════════════╪═══════════════╪═══════════╪═══════════╡
# │ IPEDS Graduation Rates(150%) ┆ CHANGED       ┆ 1996-2022 ┆ 1996-2023 │
# │ IPEDS Directory              ┆ ANCHOR(ipeds) ┆ 1979-2024 ┆ 1980-2024 │
# └──────────────────────────────┴───────────────┴───────────┴───────────┘
# UNTESTABLE: 0
# 
# Saved: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_skill-spotcheck/16_year-audit-results.parquet  (44 probes)
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
