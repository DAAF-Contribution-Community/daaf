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
from unittest import mock

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
        self.assertEqual((lc.TOOL_VERSION, lc.CONTRACT_VERSION), ("1.8.1-daaf", "0.5.0"))
        # The certainty phrase table and its lockstep copy carry the contract version.
        self.assertEqual(lc.lv.lrr.CERTAINTY_LANGUAGE["contract_version"], lc.CONTRACT_VERSION)
        self.assertEqual(lc.SCHEMAS["paper_notes"], "lit-paper-notes-v1")
        self.assertEqual(lc.SCHEMAS["citation_adjudications"], "lit-adjudications-v1")
        self.assertEqual(lc.RULE_VERSIONS["paperkey"], "paperkey-v1")
        self.assertEqual(lc.RULE_VERSIONS["verify_regrade"], "verify-regrade-v3")
        self.assertEqual(lc.RULE_VERSIONS["glance_words"], "glance-words-v3")
        self.assertEqual(lc.RULE_VERSIONS["adj_model_check"], "adj-model-check-v1")
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
        # 1.4.0: an old table's verified_rule is exported as what it now means (held for its second check)
        self.assertIn("daaf_citation_status = {pending_adjudication}", e)
        self.assertNotIn("verified_rule", e + lc.ris_entry(self.ROW, self.META, None))
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
            self.assertIn("SELFTEST PASS: 36/36", out.getvalue())
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


class SecondCheckRuleTests(unittest.TestCase):
    # 1.4.0 (S5 W1-b): the stdlib rules of the citation second check. Every word invented.
    def test_rules_version_order(self):
        order = ["2026-10-06", "2026-10-06f", "2026-11-01", "2026-11-01a", "2026-11-01b", "2026-11-01c",
                 "2026-11-01d", "2026-11-01z", "2026-11-01aa", "2026-11-02"]
        self.assertEqual(sorted(order, key=lc.rules_version_key), order)
        self.assertTrue(lc.rules_older("2026-11-01c"))                          # MIN_RULES_VERSION is 2026-11-01d
        self.assertFalse(lc.rules_older("2026-11-01d"))
        self.assertFalse(lc.rules_older("2026-11-01aa"))
        for bad in (None, "", "v2", "2026-11-01C", "2026-11-1c"):
            self.assertTrue(lc.rules_older(bad), bad)                             # unreadable: fail closed
        self.assertEqual(lc.MIN_RULES_VERSION, "2026-11-01d")

    def test_statuses_and_citability(self):
        self.assertEqual(lc.read_status("verified_rule"), "pending_adjudication")     # legacy tables
        self.assertEqual((lc.read_status(None), lc.read_status("human_confirmed")), ("unverified", "human_confirmed"))
        self.assertEqual(set(lc.CITABLE_FINAL), {"model_confirmed", "model_adjudicated", "human_confirmed",
                                                 "human_overridden"})
        self.assertEqual(set(lc.CITABLE_DRAFT) - set(lc.CITABLE_FINAL), {"pending_adjudication",
                                                                          "human_accepted_unbound"})
        self.assertEqual(lc.CITABLE, lc.CITABLE_DRAFT)
        self.assertEqual(set(lc.DRAFT_REVIEW_STATUSES), {"pending_adjudication", "human_accepted_unbound"})
        for st in ("rejected", "unverified"):
            self.assertNotIn(st, lc.CITABLE_DRAFT)
        self.assertEqual(set(lc.CITATION_STATUSES), set(lc.CITABLE_DRAFT) | {"rejected", "unverified"})
        self.assertEqual((lc.ADJUDICATOR_LIST_VERSION, lc.evaluated_identities()), ("adjudicator-list-none", set()))

    def test_evaluated_identity_needs_every_dimension(self):
        # the evaluated list is keyed by the whole identity: a list entry differing in ONE dimension never matches
        e = lc.demo_evaluated_entry()
        ident = dict(zip(("model_id", "template_sha256", "rubric_version", "agent_file_sha256"), e))
        other = {"model_id": "another-model", "template_sha256": "0" * 64, "rubric_version": "fixture-rubric-v2",
                 "agent_file_sha256": "1" * 64}
        with mock.patch.dict(lc.ADJUDICATOR_EVALUATED_LISTS, {"adjudicator-list-test": (e,)}):
            self.assertTrue(lc.evaluated_identity("adjudicator-list-test", *e, e[3]))
            for dim, value in other.items():
                with self.subTest(dim):
                    got = dict(ident, **{dim: value})
                    self.assertFalse(lc.evaluated_identity("adjudicator-list-test", got["model_id"],
                                                           got["template_sha256"], got["rubric_version"],
                                                           got["agent_file_sha256"], got["agent_file_sha256"]))
            self.assertFalse(lc.evaluated_identity("adjudicator-list-test", *e, "1" * 64))   # agent file edited
            self.assertFalse(lc.evaluated_identity("adjudicator-list-test", *e, None))       # or gone at ingest
            self.assertFalse(lc.evaluated_identity(None, *e, e[3]))                          # no list version
            self.assertFalse(lc.evaluated_identity("adjudicator-list-none", *e, e[3]))       # another version
        with mock.patch.dict(lc.ADJUDICATOR_EVALUATED_LISTS, {"adjudicator-list-test": (e[0], e[:3])}):
            self.assertFalse(lc.evaluated_identity("adjudicator-list-test", *e, e[3]))       # malformed entries
            self.assertEqual(lc.evaluated_identities("adjudicator-list-test"), set())

    def test_status_transitions(self):
        s = lc.adjudication_status
        cases = [(("CONFIDENT", None, None, False, None), "pending_adjudication"),
                 (("CONFIDENT", "SAME_WORK", "UNCERTAIN", False, None), "pending_adjudication"),   # unevaluated model
                 (("CONFIDENT", "SAME_WORK", "SAME_WORK", False, None), "model_confirmed"),
                 (("CONFIDENT", "DIFFERENT_WORK", "DIFFERENT_WORK", False, None), "rejected"),
                 (("WEAK", "SAME_WORK", "SAME_WORK", False, None), "model_adjudicated"),
                 (("WEAK", "SAME_WORK", "SAME_WORK", True, None), "unverified"),                     # floor: a person
                 (("WEAK", "DIFFERENT_WORK", "UNCERTAIN", False, None), "unverified"),
                 (("WEAK", "SAME_WORK", "SAME_WORK", False, "defer"), "model_adjudicated"),
                 (("CONFIDENT", None, None, False, "same_work"), "human_confirmed"),
                 (("WEAK", "SAME_WORK", "UNCERTAIN", False, "same_work"), "human_confirmed"),
                 (("WEAK", "DIFFERENT_WORK", "DIFFERENT_WORK", False, "same_work"), "human_overridden"),
                 (("WEAK", "DIFFERENT_WORK", "UNCERTAIN", False, "same_work"), "human_overridden"),
                 (("CONFIDENT", "SAME_WORK", "SAME_WORK", False, "different_work"), "rejected"),
                 (("MISMATCH", None, None, False, "override_mismatch"), "human_overridden"),
                 (("WEAK", None, None, False, "override_mismatch"), "unverified"),
                 (("MISMATCH", None, None, False, "defer"), "unverified"),
                 (("EXISTS", None, None, False, "same_work"), "unverified")]
        for args, want in cases:
            self.assertEqual(s(*args), want, args)

    def test_per_dimension_rule(self):
        c = lc.combine_dimensions
        self.assertEqual(c({"title": "SAME_WORK", "author": "SAME_WORK"}, ["title", "author"]), "SAME_WORK")
        self.assertEqual(c({"title": "SAME_WORK", "author": "DIFFERENT_WORK"}, ["title"]), "DIFFERENT_WORK")
        self.assertEqual(c({"title": "SAME_WORK", "author": "UNCERTAIN"}, ["title"]), "UNCERTAIN")
        self.assertEqual(c({"title": "SAME_WORK"}, ["title", "type"]), "UNCERTAIN")           # an omitted dimension

    def test_title_grade_matches_verify_on_the_held_out_shapes(self):
        # verify-regrade-v3: a negation, a one-word swap and a flipped mark step aside to WEAK exactly as verify does
        pairs = [("Statistics notes: Absence of evidence is evidence of absence",
                  "Statistics notes: Absence of evidence is not evidence of absence"),
                 ("Invented reading clubs raise better scores in rural districts across ten counties",
                  "Invented reading clubs raise worse scores in rural districts across ten counties"),
                 ("Invented mortality in children aged <5 years in rural districts",
                  "Invented mortality in children aged >5 years in rural districts"),
                 ("Invented tutoring trial in Bogotá schools", "Invented tutoring trial in Bogota schools"),
                 ("Tutoring Small Groups: An Invented Trial", "Tutoring small groups: an invented trial")]
        got = [lc.title_grade(a, b) for a, b in pairs]
        self.assertEqual(got[1:3], ["WEAK", "WEAK"])
        self.assertEqual(got[4], "CONFIDENT")
        try:
            import scholar_search
        except ImportError:                                  # httpx missing: the documented verdicts above stand
            return
        self.assertEqual(got, [scholar_search.verify_title_grade(a, b)[0] for a, b in pairs])

    def test_selector_tags(self):
        self.assertEqual(lc.adj_selector({"verdict": "CONFIDENT"}, "CONFIDENT"),
                         (["confident_second_check"], ["author", "title", "type", "version"]))
        org = {"verdict": "WEAK", "author_check": {"name_part": lc.sc.ORG_NOT_EXACT}, "title_similarity": 0.9}
        self.assertEqual(lc.adj_selector(org, "WEAK"), (["org_not_exact", "title_band"], ["org", "title", "type"]))
        unchecked = {"verdict": "WEAK", "author_check": {"status": "unchecked", "reason": "the cited author reads as "
                                                                                         "an organization"}}
        self.assertIn("org_unchecked", lc.adj_selector(unchecked, "WEAK")[0])
        yr = {"verdict": "WEAK", "year_check": {"ok": False}, "title_similarity": 1.0}
        self.assertEqual(lc.adj_selector(yr, "WEAK")[0], ["version"])

    def test_pack_log_parser(self):
        out = ("ADJUDICATION_PACK batch_id=b01 rows=1 model_id=m agent_name=citation-adjudicator prompt_version=p "
               "rubric_version=r template_sha256=" + "d" * 64 + " agent_file_sha256=" + "e" * 64 +
               "\nADJUDICATION_ROW " + "a" * 64 + "\nADJUDICATION_BUNDLE_SHA256 " + "b" * 64 +
               " x\nADJUDICATION_PROMPT_SHA256 " + "c" * 64 + " y\n")
        log = lambda body, code="0", cap="COMPLETE": ("print(1)\n\n# " + "=" * 77 + "\n" + body + "\n# Exit code: "
                                                      + code + "\n# Capture: " + cap + "\n# --- STDOUT ---\n" +
                                                      "".join("# " + x + "\n" for x in out.splitlines())).encode()
        good = lc.parse_pack_log(log("# EXECUTION LOG"), "b01")
        self.assertEqual((good["model_id"], good["rows"], good["bundle_sha256"]), ("m", ["a" * 64], "b" * 64))
        self.assertEqual((good["template_sha256"], good["agent_file_sha256"]), ("d" * 64, "e" * 64))
        full = out
        for gone in (" template_sha256=" + "d" * 64, " agent_file_sha256=" + "e" * 64):
            out = full.replace(gone, "")                                       # the identity must be in the log
            self.assertIsNone(lc.parse_pack_log(log("# EXECUTION LOG"), "b01"), gone)
        out = full
        self.assertIsNone(lc.parse_pack_log(log("# EXECUTION LOG"), "b02"))                   # another batch
        self.assertIsNone(lc.parse_pack_log(log("# EXECUTION LOG", code="1"), "b01"))        # failed run
        self.assertIsNone(lc.parse_pack_log(log("# EXECUTION LOG", cap="INCOMPLETE"), "b01"))
        self.assertIsNone(lc.parse_pack_log(log("# EXECUTION LOG\n# EXECUTION LOG"), "b01"))  # two markers
        self.assertIsNone(lc.parse_pack_log(log("no marker"), "b01"))


class TemplateContractTests(unittest.TestCase):
    # The fixed prompt template's extraction contract (lit-corpus.md § Adjudication prompt template).
    START = '<!-- adjudication-prompt-template prompt_version="adj-prompt-v1" rubric_version="adj-rubric-v1" -->'

    def setUp(self):
        self.d = _SCRIPTS / "scratch" / f"lit_corpus_test_{uuid.uuid4().hex[:8]}"
        self.d.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def extract(self, text):
        p = self.d / f"t{uuid.uuid4().hex[:6]}.md"
        p.write_text(text)
        return lc.adj_template({"paths": {"template": str(p)}, "row": {"inputs": []}})

    def code(self, text):
        with self.assertRaises(lc.CorpusError) as cm:
            self.extract(text)
        return cm.exception.code

    def block(self, body, start=None):
        return f"# Rubric\n\nprose\n\n{start or self.START}\n```text\n{body}\n```\n{lc.ADJ_TEMPLATE_END}\n\nmore prose\n"

    def test_good_block(self):
        body, pv, rv, sha = self.extract(self.block("Read only {BUNDLE_PATH}.\nReturn JSONL."))
        self.assertEqual((body, pv, rv), ("Read only {BUNDLE_PATH}.\nReturn JSONL.", "adj-prompt-v1", "adj-rubric-v1"))
        self.assertEqual(sha, lc.sha256_bytes(body.encode()))

    def test_refusals(self):
        with self.assertRaises(lc.CorpusError) as cm:
            lc.adj_template({"paths": {"template": str(self.d / "absent.md")}, "row": {"inputs": []}})
        self.assertEqual(cm.exception.code, 10)                                                # file missing
        self.assertEqual(self.code("# Rubric only, no block\n"), 8)
        self.assertEqual(self.code(self.block("x {BUNDLE_PATH}") + self.block("y {BUNDLE_PATH}")), 8)  # two blocks
        self.assertEqual(self.code(self.block("{BUNDLE_PATH} and {BUNDLE_PATH}")), 8)
        self.assertEqual(self.code(self.block("{BUNDLE_PATH} for {CLAIM_TEXT}")), 8)             # a free slot
        self.assertEqual(self.code(self.block("no placeholder")), 8)
        self.assertEqual(self.code(self.block("x {BUNDLE_PATH}", start=self.START.replace(' rubric_version="adj-rubric-'
                                                                                           'v1"', ""))), 8)
        self.assertEqual(self.code(self.block("x {BUNDLE_PATH}").replace("```text", "```")), 8)


