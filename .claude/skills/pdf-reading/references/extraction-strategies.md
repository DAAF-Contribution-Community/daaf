# Extraction strategies and reading quality

How to read each kind of page so the evidence card stays anchorable, how to
use the secondary readings (lane B, OCR, renders) without letting them
overwrite the anchor, and how to judge and log reading quality. Adapted from
the user's source skill (`research/2026-10-02_FrameworkDev_ScholarlySearch/pdf-reading/references/extraction-strategies.md`
and `quality-rubrics.md`) per preliminary note 10 § 1: PyMuPDF, Gemini,
LlamaParse and in-skill subagent dispatch are dropped; the "authority
hierarchy" that let vision replace text is rewritten as the reconciliation
rule below.

**Contents:** The reconciliation rule · Page types · Vision prompts ·
Figure descriptions · Reading-quality rubric · Re-read triggers ·
Discrepancy log

## The reconciliation rule

DAAF never merges two readings into one text. Each reading keeps its lane:

| Reading | Lane | May it be quoted? |
|---------|------|-------------------|
| Anchor (`pdftotext`, via `pages/`) | text | Yes: the only text a `PASS` quote comes from |
| Lane B (pypdfium2) | — | No; it only scores agreement. If it reads a passage the anchor garbles, log it and quote nothing from lane B |
| OCR (Tesseract, `pages/pNNN_ocr.txt`) | ocr | Yes, as `source: "ocr"` (`PASS_OCR`, weaker; caps the card at PARTIAL) |
| Vision (renders, when validated) | vision | As `source: "vision"` (no quote, numbers `vision-only`) or `both` (a text quote plus vision corroboration) |

When two readings disagree, record both in the card's text/vision
discrepancy log with the page, what each lane shows, and which one the claim
relies on. Never pick one silently (spec §7.3). The user's source skill said
"prefer vision" for conflicts; DAAF's rule replaces that (user decision D-20
item 4).

## Page types

| Page type | Signal | How to read |
|-----------|--------|-------------|
| Two-column body text | Normal flags; sometimes `low_agreement` | The anchor (`pdftotext` default mode) usually keeps column order. Quote within a column. A sentence that crosses a column break is fine on one page; one that crosses a page break needs `page_end`. `low_agreement` on a clean page is often lane B ordering columns differently (`fuzz.ratio` is order-sensitive), not an error: read the page and decide |
| Fused compound hyphens | Quote "natural-language" vs anchor "naturallanguage" | Quote the page as printed; SKELETON matching absorbs it (`PASS_SKELETON`). Never "correct" the anchor |
| Small caps | "I NLINE S EARCH" in the anchor | SKELETON absorbs the split; quote the visible words |
| Ligatures and DTP exports (InDesign, Pages) | `garbled`, `(cid:` evidence, or words like "defned" | NFKC folds U+FB00–FB04 ligatures. Where a glyph is unmapped, the anchor lacks the text: quote a nearby clean sentence, or use vision when validated; log the garbling. The source skill's benchmark: PyMuPDF turned "defined" into "defned" on an InDesign export |
| Tables (ruled) | `table` via `find_tables`, `numeric` | Numbers come from the anchor text of that page, as printed. `-layout` would keep the grid but interleave columns, so the anchor (default mode) can list cells in an unusual order: match numbers, not row layout. Use the 300-DPI crop when vision is validated |
| Tables (borderless, booktabs) | Caption-only `table`, often `numeric` | `find_tables` (`lines` strategy) misses them. Read the anchor; check that the row and column you attribute a number to are right (`table_ref`); a validated vision reading is the main help here |
| Equations | Unicode symbols in the anchor | Quote prose around an equation, not the equation; describe the equation in a summary field. For LaTeX fidelity on arXiv papers see `arxiv-and-html.md` |
| Figures | `figure` (caption or image ≥ 5%) | Text in a figure is usually not in the anchor. Quote the caption; numbers read off a chart are `vision-only` at best and are never effect sizes |
| Sparse pages | `scanned` without a large image (a figure page with a caption) | A short exact anchor covers it (`COVERED_SPARSE`, no cap) |
| Truly scanned pages | `scanned` + one image ≥ 50% of the page, `ocr` | Read `pages/pNNN_ocr.txt`; quotes are `source: "ocr"`. The card is capped at PARTIAL. With empty OCR and no validated vision the page cannot be covered: report it |
| Scans with an existing OCR layer | `ocr_layer_suspected` | Both lanes read the same, possibly noisy, OCR layer, so agreement looks fine. Check suspicious words and numbers; vision when validated |
| Rotated pages | `rotated` | The anchor still holds the text. Renders honor `/Rotate`; crops are skipped on such pages. Models misread rotated images more often, so treat vision there with extra care |
| CJK text | `cjk_risk` | poppler-data is not installed, so glyphs may be dropped or mis-mapped. Say so in the card; do not quote CJK text the anchor lacks |
| Running headers and footers | `header_footer` in the manifest | They stay in the anchor; do not use them as anchors (they are not unique) |

