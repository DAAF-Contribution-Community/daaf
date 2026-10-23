# The evidence card and the `lit_verify card` gate

How to write an evidence card that `scripts/lit_verify.sh card` can verify,
what every check and status means, and how to fix a failing card. Source of
truth: the header, `validate_card()`, `check_card()` and the selftest in
`scripts/lit_verify.py` (`TOOL_VERSION = "1.4.0-daaf"`, 2026-10-22; card
schemas `lit-verify-card-v1` and `lit-verify-card-v2`, result schema
`lit-verify-card-check-v2`) and the ladder and number rules in
`scripts/pdf_text_common.py` (`ladder-v1`, `numbers-v3`). A later session
adds `lit_verify report` (S4); the full card schema is formalized later in
`LIT_REVIEW_OUTPUT_CONTRACT.md` (spec C14). If this page and the code
disagree, the code wins.

**Contents:** Syntax · Card anatomy · Front matter · The lit-verify block ·
Card schema v2 and section locators · Checks in order · The match ladder ·
Identifying quotes · Page classes · Coverage statuses · Numbers · Vision
consistency · arXiv HTML statuses · Verdicts and grades · card_check JSON ·
MANIFEST row · Exit codes · Fixing a failing card · Selftest · Worked
examples

## Syntax

```
bash /daaf/scripts/lit_verify.sh card <PAPER_DIR> <CARD_PATH> [--ingest-suffix S]
bash /daaf/scripts/lit_verify.sh selftest <SCRATCH_DIR>
```

- `PAPER_DIR` = `papers/{paper_key}/` written by `pdf_ingest`. It and its
  parent (the papers dir, where MANIFEST.jsonl lives) must pass the
  destination guard; its basename must be a paper key.
- `CARD_PATH` must resolve to a file **directly inside** `PAPER_DIR`, at most
  5 MB, UTF-8. Name it `evidence_card.md`, then `evidence_card_a.md`,
  `evidence_card_b.md` for revisions.
- `--ingest-suffix` pins an ingest version (`''` or `_a`…`_z`); default: the
  latest complete ingest (the latest `ingest_manifest{S}.json`).
- No network calls, no model calls. It never reads the fenced reading copies
  (`pages/`, `fulltext.md`); it matches the byte-for-byte anchor.

## Card anatomy

`evidence_card{S}.md` = YAML front matter + free prose sections (spec §7.6:
coverage ledger, question and contribution, design and identification,
sample, measures, findings table, heterogeneity, limitations, appraisal,
open questions, relevance and directness, reader confidence, and the
**text/vision discrepancy log**) + **exactly one** fenced block whose info
string is `lit-verify` (three or more backticks or tildes), holding strict
JSON. The gate reads only that block. Zero blocks, two blocks, an unclosed
block, invalid JSON, duplicate keys, NaN/Infinity, unknown fields or wrong
types → exit 8. JSON allows no comments, so commentary goes in prose.

## Front matter

Free-form for the gate. Spec §7.6 lists `paper_key`, `doi`, `openalex_id`,
`citekey`, `title`, `authors`, `year`, `venue`, `evidence_grade`,
`source_pdf_sha256`, `extractors`, `vision_mode`, `reader_model`, `read_at`,
`review_type`. A v2 card writes `source_sha256` (in place of
`source_pdf_sha256`) and, on arXiv HTML, `source_version` (`v4`) and the
source as "arXiv HTML vN". This skill adds the vision-gating fields that the block does
**not** define (putting them in the block would be an unknown field, exit 8):

| Field | Value | Who sets it |
|-------|-------|-------------|
| `reader_model_source` | `self-report` | The reader. The orchestrator's audit result (`transcript-confirmed` or a mismatch) is recorded by the orchestrator outside the card, because editing a checked card breaks the SHA-256 its `card_check` records (`vision-validation.md` § Gating) |
| `reader_route` | One of the route names in `vision-validation.md` § Routes, as given in the dispatch | The reader, copying the dispatch |
| `vision` | `validated` or `unavailable` (the CLAUDE.md D-7 wording) | The reader, from the list check |

`lit_verify` does **not** check any front-matter field.

## The lit-verify block

| Field | Required | Rule |
|-------|----------|------|
| `schema_version` | yes | `"lit-verify-card-v1"`; anything else → exit 8 |
| `paper_key` | yes | Non-empty; must equal the PAPER_DIR basename (else `PAPER_KEY_MISMATCH`, a fail) |
| `source_pdf_sha256` | yes | 64 lowercase hex; must equal the ingest manifest's `source.sha256` (else `SOURCE_HASH_MISMATCH`) |
| `ingest_suffix` | no | `""` or `_a`…`_z`; a mismatch is only a warning (hashes decide integrity) |
| `reader_model` | yes | Non-empty string, recorded, not judged |
| `vision_mode` | yes | `auto`, `all-pages` or `off` |
| `vision_validated` | yes | JSON boolean |
| `vision_list_version` | yes | String or `null` (write the list version from SKILL.md) |
| `coverage` | yes | Array, one object per page: `page` (int ≥ 1), `anchors` (array of strings), `summary` (string), optional `sparse` (bool, advisory), optional `vision_only` (bool). A page listed twice → exit 8. A page absent from 1..N is a recorded fail (`MISSING_PAGE`), not a parse error |
| `claims` | yes | Array of objects: `claim_id` (unique, `[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}`), `page` (int), optional `page_end` (exactly `page + 1`), `quote` (string; `null` or empty only when `source` is `vision`), `numbers` (array of strings, as printed), `source` (`text`, `vision`, `both` or `ocr`), optional `table_ref` (string or null), optional `claim` (string) |

