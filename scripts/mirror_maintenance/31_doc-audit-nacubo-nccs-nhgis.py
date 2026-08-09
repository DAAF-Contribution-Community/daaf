# --- Config ---
# INTENT: Verify documented column/dtype/null-count/row-count/scale claims for NACUBO,
#         NCCS, and NHGIS against the pinned mirror; plus a codebook .xls readability probe.
# REASONING: NACUBO "7 columns only" + null-count table, NCCS "161 columns", NHGIS
#            "47 vs 38 col" schema-difference and per-entity dtype claims are all data-testable.
# ASSUMES: pinned public repo; polars scan_parquet over HTTPS. .xls read attempted read-only.
# Skills under test: education-data-source-{nacubo,nccs,nhgis}/SKILL.md.
import polars as pl

PIN = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
BASE = f"https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/{PIN}"

def schema(rel): return dict(pl.scan_parquet(f"{BASE}/{rel}.parquet").collect_schema())
def dtype(rel, col): return str(schema(rel).get(col))
def nrows(rel): return pl.scan_parquet(f"{BASE}/{rel}.parquet").select(pl.len()).collect().item()
def probe(label, fn):
    try: print(f"[{label}] {fn()}")
    except Exception as e: print(f"[{label}] ERROR {type(e).__name__}: {str(e)[:130]}")

# ============ NACUBO ============
print("===== NACUBO =====")
NB = "nacubo/colleges_nacubo_endow"
def nacubo_cols():
    doc = ["year","unitid","inst_name_nacubo","fips","endow_total","endow_per_fte","endow_chg_mktval"]
    sc = schema(NB)
    act = list(sc.keys())
    return f"n_cols={len(act)} (claim EXACTLY 7); cols={act}; documented-not-present={sorted(set(doc)-set(act))}; extra={sorted(set(act)-set(doc))}"
probe("7-columns-only claim", nacubo_cols)
probe("dtypes", lambda: {k: str(v) for k, v in schema(NB).items()})
def nacubo_nulls():
    # claim: fips=1, endow_per_fte=1260, endow_chg_mktval=3972, others=0
    nc = pl.scan_parquet(f"{BASE}/{NB}.parquet").select(pl.all().null_count()).collect()
    return {c: nc[c][0] for c in nc.columns}
probe("null-counts (claim fips=1 per_fte=1260 chg=3972 rest=0)", nacubo_nulls)
probe("year range (claim 2012-2022)", lambda: (lambda s: f"min={s['mn'][0]} max={s['mx'][0]}")(pl.scan_parquet(f"{BASE}/{NB}.parquet").select(pl.col('year').min().alias('mn'), pl.col('year').max().alias('mx')).collect()))
probe("endow_chg_mktval scale (claim decimal fraction ~ -1..1, NOT 0-100)", lambda: (lambda s: f"min={s['mn'][0]} max={s['mx'][0]}")(pl.scan_parquet(f"{BASE}/{NB}.parquet").select(pl.col('endow_chg_mktval').min().alias('mn'), pl.col('endow_chg_mktval').max().alias('mx')).collect()))
probe("no -1/-2/-3 sentinels in endow_total (claim null-only missing)", lambda: [c for c in (-1,-2,-3) if pl.scan_parquet(f"{BASE}/{NB}.parquet").filter(pl.col('endow_total')==c).select(pl.len()).collect().item() > 0])

# ============ NCCS ============
print("\n===== NCCS =====")
NC = "nccs/colleges_nccs_all"
probe("161-columns claim", lambda: f"n_cols={len(schema(NC))} (claim 161); rows={nrows(NC)} (claim ~30K)")
def nccs_mapcols():
    doc = ["year","fiscal_year","unitid","ein","fips","inst_name_nccs","mult_ein_flag","contributions_total",
           "prog_serv_rev","revenue_total","expenses_total","total_assets_eoy","net_assets_eoy","compensation_officers","salaries_other"]
    sc = schema(NC)
    return f"documented-map-cols not present: {[c for c in doc if c not in sc]}; ein_dtype={sc.get('ein')} fips_dtype={sc.get('fips')} year_dtype={sc.get('year')}"
probe("Portal name-mapping cols present + id dtypes", nccs_mapcols)
probe("NTEE absent (claim: no NTEE in Portal)", lambda: [c for c in schema(NC) if "ntee" in c.lower()])
probe("year range (claim 1993-2016)", lambda: (lambda s: f"min={s['mn'][0]} max={s['mx'][0]}")(pl.scan_parquet(f"{BASE}/{NC}.parquet").select(pl.col('year').min().alias('mn'), pl.col('year').max().alias('mx')).collect()))
probe("fiscal_year range (claim 1994-2017)", lambda: (lambda s: f"min={s['mn'][0]} max={s['mx'][0]}")(pl.scan_parquet(f"{BASE}/{NC}.parquet").select(pl.col('fiscal_year').min().alias('mn'), pl.col('fiscal_year').max().alias('mx')).collect()))

# ============ NHGIS ============
print("\n===== NHGIS =====")
def nhgis_counts():
    return {
        "schools_2020_cols": len(schema("nhgis/schools_nhgis_geog_2020")),  # claim 47
        "colleges_2020_cols": len(schema("nhgis/colleges_nhgis_geog_2020")),  # claim 38
        "schools_1990_cols": len(schema("nhgis/schools_nhgis_geog_1990")),  # claim 35
    }
