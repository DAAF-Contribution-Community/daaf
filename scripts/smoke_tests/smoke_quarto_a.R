# smoke_quarto.R — Smoke test for Quarto + knitr installation
# Validates: Quarto CLI, .qmd creation, rendering, chunk options, inline R,
#            figure output (ggplot2), table output (knitr::kable)

# --- Config ---

test_dir <- file.path(tempdir(), "quarto_smoke_test")
dir.create(test_dir, recursive = TRUE, showWarnings = FALSE)
pass_count <- 0L
fail_count <- 0L

check <- function(label, condition) {
  if (isTRUE(condition)) {
    cat("[PASS]", label, "\n")
    pass_count <<- pass_count + 1L
  } else {
    cat("[FAIL]", label, "\n")
    fail_count <<- fail_count + 1L
  }
}

# --- Test 1: Quarto CLI installed ---

quarto_version <- tryCatch(
  system2("quarto", c("--version"), stdout = TRUE, stderr = TRUE),
  error = function(e) NULL
)
check("Test 1: Quarto CLI installed", !is.null(quarto_version) && length(quarto_version) > 0)
cat("  Quarto version:", quarto_version, "\n")

# --- Test 2: Write minimal .qmd with R chunk ---

minimal_qmd <- file.path(test_dir, "minimal.qmd")
writeLines(c(
  "---",
  'title: "Smoke Test"',
  "format: html",
  "---",
  "",
  "## Hello",
  "",
  "This is a minimal Quarto document.",
  "",
  "```{r}",
  "1 + 1",
  "```"
), minimal_qmd)
check("Test 2: Write minimal .qmd with R chunk", file.exists(minimal_qmd))

# --- Test 3: quarto render to HTML ---

minimal_html <- file.path(test_dir, "minimal.html")
render_result <- tryCatch({
  system2("quarto", c("render", minimal_qmd, "--to", "html", "--quiet"),
          stdout = TRUE, stderr = TRUE)
  file.exists(minimal_html)
}, error = function(e) FALSE)
check("Test 3: quarto render to HTML", render_result)

# --- Test 4: YAML frontmatter parsed correctly ---

if (file.exists(minimal_html)) {
  html_content <- readLines(minimal_html, warn = FALSE)
  html_text <- paste(html_content, collapse = "\n")
  has_title <- grepl("Smoke Test", html_text, fixed = TRUE)
  check("Test 4: YAML frontmatter parsed correctly (title present)", has_title)
} else {
  check("Test 4: YAML frontmatter parsed correctly (title present)", FALSE)
}

# --- Test 5: Code chunk with #| echo: true ---

echo_qmd <- file.path(test_dir, "echo_test.qmd")
writeLines(c(
  "---",
  'title: "Echo Test"',
  "format: html",
  "---",
  "",
  "```{r}",
  "#| echo: true",
  "#| label: echo-chunk",
  'cat("echo_sentinel_value")',
  "```"
), echo_qmd)

echo_html <- file.path(test_dir, "echo_test.html")
tryCatch({
  system2("quarto", c("render", echo_qmd, "--to", "html", "--quiet"),
          stdout = TRUE, stderr = TRUE)
}, error = function(e) NULL)

if (file.exists(echo_html)) {
  echo_content <- paste(readLines(echo_html, warn = FALSE), collapse = "\n")
  has_code <- grepl("echo_sentinel_value", echo_content, fixed = TRUE)
  check("Test 5: Code chunk with #| echo: true", has_code)
} else {
  check("Test 5: Code chunk with #| echo: true", FALSE)
}

# --- Test 6: Inline R expression ---

inline_qmd <- file.path(test_dir, "inline_test.qmd")
writeLines(c(
  "---",
  'title: "Inline Test"',
  "format: html",
  "---",
  "",
  "The answer is `r 6 * 7`."
), inline_qmd)

inline_html <- file.path(test_dir, "inline_test.html")
tryCatch({
  system2("quarto", c("render", inline_qmd, "--to", "html", "--quiet"),
          stdout = TRUE, stderr = TRUE)
}, error = function(e) NULL)

if (file.exists(inline_html)) {
  inline_content <- paste(readLines(inline_html, warn = FALSE), collapse = "\n")
  has_42 <- grepl("42", inline_content, fixed = TRUE)
  check("Test 6: Inline R expression (`r 6 * 7` = 42)", has_42)
} else {
  check("Test 6: Inline R expression (`r 6 * 7` = 42)", FALSE)
}

