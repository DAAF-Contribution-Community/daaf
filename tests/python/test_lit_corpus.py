"""Unit tests for scripts/lit_corpus.py (DAAF Literature Review corpus CLI, S4 D3).

The stdlib core (keys, citekeys, summaries, sign test, BibTeX/RIS escaping, finding rules, exit table) runs on
the bare CI runner; the round trip (the CLI's selftest on a synthetic project) needs rapidfuzz and polars or
pyarrow and is skipped without them. Every word and number in the fixtures is invented. Run file-first (FC10).
"""
import io
import os
import re
import shutil
import sys
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS))
import lit_corpus as lc  # noqa: E402

HAVE_FUZZ = lc.lv.try_import("rapidfuzz.fuzz") is not None
HAVE_PARQUET = lc.parquet_io()[0] is not None


class ExitTableTests(unittest.TestCase):
    @staticmethod
    def header_codes(text, start, stop):
        block = text.split(start, 1)[1].split(stop, 1)[0]
        return {int(m) for m in re.findall(r"(?m)^#\s{2,}(\d+)\s{2,}", block)}

    def test_three_copies_agree_and_3_is_unused(self):
        py = self.header_codes((_SCRIPTS / "lit_corpus.py").read_text(), "--- Exit code table", "# Titles, abstracts")
        sh = self.header_codes((_SCRIPTS / "lit_corpus.sh").read_text(), "# Exit codes are passed", "# Titles, abstr")
        desc = lc.build_parser().description.split("Exit codes:", 1)[1]
        argp = {int(m) for m in re.findall(r"(?:^|; )\s*(\d+) ", desc)}
        self.assertEqual(py, set(lc.EXIT_CODES))
        self.assertEqual((sh, argp), (py, py))
        self.assertNotIn(3, py)
        self.assertIn("3 is reserved", desc)

    def test_wrapper_versions_and_schemas(self):
        self.assertTrue(os.stat(_SCRIPTS / "lit_corpus.sh").st_mode & 0o111)
        self.assertEqual((lc.TOOL_VERSION, lc.CONTRACT_VERSION), ("1.3.0-daaf", "0.3.0"))
        # The certainty phrase table and its lockstep copy carry the same contract version.
        self.assertEqual(lc.lv.lrr.CERTAINTY_LANGUAGE["contract_version"], lc.CONTRACT_VERSION)
        self.assertEqual(lc.SCHEMAS["paper_notes"], "lit-paper-notes-v1")
        self.assertEqual(lc.RULE_VERSIONS["paperkey"], "paperkey-v1")
        self.assertIn("exec python3 \"$TOOL\" \"$@\"", (_SCRIPTS / "lit_corpus.sh").read_text())

    def test_usage_exits_1_and_guards_exit_2(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                lc.build_parser().parse_args(["ingest"])
        self.assertEqual(cm.exception.code, 1)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(lc.run(["counts", "/tmp"]), 2)
            self.assertEqual(lc.run(["counts", str(_REPO_ROOT / ".claude")]), 2)


class KeyAndCitekeyTests(unittest.TestCase):
    def test_paper_key_order_and_doi_collision(self):
        self.assertEqual(lc.new_key({"ids": {"openalex": ["https://openalex.org/W123"], "doi": ["10.1/x"]}}, {}),
                         "W123")
        k = lc.new_key({"doi": "https://doi.org/10.1/ABC"}, {})
        self.assertEqual(k, "doi_" + lc.hashlib.sha256(b"10.1/abc").hexdigest()[:8])
        self.assertNotEqual(lc.doi_key("10.1/abc", {k: "10.9/other"}), k)            # collision -> "#1"
        self.assertEqual(lc.new_key({"ids": {"eric": ["ED123456"]}}, {}), "eric_ED123456")
        self.assertTrue(lc.lv.PAPER_KEY_RE.match(lc.new_key({"ids": {"s2": ["abc"]}}, {})))

    def test_citekey_rules(self):
        self.assertEqual(lc.citekey_base("The Effects of Tutoring", ["Matthew A. Kraft"], 2019), "kraft2019effects")
        self.assertEqual(lc.citekey_base("A", [], None), "anonnduntitled")
        self.assertEqual(lc.citekey_base("Poverty in 2020", ["The World Bank"], 2020), "world2020poverty")
        self.assertEqual(lc.citekey_base("Über Lernen", ["Zoë Müller"], 2021), "muller2021uber")
        self.assertEqual(lc.citekey_for("kraft2019effects", {"kraft2019effects", "kraft2019effectsa"}),
                         "kraft2019effectsb")

    def test_stem_key_matches_scholar_search(self):
        self.assertEqual(lc.stem_key("Exploring Mechanisms of Effective Coaching: A Tale", ["Matthew Kraft"]),
                         "exploring mechanisms of effective coaching|kraft")
        self.assertIsNone(lc.stem_key("Short: title here", ["Kraft"]))


class SummaryTests(unittest.TestCase):
    def claims(self, metrics=("sd",) * 3, keys=("p1", "p2", "p3"), values=("0.21", "0.15", "0.09")):
        return {f"{k}-c01": {"paper_key": k, "metric": m, "verification": "verified", "evidence_grade": "FULL_TEXT_"
                             "VERIFIED", "numbers_status": "ok",
                             "quant_json": lc.canon({"estimate": {"value": v, "status": "QUANT_OK"}})}
                for k, m, v in zip(keys, metrics, values)}

    def test_descriptive_summary_needs_three_papers_one_metric(self):
        c, r = self.claims(), []
        ds = lc.descriptive_summary({"claim_ids": list(c), "metric": "SD"}, c, r, "w")
        self.assertEqual((r, ds["median"], ds["q1"], ds["q3"], ds["label"]),
                         ([], "0.15", "0.12", "0.18", "descriptive summary, not a pooled estimate"))
        r = []
        lc.descriptive_summary({"claim_ids": list(c)[:2], "metric": "sd"}, c, r, "w")
        self.assertTrue(any("at least 3" in x for x in r))
        r = []
        lc.descriptive_summary({"claim_ids": list(self.claims(keys=("p1", "p1", "p3"))), "metric": "sd"},
                               self.claims(keys=("p1", "p1", "p3")), r, "w")
        self.assertTrue(r)
        r, c = [], self.claims(metrics=("sd", "sd", "percent"))
        lc.descriptive_summary({"claim_ids": list(c), "metric": "sd"}, c, r, "w")
        self.assertTrue(any("metric" in x for x in r))

    def test_sign_test(self):
        st = lc.sign_test(10, 12)
        self.assertEqual((st["p_two_sided"], st["proportion"]), (0.038574, 0.833333))   # Cochrane ch.12: P = 0.039
        self.assertEqual([round(x, 2) for x in st["ci95"]], [0.55, 0.95])               # "(95% CI 55% to 95%)"

    def test_finding_rules(self):
        c = self.claims()
        base = {"finding_id": "F01", "statement": "s", "claim_ids": list(c), "synthesis_method": "swim",
                "certainty_scheme": "stated", "certainty": "moderate", "certainty_reason": "see p1-c01",
                "decided_by": {"role": "synthesizer"}, "moderator_status": "none"}
        self.assertEqual(lc.check_finding(base, c, {}, 1)[0], [])
        for change, frag in (({"pooled_estimate": "0.1"}, "pooled"), ({"weighted_mean": 1}, "pooled"),
                             ({"certainty_reason": ""}, "needs a certainty_reason"),
                             ({"certainty_reason": "no ids"}, "name at least one claim id"),
                             ({"certainty_scheme": "researcher_grade"}, "researcher_grade needs"),
                             ({"certainty_scheme": "not_rated"}, "not_rated finding"),
                             ({"claim_ids": ["nope"]}, "not a current claim")):
            r, _ = lc.check_finding(dict(base, **change), c, {}, 1)
            self.assertTrue(any(frag in x for x in r), (change, r))
        abstract = {k: dict(v, evidence_grade="ABSTRACT_ONLY") for k, v in c.items()}
        r, _ = lc.check_finding(base, abstract, {}, 1)
        self.assertTrue(any("abstract-only" in x for x in r))


class ExportTests(unittest.TestCase):
    META = {"title": "Reading {Braces} @home 100% & More_x NBER", "authors": ["Ada Allen", "World Bank Group"],
            "year": 2021, "venue": "J. Invented", "type": "article", "doi": "10.9/x", "first_page": "1",
            "last_page": "9"}
    ROW = {"paper_key": "user_f1c70003", "citekey": "allen2021reading", "title": "t",
           "citation_status": "verified_rule", "verify_row_sha256": "a" * 64}

    def test_bibtex_escapes_untrusted_text(self):
        e = lc.bib_entry(self.ROW, self.META, "FULL_TEXT_VERIFIED")
        self.assertEqual(e.count("{"), e.count("}"))
        self.assertIn("@home", e)                                             # harmless inside a braced value
        self.assertIn(r"100\%", e)
        self.assertIn("{NBER}", e)
        self.assertIn("Allen, Ada and {World Bank Group}", e)
        self.assertTrue(e.startswith("@article{allen2021reading,"))
        self.assertIn("daaf_verify_row_sha256", e)
        hostile = lc.bib_entry(self.ROW, dict(self.META, title="x}\n@misc{evil, title={y"), None)
        self.assertEqual(len(re.findall(r"(?m)^@", hostile)), 1)

    def test_ris_one_line_values(self):
        r = lc.ris_entry(self.ROW, dict(self.META, title="two\nlines"), "FULL_TEXT_VERIFIED")
        self.assertIn("TI  - two lines", r)
        self.assertTrue(r.startswith("TY  - JOUR") and r.rstrip().endswith("ER  -"))

    @unittest.skipUnless(shutil.which("quarto"), "needs quarto (bundled pandoc)")
    def test_pandoc_reads_the_bib_and_ris(self):
        d = _SCRIPTS / "scratch" / f"lit_corpus_test_{uuid.uuid4().hex[:8]}"
        d.mkdir(parents=True)
        try:
            (d / "r.bib").write_text(lc.bib_entry(self.ROW, self.META, None))
            (d / "r.ris").write_text(lc.ris_entry(self.ROW, self.META, None))
            items = lc.pandoc_parse(str(d / "r.bib"), "bibtex")
            self.assertEqual(items[0]["id"], "allen2021reading")
            self.assertIn("home 100% & ", items[0]["title"])                  # % and & round-trip
            self.assertEqual(len(lc.pandoc_parse(str(d / "r.ris"), "ris")), 1)
        finally:
            shutil.rmtree(d, ignore_errors=True)


@unittest.skipUnless(HAVE_FUZZ and HAVE_PARQUET, "needs rapidfuzz and polars or pyarrow")
class RoundTripTests(unittest.TestCase):
    def test_selftest_passes_and_cleans_up(self):
        scratch = _SCRIPTS / "scratch" / f"lit_corpus_test_{uuid.uuid4().hex[:8]}"
        try:
            with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
                code = lc.run(["selftest", str(scratch)])
            self.assertEqual(code, 0, out.getvalue())
            self.assertIn("SELFTEST PASS: 19/19", out.getvalue())   # unchanged in 1.1.0
            self.assertEqual([p.name for p in scratch.iterdir()], ["MANIFEST.jsonl"])
        finally:
            shutil.rmtree(scratch, ignore_errors=True)


class ReviewFixE1Tests(unittest.TestCase):
    # 1.1.0 (S4 review cycle 1): stdlib rules; every word invented.
    def test_title_grade_matches_scholar_search(self):
        pairs = [("Tutoring Small Groups: An Invented Trial", "Tutoring small groups: an invented trial"),
                 ("Teachers I", "Teachers II"), ("A", "A"), ("Reading Policy Adoption", "Dentistry for Beginners"),
                 ("Reading Policy Adoption and Pupil Scores", "Reading Policy Adoption: Pupil Scores Revisited")]
        try:
            import scholar_search
        except ImportError:                                  # httpx missing: compare with the documented verdicts
            got = [lc.title_grade(a, b) for a, b in pairs]
            self.assertEqual((got[0], got[2], got[3]), ("CONFIDENT", "WEAK", "MISMATCH"))
            return
        self.assertEqual([lc.title_grade(a, b) for a, b in pairs],
                         [scholar_search.verify_title_grade(a, b)[0] for a, b in pairs])

    def test_verify_regrade_never_raises_a_row(self):
        row = {"paper_key": "W1", "doi": "10.9/x"}
        work = {"id": "https://openalex.org/W1", "doi": "https://doi.org/10.9/x", "display_name": "Reading Policy "
                "Adoption and Pupil Scores", "publication_year": 2020, "authorships": [{"author": {"display_name":
                                                                                              "Ben Baker"}}]}
        raw = lambda params, w=work: lc.json.dumps({"query": "10.9/x", "parameters": params, "requests": [
            {"backend": "openalex", "response": w}]}).encode()
        title = {"title": "Reading Policy Adoption and Pupil Scores"}
        self.assertEqual(lc.verify_regrade(raw(title), row, "CONFIDENT")[0], "CONFIDENT")
        self.assertEqual(lc.verify_regrade(raw(title), row, "WEAK")[0], "WEAK")              # the row is a ceiling
        self.assertEqual(lc.verify_regrade(raw({"title": "Dentistry"}), row, "CONFIDENT")[0], "MISMATCH")
        self.assertEqual(lc.verify_regrade(raw(dict(title, year="2015")), row, "CONFIDENT")[0], "WEAK")
        self.assertEqual(lc.verify_regrade(raw(dict(title, author="Zulu")), row, "CONFIDENT")[0], "WEAK")
        self.assertEqual(lc.verify_regrade(raw({}), row, "CONFIDENT")[0], "EXISTS")
        self.assertIsNone(lc.verify_regrade(raw(title), dict(row, doi="10.9/other", paper_key="W2"), "CONFIDENT")[0])

    def test_retraction_status_from_the_raw_response(self):
        def raw(*reqs):
            return lc.json.dumps({"requests": list(reqs)}).encode()
        oa = lambda flag: {"backend": "openalex", "response": {"doi": "https://doi.org/10.9/x", "is_retracted": flag}}
        cr = lambda kind: {"backend": "crossref", "params": {"filter": "updates:10.9/x"}, "response": {"message": {
            "items": [{"DOI": "10.9/n", "update-to": [{"DOI": "10.9/x", "type": kind}]}]}}}
        row = {"retractions": [{"doi": "10.9/x", "status": "none"}]}
        self.assertEqual(lc.retraction_status(raw(oa(True)), row, "10.9/x"), "retracted")      # the row cannot lower it
        self.assertEqual(lc.retraction_status(raw(oa(False), cr("correction")), row, "10.9/x"), "corrected")
        self.assertEqual(lc.retraction_status(raw(oa(False), cr("addendum")), row, "10.9/x"), "updated")
        self.assertEqual(lc.retraction_status(raw(oa(False)), {"retractions": [{"doi": "10.9/x", "status":
                                                                                "expression of concern"}]}, "10.9/x"),
                         "expression of concern")                                              # the row can raise it
        self.assertIsNone(lc.retraction_status(raw(oa(True)), row, "10.9/other"))             # no response: unchecked

    def test_crossref_update_kinds_mirror_the_adapter(self):
        src = (_SCRIPTS / "scholar_backends" / "crossref.py").read_text()
        block = src.split("UPDATE_KINDS = ", 1)[1].split("\n\n", 1)[0]
        self.assertEqual(lc.CROSSREF_UPDATE_KINDS, eval(block, {}))       # noqa: S307 - a literal dict from our own file

    def test_merged_away_citekey_is_never_reused(self):
        aliases = [{"alias_kind": "citekey_history", "alias_value": "baker2020reading", "paper_key": "user_1"},
                   {"alias_kind": "merged_key", "alias_value": "user_1", "paper_key": "user_2"}]
        idx = lc.KeyIndex([{"paper_key": "user_2", "citekey": "allen2019tutoring", "title": "t",
                            "authors_json": "[]"}], aliases)
        self.assertEqual(lc.citekey_for("baker2020reading", idx.citekeys), "baker2020readinga")

    def test_failed_number_and_wrong_page_never_carry_a_finding(self):
        c = SummaryTests().claims()
        base = {"finding_id": "F01", "statement": "s", "claim_ids": list(c), "synthesis_method": "swim",
                "certainty_scheme": "stated", "certainty": "low", "certainty_reason": "see p1-c01",
                "decided_by": {"role": "synthesizer"}, "moderator_status": "none"}
        bad = dict(c, **{"p1-c01": dict(c["p1-c01"], numbers_status="fail")})
        self.assertTrue(any("failed the page check" in x for x in lc.check_finding(base, bad, {}, 1)[0]))
        card = {"claims": [{"claim_id": "C1", "quote": "q", "numbers": [], "page": 1}], "reader_model": "m"}
        cc = {"items": [{"kind": "claim_quote", "claim_id": "C1", "status": "WRONG_PAGE", "severity": "fail"}],
              "evidence_grade_suggested": None, "verdict": "FAIL"}
        self.assertEqual(lc.claim_rows_from_card("p1", "k", card, cc, {})[0]["verification"], "wrong_page")

    def test_sidecar_naming_another_raw_log_is_refused(self):
        d = _SCRIPTS / "scratch" / f"lit_corpus_test_{uuid.uuid4().hex[:8]}"
        d.mkdir(parents=True)
        try:
            side = lc.json.dumps({"schema_version": lc.RECORDS_SCHEMA, "groups": [], "raw_sha256": "b" * 64}).encode()
            (d / "s.records.json").write_bytes(side)
            ctx = {"pd": str(d.resolve()), "row": {"inputs": []}}
            entry = {"row": {"records_artifact": "s.records.json", "records_sha256": lc.sha256_bytes(side),
                             "raw_sha256": "a" * 64}, "dir": str(d.resolve())}
            with self.assertRaises(lc.CorpusError) as cm:
                lc.load_sidecar(ctx, "c" * 64, entry)
            self.assertEqual(cm.exception.code, 9)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_bibtex_organisation_authors(self):
        for authors, want in ((["National Bureau of Economic Research", "Jane Smith"],
                               "author = {{National Bureau of Economic Research} and Smith, Jane}"),
                              (["National Bureau of Economic Research"],
                               "author = {{National Bureau of Economic Research}}")):
            e = lc.bib_entry(ExportTests.ROW, dict(ExportTests.META, authors=authors), None)
            self.assertIn(want, e)
            self.assertEqual(e.count("{"), e.count("}"))

    @unittest.skipUnless(shutil.which("quarto"), "needs quarto (bundled pandoc)")
    def test_pandoc_reads_organisation_authors(self):
        d = _SCRIPTS / "scratch" / f"lit_corpus_test_{uuid.uuid4().hex[:8]}"
        d.mkdir(parents=True)
        try:
            for i, authors in enumerate((["National Bureau of Economic Research", "Jane Smith"],
                                         ["National Bureau of Economic Research"])):
                (d / f"o{i}.bib").write_text(lc.bib_entry(ExportTests.ROW, dict(ExportTests.META, authors=authors),
                                                          None))
                items = lc.pandoc_parse(str(d / f"o{i}.bib"), "bibtex")
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0]["author"][0].get("literal"), "National Bureau of Economic Research")
        finally:
            shutil.rmtree(d, ignore_errors=True)


