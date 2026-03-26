# Data Source Skill Template

This document defines the **canonical structure** for all `*-data-source-*` skills. Every data source skill MUST follow this section order and formatting. The template ensures consistent subagent consumption, predictable section locations, and uniform quality across all 14+ data source skills.

**Audience:** Skill authors and agents performing skill maintenance.

---

## How to Use This Template

1. **New skills:** Copy the skeleton below, fill in source-specific content
2. **Existing skills:** Restructure to match the canonical section order — preserve all content, only reorganize
3. **Key rule:** No information loss during restructuring. Source-specific sections (e.g., CCD's "Grade -1 Encoding", EDFacts' "Cross-State Comparison" warning) become subsections within the standardized structure

---

## Canonical Section Order (MANDATORY)

Every data source SKILL.md MUST contain these sections in this exact order:

```
 1. Frontmatter (YAML)
 2. Title
 3. Summary paragraph
 4. Value Encodings Warnings (blockquote)
 5. ## What is [Source]?
 6. ## Reference File Structure
 7. ## Decision Trees
 8. ## Quick Reference: [Source-Specific]
 9. ## Data Access
10. ## Common Pitfalls
11. ## Related Data Sources
12. ## Topic Index
```

Optional sections (insert between 10 and 11 if needed):
- `## Limitations` — only if content doesn't fit naturally in Common Pitfalls
- `## Common Use Cases` — if the source has distinct research applications worth enumerating
- `## [Source-Specific Critical Section]` — e.g., EDFacts' cross-state warning, Scorecard's Title IV limitation
- `## Multi-File Structure` — for HIERARCHICAL data sources with multiple related files (see Section 11.5 in the annotated skeleton)

> **Section numbering note:** The annotated skeleton below numbers optional sections as 11 and 11.5, which shifts Related Data Sources and Topic Index to positions 12 and 13 in the skeleton. The **canonical count is 12 mandatory sections** (numbered 1–12 in the list above). In the final generated skill, if no optional sections are used, Related Data Sources is the 11th section and Topic Index is the 12th. The skeleton's higher numbers are an annotation artifact, not a different count.

---

## Annotated Skeleton

Everything below this line is the template. Annotations appear in `<!-- HTML comments -->` and should be removed in the final skill. Placeholder tokens appear in `[BRACKETS]` and must be replaced.

---

### Section 1: Frontmatter

```yaml
---
name: *-data-source-[acronym]
description: >-
  [Full source name] ([ACRONYM]) — [what it is and what it covers] ([year range]).
  Use when [specific research questions or data needs that should trigger this skill].
  [Key constraint: Portal-only data scope, coverage gap, or critical limitation.]
metadata:
  audience: any-agent
  domain: data-source
  skill-authored: "YYYY-MM-DD"      # Date this skill was first created
  skill-last-updated: "YYYY-MM-DD"  # Date this skill was last updated or re-verified
---
```

<!-- RULES:
  - name: must match the directory name exactly
  - NAMING CONVENTION: {content-domain}-data-source-{acronym}
    - {content-domain} groups related sources by subject area (education, election, health)
    - This is distinct from metadata.domain which categorizes the functional type ("data-source")
    - {acronym} is the standard abbreviation (CCD, IPEDS, CRDC) — not the full name
    - Examples: education-data-source-ccd, election-data-source-countypres
    - When a source has multiple tables, append a table identifier
      (e.g., education-data-source-ccd-schools)
  - description: max 1024 chars, no angle brackets (< >)
  - description: MUST include both "what it does" AND "when to use it"
  - description: MUST include approximate year coverage for the source (e.g., "2009-2022")
  - description: Front-load the source identity (name + what it is), NOT skill-document
    framing — write "Common Core of Data (CCD) — the federal universe database of..."
    not "Deep reference for the Common Core of Data (CCD)..."
  - description: Include Portal-specific data scope when it differs from the full source
    (e.g., "Portal mirror provides only 7 columns; full study requires separate access")
  - domain: ALWAYS use "data-source" for all data source skills
  - audience: ALWAYS use "any-agent" for data source skills
  - PROVENANCE (REQUIRED for all data source skills — stored as metadata keys):
    - skill-authored: ISO-8601 date when the skill was first created (never changes)
    - skill-last-updated: ISO-8601 date when the skill was last updated or re-verified
    - On updates: change skill-last-updated only; skill-authored remains fixed
    - STALENESS: If skill-last-updated is more than a few months old, treat skill
      claims with caution — data sources evolve and skill documentation may have drifted
