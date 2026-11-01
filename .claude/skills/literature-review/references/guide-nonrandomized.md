# Guide: Non-Randomized Studies (ROBINS-I V2, ROBINS-E, Design Checks)

A formal-level guide for studies without random assignment: ROBINS-I Version 2
for non-randomized studies of interventions, ROBINS-E for exposures that are
not deliberate interventions, and **DAAF's design checks** for
quasi-experimental designs (difference-in-differences, regression
discontinuity, instrumental variables, matching, synthetic control,
interrupted time series), which neither ROBINS tool covers. It states each
tool's domains, scale and overall rule in words; it does not reproduce tool
questions and does not compute ratings. The researcher makes every judgment.

## Contents

- [Which tool](#which-tool)
- [ROBINS-I Version 2](#robins-i-version-2)
- [ROBINS-E](#robins-e)
- [DAAF design checks for quasi-experiments](#daaf-design-checks-for-quasi-experiments)
- [What to quote](#what-to-quote)
- [How DAAF and the researcher use it](#how-daaf-and-the-researcher-use-it)
- [Pitfalls](#pitfalls)
- [Not verified](#not-verified)
- [Sources](#sources)

## Which tool

| Study | Use |
|---|---|
| A cohort-type study of an intervention someone chose to deliver (a program, a policy, a treatment) | ROBINS-I V2 |
| A DiD, RD, IV, synthetic-control, ITS or matching study of an intervention | ROBINS-I V2 domains **plus** DAAF's design checks for that design (DAAF's adaptation: V2 is written for cohort studies; its domains are used here as prompts) |
| A study of an exposure nobody assigned (poverty, school segregation, neighbourhood) | ROBINS-E |

ROBINS-I V2 covers "follow-up (cohort) studies" only, and neither ROBINS tool
has design-specific questions for RD, IV or synthetic control (DAAF's survey
searched the V2 text for "regression discontinu", "instrumental" and
"difference-in" and found none). That gap is why the design checks exist.

## ROBINS-I Version 2

**Version.** "A revised version of Version 2… posed on 20 November 2025. Note
that this is still a draft version and is subject to change"
(https://www.riskofbias.info/welcome/robins-i-v2). Record the version date on
every appraisal (guide id `robins-i-v2`); a draft can change.

**Target trial.** V2 requires a target-trial specification: the randomized
trial the study is trying to emulate. Write it down (population, intervention
and comparator, outcome, follow-up) with a quote where the paper states its
question.

**Triage (part B).** Before the domains: if confounding is unaddressed and
serious (B2), or the outcome measurement is inappropriate (B3), the result is
at "Critical risk of bias and no further assessment is required".

**Six domains.**

1. Confounding (variant A: intention-to-treat or baseline; variant B:
   per-protocol or time-varying).
2. Classification of interventions.
3. Selection of participants into the study (or into the analysis).
4. Missing data.
5. Measurement of the outcome.
6. Selection of the reported result.

The V1 domain "deviations from intended interventions" was dropped in V2.

**Answers.** "Most signalling questions have response options 'Yes',
'Probably yes', 'Probably no', 'No' and 'No information'" (record as `Y`, `PY`,
`PN`, `N`, `NI`), and "Some questions have additional response options (a
'weak' and a 'strong' version of 'Yes' or 'No')" (record as `SY`, `WY`, `WN`,
`SN`). Use a strong or weak answer only where the question offers it. The
triage questions (B1 to B3) offer `Y`, `PY`, `PN`, `N` only. Mark an unreached
question `NA`.

**Judgment scale.** **Low** (for domain 1: "Low risk of bias (except for
concerns about uncontrolled confounding)"), **Moderate**, **Serious**,
**Critical**. A Critical result "should generally be excluded from evidence
syntheses".

**Overall rule, in words.**

- **Low (except for confounding):** domain 1 low-except-confounding and every
  other domain low.
- **Moderate:** at least one domain moderate, none serious or critical.
- **Serious:** at least one domain serious and none critical, "OR several
  domains are at Moderate, leading to an additive judgement of Serious".
- **Critical:** at least one domain critical, "OR several domains are at
  Serious".

The "several domains" conditions are judgments for the researcher; record the
reasoning either way.

**What Cochrane says about certainty.** With ROBINS-I "all studies may start as
high certainty", but a body of non-randomized evidence "should generally be
downgraded by two levels", and "Very few examples of where not rating down by
two levels is appropriate currently exist" (Handbook ch.14). How DAAF applies
that to quasi-experiments: `certainty-of-evidence.md` § Where to start.

## ROBINS-E

**Version.** Full version for follow-up studies, launched June 2022; Higgins et
al., Environment International 2024, doi:10.1016/j.envint.2024.108602
(PMC11098530). Guide id `robins-e`.

**Seven domains.** Confounding; measurement of the exposure; selection of
participants; post-exposure interventions; missing data; measurement of the
outcome; selection of the reported result.

**Judgments.** "'Low risk of bias', 'Some concerns', 'High risk of bias' and
'Very high risk of bias'". Each domain also gets a predicted **direction of
bias** and a **threat to conclusions** (Yes, No, Cannot tell).

**Overall rule.** The "default… overall risk-of-bias judgement is that for the
domain with the greatest risk of bias", which can be overridden upward with a
reason.

## DAAF design checks for quasi-experiments

**These checks are DAAF's adaptation, not a published tool.** They draw on
Waddington, Wilson, Pigott, Aloe, Tugwell, Welch & Stewart 2026, "Risk of Bias
in Experiments, Quasi-Experiments and Natural Experiments Across Disciplines",
Campbell Systematic Reviews, doi:10.1177/18911803261435894, and on the threats
table in `data-scientist` `references/causal-inference.md` § Threats to
Validity Checklist. Waddington et al. "do not provide… a decision algorithm";
neither does DAAF.

Use them beside the ROBINS-I V2 domains (applying V2's domains to these
designs is itself DAAF's adaptation, since V2 is written for cohort studies):
they mostly inform domain 1 (confounding) and domain 6 (reported result).

| Design | Core checks | Other checks |
|---|---|---|
| DiD / event study | `QD1` pre-intervention trends assessed and shown ("it is standard to undertake assessment of parallel pre-intervention trends"); `QD2` no anticipation and no change in who is measured | `QD3` staggered timing handled with a heterogeneity-robust estimator (when timing is staggered) |
| RD | `QR1` adherence to the assignment rule, no bunching at the threshold ("bunching of observations at the threshold… is evidence of subversion"); `QR2` results across bandwidths and functional forms | `QR3` covariate continuity or placebo cutoffs ("placebo discontinuities") |
| IV | `QI1` instrument relevance (first-stage strength reported); `QI2` exclusion argued: the instrument "is only causally related to the outcome by determining selection to treatment" | `QI3` over-identification or placebo test where applicable |
| Matching, regression on observables | `QM1` overlap and balance reported; `QM2` selection plausibly explained by what was observed | — |
| Synthetic control | `QS1` pre-period fit shown; `QS2` donor pool justified | `QS3` placebo in space or time |
| Interrupted time series | `QT1` enough pre-period points; `QT2` co-interventions considered | — |

**Answers:** Y, PY, PN, N. Information that is "not stated… becomes equivalent
to 'No' or 'Probably No'" (Waddington et al. 2026). DAAF encodes no numeric
thresholds (for example a first-stage F cutoff): two local DAAF sources state
different rules of thumb, so the quote carries the number and the researcher
judges it.

**How the checks bear on the judgment (DAAF's suggestion, for the researcher
to accept or not in the protocol):** a core check answered N or PN is a strong
reason to judge ROBINS-I V2 domain 1 as Serious or worse for that result.
Matching on observables where people chose their own treatment deserves
particular care: Waddington et al. write that such studies "are likely to be at
'high-risk of bias' no matter how fancy the statistical methods". A pre-trend
test that passes is "neither necessary nor sufficient" for parallel trends
(`data-scientist` `references/causal-inference.md` § Parallel Trends); quote
what the paper shows, not its conclusion that trends are parallel.

## What to quote

| Item | Quote |
|---|---|
| Target trial | The sentence stating the paper's question and comparison |
| Confounding | The identification strategy; the controls or design feature that addresses confounding; the design check evidence (event-study figure caption and coefficients, density test result, first-stage statistic, balance table row) |
| Classification of interventions or exposure | How exposure or treatment status was defined and measured |
| Selection | Who entered the analysis and when, relative to the start of exposure |
| Missing data | Sample sizes at each stage; the missing-data method |
| Outcome measurement | The measure and its source; whether it could differ by group |
| Reported result | The pre-analysis plan or registry entry, if any, beside the reported analyses |

## How DAAF and the researcher use it

1. Pick the tool by the table above; for a quasi-experiment, add the design
   checks for its design.
2. The reader drafts the target trial, the triage answers, an answer and a
   quote per question and per design check, and an `NI` reason where the paper
   is silent.
3. Each answer is an appraisal claim (`formal-review.md` § Recording checklist
   answers): guide `robins-i-v2` or `robins-e`, item = the tool's own question
   id, or `QD1`… for a design check (DAAF ids, prefixed so they never clash
   with tool ids), answer on the scale above.
4. The researcher decides each domain judgment (and for ROBINS-E the direction
   and threat to conclusions) and the overall judgment, using the rules above;
   the record quotes them.
5. A result the researcher judges Critical is normally left out of findings;
   if kept, the synthesis says why.

## Pitfalls

- **Applying ROBINS-I to RD, IV or synthetic control without design checks.**
  V2 is cohort-only.
- **Reading high risk of bias as overestimation.** Waddington et al. warn to
  "avoid assuming that studies at 'high risk of bias' will de facto
  over-estimate a treatment effect".
- **Treating a statistically fancy method as a fix for self-selection.**
- **Quality labels.** "Avoid reporting risk-of-bias assessments as markers of
  the quality of a study" (Waddington et al. 2026).

## Not verified

- ROBINS-I V2's question ids and its per-domain algorithms were not transcribed
  from the stored V2 PDF; copy them from the tool version in use.
- The full ROBINS-E tool text was not read; its domains, scale and overall rule
  come from the 2024 paper only, and its domain algorithms are not described
  here.
- The design checks are one 2026 framework plus DAAF's reading; no published
  algorithm combines them with ROBINS-I.

## Sources

riskofbias.info ROBINS-I V2 page and the V2 draft PDF dated 20 November 2025;
Higgins et al. 2024 (ROBINS-E); Waddington et al. 2026 (OpenAlex cached full
text); Cochrane Handbook ch.14 (last updated August 2023). Read for DAAF's
2026-10-30 appraisal survey. Records seen but not read: Waddington et al. 2017
(quasi-experimental study designs series, paper 6); Windle et al. 2025
(doi:10.1016/j.jclinepi.2025.112121); Barker et al. 2024 (revised JBI
quasi-experimental tool).
