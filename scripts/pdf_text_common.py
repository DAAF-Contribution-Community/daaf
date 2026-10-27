#!/usr/bin/env python3
# =============================================================================
# pdf_text_common.py - shared text normalization for DAAF's PDF-layer
#                      framework CLIs (added 2026-10-13, Lit Review S3, FE-2)
# =============================================================================
#
# Imported by scripts/pdf_ingest.py (two-extractor agreement on SKELETON
# text) and, from FE-3, by scripts/lit_verify.py (quote anchoring). One
# definition of NORMALIZE and SKELETON keeps both tools comparing text the
# same way; a change to either changes what counts as "the same text" for
# both, so bump NORMALIZE_VERSION with any behavior change to them and record
# it in the artifacts that depend on it (pdf_ingest writes it into
# ingest_manifest.json). The ladder and number rules below carry their own
# version constants (see "Versions").
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
# requiring argparse"). The functions here are pure (no I/O, no state).
# NORMALIZE/SKELETON are covered by tests/python/test_pdf_ingest.py; the
# ladder and number rules by tests/python/test_lit_verify.py.
#
# --- Versions (independent rule sets; bump the one you change) --------------
#   NORMALIZE_VERSION     NORMALIZE + SKELETON (pdf_ingest agreement and
#                         lit_verify matching both depend on it)
#   MATCH_LADDER_VERSION  the quote match ladder, the identifying-quote rule
#                         and their constants (lit_verify only)
#   NUMBER_RULES_VERSION  number normalization, comparison and locality,
#                         including the unique-row rule (lit_verify)
#   COLUMN_CHECK_VERSION  (2026-10-23, FE-5g, D-23) the column-not-checked
#                         LABEL on cleared numbers (§ COLUMN_CHECK); it
#                         changes no number status, so it is versioned apart
#                         from NUMBER_RULES_VERSION
#   lit_verify records all of these in every card_check JSON. OVERLAP_VERSION
#   (the overlap_score diagnostic) is recorded by pdf_ingest.
#
# --- Quote match ladder (added 2026-10-15, FE-3; note 08 §5) ----------------
#   Evaluated in this order for a quote cited to page P (or the declared
#   range P..P+1 when page_end is given); the first hit wins:
#   REDACTED_SPAN  the quote holds a scrub/redaction token or fence text: it
#                  was copied from a reading copy, not the page (human check)
#   PASS           exact substring of NORMALIZE(page text) on a cited page
#   PASS_SKELETON  exact substring on SKELETON (absorbs pdftotext's fused
#                  compound hyphens and small-caps splits); counts as a pass
#   PASS_SPAN      page_end = P+1 declared and the quote runs from the end of
#                  P into the start of P+1 (recorded header/footer lines
#                  between the two are skipped by the caller)
#   PASS_OCR       exact/skeleton match in a cited page's OCR text only
#                  (user decision Q-A: a distinct, weaker status)
#   NEAR           best windowed rapidfuzz partial_ratio_alignment score on a
#                  cited page (anchor or OCR text, NORMALIZE + casefold) is
#                  >= FUZZ_SCORE_CUTOFF: a human check, NEVER a pass
#   WRONG_PAGE     exact/skeleton match only on other pages, other pages'
#                  OCR text, or across a page boundary not declared with
#                  page_end (an undeclared span is WRONG_PAGE, never a pass)
#   NOT_FOUND      none of the above
#   Long quotes and the fuzzy tier: rapidfuzz's partial_ratio is only
#   guaranteed optimal for a needle of <= 64 chars, so a longer quote is cut
#   into overlapping windows of FUZZ_WINDOW_CHARS (step FUZZ_WINDOW_STEP); the
#   score is the minimum window score, and the windows must align in order
#   within FUZZ_SPAN_SLACK x the quote length (+ FUZZ_SPAN_SLACK_CHARS), or
#   the quote is not NEAR (stitched fragments are not a near match).
#   Identifying quote: >= MIN_QUOTE_CHARS normalized chars AND >=
#   MIN_QUOTE_WORDS words AND its SKELETON occurs exactly once across all
#   pages' anchor text and page boundaries (plus all OCR text when it matched
#   in OCR). The caller applies this rule and the sparse-page waiver.
#   ladder-v2 (2026-10-23, S3-A, review finding B2): the QUOTE-NUMBER rule,
#   applied by the caller to every claim quote that passes on any tier. The
#   number tokens of the quote (parse_numbers on the quote as written, sign
#   included) must equal, in order, the number tokens of the page span it
#   matched (number_view() of the page text, tokens overlapping the span,
#   whole tokens: quote_numbers_agree()). SKELETON deletes "-", so without
#   this rule "slope was 0.164" passes on a page printing "slope was −0.164"
#   and "510%" on "5–10%". The two token lists are compared under both
#   readings of a plain space between digit groups (equal under either is
#   agreement). lit_verify grades a mismatch QUOTE_NUMBERS_DIFFER (review),
#   never a pass. The tiers themselves are unchanged.
#   ladder-v3 (2026-10-27, S3-C1b, review cycle 2 NB2): the quote-number rule
#   (quote_number_check(); quote_numbers_agree() is its 3-tuple form) also
#   fails when (a) a token's superscript or footnote-letter marks differ
#   ("10³" over a printed "10⁻³"), or (b) the page span prints a SIGN-SHAPED
#   DASH the quote lacks: a "-" (any dash or minus NORMALIZE folds, the
#   superscript minus included) directly or after one space before a digit or
#   ".digit", or a dash the line-break rejoin deleted there (normalize_map's
#   `dashed`). (b) compares position by position on the SKELETON chars of the
#   quote and of the span (equal by construction; a count is the fallback
#   when their lengths differ), so a deleted dash is caught even where no
#   number token is parsed ("−0.164ab"); a dash outside the span (before its
#   first char) is not the span's, and extra dashes in the quote are allowed
#   ("K-12" over a rejoined "K12"). (c) A spaced dash read sign-ambiguous on
#   the page (numbers-v6), or any spaced dash before a quote token, compares
#   the two tokens without their sign (the dash itself is checked by (b)).
#
# --- Number rules (added 2026-10-15, FE-3; note 08 §5) ----------------------
#   U+2212, U+2013, U+FE63, U+FF0D directly before a digit -> "-"; then NFKC
#   (fullwidth digits). "-" is a SIGN only at the start or after whitespace
#   or one of ( [ { = < > : ; , / ~ (so "2019-2020" is two positive numbers);
#   numbers-v4 adds the spaced sign (below).
#   Thousands separators "," U+2009 U+202F, and a plain space, are removed
#   only between groups of exactly 3 digits (1,204 / 1 204 -> 1204). A plain
#   space is ambiguous (two table cells "1" "204"), so number_candidates()
#   returns tokens for BOTH readings. "^-?." -> "0." (.05 -> 0.05).
#   Trailing * † ‡ are stripped and kept as `marks`; "%" is an attribute;
#   parentheses are role "paren" (an SE or t statistic), NEVER negative.
#   compare_number(): same Decimal value AND same digit string -> "exact";
#   same value, different digit string (0.5 vs 0.50) -> "precision" (a
#   warning for a human, never a pass); otherwise no match.
#   numbers-v2 (2026-10-19, FE-5, D-21 N1): LOCALITY. An exact page token
#   must also overlap the claim quote's matched span (+- NUMBER_NEAR_CHARS,
#   chosen 0: inside the quote); quote_spans() / number_near_spans() below.
#   The caller grades a page-level hit that is not local as a review item.
#   numbers-v3 (2026-10-22, FE-5c, D-22): a second locality path, the
#   UNIQUE-ROW rule (quote_row(), number_in_row(); § ROW_RULE below): the
#   quote's leading label identifies exactly one lane B row on the page and
#   that row prints the value. An ambiguous label falls back to in-quote.
#   overlap_score() is the order-free character overlap (D-21 N4), a
#   diagnostic pdf_ingest records beside `agreement` (OVERLAP_VERSION).
#   column-check-v1 (2026-10-23, FE-5g, D-23): column_values() (§ COLUMN_CHECK
#   at the end) counts the comparable values a cleared number's clearing
#   text prints; lit_verify labels the number "column-not-checked" when there
#   are two or more. A label only: no number status changes.
#   numbers-v4 (2026-10-23, S3-A, review findings B1, B3 and the superscript
#   finding):
#     SPACED SIGN (B1): a "-" separated from the number by spaces/tabs and at
#       most one newline is a sign when the char before the dash (skipping
#       spaces/tabs) is one of SIGN_CONTEXT or the text starts there
#       ("Est = - 0.041", "(- 0.044)"); after a digit or letter it stays a
#       range or subtraction ("28 - 75", "(n − 1)"). U+2212, U+2013, U+FE63
#       and U+FF0D fold to "-" before such a gap too.
#     SUPERSCRIPTS: a superscript or subscript char (Unicode decomposition
#       tag <super> or <sub>: "¹", "²", "⁻", "ᵃ", "₂") is a MARK, never a
#       digit: number_text() keeps it out of NFKC (which folded "0.62¹" into
#       "0.621") and parse_numbers() records it in `marks` and `sup`.
#       compare_number() requires equal `sup` when the CLAIM writes one (a
#       superscript can be an exponent, "10⁵", so a declared one is part of
#       the value); a claim without one matches a page token that has one (a
#       footnote mark the reader left out). Stars and daggers are NOT
#       compared (they never change the value, and extracted text often
#       detaches them from the cell); inside a claim quote they are kept by
#       both NORMALIZE and SKELETON, so a quote cannot change them.
#     NUMBER VIEW: number_view() reads the page text's numbers in NORMALIZE
#       coordinates without NORMALIZE's losses (superscripts, thin-space
#       groups, a sign "-" deleted by the line-break rejoin, and a token
#       boundary where the rejoin fused a number with the word or number
#       beside it: "749–\n756", "6-\nyear", "K-\n12"), via normalize_map();
#       locality, the column label and the quote-number rule use it.
#     ROW RULE GUARDS (B3): § ROW_RULE (label >= ROW_LABEL_MIN_CHARS = 3
#       letters, a cell-like tail, a table/numeric page, a quote that starts
#       at a row start).
#   numbers-v5 (2026-10-23, S3-B1, S3-A2 open question 1): a fifth row-rule
#     guard, the ANCHOR CELL: on the raw anchor line where the quote's match
#     begins, the identified row label must stand as a cell (what follows it
#     on that line is cell-like: row_label_is_cell()). Closes the two holes
#     S3-A2 left (a prose sentence starting with a row label word,
#     "ORGANIZATION and other models; ...", and a lane B fragment row "the 1"
#     that any quote starting with "the" identified). Applied by the caller.
#   numbers-v6 (2026-10-27, S3-C1b, review cycle 2 NB2 and W-a; user-approved
#   principle: when the parser cannot be sure a sign or a digit belongs to the
#   number, the claim goes to review or fails, never to a silent pass):
#     FOOTNOTE LETTER (NB2): a number followed by exactly ONE letter of
#       FOOTNOTE_LETTERS (a-g) that ends the word ("−0.164a", "1.20b",
#       "2017a", "(7b)") is read as the number with that letter as a mark
#       (`letter`, also in `marks`). Not when another letter, a digit or "_"
#       follows, or ".", "-", "+", "'" and then a letter or digit ("5mg",
#       "3rd", "1e-5", "a.m."); other letters stay non-numbers ("1990s", "5m",
#       "2x"). compare_number() requires an equal letter when the CLAIM writes
#       one; a claim without one matches a page token with one (a footnote
#       mark the reader left out), as for superscripts.
#     SPACED DASH AT A LINE START (W-a): a "-" with spaces/tabs before the
#       number is a sign when only spaces/tabs stand between the dash and the
#       start of its line ("\n– 0.30", a table cell); in a number view, where
#       NORMALIZE turned the newline into a space, the view's `breaks` carry
#       the line starts. normalize_map() also reads a rejoin-deleted dash at a
#       line start as a lost sign.
#     SIGN-AMBIGUOUS (W-a): a spaced dash after a letter or a closing bracket
#       with a space or tab between them (SIGN_AMBIGUOUS_AFTER: "of – 0.30",
#       "(n − 1)", "(Girls) – 0.30"; not "K-\n12") may be
#       a minus sign or a subtraction / range dash: the token keeps the
#       positive reading and is marked `sign_ambiguous`. compare_number()
#       returns "sign-ambiguous" (never "exact") for a claim of either sign
#       that only such a token prints (zero excepted: its sign is moot);
#       lit_verify grades it NUMBER_SIGN_AMBIGUOUS (review). After a digit,
#       "%" or another dash it stays a range ("28 - 75", numbers-v4). A
#       rejoin-deleted dash after a word is ambiguous in the view too
#       (normalize_map's `ambig`). Every token also records `spaced_dash`
#       (a spaced dash precedes it and was not read as a sign).
#
# --- Versions note (numbers-v6 / ladder-v3) ---------------------------------
#   normalize_map() returns two more sets (dashed, ambig); number_view()
#   carries them and `breaks`; NORMALIZE itself is unchanged (normalize-v1).
#
# rapidfuzz is NOT imported here: callers pass the `rapidfuzz.fuzz` module
# (or None, which skips the NEAR tier), so this module stays stdlib-only at
# import time and its exact tiers run on a bare interpreter.
# =============================================================================

