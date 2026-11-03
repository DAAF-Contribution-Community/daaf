"""Regression fixtures for the two S04 data-recipe corrections.

Guards the `election-data-source-countypres` and `education-data-source-saipe`
skills against regressing to the editorial contradictions the S04 repair removed:
a Common Pitfalls row instructing a bare `mode == 'TOTAL'` filter (which silently
drops ~1,000 counties in 2020+ data), and a worked example thresholding a 0-1
proportion column as if it were 0-100.

Three gates
-----------
1. **Mode reconstruction (behavioral).** Extracts the *live* 3-pattern
   reconstruction code from
   `.claude/skills/election-data-source-countypres/references/mode-reconstruction.md`
   and executes it against a hand-built 2020 fixture frame. The block under test
   is the **first (`python`) fence under the `## Complete Polars Code Pattern`
   heading** — not a copy pasted into this file — so the test fails if the
   reference document drifts. Fence counts are asserted at both the file level
   (`EXPECTED_MR_FENCES`) and the heading level, so a renamed heading or an added
   example fails loudly rather than silently testing nothing.

   The fixture reproduces all three patterns plus the NC-2024 counter-example:
   county A has TOTAL + a breakdown (Pattern 1: keep TOTAL, do not sum to 160),
   county B has breakdowns only (Pattern 2: sum to 75), county C has a single
   empty-string row per candidate group (Pattern 3: reclassify to TOTAL), and
   county D has *two* empty-string rows per group, which
   `mode-reconstruction.md` (Empty-String Mode Detection Logic) requires be left
   as breakdowns rather than reclassified — blind reclassification is what
   corrupted ~202 DEM/REP groups in NC 2024. The naive `mode == "TOTAL"` filter
   keeps exactly one of the four counties; that delta is the regression.

2. **SAIPE scale (behavioral + drift guard).** A 4-row in-memory frame confirms
   the arithmetic consequence of the 0-1 proportion scale: `>= 0.20` keeps 2
   rows, `>= 20` keeps 0. Then a regex sweep over the *live* `saipe/SKILL.md`
   asserts no fenced code block thresholds a `poverty_pct` column at `>= 20`.

3. **countypres pitfall guard (textual).** Asserts the live `countypres/SKILL.md`
   and `references/variable-definitions.md` carry no "always filter
   `mode == 'TOTAL'`" instruction, and that the Common Pitfalls row for cross-year
   mode mismatch routes the reader to `mode-reconstruction.md`.

Design notes
------------
* `polars` is optional: the textual gates (2's drift guard, 3) and all extraction
  are stdlib-only, so this module is safe on a bare CI runner. The behavioral
  fixtures are skipped via `unittest.skipUnless(HAS_POLARS, ...)`.
* All fixtures are in-memory DataFrames; this module writes no files, so no
  scratch directory is created. Were one ever needed it would live under
  `tests/python/_scratch_data_recipes/<uuid>/` (inside the repo, never `/tmp`
  per CLAUDE.md § Scratch Files).
* This module is the framework's own regression suite under `tests/`; the
  CLAUDE.md "no test files" rule governs research pipeline scripts, and the
  standalone-tooling exception covers the classes used here.

Run directly:
  python3 -m unittest discover -s /daaf/tests/python -p 'test_data_recipe_fixtures.py' -v
"""

import re
import unittest
from pathlib import Path

_THIS = Path(__file__).resolve()
REPO_ROOT = _THIS.parents[2]                     # tests/python/ -> tests/ -> /daaf

SKILLS = REPO_ROOT / ".claude" / "skills"
CP_SKILL = SKILLS / "election-data-source-countypres" / "SKILL.md"
CP_VARDEF = SKILLS / "election-data-source-countypres" / "references" / "variable-definitions.md"
CP_MODE_MD = SKILLS / "election-data-source-countypres" / "references" / "mode-reconstruction.md"
SAIPE_SKILL = SKILLS / "education-data-source-saipe" / "SKILL.md"

# Fence inventory of mode-reconstruction.md: 2 under "Complete Polars Code
# Pattern" (python + r) and 2 under "Validation Checklist" (python + r).
# Bump deliberately if the document gains a block; an accidental change fails.
EXPECTED_MR_FENCES = 4
MR_CODE_HEADING = "Complete Polars Code Pattern"