## Vision prompts (only with validated vision)

Kept from the source skill's verified prompt patterns, adapted:
- **Transcribe verbatim**: "do not paraphrase, summarize or invent; mark an
  unreadable cell as unreadable".
- **Tables as TSV** with the row and column labels as printed, the minus sign
  as printed, parentheses kept, stars kept.
- **"Transcribe every cell; do not stop early."** Early stopping is the main
  failure mode on long tables.
- Compare with the anchor text of the same page and log every difference.

## Figure descriptions

The source skill's structured figure description (Type, Components, Layout,
Key relationships, Annotations, Trends, Significance, Visual notes) is useful
reader prose. Keep it in the card's prose sections, labeled as the reader's
description, never inside a `quote`. "Significance" is interpretation and
belongs with reader-assessed content (spec §7.6 keeps author-stated and
reader-assessed material apart).

## Reading-quality rubric

Use it to judge a reading before writing claims, and in a spot-check audit.

| Severity | Definition | Action |
|----------|-----------|--------|
| CRITICAL | A page with no usable anchor text that is not flagged; column order wrong across a passage you rely on; a number attributed to the wrong cell | Re-read the page; use OCR or validated vision; if still unresolved, exclude the claim and log it |
| MODERATE | A table missing headers in the anchor, a figure with no caption text, garbled symbols in a quoted passage | Re-read with the crop (validated vision) or quote elsewhere; log it |
| LOW | Extra whitespace, hyphenation, running headers in the text | Note only |

Spot-check scoring (per page, rendered page against the anchor):

| Aspect | HIGH | MEDIUM | LOW |
|--------|------|--------|-----|
| Text | All text, right order, no garbling | Minor omissions (headers, page numbers) | Missing paragraphs, wrong column order, garbling |
| Tables | Every row and column, labels right | Structure right, a cell or alignment wrong | Rows or columns missing, structure broken |
| Numbers | Every claimed number found as printed | Precision or formatting differences only | A changed digit or sign |

There is no "skip review" option: the source skill's `review: false` for
batches conflicts with DAAF's rigor rules and was dropped. Every card goes
through `lit_verify card`; the Literature Review mode adds a claim spot-check
audit on a sample (spec §12).

## Re-read triggers

| Condition | Threshold | Response |
|-----------|-----------|----------|
| Missing text on a page | More than a paragraph | OCR text or validated vision for that page; log |
| Wrong reading order | More than 2 sentences out of order in a passage you quote | Quote within one column; log |
| Broken table | A column missing or more than 3 cells uncertain | Crop plus validated vision, or no numeric claims from that table |
| `low_agreement`, `garbled` or `ocr_layer_suspected` on a page you quote | Any | Read the page closely before quoting; log what you saw |
| A whole chunk reads poorly | More than half its pages LOW | Report to the orchestrator before writing claims |

## Discrepancy log

One row per disagreement, in the card's "Text/vision discrepancies log"
section:

| Page | Item | Anchor text says | Other lane says (lane) | Claim relies on | Note |
|------|------|------------------|------------------------|-----------------|------|
| 7 | Table 2, row "Boys", col (3) | `0.12` | `0.17` (vision) | anchor | The render is blurry at 8 pt; flagged for human check |

A discrepancy is information for the reviewer, not a failure. An unlogged one
is.
