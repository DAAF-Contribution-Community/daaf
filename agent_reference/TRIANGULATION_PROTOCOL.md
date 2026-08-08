# Triangulation Protocol

This document defines the bookkeeping and provenance substrate for **creative
verification** (analytic triangulation). The `creative-verification` skill supplies the
*methodology* — what challenges to design and how to interpret them; this protocol
supplies the *record-keeping* — how hypotheses, tests, and interpretations are logged,
linked to their provenance, and presented as a coverage map of what has and has not
been verified. The two are companions: read the skill for the challenge taxonomy,
sensitivity statistics, interpretation rules, and interactive-artifact QA; read this
protocol when setting up or maintaining the ledger for a session.

**Piloted in Ad Hoc Collaboration mode only** (v1). The orchestrator loads the
`creative-verification` skill directly, runs the challenge loop conversationally, and
maintains the ledger described here in the session workspace. This protocol introduces
**no parallel provenance system** — it reuses DAAF's existing file-first script
versioning and Inline Audit Trail (IAT) as the provenance substrate, and adds only the
hypothesis/evidence bookkeeping layer on top.

**Audience:** the orchestrator (ledger owner in v1) and any agent executing a
triangulation test. Related: `.claude/skills/creative-verification/SKILL.md`,
`.claude/skills/daaf-orchestrator/references/ad-hoc-collaboration-mode.md`,
`agent_reference/INLINE_AUDIT_TRAIL.md`, `agent_reference/SCRIPT_EXECUTION_REFERENCE.md`.

---

## The Ledger

### Location and Format

The **triangulation ledger** is a single Markdown file in the session workspace:

```
{PROJECT_DIR}/TRIANGULATION_LEDGER.md
```

Markdown (not Parquet or JSON) because the ledger is a human-facing audit artifact the
researcher reads and reasons over, and because it must be diff-able alongside the rest
of the workspace. It holds **two tables** — a hypothesis table and a test table — plus a
short header recording the focal claim(s) and the pre-committed stopping rule for the
session.

The ledger is created at the **first substantive triangulation milestone** (the first
hypothesis stated or first test pre-committed), the same deferral discipline Ad Hoc
Collaboration applies to `SESSION_NOTES.md`. In a session that stays purely
conversational, no ledger is created. The orchestrator owns and writes the ledger in
v1; subagents return test results and the orchestrator records them (subagents do not
write the ledger, consistent with STATE.md ownership).

### Header

```markdown
# Triangulation Ledger: {Topic}

**Started:** YYYY-MM-DD
**Workspace:** {PROJECT_DIR}
**Mode:** Ad Hoc Collaboration (creative verification)
**Variant:** results-verification | pre-analysis challenge design

## Focal Claim(s)
- FC1: [precise statement — magnitude, population, period, conditioning, the decision it informs]

## Stopping Rule (pre-committed)
- [e.g. "each competing explanation gets ≥1 discriminating test; stop after 2 bundles
   of non-discriminating results; default first bundle = 3 complementary tests"]
```

### Hypothesis Table

One row per hypothesis — the focal claim and each competing explanation that could also
produce the observed result.

| Column | Contents |
|--------|----------|
| **id** | `H1`, `H2`, … (focal claim is a hypothesis too — mark it) |
| **source** | `researcher-supplied` \| `DAAF-generated` (never blur these — see Separation of Layers) |
| **focal claim / explanation** | The precise statement of this hypothesis or competing explanation |
| **relationship** | `focal` \| `competing-substantive` \| `competing-data-process` |
| **current status** | `open` \| `supported` \| `weakened` \| `resolved-data-issue` \| `set-aside` |

### Test Table

One row per test. **Interpretation is pre-committed before execution** — the "supports
vs. weakens" columns are filled in *before* the test runs and are not edited afterward;
the observed result and status are added after.

| Column | Contents | Filled |
|--------|----------|--------|
| **id** | `T1`, `T2`, … | at proposal |
| **hypothesis(es)** | Linked `H` id(s) this test discriminates among | at proposal |
| **challenge family** | Family 1–12 (`challenge-families.md`) | at proposal |
| **label** | `exploratory` \| `pre-specified` \| `confirmatory` \| `post-hoc` | at proposal |
| **pre-committed rule** | What result would SUPPORT vs. WEAKEN the focal claim — the arbiter | **before execution** |
| **script path** | Absolute path to the file-first generating script | at execution |
| **artifact paths** | Data (Parquet) / figure (PNG) / app-state paths produced | at execution |
| **QA result** | QA checkpoint / interactive-artifact-QA outcome (`PASSED`/`WARNING`/`BLOCKER`) | after execution |
| **observed result** | The quoted number/output (observed, not recalled) | after execution |
| **interpretation status** | One of the six (`interpretation-and-evidence.md`) | after interpretation |
| **budget counter** | Bundle #/test # within the pre-committed budget | at proposal |

