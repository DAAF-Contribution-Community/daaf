# Data Onboarding: Synthetic Path (Stages DS-1 through DS-5)

Loaded by the orchestrator when a Data Onboarding engagement takes the **synthetic (privacy-preserving) path** — the third intake branch selected at the DI-1 **sensitivity gate** (outcome 3: the data is sensitive/proprietary/regulated and the user is unsure of, or lacks, adequate data-privacy protections). On this path the raw data never enters the DAAF container. Instead, the user runs a disclosure-controlled profiling script on their own machine, reviews what it captured, and hands DAAF only a summary **profile report**; DAAF validates and interprets that report, builds a seeded **synthetic** stand-in dataset from it, and then authors the data source skill with explicit synthetic provenance.

This file contains the DS-stage details, invocation templates, verification checklists, and PSU templates for the synthetic path. The main mode reference file (`data-onboarding-mode.md`) contains the DI-1 sensitivity gate itself, the overall workflow overview, and the standard gate definitions. The domain knowledge — the disclosure-tier ladder, the profiling-script specification, the generation patterns, and the three-part QA model — lives in the `synthetic-data-workflow` skill and its reference files; the agent invocation templates below load that skill on demand. **Do not restate the skill's content here** — cite it.

> **Read the skill's Cardinal Doctrine first.** Synthetic data built from a profile is a **code-development scaffold, not an analytic substitute** (`synthetic-data-workflow` SKILL.md § The Cardinal Doctrine). It is structurally valid but statistically approximate; its only purpose is to let DAAF and the user develop and dry-run analysis code against something shaped like the real data. Every deliverable on this path carries the "finalize against the real data, inside the environment where it lives" requirement. This doctrine is load-bearing for every stage below.

---

## Entry Conditions and What Makes This Path Different

**Entry:** The orchestrator arrives here only after the DI-1 sensitivity gate returns **outcome 3** (see `data-onboarding-mode.md` § Sensitivity Gate). Outcomes 1 (not sensitive) and 2 (sensitive but protections confirmed) both continue on the normal Data Onboarding path (access-method determination → DI-2 → profiling DI-3–6). Outcome 3 short-circuits the normal access-method determination: there is no LOCAL FILE to copy and no in-container API pull of the sensitive data.

**How this path differs from standard profiling (DI-2 through DI-6):**

| Standard path | Synthetic path |
|---------------|----------------|
| Raw data copied into `data/raw/`; profiling scripts load it in-container | Raw data **never enters the container**; the profile report is the source of truth |
| data-ingest runs scripts 01–11 against the real `df` | The user runs a disclosure-controlled profiler locally (DS-2); DAAF works from the returned report |
| QA (QAP1–4) **recomputes statistics against the source file** | QA is **inverted** — it cannot touch raw data. Three checks instead: disclosure-safety of the outbound script, internal consistency of the returned report, and synthetic-vs-profile fidelity (`synthetic-data-workflow` `references/validation-checks.md`) |
| Interpretation (DI-6) reads real column values | Interpretation (DS-4) reads the **report** — column names, dtypes, tier-permitted marginals, relationships — not values |
| Skill authored with `data-provenance: real` | Skill authored with `data-provenance: synthetic-profile-t{1,2,3}` or `synthetic-local-t4`, plus a mandatory "Synthetic Data Notice" section |