import re
import unicodedata
from decimal import Decimal, InvalidOperation

# §§ CONSTANTS
NORMALIZE_VERSION = "normalize-v1"
MATCH_LADDER_VERSION = "ladder-v3"
NUMBER_RULES_VERSION = "numbers-v6"
# The order-free overlap diagnostic (overlap_score); pdf_ingest records it.
OVERLAP_VERSION = "overlap-v1"

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


def normalize_map(text):
    # (numbers-v4) (NORMALIZE(text), idx, lost): idx[i] is the index in
    # `text` of the char that produced norm char i; `lost` holds the norm
    # indices where step 5 (the line-break rejoin) deleted a "-" the number
    # rules read as a sign (SIGN_CONTEXT or the start before it, one newline,
    # a digit or ".digit" after). None when this char-wise construction does
    # not reproduce normalize(text) exactly (e.g. an NFKC composition across
    # chars); callers then fall back to NORMALIZE alone.
    # numbers-v6: returns (norm, idx, lost, splits, dashed, ambig). `dashed`:
    # norm indices of a number whose preceding dash the rejoin deleted (any
    # context; the quote-number rule's sign-dash check); `ambig`: those whose
    # deleted dash followed a word or closing bracket after a space (sign-
    # ambiguous). A dash at a line start before the rejoin is a lost sign.
    src = (text or "").replace("\r\n", "\n")
    shift = [i for i, c in enumerate(text or "") if not (c == "\r" and (text or "")[i + 1:i + 2] == "\n")]
    chars = []
    i = 0
    while i < len(src):
        j = i + 1
        while j < len(src) and unicodedata.combining(src[j]):
            j += 1
        piece = unicodedata.normalize("NFKC", src[i:j].translate(FOLD_TABLE)).translate(FOLD_TABLE)
        chars.extend((c, shift[i], False) for c in piece)
        i = j
    s = "".join(c for c, _, _ in chars)
    drop, lost_at, split_at, dashed_at, ambig_at = set(), set(), set(), set(), set()
    for m in HYPHEN_BREAK_RE.finditer(s):
        drop.update(range(m.start(), m.end()))
        k = m.start() - 1
        while k >= 0 and s[k] in " \t":
            k -= 1
        digit_after = re.match(r"\.?\d", s[m.end():m.end() + 2]) is not None
        if digit_after:
            # INTENT (numbers-v6): any dash the rejoin deletes before a number
            #   still counts as a sign-shaped dash for the quote-number rule.
            dashed_at.add(m.end())
        one_nl = m.group(0).count("\n") == 1
        if one_nl and (k < 0 or s[k] in SIGN_CONTEXT or s[k] in LINE_BREAK_CHARS) and digit_after:
            lost_at.add(m.end())
        elif one_nl and digit_after and k < m.start() - 1 and (s[k].isalpha() or s[k] in SIGN_AMBIGUOUS_AFTER):
            # INTENT (numbers-v6, W-a): "of –\n0.30": a spaced dash after a
            #   word, deleted by the rejoin: the number's sign is undecided.
            ambig_at.add(m.end())
        elif m.start() > 0 and ((s[m.start() - 1].isdigit() and s[m.end():m.end() + 1].isalnum()) or (
                s[m.start() - 1].isalpha() and s[m.end():m.end() + 1].isdigit())):
            # INTENT: "749–\n756" / "6-\nyear": the rejoin fuses a number with
            #   what follows; the number view splits there (a token boundary).
            #   S3-A2: the mirror case "K-\n12" / "COVID-\n19" (a letter before
            #   the dash, a digit after): the rejoin fuses the number INTO the
            #   word before it ("K12"), which hides it from the number rules,
            #   so a genuine quote "K-12" read as QUOTE_NUMBERS_DIFFER.
            split_at.add(m.end())
    # INTENT (numbers-v6): each kept char carries a tuple of tags (a position
    #   can be both "dashed" and one of lost / ambig / split).
    tags = {k: tuple(t for t, at in (("lost", lost_at), ("split", split_at), ("dashed", dashed_at),
                                       ("ambig", ambig_at)) if k in at)
            for k in lost_at | split_at | dashed_at | ambig_at}
    kept = [(c, r, tags.get(k, ())) for k, (c, r, _) in enumerate(chars) if k not in drop]
    s2 = "".join(c for c, _, _ in kept)
    out, pos = [], 0
    for m in WHITESPACE_RE.finditer(s2):
        out.extend(kept[pos:m.start()])
        out.append((" ", kept[m.start()][1], ()))
        pos = m.end()
    out.extend(kept[pos:])
    while out and out[0][0] == " ":
        out.pop(0)
    while out and out[-1][0] == " ":
        out.pop()
    norm = "".join(c for c, _, _ in out)
    if norm != normalize(text):
        return None
    tagged = lambda name: frozenset(i for i, (_, _, f) in enumerate(out) if name in f)  # noqa: E731
    return (norm, [r for _, r, _ in out], tagged("lost"), tagged("split"), tagged("dashed"), tagged("ambig"))


