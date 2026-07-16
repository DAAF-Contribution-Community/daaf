---
name: marimo
description: >-
  Reactive Python notebook system with cell reactivity, UI elements, SQL cells, plotting, and app deployment. DAAF's standard notebook format — stored as Git-friendly .py files, not .ipynb. For DAAF pipelines, Stage 9 literally archives existing executed scripts in bounded comment/pass cells paired with real execution logs; optional display-only cells may preview existing Parquet data or show already-created figures, but may not analyze data or generate figures. Use when assembling Stage 9 research notebooks, building standalone interactive data apps, or converting Jupyter notebooks to marimo format. R equivalent: quarto — when execution language is R, use quarto instead.
metadata:
  audience: research-coders
  domain: python-library
  library-version: "0.19.x"
  skill-last-updated: "2026-03-28"
---

# marimo

marimo reactive Python notebook system for reproducible and interactive data work. Covers cell reactivity model, UI elements (sliders, dropdowns, tables, forms), SQL cells, DataFrame display, plotting integration, validation patterns for data pipelines, and deployment as apps, scripts, or WASM. In DAAF Stage 9, its role narrows to literal script-and-log archival, with only bounded existing-data or existing-figure display allowed; the broader interactive capabilities apply outside Stage 9. Use when assembling Stage 9 research notebooks, developing reactive marimo notebooks, building interactive data apps, or converting Jupyter notebooks to marimo's Git-friendly .py format.

Comprehensive skill for building reactive Python notebooks with marimo. Use decision trees below to find the right guidance, then load detailed references.

## What is Marimo?

marimo is an open-source **reactive Python notebook** that automatically keeps code and outputs consistent:
- **Reactive**: Run a cell, and dependent cells automatically re-run
- **No hidden state**: Delete a cell, its variables are scrubbed from memory
- **Pure Python**: Notebooks stored as `.py` files (Git-friendly)
- **Interactive**: UI elements sync with Python without callbacks
- **Deployable**: Run as scripts, deploy as web apps, export to WASM

## How to Use This Skill

### Reference File Structure

Each topic in `./references/` contains focused documentation:

| File | Purpose | When to Read |
|------|---------|--------------|
| `quickstart.md` | Installation, CLI, first notebook | Starting a new project |
| `reactivity.md` | Cell execution model, dataflow | Understanding marimo's reactive model |
| `validation-patterns.md` | Transform-validate patterns, checkpoints | **REQUIRED for data analysis workflows** |
| `ui-elements.md` | Interactive elements (mo.ui.*) | Adding interactivity |
| `sql-data.md` | SQL cells, dataframes, plotting | Working with data |
| `outputs-layouts.md` | Markdown, layouts, formatting | Styling outputs |
| `apps-deployment.md` | Apps, scripts, export, deploy | Sharing/deploying notebooks |
| `gotchas.md` | Common errors, best practices | Debugging issues |

### Reading Order

1. **New to marimo?** Start with `quickstart.md` then `reactivity.md`
2. **Data analysis workflows?** Read `validation-patterns.md` (REQUIRED for rigorous analysis)
3. **Building features?** Read the relevant topic file
4. **Having issues?** Check `gotchas.md` first

**The reference-file routing in this skill applies to advisory and brainstorming turns as much as implementation.** Recommending an approach, reviewing a plan, or answering a question that touches a routed topic calls for reading the routed reference file just as much as writing code does — the reference files carry curated caveats and environment-specific constraints that this overview and general knowledge lack.

## Related Skills

Load these skills together with marimo for comprehensive workflow support:

**Always Load Together:**
- `data-scientist` - Provides validation methodology and EDA principles that inform notebook structure
- `polars` - DataFrame operations for data transformations within notebooks

**Load for Specific Features:**
- `plotnine` - Static publication-quality plots (ggplot2 style)
- `plotly` - Interactive visualizations with hover/zoom

**Prerequisite Knowledge:**
If new to marimo, first understand:
1. Python basics
2. DataFrame operations (polars or pandas)
3. Basic plotting concepts

---

## CRITICAL: Stage 9 is Script COMPILATION, Not Dashboard Building

**For data research workflows**, the Stage 9 marimo notebook has ONE job: **LITERALLY COPY script file contents into cells.**

### What Stage 9 IS

- **A script viewer** — Copy-paste scripts into marimo cells
- **An audit tool** — Display execution logs to prove what ran
- **A file compiler** — Read files, copy contents, format as notebook

### What Stage 9 is NOT

- ❌ NOT a dashboard builder
- ❌ NOT an interactive analysis tool
- ❌ NOT a place for new aggregations or filters
- ❌ NOT a place for UI widgets (dropdowns, sliders, search)

### Stage 9 Notebook Assembly