**Stage sequence (replaces DI-2's raw-data staging and DI-3 through DI-6):**

```
DI-1 sensitivity gate → outcome 3
   → DI-2 (project setup, synthetic variant — no data/raw/ copy)
   → PSU-DS1: Tier Selection & Setup Confirmation (user gate)
   → DS-1  Script Preparation           (research-executor → code-reviewer QAS-A: disclosure-safety)
   → DS-2  User Local Run                (HUMAN STEP, outside the container — wait state)
   → DS-3  Report Intake & Validation    (research-executor → code-reviewer QAS-B: report consistency)
   → DS-4  Interpretation                (data-ingest → PSU-DS2 findings review, user gate)
   → DS-5  Synthetic Generation & Validation (research-executor → code-reviewer QAS-C: synthetic-vs-profile)
   → Pre-Authoring Research Offer (optional, same as standard path)
   → rejoin DI-7 / DI-8 (skill authoring with synthetic-provenance overrides)
```

**DI-2 setup, synthetic variant.** Create the research project folder as normal, but:
- **Do NOT** create or populate `data/raw/` with the sensitive file (it will never be present).
- Create `data/profile_report/` (holds the returned JSON + `.txt`), `data/synthetic/` (holds the generated seeded parquet — never `data/raw/`), and `output/preliminary_notes/`.
- Initialize STATE.md from `agent_reference/STATE_TEMPLATE_ONBOARDING.md` and populate the **Synthetic Path Tracking** section (records the sensitivity-gate outcome, chosen tier, suppression threshold, relationship spec, report/synthetic file paths, and per-stage DS status). All synthetic-path progress is tracked in that section throughout this workflow.

---

## Wave / Gate Discipline (Async Dispatch)

Subagents dispatched via the Agent tool run in the background and return via completion notifications that may arrive one at a time. Every "wait for the agent to return" instruction below is a **hard barrier**: do not evaluate QA severity, update STATE.md conclusions, advance to the next DS stage, or present a user gate until the dispatched subagent has actually returned. Where a stage dispatches an agent and then its reviewer, treat them sequentially — the reviewer is dispatched only after the producing agent has returned and its output has been persisted. See the master statement in `SKILL.md` § Subagent Coordination > "Wave Barrier Discipline (Async Dispatch)."

Each DS stage is an atomic unit: producer → reviewer → evaluate severity → (revise if BLOCKER) → update STATE.md → proceed. This mirrors the standard Per-Part Execution Cycle (`data-onboarding-mode.md` § Per-Part Execution Cycle); the difference is only in which agents act and what they review.

---

## Gate Definitions (Synthetic Path)

These gates replace GDI-2 through GDI-6 for the synthetic path. GDI-7 and GDI-8 (skill authoring and delivery) still apply after rejoin.

| Gate | After Stage | Criteria | STOP If |
|------|-------------|----------|---------|
| GDS-0 | PSU-DS1 | Tier confirmed by user; suppression threshold set; relationship spec (T3) collected if wanted; setup summary confirmed | User declines to choose a tier or wants to reconsider the sensitivity decision |
| GDS-1 | DS-1 | Customized profiling script prepared; **QAS-A disclosure-safety review PASSED** (no forbidden emission reachable at the chosen tier) | QAS-A finds any possible disclosure leak (BLOCKER — a leak is irreversible once the report is shared) |
| GDS-2 | DS-2 | User confirms they ran the script, reviewed the `.txt` summary, and returned the JSON report; report file present in `data/profile_report/` | User cannot run the script, or the run failed, or the user is not comfortable sharing the report after review |
| GDS-3 | DS-3 | Report loads; `report_version` recognized; **QAS-B internal-consistency PASSED** (or WARNING) | Report corrupt/untrustworthy (b2/b3/b4/b6/b9), or a sub-threshold cell slipped through (b5 — also a disclosure event; notify the user) |
| GDS-4 | DS-4 | Interpretation complete, all `[PRELIMINARY]`; **PSU-DS2 findings confirmed by user** | User rejects the interpretation basis and no revised interpretation can be agreed |
| GDS-5 | DS-5 | Synthetic parquet in `data/synthetic/`; seed recorded; **QAS-C synthetic-vs-profile PASSED** (or WARNING) | Generation bug or disclosure-adjacent failure (c1/c2/c7/c8), or a missing seed (c10 — a BLOCKER by default; only the narrow, researcher-authorized T4 exception in § T4 Variant may proceed without one) |

**Severity mapping** for QAS-A/B/C is defined in `synthetic-data-workflow` `references/validation-checks.md` § Severity mapping — follow it verbatim; it gives the default severity of each finding. In short: any disclosure-safety uncertainty (QAS-A), and any sub-threshold cell in a returned report — a categorical/`__OTHER__` cell (QAS-B b5) or a lone suppressed cross-tab cell (QAS-B b12) — are BLOCKERs, never WARNINGs. A missing generation seed (QAS-C c10) is a BLOCKER **by default**, with a single narrow carve-out layered on top of that default: the researcher-authorized T4 missing-seed exception defined in § T4 Variant.

---

## PSU-DS1: Tier Selection & Setup Confirmation

Present after DI-2 setup completes and before dispatching DS-1. This is the synthetic-path analog of PSU-DI1, and it additionally asks the user to choose a disclosure tier — the single most consequential design decision on this path. **Plain language only** — no internal terms (tier-forbidden-emissions, QAS, DS-N).

Before presenting, read `synthetic-data-workflow` `references/disclosure-tiers.md` so the tier explanations are accurate. Frame the choice around the **lowest tier that still lets the code development proceed** (remove only as much protection as the task forces you to give up).

```
**Synthetic Data Onboarding: Setup Complete — One Choice Before We Start**

Because this dataset is sensitive and we're using the privacy-preserving path, your
real data will never enter DAAF. Here's what will happen: I'll prepare a small
profiling script; you'll run it on your own machine where the data lives; you'll
review exactly what it captured; and you'll send me back only that summary. From
the summary I'll build a realistic *synthetic* stand-in and develop all the
analysis code against it.

**One important note up front:** the synthetic data is a stand-in for *building and
testing code*, not for producing findings. Any real results have to come from
re-running the finished code against your real data, in the environment where it
lives. I'll carry that reminder through everything we build.

**Project folder:** [absolute path to research project]
**Source name:** [source-name]   **Target skill:** [skill-name]

**How much detail should the summary capture?** More detail makes the synthetic
data more realistic but shares a little more about your data's shape. Nothing about
any individual record ever crosses over at any level.

- **Level 1 — Structure only:** just column names, types, and the row count. Safest;
  the synthetic data will have the right shape but random values.
- **Level 2 — Structure + per-column summaries (default):** adds, for each column,
  its distribution summarized as percentiles (never raw minimums/maximums), category
  labels with small groups hidden, and how often values are missing. Good realism for
  most code development.
- **Level 3 — Level 2 + relationships:** adds how columns move together (correlations,
  association between categories). Choose this if your analysis code depends on
  relationships between variables.
- **Level 4 — You synthesize locally:** if you need very high fidelity, you run a
  synthesizer on your machine and send only the resulting fake rows — never the real
  data or the fitted model. More setup on your end; I'll provide the template.

  *Are there specific relationships you need preserved — say, a key outcome and a key
  predictor? Level 3 captures those as correlations; nothing about individual records
  crosses over. If your code doesn't lean on cross-variable relationships, Level 2 is
  usually plenty.*

**Small-group hiding:** by default, any category with fewer than **5** records is
hidden and folded into an "other" bucket, so no small group can be singled out. I can
raise that threshold if you'd like more caution.

**My recommendation:** [seed from intake — e.g., "Level 2, since your described
analysis is column-level distributions" OR "Level 3, since you mentioned needing the
outcome~exposure relationship"].

**Which level would you like, and is the small-group threshold of 5 okay?**
```

Record the confirmed tier, suppression threshold, and any named relationship spec in STATE.md's **Synthetic Path Tracking** section (Key Decisions Made as well). Gate GDS-0.

---

## DS-1: Script Preparation

**Purpose:** Prepare the disclosure-controlled profiling script the user will run locally. | **Producer:** research-executor | **Reviewer:** code-reviewer (QAS-A) | **Skill:** `synthetic-data-workflow` (loaded on demand)

research-executor **copies** the shipped asset template into the project and customizes the copy — it never edits or executes the shipped asset in place (execution logs would pollute the pristine template). The customized script is destined to run on the **user's machine, outside DAAF**, so the DAAF file-first execution protocol does **not** apply to it — research-executor writes and customizes it but does **not** execute it in-container. The customization *itself* is what gets reviewed (QAS-A), because a disclosure leak here is irreversible once the user shares the report.

### DS-1 research-executor Invocation Template

```python
Agent({
    description: "DS-1: Prepare disclosure-controlled profiling script",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.
**PROJECT_DIR:** {absolute path to research project}

**AGENT PROTOCOL:** Read `.claude/agents/research-executor.md`.
**LOAD SKILL:** Invoke the `synthetic-data-workflow` skill (Skill tool). Read
`references/profiling-script-spec.md` (the outbound-script contract and JSON schema)
and `references/disclosure-tiers.md` (what the chosen tier may and may not emit).

**TASK:** Copy the shipped profiling asset template into this project and customize
the copy for the user's file and chosen disclosure tier. Do NOT execute it — it runs
on the user's own machine outside DAAF.

**CONTEXT:**
- Chosen tier: {1 | 2 | 3}
- Suppression threshold: {default 5, or user value}
- Relationship spec (T3 only): {named outcome~predictor pairs / cross-tab pairs, or none}
- Execution language: R (user preference) — copy `assets/profile_data_template.R`
  (use the `.py` template only if the user's local environment is Python-only)
- Source name / dataset slug: {source_name} / {dataset_slug}
- Expected file format on the user's machine: {CSV / parquet / Stata / ...}
- Max categorical levels before high-cardinality treatment: {default 50}

**INSTRUCTIONS:**
1. Copy `{BASE_DIR}/.claude/skills/synthetic-data-workflow/assets/profile_data_template.R`
   to `{PROJECT_DIR}/scripts/local_profiling/profile_{dataset_slug}.R`. Copy — never
   move or edit the shipped asset.
2. Fill ONLY the `# --- Config (EDIT THESE) ---` block: INPUT_PATH placeholder (the
   user sets their own path), DATASET_NAME, OUTPUT_DIR, TIER, SUPPRESSION_THRESHOLD,
   RELATIONSHIP_SPEC (T3 only), MAX_CATEGORICAL_LEVELS. Leave the profiling body's
   suppression logic exactly as shipped — suppression is structural, not a flag.