The **pre-committed rule** column is the mechanism that closes the garden-of-forking-
paths gap: because the reading of the result is fixed before the result is seen, a
test cannot be silently reinterpreted to rescue a claim. The ledger is the arbiter.

---

## Test Lifecycle

Each test moves through a fixed sequence of states. The transition from `pre-committed`
to `executed` is the one-way gate: once a test is pre-committed, its interpretation rule
and label are frozen.

```
proposed ──▶ approved ──▶ pre-committed ──▶ executed ──▶ interpreted ──▶ ledger-updated
   │            │              │                │             │                │
 (family,     (researcher    (support/weaken   (file-first   (assign one    (coverage
  label,       agrees test    rule + label      script runs   of six         map + H-row
  budget       is worth        FROZEN in         via run_      statuses vs.   status
  slot)        running)        ledger)           with_capture) pre-commit)    updated)
```

- **proposed → approved:** the researcher agrees the test is worth its cost (the
  prioritization rubric in SKILL.md; decision relevance × discriminatory power over the
  attention denominator). Scope-changing tests need explicit approval (below).
- **approved → pre-committed:** the support/weaken rule and the label are written into
  the ledger. Nothing about the test's interpretation may change after this point.
- **pre-committed → executed:** the test runs through normal DAAF machinery — a
  file-first script executed via `run_with_capture.sh`, with inline validation and, for
  substantive tests, QA review. Diagnostic dashboards run the interactive-artifact QA
  contract instead of / in addition to standard QA.
- **executed → interpreted:** the observed result is compared to the pre-committed rule
  and assigned exactly one of the six statuses.
- **interpreted → ledger-updated:** the coverage map and the linked hypothesis rows are
  updated; the loop then stops, iterates a new bundle, or promotes a confirmed change.

---

## Provenance Chain

Every test carries a full provenance chain, and every link reuses machinery DAAF
already has — this protocol adds no new provenance store:

```
claim ─▶ test ─▶ script ─▶ data ─▶ figure/app-state ─▶ QA result ─▶ interpretation
 (H-id)  (T-id)  (versioned  (Parquet   (PNG / Marimo    (QA1-4 /    (one of six,
                  file-first  from       .py + static     interactive  vs. pre-
                  script +    captured   export)          -artifact    committed rule)
                  IAT)        script)                     QA)
```

- **script** is an immutable file-first script; fixes create `_a`/`_b` revisions via
  `create_script_revision.sh`, never in-place edits (CLAUDE.md § Immutable script
  versioning). The script's appended execution log is the observed-output source of
  truth.
- **data** is Parquet produced by that script — the diagnostic-data boundary rule
  (`interactive-artifact-qa.md`): captured, immutable, never live-computed.
- **IAT** (`# INTENT:` / `# REASONING:` / `# ASSUMES:`) inside the script documents each
  filter, join, and derivation, so a reviewer follows the test's logic without rerunning
  it (`agent_reference/INLINE_AUDIT_TRAIL.md`).

Because provenance is the existing script-versioning + IAT substrate, a test entry in
the ledger is *addressable* — the researcher can walk from a report claim to the exact
script line and raw cell that produced its number (Family 9 source-to-report tracing).

---

## Coverage-Map Presentation Duty

The ledger is not only a record — it is a **map of what has been triangulated and what
remains unverified**, and it must be presentable that way to the researcher on demand.
This is a standing duty, not an optional courtesy.

A coverage-map presentation answers, for the focal claim: which competing explanations
have a linked, observed test with an assigned status; which validity types
(`challenge-families.md` validity-type map) have been probed and which are untouched;
and which facets of the data/process/results still have no test. **Gaps are the honest
statement of the verification frontier** — they tell the researcher where remaining
attention should go, in service of the mission's "calibrated confidence per unit of
researcher attention." Present the map as coverage-and-gaps, never as a highlight reel
of supporting tests (a ledger that shows only confirmations is a fishing expedition
with good PR).