Stage 9 is handled by the **notebook-assembler agent** (see `.claude/agents/notebook-assembler.md`), which:
1. READS script files from `scripts/stage{5,6,7,8}_*/`
2. EMITS a recognizable DAAF Marimo archive identity (`import marimo`, `app = marimo.App(...)`, and `Generated by notebook-assembler agent.`)
3. EMITS one contiguous canonical three-cell bundle per script: a literal `mo.md()` header whose `**Script:**` path matches the archive source; an immediately following exact `# SOURCE: scripts/<stage>/<filename>.py` comment/pass-only archive cell; and an immediately following matching `Execution Log (<filename>.py)` accordion with one literal plain-fenced `mo.md()` body
4. REQUIRES the accordion body to contain the real, non-empty, non-placeholder execution log copied verbatim; a missing or ambiguous log blocks assembly rather than producing a placeholder
5. OPTIONALLY ADDS, only after the complete bundle, either a bounded Parquet preview (`pl.read_parquet()` + `head()`/`mo.ui.table()`) or display of an already-created figure (`mo.image()`); neither path performs analysis or creates/modifies a figure, and display cells are not decompiled

All three path labels match one project-relative `scripts/<stage>/<safe-name>.py`
path, where `<stage>` is exactly `stage5_fetch`, `stage6_clean`,
`stage7_transform`, or `stage8_analysis`. Absolute paths, backslashes, traversal
components, and extra path levels are not canonical.

**Archival mechanism:** every copied Python line is prefixed with `# ` (a blank
line becomes `#`) and the archive cell ends with exactly one `pass  # Cell must
have executable statement`, with no other executable content. This keeps the
code visible and searchable without executing it (Marimo cells are live;
uncommented copies would collide on imports and variable names). Canonical
structural recognition centers on the literal `mo.md()` script header, preserving
the intentional Plan-template mapping; Quarto/R instead centers on its exact
`VERBATIM COPY` marker. Bounded legacy forms accepted by the decompiler are
intake compatibility only, not newly emitted output. See
`.claude/agents/notebook-assembler.md` for the emitting template.

### ABSOLUTE PROHIBITIONS for Stage 9

The following are **NEVER ALLOWED** in Stage 9 notebooks:

| Prohibited Element | Why |
|-------------------|-----|
| `mo.ui.dropdown()` | No dropdowns — not a dashboard |
| `mo.ui.slider()` | No sliders — not a dashboard |
| `mo.ui.multiselect()` | No multiselects — not a dashboard |
| `mo.ui.text()` for search | No search boxes — not a dashboard |
| `.group_by()` (new) | No new aggregations — copy script code only |
| `.agg()` (new) | No new aggregations — copy script code only |
| `.pivot()` (new) | No pivot tables — copy script code only |
| `.filter()` in data cells | No filtering — just load and display |
| `.with_columns()` in data cells | No transforms — just load and display |
| "Interactive Filters" section | Not a dashboard |
| "Data Explorer" section | Not a dashboard |
| "Institution Lookup" feature | Not a dashboard |

### The Only Permitted New Display Code

Stage 9 permits exactly two bounded display forms:

1. Preview existing Parquet data without transforming it:
```python
df = pl.read_parquet("path/to/file.parquet")
mo.ui.table(df.head(100))
```
2. Display an already-created Stage 8 figure without generating a new one:
```python
mo.image("output/figures/existing-figure.png")
```

No `.filter()`, `.with_columns()`, `.select()`, aggregation, plotting, or figure generation. The preview is bounded to the first 100 rows; the image cell only displays an existing artifact.

### Anti-Patterns (What BAD Output Looks Like)

```python
# ❌ WRONG — This is new analysis code
tier_summary = risk_data.group_by("tier").agg(pl.len())

# ❌ WRONG — This is a dashboard widget
sector_dropdown = mo.ui.dropdown(options=["Public", "Private"])

# ❌ WRONG — This is a transformation when loading
df = pl.read_parquet("data.parquet").with_columns(pl.col("x") * 2)

# ❌ WRONG — This is filtering
filtered = df.filter(pl.col("state") == "VA")
```

```python
# ✅ CORRECT — Contiguous canonical archive bundle
@app.cell
def _(mo):
    mo.md("""
    ### 5.1: Fetch Data

    **Script:** `scripts/stage5_fetch/01_fetch.py`
    **Status:** CP1 PASSED
    """)
    return

@app.cell
def _():
    # SOURCE: scripts/stage5_fetch/01_fetch.py
    # =========================================================================
    # ARCHIVED SCRIPT CODE (commented out to prevent execution conflicts)
    # Full executable script preserved at: scripts/stage5_fetch/01_fetch.py
    # =========================================================================
    #
    # import polars as pl
    #
    # output_path = "data/raw/file.parquet"
    # print(f"Saved existing output to {output_path}")
    pass  # Cell must have executable statement

@app.cell
def _(mo):
    mo.accordion({"Execution Log (01_fetch.py)": mo.md('''```
Executed: 2026-01-24 14:32:05
Exit code: 0
CP1 STATUS: PASSED
```''')})
    return

# ✅ CORRECT — Either optional display form follows the complete bundle
@app.cell
def _(pl, mo):
    df = pl.read_parquet("data/raw/file.parquet")
    mo.ui.table(df.head(100))

@app.cell
def _(mo):
    mo.image("output/figures/existing-figure.png")
```