That is schema v1, which stays **PDF-only** and checks exactly as before.

## Card schema v2 and section locators (1.4.0, D-21 N5)

`lit-verify-card-v2` is accepted beside v1. It names the source kind, so one
schema covers both anchors. Use v2 for every arXiv HTML card; a v2 card with
`anchor_kind: "pdf"` checks exactly as the same v1 card.

| Field | `anchor_kind: "pdf"` | `anchor_kind: "arxiv_html"` | Rule |
|-------|----------------------|-----------------------------|------|
| `schema_version` | `"lit-verify-card-v2"` | same | — |
| `anchor_kind` | `"pdf"` | `"arxiv_html"` | Required; must equal the ingest manifest's `anchor_kind` (a manifest without the field is `pdf`), else `ANCHOR_KIND_MISMATCH` (fail; nothing else is checked) |
| `source_sha256` | required | required | 64 lowercase hex = the manifest's `source.sha256` (the raw HTML's hash on HTML). v1's `source_pdf_sha256` is an **unknown field** in v2 (exit 8) |
| `source_version` | absent or `null` (a value → exit 8) | **required**, `v` + digits (`"v4"`) | Must equal the manifest's `arxiv.version`, else `SOURCE_VERSION_MISMATCH` (fail) |
| `paper_key`, `ingest_suffix`, `reader_model`, `vision_mode`, `vision_validated`, `vision_list_version` | as v1 | as v1, but `vision_mode` `"off"` or `vision_validated` false (both declared available → exit 8) | — |
| `coverage` | per page, as v1 | one object per **section**: `section`, `anchors`, `summary`, optional `sparse`; `page` and `vision_only` are unknown fields; a section listed twice → exit 8 | — |
| `claims` | as v1 | `claim_id`, `section`, optional `section_end`, `quote` (non-empty string), `numbers`, `source` (`"text"` only, else exit 8), optional `table_ref`, `claim` | `section_end` must differ from `section` (exit 8) and be the **next** unit in document order, else `SECTION_END_NOT_NEXT` (fail; the quote is then checked in its section alone) |

**Section locators.** A `section` is a unit label exactly as `pdf_ingest`
prints it (manifest `units[].label`; the fulltext marker `section=…`):
`front`, a heading number (`3.2`, `A.1`, `S4.1`, thesis `1.3.1`), a LaTeXML
id fallback (`S1.SSx1`, `bib`), `unitN`, or a de-duplicated `1#2`. Pattern
`^[A-Za-z0-9][A-Za-z0-9._:#-]{0,79}$` (anything else → exit 8). A label the
ingest does not have is `SECTION_NOT_FOUND` (fail). Every unit 1..N needs a
coverage entry (`MISSING_SECTION`, fail). Uniqueness of a quote is judged
across all units and their boundaries. How units and labels are built:
`arxiv-and-html.md` § Units and labels.

## Checks in order

1. **Integrity.** Card `source_pdf_sha256` = manifest; card `paper_key` =
   manifest `paper_key` = PAPER_DIR basename; each anchor file's SHA-256 =
   the manifest record and the page_index record; page_index.parquet = its
   manifest record; each OCR text file used = its record (a mismatching OCR
   file is not used); each lane B file = its manifest and page_index record
   (1.3.0; a mismatch is `LANE_B_HASH_MISMATCH`, a fail, and that page's
   lane B is not used); the ingest manifest = the hash in the pdf_ingest
   MANIFEST row (no row: warning `NO_INGEST_ROW`). An ingest made with another
   `NORMALIZE_VERSION`: warning. v2 (1.4.0): card `anchor_kind` = ingest
   (`ANCHOR_KIND_MISMATCH`), `source_version` = `arxiv.version`
   (`SOURCE_VERSION_MISMATCH`), every complete ingest of the key has one
   anchor kind (`MIXED_ANCHOR_KINDS`); on HTML each `rows{S}/uNNN.txt` = its
   manifest and page_index record (`TABLE_ROWS_HASH_MISMATCH`; the file is
   then not used) and the `HTML_EXTRACT_VERSION` is one the tool knows
   (else warning `HTML_EXTRACT_VERSION_DIFFERS`).
2. **Quote ladder** for every coverage anchor and claim quote.
3. **Identifying-quote rule** on every quote that matched.
4. **Coverage** of every page 1..N.
5. **Numbers** of every claim.
6. **Vision consistency** with what the card declares.

## The match ladder (`ladder-v1`)

Evaluated for a quote cited to page P (or P..P+1 with `page_end`); first hit
wins.

