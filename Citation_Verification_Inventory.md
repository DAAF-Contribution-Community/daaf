# Citation Verification Inventory

**Purpose:** Comprehensive verification of every citation, reference, URL, and attributed claim across all DAAF v2.0.0 skill documents.
**Created:** 2026-03-27
**Status:** COMPLETE -- ALL CORRECTIONS APPLIED
**Corrections applied:** 2026-03-27 (all 58 actionable items fixed across 10 parallel agents)

---

## Verification Legend

| Status | Meaning |
|--------|---------|
| VERIFIED | Citation confirmed accurate via web search |
| NEEDS CORRECTION | Error found, correction pending |
| UNABLE TO VERIFY | Could not confirm via available sources |
| URL DEAD | URL no longer resolves |

---

## Grand Totals

| Metric | Count |
|--------|-------|
| **Total citations/references checked** | **1,005** |
| **Verified** | **932 (92.7%)** |
| **Needs Correction** | **65 (6.5%)** |
| **Unable to Verify** | **9 (0.9%)** |
| **URL Dead** | **2 (0.2%)** |

---

## Summary Dashboard

| Skill | Files Checked | Citations Found | Verified | Needs Correction | Unable to Verify | URL Dead |
|-------|--------------|----------------|----------|-----------------|-----------------|----------|
| data-scientist (SKILL.md + causal-inference) | 2 | 98 | 94 | 1 | 3 | 0 |
| data-scientist (statistical-modeling + supervised-ml) | 2 | 67 | 63 | 4 | 0 | 0 |
| data-scientist (descriptive + unsupervised) | 2 | 67 | 65 | 1 | 1 | 0 |
| data-scientist (geospatial + visualization) | 9 | 73 | 71 | 2 | 0 | 0 |
| science-communication | 7 | 68 | 64 | 4 | 0 | 0 |
| linearmodels | 8 | 91 | 82 | 8 | 0 | 1 |
| geopandas | 10 | 92 | 84 | 8 | 0 | 0 |
| pyfixest | 9 | 72 | 68 | 3 | 1 | 1 |
| statsmodels | 8 | 109 | 104 | 4 | 1 | 0 |
| scikit-learn | 15 | 77 | 71 | 4 | 2 | 0 |
| plotnine + plotly | 12 | 63 | 56 | 7 | 0 | 0 |
| polars + marimo | 18 | 128 | 110 | 19 | 1 | 0 |

---

## Master Correction List

All items requiring action, organized by priority. Each entry links to the detailed finding below.

### HIGH PRIORITY -- Factual Errors in Academic Citations

