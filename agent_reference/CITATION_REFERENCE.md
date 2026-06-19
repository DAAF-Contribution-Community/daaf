# Citation Reference

> **Purpose:** Lightweight citation index for verifying and deduplicating citations accumulated during pipeline execution. Used by the orchestrator for citation management and by the report-writer and data-verifier for completeness checking.
> **Audience:** Orchestrator, report-writer, data-verifier
> **When to read:** Orchestrator consults on-demand when managing STATE.md citations. Report-writer loads at Stage 11 for verification. Data-verifier loads at Stage 12.

## Citation Philosophy

Three questions determine whether something warrants citation in a DAAF report:

1. **Did this method or tool directly produce an analytical result?** (e.g., pyfixest ran the regression, not polars which just loaded the data)
2. **Would a different methodological choice here have changed the findings?** (e.g., choosing Callaway-Sant'Anna over TWFE for staggered DiD)
3. **Does the creator deserve credit for enabling this specific work?** (e.g., a survey analysis library whose weighting implementation you relied on)

If yes to any — include with rationale. If no to all — omit.

**Parsimony principle:** A report with 5 well-justified citations is better than one with 30 perfunctory ones. Every citation should earn its place.

## Inclusion Thresholds

### Software & Tools

Cite when the library's **analytical functionality** drives a result. Do NOT cite for routine data wrangling (e.g., using polars to load a parquet file).

| Library | Canonical Citation | Cite When | Do NOT Cite When |
|---------|-------------------|-----------|------------------|
| DAAF | Kim, B.H. (2026). *DAAF: Data Analyst Augmentation Framework* (Version 2.1.0) [Computer software]. https://github.com/DAAF-Contribution-Community/daaf | Always (pre-populated in STATE.md) | — |
| pyfixest | Berge, L., Butts, K., & McDermott, G. (2026). pyfixest: Fast high-dimensional fixed effects estimation [Computer software]. Based on fixest (R). | Used for regression estimation or DiD | Only imported but not used for estimation |
| statsmodels | Seabold, S. & Perktold, J. (2010). "Statsmodels: Econometric and Statistical Modeling with Python." *Proceedings of the 9th Python in Science Conference*. | Used for GLM, time series, or statistical testing | Only used for post-estimation diagnostics supporting another library's estimation |
| linearmodels | Sheppard, K. linearmodels: Econometric models for panel, IV, and system regression [Computer software]. https://bashtage.github.io/linearmodels/ | Used for panel, IV/GMM, or system estimation | — |
| scikit-learn | Pedregosa, F. et al. (2011). "Scikit-learn: Machine Learning in Python." *Journal of Machine Learning Research*, 12, 2825-2830. | Used for ML models, clustering, or dimensionality reduction | Only used for a single preprocessing step |
| geopandas | Jordahl, K. et al. geopandas: Python tools for geographic data [Computer software]. https://geopandas.org/ | Used for spatial operations, joins, or mapping | Only used to read a shapefile for reference |
| PySAL | Rey, S.J. et al. (2022). "The PySAL Ecosystem of Open-Source Python Packages for the Analysis of Spatial Data." *Geographical Analysis*, 54(3), 467-487. | Used for spatial weights, autocorrelation, or spatial regression | — |
| svy | Diallo, M.S. svy: Python package for complex survey sampling and analysis [Computer software]. (Formerly samplics.) | Used for survey-weighted estimation | — |
| polars | Vink, R. et al. Polars: Blazingly fast DataFrames [Computer software]. https://pola.rs/ | Core data processing engine for the analysis | Only used for trivial file I/O |
| plotnine | Kibirige, H. et al. plotnine: Grammar of graphics for Python [Computer software]. https://plotnine.org/ | Primary visualization library producing report figures | Only used for a quick exploratory plot |
| plotly | Plotly Technologies Inc. Plotly: Interactive graphing library [Computer software]. https://plotly.com/ | Primary visualization library producing report figures | Only used for a quick exploratory plot |
| marimo | marimo team. marimo: Reactive Python notebook [Computer software]. https://marimo.io/ | Always (analysis notebook is a marimo notebook) | — |

### Methodological References

Cite the **primary** citation per method — the one paper you would cite in a journal article, not a comprehensive bibliography.

#### Causal Inference

| Method | Primary Citation | Cite When |
|--------|-----------------|-----------|
| DiD (staggered, Callaway-Sant'Anna) | Callaway, B. & Sant'Anna, P.H.C. (2021). "Difference-in-Differences with Multiple Time Periods." *Journal of Econometrics*, 225(2), 200-230. | Callaway-Sant'Anna estimator is the primary identification strategy |
| DiD (TWFE heterogeneity concerns) | Goodman-Bacon, A. (2021). "Difference-in-Differences with Variation in Treatment Timing." *Journal of Econometrics*, 225(2), 254-277. | Bacon decomposition or TWFE bias discussion |
| DiD (did2s) | Gardner, J. (2022). "Two-Stage Differences in Differences." arXiv:2207.05943. | did2s estimator used |
| DiD (Sun-Abraham) | Sun, L. & Abraham, S. (2021). "Estimating Dynamic Treatment Effects in Event Studies with Heterogeneous Treatment Effects." *Journal of Econometrics*, 225(2), 175-199. | Interaction-weighted estimator used |
| DiD (imputation) | Borusyak, K., Jaravel, X., & Spiess, J. (2024). "Revisiting Event-Study Designs: Robust and Efficient Estimation." *Review of Economic Studies*, 91(6), 3253-3285. | Imputation estimator used |
| DiD (doubly robust) | Sant'Anna, P.H.C. & Zhao, J. (2020). "Doubly Robust Difference-in-Differences Estimators." *Journal of Econometrics*, 219(1), 101-122. | Doubly robust DiD estimation used |
| DiD (TWFE negative weights) | de Chaisemartin, C. & D'Haultfoeuille, X. (2020). "Two-Way Fixed Effects Estimators with Heterogeneous Treatment Effects." *American Economic Review*, 110(9), 2964-2996. | TWFE decomposition or negative weight analysis performed |
| DiD (sensitivity analysis) | Rambachan, A. & Roth, J. (2023). "A More Credible Approach to Parallel Trends." *Review of Economic Studies*, 90(5), 2555-2591. | Sensitivity analysis for parallel trends violations performed |
| DiD (practitioner's guide) | Baker, A., Callaway, B., Cunningham, S., Goodman-Bacon, A., & Sant'Anna, P.H.C. (Forthcoming). "Difference-in-Differences Designs: A Practitioner's Guide." *Journal of Economic Literature*. arXiv:2503.13323. | DiD is the primary identification strategy (comprehensive methodology reference) |
| IV (weak instruments) | Staiger, D. & Stock, J.H. (1997). "Instrumental Variables Regression with Weak Instruments." *Econometrica*, 65(3), 557-586. | IV estimation with first-stage F-test |
| RD design | Cattaneo, M.D., Idrobo, N., & Titiunik, R. (2020). *A Practical Introduction to Regression Discontinuity Designs.* Cambridge University Press. | RD is primary identification strategy |
| Synthetic control | Abadie, A., Diamond, A., & Hainmueller, J. (2010). "Synthetic Control Methods for Comparative Case Studies." *Journal of the American Statistical Association*, 105(490), 493-505. | Synthetic control method used |
| Synthetic difference-in-differences | Arkhangelsky, D., Athey, S., Hirshberg, D.A., Imbens, G.W., & Wager, S. (2021). "Synthetic Difference-in-Differences." *American Economic Review*, 111(12), 4088-4118. | SDID estimator used (distinct from classical SC or standard DiD) |
| Propensity score | Rosenbaum, P.R. & Rubin, D.B. (1983). "The Central Role of the Propensity Score in Observational Studies for Causal Effects." *Biometrika*, 70(1), 41-55. | Propensity score matching or weighting used |
| Heckman selection correction | Heckman, J.J. (1979). "Sample Selection Bias as a Specification Error." *Econometrica*, 47(1), 153-162. | Heckman two-step or FIML selection correction used |
| Causal mediation (ACME/NDE/NIE) | Imai, K., Keele, L., & Tingley, D. (2010). "A General Approach to Causal Mediation Analysis." *Psychological Methods*, 15(4), 309-334. | Causal mediation analysis (ACME/ADE decomposition) performed |
| AIPW / doubly robust estimation | Robins, J.M., Rotnitzky, A., & Zhao, L.P. (1994). "Estimation of Regression Coefficients When Some Regressors Are Not Always Observed." *Journal of the American Statistical Association*, 89(427), 846-866. | Augmented IPW or doubly robust estimator used |
| Double/debiased ML (DML) | Chernozhukov, V., Chetverikov, D., Demirer, M., Duflo, E., Hansen, C., Newey, W., & Robins, J. (2018). "Double/Debiased Machine Learning for Treatment and Structural Parameters." *Econometrics Journal*, 21(1), C1-C68. | DML estimator used for ATE estimation with ML nuisance models |
| Meta-learners (CATE) | Künzel, S.R., Sekhon, J.S., Bickel, P.J., & Yu, B. (2019). "Metalearners for Estimating Heterogeneous Treatment Effects Using Machine Learning." *PNAS*, 116(10), 4156-4165. | S/T/X/R/DR-learner used for heterogeneous treatment effect estimation |

#### Survey Analysis

| Method | Primary Citation | Cite When |
|--------|-----------------|-----------|
| Complex survey design | Heeringa, S.G., West, B.T., & Berglund, P.A. (2017). *Applied Survey Data Analysis* (2nd ed.). CRC Press. | Survey-weighted analysis with stratification/clustering |
| Weighting decisions | Solon, G., Haider, S.J., & Wooldridge, J.M. (2015). "What Are We Weighting For?" *Journal of Human Resources*, 50(2), 301-316. | Explicit weighting methodology discussion |

#### Machine Learning

| Method | Primary Citation | Cite When |
|--------|-----------------|-----------|
| Prediction vs explanation | Shmueli, G. (2010). "To Explain or to Predict?" *Statistical Science*, 25(3), 289-310. | ML methods used for prediction in social science context |
| Causal forests | Wager, S. & Athey, S. (2018). "Estimation and Inference of Heterogeneous Treatment Effects Using Random Forests." *Journal of the American Statistical Association*, 113(523), 1228-1242. | Heterogeneous treatment effect estimation |
| SHAP | Lundberg, S.M. & Lee, S.-I. (2017). "A Unified Approach to Interpreting Model Predictions." *NeurIPS*. | SHAP values used for model interpretation |

#### Geospatial

| Method | Primary Citation | Cite When |
|--------|-----------------|-----------|
| Spatial autocorrelation | Anselin, L. (1995). "Local Indicators of Spatial Association--LISA." *Geographical Analysis*, 27(2), 93-115. | Moran's I or LISA computed |

#### Decomposition

| Method | Primary Citation | Cite When |
|--------|-----------------|-----------|
| Oaxaca-Blinder | Blinder, A.S. (1973). "Wage Discrimination: Reduced Form and Structural Estimates." *Journal of Human Resources*, 8(4), 436-455; Oaxaca, R. (1973). "Male-Female Wage Differentials in Urban Labor Markets." *International Economic Review*, 14(3), 693-709. | Oaxaca-Blinder decomposition performed |

#### Clustered Standard Errors

| Method | Primary Citation | Cite When |
|--------|-----------------|-----------|
| Clustering guidance | Abadie, A., Athey, S., Imbens, G.W., & Wooldridge, J.M. (2023). "When Should You Adjust Standard Errors for Clustering?" *Quarterly Journal of Economics*, 138(1), 1-35. | Clustered SEs used with explicit justification for clustering level |

### Reporting Standards

| Standard | Citation | Cite When |
|----------|----------|-----------|
| GUIDE-LLM | Feuerriegel, S. et al. (2026). "Generative AI Models in Science: Risks and Opportunities -- The GUIDE-LLM Checklist." | AI disclosure section present (always in DAAF reports) |
| Do No Harm Guide | Schwabish, J. & Feng, A. (2021). *Do No Harm Guide: Applying Equity Awareness in Data Visualization.* Urban Institute. | Equity-sensitive visualizations or race/ethnicity data |
| Causal language | Haber, N.A. et al. (2022). "Causal and Associational Language in Observational Health Research." *American Journal of Epidemiology*, 191(12), 2020-2028. | Causal claims made or explicitly hedged |

---

## Accumulation Protocol

1. **After each Stage 6 script:** Orchestrator extracts data source citation from research-executor output and appends to STATE.md > Citations Accumulated > Data Sources.
2. **After each Stage 7-8 script:** Orchestrator extracts method and software citations from research-executor output and appends to STATE.md > Citations Accumulated > Methodological References and/or Software & Tools. Deduplicate by checking if the citation already exists in STATE.md.
3. **At project setup:** Orchestrator pre-populates the DAAF, marimo, and GUIDE-LLM citations in STATE.md (these are always present).
4. **At Stage 11:** Report-writer reads STATE.md > Citations Accumulated as the primary source for the report's References section. Consults this file for verification if needed.
5. **At Stage 12:** Data-verifier checks that all accumulated citations appear in the report and that no uncited methods or tools are present.