class GapWordsTests(unittest.TestCase):
    # gap-words-v1 (review M-W9): codes optional, plain words in the researcher-facing register.
    DOC = _REPO_ROOT / ".claude" / "skills" / "literature-review" / "references" / "gaps-and-saturation.md"

    def test_heading_uses_plain_words_never_codes(self):
        h = lc.gap_heading({"gap_id": "G01", "miles_type": "population", "sa_mode": "neglect", "confidence": "low"})
        self.assertEqual(h, "## G01: a population not yet studied; an overlooked area (how sure we are the gap is "
                            "real: low)")
        h2 = lc.gap_heading({"gap_id": "G02", "miles_type": "unclassified", "sa_mode": "application_spotting",
                             "confidence": "moderate"})
        self.assertEqual(h2, "## G02: existing work could be extended (how sure we are the gap is real: moderate)")
        h3 = lc.gap_heading({"gap_id": "G03", "miles_type": "unclassified", "sa_mode": "unclassified",
                             "confidence": "high"})
        self.assertEqual(h3, "## G03: not classified (how sure we are the gap is real: high)")
        # "population" is also a plain word ("a population not yet studied"); no other code may appear
        for code in set(lc.MILES_TYPES + lc.SA_MODES + (lc.GAP_UNCLASSIFIED,)) - {"population"}:
            self.assertNotIn(code, h + h2 + h3)

    @unittest.skipUnless(DOC.is_file(), "literature-review skill not present")
    def test_plain_words_match_the_skill_tables(self):
        cells = {}
        for line in self.DOC.read_text().splitlines():
            m = re.match(r"^\| `([a-z_]+)` \|(?: [^|]+ \|)? ([^|]+) \|$", line)
            if m:
                cells[m.group(1)] = m.group(2).strip()
        for code, words in list(lc.MILES_WORDS.items()) + list(lc.SA_WORDS.items()):
            self.assertTrue(cells.get(code, "").startswith(words), (code, cells.get(code), words))
        self.assertEqual(set(lc.MILES_WORDS), set(lc.MILES_TYPES))
        self.assertEqual(set(lc.SA_WORDS), set(lc.SA_MODES))


