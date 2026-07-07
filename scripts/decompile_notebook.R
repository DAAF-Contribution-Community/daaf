#!/usr/bin/env Rscript
# =============================================================================
# Decompile a DAAF Quarto (.qmd) notebook into individual R script files.
#
# This is the R-mode counterpart to decompile_notebook.py (the marimo
# decompiler). It parses a DAAF Stage 9 Quarto notebook (assembled per
# .claude/skills/quarto/references/daaf-notebook.md) and extracts each
# executed script back into a standalone .R file with its execution log
# appended — a faithful reconstruction of the original executed script file
# as it existed before notebook assembly.
#
# The .qmd assembly format this inverts (see daaf-notebook.md):
#   - Each script lives in an ```{r} ... ``` chunk whose first content line is
#         # --- VERBATIM COPY of scripts/<stage_dir>/<name>.R ---
#     followed by the exact (un-commented) script body.
#   - The execution log follows in a Quarto callout block (PRIMARY format the
#     notebook-assembler emits):
#         ::: {.callout-note collapse="true" title="Execution Log"}
#         ```
#         <stdout/stderr text>
#         ```
#         :::
#     For backward compatibility with older notebooks, a legacy <details> block
#     is still recognized as a FALLBACK:
#         <details>
#         <summary>Execution Log</summary>
#         ```
#         <stdout/stderr text>
#         ```
#         </details>
#   - Data-inspection chunks (arrow::read_parquet(...) |> glimpse()/head(...))
#     carry `#| eval: true` and no VERBATIM COPY marker — they are NOT scripts
#     and are skipped.
#
# The "# --- VERBATIM COPY of scripts/<path> ---" marker is the SINGLE contract
# for script identification: chunks without it are not scripts and are skipped.
# Narrative lines ("Source:", "**Script:**") are display-only and deliberately
# NOT used as extraction anchors. The narrative "**Output:**" line IS captured,
# but only as manifest metadata (the "Original Output" column), never as an
# extraction anchor.
#
# Unlike the marimo format, R chunk code is stored VERBATIM (not comment-
# prefixed), so there is no un-commenting step — the VERBATIM COPY marker line
# is stripped and everything else in the chunk is the code.
#
# After extraction, a cross-chunk variable reference validation pass runs via
# codetools::findGlobals() (the R analogue of the Python version's ast pass).
# Scripts that reference variables never assigned within them are flagged with
# warnings in stdout and a "Dangling Reference Warnings" section in MANIFEST.md.
#
# Usage:
#     Rscript decompile_notebook.R <notebook_path> <output_dir>
#
# Example:
#     Rscript scripts/decompile_notebook.R \
#         research/2026-02-15_.../2026-02-15_...Analysis.qmd \
#         research/2026-03-24_.../original_files/scripts
#
# Output:
#     One .R file per script, organized into stage subdirectories matching the
#     original layout (e.g. output_dir/stage5_fetch/01_fetch-source.R), plus a
#     MANIFEST.md summarizing what was extracted.
#
# Framework-utility exception: this is a standalone CLI tool (stdout reporting,
# not an audit artifact) whitelisted by enforce-file-first.sh for /daaf/scripts/
# paths — it may be run directly with Rscript. commandArgs argument handling is
# used per the standalone-CLI-tool exception to the sequential-script style.
# =============================================================================

# --- Config ---
args <- commandArgs(trailingOnly = TRUE)

if (length(args) != 2) {
  cat("Usage: Rscript decompile_notebook.R <notebook_path> <output_dir>\n")
  cat("\n")
  cat("Example:\n")
  cat("  Rscript scripts/decompile_notebook.R \\\n")
  cat("    research/2026-02-15_.../2026-02-15_...Analysis.qmd \\\n")
  cat("    research/2026-03-24_.../original_files/scripts\n")
  quit(status = 1)
}

notebook_path <- args[1]
output_dir <- args[2]

if (!file.exists(notebook_path)) {
  cat(sprintf("Error: Notebook not found: %s\n", notebook_path))
  quit(status = 1)
}