**See:**
- `.claude/agents/notebook-assembler.md` for the complete behavioral protocol
- `agent_reference/WORKFLOW_PHASE4_ANALYSIS.md` Stage 9 for template

---

## Quick Decision Trees

### "I need to get started"

```
Getting started?
├─ Install marimo → ./references/quickstart.md
├─ Create first notebook → ./references/quickstart.md
├─ Understand how cells work → ./references/reactivity.md
└─ Run built-in tutorials → marimo tutorial intro
```

### "I need interactivity"

```
Need interactive elements?
├─ Sliders, dropdowns, text inputs → ./references/ui-elements.md
├─ Tables with selection → ./references/ui-elements.md
├─ Forms with submit buttons → ./references/ui-elements.md
├─ Dynamic arrays of elements → ./references/ui-elements.md
├─ Charts with selection → ./references/sql-data.md (plotting section)
└─ Custom widgets (anywidget) → ./references/ui-elements.md
```

### "I need to work with data"

```
Need data operations?
├─ Query dataframes with SQL → ./references/sql-data.md
├─ Connect to databases (Postgres, SQLite) → ./references/sql-data.md
├─ Display/filter dataframes → ./references/sql-data.md
├─ Create plots (Altair, Matplotlib, Plotly) → ./references/sql-data.md
└─ Interactive data exploration → ./references/sql-data.md
```

### "I need to format output"

```
Need output formatting?
├─ Write markdown with Python values → ./references/outputs-layouts.md
├─ Arrange elements (hstack, vstack) → ./references/outputs-layouts.md
├─ Tabs, accordions, sidebars → ./references/outputs-layouts.md
├─ Progress bars, spinners → ./references/outputs-layouts.md
└─ Conditional output display → ./references/outputs-layouts.md
```

### "I need to share/deploy"

```
Need to share or deploy?
├─ Run as read-only web app → ./references/apps-deployment.md
├─ Execute as Python script → ./references/apps-deployment.md
├─ Export to HTML/WASM → ./references/apps-deployment.md
├─ Deploy with Docker → ./references/apps-deployment.md
├─ Grid/slides layout → ./references/apps-deployment.md
└─ Convert from Jupyter → ./references/quickstart.md
```

### "Something isn't working"

```
Having issues?
├─ "Multiple definitions" error → ./references/gotchas.md
├─ Cells not re-running as expected → ./references/reactivity.md
├─ UI element not updating → ./references/gotchas.md
├─ Cycle dependency error → ./references/gotchas.md
├─ Expensive cells running too often → ./references/gotchas.md
└─ Mutations not triggering updates → ./references/reactivity.md
```

## Quick Reference

### Essential CLI Commands

| Command | Purpose |
|---------|---------|
| `marimo edit` | Launch notebook server |
| `marimo edit notebook.py` | Create/edit specific notebook |
| `marimo run notebook.py` | Run as read-only app |
| `python notebook.py` | Execute as script |
| `marimo tutorial intro` | Run interactive tutorial |
| `marimo convert nb.ipynb -o nb.py` | Convert other formats INTO marimo (inbound only) |
| `marimo export html notebook.py` | Export to HTML |

> **Docker:** When running in a container, add `--host 0.0.0.0 --port 2718 --headless` to `run` and `edit` commands.

### Core marimo Library

| Function | Purpose |
|----------|---------|
| `mo.md("text")` | Render markdown |
| `mo.ui.slider(start, stop)` | Create slider |
| `mo.ui.dropdown(options)` | Create dropdown |
| `mo.ui.table(data)` | Interactive table |
| `mo.hstack([...])` | Horizontal layout |
| `mo.vstack([...])` | Vertical layout |
| `mo.sql(f"SELECT ...")` | SQL query |
| `mo.stop(condition)` | Conditionally stop execution |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Installation & Setup | `./references/quickstart.md` |
| CLI Commands | `./references/quickstart.md` |
| Reactive Execution | `./references/reactivity.md` |
| Cell Dataflow | `./references/reactivity.md` |
| **Validation Patterns** | `./references/validation-patterns.md` |
| **Transform-Validate Pairs** | `./references/validation-patterns.md` |
| **Data Quality Checkpoints** | `./references/validation-patterns.md` |
| Sliders & Inputs | `./references/ui-elements.md` |
| Tables & Forms | `./references/ui-elements.md` |
| SQL Cells | `./references/sql-data.md` |
| DataFrames | `./references/sql-data.md` |
| Plotting | `./references/sql-data.md` |
| Markdown | `./references/outputs-layouts.md` |
| Layouts | `./references/outputs-layouts.md` |
| Apps & Scripts | `./references/apps-deployment.md` |
| Export & Deploy | `./references/apps-deployment.md` |
| Common Errors | `./references/gotchas.md` |
| Best Practices | `./references/gotchas.md` |

## Citation

When this library is used as a primary analytical tool, include in the report's
Software & Tools references:

> marimo team. marimo: Reactive Python notebook [Computer software]. https://marimo.io/

**Cite when:** The analysis notebook is delivered as a marimo notebook (typically always true in DAAF pipelines).
**Do not cite when:** marimo is not used for the analysis delivery format.