| Tier | Meaning | Severity |
|------|---------|----------|
| `REDACTED_SPAN` | The quote holds a scrub token, `[REDACTED:`, or fence text: it was copied from a reading copy, not the page | review |
| `PASS` | Exact substring of NORMALIZE(page text) on a cited page | pass |
| `PASS_SKELETON` | Exact on SKELETON (absorbs fused compound hyphens, small-caps splits) | pass |
| `PASS_SPAN` | `page_end` = P+1 declared and the quote runs from the end of P into the start of P+1 (recorded running footers/headers between them skipped) | pass |
| `PASS_OCR` | Exact or skeleton match in a cited page's OCR text only | partial |
| `NEAR` | Best windowed rapidfuzz `partial_ratio_alignment` score on a cited page ≥ 95 (anchor or OCR text) | review, **never a pass** |
| `WRONG_PAGE` | Exact or skeleton match only on other pages, other pages' OCR, or across a page boundary not declared with `page_end` | fail |
| `NOT_FOUND` | None of the above | fail |

Long quotes (over 64 chars) are scored in 64-char windows (step 32); the
score is the minimum window score, and the windows must align in order
within 1.25 × the quote length + 10 chars, or the quote is not NEAR
(stitched fragments are not a near match).

## Identifying quotes

A matched quote must be **identifying**: at least `MIN_QUOTE_CHARS = 40`
normalized characters AND `MIN_QUOTE_WORDS = 6` words AND its SKELETON occurs
**exactly once** across all pages' anchor text and page boundaries (plus all
OCR text when it matched in OCR). Both thresholds are **PROVISIONAL**,
kept after the S3 bake-off (2026-10-19): on five real papers the length
floor almost never decided the outcome; uniqueness did. Random 6-word,
40-character spans were non-unique 3–11% of the time in four papers and 41%
in a 192-page report full of repeated table headers and notes ("Sample
Control Mean Impact SE p-value Effect" recurs 88 times), and 20-word spans
were still non-unique 32% of the time there. So on such papers, quote a
distinctive sentence, never a table header or boilerplate note. Otherwise the
status is `NON_IDENTIFYING` (a claim quote fails; a NEAR on a short quote is
NON_IDENTIFYING too).

**Duplicated pages (1.1.0).** When a page has no unique line of its own
because its text recurs on another page (a scan that repeats a page), no
anchor can be unique. A full-length anchor (at least 40 characters and 6
words) that matches exactly on that page then covers it as
`COVERED_DUPLICATE`. Claim quotes get no such waiver: cite a claim from a
duplicated page as a quote that includes the page's distinctive context, or
flag it in prose.

**Sparse waiver (Q-B).** On a sparse or truly scanned page, a coverage anchor
that is too **short** but matches exactly (`PASS`, `PASS_SKELETON` or
`PASS_OCR`) on that page is `COVERED_SPARSE`, if it is unique or the page has
no unique line of its own. On a normal page a non-identifying anchor does not
cover the page.

## Page classes (user decision Q-B, 2026-10-14)

| Class | Rule | Effect |
|-------|------|--------|
| `normal` | Not flagged `scanned` | — |
| `scanned` (truly scanned) | Flagged `scanned` AND one embedded image covers at least `TRULY_SCANNED_IMAGE_AREA_MIN = 0.50` of the page area (**PROVISIONAL**, parsed from pdf_ingest's flag evidence); also when image evidence is unavailable (pdfimages and pdfplumber both missing), the conservative reading | Adds a `SCANNED_PAGE` partial item: the card is at best PARTIAL |
| `sparse` | Flagged `scanned` but not mostly one image (a figure page with a short caption) | No cap; the sparse waiver applies. The card's `sparse` field is advisory (a mismatch is a warning) |

**OCR-layer pages (1.2.0, user decision D-21 N2).** A page flagged
`ocr_layer_suspected` (an image covers at least 80% of the page and the
anchor has text: someone else's OCR, which the gate never compared with the
image) is recorded per page as `ocr_layer: true` and treated like our own
OCR (Q-A) **for claims only**: a claim quote that passes there becomes
`PASS_OCR_LAYER` and each number found inside it `NUMBER_OCR_LAYER`
(`ocr-layer`), or `NUMBER_OCR_LAYER_VISION` (`ocr-layer+vision`) when the
claim's `source` is `both`; all are partial, so the card is at best PARTIAL.
Coverage anchors on such a page do **not** cap: the flag also fires on a
born-digital cover image (bake-off: one false positive in 342 pages), and a
cited-claims rule keeps that harmless. On the bake-off scan ED083756 (70 of
71 pages flagged) every claim is now partial.

## Coverage statuses (per page)

| Status | When | Severity |
|--------|------|----------|
| `PASS` | An identifying text-layer anchor passes | pass |
| `COVERED_SPARSE` | The sparse waiver applied | pass on a sparse text page; partial on a scanned page or via OCR |
| `COVERED_DUPLICATE` | A full-length exact anchor on a page with no unique line (its text recurs on another page) | pass; partial on a scanned page or via OCR |
| `PASS_OCR` | Best anchor matched in OCR text | partial |
| `VISION_ONLY` | A `vision_only` digest on a truly scanned page with no text in any lane, with validated vision | partial |
| `COVERED_EMPTY` | A page with no text in any lane that is not truly scanned, given an empty `anchors` list or a validated `vision_only` digest | pass |
| `NEEDS_REVIEW` | No passing anchor; the best is NEAR or REDACTED_SPAN | review |
| `NOT_COVERED` | No anchor passes | fail |
| `MISSING_PAGE` | No coverage entry | fail |

Every anchor is checked: a `NOT_FOUND` or `WRONG_PAGE` anchor always fails
(a fabricated quote), even on a page another anchor covers. An extra
NON_IDENTIFYING or NEAR anchor on a covered page is a warning.

**Consequence of the empty vision list (today).** A truly scanned page whose
OCR text is empty can only be covered by a validated `vision_only` digest, so
with no validated model it is `NOT_COVERED` and the card FAILs. Report such a
paper to the orchestrator rather than forcing the card.

## Numbers (`numbers-v3`)

Write each number exactly as printed. It must be **local** to the claim's
quote by one of two paths (recorded per number as `locality`): inside the
quote (`in-quote`), or in the one lane B row the quote's leading row label
identifies (`row`, 1.3.0). What to quote for a table number:
§ What to quote for a table number below. Rules applied to both the card
string and the page text:
- U+2212, U+2013, U+FE63, U+FF0D directly before a digit → `-`; then NFKC.
- `-` is a sign only at the start, after whitespace or after one of
  `( [ { = < > : ; , / ~`, so "2019-2020" is two positive numbers.
- `,`, U+2009, U+202F and a plain space are thousands separators only
  between groups of exactly 3 digits (`1,204` = `1 204` = 1204). A plain space
  is ambiguous (two table cells "1" "204"), so the page is searched under
  both readings.
- `.05` → `0.05`. Trailing `*`, `†`, `‡` are kept as marks. `%` is an
  attribute. Parentheses mean an SE or t statistic, **never** a negative.
- Same value and same digit string → exact; same value, other digits
  (`0.5` vs `0.50`) → precision differs; sign is part of the value.

| Status | Label | When | Severity |
|--------|-------|------|----------|
| `NUMBER_OK` | `ok` | Same value and digits in the cited page's anchor text, and local: inside the claim's quote where it matched (`locality: in-quote`) or in the one lane B row its leading label identifies (`locality: row`) | pass |
| `NUMBER_NOT_NEAR_QUOTE` | `not-near-quote` | Printed on the cited page (in the lane it was found in) but not local, or the claim has no quote located there (a `vision` claim without a quote) | review |
| `NUMBER_OCR_LAYER` | `ocr-layer` | As `ok`, on a page flagged `ocr_layer_suspected` | partial |
| `NUMBER_OCR_LAYER_VISION` | `ocr-layer+vision` | As `ocr-layer`, claim `source` `both` | partial |
| `NUMBER_OCR_ONLY` | `ocr-only` | Only in that page's OCR text, inside the quote's OCR match | partial |
| `NUMBER_OCR_VISION` | `ocr+vision` | Only in OCR text, claim `source` `both` (vision corroborates) | partial (the paper still relies on OCR, Q-A) |
| `NUMBER_VISION_ONLY` | `vision-only` | In no text lane, claim `source` `vision` | partial |
| `NUMBER_PRECISION_DIFFERS` | `precision-differs` | Same value, other digits | review |
| `NUMBER_MISSING` | `missing` | Anything else (a changed digit, a dropped minus; `both` declares a text reading, so a number in no text lane fails) | fail |
| `NUMBER_UNPARSEABLE` | `unparseable` | The card string is not one number | fail |

**Locality (`numbers-v2`, 1.2.0, user decision D-21 N1).** Under
`numbers-v1` a number passed when its value was printed anywhere on the
cited page; in the S3 bake-off a planted last-digit change still passed 44%
of the time on dense table pages (351 of 800) and a sign flip 5% (42 of
800). Now a page token printing the value must overlap the place where the
claim's quote matched (`NUMBER_NEAR_CHARS = 0`: inside the quote; page
tokens are used, so a minus the SKELETON tier ignores cannot slip through;
a declared `page_end` span is matched across the page boundary). A value
printed elsewhere on the page is `not-near-quote`: a **human check, not a
fail**; a value absent from the page is still `missing`. Measured on the
bake-off ingests (FE-5 script 69; 453 table claims from B and C, quote =
12 words from the row label as a reader copying from `pages/` gets them;
119 prose numbers from A, B, F), share graded ok, genuine / last digit
changed / sign flipped:

| Rule | Table numbers | Prose numbers |
|------|---------------|---------------|
| Page-level (`numbers-v1`) | 1.000 / 0.110 / 0.009 | 1.000 / 0.034 / 0.000 |
| **Inside the quote (chosen)** | **0.305 / 0.013 / 0.000** | **1.000 / 0.000 / 0.000** |
| Within 40 chars of the quote | 0.322 / 0.026 / 0.000 | 1.000 / 0.000 / 0.000 |
| Within 160 chars | 0.470 / 0.035 / 0.000 | 1.000 / 0.000 / 0.000 |
| Lane B row (the number on one lane B line that shares ≥ 6 letters with the quote) | 1.000 / 0.053 / 0.000 | 0.941 / 0.000 / 0.000 |

The rule with the fewest fabricated passes was chosen (gate integrity
first). *Correction (FE-5c, 2026-10-22):* script 69 quoted each table claim
from the **first** occurrence of its row label on the page. On report-style
pages a label such as "Full Sample" recurs in several panels, so that quote
often belonged to another row, and the 0.305 above understates the in-quote
rule (FE-5c scripts 75 and 76).

**The unique-row rule (`numbers-v3`, 1.3.0, user decision D-22).** The user
adopted lane B's row-by-row text as locality evidence, because human review
time matters. A number printed on the anchor page also clears (`locality:
row`) when all of these hold:
1. the claim quote passed on the **anchor** (`PASS`, `PASS_SKELETON`,
   `PASS_SPAN` or `PASS_OCR_LAYER`). Lane B never anchors a quote;
2. the quote's **leading label** identifies **exactly one** lane B row on
   the page(s) where the quote matched. The leading label is the quote's
   letters before its first number that follows a letter, or the whole quote
   when it holds no such number. A row is a lane B line whose own label (its
   letters before its first number after a letter, at least
   `ROW_LABEL_MIN_CHARS = 2` letters) is followed by at least one number.
   The quote's leading label must *start with* the row's label and the label
   must end at a word boundary ("No" does not match "Notes"). The longest
   matching label wins. Two or more lines with that label are `ambiguous`,
   none is `none`. Letters only, so `co-teaching` = `coteaching`, but rows
   `Grade 3` and `Grade 4` share the label `grade` and are ambiguous (the
   safe side);
3. that row prints the claimed value with the same digits and sign, after
   its label (a row index such as `7.` is not a cell).

An `ambiguous` or `none` label falls back to the in-quote path. Otherwise
the number is `not-near-quote` (review). Every number item records
`locality` (`in-quote`, `row` or null) and `row_match` (`unique`,
`ambiguous`, `none`, or null when the row path was not tried) so a reviewer
sees which path cleared it. Measured on the bake-off ingests, with each table
quote taken from the number's own row (FE-5c script 76: 449 claims from B and
C; 60 DOI/URL and footnote rows excluded). Shares graded ok, genuine / last
digit changed / sign flipped:

