# Output Format Configuration

## Format Selection

The `format` key in YAML frontmatter controls output. Quarto supports many formats;
these four are relevant for DAAF:

| Format | Use Case | Requirements |
|--------|----------|--------------|
| `html` | Default, interactive, self-contained | None |
| `pdf` | PDF through LaTeX, the default PDF path: journal or LaTeX templates, kableExtra, LaTeX-only options | None (the image ships TinyTeX); set `latex-auto-install: false` |
| `typst` | Quick, simple PDF, or when the user asks for Typst | None (Typst is bundled with Quarto) |
| `docx` | Collaboration, Word users | None |

## HTML Format

### Basic HTML

```yaml
---
title: "Analysis Report"
format: html
---
```

### HTML with Options

```yaml
---
title: "Analysis Report"
format:
  html:
    toc: true
    toc-depth: 3
    toc-location: left
    number-sections: true
    code-fold: true
    code-summary: "Show code"
    theme: cosmo
    self-contained: true
---
```

### HTML Options Reference

| Option | Default | Values | Purpose |
|--------|---------|--------|---------|
| `toc` | `false` | `true`/`false` | Table of contents |
| `toc-depth` | `3` | 1-6 | Heading levels in TOC |
| `toc-location` | `right` | `left`, `right`, `body` | TOC placement |
| `number-sections` | `false` | `true`/`false` | Number headings |
| `code-fold` | `false` | `true`, `false`, `show` | Foldable code blocks |
| `code-tools` | `false` | `true`/`false` | Code copy/view-source buttons |
| `theme` | `default` | See themes below | Visual theme |
| `self-contained` | `false` | `true`/`false` | Single .html file (no external deps) |
| `embed-resources` | `false` | `true`/`false` | Embed images/CSS (preferred over self-contained) |
| `smooth-scroll` | `false` | `true`/`false` | Smooth scrolling |
| `anchor-sections` | `true` | `true`/`false` | Linkable section headers |
| `fig-responsive` | `true` | `true`/`false` | Responsive figure sizing |

### Available Themes

Built-in Bootswatch themes:

| Theme | Description |
|-------|-------------|
| `default` | Clean, minimal |
| `cosmo` | Contemporary, professional |
| `flatly` | Flat design |
| `journal` | Academic feel |
| `lumen` | Light, readable |
| `simplex` | Clean, minimalist |
| `darkly` | Dark mode |
| `cyborg` | Dark, technical |

```yaml
format:
  html:
    theme: cosmo
```

### Dark Mode Toggle

```yaml
format:
  html:
    theme:
      light: cosmo
      dark: darkly
```

### Self-Contained Output

For sharing a single HTML file with all assets embedded:

```yaml
format:
  html:
    embed-resources: true
```

`embed-resources: true` is the modern replacement for `self-contained: true`.
Both work, but `embed-resources` is preferred in Quarto 1.7+.

## PDF Format

The DAAF image renders PDF two ways: through LaTeX (`format: pdf`) and through
Typst (`format: typst`). Both work out of the box.

### Choosing a PDF Path

| Choose | When |
|--------|------|
| LaTeX (`format: pdf`) | **The default PDF path in DAAF.** Use it unless the user asks for Typst or the case below applies. Required for a journal or LaTeX template or document class, kableExtra tables, LaTeX-only options such as `fig-pos` or natbib/biblatex citations (`cite-method`), and raw LaTeX in the source |
| Typst (`format: typst`) | The user asks for it, or a quick, simple PDF (a draft or a one-off) where none of the LaTeX needs apply. Typst compiles quickly, needs no font-database step on first use, and its default font covers Greek and Cyrillic, which LaTeX's default font does not unless `mainfont` is set (`./gotchas.md` § Unicode Characters in LaTeX PDF) |

DAAF's researchers usually expect LaTeX output (journal conventions, LaTeX
typography and templates), so a PDF deliverable defaults to `format: pdf`.

### Basic PDF (LaTeX)

```yaml
---
title: "Analysis Report"
format: pdf
latex-auto-install: false
---
```

LaTeX comes from a pinned TinyTeX bundle (TeX Live 2026) installed in the image
at `/opt/TinyTeX`, with `lualatex`, `xelatex`, `pdflatex` and `tlmgr` on the
PATH. The default `pdf-engine` is `lualatex` (Quarto 1.8 and later; earlier
Quarto versions defaulted to `xelatex`); `pdf-engine: xelatex` also renders in
the image, and `--to latex` writes the `.tex` source without compiling it.

Set `latex-auto-install: false` in every LaTeX document, or once in a Quarto
project's `_quarto.yml` (there is no install-wide switch). The TinyTeX tree is
root-owned and read-only for the user DAAF runs as, so no
package can be added at runtime; with the setting, a missing package stops the
render with a clear error naming the `.sty` file instead of Quarto trying a
`tlmgr` install. Adding a package is a Dockerfile change and a rebuild, never
`tlmgr install`, `quarto install tinytex` or `tinytex::install_tinytex()`
(`./gotchas.md` § Missing LaTeX Packages).

### PDF with Options