-->

---

### Section 2: Title

```markdown
# [ACRONYM] Data Source Reference
```

<!-- RULES:
  - Format: "# [ACRONYM] Data Source Reference"
  - Examples: "# CCD Data Source Reference", "# IPEDS Data Source Reference"
  - NOT: "Education Data Source: [Name]", "[Name] Source Guide", "[Acronym]: [Full Name]"
  - Use the standard acronym, not the full name
-->

---

### Section 3: Summary Paragraph

```markdown
[One to two sentences describing the source's primary purpose and unique value.
Should orient the reader immediately — what this source provides that others don't.]
```

<!-- RULES:
  - Max 2 sentences
  - State the unique value proposition (why use THIS source vs. alternatives)
  - Do NOT repeat the frontmatter description verbatim
-->

---

### Section 4: Value Encodings Warnings (MANDATORY)

```markdown
> **CRITICAL: Value Encoding**
>
> Many data sources use **integer codes** for categorical variables, and some
> re-processed/cleaned datasets may adjust these in such a way that they
> differ from the [original source]'s [string codes / raw file formats].
> Always verify codes against codebooks whenever possible.
>
> | Context | [Example Field 1] | [Example Field 2] | [Example Field 3] |
> |---------|--------------------|--------------------|---------------------|
> | **Current source** | `[value]` | `[value]` | `[value]` |
> | [Original source] | `[value]` | `[value]` | `[value]` |
>
> See `./references/variable-definitions.md` for complete encoding tables.
```

<!-- RULES:
  - MANDATORY for every skill — no exceptions
  - MUST appear here (after summary, before "What is" section)
  - Include a comparison table showing at least 2-3 example encodings
  - Reference the variable-definitions.md file for complete mappings
  - If the source uses nulls instead of -1/-2/-3 codes, note that here
  - Do NOT place Truth Hierarchy here — it belongs in Section 9 (Data Access)
-->

---

### Section 4.5: Staleness Warning

> **Note:** This warning is NOT a separate section in the generated SKILL.md.
> It is guidance for agents and humans consuming the skill. The provenance
> metadata keys (`skill-authored`, `skill-last-updated`) are sufficient — this rule governs interpretation.

**Rule:** If `skill-last-updated` is **more than a few months old**, treat the
skill's claims about column definitions, coded values, suppression patterns,
and data quality with caution. Data sources evolve — new years are added,
schemas change, coded values are revised, and suppression thresholds shift.
When in doubt, re-run data-ingest to re-verify against fresh data.

---

### Section 5: What is [Source]?

```markdown
## What is [Source Full Name]?

[Optional 1-sentence intro if needed for context.]

- **[Attribute 1]**: [Value] (e.g., "Collector: National Center for Education Statistics (NCES)")
- **[Attribute 2]**: [Value] (e.g., "Coverage: ~100,000 public schools nationwide")
- **[Attribute 3]**: [Value] (e.g., "Frequency: Annual collection")
- **[Attribute 4]**: [Value] (e.g., "Available years: 1986-present")
- **[Attribute 5]**: [Value] (e.g., "Primary identifier: NCESSCH (12-digit school ID)")
```

<!-- RULES:
  - Use a bullet list with bold attribute keys
  - Include at minimum: who collects it, what it covers, coverage scope,
    frequency, available years, and primary identifier
  - NOT paragraphs, NOT numbered lists, NOT subsections
  - Keep to 5-8 bullets max
