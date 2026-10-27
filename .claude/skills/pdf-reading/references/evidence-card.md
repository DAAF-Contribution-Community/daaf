# The evidence card and the `lit_verify card` gate

How to write an evidence card that `scripts/lit_verify.sh card` can verify,
what every check and status means, and how to fix a failing card. Source of
truth: the header, `validate_card()`, `check_card()` and the selftest in
`scripts/lit_verify.py` (`TOOL_VERSION = "1.8.0-daaf"`, 2026-10-27; card
schemas `lit-verify-card-v1` and `lit-verify-card-v2`, result schema
`lit-verify-card-check-v2`, re-derivation `rederive-v2`) and the ladder,
number and column-label rules in `scripts/pdf_text_common.py` (`ladder-v3`,
`numbers-v6`, `column-check-v1`, `normalize-v1`). A later session
adds `lit_verify report` (S4); the full card schema is formalized later in
`LIT_REVIEW_OUTPUT_CONTRACT.md` (spec C14). If this page and the code
disagree, the code wins.

**Contents:** Syntax · Card anatomy · Front matter · The lit-verify block ·
Card schema v2 and section locators · Checks in order · Re-derivation ·
The match ladder · The quote-number rule · Identifying quotes · Page
classes · Coverage statuses · Numbers · Vision consistency · arXiv HTML
statuses · Integrity and warning statuses · Status index · Verdicts and
grades · card_check JSON · MANIFEST row · Exit codes · Fixing a failing card
· Selftest · Worked examples

## Syntax

