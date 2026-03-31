# Learnings: College Graduation Rate & Selectivity Analysis

**Date:** 2026-03-29
**Data Sources:** IPEDS (Directory, Admissions, Grad Rates, Fall Enrollment Race, Student-Faculty Ratio, Finance, Fall Retention), FSA (Grants)
**Analysis Type:** Descriptive cross-sectional analysis with supplementary regression — graduation rate variation by institutional selectivity, student composition, resources, and sector

---

## What Worked Well

Approaches that succeeded and should be reused:

- **Parallel wave dispatch** for fetch and clean tasks — 3-5 subagents at a time kept throughput high
- **Smart dedup** for IPEDS GRS: sort by completion_rate descending (nulls last), then unique(keep="first") — preserved all 1,949 valid rates
- **Exact column names** over pattern-matching — the finance column `exp_instruc_total` would have been missed by searching for "instruction"

---

## What Didn't Work

Approaches that failed, with explanations:

- **FSA Grants for Pell data** — `grant_recipients_unitid` is 100% NULL for 2020-2021 in the Portal mirror. Took 5 script versions before confirming the data is simply unavailable. Resolution: IPEDS SFA grants/net-price endpoint as proxy.
- **Pattern-matching for IPEDS finance columns** — searching for "instruction"/"expend"/"expense" missed `exp_instruc_total` because it uses the abbreviation "instruc". Always log ALL column names first.
- **Naive dedup for IPEDS GRS** — `unique(keep="first")` without sorting lost valid completion rates because null-rate rows were sometimes first. Required sorting by rate descending before dedup.

---

## Surprises

Unexpected findings about data, access, or methodology:

- **`open_public` is NOT open admissions** — it means "open to the general public" (i.e., operating institution). Harvard has open_public=1. The actual open-admissions variable (`OPENADMP`) is missing from the Portal mirror.
- **Education Data Portal stores rates as 0-1 proportions** — both graduation rates and retention rates needed rescaling to 0-100. The original IPEDS surveys collect percentages, but the Portal normalizes them.
- **IPEDS GRS has duplicate rows per institution** within the same subcohort/level/race/sex/year, differing in `cohort_rev` and related count columns. Not documented in the skill.
- **SFA type_of_aid=9 captures ALL grant/scholarship recipients** (median ratio to total students = 0.984), not Pell-specific. Near-universal — will overestimate "Pell share."

---

## Access/Data Gotchas

Specific issues with data sources worth documenting:

### IPEDS

- `open_public` (from `openpubl`) = "open to general public" — NOT open admissions. The API has `open_admissions` but the mirror parquet omits it.
- Subcohort codes in GRS: {1, 2, 99}. Subcohort=2 = bachelor's-seeking at 4-year institutions (~2,010 institutions).
- `completion_rate_150pct` and `retention_rate` are 0-1 proportions in the Portal (not 0-100).
- Finance column naming uses `exp_instruc_total` (abbreviated "instruc"), not "instruction". The `exp_*` family has 27 expenditure columns.
- `est_fte` has 39 zeros among 6,857 institutions — must filter before division.
- SFA `sfa_grants_and_net_price`: type_of_aid=9 has grant data; type_of_aid=3 has net price only. Income_level=99 is verified institution total. 6 rows per unitid (5 income levels + total).
- Retention: ftpt has 3 values {1=FT, 2=PT, 99=Total}; PT has 48.8% null rate vs FT 11.2%.
- Admissions: sex==99 for totals; ~1,989 institutions report (open-admissions exempt).
- No coded missing values (-1/-2/-3) were found in most 2020 datasets — the Portal may pre-clean these.
- SFA match rate to 4-year degree-granting institutions is ~77% (below 80% expectation); SFA universe is broader than the filtered 4-yr core.
- Retention null rate compounds across joins: 14.6% key-miss + 11.2% pre-existing nulls → 28.1% total null in merged dataset.
- Finance per-FTE for specialized professional schools (law, medical, optometry) produces extreme outliers ($1M-$14M/FTE); mean shifts 68.6% when removed. Log-transform or winsorize for regression.
- "Highly Selective" band (admit_rate <25%) yields N=71 in analysis population; Plan's N≥100 per band is not achievable for this category.
- DeVry University-Missouri (unitid 482538) has admit_rate=0.0% from 2 applications/0 admissions — classified Highly Selective but is a for-profit data artifact.