| Rule | Table numbers, pooled | Column-major rows (31) |
|------|-----------------------|------------------------|
| Inside the quote (`numbers-v2`) | 0.976 / 0.018 / 0.000 | 0.645 / 0.000 / 0.000 |
| Lane B, any line sharing ≥ 6 letters (B6) | 1.000 / 0.058 / 0.000 | 1.000 / 0.097 / 0.000 |
| **Unique row OR inside the quote (`numbers-v3`, shipped)** | **0.996 / 0.018 / 0.000** | **0.935 / 0.000 / 0.000** |

On script 69's own sample (430 table claims after removing 23 noise rows),
the shipped rule cleared 0.277 genuine and B6 1.000, with 0.016 and 0.056
fabricated last digits. Those quotes started at a recurring label: the
shipped rule calls 98% of C's quotes `ambiguous`, and B6 clears them by
matching any line that shares the label, including the look-alike rows. Prose
numbers (51 claims from A, B, F): 1.000 genuine and 0.000 fabricated under
both in-quote and the shipped rule (script 74).

**Residuals (documented, not caught):**
- (a) *same row, another column.* In a row `Overage 0.58 0.57 0.59 …`, a
  claim of 0.59 for the first column clears: the gate knows the row, not the
  column. The same holds inside a quote that holds the whole row. A validated
  vision cross-check could catch it (none is validated yet).
