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
- `## [Source-Specific Critical Section]` — e.g., EDFacts' cross-state warning, Scorecard's Title IV limitation. Place after Common Pitfalls, before Related Data Sources.

---

## Annotated Skeleton

Everything below this line is the template. Annotations appear in `<!-- HTML comments -->` and should be removed in the final skill. Placeholder tokens appear in `[BRACKETS]` and must be replaced.

---

### Section 1: Frontmatter

```yaml
---
name: *-data-source-[acronym]
description: >-
  [Full source name] ([ACRONYM]) [what it covers]. Use when [specific trigger
  conditions — what research questions or data needs should cause this skill
  to be loaded]. [One sentence on key limitation or scope if critical.]
metadata:
  audience: data-analysts
  domain: education-data  # Use your active domain identifier (e.g., "education-data", "health-data")
provenance:
  skill_authored: "YYYY-MM-DD"      # Date this skill was first created
  skill_last_updated: "YYYY-MM-DD"  # Date this skill was last updated or re-verified
---
```

<!-- RULES:
  - name: must match the directory name exactly
  - NAMING CONVENTION: {domain}-data-source-{acronym}
    - {domain} groups related sources and must match metadata.domain
    - {acronym} is the standard abbreviation (CCD, IPEDS, CRDC) — not the full name
    - Examples: education-data-source-ccd, election-data-source-countypres
    - When a source has multiple tables, append a table identifier
      (e.g., education-data-source-ccd-schools)
  - description: max 1024 chars, no angle brackets (< >)
  - description: MUST include both "what it does" AND "when to use it"
  - domain: ALWAYS use a consistent domain identifier for your domain (e.g., "education-data" for education; not variants like "education-civil-rights")
  - audience: ALWAYS use "data-analysts" for source skills
  - PROVENANCE (REQUIRED for all data source skills):
    - skill_authored: ISO-8601 date when the skill was first created (never changes after initial authoring)
    - skill_last_updated: ISO-8601 date when the skill was last updated or re-verified against data
    - On updates: change skill_last_updated only; skill_authored remains fixed
    - STALENESS: If skill_last_updated is more than a few months old, treat skill
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
> dates in frontmatter are sufficient — this rule governs interpretation.

**Rule:** If `skill_last_updated` is **more than a few months old**, treat the
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
  - Every skill should have at minimum: variable-definitions.md and data-quality.md
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
  - MUST have all four subsections: Dataset Paths, Codebooks, Example Fetch, Filtering
  - Dataset Paths table: 3 columns (Topic | Type | Path) — canonical paths from datasets-reference.md
  - Codebooks table: 2 columns (Dataset | Codebook Path) + standard blockquote note
  - Example Fetch: ALWAYS use fetch_from_mirrors() pattern from fetch-patterns.md
  - Example Fetch: Include at least one filter (fips + year is the standard pattern)
  - Filtering subsection: Show source-specific filter patterns (e.g., grade codes for CCD)
  - If a source has data NOT available via mirrors, note that explicitly
  - The Filtering subsection can be omitted ONLY if Example Fetch already shows
    all common filter patterns (to avoid redundancy)
  - MUST include Truth Hierarchy blockquote in this section (after Codebooks, before
    Example Fetch). This is the CANONICAL location for Truth Hierarchy across all skills.
    Use this exact format:
      > **Truth Hierarchy:** When interpreting variable values, apply this priority:
      > 1. **Actual data file** (what you observe in the parquet/CSV) — this IS the truth
      > 2. **Live codebook** (.xls in mirror) — authoritative documentation, may lag
      > 3. **This skill documentation** — convenient summary, may drift from codebook
      >
      > If this documentation contradicts the codebook, trust the codebook.
      > If the codebook contradicts observed data, trust the data and investigate.
-->

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

**Line guidance:** Target 200-350 lines for SKILL.md. Skills over 500 lines should split content into reference files. This is a guideline, not a strict rule — clarity and completeness take priority over line count.

| Metric | Target | Hard Limit |
|--------|--------|------------|
| Total SKILL.md lines | 200-350 | 500 |
| Frontmatter description | 100-200 chars | 1024 chars |
| Summary paragraph | 1-2 sentences | 3 sentences |
| Decision trees | 2-4 trees | 6 trees |
| Quick Reference subsections | 3-6 | 10 |
| Common Pitfalls rows | 3-8 | 12 |
| Topic Index rows | 10-30 | 50 |

---

## Checklist for Compliance

Use this checklist when reviewing a skill for template compliance:

- [ ] Frontmatter: `domain: [appropriate-domain]` (must match the dataset's domain consistently throughout; e.g., education-data, election-data, economic-mobility)
- [ ] Frontmatter: description includes "what" AND "when to use"
- [ ] Frontmatter: `provenance.skill_authored` and `provenance.skill_last_updated` present with ISO-8601 dates
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
- [ ] Total lines under 500
- [ ] Registered in `.claude/skills/daaf-orchestrator/references/skill-catalog.md` (Skill Quick Reference table)
