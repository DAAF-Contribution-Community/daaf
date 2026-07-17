# --- Config ---
# INTENT: Smoke test for tidyverse skill — verify installed versions and
#         core API patterns documented in skill reference files

library(dplyr)
library(tidyr)
library(readr)
library(purrr)
library(stringr)
library(forcats)
library(lubridate)
library(arrow)
library(data.table)

test_count <- 0
pass_count <- 0

# --- Version Check ---
cat("=== VERSION CHECK ===\n")

# Test 1: Package version alignment with SKILL.md metadata
expected_versions <- list(
  dplyr = "1.2.1",
  tidyr = "1.3.2",
  readr = "2.2.0",
  purrr = "1.2.2",
  stringr = "1.6.0",
  forcats = "1.0.1",
  lubridate = "1.9.5",
  data.table = "1.18.2.1",
  arrow = "23.0.1.2"
)

for (pkg_name in names(expected_versions)) {
  installed <- as.character(packageVersion(pkg_name))
  expected <- expected_versions[[pkg_name]]
  cat(pkg_name, ": installed =", installed, ", expected =", expected, "\n")
  stopifnot(installed == expected)
}

cat("R version:", R.version$major, ".", R.version$minor, "\n", sep = "")
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("PASS: Versions aligned\n\n")

# --- Core API Tests ---
cat("=== CORE API TESTS ===\n")

# Test 2: filter() + select() + mutate() — core verb pipeline
# Source: quickstart.md
test_df <- tibble(
  state = c("CA", "TX", "NY", "CA", "TX"),
  year = c(2020, 2020, 2020, 2021, 2021),
  enrollment = c(6200, 5400, 2600, 6100, 5500),
  frl_count = c(3100, 2700, 1300, 3000, 2750)
)

result <- test_df |>
  filter(year == 2020) |>
  select(state, enrollment, frl_count) |>
  mutate(frl_rate = frl_count / enrollment)

stopifnot(nrow(result) == 3)
stopifnot(ncol(result) == 4)
stopifnot("frl_rate" %in% names(result))
stopifnot(all(result$frl_rate >= 0 & result$frl_rate <= 1))
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("PASS: filter() + select() + mutate() pipeline\n")

# Test 3: group_by() + summarize()
# Source: quickstart.md
grouped <- test_df |>
  group_by(state) |>
  summarize(
    avg_enroll = mean(enrollment),
    n = n(),
    .groups = "drop"
  )

stopifnot(nrow(grouped) == 3)
stopifnot(all(c("state", "avg_enroll", "n") %in% names(grouped)))
stopifnot(grouped$n[grouped$state == "CA"] == 2)
stopifnot(!is.grouped_df(grouped))
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("PASS: group_by() + summarize()\n")

# Test 4: pivot_longer() + pivot_wider()
# Source: reshaping.md
wide_df <- tibble(
  state = c("CA", "TX"),
  pop_2020 = c(39500, 29000),
  pop_2021 = c(39200, 29200)
)

long_df <- wide_df |>
  pivot_longer(
    cols = starts_with("pop_"),
    names_to = "year",
    names_prefix = "pop_",
    values_to = "population"
  )

stopifnot(nrow(long_df) == 4)
stopifnot(all(c("state", "year", "population") %in% names(long_df)))
stopifnot(all(long_df$year %in% c("2020", "2021")))

# Round-trip back to wide
wide_again <- long_df |>
  pivot_wider(
    names_from = year,
    values_from = population,
    names_prefix = "pop_"
  )

stopifnot(nrow(wide_again) == 2)
stopifnot(ncol(wide_again) == 3)
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("PASS: pivot_longer() + pivot_wider()\n")

# Test 5: left_join() + anti_join()
# Source: joins.md
schools <- tibble(
  ncessch = c("001", "002", "003", "004"),
  state = c("CA", "CA", "TX", "NY"),
  enrollment = c(500, 300, 450, 600)
)

districts <- tibble(
  ncessch = c("001", "002", "003"),
  district_name = c("LA USD", "SF USD", "Houston ISD")
)

joined <- schools |> left_join(districts, by = "ncessch")
stopifnot(nrow(joined) == 4)
stopifnot(sum(is.na(joined$district_name)) == 1)

unmatched <- schools |> anti_join(districts, by = "ncessch")
stopifnot(nrow(unmatched) == 1)
stopifnot(unmatched$ncessch == "004")
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("PASS: left_join() + anti_join()\n")

# --- Integration Tests ---
cat("\n=== INTEGRATION TESTS ===\n")

# Test 6: Parquet round-trip via arrow
# Source: io.md
tmp_parquet <- tempfile(fileext = ".parquet")

write_parquet(test_df, tmp_parquet)
stopifnot(file.exists(tmp_parquet))

df_read <- read_parquet(tmp_parquet)
stopifnot(nrow(df_read) == nrow(test_df))
stopifnot(ncol(df_read) == ncol(test_df))
stopifnot(all(names(df_read) == names(test_df)))
stopifnot(all(df_read$enrollment == test_df$enrollment))

file.remove(tmp_parquet)
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("PASS: arrow::read_parquet() + arrow::write_parquet() round-trip\n")

# Test 7: Native pipe |> works
# Source: quickstart.md
pipe_result <- test_df |> filter(year == 2020) |> nrow()
stopifnot(pipe_result == 3)
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("PASS: Native pipe |> works\n")

