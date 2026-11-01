# Gotchas & Common Pitfalls

## Chunk Option Syntax

### The #1 Mistake: Wrong Chunk Option Syntax

Quarto uses `#|` (hash-pipe) syntax. The legacy R Markdown `{r, ...}` header
syntax still works but should not be used in Quarto documents.

````markdown
# WRONG -- legacy R Markdown syntax
```{r, echo=FALSE, fig.width=8}
plot(x, y)
```

# CORRECT -- Quarto hash-pipe syntax
```{r}
#| echo: false
#| fig-width: 8

plot(x, y)
```
````

Key differences:

| Legacy (R Markdown) | Quarto (#|) | Notes |
|---------------------|-------------|-------|
| `echo=FALSE` | `echo: false` | YAML boolean, not R boolean |
| `fig.width=8` | `fig-width: 8` | Hyphens, not dots |
| `fig.cap="text"` | `fig-cap: "text"` | Hyphens, not dots |
| `message=FALSE` | `message: false` | Lowercase `false`, not `FALSE` |
| `results='asis'` | `output: asis` | Different key name |
| `cache=TRUE` | `cache: true` | Lowercase `true`, not `TRUE` |

### Dots vs Hyphens

All chunk options use **hyphens** in Quarto, not dots:

| Wrong | Correct |
|-------|---------|
| `fig.width` | `fig-width` |
| `fig.height` | `fig-height` |
| `fig.cap` | `fig-cap` |
| `fig.align` | `fig-align` |
| `tbl.cap` | `tbl-cap` |
| `out.width` | `out-width` |

### Boolean Values

Use YAML booleans (`true`/`false`), not R booleans (`TRUE`/`FALSE`):

```yaml
#| echo: false      # Correct
#| echo: FALSE      # Wrong (treated as string "FALSE")
#| eval: true       # Correct
#| eval: TRUE       # Wrong
```

### Spacing After #|

A space after `#|` is required:

```yaml
#| echo: false      # Correct
#|echo: false       # Wrong -- no space after pipe
```

## YAML Frontmatter Errors

### Indentation

YAML is indentation-sensitive. Use spaces (not tabs), consistently:

```yaml
# CORRECT
format:
  html:
    toc: true
    theme: cosmo

# WRONG -- inconsistent indentation
format:
  html:
    toc: true
   theme: cosmo     # Only 3 spaces instead of 4

# WRONG -- tabs instead of spaces
format:
	html:             # Tab character
		toc: true       # Tab character
```

### Colons in Values

Values containing colons need quoting:

```yaml
# WRONG
title: Analysis: A Study

# CORRECT
title: "Analysis: A Study"
```

### Multi-line Strings

```yaml
# Folded (newlines become spaces)
description: >
  This is a long description
  that wraps across lines.

# Literal (newlines preserved)
abstract: |
  Line one.
  Line two.
  Line three.
```

### Missing Document Separator

The YAML block MUST start and end with `---`:

```yaml
---
title: "My Doc"
format: html
---
```

If the closing `---` is missing, the entire document is treated as YAML.

## Figure Path Issues

### Relative vs Absolute Paths

R code in .qmd executes in the directory containing the .qmd file. Paths
must be relative to that location:

```r
# If .qmd is in project root:
df <- arrow::read_parquet("data/raw/schools.parquet")  # Correct

# If .qmd is in a subdirectory:
df <- arrow::read_parquet("../data/raw/schools.parquet")  # Relative to .qmd
```

### The _files Directory

Rendered figures go to `document_files/figure-html/`:

```
analysis.qmd
analysis.html
analysis_files/
  figure-html/
    fig-scatter-1.png
```

This directory is auto-managed by Quarto. Do not manually add files to it.

With `embed-resources: true`, no `_files` directory is created.

### ggsave and Chunk Figures

If you use `ggsave()` AND display the plot, you get two copies:

```r
# Creates BOTH a saved file AND a chunk figure
p <- ggplot(df, aes(x, y)) + geom_point()
ggsave("output/plot.png", p)
p  # This also creates a figure in _files/
```

In DAAF Stage 9 notebooks, archive chunks do not execute because both global
and per-chunk `eval: false` guard them. If an existing Stage 8 figure is
included, use standard Markdown image syntax or a dedicated
`knitr::include_graphics()` display chunk; do not run this plotting pattern in
Stage 9. Optional data-preview and dedicated figure-display chunks explicitly
using `#| eval: true` do execute, but contain no plotting code.

## knitr Cache Pitfalls

### When Cache Breaks

The knitr cache invalidates when the chunk code changes. But it does NOT
detect:

| Change | Cache Detects? | Risk |
|--------|---------------|------|
| Code in the chunk | Yes | None |
| External data file changes | No | Stale results |
| Changes in sourced files | No | Stale results |
| Package updates | No | Stale results |
| Changes in other chunks | Partially | May miss indirect deps |

### Fixing Stale Cache

```bash
# Delete cache directory
rm -r document_cache/

# Or force refresh on render
quarto render doc.qmd --cache-refresh
```

### Safe Cache Usage

```yaml
#| cache: true
#| dependson: "load-data"  # Invalidate when load-data chunk changes
```

Use `dependson` to explicitly declare inter-chunk dependencies.

For DAAF Stage 9 notebooks, caching is irrelevant for archive chunks because
they remain at `eval: false`. Optional canonical data-preview or existing-figure
display chunks may execute, but are intentionally small and should not use the
cache as a substitute for validating their current file references.

## PDF Rendering Issues

### LaTeX in the DAAF Image

The image includes LaTeX: a pinned TinyTeX bundle (TeX Live 2026) at
`/opt/TinyTeX`, with `lualatex`, `xelatex`, `pdflatex` and `tlmgr` on the PATH
through links in `/usr/local/bin`. `quarto check` (Quarto 1.10.18) reports:

```
[✓] Checking LaTeX....................OK
      Using: Installation From Path
      Path: /usr/local/bin
      Version: 2026
```

Its tools section lists "TinyTeX: (external install)", which only means Quarto
did not install it; that is expected.

The tree is owned by root and read-only for the user DAAF runs as, so nothing
can be added to it at runtime. `tlmgr install` fails:

```
You don't have permission to change the installation in any way,
specifically, the directory /opt/TinyTeX/tlpkg/ is not writable.
```

Do not try the other routes either: `quarto install tinytex`,
`tinytex::install_tinytex()` and `tlmgr --usermode` are runtime installs,
which DAAF policy forbids (CLAUDE.md § Runtime Package Installation) because
the next rebuild silently reverts them. `quarto install tinytex` also puts an
unpinned TeX Live in `~/.TinyTeX`, which Quarto then prefers over the image's
tree.

### Missing LaTeX Packages

The image carries the TinyTeX bundle plus the packages Quarto's LaTeX template
loads for common features (`lang:`, strikeout, `.mark` highlight, natbib margin
citations). Check for a package with `kpsewhich <package>.sty`: it prints the
file's path, or nothing when the package is absent.

Set `latex-auto-install: false` in every LaTeX document, or once in a Quarto
project's `_quarto.yml`, which applies it to every document in the project
(`quarto inspect` on a project document shows it resolved to `false`). There
is no install-wide switch: Quarto 1.10.18 reads no environment variable or
user-level setting for it and defaults to `true`. With `true`, Quarto tries
`tlmgr update` and `tlmgr install` after a failed LaTeX run; on the read-only
tree those cannot succeed, and an open upstream issue
(quarto-dev/quarto-cli#14413) reports the resulting error as giving no
context. With the setting, a missing package stops the render with the cause
(here a document loading `tikz-cd`, which the image lacks; "automatic
installed disabled" is Quarto's wording):

```
ERROR:
compilation failed- missing packages (automatic installed disabled)
LaTeX Error: File `tikz-cd.sty' not found.
```

Fix: a Dockerfile change. The error names a `.sty` file, and the TeX Live
package that holds it can have a different name (`tikz.sty` is in the package
`pgf`), so look the file up on CTAN (ctan.org) to find the TeX Live package
name before proposing the change. Never edit the Dockerfile on your own
initiative: tell the user the document needs that package. Adding it means
putting the name in the TinyTeX package list (`TT_PKGS`) in the Dockerfile's
TinyTeX block and rebuilding (`bash rebuild_daaf.sh`, or `.\rebuild_daaf.ps1`
on Windows, from the `daaf-docker` folder). The user decides, may ask you to
make the edit, and runs the rebuild; `user_reference/04_extending_daaf.md`
§ LaTeX Packages gives the user these steps. If the document needs nothing
LaTeX-specific, `format: typst` renders it without the package.

### First LaTeX Render Builds the Font Database

The first LaTeX render in a newly created container (after a rebuild or an
update) prints:

```
luaotfload | db : Font names database not found, generating new one.
luaotfload | db : This can take several minutes; please be patient.
```

`lualatex` is building its font-name cache in `$TEXMFVAR`
(`/home/appuser/.cache/texmf-var/`). That folder is in the container, not on
one of DAAF's volumes, so each new container builds the cache again. It is not
a hang: in the DAAF image it adds about a second to that first render, and
later renders in the same container reuse the cache. Typst renders have no
such step.

### PDF Standard Not Validated

`pdf-standard` is applied: a `lualatex` render with `pdf-standard: ua-2` is a
tagged PDF 2.0. Quarto then prints:

```
WARN: PDF standard validation requested but verapdf is not installed.
Install with: quarto install verapdf
```

The PDF is produced; only Quarto's post-render check against the standard is
skipped. Do not follow the hint: `quarto install verapdf` is a runtime install,
and adding veraPDF, with whatever it needs to run, is a Dockerfile change for
the user to decide on. When a
deliverable claims PDF/A or PDF/UA conformance, say that the standard was
requested but not validated in the container.

### kableExtra Tables in LaTeX PDF

kableExtra renders in a LaTeX PDF. With `caption =` in `kbl()` and no `tbl-`
label it prints "Raw LaTeX table found with non-tbl label" and cannot be
cross-referenced; with a label and `caption =` the numbering goes wrong; with
neither, it renders with no warning, no caption and no cross-reference. Put the
label and `tbl-cap` on the chunk instead. A hard-coded `kbl(format = "html")` stops the
render ("Functions that produce HTML output found in document targeting pdf
output"), so leave `format =` out. See `./tables.md` § kableExtra in LaTeX PDF.

### Unicode Characters in LaTeX PDF

Accented Latin text (café, naïve) renders with the default engine (`lualatex`)
and font (Latin Modern). Characters Latin Modern lacks do not: Greek,
Cyrillic and CJK come out blank in the PDF and are missing from its text
layer (`pdftotext` shows `�`), while the render exits 0 and Quarto prints no
warning. The only trace is in the LaTeX log, which Quarto deletes unless the
format sets `latex-clean: false`:

```
Missing character: There is no α (U+03B1) in font [lmroman10-regular]:+tlig;!
```

The cause is the font, so the fix is a font that covers the script.
`fc-list :lang=<code> family` lists the system fonts (under
`/usr/share/fonts`) that cover a language; it does not list the fonts inside
the TinyTeX tree (`/opt/TinyTeX/texmf-dist/fonts/`), which `lualatex` can also
use. Of the system fonts, DejaVu Serif and DejaVu Sans cover Greek and
Cyrillic:

```yaml
format:
  pdf:
    mainfont: DejaVu Serif
```

The image has no CJK font (`fc-list :lang=zh` prints nothing), so CJK text
stays missing in either PDF path until a font is added in the Dockerfile and
the image rebuilt. Check the rendered PDF whenever the text goes beyond Latin
script.

### Missing Glyphs in Typst PDF

Typst reads Unicode text without extra configuration, and its default font
(Libertinus Serif) covers Greek and Cyrillic. A character no available font
covers renders as a missing-glyph box and may be lost from the PDF's text
layer, with no warning (CJK text, for example: the DAAF image ships no CJK
fonts). Check the rendered PDF when the text goes beyond Latin script.

### Long Tables Overflowing

Applies only when rendering through LaTeX (`latex_options` is a LaTeX
setting). Tables wider than the page in PDF:

```r
knitr::kable(df) |>
  kableExtra::kable_styling(latex_options = "scale_down")
```

## Cross-Reference Issues

### Cross-References Not Rendering

Common causes:

1. **Label missing `fig-` or `tbl-` prefix:**
```yaml
#| label: scatter          # Won't cross-reference
#| label: fig-scatter      # Will cross-reference
```

2. **Caption missing:**
```yaml
#| label: fig-scatter
# No fig-cap -- cross-reference won't work
```

3. **Wrong reference syntax:**
```markdown
See Figure @fig-scatter    # Wrong -- "Figure" is redundant
See @fig-scatter           # Correct -- Quarto adds "Figure"
```

Quarto automatically adds "Figure" or "Table" prefix to cross-references.
Writing `Figure @fig-scatter` produces "Figure Figure 1".

### Duplicate Labels

Each label must be unique within a document:

````markdown
```{r}
#| label: fig-plot
# First occurrence -- OK
```

```{r}
#| label: fig-plot
# ERROR -- duplicate label
```
````

## Inline R Expression Issues

### Expression Too Complex

Inline expressions must be single expressions:

```markdown
The count is `r nrow(df)`.                    # OK
The count is `r x <- nrow(df); x`.            # WRONG -- multiple expressions
The count is `r format(nrow(df), big.mark=",")`  # OK -- single nested call
```

### Missing Backtick

Inline code needs proper backtick delimiters:

```markdown
The count is `r nrow(df)`.    # Correct
The count is `r nrow(df).     # Wrong -- missing closing backtick
```

### NULL Output

If the expression returns NULL, nothing is printed:

```markdown
The result is `r invisible(42)`.  # Prints nothing!
The result is `r 42`.             # Prints "42"
```

## Common Quarto vs R Markdown Differences

If you have R Markdown experience, watch for these:

| R Markdown | Quarto | Notes |
|-----------|--------|-------|
| `output: html_document` | `format: html` | Different key names |
| `rmarkdown::render()` | `quarto render` CLI | Different rendering path |
| `setup` chunk with `knitr::opts_chunk$set()` | `execute:` in YAML | Global options location |
| `{r chunk-name, ...}` | `{r}` + `#| label: name` | Option location |
| `.Rmd` extension | `.qmd` extension | File format |
| `fig.width` | `fig-width` | Dots to hyphens |
| `results = 'asis'` | `output: asis` | Different option name |

## Markdown Syntax Changes (Quarto 1.9+)

Quarto 1.9 updated Pandoc to 3.8.3 (1.10.18, the installed version, bundles
Pandoc 3.10), and its changelog lists two changes that can surprise documents
written for older versions, one in prose and one in YAML:

- **Superscripts that open with a span may parse as inline footnotes** (Quarto
  1.9 changelog, #13925): Pandoc 3.8.3 introduces `^[text]^` as inline-footnote
  syntax, which can conflict with a superscript whose content starts with a
  span, such as `^[text]{.class}^`. DAAF's probe on 1.10.18 did **not** reproduce this for the
  one form it tried: `SUPA^[text]{.cls}^SUPB` rendered as
  `SUPA<sup><span class="cls">text</span></sup>SUPB`, with no footnote (HTML
  output only, observed 2026-10-05). Other forms and other output
  formats were not probed, so check the rendered output when prose uses a
  superscript that starts with `[`. The changelog's workaround is a zero-width
  space between `^` and `[`. Stage 9 archive chunks are fenced code and are not
  affected; this matters only in prose.
- **`highlight-style` is deprecated in favor of `syntax-highlighting`.** The old
  key still works (a 1.10.18 render that used it printed no deprecation
  warning, observed 2026-10-05); prefer the new one in new documents.

## Rendering Fails Silently

If `quarto render` exits without error but output looks wrong:

1. **Check `--log`:** `quarto render doc.qmd --log render.log`
2. **Check warnings:** Render with `warning: true` on all chunks
3. **Check eval:** Verify `eval` is set correctly (true for execution, false for display)
4. **Check format:** Ensure YAML format matches `--to` flag

## Environment Issues

### Library Not Found

```
Error in library(ggplot2) : there is no package called 'ggplot2'
```

Quarto uses the R installation found by `quarto check knitr`. Ensure
packages are installed in the correct library path:

```bash
quarto check knitr
# Shows: LibPaths and installed packages
```

### Wrong R Version

```bash
quarto check knitr
# Shows: Version and Path
```

If Quarto uses the wrong R, set `QUARTO_R` environment variable:

```bash
export QUARTO_R=/opt/R/4.5.3/bin/R
quarto render doc.qmd
```

## Summary Checklist

| Issue | Fix |
|-------|-----|
| Chunk options not working | Use `#|` syntax with hyphens, not dots |
| YAML parse error | Check indentation (spaces, not tabs) |
| Cross-ref not linking | Add `fig-`/`tbl-` prefix AND caption |
| LaTeX PDF won't render | Read the LaTeX error; a missing `.sty` is a Dockerfile change + rebuild that the user decides on (never on your own initiative), never `tlmgr install` or `quarto install tinytex`; keep `latex-auto-install: false`; `format: typst` if nothing LaTeX-specific is needed |
| Non-Latin text blank in LaTeX PDF | Set `mainfont` to a font covering the script (DejaVu Serif for Greek, Cyrillic) |
| Cache stale | Delete `_cache/` or `--cache-refresh` |
| Wrong R version | Check `quarto check knitr` |
| Figures missing | Check paths relative to .qmd location |
| "Figure Figure 1" | Remove manual prefix -- `@fig-x` adds it |
