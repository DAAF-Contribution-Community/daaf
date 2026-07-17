# smoke_gt.R -- Smoke test for gt + kableExtra + modelsummary
# Validates: gt, kableExtra, modelsummary, knitr
# All tables saved to temp files, verified, then cleaned up.

# --- Config ---
library(gt)
library(kableExtra)
library(modelsummary)

cat("=== gt Smoke Test ===\n\n")

# --- Test 1: Version checks ---
cat("Test 1: Version checks\n")
gt_ver <- as.character(packageVersion("gt"))
kableExtra_ver <- as.character(packageVersion("kableExtra"))
modelsummary_ver <- as.character(packageVersion("modelsummary"))
knitr_ver <- as.character(packageVersion("knitr"))

cat("  gt:", gt_ver, "\n")
cat("  kableExtra:", kableExtra_ver, "\n")
cat("  modelsummary:", modelsummary_ver, "\n")
cat("  knitr:", knitr_ver, "\n")

stopifnot(numeric_version(gt_ver) >= "1.0.0")
stopifnot(numeric_version(kableExtra_ver) >= "1.4.0")
stopifnot(numeric_version(modelsummary_ver) >= "2.0.0")
cat("  PASS: All versions meet minimum requirements\n\n")

# --- Test 2: Basic gt() table creation ---
cat("Test 2: gt() basic table creation\n")
tbl2 <- head(mtcars, 5) |>
  tibble::rownames_to_column("car") |>
  gt()
stopifnot(inherits(tbl2, "gt_tbl"))
cat("  PASS\n\n")

# --- Test 3: fmt_number() formatting ---
cat("Test 3: fmt_number() formatting\n")
tbl3 <- data.frame(
  item = c("A", "B", "C"),
  value = c(1234.567, 89012.34, 5.6789)
) |>
  gt() |>
  fmt_number(columns = value, decimals = 2)
stopifnot(inherits(tbl3, "gt_tbl"))
cat("  PASS\n\n")

# --- Test 4: tab_header() / tab_source_note() ---
cat("Test 4: tab_header() and tab_source_note()\n")
tbl4 <- head(mtcars, 3) |>
  gt() |>
  tab_header(
    title = "Test Title",
    subtitle = "Test Subtitle"
  ) |>
  tab_source_note("Source: mtcars dataset.")
stopifnot(inherits(tbl4, "gt_tbl"))
cat("  PASS\n\n")

# --- Test 5: tab_style() conditional formatting ---
cat("Test 5: tab_style() conditional formatting\n")
tbl5 <- mtcars[1:6, c("mpg", "cyl", "hp")] |>
  gt() |>
  tab_style(
    style = list(
      cell_text(weight = "bold", color = "red")
    ),
    locations = cells_body(
      columns = mpg,
      rows = mpg > 20
    )
  )
stopifnot(inherits(tbl5, "gt_tbl"))
cat("  PASS\n\n")

# --- Test 6: tab_spanner() column spanners ---
cat("Test 6: tab_spanner() column spanners\n")
tbl6 <- mtcars[1:4, c("mpg", "cyl", "hp", "wt")] |>
  gt() |>
  tab_spanner(label = "Performance", columns = c(mpg, hp)) |>
  tab_spanner(label = "Specs", columns = c(cyl, wt))
stopifnot(inherits(tbl6, "gt_tbl"))
cat("  PASS\n\n")

# --- Test 7: fmt_percent() and fmt_currency() ---
cat("Test 7: fmt_percent() and fmt_currency()\n")
tbl7 <- data.frame(
  category = c("X", "Y"),
  rate = c(0.452, 0.831),
  cost = c(1500.50, 2300.75)
) |>
  gt() |>
  fmt_percent(columns = rate, decimals = 1) |>
  fmt_currency(columns = cost, currency = "USD", decimals = 0)
stopifnot(inherits(tbl7, "gt_tbl"))
cat("  PASS\n\n")

