#!/usr/bin/env Rscript
# =============================================================================
# Decompile a canonical DAAF Stage 9 Quarto archive into individual R scripts.
#
# The accepted input contract is defined by:
#   .claude/skills/quarto/references/daaf-notebook.md
#
# Each archived script must be stored in an R chunk whose first nonblank line,
# after zero or more #| option lines, is:
#   # --- VERBATIM COPY of scripts/<stage_dir>/<safe_name>.R ---
#
# The chunk must explicitly carry both `#| eval: false` and
# `#| code-fold: false`. It must be followed immediately (blank lines only) by
# exactly one canonical collapsed Execution Log callout. A strictly bounded
# legacy <details> form remains supported for older DAAF archives.
#
# This utility intentionally fails closed. It validates the complete notebook,
# builds and bounds-checks the complete extraction plan in memory, and only then
# creates directories or writes scripts and MANIFEST.md. Arbitrary Quarto files
# and malformed archive-shaped documents are not decompiled.
#
# Usage:
#   Rscript scripts/decompile_notebook.R <notebook_path> <output_dir>
#
# Framework-utility exception: this standalone CLI is not a research execution
# artifact and is directly runnable from /daaf/scripts/.
# =============================================================================

# --- Helpers ---
fail <- function(message) {
  cat(sprintf("Error: %s\n", message), file = stderr())
  quit(save = "no", status = 1, runLast = FALSE)
}

is_blank <- function(line) {
  grepl("^[[:space:]]*$", line)
}

is_symlink <- function(path) {
  # Sys.readlink() follows a terminal slash as a directory lookup on some
  # platforms, so strip it to test the requested filesystem entry itself.
  probe <- sub("/+$", "", path)
  if (!nzchar(probe)) {
    probe <- "/"
  }
  target <- Sys.readlink(probe)
  !is.na(target) && nzchar(target)
}

is_plain_fence <- function(line) {
  grepl("^[[:space:]]*```[[:space:]]*$", line)
}

is_r_chunk_open <- function(line) {
  grepl(
    "^[[:space:]]*```\\{[rR]([[:space:],][^}]*)?\\}[[:space:]]*$",
    line
  )
}

pattern_count <- function(text, pattern) {
  matches <- gregexpr(pattern, text, perl = TRUE)[[1]]
  if (length(matches) == 1 && identical(matches[1], -1L)) {
    return(0L)
  }
  length(matches)
}

skip_blank_lines <- function(lines, index) {
  while (index <= length(lines) && is_blank(lines[index])) {
    index <- index + 1L
  }
  index
}

is_legacy_execution_log_start <- function(lines, index) {
  if (index > length(lines) ||
      !grepl("^[[:space:]]*<details>[[:space:]]*$", lines[index])) {
    return(FALSE)
  }
  summary_index <- skip_blank_lines(lines, index + 1L)
  summary_index <= length(lines) && grepl(
    "^[[:space:]]*<summary>[[:space:]]*Execution Log[[:space:]]*</summary>[[:space:]]*$",
    lines[summary_index]
  )
}

is_execution_log_start <- function(lines, index) {
  if (index > length(lines)) {
    return(FALSE)
  }
  line <- lines[index]
  callout_log <- grepl("^[[:space:]]*:::", line) &&
    grepl("Execution Log", line, fixed = TRUE)
  callout_log || is_legacy_execution_log_start(lines, index)
}

validate_source_path <- function(source_path, notebook_line) {
  if (!nzchar(source_path)) {
    fail(sprintf("empty archive source path at notebook line %d", notebook_line))
  }
  if (grepl("[[:cntrl:]]", source_path)) {
    fail(sprintf(
      "archive source path contains a control character at notebook line %d",
      notebook_line
    ))
  }
  if (startsWith(source_path, "/") ||
      grepl("^[A-Za-z]:/", source_path)) {
    fail(sprintf(
      "archive source path must be relative, not absolute: %s",
      source_path
    ))
  }
  if (grepl("\\", source_path, fixed = TRUE)) {
    fail(sprintf(
      "archive source path must use forward slashes: %s",
      source_path
    ))
  }

  components <- strsplit(source_path, "/", fixed = TRUE)[[1]]
  if (any(components %in% c(".", ".."))) {
    fail(sprintf(
      "archive source path contains a forbidden '.' or '..' component: %s",
      source_path
    ))
  }
  if (length(components) != 2L) {
    fail(sprintf(
      "archive source path must contain exactly one stage directory and one filename: %s",
      source_path
    ))
  }

  allowed_stages <- c(
    "stage5_fetch",
    "stage6_clean",
    "stage7_transform",
    "stage8_analysis"
  )
  if (!(components[1] %in% allowed_stages)) {
    fail(sprintf(
      "archive source path has a noncanonical stage directory: %s",
      source_path
    ))
  }
  if (!grepl("^[A-Za-z0-9][A-Za-z0-9._-]*\\.R$", components[2])) {
    fail(sprintf(
      "archive source filename is unsafe or does not end in uppercase .R: %s",
      source_path
    ))
  }

  invisible(TRUE)
}

