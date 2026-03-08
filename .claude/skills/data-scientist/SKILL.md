---
name: data-scientist
description: Python data science methodology and mindset. Enforces rigorous EDA, data validation, documentation, and verification practices before and during analysis. Use for any data analysis, exploration, transformation, or modeling task in Python.
metadata:
  audience: python-developers
  domain: data-science
---

# Data Scientist Skill

Establishes a rigorous, methodical approach to data science work. This skill is about *how* to think and work, not specific tools. Load specialized skills (polars, plotnine, plotly, marimo, etc.) for tool-specific guidance.

## Core Principles - NON-NEGOTIABLE

These five principles must guide ALL data science work. They are not optional.

### Principle 1: Data Robustness First

**ALWAYS check data before operating on it.**

Before ANY analysis or transformation:
- Check shape, types, and memory usage
- Examine value distributions and ranges
- Identify and characterize missing values (count, percentage, pattern)
- Understand what uniquely identifies each row (granularity)
- Look for outliers and anomalies

Be VERBOSE about what you're checking and what you find. Never assume data is clean.

```python
# ALWAYS start with this pattern
print(f"Shape: {df.shape}")
print(f"Columns: {df.columns.to_list()}")
print(f"Types:\n{df.dtypes}")
print(f"Null counts:\n{df.null_count()}")
print(f"Sample:\n{df.sample(5)}")
```

This principle applies only when you are conducting actual data work. Do NOT conduct net new analyses or data inspections when tasked with compiling past work (e.g., analytic notebook creation), or synthesizing prior analyses into a report (e.g., final report writing).

### Principle 2: Documentation First

**ALWAYS understand or create data documentation.**

Before analysis:
- Seek data dictionaries, schemas, or documentation
- Understand where data comes from (provenance)
- Learn collection methods and their implications
- Identify known quality issues or caveats
- Clarify what each column means in business context

If documentation doesn't exist, CREATE IT as you learn about the data.

### Principle 3: Verify Every Operation

**NEVER assume a transformation worked correctly.**

For EVERY data operation:
- Check row counts before and after
- Examine random samples of affected rows
- Validate that expected changes occurred
- Confirm no unintended side effects
- Document what you checked and what you found

```python
# Before transformation
print(f"Before: {len(df)} rows, columns: {df.columns.to_list()}")
sample_before = df.filter(pl.col("id").is_in([1, 42, 100]))

# After transformation
print(f"After: {len(result)} rows, columns: {result.columns.to_list()}")
sample_after = result.filter(pl.col("id").is_in([1, 42, 100]))
print(f"Sample comparison:\nBefore:\n{sample_before}\nAfter:\n{sample_after}")
```

### Principle 4: Thorough Code Documentation (ENFORCED)

**Write extensive comments explaining your reasoning. This is MANDATORY, not optional.**

In research workflows, follow the **Inline Audit Trail (IAT)** standard (see `agent_reference/INLINE_AUDIT_TRAIL.md`). The IAT standard is enforced during QA review — scripts with sparse documentation receive WARNING findings.

Every code block should explain:
- WHAT you're trying to accomplish (the goal) → IAT Type 2: Intent Comment
- WHY you chose this approach (the reasoning) → IAT Type 3: Reasoning Comment
- WHAT assumptions you're making (the dependencies) → IAT Type 4: Assumption Comment

For tests and validations, explain:
- What behavior you're checking
- What would indicate success vs. failure
- Why this check matters

### Principle 5: Focus on Research Questions

**Balance rigor with usefulness.**

Always consider:
- What question are we actually answering?
- What level of rigor does this decision require?
- Are there multiple valid approaches with different tradeoffs?
- Should I check with the user before proceeding?

CHECK IN with users when:
- Multiple valid methodologies exist
- Tradeoffs between precision and practicality arise
- Findings are surprising or counterintuitive
- Scope might need adjustment

## Related Skills - When to Load

**Core Workflow Skills (Load Together):**
- `polars` - Required for DataFrame operations; data-scientist provides methodology, polars provides syntax
- `marimo` - Required for creating validated notebooks; data-scientist defines validation patterns, marimo provides implementation

**For Data Analysis Workflows:**

In the research pipeline, data-scientist methodology is applied within the **file-first execution pattern**:
- Write script files FIRST (to `scripts/stage{N}_{type}/`)
- Execute via Bash with automatic output capture wrapper script
- Validation results get automatically embedded in scripts as comments
- Marimo notebook assembles validated scripts for interactive review

Closely read `agent_reference/EXECUTION_CAPTURE.md` for the mandatory file-first execution protocol covering complete code file writing, output capture, and file versioning rules.

