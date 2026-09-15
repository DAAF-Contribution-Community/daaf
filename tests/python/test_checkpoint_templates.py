"""Regression suite for the truthful checkpoint/QA code templates.

Guards `agent_reference/QA_CHECKPOINTS.md` and
`agent_reference/VALIDATION_CHECKPOINTS.md` against silently regressing to the
defect class the S03 repair removed: a check that never ran reporting `[PASS]`,
and a verdict line asserting an unqualified pass over checks that never
executed.

What it does
------------
1. **Extraction** — pulls the live template code blocks out of the two markdown
   files by heading (QA: `QA\\d[ab]? .*Script`; VC: `## CP\\d`,
   `## Join-Specific Validation`, `## Substantiveness Validation`, `### CPP\\d`,
   `### CPP-SKILL`) and language fence. The three *auxiliary* inline blocks
   (Python/R Stub Detection, Wiring Check) sit under headings that match none of
   those patterns and carry their own in-code markers, so they live in a separate
   `AUX_BLOCKS` registry rather than being folded into `VC_BLOCKS`. The expected
   block count per registry is asserted, so a heading rename fails loudly rather
   than silently testing nothing.
2. **Syntax gate** — `compile()` on every Python block; `Rscript -e parse()` on
   every R block.
3. **Fixture matrix** — executes the extracted template text against adversarial
   namespaces (missing / empty / zero / NULL / contradictory / unrecognized
   config) plus correct-value controls, and asserts the exact outcome token, the
   count line, and the verdict line for each. Four fixtures are the original
   defect reproductions from the 2026-09-05 review (see `_REGRESSION_ANCHORS`).
4. **Comparator safety** — no per-check line may carry a `CP<n>` / `QA<n>` /
   `CPP<n>` identifier (design contract § 2), because
   `scripts/compare_execution_logs.py` treats such a line as a checkpoint
   verdict.

Design notes
------------
* Third-party imports (`polars`) are optional: the extraction and syntax gates
  are stdlib-only so the module is safe on a bare CI runner. Fixture execution
  is skipped when polars is absent, and R work is skipped when `Rscript` is
  absent.
* Every temporary artifact lives under
  `tests/python/_scratch_checkpoint_templates/<uuid>/` (inside the repo, never
  `/tmp` per CLAUDE.md § Scratch Files) and is removed in teardown.
* This module is the framework's own regression suite under `tests/`; the
  CLAUDE.md "no test files" rule governs research pipeline scripts, and the
  standalone-tooling exception covers the classes/functions used here.

Run directly:
  python3 -m unittest discover -s /daaf/tests/python -p 'test_checkpoint_templates.py' -v
"""

import contextlib
import io
import re
import shutil
import subprocess
import unittest
import uuid
from pathlib import Path

_THIS = Path(__file__).resolve()
REPO_ROOT = _THIS.parents[2]                     # tests/python/ -> tests/ -> /daaf
QA_MD = REPO_ROOT / "agent_reference" / "QA_CHECKPOINTS.md"
VC_MD = REPO_ROOT / "agent_reference" / "VALIDATION_CHECKPOINTS.md"
SCRATCH_ROOT = _THIS.parent / "_scratch_checkpoint_templates"

RSCRIPT = shutil.which("Rscript")

try:  # optional: fixture execution needs a DataFrame library, extraction does not
    import polars as pl
    HAS_POLARS = True
except ImportError:  # pragma: no cover - exercised only on bare runners
    pl = None
    HAS_POLARS = False

try:  # optional: only the CP4 numpy-scalar fixtures need it
    import numpy as np
    HAS_NUMPY = True
except ImportError:  # pragma: no cover - exercised only on bare runners
    np = None
    HAS_NUMPY = False

# The four original defect reproductions retained from the 2026-09-05 review
# (research/2026-09-05_FrameworkDev_ReviewSynthesis/scripts/scratch/direct/).
# Each name below must stay present in this module.
_REGRESSION_ANCHORS = (
    "qa4a_convergence_missing",        # convergence_missing_snippet.txt
    "qa4a_robustness_name_only",       # robustness_missing_snippet.txt
    "cp3_unknown_relationship",        # unknown_row_relationship_snippet.txt
    "qa2_suppression_reported_zero",   # suppression_zero_snippet.txt
)

_IDENTIFIER_ON_CHECK_LINE = re.compile(r"\b(CPP\d|CP\d|QA\d)")


# --------------------------------------------------------------------------
# Markdown parsing: fence-aware walk producing headings and code blocks
# --------------------------------------------------------------------------

