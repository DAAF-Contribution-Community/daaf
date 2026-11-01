# Guide: Education Effect Studies (WWC v5.0 Lens)

A formal-level guide to the What Works Clearinghouse (WWC) standards as an
**optional lens** for education effect studies. It is recorded beside the
risk-of-bias guide for the design (`guide-randomized.md`,
`guide-nonrandomized.md`), never instead of it. A WWC rating is a judgment about
one study finding's design, not a certainty rating for a body of evidence. The
researcher makes every judgment; DAAF computes nothing.

## Contents

- [Version and source](#version-and-source)
- [Ratings](#ratings)
- [Attrition (randomized trials)](#attrition-randomized-trials)
- [Baseline equivalence](#baseline-equivalence)
- [Rating ceilings](#rating-ceilings)
- [Regression discontinuity standards](#regression-discontinuity-standards)
- [Single-case designs](#single-case-designs)
- [WWC and ESSA labels are not certainty](#wwc-and-essa-labels-are-not-certainty)
- [How DAAF and the researcher use it](#how-daaf-and-the-researcher-use-it)
- [Not verified](#not-verified)

## Version and source

"Current Standards Version 5.0, August 2022 (Revised December 2022)", per
https://ies.ed.gov/ncee/wwc/handbooks (fetched 2026-10-30; no newer version
listed). Handbook PDF: ERIC ED621928. Guide id `wwc5`.

## Ratings

Applied per finding (Handbook Table 3):

| Rating | Meaning (quoted) |
|---|---|
| Meets WWC Standards Without Reservations | "highest degree of confidence that the intervention caused the observed effect" |
| Meets WWC Standards With Reservations | evidence that does "not sufficiently rule out that something other than the intervention caused the observed effect" |
| Does Not Meet WWC Standards | — |

## Attrition (randomized trials)

- "High attrition is defined as potential bias ≥ 0.05 standard deviation"; low
  attrition is below 0.05 SD.
- The boundary between low and high depends on overall and differential
  attrition together, in the Handbook's Appendix C tables (not transcribed:
  look the pair up there).
- Optimistic versus cautious boundary: "If review teams… cannot defensibly
  choose… they should use the cautious assumptions."

## Baseline equivalence

For "all QEDs and compromised RCTs" (Table 10), using the absolute effect size
of the baseline difference:

| Baseline \|ES\| | Result |
|---|---|
| 0.00 to 0.05 | "Satisfies" |
| above 0.05, up to 0.25 | "Requires statistical adjustment" |
| above 0.25 | "Does not satisfy" |

## Rating ceilings

- "Highest possible rating for QEDs is Meets WWC Standards With Reservations".
- Individual RCTs with high attrition are capped at With Reservations.
- A study with a confounding factor (for example an N = 1
  confound) gets Does Not Meet.

## Regression discontinuity standards

Table 14 lists five standards: integrity of the forcing variable; attrition and
baseline equivalence; continuity; functional form and bandwidth; fuzzy RDD.
"Completely satisfy" all five earns Without Reservations; "partially satisfy"
earns With Reservations.

## Single-case designs

v5.0 needs "at least six data points in the initial baseline phases" for
Without Reservations, with an exception for "three or more data points and zero
within-phase variance", and adds a nonoverlap-of-all-pairs "limit risk of bias"
step. Single-case designs are rarely central to DAAF reviews; use the Handbook
directly if they are.

## WWC and ESSA labels are not certainty

- A WWC rating expresses confidence in one study finding's design, not the
  certainty of a body of evidence (DAAF's reading). Use it to inform a study's risk-of-bias
  note and weight, never as a finding's certainty.
- Evidence for ESSA's "Strong" level requires "a statistically significant
  positive effect on at least one major measure". That is a significance-based
  classification, not a certainty rating, and treating it as one is a form of
  vote counting (DAAF's reading). Do not use ESSA levels as quality or
  certainty.

## How DAAF and the researcher use it

1. Decide in the protocol whether the WWC lens applies (education effect
   studies only) and whether the optimistic or cautious attrition boundary is
   used.
2. The reader records, with quotes and numbers: the design (`rct`, `crct`,
   `qed`, `rdd`, `scd`), overall and differential attrition, the baseline
   effect size per outcome and whether the analysis adjusts for it, any
   confounding factor, and for RD each of the five standards.
3. Each item is an appraisal claim (guide `wwc5`; item, e.g. `baseline-es`,
   `attrition-overall`, `rdd-continuity`; answer, e.g. `0.12`, `adjusted`,
   `partial`); numbers go in the claim's `numbers` so they are page-checked.
4. The researcher looks up the attrition boundary, applies the thresholds and
   ceilings above, and states the WWC rating; the record quotes them.

## Not verified

- The Appendix C attrition boundary tables were not read; they are needed to
  call attrition low or high.
- The Handbook's full design standards beyond the items above were not read in
  full.

Sources: WWC Procedures and Standards Handbook v5.0 (ED621928); the WWC
handbooks page; the Evidence for ESSA standards PDF. Read for DAAF's 2026-10-30
appraisal survey.
