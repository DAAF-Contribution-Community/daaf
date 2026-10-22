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
# --- Versions (three independent rule sets; bump the one you change) --------
#   NORMALIZE_VERSION     NORMALIZE + SKELETON (pdf_ingest agreement and
#                         lit_verify matching both depend on it)
#   MATCH_LADDER_VERSION  the quote match ladder, the identifying-quote rule
#                         and their constants (lit_verify only)
#   NUMBER_RULES_VERSION  number normalization and comparison (lit_verify)
#   lit_verify records all three in every card_check JSON.
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
#
# --- Number rules (added 2026-10-15, FE-3; note 08 §5) ----------------------
#   U+2212, U+2013, U+FE63, U+FF0D directly before a digit -> "-"; then NFKC
#   (fullwidth digits). "-" is a SIGN only at the start or after whitespace
#   or one of ( [ { = < > : ; , / ~ (so "2019-2020" is two positive numbers).
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
#   overlap_score() is the order-free character overlap (D-21 N4), a
#   diagnostic pdf_ingest records beside `agreement`.
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
MATCH_LADDER_VERSION = "ladder-v1"
NUMBER_RULES_VERSION = "numbers-v2"

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
NUMBER_MINUS_RE = re.compile("[\u2212\u2013\ufe63\uff0d](?=\\.?\\d)")
THIN_GROUP_SEP_RE = re.compile("(?<=\\d)[\u2009\u202f](?=\\d)")
GROUP_PLACEHOLDER = "\x00"
# INTENT: a "-" directly before a number is a sign only after one of these
#   (or at the start / after whitespace); after a digit or letter it is a
#   range dash or a subtraction ("2019-2020", "x-3").
SIGN_CONTEXT = "([{=<>:;,/~"
NUMBER_CORE_RE = {
    False: re.compile(r"\d{1,3}(?:[,\x00]\d{3})+(?!\d)(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+"),
    True: re.compile(r"\d{1,3}(?:[,\x00 ]\d{3})+(?!\d)(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+"),
}
PERCENT_RE = re.compile(r" ?%")
NUMBER_MARKS = "*†‡"


def number_text(text):
    # The number-rule preparation of a text: minus folds before digits, thin
    # spaces between digits marked as group separators, then NFKC.
    text = (text or "").replace("\r\n", "\n")
    text = NUMBER_MINUS_RE.sub("-", text)
    text = THIN_GROUP_SEP_RE.sub(GROUP_PLACEHOLDER, text)
    return unicodedata.normalize("NFKC", text)


def parse_numbers(text, join_spaces=False):
    # Every number token in `text` as a dict: raw, digits (canonical string),
    # value (Decimal), negative, paren, percent, marks, start, end. With
    # join_spaces, a plain space between 3-digit groups is a thousands
    # separator too.
    t = number_text(text)
    out = []
    for m in NUMBER_CORE_RE[join_spaces].finditer(t):
        s, e = m.start(), m.end()
        prev = t[s - 1] if s > 0 else ""
        if prev and (prev.isalnum() or prev in "._" or prev == GROUP_PLACEHOLDER):
            continue
        start, negative = s, False
        if prev == "-":
            before = t[s - 2] if s >= 2 else ""
            if before == "" or before.isspace() or before in SIGN_CONTEXT:
                start, negative = s - 1, True
        end, percent = e, False
        pm = PERCENT_RE.match(t, end)
        if pm:
            end, percent = pm.end(), True
        marks_at = end
        while end < len(t) and t[end] in NUMBER_MARKS:
            end += 1
        marks = t[marks_at:end]
        if not percent:
            pm = PERCENT_RE.match(t, end)
            if pm and pm.end() > end:
                end, percent = pm.end(), True
        after = t[end] if end < len(t) else ""
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
                    "percent": percent, "marks": marks, "start": start, "end": end})
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
    precision = None
    for tok in candidates:
        if tok["value"] == claim["value"] and tok["negative"] == claim["negative"]:
            if tok["digits"] == claim["digits"]:
                return "exact", tok
            precision = precision or tok
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
NUMBER_NEAR_CHARS = 0
# Measurement only (script 69): the lane B row rule was measured and NOT
#   adopted; lane_b_row_hit() and row_label_skeleton() are kept so the
#   measurement can be re-run. The gate never calls them.
LANE_B_LABEL_RE = re.compile(r"[^\W\d_]+")


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