def _parse_md(path):
    """Return document-ordered items: ('heading', level, text) / ('fence', lang, code).

    Fence interiors are consumed wholesale so that in-code comment lines
    (`# --- Config ---`) and markdown-inside-code examples are never mistaken
    for document headings.
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
            # A fence in some other language: skip its body too.
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
    """Fences belonging to the heading at `items[index]` (up to the next
    heading of the same or higher level)."""
    _, level, _ = items[index]
    out = []
    for kind, a, b in items[index + 1:]:
        if kind == "heading" and a <= level:
            break
        if kind == "fence":
            out.append((a, b))
    return out


def _split_regions(code):
    """Slice a template block at its `# --- <marker> ---` separators.

    Returns {marker: code}. Lets a fixture run one check in isolation with a
    controlled namespace instead of standing up the whole template's inputs.
    """
    marker_re = re.compile(r"^# --- (.+) ---\s*$")
    regions = {}
    marker = None
    buf = []
    for line in code.splitlines():
        m = marker_re.match(line)
        if m:
            if marker is not None:
                regions[marker] = "\n".join(buf)
            marker = m.group(1)
            buf = []
        elif marker is not None:
            buf.append(line)
    if marker is not None:
        regions[marker] = "\n".join(buf)
    return regions


# --------------------------------------------------------------------------
# Extraction (module import time; cheap — two file reads plus regex)
# --------------------------------------------------------------------------

_QA_HEADING_RE = re.compile(r"^(QA\d[ab]?)\s.*Script")

QA_BLOCKS = {}   # (family, lang) -> code, e.g. ("QA4a", "python")
_qa_items = _parse_md(QA_MD)
for _idx, _item in enumerate(_qa_items):
    if _item[0] != "heading":
        continue
    _m = _QA_HEADING_RE.match(_item[2])
    if not _m:
        continue
    for _lang, _code in _fences_under_heading(_qa_items, _idx):
        QA_BLOCKS[(_m.group(1), _lang)] = _code

# Canonical VC template blocks are the fences carrying a `# --- <X> Validation`
# marker; the other fences in those sections are config stanzas.
_VC_MARKER_RE = re.compile(r"^# --- (CPP-SKILL|CPP\d|CP\d|Join|Substantiveness) Validation", re.M)
_VC_SECTION_RE = re.compile(r"^(CP\d):|^(Join-Specific Validation)|^(Substantiveness Validation)"
                            r"|^(CPP-SKILL):|^(CPP\d):")

VC_BLOCKS = {}       # (family, lang) -> [code, ...]  (Substantiveness has 3 python)
VC_SECTIONS = []     # ordered list of matched section headings
_vc_items = _parse_md(VC_MD)
for _idx, _item in enumerate(_vc_items):
    if _item[0] != "heading":
        continue
    _m = _VC_SECTION_RE.match(_item[2])
    if not _m:
        continue
    _family = next(g for g in _m.groups() if g)
    if _family == "Join-Specific Validation":
        _family = "Join"
    if _family == "Substantiveness Validation":
        _family = "Substantiveness"
    VC_SECTIONS.append(_item[2])
    for _lang, _code in _fences_under_heading(_vc_items, _idx):
        if _VC_MARKER_RE.search(_code):
            VC_BLOCKS.setdefault((_family, _lang), []).append(_code)


# The auxiliary inline blocks are deliberately NOT folded into VC_BLOCKS: their
# headings ("Python Stub Detection (Inline)", "R/Quarto Stub Detection (Inline)",
# "Wiring Check (Inline)") match no `_VC_SECTION_RE` pattern and their in-code
# markers are `# --- Stub Detection: Project Scan ---` / `# --- Wiring Check ---`,
# so widening either regex to catch them would also loosen the canonical-template
# inventory that EXPECTED_VC_*_TOTAL guards. Attaching each matching fence to the
# nearest preceding heading keeps the Wiring block (a level-4 subsection nested
# under the level-3 R stub heading) from being counted twice.
_AUX_MARKER_RE = re.compile(r"^# --- (Stub Detection: Project Scan|Wiring Check) ---\s*$", re.M)
_AUX_HEADINGS = ("Python Stub Detection (Inline)",
                 "R/Quarto Stub Detection (Inline)",
                 "Wiring Check (Inline)")

AUX_BLOCKS = {}      # (heading text, lang) -> code
_aux_heading = None
for _kind, _a, _b in _vc_items:
    if _kind == "heading":
        _aux_heading = _b
        continue
    if _aux_heading in _AUX_HEADINGS and _AUX_MARKER_RE.search(_b):
        AUX_BLOCKS[(_aux_heading, _a)] = _b


def _vc(family, lang="python"):
    blocks = VC_BLOCKS[(family, lang)]
    assert len(blocks) == 1, f"{family}/{lang}: expected 1 canonical block, got {len(blocks)}"
    return blocks[0]


def _aux(heading, lang="python"):
    return AUX_BLOCKS[(heading, lang)]


# Substantiveness ships three Python blocks (data / text / code); select the data
# one by its marker rather than by list position, which a reordering would break.
_SUBST_DATA = next(c for c in VC_BLOCKS[("Substantiveness", "python")]
                   if "# --- Substantiveness Validation: Data ---" in c)


def _qa_region(family, lang, marker):
    return _split_regions(QA_BLOCKS[(family, lang)])[marker]


EXPECTED_QA_FAMILIES = ("QA1", "QA2", "QA3", "QA4a", "QA4b")
EXPECTED_VC_SINGLE = ("CP1", "CP2", "CP3", "CP4", "Join")
EXPECTED_VC_PY_TOTAL = 13   # CP1-4 (4) + Join (1) + Substantiveness (3) + CPP1-4 (4) + CPP-SKILL (1)
EXPECTED_VC_R_TOTAL = 10    # CP1-4 (4) + Join (1) + Substantiveness data (1) + CPP1-4 (4)
EXPECTED_QA_TOTAL = 10      # QA1-QA4b x {python, r}
EXPECTED_AUX_TOTAL = 3      # Stub Detection (python + r) + Wiring Check (python)
AUX_STUB_PY = "Python Stub Detection (Inline)"
AUX_STUB_R = "R/Quarto Stub Detection (Inline)"
AUX_WIRING = "Wiring Check (Inline)"


# --------------------------------------------------------------------------
# Scratch directory management (inside the repo, never /tmp)
# --------------------------------------------------------------------------

def _new_scratch():
    d = SCRATCH_ROOT / uuid.uuid4().hex[:12]
    d.mkdir(parents=True, exist_ok=False)
    return d


def _drop_scratch(d):
    if d is not None and d.exists():
        shutil.rmtree(d)
    # Leave no residue under tests/python/ once the last run's dir is gone.
    with contextlib.suppress(OSError):
        SCRATCH_ROOT.rmdir()


# --------------------------------------------------------------------------
# Python fixture registry
# --------------------------------------------------------------------------

_NOT_APPLICABLE_SEAM = re.compile(r"^not_applicable = \{\}.*$", re.M)


def _set_not_applicable(code, mapping):
    """Rewrite a template's `not_applicable = {}` config seam.

    Templates that own a `# --- Config ---` region reassign the mapping, so a
    namespace-injected value would be discarded. Editing the seam is what an
    executor does, and asserting the seam exists keeps the fixture honest if the
    config line is ever renamed.
    """
    assert len(_NOT_APPLICABLE_SEAM.findall(code)) == 1, \
        "expected exactly one `not_applicable = {}` config seam in the template"
    # A lambda replacement keeps backslash sequences in the reason strings literal.
    return _NOT_APPLICABLE_SEAM.sub(lambda _m: f"not_applicable = {mapping!r}", code)


def _counters(family):
    if family.startswith("QA"):
        return {"passed": 0, "warnings": 0, "blockers": 0,
                "not_verified": 0, "skipped": 0, "info": 0}
    return {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}


KNOWN_AGG_FUNCS = ("sum", "mean", "count", "median", "min", "max")
KNOWN_SIGNS = (-1, 0, 1)
KNOWN_CARDINALITIES = ("1:1", "1:many", "many:1", "many:many")
KNOWN_JOIN_TYPES = ("inner", "left", "right", "outer", "full", "semi", "anti")


def _py_fixtures(scratch):
    """Build the Python fixture registry. Requires polars; call only under the
    HAS_POLARS guard. `scratch` is the per-run scratch directory."""
    # 'x' carries the suppression sentinel -3 in 2 of 4 rows == exactly 50%.
    raw_fx = pl.DataFrame({"x": [-3, -3, 10, 20]})
    clean_fx = pl.DataFrame({"x": [None, None, 10, 20]})
    cp3_frame = pl.DataFrame({"a": [1, 2, 3, 4], "b": [1, 1, 2, 2]})
    good_df = pl.DataFrame({
        "id": list(range(150)),
        "x": [float(i) for i in range(150)],
        "name": [f"n{i}" for i in range(150)],
    })
    allnull_df = pl.DataFrame({"id": list(range(150)), "x": [None] * 150},
                              schema={"id": pl.Int64, "x": pl.Float64})
    skill_ok = _build_fixture_skill(scratch, "good_value_interpretation", substring_trap=False)
    skill_trap = _build_fixture_skill(scratch, "heading_substring", substring_trap=True)

    fx = {}

    # --- Regression anchors (the four original defect reproductions) ---

    fx["qa4a_convergence_missing"] = dict(
        code=_qa_region("QA4a", "python", "Validate: model_convergence"),
        ns={"plan_spec": {"model_results": {}}, "not_applicable": {},
            "qa4a": _counters("QA4a")},
        token="[NOT VERIFIED]", contains=["model_convergence"],
        counter=("qa4a", "not_verified", 1))

    fx["qa4a_robustness_name_only"] = dict(
        code=_qa_region("QA4a", "python", "Validate: robustness"),
        ns={"plan_spec": {"robustness_checks": [{"name": "alt-spec"}]},
            "not_applicable": {}, "KNOWN_SIGNS": KNOWN_SIGNS,
            "qa4a": _counters("QA4a")},
        token="[NOT VERIFIED]", contains=["robustness 'alt-spec'"],
        counter=("qa4a", "not_verified", 1))

    fx["cp3_unknown_relationship"] = dict(
        code=_vc("CP3"),
        ns={"input_df": cp3_frame, "output_df": cp3_frame, "operation": "fixture",
            "preserved_cols": ["a"], "expected_relationship": "smae",
            "not_applicable": {}},
        contains=["[FAIL] row relationship: unrecognized expected_relationship 'smae'",
                  "CP3 VALIDATION: FAILED"],
        raises="CP3 FAILED - see details above")

    fx["qa2_suppression_reported_zero"] = dict(
        code=_qa_region("QA2", "python", "Validate: suppression"),
        ns={"pl": pl, "df": clean_fx, "raw_df": raw_fx,
            "plan_spec": {"suppression_columns": ["x"], "suppression_code": -3,
                          "reported_suppression_rate": {"x": 0.0}},
            "not_applicable": {}, "qa2": _counters("QA2")},
        token="[BLOCKER]", contains=["reported 0.0%", "50.0%", "2/4"],
        counter=("qa2", "blockers", 1))

    fx["qa2_suppression_correct_control"] = dict(
        code=_qa_region("QA2", "python", "Validate: suppression"),
        ns={"pl": pl, "df": clean_fx, "raw_df": raw_fx,
            "plan_spec": {"suppression_columns": ["x"], "suppression_code": -3,
                          "reported_suppression_rate": {"x": 0.5}},
            "not_applicable": {}, "qa2": _counters("QA2")},
        token="[PASS]", contains=["reported 50.0%", "n=2/4"],
        counter=("qa2", "passed", 1))

    # --- Design contract § 6 metric corrections ---

    fx["qa4a_aggregation_zero_source"] = dict(
        code=_qa_region("QA4a", "python", "Validate: aggregation"),
        ns={"pl": pl, "df": pl.DataFrame({"g": ["a"], "v": [5000.0]}),
            "source_df": pl.DataFrame({"g": ["a"], "v": [0.0]}),
            "plan_spec": {"aggregation": {"group_by": "g", "column": "v", "function": "sum"}},
            "not_applicable": {}, "KNOWN_AGG_FUNCS": KNOWN_AGG_FUNCS,
            "qa4a": _counters("QA4a")},
        token="[BLOCKER]", contains=["source=0", "5000"],
        counter=("qa4a", "blockers", 1))

    fx["qa3_unknown_aggregation_function"] = dict(
        code=_qa_region("QA3", "python", "Validate: aggregation"),
        ns={"pl": pl, "df": pl.DataFrame({"g": ["a"], "v": [1.0]}),
            "transform_spec": {"aggregation": {"group_by": "g", "column": "v",
                                               "function": "mode"}},
            "source_dfs": {"input": pl.DataFrame({"g": ["a"], "v": [1.0]})},
            "not_applicable": {}, "KNOWN_AGG_FUNCS": KNOWN_AGG_FUNCS,
            "qa3": _counters("QA3")},
        token="[BLOCKER]", contains=["unrecognized function 'mode'"],
        counter=("qa3", "blockers", 1))

    fx["join_outer_1to1_fanout"] = dict(
        code=_vc("Join"),
        ns={"left_df": pl.DataFrame({"k": list(range(100))}),
            "right_df": pl.DataFrame({"k": list(range(100))}),
            "result_df": pl.DataFrame({"k": [i % 100 for i in range(10000)]}),
            "join_keys": ["k"], "expected_cardinality": "1:1", "join_type": "outer",
            "not_applicable": {}},
        contains=["[FAIL] cardinality: result 10,000 rows exceeds the '1:1'/'outer' "
                  "upper bound of 200",
                  "JOIN VALIDATION: FAILED"],
        raises="Join validation FAILED - see details above")

    fx["join_left_rows_zero"] = dict(
        code=_vc("Join"),
        ns={"left_df": pl.DataFrame({"k": []}, schema={"k": pl.Int64}),
            "right_df": pl.DataFrame({"k": list(range(100))}),
            "result_df": pl.DataFrame({"k": []}, schema={"k": pl.Int64}),
            "join_keys": ["k"], "expected_cardinality": "1:1", "join_type": "inner",
            "not_applicable": {}},
        contains=["[FAIL] row loss: left_df is empty (0 rows)",
                  "JOIN VALIDATION: FAILED"],
        raises="Join validation FAILED - see details above")

    # A declared skip prints its reason, is counted, and leaves the verdict alone.
    fx["cp3_not_applicable_declared"] = dict(
        code=_vc("CP3"),
        ns={"input_df": cp3_frame, "output_df": cp3_frame, "operation": "fixture",
            "preserved_cols": ["a"], "expected_relationship": "same",
            "not_applicable": {"row_relationship":
                               "reshape is row-preserving by construction"}},
        contains=["[SKIPPED] row relationship: reshape is row-preserving by construction",
                  "Checks: 3 passed, 0 warnings, 0 failed, 0 not verified, 1 skipped",
                  "CP3 VALIDATION: PASSED"])

    fx["cp1_empty_required_columns"] = dict(
        code=_vc("CP1"),
        ns={"df": pl.DataFrame({"year": [2020, 2021]}), "expected_rows": 2,
            "required_cols": [], "expected_years": [2020, 2021], "year_col": "year",
            "FLAG_YEARS": [2020], "not_applicable": {}},
        contains=["[NOT VERIFIED] required columns: required_cols is empty",
                  "CP1 VALIDATION: FAILED"],
        raises="CP1 FAILED - see details above")

    fx["cpp2_all_null_numeric_column"] = dict(
        code=_vc("CPP2"),
        ns={"df": allnull_df, "numeric_columns": ["x"], "temporal_expected": False,
            "time_columns_found": None, "not_applicable": {}},
        contains=["[NOT VERIFIED] numeric summary 'x': entirely null over 150 rows",
                  "CPP2 VALIDATION: FAILED"],
        raises="CPP2 FAILED - see details above")

    fx["cpp4_multiline_unhedged_second_line"] = dict(
        code=_vc("CPP4"),
        ns={"data_dictionary_draft": [
                {"column": "a",
                 "interpretation": "[PRELIMINARY] good claim\nunhedged bad claim"}],
            "documentation_provided": False, "reconciliation_ran": None,
            "not_applicable": {}},
        contains=["[FAIL] interpretation 'a': 1 of 2 claim lines unhedged",
                  "CPP4 VALIDATION: FAILED"],
        raises="CPP4 FAILED - see details above")

    fx["cpp_skill_heading_substring_rejected"] = dict(
        code=_vc("CPP-SKILL"),
        ns={"skill_draft_dir": str(skill_trap), "profiled_columns": ["col_a", "col_b"],
            "manual_determinations": dict(_MANUAL_OK), "not_applicable": {}},
        contains=["[FAIL] canonical sections:", "'What is [Source]?'",
                  "CPP-SKILL VALIDATION: FAILED"],
        raises="CPP-SKILL FAILED - see details above")

    fx["cpp_skill_value_interpretation_accepted"] = dict(
        code=_vc("CPP-SKILL"),
        ns={"skill_draft_dir": str(skill_ok), "profiled_columns": ["col_a", "col_b"],
            "manual_determinations": dict(_MANUAL_OK), "not_applicable": {}},
        contains=["[PASS] reference files: all 5 present", "value-interpretation.md",
                  "[PASS] canonical sections: all 8 present in canonical order",
                  "CPP-SKILL VALIDATION: PASSED"])

    # Zero checks run: FAILED for the script-halting family, WARNING for the
    # review-severity family (design contract § 3).
    fx["cp3_zero_checks_run"] = dict(
        code=_vc("CP3"),
        ns={"input_df": cp3_frame, "output_df": cp3_frame, "operation": "fixture",
            "preserved_cols": ["a"], "expected_relationship": "same",
            "not_applicable": {"row_relationship": "declared N/A for this fixture",
                               "row_loss": "declared N/A for this fixture",
                               "new_nulls": "declared N/A for this fixture",
                               "preserved_columns": "declared N/A for this fixture"}},
        contains=["Checks: 0 passed, 0 warnings, 0 failed, 0 not verified, 4 skipped",
                  "CP3 VALIDATION: FAILED"],
        raises="CP3 FAILED - see details above")

    # The QA templates carry their own `# --- Config ---` region, which
    # reassigns `not_applicable = {}`. Injecting the mapping through the
    # namespace would be overwritten, so the fixture edits the config seam the
    # way an executor would.
    fx["qa1_zero_checks_run"] = dict(
        code=_set_not_applicable(
            QA_BLOCKS[("QA1", "python")],
            {"schema": "declared N/A for this fixture",
             "year_coverage": "declared N/A for this fixture",
             "id_uniqueness": "declared N/A for this fixture"}),
        ns={"df": good_df, "plan_spec": {}},
        contains=["Checks: 0 passed, 0 warnings, 0 blockers, 0 not verified, "
                  "3 skipped, 0 info",
                  "QA1 RESULT: WARNING"])

    # --- CP4 (Stage 8) — sub-checks 4.1 and 4.4 ------------------------------
    # The CP4.4 scan reads a real script off disk, so both a correct Stage-8
    # script and a genuinely raw-reading one are materialised in scratch.
    good_script, bad_script = _build_cp4_scripts(scratch)
    cp4_ns = dict(
        analysis_df=pl.DataFrame({"ncessch": ["a", "b"], "enrollment": [1, 2]}),
        critical_columns=["ncessch", "enrollment"],
        min_n=500, expected_signs={}, required_figures=[], figures_dir=str(scratch),
        expected_input_dir="data/processed/", forbidden_input_dir="data/raw/",
        # The figures sub-check has nothing to inspect in an analysis-only fixture;
        # declaring it keeps the fixture's subject (4.1 / 4.4) the only variable.
        not_applicable={"figures": "analysis-only fixture script produces no figure"},
    )
    cp4_results_ok = {"estimates": {"poverty_rate": -0.184}, "n": 8421, "converged": True}
    cp4_pass_counts = ("Checks: 7 passed, 0 warnings, 0 failed, 0 not verified, 2 skipped",
                       "CP4 VALIDATION: PASSED")

    # The CP4.4 self-reference control: a correct script whose own CP4 config
    # assigns forbidden_input_dir = "data/raw/" must still PASS.
    fx["cp4_data_source_self_reference_control"] = dict(
        code=_vc("CP4"),
        ns=dict(cp4_ns, analysis_results=dict(cp4_results_ok),
                script_source_path=str(good_script)),
        contains=["[PASS] data source:", "reads 'data/processed/'"] + list(cp4_pass_counts))

    fx["cp4_data_source_genuine_raw_read"] = dict(
        code=_vc("CP4"),
        ns=dict(cp4_ns, analysis_results=dict(cp4_results_ok),
                script_source_path=str(bad_script)),
        contains=["[FAIL] data source:", "references 'data/raw/'",
                  "Checks: 6 passed, 0 warnings, 1 failed, 0 not verified, 2 skipped",
                  "CP4 VALIDATION: FAILED"],
        raises="CP4 FAILED - see details above")

    # numpy scalars are what estimators actually return; isinstance(v, (int, float))
    # rejected every one of them and turned a valid estimate into a false FAIL.
    if HAS_NUMPY:
        fx["cp4_numpy_scalar_estimate_and_n"] = dict(
            code=_vc("CP4"),
            ns=dict(cp4_ns,
                    analysis_results={"estimates": {"beta": np.float64(-0.184)},
                                      "n": np.int64(8421), "converged": True},
                    script_source_path=str(good_script)),
            contains=["[PASS] estimates finite: all 1 finite", "[PASS] sample size: n=8,421"]
                     + list(cp4_pass_counts))

    # bool subclasses int, so a flag must not be accepted as an estimate.
    fx["cp4_bool_estimate_rejected"] = dict(
        code=_vc("CP4"),
        ns=dict(cp4_ns,
                analysis_results={"estimates": {"beta": True}, "n": 8421, "converged": True},
                script_source_path=str(good_script)),
        contains=["[FAIL] estimates finite:", "beta=True",
                  "Checks: 6 passed, 0 warnings, 1 failed, 0 not verified, 2 skipped",
                  "CP4 VALIDATION: FAILED"],
        raises="CP4 FAILED - see details above")

    # numpy.bool_ is neither a `bool` instance nor `is True`; before the CP4.1
    # convergence-guard fix this reported [NOT VERIFIED] and failed the checkpoint.
    if HAS_NUMPY:
        fx["cp4_numpy_bool_convergence"] = dict(
            code=_vc("CP4"),
            ns=dict(cp4_ns,
                    analysis_results={"estimates": {"beta": -0.184}, "n": 8421,
                                      "converged": np.bool_(True)},
                    script_source_path=str(good_script)),
            contains=["[PASS] convergence: estimator reported converged=True"]
                     + list(cp4_pass_counts))

    # --- CP2 dtype comparability (design contract § 10 numeric guards) --------

    fx["cp2_string_column_vs_int_sentinel"] = dict(
        code=_vc("CP2"),
        ns={"raw_df": pl.DataFrame({"x": ["-3", "-3", "10", "20"]}),
            "clean_df": pl.DataFrame({"x": ["10", "20"]}),
            "key_variables": ["x"], "SUPPRESSION_CODE": -3,
            "CODED_MISSING_VALUES": [-1, -2, -3], "SUPPRESSION_THRESHOLD": 0.5,
            "not_applicable": {}},
        contains=["[NOT VERIFIED] suppression 'x':", "not comparable to sentinel -3",
                  "Checks: 1 passed, 0 warnings, 0 failed, 2 not verified, 0 skipped",
                  "CP2 VALIDATION: FAILED"],
        raises="CP2 FAILED - see details above")

    # Control: a comparable column IS measured and the line carries its numbers.
    # 50% is above the 20% "notable" floor and below the 60% fail threshold, so
    # [WARNING] with evidence is the correct outcome — the point is that the rate
    # is computed at all.
    fx["cp2_numeric_column_rate_computed"] = dict(
        code=_vc("CP2"),
        ns={"raw_df": pl.DataFrame({"x": [-3, -3, 10, 20]}),
            "clean_df": pl.DataFrame({"x": [10, 20]}),
            "key_variables": ["x"], "SUPPRESSION_CODE": -3,
            "CODED_MISSING_VALUES": [-1, -2, -3], "SUPPRESSION_THRESHOLD": 0.6,
            "not_applicable": {}},
        contains=["[WARNING] suppression 'x': 50.0% (n=2/4 sentinel -3) is notable",
                  "Checks: 2 passed, 1 warnings, 0 failed, 0 not verified, 0 skipped",
                  "CP2 VALIDATION: PASSED WITH WARNINGS"])

    # --- Join 1:1 bound is min(left, right), not left -------------------------

    fx["join_1to1_inner_exceeds_min_bound"] = dict(
        code=_vc("Join"),
        ns={"left_df": pl.DataFrame({"k": [1, 2, 3, 4, 5, 6]}),
            "right_df": pl.DataFrame({"k": [1, 2, 3]}),
            "result_df": pl.DataFrame({"k": [1, 1, 2, 2, 3, 3]}),
            "join_keys": ["k"], "expected_cardinality": "1:1", "join_type": "inner",
            "not_applicable": {}},
        contains=["[FAIL] cardinality: result 6 rows exceeds the '1:1'/'inner' "
                  "upper bound of 3",
                  "Checks: 4 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped",
                  "JOIN VALIDATION: FAILED"],
        raises="Join validation FAILED - see details above")

    fx["join_1to1_inner_within_min_bound"] = dict(
        code=_vc("Join"),
        ns={"left_df": pl.DataFrame({"k": [1, 2, 3, 4, 5, 6]}),
            "right_df": pl.DataFrame({"k": [1, 2, 3]}),
            "result_df": pl.DataFrame({"k": [1, 2, 3]}),
            "join_keys": ["k"], "expected_cardinality": "1:1", "join_type": "inner",
            "not_applicable": {}},
        contains=["[PASS] cardinality: result 3 rows within the '1:1'/'inner' "
                  "upper bound of 3",
                  "Checks: 5 passed, 0 warnings, 0 failed, 0 not verified, 0 skipped",
                  "JOIN VALIDATION: PASSED"])

    # --- Join: a declared cardinality contradicted by the inputs is a FAIL -----

    # Design contract § 11: duplicate keys on a side the declaration calls unique
    # are a [FAIL], not a [WARNING]. The row-count bound is satisfied in all three
    # fixtures below, which is exactly why the duplicate-keys check has to be the
    # one that fires: a 1:1 right join over a duplicated right key returns exactly
    # right_rows and used to report PASSED WITH WARNINGS.
    fx["join_1to1_right_dup_keys"] = dict(
        code=_vc("Join"),
        ns={"left_df": pl.DataFrame({"k": [1, 2, 3]}),
            "right_df": pl.DataFrame({"k": [1, 2, 2]}),
            "result_df": pl.DataFrame({"k": [1, 2, 2]}),
            "join_keys": ["k"], "expected_cardinality": "1:1", "join_type": "right",
            "not_applicable": {}},
        contains=["[PASS] cardinality: result 3 rows within the '1:1'/'right' "
                  "upper bound of 3",
                  "[FAIL] duplicate keys 'k': declared 1:1 but left has 0 and "
                  "right has 1 duplicate key rows",
                  "Checks: 4 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped",
                  "JOIN VALIDATION: FAILED"],
        raises="Join validation FAILED - see details above")

    # 1:many with duplicates on the '1' (left) side. Also the row-gain phrasing:
    # 3 left rows in, 4 rows out is a gain, not "-33.3% of left rows lost".
    fx["join_1tomany_left_dup_keys"] = dict(
        code=_vc("Join"),
        ns={"left_df": pl.DataFrame({"k": [1, 1, 2]}),
            "right_df": pl.DataFrame({"k": [1, 2, 2, 3]}),
            "result_df": pl.DataFrame({"k": [1, 1, 2, 2]}),
            "join_keys": ["k"], "expected_cardinality": "1:many", "join_type": "inner",
            "not_applicable": {}},
        contains=["[FAIL] duplicate keys 'k': declared 1:many but the left ('1') "
                  "side has 1 duplicate key rows",
                  "[PASS] row loss: 0 left rows lost; the result gained 1 rows "
                  "over the 3 left rows (33.3% gain",
                  "Checks: 4 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped",
                  "JOIN VALIDATION: FAILED"],
        raises="Join validation FAILED - see details above")

    fx["join_many1_right_dup_keys"] = dict(
        code=_vc("Join"),
        ns={"left_df": pl.DataFrame({"k": [1, 1, 2]}),
            "right_df": pl.DataFrame({"k": [1, 2, 2]}),
            "result_df": pl.DataFrame({"k": [1, 1, 2]}),
            "join_keys": ["k"], "expected_cardinality": "many:1", "join_type": "inner",
            "not_applicable": {}},
        contains=["[FAIL] duplicate keys 'k': declared many:1 but the right ('1') "
                  "side has 1 duplicate key rows",
                  "Checks: 4 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped",
                  "JOIN VALIDATION: FAILED"],
        raises="Join validation FAILED - see details above")

    # A declared duplication is one [SKIPPED] line and the block still passes.
    fx["join_1to1_dup_keys_declared"] = dict(
        code=_vc("Join"),
        ns={"left_df": pl.DataFrame({"k": [1, 2, 3]}),
            "right_df": pl.DataFrame({"k": [1, 2, 2]}),
            "result_df": pl.DataFrame({"k": [1, 2, 2]}),
            "join_keys": ["k"], "expected_cardinality": "1:1", "join_type": "right",
            "not_applicable": {"duplicate_keys":
                               "the right side is a versioned lookup; the Plan "
                               "documents the duplicate vintage rows"}},
        contains=["[SKIPPED] duplicate keys: the right side is a versioned lookup",
                  "Checks: 4 passed, 0 warnings, 0 failed, 0 not verified, 1 skipped",
                  "JOIN VALIDATION: PASSED"])

    # --- CPP4 marker semantics -------------------------------------------------

    # [NO INTERPRETATION] cannot hedge a claim it shares its line with.
    fx["cpp4_abstention_marker_with_claim"] = dict(
        code=_vc("CPP4"),
        ns={"data_dictionary_draft": [
                {"column": "a",
                 "interpretation": "[NO INTERPRETATION] enrollment is a headcount"}],
            "documentation_provided": False, "reconciliation_ran": None,
            "not_applicable": {}},
        contains=["[FAIL] interpretation 'a': 1 of 1 claim lines unhedged",
                  "Checks: 1 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped",
                  "CPP4 VALIDATION: FAILED"],
        raises="CPP4 FAILED - see details above")

    fx["cpp4_abstention_marker_alone"] = dict(
        code=_vc("CPP4"),
        ns={"data_dictionary_draft": [{"column": "a",
                                       "interpretation": "  [NO INTERPRETATION]  "}],
            "documentation_provided": False, "reconciliation_ran": None,
            "not_applicable": {}},
        contains=["[PASS] interpretation 'a': all 1 claim lines carry",
                  "Checks: 2 passed, 0 warnings, 0 failed, 0 not verified, 0 skipped",
                  "CPP4 VALIDATION: PASSED"])

    # --- Substantiveness: hoisted skip + small-frame WARNING -------------------

    fx["substantiveness_small_frame_hoisted_skip"] = dict(
        code=_SUBST_DATA,
        ns={"df": pl.DataFrame({"a": [1, 2, 3, 4, 5], "b": [9, 9, 9, 9, 9]}),
            "key_columns": ["a", "b"], "context": "small-frame fixture",
            "not_applicable": {"round_numbers": "counts are officially reported rounded"}},
        contains=["[WARNING] frame size: 5 rows",
                  "[SKIPPED] round-numbers: counts are officially reported rounded",
                  "Checks: 5 passed, 1 warnings, 1 failed, 0 not verified, 1 skipped",
                  "DATA SUBSTANTIVENESS: FAILED"],
        # One declared decision is one [SKIPPED] line, however many columns the
        # check would have visited.
        line_count=("[SKIPPED] round-numbers", 1))

    # --- CPP-SKILL evidence floor ---------------------------------------------

    fx["cpp_skill_short_determination"] = dict(
        code=_vc("CPP-SKILL"),
        ns={"skill_draft_dir": None, "profiled_columns": None,
            "manual_determinations": {"related_skills_crossref": "PASS: x"},
            "not_applicable": {}},
        contains=["[NOT VERIFIED]", "at least 20 characters of evidence",
                  # Nothing else is adjudicable with skill_draft_dir=None, so every
                  # item is unverified — including the one that carried "PASS: x".
                  "Checks: 0 passed, 0 warnings, 0 failed, 23 not verified, 0 skipped",
                  "CPP-SKILL VALIDATION: FAILED"],
        raises="CPP-SKILL FAILED - see details above")

    # --- Auxiliary inline blocks (advisory: verdict, no raise) -----------------

    (scratch / "empty_notebook.py").write_text("import polars as pl\nprint('hello')\n")
    fx["wiring_zero_transforms_zero_saves"] = dict(
        code=_aux(AUX_WIRING),
        ns={"project_dir": scratch, "notebook_path": scratch / "empty_notebook.py",
            "report_path": None, "not_applicable": {}},
        contains=["[FAIL] transform saves: 0 transformations and 0 saves",
                  "Checks: 0 passed, 0 warnings, 1 failed, 2 not verified, 0 skipped",
                  "WIRING CHECK: FAILED"])

    (scratch / "emptydir").mkdir(exist_ok=True)
    fx["stub_scan_zero_files"] = dict(
        code=_aux(AUX_STUB_PY),
        ns={"project_dir": scratch / "emptydir", "not_applicable": {}},
        contains=["[NOT VERIFIED] stub scan: 0 .py/.md files found",
                  "Checks: 0 passed, 0 warnings, 0 failed, 1 not verified, 0 skipped",
                  "STUB DETECTION: FAILED"])

    # A stub-free project must reach PASSED. This is the control for the removal
    # of the `stub_scan` not-applicable path: with one check and no skip route,
    # the only way to a clean verdict is a scan that actually ran and found
    # nothing. (The absence of that route is asserted on the block source in
    # TemplateExtractionTests.test_stub_detection_has_no_not_applicable_path.)
    clean_proj = scratch / "clean_project"
    clean_proj.mkdir(exist_ok=True)
    (clean_proj / "nb.py").write_text(
        'import polars as pl\n'
        'df = pl.read_parquet("data/processed/clean.parquet")\n'
        'out = df.filter(pl.col("x") > 0).with_columns(pl.col("x") * 2)\n'
        'out.write_parquet("data/processed/out.parquet")\n')
    (clean_proj / "REPORT.md").write_text("# Report\n\nSee f1.png for the trend.\n")
    fx["stub_scan_clean_project"] = dict(
        code=_aux(AUX_STUB_PY),
        ns={"project_dir": clean_proj},
        contains=["[PASS] stub scan: 0 matches for 12 stub and 2 warning patterns "
                  "across 2 .py/.md files",
                  "Checks: 1 passed, 0 warnings, 0 failed, 0 not verified, 0 skipped",
                  "STUB DETECTION: PASSED"])

    # Wiring `data usage`: the idiomatic load-then-transform-into-a-new-name shape
    # references the loaded frame exactly once and must PASS naming that count.
    # `uses < 2` made this a guaranteed false [FAIL] on a correct notebook.
    wired = scratch / "wired_project"
    wired.mkdir(exist_ok=True)
    (wired / "nb.py").write_text(
        'import polars as pl\n'
        'df = pl.read_parquet("data/processed/clean.parquet")\n'
        'out = df.filter(pl.col("x") > 0).with_columns(pl.col("x") * 2)\n'
        'out.write_parquet("data/processed/out.parquet")\n'
        'fig.savefig("output/figures/f1.png")\n')
    (wired / "REPORT.md").write_text("# Report\n\nSee f1.png for the trend.\n")
    fx["wiring_single_downstream_use"] = dict(
        code=_aux(AUX_WIRING),
        ns={"project_dir": wired, "notebook_path": wired / "nb.py",
            "report_path": wired / "REPORT.md", "not_applicable": {}},
        contains=["[PASS] data usage 'df': loaded from data/processed/clean.parquet "
                  "via read_parquet and referenced 1 time(s) after the load",
                  "Checks: 3 passed, 0 warnings, 0 failed, 0 not verified, 0 skipped",
                  "WIRING CHECK: PASSED"],
        # The whole point of the repair: no [FAIL] line at all on a clean notebook.
        line_count=("[FAIL]", 0))

    # Zero downstream references is the one genuine wiring defect: a dead load.
    dead = scratch / "dead_load_project"
    dead.mkdir(exist_ok=True)
    (dead / "nb.py").write_text(
        'import polars as pl\n'
        'df = pl.read_parquet("data/processed/clean.parquet")\n'
        'other = pl.DataFrame({"a": [1]}).filter(pl.col("a") > 0)\n'
        'other.write_parquet("data/processed/out.parquet")\n')
    (dead / "REPORT.md").write_text("# Report\n\nNo figures in this analysis.\n")
    fx["wiring_zero_downstream_uses"] = dict(
        code=_aux(AUX_WIRING),
        ns={"project_dir": dead, "notebook_path": dead / "nb.py",
            "report_path": dead / "REPORT.md", "not_applicable": {}},
        contains=["[FAIL] data usage 'df': loaded from data/processed/clean.parquet "
                  "via read_parquet but never referenced again — the load is dead",
                  "Checks: 1 passed, 0 warnings, 1 failed, 1 not verified, 0 skipped",
                  "WIRING CHECK: FAILED"])

    return fx


def _build_cp4_scripts(scratch):
    """Write the two Stage-8 scripts the CP4.4 source scan reads.

    `good` is the self-reference control: it reads only `data/processed/`, yet its
    own CP4 config assigns `forbidden_input_dir = "data/raw/"` and its CP4 block
    quotes both literals — the exact shape that produced a guaranteed false [FAIL]
    before the config/comment/own-block exclusions were added.
    """
    good = scratch / "good_stage8.py"
    bad = scratch / "bad_stage8.py"
    good.write_text(
        '# Stage 8 analysis script\n'
        'import polars as pl\n'
        'df = pl.read_parquet("data/processed/analysis.parquet")\n'
        '# note: raw inputs live in data/raw/ but this script must not read them\n'
        '\n'
        '# --- CP4 Validation: Post-Analysis & Visualization (Stage 8) ---\n'
        'expected_input_dir = "data/processed/"\n'
        'forbidden_input_dir = "data/raw/"\n'
        'print("[FAIL] data source: references \'data/raw/\'")\n'
        'raise ValueError("CP4 FAILED - see details above")\n')
    bad.write_text(
        '# Stage 8 analysis script that genuinely reads raw data\n'
        'import polars as pl\n'
        'df = pl.read_parquet("data/raw/ccd_directory.parquet")\n')
    return good, bad


# --------------------------------------------------------------------------
# CPP-SKILL fixture skill directories
# --------------------------------------------------------------------------

_MANUAL_OK = {
    "related_skills_crossref": "PASS: Related Data Sources names bar-source explorer and query skills",
    "coded_values_complete": "PASS: no coded values found in profiling; value-interpretation.md documents sentinel semantics",
    "data_quality_complete": "PASS: all 4 anomalies from script 09 are catalogued",
    "variable_definitions_grouped": "PASS: 2 semantic families documented",
    "interpretive_share": "PASS: ~55% of reference lines are interpretive",
    "topic_specific_file": "PASS: source has 2 use cases, no topic file required",
    "cross_dataset_join": "PASS: join example with bar-source on col_a present",
}

_SKILL_HEAD = """---
name: foo-source
description: Foo data source reference.
metadata:
  data-pull-date: 2026-09-13
  profiled: 2026-09-13
