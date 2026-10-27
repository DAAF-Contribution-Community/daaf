# arXiv papers: the HTML lane

An arXiv paper that has an HTML rendering at the cited version can be read
and gate-checked from that HTML instead of the PDF (user decision D-21 N5,
2026-10-19: "Full grade, cite sections"). `pdf_ingest --source arxiv-html`
turns the LaTeXML page into **section units**, and `lit_verify card` checks a
`lit-verify-card-v2` card against them exactly as it checks a PDF card
against pages. Source of truth: the `§§ ARXIV_HTML` block of
`scripts/pdf_ingest.py` (added in 1.2.0-daaf; current 1.2.2-daaf,
`HTML_EXTRACT_VERSION = "arxiv-html-v1"`) and the "arXiv HTML ingests"
header block of `scripts/lit_verify.py` (added in 1.4.0-daaf; current
1.8.0-daaf). If this page and the code disagree, the code wins.

**Contents:** Which path · Detecting an arXiv paper · Fetching the HTML ·
Availability · Ingesting · Version pinning · Units and labels · Grades ·
No vision · Conversion errors · One paper key per source · Table rows ·
Sparse units · Measured on real papers · The LaTeX source

## Which path

| Situation | Path |
|-----------|------|
| arXiv paper, HTML exists at the version you cite | **HTML lane**: fetch `arxiv.org/html/{id}v{N}`, ingest with `--source arxiv-html`, write a v2 card cited by section |
| arXiv paper, no HTML at that version (404), or the ingest exits 12 | The PDF of the same version: `pdf_ingest` (default), a card cited by page |
| A claim must carry a page number (a manuscript `[@key, p. 7]`) | The PDF: HTML units have no page numbers |
| You need what a figure shows | The PDF with validated vision (HTML figures are not fetched, so vision is unavailable on HTML) |
| Not on arXiv | The PDF |

Both lanes earn the same grades (§ Grades). Pick one per paper and record
it: the card's `anchor_kind` names it.

## Detecting an arXiv paper

- The record's IDs from `scholarly-search` (`work`, `oa`: the arXiv leg is
  derived from the ID), a URL on `arxiv.org`, or an ID the user gives.
- When scanning text for an ID, require the `arXiv` prefix
  (`arXiv:2310.08726`). A bare `NNNN.NNNNN` pattern matches many unrelated
  numbers; the source skill's analyzer regex had an optional prefix and
  matched them (note 10 § 1) [inf].
- Note the **version** you are citing (`v1`, `v4`). The record or the abs
  page lists the versions; cite the one you read.

## Fetching the HTML (retrieval contexts only)

Readers never fetch: a reader that needs the HTML hands the need back to the
orchestrator. A retrieval context fetches the **versioned** URL through the
`web-retrieval` skill (built-in WebFetch is blocked):

```
bash /daaf/scripts/web_fetch.sh https://arxiv.org/html/{id}v{N} {PROJECT_DIR}/web_fetches/arxiv_html/
```

- Exit 0 saves the raw `.html`, an extract `.md` and a MANIFEST row. The raw
  `.html` is what `pdf_ingest` reads; the row is its provenance (`final_url`,
  `raw_sha256`).
- Use `https://arxiv.org/html/{id}v{N}`, never ar5iv and never an
  unversioned URL. On 2026-10-19 `https://ar5iv.labs.arxiv.org/html/2310.08726`
  returned HTTP 200 with `final_url` `https://arxiv.org/abs/2310.08726`: the
  abs page, not the paper (web_fetch exit 0) [obs:
  `web_fetches/s3_bakeoff_arxiv_html/MANIFEST.jsonl` row 2]. `pdf_ingest`
  refuses such a file (exit 12), but the fetch itself looks like a success.

## Availability