3. Preserve every IAT comment and the loud REVIEW-BEFORE-SHARING closing block.
4. Confirm the script is zero-DAAF-dependency (no DAAF paths, no network, no sourcing)
   and self-contained per `profiling-script-spec.md` § design-constraints.
5. Do NOT run the script. Return its path and a plain-language "how to run it"
   summary the orchestrator can relay to the user.

**OUTPUT FORMAT:** research-executor standard return. Emphasize: customized script
path; the exact Config values set; the two output files it will produce
({dataset}_profile_report.json + .txt); confirmation it is safe to hand to a
non-programmer; any tier/spec ambiguity for the orchestrator to resolve.""",
    subagent_type: "research-executor"
})
```

After research-executor returns, persist the full return to `output/preliminary_notes/{date}_ds1_script-preparation.md`, then dispatch QAS-A.

### DS-1 code-reviewer Invocation Template (QAS-A: Disclosure-Safety)

```python
Agent({
    description: "QAS-A: Disclosure-safety review of the outbound profiling script",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**AGENT PROTOCOL:** Read `.claude/agents/code-reviewer.md`. This is a Data Onboarding
synthetic-path QA — there is no Plan.md and no raw data to recompute against. Your job
is a **static disclosure-safety review** of a script that will touch real sensitive
data on the user's machine.
**LOAD SKILL:** Invoke `synthetic-data-workflow`. Read `references/validation-checks.md`
§ (a) Disclosure-safety and `references/disclosure-tiers.md` § forbidden-emissions.

**SCRIPT TO REVIEW:** {PROJECT_DIR}/scripts/local_profiling/profile_{dataset_slug}.R
**Chosen tier:** {1 | 2 | 3}   **Suppression threshold:** {n}

**TASK:** Trace EVERY emission path for whether the configured script can emit anything
the chosen tier forbids. Work the FULL checklist a1–a10 from validation-checks.md § (a). Pay
special attention to a6 (edge cases — the all-null column, the single-distinct-value
column, the two-level column with one small cell, the identifier that slips the
uniqueness heuristic) and its companion edge-case checks: a8 (a residual `__OTHER__` below
threshold must roll in the smallest retained levels — a bare `__OTHER__ = sum(binned)` with
no roll-in is a leak), a9 (small-n / near-constant / all-missing numerics degrade to
quartiles-only or withhold the value, and must not crash `quantile([])`), and a10 (T3
cross-tab suppression is complementary and `null`-coded, so no row/col has a lone
recoverable suppressed cell). The common leak is the edge case, not the main path. Trace the
smallest-cell case for every categorical/cross-tab emission. You may write a probe that
feeds SYNTHETIC toy input to the script to exercise these edge cases (never real data —
you do not have it), but the review is primarily static.

**SEVERITY:** Any item that is not clearly safe is a FAILURE. A possible leak is a
**BLOCKER**, never a WARNING (a disclosure leak is irreversible once the report is
shared). Do not pass the gate on "probably fine."

**OUTPUT FORMAT (3500-word cap):**
### QAS-A: Disclosure-Safety Review
**Status:** [PASSED | BLOCKER]
**Checklist a1–a10:** [table with pass/fail + evidence per item]
**Edge cases traced:** [which, and the emission each produces]
**Issues Found:** [BLOCKER list with exact code path + fix]
**Recommendation:** [PROCEED (safe to hand to user) | REVISION_REQUIRED]""",
    subagent_type: "code-reviewer"
})
```

**Revision flow (if QAS-A BLOCKER):** re-invoke research-executor to produce a versioned fix (`profile_{dataset_slug}_a.R`), re-invoke QAS-A. Max 2 self-revisions before escalating to the user. **Never hand the user a script that has not passed QAS-A.** Update STATE.md Synthetic Path Tracking (DS-1 status, QAS-A result), then proceed to DS-2. Gate GDS-1.

---

## DS-2: User Local Run (Human Step — Outside the Container)

This stage runs entirely on the user's machine; DAAF does nothing but wait. Present the handoff instructions in plain language, then enter a **wait state**.

### User-Facing Handoff (relay to the user)

```
**Your turn — run the profiling script on your own machine**

