# Paper Notes

The per-paper record at the standard and formal levels: what kind of study it
is, its main limitations quoted with their pages, how much weight it should
carry in the synthesis and why, and how directly it speaks to the review
question. A paper note is a reasoned judgment written out in full, not a score;
the formal level adds checklist answers on top (`formal-review.md`).

## Contents

- [Fields](#fields)
- [Design labels](#design-labels)
- [Quoted limitations](#quoted-limitations)
- [Weight](#weight)
- [Directness](#directness)
- [Signals that are not quality](#signals-that-are-not-quality)
- [Prompts by design](#prompts-by-design)
- [Where the note lives](#where-the-note-lives)
- [Worked example](#worked-example)
- [Pitfalls](#pitfalls)

## Fields

| Field | Content | Rule |
|---|---|---|
| `design` | One label from § Design labels | Quote where the paper states its design |
| limitations | The main limitations, each a quoted, page-checked claim | Author-stated and reader-assessed kept apart |
| `study_weight` | `substantial`, `moderate` or `limited` | Never a number; never "high quality" |
| `weight_reason` | Two to five sentences naming the limitation claims that drive the weight | Must cite at least one limitation claim, or say why none matter |
| directness | Population, intervention or exposure, comparator, outcome, setting, time: each `direct`, `partly` or `indirect` | Optional: rate the parts that matter for the question. Relative to the review question, not the paper's own |
| reader confidence | H, M or L with a one-line reason | Confidence in the reading (e.g. a garbled table), not in the study |

The weight words are deliberately different from the certainty words (high,
moderate, low, very low): weight belongs to one paper, certainty to a
conclusion drawn across papers.

## Design labels

`rct`, `crct` (cluster-randomized), `crossover`, `cohort`, `did`
(difference-in-differences or event study), `rd` (regression discontinuity),
`iv` (instrumental variables), `synthetic_control`, `its` (interrupted time
series), `matching` (selection on observables), `exposure_cohort` (an exposure
that is not a deliberate intervention), `cross_sectional`, `survey`,
`qualitative`, `systematic_review`, `theory`, `other` (say what).

Label the design the paper actually uses, not the one it claims in its title. A
"natural experiment" that compares adopters with non-adopters on observables is
`matching`, and the note says so.

## Quoted limitations

The limitations carry the note, so each is a claim with a verbatim quote and a
page, checked by `lit_verify card` like any other claim. Record two kinds,
labelled:

- **Author-stated:** what the paper itself says limits its result ("our sample
  is drawn from a single district", "attrition was 31% in the control group").
- **Reader-assessed:** what the reader sees that the paper does not concede,
  anchored on the passage that shows it (a table with no pre-period, a
  sentence describing self-selection into treatment). Phrase the assessment in
  the note; quote the evidence for it.

A limitation without a quote is an opinion. If the paper is silent on
something that matters (no attrition reported), say "not reported" in the note
and treat it as a limitation: Waddington et al. 2026 advise that information
"not stated… becomes equivalent to 'No' or 'Probably No'".

## Weight

| Weight | Use when | Typical pattern |
|---|---|---|
| `substantial` | The design answers the question credibly and no limitation threatens the result the review uses | A randomized trial with low attrition and pre-specified outcomes; a quasi-experiment whose key checks are reported and hold |
| `moderate` | Credible, but one or more limitations could plausibly move the result | A well-identified study in a setting only partly like the review's; a trial with notable attrition handled by sensitivity analysis |
| `limited` | The result could well be an artifact of the design or reporting, or it barely speaks to the question | Self-selection with only observed controls; outcome measures the authors built and did not validate; a small single-site pilot |

The weight reason names the claims that drive it: "Limited: participation was
voluntary [W123-c07, p. 4] and the comparison group differs at baseline on prior
achievement [W123-c09, p. 11]; no sensitivity analysis is reported."

**What weight is not.**

- Not a checklist score: no items are counted and nothing is summed (AMSTAR 2
  and AXIS both refuse scores; DAAF follows them).
- Not a quality label for the paper as a whole: Waddington et al. 2026 advise
  to "avoid reporting risk-of-bias assessments as markers of the quality of a
  study". Weight is about the result the review uses.
- Not a prediction of direction: Waddington et al. also warn against "assuming
  that studies at 'high risk of bias' will de facto over-estimate a treatment
  effect".
- Not a verdict on the authors.

## Directness

Rate the parts that matter for the question (not every part needs a rating),
each against the review question, with a short reason:

| Part | Direct | Partly | Indirect |
|---|---|---|---|
| Population | Same group (e.g. grade 3–5 public-school pupils in the US) | Overlapping (grades 1–8) | Different (adult learners) |
| Intervention or exposure | Same program or exposure | Similar mechanism, different delivery | Related concept only |
| Comparator | The comparison the question needs | A different but informative comparison | No relevant comparison |
| Outcome | The outcome asked about | A proxy (attendance for engagement) | A distant proxy |
| Setting | Same system and context | Similar system | Very different system |
| Time | Current enough for the question | Older but conditions similar | Conditions have changed |

Directness feeds certainty (indirectness is one of the five GRADE domains,
`certainty-of-evidence.md`). The reader drafts it; the synthesizer settles it
across papers.

## Signals that are not quality

These may appear as context, labelled, but never set a weight:

- **Citation counts, venue prestige, journal quartile:** popularity and
  context, not validity.
- **Peer-review status and preprint versus published version:** recorded facts;
  they matter only through a specific consequence ("the outcome changed between
  the working paper and the journal version").
- **Retraction or expression of concern:** a hard flag. The paper is excluded
  from findings unless the researcher decides otherwise, and is labelled
  "retracted" wherever cited.
- **Scite contradicting tallies:** prompt a re-read; never a verdict.
- **Funding and conflicts of interest:** recorded and noted, not scored.

## Prompts by design

Questions worth asking while writing the note. They are prompts, not
checklists: the formal-level guides hold the published checklists.

| Design | Ask |
|---|---|
| Randomized trial | How was assignment done and concealed? Attrition overall and by arm? Were outcomes and analyses pre-specified? Deviations from assignment? |
| DiD / event study | Are pre-period trends shown? Any anticipation or change in who is measured? Staggered timing handled with a heterogeneity-robust estimator? |
| RD | Any bunching at the cutoff? Results across bandwidths and functional forms? Covariates continuous at the cutoff? |
| IV | First-stage strength reported? Is the exclusion argued, not assumed? |
| Matching, regression on observables | Overlap and balance shown? Is selection plausibly explained by what was observed? |
| Synthetic control | Pre-period fit shown? Donor pool justified? Placebo tests? |
| Descriptive, survey | Sample frame and non-response? Measures valid? Does the analysis match the claim (no causal reading of a correlation)? |
| Qualitative | Is the researcher's position stated? Do participants' voices support the themes? |
| Review | Protocol? Search adequate? Risk of bias considered in the conclusions? |

Design threats in depth: `data-scientist` `references/causal-inference.md`
§ Threats to Validity Checklist and § Parallel Trends.

## Where the note lives

**Card v3 (`lit_verify` 1.9.0, built):** each limitation is a claim with
`claim_type: limitation` and `limitation_kind`: `author_stated` (the authors
name it) or `reader_assessed` (the reader names it, quoting the passage that
shows it). An optional `paper_note` block holds `design`, `study_weight`,
`weight_reason` (required with a weight), `limitation_claim_ids` and
`directness`; the gate refuses the card (exit 8) unless every listed id exists
in the card and is a limitation claim. `lit_corpus claims build` collects the
notes into the `paper_notes_v{N}` table (`lit-corpus.md`); `lit_corpus notes
record` records a synthesizer's or the researcher's later note.

**Older cards (schema v1 and v2):** limitations are ordinary claims whose
`claim` text starts "Limitation (author-stated):" or "Limitation
(reader-assessed):", with the design label, weight, reason and directness in
the card's prose sections (Appraisal; Relevance and directness), naming the
claim ids. They still check; write new cards as v3.

## Worked example

> **Design:** `did`; "we compare districts that adopted the policy in 2015 with
> those that adopted later, using an event-study specification" [c02, p. 6].
>
> **Limitations.** Author-stated: "adoption was voluntary, and early adopters
> had higher baseline spending" [c07, p. 9]. Reader-assessed: the event-study
> figure shows two pre-period coefficients, both positive [c11, p. 14], so the
> pre-period is short; no sensitivity analysis to trend violations is reported
> (not reported).
>
> **Weight:** moderate. The design is credible and pre-trends are shown, but
> self-selection on spending [c07] and a two-point pre-period [c11] leave room
> for differential trends; the main estimate could move.
>
> **Directness:** population direct; intervention direct; comparator partly
> (later adopters, not never-adopters); outcome direct; setting direct; time
> partly (2012–2018).
>
> **Reader confidence:** H; tables read from the text layer, numbers checked.

## Pitfalls

- **Summing.** Counting problems into a score hides which problem matters for
  the result.
- **Quality by reputation.** A famous paper in a top journal can still have a
  limitation that matters here.
- **Weight from abstracts.** A paper read only at the abstract has no weight;
  it is "per abstract" context.
- **AI blind spots.** Selective reporting and interpretive items are where
  language models agree least with human appraisers (Eisele-Metzger et al.
  2025; Lai et al. 2024; Shereefdeen et al. 2025; abstracts). Check registered
  or pre-specified outcomes against those reported, and flag these judgments
  for the researcher.
- **Copying the authors' framing.** Author-stated and reader-assessed
  limitations stay apart, so the researcher can see where the reader disagrees
  with the paper.
