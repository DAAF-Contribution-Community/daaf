"""Regression suite for the truthful checkpoint/QA code templates.

Guards `agent_reference/QA_CHECKPOINTS.md` and
`agent_reference/VALIDATION_CHECKPOINTS.md` against silently regressing to the
defect class their evidence-bearing rewrite removed: a check that never ran
reporting `[PASS]`, and a verdict line asserting an unqualified pass over checks
that never executed.

What it does
------------
1. **Extraction** — pulls the live template code blocks out of the two markdown
   files by heading (QA: `QA\\d[ab]? .*Script`; VC: `## CP\\d`,
   `## Join-Specific Validation`, `## Substantiveness Validation`, `### CPP\\d`,
   `### CPP-SKILL`, `### CPS-INTAKE`, `### CPS-GEN`) and language fence. The
   three *auxiliary* inline blocks
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
   `CPP<n>` identifier, because
   `scripts/compare_execution_logs.py` treats such a line as a checkpoint
   verdict. The synthetic-path identifiers `CPS-INTAKE` / `CPS-GEN` are
   comparator-safe by construction (`CPS-` carries no digit after `CP`), which is
   why widening the extraction regexes to admit them leaves that guard untouched.
5. **Disclosure leak scan (CPS only)** — every CPS fixture's whole stdout, both
   blocks and both languages, is scanned for the planted disclosure tokens in
   `CPS_LEAK_TOKENS` (outcome lines carry positions and aggregates, never a
   released or suppressed value). Each fixture's
   report (or, for CPS-GEN, its `seed_exception` pointer) must carry at least one
   planted token, every token must be planted somewhere, and a negative control
   proves the scanner fires, so the scan cannot pass vacuously.
6. **Cross-language parity (CPS only)** — every CPS fixture has an `r_` twin, and
   `test_cps_py_r_outcome_lines_byte_identical` asserts the two languages print
   byte-identical outcome lines (per-check, count, verdict) on the same input.
   The comparison is on raw bytes — R's stdout is captured undecoded, Python's
   text is encoded with `surrogatepass` — and the same test requires Python's
   stdout to be strict UTF-8 and both languages' stdout to carry no raw control or
   line-separator character (report-derived text prints those as `\\uXXXX`, so a
   crafted name cannot forge a line). Every stdout line split in this module is a
   split on "\\n" only, so a raw separator could never pass for a line boundary.

Block and fixture inventory
---------------------------
(Counts as of 2026-10-08, read from the live module by an inventory script that
imports it. The block totals are asserted against the live markdown by
`test_vc_template_block_counts` / `test_qa_template_block_inventory` /
`test_aux_inline_block_inventory`, and the CPS fixture total by the leak scans and
the parity test via `CPS_MIN_FIXTURES`, so a stale figure fails there first.)

* VC canonical blocks: 15 python / 12 r — CP1-CP4, Join, Substantiveness
  (3 python, 1 r), CPP1-CPP4, CPP-SKILL (python only), and the synthetic-path
  **CPS family** (CPS-INTAKE, CPS-GEN — 1 python + 1 r each). The CPS
  documentation-only `# --- Config ---` stanza fences are excluded by the same
  marker rule that excludes every other config stanza.
* QA blocks: 10 (QA1-QA4b x python/r). Auxiliary inline blocks: 3.
* Fixtures: 174 python (172 without numpy, which gates two CP4 fixtures), 146 r.
  Of these, 135 python / 135 r are CPS fixtures: 8 / 8 hand-registered
  (control, sub-threshold, non-declarable, missing block, genuine tier 2; GEN
  control, unreleased level, non-declarable — the four R twins of the
  Python-only ones were added for the parity test) plus the 127 rows of
  `CPS_REGRESSION_CASES` (98 CPS-INTAKE, 29 CPS-GEN), registered in both
  languages from the one table:
    - collapsed entries, identifier allow-list and withheld shape, JSON nulls
      beside a reported path, not_applicable keys (unrecognized; empty reasons on
      declarable and non-declarable checks), a sub-threshold leak variant, and on
      the CPS-GEN side a short correlation matrix and an unrecognized percentile
      key;
    - strict schema and typing, CPS-INTAKE: case-insensitive value-shaped keys,
      the per-role allow-list, over-long number tokens, strings under numeric
      keys, duplicate keys, NaN literals, negative cross-tab dimensions, dtype /
      settings / check-reason vocabularies, the approved threshold (declared
      below it, above it, unset);
    - cross-tab complementary suppression: two pure lone-cell grids, two
      lone-cell grids that also carry a bridge (`(+1 more)`), two cycles joined
      by one bridge, two bridges (`(+1 more)`), a hidden 2x2 cycle, a 3x3 single
      6-cycle, a cycle beside structural zeros (three PASS controls), a genuine
      tier-3 report from an earlier profiler whose 4x4 cross-tab carries a
      bridge, a hidden cell coded as 0, and a cells_suppressed mismatch;
    - disclosure arithmetic and scope, CPS-INTAKE: negative / zero level counts,
      level-sum and categorical n-vs-nonmissing_n residuals, cross-tab residual,
      negative cell, structural-zero PASS, report tier above the approved tier,
      relationships released below tier 3, non-string level value, an unknown
      top-level key with required_top_level_keys declared, dataset_name format,
      BOM / raw NUL / lone-surrogate / escaped-NUL parse errors, a newline-forged
      column name and a non-ASCII column name (both printed `\\uXXXX`);
    - CPS-INTAKE number tokens (65 and 64 characters), a tier-1 identifier
      carrying tier-2 keys, one support-gate breach per band (full summary,
      small_n, constant, string_structure, named, Cramer's V) plus an
      every-band-on-its-edge PASS, and a categorical record with dtype `integer`;
    - complement groups of an available named regression (CPS-INTAKE support
      gate): outcome and predictor groups one below the gate, both groups on the
      gate and both empty (PASS), an outcome with no numeric n, a leak variant
      whose derived group size is a planted token, and an entry withheld with
      reason `small_complement_group` (PASS);
    - repeated level labels (a plain label and `__OTHER__`) and missing-partner
      cells (`_a3_mp`, grids in code-point label order): a row-side and a
      column-side pinned count (planted as a token, never printed), the
      one-row and one-column baselines (exempt, PASS), a zero-residual line, a
      collapsed entry and a genuine shape with cycle-protected cells (PASS), an
      entry n above a pair column's nonmissing_n, and both [NOT VERIFIED] forms
      (a repeated label in a pair column; no usable gate) plus their
      baseline-only control;
    - one cross-tab per unordered pair, on the released categories
      (CPS-INTAKE `crosstab_schema_and_suppression`): a self-pair, a self-pair
      entered twice, a repeated pair in the same order, in swapped order, and
      after an unavailable entry on the pair; rows and cols unequal to the
      released level counts; a pair column that is numeric, an identifier, has
      no categorical block, or has a `levels` that is not an array; and a
      genuine-shape PASS with a pooled `__OTHER__` row and a row of structural
      zeros. Every grid fixture sits on its pair columns' released categories;
    - CPS-GEN: null coefficient / level count, a numeric column written as
      String, empty percentile grids, tier 3 without and tier 2 without a
      pearson block, the tier-4 seed and seed-exception outcomes, a nested
      duplicate key, whole-number float IDs vs an integer-coded label, boolean vs
      `True`/`TRUE` labels (dtype FAIL, level checks PASS) and their string-label
      companions, a Duration column, a fully pooled column (`__OTHER__` and
      all-null), duplicate parquet column names, a BOM report, an NBSP-only
      seed_exception at tier 4, a 65-character number token, and a configured
      tier that differs from the report's.
  Rows without a hand-written test method get a generated `test_<name>` /
  `test_r_<name>`. CPS fixtures read real artifacts — profile report JSONs and
  synthetic parquets built by `_report_fixtures()`, normalised to real profiler
  output — and rewrite the block's own multi-key config stanza (including
  `expected_threshold` / `seed_exception`) instead of injecting a namespace.
* Tests: 340 in this module.

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

import ast
import contextlib
import difflib
import io
import json
import math
import random
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

# The four original defect reproductions retained from the 2026-09-05 framework
# review (each comment names the snippet it reproduced). Each name below must stay
# present in this module.
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
_VC_MARKER_RE = re.compile(
    r"^# --- (CPP-SKILL|CPP\d|CP\d|CPS-INTAKE|CPS-GEN|Join|Substantiveness) Validation", re.M)
_VC_SECTION_RE = re.compile(r"^(CP\d):|^(Join-Specific Validation)|^(Substantiveness Validation)"
                            r"|^(CPP-SKILL):|^(CPP\d):|^(CPS-INTAKE):|^(CPS-GEN):")

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
EXPECTED_VC_SINGLE = ("CP1", "CP2", "CP3", "CP4", "Join", "CPS-INTAKE", "CPS-GEN")
# CPS-INTAKE / CPS-GEN each ship one python + one r canonical block. The two
# documentation-only `# --- Config ---` stanza fences that sit above them carry no
# `# --- <X> Validation` marker, so they stay out of the inventory by the same rule
# that excludes every other config stanza.
# What the totals count: ```python / ```r fences in VALIDATION_CHECKPOINTS.md that
# sit under a `_VC_SECTION_RE` heading AND carry a `# --- <X> Validation` marker
# (one canonical template each). Unmarked fences — config stanzas, including the
# two CPS documentation-only stanzas — are not counted. Live file 2026-09-24:
EXPECTED_VC_PY_TOTAL = 15   # 15 python = CP1-4 (4) + Join (1) + Substantiveness data/text/code
                            # (3) + CPP1-4 (4) + CPP-SKILL (1) + CPS-INTAKE (1) + CPS-GEN (1)
EXPECTED_VC_R_TOTAL = 12    # 12 r = CP1-4 (4) + Join (1) + Substantiveness data (1)
                            # + CPP1-4 (4) + CPS-INTAKE (1) + CPS-GEN (1); CPP-SKILL has no r
EXPECTED_QA_TOTAL = 10      # QA_CHECKPOINTS.md fences under `QA\d[ab]? .*Script` headings:
                            # 5 families (QA1, QA2, QA3, QA4a, QA4b) x {python, r}
EXPECTED_AUX_TOTAL = 3      # auxiliary inline VC fences (AUX_BLOCKS, not in the totals above):
                            # Stub Detection (python + r) + Wiring Check (python only)
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


# The CPS blocks own a multi-key `# --- Config ---` region (report_path, tier,
# expected_threshold [CPS-INTAKE], synthetic_path / seed / seed_exception [CPS-GEN],
# not_applicable) in exactly the way the QA templates own `not_applicable`: every
# one of those names is reassigned inside the block, so a namespace-injected value
# would be discarded. The fixtures therefore rewrite the shipped default assignment
# the way an executing agent edits the stanza. Anchoring on the *default* right-hand
# side (`= None` / `= {}`, R `<- NULL` / `<- list()`) rather than on the bare name
# keeps the rewrite from matching a later reassignment, and the exactly-one
# assertion fails loudly if a seam is renamed. (`^seed = None` cannot match the
# `seed_exception = None` line: the pattern requires a space after the name.)
_CPS_PY_DEFAULTS = {"report_path": "None", "tier": "None", "synthetic_path": "None",
                    "seed": "None", "seed_exception": "None",
                    "expected_threshold": "None", "not_applicable": "{}"}
_CPS_R_DEFAULTS = {"report_path": "NULL", "tier": "NULL", "synthetic_path": "NULL",
                   "seed": "NULL", "seed_exception": "NULL",
                   "expected_threshold": "NULL", "not_applicable": "list()"}
# The suppression threshold the fixtures' researcher "approved" at tier selection
# (CPS-INTAKE's `expected_threshold`). Every report the builder writes declares 5,
# so the effective gate is max(declared, 5) — the control family's PASS line names
# both.
CPS_APPROVED_THRESHOLD = 5


def _set_cps_config(code, assignments, lang="python"):
    """Rewrite named `# --- Config ---` assignments in a CPS block.

    `assignments` maps a config name to the literal source text to assign.
    """
    defaults = _CPS_PY_DEFAULTS if lang == "python" else _CPS_R_DEFAULTS
    op = "=" if lang == "python" else "<-"
    for name, literal in assignments.items():
        seam = re.compile(r"^%s %s %s.*$" % (re.escape(name), re.escape(op),
                                             re.escape(defaults[name])), re.M)
        assert len(seam.findall(code)) == 1, \
            f"expected exactly one `{name} {op} {defaults[name]}` config seam in the block"
        code = seam.sub(lambda _m, _lit=literal: f"{name} {op} {_lit}", code, count=1)
    return code


def _cps_col_rec(df, name, dtype, role, block_key, block):
    """One profile-report column record (report_version 2.0 T2+ field list)."""
    s = df[name]
    nonmissing = int(s.len() - s.null_count())
    rec = {
        "name": name,
        "dtype": dtype,
        "role": role,
        "missing_rate": round((df.height - nonmissing) / df.height, 6),
        "nonmissing_n": nonmissing,
        "n_distinct": int(s.n_unique()),
        "uniqueness_ratio": round(int(s.n_unique()) / nonmissing, 6),
        "is_identifier": False,
    }
    rec[block_key] = block
    return rec


def _report_fixtures(scratch):
    """Build the CPS profile-report + synthetic-parquet fixture family.

    The point of the builder is that every number the control report claims is
    *derived from the frame with the same polars call CPS-GEN re-derives it with*
    (`Series.quantile(..., interpolation="linear")` — the
    block's documented percentile rule, R `quantile(type = 7)` — and `pl.corr`), so
    a control FAIL indicts the shipped block and never the fixture. Stdlib `random`
    replaces numpy here so the CPS fixtures do not inherit the numpy skip.

    The reports are normalised to what the two shipped profilers actually emit, so
    no free-text field opens a leak path: every PASS entry in
    `validation.checks` carries the fixed reason `candidate_fields_checked`,
    `generator.language` is `Python` (not `python`), and `settings` carries the full
    profiler key set. CPS-INTAKE holds those fields to their spec vocabularies, so
    hand-written prose there is itself a `[FAIL]` — which is exactly the finding the
    `cps_intake_free_text_check_reason` row asserts on purpose, and nowhere else.

    Returns {name: path-as-str}. Requires polars; call under the HAS_POLARS guard.
    """
    out = scratch / "cps_fixtures"
    out.mkdir(parents=True, exist_ok=True)
    seed, n_rows, threshold = 20260915, 40, 5
    pctls = ["p1", "p5", "p10", "p25", "p50", "p75", "p90", "p95", "p99"]

    rng = random.Random(seed)
    z1 = [rng.gauss(0.0, 1.0) for _ in range(n_rows)]
    z2 = [rng.gauss(0.0, 1.0) for _ in range(n_rows)]
    num_a = [50.0 + 10.0 * a for a in z1]
    num_b = [20.0 + 3.0 * (0.7 * a + math.sqrt(1.0 - 0.7 ** 2) * b)
             for a, b in zip(z1, z2)]
    # cat_a = A x20, ZQXRARELABEL x10, __OTHER__ x10 (3 levels, one pooled bucket);
    # cat_b = X x20, Y x20; the [cat_a, cat_b] crosstab is then exactly
    # [10, 10, 5, 5, 5, 5] — the individual cell counts the disclosure PASS line
    # must never echo (see test_cps_intake_pass_line_is_aggregate_only).
    # The second level carries the planted disclosure token ZQXRARELABEL (see
    # CPS_LEAK_TOKENS) so that every fixture derived from this control — both
    # blocks, both languages — gives the whole-stdout leak scan something real to
    # find. The released counts here (20/10/5) are too small to scan for
    # stdout-wide without false positives; the token-bearing `a3a_*` family below
    # carries distinctive four-digit counts for that.
    cat_a = ["A"] * 20 + ["ZQXRARELABEL"] * 10 + ["__OTHER__"] * 10
    cat_b = (["X"] * 10 + ["Y"] * 10) + (["X"] * 5 + ["Y"] * 5) + (["X"] * 5 + ["Y"] * 5)
    df = pl.DataFrame({
        "num_a": pl.Series(num_a, dtype=pl.Float64),
        "num_b": pl.Series(num_b, dtype=pl.Float64),
        "cat_a": pl.Series(cat_a, dtype=pl.String),
        "cat_b": pl.Series(cat_b, dtype=pl.String),
    })

    numeric_blocks = {}
    for nm in ("num_a", "num_b"):
        s = df[nm]
        grid = {k: round(s.quantile(float(k[1:]) / 100.0, interpolation="linear"), 6)
                for k in pctls}
        numeric_blocks[nm] = {"n": int(s.len() - s.null_count()),
                              "mean": round(s.mean(), 6),
                              "sd": round(s.std(ddof=1), 6),
                              "percentiles": grid}
    pearson_ab = round(df.select(pl.corr(pl.col("num_a"), pl.col("num_b"))).item(), 6)
    spearman_ab = round(df.select(
        pl.corr(pl.col("num_a"), pl.col("num_b"), method="spearman")).item(), 6)

    ct_cells = [int(df.filter((pl.col("cat_a") == a) & (pl.col("cat_b") == b)).height)
                for a in ("A", "ZQXRARELABEL", "__OTHER__") for b in ("X", "Y")]
    assert ct_cells == [10, 10, 5, 5, 5, 5], ct_cells

    columns = [
        _cps_col_rec(df, "num_a", "double", "numeric", "numeric", numeric_blocks["num_a"]),
        _cps_col_rec(df, "num_b", "double", "numeric", "numeric", numeric_blocks["num_b"]),
        _cps_col_rec(df, "cat_a", "string", "categorical", "categorical",
                     {"n": n_rows, "n_levels_binned": 3,
                      "levels": [{"value": "A", "count": 20},
                                 {"value": "ZQXRARELABEL", "count": 10},
                                 {"value": "__OTHER__", "count": 10}]}),
        _cps_col_rec(df, "cat_b", "string", "categorical", "categorical",
                     {"n": n_rows, "n_levels_binned": 0,
                      "levels": [{"value": "X", "count": 20},
                                 {"value": "Y", "count": 20}]}),
    ]
    # A profiler writes the report only when every check is PASS / NOT_APPLICABLE,
    # and a PASS entry's shareable reason is the fixed token below.
    validation_checks = [
        {"name": nm, "status": "PASS", "applicable": True,
         "reason": "candidate_fields_checked"}
        for nm in ("column_shapes_and_support", "percentiles_monotone",
                   "category_counts_le_rowcount", "missing_rate_in_unit_interval",
                   "no_subthreshold_cells_emitted", "correlation_matrix_symmetric",
                   "relationship_support_and_shape")]
    control = {
        "report_version": "2.0",
        "dataset_name": "cps_fixture_control",
        "generated_utc": "2026-09-15T00:00:00Z",
        "generator": {"template_version": "2.0", "language": "Python",
                      "template": "profile_data_template.py"},
        "settings": {"tier": 3, "suppression_threshold": threshold,
                     "max_categorical_levels": 50, "relationship_spec": None,
                     "support_unit": "record", "full_summary_cutoff": 10},
        "dataset": {"row_count": n_rows, "column_count": 4},
        "columns": columns,
        "relationships": {
            "pearson": {"available": True, "columns": ["num_a", "num_b"],
                        "pair_n": [[40, 40], [40, 40]],
                        "matrix": [[1.0, pearson_ab], [pearson_ab, 1.0]]},
            "spearman": {"available": True, "columns": ["num_a", "num_b"],
                         "pair_n": [[40, 40], [40, 40]],
                         "matrix": [[1.0, spearman_ab], [spearman_ab, 1.0]]},
            "cramers_v": [], "named": [],
            "crosstabs": [{"pair": ["cat_a", "cat_b"], "n": n_rows, "available": True,
                           "rows": 3, "cols": 2, "cells": ct_cells,
                           "cells_suppressed": 0}],
        },
        "validation": {"checks": validation_checks, "all_passed": True},
    }
    paths = {}

    def _write(name, obj, ensure_ascii=True):
        p = out / name
        p.write_text(json.dumps(obj, indent=2, ensure_ascii=ensure_ascii), encoding="utf-8")
        paths[name.replace(".json", "")] = str(p)

    def _write_bytes(name, data):
        # Byte-level variants (BOM, raw NUL) that no JSON serializer would emit.
        p = out / name
        p.write_bytes(data)
        paths[name.replace(".json", "")] = str(p)

    _write("report_control.json", control)

    # Sub-threshold variant: cat_b becomes X:20, Y:17, Z:3, so the count-3 level sits
    # at index 2 and a correct FAIL names the index without echoing the count.
    # The cross-tab sits on the released categories (3 x 3), as CPS-INTAKE requires:
    # the full table is rows A / ZQXRARELABEL / __OTHER__ = [10, 10, 0] / [5, 5, 0] /
    # [5, 2, 3], whose totals are exactly the released levels, and the four cells of
    # rows 1-2 x columns Y-Z are hidden as one 2x2 cycle (no cell recoverable from the
    # totals). The visible 0 is a structural zero and every visible cell clears the
    # gate, so the sub-threshold level is the report's one finding.
    sub = json.loads(json.dumps(control))
    sub["dataset_name"] = "cps_fixture_subthreshold"
    for c in sub["columns"]:
        if c["name"] == "cat_b":
            c["categorical"]["levels"] = [{"value": "X", "count": 20},
                                          {"value": "Y", "count": 17},
                                          {"value": "Z", "count": 3}]
            c["n_distinct"] = 3
            c["uniqueness_ratio"] = round(3 / n_rows, 6)
    sub["relationships"]["crosstabs"][0].update(
        {"rows": 3, "cols": 3, "cells": [10, 10, 0, 5, None, None, 5, None, None],
         "cells_suppressed": 4})
    _write("report_subthreshold.json", sub)

    # Missing-block variant: cat_b keeps role categorical but loses its block, so the
    # disclosure sweep must report an incomplete scan rather than a clean one. With no
    # released levels for cat_b there are no categories to build a cross-tab on, so
    # the [cat_a, cat_b] entry is the unavailable one a profiler would write; an
    # available grid over a block-less column is its own row
    # (cps_intake_crosstab_pair_column_without_block).
    miss = json.loads(json.dumps(control))
    miss["dataset_name"] = "cps_fixture_missing_catblock"
    for c in miss["columns"]:
        if c["name"] == "cat_b":
            del c["categorical"]
    miss["relationships"]["crosstabs"] = [{"pair": ["cat_a", "cat_b"], "n": n_rows,
                                           "available": False, "reason": "ineligible_roles"}]
    _write("report_missing_catblock.json", miss)

    # Tier-2 variant that still carries a `relationships` block (the spearman record and
    # the cross-tab). No profiler writes this: CPS-INTAKE treats it as a release beyond
    # the approved scope (`cps_intake_relationships_below_tier3`), while CPS-GEN, which
    # reads only the pearson block, still uses it for its tier-2 SKIPPED control.
    tier2 = json.loads(json.dumps(control))
    tier2["dataset_name"] = "cps_fixture_tier2"
    tier2["settings"]["tier"] = 2
    del tier2["relationships"]["pearson"]
    _write("report_tier2_nopearson.json", tier2)

    # Genuine tier-2 report, shaped the way profile_data_template.py writes one: the
    # `relationships` key is omitted entirely below tier 3 (the profiler only builds it
    # `if TIER == 3`), and the two relationship-family embedded checks are auto-declared
    # NOT_APPLICABLE with the profiler's own reasons ("tier 2 releases no
    # correlations" / "... no relationships"). The absent matrix is then a structural
    # fact ([SKIPPED], 0 matrices declared) and the verdict PASSED.
    tier2g = json.loads(json.dumps(control))
    tier2g["dataset_name"] = "cps_fixture_tier2_genuine"
    tier2g["settings"]["tier"] = 2
    del tier2g["relationships"]
    for chk in tier2g["validation"]["checks"]:
        if chk["name"] == "correlation_matrix_symmetric":
            chk.update(status="NOT_APPLICABLE", applicable=False,
                       reason="tier 2 releases no correlations")
        elif chk["name"] == "relationship_support_and_shape":
            chk.update(status="NOT_APPLICABLE", applicable=False,
                       reason="tier 2 releases no relationships")
    _write("report_tier2_genuine.json", tier2g)

    control_pq = out / "synthetic_control.parquet"
    df.write_parquet(control_pq)
    paths["synthetic_control"] = str(control_pq)

    # Bad-level variant: row 0's cat_a becomes a level the report never released.
    bad_pq = out / "synthetic_badlevel.parquet"
    df.with_columns(pl.when(pl.int_range(pl.len()) == 0).then(pl.lit("Z"))
                    .otherwise(pl.col("cat_a")).alias("cat_a")).write_parquet(bad_pq)
    paths["synthetic_badlevel"] = str(bad_pq)

    # --- CPS-GEN correlation-matrix and percentile-key artifacts --------------
    # Short matrix: a third numeric column exists in both the frame and the report,
    # and the pearson block names all three columns — but still carries the 2x2
    # matrix. The fence used to index past the matrix and abort with an uncaught
    # exception.
    syn3 = df.with_columns((pl.col("num_a") * 2.0).alias("num_c"))
    syn3_pq = out / "synthetic_threecols.parquet"
    syn3.write_parquet(syn3_pq)
    paths["synthetic_threecols"] = str(syn3_pq)
    s_c = syn3["num_c"]
    q1 = json.loads(json.dumps(control))
    q1["dataset_name"] = "cps_fixture_q1_matrix_short"
    q1["dataset"]["column_count"] = 5
    q1["columns"].append(_cps_col_rec(
        syn3, "num_c", "double", "numeric", "numeric",
        {"n": int(s_c.len() - s_c.null_count()), "mean": round(s_c.mean(), 6),
         "sd": round(s_c.std(ddof=1), 6),
         "percentiles": {k: round(s_c.quantile(float(k[1:]) / 100.0, interpolation="linear"), 6)
                         for k in pctls}}))
    q1["relationships"]["pearson"]["columns"] = ["num_a", "num_b", "num_c"]  # 3 names, 2x2 matrix
    _write("report_q1_matrix_short.json", q1)

    # Percentile key: a `median` alias beside p50 on num_a — a key outside the grid
    # vocabulary. Python used to crash parsing it; R misattributed it as an NA
    # quantile and reported [NOT VERIFIED] on the wrong cause.
    q2 = json.loads(json.dumps(control))
    q2["dataset_name"] = "cps_fixture_q2_median_key"
    q2["columns"][0]["numeric"]["percentiles"]["median"] = \
        q2["columns"][0]["numeric"]["percentiles"]["p50"]
    _write("report_q2_median_key.json", q2)

    # --- CPS-INTAKE token-bearing family (`a3a_*`) ------------------------------
    # One base that passes all 12 checks yet carries a released level label (ZQXRARELABEL)
    # with a distinctive count (4441), distinctive four-digit cross-tab cells, and a
    # structurally clean identifier column. Every case is the base plus exactly one
    # perturbation, so a verdict cannot be credited to the wrong cause. row_count
    # 9000 keeps every count far above threshold 5; missing_rate 0 with nonmissing_n
    # 9000 reconciles exactly; the 2x2 cross-tab sums to 9000.
    a3 = json.loads(json.dumps(control))
    a3["dataset_name"] = "cps_fixture_a3a_base"
    a3["dataset"]["row_count"] = 9000
    a3["dataset"]["column_count"] = 5
    for c in a3["columns"]:
        c["missing_rate"] = 0.0
        c["nonmissing_n"] = 9000
        if c["name"] == "cat_a":
            c["categorical"] = {"n": 9000, "n_levels_binned": 0,
                                "levels": [{"value": "ZQXRARELABEL", "count": 4441},
                                           {"value": "OTHERLBL", "count": 4559}]}
            c["n_distinct"] = 2
        elif c["name"] == "cat_b":
            c["categorical"] = {"n": 9000, "n_levels_binned": 0,
                                "levels": [{"value": "X", "count": 4500},
                                           {"value": "Y", "count": 4500}]}
            c["n_distinct"] = 2
    a3["columns"].append({"name": "member_id", "dtype": "string", "role": "identifier",
                          "missing_rate": 0.0, "nonmissing_n": 9000, "n_distinct": 9000,
                          "uniqueness_ratio": 1.0, "is_identifier": True,
                          "string_structure": {"n": 9000, "length_min": 7, "length_mean": 7.0,
                                               "length_max": 7,
                                               "pattern_flags": {"email": False, "phone": False,
                                                                 "date": False, "id": True,
                                                                 "free_text": False}}})
    a3_ct = a3["relationships"]["crosstabs"][0]
    a3_ct.update({"rows": 2, "cols": 2, "n": 9000, "cells": [2221, 2220, 2280, 2279],
                  "cells_suppressed": 0})
    _write("report_a3a_base.json", a3)

    def _a3_grid(cells, rows, cols):
        """The a3 base with entry 0 replaced by a `rows` x `cols` grid on the released
        categories.

        CPS-INTAKE holds an available cross-tab's rows and cols to the number of
        levels its pair columns' categorical blocks release (VC § CPS Usage Notes,
        "Released categories"), so a grid of another shape must re-release cat_a at
        `rows` levels and cat_b at `cols`. The grid is completed into a full table —
        the hidden cells share what the visible cells leave of n 9000 as evenly as
        whole numbers allow — and that table's row and column totals become the two
        columns' level counts. The report is then one a profiler could have written:
        the levels sum to n, every total clears the gate, and the hidden cells are
        exactly the cells the released totals constrain. The first two levels keep
        the planted labels ZQXRARELABEL / OTHERLBL and X / Y.
        """
        v = json.loads(json.dumps(a3))
        hidden = [i for i, x in enumerate(cells) if x is None]
        deficit = 9000 - sum(x for x in cells if x is not None)
        assert len(cells) == rows * cols and len(hidden) > 0 and deficit >= len(hidden), \
            (rows, cols, deficit)
        full = list(cells)
        for k, i in enumerate(hidden):
            full[i] = deficit // len(hidden) + (1 if k < deficit % len(hidden) else 0)
        row_tot = [sum(full[r * cols:(r + 1) * cols]) for r in range(rows)]
        col_tot = [sum(full[r * cols + c] for r in range(rows)) for c in range(cols)]
        assert sum(row_tot) == 9000 and min(row_tot + col_tot) >= threshold, (row_tot, col_tot)
        for pos, labels, totals in (
                (2, ["ZQXRARELABEL", "OTHERLBL"] + [f"a{i}" for i in range(2, rows)], row_tot),
                (3, ["X", "Y"] + [f"b{j}" for j in range(2, cols)], col_tot)):
            v["columns"][pos]["categorical"] = {
                "n": 9000, "n_levels_binned": 0,
                "levels": [{"value": lbl, "count": t} for lbl, t in zip(labels, totals)]}
            v["columns"][pos]["n_distinct"] = len(totals)
            v["columns"][pos]["uniqueness_ratio"] = round(len(totals) / 9000, 6)
        v["relationships"]["crosstabs"][0].update(
            {"rows": rows, "cols": cols, "cells": list(cells), "cells_suppressed": len(hidden)})
        return v

    def _with_cat_c(v):
        """Append a third categorical column, cat_c (P / Q, 4500 each), so a second
        cross-tab entry can cover a pair of its own: two entries on one unordered pair
        are a finding in their own right ("One cross-tab per unordered pair")."""
        v["dataset"]["column_count"] += 1
        v["columns"].append({"name": "cat_c", "dtype": "string", "role": "categorical",
                             "missing_rate": 0.0, "nonmissing_n": 9000, "n_distinct": 2,
                             "uniqueness_ratio": round(2 / 9000, 6), "is_identifier": False,
                             "categorical": {"n": 9000, "n_levels_binned": 0,
                                             "levels": [{"value": "P", "count": 4500},
                                                        {"value": "Q", "count": 4500}]}})
        return v

    # Collapsed entry over an all-null grid — the legitimate whole-table hide.
    v = json.loads(json.dumps(a3))
    v["relationships"]["crosstabs"][0].update(
        {"cells": [None, None, None, None], "cells_suppressed": 4, "collapsed": True})
    _write("report_a3a_q3a_collapsed_allnull.json", v)

    # A clean entry 0 plus a collapsed entry 1 that still shows one visible cell (the
    # planted 2221) — the FAIL must name the positional index 1. Entry 1 covers its
    # own pair [cat_b, cat_c], so the collapsed-but-visible finding is the only one.
    v = _with_cat_c(json.loads(json.dumps(a3)))
    v["relationships"]["crosstabs"].append(
        {"pair": ["cat_b", "cat_c"], "n": 9000, "available": True, "rows": 2, "cols": 2,
         "cells": [2221, None, None, None], "cells_suppressed": 3, "collapsed": True})
    _write("report_a3a_q3b_collapsed_visible.json", v)

    # The identifier's string_structure carries example = the planted value.
    v = json.loads(json.dumps(a3))
    v["columns"][4]["string_structure"]["example"] = "QZ-8417"
    _write("report_a3a_q4a_identifier_example.json", v)

    # The sanctioned withheld shape {n, withheld: true, reason} (n < k). The spec makes
    # a string_structure's n its column's nonmissing_n (the support gate in
    # no_released_count_below_threshold checks it), so the column record is made
    # consistent with n = 3 — a report a profiler could write.
    v = json.loads(json.dumps(a3))
    v["columns"][4]["string_structure"] = {"n": 3, "withheld": True,
                                           "reason": "insufficient_support"}
    v["columns"][4].update(nonmissing_n=3, n_distinct=3, uniqueness_ratio=1.0,
                           missing_rate=round((9000 - 3) / 9000, 6))
    _write("report_a3a_q4b_identifier_withheld.json", v)

    # The identifier example above plus an all-null collapsed entry 1 on its own pair
    # [cat_b, cat_c], i.e. JSON nulls in a sibling subtree the R walker pops before
    # `columns`. The FAIL path must still read report.columns[4].string_structure.example
    # (cat_c is appended at index 5) — the R stack used to desynchronise from its path
    # list on a NULL push.
    v = _with_cat_c(json.loads(json.dumps(a3)))
    v["columns"][4]["string_structure"]["example"] = "QZ-8417"
    v["relationships"]["crosstabs"].append(
        {"pair": ["cat_b", "cat_c"], "n": 9000, "available": True, "rows": 2, "cols": 2,
         "cells": [None, None, None, None], "cells_suppressed": 4, "collapsed": True})
    _write("report_a3a_q4d_null_sibling.json", v)

    # A 12-element scalar list (cap 9) holding one JSON null, under a key name that is
    # not value-shaped, so only rule (2) can catch it. The R fence used to treat a
    # null-bearing list as non-scalar and exempt it.
    v = json.loads(json.dumps(a3))
    v["columns"][0]["numeric"]["notes"] = [f"v{k}" for k in range(11)] + [None]
    _write("report_a3a_q4e_null_in_long_list.json", v)

    # Leak variant: a sub-threshold level with a distinctive count. The gate is
    # raised to 1000 so the offending count can be 673 — distinctive enough to scan
    # the whole of stdout for — while every other released count stays >= 1000. The
    # FAIL must name the block and level index only; 673 must reach no line. At gate
    # 1000 the full-summary cutoff is also 1000, so each numeric block's n is raised to
    # its column's nonmissing_n (9000): the full summaries then sit in their support
    # band and the level is the sweep's one breach. The cross-tab sits on the released
    # categories (2 x 3): the full table is [2221, 1920, 300] / [2279, 1907, 373], and
    # every cell of the Y and Z columns is below the 1000 gate or hidden with them, so
    # columns Y-Z are hidden whole — one 2x2 cycle, no cell recoverable from the totals.
    v = json.loads(json.dumps(a3))
    v["dataset_name"] = "cps_fixture_a3a_leak_subthreshold"
    v["settings"]["suppression_threshold"] = 1000
    for c in v["columns"]:
        if c["role"] == "numeric":
            c["numeric"]["n"] = 9000
        if c["name"] == "cat_b":
            c["categorical"]["levels"] = [{"value": "X", "count": 4500},
                                          {"value": "Y", "count": 3827},
                                          {"value": "Z", "count": 673}]
            c["n_distinct"] = 3
    v["relationships"]["crosstabs"][0].update(
        {"rows": 2, "cols": 3, "cells": [2221, None, None, 2279, None, None],
         "cells_suppressed": 4})
    _write("report_a3a_leak_subthreshold.json", v)

    # --- Strict-schema regression artifacts (CPS-INTAKE / CPS-GEN) ------------
    # Each is the a3 base plus one perturbation (so ZQXRARELABEL / OTHERLBL / the
    # four-digit counts stay planted). Where a perturbation needs a value, it is the
    # planted token `Realname`, so the whole-stdout scan also proves the FAIL lines
    # name keys and positions, never the offending value.
    # Rule 1 is case-insensitive — a capitalised `Sample` list is a dump.
    v = json.loads(json.dumps(a3))
    v["columns"][2]["Sample"] = ["Alice Q. Realname", "Bob R. Realname"]
    _write("report_a3a_i1a_sample_capitalised.json", v)
    # Rule 4's per-role allow-list catches a key no deny-list named.
    v = json.loads(json.dumps(a3))
    v["columns"][3]["top_values"] = ["Alice Q. Realname", "Bob R. Realname"]
    _write("report_a3a_i1b_top_values.json", v)
    # A 401-digit integer is exact in Python but Inf in jsonlite. Any number token
    # longer than 64 characters is a parse error in both languages, so this one is
    # refused before either parser reads it.
    v = json.loads(json.dumps(a3))
    v["columns"][0]["numeric"]["percentiles"]["p99"] = 10 ** 400
    _write("report_a3a_i4_401_digit_percentile.json", v)
    # An allow-listed numeric key holding a string is a value in disguise.
    v = json.loads(json.dumps(a3))
    v["columns"][0]["numeric"]["n"] = "Realname"
    _write("report_a3a_s1_string_n.json", v)
    # Cross-tab dimensions are a validated field, so -2 is a [FAIL].
    v = json.loads(json.dumps(a3))
    v["relationships"]["crosstabs"][0].update({"rows": -2, "cols": -2})
    _write("report_a3a_e4_negative_dims.json", v)
    # Column dtype held to the spec vocabulary; the value is never echoed.
    v = json.loads(json.dumps(a3))
    v["columns"][0]["dtype"] = "Realname"
    _write("report_a3a_bad_dtype.json", v)
    # The settings subtree is held to the spec key allow-list (rule 5).
    v = json.loads(json.dumps(a3))
    v["settings"]["comment"] = "Realname"
    _write("report_a3a_settings_unknown_key.json", v)
    # A PASS entry's reason must be `candidate_fields_checked`; free text is a leak path.
    v = json.loads(json.dumps(a3))
    v["validation"]["checks"][0]["reason"] = "Realname checked by hand"
    _write("report_a3a_free_text_reason.json", v)
    # The report declares a weaker gate (1) than the researcher approved (5) and
    # releases a count (2) that only the weaker gate would let through. Its cross-tab
    # sits on the released categories (2 x 3) and releases the Z column's small cells
    # in full, as a profiler run at gate 1 would; its totals match the levels exactly.
    v = json.loads(json.dumps(a3))
    v["settings"]["suppression_threshold"] = 1
    v["columns"][3]["categorical"]["levels"] = [{"value": "X", "count": 4500},
                                                {"value": "Y", "count": 4498},
                                                {"value": "Z", "count": 2}]
    v["columns"][3]["n_distinct"] = 3
    v["relationships"]["crosstabs"][0].update(
        {"rows": 2, "cols": 3, "cells": [2221, 2219, 1, 2279, 2279, 1]})
    _write("report_a3a_i6_declared_below_approved.json", v)
    # A report stricter than the approval is honoured at its own value.
    v = json.loads(json.dumps(a3))
    v["settings"]["suppression_threshold"] = 10
    _write("report_a3a_declared_above_approved.json", v)

    # --- Cross-tab complementary-suppression fixtures (lone cells) -------------
    # Pure lone-cell grids (VC § CPS Usage Notes, "Complementary suppression"): the
    # hidden cells are a 4-cycle plus ONE pendant cell, so the only recoverable hidden
    # cell is the lone one and the FAIL names one position with no `(+N more)`. Every
    # grid below is built by `_a3_grid`, so cat_a and cat_b release exactly as many
    # levels as the grid has rows and columns. Row-only: hidden (0,0) hangs off the
    # cycle rows 1-2 x cols 0-1, so rows hold 1/2/2 nulls and columns 3/2/0.
    _write("report_a3a_lone_cell_row.json",
           _a3_grid([None, 2221, 2220, None, None, 2280, None, None, 1100], 3, 3))
    # Column-only: the transpose — hidden (0,0) hangs off the cycle rows 0-1 x cols
    # 1-2, so columns hold 1/2/2 nulls and rows 3/2/0.
    _write("report_a3a_lone_cell_col.json",
           _a3_grid([None, None, None, 2221, None, None, 2220, 2280, 1100], 3, 3))
    # The two earlier lone-cell grids, kept as rows of their own: each holds the lone
    # cell AND a hidden cell whose row and column both hold two or more nulls but which
    # lies on no cycle (row-only grid: (1,0); column-only grid: (0,1)), so the lone-cell
    # line is followed by `(+1 more)`. Exact recovery of both cells was confirmed by an
    # independent rational-arithmetic solver that uses no graph code.
    _write("report_a3a_lone_cell_row_with_bridge.json",
           _a3_grid([None, 2221, 2220, None, None, None, 2280, None, None], 3, 3))
    _write("report_a3a_lone_cell_col_with_bridge.json",
           _a3_grid([None, None, 2221, 2220, None, None, 2280, None, None], 3, 3))

    # --- Bridge-cell suppression fixtures (VC § CPS Usage Notes, "Complementary
    # suppression") -------------------------------------------------------------
    # Read the hidden cells as edges between their row and their column; a hidden
    # cell is exactly recoverable from the released totals iff its edge is a bridge
    # (lies on no cycle). The planted labels ride along on the a3 base. Every grid's
    # visible cells are >= the gate (or a structural 0) and sum below n 9000, and the
    # grid sits on the released categories, so the cross-tab bridge rule is the only
    # finding a FAIL row can carry.
    # One bridge: 2x2 cycles rows 0-1 x cols 0-1 and rows 2-3 x cols 2-3, joined by
    # hidden (2,1) — row 2 and column 1 each hold three nulls, so no line is lone.
    _write("report_a3a_bridge_one.json",
           _a3_grid([None, None, 2221, 2220, None, None, 2280, 400,
                     300, None, None, None, 200, 100, None, None], 4, 4))
    # Two bridges: the same two cycles on a 4x5 grid, joined through column 4 by the
    # path row 1 - column 4 - row 2, so hidden (1,4) and (2,4) are both bridges.
    _write("report_a3a_bridge_two.json",
           _a3_grid([None, None, 2221, 2220, 2280, None, None, 300, 300, None,
                     300, 300, None, None, None, 300, 300, None, None, 300], 4, 5))
    # Hidden 2x2 cycle: every hidden cell lies on the cycle — PASS.
    _write("report_a3a_hidden_2x2_cycle.json",
           _a3_grid([None, None, 2221, None, None, 2220, 2280, 1100, 600], 3, 3))
    # One 6-cycle on a 3x3 grid: r0-c0-r2-c2-r1-c1-r0 — PASS.
    _write("report_a3a_six_cycle_3x3.json",
           _a3_grid([None, None, 2221, 2220, None, None, None, 2280, None], 3, 3))
    # A hidden 2x2 cycle beside two visible structural zeros: a visible 0 is not an
    # edge, so it neither breaks the cycle nor counts as hidden — PASS.
    _write("report_a3a_cycle_with_structural_zeros.json",
           _a3_grid([None, None, 0, None, None, 2221, 0, 2220, 2280], 3, 3))
    # A genuine tier-3 report written by an earlier profile_data_template.py (before
    # profilers removed bridge cells), copied field for field. Its 4x4 cross-tab hides
    # two 2x2 cycles joined by hidden (1,2), which that profiler released and the
    # earlier lone-cell-only rule passed. Only two level labels are changed — `a2` and
    # `a0` become the planted ZQXRARELABEL and OTHERLBL — so the whole-stdout leak scan
    # has a token to look for; no rule reads a label's spelling.
    genuine_bridge = {
        "report_version": "2.0", "dataset_name": "bridge",
        "generated_utc": "2026-10-06T18:46:34Z",
        "generator": {"language": "Python", "template": "profile_data_template.py",
                      "template_version": "2.0"},
        "settings": {"tier": 3, "suppression_threshold": 5, "max_categorical_levels": 50,
                     "relationship_spec": [["cat_a", "cat_b"]], "support_unit": "record",
                     "full_summary_cutoff": 10},
        "dataset": {"row_count": 100, "column_count": 2},
        "columns": [
            {"name": "cat_a", "dtype": "string", "role": "categorical", "missing_rate": 0.0,
             "nonmissing_n": 100, "n_distinct": 4, "uniqueness_ratio": 0.04,
             "is_identifier": False,
             "categorical": {"n": 100, "n_levels_binned": 0,
                             "levels": [{"value": "ZQXRARELABEL", "count": 28},
                                        {"value": "OTHERLBL", "count": 27},
                                        {"value": "a3", "count": 23},
                                        {"value": "a1", "count": 22}]}},
            {"name": "cat_b", "dtype": "string", "role": "categorical", "missing_rate": 0.0,
             "nonmissing_n": 100, "n_distinct": 4, "uniqueness_ratio": 0.04,
             "is_identifier": False,
             "categorical": {"n": 100, "n_levels_binned": 0,
                             "levels": [{"value": "b3", "count": 30},
                                        {"value": "b1", "count": 28},
                                        {"value": "b0", "count": 23},
                                        {"value": "b2", "count": 19}]}}],
        "relationships": {
            "cramers_v": [{"pair": ["cat_a", "cat_b"], "n": 100, "available": True,
                           "v": 0.402471}],
            "named": [],
            "crosstabs": [{"pair": ["cat_a", "cat_b"], "n": 100, "available": True,
                           "rows": 4, "cols": 4,
                           "cells": [None, None, 10, 12, None, None, None, 15,
                                     11, 13, None, None, 9, 8, None, None],
                           "cells_suppressed": 9}],
            "pearson": {"available": False, "columns": [], "pair_n": [], "matrix": [],
                        "reason": "fewer_than_two_eligible_columns"},
            "spearman": {"available": False, "columns": [], "pair_n": [], "matrix": [],
                         "reason": "fewer_than_two_eligible_columns"}},
        "validation": {"checks": [
            {"name": "column_shapes_and_support", "status": "PASS", "applicable": True,
             "reason": "candidate_fields_checked"},
            {"name": "percentiles_monotone", "status": "NOT_APPLICABLE", "applicable": False,
             "reason": "report declares 0 numeric columns at tier 3"},
            {"name": "category_counts_le_rowcount", "status": "PASS", "applicable": True,
             "reason": "candidate_fields_checked"},
            {"name": "missing_rate_in_unit_interval", "status": "PASS", "applicable": True,
             "reason": "candidate_fields_checked"},
            {"name": "no_subthreshold_cells_emitted", "status": "PASS", "applicable": True,
             "reason": "candidate_fields_checked"},
            {"name": "correlation_matrix_symmetric", "status": "NOT_APPLICABLE",
             "applicable": False,
             "reason": "0 of 2 correlation blocks released (fewer_than_two_eligible_columns)"},
            {"name": "relationship_support_and_shape", "status": "PASS", "applicable": True,
             "reason": "candidate_fields_checked"}],
            "all_passed": True}}
    _write("report_genuine_old_profiler_bridge.json", genuine_bridge)
    # A hidden cell mis-coded as 0 instead of null: cells_suppressed says one cell was
    # hidden, the grid holds no null. Since structural zeros became legitimate (a
    # visible 0 is never itself a finding), the cells_suppressed-vs-null-count
    # agreement is what catches the mis-coding — and because the grid then "hides no
    # cell", the differencing residual (6780 visible vs n 9000) fires behind it.
    v = json.loads(json.dumps(a3))
    v["relationships"]["crosstabs"][0].update({"cells": [2221, 0, 2280, 2279],
                                               "cells_suppressed": 1})
    _write("report_a3a_hidden_coded_zero.json", v)
    # cells_suppressed claims 2 hidden cells over a grid that hides none.
    v = json.loads(json.dumps(a3))
    v["relationships"]["crosstabs"][0]["cells_suppressed"] = 2
    _write("report_a3a_suppressed_count_disagrees.json", v)

    # --- Disclosure fixtures (CPS-INTAKE level / cell / scope) ------------------
    # Each is the a3 base plus one perturbation. Level counts first.
    v = json.loads(json.dumps(a3))   # a negative level count is below any gate
    v["columns"][2]["categorical"]["levels"][0]["count"] = -4441
    _write("report_a3a_negative_level_count.json", v)
    # A level listed at 0 still names a category. The cross-tab carries that level as
    # a third column of structural zeros (2 x 3, totals equal to the levels), so the
    # zero-count level is the report's one finding.
    v = json.loads(json.dumps(a3))
    v["columns"][3]["categorical"]["levels"] = [{"value": "X", "count": 4500},
                                                {"value": "Y", "count": 4500},
                                                {"value": "ZQXRARELABEL", "count": 0}]
    v["relationships"]["crosstabs"][0].update(
        {"rows": 2, "cols": 3, "cells": [2221, 2220, 0, 2279, 2280, 0]})
    _write("report_a3a_zero_count_level.json", v)
    v = json.loads(json.dumps(a3))   # levels sum to 8998 against n 9000: residual 2
    v["columns"][3]["categorical"]["levels"][1]["count"] = 4498
    _write("report_a3a_level_sum_residual.json", v)
    v = json.loads(json.dumps(a3))   # block n 8998 against nonmissing_n 9000
    v["columns"][3]["categorical"]["n"] = 8998
    v["columns"][3]["categorical"]["levels"][1]["count"] = 4498
    _write("report_a3a_cat_n_mismatch.json", v)
    # Cross-tab cells: residual with nothing hidden, a negative cell, a structural zero.
    v = json.loads(json.dumps(a3))
    v["relationships"]["crosstabs"][0]["cells"] = [2221, 2220, 2280, 2277]
    _write("report_a3a_crosstab_residual.json", v)
    v = json.loads(json.dumps(a3))
    v["relationships"]["crosstabs"][0]["cells"] = [2221, 2220, 2280, -2279]
    _write("report_a3a_negative_cell.json", v)
    v = json.loads(json.dumps(a3))   # sums to n 9000 with one visible structural zero
    v["relationships"]["crosstabs"][0]["cells"] = [2221, 0, 4500, 2279]
    _write("report_a3a_structural_zero.json", v)
    # Free-text channels the rule-4 / rule-6 tests close.
    v = json.loads(json.dumps(a3))   # a level label that is a list, not a string
    v["columns"][2]["categorical"]["levels"][0]["value"] = ["ZQXRARELABEL", "Realname"]
    _write("report_a3a_level_value_list.json", v)
    v = json.loads(json.dumps(a3))   # an unknown top-level key carrying free text
    v["notes"] = "Realname exported this by hand"
    _write("report_a3a_toplevel_extra.json", v)
    v = json.loads(json.dumps(a3))   # dataset_name outside [A-Za-z0-9_-]+
    v["dataset_name"] = "Realname survey export"
    _write("report_a3a_dataset_name_freetext.json", v)
    # Escaping: an identifier column whose name tries to forge a count line and a
    # verdict with embedded newlines, and one with a non-ASCII name written as raw
    # UTF-8. Each carries one extra (non-allow-listed) key so the identifier check
    # has to print the name on a FAIL line.
    v = json.loads(json.dumps(a3))
    v["columns"][4]["name"] = CPS_FORGED_NAME
    v["columns"][4]["extra"] = "QZ-8417"
    _write("report_a3a_newline_name.json", v)
    v = json.loads(json.dumps(a3))
    v["columns"][4]["name"] = "café_id"
    v["columns"][4]["extra"] = "QZ-8417"
    _write("report_a3a_nonascii_name.json", v, ensure_ascii=False)

    # --- Review-cycle-4 artifacts (CPS-INTAKE support gate, dtype, tier 1) ------
    # Each is the a3 base plus one perturbation. Gate k = 5, full-summary cutoff
    # f = max(k, 10) = 10. Every band breach below sits one step under its band's
    # lower edge; the `edges` report puts every band exactly on its edge (PASS).
    a3_grid = a3["columns"][0]["numeric"]["percentiles"]
    a3_small = {"p25": a3_grid["p25"], "p50": a3_grid["p50"], "p75": a3_grid["p75"]}
    v = json.loads(json.dumps(a3))   # full summary at n = f - 1
    v["columns"][0]["numeric"]["n"] = 9
    _write("report_a3a_gate_full_below_cutoff.json", v)
    v = json.loads(json.dumps(a3))   # small_n at n = k - 1
    v["columns"][0]["numeric"] = {"n": 4, "small_n": True, "percentiles": dict(a3_small)}
    _write("report_a3a_gate_small_n_below_gate.json", v)
    v = json.loads(json.dumps(a3))   # constant at n = k - 1
    v["columns"][0]["numeric"] = {"n": 4, "constant": True, "value": 50.0, "mean": 50.0, "sd": 0.0}
    _write("report_a3a_gate_constant_below_gate.json", v)
    v = json.loads(json.dumps(a3))   # full identifier string_structure at n = k - 1
    v["columns"][4]["string_structure"]["n"] = 4
    v["columns"][4].update(nonmissing_n=4, n_distinct=4, uniqueness_ratio=1.0,
                           missing_rate=round((9000 - 4) / 9000, 6))
    _write("report_a3a_gate_string_structure_below_gate.json", v)
    named_entry = {"outcome": "num_a", "predictor": "num_b", "n": 9, "available": True,
                   "pearson": 0.7, "spearman": 0.7,
                   "ols": {"intercept": 1.5, "slope": 0.2, "r_squared": 0.49}}
    v = json.loads(json.dumps(a3))   # available named (OLS) entry at n = f - 1
    v["relationships"]["named"] = [dict(named_entry)]
    _write("report_a3a_gate_named_below_cutoff.json", v)
    cramers_entry = {"pair": ["cat_a", "cat_b"], "n": 4, "v": 0.1, "available": True}
    v = json.loads(json.dumps(a3))   # available Cramer's V at n = k - 1
    v["relationships"]["cramers_v"] = [dict(cramers_entry)]
    _write("report_a3a_gate_cramers_v_below_gate.json", v)
    # Every band on its lower edge: num_a full at n = f, a third numeric column num_c
    # small_n at n = k, the identifier's full string_structure at n = k, named at n = f,
    # Cramer's V at n = k — and the named entry's two complement groups on theirs: its
    # outcome num_a (n 10) leaves 0 records outside the entry's n 10, and its predictor
    # num_b (full at n 15) leaves exactly k = 5. The small_n edge sits on num_c because a
    # named end at n = k could only leave a negative complement group against n = f.
    v = json.loads(json.dumps(a3))
    v["dataset"]["column_count"] = 6
    v["columns"][0]["numeric"]["n"] = 10
    v["columns"][1]["numeric"]["n"] = 15
    num_c = json.loads(json.dumps(v["columns"][1]))
    num_c["name"] = "num_c"
    num_c["numeric"] = {"n": 5, "small_n": True, "percentiles": {
        k: num_c["numeric"]["percentiles"][k] for k in ("p25", "p50", "p75")}}
    v["columns"].append(num_c)
    v["columns"][4]["string_structure"]["n"] = 5
    v["columns"][4].update(nonmissing_n=5, n_distinct=5, uniqueness_ratio=1.0,
                           missing_rate=round((9000 - 5) / 9000, 6))
    v["relationships"]["named"] = [dict(named_entry, n=10)]
    v["relationships"]["cramers_v"] = [dict(cramers_entry, n=5)]
    _write("report_a3a_gate_edges.json", v)

    # --- Complement groups of a named regression (support gate, VC § CPS Usage Notes,
    # "Complement groups of a named regression") -----------------------------------
    # For an available named entry each end's complement group is g = (the end's
    # numeric-block n) - (the entry's pair-complete n): the records with that column but
    # not the other. It must be 0 or >= the gate k = 5. The a3 base's numeric blocks carry
    # n 40, so the entry's n and the ends' n set g directly; every entry keeps n >= f.
    def _a3_named(entry_n, n_a=None, n_b=None, **entry):
        v = json.loads(json.dumps(a3))
        if n_a is not None:
            v["columns"][0]["numeric"]["n"] = n_a
        if n_b is not None:
            v["columns"][1]["numeric"]["n"] = n_b
        v["relationships"]["named"] = [dict(named_entry, n=entry_n, **entry)]
        return v
    # Outcome g = 40 - 36 = 4 = k - 1 (the predictor's is 4 too; one finding per entry,
    # outcome first).
    _write("report_a3a_cg_outcome_below_gate.json", _a3_named(36))
    # Outcome g = 0, predictor g = 44 - 40 = 4 = k - 1.
    _write("report_a3a_cg_predictor_below_gate.json", _a3_named(40, n_b=44))
    # Both groups exactly k: 45 - 40 = 5 on each end.
    _write("report_a3a_cg_at_gate.json", _a3_named(40, n_a=45, n_b=45))
    # Both groups empty: every record of either column is pair-complete.
    _write("report_a3a_cg_zero.json", _a3_named(40))
    # The outcome is a categorical column, which carries no numeric block — there is no
    # whole-number numeric n to gate its complement group on.
    _write("report_a3a_cg_outcome_no_numeric_n.json", _a3_named(40, outcome="cat_a"))
    # The profiler's own answer to a small complement group: the entry is withheld with
    # reason small_complement_group (an unavailable named entry carries no estimates).
    v = json.loads(json.dumps(a3))
    v["relationships"]["named"] = [{"outcome": "num_a", "predictor": "num_b", "n": 36,
                                    "available": False, "reason": "small_complement_group"}]
    _write("report_a3a_cg_reason_small_complement_group.json", v)
    # Leak variant: at gate 1000 the outcome's complement group is 9000 - 8327 = 673, the
    # planted three-digit token. The group size is derived, never released, and must reach
    # no line. Numeric blocks carry n 9000 / 8327 so the full summaries sit in their band.
    v = _a3_named(8327, n_a=9000, n_b=8327)
    v["settings"]["suppression_threshold"] = 1000
    _write("report_a3a_cg_leak_gate_1000.json", v)

    # --- Duplicate level labels (rule 4, VC § CPS Usage Notes, "Distinct labels") ---
    # On a third categorical column cat_c that no cross-tab uses, so the repeated label
    # is the report's one finding. Q's 4500 is split across two entries labelled Q; the
    # level counts still sum to n 9000 and each clears the gate.
    v = _with_cat_c(json.loads(json.dumps(a3)))
    v["columns"][5]["categorical"]["levels"] = [{"value": "P", "count": 4500},
                                                {"value": "Q", "count": 2250},
                                                {"value": "Q", "count": 2250}]
    _write("report_a3a_dup_level_label.json", v)
    # The same with the pooled bucket written twice: `__OTHER__` is a label like any other.
    v = _with_cat_c(json.loads(json.dumps(a3)))
    v["columns"][5]["categorical"] = {"n": 9000, "n_levels_binned": 4,
                                      "levels": [{"value": "P", "count": 4500},
                                                 {"value": "__OTHER__", "count": 2250},
                                                 {"value": "__OTHER__", "count": 2250}]}
    _write("report_a3a_dup_level_other.json", v)
    # A categorical record whose dtype is a vocabulary word other than "string".
    v = json.loads(json.dumps(a3))
    v["columns"][3]["dtype"] = "integer"
    _write("report_a3a_categorical_dtype_integer.json", v)
    # Tier 1 releases {name, dtype} per column. The identifier record still carries the
    # tier-2 metadata keys (but no string_structure, so the support gate stays out of
    # it). No level or cell survives at tier 1, so the planted token rides in
    # dataset_name, which no outcome line prints.
    t1 = json.loads(json.dumps(a3))
    t1["dataset_name"] = "cps_fixture_t1_ZQXRARELABEL"
    t1["settings"]["tier"] = 1
    del t1["relationships"]
    t1["columns"] = [{"name": c["name"], "dtype": c["dtype"]} for c in a3["columns"][:4]]
    t1["columns"].append({"name": "member_id", "dtype": "string", "role": "identifier",
                          "missing_rate": 0.0, "nonmissing_n": 9000, "n_distinct": 9000,
                          "uniqueness_ratio": 1.0, "is_identifier": True})
    t1_na = {"percentiles_monotone": "report declares 0 numeric columns at tier 1",
             "category_counts_le_rowcount": "report declares 0 categorical columns at tier 1",
             "missing_rate_in_unit_interval": "tier 1 releases name and dtype only",
             "correlation_matrix_symmetric": "tier 1 releases no correlations",
             "relationship_support_and_shape": "tier 1 releases no relationships"}
    for chk in t1["validation"]["checks"]:
        if chk["name"] in t1_na:
            chk.update(status="NOT_APPLICABLE", applicable=False, reason=t1_na[chk["name"]])
    _write("report_t1_identifier_t2_keys.json", t1)

    # --- One cross-tab per unordered pair, on the released categories ----------
    # (VC § CPS Usage Notes, "One cross-tab per unordered pair of two distinct columns"
    # and "Released categories"). Each is the a3 base plus one perturbation; every
    # added grid is internally sound (no hidden cell, cells summing to n 9000, visible
    # cells 0 or >= the gate), so the rule under test is the only finding.
    a3_entry = dict(a3["relationships"]["crosstabs"][0])
    # A self-pair at entry index 1: a cat_a x cat_a "table" is the diagonal of cat_a's
    # own level counts — no cross-tab at all.
    self_pair = {"pair": ["cat_a", "cat_a"], "n": 9000, "available": True, "rows": 2,
                 "cols": 2, "cells": [4441, 0, 0, 4559], "cells_suppressed": 0}
    v = json.loads(json.dumps(a3))
    v["relationships"]["crosstabs"].append(dict(self_pair))
    _write("report_a3a_self_pair.json", v)
    # The same self-pair entered twice (entry indices 1 and 2): entry 2 is both a
    # self-pair and a repeat of entry 1, so three findings in all.
    v = json.loads(json.dumps(a3))
    v["relationships"]["crosstabs"] += [dict(self_pair), dict(self_pair)]
    _write("report_a3a_self_pair_twice.json", v)
    # Entry 0's pair again at entry index 1, same order and same grid.
    v = json.loads(json.dumps(a3))
    v["relationships"]["crosstabs"].append(json.loads(json.dumps(a3_entry)))
    _write("report_a3a_repeat_pair_same_order.json", v)
    # Entry 0's pair again at entry index 1 in swapped order: [cat_b, cat_a] with the
    # transposed grid, which hides nothing the first does not — still a repeat.
    v = json.loads(json.dumps(a3))
    v["relationships"]["crosstabs"].append(
        {"pair": ["cat_b", "cat_a"], "n": 9000, "available": True, "rows": 2, "cols": 2,
         "cells": [2221, 2280, 2220, 2279], "cells_suppressed": 0})
    _write("report_a3a_repeat_pair_swapped.json", v)
    # An unavailable entry on the pair first (index 0), then the available grid
    # (index 1): the rule holds whatever `available` says, so the available entry is
    # reported as the repeat and the unavailable one is the first entry on the pair.
    v = json.loads(json.dumps(a3))
    v["relationships"]["crosstabs"] = [
        {"pair": ["cat_b", "cat_a"], "n": 9000, "available": False,
         "reason": "insufficient_support"},
        json.loads(json.dumps(a3_entry))]
    _write("report_a3a_repeat_pair_unavailable_first.json", v)
    # A third row for a level cat_a's block does not release (as if a source level
    # pooled into __OTHER__ kept a row of its own): rows 3 against 2 released levels.
    v = json.loads(json.dumps(a3))
    v["relationships"]["crosstabs"][0].update(
        {"rows": 3, "cols": 2, "cells": [2221, 2220, 2280, 2272, 0, 7]})
    _write("report_a3a_crosstab_rows_unequal.json", v)
    # The same along the columns: cols 3 against cat_b's 2 released levels.
    v = json.loads(json.dumps(a3))
    v["relationships"]["crosstabs"][0].update(
        {"rows": 2, "cols": 3, "cells": [2221, 2215, 5, 2279, 2280, 0]})
    _write("report_a3a_crosstab_cols_unequal.json", v)
    # Pair position 0 is a numeric column (num_a): there are no released categories to
    # put a grid on. Position 1 (cat_b, 2 levels) matches its 2 columns.
    v = json.loads(json.dumps(a3))
    v["relationships"]["crosstabs"][0]["pair"] = ["num_a", "cat_b"]
    _write("report_a3a_crosstab_pair_numeric.json", v)
    # Pair position 1 is the identifier column (member_id).
    v = json.loads(json.dumps(a3))
    v["relationships"]["crosstabs"][0]["pair"] = ["cat_a", "member_id"]
    _write("report_a3a_crosstab_pair_identifier.json", v)
    # cat_b keeps role categorical but carries no categorical block, while the
    # available [cat_a, cat_b] grid stays.
    v = json.loads(json.dumps(a3))
    del v["columns"][3]["categorical"]
    _write("report_a3a_crosstab_pair_without_block.json", v)
    # cat_b's categorical block is present but its `levels` is not an array.
    v = json.loads(json.dumps(a3))
    v["columns"][3]["categorical"]["levels"] = None
    _write("report_a3a_crosstab_pair_levels_null.json", v)
    # A genuine-shape PASS: the grid sits on the released categories the way the
    # profilers build it. cat_a releases three kept levels in code-point label order
    # (MISSPAIR < OTHERLBL < ZQXRARELABEL) and then __OTHER__ for its three pooled
    # source levels; cat_b is missing on exactly the 1000 MISSPAIR rows, so the pair
    # has 8000 complete rows and the MISSPAIR row is a row of structural zeros. The
    # pooled __OTHER__ row is one row — no pooled source level has a row of its own.
    # Row totals 0 / 3000 / 4441 / 559 and column totals 4000 / 4000 equal the
    # pair-complete counts behind the released levels.
    v = json.loads(json.dumps(a3))
    v["dataset_name"] = "cps_fixture_a3a_released_categories"
    v["columns"][2].update(n_distinct=6, uniqueness_ratio=round(6 / 9000, 6))
    v["columns"][2]["categorical"] = {
        "n": 9000, "n_levels_binned": 3,
        "levels": [{"value": "MISSPAIR", "count": 1000}, {"value": "OTHERLBL", "count": 3000},
                   {"value": "ZQXRARELABEL", "count": 4441}, {"value": "__OTHER__", "count": 559}]}
    v["columns"][3].update(missing_rate=round(1000 / 9000, 6), nonmissing_n=8000,
                           uniqueness_ratio=round(2 / 8000, 6))
    v["columns"][3]["categorical"] = {"n": 8000, "n_levels_binned": 0,
                                      "levels": [{"value": "X", "count": 4000},
                                                 {"value": "Y", "count": 4000}]}
    v["relationships"]["crosstabs"][0].update(
        {"n": 8000, "rows": 4, "cols": 2,
         "cells": [0, 0, 1500, 1500, 2221, 2220, 279, 280], "cells_suppressed": 0})
    _write("report_a3a_released_categories_pass.json", v)

    # --- Missing-partner cells (VC § CPS Usage Notes, "Missing-partner cells") ------
    def _a3_mp(core, extc, extr, hidden=(), gate=None, collapsed=False, other=False):
        """The a3 base with entry 0 replaced by a cross-tab whose pair columns carry
        missing values, built from the full extended table.

        `core` is the R x C table of pair-complete counts, `extc[i]` the records in row
        category i whose second pair column (cat_b) is missing, and `extr[j]` the records
        missing cat_a in column category j; the both-missing corner takes the rest of
        row_count 9000. Each pair column's level counts are its full margin (core line
        sum plus its missing-partner count) and its nonmissing_n their sum, so the report
        is one a profiler could have written; the entry's n is the core total. `hidden`
        is the set of (i, j) core cells released as null (every cell when `collapsed`).

        Rows and columns follow the released categories in the profilers' grid order —
        kept labels in code-point order, then `__OTHER__` (`other=True` makes the last
        row the pooled bucket) — because the missing-partner scan maps each level count
        onto its grid line by that order. (The `_a3_grid` fixtures need no such care:
        on complete data the scan adds no edge and never reads a label.) `gate` raises the
        declared threshold, with every numeric block's n lifted to 9000 so the full
        summaries stay in their band, as the leak variant above does.
        """
        rows, cols = len(core), len(core[0])
        alab = sorted(["OTHERLBL", "ZQXRARELABEL"] + [f"a{i}" for i in range(2, rows)])[:rows]
        if other:
            alab[-1] = "__OTHER__"
        blab = sorted(["X", "Y"] + [f"b{j}" for j in range(2, cols)])[:cols]
        ta = [sum(core[i]) + extc[i] for i in range(rows)]
        tb = [sum(core[i][j] for i in range(rows)) + extr[j] for j in range(cols)]
        n = sum(map(sum, core))
        assert 9000 - n - sum(extc) - sum(extr) >= 0, "the both-missing corner went negative"
        v = json.loads(json.dumps(a3))
        for pos, labs, tot in ((2, alab, ta), (3, blab, tb)):
            nn = sum(tot)
            # Released level order: count descending, ties by label (the profilers').
            order = sorted(range(len(labs)), key=lambda k: (-tot[k], labs[k]))
            v["columns"][pos].update(nonmissing_n=nn, missing_rate=round((9000 - nn) / 9000, 6),
                                     n_distinct=len(labs) + (1 if "__OTHER__" in labs else 0),
                                     uniqueness_ratio=round(len(labs) / nn, 6))
            v["columns"][pos]["categorical"] = {
                "n": nn, "n_levels_binned": 2 if "__OTHER__" in labs else 0,
                "levels": [{"value": labs[k], "count": tot[k]} for k in order]}
        cells = [None if (collapsed or (i, j) in hidden) else core[i][j]
                 for i in range(rows) for j in range(cols)]
        v["relationships"]["crosstabs"][0] = {
            "pair": ["cat_a", "cat_b"], "n": n, "available": True, "rows": rows, "cols": cols,
            "cells": cells, "cells_suppressed": sum(1 for c in cells if c is None)}
        if collapsed:
            v["relationships"]["crosstabs"][0]["collapsed"] = True
        if gate is not None:
            v["settings"]["suppression_threshold"] = gate
            for c in v["columns"]:
                if c["role"] == "numeric":
                    c["numeric"]["n"] = 9000
        return v

    # Row-side leak at gate 1000: every core cell is visible, and 673 records of row 0
    # (OTHERLBL) lack cat_b. Row 0's released count minus its visible row sum pins that
    # count; 673 is the planted token, so the FAIL must name row index 0 and print no
    # count. Row 1 pins 0 (a known zero, not a finding).
    _write("report_a3a_mp_row_fail.json",
           _a3_mp([[2279, 1607], [2221, 2220]], [673, 0], [0, 0], gate=1000))
    # Column-side mirror: 673 records of column 1 (Y) lack cat_a; cat_b is complete, so
    # the missing-partner column's residual is 0 and the finding is on the column side.
    _write("report_a3a_mp_col_fail.json",
           _a3_mp([[2280, 2279], [2220, 1548]], [0, 0], [0, 673], gate=1000))
    # Baseline: a one-row grid. Its missing-partner column cell is pinned by the released
    # n and missing counts alone, whatever the grid shows — exempt, PASS.
    _write("report_a3a_mp_one_row_exempt.json",
           _a3_mp([[4500, 3827]], [673], [0, 0], gate=1000))
    # Baseline mirror: a one-column grid's missing-partner row cell — exempt, PASS.
    _write("report_a3a_mp_one_col_exempt.json",
           _a3_mp([[4441], [3886]], [0, 0], [673], gate=1000))
    # Only cat_a has missing values, so the missing-partner column's residual is 0: a
    # line of known zeros that adds no edge. The missing-partner row cells are pinned
    # (every core cell is visible) at 500 and 500, both above the gate — PASS.
    _write("report_a3a_mp_zero_residual_line.json",
           _a3_mp([[1779, 1780], [2221, 2220]], [0, 0], [500, 500]))
    # A collapsed entry (every core cell null) over a pair with 3 records of row 1 lacking
    # cat_b: with the whole grid hidden the graph is the baseline itself — PASS.
    _write("report_a3a_mp_collapsed.json",
           _a3_mp([[2279, 2280], [2221, 2217]], [0, 3], [0, 0], collapsed=True))
    # Genuine shape: kept levels in code-point order, then __OTHER__ last; the four
    # sub-threshold core cells (1-4) hidden as one 2x2 cycle; rows 0-1 carry 3 and 4
    # records lacking cat_b. Those two missing-partner cells close a cycle with the hidden
    # cells (missing column - row 0 - column 0 - row 1 - missing column), so neither is
    # pinned; row 2's pins 0 — PASS. This is what a profiler's extended rule leaves.
    _write("report_a3a_mp_genuine_protected.json",
           _a3_mp([[1, 2, 1500], [3, 4, 1500], [2221, 2220, 500]], [3, 4, 0], [0, 0, 0],
                  hidden={(0, 0), (0, 1), (1, 0), (1, 1)}, other=True))
    # The entry's pair-complete n (9000) above cat_b's nonmissing_n (8997): impossible,
    # and the scan does not run on that entry.
    v = json.loads(json.dumps(a3))
    v["columns"][3].update(nonmissing_n=8997, missing_rate=round(3 / 9000, 6),
                           uniqueness_ratio=round(2 / 8997, 6))
    v["columns"][3]["categorical"] = {"n": 8997, "n_levels_binned": 0,
                                      "levels": [{"value": "X", "count": 4500},
                                                 {"value": "Y", "count": 4497}]}
    _write("report_a3a_n_above_nonmissing.json", v)
    # A pair column with missing values whose block repeats a label (row 2's `a2` relabelled
    # OTHERLBL): the levels no longer map onto grid rows, so the scan lacks the totals it
    # needs ([NOT VERIFIED]) beside rule 4's repeated-label [FAIL].
    v = _a3_mp([[1779, 1780], [1000, 1000], [1221, 1220]], [0, 0, 0], [500, 500])
    for lv in v["columns"][2]["categorical"]["levels"]:
        if lv["value"] == "a2":
            lv["value"] = "OTHERLBL"
    _write("report_a3a_mp_dup_label_pair_column.json", v)

    # Text-built strict-parse variants: json.dumps cannot emit a duplicate key
    # or a NaN literal, so each is the base text with one textual splice.
    a3_text = json.dumps(a3, indent=2)
    ctl_text = json.dumps(control, indent=2)
    for name, src, old, new in (
            # Duplicate key, number first then string ({"n": 40, "n": "Realname"}).
            ("report_a3a_dup_key_number_first.json", a3_text, '"mean": ',
             '"n": "Realname", "mean": '),
            # Duplicate key, string first then number — the order jsonlite's `[[` and
            # Python's default dict would each resolve to a different value.
            ("report_a3a_dup_key_string_first.json", a3_text, '"n": 40,',
             '"n": "Realname", "n": 40,'),
            ("report_a3a_nan_literal.json", a3_text, '"missing_rate": 0.0,',
             '"missing_rate": NaN,'),
            # CPS-GEN: a duplicate key nested inside a level entry.
            ("report_p2_dup_key_nested.json", ctl_text, '"value": "A",',
             '"value": "Realname Q.", "value": "A",'),
            # Number-token length: a token of 65 characters is a parse error, one of
            # 64 parses as before. Both spell the declared value (5 columns / 40 rows)
            # with trailing fraction zeros, so the value itself is unchanged and only
            # the token length decides the outcome.
            ("report_a3a_number_token_65.json", a3_text, '"column_count": 5\n',
             '"column_count": 5.%s\n' % ("0" * 63)),
            ("report_a3a_number_token_64.json", a3_text, '"column_count": 5\n',
             '"column_count": 5.%s\n' % ("0" * 62)),
            ("report_control_number_token_65.json", ctl_text, '"row_count": 40,',
             '"row_count": 40.%s,' % ("0" * 62))):
        assert src.count(old) >= 1, (name, old)
        p = out / name
        p.write_text(src.replace(old, new, 1), encoding="utf-8")
        paths[name.replace(".json", "")] = str(p)

    # Strict-parse refusals decided on the file's bytes or escape sequences, before
    # either parser runs (the two parsers would otherwise read them differently).
    # Each splice lands inside a string so the rest of the file stays valid JSON.
    for name, src, old, new in (
            # Escaped NUL: jsonlite cuts the string there, Python keeps it.
            ("report_a3a_escaped_nul.json", a3_text, '"OTHERLBL"', '"OTHERLBL\\u0000x"'),
            # Unpaired high surrogate escape: jsonlite rewrites it, Python keeps it.
            ("report_a3a_lone_surrogate.json", a3_text, '"ZQXRARELABEL"',
             '"ZQXRARELABEL\\ud800"')):
        assert src.count(old) >= 1, (name, old)
        p = out / name
        p.write_text(src.replace(old, new, 1), encoding="utf-8")
        paths[name.replace(".json", "")] = str(p)
    # A leading UTF-8 byte-order mark (jsonlite accepts it, json.loads refuses it).
    _write_bytes("report_a3a_bom.json", b"\xef\xbb\xbf" + a3_text.encode("utf-8"))
    _write_bytes("report_control_bom.json", b"\xef\xbb\xbf" + ctl_text.encode("utf-8"))
    # A raw NUL byte inside the dataset_name string (R's text reader stops at it).
    assert a3_text.count('"cps_fixture_a3a_base"') == 1
    _write_bytes("report_a3a_raw_nul.json",
                 a3_text.replace('"cps_fixture_a3a_base"', '"cps_fixture\x00a3a_base"')
                 .encode("utf-8"))

    # --- CPS-GEN null-evidence and tier artifacts ----------------------------
    v = json.loads(json.dumps(control))
    v["relationships"]["pearson"]["matrix"][0][1] = None
    v["relationships"]["pearson"]["matrix"][1][0] = None
    _write("report_g2_null_correlation.json", v)
    v = json.loads(json.dumps(control))
    v["columns"][2]["categorical"]["levels"][1]["count"] = None
    _write("report_g3_null_level_count.json", v)
    # Grids released but empty — zero comparisons is never a PASS.
    v = json.loads(json.dumps(control))
    for c in v["columns"]:
        if c["role"] == "numeric":
            c["numeric"]["percentiles"] = {}
    _write("report_e1_empty_grids.json", v)
    # A tier-3 report (settings.tier 3) that carries no pearson block.
    v = json.loads(json.dumps(control))
    v["dataset_name"] = "cps_fixture_tier3_nopearson"
    del v["relationships"]["pearson"]
    _write("report_tier3_nopearson.json", v)
    # A numeric column written as String in the synthetic frame.
    str_pq = out / "synthetic_numa_string.parquet"
    df.with_columns(pl.col("num_a").cast(pl.String)).write_parquet(str_pq)
    paths["synthetic_numa_string"] = str(str_pq)

    # --- CPS-GEN review-cycle-3 artifacts (canonical text form, types, pooling) ---
    # Integer-coded categorical `code` (labels "1"/"2", as both profilers write an
    # integer level) plus a numeric identifier `member_id` numbered 1..40 and stored as
    # a whole-number Float64. Under the one canonical text form 1.0 is "1", so the
    # synthetic identifier collides with a released label in BOTH languages.
    syn_ids = df.with_columns(
        pl.Series("code", [1] * 20 + [2] * 20, dtype=pl.Int64),
        pl.Series("member_id", [float(i) for i in range(1, n_rows + 1)], dtype=pl.Float64))
    ids_pq = out / "synthetic_float_ids.parquet"
    syn_ids.write_parquet(ids_pq)
    paths["synthetic_float_ids"] = str(ids_pq)
    v = json.loads(json.dumps(control))
    v["dataset"]["column_count"] = 6
    v["columns"].append({"name": "code", "dtype": "integer", "role": "categorical",
                         "missing_rate": 0.0, "nonmissing_n": n_rows, "n_distinct": 2,
                         "uniqueness_ratio": 0.05, "is_identifier": False,
                         "categorical": {"n": n_rows, "n_levels_binned": 0,
                                         "levels": [{"value": "1", "count": 20},
                                                    {"value": "2", "count": 20}]}})
    v["columns"].append({"name": "member_id", "dtype": "integer", "role": "identifier",
                         "missing_rate": 0.0, "nonmissing_n": n_rows, "n_distinct": n_rows,
                         "uniqueness_ratio": 1.0, "is_identifier": True,
                         "string_structure": {"n": n_rows, "length_min": 1, "length_mean": 1.8,
                                              "length_max": 2,
                                              "pattern_flags": {"email": False, "phone": False,
                                                                "date": False, "id": True,
                                                                "free_text": False}}})
    _write("report_gen_float_ids.json", v)

    # Boolean categorical: the Python profiler writes a bool level as "True"/"False",
    # the R profiler as "TRUE"/"FALSE", and both declare dtype string. A synthetic
    # Boolean column must match either spelling through the canonical text form.
    syn_bool = df.with_columns(pl.Series("flag", [True] * 20 + [False] * 20,
                                         dtype=pl.Boolean))
    bool_pq = out / "synthetic_bool.parquet"
    syn_bool.write_parquet(bool_pq)
    paths["synthetic_bool"] = str(bool_pq)
    for suffix, t_lbl, f_lbl in (("py", "True", "False"), ("r", "TRUE", "FALSE")):
        v = json.loads(json.dumps(control))
        v["dataset"]["column_count"] = 5
        v["columns"].append({"name": "flag", "dtype": "string", "role": "categorical",
                             "missing_rate": 0.0, "nonmissing_n": n_rows, "n_distinct": 2,
                             "uniqueness_ratio": 0.05, "is_identifier": False,
                             "categorical": {"n": n_rows, "n_levels_binned": 0,
                                             "levels": [{"value": t_lbl, "count": 20},
                                                        {"value": f_lbl, "count": 20}]}})
        _write(f"report_gen_bool_{suffix}.json", v)
        # The generation recipes write a boolean categorical as its string labels, so
        # the synthetic column is a String holding the profiler's own spelling — the
        # shape column_set_and_dtypes accepts against the declared dtype `string`.
        text_pq = out / f"synthetic_bool_text_{suffix}.parquet"
        df.with_columns(pl.Series("flag", [t_lbl] * 20 + [f_lbl] * 20,
                                  dtype=pl.String)).write_parquet(text_pq)
        paths[f"synthetic_bool_text_{suffix}"] = str(text_pq)

    # A Duration column where the report declares the categorical cat_b: outside the
    # text-comparable types, so every level check is a named FAIL, never an escape.
    dur_pq = out / "synthetic_catb_duration.parquet"
    df.with_columns(pl.Series("cat_b", [i * 1_000_000 for i in range(n_rows)],
                              dtype=pl.Int64).cast(pl.Duration("us"))).write_parquet(dur_pq)
    paths["synthetic_catb_duration"] = str(dur_pq)

    # Fully pooled categorical: `pool` has 1 non-missing value of 200 (below the gate),
    # so the profiler releases `levels: []` with `n_levels_binned: 1`. A 200-row frame
    # keeps the all-null synthetic's null-rate drift (0.005) inside the 0.01 band.
    # Tier 2 (no relationships), shaped like report_tier2_genuine; cat_a carries the
    # planted labels.
    n_pool = 200
    pool_cat = ["ZQXRARELABEL"] * 120 + ["OTHERLBL"] * 80
    pool_report = json.loads(json.dumps(tier2g))
    pool_report["dataset_name"] = "cps_fixture_gen_pooled"
    pool_report["dataset"] = {"row_count": n_pool, "column_count": 2}
    pool_report["columns"] = [
        {"name": "cat_a", "dtype": "string", "role": "categorical", "missing_rate": 0.0,
         "nonmissing_n": n_pool, "n_distinct": 2, "uniqueness_ratio": 0.01,
         "is_identifier": False,
         "categorical": {"n": n_pool, "n_levels_binned": 0,
                         "levels": [{"value": "ZQXRARELABEL", "count": 120},
                                    {"value": "OTHERLBL", "count": 80}]}},
        {"name": "pool", "dtype": "string", "role": "categorical", "missing_rate": 0.995,
         "nonmissing_n": 1, "n_distinct": 1, "uniqueness_ratio": 1.0,
         "is_identifier": False,
         "categorical": {"n": 1, "n_levels_binned": 1, "levels": []}}]
    _write("report_gen_pooled.json", pool_report)
    for name, pool_vals in (("synthetic_pooled_other", ["__OTHER__"] + [None] * (n_pool - 1)),
                            ("synthetic_pooled_null", [None] * n_pool)):
        p = out / f"{name}.parquet"
        pl.DataFrame({"cat_a": pl.Series(pool_cat, dtype=pl.String),
                      "pool": pl.Series(pool_vals, dtype=pl.String)}).write_parquet(p)
        paths[name] = str(p)

    # A synthetic parquet storing the same column name twice. Polars cannot write one,
    # so pyarrow (the dependency CPS-GEN's own raw-schema read already needs) does.
    import pyarrow as pa
    import pyarrow.parquet as pq
    dup_pq = out / "synthetic_dup_names.parquet"
    pq.write_table(pa.Table.from_arrays(
        [pa.array(num_a), pa.array(num_a), pa.array(num_b), pa.array(cat_a), pa.array(cat_b)],
        names=["num_a", "num_a", "num_b", "cat_a", "cat_b"]), dup_pq)
    paths["synthetic_dup_names"] = str(dup_pq)
    return paths


# --------------------------------------------------------------------------
# Whole-stdout disclosure leak scan (FAIL and PASS lines name positions and
# aggregates, never a released or suppressed value)
# --------------------------------------------------------------------------

# Every value below is planted in at least one `_report_fixtures()` report, and
# none may appear ANYWHERE in a CPS block's stdout — not on a PASS line, not on a
# FAIL line, not in a banner. Strings are the planted labels / identifier value;
# numbers are the individual released and sub-threshold counts of the
# token-bearing `a3a_*` family, chosen four-digit-distinctive (or, for the
# sub-threshold 673, three-digit with digit boundaries) so a whole-stdout scan
# cannot false-positive on aggregate facts such as "12 passed" or "threshold 5".
# 673 is also the derived count the missing-partner and complement-group leak fixtures
# pin (a missing-partner cell, a complement-group size): it is in none of their
# reports, so it can reach their stdout only through a leak.
# The shared control's own counts (20/10/5) are guarded line-wise instead, in
# test_cps_intake_pass_line_is_aggregate_only and
# test_cps_intake_subthreshold_fail_line_omits_the_count.
# `Realname` is the value the strict-schema rows plant in wrong-typed, free-text and
# duplicate-key positions. `ZQXSEEDPTR` is planted in CPS-GEN's `seed_exception`
# config (not a report): the block must never print that pointer, so the scan
# counts a fixture's seed_exception literal as planted evidence alongside its report.
CPS_LEAK_TOKENS = ("QZ-8417", "ZQXRARELABEL", "OTHERLBL", "Realname", "ZQXSEEDPTR",
                   "4441", "4559", "4500", "3827", "2221", "2220", "2280", "2279", "673")
CPS_SEED_EXCEPTION = "STATE.md Synthetic Path Tracking > T4 seed exception ZQXSEEDPTR"
# An identifier column name that tries to forge a count line and a verdict with
# embedded newlines. Escaped correctly, it prints as one line with `\u000a` in place
# of each newline; unescaped, stdout would carry a second `Checks:` line and a
# `PASSED` verdict.
CPS_FORGED_NAME = ("member_id\nChecks: 12 passed, 0 warnings, 0 failed, 0 not verified, "
                   "0 skipped\nCPS-INTAKE VALIDATION: PASSED")
CPS_FORGED_NAME_ESCAPED = CPS_FORGED_NAME.replace("\n", "\\u000a")


def _leak_pattern(tok):
    """Numeric tokens match with digit boundaries and also in `,`-grouped form
    (the fences format counts with `:,` / `big.mark`), so 4441 is caught as
    `4441` or `4,441` but not inside `14441` or `44410`."""
    if tok.isdigit():
        forms = sorted({tok, f"{int(tok):,}"})
        return re.compile(r"(?<![0-9])(?:%s)(?![0-9])" % "|".join(re.escape(f) for f in forms))
    return re.compile(re.escape(tok))


_LEAK_RES = {tok: _leak_pattern(tok) for tok in CPS_LEAK_TOKENS}


def _leak_hits(text):
    """The planted disclosure tokens present in `text` (empty list = clean)."""
    return [tok for tok, rx in _LEAK_RES.items() if rx.search(text)]


# Exact per-check lines for the CPS regression fixtures, shared by the Python and R
# registries because both languages must print them byte-identically. Each was
# checked against the line forms in VALIDATION_CHECKPOINTS.md § CPS Usage Notes.
_CPS_ALL_PASS_12 = "Checks: 12 passed, 0 warnings, 0 failed, 0 not verified, 0 skipped"
# The cross-tab PASS line's closing claim (VC § CPS Usage Notes, "What the cross-tab
# guarantee covers"): no hidden cell is recoverable from the released row and column
# totals — and nothing broader.
CPS_CT_PASS_TAIL = "no hidden cell recoverable from the row and column totals"
CPS_Q3A_PASS_LINE = ("[PASS] crosstab_schema_and_suppression: 1 entries, 4 cells examined, "
                     "4 hidden as null, 1 fully collapsed, " + CPS_CT_PASS_TAIL)
CPS_Q3B_FAIL_LINE = ("[FAIL] crosstab_schema_and_suppression: entry 1 is marked collapsed "
                     "but still releases visible cells")
CPS_Q4_ID_FAIL_LINE = ("[FAIL] identifier_columns_value_free: column 'member_id' carries "
                       "non-structural key 'example'")
CPS_Q4_VALUE_KEY_FAIL_LINE = ("[FAIL] no_raw_value_shaped_fields: value-shaped key 'example' "
                              "at report.columns[4].string_structure.example")
# Rule 4's per-role allow-list: `notes` is also outside the numeric block's
# allow-list, so the walker's rule-2 hit is followed by one more finding.
CPS_Q4E_FAIL_LINE = ("[FAIL] no_raw_value_shaped_fields: report.columns[0].numeric.notes is a "
                     "12-element scalar list, longer than the declared cap 9 (+1 more)")
CPS_INTAKE_Q5_FAIL_LINE = (
    "[FAIL] not_applicable: unrecognized key 'no_such_check' (declarable keys: "
    "report_version, required_top_level_keys, row_count_positive, percentiles_monotone, "
    "category_counts_le_rowcount, missing_rate_in_unit_interval, "
    "correlation_matrix_wellformed, embedded_validation_complete)")
CPS_GEN_Q5_FAIL_LINE = (
    "[FAIL] not_applicable: unrecognized key 'no_such' (declarable keys: row_count_matches, "
    "column_set_and_dtypes, numeric_marginals_within_tolerance, "
    "categorical_proportions_within_tolerance, correlations_within_tolerance, "
    "missingness_within_tolerance)")
CPS_Q1_FAIL_LINE = ("[FAIL] correlations_within_tolerance: released pearson block declares "
                    "3 columns but carries an 2x2 matrix")
CPS_Q2_FAIL_LINE = ("[FAIL] numeric_marginals_within_tolerance: column 'num_a' percentile "
                    "grid carries unrecognized key 'median'")
# JSON-node counts of the null-bearing `a3a_*` reports. Python counts a JSON null
# as a node; the R walker must reach the same totals, which is the executable
# form of "a NULL push never desynchronises the node stack". The PASS line also
# carries rule 4's and rule 5's evidence: the non-identifier column records (the
# identifier belongs to identifier_columns_value_free) — 4, or 5 where the report
# adds cat_c — and 14 subtree records (dataset, settings, generator, relationships,
# validation, the pearson and spearman records, and the 7 validation.checks entries;
# cross-tab entries are owned by crosstab_schema_and_suppression and are not queued).
# Each total equals an independent count of every JSON value in the report file,
# root and nulls included.
CPS_A3_NODE_LINES = {
    key: ("[PASS] no_raw_value_shaped_fields: %d JSON nodes walked, 0 value-shaped keys, "
          "longest scalar list 4 <= declared cap 9, %d column records within the per-role "
          "key allow-list, 14 subtree records within the spec key allow-lists and "
          "vocabularies" % (n, recs))
    for key, n, recs in (("q3a", 218, 4), ("q3b", 251, 5), ("q4b", 210, 4), ("base", 217, 4))}
# The control's disclosure-sweep PASS line: effective gate = max(declared 5,
# approved 5). Allowed facts only — blocks, cells, thresholds.
CPS_CONTROL_SWEEP_PASS_LINE = (
    "[PASS] no_released_count_below_threshold: 3 of 3 declared blocks scanned "
    "(2 categorical + 1 cross-tab), 11 visible cells examined, all >= effective "
    "threshold 5 (declared 5, approved 5)")
CPS_PARSE_ERROR = "report did not parse as JSON (parser message withheld: it can quote report content)"
_CPS_INTAKE_CHECKS = ("report_version", "required_top_level_keys", "row_count_positive",
                      "percentiles_monotone", "category_counts_le_rowcount",
                      "missing_rate_in_unit_interval", "correlation_matrix_wellformed",
                      "no_released_count_below_threshold", "embedded_validation_complete",
                      "no_raw_value_shaped_fields", "identifier_columns_value_free",
                      "crosstab_schema_and_suppression")
_CPS_GEN_REPORT_CHECKS = ("row_count_matches", "column_set_and_dtypes",
                          "numeric_marginals_within_tolerance",
                          "categorical_proportions_within_tolerance",
                          "suppressed_categories_absent", "correlations_within_tolerance",
                          "synthetic_levels_within_released_levels",
                          "identifier_columns_value_free", "missingness_within_tolerance")
# Strict parsing: every report-reading check names the parse failure.
CPS_INTAKE_PARSE_LINES = [f"[NOT VERIFIED] {c}: {CPS_PARSE_ERROR}" for c in _CPS_INTAKE_CHECKS]
CPS_GEN_PARSE_LINES = [f"[NOT VERIFIED] {c}: {CPS_PARSE_ERROR}" for c in _CPS_GEN_REPORT_CHECKS]
_C11 = "Checks: 11 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped"
_C10F2 = "Checks: 10 passed, 0 warnings, 2 failed, 0 not verified, 0 skipped"
_G9F1 = "Checks: 9 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped"
_G9NV1 = "Checks: 9 passed, 0 warnings, 0 failed, 1 not verified, 0 skipped"
_CPS_INTAKE_ALL_NV = "Checks: 0 passed, 0 warnings, 0 failed, 12 not verified, 0 skipped"
_CPS_GEN_SEED_PASS = ("[PASS] seed_recorded: generation seed 20260915 present in the script "
                      "config and printed to the log")
_CPS_GEN_READ_ERROR = ("the synthetic parquet did not read (reader message withheld: the two "
                       "readers word it differently)")
CPS_GEN_READ_LINES = [f"[NOT VERIFIED] {c}: {_CPS_GEN_READ_ERROR}" for c in _CPS_GEN_REPORT_CHECKS]
_CPS_GEN_UNTEXTABLE = ("holds values outside the text-comparable types (string, categorical, "
                       "integer below 2^53, float, boolean)")
# The boolean rows assert the undeclared outcome. Both profilers declare a bool
# column dtype `string`, and column_set_and_dtypes requires a text column for that
# (VC § CPS Usage Notes, "Synthetic column types"), so a synthetic Boolean `flag`
# FAILS the dtype check — while the three level checks still compare it through the
# canonical text form and PASS. 7 = cat_a's 3 + cat_b's 2 + flag's 2 level
# proportions / distinct levels.
_CPS_BOOL_LEVEL_PASS_LINES = [
    "[PASS] categorical_proportions_within_tolerance: 3 columns, 7 level proportions, "
    "all within +/-0.02",
    "[PASS] suppressed_categories_absent: 3 categorical columns examined, 1 pooled buckets "
    "preserved, 0 levels added",
    "[PASS] synthetic_levels_within_released_levels: 3 columns, 7 distinct synthetic "
    "levels, all inside the released sets"]
CPS_BOOL_LINES = (
    ["[FAIL] column_set_and_dtypes: column 'flag' is not a string column, the report "
     "declares string"]
    + _CPS_BOOL_LEVEL_PASS_LINES
    + ["Checks: 9 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped"])
# The companion rows: the synthetic `flag` written as the profiler's string labels (the
# generation recipes' shape) matches the declared `string` dtype, so all ten checks PASS.
CPS_BOOL_TEXT_LINES = (
    ["[PASS] column_set_and_dtypes: 5 declared columns, names and dtypes all matched"]
    + _CPS_BOOL_LEVEL_PASS_LINES
    + ["Checks: 10 passed, 0 warnings, 0 failed, 0 not verified, 0 skipped"])
_G8S2 = "Checks: 8 passed, 0 warnings, 0 failed, 0 not verified, 2 skipped"

_VERDICT_LINE_RE = re.compile(r"^[A-Z][A-Z0-9 -]* VALIDATION: (PASSED|PASSED WITH WARNINGS|FAILED)$")


def _assert_line_expectations(tc, name, spec, out):
    """Whole-line assertions shared by the Python and R fixture runners.

    `contains` is a substring test, which a longer or doubled line still
    satisfies; the regression fixtures need the stronger forms:
      lines           each string is an entire stdout line (right-stripped)
      absent_prefixes no stdout line starts with any of these
      line_counts     [(prefix, n)] exactly n lines start with prefix
      verdict         the block printed exactly one verdict line, and it is this
    """
    # Split on "\n" only: str.splitlines() would also break at \r, \x0b, \x0c, \x1c-\x1e,
    # \x85, U+2028 and U+2029, so a raw control character that escaped the fences'
    # \uXXXX table could pass for a line boundary here and hide a forged line.
    out_lines = [ln.rstrip() for ln in out.split("\n")]
    for line in spec.get("lines", []):
        tc.assertIn(line, out_lines, f"{name}: missing whole line {line!r}\n{out}")
    for prefix in spec.get("absent_prefixes", []):
        hits = [ln for ln in out_lines if ln.startswith(prefix)]
        tc.assertEqual(hits, [], f"{name}: expected no line starting {prefix!r}\n{out}")
    for prefix, expected in spec.get("line_counts", []):
        got = sum(1 for ln in out_lines if ln.startswith(prefix))
        tc.assertEqual(got, expected, f"{name}: expected {expected} line(s) starting "
                                      f"{prefix!r}, got {got}\n{out}")
    if spec.get("verdict") is not None:
        verdicts = [ln for ln in out_lines if _VERDICT_LINE_RE.match(ln)]
        tc.assertEqual(verdicts, [spec["verdict"]],
                       f"{name}: expected the sole verdict {spec['verdict']!r}\n{out}")


# --------------------------------------------------------------------------
# CPS regression cases (CPS-INTAKE and CPS-GEN, both languages)
# --------------------------------------------------------------------------
# One table drives both registries: `_py_fixtures` registers each row under its
# own name, R_FIXTURES under `r_<name>`, so a Python expectation can never be
# edited without its R mirror. Every expected line was observed on the live fences
# in both languages and checked against the line forms in VALIDATION_CHECKPOINTS.md
# § CPS Usage Notes. Row names keep short case tags (q3a, i1a, e11, g2, t4a, ...)
# so earlier test ids stay stable; each row's comment or `doc` says what it guards.
#
# Row keys: block, report (a `_report_fixtures()` key), synthetic (CPS-GEN only),
# na (the not_applicable mapping), the optional config overrides tier (default 3),
# exp (CPS-INTAKE `expected_threshold`, default CPS_APPROVED_THRESHOLD; None means
# unset), seed (CPS-GEN, default 20260915; None means unset) and seed_exception
# (CPS-GEN, default unset), doc (the generated test's docstring), plus the
# `_assert_line_expectations` keys. A FAILED verdict implies the block halts with
# its own halt message (Python `raises`, R `stop()`); any other exception fails
# the fixture, which is how "no traceback / no R error" is enforced for every row.
_CPS_CASE_EXPECTATION_KEYS = ("lines", "absent_prefixes", "line_counts", "verdict")
_INTAKE_FAILED = "CPS-INTAKE VALIDATION: FAILED"
_GEN_FAILED = "CPS-GEN VALIDATION: FAILED"
_INTAKE_PASSED = "CPS-INTAKE VALIDATION: PASSED"
_GEN_PASSED = "CPS-GEN VALIDATION: PASSED"
_CPS_DEFAULT_SEED = 20260915

CPS_REGRESSION_CASES = {
    # An all-null collapsed entry is the legitimate whole-table hide.
    "cps_intake_q3a_collapsed_all_null": dict(
        block="CPS-INTAKE", report="report_a3a_q3a_collapsed_allnull",
        lines=[CPS_Q3A_PASS_LINE, CPS_A3_NODE_LINES["q3a"], _CPS_ALL_PASS_12],
        verdict="CPS-INTAKE VALIDATION: PASSED"),
    # A collapsed flag over a grid that still shows a cell is a bypass. The entry sits
    # at index 1 on a pair of its own, so its finding is the report's only one.
    "cps_intake_q3b_collapsed_visible": dict(
        block="CPS-INTAKE", report="report_a3a_q3b_collapsed_visible",
        lines=[CPS_Q3B_FAIL_LINE, CPS_A3_NODE_LINES["q3b"],
               "Checks: 11 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped"],
        line_counts=[("[FAIL]", 1)],
        verdict=_INTAKE_FAILED),
    # `string_structure.example` fails BOTH identifier checks, key name only.
    "cps_intake_q4a_identifier_example": dict(
        block="CPS-INTAKE", report="report_a3a_q4a_identifier_example",
        lines=[CPS_Q4_ID_FAIL_LINE, CPS_Q4_VALUE_KEY_FAIL_LINE,
               "Checks: 10 passed, 0 warnings, 2 failed, 0 not verified, 0 skipped"],
        verdict=_INTAKE_FAILED),
    # The spec's withheld identifier shape is allowed and counted.
    "cps_intake_q4b_identifier_withheld": dict(
        block="CPS-INTAKE", report="report_a3a_q4b_identifier_withheld",
        lines=["[PASS] identifier_columns_value_free: 1 identifier columns examined, "
               "structure keys only (allow-list), 1 withheld",
               CPS_A3_NODE_LINES["q4b"], _CPS_ALL_PASS_12],
        verdict="CPS-INTAKE VALIDATION: PASSED"),
    # Allow-listed identifier keys only — the control for the `example` row above.
    "cps_intake_q4c_identifier_allowlist_control": dict(
        block="CPS-INTAKE", report="report_a3a_base",
        lines=["[PASS] identifier_columns_value_free: 1 identifier columns examined, "
               "structure keys only (allow-list), 0 withheld",
               CPS_A3_NODE_LINES["base"], _CPS_ALL_PASS_12],
        verdict="CPS-INTAKE VALIDATION: PASSED"),
    # JSON nulls in a sibling subtree must not shift the reported path.
    "cps_intake_q4d_null_sibling_path": dict(
        block="CPS-INTAKE", report="report_a3a_q4d_null_sibling",
        lines=[CPS_Q4_VALUE_KEY_FAIL_LINE, CPS_Q4_ID_FAIL_LINE,
               "[PASS] crosstab_schema_and_suppression: 2 entries, 8 cells examined, "
               "4 hidden as null, 1 fully collapsed, " + CPS_CT_PASS_TAIL,
               "Checks: 10 passed, 0 warnings, 2 failed, 0 not verified, 0 skipped"],
        verdict=_INTAKE_FAILED),
    # A long scalar list holding a null is still flagged by rule (2).
    "cps_intake_q4e_null_in_long_list": dict(
        block="CPS-INTAKE", report="report_a3a_q4e_null_in_long_list",
        lines=[CPS_Q4E_FAIL_LINE,
               "Checks: 11 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped"],
        verdict=_INTAKE_FAILED),
    # An unrecognized not_applicable key is one [FAIL], exactly once, and nothing else
    # moves.
    "cps_intake_q5_unrecognized_key": dict(
        block="CPS-INTAKE", report="report_a3a_base", na={"no_such_check": "typo'd key"},
        lines=["Checks: 12 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped"],
        line_counts=[(CPS_INTAKE_Q5_FAIL_LINE, 1), ("[FAIL] not_applicable:", 1)],
        verdict=_INTAKE_FAILED),
    # A declarable key with a whitespace reason is NOT VERIFIED and the check does
    # not run (its PASS line must be absent).
    "cps_intake_q6_empty_reason_declarable": dict(
        block="CPS-INTAKE", report="report_a3a_base", na={"percentiles_monotone": "   "},
        lines=["[NOT VERIFIED] percentiles_monotone: declared not_applicable with an "
               "empty reason",
               "Checks: 11 passed, 0 warnings, 0 failed, 1 not verified, 0 skipped"],
        absent_prefixes=["[PASS] percentiles_monotone:", "[SKIPPED] percentiles_monotone:"],
        verdict=_INTAKE_FAILED),
    # A non-declarable key keeps its [FAIL] however empty its reason, and the check
    # still runs (exactly one PASS line for it, no NOT VERIFIED).
    "cps_intake_q6b_empty_reason_non_declarable": dict(
        block="CPS-INTAKE", report="report_a3a_base",
        na={"no_released_count_below_threshold": ""},
        lines=["[FAIL] no_released_count_below_threshold: non-declarable check declared "
               "not_applicable under key 'no_released_count_below_threshold'",
               "Checks: 12 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped"],
        line_counts=[("[PASS] no_released_count_below_threshold: ", 1)],
        absent_prefixes=["[NOT VERIFIED] no_released_count_below_threshold:"],
        verdict=_INTAKE_FAILED),
    # Leak variant: a sub-threshold count is named by position only.
    "cps_intake_leak_subthreshold": dict(
        block="CPS-INTAKE", report="report_a3a_leak_subthreshold",
        lines=["[FAIL] no_released_count_below_threshold: categorical block 'cat_b' "
               "level index 2 carries a visible count below the gate",
               "Checks: 11 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped"],
        verdict=_INTAKE_FAILED),
    # Three declared columns over a 2x2 matrix — a named FAIL, not a crash.
    "cps_gen_q1_matrix_dimension_mismatch": dict(
        block="CPS-GEN", report="report_q1_matrix_short", synthetic="synthetic_threecols",
        lines=[CPS_Q1_FAIL_LINE,
               "Checks: 9 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped"],
        verdict=_GEN_FAILED),
    # An unrecognized percentile key is named — not a crash (Python), and not a
    # misattributed NA-quantile [NOT VERIFIED] (R).
    "cps_gen_q2_unrecognized_percentile_key": dict(
        block="CPS-GEN", report="report_q2_median_key", synthetic="synthetic_control",
        lines=[CPS_Q2_FAIL_LINE,
               "Checks: 9 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped"],
        absent_prefixes=["[NOT VERIFIED] numeric_marginals_within_tolerance:"],
        verdict=_GEN_FAILED),
    "cps_gen_q5_unrecognized_key": dict(
        block="CPS-GEN", report="report_control", synthetic="synthetic_control",
        na={"no_such": "x"},
        lines=["Checks: 10 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped"],
        line_counts=[(CPS_GEN_Q5_FAIL_LINE, 1), ("[FAIL] not_applicable:", 1)],
        verdict=_GEN_FAILED),
    "cps_gen_q6_empty_reason_declarable": dict(
        block="CPS-GEN", report="report_control", synthetic="synthetic_control",
        na={"missingness_within_tolerance": "  "},
        lines=["[NOT VERIFIED] missingness_within_tolerance: declared not_applicable "
               "with an empty reason",
               "Checks: 9 passed, 0 warnings, 0 failed, 1 not verified, 0 skipped"],
        absent_prefixes=["[PASS] missingness_within_tolerance:",
                         "[SKIPPED] missingness_within_tolerance:"],
        verdict=_GEN_FAILED),
    "cps_gen_q6b_empty_reason_non_declarable": dict(
        block="CPS-GEN", report="report_control", synthetic="synthetic_control",
        na={"seed_recorded": ""},
        lines=["[FAIL] seed_recorded: non-declarable check declared not_applicable "
               "under key 'seed_recorded'",
               "[PASS] seed_recorded: generation seed 20260915 present in the script "
               "config and printed to the log",
               "Checks: 10 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped"],
        absent_prefixes=["[NOT VERIFIED] seed_recorded:"],
        verdict=_GEN_FAILED),

    # ---- Strict schema, typing and free-text channels, CPS-INTAKE ---------------
    "cps_intake_i1a_sample_capitalised": dict(
        block="CPS-INTAKE", report="report_a3a_i1a_sample_capitalised",
        doc="Rule 1 is case-insensitive, so a capitalised `Sample` list is a dump (and "
            "rule 4 flags the same key: `(+1 more)`).",
        lines=["[FAIL] no_raw_value_shaped_fields: report.columns[2].Sample is a list under "
               "a value-shaped key name (+1 more)", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_i1b_top_values": dict(
        block="CPS-INTAKE", report="report_a3a_i1b_top_values",
        doc="`top_values` is named by no deny-list; rule 4's per-role "
            "allow-list catches it, naming the key only.",
        lines=["[FAIL] no_raw_value_shaped_fields: column 'cat_b' carries non-structural "
               "key 'top_values'", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_i4_401_digit_percentile": dict(
        block="CPS-INTAKE", report="report_a3a_i4_401_digit_percentile",
        doc="A 401-digit percentile is exact in Python and Inf "
            "in jsonlite; a number token longer than 64 characters is now a parse error in "
            "both languages, so every check is NOT VERIFIED on the parse failure.",
        lines=CPS_INTAKE_PARSE_LINES + [_CPS_INTAKE_ALL_NV],
        line_counts=[("[FAIL]", 0)],
        verdict=_INTAKE_FAILED),
    "cps_intake_s1_string_under_numeric_key": dict(
        block="CPS-INTAKE", report="report_a3a_s1_string_n",
        doc="A string under the allow-listed numeric key `n` is a released "
            "value wearing a structural key's name; the support gate, which needs a "
            "whole-number n to gate the block's shape on, fails on the same field.",
        lines=["[FAIL] no_released_count_below_threshold: numeric block 'num_a' carries no "
               "non-negative whole-number n and nonmissing_n to gate its shape on",
               "[FAIL] no_raw_value_shaped_fields: column 'num_a' carries a non-numeric 'n'",
               _C10F2],
        verdict=_INTAKE_FAILED),
    "cps_intake_e11_duplicate_key_number_first": dict(
        block="CPS-INTAKE", report="report_a3a_dup_key_number_first",
        doc="A duplicate object key (number, then string) is a parse error; "
            "Python's dict and jsonlite's `[[` used to judge two different values.",
        lines=CPS_INTAKE_PARSE_LINES
              + ["Checks: 0 passed, 0 warnings, 0 failed, 12 not verified, 0 skipped"],
        verdict=_INTAKE_FAILED),
    "cps_intake_e11b_duplicate_key_string_first": dict(
        block="CPS-INTAKE", report="report_a3a_dup_key_string_first",
        doc="The same duplicate key in the other order is the same outcome.",
        lines=CPS_INTAKE_PARSE_LINES
              + ["Checks: 0 passed, 0 warnings, 0 failed, 12 not verified, 0 skipped"],
        verdict=_INTAKE_FAILED),
    "cps_intake_nan_literal": dict(
        block="CPS-INTAKE", report="report_a3a_nan_literal",
        doc="A bare NaN literal is a parse error in both languages (Python's "
            "json.loads would otherwise admit it).",
        lines=CPS_INTAKE_PARSE_LINES
              + ["Checks: 0 passed, 0 warnings, 0 failed, 12 not verified, 0 skipped"],
        verdict=_INTAKE_FAILED),
    "cps_intake_e4_negative_crosstab_dims": dict(
        block="CPS-INTAKE", report="report_a3a_e4_negative_dims",
        doc="Rows/cols are fields the check validates, so -2 is a FAIL, "
            "not missing evidence.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry cat_a x cat_b has no positive "
               "integer rows/cols with a cells array — the grid cannot be reshaped", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_dtype_outside_vocabulary": dict(
        block="CPS-INTAKE", report="report_a3a_bad_dtype",
        doc="Free-text paths: a column dtype outside the spec vocabulary FAILS "
            "and the value is never echoed.",
        lines=["[FAIL] no_raw_value_shaped_fields: column 'num_a' carries a 'dtype' outside "
               "the spec vocabulary", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_settings_unknown_key": dict(
        block="CPS-INTAKE", report="report_a3a_settings_unknown_key",
        doc="Free-text paths: `settings` is held to the spec key allow-list.",
        lines=["[FAIL] no_raw_value_shaped_fields: settings carries non-structural key "
               "'comment'", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_free_text_check_reason": dict(
        block="CPS-INTAKE", report="report_a3a_free_text_reason",
        doc="Free-text paths: a PASS entry's reason must be "
            "`candidate_fields_checked`; free text there is a leak path.",
        lines=["[FAIL] no_raw_value_shaped_fields: validation.checks[0].reason is outside "
               "the spec vocabulary", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_i6_declared_below_approved": dict(
        block="CPS-INTAKE", report="report_a3a_i6_declared_below_approved",
        doc="A report declaring threshold 1 against an approved 5 FAILS — "
            "the gate is never the report's word alone.",
        lines=["[FAIL] no_released_count_below_threshold: report declares threshold 1, "
               "below the approved threshold 5", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_expected_threshold_unset": dict(
        block="CPS-INTAKE", report="report_a3a_base", exp=None,
        doc="With expected_threshold unset the non-declarable sweep cannot run, so "
            "it is NOT VERIFIED and the block FAILS.",
        lines=["[NOT VERIFIED] no_released_count_below_threshold: expected_threshold not "
               "configured",
               "Checks: 11 passed, 0 warnings, 0 failed, 1 not verified, 0 skipped"],
        verdict=_INTAKE_FAILED),
    "cps_intake_declared_above_approved": dict(
        block="CPS-INTAKE", report="report_a3a_declared_above_approved",
        doc="Declared 10 over approved 5 is honoured at the stricter value — "
            "effective threshold max(10, 5).",
        lines=["[PASS] no_released_count_below_threshold: 3 of 3 declared blocks scanned "
               "(2 categorical + 1 cross-tab), 8 visible cells examined, all >= effective "
               "threshold 10 (declared 10, approved 5)", _CPS_ALL_PASS_12],
        verdict=_INTAKE_PASSED),
    # Cross-tab complementary-suppression defects (non-declarable check): lone cells.
    "cps_intake_lone_hidden_cell_row": dict(
        block="CPS-INTAKE", report="report_a3a_lone_cell_row",
        doc="One hidden cell alone in a row is recoverable by differencing the "
            "row total; the FAIL names the pair and the row index only. The grid's other "
            "hidden cells form a cycle, so the lone cell is the only finding.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry cat_a x cat_b leaves a lone "
               "hidden cell in row index 0 — recoverable by differencing", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_lone_hidden_cell_column": dict(
        block="CPS-INTAKE", report="report_a3a_lone_cell_col",
        doc="The same defect along a column, again the grid's only finding.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry cat_a x cat_b leaves a lone "
               "hidden cell in column index 0 — recoverable by differencing", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_lone_row_with_bridge": dict(
        block="CPS-INTAKE", report="report_a3a_lone_cell_row_with_bridge",
        doc="Bridge rule: the earlier lone-cell row grid also hides a recoverable cell "
            "whose row and column each hold two or more nulls; the lone-cell line comes "
            "first and the bridge counts into `(+1 more)`.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry cat_a x cat_b leaves a lone "
               "hidden cell in row index 0 — recoverable by differencing (+1 more)", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_lone_column_with_bridge": dict(
        block="CPS-INTAKE", report="report_a3a_lone_cell_col_with_bridge",
        doc="Bridge rule: the earlier lone-cell column grid, likewise lone cell first and "
            "the bridge in `(+1 more)`.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry cat_a x cat_b leaves a lone "
               "hidden cell in column index 0 — recoverable by differencing (+1 more)", _C11],
        verdict=_INTAKE_FAILED),
    # Bridge-cell suppression (non-declarable check): a hidden cell whose edge in the
    # row/column graph of hidden cells lies on no cycle is pinned by the released totals.
    "cps_intake_bridge_between_two_cycles": dict(
        block="CPS-INTAKE", report="report_a3a_bridge_one",
        doc="Bridge rule: two hidden 2x2 cycles joined by one hidden cell. No row or column "
            "holds a lone hidden cell, yet the joining cell is exactly recoverable; the FAIL "
            "names its row and column index only.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry cat_a x cat_b leaves hidden "
               "cell at row index 2, column index 1 recoverable from the released totals",
               _C11],
        absent_prefixes=["[FAIL] crosstab_schema_and_suppression: entry cat_a x cat_b leaves a "
                         "lone"],
        verdict=_INTAKE_FAILED),
    "cps_intake_two_bridges": dict(
        block="CPS-INTAKE", report="report_a3a_bridge_two",
        doc="Bridge rule: two cycles joined through a path of two hidden cells — both are "
            "bridges, reported in row-major order, the second in `(+1 more)`.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry cat_a x cat_b leaves hidden "
               "cell at row index 1, column index 4 recoverable from the released totals "
               "(+1 more)", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_hidden_2x2_cycle": dict(
        block="CPS-INTAKE", report="report_a3a_hidden_2x2_cycle",
        doc="Bridge rule control: a hidden 2x2 block is a cycle, so no hidden cell is "
            "exactly recoverable — PASS.",
        lines=["[PASS] crosstab_schema_and_suppression: 1 entries, 9 cells examined, 4 hidden "
               "as null, 0 fully collapsed, " + CPS_CT_PASS_TAIL, _CPS_ALL_PASS_12],
        line_counts=[("[FAIL]", 0)],
        verdict=_INTAKE_PASSED),
    "cps_intake_six_cycle_3x3": dict(
        block="CPS-INTAKE", report="report_a3a_six_cycle_3x3",
        doc="Bridge rule control: six hidden cells forming one 6-cycle on a 3x3 grid (every "
            "row and column holds two) — no bridge, PASS.",
        lines=["[PASS] crosstab_schema_and_suppression: 1 entries, 9 cells examined, 6 hidden "
               "as null, 0 fully collapsed, " + CPS_CT_PASS_TAIL, _CPS_ALL_PASS_12],
        line_counts=[("[FAIL]", 0)],
        verdict=_INTAKE_PASSED),
    "cps_intake_cycle_with_structural_zeros": dict(
        block="CPS-INTAKE", report="report_a3a_cycle_with_structural_zeros",
        doc="Bridge rule control: a hidden 2x2 cycle beside two visible structural zeros. A "
            "visible 0 is not a hidden cell, so it is neither an edge nor a finding — PASS.",
        lines=["[PASS] crosstab_schema_and_suppression: 1 entries, 9 cells examined, 4 hidden "
               "as null, 0 fully collapsed, " + CPS_CT_PASS_TAIL, _CPS_ALL_PASS_12],
        line_counts=[("[FAIL]", 0)],
        verdict=_INTAKE_PASSED),
    "cps_intake_genuine_old_profiler_bridge": dict(
        block="CPS-INTAKE", report="report_genuine_old_profiler_bridge",
        doc="Bridge rule: a genuine tier-3 report from an earlier Python profiler, "
            "whose 4x4 cross-tab joins two hidden 2x2 cycles through hidden (1,2). The old "
            "lone-cell rule passed it; it now FAILS on that cell.",
        lines=["[SKIPPED] percentiles_monotone: report declares 0 numeric columns at tier 3 "
               "(0 grids, 0 percentiles)",
               "[FAIL] crosstab_schema_and_suppression: entry cat_a x cat_b leaves hidden "
               "cell at row index 1, column index 2 recoverable from the released totals",
               "Checks: 10 passed, 0 warnings, 1 failed, 0 not verified, 1 skipped"],
        verdict=_INTAKE_FAILED),
    "cps_intake_hidden_cell_coded_zero": dict(
        block="CPS-INTAKE", report="report_a3a_hidden_coded_zero",
        doc="A visible 0 is a legitimate structural zero, so the old "
            "'codes a hidden cell as 0' rule is gone; a hidden cell mis-coded as 0 is "
            "still caught because cells_suppressed (1) disagrees with the nulls in the "
            "grid (0) — and the grid that then 'hides no cell' fails the residual too.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry cat_a x cat_b reports a "
               "cells_suppressed that disagrees with the 0 nulls in the grid (+1 more)", _C11],
        absent_prefixes=["[FAIL] crosstab_schema_and_suppression: entry cat_a x cat_b codes"],
        verdict=_INTAKE_FAILED),
    "cps_intake_cells_suppressed_disagrees": dict(
        block="CPS-INTAKE", report="report_a3a_suppressed_count_disagrees",
        doc="`cells_suppressed` must equal the null cells actually in the grid.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry cat_a x cat_b reports a "
               "cells_suppressed that disagrees with the 0 nulls in the grid", _C11],
        verdict=_INTAKE_FAILED),

    # ---- Disclosure arithmetic, release scope and escaping, CPS-INTAKE ----------
    # Disclosure: level counts, differencing residuals, cross-tab cells, scope.
    "cps_intake_negative_level_count": dict(
        block="CPS-INTAKE", report="report_a3a_negative_level_count",
        doc="A negative level count is a sub-threshold count wearing a sign; the "
            "FAIL names the block and level index, never the count.",
        lines=["[FAIL] no_released_count_below_threshold: categorical block 'cat_a' level "
               "index 0 carries a visible count below the gate", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_zero_count_level": dict(
        block="CPS-INTAKE", report="report_a3a_zero_count_level",
        doc="A level listed at 0 still names a category, so it breaches the gate.",
        lines=["[FAIL] no_released_count_below_threshold: categorical block 'cat_b' level "
               "index 2 carries a visible count below the gate", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_level_sum_residual": dict(
        block="CPS-INTAKE", report="report_a3a_level_sum_residual",
        doc="Levels summing to n - 2 release a hidden count of 2 by subtraction.",
        lines=["[FAIL] no_released_count_below_threshold: categorical block 'cat_b' level "
               "counts do not sum to its n", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_categorical_n_vs_nonmissing": dict(
        block="CPS-INTAKE", report="report_a3a_cat_n_mismatch",
        doc="A categorical block n below its column's nonmissing_n releases the "
            "difference by subtraction even when the levels sum to n.",
        lines=["[FAIL] no_released_count_below_threshold: categorical block 'cat_b' n does "
               "not equal its column's nonmissing_n", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_crosstab_residual": dict(
        block="CPS-INTAKE", report="report_a3a_crosstab_residual",
        doc="A cross-tab entry that hides no cell must sum to its n exactly.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry cat_a x cat_b hides no cell but "
               "its visible cells do not sum to its n", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_negative_crosstab_cell": dict(
        block="CPS-INTAKE", report="report_a3a_negative_cell",
        doc="A negative cross-tab cell breaches the gate, named by cell index.",
        lines=["[FAIL] no_released_count_below_threshold: cross-tab block cat_a x cat_b cell "
               "index 3 carries a visible count below the gate", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_structural_zero_cell": dict(
        block="CPS-INTAKE", report="report_a3a_structural_zero",
        doc="A visible cross-tab 0 is a legitimate structural zero — PASS.",
        lines=["[PASS] crosstab_schema_and_suppression: 1 entries, 4 cells examined, 0 hidden "
               "as null, 0 fully collapsed, " + CPS_CT_PASS_TAIL, _CPS_ALL_PASS_12],
        line_counts=[("[FAIL]", 0)],
        verdict=_INTAKE_PASSED),
    "cps_intake_report_tier_above_approved": dict(
        block="CPS-INTAKE", report="report_a3a_base", tier=2,
        doc="A tier-3 report against an approved tier 2 is a release beyond the "
            "approved scope; never raise the config tier to match.",
        lines=["[SKIPPED] correlation_matrix_wellformed: tier 2 releases no correlation "
               "matrices (2 matrices declared)",
               "[FAIL] no_released_count_below_threshold: report declares tier 3, above the "
               "approved tier 2",
               "Checks: 10 passed, 0 warnings, 1 failed, 0 not verified, 1 skipped"],
        verdict=_INTAKE_FAILED),
    "cps_intake_relationships_below_tier3": dict(
        block="CPS-INTAKE", report="report_tier2_nopearson", tier=2,
        doc="A tier-2 report that still carries a relationships block (here a "
            "spearman record and a cross-tab) FAILS; the skip line counts the released "
            "matrix instead of waving it through.",
        lines=["[SKIPPED] correlation_matrix_wellformed: tier 2 releases no correlation "
               "matrices (1 matrices declared)",
               "[FAIL] no_released_count_below_threshold: the report releases a relationships "
               "block below tier 3 (approved tier 2, declared tier 2)",
               "Checks: 10 passed, 0 warnings, 1 failed, 0 not verified, 1 skipped"],
        verdict=_INTAKE_FAILED),
    # Free-text channels.
    "cps_intake_level_value_not_string": dict(
        block="CPS-INTAKE", report="report_a3a_level_value_list",
        doc="A level label must be a JSON string; a list there is a value dump "
            "wearing the label's name.",
        lines=["[FAIL] no_raw_value_shaped_fields: column 'cat_a' level index 0 carries a "
               "non-string 'value'", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_toplevel_key_with_declared_keys_check": dict(
        block="CPS-INTAKE", report="report_a3a_toplevel_extra",
        na={"required_top_level_keys": "reviewed manually"},
        doc="Declaring required_top_level_keys away does not open a channel — rule 6 "
            "of the non-declarable no_raw_value_shaped_fields still FAILS the unknown key.",
        lines=["[SKIPPED] required_top_level_keys: reviewed manually",
               "[FAIL] no_raw_value_shaped_fields: report carries non-structural key 'notes'",
               "Checks: 10 passed, 0 warnings, 1 failed, 0 not verified, 1 skipped"],
        verdict=_INTAKE_FAILED),
    "cps_intake_dataset_name_outside_format": dict(
        block="CPS-INTAKE", report="report_a3a_dataset_name_freetext",
        doc="`dataset_name` is held to the profilers' slug format; the value is "
            "never echoed.",
        lines=["[FAIL] no_raw_value_shaped_fields: report.dataset_name is outside the spec "
               "format", _C11],
        verdict=_INTAKE_FAILED),
    # Strict parsing: refused before either parser runs.
    "cps_intake_utf8_bom": dict(
        block="CPS-INTAKE", report="report_a3a_bom",
        doc="A leading UTF-8 BOM is a parse error in both languages (jsonlite would "
            "accept it with a warning).",
        lines=CPS_INTAKE_PARSE_LINES + [_CPS_INTAKE_ALL_NV],
        verdict=_INTAKE_FAILED),
    "cps_intake_raw_nul_byte": dict(
        block="CPS-INTAKE", report="report_a3a_raw_nul",
        doc="A raw NUL byte is a parse error in both languages.",
        lines=CPS_INTAKE_PARSE_LINES + [_CPS_INTAKE_ALL_NV],
        verdict=_INTAKE_FAILED),
    "cps_intake_lone_surrogate_escape": dict(
        block="CPS-INTAKE", report="report_a3a_lone_surrogate",
        doc="An unpaired \\ud800 escape is a parse error in both languages "
            "(jsonlite rewrites it to '?', Python keeps it).",
        lines=CPS_INTAKE_PARSE_LINES + [_CPS_INTAKE_ALL_NV],
        verdict=_INTAKE_FAILED),
    "cps_intake_escaped_nul": dict(
        block="CPS-INTAKE", report="report_a3a_escaped_nul",
        doc="An escaped \\u0000 is a parse error in both languages (jsonlite "
            "truncates the string there, Python keeps it).",
        lines=CPS_INTAKE_PARSE_LINES + [_CPS_INTAKE_ALL_NV],
        verdict=_INTAKE_FAILED),
    # Escaping: report-derived names print through the \\uXXXX table.
    "cps_intake_newline_in_column_name": dict(
        block="CPS-INTAKE", report="report_a3a_newline_name",
        doc="A column name with embedded newlines cannot forge a count line or a "
            "verdict — it prints as one line with \\u000a escapes, and stdout (split on "
            "\\n only) carries exactly one Checks: line and one verdict line (the "
            "`verdict` key asserts the sole verdict-shaped line is FAILED).",
        lines=["[FAIL] identifier_columns_value_free: column '%s' carries non-structural "
               "key 'extra'" % CPS_FORGED_NAME_ESCAPED, _C11],
        line_counts=[("Checks:", 1)],
        verdict=_INTAKE_FAILED),
    "cps_intake_nonascii_column_name": dict(
        block="CPS-INTAKE", report="report_a3a_nonascii_name",
        doc="A non-ASCII column name (raw UTF-8 in the file) prints \\uXXXX-escaped "
            "identically in both languages.",
        lines=["[FAIL] identifier_columns_value_free: column 'caf\\u00e9_id' carries "
               "non-structural key 'extra'", _C11],
        verdict=_INTAKE_FAILED),

    # ---- Number tokens, tier-1 records, support gate and dtype, CPS-INTAKE ------
    # Number-token length: the 64-character cap, both sides of the edge.
    "cps_intake_number_token_65_chars": dict(
        block="CPS-INTAKE", report="report_a3a_number_token_65",
        doc="A 65-character number token (5 written with 63 fraction zeros) is a "
            "parse error in both languages, although its value is the base report's.",
        lines=CPS_INTAKE_PARSE_LINES + [_CPS_INTAKE_ALL_NV],
        verdict=_INTAKE_FAILED),
    "cps_intake_number_token_64_chars": dict(
        block="CPS-INTAKE", report="report_a3a_number_token_64",
        doc="Edge case: the same value written as a 64-character token parses as before — "
            "the base report's unchanged PASS.",
        lines=["[PASS] row_count_positive: dataset.row_count = 9,000 over 5 declared columns",
               _CPS_ALL_PASS_12],
        line_counts=[("[FAIL]", 0), ("[NOT VERIFIED]", 0)],
        verdict=_INTAKE_PASSED),
    # Tier-1 identifier records.
    "cps_intake_t1_identifier_with_t2_keys": dict(
        block="CPS-INTAKE", report="report_t1_identifier_t2_keys", tier=1,
        doc="At tier 1 an identifier record is held to {name, dtype}; one carrying "
            "the tier-2 metadata keys FAILS identifier_columns_value_free, naming the first "
            "key only and counting the rest.",
        lines=["[SKIPPED] percentiles_monotone: report declares 0 numeric columns at tier 1 "
               "(0 grids, 0 percentiles)",
               "[SKIPPED] category_counts_le_rowcount: report declares 0 categorical columns "
               "at tier 1 (0 levels)",
               "[SKIPPED] correlation_matrix_wellformed: tier 1 releases no correlation "
               "matrices (0 matrices declared)",
               "[FAIL] identifier_columns_value_free: column 'member_id' carries "
               "non-structural key 'is_identifier' (+5 more)",
               "Checks: 8 passed, 0 warnings, 1 failed, 0 not verified, 3 skipped"],
        line_counts=[("[FAIL]", 1)],
        verdict=_INTAKE_FAILED),
    # Support gate: one breach per band, each one step below its band's edge.
    "cps_intake_gate_full_summary_below_cutoff": dict(
        block="CPS-INTAKE", report="report_a3a_gate_full_below_cutoff",
        doc="A full numeric summary at n = 9, below the full-summary cutoff "
            "f = max(5, 10), is a support-gate breach naming the column and shape only.",
        lines=["[FAIL] no_released_count_below_threshold: numeric block 'num_a' shape 'full' "
               "does not match the support band of its n", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_gate_small_n_below_gate": dict(
        block="CPS-INTAKE", report="report_a3a_gate_small_n_below_gate",
        doc="A small_n block at n = 4, below the gate k = 5.",
        lines=["[FAIL] no_released_count_below_threshold: numeric block 'num_a' shape "
               "'small_n' does not match the support band of its n", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_gate_constant_below_gate": dict(
        block="CPS-INTAKE", report="report_a3a_gate_constant_below_gate",
        doc="A constant block at n = 4, below the gate k = 5.",
        lines=["[FAIL] no_released_count_below_threshold: numeric block 'num_a' shape "
               "'constant' does not match the support band of its n", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_gate_string_structure_below_gate": dict(
        block="CPS-INTAKE", report="report_a3a_gate_string_structure_below_gate",
        doc="A full identifier string_structure at n = 4 (= its nonmissing_n), "
            "below the gate k = 5, should have been withheld.",
        lines=["[FAIL] no_released_count_below_threshold: string_structure block 'member_id' "
               "shape 'full' does not match the support band of its n", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_gate_named_below_cutoff": dict(
        block="CPS-INTAKE", report="report_a3a_gate_named_below_cutoff",
        doc="An available named (OLS) entry at n = 9, below the full-summary cutoff.",
        lines=["[FAIL] no_released_count_below_threshold: named entry num_a ~ num_b is "
               "available although its n is below the full-summary cutoff", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_gate_cramers_v_below_gate": dict(
        block="CPS-INTAKE", report="report_a3a_gate_cramers_v_below_gate",
        doc="An available Cramer's V entry at n = 4, below the gate.",
        lines=["[FAIL] no_released_count_below_threshold: cramers_v entry cat_a x cat_b is "
               "available although its n is below the gate", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_gate_band_edges_pass": dict(
        block="CPS-INTAKE", report="report_a3a_gate_edges",
        doc="Band edges: a full summary at n = f, small_n and a full string_structure at "
            "n = k, named at n = f with complement groups of 0 (outcome) and k "
            "(predictor), and Cramer's V at n = k all sit in their bands — PASS.",
        lines=["[PASS] no_released_count_below_threshold: 3 of 3 declared blocks scanned "
               "(2 categorical + 1 cross-tab), 8 visible cells examined, all >= effective "
               "threshold 5 (declared 5, approved 5)", _CPS_ALL_PASS_12],
        line_counts=[("[FAIL]", 0)],
        verdict=_INTAKE_PASSED),
    # Complement groups of an available named entry (support gate, non-declarable):
    # g = end's numeric n - entry n must be 0 or >= the gate k = 5.
    "cps_intake_complement_group_outcome_below_gate": dict(
        block="CPS-INTAKE", report="report_a3a_cg_outcome_below_gate",
        doc="The outcome's complement group is k - 1 = 4 records: the released mean and "
            "the fitted line together give their summed value, so the entry may not be "
            "available. The FAIL names the entry and the end, never the group size; the "
            "outcome is tested first and one finding is reported per entry.",
        lines=["[FAIL] no_released_count_below_threshold: named entry num_a ~ num_b is "
               "available although the complement group of its outcome is below the gate",
               _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_complement_group_predictor_below_gate": dict(
        block="CPS-INTAKE", report="report_a3a_cg_predictor_below_gate",
        doc="Outcome group 0, predictor group k - 1 = 4: the same finding on the predictor.",
        lines=["[FAIL] no_released_count_below_threshold: named entry num_a ~ num_b is "
               "available although the complement group of its predictor is below the gate",
               _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_complement_group_at_gate_pass": dict(
        block="CPS-INTAKE", report="report_a3a_cg_at_gate",
        doc="Both complement groups exactly k = 5 records — on the band edge, PASS.",
        lines=["[PASS] no_released_count_below_threshold: 3 of 3 declared blocks scanned "
               "(2 categorical + 1 cross-tab), 8 visible cells examined, all >= effective "
               "threshold 5 (declared 5, approved 5)", _CPS_ALL_PASS_12],
        line_counts=[("[FAIL]", 0)],
        verdict=_INTAKE_PASSED),
    "cps_intake_complement_group_zero_pass": dict(
        block="CPS-INTAKE", report="report_a3a_cg_zero",
        doc="Both complement groups empty (every record of either column is pair-complete) "
            "— PASS.",
        lines=["[PASS] no_released_count_below_threshold: 3 of 3 declared blocks scanned "
               "(2 categorical + 1 cross-tab), 8 visible cells examined, all >= effective "
               "threshold 5 (declared 5, approved 5)", _CPS_ALL_PASS_12],
        line_counts=[("[FAIL]", 0)],
        verdict=_INTAKE_PASSED),
    "cps_intake_complement_group_no_numeric_n": dict(
        block="CPS-INTAKE", report="report_a3a_cg_outcome_no_numeric_n",
        doc="A named entry whose outcome column carries no numeric block has no "
            "whole-number numeric n to gate its complement group on — a sweep breach.",
        lines=["[FAIL] no_released_count_below_threshold: named entry cat_a ~ num_b has no "
               "whole-number numeric n for its outcome to gate the complement group on",
               _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_complement_group_leak": dict(
        block="CPS-INTAKE", report="report_a3a_cg_leak_gate_1000",
        doc="Leak variant at gate 1000: the outcome's complement group is the planted 673 "
            "records. The size is derived, never released, and reaches no line.",
        lines=["[FAIL] no_released_count_below_threshold: named entry num_a ~ num_b is "
               "available although the complement group of its outcome is below the gate",
               _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_named_reason_small_complement_group": dict(
        block="CPS-INTAKE", report="report_a3a_cg_reason_small_complement_group",
        doc="The profilers withhold such an entry with reason small_complement_group; the "
            "reason is in the spec vocabulary, so the withheld entry PASSES intake.",
        lines=[_CPS_ALL_PASS_12],
        line_counts=[("[FAIL]", 0), ("[NOT VERIFIED]", 0)],
        verdict=_INTAKE_PASSED),
    # Categorical columns are string columns.
    "cps_intake_categorical_dtype_integer": dict(
        block="CPS-INTAKE", report="report_a3a_categorical_dtype_integer",
        doc="Both profilers give the categorical role only to dtype string, so a "
            "categorical record declaring integer FAILS — the dtype is not echoed.",
        lines=["[FAIL] no_raw_value_shaped_fields: column 'cat_b' declares role 'categorical' "
               "with a dtype other than 'string'", _C11],
        verdict=_INTAKE_FAILED),

    # ---- One cross-tab per unordered pair, on the released categories ---------
    # (crosstab_schema_and_suppression, non-declarable). Line forms verbatim from VC
    # § CPS Usage Notes, "One cross-tab per unordered pair of two distinct columns"
    # and "Released categories". Every FAIL row's report is otherwise sound, so the
    # rule under test is the cross-tab check's only finding (asserted by the exact
    # line, which would carry `(+N more)` otherwise).
    "cps_intake_crosstab_self_pair": dict(
        block="CPS-INTAKE", report="report_a3a_self_pair",
        doc="A cross-tab whose pair names one column twice is no cross-tab at all; the "
            "FAIL names the entry by index (here 1, after a clean entry 0), never a column.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry index 1 names one column twice "
               "in its 'pair'", _C11],
        line_counts=[("[FAIL]", 1)],
        verdict=_INTAKE_FAILED),
    "cps_intake_crosstab_self_pair_twice": dict(
        block="CPS-INTAKE", report="report_a3a_self_pair_twice",
        doc="The same self-pair at entry indices 1 and 2: each is a self-pair and entry 2 "
            "also repeats entry 1's pair, so three findings — the first printed, two counted.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry index 1 names one column twice "
               "in its 'pair' (+2 more)", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_crosstab_repeat_pair_same_order": dict(
        block="CPS-INTAKE", report="report_a3a_repeat_pair_same_order",
        doc="Two entries on one pair in the same order: the later entry is reported and "
            "names the first. Two cross-tabs of one pair can hide different cells, and "
            "their union can recover cells neither hides alone.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry index 1 repeats the pair of "
               "entry index 0", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_crosstab_repeat_pair_swapped": dict(
        block="CPS-INTAKE", report="report_a3a_repeat_pair_swapped",
        doc="The same pair in swapped order ([cat_b, cat_a] after [cat_a, cat_b]) is the "
            "same unordered pair, so the same finding.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry index 1 repeats the pair of "
               "entry index 0", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_crosstab_repeat_pair_unavailable_first": dict(
        block="CPS-INTAKE", report="report_a3a_repeat_pair_unavailable_first",
        doc="The rule holds whatever `available` says: an unavailable entry on the pair at "
            "index 0 is the first entry on it, so the available grid at index 1 repeats it.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry index 1 repeats the pair of "
               "entry index 0", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_crosstab_rows_unequal": dict(
        block="CPS-INTAKE", report="report_a3a_crosstab_rows_unequal",
        doc="An available grid with a row for a level cat_a's block does not release (3 "
            "rows against 2 released levels): a pooled level's own row could be subtracted "
            "from the released __OTHER__ count. No count is printed.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry cat_a x cat_b has rows unequal "
               "to the released level count of pair position 0", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_crosstab_cols_unequal": dict(
        block="CPS-INTAKE", report="report_a3a_crosstab_cols_unequal",
        doc="The same along the columns: 3 cols against cat_b's 2 released levels.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry cat_a x cat_b has cols unequal "
               "to the released level count of pair position 1", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_crosstab_pair_numeric_column": dict(
        block="CPS-INTAKE", report="report_a3a_crosstab_pair_numeric",
        doc="Pair position 0 is a numeric column, which has no released categories to put "
            "a grid on; position 1 matches, so position 0 is the only finding.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry num_a x cat_b pair position 0 "
               "is not a categorical column with a released levels array", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_crosstab_pair_identifier_column": dict(
        block="CPS-INTAKE", report="report_a3a_crosstab_pair_identifier",
        doc="Pair position 1 is the identifier column — the same finding at position 1.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry cat_a x member_id pair "
               "position 1 is not a categorical column with a released levels array", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_crosstab_pair_column_without_block": dict(
        block="CPS-INTAKE", report="report_a3a_crosstab_pair_without_block",
        doc="A pair column that declares role categorical but carries no categorical block "
            "releases no levels to count, so an available grid over it FAILS — beside the "
            "incomplete-sweep FAIL and the category-count NOT VERIFIED the missing block "
            "earns on its own.",
        lines=["[NOT VERIFIED] category_counts_le_rowcount: column 'cat_b' declares role "
               "categorical but has no categorical block",
               "[FAIL] no_released_count_below_threshold: scanned 2 of 3 declared blocks — "
               "the sweep is incomplete",
               "[FAIL] crosstab_schema_and_suppression: entry cat_a x cat_b pair position 1 "
               "is not a categorical column with a released levels array",
               "Checks: 9 passed, 0 warnings, 2 failed, 1 not verified, 0 skipped"],
        verdict=_INTAKE_FAILED),
    "cps_intake_crosstab_pair_levels_not_array": dict(
        block="CPS-INTAKE", report="report_a3a_crosstab_pair_levels_null",
        doc="A categorical block whose `levels` is not an array (here null) releases no "
            "level count either — the same cross-tab finding.",
        lines=["[NOT VERIFIED] category_counts_le_rowcount: column 'cat_b' has a categorical "
               "block with no levels array",
               "[FAIL] no_released_count_below_threshold: scanned 2 of 3 declared blocks — "
               "the sweep is incomplete",
               "[FAIL] crosstab_schema_and_suppression: entry cat_a x cat_b pair position 1 "
               "is not a categorical column with a released levels array",
               "Checks: 9 passed, 0 warnings, 2 failed, 1 not verified, 0 skipped"],
        verdict=_INTAKE_FAILED),
    "cps_intake_crosstab_released_categories_pass": dict(
        block="CPS-INTAKE", report="report_a3a_released_categories_pass",
        doc="Genuine shape: a 4 x 2 grid on the released categories — three kept levels in "
            "code-point order, one pooled __OTHER__ row, and a row of structural zeros for "
            "a level with no pair-complete rows — matches both level counts and PASSES.",
        lines=["[PASS] crosstab_schema_and_suppression: 1 entries, 8 cells examined, 0 hidden "
               "as null, 0 fully collapsed, " + CPS_CT_PASS_TAIL, _CPS_ALL_PASS_12],
        line_counts=[("[FAIL]", 0), ("[NOT VERIFIED]", 0)],
        verdict=_INTAKE_PASSED),

    # ---- Repeated level labels and missing-partner cells, CPS-INTAKE -------------
    # Line forms verbatim from VC § CPS Usage Notes, "Distinct labels" and
    # "Missing-partner cells". Missing-partner fixtures come from `_a3_mp`, whose grids
    # follow the released categories in code-point order.
    "cps_intake_dup_level_label": dict(
        block="CPS-INTAKE", report="report_a3a_dup_level_label",
        doc="A categorical block that releases one label twice splits a category's count "
            "in a way nothing reconciles; the FAIL names the later level and the first one "
            "carrying the label, never the label.",
        lines=["[FAIL] no_raw_value_shaped_fields: column 'cat_c' level index 2 repeats the "
               "'value' of level index 1", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_dup_level_other": dict(
        block="CPS-INTAKE", report="report_a3a_dup_level_other",
        doc="The pooled bucket `__OTHER__` written twice is the same finding.",
        lines=["[FAIL] no_raw_value_shaped_fields: column 'cat_c' level index 2 repeats the "
               "'value' of level index 1", _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_missing_partner_row_index": dict(
        block="CPS-INTAKE", report="report_a3a_mp_row_fail",
        doc="A fully visible row leaves 'released level count minus row sum' on the wire: "
            "the planted 673 records of row 0 lacking cat_b, below gate 1000. The FAIL "
            "names the row index only; the count reaches no line.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry cat_a x cat_b leaves the "
               "missing-partner cell at row index 0 recoverable from the released totals",
               _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_missing_partner_column_index": dict(
        block="CPS-INTAKE", report="report_a3a_mp_col_fail",
        doc="The column-side mirror: 673 records of column 1 lacking cat_a, pinned by the "
            "column total; the missing-partner column's residual is 0, so no row-side edge "
            "exists and the position counts columns from 0.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry cat_a x cat_b leaves the "
               "missing-partner cell at column index 1 recoverable from the released totals",
               _C11],
        verdict=_INTAKE_FAILED),
    "cps_intake_missing_partner_one_row_exempt": dict(
        block="CPS-INTAKE", report="report_a3a_mp_one_row_exempt",
        doc="Baseline: a one-row grid's missing-partner column cell (673, below gate 1000) "
            "is pinned by the released n and missing counts alone, whatever the grid shows, "
            "so it is exempt — PASS.",
        lines=["[PASS] crosstab_schema_and_suppression: 1 entries, 2 cells examined, 0 hidden "
               "as null, 0 fully collapsed, " + CPS_CT_PASS_TAIL, _CPS_ALL_PASS_12],
        line_counts=[("[FAIL]", 0)],
        verdict=_INTAKE_PASSED),
    "cps_intake_missing_partner_one_column_exempt": dict(
        block="CPS-INTAKE", report="report_a3a_mp_one_col_exempt",
        doc="Baseline mirror: a one-column grid's missing-partner row cell is exempt — PASS.",
        lines=["[PASS] crosstab_schema_and_suppression: 1 entries, 2 cells examined, 0 hidden "
               "as null, 0 fully collapsed, " + CPS_CT_PASS_TAIL, _CPS_ALL_PASS_12],
        line_counts=[("[FAIL]", 0)],
        verdict=_INTAKE_PASSED),
    "cps_intake_missing_partner_zero_residual_line": dict(
        block="CPS-INTAKE", report="report_a3a_mp_zero_residual_line",
        doc="Only cat_a has missing values: the missing-partner column's residual is 0, a "
            "line of known zeros that adds no edge, and the pinned missing-partner row "
            "cells are above the gate — PASS.",
        lines=["[PASS] crosstab_schema_and_suppression: 1 entries, 4 cells examined, 0 hidden "
               "as null, 0 fully collapsed, " + CPS_CT_PASS_TAIL, _CPS_ALL_PASS_12],
        line_counts=[("[FAIL]", 0)],
        verdict=_INTAKE_PASSED),
    "cps_intake_missing_partner_collapsed": dict(
        block="CPS-INTAKE", report="report_a3a_mp_collapsed",
        doc="A collapsed entry over a pair with 3 records lacking cat_b: an all-null grid "
            "leaves exactly the baseline graph, so the scan skips it — PASS.",
        lines=["[PASS] crosstab_schema_and_suppression: 1 entries, 4 cells examined, 4 hidden "
               "as null, 1 fully collapsed, " + CPS_CT_PASS_TAIL, _CPS_ALL_PASS_12],
        line_counts=[("[FAIL]", 0)],
        verdict=_INTAKE_PASSED),
    "cps_intake_missing_partner_genuine_protected": dict(
        block="CPS-INTAKE", report="report_a3a_mp_genuine_protected",
        doc="Genuine shape: kept levels in code-point order then __OTHER__, a hidden 2x2 "
            "cycle of the sub-threshold cells, and two sub-threshold missing-partner cells "
            "that close a cycle with it, so neither is pinned — PASS.",
        lines=["[PASS] crosstab_schema_and_suppression: 1 entries, 9 cells examined, 4 hidden "
               "as null, 0 fully collapsed, " + CPS_CT_PASS_TAIL, _CPS_ALL_PASS_12],
        line_counts=[("[FAIL]", 0), ("[NOT VERIFIED]", 0)],
        verdict=_INTAKE_PASSED),
    "cps_intake_crosstab_n_above_nonmissing": dict(
        block="CPS-INTAKE", report="report_a3a_n_above_nonmissing",
        doc="An entry's pair-complete n above a pair column's nonmissing_n cannot be true; "
            "the FAIL names the pair position and the scan does not run.",
        lines=["[FAIL] crosstab_schema_and_suppression: entry cat_a x cat_b has an n above "
               "the nonmissing_n of pair position 1", _C11],
        line_counts=[("[FAIL]", 1)],
        verdict=_INTAKE_FAILED),
    "cps_intake_missing_partner_lacks_totals": dict(
        block="CPS-INTAKE", report="report_a3a_mp_dup_label_pair_column",
        doc="A pair column with missing values whose block repeats a label: its levels no "
            "longer map onto grid rows, so the scan lacks the totals it needs — [NOT "
            "VERIFIED] on the cross-tab check, beside rule 4's repeated-label [FAIL].",
        lines=["[FAIL] no_raw_value_shaped_fields: column 'cat_a' level index 1 repeats the "
               "'value' of level index 0",
               "[NOT VERIFIED] crosstab_schema_and_suppression: entry cat_a x cat_b lacks the "
               "released totals the missing-partner scan needs",
               "Checks: 10 passed, 0 warnings, 1 failed, 1 not verified, 0 skipped"],
        verdict=_INTAKE_FAILED),
    "cps_intake_missing_partner_cannot_gate": dict(
        block="CPS-INTAKE", report="report_a3a_mp_zero_residual_line", exp=None,
        doc="With expected_threshold unset, a pinned (non-baseline) missing-partner cell "
            "has no gate to be tested against — [NOT VERIFIED], beside the sweep's own.",
        lines=["[NOT VERIFIED] no_released_count_below_threshold: expected_threshold not "
               "configured",
               "[NOT VERIFIED] crosstab_schema_and_suppression: entry cat_a x cat_b cannot "
               "gate its missing-partner cells: expected_threshold or "
               "settings.suppression_threshold is unusable",
               "Checks: 10 passed, 0 warnings, 0 failed, 2 not verified, 0 skipped"],
        verdict=_INTAKE_FAILED),
    "cps_intake_missing_partner_ungated_exempt_only": dict(
        block="CPS-INTAKE", report="report_a3a_mp_one_row_exempt", exp=None,
        doc="Control: with no gate but only baseline-exempt missing-partner cells, there is "
            "nothing to gate, so the cross-tab check still PASSES.",
        lines=["[NOT VERIFIED] no_released_count_below_threshold: expected_threshold not "
               "configured",
               "[PASS] crosstab_schema_and_suppression: 1 entries, 2 cells examined, 0 hidden "
               "as null, 0 fully collapsed, " + CPS_CT_PASS_TAIL,
               "Checks: 11 passed, 0 warnings, 0 failed, 1 not verified, 0 skipped"],
        verdict=_INTAKE_FAILED),

    # ---- Fidelity, typing and seed rows, CPS-GEN ------------------------------
    "cps_gen_g2_null_correlation": dict(
        block="CPS-GEN", report="report_g2_null_correlation", synthetic="synthetic_control",
        doc="A null released coefficient is unusable evidence (NOT VERIFIED), "
            "never a crash and never a PASS.",
        lines=["[NOT VERIFIED] correlations_within_tolerance: the released pearson matrix "
               "carries no usable coefficient for pair (num_a, num_b)", _G9NV1],
        verdict=_GEN_FAILED),
    "cps_gen_g3_null_level_count": dict(
        block="CPS-GEN", report="report_g3_null_level_count", synthetic="synthetic_control",
        doc="A level entry with a null count is named by index (never its "
            "label) on every check that reads it.",
        lines=["[NOT VERIFIED] categorical_proportions_within_tolerance: column 'cat_a' level "
               "index 1 is not a string label with a whole-number count",
               "[NOT VERIFIED] suppressed_categories_absent: column 'cat_a' level index 1 is "
               "not a string label with a whole-number count",
               "[NOT VERIFIED] synthetic_levels_within_released_levels: column 'cat_a' level "
               "index 1 is not a string label with a whole-number count",
               "Checks: 7 passed, 0 warnings, 0 failed, 3 not verified, 0 skipped"],
        verdict=_GEN_FAILED),
    "cps_gen_g5_numeric_written_as_string": dict(
        block="CPS-GEN", report="report_control", synthetic="synthetic_numa_string",
        doc="A numeric column written as String is a wrong type in the frame "
            "under validation — three named FAILs, no exception.",
        lines=["[FAIL] column_set_and_dtypes: column 'num_a' is not numeric, the report "
               "declares double",
               "[FAIL] numeric_marginals_within_tolerance: column 'num_a' is not numeric in "
               "the synthetic frame — its released percentiles cannot be reproduced",
               "[FAIL] correlations_within_tolerance: column 'num_a' is correlated in the "
               "report but not numeric in the synthetic frame",
               "Checks: 7 passed, 0 warnings, 3 failed, 0 not verified, 0 skipped"],
        verdict=_GEN_FAILED),
    "cps_gen_e1_zero_percentile_comparisons": dict(
        block="CPS-GEN", report="report_e1_empty_grids", synthetic="synthetic_control",
        doc="A fidelity check that compared nothing is NOT VERIFIED, never "
            "PASS.",
        lines=["[NOT VERIFIED] numeric_marginals_within_tolerance: 2 columns released a "
               "percentile grid but 0 percentile comparisons were made", _G9NV1],
        absent_prefixes=["[PASS] numeric_marginals_within_tolerance:"],
        verdict=_GEN_FAILED),
    "cps_gen_tier3_without_pearson": dict(
        block="CPS-GEN", report="report_tier3_nopearson", synthetic="synthetic_control",
        doc="A tier-3 report always releases a pearson block, so its absence is "
            "missing evidence (NOT VERIFIED), not SKIPPED. The report declares settings.tier "
            "3, matching the configured tier 3, so the tier-mismatch FAIL does not fire.",
        lines=["[NOT VERIFIED] correlations_within_tolerance: the report at configured tier 3 "
               "carries no pearson block — the released correlations cannot be compared",
               _G9NV1],
        line_counts=[("[FAIL]", 0)],
        absent_prefixes=["[SKIPPED] correlations_within_tolerance:"],
        verdict=_GEN_FAILED),
    "cps_gen_tier2_without_pearson": dict(
        block="CPS-GEN", report="report_tier2_nopearson", synthetic="synthetic_control",
        tier=2,
        doc="Control: below tier 3 nothing is released, so the absent pearson block "
            "is SKIPPED and the verdict PASSED.",
        lines=["[SKIPPED] correlations_within_tolerance: no available correlation matrix at "
               "tier 2 — nothing was released to reproduce",
               "Checks: 9 passed, 0 warnings, 0 failed, 0 not verified, 1 skipped"],
        verdict=_GEN_PASSED),
    "cps_gen_t4a_tier4_report_and_seed": dict(
        block="CPS-GEN", report="report_control", synthetic="synthetic_control", tier=4,
        doc="Config tier 4 with a profile report and the user's logged seed "
            "runs in full and PASSES.",
        lines=["[PASS] seed_recorded: generation seed 20260915 present in the script config "
               "and printed to the log",
               "Checks: 10 passed, 0 warnings, 0 failed, 0 not verified, 0 skipped"],
        verdict=_GEN_PASSED),
    "cps_gen_t4b_seed_exception": dict(
        block="CPS-GEN", report="report_control", synthetic="synthetic_control", tier=4,
        seed=None, seed_exception=CPS_SEED_EXCEPTION,
        doc="The researcher-authorized T4 missing-seed exception is a "
            "WARNING, never a PASS, and its STATE pointer is never printed.",
        lines=["[WARNING] seed_recorded: tier 4 import with no recorded seed — "
               "researcher-authorized non-reproducible T4 exception (authorization "
               "recorded in STATE)",
               "Checks: 9 passed, 1 warnings, 0 failed, 0 not verified, 0 skipped"],
        line_counts=[("[PASS] seed_recorded:", 0)],
        verdict="CPS-GEN VALIDATION: PASSED WITH WARNINGS"),
    "cps_gen_t4c_seed_exception_below_tier4": dict(
        block="CPS-GEN", report="report_control", synthetic="synthetic_control", tier=3,
        seed=None, seed_exception=CPS_SEED_EXCEPTION,
        doc="`seed_exception` is honored only at tier 4.",
        lines=["[FAIL] seed_recorded: seed_exception is honored only at tier 4", _G9F1],
        verdict=_GEN_FAILED),
    "cps_gen_t4d_seed_and_exception_both_set": dict(
        block="CPS-GEN", report="report_control", synthetic="synthetic_control", tier=4,
        seed_exception=CPS_SEED_EXCEPTION,
        doc="Seed and seed_exception are mutually exclusive.",
        lines=["[FAIL] seed_recorded: seed and seed_exception are both set — record one",
               _G9F1],
        verdict=_GEN_FAILED),
    "cps_gen_p2_nested_duplicate_key": dict(
        block="CPS-GEN", report="report_p2_dup_key_nested", synthetic="synthetic_control",
        doc="A duplicate key nested in a level entry is a parse error in both "
            "languages; seed_recorded reads only the config, so it still runs.",
        lines=CPS_GEN_PARSE_LINES
              + ["[PASS] seed_recorded: generation seed 20260915 present in the script "
                 "config and printed to the log",
                 "Checks: 1 passed, 0 warnings, 0 failed, 9 not verified, 0 skipped"],
        verdict=_GEN_FAILED),

    # ---- Canonical text form, column types and pooling, CPS-GEN -------------------
    "cps_gen_float_ids_vs_integer_label": dict(
        block="CPS-GEN", report="report_gen_float_ids", synthetic="synthetic_float_ids",
        doc="Synthetic identifiers stored as whole-number floats (1.0, 2.0, ...) "
            "reduce to the canonical text '1', '2', ..., so they collide with the "
            "integer-coded released label '1' in both languages — the same FAIL.",
        lines=["[FAIL] identifier_columns_value_free: identifier column 'member_id' reuses "
               "a value from a released level set", _G9F1],
        verdict=_GEN_FAILED),
    "cps_gen_bool_vs_python_labels": dict(
        block="CPS-GEN", report="report_gen_bool_py", synthetic="synthetic_bool",
        doc="A synthetic Boolean matches the Python profiler's "
            "'True'/'False' labels through the canonical text form (true/false, "
            "case-insensitive), so the level checks PASS — but undeclared, "
            "column_set_and_dtypes FAILS it against the declared dtype string.",
        lines=CPS_BOOL_LINES,
        verdict=_GEN_FAILED),
    "cps_gen_bool_vs_r_labels": dict(
        block="CPS-GEN", report="report_gen_bool_r", synthetic="synthetic_bool",
        doc="The same synthetic Boolean against the R profiler's "
            "'TRUE'/'FALSE' — level checks PASS, the dtype check FAILS.",
        lines=CPS_BOOL_LINES,
        verdict=_GEN_FAILED),
    "cps_gen_bool_text_vs_python_labels": dict(
        block="CPS-GEN", report="report_gen_bool_py", synthetic="synthetic_bool_text_py",
        doc="Companion: the boolean column written as the Python "
            "profiler's string labels, as the generation recipes write it, satisfies the "
            "declared dtype string — PASSED.",
        lines=CPS_BOOL_TEXT_LINES,
        verdict=_GEN_PASSED),
    "cps_gen_bool_text_vs_r_labels": dict(
        block="CPS-GEN", report="report_gen_bool_r", synthetic="synthetic_bool_text_r",
        doc="Companion: the same with the R profiler's 'TRUE'/'FALSE' "
            "string labels — PASSED.",
        lines=CPS_BOOL_TEXT_LINES,
        verdict=_GEN_PASSED),
    "cps_gen_duration_column": dict(
        block="CPS-GEN", report="report_control", synthetic="synthetic_catb_duration",
        doc="A Duration column compared with released labels is outside the "
            "text-comparable types — a named FAIL on every level check, never an escape.",
        lines=[f"[FAIL] categorical_proportions_within_tolerance: column 'cat_b' "
               f"{_CPS_GEN_UNTEXTABLE} — its levels cannot be compared",
               f"[FAIL] suppressed_categories_absent: column 'cat_b' {_CPS_GEN_UNTEXTABLE} — "
               f"its levels cannot be compared",
               f"[FAIL] synthetic_levels_within_released_levels: column 'cat_b' "
               f"{_CPS_GEN_UNTEXTABLE} — its levels cannot be compared",
               "[FAIL] column_set_and_dtypes: column 'cat_b' is not a string column, the "
               "report declares string",
               "Checks: 6 passed, 0 warnings, 4 failed, 0 not verified, 0 skipped"],
        verdict=_GEN_FAILED),
    "cps_gen_pooled_column_emits_other": dict(
        block="CPS-GEN", report="report_gen_pooled", synthetic="synthetic_pooled_other",
        tier=2,
        doc="A fully pooled column (levels [], n_levels_binned > 0) may carry the "
            "literal __OTHER__ as its one level — PASS (3 distinct synthetic levels: "
            "cat_a's two plus pool's __OTHER__, all admitted).",
        lines=["[PASS] suppressed_categories_absent: 2 categorical columns examined, 0 pooled "
               "buckets preserved, 0 levels added",
               "[PASS] synthetic_levels_within_released_levels: 2 columns, 3 distinct "
               "synthetic levels, all inside the released sets",
               "[PASS] missingness_within_tolerance: 2 columns, all null rates within "
               "+/-0.01 of the reported rate", _G8S2],
        verdict=_GEN_PASSED),
    "cps_gen_pooled_column_all_null": dict(
        block="CPS-GEN", report="report_gen_pooled", synthetic="synthetic_pooled_null",
        tier=2,
        doc="The same fully pooled column left entirely null is also satisfiable "
            "(no __OTHER__ demanded when __OTHER__ is not a released level) — PASS.",
        lines=["[PASS] suppressed_categories_absent: 2 categorical columns examined, 0 pooled "
               "buckets preserved, 0 levels added",
               "[PASS] synthetic_levels_within_released_levels: 2 columns, 2 distinct "
               "synthetic levels, all inside the released sets",
               "[PASS] missingness_within_tolerance: 2 columns, all null rates within "
               "+/-0.01 of the reported rate", _G8S2],
        verdict=_GEN_PASSED),
    "cps_gen_duplicate_parquet_column_names": dict(
        block="CPS-GEN", report="report_control", synthetic="synthetic_dup_names",
        doc="A parquet storing a column name twice is a read failure in both "
            "languages (polars alone would silently keep one of the repeats).",
        lines=CPS_GEN_READ_LINES
              + [_CPS_GEN_SEED_PASS,
                 "Checks: 1 passed, 0 warnings, 0 failed, 9 not verified, 0 skipped"],
        verdict=_GEN_FAILED),
    "cps_gen_report_utf8_bom": dict(
        block="CPS-GEN", report="report_control_bom", synthetic="synthetic_control",
        doc="A report with a leading UTF-8 BOM is a parse error in both languages.",
        lines=CPS_GEN_PARSE_LINES
              + [_CPS_GEN_SEED_PASS,
                 "Checks: 1 passed, 0 warnings, 0 failed, 9 not verified, 0 skipped"],
        verdict=_GEN_FAILED),
    "cps_gen_nbsp_seed_exception_is_unset": dict(
        block="CPS-GEN", report="report_control", synthetic="synthetic_control", tier=4,
        seed=None, seed_exception="  ",
        doc="A seed_exception of no-break spaces only is blank (Python str.strip() "
            "whitespace, spelled out in R), so it counts as unset in both languages and "
            "seed_recorded FAILS — not the tier-4 WARNING.",
        lines=["[FAIL] seed_recorded: the generation seed is not an integer recorded in "
               "this script's config", _G9F1],
        line_counts=[("[WARNING] seed_recorded:", 0)],
        verdict=_GEN_FAILED),

    # ---- Number tokens and configured tier, CPS-GEN ----------------------------
    "cps_gen_number_token_65_chars": dict(
        block="CPS-GEN", report="report_control_number_token_65", synthetic="synthetic_control",
        doc="A 65-character number token in the report (40 written with 62 fraction "
            "zeros) is a parse error in both languages; seed_recorded reads only the "
            "config, so it still runs.",
        lines=CPS_GEN_PARSE_LINES
              + [_CPS_GEN_SEED_PASS,
                 "Checks: 1 passed, 0 warnings, 0 failed, 9 not verified, 0 skipped"],
        verdict=_GEN_FAILED),
    "cps_gen_configured_tier_differs_from_report": dict(
        block="CPS-GEN", report="report_control", synthetic="synthetic_control", tier=2,
        doc="The configured tier is the tier the report was produced at, so a "
            "tier-3 report checked at configured tier 2 FAILS instead of silently skipping "
            "its released correlations.",
        lines=["[FAIL] correlations_within_tolerance: configured tier 2 differs from the "
               "report's declared tier 3", _G9F1],
        absent_prefixes=["[SKIPPED] correlations_within_tolerance:"],
        verdict=_GEN_FAILED),
}

# Every CPS fixture of either language: the 8 hand-registered ones (5 CPS-INTAKE +
# 3 CPS-GEN, each with an R twin) plus one per CPS_REGRESSION_CASES row. The leak
# scans and the parity test assert at least this many, so a registration that
# silently drops rows fails loudly.
_CPS_HAND_REGISTERED = 8
CPS_MIN_FIXTURES = _CPS_HAND_REGISTERED + len(CPS_REGRESSION_CASES)


def _r_na_literal(mapping):
    """An R `list(...)` literal for a not_applicable mapping. JSON string escapes
    are valid R string escapes for these ASCII reasons."""
    if len(mapping) == 0:
        return "list()"
    return "list(%s)" % ", ".join(f"{k} = {json.dumps(v)}" for k, v in mapping.items())


def _cps_literal(value, lang):
    """Source text assigning `value` in a CPS `# --- Config ---` stanza.

    Python: `repr`. R: NULL for None, an integer literal (`5L`) for ints that fit
    R's 32-bit integers, and a JSON-escaped string — JSON string escapes are valid
    R string escapes for the ASCII values used here.
    """
    if lang == "python":
        return repr(value)
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return f"{value}L" if abs(value) < 2 ** 31 else str(value)
    if isinstance(value, float):
        return repr(value)
    return json.dumps(value)


def _cps_case_config(case, rf, lang):
    """The `# --- Config ---` rewrite for one CPS_REGRESSION_CASES row, in either
    language, from the same row values — so the two registries cannot configure a
    row differently."""
    cfg = {"report_path": _cps_literal(rf[case["report"]], lang),
           "tier": _cps_literal(case.get("tier", 3), lang),
           "not_applicable": (repr(case.get("na", {})) if lang == "python"
                              else _r_na_literal(case.get("na", {})))}
    if case["block"] == "CPS-INTAKE":
        cfg["expected_threshold"] = _cps_literal(case.get("exp", CPS_APPROVED_THRESHOLD), lang)
    else:
        cfg["synthetic_path"] = _cps_literal(rf[case["synthetic"]], lang)
        cfg["seed"] = _cps_literal(case.get("seed", _CPS_DEFAULT_SEED), lang)
        cfg["seed_exception"] = _cps_literal(case.get("seed_exception"), lang)
    return cfg


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

    # --- Metric corrections (rates and ratios guarded against zero sources) ---

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
    # review-severity family.
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

    # --- CP2 dtype comparability (numeric guards) -----------------------------

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

    # Duplicate keys on a side the declaration calls unique
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

    # --- CPS-INTAKE / CPS-GEN (Data Onboarding, synthetic path) ---------------
    # These blocks read real artifacts (a profile report JSON, a synthetic
    # parquet) rather than a prepared namespace, so the fixture supplies files and
    # rewrites the block's own `# --- Config ---` assignments to point at them.
    rf = _report_fixtures(scratch)

    # Every CPS-INTAKE fixture configures the researcher-approved threshold: with
    # `expected_threshold` unset the disclosure sweep is [NOT VERIFIED] and the block
    # FAILS by design (asserted on purpose in cps_intake_expected_threshold_unset).
    _cps_intake_cfg = {"tier": "3", "expected_threshold": repr(CPS_APPROVED_THRESHOLD),
                       "not_applicable": "{}"}

    fx["cps_intake_control"] = dict(
        code=_set_cps_config(_vc("CPS-INTAKE"),
                             dict(_cps_intake_cfg, report_path=repr(rf["report_control"]))),
        ns={},
        contains=[CPS_CONTROL_SWEEP_PASS_LINE,
                  "Checks: 12 passed, 0 warnings, 0 failed, 0 not verified, 0 skipped",
                  "CPS-INTAKE VALIDATION: PASSED"],
        counter_dict=("cps_intake", {"passed": 12, "warning": 0, "failed": 0,
                                     "not_verified": 0, "skipped": 0}))

    # A count below the gate is named by block and level INDEX; the count itself
    # never reaches the log (asserted line-wise in
    # test_cps_intake_subthreshold_fail_line_omits_the_count).
    fx["cps_intake_subthreshold_count"] = dict(
        code=_set_cps_config(_vc("CPS-INTAKE"),
                             dict(_cps_intake_cfg, report_path=repr(rf["report_subthreshold"]))),
        ns={},
        contains=["[FAIL] no_released_count_below_threshold: categorical block 'cat_b' "
                  "level index 2 carries a visible count below the gate",
                  "Checks: 11 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped",
                  "CPS-INTAKE VALIDATION: FAILED"],
        counter_dict=("cps_intake", {"passed": 11, "warning": 0, "failed": 1,
                                     "not_verified": 0, "skipped": 0}),
        raises="CPS-INTAKE FAILED - see details above")

    # Declaring a non-declarable disclosure check is itself the finding — one [FAIL]
    # for the declaration, and the check still runs.
    fx["cps_intake_non_declarable_declared"] = dict(
        code=_set_cps_config(
            _vc("CPS-INTAKE"),
            dict(_cps_intake_cfg, report_path=repr(rf["report_control"]),
                 not_applicable=repr({"no_released_count_below_threshold": "x"}))),
        ns={},
        contains=["[FAIL] no_released_count_below_threshold: non-declarable check "
                  "declared not_applicable under key 'no_released_count_below_threshold'",
                  "[PASS] no_released_count_below_threshold: 3 of 3 declared blocks scanned",
                  "Checks: 12 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped",
                  "CPS-INTAKE VALIDATION: FAILED"],
        counter_dict=("cps_intake", {"passed": 12, "warning": 0, "failed": 1,
                                     "not_verified": 0, "skipped": 0}),
        raises="CPS-INTAKE FAILED - see details above")

    # Scan completeness is itself a check: a column that declares a role but carries
    # no block is missing evidence, and the sweep that skipped it must say so rather
    # than reporting a clean pass over the blocks it did reach. The report's cross-tab
    # entry is unavailable (no released levels to build it on), so the sweep declares
    # the two categorical blocks only and reaches one of them.
    fx["cps_intake_missing_categorical_block"] = dict(
        code=_set_cps_config(_vc("CPS-INTAKE"),
                             dict(_cps_intake_cfg,
                                  report_path=repr(rf["report_missing_catblock"]))),
        ns={},
        contains=["[NOT VERIFIED] category_counts_le_rowcount: column 'cat_b' declares "
                  "role categorical but has no categorical block",
                  "[FAIL] no_released_count_below_threshold: scanned 1 of 2 declared "
                  "blocks — the sweep is incomplete",
                  "Checks: 10 passed, 0 warnings, 1 failed, 1 not verified, 0 skipped",
                  "CPS-INTAKE VALIDATION: FAILED"],
        counter_dict=("cps_intake", {"passed": 10, "warning": 0, "failed": 1,
                                     "not_verified": 1, "skipped": 0}),
        raises="CPS-INTAKE FAILED - see details above")

    # SKIPPED versus NOT VERIFIED: a tier that releases no correlations is
    # a structural fact, so the absent matrix is [SKIPPED] and the verdict PASSED. The
    # report is a genuine tier-2 one — no `relationships` key at all, as the profiler
    # writes it; a tier-2 report that still carries relationships content is a FAIL
    # (asserted in cps_intake_relationships_below_tier3).
    fx["cps_intake_tier2_no_correlations"] = dict(
        code=_set_cps_config(_vc("CPS-INTAKE"),
                             dict(_cps_intake_cfg, tier="2",
                                  report_path=repr(rf["report_tier2_genuine"]))),
        ns={},
        contains=["[SKIPPED] correlation_matrix_wellformed: tier 2 releases no "
                  "correlation matrices (0 matrices declared)",
                  "Checks: 11 passed, 0 warnings, 0 failed, 0 not verified, 1 skipped",
                  "CPS-INTAKE VALIDATION: PASSED"],
        counter_dict=("cps_intake", {"passed": 11, "warning": 0, "failed": 0,
                                     "not_verified": 0, "skipped": 1}))

    _cps_gen_cfg = {"report_path": repr(rf["report_control"]), "tier": "3",
                    "seed": "20260915", "not_applicable": "{}"}

    # The CPS-GEN control is the regression that caught a polars `value_counts()`
    # row-ordering bug: level proportions compared by position instead of by label
    # made a faithful frame look off-tolerance, non-deterministically.
    fx["cps_gen_control"] = dict(
        code=_set_cps_config(_vc("CPS-GEN"),
                             dict(_cps_gen_cfg,
                                  synthetic_path=repr(rf["synthetic_control"]))),
        ns={},
        contains=["[PASS] categorical_proportions_within_tolerance:",
                  "[PASS] synthetic_levels_within_released_levels:",
                  "[PASS] seed_recorded: generation seed 20260915 present in the script "
                  "config and printed to the log",
                  "Checks: 10 passed, 0 warnings, 0 failed, 0 not verified, 0 skipped",
                  "CPS-GEN VALIDATION: PASSED"],
        counter_dict=("cps_gen", {"passed": 10, "warning": 0, "failed": 0,
                                  "not_verified": 0, "skipped": 0}))

    # Fabrication: one row carries a level the report never released. Fidelity
    # drift is a [WARNING]; inventing a level is a [FAIL] on two checks.
    fx["cps_gen_unreleased_level"] = dict(
        code=_set_cps_config(_vc("CPS-GEN"),
                             dict(_cps_gen_cfg,
                                  synthetic_path=repr(rf["synthetic_badlevel"]))),
        ns={},
        contains=["[FAIL] synthetic_levels_within_released_levels: column 'cat_a' "
                  "carries 1 synthetic levels outside the released set",
                  "[FAIL] suppressed_categories_absent: column 'cat_a' carries 4 "
                  "distinct synthetic levels against 3 released",
                  "Checks: 7 passed, 1 warnings, 2 failed, 0 not verified, 0 skipped",
                  "CPS-GEN VALIDATION: FAILED"],
        counter_dict=("cps_gen", {"passed": 7, "warning": 1, "failed": 2,
                                  "not_verified": 0, "skipped": 0}),
        raises="CPS-GEN FAILED - see details above")

    # The non-declarable rule on the CPS-GEN side (seed_recorded is non-declarable).
    fx["cps_gen_non_declarable_declared"] = dict(
        code=_set_cps_config(
            _vc("CPS-GEN"),
            dict(_cps_gen_cfg, synthetic_path=repr(rf["synthetic_control"]),
                 not_applicable=repr({"seed_recorded": "x"}))),
        ns={},
        contains=["[FAIL] seed_recorded: non-declarable check declared not_applicable "
                  "under key 'seed_recorded'",
                  "[PASS] seed_recorded: generation seed 20260915 present in the script "
                  "config and printed to the log",
                  "Checks: 10 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped",
                  "CPS-GEN VALIDATION: FAILED"],
        counter_dict=("cps_gen", {"passed": 10, "warning": 0, "failed": 1,
                                  "not_verified": 0, "skipped": 0}),
        raises="CPS-GEN FAILED - see details above")

    # --- CPS regression fixtures (CPS_REGRESSION_CASES) -----------------------
    # One entry per `CPS_REGRESSION_CASES` row; the R registry builds its mirrors
    # from the same rows, so the two languages cannot drift apart.
    for case_name, case in CPS_REGRESSION_CASES.items():
        halts = case["verdict"].endswith(": FAILED")
        fx[case_name] = dict(
            code=_set_cps_config(_vc(case["block"]), _cps_case_config(case, rf, "python")),
            ns={},
            raises=f"{case['block']} FAILED - see details above" if halts else None,
            **{k: case[k] for k in _CPS_CASE_EXPECTATION_KEYS if k in case})

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
    # R side of the duplicate-key rule: a duplicated right key under a declared 1:1 is a
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

# The R CPS fixtures mirror the Python control/defect pairs for the same blocks.
# They read real artifacts, so they carry a `config` callable that receives the
# `_report_fixtures()` path map and returns the `# --- Config ---` rewrite for the
# block; registration is conditional on polars because that is what builds the
# report JSON and the synthetic parquet (the R fences load jsonlite and arrow
# themselves).
if HAS_POLARS:
    R_FIXTURES["r_cps_intake_control"] = dict(
        block=("VC", "CPS-INTAKE", "r"), setup="",
        config=lambda rf: {"report_path": '"%s"' % rf["report_control"],
                           "tier": "3L", "expected_threshold": "%dL" % CPS_APPROVED_THRESHOLD,
                           "not_applicable": "list()"},
        contains=[CPS_CONTROL_SWEEP_PASS_LINE,
                  "Checks: 12 passed, 0 warnings, 0 failed, 0 not verified, 0 skipped",
                  "CPS-INTAKE VALIDATION: PASSED"],
        stops=False)
    R_FIXTURES["r_cps_intake_subthreshold_count"] = dict(
        block=("VC", "CPS-INTAKE", "r"), setup="",
        config=lambda rf: {"report_path": '"%s"' % rf["report_subthreshold"],
                           "tier": "3L", "expected_threshold": "%dL" % CPS_APPROVED_THRESHOLD,
                           "not_applicable": "list()"},
        contains=["[FAIL] no_released_count_below_threshold: categorical block 'cat_b' "
                  "level index 2 carries a visible count below the gate",
                  "Checks: 11 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped",
                  "CPS-INTAKE VALIDATION: FAILED"],
        stops=True)
    R_FIXTURES["r_cps_gen_control"] = dict(
        block=("VC", "CPS-GEN", "r"), setup="",
        config=lambda rf: {"synthetic_path": '"%s"' % rf["synthetic_control"],
                           "report_path": '"%s"' % rf["report_control"],
                           "seed": "20260915L", "tier": "3L",
                           "not_applicable": "list()"},
        contains=["[PASS] synthetic_levels_within_released_levels:",
                  "[PASS] seed_recorded: generation seed 20260915 present in the script "
                  "config and printed to the log",
                  "Checks: 10 passed, 0 warnings, 0 failed, 0 not verified, 0 skipped",
                  "CPS-GEN VALIDATION: PASSED"],
        stops=False)
    R_FIXTURES["r_cps_gen_unreleased_level"] = dict(
        block=("VC", "CPS-GEN", "r"), setup="",
        config=lambda rf: {"synthetic_path": '"%s"' % rf["synthetic_badlevel"],
                           "report_path": '"%s"' % rf["report_control"],
                           "seed": "20260915L", "tier": "3L",
                           "not_applicable": "list()"},
        contains=["[FAIL] synthetic_levels_within_released_levels: column 'cat_a' "
                  "carries 1 synthetic levels outside the released set",
                  "[FAIL] suppressed_categories_absent: column 'cat_a' carries 4 "
                  "distinct synthetic levels against 3 released",
                  "Checks: 7 passed, 1 warnings, 2 failed, 0 not verified, 0 skipped",
                  "CPS-GEN VALIDATION: FAILED"],
        stops=True)

    # R twins of the four hand-registered Python-only CPS fixtures, added so the
    # Py/R parity test covers every hand-registered CPS fixture too.
    R_FIXTURES["r_cps_intake_non_declarable_declared"] = dict(
        block=("VC", "CPS-INTAKE", "r"), setup="",
        config=lambda rf: {"report_path": '"%s"' % rf["report_control"],
                           "tier": "3L", "expected_threshold": "%dL" % CPS_APPROVED_THRESHOLD,
                           "not_applicable": 'list(no_released_count_below_threshold = "x")'},
        contains=["[FAIL] no_released_count_below_threshold: non-declarable check "
                  "declared not_applicable under key 'no_released_count_below_threshold'",
                  "[PASS] no_released_count_below_threshold: 3 of 3 declared blocks scanned",
                  "Checks: 12 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped",
                  "CPS-INTAKE VALIDATION: FAILED"],
        stops=True)
    R_FIXTURES["r_cps_intake_missing_categorical_block"] = dict(
        block=("VC", "CPS-INTAKE", "r"), setup="",
        config=lambda rf: {"report_path": '"%s"' % rf["report_missing_catblock"],
                           "tier": "3L", "expected_threshold": "%dL" % CPS_APPROVED_THRESHOLD,
                           "not_applicable": "list()"},
        contains=["[NOT VERIFIED] category_counts_le_rowcount: column 'cat_b' declares "
                  "role categorical but has no categorical block",
                  "[FAIL] no_released_count_below_threshold: scanned 1 of 2 declared "
                  "blocks — the sweep is incomplete",
                  "Checks: 10 passed, 0 warnings, 1 failed, 1 not verified, 0 skipped",
                  "CPS-INTAKE VALIDATION: FAILED"],
        stops=True)
    R_FIXTURES["r_cps_intake_tier2_no_correlations"] = dict(
        block=("VC", "CPS-INTAKE", "r"), setup="",
        config=lambda rf: {"report_path": '"%s"' % rf["report_tier2_genuine"],
                           "tier": "2L", "expected_threshold": "%dL" % CPS_APPROVED_THRESHOLD,
                           "not_applicable": "list()"},
        contains=["[SKIPPED] correlation_matrix_wellformed: tier 2 releases no "
                  "correlation matrices (0 matrices declared)",
                  "Checks: 11 passed, 0 warnings, 0 failed, 0 not verified, 1 skipped",
                  "CPS-INTAKE VALIDATION: PASSED"],
        stops=False)
    R_FIXTURES["r_cps_gen_non_declarable_declared"] = dict(
        block=("VC", "CPS-GEN", "r"), setup="",
        config=lambda rf: {"synthetic_path": '"%s"' % rf["synthetic_control"],
                           "report_path": '"%s"' % rf["report_control"],
                           "seed": "20260915L", "tier": "3L",
                           "not_applicable": 'list(seed_recorded = "x")'},
        contains=["[FAIL] seed_recorded: non-declarable check declared not_applicable "
                  "under key 'seed_recorded'",
                  "[PASS] seed_recorded: generation seed 20260915 present in the script "
                  "config and printed to the log",
                  "Checks: 10 passed, 0 warnings, 1 failed, 0 not verified, 0 skipped",
                  "CPS-GEN VALIDATION: FAILED"],
        stops=True)

    # Regression-case mirrors: same rows as the Python fixtures (CPS_REGRESSION_CASES).
    # A FAILED verdict must come with the block's own stop() message and nothing else —
    # an R-level error (e.g. "subscript out of bounds", how a short correlation matrix
    # once aborted the R block) would be captured as a different STOPPED message and
    # fail `stop_message`.
    for _case_name, _case in CPS_REGRESSION_CASES.items():
        _halts = _case["verdict"].endswith(": FAILED")
        R_FIXTURES["r_" + _case_name] = dict(
            block=("VC", _case["block"], "r"), setup="",
            config=lambda rf, _c=_case: _cps_case_config(_c, rf, "r"),
            contains=[], stops=_halts,
            stop_message=f"{_case['block']} FAILED - see details above" if _halts else None,
            **{k: _case[k] for k in _CPS_CASE_EXPECTATION_KEYS if k in _case})


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
             "CPP1", "CPP2", "CPP3", "CPP4", "CPP-SKILL",
             "CPS-INTAKE", "CPS-GEN"},
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
        """Stub Detection's single check has no
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
        # [WARN] is retired in favour of [WARNING].
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
        # 5 = EXPECTED_QA_TOTAL / 2 (one python block per QA family)
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
        # Registered first: unittest skips tearDownClass when setUpClass raises.
        cls.addClassCleanup(_drop_scratch, cls.scratch)
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

    def test_rscript_driver_ran(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)
        self.assertEqual(len(self.results), len(self.labels),
                         f"parsed {sorted(self.results)} vs expected "
                         f"{sorted(n for n, _ in self.labels)}")

    def test_every_r_template_block_parses(self):
        # 5 = EXPECTED_QA_TOTAL / 2 (one r block per QA family)
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
        # Registered before the fixtures are built: unittest skips tearDown when setUp
        # raises, so a fixture build that fails would otherwise leave its scratch behind.
        self.addCleanup(_drop_scratch, self.scratch)
        self.fixtures = _py_fixtures(self.scratch)

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
        except ValueError as exc:      # the templates' halting mechanism
            raised = str(exc)
        out = buf.getvalue()
        emitted = [ln for ln in out.split("\n") if ln.startswith("[")]

        # A per-check line must not look like a checkpoint
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
        if spec.get("counter_dict") is not None:
            key, expected = spec["counter_dict"]
            self.assertIn(key, ns, f"{name}: block defined no `{key}` accumulator\n{out}")
            self.assertEqual(ns[key], expected, f"{name}: {key} {ns[key]}\n{out}")
        if spec.get("line_count") is not None:
            prefix, expected = spec["line_count"]
            got = sum(1 for ln in out.splitlines() if ln.startswith(prefix))
            self.assertEqual(got, expected,
                             f"{name}: expected {expected} line(s) starting {prefix!r}, "
                             f"got {got}\n{out}")
        _assert_line_expectations(self, name, spec, out)
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

    # -- metric corrections (rates and ratios guarded against zero sources) -

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

    # -- Join: declared cardinality contradicted by the inputs -----------

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

    # -- CPS-INTAKE / CPS-GEN (synthetic path) ----------------------------

    def test_cps_intake_control(self):
        """The control report is derived from the fixture frame with the same
        polars calls the blocks re-derive it with, so a FAIL here indicts the
        shipped block rather than the fixture."""
        self._run("cps_intake_control")

    def test_cps_intake_subthreshold_count(self):
        self._run("cps_intake_subthreshold_count")

    def test_cps_intake_subthreshold_fail_line_omits_the_count(self):
        """A FAIL on a disclosure check names the block and the cell
        position only. The offending level's count is 3, so the FAIL line must not
        carry that digit at all."""
        out = self._run("cps_intake_subthreshold_count")
        lines = [ln for ln in out.splitlines()
                 if ln.startswith("[FAIL] no_released_count_below_threshold")]
        self.assertEqual(len(lines), 1, out)
        self.assertNotIn("3", lines[0].split(":", 1)[1],
                         f"the FAIL line leaks the suppressed count: {lines[0]!r}")

    def test_cps_intake_non_declarable_declared(self):
        """Declaring a non-declarable disclosure check is itself a [FAIL], and the
        check still runs on the un-declared path."""
        self._run("cps_intake_non_declarable_declared")

    def test_cps_intake_missing_categorical_block(self):
        self._run("cps_intake_missing_categorical_block")

    def test_cps_intake_tier2_no_correlations(self):
        self._run("cps_intake_tier2_no_correlations")

    def test_cps_intake_pass_line_is_aggregate_only(self):
        """Aggregate-only evidence, positive side.

        Approach: the [PASS] line is allowed to carry aggregate facts (blocks
        scanned, cells examined, the threshold). Strip exactly those, then assert
        no fixture cell count survives. The fixture's individual counts are
        20/10/10 (cat_a levels), 20/20 (cat_b levels) and 10/10/5/5/5/5 (crosstab
        cells), so a standalone 20, 10 or 5 in the residue would be a leaked
        value. The threshold literals (effective, declared and approved — all 5
        here) are stripped first, since a threshold is an allowed disclosure — it
        is a policy constant, not an observation.
        """
        out = self._run("cps_intake_control")
        lines = [ln for ln in out.splitlines()
                 if ln.startswith("[PASS] no_released_count_below_threshold")]
        self.assertEqual(len(lines), 1, out)
        residue = lines[0]
        for allowed in ("3 of 3 declared blocks scanned",
                        "(2 categorical + 1 cross-tab)",
                        "11 visible cells examined",
                        "effective threshold 5",
                        "(declared 5, approved 5)"):
            self.assertIn(allowed, residue,
                          f"aggregate phrasing changed; re-derive the strip list: {lines[0]!r}")
            residue = residue.replace(allowed, "")
        self.assertIsNone(
            re.search(r"\b(20|10|5)\b", residue),
            f"the PASS line carries a fixture cell count: {lines[0]!r} (residue {residue!r})")

    def test_cps_gen_control(self):
        """Regression: comparing level proportions by position rather than by
        label made a faithful frame fail non-deterministically, because polars
        `value_counts()` does not promise a row order."""
        self._run("cps_gen_control")

    def test_cps_gen_unreleased_level(self):
        self._run("cps_gen_unreleased_level")

    def test_cps_gen_non_declarable_declared(self):
        self._run("cps_gen_non_declarable_declared")

    # -- CPS regression rows with hand-written test methods ---------------

    def test_cps_intake_q3a_collapsed_all_null(self):
        """An all-null collapsed entry earns the complementary-suppression bypass and is
        counted."""
        self._run("cps_intake_q3a_collapsed_all_null")

    def test_cps_intake_q3b_collapsed_visible(self):
        """`collapsed: true` over a grid that still shows a cell used to switch
        the complementary-suppression scan off while the cell stayed released."""
        self._run("cps_intake_q3b_collapsed_visible")

    def test_cps_intake_q4a_identifier_example(self):
        """The deny-list let `string_structure.example` through; the allow-list
        and the scalar value-key rule must each FAIL, naming the key only."""
        self._run("cps_intake_q4a_identifier_example")

    def test_cps_intake_q4b_identifier_withheld(self):
        self._run("cps_intake_q4b_identifier_withheld")

    def test_cps_intake_q4c_identifier_allowlist_control(self):
        self._run("cps_intake_q4c_identifier_allowlist_control")

    def test_cps_intake_q4d_null_sibling_path(self):
        self._run("cps_intake_q4d_null_sibling_path")

    def test_cps_intake_q4e_null_in_long_list(self):
        self._run("cps_intake_q4e_null_in_long_list")

    def test_cps_intake_q5_unrecognized_key(self):
        """A typo'd key used to declare nothing and be ignored."""
        self._run("cps_intake_q5_unrecognized_key")

    def test_cps_intake_q6_empty_reason_declarable(self):
        """A whitespace reason used to drop the declaration and silently run
        the check, printing a [PASS] for a question the author withdrew."""
        self._run("cps_intake_q6_empty_reason_declarable")

    def test_cps_intake_q6b_empty_reason_non_declarable(self):
        self._run("cps_intake_q6b_empty_reason_non_declarable")

    def test_cps_intake_leak_subthreshold(self):
        self._run("cps_intake_leak_subthreshold")

    def test_cps_gen_q1_matrix_dimension_mismatch(self):
        """Three declared columns over a 2x2 matrix used to abort the block
        with an uncaught IndexError instead of a verdict."""
        self._run("cps_gen_q1_matrix_dimension_mismatch")

    def test_cps_gen_q2_unrecognized_percentile_key(self):
        """A `median` alias used to crash the percentile parse."""
        self._run("cps_gen_q2_unrecognized_percentile_key")

    def test_cps_gen_q5_unrecognized_key(self):
        self._run("cps_gen_q5_unrecognized_key")

    def test_cps_gen_q6_empty_reason_declarable(self):
        self._run("cps_gen_q6_empty_reason_declarable")

    def test_cps_gen_q6b_empty_reason_non_declarable(self):
        self._run("cps_gen_q6b_empty_reason_non_declarable")

    # -- whole-stdout disclosure leak scan --------------------------------

    def test_cps_whole_stdout_leak_scan(self):
        """No planted disclosure token may reach ANY line
        of any CPS fixture's stdout.

        The older aggregate-only test guards one PASS line; a leak on a FAIL line,
        a banner, or a second PASS line would slip past it. This scans the whole
        of stdout for every CPS fixture of both blocks. It is non-vacuous by
        construction: each fixture's report (read from the path its own config
        seam points at) must carry at least one planted token, and every token
        must be planted in at least one report.
        """
        cps = sorted(n for n in self.fixtures if n.startswith("cps_"))
        self.assertGreaterEqual(len(cps), CPS_MIN_FIXTURES, cps)
        planted_anywhere = set()
        for name in cps:
            with self.subTest(fixture=name):
                m = re.search(r"^report_path = (.+)$", self.fixtures[name]["code"], re.M)
                self.assertIsNotNone(m, f"{name}: no rewritten report_path seam")
                report_text = Path(ast.literal_eval(m.group(1))).read_text(encoding="utf-8")
                # A CPS-GEN seed_exception is a STATE pointer the block must never
                # print, so a token planted there is scanned for like a report's.
                m_exc = re.search(r"^seed_exception = (.+)$", self.fixtures[name]["code"], re.M)
                if m_exc is not None and isinstance(ast.literal_eval(m_exc.group(1)), str):
                    report_text += "\n" + ast.literal_eval(m_exc.group(1))
                planted = _leak_hits(report_text)
                self.assertTrue(planted, f"{name}: its report carries no planted token, "
                                         f"so the scan would be vacuous for it")
                planted_anywhere.update(planted)
                out = self._run(name)
                self.assertEqual(_leak_hits(out), [],
                                 f"{name}: planted disclosure token(s) in stdout\n{out}")
        self.assertEqual(sorted(planted_anywhere), sorted(CPS_LEAK_TOKENS),
                         "a leak token is scanned for but planted in no fixture report")

    def test_cps_leak_scanner_negative_control(self):
        """The scanner must be able to fail, or the scan above proves nothing.

        Synthetic strings exercise each matching rule; then a real captured
        stdout, clean on its own, is shown to be caught once a single planted
        count is spliced into one line in the fences' own `,`-grouped format.
        """
        self.assertEqual(_leak_hits("[FAIL] x: level 'ZQXRARELABEL' carries 4,441"),
                         ["ZQXRARELABEL", "4441"])
        self.assertEqual(_leak_hits("[PASS] x: example QZ-8417 kept"), ["QZ-8417"])
        self.assertEqual(_leak_hits("cells 2221 2220 2280 2279; Z=673"),
                         ["2221", "2220", "2280", "2279", "673"])
        # Digit boundaries: longer numbers that merely contain a token are clean,
        # and so is the aggregate shape every CPS count line has.
        self.assertEqual(_leak_hits("14441 44410 6730 16731 9,000 rows, threshold 1,000"), [])
        self.assertEqual(_leak_hits(_CPS_ALL_PASS_12), [])
        out = self._run("cps_intake_q4c_identifier_allowlist_control")
        self.assertEqual(_leak_hits(out), [])
        spliced = out.replace("[PASS] category_counts_le_rowcount:",
                              "[PASS] category_counts_le_rowcount: max level 4,559;", 1)
        self.assertNotEqual(spliced, out, "splice target line changed; re-pick it")
        self.assertEqual(_leak_hits(spliced), ["4559"])

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
        # Registered before the fixtures are built: unittest skips tearDownClass when
        # setUpClass raises, so a failing build would otherwise leave its scratch behind.
        cls.addClassCleanup(_drop_scratch, cls.scratch)
        cls.report_fixtures = _report_fixtures(cls.scratch) if HAS_POLARS else None
        runners = []
        for name, spec in R_FIXTURES.items():
            block_path = cls.scratch / f"block_{name}.R"
            src = _r_block_source(spec["block"])
            if spec.get("config") is not None:
                src = _set_cps_config(src, spec["config"](cls.report_fixtures), lang="r")
            block_path.write_text(src + "\n")
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
        # Captured as raw bytes and split on b"\n" only: the parity test compares R's
        # bytes with Python's, so no lossy decode (and no universal-newline rewrite)
        # may sit in between. `outputs` is the same capture decoded losslessly
        # (surrogateescape keeps any invalid byte recoverable) for the str-based checks.
        proc = subprocess.run([RSCRIPT, str(driver)] + [str(r) for r in runners],
                              capture_output=True, timeout=300)
        cls.proc = proc
        cls.stdout_text = proc.stdout.decode("utf-8", "surrogateescape")
        cls.stderr_text = proc.stderr.decode("utf-8", "replace")
        cls.raw_outputs = {}
        current = None
        buf = []
        for line in proc.stdout.split(b"\n"):
            begin = re.match(rb"^### FIXTURE (\S+) BEGIN$", line)
            end = re.match(rb"^### FIXTURE (\S+) END$", line)
            if begin:
                current, buf = begin.group(1).decode("ascii"), []
                continue
            if end:
                cls.raw_outputs[end.group(1).decode("ascii")] = b"\n".join(buf)
                current = None
                continue
            if current is not None:
                buf.append(line)
        cls.outputs = {k: v.decode("utf-8", "surrogateescape")
                       for k, v in cls.raw_outputs.items()}

    def _check(self, name):
        spec = R_FIXTURES[name]
        self.assertIn(name, self.outputs,
                      f"{name}: no captured output. stderr:\n{self.stderr_text}")
        out = self.outputs[name]
        for line in out.split("\n"):
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
                          f"{name}: stop message is not the block's halt message\n{out}")
        if spec.get("stop_message") is not None:
            # Exact: the block's own halt is the only permitted stop, so an R-level
            # error surfacing through tryCatch reads as a different message.
            stops = [ln for ln in out.split("\n") if ln.startswith("### STOPPED:")]
            self.assertEqual(stops, [f"### STOPPED: {spec['stop_message']}"],
                             f"{name}: expected only the block's own stop\n{out}")
        _assert_line_expectations(self, name, spec, out)
        return out

    def test_r_driver_ran(self):
        self.assertEqual(self.proc.returncode, 0, self.stderr_text)
        self.assertNotIn("### RUNNER ERROR", self.stdout_text)
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

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_intake_control(self):
        self._check("r_cps_intake_control")

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_intake_subthreshold_count(self):
        self._check("r_cps_intake_subthreshold_count")

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_gen_control(self):
        self._check("r_cps_gen_control")

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_gen_unreleased_level(self):
        self._check("r_cps_gen_unreleased_level")

    # -- CPS regression rows, R mirrors (CPS_REGRESSION_CASES) -------------

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_intake_q3a_collapsed_all_null(self):
        self._check("r_cps_intake_q3a_collapsed_all_null")

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_intake_q3b_collapsed_visible(self):
        self._check("r_cps_intake_q3b_collapsed_visible")

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_intake_q4a_identifier_example(self):
        """R path of the identifier `example` row: the allow-list and the scalar
        value-key rule both FAIL, and the JSON path is the real one."""
        self._check("r_cps_intake_q4a_identifier_example")

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_intake_q4b_identifier_withheld(self):
        self._check("r_cps_intake_q4b_identifier_withheld")

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_intake_q4c_identifier_allowlist_control(self):
        self._check("r_cps_intake_q4c_identifier_allowlist_control")

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_intake_q4d_null_sibling_path(self):
        """The R walker used to push a NULL with `[[<-`, which appends nothing, so
        its node stack fell out of step with its path list and the FAIL named the
        wrong JSON path (fixed 2026-09-24)."""
        self._check("r_cps_intake_q4d_null_sibling_path")

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_intake_q4e_null_in_long_list(self):
        """The R fence used to treat a null-bearing list as non-scalar, exempting
        an over-long value list from rule (2)."""
        self._check("r_cps_intake_q4e_null_in_long_list")

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_intake_q5_unrecognized_key(self):
        self._check("r_cps_intake_q5_unrecognized_key")

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_intake_q6_empty_reason_declarable(self):
        self._check("r_cps_intake_q6_empty_reason_declarable")

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_intake_q6b_empty_reason_non_declarable(self):
        self._check("r_cps_intake_q6b_empty_reason_non_declarable")

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_intake_leak_subthreshold(self):
        self._check("r_cps_intake_leak_subthreshold")

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_gen_q1_matrix_dimension_mismatch(self):
        """A short correlation matrix used to abort the R block with 'subscript out of bounds'."""
        self._check("r_cps_gen_q1_matrix_dimension_mismatch")

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_gen_q2_unrecognized_percentile_key(self):
        """A `median` percentile key used to degrade to a [NOT VERIFIED] blaming an NA quantile."""
        self._check("r_cps_gen_q2_unrecognized_percentile_key")

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_gen_q5_unrecognized_key(self):
        self._check("r_cps_gen_q5_unrecognized_key")

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_gen_q6_empty_reason_declarable(self):
        self._check("r_cps_gen_q6_empty_reason_declarable")

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_gen_q6b_empty_reason_non_declarable(self):
        self._check("r_cps_gen_q6b_empty_reason_non_declarable")

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_r_cps_whole_stdout_leak_scan(self):
        """R side: the same whole-stdout scan over every R CPS fixture's
        captured output (including the stop() text), with the same non-vacuity
        guards — each fixture's report carries a planted token, and every token is
        planted somewhere."""
        cps = sorted(n for n in R_FIXTURES if n.startswith("r_cps_"))
        self.assertGreaterEqual(len(cps), CPS_MIN_FIXTURES, cps)
        planted_anywhere = set()
        for name in cps:
            with self.subTest(fixture=name):
                cfg = R_FIXTURES[name]["config"](self.report_fixtures)
                report_text = Path(cfg["report_path"].strip('"')).read_text(encoding="utf-8")
                # Same rule as the Python scan: a seed_exception pointer counts as planted.
                if cfg.get("seed_exception", "NULL") != "NULL":
                    report_text += "\n" + json.loads(cfg["seed_exception"])
                planted = _leak_hits(report_text)
                self.assertTrue(planted, f"{name}: its report carries no planted token, "
                                         f"so the scan would be vacuous for it")
                planted_anywhere.update(planted)
                out = self._check(name)
                self.assertEqual(_leak_hits(out), [],
                                 f"{name}: planted disclosure token(s) in stdout\n{out}")
        self.assertEqual(sorted(planted_anywhere), sorted(CPS_LEAK_TOKENS),
                         "a leak token is scanned for but planted in no fixture report")

    # -- Python and R print byte-identical outcome lines -------------------

    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test_cps_py_r_outcome_lines_byte_identical(self):
        """For every CPS fixture that has an `r_` twin, the Python and R
        blocks print the same outcome lines, byte for byte, in the same order.

        Outcome lines are the per-check lines (`[...]`), the count line and the
        verdict line — banners and separators are excluded (R's `cat(strrep(...),
        "\\n")` legitimately ends its rule with a space). The Python fixtures are
        rebuilt here in a scratch of their own; `_report_fixtures()` is
        deterministic (seeded) and no outcome line carries a path, so the two runs
        see identical report content. A mismatch prints a unified diff per fixture.

        The comparison is on raw bytes. R's stdout is captured undecoded; Python's
        captured text is encoded with `surrogatepass`, so a lone surrogate that
        slipped past the escape table becomes bytes that no R output can equal,
        rather than being replaced or dropped by a lossy decode. Two guards ride
        along on every paired fixture: Python's stdout must encode as strict UTF-8 (a
        real run writes to a console or log that cannot hold a lone surrogate), and
        neither language may print a C0/C1 control character other than "\\n" or
        U+2028/U+2029 — each of those must reach stdout as `\\uXXXX`.
        """
        scratch = _new_scratch()
        try:
            py_fx = _py_fixtures(scratch)
            paired = sorted(n for n in py_fx
                            if n.startswith("cps_") and "r_" + n in R_FIXTURES)
            unpaired = sorted(n for n in py_fx
                              if n.startswith("cps_") and "r_" + n not in R_FIXTURES)
            self.assertEqual(unpaired, [], "CPS fixtures with no R twin (list them "
                                           "here only if they legitimately differ)")
            self.assertGreaterEqual(len(paired), CPS_MIN_FIXTURES, paired)
            diffs, unencodable, raw_controls = [], [], []
            for name in paired:
                py_out = _exec_py_fixture(py_fx[name])[0]
                try:
                    py_out.encode("utf-8")
                except UnicodeEncodeError as exc:
                    unencodable.append(f"{name}: {exc}")
                py_raw = py_out.encode("utf-8", "surrogatepass")
                r_raw = self.raw_outputs.get("r_" + name, b"")
                for lang, text in (("python", py_out), ("r", self.outputs.get("r_" + name, ""))):
                    hits = _CPS_RAW_CONTROL_RE.findall(text)
                    if hits:
                        raw_controls.append(f"{lang}:{name}: {sorted(set(hits))!r}")
                py_lines = _cps_outcome_lines_bytes(py_raw)
                r_lines = _cps_outcome_lines_bytes(r_raw)
                if py_lines != r_lines:
                    diffs.append("\n".join(difflib.unified_diff(
                        [ln.decode("utf-8", "backslashreplace") for ln in py_lines],
                        [ln.decode("utf-8", "backslashreplace") for ln in r_lines],
                        fromfile=f"python:{name}", tofile=f"r:r_{name}", lineterm="")))
            self.assertEqual(unencodable, [], "Python stdout is not strict UTF-8")
            self.assertEqual(raw_controls, [], "a raw control / line-separator character "
                                               "reached stdout unescaped")
            self.assertEqual(diffs, [], "Py/R outcome lines differ:\n" + "\n\n".join(diffs))
        finally:
            _drop_scratch(scratch)