cat(sprintf("Decompiling: %s\n", notebook_path))
cat(sprintf("Output dir:  %s\n", output_dir))
cat("\n")

# --- Load ---
# Read the notebook as raw lines. Line-oriented scanning is more robust than a
# single-regex sweep for the interleaved chunk / <details> structure of a .qmd.
nb_lines <- readLines(notebook_path, warn = FALSE)

# --- Parse: walk the notebook line by line ---
# State machine over the regions of interest:
#   in_chunk       — inside a ```{r ...} ... ``` fenced code chunk
#   in_log_block   — inside an Execution Log container, either the PRIMARY
#                    ::: {.callout-note ...} callout or the FALLBACK <details>
#   in_log_fence   — inside the ``` ... ``` fence nested in that container
#
# The opening R-chunk fence matches ```{r} or ```{r, opts} or ```{r label}.
# A plain ``` (no {r}) opens the execution-log fence when we are already inside
# an Execution Log container.
#
# Execution Log container recognition:
#   PRIMARY  — a callout div fence `::: {.callout-... title="Execution Log" ...}`
#              (or with `.callout-note`/other callout class) opens the container;
#              a bare `:::` closes it. The "Execution Log" title marks it as a log.
#   FALLBACK — a <details> whose <summary> contains "Execution Log"; </details>
#              closes it. Kept for older notebooks assembled before the callout
#              format (see daaf-notebook.md history).

# Anchor that identifies a script chunk and carries its source path.
# Example: "# --- VERBATIM COPY of scripts/stage5_fetch/01_fetch-source.R ---"
verbatim_re <- "^\\s*#\\s*---\\s*VERBATIM COPY of scripts/(.+?)\\s*---\\s*$"

# Header-metadata anchor: the narrative "**Output:**" line the assembler emits
# above each script chunk. Captured ONLY for the MANIFEST "Original Output"
# column (mirrors extract_header_metadata() in decompile_notebook.py) — never
# used as an extraction anchor.
# Example: "**Output:** `data/raw/2026-01-24_ccd_schools.parquet`"
output_re <- "^\\s*\\*\\*Output:\\*\\*\\s*`(.+?)`\\s*$"

scripts_extracted <- list()   # each: list(source_path, code, log_text)

in_chunk <- FALSE
chunk_lines <- character(0)

in_log_block <- FALSE         # inside an exec-log container (callout or details)
saw_exec_summary <- FALSE     # container is confirmed an "Execution Log" block
log_block_kind <- NA_character_  # "callout" or "details" — controls the closer
in_log_fence <- FALSE         # inside the ``` fence within the exec-log block
log_lines <- character(0)

# Track the most recent "**Output:**" narrative path; attached to the next
# script chunk as manifest metadata.
pending_output <- NA_character_

# When a script chunk closes, we stash it here awaiting its (optional) log,
# which appears in the next Execution Log <details> block before the next chunk.
pending_script <- NULL

flush_pending_script <- function(pending, log_text) {
  # Attach any captured log text and append to the global results list.
  pending$log_text <- log_text
  scripts_extracted[[length(scripts_extracted) + 1]] <<- pending
}