### FSA

- `grant_recipients_unitid` is 100% NULL for Pell (grant_type==1) in 2020-2021. Disbursement amounts also appear to be null. The endpoint is unusable for recent Pell data.

---

## Time Sinks

What took longer than expected and how to avoid:

- **plotnine API compatibility** — 8 of 13 Stage 8 visualization scripts required revisions (19 total revisions across Stage 8). Root cause: plotnine differs from ggplot2 in several ways (`stat_summary` requires callable not string, `guide=False` deprecated, R color names like `gray40` not recognized, `guide_colorbar()` parameters differ). Optimization: create a plotnine gotchas reference or test palette/stat calls before full script.
- **FSA Pell data dead end** — 5 script versions for Task 1.4 before confirming FSA `grant_recipients_unitid` is 100% NULL for 2020-2021. Should check Portal data availability with a small sample query before writing a full fetch script.
- **Quintile label mismatch** — Polars `qcut()` produces labels like "Q1 (Lowest)" not bare "Q1". Both cross-tab scripts (7.2, 7.3) failed v1 for this reason. Always inspect actual label values from upstream before hardcoding.

---

## Reusable Patterns

Code snippets, queries, or approaches to extract for reuse:

### Smart Dedup for IPEDS GRS
**Use case:** When IPEDS grad rates have multiple rows per institution within the same subcohort
```python
# Sort by completion_rate descending (nulls last), then unique
df = df.sort("completion_rate_150pct", descending=True, nulls_last=True).unique(subset=["unitid"], keep="first")
```
**Notes:** Naive `unique(keep="first")` may keep null-rate rows; always sort by the target variable first.

---

## Data Quality Notes

Issues specific to this dataset/analysis:

| Variable | Issue | Rate | Handling |
|----------|-------|------|----------|
| completion_rate_150pct | 0-1 proportion scale | 100% | Rescaled to 0-100 in Stage 6 |
| retention_rate | 0-1 proportion scale | 100% | Rescaled to 0-100 in Stage 6 |
| grant_recipients (SFA) | All-grant proxy, not Pell-specific | 100% | Documented as limitation |
| instr_expend_per_fte | Extreme outliers up to $14.1M | 0.6% >$200K | Winsorize in regression |
| retention_rate (FT) | Null values | 11.2% | Preserved as null for LEFT join |
| admit_rate | Null for 23 institutions | 1.2% | Institutions with 0 applicants |

---

## Questions for Future Investigation

Open questions raised by this analysis:

- [ ] Is retention rate partially tautological with graduation rate? A student retained after year 1 is on the path to graduating — the R² jump from M2→M3 may be mechanically inflated.
- [ ] What explains the for-profit sign reversal (r=+0.26)? Is it genuine or an artifact of small N (52 plottable institutions)?
- [ ] Why does the Pell gap reverse at the Open/Less Selective band? High-Pell open institutions graduate more than low-Pell — is this a compositional effect (sector mix) or genuine?
- [ ] SFA `grant_recipients` appears to be first-time count, not total Pell enrollment — is this confirmed in the SFA documentation?

---

## Recommendations for Similar Analyses

If someone were to do a similar analysis:

1. **Start with:** IPEDS Directory filtered to 4-yr degree-granting as the universe; LEFT join everything onto it
2. **Watch out for:** `open_public` does NOT mean open admissions; FSA Pell data is dead for recent years (use SFA); IPEDS rates are 0-1 proportions not 0-100
3. **Don't bother with:** College Scorecard via Portal (key demographics missing); FSA Pell grants for 2020+ (100% NULL)
4. **Make sure to:** Log-transform instr_expend_per_fte before regression (outliers to $14.1M); verify Polars qcut label format before string matching; always check column names with value_counts before assuming names from documentation

