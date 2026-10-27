---
paper_key: user_00e2e002
title: "pdf_ingest fixture: multipage"
source_pdf_sha256: fa6a68eebb16f7f68fc4574539d976b051dd67f289d41768a6c0579e50c8f002
vision_mode: auto
reader_model: example-reader
review_type: example
---

<!--
  EXAMPLE evidence card for lit_verify (schema lit-verify-card-v1), written by
  hand for DAAF's tests. It describes the SYNTHETIC fixture
  tests/python/fixtures/pdf_ingest/pdf/multipage.pdf (every word in it is
  invented; no third-party text). The front matter and prose sections are
  free-form (the Literature Review output contract formalizes them later).
  lit_verify reads ONLY the
  single fenced block whose info string is `lit-verify`, which must be strict
  JSON (JSON allows no comments, so the commentary lives here):

  - coverage: one entry per page 1..N; each anchor is a VERBATIM sentence
    from that page. Page 2's anchor keeps the real hyphen in
    "natural-language" while pdftotext fused it ("naturallanguage"): it
    passes as PASS_SKELETON. Page 4 is sparse (a figure page with a caption,
    flagged scanned by pdf_ingest but not mostly one image): its caption is
    long and unique, so it passes as PASS. Page 5 is TRULY scanned (one image
    covers about 61% of the page), so its anchor comes from the OCR text
    (PASS_OCR) and the page adds a SCANNED_PAGE item.
  - claims: numbers are written as printed ("-3" matches the page's U+2212
    minus; "(2.1)" is an SE in parentheses, not a negative number). Claim M2
    is read from OCR text, so its number is labeled ocr-only.

  Expected result after `pdf_ingest` of multipage.pdf with --paper-key
  user_00e2e002: verdict PARTIAL, evidence_grade_suggested FULL_TEXT_PARTIAL
  (asserted by tests/python/test_lit_verify.py).
-->

# Evidence card: pdf_ingest fixture "multipage" (example)

## 1. Reading coverage ledger

| Page | Digest |
|---|---|
| 1 | Plain prose; the planted sentence about the violet ferry. |
| 2 | Two columns; the method relies on natural-language summaries. |
| 3 | Table 1, invented counts (gulls, boats) with SEs in parentheses. |
| 4 | Figure 1 (an embedded raster) with its caption. |
| 5 | An image-only page, read through its OCR text. |

## 6. Findings table

| Claim | Estimate | Uncertainty | Page | Ref | Source |
|---|---|---|---|---|---|
| M1 | 14; -3 | (2.1) | 3 | Table 1 | text |
| M2 | 58 boats | | 5 | | ocr |
| M3 | gulls counted in threes | | 2 | | text |

```lit-verify
{
  "schema_version": "lit-verify-card-v1",
  "paper_key": "user_00e2e002",
  "source_pdf_sha256": "fa6a68eebb16f7f68fc4574539d976b051dd67f289d41768a6c0579e50c8f002",
  "ingest_suffix": "",
  "reader_model": "example-reader",
  "vision_mode": "auto",
  "vision_validated": false,
  "vision_list_version": null,
  "coverage": [
    {"page": 1, "anchors": ["The violet ferry carried nineteen patient cartographers across the silver estuary."],
     "summary": "plain prose; planted sentence"},
    {"page": 2, "anchors": ["relies on natural-language summaries of each imaginary voyage"],
     "summary": "two columns; method"},
    {"page": 3, "anchors": ["The table above is invented and exists only to exercise the table flag."],
     "summary": "Table 1"},
    {"page": 4, "anchors": ["Figure 1: Invented bar heights from the imaginary voyage"],
     "summary": "figure page", "sparse": true},
    {"page": 5, "anchors": ["LANTERN 4821 OTTER 3907 MEADOW 1265 The quiet harbour kept 58 copper boats."],
     "summary": "image-only page, OCR text"}
  ],
  "claims": [
    {"claim_id": "M1", "page": 3, "quote": "Low tide High tide Gulls Boats 14 −3 (2.1) (0.8) 27",
     "numbers": ["14", "-3", "(2.1)", "27"], "source": "text", "table_ref": "Table 1"},
    {"claim_id": "M2", "page": 5, "quote": "MEADOW 1265 The quiet harbour kept 58 copper boats.",
     "numbers": ["58"], "source": "ocr"},
    {"claim_id": "M3", "page": 2, "quote": "the harbour pilot counted gulls in threes and rounded every total down",
     "numbers": [], "source": "text"}
  ]
}
```