Not every arXiv paper has HTML. arXiv converts LaTeX submissions with
LaTeXML; some papers have none, and older ones may never have been
converted. `https://arxiv.org/html/2310.08726` and `…/2310.08726v1` both
returned **404** (web_fetch exit 5) on 2026-10-19 [obs: same MANIFEST, rows
1 and 3]. A 404 means: use the PDF of the same version. The three B1 papers
(2504.04906v4, 2403.00922v1, 2403.05420v1) all had HTML [obs:
`web_fetches/s3_arxiv_html_candidates/MANIFEST.jsonl`].

## Ingesting

```
bash /daaf/scripts/pdf_ingest.sh <HTML_PATH> {PROJECT_DIR}/papers/ --paper-key KEY \
     --source arxiv-html [--max-pages N] [--max-bytes N] [--reingest]
```

- `HTML_PATH` is the raw `.html` web_fetch saved (keep it in its
  `web_fetches/` folder, beside the MANIFEST that proves where it came from).
  `lit_verify` 1.7.0 re-extracts the units from that file at every check
  (`evidence-card.md` § Re-derivation): moved or deleted, it is
  `SOURCE_MISSING` (fail).
- `--render` and `--ocr` are refused with `--source arxiv-html` (exit 1):
  there are no page images. `--max-pages` caps the **unit** count.
- Running the default PDF path on an HTML file exits 8 with the hint
  "an arXiv HTML file? use --source arxiv-html".
- poppler is not needed on this path; polars is (exit 10 without it).
- Exit 12 refuses a file that is not a version-pinned LaTeXML article: not
  UTF-8; no `<article class="ltx_document">` (an ar5iv or unversioned URL that
  landed on the abs page); no `arXiv:IDvN` watermark; or a watermark whose ID
  or version contradicts the web_fetch `final_url`. Fix: fetch
  `https://arxiv.org/html/{id}v{N}`, or use the PDF.

Artifacts (`pdf-ingest.md` § arXiv HTML mode has the full list):
`anchor{S}/uNNN.txt` (the unit text the gate matches), `pages{S}/uNNN.txt`
(fenced reading copies, **for you**), `rows{S}/uNNN.txt` (a unit's table
rows), `fulltext{S}.md` with one marker per unit
(`<!-- unit N/TOTAL section=LABEL id=ID anchor_sha256=… -->` plus a flags
line), `page_index{S}.parquet` (one row per unit) and
`ingest_manifest{S}.json` (`anchor_kind: "arxiv_html"`).

## Version pinning

The ingest records the arXiv ID and version from the page's watermark
(`<div id="watermark-tr">arXiv:2504.04906v4 [stat.ME] …`): manifest
`arxiv.id`, `arxiv.version`, `arxiv.id_version`, `watermark`, `category`,
`date`, `license_text`. With web_fetch provenance, the watermark must agree
with the fetched URL's ID and (when the URL names one) version, else exit 12.
The card repeats the version as `source_version` (`"v4"`); `lit_verify`
fails the card with `SOURCE_VERSION_MISMATCH` when it differs. A new arXiv
version is a new source: fetch it, ingest it under its own key, and write a
new card.

## Units and labels

- **Units.** Only the text inside the LaTeXML `<article>` is read (the arXiv
  banner, sidebar TOC and footer are dropped). Unit `front` is the article's
  own text outside every section (title, authors, abstract); then each
  section-class element (`ltx_part`, `ltx_chapter`, `ltx_section`,
  `ltx_subsection`, `ltx_subsubsection`, `ltx_appendix`, `ltx_index`) is its
  own unit holding **its own** text in document order; the bibliography
  (`ltx_bibliography`) is its own unit. A run-in `ltx_paragraph` stays in
  its parent unit. A section's text after its last subsection stays in the
  section's unit.
- **Text rules (`arxiv-html-v1`).** Whitespace collapsed as a browser does;
  block elements end a line; math becomes its TeX `alttext` (else its
  `application/x-tex` annotation); each `ltx_tabular` row is one line with
  cells joined by a tab; captions stay in place; footnote text moves to the
  end of its unit (its mark stays in the text); navigation, scripts, images
  and form controls are skipped. NORMALIZE folds the tab to a space, so a
  quote copied from `pages/` matches.