# C0 controls except "\n", DEL, C1 controls, and the two Unicode line/paragraph
# separators: every one of them must reach a CPS stdout as `\uXXXX`, never raw.
_CPS_RAW_CONTROL_RE = re.compile("[\x00-\x09\x0b-\x1f\x7f-\x9f  ]")
_VERDICT_LINE_RE_B = re.compile(rb"^[A-Z][A-Z0-9 -]* VALIDATION: (PASSED|PASSED WITH WARNINGS|FAILED)$")


def _cps_outcome_lines(out):
    """Per-check, count and verdict lines of one CPS run (right-stripped; split on
    "\\n" only, for the reason given in `_assert_line_expectations`)."""
    lines = [ln.rstrip() for ln in out.split("\n")]
    return [ln for ln in lines
            if ln.startswith("[") or ln.startswith("Checks:") or _VERDICT_LINE_RE.match(ln)]


def _cps_outcome_lines_bytes(raw):
    """`_cps_outcome_lines` over raw stdout bytes — the parity test's form."""
    lines = [ln.rstrip() for ln in raw.split(b"\n")]
    return [ln for ln in lines
            if ln.startswith(b"[") or ln.startswith(b"Checks:") or _VERDICT_LINE_RE_B.match(ln)]


def _exec_py_fixture(spec):
    """Run one Python fixture's code; return (stdout, halting ValueError text or None)."""
    ns = dict(spec["ns"])
    ns.setdefault("pl", pl)
    buf = io.StringIO()
    raised = None
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(spec["code"], "<fixture>", "exec"), ns)
    except ValueError as exc:
        raised = str(exc)
    return buf.getvalue(), raised