# §§ MATCH_LADDER (MATCH_LADDER_VERSION; added 2026-10-15, FE-3)
# PROVISIONAL: note 08 §5 synthesis. The S3 bake-off on real papers
#   calibrates them; uniqueness is the real test, and the length floor keeps
#   short common phrases ("citation quality") from passing by luck.
MIN_QUOTE_CHARS = 40
MIN_QUOTE_WORDS = 6
FUZZ_SCORE_CUTOFF = 95.0
# INTENT: rapidfuzz documents that partial_ratio is only guaranteed to find
#   the optimal alignment for a needle of at most 64 chars.
FUZZ_WINDOW_CHARS = 64
FUZZ_WINDOW_STEP = 32
FUZZ_SPAN_SLACK = 1.25
FUZZ_SPAN_SLACK_CHARS = 10

TIER_REDACTED_SPAN = "REDACTED_SPAN"
TIER_PASS = "PASS"
TIER_PASS_SKELETON = "PASS_SKELETON"
TIER_PASS_SPAN = "PASS_SPAN"
TIER_PASS_OCR = "PASS_OCR"
TIER_NEAR = "NEAR"
TIER_WRONG_PAGE = "WRONG_PAGE"
TIER_NOT_FOUND = "NOT_FOUND"
PASS_TIERS = (TIER_PASS, TIER_PASS_SKELETON, TIER_PASS_SPAN, TIER_PASS_OCR)


def prepare_doc(anchors, ocr=None, spans=None):
    # Precomputes NORMALIZE and SKELETON forms once per document.
    #   anchors  {page: raw anchor text}
    #   ocr      {page: raw OCR text} (pages without OCR text are omitted)
    #   spans    {(n, n + 1): (tail of page n, head of page n + 1)}, raw text
    #            with recorded header/footer lines already removed
    doc = {"anchor": {n: (normalize(t), skeleton(t)) for n, t in anchors.items()},
           "ocr": {n: (normalize(t), skeleton(t)) for n, t in (ocr or {}).items() if t and t.strip()},
           "span": {}}
    for key, (left, right) in (spans or {}).items():
        doc["span"][key] = (normalize(left), normalize(right), skeleton(left), skeleton(right))
    return doc


def count_overlapping(needle, hay):
    # Number of (possibly overlapping) occurrences of `needle` in `hay`.
    if not needle:
        return 0
    n, i = 0, hay.find(needle)
    while i != -1:
        n += 1
        i = hay.find(needle, i + 1)
    return n


def crossing_count(needle, left, right, sep):
    # Occurrences of `needle` in left + sep + right that take at least one
    # char from each side (a match wholly inside one page is not a span).
    if not needle or not left or not right:
        return 0
    lo = max(0, len(left) - len(needle) + 1)
    window = left[lo:] + sep + right[:len(needle) - 1]
    b = len(left) - lo
    count, i = 0, window.find(needle)
    while i != -1:
        if i < b and i + len(needle) > b + len(sep):
            count += 1
        i = window.find(needle, i + 1)
    return count


def exact_hit(qn, qs, pair):
    # "normalize" / "skeleton" when the quote is a substring of the
    # (NORMALIZE, SKELETON) pair, else None.
    norm, skel = pair
    if qn and qn in norm:
        return "normalize"
    if qs and qs in skel:
        return "skeleton"
    return None


def span_hit(qn, qs, span):
    # "normalize" / "skeleton" when the quote crosses the page boundary.
    ln, rn, ls, rs = span
    if crossing_count(qn, ln, rn, " "):
        return "normalize"
    if crossing_count(qs, ls, rs, ""):
        return "skeleton"
    return None


def fuzzy_score(qn, text_norm, fuzz):
    # Windowed rapidfuzz score of a NORMALIZEd quote against one NORMALIZEd
    # page text, casefolded. Returns {"score", "aligned"}: `aligned` is False
    # when the windows of a long quote do not line up in order (stitched).
    q, t = qn.casefold(), text_norm.casefold()
    if not q or not t:
        return {"score": 0.0, "aligned": False}
    if len(q) <= FUZZ_WINDOW_CHARS:
        return {"score": float(fuzz.partial_ratio_alignment(q, t).score), "aligned": True}
    starts = list(range(0, len(q) - FUZZ_WINDOW_CHARS + 1, FUZZ_WINDOW_STEP))
    if starts[-1] != len(q) - FUZZ_WINDOW_CHARS:
        starts.append(len(q) - FUZZ_WINDOW_CHARS)
    scores, dest = [], []
    for s in starts:
        al = fuzz.partial_ratio_alignment(q[s:s + FUZZ_WINDOW_CHARS], t)
        scores.append(float(al.score))
        dest.append((al.dest_start, al.dest_end))
    aligned = True
    if len(t) > FUZZ_WINDOW_CHARS:
        ordered = all(dest[i][0] <= dest[i + 1][0] for i in range(len(dest) - 1))
        width = dest[-1][1] - dest[0][0]
        aligned = ordered and width <= len(q) * FUZZ_SPAN_SLACK + FUZZ_SPAN_SLACK_CHARS
    return {"score": min(scores), "aligned": aligned}


def found_elsewhere(qn, qs, doc, cited, declared_span=None):
    # Exact/skeleton hits outside the cited pages: other pages' anchor text,
    # other pages' OCR text, and page boundaries other than the declared span.
    hits = []
    for lane in ("anchor", "ocr"):
        for n, pair in sorted(doc[lane].items()):
            if n not in cited:
                via = exact_hit(qn, qs, pair)
                if via:
                    hits.append({"pages": [n], "lane": lane, "via": via})
    for key, span in sorted(doc["span"].items()):
        if key != declared_span:
            via = span_hit(qn, qs, span)
            if via:
                hits.append({"pages": list(key), "lane": "span", "via": via})
    return hits


