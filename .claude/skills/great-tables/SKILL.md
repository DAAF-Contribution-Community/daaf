---
name: great-tables
description: >-
  Python table formatting with great-tables: publication-quality display tables
  from Polars/pandas DataFrames. GT() grammar-of-tables object, fmt_*() number
  formatting, tab_*() structure (header, spanners, stub, source notes), tab_style()
  and data_color() styling, cols_*() column operations, and HTML/LaTeX export via
  as_raw_html()/write_raw_html()/as_latex(). Use when execution language is Python
  and the task involves formatted data tables, summary tables, or descriptive-stat
  tables for reports. R equivalent: gt (use when execution language is R). For
  regression/model tables in Python, use the estimator's own output (pyfixest
  etable(), statsmodels summary()) — great-tables has no modelsummary equivalent.
  For figures/charts use plotnine or plotly, not this skill.
metadata:
  audience: research-coders
  domain: python-library
  library-version: "0.21.0"
  skill-last-updated: "2026-07-13"
---

# Great Tables Skill

great-tables is the Python implementation of the **grammar of tables** — the same
grammar as R's gt, by the same author (Rich Iannone, Posit). It builds
publication-quality display tables declaratively by layering formatting, structure,
and style onto a `GT()` object. Use when execution language is Python and the task
involves creating formatted data tables, cross-tabulations, or descriptive-statistics
tables for reports and papers. great-tables accepts Polars DataFrames natively (DAAF's
default) as well as pandas. For figures use `plotnine` (static) or `plotly`
(interactive); for regression/model comparison tables great-tables has no
modelsummary-style helper, so use the estimator's own tabular output instead
(pyfixest `etable()`, statsmodels `.summary()`). R counterpart: the `gt` skill —
substitute it when execution language is R.

## What is great-tables?

great-tables implements a **grammar of tables**, analogous to plotnine/ggplot2's
grammar of graphics but for tabular output:

- **Declarative**: build tables by chaining formatting, structure, and style methods
- **Method-chaining**: every method returns a new `GT` object, so operations chain
  with `.` (Python) rather than R's `|>` pipe
- **Rich formatting**: `fmt_number`, `fmt_percent`, `fmt_currency`, `fmt_date`,
  `fmt_markdown`, conditional styling, color scales
- **Structured**: header (title/subtitle), column spanners, row-group stub,
  grand summary rows, source notes, footnotes
- **DataFrame-native**: pass a Polars DataFrame directly to `GT()` (pandas also
  accepted; Polars is the DAAF default)

**Probe-verified against installed 0.21.0** (2026-07-13): all API claims in this
skill and its references were executed against the package. Version-specific caveats
(e.g., `grand_summary_rows` expecting Polars expressions, `cols_merge` 0-based
indices, `save()` needing selenium) are documented at their point of use.

## Version Notes (0.21.0)

- **Canonical constructor is `gt.GT(df)`.** The `GT.from_data()` classmethod is
  broken in 0.21.0 (raises `TypeError` on an internal `_tbl_data` kwarg) — do not
  use it. Probe: `04_extras_a.py` in the R_Support sessionF scratch.
- **`grand_summary_rows(fns=...)` expects Polars expressions**, not R-style string
  aggregator names. Use `{"Total": pl.all().sum()}`, not `{"Total": "sum"}`. It also
  does **not** support the `columns=` selection argument in 0.21.0 (raises
  `NotImplementedError`) — summaries apply across all numeric columns.
- **`cols_merge(pattern=...)` uses 0-based `{0}`, `{1}` indices** — differs from R
  gt's 1-based `{1}`, `{2}`.
- **HTML and LaTeX export work in-process** (`as_raw_html`, `write_raw_html`,
  `as_latex`) — no external dependency. This differs from the R `gt` sibling, whose
  `as_raw_html()` currently fails in DAAF due to a missing libnode.
- **Image export (`save()` to PNG/PDF) does NOT work in the DAAF container** — it
  requires `selenium` + a headless Chrome driver, neither of which is installed
  (and runtime `pip install` is blocked by DAAF policy). Export tables as HTML
  instead. See `./references/export.md`.