**Load for Specific Needs:**
```
What task are you performing?
├─ Statistical analysis (regression, robustness checks)
│   └─ Stage 8.1 — use data-scientist methodology + polars for data prep
├─ Data visualization (any kind)
│   └─ Stage 8.2 — FIRST read visualization reference files below:
│       ├─ ./references/visualization-design.md (chart selection, encoding, emphasis)
│       └─ ./references/visualization-execution.md (color, labeling, accessibility, export)
│       THEN load the tool-specific skill:
│       ├─ Static plots → Load `plotnine` skill for grammar of graphics
│       └─ Interactive plots → Load `plotly` skill for interactive charts
```

**Visualization loading order matters:** The reference files provide *design principles* (what chart to use, how to direct attention, how to handle color accessibly). The tool skills provide *syntax* (how to code it). Read the design guidance first so implementation choices are principled, not ad-hoc.

**For Domain-Specific Analysis (e.g., CCD Education Data):**
- Load relevant `*-data-source-*` skill first to understand domain-specific data caveats
- Then apply data-scientist methodology with that context

**Prerequisite Knowledge:**
This skill assumes familiarity with:
- Python programming basics
- DataFrame concepts (rows, columns, filtering)
- Basic statistical concepts (mean, distribution, correlation)

**Important:** This skill provides the METHODOLOGY. The specialized skills provide TOOL KNOWLEDGE. Use both together.

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `eda-checklist.md` | Detailed EDA procedures and validation checks | Starting analysis on new data |
| `data-documentation.md` | Understanding and creating data documentation | Working with unfamiliar data |
| `transformation-validation.md` | Validating data operations | Before/after any transformation |
| `code-documentation.md` | Writing thorough comments and docs | Writing any analysis code |
| `research-questions.md` | Framing questions, stakeholder communication | Scoping work, presenting findings |
| `visualization-design.md` | Chart selection, visual encoding, emphasis, integrity | **Before creating any visualization** |
| `visualization-execution.md` | Color palettes, accessibility, labeling, typography, export | **When producing figures** |

### Validation Tracking

For multi-step transformations, track validation state with a simple dict:

```python
validation_log = {}

# After each transformation step:
validation_log["Filter to high schools"] = {
    "pre_rows": pre_rows,
    "post_rows": result.shape[0],
    "status": "PASSED" if result.shape[0] > 0 else "FAILED",
}

# Print summary at end:
for step, info in validation_log.items():
    print(f"  [{info['status']}] {step}: {info['pre_rows']:,} → {info['post_rows']:,}")
```

This is inline code, not a separate module. Never create a `validation.py` or import a validation class.

## Quick Decision Trees

### "I'm starting a new analysis"

```
Starting new analysis?
├─ Do I have data documentation?
│   ├─ Yes → Read it thoroughly first
│   │         → ./references/data-documentation.md
│   └─ No → Create it as you explore
│           → ./references/data-documentation.md
├─ Have I profiled the data?
│   └─ No → Run full EDA checklist
│           → ./references/eda-checklist.md
├─ Do I understand the research question?
│   └─ Unclear → Clarify with stakeholder
│                → ./references/research-questions.md
└─ Ready to analyze → Document as you go
                      → ./references/code-documentation.md
```

### "I have unfamiliar data"

```
Unfamiliar data?
├─ Step 1: Basic inspection
│   └─ Shape, types, head/tail/sample
│      → ./references/eda-checklist.md
├─ Step 2: Understand granularity
│   └─ What does each row represent?
│   └─ What columns uniquely identify a row?
├─ Step 3: Check data quality
│   └─ Missing values, duplicates, outliers
│      → ./references/eda-checklist.md
├─ Step 4: Seek documentation
│   └─ Data dictionary, schema, provenance
│      → ./references/data-documentation.md
└─ Step 5: Document findings
    └─ Create documentation if none exists
```

### "I need to transform data"

```
Transforming data?
├─ Before transformation:
│   ├─ Document current state (shape, sample)
│   ├─ Identify what SHOULD change
│   └─ Identify what should NOT change
│      → ./references/transformation-validation.md
├─ After transformation:
│   ├─ Verify shape changes are expected
│   ├─ Check random sample of results
│   ├─ Validate invariants (sums, counts)
│   └─ Document what you verified
│      → ./references/transformation-validation.md
└─ For joins specifically:
    ├─ Check for unintended row duplication
    ├─ Check for unintended data loss
    └─ Validate join keys match expectations
```

### "I need to communicate findings"

```
Communicating findings?
├─ Have I documented limitations?
│   └─ No → List caveats and assumptions
│           → ./references/research-questions.md
├─ Am I making causal claims?
│   └─ Yes → Ensure justified; prefer correlational language
│            → ./references/research-questions.md
├─ Is uncertainty quantified?
│   └─ No → Add confidence intervals or ranges
└─ Have I checked in with stakeholder?
    └─ No → Validate findings align with expectations
```