normalize_with_existing_ancestor <- function(path, description) {
  expanded <- path.expand(path)
  if (!grepl("^/", expanded)) {
    expanded <- file.path(getwd(), expanded)
  }

  probe <- expanded
  suffix <- character(0)
  repeat {
    is_link <- is_symlink(probe)
    if (file.exists(probe) || dir.exists(probe) || is_link) {
      break
    }
    parent <- dirname(probe)
    if (identical(parent, probe)) {
      fail(sprintf("cannot resolve %s: %s", description, path))
    }
    suffix <- c(basename(probe), suffix)
    probe <- parent
  }

  resolved_ancestor <- tryCatch(
    normalizePath(probe, winslash = "/", mustWork = TRUE),
    error = function(e) {
      fail(sprintf(
        "cannot resolve %s through existing ancestor '%s': %s",
        description,
        probe,
        conditionMessage(e)
      ))
    }
  )

  rebuilt <- resolved_ancestor
  if (length(suffix) > 0L) {
    for (component in suffix) {
      rebuilt <- file.path(rebuilt, component)
    }
  }
  normalized <- normalizePath(rebuilt, winslash = "/", mustWork = FALSE)
  if (nchar(normalized) > 1L) {
    normalized <- sub("/+$", "", normalized)
  }
  normalized
}

is_strict_descendant <- function(candidate, root) {
  root_prefix <- if (identical(root, "/")) "/" else paste0(root, "/")
  !identical(candidate, root) && startsWith(candidate, root_prefix)
}

parse_callout_log <- function(lines, start_index, notebook_line_offset) {
  opener <- lines[start_index]
  opener_match <- regexec(
    "^[[:space:]]*:::[[:space:]]*\\{([^}]*)\\}[[:space:]]*$",
    opener,
    perl = TRUE
  )
  opener_parts <- regmatches(opener, opener_match)[[1]]
  if (length(opener_parts) != 2L) {
    fail(sprintf(
      "malformed Execution Log callout opener at notebook line %d",
      notebook_line_offset + start_index - 1L
    ))
  }

  attributes <- opener_parts[2]
  callout_classes <- regmatches(
    attributes,
    gregexpr("\\.callout-[A-Za-z0-9_-]+", attributes, perl = TRUE)
  )[[1]]
  if (length(callout_classes) != 1L ||
      !identical(callout_classes[1], ".callout-note")) {
    fail(sprintf(
      "Execution Log callout must use exactly the .callout-note class at notebook line %d",
      notebook_line_offset + start_index - 1L
    ))
  }
  if (pattern_count(
        attributes,
        "(^|[[:space:]])collapse[[:space:]]*="
      ) != 1L ||
      !grepl(
        "(^|[[:space:]])collapse[[:space:]]*=[[:space:]]*\"true\"([[:space:]]|$)",
        attributes,
        perl = TRUE
      )) {
    fail(sprintf(
      "Execution Log callout must set collapse=\"true\" exactly once at notebook line %d",
      notebook_line_offset + start_index - 1L
    ))
  }
  if (pattern_count(
        attributes,
        "(^|[[:space:]])title[[:space:]]*="
      ) != 1L ||
      !grepl(
        "(^|[[:space:]])title[[:space:]]*=[[:space:]]*\"Execution Log\"([[:space:]]|$)",
        attributes,
        perl = TRUE
      )) {
    fail(sprintf(
      "Execution Log callout must set title=\"Execution Log\" exactly once at notebook line %d",
      notebook_line_offset + start_index - 1L
    ))
  }

  index <- skip_blank_lines(lines, start_index + 1L)
  if (index > length(lines) || !is_plain_fence(lines[index])) {
    fail(sprintf(
      "Execution Log callout is missing its plain fenced body after notebook line %d",
      notebook_line_offset + start_index - 1L
    ))
  }

  index <- index + 1L
  log_lines <- character(0)
  while (index <= length(lines) && !is_plain_fence(lines[index])) {
    log_lines <- c(log_lines, lines[index])
    index <- index + 1L
  }
  if (index > length(lines)) {
    fail(sprintf(
      "unclosed Execution Log fence opened after notebook line %d",
      notebook_line_offset + start_index - 1L
    ))
  }

  index <- skip_blank_lines(lines, index + 1L)
  if (index > length(lines)) {
    fail(sprintf(
      "unclosed Execution Log callout opened at notebook line %d",
      notebook_line_offset + start_index - 1L
    ))
  }
  if (!grepl("^[[:space:]]*:::[[:space:]]*$", lines[index])) {
    fail(sprintf(
      "malformed Execution Log callout: only blank lines may follow its fenced body before the close (notebook line %d)",
      notebook_line_offset + index - 1L
    ))
  }

  list(
    log_text = paste(log_lines, collapse = "\n"),
    next_index = index + 1L
  )
}