i <- 1
n <- length(nb_lines)
while (i <= n) {
  line <- nb_lines[i]

  # --- Chunk boundary detection ---
  if (!in_chunk && grepl("^```\\{[rR]([ ,}].*)?$", line)) {
    # Opening an R code chunk.
    in_chunk <- TRUE
    chunk_lines <- character(0)
    i <- i + 1
    next
  }

  if (in_chunk) {
    if (grepl("^```\\s*$", line)) {
      # Closing the R chunk. Decide whether it is a script chunk.
      in_chunk <- FALSE

      # Find the VERBATIM COPY marker to get the source path + body start.
      marker_idx <- which(grepl(verbatim_re, chunk_lines))
      if (length(marker_idx) >= 1) {
        mi <- marker_idx[1]
        src <- sub(verbatim_re, "\\1", chunk_lines[mi])

        # Code is everything AFTER the marker line. Chunk-option lines (#| ...)
        # precede the marker and are notebook scaffolding, not script code.
        body <- if (mi < length(chunk_lines)) {
          chunk_lines[(mi + 1):length(chunk_lines)]
        } else {
          character(0)
        }
        # Trim leading blank lines that separated the marker from the code.
        while (length(body) > 0 && grepl("^\\s*$", body[1])) {
          body <- body[-1]
        }

        # If a previous script chunk is still pending (no log appeared before
        # this next script chunk), flush it with an empty log first.
        if (!is.null(pending_script)) {
          flush_pending_script(pending_script, "")
          pending_script <<- NULL
        }

        pending_script <<- list(
          source_path = src,
          code = paste(body, collapse = "\n"),
          log_text = "",
          original_output = pending_output
        )
        pending_output <<- NA_character_
      }
      # Non-script chunks (data inspection, etc.) are simply dropped.
      chunk_lines <- character(0)
      i <- i + 1
      next
    }
    # Accumulate chunk body lines.
    chunk_lines <- c(chunk_lines, line)
    i <- i + 1
    next
  }

  # --- Narrative **Output:** line (header-metadata capture for the manifest) ---
  if (grepl(output_re, line)) {
    pending_output <- sub(output_re, "\\1", line)
  }

  # --- Execution Log container detection ---
  # PRIMARY: a Quarto callout div fence. A callout opener is a line that both
  # opens a fenced div (`::: {...}`) and declares a callout class
  # (`.callout-note`, `.callout-...`). We treat a callout as an Execution Log
  # container when its attributes carry the "Execution Log" title.
  if (!in_log_block &&
      grepl("^\\s*:::+\\s*\\{[^}]*\\.callout", line)) {
    in_log_block <- TRUE
    log_block_kind <- "callout"
    saw_exec_summary <- grepl("Execution Log", line, ignore.case = TRUE)
    in_log_fence <- FALSE
    log_lines <- character(0)
    i <- i + 1
    next
  }

  # FALLBACK: legacy <details> block (older notebooks).
  if (!in_log_block && grepl("^\\s*<details>\\s*$", line)) {
    in_log_block <- TRUE
    log_block_kind <- "details"
    saw_exec_summary <- FALSE
    in_log_fence <- FALSE
    log_lines <- character(0)
    i <- i + 1
    next
  }

  if (in_log_block) {
    # <details> confirms the log via its <summary>; callouts confirm via title.
    if (identical(log_block_kind, "details") &&
        grepl("<summary>.*Execution Log.*</summary>", line, ignore.case = TRUE)) {
      saw_exec_summary <- TRUE
      i <- i + 1
      next
    }
    if (!in_log_fence && grepl("^```\\s*$", line)) {
      # Opening the plain fenced block that holds the log text.
      in_log_fence <- TRUE
      i <- i + 1
      next
    }
    if (in_log_fence && grepl("^```\\s*$", line)) {
      # Closing the log fence.
      in_log_fence <- FALSE
      i <- i + 1
      next
    }
    if (in_log_fence) {
      log_lines <- c(log_lines, line)
      i <- i + 1
      next
    }
    # Container closer: bare `:::` for a callout, </details> for the fallback.
    is_callout_close <- identical(log_block_kind, "callout") &&
      grepl("^\\s*:::+\\s*$", line)
    is_details_close <- identical(log_block_kind, "details") &&
      grepl("^\\s*</details>\\s*$", line)
    if (is_callout_close || is_details_close) {
      # Closing the container. If it was an Execution Log block and a script
      # is pending, attach the captured log to it.
      in_log_block <- FALSE
      if (saw_exec_summary && !is.null(pending_script)) {
        flush_pending_script(pending_script, paste(log_lines, collapse = "\n"))
        pending_script <<- NULL
      }
      saw_exec_summary <- FALSE
      log_block_kind <- NA_character_
      log_lines <- character(0)
      i <- i + 1
      next
    }
    i <- i + 1
    next
  }

  i <- i + 1
}