I've prepared a small, self-contained profiling script and had it independently
reviewed to confirm it only captures the summary you approved (Level {N}, small groups
under {threshold} hidden) and nothing that could identify an individual record.

**1. Get the script onto the machine where your data lives.**
   The script is at:
   `{PROJECT_DIR}/scripts/local_profiling/profile_{dataset_slug}.R`
   Copy it out to your machine the same way you move files in and out of DAAF — for
   example, drag it out of the browser code editor, or copy it from the project folder
   via Docker Desktop. (See `user_reference/01_installation_and_quickstart.md` for the
   file-exchange options.)

**2. Point it at your data and run it — on YOUR machine, not in DAAF.**
   Open the script, set `INPUT_PATH` (and `OUTPUT_DIR`, a local folder) at the top,
   then run it with a single command in your own terminal:
   `Rscript profile_{dataset_slug}.R`
   (If your local environment is Python, it's `python profile_{dataset_slug}.py`.)
   It needs only a standard R (or Python) install — no DAAF, no internet.

**3. It produces two files:**
   - `{dataset_slug}_profile_report.json` — the machine-readable summary I'll work from
   - `{dataset_slug}_profile_report.txt` — a plain-English version for YOU to read

**4. Review the `.txt` before you share anything — this is the important step.**
   Read the whole `.txt`. Confirm:
   - No column *name* itself gives away something sensitive.
   - Every category label listed is safe to share, and every small group is shown as
     hidden/"other" (check the "What was suppressed" section).
   - If you chose Level 3, look at each named relationship you asked me to preserve and
     confirm you're comfortable sharing it.
   - The tier and threshold at the top match what you intended.
   - The script's own checks all passed (if any failed, don't share — tell me).

**5. Send me back only the `.json` file** (the `.txt` is yours to keep). Bring it into
   the project's `data/profile_report/` folder the same way you took the script out —
   browser code editor drag-and-drop or Docker Desktop.