```
bash /daaf/scripts/lit_verify.sh card <PAPER_DIR> <CARD_PATH> [--ingest-suffix S] [--timeout S]
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
- `--timeout` (1.7.0): seconds per subprocess when re-deriving the anchors
  from the source (default 120, as `pdf_ingest`); exceeded →
  `SOURCE_REDERIVE_ERROR`, a recorded fail.
- No network calls, no model calls. It never reads the fenced reading copies
  (`pages/`, `fulltext.md`); it matches the byte-for-byte anchor, after
  re-deriving it from the stored source (§ Re-derivation).
- **The source must stay where `pdf_ingest` found it** (the manifest's
  `source.path`, normally web_fetch's raw artifact in `web_fetches/`, or the
  file in `user_pdfs/`): a moved or deleted source now fails closed
  (`SOURCE_MISSING`).

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
| `schema_version` | yes | `"lit-verify-card-v1"` (or `"lit-verify-card-v2"`, next section); anything else → exit 8 |
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
   MANIFEST row (no row: `NO_INGEST_ROW`, a fail from 1.7.0). An ingest made with another
   `NORMALIZE_VERSION`: warning. v2 (1.4.0): card `anchor_kind` = ingest
   (`ANCHOR_KIND_MISMATCH`), `source_version` = `arxiv.version`
   (`SOURCE_VERSION_MISMATCH`), every complete ingest of the key has one
   anchor kind (`MIXED_ANCHOR_KINDS`); on HTML each `rows{S}/uNNN.txt` = its
   manifest and page_index record (`TABLE_ROWS_HASH_MISMATCH`; the file is
   then not used) and the `HTML_EXTRACT_VERSION` is one the tool knows
   (else warning `HTML_EXTRACT_VERSION_DIFFERS`). The statuses:
   § Integrity and warning statuses.
   1b. **Re-derivation** (1.7.0): the anchor text, lane B and table rows are
   re-derived from the stored source and compared byte-for-byte
   (§ Re-derivation).
2. **Quote ladder** for every coverage anchor and claim quote, then the
   **quote-number rule** on every claim quote that passed (`ladder-v3`).
3. **Identifying-quote rule** on every quote that matched.
4. **Coverage** of every page 1..N, then the paper-level OCR-layer cap.
5. **Numbers** of every claim.
6. **Vision consistency** with what the card declares and the embedded
   vision list.

## Re-derivation (1.7.0 `rederive-v1`, D-24 W1; 1.8.0 `rederive-v2`, review cycle 2)

Hashes alone prove only that the manifest, page_index and anchor files agree
with **each other**: in review cycle 1 a hand-written ingest set with a
fabricated anchor sentence and consistent hashes (and a MANIFEST row) passed.
So before any quote is matched, `lit_verify` re-derives the text it is about
to trust from the source the ingest recorded, with `pdf_ingest`'s own code
(`pdf-ingest.md` § Functions lit_verify reuses):

| Source | What is re-derived and compared byte-for-byte | Mismatch |
|--------|-----------------------------------------------|----------|
| The stored source (`source.path`) | Must resolve under the DAAF root and outside the forbidden prefixes (`.claude`, `.git`, `/tmp`, …), be a file of at most `SOURCE_MAX_BYTES` (100 MiB, `pdf_ingest`'s default `--max-bytes`) and hash to the manifest's `source.sha256` | `SOURCE_MISSING` (not recorded, outside the root, moved, deleted, oversize or unreadable) or `SOURCE_FILE_HASH_MISMATCH` (another file at that path): fail; nothing is re-derived, so no anchor is trusted |
| PDF anchor | `pdftotext` page by page with `pdf_ingest.anchor_argv()` (`LC_ALL=C`), **every** page (the uniqueness rule reads them all), 4 in parallel (`REDERIVE_WORKERS`); the page count from `pdfinfo` | `ANCHOR_REDERIVE_MISMATCH` (fail) |
| PDF lane B | `pdf_ingest.lane_b_page_text()` (pypdfium2) on every page that has a lane B file | `ROW_SOURCE_REDERIVE_MISMATCH` (fail; that page's lane B is then not used, so no number takes the row path there) |
| arXiv HTML | `pdf_ingest.html_units()` / `unit_evidence()` (`HTML_EXTRACT_VERSION`): unit count, labels, unit text, unit flags and the watermark's arXiv id and version; each `rows{S}/uNNN.txt` | `ANCHOR_REDERIVE_MISMATCH`; rows: `ROW_SOURCE_REDERIVE_MISMATCH` (the file is not used) |

- A `pdftotext` or pypdfium2 version other than the one the ingest recorded
  is `EXTRACTOR_VERSION_DIFFERS` (warning): the byte comparison still decides.
- `pdftotext`, `pdfinfo` or (1.8.0) `pdfimages` missing → exit 10. One of
  them failing, or exceeding `--timeout`, or HTML that no longer decodes →
  `SOURCE_REDERIVE_ERROR` (fail; raise `--timeout` if it timed out).
  pypdfium2 missing or failing → `ROW_SOURCE_NOT_REDERIVED` (warning; lane B
  is not used, so no number takes the row path).
- **Read once (1.8.0, `rederive-v2`, review W-b):** the source file is read
  once and those bytes are hashed; every lane re-derives from the same
  bytes, never from the path again (poppler reads a sealed memfd as
  `/dev/fd/N`; pypdfium2, pdfplumber and the HTML lane read the bytes). A
  file swapped in at the path after the hash changes nothing. Without
  memfd sealing (non-Linux) → `SOURCE_REDERIVE_ERROR` (fail; no fallback to
  the path).
- **Header/footer, page flags and OCR (1.8.0, review NB1, W-c, W-d):** from
  the re-derived anchors, with `pdf_ingest`'s own rules (its
  `header_footer_records()`, `text_flag_evidence()`, `caption_evidence()`,
  `image_evidence()`, `ocr_layer_evidence()`):
  - the header/footer lines a declared span may skip; a manifest list that
    differs → `HEADER_FOOTER_REDERIVE_MISMATCH` (fail), and only the
    re-derived lines are skipped (a forged record had let a span quote skip
    a printed line);
  - the page flags that move a grade (`GRADE_FLAGS`: `table`, `numeric`,
    `scanned`, `ocr_layer_suspected`) and the truly-scanned image evidence,
    from the text, `pdfimages -list` and `pdfinfo` on the same bytes;
    pdfplumber only where needed (`find_tables` on a caption-less `table`
    page a numbered claim cites; elsewhere `table` changes no item and is
    kept as recorded; `page.images` on a scanned page of a document
    pdfimages lists no image for, and on an `ocr_layer_suspected` page
    pdfimages alone does not confirm). A flag or page class that differs →
    `FLAGS_REDERIVE_MISMATCH` (fail); the gate uses the re-derived flags
    (a forged removal of 70 `ocr_layer_suspected` flags had lifted the
    D-24 cap). pdfplumber unavailable → `FLAGS_NOT_REDERIVED` (warning) and
    a conservative reading: an unconfirmed `table` closes the row path, a
    recorded `ocr_layer_suspected` is kept. Residual: a page whose ≥ 80%
    image only pdfplumber sees, with the flag removed from the manifest (no
    such page in the five bake-off PDFs);
  - OCR text on a page that re-derives with ≥ 200 non-whitespace anchor
    chars (not scanned, so `pdf_ingest` never OCRs it) → `OCR_ON_TEXT_PAGE`
    (fail; the OCR text is not used).
- **Not re-derived:** OCR text itself (Tesseract on a 300-DPI render costs
  seconds per page). Its files are hash-checked only, and a paper whose OCR
  text is used carries one `OCR_NOT_REDERIVED` warning; OCR evidence is
  already capped at PARTIAL. The display-only flags (figure, garbled,
  rotated, cjk_risk, low_agreement, ocr) move no verdict.
- `rederive.source_kind` (recorded only; no verdict effect): `web_fetch`
  (a web_fetch `MANIFEST.jsonl` beside the source names it with its hash;
  `web_fetch_row` gives `manifest_line`, `final_url` and `fetch_timestamp`),
  `web_fetch_row_conflict` (rows name the file with another hash),
  `user_supplied` (no such row), `synthetic` (selftest only; the CLI never
  produces it) or `unknown` (that MANIFEST could not be read).
  `source_kind_ingest` is what `pdf_ingest` recorded at ingest time.
- **What the gate does not prove (the whole-chain residual).** Re-derivation
  proves that the card and the ingest agree with the bytes on disk at
  `source.path`, not that those bytes came from the publisher. An agent with
  Write can author a source file, a matching web_fetch MANIFEST row, the
  ingest set and the card, and that self-consistent forgery passes.
  Re-derivation (the anchors, lane B and, from 1.8.0, the header/footer
  lines, OCR acceptance and the `GRADE_FLAGS` `table`, `numeric`, `scanned`
  and `ocr_layer_suspected`) catches a forged ingest over a genuine source;
  OCR text stays hash-checked only (above). It cannot catch a forged source.
  The orchestrator's audit can: compare `source_kind` and `web_fetch_row` in
  the `card_check` with its own record of fetches (its transcript and the
  web_fetch MANIFEST rows of the fetches it dispatched). A `web_fetch` source
  whose line, URL and timestamp
  match no dispatched fetch, any `web_fetch_row_conflict`, a `user_supplied`
  source the user did not supply, and `synthetic` or `unknown` on a real card
  are reported, not trusted. *Inference:* this audit step is specified here
  and is to be built into the Literature Review mode (S5); it has not been
  exercised yet.
- `card_check` records the outcome in `rederive` (§ card_check JSON) and the
  MANIFEST row a summary. On the nine bake-off cards every re-derivation
  matched, in 0.06–0.97 s under 1.7.0 (0.968 s for the 192-page report)
  and 0.065–1.67 s under 1.8.0 (1.665 s for that report).
- Selftest and unit-test ingests are built in code and have no source file:
  `build_synthetic_ingest()` registers the planted text (and, 1.8.0, what
  the image and table tools would report for it) in an in-process registry
  (`SYNTHETIC_SOURCES`) that the CLI never fills, so no file or argument can
  reach it.

**If a card fails here, do not edit the card.** Report it: the ingest or its
source changed after the ingest, and the orchestrator re-ingests (or restores
the source to its recorded path).

## The match ladder (`ladder-v3`)

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

The tiers are those of `ladder-v1`; `ladder-v2` (1.6.0) adds the
quote-number rule below on top of them, and `ladder-v3` (1.8.0) widens it.

## The quote-number rule (`ladder-v2`, 1.6.0, S3-A review finding B2; `ladder-v3`, 1.8.0)

SKELETON deletes `-`, so without this rule a claim quote "slope was 0.164"
passed on a page printing "slope was −0.164", and "510%" on "5–10%". Now a
**claim quote** that passes on any tier (`PASS`, `PASS_SKELETON`,
`PASS_SPAN`, `PASS_OCR`, `PASS_OCR_LAYER`, `PASS_CONVERSION_ERROR`) must
print, **in order**, the same number tokens, sign included, as the page span
it matched (`pdf_text_common.quote_numbers_agree()`). The quote is parsed as
written; the page side is the page's *number view* (NORMALIZE coordinates
with superscripts, thin-space groups and a sign lost to a line-break rejoin
put back; the whole tokens that overlap the matched span). A plain space
between digit groups is read both ways; agreement under either reading
counts. Otherwise the quote is `QUOTE_NUMBERS_DIFFER` (review): the item
keeps the pass it replaced in `status_if_confirmed`, and carries
`quote_numbers`, `page_numbers` and `quote_numbers_agree`. A passing quote
whose matched span cannot be located is graded the same way (fail closed).
Coverage anchors are not checked (they carry no claim). A
`QUOTE_NUMBERS_DIFFER` quote also leaves the row path (§ Numbers).

`ladder-v3` (1.8.0, S3-C1b, review cycle 2 NB2;
`pdf_text_common.quote_number_check()`) adds three things:
- **Marks.** Each token's superscript and footnote letter must agree too, so
  "p < 10³" over a printed "p < 10⁻³" (the superscript minus dropped) and
  "0.164a" over "−0.164a" are caught.
- **Sign-shaped dashes, position by position.** Every `-` the span prints
  directly (or after one space) before a digit or `.digit` must stand at the
  same place in the quote, compared on the SKELETON characters of the two
  (equal by construction). Every dash and minus that NORMALIZE folds counts,
  the superscript minus included, and so does a dash the line-break rejoin
  deleted (`K-` + line break + `12`). This catches a deleted dash even where
  no number token is parsed ("0.164ab" over "−0.164ab"). A dash outside the
  span (before its first character) is not checked; an extra dash in the
  quote is allowed.
- **Spaced dashes compare without the sign.** When the page token is
  sign-ambiguous (§ Numbers), or a spaced dash precedes the quote's token,
  the two tokens compare digits without the sign. The dash itself is still
  checked by the position rule.

**Fixing `QUOTE_NUMBERS_DIFFER`.** Compare `quote_numbers` with
`page_numbers` in the item; the reason says whether the digits, a mark
(superscript or footnote letter) or a sign-shaped dash differ. Usually a
minus, a range dash, a superscript or a digit was lost when the quote was
retyped. Re-copy the quote from `pages/pNNN.txt` with every number exactly as
printed (`−0.164`, `5–10%`, `10⁻³`). If the page itself prints the dash as
something that is not a sign (a binary minus in a formula, an exponent),
leave the item for the human check. On the bake-off papers the rule raised
2 false alarms in 2,407 genuine quotes under `ladder-v2` (both quotes
starting with such a minus, S3-A2) and 0 under `ladder-v3` (WS script 111;
the binary minus there is now sign-ambiguous). Of 217 planted minus
deletions it flagged 208 under `ladder-v2` and 217 under `ladder-v3`.

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

**Paper-level cap (1.6.0, user decision D-24 W2).** A paper with at least
`OCR_LAYER_PAPER_CAP_PAGES = 2` pages flagged `ocr_layer_suspected` gets one
`OCR_LAYER_PAPER` item (partial) and is at best PARTIAL even when no claim
cites those pages: much of its text is someone else's OCR. One flagged page
alone does not cap the paper (the false-positive cover image above). PDF
only; `counts.pages_ocr_layer` records the number of flagged pages.

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

## Numbers (`numbers-v6`)

Versions: `numbers-v2` locality, `numbers-v3` the unique-row path,
`numbers-v4` the spaced sign, superscript marks and row guards (1.6.0),
`numbers-v5` the anchor-cell guard (1.7.0), `numbers-v6` footnote letters,
the line-start sign and sign-ambiguous dashes (1.8.0). Write each number exactly as
printed. It must be **local** to the claim's
quote by one of two paths (recorded per number as `locality`): inside the
quote (`in-quote`), or in the one lane B row the quote's leading row label
identifies (`row`, 1.3.0). What to quote for a table number:
§ What to quote for a table number below. Rules applied to both the card
string and the page text:
- U+2212, U+2013, U+FE63, U+FF0D directly before a digit → `-`; then NFKC.
- `-` is a sign only at the start, after whitespace or after one of
  `( [ { = < > : ; , / ~`, so "2019-2020" is two positive numbers. From
  `numbers-v4` a dash separated from the number by spaces (and at most one
  line break) is a sign after one of those characters or at the start
  (`Est = - 0.041`, `(- 0.044)`); after a digit it stays a range or
  subtraction (`28 - 75`). From `numbers-v6` (1.8.0, S3-C1b, W-a) it is also
  a sign at a **line start** (only spaces or tabs back to the line break: a
  column-major table cell `– 0.30`). After a letter or a closing bracket
  with a space before the dash (`of – 0.30`, `(n − 1)`, `(Girls) – 0.30`)
  the sign is **ambiguous**: the dash may be a minus or a subtraction or
  range dash. A claim of either sign that only such a token prints is
  `sign-ambiguous` (review, never `ok`); zero excepted. "K-" + line break +
  "12" (no space before the dash) is a compound, not a sign.
- Superscript and subscript characters (`¹`, `²`, `⁻`, `ᵃ`, `₂`) are marks,
  never digits (`numbers-v4`: NFKC used to fold `0.62¹` into `0.621`). A
  superscript the **claim** writes must be printed (it can be an exponent,
  `10⁵`); a claim without one matches a page value that has one (a footnote
  mark left out). Stars and daggers are not compared.
- One **footnote letter** a–g right after a number that ends the word
  (`−0.164a`, `1.20b`, `2017a`, `(7b)`) is read as the number with the letter
  as a mark (`numbers-v6`); write the number without it (`-0.164`), or with
  it, which must then match. Two letters, a digit, or `.`/`-`/`+`/`'` and a
  letter or digit after it keep the old reading (`5mg`, `3rd`, `1e-5`,
  `5a.m.`), and other letters stay non-numbers (`1990s`, `5m`, `2x`).
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
| `NUMBER_SIGN_AMBIGUOUS` | `sign-ambiguous` | (`numbers-v6`, 1.8.0) Inside the claim's quote, the only token printing the claim's digits (either sign) follows a spaced dash after a word or a closing bracket (`of – 0.30`): minus or subtraction is undecided | review |
| `NUMBER_MISSING` | `missing` | Anything else (a changed digit, a dropped minus, the spaced form `= - 0.041` included from `numbers-v4`, a line-start cell `– 0.30` from `numbers-v6`; `both` declares a text reading, so a number in no text lane fails). A minus deleted *inside the quote* is the quote's `QUOTE_NUMBERS_DIFFER` (review, `ladder-v3`), not this | fail |
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
   `PASS_SPAN`, `PASS_OCR_LAYER` or, on arXiv HTML, `PASS_CONVERSION_ERROR`)
   and the quote-number rule held (a `QUOTE_NUMBERS_DIFFER` quote never takes
   the row path). Lane B never anchors a quote;
2. the quote's **leading label** identifies **exactly one** lane B row on
   the page(s) where the quote matched. The leading label is the quote's
   letters before its first number that follows a letter, or the whole quote
   when it holds no such number. A row is a lane B line whose own label (its
   letters before its first number after a letter, at least
   `ROW_LABEL_MIN_CHARS = 3` letters from `numbers-v4`; 2 before) is
   followed by at least one number in a cell-like tail (letters at most
   `ROW_TAIL_LETTER_SHARE_MAX = 0.25` of the tail's non-space characters).
   From `numbers-v4` (1.6.0, S3-A) the row path also needs a page flagged
   `table` or `numeric` (`ROW_PAGE_FLAGS`) and a quote whose anchor match
   begins at a row start (no letter before it on its line), on a single page
   (a declared two-page span never takes the row path). From `numbers-v5`
   (1.7.0) the identified label must also **stand as a cell** on the raw
   anchor line where the quote's match begins: what follows the label on that
   line is cell-like (letters at most 25% of its non-space characters; an
   empty rest counts), so a column-major label alone on its line
   (`Huber-White (HW)`) or a row-major label followed by its cells passes,
   while a prose sentence that merely starts with a label word
   ("ORGANIZATION and other models; …") does not
   (`pdf_text_common.row_label_is_cell()`). Otherwise `row_match` is
   `ineligible`, with the reason.
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
| **Unique row OR inside the quote (`numbers-v3`, shipped in 1.3.0)** | **0.996 / 0.018 / 0.000** | **0.935 / 0.000 / 0.000** |

On script 69's own sample (430 table claims after removing 23 noise rows),
the `numbers-v3` rule cleared 0.277 genuine and B6 1.000, with 0.016 and 0.056
fabricated last digits. Those quotes started at a recurring label: the
`numbers-v3` rule calls 98% of C's quotes `ambiguous`, and B6 clears them by
matching any line that shares the label, including the look-alike rows. Prose
numbers (51 claims from A, B, F): 1.000 genuine and 0.000 fabricated under
both in-quote and the `numbers-v3` rule (script 74).

**Residuals (documented, not caught):**
- (a) *same row, another column.* In a row `Overage 0.58 0.57 0.59 …`, a
  claim of 0.59 for the first column clears: the gate knows the row, not the
  column. The same holds inside a quote that holds the whole row. A validated
  vision cross-check could catch it (none is validated yet). Since 1.5.0
  such a number carries the visible label `column-not-checked` (below).
- (b) *look-alike rows* are closed: under B6, "Time III (Inclusive with
  co-teaching)" matched the "… without co-teaching" row and "Full Sample"
  matched another table's row. Now the label must identify one row, so such
  claims go to review. *Remote rows* (S3-A review, B3) were not closed by
  `numbers-v3`: a prose quote named a prose lane B line ("which …", "of …")
  and cleared its numbers (69 prose windows in four bake-off papers).
  `numbers-v4`'s guards (above) cut that to 6 (S3-A script 93); those left
  start at a row start on a table page with a label a table row shares.
  `numbers-v5`'s anchor-cell guard closed the two holes S3-A2 still found
  (a prose sentence starting with a row-label word; a lane B fragment row
  "the 1" that any quote starting with "the" identified), at the cost of one
  genuine row-path quote on the bake-off papers (now review).

**The column label (`column-check-v1`, 1.5.0, user decision D-23).** The
user asked for residual (a) to be visible "for future reference, and then it
can go to human review if required later on down the line". So a number
that clears now says whether the gate could tell which cell it came from.
This is a **label only**: no number status, verdict or grade changes. Every
number item carries:

| Field | Value |
|-------|-------|
| `column_checked` | `false` when the clearing text prints two or more distinct comparable values; `true` when the claimed value is the only one; `null` when the number did not clear (no `locality`: `missing`, `not-near-quote`, `precision-differs`, `vision-only`, `unparseable`) |
| `column_label` | `"column-not-checked"` when `column_checked` is false, else null |
| `column_values` | The number of distinct comparable values counted (null with `column_checked` null) |
| `column_severity` | `COLUMN_UNCHECKED_SEVERITY` (`"label"`) on a labeled item, else null |

The rule (`pdf_text_common.column_values`):
- **Clearing text.** For `locality: in-quote`, the claim quote's matched span
  in the page text the number was found in (the anchor, or the OCR text for
  `ocr-only` and `ocr+vision`); for `locality: row`, the identified lane B
  row (on HTML, the `rows/` row) after its label, as the row rule reads it.
  Every cleared status gets the label: `ok`, `ocr-layer`, `ocr-layer+vision`,
  `ocr-only`, `ocr+vision`, `conversion-error`.
- **Number token.** The number parser above, one reading only (a plain space
  between digit groups splits). A token that overlaps the token printing the
  claim is the claim itself, so `1 204` read as 1204 is one number, not the
  cells 1 and 204.
- **Comparable.** Same shape as the printed claim: integer vs decimal, and
  with vs without `%`. A count `1,204` is not a candidate for the coefficient
  `0.05`. Parentheses and sign do not split shapes: a coefficient and its SE
  can be confused, and so can a point estimate and its interval bounds.
- **Not counted.** Years (a bare 4-digit integer from `COLUMN_YEAR_MIN =
  1900` to `COLUMN_YEAR_MAX = 2099`, unless the claim is itself a year) and
  reference numbers (an integer right after one of the 32
  `COLUMN_REFERENCE_WORDS`, case-insensitive, an optional `.` after the word:
  `table`, `tables`, `tab`, `figure`, `figures`, `fig`, `figs`, `section`,
  `sections`, `sec`, `chapter`, `ch`, `appendix`, `panel`, `model`, `models`,
  `column`, `columns`, `col`, `equation`, `eq`, `eqs`, `page`, `pages`, `p`,
  `pp`, `note`, `notes`, `footnote`, `step`, `wave`, `hypothesis`; no other
  plural is listed, so "Appendices 2" or "Panels 3" counts). So "In 2019 Table 4 listed 41
  boats on page 3" is one data number, and an ordinary prose sentence with one
  number is not labeled.
- **Values, not tokens.** Distinct digit strings, the claim's own value
  counted once however often it is printed: a row `0.57 0.57` with nothing
  else comparable makes the claim true in either column (`column_checked:
  true`); `0.57 0.59 0.57` does not.

What it costs and catches: on the bake-off cards (FE-5g script 90) the label
fell on the 5 numbers C quotes from one five-cell row, on one HTML number
inside a confidence interval (`7.2% (6.5% - 11.2%)`), and on one HTML number
in a short math expression beside a heading number; no prose sentence with
one number was labeled. The residual it marks was measured at 1.8% of
last-digit fabrications on PDF true-row quotes (FE-5c script 76) and about 9%
on whole-row arXiv HTML quotes (FE-5f script 86). `counts` gains
`numbers_column_not_checked`, the JSON lists the labeled items in
`column_not_checked_items`, and the stdout summary line prints the count
(`… 15 number(s), 5 column-not-checked; …` on C).

**Severity `label` and the review hook.** `label` is a sixth severity level
that no verdict rule reads, and it is never an item's own `severity` (only
its `column_severity`). It is a constant, `COLUMN_UNCHECKED_SEVERITY` in
`lit_verify.py`, recorded in `card_check` `constants`, so a later decision
can route labeled numbers to a human. Set it to `"review"` and every labeled
item's `severity` is raised to review (never lowered), its reason says
"column not checked", and the card becomes NEEDS_REVIEW with no other code
change. Until then, a reviewer or the synthesis stage can read the label and
check those cells by hand. The card needs no change: v1 and v2 cards get the
label alike, and a labeled number is not an error to fix.

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
(`VISION_UNAVAILABLE_CLAIM`).

**Fail-closed on the list (1.6.0).** `lit_verify` embeds the vision-validated
list (`VISION_VALIDATED_LISTS`, one entry per `vision_list_version`; the
current `vision-list-2026-10-19` is empty) and records it in `card_check`
`constants`. `vision_validated: true` for a `reader_model` that is not on the
entry for the card's `vision_list_version`, or for a list version the tool
does not know, is `VISION_NOT_ON_LIST` (fail), and vision then counts as
unavailable, so the card's vision claims also fail as
`VISION_UNAVAILABLE_CLAIM`. Only the block is read: the route is front
matter, so the gate checks the model ID against the version's rows for any
route. Whether the reader really ran as that model, on that route, stays
with the orchestrator's audit (`vision-validation.md` § Gating).

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

## Integrity and warning statuses

Statuses about the ingest and the card as a whole (item `kind` `integrity`,
`card`, `coverage`, `claim` or `paper`), beside the re-derivation statuses
(§ Re-derivation) and the HTML ones above:

| Status | When | Severity |
|--------|------|----------|
| `SOURCE_HASH_MISMATCH` | Card `source_pdf_sha256` (v2: `source_sha256`) differs from the ingest manifest's `source.sha256` | fail |
| `PAPER_KEY_MISMATCH` | Card `paper_key`, or the manifest's `paper_key`, differs from the PAPER_DIR basename | fail |
| `ANCHOR_HASH_MISMATCH` | An anchor file's SHA-256 differs from its manifest record, or page_index's `anchor_sha256` differs from that record | fail |
| `PAGE_INDEX_HASH_MISMATCH` | `page_index{S}.parquet` differs from its manifest record | fail |
| `OCR_HASH_MISMATCH` | An OCR text file differs from its record (the file is then not used) | fail |
| `LANE_B_HASH_MISMATCH` | A lane B file differs from its manifest or page_index record (not used) | fail |
| `INGEST_MANIFEST_HASH_MISMATCH` | The ingest manifest differs from the hash in the pdf_ingest MANIFEST row that wrote it | fail |
| `NO_INGEST_ROW` | No pdf_ingest MANIFEST row in the papers dir records the ingest manifest (a fail from 1.7.0; a warning before) | fail |
| `PAGE_OUT_OF_RANGE` | A coverage entry or a claim cites a page beyond the ingest's page count (the claim is not checked further) | fail |
| `INGEST_SUFFIX_DIFFERS` | The card's `ingest_suffix` is not the suffix checked (hashes decide integrity) | warning |
| `INCOMPLETE_INGEST_IGNORED` | A suffix has artifacts but no ingest manifest (pdf_ingest did not finish); it is never read | warning |
| `NORMALIZE_VERSION_DIFFERS` | The ingest recorded a `NORMALIZE_VERSION` other than the tool's | warning |
| `SPARSE_DECLARATION_MISMATCH` | The card says `sparse: true` for a page (unit) `pdf_ingest` did not flag `scanned` (`sparse`); the class is computed, the field is advisory | warning |
| `VISION_ONLY_IGNORED` | A `vision_only` digest on a page with text: an anchor must cover it | warning |
| `OCR_LAYER_PAPER` | ≥ 2 pages flagged `ocr_layer_suspected` (§ Page classes) | partial |
| `SCANNED_PAGE` | A truly scanned page (§ Page classes) | partial |

An extra `NON_IDENTIFYING`, `NEAR` or `REDACTED_SPAN` anchor on a page that
another anchor covers is downgraded to `warning`.

## Status index

What `lit_verify` 1.8.0 can write, with the severity and the section that
explains each: the 70 keys of `SEVERITY` in `lit_verify.py` (one of them,
`COLUMN_NOT_CHECKED`, is a label, never a status: last row), plus
`COVERED_SPARSE`†. `COVERED_SPARSE` and `COVERED_DUPLICATE` take their
severity from the page (§ Coverage statuses).

† Not a `SEVERITY` key: a coverage status whose severity is set per page.

| Severity | Statuses |
|----------|----------|
| pass | `PASS`, `PASS_SKELETON`, `PASS_SPAN` (§ The match ladder); `COVERED_EMPTY`, `COVERED_DUPLICATE`, `COVERED_SPARSE`† (§ Coverage statuses); `NUMBER_OK` (§ Numbers) |
| partial | `PASS_OCR`, `VISION_ONLY`, `SCANNED_PAGE`, `PASS_OCR_LAYER`, `OCR_LAYER_PAPER` (§ Page classes, § Coverage statuses); `NUMBER_OCR_ONLY`, `NUMBER_OCR_VISION`, `NUMBER_VISION_ONLY`, `NUMBER_OCR_LAYER`, `NUMBER_OCR_LAYER_VISION` (§ Numbers); `PASS_CONVERSION_ERROR`, `NUMBER_CONVERSION_ERROR` (§ arXiv HTML statuses) |
| review | `NEAR`, `REDACTED_SPAN` (§ The match ladder); `QUOTE_NUMBERS_DIFFER` (§ The quote-number rule); `NEEDS_REVIEW` (coverage, § Coverage statuses); `NUMBER_PRECISION_DIFFERS`, `NUMBER_NOT_NEAR_QUOTE`, `NUMBER_SIGN_AMBIGUOUS` (§ Numbers) |
| fail | `WRONG_PAGE`, `NOT_FOUND` (§ The match ladder); `NON_IDENTIFYING` (§ Identifying quotes); `NOT_COVERED`, `MISSING_PAGE` (§ Coverage statuses); `NUMBER_MISSING`, `NUMBER_UNPARSEABLE` (§ Numbers); `VISION_UNAVAILABLE_CLAIM`, `VISION_NOT_ON_LIST` (§ Vision consistency); `ANCHOR_KIND_MISMATCH`, `SOURCE_VERSION_MISMATCH`, `SECTION_NOT_FOUND`, `MISSING_SECTION`, `WRONG_SECTION`, `SECTION_END_NOT_NEXT`, `TABLE_ROWS_HASH_MISMATCH`, `MIXED_ANCHOR_KINDS` (§ arXiv HTML statuses); `SOURCE_HASH_MISMATCH`, `PAPER_KEY_MISMATCH`, `ANCHOR_HASH_MISMATCH`, `PAGE_INDEX_HASH_MISMATCH`, `OCR_HASH_MISMATCH`, `LANE_B_HASH_MISMATCH`, `INGEST_MANIFEST_HASH_MISMATCH`, `NO_INGEST_ROW`, `PAGE_OUT_OF_RANGE` (§ Integrity and warning statuses); `ANCHOR_REDERIVE_MISMATCH`, `ROW_SOURCE_REDERIVE_MISMATCH`, `SOURCE_MISSING`, `SOURCE_FILE_HASH_MISMATCH`, `SOURCE_REDERIVE_ERROR`, `HEADER_FOOTER_REDERIVE_MISMATCH`, `FLAGS_REDERIVE_MISMATCH`, `OCR_ON_TEXT_PAGE` (§ Re-derivation) |
| warning | `INGEST_SUFFIX_DIFFERS`, `INCOMPLETE_INGEST_IGNORED`, `NORMALIZE_VERSION_DIFFERS`, `SPARSE_DECLARATION_MISMATCH`, `VISION_ONLY_IGNORED` (§ Integrity and warning statuses); `HTML_EXTRACT_VERSION_DIFFERS` (§ arXiv HTML statuses); `EXTRACTOR_VERSION_DIFFERS`, `OCR_NOT_REDERIVED`, `ROW_SOURCE_NOT_REDERIVED`, `FLAGS_NOT_REDERIVED` (§ Re-derivation) |
| label | `COLUMN_NOT_CHECKED` (a number item's `column_severity` only, never its `severity`; § Numbers, the column label) |

## Verdicts and grades

Every item carries a severity `pass`, `partial`, `review`, `fail` or
`warning`. A sixth level, `label` (1.5.0), appears only as a number item's
`column_severity` and is ignored by every verdict rule (§ Numbers, the
column label).

| Verdict | When | `evidence_grade_suggested` | Exit |
|---------|------|-----------------------------|------|
| `FAIL` | Any fail item (all listed) | null | 11 |
| `NEEDS_REVIEW` | No fail; a NEAR, REDACTED_SPAN, NEEDS_REVIEW, QUOTE_NUMBERS_DIFFER, precision-differs, not-near-quote or sign-ambiguous item | null; `evidence_grade_if_review_confirmed` = `FULL_TEXT_VERIFIED`, or `FULL_TEXT_PARTIAL` when partial items exist | 0 |
| `PARTIAL` | No fail or review; an OCR_LAYER_PAPER, PASS_OCR, PASS_OCR_LAYER, VISION_ONLY, ocr-only, ocr+vision, ocr-layer, ocr-layer+vision, vision-only, COVERED_SPARSE-on-scanned or SCANNED_PAGE item, or (arXiv HTML) a PASS_CONVERSION_ERROR or conversion-error item | `FULL_TEXT_PARTIAL` | 0 |
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

**1.5.0 (additive; result schema unchanged):** number items also carry
`column_checked`, `column_label`, `column_values` and `column_severity`;
`counts` gains `numbers_column_not_checked` (also in the MANIFEST row's
`counts`); `column_not_checked_items` lists the labeled items; `rule_versions`
gains `column_check` (`column-check-v1`); `constants` gain
`COLUMN_UNCHECKED_SEVERITY`, `COLUMN_YEAR_MIN`, `COLUMN_YEAR_MAX` and
`COLUMN_REFERENCE_WORDS`. `numbers` stayed `numbers-v3`: the label is not a
number rule, so it is versioned apart.

**1.6.0 (additive; result schema unchanged):** `claim_quote` items carry
`quote_numbers`, `page_numbers`, `quote_numbers_agree` and
`status_if_confirmed` (null until the quote-number rule runs on a passing
quote); number items can carry `row_match: "ineligible"` with the reason;
`counts` gains `pages_ocr_layer`; `rule_versions.match_ladder` is
`ladder-v2` and `numbers` `numbers-v4`; `constants` gain
`ROW_TAIL_LETTER_SHARE_MAX`, `ROW_PAGE_FLAGS`, `OCR_LAYER_PAPER_CAP_PAGES`,
`VISION_LIST_VERSION` and `VISION_VALIDATED_LISTS`.

**1.7.0 (additive; result schema unchanged):** a top-level `rederive`
block: `version` (`rederive-v1`), `method`, `source_path`, `source_sha256`,
`extractor`, `extractor_version` (now) and `extractor_version_ingest`,
`anchors_checked`, `anchor_mismatches` and `row_source_mismatches` (lists of
pages or unit labels; `"count"` for a page-count mismatch),
`row_sources_checked`, `ocr` (a note when OCR text was hash-checked only),
`outcome` (`match`, `mismatch`, `source missing`, `source hash mismatch` or
`error`) and `seconds` (1.8.0 adds, still additive: `version`
`rederive-v2`, `read`, `source_kind`, `source_kind_ingest`, `web_fetch_row`,
`header_footer` {records, outcome}, `flags` {pages_checked, mismatches,
table_probed, table_not_rederived_uncited, not_rederived},
`ocr_on_text_pages`; `constants` gain `GRADE_FLAGS`); `rule_versions` gains `rederive` and `numbers` is
`numbers-v5`; `constants` gain `SOURCE_MAX_BYTES`, `REDERIVE_TIMEOUT_S` (the
`--timeout` used) and `REDERIVE_WORKERS`.

**1.8.0, part 2 (S3-C1b; result schema unchanged):** `rule_versions.match_ladder`
is `ladder-v3` and `numbers` `numbers-v6`; a number item can carry the
status `NUMBER_SIGN_AMBIGUOUS` (label `sign-ambiguous`, review, `locality`
null); a `QUOTE_NUMBERS_DIFFER` reason now says whether the digits, a mark
or a sign-shaped dash differ.

## MANIFEST row (papers dir, kind `lit_verify`)

One row per attempt with a valid papers dir: `kind`, `tool_version`,
`command`, `paper_key`, `parameters`, `timestamp`, `requesting_context`,
`card` (path, bytes, SHA-256), `ingest` (suffix, manifest, manifest SHA-256,
page count, and since 1.4.0 `anchor_kind` and `unit_count` (null on PDF)),
`rederive` (1.7.0: `version`, `method`, `outcome`, `anchors_checked`,
`row_sources_checked`, `seconds`, and the counts `anchor_mismatches` and
`row_source_mismatches`; 1.8.0 adds `source_kind`, the `header_footer`
outcome and the counts `flag_mismatches` and `ocr_on_text_pages`),
`artifacts.card_check` (name, bytes, SHA-256),
`verdict`, `evidence_grade_suggested`, `counts`, `redaction_count`,
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
| 10 | Ingest artifacts missing or incomplete (no manifest for the suffix, a missing anchor, OCR, table-rows or page_index file, an unreadable manifest, a manifest with an unknown `anchor_kind`, an HTML manifest without unique unit labels or `arxiv.version`), or a required dependency missing (rapidfuzz; polars or pyarrow; from 1.7.0 pdftotext and pdfinfo, which re-derive PDF anchors; from 1.8.0 pdfimages, which re-derives page flags) |
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
| `QUOTE_NUMBERS_DIFFER` (review) | A minus, range dash, superscript or digit lost when the quote was retyped | Re-copy the quote with every number as printed (§ The quote-number rule); a non-sign dash on the page stays a human check |
| `NUMBER_SIGN_AMBIGUOUS` (review) | The page prints the number after a spaced dash that follows a word or bracket (`of – 0.30`) | Nothing to fix in the card if the number is copied right: a human reads the page (or its render) and decides minus or subtraction |
| `VISION_NOT_ON_LIST` | `vision_validated: true` for a model not on the card's list version | Set `vision_validated: false`, `vision: unavailable`, and re-read flagged pages from the text layer |
| `SOURCE_MISSING` / `SOURCE_FILE_HASH_MISMATCH` | The ingest's source was moved, deleted or replaced after the ingest | Do not edit the card: report it; restore the source to its recorded path or re-ingest |
| `ANCHOR_REDERIVE_MISMATCH` / `ROW_SOURCE_REDERIVE_MISMATCH` | The ingest's files do not re-derive from its source (edited or forged after the ingest) | Do not edit the card: report it; the orchestrator re-ingests |
| `SOURCE_REDERIVE_ERROR` | `pdftotext` or `pdfinfo` failed or timed out on the source | Re-run with a larger `--timeout`; otherwise report it |
| `NO_INGEST_ROW` / `INGEST_MANIFEST_HASH_MISMATCH` | The ingest was not written by a recorded `pdf_ingest` run, or its manifest changed afterwards | Report it; the orchestrator re-ingests |

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
label shared by two rows (both NEEDS_REVIEW via NUMBER_NOT_NEAR_QUOTE), the
column label (1.5.0: the same-row residual number is `column-not-checked`
and a one-number quote on that page is column-checked, verdict still PASS),
and (1.4.0) on a synthetic arXiv HTML paper ingested through `pdf_ingest`'s real
`--source arxiv-html` lane (units `front`, `1`, `1.1` with a table, `2` with
an `ltx_ERROR` span, `bib`): a genuine v2 card with a number found in-quote
and one through its `rows/` row (PASS via NUMBER_OK), a quote cited to
another section (FAIL via WRONG_SECTION), a claim in the conversion-error
section (PARTIAL via PASS_CONVERSION_ERROR), a card pinned to another arXiv
version (FAIL via SOURCE_VERSION_MISMATCH) and a v1 card on the HTML ingest
(FAIL via ANCHOR_KIND_MISMATCH); (1.6.0) on a sign-and-row page: a genuine
spaced minus `= - 0.041` (PASS) and its sign-flipped claim (FAIL via
NUMBER_MISSING), a minus deleted inside a quote (NEEDS_REVIEW via
QUOTE_NUMBERS_DIFFER), a prose quote naming a prose lane B line
(NEEDS_REVIEW via NUMBER_NOT_NEAR_QUOTE) and `vision_validated: true` for a
model not on the list (FAIL via VISION_NOT_ON_LIST); (1.7.0) a forged ingest
set with consistent hashes and a MANIFEST row (FAIL via
ANCHOR_REDERIVE_MISMATCH), an ingest without a pdf_ingest MANIFEST row (FAIL
via NO_INGEST_ROW), and on a column-major page a row label alone on its
anchor line (PASS via NUMBER_OK) and a prose quote starting with that label
(NEEDS_REVIEW via NUMBER_NOT_NEAR_QUOTE); (1.8.0) three forged manifest
fields, each with a forged MANIFEST row: a header/footer record that lets a
span quote skip a printed line (FAIL via HEADER_FOOTER_REDERIVE_MISMATCH),
removed `scanned` / `ocr_layer_suspected` flags (FAIL via
FLAGS_REDERIVE_MISMATCH) and OCR text on a text page (FAIL via
OCR_ON_TEXT_PAGE); (1.8.0, S3-C1b) on a number-parsing page: a genuine
footnote-lettered negative `−0.164a` (PASS), its minus deleted in the quote
and a superscript minus deleted from `10⁻³` (both NEEDS_REVIEW via
QUOTE_NUMBERS_DIFFER), a spaced minus after a word (NEEDS_REVIEW via
NUMBER_SIGN_AMBIGUOUS), and a line-start cell `– 0.25`, genuine (PASS) and
sign-flipped (FAIL via NUMBER_MISSING); plus one check that each card run
wrote one MANIFEST row with a matching `card_check` hash: **43
expectations**. It needs
no PDF tools, but it needs rapidfuzz, polars or pyarrow, **and polars** (the
HTML case is ingested by `pdf_ingest`, which writes its page_index with
polars; without it, exit 10). It removes its work dir and prints
`lit_verify: SELFTEST PASS: 43/43 expectations held; work dir removed`.

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