# --------------------------------------------------------------------------
# Generated tests for the CPS_REGRESSION_CASES rows that have no hand-written
# test method. Each row becomes `test_<name>` on
# PythonFixtureTests and `test_r_<name>` on RFixtureTests, with the row's `doc`
# as its docstring, so every row is a named, individually reported test in both
# languages and adding a row can never silently add an untested fixture.
# --------------------------------------------------------------------------

def _make_py_case_test(name, doc):
    def test(self):
        self._run(name)       # assertions live in the runner; return None
    test.__name__ = "test_" + name
    test.__doc__ = doc
    return test


def _make_r_case_test(r_name, doc):
    @unittest.skipUnless(HAS_POLARS, "polars builds the CPS report/parquet fixtures")
    def test(self):
        self._check(r_name)   # assertions live in the runner; return None
    test.__name__ = "test_" + r_name
    test.__doc__ = doc
    return test


for _case_name, _case in CPS_REGRESSION_CASES.items():
    if not hasattr(PythonFixtureTests, "test_" + _case_name):
        setattr(PythonFixtureTests, "test_" + _case_name,
                _make_py_case_test(_case_name, _case.get("doc")))
    if not hasattr(RFixtureTests, "test_r_" + _case_name):
        setattr(RFixtureTests, "test_r_" + _case_name,
                _make_r_case_test("r_" + _case_name, _case.get("doc")))

# The hand-registered R twins added for the parity test (no table row).
for _r_name in ("r_cps_intake_non_declarable_declared", "r_cps_intake_missing_categorical_block",
                "r_cps_intake_tier2_no_correlations", "r_cps_gen_non_declarable_declared"):
    if _r_name in R_FIXTURES and not hasattr(RFixtureTests, "test_" + _r_name):
        setattr(RFixtureTests, "test_" + _r_name, _make_r_case_test(_r_name, None))

if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
