# Output Format Configuration

## Format Selection

The `format` key in YAML frontmatter controls output. Quarto supports many formats;
these three are relevant for DAAF:

| Format | Use Case | Requirements |
|--------|----------|--------------|
| `html` | Default, interactive, self-contained | None |
| `pdf` | Print-ready, formal reports | LaTeX (TinyTeX) or Typst |
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

### Basic PDF

```yaml
---
title: "Analysis Report"
format: pdf
---
```

Requires LaTeX. Install TinyTeX:

```bash
quarto install tinytex
```

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
---
```

### PDF Options Reference

| Option | Default | Values | Purpose |
|--------|---------|--------|---------|
| `documentclass` | `article` | `article`, `report`, `book` | LaTeX class |
| `papersize` | `letter` | `letter`, `a4` | Paper size |
| `geometry` | (default) | LaTeX geometry strings | Margins, layout |
| `fontsize` | `11pt` | `10pt`, `11pt`, `12pt` | Base font size |
| `colorlinks` | `false` | `true`/`false` | Colored hyperlinks |
| `lof` | `false` | `true`/`false` | List of figures |
| `lot` | `false` | `true`/`false` | List of tables |
| `mainfont` | (system) | font name | Main text font |
| `monofont` | (system) | font name | Code font |

### PDF via Typst (Alternative)

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
  pdf:
    toc: true
  docx: default
---
```

```bash
# Renders all formats
quarto render doc.qmd

# Render specific format
quarto render doc.qmd --to pdf
```

### Format-Specific Content

Use conditional content blocks:

```markdown
::: {.content-visible when-format="html"}
This only appears in HTML output.
:::

::: {.content-visible when-format="pdf"}
This only appears in PDF output.
:::
```

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
    code-fold: false
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
- `embed-resources: true` -- single file for archiving
- `code-fold: false` -- code should be visible by default

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