# Flush any final pending script that had no trailing execution-log block.
if (!is.null(pending_script)) {
  flush_pending_script(pending_script, "")
  pending_script <- NULL
}

cat(sprintf("Found %d script chunk(s)\n", length(scripts_extracted)))
cat("\n")

# --- Reconstruct each script (code + commented execution log) ---
# Mirrors reconstruct_script() in decompile_notebook.py: verbatim code, blank
# separation, then the execution log re-commented with a single "# " prefix and
# a guaranteed "# EXECUTION LOG" header. run_with_capture.sh checks for
# "^# EXECUTION LOG" before allowing re-execution, and RV-2's stripping step
# looks for this marker to remove the log before re-running.

reconstruct_script <- function(code, log_text) {
  log_lines <- strsplit(log_text, "\n", fixed = TRUE)[[1]]
  if (length(log_lines) == 0) log_lines <- character(0)

  # Detect whether the stored log is already comment-prefixed. The known
  # assembler stores plain (un-commented) log text, but handle both defensively
  # to avoid double-commenting (# # EXECUTION LOG).
  is_precommented <- FALSE
  for (ln in head(log_lines, 10)) {
    s <- trimws(ln)
    if (s %in% c("# EXECUTION LOG", "# ====", "# =====")) {
      is_precommented <- TRUE
      break
    }
    if (grepl("^# =", s) && grepl("==========", s)) {
      is_precommented <- TRUE
      break
    }
  }

  if (is_precommented) {
    cleaned <- vapply(log_lines, function(ln) {
      if (startsWith(ln, "# ")) substring(ln, 3)
      else if (identical(ln, "#")) ""
      else ln
    }, character(1), USE.NAMES = FALSE)
  } else {
    cleaned <- log_lines
  }

  commented <- vapply(cleaned, function(ln) {
    if (nzchar(ln)) paste0("# ", ln) else "#"
  }, character(1), USE.NAMES = FALSE)
  commented_log <- paste(commented, collapse = "\n")

  script <- sub("[ \t\r\n]+$", "", code)   # rstrip trailing whitespace
  script <- paste0(script, "\n\n\n")

  if (!grepl("# EXECUTION LOG", commented_log)) {
    script <- paste0(
      script,
      "# =============================================================================\n",
      "# EXECUTION LOG\n",
      "# =============================================================================\n"
    )
  }
  script <- paste0(script, commented_log, "\n")
  script
}

# --- Write scripts + build manifest ---
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

manifest_rows <- list()
for (s in scripts_extracted) {
  src <- s$source_path
  code <- s$code
  log_text <- s$log_text

  script_content <- reconstruct_script(code, log_text)

  out_path <- file.path(output_dir, src)
  dir.create(dirname(out_path), recursive = TRUE, showWarnings = FALSE)
  writeLines(script_content, out_path, sep = "")

  stage_dir <- if (grepl("/", src)) dirname(src) else "—"
  code_lines <- length(strsplit(code, "\n", fixed = TRUE)[[1]])
  has_log <- nzchar(trimws(log_text))
  original_output <- s$original_output
  if (is.null(original_output) || is.na(original_output)) original_output <- "—"

  manifest_rows[[length(manifest_rows) + 1]] <- list(
    source_path = src,
    stage = stage_dir,
    original_output = original_output,
    code_lines = code_lines,
    has_log = has_log
  )
  cat(sprintf("  -> %s (%d code lines, log: %s)\n",
              src, code_lines, if (has_log) "yes" else "no"))
}

# --- Validate cross-chunk references ---
# Mirrors validate_references() in decompile_notebook.py. R has no ast module;
# codetools::findGlobals() on a function wrapper yields the same signal: free
# variables the code reads but never assigns. Function NAMES are excluded
# (merge = FALSE, $variables only) so every library call does not appear as
# noise; base constants are filtered below. eval() of the parsed
# `function() {...}` wrapper only BUILDS the closure — the body is not run.
# KNOWN LIMITATION: column names used inside tidyverse NSE verbs (mutate,
# filter, summarise, ggplot aes, ...) are not statically resolvable and appear
# as false positives. Warnings are review prompts, not errors — deliberately
# conservative, mirroring the Python version's stance.
cat("\n")
KNOWN_SAFE <- c("T", "F", "pi", "letters", "LETTERS", "month.name",
                "month.abb", ".Machine")