Completion accounting on the map — "N tests, M support, K reveal data issues" — is
**derived from the ledger's own rows**, never recalled (CLAUDE.md § Evidence-graded
reporting).

---

## Pre-Analysis Variant

The same ledger serves pre-analysis challenge design, with one difference: tests are
designed and pre-committed **before the analysis runs**, so they are labeled
`pre-specified` (occasionally `confirmatory` when the prediction precedes any data
contact). The header's **Variant** field records `pre-analysis challenge design`. The
workflow is otherwise identical — hypotheses, competing explanations, discriminating
observables, pre-committed rules, budget, stopping rule — and the resulting ledger
functions as a lightweight pre-registration whose interpretation rules are fixed in
advance, closing the how-tested fork that hypothesis-only pre-registration leaves open
(`interpretation-and-evidence.md`). When the analysis later runs, the pre-committed
tests are executed and interpreted against their frozen rules.

---

## Scope-Change Approval Rules

Creative verification runs **alongside** the official analysis and never silently
changes it. A triangulation test that would alter official scope requires **explicit
researcher approval before execution**:

- **New data source** — pulling in data the official analysis did not use.
- **Population change** — redefining who is in the analysis (a Family 1 denominator
  test that *proposes adopting* a new base, versus merely reporting the spread).
- **Methodology change** — changing the estimator, identification strategy, or model of
  the official analysis.

Tests that stay within the existing data, population, and methodology (recomputing,
reconciling, placebo-testing, sensitivity-analyzing) do **not** need scope approval —
they are the normal business of verification. The distinction: verifying the existing
analysis is in-scope; *changing* it is a scope change.

**Preserve the official analysis.** The official artifacts are never overwritten by a
triangulation test. When a triangulation result is confirmed and the researcher wants to
act on it — adopt a different denominator, add a robustness result, correct a data-
process issue — it is **promoted into Revision and Extension mode**, not slipped into
the official analysis in place. The promotion path is explicit and researcher-approved;
the ledger records the promotion (which hypothesis, which confirming tests, what change
is being promoted).

---

## Separation of Layers

The protocol keeps five layers distinct, in the ledger and in every presentation to the
researcher. Blurring them is the most common way triangulation goes wrong — it lets a
concern read as a conclusion or a suggestion read as evidence.

| Layer | What it is | Ledger location | Must never… |
|-------|-----------|-----------------|-------------|
| **Researcher concerns** | Doubts, surprises, skeptical-reviewer questions the researcher raised | Hypothesis table, `source = researcher-supplied` | …be treated as empirical evidence for or against the claim |
| **DAAF-generated hypotheses** | Competing explanations DAAF proposed | Hypothesis table, `source = DAAF-generated` | …be treated as findings — they are suggestions requiring a test and the researcher's judgment |
| **Test designs** | The discriminating tests and their pre-committed rules | Test table, before execution | …be edited after execution to fit the result |
| **Executed observations** | The quoted results of running the tests | Test table, `observed result` | …be recalled rather than quoted from the script's captured output |
| **Interpretations** | The assigned statuses | Test table, `interpretation status` | …exceed what the label permits (exploratory suggests, never confirms) |

Domain knowledge and researcher intuition are a rich source of *hypotheses* and never
automatic *evidence*; DAAF-generated hypotheses are *suggestions* requiring an empirical
test and human judgment (SKILL.md loop). The layer separation is what enforces both.

---

## Stopping Rules and the Record-Everything Requirement

**Stopping rules** are pre-committed in the ledger header and enforced during the loop
(the budget counter column tracks position against them). The canonical defaults —
small first bundle (~3 complementary tests), pause to interpret, stop when competing
explanations are covered or two bundles return non-discriminating results, and never
iterate toward a desired finding — are defined in `interpretation-and-evidence.md` §
Test Budgets and Stopping Rules. The ledger is where they are made concrete for the
session and where adherence is auditable.

**Record everything.** Every attempted test is recorded in the test table with its
status — **including nulls, failures, contradictions, and results that weaken the focal
claim or dash the researcher's hope.** A test that returned *does not discriminate* or
*inconclusive* still occupies a row; a test whose script errored is recorded as
attempted-and-failed, not deleted. Omitting inconvenient tests turns the ledger from an
audit trail into a selective advertisement and destroys the coverage map's meaning. The
completeness of the record is what lets the ledger honestly answer "what has been
triangulated, and what did we find" — the whole point of the protocol.