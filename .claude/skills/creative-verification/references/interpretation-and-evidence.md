# Interpretation and Evidence

How to read the result of a challenge test, assign it a status, and keep the whole
session honest. This file carries the six interpretation statuses and their decision
rules, the four-way test labeling that governs how much a result is allowed to claim,
the test budgets and stopping rules that make the loop resist fishing, the
specification-curve summary contract, and the mapping to DAAF's evidence-graded
reporting. It is the interpretive half of creative verification — `challenge-families.md`
designs the test, this file decides what the result means.

**The one rule under all the rules.** Never iterate toward a desired finding. Every
device below — pre-committed interpretation, labeled tests, bounded budgets, recording
nulls — exists to close the garden-of-forking-paths gap (Gelman & Loken 2013 —
https://atticusli.com/replication-crisis/garden-of-forking-paths/), where data-
dependent analytic choices act as hidden multiple comparisons that invalidate
inference even without explicit p-hacking. The ledger (`agent_reference/TRIANGULATION_PROTOCOL.md`)
is the arbiter; interpretation is measured against what was pre-committed there, not
against what would be convenient now.

---

## The Six Interpretation Statuses

Every executed test resolves to exactly one status. The status is assigned by
comparing the observed result to the **pre-committed interpretation rule** recorded in
the ledger before execution (SKILL.md loop step 6) — not by reasoning backward from the
result.

| # | Status | Decision rule (assign when…) |
|---|--------|------------------------------|
| 1 | **Supports focal claim** | The result matches the pre-committed "would support" condition AND weakens at least one credible competing explanation. Consistency alone is not support — it must also discriminate. |
| 2 | **Weakens focal claim** | The result materially changes the claim's magnitude, direction, population, or interpretation relative to what was stated. A weakening result is reported with the same prominence as a supporting one. |
| 3 | **Does not discriminate** | The result is compatible with both the focal claim and at least one alternative — the test lacked discriminatory power for *this* data. Not a null finding; a design that couldn't separate the explanations. |
| 4 | **Reveals data/process issue** | The decisive movement traces to missingness, coding, joins, suppression, duplication, or lineage rather than the substantive relationship. Routes to Family 9 escalation / code review of the implicated chunk. |
| 5 | **Inconclusive** | The data or design cannot answer the challenge at all (insufficient coverage, non-convergence, unavailable tooling). Distinct from #3: #3 ran and couldn't separate; #5 could not run meaningfully. |
| 6 | **Generates new hypothesis** | The result warrants follow-up but must **not** be presented as confirmation. Stakeholder questions (Family 10) and surprising side-observations land here until they are given their own discriminating test. |

**Adjacent-status discipline.** The two most abused boundaries: (a) calling a *does not
discriminate* result *supports* because it is "consistent with" the claim —
consistency without discrimination is status 3, not 1; (b) calling a *generates new
hypothesis* result *supports* because the follow-up looks promising — a hypothesis is
not its own evidence (status 6, never 1). When in doubt between two statuses, record
both candidate readings in the ledger and let the researcher adjudicate.

---

## Four-Way Test Labeling

Independently of status, every test carries one of four labels describing *when it was
specified relative to seeing the data it uses*. The label caps how strongly the result
may be interpreted (registered-reports / preregistration tradition — its known limit is
that pre-registering a hypothesis leaves the *how-tested* forks open, which the pre-
committed interpretation rule closes; https://experimentology.io/011-prereg.html).

| Label | Specified… | Interpretation consequence |
|-------|-----------|----------------------------|
| **Exploratory** | After seeing the data, to generate ideas | May *suggest*, never *confirm*. Findings feed status 6 (new hypothesis), not status 1. |
| **Pre-specified** | Before running the test, with interpretation rule pre-committed in the ledger | Full inferential weight for a challenge. The default for pre-analysis challenge design. |
| **Confirmatory** | Before *any* data was seen, as a standing prediction | Strongest weight; rare in verification, where data usually already exists. |
| **Post-hoc** | After seeing a result, to probe or rationalize it | Interpret with maximum caution; useful for diagnosis, weak for confirmation. Flag explicitly. |

**Pre-analysis challenge design produces pre-specified tests** — this is the venue where
verification earns confirmatory-adjacent weight, because the interpretation rule is
committed before the analysis runs. Results-verification on a completed analysis is
usually pre-specified-at-best (the outcome data already exists) and often post-hoc; be
honest about which. A test's label is recorded in the ledger and never upgraded after
the fact.

---

## Test Budgets and Stopping Rules

Bounded budgets with explicit stopping rules are how the loop resists fishing — an
unbounded search across tests is a garden of forking paths regardless of how principled
each individual test looks (minP-type multiplicity concern;
https://arxiv.org/pdf/2401.11537).

**Default budget.** Propose a **small first bundle of ~3 complementary tests**, execute,
interpret, update the coverage map, then *pause* before proposing more. Complementary
means the three probe *different* competing explanations, not three angles on the same
one.

**Explicit stop conditions.** Record the stopping rule in the ledger before starting.
Stop when any fires:

- The focal claim's competing explanations have each been given at least one
  discriminating test (coverage-complete for the stated claim).
- Two successive bundles return *does not discriminate* / *inconclusive* — the data has
  reached its resolving power; more tests will not help.
- A *reveals data/process issue* result requires fixing the pipeline before further
  substantive tests mean anything — stop and escalate the fix.
- The researcher's decision no longer turns on the remaining candidate tests (decision-
  relevance exhausted — the mission's attention denominator has gone to zero).

**Anti-iteration rule.** Never add tests *because the current ones did not produce the
hoped-for result*. Adding a fourth, fifth, sixth denominator/spec/subgroup until one
"works" is the exact failure mode the budget exists to prevent. If a bundle weakens the
claim, the honest move is to record the weakening — not to keep drawing until the claim
is rescued.

---

## Specification-Curve Summary Contract

When a challenge enumerates alternatives (Family 6 spec grids, but also multi-
denominator, multi-operationalization, multi-window sweeps), summarize the resulting
distribution of estimates with a fixed contract rather than cherry-picking a point on
it. The contract mirrors the established `specr` summary (verified from
https://masurp.github.io/specr/articles/specr.html) plus the multiverse framing
(Steegen et al. 2016 — https://sites.stat.columbia.edu/gelman/research/published/multiverse_published.pdf).

**Required summary statistics** (over all specifications in the pre-committed grid):

- **median** estimate, and **MAD** (median absolute deviation) as the spread measure
- **min** and **max** estimate
- **q25** and **q75** (interquartile range of estimates)
- **share of specifications** that are same-signed as the median, and the share that are
  same-signed *and* significant at the pre-committed α
- median / min / max **sample size** across specs (a spec that silently drops data is a
  Family 9 signal, not a robustness win)

**Required visual (two panels).**

- **Panel A — ranked curve:** every estimate sorted ascending with its CI, so the reader
  sees the full range and where the null sits.
- **Panel B — choice panel:** aligned beneath Panel A, one row per analytic choice
  (which controls, which FE, which denominator), marked to show which choices produce
  which estimates.

**The framing that matters: which choice explains the variance.** The point of the curve
is not "most specs are significant" (a vote count) but **which analytic decision moves
the estimate most** — a variance-decomposition reading. If the estimate swings on one
arbitrary choice (a single cutpoint, one FE structure), the claim is fragile in a
specific, nameable way; say which choice. A tight curve centered away from the null
across *all* choices is strong support; a curve straddling the null is *does not
discriminate*.

**Multiplicity caution (minP).** A spec curve describes fragility; it does **not**
license reading off the significant tail as "the" result. If the grid is large and an
inferential claim is made on the share-significant, note that naive counting inflates
false positives and a minP-type adjustment across specifications is the principled
correction (https://arxiv.org/pdf/2401.11537). The curve's job is honest description of
dependence on choices, not manufacturing a significant subset.

---

## Mapping to DAAF Evidence-Graded Reporting

Creative verification inherits DAAF's core reporting rule (CLAUDE.md § Execution
Philosophy > Evidence-graded reporting): a report must let the reader distinguish
**observed facts** from **inference**.

- **A test result is *observed* only when the generating script and its relevant output
  are quoted or linked.** A remembered or paraphrased result is inference. In practice
  this means every ledger test entry links its script path and its captured output
  (data/figure/app-state artifact), and any status assigned to it points at that
  evidence. A status with no linked artifact is not yet an observed result.
- **Negative claims carry the higher bar.** "The placebo was null," "the join dropped
  nothing," "no denominator moves the rate" — each is a negative claim that fails
  silently if wrong, so quote the probe (the assertion and its output) that establishes
  it, exactly as the sensitivity-statistics and Family-9 recipes do with their
  `assert` + `print` lines.
- **Sensitivity statistics carry their formula-confidence label.** A robustness value or
  E-value is reported with its primary-source-verified / secondary-corroborated /
  verify-before-relying label from `sensitivity-statistics.md` — the label travels with
  the number into the report.
- **Completion accounting is derived, not recalled.** "We ran 7 tests, 5 support" is
  read off the ledger's own rows (the coverage map), never from memory.

**The coverage map is the honest statement of what remains unverified.** When presenting
to the researcher, show the ledger as a map: which facets of the data, process, and
results have a linked observed test with a status, and which do not. Gaps are not
failures to hide — they are the precise, auditable statement of the analysis's current
verification frontier, and they are what tells the researcher where their remaining
attention should go.

## References

- Gelman & Loken (2013), Garden of Forking Paths — https://atticusli.com/replication-crisis/garden-of-forking-paths/
- Preregistration / registered reports (and their how-tested limitation) — https://experimentology.io/011-prereg.html
- minP multiplicity adjustment across specifications — https://arxiv.org/pdf/2401.11537
- Steegen et al. (2016), Multiverse analysis — https://sites.stat.columbia.edu/gelman/research/published/multiverse_published.pdf
- `specr` summary contract (median/MAD/min/max/q25/q75, curve + choice panel, variance decomposition) — https://masurp.github.io/specr/articles/specr.html