| # | Skill | File | Issue | Correction |
|---|-------|------|-------|------------|
| H1 | science-communication | communication-review.md:35,197 | **Fabricated author names**: "Winton & Gaynor (2017)" for "Seven Deadly Sins of Statistical Misinterpretation" | Correct authors are **Winnifred Louis & Cassandra Chapman** (University of Queensland). [The Conversation link](https://theconversation.com/the-seven-deadly-sins-of-statistical-misinterpretation-and-how-to-avoid-them-74306) |
| H2 | data-scientist | causal-inference.md:879 | **Haber et al. (2022) page numbers wrong**: listed as "2020-2028" | Correct pages are **2084-2097**. *AJE* 191(12) |
| H3 | data-scientist | supervised-ml.md:546 | **Author order reversed**: "Athey, S. and Wager, S. (2018)" | Should be **"Wager, S. and Athey, S."** -- Stefan Wager is first author on the published JASA paper |
| H4 | data-scientist | exploratory-unsupervised.md:460 | **Wrong co-author on UMAP software citation**: lists "Astels, S." | Steve Astels co-authored the **HDBSCAN** JOSS paper, not UMAP. UMAP JOSS authors: **McInnes, Healy, Saul, Grossberger** |
| H5 | data-scientist | geospatial-analysis.md:700, geospatial-operations.md:415, pysal-spatial-stats.md:561 | **Wrong journal for PySAL paper**: cited as *Journal of Open Source Software* | Correct journal: ***Geographical Analysis***, 54(3), 467-487. Appears in 3 files |

### MEDIUM PRIORITY -- Incorrect API Claims / Deprecated Parameters

| # | Skill | File | Issue | Correction |
|---|-------|------|-------|------------|
| M1 | polars | joins-concat.md:36 | `how="outer"` listed as alias for `how="full"` | **Not valid in Polars 1.x**. Remove line; only `how="full"` works |
| M2 | polars | dataframes-series.md:275 | `fill_null(strategy="mean")` | **Does not exist**. Use `fill_null(pl.col("value").mean())` instead |
| M3 | polars | io-data.md:18,37 | `dtypes={"id": pl.Int32}` parameter | Renamed to **`schema_overrides`** in 0.20.31. Appears in both `read_csv` and `scan_csv` examples |
| M4 | polars | strings-datetime-categorical.md:191 | `dt.weekday()` returns "0=Monday, 6=Sunday" | Actually returns **1=Monday, 7=Sunday** (ISO convention) |
| M5 | polars | strings-datetime-categorical.md:49 | `str.find()` returns "-1 if not found" | Actually returns **null (None)** when not found |
| M6 | polars | gotchas.md:280 | `df[0]` returns "first row as dict" | Returns a **1-row DataFrame**. Use `df.row(0, named=True)` for dict |
| M7 | statsmodels | linear-models.md:196 | "No formula API for GLS" | **Incorrect**: `smf.gls()` exists and is documented |
| M8 | statsmodels | linear-models.md:617 | "MixedLM uses the EM algorithm by default" | **Incorrect**: Defaults to gradient-based optimization (BFGS, L-BFGS-B, CG) |
| M9 | statsmodels | glm-discrete.md:75 | Cauchy link: `g(mu) = arctan(mu)` | **Oversimplified**: Actual formula is `g(p) = tan(pi*(p - 0.5))` using Cauchy CDF |
| M10 | linearmodels | panel-models.md:142-143 | `res.f_poolable` attribute | Correct attribute name is **`res.f_pooled`** |
| M11 | linearmodels | quickstart.md:343-344 | `res.entity_info` and `res.time_info` typed as `dict` | Actually return **pandas Series** |
| M12 | linearmodels | panel-models.md:432-433 | `res.entity_info.total` / `res.time_info.total` | **Invalid**: `.total` is not a valid Series accessor |
| M13 | plotnine | aesthetics.md:134-148 | Shape codes 0-25 (ggplot2 integer codes) | **plotnine uses matplotlib markers**, not ggplot2 0-25 codes. Use "o", "s", "^", "D", etc. |
| M14 | plotly | export.md:257-262 | `pio.kaleido.scope.*` configuration | **Deprecated since Plotly 6.2**. Use `pio.defaults.*` instead |
| M15 | plotly | export.md:178 | CDN URL `plotly-latest.min.js` | **Frozen at v1.58.5** (July 2021). Use versioned URL for Plotly 6.x |
| M16 | marimo | ui-elements.md:232-242 | `mo.ui.form(content, elements_dict)` two-arg pattern | **Incorrect API**: Use `.batch().form()` pattern instead |
| M17 | marimo | apps-deployment.md:80-83 | `mo.cli_arg()` function | **Does not exist**. `mo.cli_args()` is a simple dict-returning utility |
| M18 | marimo | apps-deployment.md:253-257 | `create_asgi_app("notebook.py")` | **Wrong pattern**: Uses `.with_app(path="", root="notebook.py").build()` |
| M19 | scikit-learn | gotchas.md:140 | "10 is the default for `init='k-means++'` since 1.4" | **Inverted**: `n_init='auto'` gives **1** for k-means++ and **10** for random |

### LOW PRIORITY -- Outdated Claims, Minor Inaccuracies, Incomplete Lists

| # | Skill | File | Issue | Correction |
|---|-------|------|-------|------------|
| L1 | data-scientist | statistical-modeling.md:481 | McDermott SE blog URL uses old path | Update to `https://grantmcdermott.com/posts/better-way-adjust-ses/` |
| L2 | data-scientist | statistical-modeling.md:473 | pyfixest author "Schar" | Minor: standard ASCII rendering is "Schaer" |
| L3 | data-scientist | supervised-ml.md:481 | PyTorch tutorials URL | May have migrated to `https://docs.pytorch.org/tutorials/` |
| L4 | data-scientist | causal-inference.md:656,831 | Callaway, Goodman-Bacon, Sant'Anna "forthcoming, *AER*" | AER venue **unconfirmed**; companion paper appeared in *AEA P&P* |
| L5 | science-communication | narrative-frameworks.md:327, deliverable-templates.md:258 | Minto (2009) Pyramid Principle 3rd ed. | Year likely **2010** (hardcover ISBN 0273710516). Appears in 2 files |
| L6 | science-communication | accessibility-equity.md:122 | "Schwabish et al., 2021" for Do No Harm Guide | Only 2 authors (Schwabish & Feng); "et al." incorrect for 2-author work |
| L7 | linearmodels | quickstart.md:102 | Error type listed as "TypeError" | Should be **"ValueError"** (inconsistent with gotchas.md:39) |
| L8 | linearmodels | iv-models.md:99 | "(Shea's)" parenthetical on F > 10 rule | Misleading: Staiger-Stock F is the standard partial F, not specifically Shea's statistic |
| L9 | linearmodels | gotchas.md:157-159 | "linearmodels does not detect or remove singletons" | **Outdated**: PanelOLS now has a `singletons` parameter (default True) |
| L10 | linearmodels | covariance-inference.md:278 | `vcov={"CRV1": "e+t"}` abbreviated pyfixest syntax | Should use full form `vcov={"CRV1": "entity+time"}` |
| L11 | geopandas | quickstart.md:303, data-io.md:304, crs-projections.md:257 | Tenkanen et al. listed as "(forthcoming)" | Book is **published** (2024 CRC Press). 3 files affected |
| L12 | geopandas | crs-projections.md:138 | EPSG:2163 "US National Atlas" | **Deprecated** in favor of EPSG:9311 |
| L13 | geopandas | spatial-operations.md:358 | Rey et al. Ch. 4 cited as "Spatial data" | Ch. 4 is actually **"Spatial Weights"** |
| L14 | geopandas | visualization.md:128 | NaturalBreaks described as "Synonym for Fisher-Jenks" | They are **separate classifiers** in mapclassify with different algorithms |
| L15 | geopandas | pysal-spatial-stats.md:555 | Ch. 12 grouped as "Spatial regression" | Ch. 12 is **"Spatial Feature Engineering"** |
| L16 | pyfixest | SKILL.md:179 vs difference-in-differences.md:293 | Gardner year: "(2021)" vs "(2022)" | **Internal inconsistency**: pick one and standardize |
| L17 | pyfixest | difference-in-differences.md:294 | Dube et al. title includes "Event Studies" | NBER WP title is **"A Local Projections Approach to Difference-in-Differences"** (without "Event Studies") |
| L18 | statsmodels | diagnostics.md:105 | "Shapiro-Wilk limited to N <= 5000" | Not a hard limit -- scipy issues a **warning** but still runs |
| L19 | scikit-learn | interpretation.md:82 | "KernelExplainer is O(2^F)" | That's exact Shapley complexity, not KernelExplainer which **uses sampling** |
| L20 | scikit-learn | classification.md:25 | `penalty="l2"` as default | **Deprecated in 1.8.0** -- replaced by `l1_ratio=0` |
| L21 | scikit-learn | classification.md:267 | XGBoost "Requires encoding" for categoricals | **Outdated**: native support since XGBoost 1.5 via `enable_categorical=True` |
| L22 | plotnine | geoms.md:117 | Comment "# Default loess smooth" | Default is `method="auto"`: **loess for n<1000, glm otherwise** |
| L23 | plotly | charts.md:48 | Marginal plot options list | Missing **"rug"** option |
| L24 | plotly | charts.md:168 | histnorm options list | Missing **"probability density"** option |
| L25 | plotly | charts.md:187 | px.box points options | Missing **"suspectedoutliers"** option |
| L26 | polars | aggregations-grouping.md:204 | `pl.arange()` usage | **Deprecated**: use `pl.int_range()` |
| L27 | polars | io-data.md:322 | `pip install polars[avro]` | **Does not exist**: Avro support is built-in |
| L28 | polars | io-data.md:338 | `delta_table_options={"version": 5}` | Not standard API; use **`version=5`** directly |
| L29 | polars | performance.md:255 | `pl.thread_pool_size()` | Current API name is **`pl.threadpool_size()`** |
| L30 | polars | performance.md:345 | zstd level 19 labeled "Max compression" | Max is **22**, not 19 |
| L31 | polars | validation-patterns.md:212 | `pl.count()` in aggregation | **Deprecated**: use `pl.len()` |
| L32 | marimo | SKILL.md:14 | `library-version: "0.10.x"` | **Outdated**: current is 0.19.x |
| L33 | marimo | apps-deployment.md:242-245 | `App.run()` return value | Returns **`(outputs, defs)` tuple**, not single result |
| L34 | marimo | sql-data.md:11 | `marimo[sql]` "Includes: duckdb, polars" | May overstate; polars likely in `[recommended]` not `[sql]` |

### URL Dead

| # | Skill | File | Dead URL | Suggested Replacement |
|---|-------|------|----------|----------------------|
| U1 | linearmodels | system-models.md:374 | `https://bashtage.github.io/linearmodels/system/introduction.html` | `https://bashtage.github.io/linearmodels/system/index.html` |
| U2 | pyfixest | gotchas.md:336 | `https://github.com/py-econometrics/pyfixest/blob/master/CHANGELOG.md` | `https://py-econometrics.github.io/pyfixest/changelog.html` |

### Unable to Verify

| # | Skill | File | Claim | Notes |
|---|-------|------|-------|-------|
| V1 | data-scientist | causal-inference.md:203-205 | Angrist 2021 Nobel lecture exact quote | Attribution and sentiment correct; exact wording unconfirmable from indexed sources |
| V2 | data-scientist | causal-inference.md:656,831 | Callaway et al. "forthcoming, *AER*" | Paper exists (arXiv:2107.02637) but AER venue specifically unconfirmed |
| V3 | data-scientist | exploratory-unsupervised.md:323 | Lanza et al. (2013) attenuation values "-0.115 to -0.421" | Paper is paywalled; general claim is supported but exact numbers unconfirmable |
| V4 | pyfixest | gotchas.md:53 | ssc option "nested" renamed to "nonnested" | Plausible but not documented in available online sources |
| V5 | statsmodels | glm-discrete.md:699 | URL `statsmodels.org/stable/margeff.html` | May not exist as standalone page; marginal effects documented per-model |
| V6 | scikit-learn | fairness.md:24 | fairlearn 0.12.0 pinned in DAAF Dockerfile | Internal infrastructure claim |
| V7 | scikit-learn | fairness.md:24 | fairlearn 0.13.0 scipy<1.16.0 constraint | Could not access pyproject.toml dependencies |
| V8 | polars + marimo | outputs-layouts.md:224-225 | `mo.toast()` exact `kind` parameter values | Function exists but exact parameter values need direct doc verification |

---

## Detailed Findings by Skill

### 1. data-scientist: SKILL.md + causal-inference.md

**Files:** `SKILL.md`, `references/causal-inference.md`
**Citations checked:** 98 | **Verified:** 94 | **Needs Correction:** 1 | **Unable to Verify:** 3

This is the most citation-dense file in the entire framework, with 98 verifiable references. The causal inference document cites papers spanning Holland (1986) through Baker et al. (forthcoming), covering the full landscape of modern causal methods.

**All formal bibliography entries verified correct** except:
- **Haber et al. (2022)** page numbers: listed as 2020-2028, should be **2084-2097** (line 879)

**Key verified citations include:**
- Holland (1986) JASA 81(396), 945-960 -- fundamental problem of causal inference
- Pearl (1995) Biometrika 82(4), 669-688 -- back-door criterion
- Angrist & Pischke (2010) JEP 24(2), 3-30 -- credibility revolution
- Staiger & Stock (1997) Econometrica 65(3), 557-586 -- F > 10 rule
- Calonico, Cattaneo, Titiunik (2014) Econometrica 82(6), 2295-2326 -- optimal RD bandwidth
- Goodman-Bacon (2021) J. Econometrics 225(2), 254-277 -- TWFE decomposition
- de Chaisemartin & d'Haultfoeuille (2020) AER 110(9), 2964-2996 -- negative weights
- Rambachan & Roth (2023) REStud 90(5), 2555-2591 -- Honest DiD
- All DOIs verified correct (Callaway & Sant'Anna, Roth & Sant'Anna, Sant'Anna & Zhao)
- All URLs live: mixtape.scunning.com, theeffectbook.net, dagitty.net, nobelprize.org, mru.org, lost-stats.github.io
- Software claims verified: rdrobust, CausalPy, synthdid, csdid all installable via pip

---

### 2. data-scientist: statistical-modeling.md + supervised-ml.md

**Files:** `references/statistical-modeling.md`, `references/supervised-ml.md`
**Citations checked:** 67 | **Verified:** 63 | **Needs Correction:** 4

**Corrections needed:**
- **Wager & Athey (2018) author order** (supervised-ml.md:546): First author is Stefan Wager, not Susan Athey
- **McDermott SE blog URL** (statistical-modeling.md:481): Path changed to `/posts/better-way-adjust-ses/`
- **pyfixest author "Schar"** (statistical-modeling.md:473): Minor -- standard ASCII is "Schaer"
- **PyTorch tutorials URL** (supervised-ml.md:481): May have migrated to `docs.pytorch.org/tutorials/`

**Key verified citations include:**
- Leamer (1983) AER 73(1), 31-43 -- specification searches
- Mundlak (1978) Econometrica 46(1), 69-85 -- CRE approach
- Abadie, Athey, Imbens, Wooldridge (2023) QJE 138(1), 1-35 -- clustering
- Cameron, Gelbach, Miller (2008) REStat 90(3), 414-427 -- wild cluster bootstrap
- Cohen (1988) 2nd ed. Lawrence Erlbaum -- effect size benchmarks
- Breiman (2001) Statistical Science 16(3), 199-231 -- two cultures
- Shmueli (2010) Statistical Science 25(3), 289-310 -- explain vs predict
- Rudin (2019) Nature Machine Intelligence 1, 206-215 -- interpretable models
- Obermeyer et al. (2019) Science 366(6464), 447-453 -- racial bias in healthcare algorithm
- Kleinberg, Mullainathan, Raghavan (2016) arXiv/ITCS 2017 -- fairness impossibility
- All book URLs live: statlearning.com, hastie.su.domains, christophm.github.io

---

### 3. data-scientist: descriptive-analysis.md + exploratory-unsupervised.md

**Files:** `references/descriptive-analysis.md`, `references/exploratory-unsupervised.md`
**Citations checked:** 67 | **Verified:** 65 | **Needs Correction:** 1 | **Unable to Verify:** 1

**Correction needed:**
- **UMAP software citation** (exploratory-unsupervised.md:460): Lists "Astels, S." as co-author -- Astels is from the **HDBSCAN** JOSS paper, not UMAP. Correct authors: McInnes, Healy, Saul, Grossberger

**Unable to verify:**
- Lanza, Tan, Bray (2013) specific attenuation values "-0.115 to -0.421" -- paper paywalled

**Key verified citations include:**
- Oaxaca (1973) IER 14(3), 693-709 / Blinder (1973) JHR 8(4), 436-455 -- decomposition
- Kitagawa (1955) JASA 50(272), 1168-1194 -- components of differences
- Gelbach (2016) J. Labor Econ. 34(2), 509-543 -- covariate selection
- Kaufman & Rousseeuw (1990) -- silhouette thresholds (>0.7 strong, >0.5 reasonable, >0.25 weak)
- van der Maaten & Hinton (2008) JMLR 9, 2579-2605 -- t-SNE
- McInnes, Healy, Melville (2018) arXiv:1802.03426 -- UMAP
- Hennig (2015) Pattern Recognition Letters 64, 53-62 -- "what are true clusters?"
- Monti et al. (2003) Machine Learning 52, 91-118 -- consensus clustering

---

### 4. data-scientist: geospatial + visualization + other references

**Files:** 9 reference files (geospatial-analysis, geospatial-operations, visualization-design, visualization-execution, research-questions, eda-checklist, transformation-validation, data-documentation, code-documentation)
**Citations checked:** 73 | **Verified:** 71 | **Needs Correction:** 2

**Correction needed (same error in 2 files):**
- **PySAL ecosystem paper journal** (geospatial-analysis.md:700, geospatial-operations.md:415): Cited as *Journal of Open Source Software*. Correct: ***Geographical Analysis*** 54(3), 467-487

**Key verified citations include:**
- Tobler (1970) Economic Geography 46(Supplement), 234-240 -- First Law of Geography
- Openshaw (1984) CATMOG No. 38 -- MAUP
- Robinson (1950) ASR 15(3), 351-357 -- ecological fallacy
- Anselin (1995) Geographical Analysis 27(2), 93-115 -- LISA
- Cleveland & McGill (1984) JASA 79(387), 531-554 -- graphical perception
- Conley (1999) J. Econometrics 92(1), 1-45 -- spatial HAC
- Fotheringham, Brunsdon, Charlton (2002) Wiley -- GWR
- All EPSG codes verified: 4326=WGS84, 5070=NAD83 Conus Albers, 3857=Web Mercator, 32617=UTM 17N
- All viz URLs live: colorbrewer2.org, clauswilke.com/dataviz, data-to-viz.com, urbaninstitute.github.io, colororacle.org
- Okabe-Ito palette hex values confirmed correct
- WCAG 2.1 contrast ratios confirmed: 4.5:1 text, 3:1 graphical elements

---

### 5. science-communication

**Files:** `SKILL.md` + 6 reference files (audience-analysis, narrative-frameworks, plain-language, deliverable-templates, communication-review, accessibility-equity)
**Citations checked:** 68 | **Verified:** 64 | **Needs Correction:** 4

**Corrections needed:**
- **CRITICAL -- Fabricated author names** (communication-review.md:35,197): "Winton, B. and Gaynor, M." are **wrong**. Actual authors of "Seven Deadly Sins of Statistical Misinterpretation" are **Winnifred Louis and Cassandra Chapman** (Univ. of Queensland). [Verified link](https://theconversation.com/the-seven-deadly-sins-of-statistical-misinterpretation-and-how-to-avoid-them-74306)
- **Minto publication year** (narrative-frameworks.md:327, deliverable-templates.md:258): Listed as 2009, evidence suggests **2010** for the widely available 3rd edition hardcover (ISBN 0273710516)
- **"Schwabish et al."** (accessibility-equity.md:122): Only 2 authors (Schwabish & Feng); should be **"Schwabish & Feng, 2021"**

**Key verified citations include:**
- IPCC calibrated uncertainty language: all 10 likelihood levels with exact probability ranges confirmed correct
- Haber et al. (2022) AJE 191(12), 2084-2097 -- causal language (correctly cited here, unlike causal-inference.md)
- Mastrandrea et al. (2011) Climatic Change 108, 675-691 -- IPCC guidance note
- AAAS Communication Toolkit URL live and confirmed
- NIH Clear & Simple and Plain Language URLs all live
- WCAG 2.1 criterion numbers all correct (1.4.3, 1.4.11, 1.1.1, 1.4.1)
- D'Ignazio & Klein (2020) Data Feminism -- MIT Press, URL live
- Pew 2020 survey: 3% Latinx usage figure confirmed
- Urban Institute Do No Harm Guide (2021) URL live

---

### 6. linearmodels

**Files:** `SKILL.md` + 7 reference files (quickstart, panel-models, covariance-inference, iv-models, asset-pricing, system-models, gotchas)
**Citations checked:** 91 | **Verified:** 82 | **Needs Correction:** 8 | **URL Dead:** 1

**Corrections needed:**
- `res.f_poolable` should be **`res.f_pooled`** (panel-models.md:142-143)
- `res.entity_info` and `res.time_info` typed as `dict` but are **pandas Series** (quickstart.md:343-344)
- `res.entity_info.total` / `res.time_info.total` invalid Series access (panel-models.md:432-433)
- Error type "TypeError" should be **"ValueError"** (quickstart.md:102 vs gotchas.md:39)
- "(Shea's)" parenthetical misleading on F > 10 rule (iv-models.md:99)
- Singletons claim outdated -- PanelOLS now has `singletons` parameter (gotchas.md:157-159)
- Abbreviated pyfixest syntax `"e+t"` should use full `"entity+time"` (covariance-inference.md:278)

**URL Dead:** `linearmodels/system/introduction.html` returns 404 -> use `.../system/index.html`

**Key verified citations include:**
- Driscoll & Kraay (1998) REStat 80(4), 549-560
- Newey & West (1987) Econometrica 55(3), 703-708
- Petersen (2009) RFS 22(1), 435-480
- Zellner (1962) JASA 57(298), 348-368 -- SUR
- Zellner & Theil (1962) Econometrica 30(1), 54-78 -- 3SLS
- Fama & French (1993) JFE 33(1), 3-56
- Gibbons, Ross, Shanken (1989) Econometrica 57(5), 1121-1152 -- GRS test
- Hansen (1982) Econometrica 50(4), 1029-1054 -- GMM
- All class names verified: PanelOLS, RandomEffects, BetweenOLS, FirstDifferenceOLS, IV2SLS, IVLIML, IVGMM, SUR, IV3SLS, AbsorbingLS
- EntityEffects/TimeEffects formula keywords confirmed
- Kevin Sheppard authorship confirmed

---

### 7. geopandas

**Files:** `SKILL.md` + 9 reference files (quickstart, data-io, crs-projections, spatial-operations, raster-integration, gotchas, visualization, pysal-spatial-stats)
**Citations checked:** 92 | **Verified:** 84 | **Needs Correction:** 8

**Corrections needed:**
- Tenkanen et al. listed as "(forthcoming)" but **already published** (2024 CRC Press) -- 3 files
- **EPSG:2163 deprecated** in favor of EPSG:9311 (crs-projections.md:138)
- Rey et al. Ch. 4 titled **"Spatial Weights"** not "Spatial data" (spatial-operations.md:358)
- **NaturalBreaks is NOT a synonym for FisherJenks** -- separate classifiers (visualization.md:128)
- **PySAL journal name wrong** (same error as Agent 4) -- *Geographical Analysis* not *JOSS* (pysal-spatial-stats.md:561)
- Rey et al. Ch. 12 is **"Spatial Feature Engineering"** not "Spatial regression" (pysal-spatial-stats.md:555)

**Key verified items include:**
- All PySAL API verified: libpysal.weights.Queen, Rook, KNN, DistanceBand, Kernel, Graph.build_*
- esda: Moran, Moran_Local, Moran_BV, Moran_Rate, Geary, G, G_Local, Join_Counts -- all confirmed
- spreg: OLS (spat_diag), ML_Lag, ML_Error, GM_Lag, GM_Error -- all confirmed
- pointpats: centrography, QStatistic, Genv, Fenv, Kenv -- all confirmed
- All LISA quadrant codes confirmed: 1=HH, 2=LH, 3=LL, 4=HL
- Shapely >= 2.0 requirement confirmed; PyGEOS removal confirmed
- pyogrio as default I/O engine confirmed; cascaded_union removal confirmed
- Boeing (2017) CEUS 65, 126-139 -- OSMnx confirmed
- Hoyer & Hamman (2017) JORS 5(1), 10 -- xarray confirmed

---

### 8. pyfixest

**Files:** `SKILL.md` + 8 reference files (quickstart, fixed-effects, advanced-inference, difference-in-differences, instrumental-variables, integration, tables-and-plots, gotchas)
**Citations checked:** 72 | **Verified:** 68 | **Needs Correction:** 3 | **Unable to Verify:** 1 | **URL Dead:** 1

**Corrections needed:**
- **Gardner year inconsistency**: SKILL.md says "(2021)", difference-in-differences.md says "(2022)" -- standardize
- **Dube et al. title**: NBER WP title is "A Local Projections Approach to Difference-in-Differences" (without "Event Studies")

**URL Dead:** `github.com/.../blob/master/CHANGELOG.md` returns 404 -> use docs site changelog

**Key verified citations include:**
- Berge, Butts, McDermott (2026) arXiv:2601.21749 -- fixest R package
- Sun & Abraham (2021) J. Econometrics 225(2), 175-199
- Callaway & Sant'Anna (2021) J. Econometrics 225(2), 200-230
- de Chaisemartin & D'Haultfoeuille (2020) AER 110(9), 2964-2996
- Goodman-Bacon (2021) J. Econometrics 225(2), 254-277
- Roth (2022) AER: Insights 4(3), 305-322
- Rambachan & Roth (2023) REStud 90(5), 2555-2591
- Romano & Wolf (2005) Econometrica 73(4), 1237-1282
- Borusyak, Hull, Jaravel (2022) REStud 89(1), 181-213
- Goldsmith-Pinkham, Sorkin, Swift (2020) AER 110(8), 2586-2624
- All v0.40.0 breaking changes confirmed: default SEs iid, ssc() renames, fixef_rm singleton default

---

### 9. statsmodels

**Files:** `SKILL.md` + 7 reference files (quickstart, linear-models, glm-discrete, diagnostics, hypothesis-testing, gotchas, time-series)
**Citations checked:** 109 | **Verified:** 104 | **Needs Correction:** 4 | **Unable to Verify:** 1

**Corrections needed:**
- **GLS has a formula API** -- `smf.gls()` exists (linear-models.md:196)
- **MixedLM does NOT default to EM** -- uses BFGS/L-BFGS-B/CG (linear-models.md:617)
- **Cauchy link formula oversimplified** -- missing pi scaling and 0.5 offset (glm-discrete.md:75)
- **Shapiro-Wilk N<=5000 is not a hard limit** -- scipy warns but runs (diagnostics.md:105)

**Key verified items include:**
- All GLM families and default links verified correct (7 families)
- All diagnostic test return values verified (het_breuschpagan, het_white, jarque_bera, etc.)
- Time series: SARIMAX, VAR, VECM, ETS, UnobservedComponents, DynamicFactor -- all API claims correct
- Unit root tests: ADF, KPSS, Zivot-Andrews -- all confirmed
- Hamilton (1994), Hyndman & Athanasopoulos (2021), Lutkepohl (2005), Harvey (1989) -- all confirmed
- Seabold & Perktold (2010) SciPy Conf. -- confirmed
- Cameron & Trivedi (2013) Cambridge -- confirmed
- McCullagh & Nelder (1989) Chapman & Hall -- confirmed
- All 26 URLs tested are live

---

### 10. scikit-learn

**Files:** `SKILL.md` + 14 reference files (interpretation, evaluation-supervised, evaluation-unsupervised, quickstart, classification, regression-ml, feature-selection, gotchas, clustering, decomposition, mixture-models, manifold, preprocessing, fairness)
**Citations checked:** 77 | **Verified:** 71 | **Needs Correction:** 4 | **Unable to Verify:** 2

**Corrections needed:**
- **KernelExplainer O(2^F)** -- that's exact Shapley complexity, not the sampling-based implementation (interpretation.md:82)
- **`penalty="l2"` deprecated** in sklearn 1.8.0 (classification.md:25)
- **XGBoost categoricals**: native support since 1.5 via `enable_categorical=True` (classification.md:267)
- **KMeans n_init values inverted**: auto gives 1 for k-means++ and 10 for random, not vice versa (gotchas.md:140)

**Key verified items include:**
- HDBSCAN first-class since 1.3, set_output since 1.2, HistGradientBoosting stable since 1.0
- All default parameter values verified (RandomForest n_estimators=100, SVC kernel=rbf, etc.)
- All metric definitions confirmed correct (precision, recall, F1, AUC-ROC, silhouette, DBI)
- Confusion matrix layout [[TN,FP],[FN,TP]] confirmed
- fairlearn API verified: MetricFrame, ThresholdOptimizer, ExponentiatedGradient
- All sklearn version claims independently confirmed

---

### 11. plotnine + plotly

**Files:** plotnine SKILL.md + 5 refs; plotly SKILL.md + 5 refs
**Citations checked:** 63 | **Verified:** 56 | **Needs Correction:** 7

**Corrections needed:**
- **plotnine shape codes table uses ggplot2 conventions** -- plotnine uses matplotlib markers (aesthetics.md:134-148) -- **HIGH priority**
- geom_smooth default comment should note `method="auto"` behavior (geoms.md:117)
- `pio.kaleido.scope.*` deprecated since Plotly 6.2; use `pio.defaults.*` (export.md:257-262)
- `plotly-latest.min.js` CDN URL frozen at v1.58.5 (export.md:178)
- px marginal options missing "rug" (charts.md:48)
- histnorm options missing "probability density" (charts.md:168)
- px.box points missing "suspectedoutliers" (charts.md:187)

**Key verified items include:**
- plotnine: all geoms, scales, coords, facets, themes confirmed; Polars DataFrame support confirmed
- plotly: 40+ chart types claim confirmed; all built-in datasets confirmed
- Template combination "plotly_dark+presentation" syntax confirmed
- All tile provider paths confirmed (CartoDB.Positron, Stadia.StamenTerrain, etc.)

---

### 12. polars + marimo

**Files:** polars SKILL.md + 9 refs; marimo SKILL.md + 7 refs
**Citations checked:** 128 | **Verified:** 110 | **Needs Correction:** 19 | **Unable to Verify:** 1

This had the most corrections -- primarily deprecated Polars API names and incorrect marimo API patterns.

**Polars corrections (12):**
- `how="outer"` not valid in 1.x -- use `how="full"` (joins-concat.md:36)
- `fill_null(strategy="mean")` does not exist (dataframes-series.md:275)
- `dtypes` renamed to `schema_overrides` in 0.20.31 (io-data.md:18,37)
- `dt.weekday()` returns 1-7 not 0-6 (strings-datetime-categorical.md:191)
- `str.find()` returns null not -1 (strings-datetime-categorical.md:49)
- `df[0]` returns DataFrame not dict (gotchas.md:280)
- `pl.arange` deprecated; use `pl.int_range` (aggregations-grouping.md:204)
- `polars[avro]` extra doesn't exist (io-data.md:322)
- `delta_table_options={"version": 5}` not standard API (io-data.md:338)
- `pl.thread_pool_size()` should be `pl.threadpool_size()` (performance.md:255)
- zstd level 19 is not "max" (max is 22) (performance.md:345)
- `pl.count()` deprecated; use `pl.len()` (validation-patterns.md:212)

**Marimo corrections (7):**
- `library-version: "0.10.x"` is outdated; current is 0.19.x (SKILL.md:14)
- `mo.ui.form(content, dict)` two-arg pattern incorrect; use `.batch().form()` (ui-elements.md:232-242)
- `mo.cli_arg()` does not exist (apps-deployment.md:80-83)
- `create_asgi_app("notebook.py")` has wrong API pattern (apps-deployment.md:253-257)
- `App.run()` returns `(outputs, defs)` tuple (apps-deployment.md:242-245)
- `marimo[sql]` comment may overstate included packages (sql-data.md:11)

**Key verified items include:**
- All Polars type system, expression API, lazy/eager patterns confirmed
- All rename history confirmed (apply->map_elements, groupby->group_by, melt->unpivot, Utf8->String)
- Apache Arrow columnar format, streaming, no-dependencies claims confirmed
- marimo: reactivity model, caching, UI elements, SQL cells, deployment patterns largely correct
- All marimo URLs live: docs.marimo.io, github, discord, gallery, VS Code extension, molab

---

## Methodology

Each verification was performed by a dedicated subagent that:
1. Read every line of assigned files
2. Extracted every citation, URL, method attribution, API claim, and factual assertion
3. Performed web searches to verify each item against authoritative sources
4. Checked URLs for liveness
5. Verified API claims against official documentation
6. Cross-referenced academic citations against publisher databases

Verification was conducted on 2026-03-27 using web search and direct URL fetching.