-->

---

### Section 6: Reference File Structure

```markdown
## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `[filename].md` | [What this file covers] | [Trigger: when would an agent need this] |
| `[filename].md` | [What this file covers] | [Trigger] |
| `variable-definitions.md` | Key variables, codes, special values | Interpreting specific data elements |
| `data-quality.md` | Known issues, suppression, limitations | Assessing data reliability |
```

<!-- RULES:
  - MUST be a 3-column table: File | Purpose | When to Read
  - Every skill should have at minimum: variable-definitions.md, data-quality.md, and analytical-context.md
  - File paths use backtick formatting
  - "When to Read" should be action-oriented (e.g., "Working with enrollment data")
-->

---

### Section 7: Decision Trees

```markdown
## Decision Trees

### [Primary decision tree title — e.g., "What data do I need?"]

```
[Research question or task]?
├─ [Option A] → ./references/[file].md
│   └─ [Sub-option] → ./references/[file].md#[section]
├─ [Option B] → ./references/[file].md
└─ [Option C] → ./references/[file].md
```

### [Secondary decision tree — e.g., "Is this a data quality issue?"]

```
[Situation]?
├─ [Scenario A] → [Action/Reference]
├─ [Scenario B] → [Action/Reference]
└─ [Scenario C] → [Action/Reference]
```
```

<!-- RULES:
  - Use ASCII tree diagrams inside code blocks
  - Include at least 2 decision trees (primary navigation + quality/validity check)
  - Leaf nodes should point to specific reference files or sections
  - Trees should cover the most common agent decision points for this source
-->

---

### Section 8: Quick Reference

```markdown
## Quick Reference: [Primary Domain Tables]

### [Source-Specific Subsection — e.g., "Key Variables", "Survey Components"]

| [Column 1] | [Column 2] | [Column 3] |
|-------------|-------------|-------------|
| [data] | [data] | [data] |

### Key Identifiers

| ID | Format | Level | Example | Notes |
|----|--------|-------|---------|-------|
| `[id_field]` | [format] | [School/District/Institution] | `[example]` | [notes] |

### Missing Data Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| `-1` | Missing | Data not reported |
| `-2` | Not applicable | Item doesn't apply to this entity |
| `-3` | Suppressed | Data suppressed for privacy |
| `null` | Not available | [If source uses nulls instead of/in addition to codes] |

### [Additional Source-Specific Subsections as needed]
```

<!-- RULES:
  - Section title: "## Quick Reference: [Descriptive Label]"
  - MUST include a "### Missing Data Codes" subsection (even if brief)
  - MUST include a "### Key Identifiers" subsection if the source has join keys
  - Source-specific content goes in additional ### subsections
  - Use tables for all quick-lookup content
  - Include categorical code tables here (race codes, type codes, etc.)
  - Source-critical warnings (e.g., CCD grade -1, IPEDS no inst_level 3)
    become ### subsections within Quick Reference
-->

---

### Section 9: Data Access

```markdown
## Data Access

### Dataset Paths

| Topic | Type | Path |
|-------|------|------|
| [Dataset name] | [Single/Yearly] | `[path/to/file]` |
| [Dataset name] | [Single/Yearly] | `[path/to/file_{year}]` |

### Codebooks

| Dataset | Codebook Path |
|---------|---------------|
| [Dataset name] | `[path/to/codebook_name]` |

> Codebooks are `.xls` files on both mirrors. See `datasets-reference.md` for the
> full catalog and `fetch-patterns.md` for `get_codebook_url()`. For human
> reference — not parsed programmatically.

### Example Fetch

```python
# Uses fetch_from_mirrors() from fetch-patterns.md — tries each mirror
# in priority order per mirrors.yaml and applies filters locally.
from fetch_utils import fetch_from_mirrors

df = fetch_from_mirrors(
    "[source]/[dataset_path]",
    filters={"fips": 6},  # California
    years=[[year]],
)
```

### Filtering

```python
# [Source-specific filtering examples]
# Show 2-3 common filter patterns relevant to this source
```
```

