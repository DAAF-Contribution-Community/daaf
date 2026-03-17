# Skill Catalog

This catalog provides quick-reference tables for identifying which skills to use when constructing subagent prompts or answering user questions about available data sources.

## Skill Quick Reference

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `education-data-explorer` | Find available data | Stage 2: Initial data exploration |
| `education-data-query` | Download data from mirrors | Stage 5: Data retrieval |
| `education-data-context` | Interpret data, handle caveats | Stage 6: Context application |
| `education-data-source-ccd` | CCD-specific knowledge | K-12 public school/district data |
| `education-data-source-ipeds` | IPEDS-specific knowledge | College/university data |
| `education-data-source-crdc` | CRDC-specific knowledge | Civil rights/discipline data |
| `education-data-source-scorecard` | Scorecard-specific knowledge | Post-college outcomes |
| `education-data-source-edfacts` | EDFacts-specific knowledge | State assessment/graduation data |
| `education-data-source-meps` | MEPS-specific knowledge | School-level poverty estimates |
| `education-data-source-saipe` | SAIPE-specific knowledge | District-level poverty estimates |
| `education-data-source-fsa` | FSA-specific knowledge | Federal student aid data |
| `education-data-source-nhgis` | NHGIS-specific knowledge | Census/demographic data |
| `education-data-source-nccs` | NCCS-specific knowledge | Private college 990 data |
| `education-data-source-pseo` | PSEO-specific knowledge | Post-college employment outcomes |
| `education-data-source-eada` | EADA-specific knowledge | College athletics data |
| `education-data-source-nacubo` | NACUBO-specific knowledge | College endowment data |
| `education-data-source-campus-safety` | Campus Safety knowledge | Campus crime statistics |
| `data-scientist` | Methodology and rigor | All analysis stages |
| `polars` | DataFrame operations | Stage 7-8: Data transformation and statistical analysis |
| `plotnine` | Static visualization | Stage 8.2: Publication plots |
| `plotly` | Interactive visualization | Stage 8.2: Interactive plots |
| `marimo` | Reactive notebooks | General marimo development (Stage 9 uses notebook-assembler agent for COMPILATION only — NO dashboards) |

## Meta/Development Skills

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `skill-authoring` | Guide for creating Skills | When creating a new skill, reviewing skill structure, or debugging skill loading issues |
| `agent-authoring` | Guide for creating Agents | When creating a new agent definition file or verifying agent integration |

## Data Source Quick Lookup

| Data Need | Primary Source | Skill |
|-----------|----------------|-------|
| K-12 enrollment | CCD | `education-data-source-ccd` |
| K-12 finance | CCD | `education-data-source-ccd` |
| School discipline | CRDC | `education-data-source-crdc` |
| School poverty | MEPS, SAIPE | `education-data-source-meps`, `education-data-source-saipe` |
| College enrollment | IPEDS | `education-data-source-ipeds` |
| College graduation rates | IPEDS | `education-data-source-ipeds` |
| Post-college earnings | Scorecard, PSEO | `education-data-source-scorecard`, `education-data-source-pseo` |
| State assessments | EDFacts | `education-data-source-edfacts` |
| College athletics | EADA | `education-data-source-eada` |
| College endowments | NACUBO | `education-data-source-nacubo` |
| Campus crime | Campus Safety | `education-data-source-campus-safety` |
| Private college 990 data | NCCS | `education-data-source-nccs` |
| Federal student aid | FSA | `education-data-source-fsa` |
| Census/demographic data | NHGIS | `education-data-source-nhgis` |
| County presidential returns | MEDSL | `election-data-source-countypres` |

## Skill Locations

All skills are located in `.claude/skills/[skill-name]/SKILL.md`.
