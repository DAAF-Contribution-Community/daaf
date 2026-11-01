# Guide: Qualitative Studies (JBI, CASP)

A formal-level guide for qualitative studies (interviews, focus groups,
ethnographies, case studies analysed qualitatively): the JBI checklist by
default, CASP as an alternative. Neither tool has an overall rating rule, and
DAAF does not compute one. Findings that rest on qualitative evidence carry
"certainty not rated: qualitative evidence", because GRADE does not apply to
themes and the qualitative alternative (GRADE-CERQual) is deferred. The
researcher makes every judgment.

## Contents

- [JBI Checklist for Qualitative Research](#jbi-checklist-for-qualitative-research)
- [CASP Qualitative Checklist](#casp-qualitative-checklist)
- [No overall rule](#no-overall-rule)
- [Interpretive items need the researcher most](#interpretive-items-need-the-researcher-most)
- [What to quote](#what-to-quote)
- [How DAAF and the researcher use it](#how-daaf-and-the-researcher-use-it)
- [Why certainty is not rated, and what CERQual would add](#why-certainty-is-not-rated-and-what-cerqual-would-add)
- [Sources](#sources)

## JBI Checklist for Qualitative Research

2024 version (file dated 2026-05); cite as Porritt et al., JBI Manual 2024.
Guide id `jbi-qual`. Ten items answered Yes, No, Unclear (`Y`, `N`, `U`; `NA`
where an item does not apply), paraphrased:

1. "Congruity between the philosophical or theoretical positioning… and the
   methodological approach".
2. Congruity between methodology and the research question.
3. Between methodology and data-collection methods.
4. Between methodology and analysis.
5. Between methodology and interpretation.
6. A "statement locating the researcher culturally or theoretically".
7. The "influence of the researcher… addressed".
8. "Participants, and… their voices, adequately represented".
9. Ethics.
10. "Conclusions… flow from the analysis".

The tool's output is Include, Exclude or Seek further info, not a rating.

## CASP Qualitative Checklist

2024, https://casp-uk.net/casp-checklists/CASP-checklist-qualitative-2024.pdf.
Licence CC BY-NC-SA. Guide id `casp-qual`. Ten questions answered Yes, No, Can't
tell (`Y`, `N`, `CT`), in three sections:

- **A. Are the results valid?** (questions 1–6): aims; whether a qualitative
  methodology is appropriate; design; recruitment; data collection; the
  researcher–participant relationship.
- **B. What are the results?** (7–9): ethics; rigour of analysis; a clear
  statement of findings.
- **C. Will the results help locally?** (10): value.

## No overall rule

CASP gives none: "If there are a large number of 'Can't tell' responses,
consider whether the findings… are trustworthy". JBI's output is an inclusion
decision. The researcher states the study's methodological limitations in
words; to keep a later CERQual adoption cheap, use CERQual's own concern scale
for that statement: no or very minor, minor, moderate or serious concerns
(DAAF's reading: CERQual applies that scale to a review finding, not to one
study).

## Interpretive items need the researcher most

In Shereefdeen et al. 2025 (abstract), GPT-5's agreement with human appraisers
was κ below 0 to 0.46 on CASP and below 0 to 0.83 on JBI; agreement was highest
on reporting items (aims, ethics) and worst on "interpretive and
context-dependent items such as research design, researcher-participant
relationships, and worldview-methodology congruity". Flag JBI items 1, 6, 7 and
8 and CASP question 6 for the researcher's close attention (DAAF's reading:
the mapping of the abstract's categories to these item numbers is DAAF's).

## What to quote

| Item | Quote |
|---|---|
| Positioning and congruity (JBI 1–5; CASP 2–3) | The stated methodology and its rationale, beside the question and the methods |
| Researcher's position and influence (JBI 6–7; CASP 6) | The reflexivity statement, or its absence |
| Participants' voices (JBI 8) | Representative participant quotations the paper uses to support a theme |
| Analysis and conclusions (JBI 10; CASP 8–9) | The analysis method and a conclusion beside the data it rests on |

## How DAAF and the researcher use it

1. The reader drafts an answer and a quote per item, with a reason for any `U`,
   `CT` or `NA`.
2. Each answer is an appraisal claim (`formal-review.md` § Recording checklist
   answers): guide `jbi-qual` or `casp-qual`, item = the item number, answer on
   the tool's scale.
3. The researcher reviews the drafts, states the methodological-limitations
   concern in words, and the record quotes them.

## Why certainty is not rated, and what CERQual would add

GRADE rates certainty in effects; Murad et al. 2017's no-pooling guidance
explicitly excludes "qualitative systematic reviews", and applying GRADE to
themes misreads them. The qualitative counterpart, GRADE-CERQual (Lewin et al.
2018, Implementation Science; PMC5791040, PMC5791047), rates confidence in each
review finding from four components ("methodological limitations, coherence,
adequacy of data and relevance"), each with concerns of "No or very minor /
Minor / Moderate / Serious", starting from "high confidence" and rating down. It
uses "confidence" where DAAF uses "certainty", and its levels describe whether a
finding is "a reasonable representation of the phenomenon of interest", not an
effect.

DAAF has deferred CERQual, so a finding resting on qualitative evidence reads
"certainty not rated: qualitative evidence" (`certainty-language.yaml`
`not_rated.qualitative_evidence`) and uses none of the GRADE hedges. Adopting it
later would add, per finding, judgments of coherence, adequacy and relevance
with a written explanation; the per-study limitations statement above is the
part already in place.

## Sources

JBI Checklist for Qualitative Research (2024); CASP Qualitative Checklist
(2024); Lewin et al. 2018 (GRADE-CERQual series); Murad et al. 2017; Shereefdeen
et al. 2025, Inquiry (PMC12665031, abstract only). Read for DAAF's 2026-10-30
appraisal survey.