try:  # optional: behavioral fixtures need a DataFrame library, extraction does not
    import polars as pl
    HAS_POLARS = True
except ImportError:  # pragma: no cover - exercised only on bare runners
    pl = None
    HAS_POLARS = False


# --------------------------------------------------------------------------
# Markdown parsing: fence-aware walk (mirrors test_checkpoint_templates.py)
# --------------------------------------------------------------------------

def _parse_md(path):
    """Return document-ordered items: ('heading', level, text) / ('fence', lang, code).

    Fence interiors are consumed wholesale so in-code comment lines
    (`# --- Constants ---`) are never mistaken for document headings.
    """
    lines = path.read_text().splitlines()
    items = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped in ("```python", "```r"):
            lang = "python" if stripped == "```python" else "r"
            j = i + 1
            buf = []
            while j < len(lines) and not lines[j].startswith("```"):
                buf.append(lines[j])
                j += 1
            items.append(("fence", lang, "\n".join(buf)))
            i = j + 1
            continue
        if stripped.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            i = j + 1
            continue
        m = re.match(r"^(#{1,6})\s+(\S.*)$", line)
        if m:
            items.append(("heading", len(m.group(1)), m.group(2).strip()))
        i += 1
    return items


def _fences_under_heading(items, index):
    """Fences belonging to the heading at `items[index]` (up to the next heading
    of the same or higher level)."""
    _, level, _ = items[index]
    out = []
    for kind, a, b in items[index + 1:]:
        if kind == "heading" and a <= level:
            break
        if kind == "fence":
            out.append((a, b))
    return out


def _fenced_code_blocks(path):
    """All fenced code bodies in `path`, any language, in document order."""
    lines = path.read_text().splitlines()
    blocks = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("```"):
            j = i + 1
            buf = []
            while j < len(lines) and not lines[j].startswith("```"):
                buf.append(lines[j])
                j += 1
            blocks.append("\n".join(buf))
            i = j + 1
            continue
        i += 1
    return blocks


# Module-level extraction so a broken reference fails at import, not mid-test.
_MR_ITEMS = _parse_md(CP_MODE_MD)
_MR_ALL_FENCES = [(lang, code) for kind, lang, code in _MR_ITEMS if kind == "fence"]

_MR_HEADING_IDX = [
    i for i, (kind, _lvl, text) in enumerate(_MR_ITEMS)
    if kind == "heading" and text == MR_CODE_HEADING
]

_MR_SECTION_FENCES = (
    _fences_under_heading(_MR_ITEMS, _MR_HEADING_IDX[0]) if _MR_HEADING_IDX else []
)
_MR_PYTHON_BLOCKS = [code for lang, code in _MR_SECTION_FENCES if lang == "python"]
MR_RECONSTRUCTION_CODE = _MR_PYTHON_BLOCKS[0] if _MR_PYTHON_BLOCKS else None


# --------------------------------------------------------------------------
# Fixture construction
# --------------------------------------------------------------------------