---

# FOO Data Source Reference

FOO is a synthetic fixture source used to exercise CPP-SKILL template compliance.

## Value Encodings Warnings

| Value | FOO meaning | Naive reading |
|-------|-------------|---------------|
| -1 | missing | negative count |
| -2 | not applicable | negative count |

"""

_WHATIS_GOOD = "## What is FOO?\n\nFOO is a fixture.\n\n"
# The substring trap: 'What is NOT Included in FOO' contains 'What is', so a
# naive substring test accepts it as the canonical 'What is [Source]?' section.
_WHATIS_TRAP = ("## What is NOT Included in FOO\n\n"
                "FOO excludes nothing; this heading is the substring trap.\n\n")

_TREES_TWO = """## Reference File Structure

| File | Purpose |
|------|---------|
| columns.md | column list |

## Decision Trees

### Which file do I need?

```
Need columns? -> columns.md
```

### Is this a quality issue?

```
Null? -> data-quality.md
```

"""

_SKILL_TAIL = """## Quick Reference: FOO Tables

### Key Identifiers

| Column | Role |
|--------|------|
| col_a | id |

### Missing Data Codes

| Code | Meaning |
|------|---------|
| -1 | missing |

## Data Access

> **Truth Hierarchy:** the data beats the documentation beats the interpretation.

