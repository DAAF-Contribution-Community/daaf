---
paper_key: user_00e2e003
title: "pdf_ingest fixture: synthetic LaTeXML (arXiv HTML)"
source_sha256: ec22fbb42125ccda96e5c08af6cf8900eadfab222401766ccfa1b6df4f059169
source_version: v2
vision_mode: "off"
reader_model: example-reader
review_type: example
---

<!--
  EXAMPLE evidence card for lit_verify (schema lit-verify-card-v2, anchor_kind
  arxiv_html), written by hand for DAAF's tests. It describes the SYNTHETIC
  fixture tests/python/fixtures/pdf_ingest/html/synthetic_latexml.html (every
  word in it is invented; no third-party text), ingested with
  `pdf_ingest --source arxiv-html`. lit_verify reads ONLY the single fenced
  block whose info string is `lit-verify` (strict JSON; commentary lives here):

  - Locators are SECTION LABELS as pdf_ingest prints them (ingest_manifest
    units[].label, also in each fulltext unit marker), not pages. Every unit
    1..N needs a coverage entry; this fixture's units are all short, so
    pdf_ingest flags each one `sparse` and a short exact anchor covers it
    (COVERED_SPARSE), e.g. the heading-only unit "2".
  - source_version pins the arXiv version (ingest_manifest arxiv.version);
    source_sha256 is the sha256 of the raw HTML file.
  - vision_mode is "off": HTML units have no page images, so every claim's
    source is "text".
  - Claim X2 spans from section S1 into the next unit S1.SSx1 and declares
    section_end. Claim X3 quotes unit 2.3.1, which holds LaTeXML conversion
    errors (ltx_ERROR), so it is PASS_CONVERSION_ERROR (partial).

  Expected result after `pdf_ingest --source arxiv-html` of the fixture with
  --paper-key user_00e2e003: verdict PARTIAL, evidence_grade_suggested
  FULL_TEXT_PARTIAL (asserted by tests/python/test_lit_verify.py).
-->

# Evidence card: pdf_ingest fixture "synthetic LaTeXML" (example)

```lit-verify
{
  "schema_version": "lit-verify-card-v2",
  "paper_key": "user_00e2e003",
  "anchor_kind": "arxiv_html",
  "source_sha256": "ec22fbb42125ccda96e5c08af6cf8900eadfab222401766ccfa1b6df4f059169",
  "source_version": "v2",
  "ingest_suffix": "",
  "reader_model": "example-reader",
  "vision_mode": "off",
  "vision_validated": false,
  "vision_list_version": null,
  "coverage": [
    {"section": "front", "anchors": ["The violet ferry carried nineteen patient cartographers across the silver estuary."],
     "summary": "title and abstract"},
    {"section": "S1", "anchors": ["The crew logged a tide index of n=207 on the quiet morning"],
     "summary": "harbour tides"},
    {"section": "S1.SSx1", "anchors": ["The unnumbered notes describe the amber lantern beside the northern quay wall."],
     "summary": "unnumbered notes"},
    {"section": "1.2", "anchors": ["A paragraph section stays in its parent unit."], "summary": "Table 1"},
    {"section": "2", "anchors": ["Chapter 2 Lanterns"], "summary": "heading-only chapter unit", "sparse": true},
    {"section": "2.3", "anchors": ["3 Relative numbering"], "summary": "heading-only section", "sparse": true},
    {"section": "2.3.1", "anchors": ["A broken macro \\midsloppy\\inner appears here."],
     "summary": "a LaTeXML conversion error"},
    {"section": "S4", "anchors": ["S4 Supplement"], "summary": "heading only", "sparse": true},
    {"section": "S4.1", "anchors": ["Supplement text about invented herons."], "summary": "supplement"},
    {"section": "A", "anchors": ["Appendix text about the invented copper heron."], "summary": "appendix"},
    {"section": "1", "anchors": ["1. Duplicate number"], "summary": "heading only", "sparse": true},
    {"section": "bib", "anchors": ["Invented, A. (2025). A ledger of tides."], "summary": "references"}
  ],
  "claims": [
    {"claim_id": "X1", "section": "1.2", "quote": "Table 1: Invented tide counts Harbour Spring Autumn North Quay -0.087 1,204",
     "numbers": ["-0.087", "1,204"], "source": "text", "table_ref": "Table 1"},
    {"claim_id": "X2", "section": "S1", "section_end": "S1.SSx1",
     "quote": "The invented gauge was calibrated twice. Unnumbered notes on the ledger", "numbers": [], "source": "text"},
    {"claim_id": "X3", "section": "2.3.1", "quote": "A broken macro \\midsloppy\\inner appears here",
     "numbers": [], "source": "text"},
    {"claim_id": "X4", "section": "S1", "quote": "The crew logged a tide index of n=207 on the quiet morning",
     "numbers": ["207"], "source": "text"}
  ]
}
```
