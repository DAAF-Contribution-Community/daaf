---
paper_key: user_00e2e001
source_pdf_sha256: a98f43df329bf965e1bb009737994b94996ac6a4d299c666bff29ecb161e9c69
---

<!-- Synthetic test card (hand-written for DAAF's tests) for the synthetic
     fixture tests/python/fixtures/pdf_ingest/pdf/single_column.pdf. Every
     quote is verbatim from that one-page fixture. Expected: PASS,
     FULL_TEXT_VERIFIED. -->

# Evidence card: pdf_ingest fixture "single_column" (genuine)

```lit-verify
{
  "schema_version": "lit-verify-card-v1",
  "paper_key": "user_00e2e001",
  "source_pdf_sha256": "a98f43df329bf965e1bb009737994b94996ac6a4d299c666bff29ecb161e9c69",
  "reader_model": "test-reader",
  "vision_mode": "off",
  "vision_validated": false,
  "vision_list_version": null,
  "coverage": [
    {"page": 1, "anchors": ["The cobalt heron recorded eleven quiet tides beside the amber lighthouse before dawn."],
     "summary": "single-column prose with the planted sentence"}
  ],
  "claims": [
    {"claim_id": "S1", "page": 1,
     "quote": "The surveyors walked along the gravel path, compared their notes on the weather",
     "numbers": [], "source": "text"}
  ]
}
```