# One 2020 frame exercising all three reconstruction patterns plus the NC
# counter-example. One candidate/party per county keeps the group arithmetic
# readable; the reconstruction keys on (county_fips, year, candidate, party).
#
#   A 06001 CA  TOTAL 100 + ELECTION DAY 60  -> Pattern 1, keep 100 (not 160)
#   B 13001 GA  ABSENTEE 40 + ELECTION DAY 35 -> Pattern 2, sum to 75
#   C 49001 UT  one "" row, 80                -> Pattern 3, reclassify to TOTAL
#   D 37001 NC  two "" rows, 30 + 25          -> NOT reclassified; Pattern 2 -> 55
_FIXTURE_ROWS = [
    # (county_fips, year, state_po, state, county_name, candidate, party, mode, candidatevotes, totalvotes)
    (6001, 2020, "CA", "CALIFORNIA", "ALAMEDA", "JOSEPH R BIDEN JR", "DEMOCRAT", "TOTAL", 100, 200),
    (6001, 2020, "CA", "CALIFORNIA", "ALAMEDA", "JOSEPH R BIDEN JR", "DEMOCRAT", "ELECTION DAY", 60, 120),
    (13001, 2020, "GA", "GEORGIA", "APPLING", "JOSEPH R BIDEN JR", "DEMOCRAT", "ABSENTEE", 40, 90),
    (13001, 2020, "GA", "GEORGIA", "APPLING", "JOSEPH R BIDEN JR", "DEMOCRAT", "ELECTION DAY", 35, 90),
    (49001, 2020, "UT", "UTAH", "BEAVER", "JOSEPH R BIDEN JR", "DEMOCRAT", "", 80, 160),
    (37001, 2020, "NC", "NORTH CAROLINA", "ALAMANCE", "JOSEPH R BIDEN JR", "DEMOCRAT", "", 30, 110),
    (37001, 2020, "NC", "NORTH CAROLINA", "ALAMANCE", "JOSEPH R BIDEN JR", "DEMOCRAT", "", 25, 110),
]

_FIXTURE_COLUMNS = [
    "county_fips", "year", "state_po", "state", "county_name",
    "candidate", "party", "mode", "candidatevotes", "totalvotes",
]

# Expected post-reconstruction candidatevotes by county_fips.
_EXPECTED_VOTES = {6001: 100, 13001: 75, 49001: 80, 37001: 55}

# SAIPE: values on the documented 0-1 proportion scale (variable-definitions.md
# SCALE TRAP box). 0.22 and 0.41 are the two districts above a 20% threshold.
_SAIPE_PCT_VALUES = [0.05, 0.185, 0.22, 0.41]

# Drift guard: a fenced code block thresholding a poverty_pct column at >= 20.
_SAIPE_BAD_THRESHOLD = re.compile(r"poverty_pct[^\n]*>= *20\b")

# Drift guard: the retired "always filter mode == 'TOTAL'" instruction.
_ALWAYS_TOTAL = re.compile(r"[Aa]lways filter .*mode ?== ?'TOTAL'")


def _build_fixture_frame():
    """The 2020 fixture frame, with the metadata columns the block carries forward."""
    rows = [
        dict(zip(_FIXTURE_COLUMNS, row)) | {"office": "US PRESIDENT", "version": 20260211}
        for row in _FIXTURE_ROWS
    ]
    return pl.DataFrame(rows)


def _run_reconstruction(frame):
    """Execute the live reconstruction block against `frame`; return (df, namespace).

    The block imports polars itself and mutates a name `df` in place, matching how
    a Stage 6 cleaning script would use it.
    """
    namespace = {"df": frame}
    exec(compile(MR_RECONSTRUCTION_CODE, str(CP_MODE_MD), "exec"), namespace)
    return namespace["df"], namespace


# --------------------------------------------------------------------------
# Gate 1a: extraction integrity
# --------------------------------------------------------------------------

class ModeReconstructionExtractionTests(unittest.TestCase):
    """The block under test must actually be the live reference block."""

    def test_reference_file_exists(self):
        self.assertTrue(CP_MODE_MD.is_file(), f"missing reference: {CP_MODE_MD}")

    def test_total_fence_count_is_stable(self):
        self.assertEqual(
            len(_MR_ALL_FENCES), EXPECTED_MR_FENCES,
            f"{CP_MODE_MD.name} fence count drifted: expected {EXPECTED_MR_FENCES}, "
            f"found {len(_MR_ALL_FENCES)}. Update EXPECTED_MR_FENCES deliberately.",
        )

    def test_code_heading_present_exactly_once(self):
        self.assertEqual(
            len(_MR_HEADING_IDX), 1,
            f"expected exactly one '{MR_CODE_HEADING}' heading in {CP_MODE_MD.name}, "
            f"found {len(_MR_HEADING_IDX)}",
        )

    def test_code_section_has_one_python_and_one_r_fence(self):
        langs = sorted(lang for lang, _ in _MR_SECTION_FENCES)
        self.assertEqual(
            langs, ["python", "r"],
            f"'{MR_CODE_HEADING}' should hold exactly one python and one r fence, got {langs}",
        )

    def test_extracted_block_is_the_reconstruction(self):
        self.assertIsNotNone(MR_RECONSTRUCTION_CODE, "no python fence extracted")
        # Anchor on the block's own step markers, so extracting the wrong fence fails.
        for anchor in (
            "B.1: Classify empty-string mode states",
            "B.2: Reclassify empty-string totals",
            "B.5b: Counties WITHOUT TOTAL",
            "B.6: Post-concat deduplication",
        ):
            self.assertIn(anchor, MR_RECONSTRUCTION_CODE,
                          f"extracted fence is missing anchor {anchor!r}")

    def test_extracted_block_compiles(self):
        compile(MR_RECONSTRUCTION_CODE, str(CP_MODE_MD), "exec")