parse_legacy_log <- function(lines, start_index, notebook_line_offset) {
  if (!grepl("^[[:space:]]*<details>[[:space:]]*$", lines[start_index])) {
    fail(sprintf(
      "legacy Execution Log container must open with a plain <details> tag at notebook line %d",
      notebook_line_offset + start_index - 1L
    ))
  }

  index <- skip_blank_lines(lines, start_index + 1L)
  if (index > length(lines) || !grepl(
        "^[[:space:]]*<summary>[[:space:]]*Execution Log[[:space:]]*</summary>[[:space:]]*$",
        lines[index]
      )) {
    fail(sprintf(
      "legacy Execution Log container has a missing or mismatched summary after notebook line %d",
      notebook_line_offset + start_index - 1L
    ))
  }

  index <- skip_blank_lines(lines, index + 1L)
  if (index > length(lines) || !is_plain_fence(lines[index])) {
    fail(sprintf(
      "legacy Execution Log container is missing its plain fenced body after notebook line %d",
      notebook_line_offset + start_index - 1L
    ))
  }

  index <- index + 1L
  log_lines <- character(0)
  while (index <= length(lines) && !is_plain_fence(lines[index])) {
    log_lines <- c(log_lines, lines[index])
    index <- index + 1L
  }
  if (index > length(lines)) {
    fail(sprintf(
      "unclosed legacy Execution Log fence opened after notebook line %d",
      notebook_line_offset + start_index - 1L
    ))
  }

  index <- skip_blank_lines(lines, index + 1L)
  if (index > length(lines)) {
    fail(sprintf(
      "unclosed legacy Execution Log <details> container opened at notebook line %d",
      notebook_line_offset + start_index - 1L
    ))
  }
  if (!grepl("^[[:space:]]*</details>[[:space:]]*$", lines[index])) {
    fail(sprintf(
      "malformed legacy Execution Log container: only blank lines may follow its fenced body before </details> (notebook line %d)",
      notebook_line_offset + index - 1L
    ))
  }

  list(
    log_text = paste(log_lines, collapse = "\n"),
    next_index = index + 1L
  )
}

is_placeholder_execution_log <- function(log_text) {
  log_lines <- strsplit(log_text, "\n", fixed = TRUE)[[1]]
  normalized_lines <- character(0)
  for (line in log_lines) {
    normalized_line <- trimws(sub("^[[:space:]]*#[[:space:]]?", "", line))
    is_decoration <- nzchar(normalized_line) &&
      grepl("^[=\\-_*]+$", normalized_line)
    if (nzchar(normalized_line) && !is_decoration) {
      normalized_lines <- c(normalized_lines, normalized_line)
    }
  }

  normalized <- tolower(paste(normalized_lines, collapse = " "))
  normalized <- trimws(gsub("[^[:alnum:]_]+", " ", normalized))
  if (!nzchar(normalized)) {
    return(FALSE)
  }

  placeholder_forms <- c(
    "no execution log found",
    "todo",
    "tbd",
    "placeholder",
    "generic placeholder",
    "execution log placeholder",
    "placeholder execution log",
    "execution log todo",
    "todo execution log",
    "execution log tbd",
    "tbd execution log",
    "verbatim copy from script",
    "verbatim copy from the script"
  )
  candidate_forms <- normalized
  if (startsWith(normalized, "execution log ")) {
    candidate_forms <- c(
      candidate_forms,
      trimws(sub("^execution log[[:space:]]+", "", normalized))
    )
  }

  allowed_instruction_words <- c(
    "a", "actual", "add", "an", "and", "below", "complete", "copy",
    "execution", "from", "full", "generic", "here", "is", "later", "log",
    "paste", "placeholder", "please", "real", "script", "text", "the",
    "this", "tbd", "todo", "verbatim"
  )
  for (candidate in candidate_forms) {
    if (candidate %in% placeholder_forms) {
      return(TRUE)
    }

    words <- unique(strsplit(candidate, " ", fixed = TRUE)[[1]])
    is_log_instruction <- any(words %in% c("paste", "copy", "add")) &&
      all(c("execution", "log") %in% words) &&
      all(words %in% allowed_instruction_words)
    if (is_log_instruction) {
      return(TRUE)
    }

    is_generic_placeholder <- "placeholder" %in% words &&
      all(words %in% allowed_instruction_words)
    if (is_generic_placeholder) {
      return(TRUE)
    }

    is_verbatim_copy_instruction <-
      all(c("verbatim", "copy", "from", "script") %in% words) &&
      all(words %in% allowed_instruction_words)
    if (is_verbatim_copy_instruction) {
      return(TRUE)
    }
  }

  FALSE
}

