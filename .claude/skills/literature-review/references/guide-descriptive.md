# Guide: Descriptive, Correlational and Cross-Sectional Studies

A formal-level guide for studies that describe or correlate rather than
estimate an intervention's effect: surveys, cross-sectional studies,
administrative-data descriptions, correlational analyses. Two published tools
(JBI's analytical cross-sectional checklist and AXIS) supply the items; **DAAF's
descriptive checklist** below adapts them for social-science studies. None of
them has a published overall rating rule, and DAAF does not compute one. The
researcher makes every judgment.

## Contents

- [The published tools](#the-published-tools)
- [DAAF descriptive checklist](#daaf-descriptive-checklist)
- [No score](#no-score)
- [What to quote](#what-to-quote)
- [How DAAF and the researcher use it](#how-daaf-and-the-researcher-use-it)
- [Pitfalls](#pitfalls)
- [Sources](#sources)

## The published tools

**JBI Assessment of Risk of Bias for Analytical Cross-sectional Studies
(2026).** Barker et al., JBI Evidence Synthesis 2026;24(3):401-8. Guide id
`jbi-xs`. Eight items (paraphrased):

1. Inclusion criteria.
2. Objective criteria for the condition (per outcome).
3. Exposure "measured in a valid and reliable way".
4. Outcomes measured validly (per outcome).
5. "Confounding factors identified".
6. "Strategies to deal with confounding factors stated".
7. "Appropriate statistical analysis" (per result).
8. Subjects and setting described.

Items are grouped by internal validity (domain of bias), statistical-conclusion
validity and comprehensiveness of reporting. Answers Yes, No, Unclear (`Y`, `N`,
`U`), plus `NA`. The tool's output is Include, Exclude or Seek further info, not
a rating.

**AXIS** (Downes et al. 2016, BMJ Open, PMC5168618). Guide id `axis`. 20 items,
including sample-frame representativeness (Q5–6), non-response (Q7, Q13–14),
measurement validity (Q8–9), whether "conclusions [were] justified by the
results" (Q17) and funding and conflicts of interest (Q19). "A numerical scale
to reflect quality was not included."

Both are health-origin tools. Their items (sampling, measurement validity,
confounding acknowledged, analysis matching the claim) port to survey and
administrative-data studies with rewording, which is what DAAF's checklist does.

## DAAF descriptive checklist

**This checklist is DAAF's adaptation, not a published tool.** Record answers
under guide `other` with item ids `DS1`…`DS8`, or answer the source tool's items
directly under `jbi-xs` or `axis` if the protocol prefers.

| Id | Item (paraphrase) | Core? | Source items |
|---|---|---|---|
| `DS1` | The sample frame and selection make the sample representative of the target population | core | AXIS Q5–6; JBI-XS 1 |
| `DS2` | Non-response addressed and described | — | AXIS Q7, Q13–14 |
| `DS3` | Exposure or predictor measured validly and reliably | core | JBI-XS 3; AXIS Q8 |
| `DS4` | Outcome measured validly and reliably | core | JBI-XS 4; AXIS Q9 |
| `DS5` | Confounders identified | — | JBI-XS 5 |
| `DS6` | Confounding addressed (only when the paper's claim is explanatory) | core if explanatory | JBI-XS 6 |
| `DS7` | Analysis appropriate to the claim (no causal reading of a correlation) | core | JBI-XS 7 |
| `DS8` | Conclusions justified by the results | core | AXIS Q17 |

Answers: `Y`, `N`, `U` (unclear), `NA`.

**Overall concern (DAAF's suggestion, for the researcher to accept or not in
the protocol):** any core item answered N points to high concern; any core item
U, with none N, to some concerns; otherwise low concern. This is a prompt for
the researcher's judgment, not a published rule, and DAAF never applies it on
its own.

## No score

Do not count Yes answers into a score. AXIS deliberately has no numerical
scale, and JBI outputs a decision, not a number. A score hides which item
matters for the result the review uses: a representative sample does not
rescue a causal reading of a correlation.

## What to quote

| Item | Quote |
|---|---|
| `DS1` | The sampling frame, the selection procedure, the response rate |
| `DS2` | Non-response figures and any weighting or comparison of responders with non-responders |
| `DS3`, `DS4` | The measure, its source and any validity or reliability evidence cited |
| `DS5`, `DS6` | The control variables or design feature, and the sentence stating the claim's type (descriptive or explanatory) |
| `DS7` | The model or comparison used and the sentence interpreting it |
| `DS8` | The conclusion sentence beside the result it rests on |

## How DAAF and the researcher use it

1. The reader drafts an answer and a quote per item; an `NA` or `U` carries a
   one-line reason.
2. Each answer is an appraisal claim (`formal-review.md` § Recording checklist
   answers).
3. The researcher reviews the answers, states the overall concern in their own
   words, and the record quotes them.
4. In the synthesis, descriptive evidence supports descriptive findings; a
   finding about effects resting only on correlational studies is worded with
   "is associated with" and a low starting point for certainty
   (`certainty-of-evidence.md`).

## Pitfalls

- **Causal language from correlational studies.** Check the paper's own
  conclusion against its design (`data-scientist` `references/research-questions.md`
  § Causal vs. Correlational Language).
- **Star scores.** The Newcastle–Ottawa scale gives stars; DAAF's survey did not
  read it and does not use it.
- **Treating a large sample as a valid sample.** Size does not fix a biased
  frame.

## Sources

Barker et al. 2026 (JBI analytical cross-sectional); Downes et al. 2016 (AXIS).
Read for DAAF's 2026-10-30 appraisal survey.
