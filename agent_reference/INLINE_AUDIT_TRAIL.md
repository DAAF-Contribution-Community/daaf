# Inline Audit Trail (IAT) Protocol

The Inline Audit Trail is the mandatory documentation standard for all scripts (Python and R) produced in the research workflow. Every script must be self-explanatory to a human reader **without running the code**.

---

## Purpose & Philosophy

Research scripts are **write-once, execute-once, archive** artifacts. Unlike application code, they are read far more often than they are modified. The IAT ensures that:

1. **Auditability:** A reviewer can follow every decision by reading the source alone
2. **Reproducibility:** Assumptions and reasoning are captured alongside the code, not in separate docs
3. **QA Efficiency:** Code-reviewer can verify methodology alignment without re-deriving intent
4. **Onboarding:** New team members understand *why* a transformation was done, not just *what* it does

**The IAT philosophy:**
> Code tells you HOW. Comments tell you WHY, WHAT FOR, and WHAT'S ASSUMED.

**Language applicability:** The IAT applies identically to Python (`.py`) and R (`.R`) scripts. Both languages use `#` for comments, so all comment types, prefixes (`# INTENT:`, `# REASONING:`, `# ASSUMES:`), and section separators (`# --- Config ---`) work the same way. Examples below use Python syntax; R equivalents follow the same comment patterns with R code.

**Default posture:** Be verbose ALWAYS for research scripts (Stages 5-8). Silence is not golden — it's a documentation gap.

---

## Comment Taxonomy (5 Types)

The IAT defines five comment types. Each has clear rules for when it's required.

| # | Type | Format | Required When |
|---|------|--------|---------------|
| 1 | **Section Preamble** | Block comment above `# --- Section ---` header | Every section (Config, Load, Transform, Validate, Save) |
| 2 | **Intent Comment** | `# INTENT: ...` or block describing goal | Before every logical block (filter, join, agg, derived column) |
| 3 | **Reasoning Comment** | `# REASONING: ...` or `# WHY: ...` | When a non-obvious choice was made (join type, threshold, filter condition) |
| 4 | **Assumption Comment** | `# ASSUMES: ...` | When code depends on data properties (uniqueness, no nulls, value ranges) |
| 5 | **Inline Annotation** | End-of-line `# ...` | For non-obvious single operations (complex Polars expressions, regex, edge cases) |

---

### Type 1: Section Preamble

A block comment that introduces each major section of a script. Provides orientation for the reader.

**Template by section type:**

```python
# --- Config ---
# Configuration constants for this script. Paths are relative to the project
# root. Constants are derived from the Plan's query specification.
# (R scripts: library() calls go here as well.)

# --- Load ---
# Load input data from the prior stage's output. Verify shape and schema
# match expectations before proceeding.

# --- Pre-state ---
# Capture the current state of the data BEFORE transformation. These values
# are compared against post-state to validate the transformation worked
# correctly and didn't introduce unexpected changes.

# --- Transform ---
# [SPECIFIC DESCRIPTION of what this section does and why]
# This is the core operation of this script: [brief summary].

# --- Validate ---
# Checkpoint validation against Plan expectations. Each check corresponds
# to a specific Plan requirement or invariant that must be preserved.

# --- Save ---
# Persist results in parquet.
# Output paths match the Plan's file specification.
```

**Required:** Every section in every script.

---

### Type 2: Intent Comment

Explains *what* a code block is trying to accomplish and *why* it exists in the pipeline.

```python
# INTENT: Filter to only regular public schools (excluding charter, magnet, special ed)
# because the research question focuses on traditional public school enrollment patterns.
# Charter schools have different funding and enrollment dynamics that would confound
# the poverty-enrollment relationship we're measuring.
df = df.filter(pl.col("school_type") == 1)
```

**Required:** Before every filter, join, aggregation, derived column, and multi-step operation.

---

### Type 3: Reasoning Comment

Explains *why* a particular approach was chosen over alternatives. Documents the decision.

