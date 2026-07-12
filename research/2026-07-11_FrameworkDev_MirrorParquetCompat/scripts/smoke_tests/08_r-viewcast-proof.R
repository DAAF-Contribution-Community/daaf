# Proof that the view-safe cast actually FIRED on saipe.district_name, plus a
# digest-sensitivity self-test.
#
# WHY: the whole-column digest MATCH (script 07) only proves equivalence if the
#   view-safe path genuinely exercised the string_view->utf8 cast. If R had somehow
#   read district_name as plain utf8 without casting, the test would be measuring
#   the wrong thing. Here we (a) show the RAW arrow schema declares string_view for
#   district_name and NOT for meps, and (b) confirm the naive read (as_data_frame
#   =TRUE) FAILS on saipe — establishing the fix is load-bearing. Then (c) a digest
#   self-test: mangle one character and show the digest changes (guards against a
#   vacuous MATCH).

# --- Config ---
library(arrow)
library(digest)
Sys.setlocale("LC_COLLATE", "C")

scratch <- "/daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch"

# --- (a) raw schema: which columns are string_view? ---
cat("### RAW arrow schema view-type scan (before any cast)\n")
for (f in c("saipe_districts_FAILING.parquet", "meps_schools_WORKING.parquet",
            "edfacts_grad_rates_2018.parquet", "crdc_discipline_2017.parquet")) {
  tbl <- arrow::read_parquet(file.path(scratch, f), as_data_frame = FALSE)
  sch <- tbl$schema
  views <- character(0)
  for (i in seq_len(length(sch$names))) {
    fld <- sch$field(i - 1L)
    ts <- fld$type$ToString()
    if (grepl("view", ts, fixed = TRUE)) views <- c(views, paste0(fld$name, ":", ts))
  }
  cat(sprintf("  %-40s view_cols=%s\n", f, if (length(views)) paste(views, collapse=", ") else "(none)"))
}

# --- (b) naive read FAILS on saipe (proving the fix is load-bearing) ---
cat("\n### Naive read (as_data_frame=TRUE) on the view-typed file\n")
naive <- tryCatch({
  df <- arrow::read_parquet(file.path(scratch, "saipe_districts_FAILING.parquet"))
  "UNEXPECTED SUCCESS — file may not actually carry a view type"
}, error = function(e) paste0("FAILED as expected: ", conditionMessage(e)))
cat("  saipe naive read:", naive, "\n")

# confirm the view-safe read succeeds and returns character
tbl <- arrow::read_parquet(file.path(scratch, "saipe_districts_FAILING.parquet"), as_data_frame = FALSE)
sch <- tbl$schema
fields <- lapply(seq_len(length(sch$names)), function(i) {
  fld <- sch$field(i - 1L)
  ts <- fld$type$ToString()
  nt <- if (grepl("large_string_view", ts, fixed=TRUE)) arrow::large_utf8()
    else if (grepl("string_view", ts, fixed=TRUE)) arrow::utf8()
    else if (grepl("binary_view", ts, fixed=TRUE)) arrow::binary()
    else fld$type
  arrow::field(fld$name, nt)
})
df <- as.data.frame(tbl$cast(arrow::schema(fields)))
cat("  view-safe read class(district_name):", class(df$district_name), "\n")
cat("  view-safe read succeeded; nrow:", nrow(df), "\n")

# --- (c) digest sensitivity self-test ---
cat("\n### Digest sensitivity self-test (must DIFFER when one char changes)\n")
mk_digest <- function(vals) {
  f <- factor(vals); lv <- levels(f); ct <- tabulate(as.integer(f), nbins=length(lv))
  ord <- order(lv); lv <- lv[ord]; ct <- ct[ord]
  rc <- rawConnection(raw(0), "w"); on.exit(close(rc))
  for (i in seq_along(lv)) {
    writeBin(charToRaw(enc2utf8(lv[i])), rc); writeBin(as.raw(0x01), rc)
    writeBin(charToRaw(as.character(ct[i])), rc); writeBin(as.raw(0x02), rc)
  }
  digest::digest(rawConnectionValue(rc), algo="sha256", serialize=FALSE)
}
base_vals <- c("Cañon City", "Española", "Plain District")
d1 <- mk_digest(base_vals)
# mangle ñ (U+00F1) -> n in one value
mangled <- c("Canon City", "Española", "Plain District")
d2 <- mk_digest(mangled)
cat("  original digest:", substr(d1,1,20), "\n")
cat("  mangled  digest:", substr(d2,1,20), "\n")
cat("  self-test:", if (d1 != d2) "PASS (digest is sensitive to a single-codepoint change)" else "FAIL (vacuous)", "\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 19:34:45
# Command: Rscript /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/smoke_tests/08_r-viewcast-proof.R
# Duration: 1s
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
# [1] "C"
# ### RAW arrow schema view-type scan (before any cast)
#   saipe_districts_FAILING.parquet          view_cols=district_name:string_view
#   meps_schools_WORKING.parquet             view_cols=(none)
#   edfacts_grad_rates_2018.parquet          view_cols=school_name:string_view, lea_name:string_view
#   crdc_discipline_2017.parquet             view_cols=(none)
# 
# ### Naive read (as_data_frame=TRUE) on the view-typed file
#   saipe naive read: FAILED as expected: cannot handle Array of type <utf8_view> 
#   view-safe read class(district_name): character 
#   view-safe read succeeded; nrow: 368967 
# 
# ### Digest sensitivity self-test (must DIFFER when one char changes)
#   original digest: e6ed3b0b627e5c050ef9 
#   mangled  digest: 7d8c1a091053204a5d4e 
#   self-test: PASS (digest is sensitive to a single-codepoint change) 
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