Take your time. When the report is in `data/profile_report/`, tell me and we'll
continue. Nothing else from your data ever needs to leave your machine.
```

### Wait State

DS-2 is a natural **session-suspension boundary**. Update STATE.md Synthetic Path Tracking:
- DS-1 = complete (QAS-A PASSED); DS-2 = **awaiting user local run**.
- Record the expected report filename and its target path (`data/profile_report/{dataset_slug}_profile_report.json`).
- Set Next Actions to "Resume at DS-3 once the user confirms the report is in `data/profile_report/`."
- Write a restart prompt so a fresh session can resume cleanly.

The session may end here and resume later. When the user returns and confirms the report is placed, verify the JSON file exists and is non-empty, then proceed to DS-3. Gate GDS-2.

---

## DS-3: Report Intake & Validation

**Purpose:** Confirm the returned report is internally coherent and trustworthy before anything is built from it. | **Producer:** research-executor (consistency-check script) | **Reviewer:** code-reviewer (QAS-B) | **Skill:** `synthetic-data-workflow`

The report is now in-container (`data/profile_report/`), so unlike the outbound-script review this stage **can** compute — but only over the report's own numbers, never raw data. The embedded `validation.all_passed` in the report is the *user's* claim; DAAF re-verifies it independently.

### DS-3 research-executor Invocation Template

```python
Agent({
    description: "DS-3: Validate returned profile report internal consistency",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.
**PROJECT_DIR:** {absolute path to research project}
**AGENT PROTOCOL:** Read `.claude/agents/research-executor.md`. Read
`agent_reference/SCRIPT_EXECUTION_REFERENCE.md` — this script IS executed in-container
(file-first protocol applies; use run_with_capture.sh).
**LOAD SKILL:** Invoke `synthetic-data-workflow`. Read `references/validation-checks.md`
§ (b) Internal-consistency and `references/profiling-script-spec.md` § json-schema.

**REPORT:** {PROJECT_DIR}/data/profile_report/{dataset_slug}_profile_report.json

**TASK:** Write and execute an R consistency-check script that re-verifies checks b1–b12
from validation-checks.md § (b) against the report's own numbers — do NOT trust the
embedded `all_passed`; recompute. Confirm: report_version recognized; percentiles
monotone; category counts (incl. __OTHER__) ≤ row_count; missing rates in [0,1]; NO
emitted cell has a count in (0, suppression_threshold); (T3) correlation matrices square,
symmetric, unit-diagonal, entries in [-1,1], smallest eigenvalue ≥ -1e-6; suppression
settings recorded; each column's stat block matches its role; embedded validation
present and passing; (T3) cross-tab schema well-formed — `cells` length = `rows`×`cols`,
suppressed cells encoded as `null` (never `0`), and `cells_suppressed` equals the count of
`null` cells (b11); (T3) no cross-tab row or column has exactly one `null` cell unless the
whole table is marked `"collapsed": true` (b12 — a lone suppressed cell is recoverable by
differencing against the margins).

Script path: `{PROJECT_DIR}/scripts/profile_report_intake/01_validate-report.R`
Execute: bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/profile_report_intake/01_validate-report.R
Flat sequential style; IAT comments; stopifnot() + cat() validation.

**OUTPUT FORMAT:** research-executor standard return. Emphasize per-check b1–b12 result,
any check that failed and the specific column/value, and whether a sub-threshold cell is
present (b5, or a lone suppressed cross-tab cell b12 — each is BOTH a consistency failure
AND a disclosure event to escalate).""",
    subagent_type: "research-executor"
})
```

Persist the return to `output/preliminary_notes/{date}_ds3_report-intake.md`, then dispatch QAS-B.

### DS-3 code-reviewer Invocation Template (QAS-B: Report Consistency)

```python
Agent({
    description: "QAS-B: Independent review of report internal-consistency validation",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.
**AGENT PROTOCOL:** Read `.claude/agents/code-reviewer.md`. Data Onboarding synthetic-path
QA — no raw data; validate the report's coherence and the DS-3 script's correctness.
**LOAD SKILL:** Invoke `synthetic-data-workflow`. Read `references/validation-checks.md`
§ (b) and § Severity mapping.

**SCRIPT TO REVIEW:** {PROJECT_DIR}/scripts/profile_report_intake/01_validate-report.R
**REPORT:** {PROJECT_DIR}/data/profile_report/{dataset_slug}_profile_report.json

**TASK:** Verify the DS-3 script genuinely re-computes b1–b12 (not merely echoing the
report's embedded all_passed). Independently spot-check the load-bearing checks (b2
percentile monotonicity, b3 counts ≤ row_count, b5 no sub-threshold cells) and, at T3, the
cross-tab integrity checks (b11 schema well-formedness, b12 no lone suppressed cell). Create
QA script(s) at `scripts/cr/qas_b_report-consistency.R` and execute via run_with_capture.sh.

**SEVERITY** (validation-checks.md § Severity mapping): b5 sub-threshold cell present =
BLOCKER + a disclosure event (tell the user their shared report contains a small cell);
b2/b3/b4/b6/b9 failures = BLOCKER (report corrupt — do not generate from it); (T3) b12 lone
suppressed cross-tab cell = BLOCKER + a disclosure event (recoverable by differencing
against the margins); b11 malformed cross-tab schema = BLOCKER (signals a tampered report);
b7 mild non-PSD = WARNING (project to nearest PD, note it).

**OUTPUT FORMAT (3500-word cap):**
### QAS-B: Report Consistency Review
**Status:** [PASSED | WARNING | BLOCKER]
**Checks b1–b12:** [table]
**Issues Found / Recommendation**""",
    subagent_type: "code-reviewer"
})
```

Revision flow mirrors DS-1 (versioned script fixes, max 2, then escalate). Note: a BLOCKER here usually means the *report* is bad, not the DS-3 script — if the report is corrupt or contains a sub-threshold cell, the fix is to inform the user and (for a disclosure event) have them discard the shared report and re-run a corrected profiler, not to re-run the DS-3 script. Update STATE.md Synthetic Path Tracking. Gate GDS-3.

---

## DS-4: Interpretation

**Purpose:** Read the validated report as a data dictionary — the synthetic-path analog of standard Part D (DI-6). | **Producer:** data-ingest | **User gate:** PSU-DS2 | **Skill:** `synthetic-data-workflow`

This is the one DS stage that requires interpretive (LLM) reasoning, and it is performed by **data-ingest** — the same agent that interprets in standard onboarding — but working from the *report* instead of raw data. Script 10's inputs (column names, dtypes, value patterns, distributions, relationships) are exactly what the report carries, so semantic interpretation is feasible; confidence depends on how much the tier preserved. All interpretations are marked `[PRELIMINARY]`, exactly as in standard Part D.

### DS-4 data-ingest Invocation Template

```python
Agent({
    description: "DS-4: Interpret the profile report (semantic classification, data dictionary)",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.
**PROJECT_DIR:** {absolute path to research project}
**AGENT PROTOCOL:** Read `.claude/agents/data-ingest.md`. This is the synthetic-path
interpretation stage — the analog of Part D (script 10 semantic-interpretation), but your
input is the profile REPORT, not raw data. There is no `df` to load and no in-container
data-touching profiling; work entirely from the report JSON.
**LOAD SKILL:** Invoke `synthetic-data-workflow`. Read `references/profiling-script-spec.md`
§ json-schema so you read the report structure correctly.

**REPORT:** {PROJECT_DIR}/data/profile_report/{dataset_slug}_profile_report.json
**Tier:** {N}   **Domain context:** {domain_context}   **Intended use:** {intended_use}
**Documentation (if the user provided any):** {doc_paths_or_none}

**TASK (adapt Part D semantic interpretation to the report):**
1. Column semantic classification from names + dtypes + tier-permitted stats:
   name-pattern matching (FIPS->geo, _id->identifier, _pct->percentage, _cd->categorical),
   value-pattern inference from percentiles/levels (binary, year-like, percentage-like),
   join-key candidates (from is_identifier flags + uniqueness ratios).
2. Draft data dictionary — ALL entries marked [PRELIMINARY]. State the report-based
   BASIS for each (e.g., "9 suppressed-and-binned levels, uniqueness 0.001 → low-
   cardinality categorical").
3. Domain decomposition: group columns into analytical domains; note which warrant a
   dedicated reference file in the eventual skill.
4. Exclusion / population-boundary observations inferable from the report or docs.
5. Interpretation-confidence caveat: explicitly flag where the chosen tier LIMITED your
   confidence (e.g., "at Level 2 no cross-column relationships were shared, so join
   cardinality is inferred from uniqueness alone, not observed").

**CONSTRAINT:** You must not ask for, and will not be given, the raw data or any raw
values. Interpret only what the report contains. If a column's meaning cannot be
inferred from the report, say so — do not guess beyond the report.

**OUTPUT FORMAT:** data-ingest standard return. Emphasize the full [PRELIMINARY]
interpretation table (every column — this feeds the PSU-DS2 user review), domain
decomposition, exclusions, and the per-interpretation confidence with its tier-driven
limits.""",
    subagent_type: "data-ingest"
})
```

Persist the return to `output/preliminary_notes/{date}_ds4_interpretation.md`.

### PSU-DS2: Interpretation Findings Review (User Gate)

The synthetic-path analog of PSU-DI2 — the CRITICAL review point where interpretations become the basis for the skill. Use the **PSU-DI2 template** from `data-onboarding-mode.md` (Preliminary Interpretations table; CONFIRM / REJECT / MODIFY per row), with two synthetic-path additions:

1. State plainly that these interpretations come from the **profile summary, not the raw data**, and note where the chosen level limited confidence — so the user calibrates their review. (E.g., "Because we captured Level 2, I inferred the join keys from uniqueness rather than observing how the tables actually link — please confirm these if you know them.")
2. Keep the synthetic-scaffold reminder visible: what we confirm here shapes the *code-development* skill; findings still require the real data.

After the user responds, update STATE.md Synthetic Path Tracking AND Interpretation Tracking sections (Interpretation Tracking is a separate top-level section; record User Decision + Final Interpretation for every row) — this is a mandatory gate, DS-5 and DI-7 cannot proceed until every row has a Final Interpretation. Then present the standard **Pre-Authoring Research Offer** (`data-onboarding-mode.md` § Pre-Authoring Research Offer) exactly as on the normal path. Gate GDS-4.

---

## DS-5: Synthetic Generation & Validation

**Purpose:** Build a seeded synthetic dataset from the report and confirm it faithfully reflects the profile. | **Producer:** research-executor | **Reviewer:** code-reviewer (QAS-C) | **Skill:** `synthetic-data-workflow`

Generation is **profile-only** (from declarations — marginals + correlation matrix — never microdata), so it runs *inside* DAAF on the returned report. **All generation is seeded** and the seed is recorded; output parquet goes to `data/synthetic/` (never `data/raw/`).

### DS-5 research-executor Invocation Template (Generation)

```python
Agent({
    description: "DS-5: Generate seeded synthetic dataset from the profile report",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.
**PROJECT_DIR:** {absolute path to research project}
**AGENT PROTOCOL:** Read `.claude/agents/research-executor.md`. Read
`agent_reference/SCRIPT_EXECUTION_REFERENCE.md` — executed in-container (file-first;
run_with_capture.sh).
**LOAD SKILL:** Invoke `synthetic-data-workflow`. Read `references/generation-patterns-r.md`
(flagship path) and `references/validation-checks.md` § (c).

**REPORT:** {PROJECT_DIR}/data/profile_report/{dataset_slug}_profile_report.json
**Tier:** {N}   **Seed:** {choose and RECORD a fixed integer seed}

**TASK:** Write and execute an R generation script that builds a synthetic dataset
matching the report:
- **R flagship: simstudy** — Gaussian copula via genCorGen/addCorGen from the reported
  marginals + correlation matrix; base-R copula fallback per generation-patterns-r.md if
  simstudy is unavailable. (Python equivalent: NumPy/SciPy Gaussian-copula per
  generation-patterns-python.md — only if the project is Python.)
- Draw categoricals ONLY from the report's emitted levels; keep `__OTHER__` as an
  aggregate bucket — never invent real-looking rare values.
- Identifier columns: structurally shaped but value-free (Faker-style / synthetic
  patterns) — never anything resembling a real identifier or routable value.
- Match row_count; seed the RNG and print the seed.
- Write to `{PROJECT_DIR}/data/synthetic/{date}_{dataset_slug}_synthetic.parquet`
  (arrow::write_parquet). Print a generation log: seed, row/col counts, per-column method.

Script path: `{PROJECT_DIR}/scripts/synth_generate/01_generate-synthetic.R`
Execute: bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/synth_generate/01_generate-synthetic.R

**OUTPUT FORMAT:** research-executor standard return. Emphasize: synthetic parquet path,
recorded seed, generation method per column, and any marginal/correlation the copula
could not reproduce well (flag binary/low-cardinality correlations — recovered less
faithfully).""",
    subagent_type: "research-executor"
})
```

Persist the return to `output/preliminary_notes/{date}_ds5_generation.md`, then dispatch QAS-C.

### DS-5 code-reviewer Invocation Template (QAS-C: Synthetic-vs-Profile)

```python
Agent({
    description: "QAS-C: Validate synthetic data against the profile report",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.
**AGENT PROTOCOL:** Read `.claude/agents/code-reviewer.md`. Data Onboarding synthetic-path
QA — validate the GENERATED synthetic data against the profile (within tolerance, because
profile-based synthesis is approximate by design).
**LOAD SKILL:** Invoke `synthetic-data-workflow`. Read `references/validation-checks.md`
§ (c) and § Tolerances.

**SYNTHETIC:** {PROJECT_DIR}/data/synthetic/{date}_{dataset_slug}_synthetic.parquet
**REPORT:** {PROJECT_DIR}/data/profile_report/{dataset_slug}_profile_report.json
**GENERATION SCRIPT:** {PROJECT_DIR}/scripts/synth_generate/01_generate-synthetic.R

**TASK:** Create and execute QA script(s) at `scripts/cr/qas_c_synthetic-validation.R`
checking c1–c11: row count matched; column set + types matched; numeric marginals within
tolerance; categorical proportions within tolerance; __OTHER__ preserved as a bucket;
(T3) correlations reproduced within tolerance (looser for binary/low-cardinality);
suppressed categories absent from synthetic; identifiers structurally shaped and value-
free (do not resemble anything real, no routable domain/format); missingness within
tolerance; **seed recorded in the generation log**; (T3) each named relationship
reproduced — the synthetic OLS slope of `outcome ~ predictor` within ±10% of the reported
slope and R² within ±0.10 (c11). Use the § Tolerances defaults.

**SEVERITY** (§ Severity mapping): c1/c2/c7/c8 = BLOCKER (generation bug or disclosure
risk); c10 missing seed = BLOCKER **by default** — the reviewer always reports a missing
seed as a BLOCKER finding; only the orchestrator, with explicit researcher authorization at
the gate, may waive it via the T4 missing-seed path (see § T4 Variant below); c3/c4/c6/c9/c11 out of
tolerance = WARNING (investigate — may be an acceptable approximation limit).

**OUTPUT FORMAT (3500-word cap):**
### QAS-C: Synthetic-vs-Profile Review
**Status:** [PASSED | WARNING | BLOCKER]
**Checks c1–c11:** [table]
**Issues Found / Recommendation**
Note: passing means "structurally faithful to the profile," NEVER "analytically valid."""",
    subagent_type: "code-reviewer"
})
```

Revision flow mirrors the other stages. Update STATE.md Synthetic Path Tracking (DS-5 status, synthetic parquet path, seed, QAS-C result). Gate GDS-5.

### T4 Variant — User Ran Local High-Fidelity Synthesis

If the user chose **Level 4** at PSU-DS1, DS-1/DS-2 hand the user a **synthesizer** template instead of (or alongside) the profiler:

- **DS-1 (T4):** research-executor copies `assets/synthesize_local_template.R` (synthpop CART, flagship) — or `.py` (SDV GaussianCopula) — into `scripts/local_profiling/`, customizes the Config, and QAS-A reviews it for the same disclosure discipline **plus** the T4-specific guarantee that only synthetic *rows* — never the real data and never the fitted model artifacts — are emitted (see `synthetic-data-workflow` `references/local-synthesis-t4.md`).
- **DS-2 (T4):** the user runs the synthesizer locally; only the synthetic rows cross the boundary. **Parquet is the preferred exchange format**; CSV is a permitted fallback only when the user's local environment lacks Arrow/PyArrow — the **audited boundary exception** (see DS-5 below and `synthetic-data-workflow` `references/local-synthesis-t4.md`). Optionally a T2/T3 profile report crosses too, if they also ran the profiler, which enables a stronger QAS-C.
- **DS-5 becomes import + validation** rather than generation. **If the rows arrived as CSV (the audited boundary exception), the FIRST in-container action is to convert the CSV to Parquet and record an exchange manifest** (a JSON sidecar named `{converted_filename}_exchange_manifest.json`) beside the converted file — capturing the original filename, source format, row and column counts, the file hash (e.g., SHA-256), and the conversion timestamp — after which all subsequent in-container work uses only the converted Parquet (the framework's in-container Parquet-only rule is thereby preserved: Parquet-only, with one audited exception at this T4 local-exchange boundary). If the rows arrived as Parquet, import them directly. research-executor imports the user-supplied synthetic data into `data/synthetic/`; QAS-C validates it **against the profile report if one was also produced**, or **against the user's declared metadata** (row count, column set/types, declared marginals) if no report accompanies it.
- **Missing-seed policy (default BLOCKER, one narrow T4 exception).** The seed requirement (c10) applies to the *user's* synthesis log — request it. A missing seed is a **BLOCKER by default** (as at GDS-5 and in QAS-C severity): synthetic data without a recorded seed is not reproducible. T4 is the **sole exception path**, and it may proceed only under all three of these conditions: (1) **explicit researcher authorization at the gate** — the orchestrator must ask the researcher directly and may never auto-waive the requirement; (2) the resulting artifact is labeled a **"non-reproducible T4 synthetic artifact"**, and that status is carried both in the artifact's provenance and in the skill's Synthetic Data Notice; (3) the artifact remains eligible for downstream skill delivery (rejoin DI-7/DI-8), but the delivered skill's Synthetic Data Notice MUST carry the non-reproducibility qualification. If the researcher does not authorize the exception, the missing seed stays a BLOCKER — request a re-run that records one.

Everything downstream of DS-5 (rejoin DI-7/DI-8) is identical across T1–T4 except the `data-provenance` value.

---

## Rejoin DI-7 / DI-8: Skill Authoring with Synthetic Provenance

After DS-5 passes, skill authoring proceeds per `WORKFLOW_PHASE_DO_AUTHORING.md` (Stages DI-7/DI-8) — same authoring agent, same template, same delivery — with these **synthetic-provenance overrides**. Pass all of them into the DI-7 authoring invocation:

1. **`data-provenance` frontmatter** set to the tier value: `synthetic-profile-t1`, `synthetic-profile-t2`, `synthetic-profile-t3`, or `synthetic-local-t4` (never `real`). This key and its vocabulary are defined in `DATA_SOURCE_SKILL_TEMPLATE.md`.
2. **Mandatory "Synthetic Data Notice" section** in the skill (per the template): states that the skill was built from a disclosure-controlled profile of sensitive data the container never saw; that the bundled/example data is synthetic; and — foregrounded — the scaffold-not-substitute doctrine: **all findings must be finalized by re-running the vetted code against the real data, in the environment where the real data lives.** If the artifact was produced under the authorized T4 missing-seed exception (§ T4 Variant), the Notice MUST additionally carry the **"non-reproducible T4 synthetic artifact"** qualification.
3. **Every skill mention of the data carries the scaffold caveat.** Decision trees, example fetches, and quick-reference tables that reference the dataset note that values are synthetic and structurally (not analytically) representative.
4. **Bundle the provenance scripts** into `.claude/skills/{skill_name}/scripts/` (the existing DI-7 script-bundling pattern): the customized local profiling script (`profile_{dataset_slug}.R`), the DS-3 report-intake validator, and the DS-5 generation script — so the whole synthetic construction is reproducible. Do **not** bundle the profile report itself unless the user explicitly approves (it is a summary of their sensitive data); reference its schema instead.
5. **Data Access section** documents the two-world reality: the synthetic parquet in `data/synthetic/` is for code development; real analysis runs where the real data lives. If the user documented an access pattern for the real data (path, enclave, connection), record it as the production path with the synthetic file as the development stand-in.

DI-8 delivery is standard, but the final delivery message must surface the provenance: name the tier, state that the shipped data is synthetic, and repeat the finalize-against-real-data requirement. LEARNINGS.md consolidation is standard; note any tier/fidelity limitations discovered as Data Quality Notes.

---

## Boundaries (Synthetic Path)

These supplement the Data Onboarding boundaries in `data-onboarding-mode.md` and the universal boundaries in `CLAUDE.md`. On this path, the disclosure boundary is the whole point — treat every one as non-negotiable.

**Always Do:**
1. Pass QAS-A (disclosure-safety) before the user ever runs the outbound script — a possible leak is a BLOCKER, never a WARNING.
2. Have the user review the `.txt` summary before they share the JSON — the human disclosure review is a required gate (DS-2), not a formality.
3. Seed all generation and record the seed; write synthetic parquet to `data/synthetic/`.
4. Carry the scaffold-not-substitute doctrine into every deliverable and every skill mention of the data.

**Never Do:**
1. **Never request or accept the raw sensitive file** once the synthetic path is chosen — not "just a few rows," not a sample, not unsuppressed cross-tabs, not example values, not the fitted synthesis model. If a step seems to need any of these, stop and re-scope to a tier that does not.
2. **Never attempt to reconstruct suppressed values or infer beyond the report.** `__OTHER__` stays an aggregate; suppressed small cells stay suppressed; interpretation does not guess past what the report contains.
3. **Never write synthetic data to `data/raw/`** — `data/raw/` implies real provenance and is empty on this path by design.
4. **Never present synthetic-data results as findings.** If the user starts treating synthetic numbers as answers, stop and re-anchor to the doctrine.

**If the user tries to paste raw microdata** (rows, records, an unsuppressed extract) into the conversation or a file: stop, do not ingest or persist it, and redirect to the sensitivity-gate decision — "We chose the privacy-preserving path specifically so this data never enters DAAF; let's put that back and I'll capture what we need through the profile summary instead." If sensitivity was misjudged and the user now has confirmed protections, that is a *re-decision at the sensitivity gate* (potentially switching to the normal path), not an ad hoc paste.

---

## STATE.md Update Points (Synthetic Path)

All synthetic-path state lives in the **Synthetic Path Tracking** section of STATE.md (from `STATE_TEMPLATE_ONBOARDING.md`). Update it at these points:

| Event | Synthetic Path Tracking updates |
|-------|--------------------------------|
| Sensitivity gate outcome 3 recorded | Gate outcome; reason (unsure / unprotected); Current Position = synthetic path |
| PSU-DS1 confirmed (GDS-0) | Chosen tier; suppression threshold; relationship spec; Key Decisions Made |
| DS-1 complete (GDS-1) | Customized script path; QAS-A result; Files Created |
| DS-2 handoff issued | DS-2 = awaiting user local run; expected report path; restart prompt (wait state) |
| DS-2 report returned (GDS-2) | Report path confirmed present; DS-2 = complete |
| DS-3 complete (GDS-3) | QAS-B result (b1–b12); any disclosure event (b5 or b12) escalated |
| DS-4 complete + PSU-DS2 (GDS-4) | Interpretation Tracking section (a separate top-level STATE section) — User Decision + Final Interpretation, all rows; Pre-Authoring Research choice |
| DS-5 complete (GDS-5) | Synthetic parquet path; recorded seed; QAS-C result; provenance tier value |
| Any QAS BLOCKER | QA Blockers table; Error Budget Consumed; revision status |
| Context ELEVATED+ | Context Snapshot + restart prompt (DS-2 and post-PSU-DS2 are natural restart boundaries) |
| Rejoin DI-7 | Current Position = DI-7; pass provenance overrides to authoring |

**Natural restart boundaries:** DS-2 (waiting on the user's local run) and post-PSU-DS2 (interpretations confirmed, before generation). If utilization is ELEVATED or higher at either, finalize STATE.md and recommend resuming in a fresh session.

---

## Verification Checklists

#### DS-1 (Script Preparation)
- [ ] Shipped asset **copied** (not edited/executed in place) to `scripts/local_profiling/`
- [ ] Only the Config block customized; suppression logic left structural
- [ ] Zero-DAAF-dependency, self-contained, IAT + REVIEW-BEFORE-SHARING block intact
- [ ] Script NOT executed in-container
- [ ] QAS-A disclosure-safety PASSED (a1–a10, edge cases traced) — no forbidden emission reachable

#### DS-2 (User Local Run)
- [ ] Plain-language handoff issued (get script out, run one command locally, two outputs, review `.txt`, return only JSON)
- [ ] Disclosure-review instruction explicit (categorical levels, named relationships, suppression section, tier match)
- [ ] Wait state recorded in STATE.md with restart prompt
- [ ] Returned JSON present and non-empty in `data/profile_report/`

#### DS-3 (Report Intake & Validation)
- [ ] DS-3 script re-computes b1–b12 independently (not echoing embedded all_passed)
- [ ] QAS-B PASSED/WARNING; any b5 sub-threshold cell or b12 lone suppressed cross-tab cell escalated as a disclosure event
- [ ] Report confirmed trustworthy before any generation

#### DS-4 (Interpretation)
- [ ] All interpretations marked `[PRELIMINARY]` with report-based basis
- [ ] Tier-driven confidence limits stated per interpretation
- [ ] Domain decomposition + exclusion observations produced
- [ ] PSU-DS2 presented; every Interpretation Tracking row has a Final Interpretation
- [ ] Pre-Authoring Research Offer presented (skippable)

#### DS-5 (Generation & Validation)
- [ ] Generation seeded; seed recorded in the log
- [ ] Synthetic parquet written to `data/synthetic/` (not `data/raw/`)
- [ ] Categoricals drawn only from emitted levels; `__OTHER__` preserved; identifiers value-free
- [ ] QAS-C PASSED/WARNING (c1–c11); c1/c2/c7/c8 clear, and c10 clear unless the researcher-authorized T4 missing-seed exception applies
- [ ] (T4) user-supplied synthetic imported + validated against report or declared metadata; if it arrived as CSV, converted to Parquet with an exchange manifest recorded as the first in-container action
- [ ] (T4) missing seed handled per policy — BLOCKER by default, or the researcher-authorized "non-reproducible T4 synthetic artifact" exception recorded in provenance + Synthetic Data Notice

#### Rejoin (DI-7/DI-8)
- [ ] `data-provenance` frontmatter set to the tier value (not `real`)
- [ ] "Synthetic Data Notice" section present with scaffold-not-substitute doctrine
- [ ] Provenance scripts bundled (local profiler + intake validator + generation script)
- [ ] Every data mention carries the scaffold caveat
- [ ] Delivery message surfaces provenance + finalize-against-real-data requirement
