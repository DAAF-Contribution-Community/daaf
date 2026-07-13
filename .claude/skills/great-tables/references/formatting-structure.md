# Great Tables: Formatting, Styling & Structure

All examples executed against great-tables 0.21.0 in the DAAF container.

## Contents

- [The fmt_* family](#the-fmt-family)
- [Substitution: missing and zero values](#substitution-missing-and-zero-values)
- [Conditional styling: tab_style, loc, style](#conditional-styling-tab_style-loc-style)
- [Color scales: data_color](#color-scales-data_color)
- [Column spanners](#column-spanners)
- [Grand summary rows](#grand-summary-rows)
- [Column operations](#column-operations)
- [Table options](#table-options)

## The fmt_* family

All `fmt_*` methods select columns by name or list of names via `columns=` and
return a new `GT`. Full set available in 0.21.0:

| Method | Purpose |
|--------|---------|
| `fmt_number(columns, decimals=, use_seps=)` | Fixed-decimal numbers with thousands separators |
| `fmt_integer(columns)` | Integers with separators |
| `fmt_percent(columns, decimals=)` | Multiply by 100, append `%` |
| `fmt_currency(columns, currency=, decimals=)` | Currency with symbol (e.g. `currency="USD"`) |
| `fmt_scientific(columns)` | Scientific notation |
| `fmt_engineering(columns)` | Engineering notation |
| `fmt_bytes(columns)` | Byte sizes (KB/MB/GB) |
| `fmt_roman(columns)` | Roman numerals |
| `fmt_date(columns, date_style=)` | Dates (see date_style names below) |
| `fmt_datetime(columns)` / `fmt_time(columns)` | Datetimes / times |
| `fmt_markdown(columns)` | Render cell contents as Markdown |
| `fmt_units(columns)` | Scientific units notation |
| `fmt_image(columns)` / `fmt_flag(columns)` / `fmt_icon(columns)` | Images, country flags, Font Awesome icons in cells |
| `fmt_nanoplot(columns)` | Inline sparkline-style plots |
| `fmt_tf(columns)` | Boolean → text/symbol |
| `fmt(fns=, columns=)` | Generic custom formatter (callable) |

```python
tbl = (
    gt.GT(df)
    .fmt_number(columns="revenue", decimals=2)
    .fmt_percent(columns="share", decimals=1)
    .fmt_markdown(columns="label")   # cells like "**bold**" render bold
)
```

## Substitution: missing and zero values

```python
tbl = (
    gt.GT(df)
    .sub_missing(missing_text="--")   # replace nulls with "--"
    .sub_zero(zero_text="—")          # replace exact zeros
)
```

`sub_missing` accepts `columns=`/`rows=` to scope the substitution; called without
them it applies table-wide. (Probe-verified: `sub_missing(missing_text="--")`
produces `--` in the rendered HTML for null cells.)

## Conditional styling: tab_style, loc, style

`tab_style(style=..., locations=...)` applies a style to targeted cells. Build the
style with the `style` module and target cells with the `loc` module.

```python
from great_tables import loc, style

tbl = (
    gt.GT(df)
    .tab_style(
        style=style.fill(color="lightyellow"),
        locations=loc.body(columns="revenue", rows=[0]),   # first data row
    )
    .tab_style(
        style=style.text(weight="bold"),
        locations=loc.column_labels(columns=["revenue", "share"]),
    )
)
```

- **Style constructors:** `style.fill(color=)`, `style.text(color=, weight=, size=, style=)`, `style.borders(sides=, color=, weight=)`.
- **Location selectors:** `loc.body(columns=, rows=)`, `loc.column_labels(columns=)`, `loc.stub(rows=)`, `loc.row_groups()`, `loc.title()`, `loc.source_notes()`.
- `rows=` accepts integer positions (0-based) or a Polars boolean expression for conditional targeting.

## Color scales: data_color

`data_color` maps cell values to a color gradient.

```python
tbl = (
    gt.GT(df)
    .data_color(columns=["y"], palette=["white", "blue"])
)
```

Full signature (0.21.0): `data_color(columns=None, rows=None, palette=None,
domain=None, na_color=None, alpha=None, reverse=False, autocolor_text=True,
truncate=False)`. `autocolor_text=True` flips text to light/dark for contrast;
`domain=` fixes the value range for consistent scales across tables.

## Column spanners

`tab_spanner(label=, columns=)` groups columns under a shared header label.

```python
tbl = (
    gt.GT(df)
    .tab_spanner(label="Financials", columns=["revenue", "share"])
)
```

`tab_spanner_delim(delim=)` auto-creates spanners by splitting column names on a
delimiter (e.g. `"2024_revenue"` → spanner `2024`).

## Grand summary rows

`grand_summary_rows(fns=...)` appends aggregate rows. **In 0.21.0 the `fns` values
must be Polars expressions** (for Polars-backed tables), not R-style string
aggregator names, and the `columns=` selection argument is **not supported**
(raises `NotImplementedError`) — the summary spans all numeric columns.

```python
tbl = (
    gt.GT(df)
    .grand_summary_rows(
        fns={"Total": pl.all().sum(), "Mean": pl.all().mean()},
    )
)
```

Common pitfalls (both probe-verified as errors):
- `fns={"Total": "sum"}` → `ColumnNotFoundError` (string treated as a column name).
- `grand_summary_rows(fns=..., columns=["x"])` → `NotImplementedError`.

Use `side="top"` to place summaries above the body (default `"bottom"`), and
`fmt=` for a formatting function applied to summary cells.

## Column operations

| Method | Purpose | Note |
|--------|---------|------|
| `cols_label(**kwargs)` | Rename displayed column labels | `cols_label(rev="Revenue")` |
| `cols_align(align=, columns=)` | Set alignment (`"left"`/`"center"`/`"right"`) | |
| `cols_hide(columns=)` / `cols_unhide(columns=)` | Hide / restore columns | Data retained for calculations |
| `cols_move(columns=, after=)` | Reorder columns | Also `cols_move_to_start`/`cols_move_to_end` |
| `cols_width(cases=)` | Set widths | Dict form: `cols_width({"col": "150px"})` |
| `cols_merge(columns=, pattern=)` | Merge cells into one column | **Pattern uses 0-based indices** |
| `cols_label_with(fn=)` | Transform labels via a callable | |

**`cols_merge` index base differs from R gt.** Python great-tables uses 0-based
`{0}`, `{1}` placeholders; R gt uses 1-based `{1}`, `{2}`.

```python
# Python great-tables (0-based):
tbl = gt.GT(df).cols_merge(columns=["lo", "hi"], pattern="{0}–{1}")
# Using {1}–{2} here raises: ValueError, "Pattern references column {2} but only 2
# columns were provided".
```

## Table options

- `tab_options(...)` — fine-grained table styling (font sizes, padding, borders, background).
- `opt_*` convenience methods: `opt_row_striping()`, `opt_all_caps()`,
  `opt_stylize()` (preset themes), `opt_table_font(font=)`,
  `opt_table_outline()`, `opt_horizontal_padding()` / `opt_vertical_padding()`,
  `opt_align_table_header(align=)`.

```python
tbl = (
    gt.GT(df)
    .opt_row_striping()
    .opt_stylize(style=1, color="blue")
)
```

## Scalar value formatting (no table)

The `vals` module formats plain lists/values with the same formatters, useful for
inline report text:

```python
from great_tables import vals
vals.fmt_number([1234.5, 6789.0], decimals=1)   # ['1,234.5', '6,789.0']
vals.fmt_percent([0.123, 0.456])
vals.fmt_currency([1000.0], currency="USD")
```