<!-- RULES:
  - Section name: ALWAYS "## Data Access" (not "Data Fetching", "API Gotchas", etc.)
  - TWO ACCESS MODELS: Choose the appropriate skeleton based on how the data is accessed:
    - MIRROR-BASED: Use the skeleton above (Dataset Paths, Codebooks, Example Fetch, Filtering)
    - API-BASED: Use the alternative skeleton below (Prerequisites, Dataset Endpoints,
      Example Fetch with API pattern, Data Persistence, Filtering)
    - A skill may include BOTH if the data is available through mirrors AND an API
  - MIRROR-BASED RULES:
    - MUST have all four subsections: Dataset Paths, Codebooks, Example Fetch, Filtering
    - Dataset Paths table: 3 columns (Topic | Type | Path) — canonical paths from datasets-reference.md
    - Codebooks table: 2 columns (Dataset | Codebook Path) + standard blockquote note
    - Example Fetch: ALWAYS use fetch_from_mirrors() pattern from fetch-patterns.md
    - Example Fetch: Include at least one filter (fips + year is the standard pattern)
  - API-BASED RULES:
    - MUST have Prerequisites subsection if authentication is required
    - MUST have Example Fetch using os.environ for API key (NEVER hardcode keys)
    - MUST have Data Persistence subsection documenting both local-storage and
      live-query patterns when the source supports API access
    - The election-data-source-countypres skill is the reference implementation
      for the API access pattern
  - COMMON RULES (both models):
    - Filtering subsection: Show source-specific filter patterns
    - The Filtering subsection can be omitted ONLY if Example Fetch already shows
      all common filter patterns (to avoid redundancy)
    - MUST include Truth Hierarchy blockquote in this section (after Codebooks/Endpoints,
      before Example Fetch). This is the CANONICAL location for Truth Hierarchy across
      all skills. Use this exact format:
        > **Truth Hierarchy:** When interpreting variable values, apply this priority:
        > 1. **Actual data file** (what you observe in the parquet/CSV) — this IS the truth
        > 2. **Live codebook** (.xls in mirror) — authoritative documentation, may lag
        > 3. **This skill documentation** — convenient summary, may drift from codebook
        >
        > If this documentation contradicts the codebook, trust the codebook.
        > If the codebook contradicts observed data, trust the data and investigate.
-->

#### Alternative Skeleton: API-Based Data Access

Use this skeleton instead of (or in addition to) the mirror-based skeleton above when the data source is accessed via API:

```markdown
## Data Access

### Prerequisites

> **API Key Required:** This data source requires authentication.
> Set the `[ENV_VAR_NAME]` environment variable before launching Claude Code.
> See the Installation Guide (Step 8) for setup instructions.

| Requirement | Details |
|-------------|---------|
| Environment variable | `[ENV_VAR_NAME]` |
| Where to get a key | [URL + brief instructions] |
| Rate limits | [if known, or "Unknown"] |

### Dataset Endpoints

| Dataset | Endpoint / DOI | Format | Notes |
|---------|---------------|--------|-------|
| [name] | [URL or DOI] | [TSV/JSON/CSV/Parquet] | [notes] |

> **Truth Hierarchy:** When interpreting variable values, apply this priority:
> 1. **Actual data file** (what you observe in the downloaded data) — this IS the truth
> 2. **API documentation / codebook** — authoritative, may lag behind actual data
> 3. **This skill documentation** — convenient summary, may drift from source docs
>
> If this documentation contradicts the API docs, trust the API docs.
> If the API docs contradict observed data, trust the data and investigate.

### Example Fetch

```python
import os, io, requests
import polars as pl

# --- Config ---
API_KEY = os.environ["[ENV_VAR_NAME]"]
ENDPOINT = "[base_url/endpoint]"

