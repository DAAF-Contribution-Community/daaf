---
paper_key: user_f1c70003
reader_model: fixture-synthetic
---

# Evidence card (synthetic fixture, card v3)

Every word is invented.

```lit-verify
{
  "schema_version": "lit-verify-card-v3",
  "paper_key": "user_f1c70003",
  "anchor_kind": "pdf",
  "source_sha256": "b03f3336b9c74a6b327f927debff47ca33b16420ede65c64afd7256b2680b7f8",
  "ingest_suffix": "",
  "reader_model": "fixture-synthetic",
  "vision_mode": "off",
  "vision_validated": false,
  "vision_list_version": null,
  "coverage": [
    {
      "page": 1,
      "anchors": [
        "The survey measured library hours once, and the authors note that families who chose late libraries"
      ],
      "summary": "invented"
    }
  ],
  "claims": [
    {
      "claim_id": "S1",
      "page": 1,
      "quote": "In an invented survey of 2,560 pupils, reading scores were 0.09 standard deviations (standard error 0.03) higher where libraries opened late",
      "numbers": [
        "2,560",
        "0.09",
        "0.03"
      ],
      "source": "text",
      "claim_type": "finding",
      "quant": {
        "estimate": "0.09",
        "se": "0.03",
        "n": "2,560",
        "metric": "SD units of reading score"
      }
    },
    {
      "claim_id": "S2",
      "page": 1,
      "quote": "The survey measured library hours once, and the authors note that families who chose late libraries may differ",
      "numbers": [],
      "source": "text",
      "claim_type": "limitation",
      "limitation_kind": "author_stated"
    }
  ],
  "paper_note": {
    "design": "cross_sectional",
    "study_weight": "limited",
    "weight_reason": "One cross-sectional survey; self-selection of families [S2] could explain the difference.",
    "limitation_claim_ids": [
      "S2"
    ]
  }
}
```
