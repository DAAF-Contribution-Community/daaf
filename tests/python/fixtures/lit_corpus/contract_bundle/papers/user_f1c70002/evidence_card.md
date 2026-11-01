---
paper_key: user_f1c70002
reader_model: fixture-synthetic
---

# Evidence card (synthetic fixture, card v3)

Every word is invented.

```lit-verify
{
  "schema_version": "lit-verify-card-v3",
  "paper_key": "user_f1c70002",
  "anchor_kind": "pdf",
  "source_sha256": "7b998defe2f2c3a71fdd52bda0152585bbe84e0ac4f6d13d0a3caf7c457d496b",
  "ingest_suffix": "",
  "reader_model": "fixture-synthetic",
  "vision_mode": "off",
  "vision_validated": false,
  "vision_list_version": null,
  "coverage": [
    {
      "page": 1,
      "anchors": [
        "The invented policy reached some imaginary districts in 2015 and others in 2018"
      ],
      "summary": "invented"
    }
  ],
  "claims": [
    {
      "claim_id": "D1",
      "page": 1,
      "quote": "The policy raised reading scores by 0.15 standard deviations (standard error 0.06) across 1,830 invented pupils",
      "numbers": [
        "0.15",
        "0.06",
        "1,830"
      ],
      "source": "text",
      "claim_type": "finding",
      "quant": {
        "estimate": "0.15",
        "se": "0.06",
        "n": "1,830",
        "metric": "SD units of reading score"
      }
    },
    {
      "claim_id": "D2",
      "page": 1,
      "quote": "The two pre-period coefficients are small, and adoption was voluntary for every imaginary district",
      "numbers": [],
      "source": "text",
      "claim_type": "limitation",
      "limitation_kind": "reader_assessed"
    },
    {
      "claim_id": "D3",
      "page": 1,
      "quote": "The invented policy reached some imaginary districts in 2015 and others in 2018, and the study compares them in an event study",
      "numbers": [
        "2015",
        "2018"
      ],
      "source": "text",
      "claim_type": "appraisal",
      "appraisal": {
        "guide": "robins-i-v2",
        "item": "D1.1",
        "answer": "PY"
      }
    },
    {
      "claim_id": "D4",
      "page": 1,
      "quote": "The two pre-period coefficients are small, and adoption was voluntary for every imaginary district",
      "numbers": [],
      "source": "text",
      "claim_type": "appraisal",
      "appraisal": {
        "guide": "robins-i-v2",
        "item": "D1.2",
        "answer": "PN"
      }
    }
  ],
  "paper_note": {
    "design": "did",
    "study_weight": "moderate",
    "weight_reason": "Credible event study, but voluntary adoption and a two-point pre-period [D2] leave room for differential trends.",
    "limitation_claim_ids": [
      "D2"
    ],
    "directness": {
      "population": "direct",
      "time": "partly"
    }
  }
}
```