```python
# REASONING: Using INNER join (not LEFT) because:
#   - We need BOTH enrollment AND poverty data for every school in the analysis
#   - Schools missing from MEPS lack poverty estimates and cannot contribute
#     to the research question ("How does poverty correlate with enrollment?")
#   - Plan specifies inner join with expected match rate of ~85%
#
# Alternative considered: LEFT join would preserve all CCD schools but create
# nulls in poverty columns that would need imputation or exclusion downstream.
# Inner join is simpler and directly serves the research question.
df = df_ccd.join(df_meps, on=JOIN_KEY, how="inner")
```

**Required:** When a non-obvious choice was made — join type, threshold value, filter condition, aggregation function, column selection, year range, etc.

---

### Type 4: Assumption Comment

Documents data properties that the code depends on. If these assumptions are violated, the code may produce incorrect results silently.

```python
# ASSUMES:
#   - JOIN_KEY ("ncessch") is the 12-digit NCES school ID, unique per school-year
#   - Both datasets have been cleaned (Stage 6) — no coded missing values remain
#   - Key overlap was verified in pre-state check above (~85% expected)
#   - CCD has one row per school per year (verified in CP1)
df = df_ccd.join(df_meps, on=JOIN_KEY, how="inner")
```

**Required:** When code depends on data properties — uniqueness, no nulls, value ranges, sort order, data type, cardinality.

---

### Type 5: Inline Annotation

Short end-of-line comments for non-obvious single operations.

```python
overlap_pct = key_overlap / len(ccd_keys) if ccd_keys else 0  # Guard against empty set division
df = df.with_columns(
    pl.col("ncessch").cast(pl.Utf8).str.zfill(12).alias("ncessch")  # Pad to 12-digit NCES ID format
)
row_change_pct = ((df.shape[0] - pre_ccd_rows) / pre_ccd_rows * 100)  # Negative = rows lost
```

**Required:** For complex Polars expressions, regex patterns, edge case handling, and any single-line operation where the purpose isn't immediately obvious.

---

## What NOT to Comment

The IAT is about useful documentation, not noise. Do NOT comment:

| Skip Commenting | Example | Why |
|-----------------|---------|-----|
| Obvious imports | `import polars as pl` / `library(tidyverse)` | Universal knowledge |
| Simple variable assignment to a literal | `DATE_PREFIX = "2026-01-24"` / `DATE_PREFIX <- "2026-01-24"` | Self-evident |
| Standard boilerplate | `#!/usr/bin/env python3` | Convention |
| Print separators | `print("=" * 60)` / `cat(strrep("=", 60))` | Visual formatting |
| Obvious operations | `df.shape[0]` / `nrow(df)` | Self-explanatory |
| The `EXECUTION LOG` section | Auto-appended output | Not authored code |

**Rule of thumb:** If removing the comment would leave a reader confused about *why* something is done, the comment is needed. If removing it would only leave them unsure of *what* the code literally does (and the code is clear), skip it.

---

## Before/After Examples

### Example 1: Stage 5 Fetch Script

**BEFORE (sparse):**
```python
# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-01-24_School_Analysis")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-01-24"
YEARS = list(range(2018, 2023))

DATASET_PATH = "ccd/schools_ccd_directory"

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_ccd_schools.parquet"

# Education domain example — substitute your domain's query skill path
MIRRORS_YAML = Path("/daaf/.claude/skills/education-data-query/references/mirrors.yaml")
with open(MIRRORS_YAML) as f:
    MIRRORS = yaml.safe_load(f)["mirrors"]

# --- Fetch ---
print("=" * 60)
print("Stage 5.1: Fetch CCD school directory")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

df = fetch_from_mirrors(DATASET_PATH, years=YEARS)
print(f"Shape: {df.shape[0]:,} rows x {df.shape[1]} cols")
```