reconstruct_script <- function(code, log_text) {
  log_lines <- strsplit(log_text, "\n", fixed = TRUE)[[1]]
  if (length(log_lines) == 0L) {
    log_lines <- character(0)
  }

  is_precommented <- FALSE
  for (line in head(log_lines, 10L)) {
    stripped <- trimws(line)
    if (stripped %in% c("# EXECUTION LOG", "# ====", "# =====") ||
        (grepl("^# =", stripped) && grepl("==========", stripped))) {
      is_precommented <- TRUE
      break
    }
  }

  if (is_precommented) {
    cleaned <- vapply(
      log_lines,
      function(line) {
        if (startsWith(line, "# ")) {
          substring(line, 3L)
        } else if (identical(line, "#")) {
          ""
        } else {
          line
        }
      },
      character(1),
      USE.NAMES = FALSE
    )
  } else {
    cleaned <- log_lines
  }

  commented <- vapply(
    cleaned,
    function(line) if (nzchar(line)) paste0("# ", line) else "#",
    character(1),
    USE.NAMES = FALSE
  )
  commented_log <- paste(commented, collapse = "\n")

  script <- sub("[ \t\r\n]+$", "", code)
  script <- paste0(script, "\n\n\n")
  if (!grepl("# EXECUTION LOG", commented_log, fixed = TRUE)) {
    script <- paste0(
      script,
      "# =============================================================================\n",
      "# EXECUTION LOG\n",
      "# =============================================================================\n"
    )
  }
  paste0(script, commented_log, "\n")
}

# --- Config ---
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2L) {
  cat("Usage: Rscript decompile_notebook.R <notebook_path> <output_dir>\n")
  quit(save = "no", status = 1, runLast = FALSE)
}

notebook_path <- args[1]
output_dir <- args[2]
if (!file.exists(notebook_path) || dir.exists(notebook_path)) {
  fail(sprintf("notebook not found or is not a regular file: %s", notebook_path))
}
if (!nzchar(output_dir)) {
  fail("output directory must not be empty")
}
if (!requireNamespace("yaml", quietly = TRUE)) {
  fail(
    "the installed R package 'yaml' is required to validate canonical Stage 9 frontmatter; rebuild the DAAF image with that package available"
  )
}

cat(sprintf("Decompiling: %s\n", notebook_path))
cat(sprintf("Output dir:  %s\n\n", output_dir))

# --- Load ---
notebook_size <- file.info(notebook_path)$size
notebook_raw <- readBin(notebook_path, what = "raw", n = notebook_size)
if (any(notebook_raw == as.raw(0L))) {
  fail("notebook contains a NUL byte")
}
notebook_lines <- readLines(notebook_path, warn = FALSE)
if (length(notebook_lines) == 0L || !all(validUTF8(notebook_lines))) {
  fail("notebook is empty or contains invalid UTF-8")
}