# Test 8: readr::read_csv() on inline data
# Source: io.md
csv_data <- "state,year,enrollment\nCA,2020,6200\nTX,2020,5400\n"
df_csv <- read_csv(csv_data, show_col_types = FALSE)
stopifnot(nrow(df_csv) == 2)
stopifnot(all(c("state", "year", "enrollment") %in% names(df_csv)))
stopifnot(df_csv$enrollment[1] == 6200)
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("PASS: readr::read_csv() on inline data\n")

# Test 9: stringr::str_detect() + str_replace()
# Source: strings-dates.md
test_strings <- c("Elementary School", "Middle School", "High School")
detected <- str_detect(test_strings, "Elementary")
stopifnot(identical(detected, c(TRUE, FALSE, FALSE)))

replaced <- str_replace(test_strings[1], "Elementary", "Primary")
stopifnot(replaced == "Primary School")

padded <- str_pad("42", width = 5, side = "left", pad = "0")
stopifnot(padded == "00042")
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("PASS: stringr::str_detect() + str_replace() + str_pad()\n")

# Test 10: lubridate::ymd() + date arithmetic
# Source: strings-dates.md
d <- ymd("2024-01-15")
stopifnot(inherits(d, "Date"))
stopifnot(year(d) == 2024)
stopifnot(month(d) == 1)
stopifnot(day(d) == 15)

d_plus_7 <- d + days(7)
stopifnot(d_plus_7 == ymd("2024-01-22"))

d_plus_month <- d + months(1)
stopifnot(d_plus_month == ymd("2024-02-15"))

diff_days <- as.numeric(ymd("2024-06-30") - d, units = "days")
stopifnot(diff_days == 167)
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("PASS: lubridate::ymd() + date arithmetic\n")

# Test 11: data.table basic operations
# Source: data-table.md
DT <- as.data.table(test_df)
stopifnot(is.data.table(DT))

# Filter (i)
dt_filtered <- DT[year == 2020]
stopifnot(nrow(dt_filtered) == 3)

# Aggregate (j + by)
dt_agg <- DT[, .(avg_enroll = mean(enrollment), n = .N), by = state]
stopifnot(nrow(dt_agg) == 3)
stopifnot(all(c("state", "avg_enroll", "n") %in% names(dt_agg)))

# In-place column creation
DT[, rate := frl_count / enrollment]
stopifnot("rate" %in% names(DT))
stopifnot(all(DT$rate >= 0 & DT$rate <= 1))
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("PASS: data.table DT[i, j, by] + := operations\n")

# --- Summary ---
cat("\n=== SMOKE TEST SUMMARY ===\n")
cat("Skill: tidyverse\n")
cat("Tests run:", test_count, "\n")
cat("Tests passed:", pass_count, "\n")
stopifnot(test_count == pass_count)
cat("All tests PASSED\n")


# =============================================================================


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-07 15:18:42
# Command: Rscript /daaf/scripts/smoke_tests/smoke_tidyverse_a.R
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
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
# Attaching package: ‘lubridate’
# 
# The following objects are masked from ‘package:base’:
# 
#     date, intersect, setdiff, union
# 
# 
# Attaching package: ‘arrow’
# 
# The following object is masked from ‘package:lubridate’:
# 
#     duration
# 
# The following object is masked from ‘package:utils’:
# 
#     timestamp
# 
# 
# Attaching package: ‘data.table’
# 
# The following objects are masked from ‘package:lubridate’:
# 
#     hour, isoweek, isoyear, mday, minute, month, quarter, second, wday,
#     week, yday, year
# 
# The following object is masked from ‘package:purrr’:
# 
#     transpose
# 
# The following objects are masked from ‘package:dplyr’:
# 
#     between, first, last
# 
# === VERSION CHECK ===
# dplyr : installed = 1.2.1 , expected = 1.2.1 
# tidyr : installed = 1.3.2 , expected = 1.3.2 
# readr : installed = 2.2.0 , expected = 2.2.0 
# purrr : installed = 1.2.2 , expected = 1.2.2 
# stringr : installed = 1.6.0 , expected = 1.6.0 
# forcats : installed = 1.0.1 , expected = 1.0.1 
# lubridate : installed = 1.9.5 , expected = 1.9.5 
# data.table : installed = 1.18.2.1 , expected = 1.18.2.1 
# arrow : installed = 23.0.1.2 , expected = 23.0.1.2 
# R version:4.5.3
# PASS: Versions aligned
# 
# === CORE API TESTS ===
# PASS: filter() + select() + mutate() pipeline
# PASS: group_by() + summarize()
# PASS: pivot_longer() + pivot_wider()
# PASS: left_join() + anti_join()
# 
# === INTEGRATION TESTS ===
# [1] TRUE
# PASS: arrow::read_parquet() + arrow::write_parquet() round-trip
# PASS: Native pipe |> works
# Warning message:
# The `file` argument of `read_csv()` should use `I()` for literal data as of
# readr 2.2.0.
#   
#   # Bad (for example):
#   read_csv("x,y\n1,2")
#   
#   # Good:
#   read_csv(I("x,y\n1,2")) 
# PASS: readr::read_csv() on inline data
# PASS: stringr::str_detect() + str_replace() + str_pad()
# PASS: lubridate::ymd() + date arithmetic
# PASS: data.table DT[i, j, by] + := operations
# 
# === SMOKE TEST SUMMARY ===
# Skill: tidyverse
# Tests run: 11 
# Tests passed: 11 
# All tests PASSED
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
