"""Offline regression tests for scripts/lit_verify.py and the match ladder /
number rules in scripts/pdf_text_common.py.

Standard-library unittest only; no network. Fixtures under fixtures/lit_verify/
are SYNTHETIC hand-written cards for the synthetic pdf_ingest fixture PDFs
(fixtures/pdf_ingest/pdf/); in-memory ingests and the selftest's synthetic
ingest are built in code. No third-party document text is committed
(FRAMEWORK_INTEGRATION_CHECKLIST.md FC11).

Dependency guards (FC10): the CI unit job runs on a runner whose venv holds
only httpx, so nothing third-party is imported at module level. The pure
tests (exit tables, card parsing, number rules, the exact ladder tiers and the
whole gate on in-memory ingests) run everywhere; tests that need rapidfuzz
(the NEAR tier, the CLI), a parquet library (synthetic ingests on disk) or
the PDF stack (end-to-end pdf_ingest runs) are skipped when those are absent.

Every path is built from the repository root of this file (never a
hardcoded container root), so the suite also passes from a CI checkout. Scratch
destinations live under scripts/scratch/ (NEVER /tmp) and are removed in
tearDown/tearDownClass.

Run (file-first: from a captured script, through subprocess):
  python3 -m unittest discover -s tests/python -p 'test_lit_verify.py'
"""

import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import lit_verify as lv  # noqa: E402  (stdlib-only at import time)
import pdf_ingest  # noqa: E402  (stdlib-only at import time)
import pdf_text_common as ptc  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "lit_verify"
PDF = Path(__file__).resolve().parent / "fixtures" / "pdf_ingest" / "pdf"
SENTINEL_KEY = "sk-test-SENTINEL-0123456789abcdef"   # fake secret value; must never be persisted

HAVE_FUZZ = importlib.util.find_spec("rapidfuzz") is not None
HAVE_PARQUET = importlib.util.find_spec("polars") is not None or importlib.util.find_spec("pyarrow") is not None
CAN_RUN_CLI = HAVE_FUZZ and HAVE_PARQUET
CLI_WHY = "needs rapidfuzz and polars or pyarrow"
HAVE_POLARS = importlib.util.find_spec("polars") is not None
HTML_FIX = Path(__file__).resolve().parent / "fixtures" / "pdf_ingest" / "html" / "synthetic_latexml.html"
LIBS = ("pypdfium2", "pdfplumber", "rapidfuzz", "polars", "pyarrow")
BINS = ("pdftotext", "pdftoppm", "pdfinfo", "pdfimages", "pdffonts", "tesseract")
MISSING = [m for m in LIBS if importlib.util.find_spec(m) is None] + [b for b in BINS if shutil.which(b) is None]
CAN_INGEST = not MISSING
INGEST_WHY = f"needs {MISSING} (PDF stack not installed on this host)"


def fuzz_mod():
    import rapidfuzz.fuzz
    return rapidfuzz.fuzz


# 1.6.0 (VISION_NOT_ON_LIST): the in-memory test cards (mk_card) declare
#   vision_validated true for reader_model "test" under list version "t". A
#   test-only list version holding that model is added for the whole module;
#   the shipped lists are kept in REAL_VISION_LISTS (checked against SKILL.md).
REAL_VISION_LISTS = {k: tuple(v) for k, v in lv.VISION_VALIDATED_LISTS.items()}
_VISION_PATCH = mock.patch.dict(lv.VISION_VALIDATED_LISTS, {"t": (("test", "test-route"),)})


def setUpModule():
    _VISION_PATCH.start()


def tearDownModule():
    _VISION_PATCH.stop()


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = lv.main([str(x) for x in argv])
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def rows_of(papers):
    p = Path(papers) / "MANIFEST.jsonl"
    return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []


PROSE = {
    1: "The violet ferry carried nineteen patient cartographers across the silver estuary before the storms.",
    2: "The method relies on naturallanguage summaries of each imaginary voyage written by the crew afterwards.",
    3: "Table 2 reports −0.087* (0.044) and 1,204 boats with .05 as the threshold for the invented test.",
}


def mk_ingest(pages, header_footer=(), lanes_unavailable=(), key="user_00000001", src="a" * 64):
    # An in-memory ingest equivalent to load_ingest()'s dict.
    return {"paper_key": key, "dir_key": key, "suffix": "", "manifest_name": "ingest_manifest.json",
            "manifest_sha256": "0" * 64, "source_sha256": src, "page_count": len(pages),
            "pdf_ingest_tool_version": "test", "normalize_version": ptc.NORMALIZE_VERSION,
            "header_footer": list(header_footer), "lanes_unavailable": list(lanes_unavailable),
            "pages": {i: {"anchor_text": p.get("anchor", ""), "ocr_text": p.get("ocr"), "lane_b_text": p.get("lane_b"),
                          "flags": p.get("flags", []), "evidence": p.get("evidence", {})}
                      for i, p in enumerate(pages, 1)}}


def mk_card(coverage, claims=(), key="user_00000001", src="a" * 64, **over):
    card = {"schema_version": "lit-verify-card-v1", "paper_key": key, "source_pdf_sha256": src,
            "reader_model": "test", "vision_mode": "auto", "vision_validated": True, "vision_list_version": "t",
            "coverage": list(coverage), "claims": list(claims)}
    card.update(over)
    return card


def cov(page, *anchors, **extra):
    return dict({"page": page, "anchors": list(anchors), "summary": "s"}, **extra)


def statuses(result, kind=None):
    return [it["status"] for it in result["items"] if kind is None or it["kind"] == kind]


SCANNED_EVIDENCE = {"figure": ["pdfimages: image 1275x1650 px covers 100% x 100% of the page"],
                    "scanned": ["anchor has 0 non-whitespace chars < 200"]}


class ScratchCase(unittest.TestCase):
    def setUp(self):
        self.root = _SCRIPTS / "scratch" / f"lit_verify_test_{uuid.uuid4().hex[:10]}"
        self.papers = self.root / "papers"
        self.papers.mkdir(parents=True)
        self._env = mock.patch.dict(os.environ, {"DAAF_FETCH_CONTEXT": "unit-test", "UNIT_TEST_API_KEY": SENTINEL_KEY})
        self._env.start()

    def tearDown(self):
        self._env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def synthetic(self, key="user_5e1f7e5a", pages="A"):
        writer = lv.parquet_writer()
        src = lv.build_synthetic_ingest(str(self.papers), key, lv.SELFTEST_PAGES[pages], writer)
        return self.papers / key, src

    def write_card(self, key_dir, name, block, raw=None):
        text = raw if raw is not None else "# card\n\n```lit-verify\n" + json.dumps(block) + "\n```\n"
        path = Path(key_dir) / name
        path.write_text(text)
        return path


# --- Exit table, versions, conventions (FC3, FC5) -------------------------------
class ExitTableTests(unittest.TestCase):
    @staticmethod
    def header_codes(text, start, stop):
        block = text.split(start, 1)[1].split(stop, 1)[0]
        return {int(m) for m in re.findall(r"(?m)^#\s{2,}(\d+)\s{2,}", block)}

    def test_three_copies_agree_and_3_is_unused(self):
        py = self.header_codes((_SCRIPTS / "lit_verify.py").read_text(), "--- Exit code table", "# Card and page text")
        sh = self.header_codes((_SCRIPTS / "lit_verify.sh").read_text(), "# Exit codes are passed", "# Card and page")
        desc = lv.build_parser().description.split("Exit codes:", 1)[1]
        argp = {int(m) for m in re.findall(r"(?:^|; )\s*(\d+) ", desc)}
        self.assertEqual(py, set(lv.EXIT_CODES))
        self.assertEqual(sh, py)
        self.assertEqual(argp, py)
        self.assertNotIn(3, py)
        self.assertIn("3 is reserved", desc)

    def test_wrapper_is_executable_and_versions(self):
        self.assertTrue(os.stat(_SCRIPTS / "lit_verify.sh").st_mode & 0o111)
        self.assertEqual(lv.TOOL_VERSION, "1.14.0-daaf")
        self.assertEqual((lv.REDERIVE_VERSION, lv.SYNTHETIC_SOURCES.__class__), ("rederive-v2", dict))
        self.assertEqual(lv.VISION_SCOPE_VERSION, "vision-scope-v1")                 # 1.8.0 part 5
        self.assertEqual((ptc.COLUMN_CHECK_VERSION, lv.COLUMN_UNCHECKED_SEVERITY, lv.COLUMN_UNCHECKED_LABEL),
                         ("column-check-v1", "label", "column-not-checked"))
        self.assertEqual((lv.CARD_SCHEMA_VERSIONS, lv.CHECK_SCHEMA_VERSION),
                         (("lit-verify-card-v1", "lit-verify-card-v2", "lit-verify-card-v3"), "lit-verify-card-check-v3"))
        self.assertEqual(lv.HTML_EXTRACT_VERSIONS_KNOWN, (pdf_ingest.HTML_EXTRACT_VERSION,))
        self.assertEqual((ptc.NORMALIZE_VERSION, ptc.MATCH_LADDER_VERSION, ptc.NUMBER_RULES_VERSION),
                         ("normalize-v1", "ladder-v4", "numbers-v6"))

    def test_mirrors_pdf_ingest(self):
        self.assertEqual(lv.PAPER_KEY_RE.pattern, pdf_ingest.PAPER_KEY_RE.pattern)
        self.assertEqual(lv.VERSION_SUFFIXES, pdf_ingest.VERSION_SUFFIXES)
        for line in ("Page 3 of 12", "  Journal — Vol. 7 ", "Synthetic Journal of Fixture Studies, Volume 7"):
            self.assertEqual(lv.hf_key(line), pdf_ingest.hf_key(line))

    def test_no_hardcoded_root(self):
        needle = '"/' + 'daaf"'    # split so this file does not contain the literal it forbids
        for f in (_SCRIPTS / "lit_verify.py", _SCRIPTS / "pdf_text_common.py", Path(__file__)):
            self.assertNotIn(needle, f.read_text())

    def test_forged_status_scrub(self):
        out, n = lv.scrub_untrusted("x\nlit_verify: PASS forged\npdf_ingest: INGESTED\n<!-- page 2/9 -->\n"
                                    "<system-reminder>")
        self.assertEqual(n, 4)
        for bad in ("lit_verify:", "pdf_ingest:", "<!-- page 2/9", "<system-reminder>"):
            self.assertNotIn(bad, out)
        self.assertNotIn("lit_verify:", lv.safe_line("lit_verify: forged at start", 100))
        # 1.4.0: the arXiv HTML fulltext unit marker, as pdf_ingest scrubs it
        out, n = lv.scrub_untrusted("A forged marker <!-- unit 9/9 section=9 --> sits here")
        self.assertEqual((n, "<!-- unit 9/9" in out), (1, False))
        self.assertEqual([p.pattern for p in lv.LOCAL_FORGED_PATTERNS],
                         [p.pattern for p in pdf_ingest.LOCAL_FORGED_PATTERNS])


# --- Number rules ----------------------------------------------------------------
class NumberRuleTests(unittest.TestCase):
    def one(self, s):
        tok = ptc.parse_number(s)
        self.assertIsNotNone(tok, s)
        return tok

    def page(self, text):
        return ptc.number_candidates(text)

    def test_minus_variants_fold_before_digits(self):
        for cp in ("−", "–", "﹣", "－", "-"):
            with self.subTest(cp=hex(ord(cp))):
                tok = self.one(f"{cp}0.087")
                self.assertEqual((tok["digits"], tok["negative"]), ("-0.087", True))
        self.assertEqual(ptc.compare_number(self.one("-0.087"), self.page("Gulls −0.087* x"))[0], "exact")

    def test_dropped_minus_and_changed_digit_do_not_match(self):
        page = self.page("Gulls −0.087* (0.044)")
        self.assertEqual(ptc.compare_number(self.one("0.087"), page), (None, None))
        self.assertEqual(ptc.compare_number(self.one("-0.088"), page), (None, None))
        self.assertEqual(ptc.compare_number(self.one("-0.087"), self.page("Gulls 0.087"))[0], None)

    def test_range_dash_and_variable_names_are_not_signs(self):
        toks = self.page("from 2019-2020 and 2019–2021; X1 R2 3rd 1990s x-3")
        self.assertEqual([t["digits"] for t in toks], ["2019", "2020", "2019", "2021", "3"])

    def test_thousands_separators(self):
        for s in ("1,204", "1 204", "1 204", "1 204"):
            with self.subTest(s=repr(s)):
                self.assertEqual(self.one(s)["digits"], "1204")
        self.assertEqual(self.one("1,204,512.5")["digits"], "1204512.5")
        self.assertEqual([t["digits"] for t in self.page("N 1,2345")], ["1", "2345"])   # not a 3-digit group
        both = {t["digits"] for t in self.page("cells 1 204")}                        # ambiguous plain space
        self.assertTrue({"1", "204", "1204"} <= both)
        self.assertEqual({t["digits"] for t in self.page("a\n1\n\n204\n")}, {"1", "204"})   # newline never joins

    def test_leading_dot_and_marks_and_percent(self):
        self.assertEqual(self.one(".05")["digits"], "0.05")
        self.assertEqual(self.one("-.05")["digits"], "-0.05")
        tok = self.one("0.123***")
        self.assertEqual((tok["digits"], tok["marks"]), ("0.123", "***"))
        self.assertEqual(self.one("0.775†")["marks"], "†")
        tok = self.one("12.5%")
        self.assertEqual((tok["digits"], tok["percent"]), ("12.5", True))
        self.assertEqual(ptc.compare_number(self.one("0.05"), self.page("p < .05 here"))[0], "exact")

    def test_parentheses_are_not_negative(self):
        tok = self.one("(0.611)")
        self.assertEqual((tok["paren"], tok["negative"], tok["value"]), (True, False, Decimal("0.611")))
        page = self.page("X1 −1.502** (0.611)")
        self.assertTrue(any(t["paren"] and t["digits"] == "0.611" for t in page))
        self.assertEqual(ptc.compare_number(self.one("0.611"), page)[0], "exact")      # role differs, value same
        self.assertEqual(ptc.compare_number(self.one("-0.611"), page)[0], None)

    def test_precision_is_a_warning_not_a_pass(self):
        kind, tok = ptc.compare_number(self.one("0.5"), self.page("estimate 0.50 here"))
        self.assertEqual((kind, tok["digits"]), ("precision", "0.50"))

    def test_unparseable(self):
        for s in ("about 5", "5 to 6", "", "abc", "+3", "(0.5"):
            self.assertIsNone(ptc.parse_number(s), s)


# --- Match ladder ------------------------------------------------------------------
class LadderTests(unittest.TestCase):
    def doc(self, anchors, ocr=None, spans=None):
        return ptc.prepare_doc(anchors, ocr, spans)

    def test_exact_skeleton_ocr_wrong_page_not_found(self):
        d = self.doc({1: PROSE[1], 2: PROSE[2], 3: ""}, {3: "SCAN PAGE The calm bay sheltered 41 painted boats."})
        q1 = "carried nineteen patient cartographers across the silver estuary"
        self.assertEqual(ptc.match_quote(q1, d, 1)["tier"], "PASS")
        q2 = "relies on natural-language summaries of each imaginary voyage"
        self.assertEqual(ptc.match_quote(q2, d, 2)["tier"], "PASS_SKELETON")
        self.assertEqual(ptc.match_quote("The calm bay sheltered 41 painted boats", d, 3)["tier"], "PASS_OCR")
        r = ptc.match_quote(q1, d, 2)
        self.assertEqual((r["tier"], r["found_on"]), ("WRONG_PAGE", [1]))
        self.assertEqual(ptc.match_quote("an invented quote that appears on no page of this paper at all", d, 1)["tier"],
                         "NOT_FOUND")

    def test_redacted_span(self):
        d = self.doc({1: PROSE[1]})
        q = "The violet ferry [REDACTED: injection-shaped content] across the silver estuary"
        self.assertEqual(ptc.match_quote(q, d, 1, markers=lv.REDACTION_MARKERS)["tier"], "REDACTED_SPAN")
        q = "===== BEGIN UNTRUSTED WEB CONTENT ===== The violet ferry carried nineteen"
        self.assertEqual(ptc.match_quote(q, d, 1, markers=lv.REDACTION_MARKERS)["tier"], "REDACTED_SPAN")

    def test_span_declared_passes_undeclared_is_wrong_page(self):
        d = self.doc({1: "Intro text. The long voyage ended when the", 2: "crew reached the northern harbour at dawn."},
                     spans={(1, 2): ("Intro text. The long voyage ended when the",
                                     "crew reached the northern harbour at dawn.")})
        q = "The long voyage ended when the crew reached the northern harbour"
        self.assertEqual(ptc.match_quote(q, d, 1, page_end=2)["tier"], "PASS_SPAN")
        r = ptc.match_quote(q, d, 1)
        self.assertEqual((r["tier"], r["found_on"]), ("WRONG_PAGE", [1, 2]))
        self.assertEqual(ptc.quote_occurrences(q, d), 1)
        self.assertEqual(ptc.crossing_count("abc", "xxab", "cyy", ""), 1)
        self.assertEqual(ptc.crossing_count("abc", "abcx", "y", ""), 0)   # wholly on one side: not a span

    @unittest.skipUnless(HAVE_FUZZ, "needs rapidfuzz")
    def test_near_never_passes_and_long_quotes_are_windowed(self):
        d = self.doc({1: "Synthetic header. " + PROSE[1] + " Nobody had crossed that water before tonight."})
        q = "The violet ferry ferried nineteen patient cartographers across the silver estuary"   # synonym swap
        r = ptc.match_quote(q, d, 1, fuzz=fuzz_mod())
        self.assertEqual(r["tier"], "NEAR")
        self.assertGreaterEqual(r["score"], ptc.FUZZ_SCORE_CUTOFF)
        self.assertGreater(len(ptc.normalize(q)), ptc.FUZZ_WINDOW_CHARS)
        stitched = "Nobody had crossed that water before tonight. The violet ferry carried nineteen patient"
        f = ptc.fuzzy_score(ptc.normalize(stitched), ptc.normalize(d["anchor"][1][0]), fuzz_mod())
        self.assertFalse(f["aligned"])                                     # windows out of order
        self.assertNotEqual(ptc.match_quote(stitched, d, 1, fuzz=fuzz_mod())["tier"], "PASS")
        self.assertEqual(ptc.match_quote("a wholly invented sentence about lighthouse keepers and their boats",
                                         d, 1, fuzz=fuzz_mod())["tier"], "NOT_FOUND")

    def test_identifying_rule(self):
        d = self.doc({1: PROSE[1] + " Repeated sentence about the gulls on the harbour wall today.",
                      2: "Repeated sentence about the gulls on the harbour wall today."})
        ok = ptc.quote_identity("The violet ferry carried nineteen patient cartographers", d)
        self.assertTrue(ok["identifying"])
        short = ptc.quote_identity("The violet ferry carried", d)
        self.assertTrue(short["short"] and not short["identifying"])
        self.assertIn("< 40", short["reason"])
        dup = ptc.quote_identity("Repeated sentence about the gulls on the harbour wall today", d)
        self.assertEqual((dup["occurrences"], dup["identifying"], dup["short"]), (2, False, False))
        few_words = ptc.quote_identity("Supercalifragilisticexpialidocious-antidisestablishment", d)
        self.assertIn("words < 6", few_words["reason"])


# --- The gate on in-memory ingests (pure) -----------------------------------------
class CheckCardTests(unittest.TestCase):
    def run_check(self, ingest, card, fuzz=None):
        return lv.check_card(card, ingest, fuzz)

    def test_genuine_pass_and_grade(self):
        ing = mk_ingest([{"anchor": PROSE[1]}, {"anchor": PROSE[2]}, {"anchor": PROSE[3]}])
        card = mk_card([cov(1, "The violet ferry carried nineteen patient cartographers"),
                        cov(2, "relies on natural-language summaries of each imaginary voyage"),
                        cov(3, "Table 2 reports -0.087* (0.044) and 1,204 boats")],
                       [{"claim_id": "C1", "page": 3, "quote": "reports −0.087* (0.044) and 1,204 boats with .05",
                         "numbers": ["-0.087", "(0.044)", "1,204", "0.05"], "source": "text"}])
        r = self.run_check(ing, card)
        self.assertEqual((r["verdict"], r["evidence_grade_suggested"]), ("PASS", "FULL_TEXT_VERIFIED"), r["failures"])
        self.assertEqual(statuses(r, "claim_number"), ["NUMBER_OK"] * 4)
        self.assertIn("PASS_SKELETON", statuses(r, "coverage_anchor"))
        for it in r["items"]:
            for k in ("page", "claim_id", "quote", "tier", "score", "reason", "severity"):
                self.assertIn(k, it)

    def test_missing_page_out_of_range_and_fabricated_extra_anchor(self):
        ing = mk_ingest([{"anchor": PROSE[1]}, {"anchor": PROSE[2]}])
        r = self.run_check(ing, mk_card([cov(1, "The violet ferry carried nineteen patient cartographers"),
                                         cov(3, "x")]))
        self.assertEqual(r["verdict"], "FAIL")
        self.assertIn("MISSING_PAGE", statuses(r, "coverage"))
        self.assertIn("PAGE_OUT_OF_RANGE", statuses(r, "coverage"))
        card = mk_card([cov(1, "The violet ferry carried nineteen patient cartographers",
                            "An invented anchor sentence that the reader never saw on this page"),
                        cov(2, "relies on natural-language summaries of each imaginary voyage")])
        r = self.run_check(ing, card)
        self.assertEqual(r["verdict"], "FAIL")
        self.assertIn("NOT_FOUND", statuses(r, "coverage_anchor"))

    def test_extra_non_identifying_anchor_on_covered_page_is_a_warning(self):
        ing = mk_ingest([{"anchor": PROSE[1]}])
        r = self.run_check(ing, mk_card([cov(1, "The violet ferry carried nineteen patient cartographers",
                                             "violet ferry")]))
        self.assertEqual(r["verdict"], "PASS")
        self.assertEqual(r["counts"]["warning"], 1)

    def test_qb_page_classes(self):
        self.assertEqual(lv.classify_page({"flags": [], "evidence": {}}, [])[0], "normal")
        self.assertEqual(lv.classify_page({"flags": ["scanned"], "evidence": SCANNED_EVIDENCE}, [])[0], "scanned")
        sparse = {"flags": ["figure", "scanned"],
                  "evidence": {"figure": ["caption: Figure 1", "pdfimages: image 400x300 px covers 53% x 31% of the "
                                                               "page"]}}
        cls, area, _ = lv.classify_page(sparse, [])
        self.assertEqual((cls, round(area, 4)), ("sparse", 0.1643))
        self.assertEqual(lv.classify_page({"flags": ["scanned"], "evidence": {
            "figure": ["pdfimages: image 1275x1650 px covers 78% x 78% of the page"]}}, [])[0], "scanned")   # 0.61
        self.assertEqual(lv.classify_page({"flags": ["scanned"], "evidence": {}}, [])[0], "sparse")
        self.assertEqual(lv.classify_page({"flags": ["scanned"], "evidence": {}}, ["pdfimages", "pdfplumber"])[0],
                         "scanned")                                      # unknown -> conservative

    def test_sparse_page_short_anchor_does_not_cap_or_fail(self):
        ing = mk_ingest([{"anchor": PROSE[1]}, {"anchor": "Figure 2: Gulls by tide\n\f", "flags": ["scanned"]}])
        r = self.run_check(ing, mk_card([cov(1, "The violet ferry carried nineteen patient cartographers"),
                                         cov(2, "Figure 2: Gulls by tide")]))
        self.assertEqual(r["verdict"], "PASS", r["failures"])
        self.assertIn("COVERED_SPARSE", statuses(r, "coverage"))
        # the same short anchor on a NORMAL page does not cover it
        ing = mk_ingest([{"anchor": PROSE[1]}, {"anchor": "Figure 2: Gulls by tide\n\f"}])
        r = self.run_check(ing, mk_card([cov(1, "The violet ferry carried nineteen patient cartographers"),
                                         cov(2, "Figure 2: Gulls by tide")]))
        self.assertEqual(r["verdict"], "FAIL")
        self.assertIn("NOT_COVERED", statuses(r, "coverage"))
        self.assertIn("NON_IDENTIFYING", statuses(r, "coverage_anchor"))

    def test_duplicated_page_is_covered_by_a_full_length_anchor(self):
        # S3 bake-off: a real scan carried the same page text twice; no anchor
        # on either page can be unique. Synthetic text (every word invented).
        twin = "The amber ferry paid each harbour a prorated share of the invented toll every winter.\n"
        ing = mk_ingest([{"anchor": PROSE[1]}, {"anchor": twin}, {"anchor": twin}])
        q = "The amber ferry paid each harbour a prorated share of the invented toll"
        r = self.run_check(ing, mk_card([cov(1, "The violet ferry carried nineteen patient cartographers"),
                                         cov(2, q), cov(3, q)]))
        self.assertEqual(r["verdict"], "PASS", r["failures"])
        self.assertEqual(statuses(r, "coverage"), ["PASS", "COVERED_DUPLICATE", "COVERED_DUPLICATE"])
        self.assertEqual(r["counts"]["pages_covered"], 3)
        # a SHORT anchor on a duplicated page, and a claim quote, stay non-identifying
        r = self.run_check(ing, mk_card([cov(1, "The violet ferry carried nineteen patient cartographers"),
                                         cov(2, "The amber ferry paid"), cov(3, q)],
                                        [{"claim_id": "C1", "page": 2, "quote": q, "numbers": [], "source": "text"}]))
        self.assertEqual(r["verdict"], "FAIL")
        self.assertIn("NOT_COVERED", statuses(r, "coverage"))
        self.assertEqual(statuses(r, "claim_quote"), ["NON_IDENTIFYING"])
        # a page that HAS a unique line still needs a unique anchor
        ing = mk_ingest([{"anchor": PROSE[1]}, {"anchor": twin + "Only this page names the copper heron.\n"},
                         {"anchor": twin}])
        r = self.run_check(ing, mk_card([cov(1, "The violet ferry carried nineteen patient cartographers"),
                                         cov(2, q), cov(3, q)]))
        self.assertEqual(r["verdict"], "FAIL")
        self.assertEqual(statuses(r, "coverage"), ["PASS", "NOT_COVERED", "COVERED_DUPLICATE"])

    def test_sparse_waiver_needs_a_unique_anchor_when_one_exists(self):
        hdr = "Synthetic Journal, Volume 7\n"
        ing = mk_ingest([{"anchor": hdr + PROSE[1]}, {"anchor": hdr + "Page 2 of 2\n", "flags": ["scanned"]}])
        r = self.run_check(ing, mk_card([cov(1, "The violet ferry carried nineteen patient cartographers"),
                                         cov(2, "Synthetic Journal, Volume 7")]))
        self.assertIn("NOT_COVERED", statuses(r, "coverage"))
        r = self.run_check(ing, mk_card([cov(1, "The violet ferry carried nineteen patient cartographers"),
                                         cov(2, "Page 2 of 2")]))
        self.assertEqual(r["verdict"], "PASS", r["failures"])

    def test_scanned_page_ocr_and_vision_only(self):
        ocr = "SCAN PAGE\nCOMPASS 7314 HERON 2659\nThe calm bay sheltered 41 painted rowing boats.\n"
        ing = mk_ingest([{"anchor": PROSE[1]}, {"anchor": "\f", "ocr": ocr, "flags": ["scanned"],
                                                "evidence": SCANNED_EVIDENCE}])
        base = [cov(1, "The violet ferry carried nineteen patient cartographers")]
        r = self.run_check(ing, mk_card(base + [cov(2, "COMPASS 7314 HERON 2659 The calm bay sheltered 41")],
                                        [{"claim_id": "B1", "page": 2, "quote": "The calm bay sheltered 41 painted "
                                          "rowing boats", "numbers": ["41"], "source": "ocr"},
                                         {"claim_id": "B2", "page": 2, "quote": "HERON 2659 The calm bay sheltered "
                                          "41 painted", "numbers": ["2659"], "source": "both"}]))
        # 1.8.0 part 5: B2's vision reading sits on a truly scanned page, so the card goes to review
        self.assertEqual((r["verdict"], r["evidence_grade_suggested"], r["evidence_grade_if_review_confirmed"]),
                         ("NEEDS_REVIEW", None, "FULL_TEXT_PARTIAL"), r["failures"])
        self.assertEqual([(it["status"], it["claim_id"], it["page"]) for it in r["items"] if it["kind"] == "vision"],
                         [("VISION_ON_SCAN_PAGE", "B2", 2)])
        self.assertIn("PASS_OCR", statuses(r, "coverage"))
        self.assertIn("SCANNED_PAGE", statuses(r, "page"))
        self.assertEqual(statuses(r, "claim_number"), ["NUMBER_OCR_ONLY", "NUMBER_OCR_VISION"])
        labels = [it["label"] for it in r["items"] if it["kind"] == "claim_number"]
        self.assertEqual(labels, ["ocr-only", "ocr+vision"])
        # no OCR text: a vision_only digest covers the page (VISION_ONLY, partial) and, on a scan, goes to
        #   review (1.8.0 part 5); without vision it fails
        ing = mk_ingest([{"anchor": PROSE[1]}, {"anchor": "\f", "flags": ["scanned"], "evidence": SCANNED_EVIDENCE}])
        r = self.run_check(ing, mk_card(base + [cov(2, vision_only=True)]))
        self.assertEqual((r["verdict"], r["evidence_grade_if_review_confirmed"]), ("NEEDS_REVIEW", "FULL_TEXT_PARTIAL"))
        self.assertIn("VISION_ONLY", statuses(r, "coverage"))
        self.assertEqual(statuses(r, "vision"), ["VISION_ON_SCAN_PAGE"])
        r = self.run_check(ing, mk_card(base + [cov(2, vision_only=True)], vision_validated=False))
        self.assertEqual(r["verdict"], "FAIL")
        self.assertIn("VISION_UNAVAILABLE_CLAIM", statuses(r, "vision"))
        r = self.run_check(ing, mk_card(base + [cov(2)]))
        self.assertIn("NOT_COVERED", statuses(r, "coverage"))

    def test_empty_non_scanned_page_is_covered_empty(self):
        ing = mk_ingest([{"anchor": PROSE[1]}, {"anchor": "\f", "flags": ["scanned"]}])
        r = self.run_check(ing, mk_card([cov(1, "The violet ferry carried nineteen patient cartographers"), cov(2)]))
        self.assertEqual(r["verdict"], "PASS")
        self.assertIn("COVERED_EMPTY", statuses(r, "coverage"))

    def test_vision_numbers_precision_and_consistency(self):
        ing = mk_ingest([{"anchor": PROSE[3] + " The estimate was 0.50 in the invented pilot."}])
        c = [cov(1, "Table 2 reports -0.087* (0.044) and 1,204 boats")]
        claims = [{"claim_id": "V1", "page": 1, "quote": None, "numbers": ["31"], "source": "vision"},
                  {"claim_id": "V2", "page": 1, "quote": "The estimate was 0.50 in the invented pilot",
                   "numbers": ["0.5"], "source": "text"}]
        r = self.run_check(ing, mk_card(c, claims))
        self.assertEqual(r["verdict"], "NEEDS_REVIEW")
        self.assertEqual(r["evidence_grade_if_review_confirmed"], "FULL_TEXT_PARTIAL")
        self.assertIn("NUMBER_VISION_ONLY", statuses(r, "claim_number"))
        self.assertIn("NUMBER_PRECISION_DIFFERS", statuses(r, "claim_number"))
        self.assertIn("VISION_ONLY", statuses(r, "claim_quote"))
        r = self.run_check(ing, mk_card(c, claims, vision_mode="off"))
        self.assertEqual(r["verdict"], "FAIL")
        self.assertIn("VISION_UNAVAILABLE_CLAIM", statuses(r, "vision"))
        both = [{"claim_id": "V3", "page": 1, "quote": "reports −0.087* (0.044) and 1,204 boats",
                 "numbers": ["99"], "source": "both"}]
        r = self.run_check(ing, mk_card(c, both))
        self.assertIn("NUMBER_MISSING", statuses(r, "claim_number"))

    def test_identity_integrity(self):
        ing = mk_ingest([{"anchor": PROSE[1]}])
        c = [cov(1, "The violet ferry carried nineteen patient cartographers")]
        r = self.run_check(ing, mk_card(c, src="b" * 64))
        self.assertIn("SOURCE_HASH_MISMATCH", statuses(r))
        r = self.run_check(ing, mk_card(c, key="user_00000002"))
        self.assertIn("PAPER_KEY_MISMATCH", statuses(r))
        r = self.run_check(ing, mk_card(c, ingest_suffix="_a"))
        self.assertEqual((r["verdict"], r["counts"]["warning"]), ("PASS", 1))

    # --- numbers-v2 locality and OCR-layer pages (1.2.0) ---
    TABLE = ("Table 4: Invented harbour counts\nHerons Gulls Terns\n0.31 0.47 0.52\n"
             "The counts in Table 4 were invented for the locality rule of the gate and describe no harbour.\n\f")

    def test_number_inside_quote_ok_elsewhere_on_page_review(self):
        ing = mk_ingest([{"anchor": self.TABLE}])
        c = [cov(1, "The counts in Table 4 were invented for the locality rule")]
        inside = {"claim_id": "N1", "page": 1, "quote": "Table 4: Invented harbour counts Herons Gulls Terns 0.31 0.47",
                  "numbers": ["0.31", "0.47"], "source": "text"}
        r = self.run_check(ing, mk_card(c, [inside]))
        self.assertEqual(r["verdict"], "PASS", r["review_items"])
        self.assertEqual(statuses(r, "claim_number"), ["NUMBER_OK", "NUMBER_OK"])
        # 0.52 is printed on the page but not inside the quote: review, not fail
        far = dict(inside, numbers=["0.52"])
        r = self.run_check(ing, mk_card(c, [far]))
        self.assertEqual((r["verdict"], statuses(r, "claim_number")), ("NEEDS_REVIEW", ["NUMBER_NOT_NEAR_QUOTE"]))
        self.assertEqual(r["evidence_grade_if_review_confirmed"], "FULL_TEXT_VERIFIED")
        self.assertEqual([it["label"] for it in r["items"] if it["kind"] == "claim_number"], ["not-near-quote"])
        # a value absent from the page stays missing (fail); a sign flip of an in-quote value too
        r = self.run_check(ing, mk_card(c, [dict(inside, numbers=["0.48"])]))
        self.assertEqual(statuses(r, "claim_number"), ["NUMBER_MISSING"])
        r = self.run_check(ing, mk_card(c, [dict(inside, numbers=["-0.31"])]))
        self.assertEqual(statuses(r, "claim_number"), ["NUMBER_MISSING"])

    def test_locality_uses_page_tokens_and_spans_and_ocr(self):
        # skeleton ignores "-", so the quote "... -0.31" matches a page that
        # prints 0.31 here; a -0.31 printed elsewhere must not make it local
        ing = mk_ingest([{"anchor": "Synthetic sign page: the heron index was 0.31 in the invented spring survey.\n"
                                    "Elsewhere a different invented index was −0.31 for terns.\n\f"}])
        cl = {"claim_id": "S1", "page": 1, "quote": "the heron index was -0.31 in the invented spring survey",
              "numbers": ["-0.31"], "source": "text"}
        r = self.run_check(ing, mk_card([cov(1, "the heron index was 0.31 in the invented spring survey")], [cl]))
        # 1.6.0 (ladder-v2): the quote's "-0.31" differs from the page's 0.31: the quote is review too
        self.assertEqual(statuses(r, "claim_quote"), ["QUOTE_NUMBERS_DIFFER"])
        self.assertEqual(statuses(r, "claim_number"), ["NUMBER_NOT_NEAR_QUOTE"])
        # a declared span: the number on the next page, inside the crossing quote
        ing = mk_ingest([{"anchor": PROSE[1] + "\nIn the end the invented ferry index reached\n\f"},
                         {"anchor": "0.73 at the northern harbour before dawn.\n\f"}])
        sp = {"claim_id": "S2", "page": 1, "page_end": 2, "numbers": ["0.73"], "source": "text",
              "quote": "the invented ferry index reached 0.73 at the northern harbour"}
        r = self.run_check(ing, mk_card([cov(1, "The violet ferry carried nineteen patient cartographers"),
                                         cov(2, "0.73 at the northern harbour before dawn")], [sp]))
        self.assertEqual(statuses(r, "claim_number"), ["NUMBER_OK"], r["review_items"])
        # OCR lane: locality is checked in the OCR text the number was found in
        ocr = "SCAN PAGE\nCOMPASS 7314 HERON 2659\nThe calm bay sheltered 41 painted rowing boats.\n"
        ing = mk_ingest([{"anchor": PROSE[1]}, {"anchor": "\f", "ocr": ocr, "flags": ["scanned"],
                                                "evidence": SCANNED_EVIDENCE}])
        ocl = {"claim_id": "O1", "page": 2, "quote": "The calm bay sheltered 41 painted rowing boats",
               "numbers": ["41", "7314"], "source": "ocr"}
        r = self.run_check(ing, mk_card([cov(1, "The violet ferry carried nineteen patient cartographers"),
                                         cov(2, "COMPASS 7314 HERON 2659 The calm bay sheltered 41")], [ocl]))
        self.assertEqual(statuses(r, "claim_number"), ["NUMBER_OCR_ONLY", "NUMBER_NOT_NEAR_QUOTE"])

    def test_vision_number_without_a_quote_is_not_local(self):
        ing = mk_ingest([{"anchor": self.TABLE}])
        r = self.run_check(ing, mk_card([cov(1, "The counts in Table 4 were invented for the locality rule")],
                                        [{"claim_id": "V1", "page": 1, "quote": None, "numbers": ["0.52"],
                                          "source": "vision"}]))
        self.assertEqual(statuses(r, "claim_number"), ["NUMBER_NOT_NEAR_QUOTE"])
        self.assertIn("not located", [it for it in r["items"] if it["kind"] == "claim_number"][0]["reason"])

    def test_ocr_layer_page_caps_cited_claims_not_coverage(self):
        layer = {"flags": ["figure", "ocr_layer_suspected"],
                 "evidence": {"ocr_layer_suspected": ["an image covers 100% of the page area (>= 80%)"]}}
        ing = mk_ingest([dict(layer, anchor=self.TABLE), {"anchor": PROSE[1]}])
        c = [cov(1, "The counts in Table 4 were invented for the locality rule"),
             cov(2, "The violet ferry carried nineteen patient cartographers")]
        # coverage only (a falsely flagged cover image): no cap
        r = self.run_check(ing, mk_card(c))
        self.assertEqual(r["verdict"], "PASS", r["partial_items"])
        self.assertEqual([p["ocr_layer"] for p in r["pages"]], [True, False])
        # a claim with a number on that page: partial (PASS_OCR_LAYER + ocr-layer)
        cl = {"claim_id": "L1", "page": 1, "quote": "Table 4: Invented harbour counts Herons Gulls Terns 0.31 0.47",
              "numbers": ["0.31"], "source": "text"}
        r = self.run_check(ing, mk_card(c, [cl]))
        self.assertEqual((r["verdict"], r["evidence_grade_suggested"]), ("PARTIAL", "FULL_TEXT_PARTIAL"))
        self.assertEqual(statuses(r, "claim_quote"), ["PASS_OCR_LAYER"])
        self.assertEqual([it["label"] for it in r["items"] if it["kind"] == "claim_number"], ["ocr-layer"])
        r = self.run_check(ing, mk_card(c, [dict(cl, source="both")]))
        self.assertEqual(statuses(r, "claim_number"), ["NUMBER_OCR_LAYER_VISION"])
        # 1.8.0 part 5: a vision reading on an OCR-layer page goes to review
        self.assertEqual((r["verdict"], statuses(r, "vision")), ("NEEDS_REVIEW", ["VISION_ON_SCAN_PAGE"]))
        # a claim on the other page is unaffected
        r = self.run_check(ing, mk_card(c, [{"claim_id": "P1", "page": 2, "numbers": [], "source": "text",
                                             "quote": "The violet ferry carried nineteen patient cartographers"}]))
        self.assertEqual(r["verdict"], "PASS")

    def test_locality_helpers(self):
        norm, spans = ptc.quote_spans("relies on natural-language summaries", PROSE[2])
        self.assertEqual(len(spans), 1)                                   # skeleton match mapped back
        self.assertEqual(norm[spans[0][0]:spans[0][1]], "relies on naturallanguage summaries")
        skel, idx = ptc.skeleton_index(ptc.normalize("A b-C ß"))
        self.assertEqual((skel, idx), ("abcss", [0, 2, 4, 6, 6]))
        tok = ptc.parse_number("0.47")
        n2, sp = ptc.quote_spans("Herons Gulls Terns 0.31 0.47", self.TABLE)
        self.assertTrue(ptc.number_near_spans(tok, n2, sp, 0))
        self.assertFalse(ptc.number_near_spans(ptc.parse_number("0.52"), n2, sp, 0))
        self.assertTrue(ptc.number_near_spans(ptc.parse_number("0.52"), n2, sp, 6))
        self.assertEqual(ptc.NUMBER_NEAR_CHARS, 0)

    # --- numbers-v3: the unique-row rule (1.3.0); synthetic text, every word invented ---
    R = lv.SELFTEST_PAGES["R"][0]
    R_COV = [cov(1, "The counts in Table 5 are invented to exercise the row rule of the verification gate")]
    R_QUOTE = "North Quay (with tide gauge) North Quay (without tide gauge) All Harbours"

    def r_check(self, claims, page=None):
        return self.run_check(mk_ingest([page or self.R]), mk_card(self.R_COV, claims))

    def number_items(self, r):
        return [it for it in r["items"] if it["kind"] == "claim_number"]

    def test_unique_row_clears_a_column_major_number(self):
        r = self.r_check([{"claim_id": "R1", "page": 1, "quote": self.R_QUOTE, "numbers": ["0.63", "0.62"],
                           "source": "text"}])
        self.assertEqual(r["verdict"], "PASS", r["review_items"])
        self.assertEqual([(it["status"], it["locality"], it["row_match"]) for it in self.number_items(r)],
                         [("NUMBER_OK", "row", "unique")] * 2)
        self.assertEqual(r["pages"][0]["lane_b"], True)

    def test_look_alike_row_goes_to_review(self):
        # 0.74 is printed only in the "(without tide gauge)" row; B6 would have cleared it
        self.assertIsNotNone(ptc.lane_b_row_hit(ptc.parse_number("0.74"), self.R_QUOTE, self.R["lane_b"], 6))
        r = self.r_check([{"claim_id": "R3", "page": 1, "quote": self.R_QUOTE, "numbers": ["0.74"], "source": "text"}])
        self.assertEqual(r["verdict"], "NEEDS_REVIEW")
        it = self.number_items(r)[0]
        self.assertEqual((it["status"], it["locality"], it["row_match"]), ("NUMBER_NOT_NEAR_QUOTE", None, "unique"))
        self.assertIn("does not print it", it["reason"])

    def test_same_row_other_column_is_a_documented_residual(self):
        # a fabricated Spring value equal to the Autumn cell of the same row clears (residual a)
        r = self.r_check([{"claim_id": "R2", "page": 1, "quote": self.R_QUOTE, "numbers": ["0.63"], "source": "text",
                           "claim": "Spring count 0.63"}])
        self.assertEqual((r["verdict"], self.number_items(r)[0]["locality"]), ("PASS", "row"))
        # a value no cell of the page prints still fails, and so does a sign flip
        r = self.r_check([{"claim_id": "R2", "page": 1, "quote": self.R_QUOTE, "numbers": ["0.64", "-0.63"],
                           "source": "text"}])
        self.assertEqual(statuses(r, "claim_number"), ["NUMBER_MISSING", "NUMBER_MISSING"])

    def test_ambiguous_or_missing_label_falls_back_to_in_quote(self):
        q = "All Harbours All Harbours Spring 0.62 0.71 0.55"
        r = self.r_check([{"claim_id": "R4", "page": 1, "quote": q, "numbers": ["0.41", "0.55"], "source": "text"}])
        items = self.number_items(r)
        self.assertEqual([(it["status"], it["locality"], it["row_match"]) for it in items],
                         [("NUMBER_NOT_NEAR_QUOTE", None, "ambiguous"), ("NUMBER_OK", "in-quote", "ambiguous")])
        self.assertIn("matches 2 lane B rows", items[0]["reason"])
        # no lane B on the page: the row path is simply absent (as for every v1 ingest without lane B)
        r = self.r_check([{"claim_id": "R1", "page": 1, "quote": self.R_QUOTE, "numbers": ["0.63"], "source": "text"}],
                         page=dict(self.R, lane_b=None))
        it = self.number_items(r)[0]
        self.assertEqual((it["status"], it["row_match"], r["pages"][0]["lane_b"]), ("NUMBER_NOT_NEAR_QUOTE", None,
                                                                                     False))

    def test_row_path_needs_an_anchor_quote_pass(self):
        # a quote copied from lane B (row-major) is not on the column-major anchor: no row path
        r = self.r_check([{"claim_id": "R5", "page": 1, "quote": "North Quay (with tide gauge) 0.62 0.63 North Quay",
                           "numbers": ["0.63"], "source": "text"}])
        self.assertIn(statuses(r, "claim_quote")[0], ("NOT_FOUND", "NEAR"))
        self.assertIsNone(self.number_items(r)[0]["row_match"])

    def test_v1_card_without_table_rows_checks_as_before(self):
        # a 1.2.0-style card on a prose page: in-quote locality, row_match "none"
        ing = mk_ingest([{"anchor": PROSE[3], "lane_b": PROSE[3]}])
        card = mk_card([cov(1, "Table 2 reports -0.087* (0.044) and 1,204 boats")],
                       [{"claim_id": "C1", "page": 1, "quote": "reports −0.087* (0.044) and 1,204 boats with .05",
                         "numbers": ["-0.087", "1,204"], "source": "text"}])
        r = self.run_check(ing, card)
        self.assertEqual(r["verdict"], "PASS", r["failures"])
        # numbers-v4: a prose page (not flagged table/numeric) never takes the row path
        self.assertEqual({(it["locality"], it["row_match"]) for it in self.number_items(r)},
                         {("in-quote", "ineligible")})

    def test_quote_row_label_rules(self):
        lane_b = "Not 288 321\nNotes on the invented ferries 4 5\nCo-teaching group 0.31 0.33\n7. Gender (Girls) 0.50 0.52\n"
        self.assertEqual(ptc.quote_row("Notes on the invented ferries and their harbours", [lane_b])["status"], "unique")
        self.assertEqual(ptc.quote_row("Notes on the invented ferries", [lane_b])["row"]["label"],
                         "notesontheinventedferries")                        # row "Not" does not match "Notes"
        self.assertEqual(ptc.quote_row("Not one invented ferry crossed the harbour", [lane_b])["row"]["label"],
                         "not")
        # numbers-v4: a 2-letter label is no longer a row
        self.assertEqual(ptc.quote_row("No invented ferry crossed the harbour", ["No 288 321\n"])["status"], "none")
        hit = ptc.quote_row("Coteaching group and the invented control group", [lane_b])
        self.assertEqual((hit["status"], hit["row"]["label"]), ("unique", "coteachinggroup"))   # fused hyphen
        hit = ptc.quote_row("Gender (Girls) Gender (Boys) invented rows", [lane_b])
        self.assertTrue(hit["status"] == "unique" and ptc.number_in_row(ptc.parse_number("0.52"), hit["row"]))
        self.assertFalse(ptc.number_in_row(ptc.parse_number("7"), hit["row"]))     # the row index is not a cell
        self.assertEqual(ptc.quote_row("An invented sentence with no row label", [lane_b])["status"], "none")

    def test_reading_aid_quote_is_not_a_pass(self):
        # Reading aid (pdf_ingest 1.1.0): a line copied verbatim from the reading aid carries the prefix no page prints
        aid, _ = pdf_ingest.reading_aid_body(self.R["lane_b"])
        line = next(ln for ln in aid.split("\n") if "with tide gauge" in ln)
        r = self.r_check([{"claim_id": "A1", "page": 1, "quote": line, "numbers": [], "source": "text"}])
        self.assertEqual(statuses(r, "claim_quote"), ["NOT_FOUND"])
        r = self.run_check(mk_ingest([self.R]), mk_card(self.R_COV, [
            {"claim_id": "A2", "page": 1, "quote": line[len(pdf_ingest.READING_AID_PREFIX):], "numbers": [],
             "source": "text"}]), fuzz=fuzz_mod() if HAVE_FUZZ else None)
        self.assertEqual(statuses(r, "claim_quote"), ["NOT_FOUND"])

    def test_span_skips_recorded_header_footer(self):
        hf = [{"position": "bottom", "pattern": "page # of #", "pages": [1, 2]},
              {"position": "top", "pattern": "synthetic journal, volume #", "pages": [1, 2]}]
        p1 = "Synthetic Journal, Volume 7\n" + PROSE[1] + "\nIn the end the long voyage ended when the\nPage 1 of 2\n\f"
        p2 = "Synthetic Journal, Volume 7\ncrew reached the northern harbour at dawn.\nPage 2 of 2\n\f"
        ing = mk_ingest([{"anchor": p1}, {"anchor": p2}], header_footer=hf)
        card = mk_card([cov(1, "The violet ferry carried nineteen patient cartographers"),
                        cov(2, "crew reached the northern harbour at dawn")],
                       [{"claim_id": "S1", "page": 1, "page_end": 2, "numbers": [], "source": "text",
                         "quote": "the long voyage ended when the crew reached the northern harbour"}])
        r = self.run_check(ing, card)
        self.assertEqual(r["verdict"], "PASS", r["failures"])
        self.assertIn("PASS_SPAN", statuses(r, "claim_quote"))
        card["claims"][0].pop("page_end")
        self.assertIn("WRONG_PAGE", statuses(self.run_check(ing, card), "claim_quote"))


# --- arXiv HTML ingests (1.4.0): card v2 on in-memory unit ingests (pure) ---
# Every word below is invented (no third-party text).
UNITS = [
    {"label": "front", "flags": ["sparse"],
     "anchor": "The Invented Harbour Ledger\nAbstract\nThe violet ferry carried nineteen patient cartographers across "
               "the silver estuary.\n"},
    {"label": "1", "anchor": "1 Harbour tides\nThe crew logged a tide index of 207 on the quiet morning before the "
                             "gulls returned to the harbour wall.\nIn the end the invented ferry index reached\n"},
    {"label": "1.1", "flags": ["table"],
     "anchor": "0.73 at the northern harbour before dawn, and nobody on board had crossed that water before.\n"
               "Table 1: Invented tide counts\nHarbour\tSpring\tAutumn\tWinter\nNorth Quay beside the old harbour "
               "office\t0.62\t-0.087\t0.33\nSouth Quay\t0.41\t1,204\t0.18\n",
     "rows": "Harbour\tSpring\tAutumn\tWinter\nNorth Quay beside the old harbour office\t0.62\t-0.087\t0.33\n"
             "South Quay\t0.41\t1,204\t0.18\n"},
    {"label": "2", "flags": ["conversion_error"],
     "anchor": "2 Method\nA broken macro \\midsloppy weighted each quay by its 23 painted bollards before pooling the "
               "counts.\n"},
    {"label": "bib", "flags": ["sparse"], "anchor": "References\nInvented, A. (2025). A ledger of tides.\n"},
]


def mk_unit_ingest(units=UNITS, key="user_00000001", src="a" * 64, version="v2"):
    # An in-memory arXiv HTML ingest equivalent to load_unit_ingest()'s dict.
    return {"anchor_kind": "arxiv_html", "paper_key": key, "dir_key": key, "suffix": "",
            "manifest_name": "ingest_manifest.json", "manifest_sha256": "0" * 64, "source_sha256": src,
            "page_count": None, "unit_count": len(units), "source_version": version,
            "arxiv_id_version": "2601.00001" + version, "html_extract_version": "arxiv-html-v1",
            "pdf_ingest_tool_version": "test", "normalize_version": ptc.NORMALIZE_VERSION, "header_footer": [],
            "lanes_unavailable": [],
            "pages": {i: {"anchor_text": u["anchor"], "ocr_text": None, "lane_b_text": u.get("rows"),
                          "flags": u.get("flags", []), "evidence": {}, "label": u["label"], "latexml_id": None,
                          "section_class": "ltx_section"} for i, u in enumerate(units, 1)}}


def mk_html_card(coverage, claims=(), key="user_00000001", src="a" * 64, version="v2", **over):
    card = {"schema_version": "lit-verify-card-v2", "paper_key": key, "anchor_kind": "arxiv_html", "source_sha256": src,
            "source_version": version, "reader_model": "test", "vision_mode": "off", "vision_validated": False,
            "vision_list_version": None, "coverage": list(coverage), "claims": list(claims)}
    card.update(over)
    return card


def sec(label, *anchors, **extra):
    return dict({"section": label, "anchors": list(anchors), "summary": "s"}, **extra)


H_COV = [sec("front", "The violet ferry carried nineteen patient cartographers"),
         sec("1", "The crew logged a tide index of 207 on the quiet morning"),
         sec("1.1", "nobody on board had crossed that water before"),
         sec("2", "weighted each quay by its 23 painted bollards before pooling"),
         sec("bib", "Invented, A. (2025). A ledger of tides.")]
ROW_QUOTE = "North Quay beside the old harbour office 0.62 -0.087"


def hclaim(cid, section, quote, numbers=(), **extra):
    return dict({"claim_id": cid, "section": section, "quote": quote, "numbers": list(numbers), "source": "text"},
                **extra)


class HtmlCheckTests(unittest.TestCase):
    def run_check(self, card, ingest=None, fuzz=None):
        return lv.check_card(card, ingest or mk_unit_ingest(), fuzz)

    def nums(self, r):
        return [it for it in r["items"] if it["kind"] == "claim_number"]

    def test_genuine_card_passes_with_section_locators(self):
        r = self.run_check(mk_html_card(H_COV, [hclaim("T1", "1.1", ROW_QUOTE + " 0.33", ["0.62", "-0.087", "0.33"])]))
        self.assertEqual((r["verdict"], r["evidence_grade_suggested"]), ("PASS", "FULL_TEXT_VERIFIED"), r["failures"])
        self.assertEqual(statuses(r, "coverage"), ["PASS", "PASS", "PASS", "PASS", "COVERED_SPARSE"])
        self.assertEqual([(it["status"], it["locality"]) for it in self.nums(r)], [("NUMBER_OK", "in-quote")] * 3)
        for it in r["items"]:
            self.assertIsNone(it["page"])
            self.assertIn("section_end", it)
        self.assertEqual({it["section"] for it in r["items"] if it["kind"] == "coverage"}, {"front", "1", "1.1", "2",
                                                                                          "bib"})
        self.assertEqual(r["pages"], [])
        self.assertEqual([(s["section"], s["class"], s["conversion_error"], s["table_rows"]) for s in r["sections"]],
                         [("front", "sparse", False, False), ("1", "normal", False, False), ("1.1", "normal", False, True),
                          ("2", "normal", True, False), ("bib", "sparse", False, False)])
        self.assertEqual((r["counts"]["sections"], r["counts"]["sections_covered"], r["vision_available"]), (5, 5, False))
        self.assertTrue(lv.summary_line(next(it for it in r["items"] if it["kind"] == "coverage")).startswith(
            "PASS sec front"))

    def test_anchor_kind_mismatch_both_ways(self):
        r = self.run_check(mk_card([cov(1, "The violet ferry carried nineteen patient cartographers")]))
        self.assertEqual((r["verdict"], statuses(r)), ("FAIL", ["ANCHOR_KIND_MISMATCH"]))
        self.assertEqual((r["sections"], r["counts"]["sections"]), ([], 5))
        r = lv.check_card(mk_html_card(H_COV), mk_ingest([{"anchor": PROSE[1]}]), None)
        self.assertEqual((r["verdict"], statuses(r)), ("FAIL", ["ANCHOR_KIND_MISMATCH"]))

    def test_source_version_section_not_found_and_missing_section(self):
        r = self.run_check(mk_html_card(H_COV, version="v1"))
        self.assertEqual((r["verdict"], statuses(r, "integrity")), ("FAIL", ["SOURCE_VERSION_MISMATCH"]))
        r = self.run_check(mk_html_card(H_COV[:4] + [sec("9.9", "x")], [hclaim("C1", "7", ROW_QUOTE),
                                                                         hclaim("C2", "1", ROW_QUOTE, section_end="8")]))
        self.assertEqual(r["verdict"], "FAIL")
        self.assertEqual(statuses(r, "coverage"), ["SECTION_NOT_FOUND", "PASS", "PASS", "PASS", "PASS",
                                                   "MISSING_SECTION"])
        self.assertEqual([(it["section"], it["section_end"]) for it in r["items"] if it["kind"] == "claim"],
                         [("7", None), ("1", "8")])
        self.assertEqual(statuses(r, "claim"), ["SECTION_NOT_FOUND", "SECTION_NOT_FOUND"])

    def test_wrong_section_and_section_end_spans(self):
        r = self.run_check(mk_html_card(H_COV, [hclaim("W1", "1", ROW_QUOTE + " 0.33")]))
        it = next(it for it in r["items"] if it["kind"] == "claim_quote")
        self.assertEqual((it["status"], it["found_on"], it["section"]), ("WRONG_SECTION", ["1.1"], "1"))
        self.assertIn("other section(s): ['1.1']", it["reason"])
        q = "the invented ferry index reached 0.73 at the northern harbour"
        r = self.run_check(mk_html_card(H_COV, [hclaim("S1", "1", q, ["0.73"], section_end="1.1")]))
        self.assertEqual(r["verdict"], "PASS", r["failures"])
        it = next(it for it in r["items"] if it["kind"] == "claim_quote")
        self.assertEqual((it["status"], it["section"], it["section_end"]), ("PASS_SPAN", "1", "1.1"))
        self.assertEqual(statuses(r, "claim_number"), ["NUMBER_OK"])
        self.assertEqual(statuses(self.run_check(mk_html_card(H_COV, [hclaim("S1", "1", q)])), "claim_quote"),
                         ["WRONG_SECTION"])                                   # undeclared span
        r = self.run_check(mk_html_card(H_COV, [hclaim("S1", "1", q, section_end="2")]))
        self.assertEqual((statuses(r, "claim"), statuses(r, "claim_quote")), (["SECTION_END_NOT_NEXT"], ["WRONG_SECTION"]))
        self.assertIn("not the unit after section '1'", next(it for it in r["items"] if it["kind"] == "claim")["reason"])

    def test_conversion_error_caps_claims_not_coverage(self):
        q = "weighted each quay by its 23 painted bollards before pooling"
        r = self.run_check(mk_html_card(H_COV, [hclaim("E1", "2", q, ["23"])]))
        self.assertEqual((r["verdict"], r["evidence_grade_suggested"]), ("PARTIAL", "FULL_TEXT_PARTIAL"))
        self.assertEqual(statuses(r, "claim_quote"), ["PASS_CONVERSION_ERROR"])
        self.assertEqual([(it["status"], it["label"]) for it in self.nums(r)],
                         [("NUMBER_CONVERSION_ERROR", "conversion-error")])
        self.assertIn("conversion errors", self.nums(r)[0]["reason"])
        self.assertEqual(self.run_check(mk_html_card(H_COV))["verdict"], "PASS")   # coverage alone: no cap
        # a failing quote in that unit is not softened
        r = self.run_check(mk_html_card(H_COV, [hclaim("E2", "2", "an invented sentence that this section never "
                                                                  "prints anywhere")]))
        self.assertEqual(statuses(r, "claim_quote"), ["NOT_FOUND"])

    def test_row_path_uses_the_rows_file(self):
        r = self.run_check(mk_html_card(H_COV, [hclaim("R1", "1.1", ROW_QUOTE, ["0.33"])]))
        self.assertEqual(r["verdict"], "PASS", r["review_items"])
        it = self.nums(r)[0]
        self.assertEqual((it["status"], it["locality"], it["row_match"]), ("NUMBER_OK", "row", "unique"))
        self.assertIn("table row", it["reason"])
        units = [dict(u, rows=None) if u["label"] == "1.1" else u for u in UNITS]   # rows unavailable (hash mismatch)
        r = self.run_check(mk_html_card(H_COV, [hclaim("R1", "1.1", ROW_QUOTE, ["0.33"])]), mk_unit_ingest(units))
        it = self.nums(r)[0]
        self.assertEqual((it["status"], it["row_match"]), ("NUMBER_NOT_NEAR_QUOTE", None))
        self.assertIn("cited section(s)", it["reason"])
        # a value from the other row is not local; a value no section prints is missing, with the label shown
        r = self.run_check(mk_html_card(H_COV, [hclaim("R2", "1.1", ROW_QUOTE, ["0.18", "0.99", "23"])]))
        self.assertEqual(statuses(r, "claim_number"), ["NUMBER_NOT_NEAR_QUOTE", "NUMBER_MISSING", "NUMBER_MISSING"])
        self.assertIn("found in section(s) ['2']", self.nums(r)[2]["reason"])

    def test_sparse_waiver_duplicate_rule_and_cross_unit_uniqueness(self):
        # a short exact anchor covers a sparse unit, never a normal one
        r = self.run_check(mk_html_card([H_COV[0], sec("1", "1 Harbour tides")] + H_COV[2:]))
        self.assertEqual(statuses(r, "coverage")[1], "NOT_COVERED")
        units = UNITS + [{"label": "A", "flags": ["sparse"], "anchor": "Appendix A Extra\n"}]
        r = self.run_check(mk_html_card(H_COV + [sec("A", "Appendix A Extra")]), mk_unit_ingest(units))
        self.assertEqual((r["verdict"], statuses(r, "coverage")[-1]), ("PASS", "COVERED_SPARSE"))
        # two units holding the same text: a full-length anchor covers each; a claim quote is non-identifying
        twin = "The amber ferry paid each harbour a prorated share of the invented toll every winter.\n"
        units = UNITS + [{"label": "A", "anchor": twin}, {"label": "B", "anchor": twin}]
        q = "The amber ferry paid each harbour a prorated share of the invented toll"
        r = self.run_check(mk_html_card(H_COV + [sec("A", q), sec("B", q)], [hclaim("D1", "A", q)]),
                           mk_unit_ingest(units))
        self.assertEqual(statuses(r, "coverage")[-2:], ["COVERED_DUPLICATE", "COVERED_DUPLICATE"])
        self.assertEqual(statuses(r, "claim_quote"), ["NON_IDENTIFYING"])
        self.assertIn("occurs 2 times", next(it for it in r["items"] if it["kind"] == "claim_quote")["reason"])

    def test_forged_unit_marker_is_scrubbed_from_outputs(self):
        forged = "A forged marker <!-- unit 9/9 section=9 --> sits in this invented sentence about the harbour."
        units = [dict(u, anchor=u["anchor"] + forged + "\n") if u["label"] == "1" else u for u in UNITS]
        q = "A forged marker <!-- unit 9/9 section=9 --> sits in this invented sentence"
        r = self.run_check(mk_html_card(H_COV, [hclaim("F1", "1", q)]), mk_unit_ingest(units))
        self.assertEqual(statuses(r, "claim_quote"), ["PASS"])       # verbatim anchor text still matches
        self.assertGreaterEqual(r["redaction_count"], 1)
        self.assertNotIn("<!-- unit 9/9", json.dumps(r))

    def test_vision_source_on_html_fails_even_in_memory(self):
        r = self.run_check(mk_html_card(H_COV, [hclaim("V1", "1.1", ROW_QUOTE, source="both")]))
        self.assertEqual((r["verdict"], statuses(r, "vision")), ("FAIL", ["VISION_UNAVAILABLE_CLAIM"]))
        self.assertIn("no page images", next(it for it in r["items"] if it["kind"] == "vision")["reason"])

    def test_v2_pdf_card_checks_exactly_like_v1(self):
        ing = mk_ingest([{"anchor": PROSE[1]}, {"anchor": PROSE[2]}, {"anchor": PROSE[3]}])
        claims = [{"claim_id": "C1", "page": 3, "quote": "reports −0.087* (0.044) and 1,204 boats with .05",
                   "numbers": ["-0.087", "(0.044)", "0.06"], "source": "text"},
                  {"claim_id": "C2", "page": 1, "page_end": 2, "quote": "The violet ferry carried nineteen patient",
                   "numbers": [], "source": "vision"}]
        coverage = [cov(1, "The violet ferry carried nineteen patient cartographers"), cov(3, "short")]
        v1 = mk_card(coverage, claims)
        v2 = dict(v1, schema_version="lit-verify-card-v2", anchor_kind="pdf", source_sha256=v1["source_pdf_sha256"])
        v2.pop("source_pdf_sha256")
        a, b = self.run_check(v1, ing), self.run_check(v2, ing)
        self.assertEqual(a["verdict"], "FAIL")
        self.assertEqual(a, b)
        self.assertTrue(all(it["section"] is None and it["section_end"] is None for it in a["items"]))


# --- 1.5.0: the column-not-checked label on cleared numbers (pure; every word invented) ---
class ColumnLabelTests(unittest.TestCase):
    TABLE = CheckCardTests.TABLE
    T_COV = [cov(1, "The counts in Table 4 were invented for the locality rule")]
    T_QUOTE = "Table 4: Invented harbour counts Herons Gulls Terns 0.31 0.47"

    def nums(self, r):
        return [it for it in r["items"] if it["kind"] == "claim_number"]

    def cols(self, r):
        return [(it["number"], it["column_checked"], it["column_label"], it["column_values"]) for it in self.nums(r)]

    def one_page(self, anchor, quote, numbers, **page):
        ing = mk_ingest([dict({"anchor": anchor}, **page)])
        anchor_cov = next(s for s in anchor.split("\n") if len(s) > 45)
        return lv.check_card(mk_card([cov(1, anchor_cov)], [{"claim_id": "K1", "page": 1, "quote": quote,
                                                             "numbers": list(numbers), "source": "text"}]), ing, None)

    def test_multi_number_quote_is_labeled_single_number_is_checked(self):
        r = lv.check_card(mk_card(self.T_COV, [{"claim_id": "K1", "page": 1, "quote": self.T_QUOTE,
                                                "numbers": ["0.31"], "source": "text"}]), mk_ingest([{"anchor": self.TABLE}]),
                          None)
        self.assertEqual(r["verdict"], "PASS", r["review_items"])                     # a label is not a verdict
        it = self.nums(r)[0]
        self.assertEqual((it["status"], it["locality"], it["severity"], it["label"]), ("NUMBER_OK", "in-quote", "pass",
                                                                                         "ok"))
        self.assertEqual(self.cols(r), [("0.31", False, "column-not-checked", 2)])
        self.assertEqual((it["column_severity"], r["counts"]["numbers_column_not_checked"]), ("label", 1))
        self.assertEqual(len(r["column_not_checked_items"]), 1)
        # an ordinary prose sentence with one number is checked
        prose = "Synthetic prose page: the heron index was 0.31 in the invented spring survey of the bay.\n\f"
        r = self.one_page(prose, "the heron index was 0.31 in the invented spring survey", ["0.31"])
        self.assertEqual((self.cols(r), r["counts"]["numbers_column_not_checked"], r["column_not_checked_items"]),
                         ([("0.31", True, None, 1)], 0, []))

    def test_token_definition_edge_cases(self):
        # shapes: an integer count is not a candidate for a coefficient, and the reverse;
        # the "1" of "Table 2" would not count anyway (a reference number)
        q3 = "reports −0.087* (0.044) and 1,204 boats with .05"
        r = self.one_page(PROSE[3], q3, ["-0.087", "(0.044)", "1,204", "0.05"])
        self.assertEqual([(n, c, v) for n, c, _, v in self.cols(r)],
                         [("-0.087", False, 3), ("(0.044)", False, 3), ("1,204", True, 1), ("0.05", False, 3)])
        # years and reference numbers ("Table 4", "page 3") are not cells; a claim that is itself a
        #   year counts the other integers (here 41) as candidates
        page = "Synthetic ledger line: in 2019 the keepers of Table 4 listed 41 invented boats on page 3 of the log.\n\f"
        q = "in 2019 the keepers of Table 4 listed 41 invented boats on page 3"
        r = self.one_page(page, q, ["41", "2019"])
        self.assertEqual([(n, c, v) for n, c, _, v in self.cols(r)], [("41", True, 1), ("2019", False, 2)])
        # the claim's own value printed twice counts once; another value makes it ambiguous
        page = "Synthetic row page: Amber lantern quay 0.57 0.57 was the only invented row the keepers kept.\n\f"
        r = self.one_page(page, "Amber lantern quay 0.57 0.57 was the only invented row", ["0.57"])
        self.assertEqual(self.cols(r), [("0.57", True, None, 1)])
        page = "Synthetic row page: Amber lantern quay 0.57 0.59 0.57 was the only invented row the keepers kept.\n\f"
        r = self.one_page(page, "Amber lantern quay 0.57 0.59 0.57 was the only invented row", ["0.57"])
        self.assertEqual(self.cols(r), [("0.57", False, "column-not-checked", 2)])
        # a plain-space thousands group read as the claim is the claim itself, not two cells
        page = "Synthetic fleet page: the invented fleet counted 1 204 boats on the northern quay that winter.\n\f"
        r = self.one_page(page, "the invented fleet counted 1 204 boats on the northern quay", ["1,204"])
        self.assertEqual(self.cols(r), [("1,204", True, None, 1)])
        # percent is its own shape
        page = "Synthetic share page: 45% of the 120 invented boats and 52% of the gulls left the quay early.\n\f"
        r = self.one_page(page, "45% of the 120 invented boats and 52% of the gulls left", ["45%", "120"])
        self.assertEqual([(n, c, v) for n, c, _, v in self.cols(r)], [("45%", False, 2), ("120", True, 1)])

    def test_helper_directly(self):
        tok = ptc.parse_number("0.59")
        line = ptc.normalize("Overage (invented) 0.58 0.57 0.59 0.56 0.55 0.57")
        self.assertEqual(ptc.column_values(tok, line, 0, len(line)), 5)
        self.assertIsNone(ptc.column_values(ptc.parse_number("0.60"), line, 0, len(line)))   # not printed: no label
        self.assertEqual(ptc.column_values(tok, line, line.index("0.59"), line.index("0.59") + 4), 1)
        for text, ref in (("Fig. 2", True), ("p. 14", True), ("pp. 14", True), ("Grade 3", False), ("Table 0.5", False)):
            toks = ptc.parse_numbers(text)
            self.assertEqual(ptc.column_is_reference(toks[-1], text), ref, text)
        self.assertTrue(ptc.column_is_year(ptc.parse_numbers("in 1987")[0]))
        self.assertFalse(ptc.column_is_year(ptc.parse_numbers("1,987 boats")[0]))
        self.assertFalse(ptc.column_is_year(ptc.parse_numbers("7314")[0]))

    def test_row_path_multi_number_labeled_single_number_checked(self):
        R = lv.SELFTEST_PAGES["R"][0]
        r = lv.check_card(mk_card(CheckCardTests.R_COV, [{"claim_id": "R1", "page": 1, "quote": CheckCardTests.R_QUOTE,
                                                           "numbers": ["0.63"], "source": "text"}]), mk_ingest([R]), None)
        self.assertEqual((r["verdict"], self.nums(r)[0]["locality"]), ("PASS", "row"))
        self.assertEqual(self.cols(r), [("0.63", False, "column-not-checked", 2)])
        # a column-major page whose identified row prints one number
        anchor = ("Table 6: Invented bell counts\nHarbour\nEast Pier beside the old copper bell\nWest Pier\nBells\n"
                  "0.44\n0.29\nThe bell counts in Table 6 are invented for the column label of the gate.\n\f")
        lane_b = ("Table 6: Invented bell counts\nHarbour Bells\nEast Pier beside the old copper bell 0.44\nWest Pier 0.29\n"
                  "The bell counts in Table 6 are invented for the column label of the gate.\n")
        ing = mk_ingest([{"anchor": anchor, "lane_b": lane_b, "flags": ["table"]}])   # numbers-v4: a table page
        r = lv.check_card(mk_card([cov(1, "The bell counts in Table 6 are invented for the column label")],
                                  [{"claim_id": "B1", "page": 1, "quote": "East Pier beside the old copper bell West Pier "
                                                                         "Bells", "numbers": ["0.44"], "source": "text"}]),
                          ing, None)
        self.assertEqual((r["verdict"], self.nums(r)[0]["locality"], self.nums(r)[0]["row_match"]),
                         ("PASS", "row", "unique"), r["review_items"])
        self.assertEqual(self.cols(r), [("0.44", True, None, 1)])

    def test_null_where_no_locality(self):
        claim = {"claim_id": "K1", "page": 1, "quote": self.T_QUOTE, "numbers": ["0.52", "0.48", "zero", "0.310"],
                 "source": "text"}
        r = lv.check_card(mk_card(self.T_COV, [claim]), mk_ingest([{"anchor": self.TABLE}]), None)
        self.assertEqual(statuses(r, "claim_number"), ["NUMBER_NOT_NEAR_QUOTE", "NUMBER_MISSING", "NUMBER_UNPARSEABLE",
                                                       "NUMBER_PRECISION_DIFFERS"])
        for it in self.nums(r):
            self.assertEqual((it["column_checked"], it["column_label"], it["column_values"], it["column_severity"]),
                             (None, None, None, None), it["status"])
        # a vision number without a quote: no clearing text
        r = lv.check_card(mk_card(self.T_COV, [{"claim_id": "V1", "page": 1, "quote": None, "numbers": ["0.47"],
                                                "source": "vision"}]), mk_ingest([{"anchor": "\f", "flags": ["scanned"],
                                                                                   "evidence": SCANNED_EVIDENCE}]), None)
        self.assertEqual([(it["status"], it["column_checked"]) for it in self.nums(r)], [("NUMBER_VISION_ONLY", None)])

    def test_ocr_lane_uses_the_ocr_span(self):
        ocr = "SCAN PAGE\nCOMPASS 7314 HERON 2659\nThe calm bay sheltered 41 painted rowing boats.\n"
        ing = mk_ingest([{"anchor": PROSE[1]}, {"anchor": "\f", "ocr": ocr, "flags": ["scanned"],
                                                "evidence": SCANNED_EVIDENCE}])
        c = [cov(1, "The violet ferry carried nineteen patient cartographers"),
             cov(2, "COMPASS 7314 HERON 2659 The calm bay sheltered 41")]
        for quote, want in (("The calm bay sheltered 41 painted rowing boats", ("41", True, None, 1)),
                            ("COMPASS 7314 HERON 2659 The calm bay sheltered 41", ("41", False, "column-not-checked", 3))):
            r = lv.check_card(mk_card(c, [{"claim_id": "O1", "page": 2, "quote": quote, "numbers": ["41"],
                                           "source": "ocr"}]), ing, None)
            self.assertEqual((statuses(r, "claim_number"), self.cols(r)), (["NUMBER_OCR_ONLY"], [want]))
            self.assertEqual(r["verdict"], "PARTIAL")

    def test_verdict_unchanged_and_the_review_hook(self):
        claims = [{"claim_id": "K1", "page": 1, "quote": self.T_QUOTE, "numbers": ["0.31", "0.47"], "source": "text"}]
        ing = mk_ingest([{"anchor": self.TABLE}])
        r = lv.check_card(mk_card(self.T_COV, claims), ing, None)
        self.assertEqual((r["verdict"], r["evidence_grade_suggested"], r["review_items"]), ("PASS", "FULL_TEXT_VERIFIED",
                                                                                            []))
        self.assertEqual((r["counts"]["review"], r["counts"]["numbers_column_not_checked"]), (0, 2))
        self.assertNotIn("label", {it["severity"] for it in r["items"]})
        # the hook: flipping the constant routes labeled numbers to review, nothing else changes
        with mock.patch.object(lv, "COLUMN_UNCHECKED_SEVERITY", "review"):
            h = lv.check_card(mk_card(self.T_COV, claims), ing, None)
        self.assertEqual((h["verdict"], h["evidence_grade_if_review_confirmed"], h["counts"]["review"]),
                         ("NEEDS_REVIEW", "FULL_TEXT_VERIFIED", 2))
        self.assertTrue(all("column not checked" in s for s in h["review_items"]))
        self.assertEqual([it["status"] for it in h["items"]], [it["status"] for it in r["items"]])
        # a failing card stays FAIL; the label never softens or hardens it
        bad = [dict(claims[0], numbers=["0.31", "0.48"])]
        self.assertEqual(lv.check_card(mk_card(self.T_COV, bad), ing, None)["verdict"], "FAIL")

    def test_v1_v2_and_html_cards(self):
        ing = mk_ingest([{"anchor": PROSE[1]}, {"anchor": PROSE[2]}, {"anchor": PROSE[3]}])
        claims = [{"claim_id": "C1", "page": 3, "quote": "reports −0.087* (0.044) and 1,204 boats with .05",
                   "numbers": ["-0.087", "1,204"], "source": "text"}]
        coverage = [cov(1, "The violet ferry carried nineteen patient cartographers"),
                    cov(2, "relies on natural-language summaries of each imaginary voyage"),
                    cov(3, "Table 2 reports -0.087* (0.044) and 1,204 boats")]
        v1 = mk_card(coverage, claims)
        v2 = dict(v1, schema_version="lit-verify-card-v2", anchor_kind="pdf", source_sha256=v1["source_pdf_sha256"])
        v2.pop("source_pdf_sha256")
        a, b = lv.check_card(v1, ing, None), lv.check_card(v2, ing, None)
        self.assertEqual(a, b)
        self.assertEqual([(n, c) for n, c, _, _ in self.cols(a)], [("-0.087", False), ("1,204", True)])
        # arXiv HTML: in-quote through the row, the rows/ row path, and a one-number prose section
        card = mk_html_card(H_COV, [hclaim("T1", "1.1", ROW_QUOTE + " 0.33", ["0.62"]),
                                    hclaim("R1", "1.1", ROW_QUOTE, ["0.33"]),
                                    hclaim("E1", "2", "weighted each quay by its 23 painted bollards before pooling",
                                           ["23"])])
        r = lv.check_card(card, mk_unit_ingest(), None)
        self.assertEqual(r["verdict"], "PARTIAL", r["failures"])                    # the conversion-error cap, as before
        self.assertEqual([(it["locality"], it["column_checked"], it["column_values"]) for it in self.nums(r)],
                         [("in-quote", False, 3), ("row", False, 3), ("in-quote", True, 1)])
        self.assertEqual(r["counts"]["numbers_column_not_checked"], 2)


# --- 1.6.0 (S3-A, review-fix round 1): gate soundness (pure; every word and number invented) ---
class SoundnessFixTests(unittest.TestCase):
    SIGN_PAGE = ("Synthetic sign page: the invented model estimated the tide slope (Est = - 0.041, SE = 0.050) for the "
                 "northern quay.\nThe lantern slope was −0.164 for the amber lanterns and nobody checked it twice.\n"
                 "An increase of 5–10% in the invented gull counts was reported by the keepers that winter.\n\f")
    S_COV = [cov(1, "nobody checked it twice")]

    def gate(self, claims, anchor=None, **page):
        text = anchor or self.SIGN_PAGE
        ing = mk_ingest([dict({"anchor": text}, **page)])
        anchor_cov = next(s for s in text.split("\n") if len(s) > 45)[:60]
        return lv.check_card(mk_card([cov(1, anchor_cov)], claims), ing, None)

    def item_of(self, r, kind, cid):
        return next(it for it in r["items"] if it["kind"] == kind and it["claim_id"] == cid)

    # B1: the spaced minus, both directions
    def test_spaced_minus_is_a_sign_after_sign_context_only(self):
        for s, want in (("Est = - 0.041", ("-0.041", True)), ("(- 0.044)", ("-0.044", True)),
                        ("Est = − 0.041", ("-0.041", True)), ("x = -\t0.5", ("-0.5", True)),
                        ("Est = -\n0.041", ("-0.041", True)), ("- 0.07 at the start", ("-0.07", True)),
                        ("ages (28 - 75)", ("75", False)), ("(n − 1)", ("1", False)), ("pages 1 – 3", ("3", False)),
                        ("slope - 0.5", ("0.5", False)), ("Est = -\n\n0.041", ("0.041", False))):
            with self.subTest(s=s):
                t = ptc.number_candidates(s)[-1]
                self.assertEqual((t["digits"], t["negative"]), want)
        self.assertTrue(ptc.number_candidates("(- 0.044)")[0]["paren"])
        r = self.gate([{"claim_id": "N1", "page": 1, "quote": "the tide slope (Est = - 0.041, SE = 0.050) for the "
                        "northern quay", "numbers": ["-0.041"], "source": "text"}])
        self.assertEqual((r["verdict"], statuses(r, "claim_number")), ("PASS", ["NUMBER_OK"]), r["review_items"])
        r = self.gate([{"claim_id": "N2", "page": 1, "quote": "the tide slope (Est = - 0.041, SE = 0.050) for the "
                        "northern quay", "numbers": ["0.041"], "source": "text"}])
        self.assertEqual((r["verdict"], statuses(r, "claim_number")), ("FAIL", ["NUMBER_MISSING"]))

    # B2: a minus (or range dash) deleted inside a quote; ladder-v2 quote-number rule
    def test_deleted_minus_in_a_quote_is_review_with_or_without_declared_numbers(self):
        q = "The lantern slope was 0.164 for the amber lanterns and nobody checked"
        r = self.gate([{"claim_id": "Q1", "page": 1, "quote": q, "numbers": [], "source": "text"}])
        it = self.item_of(r, "claim_quote", "Q1")
        self.assertEqual((r["verdict"], it["status"], it["severity"], it["tier"], it["status_if_confirmed"]),
                         ("NEEDS_REVIEW", "QUOTE_NUMBERS_DIFFER", "review", "PASS_SKELETON", "PASS_SKELETON"))
        self.assertEqual((it["quote_numbers"], it["page_numbers"], it["quote_numbers_agree"]),
                         (["0.164"], ["-0.164"], False))
        self.assertEqual(r["evidence_grade_if_review_confirmed"], "FULL_TEXT_VERIFIED")
        r = self.gate([{"claim_id": "Q2", "page": 1, "quote": q, "numbers": ["0.164"], "source": "text"}])
        self.assertEqual((r["verdict"], statuses(r, "claim_quote"), statuses(r, "claim_number")),
                         ("FAIL", ["QUOTE_NUMBERS_DIFFER"], ["NUMBER_MISSING"]))
        r = self.gate([{"claim_id": "Q3", "page": 1, "quote": "An increase of 510% in the invented gull counts was "
                        "reported", "numbers": [], "source": "text"}])
        self.assertEqual(statuses(r, "claim_quote"), ["QUOTE_NUMBERS_DIFFER"])
        # the genuine quotes agree (and record their numbers)
        r = self.gate([{"claim_id": "G1", "page": 1, "quote": "The lantern slope was -0.164 for the amber lanterns "
                        "and nobody", "numbers": ["-0.164"], "source": "text"},
                       {"claim_id": "G2", "page": 1, "quote": "An increase of 5-10% in the invented gull counts was "
                        "reported", "numbers": [], "source": "text"}])
        self.assertEqual(r["verdict"], "PASS", r["review_items"])
        self.assertEqual([(it["quote_numbers"], it["quote_numbers_agree"]) for it in r["items"]
                          if it["kind"] == "claim_quote"], [(["-0.164"], True), (["5", "10%"[:-1]], True)])

    def test_quote_number_mismatch_truncation_and_lost_line_break_sign(self):
        page = "Synthetic page: the invented heron index was 0.164 in the spring survey of the bay.\n\f"
        r = self.gate([{"claim_id": "T1", "page": 1, "quote": "the invented heron index was 0.16", "numbers": [],
                        "source": "text"}], anchor=page)
        self.assertIn(statuses(r, "claim_quote")[0], ("QUOTE_NUMBERS_DIFFER", "NON_IDENTIFYING"))
        r = self.gate([{"claim_id": "T2", "page": 1, "quote": "Synthetic page: the invented heron index was 0.16",
                        "numbers": [], "source": "text"}], anchor=page)
        self.assertEqual(statuses(r, "claim_quote"), ["QUOTE_NUMBERS_DIFFER"])
        # NORMALIZE's line-break rejoin deletes "-\n"; the number view keeps the sign
        page = "Synthetic page: the invented tide slope (Est = -\n0.041, SE = 0.050) for the northern quay.\n\f"
        view = ptc.number_view(page)
        self.assertEqual([t["digits"] for t in ptc.view_numbers(view)], ["-0.041", "0.050"])
        q = "the invented tide slope (Est = 0.041, SE = 0.050) for the northern"
        r = self.gate([{"claim_id": "L1", "page": 1, "quote": q, "numbers": [], "source": "text"}], anchor=page)
        self.assertEqual(statuses(r, "claim_quote"), ["QUOTE_NUMBERS_DIFFER"])
        r = self.gate([{"claim_id": "L2", "page": 1, "quote": "the invented tide slope (Est = -0.041, SE = 0.050) for "
                        "the northern", "numbers": ["-0.041"], "source": "text"}], anchor=page)
        self.assertEqual((statuses(r, "claim_quote"), statuses(r, "claim_number")), (["PASS_SKELETON"], ["NUMBER_OK"]))

    def test_quote_numbers_differ_keeps_the_partial_weight(self):
        layer = {"flags": ["ocr_layer_suspected"], "evidence": {"ocr_layer_suspected": ["an image covers 100%"]}}
        r = self.gate([{"claim_id": "Q1", "page": 1, "quote": "The lantern slope was 0.164 for the amber lanterns",
                        "numbers": [], "source": "text"}], **layer)
        it = self.item_of(r, "claim_quote", "Q1")
        self.assertEqual((r["verdict"], it["status_if_confirmed"], r["evidence_grade_if_review_confirmed"]),
                         ("NEEDS_REVIEW", "PASS_OCR_LAYER", "FULL_TEXT_PARTIAL"))

    # superscripts are marks, not digits; stars are not compared
    def test_superscript_marks(self):
        self.assertEqual(ptc.normalize("r = 0.62¹"), "r = 0.621")          # NORMALIZE itself is unchanged
        tok = ptc.number_candidates("r = 0.62¹ and")[0]
        self.assertEqual((tok["digits"], tok["marks"], tok["sup"]), ("0.62", "¹", "¹"))
        page = ptc.number_candidates("r = 0.62¹ and 10⁵ boats and 0.33ᵃ gulls")
        for claim, want in (("0.621", None), ("0.62", "exact"), ("0.62¹", "exact"), ("0.62²", None), ("105", None),
                            ("10⁵", "exact"), ("10³", None), ("0.33", "exact")):
            with self.subTest(claim=claim):
                self.assertEqual(ptc.compare_number(ptc.parse_number(claim), page)[0], want)
        # stars are not compared (documented): the quote carries them
        self.assertEqual(ptc.compare_number(ptc.parse_number("0.123***"), ptc.number_candidates("b = 0.123"))[0],
                         "exact")
        page = "Synthetic page: the invented correlation was r = 0.62¹ in the spring survey of the bay.\n\f"
        r = self.gate([{"claim_id": "U1", "page": 1, "quote": "the invented correlation was r = 0.621 in the spring",
                        "numbers": [], "source": "text"}], anchor=page)
        self.assertEqual(statuses(r, "claim_quote"), ["QUOTE_NUMBERS_DIFFER"])
        r = self.gate([{"claim_id": "U2", "page": 1, "quote": "the invented correlation was r = 0.62¹ in the spring",
                        "numbers": ["0.62"], "source": "text"}], anchor=page)
        self.assertEqual((r["verdict"], statuses(r, "claim_number")), ("PASS", ["NUMBER_OK"]), r["review_items"])
        self.assertIn("superscript", self.item_of(r, "claim_number", "U2")["reason"])
        r = self.gate([{"claim_id": "U3", "page": 1, "quote": "the invented correlation was r = 0.62¹ in the spring",
                        "numbers": ["0.621"], "source": "text"}], anchor=page)
        self.assertEqual(statuses(r, "claim_number"), ["NUMBER_MISSING"])

    def test_normalize_map_reproduces_normalize(self):
        for s in ("a\r\nb", "natural-\n language", "x­Y ‘q’ “w” ０.５ ﬁ", "  lead  and\ttrail \n", "é café",
                  "1 204 and 0.62¹", "", "Est = -\n0.041"):
            with self.subTest(s=s):
                m = ptc.normalize_map(s)
                self.assertIsNotNone(m)
                self.assertEqual(m[0], ptc.normalize(s))
                self.assertEqual(len(m[1]), len(m[0]))
        self.assertEqual(sorted(ptc.normalize_map("Est = -\n0.041")[2]), [6])
        self.assertEqual(ptc.normalize_map("1277–\n1295")[2], frozenset())        # a range dash is not a sign
        self.assertEqual(ptc.normalize("pages 749–\n756"), "pages 749756")         # NORMALIZE fuses the range ...
        self.assertEqual([t["digits"] for t in ptc.view_numbers(ptc.number_view("pages 749–\n756 and a 6-\nyear"))],
                         ["749", "756", "6"])                                     # ... the number view does not
        # S3-A2: the mirror case, a letter before the line-break dash and a digit
        #   after ("K-\n12" -> NORMALIZE "K12" hides the 12 from the number rules)
        self.assertEqual(ptc.normalize("all K-\n12 schools"), "all K12 schools")
        self.assertEqual([t["digits"] for t in ptc.view_numbers(ptc.number_view("all K-\n12 schools and COVID-\n19"))],
                         ["12", "19"])
        self.assertEqual([t["digits"] for t in ptc.view_numbers(ptc.number_view("a natural-\nlanguage 7"))], ["7"])
        page = "Synthetic page: the invented survey of all K-\n12 harbour schools counted 41 copper lanterns.\n\f"
        r = self.gate([{"claim_id": "K1", "page": 1, "quote": "the invented survey of all K-12 harbour schools counted",
                        "numbers": ["12"], "source": "text"}], anchor=page)
        self.assertEqual((statuses(r, "claim_quote"), statuses(r, "claim_number")), (["PASS_SKELETON"], ["NUMBER_OK"]))
        v = ptc.number_view("cells 1 204 here")
        self.assertEqual([t["digits"] for t in ptc.view_numbers(v)], ["1204"])

    # B3: the row path's guards
    TABLE_A = ("Table 7: Invented gull counts\nHarbour\nNorth Pier beside the copper bell\nSouth Pier\nSpring\n0.44\n"
               "0.29\nwhich invented keepers counted the gulls along the quay wall every winter morning\n"
               "The gull counts in Table 7 are invented for the row guards of the gate.\n\f")
    LANE_B = ("Table 7: Invented gull counts\nHarbour Spring\nNorth Pier beside the copper bell 0.44\nSouth Pier 0.29\n"
              "which 27 invented keepers counted the gulls along the quay wall every winter morning 0.29\n"
              "The gull counts in Table 7 are invented for the row guards of the gate.\n")

    def row_gate(self, quote, numbers, flags=("table",), anchor=None):
        ing = mk_ingest([{"anchor": (anchor or self.TABLE_A) + "27 and 0.29\n", "lane_b": self.LANE_B,
                          "flags": list(flags)}])
        r = lv.check_card(mk_card([cov(1, "The gull counts in Table 7 are invented for the row guards")],
                                  [{"claim_id": "W1", "page": 1, "quote": quote, "numbers": list(numbers),
                                    "source": "text"}]), ing, None)
        return r, [it for it in r["items"] if it["kind"] == "claim_number"]

    def test_row_guards_reject_prose_lines_and_accept_table_rows(self):
        rows = ptc.lane_b_rows(self.LANE_B)
        self.assertEqual([x["label"] for x in rows], ["northpierbesidethecopperbell", "southpier"])
        self.assertEqual(ptc.lane_b_rows("of 1552 students without disabilities in the invented sample\n"), [])
        self.assertEqual(ptc.lane_b_rows("Gender (Girls) 0.50 (0.02) 0.52 n.s.\n")[0]["label"], "gendergirls")
        r, nums = self.row_gate("North Pier beside the copper bell South Pier Spring", ["0.44"])
        self.assertEqual([(it["status"], it["locality"], it["row_match"]) for it in nums],
                         [("NUMBER_OK", "row", "unique")])
        r, nums = self.row_gate("which invented keepers counted the gulls along the quay wall", ["27"])
        self.assertEqual([(it["status"], it["row_match"]) for it in nums], [("NUMBER_NOT_NEAR_QUOTE", "none")])

    def test_row_guards_page_flag_and_row_start(self):
        r, nums = self.row_gate("North Pier beside the copper bell South Pier Spring", ["0.44"], flags=())
        self.assertEqual([(it["status"], it["row_match"]) for it in nums], [("NUMBER_NOT_NEAR_QUOTE", "ineligible")])
        self.assertIn("not flagged table or numeric", nums[0]["reason"])
        mid = self.TABLE_A.replace("Harbour\nNorth Pier", "Harbour North Pier")
        r, nums = self.row_gate("North Pier beside the copper bell South Pier Spring", ["0.44"], anchor=mid)
        self.assertEqual([(it["status"], it["row_match"]) for it in nums], [("NUMBER_NOT_NEAR_QUOTE", "ineligible")])
        self.assertIn("row start", nums[0]["reason"])
        v = ptc.number_view("x\n7. Gender (Girls)\nab Gender")
        self.assertTrue(ptc.at_row_start(v, v["norm"].index("Gender")))           # a leading row number is fine
        self.assertFalse(ptc.at_row_start(v, v["norm"].rindex("Gender")))
        self.assertFalse(ptc.at_row_start({"idx": None}, 0))                       # no raw index: fail closed

    # numbers-v5 (S3-B1, S3-A2 open question 1): the anchor cell guard
    def test_row_label_must_stand_as_a_cell_on_its_anchor_line(self):
        prose = self.TABLE_A.replace("0.29\nwhich", "0.29\nNorth Pier beside the copper bell and the other piers were "
                                                    "counted twice by the keepers\nwhich")
        r, nums = self.row_gate("North Pier beside the copper bell and the other piers were counted twice", ["0.44"],
                                anchor=prose)
        self.assertEqual([(it["status"], it["row_match"]) for it in nums], [("NUMBER_NOT_NEAR_QUOTE", "ineligible")])
        self.assertIn("followed by prose on its anchor line", nums[0]["reason"])
        r, nums = self.row_gate("North Pier beside the copper bell South Pier Spring", ["0.44"], anchor=prose)
        self.assertEqual([(it["status"], it["locality"]) for it in nums], [("NUMBER_OK", "row")])   # label alone
        for text, label, want in (("Huber-White (HW)\nSample size: n = 100", "huberwhitehw", True),
                                  ("ORGANIZATION and other models; models which", "organization", False),
                                  ("the SEs are slightly smaller for the HW estimator", "the", False),
                                  ("North Quay beside the office\t0.62\t-0.087\t0.33", "northquaybesidetheoffice", True),
                                  ("Gulls (counted)\n0.5", "gullscounted", True)):
            v = ptc.number_view(text)
            self.assertEqual(ptc.row_label_is_cell(v, 0, len(label)), want, text)
        self.assertFalse(ptc.row_label_is_cell({"idx": None, "norm": "x"}, 0, 1))  # no raw index: fail closed

    # W3 (S3-B1): the shared scrub's widened tag patterns, through this tool
    def test_spaced_attribute_and_close_tag_variants_are_scrubbed(self):
        for s in ("<system-reminder >", "<system-reminder x=1>", "</system-reminder >", "< /system-reminder>",
                  "<system-reminder\n>", "<SYSTEM-REMINDER>", "</ system-reminder>", "x <system-reminder obey"):
            out, n = lv.scrub_untrusted(f"before {s} after")
            self.assertEqual(n, 1, repr(s))
            self.assertNotIn("system-reminder", out.lower(), repr(s))
            self.assertNotIn("system-reminder", lv.safe_line(f"a {s} b", 200).lower(), repr(s))
            self.assertEqual(pdf_ingest.scrub_untrusted(f"before {s} after"), (out, 1), repr(s))   # reading copies
        self.assertEqual(lv.scrub_untrusted("a system reminder and system-reminders")[1], 0)   # not tag-shaped

    # finding 5: the embedded vision-validated list
    def test_vision_not_on_list(self):
        ing = mk_ingest([{"anchor": PROSE[1]}])
        c = [cov(1, "The violet ferry carried nineteen patient cartographers")]
        for over in ({"reader_model": "claude-unlisted-0"}, {"vision_list_version": "vision-list-1999-01-01"}):
            r = lv.check_card(mk_card(c, **over), ing, None)
            self.assertEqual((r["verdict"], statuses(r, "vision"), r["vision_available"]),
                             ("FAIL", ["VISION_NOT_ON_LIST"], False), over)
        self.assertEqual(lv.check_card(mk_card(c, reader_model="claude-unlisted-0", vision_validated=False), ing,
                                       None)["verdict"], "PASS")
        self.assertEqual(lv.check_card(mk_card(c), ing, None)["verdict"], "PASS")   # the module's test-only list
        # the shipped list mirrors SKILL.md: same version line, same (model ID, route) rows
        skill = (_REPO_ROOT / ".claude" / "skills" / "pdf-reading" / "SKILL.md").read_text()
        self.assertIn(f'`vision_list_version: "{lv.VISION_LIST_VERSION}"`', skill)
        section = skill.split("### Vision-validated model list", 1)[1].split("\n### ", 1)[0]
        rows = re.findall(r"^\| `([^`]+)` \| `([^`]+)` \|", section, re.M)
        self.assertEqual(sorted(rows), sorted(REAL_VISION_LISTS[lv.VISION_LIST_VERSION]))
        self.assertEqual(len(rows), len(set(rows)))
        self.assertNotIn("*(none yet)*", skill)

    # 1.8.0 part 4: vision-list-2026-10-28 (the probe of 2026-10-28 plus the user's policy admissions)
    LISTED_2026_10_28 = ("claude-opus-5-5", "claude-sonnet-5", "claude-sonnet-5-5", "claude-fable-5-1", "claude-fable-5")
    # 1.8.0 part 6: vision-list-2026-10-30 adds the GPT models that passed on chatgpt-subscription (shim)
    LISTED_GPT_2026_10_30 = ("gpt-6-sol", "gpt-6.1-sol", "gpt-6-astra")

    def test_vision_list_2026_10_28_rows(self):
        # 1.8.0 part 6: no longer the current version (test_vision_list_2026_10_30_rows pins that); kept unchanged
        self.assertIn("vision-list-2026-10-28", REAL_VISION_LISTS)
        self.assertEqual(REAL_VISION_LISTS["vision-list-2026-10-19"], ())   # kept, still empty
        want = {(m, r) for m in self.LISTED_2026_10_28 for r in ("anthropic-subscription", "anthropic-api")}
        got = REAL_VISION_LISTS["vision-list-2026-10-28"]
        self.assertEqual((set(got), len(got)), (want, 10))
        # every key is bare (no [1m] suffix), as the reader writes reader_model
        self.assertFalse([m for m, _ in got if "[" in m or m != m.strip() or m != m.lower()])

    def test_vision_list_skill_rows_and_basis_labels(self):
        # Every data row of SKILL.md's list table has the backticked (ID, route) shape (a row without
        # backticks would escape the mirror check), and each row's basis label is pinned.
        skill = (_REPO_ROOT / ".claude" / "skills" / "pdf-reading" / "SKILL.md").read_text()
        section = skill.split("### Vision-validated model list", 1)[1].split("\n### ", 1)[0]
        lines = [ln for ln in section.splitlines() if ln.startswith("|")]
        self.assertEqual(lines[0], "| Exact model ID | Route | Basis (date, result) | Validated on |")
        self.assertTrue(set(lines[1]) <= set("|- "), lines[1])
        data = lines[2:]
        self.assertEqual(len(data), 16)   # 1.8.0 part 6: vision-list-2026-10-30
        probed, admitted = ("claude-opus-5-5", "claude-sonnet-5"), ("claude-sonnet-5-5", "claude-fable-5-1",
                                                                     "claude-fable-5")
        kinds = {"probed": 0, "probed-model api (inference)": 0, "admitted": 0, "gpt probed": 0,
                 "gpt api (inference)": 0}
        policy = "admitted 2026-10-28 by user policy decision, not by DAAF quality validation"
        for ln in data:
            m = re.match(r"^\| `([^`]+)` \| `([^`]+)` \| ([^|]+) \| ([^|]+) \|$", ln)
            self.assertIsNotNone(m, ln)
            model, route, basis, scope = m.groups()
            self.assertIn("`scanned` or `ocr_layer_suspected`", scope, ln)
            self.assertEqual(scope.endswith("(inference)"), route in ("anthropic-api", "openai-api")
                             and model not in admitted, ln)
            if model in self.LISTED_GPT_2026_10_30 and route == "chatgpt-subscription":
                self.assertTrue(basis.startswith("Probed 2026-10-28 (scored 2026-10-30): 3 of 3 runs passed"), ln)
                self.assertIn("381/381 synthetic and 1,081/1,081 real", basis, ln)
                self.assertIn("echoed by the shim", basis, ln)        # the shim caveat travels with the row
                kinds["gpt probed"] += 1
            elif model in self.LISTED_GPT_2026_10_30 and route == "openai-api":
                self.assertTrue(basis.startswith("Not probed on this route; listed by inference"), ln)
                self.assertIn("parity with the subscription route assumed by user decision 2026-10-30", basis, ln)
                self.assertNotIn("admitted", basis, ln)
                kinds["gpt api (inference)"] += 1
            elif model in probed and route == "anthropic-subscription":
                self.assertTrue(basis.startswith("Probed 2026-10-28: 3 of 3 runs passed"), ln)
                kinds["probed"] += 1
            elif model in probed and route == "anthropic-api":
                self.assertIn("inference", basis, ln)
                self.assertNotIn("admitted", basis, ln)
                kinds["probed-model api (inference)"] += 1
            else:
                self.assertIn(model, admitted, ln)
                self.assertIn(policy, basis, ln)
                self.assertNotIn("Probed", basis, ln)
                self.assertEqual("route by inference" in basis, route == "anthropic-api", ln)
                kinds["admitted"] += 1
        self.assertEqual(kinds, {"probed": 2, "probed-model api (inference)": 2, "admitted": 6, "gpt probed": 3,
                                 "gpt api (inference)": 3})

    def test_vision_list_2026_10_28_listed_ids_pass(self):
        ing = mk_ingest([{"anchor": PROSE[3] + " The estimate was 0.50 in the invented pilot."}])
        c = [cov(1, "Table 2 reports -0.087* (0.044) and 1,204 boats")]
        vision = [{"claim_id": "V1", "page": 1, "quote": None, "numbers": ["31"], "source": "vision"}]
        for model in self.LISTED_2026_10_28:
            card = dict(reader_model=model, vision_list_version="vision-list-2026-10-28")
            r = lv.check_card(mk_card(c, **card), ing, None)
            self.assertEqual((r["verdict"], statuses(r, "vision"), r["vision_available"]), ("PASS", [], True), model)
            # a listed reader's vision claim is a vision reading (partial), not an unavailable claim
            r = lv.check_card(mk_card(c, vision, **card), ing, None)
            self.assertEqual((r["verdict"], statuses(r, "vision")), ("PARTIAL", []), model)
            self.assertIn("NUMBER_VISION_ONLY", statuses(r, "claim_number"))

    def test_vision_list_2026_10_28_unlisted_ids_fail(self):
        ing = mk_ingest([{"anchor": PROSE[1]}])
        c = [cov(1, "The violet ferry carried nineteen patient cartographers")]
        # an unlisted model, the [1m] form a reader must strip, a case or spacing variant, a shim candidate,
        # an older Opus, the provider-prefixed and dotted (OpenRouter) forms, and leading spaces
        for model in ("claude-unlisted-0", "claude-opus-5-5[1m]", "Claude-Opus-5-5", "claude-sonnet-5 ", "gpt-6-sol",
                      "claude-opus-4-8", "anthropic/claude-opus-5-5", "claude-fable-5.1", " claude-opus-5-5",
                      " claude-fable-5"):
            r = lv.check_card(mk_card(c, reader_model=model, vision_list_version="vision-list-2026-10-28"), ing, None)
            self.assertEqual((r["verdict"], statuses(r, "vision"), r["vision_available"]),
                             ("FAIL", ["VISION_NOT_ON_LIST"], False), model)
            reason = next(it["reason"] for it in r["items"] if it["status"] == "VISION_NOT_ON_LIST")
            self.assertIn("is not on vision list 'vision-list-2026-10-28' (10 entries)", reason, model)

    def test_vision_list_old_and_unknown_versions_fail(self):
        ing = mk_ingest([{"anchor": PROSE[1]}])
        c = [cov(1, "The violet ferry carried nineteen patient cartographers")]
        vision = [{"claim_id": "V1", "page": 1, "quote": None, "numbers": ["31"], "source": "vision"}]
        # a listed ID under the OLD version still fails: that list is empty, and cards keep the version
        for model in self.LISTED_2026_10_28:
            r = lv.check_card(mk_card(c, vision, reader_model=model, vision_list_version="vision-list-2026-10-19"),
                              ing, None)
            self.assertEqual((r["verdict"], statuses(r, "vision"), r["vision_available"]),
                             ("FAIL", ["VISION_NOT_ON_LIST", "VISION_UNAVAILABLE_CLAIM"], False), model)
        # an unknown or missing version fails for a listed ID too
        for version in ("vision-list-2026-10-29", "vision-list-2026-11-02", "VISION-LIST-2026-10-28", None):
            r = lv.check_card(mk_card(c, reader_model="claude-opus-5-5", vision_list_version=version), ing, None)
            self.assertEqual((r["verdict"], statuses(r, "vision")), ("FAIL", ["VISION_NOT_ON_LIST"]), version)
            reason = next(it["reason"] for it in r["items"] if it["status"] == "VISION_NOT_ON_LIST")
            self.assertIn("is not a list version this tool knows", reason, version)
        # vision_validated false never consults the list
        r = lv.check_card(mk_card(c, reader_model="claude-opus-5-5", vision_validated=False,
                                  vision_list_version="vision-list-2026-10-19"), ing, None)
        self.assertEqual(r["verdict"], "PASS")

    # 1.8.0 part 6: vision-list-2026-10-30 (the GPT probe on chatgpt-subscription, scored 2026-10-30)
    def test_vision_list_2026_10_30_rows(self):
        self.assertEqual(lv.VISION_LIST_VERSION, "vision-list-2026-10-30")
        self.assertEqual(set(REAL_VISION_LISTS),
                         {"vision-list-2026-10-19", "vision-list-2026-10-28", "vision-list-2026-10-30"})
        claude = {(m, r) for m in self.LISTED_2026_10_28 for r in ("anthropic-subscription", "anthropic-api")}
        gpt = {(m, r) for m in self.LISTED_GPT_2026_10_30 for r in ("chatgpt-subscription", "openai-api")}
        got = REAL_VISION_LISTS["vision-list-2026-10-30"]
        self.assertEqual((set(got), len(got)), (claude | gpt, 16))
        # the ten 2026-10-28 rows carry over unchanged, and the older versions keep their own rows
        self.assertEqual(set(REAL_VISION_LISTS["vision-list-2026-10-28"]), claude)
        self.assertEqual((REAL_VISION_LISTS["vision-list-2026-10-19"], len(REAL_VISION_LISTS["vision-list-2026-10-28"])),
                         ((), 10))
        # every key is bare: no [1m] suffix, no provider prefix, lower case, no spaces
        self.assertFalse([m for m, _ in got if "[" in m or "/" in m or m != m.strip() or m != m.lower()])
        # no OpenRouter row and no failed or unprobed GPT model
        self.assertFalse([row for row in got if row[1] == "openrouter" or row[0] in ("gpt-6-luna", "gpt-5.6-sol")])

    def test_vision_list_2026_10_30_listed_ids_pass(self):
        ing = mk_ingest([{"anchor": PROSE[3] + " The estimate was 0.50 in the invented pilot."}])
        c = [cov(1, "Table 2 reports -0.087* (0.044) and 1,204 boats")]
        vision = [{"claim_id": "V1", "page": 1, "quote": None, "numbers": ["31"], "source": "vision"}]
        for model in self.LISTED_2026_10_28 + self.LISTED_GPT_2026_10_30:
            card = dict(reader_model=model, vision_list_version="vision-list-2026-10-30")
            r = lv.check_card(mk_card(c, **card), ing, None)
            self.assertEqual((r["verdict"], statuses(r, "vision"), r["vision_available"]), ("PASS", [], True), model)
            r = lv.check_card(mk_card(c, vision, **card), ing, None)
            self.assertEqual((r["verdict"], statuses(r, "vision")), ("PARTIAL", []), model)
            self.assertIn("NUMBER_VISION_ONLY", statuses(r, "claim_number"))
        # A whole card as a GPT reader on chatgpt-subscription writes it: the route sits in the front matter,
        # which the gate never reads (route and identity stay with the orchestrator audit), so the card passes
        # on the model ID and the list version alone.
        block = mk_card(c, vision, reader_model="gpt-6-sol", vision_list_version="vision-list-2026-10-30")
        text = ("---\npaper_key: user_00000001\nreader_model: gpt-6-sol\nreader_model_source: self-report\n"
                "reader_route: chatgpt-subscription\nvision: validated\n---\n\n# Evidence card\n\n"
                "```lit-verify\n" + json.dumps(block, indent=2) + "\n```\n")
        r = lv.check_card(lv.parse_card(text), ing, None)
        self.assertEqual((r["verdict"], statuses(r, "vision"), r["vision_available"]), ("PARTIAL", [], True))

    def test_vision_list_2026_10_30_near_miss_ids_fail(self):
        ing = mk_ingest([{"anchor": PROSE[1]}])
        c = [cov(1, "The violet ferry carried nineteen patient cartographers")]
        # the failed sonnet-tier model, the [1m] form a reader must strip, the OpenRouter-prefixed form, a -pro
        # variant, an unprobed older Sol, case and spacing variants, and an unlisted Claude ID
        for model in ("gpt-6-luna", "gpt-6-sol[1m]", "openai/gpt-6-sol", "gpt-6-sol-pro", "gpt-6.1-sol-pro",
                      "gpt-6-astra-pro", "gpt-5.6-sol", "GPT-6-Sol", "gpt-6-sol ", " gpt-6-astra", "gpt-6.1-sol[1m]",
                      "openai/gpt-6-astra", "openai/gpt-6-luna", "gpt-6-luna[1m]", "claude-opus-5-5[1m]",
                      "claude-unlisted-0"):
            r = lv.check_card(mk_card(c, reader_model=model, vision_list_version="vision-list-2026-10-30"), ing, None)
            self.assertEqual((r["verdict"], statuses(r, "vision"), r["vision_available"]),
                             ("FAIL", ["VISION_NOT_ON_LIST"], False), model)
            reason = next(it["reason"] for it in r["items"] if it["status"] == "VISION_NOT_ON_LIST")
            self.assertIn("is not on vision list 'vision-list-2026-10-30' (16 entries)", reason, model)

    def test_vision_list_older_versions_keep_their_rows(self):
        # A card keeps the meaning of the list it was read under: the GPT models are NOT on the 2026-10-28 or
        # 2026-10-19 lists, the Claude models stay on 2026-10-28, and an unknown later version fails.
        ing = mk_ingest([{"anchor": PROSE[1]}])
        c = [cov(1, "The violet ferry carried nineteen patient cartographers")]
        for model in self.LISTED_GPT_2026_10_30:
            for version, entries in (("vision-list-2026-10-28", "10 entries"), ("vision-list-2026-10-19", "0 entries")):
                r = lv.check_card(mk_card(c, reader_model=model, vision_list_version=version), ing, None)
                self.assertEqual((r["verdict"], statuses(r, "vision")), ("FAIL", ["VISION_NOT_ON_LIST"]), (model, version))
                reason = next(it["reason"] for it in r["items"] if it["status"] == "VISION_NOT_ON_LIST")
                self.assertIn(f"is not on vision list '{version}' ({entries})", reason, (model, version))
        for model in self.LISTED_2026_10_28:
            r = lv.check_card(mk_card(c, reader_model=model, vision_list_version="vision-list-2026-10-28"), ing, None)
            self.assertEqual((r["verdict"], r["vision_available"]), ("PASS", True), model)
        for version in ("vision-list-2026-10-31", "vision-list-2026-10-30 ", "VISION-LIST-2026-10-30"):
            r = lv.check_card(mk_card(c, reader_model="gpt-6-sol", vision_list_version=version), ing, None)
            self.assertEqual((r["verdict"], statuses(r, "vision")), ("FAIL", ["VISION_NOT_ON_LIST"]), version)
            reason = next(it["reason"] for it in r["items"] if it["status"] == "VISION_NOT_ON_LIST")
            self.assertIn("is not a list version this tool knows", reason, version)

    # W2 (1.6.0): the OCR-layer paper cap
    def test_ocr_layer_paper_cap(self):
        layer = {"flags": ["ocr_layer_suspected"], "evidence": {"ocr_layer_suspected": ["an image covers 100%"]}}
        pages = [dict(layer, anchor=PROSE[1]), dict(layer, anchor=PROSE[2]), {"anchor": PROSE[3]}]
        c = [cov(1, "The violet ferry carried nineteen patient cartographers"),
             cov(2, "relies on natural-language summaries of each imaginary voyage"),
             cov(3, "Table 2 reports -0.087* (0.044) and 1,204 boats")]
        r = lv.check_card(mk_card(c), mk_ingest(pages), None)
        self.assertEqual((r["verdict"], r["evidence_grade_suggested"], statuses(r, "paper"), r["counts"]["pages_ocr_layer"]),
                         ("PARTIAL", "FULL_TEXT_PARTIAL", ["OCR_LAYER_PAPER"], 2))
        r = lv.check_card(mk_card(c), mk_ingest([pages[0], {"anchor": PROSE[2]}, pages[2]]), None)
        self.assertEqual((r["verdict"], statuses(r, "paper"), r["counts"]["pages_ocr_layer"]), ("PASS", [], 1))
        self.assertEqual(lv.OCR_LAYER_PAPER_CAP_PAGES, 2)


# --- 1.8.0 part 5: a vision reading on a scan page goes to review (VISION_ON_SCAN_PAGE) ---
class VisionOnScanPageTests(unittest.TestCase):
    LISTED = {"reader_model": "claude-opus-5-5", "vision_list_version": "vision-list-2026-10-28"}
    OCR = "SCAN PAGE\nCOMPASS 7314 HERON 2659\nThe calm bay sheltered 41 painted rowing boats.\n"
    LAYER = {"flags": ["figure", "ocr_layer_suspected"],
             "evidence": {"ocr_layer_suspected": ["an image covers 100% of the page area (>= 80%)"]}}
    COV = [cov(1, "The violet ferry carried nineteen patient cartographers"),
           cov(2, "COMPASS 7314 HERON 2659 The calm bay sheltered 41")]
    V1 = {"claim_id": "V1", "page": 2, "quote": None, "numbers": ["88"], "source": "vision"}
    # the researcher-facing reason parts (plain language, user requirement 2026-10-28)
    WHERE = " (its position in the file; the printed page number may differ)"
    SCAN = "This page looks like a scan."
    OCR_LAYER = ("This page looks like a scan, and its text was machine-recognized (OCR) when the PDF was made, so the "
                 "text may contain errors.")
    TESTED = "DAAF has tested AI reading of page pictures only on clean digital pages."
    TESTED_NUM = ("DAAF has tested AI reading of page pictures only on clean digital pages; on a scan, a model can "
                  "guess digits it cannot make out.")

    def scanned(self):
        return mk_ingest([{"anchor": PROSE[1]}, {"anchor": "\f", "ocr": self.OCR, "flags": ["scanned"],
                                                "evidence": SCANNED_EVIDENCE}])

    @staticmethod
    def scan_items(r):
        return [it for it in r["items"] if it["status"] == "VISION_ON_SCAN_PAGE"]

    def test_listed_reader_vision_claim_on_a_scanned_page_is_review(self):
        r = lv.check_card(mk_card(self.COV, [self.V1], **self.LISTED), self.scanned(), None)
        self.assertEqual((r["verdict"], r["evidence_grade_suggested"], r["evidence_grade_if_review_confirmed"],
                          r["vision_available"]), ("NEEDS_REVIEW", None, "FULL_TEXT_PARTIAL", True), r["failures"])
        items = self.scan_items(r)
        self.assertEqual([(it["kind"], it["severity"], it["page"], it["claim_id"]) for it in items],
                         [("vision", "review", 2, "V1")])
        self.assertEqual(items[0]["reason"], "The AI reader took the number 88 from a picture of PDF page 2" + self.WHERE
                         + ". " + self.SCAN + " " + self.TESTED_NUM + " Please compare 88 with PDF page 2.")
        self.assertIn("NUMBER_VISION_ONLY", statuses(r, "claim_number"))          # the number status is unchanged
        self.assertTrue(any(s.startswith("VISION_ON_SCAN_PAGE p2 claim V1: The AI reader took the number 88")
                            for s in r["review_items"]))
        self.assertEqual(lv.SEVERITY["VISION_ON_SCAN_PAGE"], "review")
        # a `both` claim on a truly scanned page: its text is DAAF's own OCR, so "machine-read text", never "text layer"
        both = {"claim_id": "B2", "page": 2, "quote": "HERON 2659 The calm bay sheltered 41 painted", "numbers": ["2659"],
                "source": "both"}
        reason = self.scan_items(lv.check_card(mk_card(self.COV, [both], **self.LISTED), self.scanned(), None))[0][
            "reason"]
        self.assertEqual(reason, "The AI reader took the number 2659 from a picture of PDF page 2" + self.WHERE
                         + " and from the page's machine-read text. " + self.SCAN + " " + self.TESTED_NUM
                         + " Please compare 2659 with PDF page 2.")

    def test_reason_texts_are_plain(self):
        # user requirement (2026-10-28): no back-end jargon in a researcher-facing reason
        cases = [mk_card(self.COV, [self.V1], **self.LISTED),
                 mk_card(self.COV, [dict(self.V1, numbers=[])], **self.LISTED),
                 mk_card(self.COV, [dict(self.V1, source="both", quote="HERON 2659 The calm bay sheltered 41 painted",
                                         numbers=["2659"])], **self.LISTED)]
        reasons = [it["reason"] for card in cases for it in self.scan_items(lv.check_card(card, self.scanned(), None))]
        ing = mk_ingest([{"anchor": PROSE[1]}, {"anchor": "\f", "flags": ["scanned"], "evidence": SCANNED_EVIDENCE}])
        reasons += [it["reason"] for it in self.scan_items(lv.check_card(
            mk_card([self.COV[0], cov(2, vision_only=True)], **self.LISTED), ing, None))]
        self.assertEqual(len(reasons), 4)
        for r in reasons:
            for jargon in ("text layer", "vision validation", "digest", "page image", "anchor", "vision-only"):
                self.assertNotIn(jargon, r.lower(), r)
            self.assertIn("(its position in the file; the printed page number may differ)", r)
            self.assertRegex(r, r"Please compare .+ with PDF page 2\.$")

    def test_vision_and_both_claims_on_an_ocr_layer_page(self):
        ing = mk_ingest([dict(self.LAYER, anchor=CheckCardTests.TABLE), {"anchor": PROSE[1]}])
        c = [cov(1, "The counts in Table 4 were invented for the locality rule"),
             cov(2, "The violet ferry carried nineteen patient cartographers")]
        both = {"claim_id": "L1", "page": 1, "quote": "Table 4: Invented harbour counts Herons Gulls Terns 0.31 0.47",
                "numbers": ["0.31", "0.47"], "source": "both"}
        r = lv.check_card(mk_card(c, [both], **self.LISTED), ing, None)
        self.assertEqual((r["verdict"], r["evidence_grade_if_review_confirmed"]), ("NEEDS_REVIEW", "FULL_TEXT_PARTIAL"))
        self.assertEqual(statuses(r, "claim_number"), ["NUMBER_OCR_LAYER_VISION"] * 2)
        items = self.scan_items(r)
        self.assertEqual([(it["page"], it["claim_id"]) for it in items], [(1, "L1")])   # once per page, not per number
        self.assertEqual(items[0]["reason"], "The AI reader took the numbers 0.31, 0.47 from a picture of PDF page 1"
                         + self.WHERE + " and from the page's machine-read text. " + self.OCR_LAYER + " "
                         + self.TESTED_NUM + " Please compare 0.31, 0.47 with PDF page 1.")
        r = lv.check_card(mk_card(c, [dict(both, numbers=[], source="vision")], **self.LISTED), ing, None)
        self.assertEqual((r["verdict"], statuses(r, "claim_quote")), ("NEEDS_REVIEW", ["PASS_OCR_LAYER"]))
        self.assertEqual(self.scan_items(r)[0]["reason"],
                         "The AI reader based this claim on a picture of PDF page 1" + self.WHERE + ". " + self.OCR_LAYER
                         + " " + self.TESTED + " Please compare the claim with PDF page 1.")

    def test_normal_and_sparse_pages_and_non_vision_sources_raise_nothing(self):
        ing = mk_ingest([{"anchor": PROSE[3]}])
        c = [cov(1, "Table 2 reports -0.087* (0.044) and 1,204 boats")]
        for cl in ({"claim_id": "V1", "page": 1, "quote": None, "numbers": ["31"], "source": "vision"},
                   {"claim_id": "V2", "page": 1, "quote": "Table 2 reports −0.087* (0.044) and 1,204 boats with .05 as "
                                                          "the threshold", "numbers": ["1,204"], "source": "both"}):
            r = lv.check_card(mk_card(c, [cl], **self.LISTED), ing, None)
            self.assertEqual((r["verdict"], self.scan_items(r)), ("PARTIAL" if cl["source"] == "vision" else "PASS", []),
                             cl["claim_id"])
        # text and OCR readings of a scan are not vision readings
        ocl = {"claim_id": "O1", "page": 2, "quote": "The calm bay sheltered 41 painted rowing boats", "numbers": ["41"],
               "source": "ocr"}
        r = lv.check_card(mk_card(self.COV, [ocl], **self.LISTED), self.scanned(), None)
        self.assertEqual((r["verdict"], self.scan_items(r)), ("PARTIAL", []))
        # a sparse page (flagged scanned, not mostly one image: a figure with a caption) is not a scan
        sparse = mk_ingest([{"anchor": PROSE[1]}, {"anchor": "Figure 2: Gulls by tide\n\f", "flags": ["figure", "scanned"],
                                                   "evidence": {"figure": ["pdfimages: image 400x300 px covers 53% x 31% "
                                                                           "of the page"]}}])
        r = lv.check_card(mk_card([self.COV[0], cov(2, "Figure 2: Gulls by tide")], [dict(self.V1, numbers=["5"])],
                                  **self.LISTED), sparse, None)
        self.assertEqual(([p["class"] for p in r["pages"]], self.scan_items(r)), (["normal", "sparse"], []))

    def test_vision_only_digest_span_and_unlisted_reader(self):
        ing = mk_ingest([{"anchor": PROSE[1]}, {"anchor": "\f", "flags": ["scanned"], "evidence": SCANNED_EVIDENCE}])
        digest = [self.COV[0], cov(2, vision_only=True)]
        r = lv.check_card(mk_card(digest, **self.LISTED), ing, None)
        items = self.scan_items(r)
        self.assertEqual((r["verdict"], [(it["page"], it["claim_id"]) for it in items]), ("NEEDS_REVIEW", [(2, None)]))
        self.assertIn("VISION_ONLY", statuses(r, "coverage"))
        self.assertEqual(items[0]["reason"], "The AI reader wrote its summary of PDF page 2" + self.WHERE
                         + " from a picture of the page alone. " + self.SCAN + " " + self.TESTED
                         + " Please compare the summary with PDF page 2.")
        # a digest on a page with text is ignored (VISION_ONLY_IGNORED: an anchor must cover it), so no review item
        r = lv.check_card(mk_card([self.COV[0], cov(2, "COMPASS 7314 HERON 2659 The calm bay sheltered 41",
                                                    vision_only=True)], **self.LISTED), self.scanned(), None)
        self.assertEqual((statuses(r, "coverage").count("VISION_ONLY_IGNORED"), self.scan_items(r)), (1, []))
        # a declared span over two scan pages: one item per cited page, for the claim and for each digest
        two = mk_ingest([{"anchor": PROSE[1]}] + [{"anchor": "\f", "flags": ["scanned"], "evidence": SCANNED_EVIDENCE}
                                                  for _ in range(2)])
        span = {"claim_id": "S1", "page": 2, "page_end": 3, "quote": None, "numbers": ["12"], "source": "vision"}
        r = lv.check_card(mk_card(digest + [cov(3, vision_only=True)], [span], **self.LISTED), two, None)
        self.assertEqual(sorted((it["page"], it["claim_id"] or "") for it in self.scan_items(r)),
                         [(2, ""), (2, "S1"), (3, ""), (3, "S1")])
        # an unlisted reader, or vision declared unavailable: its vision readings fail (VISION_UNAVAILABLE_CLAIM),
        #   so the card is FAIL, and the review items stand beside the fails
        for over in ({"reader_model": "claude-unlisted-0", "vision_list_version": "vision-list-2026-10-28"},
                     {"vision_validated": False}):
            r = lv.check_card(mk_card(digest, [self.V1], **over), ing, None)
            self.assertEqual((r["verdict"], statuses(r, "vision").count("VISION_UNAVAILABLE_CLAIM")), ("FAIL", 2), over)
            self.assertEqual(sorted((it["page"], it["claim_id"] or "") for it in self.scan_items(r)),
                             [(2, ""), (2, "V1")], over)
            self.assertEqual(len([s for s in r["review_items"] if s.startswith("VISION_ON_SCAN_PAGE")]), 2, over)
            self.assertEqual("VISION_NOT_ON_LIST" in statuses(r, "vision"), "reader_model" in over, over)

    def test_page_facts_not_rederived_count_as_a_scan(self):
        # fail closed: a page whose flags were not re-derived from the source (as after SOURCE_MISSING) is a scan
        ing = mk_ingest([{"anchor": PROSE[3]}, {"anchor": PROSE[1]}])
        c = [cov(1, "Table 2 reports -0.087* (0.044) and 1,204 boats"),
             cov(2, "The violet ferry carried nineteen patient cartographers")]
        claims = [{"claim_id": "V1", "page": 1, "quote": None, "numbers": ["31"], "source": "vision"},
                  {"claim_id": "V2", "page": 2, "quote": None, "numbers": ["31"], "source": "vision"}]
        ing["page_facts_rederived"] = [1]
        items = self.scan_items(lv.check_card(mk_card(c, claims, **self.LISTED), ing, None))
        self.assertEqual([(it["page"], it["claim_id"]) for it in items], [(2, "V2")])
        self.assertIn("DAAF could not reopen the original PDF to check this page, so it treats it as a possible scan.",
                      items[0]["reason"])
        self.assertIn("from a picture of PDF page 2", items[0]["reason"])
        ing["page_facts_rederived"] = [1, 2]
        self.assertEqual(self.scan_items(lv.check_card(mk_card(c, claims, **self.LISTED), ing, None)), [])

    def test_severity_table_count(self):
        # every SEVERITY key is a status (one, COLUMN_NOT_CHECKED, a label); evidence-card.md § Status index counts them
        self.assertEqual(len(lv.SEVERITY), 81)
        self.assertEqual(lv.VISION_SOURCES, ("vision", "both"))
        index = (_REPO_ROOT / ".claude" / "skills" / "pdf-reading" / "references" / "evidence-card.md").read_text()
        self.assertIn(f"the {len(lv.SEVERITY)} keys of `SEVERITY`", index)
        table = index.split("## Status index", 1)[1].split("\n## ", 1)[0]
        self.assertEqual(sorted(k for k in lv.SEVERITY if f"`{k}`" not in table), [])


# --- numbers-v6 / ladder-v3 (S3-C1b, review cycle 2 NB2 and W-a); every word invented ---
class NumberParsingTests(unittest.TestCase):
    NB2_PAGE = ("Synthetic page: the invented lantern slope was −0.164a in the full model and the intercept was 1.20b "
                "overall.\nThe tide gap between the two invented quays was significant at p < 10⁻³ in every winter.\n"
                "The gull slope was −0.211ab for the amber lanterns nobody ever counted.\n\f")
    WA_PAGE = ("Synthetic page: the gull counts fell by a change of – 0.30 points along the invented quay wall.\n"
               "Keepers on the northern quay recorded the change in their ledger\n– 0.25\nand nobody disputed it.\n"
               "A zero change of – 0 lanterns was logged by the invented night keepers.\n\f")

    def gate(self, anchor, claims):
        ing = mk_ingest([{"anchor": anchor}])
        anchor_cov = next(s for s in anchor.split("\n") if len(s) > 45)[:60]
        return lv.check_card(mk_card([cov(1, anchor_cov)], claims), ing, None)

    def claim(self, cid, quote, numbers=()):
        return {"claim_id": cid, "page": 1, "quote": quote, "numbers": list(numbers), "source": "text"}

    def digits(self, text):
        return [t["digits"] for t in ptc.number_candidates(text)]

    # NB2 (a): one footnote letter after a number is a mark; units and plurals are not
    def test_footnote_letter_reading_is_narrow(self):
        tok = ptc.number_candidates("slope −0.164a here")[0]
        self.assertEqual((tok["digits"], tok["letter"], tok["marks"], tok["raw"]), ("-0.164", "a", "a", "-0.164a"))
        self.assertEqual(ptc.number_candidates("(7b) holds")[0]["paren"], True)
        for text, want in (("intercept 1.20b overall", ["1.20"]), ("Trinh, 2017a.", ["2017"]), ("item 2a, then", ["2"]),
                           ("COVID-19 and K-12", ["19", "12"]), ("the 1990s", []), ("5mg and 10kg", []),
                           ("the 3rd wave", []), ("5m 2x 5k", []), ("rate 1e-5", ["5"]), ("at 5a.m. sharp", []),
                           ("slope −0.164ab", []), ("x 0.5A", [])):
            with self.subTest(text=text):
                self.assertEqual(self.digits(text), want)
        claim = ptc.parse_number("-0.164a")
        self.assertEqual((claim["digits"], claim["letter"]), ("-0.164", "a"))
        page = ptc.number_candidates("slope −0.164a here")
        for c, want in (("-0.164", "exact"), ("-0.164a", "exact"), ("-0.164b", None), ("0.164", None)):
            with self.subTest(claim=c):
                self.assertEqual(ptc.compare_number(ptc.parse_number(c), page)[0], want)

    # W-a: a spaced dash at a line start is a sign; after a word or a closing bracket it is ambiguous
    def test_spaced_dash_line_start_sign_and_ambiguity(self):
        for text, want in (("Gender (Girls)\n– 0.30\n0.12", ("-0.30", False)), ("ledger\n  - 0.25", ("-0.25", False)),
                           ("a change of – 0.30 points", ("0.30", True)), ("(Girls) – 0.30", ("0.30", True)),
                           ("(n − 1)", ("1", True)), ("ages (28 - 75)", ("75", False)), ("all K-\n12", ("12", False)),
                           ("Est = - 0.041", ("-0.041", False))):
            with self.subTest(text=text):
                t = [x for x in ptc.number_candidates(text) if x["digits"].lstrip("-") == want[0].lstrip("-")][0]
                self.assertEqual((t["digits"], t["sign_ambiguous"]), want)
        self.assertTrue(ptc.number_candidates("ages (28 - 75)")[-1]["spaced_dash"])
        # the number view keeps the line start NORMALIZE turned into a space ...
        v = ptc.number_view("Gender (Girls)\n– 0.30\n0.12\n")
        self.assertEqual(v["norm"], "Gender (Girls) - 0.30 0.12")
        self.assertEqual([t["digits"] for t in ptc.view_numbers(v)], ["-0.30", "0.12"])
        # ... and the rejoin-deleted dash after a word (ambiguous) or at a line start (sign)
        self.assertTrue(ptc.view_numbers(ptc.number_view("a change of –\n0.30 here"))[0]["sign_ambiguous"])
        self.assertEqual(ptc.view_numbers(ptc.number_view("cells\n-\n0.30 here"))[0]["digits"], "-0.30")
        self.assertEqual(len(ptc.normalize_map("a –\n0.30")), 6)
        # a declared span: the right page's first line starts at the join
        j = ptc.join_views(ptc.number_view("left page text\n"), ptc.number_view("– 0.30 right page\n"))
        self.assertEqual([t["digits"] for t in ptc.view_numbers(j)], ["-0.30"])
        amb = ptc.number_candidates("a change of – 0.30 points and of – 0 lanterns")
        for c, want in (("0.30", "sign-ambiguous"), ("-0.30", "sign-ambiguous"), ("0.3", "precision"), ("0", "exact")):
            with self.subTest(claim=c):
                self.assertEqual(ptc.compare_number(ptc.parse_number(c), amb)[0], want)

    # NB2 (b) + FX-Q: the quote-number rule compares marks and sign-shaped dashes
    def test_quote_number_check_marks_and_sign_dashes(self):
        def check(page, quote):
            norm, spans = ptc.quote_spans(quote, page)
            self.assertTrue(spans, quote)
            return ptc.quote_number_check(quote, ptc.number_view(page), spans)
        for page, quote, want in (
                (self.NB2_PAGE, "was significant at p < 10⁻³ in every", (True, None)),
                (self.NB2_PAGE, "was significant at p < 10³ in every", (False, "marks")),
                (self.NB2_PAGE, "lantern slope was −0.164a in the full", (True, None)),
                (self.NB2_PAGE, "lantern slope was 0.164a in the full", (False, "digits")),
                (self.NB2_PAGE, "gull slope was 0.211ab for the amber", (False, "sign-dash")),
                (self.NB2_PAGE, "gull slope was −0.211ab for the amber", (True, None)),
                ("Synthetic: all K-\n12 harbour schools counted lanterns.", "all K-12 harbour schools", (True, None)),
                # the number view splits "K-\n12" (S3-A2), so a quote "K12" already differs in its tokens
                ("Synthetic: all K-\n12 harbour schools counted lanterns.", "all K12 harbour schools", (False, "digits")),
                # a dash the line-break rejoin deleted, where no token is parsed
                ("Synthetic: the code K-\n12ab ran twice that winter.", "the code K12ab ran twice", (False, "sign-dash")),
                ("Synthetic: the code K-\n12ab ran twice that winter.", "the code K-12ab ran twice", (True, None)),
                # a range dash the quote adds between digits is allowed (FX-Q; kept by ladder-v4)
                ("Synthetic: the invented range 5 10 of lanterns.", "the invented range 5-10 of lanterns", (True, None)),
                (self.WA_PAGE, "recorded the change in their ledger – 0.25 and nobody", (True, None)),
                (self.WA_PAGE, "recorded the change in their ledger 0.25 and nobody", (False, "digits")),
                (self.WA_PAGE, "fell by a change of – 0.30 points", (True, None)),
                (self.WA_PAGE, "fell by a change of 0.30 points", (False, "sign-dash"))):
            with self.subTest(quote=quote):
                r = check(page, quote)
                self.assertEqual((r["agree"], r["why"]), want)
        # a dash before the span's first char is not the span's; extra quote dashes are allowed
        self.assertEqual(ptc.sign_dash_flags("x -5 and -6", 3, 11), [False, False, False, False, True])
        self.assertEqual(ptc.quote_numbers_agree("q", None, []), (None, [], None))

    def test_gate_footnote_letter_superscript_minus_and_sign_dash(self):
        q = "the invented lantern slope was −0.164a in the full model"
        r = self.gate(self.NB2_PAGE, [self.claim("G1", q, ["-0.164"])])
        self.assertEqual((r["verdict"], statuses(r, "claim_number")), ("PASS", ["NUMBER_OK"]), r["review_items"])
        self.assertIn("footnote letter 'a'", [it for it in r["items"] if it["kind"] == "claim_number"][0]["reason"])
        r = self.gate(self.NB2_PAGE, [self.claim("F1", q.replace("−", ""))])
        it = [x for x in r["items"] if x["kind"] == "claim_quote"][0]
        self.assertEqual((r["verdict"], it["status"], it["quote_numbers"], it["page_numbers"]),
                         ("NEEDS_REVIEW", "QUOTE_NUMBERS_DIFFER", ["0.164"], ["-0.164"]))
        r = self.gate(self.NB2_PAGE, [self.claim("F2", "two invented quays was significant at p < 10³ in every")])
        self.assertEqual(statuses(r, "claim_quote"), ["QUOTE_NUMBERS_DIFFER"])
        self.assertIn("superscripts or footnote letters", r["items"][-1]["reason"])
        r = self.gate(self.NB2_PAGE, [self.claim("F3", "The gull slope was 0.211ab for the amber lanterns")])
        self.assertEqual(statuses(r, "claim_quote"), ["QUOTE_NUMBERS_DIFFER"])
        self.assertIn("sign-shaped dash", r["items"][-1]["reason"])

    def test_gate_sign_ambiguous_and_line_start(self):
        q = "the gull counts fell by a change of – 0.30 points along the invented"
        for numbers in (["0.30"], ["-0.30"]):
            r = self.gate(self.WA_PAGE, [self.claim("A1", q, numbers)])
            num = [it for it in r["items"] if it["kind"] == "claim_number"][0]
            self.assertEqual((r["verdict"], num["status"], num["severity"], num["label"], num["locality"]),
                             ("NEEDS_REVIEW", "NUMBER_SIGN_AMBIGUOUS", "review", "sign-ambiguous", None), numbers)
        self.assertEqual(lv.SEVERITY["NUMBER_SIGN_AMBIGUOUS"], "review")
        r = self.gate(self.WA_PAGE, [self.claim("Z1", "A zero change of – 0 lanterns was logged by the invented",
                                                ["0"])])
        self.assertEqual((r["verdict"], statuses(r, "claim_number")), ("PASS", ["NUMBER_OK"]))   # a zero's sign is moot
        q = "recorded the change in their ledger – 0.25 and nobody disputed it"
        r = self.gate(self.WA_PAGE, [self.claim("L1", q, ["-0.25"])])
        self.assertEqual((r["verdict"], statuses(r, "claim_number")), ("PASS", ["NUMBER_OK"]), r["review_items"])
        r = self.gate(self.WA_PAGE, [self.claim("L2", q, ["0.25"])])
        self.assertEqual((r["verdict"], statuses(r, "claim_number")), ("FAIL", ["NUMBER_MISSING"]))

    # --- ladder-v4 (S3-D, review cycle 3 quality W1): a quote that ADDS a sign-shaped dash ---
    ADD_PAGE = ("Synthetic page: the invented gull counts rose by 0.30 points along the quay wall after the reform.\n"
                "Invented lantern outcomes by keeper (Girls) 0.30 and (Boys) 0.12 in the amber winter.\n"
                "The invented plot totals [26 28] were logged, and the slope −0.164 held for the gulls on the quay.\n"
                "The keepers noted a change of –\n0.30 points in the ledger that nobody disputed.\n\f")

    def test_quote_number_check_added_sign_dash(self):
        def check(quote, page=None):
            page = page or self.ADD_PAGE
            norm, spans = ptc.quote_spans(quote, page)
            self.assertTrue(spans, quote)
            return ptc.quote_number_check(quote, ptc.number_view(page), spans)
        for quote, want in (
                ("gull counts rose by – 0.30 points along the quay", (False, "sign-dash-added")),
                ("by keeper (Girls)−0.30 and (Boys) 0.12 in the", (False, "sign-dash-added")),
                ("by keeper (Girls) -0.30 and (Boys) 0.12 in the", (False, "digits")),   # the token's sign differs
                ("gull counts rose by 0.30 points along the quay", (True, None)),
                # a spaced range dash after a digit cannot read as a sign (as parse_numbers reads it)
                ("The invented plot totals [26 - 28] were logged", (True, None)),
                # the page prints the dash just before the span's first char (lookback)
                ("- 0.164 held for the gulls on the quay", (True, None)),
                # the line-break rejoin deleted the page's dash (`dashed`): not added
                ("noted a change of – 0.30 points in the ledger", (True, None))):
            with self.subTest(quote=quote):
                r = check(quote)
                self.assertEqual((r["agree"], r["why"]), want)
        # compound and range dashes glued to the digit stay allowed
        self.assertEqual((check("all K-12 harbour schools", "Synthetic: all K-\n12 harbour schools counted.")["agree"],
                          check("the invented range 5-10 of lanterns", "Synthetic: the invented range 5 10 of lanterns.")
                          ["agree"]), (True, True))
        s = "K-12 (a)-3 5 - 6 x - 7"
        self.assertEqual(ptc.sign_dash_flags(s, 0, len(s)), [False, True, False, False, False, False, True, False, True,
                                                             False, True])
        self.assertEqual(ptc.sign_dash_flags(s, 0, len(s), sign_only=True),
                         [False, False, False, False, False, False, True, False, False, False, True])
        self.assertEqual(ptc.sign_dash_flags("x -5 and -6", 3, 11, lookback=True), [True, False, False, False, True])

    def test_gate_added_sign_dash(self):
        q = "the invented gull counts rose by – 0.30 points along the quay wall"
        r = self.gate(self.ADD_PAGE, [self.claim("D1", q)])
        it = [x for x in r["items"] if x["kind"] == "claim_quote"][0]
        self.assertEqual((r["verdict"], it["status"], it["status_if_confirmed"], it["severity"]),
                         ("NEEDS_REVIEW", "QUOTE_NUMBERS_DIFFER", "PASS_SKELETON", "review"))
        self.assertIn("the quote prints a sign-shaped dash", it["reason"])
        # the declared number is still checked: the added sign is printed nowhere on this page
        one = self.ADD_PAGE.split("\n")[0] + "\nNo other figure appears on this invented page of the keepers' notes.\n\f"
        r = self.gate(one, [self.claim("D3", q, ["-0.30"])])
        self.assertEqual((r["verdict"], statuses(r, "claim_number")), ("FAIL", ["NUMBER_MISSING"]))
        r = self.gate(self.ADD_PAGE, [self.claim("D5", "Invented lantern outcomes by keeper (Girls)−0.30 and (Boys) "
                                                       "0.12 in the amber")])
        self.assertEqual((r["verdict"], statuses(r, "claim_quote")), ("NEEDS_REVIEW", ["QUOTE_NUMBERS_DIFFER"]))
        r = self.gate(self.ADD_PAGE, [self.claim("G1", "the invented gull counts rose by 0.30 points along the quay "
                                                       "wall", ["0.30"])])
        self.assertEqual((r["verdict"], statuses(r, "claim_number")), ("PASS", ["NUMBER_OK"]), r["review_items"])


class HtmlCardParseTests(unittest.TestCase):
    GOOD =mk_html_card([sec("front", "x")], [hclaim("C1", "1.1", "q", section_end="1.2")])

    def bad(self, obj):
        with self.assertRaises(lv.LitVerifyError) as cm:
            lv.parse_card("```lit-verify\n" + json.dumps(obj) + "\n```\n")
        self.assertEqual(cm.exception.code, 8)
        return cm.exception.note

    def mutate(self, **changes):
        c = json.loads(json.dumps(self.GOOD))
        c.update(changes)
        return c

    def test_good_v2_cards_parse(self):
        self.assertEqual(lv.parse_card("```lit-verify\n" + json.dumps(self.GOOD) + "\n```\n")["anchor_kind"],
                         "arxiv_html")
        pdf = mk_card([cov(1, "x")])
        pdf.update(schema_version="lit-verify-card-v2", anchor_kind="pdf", source_sha256=pdf.pop("source_pdf_sha256"),
                   source_version=None)
        self.assertEqual(lv.parse_card("```lit-verify\n" + json.dumps(pdf) + "\n```\n")["claims"], [])

    def test_v2_schema_errors(self):
        claim = self.GOOD["claims"][0]
        pdf = mk_card([cov(1, "x")], schema_version="lit-verify-card-v2", anchor_kind="pdf",
                      source_sha256="a" * 64)
        pdf_with_old = dict(pdf)
        pdf.pop("source_pdf_sha256")
        cases = [
            (self.mutate(anchor_kind="epub"), "anchor_kind must be one of"),
            (self.mutate(source_version=None), "source_version is required"),
            (self.mutate(source_version="2"), "source_version is required"),
            (dict(pdf, source_version="v2"), "applies to anchor_kind \"arxiv_html\" only"),
            (pdf_with_old, "unknown field"),                                        # v1's name in a v2 card
            (self.mutate(vision_mode="auto", vision_validated=True), "write vision_mode \"off\""),
            (self.mutate(coverage=[{"page": 1, "anchors": [], "summary": ""}]), "unknown field"),
            (self.mutate(coverage=[sec("front", "x", vision_only=True)]), "unknown field"),
            (self.mutate(coverage=[sec("front", "x"), sec("front", "y")]), "listed twice"),
            (self.mutate(coverage=[sec("<!-- unit 1/2", "x")]), "unit label"),
            (self.mutate(claims=[dict(claim, page=1)]), "unknown field"),
            (self.mutate(claims=[dict(claim, section_end="1.1")]), "NEXT section"),
            (self.mutate(claims=[dict(claim, source="vision")]), "must be \"text\""),
            (self.mutate(claims=[dict(claim, source="ocr")]), "must be \"text\""),
            (self.mutate(claims=[dict(claim, quote="")]), "non-empty string"),
            (self.mutate(claims=[dict(claim, section="")]), "unit label"),
        ]
        for obj, needle in cases:
            with self.subTest(needle=needle):
                self.assertIn(needle, self.bad(obj))
        self.assertEqual(lv.parse_card("```lit-verify\n" + json.dumps(self.mutate(vision_mode="auto")) + "\n```\n")[
            "vision_mode"], "auto")                                             # auto + vision_validated false is fine


# --- Card parsing (exit 8) ---------------------------------------------------------
class CardParseTests(unittest.TestCase):
    GOOD = mk_card([cov(1, "x")], [{"claim_id": "C1", "page": 1, "quote": "q", "numbers": [], "source": "text"}])

    def bad(self, text):
        with self.assertRaises(lv.LitVerifyError) as cm:
            lv.parse_card(text)
        self.assertEqual(cm.exception.code, 8)
        return cm.exception.note

    def block(self, obj):
        return "front\n```lit-verify\n" + json.dumps(obj) + "\n```\n"

    def mutate(self, **changes):
        c = json.loads(json.dumps(self.GOOD))
        c.update(changes)
        return c

    def test_good_card_parses(self):
        self.assertEqual(lv.parse_card(self.block(self.GOOD))["paper_key"], "user_00000001")
        self.assertEqual(lv.parse_card("~~~~ lit-verify\n" + json.dumps(self.GOOD) + "\n~~~~\n")["claims"][0]["page"], 1)

    def test_block_errors(self):
        self.assertIn("no ```lit-verify", self.bad("# card without a block\n```json\n{}\n```\n"))
        self.assertIn("2 lit-verify blocks", self.bad(self.block(self.GOOD) + self.block(self.GOOD)))
        self.assertIn("never closed", self.bad("```lit-verify\n{}\n"))
        self.assertIn("not valid JSON", self.bad("```lit-verify\n{oops}\n```\n"))
        self.assertIn("duplicate JSON key", self.bad('```lit-verify\n{"a": 1, "a": 2}\n```\n'))
        self.assertIn("non-finite", self.bad('```lit-verify\n{"a": NaN}\n```\n'))

    def test_schema_errors(self):
        cases = [
            (self.mutate(schema_version="lit-verify-card-v9"), "unknown schema_version"),
            (self.mutate(extra=1), "unknown field"),
            (self.mutate(vision_validated="true"), "vision_validated"),
            (self.mutate(source_pdf_sha256="ABC"), "source_pdf_sha256"),
            (self.mutate(coverage=[cov(True, "x")]), "page must be an integer"),
            (self.mutate(coverage=[cov("1", "x")]), "page must be an integer"),
            (self.mutate(coverage=[cov(1, "x"), cov(1, "y")]), "listed twice"),
            (self.mutate(coverage=[{"anchors": [], "summary": ""}]), "missing field"),
            (self.mutate(claims=self.GOOD["claims"] * 2), "duplicate claim_id"),
            (self.mutate(claims=[dict(self.GOOD["claims"][0], page_end=3)]), "page_end"),
            (self.mutate(claims=[dict(self.GOOD["claims"][0], quote=None)]), "quote may be empty"),
            (self.mutate(claims=[dict(self.GOOD["claims"][0], numbers=[0.5])]), "numbers"),
            (self.mutate(claims=[dict(self.GOOD["claims"][0], source="model")]), "source"),
            (self.mutate(ingest_suffix="_A"), "ingest_suffix"),
        ]
        for obj, needle in cases:
            with self.subTest(needle=needle):
                self.assertIn(needle, self.bad(self.block(obj)))
        self.assertEqual(lv.parse_card(self.block(self.mutate(claims=[dict(
            self.GOOD["claims"][0], quote=None, source="vision")])))["claims"][0]["quote"], None)


# --- CLI guards (no ingest needed) ---------------------------------------------------
class GuardTests(ScratchCase):
    def test_refused_dirs_exit_2_without_row(self):
        card = FIX / "single_column_genuine.md"
        for bad in ("/tmp", str(_REPO_ROOT / ".claude" / "skills"), "/etc"):
            with self.subTest(bad=bad):
                code, _, err = run_main(["card", bad, card])
                self.assertEqual(code, 2)
                self.assertIn("refused", err)
        code, _, err = run_main(["selftest", "/tmp"])
        self.assertEqual((code, "refused" in err), (2, True))

    def test_usage_errors_exit_1_without_row(self):
        key_dir = self.papers / "user_00000001"
        key_dir.mkdir()
        card = self.write_card(key_dir, "evidence_card.md", {})
        for argv in (["card"], ["card", key_dir], ["card", self.papers / "user_0000000f", card],
                     ["card", key_dir, key_dir / "missing.md"], ["card", key_dir, card, "--ingest-suffix", "_A"],
                     ["bogus"], []):
            with self.subTest(argv=argv):
                self.assertEqual(run_main(argv)[0], 1)
        self.assertEqual(rows_of(self.papers), [])

    def test_card_path_and_paper_key_guards_write_rows(self):
        key_dir = self.papers / "user_00000001"
        key_dir.mkdir()
        outside = self.write_card(self.papers, "evidence_card.md", {})
        code, _, err = run_main(["card", key_dir, outside])
        self.assertEqual(code, 2)
        self.assertIn("directly inside PAPER_DIR", err)
        bad_dir = self.papers / "not_a_key"
        bad_dir.mkdir()
        code, _, _ = run_main(["card", bad_dir, self.write_card(bad_dir, "evidence_card.md", {})])
        self.assertEqual(code, 2)
        rows = rows_of(self.papers)
        self.assertEqual([r["exit_code"] for r in rows], [2, 2])
        self.assertTrue(all(r["kind"] == "lit_verify" and r["requesting_context"] == "unit-test" for r in rows))

    def test_secret_in_argument_refused_and_never_persisted(self):
        key_dir = self.papers / "user_00000001"
        key_dir.mkdir()
        card = self.write_card(key_dir, f"evidence_card_{SENTINEL_KEY}.md", {})
        code, out, err = run_main(["card", key_dir, card])
        self.assertEqual(code, 2)
        self.assertIn("UNIT_TEST_API_KEY", err)
        self.assertNotIn(SENTINEL_KEY, (self.papers / "MANIFEST.jsonl").read_text() + out + err)

    def test_unparseable_card_exits_8_with_row(self):
        key_dir = self.papers / "user_00000001"
        key_dir.mkdir()
        card = self.write_card(key_dir, "evidence_card.md", None, raw="# no block here\n")
        code, _, _ = run_main(["card", key_dir, card])
        self.assertEqual(code, 8)
        row = rows_of(self.papers)[-1]
        self.assertEqual((row["exit_code"], row["card"]["path"]), (8, "user_00000001/evidence_card.md"))
        self.assertFalse(list(key_dir.glob("card_check*")))

    def test_missing_library_exits_10(self):
        key_dir = self.papers / "user_00000001"
        key_dir.mkdir()
        card = self.write_card(key_dir, "evidence_card.md", mk_card([cov(1, "x")]))
        real = lv.try_import
        with mock.patch.object(lv, "try_import", side_effect=lambda n: None if n.startswith("rapidfuzz") else real(n)):
            code, _, _ = run_main(["card", key_dir, card])
        self.assertEqual(code, 10)
        self.assertIn("rapidfuzz", rows_of(self.papers)[-1]["note"])


# --- Synthetic ingests on disk: ingest loading, integrity, rows, naming -------------
@unittest.skipUnless(CAN_RUN_CLI, CLI_WHY)
class IngestAndRowTests(ScratchCase):
    def genuine_block(self, key, src):
        cases = lv.selftest_cases({})
        _, _, coverage, claims, *_ = cases[0]
        return json.loads(lv.selftest_card(key, src, coverage, claims).split("```lit-verify\n", 1)[1]
                          .split("\n```", 1)[0])

    def test_pass_row_fields_and_never_overwrite(self):
        key_dir, src = self.synthetic()
        block = self.genuine_block(key_dir.name, src)
        card = self.write_card(key_dir, "evidence_card.md", block)
        code, out, err = run_main(["card", key_dir, card])
        self.assertEqual(code, 0, err)
        self.assertIn("lit_verify: PASS user_5e1f7e5a", out)
        row = rows_of(self.papers)[-1]
        for k in ("kind", "tool_version", "command", "paper_key", "parameters", "timestamp", "requesting_context",
                  "card", "ingest", "artifacts", "verdict", "evidence_grade_suggested", "counts", "redaction_count",
                  "secret_redactions", "exit_code", "note"):
            self.assertIn(k, row)
        self.assertEqual((row["kind"], row["command"], row["verdict"], row["exit_code"]),
                         ("lit_verify", "card", "PASS", 0))
        self.assertEqual(row["card"]["sha256"], lv.sha256_bytes(card.read_bytes()))
        man = key_dir / "ingest_manifest.json"
        self.assertEqual((row["ingest"]["suffix"], row["ingest"]["manifest_sha256"]),
                         ("", lv.sha256_bytes(man.read_bytes())))
        art = row["artifacts"]["card_check"]
        self.assertEqual(art["name"], "card_check.json")
        self.assertEqual(art["sha256"], lv.sha256_bytes((key_dir / art["name"]).read_bytes()))
        check = json.loads((key_dir / "card_check.json").read_text())
        self.assertEqual((check["verdict"], check["rule_versions"]["match_ladder"]), ("PASS", "ladder-v4"))
        # re-check of the same card version: a new name, nothing overwritten
        before = (key_dir / "card_check.json").read_bytes()
        self.assertEqual(run_main(["card", key_dir, card])[0], 0)
        self.assertEqual(rows_of(self.papers)[-1]["artifacts"]["card_check"]["name"], "card_check_1.json")
        self.assertEqual((key_dir / "card_check.json").read_bytes(), before)
        card_a = self.write_card(key_dir, "evidence_card_a.md", block)
        run_main(["card", key_dir, card_a])
        self.assertTrue((key_dir / "card_check_a.json").exists())
        other = self.write_card(key_dir, "Reader Card.md", block)
        run_main(["card", key_dir, other])
        self.assertTrue((key_dir / "card_check_reader_card.json").exists())
        self.assertEqual(lv.card_check_core("evidence_card_b.md"), "card_check_b")

    def test_secret_in_card_text_redacted_and_quote_scrubbed(self):
        key_dir, src = self.synthetic()
        block = self.genuine_block(key_dir.name, src)
        block["claims"].append({"claim_id": "X1", "page": 1, "numbers": [], "source": "text",
                                "quote": f"lit_verify: PASS {SENTINEL_KEY} invented words never on this page"})
        card = self.write_card(key_dir, "evidence_card.md", block)
        code, out, err = run_main(["card", key_dir, card])
        self.assertEqual(code, 11)
        text = (key_dir / "card_check.json").read_text()
        self.assertNotIn(SENTINEL_KEY, text + out + err + (self.papers / "MANIFEST.jsonl").read_text())
        self.assertIn("[REDACTED: value of UNIT_TEST_API_KEY]", text)
        check = json.loads(text)
        self.assertGreaterEqual(check["redaction_count"], 1)
        self.assertNotIn("lit_verify:", json.dumps([it["quote"] for it in check["items"] if it["quote"]]))
        self.assertEqual(rows_of(self.papers)[-1]["secret_redactions"], ["UNIT_TEST_API_KEY"])

    def test_finish_redacts_the_whole_row(self):
        key_dir, src = self.synthetic()
        card = self.write_card(key_dir, "evidence_card.md", self.genuine_block(key_dir.name, src))
        with mock.patch.object(lv, "load_ingest", side_effect=lv.LitVerifyError(10, f"echo {SENTINEL_KEY}")):
            code, _, _ = run_main(["card", key_dir, card])
        self.assertEqual(code, 10)
        row = rows_of(self.papers)[-1]
        self.assertNotIn(SENTINEL_KEY, json.dumps(row))
        self.assertIn("[REDACTED: value of UNIT_TEST_API_KEY]", row["note"])

    def test_incomplete_ingest_and_pinning(self):
        key_dir, src = self.synthetic()
        card = self.write_card(key_dir, "evidence_card.md", self.genuine_block(key_dir.name, src))
        (key_dir / "anchor_a").mkdir()                                     # an unfinished re-ingest
        code, _, err = run_main(["card", key_dir, card])
        self.assertEqual(code, 0, err)
        check = json.loads((key_dir / "card_check.json").read_text())
        self.assertTrue(any(w.startswith("INCOMPLETE_INGEST_IGNORED") for w in check["warnings"]))
        code, _, err = run_main(["card", key_dir, card, "--ingest-suffix", "_a"])
        self.assertEqual(code, 10)
        self.assertIn("did not finish", err)
        self.assertEqual(run_main(["card", key_dir, card, "--ingest-suffix="])[0], 0)
        (key_dir / "ingest_manifest.json").unlink()
        self.assertEqual(run_main(["card", key_dir, card])[0], 10)

    def test_missing_anchor_and_escaping_path(self):
        key_dir, src = self.synthetic()
        card = self.write_card(key_dir, "evidence_card.md", self.genuine_block(key_dir.name, src))
        (key_dir / "anchor" / "p002.txt").unlink()
        code, _, err = run_main(["card", key_dir, card])
        self.assertEqual(code, 10)
        self.assertIn("incomplete ingest", err)
        key_dir2, src2 = self.synthetic("user_5e1f7e5d")
        man = json.loads((key_dir2 / "ingest_manifest.json").read_text())
        man["pages"][0]["anchor"]["path"] = "../../../../CLAUDE.md"
        (key_dir2 / "ingest_manifest.json").write_text(json.dumps(man))
        card2 = self.write_card(key_dir2, "evidence_card.md", self.genuine_block(key_dir2.name, src2))
        code, _, err = run_main(["card", key_dir2, card2])
        self.assertEqual(code, 2)
        self.assertIn("outside PAPER_DIR", err)

    def test_tampered_artifacts_fail_as_recorded_results(self):
        key_dir, src = self.synthetic("user_5e1f7e5b", pages="B")
        cases = lv.selftest_cases({})
        _, _, coverage, claims, *_ = cases[9]
        card = self.write_card(key_dir, "evidence_card.md", None, raw=lv.selftest_card(key_dir.name, src, coverage,
                                                                                        claims))
        self.assertEqual(run_main(["card", key_dir, card])[0], 0)
        with open(key_dir / "ocr" / "p002.txt", "a") as f:
            f.write("tampered\n")
        code, _, _ = run_main(["card", key_dir, card])
        self.assertEqual(code, 11)
        check = json.loads((key_dir / "card_check_1.json").read_text())
        self.assertIn("OCR_HASH_MISMATCH", statuses(check))
        man = key_dir / "ingest_manifest.json"
        man.write_text(man.read_text().replace('"normalize-v1"', '"normalize-v1" '))
        code, _, _ = run_main(["card", key_dir, card])
        check = json.loads((key_dir / "card_check_2.json").read_text())
        self.assertIn("INGEST_MANIFEST_HASH_MISMATCH", statuses(check))
        m = json.loads(man.read_text())
        m["artifacts"]["page_index"]["sha256"] = "0" * 64
        man.write_text(json.dumps(m))
        self.assertEqual(run_main(["card", key_dir, card])[0], 11)
        check = json.loads((key_dir / "card_check_3.json").read_text())
        self.assertIn("PAGE_INDEX_HASH_MISMATCH", statuses(check))

    def test_lane_b_is_hash_checked_and_unused_on_mismatch(self):
        key_dir, src = self.synthetic("user_5e1f7e5e", pages="R")
        cases = [c for c in lv.selftest_cases({}) if c[1] == "R"]
        _, _, coverage, claims, *_ = cases[0]
        card = self.write_card(key_dir, "evidence_card.md", None, raw=lv.selftest_card(key_dir.name, src, coverage,
                                                                                        claims))
        self.assertEqual(run_main(["card", key_dir, card])[0], 0)
        check = json.loads((key_dir / "card_check.json").read_text())
        nums = [it for it in check["items"] if it["kind"] == "claim_number"]
        self.assertEqual((check["verdict"], nums[0]["locality"]), ("PASS", "row"))
        self.assertEqual(check["constants"]["ROW_LABEL_MIN_CHARS"], ptc.ROW_LABEL_MIN_CHARS)
        self.assertEqual(check["rule_versions"]["numbers"], "numbers-v6")
        # 1.5.0: the row prints 0.62 and 0.63, so the cleared number is
        #   labeled; counted, printed on stdout and recorded with its constants
        self.assertEqual((nums[0]["column_checked"], nums[0]["column_label"], nums[0]["column_values"]),
                         (False, "column-not-checked", 2))
        self.assertEqual((check["counts"]["numbers_column_not_checked"], len(check["column_not_checked_items"])), (1, 1))
        self.assertIn("column-not-checked: 2 comparable values", check["column_not_checked_items"][0])
        self.assertEqual((check["rule_versions"]["column_check"], check["constants"]["COLUMN_UNCHECKED_SEVERITY"]),
                         ("column-check-v1", "label"))
        self.assertEqual(rows_of(self.papers)[-1]["counts"]["numbers_column_not_checked"], 1)
        _, out, _ = run_main(["card", key_dir, card])
        self.assertIn("1 number(s), 1 column-not-checked;", out)
        with open(key_dir / "lane_b" / "p001.txt", "a") as f:
            f.write("North Quay (with tide gauge) 0.74\n")                 # a planted row
        self.assertEqual(run_main(["card", key_dir, card])[0], 11)
        check = json.loads((key_dir / "card_check_2.json").read_text())
        self.assertIn("LANE_B_HASH_MISMATCH", statuses(check, "integrity"))
        self.assertEqual([it["row_match"] for it in check["items"] if it["kind"] == "claim_number"], [None])

    @unittest.skipUnless(HAVE_POLARS, "needs polars (pdf_ingest's arXiv HTML lane builds selftest paper H)")
    def test_selftest_passes_and_cleans_up(self):
        code, out, err = run_main(["selftest", self.root])
        self.assertEqual(code, 0, out + err)
        self.assertIn("SELFTEST PASS: 71/71", out)                                  # 1.10.0: + 18 report
        self.assertIn("report: claims table forged to verified", out)               # 1.10.0 (user decision, October 2026)
        self.assertIn("forged ingest set, consistent hashes and row", out)          # 1.7.0 (W1)
        self.assertIn("listed reader's vision reading on a scan page", out)         # 1.8.0 part 5
        for case in ("forged header/footer line, span skips it", "forged page flags lift the OCR-layer cap",
                     "forged OCR text on a text page"):                         # 1.8.0 (review cycle 2)
            self.assertIn(case, out)
        for case in ("minus deleted before a footnote letter", "superscript minus deleted from an exponent",
                     "spaced minus after a word", "spaced minus at a line start, sign-flipped claim"):   # S3-C1b
            self.assertIn(case, out)
        self.assertIn("prose quote starting with a row label", out)                # numbers-v5
        self.assertIn("HTML quote cited to another section", out)
        self.assertIn("cols 0.63:not-checked,5:checked", out)                  # 1.5.0
        row = rows_of(self.root)[-1]
        self.assertEqual((row["command"], row["verdict"], row["exit_code"]), ("selftest", "PASS", 0))
        self.assertTrue(row["counts"]["work_dir_removed"])
        self.assertFalse(any(p.name.startswith("lit_verify_selftest_") for p in self.root.iterdir()))

    def test_wrapper_passes_exit_codes_through(self):
        proc = subprocess.run(["bash", str(_SCRIPTS / "lit_verify.sh")], capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 1)
        proc = subprocess.run(["bash", str(_SCRIPTS / "lit_verify.sh"), "selftest", "/tmp"], capture_output=True,
                              text=True, timeout=60)
        self.assertEqual(proc.returncode, 2)


# --- 1.7.0 (S3-B1, review W1): re-derivation and the ingest row -----------------------
@unittest.skipUnless(CAN_RUN_CLI, CLI_WHY)
class RederiveTests(ScratchCase):
    def card_for(self, key_dir, src, extra_claims=()):
        _, _, coverage, claims, *_ = lv.selftest_cases({})[0]
        return self.write_card(key_dir, "evidence_card.md", None,
                               raw=lv.selftest_card(key_dir.name, src, coverage, list(claims) + list(extra_claims)))

    def last_check(self, key_dir):
        art = rows_of(self.papers)[-1]["artifacts"]["card_check"]
        return json.loads((key_dir / art["name"]).read_text())

    def test_forged_ingest_set_fails_with_and_without_a_forged_row(self):
        key_dir, src = self.synthetic()
        fab = {"claim_id": "Z1", "page": 1, "quote": lv.SELFTEST_FABRICATED, "numbers": [], "source": "text"}
        card = self.card_for(key_dir, src, [fab])
        lv.forge_ingest_set(str(self.papers), key_dir.name, lv.SELFTEST_FABRICATED, lv.parquet_reader(),
                            lv.parquet_writer())
        code, out, err = run_main(["card", key_dir, card])
        check = self.last_check(key_dir)
        self.assertEqual((code, check["verdict"], check["ingest"]["suffix"]), (11, "FAIL", "_a"), out + err)
        mm = [it for it in check["items"] if it["status"] == "ANCHOR_REDERIVE_MISMATCH"]
        self.assertEqual([(it["page"], it["severity"]) for it in mm], [(1, "fail")])
        self.assertEqual((check["rederive"]["outcome"], check["rederive"]["anchor_mismatches"]), ("mismatch", [1]))
        self.assertEqual(check["rule_versions"]["rederive"], "rederive-v2")
        self.assertNotIn("NO_INGEST_ROW", statuses(check))                      # the forged row is present
        rows = [json.loads(x) for x in (self.papers / "MANIFEST.jsonl").read_text().splitlines()]
        kept = [r for r in rows if "FORGED" not in (r.get("note") or "")]
        (self.papers / "MANIFEST.jsonl").write_text("".join(json.dumps(r) + "\n" for r in kept))
        code, _, _ = run_main(["card", key_dir, card])
        check = self.last_check(key_dir)
        self.assertEqual(code, 11)
        self.assertTrue({"ANCHOR_REDERIVE_MISMATCH", "NO_INGEST_ROW"} <= set(statuses(check, "integrity")))
        self.assertEqual(rows_of(self.papers)[-1]["rederive"]["anchor_mismatches"], 1)

    def test_no_ingest_row_is_a_fail(self):
        writer = lv.parquet_writer()
        src = lv.build_synthetic_ingest(str(self.papers), "user_5e1f7e5a", lv.SELFTEST_PAGES["A"], writer,
                                        with_row=False)
        key_dir = self.papers / "user_5e1f7e5a"
        code, _, _ = run_main(["card", key_dir, self.card_for(key_dir, src)])
        check = self.last_check(key_dir)
        self.assertEqual((code, check["verdict"], statuses(check, "integrity")), (11, "FAIL", ["NO_INGEST_ROW"]))
        self.assertEqual(lv.SEVERITY["NO_INGEST_ROW"], "fail")

    def test_unregistered_synthetic_source_is_missing(self):
        key_dir, src = self.synthetic()
        card = self.card_for(key_dir, src)
        self.assertEqual(run_main(["card", key_dir, card])[0], 0)
        self.assertEqual(self.last_check(key_dir)["rederive"]["outcome"], "match")
        entry = lv.SYNTHETIC_SOURCES.pop(src)
        try:
            code, _, _ = run_main(["card", key_dir, card])
        finally:
            lv.SYNTHETIC_SOURCES[src] = entry
        check = self.last_check(key_dir)
        self.assertEqual((code, statuses(check, "integrity"), check["rederive"]["outcome"]),
                         (11, ["SOURCE_MISSING"], "source missing"))

    def test_tampered_lane_b_and_ocr_are_reported(self):
        key_dir, src = self.synthetic("user_5e1f7e5b", pages="B")
        _, _, coverage, claims, *_ = lv.selftest_cases({})[9]
        card = self.write_card(key_dir, "evidence_card.md", None,
                               raw=lv.selftest_card(key_dir.name, src, coverage, claims))
        self.assertEqual(run_main(["card", key_dir, card])[0], 0)
        check = self.last_check(key_dir)
        self.assertIn("OCR_NOT_REDERIVED", statuses(check, "integrity"))        # OCR: hash-checked only
        self.assertEqual(check["verdict"], "PARTIAL")
        self.assertTrue(check["rederive"]["ocr"].startswith("hash-checked only"))

    def test_timeout_argument(self):
        key_dir, src = self.synthetic()
        card = self.card_for(key_dir, src)
        for bad in ("0", "-1", "x", "4000"):
            self.assertEqual(run_main(["card", key_dir, card, "--timeout", bad])[0], 1, bad)
        self.assertEqual(run_main(["card", key_dir, card, "--timeout", "5"])[0], 0)
        self.assertEqual(rows_of(self.papers)[-1]["parameters"]["timeout_s"], 5.0)


# --- 1.8.0 (S3-C1a, review cycle 2): header/footer, page flags, OCR acceptance -----------
@unittest.skipUnless(CAN_RUN_CLI, CLI_WHY)
class RederiveFactsTests(ScratchCase):
    CASES = {c[0]: c for c in lv.selftest_cases({})}

    def check(self, key_dir, src, case, name="evidence_card.md"):
        _, _, coverage, claims, *_ = self.CASES[case]
        card = self.write_card(key_dir, name, None, raw=lv.selftest_card(key_dir.name, src, coverage, claims))
        code, out, err = run_main(["card", key_dir, card])
        art = rows_of(self.papers)[-1]["artifacts"]["card_check"]
        return code, json.loads((key_dir / art["name"]).read_text()), out + err

    def loaded(self, key_dir):
        ing, items = lv.load_ingest(str(key_dir), str(self.papers), key_dir.name, None, lv.parquet_reader())
        return ing, items

    def test_forged_header_footer_record_fails_and_is_not_used(self):
        hf = {"position": "bottom", "pattern": lv.hf_key(lv.SELFTEST_SKIPPED_LINE), "example": "forged", "pages": [1]}
        # the attack shape is real: trusted, the forged record lets the span quote skip a printed line
        pages = [{"anchor": p["anchor"]} for p in lv.SELFTEST_PAGES["A"]]
        n1 = next(c for c in self.CASES["forged header/footer line, span skips it"][3] if c["claim_id"] == "N1")
        result = lv.check_card(mk_card([cov(1, "x")], [n1]), mk_ingest(pages, header_footer=[hf]), fuzz_mod())
        self.assertIn("PASS_SPAN", statuses(result, "claim_quote"))
        key_dir, src = self.synthetic("user_5e1f7e65")
        code, check, log = self.check(key_dir, src, "genuine card")
        self.assertEqual((code, check["rederive"]["header_footer"], check["rederive"]["outcome"]),
                         (0, {"records": 0, "outcome": "match"}, "match"), log)
        lv.forge_manifest_set(str(self.papers), key_dir.name, lambda m: m["header_footer"].append(hf))
        code, check, log = self.check(key_dir, src, "forged header/footer line, span skips it", "evidence_card_a.md")
        self.assertEqual((code, check["verdict"], check["ingest"]["suffix"]), (11, "FAIL", "_a"), log)
        self.assertIn("HEADER_FOOTER_REDERIVE_MISMATCH", statuses(check, "integrity"))
        quote = next(it for it in check["items"] if it["claim_id"] == "N1" and it["kind"] == "claim_quote")
        self.assertNotIn(quote["status"], ("PASS_SPAN", "PASS", "PASS_SKELETON"))
        self.assertEqual((check["rederive"]["header_footer"]["outcome"], check["rederive"]["outcome"]),
                         ("mismatch", "mismatch"))
        self.assertEqual(rows_of(self.papers)[-1]["rederive"]["header_footer"], "mismatch")

    def test_forged_flags_fail_and_the_rederived_flags_are_used(self):
        key_dir, src = self.synthetic("user_5e1f7e66", pages="B")
        code, check, log = self.check(key_dir, src, "claim on an existing OCR text layer page")
        self.assertEqual((code, check["verdict"], check["rederive"]["flags"]["mismatches"]), (0, "PARTIAL", []), log)
        self.assertEqual(check["rederive"]["flags"]["pages_checked"], 3)
        lv.forge_manifest_set(str(self.papers), key_dir.name, lambda m: [r.update(flags=[f for f in r["flags"] if f not in (
            "scanned", "ocr_layer_suspected")]) for r in m["pages"]])
        code, check, log = self.check(key_dir, src, "claim on an existing OCR text layer page", "evidence_card_a.md")
        self.assertEqual((code, check["verdict"]), (11, "FAIL"), log)
        self.assertEqual([it["page"] for it in check["items"] if it["status"] == "FLAGS_REDERIVE_MISMATCH"], [2, 3])
        self.assertIn("PASS_OCR_LAYER", statuses(check, "claim_quote"))          # the re-derived flag is used
        self.assertEqual({p["page"]: p["class"] for p in check["pages"]}[2], "scanned")
        self.assertEqual(check["constants"]["GRADE_FLAGS"], list(lv.GRADE_FLAGS))

    def test_forged_table_and_numeric_flags_cannot_open_the_row_path(self):
        key_dir, src = self.synthetic("user_5e1f7e6a")
        claim = {"claim_id": "Q1", "page": 1, "quote": "The violet ferry carried nineteen patient cartographers across "
                                                       "the silver estuary", "numbers": ["1"], "source": "text"}
        _, _, coverage, _, *_ = self.CASES["genuine card"]
        lv.forge_manifest_set(str(self.papers), key_dir.name, lambda m: m["pages"][0].update(flags=["table", "numeric"]))
        card = self.write_card(key_dir, "evidence_card.md", None, raw=lv.selftest_card(key_dir.name, src, coverage,
                                                                                        [claim]))
        code, _, _ = run_main(["card", key_dir, card])
        check = json.loads((key_dir / rows_of(self.papers)[-1]["artifacts"]["card_check"]["name"]).read_text())
        mm = [it for it in check["items"] if it["status"] == "FLAGS_REDERIVE_MISMATCH"]
        self.assertEqual((code, [it["page"] for it in mm]), (11, [1]))
        self.assertIn("['table', 'numeric']", mm[0]["reason"])
        self.assertEqual(check["rederive"]["flags"]["table_probed"], [1])

    def test_table_probe_scope_and_conservative_fallbacks(self):
        key_dir, src = self.synthetic("user_5e1f7e61", pages="S")
        texts = {1: lv.SYNTHETIC_SOURCES[src]["pages"][1].decode("utf-8")}
        # no numbered claim cites page 1: a caption-less `table` is kept as recorded, not probed
        ing, _ = self.loaded(key_dir)
        items, rec = [], {"ocr_on_text_pages": []}
        lv.rederive_page_facts(ing, texts, {}, {}, lambda n: self.fail("probed"), lambda n: [], set(), items, rec)
        self.assertEqual((items, rec["flags"]["table_not_rederived_uncited"], ing["pages"][1]["flags"]),
                         ([], 1, ["table"]))
        # pdfplumber unavailable on a cited page: the row path closes, with a warning (not a mismatch)
        ing, _ = self.loaded(key_dir)
        items, rec = [], {"ocr_on_text_pages": []}
        lv.rederive_page_facts(ing, texts, {}, {}, lambda n: None, lambda n: None, {1}, items, rec)
        self.assertEqual([it["status"] for it in items], ["FLAGS_NOT_REDERIVED"])
        self.assertEqual((ing["pages"][1]["flags"], rec["flags"]["not_rederived"]), ([], [1]))
        # paper B, pdfimages sees no image and pdfplumber is missing: the OCR-layer flag is kept
        #   (it only caps) and the scanned page stays truly scanned
        key_b, src_b = self.synthetic("user_5e1f7e5b", pages="B")
        ing, _ = self.loaded(key_b)
        texts_b = {n: b.decode("utf-8") for n, b in lv.SYNTHETIC_SOURCES[src_b]["pages"].items()}
        items, rec = [], {"ocr_on_text_pages": []}
        lv.rederive_page_facts(ing, texts_b, {}, {}, lambda n: None, lambda n: None, None, items, rec)
        self.assertEqual([it["status"] for it in items], ["FLAGS_NOT_REDERIVED"])
        self.assertIn("ocr_layer_suspected", ing["pages"][3]["flags"])
        self.assertEqual(lv.classify_page(ing["pages"][2], ing["lanes_unavailable"])[0], "scanned")
        # forged image evidence that turns a truly scanned page into a sparse one
        ing, _ = self.loaded(key_b)
        ing["pages"][2]["evidence"]["figure"] = ["pdfimages: image 100x100 px covers 10% x 10% of the page"]
        items, rec = lv.rederive(ing, 30)
        mm = [it for it in items if it["status"] == "FLAGS_REDERIVE_MISMATCH"]
        self.assertEqual([it["page"] for it in mm], [2])
        self.assertIn("page class sparse -> scanned", mm[0]["reason"])

    def test_forged_ocr_text_on_a_text_page_is_refused(self):
        key_dir, src = self.synthetic("user_5e1f7e67")
        # the attack shape is real: trusted, the forged OCR text passes (PASS_OCR, partial)
        pages = [{"anchor": p["anchor"]} for p in lv.SELFTEST_PAGES["A"]]
        pages[0]["ocr"] = lv.SELFTEST_FABRICATED_OCR + "\n"
        o1 = next(c for c in self.CASES["forged OCR text on a text page"][3] if c["claim_id"] == "O1")
        self.assertIn("PASS_OCR", statuses(lv.check_card(mk_card([cov(1, "x")], [o1]), mk_ingest(pages), fuzz_mod()),
                                           "claim_quote"))
        ob = (lv.SELFTEST_FABRICATED_OCR + "\n").encode("utf-8")
        lv.forge_manifest_set(str(self.papers), key_dir.name, lambda m: m["pages"][0].update(ocr={"text": {
            "path": "ocr_a/p001.txt", "bytes": len(ob), "sha256": lv.sha256_bytes(ob)}}), files={"ocr_a/p001.txt": ob})
        code, check, log = self.check(key_dir, src, "forged OCR text on a text page")
        self.assertEqual((code, check["verdict"]), (11, "FAIL"), log)
        self.assertEqual([it["page"] for it in check["items"] if it["status"] == "OCR_ON_TEXT_PAGE"], [1])
        quote = next(it for it in check["items"] if it["claim_id"] == "O1" and it["kind"] == "claim_quote")
        self.assertEqual(quote["severity"], "fail")
        self.assertEqual((check["rederive"]["ocr_on_text_pages"], check["rederive"]["ocr"]), ([1], None))
        self.assertEqual((check["rederive"]["source_kind"], lv.SEVERITY["OCR_ON_TEXT_PAGE"]), ("synthetic", "fail"))

    def test_vision_on_a_scan_uses_the_rederived_flags(self):
        # 1.8.0 part 5: the page type comes from the source, so neither forged manifest flags nor a card's
        #   `sparse` field hide a scan (except the documented residual: a scan or OCR layer whose only image
        #   evidence is a pdfplumber image box, removed from a forged manifest in a document where pdfimages
        #   lists images; lit_verify header § Re-derivation, Facts), and a source that cannot be read fails
        #   closed (every page a possible scan)
        key_dir, src = self.synthetic("user_5e1f7e6b", pages="B")
        case = self.CASES["listed reader's vision reading on a scan page"]
        coverage = [dict(e, sparse=True) if e["page"] == 2 else e for e in case[2]]
        claims = list(case[3]) + [{"claim_id": "V2", "page": 2, "quote": None, "numbers": ["88"], "source": "vision"}]
        reader = case[9]["reader"]

        def run(name):
            card = self.write_card(key_dir, name, None, raw=lv.selftest_card(key_dir.name, src, coverage, claims, True,
                                                                             reader))
            code, out, err = run_main(["card", key_dir, card])
            art = rows_of(self.papers)[-1]["artifacts"]["card_check"]
            check = json.loads((key_dir / art["name"]).read_text())
            return code, check, sorted((it["page"], it["claim_id"]) for it in check["items"]
                                       if it["status"] == "VISION_ON_SCAN_PAGE"), out + err

        code, check, scan, log = run("evidence_card.md")
        self.assertEqual((code, check["verdict"], check["vision_available"]), (0, "NEEDS_REVIEW", True), log)
        self.assertEqual(scan, [(2, "V2"), (3, "V1")])
        self.assertEqual({p["page"]: (p["class"], p["ocr_layer"]) for p in check["pages"]},
                         {1: ("normal", False), 2: ("scanned", False), 3: ("normal", True)})
        self.assertEqual(check["evidence_grade_if_review_confirmed"], "FULL_TEXT_PARTIAL")
        self.assertEqual(check["rule_versions"]["vision_scope"], "vision-scope-v1")
        lv.forge_manifest_set(str(self.papers), key_dir.name, lambda m: [r.update(flags=[f for f in r["flags"] if f not in (
            "scanned", "ocr_layer_suspected")]) for r in m["pages"]])
        code, check, scan, log = run("evidence_card_a.md")
        self.assertEqual((code, check["verdict"], check["ingest"]["suffix"]), (11, "FAIL", "_a"), log)
        self.assertEqual([it["page"] for it in check["items"] if it["status"] == "FLAGS_REDERIVE_MISMATCH"], [2, 3])
        self.assertEqual(scan, [(2, "V2"), (3, "V1")])                         # the re-derived flags decide
        entry = lv.SYNTHETIC_SOURCES.pop(src)
        try:
            code, check, scan, log = run("evidence_card_b.md")
        finally:
            lv.SYNTHETIC_SOURCES[src] = entry
        self.assertEqual((code, check["rederive"]["outcome"]), (11, "source missing"), log)
        self.assertEqual(scan, [(2, "V2"), (3, "V1")])
        self.assertTrue(all("DAAF could not reopen the original PDF to check this page" in it["reason"]
                            for it in check["items"] if it["status"] == "VISION_ON_SCAN_PAGE"))

    def test_vision_on_a_scan_without_pdfplumber(self):
        # 1.8.0 part 5, FLAGS_NOT_REDERIVED path: pdfplumber missing and pdfimages listing no image, the scanned
        #   page stays truly scanned and the recorded OCR layer is kept, so both readings still go to review
        key_b, src_b = self.synthetic("user_5e1f7e6c", pages="B")
        ing, _ = self.loaded(key_b)
        texts_b = {n: b.decode("utf-8") for n, b in lv.SYNTHETIC_SOURCES[src_b]["pages"].items()}
        items, rec = [], {"ocr_on_text_pages": []}
        lv.rederive_page_facts(ing, texts_b, {}, {}, lambda n: None, lambda n: None, None, items, rec)
        self.assertEqual(([it["status"] for it in items], ing["page_facts_rederived"]), (["FLAGS_NOT_REDERIVED"], [1, 2, 3]))
        claims = [{"claim_id": "V2", "page": 2, "quote": None, "numbers": ["88"], "source": "vision"},
                  {"claim_id": "V3", "page": 3, "quote": None, "numbers": ["23"], "source": "vision"}]
        card = mk_card([cov(1, "x")], claims, key=key_b.name, src=src_b, reader_model="claude-opus-5-5",
                       vision_list_version="vision-list-2026-10-28")
        r = lv.check_card(card, ing, None, items)
        self.assertEqual(sorted((it["page"], it["claim_id"]) for it in r["items"]
                                if it["status"] == "VISION_ON_SCAN_PAGE"), [(2, "V2"), (3, "V3")])
        self.assertIn("This page looks like a scan.", next(it["reason"] for it in r["items"]
                                                            if it["status"] == "VISION_ON_SCAN_PAGE" and it["page"] == 2))

    def test_new_statuses_have_severities(self):
        self.assertEqual({s: lv.SEVERITY[s] for s in ("HEADER_FOOTER_REDERIVE_MISMATCH", "FLAGS_REDERIVE_MISMATCH",
                                                      "OCR_ON_TEXT_PAGE", "FLAGS_NOT_REDERIVED")},
                         {"HEADER_FOOTER_REDERIVE_MISMATCH": "fail", "FLAGS_REDERIVE_MISMATCH": "fail",
                          "OCR_ON_TEXT_PAGE": "fail", "FLAGS_NOT_REDERIVED": "warning"})
        self.assertEqual(lv.GRADE_FLAGS, ("table", "numeric", "scanned", "ocr_layer_suspected"))
        self.assertTrue(set(ptc.ROW_PAGE_FLAGS) <= set(lv.GRADE_FLAGS))


# --- arXiv HTML on disk: real pdf_ingest --source arxiv-html on the synthetic fixture ----
@unittest.skipUnless(CAN_RUN_CLI and HAVE_POLARS, "needs rapidfuzz and polars (pdf_ingest's arXiv HTML lane)")
class HtmlOnDiskTests(ScratchCase):
    KEY = "user_00e2e003"

    def ingest_html(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = pdf_ingest.main([str(HTML_FIX), str(self.papers), "--paper-key", self.KEY, "--source", "arxiv-html",
                                    *extra])
        self.assertEqual(code, 0, err.getvalue())
        return self.papers / self.KEY

    def check(self, key_dir, name="evidence_card.md", *extra):
        card = key_dir / name
        if not card.exists():
            shutil.copy(FIX / "arxiv_html_evidence_card.md", card)
        code, out, err = run_main(["card", key_dir, card, *extra])
        art = (rows_of(self.papers)[-1].get("artifacts") or {}).get("card_check")
        return code, (json.loads((key_dir / art["name"]).read_text()) if art else None), out + err

    def test_example_card_is_partial_with_sections_recorded(self):
        key_dir = self.ingest_html()
        code, check, log = self.check(key_dir)
        self.assertEqual((code, check["verdict"], check["evidence_grade_suggested"]),
                         (0, "PARTIAL", "FULL_TEXT_PARTIAL"), log)
        self.assertEqual(check["failures"] + check["review_items"], [])
        self.assertEqual((check["schema_version"], check["tool_version"], check["anchor_kind"]),
                         ("lit-verify-card-check-v3", lv.TOOL_VERSION, "arxiv_html"))
        ing = check["ingest"]
        self.assertEqual((ing["anchor_kind"], ing["unit_count"], ing["source_version"], ing["arxiv_id_version"],
                          ing["html_extract_version"], ing["source_pdf_sha256"], ing["page_count"]),
                         ("arxiv_html", 12, "v2", "2601.00001v2", "arxiv-html-v1", None, None))
        self.assertEqual((check["card"]["anchor_kind"], check["card"]["source_version"]), ("arxiv_html", "v2"))
        self.assertEqual(check["constants"]["HTML_EXTRACT_VERSIONS_KNOWN"], ["arxiv-html-v1"])
        quotes = {it["claim_id"]: (it["status"], it["section"], it["section_end"]) for it in check["items"]
                  if it["kind"] == "claim_quote"}
        self.assertEqual(quotes, {"X1": ("PASS", "1.2", None), "X2": ("PASS_SPAN", "S1", "S1.SSx1"),
                                  "X3": ("PASS_CONVERSION_ERROR", "2.3.1", None), "X4": ("PASS", "S1", None)})
        self.assertEqual({it["status"] for it in check["items"] if it["kind"] == "claim_number"}, {"NUMBER_OK"})
        cov_status = {it["section"]: it["status"] for it in check["items"] if it["kind"] == "coverage"}
        self.assertEqual((cov_status["2"], cov_status["A"], len(cov_status)), ("COVERED_SPARSE", "PASS", 12))
        self.assertEqual([s["section"] for s in check["sections"]][:4], ["front", "S1", "S1.SSx1", "1.2"])
        self.assertEqual(check["pages"], [])
        row = rows_of(self.papers)[-1]
        self.assertEqual((row["ingest"]["anchor_kind"], row["ingest"]["unit_count"], row["verdict"]),
                         ("arxiv_html", 12, "PARTIAL"))
        self.assertIn("12/12 sections covered (arXiv HTML 2601.00001v2)", log)
        self.assertIn("PASS_CONVERSION_ERROR sec 2.3.1 claim X3", log)

    def test_tampered_rows_and_anchor_fail(self):
        key_dir = self.ingest_html()
        with open(key_dir / "rows" / "u004.txt", "a") as f:
            f.write("South Quay\t0.99\t7\n")                                # a planted row
        code, check, _ = self.check(key_dir)
        self.assertEqual((code, check["verdict"]), (11, "FAIL"))
        it = next(it for it in check["items"] if it["status"] == "TABLE_ROWS_HASH_MISMATCH")
        self.assertEqual((it["section"], it["page"], it["severity"]), ("1.2", None, "fail"))
        self.assertFalse(next(s for s in check["sections"] if s["section"] == "1.2")["table_rows"])
        with open(key_dir / "anchor" / "u011.txt", "a") as f:
            f.write("A line added after ingest.\n")
        code, check, _ = self.check(key_dir)
        self.assertIn(("ANCHOR_HASH_MISMATCH", "1"), [(it["status"], it["section"]) for it in check["items"]])

    def test_rederive_html_match_mismatch_and_edited_source(self):
        src_dir = self.root / "src"
        src_dir.mkdir()
        copy = src_dir / "synthetic_latexml_copy.html"
        shutil.copy(HTML_FIX, copy)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = pdf_ingest.main([str(copy), str(self.papers), "--paper-key", self.KEY, "--source", "arxiv-html"])
        self.assertEqual(code, 0, err.getvalue())
        key_dir = self.papers / self.KEY
        code, check, log = self.check(key_dir)
        rd = check["rederive"]
        self.assertEqual((code, rd["outcome"], rd["anchors_checked"], rd["extractor_version"]),
                         (0, "match", 12, pdf_ingest.HTML_EXTRACT_VERSION), log)
        self.assertGreaterEqual(rd["row_sources_checked"], 1)
        ing, _ = lv.load_ingest(str(key_dir), str(self.papers), self.KEY, None, lv.parquet_reader())
        n = next(n for n, p in ing["pages"].items() if p.get("lane_b_file_sha256"))
        ing["pages"][n]["lane_b_file_sha256"] = "0" * 64
        ing["pages"][1]["anchor_file_sha256"] = "0" * 64
        ing["pages"][2]["flags"] = ["table"]
        items, rec = lv.rederive(ing, 30)
        self.assertEqual(sorted({it["status"] for it in items}), ["ANCHOR_REDERIVE_MISMATCH",
                                                                  "ROW_SOURCE_REDERIVE_MISMATCH"])
        self.assertEqual((rec["anchor_mismatches"], ing["pages"][n]["lane_b_text"]),
                         ([ing["pages"][1]["label"], ing["pages"][2]["label"]], None))
        copy.write_text(copy.read_text() + "<!-- edited after the ingest -->\n")
        code, check, _ = self.check(key_dir, "evidence_card_a.md")
        self.assertEqual((code, check["rederive"]["outcome"]), (11, "source hash mismatch"))
        self.assertIn("SOURCE_FILE_HASH_MISMATCH", statuses(check, "integrity"))

    def test_kind_rules_one_key_one_source(self):
        key_dir = self.ingest_html()
        self.ingest_html("--reingest")                                   # _a, the same source
        man = key_dir / "ingest_manifest.json"
        m = json.loads(man.read_text())
        m["anchor_kind"] = "pdf"
        man.write_text(json.dumps(m))
        code, check, _ = self.check(key_dir)
        self.assertEqual((code, check["ingest"]["suffix"]), (11, "_a"))
        self.assertIn("MIXED_ANCHOR_KINDS", statuses(check, "integrity"))
        m["anchor_kind"] = "epub"
        (key_dir / "ingest_manifest_a.json").write_text(json.dumps(m))
        code, check, log = self.check(key_dir, "evidence_card_a.md")
        self.assertEqual((code, check), (10, None))
        self.assertIn("anchor_kind 'epub'", log)

    def test_incomplete_html_ingest_is_ignored_and_v1_card_mismatches(self):
        key_dir = self.ingest_html()
        (key_dir / "rows_a").mkdir()                                     # an unfinished re-ingest
        code, check, log = self.check(key_dir)
        self.assertEqual(code, 0, log)
        self.assertTrue(any(w.startswith("INCOMPLETE_INGEST_IGNORED") for w in check["warnings"]))
        v1 = mk_card([cov(1, "The violet ferry carried nineteen patient cartographers")], key=self.KEY,
                     src=lv.sha256_bytes(HTML_FIX.read_bytes()))
        card = self.write_card(key_dir, "evidence_card_a.md", v1)
        code, check, _ = self.check(key_dir, card.name)
        self.assertEqual((code, statuses(check)), (11, ["INCOMPLETE_INGEST_IGNORED", "ANCHOR_KIND_MISMATCH"]))


# --- End to end: real pdf_ingest on the committed synthetic fixture PDFs ------------
@unittest.skipUnless(CAN_INGEST, INGEST_WHY)
class EndToEndTests(ScratchCase):
    def ingest(self, name, key, *extra):
        proc = subprocess.run(["bash", str(_SCRIPTS / "pdf_ingest.sh"), str(PDF / f"{name}.pdf"), str(self.papers),
                               "--paper-key", key, "--render", "none", *extra], capture_output=True, text=True,
                              timeout=600)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return self.papers / key

    def check(self, key_dir, fixture, name="evidence_card.md", *extra):
        card = Path(key_dir) / name
        shutil.copy(FIX / fixture, card)
        code, out, err = run_main(["card", key_dir, card, *extra])
        art = rows_of(self.papers)[-1]["artifacts"]["card_check"]
        return code, json.loads((Path(key_dir) / art["name"]).read_text()), out + err

    def test_single_column_genuine_passes_fabricated_fails(self):
        key_dir = self.ingest("single_column", "user_00e2e001")
        code, check, log = self.check(key_dir, "single_column_genuine.md")
        self.assertEqual((code, check["verdict"], check["evidence_grade_suggested"]),
                         (0, "PASS", "FULL_TEXT_VERIFIED"), log)
        code, check, log = self.check(key_dir, "single_column_fabricated.md", "evidence_card_a.md")
        self.assertEqual((code, check["verdict"]), (11, "FAIL"), log)
        self.assertIn("NOT_FOUND", statuses(check, "claim_quote"))
        self.assertIn("NUMBER_MISSING", statuses(check, "claim_number"))
        self.assertTrue((key_dir / "card_check_a.json").exists())
        # a re-ingest becomes the current ingest; pinning reads the first
        self.ingest("single_column", "user_00e2e001", "--reingest")
        code, check, _ = self.check(key_dir, "single_column_genuine.md", "evidence_card_b.md")
        self.assertEqual((code, check["ingest"]["suffix"]), (0, "_a"))
        code, check, _ = self.check(key_dir, "single_column_genuine.md", "evidence_card_c.md", "--ingest-suffix=")
        self.assertEqual((code, check["ingest"]["suffix"]), (0, ""))

    def test_rederive_real_pdf_match_forgery_timeout_and_missing_poppler(self):
        key_dir = self.ingest("single_column", "user_00e2e001")
        code, check, log = self.check(key_dir, "single_column_genuine.md")
        rd = check["rederive"]
        self.assertEqual((code, rd["outcome"], rd["anchors_checked"]), (0, "match", check["counts"]["pages"]), log)
        self.assertTrue(rd["method"].startswith("pdftotext per page"))
        self.assertEqual(rd["extractor_version"], rd["extractor_version_ingest"])
        code, check, _ = self.check(key_dir, "single_column_genuine.md", "evidence_card_a.md", "--timeout", "0.000001")
        self.assertEqual(code, 11)
        self.assertIn("SOURCE_REDERIVE_ERROR", statuses(check, "integrity"))
        with mock.patch.object(lv.shutil, "which", return_value=None):
            code, _, _ = run_main(["card", key_dir, key_dir / "evidence_card.md"])
        self.assertEqual(code, 10)
        self.assertIn("pdftotext", rows_of(self.papers)[-1]["note"])
        lv.forge_ingest_set(str(self.papers), key_dir.name, "An invented sentence this source never printed on "
                                                            "its first page.", lv.parquet_reader(), lv.parquet_writer())
        code, check, _ = self.check(key_dir, "single_column_genuine.md", "evidence_card_b.md")
        self.assertEqual((code, check["ingest"]["suffix"]), (11, "_a"))
        self.assertIn(("ANCHOR_REDERIVE_MISMATCH", 1), [(it["status"], it["page"]) for it in check["items"]])

    def test_sealed_source_defeats_a_swap_after_hashing(self):
        # 1.8.0 (review W-b): the source is read once and re-derived from those
        #   bytes; a file swapped in at the path after the hash changes nothing.
        src_dir = self.root / "src"
        src_dir.mkdir()
        src = src_dir / "single_column_copy.pdf"
        shutil.copy(PDF / "single_column.pdf", src)
        proc = subprocess.run(["bash", str(_SCRIPTS / "pdf_ingest.sh"), str(src), str(self.papers), "--paper-key",
                               "user_00e2e001", "--render", "none"], capture_output=True, text=True, timeout=600)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        key_dir = self.papers / "user_00e2e001"
        real_run_tool, state = lv.pdi.run_tool, {"swapped": False}

        def swapping_run_tool(*a, **kw):
            if not state["swapped"]:
                state["swapped"] = True
                shutil.copy(PDF / "multipage.pdf", src)                  # another PDF at the path
            return real_run_tool(*a, **kw)

        with mock.patch.object(lv.pdi, "run_tool", side_effect=swapping_run_tool):
            code, check, log = self.check(key_dir, "single_column_genuine.md")
        rd = check["rederive"]
        self.assertTrue(state["swapped"])
        self.assertEqual((code, check["verdict"], rd["outcome"]), (0, "PASS", "match"), log)
        self.assertTrue(rd["read"].startswith("once"))
        self.assertEqual((rd["source_kind"], rd["source_kind_ingest"], rd["web_fetch_row"]),
                         ("user_supplied", "user_supplied", None))
        code, check, _ = self.check(key_dir, "single_column_genuine.md", "evidence_card_a.md")   # the swap is real
        self.assertEqual((code, check["rederive"]["outcome"]), (11, "source hash mismatch"))
        shutil.copy(PDF / "single_column.pdf", src)
        with mock.patch.object(lv, "sealed_copy", side_effect=AttributeError("memfd_create")):
            code, check, _ = self.check(key_dir, "single_column_genuine.md", "evidence_card_b.md")
        self.assertEqual((code, check["rederive"]["outcome"]), (11, "error"))
        self.assertIn("memfd_create", next(it["reason"] for it in check["items"]
                                           if it["status"] == "SOURCE_REDERIVE_ERROR"))
        real_which = shutil.which
        with mock.patch.object(lv.shutil, "which", side_effect=lambda b: None if b == "pdfimages" else real_which(b)):
            code, _, _ = run_main(["card", key_dir, key_dir / "evidence_card.md"])
        self.assertEqual(code, 10)
        self.assertIn("pdfimages", rows_of(self.papers)[-1]["note"])

    def test_real_pdf_forged_header_footer_and_flags_fail(self):
        key_dir = self.ingest("multipage", "user_00e2e002")
        code, check, log = self.check(key_dir, "example_evidence_card.md")
        rd = check["rederive"]
        self.assertEqual((code, check["verdict"], rd["outcome"], rd["flags"]["mismatches"]),
                         (0, "PARTIAL", "match", []), log)
        self.assertEqual((rd["header_footer"]["outcome"], rd["flags"]["pages_checked"]), ("match", 5))
        man = json.loads((key_dir / "ingest_manifest.json").read_text())
        self.assertIn("scanned", man["pages"][4]["flags"])

        def forge(m):
            m["header_footer"].append({"position": "bottom", "pattern": "forged running footer", "example": "forged",
                                       "pages": [1, 2, 3]})
            m["pages"][4]["flags"] = [f for f in m["pages"][4]["flags"] if f != "scanned"]

        lv.forge_manifest_set(str(self.papers), key_dir.name, forge)
        code, check, _ = self.check(key_dir, "example_evidence_card.md", "evidence_card_a.md")
        self.assertEqual(code, 11)
        st = [(it["status"], it["page"]) for it in check["items"] if it["kind"] == "integrity"]
        self.assertIn(("HEADER_FOOTER_REDERIVE_MISMATCH", None), st)
        self.assertIn(("FLAGS_REDERIVE_MISMATCH", 5), st)
        self.assertEqual({p["page"]: p["class"] for p in check["pages"]}[5], "scanned")   # re-derived flags used

    def test_multipage_example_card_is_partial(self):
        key_dir = self.ingest("multipage", "user_00e2e002")
        code, check, log = self.check(key_dir, "example_evidence_card.md")
        self.assertEqual((code, check["verdict"], check["evidence_grade_suggested"]),
                         (0, "PARTIAL", "FULL_TEXT_PARTIAL"), log)
        classes = {p["page"]: p["class"] for p in check["pages"]}
        self.assertEqual(classes, {1: "normal", 2: "normal", 3: "normal", 4: "sparse", 5: "scanned"})
        cov_status = {it["page"]: it["status"] for it in check["items"] if it["kind"] == "coverage"}
        self.assertEqual(cov_status, {1: "PASS", 2: "PASS", 3: "PASS", 4: "PASS", 5: "PASS_OCR"})
        self.assertIn("PASS_SKELETON", statuses(check, "coverage_anchor"))
        nums = {(it["claim_id"], it["number"]): it["status"] for it in check["items"] if it["kind"] == "claim_number"}
        self.assertEqual(nums[("M1", "-3")], "NUMBER_OK")                  # page prints U+2212
        self.assertEqual(nums[("M1", "(2.1)")], "NUMBER_OK")
        self.assertEqual(nums[("M2", "58")], "NUMBER_OCR_ONLY")
        self.assertEqual(check["failures"], [])
        self.assertEqual([s.split(" ")[0] for s in check["partial_items"]].count("SCANNED_PAGE"), 1)


# --- Card schema v3 (1.9.0, S4 D3): typed claims, quant fields, page labels; every word invented ---
def mk_v3(coverage, claims=(), **over):
    card = {"schema_version": "lit-verify-card-v3", "paper_key": "user_00000001", "anchor_kind": "pdf",
            "source_sha256": "a" * 64, "reader_model": "test", "vision_mode": "auto", "vision_validated": False,
            "vision_list_version": None, "coverage": list(coverage), "claims": list(claims)}
    card.update(over)
    return card


class CardV3Tests(unittest.TestCase):
    CI_PAGE = "The invented tutoring estimate was 0.30 (95% CI 0.10 to 0.50) across 412 invented pupils in the trial.\n\f"
    QUOTE = "The invented tutoring estimate was 0.30 (95% CI 0.10 to 0.50) across 412 invented pupils"
    NUMS = ["0.30", "0.10", "0.50", "412"]

    def run_quant(self, quant, numbers=None, quote=None):
        ing = mk_ingest([{"anchor": self.CI_PAGE}])
        claim = {"claim_id": "C1", "page": 1, "quote": quote or self.QUOTE, "numbers": numbers or self.NUMS,
                 "source": "text", "claim_type": "finding", "quant": quant}
        return lv.check_card(mk_v3([cov(1, self.QUOTE)], [claim]), ing, None)

    def quant(self, result):
        return {it["quant_field"]: it["status"] for it in result["items"] if it["kind"] == "claim_quant"}

    def test_quant_fields_on_checked_numbers(self):
        r = self.run_quant({"estimate": "0.30", "ci_low": "0.10", "ci_high": "0.50", "n": "412", "ci_level": "95",
                            "metric": "SD units"})
        self.assertEqual(self.quant(r), {"estimate": "QUANT_OK", "ci_low": "QUANT_OK", "ci_high": "QUANT_OK",
                                         "n": "QUANT_OK"})
        self.assertEqual((r["verdict"], r["counts"]["quant_fields"], r["counts"]["claims_by_type"]),
                         ("PASS", 4, {"finding": 1}))
        ok = next(it for it in r["items"] if it["kind"] == "claim_quant")
        self.assertEqual(ok["matched_number"], "0.30")
        self.assertIn("inside the quote on PDF page 1", ok["reason"])
        self.assertNotIn("QUANT_", ok["reason"])                                    # plain language, no status codes

    def test_quant_value_not_in_numbers_fails(self):
        r = self.run_quant({"estimate": "0.3"})                                     # other digits: not the same number
        self.assertEqual((self.quant(r), r["verdict"]), ({"estimate": "QUANT_NOT_IN_NUMBERS"}, "FAIL"))
        r = self.run_quant({"estimate": "about 0.30"})
        self.assertEqual(self.quant(r), {"estimate": "QUANT_NOT_IN_NUMBERS"})

    def test_quant_inherits_the_number_outcome(self):
        r = self.run_quant({"estimate": "0.31"}, numbers=["0.31"])                  # a number not on the page
        self.assertEqual((self.quant(r), r["verdict"]), ({"estimate": "QUANT_NUMBER_FAILED"}, "FAIL"))
        r = self.run_quant({"n": "412"}, numbers=["412"], quote="The invented tutoring estimate was 0.30 (95% CI "
                                                                "0.10 to 0.50) across")
        self.assertEqual((self.quant(r), r["verdict"]), ({"n": "QUANT_NUMBER_REVIEW"}, "NEEDS_REVIEW"))

    def test_parentheses_must_agree_except_for_se(self):
        ing = mk_ingest([{"anchor": PROSE[3] + "\n\f"}])
        q = "Table 2 reports −0.087* (0.044) and 1,204 boats with .05 as the threshold"
        base = {"claim_id": "C1", "page": 1, "quote": q, "numbers": ["-0.087", "(0.044)", "1,204"], "source": "text",
                "claim_type": "finding"}
        r = lv.check_card(mk_v3([cov(1, q)], [dict(base, quant={"se": "0.044", "estimate": "(0.044)"})]), ing, None)
        self.assertEqual(self.quant(r), {"se": "QUANT_OK", "estimate": "QUANT_OK"})
        r = lv.check_card(mk_v3([cov(1, q)], [dict(base, quant={"estimate": "0.044"})]), ing, None)
        self.assertEqual(self.quant(r), {"estimate": "QUANT_NOT_IN_NUMBERS"})

    def test_n_must_be_a_whole_count(self):
        self.assertEqual(self.quant(self.run_quant({"n": "0.30"})), {"n": "QUANT_N_NOT_INTEGER"})

    def test_interval_order_and_estimate_outside(self):
        r = self.run_quant({"estimate": "0.30", "ci_low": "0.50", "ci_high": "0.10"})
        self.assertEqual((self.quant(r)["ci"], r["verdict"]), ("QUANT_CI_ORDER", "NEEDS_REVIEW"))
        r = self.run_quant({"estimate": "412", "ci_low": "0.10", "ci_high": "0.50"})
        self.assertEqual(self.quant(r)["ci"], "QUANT_ESTIMATE_OUTSIDE_CI")

    def test_page_label_in_header_or_footer(self):
        body = ("Synthetic folio page. The invented lamplighter counted every copper lamp on the long street.\n"
                "He wrote the totals in a green notebook kept in a drawer at the invented lamp office.\n"
                "Nobody else read the notebook, and Table 7 lists its totals by street and by year.\n"
                "Each evening he walked the same route and checked that every lamp was burning.\n"
                "The route passed the harbour, the market and the long row of painted houses.\n"
                "On windy nights he walked it twice, because the copper lamps went out more often.\n")
        q = "Each evening he walked the same route and checked that every lamp was burning"
        for page, label, want in ((body + "12\n\f", "12", "PAGE_LABEL_OK"), ("12\n" + body + "\f", "12", "PAGE_LABEL_OK"),
                                  (body + "12\n\f", "13", "PAGE_LABEL_UNCONFIRMED"),
                                  (body + "\f", "7", "PAGE_LABEL_UNCONFIRMED"),            # "Table 7" is body text
                                  (body + "– xii –\n\f", "XII", "PAGE_LABEL_OK")):
            claim = {"claim_id": "L1", "page": 1, "quote": q, "numbers": [], "source": "text", "claim_type": "method",
                     "page_label": label}
            r = lv.check_card(mk_v3([cov(1, q)], [claim]), mk_ingest([{"anchor": page}]), None)
            self.assertEqual(statuses(r, "page_label"), [want], (label, page[-12:]))
            self.assertEqual(r["verdict"], "PASS")                              # a warning never fails a card

    def test_v1_and_v2_cards_carry_no_typed_fields(self):
        r = lv.check_card(mk_card([cov(1, PROSE[1])], src="a" * 64), mk_ingest([{"anchor": PROSE[1] + "\n\f"}]), None)
        self.assertEqual((r["counts"]["claims_by_type"], r["counts"]["quant_fields"]), ({}, 0))


class CardV3StructureTests(unittest.TestCase):
    CLAIM = {"claim_id": "C1", "page": 1, "quote": "q", "numbers": [], "source": "text", "claim_type": "finding"}

    def assert_exit8(self, card, fragment):
        with self.assertRaises(lv.LitVerifyError) as cm:
            lv.validate_card(card)
        self.assertEqual(cm.exception.code, 8)
        self.assertIn(fragment, cm.exception.note)

    def test_valid_v3_card(self):
        lim = dict(self.CLAIM, claim_id="C2", claim_type="limitation", limitation_kind="author_stated")
        apr = dict(self.CLAIM, claim_id="C3", claim_type="appraisal",
                   appraisal={"guide": "rob2", "item": "1.2", "answer": "PY"})
        use = dict(self.CLAIM, claim_id="C4", claim_type="citation_use",
                   citation_use={"cites_key": "W2741809807", "relation": "uses_method"})
        ext = dict(use, claim_id="C5", citation_use={"cites_key": "external:10.1257/aer.104.9.2593",
                                                     "relation": "background"})
        note = {"design": "did", "study_weight": "moderate", "weight_reason": "Self-selection [C2].",
                "limitation_claim_ids": ["C2"], "directness": {"population": "direct", "time": "partly"}}
        lv.validate_card(mk_v3([], [dict(self.CLAIM, quant={"estimate": "0.1", "metric": "SD"}, page_label="iv"),
                                    lim, apr, use, ext], paper_note=note))

    def test_structure_errors_exit_8(self):
        c = self.CLAIM
        self.assert_exit8(mk_v3([], [dict(c, claim_type="opinion")]), "claim_type must be one of")
        self.assert_exit8(mk_v3([], [{k: v for k, v in c.items() if k != "claim_type"}]), "missing field")
        self.assert_exit8(mk_v3([], [dict(c, appraisal={"guide": "rob2", "item": "1", "answer": "Y"})]),
                          "appraisal is required with claim_type 'appraisal' and allowed only there")
        self.assert_exit8(mk_v3([], [dict(c, claim_type="limitation")]), "limitation_kind is required")
        self.assert_exit8(mk_v3([], [dict(c, claim_type="appraisal", appraisal={"guide": "rob3", "item": "1",
                                                                                 "answer": "Y"})]), "guide must be")
        self.assert_exit8(mk_v3([], [dict(c, claim_type="appraisal", appraisal={"guide": "rob2", "item": "x" * 41,
                                                                                 "answer": "Y"})]), "at most 40")
        self.assert_exit8(mk_v3([], [dict(c, claim_type="citation_use",
                                          citation_use={"cites_key": "smith2020", "relation": "uses_method"})]),
                          "cites_key must be")
        self.assert_exit8(mk_v3([], [dict(c, quant={"pooled": "0.1"})]), "unknown field")
        self.assert_exit8(mk_v3([], [dict(c, quant={"estimate": 0.1})]), "quant.estimate must be")
        self.assert_exit8(mk_v3([], [dict(c, page_label="p 7")]), "page_label must be")
        html = mk_v3([], [{"claim_id": "C1", "section": "1", "quote": "q", "numbers": [], "source": "text",
                           "claim_type": "finding", "page_label": "7"}], anchor_kind="arxiv_html", source_version="v1",
                     vision_mode="off")
        self.assert_exit8(html, "page_label applies to PDF cards only")
        self.assert_exit8(mk_v3([], [c], paper_note={"design": "rct", "study_weight": "moderate",
                                                     "weight_reason": "r", "limitation_claim_ids": ["C1"]}),
                          "is a 'finding' claim")
        self.assert_exit8(mk_v3([], [c], paper_note={"design": "rct", "study_weight": "moderate",
                                                     "limitation_claim_ids": []}), "weight_reason")
        self.assert_exit8(mk_v3([], [c], paper_note={"design": "rct", "study_weight": "high", "weight_reason": "r",
                                                     "limitation_claim_ids": []}), "study_weight must be")
        v2 = dict(mk_v3([], [c]), schema_version="lit-verify-card-v2")
        self.assert_exit8(v2, "unknown field")                                    # v2 cards keep the v2 claim fields

    def test_vocabularies_match_the_literature_review_skill(self):
        refs = _REPO_ROOT / ".claude" / "skills" / "literature-review" / "references"
        formal = (refs / "formal-review.md").read_text()
        guides = formal.split("`guide` is one of", 1)[1].split(";", 1)[0]
        self.assertEqual(tuple(re.findall(r"`([a-z0-9-]+)`", guides)), lv.APPRAISAL_GUIDES)
        notes = (refs / "paper-notes.md").read_text()
        labels = notes.split("## Design labels", 1)[1].split("Label the design", 1)[0]
        self.assertEqual(tuple(re.findall(r"`([a-z_]+)`", labels)), lv.DESIGN_LABELS)


# --- report (1.10.0, S4 D4): the pure rules on an in-memory view; every word invented ---------------
import lit_report_rules as lrr  # noqa: E402  (stdlib)

HAVE_YAML = importlib.util.find_spec("yaml") is not None
BUNDLE = Path(__file__).resolve().parent / "fixtures" / "lit_corpus" / "contract_bundle"


def mk_view():
    def paper(key, grade="FULL_TEXT_VERIFIED", verdict="CONFIDENT", rs="none", **kw):
        return dict({"paper_key": key, "grade": grade, "verify_verdict": verdict, "verify_note": None,
                     "accept_weak": False, "retraction_status": rs, "include_retracted": False, "in_bib": True}, **kw)

    def claim(key, verification="verified", numbers=(), quote="q", status="current"):
        return {"paper_key": key, "citekey": None, "status": status, "superseded_by": None,
                "verification": verification, "quote": quote, "numbers": list(numbers)}

    def finding(cert, claims, scheme="stated", **kw):
        return dict({"status": "current", "certainty_scheme": scheme, "certainty": cert,
                     "certainty_reason": "rests on pa-c01", "decided_by": {"role": "synthesizer"},
                     "not_rated_reason": None, "moderator_status": "none", "claim_ids": claims, "dsum": None,
                     "dirs": None}, **kw)
    three = ["pa-c01", "pb-c01", "pc-c01"]
    return {
        "papers": {"a": paper("pa"), "b": paper("pb"), "c": paper("pc"), "f": paper("pf", "ABSTRACT_ONLY"),
                   "f2": paper("pf2", "ABSTRACT_ONLY"),
                   "m": paper("pm", "METADATA_ONLY"), "r": paper("pr", rs="retracted"),
                   "rd": paper("prd", rs="retracted", include_retracted=True), "co": paper("pco", rs="corrected"),
                   "nr": paper("pnr", rs=None), "w": paper("pw", verdict="WEAK"),
                   "wa": paper("pwa", verdict="WEAK", accept_weak=True), "u": paper("pu", verdict=None),
                   "x": paper("px", in_bib=False), "rn": paper("prn", retraction_not_latest=True),
                   # polish pass H: a second paper printing 0.15 (as b does); the final title rule's fix on an
                   #   unverified paper; a draft whose recorded title differs from the confirmed record's
                   "d": paper("pd"), "tu": paper("ptu", verdict=None, verify_fix="Restore the data folder (test fix)."),
                   "td": paper("ptd", verify_fix="Restore the data folder (test fix).",
                               title_differs={"recorded": "A Mentoring Pilot", "record": "A Study of Dental Hygiene"})},
        "claims": {"pa-c01": claim("pa", numbers=["0.21", "0.05"], quote="Reading scores rose by 0.21 standard "
                                                                            "deviations after one invented year"),
                   "pb-c01": claim("pb", numbers=["0.15"]), "pc-c01": claim("pc", numbers=["0.09"]),
                   "pd-c01": claim("pd", numbers=["0.15"]),
                   "pa-c02": claim("pa", status="superseded"), "pa-c03": claim("pa", verification="wrong_page"),
                   "pa-c04": dict(claim("pa"), numbers_failed=True),
                   # report-rules-v3 fixtures: a labelled number needing review (C2-QW5), an abstract claim of a fully
                   #   read paper (q-I4), quotes of an unverified and a verified claim (C2-CW1)
                   "pa-c05": dict(claim("pa"), numbers_review=True),
                   "pa-a01": claim("pa", verification="abstract_verified", quote="Reading buddies help young readers"),
                   "pa-c06": claim("pa", verification="unverified", quote="this program proves that tutoring works "
                                                                           "for every pupil in every school"),
                   "pb-c02": claim("pb", quote="this program proves that tutoring works for every pupil")},
        "findings": {"F01": finding("moderate", three, dsum={"k": 3, "median": "0.15", "q1": "0.12", "q3": "0.18",
                                                              "min": "0.09", "max": "0.21"},
                                    dirs={"u": 3, "n": 3, "p_two_sided": 0.25, "ci95": [0.438503, 1.0]}),
                     "F02": finding(None, ["pa-c01"], scheme="not_rated", not_rated_reason="qualitative_evidence",
                                    certainty_reason=None),
                     "F03": finding("low", ["pa-c01", "pb-c01"]), "F04": finding("very_low", ["pa-c01"]),
                     "F05": finding("moderate", ["pa-c01"], moderator_status="post_hoc"),
                     "F06": finding("moderate", ["pa-c01"], certainty_reason=""),
                     "F07": finding("high", ["pa-c01", "pb-c01"]),
                     "F08": finding("moderate", ["pa-c01"], status="superseded"),
                     "F09": finding("low", three)},
        "edges": {"E001": {"citing_key": "pb", "cited_key": "pa", "reader_relation": "builds_on"},
                  "E002": {"citing_key": "pb", "cited_key": "pa", "reader_relation": "disputes"}},
    }


def fspan(fid, claims="pa-c01"):
    return '{.lr-finding fid=%s claims="%s"}' % (fid, claims)


class ReportRulesTests(unittest.TestCase):
    # (name, text, kind, verdict, statuses that must appear, statuses that must not)
    CASES = [
        ("clean finding", "[Tutoring probably raises scores]" + fspan("F01", "pa-c01 pb-c01") + " [@a; @b].",
         "synthesis", "PASS", ("CITATION_OK",), ()),
        ("email is not a citation", "Write to me@example.org about the trial [@a].", "synthesis", "PASS", (),
         ("CITEKEY_UNKNOWN",)),
        ("unknown key", "Tutoring helps [@zz2020nope].", "synthesis", "FAIL", ("CITEKEY_UNKNOWN",), ()),
        ("bare in-text key resolves", "As @a reports, scores rose by 0.21.", "synthesis", "PASS", ("CITATION_OK",), ()),
        ("not in the reference list", "Tutoring helps [@x].", "synthesis", "FAIL", ("CITEKEY_NOT_IN_BIB",), ()),
        ("unverified", "Tutoring helps [@u].", "synthesis", "FAIL", ("CITATION_UNVERIFIED",), ()),
        ("weak, undecided", "Tutoring helps [@w].", "synthesis", "FAIL", ("CITATION_WEAK_UNDECIDED",), ()),
        ("weak, accepted by the researcher", "Tutoring helps [@wa].", "synthesis", "NEEDS_REVIEW",
         ("CITATION_HUMAN_DECISION_UNBOUND",), ()),
        ("retracted", "Tutoring helps [@r].", "synthesis", "FAIL", ("RETRACTED_CITED",), ()),
        ("retracted, kept, unlabelled", "Tutoring helps [@rd].", "synthesis", "FAIL", ("RETRACTED_UNLABELED",), ()),
        ("retracted, kept, labelled", "A later retracted trial reported gains [@rd].", "synthesis", "PASS",
         ("RETRACTED_CITED_DECIDED",), ()),
        ("corrected", "Tutoring helps [@co].", "synthesis", "PASS", ("CORRECTED_CITED",), ()),
        ("retraction not checked", "Tutoring helps [@nr].", "synthesis", "NEEDS_REVIEW", ("RETRACTION_NOT_CHECKED",),
         ()),
        ("metadata only", "Tutoring helps [@m].", "synthesis", "FAIL", ("METADATA_ONLY_CITED",), ()),
        ("metadata only in a bibliography", "Further reading [@m].", "bibliography", "PASS", (),
         ("METADATA_ONLY_CITED",)),
        ("abstract only, unlabelled", "Buddies help readers [@f].", "synthesis", "FAIL", ("ABSTRACT_ONLY_UNLABELED",),
         ()),
        ("abstract only, labelled", "Buddies may help readers [@f, per abstract].", "synthesis", "PASS", (), ()),
        ("abstract only, labelled, two keys (quick scan)", "Buddies may help readers [@f, per abstract; "
         "@f2, per abstract].", "synthesis", "PASS", (), ("FINDING_UNMARKED",)),
        ("label on a full-text paper", "Scores rose [@a, per abstract].", "synthesis", "PASS",
         ("PER_ABSTRACT_ON_FULL_TEXT",), ()),
        ("abstract only with a number", "Buddies raised scores by 0.4 SD [@f, per abstract].", "synthesis", "FAIL",
         ("ABSTRACT_ONLY_NUMBER",), ()),
        ("finding unknown", "[It works]" + fspan("F99") + " [@a].", "synthesis", "FAIL", ("FINDING_UNKNOWN",), ()),
        ("finding superseded", "[It probably works]" + fspan("F08") + " [@a].", "synthesis", "FAIL",
         ("FINDING_UNKNOWN",), ()),
        ("finding without a reason", "[It probably works]" + fspan("F06") + " [@a].", "synthesis", "FAIL",
         ("FINDING_UNREASONED",), ()),
        ("claim unknown", '[It works]{.lr-claim claims="pa-c99"} [@a].', "synthesis", "FAIL", ("CLAIM_UNKNOWN",), ()),
        ("claim superseded", '[It works]{.lr-claim claims="pa-c02"} [@a].', "synthesis", "FAIL",
         ("CLAIM_SUPERSEDED",), ()),
        ("claim not on its page", '[It works]{.lr-claim claims="pa-c03"} [@a].', "synthesis", "FAIL",
         ("CLAIM_NOT_VERIFIED",), ()),
        ("claim of another paper", "[Tutoring probably raises scores]" + fspan("F01", "pc-c01") + " [@a].",
         "synthesis", "FAIL", ("CLAIM_PAPER_NOT_CITED",), ()),
        ("span claims not the finding's", "[Tutoring probably raises scores]" + fspan("F05", "pb-c01")
         + " [@b], which was exploratory.", "synthesis", "NEEDS_REVIEW", ("FINDING_CLAIMS_DIFFER",), ()),
        ("malformed marker", "[It works]{.lr-finding claims=\"pa-c01\"} [@a].", "synthesis", "FAIL",
         ("SPAN_MALFORMED",), ()),
        ("significance vote count", "Seven of ten studies found significant effects [@a; @b].", "synthesis", "FAIL",
         ("VOTE_COUNT_SIGNIFICANCE",), ()),
        ("informal vote count", "Most studies found improvements [@a; @b].", "synthesis", "NEEDS_REVIEW",
         ("VOTE_COUNT_INFORMAL",), ()),
        ("count of designs is fine", "12 of 40 studies used randomized designs [@a; @b].", "synthesis", "PASS", (),
         ("VOTE_COUNT_INFORMAL", "FINDING_UNMARKED")),
        ("count of effects by risk of bias is fine", "Only five of the 15 effects were judged at low risk of bias "
         "[@a; @b].", "synthesis", "PASS", (), ("VOTE_COUNT_INFORMAL",)),
        ("'the most rigorous studies' is not a count", "The most rigorous studies used state tests [@a].",
         "synthesis", "PASS", (), ("VOTE_COUNT_INFORMAL",)),
        ("sign test equal to the computed one", "[Three of three effects favoured tutoring (sign test, p = 0.25)]"
         + fspan("F01", "pa-c01 pb-c01 pc-c01") + " [@a; @b; @c].", "synthesis", "PASS", ("DIRECTION_SIGN_TEST",), ()),
        ("sign test numbers differ", "[Two of three effects favoured tutoring (sign test)]"
         + fspan("F01", "pa-c01 pb-c01 pc-c01") + " [@a; @b; @c].", "synthesis", "FAIL", ("SIGN_TEST_MISMATCH",), ()),
        ("pooled estimate", "The pooled effect was 0.15 [@a; @b].", "synthesis", "FAIL", ("POOLED_ESTIMATE",), ()),
        ("a study's own average is fine", "The trial's average effect was 0.21 [@a].", "synthesis", "PASS", (),
         ("POOLED_ESTIMATE",)),
        ("weighted summary", "The weighted average of the studies was 0.15 [@a; @b].", "synthesis", "FAIL",
         ("WEIGHTED_SUMMARY",), ()),
        ("descriptive summary as computed", "[Across 3 studies the estimates ranged from 0.09 to 0.21 (median 0.15; "
         "IQR 0.12 to 0.18; descriptive summary, not a pooled estimate)]" + fspan("F01", "pa-c01 pb-c01 pc-c01")
         + " [@a; @b; @c].", "synthesis", "PASS", ("DESCRIPTIVE_SUMMARY_OK",), ("POOLED_ESTIMATE",)),
        ("descriptive summary unlabelled", "[Across 3 studies the estimates ranged from 0.09 to 0.21 (median 0.15)]"
         + fspan("F01", "pa-c01 pb-c01 pc-c01") + " [@a; @b; @c].", "synthesis", "FAIL",
         ("DESCRIPTIVE_SUMMARY_UNLABELED",), ()),
        ("descriptive summary with other numbers", "[Across 3 studies the median was 0.16 (range 0.09 to 0.21; "
         "descriptive summary, not a pooled estimate)]" + fspan("F01", "pa-c01 pb-c01 pc-c01") + " [@a; @b; @c].",
         "synthesis", "FAIL", ("DESCRIPTIVE_SUMMARY_NUMBER_MISMATCH",), ()),
        ("median without a computed summary", "Across the studies the median effect size was 0.15 (range 0.09 to "
         "0.21) [@a; @b; @c].", "synthesis", "FAIL", ("DESCRIPTIVE_SUMMARY_UNSUPPORTED",), ()),
        ("number in no cited claim, one paper", "The trial raised scores by 0.33 [@a].", "synthesis", "NEEDS_REVIEW",
         ("NUMBER_NOT_IN_CITED_CLAIM",), ()),
        ("number in no cited claim, two papers", "[Tutoring probably raises scores by 0.18]"
         + fspan("F01", "pa-c01 pb-c01") + " [@a; @b].", "synthesis", "FAIL", ("NUMBER_ACROSS_PAPERS",), ()),
        ("number of a cited claim", "The trial raised scores by 0.21 [@a].", "synthesis", "PASS", (),
         ("NUMBER_NOT_IN_CITED_CLAIM",)),
        ("certainty stronger", "[Tutoring raises scores]" + fspan("F01", "pa-c01 pb-c01") + " [@a; @b].",
         "synthesis", "FAIL", ("CERTAINTY_STRONGER",), ()),
        ("certainty weaker", "[Tutoring may raise scores]" + fspan("F01", "pa-c01 pb-c01") + " [@a; @b].",
         "synthesis", "NEEDS_REVIEW", ("CERTAINTY_WEAKER",), ()),
        ("stacked hedges", "[Tutoring may probably raise scores]" + fspan("F01", "pa-c01 pb-c01") + " [@a; @b].",
         "synthesis", "NEEDS_REVIEW", ("CERTAINTY_STACKED_HEDGE",), ()),
        ("'likely' on a moderate finding", "[Tutoring likely raises scores]" + fspan("F01", "pa-c01 pb-c01")
         + " [@a; @b].", "synthesis", "NEEDS_REVIEW", ("FORBIDDEN_HEDGE",), ()),
        ("'likely' on a low finding is stronger", "[Tutoring likely raises scores]" + fspan("F03", "pa-c01 pb-c01")
         + " [@a; @b].", "synthesis", "FAIL", ("CERTAINTY_STRONGER",), ()),
        ("'more likely to' is not a hedge", "[Tutored pupils are probably more likely to read]"
         + fspan("F01", "pa-c01 pb-c01") + " [@a; @b].", "synthesis", "PASS", (), ("FORBIDDEN_HEDGE",)),
        ("'May 2020' is a month", "[Since May 2020 tutoring raises scores]" + fspan("F07", "pa-c01 pb-c01")
         + " [@a; @b].", "synthesis", "PASS", (), ("CERTAINTY_WEAKER",)),
        ("booster", "[Tutoring probably raises scores and the trial proves it]" + fspan("F01", "pa-c01 pb-c01")
         + " [@a; @b].", "synthesis", "FAIL", ("BOOSTER",), ()),
        ("no effect", "[Tutoring probably has no effect on attendance]" + fspan("F01", "pa-c01 pb-c01")
         + " [@a; @b].", "synthesis", "FAIL", ("NO_EFFECT_CLAIM",), ()),
        ("very low without 'uncertain'", "[Tutoring may raise scores]" + fspan("F04") + " [@a].", "synthesis",
         "FAIL", ("VERY_LOW_WITHOUT_UNCERTAIN",), ()),
        ("very low direction template", "[Tutoring may raise scores, but the evidence is very uncertain]"
         + fspan("F04") + " [@a].", "synthesis", "PASS", (), ("CERTAINTY_STACKED_HEDGE",)),
        ("not rated, unstated", "[Teachers describe scheduling as a barrier]" + fspan("F02") + " [@a].",
         "synthesis", "NEEDS_REVIEW", ("NOT_RATED_UNSTATED",), ()),
        ("not rated with a hedge", "[Teachers probably see scheduling as a barrier (certainty not rated: qualitative "
         "evidence)]" + fspan("F02") + " [@a].", "synthesis", "FAIL", ("NOT_RATED_WITH_HEDGE",), ()),
        ("post hoc, unlabelled", "[Tutoring probably helps boys more]" + fspan("F05") + " [@a].", "synthesis",
         "FAIL", ("POST_HOC_UNLABELED",), ()),
        ("nonstandard hedge", "[Tutoring appears to probably raise scores]" + fspan("F01", "pa-c01 pb-c01")
         + " [@a; @b].", "synthesis", "NEEDS_REVIEW", ("NONSTANDARD_HEDGE",), ()),
        ("significance label", "[Tutoring probably raises scores, a statistically significant gain]"
         + fspan("F01", "pa-c01 pb-c01") + " [@a; @b].", "synthesis", "NEEDS_REVIEW", ("SIGNIFICANCE_LABEL",), ()),
        ("moderator cue, unbound", "Effects were stronger for boys [@a].", "synthesis", "NEEDS_REVIEW",
         ("MODERATOR_CUE_UNLABELED",), ()),
        ("unmarked conclusion", "Tutoring probably raises scores [@a; @b].", "synthesis", "NEEDS_REVIEW",
         ("FINDING_UNMARKED",), ()),
        ("quote of a cited claim is exempt", '[The trial reports that "Reading scores rose by 0.21 standard '
         'deviations"]' + fspan("F07", "pa-c01 pb-c01") + " [@a; @b].", "synthesis", "PASS", (),
         ("QUOTE_NOT_FROM_CLAIM",)),
        ("quote not from a claim", 'The authors wrote "seven of ten studies were clearly positive" [@a].',
         "synthesis", "NEEDS_REVIEW", ("QUOTE_NOT_FROM_CLAIM",), ()),
        ("exempt methods section", "## Methods\n\nWe did not pool; 7 of 10 studies were significant [@a].",
         "synthesis", "PASS", ("SECTION_EXEMPT", "CITATION_OK"), ("VOTE_COUNT_SIGNIFICANCE",)),
        ("citations still checked in an exempt section", "## References\n\nSee [@zz2020nope].", "synthesis", "FAIL",
         ("CITEKEY_UNKNOWN",), ()),
        ("edge unknown", '[B builds on A]{.lr-edge edges="E099"} [@b; @a].', "synthesis", "FAIL", ("EDGE_UNKNOWN",),
         ()),
        ("dispute without a quoted relation", '[B disputes A]{.lr-edge edges="E001"} [@b; @a].', "synthesis",
         "NEEDS_REVIEW", ("EDGE_RELATION_UNSUPPORTED",), ()),
        ("dispute with a quoted relation", '[B disputes A]{.lr-edge edges="E002"} [@b; @a].', "synthesis", "PASS",
         ("EDGE_OK",), ()),
        ("dispute wording with no link", "Baker disputes the earlier trial [@b; @a].", "synthesis", "NEEDS_REVIEW",
         ("EDGE_RELATION_UNSUPPORTED",), ()),
        ("code is not read", "Run `lit_verify report` with `@notakey` [@a].", "synthesis", "PASS", (),
         ("CITEKEY_UNKNOWN",)),
        # --- 1.11.0 (review cycle 1): lint false negatives (Q-W5) ---
        ("FN1 on average", "On average, the programmes raised reading scores by 0.15 SD [@a; @b; @c].", "synthesis",
         "FAIL", ("POOLED_ESTIMATE",), ()),
        ("FN2 combined gain", "Tutoring produced a combined gain of 0.15 SD [@a; @b].", "synthesis", "FAIL",
         ("POOLED_ESTIMATE",), ()),
        ("FN3 averaging", "Averaging the three estimates gives 0.15 SD [@a; @b; @c].", "synthesis", "FAIL",
         ("POOLED_ESTIMATE",), ()),
        ("FN4 mean of the estimates", "The mean of the study estimates was 0.15 SD [@a; @b].", "synthesis", "FAIL",
         ("POOLED_ESTIMATE",), ()),
        # report-lint-v3 (user decision 2026-11-01, item 2): a pooling phrase with no number is not a pooled estimate; the
        #   unmarked multi-paper conclusion goes to a person
        ("FN5 on average across trials (no number: user decision 2026-11-01)", "On average, tutoring programmes raised reading scores "
         "across the included trials [@a; @b].", "synthesis", "NEEDS_REVIEW", ("FINDING_UNMARKED",),
         ("POOLED_ESTIMATE",)),
        ("FN6 bare count", "Seven studies reported statistically significant gains, while three did not [@a; @b].",
         "synthesis", "FAIL", ("VOTE_COUNT_SIGNIFICANCE",), ()),
        ("FN7 most of the included", "Most of the included studies found positive effects [@a; @b].", "synthesis",
         "NEEDS_REVIEW", ("VOTE_COUNT_INFORMAL",), ()),
        ("FN8 fraction", "In 3/5 studies the effect was positive and significant [@a; @b].", "synthesis", "FAIL",
         ("VOTE_COUNT_SIGNIFICANCE",), ()),
        ("FN9 all three", "All three trials found significant improvements [@a; @b; @c].", "synthesis", "FAIL",
         ("VOTE_COUNT_SIGNIFICANCE",), ()),
        ("FN10 unbound booster (review since report-lint-v3)", "Small-group tutoring conclusively raises reading "
         "scores [@a].", "synthesis", "NEEDS_REVIEW", ("BOOSTER_UNMARKED",), ("BOOSTER",)),
        ("FN11 clearly improves", "[Tutoring probably raises scores and clearly improves attendance]"
         + fspan("F01", "pa-c01 pb-c01") + " [@a; @b].", "synthesis", "FAIL", ("BOOSTER",), ()),
        ("FN12 typed sign-test p", "[Three of three effects favoured tutoring (sign test, p = 0.01)]"
         + fspan("F01", "pa-c01 pb-c01 pc-c01") + " [@a; @b; @c].", "synthesis", "FAIL", ("SIGN_TEST_MISMATCH",), ()),
        ("sign test with the computed interval", "[Three of three effects favoured tutoring (sign test, p = 0.25; 95% "
         "CI 44% to 100%)]" + fspan("F01", "pa-c01 pb-c01 pc-c01") + " [@a; @b; @c].", "synthesis", "PASS",
         ("DIRECTION_SIGN_TEST",), ()),
        ("FN13 percent summary", "[Across 3 studies the estimates ranged from 12% to 45% (descriptive summary, not a "
         "pooled estimate)]" + fspan("F01", "pa-c01 pb-c01 pc-c01") + " [@a; @b; @c].", "synthesis", "FAIL",
         ("DESCRIPTIVE_SUMMARY_NUMBER_MISMATCH",), ()),
        ("FN14 abstract percent words", "Reading buddies raised scores by 12 percent [@f, per abstract].", "synthesis",
         "FAIL", ("ABSTRACT_ONLY_NUMBER",), ()),
        ("FN16 unhedged unmarked conclusion", "Small-group tutoring raises reading scores [@a; @b].", "synthesis",
         "NEEDS_REVIEW", ("FINDING_UNMARKED",), ()),
        # --- false positives (Q-W6, M-I1/I2) ---
        ("FP5 CI level is not a result", "Allen found 0.21 (95% CI) and Baker found 0.15 [@a; @b].", "synthesis",
         "NEEDS_REVIEW", (), ("NUMBER_ACROSS_PAPERS",)),
        ("FP6 p threshold is not a result", "The trial found gains (p < .05) [@a].", "synthesis", "PASS", (),
         ("NUMBER_NOT_IN_CITED_CLAIM",)),
        ("FP7 a cited meta-analysis's own estimate", "A prior meta-analysis [@b] reported a pooled effect of 0.15, "
         "larger than the single trial [@a].", "synthesis", "PASS", (), ("POOLED_ESTIMATE",)),
        ("FP9 escaped at signs", "Write to lab\\@x or see \\@notakey [@a].", "synthesis", "PASS", (),
         ("CITEKEY_UNKNOWN", "CITEKEY_NOT_IN_BIB")),
        ("FP2 'Since May' is a month", "[Since May, tutoring raises scores]" + fspan("F07", "pa-c01 pb-c01")
         + " [@a; @b].", "synthesis", "PASS", (), ("CERTAINTY_WEAKER", "CERTAINTY_STACKED_HEDGE")),
        ("I1 study features are not results", "Few studies report effects for rural pupils [@a; @b].", "synthesis",
         "PASS", (), ("VOTE_COUNT_INFORMAL",)),
        # --- Pandoc @{key} (Q-W7) ---
        ("@{key} is a citation", "Tutoring helps [@{u}].", "synthesis", "FAIL", ("CITATION_UNVERIFIED",), ()),
        ("@{key} unknown", "Tutoring helps [@{zz nope}].", "synthesis", "FAIL", ("CITEKEY_UNKNOWN",), ()),
        ("unclosed @{ fails closed", "Tutoring helps @{u and more.", "synthesis", "FAIL", ("CITEKEY_UNKNOWN",), ()),
        # --- wrapped markers (C-W1) ---
        ("wrapped marker is read", "[Tutoring probably raises scores]{.lr-finding\nfid=F01 claims=\"pa-c01 pb-c01\"} "
         "[@a; @b].", "synthesis", "PASS", (), ("SPAN_MALFORMED", "FINDING_UNMARKED")),
        ("detached marker is malformed", "[Tutoring probably raises scores]\n{.lr-finding fid=F01 claims=\"pa-c01\"} "
         "[@a; @b].", "synthesis", "FAIL", ("SPAN_MALFORMED",), ()),
        # --- the table's own wording (M-B1, M-W11..M-W14) ---
        ("little to no difference, high", "[Tutoring results in little to no difference in attendance]"
         + fspan("F07", "pa-c01 pb-c01") + " [@a; @b].", "synthesis", "PASS", (), ("NO_EFFECT_CLAIM",)),
        ("little to no difference, moderate", "[Tutoring probably results in little to no difference in attendance]"
         + fspan("F01", "pa-c01 pb-c01") + " [@a; @b].", "synthesis", "PASS", (), ("NO_EFFECT_CLAIM",)),
        ("little to no difference, low", "[Tutoring may result in little to no difference in attendance]"
         + fspan("F03", "pa-c01 pb-c01") + " [@a; @b].", "synthesis", "PASS", (), ("NO_EFFECT_CLAIM",)),
        ("little to no effect, very low", "[Tutoring may have little to no effect on attendance, but the evidence is "
         "very uncertain]" + fspan("F04") + " [@a].", "synthesis", "PASS", (), ("NO_EFFECT_CLAIM",)),
        ("paired absence statement", "[There is no evidence of an effect on attendance, which is not evidence of no "
         "effect]" + fspan("F03", "pa-c01 pb-c01") + " [@a; @b].", "synthesis", "PASS", (),
         ("NO_EFFECT_CLAIM", "CERTAINTY_STRONGER")),
        ("unbound no effect (review since report-lint-v3)", "Tutoring has no effect on attendance [@a].", "synthesis",
         "NEEDS_REVIEW", ("NO_EFFECT_CLAIM_UNMARKED",), ("NO_EFFECT_CLAIM",)),
        ("newly established is not a booster", "[Tutoring probably improves reading scores in newly established "
         "charter schools]" + fspan("F01", "pa-c01 pb-c01") + " [@a; @b].", "synthesis", "PASS", (), ("BOOSTER",)),
        ("established that is a booster", "[Tutoring probably raises scores; the trial established that it works]"
         + fspan("F01", "pa-c01 pb-c01") + " [@a; @b].", "synthesis", "FAIL", ("BOOSTER",), ()),
        ("evidence suggests, low", "[Evidence suggests that tutoring improves reading scores]"
         + fspan("F03", "pa-c01 pb-c01") + " [@a; @b].", "synthesis", "PASS", (), ("CERTAINTY_STRONGER",)),
        ("the available evidence suggests, low", "[The available evidence suggests that tutoring improves reading "
         "scores]" + fspan("F03", "pa-c01 pb-c01") + " [@a; @b].", "synthesis", "PASS", (), ("CERTAINTY_STRONGER",)),
        ("unclear whether, very low", "[It is unclear whether tutoring improves reading scores]" + fspan("F04")
         + " [@a].", "synthesis", "PASS", (), ("CERTAINTY_STRONGER", "VERY_LOW_WITHOUT_UNCERTAIN")),
        ("we don't know if, very low", "[We don't know if tutoring improves reading scores]" + fspan("F04")
         + " [@a].", "synthesis", "PASS", (), ("CERTAINTY_STRONGER", "VERY_LOW_WITHOUT_UNCERTAIN")),
        ("unclear whether on a low finding is weaker", "[It is unclear whether tutoring improves reading scores]"
         + fspan("F03", "pa-c01 pb-c01") + " [@a; @b].", "synthesis", "NEEDS_REVIEW", ("CERTAINTY_WEAKER",),
         ("CERTAINTY_STRONGER",)),
        ("another level's word", "[Tutoring probably improves reading scores; whether it lasts is uncertain]"
         + fspan("F01", "pa-c01 pb-c01") + " [@a; @b].", "synthesis", "NEEDS_REVIEW", ("NONSTANDARD_HEDGE",), ()),
        ("'may' on an unrated finding", "[Teachers may see scheduling as a barrier (certainty not rated: qualitative "
         "evidence)]" + fspan("F02") + " [@a].", "synthesis", "FAIL", ("NOT_RATED_WITH_HEDGE",), ()),
        # --- a claim whose number failed (Q-W1) ---
        ("claim with a failed number", '[It works]{.lr-claim claims="pa-c04"} [@a].', "synthesis", "FAIL",
         ("CLAIM_NOT_VERIFIED",), ()),
        # --- report-lint-v3 / report-rules-v3 (review cycle 2, user decision 2026-11-01) ---
        # pooling (user decision 2026-11-01, item 2): one number for several cited studies fails; the phrases alone do not
        ("D35 overall + one number", "Overall, tutoring raised reading scores by 0.15 SD [@a; @b; @c].", "synthesis",
         "FAIL", ("POOLED_ESTIMATE",), ()),
        ("D35 pooling the estimates", "Pooling the three estimates gives 0.15 SD [@a; @b; @c].", "synthesis", "FAIL",
         ("POOLED_ESTIMATE",), ()),
        ("D35 taken together + a number", "Taken together, the studies show a gain of about 0.15 SD [@a; @b; @c].",
         "synthesis", "FAIL", ("POOLED_ESTIMATE",), ()),
        ("D35 the typical study + a number", "The typical study found a gain of 0.15 SD [@a; @b; @c].", "synthesis",
         "FAIL", ("POOLED_ESTIMATE",), ()),
        ("D35 overall + one number with its interval", "Overall, the effect was 0.15 SD (95% CI 0.05 to 0.25) [@a; @b; "
         "@c].", "synthesis", "FAIL", ("POOLED_ESTIMATE",), ()),
        ("D35 taken together, bound, low, no number", "[Taken together, the studies suggest tutoring may improve "
         "reading]" + fspan("F09", "pa-c01 pb-c01 pc-c01") + " [@a; @b; @c].", "synthesis", "PASS", (), ()),
        ("D35 overall, bound, moderate, no number", "[Overall, tutoring probably raises reading scores]"
         + fspan("F01", "pa-c01 pb-c01") + " [@a; @b].", "synthesis", "PASS", (), ()),
        ("D35 the typical study, no number", "The typical study was a small trial in one district [@a; @b].",
         "synthesis", "PASS", (), ("POOLED_ESTIMATE",)),
        ("D35 remedy: each study's estimate with its own citation", "Tutoring raised scores by 0.21 SD in one trial "
         "[@a] and by 0.15 SD in an event study [@b].", "synthesis", "NEEDS_REVIEW", (), ("POOLED_ESTIMATE",)),
        ("D35 remedy: overall + per-study numbers", "Overall, the trial found 0.21 SD and the event study 0.15 SD "
         "[@a; @b].", "synthesis", "NEEDS_REVIEW", (), ("POOLED_ESTIMATE",)),
        ("D35 remedy: the labelled descriptive summary", "[Across 3 studies reporting SD units of reading score, the "
         "estimates ranged from 0.09 to 0.21 (median 0.15; IQR 0.12 to 0.18; descriptive summary, not a pooled "
         "estimate)]" + fspan("F01", "pa-c01 pb-c01 pc-c01") + " [@a; @b; @c].", "synthesis", "PASS",
         ("DESCRIPTIVE_SUMMARY_OK",), ("POOLED_ESTIMATE",)),
        ("D35 remedy: overall + the descriptive summary", "[Overall, across 3 studies the estimates ranged from 0.09 "
         "to 0.21 (median 0.15; IQR 0.12 to 0.18; descriptive summary, not a pooled estimate)]"
         + fspan("F01", "pa-c01 pb-c01 pc-c01") + " [@a; @b; @c].", "synthesis", "PASS", ("DESCRIPTIVE_SUMMARY_OK",),
         ("POOLED_ESTIMATE",)),
        ("D35 combined intervention is not pooling", "Allen reported the combined effect of tutoring and coaching, "
         "while Baker studied tutoring alone [@a; @b].", "synthesis", "PASS", (), ("POOLED_ESTIMATE",)),
        ("D35 on average, a characteristic in words", "Pupils in the two evaluations were, on average, in the middle "
         "primary grades [@a; @b].", "synthesis", "PASS", (), ("POOLED_ESTIMATE",)),
        # realistic prose (C2-QW1): no false FAIL
        ("QW1 at baseline no difference", "At baseline, the trial found no difference in reading scores between the "
         "two arms [@a].", "synthesis", "PASS", (), ("NO_EFFECT_CLAIM", "NO_EFFECT_CLAIM_UNMARKED")),
        ("QW1 no difference at baseline", "The arms showed no difference in reading scores at baseline [@a].",
         "synthesis", "PASS", (), ("NO_EFFECT_CLAIM", "NO_EFFECT_CLAIM_UNMARKED")),
        ("QW1 have established programmes", "Several states have established tutoring programmes [@a].", "synthesis",
         "PASS", (), ("BOOSTER", "BOOSTER_UNMARKED")),
        ("QW1 study characteristics range", "Sample sizes ranged from 412 to 2,560 pupils across the three studies "
         "[@a; @b; @c].", "synthesis", "NEEDS_REVIEW", (), ("DESCRIPTIVE_SUMMARY_UNSUPPORTED",)),
        ("QW1 abstract-only citation in its own clause", "Allen found gains of 0.21 SD [@a], and a pilot reported "
         "similar gains [@f, per abstract].", "synthesis", "NEEDS_REVIEW", (), ("ABSTRACT_ONLY_NUMBER",)),
        ("QW1 abstract number before its citation", "Gains were 12 percent, the pilot reported [@f, per abstract].",
         "synthesis", "FAIL", ("ABSTRACT_ONLY_NUMBER",), ()),
        ("QW1 clearly show, unmarked", "The authors clearly show the attrition in each arm [@a].", "synthesis",
         "NEEDS_REVIEW", ("BOOSTER_UNMARKED",), ("BOOSTER",)),
        ("QW1 programme name, unmarked", "The district adopted the Proven Readers programme in 2016 [@a].",
         "synthesis", "NEEDS_REVIEW", ("BOOSTER_UNMARKED",), ("BOOSTER",)),
        ("QW1 has established that, unmarked", "The trial has established that tutoring works [@a].", "synthesis",
         "NEEDS_REVIEW", ("BOOSTER_UNMARKED",), ()),
        # C2-CW1: only a quote found on its page exempts a sentence
        ("CW1 quote of an unverified claim is linted", 'The authors wrote that "this program proves that tutoring '
         'works for every pupil in every school" [@a].', "synthesis", "NEEDS_REVIEW",
         ("QUOTE_NOT_FROM_CLAIM", "BOOSTER_UNMARKED"), ()),
        ("CW1 quote of a verified claim is exempt", 'The authors wrote that "this program proves that tutoring works '
         'for every pupil"' + " [@b].", "synthesis", "PASS", (), ("QUOTE_NOT_FROM_CLAIM", "BOOSTER_UNMARKED")),
        # C2-CW2 / user decision 2026-11-01, item 3: a title-only paper under "Further reading"
        ("CW2 metadata only under Further reading", "## Further reading\n\n- A study of rural tutoring [@m].",
         "synthesis", "PASS", (), ("METADATA_ONLY_CITED",)),
        ("CW2 metadata only under Further reading, final", "## Further reading\n\n- A study of rural tutoring [@m].",
         "final", "PASS", (), ("METADATA_ONLY_CITED",)),
        ("CW2 Further reading subsection", "## Further reading\n\n### Rural schools\n\n- Rural tutoring [@m].",
         "synthesis", "PASS", (), ("METADATA_ONLY_CITED",)),
        ("CW2 Further reading with a number", "## Further reading\n\n- Scores rose by 0.40 SD [@m].", "synthesis",
         "FAIL", ("METADATA_ONLY_CITED",), ()),
        ("CW2 Further reading with a marker", "## Further reading\n\n- [Tutoring probably helps]"
         + fspan("F01", "pa-c01") + " [@m; @a].", "synthesis", "FAIL", ("METADATA_ONLY_CITED",), ()),
        ("CW2 another heading", "## Where to start reading\n\n- A study of rural tutoring [@m].", "synthesis", "FAIL",
         ("METADATA_ONLY_CITED",), ()),
        ("CW2 level-1 heading is not the reading list", "# Further reading\n\n- A study of rural tutoring [@m].",
         "synthesis", "FAIL", ("METADATA_ONLY_CITED",), ()),
        # q-I4: claims marked from an abstract need the label even on a fully read paper
        ("I4 abstract claim of a read paper, unlabelled", '[Buddies help readers]{.lr-claim claims="pa-a01"} [@a].',
         "synthesis", "FAIL", ("ABSTRACT_ONLY_UNLABELED",), ()),
        ("I4 abstract claim of a read paper, labelled", '[Buddies help readers]{.lr-claim claims="pa-a01"} '
         "[@a, per abstract].", "synthesis", "PASS", (), ("ABSTRACT_ONLY_UNLABELED", "PER_ABSTRACT_ON_FULL_TEXT")),
        # C2-QW5: a labelled number needing review is a review item, not a failed number
        ("QW5 labelled number needs review", '[It works]{.lr-claim claims="pa-c05"} [@a].', "synthesis",
         "NEEDS_REVIEW", ("CLAIM_NUMBER_NEEDS_REVIEW",), ("CLAIM_NOT_VERIFIED",)),
        # C2-B2: the newest retraction check is not the attached one
        ("B2 retraction record not the newest, draft", "Tutoring helps [@rn].", "synthesis", "NEEDS_REVIEW",
         ("RETRACTION_CHECK_NOT_LATEST_DRAFT",), ("RETRACTION_CHECK_NOT_LATEST",)),
        ("B2 retraction record not the newest, final", "Tutoring helps [@rn].", "final", "FAIL",
         ("RETRACTION_CHECK_NOT_LATEST",), ()),
        # --- report-lint-v4 (review cycle 3, round G1) ---
        # W2: one effect number credited to several studies, in the wordings a writer uses
        ("G1 W2 pooled across the trials", "Pooled across the trials, the effect was 0.15 SD [@a; @b; @c].",
         "synthesis", "FAIL", ("POOLED_ESTIMATE",), ()),
        ("G1 W2 finding across the three trials", "[Across the three trials, tutoring probably raised reading scores by "
         "0.15 SD]" + fspan("F01", "pa-c01 pb-c01 pc-c01") + " [@a; @b; @c].", "synthesis", "FAIL",
         ("POOLED_ESTIMATE",), ()),
        ("G1 W2 number before the phrase", "The gain was 0.15 SD, taken together [@a; @b; @c].", "synthesis", "FAIL",
         ("POOLED_ESTIMATE",), ()),
        ("G1 W2 citation at the end of the next clause", "Pooled across the trials, the effect was 0.15 SD, as three "
         "trials report [@a; @b; @c].", "synthesis", "FAIL", ("POOLED_ESTIMATE",), ()),
        ("G1 W2 an average gain", "The studies found an average gain of 0.15 SD [@a; @b; @c].", "synthesis", "FAIL",
         ("POOLED_ESTIMATE",), ()),
        ("G1 W2 combined,", "Combined, the trials show a gain of 0.15 SD [@a; @b; @c].", "synthesis", "FAIL",
         ("POOLED_ESTIMATE",), ()),
        ("G1 W2 in aggregate", "In aggregate, tutoring raised scores by 0.15 SD [@a; @b; @c].", "synthesis", "FAIL",
         ("POOLED_ESTIMATE",), ()),
        ("G1 W2 collectively", "Collectively, the three trials point to a gain of 0.15 SD [@a; @b; @c].", "synthesis",
         "FAIL", ("POOLED_ESTIMATE",), ()),
        ("G1 across, bound, no number (user decision 2026-11-01)", "[Across the three trials, tutoring probably raised reading scores]"
         + fspan("F01", "pa-c01 pb-c01 pc-c01") + " [@a; @b; @c].", "synthesis", "PASS", (), ("POOLED_ESTIMATE",)),
        # W3: study descriptions are not pooled effects; a range with one citation per number lists studies
        ("G1 W3 typical study enrolled", "The typical study enrolled about 600 pupils [@a; @b].", "synthesis",
         "NEEDS_REVIEW", (), ("POOLED_ESTIMATE", "NUMBER_ACROSS_PAPERS")),
        ("G1 W3 average age", "On average, pupils in the two evaluations were 8.5 years old [@a; @b].", "synthesis",
         "NEEDS_REVIEW", (), ("POOLED_ESTIMATE", "NUMBER_ACROSS_PAPERS")),
        ("G1 W3 range with own citations", "The two trials' estimates ranged from 0.09 SD [@c] to 0.21 SD [@a].",
         "synthesis", "PASS", (), ("DESCRIPTIVE_SUMMARY_UNSUPPORTED",)),
        ("G1 W3 range, own citations after words", "Estimates ranged from 0.09 SD in the survey [@c] to 0.21 SD in the "
         "trial [@a].", "synthesis", "PASS", (), ("DESCRIPTIVE_SUMMARY_UNSUPPORTED",)),
        # consistency I7: a number with its own citation must be that paper's
        ("G1 I7 number credited to the wrong study", "Tutoring raised scores by 0.15 SD in one trial [@a] and by 0.21 SD "
         "in another [@b].", "synthesis", "NEEDS_REVIEW", ("NUMBER_NOT_IN_CITED_CLAIM",), ()),
        ("G1 I7 each number with its own paper", "Tutoring raised scores by 0.21 SD in one trial [@a] and by 0.15 SD in "
         "another [@b].", "synthesis", "NEEDS_REVIEW", (), ("NUMBER_NOT_IN_CITED_CLAIM",)),
        # W4: an effect number in a sentence that cites nothing goes to a person
        ("G1 W4 uncited effect number", "Allen ran a cluster trial in nine schools [@a]. Reading scores rose by 0.45 SD.",
         "synthesis", "NEEDS_REVIEW", ("NUMBER_NOT_IN_CITED_CLAIM",), ()),
        ("G1 W4 an uncited count is not an effect", "The search found 1,204 records.", "synthesis", "PASS", (),
         ("NUMBER_NOT_IN_CITED_CLAIM",)),
        # W5: a Further reading item names a paper and why to read it, never what it found
        ("G1 W5 taken together these papers show", "## Further reading\n\nTaken together, these papers show that "
         "tutoring works [@m].", "synthesis", "FAIL", ("METADATA_ONLY_CITED",), ()),
        ("G1 W5 item stating a finding", "## Further reading\n\n- Smith shows that tutoring doubles reading gains for "
         "every pupil [@m].", "synthesis", "FAIL", ("METADATA_ONLY_CITED",), ()),
        ("G1 W5 item with a result verb", "## Further reading\n\n- Rural tutoring raised reading scores [@m].",
         "synthesis", "FAIL", ("METADATA_ONLY_CITED",), ()),
        ("G1 W5 a good list", "## Further reading\n\n- A district case study of how tutoring was rolled out [@m]\n"
         "- Background on programme costs [@m]\n", "synthesis", "PASS", (), ("METADATA_ONLY_CITED",)),
        ("G1 W5 'the effect of' names a topic", "## Further reading\n\n- A study of the effect of tutoring on reading "
         "[@m].", "synthesis", "PASS", (), ("METADATA_ONLY_CITED",)),
        ("G1 W5 'may be useful' is fine", "## Further reading\n\n- A rural case study that may be useful for small "
         "schools [@m].", "final", "PASS", (), ("METADATA_ONLY_CITED",)),
        ("G1 I2 numbered heading '6.'", "## 6. Further reading\n\n- A study of rural tutoring [@m].", "synthesis",
         "PASS", (), ("METADATA_ONLY_CITED",)),
        ("G1 I2 numbered heading '6'", "## 6 Further reading\n\n- A study of rural tutoring [@m].", "synthesis", "PASS",
         (), ("METADATA_ONLY_CITED",)),
        ("G1 I2 trailing colon", "## Further reading:\n\n- A study of rural tutoring [@m].", "synthesis", "PASS", (),
         ("METADATA_ONLY_CITED",)),
        # --- report-lint-v5 / report-rules-v5 (polish pass H, round-G re-review) ---
        # W2: a Further reading item that names a question, a design or what the title suggests names a topic
        ("H W2 examines whether", "## Further reading\n\n- [@m]: examines whether tutoring improves attendance in rural "
         "schools.", "final", "PASS", (), ("METADATA_ONLY_CITED",)),
        ("H W2 asks whether", "## Further reading\n\n- [@m]: asks whether peer tutoring raises reading scores for older "
         "pupils.", "final", "PASS", (), ("METADATA_ONLY_CITED",)),
        ("H W2 tests whether", "## Further reading\n\n- [@m]: tests whether tutoring reduces chronic absence.", "final",
         "PASS", (), ("METADATA_ONLY_CITED",)),
        ("H W2 whether ... had any effect", "## Further reading\n\n- [@m]: an evaluation of whether summer tutoring had "
         "any effect on reading.", "final", "PASS", (), ("METADATA_ONLY_CITED",)),
        ("H W2 shows how", "## Further reading\n\n- [@m]: shows how one district scheduled tutoring time.", "final",
         "PASS", (), ("METADATA_ONLY_CITED",)),
        ("H W2 its title suggests", "## Further reading\n\n- [@m]: its title suggests a study of tutor training.",
         "final", "PASS", (), ("METADATA_ONLY_CITED",)),
        ("H W2 meta-analytic review", "## Further reading\n\n- [@m]: a meta-analytic review of tutoring programmes.",
         "final", "PASS", (), ("METADATA_ONLY_CITED",)),
        ("H W2 across 40 studies", "## Further reading\n\n- [@m]: a review of tutoring across 40 studies.", "final",
         "PASS", (), ("METADATA_ONLY_CITED",)),
        # W2: a finding in other words still fails
        ("H W2 argues that", "## Further reading\n\n- [@m]: argues that tutoring works best in small groups.",
         "synthesis", "FAIL", ("METADATA_ONLY_CITED",), ()),
        ("H W2 reports that", "## Further reading\n\n- [@m]: reports that tutored pupils read better than their "
         "peers.", "synthesis", "FAIL", ("METADATA_ONLY_CITED",), ()),
        ("H W2 outperformed", "## Further reading\n\n- [@m]: tutored pupils outperformed their peers.", "synthesis",
         "FAIL", ("METADATA_ONLY_CITED",), ()),
        ("H W2 according to the authors", "## Further reading\n\n- [@m]: according to the authors, tutoring is "
         "cost-effective.", "synthesis", "FAIL", ("METADATA_ONLY_CITED",), ()),
        ("H W2 shows that", "## Further reading\n\n- [@m]: shows that mentoring raises attendance in rural schools.",
         "synthesis", "FAIL", ("METADATA_ONLY_CITED",), ()),
        ("H W2 unclear whether stays certainty wording", "## Further reading\n\n- [@m]: it is unclear whether "
         "tutoring helps.", "synthesis", "FAIL", ("METADATA_ONLY_CITED",), ()),
        # W3: one effect number credited to several studies of which only one prints it goes to a person
        ("H W3 one number, one study prints it", "Effects in the three trials were about 0.15 SD [@a; @b; @c].",
         "synthesis", "NEEDS_REVIEW", ("NUMBER_NOT_IN_CITED_CLAIM",), ("NUMBER_ACROSS_PAPERS",)),
        ("H W3 one number in a finding marker", "[Tutoring probably raises reading scores, by about 0.15 SD in these "
         "trials]" + fspan("F01", "pa-c01 pb-c01 pc-c01") + " [@a; @b; @c].", "synthesis", "NEEDS_REVIEW",
         ("NUMBER_NOT_IN_CITED_CLAIM",), ()),
        ("H W3 one number no study prints still fails", "Effects in the three trials were about 0.16 SD [@a; @b; @c].",
         "synthesis", "FAIL", ("NUMBER_ACROSS_PAPERS",), ()),
        ("H W3 every cited study prints it", "Effects in both trials were about 0.15 SD [@b; @d].", "synthesis",
         "PASS", (), ("NUMBER_NOT_IN_CITED_CLAIM", "NUMBER_ACROSS_PAPERS")),
        ("H W3 a cited meta-analysis's number is its own", "A prior meta-analysis [@b] reported an effect of 0.15, "
         "larger than the single trial [@a].", "synthesis", "PASS", (), ("NUMBER_NOT_IN_CITED_CLAIM",)),
        # W5: a number between commas credited to the citation after it is not a pooled estimate
        ("H W5 appositive with its own citation", "Overall, the largest estimate, 0.21 SD, came from the trial [@a]; "
         "the event study found 0.15 SD [@b].", "synthesis", "NEEDS_REVIEW", (), ("POOLED_ESTIMATE",)),
        ("H W5 appositive, taken together", "Taken together, the clearest result, a gain of 0.21 SD, comes from the "
         "trial [@a], and the event study [@b] points the same way.", "synthesis", "NEEDS_REVIEW", (),
         ("POOLED_ESTIMATE",)),
        ("H W5 appositive credited to three studies still fails", "Overall, the gain, 0.15 SD, came from the three "
         "trials [@a; @b; @c].", "synthesis", "FAIL", ("POOLED_ESTIMATE",), ()),
        # round-G lines the re-review found untested: months of learning are an effect; table cells are not read
        ("H R6 months of learning is an effect", "Overall, tutored pupils gained 2.5 months of learning [@a; @b; @c].",
         "synthesis", "FAIL", ("POOLED_ESTIMATE",), ()),
        ("H R7 an uncited table cell is not read", "| Study | Effect |\n|---|---|\n| Allen trial | 0.21 SD |\n",
         "synthesis", "PASS", (), ("NUMBER_NOT_IN_CITED_CLAIM",)),
        # W1 / I8: the final title rule's own fix, and its review item in a draft
        ("H W1 title differs in a draft", "Tutoring helps [@td].", "synthesis", "NEEDS_REVIEW",
         ("CITATION_TITLE_DIFFERS_DRAFT",), ("CITATION_UNVERIFIED",)),
    ]

    def test_reviewer_memo_has_no_false_fail(self):
        # C2-QW1: the cycle-2 reviewer's should-not-FAIL sentences (probe 02 Part B) give no FAIL item
        sentences = [
            "Allen found gains of 0.21 SD [@a], and a pilot reported similar gains [@f, per abstract].",
            "At baseline the trial found no difference between arms [@a].",
            "Several states have established tutoring programmes [@a].",
            "Sample sizes ranged from 412 to 2,560 pupils [@a; @b; @c].",
            "Allen reported the combined effect of tutoring and coaching, while Baker studied tutoring alone [@a; @b].",
            "Allen's pupils were, on average, eight years old, and Baker's were ten [@a; @b].",
            "The authors clearly show the attrition in each arm [@a].",
            "The authors report no effect on attendance (0.01 SD) [@a].",
            "The district adopted the Proven Readers programme in 2016 [@a]."]
        view = mk_view()
        for s in sentences:
            with self.subTest(s):
                items, _ = lrr.check_report(s, view, "synthesis")
                self.assertEqual([i["status"] for i in items if i["severity"] == "fail"], [])

    def test_fix_texts_name_remedies_that_pass(self):
        # Lesson of review cycles 1 and 2: the remedy a fix text names must pass the gate.
        view = mk_view()
        items, _ = lrr.check_report("Overall, tutoring raised reading scores by 0.15 SD [@a; @b; @c].", view)
        fix = next(i["fix"] for i in items if i["status"] == "POOLED_ESTIMATE")
        self.assertIn("each study's estimate with its own citation", fix)
        self.assertIn("descriptive summary (median and range)", fix)
        items, _ = lrr.check_report("Tutoring helps [@m].", view)
        fix = next(i["fix"] for i in items if i["status"] == "METADATA_ONLY_CITED")
        self.assertIn("'Further reading'", fix)
        # round G1: the Further-reading result-wording fix and the uncited-number fix name remedies that pass
        items, _ = lrr.check_report("## Further reading\n\n- Smith shows that tutoring works [@m].", view)
        fix = next(i["fix"] for i in items if i["status"] == "METADATA_ONLY_CITED")
        self.assertIn("A district case study of how tutoring was rolled out", fix)
        items, _ = lrr.check_report("Reading scores rose by 0.45 SD.", view)
        self.assertIn("Cite the paper that prints the number", next(i["fix"] for i in items))
        # polish pass H (W3): one study's number credited to three; its fix names the per-study remedy, which passes
        items, _ = lrr.check_report("Effects in the three trials were about 0.15 SD [@a; @b; @c].", view)
        it = next(i for i in items if i["status"] == "NUMBER_NOT_IN_CITED_CLAIM")
        self.assertIn("only b prints it", it["reason"])
        self.assertIn("credits it to all of them", it["reason"])
        self.assertIn("each study's estimate with its own citation", it["fix"])
        self.assertIn("labelled descriptive summary", it["fix"])
        # polish pass H (W1): the fix lit_verify gives for a paper reaches the researcher on CITATION_UNVERIFIED
        items, _ = lrr.check_report("Tutoring helps [@tu].", view)
        self.assertEqual(next(i["fix"] for i in items if i["status"] == "CITATION_UNVERIFIED"),
                         "Restore the data folder (test fix).")
        items, _ = lrr.check_report("Tutoring helps [@u].", view)
        self.assertIn("checked again and confirmed", next(i["fix"] for i in items if i["status"] == "CITATION_UNVERIFIED"))
        for remedy in ("## Further reading\n\n- A district case study of how tutoring was rolled out [@m].",
                       "## Further reading\n\n- [@m]: examines whether tutoring improves attendance in rural schools.",
                       "Effect sizes were 0.21 SD in one trial [@a], 0.15 SD in another [@b] and 0.09 SD in the "
                       "survey [@c].",
                       "Reading scores rose by 0.21 standard deviations [@a].",
                       "Tutoring raised scores by 0.21 SD in one trial [@a] and by 0.15 SD in an event study [@b]."):
            with self.subTest(remedy):
                items, _ = lrr.check_report(remedy, view)
                self.assertNotIn("fail", {i["severity"] for i in items}, sorted({i["status"] for i in items}))
        for remedy in ("Tutoring raised scores by 0.21 SD in one trial [@a] and by 0.15 SD in an event study [@b].",
                       "[Across 3 studies reporting SD units of reading score, the estimates ranged from 0.09 to 0.21 "
                       "(median 0.15; IQR 0.12 to 0.18; descriptive summary, not a pooled estimate)]"
                       + fspan("F01", "pa-c01 pb-c01 pc-c01") + " [@a; @b; @c].",
                       "## Further reading\n\n- A study of rural tutoring [@m].",
                       "Buddies may help readers [@f, per abstract]."):
            with self.subTest(remedy):
                items, _ = lrr.check_report(remedy, view)
                self.assertNotIn("fail", {i["severity"] for i in items}, sorted({i["status"] for i in items}))

    def test_every_template_passes_at_its_own_level(self):
        # M-B1: each certainty-language template, filled in, passes bound to a finding of its own level
        fill = {"{X}": "Tutoring", "{Y}": "reading scores", "{verb}": "raise", "{reduction|increase}": "increase"}
        fid = {"high": ("F07", "pa-c01 pb-c01", "[@a; @b]"), "moderate": ("F01", "pa-c01 pb-c01", "[@a; @b]"),
               "low": ("F03", "pa-c01 pb-c01", "[@a; @b]"), "very_low": ("F04", "pa-c01", "[@a]")}
        view = mk_view()
        n = 0
        for level, spec in lrr.CERTAINTY_LANGUAGE["levels"].items():
            for name, tpl in spec["templates"].items():
                s = tpl
                for k, v in fill.items():
                    s = s.replace(k, v)
                s = s.replace("{verb}s", "raises").replace("raises", "raises")
                s = s.replace("raise s", "raises").rstrip(".")
                f, cl, cite = fid[level]
                text = f"[{s}]" + fspan(f, cl) + f" {cite}."
                with self.subTest(level=level, template=name, text=text):
                    items, _ = lrr.check_report(text, view, "synthesis")
                    self.assertEqual(lrr.verdict_of(items), "PASS", sorted({i["status"] for i in items}))
                    n += 1
        self.assertGreaterEqual(n, 14)

    def test_nonstandard_reason_names_the_other_level(self):
        text = ("[Tutoring probably improves reading scores; whether it lasts is uncertain]"
                + fspan("F01", "pa-c01 pb-c01") + " [@a; @b].")
        items, _ = lrr.check_report(text, mk_view(), "synthesis")
        it = next(i for i in items if i["status"] == "NONSTANDARD_HEDGE")
        self.assertIn("a word for very low certainty", it["reason"])
        self.assertNotIn("not one of the certainty words", it["reason"])

    def test_cases(self):
        view = mk_view()
        for name, text, kind, verdict, must, must_not in self.CASES:
            with self.subTest(name):
                items, _ = lrr.check_report(text, view, kind)
                got = {it["status"] for it in items}
                self.assertEqual(lrr.verdict_of(items), verdict, (name, sorted(got)))
                self.assertEqual([s for s in must if s not in got], [], name)
                self.assertEqual([s for s in must_not if s in got], [], name)
                for it in items:                                   # plain reasons: no status or internal codes
                    self.assertNotRegex(it["reason"] + " " + it["fix"], r"\b[A-Z]+_[A-Z_]{3,}\b|state: |the check said|"
                                        r"ocr-layer|ocr\+vision|not-near-quote|precision-differs|\{\.lr-|fid=", name)

    def test_citation_parse(self):
        cites, groups = lrr.parse_citations("A [see @k1, pp. 3-5; -@k2, per abstract] and @k3. said; me@x.org; "
                                            "[@Key.With:Punct.]")
        self.assertEqual([c["key"] for c in cites], ["k1", "k2", "k3", "Key.With:Punct"])
        self.assertEqual([c["per_abstract"] for c in cites], [False, True, False, False])
        self.assertEqual([c["in_text"] for c in cites], [False, False, True, False])
        self.assertEqual(len(groups), 2)

    def test_sentence_split(self):
        text = "Smith et al. found gains. Then p. 7 gives 0.5 and e.g. more. Next one!\n\n| a | b |\n|---|---|\n- item"
        units = lrr.split_units(text)
        self.assertEqual([text[s:e].strip() for s, e in units],
                         ["Smith et al. found gains.", "Then p. 7 gives 0.5 and e.g. more.", "Next one!", "a", "b",
                          "- item"])

    def test_statuses_and_versions(self):
        self.assertEqual(set(lrr.REPORT_SEVERITY.values()), {"pass", "fail", "review", "warning"})
        self.assertEqual((lv.REPORT_CHECK_SCHEMA_VERSION, lv.REPORT_REDERIVE_VERSION, lrr.REPORT_RULES_VERSION,
                          lrr.CITATION_PARSE_VERSION, lrr.SENTENCE_SPLIT_VERSION, lrr.REPORT_LINT_VERSION),
                         ("lit-verify-report-check-v1", "report-rederive-v5", "report-rules-v5", "citations-v2",
                          "sentences-v1", "report-lint-v5"))
        self.assertEqual(lv.TOOL_VERSION, "1.14.0-daaf")
        self.assertEqual(lrr.CERTAINTY_LANGUAGE["table_version"], "2026-11-01b")
        # M-W16: a number's state is named in words in the quant reasons, never by its label code
        self.assertEqual(set(lv.NUMBER_LABEL_WORDS) - set(lv.NUMBER_LABELS.values()), set())
        self.assertEqual(len(lv.SEVERITY), 81)                       # the card table is untouched
        self.assertFalse(set(lrr.REPORT_SEVERITY) & {"CRITICAL_RISK_CONTRIBUTOR", "ESCALATION_UNRESOLVED",
                                                     "APPRAISAL_REDERIVE_MISMATCH", "CERTAINTY_ARITHMETIC_MISMATCH"})

    def test_status_index_count(self):
        # every REPORT_SEVERITY key is documented in lit-verify-report.md § Status index, with its severity
        doc = (_REPO_ROOT / ".claude" / "skills" / "literature-review" / "references" /
               "lit-verify-report.md").read_text()
        self.assertIn(f"the {len(lrr.REPORT_SEVERITY)} keys of `REPORT_SEVERITY`", doc)
        table = doc.split("## Status index", 1)[1].split("\n## ", 1)[0]
        rows = dict(re.findall(r"(?m)^\| `([A-Z_]+)` \| (pass|fail|review|warning) \|", table))
        self.assertEqual(rows, lrr.REPORT_SEVERITY)

    def test_phrase_table_hash_is_canonical(self):
        canon = json.dumps(lrr.CERTAINTY_LANGUAGE, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        import hashlib
        self.assertEqual(hashlib.sha256(canon.encode("utf-8")).hexdigest(), lrr.CERTAINTY_LANGUAGE_SHA256)

    @unittest.skipUnless(HAVE_YAML, "needs PyYAML (in the DAAF image, not on the CI runner)")
    def test_phrase_table_lockstep_with_yaml(self):
        import yaml
        published = yaml.safe_load((_REPO_ROOT / lv.REPORT_YAML_PATH).read_text())
        self.assertEqual(published, lrr.CERTAINTY_LANGUAGE)


@unittest.skipUnless(CAN_RUN_CLI, CLI_WHY)
class ReportOnDiskTests(ScratchCase):
    # `report` end to end on a copy of the P3 contract bundle (tests/python/fixtures/lit_corpus/contract_bundle).
    CLEAN = ("# Synthesis (fixture)\n\n## Findings\n\n[Small-group tutoring probably raises reading scores]"
             '{.lr-finding fid=F01 claims="user_f1c70001-c01 user_f1c70002-c01"} '
             "[@fixture-allen2019tutoring; @fixture-baker2020reading].\n\n"
             "[Across 3 studies reporting SD units of reading score, the estimates ranged from 0.09 to 0.21 (median "
             "0.15; IQR 0.12 to 0.18; descriptive summary, not a pooled estimate)]"
             '{.lr-finding fid=F01 claims="user_f1c70001-c01 user_f1c70002-c01 user_f1c70003-c01"} '
             "[@fixture-allen2019tutoring; @fixture-baker2020reading; @fixture-chen2021library].\n\n"
             "[Teachers described scheduling as the main barrier (certainty not rated: qualitative evidence)]"
             '{.lr-finding fid=F02 claims="user_f1c70004-c01"} [@fixture-diaz2022teachers].\n')
    PLANTED = ("Small-group tutoring had an average effect of 0.15 SD across the studies [@fixture-allen2019tutoring; "
               "@fixture-baker2020reading].\n\nSeven of ten studies found significant effects [@nosuch2020x].\n")

    def setUp(self):
        super().setUp()
        self.pd = self.root / "project"
        shutil.copytree(BUNDLE, self.pd)

    def report(self, name, text, *args):
        path = self.pd / "output" / name
        path.write_text(text)
        code, out, err = run_main(["report", self.pd, path, *args])
        rows = rows_of(self.pd / "output")
        check = json.loads((self.pd / "output" / rows[-1]["artifacts"]["report_check"]["name"]).read_text()) \
            if rows and rows[-1].get("artifacts") else None
        return code, check, out + err

    def test_clean_and_planted(self):
        code, check, out = self.report("clean.md", self.CLEAN)
        self.assertEqual((code, check["verdict"]), (0, "PASS"), out)
        self.assertEqual(check["schema_version"], "lit-verify-report-check-v1")
        self.assertEqual(check["inputs"]["phrase_table"]["sha256"], lrr.CERTAINTY_LANGUAGE_SHA256)
        self.assertGreaterEqual(check["rederive"]["cards_checked"], 4)
        code, check, out = self.report("planted.md", self.PLANTED)
        got = {it["status"] for it in check["items"]}
        self.assertEqual((code, check["verdict"]), (11, "FAIL"))
        for s in ("POOLED_ESTIMATE", "VOTE_COUNT_SIGNIFICANCE", "CITEKEY_UNKNOWN"):
            self.assertIn(s, got)
        self.assertNotIn(SENTINEL_KEY, (self.pd / "output" / "MANIFEST.jsonl").read_text())

    def test_final_rechecks_cards_and_the_bundle_has_no_sources(self):
        # The bundle's ingests name no stored source, so a re-check cannot re-derive them: fail closed.
        with mock.patch.dict(lv.SYNTHETIC_SOURCES, clear=True):
            code, check, _ = self.report("final.md", self.CLEAN, "--kind", "final")
        self.assertEqual((code, check["verdict"], check["rederive"]["cards_rechecked"] >= 4), (11, "FAIL", True))
        self.assertIn("CARD_RECHECK_DIFFERS", {it["status"] for it in check["items"]})

    def test_guards(self):
        outside = self.pd / "notes.md"
        outside.write_text("x")
        self.assertEqual(run_main(["report", self.pd, outside])[0], 2)
        bad = self.pd / "output" / "latin1.md"
        bad.write_bytes("caf\xe9".encode("latin-1"))
        self.assertEqual(run_main(["report", self.pd, bad])[0], 8)
        (self.pd / "output" / "references_v1.bib").unlink()
        good = self.pd / "output" / "x.md"
        good.write_text("Text.\n")
        self.assertEqual(run_main(["report", self.pd, good])[0], 10)
        self.assertEqual(run_main(["report", self.pd, good, "--data-version", "claims=x"])[0], 1)

    def test_tampered_table_fails_closed(self):
        claims = sorted((self.pd / "data").glob("claims_v*.parquet"))[-1]
        claims.write_bytes(claims.read_bytes() + b"\0")
        code, check, _ = self.report("t.md", "Tutoring helps [@fixture-allen2019tutoring].\n")
        self.assertEqual(code, 11)
        self.assertIn("TABLE_HASH_MISMATCH", {it["status"] for it in check["items"]})

    # --- 1.11.0 (review cycle 1): one appended row or table version must never clear anything (user decision, October 2026) ---
    @staticmethod
    def append_row(manifest, row):
        line = json.dumps(row, ensure_ascii=False)
        with open(manifest, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return lv.sha256_bytes(line.encode("utf-8"))

    def forge_table(self, table, change):
        # A new version of `table` with `change` applied to every row, plus a consistent data MANIFEST row.
        lc = lv.report_lc()
        data = self.pd / "data"
        latest = max(data.glob(f"{table}_v*.parquet"), key=lambda p: int(p.stem.rsplit("_v", 1)[1]))
        read, write = lc.parquet_io()
        cols = {"findings": lc.findings_columns(), "corpus": lc.corpus_columns(),
                "citation_edges": lc.edges_columns(), "claims": lc.claims_columns()}[table]
        blob = write([change(dict(r)) for r in read(latest.read_bytes())], cols)
        name = f"{table}_v{int(latest.stem.rsplit('_v', 1)[1]) + 1}.parquet"
        (data / name).write_bytes(blob)
        self.append_row(data / "MANIFEST.jsonl", {"kind": "lit_corpus", "command": "forged", "exit_code": 0, "artifacts": [
            {"table": table, "name": name, "path": f"data/{name}", "sha256": lv.sha256_bytes(blob)}]})

    def test_forged_verify_rows_fail_closed(self):
        lc = lv.report_lc()
        p = lc.DEMO_PAPERS[0]
        work = dict(lc.demo_work_json(p), display_name="A Completely Different Paper on Dentistry")
        lc.demo_verify_row(str(self.pd), p, verdict="MISMATCH", work=work)
        man = self.pd / "lit_search" / "verify" / "MANIFEST.jsonl"
        genuine = json.loads(man.read_text().splitlines()[-1])
        forged = self.append_row(man, dict(genuine, verdict="CONFIDENT"))          # the raw is untouched
        baker_raw = [json.loads(x) for x in man.read_text().splitlines()][1]       # another paper's verify row
        no_record = self.append_row(man, dict(baker_raw, verdict="CONFIDENT"))
        for sha in (forged, no_record):
            with self.subTest(sha=sha[:8]):
                self.forge_table("corpus", lambda r: dict(r, verify_row_sha256=sha, verify_verdict="CONFIDENT",
                                                          citation_status="verified_rule")
                                 if r["paper_key"] == p["key"] else r)
                code, check, _ = self.report(f"v{sha[:6]}.md", "Tutoring helps [@fixture-allen2019tutoring].\n")
                self.assertEqual((code, check["verdict"]), (11, "FAIL"))
                self.assertIn("CITATION_UNVERIFIED", {it["status"] for it in check["items"]})
        # the attach path re-grades too: the forged CONFIDENT row records MISMATCH, not citable
        mp = self.pd / "inputs" / "forged_verify.jsonl"
        mp.write_text(json.dumps({"row_sha256": forged, "paper_key": p["key"]}) + "\n")
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
            self.assertEqual(lc.run(["attach", "verify", str(self.pd), str(mp)]), 0)
        self.assertIn("re-grades to MISMATCH", out.getvalue())

    def test_forged_retraction_row_fails_closed(self):
        lc = lv.report_lc()
        p = lc.DEMO_PAPERS[0]
        sha = lc.demo_retractions_row(str(self.pd), [(p["doi"], "retracted")], row_statuses=[(p["doi"], "none")])
        self.forge_table("corpus", lambda r: dict(r, retraction_json=json.dumps({"status": "none", "row_sha256": sha}))
                         if r["paper_key"] == p["key"] else r)
        code, check, _ = self.report("r.md", "Tutoring helps [@fixture-allen2019tutoring].\n")
        self.assertEqual((code, check["verdict"]), (11, "FAIL"))
        self.assertIn("RETRACTED_CITED", {it["status"] for it in check["items"]})
        # 1.12.0 (C2-B2): pointing the record at a check whose response names ANOTHER DOI hides nothing: the newest
        #   check that answers this DOI still decides, and the record is flagged as not naming it
        empty = lc.demo_retractions_row(str(self.pd), [("10.9999/other", "none")], row_statuses=[(p["doi"], "none")])
        self.forge_table("corpus", lambda r: dict(r, retraction_json=json.dumps({"status": "none", "row_sha256": empty}))
                         if r["paper_key"] == p["key"] else r)
        code, check, _ = self.report("r2.md", "Tutoring helps [@fixture-allen2019tutoring].\n")
        got = {it["status"] for it in check["items"]}
        self.assertTrue({"RETRACTED_CITED", "RETRACTION_CHECK_NOT_LATEST_DRAFT"} <= got, got)

    def forge_rows(self, table, fn):
        # A new version of `table` holding fn(rows), plus a consistent data MANIFEST row.
        lc = lv.report_lc()
        data = self.pd / "data"
        latest = max(data.glob(f"{table}_v*.parquet"), key=lambda p: int(p.stem.rsplit("_v", 1)[1]))
        read, write = lc.parquet_io()
        cols = {"claims": lc.claims_columns(), "corpus": lc.corpus_columns()}[table]
        blob = write(fn([dict(r) for r in read(latest.read_bytes())]), cols)
        name = f"{table}_v{int(latest.stem.rsplit('_v', 1)[1]) + 1}.parquet"
        (data / name).write_bytes(blob)
        self.append_row(data / "MANIFEST.jsonl", {"kind": "lit_corpus", "command": "forged", "exit_code": 0, "artifacts": [
            {"table": table, "name": name, "path": f"data/{name}", "sha256": lv.sha256_bytes(blob)}]})

    def statuses_by_claim(self, check):
        return {(it["status"], cid) for it in check["items"] for cid in it.get("claim_ids") or [None]}

    def test_abstract_rows_are_rebuilt_from_the_abstract(self):
        # C2-B1: an abstract claim row is rebuilt with abstract_claim_row; stored extra fields clear nothing.
        lc = lv.report_lc()
        allen = lc.DEMO_PAPERS[0]["key"]
        mp = self.pd / "inputs" / "abstract_claims.jsonl"
        mp.write_text(json.dumps({"paper_key": allen, "quote": "An invented abstract.", "claim_type": "finding"}) + "\n")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(lc.run(["claims", "abstract", str(self.pd), str(mp)]), 0)
        quant = json.dumps({"estimate": {"raw": "0.50", "value": "0.50", "status": "QUANT_OK"},
                            "metric": lc.DEMO_METRIC})

        def forge(rows):
            g = next(r for r in rows if r["claim_id"] == f"{allen}-a01")
            return rows + [
                dict(g, claim_id=f"{allen}-a90", quant_json=quant, metric=lc.DEMO_METRIC.lower(), estimate="0.50"),
                dict(g, claim_id=f"{allen}-a91", claim_type="citation_use", cites_key="user_f1c70002",
                     citation_relation="disputes"),
                dict(g, claim_id=f"{allen}-a92", claim_type="appraisal", quote="invented",
                     quote_sha256=lv.sha256_bytes(b"invented")),
                # the source names a different identifier: the quote is allen's, the row names baker
                dict(g, claim_id="user_f1c70002-a93", paper_key="user_f1c70002", citekey="fixture-baker2020reading")]
        self.forge_rows("claims", forge)
        code, check, _ = self.report("ab.md", "Tutoring helps [@fixture-allen2019tutoring].\n")
        got = self.statuses_by_claim(check)
        for cid in (f"{allen}-a90", f"{allen}-a91", f"{allen}-a92", "user_f1c70002-a93"):
            self.assertIn(("CLAIM_ROW_MISMATCH", cid), got)
        self.assertNotIn(("CLAIM_ROW_MISMATCH", f"{allen}-a01"), got)          # the genuine row is rebuilt equal
        self.assertEqual(code, 11)

    def test_abstract_row_differing_only_from_the_rebuild_fails(self):
        # C2-B1 (F1b mutation a1): a row that passes every explicit guard (type, length, quote, empty fields) but
        #   claims a full-text grade differs only from the rebuilt row; using the stored row would let it count as
        #   full-text evidence. The comparison with the rebuilt row must catch it.
        lc = lv.report_lc()
        allen = lc.DEMO_PAPERS[0]["key"]
        mp = self.pd / "inputs" / "abstract_claims.jsonl"
        mp.write_text(json.dumps({"paper_key": allen, "quote": "An invented abstract.", "claim_type": "finding"}) + "\n")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(lc.run(["claims", "abstract", str(self.pd), str(mp)]), 0)

        def forge(rows):
            g = next(r for r in rows if r["claim_id"] == f"{allen}-a01")
            return rows + [dict(g, claim_id=f"{allen}-a94", evidence_grade="FULL_TEXT_VERIFIED")]
        self.forge_rows("claims", forge)
        code, check, _ = self.report("ab2.md", "Tutoring helps [@fixture-allen2019tutoring].\n")
        got = self.statuses_by_claim(check)
        self.assertIn(("CLAIM_ROW_MISMATCH", f"{allen}-a94"), got)
        self.assertNotIn(("CLAIM_ROW_MISMATCH", f"{allen}-a01"), got)
        self.assertEqual(code, 11)

    def test_paper_identity_is_rederived(self):
        # C2-B2: a corpus DOI pointed at another paper (the source names a different identifier) fails closed.
        lc = lv.report_lc()
        a, b = lc.DEMO_PAPERS[0], lc.DEMO_PAPERS[1]
        self.forge_table("corpus", lambda r: dict(r, doi=b["doi"]) if r["paper_key"] == a["key"] else r)
        code, check, _ = self.report("id.md", "Tutoring helps [@fixture-allen2019tutoring].\n")
        got = {(it["status"], tuple(it["citekeys"])) for it in check["items"]}
        self.assertIn(("PAPER_IDENTITY_MISMATCH", ("fixture-allen2019tutoring",)), got)
        self.assertIn(("CITATION_UNVERIFIED", ("fixture-allen2019tutoring",)), got)
        self.assertEqual(code, 11)

    def test_newest_retraction_check_decides_and_attach_never_goes_back(self):
        # C2-B2: a newer check that is not attached: review in a draft, fail at final; attach refuses an older one.
        lc = lv.report_lc()
        p = lc.DEMO_PAPERS[0]
        old = json.loads(self.pd.joinpath("inputs", "retractions_map.jsonl").read_text().splitlines()[0])["row_sha256"]
        new = lc.demo_retractions_row(str(self.pd), [(p["doi"], "retracted")])
        code, check, _ = self.report("n1.md", "Tutoring helps [@fixture-allen2019tutoring].\n")
        self.assertTrue({"RETRACTED_CITED", "RETRACTION_CHECK_NOT_LATEST_DRAFT"} <= {i["status"] for i in check["items"]})
        code, check, _ = self.report("n2.md", "Tutoring helps [@fixture-allen2019tutoring].\n", "--kind", "final",
                                     "--no-recheck-cards")
        self.assertIn("RETRACTION_CHECK_NOT_LATEST", {i["status"] for i in check["items"]})
        for sha, want in ((new, 0), (old, 11)):
            mp = self.pd / "inputs" / f"retr_{sha[:6]}.jsonl"
            mp.write_text(json.dumps({"row_sha256": sha, "paper_key": p["key"]}) + "\n")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(lc.run(["attach", "retractions", str(self.pd), str(mp)]), want)
        code, check, _ = self.report("n3.md", "Tutoring helps [@fixture-allen2019tutoring].\n")
        got = {i["status"] for i in check["items"]}
        self.assertIn("RETRACTED_CITED", got)
        self.assertNotIn("RETRACTION_CHECK_NOT_LATEST_DRAFT", got)

    def test_reference_list_must_be_the_export(self):
        # C2-QW4: a second field, a second entry, an edited entry, an entry naming another verify row (the source
        #   names a different identifier) or an entry for no paper all fail.
        out = self.pd / "output"
        genuine = (out / "references_v1.bib").read_text()
        ck = "fixture-chen2021library"
        entry = re.search(r"(?ms)^@\w+\{" + re.escape(ck) + r",\n.*?^\}\n", genuine).group(0)
        other_sha = re.search(r"(?m)^  daaf_verify_row_sha256 = \{(\w+)\}", genuine.replace(entry, "")).group(1)
        variants = {
            "second title": genuine.replace(entry, entry.replace("  year =", "  title = {A Forged Title},\n  year =")),
            "second entry": genuine.replace(entry, entry.replace("Library Hours", "Forged Hours") + "\n" + entry),
            # F1b (mutation e2): the genuine entry FIRST, a forged one after it (the one Pandoc renders)
            "second entry after": genuine.replace(entry, entry + "\n" + entry.replace("Library Hours", "Forged Hours")),
            "text outside the entries": genuine + "\n@string{forged = {Forged Hours}}\n",
            "edited title": genuine.replace(entry, entry.replace("Library Hours", "Forged Hours")),
            "other verify row": genuine.replace(entry, re.sub(r"daaf_verify_row_sha256 = \{\w+\}",
                                                              "daaf_verify_row_sha256 = {" + other_sha + "}", entry)),
            "entry for no paper": genuine + "\n" + entry.replace(ck, "nosuch2020paper"),
            # polish pass H (round-G re-review W4, mutant R2): the header line must be export-bib's exactly
            "text on the header line": genuine.replace("verified records only\n", "verified records only; "
                                                       "title = {Forged Hours}\n", 1),
        }
        for n, (name, text) in enumerate(variants.items(), 2):
            with self.subTest(name):
                self.assertNotEqual(text, genuine)
                bib = out / f"references_v{n}.bib"
                bib.write_text(text)
                self.append_row(self.pd / "data" / "MANIFEST.jsonl", {
                    "kind": "lit_corpus", "command": "forged", "exit_code": 0, "artifacts": [
                        {"table": None, "name": bib.name, "path": f"output/{bib.name}",
                         "sha256": lv.sha256_bytes(text.encode("utf-8"))}]})
                code, check, _ = self.report(f"b{n}.md", f"Tutoring helps [@{ck}].\n")
                got = {i["status"] for i in check["items"]}
                self.assertEqual(code, 11, got)
                self.assertIn("BIB_ENTRY_MISMATCH", got)

    def test_forged_findings_and_edges_fail_closed(self):
        def finding(r):
            if r["finding_id"] == "F01":
                ds = json.loads(r["descriptive_summary_json"])
                return dict(r, descriptive_summary_json=json.dumps(dict(ds, median="0.16")))
            if r["finding_id"] == "F02":
                return dict(r, certainty_scheme="researcher_grade", certainty="high", certainty_reason="trust me",
                            not_rated_reason=None)
            return r
        self.forge_table("findings", finding)
        self.forge_table("citation_edges", lambda r: dict(r, reader_relation="disputes"))
        code, check, _ = self.report("f.md", "[The interview study disputes the tutoring trial]{.lr-edge edges=\"E001\"} "
                                     "[@fixture-diaz2022teachers; @fixture-allen2019tutoring].\n")
        got = {it["status"] for it in check["items"]}
        self.assertEqual(code, 11)
        for s in ("SUMMARY_REDERIVE_MISMATCH", "FINDING_RULE_FAILED", "EDGE_ROW_MISMATCH", "EDGE_RELATION_UNSUPPORTED"):
            self.assertIn(s, got)
        self.assertNotIn("EDGE_OK", got)

    def test_final_with_an_older_pinned_table_fails(self):
        with mock.patch.dict(lv.SYNTHETIC_SOURCES, clear=True):
            code, check, _ = self.report("p.md", "Tutoring helps [@fixture-allen2019tutoring].\n", "--kind", "final",
                                         "--data-version", "corpus=1")
        self.assertIn("PINNED_OLDER_VERSION", {it["status"] for it in check["items"]})
        code, check, _ = self.report("p2.md", "Tutoring helps [@fixture-allen2019tutoring].\n", "--data-version",
                                     "corpus=1")
        self.assertNotIn("PINNED_OLDER_VERSION", {it["status"] for it in check["items"]})


@unittest.skipUnless(CAN_RUN_CLI, CLI_WHY)
class ReportRecheckForgeryTests(ScratchCase):
    # Q-B1: a card_check edited in ONE quant item (verdict kept) must not clear a summary under --kind final.
    def test_quant_only_card_check_edit_fails_final(self):
        lc = lv.report_lc()
        pd = self.root / "review"
        pd.mkdir()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            demo = lc.build_demo(str(pd))
        self.assertEqual([n for n, c, _ in demo["steps"] if c], [])
        p = lc.DEMO_PAPERS[2]
        claims = [dict(p["claims"][0], quant=dict(p["claims"][0]["quant"], estimate="0.031"))] + p["claims"][1:]
        kdir = pd / "papers" / p["key"]
        card = kdir / "evidence_card_a.md"
        card.write_text(lc.demo_card(p, claims))
        self.assertEqual(run_main(["card", kdir, card])[0], 11)                  # genuine: not one of its numbers
        man = pd / "papers" / "MANIFEST.jsonl"
        last = [r for r in rows_of(pd / "papers") if r.get("command") == "card"][-1]
        cc = json.loads((kdir / last["artifacts"]["card_check"]["name"]).read_text())
        flipped = 0
        for it in cc["items"]:
            if it["kind"] == "claim_quant" and it["status"] == "QUANT_NOT_IN_NUMBERS":
                it.update(status="QUANT_OK", severity="pass")
                flipped += 1
        self.assertEqual(flipped, 1)
        data = json.dumps(cc).encode("utf-8")
        (kdir / "card_check_forged.json").write_bytes(data)
        ReportOnDiskTests.append_row(man, dict(last, artifacts={"card_check": {
            "name": "card_check_forged.json", "bytes": len(data), "sha256": lv.sha256_bytes(data)}}))
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(lc.run(["claims", "build", str(pd)]), 0)
        ctx = {"pd": os.path.realpath(pd), "data": str(pd / "data"), "read": lc.parquet_io()[0], "cache": {},
               "row": {"inputs": []}}
        rows, _ = lc.load_table(ctx, "claims")
        chen = next(r["claim_id"] for r in rows if r["paper_key"] == p["key"] and r["card_claim_id"] == "S1"
                    and r["status"] == "current")
        f09 = {"finding_id": "F09", "statement": "s", "claim_ids": ["user_f1c70001-c01", "user_f1c70002-c01", chen],
               "synthesis_method": "swim", "certainty_scheme": "stated", "certainty": "low",
               "certainty_reason": f"rests on {chen}", "decided_by": {"role": "synthesizer"}, "moderator_status": "none",
               "descriptive_summary": {"claim_ids": ["user_f1c70001-c01", "user_f1c70002-c01", chen],
                                       "metric": lc.DEMO_METRIC}}
        fp = pd / "inputs" / "f09.jsonl"
        fp.write_text(json.dumps(f09) + "\n")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(lc.run(["findings", "record", str(pd), str(fp)]), 0)   # the forgery reached the table
        memo = pd / "output" / "m.md"
        memo.write_text("Tutoring helps [@allen2019tutoring].\n")
        code, _, _ = run_main(["report", pd, memo, "--kind", "final"])
        check = json.loads((pd / "output" / rows_of(pd / "output")[-1]["artifacts"]["report_check"]["name"]).read_text())
        got = {(it["status"], it.get("finding_id")) for it in check["items"]}
        self.assertEqual(code, 11)
        self.assertIn(("SUMMARY_REDERIVE_MISMATCH", "F09"), got)
        self.assertIn("CARD_RECHECK_DIFFERS", {s for s, _ in got})

    def demo(self):
        lc = lv.report_lc()
        pd = self.root / "review"
        pd.mkdir()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            demo = lc.build_demo(str(pd))
        self.assertEqual([n for n, c, _ in demo["steps"] if c], [])
        return lc, pd

    def forge_claims(self, pd, fn):
        lc = lv.report_lc()
        data = pd / "data"
        latest = max(data.glob("claims_v*.parquet"), key=lambda p: int(p.stem.rsplit("_v", 1)[1]))
        read, write = lc.parquet_io()
        blob = write(fn([dict(r) for r in read(latest.read_bytes())]), lc.claims_columns())
        name = f"claims_v{int(latest.stem.rsplit('_v', 1)[1]) + 1}.parquet"
        (data / name).write_bytes(blob)
        ReportOnDiskTests.append_row(data / "MANIFEST.jsonl", {"kind": "lit_corpus", "command": "forged", "exit_code": 0,
                                                               "artifacts": [{"table": "claims", "name": name,
                                                                              "sha256": lv.sha256_bytes(blob)}]})

    def report_items(self, pd, text, *args):
        memo = pd / "output" / f"m{uuid.uuid4().hex[:6]}.md"
        memo.write_text(text)
        code, _, _ = run_main(["report", pd, memo, *args])
        check = json.loads((pd / "output" / rows_of(pd / "output")[-1]["artifacts"]["report_check"]["name"]).read_text())
        return code, {(it["status"], cid) for it in check["items"] for cid in it.get("claim_ids") or [None]}

    def test_unused_forged_claim_row_is_caught(self):
        # q-I1 (mutant M1): the withdrawn wrong-page claim set to current and verified, NOT used by the memo, is
        #   still reported (CLAIM_VERIFICATION_FORGED) and, naming an older card run, CLAIM_ROW_MISMATCH.
        lc, pd = self.demo()
        target = []

        def forge(rows):
            for r in rows:
                if r["paper_key"] == "user_f1c70001" and r["card_claim_id"] == "C9":
                    r.update(status="current", verification="verified", superseded_by=None)
                    target.append(r["claim_id"])
            return rows
        self.forge_claims(pd, forge)
        self.assertEqual(len(target), 1)
        code, got = self.report_items(pd, "Tutoring helps [@allen2019tutoring].\n")
        self.assertEqual(code, 11)
        self.assertIn(("CLAIM_VERIFICATION_FORGED", target[0]), got)
        self.assertIn(("CLAIM_ROW_MISMATCH", target[0]), got)

    def test_withdrawn_claim_revived_by_status_edit_fails(self):
        # C2-QW3: chen's newer card drops S1, claims build withdraws it; a one-field status edit cannot revive it
        #   (the row names an older card run than the paper's latest: the source names a different check).
        lc, pd = self.demo()
        p = lc.DEMO_PAPERS[2]
        p["papers"] = str(pd / "papers")
        steps = []
        lc.demo_card_run(steps, p, p["claims"][1:], "_a")
        self.assertEqual([c for _, c, _ in steps], [0])
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(lc.run(["claims", "build", str(pd)]), 0)
        revived = []

        def forge(rows):
            for r in rows:
                if r["paper_key"] == p["key"] and r["card_claim_id"] == "S1" and r["status"] == "superseded":
                    r.update(status="current", superseded_by=None)
                    revived.append(r["claim_id"])
            return rows
        self.forge_claims(pd, forge)
        self.assertEqual(len(revived), 1)
        code, got = self.report_items(pd, "Library hours may matter [@chen2021library].\n", "--kind", "final")
        self.assertEqual(code, 11)
        self.assertIn(("CLAIM_ROW_MISMATCH", revived[0]), got)

    def test_genuine_final_report_passes(self):
        lc, pd = self.demo()
        text = ("[Small-group tutoring probably raises reading scores]"
                '{.lr-finding fid=F01 claims="user_f1c70001-c01 user_f1c70002-c01"} '
                "[@allen2019tutoring; @baker2020reading].\n\n"
                "[Across 3 studies reporting SD units of reading score, the estimates ranged from 0.09 to 0.21 (median "
                "0.15; IQR 0.12 to 0.18; descriptive summary, not a pooled estimate)]"
                '{.lr-finding fid=F01 claims="user_f1c70001-c01 user_f1c70002-c01 user_f1c70003-c01"} '
                "[@allen2019tutoring; @baker2020reading; @chen2021library].\n")
        code, got = self.report_items(pd, text, "--kind", "final")
        self.assertEqual(code, 0, sorted(got))
        self.assertFalse({s for s, _ in got} & {"PAPER_IDENTITY_MISMATCH", "BIB_ENTRY_MISMATCH", "CLAIM_ROW_MISMATCH",
                                                "RETRACTION_CHECK_NOT_LATEST"})


@unittest.skipUnless(CAN_RUN_CLI, CLI_WHY)
class IdentityHistoryTests(ScratchCase):
    # Round G1 (review cycle 3 B1, W1, W6, consistency W2): identity comes from the table history, never from a
    #   corpus field; each forgery below would PASS if the one defence it targets were removed.
    GENUINE = ("[Small-group tutoring probably raises reading scores]"
               '{.lr-finding fid=F01 claims="user_f1c70001-c01 user_f1c70002-c01"} '
               "[@allen2019tutoring; @baker2020reading].\n")

    def setUp(self):
        super().setUp()
        self.lc = lv.report_lc()
        self.pd = self.root / "review"
        self.pd.mkdir()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            demo = self.lc.build_demo(str(self.pd))
        self.assertEqual([n for n, c, _ in demo["steps"] if c], [])
        self.a = self.lc.DEMO_PAPERS[0]
        self.evans = {"doi": "10.9999/fixture.0005", "title": "An Invented Survey of Adult Reading Clubs",
                      "authors": ["Eve Evans"], "year": 2018, "w": "W900000005"}

    def run_lc(self, *argv, **kw):
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
            code = self.lc.run([str(x) for x in argv], **kw)
        return code, out.getvalue()

    def versions(self):
        return sorted((self.pd / "data").glob("corpus_v*.parquet"), key=lambda p: int(p.stem.rsplit("_v", 1)[1]))

    def rows(self, path=None):
        return [dict(r) for r in self.lc.parquet_io()[0]((path or self.versions()[-1]).read_bytes())]

    def write_version(self, rows, row_extra, name=None):
        # A corpus version (new, or an existing file rewritten) plus one appended data MANIFEST row naming it.
        name = name or f"corpus_v{len(self.versions()) + 1}.parquet"
        blob = self.lc.parquet_io()[1](rows, self.lc.corpus_columns())
        path = self.pd / "data" / name
        if path.exists():
            os.chmod(path, 0o644)
        path.write_bytes(blob)
        ReportOnDiskTests.append_row(self.pd / "data" / "MANIFEST.jsonl", dict(
            {"kind": "lit_corpus", "command": "forged", "exit_code": 0, "artifacts": [
                {"table": "corpus", "name": name, "path": f"data/{name}", "sha256": lv.sha256_bytes(blob)}]},
            **row_extra))

    def evans_identity(self, r):
        ev = next(x for x in self.rows() if x["paper_key"] == self.evans["w"])
        return dict(r, **{k: ev[k] for k in ("found_by_json", "doi", "title", "abstract", "authors_json", "year",
                                             "venue", "type")})

    def legit_cite(self, key, p):
        # Only real commands: verify and retraction checks of p's DOI attached to `key`, then export-bib.
        v, r = self.lc.demo_verify_row(str(self.pd), p), self.lc.demo_retractions_row(str(self.pd), [(p["doi"], "none")])
        for kind, sha in (("verify", v), ("retractions", r)):
            mp = self.pd / "inputs" / f"g1_{kind}_{sha[:6]}.jsonl"
            mp.write_text(json.dumps({"row_sha256": sha, "paper_key": key}) + "\n")
            self.assertEqual(self.run_lc("attach", kind, self.pd, mp)[0], 0)
        self.assertEqual(self.run_lc("export-bib", self.pd)[0], 0)

    def report(self, text, *args):
        memo = self.pd / "output" / f"m{uuid.uuid4().hex[:6]}.md"
        memo.write_text(text)
        code, _, _ = run_main(["report", self.pd, memo, *args])
        check = json.loads((self.pd / "output" / rows_of(self.pd / "output")[-1]["artifacts"]["report_check"]["name"])
                           .read_text())
        for it in check["items"]:                       # consistency I5: plain reasons, no field names or states
            self.assertNotRegex(it["reason"] + " " + it["fix"], r"\b[A-Z]+_[A-Z_]{3,}\b|state: |\bdoi, |found_by|"
                                r"add-record run|\{\.lr-|fid=")
        return code, {(it["status"], ck) for it in check["items"] for ck in it.get("citekeys") or [None]}, check

    def test_found_by_swap_to_another_search_record_fails(self):
        # B1 (reviewer probe 01 I1; mutant m1's target): allen keeps its key, cards and claims but takes evans's search
        #   record and identity fields; legit verify, retraction check and export follow. The history says allen was
        #   added by its own add-record run, so the swap fails closed at every kind.
        self.write_version([self.evans_identity(r) if r["paper_key"] == self.a["key"] else r for r in self.rows()], {})
        self.legit_cite(self.a["key"], self.evans)
        for kind in ("synthesis", "final"):
            code, got, _ = self.report(self.GENUINE, "--kind", kind)
            self.assertEqual(code, 11, kind)
            self.assertIn(("PAPER_IDENTITY_MISMATCH", "allen2019tutoring"), got)
        # the search record names a different identifier: evans's corpus DOI pointed at allen's
        self.write_version([dict(r, doi=self.a["doi"]) if r["paper_key"] == self.evans["w"] else r
                            for r in self.rows()], {})
        _, got, _ = self.report("Text.\n")
        self.assertIn(("PAPER_IDENTITY_MISMATCH", "evans2018invented"), got)

    def test_appended_add_record_row_does_not_move_identity(self):
        # B1 (mutant m2's target): a genuine second add-record of allen (same DOI, another title) merges and changes
        #   nothing; a forged appended add-record row naming allen with evans's details cannot re-point it.
        pdf = self.pd / "papers" / self.a["key"] / "ingest_manifest.json"
        self.assertEqual(self.run_lc("add-record", self.pd, "--user-pdf", pdf, "--title", "Tutoring small groups, a "
                                     "second copy", "--doi", self.a["doi"], "--round", "2")[0], 0)
        self.assertEqual(self.run_lc("export-bib", self.pd)[0], 0)
        code, got, _ = self.report(self.GENUINE)
        self.assertNotIn("PAPER_IDENTITY_MISMATCH", {s for s, _ in got})
        self.write_version([self.evans_identity(r) if r["paper_key"] == self.a["key"] else r for r in self.rows()],
                           {"command": "add-record", "paper_key": self.a["key"],
                            "parameters": {"doi": self.evans["doi"], "title": self.evans["title"]}})
        self.legit_cite(self.a["key"], self.evans)
        code, got, _ = self.report(self.GENUINE)
        self.assertEqual(code, 11)
        self.assertIn(("PAPER_IDENTITY_MISMATCH", "allen2019tutoring"), got)

    def test_rewritten_history_fails(self):
        # B1: every earlier corpus version rewritten without allen and re-recorded by an appended row, then a forged
        #   add-record row adds allen back with evans's details. The FIRST record of each file counts, so the
        #   rewritten history fails (with "last record wins" this forgery would pass).
        latest = self.rows()
        for p in self.versions():
            self.write_version([r for r in self.rows(p) if r["paper_key"] != self.a["key"]], {}, name=p.name)
        self.write_version([self.evans_identity(r) if r["paper_key"] == self.a["key"] else r for r in latest],
                           {"command": "add-record", "paper_key": self.a["key"],
                            "parameters": {"doi": self.evans["doi"], "title": self.evans["title"]}})
        self.legit_cite(self.a["key"], self.evans)
        code, got, _ = self.report(self.GENUINE)
        self.assertEqual(code, 11)
        self.assertIn("TABLE_HASH_MISMATCH", {s for s, _ in got})

    def test_one_creating_record_one_paper_key(self):
        # B1: a second paper key claiming allen's creating record (a copy of its row under a DOI-chain key, written
        #   by a forged add-record row that names allen) fails: a step adds only the paper it names.
        # (no abstract: the abstract-history check would otherwise catch the copy before this rule; mutation run 1)
        dup = dict(next(r for r in self.rows() if r["paper_key"] == self.a["key"]), paper_key="doi_0badf00d",
                   citekey="dup2019tutoring", abstract=None)
        self.write_version(self.rows() + [dup], {"command": "add-record", "paper_key": self.a["key"], "parameters": {
            "doi": self.a["doi"], "title": self.a["title"]}})
        self.legit_cite("doi_0badf00d", self.a)
        code, got, _ = self.report("## Further reading\n\n- A study of small-group tutoring [@dup2019tutoring].\n")
        self.assertEqual(code, 11)
        self.assertIn(("PAPER_IDENTITY_MISMATCH", "dup2019tutoring"), got)
        # the same copy added by a step that never adds papers (any other command) fails too
        dup2 = dict(dup, paper_key="doi_0badf00e", citekey="dup2019tutoringb")
        self.write_version(self.rows() + [dup2], {})
        self.legit_cite("doi_0badf00e", self.a)
        code, got, _ = self.report("## Further reading\n\n- A study of small-group tutoring [@dup2019tutoringb].\n")
        self.assertEqual(code, 11)
        self.assertIn(("PAPER_IDENTITY_MISMATCH", "dup2019tutoringb"), got)

    def test_newer_partial_retraction_check_never_lowers_the_status(self):
        # W1: an older full check finds a retraction; a newer check where OpenAlex failed says none. attach records
        #   the most severe status and says so; the report agrees (RETRACTED_CITED at final).
        doi = self.a["doi"]
        old = self.lc.demo_retractions_row(str(self.pd), [(doi, "retracted")])
        reqs = [{"backend": "openalex", "endpoint": "x", "response": None, "error": "HTTP 503 (synthetic)"},
                {"backend": "crossref", "endpoint": "https://api.crossref.org/works",
                 "params": {"filter": "updates:" + doi}, "response": {"message": {"items": []}}}]
        new = self.lc.demo_search_row(str(self.pd), "verify", "retractions", doi, [], sidecar=False, raw_requests=reqs,
                                      row_extra={"retractions": [{"doi": doi, "status": "none"}],
                                                 "failed_backends": ["openalex"], "timestamp": "2026-11-01T09:00:00Z"})
        self.assertNotEqual(old, new)
        mp = self.pd / "inputs" / "g1_newer.jsonl"
        mp.write_text(json.dumps({"row_sha256": new, "paper_key": self.a["key"]}) + "\n")
        code, out = self.run_lc("attach", "retractions", self.pd, mp)
        self.assertEqual(code, 0)
        self.assertIn("most severe", out)
        row = next(r for r in self.rows() if r["paper_key"] == self.a["key"])
        self.assertEqual(json.loads(row["retraction_json"])["status"], "retracted")
        code, got, _ = self.report(self.GENUINE, "--kind", "final")
        self.assertEqual(code, 11)
        self.assertIn(("RETRACTED_CITED", "allen2019tutoring"), got)
        self.assertNotIn("RETRACTION_CHECK_NOT_LATEST", {s for s, _ in got})

    def add_and_screen(self, pdf, title, authors, year, doi, name):
        # A user PDF added with legit commands (add-record, then included at screening); returns (key, citekey).
        code, out = self.run_lc("add-record", self.pd, "--user-pdf", pdf, "--title", title, "--authors", authors,
                                "--year", year, "--doi", doi, "--round", "2")
        self.assertEqual(code, 0, out)
        key = out.split("add-record: ")[1].split(" ")[0]
        sp = self.pd / "inputs" / f"{name}_screen.jsonl"
        sp.write_text(json.dumps({"paper_key": key, "stage": "ta", "pass": "primary", "decision": "include",
                                  "screener": {"agent": "t", "model_id": "t"}}) + "\n")
        self.assertEqual(self.run_lc("screen", "record", self.pd, sp)[0], 0)
        return key, next(r["citekey"] for r in self.rows() if r["paper_key"] == key)

    def test_corpus_title_must_match_the_verified_record(self):
        # W6 (reviewer probe 01 Q1, legit commands only): a user PDF titled X is added with a DOI whose record is Y,
        #   and the reference check is run with Y's title. Polish pass H (round-G re-review W1, I8): a draft shows a
        #   review item naming both titles; a final report fails the citation with the title rule's own reason and
        #   fix, never as a hand-edited reference list; running the check again cannot fix it; the fix's route
        #   (restore data/ from a backup made before the paper was added, add it again with its own DOI) passes.
        backup = self.root / "data_before_the_paper"
        shutil.copytree(self.pd / "data", backup)
        pdf = self.pd / "inputs" / "pilot.pdf"
        pdf.write_bytes(b"%PDF-1.4 synthetic placeholder (test only)\n")
        mine = "A Mentoring Pilot in Rural Schools"
        y = {"doi": "10.9999/fixture.0099", "title": "An Unrelated Study of Dental Hygiene in Adults",
             "authors": ["Zed Zane"], "year": 2015, "w": "W900000099"}
        key, ck = self.add_and_screen(pdf, mine, "Mo Moss", "2021", y["doi"], "g1")
        self.legit_cite(key, y)
        memo = f"## Further reading\n\n- A mentoring pilot in rural schools [@{ck}].\n"
        code, got, check = self.report(memo, "--kind", "synthesis")
        self.assertNotIn("CITATION_UNVERIFIED", {s for s, _ in got})
        it = next(i for i in check["items"] if i["status"] == "CITATION_TITLE_DIFFERS_DRAFT")
        self.assertIn(mine, it["reason"])
        self.assertIn(y["title"], it["reason"])
        self.assertEqual(it["fix"], lv.TITLE_REMEDY)
        code, got, check = self.report(memo, "--kind", "final")
        self.assertEqual(code, 11)
        self.assertIn(("CITATION_UNVERIFIED", ck), got)
        self.assertNotIn("BIB_ENTRY_MISMATCH", {s for s, _ in got})            # not a hand-edited reference list
        self.assertEqual(check["rederive"]["mismatches"], 0)
        it = next(i for i in check["items"] if i["status"] == "CITATION_UNVERIFIED")
        self.assertIn("the title recorded when this paper was added is not the title of the record its DOI leads to",
                      it["reason"])
        self.assertEqual(it["fix"], lv.TITLE_REMEDY)
        # the fix says running the reference check again will not help: run it with the paper's own title
        v = self.lc.demo_verify_row(str(self.pd), y, cited_title=mine)
        mp = self.pd / "inputs" / "h_verify_again.jsonl"
        mp.write_text(json.dumps({"row_sha256": v, "paper_key": key}) + "\n")
        self.assertEqual(self.run_lc("attach", "verify", self.pd, mp)[0], 0)
        self.assertEqual(self.run_lc("export-bib", self.pd)[0], 0)
        code, got, _ = self.report(memo, "--kind", "final")
        self.assertEqual(code, 11)
        self.assertIn(("CITATION_UNVERIFIED", ck), got)
        # the fix's route: restore data/ from the backup made before the paper was added, add it again with its own
        #   DOI and title, screen it, check its reference and retractions, export the reference list again
        for p in (self.pd / "data").rglob("*"):
            os.chmod(p, 0o755 if p.is_dir() else 0o644)
        shutil.rmtree(self.pd / "data")
        shutil.copytree(backup, self.pd / "data")
        z = {"doi": "10.9999/fixture.0098", "title": mine, "authors": ["Mo Moss"], "year": 2021, "w": "W900000098"}
        key2, ck2 = self.add_and_screen(pdf, mine, "Mo Moss", "2021", z["doi"], "h_again")
        self.legit_cite(key2, z)
        code, got, _ = self.report(f"## Further reading\n\n- A mentoring pilot in rural schools [@{ck2}].\n",
                                   "--kind", "final")
        self.assertEqual(code, 0, sorted(got))

    def test_partial_title_match_lowers_the_final_verdict(self):
        # Polish pass H (round-G re-review W4, mutant R3; reviewer probe 02 T-b): a title recorded without its
        #   subtitle matches the confirmed record only in part. A draft cites it; the final check asks for the
        #   researcher's decision (a partial match nobody accepted).
        pdf = self.pd / "inputs" / "tb.pdf"
        pdf.write_bytes(b"%PDF-1.4 synthetic tb (test only)\n")
        y = {"doi": "10.9999/fixture.0097", "title": "Small-Group Tutoring and Reading: Evidence from a Cluster "
             "Randomized Trial in Nine Schools", "authors": ["Pat Park"], "year": 2021, "w": "W900000097"}
        key, ck = self.add_and_screen(pdf, "Small-Group Tutoring and Reading", "Pat Park", "2021", y["doi"], "tb")
        self.legit_cite(key, y)
        memo = f"## Further reading\n\n- A tutoring study in nine schools [@{ck}].\n"
        code, got, _ = self.report(memo, "--kind", "synthesis")
        self.assertFalse({s for s, _ in got} & {"CITATION_WEAK_UNDECIDED", "CITATION_TITLE_DIFFERS_DRAFT"}, sorted(got))
        code, got, _ = self.report(memo, "--kind", "final")
        self.assertEqual(code, 11)
        self.assertIn(("CITATION_WEAK_UNDECIDED", ck), got)

    def test_new_key_on_an_already_ingested_search_row_fails(self):
        # Polish pass H (round-G re-review W4, mutant R1; reviewer probe 02 A2b): a forged ingest version re-lists a
        #   search row the previous search-log version already holds, with a new key in place of evans, and the new
        #   key copies evans's record. Only the rows an ingest ADDED count, so the new key first appears in a step
        #   whose saved results do not list it.
        data = self.pd / "data"
        read, write = self.lc.parquet_io()
        sv = max(data.glob("search_log_v*.parquet"), key=lambda p: int(p.stem.rsplit("_v", 1)[1]))
        srow = [dict(r) for r in read(sv.read_bytes())]
        old = next(r for r in srow if self.evans["w"] in (self.lc.jload(r["keys_json"], []) or []))
        target = "doi_0badbee1"
        relisted = dict(old, keys_json=self.lc.canon([target if k == self.evans["w"] else k
                                                       for k in self.lc.jload(old["keys_json"], [])]))
        srow = [r for r in srow if r["row_sha256"] != old["row_sha256"]] + [relisted]
        ev = next(r for r in self.rows() if r["paper_key"] == self.evans["w"])
        crow = sorted(self.rows() + [dict(ev, paper_key=target, citekey="evans2018inventedz", found_by_json="[]")],
                      key=lambda r: r["paper_key"])
        cname = f"corpus_v{len(self.versions()) + 1}.parquet"
        sname = f"search_log_v{int(sv.stem.rsplit('_v', 1)[1]) + 1}.parquet"
        cb, sb = write(crow, self.lc.corpus_columns()), write(srow, list(srow[0].keys()))
        (data / cname).write_bytes(cb)
        (data / sname).write_bytes(sb)
        ReportOnDiskTests.append_row(data / "MANIFEST.jsonl", {"kind": "lit_corpus", "command": "ingest", "exit_code": 0,
                                                               "artifacts": [
            {"table": "corpus", "name": cname, "path": f"data/{cname}", "sha256": lv.sha256_bytes(cb)},
            {"table": "search_log", "name": sname, "path": f"data/{sname}", "sha256": lv.sha256_bytes(sb)}]})
        sp = self.pd / "inputs" / "h_a2b_screen.jsonl"
        sp.write_text(json.dumps({"paper_key": target, "stage": "ta", "pass": "primary", "decision": "include",
                                  "screener": {"agent": "t", "model_id": "t"}}) + "\n")
        self.assertEqual(self.run_lc("screen", "record", self.pd, sp)[0], 0)
        self.legit_cite(target, self.evans)
        code, got, check = self.report("## Further reading\n\n- A survey of reading clubs [@evans2018inventedz, per "
                                       "abstract].\n", "--kind", "final")
        self.assertEqual(code, 11)
        it = next(i for i in check["items"] if i["status"] == "PAPER_IDENTITY_MISMATCH"
                  and "evans2018inventedz" in i["citekeys"])
        self.assertIn("a search step whose saved results do not list it", it["reason"])

    def test_table_remedies_pass(self):
        # Consistency W2: the fix text of a changed table names two remedies; both are run here and pass.
        backup = self.root / "data_backup"
        shutil.copytree(self.pd / "data", backup)
        self.write_version([dict(r, doi=self.lc.DEMO_PAPERS[1]["doi"]) if r["paper_key"] == self.a["key"] else r
                            for r in self.rows()], {})
        claims = max((self.pd / "data").glob("claims_v*.parquet"), key=lambda p: int(p.stem.rsplit("_v", 1)[1]))
        os.chmod(claims, 0o644)
        claims.write_bytes(claims.read_bytes() + b"\0")
        code, got, check = self.report(self.GENUINE)
        self.assertEqual(code, 11)
        fixes = {it["fix"] for it in check["items"] if it["status"] in ("TABLE_HASH_MISMATCH", "PAPER_IDENTITY_MISMATCH")}
        self.assertEqual(fixes, {lv.TABLE_REMEDY})
        # remedy 1: restore the data folder from the backup
        for p in (self.pd / "data").rglob("*"):
            os.chmod(p, 0o755 if p.is_dir() else 0o644)
        shutil.rmtree(self.pd / "data")
        shutil.copytree(backup, self.pd / "data")
        self.assertEqual(self.report(self.GENUINE)[0], 0)
        # remedy 2, followed as the text gives it (polish pass H, round-G re-review INFO): a new project folder with
        #   the saved searches, the papers and the input files; the lit_corpus commands that wrote a table re-run in
        #   the order data/MANIFEST.jsonl lists them (the copy made before the change), with the same input files;
        #   then export-bib. Every paper keeps its key. (build_demo set the demo's add-record keys with the test-only
        #   key override; a user's add-record key comes from the DOI or the file, so the recorded key stands in.)
        new = self.root / "rebuilt"
        new.mkdir()
        for d in ("lit_search", "papers", "inputs"):
            shutil.copytree(self.pd / d, new / d)
        old_pd, replayed = str(self.pd), []
        for line in (backup / "MANIFEST.jsonl").read_text().splitlines():
            row = json.loads(line) if line.strip() else {}
            if row.get("kind") != "lit_corpus" or row.get("exit_code") != 0 or \
                    not any(art.get("table") for art in row.get("artifacts") or []):
                continue
            prm = row.get("parameters") or {}
            argv = row["command"].split() + [str(new)] + ([prm["file"].replace(old_pd, str(new))] if prm.get("file")
                                                          else [])
            for k, v in prm.items():
                if k not in ("project_dir", "kind", "action", "file") and v is not None:
                    argv += ["--" + k.replace("_", "-"), str(v).replace(old_pd, str(new))]
            kw = {"key_override": row["paper_key"]} if row["command"] == "add-record" else {}
            self.assertEqual(self.run_lc(*argv, **kw)[0], 0, argv)
            replayed.append(row["command"])
        self.assertEqual(self.run_lc("export-bib", new)[0], 0)
        self.assertEqual(replayed[:5], ["add-record"] * 4 + ["ingest"])          # the recorded order, not another
        before = {r["paper_key"] for r in self.rows(max(backup.glob("corpus_v*.parquet"),
                                                         key=lambda p: int(p.stem.rsplit("_v", 1)[1])))}
        self.pd = new
        self.assertEqual({r["paper_key"] for r in self.rows()}, before)            # every paper keeps its key
        self.assertEqual(self.report(self.GENUINE)[0], 0)


class VerifyAliasTests(unittest.TestCase):
    # q-I3: a paper with no DOI and no W-id key is found in a verify response by its OpenAlex alias.
    def test_alias_match_and_a_different_work(self):
        lc = lv.report_lc()
        raw = json.dumps({"requests": [{"response": {"id": "https://openalex.org/W123", "display_name": "A Paper",
                                                     "publication_year": 2020}}]}).encode("utf-8")
        row = {"paper_key": "user_abcd1234", "doi": None}
        self.assertEqual(lc.verified_record(raw, row, ["W123"])["openalex"], "W123")
        self.assertIsNone(lc.verified_record(raw, row, ["W999"]))           # the alias names a different work
        self.assertIsNone(lc.verified_record(raw, row))
        self.assertIsNone(lc.verified_record(raw, dict(row, doi="10.1/x"), ["W123"]))   # a DOI decides when present


if __name__ == "__main__":
    unittest.main()