# --- Validate canonical YAML before archive parsing ---
if (!grepl("^---[[:space:]]*$", notebook_lines[1])) {
  fail("canonical YAML frontmatter must begin on the first line with '---'")
}
frontmatter_candidates <- which(
  seq_along(notebook_lines) > 1L &
    grepl("^---[[:space:]]*$", notebook_lines)
)
if (length(frontmatter_candidates) == 0L) {
  fail("canonical YAML frontmatter is unclosed")
}
frontmatter_end <- frontmatter_candidates[1]
if (frontmatter_end <= 2L) {
  fail("canonical YAML frontmatter is empty")
}
frontmatter_text <- paste(
  notebook_lines[2:(frontmatter_end - 1L)],
  collapse = "\n"
)
frontmatter <- tryCatch(
  yaml::yaml.load(frontmatter_text, eval.expr = FALSE),
  warning = function(w) {
    fail(sprintf("malformed canonical YAML frontmatter: %s", conditionMessage(w)))
  },
  error = function(e) {
    fail(sprintf("malformed canonical YAML frontmatter: %s", conditionMessage(e)))
  }
)
if (!is.list(frontmatter)) {
  fail("canonical YAML frontmatter must be a mapping")
}
if (!is.character(frontmatter$title) || length(frontmatter$title) != 1L ||
    !nzchar(trimws(frontmatter$title))) {
  fail("canonical YAML frontmatter requires nonempty scalar title metadata")
}
if (!is.list(frontmatter$format) || !is.list(frontmatter$format$html)) {
  fail("canonical YAML frontmatter requires a nested format.html mapping")
}
html_settings <- frontmatter$format$html
if (!identical(html_settings$toc, TRUE)) {
  fail("canonical YAML setting format.html.toc must be true")
}
if (!is.numeric(html_settings[["toc-depth"]]) ||
    length(html_settings[["toc-depth"]]) != 1L ||
    is.na(html_settings[["toc-depth"]]) ||
    html_settings[["toc-depth"]] != 2) {
  fail("canonical YAML setting format.html.toc-depth must be 2")
}
if (!identical(html_settings[["code-fold"]], "show")) {
  fail("canonical YAML setting format.html.code-fold must be 'show'")
}
if (!identical(html_settings[["embed-resources"]], TRUE)) {
  fail("canonical YAML setting format.html.embed-resources must be true")
}
if (!identical(html_settings$theme, "cosmo")) {
  fail("canonical YAML setting format.html.theme must be 'cosmo'")
}
if (!is.list(frontmatter$execute)) {
  fail("canonical YAML frontmatter requires an execute mapping")
}
if (!identical(frontmatter$execute$echo, TRUE)) {
  fail("canonical YAML setting execute.echo must be true")
}
if (!identical(frontmatter$execute$eval, FALSE)) {
  fail("canonical YAML setting execute.eval must be false")
}
if (!identical(frontmatter$execute$warning, FALSE)) {
  fail("canonical YAML setting execute.warning must be false")
}

# --- Parse and validate the complete archive ---
content_start <- frontmatter_end + 1L
content_lines <- if (content_start <= length(notebook_lines)) {
  notebook_lines[content_start:length(notebook_lines)]
} else {
  character(0)
}
notebook_line_offset <- content_start

verbatim_re <- paste0(
  "^[[:space:]]*#[[:space:]]*---[[:space:]]*",
  "VERBATIM COPY of scripts/(.*?)[[:space:]]*---[[:space:]]*$"
)
verbatim_hint_re <- paste0(
  "^[[:space:]]*#[[:space:]]*---[[:space:]]*",
  "VERBATIM COPY of scripts/"
)
output_re <- "^[[:space:]]*\\*\\*Output:\\*\\*[[:space:]]*`(.+?)`[[:space:]]*$"