# --------------------------------------------------------------------------
# Gate 1b: mode reconstruction behavior
# --------------------------------------------------------------------------

@unittest.skipUnless(HAS_POLARS, "polars not available on this host")
class ModeReconstructionBehaviorTests(unittest.TestCase):

    def setUp(self):
        self.raw = _build_fixture_frame()
        self.out, self.namespace = _run_reconstruction(self.raw)

    def test_naive_total_filter_keeps_only_one_county(self):
        """The defect the corrected pitfall row warns about."""
        naive = self.raw.filter(pl.col("mode") == "TOTAL")
        self.assertEqual(naive["county_fips"].n_unique(), 1)
        self.assertEqual(set(naive["county_fips"].to_list()), {6001})

    def test_reconstruction_keeps_every_county(self):
        self.assertEqual(
            set(self.out["county_fips"].to_list()),
            set(_EXPECTED_VOTES),
            "reconstruction dropped or invented a county",
        )

    def test_reconstruction_vote_totals(self):
        actual = {
            row["county_fips"]: row["candidatevotes"]
            for row in self.out.iter_rows(named=True)
        }
        # A=100 (Pattern 1: TOTAL kept, breakdown dropped — not 160)
        # B=75  (Pattern 2: 40 + 35 summed)
        # C=80  (Pattern 3: single "" row reclassified as TOTAL)
        # D=55  (Pattern 2: 30 + 25 summed as breakdowns, NOT reclassified)
        self.assertEqual(actual, _EXPECTED_VOTES)

    def test_pattern_one_does_not_double_count(self):
        """County A must be 100, never 160 — the TOTAL row wins over breakdowns."""
        a_votes = self.out.filter(pl.col("county_fips") == 6001)["candidatevotes"].to_list()
        self.assertEqual(a_votes, [100])

    def test_all_output_rows_are_total_mode(self):
        self.assertEqual(
            self.out.filter(pl.col("mode") != "TOTAL").height, 0,
            "non-TOTAL rows survived reconstruction",
        )

    def test_no_duplicate_county_candidate_groups(self):
        dup = (
            self.out.group_by(["county_fips", "year", "candidate", "party"])
            .len()
            .filter(pl.col("len") > 1)
        )
        self.assertEqual(dup.height, 0, "duplicate groups remain after reconstruction")

    def test_nc_style_multi_empty_rows_classified_as_breakdowns(self):
        """mode-reconstruction.md, Empty-String Mode Detection Logic: more than one
        empty-string row per (county, candidate, party) group means breakdowns.
        Reclassifying them as TOTAL is what corrupted NC 2024."""
        breakdowns = self.namespace["breakdown_state_years"]
        totals = self.namespace["total_state_years"]
        self.assertIn(("NC", 2020), breakdowns)
        self.assertNotIn(("NC", 2020), totals)

    def test_single_empty_row_state_classified_as_totals(self):
        totals = self.namespace["total_state_years"]
        self.assertIn(("UT", 2020), totals)


# --------------------------------------------------------------------------
# Gate 2: SAIPE proportion scale
# --------------------------------------------------------------------------