scripts_with_warnings <- list()
codetools_ok <- requireNamespace("codetools", quietly = TRUE)
if (codetools_ok) {
  for (s in scripts_extracted) {
    dangling <- character(0)
    wrapped <- tryCatch(
      eval(parse(text = paste0("function() {\n", s$code, "\n}"))),
      error = function(e) NULL   # unparseable code: skip validation
    )
    if (!is.null(wrapped)) {
      globals <- tryCatch(
        codetools::findGlobals(wrapped, merge = FALSE)$variables,
        error = function(e) character(0)
      )
      dangling <- setdiff(globals, KNOWN_SAFE)
    }
    if (length(dangling) > 0) {
      scripts_with_warnings[[length(scripts_with_warnings) + 1]] <-
        list(source_path = s$source_path, dangling = dangling)
      cat(sprintf("  WARNING: %s — dangling references: %s\n",
                  s$source_path, paste(dangling, collapse = ", ")))
    }
  }
  if (length(scripts_with_warnings) > 0) {
    cat(sprintf("\n  %d script(s) have dangling references (variables used but never defined).\n",
                length(scripts_with_warnings)))
    cat("  These may be cross-chunk dependencies lost during decompilation.\n")
    cat("  Review these scripts before re-execution in Reproducibility Verification.\n")
  } else {
    cat("  Reference validation: all scripts are self-contained (no dangling references detected).\n")
  }
} else {
  cat("  Reference validation SKIPPED: codetools not available.\n")
}

# --- Write MANIFEST.md ---
manifest_path <- file.path(output_dir, "MANIFEST.md")
ml <- c(
  "# Decompiled Script Manifest",
  "",
  sprintf("**Source Notebook:** `%s`", basename(notebook_path)),
  sprintf("**Decompiled:** %d scripts", length(scripts_extracted)),
  "",
  "| # | Script | Stage | Original Output | Code Lines | Has Log |",
  "|---|--------|-------|-----------------|-----------|---------|"
)
idx <- 1
for (m in manifest_rows) {
  ml <- c(ml, sprintf("| %d | `%s` | %s | `%s` | %d | %s |",
                      idx, m$source_path, m$stage, m$original_output,
                      m$code_lines, if (m$has_log) "Yes" else "No"))
  idx <- idx + 1
}

# Dangling-reference section (mirrors the Python manifest section).
if (!codetools_ok) {
  ml <- c(ml, "", "## Dangling Reference Warnings", "",
          "Reference validation not run: codetools package unavailable.")
} else if (length(scripts_with_warnings) > 0) {
  ml <- c(ml, "", "## Dangling Reference Warnings", "",
          "The following scripts reference variables that are not defined within the script.",
          "These may be cross-chunk dependencies from the Quarto notebook that were lost during decompilation.",
          "Scripts with dangling references may fail during re-execution and require modification.",
          "NOTE: column names used inside tidyverse NSE verbs (mutate, filter, summarise, aes, ...)",
          "are not statically resolvable and may appear here as false positives — treat these",
          "warnings as review prompts, not errors.",
          "",
          "| Script | Undefined Names |",
          "|--------|-----------------|")
  for (w in scripts_with_warnings) {
    ml <- c(ml, sprintf("| `%s` | %s |", w$source_path,
                        paste(sprintf("`%s`", w$dangling), collapse = ", ")))
  }
}
writeLines(paste0(paste(ml, collapse = "\n"), "\n"), manifest_path, sep = "")
cat(sprintf("\nManifest written to: %s\n", manifest_path))

cat(sprintf("\nDone. %d scripts extracted to %s\n",
            length(scripts_extracted), output_dir))