@unittest.skipUnless(HAVE_FUZZ and HAVE_PARQUET, "needs rapidfuzz and polars or pyarrow")
class SecondCheckCommandTests(unittest.TestCase):
    # 1.4.0: pack | ingest | record-human | glance-sheet on a copy of the contract bundle (whose four papers were
    #   confirmed by the researcher's one reply). A new verify row puts a paper back to its second check. Each
    #   hardening test plants ONE forgery that only the named check stops.
    def setUp(self):
        self.root = _SCRIPTS / "scratch" / f"lit_corpus_test_{uuid.uuid4().hex[:8]}"
        self.pd = self.root / "project"
        shutil.copytree(ContractBundleTests.BUNDLE, self.pd)
        self.steps = []

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_lc(self, *argv, **internal):
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            code = lc.run([str(x) for x in argv], **internal)
        return code, out.getvalue() + err.getvalue()

    def step(self, name, argv, **internal):
        code, out = self.run_lc(*argv, **internal)
        self.steps.append((name, code, out))
        return code

    def jsonl(self, rows):
        p = self.pd / "inputs" / f"t_{uuid.uuid4().hex[:6]}.jsonl"
        p.write_text("".join(lc.json.dumps(r) + "\n" for r in rows))
        return p

    def table(self, name):
        ctx = {"pd": os.path.realpath(self.pd), "data": str(self.pd / "data"), "read": lc.parquet_io()[0],
               "cache": {}, "row": {"inputs": []}}
        return lc.load_table(ctx, name)[0]

    def paper(self, key):
        return next(r for r in self.table("corpus") if r["paper_key"] == key)

    def attach(self, *specs):
        # specs: (paper index, demo_verify_row kwargs) -> {paper key: new verify row sha}
        vmap, out = [], {}
        for i, kw in specs:
            p = lc.DEMO_PAPERS[i]
            out[p["key"]] = lc.demo_verify_row(str(self.pd), p, **kw)
            vmap.append({"row_sha256": out[p["key"]], "paper_key": p["key"]})
        code, o = self.run_lc("attach", "verify", self.pd, self.jsonl(vmap))
        self.assertEqual(code, 0, o)
        return out

    def adjudicate(self, batch, keys, **kw):
        lc.demo_adjudicate(self.step, self.steps, str(self.pd), batch, keys=keys, **kw)
        return [c for _, c, _ in self.steps[-2:]] if self.steps[-1][0].startswith("adjudications ingest") else \
            [self.steps[-1][1]]

    def rows_file(self, shas):
        p = self.pd / "inputs" / f"rows_{uuid.uuid4().hex[:6]}.txt"
        p.write_text("".join(s + "  # invented\n" for s in shas))
        return p

    def human(self, shas, decision="same_work", words="These look right.", rationale="Checked each title."):
        argv = ["adjudications", "record-human", self.pd, "--rows", self.rows_file(shas), "--decision", decision]
        argv += (["--user-words", words] if words is not None else []) + (
            ["--rationale", rationale] if rationale is not None else [])
        return self.run_lc(*argv)

    P1, P2, P3 = (lc.DEMO_PAPERS[i]["key"] for i in range(3))

    def test_bundle_papers_were_confirmed_by_one_reply(self):
        led = self.table("citation_adjudications")
        self.assertEqual({r["citation_status"] for r in led if r["human_decision"]}, {"human_confirmed"})
        self.assertEqual({self.paper(lc.DEMO_PAPERS[i]["key"])["citation_status"] for i in range(4)},
                         {"human_confirmed"})
        bib = (self.pd / "output" / "references_v1.bib").read_text()
        self.assertEqual(bib.count("daaf_citation_status = {human_confirmed}"), 4)

    def test_pack_selects_confident_and_weak_never_mismatch(self):
        # (i): every CONFIDENT and every WEAK row; never MISMATCH or EXISTS
        bad = dict(lc.demo_work_json(lc.DEMO_PAPERS[2]), display_name="A Completely Different Invented Dentistry Study")
        self.attach((0, {}), (1, {"verdict": "WEAK", "extra": {"title_similarity": 0.9}}), (2, {"work": bad}))
        self.assertEqual(self.paper(self.P1)["citation_status"], "pending_adjudication")
        self.assertEqual(self.paper(self.P3)["verify_verdict"], "MISMATCH")
        code, out = self.run_lc("adjudications", "pack", self.pd, "--batch", "t1", "--model-id", "m",
                                paths=lc.demo_adj_paths(str(self.pd)))
        self.assertEqual(code, 0, out)
        b = lc.json.loads((self.pd / "data" / "adjudication_bundles" / "t1.json").read_text())
        sel = {r["rule_verdict"]: r["selector"] for r in b["rows"]}
        self.assertEqual(sel, {"CONFIDENT": ["confident_second_check"], "WEAK": ["title_band"]})
        self.assertEqual(out.count("ADJUDICATION_ROW "), 2)
        row = b["rows"][0]
        self.assertEqual(row["record"]["type"], "article")
        self.assertEqual(row["record"]["venue"], "Journal of Invented Studies")
        self.assertTrue(row["cited"]["authors_full"] and row["cited"]["title_raw"])
        prompt = (self.pd / "data" / "adjudication_bundles" / "t1_prompt.txt").read_text()
        self.assertIn(os.path.realpath(self.pd / "data" / "adjudication_bundles" / "t1.json"), prompt)
        self.assertIn(f"ADJUDICATION_PROMPT_SHA256 {lc.sha256_bytes(prompt.encode())}", out)
        again = self.run_lc("adjudications", "pack", self.pd, "--batch", "t2", "--model-id", "m",
                            paths=lc.demo_adj_paths(str(self.pd)))
        self.assertEqual(again[0], 11, again[1])         # both rows sit in batch t1 (re-dispatch it, never re-pack)

    def test_c_pack_refuses_confident_under_old_rules(self):
        self.attach((0, {"rules_version": "2026-11-01b"}))
        code, out = self.run_lc("adjudications", "pack", self.pd, "--batch", "t1", "--model-id", "m",
                                paths=lc.demo_adj_paths(str(self.pd)))
        self.assertEqual(code, 11, out)
        self.assertIn("re-verify", out)
        self.assertFalse((self.pd / "data" / "adjudication_bundles" / "t1.json").exists())

    def test_unevaluated_model_counts_uncertain_and_e_model_id_from_the_log(self):
        # (e): the return claims an evaluated model; the pack log (the dispatch record) names another
        self.attach((0, {}))
        with mock.patch.dict(lc.ADJUDICATOR_EVALUATED_LISTS, {"adjudicator-list-none": ("model-x",)}):
            codes = self.adjudicate("t1", [self.P1], ret_extra={"model_id": "model-x", "agent_name": "paper-reader"})
        self.assertEqual(codes, [0, 0], self.steps[-1][2])
        led = [r for r in self.table("citation_adjudications") if r["batch_id"] == "t1"][0]
        self.assertEqual((led["model_id"], led["model_id_source"], led["agent_name"]),
                         (lc.DEMO_ADJ_MODEL, "orchestrator_dispatch_record", "citation-adjudicator"))
        self.assertEqual((led["verdict"], led["effective_verdict"], led["citation_status"]),
                         ("SAME_WORK", "UNCERTAIN", "pending_adjudication"))
        self.assertEqual(self.paper(self.P1)["citation_status"], "pending_adjudication")

    def test_evaluated_model_confirms_and_d_floor_sends_to_a_person(self):
        self.attach((0, {}), (1, {"verdict": "WEAK", "extra": {"title_similarity": 0.7,
                                                               "title_similarity_subtitle_aware": 0.7}}),
                    (2, {"verdict": "WEAK", "extra": {"title_similarity": 0.9, "title_similarity_subtitle_aware": 0.9,
                                                      "author_check": {"status": "unchecked", "reason": "the cited "
                                                                       "author reads as an organization"}}}),
                    (3, {"verdict": "WEAK", "extra": {"title_similarity": 0.9,
                                                      "title_similarity_subtitle_aware": 0.9}}))
        with mock.patch.dict(lc.ADJUDICATOR_EVALUATED_LISTS, {"adjudicator-list-none": (lc.demo_evaluated_entry(),)}):
            self.assertEqual(self.adjudicate("t1", None), [0, 0], self.steps[-1][2])
        st = {k: self.paper(k)["citation_status"] for k in (self.P1, self.P2, self.P3, lc.DEMO_PAPERS[3]["key"])}
        self.assertEqual(st, {self.P1: "model_confirmed", self.P2: "unverified", self.P3: "unverified",
                              lc.DEMO_PAPERS[3]["key"]: "model_adjudicated"})
        floor = {r["paper_key"]: r["title_floor_applied"] for r in self.table("citation_adjudications")
                 if r["batch_id"] == "t1"}
        self.assertEqual((floor[self.P2], floor[self.P3], floor[self.P1]), (True, True, False))

    def test_a_audit_read_outside_the_bundle_refuses_the_batch(self):
        self.attach((0, {}))
        codes = self.adjudicate("t1", [self.P1], extra_targets=[("Read", str(self.pd / "lit_search" / "verify" /
                                                                             "MANIFEST.jsonl"))])
        self.assertEqual(codes, [0, 11], self.steps[-1][2])
        self.assertIn("not the bundle", self.steps[-1][2])
        self.assertEqual(self.paper(self.P1)["citation_status"], "pending_adjudication")

    def test_a_audit_wrong_agent_or_no_record(self):
        self.attach((0, {}))
        lc.demo_adjudicate(self.step, self.steps, str(self.pd), "t1", keys=[self.P1], ingest=False)
        bundle = os.path.realpath(self.pd / "data" / "adjudication_bundles" / "t1.json")
        for name, targets, kw in (("other agent type", [("Read", bundle)], {"agent_type": "search-agent"}),
                                  ("no record", [], {}), ("clean control", [("Read", bundle)], {})):
            with self.subTest(name):
                agent = f"x{uuid.uuid4().hex[:6]}"
                log = lc.demo_audit_log(str(self.pd), agent, targets, **kw)
                lc.demo_transcript(str(self.pd), agent, [lc.DEMO_ADJ_MODEL])       # the packed model ran
                code, out = self.run_lc("adjudications", "ingest", self.pd, "--batch", "t1", "--agent-id", agent,
                                        paths=dict(lc.demo_adj_paths(str(self.pd)), audit_log=log))
                self.assertEqual(code, 0 if name == "clean control" else 11, out)

    def test_b_bundle_forged_with_its_manifest_row_is_caught_by_the_pack_log(self):
        self.attach((0, {}))
        lc.demo_adjudicate(self.step, self.steps, str(self.pd), "t1", keys=[self.P1], ingest=False)
        bpath = self.pd / "data" / "adjudication_bundles" / "t1.json"
        b = lc.json.loads(bpath.read_text())
        b["rows"][0]["cited"]["title_raw"] = "A Forged Invented Title"
        forged = (lc.json.dumps(b, indent=1, ensure_ascii=False, sort_keys=True) + "\n").encode()
        os.chmod(bpath, 0o644)
        bpath.write_bytes(forged)
        man = self.pd / "data" / "MANIFEST.jsonl"
        lines = man.read_text().splitlines()
        for i, line in enumerate(lines):
            r = lc.json.loads(line)
            if r.get("command") == "adjudications pack" and r.get("batch_id") == "t1":
                lines[i] = lc.json.dumps(dict(r, bundle_sha256=lc.sha256_bytes(forged)), ensure_ascii=False)
        os.chmod(man, 0o644)
        man.write_text("\n".join(lines) + "\n")
        log = next((self.pd / "inputs").glob("audit_fixture_*t1.jsonl"))
        code, out = self.run_lc("adjudications", "ingest", self.pd, "--batch", "t1", "--agent-id",
                                f"{lc.DEMO_ADJ_AGENT}-t1", paths={"audit_log": str(log)})
        self.assertEqual(code, 9, out)

    def latest(self, pattern):
        return max((self.pd / "output").glob(pattern), key=lambda p: int(p.stem.rsplit("_v", 1)[1]))

    def forge_corpus(self, change):
        # A new corpus version with `change(row)` applied to every row, and a consistent data MANIFEST row.
        data = self.pd / "data"
        latest = max(data.glob("corpus_v*.parquet"), key=lambda p: int(p.stem.rsplit("_v", 1)[1]))
        read, write = lc.parquet_io()
        blob = write([change(dict(r)) for r in read(latest.read_bytes())], lc.corpus_columns())
        name = f"corpus_v{int(latest.stem.rsplit('_v', 1)[1]) + 1}.parquet"
        (data / name).write_bytes(blob)
        with open(data / "MANIFEST.jsonl", "a") as f:
            f.write(lc.json.dumps({"kind": "lit_corpus", "command": "forged (test)", "exit_code": 0, "artifacts": [
                {"table": "corpus", "name": name, "path": f"data/{name}", "sha256": lc.sha256_bytes(blob)}]}) + "\n")

    def ingest_again(self, batch, paths):
        return self.run_lc("adjudications", "ingest", self.pd, "--batch", batch, "--agent-id",
                           f"{lc.DEMO_ADJ_AGENT}-{batch}", paths=paths)

    def test_evaluated_identity_each_dimension_alone_keeps_uncertain(self):
        # the evaluated list holds an entry differing from the dispatch's identity in ONE dimension (model, template,
        #   rubric, agent file): the model's SAME_WORK still counts UNCERTAIN. The exact entry (control) confirms.
        e = lc.demo_evaluated_entry()
        cases = [("model", ("another-model",) + e[1:]), ("template", (e[0], "0" * 64) + e[2:]),
                 ("rubric", e[:2] + ("fixture-rubric-v2", e[3])), ("agent file", e[:3] + ("1" * 64,)),
                 ("exact (control)", e)]
        for n, (name, entry) in enumerate(cases):
            with self.subTest(name):
                self.attach((0, {}))
                with mock.patch.dict(lc.ADJUDICATOR_EVALUATED_LISTS, {"adjudicator-list-none": (entry,)}):
                    self.assertEqual(self.adjudicate(f"t{n}", [self.P1]), [0, 0], self.steps[-1][2])
                led = [r for r in self.table("citation_adjudications") if r["batch_id"] == f"t{n}"][0]
                want = ("SAME_WORK", "model_confirmed") if entry == e else ("UNCERTAIN", "pending_adjudication")
                self.assertEqual((led["verdict"], led["effective_verdict"], led["citation_status"]),
                                 ("SAME_WORK",) + want)
                self.assertEqual((led["template_sha256"], led["rubric_version"], led["agent_file_sha256"],
                                  led["agent_file_sha256_at_ingest"]), e[1:] + (e[3],))
        b = lc.json.loads((self.pd / "data" / "adjudication_bundles" / "t0.json").read_text())
        self.assertEqual((b["template_sha256"], b["agent_file_sha256"], b["agent_file"]),
                         (e[1], e[3], ".claude/agents/citation-adjudicator.md"))
        self.assertIn(f"template_sha256={e[1]} agent_file_sha256={e[3]}", self.steps[0][2])

    def test_agent_file_edited_after_the_pack_counts_unevaluated(self):
        # the exact identity is on the list, but the agent file changed between pack and ingest
        self.attach((0, {}))
        e = lc.demo_evaluated_entry()
        paths = lc.demo_adjudicate(self.step, self.steps, str(self.pd), "t1", keys=[self.P1], ingest=False)
        agent = Path(paths["agent_file"])
        os.chmod(agent, 0o644)
        agent.write_text(agent.read_text() + "An edited line.\n")
        with mock.patch.dict(lc.ADJUDICATOR_EVALUATED_LISTS, {"adjudicator-list-none": (e,)}):
            code, out = self.ingest_again("t1", paths)
        self.assertEqual(code, 0, out)
        self.assertIn("WARNING: the adjudicator's agent file", out)
        led = [r for r in self.table("citation_adjudications") if r["batch_id"] == "t1"][0]
        self.assertEqual((led["effective_verdict"], led["citation_status"]), ("UNCERTAIN", "pending_adjudication"))
        self.assertNotEqual(led["agent_file_sha256_at_ingest"], led["agent_file_sha256"])

    def test_bundle_claiming_another_template_is_refused(self):
        # a forger rewrites the bundle's template hash (with the pack log and the pack row to match); the dispatched
        #   prompt is still the fixture template filled with the bundle path, so ingest refuses (exit 9)
        self.attach((0, {}))
        paths = lc.demo_adjudicate(self.step, self.steps, str(self.pd), "t1", keys=[self.P1], ingest=False)
        b = lc.json.loads((self.pd / "data" / "adjudication_bundles" / "t1.json").read_text())
        self.rewrite_pack("t1", dict(b, template_sha256="f" * 64))
        code, out = self.ingest_again("t1", paths)
        self.assertEqual(code, 9, out)
        self.assertIn("is not the template its bundle names", out)
        # control: the same rewrite with the true hash ingests
        self.rewrite_pack("t1", b)
        self.assertEqual(self.ingest_again("t1", paths)[0], 0)

    def test_override_binds_to_the_record_the_regrade_compared(self):
        miss = dict(lc.demo_work_json(lc.DEMO_PAPERS[2]), display_name="A Completely Different Invented Dentistry Study")
        m = self.attach((2, {"work": miss}))[self.P3]
        self.assertIsNone(self.paper(self.P3)["verify_record_json"])
        code, out = self.human([m], "override_mismatch", "Keep it; the index renamed it.", "Same DOI, renamed.")
        self.assertEqual(code, 0, out)
        rec = lc.canon(lc.openalex_meta(miss))
        led = next(r for r in self.table("citation_adjudications") if r["verify_row_sha256"] == m
                   and not r["superseded_by"])
        self.assertEqual((led["citation_status"], led["override_record_json"]), ("human_overridden", rec))
        self.assertEqual(self.paper(self.P3)["verify_record_json"], rec)
        code, out = self.run_lc("export-bib", self.pd)
        self.assertEqual(code, 0, out)
        bib = self.latest("references_v*.bib").read_text()
        entry = bib.split("@")[[i for i, x in enumerate(bib.split("@")) if self.P3 in x][0]]
        self.assertIn("Dentistry", entry)
        self.assertIn("daaf_citation_status = {human_overridden}", entry)
        # attaching the same check again keeps the override and its record
        self.assertEqual(self.run_lc("attach", "verify", self.pd, self.jsonl([{"row_sha256": m,
                                                                               "paper_key": self.P3}]))[0], 0)
        self.assertEqual((self.paper(self.P3)["citation_status"], self.paper(self.P3)["verify_record_json"]),
                         ("human_overridden", rec))
        # a later defer on the row: no override binds, so the record is no longer the paper's reference record
        self.assertEqual(self.human([m], "defer", "Not sure now.", None)[0], 0)
        self.assertEqual((self.paper(self.P3)["citation_status"], self.paper(self.P3)["verify_record_json"]),
                         ("unverified", None))

    def test_attach_keeps_an_override_only_for_its_record(self):
        # the current ledger row of an override is forged to name another record; attaching the same check again
        #   re-derives the record and finds no override for it: the paper goes back to unverified, no record
        miss = dict(lc.demo_work_json(lc.DEMO_PAPERS[2]), display_name="A Completely Different Invented Dentistry Study")
        m = self.attach((2, {"work": miss}))[self.P3]
        self.assertEqual(self.human([m], "override_mismatch", "Keep it.", "Same DOI.")[0], 0)
        other = lc.canon(lc.openalex_meta(dict(miss, display_name="Another Invented Record Altogether")))
        data = self.pd / "data"
        latest = max(data.glob("citation_adjudications_v*.parquet"), key=lambda p: int(p.stem.rsplit("_v", 1)[1]))
        read, write = lc.parquet_io()
        rows = [dict(r, override_record_json=other) if r["verify_row_sha256"] == m and not r["superseded_by"] else r
                for r in read(latest.read_bytes())]
        blob = write(rows, lc.ledger_columns())
        name = f"citation_adjudications_v{int(latest.stem.rsplit('_v', 1)[1]) + 1}.parquet"
        (data / name).write_bytes(blob)
        with open(data / "MANIFEST.jsonl", "a") as f:
            f.write(lc.json.dumps({"kind": "lit_corpus", "command": "forged (test)", "exit_code": 0, "artifacts": [
                {"table": "citation_adjudications", "name": name, "path": f"data/{name}",
                 "sha256": lc.sha256_bytes(blob)}]}) + "\n")
        self.assertEqual(self.run_lc("attach", "verify", self.pd, self.jsonl([{"row_sha256": m,
                                                                               "paper_key": self.P3}]))[0], 0)
        self.assertEqual((self.paper(self.P3)["citation_status"], self.paper(self.P3)["verify_record_json"]),
                         ("unverified", None))

    def test_override_refused_when_no_record_of_the_paper_can_be_identified(self):
        # the corpus is forged to call the fourth paper's check a MISMATCH, but the check's saved response holds
        #   another paper's record only: no record to bind, so the override is refused and nothing is written
        p4 = lc.DEMO_PAPERS[3]["key"]
        other = lc.demo_verify_row(str(self.pd), lc.DEMO_PAPERS[0])
        self.forge_corpus(lambda r: dict(r, verify_row_sha256=other, verify_verdict="MISMATCH",
                                         citation_status="unverified", adjudication_ref=None)
                          if r["paper_key"] == p4 else r)
        n = len(self.table("citation_adjudications"))
        code, out = self.human([other], "override_mismatch", "Keep it.", "Invented.")
        self.assertEqual(code, 11, out)
        self.assertIn("no single record of the paper can be identified", out)
        self.assertEqual(len(self.table("citation_adjudications")), n)

    def test_bundle_identity_must_be_the_one_the_log_printed(self):
        # a forger rewrites the bundle's agent file hash to the evaluated value (bundle hash in the log and pack row
        #   updated to match) but cannot rewrite what the pack printed before dispatch: ingest refuses (exit 9)
        self.attach((0, {}))
        paths = lc.demo_adjudicate(self.step, self.steps, str(self.pd), "t1", keys=[self.P1], ingest=False)
        b = lc.json.loads((self.pd / "data" / "adjudication_bundles" / "t1.json").read_text())
        e = lc.demo_evaluated_entry()
        for k, v in (("agent_file_sha256", "1" * 64), ("rubric_version", "fixture-rubric-v9")):
            with self.subTest(k):
                self.rewrite_pack("t1", dict(b, **{k: v}), printed=b)
                with mock.patch.dict(lc.ADJUDICATOR_EVALUATED_LISTS, {"adjudicator-list-none": (
                        e[:2] + ("fixture-rubric-v9", "1" * 64),)}):
                    code, out = self.ingest_again("t1", paths)
                self.assertEqual(code, 9, out)
                self.assertIn("is not the one its pack log printed", out)

    def rewrite_pack(self, batch, b, printed=None):
        # A forger's consistent rewrite of one packed batch: the bundle `b`, the captured pack log (printed from the
        #   identity fields of `printed`, by default the bundle's own) and the pack's MANIFEST row.
        p = printed or b
        bpath = self.pd / "data" / "adjudication_bundles" / f"{batch}.json"
        data = (lc.json.dumps(b, indent=1, ensure_ascii=False, sort_keys=True) + "\n").encode()
        os.chmod(bpath, 0o644)
        bpath.write_bytes(data)
        psha = lc.sha256_bytes((self.pd / "data" / "adjudication_bundles" / f"{batch}_prompt.txt").read_bytes())
        shas = [r["row_sha256"] for r in b["rows"]]
        out = (f"ADJUDICATION_PACK batch_id={batch} rows={len(shas)} model_id={lc.DEMO_ADJ_MODEL} "
               f"agent_name=citation-adjudicator prompt_version={p['prompt_version']} "
               f"rubric_version={p['rubric_version']} template_sha256={p['template_sha256']} "
               f"agent_file_sha256={p['agent_file_sha256']} claude_md_sha256={p.get('claude_md_sha256') or 'none'}\n"
               + "".join(f"ADJUDICATION_ROW {s}\n" for s in shas)
               + f"ADJUDICATION_BUNDLE_SHA256 {lc.sha256_bytes(data)} x\nADJUDICATION_PROMPT_SHA256 {psha} y\n")
        for old in (self.pd / "scripts" / "lr_adjudication").glob(f"*{batch}.py"):
            os.chmod(old, 0o644)
            old.unlink()
        lc.demo_pack_log(str(self.pd), batch, out)
        man = self.pd / "data" / "MANIFEST.jsonl"
        lines = man.read_text().splitlines()
        for i, x in enumerate(lines):
            r = lc.json.loads(x)
            if r.get("command") == "adjudications pack" and r.get("batch_id") == batch:
                lines[i] = lc.json.dumps(dict(r, bundle_sha256=lc.sha256_bytes(data), row_sha256s=shas,
                                              template_sha256=p["template_sha256"],
                                              agent_file_sha256=p["agent_file_sha256"],
                                              claude_md_sha256=p.get("claude_md_sha256")))
        os.chmod(man, 0o644)
        man.write_text("\n".join(lines) + "\n")

    def test_full_forgery_of_a_mismatch_row_is_still_refused(self):
        # A forger who rewrites the bundle, the pack log AND the pack row consistently to offer a MISMATCH row: only the
        #   rule-verdict check of ingest stops it (a hard rule finding is never adjudicated).
        miss = dict(lc.demo_work_json(lc.DEMO_PAPERS[2]), display_name="A Completely Different Invented Dentistry Study")
        shas = self.attach((0, {}), (2, {"work": miss}))
        paths = lc.demo_adjudicate(self.step, self.steps, str(self.pd), "t1", keys=[self.P1], ingest=False)
        bpath = self.pd / "data" / "adjudication_bundles" / "t1.json"
        b = lc.json.loads(bpath.read_text())
        entry = lc.search_rows({"pd": os.path.realpath(self.pd), "lit_search": str(self.pd / "lit_search"),
                                "row": {"inputs": []}})[shas[self.P3]]
        no, line = lc.manifest_line(os.path.join(os.path.realpath(self.pd), entry["manifest"]), shas[self.P3])
        b["rows"] = [dict(b["rows"][0], row_sha256=shas[self.P3], manifest_line=line.decode(), manifest_line_no=no,
                          raw_sha256=entry["row"]["raw_sha256"], rule_verdict="MISMATCH", digest=None,
                          digest_sha256=None)]
        self.rewrite_pack("t1", b)
        raw = self.pd / "data" / "adjudication_raw" / "t1.jsonl"
        os.chmod(raw, 0o644)
        raw.write_text(lc.json.dumps({"row_sha256": shas[self.P3], "verdict": "SAME_WORK", "dimension_verdicts": {
            d: "SAME_WORK" for d in b["rows"][0]["dimension"]}, "rationale": "forged"}) + "\n")
        code, out = self.run_lc("adjudications", "ingest", self.pd, "--batch", "t1", "--agent-id",
                                f"{lc.DEMO_ADJ_AGENT}-t1", paths=paths)
        self.assertEqual(code, 11, out)
        self.assertIn("only WEAK and CONFIDENT", out)

    def test_ingest_refusals(self):
        self.attach((0, {}), (1, {}))
        lc.demo_adjudicate(self.step, self.steps, str(self.pd), "t1", keys=[self.P1, self.P2])
        self.assertEqual(self.steps[-1][1], 0, self.steps[-1][2])
        audit = str(next((self.pd / "inputs").glob("audit_fixture_*t1.jsonl")))
        self.assertEqual(self.run_lc("adjudications", "ingest", self.pd, "--batch", "t1", "--agent-id",
                                     f"{lc.DEMO_ADJ_AGENT}-t1", paths={"audit_log": audit})[0], 11)   # twice
        self.attach((0, {}), (1, {}))
        b = lc.demo_adjudicate(self.step, self.steps, str(self.pd), "t2", keys=[self.P1, self.P2], ingest=False)
        rows = [lc.json.loads(x) for x in (self.pd / "data" / "adjudication_raw" / "t2.jsonl").read_text().splitlines()]
        audit = str(next((self.pd / "inputs").glob("audit_fixture_*t2.jsonl")))
        raw = self.pd / "data" / "adjudication_raw" / "t2.jsonl"
        for name, lines in (("not in the bundle", [dict(rows[0], row_sha256="d" * 64)]),
                            ("duplicate", [rows[0], rows[0]]),
                            ("per-dimension rule", [dict(rows[0], dimension_verdicts=dict(
                                rows[0]["dimension_verdicts"], author="DIFFERENT_WORK"))]),
                            ("vocabulary", [dict(rows[0], verdict="PROBABLY")])):
            with self.subTest(name):
                os.chmod(raw, 0o644)
                raw.write_text("".join(lc.json.dumps(x) + "\n" for x in lines))
                code, out = self.run_lc("adjudications", "ingest", self.pd, "--batch", "t2", "--agent-id",
                                        f"{lc.DEMO_ADJ_AGENT}-t2", paths=dict(b, audit_log=audit))
                self.assertEqual(code, 11, out)
        raw.unlink()
        self.assertEqual(self.run_lc("adjudications", "ingest", self.pd, "--batch", "t2", "--agent-id",
                                     f"{lc.DEMO_ADJ_AGENT}-t2", paths=dict(b, audit_log=audit))[0], 10)  # no return
        self.assertEqual(self.run_lc("adjudications", "ingest", self.pd, "--batch", "t9", "--agent-id", "a",
                                     paths={"audit_log": audit})[0], 10)                              # no pack log

    def test_h_record_human_refusals_and_binding(self):
        miss = dict(lc.demo_work_json(lc.DEMO_PAPERS[2]), display_name="A Completely Different Invented Dentistry Study")
        shas = self.attach((0, {}), (1, {"verdict": "WEAK", "extra": {"title_similarity": 0.9}}), (2, {"work": miss}))
        ex = lc.demo_verify_row(str(self.pd), lc.DEMO_PAPERS[3], verdict="EXISTS", cited_title="")
        self.assertEqual(self.run_lc("attach", "verify", self.pd, self.jsonl([{"row_sha256": ex, "paper_key":
                                                                                lc.DEMO_PAPERS[3]["key"]}]))[0], 0)
        c, w, m = shas[self.P1], shas[self.P2], shas[self.P3]
        for name, args, want in (("no user words", ([c], "same_work", None, "r"), 11),
                                 ("empty user words", ([c], "same_work", "  ", "r"), 11),
                                 ("no rationale", ([c], "same_work", "ok", None), 11),
                                 ("override on CONFIDENT", ([c], "override_mismatch", "ok", "r"), 11),
                                 ("same_work on MISMATCH", ([m], "same_work", "ok", "r"), 11),
                                 ("EXISTS row", ([ex], "same_work", "ok", "r"), 11),
                                 ("unknown row", (["e" * 64], "same_work", "ok", "r"), 11),
                                 ("listed twice", ([c, c], "same_work", "ok", "r"), 11)):
            with self.subTest(name):
                code, out = self.human(*args)
                self.assertEqual(code, want, out)
        self.assertEqual(self.paper(self.P1)["citation_status"], "pending_adjudication")        # nothing written
        code, out = self.human([c, w], "same_work", "Both of those look right to me.", "Titles compared.")
        self.assertEqual(code, 0, out)
        code, out = self.human([m], "override_mismatch", "Keep the dentistry one, the index renamed it.",
                               "The record was renamed; the DOI is the cited work.")
        self.assertEqual(code, 0, out)
        led = {r["verify_row_sha256"]: r for r in self.table("citation_adjudications") if not r["superseded_by"]}
        self.assertEqual({k: led[s]["citation_status"] for k, s in ((self.P1, c), (self.P2, w), (self.P3, m))},
                         {self.P1: "human_confirmed", self.P2: "human_confirmed", self.P3: "human_overridden"})
        self.assertEqual(led[c]["human_instruction_verbatim"], "Both of those look right to me.")
        self.assertEqual((led[c]["human_binding"], led[c]["human_decider"]), ("permission_prompt", "researcher"))
        self.assertEqual(self.paper(self.P3)["citation_status"], "human_overridden")
        man = [lc.json.loads(x) for x in (self.pd / "data" / "MANIFEST.jsonl").read_text().splitlines()]
        rh = [r for r in man if r.get("command") == "adjudications record-human" and r["exit_code"] == 0
              and r.get("rows") == [c, w]]                       # one row per reply, listing each row hash
        self.assertEqual(len(rh), 1)
        self.assertEqual(rh[0]["parameters"]["user_words"], "Both of those look right to me.")

    def test_reversal_of_an_evaluated_different_work_is_labelled(self):
        shas = self.attach((1, {"verdict": "WEAK", "extra": {"title_similarity": 0.9,
                                                             "title_similarity_subtitle_aware": 0.9}}))
        with mock.patch.dict(lc.ADJUDICATOR_EVALUATED_LISTS, {"adjudicator-list-none": (lc.demo_evaluated_entry(),)}):
            self.assertEqual(self.adjudicate("t1", [self.P2], verdict="DIFFERENT_WORK"), [0, 0])
            self.assertEqual(self.paper(self.P2)["citation_status"], "rejected")
            self.assertEqual(self.human([shas[self.P2]], "same_work", "It is the same paper.", None)[0], 11)
            self.assertEqual(self.human([shas[self.P2]], "same_work", "It is the same paper.", "Same DOI.")[0], 0)
        self.assertEqual(self.paper(self.P2)["citation_status"], "human_overridden")

    def test_f_retraction_is_never_cleared_and_the_log_hash_is_recorded(self):
        self.attach((0, {"extra": {"retracted": True}}))
        before = self.paper(self.P1)["retraction_json"]
        self.assertEqual(self.adjudicate("t1", [self.P1]), [0, 0], self.steps[-1][2])
        led = [r for r in self.table("citation_adjudications") if r["batch_id"] == "t1"][0]
        log = next((self.pd / "scripts" / "lr_adjudication").glob("*_pack_batch_t1.py"))
        self.assertEqual((led["retracted"], led["batch_log_sha256"]), (True, lc.sha256_bytes(log.read_bytes())))
        self.assertEqual(self.human([led["verify_row_sha256"]], "same_work", "Fine.", "Checked.")[0], 0)
        self.assertEqual(self.paper(self.P1)["retraction_json"], before)
        self.assertEqual(self.paper(self.P1)["citation_status"], "human_confirmed")

    def test_legacy_verified_rule_table_is_read_as_pending(self):
        data = self.pd / "data"
        latest = max(data.glob("corpus_v*.parquet"), key=lambda p: int(p.stem.rsplit("_v", 1)[1]))
        read, write = lc.parquet_io()
        rows = [dict(r, citation_status="verified_rule", adjudication_ref=None) if r["paper_key"] == self.P1 else r
                for r in read(latest.read_bytes())]
        blob = write(rows, lc.corpus_columns())
        name = f"corpus_v{int(latest.stem.rsplit('_v', 1)[1]) + 1}.parquet"
        (data / name).write_bytes(blob)
        with open(data / "MANIFEST.jsonl", "a") as f:
            f.write(lc.json.dumps({"kind": "lit_corpus", "command": "legacy table (test)", "exit_code": 0, "artifacts": [
                {"table": "corpus", "name": name, "path": f"data/{name}", "sha256": lc.sha256_bytes(blob)}]}) + "\n")
        code, out = self.run_lc("adjudications", "glance-sheet", self.pd, "--keys", self.P1)
        self.assertEqual(code, 0, out)
        md = max((self.pd / "output").glob("reference_glance_v*.md"), key=lambda p: int(p.stem.rsplit("_v", 1)[1]))
        self.assertIn("matches the record; not yet confirmed", md.read_text())
        code, out = self.run_lc("export-bib", self.pd)
        self.assertEqual(code, 0, out)
        bib = (self.pd / "output" / "references_v2.bib").read_text()
        self.assertEqual(bib.count("daaf_citation_status = {pending_adjudication}"), 1)
        self.assertNotIn("verified_rule", bib)

    def test_glance_sheet_plain_words_and_rows_file(self):
        miss = dict(lc.demo_work_json(lc.DEMO_PAPERS[1]), display_name="A Completely Different Invented Dentistry Study")
        review = dict(lc.demo_work_json(lc.DEMO_PAPERS[2]), type="book-review")
        shas = self.attach((0, {}), (1, {"work": miss}), (2, {"work": review}))
        code, out = self.run_lc("adjudications", "glance-sheet", self.pd)
        self.assertEqual(code, 0, out)
        md = max((self.pd / "output").glob("reference_glance_v*.md"), key=lambda p: int(p.stem.rsplit("_v", 1)[1]))
        text = md.read_text()
        self.assertIn("| # | Reference | Title as cited | Title on record | Authors as cited | Authors on record |", text)
        self.assertIn("matches the record; not yet confirmed", text)
        self.assertIn("does not match the record", text)
        self.assertIn("you confirmed it", text)
        self.assertIn("book review", text)
        for code_word in lc.CITATION_STATUSES + lc.ADJ_VERDICTS + ("CONFIDENT", "WEAK", "MISMATCH", "verified_rule",
                                                                   "row_sha256", "adjudication"):
            self.assertNotIn(code_word, text)
        rows = md.with_name(md.stem + "_rows.txt").read_text()
        self.assertIn(shas[self.P1], rows)
        self.assertIn(shas[self.P3], rows)
        self.assertNotIn(shas[self.P2], rows)                     # a MISMATCH row is not confirmable by a reply
        # plain-language review W3: the status column says where each reference stands; a reply is asked for
        self.assertIn("| Where published | Where it stands |", text)
        self.assertNotIn("What the automatic check said", text)
        self.assertIn("Please read down the list and reply", text)
        # a list with nothing a reply can confirm asks only about keeping a reference whose record does not match
        self.assertEqual(self.run_lc("adjudications", "glance-sheet", self.pd, "--keys", self.P2)[0], 0)
        md = max((self.pd / "output").glob("reference_glance_v*.md"), key=lambda p: int(p.stem.rsplit("_v", 1)[1]))
        self.assertIn("None of these references can be confirmed as they stand. To keep one whose record does not "
                      "match, say so with your reason.", md.read_text())
        self.assertNotIn("Please read down the list", md.read_text())

    # 1.5.0: --keys adds to --deliverable (one sheet, one reply); either flag alone lists what it did before.
    def draft(self, *keys):
        p = self.pd / "inputs" / f"draft_{uuid.uuid4().hex[:6]}.md"
        p.write_text("An invented draft " + "; ".join(f"[@{self.paper(k)['citekey']}]" for k in keys) + ".\n")
        return p

    def glance(self, *flags):
        # (exit code, stdout+stderr, sheet text, rows file text, the command's MANIFEST row)
        before = set((self.pd / "output").glob("reference_glance_v*.md"))
        code, out = self.run_lc("adjudications", "glance-sheet", self.pd, *flags)
        new = set((self.pd / "output").glob("reference_glance_v*.md")) - before
        md = next(iter(new)) if new else None
        row = [lc.json.loads(x) for x in (self.pd / "data" / "MANIFEST.jsonl").read_text().splitlines()][-1]
        return (code, out, md.read_text() if md else "", md.with_name(md.stem + "_rows.txt").read_text() if md else "",
                row)

    def sheet_keys(self, text):
        # citekeys of the sheet's table rows, in sheet order
        return [line.split(" | ")[1] for line in text.splitlines() if re.match(r"^\| \d+ \| ", line)]

    def test_glance_sheet_deliverable_plus_keys_is_one_list_in_order(self):
        p4 = lc.DEMO_PAPERS[3]["key"]
        shas = self.attach((0, {}), (1, {}), (2, {}), (3, {}))           # all four pending again: all confirmable
        code, out, text, rows, row = self.glance("--deliverable", self.draft(self.P3, self.P2), "--keys",
                                                 f"{p4},{self.P1}")
        self.assertEqual(code, 0, out)
        want = [self.P2, self.P3, p4, self.P1]                          # the deliverable's (key order), then added
        self.assertEqual((row["keys"], row["keys_from_deliverable"], row["keys_added"]),
                         (want, [self.P2, self.P3], [p4, self.P1]))
        self.assertEqual(self.sheet_keys(text), [self.paper(k)["citekey"] for k in want])
        self.assertIn("Numbers 1 and 2 are the references cited in inputs/draft_", text)
        self.assertIn("; numbers 3 and 4 were added by name.", text)
        # each rows-file line is that paper's verify row, then "# n citekey" for its number on the sheet
        self.assertEqual([x for x in rows.splitlines() if not x.startswith("#")],
                         [f"{shas[k]}  # {n} {self.paper(k)['citekey']}" for n, k in enumerate(want, 1)])
        self.assertIn("2 cited in inputs/draft_", out)
        # the combined rows file, passed whole, is what one reply confirms
        rows_path = max((self.pd / "output").glob("reference_glance_v*_rows.txt"),
                        key=lambda p: int(p.stem.rsplit("_v", 1)[1].split("_")[0]))
        code, out = self.run_lc("adjudications", "record-human", self.pd, "--rows", rows_path, "--decision",
                                "same_work", "--user-words", "All of them look right.", "--rationale", "Checked each.")
        self.assertEqual(code, 0, out)
        self.assertEqual({self.paper(k)["citation_status"] for k in want}, {"human_confirmed"})
        # the other sentence forms: one cited reference, and ranges of three or more
        p4 = lc.DEMO_PAPERS[3]["key"]
        for cited, named, words in (
                ((self.P1,), (self.P2, self.P3, p4),
                 ("Number 1 is the reference cited in inputs/draft_", "; numbers 2 to 4 were added by name.")),
                ((self.P1, self.P2, self.P3), (p4,),
                 ("Numbers 1 to 3 are the references cited in inputs/draft_", "; number 4 was added by name.")),
                ((self.P1, self.P2), (self.P1,),
                 ("Every reference below is cited in inputs/draft_", "; the paper added by name is already cited "
                                                                     "there.")),
                ((self.P1, self.P2), (self.P2, self.P1),
                 ("Every reference below is cited in inputs/draft_", "; every paper added by name is already cited "
                                                                     "there."))):
            with self.subTest(cited=cited, named=named):
                code, out, text, _, _ = self.glance("--deliverable", self.draft(*cited), "--keys", ",".join(named))
                self.assertEqual(code, 0, out)
                for w in words:
                    self.assertIn(w, text)

    def test_glance_sheet_key_already_cited_is_listed_once(self):
        shas = self.attach((0, {}), (1, {}))
        code, out, text, rows, row = self.glance("--deliverable", self.draft(self.P1, self.P2), "--keys",
                                                 f"{self.P2},{self.P1},{self.P2}")
        self.assertEqual(code, 0, out)
        self.assertEqual((row["keys"], row["keys_added"]), ([self.P1, self.P2], []))
        self.assertEqual(self.sheet_keys(text), [self.paper(k)["citekey"] for k in (self.P1, self.P2)])
        self.assertIn("; every paper added by name is already cited there.", text)
        body = [x.split()[0] for x in rows.splitlines() if not x.startswith("#")]
        self.assertEqual(body, [shas[self.P1], shas[self.P2]])              # record-human refuses a row listed twice
        # a draft that cites none of the corpus's papers: every listed reference was added by name, with a WARNING
        code, out, text, _, row = self.glance("--deliverable", self.draft(), "--keys", self.P3)
        self.assertEqual((code, row["keys"], row["keys_from_deliverable"], row["keys_added"]),
                         (0, [self.P3], [], [self.P3]), out)
        self.assertIn("None of the review's papers is cited in inputs/draft_", text)
        self.assertIn("; every reference below was added by name.", text)
        self.assertIn("WARNING:", out)

    def test_glance_sheet_either_flag_alone_unchanged(self):
        draft = self.draft(self.P3, self.P1)
        code, out, text, _, row = self.glance("--deliverable", draft)
        self.assertEqual(code, 0, out)
        self.assertEqual((row["keys"], row["keys_from_deliverable"], row["keys_added"]),
                         ([self.P1, self.P3], [self.P1, self.P3], None))
        code, out, text2, _, row = self.glance("--keys", f"{self.P3},{self.P1},{self.P3}")
        self.assertEqual(code, 0, out)
        self.assertEqual((row["keys"], row["keys_from_deliverable"], row["keys_added"]),
                         ([self.P3, self.P1], None, [self.P3, self.P1]))   # the order given, a repeat listed once
        self.assertEqual(self.sheet_keys(text2), [self.paper(k)["citekey"] for k in (self.P3, self.P1)])
        for t in (text, text2):
            self.assertNotIn("added by name", t)
            self.assertNotIn("cited in", t)
        # an unknown --keys key is refused with or without a deliverable, and nothing is written
        for flags in (("--keys", f"{self.P1},W1"), ("--deliverable", draft, "--keys", "W1")):
            with self.subTest(flags=flags):
                code, out, text, _, row = self.glance(*flags)
                self.assertEqual((code, text), (11, ""), out)
                self.assertIn("unknown W1", out)
                self.assertEqual(row["refusals"], ["unknown W1"])
        # a --keys that names no key is refused with or without a deliverable (never "every included paper")
        for flags in (("--keys", ","), ("--keys", ""), ("--deliverable", draft, "--keys", ","),
                      ("--deliverable", draft, "--keys", "")):
            with self.subTest(flags=flags):
                code, out, text, _, row = self.glance(*flags)
                self.assertEqual((code, text), (11, ""), out)
                self.assertIn("--keys names no paper key", out)

    # 1.6.0: a MISMATCH or EXISTS reference shows the record found for its identifier, labelled; display only. A NOT
    #   FOUND reference shows no record; a reference kept with override_mismatch shows its bound record unlabelled.
    NOTE = "A title on record that starts with "
    NOTE_MISMATCH = ("A title on record that starts with \"Does not match:\" comes from the database record with the same "
                     "identifier (DOI or database ID) as that reference. The automatic check found that this record "
                     "does not match the citation: its title or its authors differ. If you keep that reference anyway, "
                     "it is cited from this record, with the title on record.")
    NOTE_EXISTS = ("A title on record that starts with \"Not compared:\" comes from the database record with the same "
                   "identifier (DOI or database ID) as that reference; the check did not compare that title with the "
                   "title as cited. It is shown only so you can compare.")
    LEAD = ("Each row puts the title as cited next to the title of the database record found for it, where one was "
            "found. ")
    # 1.7.0 (glance-words-v2): the words that end "Where it stands" for a reference no reply can keep
    LEFT_OUT = "left out of the reference list unless an automatic check matches it"

    def sheet_row(self, text, citekey):
        # the cells of the sheet's table row for one citekey: [number, citekey, title as cited, title on record,
        #   authors as cited, authors on record, years, where published, where it stands]
        return next(line.split(" | ") for line in text.splitlines()
                    if re.match(r"^\| \d+ \| ", line) and line.split(" | ")[1] == citekey)

    def test_glance_sheet_shows_a_non_matching_record_labelled_never_stored(self):
        p2 = lc.DEMO_PAPERS[1]
        miss = dict(lc.demo_work_json(p2), display_name="A Completely Different Invented Dentistry Study")
        shas = self.attach((1, {"work": miss}))
        self.assertEqual((self.paper(self.P2)["verify_verdict"], self.paper(self.P2)["verify_record_json"]),
                         ("MISMATCH", None))
        code, out, text, rows, _ = self.glance("--keys", self.P2)
        self.assertEqual(code, 0, out)
        cells = self.sheet_row(text, self.paper(self.P2)["citekey"])
        self.assertEqual(cells[3], "Does not match: A Completely Different Invented Dentistry Study")
        self.assertEqual(cells[5], "; ".join(p2["authors"]))
        self.assertTrue(cells[6].endswith(f" / {p2['year']}"), cells[6])
        self.assertEqual(cells[7], "Journal of Invented Studies, article")
        self.assertEqual(cells[8], "does not match the record |")
        self.assertIn(self.NOTE_MISMATCH, text)
        self.assertNotIn(self.NOTE_EXISTS, text)                  # one note per label shown
        self.assertIn(self.LEAD, text)
        for code_word in lc.CITATION_STATUSES + lc.ADJ_VERDICTS + ("CONFIDENT", "WEAK", "MISMATCH"):
            self.assertNotIn(code_word, text)
        self.assertNotIn(shas[self.P2], rows)                     # still not confirmable by a reply
        # display only: the corpus stores no record, and the .bib lists neither the paper nor the record
        self.assertIsNone(self.paper(self.P2)["verify_record_json"])
        code, out = self.run_lc("export-bib", self.pd)
        self.assertEqual(code, 0, out)
        bib = self.latest("references_v*.bib").read_text()
        self.assertNotIn(self.P2, bib)
        self.assertNotIn("Dentistry", bib)
        self.assertEqual(bib.count("daaf_citation_status = {human_confirmed}"), 3)   # the other three papers

    def test_glance_sheet_author_mismatch_note_does_not_claim_the_titles_differ(self):
        # review cycle 2 N1: verify gives MISMATCH when the cited --author is on no listed author, with the title
        #   matching; lit_corpus keeps that verdict. The sheet shows the same title on both sides, so the note above
        #   the table must not say the titles differ.
        p2 = lc.DEMO_PAPERS[1]
        sha = lc.demo_search_row(str(self.pd), "verify", "verify", p2["doi"], [], sidecar=False,
                                 raw_requests=[{"backend": "openalex", "endpoint": "https://api.openalex.org/works/doi:"
                                                + p2["doi"], "response": lc.demo_work_json(p2)}],
                                 raw_params={"title": p2["title"], "author": "Zzyzxson"},
                                 row_extra={"verdict": "MISMATCH", "verify_cutoffs": {
                                     "rules_version": lc.sc.VERIFY_RULES_VERSION,
                                     "confident_min": lc.sc.VERIFY_CONFIDENT_MIN},
                                     "title_similarity": 1.0, "title_similarity_subtitle_aware": 1.0})
        code, out = self.run_lc("attach", "verify", self.pd, self.jsonl([{"row_sha256": sha, "paper_key": self.P2}]))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.paper(self.P2)["verify_verdict"], "MISMATCH")
        code, out, text, _, _ = self.glance("--keys", self.P2)
        self.assertEqual(code, 0, out)
        cells = self.sheet_row(text, self.paper(self.P2)["citekey"])
        self.assertEqual((cells[2], cells[3]), (p2["title"], f"Does not match: {p2['title']}"))
        for claim in ("title does not match the title as cited", "titles differ", "title differs"):
            self.assertNotIn(claim, text)
        self.assertIn(self.NOTE_MISMATCH, text)

    def test_glance_sheet_exists_record_labelled_not_found_shows_none(self):
        # EXISTS: the record found for the identifier, labelled "Not compared:". NOT FOUND: no record, although the
        #   check's saved response holds one of the paper (a record beside "no record found" would contradict it).
        p3, p4 = lc.DEMO_PAPERS[2], lc.DEMO_PAPERS[3]
        ex = lc.demo_verify_row(str(self.pd), p3, verdict="EXISTS")
        nf = lc.demo_verify_row(str(self.pd), p4, verdict="NOT FOUND")
        code, out = self.run_lc("attach", "verify", self.pd, self.jsonl([{"row_sha256": ex, "paper_key": self.P3},
                                                                          {"row_sha256": nf, "paper_key": p4["key"]}]))
        self.assertEqual(code, 0, out)
        self.assertEqual([(self.paper(k)["verify_verdict"], self.paper(k)["verify_record_json"])
                          for k in (self.P3, p4["key"])], [("EXISTS", None), ("NOT FOUND", None)])
        code, out, text, _, _ = self.glance("--keys", f"{self.P3},{p4['key']}")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.sheet_row(text, self.paper(self.P3)["citekey"])[3], f"Not compared: {p3['title']}")
        nf_cells = self.sheet_row(text, self.paper(p4["key"])["citekey"])
        self.assertEqual((nf_cells[3], nf_cells[5], nf_cells[7], nf_cells[8]),
                         ("(none recorded)", "(none recorded)", "(none recorded)",
                          f"no record found; {self.LEFT_OUT} |"))
        self.assertIn(self.NOTE_EXISTS, text)
        self.assertNotIn(self.NOTE_MISMATCH, text)
        self.assertIn(self.LEAD, text)
        self.assertEqual([self.paper(k)["verify_record_json"] for k in (self.P3, p4["key"])], [None, None])

    def test_glance_sheet_after_an_override_shows_the_bound_record_unlabelled(self):
        # quality review W5: a reference kept with override_mismatch stores its record (verify_record_json), so the
        #   sheet shows that record as the reference's own: no "Does not match:" label and no note about it. Kills
        #   the mutation that drops the `not rec and` guard.
        miss = dict(lc.demo_work_json(lc.DEMO_PAPERS[2]), display_name="A Completely Different Invented Dentistry Study")
        m = self.attach((2, {"work": miss}))[self.P3]
        code, out = self.human([m], "override_mismatch", "Keep it; the index renamed it.", "Same DOI, renamed.")
        self.assertEqual(code, 0, out)
        row = self.paper(self.P3)
        self.assertEqual((row["verify_verdict"], row["citation_status"]), ("MISMATCH", "human_overridden"))
        rec = lc.jload(row["verify_record_json"])
        code, out, text, _, _ = self.glance("--keys", self.P3)
        self.assertEqual(code, 0, out)
        cells = self.sheet_row(text, row["citekey"])
        self.assertEqual(cells[3], lc.glance_cell(rec["title"]))
        self.assertEqual(cells[3], "A Completely Different Invented Dentistry Study")
        self.assertTrue(cells[8].startswith("accepted by you despite the automatic reference check"), cells[8])
        self.assertNotIn(self.NOTE, text)
        for label in ("Does not match:", "Not compared:"):
            self.assertNotIn(label, text)

    def test_glance_sheet_without_a_record_still_shows_none_recorded(self):
        # the check's saved response holds another paper's record only: no record of this paper to show
        other = lc.demo_verify_row(str(self.pd), lc.DEMO_PAPERS[1], work=lc.demo_work_json(lc.DEMO_PAPERS[0]))
        code, out = self.run_lc("attach", "verify", self.pd, self.jsonl([{"row_sha256": other, "paper_key": self.P2}]))
        self.assertEqual(code, 0, out)
        code, out, text, _, _ = self.glance("--keys", self.P2)
        self.assertEqual(code, 0, out)
        cells = self.sheet_row(text, self.paper(self.P2)["citekey"])
        self.assertEqual((cells[3], cells[5], cells[7]), ("(none recorded)",) * 3)
        self.assertNotIn(self.NOTE, text)

    def test_glance_sheet_confident_and_weak_rows_unchanged(self):
        self.attach((0, {}), (1, {"verdict": "WEAK", "extra": {"title_similarity": 0.9}}))
        code, out, text, _, _ = self.glance("--keys", f"{self.P1},{self.P2}")
        self.assertEqual(code, 0, out)
        for key, verdict in ((self.P1, "CONFIDENT"), (self.P2, "WEAK")):
            with self.subTest(verdict=verdict):
                row = self.paper(key)
                rec = lc.jload(row["verify_record_json"])
                self.assertEqual(row["verify_verdict"], verdict)
                cells = self.sheet_row(text, row["citekey"])
                self.assertEqual((cells[3], cells[5]), (lc.glance_cell(rec["title"]),
                                                        lc.glance_cell("; ".join(rec["authors"]))))
        self.assertNotIn(self.NOTE, text)
        for label in ("Does not match:", "Not compared:"):
            self.assertNotIn(label, text)

    # 1.7.0 (user decision of 2026-11-02): a reference no reply can decide cannot be cited, so the sheet says it will
    #   be left out of the reference list, never that nothing needs a reply.
    def test_glance_sheet_of_only_left_out_references_says_they_are_left_out(self):
        p3, p4 = lc.DEMO_PAPERS[2], lc.DEMO_PAPERS[3]
        ex = lc.demo_verify_row(str(self.pd), p3, verdict="EXISTS")
        nf = lc.demo_verify_row(str(self.pd), p4, verdict="NOT FOUND")
        code, out = self.run_lc("attach", "verify", self.pd, self.jsonl([{"row_sha256": ex, "paper_key": self.P3},
                                                                          {"row_sha256": nf, "paper_key": p4["key"]}]))
        self.assertEqual(code, 0, out)
        code, out, text, rows, _ = self.glance("--keys", f"{self.P3},{p4['key']}")
        self.assertEqual(code, 0, out)
        for claim in ("nothing needs a reply", "already decided"):
            self.assertNotIn(claim, text)
        self.assertIn(self.LEAD + "Numbers 1 and 2 could not be confirmed against a database record, so they will be "
                      "left out of the reference list unless an automatic check matches them. To keep one, ask for it "
                      "to be checked again.\n", text)
        self.assertEqual(self.sheet_row(text, self.paper(self.P3)["citekey"])[8],
                         f"the identifier exists, but its title was not compared; {self.LEFT_OUT} |")
        self.assertEqual(self.sheet_row(text, self.paper(p4["key"])["citekey"])[8], f"no record found; {self.LEFT_OUT} |")
        self.assertEqual([x for x in rows.splitlines() if not x.startswith("#")], [])     # no reply can keep them
        # with a decided reference beside them: one left out (singular words), the rest already decided
        code, out, text, _, _ = self.glance("--keys", f"{self.P1},{p4['key']}")
        self.assertEqual(code, 0, out)
        self.assertIn(self.LEAD + "Number 2 could not be confirmed against a database record, so it will be left out "
                      "of the reference list unless an automatic check matches it. To keep it, ask for it to be "
                      "checked again. Every other reference below is already decided.\n", text)
        self.assertEqual(self.sheet_row(text, self.paper(self.P1)["citekey"])[8], "you confirmed it |")
        self.assertNotIn("nothing needs a reply", text)

    def test_glance_sheet_mixed_names_only_the_left_out_numbers(self):
        # a reference a reply can confirm, one no reply can keep, and one whose record does not match
        miss = dict(lc.demo_work_json(lc.DEMO_PAPERS[2]), display_name="A Completely Different Invented Dentistry Study")
        shas = self.attach((0, {}), (1, {"verdict": "NOT FOUND"}), (2, {"work": miss}))
        code, out, text, rows, _ = self.glance("--keys", f"{self.P1},{self.P2},{self.P3}")
        self.assertEqual(code, 0, out)
        self.assertIn(self.LEAD + "Please read down the list and reply in your own words, for example \"all of them "
                      "look right\" or \"number 3 is a different paper\". One reply can cover the whole list. Number 2 "
                      "could not be confirmed against a database record, so it will be left out of the reference list "
                      "unless an automatic check matches it. To keep it, ask for it to be checked again.\n", text)
        self.assertNotIn("already decided", text)
        self.assertEqual(self.sheet_row(text, self.paper(self.P1)["citekey"])[8],
                         "matches the record; not yet confirmed |")
        self.assertEqual(self.sheet_row(text, self.paper(self.P3)["citekey"])[8], "does not match the record |")
        self.assertEqual([x.split()[0] for x in rows.splitlines() if not x.startswith("#")], [shas[self.P1]])
        # nothing a reply can confirm: the keep-a-mismatch request, then the left-out words
        code, out, text, _, _ = self.glance("--keys", f"{self.P3},{self.P2}")
        self.assertEqual(code, 0, out)
        self.assertIn(self.LEAD + "None of these references can be confirmed as they stand. To keep one whose record "
                      "does not match, say so with your reason. Number 2 could not be confirmed against a database "
                      "record, so it will be left out of the reference list unless an automatic check matches it. To "
                      "keep it, ask for it to be checked again.\n", text)

    # 1.8.0: preparing the adjudicator evaluation. Every word and model ID below is invented.
    def test_glance_sheet_with_decided_references_never_says_none_can_be_confirmed(self):
        # the bundle's papers are decided (confirmed by the researcher); a MISMATCH one beside them: the request says
        #   some are decided and speaks of the others (glance-words-v3)
        miss = dict(lc.demo_work_json(lc.DEMO_PAPERS[2]), display_name="A Completely Different Invented Dentistry Study")
        self.attach((2, {"work": miss}))
        code, out, text, _, _ = self.glance("--keys", f"{self.P1},{self.P3}")
        self.assertEqual(code, 0, out)
        self.assertIn(self.LEAD + "One reference below is already decided. None of the others can be confirmed as "
                      "they stand. To keep one whose record does not match, say so with your reason.\n", text)
        self.assertNotIn("None of these references", text)
        self.assertEqual(self.sheet_row(text, self.paper(self.P1)["citekey"])[8], "you confirmed it |")
        # two decided references: the plural words
        code, out, text, _, _ = self.glance("--keys", f"{self.P1},{self.P2},{self.P3}")
        self.assertEqual(code, 0, out)
        self.assertIn(self.LEAD + "Some references below are already decided. None of the others can be confirmed as "
                      "they stand. To keep one whose record does not match, say so with your reason.\n", text)

    def ingest_with_transcript(self, batch, ran, **kw):
        # pack + return + audit log, a transcript recording `ran`, then ingest: (exit, output, the ingest MANIFEST row)
        paths = lc.demo_adjudicate(self.step, self.steps, str(self.pd), batch, keys=[self.P1], ingest=False, ran=ran,
                                   **kw)
        code, out = self.ingest_again(batch, paths)
        row = [lc.json.loads(x) for x in (self.pd / "data" / "MANIFEST.jsonl").read_text().splitlines()][-1]
        return code, out, row

    def test_model_check_refuses_a_transcript_naming_another_model(self):
        self.attach((0, {}))
        for name, ran in (("another model", ["claude-invented-9"]), ("a change mid-run", [lc.DEMO_ADJ_MODEL, "other"]),
                          ("no model in it", [])):
            with self.subTest(name):
                n = len(self.table("citation_adjudications"))
                batch = f"m{uuid.uuid4().hex[:6]}"
                code, out, row = self.ingest_with_transcript(batch, ran)
                self.assertEqual(code, 11, out)
                self.assertIn("not the packed model", out)
                self.assertEqual((row["command"], row["model_id_observed"]), ("adjudications ingest", ran))
                self.assertTrue(lc.SHA_RE.match(row["model_transcript_sha256"]))
                self.assertEqual(len(self.table("citation_adjudications")), n)                 # nothing written
                self.assertEqual(self.paper(self.P1)["citation_status"], "pending_adjudication")
                self.assertEqual(self.run_lc("adjudications", "release", self.pd, "--batch", batch, "--reason",
                                             "Invented: the transcript names another model.")[0], 0)

    def test_model_check_accepts_the_packed_model_in_another_spelling(self):
        # pack names claude-opus-5-5; the transcript's provider-dotted [1m] spelling is the same model (norm_model)
        self.attach((0, {}))
        code, out, row = self.ingest_with_transcript("t1", ["claude-opus-5.5[1m]", "claude-opus-5-5"],
                                                     model_id="claude-opus-5-5")
        self.assertEqual(code, 0, out)
        led = [r for r in self.table("citation_adjudications") if r["batch_id"] == "t1"][0]
        self.assertEqual((led["model_id"], led["model_id_observed"]),
                         ("claude-opus-5-5", "claude-opus-5.5[1m], claude-opus-5-5"))
        self.assertEqual(row["model_transcript"], os.path.join("-fixture", "fixture-session", "subagents",
                                                               f"agent-{lc.DEMO_ADJ_AGENT}-t1.jsonl"))

    def test_model_check_missing_ambiguous_or_malformed(self):
        self.attach((0, {}))
        paths = lc.demo_adjudicate(self.step, self.steps, str(self.pd), "t1", keys=[self.P1], ingest=False)
        agent = f"{lc.DEMO_ADJ_AGENT}-t1"
        tx = next(Path(paths["transcripts_root"]).rglob(f"agent-{agent}.jsonl"))
        twin = Path(paths["transcripts_root"]) / "-other" / "s2" / "subagents" / tx.name
        twin.parent.mkdir(parents=True)
        shutil.copy(tx, twin)
        self.assertEqual(self.ingest_again("t1", paths)[0], 11)                       # two transcripts for one ID
        twin.unlink()
        os.chmod(tx, 0o644)
        tx.unlink()
        code, out = self.ingest_again("t1", paths)
        self.assertEqual(code, 10, out)                                              # no transcript
        self.assertIn("no Claude Code transcript", out)
        code, out = self.run_lc("adjudications", "ingest", self.pd, "--batch", "t1", "--agent-id", "../x*", paths=paths)
        self.assertEqual(code, 1, out)                                               # outside the id allowlist
        self.assertEqual(self.paper(self.P1)["citation_status"], "pending_adjudication")

    def test_claude_md_is_recorded_and_never_gates(self):
        # the exact identity is evaluated; CLAUDE.md changes between pack and ingest: a WARNING, both hashes kept, and
        #   the judgment still counts (model_confirmed)
        self.attach((0, {}))
        e = lc.demo_evaluated_entry()
        paths = lc.demo_adjudicate(self.step, self.steps, str(self.pd), "t1", keys=[self.P1], ingest=False)
        packed = lc.sha256_bytes(lc.DEMO_CLAUDE_MD.encode())
        b = lc.json.loads((self.pd / "data" / "adjudication_bundles" / "t1.json").read_text())
        self.assertEqual(b["claude_md_sha256"], packed)
        self.assertIn(f"agent_file_sha256={e[3]} claude_md_sha256={packed}", self.steps[0][2])
        cm = Path(paths["claude_md"])
        os.chmod(cm, 0o644)
        cm.write_text(lc.DEMO_CLAUDE_MD + "An edited line.\n")
        with mock.patch.dict(lc.ADJUDICATOR_EVALUATED_LISTS, {"adjudicator-list-none": (e,)}):
            code, out = self.ingest_again("t1", paths)
        self.assertEqual(code, 0, out)
        self.assertIn("WARNING: CLAUDE.md changed", out)
        led = [r for r in self.table("citation_adjudications") if r["batch_id"] == "t1"][0]
        self.assertEqual((led["claude_md_sha256"], led["claude_md_sha256_at_ingest"], led["citation_status"]),
                         (packed, lc.sha256_bytes(cm.read_bytes()), "model_confirmed"))
        self.assertEqual(lc.ADJUDICATOR_EVALUATED_CLAUDE_MD, {lc.ADJUDICATOR_LIST_VERSION: None})
        # every evaluated-list version has its CLAUDE.md record (the mode's identity check reads it by list version)
        self.assertEqual(set(lc.ADJUDICATOR_EVALUATED_CLAUDE_MD), set(lc.ADJUDICATOR_EVALUATED_LISTS))
        # a forged bundle naming another CLAUDE.md than its pack log printed is an integrity stop, as for the identity
        self.attach((0, {}))
        paths = lc.demo_adjudicate(self.step, self.steps, str(self.pd), "t2", keys=[self.P1], ingest=False)
        b2 = lc.json.loads((self.pd / "data" / "adjudication_bundles" / "t2.json").read_text())
        self.rewrite_pack("t2", dict(b2, claude_md_sha256="0" * 64), printed=b2)
        code, out = self.ingest_again("t2", paths)
        self.assertEqual(code, 9, out)

    def test_release_frees_an_uningested_batch_and_never_an_ingested_one(self):
        self.attach((0, {}))
        lc.demo_adjudicate(self.step, self.steps, str(self.pd), "t1", keys=[self.P1], ingest=False)
        paths = lc.demo_adj_paths(str(self.pd))
        pack = ["adjudications", "pack", self.pd, "--model-id", lc.DEMO_ADJ_MODEL, "--keys", self.P1]
        self.assertEqual(self.run_lc(*pack[:3], "--batch", "t2", *pack[3:], paths=paths)[0], 11)   # held in t1
        release = ["adjudications", "release", self.pd, "--batch"]
        self.assertEqual(self.run_lc(*release, "t1")[0], 1)                                       # no --reason
        self.assertEqual(self.run_lc(*release, "t1", "--reason", "  ")[0], 11)                    # empty reason
        self.assertEqual(self.run_lc(*release, "t9", "--reason", "Invented.")[0], 11)             # never packed
        code, out = self.run_lc(*release, "t1", "--reason", "Invented: never dispatched.")
        self.assertEqual(code, 0, out)
        row = [lc.json.loads(x) for x in (self.pd / "data" / "MANIFEST.jsonl").read_text().splitlines()][-1]
        self.assertEqual((row["command"], row["batch_id"], row["row_sha256s"], row["reason"]),
                         ("adjudications release", "t1", [self.paper(self.P1)["verify_row_sha256"]],
                          "Invented: never dispatched."))
        self.assertEqual(row["files_kept"], ["data/adjudication_bundles/t1.json",
                                             "data/adjudication_bundles/t1_prompt.txt"])
        self.assertTrue((self.pd / "data" / "adjudication_bundles" / "t1.json").exists())         # the trail stays
        self.assertEqual(self.run_lc(*release, "t1", "--reason", "Again.")[0], 11)                # already released
        code, out = self.ingest_again("t1", dict(paths, audit_log=str(next((self.pd / "inputs").glob(
            "audit_fixture_*t1.jsonl")))))
        self.assertEqual(code, 11, out)                                                           # never ingested
        self.assertIn("was released", out)
        self.assertEqual(self.adjudicate("t2", [self.P1]), [0, 0], self.steps[-1][2])             # packed again
        code, out = self.run_lc(*release, "t2", "--reason", "Invented.")
        self.assertEqual(code, 11, out)                                                           # ingested
        self.assertIn("was ingested", out)

    # One test per documented rule of the model check, release and the CLAUDE.md records that the module did not yet
    #   pin. Every word and model ID below is invented.
    def packed_with_transcript(self, batch, records):
        # pack + return + audit log + a transcript of the packed model, then the transcript replaced by `records`
        #   (one JSON object per line): (paths, the transcript path)
        paths = lc.demo_adjudicate(self.step, self.steps, str(self.pd), batch, keys=[self.P1], ingest=False)
        tx = next(Path(paths["transcripts_root"]).rglob(f"agent-{lc.DEMO_ADJ_AGENT}-{batch}.jsonl"))
        os.chmod(tx, 0o644)
        tx.write_text("".join(lc.json.dumps(r) + "\n" for r in records))
        return paths, tx

    @staticmethod
    def asst(model, **extra):
        return dict({"type": "assistant", "isSidechain": True, "message": {"model": model, "content": []}}, **extra)

    def last_row(self):
        return [lc.json.loads(x) for x in (self.pd / "data" / "MANIFEST.jsonl").read_text().splitlines()][-1]

    def test_model_check_skips_api_error_records(self):
        # an API-error record naming another model is not a response of that model (the context-reporter rule)
        self.attach((0, {}))
        paths, _ = self.packed_with_transcript("t1", [self.asst("claude-invented-9", isApiErrorMessage=True),
                                                      self.asst(lc.DEMO_ADJ_MODEL)])
        code, out = self.ingest_again("t1", paths)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.last_row()["model_id_observed"], [lc.DEMO_ADJ_MODEL])

    def test_model_check_skips_synthetic_records(self):
        # a "<synthetic>" message.model is Claude Code's own record, never a model that ran
        self.attach((0, {}))
        paths, _ = self.packed_with_transcript("t1", [self.asst("<synthetic>"), self.asst(lc.DEMO_ADJ_MODEL)])
        code, out = self.ingest_again("t1", paths)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.last_row()["model_id_observed"], [lc.DEMO_ADJ_MODEL])

    def test_model_check_refuses_a_transcript_over_the_size_limit(self):
        self.attach((0, {}))
        paths, _ = self.packed_with_transcript("t1", [self.asst(lc.DEMO_ADJ_MODEL)])
        n = len(self.table("citation_adjudications"))
        with mock.patch.object(lc.lv, "TRANSCRIPT_MAX_BYTES", 10):
            code, out = self.ingest_again("t1", paths)
        self.assertEqual(code, 8, out)
        self.assertIn("larger than 512 MiB", out)
        self.assertEqual(len(self.table("citation_adjudications")), n)                         # nothing written

    def test_model_check_reads_only_a_regular_transcript(self):
        # a symlink (even to a file naming the packed model) and a FIFO are refused as unreadable, at once (exit 8)
        self.attach((0, {}))
        paths, tx = self.packed_with_transcript("t1", [self.asst(lc.DEMO_ADJ_MODEL)])
        elsewhere = self.root / "elsewhere.jsonl"
        elsewhere.write_text(lc.json.dumps(self.asst(lc.DEMO_ADJ_MODEL)) + "\n")
        tx.unlink()
        tx.symlink_to(elsewhere)
        code, out = self.ingest_again("t1", paths)
        self.assertEqual(code, 8, out)                                                         # a symlink
        self.assertIn("cannot be read", out)
        tx.unlink()
        os.mkfifo(tx)
        code, out = self.ingest_again("t1", paths)
        self.assertEqual(code, 8, out)                                                         # a FIFO, no wait
        self.assertIn("not a regular file", out)
        tx.unlink()
        self.assertEqual(self.paper(self.P1)["citation_status"], "pending_adjudication")

    def test_release_refuses_a_batch_whose_ledger_rows_exist(self):
        # the ledger alone shows the batch was ingested (its ingest MANIFEST row no longer reads as one): never released
        self.attach((0, {}))
        self.assertEqual(self.adjudicate("t1", [self.P1]), [0, 0], self.steps[-1][2])
        man = self.pd / "data" / "MANIFEST.jsonl"
        lines = man.read_text().splitlines()
        for i, x in enumerate(lines):
            r = lc.json.loads(x)
            if r.get("command") == "adjudications ingest" and r.get("batch_id") == "t1":
                lines[i] = lc.json.dumps(dict(r, command="forged (test)"))
        os.chmod(man, 0o644)
        man.write_text("\n".join(lines) + "\n")
        code, out = self.run_lc("adjudications", "release", self.pd, "--batch", "t1", "--reason", "Invented.")
        self.assertEqual(code, 11, out)
        self.assertIn("was ingested", out)

    def test_pack_row_claude_md_must_match_the_pack_log(self):
        # the pack's MANIFEST row alone names another CLAUDE.md (pack log and bundle intact): an integrity stop
        self.attach((0, {}))
        paths = lc.demo_adjudicate(self.step, self.steps, str(self.pd), "t1", keys=[self.P1], ingest=False)
        man = self.pd / "data" / "MANIFEST.jsonl"
        lines = man.read_text().splitlines()
        for i, x in enumerate(lines):
            r = lc.json.loads(x)
            if r.get("command") == "adjudications pack" and r.get("batch_id") == "t1":
                lines[i] = lc.json.dumps(dict(r, claude_md_sha256="0" * 64))
        os.chmod(man, 0o644)
        man.write_text("\n".join(lines) + "\n")
        code, out = self.ingest_again("t1", paths)
        self.assertEqual(code, 9, out)
        self.assertIn("the pack log and the pack's MANIFEST row disagree", out)

    def test_pack_log_claude_md_must_be_a_sha256(self):
        # a pack log printing a CLAUDE.md value that is neither a sha256 nor "none" is no completed pack run
        self.attach((0, {}))
        paths = lc.demo_adjudicate(self.step, self.steps, str(self.pd), "t1", keys=[self.P1], ingest=False)
        b = lc.json.loads((self.pd / "data" / "adjudication_bundles" / "t1.json").read_text())
        self.rewrite_pack("t1", b, printed=dict(b, claude_md_sha256="xyz"))
        code, out = self.ingest_again("t1", paths)
        self.assertEqual(code, 10, out)
        self.assertIn("no completed pack run", out)

    def test_bundle_without_a_claude_md_field_warns_not_recorded(self):
        # a bundle packed before the field existed (no claude_md_sha256 key; its pack log prints none): ingest says
        #   CLAUDE.md was not recorded, never that it changed, and the batch counts as before
        self.attach((0, {}))
        paths = lc.demo_adjudicate(self.step, self.steps, str(self.pd), "t1", keys=[self.P1], ingest=False)
        b = lc.json.loads((self.pd / "data" / "adjudication_bundles" / "t1.json").read_text())
        old = {k: v for k, v in b.items() if k != "claude_md_sha256"}
        self.rewrite_pack("t1", old)
        code, out = self.ingest_again("t1", paths)
        self.assertEqual(code, 0, out)
        self.assertIn("WARNING: CLAUDE.md was not recorded at the pack", out)
        self.assertNotIn("CLAUDE.md changed", out)

    # 1.8.1: pack takes --model-id only in the form ingest compares (lit_verify.norm_model). Every model ID below is
    #   invented.
    def test_pack_refuses_a_model_id_not_in_the_form_ingest_compares(self):
        # each form norm_model would change is refused (exit 1), the message names the form to pass, nothing is packed
        #   and the value is never rewritten into a bundle
        self.attach((0, {}))
        paths = lc.demo_adj_paths(str(self.pd))
        bdir = self.pd / "data" / "adjudication_bundles"
        bare = "claude-invented-9-9"
        for name, given, norm in (("a trailing [1m]", bare + "[1m]", bare),
                                  ("a dotted Claude ID", "claude-invented-9.9", bare),
                                  ("a dotted Claude ID with [1m]", "claude-invented-9.9[1m]", bare),
                                  ("leading whitespace", " " + bare, bare),
                                  ("trailing whitespace", bare + " ", bare),
                                  ("a trailing newline", bare + "\n", bare),
                                  ("a provider-prefixed dotted ID", "anthropic/claude-invented-9.9",
                                   "anthropic/" + bare)):
            with self.subTest(name):
                data_before = sorted(p.name for p in (self.pd / "data").iterdir() if p.name != "MANIFEST.jsonl")
                bundles_before = sorted(p.name for p in bdir.iterdir())
                code, out = self.run_lc("adjudications", "pack", self.pd, "--batch", "t1", "--model-id", given,
                                        paths=paths)
                self.assertEqual(code, 1, out)
                self.assertIn(f"pass --model-id {norm} instead", out)
                self.assertNotIn("ADJUDICATION_PACK", out)
                self.assertEqual(sorted(p.name for p in bdir.iterdir()), bundles_before)        # nothing packed
                self.assertEqual(sorted(p.name for p in (self.pd / "data").iterdir() if p.name != "MANIFEST.jsonl"),
                                 data_before)                                                  # no table version
                row = self.last_row()
                self.assertEqual((row["command"], row["exit_code"], row["parameters"]["model_id"]),
                                 ("adjudications pack", 1, given))
                self.assertNotIn("bundle_sha256", row)
        self.assertEqual(self.paper(self.P1)["citation_status"], "pending_adjudication")

    def test_pack_takes_a_model_id_already_in_that_form_unchanged(self):
        # a bare ID packs and is recorded byte for byte; a provider-prefixed ID that norm_model leaves unchanged packs
        #   too (it is not stripped: ingest then needs the transcript to record that same spelling)
        self.attach((0, {}), (1, {}))
        paths = lc.demo_adj_paths(str(self.pd))
        for batch, key, given in (("t1", self.P1, "claude-invented-9-9"), ("t2", self.P2, "anthropic/claude-invented-9-9")):
            with self.subTest(given):
                code, out = self.run_lc("adjudications", "pack", self.pd, "--batch", batch, "--model-id", given,
                                        "--keys", key, paths=paths)
                self.assertEqual(code, 0, out)
                self.assertIn(f" model_id={given} ", out)
                self.assertEqual((self.last_row()["exit_code"], self.last_row()["model_id"]), (0, given))
                self.assertTrue((self.pd / "data" / "adjudication_bundles" / f"{batch}.json").exists())

    def test_attach_verify_refuses_a_row_with_no_verdict(self):
        # review cycle 3 C1: a verify call that failed before grading writes a row with no verdict, which
        #   verify_regrade would read as MISMATCH; attach refuses it (exit 11), and nothing is written, not even the
        #   good row in the same map.
        p3 = lc.DEMO_PAPERS[2]
        before = (self.paper(self.P1)["verify_row_sha256"], self.paper(self.P3)["verify_row_sha256"])
        unfinished = lc.demo_search_row(str(self.pd), "verify", "verify", p3["doi"], [], sidecar=False,
                                        raw_requests=[{"backend": "openalex", "response": lc.demo_work_json(p3)}],
                                        raw_params={"title": p3["title"]}, row_extra={"exit_code": 12})
        good = lc.demo_verify_row(str(self.pd), lc.DEMO_PAPERS[0])
        for name, sha in (("no verdict field", unfinished),
                          ("verdict null", lc.demo_verify_row(str(self.pd), p3, verdict=None)),
                          ("a verdict verify never gives", lc.demo_verify_row(str(self.pd), p3, verdict="PENDING"))):
            with self.subTest(name):
                code, out = self.run_lc("attach", "verify", self.pd, self.jsonl(
                    [{"row_sha256": good, "paper_key": self.P1}, {"row_sha256": sha, "paper_key": self.P3}]))
                self.assertEqual(code, 11, out)
                row = [lc.json.loads(x) for x in (self.pd / "data" / "MANIFEST.jsonl").read_text().splitlines()][-1]
                self.assertEqual((row["exit_code"], row["artifacts"]), (11, []))
                self.assertEqual(row["refusals"], [f"line 2: verify row {sha[:12]} records no verdict that verify "
                                                   "gives (the check did not finish, or the row was changed); run the "
                                                   "check again and attach the new row"])
        self.assertEqual((self.paper(self.P1)["verify_row_sha256"], self.paper(self.P3)["verify_row_sha256"]), before)
        # a finished check of the same paper is attached
        done = lc.demo_verify_row(str(self.pd), p3, verdict="MISMATCH")
        self.assertEqual(self.run_lc("attach", "verify", self.pd, self.jsonl([{"row_sha256": done,
                                                                               "paper_key": self.P3}]))[0], 0)
        self.assertEqual(self.paper(self.P3)["verify_row_sha256"], done)

    def test_glance_sheet_authors_as_cited_is_the_author_the_check_looked_for(self):
        # quality review I6 / review cycle 3 C4: where a check was run with --author (and --first-author), "Authors as
        #   cited" shows that name, so an author-only mismatch is visible; display only, nothing stored changes.
        p2, p3 = lc.DEMO_PAPERS[1], lc.DEMO_PAPERS[2]

        def checked(p, params, verdict):
            return lc.demo_search_row(str(self.pd), "verify", "verify", p["doi"], [], sidecar=False,
                                      raw_requests=[{"backend": "openalex", "response": lc.demo_work_json(p)}],
                                      raw_params=dict(params, title=p["title"]),
                                      row_extra={"verdict": verdict, "verify_cutoffs": {
                                          "rules_version": lc.sc.VERIFY_RULES_VERSION,
                                          "confident_min": lc.sc.VERIFY_CONFIDENT_MIN},
                                          "title_similarity": 1.0, "title_similarity_subtitle_aware": 1.0})
        vmap = [{"row_sha256": checked(p2, {"author": "Zzyzxson"}, "MISMATCH"), "paper_key": self.P2},
                {"row_sha256": checked(p3, {"author": "Chen", "first_author": True}, "CONFIDENT"),
                 "paper_key": self.P3}]
        self.assertEqual(self.run_lc("attach", "verify", self.pd, self.jsonl(vmap))[0], 0)
        stored = {k: self.paper(k)["authors_json"] for k in (self.P1, self.P2, self.P3)}
        code, out, text, _, row = self.glance("--keys", f"{self.P1},{self.P2},{self.P3}")
        self.assertEqual(code, 0, out)
        c1, c2, c3 = (self.sheet_row(text, self.paper(k)["citekey"]) for k in (self.P1, self.P2, self.P3))
        self.assertEqual((c2[4], c2[5]), ("Zzyzxson (the name the check looked for)", "Ben Baker"))
        self.assertEqual((c3[4], c3[5]), ("Chen (the name the check looked for as first author)", "Cy Chen"))
        self.assertEqual(c1[4], "; ".join(lc.DEMO_PAPERS[0]["authors"]))           # checked without --author
        self.assertEqual({k: self.paper(k)["authors_json"] for k in stored}, stored)
        self.assertEqual({a["table"] for a in row["artifacts"]}, {None})                # the sheet writes no table

    def test_glance_sheet_authors_as_cited_is_escaped_and_keeps_its_explanation(self):
        # the --author a check ran with is untrusted text: a pipe is escaped and a newline folded, so the table keeps
        #   its nine columns; a long name is cut before the explanation is added, so the explanation stays whole.
        p1, p4 = lc.DEMO_PAPERS[0], lc.DEMO_PAPERS[3]

        def checked(p, params):
            return lc.demo_search_row(str(self.pd), "verify", "verify", p["doi"], [], sidecar=False,
                                      raw_requests=[{"backend": "openalex", "response": lc.demo_work_json(p)}],
                                      raw_params=dict(params, title=p["title"]),
                                      row_extra={"verdict": "CONFIDENT", "verify_cutoffs": {
                                          "rules_version": lc.sc.VERIFY_RULES_VERSION,
                                          "confident_min": lc.sc.VERIFY_CONFIDENT_MIN},
                                          "title_similarity": 1.0, "title_similarity_subtitle_aware": 1.0})
        vmap = [{"row_sha256": checked(p1, {"author": "Evil | Pipe\nNew line"}), "paper_key": self.P1},
                {"row_sha256": checked(p4, {"author": "Z" * 320, "first_author": True}), "paper_key": p4["key"]}]
        self.assertEqual(self.run_lc("attach", "verify", self.pd, self.jsonl(vmap))[0], 0)
        code, out, text, _, _ = self.glance("--keys", f"{self.P1},{p4['key']}")
        self.assertEqual(code, 0, out)
        c1 = self.sheet_row(text, self.paper(self.P1)["citekey"])
        self.assertEqual(c1[4], "Evil \\| Pipe New line (the name the check looked for)")
        line = next(x for x in text.splitlines() if x.startswith("| 1 | "))
        self.assertEqual(len(re.findall(r"(?<!\\)\|", line)), 10, line)                 # nine cells, no bare pipe
        self.assertEqual(self.sheet_row(text, self.paper(p4["key"])["citekey"])[4],
                         "Z" * 199 + "… (the name the check looked for as first author)")

    def test_glance_sheet_not_found_check_regraded_to_mismatch_is_left_out(self):
        # a title search that verify graded NOT FOUND, whose saved response still holds the paper's record under a far
        #   title: attach verify re-grades it to MISMATCH, but no reply can decide it (its verify row says NOT FOUND), so
        #   the sheet marks it left out, shows no "Does not match:" record, offers no keep reply, and the decision
        #   command refuses it.
        p3 = lc.DEMO_PAPERS[2]
        far = "A Completely Different Invented Dentistry Study"
        sha = lc.demo_search_row(str(self.pd), "verify", "verify", f'title:"{far}"', [], sidecar=False,
                                 raw_requests=[{"backend": "openalex", "endpoint": "https://api.openalex.org/works",
                                                "response": {"results": [lc.demo_work_json(p3)]}}],
                                 row_extra={"verdict": "NOT FOUND", "exit_code": 11, "verify_cutoffs": {
                                     "rules_version": lc.sc.VERIFY_RULES_VERSION,
                                     "confident_min": lc.sc.VERIFY_CONFIDENT_MIN}})
        code, out = self.run_lc("attach", "verify", self.pd, self.jsonl([{"row_sha256": sha, "paper_key": self.P3}]))
        self.assertEqual(code, 0, out)
        self.assertEqual((self.paper(self.P3)["verify_verdict"], self.paper(self.P3)["citation_status"]),
                         ("MISMATCH", "unverified"))
        code, out, text, rows, _ = self.glance("--keys", self.P3)
        self.assertEqual(code, 0, out)
        cells = self.sheet_row(text, self.paper(self.P3)["citekey"])
        self.assertEqual((cells[3], cells[8]), ("(none recorded)", f"no record found; {self.LEFT_OUT} |"))
        self.assertIn(self.LEAD + "Number 1 could not be confirmed against a database record, so it will be left out "
                      "of the reference list unless an automatic check matches it. To keep it, ask for it to be "
                      "checked again.\n", text)
        for claim in ("say so with your reason", "Does not match:", self.NOTE_MISMATCH):
            self.assertNotIn(claim, text)
        self.assertEqual([x for x in rows.splitlines() if not x.startswith("#")], [])
        n = len(self.table("citation_adjudications"))
        for decision, rationale in (("override_mismatch", "Same DOI."), ("defer", None)):
            with self.subTest(decision):
                code, out = self.human([sha], decision, "Keep it.", rationale)
                self.assertEqual(code, 11, out)
                self.assertIn("its verify row says NOT FOUND", out)
        self.assertEqual(len(self.table("citation_adjudications")), n)                  # nothing written

    def test_record_human_refuses_a_row_whose_verify_row_gives_no_verdict(self):
        # a verify row with no verdict, or with one verify never gives, attached to a table before attach verify refused
        #   such rows: its corpus verdict reads MISMATCH (verify_regrade's fallback), but no reply can decide it, so the
        #   decision command refuses every decision on it and the sheet marks it left out.
        p3 = lc.DEMO_PAPERS[2]
        for verdict in (None, "PENDING"):
            with self.subTest(verdict=verdict):
                sha = lc.demo_verify_row(str(self.pd), p3, verdict=verdict)
                self.forge_corpus(lambda r: dict(r, verify_row_sha256=sha, verify_verdict="MISMATCH",
                                                 verify_record_json=None, citation_status="unverified",
                                                 adjudication_ref=None) if r["paper_key"] == self.P3 else r)
                n = len(self.table("citation_adjudications"))
                for decision, rationale in (("override_mismatch", "Same DOI."), ("defer", None)):
                    code, out = self.human([sha], decision, "Keep it.", rationale)
                    self.assertEqual(code, 11, out)
                    self.assertIn(f"its verify row says {verdict or 'no verdict'}", out)
                self.assertEqual(len(self.table("citation_adjudications")), n)
                code, out, text, _, _ = self.glance("--keys", self.P3)
                self.assertEqual(code, 0, out)
                self.assertEqual(self.sheet_row(text, self.paper(self.P3)["citekey"])[8],
                                 f"no record found; {self.LEFT_OUT} |")
                self.assertIn("Number 1 could not be confirmed against a database record", text)
                self.assertNotIn("Does not match:", text)

    def test_glance_sheet_left_out_row_never_borrows_the_verify_rows_words(self):
        # the check's saved response holds another paper's record only (corpus verdict None) while the verify row says
        #   CONFIDENT, WEAK or MISMATCH: the cell reads "no record found" and the left-out words, never the row's own
        #   words, which would ask for a decision no reply can record.
        for verdict in ("CONFIDENT", "WEAK", "MISMATCH"):
            with self.subTest(verdict=verdict):
                other = lc.demo_verify_row(str(self.pd), lc.DEMO_PAPERS[1], verdict=verdict,
                                           work=lc.demo_work_json(lc.DEMO_PAPERS[0]))
                code, out = self.run_lc("attach", "verify", self.pd, self.jsonl([{"row_sha256": other,
                                                                                  "paper_key": self.P2}]))
                self.assertEqual(code, 0, out)
                self.assertIsNone(self.paper(self.P2)["verify_verdict"])
                code, out, text, _, _ = self.glance("--keys", self.P2)
                self.assertEqual(code, 0, out)
                self.assertEqual(self.sheet_row(text, self.paper(self.P2)["citekey"])[8],
                                 f"no record found; {self.LEFT_OUT} |")
                for words in ("please decide", "does not match the record", "matches the record"):
                    self.assertNotIn(words, text)

    def test_glance_sheet_left_out_request_names_each_kind(self):
        # one sentence names every left-out number ("1, 2 and 3" for three); a reference checked before is to be checked
        #   again, one never checked (its cell "not checked yet" plus the left-out words) is to be checked, and a sheet
        #   holding both kinds names the never-checked numbers apart.
        p4 = lc.DEMO_PAPERS[3]["key"]
        self.attach((0, {"verdict": "NOT FOUND"}), (1, {"verdict": "NOT FOUND"}), (2, {"verdict": "NOT FOUND"}))
        code, out, text, _, _ = self.glance("--keys", f"{self.P1},{self.P2},{self.P3}")
        self.assertEqual(code, 0, out)
        self.assertIn(self.LEAD + "Numbers 1, 2 and 3 could not be confirmed against a database record, so they will be "
                      "left out of the reference list unless an automatic check matches them. To keep one, ask for it "
                      "to be checked again.\n", text)
        self.forge_corpus(lambda r: dict(r, verify_row_sha256=None, verify_verdict=None, verify_record_json=None,
                                         citation_status="unverified", adjudication_ref=None)
                          if r["paper_key"] in (self.P3, p4) else r)
        code, out, text, rows, _ = self.glance("--keys", p4)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.sheet_row(text, self.paper(p4)["citekey"])[8], f"not checked yet; {self.LEFT_OUT} |")
        self.assertIn(self.LEAD + "Number 1 could not be confirmed against a database record, so it will be left out of "
                      "the reference list unless an automatic check matches it. To keep it, ask for it to be checked."
                      "\n", text)
        self.assertNotIn("checked again", text)
        self.assertEqual([x for x in rows.splitlines() if not x.startswith("#")], [])
        for keys, words in (
                (f"{self.P1},{p4}", "Numbers 1 and 2 could not be confirmed against a database record, so they will be "
                                    "left out of the reference list unless an automatic check matches them. Number 2 "
                                    "has not been checked yet: to keep it, ask for it to be checked. To keep the other, "
                                    "ask for it to be checked again.\n"),
                (f"{self.P1},{self.P3},{p4}", "Numbers 1, 2 and 3 could not be confirmed against a database record, so "
                                              "they will be left out of the reference list unless an automatic check "
                                              "matches them. Numbers 2 and 3 have not been checked yet: to keep one of "
                                              "them, ask for it to be checked. To keep the other, ask for it to be "
                                              "checked again.\n"),
                (f"{self.P1},{self.P2},{p4}", "Numbers 1, 2 and 3 could not be confirmed against a database record, so "
                                              "they will be left out of the reference list unless an automatic check "
                                              "matches them. Number 3 has not been checked yet: to keep it, ask for it "
                                              "to be checked. To keep one of the others, ask for it to be checked "
                                              "again.\n"),
                (f"{self.P3},{p4}", "Numbers 1 and 2 could not be confirmed against a database record, so they will be "
                                    "left out of the reference list unless an automatic check matches them. To keep "
                                    "one, ask for it to be checked.\n")):
            with self.subTest(keys=keys):
                code, out, text, _, _ = self.glance("--keys", keys)
                self.assertEqual(code, 0, out)
                self.assertIn(self.LEAD + words, text)


