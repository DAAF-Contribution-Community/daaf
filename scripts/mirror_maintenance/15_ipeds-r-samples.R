# --- Config ---
# INTENT: Execute the IPEDS R query samples verbatim against the live pinned HF
#   mirror. Both samples use a PLAIN read_parquet(url) and carry a documented NOTE
#   that this can fail under the R arrow binding on Polars-written string_view
#   columns. Running AS WRITTEN — if a sample fails, that is a finding, not a fix.
#     15a - graduation-rates.md R outcome-measures example (lines 568-593)
#     15b - financial-aid.md R net-price-by-income example (lines 611-637)
# ASSUMES: network egress to huggingface.co; arrow/dplyr present.

sample_results <- list()

# Download timeout raised so the HTTP parquet reads do not truncate (the samples
# themselves do not set it; without this a large read would truncate — a separate
# concern from the string_view NOTE the samples carry).
options(timeout = max(600, getOption("timeout")))

library(arrow)
library(dplyr)

# ===========================================================================
# SAMPLE 15a
# SOURCE: education-data-source-ipeds/references/graduation-rates.md lines 568-593
#   "Querying Outcome Measures (Example)" — R. Plain read_parquet as written.
# ===========================================================================
cat("\n=== SAMPLE 15a: graduation-rates.md R outcome-measures (lines 568-593) ===\n")
sample_results[["15a"]] <- tryCatch({
  # Mirror root + pinned revision (keep in sync with education-data-query
  # references/mirrors.yaml: HF root_url + vintage.hf_revision).
  MIRROR <- "https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve"
  REVISION <- "0ad00ce0e232c96b0642459e4e7326607a8d26aa"  # immutable commit SHA of the v2 upload
  url <- paste0(MIRROR, "/", REVISION, "/ipeds/colleges_ipeds_outcome-measures.parquet")
  # NOTE: illustrative only — mirror parquet files are Polars-written and may
  # declare string_view columns, so a plain read can fail under R arrow
  # ("cannot handle Array of type <utf8_view>").
  df <- read_parquet(url)

  # 8-year completion rates by enrollment intensity for first-time students
  om <- df |>
    filter(
      year == 2022,
      class_level == 1,
      fed_aid_type == 99,
      ftpt %in% c(1, 2)
    ) |>
    select(unitid, ftpt, completion_rate_8yr, transfer_rate_8yr)

  cat(sprintf("  full parquet: %s rows x %d cols\n", format(nrow(df), big.mark = ","), ncol(df)))
  cat(sprintf("  filtered om: %s rows\n", format(nrow(om), big.mark = ",")))
  print(utils::head(om, 5))
  # Task bar: a sample must produce a non-empty, sane result.
  stopifnot(nrow(om) > 0)
  list(status = "PASS",
       evidence = sprintf("plain read_parquet succeeded (%s rows); filtered om=%s rows",
                          format(nrow(df), big.mark = ","), format(nrow(om), big.mark = ",")))
}, error = function(e) {
  cat(sprintf("SAMPLE 15a FAILED: %s\n", conditionMessage(e)))
  list(status = "FAIL", evidence = conditionMessage(e))
})


# ===========================================================================
# SAMPLE 15b
# SOURCE: education-data-source-ipeds/references/financial-aid.md lines 611-637
#   "Querying Net Price by Income (Example)" — R. Plain read_parquet as written.
# ===========================================================================
cat("\n=== SAMPLE 15b: financial-aid.md R net-price-by-income (lines 611-637) ===\n")
sample_results[["15b"]] <- tryCatch({
  MIRROR <- "https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve"
  REVISION <- "0ad00ce0e232c96b0642459e4e7326607a8d26aa"  # immutable commit SHA of the v2 upload
  url <- paste0(MIRROR, "/", REVISION, "/ipeds/colleges_ipeds_sfa_grants_and_net_price.parquet")
  # NOTE: illustrative only — plain read can fail under R arrow on string_view.
  df <- read_parquet(url)

  # Net price by income level for a specific institution and year
  net_prices <- df |>
    filter(
      unitid == 166027,
      year == 2020,
      income_level %in% c(1, 2, 3, 4, 5),
      type_of_aid == 9
    ) |>
    select(income_level, net_price, number_of_students) |>
    arrange(income_level)

  cat(sprintf("  full parquet: %s rows x %d cols\n", format(nrow(df), big.mark = ","), ncol(df)))
  cat(sprintf("  filtered net_prices: %s rows\n", format(nrow(net_prices), big.mark = ",")))
  print(net_prices)
  stopifnot(nrow(net_prices) > 0)
  list(status = "PASS",
       evidence = sprintf("plain read_parquet succeeded (%s rows); MIT 2020 net-price=%s rows",
                          format(nrow(df), big.mark = ","), format(nrow(net_prices), big.mark = ",")))
}, error = function(e) {
  cat(sprintf("SAMPLE 15b FAILED: %s\n", conditionMessage(e)))
  list(status = "FAIL", evidence = conditionMessage(e))
})


# --- Summary ---
cat("\n=== IPEDS R SAMPLE SUMMARY ===\n")
for (sid in c("15a", "15b")) {
  r <- sample_results[[sid]]
  cat(sprintf("  [%s] %s: %s\n", r$status, sid, r$evidence))
}
n_pass <- sum(vapply(sample_results, function(r) r$status == "PASS", logical(1)))
cat(sprintf("\nPASS %d/%d\n", n_pass, length(sample_results)))


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 13:11:45
# Command: Rscript /daaf/scripts/mirror_maintenance/15_ipeds-r-samples.R
# Duration: 3s
# Exit code: 0
#
# --- STDOUT ---
# 
# Attaching package: ‘arrow’
# 
# The following object is masked from ‘package:utils’:
# 
#     timestamp
# 
# 
# Attaching package: ‘dplyr’
# 
# The following objects are masked from ‘package:stats’:
# 
#     filter, lag
# 
# The following objects are masked from ‘package:base’:
# 
#     intersect, setdiff, setequal, union
# 
# 
# === SAMPLE 15a: graduation-rates.md R outcome-measures (lines 568-593) ===
#   full parquet: 575,473 rows x 38 cols
#   filtered om: 0 rows
# # A tibble: 0 × 4
# # ℹ 4 variables: unitid <int>, ftpt <int>, completion_rate_8yr <dbl>,
# #   transfer_rate_8yr <dbl>
# SAMPLE 15a FAILED: nrow(om) > 0 is not TRUE
# 
# === SAMPLE 15b: financial-aid.md R net-price-by-income (lines 611-637) ===
#   full parquet: 597,920 rows x 15 cols
#   filtered net_prices: 5 rows
# # A tibble: 5 × 3
#   income_level net_price number_of_students
#          <int>     <int>              <int>
# 1            1      1754                 67
# 2            2      -273                 90
# 3            3       538                109
# 4            4     10912                 32
# 5            5     48113                 99
# 
# === IPEDS R SAMPLE SUMMARY ===
#   [FAIL] 15a: nrow(om) > 0 is not TRUE
#   [PASS] 15b: plain read_parquet succeeded (597,920 rows); MIT 2020 net-price=5 rows
# 
# PASS 1/2
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
