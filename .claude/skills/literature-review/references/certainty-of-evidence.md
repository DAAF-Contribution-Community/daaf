# Certainty of Evidence

How to state how sure we can be about a synthesized finding, without pooling
any numbers. At the standard level the synthesizer **states** a certainty
(high, moderate, low, very low) and writes the reason; at the formal level the
**researcher** decides it, GRADE-style, with notes per domain. Nothing is
computed: GRADE's domains are prompts for a written judgment, not arithmetic.
The words that each level allows are in `certainty-language.yaml`.

## Contents

- [What certainty is, and is not](#what-certainty-is-and-is-not)
- [Where to start](#where-to-start)
- [The five reasons to be less sure](#the-five-reasons-to-be-less-sure)
- [Reasons to be more sure](#reasons-to-be-more-sure)
- [Writing the reason (standard level)](#writing-the-reason-standard-level)
- [The researcher's rating (formal level)](#the-researchers-rating-formal-level)
- [Not rated](#not-rated)
- [Finding record fields](#finding-record-fields)
- [Choosing the words](#choosing-the-words)
- [Worked examples](#worked-examples)
- [Not verified](#not-verified)
- [Sources](#sources)

## What certainty is, and is not

Certainty belongs to a **finding**, a conclusion drawn across the papers that
bear on it. It is not a paper's weight (`paper-notes.md`), not the reader's
confidence in a card, and not a gap's confidence. The four levels, in the words
shown to readers (`certainty-language.yaml` `plain_meaning`):

| Level | Plain meaning |
|---|---|
| high | We are confident this is true; further research is very unlikely to change it. |
| moderate | This is probably true; better studies might change it. |
| low | This may be true, but better studies could well change it. |
| very low | We do not know whether this is true; the evidence is very weak. |

## Where to start

Think first about the designs behind the finding:

- A body of randomized trials, or of studies whose design rules out the main
  rival explanations, can support high certainty if nothing below holds it
  down.
- Non-randomized studies start, in practice, at **low**. Cochrane notes that
  with ROBINS-I "all studies may start as high certainty", but "a body of
  evidence from NRSI should generally be downgraded by two levels due to the
  inherent risk of bias associated with the lack of randomization, namely
  confounding and selection bias. Not downgrading NRSI from high to low
  certainty needs transparent and detailed justification for what mitigates
  concerns about confounding and selection bias … Very few examples of where
  not rating down by two levels is appropriate currently exist", and "review
  authors will generally grade evidence from sound non-randomized studies as
  low certainty, even if ROBINS-I is used" (Handbook ch.14).
- Quasi-experiments (DiD, RD, IV, synthetic control) are non-randomized
  studies, so the same starting point applies. **DAAF's reading** for social
  science: design checks that are reported and hold (`guide-nonrandomized.md`
  § DAAF design checks for quasi-experiments) can be the "transparent and detailed justification"
  Cochrane asks for, so a body of such studies may be stated at moderate, but
  only when the reason says what mitigates confounding and selection and names
  the claim ids that show it. Without that, stay at low. A body of
  correlational studies stays at low or very low for any claim about effects.
- Descriptive findings (prevalence, trends, gaps between groups) are judged on
  whether the samples and measures answer the descriptive question, not on
  causal design.

This is where reasoning begins, not a number to adjust.

## The five reasons to be less sure

GRADE's five domains, with Murad et al. 2017's advice for applying each when
there is no pooled estimate (quoted from its Table 1):

| Domain | Ask | Without pooling (Murad et al. 2017) |
|---|---|---|
| Risk of bias | Do the papers given most weight have limitations that could move the result? | "Make a judgement on the risk of bias across studies for an individual outcome… consider the size of a study, its risk of bias and the impact it would have on the summarised effect." |
| Inconsistency | Do results differ in direction or size in ways no known moderator explains? | "Judge inconsistency by evaluating the consistency of the direction and primarily the difference in the magnitude of effects across studies (since statistical measures of heterogeneity are not available)." |
| Indirectness | Do populations, interventions, comparators, outcomes, settings or times differ from the question? (paper notes' directness) | "Make a global judgement on how dissimilar the research evidence is to the clinical question at hand." |
| Imprecision | Are there few studies or small samples; do the largest studies' intervals include both no effect and an important effect? | "Consider the optimal information size (or the total number of events for binary outcomes and the number of participants in continuous outcomes) across all studies. A threshold of 400 or less is concerning for imprecision. Results may also be imprecise when the CIs of all the studies or of the largest studies include no effect and clinically meaningful benefits or harms." |
| Publication bias | Might results be missing? | "Suspected when the body of evidence consists of only small positive studies or when studies are reported in trial registries but not published. Statistical evaluation… is not possible… more likely if the search… is not comprehensive." |

For a yes-or-no outcome (graduation, retention), the 400 counts **events**
(pupils who graduated, or who did not), not pupils. For clustered designs
(pupils in schools), 400 pupils carry less information than 400 independent
participants; judge imprecision with clustering in mind (DAAF's adaptation).

**Signals that results may be missing,** without a funnel plot (Cochrane
ch.13 and ROB-ME, whose non-statistical signals carry over): outcomes
"pre-specified" in registries, protocols or analysis plans compared with
"those for which results are available"; outcomes "expected to have been
measured"; search comprehensiveness, including languages; "time-lag bias"; and
"the typical size and complexity of eligible studies" (large studies are hard to
hide; small, cheap ones are not). Social-science registries worth checking
include the AEA RCT Registry, OSF Registries and SREE's registry (DAAF's
inference; not verified in the survey). An outcome that changed between a
working paper and the journal version is a reporting-bias signal.

## Reasons to be more sure

Rate up only when no risk-of-bias concern is holding the finding down
(Cochrane ch.14 practice), and only for:

- a **large effect**: "A large estimated effect (e.g. RR >2 or RR <0.5) in the
  absence of plausible confounders, or a very large effect (e.g. RR >5 or RR
  <0.2) in studies with no major threats to validity". Cochrane's examples are
  risk ratios only; for effects in standard-deviation units, "large" needs an
  importance threshold declared in the protocol or review notes before reading
  (DAAF's adaptation);
- a **dose-response** gradient;
- **opposing bias**: "all plausible biases… working to under-estimate" the
  effect.

Murad et al.: "consider rating up… particularly if it is noted in the majority
of studies".

## Writing the reason (standard level)

The synthesizer records the certainty and a short paragraph, `certainty_reason`,
that:

1. names the papers that carry the finding and their weight;
2. says which of the five domains hold it down (or which reason raises it),
   each with the claim ids that show it; for non-randomized studies stated
   above low, what mitigates confounding and selection (§ Where to start);
3. says what would change it ("a trial outside urban districts").

Two guards, both enforced by `lit_corpus findings record` (exit 11, nothing
written):

- **A reason is required,** and it names at least one claim id.
- **High or moderate certainty cannot rest only on abstract-only claims.** An
  abstract cannot show the limitations that certainty is about.

Example: "Moderate. Two trials given substantial weight [W123-c03, W456-c01]
agree in direction and size; certainty is held down for indirectness, because
both are in urban districts [W123-c05] and the question covers rural ones too.
A trial in a rural setting could change it."

## The researcher's rating (formal level)

At the formal level the certainty is `researcher_grade`. DAAF drafts notes per
domain (risk of bias, inconsistency, indirectness, imprecision, publication
bias, any rating up), each citing claim ids and the checklist judgments behind
them; the researcher decides the level and may edit the notes. The record names
the researcher as decider and quotes their instruction. If the researcher
departs from the drafted notes, record why; that is a judgment, not an error.

## Not rated

Some findings get no certainty level; they say so in fixed words
(`certainty-language.yaml` `not_rated`):

| Reason | Wording | When |
|---|---|---|
| `abstracts_only` | "certainty not rated: abstracts only" | Any finding whose claims all come from abstracts. To record one, quote its claims from the stored abstracts with `lit_corpus claims abstract` (`lit-corpus.md` § Subcommands); a quick-scan memo itself states such a finding in words only, without a finding marker (`quick-scan.md`) |
| `qualitative_evidence` | "certainty not rated: qualitative evidence" | Themes from qualitative studies (GRADE-CERQual is deferred; `guide-qualitative.md`) |

A scoping or mapping review states certainty or "not rated" per finding,
decided case by case; it is not exempt by type. An unrated finding uses none of
the GRADE hedges: "probably", "likely", "may" and "might" all fail there
(`certainty-language.yaml` `not_rated.forbidden`; the month, as in "May 2020"
or "in May", is not a hedge).

## Finding record fields

What a finding records, in the shape `lit_corpus findings record` checks
(`lit-corpus.md` § Findings, summaries, sign tests).

| Field | Content |
|---|---|
| `finding_id` | `F01`, `F02`, …; frozen once used; a changed finding gets a new id |
| `statement` | The finding in plain words |
| `claim_ids` | The page-checked claims it rests on |
| `synthesis_method` | `swim`, `narrative`, `thematic`, `concept_matrix`, `egm`, `realist`, `umbrella` |
| `certainty_scheme` | `stated` (standard), `researcher_grade` (formal), `not_rated` |
| `certainty` | `high`, `moderate`, `low`, `very_low` (with `stated` or `researcher_grade`) |
| `certainty_reason` | Required with a certainty; names at least one claim id |
| `grade_notes` | Formal only, optional: notes per GRADE domain |
| `decided_by` | Role (`synthesizer` or `researcher`), agent and model ID, and for `researcher_grade` the researcher's quoted instruction |
| `not_rated_reason` | `abstracts_only` or `qualitative_evidence` (with `not_rated`) |
| `boundary_conditions`, `sensitivity_note` | Text; a sensitivity note whenever the finding could rest on weaker papers |
| `moderator_status` | `prespecified`, `post_hoc` or `none` |
| `descriptive_summary`, `direction_summary` | Requests for a computed summary or sign test (`synthesis-methods.md`); never typed numbers |

Pooled or weighted fields (a pooled estimate, an average effect) are refused.

## Choosing the words

1. Take the finding's certainty.
2. Take the canonical wording for that level from `certainty-language.yaml`
   (`levels.{level}.canonical`) and a template that fits the magnitude.
3. Take the verb the designs allow: causal verbs only where the designs earn
   them, "is associated with" otherwise (`data-scientist`
   `references/research-questions.md` § Causal vs. Correlational Language).
4. Check the sentence against the level's `forbidden` list and the
   `global_forbidden` patterns. One hedge per sentence.
5. Keep "what would change it" out of the finding sentence. It belongs in the
   certainty reason or a sentence of its own: inside the marked finding, a
   "could" ("a rural trial could change this") reads as a second hedge, and
   `lit_verify report` sends it to review.

The words `lit_verify report` reads as each level (the `markers` in
`certainty-language.yaml`; anything else from the list below in a finding of
another level is a mismatch):

| Level | Wording that reads as this level |
|---|---|
| high | the plain verb, no hedge ("results in", "improves") |
| moderate | "probably" ("likely" also reads as moderate, but DAAF does not use it) |
| low | "may", "might", "the evidence suggests" (also "evidence suggests", "the available evidence suggests") |
| very low | "the evidence is very uncertain", "it is uncertain whether", "it is unclear whether", "we do not know whether" (or "if") |
| not rated | "certainty not rated: …", with no hedge at all: "probably", "likely", "may" and "might" fail |

"Little to no difference" needs an importance threshold declared in advance;
"no effect" and "no difference" are never conclusions, but "little to no
difference" (or "little to no effect") passes the check at every level.
Cochrane §15.6.4: "A common mistake is to confuse 'no evidence of an effect'
with 'evidence of no effect'"; "if one of the possibilities is mentioned in
the conclusion, the other possibility should be mentioned as well". The
paired sentence ("there is no evidence of an effect, which is not evidence of
no effect") passes beside a finding of any certainty: it states what is
missing, not a level, so its wording is not compared with the finding's.

## Worked examples

| Body of evidence | Certainty and reason (short) | Sentence |
|---|---|---|
| Three trials given substantial weight, consistent direction, similar settings, about 2,000 pupils | High: no domain holds it down | "Small-group tutoring improves reading scores in grades 1–3." |
| Two well-identified DiD studies agree; pre-periods short | Low: non-randomized, and the short pre-periods leave confounding open, so nothing justifies moving off Cochrane's two-level default | "The policy may have reduced chronic absence." |
| Two regression discontinuity studies at the same cutoff; no bunching, results stable across bandwidths, covariates continuous | Moderate, with the justification written out: the design checks [claim ids] address confounding and selection near the cutoff (DAAF's reading, § Where to start); the finding speaks only of pupils near the cutoff, so it is not held down for indirectness | "Summer school probably raises grade-9 math scores for pupils near the promotion cutoff." |
| Four correlational studies, one direction, no design addresses selection | Low: risk of bias (selection) | "Smaller classes may be associated with higher attendance." |
| One small pilot and one study given limited weight, opposite directions | Very low: inconsistency and imprecision | "The evidence is very uncertain about the effect of the program on attainment." |
| Six interview studies on teachers' views | Not rated | "Teachers described scheduling as the main barrier (certainty not rated: qualitative evidence)." |

## Not verified

The Core GRADE series (BMJ 2025, seven papers, e.g. "Core GRADE 2: choosing the
target of certainty rating and assessing imprecision") was not readable (403);
whether it changes the no-pooling guidance is unknown. DAAF read only the
abstract of Santesso et al. 2020.

## Sources

Murad et al. 2017, Evid Based Med 22:85–87 (PMC5502230); Cochrane Handbook
ch.14 (last updated August 2023; § 14.2.1 on starting certainty and § 14.2.3
on rating up), ch.13 (last updated August 2024) and §15.6.4;
ROB-ME (Page et al., BMJ 2023;383:e076754); SWiM item 6 (Campbell et al. 2020).
Read for DAAF's 2026-10-30 appraisal survey.