- (b) *look-alike rows* are closed: under B6, "Time III (Inclusive with
  co-teaching)" matched the "… without co-teaching" row and "Full Sample"
  matched another table's row. Now the label must identify one row, so such
  claims go to review.

### What to quote for a table number

- **Row-major anchor** (`pages/` shows the row's label and cells on one
  line): quote from the row label through the cell, for example
  `North Quay (with tide gauge) 0.62 0.63`. This clears in-quote.
- **Column-major anchor** (`pages/` lists the row labels, then each column):
  **start the claim quote at the row label** and copy forward from `pages/`,
  usually a run of row labels such as `North Quay (with tide gauge) North Quay
  (without tide gauge) All Harbours`. The gate finds the row in lane B. Open
  `pages/pNNN_rows.txt` (the reading aid, `pdf-ingest.md` § Reading aid) to
  see which value belongs to which row. Never quote the aid itself: its lines
  carry a `lane-B| ` prefix, and lane B is not the anchor, so a quote copied
  from it fails (`NOT_FOUND`) unless the anchor prints the same text.
- The quote must still be identifying. When a label recurs on the page (two
  `Full Sample` rows), the row path is `ambiguous`: quote the row's cells
  in-quote if the anchor allows it, or accept the review item.
- No card change: v1 cards are unchanged and still valid, and their numbers
  can only gain the row path. `table_ref` stays optional and is not checked.

Known limits: a plain-space thousands separator reads both ways (by design);
European decimals (`1.204,5`) are not handled, so write such a number as a
quote instead and flag it; parenthesis or percent differences between card
and page are notes on an `ok`, not failures.

## Vision consistency

With `vision_mode: "off"` or `vision_validated: false`, every claim with
`source` `vision` or `both` and every `vision_only` digest is a fail
(`VISION_UNAVAILABLE_CLAIM`). `lit_verify` does not decide whether the model is
validated; it enforces only consistency with what the card declares
(`vision-validation.md` § Gating covers the rest).

## arXiv HTML statuses (1.4.0)

On an HTML ingest the page checks run on units (class `sparse` when
`pdf_ingest` flagged the unit sparse, else `normal`; never `scanned`), with
these statuses beside the PDF ones:

| Status | When | Severity |
|--------|------|----------|
| `ANCHOR_KIND_MISMATCH` | Card `anchor_kind` (v1 = `pdf`) differs from the ingest's | fail (nothing else checked) |
| `SOURCE_VERSION_MISMATCH` | Card `source_version` differs from the ingest's arXiv version | fail |
| `MIXED_ANCHOR_KINDS` | The key's complete ingests mix `pdf` and `arxiv_html` | fail |
| `TABLE_ROWS_HASH_MISMATCH` | A `rows{S}/uNNN.txt` hash differs from its records | fail |
| `SECTION_NOT_FOUND` | A coverage or claim `section`/`section_end` label the ingest does not have | fail |
| `MISSING_SECTION` | A unit with no coverage entry (the `MISSING_PAGE` analogue) | fail |
| `WRONG_SECTION` | The quote matches exactly only in other units, or across an undeclared unit boundary (the `WRONG_PAGE` analogue) | fail |
| `SECTION_END_NOT_NEXT` | `section_end` is not the unit right after `section` | fail |
| `PASS_CONVERSION_ERROR` | A claim quote passed in a unit flagged `conversion_error` (LaTeXML `ltx_ERROR`) | partial |
| `NUMBER_CONVERSION_ERROR` (`conversion-error`) | A number that would be `ok`, in such a unit | partial |
| `HTML_EXTRACT_VERSION_DIFFERS` | The ingest used an extraction version the tool was not built for | warning |

Coverage anchors in a conversion-error unit do not cap. Every other status
(the ladder tiers, `NON_IDENTIFYING`, `COVERED_SPARSE`, `COVERED_DUPLICATE`,
the number statuses) means what it means on a page; the OCR and vision
statuses cannot occur.

## Verdicts and grades

Every item carries a severity `pass`, `partial`, `review`, `fail` or
`warning`.

| Verdict | When | `evidence_grade_suggested` | Exit |
|---------|------|-----------------------------|------|
| `FAIL` | Any fail item (all listed) | null | 11 |
| `NEEDS_REVIEW` | No fail; a NEAR, REDACTED_SPAN, NEEDS_REVIEW, precision-differs or not-near-quote item | null; `evidence_grade_if_review_confirmed` = `FULL_TEXT_VERIFIED`, or `FULL_TEXT_PARTIAL` when partial items exist | 0 |
| `PARTIAL` | No fail or review; a PASS_OCR, PASS_OCR_LAYER, VISION_ONLY, ocr-only, ocr+vision, ocr-layer, ocr-layer+vision, vision-only, COVERED_SPARSE-on-scanned or SCANNED_PAGE item, or (arXiv HTML) a PASS_CONVERSION_ERROR or conversion-error item | `FULL_TEXT_PARTIAL` | 0 |
| `PASS` | Everything anchored in the text layer | `FULL_TEXT_VERIFIED` | 0 |

Evidence grades and what synthesis may do with each: spec §7.5
(`FULL_TEXT_PARTIAL` = claims from verified pages only, exceptions listed).

## `card_check{S}.json`

Written in `PAPER_DIR`, named after the card version: `evidence_card.md` →
`card_check.json`, `evidence_card_a.md` → `card_check_a.json`, any other
card name → `card_check_<slug>.json`. **Never overwritten**: a re-check of the
same card version gets `_1`, `_2` (`card_check_a_1.json`). Written only when a
verdict exists (exit 0 or 11). Holds `kind`, `schema_version`,
`tool_version`, `checked_at`, `paper_key`, `card` (path, bytes, SHA-256,
`reader_model`, `vision_mode`, `vision_validated`, `vision_list_version`),
`ingest` (suffix, manifest name and SHA-256, page count, source SHA-256,
pdf_ingest version, normalize version), `rule_versions`, `constants` (with
the PROVISIONAL list), `verdict`, the grades, `vision_available`,
`fuzzy_tier_run`, `counts`, `failures`, `review_items`, `partial_items`,
`warnings`, `pages` (class, image area, `ocr_layer`, `lane_b` (lane B
available and used), coverage status per page) and `items` (number items
also carry `locality` and `row_match`, 1.3.0; constants gain
`ROW_LABEL_MIN_CHARS`). Card quotes in it are injection-scrubbed and secret-redacted, with
the original quote's SHA-256 kept. **It holds no page text.**

**Result schema `lit-verify-card-check-v2` (1.4.0)** is v1 plus additive
fields, written for PDF and HTML cards alike: top-level `anchor_kind`;
`card.schema_version`, `card.anchor_kind`, `card.source_version`;
`ingest.anchor_kind`, `unit_count`, `source_sha256`, `source_version`,
`arxiv_id_version`, `html_extract_version` (`ingest.source_pdf_sha256` is
null on HTML); every item carries `section` and `section_end` (the unit
labels on HTML, where `page`/`page_end` are null; null on PDF); `sections`
(one summary per unit on HTML: `unit`, `section`, `latexml_id`, `class`,
`basis`, `conversion_error`, `table_rows`, `anchors`, `coverage_status`;
`[]` on PDF) beside `pages` (`[]` on HTML); `counts` gains `sections`,
`sections_covered`, `sections_sparse`, `sections_conversion_error` on HTML
(in place of the page counts); constants gain `HTML_EXTRACT_VERSIONS_KNOWN`.