@unittest.skipUnless(HAVE_PARQUET, "needs polars or pyarrow")
class BundleCopyTests(unittest.TestCase):
    # Subcommands on a copy of the contract bundle (removed after each test).
    def setUp(self):
        self.root = _SCRIPTS / "scratch" / f"lit_corpus_test_{uuid.uuid4().hex[:8]}"
        self.pd = self.root / "project"
        shutil.copytree(ContractBundleTests.BUNDLE, self.pd)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_lc(self, *argv):
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            code = lc.run([str(x) for x in argv])
        return code, out.getvalue() + err.getvalue()

    def jsonl(self, name, rows):
        p = self.pd / "inputs" / name
        p.write_text("".join(lc.json.dumps(r) + "\n" for r in rows))
        return p

    def table(self, name):
        ctx = {"pd": os.path.realpath(self.pd), "data": str(self.pd / "data"), "read": lc.parquet_io()[0],
               "cache": {}, "row": {"inputs": []}}
        return lc.load_table(ctx, name)[0]

    def test_full_text_screening_needs_a_title_abstract_include(self):
        code, out = self.run_lc("screen", "record", self.pd, self.jsonl("ft.jsonl", [
            {"paper_key": "W900000005", "stage": "ft", "pass": "primary", "decision": "include",
             "screener": {"model_id": "m"}}]))
        self.assertEqual(code, 11, out)

    def test_card_edited_after_its_check_is_refused(self):
        card = self.pd / "papers" / "user_f1c70001" / "evidence_card_a.md"
        card.write_bytes(card.read_bytes() + b" ")
        self.assertEqual(self.run_lc("claims", "build", self.pd, "--keys", "user_f1c70001")[0], 9)

    def test_recorded_note_is_never_replaced_by_the_card(self):
        code, out = self.run_lc("notes", "record", self.pd, self.jsonl("n.jsonl", [
            {"paper_key": "user_f1c70001", "design": "rct", "study_weight": "limited", "weight_reason": "one district",
             "decided_by": {"role": "researcher", "name": "probe"}}]))
        self.assertEqual(code, 0, out)
        code, out = self.run_lc("claims", "build", self.pd)
        self.assertEqual(code, 0, out)
        self.assertIn("was kept", out)
        note = next(r for r in self.table("paper_notes") if r["paper_key"] == "user_f1c70001")
        self.assertEqual((note["study_weight"], note["source"]), ("limited", "recorded"))

    def test_gap_without_codes_is_recorded_as_unclassified(self):
        g01 = next(r for r in self.table("gap_register") if r["gap_id"] == "G01")
        sha = lc.jload(g01["evidence_of_absence_json"])[0]["row_sha256"]
        gap = {"gap_id": "G03", "statement": "No invented study followed pupils past one year.", "confidence": "low",
               "data_answerable": False, "absence": [{"row_sha256": sha, "kind": "zero_results"}]}
        code, out = self.run_lc("gaps", "record", self.pd, self.jsonl("g.jsonl", [gap]))
        self.assertEqual(code, 0, out)
        row = next(r for r in self.table("gap_register") if r["gap_id"] == "G03")
        self.assertEqual((row["miles_type"], row["sa_mode"]), ("unclassified", "unclassified"))
        md = max((self.pd / "output").glob("gap_register_v*.md"), key=lambda p: int(p.stem.rsplit("_v", 1)[1]))
        text = md.read_text()
        self.assertIn("## G03: not classified (how sure we are the gap is real: low)", text)
        self.assertIn("- the search returned nothing: `find`", text)
        for code_word in ("unclassified", "neglect", "application_spotting", "zero_results", "none_eligible"):
            self.assertNotIn(code_word, text)
        bad = self.run_lc("gaps", "record", self.pd, self.jsonl("g2.jsonl", [dict(gap, gap_id="G04",
                                                                                  miles_type="vibes")]))
        self.assertEqual(bad[0], 11, bad[1])                                    # a given code must still be valid

    def test_dedup_chains_and_never_merges_a_read_paper(self):
        keys = []
        for i, word in enumerate(("Alpha", "Beta", "Gamma")):
            pdf = self.pd / "inputs" / f"u{i}.pdf"
            pdf.write_bytes(f"invented {i}".encode())
            code, out = self.run_lc("add-record", self.pd, "--user-pdf", pdf, "--title", f"{word} Invented Club Notes",
                                    "--authors", "Eve Evans", "--year", "2018")
            self.assertEqual(code, 0, out)
            keys.append(re.search(r"(user_[0-9a-f]{8})", out).group(1))
        dec = lambda k, m: {"keep": k, "merge": m, "reason": "same work", "decided_by": {"role": "researcher"}}
        code, out = self.run_lc("dedup", "decide", self.pd, self.jsonl("d.jsonl", [dec(keys[0], keys[1]),
                                                                                  dec(keys[1], keys[2])]))
        self.assertEqual(code, 0, out)
        corpus = {r["paper_key"] for r in self.table("corpus")}
        self.assertEqual((keys[0] in corpus, keys[1] in corpus, keys[2] in corpus), (True, False, False))
        code, out = self.run_lc("dedup", "decide", self.pd, self.jsonl("d2.jsonl", [dec(keys[0], "user_f1c70001")]))
        self.assertEqual(code, 11, out)

    def test_chained_dedup_batch_keeps_the_screening_clash_rule(self):
        # q-I2 (dedup-v3): X (screened ta) into Y, then Y into Z (screened ta) in ONE batch: the second line sees X's
        #   rows already on Y, so the clash refuses the batch.
        keys = []
        for i, word in enumerate(("Delta", "Epsilon", "Zeta")):
            pdf = self.pd / "inputs" / f"c{i}.pdf"
            pdf.write_bytes(f"invented chain {i}".encode())
            code, out = self.run_lc("add-record", self.pd, "--user-pdf", pdf, "--title", f"{word} Invented Chain Notes",
                                    "--authors", "Eve Evans", "--year", "2018")
            self.assertEqual(code, 0, out)
            keys.append(re.search(r"(user_[0-9a-f]{8})", out).group(1))
        x, y, z = keys
        who = {"model_id": "m"}
        code, out = self.run_lc("screen", "record", self.pd, self.jsonl("s.jsonl", [
            {"paper_key": x, "stage": "ta", "pass": "primary", "decision": "include", "screener": who},
            {"paper_key": z, "stage": "ta", "pass": "primary", "decision": "exclude", "reason_code": "population",
             "rationale": "adults", "screener": who}]))
        self.assertEqual(code, 0, out)
        dec = lambda k, m: {"keep": k, "merge": m, "reason": "same work", "decided_by": {"role": "researcher"}}
        code, out = self.run_lc("dedup", "decide", self.pd, self.jsonl("dc.jsonl", [dec(y, x), dec(z, y)]))
        self.assertEqual(code, 11, out)
        self.assertIn("both papers were screened at stage ta", out)
        self.assertEqual({r["paper_key"] for r in self.table("corpus")} >= {x, y, z}, True)   # nothing written

    def test_ingest_fills_an_empty_abstract_and_never_replaces_one(self):
        # q-I5 (abstract-fill-v1): the bundle's papers were added by add-record (no abstract) and then found by a
        #   search whose record carries an abstract: the empty abstract was filled and the found_by entry says so.
        allen = next(r for r in self.table("corpus") if r["paper_key"] == "user_f1c70001")
        self.assertEqual(allen["abstract"], "An invented abstract.")
        fb = lc.jload(allen["found_by_json"])
        self.assertEqual([bool(e.get("abstract_filled")) for e in fb], [False, True])
        lc.demo_search_row(str(self.pd), "round9", "find", "tutoring again", [{"primary": dict(
            lc.demo_record(lc.DEMO_PAPERS[0]), abstract="A different invented abstract that must not replace it.")}])
        self.assertEqual(self.run_lc("ingest", self.pd, "--round", "2")[0], 0)
        allen = next(r for r in self.table("corpus") if r["paper_key"] == "user_f1c70001")
        self.assertEqual(allen["abstract"], "An invented abstract.")
        self.assertEqual(sum(1 for e in lc.jload(allen["found_by_json"]) if e.get("abstract_filled")), 1)

    def test_abstract_claims_and_the_abstract_only_guard(self):
        abstract = "In an invented club survey, adults who joined reading clubs read more books each month."
        lc.demo_search_row(str(self.pd), "round9", "find", "clubs", [{"primary": {
            "title": "An Invented Club Survey for Adults", "authors": ["Ivy Ito"], "year": 2019,
            "doi": "10.9999/fixture.0009", "ids": {"openalex": ["W900000009"], "doi": ["10.9999/fixture.0009"]},
            "abstract": abstract}}])
        self.assertEqual(self.run_lc("ingest", self.pd, "--round", "2")[0], 0)
        code, out = self.run_lc("claims", "abstract", self.pd, self.jsonl("a.jsonl", [
            {"paper_key": "W900000009", "quote": "adults who joined reading clubs read more books each month",
             "claim_type": "finding"}]))
        self.assertEqual(code, 0, out)
        bad = self.run_lc("claims", "abstract", self.pd, self.jsonl("b.jsonl", [
            {"paper_key": "W900000009", "quote": "adults who joined reading clubs read twice as many books",
             "claim_type": "finding"}]))
        self.assertEqual(bad[0], 11, bad[1])
        row = next(r for r in self.table("claims") if r["paper_key"] == "W900000009")
        self.assertEqual((row["claim_id"], row["evidence_grade"], row["verification"]),
                         ("W900000009-a01", "ABSTRACT_ONLY", "abstract_verified"))
        f = {"finding_id": "F09", "statement": "s", "claim_ids": ["W900000009-a01"], "synthesis_method": "narrative",
             "certainty_scheme": "stated", "certainty": "moderate", "certainty_reason": "W900000009-a01",
             "decided_by": {"role": "synthesizer"}, "moderator_status": "none"}
        code, out = self.run_lc("findings", "record", self.pd, self.jsonl("f.jsonl", [f]))
        self.assertEqual(code, 11, out)                                         # V4: never moderate on abstracts
        code, out = self.run_lc("findings", "record", self.pd, self.jsonl("f2.jsonl", [dict(
            f, certainty_scheme="not_rated", certainty=None, certainty_reason=None, not_rated_reason="abstracts_only")]))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.run_lc("claims", "build", self.pd)[0], 0)          # a later build keeps them current
        row = next(r for r in self.table("claims") if r["claim_id"] == "W900000009-a01")
        self.assertEqual(row["status"], "current")