def match_quote(quote, doc, page, page_end=None, fuzz=None, markers=()):
    # The ladder for one quote cited to `page` (or page..page_end). Returns
    # {"tier", "score", "lane", "via", "found_on", "elsewhere", "detail"}.
    qn, qs = normalize(quote), skeleton(quote)
    res = {"tier": TIER_NOT_FOUND, "score": None, "lane": None, "via": None, "found_on": [], "elsewhere": [],
           "detail": ""}
    if not qs:
        res["detail"] = "the quote is empty after normalization"
        return res
    folded = qn.casefold()
    marker = next((m for m in markers if normalize(m) and normalize(m).casefold() in folded), None)
    if marker:
        res.update(tier=TIER_REDACTED_SPAN, detail=f"the quote contains {marker!r}: it was copied from a scrubbed or "
                                                   "fenced reading copy, not from the page text")
        return res
    cited = [page] + ([page_end] if page_end else [])
    for n in cited:
        via = exact_hit(qn, qs, doc["anchor"][n]) if n in doc["anchor"] else None
        if via:
            res.update(tier=TIER_PASS if via == "normalize" else TIER_PASS_SKELETON, score=100.0, lane="anchor",
                       via=via, found_on=[n])
            return res
    if page_end:
        span = doc["span"].get((page, page_end))
        via = span_hit(qn, qs, span) if span else None
        if via:
            res.update(tier=TIER_PASS_SPAN, score=100.0, lane="span", via=via, found_on=[page, page_end])
            return res
    for n in cited:
        via = exact_hit(qn, qs, doc["ocr"][n]) if n in doc["ocr"] else None
        if via:
            res.update(tier=TIER_PASS_OCR, score=100.0, lane="ocr", via=via, found_on=[n])
            return res
    declared = (page, page_end) if page_end else None
    elsewhere = found_elsewhere(qn, qs, doc, cited, declared)
    res["elsewhere"] = elsewhere
    best = None
    if fuzz is not None:
        for lane in ("anchor", "ocr"):
            for n in cited:
                if n not in doc[lane]:
                    continue
                f = fuzzy_score(qn, doc[lane][n][0], fuzz)
                cand = (f["score"] if f["aligned"] else 0.0, f["score"], lane, n, f["aligned"])
                if best is None or cand > best:
                    best = cand
        if best is not None:
            res["score"] = round(best[1], 2)
            if best[4] and best[1] >= FUZZ_SCORE_CUTOFF:
                note = f"best score {best[1]:.1f} on page {best[3]} ({best[2]} text)"
                if elsewhere:
                    note += f"; also an exact match elsewhere: {elsewhere}"
                res.update(tier=TIER_NEAR, lane=best[2], found_on=[best[3]], detail=note)
                return res
    if elsewhere:
        res.update(tier=TIER_WRONG_PAGE, found_on=sorted({p for h in elsewhere for p in h["pages"]}),
                   detail="exact match only off the cited page(s): " + "; ".join(
                       f"{h['lane']} p{'-p'.join(str(p) for p in h['pages'])} via {h['via']}" for h in elsewhere))
        return res
    res["detail"] = "no exact, skeleton, OCR or near match on the cited page(s) or elsewhere" + (
        "" if fuzz is not None else " (fuzzy tier not run)")
    return res


def quote_occurrences(quote, doc, include_ocr=False):
    # Occurrences of the quote's SKELETON across every page's anchor text and
    # page boundary (plus every page's OCR text when include_ocr).
    qs = skeleton(quote)
    n = sum(count_overlapping(qs, skel) for _, skel in doc["anchor"].values())
    n += sum(crossing_count(qs, ls, rs, "") for (_, _, ls, rs) in doc["span"].values())
    if include_ocr:
        n += sum(count_overlapping(qs, skel) for _, skel in doc["ocr"].values())
    return n


def quote_identity(quote, doc, include_ocr=False):
    # The identifying-quote rule: length floor, word floor, uniqueness.
    qn = normalize(quote)
    chars, words = len(qn), len(qn.split())
    occ = quote_occurrences(quote, doc, include_ocr)
    reasons = []
    if chars < MIN_QUOTE_CHARS:
        reasons.append(f"{chars} normalized chars < {MIN_QUOTE_CHARS}")
    if words < MIN_QUOTE_WORDS:
        reasons.append(f"{words} words < {MIN_QUOTE_WORDS}")
    if occ != 1:
        reasons.append(f"skeleton occurs {occ} times in the document (must be exactly 1)")
    return {"chars": chars, "words": words, "occurrences": occ, "short": chars < MIN_QUOTE_CHARS or
            words < MIN_QUOTE_WORDS, "identifying": not reasons, "reason": "; ".join(reasons)}


# §§ NUMBERS (NUMBER_RULES_VERSION; added 2026-10-15, FE-3)
# numbers-v4: also before a spaced gap (the spaced-sign rule decides whether
#   the "-" is a sign).
NUMBER_MINUS_RE = re.compile("[\u2212\u2013\ufe63\uff0d](?=[ \\t]*\\n?[ \\t]*\\.?\\d)")
# INTENT (numbers-v4): every superscript / subscript char (decomposition tag
#   <super> or <sub>); kept out of NFKC in number_text() and read as a mark.
SUPSUB_CHARS = frozenset(chr(c) for c in range(0xA0, 0x20000)
                         if unicodedata.decomposition(chr(c)).startswith(("<super>", "<sub>")))
SUPSUB_SPLIT_RE = re.compile("([" + re.escape("".join(sorted(SUPSUB_CHARS))) + "]+)")
THIN_SPACES = "\u2009\u202f"
THIN_GROUP_SEP_RE = re.compile("(?<=\\d)[\u2009\u202f](?=\\d)")
GROUP_PLACEHOLDER = "\x00"
# INTENT: a "-" directly before a number is a sign only after one of these
#   (or at the start / after whitespace); after a digit or letter it is a
#   range dash or a subtraction ("2019-2020", "x-3").
SIGN_CONTEXT = "([{=<>:;,/~"
# INTENT (numbers-v6, W-a): a spaced dash right after one of these (or after a
#   letter) is SIGN-AMBIGUOUS: "of – 0.30" may be a minus sign or a
#   subtraction; "(Girls) – 0.30" may be a table cell or a range. Only spaces
#   or tabs before the dash back to a LINE_BREAK_CHARS char (or the text
#   start) make it a sign instead (a cell at a line start).
SIGN_AMBIGUOUS_AFTER = ")]}"
LINE_BREAK_CHARS = "\n\f"
# INTENT (numbers-v6, NB2): footnote / sub-label letters read as a mark after
#   a number ("−0.164a", "2017a", "(7b)"). Narrow on purpose: the S3-C1b
#   corpus scan (WS script 109: 196 number+letter shapes in 848 bake-off
#   pages) found a/b/c as table notes, equation labels and citation years,
#   and x, k, y, p, z, t, r, q mostly as math variables; "s" is a plural
#   ("1990s") and m/k multipliers ("5m", "5k"), so they stay non-numbers.
# REASONING: a mark letter changes no digit, so reading "1.20b" as 1.20 only
#   lets the number rules see a token they missed (a deleted minus before it,
#   a declared number printed with a footnote letter).
FOOTNOTE_LETTERS = "abcdefg"
NUMBER_CORE_RE = {
    False: re.compile(r"\d{1,3}(?:[,\x00]\d{3})+(?!\d)(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+"),
    True: re.compile(r"\d{1,3}(?:[,\x00 ]\d{3})+(?!\d)(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+"),
}
PERCENT_RE = re.compile(r" ?%")
NUMBER_MARKS = "*†‡"


def number_text(text):
    # The number-rule preparation of a text: minus folds before digits, thin
    # spaces between digits marked as group separators, then NFKC.
    # numbers-v4: superscript / subscript runs are kept verbatim (marks).
    text = (text or "").replace("\r\n", "\n")
    text = NUMBER_MINUS_RE.sub("-", text)
    text = THIN_GROUP_SEP_RE.sub(GROUP_PLACEHOLDER, text)
    parts = SUPSUB_SPLIT_RE.split(text)
    return "".join(p if k % 2 else unicodedata.normalize("NFKC", p) for k, p in enumerate(parts))