scripts_extracted <- list()
seen_source_paths <- character(0)
pending_output <- NA_character_
index <- 1L
while (index <= length(content_lines)) {
  line <- content_lines[index]

  if (grepl(output_re, line, perl = TRUE)) {
    output_match <- regexec(output_re, line, perl = TRUE)
    pending_output <- regmatches(line, output_match)[[1]][2]
  }

  if (is_execution_log_start(content_lines, index)) {
    fail(sprintf(
      "Execution Log container at notebook line %d is not immediately associated with an archive chunk",
      notebook_line_offset + index - 1L
    ))
  }

  if (!is_r_chunk_open(line)) {
    index <- index + 1L
    next
  }

  chunk_open_index <- index
  chunk_close_index <- index + 1L
  while (chunk_close_index <= length(content_lines) &&
         !is_plain_fence(content_lines[chunk_close_index])) {
    chunk_close_index <- chunk_close_index + 1L
  }
  if (chunk_close_index > length(content_lines)) {
    fail(sprintf(
      "unclosed R chunk opened at notebook line %d",
      notebook_line_offset + chunk_open_index - 1L
    ))
  }

  chunk_lines <- if (chunk_close_index > chunk_open_index + 1L) {
    content_lines[(chunk_open_index + 1L):(chunk_close_index - 1L)]
  } else {
    character(0)
  }
  marker_hints <- which(grepl(verbatim_hint_re, chunk_lines, perl = TRUE))
  marker_matches <- which(grepl(verbatim_re, chunk_lines, perl = TRUE))

  if (length(marker_hints) > 0L &&
      length(marker_matches) != length(marker_hints)) {
    malformed_local <- marker_hints[
      !marker_hints %in% marker_matches
    ][1]
    fail(sprintf(
      "malformed VERBATIM COPY marker at notebook line %d",
      notebook_line_offset + chunk_open_index + malformed_local - 1L
    ))
  }
  if (length(marker_matches) > 1L) {
    fail(sprintf(
      "duplicate VERBATIM COPY markers in R chunk opened at notebook line %d",
      notebook_line_offset + chunk_open_index - 1L
    ))
  }

  if (length(marker_matches) == 0L) {
    index <- chunk_close_index + 1L
    next
  }

  marker_index <- marker_matches[1]
  prefix_lines <- if (marker_index > 1L) {
    chunk_lines[seq_len(marker_index - 1L)]
  } else {
    character(0)
  }
  nonblank_prefix <- prefix_lines[!vapply(prefix_lines, is_blank, logical(1))]
  if (length(nonblank_prefix) > 0L &&
      any(!grepl("^[[:space:]]*#\\|", nonblank_prefix))) {
    fail(sprintf(
      "VERBATIM COPY marker must be the first nonblank non-option line in R chunk opened at notebook line %d",
      notebook_line_offset + chunk_open_index - 1L
    ))
  }
  eval_option_indices <- which(grepl(
    "^[[:space:]]*#\\|[[:space:]]*eval[[:space:]]*:",
    prefix_lines
  ))
  if (length(eval_option_indices) != 1L ||
      !grepl(
        "^[[:space:]]*#\\|[[:space:]]*eval[[:space:]]*:[[:space:]]*false[[:space:]]*$",
        prefix_lines[eval_option_indices]
      )) {
    fail(sprintf(
      "archive R chunk opened at notebook line %d requires exactly one '#| eval: false' option",
      notebook_line_offset + chunk_open_index - 1L
    ))
  }
  code_fold_option_indices <- which(grepl(
    "^[[:space:]]*#\\|[[:space:]]*code-fold[[:space:]]*:",
    prefix_lines
  ))
  if (length(code_fold_option_indices) != 1L ||
      !grepl(
        "^[[:space:]]*#\\|[[:space:]]*code-fold[[:space:]]*:[[:space:]]*false[[:space:]]*$",
        prefix_lines[code_fold_option_indices]
      )) {
    fail(sprintf(
      "archive R chunk opened at notebook line %d requires exactly one '#| code-fold: false' option",
      notebook_line_offset + chunk_open_index - 1L
    ))
  }

  marker_parts <- regmatches(
    chunk_lines[marker_index],
    regexec(verbatim_re, chunk_lines[marker_index], perl = TRUE)
  )[[1]]
  source_path <- marker_parts[2]
  marker_notebook_line <- notebook_line_offset + chunk_open_index + marker_index - 1L
  validate_source_path(source_path, marker_notebook_line)
  if (source_path %in% seen_source_paths) {
    fail(sprintf("duplicate archive source path: %s", source_path))
  }
  seen_source_paths <- c(seen_source_paths, source_path)

  code_lines <- if (marker_index < length(chunk_lines)) {
    chunk_lines[(marker_index + 1L):length(chunk_lines)]
  } else {
    character(0)
  }
  while (length(code_lines) > 0L && is_blank(code_lines[1])) {
    code_lines <- code_lines[-1]
  }
  while (length(code_lines) > 0L && is_blank(code_lines[length(code_lines)])) {
    code_lines <- code_lines[-length(code_lines)]
  }
  if (length(code_lines) == 0L || !nzchar(trimws(paste(code_lines, collapse = "\n")))) {
    fail(sprintf("archive source code is empty for %s", source_path))
  }

  log_start_index <- skip_blank_lines(content_lines, chunk_close_index + 1L)
  if (log_start_index > length(content_lines)) {
    fail(sprintf(
      "archive chunk for %s is missing its immediately adjacent Execution Log container",
      source_path
    ))
  }
  if (grepl("^[[:space:]]*:::", content_lines[log_start_index])) {
    log_result <- parse_callout_log(
      content_lines,
      log_start_index,
      notebook_line_offset
    )
  } else if (grepl(
        "^[[:space:]]*<details>[[:space:]]*$",
        content_lines[log_start_index]
      )) {
    log_result <- parse_legacy_log(
      content_lines,
      log_start_index,
      notebook_line_offset
    )
  } else {
    fail(sprintf(
      "archive chunk for %s must be followed immediately by an Execution Log container; found delayed or mismatched content at notebook line %d",
      source_path,
      notebook_line_offset + log_start_index - 1L
    ))
  }
  if (!nzchar(trimws(log_result$log_text))) {
    fail(sprintf("execution log is empty for %s", source_path))
  }
  if (is_placeholder_execution_log(log_result$log_text)) {
    fail(sprintf(
      "execution log is a placeholder rather than archived execution evidence for %s",
      source_path
    ))
  }

  duplicate_log_index <- skip_blank_lines(
    content_lines,
    log_result$next_index
  )
  if (is_execution_log_start(content_lines, duplicate_log_index)) {
    fail(sprintf(
      "duplicate Execution Log container after archive chunk for %s",
      source_path
    ))
  }

  scripts_extracted[[length(scripts_extracted) + 1L]] <- list(
    source_path = source_path,
    code = paste(code_lines, collapse = "\n"),
    log_text = log_result$log_text,
    original_output = pending_output
  )
  pending_output <- NA_character_
  index <- log_result$next_index
}

