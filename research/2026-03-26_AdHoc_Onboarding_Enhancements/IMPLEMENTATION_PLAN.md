# Implementation Plan: Data Onboarding Mode Enhancements

**Date:** 2026-03-26
**Scope:** Two enhancements to Data Onboarding Mode:
1. API-based data acquisition (Stage DI-0)
2. Multi-file / hierarchical data onboarding

**Design Principles (confirmed with user):**
- API access info lives in the data source skill by default; user is asked whether a separate query skill is warranted for complex APIs
- Default to one unified skill for related files profiled together; user is asked explicitly with guidance on tradeoffs
- Skills must accommodate both local-storage and live-API-query preferences

---

## Existing State Summary

### What Already Exists

| Component | Current State | Gap |
|-----------|--------------|-----|
| `data-onboarding-mode.md` | Full DI-1 through DI-8 workflow; 4-line multi-file stub (lines 358-366) | No API acquisition stage; multi-file stub is shallow |
| `STATE_TEMPLATE_ONBOARDING.md` | Data Source Info with single-file fields | No API access fields; no multi-file structure fields |
| `DATA_SOURCE_SKILL_TEMPLATE.md` | Section 9 "Data Access" assumes mirror-based `fetch_from_mirrors()` | No API access subsection; no multi-file structure section |
| `data-ingest.md` (agent) | Inputs require "Data file path + format" (singular) | No multi-file input handling; no awareness of API-acquired data |
| `01_installation_and_quickstart.md` | Step 8 covers Harvard Dataverse API key setup | Needs generalization for arbitrary APIs |
| `04_extending_daaf.md` | "Start with a single representative file" advice | Needs API onboarding section; multi-file guidance needs expansion |
| `election-data-source-countypres` skill | Working proof-of-concept for API access pattern | Pattern is bespoke, not generalized into template |

### Architecture Insight: Two Data Access Models

The framework already has two access models, but only one is formalized:

| Model | Example | Authentication | Formalized? |
|-------|---------|----------------|-------------|
| **Mirror-based** | All education data skills | None required | Yes (mirrors.yaml, fetch_from_mirrors()) |
| **Direct API** | Election data (Harvard Dataverse) | API key via env var | No (ad hoc in election skill only) |

This plan formalizes the direct API model as a first-class pattern.

---

## Step 1: Expand Multi-File Profiling in `data-onboarding-mode.md`

### Files to Modify

**Primary:** `.claude/skills/daaf-orchestrator/references/data-onboarding-mode.md`

### Changes

#### 1a. Update DI-1 Intake to Collect File Structure

Add to DI-1's intake collection checklist (after "file path, format, source name"):

```
├─ Collect: file structure classification
│   ├─ SINGLE — one data file
│   ├─ HORIZONTAL — multiple files, same schema (e.g., one per year)
│   └─ HIERARCHICAL — multiple files, different schemas/levels, linked by keys
├─ If HORIZONTAL: collect all file paths; confirm schema is identical
├─ If HIERARCHICAL: collect all file paths; ask user to describe:
│   ├─ What entity does each file represent? (e.g., schools, districts, states)
│   ├─ What are the linking keys between levels?
│   └─ Are all files from the same time period?
```

**Skill count decision point (DI-1):**

The orchestrator presents a decision to the user:

> **Skill Structure Decision:**
> You're providing [N] related data files. I'll profile all of them together as a single onboarding project. By default, I'll create **one unified skill** that documents the full data source — this keeps all the context (schemas, relationships, join patterns) in one place and is simpler to load.
>
> Alternatively, I can create **one skill per entity type** (e.g., `your-source-schools`, `your-source-districts`), each independently loadable. This gives more granularity per table in each skill but requires loading multiple skills when you need to join across levels.
>
> **Which do you prefer?** (Default: one unified skill)

Record the user's choice in STATE.md under Key Decisions Made.

#### 1b. Expand the Multi-File Profiling Section (lines 358-366)

Replace the current 4-line stub with a full subsection (~60 lines). The new section should cover:

**File Structure: HORIZONTAL (same schema)**
- Script 01 verifies schema compatibility across all files: column names, types, and order
- If schemas match: concatenate into a single DataFrame for profiling (with a `_source_file` tracking column)
- If schemas diverge: flag specific differences (added/removed columns, type changes) as a WARNING; profile the union of columns; note per-file availability
- Temporal scripts (05) and entity scripts (06) become especially valuable for horizontal files — they reveal coverage gaps across the file set
- The skill documents the multi-file structure (year range, file naming pattern) so future fetches know to retrieve multiple files

**File Structure: HIERARCHICAL (different schemas/levels)**
- Script 01 inventories all files and produces a **schema map table** showing: file → entity type → row count → columns → suspected join key
- Each file is profiled independently through Parts A-D, with scripts organized per-file:
  - Part A: `01a_load-and-format.py` (file 1), `01b_load-and-format.py` (file 2), etc.
  - Scripts 02, 03, 04 similarly suffixed per file
  - Scripts 07, 09, 10 run per-file AND cross-file
- **New Script 07b: cross-level-linkage.py** (see Step 5) runs during Part C to test cross-file relationships
- Part D (script 10) produces per-file semantic interpretations AND a cross-file schema map showing the join topology
- The skill documents: schema map, entity hierarchy, join keys, cardinality at each level, recommended join patterns

**State tracking for multi-file:**
- Profiling Progress table in STATE.md gains per-file rows (see Step 2)
- PSU-DI1 lists all files with their assigned entity types
- PSU-DI2 shows per-file interpretations grouped by file, plus cross-file relationship interpretations

#### 1c. Update PSU-DI1 Template

Expand the template to handle multi-file scenarios:

```
**Data Source Summary:**
- File(s): [list all files with entity types]
- File Structure: [SINGLE / HORIZONTAL / HIERARCHICAL]
- Format: [parquet / CSV / etc.]
- Total Size: [combined file size]
[If HIERARCHICAL:]
- Entity Hierarchy: [user-described hierarchy, e.g., "schools → districts → states"]
- Linking Keys: [user-described keys, e.g., "leaid links schools to districts"]
- Skill Structure: [One unified skill / One skill per entity type] (user preference)
```

#### 1d. Update PSU-DI2 Template

For hierarchical data, group interpretations by file/entity:

```
**Per-File Findings:**

### [File 1: Entity Type]
[Standard PSU-DI2 content for this file]

### [File 2: Entity Type]
[Standard PSU-DI2 content for this file]

### Cross-File Relationships
| Link | Key Column(s) | Cardinality | Coverage | Notes |
|------|--------------|-------------|----------|-------|
| [File1 → File2] | [key] | [1:M / M:M] | [% match] | [observations] |
```

---

## Step 2: Extend `STATE_TEMPLATE_ONBOARDING.md`

### Files to Modify

**Primary:** `agent_reference/STATE_TEMPLATE_ONBOARDING.md`

### Changes

#### 2a. Expand Data Source Info Section

Add new fields to the Data Source Info table:

```markdown
| **Access Method** | [Local File / API] |
| **File Structure** | [SINGLE / HORIZONTAL / HIERARCHICAL] |
| **Skill Structure** | [Unified / Per-Entity] |
```

**If Access Method = API, add:**

```markdown
| **API Base URL** | [e.g., "https://dataverse.harvard.edu/api/"] |
| **API Key Env Var** | [e.g., "HARVARD_DATAVERSE_API_KEY"] |
| **API Key Status** | [Verified present / Missing — user notified] |
| **API Documentation URL** | [URL to API docs, or "None provided"] |
| **Data Persistence Preference** | [Local storage (download once) / Live query (fetch on demand)] |
```

**If File Structure = HIERARCHICAL, add:**

```markdown
## Multi-File Structure

| File | Entity Type | Row Count | Columns | Join Key(s) | Role |
|------|-------------|-----------|---------|-------------|------|
| [filename] | [e.g., schools] | [N] | [N] | [key cols] | Primary |
| [filename] | [e.g., districts] | [N] | [N] | [key cols] | Auxiliary |

### Entity Hierarchy
[User-described hierarchy]

### Linking Keys
| Link | From File | To File | Key Column(s) | Expected Cardinality |
|------|-----------|---------|---------------|---------------------|
| [description] | [file] | [file] | [cols] | [1:M / M:M] |
```