```python
df = pl.read_parquet("foo.parquet")
```

## Common Pitfalls

| Pitfall | Why it happens | What to do |
|---------|----------------|------------|
| Treating -1 as a count | Sentinels are negative | Filter sentinels first |
| Comparing across 2019/2020 | Methodology break | Do not compare |
| Assuming completeness | Coverage is partial | Check coverage table |

## Related Data Sources

| Source | Relationship |
|--------|--------------|
| bar-source | shares col_a |

## Topic Index

| Topic | File |
|-------|------|
| columns | columns.md |
"""

_AC_TEXT = """# FOO Analytical Context

## Study Design

FOO is an administrative census of fixture entities.

## Population Coverage

All fixture entities are in scope.

### What is NOT Included

- Private entities are excluded.
- Territories are excluded.

## Temporal Scope

Coverage runs 2019-2024; do not compare across the 2020 methodology break.

### Valid Analyses

| Analysis | Why Valid |
|----------|----------|
| Within-year comparison | Consistent methodology |
| Trend 2021-2024 | No break in window |
| Entity ranking | Universe coverage |

### Invalid or Problematic Analyses

| Analysis | Why Problematic |
|----------|-----------------|
| 2019 vs 2021 comparison | Methodology break |
| National totals | Territories excluded |
| Private-sector inference | Private entities excluded |