# --- Fetch ---
# INTENT: Download [dataset] via [API name]
# ASSUMES: API key is set in environment
r = requests.get(ENDPOINT, params={"key": API_KEY})
r.raise_for_status()
df = pl.read_csv(io.BytesIO(r.content), separator="\t")

# --- Validate ---
print(f"Shape: {df.shape}")
assert df.shape[0] > 0, "STOP: Empty response from API"
```

### Data Persistence

**Local storage (download once, then use local file):**
```python
# Save to project data/raw/ after fetching
df.write_parquet(f"{DATA_DIR}/raw/{DATE}_{source}_{dataset}.parquet")
# Subsequent scripts load from local parquet — no API access needed
```

**Live query (fetch from API each time):**
```python
# Include the full API call pattern above in each Stage 5 script
# Data is always current but requires API access and a valid key
# Consider saving a local backup for offline use
```

### Filtering

```python
# [Source-specific filtering examples after download]
# All filtering is done locally with Polars after the API response is received
```
```

---

### Section 10: Common Pitfalls

```markdown
## Common Pitfalls

| Pitfall | Issue | Solution |
|---------|-------|----------|
| [Short name] | [What goes wrong] | [How to fix or avoid] |
| [Short name] | [What goes wrong] | [How to fix or avoid] |
| [Short name] | [What goes wrong] | [How to fix or avoid] |
```

<!-- RULES:
  - MUST be a 3-column table: Pitfall | Issue | Solution
  - NOT bullet lists, NOT "Do/Don't" format, NOT numbered lists
  - Include at minimum 3 pitfalls (every source has at least 3 gotchas)
  - Every skill should include "Using string codes" pitfall if applicable
  - Include source-specific pitfalls (e.g., CCD's FRPL, IPEDS' GASB/FASB)
  - If content currently exists as "Common Analysis Mistakes", "Important Caveats",
    etc., restructure into this table format
-->

---

### Section 11 (Optional): Additional Sections

```markdown
## [Source-Specific Critical Section]
```

<!-- RULES:
  - Place between Common Pitfalls and Related Data Sources
  - Use for content that doesn't fit naturally in other sections, such as:
    - EDFacts: "CRITICAL WARNING: Cross-State Comparisons" (with Valid/Invalid examples)
    - Scorecard: "Critical Limitation: Title IV Recipients Only"
    - Scorecard: "Comparison: Scorecard vs IPEDS"
    - CCD: "Coverage Notes" (What CCD Includes / Excludes)
    - MEPS: "Why MEPS Instead of FRPL?"
    - SAIPE: "Poverty Definition"
  - If a source has key comparison tables (e.g., PSEO vs Scorecard vs State Systems),
    place them here
  - This section is OPTIONAL — only use when content is critical and doesn't belong
    in Quick Reference or Common Pitfalls
-->

---

### Section 11.5 (Optional): Multi-File Structure

Use this section when the data source comprises multiple related files at different levels of aggregation (HIERARCHICAL file structure from Data Onboarding).

```markdown
## Multi-File Structure

> This data source comprises multiple related files at different levels
> of aggregation. Load the appropriate file(s) for your analysis level.

### Schema Map

| File / Table | Entity Type | Grain | Row Count | Key Column(s) |
|-------------|-------------|-------|-----------|---------------|
| [file/table 1] | [e.g., Schools] | One row per school per year | [N] | `[key]` |
| [file/table 2] | [e.g., Districts] | One row per district per year | [N] | `[key]` |

### Entity Hierarchy

```
[Level 1: States]
    └─ [Level 2: Districts] (linked by state_fips)
        └─ [Level 3: Schools] (linked by leaid)
