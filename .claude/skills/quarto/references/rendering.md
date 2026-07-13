# Rendering

## quarto render

The primary command for producing output from .qmd documents:

```bash
quarto render document.qmd
```

This reads the YAML frontmatter, executes code chunks via knitr, and produces
output in the specified format.

## Basic Usage

### Render to Default Format

```bash
# Uses the format specified in YAML frontmatter
quarto render analysis.qmd
```

### Override Format

```bash
quarto render analysis.qmd --to html
quarto render analysis.qmd --to pdf
quarto render analysis.qmd --to docx
```

### Specify Output File

```bash
# Custom output filename
quarto render analysis.qmd --output report.html

# Custom output directory
quarto render analysis.qmd --output-dir output/
```

### Suppress Console Output

```bash
quarto render analysis.qmd --quiet
```

## Format Selection

### Single Format

```yaml
---
format: html
---
```

```bash
quarto render doc.qmd   # Produces doc.html
```

### Multiple Formats

```yaml
---
format:
  html: default
  pdf: default
  docx: default
---
```

```bash
# Render all formats
quarto render doc.qmd

# Render only PDF
quarto render doc.qmd --to pdf
```

### Format-Specific Options

```yaml
---
format:
  html:
    toc: true
    theme: cosmo
  pdf:
    toc: true
    documentclass: article
---
```

## Execution Control

### Skip Code Execution

```bash
quarto render doc.qmd --no-execute
```

This renders the document without running any code chunks. Useful when:
- Code was already executed and cached
- You only want to update narrative text
- Testing layout changes

### Force Re-execution

```bash
quarto render doc.qmd --execute
```

Forces all chunks to re-run, ignoring cache.

### Freeze

In YAML:

```yaml
---
execute:
  freeze: auto
---
```

`freeze: auto` -- only re-render when source changes. Previously computed
results are reused. Useful for project-level rendering where not all files
change on every render.

`freeze: true` -- never re-render (use existing computed results).

## Parameterized Rendering

### Define Parameters

```yaml
---
params:
  year: 2024
  state: "VA"
---
```

### Use in Code

```r
df |> filter(year == params$year, state == params$state)
```

### Render with Parameters

```bash
# Override parameters on command line
quarto render doc.qmd -P year:2025 -P state:CA

# Or from a YAML file
quarto render doc.qmd --execute-params params.yml
```

params.yml:
```yaml
year: 2025
state: "CA"
```

### Batch Rendering with Different Parameters

```bash
for state in VA CA NY TX; do
  quarto render doc.qmd -P state:$state --output "report_${state}.html"
done
```

Note: In DAAF Stage 9 notebooks, parameterized rendering is not used -- the
notebook is a static compilation of already-executed scripts.

## Preview Mode

### Live Preview

```bash
quarto preview document.qmd
```

Opens a browser with live preview. Changes to the .qmd trigger automatic
re-render. The preview refreshes in-place.

### Preview Options

```bash
# Custom port
quarto preview doc.qmd --port 4200

# No browser auto-open
quarto preview doc.qmd --no-browser

# Watch additional files
quarto preview doc.qmd --render all
```

## Project Rendering

### Render All Files in a Project

If a `_quarto.yml` project file exists:

```bash
# Render entire project
quarto render

# Render specific file within project
quarto render analysis.qmd
```

### _quarto.yml

```yaml
project:
  type: default
  output-dir: _output

format:
  html:
    theme: cosmo
    toc: true
```

Project-level settings apply to all .qmd files in the directory.

## Execution Directory

By default, code executes in the directory containing the .qmd file.

```bash
# Override execution directory
quarto render doc.qmd --execute-dir /path/to/data
```

This affects relative paths in R code. For DAAF projects, scripts use
project-relative paths, so the execution directory should be the project root.

## Logging and Debugging

### Log Output

```bash
quarto render doc.qmd --log render.log --log-level info
```

Log levels: `info`, `warning`, `error`, `critical`

### Debug Mode

```bash
quarto render doc.qmd --debug
```

Keeps intermediate files (useful for diagnosing rendering issues).

### Verbose knitr Output

In YAML:

```yaml
---
execute:
  debug: true
---
```

Or per-chunk:

````markdown
```{r}
#| error: true

# Shows errors in output instead of stopping render
risky_code()
```
````

## Output File Locations

Default behavior:

| Input | Output | Location |
|-------|--------|----------|
| `analysis.qmd` | `analysis.html` | Same directory |
| `analysis.qmd` (PDF) | `analysis.pdf` | Same directory |
| `analysis.qmd` | `analysis_files/` | Figure directory (same level) |

With `--output-dir`:

```bash
quarto render analysis.qmd --output-dir output/
# Produces: output/analysis.html
```

With `embed-resources: true` in YAML, no `_files/` directory is created --
everything is in the single HTML file.

For users on the host, the `scripts/host/view_quarto.sh` / `.ps1` convenience
scripts wrap render + copy-out + browser-open in one step (the R counterpart to
`view_notebooks.sh` for marimo).

## Render Performance

### Speed Tips

1. **Use `eval: false`** for Stage 9 notebooks (no code execution)
2. **Use `freeze: auto`** for iterative development
3. **Cache expensive chunks** with `cache: true`
4. **Use `--no-execute`** when only editing narrative

### Typical Render Times

| Scenario | Time |
|----------|------|
| Stage 9 notebook (eval: false, ~20 chunks) | 2-5 seconds |
| Analysis doc (10 chunks, no caching) | 10-30 seconds |
| Analysis doc (cached) | 3-5 seconds |
| PDF with LaTeX | 15-60 seconds |
| PDF with Typst | 5-15 seconds |

## Common Render Commands for DAAF

```bash
# Stage 9 notebook (fast -- no code execution)
quarto render 2026-05-08_Research_Notebook.qmd --to html

# Analysis report with code execution
quarto render 2026-05-08_Analysis_Report.qmd --to html

# PDF report
quarto render 2026-05-08_Report.qmd --to pdf

# Check rendering setup
quarto check knitr
```

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| "knitr not found" | R/knitr not installed | `quarto check knitr` |
| Render hangs | Infinite loop in R code | Add `--execute-debug` |
| Missing figures | Wrong working directory | Check `--execute-dir` |
| PDF fails | No LaTeX | `quarto install tinytex` |
| Old output | Cache stale | `--cache-refresh` or delete `_cache/` |

See `./gotchas.md` for more detailed troubleshooting.
