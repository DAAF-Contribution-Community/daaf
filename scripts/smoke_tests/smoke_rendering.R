# smoke_rendering.R -- Smoke test for the rendering pipeline (integration seams
# that individual package smokes miss). Per the Noble migration scoping guide
# section 6.4, these are the cross-package rendering paths:
#   1. Quarto render of a minimal .qmd (one R chunk + ggplot) to HTML
#   2. gt::as_raw_html() non-empty  -- the libnode/V8 guard (dlopen at load)
#   3. leaflet htmlwidgets::saveWidget(selfcontained = FALSE) non-empty
#   4. plotly  htmlwidgets::saveWidget(selfcontained = FALSE) non-empty
#   5. marimo headless HTML export (Python notebook run end-to-end)
#
# HTML output only (DAAF default is HTML, not PDF). All scratch files go under a
# per-script working directory inside smoke_tests (NEVER /tmp per CLAUDE.md).
# Cleanup uses tryCatch(finally=) rather than on.exit(): a top-level on.exit()
# does NOT fire under `Rscript` (verified 2026-07-14), so it would leak scratch.
#
# Note on marimo: invoked as a CLI subprocess via system2() because marimo's
# headless export is a command (`marimo export html`), not an R/Python API call.
# The probe `marimo export html <nb.py> -o <out.html>` was verified to run the
# notebook and emit non-trivial HTML in this container (2026-07-14).
#
# Note on code-server: a full boot probe is intentionally NOT included. code-server
# is present (`code-server --version` -> 4.117.0 with Code 1.117.0, verified
# 2026-07-14) but a real boot binds a TCP port and runs a blocking server -- unfit
# for a one-shot synchronous smoke (same reason CI excludes view_logs.sh). The
# boot + VSIX-extension-load check belongs in the interactive/manual arm64 lane
# (scoping guide 6.3), not the automated suite.

# --- Config ---
library(gt)
library(ggplot2)
library(leaflet)
library(plotly)

cat("=== rendering Smoke Test ===\n\n")

# Per-script scratch dir inside the project (not /tmp).
args <- commandArgs(trailingOnly = FALSE)
file_arg <- sub("^--file=", "", args[grep("^--file=", args)])
smoke_dir <- if (length(file_arg) == 1) dirname(normalizePath(file_arg)) else getwd()
work_dir <- file.path(smoke_dir, "rendering_smoke_work")
unlink(work_dir, recursive = TRUE)  # clear any stale dir from a prior aborted run
dir.create(work_dir, showWarnings = FALSE, recursive = TRUE)

