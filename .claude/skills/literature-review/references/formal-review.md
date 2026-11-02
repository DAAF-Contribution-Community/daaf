# Formal or Systematic Review

The formal level is a researcher-led process: a written protocol, explicit
inclusion rules, a second screener, published appraisal checklists used as
guides, and a GRADE-style rating of each conclusion. DAAF supplies the
checklists, drafts answers with quotes, keeps every record and checks every
quote and citation; the researcher makes the judgment calls. Nothing in this
level computes a rating.

## Contents

- [What the formal level adds](#what-the-formal-level-adds)
- [Who decides what](#who-decides-what)
- [The protocol](#the-protocol)
- [Routing a study to a guide](#routing-a-study-to-a-guide)
- [Working through a checklist with the researcher](#working-through-a-checklist-with-the-researcher)
- [Recording checklist answers](#recording-checklist-answers)
- [The researcher's certainty rating](#the-researchers-certainty-rating)
- [Reporting](#reporting)
- [What is deferred, and why](#what-is-deferred-and-why)

## What the formal level adds

Everything in a standard review (`standard-review.md`), read for every included
paper rather than key papers only, plus:

- a protocol written and approved before searching;
- a second screener: by default a second **person** deciding independently on
  every full text (Cochrane's standard), and on titles and abstracts as the
  protocol says, with disagreements resolved by the researcher
  (`screening.md` § A second screener);
- a published checklist per study design, worked through with the researcher
  (the `guide-*.md` files);
- a GRADE-style certainty rating per finding, decided by the researcher with
  notes per domain (`certainty-of-evidence.md`);
- reporting to PRISMA 2020 (or PRISMA-ScR) and a full AI disclosure.

## Who decides what

| Task | DAAF | The researcher |
|---|---|---|
| Protocol | Drafts from the intent menu and parameters | Approves; owns every change |
| Screening | Primary screener; records every decision | Provides the second person for full-text decisions (themselves or a colleague); resolves disagreements; decides borderline cases |
| Reading | Reads every included paper into a page-checked card | Spot-checks cards; settles items marked for review |
| Checklists | Picks the guide by design; drafts an answer and a quote for each item | Confirms or changes each answer; decides every domain and overall judgment |
| Certainty | Drafts notes per GRADE domain, citing claim ids | Decides the rating; the rating is recorded as theirs |
| Wording | Words each finding from `certainty-language.yaml` | Approves the synthesis |

Why the split: language models answer checklist items better than they
aggregate them. In published tests their RoB 2 judgments agreed with humans at
κ 0.06–0.22 (Eisele-Metzger et al. 2025; Nyrhi et al. 2026; abstracts), and
stated judgments diverged from their own answers to the tool's
questions in a mean 42% of domain-2 judgments, with skip-logic violations in
69–100% of runs (Choi et al. 2026, abstract). Choi et al. recommend having the
model make only "atomic (single) judgments". At this level, the atomic
judgments are drafts and the aggregation is the researcher's.

## The protocol

Write it before the first search; version it on every change
(`review-types-and-levels.md` § Changing level or re-steering). Contents:

1. The question, in its frame (PICO, PECO, PCC, SPIDER).
2. Inclusion and exclusion criteria, and the exclusion reason codes.
3. Sources, search strings (or how they will be developed), dates, limits,
   grey literature and preprint policy.
4. The stopping rule (for a systematic review: exhaustive completion).
5. Seed papers for recall.
6. Screening: who the second screener is (a person on every full text by
   default; an AI second screener is a declared deviation, named here and in
   the AI disclosure), which title-and-abstract records they also screen, and
   how disagreements are resolved.
7. Reading: every included paper in full; what happens to papers without
   obtainable full text.
8. Appraisal: which guide per design (§ Routing), and any protocol choices the
   guide leaves open (e.g. RoB 2's effect of assignment or of adherence). For
   an umbrella review, the AMSTAR 2 critical items: Box 1 by default, with any
   additions or substitutions and their reasons (`guide-reviews.md`).
9. Synthesis method (`synthesis-methods.md`) and grouping of studies; any
   pre-specified moderators.
10. Certainty: GRADE-style rating by the researcher; which findings are not
    rated (qualitative evidence).
11. Reporting standard and the AI disclosure plan.

## Routing a study to a guide

| Design | Guide | File |
|---|---|---|
| Individually randomized, cluster-randomized or crossover trial | RoB 2 (guide id `rob2`) | `guide-randomized.md` |
| Cohort-type non-randomized study of an intervention | ROBINS-I V2 (`robins-i-v2`) | `guide-nonrandomized.md` |
| DiD, RD, IV, synthetic control, ITS, matching | ROBINS-I V2 domains plus DAAF's design checks (`robins-i-v2`; DAAF's adaptation: V2 is written for cohort studies; its domains are used here as prompts) | `guide-nonrandomized.md` |
| Exposure that is not a deliberate intervention | ROBINS-E (`robins-e`) | `guide-nonrandomized.md` |
| Education effect study (optional lens, beside the above, never instead) | WWC v5.0 (`wwc5`) | `guide-education-wwc.md` |
| Descriptive, correlational, cross-sectional, survey | JBI analytical cross-sectional (`jbi-xs`), AXIS (`axis`), DAAF's descriptive checklist | `guide-descriptive.md` |
| Qualitative | JBI qualitative (`jbi-qual`) or CASP (`casp-qual`) | `guide-qualitative.md` |
| Systematic review (umbrella reviews) | AMSTAR 2 (`amstar2`) | `guide-reviews.md` |
| Theory or conceptual paper | DAAF's profile (`theory`) | `guide-theory.md` |

The tool follows the design of the result being appraised, not the paper's
label. A paper with two designs (a trial plus an observational follow-up) gets
one checklist per result the review uses.

## Working through a checklist with the researcher

1. The reader has already made the page-checked card (`pdf-reading`).
2. Pick the guide by design; name the result being appraised (outcome and
   analysis), because most tools judge one result, not a whole study.
3. For each item, draft an answer on the tool's scale and quote the passage
   that supports it, with its page. If the paper is silent, say so (each guide
   says what silence means for that tool).
4. Present the drafts to the researcher, domain by domain, with the quotes.
   Mark the items language models handle worst (selective reporting,
   interpretive items) for close attention.
5. The researcher confirms or changes each answer and states each domain
   judgment and the overall judgment, using the tool's own rule as a guide.
   Record their words.

## Recording checklist answers

Each answer backed by a passage is a claim in the paper's card, so its quote
gets the same page check as any other claim. An answer that rests on the
paper's silence (`NI`, "not reported") has no passage to check: it goes in the
card's Appraisal prose with its one-line reason, not in a claim.

**Card v3:** `claim_type: appraisal` with an `appraisal` object
`{guide, item, answer}`. `guide` is one of `rob2`, `robins-i-v2`, `robins-e`,
`wwc5`, `amstar2`, `jbi-qual`, `casp-qual`, `jbi-xs`, `axis`, `theory`, `other`;
`item` and `answer` are short strings (at most 40 characters) in the tool's own
numbering and scale ("1.2", "PY"). The card stores answers only: no question
tables, no answer scales, no computed ratings.

**Older cards (v1 and v2):** each answer is an ordinary claim whose `claim`
text starts with the guide, item and answer ("rob2 1.2 PY: …"); the quote is
page-checked as usual. Write new cards as v3: `lit_corpus claims build` then
lists the answers as `appraisal` rows of the claims table.

**The researcher's judgments** (each answer confirmed or changed, each domain
and the overall judgment) are recorded in the review's appraisal log,
`output/appraisal_log_v{N}.md`, which the orchestrator writes after each
checklist review: per paper, the guide, the result judged and the judgments,
with the researcher's own words quoted and the date. They never go into the
card: a card that `lit_verify card` checked is never edited, and the reader's
drafted answers stay as drafted. A weight the researcher confirms or changes
is recorded with `lit_corpus notes record`, `decided_by.role: researcher` and
their words in `decided_by.researcher_instruction`; a later `claims build`
keeps that note rather than the reader's. A judgment that differs from the
tool's own rule is fine; record why.

## The researcher's certainty rating

At this level a finding's certainty is `researcher_grade`: the researcher's
GRADE-style judgment, with notes per domain (risk of bias, inconsistency,
indirectness, imprecision, publication bias; and any reason to rate up). DAAF
drafts the notes with claim ids; the researcher decides. The record names the
researcher as decider and quotes their instruction; a `researcher_grade`
without that record is refused by `lit_corpus findings record` (exit 11).
How to reason about each domain without a pooled estimate:
`certainty-of-evidence.md`.

## Reporting

- **PRISMA 2020** for systematic reviews, PRISMA-ScR for scoping reviews,
  PRISMA-S for the search (DAAF's search log covers its items). Flow-diagram
  counts are built by hand from the screening log at present.
- **SWiM** for synthesis without meta-analysis (`synthesis-methods.md`).
- **AI disclosure (RAISE):** what was AI-judged (screening drafts, checklist
  drafts, synthesis drafts), what code verified (citations, quotes, numbers,
  wording), and that the researcher made every judgment call. The position
  statement of Cochrane, Campbell, JBI and CEE holds authors "ultimately
  responsible" and asks that any AI that "makes or suggests judgements" be
  "fully and transparently reported".
- Attach the protocol and its versions, the screening log, the checklists with
  answers and judgments, and the certainty notes.

## What is deferred, and why

The following were designed but are not built, by the researcher's choice to
keep formal appraisal researcher-led: computed domain and overall ratings for
each tool; certainty computed from a start level plus recorded moves; adaptive
dual screening with κ and escalation; PRISMA flow-diagram counts. They may
return later as an encoded formal level. Until then, the guides state each
tool's own rules in words so the researcher can apply them, and nothing in DAAF
presents a computed rating as if a tool had produced it.