```yaml
---
title: "Analysis Report"
format:
  pdf:
    toc: true
    number-sections: true
    colorlinks: true
    documentclass: article
    papersize: letter
    geometry:
      - margin=1in
    fontsize: 11pt
latex-auto-install: false
---
```

### PDF Options Reference

| Option | Default | Values | Purpose |
|--------|---------|--------|---------|
| `documentclass` | `scrartcl` (KOMA-Script) | `scrartcl`, `article`, `report`, `book` | LaTeX class |
| `papersize` | `letter` | `letter`, `a4` | Paper size |
| `geometry` | (default) | LaTeX geometry strings | Margins, layout |
| `fontsize` | `11pt` | `10pt`, `11pt`, `12pt` | Base font size |
| `colorlinks` | `true` (not for `book`/`scrbook`) | `true`/`false` | Colored hyperlinks |
| `lof` | `false` | `true`/`false` | List of figures |
| `lot` | `false` | `true`/`false` | List of tables |
| `mainfont` | Latin Modern | font name | Main text font; set it for text beyond Latin script (`./gotchas.md` § Unicode Characters in LaTeX PDF) |
| `monofont` | (system) | font name | Code font |
| `pdf-standard` | (none) | e.g. `ua-2` | PDF/A or PDF/UA conformance. Applied (a `ua-2` render is a tagged PDF 2.0), but not validated in the image, which has no veraPDF (`./gotchas.md` § PDF Standard Not Validated) |
| `latex-auto-install` | `true` | `true`/`false` | Set `false`: the image cannot install packages at runtime |

### PDF via Typst

Typst is a modern alternative to LaTeX with faster compilation:

```yaml
---
format:
  typst:
    toc: true
    margin:
      x: 1in
      y: 1in
---
```

Typst is bundled with Quarto -- no additional installation needed.

## Word Format

### Basic Word

```yaml
---
title: "Analysis Report"
format: docx
---
```

### Word with Options

```yaml
---
title: "Analysis Report"
format:
  docx:
    toc: true
    number-sections: true
    reference-doc: template.docx
---
```

### Custom Word Template

Create a styled reference document:

1. Render a basic .docx: `quarto render doc.qmd --to docx`
2. Open the .docx and modify styles (headings, body text, etc.)
3. Save as `template.docx`
4. Reference it:

```yaml
format:
  docx:
    reference-doc: template.docx
```

## Multiple Formats

### Render All Formats

```yaml
---
format:
  html:
    toc: true
  typst:
    toc: true
  docx: default
---
```

```bash
# Renders all formats
quarto render doc.qmd

# Render specific format
quarto render doc.qmd --to typst
```

### Format-Specific Content

Use conditional content blocks:

```markdown
::: {.content-visible when-format="html"}
This only appears in HTML output.
:::

::: {.content-visible when-format="typst"}
This only appears in Typst (PDF) output.
:::
```

`when-format="pdf"` matches LaTeX output only (a LaTeX PDF or `.tex`), so
content gated on it does not appear in a Typst PDF. Gate PDF-only content on
the format you render: `pdf` for a LaTeX PDF, `typst` for a Typst PDF.

## Common YAML Patterns

### DAAF Stage 9 Notebook

```yaml
---
title: "Research Notebook: [Project Title]"
author: "[Researcher]"
date: today
format:
  html:
    toc: true
    toc-depth: 2
    code-fold: show
    embed-resources: true
    theme: cosmo
execute:
  echo: true
  eval: false
---
```

Key choices:
- `echo: true` -- code is the audit trail, must be visible
- `eval: false` -- scripts already executed; showing code, not re-running
  (script-archive chunks additionally carry a per-chunk `#| eval: false`;
  see `daaf-notebook.md` for the belt-and-suspenders contract)
- `embed-resources: true` -- single file for archiving
- `code-fold: show` -- code visible by default, collapsible for review

### Analysis Report

```yaml
---
title: "Analysis Report"
author: "Research Team"
date: today
format:
  html:
    toc: true
    code-fold: true
    theme: cosmo
execute:
  echo: true
  warning: false
  message: false
---
```

### Minimal Quick Document

```yaml
---
title: "Quick Analysis"
format: html
---
```

## Frontmatter Beyond Format

### Bibliography

```yaml
---
bibliography: references.bib
csl: apa.csl
---
```

Reference in text with `@key` syntax, bibliography auto-generated at end.

### Cross-Reference Options

```yaml
---
crossref:
  fig-prefix: "Figure"
  tbl-prefix: "Table"
  fig-title: "Figure"
  tbl-title: "Table"
---
```

### Execution Options

```yaml
---
execute:
  echo: false
  warning: false
  message: false
  freeze: auto
---
```

`freeze: auto` -- only re-render chunks when source changes (useful for projects).

### Parameters

```yaml
---
params:
  year: 2024
  state: "VA"
---
```

Access in R code:

```r
df |> filter(year == params$year, state == params$state)
```

Render with parameters:

```bash
quarto render doc.qmd -P year:2025 -P state:CA
```

## YAML Validation

YAML is indentation-sensitive. Common rules:
- Use spaces, never tabs
- Consistent indentation (2 spaces standard)
- Colons need a space after: `key: value`
- Strings with special characters need quotes

See `./gotchas.md` for common YAML errors.