tryCatch({

  # --- Test 1: Versions + toolchain presence ---
  cat("Test 1: Version checks\n")
  gt_ver <- as.character(packageVersion("gt"))
  leaflet_ver <- as.character(packageVersion("leaflet"))
  plotly_ver <- as.character(packageVersion("plotly"))
  quarto_bin <- Sys.which("quarto")
  marimo_bin <- Sys.which("marimo")
  cat("  gt:", gt_ver, "\n")
  cat("  leaflet:", leaflet_ver, "\n")
  cat("  plotly:", plotly_ver, "\n")
  cat("  quarto:", if (nzchar(quarto_bin)) quarto_bin else "NOT FOUND", "\n")
  cat("  marimo:", if (nzchar(marimo_bin)) marimo_bin else "NOT FOUND", "\n")
  stopifnot(nzchar(quarto_bin))
  stopifnot(nzchar(marimo_bin))
  cat("  PASS\n\n")

  # --- Test 2: Quarto render minimal .qmd -> HTML ---
  cat("Test 2: quarto render --to html (R chunk + ggplot)\n")
  qmd_path <- file.path(work_dir, "mini.qmd")
  qmd_lines <- c(
    "---",
    "title: Rendering Smoke",
    "format: html",
    "---",
    "",
    "```{r}",
    "library(ggplot2)",
    "ggplot(mtcars, aes(wt, mpg)) + geom_point()",
    "```"
  )
  writeLines(qmd_lines, qmd_path)
  # --no-execute-daemon keeps this a clean one-shot render (no background daemon).
  render_rc <- system2(
    "quarto",
    args = c("render", shQuote(qmd_path), "--to", "html", "--no-execute-daemon"),
    stdout = TRUE, stderr = TRUE
  )
  html_path <- file.path(work_dir, "mini.html")
  stopifnot(file.exists(html_path))
  html_size <- file.info(html_path)$size
  stopifnot(html_size > 1000)  # a real rendered doc, not an empty stub
  cat("  Rendered HTML:", html_size, "bytes\n")
  cat("  PASS\n\n")

  # --- Test 3: gt::as_raw_html() non-empty (libnode / V8 guard) ---
  cat("Test 3: gt::as_raw_html() non-empty (libnode guard)\n")
  raw_html <- gt(head(mtcars, 4)) |>
    tab_header(title = "Rendering Smoke") |>
    as_raw_html()
  stopifnot(is.character(raw_html))
  stopifnot(nchar(raw_html) > 500)
  stopifnot(grepl("<table", raw_html))
  cat("  as_raw_html() length:", nchar(raw_html), "chars\n")
  cat("  PASS\n\n")

  # --- Test 4: leaflet saveWidget(selfcontained = FALSE) ---
  cat("Test 4: leaflet saveWidget(selfcontained = FALSE)\n")
  lf <- leaflet() |>
    addTiles() |>
    addMarkers(lng = -77.0369, lat = 38.9072, popup = "DC")
  lf_html <- file.path(work_dir, "leaflet.html")
  htmlwidgets::saveWidget(lf, file = lf_html, selfcontained = FALSE)
  stopifnot(file.exists(lf_html))
  stopifnot(file.info(lf_html)$size > 0)
  cat("  leaflet HTML:", file.info(lf_html)$size, "bytes\n")
  cat("  PASS\n\n")

  # --- Test 5: plotly saveWidget(selfcontained = FALSE) ---
  cat("Test 5: plotly saveWidget(selfcontained = FALSE)\n")
  pl <- plot_ly(x = c(1, 2, 3), y = c(4, 5, 6), type = "scatter", mode = "markers")
  pl_html <- file.path(work_dir, "plotly.html")
  htmlwidgets::saveWidget(pl, file = pl_html, selfcontained = FALSE)
  stopifnot(file.exists(pl_html))
  stopifnot(file.info(pl_html)$size > 0)
  cat("  plotly HTML:", file.info(pl_html)$size, "bytes\n")
  cat("  PASS\n\n")

  # --- Test 6: marimo headless HTML export ---
  cat("Test 6: marimo export html (headless notebook run)\n")
  nb_path <- file.path(work_dir, "nb.py")
  nb_lines <- c(
    "import marimo",
    "app = marimo.App()",
    "",
    "@app.cell",
    "def _():",
    "    x = 2 + 2",
    "    return (x,)",
    "",
    "@app.cell",
    "def _(x):",
    "    y = x * 10",
    "    y",
    "    return",
    "",
    "if __name__ == '__main__':",
    "    app.run()"
  )
  writeLines(nb_lines, nb_path)
  nb_html <- file.path(work_dir, "nb.html")
  marimo_rc <- system2(
    "marimo",
    args = c("export", "html", shQuote(nb_path), "-o", shQuote(nb_html)),
    stdout = TRUE, stderr = TRUE
  )
  stopifnot(file.exists(nb_html))
  nb_size <- file.info(nb_html)$size
  stopifnot(nb_size > 1000)  # marimo emits a full HTML app, not a stub
  cat("  marimo HTML:", nb_size, "bytes\n")
  cat("  PASS\n\n")

  # --- Summary ---
  cat("=== All 6 tests PASSED ===\n")
  cat("Tested: quarto render / gt as_raw_html / leaflet + plotly saveWidget / marimo export\n")
  cat("Versions: gt", gt_ver, "/ leaflet", leaflet_ver, "/ plotly", plotly_ver, "\n")

}, finally = {
  # Remove scratch on both success and error (on.exit is unreliable here).
  unlink(work_dir, recursive = TRUE)
})


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-14 18:01:11
# Command: Rscript /daaf/scripts/smoke_tests/smoke_rendering.R
# Duration: 4s
# Exit code: 0
#
# --- STDOUT ---
# 
# Attaching package: ‘plotly’
# 
# The following object is masked from ‘package:ggplot2’:
# 
#     last_plot
# 
# The following object is masked from ‘package:stats’:
# 
#     filter
# 
# The following object is masked from ‘package:graphics’:
# 
#     layout
# 
# === rendering Smoke Test ===
# 
# Test 1: Version checks
#   gt: 1.3.0 
#   leaflet: 2.2.3 
#   plotly: 4.12.0 
#   quarto: /usr/local/bin/quarto 
#   marimo: /usr/local/bin/marimo 
#   PASS
# 
# Test 2: quarto render --to html (R chunk + ggplot)
#   Rendered HTML: 19615 bytes
#   PASS
# 
# Test 3: gt::as_raw_html() non-empty (libnode guard)
#   as_raw_html() length: 33216 chars
#   PASS
# 
# Test 4: leaflet saveWidget(selfcontained = FALSE)
#   leaflet HTML: 2409 bytes
#   PASS
# 
# Test 5: plotly saveWidget(selfcontained = FALSE)
#   plotly HTML: 2586 bytes
#   PASS
# 
# Test 6: marimo export html (headless notebook run)
#   marimo HTML: 39730 bytes
#   PASS
# 
# === All 6 tests PASSED ===
# Tested: quarto render / gt as_raw_html / leaflet + plotly saveWidget / marimo export
# Versions: gt 1.3.0 / leaflet 2.2.3 / plotly 4.12.0 
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