#### 2b. Expand Profiling Progress Table for Multi-File

For HIERARCHICAL data, the Profiling Progress table expands with per-file rows. The script numbering convention becomes:

```
01a_load-and-format.py  (file 1: schools)
01b_load-and-format.py  (file 2: districts)
02a_structural-profile.py
02b_structural-profile.py
...
07_key-integrity.py      (per-file, each file)
07b_cross-level-linkage.py  (cross-file, runs once)
```

Add a row for script 07b to the Profiling Progress table:

```markdown
| 07b | C | cross-level-linkage | `scripts/profile_relational/07b_cross-level-linkage.py` | Yes: HIERARCHICAL | [status] | ... |
```

---

## Step 3: Add API Acquisition Pathway (Stage DI-0)

### Files to Modify

**Primary:** `.claude/skills/daaf-orchestrator/references/data-onboarding-mode.md`
**Secondary:** `user_reference/01_installation_and_quickstart.md`, `user_reference/04_extending_daaf.md`, `.claude/agents/data-ingest.md`

### Changes

#### 3a. Add Stage DI-0 to Workflow Diagram

Insert before the current DI-1:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE DI-0: API DISCOVERY & ACQUISITION (CONDITIONAL)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  Stage DI-0: API Acquisition (only if user has no local file)              │
│      ├─ Determine access method: Does the user have a local file?          │
│      │   ├─ YES → Skip DI-0 entirely, proceed to DI-1 as normal           │
│      │   └─ NO → Enter API acquisition flow                                │
│      ├─ Collect from user:                                                  │
│      │   ├─ API documentation URL (or describe the API)                    │
│      │   ├─ Environment variable name holding the API key                  │
│      │   ├─ Target endpoint(s) and any query parameters                    │
│      │   └─ Data persistence preference:                                    │
│      │       ├─ LOCAL STORAGE: Download once, profile the local file       │
│      │       │   (default — simpler, works offline after initial fetch)    │
│      │       └─ LIVE QUERY: Always fetch from API in future pipelines      │
│      │           (keeps data current, but requires API access each time)   │
│      ├─ Verify API key is set in environment:                              │
│      │   └─ If missing: STOP. Present setup instructions (see below)      │
│      ├─ Research the API (orchestrator uses WebFetch/WebSearch):            │
│      │   ├─ Read API documentation                                         │
│      │   ├─ Identify available endpoints, response format, pagination      │
│      │   ├─ Identify rate limits and authentication method                 │
│      │   └─ Determine download strategy (single call vs paginated)        │
│      ├─ Write acquisition script:                                          │
│      │   ├─ Script: scripts/stage5_fetch/00_api-discovery.py               │
│      │   ├─ Checks for API key in os.environ[ENV_VAR_NAME]                │
│      │   ├─ Makes exploratory API call to verify access                   │
│      │   ├─ Downloads target data to data/raw/                             │
│      │   ├─ Saves as parquet (preferred) or preserves original format     │
│      │   └─ Prints summary: rows fetched, columns, file size, path       │
│      ├─ Present script to user for approval before execution              │
│      ├─ Execute via run_with_capture.sh                                    │
│      └─ Gate GDI-0: File downloaded, accessible, non-empty                │
│                          ↓                                                  │
│  Proceed to DI-1 with the downloaded file path as the data file           │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 3b. Add GDI-0 Gate Definition

| Gate | After Stage | Criteria | STOP If |
|------|-------------|----------|---------|
| GDI-0 | DI-0 | File downloaded and non-empty; API key verified; acquisition script archived | API returns error; authentication fails; empty response; rate limited |

#### 3c. Orchestrator API Key Guidance Block

Add a new section to `data-onboarding-mode.md` that the orchestrator uses when it detects API acquisition is needed:

```markdown
### API Key Setup Guidance (Orchestrator Reference)

When the user needs to set up an API key and it's not currently available in
the environment, present these options:

**For the current session (temporary):**

> Before launching Claude Code, run this in your Docker container terminal:
> ```bash
> export YOUR_API_KEY_NAME="your_key_here"
> ```
> Then restart Claude Code. You can also type `! export YOUR_API_KEY_NAME="your_key_here"`
> directly in the Claude Code prompt to set it for this session.

**For persistence across sessions:**

> Add the export to your shell profile inside the container:
> ```bash
> echo 'export YOUR_API_KEY_NAME="your_key_here"' >> ~/.bashrc
> ```

**For Docker Compose (recommended for team/repeated use):**

> Add to the `environment:` section in `docker-compose.yml`:
> ```yaml
> environment:
>   - YOUR_API_KEY_NAME=${YOUR_API_KEY_NAME}
> ```
> Then set the variable on your host machine before running `docker compose up`.

**Security notes to convey to user:**
- DAAF's safety guardrails prevent reading/writing `.env` files
- Credentials stay in temporary memory only — never written to files
- The acquisition script references `os.environ["KEY_NAME"]`, never hardcodes the key
- The script is archived in the project for reproducibility, but the key value is never in it
```

#### 3d. API Complexity Decision Point

After the orchestrator has researched the API documentation, present the user with a decision about skill structure for API access:

```markdown
### API Skill Structure Decision (During DI-0)

After API research, the orchestrator assesses API complexity and presents a
recommendation to the user:

**Simple API (1-3 endpoints, single dataset):**

> Your API has a straightforward structure — I'll document the access pattern
> directly in the data source skill's "Data Access" section. This keeps
> everything in one place. **Sound good?**

**Complex API (many endpoints, multiple datasets, rich query language):**

> This API offers a rich set of endpoints and datasets. I can either:
>
> 1. **Document access in the data source skill** (default) — keeps it simple,
>    covers the specific dataset(s) you're onboarding now
> 2. **Create a separate query/connector skill** (e.g., `your-domain-data-query`) —
>    like the `education-data-query` skill, this would be a reusable reference
>    for accessing any dataset from this API, useful if you plan to onboard
>    multiple datasets from this source
>
> For now, I'd recommend option 1 unless you know you'll be working with many
> datasets from this API. You can always create the query skill later.
>
> **Which do you prefer?**

Record the decision in STATE.md Key Decisions Made.
```

#### 3e. Data Persistence Preference Encoding

The user's persistence preference (local storage vs. live query) affects the skill output:

```markdown
### Data Persistence Preference Effects

| Preference | Skill "Data Access" Section | Acquisition Script | Future Pipeline Behavior |
|------------|---------------------------|-------------------|------------------------|
| **Local storage** (default) | Documents download procedure + local file path pattern | Downloads full dataset to data/raw/ | Stage 5 loads from local parquet; re-fetch only if user requests |
| **Live query** | Documents API endpoint + query code pattern | Downloads for onboarding profiling | Stage 5 queries API directly each time; script includes the full API call |

Both preferences produce the same profiling outcome — the difference is in
what the skill tells future pipeline stages about how to access the data.

When "Live query" is selected, the skill's Data Access section should include
both patterns: the API query code (primary) AND a note about local caching
(for offline use or performance).
```

#### 3f. Update User Reference Files

**`01_installation_and_quickstart.md` — Expand Step 8:**

The current Step 8 is specific to Harvard Dataverse. Generalize it:

- Change the heading to: "Step 8 (Optional): Set up data source API keys"
- Keep the Harvard Dataverse example as-is (it's a good concrete example)
- Add a paragraph above the table: "The table below shows API keys for data sources that ship with DAAF. When you onboard a new data source from an API via Data Onboarding Mode, DAAF will guide you through setting up the appropriate environment variable using the same pattern shown here."
- Add a note: "You can set multiple API keys simultaneously — each uses a unique environment variable name."

**`04_extending_daaf.md` — Add API onboarding guidance:**

Add a new subsection under "Before You Start" in the Data Onboarding section:

```markdown
### Onboarding Data from an API

If your data source is available via a REST API rather than as a downloadable
file, DAAF can handle the acquisition for you during Data Onboarding. You'll need:

1. **API documentation** — a URL to the API docs, or a description of how the
   API works (endpoints, authentication, response format)
2. **An API key** — most APIs require authentication. Set up your key as an
   environment variable inside the Docker container before starting (see
   Step 8 in the Installation Guide for the pattern)
3. **A sense of what you want to download** — which endpoint, what filters
   (date range, geography, etc.), and how much data

DAAF will research the API, write a fetch script for your approval, download
the data, and then proceed with the standard profiling workflow. The fetch
script is saved as a reproducible artifact — you (or DAAF) can re-run it
any time to get fresh data.

**Local vs. Live Access:** During setup, DAAF will ask whether you prefer to
download the data once and work with the local copy (simpler, works offline)
or always query the API live in future analyses (keeps data current). You can
change this preference later by modifying the data source skill.
```

#### 3g. Update data-ingest.md Agent

Add a note in the Inputs section that acknowledges API-acquired data:

```markdown
| Data acquisition method | Orchestrator Agent prompt | No | "local_file" (default) or "api_acquired" — if API-acquired, the acquisition script path is provided for provenance |
| Acquisition script path | Orchestrator Agent prompt | Conditional | Path to DI-0 acquisition script, if data was fetched via API |
```

And in Core Behaviors > Data Primacy, add:

```markdown
When the data was acquired via API (acquisition method = "api_acquired"), the
acquisition script in the project's scripts/stage5_fetch/ directory documents
the exact API call, parameters, and download date. Reference this for provenance
in Part D interpretations.
```

---

## Step 4: Extend `DATA_SOURCE_SKILL_TEMPLATE.md`

### Files to Modify

**Primary:** `agent_reference/DATA_SOURCE_SKILL_TEMPLATE.md`

### Changes

#### 4a. Add Optional API Access Subsection to Section 9

Modify Section 9 (Data Access) to support both mirror-based and API-based access:

```markdown
### Section 9: Data Access

<!-- RULES (updated):
  ...existing rules...
  - If the data source is accessed via API (not mirrors), replace the
    fetch_from_mirrors() pattern with the API-specific fetch pattern
  - Include a "### Prerequisites" subsection if authentication is required
  - Include a "### Data Persistence" subsection documenting both local
    and live-query access patterns when the source supports API access
  - The election-data-source-countypres skill is the reference implementation
    for the API access pattern
-->
```

Add an alternative skeleton for API-based data access:

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
| Rate limits | [if known] |

### Dataset Endpoints

| Dataset | Endpoint / DOI | Format | Notes |
|---------|---------------|--------|-------|
| [name] | [URL or DOI] | [TSV/JSON/CSV] | [notes] |

### Example Fetch

```python
import os, io, requests
import polars as pl

# --- Config ---
API_KEY = os.environ["[ENV_VAR_NAME]"]
ENDPOINT = "[base_url]"

# --- Fetch ---
# INTENT: Download [dataset] via [API name]
# ASSUMES: API key is set in environment
r = requests.get(ENDPOINT, params={"key": API_KEY, ...})
r.raise_for_status()
df = pl.read_csv(io.BytesIO(r.content), separator='\t')

# --- Validate ---
print(f"Shape: {df.shape}")
assert df.shape[0] > 0, "STOP: Empty response from API"
```

### Data Persistence

**Local storage (download once):**
```python
# Save to project data/raw/ after fetching
df.write_parquet(f"{DATA_DIR}/raw/{DATE}_{source}_{dataset}.parquet")
# Subsequent scripts load from local parquet
```

**Live query (fetch on demand):**
```python
# Fetch directly in analysis scripts — always gets current data
# Include the full API call pattern above in each Stage 5 script
# Consider caching: save a local copy as backup
```

### Filtering

```python
# [Source-specific filtering examples after download]
```
```

#### 4b. Add Optional Multi-File Structure Section

Add a new optional section (between Section 10 Common Pitfalls and Section 11 Additional Sections):

```markdown
### Section 10.5 (Optional): Multi-File Structure

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
print(f"Join coverage: {schools_with_district['col_district'].drop_nulls().len()} / {len(schools_with_district)}")
```

### Cross-Level Caveats

| Caveat | Affected Levels | Impact |
|--------|----------------|--------|
| [e.g., "Not all schools have district records"] | Schools → Districts | [X]% of school rows lose district data on join |
```

<!-- RULES:
  - Only include for sources with HIERARCHICAL file structure
  - Schema Map MUST include all files/tables with grain description
  - Entity Hierarchy MUST use ASCII tree diagram
  - Join Patterns MUST include working code with validation
  - Cross-Level Caveats MUST document known join issues
-->
```

#### 4c. Update Checklist for Compliance

Add new checklist items:

```markdown
- [ ] If API-based: Prerequisites subsection present with env var name and setup link
- [ ] If API-based: Data Persistence subsection documents both local and live patterns
- [ ] If API-based: Example Fetch uses os.environ (never hardcodes keys)
- [ ] If multi-file: Multi-File Structure section present with schema map
- [ ] If multi-file: Join Patterns include working code with validation checks
- [ ] If multi-file: Cross-Level Caveats table populated
```

---

## Step 5: Add Cross-Level Linkage Script (07b) for Part C

### Files to Modify

**Primary:** `.claude/skills/daaf-orchestrator/references/data-onboarding-mode.md`
**Secondary:** `.claude/agents/data-ingest.md`

### Changes

#### 5a. Add Script 07b to Profiling Protocol

In the Script Inventory table:

```markdown
| 07b | C | cross-level-linkage | Cross-file key testing, cardinality, coverage, temporal alignment | Yes: HIERARCHICAL | `scripts/profile_relational/07b_cross-level-linkage.py` |
```

In the Conditional Execution Rules:

```markdown
Script 07b (Cross-Level Linkage):
    File structure = HIERARCHICAL?
        YES → Execute script 07b
        NO  → Skip; document "single-file or horizontal — cross-level analysis not applicable"
```

#### 5b. Define Script 07b Content

```markdown
**07b_cross-level-linkage.py (CONDITIONAL: HIERARCHICAL files):**

Tests cross-file relationships for hierarchical data. Executed once (not per-file).

- For each pair of linked files (from the schema map):
  1. Key cardinality test: count unique key values in each file; classify as 1:1, 1:M, M:M
  2. Coverage completeness: what % of child-level keys exist in parent-level file?
  3. Orphan detection: list child records with no parent match (with counts)
  4. Temporal alignment: if both files have time columns, compare coverage periods
  5. Join loss simulation: perform inner join on declared keys; report row survival rate
  6. Join duplication check: does joining create unexpected row multiplication?

- Outputs:
  - Cross-file relationship table (file pair, key, cardinality, coverage %, orphan count)
  - Temporal alignment matrix (file × time period)
  - Join simulation results (inner join row counts, survival rates)
  - Recommendations for the skill's Multi-File Structure section

- Print Requirements (execution log — no size limit):
  - MUST print the complete cross-file relationship table
  - MUST print orphan counts and sample orphan key values (top 10)
  - MUST print join simulation results for every declared key pair
  - MUST print temporal alignment matrix if applicable
```

#### 5c. Update Part C in data-ingest.md

Add 07b to the Part C protocol:

```markdown
### Part C: Relational Analysis (Scripts 07-09, optionally 07b)

...existing scripts 07, 08, 09...

4. **Script 07b: cross-level-linkage.py** (CONDITIONAL — only if file structure is HIERARCHICAL)
   — Write to `{project_script_dir}/profile_relational/07b_cross-level-linkage.py`
   - Cross-file key cardinality, coverage, orphan detection, temporal alignment, join simulation
   - Requires: all file paths from schema map, declared linking keys from DI-1 intake
```

#### 5d. Update Part Dependency Diagram

```
Part C: Relational Analysis
  07  (ALWAYS, per-file)
  07b?(HIERARCHICAL only, cross-file — depends on 07 completing for all files)
  08? (>=3 numeric cols, per-file)
  09  (ALWAYS, per-file)
```

---

## Implementation Sequence

### Wave 1: Foundation (no functional dependencies between items)

These can be implemented in parallel:

| Task | File | Description | Estimated Complexity |
|------|------|-------------|---------------------|
| 1a | `data-onboarding-mode.md` | Add file structure classification to DI-1 intake | Low |
| 2a | `STATE_TEMPLATE_ONBOARDING.md` | Add API Access and File Structure fields to Data Source Info | Low |
| 3f-1 | `01_installation_and_quickstart.md` | Generalize Step 8 API key guidance | Low |
| 3f-2 | `04_extending_daaf.md` | Add "Onboarding Data from an API" subsection | Low |

### Wave 2: Core Workflow Changes (depends on Wave 1)

| Task | File | Description | Estimated Complexity |
|------|------|-------------|---------------------|
| 1b | `data-onboarding-mode.md` | Replace multi-file stub with full HORIZONTAL + HIERARCHICAL guidance | Medium |
| 3a-3d | `data-onboarding-mode.md` | Add Stage DI-0 (workflow diagram, gate, orchestrator guidance, decision points) | High |
| 3e | `data-onboarding-mode.md` | Add Data Persistence Preference section | Low |
| 2b | `STATE_TEMPLATE_ONBOARDING.md` | Add Multi-File Structure section and expand Profiling Progress | Medium |

### Wave 3: Template & Agent Updates (depends on Wave 2)

| Task | File | Description | Estimated Complexity |
|------|------|-------------|---------------------|
| 4a | `DATA_SOURCE_SKILL_TEMPLATE.md` | Add API Access alternative skeleton to Section 9 | Medium |
| 4b | `DATA_SOURCE_SKILL_TEMPLATE.md` | Add Multi-File Structure optional section | Medium |
| 4c | `DATA_SOURCE_SKILL_TEMPLATE.md` | Update compliance checklist | Low |
| 3g | `data-ingest.md` | Add API-acquired data awareness to inputs and Core Behaviors | Low |
| 5a-5d | `data-onboarding-mode.md` + `data-ingest.md` | Add script 07b (cross-level linkage) | Medium |

### Wave 4: PSU Templates & Polish (depends on Waves 2-3)

| Task | File | Description | Estimated Complexity |
|------|------|-------------|---------------------|
| 1c | `data-onboarding-mode.md` | Update PSU-DI1 template for multi-file + API | Low |
| 1d | `data-onboarding-mode.md` | Update PSU-DI2 template for multi-file | Low |

---

## File Change Summary

| File | Changes | Waves |
|------|---------|-------|
| `.claude/skills/daaf-orchestrator/references/data-onboarding-mode.md` | DI-0 stage, multi-file expansion, PSU updates, script 07b, API guidance, persistence preference | 1-4 |
| `agent_reference/STATE_TEMPLATE_ONBOARDING.md` | API access fields, file structure fields, multi-file structure section, 07b row | 1-3 |
| `agent_reference/DATA_SOURCE_SKILL_TEMPLATE.md` | API access skeleton, multi-file section, updated checklist | 3 |
| `.claude/agents/data-ingest.md` | API-acquired data inputs, 07b in Part C | 3 |
| `user_reference/01_installation_and_quickstart.md` | Generalize Step 8 | 1 |
| `user_reference/04_extending_daaf.md` | API onboarding guidance | 1 |

**Total files modified: 6**

---

## Design Decisions Log

| Decision | Choice | Rationale | User Confirmed |
|----------|--------|-----------|----------------|
| Default skill count for multi-file | One unified skill | Simpler to load; user asked explicitly for preference | Yes |
| Default API access location | In data source skill | Simpler; separate query skill only for complex APIs | Yes |
| Data persistence preference | Ask user; default to local | Most users want offline capability | Yes |
| DI-0 execution model | Orchestrator writes script, not data-ingest agent | DI-0 is acquisition, not profiling; different skillset | Pending |
| Script 07b scope | Cross-file only; per-file key analysis stays in 07 | Clean separation of concerns | Pending |
| Multi-file Part A approach | Per-file independent profiling with suffixed scripts | Each file may have different schema; clean audit trail | Pending |

---

## Open Questions for User

1. **DI-0 executor:** Should the orchestrator write the API fetch script directly (using research-executor), or should data-ingest gain API acquisition capabilities? I lean toward research-executor since DI-0 is about fetching, not profiling — and it produces a Stage 5-style script that's immediately reusable in future pipeline work.

2. **Horizontal multi-file concatenation:** For same-schema files, should the profiling always concatenate into one DataFrame (with a source tracking column), or should the user be asked? Concatenation makes profiling simpler but may miss per-file differences.

3. **Invocation template updates for DI-0:** The current invocation templates in data-onboarding-mode.md cover Parts A-D and DI-7. DI-0 would need its own invocation template if we use research-executor. Should this be fully specified in the plan, or is it sufficient to define DI-0's inputs/outputs and let the implementation determine the template?
