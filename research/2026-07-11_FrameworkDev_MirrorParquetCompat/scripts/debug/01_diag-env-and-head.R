# --- Config ---
# INTENT: Establish load-bearing facts for the HuggingFace large-file truncation
#   diagnosis WITHOUT downloading the full 224MB file. Three probes:
#     (A) environment facts: arrow/httr2/curl versions + getOption("timeout")
#     (B) H2 probe: HEAD request for Content-Length + server/CDN headers
#     (C) throughput probe: a CAPPED ranged GET (first ~20MB) timed, to compute
#         implied full-file transfer time vs. R's 60s default timeout (H1).
# REASONING: The execution log already quotes the failing warning
#   `In download.file(file, tf, quiet = TRUE, mode = "wb"): downloaded length
#   103688378 != reported length 224216539`. That proves arrow's URL path
#   delegates to download.file(). This script quantifies WHY it truncated.
# ASSUMES: httr2 + curl installed; network egress to huggingface.co CDN allowed.
# STAGE: debug (Framework Development diagnostic)

library(httr2)
library(curl)

URL <- "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/ccd/schools_ccd_directory.parquet"

# --- (A) Environment facts ---
cat("=== (A) ENVIRONMENT FACTS ===\n")
cat("arrow  :", as.character(packageVersion("arrow")), "\n")
cat("httr2  :", as.character(packageVersion("httr2")), "\n")
cat("curl   :", as.character(packageVersion("curl")), "\n")
cat("R       :", R.version.string, "\n")
# REASONING (H1): download.file() honors getOption("timeout") (default 60s).
#   If unset by the script, a 224MB transfer that runs past 60s is killed mid-stream.
cat("getOption('timeout') :", getOption("timeout"), "seconds\n")

# --- (B) H2 probe: HEAD request for size + CDN headers ---
# INTENT: Confirm reported content length and see which server/CDN serves the file
#   after the resolve redirect (HF Xet bridge per the failing log's URL).
cat("\n=== (B) HEAD REQUEST (follow redirects) ===\n")
head_resp <- tryCatch(
  request(URL) |>
    req_method("HEAD") |>
    req_timeout(60) |>
    req_perform(),
  error = function(e) { cat("HEAD failed:", conditionMessage(e), "\n"); NULL }
)
if (!is.null(head_resp)) {
  cat("Final URL :", head_resp$url, "\n")
  cat("Status    :", resp_status(head_resp), "\n")
  hdrs <- resp_headers(head_resp)
  for (h in c("content-length", "content-type", "accept-ranges",
              "server", "x-cache", "via", "content-disposition")) {
    v <- hdrs[[h]]
    if (!is.null(v)) cat(sprintf("  %-20s: %s\n", h, v))
  }
  cl <- suppressWarnings(as.numeric(hdrs[["content-length"]]))
  if (!is.na(cl)) cat(sprintf("Reported size: %.1f MB\n", cl / 1024^2))
}

# --- (C) Throughput probe: CAPPED ranged GET of first ~20MB ---
# INTENT: Measure real throughput to this CDN and extrapolate full-file time.
# REASONING: If (full_size / throughput) > 60s, R's default timeout is the killer
#   (H1 CONFIRMED). A ranged request avoids pulling the whole 224MB.
# ASSUMES: server honors HTTP Range (accept-ranges: bytes from probe B).
cat("\n=== (C) THROUGHPUT PROBE: first 20MB via Range header ===\n")
CAP_BYTES <- 20 * 1024^2  # 20 MB cap
t0 <- Sys.time()
range_resp <- tryCatch(
  request(URL) |>
    req_headers(Range = sprintf("bytes=0-%d", CAP_BYTES - 1L)) |>
    req_timeout(120) |>
    req_perform(),
  error = function(e) { cat("Range GET failed:", conditionMessage(e), "\n"); NULL }
)
if (!is.null(range_resp)) {
  elapsed <- as.numeric(difftime(Sys.time(), t0, units = "secs"))
  body_len <- length(resp_body_raw(range_resp))
  cat("Range status   :", resp_status(range_resp), "(206 = partial content)\n")
  cat(sprintf("Bytes received : %.1f MB\n", body_len / 1024^2))
  cat(sprintf("Elapsed        : %.2f s\n", elapsed))
  thr <- (body_len / 1024^2) / elapsed
  cat(sprintf("Throughput     : %.2f MB/s\n", thr))
  # Extrapolate full 224.2MB transfer time
  full_mb <- 224216539 / 1024^2
  est_full <- full_mb / thr
  cat(sprintf("Est. full-file transfer time (%.1f MB @ %.2f MB/s): %.1f s\n",
              full_mb, thr, est_full))
  # H1 verdict: 103.7MB was actually received before truncation
  got_mb <- 103688378 / 1024^2
  cat(sprintf("Log truncated at %.1f MB. At %.2f MB/s that is ~%.0f s of transfer.\n",
              got_mb, thr, got_mb / thr))
  if (est_full > 60) {
    cat("[H1 SUPPORTED] Full transfer exceeds 60s default timeout.\n")
  } else {
    cat("[H1 REFUTED?] Full transfer under 60s at this throughput.\n")
  }
}