### "I need to create a visualization"

```
What kind of visualization task?
├─ Choosing what chart to make
│   └─ → ./references/visualization-design.md
├─ Directing attention / emphasis strategy
│   └─ → ./references/visualization-design.md
├─ Selecting colors or ensuring accessibility
│   └─ → ./references/visualization-execution.md
├─ Labeling, titling, or annotating
│   └─ → ./references/visualization-execution.md
├─ Making it publication-ready (export, DPI, fonts)
│   └─ → ./references/visualization-execution.md
├─ Ensuring project consistency (theme, palette)
│   └─ → ./references/visualization-execution.md
└─ Tool-specific syntax (geoms, traces, themes)
    ├─ Static plots → Load `plotnine` skill
    └─ Interactive plots → Load `plotly` skill
```

## Essential Workflows

### New Data Workflow

When you receive new data, ALWAYS follow this sequence:

1. **Load and inspect** (do not transform yet)
   ```python
   # Load data
   df = pl.read_csv("data.csv")  # or scan_csv for lazy
   
   # Immediate inspection
   print(f"Shape: {df.shape}")
   print(f"Columns: {df.columns}")
   print(f"Types:\n{df.dtypes}")
   print(f"First 5 rows:\n{df.head()}")
   print(f"Last 5 rows:\n{df.tail()}")
   print(f"Random sample:\n{df.sample(5)}")
   ```

2. **Check data quality**
   ```python
   # Missing values
   print(f"Null counts:\n{df.null_count()}")
   print(f"Null percentages:\n{df.null_count() / len(df) * 100}")
   
   # Duplicates
   print(f"Duplicate rows: {len(df) - len(df.unique())}")
   
   # Unique values per column
   for col in df.columns:
       print(f"{col}: {df[col].n_unique()} unique values")
   ```

3. **Understand distributions**
   ```python
   # Numerical columns
   print(df.describe())
   
   # Categorical columns - value counts
   for col in df.select(pl.col(pl.String)).columns:
       print(f"\n{col}:\n{df[col].value_counts().head(10)}")
   ```

4. **Identify granularity**
   ```python
   # What uniquely identifies a row?
   # Test candidate keys
   candidate_keys = ["id", "user_id", ["user_id", "date"]]
   for key in candidate_keys:
       cols = [key] if isinstance(key, str) else key
       unique_count = df.select(cols).n_unique()
       print(f"{cols}: {unique_count} unique vs {len(df)} rows")
   ```

5. **Document findings** before proceeding

### Transformation Workflow

For ANY data transformation:

1. **Document pre-state**
   ```python
   # Record state before transformation
   pre_shape = df.shape
   pre_columns = df.columns.copy()
   pre_sample = df.sample(10, seed=42)  # Reproducible sample
   pre_sum = df.select(pl.col("amount").sum()).item()  # If applicable
   ```

2. **Perform transformation with comments**
   ```python
   # GOAL: Filter to active users and calculate total spend
   # REASONING: We only want users who logged in within 30 days
   # EXPECTED: Fewer rows, same columns, preserved sum for included rows
   result = (
       df
       .filter(pl.col("last_login") > cutoff_date)  # Remove inactive
       .group_by("user_id")
       .agg(pl.col("amount").sum().alias("total_spend"))
   )
   ```

3. **Validate post-state**
   ```python
   # Verify transformation results
   post_shape = result.shape
   print(f"Shape: {pre_shape} -> {post_shape}")
   
   # Check sample of results
   sample_ids = pre_sample["user_id"].to_list()[:3]
   print(f"Sample before:\n{pre_sample.filter(pl.col('user_id').is_in(sample_ids))}")
   print(f"Sample after:\n{result.filter(pl.col('user_id').is_in(sample_ids))}")
   
   # Validate invariants where applicable
   # (e.g., sum should be preserved or explainably different)
   ```

4. **Document what you verified**

### Analysis Workflow

From question to answer:

1. **Clarify the question**
   - What decision will this inform?
   - What would a "good" answer look like?
   - What level of rigor is required?

2. **Assess data fitness**
   - Does the data contain what we need?
   - What are the limitations?
   - Are there gaps or quality issues?

3. **Choose methodology**
   - What approaches are valid?
   - What are the tradeoffs?
   - CHECK WITH USER if multiple valid options

4. **Execute with verification**
   - Follow transformation workflow
   - Document each step thoroughly

5. **Validate findings**
   - Do results make sense?
   - Cross-check with known facts
   - Identify limitations and caveats

6. **Communicate with appropriate uncertainty**

## Quick Checklists

### Initial Data Inspection Checklist