def parse_numbers(text, join_spaces=False, breaks=None):
    # Every number token in `text` as a dict: raw, digits (canonical string),
    # value (Decimal), negative, paren, percent, marks, start, end. With
    # join_spaces, a plain space between 3-digit groups is a thousands
    # separator too.
    # numbers-v6: also sup, letter (a footnote letter, FOOTNOTE_LETTERS),
    #   sign_ambiguous and spaced_dash (header). `breaks`: positions of spaces
    #   in `text` that stand for a line break (a number view's NORMALIZE text);
    #   a raw text's own "\n" / "\f" need none.
    t = number_text(text)
    out = []
    for m in NUMBER_CORE_RE[join_spaces].finditer(t):
        s, e = m.start(), m.end()
        prev = t[s - 1] if s > 0 else ""
        if prev and (prev.isalnum() or prev in "._" or prev == GROUP_PLACEHOLDER):
            continue
        start, negative, ambiguous, spaced = s, False, False, False
        if prev == "-":
            before = t[s - 2] if s >= 2 else ""
            if before == "" or before.isspace() or before in SIGN_CONTEXT:
                start, negative = s - 1, True
        else:
            # INTENT (numbers-v4, B1): the spaced sign. A "-" before spaces /
            #   tabs and at most one newline is a sign when the char before it
            #   (spaces/tabs skipped) is SIGN_CONTEXT or the text starts there.
            #   numbers-v6 (W-a): or the dash starts its line; after a letter
            #   or a closing bracket the sign is ambiguous (header).
            j = s - 1
            while j >= 0 and t[j] in " \t":
                j -= 1
            if j >= 0 and t[j] == "\n":
                j -= 1
                while j >= 0 and t[j] in " \t":
                    j -= 1
            if 0 <= j < s - 1 and t[j] == "-":
                k = j - 1
                while k >= 0 and t[k] in " \t":
                    k -= 1
                line_start = k < 0 or t[k] in LINE_BREAK_CHARS or bool(
                    breaks and any(p in breaks for p in range(k + 1, j)))
                if line_start or t[k] in SIGN_CONTEXT:
                    start, negative = j, True
                else:
                    # INTENT: ambiguous only with a space or tab between the
                    #   word and the dash ("of – 0.30"); "K-\n12" is a compound
                    #   broken at a line end, not a sign.
                    spaced = True
                    ambiguous = k < j - 1 and (t[k].isalpha() or t[k] in SIGN_AMBIGUOUS_AFTER)
        end, percent = e, False
        pm = PERCENT_RE.match(t, end)
        if pm:
            end, percent = pm.end(), True
        marks_at = end
        while end < len(t) and (t[end] in NUMBER_MARKS or t[end] in SUPSUB_CHARS):
            end += 1
        marks = t[marks_at:end]
        if not percent:
            pm = PERCENT_RE.match(t, end)
            if pm and pm.end() > end:
                end, percent = pm.end(), True
        after = t[end] if end < len(t) else ""
        letter = ""
        if after and after in FOOTNOTE_LETTERS:
            # INTENT (numbers-v6, NB2): one footnote letter that ends the word
            #   is a mark ("−0.164a"); "5mg", "1e-5", "2a.m." are not.
            nxt = t[end + 1] if end + 1 < len(t) else ""
            nxt2 = t[end + 2] if end + 2 < len(t) else ""
            if not (nxt.isalnum() or nxt == "_" or (nxt and nxt in ".-+'’" and nxt2.isalnum())):
                letter, end, after = after, end + 1, nxt
        if after.isalnum() or after == "_":
            continue
        body = m.group(0)
        for sep in (",", GROUP_PLACEHOLDER, " "):
            body = body.replace(sep, "")
        if body.startswith("."):
            body = "0" + body
        digits = ("-" if negative else "") + body
        try:
            value = Decimal(digits)
        except InvalidOperation:
            continue
        out.append({"raw": t[start:end].replace(GROUP_PLACEHOLDER, " "), "digits": digits, "value": value,
                    "negative": negative, "paren": start > 0 and t[start - 1] == "(" and after == ")",
                    "percent": percent, "marks": marks + letter, "sup": "".join(c for c in marks if c in SUPSUB_CHARS),
                    "letter": letter, "sign_ambiguous": ambiguous, "spaced_dash": spaced,
                    "start": start, "end": end})
    return out


def number_candidates(text):
    # Tokens under both readings of a plain space between digit groups (one
    # number "1 204", or two table cells "1" and "204").
    toks = parse_numbers(text, join_spaces=False)
    seen = {(x["start"], x["end"]) for x in toks}
    toks.extend(x for x in parse_numbers(text, join_spaces=True) if (x["start"], x["end"]) not in seen)
    return toks


def parse_number(s):
    # One number written in a card ("-0.087", "(0.044)", "1,204", ".05",
    # "12.5%", "0.123***"); None unless the whole string is one number,
    # optionally in parentheses.
    s = (s or "").strip()
    toks = parse_numbers(s, join_spaces=True)
    if len(toks) != 1:
        return None
    tok = toks[0]
    t = number_text(s)
    lead, tail = t[:tok["start"]], t[tok["end"]:]
    if (lead, tail) not in (("", ""), ("(", ")")):
        return None
    return dict(tok, paren=lead == "(")


def compare_number(claim, candidates):
    # ("exact", token) for the same value and digit string; ("precision",
    # token) for the same value written with other digits (0.5 vs 0.50);
    # (None, None) otherwise. Sign is part of the value: 0.087 != -0.087.
    # numbers-v4: a superscript the CLAIM writes must be printed (it may be
    #   an exponent); a claim without one ignores the page's (a footnote mark).
    # numbers-v6: the same for a footnote letter; and ("sign-ambiguous",
    #   token) when the only token printing the claim's digits (either sign)
    #   is sign-ambiguous ("of – 0.30"): never "exact", so it never clears
    #   silently. A zero's sign is moot (Decimal -0 == 0): compared as usual.
    precision = ambiguous = None
    for tok in candidates:
        if claim.get("sup") and tok.get("sup") != claim["sup"]:
            continue
        if claim.get("letter") and tok.get("letter") != claim["letter"]:
            continue
        if tok.get("sign_ambiguous") and tok["value"] != 0:
            if abs(tok["value"]) == abs(claim["value"]):
                if tok["digits"].lstrip("-") == claim["digits"].lstrip("-"):
                    ambiguous = ambiguous or tok
                else:
                    precision = precision or tok
            continue
        if tok["value"] == claim["value"] and tok["negative"] == claim["negative"]:
            if tok["digits"] == claim["digits"]:
                return "exact", tok
            precision = precision or tok
    if ambiguous:
        return "sign-ambiguous", ambiguous
    return ("precision", precision) if precision else (None, None)


# §§ NUMBER_LOCALITY (numbers-v2; added 2026-10-19, FE-5, user decision D-21 N1)
# A claimed number printed somewhere on the cited page is not enough: a page
# token printing it must overlap the place where the claim's quote matched,
# widened by NUMBER_NEAR_CHARS normalized chars on each side. With the
# chosen value 0 the number must sit INSIDE the matched quote. Positions are
# in NORMALIZE(page text) coordinates; a skeleton match is mapped back
# through skeleton_index(). Page tokens are used (not the quote's own text),
# so a sign or digit the skeleton tier ignores cannot slip through.
# REASONING (FE-5 script 69, B and C table pages, 453 claims, and 119 prose
#   numbers from A, B, F): share of claims graded ok, genuine / last digit
#   changed / sign flipped:
#     page-level (numbers-v1)    1.000 / 0.110 / 0.009
#     inside the quote (0)       0.305 / 0.013 / 0.000   <- chosen
#     +-40 chars                 0.322 / 0.026 / 0.000
#     +-160 chars                0.470 / 0.035 / 0.000
#     lane B row, >= 6 letters   1.000 / 0.053 / 0.000   (not adopted)
#   Prose numbers: 1.000 genuine and 0.000 fabricated under every rule. The
#   rule with the fewest fabricated passes was chosen (user decision D-21:
#   gate integrity first); a genuine table number outside its quote goes to
#   human review (NUMBER_NOT_NEAR_QUOTE), not to FAIL.
#   Correction (FE-5c scripts 75/76): script 69 quoted from the FIRST
#   occurrence of a row label, which on report-style pages is often another
#   row (a label such as "Full Sample" recurs in several panels), so its
#   genuine rates understate in-quote. With each quote taken from the
#   number's own row (449 claims, B and C; DOI/URL and footnote rows
#   excluded): in-quote 0.976 / 0.018 / 0.000; B6 1.000 / 0.058 / 0.000;
#   in-quote OR unique row (numbers-v3, shipped) 0.996 / 0.018 / 0.000; on
#   the 31 column-major rows 0.645 -> 0.935 genuine, 0.000 last digit.
NUMBER_NEAR_CHARS = 0
# Measurement only (script 69): the loose lane B row rule (B6: any lane B line
#   sharing >= 6 letters with the quote) was measured and NOT adopted;
#   lane_b_row_hit() and row_label_skeleton() are kept so that measurement can
#   be re-run. The gate never calls them. numbers-v3 uses quote_row() below.
LANE_B_LABEL_RE = re.compile(r"[^\W\d_]+")
# numbers-v3 (2026-10-22, FE-5c, user decision D-22): the UNIQUE-ROW rule. A
#   number also clears when the claim's quote identifies exactly one lane B
#   row on the page and that row prints the value (quote_row(),
#   number_in_row()). A row label shorter than this many letters never
#   identifies a row (single letters are footnote marks and panel labels).
# numbers-v4 (2026-10-23, S3-A, review finding B3): the row path accepted any
#   lane B line with letters before a number, on any page, so a PROSE quote
#   "identified" a prose line and cleared its numbers (s3q r05: 62
#   identifying prose windows in 4 papers; r07 P1). Four guards, all required:
#     label  >= ROW_LABEL_MIN_CHARS letters (3; 2 let "of", "in" be labels)
#     tail   cell-like: letters <= ROW_TAIL_LETTER_SHARE_MAX of the tail's
#            non-space chars (a prose line's tail is mostly letters)
#     page   the page (HTML unit) where the quote matched is flagged one of
#            ROW_PAGE_FLAGS by pdf_ingest
#     start  the quote's anchor match begins at a row start: no letter between
#            the start of its raw anchor line and the quote (at_row_start();
#            on arXiv HTML the anchor's table rows are lines too). A quote
#            spanning two pages never takes the row path.
#     cell   (numbers-v5) the identified label stands as a cell on the anchor
#            line where the quote matched (row_label_is_cell())
#   The page, start and cell guards are applied by the caller (lit_verify).
# REASONING: measured in S3-A script 93 (genuine / fabricated rates before
#   and after, over every page with lane B): see the dispatch report.
ROW_LABEL_MIN_CHARS = 3
ROW_TAIL_LETTER_SHARE_MAX = 0.25
ROW_PAGE_FLAGS = ("table", "numeric")