cat("\n--- Diagnostic 01 complete ---\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 19:25:10
# Command: Rscript /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/debug/01_diag-env-and-head.R
# Duration: 15s
# Exit code: 0
#
# --- STDOUT ---
# Using libcurl 7.88.1 with OpenSSL/3.0.20
# === (A) ENVIRONMENT FACTS ===
# arrow  : 23.0.1.2 
# httr2  : 1.2.2 
# curl   : 7.0.0 
# R       : R version 4.5.3 (2026-03-11) 
# getOption('timeout') : 60 seconds
# 
# === (B) HEAD REQUEST (follow redirects) ===
# Final URL : https://us.aws.cdn.hf.co/xet-bridge-us/69894bd6e143f25e928d44de/008a67ac5b012814896edb0c0c52586c9e9ff9f2cab3a67e54881d82dc47f364?X-Xet-Cas-Uid=public&response-content-disposition=inline%3B+filename*%3DUTF-8%27%27schools_ccd_directory.parquet%3B+filename%3D%22schools_ccd_directory.parquet%22%3B&user_id=public&Expires=1783801510&Policy=eyJTdGF0ZW1lbnQiOlt7IlJlc291cmNlIjoiaHR0cHM6Ly91cy5hd3MuY2RuLmhmLmNvL3hldC1icmlkZ2UtdXMvNjk4OTRiZDZlMTQzZjI1ZTkyOGQ0NGRlLzAwOGE2N2FjNWIwMTI4MTQ4OTZlZGIwYzBjNTI1ODZjOWU5ZmY5ZjJjYWIzYTY3ZTU0ODgxZDgyZGM0N2YzNjRcXD9YLVhldC1DYXMtVWlkPXB1YmxpYyZyZXNwb25zZS1jb250ZW50LWRpc3Bvc2l0aW9uPWlubGluZSUzQitmaWxlbmFtZSUyQSUzRFVURi04JTI3JTI3c2Nob29sc19jY2RfZGlyZWN0b3J5LnBhcnF1ZXQlM0IrZmlsZW5hbWUlM0QlMjJzY2hvb2xzX2NjZF9kaXJlY3RvcnkucGFycXVldCUyMiUzQiZ1c2VyX2lkPXB1YmxpYyIsIkNvbmRpdGlvbiI6eyJEYXRlTGVzc1RoYW4iOnsiRXBvY2hUaW1lIjoxNzgzODAxNTEwfX19XX0_&Signature=MEQCIGKejV27oj9y-sE4KL-bc7xZnHaoRvVexaM9ra9nCnd0AiBcbzZa4EOhwYvLUWZQg5z%7EwsJx1uUKt6z65WyvTknTkw__&Key-Pair-Id=01KAYHXK2CBJSW0YZTMNXK9W1M 
# Status    : 200 
#   content-length      : 224216539
#   content-type        : application/octet-stream
#   accept-ranges       : bytes
#   content-disposition : inline; filename*=UTF-8''schools_ccd_directory.parquet; filename="schools_ccd_directory.parquet";
# Reported size: 213.8 MB
# 
# === (C) THROUGHPUT PROBE: first 20MB via Range header ===
# Range status   : 206 (206 = partial content)
# Bytes received : 20.0 MB
# Elapsed        : 14.29 s
# Throughput     : 1.40 MB/s
# Est. full-file transfer time (213.8 MB @ 1.40 MB/s): 152.8 s
# Log truncated at 98.9 MB. At 1.40 MB/s that is ~71 s of transfer.
# [H1 SUPPORTED] Full transfer exceeds 60s default timeout.
# 
# --- Diagnostic 01 complete ---
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