- **Labels** come from the heading tags: `3.2`, `A.1`, `S4.1`, thesis
  `1.3.1`. A tag without a dot under a numbered parent is relative and is
  composed with the parent's number (a thesis prints "1 " for section
  1.3.1). No usable tag: the LaTeXML id (`S1.SSx1`, `bib`), recorded as a
  **label fallback** in the manifest's `label_fallbacks`. Labels are unique:
  two units that derive the same number fall back to their ids, and any clash
  left gets `#2`, `#3` (`label_source` ends in `_dedup`).
- **Cite by the label exactly as printed** in `ingest_manifest.units[].label`
  or the fulltext marker `section=…`. A label the ingest does not have is
  `SECTION_NOT_FOUND` (fail): copy it, do not reconstruct it from the
  paper's printed numbering, which can differ (a fallback id, a `#2`
  suffix, a composed thesis number).

## Grades

Same grades as a PDF (D-21 N5): PASS → `FULL_TEXT_VERIFIED`, PARTIAL →
`FULL_TEXT_PARTIAL`, under the same ladder, identifying-quote rule, coverage
rule, quote-number rule (`ladder-v3`) and number rules (`numbers-v6`;
`evidence-card.md`). Only the locator changes: a
section label in place of a page, `section_end` in place of `page_end` (a
quote may run from one unit into the **next** unit only), `WRONG_SECTION`
in place of `WRONG_PAGE`, `MISSING_SECTION` in place of `MISSING_PAGE`.
Downstream, the claim's locator is the section (`§3.2`), the source is
"arXiv HTML vN" (spec §9.2 `locator`).

## No vision

HTML units have no page images (figures are not fetched), so the card
writes `vision_mode: "off"` (or `vision_validated: false`) and every claim
`source: "text"`; anything else is exit 8. The manifest says
`vision.available: false`. What a figure shows can only come from its
caption on this lane; for the figure itself use the PDF with validated
vision.

## Conversion errors

LaTeXML marks a macro it could not convert with an `ltx_ERROR` span. The
unit is flagged `conversion_error` (manifest `conversion_error_units`,
`conversion_error_count`), and its text there may differ from the paper. The
cap is **whole unit, claims only** (orchestrator default within D-21 N5): a
claim quote that passes in a flagged unit is `PASS_CONVERSION_ERROR` and its
numbers `NUMBER_CONVERSION_ERROR` (`conversion-error`), both partial, so the
card is at best PARTIAL. Coverage anchors there do not cap. To keep
`FULL_TEXT_VERIFIED`, cite the claim from another unit that states it, or
read that paper from the PDF; otherwise accept PARTIAL.

## One paper key per source

A paper key holds one source kind (orchestrator default within D-21 N5).
A paper read from its HTML has the HTML as its source and its card cites
sections. A PDF ingest of the same work gets **its own key**, for
comparison only. If one key's complete ingests mix `pdf` and `arxiv_html`,
every card on it fails with `MIXED_ANCHOR_KINDS`; a card whose `anchor_kind`
differs from the ingest fails with `ANCHOR_KIND_MISMATCH` and nothing else is
checked.

## Table rows

`rows{S}/uNNN.txt` holds a unit's `ltx_tabular` rows, one row per line,
cells tab-separated. It is the HTML row source of the unique-row path
(`numbers-v3`, with the `numbers-v4`/`-v5` guards; the role lane B plays on
a PDF page), hash-checked (`TABLE_ROWS_HASH_MISMATCH`, fail) and re-derived
from the stored HTML (`ROW_SOURCE_REDERIVE_MISMATCH`, fail); a file that
fails either is not used. The HTML
anchor is already row-major, so the simplest table claim quotes from the row
label through the cell and clears in-quote; a quote that starts at the row
label and stops short of the cell clears through the row. Numeric rows are
often too short to be identifying on their own (§ Measured on real
papers): extend the quote with the caption or header line before the row. Quote from
`pages/uNNN.txt`, not from `rows/`: the rows are anchor text too, but the
reading copy is the fenced, scrubbed copy written for you.