# --- Test 8: modelsummary() with a simple lm model ---
cat("Test 8: modelsummary() with lm()\n")
fit1 <- lm(mpg ~ wt, data = mtcars)
fit2 <- lm(mpg ~ wt + hp, data = mtcars)
tbl8 <- modelsummary(
  list("Model 1" = fit1, "Model 2" = fit2),
  output = "gt",
  stars = c("*" = 0.05, "**" = 0.01, "***" = 0.001)
)
stopifnot(inherits(tbl8, "gt_tbl"))
cat("  PASS\n\n")

# --- Test 9: kableExtra kbl() basic table ---
cat("Test 9: kableExtra kbl() basic table\n")
tbl9 <- head(mtcars, 5) |>
  kbl(format = "html", digits = 2, caption = "kableExtra Test") |>
  kable_styling(bootstrap_options = c("striped", "condensed"))
stopifnot(inherits(tbl9, "kableExtra"))
cat("  PASS\n\n")

# --- Test 10: gtsave() to HTML ---
cat("Test 10: gtsave() to HTML\n")
tmp10 <- tempfile(fileext = ".html")
tbl10 <- mtcars[1:5, c("mpg", "cyl", "hp")] |>
  gt() |>
  tab_header(title = "Export Test") |>
  fmt_number(columns = c(mpg, hp), decimals = 1)
gtsave(tbl10, tmp10)
stopifnot(file.exists(tmp10))
fsize <- file.info(tmp10)$size
cat("  File size:", fsize, "bytes\n")
stopifnot(fsize > 100)
file.remove(tmp10)
cat("  PASS\n\n")

# --- Test 11: Row groups and summary rows ---
cat("Test 11: Row groups and summary_rows()\n")
group_df <- data.frame(
  region = c("North", "North", "South", "South"),
  state = c("A", "B", "C", "D"),
  pop = c(100, 200, 150, 250)
)
tbl11 <- group_df |>
  gt(groupname_col = "region") |>
  summary_rows(
    groups = everything(),
    columns = pop,
    fns = list(Total = ~ sum(.)),
    fmt = ~ fmt_integer(.)
  )
stopifnot(inherits(tbl11, "gt_tbl"))
cat("  PASS\n\n")

# --- Summary ---
cat("=== All 11 tests PASSED ===\n")
cat("Tested: gt", gt_ver, "/ kableExtra", kableExtra_ver,
    "/ modelsummary", modelsummary_ver, "\n")
cat("        knitr", knitr_ver, "\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-05-13 17:45:54
# Command: Rscript /daaf/scripts/smoke_tests/smoke_gt.R
# Duration: 2s
# Exit code: 0
#
# --- STDOUT ---
# === gt Smoke Test ===
# 
# Test 1: Version checks
#   gt: 1.3.0 
#   kableExtra: 1.4.0 
#   modelsummary: 2.6.0 
#   knitr: 1.51 
#   PASS: All versions meet minimum requirements
# 
# Test 2: gt() basic table creation
#   PASS
# 
# Test 3: fmt_number() formatting
#   PASS
# 
# Test 4: tab_header() and tab_source_note()
#   PASS
# 
# Test 5: tab_style() conditional formatting
#   PASS
# 
# Test 6: tab_spanner() column spanners
#   PASS
# 
# Test 7: fmt_percent() and fmt_currency()
#   PASS
# 
# Test 8: modelsummary() with lm()
#   PASS
# 
# Test 9: kableExtra kbl() basic table
#   PASS
# 
# Test 10: gtsave() to HTML
#   File size: 11119 bytes
# [1] TRUE
#   PASS
# 
# Test 11: Row groups and summary_rows()
#   PASS
# 
# === All 11 tests PASSED ===
# Tested: gt 1.3.0 / kableExtra 1.4.0 / modelsummary 2.6.0 
#         knitr 1.51 
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
