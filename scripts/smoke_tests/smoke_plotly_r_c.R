# smoke_plotly_r_a.R -- Smoke test for plotly R + htmlwidgets
# Validates: plotly, htmlwidgets
# All plots saved to temp files, verified, then cleaned up.
# Fix from smoke_plotly_r.R: selfcontained = FALSE (pandoc not available)
#
# --- Revision note (_c, 2026-11-01) ---
# Temp files move out of /tmp. smoke_plotly_r_b.R wrote its widgets with bare
# tempfile(), which puts them in R's session temp dir under /tmp, outside the
# backup and audit boundary (CLAUDE.md § Provenance Boundary). With
# selfcontained = FALSE each saveWidget() also leaves a <name>_files/ folder
# beside the HTML that file.remove() does not delete. This revision writes them
# all to the repo's tool scratch folder instead,
# /daaf/scripts/scratch/smoke_plotly_r_work/ (CLAUDE.md § Scratch Files): the
# folder is created in Config (after clearing any folder a failed run left
# behind), passed as tmpdir to every tempfile() call, and removed with its
# _files/ folders before the Summary. The path is hard-coded because smoke
# tests run only inside the DAAF container at /daaf, and CI runs log-stripped
# copies staged under scripts/scratch/smoke_live/, where a script-relative
# path would be wrong. Test logic and the Test 1 version lines are unchanged.

# --- Config ---
library(plotly)
library(htmlwidgets)
library(ggplot2)

# Working folder for this test's temp files (tool scratch, never /tmp).
# Hard-coded in-container path: fail loudly when run outside the container.
stopifnot(dir.exists("/daaf/scripts"))
work_dir <- "/daaf/scripts/scratch/smoke_plotly_r_work"
unlink(work_dir, recursive = TRUE)  # clear a folder left by a failed run
dir.create(work_dir, recursive = TRUE, showWarnings = FALSE)
stopifnot(dir.exists(work_dir))

cat("=== plotly-r Smoke Test ===\n\n")

# --- Test 1: Version check ---
cat("Test 1: Version checks\n")
plotly_ver <- as.character(packageVersion("plotly"))
htmlwidgets_ver <- as.character(packageVersion("htmlwidgets"))
r_ver <- paste0(R.version$major, ".", R.version$minor)

cat("  plotly:", plotly_ver, "\n")
cat("  htmlwidgets:", htmlwidgets_ver, "\n")
cat("  R:", r_ver, "\n")

stopifnot(numeric_version(plotly_ver) >= "4.10.0")
stopifnot(numeric_version(htmlwidgets_ver) >= "1.6.0")
cat("  PASS: All versions meet minimum requirements\n\n")

# --- Test 2: Basic scatter via plot_ly() ---
cat("Test 2: plot_ly(type = 'scatter', mode = 'markers')\n")
p2 <- plot_ly(mtcars, x = ~wt, y = ~mpg, type = "scatter", mode = "markers")
tmp2 <- tempfile(fileext = ".html", tmpdir = work_dir)
saveWidget(p2, tmp2, selfcontained = FALSE)
stopifnot(file.exists(tmp2))
stopifnot(file.info(tmp2)$size > 100)
file.remove(tmp2)
cat("  PASS\n\n")

# --- Test 3: Bar chart ---
cat("Test 3: plot_ly(type = 'bar')\n")
bar_data <- data.frame(
  category = c("A", "B", "C", "D"),
  value = c(10, 25, 15, 30)
)
p3 <- plot_ly(bar_data, x = ~category, y = ~value, type = "bar")
tmp3 <- tempfile(fileext = ".html", tmpdir = work_dir)
saveWidget(p3, tmp3, selfcontained = FALSE)
stopifnot(file.exists(tmp3))
stopifnot(file.info(tmp3)$size > 100)
file.remove(tmp3)
cat("  PASS\n\n")

# --- Test 4: ggplotly() conversion ---
cat("Test 4: ggplotly() conversion from ggplot2\n")
g4 <- ggplot(mtcars, aes(x = wt, y = mpg, color = factor(cyl))) +
  geom_point(size = 3) +
  labs(title = "ggplotly Test", color = "Cylinders") +
  theme_minimal()
