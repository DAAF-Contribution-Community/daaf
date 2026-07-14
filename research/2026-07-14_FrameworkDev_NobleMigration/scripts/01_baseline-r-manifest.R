# --- Config ---
# INTENT: Capture baseline R package manifest for the current bookworm x86_64 image
#         before the Noble migration. This artifact is the "before" half of the
#         version-drift manifest diff described in §6.2 of the Noble Migration
#         Scoping Guide.
# REASONING: We must record exact Package/Version/Built fields so a post-migration
#             image can be anti-joined against this file to surface every version delta.
#             The `channel` column identifies the source image for the diff join.
# ASSUMES: Running inside the bookworm x86_64 DAAF container.
#          `arrow` is installed and writable output dir can be created.

library(arrow)

PROJECT_DIR <- "/daaf/research/2026-07-14_FrameworkDev_NobleMigration"
OUTPUT_DIR  <- file.path(PROJECT_DIR, "output")
OUTPUT_PATH <- file.path(OUTPUT_DIR,
  "2026-07-14_baseline_bookworm-x86_r-packages.parquet")

# INTENT: Create output directory if it does not already exist.
# REASONING: The project was initialised without an output/ folder; creating it
#             here keeps the script self-contained without requiring a pre-run
#             manual step.
dir.create(OUTPUT_DIR, recursive = TRUE, showWarnings = FALSE)

# --- Load ---
# INTENT: Pull the full installed-package matrix from R's package database.
# REASONING: installed.packages() is the authoritative in-process inventory;
#             only columns Package/Version/Built are needed for the drift diff.
# ASSUMES: All currently installed packages are accessible via .libPaths().
pkgs_raw <- installed.packages()[, c("Package", "Version", "Built")]

# Convert matrix to data.frame so we can add a column and coerce to tibble/arrow.
pkgs_df <- as.data.frame(pkgs_raw, stringsAsFactors = FALSE)

cat("Loaded: ", nrow(pkgs_df), "packages from installed.packages()\n")

# --- Transform ---
# INTENT: Add a `channel` column recording the source image identifier.
# REASONING: When the noble manifest is captured the same way with
#             channel = "noble-amd64" (or "noble-arm64"), a simple anti-join on
#             (Package, channel) reveals additions/removals; an inner-join diff on
#             Version reveals upgrades.
pkgs_df$channel <- "bookworm-x86_64"

cat("Shape: ", nrow(pkgs_df), "rows x", ncol(pkgs_df), "cols\n")
cat("Columns:", paste(names(pkgs_df), collapse = ", "), "\n")

# --- Validate ---
# INTENT: Assert minimum count and presence of key native-linkage packages.
# REASONING: §6.2 names arrow, sf, terra, V8, fixest, xgboost, lightgbm as
#             golden-diff anchors because they require system-library linkage;
#             if any are absent the baseline is incomplete and the diff will be
#             misleading.
# ASSUMES: All 7 packages are installed in this image.
n_pkgs <- nrow(pkgs_df)
cat("\n--- Validation ---\n")
cat("Package count:", n_pkgs, "\n")

stopifnot(
  "Package count must be >= 65" = n_pkgs >= 65
)
cat("[PASS] Row count >=65\n")

key_packages <- c("arrow", "sf", "terra", "V8", "fixest", "xgboost", "lightgbm")
present <- key_packages %in% pkgs_df$Package
names(present) <- key_packages
cat("Key native-linkage packages:\n")
print(present)
stopifnot(
  "All key native-linkage packages must be present" = all(present)
)
cat("[PASS] All key packages present\n")

# INTENT: Print versions of golden-diff anchor packages for the execution log.
# REASONING: §6.2 explicitly names sf/GDAL/PROJ version lines from smoke_sf_terra.R
#             as a "golden diff target". Printing arrow/sf/fixest versions here
#             provides an equivalent anchor directly in this script's capture log
#             without requiring the smoke runner.
cat("\n--- Golden-diff anchor versions ---\n")
for (pkg in c("arrow", "sf", "fixest")) {
  ver <- pkgs_df$Version[pkgs_df$Package == pkg]
  cat(pkg, ":", ver, "\n")
}

# --- Save ---
# INTENT: Write manifest to parquet per DAAF parquet-only convention.
# REASONING: Parquet preserves column types, is diffable via polars/arrow anti-join
#            in the migration session's analysis scripts, and matches the format
#            expected by the post-migration diff step (§6.2).
arrow::write_parquet(pkgs_df, OUTPUT_PATH)
cat("\nSaved to:", OUTPUT_PATH, "\n")
cat("Final shape:", nrow(pkgs_df), "rows x", ncol(pkgs_df), "cols\n")

# CP1 summary line (manifest capture — analogous to fetch checkpoint)
cat("\n[CP1 PASSED] R package manifest captured:",
    nrow(pkgs_df), "packages, channel=bookworm-x86_64\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-14 17:48:58
# Command: Rscript /daaf/research/2026-07-14_FrameworkDev_NobleMigration/scripts/01_baseline-r-manifest.R
# Duration: 0s
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
# Loaded:  304 packages from installed.packages()
# Shape:  304 rows x 4 cols
# Columns: Package, Version, Built, channel 
# 
# --- Validation ---
# Package count: 304 
# [PASS] Row count >=65
# Key native-linkage packages:
#    arrow       sf    terra       V8   fixest  xgboost lightgbm 
#     TRUE     TRUE     TRUE     TRUE     TRUE     TRUE     TRUE 
# [PASS] All key packages present
# 
# --- Golden-diff anchor versions ---
# arrow : 23.0.1.2 
# sf : 1.1-0 
# fixest : 0.14.0 
# 
# Saved to: /daaf/research/2026-07-14_FrameworkDev_NobleMigration/output/2026-07-14_baseline_bookworm-x86_r-packages.parquet 
# Final shape: 304 rows x 4 cols
# 
# [CP1 PASSED] R package manifest captured: 304 packages, channel=bookworm-x86_64
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