- [ ] Loaded data successfully
- [ ] Checked shape (rows x columns)
- [ ] Reviewed column names
- [ ] Checked data types
- [ ] Examined head, tail, and random sample
- [ ] Counted missing values per column
- [ ] Checked for duplicate rows
- [ ] Identified unique value counts per column
- [ ] Generated summary statistics
- [ ] Identified granularity (what uniquely identifies a row)
- [ ] Documented findings

### Pre-Transformation Checklist

- [ ] Documented current shape and columns
- [ ] Saved sample of data for comparison
- [ ] Recorded relevant aggregates (sums, counts)
- [ ] Stated what SHOULD change
- [ ] Stated what should NOT change
- [ ] Explained WHY this transformation is needed

### Post-Transformation Checklist

- [ ] Verified shape change matches expectations
- [ ] Compared sample before/after
- [ ] Validated invariants are preserved
- [ ] Checked for unintended nulls
- [ ] Checked for unintended duplicates
- [ ] Documented what was verified and results

### Documentation Checklist

- [ ] Data source documented
- [ ] Each column defined
- [ ] Missing value conventions explained
- [ ] Granularity/unit of observation stated
- [ ] Known quality issues noted
- [ ] Transformation history recorded

## Marimo Integration

When working in marimo notebooks:

### Cell Organization Pattern

```python
# Cell 1: Imports and setup
import marimo as mo
import polars as pl

# Cell 2: Data loading (separate cell for reactivity)
df = pl.read_csv("data.csv")

# Cell 3: Data inspection (markdown + code)
mo.md("## Data Inspection")
# ... inspection code ...

# Cell 4: Data quality checks
mo.md("## Data Quality")
# ... quality checks ...

# Cell 5+: Analysis cells, each with:
# - Markdown explaining goal
# - Code with thorough comments
# - Validation of results
```

### Using Reactivity for Validation

```python
# Create interactive validators
validation_column = mo.ui.dropdown(
    options=df.columns,
    label="Select column to validate"
)

# Reactive validation display
mo.md(f"""
### Validation for `{validation_column.value}`
- Null count: {df[validation_column.value].null_count()}
- Unique values: {df[validation_column.value].n_unique()}
- Sample values: {df[validation_column.value].head(5).to_list()}
""")
```

### Documentation Cells

Use markdown cells liberally:
- Before code: explain what you're about to do and why
- After code: summarize findings and implications
- At decision points: document choices made

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Initial data inspection | `./references/eda-checklist.md` |
| Missing value analysis | `./references/eda-checklist.md` |
| Distribution analysis | `./references/eda-checklist.md` |
| Outlier detection | `./references/eda-checklist.md` |
| Uniqueness and cardinality | `./references/eda-checklist.md` |
| Correlation analysis | `./references/eda-checklist.md` |
| Data dictionaries | `./references/data-documentation.md` |
| Data provenance | `./references/data-documentation.md` |
| Working with undocumented data | `./references/data-documentation.md` |
| Questions to ask about data | `./references/data-documentation.md` |
| Before/after validation | `./references/transformation-validation.md` |
| Join validation | `./references/transformation-validation.md` |
| Aggregation validation | `./references/transformation-validation.md` |
| Schema validation (Pandera) | `./references/transformation-validation.md` |
| Common transformation errors | `./references/transformation-validation.md` |
| Comment philosophy | `./references/code-documentation.md` |
| Docstring patterns | `./references/code-documentation.md` |
| Notebook documentation | `./references/code-documentation.md` |
| Test documentation | `./references/code-documentation.md` |
| Research question formulation | `./references/research-questions.md` |
| Rigor vs. practicality | `./references/research-questions.md` |
| Stakeholder check-ins | `./references/research-questions.md` |
| Communicating uncertainty | `./references/research-questions.md` |
| Causal vs. correlational claims | `./references/research-questions.md` |
| Chart selection by relationship | `./references/visualization-design.md` |
| Visual encoding hierarchy | `./references/visualization-design.md` |
| Exploratory vs. explanatory viz | `./references/visualization-design.md` |
| Small multiples | `./references/visualization-design.md` |
| Common visualization pitfalls | `./references/visualization-design.md` |
| Graphical integrity | `./references/visualization-design.md` |
| Color palette selection | `./references/visualization-execution.md` |
| Colorblind accessibility | `./references/visualization-execution.md` |
| Direct labeling vs. legends | `./references/visualization-execution.md` |
| Chart titles and annotation | `./references/visualization-execution.md` |
| Typography and layout | `./references/visualization-execution.md` |
| Export standards (DPI, format) | `./references/visualization-execution.md` |
| Project visual consistency | `./references/visualization-execution.md` |
| Figure captions | `./references/visualization-execution.md` |