def skeleton_index(norm):
    # (SKELETON of an already NORMALIZEd text, [index in norm of each
    # skeleton char]): the same chars skeleton() keeps, char by char.
    out, idx = [], []
    for i, c in enumerate(norm):
        for f in c.casefold():
            if not (f.isspace() or f == "-"):
                out.append(f)
                idx.append(i)
    return "".join(out), idx


def quote_spans(quote, text):
    # (NORMALIZE(text), [(start, end), ...]): every place the quote matches
    # in the page text, exact (NORMALIZE) occurrences first, else SKELETON
    # occurrences mapped back to NORMALIZE coordinates.
    norm, qn, qs = normalize(text), normalize(quote), skeleton(quote)
    spans = []
    i = norm.find(qn) if qn else -1
    while i != -1:
        spans.append((i, i + len(qn)))
        i = norm.find(qn, i + 1)
    if not spans and qs:
        skel, idx = skeleton_index(norm)
        i = skel.find(qs)
        while i != -1:
            spans.append((idx[i], idx[i + len(qs) - 1] + 1))
            i = skel.find(qs, i + 1)
    return norm, spans


def number_in_text(claim, text):
    # True when `text` prints the claimed number exactly (same value, digits).
    return compare_number(claim, number_candidates(text))[0] == "exact"


def number_near_spans(claim, norm, spans, window):
    # True when a token printing the claimed number exactly overlaps one of
    # `spans` widened by `window` chars on each side (NORMALIZE coordinates).
    toks = [t for t in number_candidates(norm)
            if any(t["end"] > s - window and t["start"] < e + window for s, e in spans)]
    return compare_number(claim, toks)[0] == "exact"


# §§ NUMBER_VIEW (numbers-v4; added 2026-10-23, S3-A)
# A page text's numbers in NORMALIZE coordinates (where quote_spans() puts a
# quote), read without NORMALIZE's losses: `text` is NORMALIZE(page) with the
# raw superscript / subscript chars and thin-space group separators put back
# (1:1, so positions are unchanged), and `lost_signs` the positions of numbers
# whose sign "-" the line-break rejoin deleted. When normalize_map() cannot
# map the page, the view is NORMALIZE itself (`mapped` False; idx None).
def number_view(text):
    # numbers-v6: the view also carries `dashed` and `ambig` (normalize_map)
    #   and `breaks`: positions of the spaces NORMALIZE made from a whitespace
    #   run that held a line break (so a dash after one starts its line).
    raw = text or ""
    m = normalize_map(raw)
    empty = frozenset()
    if m is None:
        norm = normalize(raw)
        return {"text": norm, "norm": norm, "raw": raw, "idx": None, "lost_signs": empty, "splits": empty,
                "dashed": empty, "ambig": empty, "breaks": empty, "mapped": False}
    norm, idx, lost, splits, dashed, ambig = m
    chars = list(norm)
    for i, r in enumerate(idx):
        c = raw[r]
        alone = (i == 0 or idx[i - 1] != r) and (i + 1 == len(idx) or idx[i + 1] != r)
        if alone and (c in SUPSUB_CHARS or (c in THIN_SPACES and not raw[r + 1:r + 2].isspace())):
            chars[i] = c
    view = "".join(chars)
    if len(number_text(view)) != len(view):
        return {"text": norm, "norm": norm, "raw": raw, "idx": None, "lost_signs": empty, "splits": empty,
                "dashed": empty, "ambig": empty, "breaks": empty, "mapped": False}
    breaks = set()
    for i, c in enumerate(norm):
        if c != " ":
            continue
        # INTENT: walk the raw whitespace run this space stands for (chars
        #   NORMALIZE deletes, e.g. a zero-width space, are skipped too).
        j = idx[i]
        while j < len(raw) and (raw[j].isspace() or raw[j] in DELETE_CHARS):
            if raw[j] in LINE_BREAK_CHARS:
                breaks.add(i)
                break
            j += 1
    return {"text": view, "norm": norm, "raw": raw, "idx": idx, "lost_signs": lost, "splits": splits,
            "dashed": dashed, "ambig": ambig, "breaks": frozenset(breaks), "mapped": True}


def join_views(left, right):
    # The view of a declared span: left + " " + right (as lit_verify matches
    # it); no raw index (the row path never runs on a span).
    # numbers-v6: dashed / ambig / breaks shifted too; the joining space is a
    #   line break (the right page's first line starts there).
    norm = left["norm"] + " " + right["norm"]
    empty = frozenset()
    if normalize(norm) != norm:
        n2 = normalize(norm)
        return {"text": n2, "norm": n2, "raw": norm, "idx": None, "lost_signs": empty, "splits": empty,
                "dashed": empty, "ambig": empty, "breaks": empty, "mapped": False}
    off = len(left["text"]) + 1
    both = lambda k: frozenset(left.get(k, ())) | {p + off for p in right.get(k, ())}  # noqa: E731
    return {"text": left["text"] + " " + right["text"], "norm": norm, "raw": norm, "idx": None,
            "lost_signs": both("lost_signs"), "splits": both("splits"), "dashed": both("dashed"),
            "ambig": both("ambig"), "breaks": both("breaks") | {off - 1}, "mapped": False}


def view_numbers(view, join_spaces=False):
    # parse_numbers() on the view, with the lost signs applied and a token
    # boundary at each split (a space is parsed there; positions map back).
    # numbers-v6: the view's line breaks are passed on (mapped through the
    #   inserted split spaces) and a rejoin-deleted ambiguous dash marks its
    #   token sign_ambiguous.
    text, cuts = view["text"], sorted(view.get("splits") or ())
    for c in reversed(cuts):
        text = text[:c] + " " + text[c:]
    back = lambda p: p - sum(1 for k, c in enumerate(cuts) if c + k < p)  # noqa: E731
    breaks = {b + sum(1 for c in cuts if c <= b) for b in view.get("breaks") or ()}
    ambig = view.get("ambig") or ()
    out = []
    for t in parse_numbers(text, join_spaces, breaks):
        if cuts:
            t = dict(t, start=back(t["start"]), end=back(t["end"]))
        if not t["negative"] and t["start"] in view["lost_signs"]:
            t = dict(t, negative=True, digits="-" + t["digits"], value=-t["value"])
        elif not t["negative"] and t["start"] in ambig:
            t = dict(t, sign_ambiguous=True, spaced_dash=True)
        out.append(t)
    return out


def view_candidates(view):
    # number_candidates() on the view (both readings of a plain space).
    toks = view_numbers(view, False)
    seen = {(x["start"], x["end"]) for x in toks}
    toks.extend(x for x in view_numbers(view, True) if (x["start"], x["end"]) not in seen)
    return toks


def number_near_view(claim, view, spans, window):
    # number_near_spans() on a number view.
    return near_view_kind(claim, view, spans, window) == "exact"


def near_view_kind(claim, view, spans, window):
    # (numbers-v6) compare_number()'s kind ("exact", "sign-ambiguous",
    # "precision" or None) over the view tokens overlapping `spans` widened
    # by `window` chars.
    toks = [t for t in view_candidates(view) if any(t["end"] > s - window and t["start"] < e + window
                                                    for s, e in spans)]
    return compare_number(claim, toks)[0]


