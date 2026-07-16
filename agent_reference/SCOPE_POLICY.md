# Scope Policy Reference

This document is the single canonical source for DAAF's plan scope and task-count
policy. It states the numeric bands ONCE; every other document (data-planner,
plan-checker, WORKFLOW_PHASE2_PLANNING) cites this file rather than restating the
numbers, so the policy has one source of truth and cannot drift.

**Audience / consumers:**
- **data-planner** — pre-return self-check: keep plans within the target band, or
  justify / flag a plan that exceeds it (never return COMPLETE silently on an
  over-target plan).
- **plan-checker** — D6 Scope verification (Step 8): assess the plan against these
  bands and apply complexity-weighted judgment in the warning band.
- **orchestrator** — Stage 4.5 adjudication: when the checker raises a scope
  escalation (21+ tasks), bring the scope question to the user and adjudicate
  between planner and checker based on the user's decision.

---

## Task-Count Bands

Raw total task count (across all waves), interpreted as a proxy for scope — see
**Complexity-Weighted Principle** below.

| Band | Total tasks | Checker behavior |
|------|-------------|------------------|
| **Target** | 5-10 | Passes on count alone |
| **Warning** | 11-20 | PASSED_WITH_WARNINGS on count alone; complexity-weighted judgment may escalate (see below) |
| **Escalation** | 21+ | ISSUES_FOUND with a scope issue → user decision point (see below) |

---

## Warning Band (11-20 tasks): Complexity-Weighted Judgment

A plan of 11-20 tasks is a **warning on count alone** — the checker returns
PASSED_WITH_WARNINGS, not a blocker. Within this band the checker applies
complexity-weighted judgment using dimensions that already exist:

- Transformations/task bands (see Supporting Bands below)
- Tasks/wave load
- Checkpoint / human-gate task types (these weigh lighter — see principle below)
- The red-flag list in `plan-checker.md` Step 8 (wave with 6+ parallel tasks,
  single task with 5+ transformation steps, analysis crammed into one task)

The checker **may escalate a warning-band plan to a blocker only when complexity
drivers stack** — e.g., many 4-5-transformation tasks, crammed multi-operation
tasks, thin checkpoint coverage. When it does, it must **name the specific
drivers**, never the raw count alone. Conversely, a 16-task plan of mechanical,
low-complexity tasks passes with a warning.

**Planner obligation in this band:** when a plan lands in the warning band, the
planner includes a brief **scope justification** in Plan.md's Scope Sizing block
(the Scope Justification field — see `agent_reference/PLAN_TEMPLATE.md`), stating
why this many tasks is warranted for the analysis.

---

## Escalation (21+ tasks): User Decision Point

**21+ tasks is a USER DECISION POINT, not an absolute prohibition.** Never frame it
as "cannot be done."

1. The checker returns **ISSUES_FOUND** with a scope issue recommending a phase
   split (e.g., "Phase A: core analysis with primary sources; Phase B: enhancement
   with secondary sources").
2. The **orchestrator** brings the scope question to the **user**.
3. The user may **approve proceeding at the stated scope** OR **request a split**.
4. **Explicit user approval RESOLVES the count objection.** The orchestrator
   adjudicates between planner and checker based on user input. On re-check, the
   checker treats a documented user-approved scope as satisfying the count
   criterion — all other dimensions are still verified normally.

---

## Pre-Approved Scope (Anti-Churn)

If the user has **already explicitly approved a large scope** before or at planning
time, the planner records that approval in Plan.md's Scope Sizing block (the
Pre-Approved Scope Record field — see `agent_reference/PLAN_TEMPLATE.md`) — **who
approved, when, and what count** — and the checker then does **not raise the count
objection at all**. This prevents a checker/planner round-trip over a scope the
user already signed off on.

---

## Complexity-Weighted Principle

Raw task count is a **proxy**, not the true measure of scope. Scope is properly
judged by:

- **Transformations, joins, and human gates** — the actual work and risk per task
- **Review load** — how much a human reviewer must audit

**Checkpoint and human-gate task types weigh lighter** than `auto` execution tasks:
a `checkpoint:human-verify` or `checkpoint:decision` task is a gate, not a
data-transformation unit of work, and should not count the same toward scope
pressure as an `auto` task that fetches, cleans, or joins data.

---

## Supporting Bands (Unchanged Mechanics)

Restated here for one-stop reading. These are existing rules, not new policy.

| Metric | Target | Warning | Blocker |
|--------|--------|---------|---------|
| Tasks/wave | 2-4 | 5 (hard max) | 6+ |
| Transformations/task | 2-3 | 4 | 5+ |
| Total context est. | ~50% | ~70% | 80%+ |

**Max 5 tasks/wave is a hard dispatch-concurrency limit** — the orchestrator cannot
dispatch more than 5 subagents concurrently. A wave with 6+ parallel tasks is a
blocker (independent tasks beyond 5 split across waves, or the orchestrator
sub-batches). This limit is independent of the total-task-count bands above.
