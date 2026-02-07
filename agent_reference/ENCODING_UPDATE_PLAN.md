# Portal Integer Encoding Update Plan

**Purpose:** Update all `education-data-source-*` skills to reflect actual Education Data Portal integer encodings instead of NCES raw file string codes.

**Created:** 2026-02-07
**Status:** In Progress
**Template Source:** CCD skill update (completed)

---

## Background

The Education Data Portal converts NCES categorical variables from strings to integers for cross-source consistency. Current skill documentation uses NCES string codes (e.g., `PK`, `KG`, `WH`, `BL`) which don't match Portal data (e.g., `-1`, `0`, `1`, `2`).

### Critical Encoding Gotchas

| Issue | Wrong | Correct | Notes |
|-------|-------|---------|-------|
| Grade totals | `grade == -99` | `grade == 99` | Positive 99 for totals |
| Grade Pre-K | `-1` = missing | `-1` = Pre-K | Context-dependent! |
| Race codes | `"WH"`, `"BL"` | `1`, `2` | Integers, not strings |
| Variable names | `MEMBER`, `GRADE` | `enrollment`, `grade` | Lowercase |

---

## Verification Protocol (Per Source)

Each source update follows this **double-verification** pattern:

### Step 1: Download Codebook
```bash
# Pattern: schools/{source}/codebook_{level}_{source}_{component}.xls
curl -sL "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/{path}" -o codebook.xls
```

### Step 2: Parse Codebook
```python
import xlrd
wb = xlrd.open_workbook("codebook.xls")

# Read variables sheet
variables = wb.sheet_by_name('variables')
# Read values sheet (coded values)
values = wb.sheet_by_name('values')

# Extract all format-specific codes
# Group by format column, list (code, label) pairs
```

### Step 3: Pull Actual Data Sample
```python
import polars as pl

# Pull small sample from HuggingFace mirror
url = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/{path}.parquet"
df = pl.read_parquet(url)

# Verify categorical columns match codebook
for col in categorical_columns:
    print(f"{col}: {df[col].unique().sort().to_list()}")
```

### Step 4: Cross-Verify
- Compare codebook values against actual data unique values
- Flag any discrepancies
- Document any values in data but not in codebook (and vice versa)

### Step 5: Update Skill Documentation
Apply CCD pattern:
1. Add Portal encoding warning at top of SKILL.md and variable-definitions.md
2. Convert all string code tables to integer code tables
3. Fix code examples to use correct integers
4. Add context-dependent warnings (e.g., `-1` meaning varies by format)
5. Update variable names to Portal lowercase format

### Step 6: Commit Changes
```bash
git add .claude/skills/education-data-source-{source}/
git commit -m "fix(skill): Update {source} to Portal integer encodings"
```

---

## Source Checklist

### Priority 1: Known Issues (from prior audit)