**AFTER (IAT-compliant):**
```python
# --- Config ---
# Configuration constants derived from the Plan's query specification (Section 4.2).
# Data is downloaded from mirrors (per mirrors.yaml priority order) rather than
# the REST API. We fetch 5 years to match the Plan's year range.
PROJECT_DIR = Path("/daaf/research/2026-01-24_School_Analysis")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-01-24"

YEARS = list(range(2018, 2023))  # 2018-2022 per Plan query specification

# Dataset path from domain query skill's datasets-reference.md
# Education domain example — substitute your domain's query skill path
DATASET_PATH = "ccd/schools_ccd_directory"

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_ccd_schools.parquet"

# --- Mirror Configuration ---
# INTENT: Load mirror configuration so fetch_from_mirrors() knows which
# mirrors to try and in what order. mirrors.yaml is the single source of
# truth for mirror URLs, formats, and read strategies.
#
# REASONING: Loading from YAML file (rather than hardcoding URLs) because
# mirrors can change independently of analysis scripts. The YAML also
# encodes the read_strategy (eager_parquet vs lazy_csv) so the fetch
# function adapts to each mirror's format automatically.
import yaml

# Education domain example — substitute your domain's query skill path
MIRRORS_YAML = Path("/daaf/.claude/skills/education-data-query/references/mirrors.yaml")

with open(MIRRORS_YAML) as f:
    MIRRORS = yaml.safe_load(f)["mirrors"]

# --- Fetch ---
# INTENT: Download CCD school directory and filter to requested years.
# The fetch_from_mirrors() function tries each mirror in priority order
# (mirrors tried in priority order per mirrors.yaml) and returns a Polars
# DataFrame filtered to the requested years.
#
# REASONING: Using mirror-based download (not the REST API) because mirrors
# serve complete files that Polars can read natively via HTTP — no pagination,
# no rate limiting, and parquet format preserves schema and compresses 3-10x.
#
# ASSUMES:
#   - At least one mirror is available and serves this dataset
#   - Dataset contains a "year" column for filtering
#   - Each year contains ~4,000-5,000 school records (based on Plan estimate)
#   - All variable names are lowercase (Portal convention)
print("=" * 60)
print("Stage 5.1: Fetch CCD school directory")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

print("\nFetching CCD school directory...")
df = fetch_from_mirrors(DATASET_PATH, years=YEARS)
print(f"Shape: {df.shape[0]:,} rows x {df.shape[1]} cols")
```

---

### Example 2: Stage 7 Join Script

**BEFORE (sparse):**
```python
# --- Join ---
df = df_ccd.join(df_meps, on=JOIN_KEY, how="inner")
print(f"\nJoin complete: {df.shape[0]:,} rows x {df.shape[1]} cols")

row_change_pct = ((df.shape[0] - pre_ccd_rows) / pre_ccd_rows * 100)
print(f"Row change from CCD: {row_change_pct:+.1f}%")
```

**AFTER (IAT-compliant):**
```python
# --- Join ---
# INTENT: Combine CCD school directory data with MEPS poverty estimates
# to create a unified analysis dataset with both enrollment and poverty metrics.
#
# REASONING: Using INNER join (not LEFT) because:
#   - We need BOTH enrollment AND poverty data for every school in the analysis
#   - Schools missing from MEPS lack poverty estimates and cannot contribute
#     to the research question ("How does poverty correlate with enrollment?")
#   - Plan specifies inner join with expected match rate of ~85%
#
# ASSUMES:
#   - JOIN_KEY ("ncessch") is the 12-digit NCES school ID, unique per school-year
#   - Both datasets have been cleaned (Stage 6) — no coded missing values remain
#   - Key overlap was verified in pre-state check above
#   - CCD has one row per school per year; MEPS has one row per school per year
#
# EXPECTED: ~18,000-20,000 rows (CCD has ~22K, MEPS has ~18K, overlap ~85%)
df = df_ccd.join(df_meps, on=JOIN_KEY, how="inner")
print(f"\nJoin complete: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Check that join didn't silently produce duplicates (would indicate
# the 1:1 cardinality assumption is violated)
row_change_pct = ((df.shape[0] - pre_ccd_rows) / pre_ccd_rows * 100)
print(f"Row change from CCD: {row_change_pct:+.1f}%")
```

---

### Example 3: Stage 8 Visualization Script

**BEFORE (sparse):**
```python
# --- Plot ---
plot = (
    ggplot(df, aes(x="poverty_rate", y="enrollment"))
    + geom_point(alpha=0.3, size=1)
    + labs(title="School Enrollment vs Poverty Rate",
           x="Poverty Rate (%)", y="Total Enrollment")
    + theme_minimal()
)
plot.save(OUTPUT_PATH, dpi=300, width=10, height=6)
```