---

## System Update Action Plan

*Generated at project completion. Each item maps a learning to a specific system file with a proposed change. This plan is NOT auto-executed — it serves as a work queue for future system maintenance.*

### Priority Legend
- **P1 (High):** Prevents incorrect results in future analyses
- **P2 (Medium):** Improves efficiency or clarity
- **P3 (Low):** Nice-to-have improvement

### Action Items

| # | Learning | Target File | Change Type | Proposed Change | Priority |
|---|---------|-------------|-------------|-----------------|----------|
| 1 | `open_public` means "open to public" not "open admissions"; OPENADMP missing from Portal | `.claude/skills/education-data-source-ipeds/SKILL.md` | Add | Add warning in admissions section: "`open_public` = operating status, NOT open-admissions indicator. Portal lacks `OPENADMP`." | P1 |
| 2 | FSA `grant_recipients_unitid` is 100% NULL for Pell (grant_type==1) in 2020-2021 | `.claude/skills/education-data-source-fsa/SKILL.md` | Add | Add data availability note: "Pell grant_recipients NULL for 2020+; use IPEDS SFA as proxy." | P1 |
| 3 | IPEDS GRS subcohort codes {1,2,99} not documented in skill | `.claude/skills/education-data-source-ipeds/SKILL.md` | Add | Add GRS coded values: subcohort 1=degree/certificate-seeking, 2=bachelor's-seeking at 4-yr, 99=total | P1 |
| 4 | Education Data Portal stores rates as 0-1 proportions (not 0-100) | `.claude/skills/education-data-context/SKILL.md` | Clarify | Add explicit note: "Portal normalizes rates to 0-1 proportions; IPEDS source surveys use 0-100 percentages" | P2 |
| 5 | SFA type_of_aid=9 is all-grant, not Pell-specific; produces pell_share ~0.12 vs expected ~0.30 | `.claude/skills/education-data-source-ipeds/SKILL.md` | Add | Add SFA caveat: "type_of_aid=9 captures ALL grant/scholarship aid; for Pell-specific, use FSA (pre-2020) or Scorecard bulk download" | P1 |
| 6 | plotnine API diverges from ggplot2 in several ways | `.claude/skills/plotnine/SKILL.md` | Add | Add gotchas section: stat_summary requires callable; guide=False deprecated (use legend_position="none"); R color names not valid; guide_colorbar params differ | P2 |
| 7 | Report-writer introduced 8+ numerical transcription errors | `.claude/agents/report-writer.md` | Add | Add verification step: "After drafting, verify EVERY numerical claim against source script execution logs before returning" | P1 |
| 8 | Polars qcut() labels include descriptive suffixes ("Q1 (Lowest)") | `.claude/skills/polars/SKILL.md` | Add | Add note: "qcut() with labels produces 'Q1 (Lowest)', 'Q5 (Highest)' etc.; inspect actual values before string matching" | P2 |

### Grouped by Target

#### Skills (`.claude/skills/*/SKILL.md`)
- [ ] education-data-source-ipeds: Add open_public warning, GRS subcohort codes, SFA type_of_aid caveat (from #1, #3, #5)
- [ ] education-data-source-fsa: Add Pell data availability note for 2020+ (from #2)
- [ ] education-data-context: Add Portal 0-1 proportion note (from #4)
- [ ] plotnine: Add API divergence gotchas section (from #6)
- [ ] polars: Add qcut label format note (from #8)

#### Agents (`.claude/agents/*.md`)
- [ ] report-writer: Add numerical verification step (from #7)

### Not Actionable (Context Only)
- Finance outliers at professional schools ($14.1M/FTE) — project-specific; already handled via log-transform
- HS band N=71 — inherent to US higher ed structure; no framework change needed
- For-profit sign reversal — interesting finding but too context-specific for framework guidance