class PackLogParseTests(unittest.TestCase):
    # quality review I1: the exit code and capture status come from the appended log's own header, never from what the
    #   script printed (run_with_capture.sh writes that output as "# " lines too). Every word invented.
    PACK = ("ADJUDICATION_PACK batch_id=b01 rows=1 model_id=claude-opus-5-5 agent_name=citation-adjudicator "
            f"prompt_version=p rubric_version=r template_sha256={'a' * 64} agent_file_sha256={'b' * 64}\n"
            f"ADJUDICATION_ROW {'c' * 64}\nADJUDICATION_BUNDLE_SHA256 {'d' * 64} data/b.json\n"
            f"ADJUDICATION_PROMPT_SHA256 {'e' * 64} data/p.txt\n")

    def log(self, exit_line="# Exit code: 0", capture="# Capture: COMPLETE", stdout=PACK):
        banner = "# " + "=" * 77
        lines = ["print('x')", "", banner, "# EXECUTION LOG", banner, "#", "# Executed: 2026-11-01 00:00:00",
                 "# Command: python3 x.py", "# Duration: 0s", exit_line, capture, "#", "# --- STDOUT ---"] + [
            "# " + x for x in stdout.splitlines()] + ["#", "# --- STDERR ---", "# (captured in STDOUT above via 2>&1)",
                                                      "#", banner]
        return ("\n".join(lines) + "\n").encode()

    def test_header_decides_not_the_scripts_output(self):
        self.assertIsNotNone(lc.parse_pack_log(self.log(), "b01"))
        # the run failed, but the script printed the header's words itself
        printed = "Exit code: 0\nCapture: COMPLETE\n" + self.PACK
        self.assertIsNone(lc.parse_pack_log(self.log("# Exit code: 1", stdout=printed), "b01"))
        self.assertIsNone(lc.parse_pack_log(self.log(capture="# Capture: INCOMPLETE", stdout=printed), "b01"))
        # pack lines printed after the STDOUT block (in the STDERR part) are not read
        tail = self.log().replace(b"# (captured in STDOUT above via 2>&1)", b"# ADJUDICATION_ROW " + b"f" * 64)
        self.assertEqual(lc.parse_pack_log(tail, "b01")["rows"], ["c" * 64])
        # no STDOUT marker: not a complete log
        self.assertIsNone(lc.parse_pack_log(self.log().replace(b"# --- STDOUT ---", b"#"), "b01"))


if __name__ == "__main__":
    unittest.main()
