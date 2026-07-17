# smoke_plotly_r.R -- Smoke test for plotly R + htmlwidgets
# Validates: plotly, htmlwidgets
# All plots saved to temp files, verified, then cleaned up.

# --- Config ---
library(plotly)
library(htmlwidgets)
library(ggplot2)

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
tmp2 <- tempfile(fileext = ".html")
saveWidget(p2, tmp2, selfcontained = TRUE)
stopifnot(file.exists(tmp2))
stopifnot(file.info(tmp2)$size > 1000)
file.remove(tmp2)
cat("  PASS\n\n")

# --- Test 3: Bar chart ---
cat("Test 3: plot_ly(type = 'bar')\n")
bar_data <- data.frame(
  category = c("A", "B", "C", "D"),
  value = c(10, 25, 15, 30)
)
p3 <- plot_ly(bar_data, x = ~category, y = ~value, type = "bar")
tmp3 <- tempfile(fileext = ".html")
saveWidget(p3, tmp3, selfcontained = TRUE)
stopifnot(file.exists(tmp3))
stopifnot(file.info(tmp3)$size > 1000)
file.remove(tmp3)
cat("  PASS\n\n")

# --- Test 4: ggplotly() conversion ---
cat("Test 4: ggplotly() conversion from ggplot2\n")
g4 <- ggplot(mtcars, aes(x = wt, y = mpg, color = factor(cyl))) +
  geom_point(size = 3) +
  labs(title = "ggplotly Test", color = "Cylinders") +
  theme_minimal()
p4 <- ggplotly(g4)
tmp4 <- tempfile(fileext = ".html")
saveWidget(p4, tmp4, selfcontained = TRUE)
stopifnot(file.exists(tmp4))
stopifnot(file.info(tmp4)$size > 1000)
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
tmp5 <- tempfile(fileext = ".html")
saveWidget(p5, tmp5, selfcontained = TRUE)
stopifnot(file.exists(tmp5))
stopifnot(file.info(tmp5)$size > 1000)
file.remove(tmp5)
cat("  PASS\n\n")

# --- Test 6: htmlwidgets::saveWidget() export ---
cat("Test 6: htmlwidgets::saveWidget() self-contained export\n")
p6 <- plot_ly(mtcars, x = ~disp, y = ~mpg, type = "scatter", mode = "markers")
tmp6 <- tempfile(fileext = ".html")
saveWidget(p6, tmp6, selfcontained = TRUE)
stopifnot(file.exists(tmp6))
fsize <- file.info(tmp6)$size
cat("  File size:", fsize, "bytes\n")
stopifnot(fsize > 100000)
file.remove(tmp6)
cat("  PASS\n\n")

# --- Test 7: subplot() composition ---
cat("Test 7: subplot() composition\n")
p7a <- plot_ly(mtcars, x = ~wt, y = ~mpg, type = "scatter", mode = "markers",
               name = "Scatter")
p7b <- plot_ly(mtcars, x = ~factor(cyl), type = "bar", name = "Bar")
p7_combined <- subplot(p7a, p7b, nrows = 1, margin = 0.05)
tmp7 <- tempfile(fileext = ".html")
saveWidget(p7_combined, tmp7, selfcontained = TRUE)
stopifnot(file.exists(tmp7))
stopifnot(file.info(tmp7)$size > 1000)
file.remove(tmp7)
cat("  PASS\n\n")

# --- Summary ---
cat("=== All 7 tests PASSED ===\n")
cat("Tested: plotly", plotly_ver, "/ htmlwidgets", htmlwidgets_ver,
    "/ R", r_ver, "\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-05-10 15:49:32
# Command: Rscript /daaf/scripts/smoke_tests/smoke_plotly_r.R
# Duration: 1s
# Exit code: 1
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
# Error in pandoc_self_contained_html(file, file) : 
#   Saving a widget with selfcontained = TRUE requires pandoc. See here to learn more https://bookdown.org/yihui/rmarkdown-cookbook/install-pandoc.html
# Calls: saveWidget -> pandoc_self_contained_html
# Execution halted
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