## Sparse units

A unit with fewer than 200 non-whitespace characters is flagged `sparse`
(`SPARSE_UNIT_MAX_CHARS`): mostly heading-only units (a chapter or section
whose text sits in its subsections). It still needs a coverage entry; a
short exact anchor such as its heading covers it (`COVERED_SPARSE`, no cap).
No unit is ever "scanned".

## Measured on real papers

FE-5f, 2026-10-22, on the three B1 ingests (2504.04906v4, 40 units;
2403.00922v1, 43; 2403.05420v1, a thesis, 43) and their same-version PDFs
ingested under their own keys [obs: workspace
`bakeoff/arxiv/2026-10-22_arxiv_html_measurements.md`, script 86 log]:

| Measure | Result |
|---------|--------|
| Genuine 40-char / 6-word spans (560) | PASS 0.945, PASS_SKELETON 0.002, NON_IDENTIFYING 0.054 (PDF bake-off: 3–11% non-identifying) |
| Planted fabrications (540: one-word swap, adjacent section, another paper's quote) | **0 passed** (NOT_FOUND, WRONG_SECTION) |
| Quotes running into the next unit (121) | PASS_SPAN with `section_end`; WRONG_SECTION (or NEAR) without |
| Table numbers from `rows/` (87, two papers), quote from the row label through the cell | genuine ok 1.000 (all in-quote; the row path never fired), last digit changed 0.093, sign flipped 0 |
| Table row quotes not identifying, even as the whole row | 58 of 86 on 2403.00922v1 |
| Sparse units / label fallbacks | 12–25% / 2–16% of units |
| Conversion errors | 1 unit (`front` of 2403.05420v1); 5 of 186 sampled quotes fell in it |
| Genuine end-to-end v2 cards | PASS, `FULL_TEXT_VERIFIED` on all three; the thesis PARTIAL only when a claim cites `front` |
| HTML labels vs the PDF's printed numbers | 2504.04906v4: 27 match, none differ; the thesis: **every chapter one lower in HTML** (`0`, `0.1` … `5` = PDF `1`, `1.1` … `6`) |
| Genuine HTML quotes that also pass against the PDF anchor | 0.54–0.67 (TeX math versus glyphs, hyphenation, ligatures) |

What this means for a reader:
- **Section numbers can differ from the PDF's.** Cite the HTML label (the
  gate checks it) and, where it matters downstream, say the numbering is
  the HTML's ("§0.1 of arXiv HTML v1"). User decision D-23 (2026-10-23): the
  HTML label stays the locator and the HTML lane is the default ("focus on
  having the HTML default").
- **Table rows are often too short to identify.** Quote the row together
  with the table caption or the header line before it, all copied from
  `pages/uNNN.txt` in order, until the quote is identifying.
- **A whole-row quote lets a wrong column through** (the same-row
  residual, as on PDF): name the column in the claim text and keep the
  quote as close to the cell as the identifying rule allows. Since
  `lit_verify` 1.5.0 (D-23) such a number carries the label
  `column-not-checked` (`evidence-card.md` § Numbers, the column label).
- **Quotes do not move between renderings**: a quote copied from the HTML
  often fails against the PDF and the reverse, one more reason a paper key
  holds one source.

## The LaTeX source

`https://arxiv.org/e-print/{arxiv_id}` returns the source archive (source
skill). `web_fetch.sh` saves it raw (exit 8, not extractable). Unpacking an
archive is a separate, deliberate step (a captured script; no extraction into
`/tmp`). Use it only when exact equations matter; the gate does not read it.