def sign_dash_flags(norm, start, end, dashed=frozenset()):
    # (ladder-v3) One bool per SKELETON char of norm[start:end] (the chars
    # skeleton_index() keeps): True on a digit, or a "." before a digit, that
    # a sign-shaped dash precedes INSIDE the slice ("-" directly or after one
    # space), or that `dashed` marks (a dash the line-break rejoin deleted
    # before it; not on the slice's first char).
    flags = []
    for i in range(start, end):
        c = norm[i]
        keep = sum(1 for f in c.casefold() if not (f.isspace() or f == "-"))
        if not keep:
            continue
        flag = False
        if c.isdigit() or (c == "." and norm[i + 1:i + 2].isdigit()):
            if i - 1 >= start and norm[i - 1] == "-":
                flag = True
            elif i - 2 >= start and norm[i - 1] == " " and norm[i - 2] == "-":
                flag = True
            elif i > start and i in dashed:
                flag = True
        flags.append(flag)
        flags.extend([False] * (keep - 1))
    return flags


def quote_number_check(quote, view, spans):
    # The quote-number rule (ladder-v2; ladder-v3 adds marks and sign dashes):
    # {"agree", "quote", "page", "why"}. The quote's number tokens
    # (parse_numbers on the quote as written) must equal, in order, the WHOLE
    # page tokens overlapping each matched span, under one of the two readings
    # of a plain space between digit groups: same digits (or, with a
    # sign-ambiguous page token or a spaced dash before the quote token, the
    # same digits without the sign), same superscript and footnote letter.
    # And every sign-shaped dash the span prints before a number must be in
    # the quote at the same SKELETON position (sign_dash_flags). `quote` and
    # `page` are digit lists; `why` is None, "digits", "marks" or "sign-dash".
    # No span: agree None (the caller fails closed).
    q = {js: parse_numbers(quote, js) for js in (False, True)}
    qd = [t["digits"] for t in q[False]]
    if not spans:
        return {"agree": None, "quote": qd, "page": None, "why": None}

    def same(a, b):
        # a quote token, b a page token
        if a["sup"] != b["sup"] or a.get("letter", "") != b.get("letter", ""):
            return False
        if a["digits"] == b["digits"]:
            return True
        loose = b.get("sign_ambiguous") or a.get("spaced_dash")
        return bool(loose) and a["digits"].lstrip("-") == b["digits"].lstrip("-")

    def agree(qs, ps):
        return len(qs) == len(ps) and all(same(a, b) for a, b in zip(qs, ps))

    qmap = normalize_map(quote)
    qnorm, qdashed = (qmap[0], qmap[4]) if qmap else (normalize(quote), frozenset())
    qflags = sign_dash_flags(qnorm, 0, len(qnorm), qdashed)
    first = None
    for s, e in spans:
        p = {js: [t for t in view_numbers(view, js) if t["end"] > s and t["start"] < e] for js in (False, True)}
        pd = [t["digits"] for t in p[False]]
        first = first or pd
        if not (agree(q[False], p[False]) or agree(q[True], p[True])):
            # INTENT: equal digit lists under one reading means only a mark
            #   (superscript or footnote letter) differs.
            digits_differ = all([t["digits"] for t in q[js]] != [t["digits"] for t in p[js]] for js in (False, True))
            return {"agree": False, "quote": qd, "page": pd, "why": "digits" if digits_differ else "marks"}
        pflags = sign_dash_flags(view["norm"], s, e, view.get("dashed") or frozenset())
        if len(pflags) == len(qflags):
            missing = any(a and not b for a, b in zip(pflags, qflags))
        else:
            missing = sum(pflags) > sum(qflags)
        if missing:
            return {"agree": False, "quote": qd, "page": pd, "why": "sign-dash"}
    return {"agree": True, "quote": qd, "page": first, "why": None}


def quote_numbers_agree(quote, view, spans):
    # ladder-v2's (agree, quote digits, page digits) form of
    # quote_number_check() (kept for callers and measurement scripts).
    r = quote_number_check(quote, view, spans)
    return r["agree"], r["quote"], r["page"]


def at_row_start(view, start):
    # numbers-v4 (B3): True when no letter stands between the start of the
    # raw line and the char at norm position `start` (a leading row number
    # "7. " is allowed). False without a raw index (fail closed).
    if view.get("idx") is None or not 0 <= start < len(view["idx"]):
        return False
    raw, r = view["raw"], view["idx"][start]
    line_start = max(raw.rfind("\n", 0, r), raw.rfind("\f", 0, r)) + 1
    return not any(c.isalpha() for c in raw[line_start:r])


def row_label_skeleton(line):
    # The letters of a line (digits, signs and punctuation dropped), as a
    # SKELETON: what a row label contributes to a table row's text.
    return skeleton(" ".join(LANE_B_LABEL_RE.findall(normalize(line))))


def lane_b_row_hit(claim, quote, lane_b_text, min_shared):
    # The first lane B line that prints the claimed number exactly AND shares
    # a run of >= min_shared letters (SKELETON) with the quote's letters: the
    # row label quoted beside the number. None when there is none.
    q = row_label_skeleton(quote)
    if len(q) < min_shared:
        return None
    for line in (lane_b_text or "").split("\n"):
        if not number_in_text(claim, line):
            continue
        lab = row_label_skeleton(line)
        n, best = len(lab), 0
        # INTENT: longest common substring, stdlib only and deterministic
        #   (difflib's autojunk heuristic would make it data-dependent).
        prev = [0] * (len(q) + 1)
        for i in range(n):
            cur = [0] * (len(q) + 1)
            for j in range(len(q)):
                if lab[i] == q[j]:
                    cur[j + 1] = prev[j] + 1
                    if cur[j + 1] > best:
                        best = cur[j + 1]
            prev = cur
        if best >= min_shared:
            return line
    return None


# §§ ROW_RULE (numbers-v3; added 2026-10-22, FE-5c, user decision D-22)
# pdftotext serializes most tables column-major, so a quote holding a row
# label rarely reaches the cell; lane B (pypdfium2) keeps each row on one line.
# The row rule uses lane B only as LOCALITY evidence for a value the anchor
# page already prints; quotes are still matched only against the anchor.
#   label     the letters (casefolded, no digits, spaces or punctuation) of
#             the text BEFORE the first number token that follows a letter:
#             "7. Gender (Girls) 0.50 0.50" -> "gendergirls";
#             "Time III (Inclusive with co-teaching) 288 34" ->
#             "timeiiiinclusivewithcoteaching". Hyphens and fused compounds
#             ("co-teaching" / "coteaching") compare equal; digits never do,
#             so rows "Grade 3" / "Grade 4" share the label "grade" (and are
#             ambiguous, the safe side).
#   row       a lane B line whose label has >= ROW_LABEL_MIN_CHARS letters and
#             that prints at least one number after its label, in a cell-like
#             tail (numbers-v4).
#   identify  the quote's LEADING label (its letters before its first number
#             token that follows a letter; the whole quote when it holds no
#             such number, e.g. a run of row labels on a column-major page)
#             must START with a row's label and the label must end at a word
#             boundary of the quote ("N" does not match "Notes"). Of the rows
#             that match, the one(s) with the longest label win; exactly one
#             winning line = "unique"; two or more lines with that label
#             (e.g. "Full Sample" in two tables of one page) = "ambiguous";
#             none = "none".
#   value     number_in_row(): the identified row prints the claimed number
#             exactly (value, digit string and sign) AFTER its label.
def letter_skeleton(norm):
    # (letters of an already NORMALIZEd text, casefolded, [index in norm of
    # each kept char]).
    out, idx = [], []
    for i, c in enumerate(norm):
        for f in c.casefold():
            if f.isalpha():
                out.append(f)
                idx.append(i)
    return "".join(out), idx


def label_cut(norm):
    # Index in `norm` where the label part ends: the start of the first number
    # token that begins after the first letter (len(norm) when there is none).
    first = next((i for i, c in enumerate(norm) if c.isalpha()), None)
    if first is None:
        return 0
    return next((t["start"] for t in parse_numbers(norm) if t["start"] > first), len(norm))


def lane_b_rows(lane_b_text):
    # [{"label", "line", "cut"}] for every lane B line that is a row.
    rows = []
    for raw in (lane_b_text or "").split("\n"):
        norm = normalize(raw)
        cut = label_cut(norm)
        label = letter_skeleton(norm[:cut])[0]
        tail = norm[cut:]
        cell_like = sum(c.isalpha() for c in tail) <= ROW_TAIL_LETTER_SHARE_MAX * max(
            1, sum(not c.isspace() for c in tail))
        if len(label) >= ROW_LABEL_MIN_CHARS and cut < len(norm) and parse_numbers(tail) and cell_like:
            rows.append({"label": label, "line": norm, "cut": cut})
    return rows