## How to Use This Skill

### Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `quickstart.md` | GT() from a Polars DataFrame, header/source notes, basic fmt_* formatting | Starting out or need a quick table |
| `formatting-structure.md` | Full fmt_* family, tab_style/data_color styling, spanners, row-group stub, grand summary rows, cols_* operations | Detailed formatting and structure |
| `export.md` | as_raw_html/write_raw_html/as_latex, the save() image limitation, saving into project outputs | Saving or embedding tables |

### Reading Order

1. **Quick data table?** Start with `quickstart.md`
2. **Complex formatting or structure?** Read `formatting-structure.md`
3. **Saving or embedding a table?** Read `export.md`

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `gt` | R counterpart — same grammar of tables. Use `gt` when execution language is R; use great-tables when Python |
| `polars` | DAAF's default DataFrame library — great-tables accepts Polars DataFrames directly; build/aggregate the data in Polars, then format with great-tables |
| `plotnine` | Static figures (charts/plots) — use plotnine for figures, great-tables for tables |
| `plotly` | Interactive figures — use plotly for interactive charts, great-tables for tables |
| `pyfixest` | Regression output — great-tables has no modelsummary equivalent; use pyfixest `etable()` for FE/DiD model tables |
| `statsmodels` | Regression output — use statsmodels `.summary()` / `summary2()` for model tables |
| `data-scientist` | Methodology guidance for what to present in tables |

**R counterpart:** For R pipelines, use the `gt` skill instead. great-tables and gt
share the grammar of tables but differ in surface details (method chaining vs `|>`,
0-based vs 1-based `cols_merge` indices, Polars-expression vs string aggregators in
summary rows, and export capabilities — see Version Notes).

## Quick Decision Trees

### "I need to make a table"

```
What kind of table?
├─ Data summary table (descriptive stats, crosstabs)
│   ├─ Simple (few rows/columns, minimal formatting)
│   │   └─ GT() + fmt_* → ./references/quickstart.md
│   └─ Complex (conditional styling, row groups, summary rows, color scales)
│       └─ tab_style / data_color / grand_summary_rows → ./references/formatting-structure.md
├─ Frequency / cross-tabulation table
│   └─ GT() with groupname_col row-group stub → ./references/formatting-structure.md
├─ Regression / model-coefficient table
│   └─ great-tables has NO modelsummary equivalent. Use the estimator's own output:
│       pyfixest etable() (FE/DiD) or statsmodels .summary() — see those skills
└─ Table with color scales or conditional formatting
    └─ data_color() or tab_style() → ./references/formatting-structure.md
```

### "How do I save or embed it?"

```
Output target?
├─ HTML string (embed in a report, session workspace) → as_raw_html() → ./references/export.md
├─ HTML file on disk → write_raw_html() → ./references/export.md
├─ LaTeX (journal submission) → as_latex() → ./references/export.md
└─ PNG/PDF image → NOT available in the container (needs selenium/headless Chrome).
    Export HTML instead → ./references/export.md
```

## File-First Execution in Research Workflows

In DAAF research pipelines, tables are generated through **script files** in
`scripts/stage8_analysis/`, not interactively. This ensures auditability and
reproducibility.

**The pattern:**
1. Write table code to `scripts/stage8_analysis/{step}_{table-name}.py`
2. Execute via `bash {BASE_DIR}/scripts/run_with_capture.sh {script_path}`
3. Output gets appended to the script as comments
4. Use `write_raw_html()` (or `as_raw_html()` + write) to save tables into the
   project output directory as HTML