| # | Source | Codebook Path | Status | Issues Found |
|---|--------|---------------|--------|--------------|
| 1 | ~~CCD~~ | schools/ccd/* | DONE | Grade -1=Pre-K, 99=Total; race 1-7 |
| 2 | ~~PSEO~~ | college-university/pseo/* | DONE | degree_level 1-10, cipcode 2-digit ints. Fixed api-access.md |
| 3 | ~~FSA~~ | college-university/fsa/* | DONE | grant_type 1-5, loan_type 1-14. Fixed API endpoints |
| 4 | ~~NHGIS~~ | schools/nhgis/* | DONE | census_region 1-4, census_division 1-9. Fixed API URLs. |
| 5 | ~~NCCS~~ | college-university/nccs/* | DONE | fips integers, yes_no 0/1. Replaced get_data(). |
| 6 | ~~Campus Safety~~ | college-university/campus-safety/* | DONE | bias 1-9, crime_type 1-18. Full encoding documented. |

### Priority 2: Other Sources (need verification)

| # | Source | Codebook Path | Status | Issues Found |
|---|--------|---------------|--------|--------------|
| 7 | ~~IPEDS~~ | college-university/ipeds/* | DONE | CRITICAL: Fixed wrong race code order in completions-data.md. Added sex code 4. |
| 8 | ~~CRDC~~ | schools/crdc/* | DONE | race 1-7, sex 1-3, disability 0-4. Converted from strings. |
| 9 | ~~Scorecard~~ | college-university/scorecard/* | DONE | pred_deg 0-4, yes_no 0/1. Uses **nulls** not -1/-2/-3. |
| 10 | ~~EDFacts~~ | schools/edfacts/* | DONE | grade_edfacts 3-9/99, race 1-7, disability 0-4, lep 1/99. |
| 11 | ~~MEPS~~ | schools/meps/* | DONE | IDs are Int64 (not strings). Uses **nulls**. Years 2009-2022. |
| 12 | ~~SAIPE~~ | school-districts/saipe/* | DONE | fips integers (1-72), leaid integers (no leading zeros). Simple source. |
| 13 | ~~EADA~~ | college-university/eada/* | DONE | ath_classification_code 1-20. Standard -1/-2/-3 codes. |
| 14 | ~~NACUBO~~ | college-university/nacubo/* | DONE | Uses **nulls** for missing, not coded values. |

### Priority 3: Cross-Cutting Documentation

| # | File | Status | Notes |
|---|------|--------|-------|
| 15 | ~~`agent_reference/REFERENCE_TABLES.md`~~ | DONE | Added Portal integer encoding tables (race, sex, grade, missing patterns) |
| 16 | ~~`agent_reference/EDUCATION_DATA_API_LEARNINGS.md`~~ | DONE | Added encoding gotchas section with semantic trap warnings |
| 17 | ~~`education-data-context` skill~~ | DONE | Added encoding tables, fixed grade=-99→99, source-specific missing data |
| 18 | ~~`education-data-query` skill~~ | DONE | Added URL vs data value mapping, semantic trap warnings |

---

## Subagent Task Template

When delegating to subagents, use this prompt template:

```
You are updating the `education-data-source-{SOURCE}` skill to use Portal integer encodings.

**BASE_DIR:** /daaf
**Reference:** See completed CCD update as template: `.claude/skills/education-data-source-ccd/`

**Your Task:**

1. DOWNLOAD codebook from HuggingFace mirror:
   - List available codebooks: `curl -s "https://huggingface.co/api/datasets/brhkim/education_data_portal_mirror/tree/main?recursive=true" | python3 -c "import json,sys; [print(f['path']) for f in json.load(sys.stdin) if '{source}' in f['path'].lower() and f['path'].endswith('.xls')]"`
   - Download to scratchpad: `/tmp/claude-0/-daaf/39766586-3e8d-4f3f-ad23-c7cd6675717e/scratchpad/codebooks/`

2. PARSE codebook:
   - Read variables sheet (variable, format, label)
   - Read values sheet (format, code, code_label, code_desc)
   - Extract all format-specific integer codes

3. PULL data sample:
   - Download parquet from mirror
   - Check unique values in categorical columns
   - Verify against codebook

4. DOCUMENT findings:
   - List all categorical variables with their integer codes
   - Note any discrepancies between codebook and data
   - Identify which skill files need updates

5. UPDATE skill files:
   - Add Portal encoding warning (see CCD template)
   - Convert string code tables to integer tables
   - Fix any code examples
   - Update variable names to lowercase

**Output Format:**
Return a structured report with:
- Codebook analysis (variables, formats, codes)
- Data verification (unique values found)
- Discrepancies (if any)
- Files updated (list with summary of changes)
- Remaining issues (if any)
```

---

## Session Recovery

If context is exhausted, resume with:

```
Resume Portal encoding update work.

Plan: `/daaf/agent_reference/ENCODING_UPDATE_PLAN.md`
Completed: [list completed sources from checklist above]
Next: Source #{N} ({source name})

Continue with the verification protocol for the next source.
```

---

## Verification Evidence Format

For each source, create a verification log:

```markdown
## {SOURCE} Verification Log

**Date:** YYYY-MM-DD
**Codebook:** {path}
**Data Sample:** {path}

### Codebook Analysis

| Format | Code | Label |
|--------|------|-------|
| ... | ... | ... |

### Data Verification

| Column | Codebook Values | Actual Values | Match? |
|--------|-----------------|---------------|--------|
| ... | ... | ... | ... |

### Discrepancies

[None / List any issues]

### Files Updated

- [ ] SKILL.md
- [ ] references/variable-definitions.md
- [ ] references/*.md (other files as needed)

### Verification Status: PASSED / FAILED
```

---

## Notes

- **xlrd** is installed for reading .xls codebooks
- **Polars** is the standard DataFrame library
- HuggingFace mirror has complete coverage (489 parquet files, 89 codebooks)
- Some sources (NHGIS) may be external and not have Portal codebooks
- Cross-reference with `agent_reference/EDUCATION_DATA_API_LEARNINGS.md` for known issues