```

### Join Patterns

```python
# Join schools to districts
schools_with_district = schools.join(
    districts,
    on="leaid",
    how="left",
    suffix="_district"
)
# ASSUMES: leaid is present in both files
# WARNING: Check for leaid values in schools that have no district match
unmatched = schools_with_district.filter(pl.col("col_district").is_null()).shape[0]
print(f"Join coverage: {len(schools_with_district) - unmatched} / {len(schools_with_district)}")
```

### Cross-Level Caveats

| Caveat | Affected Levels | Impact |
|--------|----------------|--------|
| [e.g., "Not all schools have district records"] | Schools → Districts | [X]% of school rows lose district data on join |
| [e.g., "District aggregates don't sum to state totals"] | Districts → States | State file uses independent estimates |
```

<!-- RULES:
  - ONLY include for sources with HIERARCHICAL file structure (multiple files
    at different aggregation levels)
  - Do NOT include for SINGLE or HORIZONTAL file structures
  - Schema Map MUST include all files/tables with grain description and key columns
  - Entity Hierarchy MUST use ASCII tree diagram showing parent-child relationships
  - Join Patterns MUST include working Polars code with:
    - Explicit join type (left, inner, etc.) with rationale
    - Validation check (count unmatched rows)
    - IAT comments (ASSUMES, WARNING)
  - Cross-Level Caveats MUST document known join issues discovered during profiling
    (from script 07b cross-level-linkage findings)
  - Place between Common Pitfalls / Additional Sections and Related Data Sources
-->

---

### Section 12: Related Data Sources

```markdown
## Related Data Sources

| Source | Relationship | When to Use |
|--------|--------------|-------------|
| `[skill-name]` | [How it relates] | [When to use the other source instead/together] |
| `education-data-explorer` | Parent discovery skill | Finding available endpoints |
| `education-data-query` | Data fetching | Downloading parquet/CSV files |
```

<!-- RULES:
  - Section name: ALWAYS "## Related Data Sources"
  - NOT "Related Skills and Tools", "Cross-Reference to Related Skills", etc.
  - 3-column table: Source | Relationship | When to Use
  - ALWAYS include the domain's explorer and query skill rows (e.g., `education-data-explorer` and `education-data-query` for education)
  - Include complementary data sources (e.g., CCD includes CRDC, SAIPE, MEPS)
  - Include join key information if relevant (e.g., "Join on unitid")
-->

---

### Section 13: Topic Index

```markdown
## Topic Index

| Topic | Reference File |
|-------|---------------|
| [Topic name] | `./references/[file].md` |
| [Topic name] | `./references/[file].md` |
```

<!-- RULES:
  - MUST be the LAST section in the file
  - ALWAYS 2 columns: Topic | Reference File
  - NOT 3 columns (remove any "Section" column — e.g., CRDC currently has 3)
  - Reference file paths use backtick formatting with ./references/ prefix
  - Group related topics together (all topics from same file adjacent)
  - This is the comprehensive lookup table — every reference file topic should appear
-->

---

## Size Guidelines

**Line guidance:** Target 250-400 lines for SKILL.md. Skills over 500 lines should split content into reference files. This is a guideline, not a strict rule — clarity and completeness take priority over line count.

| Metric | Target | Hard Limit |
|--------|--------|------------|
| Total SKILL.md lines | 250-400 | 500 |
| Frontmatter description | 100-200 chars | 1024 chars |
| Summary paragraph | 1-2 sentences | 3 sentences |
| Decision trees | 2-4 trees | 6 trees |
| Quick Reference subsections | 3-6 | 10 |
| Common Pitfalls rows | 3-8 | 12 |
| Topic Index rows | 10-30 | 50 |

### Reference File Density Guidelines

Reference files are loaded on-demand (Level 3 progressive disclosure), meaning their token cost is only incurred when an agent actually needs that information. This makes them the ideal location for comprehensive, detailed documentation — the token budget pressure that applies to SKILL.md (which is loaded whenever the skill triggers) does NOT apply to reference files.

**Principle: SKILL.md is the concise navigation hub; reference files are the comprehensive knowledge base.**