See `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the mandatory file-first
execution protocol.

## Quick Reference

### Essential Setup

```python
import polars as pl
import great_tables as gt
from great_tables import loc, style, md
```

### Basic GT Table (from a Polars DataFrame)

```python
tbl = (
    gt.GT(df, rowname_col="region", groupname_col="group")
    .tab_header(title="Revenue by Region", subtitle="FY2025")
    .tab_source_note(source_note=md("Source: *synthetic data*"))
    .fmt_currency(columns="revenue", currency="USD", decimals=2)
    .fmt_percent(columns="share", decimals=1)
    .cols_label(revenue="Revenue", share="Share")
)
html = tbl.as_raw_html()
```

### Core GT Operations

| Operation | Code |
|-----------|------|
| Create table (Polars or pandas) | `gt.GT(df)` |
| Row-group stub | `gt.GT(df, rowname_col="id", groupname_col="grp")` |
| Title/subtitle | `.tab_header(title=..., subtitle=...)` |
| Source note | `.tab_source_note(source_note=md("Source: ..."))` |
| Stubhead label | `.tab_stubhead(label="...")` |
| Format numbers | `.fmt_number(columns=..., decimals=2)` |
| Format percent | `.fmt_percent(columns=..., decimals=1)` |
| Format currency | `.fmt_currency(columns=..., currency="USD")` |
| Format date | `.fmt_date(columns=..., date_style=...)` |
| Markdown in cells | `.fmt_markdown(columns=...)` |
| Column spanner | `.tab_spanner(label="...", columns=[...])` |
| Grand summary rows | `.grand_summary_rows(fns={"Total": pl.all().sum()})` |
| Missing-value text | `.sub_missing(missing_text="--")` |
| Conditional style | `.tab_style(style=style.fill(color="..."), locations=loc.body(...))` |
| Color scale | `.data_color(columns=[...], palette=["white", "blue"])` |
| Column labels | `.cols_label(col="Label")` |
| Column align | `.cols_align(align="right", columns=[...])` |
| Hide columns | `.cols_hide(columns=[...])` |
| Merge columns | `.cols_merge(columns=["lo","hi"], pattern="{0}–{1}")` |
| Column width | `.cols_width({"col": "150px"})` |
| Export HTML string | `.as_raw_html()` |
| Write HTML file | `.write_raw_html("table.html")` |
| Export LaTeX | `.as_latex()` |

### Format Scalar Values (no table)

```python
from great_tables import vals
vals.fmt_number([1234.5, 6789.0], decimals=1)   # ['1,234.5', '6,789.0']
```

## Topic Index

| Topic | Reference File |
|-------|---------------|
| GT() from Polars/pandas | `./references/quickstart.md` |
| tab_header, tab_source_note, tab_stubhead | `./references/quickstart.md` |
| Basic fmt_number / fmt_percent / fmt_currency | `./references/quickstart.md` |
| cols_label column renaming | `./references/quickstart.md` |
| Full fmt_* family (date, markdown, integer, scientific, bytes) | `./references/formatting-structure.md` |
| Conditional styling (tab_style, loc, style) | `./references/formatting-structure.md` |
| Color scales (data_color) | `./references/formatting-structure.md` |
| Column spanners (tab_spanner) | `./references/formatting-structure.md` |
| Row-group stub (groupname_col, row_group_order) | `./references/formatting-structure.md` |
| Grand summary rows (Polars expressions) | `./references/formatting-structure.md` |
| sub_missing / sub_zero | `./references/formatting-structure.md` |
| Column operations (align, hide, move, merge, width) | `./references/formatting-structure.md` |
| Table options (opt_*, tab_options) | `./references/formatting-structure.md` |
| as_raw_html / write_raw_html | `./references/export.md` |
| as_latex | `./references/export.md` |
| save() image limitation (selenium) | `./references/export.md` |
| Saving into project outputs | `./references/export.md` |

## Citation

When great-tables is used as a primary table-formatting tool, include in the
report's Software & Tools references:

> Iannone, R., & Chow, M. (2024). great-tables: Easily generate information-rich,
> publication-quality tables from Python. Python package version 0.21.0.
> https://posit-dev.github.io/great-tables/

**Cite when:** great-tables produces tables included in the report or deliverables.
**Do not cite when:** only used for quick exploratory tables not included in
deliverables.