@unittest.skipUnless(HAVE_PARQUET, "needs polars or pyarrow")
class ContractBundleTests(unittest.TestCase):
    BUNDLE = _REPO_ROOT / "tests" / "python" / "fixtures" / "lit_corpus" / "contract_bundle"

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_bundle_parquet_files_are_not_git_ignored(self):
        # C-B1: the repo-wide *.parquet ignore must not drop the bundle's tables (a .gitignore negation keeps them)
        files = sorted(str(p.relative_to(_REPO_ROOT)) for p in self.BUNDLE.rglob("*.parquet"))
        self.assertTrue(files)
        r = lc.subprocess.run(["git", "-C", str(_REPO_ROOT), "check-ignore", "--no-index", *files],
                              capture_output=True, text=True)
        if r.returncode == 128:
            self.skipTest("not a git checkout")
        self.assertEqual(r.stdout.strip(), "", "git-ignored bundle files")
        self.assertFalse((self.BUNDLE / "data" / ".lit_corpus.lock").exists())

    def test_bundle_tables_match_their_manifest(self):
        rows = [r for _, r in lc.manifest_rows(str(self.BUNDLE / "data" / "MANIFEST.jsonl"))]
        arts = [a for r in rows for a in r.get("artifacts") or []]
        self.assertTrue(arts)
        for a in arts:
            self.assertEqual(lc.sha256_bytes((self.BUNDLE / a["path"]).read_bytes()), a["sha256"], a["path"])
        pointer = (self.BUNDLE / "output" / "LIT_REVIEW_MANIFEST.json").read_text()
        self.assertIn("manifests/LIT_REVIEW_MANIFEST_v1.json", pointer)
        self.assertTrue((self.BUNDLE / "data_json" / "findings.json").is_file())


if __name__ == "__main__":
    unittest.main()
