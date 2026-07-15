# scripts/scratch/xval_svy_r_00_probe.R
# INTENT: probe R-side package availability before committing to a comparison design.
# REASONING: the cross-validation plan branches on which R packages exist —
#   survey (Lumley) is the reference comparator; arrow is required to read the
#   shared parquet frame; marginaleffects is the PREFERRED margins comparator but
#   we fall back to a manual AME if it is absent; broom tidies svyglm output.
# ASSUMES: base R + these packages may or may not be installed; installed.packages()
#   is the authoritative check (Rscript -e is hook-blocked, so this runs as a file).

# --- Config ---
pkgs <- c("survey", "arrow", "marginaleffects", "broom", "dplyr")

# --- Probe ---
ip <- rownames(installed.packages())
cat("=== R package availability probe ===\n")
for (p in pkgs) {
  present <- p %in% ip
  ver <- if (present) as.character(packageVersion(p)) else "ABSENT"
  cat(sprintf("  %-18s %s\n", p, ver))
}

# --- Summary: R + survey versions verbatim ---
cat("\nR version: ", R.version.string, "\n", sep = "")
if ("survey" %in% ip) {
  cat("survey version: ", as.character(packageVersion("survey")), "\n", sep = "")
}
cat("PROBE COMPLETE\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-15 11:50:22
# Command: Rscript /daaf/scripts/scratch/xval_svy_r_00_probe.R
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# === R package availability probe ===
#   survey             4.5
#   arrow              23.0.1.2
#   marginaleffects    0.32.0
#   broom              1.0.12
#   dplyr              1.2.1
# 
# R version: R version 4.5.3 (2026-03-11)
# survey version: 4.5
# PROBE COMPLETE
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