## Filler

""" + "\n".join(f"Filler line {i} of analytical narrative." for i in range(400)) + "\n"


def _build_fixture_skill(scratch, variant, substring_trap):
    """Materialise a minimal data source skill directory for CPP-SKILL."""
    vdir = scratch / "skills" / variant
    (vdir / "references").mkdir(parents=True)
    (vdir / "scripts").mkdir(parents=True)
    whatis = _WHATIS_TRAP if substring_trap else _WHATIS_GOOD
    (vdir / "SKILL.md").write_text(_SKILL_HEAD + whatis + _TREES_TWO + _SKILL_TAIL)
    refs = vdir / "references"
    (refs / "columns.md").write_text(
        "# Columns\n\n| Column | Type |\n|---|---|\n| col_a | int |\n| col_b | str |\n")
    (refs / "value-interpretation.md").write_text(
        "# Value Interpretation\n\nNegative values are sentinels.\n")
    (refs / "data-quality.md").write_text("# Data Quality\n\nAnomaly catalog.\n")
    (refs / "variable-definitions.md").write_text(
        "# Variable Definitions\n\nSemantic families.\n")
    (refs / "analytical-context.md").write_text(_AC_TEXT)
    (vdir / "scripts" / "01_load-and-format.py").write_text("# bundled profiling script\n")
    return vdir


# --------------------------------------------------------------------------
# R fixture registry (setup code strings evaluated against extracted blocks)
# --------------------------------------------------------------------------

_R_CP3_BASE = """assign("input_df", data.frame(a = c(1,2,3,4), b = c(1,1,2,2)), envir = env)
assign("output_df", data.frame(a = c(1,2,3,4), b = c(1,1,2,2)), envir = env)
assign("operation", "fixture", envir = env)
assign("preserved_cols", c("a"), envir = env)
assign("not_applicable", list(), envir = env)
"""

_R_QA_COUNTERS = ('assign("qa4a", c(passed = 0L, warnings = 0L, blockers = 0L, '
                  'not_verified = 0L, skipped = 0L, info = 0L), envir = env)\n')

R_FIXTURES = {
    # CP3: an unrecognized expected_relationship must FAIL loudly, not fall
    # through to PASS (regression anchor, R side).
    "r_cp3_unknown_relationship": dict(
        block=("VC", "CP3", "r"),
        setup=_R_CP3_BASE + 'assign("expected_relationship", "smae", envir = env)\n',
        contains=["[FAIL] row relationship: unrecognized expected_relationship 'smae'",
                  "CP3 VALIDATION: FAILED"],
        stops=True),
    # NULL is the other historical fall-through: R's `==` on NULL yields
    # logical(0), which `if ()` cannot branch on.
    "r_cp3_null_relationship": dict(
        block=("VC", "CP3", "r"),
        setup=_R_CP3_BASE + 'assign("expected_relationship", NULL, envir = env)\n',
        contains=["[FAIL] row relationship: unrecognized expected_relationship 'NULL'",
                  "CP3 VALIDATION: FAILED"],
        stops=True),
    "r_cp2_suppression_code_null": dict(
        block=("VC", "CP2", "r"),
        setup="""assign("raw_df", data.frame(enrollment = c(-3,-3,-3,500)), envir = env)
