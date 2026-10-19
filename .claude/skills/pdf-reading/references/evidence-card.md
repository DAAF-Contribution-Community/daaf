# The evidence card and the `lit_verify card` gate

How to write an evidence card that `scripts/lit_verify.sh card` can verify,
what every check and status means, and how to fix a failing card. Source of
truth: the header, `validate_card()`, `check_card()` and the selftest in
`scripts/lit_verify.py` (`TOOL_VERSION = "1.0.0-daaf"`, 2026-10-15; card
schema `lit-verify-card-v1`, result schema `lit-verify-card-check-v1`) and
the ladder and number rules in `scripts/pdf_text_common.py`
(`ladder-v1`, `numbers-v1`). A later session adds `lit_verify report` (S4);
the full card schema is formalized later in `LIT_REVIEW_OUTPUT_CONTRACT.md`
(spec C14). If this page and the code disagree, the code wins.

**Contents:** Syntax · Card anatomy · Front matter · The lit-verify block ·
Checks in order · The match ladder · Identifying quotes · Page classes ·
Coverage statuses · Numbers · Vision consistency · Verdicts and grades ·
card_check JSON · MANIFEST row · Exit codes · Fixing a failing card ·
Selftest · Worked example

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
`review_type`. This skill adds the vision-gating fields that the block does
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

## Checks in order

1. **Integrity.** Card `source_pdf_sha256` = manifest; card `paper_key` =
   manifest `paper_key` = PAPER_DIR basename; each anchor file's SHA-256 =
   the manifest record and the page_index record; page_index.parquet = its
   manifest record; each OCR text file used = its record (a mismatching OCR
   file is not used); the ingest manifest = the hash in the pdf_ingest
   MANIFEST row (no row: warning `NO_INGEST_ROW`). An ingest made with another
   `NORMALIZE_VERSION`: warning.
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
OCR text when it matched in OCR). Both thresholds are **PROVISIONAL**
(calibrated in the S3 bake-off); uniqueness is the real test, because short
common phrases ("citation quality") recur dozens of times in one paper.
Otherwise the status is `NON_IDENTIFYING` (a claim quote fails; a NEAR on a
short quote is NON_IDENTIFYING too).

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

## Coverage statuses (per page)

| Status | When | Severity |
|--------|------|----------|
| `PASS` | An identifying text-layer anchor passes | pass |
| `COVERED_SPARSE` | The sparse waiver applied | pass on a sparse text page; partial on a scanned page or via OCR |
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

## Numbers (`numbers-v1`)

Write each number exactly as printed. Rules applied to both the card string
and the page text:
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
| `NUMBER_OK` | `ok` | Same value and digits in the cited page's anchor text | pass |
| `NUMBER_OCR_ONLY` | `ocr-only` | Only in that page's OCR text | partial |
| `NUMBER_OCR_VISION` | `ocr+vision` | Only in OCR text, claim `source` `both` (vision corroborates) | partial (the paper still relies on OCR, Q-A) |
| `NUMBER_VISION_ONLY` | `vision-only` | In no text lane, claim `source` `vision` | partial |
| `NUMBER_PRECISION_DIFFERS` | `precision-differs` | Same value, other digits | review |
| `NUMBER_MISSING` | `missing` | Anything else (a changed digit, a dropped minus; `both` declares a text reading, so a number in no text lane fails) | fail |
| `NUMBER_UNPARSEABLE` | `unparseable` | The card string is not one number | fail |

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

## Verdicts and grades

Every item carries a severity `pass`, `partial`, `review`, `fail` or
`warning`.

| Verdict | When | `evidence_grade_suggested` | Exit |
|---------|------|-----------------------------|------|
| `FAIL` | Any fail item (all listed) | null | 11 |
| `NEEDS_REVIEW` | No fail; a NEAR, REDACTED_SPAN, NEEDS_REVIEW or precision-differs item | null; `evidence_grade_if_review_confirmed` = `FULL_TEXT_VERIFIED`, or `FULL_TEXT_PARTIAL` when partial items exist | 0 |
| `PARTIAL` | No fail or review; a PASS_OCR, VISION_ONLY, ocr-only, ocr+vision, vision-only, COVERED_SPARSE-on-scanned or SCANNED_PAGE item | `FULL_TEXT_PARTIAL` | 0 |
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
`warnings`, `pages` (class, image area, coverage status per page) and
`items`. Card quotes in it are injection-scrubbed and secret-redacted, with
the original quote's SHA-256 kept. **It holds no page text.**

## MANIFEST row (papers dir, kind `lit_verify`)

One row per attempt with a valid papers dir: `kind`, `tool_version`,
`command`, `paper_key`, `parameters`, `timestamp`, `requesting_context`,
`card` (path, bytes, SHA-256), `ingest` (suffix, manifest, manifest SHA-256,
page count), `artifacts.card_check` (name, bytes, SHA-256), `verdict`,
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
| 8 | Card cannot be parsed (missing, duplicate or invalid lit-verify block; oversize or non-UTF-8 card) |
| 10 | Ingest artifacts missing or incomplete (no manifest for the suffix, a missing anchor, OCR or page_index file, an unreadable manifest), or a required library missing (rapidfuzz; polars or pyarrow) |
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
| `VISION_UNAVAILABLE_CLAIM` | A `vision`/`both` claim with vision unavailable | Use `text` (or `ocr`) with a text quote, or drop the claim and note it |
| `MISSING_PAGE` / `NOT_COVERED` | A page skipped, or only short anchors on a normal page | Add an identifying anchor for that page |
| `*_HASH_MISMATCH` | The ingest or card changed after it was written | Do not "fix" the card: report it; the orchestrator re-ingests |

## Selftest

`lit_verify.sh selftest <SCRATCH_DIR>` builds synthetic ingests in a work dir
under `SCRATCH_DIR`, plants fabrications in cards, runs the real card gate on
each and checks every expected verdict: a genuine card (PASS), one digit
changed, a quote cited to the adjacent page, an invented 12-word quote, a
dropped minus sign, a non-identifying short quote, a tampered anchor file, a
vision claim on a `vision_validated: false` card (all FAIL), a synonym-swap
paraphrase (NEEDS_REVIEW via NEAR), an OCR quote on a truly scanned page
(PARTIAL via PASS_OCR), the fused compound hyphen (PASS_SKELETON) and a
sparse non-image page (COVERED_SPARSE), plus one check that each card run
wrote one MANIFEST row with a matching `card_check` hash: 13 expectations.
It needs no PDF tools (rapidfuzz and polars or pyarrow only), removes its work
dir, and prints `lit_verify: SELFTEST PASS: 13/13 expectations held; work dir
removed`.

## Worked example

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