## MANIFEST row (papers dir, kind `lit_verify`)

One row per attempt with a valid papers dir: `kind`, `tool_version`,
`command`, `paper_key`, `parameters`, `timestamp`, `requesting_context`,
`card` (path, bytes, SHA-256), `ingest` (suffix, manifest, manifest SHA-256,
page count, and since 1.4.0 `anchor_kind` and `unit_count` (null on PDF)),
`artifacts.card_check` (name, bytes, SHA-256), `verdict`,
`evidence_grade_suggested`, `counts`, `redaction_count`,
`secret_redactions`, `exit_code`, `note`. A usage error or a refused papers
dir writes no row.

## Exit codes

| Exit | Meaning |
|------|---------|
| 0 | Verdict PASS, PARTIAL or NEEDS_REVIEW (in the card_check JSON); selftest: every expectation held |
| 1 | Usage error (bad flags; PAPER_DIR not a directory; CARD_PATH not a file) |
| 2 | Refused path (PAPER_DIR / papers dir / SCRATCH_DIR guard; CARD_PATH not directly inside PAPER_DIR; basename not a paper key; an ingest artifact path resolving outside PAPER_DIR; a secret value in an argument) |
| 3 | Reserved by `run_with_capture.sh`, never used |
| 8 | Card cannot be parsed (missing, duplicate or invalid lit-verify block; oversize or non-UTF-8 card; a v2 structural rule broken: `source_version` missing on HTML or present on PDF, a non-`text` source or vision declared available on HTML, a bad or repeated section label, `section_end` = `section`) |
| 10 | Ingest artifacts missing or incomplete (no manifest for the suffix, a missing anchor, OCR, table-rows or page_index file, an unreadable manifest, a manifest with an unknown `anchor_kind`, an HTML manifest without unique unit labels or `arxiv.version`), or a required library missing (rapidfuzz; polars or pyarrow) |
| 11 | FAIL as a recorded result (card_check written); selftest: an expectation did not hold |
| 12 | Internal error (no verdict; see the MANIFEST note) |

## Fixing a failing card

At most **two** self-revisions (spec §7.4), each a new card file
(`evidence_card_a.md`, `evidence_card_b.md`), then return with the latest
`card_check` path and the open items.

| Status | Usual cause | Fix |
|--------|-------------|-----|
| `NOT_FOUND` | Paraphrase, a quote from memory, or a word changed | Re-copy the sentence from `pages/pNNN.txt` |
| `WRONG_PAGE` | Wrong page number, or a quote that crosses a page break | Correct `page`; for a crossing quote, declare `page_end: page + 1` |
| `NON_IDENTIFYING` | Too short or a phrase that recurs | Quote a longer, distinctive sentence |
| `REDACTED_SPAN` | Copied a scrub token or fence line from a reading copy | Quote the page text around it; if the page itself holds injection-shaped text, flag it |
| `NEAR` | One character off (an OCR error, a typo in the card) | Re-copy; if the page really differs from what you read, log it |
| `NUMBER_MISSING` | Number rewritten (rounded, sign dropped, cell from another page) | Write it as printed, on the page where it is printed |
| `NUMBER_PRECISION_DIFFERS` | `0.5` for `0.50` | Copy the printed digits |
| `NUMBER_NOT_NEAR_QUOTE` | The quote does not hold the number, and its leading label identifies no single lane B row printing it (`row_match` says why) | Start the quote at the row label (§ What to quote for a table number), or quote the anchor run that holds the number; else leave it for the human check |
| `VISION_UNAVAILABLE_CLAIM` | A `vision`/`both` claim with vision unavailable | Use `text` (or `ocr`) with a text quote, or drop the claim and note it |
| `MISSING_PAGE` / `MISSING_SECTION` / `NOT_COVERED` | A page or unit skipped, or only short anchors on a normal one | Add an identifying anchor for it (a heading-only `sparse` unit: its heading, exactly) |
| `*_HASH_MISMATCH` | The ingest or card changed after it was written | Do not "fix" the card: report it; the orchestrator re-ingests |
| `WRONG_SECTION` | Wrong section label, or a quote that runs into the next unit | Correct `section`; for a quote that crosses into the next unit, declare `section_end` with that unit's label |
| `SECTION_END_NOT_NEXT` | `section_end` names a unit that is not the next one | Use the next unit's label (manifest `units`, in order), or split the quote |
| `SECTION_NOT_FOUND` | A label typed from the paper's printed numbering, or reconstructed | Copy the label from the manifest's `units[].label` or the fulltext marker `section=…` |
| `PASS_CONVERSION_ERROR` (partial) | The claim quotes a unit where LaTeXML could not convert a macro | Quote another unit that states the claim, or accept PARTIAL (or read the paper from the PDF under its own key) |
| `ANCHOR_KIND_MISMATCH` | A v1 or `pdf` card on an HTML ingest, or the reverse | Rewrite the card as `lit-verify-card-v2` with the ingest's `anchor_kind` and its locators (sections or pages) |
| `SOURCE_VERSION_MISMATCH` | The card names another arXiv version than the one ingested | Write the ingested version (manifest `arxiv.version`); if you read another version, that version needs its own fetch, key and ingest |
| `MIXED_ANCHOR_KINDS` | A PDF and an HTML ingest under one paper key | Report it: the orchestrator moves one source to its own key |