assign("clean_df", data.frame(enrollment = c(500)), envir = env)
assign("key_variables", c("enrollment"), envir = env)
assign("SUPPRESSION_CODE", NULL, envir = env)
assign("CODED_MISSING_VALUES", c(-1,-2,-3), envir = env)
assign("SUPPRESSION_THRESHOLD", 0.5, envir = env)
assign("not_applicable", list(), envir = env)
""",
        contains=["[NOT VERIFIED] suppression: SUPPRESSION_CODE is NULL/NA",
                  "CP2 VALIDATION: FAILED"],
        stops=True),
    # `$` partial matching would bind converged_flag to a `converged` lookup and
    # report a pass; the repaired template indexes with `[[`.
    "r_qa4a_convergence_misnamed_field": dict(
        block=("QA", "QA4a", "r", "Validate: model_convergence"),
        setup='assign("plan_spec", list(model_results = list(converged_flag = FALSE)), envir = env)\n'
              'assign("not_applicable", list(), envir = env)\n' + _R_QA_COUNTERS,
        contains=["[NOT VERIFIED]", "model_convergence"],
        stops=False),
    # NA signs used to abort the script at `if (NA)`.
    "r_qa4a_robustness_na_signs": dict(
        block=("QA", "QA4a", "r", "Validate: robustness"),
        setup='assign("plan_spec", list(robustness_checks = list(list(name = "alt-spec", '
              'primary_sign = NA, alt_sign = NA))), envir = env)\n'
              'assign("not_applicable", list(), envir = env)\n'
              'assign("KNOWN_SIGNS", c(-1, 0, 1), envir = env)\n' + _R_QA_COUNTERS,
        contains=["[NOT VERIFIED]", "robustness 'alt-spec'"],
        stops=False),
    "r_cpp2_all_na_column": dict(
        block=("VC", "CPP2", "r"),
        setup="""assign("df", data.frame(id = 1:150, x = as.numeric(rep(NA, 150))), envir = env)
assign("numeric_columns", c("x"), envir = env)
assign("temporal_expected", FALSE, envir = env)
assign("time_columns_found", NULL, envir = env)
assign("not_applicable", list(), envir = env)
""",
        contains=["[NOT VERIFIED] numeric summary 'x': entirely NA over 150 rows",
                  "CPP2 VALIDATION: FAILED"],
        stops=True),
    # TRE's `.` matches newline, so the old gregexpr collapsed a multi-line
    # interpretation into one match and a single leading [PRELIMINARY] laundered
    # the unhedged second line.
    "r_cpp4_multiline_launder": dict(
        block=("VC", "CPP4", "r"),
        setup='assign("data_dictionary_draft", data.frame(column = c("a"), '
              'interpretation = c("[PRELIMINARY] good claim\\nunhedged bad claim"), '
              'stringsAsFactors = FALSE), envir = env)\n'
              'assign("documentation_provided", FALSE, envir = env)\n'
              'assign("reconciliation_ran", NULL, envir = env)\n'
              'assign("not_applicable", list(), envir = env)\n',
        contains=["[FAIL] interpretation 'a': 1 of 2 claim lines unhedged",
                  "CPP4 VALIDATION: FAILED"],
        stops=True),
    # R side of the 1:1 bound repair: inner is bounded by min(left, right), so a
    # 6-row result off a 3-row right side is fan-out, not a pass.
    "r_join_1to1_inner_exceeds_min_bound": dict(
        block=("VC", "Join", "r"),
        setup="""assign("left_df", data.frame(k = 1:6), envir = env)
assign("right_df", data.frame(k = 1:3), envir = env)
assign("result_df", data.frame(k = c(1, 1, 2, 2, 3, 3)), envir = env)
assign("join_keys", c("k"), envir = env)
assign("expected_cardinality", "1:1", envir = env)
assign("join_type", "inner", envir = env)
assign("not_applicable", list(), envir = env)
""",
        contains=["[FAIL] cardinality: result 6 rows exceeds the '1:1'/'inner' upper bound of 3",
                  "Checks: 4 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped",
                  "JOIN VALIDATION: FAILED"],
        stops=True),
    # R side of the § 11 ruling: a duplicated right key under a declared 1:1 is a
    # contradiction, so [FAIL] — even though the row-count bound (right_rows) holds.
    "r_join_1to1_right_dup_keys": dict(
        block=("VC", "Join", "r"),
        setup="""assign("left_df", data.frame(k = 1:3), envir = env)
assign("right_df", data.frame(k = c(1, 2, 2)), envir = env)
assign("result_df", data.frame(k = c(1, 2, 2)), envir = env)
assign("join_keys", c("k"), envir = env)
assign("expected_cardinality", "1:1", envir = env)
assign("join_type", "right", envir = env)
assign("not_applicable", list(), envir = env)
""",
        contains=["[PASS] cardinality: result 3 rows within the '1:1'/'right' upper bound of 3",
                  "[FAIL] duplicate keys 'k': declared 1:1 but left has 0 and right has 1 duplicate key rows",
                  "Checks: 4 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped",
                  "JOIN VALIDATION: FAILED"],
        stops=True),
    # R coerces the sentinel to a string rather than raising, so a character
    # column vs a numeric sentinel must report NOT VERIFIED, not a rate.
    "r_cp2_character_column_numeric_sentinel": dict(
        block=("VC", "CP2", "r"),
        setup="""assign("raw_df", data.frame(x = c("-3", "-3", "10", "20"), stringsAsFactors = FALSE), envir = env)