# --- Test 7: Figure output from ggplot2 chunk ---

fig_qmd <- file.path(test_dir, "figure_test.qmd")
writeLines(c(
  "---",
  'title: "Figure Test"',
  "format: html",
  "execute:",
  "  echo: false",
  "---",
  "",
  "```{r}",
  "#| label: fig-test-plot",
  '#| fig-cap: "Test scatter plot"',
  "",
  "library(ggplot2)",
  "ggplot(mtcars, aes(x = wt, y = mpg)) +",
  "  geom_point() +",
  '  labs(title = "Weight vs MPG")',
  "```"
), fig_qmd)

fig_html <- file.path(test_dir, "figure_test.html")
tryCatch({
  system2("quarto", c("render", fig_qmd, "--to", "html", "--quiet"),
          stdout = TRUE, stderr = TRUE)
}, error = function(e) NULL)

if (file.exists(fig_html)) {
  fig_content <- paste(readLines(fig_html, warn = FALSE), collapse = "\n")
  # Check for figure caption or img tag
  has_figure <- grepl("fig-test-plot", fig_content, fixed = TRUE) ||
                grepl("<img", fig_content, fixed = TRUE) ||
                grepl("Test scatter plot", fig_content, fixed = TRUE)
  check("Test 7: Figure output from ggplot2 chunk", has_figure)
} else {
  check("Test 7: Figure output from ggplot2 chunk", FALSE)
}

# --- Test 8: Table output from knitr::kable chunk ---

tbl_qmd <- file.path(test_dir, "table_test.qmd")
writeLines(c(
  "---",
  'title: "Table Test"',
  "format: html",
  "---",
  "",
  "```{r}",
  "#| label: tbl-test-table",
  '#| tbl-cap: "First rows of mtcars"',
  "",
  "knitr::kable(head(mtcars, 5))",
  "```"
), tbl_qmd)

tbl_html <- file.path(test_dir, "table_test.html")
tryCatch({
  system2("quarto", c("render", tbl_qmd, "--to", "html", "--quiet"),
          stdout = TRUE, stderr = TRUE)
}, error = function(e) NULL)

if (file.exists(tbl_html)) {
  tbl_content <- paste(readLines(tbl_html, warn = FALSE), collapse = "\n")
  # Check for table element or mtcars data (e.g., "Mazda" or "<table")
  has_table <- grepl("Mazda", tbl_content, fixed = TRUE) ||
               grepl("<table", tbl_content, fixed = TRUE) ||
               grepl("First rows of mtcars", tbl_content, fixed = TRUE)
  check("Test 8: Table output from knitr::kable chunk", has_table)
} else {
  check("Test 8: Table output from knitr::kable chunk", FALSE)
}

# --- Cleanup ---

unlink(test_dir, recursive = TRUE)

# --- Summary ---

cat("\n========================================\n")
cat("Quarto Smoke Test Summary\n")
cat("========================================\n")
cat("Passed:", pass_count, "/", pass_count + fail_count, "\n")
cat("Failed:", fail_count, "/", pass_count + fail_count, "\n")

if (fail_count > 0) {
  cat("\nSMOKE TEST FAILED — review failures above\n")
} else {
  cat("\nALL TESTS PASSED\n")
}


# =============================================================================


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-07 15:19:13
# Command: Rscript /daaf/scripts/smoke_tests/smoke_quarto_a.R
# Duration: 9s
# Exit code: 0
#
# --- STDOUT ---
# [PASS] Test 1: Quarto CLI installed 
#   Quarto version: 1.7.29 
# [PASS] Test 2: Write minimal .qmd with R chunk 
# [PASS] Test 3: quarto render to HTML 
# [PASS] Test 4: YAML frontmatter parsed correctly (title present) 
# character(0)
# [PASS] Test 5: Code chunk with #| echo: true 
# character(0)
# [PASS] Test 6: Inline R expression (`r 6 * 7` = 42) 
# character(0)
# [PASS] Test 7: Figure output from ggplot2 chunk 
# character(0)
# [PASS] Test 8: Table output from knitr::kable chunk 
# 
# ========================================
# Quarto Smoke Test Summary
# ========================================
# Passed: 8 / 8 
# Failed: 0 / 8 
# 
# ALL TESTS PASSED
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