## Selftest

`lit_verify.sh selftest <SCRATCH_DIR>` builds synthetic ingests in a work dir
under `SCRATCH_DIR`, plants fabrications in cards, runs the real card gate on
each and checks every expected verdict: a genuine card (PASS), one digit
changed, a quote cited to the adjacent page, an invented 12-word quote, a
dropped minus sign, a non-identifying short quote, a tampered anchor file, a
vision claim on a `vision_validated: false` card (all FAIL), a synonym-swap
paraphrase (NEEDS_REVIEW via NEAR), an OCR quote on a truly scanned page
(PARTIAL via PASS_OCR), the fused compound hyphen (PASS_SKELETON), a
sparse non-image page (COVERED_SPARSE), a number printed on the page but
not in its quote (NEEDS_REVIEW via NUMBER_NOT_NEAR_QUOTE, 1.2.0), a claim
on an existing OCR text layer page (PARTIAL via PASS_OCR_LAYER, 1.2.0), and
on a column-major table page (1.3.0): a number found through its one lane B
row (PASS), a fabricated value the same row prints in another column (PASS:
the documented residual), a fabricated value from a look-alike row and a row
label shared by two rows (both NEEDS_REVIEW via NUMBER_NOT_NEAR_QUOTE), and
(1.4.0) on a synthetic arXiv HTML paper ingested through `pdf_ingest`'s real
`--source arxiv-html` lane (units `front`, `1`, `1.1` with a table, `2` with
an `ltx_ERROR` span, `bib`): a genuine v2 card with a number found in-quote
and one through its `rows/` row (PASS via NUMBER_OK), a quote cited to
another section (FAIL via WRONG_SECTION), a claim in the conversion-error
section (PARTIAL via PASS_CONVERSION_ERROR), a card pinned to another arXiv
version (FAIL via SOURCE_VERSION_MISMATCH) and a v1 card on the HTML ingest
(FAIL via ANCHOR_KIND_MISMATCH), plus one check that each card run wrote one
MANIFEST row with a matching `card_check` hash: **24 expectations**. It needs
no PDF tools, but it needs rapidfuzz, polars or pyarrow, **and polars** (the
HTML case is ingested by `pdf_ingest`, which writes its page_index with
polars; without it, exit 10). It removes its work dir and prints
`lit_verify: SELFTEST PASS: 24/24 expectations held; work dir removed`.

## Worked examples

`tests/python/fixtures/lit_verify/example_evidence_card.md` is a complete
card for the synthetic fixture `tests/python/fixtures/pdf_ingest/pdf/multipage.pdf`
(every word invented): a PASS_SKELETON anchor on a fused hyphen, a sparse
figure page, a truly scanned page read through OCR (PASS_OCR plus
SCANNED_PAGE), an SE in parentheses and a U+2212 minus. Its expected result
is verdict PARTIAL, `FULL_TEXT_PARTIAL`. A minimal block:

```lit-verify
{"schema_version": "lit-verify-card-v1", "paper_key": "user_00000001",
 "source_pdf_sha256": "<64 hex from ingest_manifest source.sha256>",
 "reader_model": "claude-opus-5-5", "vision_mode": "auto",
 "vision_validated": false, "vision_list_version": "vision-list-2026-10-19",
 "coverage": [{"page": 1, "anchors": ["<a verbatim, distinctive sentence from page 1>"],
               "summary": "one line"}],
 "claims": [{"claim_id": "C1", "page": 1, "quote": "<verbatim sentence>",
             "numbers": ["-0.087", "(0.044)"], "source": "text"}]}
```

(Placeholders shown in angle brackets are for illustration; a real card has
none, and a card holding this block verbatim would fail its hash check.)

**arXiv HTML.** `tests/python/fixtures/lit_verify/arxiv_html_evidence_card.md`
is a v2 card for the synthetic LaTeXML fixture
`tests/python/fixtures/pdf_ingest/html/synthetic_latexml.html` (every word
invented), ingested with `--source arxiv-html`: section locators including
fallback ids (`S1`, `S1.SSx1`), a composed thesis number (`2.3.1`) and a
de-duplicated heading, heading-only `sparse` units covered by their heading
(COVERED_SPARSE), a table claim quoted through the row, a quote that spans
into the next unit with `section_end`, and a claim in a conversion-error
unit (PASS_CONVERSION_ERROR). Expected: verdict PARTIAL,
`FULL_TEXT_PARTIAL`. A minimal block:

```lit-verify
{"schema_version": "lit-verify-card-v2", "paper_key": "user_00000002",
 "anchor_kind": "arxiv_html", "source_sha256": "<64 hex: ingest_manifest source.sha256>",
 "source_version": "v4", "reader_model": "claude-opus-5-5", "vision_mode": "off",
 "vision_validated": false, "vision_list_version": "vision-list-2026-10-19",
 "coverage": [{"section": "front", "anchors": ["<a verbatim, distinctive sentence>"],
               "summary": "title and abstract"}],
 "claims": [{"claim_id": "C1", "section": "3.2", "quote": "<verbatim sentence>",
             "numbers": ["0.41"], "source": "text"}]}
```
