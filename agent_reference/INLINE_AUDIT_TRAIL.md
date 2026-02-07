# Inline Audit Trail (IAT) Protocol

The Inline Audit Trail is the mandatory documentation standard for all Python scripts produced in the research workflow. Every script must be self-explanatory to a human reader **without running the code**.

---

## Purpose & Philosophy

Research scripts are **write-once, execute-once, archive** artifacts. Unlike application code, they are read far more often than they are modified. The IAT ensures that:

1. **Auditability:** A reviewer can follow every decision by reading the source alone
2. **Reproducibility:** Assumptions and reasoning are captured alongside the code, not in separate docs
3. **QA Efficiency:** Code-reviewer can verify methodology alignment without re-deriving intent
4. **Onboarding:** New team members understand *why* a transformation was done, not just *what* it does

**The IAT philosophy:**
> Code tells you HOW. Comments tell you WHY, WHAT FOR, and WHAT'S ASSUMED.

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
# Persist results in both parquet (for processing) and CSV (for sharing).
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
| Obvious imports | `import polars as pl` | Universal knowledge |
| Simple variable assignment to a literal | `DATE_PREFIX = "2026-01-24"` | Self-evident |
| Standard boilerplate | `#!/usr/bin/env python3` | Convention |
| Print separators | `print("=" * 60)` | Visual formatting |
| Obvious operations | `df.shape[0]` | Self-explanatory |
| The `EXECUTION LOG` section | Auto-appended output | Not authored code |

**Rule of thumb:** If removing the comment would leave a reader confused about *why* something is done, the comment is needed. If removing it would only leave them unsure of *what* the code literally does (and the code is clear), skip it.

---

## Before/After Examples

### Example 1: Stage 5 Fetch Script

**BEFORE (sparse):**
```python
# --- Config ---
PROJECT_DIR = Path("/app/python_researcher/research/2026-01-24 School Analysis")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-01-24"
BASE_URL = "https://educationdata.urban.org/api/v1/schools/ccd/directory"
YEARS = list(range(2018, 2023))

# --- Fetch ---
print("=" * 60)
print("Stage 5.1: Fetch CCD school directory")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

all_data = []
for year in YEARS:
    url = f"{BASE_URL}/{year}/"
    while url:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        data = response.json()
        all_data.extend(data["results"])
        url = data.get("next")
        if url:
            time.sleep(0.1)
```

**AFTER (IAT-compliant):**
```python
# --- Config ---
# Configuration constants derived from the Plan's query specification (Section 4.2).
# The Urban Institute Education Data Portal provides CCD school directory data
# via a paginated REST API. We fetch 5 years to match the Plan's year range.
PROJECT_DIR = Path("/app/python_researcher/research/2026-01-24 School Analysis")
DATA_RAW = PROJECT_DIR / "data" / "raw"
DATE_PREFIX = "2026-01-24"

BASE_URL = "https://educationdata.urban.org/api/v1/schools/ccd/directory"
YEARS = list(range(2018, 2023))  # 2018-2022 per Plan query specification

OUTPUT_PARQUET = DATA_RAW / f"{DATE_PREFIX}_ccd_schools.parquet"
OUTPUT_CSV = DATA_RAW / f"{DATE_PREFIX}_ccd_schools.csv"

# --- Fetch ---
# INTENT: Retrieve CCD school directory records for all 5 years from the
# Education Data Portal API. The API returns paginated JSON results (~5K
# records per page). We accumulate all pages for all years into a single list,
# then convert to a Polars DataFrame.
#
# REASONING: Fetching year-by-year (rather than a single multi-year query)
# because the API endpoint requires year as a path parameter, not a query
# parameter. This is how the Urban Institute API is structured.
#
# ASSUMES:
#   - API is available and returns JSON with "results" and "next" keys
#   - Each year returns ~4,000-5,000 school records (based on Plan estimate)
#   - "next" key is null on the final page of results
print("=" * 60)
print("Stage 5.1: Fetch CCD school directory")
print("=" * 60)

DATA_RAW.mkdir(parents=True, exist_ok=True)

all_data = []
for year in YEARS:
    print(f"  Year {year}...", end=" ")
    url = f"{BASE_URL}/{year}/"
    page_count = 0

    while url:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        data = response.json()
        all_data.extend(data["results"])
        page_count += 1
        url = data.get("next")  # None on final page terminates the loop
        if url:
            time.sleep(0.1)  # Rate limiting: 100ms between pages to avoid 429s

    print(f"Fetched {page_count} pages")
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
# visualization for Observable Truth #1: "Stakeholders can see the correlation
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

- **research-executor:** Must follow IAT when writing scripts (see `agents/research-executor.md`)
- **code-reviewer:** Checks IAT compliance in Phase 1 review (WARNING severity)
- **Stage 10:** Aggregates documentation quality findings from all QA reviews
- **data-scientist skill:** Principle 4 references IAT as the enforced standard