if (length(scripts_extracted) == 0L) {
  fail("no valid script bundles found; a canonical DAAF Stage 9 archive requires at least one marked R chunk")
}
cat(sprintf("Found %d script chunk(s)\n\n", length(scripts_extracted)))

# --- Build and bounds-check the extraction plan before any output mutation ---
# An extraction root is a new-output-only destination: never merge into,
# overwrite, or remove an existing file, directory, or symlink.
if (file.exists(output_dir) || dir.exists(output_dir) || is_symlink(output_dir)) {
  fail(sprintf(
    "output extraction root already exists; refusing to merge or overwrite: %s",
    output_dir
  ))
}
normalized_root <- normalize_with_existing_ancestor(
  output_dir,
  "extraction root"
)

extraction_plan <- list()
manifest_rows <- list()
for (script in scripts_extracted) {
  candidate_path <- file.path(output_dir, script$source_path)
  normalized_candidate <- normalize_with_existing_ancestor(
    candidate_path,
    sprintf("output candidate for %s", script$source_path)
  )
  if (!is_strict_descendant(normalized_candidate, normalized_root)) {
    fail(sprintf(
      "resolved output candidate escapes the normalized extraction root: %s -> %s (root: %s)",
      script$source_path,
      normalized_candidate,
      normalized_root
    ))
  }
  if (dir.exists(candidate_path)) {
    fail(sprintf("script output candidate is an existing directory: %s", candidate_path))
  }
  candidate_parent <- dirname(candidate_path)
  if ((file.exists(candidate_parent) || is_symlink(candidate_parent)) &&
      !dir.exists(candidate_parent)) {
    fail(sprintf(
      "script output parent exists but is not a directory: %s",
      candidate_parent
    ))
  }

  code_line_count <- length(strsplit(script$code, "\n", fixed = TRUE)[[1]])
  has_log <- nzchar(trimws(script$log_text))
  original_output <- script$original_output
  if (is.null(original_output) || is.na(original_output)) {
    original_output <- "—"
  }

  extraction_plan[[length(extraction_plan) + 1L]] <- list(
    source_path = script$source_path,
    out_path = candidate_path,
    normalized_out_path = normalized_candidate,
    script_content = reconstruct_script(script$code, script$log_text),
    code_lines = code_line_count,
    has_log = has_log
  )
  manifest_rows[[length(manifest_rows) + 1L]] <- list(
    source_path = script$source_path,
    stage = dirname(script$source_path),
    original_output = original_output,
    code_lines = code_line_count,
    has_log = has_log
  )
}

manifest_path <- file.path(output_dir, "MANIFEST.md")
normalized_manifest <- normalize_with_existing_ancestor(
  manifest_path,
  "manifest output candidate"
)
if (!is_strict_descendant(normalized_manifest, normalized_root)) {
  fail(sprintf(
    "resolved MANIFEST.md candidate escapes the normalized extraction root: %s (root: %s)",
    normalized_manifest,
    normalized_root
  ))
}
if (dir.exists(manifest_path)) {
  fail(sprintf("MANIFEST.md output candidate is an existing directory: %s", manifest_path))
}