@unittest.skipUnless(HAS_POLARS, "polars not available on this host")
class SaipeScaleBehaviorTests(unittest.TestCase):

    def setUp(self):
        self.df = pl.DataFrame({"est_population_5_17_poverty_pct": _SAIPE_PCT_VALUES})

    def test_column_is_on_proportion_scale(self):
        """The check documented at variable-definitions.md SCALE TRAP."""
        self.assertLessEqual(self.df["est_population_5_17_poverty_pct"].max(), 1.0)

    def test_proportion_threshold_selects_high_poverty_districts(self):
        kept = self.df.filter(pl.col("est_population_5_17_poverty_pct") >= 0.20)
        self.assertEqual(kept.height, 2)
        self.assertEqual(kept["est_population_5_17_poverty_pct"].to_list(), [0.22, 0.41])

    def test_percent_threshold_silently_selects_nothing(self):
        """The regression: `>= 20` on a 0-1 column returns zero rows, with no error."""
        kept = self.df.filter(pl.col("est_population_5_17_poverty_pct") >= 20)
        self.assertEqual(kept.height, 0)


class SaipeSkillDriftTests(unittest.TestCase):
    """Textual drift guard — runs without polars."""

    def test_skill_file_exists(self):
        self.assertTrue(SAIPE_SKILL.is_file(), f"missing skill: {SAIPE_SKILL}")

    def test_no_fenced_block_thresholds_poverty_pct_at_20(self):
        offenders = [
            block for block in _fenced_code_blocks(SAIPE_SKILL)
            if _SAIPE_BAD_THRESHOLD.search(block)
        ]
        self.assertEqual(
            offenders, [],
            "saipe/SKILL.md has a code block thresholding a poverty_pct column at "
            ">= 20; the column is a 0-1 proportion, so that filter returns zero rows",
        )

    def test_skill_documents_the_proportion_scale(self):
        text = SAIPE_SKILL.read_text()
        self.assertIn("0-1 proportion", text,
                      "saipe/SKILL.md no longer states the 0-1 proportion scale")

    def test_both_language_examples_use_the_proportion_threshold(self):
        text = SAIPE_SKILL.read_text()
        self.assertEqual(
            text.count("est_population_5_17_poverty_pct\") >= 0.20"), 1,
            "expected the Python filtering example to threshold at >= 0.20",
        )
        self.assertEqual(
            text.count("est_population_5_17_poverty_pct >= 0.20"), 1,
            "expected the R filtering example to threshold at >= 0.20",
        )


# --------------------------------------------------------------------------
# Gate 3: countypres pitfall guard
# --------------------------------------------------------------------------

class CountypresPitfallGuardTests(unittest.TestCase):
    """Textual drift guard — runs without polars."""

    def test_target_files_exist(self):
        self.assertTrue(CP_SKILL.is_file(), f"missing skill: {CP_SKILL}")
        self.assertTrue(CP_VARDEF.is_file(), f"missing reference: {CP_VARDEF}")

    def test_no_always_filter_total_instruction(self):
        for path in (CP_SKILL, CP_VARDEF):
            with self.subTest(path=path.name):
                hits = [
                    line for line in path.read_text().splitlines()
                    if _ALWAYS_TOTAL.search(line)
                ]
                self.assertEqual(
                    hits, [],
                    f"{path.name} instructs an unconditional `mode == 'TOTAL'` filter; "
                    "a bare filter drops ~1,000 counties in 2020+ data",
                )

    def test_cross_year_pitfall_row_routes_to_mode_reconstruction(self):
        rows = [
            line for line in CP_SKILL.read_text().splitlines()
            if line.startswith("| Cross-year mode mismatch |")
        ]
        self.assertEqual(len(rows), 1, "expected exactly one cross-year mode pitfall row")
        row = rows[0]
        self.assertEqual(
            row.count("|"), 4,
            "Common Pitfalls must stay a 3-column | Pitfall | Issue | Solution | table",
        )
        self.assertIn("mode-reconstruction.md", row,
                      "the cross-year pitfall row must route to mode-reconstruction.md")

    def test_vote_share_metric_routes_to_mode_reconstruction(self):
        rows = [
            line for line in CP_VARDEF.read_text().splitlines()
            if line.startswith("| Vote share |")
        ]
        self.assertEqual(len(rows), 1, "expected exactly one Vote share derived-metric row")
        self.assertIn("mode-reconstruction.md", rows[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
