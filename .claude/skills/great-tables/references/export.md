# Great Tables: Export

All export behaviors below were executed against great-tables 0.21.0 in the DAAF
container. The key takeaway: **HTML and LaTeX export work in-process; PNG/image
export does not work in the container.**

## Export capability summary (probe-verified 0.21.0)

| Method | Works in container? | Output | Notes |
|--------|---------------------|--------|-------|
| `as_raw_html()` | Yes | HTML string | Returns the table as an HTML string (~8 KB for a small table) |
| `write_raw_html(filename)` | Yes | HTML file | Writes directly to disk; same bytes as `as_raw_html()` |
| `as_latex(use_longtable=, tbl_pos=)` | Yes | LaTeX string | Produces `tabular` / `longtable` markup |
| `save(file)` | **No** | PNG/PDF image | Requires `selenium` + headless Chrome — not installed; runtime install blocked by DAAF policy |
| `show()` | (interactive only) | display | For notebook/REPL display; not used in file-first pipelines |

## HTML export (the default path)

`as_raw_html()` returns the fully self-contained HTML for the table (inline CSS by
default is off; see `inline_css=`). This is the primary DAAF export path — it works
in-process with no external dependency.

```python
html_str = tbl.as_raw_html()
# len(html_str) ~ 8000 for a small table; contains the title, formatted values, CSS
```

Write directly to a file with `write_raw_html`:

```python
tbl.write_raw_html("/path/to/project/output/2025-01-24_summary_table.html")
```

`write_raw_html(filename, encoding="utf-8", inline_css=False, newline=None,
make_page=False, all_important=False)`:
- `inline_css=True` — inline all CSS onto elements (useful for email / environments
  that strip `<style>` blocks).
- `make_page=True` — wrap the table in a full standalone HTML page (`<html>`…`</html>`).

## LaTeX export

```python
latex_str = tbl.as_latex()                       # tabular environment
latex_str = tbl.as_latex(use_longtable=True)     # longtable (multi-page)
```

`as_latex(use_longtable=False, tbl_pos=None)`. Probe: output contains `tabular`
(or `longtable` when requested). Use for direct inclusion in a `.tex` journal
submission.

## Image export (save) — NOT available in the container

`save()` renders the table to a raster/vector image (PNG, PDF, etc.) by driving a
headless browser. In the DAAF container this **fails**:

```python
tbl.save("table.png")
# ImportError: Module selenium not found. Run the following to install.
# `pip install selenium`
```

`save(file, selector="table", scale=1.0, expand=5, web_driver="chrome",
window_size=(6000,6000), ...)` needs both the `selenium` package and a headless
Chrome/Chromium driver. Neither is installed, and **runtime `pip install` is blocked
by DAAF policy** (add packages to the Dockerfile and rebuild instead). This mirrors
the R `gt` skill's own "gt table export is HTML-first" limitation (documented in
`user_reference/07_faq_technical.md`).

**Recommended pattern:** export tables as HTML (`write_raw_html`). HTML is the
audit-friendly, dependency-free format and renders in browsers, the DAAF session
log viewer, and Marimo notebooks. If a raster image is genuinely required for a
deliverable, flag it for the human researcher — an image can be produced outside the
container from the HTML, or `selenium` + a Chrome driver can be added to the
Dockerfile and the image rebuilt.

## Saving into project outputs (file-first workflow)

In a Stage 8 analysis script, build the table and write it into the project's
output directory as HTML:

```python
# --- Save ---
# INTENT: persist the formatted summary table as an audit-trail HTML artifact
# REASONING: HTML export works in-process; PNG export needs selenium (unavailable)
out_path = f"{PROJECT_DIR}/output/2025-01-24_regional_summary.html"
tbl.write_raw_html(out_path)
print(f"Saved table to {out_path}")
```

Follow the standard file-first execution and naming conventions in
`agent_reference/SCRIPT_EXECUTION_REFERENCE.md` and CLAUDE.md (§ File Naming
Conventions — figures/artifacts use the `YYYY-MM-DD[suffix]_[description]` pattern).
