# Guide: Randomized Trials (RoB 2)

A formal-level guide to the Cochrane risk-of-bias tool for randomized trials,
version 2 (RoB 2), for a researcher and an agent working through it together.
It states the tool's domains, answer scale and overall rule in words; it does
not reproduce the tool's questions (the tool text is the authors'; consult it)
and it does not compute ratings. The researcher makes every judgment.

## Contents

- [Version and sources](#version-and-sources)
- [Scope: one result](#scope-one-result)
- [Domains](#domains)
- [Answer scale and "no information"](#answer-scale-and-no-information)
- [Domain judgments and the overall rule](#domain-judgments-and-the-overall-rule)
- [What to quote, per domain](#what-to-quote-per-domain)
- [How DAAF and the researcher use it](#how-daaf-and-the-researcher-use-it)
- [Pitfalls](#pitfalls)
- [Not verified](#not-verified)

## Version and sources

| Variant | Version | Source |
|---|---|---|
| Individually randomized, parallel-group | "The current version (22 August 2019)" | https://www.riskofbias.info/welcome/rob-2-0-tool |
| Cluster-randomized | "10 November 2020, revised 18 March 2021" | same |
| Crossover | "8 December 2020, revised 18 March 2021" | same |

Citation: Sterne et al., BMJ 2019;366:l4898. Domain descriptions: Cochrane
Handbook chapter 8 (last updated October 2019),
https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-08.
Record the variant and version used for every appraisal (guide id `rob2`).

## Scope: one result

"The assessment is per result, not per study." Name the result being appraised
(the outcome, the time point and the analysis) before answering anything. A
trial reporting three outcomes the review uses may need three appraisals,
because missing data and outcome measurement often differ by outcome.

Decide with the researcher, in the protocol, which effect is of interest: the
effect of assignment to the intervention (intention to treat) or of adhering
to it (per protocol). Domain 2 has a version for each.

## Domains

"Each domain is required, and no additional domains should be added."

| Domain | Concerns |
|---|---|
| D1 Randomization process | How the sequence was generated and concealed; baseline differences that suggest a problem |
| D2 Deviations from intended interventions | Two versions: effect of assignment, or effect of adhering. Awareness of assignment, deviations that arose because of the trial context, the analysis used |
| D3 Missing outcome data | How much is missing, whether it could depend on the true value, whether the analysis addresses it |
| D4 Measurement of the outcome | Whether the measure is appropriate, whether it could differ between arms, whether assessors knew the assignment and could be influenced |
| D5 Selection of the reported result | Whether the result was chosen from several measurements or analyses after seeing the data |

The domain names and D2's two versions are from the Handbook chapter. The
"Concerns" column is DAAF's short paraphrase, written from general knowledge of
the tool rather than transcribed from its guidance: check it against the tool
before relying on its wording.

## Answer scale and "no information"

Each signalling question is answered **Yes**, **Probably yes**, **Probably
no**, **No** or **No information** (record as `Y`, `PY`, `PN`, `N`, `NI`).
Some questions apply only after a given answer to an earlier one; mark
unreached questions `NA`.

"No information" is "used only when… insufficient details are reported… and…
it would be unreasonable to respond 'Probably yes' or 'Probably no'". Prefer a
`PY` or `PN` with the reasoning when the paper gives a basis for one; `NI` is
not a way to avoid a judgment. The Handbook's example: "in the context of a
large trial run by an experienced clinical trials unit for regulatory
purposes, if specific information about the randomization methods is absent,
it may still be reasonable to respond 'Probably yes' rather than 'No
information' to the signalling question about allocation sequence
concealment."

What an `NI` means depends on the question (Handbook ch.8): "If the question
seeks to identify evidence of a problem, then 'No information' corresponds to
no evidence of that problem. If the question relates to an item that is
expected to be reported (such as whether any participants were lost to
follow-up), then the absence of information leads to concerns about there
being a problem."

## Domain judgments and the overall rule

Each domain is judged **Low risk of bias**, **Some concerns** or **High risk of
bias**. The tool provides an algorithm that maps signalling answers to a
proposed domain judgment; use the tool's own algorithm figures for that (DAAF
has not transcribed them, § Not verified).

The overall rule (Handbook Table 8.2.b), in words:

- **Low:** all domains low.
- **Some concerns:** at least one domain with some concerns, and none high.
- **High:** any domain high, "or… some concerns for multiple domains in a way
  that substantially lowers confidence in the result".

"The overall risk of bias for the result is the least favourable assessment
across the domains" and "can be overridden… with justification". The second
High condition is a judgment: when two or more domains have some concerns, the
researcher decides whether together they lower confidence enough to make the
result High, and records why.

## What to quote, per domain

| Domain | Quote |
|---|---|
| D1 | The sentence describing sequence generation and allocation concealment; the baseline table row or sentence on balance |
| D2 | Blinding of participants and staff; deviations reported; the analysis population (ITT, modified ITT, per protocol) |
| D3 | Numbers randomized and analysed per arm (the flow diagram or table); reasons for missingness; the missing-data method |
| D4 | The outcome measure and who assessed it; blinding of assessors |
| D5 | The registration or pre-analysis plan's outcomes and analyses, and the reported ones (quote both; a mismatch is the evidence) |

Numbers (attrition by arm, sample sizes) go in the claim's `numbers` so the
gate checks them on the page.

## How DAAF and the researcher use it

1. The reader drafts, per signalling question, an answer and a quote; an `NI`
   answer carries a one-line reason ("allocation concealment not described").
2. Each answer backed by a quoted passage is recorded as an appraisal claim:
   guide `rob2`, item = the tool's question number as printed in the version
   used, answer = `Y`, `PY`, `PN`, `N` or `NA`. An `NI` answer rests on the
   paper's silence, so it has no passage to check: it goes in the card's
   Appraisal prose with its reason, not in a claim (`formal-review.md`
   § Recording checklist answers).
3. The researcher reviews the drafts domain by domain, decides each domain
   judgment and the overall judgment, and the appraisal log quotes their
   decision as the researcher's.
4. In the synthesis, the overall judgment informs the risk-of-bias note of the
   finding's certainty (`certainty-of-evidence.md`), weighing each study by its
   size and influence, never by counting.

## Pitfalls

- **Rating the study instead of the result.** Missing data for a 12-month
  outcome says little about the 3-month one.
- **Selective reporting (D5) is where AI is weakest:** κ 0.10 for that domain
  in Eisele-Metzger et al. 2025 (abstract). Compare registered and reported
  outcomes explicitly and flag D5 for the researcher.
- **Over-flagging:** recent reasoning models "consistently over-flag" concerns
  (Nyrhi et al. 2026, abstract). A concern needs a quote.
- **Reading "not reported" the same way for every question.** For a question
  that looks for evidence of a problem, `NI` means no evidence of that problem;
  for an item a trial is expected to report (losses to follow-up, for
  example), its absence is itself a concern (§ Answer scale and "no
  information").
- **Calling a trial "high quality".** The judgment is risk of bias in one
  result.

## Not verified

- The signalling-question numbering (the ids within each domain) has not been
  checked against the full RoB 2 guidance document, which DAAF has not
  fetched. Copy question numbers from the tool version in use, never from
  memory.
- The per-domain algorithms (signalling answers → proposed domain judgment) are
  in the tool's guidance and were not transcribed.