probe("col-count claims (schools2020=47, colleges2020=38, schools1990=35)", nhgis_counts)
probe("schools geocode_accuracy dtype (claim Float64)", lambda: dtype("nhgis/schools_nhgis_geog_2020","geocode_accuracy"))
probe("colleges geocode_accuracy dtype (claim Int64 - differs from schools)", lambda: dtype("nhgis/colleges_nhgis_geog_2020","geocode_accuracy"))
probe("schools geoid_block dtype (claim Int64, not String)", lambda: dtype("nhgis/schools_nhgis_geog_2020","geoid_block"))
probe("schools key ids present (ncessch,leaid,tract,block_group,census_region,census_division)",
      lambda: [c for c in ["ncessch","leaid","tract","block_group","geoid_block","census_region","census_division"] if c in schema("nhgis/schools_nhgis_geog_2020")])
probe("colleges key ids present (unitid,opeid,tract,county_fips,county_name,state_abbr)",
      lambda: [c for c in ["unitid","opeid","tract","block_group","county_fips","county_name","state_abbr"] if c in schema("nhgis/colleges_nhgis_geog_2020")])
probe("schools ncessch/leaid dtype (claim Int64)", lambda: (dtype("nhgis/schools_nhgis_geog_2020","ncessch"), dtype("nhgis/schools_nhgis_geog_2020","leaid")))
probe("colleges opeid dtype (claim String)", lambda: dtype("nhgis/colleges_nhgis_geog_2020","opeid"))
probe("schools 1990 lacks cbsa (claim: no CBSA in 1990)", lambda: "cbsa" not in schema("nhgis/schools_nhgis_geog_1990"))

# ============ Codebook .xls readability ============
print("\n===== CODEBOOK .XLS READABILITY =====")
def xls_probe():
    import urllib.request
    url = f"{BASE}/nacubo/codebook_colleges_nacubo_endowments.xls"
    req = urllib.request.Request(url, headers={"User-Agent": "daaf-doc-audit/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        head = r.read(8)
    # Real .xls (BIFF/OLE2) magic = D0 CF 11 E0; HTML masquerade would start with '<'
    magic = head.hex()
    is_ole2 = head[:4] == b"\xd0\xcf\x11\xe0"
    # attempt pandas/xlrd read
    reader = "none"
    try:
        import pandas as pd
        try:
            _ = pd.read_excel(url, nrows=3)
            reader = "pandas.read_excel OK"
        except Exception as e2:
            reader = f"pandas.read_excel FAILED: {type(e2).__name__}: {str(e2)[:60]}"
    except Exception:
        reader = "pandas unavailable"
    return f"first8bytes={magic} OLE2_magic={is_ole2} reader={reader}"
probe("nacubo codebook .xls readability", xls_probe)

print("\nVALIDATION: nacubo/nccs/nhgis probes executed PASS")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 14:16:48
# Command: python3 /daaf/scripts/mirror_maintenance/31_doc-audit-nacubo-nccs-nhgis.py
# Duration: 29s
# Exit code: 0
#
# --- STDOUT ---
# ===== NACUBO =====
# [7-columns-only claim] n_cols=7 (claim EXACTLY 7); cols=['year', 'unitid', 'inst_name_nacubo', 'fips', 'endow_total', 'endow_per_fte', 'endow_chg_mktval']; documented-not-present=[]; extra=[]
# [dtypes] {'year': 'Int64', 'unitid': 'Int64', 'inst_name_nacubo': 'String', 'fips': 'Int64', 'endow_total': 'Float64', 'endow_per_fte': 'Float64', 'endow_chg_mktval': 'Float64'}
# [null-counts (claim fips=1 per_fte=1260 chg=3972 rest=0)] {'year': 0, 'unitid': 0, 'inst_name_nacubo': 0, 'fips': 1, 'endow_total': 0, 'endow_per_fte': 1260, 'endow_chg_mktval': 3972}
# [year range (claim 2012-2022)] min=2012 max=2022
# [endow_chg_mktval scale (claim decimal fraction ~ -1..1, NOT 0-100)] min=-0.3964872418904002 max=1.791923159748006
# [no -1/-2/-3 sentinels in endow_total (claim null-only missing)] []
# 
# ===== NCCS =====
# [161-columns claim] n_cols=161 (claim 161); rows=29889 (claim ~30K)
# [Portal name-mapping cols present + id dtypes] documented-map-cols not present: []; ein_dtype=Int64 fips_dtype=Int64 year_dtype=Int64
# [NTEE absent (claim: no NTEE in Portal)] []
# [year range (claim 1993-2016)] min=1993 max=2016
# [fiscal_year range (claim 1994-2017)] min=1994 max=2017
# 
# ===== NHGIS =====
# [col-count claims (schools2020=47, colleges2020=38, schools1990=35)] {'schools_2020_cols': 47, 'colleges_2020_cols': 38, 'schools_1990_cols': 35}
# [schools geocode_accuracy dtype (claim Float64)] Float64
# [colleges geocode_accuracy dtype (claim Int64 - differs from schools)] Int64
# [schools geoid_block dtype (claim Int64, not String)] Int64
# [schools key ids present (ncessch,leaid,tract,block_group,census_region,census_division)] ['ncessch', 'leaid', 'tract', 'block_group', 'geoid_block', 'census_region', 'census_division']
# [colleges key ids present (unitid,opeid,tract,county_fips,county_name,state_abbr)] ['unitid', 'opeid', 'tract', 'block_group', 'county_fips', 'county_name', 'state_abbr']
# [schools ncessch/leaid dtype (claim Int64)] ('Int64', 'Int64')
# [colleges opeid dtype (claim String)] String
# [schools 1990 lacks cbsa (claim: no CBSA in 1990)] True
# 
# ===== CODEBOOK .XLS READABILITY =====
# [nacubo codebook .xls readability] first8bytes=d0cf11e0a1b11ae1 OLE2_magic=True reader=pandas.read_excel OK
# 
# VALIDATION: nacubo/nccs/nhgis probes executed PASS
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
