# Guide: Systematic Reviews in an Umbrella Review (AMSTAR 2)

A formal-level guide to AMSTAR 2, the appraisal tool for systematic reviews,
for umbrella reviews (reviews of reviews). It states the tool's critical items
and its overall rule in words; it does not reproduce the items' text and does
not compute ratings. The researcher makes every judgment.

## Contents

- [Version and source](#version-and-source)
- [Items and critical domains](#items-and-critical-domains)
- [Answers and missing information](#answers-and-missing-information)
- [The overall rule](#the-overall-rule)
- [Reviews without a meta-analysis](#reviews-without-a-meta-analysis)
- [Overlap between reviews](#overlap-between-reviews)
- [How DAAF and the researcher use it](#how-daaf-and-the-researcher-use-it)
- [Not verified](#not-verified)

## Version and source

Shea et al., BMJ 2017;358:j4008 (PMC5833365). Guide id `amstar2`. 16 items.
"AMSTAR 2 is not intended to generate an overall score."

## Items and critical domains

Shea et al. list seven critical items (Box 1):

| Item | Critical domain |
|---|---|
| 2 | Protocol registered |
| 4 | Adequacy of the literature search |
| 7 | Justification for excluding studies |
| 9 | Risk of bias of included studies |
| 11 | Meta-analytic methods |
| 13 | Risk of bias considered in interpretation |
| 15 | Publication bias |

The other nine items are non-critical by default; read their wording in Shea
et al. 2017 (DAAF has not transcribed them).

Box 1 is a default, not a fixed list: "our listing is a suggestion and
appraisers may add or substitute other critical domains" (their examples:
leaving out non-randomised studies, item 3, in a review of adverse outcomes;
failing to explain large variations in effects, item 14), and "we recommend
defining critical domains before starting an appraisal". So the protocol names
the critical items before any review is appraised: Box 1 unless the researcher
adds or substitutes items, with a reason for each change
(`formal-review.md` § The protocol).

## Answers and missing information

Answer each item on the tool's scale (Yes, Partial yes where the item offers
it, No; `NA` where an item does not apply). Missing information is rated "No":
a review that does not report something has not shown it.

## The overall rule

From Box 2, which the authors call "advisory": "appraisers should decide which
items are most important for the reviews under consideration".

| Overall confidence | Rule |
|---|---|
| High | "No or one non-critical weakness" |
| Moderate | "More than one non-critical weakness"* |
| Low | "One critical flaw with or without non-critical weaknesses" |
| Critically low | "More than one critical flaw with or without non-critical weaknesses"; such a review "should not be relied on" |

\* Box 2's footnote: "Multiple non-critical weaknesses may diminish confidence
in the review and it may be appropriate to move the overall appraisal down
from moderate to low confidence".

A No on an item the protocol lists as critical is a critical flaw; a No on any
other item is a weakness. Never add items up: the tool refuses a score.

## Reviews without a meta-analysis

Item 11 (meta-analytic methods) does not apply when the review has no
meta-analysis (whether items 12 and 15 also lapse is DAAF's inference: see
§ Not verified). The appraiser should instead be "alert to… risk of bias when
review authors select individual studies to highlight in a narrative summary";
record that under item 13 with a quote.

## Overlap between reviews

Reviews in an umbrella review often include the same primary studies. List the
primary studies behind each finding and count a shared study once; say in the
synthesis when two reviews agree because they rest on the same studies. (DAAF's
convention; no overlap statistic is computed.)

## How DAAF and the researcher use it

1. The reader drafts an answer and a quote per item; a No for missing
   information quotes the section where the information would be.
2. Each answer is an appraisal claim (`formal-review.md` § Recording checklist
   answers): guide `amstar2`, item `1` to `16`, answer `Y`, `PY`, `N` or `NA`.
3. The researcher confirms or changes each answer and, using the critical
   items the protocol fixed (§ Items and critical domains), states the overall
   confidence by the rule above, including whether several weaknesses move a
   Moderate down to Low; the record quotes them.
4. A review rated Critically low is not relied on for findings; if it is
   mentioned, the synthesis says why.

At the standard level, an umbrella review's paper notes use the seven critical
items as prompts for the quoted limitations, without the formal rating.

## Not verified

- Whether items 12 and 15, like item 11, do not apply without a meta-analysis
  (DAAF's inference; check against Shea et al. 2017).
- Whether a Partial yes counts as a weakness (DAAF's understanding is that it
  does not; check against the paper).
- The wording of the nine non-critical items.