# --- Validate dangling references before writing ---
cat("\n")
known_safe <- c(
  "T", "F", "pi", "letters", "LETTERS", "month.name", "month.abb", ".Machine"
)
scripts_with_warnings <- list()
codetools_ok <- requireNamespace("codetools", quietly = TRUE)
if (codetools_ok) {
  for (script in scripts_extracted) {
    dangling <- character(0)
    parsed_code <- tryCatch(
      parse(text = script$code),
      error = function(e) NULL
    )
    wrapped <- NULL
    if (!is.null(parsed_code)) {
      # Build a closure as language data without evaluating any notebook-derived
      # expression. In particular, do not interpolate code into
      # eval(parse("function() {...}")): an unmatched brace could escape that
      # wrapper and execute a sibling top-level expression during decompilation.
      closure_body <- as.call(c(list(as.name("{")), as.list(parsed_code)))
      wrapped <- tryCatch(
        as.function(c(alist(), list(closure_body)), envir = baseenv()),
        error = function(e) NULL
      )
    }
    if (!is.null(wrapped)) {
      globals <- tryCatch(
        codetools::findGlobals(wrapped, merge = FALSE)$variables,
        error = function(e) character(0)
      )
      dangling <- setdiff(globals, known_safe)
    }
    if (length(dangling) > 0L) {
      scripts_with_warnings[[length(scripts_with_warnings) + 1L]] <- list(
        source_path = script$source_path,
        dangling = dangling
      )
      cat(sprintf(
        "  WARNING: %s — dangling references: %s\n",
        script$source_path,
        paste(dangling, collapse = ", ")
      ))
    }
  }
  if (length(scripts_with_warnings) > 0L) {
    cat(sprintf(
      "\n  %d script(s) have dangling references (variables used but never defined).\n",
      length(scripts_with_warnings)
    ))
    cat("  These may be cross-chunk dependencies lost during decompilation.\n")
    cat("  Review these scripts before re-execution in Reproducibility Verification.\n")
  } else {
    cat("  Reference validation: all scripts are self-contained (no dangling references detected).\n")
  }
} else {
  cat("  Reference validation SKIPPED: codetools not available.\n")
}

manifest_lines <- c(
  "# Decompiled Script Manifest",
  "",
  sprintf("**Source Notebook:** `%s`", basename(notebook_path)),
  sprintf("**Decompiled:** %d scripts", length(scripts_extracted)),
  "",
  "| # | Script | Stage | Original Output | Code Lines | Has Log |",
  "|---|--------|-------|-----------------|-----------|---------|"
)
for (row_index in seq_along(manifest_rows)) {
  row <- manifest_rows[[row_index]]
  manifest_lines <- c(
    manifest_lines,
    sprintf(
      "| %d | `%s` | %s | `%s` | %d | %s |",
      row_index,
      row$source_path,
      row$stage,
      row$original_output,
      row$code_lines,
      if (row$has_log) "Yes" else "No"
    )
  )
}
if (!codetools_ok) {
  manifest_lines <- c(
    manifest_lines,
    "",
    "## Dangling Reference Warnings",
    "",
    "Reference validation not run: codetools package unavailable."
  )
} else if (length(scripts_with_warnings) > 0L) {
  manifest_lines <- c(
    manifest_lines,
    "",
    "## Dangling Reference Warnings",
    "",
    "The following scripts reference variables that are not defined within the script.",
    "These may be cross-chunk dependencies from the Quarto notebook that were lost during decompilation.",
    "Scripts with dangling references may fail during re-execution and require modification.",
    "NOTE: column names used inside tidyverse NSE verbs (mutate, filter, summarise, aes, ...)",
    "are not statically resolvable and may appear here as false positives — treat these",
    "warnings as review prompts, not errors.",
    "",
    "| Script | Undefined Names |",
    "|--------|-----------------|"
  )
  for (warning in scripts_with_warnings) {
    manifest_lines <- c(
      manifest_lines,
      sprintf(
        "| `%s` | %s |",
        warning$source_path,
        paste(sprintf("`%s`", warning$dangling), collapse = ", ")
      )
    )
  }
}
manifest_content <- paste0(paste(manifest_lines, collapse = "\n"), "\n")

# --- Write only after all intake validation and planning succeeds ---
if (!dir.exists(output_dir) &&
    !dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)) {
  fail(sprintf("could not create extraction root: %s", output_dir))
}
for (planned in extraction_plan) {
  parent_dir <- dirname(planned$out_path)
  if (!dir.exists(parent_dir) &&
      !dir.create(parent_dir, recursive = TRUE, showWarnings = FALSE)) {
    fail(sprintf("could not create script output directory: %s", parent_dir))
  }
  tryCatch(
    writeLines(planned$script_content, planned$out_path, sep = ""),
    error = function(e) {
      fail(sprintf(
        "could not write extracted script %s: %s",
        planned$out_path,
        conditionMessage(e)
      ))
    }
  )
  cat(sprintf(
    "  -> %s (%d code lines, log: %s)\n",
    planned$source_path,
    planned$code_lines,
    if (planned$has_log) "yes" else "no"
  ))
}
tryCatch(
  writeLines(manifest_content, manifest_path, sep = ""),
  error = function(e) {
    fail(sprintf("could not write MANIFEST.md: %s", conditionMessage(e)))
  }
)
cat(sprintf("\nManifest written to: %s\n", manifest_path))
cat(sprintf(
  "\nDone. %d scripts extracted to %s\n",
  length(scripts_extracted),
  output_dir
))