assign("clean_df", data.frame(x = c("10", "20"), stringsAsFactors = FALSE), envir = env)
assign("key_variables", c("x"), envir = env)
assign("SUPPRESSION_CODE", -3, envir = env)
assign("CODED_MISSING_VALUES", c(-1, -2, -3), envir = env)
assign("SUPPRESSION_THRESHOLD", 0.5, envir = env)
assign("not_applicable", list(), envir = env)
""",
        contains=["[NOT VERIFIED] suppression 'x': column is character, not comparable to sentinel -3",
                  "Checks: 1 passed, 0 warnings, 0 failed, 2 not verified, 0 skipped",
                  "CP2 VALIDATION: FAILED"],
        stops=True),
    # [NO INTERPRETATION] alone on its line is a genuine abstention.
    "r_cpp4_abstention_marker_alone": dict(
        block=("VC", "CPP4", "r"),
        setup='assign("data_dictionary_draft", data.frame(column = c("a"), '
              'interpretation = c("  [NO INTERPRETATION]  "), '
              'stringsAsFactors = FALSE), envir = env)\n'
              'assign("documentation_provided", FALSE, envir = env)\n'
              'assign("reconciliation_ran", NULL, envir = env)\n'
              'assign("not_applicable", list(), envir = env)\n',
        contains=["[PASS] interpretation 'a': all 1 claim lines carry",
                  "Checks: 2 passed, 0 warnings, 0 failed, 0 not verified, 0 skipped",
                  "CPP4 VALIDATION: PASSED"],
        stops=False),
}


def _r_block_source(spec):
    if spec[0] == "VC":
        return _vc(spec[1], spec[2])
    if len(spec) == 4:
        return _qa_region(spec[1], spec[2], spec[3])
    return QA_BLOCKS[(spec[1], spec[2])]


# --------------------------------------------------------------------------
# Tests: extraction
# --------------------------------------------------------------------------

class TemplateExtractionTests(unittest.TestCase):
    """A heading rename must fail here rather than silently testing nothing."""

    def test_qa_template_block_inventory(self):
        self.assertEqual(len(QA_BLOCKS), EXPECTED_QA_TOTAL,
                         f"QA_CHECKPOINTS.md: expected {EXPECTED_QA_TOTAL} template blocks "
                         f"under headings matching 'QA\\d[ab]? .*Script', found "
                         f"{sorted(QA_BLOCKS)}")
        for family in EXPECTED_QA_FAMILIES:
            for lang in ("python", "r"):
                self.assertIn((family, lang), QA_BLOCKS)
                self.assertTrue(QA_BLOCKS[(family, lang)].strip(),
                                f"{family}/{lang} block is empty")

    def test_vc_sections_located(self):
        families = {k[0] for k in VC_BLOCKS}
        self.assertEqual(
            families,
            {"CP1", "CP2", "CP3", "CP4", "Join", "Substantiveness",
             "CPP1", "CPP2", "CPP3", "CPP4", "CPP-SKILL"},
            f"VALIDATION_CHECKPOINTS.md section headings changed; matched: {VC_SECTIONS}")

    def test_vc_template_block_counts(self):
        py = sum(len(v) for k, v in VC_BLOCKS.items() if k[1] == "python")
        r = sum(len(v) for k, v in VC_BLOCKS.items() if k[1] == "r")
        self.assertEqual(py, EXPECTED_VC_PY_TOTAL)
        self.assertEqual(r, EXPECTED_VC_R_TOTAL)
        for family in EXPECTED_VC_SINGLE + ("CPP1", "CPP2", "CPP3", "CPP4"):
            self.assertEqual(len(VC_BLOCKS[(family, "python")]), 1, family)
            self.assertEqual(len(VC_BLOCKS[(family, "r")]), 1, family)
        self.assertEqual(len(VC_BLOCKS[("Substantiveness", "python")]), 3)
        self.assertEqual(len(VC_BLOCKS[("Substantiveness", "r")]), 1)
        self.assertEqual(len(VC_BLOCKS[("CPP-SKILL", "python")]), 1)
        self.assertNotIn(("CPP-SKILL", "r"), VC_BLOCKS,
                         "CPP-SKILL is Python-only by design")

    def test_aux_inline_block_inventory(self):
        """The three auxiliary inline blocks: 2 python (Stub Detection, Wiring
        Check) + 1 r (Stub Detection). They are kept out of VC_BLOCKS because
        their headings and in-code markers differ from the canonical templates."""
        self.assertEqual(len(AUX_BLOCKS), EXPECTED_AUX_TOTAL,
                         f"auxiliary inline blocks changed; matched: {sorted(AUX_BLOCKS)}")
        self.assertEqual(sorted(AUX_BLOCKS),
                         [(AUX_STUB_PY, "python"), (AUX_STUB_R, "r"), (AUX_WIRING, "python")])
        self.assertEqual(sum(1 for k in AUX_BLOCKS if k[1] == "python"), 2)
        self.assertEqual(sum(1 for k in AUX_BLOCKS if k[1] == "r"), 1)
        for key, code in AUX_BLOCKS.items():
            self.assertTrue(code.strip(), f"{key} block is empty")
        # The aux blocks must not leak into the canonical inventory.
        for key in AUX_BLOCKS:
            self.assertNotIn(key[0], {s for s in VC_SECTIONS})

    def test_stub_detection_has_no_not_applicable_path(self):
        """Design contract § 11: Stub Detection's single check has no
        not-applicable route. Declaring it left zero checks run, which the shared
        verdict rule turns into FAILED — after printing a reassuring [SKIPPED]
        line that did not explain the failure. Asserted on the block source
        because the removed branch is unreachable by execution, so only a source
        assertion can prove it is gone. Comment lines are stripped first: the IAT
        header deliberately names `not_applicable` and `[SKIPPED]` to explain why
        neither is present, and asserting over raw text would flag the
        explanation as the defect."""
        for lang, heading in (("python", AUX_STUB_PY), ("r", AUX_STUB_R)):
            code = _aux(heading, lang)
            executable = "\n".join(ln for ln in code.splitlines()
                                   if not ln.lstrip().startswith("#"))
            with self.subTest(block=heading):
                self.assertNotIn("stub_scan", executable)
                self.assertNotIn("[SKIPPED]", executable)
                self.assertNotIn("not_applicable", executable)
                # The counter keeps its five fields so the count line's shape is
                # identical to every other block, even though `skipped` is
                # unreachable here.
                self.assertIn("skipped", executable)

    def test_regression_anchor_fixtures_are_registered(self):
        # The four original defect reproductions must never be quietly dropped.
        src = _THIS.read_text()
        for anchor in _REGRESSION_ANCHORS:
            self.assertIn(f'fx["{anchor}"]', src,
                          f"regression anchor fixture {anchor} is no longer defined")
            self.assertIn(f"def test_{anchor}", src,
                          f"regression anchor fixture {anchor} has no test method")

    def test_retired_warn_spelling_is_absent_from_templates(self):
        # Design contract § 2: [WARN] is retired in favour of [WARNING].
        for label, blocks in (("QA", list(QA_BLOCKS.values())),
                              ("VC", [c for v in VC_BLOCKS.values() for c in v])):
            for code in blocks:
                self.assertNotIn("[WARN]", code,
                                 f"{label} template still emits the retired [WARN] token")


# --------------------------------------------------------------------------
# Tests: syntax gates
# --------------------------------------------------------------------------

class PythonSyntaxGateTests(unittest.TestCase):

    def test_every_python_template_block_compiles(self):
        blocks = [(f"QA:{k[0]}", v) for k, v in QA_BLOCKS.items() if k[1] == "python"]
        blocks += [(f"VC:{k[0]}#{i}", c)
                   for k, v in VC_BLOCKS.items() if k[1] == "python"
                   for i, c in enumerate(v)]
        self.assertEqual(len(blocks), 5 + EXPECTED_VC_PY_TOTAL)
        for label, code in blocks:
            with self.subTest(block=label):
                compile(code, f"<{label}>", "exec")


@unittest.skipUnless(RSCRIPT, "Rscript not available on this host")
class RSyntaxGateTests(unittest.TestCase):

    scratch = None

    @classmethod
    def setUpClass(cls):
        cls.scratch = _new_scratch()
        cls.labels = []
        for key, code in QA_BLOCKS.items():
            if key[1] == "r":
                cls.labels.append((f"QA_{key[0]}", code))
        for key, blocks in VC_BLOCKS.items():
            if key[1] != "r":
                continue
            for i, code in enumerate(blocks):
                cls.labels.append((f"VC_{key[0]}_{i}", code))
        for label, code in cls.labels:
            (cls.scratch / f"{label}.R").write_text(code + "\n")
        # One Rscript process parses every block: R startup dominates the cost.
        driver = cls.scratch / "parse_all.R"
        driver.write_text(
            'files <- sort(list.files(commandArgs(trailingOnly = TRUE)[1], '
            'pattern = "[.]R$", full.names = TRUE))\n'
            'for (f in files) {\n'
            '  if (basename(f) == "parse_all.R") next\n'
            '  res <- tryCatch({ invisible(parse(file = f)); "OK" },\n'
            '                  error = function(e) paste("ERROR:", conditionMessage(e)))\n'
            '  cat(sprintf("%s\\t%s\\n", sub("[.]R$", "", basename(f)), res))\n'
            '}\n')
        proc = subprocess.run([RSCRIPT, str(driver), str(cls.scratch)],
                              capture_output=True, text=True, timeout=180)
        cls.proc = proc
        cls.results = {}
        for line in proc.stdout.splitlines():
            if "\t" in line:
                name, status = line.split("\t", 1)
                cls.results[name] = status

    @classmethod
    def tearDownClass(cls):
        _drop_scratch(cls.scratch)

    def test_rscript_driver_ran(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)
        self.assertEqual(len(self.results), len(self.labels),
                         f"parsed {sorted(self.results)} vs expected "
                         f"{sorted(n for n, _ in self.labels)}")

    def test_every_r_template_block_parses(self):
        self.assertEqual(len(self.labels), 5 + EXPECTED_VC_R_TOTAL)
        for label, _ in self.labels:
            with self.subTest(block=label):
                self.assertEqual(self.results.get(label), "OK",
                                 f"{label}: {self.results.get(label)}")


# --------------------------------------------------------------------------
# Tests: Python fixture matrix
# --------------------------------------------------------------------------

@unittest.skipUnless(HAS_POLARS, "polars not available on this host")
class PythonFixtureTests(unittest.TestCase):

    def setUp(self):
        self.scratch = _new_scratch()
        self.fixtures = _py_fixtures(self.scratch)

    def tearDown(self):
        _drop_scratch(self.scratch)

    # -- shared runner ----------------------------------------------------

    def _run(self, name):
        spec = self.fixtures[name]
        ns = dict(spec["ns"])
        ns.setdefault("pl", pl)
        buf = io.StringIO()
        raised = None
        try:
            with contextlib.redirect_stdout(buf):
                exec(compile(spec["code"], f"<fixture:{name}>", "exec"), ns)
        except ValueError as exc:      # the contract's halting mechanism
            raised = str(exc)
        out = buf.getvalue()
        emitted = [ln for ln in out.splitlines() if ln.startswith("[")]

        # Design contract § 2: a per-check line must not look like a checkpoint
        # verdict to scripts/compare_execution_logs.py.
        for line in emitted:
            self.assertIsNone(
                _IDENTIFIER_ON_CHECK_LINE.search(line),
                f"{name}: per-check line carries a checkpoint identifier: {line!r}")

        if spec.get("raises") is not None:
            self.assertEqual(raised, spec["raises"],
                             f"{name}: expected raise {spec['raises']!r}, got {raised!r}\n{out}")
        else:
            self.assertIsNone(raised, f"{name}: unexpected raise {raised!r}\n{out}")

        if spec.get("token") is not None:
            self.assertEqual(len(emitted), 1,
                             f"{name}: expected exactly one emitted line, got {emitted}")
            self.assertTrue(emitted[0].startswith(spec["token"]),
                            f"{name}: expected {spec['token']}, got {emitted[0]!r}")
        for needle in spec.get("contains", []):
            self.assertIn(needle, out, f"{name}: missing {needle!r}\n{out}")
        if spec.get("counter") is not None:
            key, field, value = spec["counter"]
            self.assertEqual(ns[key][field], value, f"{name}: {key}[{field}] {ns[key]}")
        if spec.get("line_count") is not None:
            prefix, expected = spec["line_count"]
            got = sum(1 for ln in out.splitlines() if ln.startswith(prefix))
            self.assertEqual(got, expected,
                             f"{name}: expected {expected} line(s) starting {prefix!r}, "
                             f"got {got}\n{out}")
        return out

    # -- regression anchors (2026-09-05 review defect reproductions) -------

    def test_qa4a_convergence_missing(self):
        """model_results={} used to print '[PASS] Model converged successfully'."""
        self._run("qa4a_convergence_missing")

    def test_qa4a_robustness_name_only(self):
        """A robustness entry with only a name used to print '[PASS] ... consistent'."""
        self._run("qa4a_robustness_name_only")

    def test_cp3_unknown_relationship(self):
        """expected_relationship='smae' used to fall through the else to [PASS]."""
        self._run("cp3_unknown_relationship")

    def test_qa2_suppression_reported_zero(self):
        """A reported rate of 0 on a 50%-suppressed column used to pass, because
        `if reported_rate and ...` is False for 0.0 and row attrition was
        computed in place of a column rate."""
        self._run("qa2_suppression_reported_zero")

    def test_qa2_suppression_correct_control(self):
        """Correct-value control: the PASS line must carry its numbers."""
        self._run("qa2_suppression_correct_control")

    # -- design contract § 6 metric corrections ---------------------------

    def test_qa4a_aggregation_zero_source(self):
        self._run("qa4a_aggregation_zero_source")

    def test_qa3_unknown_aggregation_function(self):
        self._run("qa3_unknown_aggregation_function")

    def test_join_outer_1to1_fanout(self):
        self._run("join_outer_1to1_fanout")

    def test_join_left_rows_zero(self):
        self._run("join_left_rows_zero")

    def test_cp3_not_applicable_declared(self):
        self._run("cp3_not_applicable_declared")

    def test_cp1_empty_required_columns(self):
        self._run("cp1_empty_required_columns")

    def test_cpp2_all_null_numeric_column(self):
        """An all-null numeric column must report NOT VERIFIED, not raise a
        TypeError from comparing None."""
        self._run("cpp2_all_null_numeric_column")

    def test_cpp4_multiline_unhedged_second_line(self):
        self._run("cpp4_multiline_unhedged_second_line")

    def test_cpp_skill_heading_substring_rejected(self):
        self._run("cpp_skill_heading_substring_rejected")

    def test_cpp_skill_value_interpretation_accepted(self):
        self._run("cpp_skill_value_interpretation_accepted")

    def test_cp3_zero_checks_run_is_failed(self):
        self._run("cp3_zero_checks_run")

    def test_qa1_zero_checks_run_is_warning(self):
        self._run("qa1_zero_checks_run")

    # -- CP4 (Stage 8) sub-checks 4.1 / 4.4 -------------------------------

    def test_cp4_data_source_self_reference_control(self):
        """A correct Stage-8 script used to FAIL on its own CP4 config line."""
        self._run("cp4_data_source_self_reference_control")

    def test_cp4_data_source_genuine_raw_read(self):
        self._run("cp4_data_source_genuine_raw_read")

    @unittest.skipUnless(HAS_NUMPY, "numpy not available on this host")
    def test_cp4_numpy_scalar_estimate_and_n(self):
        """np.float64 / np.int64 are what estimators return; they must not read
        as non-finite or as a missing n."""
        self._run("cp4_numpy_scalar_estimate_and_n")

    def test_cp4_bool_estimate_rejected(self):
        """bool subclasses int, so `True` must not pass as a finite estimate."""
        self._run("cp4_bool_estimate_rejected")

    @unittest.skipUnless(HAS_NUMPY, "numpy not available on this host")
    def test_cp4_numpy_bool_convergence(self):
        """np.bool_(True) is not a `bool` instance and is never `is True`; the
        CP4.1 guard must still read it as a reported convergence flag."""
        self._run("cp4_numpy_bool_convergence")

    # -- CP2 dtype comparability ------------------------------------------

    def test_cp2_string_column_vs_int_sentinel(self):
        """Polars returns all-False for a string column vs an int sentinel, so an
        unguarded compare reported '[PASS] 0.0%' over a suppressed column."""
        self._run("cp2_string_column_vs_int_sentinel")

    def test_cp2_numeric_column_rate_computed(self):
        self._run("cp2_numeric_column_rate_computed")

    # -- Join 1:1 bound ----------------------------------------------------

    def test_join_1to1_inner_exceeds_min_bound(self):
        """Bounding a 1:1 inner join by left_rows missed fan-out whenever the
        right side was the smaller input."""
        self._run("join_1to1_inner_exceeds_min_bound")

    def test_join_1to1_inner_within_min_bound(self):
        self._run("join_1to1_inner_within_min_bound")

    # -- CPP4 marker semantics ---------------------------------------------

    def test_cpp4_abstention_marker_with_claim(self):
        self._run("cpp4_abstention_marker_with_claim")

    def test_cpp4_abstention_marker_alone(self):
        self._run("cpp4_abstention_marker_alone")

    # -- Substantiveness / CPP-SKILL / auxiliary blocks ---------------------

    def test_substantiveness_small_frame_hoisted_skip(self):
        """One declared not_applicable decision emits exactly one [SKIPPED] line,
        not one per column."""
        self._run("substantiveness_small_frame_hoisted_skip")

    def test_cpp_skill_short_determination(self):
        self._run("cpp_skill_short_determination")

    def test_cpp_skill_itemized_reporting_check_removed(self):
        """The 'itemized reporting' check was true by construction — a [PASS] that
        could not fail. It must stay deleted from the block."""
        self.assertNotIn("itemized reporting", _vc("CPP-SKILL"))

    # -- Join: declared cardinality contradicted by the inputs (§ 11) -----

    def test_join_1to1_right_dup_keys(self):
        """Declared 1:1, right join, duplicated right key: the row-count bound
        holds, so only the duplicate-keys check can catch the contradiction. It
        used to print [WARNING] and the block reported PASSED WITH WARNINGS."""
        self._run("join_1to1_right_dup_keys")

    def test_join_1tomany_left_dup_keys(self):
        """Duplicates on the '1' side of a 1:many, plus the row-gain phrasing."""
        self._run("join_1tomany_left_dup_keys")

    def test_join_many1_right_dup_keys(self):
        self._run("join_many1_right_dup_keys")

    def test_join_1to1_dup_keys_declared(self):
        """Known duplication stays declarable: one [SKIPPED] line, verdict PASSED."""
        self._run("join_1to1_dup_keys_declared")

    # -- Auxiliary inline blocks ------------------------------------------

    def test_stub_scan_clean_project(self):
        """With the not-applicable path removed, a clean verdict requires a scan
        that actually ran."""
        self._run("stub_scan_clean_project")

    def test_wiring_single_downstream_use(self):
        """load -> transform into a new name is the idiomatic shape; one
        downstream reference must PASS, naming the count."""
        self._run("wiring_single_downstream_use")

    def test_wiring_zero_downstream_uses(self):
        self._run("wiring_zero_downstream_uses")

    def test_wiring_zero_transforms_zero_saves(self):
        """A notebook that does no data work is a FAILED wiring state, reported
        advisorily (no raise)."""
        self._run("wiring_zero_transforms_zero_saves")

    def test_stub_scan_zero_files(self):
        """An empty scan is not a clean scan."""
        self._run("stub_scan_zero_files")

    # -- cross-cutting ----------------------------------------------------

    def test_comparator_safety_across_all_python_fixtures(self):
        """No emitted per-check line may match \\bCP\\d / \\bQA\\d / \\bCPP\\d."""
        for name in sorted(self.fixtures):
            with self.subTest(fixture=name):
                self._run(name)   # _run asserts comparator safety per line

    def test_every_fixture_emits_at_least_one_outcome_token(self):
        for name in sorted(self.fixtures):
            with self.subTest(fixture=name):
                out = self._run(name)
                self.assertTrue(
                    [ln for ln in out.splitlines() if ln.startswith("[")],
                    f"{name}: emitted no outcome token at all")


# --------------------------------------------------------------------------
# Tests: R fixture matrix
# --------------------------------------------------------------------------

@unittest.skipUnless(RSCRIPT, "Rscript not available on this host")
class RFixtureTests(unittest.TestCase):

    scratch = None

    @classmethod
    def setUpClass(cls):
        cls.scratch = _new_scratch()
        runners = []
        for name, spec in R_FIXTURES.items():
            block_path = cls.scratch / f"block_{name}.R"
            block_path.write_text(_r_block_source(spec["block"]) + "\n")
            runner = cls.scratch / f"fixture_{name}.R"
            runner.write_text(
                f'cat("### FIXTURE {name} BEGIN\\n")\n'
                'env <- new.env(parent = globalenv())\n'
                + spec["setup"] +
                f'.res <- tryCatch({{ eval(parse(file = "{block_path}"), envir = env); '
                'NA_character_ }, error = function(e) conditionMessage(e))\n'
                'if (!is.na(.res)) cat(sprintf("### STOPPED: %s\\n", .res))\n'
                f'cat("### FIXTURE {name} END\\n")\n')
            runners.append(runner)
        driver = cls.scratch / "run_all.R"
        driver.write_text(
            'files <- commandArgs(trailingOnly = TRUE)\n'
            'for (f in files) {\n'
            '  tryCatch(source(f, local = new.env(parent = globalenv()), echo = FALSE),\n'
            '           error = function(e) cat(sprintf("### RUNNER ERROR: %s\\n", '
            'conditionMessage(e))))\n'
            '}\n')
        proc = subprocess.run([RSCRIPT, str(driver)] + [str(r) for r in runners],
                              capture_output=True, text=True, timeout=300)
        cls.proc = proc
        cls.outputs = {}
        current = None
        buf = []
        for line in proc.stdout.splitlines():
            begin = re.match(r"^### FIXTURE (\S+) BEGIN$", line)
            end = re.match(r"^### FIXTURE (\S+) END$", line)
            if begin:
                current, buf = begin.group(1), []
                continue
            if end:
                cls.outputs[end.group(1)] = "\n".join(buf)
                current = None
                continue
            if current is not None:
                buf.append(line)

    @classmethod
    def tearDownClass(cls):
        _drop_scratch(cls.scratch)

    def _check(self, name):
        spec = R_FIXTURES[name]
        self.assertIn(name, self.outputs,
                      f"{name}: no captured output. stderr:\n{self.proc.stderr}")
        out = self.outputs[name]
        for line in out.splitlines():
            if line.startswith("["):
                self.assertIsNone(
                    _IDENTIFIER_ON_CHECK_LINE.search(line),
                    f"{name}: per-check line carries a checkpoint identifier: {line!r}")
        for needle in spec["contains"]:
            self.assertIn(needle, out, f"{name}: missing {needle!r}\n{out}")
        stopped = "### STOPPED:" in out
        self.assertEqual(stopped, spec["stops"],
                         f"{name}: stop() expectation {spec['stops']} not met\n{out}")
        if stopped:
            self.assertIn("FAILED - see details above", out,
                          f"{name}: stop message is not the contract message\n{out}")

    def test_r_driver_ran(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)
        self.assertNotIn("### RUNNER ERROR", self.proc.stdout)
        self.assertEqual(set(self.outputs), set(R_FIXTURES))

    def test_r_cp3_unknown_relationship(self):
        self._check("r_cp3_unknown_relationship")

    def test_r_cp3_null_relationship(self):
        self._check("r_cp3_null_relationship")

    def test_r_cp2_suppression_code_null(self):
        self._check("r_cp2_suppression_code_null")

    def test_r_qa4a_convergence_misnamed_field(self):
        self._check("r_qa4a_convergence_misnamed_field")

    def test_r_qa4a_robustness_na_signs(self):
        self._check("r_qa4a_robustness_na_signs")

    def test_r_cpp2_all_na_column(self):
        self._check("r_cpp2_all_na_column")

    def test_r_cpp4_multiline_launder(self):
        self._check("r_cpp4_multiline_launder")

    def test_r_join_1to1_inner_exceeds_min_bound(self):
        self._check("r_join_1to1_inner_exceeds_min_bound")

    def test_r_join_1to1_right_dup_keys(self):
        """A duplicated right key under a declared 1:1 used to print [WARNING] and
        let the block report PASSED WITH WARNINGS."""
        self._check("r_join_1to1_right_dup_keys")

    def test_r_cp2_character_column_numeric_sentinel(self):
        self._check("r_cp2_character_column_numeric_sentinel")

    def test_r_cpp4_abstention_marker_alone(self):
        self._check("r_cpp4_abstention_marker_alone")


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
