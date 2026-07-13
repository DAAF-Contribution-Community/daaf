# Great Tables Quickstart

All examples below were executed against great-tables 0.21.0 in the DAAF container.

## Imports

```python
import polars as pl
import great_tables as gt
from great_tables import loc, style, md, html, px, pct, vals
```

- `gt.GT` — the table object (constructor).
- `loc` — location selectors (`loc.body`, `loc.column_labels`, `loc.stub`, etc.) for targeting styles.
- `style` — style constructors (`style.fill`, `style.text`, `style.borders`).
- `md`, `html` — mark a string as Markdown / raw HTML (for titles, source notes, cells via `fmt_markdown`).
- `px`, `pct` — CSS length helpers (e.g. `px(150)`).
- `vals` — format scalar value lists without building a table.

## Building a table from a Polars DataFrame

great-tables accepts a Polars DataFrame directly (pandas also works; Polars is the
DAAF default). Every method returns a new `GT`, so operations method-chain with `.`.

```python
df = pl.DataFrame({
    "region": ["A", "B", "C"],
    "revenue": [12345.6, 23456.7, 34567.8],
    "share": [0.123, 0.234, 0.345],
})

tbl = (
    gt.GT(df)
    .tab_header(title="Revenue by Region", subtitle="FY2025")
    .fmt_currency(columns="revenue", currency="USD", decimals=2)
    .fmt_percent(columns="share", decimals=1)
    .cols_label(revenue="Revenue", share="Share")
)

html_str = tbl.as_raw_html()   # 'Revenue by Region', '$12,345.60', '12.3%' all present
```

> **Constructor caveat:** use `gt.GT(df)`. Do **not** use `gt.GT.from_data(df)` — it
> is broken in 0.21.0 (raises `TypeError` on an internal `_tbl_data` argument).

## Row-group stub

Pass `rowname_col` and `groupname_col` to the constructor to create a stub (the
labeled left-hand column) with row groups. This mirrors R gt's row-group behavior.

```python
df = pl.DataFrame({
    "group": ["North", "North", "South", "South"],
    "region": ["A", "B", "C", "D"],
    "revenue": [12345.6, 23456.7, 34567.8, 45678.9],
})

tbl = (
    gt.GT(df, rowname_col="region", groupname_col="group")
    .tab_stubhead(label="Region")
    .fmt_currency(columns="revenue", currency="USD")
)
```

## Header, source notes, footnotes

```python
tbl = (
    gt.GT(df)
    .tab_header(title="Table Title", subtitle="Optional subtitle")
    .tab_source_note(source_note=md("Source: *synthetic test data*, 2025."))
)
```

- `tab_header(title=..., subtitle=...)` — title/subtitle block above the table.
- `tab_source_note(source_note=...)` — a note below the table. Wrap in `md(...)` for
  Markdown or `html(...)` for raw HTML; a plain string renders as literal text.
- Footnotes attach to locations via `tab_style`/footnote APIs — see
  `formatting-structure.md`.

## Basic number formatting

The `fmt_*` family targets columns by name (string) or list of names. Applied
left-to-right in the chain; later formatters on the same column win.

```python
tbl = (
    gt.GT(df)
    .fmt_number(columns=["revenue"], decimals=2)          # 12,345.60
    .fmt_percent(columns="share", decimals=1)             # 12.3%
    .fmt_currency(columns="revenue", currency="USD")      # $12,345.60
    .fmt_integer(columns="count")                         # 1,234
)
```

Common `fmt_*` methods (full list in `formatting-structure.md`):
`fmt_number`, `fmt_integer`, `fmt_percent`, `fmt_currency`, `fmt_date`,
`fmt_datetime`, `fmt_time`, `fmt_scientific`, `fmt_engineering`, `fmt_bytes`,
`fmt_roman`, `fmt_markdown`, `fmt_units`, `fmt_image`, `fmt_flag`, `fmt_icon`.

## Renaming and aligning columns

```python
tbl = (
    gt.GT(df)
    .cols_label(revenue="Revenue", share="Market Share")
    .cols_align(align="right", columns=["revenue", "share"])
)
```

## Next steps

- Detailed formatting, styling, spanners, summary rows, column ops →
  `./formatting-structure.md`
- Exporting to HTML/LaTeX and the image-export limitation → `./export.md`
