# Synthesis Methods

How to put the evidence together once papers are read: which method fits the
review type, how to report a synthesis without meta-analysis (SWiM), the two
numeric summaries DAAF allows (a labelled descriptive summary and a sign test on
directions) and the guardrails that keep prose honest. DAAF never pools,
averages or weights effects across studies into one number. Statements about
what several studies show together are the point of a synthesis, and are
worded at the finding's certainty (§ Guardrails).

## Contents

- [Method by review type](#method-by-review-type)
- [Reporting a synthesis without meta-analysis (SWiM)](#reporting-a-synthesis-without-meta-analysis-swim)
- [Descriptive summary](#descriptive-summary)
- [Direction of effect and the sign test](#direction-of-effect-and-the-sign-test)
- [Guardrails](#guardrails)
- [Ordering, sensitivity and disagreement](#ordering-sensitivity-and-disagreement)
- [Exploratory moderators](#exploratory-moderators)
- [Sources](#sources)

## Method by review type

The machine id in brackets is the finding's `synthesis_method` value
(`certainty-of-evidence.md` § Finding record fields).

| Method | Fits | Core moves | Source |
|---|---|---|---|
| SWiM-structured synthesis (`swim`) | Effect questions (systematic, rapid) | Group studies, standardize the metric, prioritize results, describe heterogeneity, present a table of each study's estimate | Campbell et al. 2020 |
| Narrative synthesis (`narrative`) | Effect or implementation questions with mixed designs | Four elements: a theory of how the intervention works, a preliminary synthesis, exploring relationships, assessing robustness | Popay et al. 2006 (snippet only) |
| Thematic synthesis (`thematic`) | Qualitative evidence | Line-by-line coding, descriptive themes, then analytical themes; it "preserves an explicit and transparent link between conclusions and the text of primary studies" | Thomas & Harden 2008 |
| Concept matrix (`concept_matrix`) | Conceptual and integrative reviews; related work | Articles × concepts (optionally × unit of analysis); a review "is concept-centric" | Webster & Watson 2002 |
| Evidence and gap map (`egm`) | Gap and scoping questions | A grid of interventions × outcomes; categories "fully comprehensive and mutually exclusive"; aim for "4–6 row and column heads each with 4–6 subcategories"; keep a dictionary of terms | Campbell EGM guidance |
| Realist synthesis (`realist`) | "What works for whom under what circumstances, how and why?" | Context–mechanism–outcome configurations; RAMESES publication standards (19) | RAMESES |
| Umbrella table (`umbrella`) | Reviews of reviews | One row per review: question, studies, conclusions, AMSTAR 2 confidence, overlap (`guide-reviews.md`) | — |

## Reporting a synthesis without meta-analysis (SWiM)

The nine SWiM items (Campbell et al. 2020, BMJ 368:l6890, Table 1; item names
verbatim):

1. Grouping studies for synthesis (1a "description of, and rationale for, the
   groups"; 1b "changes made subsequent to the protocol").
2. Describe the standardised metric and transformation methods used.
3. Describe the synthesis methods.
4. Criteria used to prioritise results for summary and synthesis.
5. Investigation of heterogeneity in reported effects.
6. Certainty of evidence.
7. Data presentation methods ("Specify key study characteristics (eg, study
   design, risk of bias) used to order the studies").
8. Reporting results ("Describe the result in language that is consistent with
   the question the synthesis addresses, and indicate which studies
   contribute").
9. Limitations of the synthesis.

SWiM is a reporting guideline, not a guide to conduct or quality ("this is not
an appropriate application of a reporting guideline"), and not for qualitative
synthesis (ENTREQ or eMERGe cover that). It is written for systematic
reviews: follow it at the formal level for effect questions. At the standard
level it is optional, a checklist of what to say; items 1–4, 6 and 8 are the
ones a reader most needs.

## Descriptive summary

Allowed only when **at least 3 estimates, one per paper (so at least 3 papers),
share a common metric**. Report the unweighted **median, interquartile range
and range**, and always label it "descriptive summary, not a pooled estimate".

- Why the label: Cochrane ch.12 says these statistics do "not account for
  differences in the relative sizes of the studies" and their "performance…
  has not been evaluated"; the label keeps a reader from taking them as a
  meta-analytic result.
- Why at least 3: ch.12 calls box plots "not appropriate when there are few
  studies"; the threshold of 3 is DAAF's choice.
- Never across different metrics (SWiM item 2): standardize first or do not
  summarize.
- Every estimate must be a page-checked number from a paper read in full; never
  from an abstract.
- Template (`certainty-language.yaml` `descriptive_summary.template`): "Across
  {k} studies reporting {metric}, the estimates ranged from {min} to {max}
  (median {median}; IQR {q1} to {q3}; descriptive summary, not a pooled
  estimate)."
- Computing it: `lit_corpus findings record` computes it from the claims
  table when a finding names a `descriptive_summary` (claim ids and metric);
  it refuses fewer than 3 estimates from 3 papers, two estimates from one
  paper, mixed metrics, and any estimate not checked on its page
  (`lit-corpus.md` § Findings, summaries, sign tests). Never compute it by mental
  arithmetic or type the numbers in.

Nothing weighted, averaged or pooled: no "average effect", "overall effect",
"pooled estimate", "weighted mean" or "typical effect" given as a number. A
number that describes several studies' effects comes only from this summary,
or, for directions, from the sign test below.

## Direction of effect and the sign test

When effect sizes cannot be put on a common metric, count **directions**, not
significance. Cochrane ch.12: "Neither statistical significance nor the size of
the effect are considered in the categorization. A sign test can be used… An
estimate of the proportion of effects favouring the intervention… p = u/n…
along with a confidence interval (e.g. using the Wilson or Jeffreys interval
methods)."

Report it as: "{u} of {n} effects favoured the intervention (sign test p =
{p}; proportion {u/n}, 95% CI {lo} to {hi})". This is the one counting sentence
the guardrails allow. `lit_corpus findings record` computes it from a
finding's `direction_summary` (exact two-sided binomial p, Wilson interval).
Studies whose direction is unclear or null (`none`) are excluded from n and
reported separately (`excluded_none`).

## Guardrails

Each guardrail, why it exists, and the `lit_verify report` check that enforces
it (all statuses, reasons and exits: `lit-verify-report.md`).

| Guardrail | Why | Check |
|---|---|---|
| No vote counting by significance ("7 of 10 studies found significant effects") | "Vote counting based on statistical significance… [is] unacceptable" (ch.12): small studies miss real effects | `VOTE_COUNT_SIGNIFICANCE` (fail) |
| No informal counts ("most studies found", "the majority of studies", "few studies") | Ch.12 flags them as unintentional vote counting | `VOTE_COUNT_INFORMAL` (review) |
| No pooled, averaged or weighted effect number credited to several studies (cross-study wording without such a number is fine; below) | Studies differ in design and quality; one number hides it | `POOLED_ESTIMATE`, `WEIGHTED_SUMMARY` (fail) |
| Descriptive summaries only under the rule above, labelled | They are unweighted and unevaluated | `DESCRIPTIVE_SUMMARY_UNLABELED`, `…_UNSUPPORTED` (fail) |
| Wording no stronger than the finding's certainty | Readers take strong verbs as settled | `CERTAINTY_STRONGER` (fail) |
| "Per abstract" on every abstract-only citation, and on a citation of a paper read in full when every claim the sentence marks from it comes from its abstract; no numbers from abstracts | Abstracts overstate and omit limitations | `ABSTRACT_ONLY_UNLABELED`, `ABSTRACT_ONLY_NUMBER` (fail) |
| No "statistically significant" in finding sentences | Significance is not size or certainty (Cochrane ch.15) | `SIGNIFICANCE_LABEL` (review) |
| No "no effect" or "no difference" as a conclusion | Absence of evidence is not evidence of absence | `NO_EFFECT_CLAIM` (fail) |
| No boosters ("proves", "clearly demonstrates") | Reviews rarely settle anything that firmly | `BOOSTER` (fail) |
| Post-hoc moderators labelled "exploratory" | They generate hypotheses, not answers | `POST_HOC_UNLABELED` (fail) |
| "Disputes" or "contradicts" only on a reader-quoted sentence | Citation counts and intents carry no disagreement | `EDGE_RELATION_UNSUPPORTED` (review) |

**Statements across studies.** A review exists to say what several studies
show together, so words such as "overall", "taken together" and "across
studies" are fine in a finding sentence worded at the finding's certainty. The
pooling check fails only one effect number credited to several studies, a
number nobody computed:

| Sentence | Result |
|---|---|
| "Taken together, the three trials indicate that tutoring probably improves reading scores [@a; @b; @c]." (moderate finding) | Passes: a cross-study statement at its certainty, with no number |
| "Overall, the two studies indicate that tutoring may improve attendance [@a; @d]." (low finding) | Passes |
| "Taken together, tutoring raised reading scores by 0.15 SD [@a; @b; @c]." | Fails: one number credited to three studies |
| "Across 3 studies reporting reading scores in SD units, the estimates ranged from 0.09 to 0.21 (median 0.15; IQR 0.12 to 0.18; descriptive summary, not a pooled estimate) [@a; @b; @c]." | Passes when `lit_corpus` computed these numbers for the marked finding (§ Descriptive summary) |

The sentences above are shown without their finding markers; in a deliverable
each sits inside its `{.lr-finding …}` marker (`lit-verify-report.md`). Each
cross-study sentence rests on its finding's stated synthesis method and on a
table of each study's estimate, so the reader can see which studies the words
summarize (SWiM item 8: "indicate which studies contribute"). Cochrane ch.12
warns that statements about how consistent the studies are ("the majority of
studies showed improvement") may amount to unintentional vote counting; the
table shows the reader what such a sentence rests on.

## Ordering, sensitivity and disagreement

- **Order by weight and directness,** not by how many studies agree (SWiM item
  7 orders by key characteristics such as design and risk of bias). Papers
  given substantial weight anchor statements; papers given limited weight are
  labelled context.
- **Sensitivity reasoning** whenever a finding could rest on weaker papers
  (`standard-review.md` § Sensitivity reasoning).
- **Disagreement** is explained through design, quality, directness or context
  before any "mixed evidence" label. Cochrane ch.10: with "inconsistency in the
  direction of effect, it may be misleading to quote an average".
- **Read the result blinded:** ask how the conclusion would be framed if the
  direction were reversed (Cochrane §15.6.4).

## Exploratory moderators

A moderator pattern noticed after reading the results (for example, "effects
look larger in rural districts") is exploratory: label it "exploratory", never
let it set a finding's certainty, and say it needs testing. A moderator named
in the protocol before reading is "pre-specified". The labels follow
`creative-verification` `references/interpretation-and-evidence.md` § Four-Way
Test Labeling; post-hoc heterogeneity explorations "can at best lead to the
generation of hypotheses" (Cochrane ch.10).

## Sources

Campbell et al. 2020, BMJ 368:l6890 (PMC7190266); Cochrane Handbook ch.10, ch.12
(McKenzie & Brennan, last updated October 2019) and ch.15; Thomas & Harden 2008;
Webster & Watson 2002; the Campbell evidence-and-gap-map guidance (PMC8356343);
RAMESES publication standards. Read for DAAF's 2026-10-02 methodology survey and
2026-10-30 appraisal survey; Popay et al. 2006 from a snippet only.
