# Skill Catalog

This catalog provides quick-reference tables for identifying which skills to use when constructing subagent prompts or answering user questions about available data sources.

The education data source skills (`education-data-source-*`) listed below access data through the **Urban Institute Education Data Portal (EDP)**, not directly from original federal source agencies. The EDP curates, standardizes (lowercase variable names, integer-encoded categoricals, standardized missing values), and may subset the original source data. Each skill documents what is available through the Portal and notes any known gaps relative to the original data collection.

## Skill Quick Reference

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `education-data-explorer` | Find available data | Stage 2: Initial data exploration |
| `education-data-query` | Download data from mirrors | Stage 5: Data retrieval |
| `education-data-context` | Interpret data, handle caveats | Stage 6: Context application |
| `education-data-source-ccd` | CCD (NCES) | K-12 enrollment, school/district directory, staffing, finance |
| `education-data-source-ipeds` | IPEDS (NCES) | College enrollment, graduation rates, finance, institutional characteristics |
| `education-data-source-crdc` | CRDC (OCR) | School discipline, course access equity, civil rights indicators |
| `education-data-source-scorecard` | College Scorecard (ED) | Post-college earnings, student debt, repayment, completion |
| `education-data-source-edfacts` | EDFacts (NCES) | State assessment proficiency, graduation rates (ACGR) |
| `education-data-source-meps` | MEPS (Urban Institute) | School-level poverty estimates (superior to FRPL cross-state) |
| `education-data-source-saipe` | SAIPE (Census) | District-level poverty estimates, Title I allocations |
| `education-data-source-fsa` | FSA (ED) | Pell Grants, Direct Loans, PLUS, financial responsibility scores |
| `education-data-source-nhgis` | NHGIS (IPUMS) | Census geography crosswalks; demographic data via direct NHGIS only |
| `education-data-source-nccs` | NCCS (Urban Institute) | Private college Form 990 financial data |
| `education-data-source-pseo` | PSEO (Census LEHD) | Post-college employment outcomes, earnings by industry |
| `education-data-source-eada` | EADA (ED) | College athletics participation, coaching, revenue |
| `education-data-source-nacubo` | NACUBO | College endowment market values (7 cols in Portal; full study separate) |
| `education-data-source-campus-safety` | Campus Safety (ED) | Campus crime statistics (hate crimes only in Portal; full data via ED) |
| `election-data-source-countypres` | MEDSL (MIT) | County-level presidential election returns 2000-2024 (not EDP) |
| `data-scientist` | Methodology and rigor | All analysis stages; Data Ingest profiling (DI-3 through DI-6) |
| `polars` | DataFrame operations | Stage 7-8: Data transformation and statistical analysis |
| `plotnine` | Static visualization | Stage 8.2: Publication plots |
| `plotly` | Interactive visualization | Stage 8.2: Interactive plots |
| `marimo` | Reactive notebooks | General marimo development (Stage 9 uses notebook-assembler agent for COMPILATION only — NO dashboards) |

## Meta/Development Skills

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `skill-authoring` | Guide for creating Skills | When creating a new skill (including Data Ingest Stage DI-7), reviewing skill structure, or debugging skill loading issues |
| `agent-authoring` | Guide for creating Agents | When creating a new agent definition file or verifying agent integration |

## Skill Locations

All skills are located in `.claude/skills/[skill-name]/SKILL.md`.
