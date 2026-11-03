---
paper_key: user_f1c70001
reader_model: fixture-synthetic
---

# Evidence card (synthetic fixture, card v3)

Every word is invented.

```lit-verify
{
  "schema_version": "lit-verify-card-v3",
  "paper_key": "user_f1c70001",
  "anchor_kind": "pdf",
  "source_sha256": "08bc13463551f3a99a13ae262e5b1584106b9c5181f8644e5769e983ddb7e6dc",
  "ingest_suffix": "",
  "reader_model": "fixture-synthetic",
  "vision_mode": "off",
  "vision_validated": false,
  "vision_list_version": null,
  "coverage": [
    {
      "page": 1,
      "anchors": [
        "The invented tutoring trial randomly assigned 412 pupils in nine imaginary schools"
      ],
      "summary": "invented"
    },
    {
      "page": 2,
      "anchors": [
        "Teachers in the comparison schools kept their usual reading lessons for the whole year"
      ],
      "summary": "invented"
    }
  ],
  "claims": [
    {
      "claim_id": "C1",
      "page": 1,
      "quote": "Reading scores rose by 0.21 standard deviations (standard error 0.05) after one invented school year",
      "numbers": [
        "0.21",
        "0.05"
      ],
      "source": "text",
      "claim_type": "finding",
      "quant": {
        "estimate": "0.21",
        "se": "0.05",
        "metric": "SD units of reading score"
      }
    },
    {
      "claim_id": "C2",
      "page": 1,
      "quote": "The invented tutoring trial randomly assigned 412 pupils in nine imaginary schools to small reading groups",
      "numbers": [
        "412"
      ],
      "source": "text",
      "claim_type": "method",
      "quant": {
        "n": "412"
      }
    },
    {
      "claim_id": "C3",
      "page": 1,
      "quote": "Attrition was 6 percent in each arm, and the authors call the single district a limitation of the study",
      "numbers": [
        "6"
      ],
      "source": "text",
      "claim_type": "limitation",
      "limitation_kind": "author_stated"
    },
    {
      "claim_id": "C9",
      "page": 1,
      "quote": "The invented trial ran in a single imaginary district with mild winters and small classes",
      "numbers": [],
      "source": "text",
      "claim_type": "method"
    }
  ],
  "paper_note": {
    "design": "rct",
    "study_weight": "substantial",
    "weight_reason": "Randomized with low, balanced attrition; the single district [C3] limits directness, not the estimate.",
    "limitation_claim_ids": [
      "C3"
    ],
    "directness": {
      "population": "direct",
      "setting": "partly"
    }
  }
}
```