p4 <- ggplotly(g4)
tmp4 <- tempfile(fileext = ".html", tmpdir = work_dir)
saveWidget(p4, tmp4, selfcontained = FALSE)
stopifnot(file.exists(tmp4))
stopifnot(file.info(tmp4)$size > 100)
file.remove(tmp4)
cat("  PASS\n\n")

# --- Test 5: layout() customization ---
cat("Test 5: layout() customization (axes, title)\n")
p5 <- plot_ly(mtcars, x = ~hp, y = ~mpg, type = "scatter", mode = "markers",
              marker = list(size = 8, color = "steelblue")) |>
  layout(
    title = list(text = "HP vs MPG", x = 0.5),
    xaxis = list(title = "Horsepower", showgrid = FALSE, showline = TRUE,
                 linecolor = "black"),
    yaxis = list(title = "Miles per Gallon", zeroline = FALSE, showline = TRUE,
                 linecolor = "black"),
    paper_bgcolor = "white",
    plot_bgcolor = "white"
  )
tmp5 <- tempfile(fileext = ".html", tmpdir = work_dir)
saveWidget(p5, tmp5, selfcontained = FALSE)
stopifnot(file.exists(tmp5))
stopifnot(file.info(tmp5)$size > 100)
file.remove(tmp5)
cat("  PASS\n\n")

# --- Test 6: htmlwidgets::saveWidget() export ---
cat("Test 6: htmlwidgets::saveWidget() export\n")
p6 <- plot_ly(mtcars, x = ~disp, y = ~mpg, type = "scatter", mode = "markers")
tmp6 <- tempfile(fileext = ".html", tmpdir = work_dir)
saveWidget(p6, tmp6, selfcontained = FALSE)
stopifnot(file.exists(tmp6))
fsize <- file.info(tmp6)$size
cat("  File size:", fsize, "bytes\n")
stopifnot(fsize > 100)
file.remove(tmp6)
cat("  PASS\n\n")

# --- Test 7: subplot() composition ---
cat("Test 7: subplot() composition\n")
p7a <- plot_ly(mtcars, x = ~wt, y = ~mpg, type = "scatter", mode = "markers",
               name = "Scatter")
p7b <- plot_ly(mtcars, x = ~factor(cyl), type = "bar", name = "Bar")
p7_combined <- subplot(p7a, p7b, nrows = 1, margin = 0.05)
tmp7 <- tempfile(fileext = ".html", tmpdir = work_dir)
saveWidget(p7_combined, tmp7, selfcontained = FALSE)
stopifnot(file.exists(tmp7))
stopifnot(file.info(tmp7)$size > 100)
file.remove(tmp7)
cat("  PASS\n\n")

# --- Cleanup ---
unlink(work_dir, recursive = TRUE)
stopifnot(!dir.exists(work_dir))

# --- Summary ---
cat("=== All 7 tests PASSED ===\n")
cat("Tested: plotly", plotly_ver, "/ htmlwidgets", htmlwidgets_ver,
    "/ R", r_ver, "\n")


# =============================================================================


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-11-01 15:12:07
# Command: Rscript /daaf/scripts/smoke_tests/smoke_plotly_r_c.R
# Duration: 1s
# Exit code: 0
# Capture: COMPLETE
#
# --- STDOUT ---
# Loading required package: ggplot2
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
# === plotly-r Smoke Test ===
# 
# Test 1: Version checks
#   plotly: 4.12.0 
#   htmlwidgets: 1.6.4 
#   R: 4.5.3 
#   PASS: All versions meet minimum requirements
# 
# Test 2: plot_ly(type = 'scatter', mode = 'markers')
# [1] TRUE
#   PASS
# 
# Test 3: plot_ly(type = 'bar')
# [1] TRUE
#   PASS
# 
# Test 4: ggplotly() conversion from ggplot2
# [1] TRUE
#   PASS
# 
# Test 5: layout() customization (axes, title)
# [1] TRUE
#   PASS
# 
# Test 6: htmlwidgets::saveWidget() export
#   File size: 3482 bytes
# [1] TRUE
#   PASS
# 
# Test 7: subplot() composition
# [1] TRUE
#   PASS
# 
# === All 7 tests PASSED ===
# Tested: plotly 4.12.0 / htmlwidgets 1.6.4 / R 4.5.3 
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