| Metric | Target | Floor |
|--------|--------|-------|
| Total reference file lines | 3-6x SKILL.md lines | 2x SKILL.md lines |
| columns.md lines per column | 3-5 lines | 2 lines |
| coded-values.md | All coded values enumerated | Top values only is insufficient |
| data-quality.md | All profiling anomalies cataloged | 150+ lines for complex sources |
| variable-definitions.md | Semantic families with examples | 150+ lines |
| Topic-specific files | 1 per major analytical domain | 0 (but encouraged) |

**Benchmark:** The hand-authored education data source skills average ~2,200 lines of reference content across 5-8 files, with individual files averaging ~400 lines. Skills authored by the data-ingest pipeline should aim toward this benchmark.

**Standard reference files for data source skills:**

| File | Content | Required? |
|------|---------|-----------|
| `columns.md` | Full column definitions, types, null rates, value ranges | Yes |
| `coded-values.md` | All coded/sentinel value mappings | Yes |
| `data-quality.md` | Anomalies, suppression, quality observations | Yes |
| `variable-definitions.md` | Semantic families, derived metrics, join guidance | Yes |
| `analytical-context.md` | Study design, population coverage, valid/invalid analyses, limitations by research context, alternative sources | Yes |
| Topic-specific files | Deep coverage of major analytical domains | When applicable |

**What belongs in reference files (not SKILL.md):**
- Complete column-by-column documentation
- Full coded value enumeration tables
- Methodology explanations and limitations for specific analytical domains
- Worked examples showing valid vs. invalid analysis patterns
- Historical context (schema changes across years, policy transitions)
- Cross-source comparison guidance for related datasets
- Study/survey design context that researchers need for proper interpretation

**Content quality target:** Reference files should be approximately 40-60% interpretive/
analytical guidance (why limitations exist, how they affect specific analyses, what
alternatives exist, when comparisons are valid vs invalid) and 40-60% factual data
description (code tables, column definitions, value enumerations). Avoid reference files
that are purely factual data dumps — these are less useful than the raw data itself.

---

## Checklist for Compliance

Use this checklist when reviewing a skill for template compliance:

- [ ] Frontmatter: `domain: data-source` (all data source skills use this functional category)
- [ ] Frontmatter: description includes "what" AND "when to use" AND approximate year coverage
- [ ] Frontmatter: description front-loads source identity (not "Deep reference for...")
- [ ] Frontmatter: `skill-authored` and `skill-last-updated` present as metadata keys with ISO-8601 dates
- [ ] Title: `# [ACRONYM] Data Source Reference` format
- [ ] Summary: 1-2 sentences after title
- [ ] Value Encodings Warnings: blockquote in position 4 with comparison table
- [ ] "What is" section: bullet list with bold keys
- [ ] Reference File Structure: 3-column table present
- [ ] Decision Trees: at least 2 trees in code blocks
- [ ] Quick Reference: includes Missing Data Codes subsection
- [ ] Data Access: has Dataset Paths table + Codebooks table + Example Fetch code
- [ ] Data Access: includes Truth Hierarchy blockquote (not in Value Encoding section)
- [ ] Common Pitfalls: 3-column table format (Pitfall | Issue | Solution)
- [ ] Related Data Sources: 3-column table, includes explorer + query skills
- [ ] Topic Index: 2-column table as final section
- [ ] No content lost from original (spot-check source-specific sections)
- [ ] Total SKILL.md lines under 500
- [ ] Reference files collectively total >= 2x SKILL.md lines (3x+ preferred)
- [ ] columns.md covers ALL columns, not just a subset
- [ ] coded-values.md enumerates ALL coded/sentinel values
- [ ] If API-based: Prerequisites subsection present with env var name and setup link
- [ ] If API-based: Data Persistence subsection documents both local and live patterns
- [ ] If API-based: Example Fetch uses `os.environ` (never hardcodes keys)
- [ ] If multi-file (HIERARCHICAL): Multi-File Structure section present with Schema Map
- [ ] If multi-file (HIERARCHICAL): Join Patterns include working Polars code with validation
- [ ] If multi-file (HIERARCHICAL): Cross-Level Caveats table populated from 07b findings
