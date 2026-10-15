#!/usr/bin/env python3
# =============================================================================
# pdf_text_common.py - shared text normalization for DAAF's PDF-layer
#                      framework CLIs (added 2026-10-13, Lit Review S3, FE-2)
# =============================================================================
#
# Imported by scripts/pdf_ingest.py (two-extractor agreement on SKELETON
# text) and, from FE-3, by scripts/lit_verify.py (quote anchoring). One
# definition of NORMALIZE and SKELETON keeps both tools comparing text the
# same way; a change here changes what counts as "the same text" for both, so
# bump NORMALIZE_VERSION with any behavior change and record it in the
# artifacts that depend on it (pdf_ingest writes it into ingest_manifest.json).
#
# Source of the rules: research/2026-10-02_FrameworkDev_ScholarlySearch/
# preliminary_notes/08_research_s3_pdf_refresh.md § 5 (UCD probe: which code
# points NFKC folds and which it leaves alone).
#
#   NORMALIZE (apply identically to page text and to a quote):
#     1. CRLF -> LF, then NFKC
#     2. delete U+00AD (soft hyphen), U+200B-U+200D (zero-width space and
#        joiners), U+2060 (word joiner), U+FEFF (BOM / ZWNBSP)
#     3. fold dashes U+2010-U+2015, U+2212 (minus), U+FE63, U+FF0D -> "-"
#     4. fold quotes U+2018-U+201B, U+2032 -> "'" and U+201C-U+201F,
#        U+2033 -> '"'
#     5. "-" + optional whitespace + newline + optional whitespace -> ""
#        (rejoin hyphenated line breaks)
#     6. collapse every whitespace run to one space; trim both ends
#   SKELETON: NORMALIZE, then casefold, then delete all whitespace and "-".
#     It absorbs poppler's lossy de-hyphenation (pdftotext's default mode
#     fuses "natural-<newline>language" into "naturallanguage") and small-caps
#     word splits ("I NLINE S EARCH").
#
# Implementation note (step order): NFKC decomposes U+2033 DOUBLE PRIME into
# two U+2032 PRIME characters, which step 4 would then fold to "''" rather
# than the '"' the rule names. The fold table (steps 2-4) is therefore applied
# once BEFORE NFKC (so U+2033 becomes '"' first) and once AFTER it (to catch
# code points NFKC produces, e.g. U+2011 NON-BREAKING HYPHEN -> U+2010). Both
# passes are idempotent, so this changes nothing else.
#
# This module is part of standalone argparse CLIs (pdf_ingest.py, and
# lit_verify.py from FE-3): the documented exception to DAAF's
# no-function-definitions rule (CLAUDE.md § Code Style, "standalone CLI tools
# requiring argparse"). The functions here are pure (no I/O, no state) and
# covered by tests/python/test_pdf_ingest.py. FE-3 adds the quote match
# ladder and number normalization here; keep each addition small and tested.
# =============================================================================

import re
import unicodedata

# §§ CONSTANTS
NORMALIZE_VERSION = "normalize-v1"

# INTENT: invisible characters that split words without changing the visible
#   text (soft hyphen, zero-width space/joiners, word joiner, BOM).
DELETE_CHARS = "­​‌‍⁠﻿"
# INTENT: dash-like code points NFKC leaves alone (2010, 2012-2014, 2212 per
#   the UCD probe) plus the rest of the 2010-2015 block and the small /
#   fullwidth hyphen-minus forms.
DASH_CHARS = "‐‑‒–—―−﹣－"
SINGLE_QUOTE_CHARS = "‘’‚‛′"
DOUBLE_QUOTE_CHARS = "“”„‟″"

FOLD_TABLE = {ord(c): None for c in DELETE_CHARS}
FOLD_TABLE.update({ord(c): "-" for c in DASH_CHARS})
FOLD_TABLE.update({ord(c): "'" for c in SINGLE_QUOTE_CHARS})
FOLD_TABLE.update({ord(c): '"' for c in DOUBLE_QUOTE_CHARS})

HYPHEN_BREAK_RE = re.compile(r"-\s*\n\s*")
WHITESPACE_RE = re.compile(r"\s+")
SKELETON_DROP_RE = re.compile(r"[\s\-]+")


# §§ NORMALIZE
def normalize(text):
    # Returns the NORMALIZE form of `text` (see the header for the rules).
    if not text:
        return ""
    text = text.replace("\r\n", "\n")
    text = text.translate(FOLD_TABLE)
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(FOLD_TABLE)
    text = HYPHEN_BREAK_RE.sub("", text)
    return WHITESPACE_RE.sub(" ", text).strip()


def skeleton(text):
    # Returns the SKELETON form: NORMALIZE, casefold, drop whitespace and "-".
    return SKELETON_DROP_RE.sub("", normalize(text).casefold())
