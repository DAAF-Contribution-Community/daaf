# smoke_quarto.R — Smoke test for Quarto + knitr installation
# Validates: Quarto CLI, .qmd creation, rendering, chunk options, inline R,
#            figure output (ggplot2), table output (knitr::kable)
#
# --- Revision note (_b, 2026-07-14) ---
# This revision fixes two defects found in smoke_quarto_a.R via a dual-arch
# (noble x86_64 + arm64) false-positive diagnosis:
#
#   D1 (exit-code): smoke_quarto_a.R printed "SMOKE TEST FAILED" when
#     fail_count > 0 but never called quit(status = 1). The script therefore
#     exited 0 on failure and the suite runner counted it PASS. Fixed in the
#     Summary block below: quit(status = 1) fires when fail_count > 0.
#
#   D2 (Test 6 invalid): Test 6 rendered a .qmd whose only R content was an
#     inline `r ...` expression. Quarto never engages the knitr engine for a
#     chunk-less doc, so the inline expression rendered UNEVALUATED. The old
#     assertion then grepped for the substring "42" anywhere in the standalone
#     HTML — and Quarto's content-hashed asset filenames sometimes contain "42"
#     (e.g. bootstrap-96b429677d...), so the verdict was decided by a random
#     hash: false-PASS on x86 (and on the 2026-07-07 bookworm run), fail on
#     arm64. Fixed here by (a) adding `engine: knitr` to the doc's YAML so the
#     inline expression evaluates, and (b) asserting the rendered HTML contains
#     the exact phrase "The answer is 42", which asset-hash boilerplate cannot
#     satisfy.

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
# REVISION (_b): `engine: knitr` in the YAML forces Quarto to engage the knitr
# engine even though the doc has no fenced R chunk, so the inline `r 6 * 7`
# expression actually evaluates to 42. The assertion checks for the exact
# rendered sentence "The answer is 42" — asset-hash boilerplate (which happens
# to contain the substring "42" on some arches) cannot satisfy this phrase.

inline_qmd <- file.path(test_dir, "inline_test.qmd")
writeLines(c(
  "---",
  'title: "Inline Test"',
  "format: html",
  "engine: knitr",
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
  has_answer <- grepl("The answer is 42", inline_content, fixed = TRUE)
  check("Test 6: Inline R expression (`r 6 * 7` -> \"The answer is 42\")", has_answer)
} else {
  check("Test 6: Inline R expression (`r 6 * 7` -> \"The answer is 42\")", FALSE)
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
  # REVISION (_b, D1): exit nonzero so the suite runner registers the failure.
  quit(status = 1)
} else {
  cat("\nALL TESTS PASSED\n")
}


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-14 20:50:12
# Command: Rscript /daaf/scripts/smoke_tests/smoke_quarto_b.R
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
# [PASS] Test 6: Inline R expression (`r 6 * 7` -> "The answer is 42") 
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