**AFTER (IAT-compliant):**
```python
# --- Plot ---
# INTENT: Create a scatter plot showing the relationship between school-level
# poverty rate (MEPS estimate) and total enrollment. This is the primary
# visualization for Research Outcome #1: "Stakeholders can see the correlation
# between poverty and enrollment across schools."
#
# REASONING: Scatter plot (not line or bar) because:
#   - Both variables are continuous, making scatter the natural choice
#   - We want to show the full distribution, not just averages
#   - Alpha=0.3 handles overplotting (~18K points would be opaque at alpha=1)
#   - Point size=1 keeps individual schools visible without blending
#
# ASSUMES:
#   - poverty_rate is 0-100 scale (percentage, not proportion)
#   - enrollment is raw count (not log-transformed)
#   - No extreme outliers remain after Stage 7 cleaning
plot = (
    ggplot(df, aes(x="poverty_rate", y="enrollment"))
    + geom_point(alpha=0.3, size=1)
    + labs(
        title="School Enrollment vs Poverty Rate",
        x="Poverty Rate (%)",  # MEPS estimate at 100% FPL
        y="Total Enrollment",  # CCD reported enrollment
    )
    + theme_minimal()
)
plot.save(OUTPUT_PATH, dpi=300, width=10, height=6)  # 300 DPI for publication quality
print(f"Saved figure: {OUTPUT_PATH}")
```

---

## QA Integration

### How code-reviewer Evaluates IAT Compliance

Documentation quality is assessed as **WARNING** severity (not BLOCKER):

| Check | Passes When | WARNING When |
|-------|-------------|--------------|
| Section preambles | All sections have preamble comments | Any section missing preamble |
| Transform documentation | All transforms have INTENT + REASONING | Any transform lacks intent comment |
| Assumption documentation | Data assumptions are explicit | Implicit assumptions in joins/filters |
| Non-obvious choices | REASONING comments on non-obvious decisions | Unexplained threshold values, filter conditions |

**Rationale:** Sparse documentation doesn't produce *wrong* results — it produces *unauditable* results. This is a quality concern, not a correctness concern. Making it a WARNING ensures it's flagged and addressed during Stage 10 aggregation.

**Exception:** If missing documentation makes it impossible to verify methodology alignment (e.g., a complex join with no reasoning comment, so the reviewer can't tell if the join type is correct), the reviewer MAY escalate to BLOCKER under the existing "methodology alignment" dimension.

### QA Report Documentation Section

Code-reviewer includes this in Phase 1 of every QA report:

```markdown
### Documentation Quality (IAT)
| Aspect | Status | Notes |
|--------|--------|-------|
| Section preambles present | YES/NO | [Which sections missing] |
| Intent comments on transforms | YES/NO | [Which transforms undocumented] |
| Reasoning comments on choices | YES/NO | [Which choices unexplained] |
| Assumption comments | YES/NO | [Which assumptions implicit] |
```

---

## Quick Reference Card

For agents to scan before writing code:

```
┌─────────────────────────────────────────────────────────────────┐
│                   IAT QUICK REFERENCE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  EVERY SECTION needs a preamble (Type 1)                         │
│    # --- Config ---                                              │
│    # [What this section contains and where values come from]     │
│                                                                  │
│  EVERY TRANSFORM needs intent (Type 2)                           │
│    # INTENT: [What this does and why it's needed]                │
│                                                                  │
│  EVERY NON-OBVIOUS CHOICE needs reasoning (Type 3)               │
│    # REASONING: [Why this approach over alternatives]            │
│                                                                  │
│  EVERY DATA DEPENDENCY needs an assumption (Type 4)              │
│    # ASSUMES: [What must be true about the data]                 │
│                                                                  │
│  EVERY COMPLEX EXPRESSION needs annotation (Type 5)              │
│    code_here  # [What this specific operation does]              │
│                                                                  │
│  DON'T COMMENT: imports, literals, boilerplate, print()          │
│                                                                  │
│  REFERENCE: agent_reference/INLINE_AUDIT_TRAIL.md                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Enforcement

- **research-executor:** Must follow IAT when writing scripts in both Python and R (see `.claude/agents/research-executor.md`)
- **code-reviewer:** Checks IAT compliance in Phase 1 review (WARNING severity) for both languages
- **Stage 10:** Aggregates documentation quality findings from all QA reviews
- **data-scientist skill:** Principle 4 references IAT as the enforced standard