def quote_row(quote, lane_b_texts):
    # The lane B row the quote's leading label identifies, across the lane B
    # texts given (the page(s) where the quote matched). Returns {"status":
    # "unique" | "ambiguous" | "none", "row": row dict or None, "label",
    # "candidates": number of lines carrying the winning label}.
    qn = normalize(quote)
    lead = qn[:label_cut(qn)]
    skel, idx = letter_skeleton(lead)
    hits = []
    for text in lane_b_texts:
        for row in lane_b_rows(text):
            k = len(row["label"])
            if not skel.startswith(row["label"]):
                continue
            end = idx[k - 1] + 1
            # INTENT: the label must end where a word of the quote ends.
            if k < len(skel) and end < len(lead) and lead[end].isalpha():
                continue
            hits.append(row)
    if not hits:
        return {"status": "none", "row": None, "label": None, "candidates": 0}
    best = max(len(r["label"]) for r in hits)
    winners = [r for r in hits if len(r["label"]) == best]
    return {"status": "unique" if len(winners) == 1 else "ambiguous", "row": winners[0] if len(winners) == 1 else None,
            "label": winners[0]["label"], "candidates": len(winners)}


def row_label_is_cell(view, start, label_letters):
    # numbers-v5 (2026-10-23, S3-B1, S3-A2 open question 1): True when the
    # identified row label stands as a CELL on the raw anchor line where the
    # quote's match begins at norm position `start`: what follows the label's
    # last letter up to the end of that line is cell-like (letters <=
    # ROW_TAIL_LETTER_SHARE_MAX of its non-space chars; empty counts). A
    # column-major label alone on its line ("Huber-White (HW)\n") or a
    # row-major label followed by cells passes; a prose sentence that merely
    # starts with a label word ("ORGANIZATION and other models", "the SEs
    # are ...") does not. `label_letters` is len(row["label"]). False without
    # a raw index (fail closed).
    if view.get("idx") is None or not 0 <= start < len(view["norm"]) or label_letters < 1:
        return False
    letters, idx = letter_skeleton(view["norm"][start:])
    if len(letters) < label_letters:
        return False
    raw = view["raw"]
    r = view["idx"][start + idx[label_letters - 1]] + 1
    ends = [x for x in (raw.find("\n", r), raw.find("\f", r)) if x != -1]
    tail = raw[r:min(ends) if ends else len(raw)]
    return sum(c.isalpha() for c in tail) <= ROW_TAIL_LETTER_SHARE_MAX * max(1, sum(not c.isspace() for c in tail))


def number_in_row(claim, row):
    # True when the row prints the claimed number exactly after its label.
    toks = [t for t in number_candidates(row["line"]) if t["start"] >= row["cut"]]
    return compare_number(claim, toks)[0] == "exact"


def overlap_score(a, b):
    # Order-free character overlap of two texts on SKELETON (Dice on the
    # character multisets): 1.0 when both hold the same characters in any
    # order. A DIAGNOSTIC only (D-21 N4): no flag or verdict uses it.
    sa, sb = skeleton(a), skeleton(b)
    if not sa and not sb:
        return None
    ca, cb = {}, {}
    for c in sa:
        ca[c] = ca.get(c, 0) + 1
    for c in sb:
        cb[c] = cb.get(c, 0) + 1
    common = sum(min(v, cb.get(k, 0)) for k, v in ca.items())
    return round(2.0 * common / (len(sa) + len(sb)), 4)


# §§ COLUMN_CHECK (COLUMN_CHECK_VERSION; added 2026-10-23, FE-5g, user decision D-23)
# A LABEL, not a number rule: it changes no number status. When a number
# clears (in-quote or row), the gate knows WHERE the value is printed but not
# WHICH of several cells the claim means. In "Overage 0.58 0.57 0.59 0.56"
# a claim of 0.59 for the first column clears (residual (a) of numbers-v3).
# column_values() counts the distinct values the clearing text prints that
# could be confused with the claimed one; two or more means the column (or,
# in a column-major quote, the row) was not checked. lit_verify records it
# per number item (column_checked, column_label "column-not-checked").
#   clearing text  in-quote: the quote's matched span in the page text the
#                  number was found in (anchor, or OCR); row: the identified
#                  lane B / rows row after its label (as number_in_row)
#   number token   parse_numbers() (one reading: a plain space between digit
#                  groups splits, so "1 204" is "1" and "204"); tokens that
#                  overlap a token printing the claim exactly are the claim
#                  itself ("1 204" read as 1204), not other cells
#   comparable     same shape as the token that printed the claim: integer vs
#                  decimal, and with vs without "%" ("1,204 boats" is not a
#                  candidate for a coefficient 0.05). Parentheses and sign do
#                  NOT split shapes (a coefficient and its SE are confusable)
#   not counted    a year (a bare 4-digit integer COLUMN_YEAR_MIN..MAX, unless
#                  the claim is itself a year) and a reference number (an
#                  integer right after one of COLUMN_REFERENCE_WORDS, "Table 5",
#                  "Fig. 2", "p. 14"), so an ordinary prose sentence with one
#                  data number is not labeled
#   value          distinct digit strings, the claim's own value counted once
#                  however often it is printed (a row "0.57 0.57" with nothing
#                  else comparable makes the claim true in either column)
# REASONING: residual (a) measured at 1.8% of last-digit fabrications on PDF
#   true-row quotes (FE-5c s76) and ~9% on whole-row arXiv HTML quotes
#   (FE-5f s86); D-23 asked for a visible label so such numbers can go to a
#   human later, not a verdict change now.
COLUMN_CHECK_VERSION = "column-check-v1"
COLUMN_YEAR_MIN = 1900
COLUMN_YEAR_MAX = 2099
COLUMN_REFERENCE_WORDS = frozenset((
    "table", "tables", "tab", "figure", "figures", "fig", "figs", "section", "sections", "sec", "chapter", "ch",
    "appendix", "panel", "model", "models", "column", "columns", "col", "equation", "eq", "eqs", "page", "pages", "p",
    "pp", "note", "notes", "footnote", "step", "wave", "hypothesis"))
# INTENT: the word (letters) right before a token, an optional "." after it
#   ("Fig. 2", "p. 14"), then optional whitespace.
COLUMN_REFERENCE_RE = re.compile(r"([^\W\d_]+)\.?\s*$")


def column_shape(tok):
    # (decimal?, percent?): what kind of cell a token is.
    return ("." in tok["digits"], tok["percent"])


def column_is_year(tok):
    # A bare 4-digit integer in the year range (no separator, sign, % or
    # parentheses).
    d = tok["digits"]
    return (len(d) == 4 and d.isdigit() and COLUMN_YEAR_MIN <= int(d) <= COLUMN_YEAR_MAX and not tok["percent"]
            and not tok["paren"] and "," not in tok["raw"])


def column_is_reference(tok, text):
    # An integer right after a reference word ("Table 5", "Fig. 2").
    if "." in tok["digits"] or tok["negative"]:
        return False
    m = COLUMN_REFERENCE_RE.search(number_text(text)[:tok["start"]])
    return bool(m) and m.group(1).casefold() in COLUMN_REFERENCE_WORDS


def column_values(claim, text, start, end):
    # The number of distinct comparable values printed in text[start:end]
    # (the clearing text), counting the claim's own value once; None when no
    # token there prints the claim exactly (nothing to label). 1 = the claim
    # is the only candidate cell (column checked); >= 2 = column not checked.
    # numbers-v4: `text` may be a number_view() (its tokens and lost signs).
    if isinstance(text, dict):
        cands, singles, text = view_candidates(text), view_numbers(text), text["text"]
    else:
        cands, singles = number_candidates(text), parse_numbers(text)
    hits = [t for t in cands if t["end"] > start and t["start"] < end
            and t["value"] == claim["value"] and t["negative"] == claim["negative"]
            and t["digits"] == claim["digits"]]
    if not hits:
        return None
    shape, year = column_shape(hits[0]), column_is_year(hits[0])
    values = {claim["digits"]}
    for t in singles:
        if not (t["end"] > start and t["start"] < end):
            continue
        if any(t["end"] > h["start"] and t["start"] < h["end"] for h in hits):
            continue
        if column_shape(t) != shape or (column_is_year(t) and not year) or column_is_reference(t, text):
            continue
        values.add(t["digits"])
    return len(values)
