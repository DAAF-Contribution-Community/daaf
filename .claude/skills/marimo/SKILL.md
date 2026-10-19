---
name: marimo
description: >-
  Reactive Python notebook system with cell reactivity, UI elements, SQL cells, plotting, and app deployment. DAAF's standard notebook format — stored as Git-friendly .py files, not .ipynb. For DAAF pipelines, Stage 9 literally archives existing executed scripts in bounded comment/pass cells paired with real execution logs; optional display-only cells may preview existing Parquet data or show already-created figures, but may not analyze data or generate figures. Use when assembling Stage 9 research notebooks, building standalone interactive data apps, or converting Jupyter notebooks to marimo format. R equivalent: quarto — when execution language is R, use quarto instead.
metadata:
  audience: research-coders
  domain: python-library
  library-version: "0.25.0"
  skill-last-updated: "2026-10-16"
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
| `quickstart.md` | Installation, CLI, `marimo check` lint rules, first notebook | Starting a new project; linting a notebook |
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
3. EMITS one contiguous canonical three-cell bundle per script: a literal `mo.md()` header whose `**Script:**` path matches the archive source; an immediately following exact `# SOURCE: scripts/<stage>/<filename>.py` comment/pass-only archive cell; and an immediately following matching `Execution Log (<filename>.py)` accordion with one plain-fenced body in a raw `mo.md(r'''...''')` literal (`r"""` when the log contains `'''`)
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
| `mo.ui.dataframe()` | No transform editor — it filters, groups, aggregates, and pivots |
| `mo.ui.data_editor()` | No data editing — display existing data only |
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
df_5_1 = pl.read_parquet(PROJECT_DIR / "data/raw/file.parquet")  # one unique name per preview cell
mo.ui.table(df_5_1.head(100), selection=None, show_column_summaries=False)
```
2. Display an already-created Stage 8 figure without generating a new one:
```python
mo.image(PROJECT_DIR / "output/figures/existing-figure.png")
```

No `.filter()`, `.with_columns()`, `.select()`, aggregation, plotting, or figure generation. The preview is bounded to the first 100 rows and shown as a plain read-only table: `selection=None` drops the row-selection checkboxes (the default is `"multi"`) and `show_column_summaries=False` drops the per-column summary charts. The image cell only displays an existing artifact.

Both forms read `PROJECT_DIR`, the absolute project `Path` the notebook defines in its own cell, and each preview gets its own name. `marimo export html` resolves a relative path against the shell's working directory, not the notebook's folder; a name assigned in two cells is a breaking MB002 error; and `mo.image()` given a string path to a missing figure renders a broken image without failing, while a `Path` fails the cell. So pass the `Path` itself to `mo.image()`, never `str(PROJECT_DIR / ...)`.

### Tooling Cautions for Stage 9 Notebooks

A Stage 9 notebook is a literal archive that `scripts/decompile_notebook.py` must be able to read back, so some routine marimo actions damage it:

- **Never `marimo check --fix` or `--unsafe-fixes`.** Every archive cell is reported as MF004 empty-cells with an unsafe fix that deletes it. Read-only `marimo check` is fine (see `./references/quickstart.md` > Check (Lint)); the Stage 9 check commands live in `.claude/agents/notebook-assembler.md`.
- **Don't re-save it from the marimo editor.** Saving can write cell options into decorators, such as `@app.cell(hide_code=True)` or, new in 0.25.0, `@app.cell(expand_output=True)` when an output is expanded. The decompiler accepts only a bare `@app.cell` line and rejects the notebook.
- **Keep the execution-log accordion keyword-free.** `mo.accordion(..., expanded=...)` (new since 0.19.11) or any other keyword makes decompilation fail.
- **Put each execution log in a raw literal**, `mo.md(r'''...''')` (or `r"""..."""` when the log contains `'''`). In a non-raw string Python decodes backslashes in the log: a Windows path `C:\new\table` silently gains a line break and a tab that `marimo check` and `export html` cannot see, and `\U` or `\N` make the cell unparsable. The decompiler warns about non-raw log literals that contain backslashes, and that warning fails Step 6c condition (i).
- **Make the log's code fence longer than any backtick run in the log.** The fence is three backticks unless the log holds a run of three or more (a printed Markdown fence, for example); then it is one backtick longer than the longest run, and the closing fence has the same length. A log line equal to the fence would close it early and cut the displayed log off; `marimo check` and `marimo export html` (Steps 6a and 6b) cannot see that. marimo's `pymdownx.superfences` closes at exactly the fence length, CommonMark at that length or more, and the longer fence is safe under both. The decompiler accepts any matched fence of three or more backticks and warns when a log line can still close it early, which fails Step 6c condition (i) (notebook-assembler "Marimo: Check the Log Before Emitting Cell 3").
- **Trailing spaces and tabs on code or log lines do not survive the Write and Edit tools**, and Step 6c cannot see the loss. Grep each final script for `[ \t]$` and report every match as an INFO under Issues Found (notebook-assembler Step 6c, "What the two whitespace flags absorb").
- **No `--sandbox`.** It runs the notebook outside the image's environment, and on `marimo edit` and `marimo run` it also rewrites the notebook file, adding a PEP 723 block (see `./references/apps-deployment.md` > Docker with Sandbox).
- **`marimo export html` writes `__marimo__/session/<notebook>.py.json` beside the notebook** every time (no opt-out); DAAF's `.gitignore` excludes `__marimo__/`.

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
    mo.accordion({"Execution Log (01_fetch.py)": mo.md(r'''```
Executed: 2026-01-24 14:32:05
Exit code: 0
Checks: 5 passed, 0 warnings, 0 failed, 0 not verified, 0 skipped
CP1 VALIDATION: PASSED
```''')})
    return

# ✅ CORRECT — Either optional display form follows the complete bundle
# (PROJECT_DIR-based Path, one unique name per preview)
@app.cell
def _(pl, mo, PROJECT_DIR):
    df_5_1 = pl.read_parquet(PROJECT_DIR / "data/raw/file.parquet")
    mo.ui.table(df_5_1.head(100), selection=None, show_column_summaries=False)

@app.cell
def _(mo, PROJECT_DIR):
    mo.image(PROJECT_DIR / "output/figures/existing-figure.png")
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
├─ Mutations not triggering updates → ./references/reactivity.md
├─ Lint a notebook without running it (marimo check) → ./references/quickstart.md
└─ Check that every cell executes (export html) → ./references/apps-deployment.md
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
| `marimo check notebook.py --format json` | Lint without running (`--select MB` for breaking rules only) |
| `marimo export html notebook.py -o out.html` | Run every cell and export to HTML; exits 1 if any cell fails |

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
| `mo.stop(condition)` | Stop this cell and the cells that read its names |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Installation & Setup | `./references/quickstart.md` |
| CLI Commands | `./references/quickstart.md` |
| Linting (`marimo check`, rule codes) | `./references/quickstart.md` |
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
| `marimo run` Is Not an Execution Test | `./references/apps-deployment.md` |
| Export & Deploy | `./references/apps-deployment.md` |
| Session snapshots (`__marimo__/`) | `./references/apps-deployment.md` |
| Common Errors | `./references/gotchas.md` |
| Best Practices | `./references/gotchas.md` |

## Citation

When this library is used as a primary analytical tool, include in the report's
Software & Tools references:

> marimo team. marimo: Reactive Python notebook [Computer software]. https://marimo.io/

**Cite when:** The analysis notebook is delivered as a marimo notebook (typically always true in DAAF pipelines).
**Do not cite when:** marimo is not used for the analysis delivery format.
