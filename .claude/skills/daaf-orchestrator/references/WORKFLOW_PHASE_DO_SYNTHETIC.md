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
| QA (QAP1–4) **recomputes statistics against the source file** | QA is **inverted** — it cannot touch raw data. Three review checkpoints instead — **QAS-A** (disclosure-safety of the outbound script), **QAS-B** (internal consistency of the returned report), **QAS-C** (synthetic-vs-profile fidelity) — defined in `agent_reference/QA_CHECKPOINTS.md` § Synthetic-Path QA Checkpoints, each of the last two preceded by a script-halting validator (**CPS-INTAKE**, **CPS-GEN**) in `agent_reference/VALIDATION_CHECKPOINTS.md` § Synthetic-Path Validation Checkpoints |
| Interpretation (DI-6) reads real column values | Interpretation (DS-4) reads the **report** — column names, dtypes, tier-permitted marginals, relationships — not values (at Level 4 with no report, the synthetic rows plus the user's description, § T4 Variant) |
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
- Create `data/profile_report/` (holds the returned JSON report; at Level 4, also the user's synthetic data file and generation log as they arrive), `data/synthetic/` (holds the generated or imported seeded parquet — never `data/raw/`), and `output/preliminary_notes/`.
- Initialize STATE.md from `agent_reference/STATE_TEMPLATE_ONBOARDING.md` and populate the **Synthetic Path Tracking** section (sensitivity-gate outcome, disclosure tier, suppression threshold, relationship spec, the handed-off script, wait-state status, report path, generation seed, and the T4 fields) and its **Synthetic QA Status** table. All synthetic-path progress is tracked there throughout this workflow, with Current Position naming the DS stage.

---

## Wave / Gate Discipline (Async Dispatch)

See `SKILL.md` § Subagent Coordination > Wave Barrier Discipline (Async Dispatch) for how results arrive. However they arrive, every "wait for the agent to return" instruction below is a **hard barrier**: do not evaluate QA severity, update STATE.md conclusions, advance to the next DS stage, or present a user gate until the dispatched subagent has actually returned. Where a stage dispatches an agent and then its reviewer, treat them sequentially — the reviewer is dispatched only after the producing agent has returned and its output has been persisted.

Each DS stage is an atomic unit: producer → reviewer → evaluate severity → (revise if BLOCKER) → update STATE.md → proceed. This mirrors the standard Per-Part Execution Cycle (`data-onboarding-mode.md` § Per-Part Execution Cycle); the difference is only in which agents act and what they review.

---

## Gate Definitions (Synthetic Path)

These gates replace GDI-2 through GDI-6 for the synthetic path. GDI-7 and GDI-8 (skill authoring and delivery) still apply after rejoin.

| Gate | After Stage | Criteria | STOP If |
|------|-------------|----------|---------|
| GDS-0 | PSU-DS1 | Tier confirmed by user; suppression threshold set; relationship spec (T3) collected if wanted; the user's local language (R or Python) known; setup summary confirmed | User declines to choose a tier or wants to reconsider the sensitivity decision |
| GDS-1 | DS-1 | Customized profiling script prepared; **`QAS-A RESULT: PASSED`** with a count line showing `0 blockers, 0 not verified, 0 skipped` (no forbidden emission reachable at the chosen tier, and every a-check actually ran) | `blockers > 0` **or** `not_verified > 0` **or** zero substantive checks ran — each reads `QAS-A RESULT: BLOCKER` (a leak is irreversible once the report is shared, and an untraced path is an unproven-safe one) |
| GDS-2 | DS-2 | User confirms they ran the script, reviewed the `.txt` summary, and returned the JSON report; report file present in `data/profile_report/`. **T4:** the synthetic data file and its generation log present in `data/profile_report/` (plus the companion JSON report, only if a companion profiler run was approved) | User cannot run the script, or the run failed, or the user is not comfortable sharing the report (T4: the synthetic rows or the log) after review |
| GDS-3 | DS-3 | Report loads; `report_version` is `2.0` (a legacy `1.0` report is kept unchanged and a local rerun requested, § DS-3); **`CPS-INTAKE VALIDATION: PASSED` or `PASSED WITH WARNINGS`** (a `FAILED` raises in the script) **and `QAS-B RESULT: PASSED` or `WARNING`**, both count lines recorded — or, **only when tier = 4 and no profile report crossed**, both rows recorded as `EXEMPT (T4, no profile report)` with their reason (§ T4 Variant) | CPS-INTAKE reports `failed > 0` or `not_verified > 0` (either forces `FAILED`), or QAS-B reports `blockers > 0` (any BLOCKER If condition in `QA_CHECKPOINTS.md` § QAS-B, with § QAS Severity Overrides) — a corrupt or untrustworthy report, or one of the **disclosure events** listed below this table, which also require telling the user and requesting a corrected local re-run; or an `EXEMPT` CPS-INTAKE or QAS-B row at tier 1–3 or with a profile report present |
| GDS-4 | DS-4 | Interpretation complete, all `[PRELIMINARY]`; **PSU-DS2 findings confirmed by user** | User rejects the interpretation basis and no revised interpretation can be agreed |
| GDS-5 | DS-5 | Synthetic parquet in `data/synthetic/`; seed recorded (at T4 only, the researcher-authorized missing-seed exception may stand in for it — recorded in STATE.md and passed to CPS-GEN as `seed_exception`, § T4 Variant); **`CPS-GEN VALIDATION: PASSED` or `PASSED WITH WARNINGS`** — or, **only when tier = 4 and no profile report crossed**, the CPS-GEN row recorded as `EXEMPT (T4, no profile report)` with its reason — **and `QAS-C RESULT: PASSED` or `WARNING`**, the count lines recorded | CPS-GEN reports `failed > 0` or `not_verified > 0`, or QAS-C reports `blockers > 0` — a generation bug or disclosure-adjacent failure (QAS-C keys: `row_count_matched`, `column_set_and_types`, `other_bucket_preserved`, `no_fabricated_categories`, `identifier_scaffolds_typed_value_free`), or a missing seed (`seed_recorded` — a BLOCKER by default; the narrow, researcher-authorized T4 exception in § T4 Variant clears only as CPS-GEN's `[WARNING] seed_recorded` line, verdict `PASSED WITH WARNINGS`); or an `EXEMPT` CPS-GEN row at tier 1–3 or with a profile report present (a report present means CPS-GEN runs) |

**Disclosure events (GDS-3).** Each of these fails CPS-INTAKE and is a QAS-B `BLOCKER`, and it also means the report the user shared released something it should not have. Tell the user, and ask for a corrected local re-run of the unmodified profiler at the approved settings; never raise the approved tier or lower the approved threshold to match the report.
- A visible count below the threshold, or a categorical block that does not reconcile: its `n` differs from its column's `nonmissing_n`, it releases levels although `n` is below the threshold, or its level counts (`__OTHER__` included) do not sum to `n` (QAS-B `no_subthreshold_cells`; CPS-INTAKE `no_released_count_below_threshold`).
- A cross-tab entry whose visible cells sum past its `n`, or short of it with no hidden cell (QAS-B `crosstab_schema_wellformed`; CPS-INTAKE `crosstab_schema_and_suppression`).
- A hidden cross-tab cell recoverable from the released row and column totals (a lone hidden cell or any other bridge); a small missing-partner count (records with a level whose partner value is missing) made recoverable by the released cells; or a cross-tab entry that pairs a column with itself, repeats a pair, or whose dimensions differ from its columns' released level counts (QAS-B `no_lone_suppressed_cell`; CPS-INTAKE `crosstab_schema_and_suppression`).
- A value summary released below its required support, including an available named regression whose complement group is non-empty and below the threshold (QAS-B `column_blocks_match_role_and_support`; CPS-INTAKE's support gate in `no_released_count_below_threshold`).
- A report beyond the approved settings: a declared suppression threshold below the one approved at PSU-DS1, a `settings.tier` above the approved tier, or a `relationships` block released below tier 3 (QAS-B `suppression_settings_recorded`; CPS-INTAKE `no_released_count_below_threshold`).

**Severity mapping** for QAS-A/B/C is canonical in `agent_reference/QA_CHECKPOINTS.md` § Synthetic-Path QA Checkpoints (QAS-A, QAS-B, QAS-C) — each check's BLOCKER condition sits in its own table row — with the path-specific escalations in § QAS Severity Overrides (Synthetic Path). The script-halting counterparts CPS-INTAKE and CPS-GEN are in `agent_reference/VALIDATION_CHECKPOINTS.md` § Synthetic-Path Validation Checkpoints. Follow those verbatim; `synthetic-data-workflow` `references/validation-checks.md` carries only the skill-local detail (forbidden emissions per tier, tolerances, maintainer regression check).

In short: any disclosure-safety uncertainty (QAS-A) is a BLOCKER — `WARNING` is not a legal QAS-A verdict, and any `[NOT VERIFIED]` in a1–a11 is itself a BLOCKER. Any sub-threshold cell in a returned report — a categorical/`__OTHER__` cell (QAS-B `no_subthreshold_cells`) or a suppressed cross-tab cell recoverable from the released row and column totals, whether lone in its row or column or any other bridge (QAS-B `no_lone_suppressed_cell`) — is a BLOCKER, never a WARNING, as is a `[NOT VERIFIED]` on those keys or on `crosstab_schema_wellformed` / QAS-C `other_bucket_preserved`, `no_fabricated_categories`, `identifier_scaffolds_typed_value_free`. None of those keys may ever be declared `not_applicable`; a declaration is itself the finding. A missing generation seed (QAS-C `seed_recorded`) is a BLOCKER **by default**, with a single narrow carve-out layered on top of that default: the researcher-authorized T4 missing-seed exception defined in § T4 Variant. That exception reaches CPS-GEN through its `seed_exception` config key and surfaces as a `[WARNING] seed_recorded` line (verdict `PASSED WITH WARNINGS`), so it is counted and visible rather than silently passed; `seed_exception` at tier 1–3, or set alongside `seed`, is a `[FAIL]`. At T4 with no profile report, CPS-INTAKE, QAS-B and CPS-GEN are not run and their STATE rows record `EXEMPT (T4, no profile report)` — the only non-verdict value those rows may carry, and legal nowhere else.

**Read the count line, not only the verdict word.** Every synthetic-path checkpoint prints `Checks: …` immediately before its verdict. A CPS verdict of `FAILED` raises in the script, so the stage cannot complete; `PASSED WITH WARNINGS` clears its gate but the warnings travel into STATE.md and into what the user sees. A QAS-B/QAS-C `WARNING` clears the gate the same way; a QAS-A anything-but-`PASSED` does not.

---

## PSU-DS1: Tier Selection & Setup Confirmation

Present after DI-2 setup completes and before dispatching DS-1. This is the synthetic-path analog of PSU-DI1, and with it this path's Scope Check (`SKILL.md` § Scope Check; `data-onboarding-mode.md` § Scope Check), and it additionally asks the user to choose a disclosure tier — the single most consequential design decision on this path. Its "What I read" and "What changed" lines report the documentation-only scoping read (`data-onboarding-mode.md` § PSU Templates > Scoping Read Before PSU-DI1); the data itself is never read on this path. **Plain language only** — no internal terms (tier-forbidden-emissions, QAS, DS-N).

Before presenting, read `synthetic-data-workflow` `references/disclosure-tiers.md` so the tier explanations are accurate. Frame the choice around the **lowest tier that still lets the code development proceed** (remove only as much protection as the task forces you to give up).

**Tell the user about the known T3 limitation before they approve Level 3.** At T3 the profiler releases Cramér's V for every supported pair of categorical columns. V is computed on the full table (unpooled, unsuppressed) and rounded to 6 decimals. Combined with the released category counts, it can let a determined analyst reconstruct small cross-tab cells, including for pairs that have no released cross-tab. Because V sees the unpooled table, it can also undo the `__OTHER__` pooling: the counts of the rare levels pooled into `__OTHER__`, and how those records spread across the partner column, can be recovered (the pooled levels' labels stay unknown). Cross-tab suppression protects hidden cells against recovery from one cross-tab together with the released row and column totals, but not against this channel, and no validator flags it. This is an accepted residual risk (`disclosure-tiers.md` § T3), not a defect. The same section documents a second accepted limitation, the **linked-release residuals**: every cross-tab and regression protection holds for one release at a time, and repeated pairs are refused by column name only, so several cross-tabs or regressions that share a column, or two encodings of one variable paired with the same partner, can together reveal a small count or the mean of a few records. No validator flags these either. The Level 3 bullet in the template below states both limitations in plain language. Do not drop either part when Level 3 is on the table. When the user picks Level 3, record in Key Decisions Made that they were told.

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

**What I read:** [each document you pointed to, one line on what in it shapes the setup] (or "Nothing beyond your answers to my setup questions")
**What changed from your original request:** [differences the documentation introduced, or "Nothing — your request and the documentation agree"]

**Project folder:** [absolute path to research project]
**Source name:** [source-name]   **Target skill:** [skill-name]

**How much detail should the summary capture?** More detail makes the synthetic
data more realistic but shares more about your data's shape. Raw records stay local,
but summary statistics can still reveal sensitive information. Support and small-cell
checks reduce disclosure; they do not guarantee anonymity. Your release review matters.

- **Level 1 — Structure only:** just column names, types, and the row count. Safest;
  the synthetic data will have the right shape but random values.
- **Level 2 — Structure + per-column summaries (default):** adds, for each column, how
  often it is blank and how many distinct values it has. Number columns add percentiles
  plus the average and spread (never the smallest or largest value). Category columns
  add their categories with counts, small groups hidden. Text columns add their lengths
  and whether values look like emails, phone numbers, dates or IDs (never the text
  itself). Good realism for most code development.
- **Level 3 — Level 2 + relationships:** adds how columns move together: correlations
  between number columns, how strongly category columns go together, count tables for
  category pairs you name (small counts hidden), and simple straight-line fits (slope,
  intercept and fit) for number pairs you name. Choose this if your analysis code
  depends on relationships between variables. *One known limitation:* for each pair of category
  columns with enough records, Level 3 shares an association score computed from the
  full, unhidden counts.
  Someone determined could combine those scores with the category counts to work out
  small groups that the hiding step would otherwise conceal, even for pairs where no
  table is shared. They could also split the "other" group back apart: how many
  records each rare category has and how they spread across the other column (though
  not the rare categories' names). If small groups across combinations of categories
  are sensitive, Level 2 avoids this.
  *A second known limitation:* the hiding protects each shared table or relationship
  on its own, not several of them read side by side. If one column appears in many of
  the relationships you ask for, comparing those summaries can reveal a small group
  (for example, the few records with a given category whose other value is blank) or
  the average of a few records' values. The same happens if the data holds one thing
  twice under two names (say, a code and its label) and both are paired with the same
  column. No automatic check catches this. To keep it small, ask for as few
  relationships per column as you need, and never include the same variable twice;
  if you need many overlapping relationships, Level 2 avoids this too.
- **Level 4 — You synthesize locally:** if you need very high fidelity, you run a
  synthesizer on your machine and send back only the fake rows it makes and its short
  log (the random seed, the package version, row and column counts, at most one
  overall quality score, and in the Python version one setting) — never the real data or
  the fitted model. More setup on your
  end; I'll provide the script. You can also run the summary script (at Level 1, 2 or
  3) alongside it, which lets me check the fake rows more thoroughly.

  *Are there specific relationships you need preserved — say, a key outcome and a key
  predictor? Level 3 captures supported relationships as summaries, never raw rows.
  Those summaries still need your release review. If your code doesn't lean on
  cross-variable relationships, Level 2 is usually plenty.*

**Minimum support and small-group hiding:** by default, a summary is shared only when
at least **5 records** with a value feed it, and small category groups are hidden or
pooled. Four records with the same value are hidden; 5,000 records with the same value
can share it. A rare blank or a rare yes does not by itself hide a column's overall
rate or average. These are counts of records, not people, so let's confirm what one
record represents. I can raise the threshold if you'd like more caution; you still
review the report for sensitive information before sharing.

**My recommendation:** [seed from intake — e.g., "Level 2, since your described
analysis is column-level distributions" OR "Level 3, since you mentioned needing the
outcome~exposure relationship"].

**Which level would you like, and is the small-group threshold of 5 okay?** And which
does the machine where your data lives have, R or Python? I'll write the script in
that language.
```

Record the confirmed tier, suppression threshold, and any named relationship spec in STATE.md's **Synthetic Path Tracking** section (Key Decisions Made as well), and the user's local language (R or Python) in Key Decisions Made: it decides which asset DS-1 copies. Gate GDS-0.

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
- Chosen tier: {1 | 2 | 3 | 4} (4 = the Level 4 synthesizer, per the [T4] lines below; a
  Level 4 companion profiler follows the profiler lines with its own tier, 1–3)
- Suppression threshold: {default 5, or user value}
- Relationship spec (T3 only): {named outcome~predictor pairs / cross-tab pairs, or none}
  — each unordered pair at most once and never a column paired with itself; the profiler
  refuses a self-pair or a repeated pair before writing anything (a reversed pair of two
  numeric columns is allowed: it is a second regression and releases no cells). Every
  named regression, a reversed one included, is released only when each group of records
  having one of its two values but not the other is empty or at least the threshold; otherwise
  the profiler marks it unavailable (`small_complement_group`), so expect that outcome
  for a pair with a few one-sided missing values. These protections hold for one pair at
  a time, and the refusal compares column names only. Keep the spec small: list each
  column in as few pairs as the work needs (several cross-tabs or regressions sharing a
  column can together reveal a small count or a few records' mean), and never list two
  encodings of one variable (a code column and its label column) with the same partner.
  If the user's needs would put one column in many pairs, raise it with the orchestrator
  (Level 2 may suit better) rather than configuring it silently
- Local profiler language: {R | Python} — the language of the user's own machine, recorded
  at PSU-DS1 (not the project's execution language); {ext} = `R` or `py` to match
- Source name / dataset slug: {source_name} / {dataset_slug}
- Expected file format on the user's machine: {CSV / parquet / Stata / ...}
- Max categorical levels before high-cardinality treatment: {default 50}

**INSTRUCTIONS:**
1. Copy `{BASE_DIR}/.claude/skills/synthetic-data-workflow/assets/profile_data_template.{ext}`
   to `{PROJECT_DIR}/scripts/local_profiling/profile_{dataset_slug}.{ext}`. Copy — never
   move or edit the shipped asset.
   [T4: copy `{BASE_DIR}/.claude/skills/synthetic-data-workflow/assets/synthesize_local_template.{ext}`
   to `{PROJECT_DIR}/scripts/local_profiling/synthesize_{dataset_slug}.{ext}` instead, and in
   step 2 touch only its `# --- Config (EDIT THESE) ---` block: the INPUT_PATH placeholder
   (the user sets their own path). Leave SEED, N_SYNTHETIC, OUTPUT_SYNTHETIC_PATH,
   OUTPUT_LOG_PATH and, in Python, ENFORCE_MIN_MAX (`False`) as shipped unless the user
   chose otherwise; see `references/local-synthesis-t4.md`.]
2. Fill ONLY the `# --- Config (EDIT THESE) ---` block: INPUT_PATH placeholder (the
   user sets their own path), DATASET_NAME (set to `{dataset_slug}`, which the output file
   names and the DS-2 handoff use), OUTPUT_DIR, TIER, SUPPRESSION_THRESHOLD,
   RELATIONSHIP_SPEC (T3 only), MAX_CATEGORICAL_LEVELS. Leave the profiling body's
   suppression logic exactly as shipped — suppression is structural, not a flag. The
   template has no `not_applicable` setting and you must not add one: the profiler marks
   inapplicable checks itself with fixed reasons, and a typed reason would carry free text
   across the boundary (CPS-INTAKE fails it).
3. Preserve every IAT comment and the loud REVIEW-BEFORE-SHARING closing block.
4. Confirm the script is zero-DAAF-dependency (no DAAF paths, no network, no sourcing)
   and self-contained per `profiling-script-spec.md` § Design constraints for the outbound script.
5. Do NOT run the script. Return its path and a plain-language "how to run it"
   summary the orchestrator can relay to the user.

**OUTPUT FORMAT:** research-executor standard return. Emphasize: customized script
path; the exact Config values set; the two output files it will produce
({dataset}_profile_report.json + .txt; T4: the OUTPUT_SYNTHETIC_PATH and OUTPUT_LOG_PATH
names, `synthetic_output.parquet` and `synthesis_log.txt` unless changed, and the `.csv`
name the synthetic file takes when arrow/pyarrow is missing); confirmation it is safe to
hand to a non-programmer; any tier/spec ambiguity for the orchestrator to resolve.""",
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
**LOAD SKILL:** Invoke `synthetic-data-workflow`. Read `references/disclosure-tiers.md`
§ forbidden-emissions and `references/validation-checks.md` (skill-local tier detail).
**CANONICAL CHECKLIST:** `agent_reference/QA_CHECKPOINTS.md` § Synthetic-Path QA Checkpoints
(QAS-A, QAS-B, QAS-C) > QAS-A, plus § QAS Severity Overrides (Synthetic Path). Use those
stable check keys verbatim; do not re-derive the checklist from memory.

**SCRIPT TO REVIEW:** {PROJECT_DIR}/scripts/local_profiling/profile_{dataset_slug}.{ext}
(T4: {PROJECT_DIR}/scripts/local_profiling/synthesize_{dataset_slug}.{ext}, reviewed for the
same disclosure discipline plus a11 and `references/local-synthesis-t4.md`)
**Chosen tier:** {1 | 2 | 3 | 4}   **Suppression threshold:** {n}

**TASK:** Trace EVERY emission path for whether the configured script can emit anything
the chosen tier forbids. Work the FULL checklist a1–a11 from QA_CHECKPOINTS.md § QAS-A. Pay
special attention to a6 (edge cases — the all-null column, the single-distinct-value
column, the two-level column with one small cell, the identifier that slips the
uniqueness heuristic) and its companion edge-case checks: a8 (a residual `__OTHER__` below
threshold must roll in the smallest retained levels — a bare `__OTHER__ = sum(binned)` with
no roll-in is a leak), a9 (2.0 support gates: below-threshold numerics/string summaries
withheld; eligible constants shared; eligible reduced numerics quartiles-only;
all-missing numerics carry no values; actual paired support and nonzero pair variance
required for correlations), and a10 (T3 cross-tab suppression: bridge-free and
`null`-coded, on the released categories, covering missing-partner counts, with the
named-regression complement-group gate and the self-pair / repeated-pair refusal — work
every BLOCKER condition in the a10 row of QA_CHECKPOINTS.md § QAS-A. Its two
reviewer-awareness notes, the full-table Cramér's V the researcher was told about at
PSU-DS1 and the linked-release residuals, are not findings; per its spec review note, raise
obviously overlapping pairs or two apparent encodings of one variable in
`RELATIONSHIP_SPEC` in your notes to the researcher, outside the per-check lines, naming
pair positions), and a11 (`t4_log_aggregate_only`
— the T4 shareable synthesis log carries no per-variable utility or comparison output, only an
aggregate statistic; at T1–T3 the check still runs and reports the zero). Also inspect the
typed rounded/suppressed candidate validation, complete required check set and explicit
NOT_APPLICABLE reasons in the profiler's own fixed forms only (no researcher `not_applicable`
setting, and no other path that writes free text into `validation.checks[].reason`), no
output on validation failure, refusal to overwrite reports,
and success only after both output writes finish. The common leak is the edge case, not the main path. Trace the
smallest-cell case for every categorical/cross-tab emission. You may write a probe that
feeds SYNTHETIC toy input to the script to exercise these edge cases (never real data —
you do not have it), but the review is primarily static.

**SEVERITY:** Any item that is not clearly safe is a FAILURE. A possible leak is a
**BLOCKER**, never a WARNING — `WARNING` is not a legal QAS-A verdict at all, and any
`[NOT VERIFIED]` item is itself a BLOCKER (an emission path you could not trace is an
unproven-safe path). QAS-A carries **no `not_applicable` mapping**: every a-check runs on
every review, and a vacuous check emits an evidence-bearing `[PASS]` stating the zero
(e.g. `[PASS] crosstab_complementary_suppression: 0 cross-tab emission paths reachable at
tier 2`). A `[PASS]` on a disclosure check carries counts and the threshold only — never a
cell value, a minimum, or a level label with its count. Do not pass the gate on
"probably fine."

**OUTPUT FORMAT (3500-word cap):**
### QAS-A: Disclosure-Safety Review
**Per-check lines:** one `[PASS]` / `[BLOCKER]` / `[NOT VERIFIED]` line per a-check
(a1–a11), keyed by its stable key, with evidence; no checkpoint identifier on a
per-check line
**Edge cases traced:** [which, and the emission each produces]
**Issues Found:** [BLOCKER list with exact code path + fix]
```
Checks: {passed} passed, {warnings} warnings, {blockers} blockers, {not_verified} not verified, {skipped} skipped, {info} info
QAS-A RESULT: PASSED | BLOCKER
```
(BLOCKER if `blockers > 0` **or** `not_verified > 0`; a run with zero substantive checks
is BLOCKER, not PASSED; `skipped` must be 0.)
**Recommendation:** [PROCEED (safe to hand to user) | REVISION_REQUIRED]""",
    subagent_type: "code-reviewer"
})
```

**Revision flow (if QAS-A BLOCKER):** re-invoke research-executor to produce a versioned fix (`profile_{dataset_slug}_a.{ext}`), re-invoke QAS-A. Max 2 self-revisions before escalating to the user. **Never hand the user a script that has not passed QAS-A.** Update STATE.md: Synthetic Path Tracking > Profiling Script Version Handed Off (the passing script's path and its tier config), and the QAS-A row of Synthetic QA Status (verdict and count line). Then proceed to DS-2. Gate GDS-1.

---

## DS-2: User Local Run (Human Step — Outside the Container)

This stage runs entirely on the user's machine; DAAF does nothing but wait. Present the handoff instructions in plain language, then enter a **wait state**. At Level 4 use the T4 handoff below instead of (or, when a companion profiler run was approved, together with) the profiler handoff.

Fill the placeholders for the user's local language, recorded at PSU-DS1:

| Placeholder | R | Python |
|-------------|---|--------|
| `{script_file}` | `profile_{dataset_slug}.R` (T4: `synthesize_{dataset_slug}.R`) | `profile_{dataset_slug}.py` (T4: `synthesize_{dataset_slug}.py`) |
| `{run_command}` | `Rscript {script_file}` | `python {script_file}`, never with `-O`, `-OO` or `PYTHONOPTIMIZE` (both Python scripts refuse optimized mode) |
| `{requirements}` (profiler) | R. Base R reads CSV files; a Parquet file also needs the arrow package, and a Stata, SPSS or SAS file the haven package | Python with pandas and NumPy, plus pyarrow for a Parquet file. The script reads CSV and Parquet files |
| `{requirements}` (T4 synthesizer) | R with the synthpop package, plus arrow to write the fake rows as a Parquet file (arrow also reads a Parquet input). The script reads CSV and Parquet files | Python with the sdv package, plus pyarrow to write the fake rows as a Parquet file (pyarrow also reads a Parquet input). The script reads CSV and Parquet files |

### User-Facing Handoff (relay to the user)

```
**Your turn — run the profiling script on your own machine**

I've prepared a small, self-contained profiling script and had it checked by a separate
AI review step (not a human review) against the summary you approved: Level {N}, at
least {threshold} records behind every shared summary, and small category groups
hidden. These safeguards do not guarantee anonymity; you still need to decide whether
the report is appropriate to share.

**1. Get the script onto the machine where your data lives.**
   The script is `{script_file}` in your project's `scripts/local_profiling/` folder.
   In the browser code editor, right-click the file and choose **Download**. You can
   also download it from Docker Desktop's view of the DAAF volume. The Installation
   Guide's section "How to Manage DAAF Project Files and Output" shows both ways.

**2. Point it at your data and run it — on YOUR machine, not in DAAF.**
   You need {requirements}. The script uses no DAAF files and no network.
   Open the script and set two lines at the top: `INPUT_PATH` to your data file, and
   `OUTPUT_DIR` to an existing, empty folder on your machine. Leave everything else as
   it is. Then, in your own terminal, from the folder that holds the script, run it
   exactly as shown:
   `{run_command}`
   At Level 2 or 3, if a number column holds very large whole numbers (above about 9
   quadrillion, such as long numeric IDs), the script stops with a message instead of
   rounding them. Tell me if that happens, and don't change the data to get past it.

**3. It produces two files:**
   - `{dataset_slug}_profile_report.json` — the machine-readable summary I'll work from
   - `{dataset_slug}_profile_report.txt` — plain-language review guidance followed by
     the exact release candidate in JSON notation, for YOU to review

**4. Review the `.txt` before you share anything — this is the important step.**
   Read the whole `.txt`. Confirm:
   - No column *name* itself gives away something sensitive.
   - Every category label listed under `categorical.levels` is safe to share.
     `n_levels_binned` counts pooled source levels; `__OTHER__` is the pooled bucket,
     including any original level literally named `__OTHER__`.
   - Value/structure blocks with `withheld:true` explain omissions in `reason`.
     Cross-tab `null` cells are hidden, not zero; relationship `available:false`
     blocks explain their absence in `reason`. These fields are inside the exact
     candidate; there is no separate "What was suppressed" section.
   - If you chose Level 3, look at each named relationship you asked me to preserve and
     confirm you're comfortable sharing it.
   - The tier and threshold at the top match what you intended.
   - Every check says PASS, or NOT_APPLICABLE with a short reason the script wrote
     itself when a check does not apply to your data. You don't need to change anything
     except the two settings in step 2.
     If validation or either write failed, do not share any partial files — tell me.
   - Counts are records: confirm whether records are the intended contributors/individuals.
   - Use a fresh output folder for a rerun; existing reports are deliberately preserved.

**5. Send me back only the `.json` file** (the `.txt` is yours to keep). In the
   browser code editor, drag it from your computer onto the project's
   `data/profile_report/` folder in the file explorer.

Take your time. When the report is in `data/profile_report/`, tell me and we'll
continue. Nothing else from your data ever needs to leave your machine.
```

### User-Facing Handoff, Level 4 (relay to the user)

The T4 synthesizer writes two files into the folder it runs from, named in its Config block: `synthetic_output.parquet` (or `synthetic_output.csv` when arrow/pyarrow is missing) and `synthesis_log.txt`. If DS-1 changed those names, use the names from the DS-1 return.

```
**Your turn — run the synthesizer on your own machine**

I've prepared a small, self-contained script that makes fake rows from your data on
your own machine, and had it checked by a separate AI review step (not a human review)
to confirm it writes only the fake rows and a short log. Your real data and the fitted
model stay on your machine.

**1. Get the script onto the machine where your data lives.**
   The script is `{script_file}` in your project's `scripts/local_profiling/` folder.
   In the browser code editor, right-click the file and choose **Download**. You can
   also download it from Docker Desktop's view of the DAAF volume. The Installation
   Guide's section "How to Manage DAAF Project Files and Output" shows both ways.

**2. Point it at your data and run it — on YOUR machine, not in DAAF.**
   You need {requirements}. The script uses no DAAF files and no network.
   Put the script in a new, empty folder: it writes its two files next to itself.
   Open it and set `INPUT_PATH` at the top to your data file. Leave everything else as
   it is. Then, in your own terminal, from that folder, run it exactly as shown:
   `{run_command}`

**3. It writes two files:**
   - `synthetic_output.parquet` — the fake rows (`synthetic_output.csv` if the Parquet
     package isn't installed; that still works, and I convert it when it arrives)
   - `synthesis_log.txt` — a short log: the random seed, the package version, the row
     and column counts, and at most one overall quality score (the Python script also
     records whether it kept values inside the real data's minimum and maximum)

**4. Look over the log, then send me back exactly those two files.** Send the log
   unchanged: I record the random seed from it, which is what makes the fake data
   reproducible. Never send your real data, and never save or send the fitted model. In the
   browser code editor, drag both files from your computer onto the project's
   `data/profile_report/` folder in the file explorer.
   [Only if you also approved a companion summary run: also send the `.json` report
   from the profiling script, following its own steps.]

Take your time. When the files are in `data/profile_report/`, tell me and we'll
continue.
```

### Wait State

DS-2 is a natural **session-suspension boundary**. Update STATE.md:
- Synthetic Path Tracking > Wait-State Status = **Awaiting user local run (DS-2)** (the QAS-A row of Synthetic QA Status already records `PASSED`); Current Position = DS-2.
- Next Actions: "Resume at DS-3 once the user confirms the report is in `data/profile_report/`", naming the expected file, `data/profile_report/{dataset_slug}_profile_report.json`. **T4:** "Resume once the user confirms the synthetic data file and `synthesis_log.txt` are in `data/profile_report/`", naming both files, plus the companion JSON report only if a companion profiler run was approved.
- Write the User Restart Prompt so a fresh session can resume cleanly.

The session may end here and resume later. When the user returns and confirms the files are placed, verify each expected file exists and is non-empty (the JSON report; at T4, the synthetic data file and the log, plus any companion report), then proceed to DS-3 (at T4, see § T4 Variant for how the stages continue). Gate GDS-2.

---

## DS-3: Report Intake & Validation

**Purpose:** Confirm the returned report is internally coherent and trustworthy before anything is built from it. | **Producer:** research-executor (consistency-check script) | **Reviewer:** code-reviewer (QAS-B) | **Skill:** `synthetic-data-workflow`

The report is now in-container (`data/profile_report/`), so this stage computes only over its own released fields, never raw data. The embedded `validation.all_passed` is not independent verification. Accept only `report_version` 2.0. A 1.0 report is a legacy report: keep it unchanged, ask the user for a local rerun with the current profiler, and never relabel its PASS results as compliance. Independently check the complete required check set, applicability/reasons, supported column shapes, paired support, and actual rounded fields per `profiling-script-spec.md`. Intake can check consistency of reported support but cannot independently establish raw support or pair variances it never received.

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
**LOAD SKILL:** Invoke `synthetic-data-workflow`. Read `references/profiling-script-spec.md`
§ Canonical JSON report schema and `references/validation-checks.md` (skill-local tier detail).

**REPORT:** {PROJECT_DIR}/data/profile_report/{dataset_slug}_profile_report.json

**TASK:** Copy the **CPS-INTAKE block** verbatim from `agent_reference/VALIDATION_CHECKPOINTS.md`
§ Synthetic-Path Validation Checkpoints (Data Onboarding, synthetic path) >
`CPS-INTAKE: Profile Report Intake Validation (DS-3)` into the script's `# --- Validate ---`
section, then set the values below in the block's own `# --- Config ---` section (the only
lines you change). Do not assign them anywhere else in the script: the block re-binds every
config variable, so a value set outside it is overwritten. That block is the only
maintained copy — do not paraphrase it, do not re-derive the checks from memory, and do not
write a prose-improvised consistency script. It recomputes from the report's released fields;
the embedded `all_passed` is the user's claim, never the verification. Use the fence for the
project's execution language: {Python | R}.

Values for the block's Config section (its stanza and comments are in VALIDATION_CHECKPOINTS.md):
- `report_path`: `"{PROJECT_DIR}/data/profile_report/{dataset_slug}_profile_report.json"`
- `tier`: {1 | 2 | 3}, from STATE.md § Synthetic Path Tracking > Disclosure Tier (T4: > T4 Companion Profile Tier)
- `expected_threshold`: {n}, from STATE.md § Synthetic Path Tracking > Suppression Threshold
- `not_applicable`: empty unless a declarable check truly does not apply (e.g.
  `correlation_matrix_wellformed` at tier 2, reason "tier 2 — the report releases no correlations")

Take `tier` and `expected_threshold` from STATE.md, never from the
report: they are the settings the researcher approved, and CPS-INTAKE holds the report to
both. `tier` is the Disclosure Tier confirmed at PSU-DS1; at T4, where DS-3 validates the
companion profile report, it is the tier the researcher approved for that companion profiler
run (STATE.md § Synthetic Path Tracking > **T4 Companion Profile Tier**), never `4` —
CPS-INTAKE accepts only 1–3. A report whose `settings.tier` exceeds the configured `tier` is a
`[FAIL]` (owned by `no_released_count_below_threshold`, which carries both PSU-DS1 approvals):
the report releases blocks the researcher did not approve, which is a disclosure event. The
disclosure sweep reads the report's own `settings.suppression_threshold` as well. It emits
`[FAIL] no_released_count_below_threshold: report declares threshold d, below the approved threshold e`
when the report declares less than the approved value. Otherwise it gates every visible
count at the larger of the two. It emits `[NOT VERIFIED]` when either threshold is missing
or is not a positive whole number; for the config value that line reads
`expected_threshold not configured`. Never set `expected_threshold` to the report's value
to make the check pass. The non-declarable keys — `no_released_count_below_threshold`,
`no_raw_value_shaped_fields`, `identifier_columns_value_free`, `crosstab_schema_and_suppression`
— may never appear in `not_applicable`; a declaration is itself a `[FAIL]`. A `not_applicable`
key that does not name one of the block's own checks is likewise a `[FAIL]`, and a key
declared with an empty or whitespace-only reason is `[NOT VERIFIED]` for that check.

Accept only `report_version` 2.0. A 1.0 report is a legacy report: keep it unchanged, report
it so the orchestrator can ask for a local rerun with the current profiler, and never relabel
its PASS results as compliance.

Script path: `{PROJECT_DIR}/scripts/profile_report_intake/01_validate-report.{ext}` ({ext} =
`py` or `R`, the project's execution language)
Execute: bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/profile_report_intake/01_validate-report.{ext}
Flat sequential style; IAT comments; assert + print() (Python) or stopifnot() + cat() (R) validation.

**OUTPUT FORMAT:** research-executor standard return. Quote the checkpoint's own
`Checks: …` count line and its `CPS-INTAKE VALIDATION: PASSED | PASSED WITH WARNINGS | FAILED`
verdict verbatim, then the per-check lines for anything that was not `[PASS]` — naming the
specific column/block — and state explicitly, for each, whether it is one of the disclosure
events in the **Disclosure events (GDS-3)** list under the gate table in
`.claude/skills/daaf-orchestrator/references/WORKFLOW_PHASE_DO_SYNTHETIC.md` § Gate
Definitions (Synthetic Path) (read that list: they fall under
`no_released_count_below_threshold` and `crosstab_schema_and_suppression`). Each is
BOTH a validation failure AND a disclosure event to escalate: the orchestrator notifies the
user and requests a corrected local re-run. Also state whether
`identifier_columns_value_free` failed — at tier 1 (configured, or the report's
`settings.tier`) an identifier record carries only `name` and `dtype`, so any other key is a
`[FAIL]` naming the key. Report the block/column position only, never the offending cell
value.""",
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
(skill-local tier detail and § Tolerances).
**CANONICAL CHECKLIST:** `agent_reference/QA_CHECKPOINTS.md` § Synthetic-Path QA Checkpoints
(QAS-A, QAS-B, QAS-C) > QAS-B, plus § QAS Severity Overrides (Synthetic Path) and
§ QAS Count Line and Verdict. Use those stable check keys verbatim.

**SCRIPT TO REVIEW:** {PROJECT_DIR}/scripts/profile_report_intake/01_validate-report.{ext}
**REPORT:** {PROJECT_DIR}/data/profile_report/{dataset_slug}_profile_report.json

**TASK:** Verify the DS-3 script is the CPS-INTAKE block copied verbatim from
`agent_reference/VALIDATION_CHECKPOINTS.md` (not a paraphrase or a from-memory rewrite) and
that it genuinely recomputes from the report's own numbers rather than echoing the embedded
`all_passed`. Then work the full QAS-B checklist b1–b12 yourself, independently spot-checking
`percentiles_monotone`, `category_counts_le_rowcount`, `no_subthreshold_cells`,
`column_blocks_match_role_and_support`, `embedded_validation_complete`, and — at T3 — paired
support/availability plus `crosstab_schema_wellformed` and `no_lone_suppressed_cell`. Accept
only `report_version` 2.0; a 1.0 report is a legacy report, kept unchanged, for which the
user is asked to rerun the current profiler locally. Distinguish an embedded `NOT_APPLICABLE` (absent target, carrying one of the
profiler's fixed reasons — the profilers take no researcher declarations, so any other reason
means a modified template or a hand-edited report) from a `[PASS]`, and both from
`[NOT VERIFIED]`; raw support itself is not independently
observable. Create QA script(s) at `scripts/cr/qas_b_report-consistency.{ext}` ({ext} = the
project's execution language) and execute via run_with_capture.sh.

**SEVERITY** (QA_CHECKPOINTS.md § QAS-B and § QAS Severity Overrides): every BLOCKER If
condition in the b1–b12 rows is a BLOCKER; a corrupt report (`percentiles_monotone`,
`category_counts_le_rowcount`, `missing_rate_in_unit_interval`,
`correlation_matrix_wellformed`, `crosstab_schema_wellformed` malformations) must not be
generated from. The rows also mark which BLOCKERs are **also disclosure events** — findings
under `no_subthreshold_cells`, `crosstab_schema_wellformed` (a cell sum that does not
reconcile with `n`), `no_lone_suppressed_cell`, `column_blocks_match_role_and_support`
(a value summary below its required support) and `suppression_settings_recorded` (tier above
or threshold below the approved settings, or relationships released below tier 3). Label
each such finding a disclosure event, so the orchestrator tells the user and requests a
corrected local re-run. The reviewer-awareness notes in b12 and b9 (missing-partner counts
revealed by released `n` and missing counts alone, the count of records missing both values,
the full-table Cramér's V, and the linked-release residuals) are accepted residuals, not
findings.
At tier 1 an identifier record carries only `name` and `dtype`; confirm CPS-INTAKE's
`identifier_columns_value_free` line agrees. `correlation_psd_tolerant`
mild non-PSD = WARNING (project to nearest PD, note it). A `[NOT VERIFIED]` on
`no_subthreshold_cells`, `crosstab_schema_wellformed`, or `no_lone_suppressed_cell` is a
BLOCKER, and none of those three may be declared `not_applicable` — a declaration is itself
`[BLOCKER] <key>: declared not_applicable — …`, and the check still runs. A `[PASS]` on a
disclosure check carries counts and the threshold only, never a cell value or a level label
with its count.

**OUTPUT FORMAT (3500-word cap):**
### QAS-B: Report Consistency Review
**Per-check lines:** one `[PASS]` / `[WARNING]` / `[BLOCKER]` / `[NOT VERIFIED]` /
`[SKIPPED]` / `[INFO]` line per b-check, keyed by its stable key, with evidence; no
checkpoint identifier on a per-check line
**CPS-INTAKE verdict re-derived:** [the script's quoted count line and verdict, and whether
your recomputation agrees]
**Issues Found / Recommendation**
```
Checks: {passed} passed, {warnings} warnings, {blockers} blockers, {not_verified} not verified, {skipped} skipped, {info} info
QAS-B RESULT: PASSED | WARNING | BLOCKER
```
(BLOCKER if `blockers > 0`; else WARNING if `warnings > 0` or `not_verified > 0`; else
PASSED. A run with zero substantive checks is WARNING, never PASSED.)""",
    subagent_type: "code-reviewer"
})
```

Revision flow mirrors DS-1 (versioned script fixes, max 2, then escalate). Note: a BLOCKER here usually means the *report* is bad, not the DS-3 script — if the report is corrupt or contains a sub-threshold cell, the fix is to inform the user and (for a disclosure event) have them discard the shared report and re-run a corrected profiler, not to re-run the DS-3 script. Update STATE.md: Synthetic Path Tracking > Report Path and Wait-State Status (Past intake), and the CPS-INTAKE and QAS-B rows of Synthetic QA Status (verdict and count line). Gate GDS-3.

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
[T4, no profile report: replace the two sentences above. Your input is synthetic rows the
user's local synthesizer made, not a profile report and not real data: the Parquet in
SYNTHETIC ROWS below. Load it in a file-first script,
`{PROJECT_DIR}/scripts/profile_interpretation/10_semantic-interpretation.{ext}` ({ext} = the
project's execution language), executed with
`bash {BASE_DIR}/scripts/run_with_capture.sh <script>`, and read the column names, dtypes and
value patterns from it, with assert/print() (Python) or stopifnot()/cat() (R) validation.]
**LOAD SKILL:** Invoke `synthetic-data-workflow`. Read `references/profiling-script-spec.md`
§ Canonical JSON report schema so you read the report structure correctly.
[T4, no profile report: read `references/local-synthesis-t4.md` § Consuming T4 output on the
DAAF side instead of the report schema.]

**REPORT:** {PROJECT_DIR}/data/profile_report/{dataset_slug}_profile_report.json
[T4, no profile report: **SYNTHETIC ROWS:** {PROJECT_DIR}/data/synthetic/{imported_parquet},
the Parquet the DS-5 import script wrote, in place of REPORT. Never read the CSV or Parquet
in `data/profile_report/` directly.]
**Tier:** {N}   **Domain context:** {domain_context}   **Intended use:** {intended_use}
**Documentation (if the user provided any):** {doc_paths_or_none}

**TASK (adapt Part D semantic interpretation to the report):**
1. Column semantic classification from names + dtypes + tier-permitted stats:
   name-pattern matching (FIPS->geo, _id->identifier, _pct->percentage, _cd->categorical),
   value-pattern inference only from AVAILABLE percentiles/levels/constants (binary,
   year-like, percentage-like); withheld summaries are unobserved, not zero or constant.
   Branch on 2.0 numeric/string shapes before reading values; do not infer missing
   distributions from cardinality alone. Join-key candidates use identifier flags +
   uniqueness ratios, with record-vs-person and heuristic uncertainty stated.
2. Draft data dictionary — ALL entries marked [PRELIMINARY]. State the report-based
   BASIS for each (e.g., "9 suppressed-and-binned levels, uniqueness 0.001 → low-
   cardinality categorical").
3. Domain decomposition: group columns into analytical domains; note which warrant a
   dedicated reference file in the eventual skill.
4. Exclusion / population-boundary observations inferable from the report or docs.
5. Interpretation-confidence caveat: explicitly flag where the chosen tier LIMITED your
   confidence (e.g., "at Level 2 no cross-column relationships were shared, so join
   cardinality is inferred from uniqueness alone, not observed").
[T4, no profile report: steps 1–5 read the loaded synthetic rows in place of report fields,
and the report-shape branching in step 1 does not apply. Each BASIS names the synthetic
rows or the user's description. In step 5, state that the patterns are what the user's
synthesizer produced, not observed real values.]

**CONSTRAINT:** You must not ask for, and will not be given, the raw data or any raw
values. Interpret only what the report contains. If a column's meaning cannot be
inferred from the report, say so — do not guess beyond the report.
[T4, no profile report: interpret only what the synthetic rows and the user's description
show, and say so where they cannot settle a column's meaning.]

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
(R project) or `references/generation-patterns-python.md` (Python project), and
`references/validation-checks.md` § Tolerances.

**REPORT:** {PROJECT_DIR}/data/profile_report/{dataset_slug}_profile_report.json
**Tier:** {N}   **Seed:** {choose and RECORD a fixed integer seed}
**Execution language:** {Python | R} — the project's execution language; {ext} = `py` or `R`

**TASK:** Write and execute a generation script, in the project's execution language, that
builds a synthetic dataset matching the report:
- **R: simstudy** — Gaussian copula via genCorGen/addCorGen from the reported
  marginals + correlation matrix; base-R copula fallback per generation-patterns-r.md if
  simstudy is unavailable. **Python:** NumPy/SciPy Gaussian copula per
  generation-patterns-python.md.
- Branch on every 2.0 numeric/string shape BEFORE percentile/moment/pattern use.
  Generate supported constants faithfully; withheld distributions get typed placeholders
  with explicit unobserved-fidelity status, not invented moments or a QA PASS. Reduced
  numerics use only their quartiles. All-missing numerics are typed nulls.
- Draw categoricals only from emitted levels; keep `__OTHER__` as an aggregate bucket.
  A column with an empty level list is filled with the literal `__OTHER__` when its
  `n_levels_binned > 0` (every source level was pooled), otherwise with null — never `""`
  and never fake hidden categories. Null is allowed but may cost a
  `missingness_within_tolerance` WARNING, since an all-null column no longer matches its
  reported missing rate.
- Use correlations/named relationships only when available and eligible; do not feed
  constant columns to a copula or replace unavailable correlations with zero targets.
- Preserve separately available missingness targets, including on withheld columns;
  inject missingness AFTER marginal/relationship generation. T1 has no such target.
- Identifier columns: synthetic structural scaffolds with declared dtypes and non-routable
  email domains; withheld structure gets a placeholder. Noncollision with unknown real
  values cannot be established from the report alone.
- Match row_count; seed the RNG and print the seed.
- Write to `{PROJECT_DIR}/data/synthetic/{date}_{dataset_slug}_synthetic.parquet`
  (`arrow::write_parquet` in R, `write_parquet` in Python). Print a generation log: seed,
  row/col counts, per-column method.

**VALIDATION — copy the CPS-GEN block, do not improvise one.** Copy the **CPS-GEN block**
verbatim from `agent_reference/VALIDATION_CHECKPOINTS.md` § Synthetic-Path Validation
Checkpoints (Data Onboarding, synthetic path) > `CPS-GEN: Synthetic Generation Validation
(DS-5)`, using the fence for the project's execution language. The block is embedded at the
**end of the generation script** (`scripts/synth_generate/01_generate-synthetic.{ext}`), after the
parquet has been written — it validates the file on disk, so it cannot run before the write.
Set the values below in the block's own `# --- Config ---` section (the only lines you
change). Do not assign them anywhere else in the script: the block re-binds every config
variable, so a value set outside it is overwritten.

Values for the block's Config section (its stanza and comments are in VALIDATION_CHECKPOINTS.md):
- `synthetic_path`: `"{PROJECT_DIR}/data/synthetic/{date}_{dataset_slug}_synthetic.parquet"`
- `report_path`: `"{PROJECT_DIR}/data/profile_report/{dataset_slug}_profile_report.json"`
- `seed`: the fixed integer seed the generator ran with
- `seed_exception`: leave `None` / `NULL` when generating here (T4 import only, § T4 Variant)
- `tier`: {1 | 2 | 3}, the tier the report was produced at (its `settings.tier`); `4` only for the T4 import
- the four `*_tolerance` scalars: the block's shipped defaults
- `not_applicable`: empty unless a declarable check truly does not apply (e.g.
  `correlations_within_tolerance` at tier 2, reason "tier 2 — no correlations released")

Keep the shipped tolerance
defaults unless the project has a stated reason to tighten them. `correlation_tolerance` is the
one band CPS-GEN applies to every released pair; the looser binary/low-cardinality band in
`validation-checks.md` § Tolerances is a QAS-C reviewer allowance, not a second CPS-GEN tolerance.
`seed_exception` exists only for the researcher-authorized T4 missing-seed exception and is
honored only at `tier` 4 — set at tier 1–3, or alongside `seed`, it is a `[FAIL]` (§ T4 Variant
gives the outcome lines). The non-declarable keys —
`suppressed_categories_absent`, `synthetic_levels_within_released_levels`,
`identifier_columns_value_free`, `seed_recorded` — may never appear in `not_applicable`;
a declaration is itself a `[FAIL]`. A `not_applicable` key that does not name one of the
block's own checks is likewise a `[FAIL]` (a typo'd key must not silently vanish), and a
key declared with an empty or whitespace-only reason is `[NOT VERIFIED]` for that check,
never a silent pass. That block is the only maintained copy: do not paraphrase
it and do not re-derive its checks from memory.

Script path: `{PROJECT_DIR}/scripts/synth_generate/01_generate-synthetic.{ext}`
Execute: bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/synth_generate/01_generate-synthetic.{ext}

**OUTPUT FORMAT:** research-executor standard return. Quote the checkpoint's own
`Checks: …` count line and its `CPS-GEN VALIDATION: PASSED | PASSED WITH WARNINGS | FAILED`
verdict verbatim. Emphasize: synthetic parquet path, recorded seed, generation method per
column, and any marginal/correlation the copula could not reproduce well (flag
binary/low-cardinality correlations — recovered less faithfully; CPS-GEN still warns on them
at the single `correlation_tolerance`, and QAS-C decides whether its reviewer allowance applies).""",
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
§ Tolerances and the skill-local generation detail.
**CANONICAL CHECKLIST:** `agent_reference/QA_CHECKPOINTS.md` § Synthetic-Path QA Checkpoints
(QAS-A, QAS-B, QAS-C) > QAS-C, plus § QAS Severity Overrides (Synthetic Path) and
§ QAS Count Line and Verdict. Use those stable check keys verbatim.

**SYNTHETIC:** {PROJECT_DIR}/data/synthetic/{date}_{dataset_slug}_synthetic.parquet
**REPORT:** {PROJECT_DIR}/data/profile_report/{dataset_slug}_profile_report.json
**GENERATION SCRIPT:** {PROJECT_DIR}/scripts/synth_generate/01_generate-synthetic.{ext}
(T4: the import script `scripts/synth_generate/01_import-synthetic.{ext}` — § T4 Variant)

**TASK:** First verify the DS-5 script's validation section is the CPS-GEN block copied
verbatim from `agent_reference/VALIDATION_CHECKPOINTS.md`, and re-derive its verdict from its
own count line. Then create and execute QA script(s) at `scripts/cr/qas_c_synthetic-validation.{ext}`
working the full QAS-C checklist c1–c11 independently: first inventory available targets by
2.0 shape. Withheld/all-missing
value distributions, unavailable relationships, and T1 fidelity targets are explicitly
NOT_APPLICABLE with reasons, never fabricated PASS. Check supported constants against
their shared value; reduced numerics against quartiles only; preserve eligible missingness
checks even on withheld columns. Structural/type/seed checks apply to placeholders too.
Then check row count; column set + types; available numeric/categorical targets within
tolerance; __OTHER__ preserved as a bucket;
(T3) correlations reproduced within tolerance (CPS-GEN applies one `correlation_tolerance`;
the looser binary/low-cardinality band is your reviewer allowance only);
synthetic categories confined to released levels — a column with an empty level list may
carry only the literal `__OTHER__` (when its `n_levels_binned > 0`) or null, and null may
cost a missingness WARNING; identifier
scaffolds explicitly synthetic, correctly typed, matching AVAILABLE structure and using
non-routable email domains. Withheld identifier structure is N/A independently of dtype;
unknown-real-value noncollision cannot be verified from this report. Missingness within
tolerance; **seed recorded in the generation log**; (T3) each named relationship
reproduced — the synthetic OLS slope of `outcome ~ predictor` within ±10% of the reported
slope and R² within ±0.10 (c11). Use the § Tolerances defaults.

**SEVERITY** (QA_CHECKPOINTS.md § QAS-C and § QAS Severity Overrides): every BLOCKER If
condition in the c1–c11 rows is a BLOCKER — `row_count_matched`, `column_set_and_types`,
`other_bucket_preserved` (the bucket replaced by invented values), `no_fabricated_categories`,
`identifier_scaffolds_typed_value_free` (generation bug or disclosure risk); `seed_recorded`
missing = BLOCKER **by default**. The one exception is the T4 missing-seed path (see § T4 Variant below): tier 4,
`seed` unset, `seed_exception` set in the CPS-GEN config, and the researcher's authorization
recorded in STATE.md § Synthetic Path Tracking > T4 Missing-Seed Exception — then it is a
WARNING, mirroring CPS-GEN's `[WARNING] seed_recorded` line. Confirm the authorization is
actually recorded; you never grant it yourself (only the orchestrator obtains it from the
researcher), and `seed_exception` at tier 1–3 or alongside `seed` is a BLOCKER;
`numeric_marginals_within_tolerance`,
`categorical_proportions_within_tolerance`, `correlations_within_tolerance`,
`missingness_within_tolerance`, `named_relationship_reproduced` out of tolerance = WARNING
(investigate — may be an acceptable approximation limit). A `[NOT VERIFIED]` on
`other_bucket_preserved`, `no_fabricated_categories`, or
`identifier_scaffolds_typed_value_free` is a BLOCKER, and none of those three may be
declared `not_applicable` — a declaration is itself `[BLOCKER] <key>: declared
not_applicable — …`, and the check still runs.

**OUTPUT FORMAT (3500-word cap):**
### QAS-C: Synthetic-vs-Profile Review
**Per-check lines:** one `[PASS]` / `[WARNING]` / `[BLOCKER]` / `[NOT VERIFIED]` /
`[SKIPPED]` / `[INFO]` line per c-check, keyed by its stable key, with evidence; no
checkpoint identifier on a per-check line
**CPS-GEN verdict re-derived:** [the script's quoted count line and verdict, and whether
your recomputation agrees]
**Issues Found / Recommendation**
```
Checks: {passed} passed, {warnings} warnings, {blockers} blockers, {not_verified} not verified, {skipped} skipped, {info} info
QAS-C RESULT: PASSED | WARNING | BLOCKER
```
(BLOCKER if `blockers > 0`; else WARNING if `warnings > 0` or `not_verified > 0`; else
PASSED. A run with zero substantive checks is WARNING, never PASSED.)
Note: passing means "structurally faithful to the profile," NEVER "analytically valid."""",
    subagent_type: "code-reviewer"
})
```

Revision flow mirrors the other stages. Update STATE.md: Synthetic Path Tracking > Generation Seed, the CPS-GEN and QAS-C rows of Synthetic QA Status (verdict and count line), and the synthetic parquet path under Files Created This Session. Gate GDS-5.

### T4 Variant — User Ran Local High-Fidelity Synthesis

If the user chose **Level 4** at PSU-DS1, DS-1/DS-2 hand the user a **synthesizer** template instead of (or alongside) the profiler:

- **DS-1 (T4):** research-executor copies `assets/synthesize_local_template.R` (synthpop CART, flagship) — or `.py` (SDV GaussianCopula), following the user's local language as on the profiler path — to `scripts/local_profiling/synthesize_{dataset_slug}.{R,py}`, customizes the Config, and QAS-A reviews it for the same disclosure discipline **plus** the T4-specific guarantee that only synthetic *rows* and an aggregate-only generation log (a11) — never the real data and never the fitted model artifacts — are emitted (see `synthetic-data-workflow` `references/local-synthesis-t4.md`).
- **DS-2 (T4):** relay § DS-2 > User-Facing Handoff, Level 4, then the wait state. The user runs the synthesizer locally and sends back the synthetic rows and the generation log (`synthesis_log.txt`), into `data/profile_report/`; only those two files cross the boundary, never the real data or the fitted model. **Parquet is the preferred exchange format**; CSV is a permitted fallback only when the user's local environment lacks Arrow/PyArrow — the **audited boundary exception** (see DS-5 below and `synthetic-data-workflow` `references/local-synthesis-t4.md`). Optionally a T2/T3 profile report crosses too, if they also ran the profiler, which enables a stronger QAS-C. That companion profiler run has its own approved tier (1–3, never 4), recorded in STATE.md § Synthetic Path Tracking > **T4 Companion Profile Tier** before DS-1 configures the companion script; DS-3 then runs CPS-INTAKE on the companion report with `tier` set to that value (CPS-INTAKE accepts only 1–3), and a companion report whose `settings.tier` exceeds it is a CPS-INTAKE `[FAIL]` and a disclosure event.
- **DS-3 and DS-4 (T4) without a profile report.** With no companion report, DS-3 has nothing to validate and is skipped: STATE.md § Synthetic QA Status records the CPS-INTAKE and QAS-B rows as **`EXEMPT (T4, no profile report)`** with the reason in place of a verdict and counts, the same form as the CPS-GEN row below; GDS-3 accepts `EXEMPT` on those two rows only when tier = 4 and no report crossed. Before DS-4, run the DS-5 import (next bullet): `scripts/synth_generate/01_import-synthetic.{ext}` writes the rows to `data/synthetic/` as Parquet, and when they arrived as CSV its first action is the conversion and exchange manifest, so nothing in the container reads the CSV first. With no report the import carries no CPS-GEN block. DS-4 then works from that imported Parquet (its column names and types, and the patterns the fake rows show) plus the user's own description of the data: dispatch the DS-4 template with its `[T4, no profile report]` lines, which give data-ingest the Parquet path in place of **REPORT** and have it load the rows in a file-first script. Every interpretation is still `[PRELIMINARY]` with a basis that names the synthetic rows or the user's description, and the PSU-DS2 statement says the interpretations come from the fake rows and the user's description, not the real data. With a companion report, DS-3 and DS-4 run as written, on that report.
- **DS-5 becomes import + validation** rather than generation. **If the rows arrived as CSV (the audited boundary exception), the FIRST in-container action is to convert the CSV to Parquet and record an exchange manifest** (a JSON sidecar named `{converted_filename}_exchange_manifest.json`) beside the converted file — capturing the original filename, source format, row and column counts, the file hash (e.g., SHA-256), and the conversion timestamp — after which all subsequent in-container work uses only the converted Parquet (the framework's in-container Parquet-only rule is thereby preserved: Parquet-only, with one audited exception at this T4 local-exchange boundary). If the rows arrived as Parquet, import them directly. research-executor imports the user-supplied synthetic data from `data/profile_report/` into `data/synthetic/` with the DS-5 host script **`scripts/synth_generate/01_import-synthetic.{ext}`** (the project's execution language; executed via `run_with_capture.sh`), which does the CSV→Parquet conversion and exchange manifest first when applicable. What happens next depends on whether a profile report also crossed:
  - **With a profile report** (the user also ran the profiler and its report cleared DS-3): the CPS-GEN block is embedded at the **end of the import script**, after the Parquet is in `data/synthetic/`, and **runs in full** — there is no lighter mode. Its config values are the DS-5 ones above with `tier = 4` (the report's own `settings.tier` then governs which blocks are expected to be released), `report_path` = the DS-3 report, `synthetic_path` = the imported Parquet in `data/synthetic/`, and `seed` = the value on the `seed:` line of the user's generation log, `data/profile_report/synthesis_log.txt` (or `seed_exception`, per the missing-seed policy below). QAS-C validates **against the profile report**.
  - **Without a profile report:** the import already ran before DS-4 (previous bullet), so DS-5 does not run it again. CPS-GEN is **not run** — it has no report to compare against. STATE.md § Synthetic QA Status records the CPS-GEN row as **`EXEMPT (T4, no profile report)`** with the reason in place of a verdict and counts; GDS-5 accepts `EXEMPT` only when tier = 4 and no report crossed. QAS-C validates **against the user's declared metadata** (row count, column set/types, declared marginals). Running the block with `report_path` unset is **not** an exemption path: it yields `[NOT VERIFIED]` lines, which force `CPS-GEN VALIDATION: FAILED`.
- **Missing-seed policy (default BLOCKER, one narrow T4 exception).** The seed requirement (c10) applies to the *user's* synthesis log, `data/profile_report/synthesis_log.txt`, which the Level 4 handoff asks the user to send unchanged with the rows; if it did not arrive, ask for it. A missing seed is a **BLOCKER by default** (as at GDS-5 and in QAS-C severity): synthetic data without a recorded seed is not reproducible. T4 is the **sole exception path**, and it may proceed only under all three of these conditions: (1) **explicit researcher authorization at the gate** — the orchestrator must ask the researcher directly and may never auto-waive the requirement; (2) the resulting artifact is labeled a **"non-reproducible T4 synthetic artifact"**, and that status is carried both in the artifact's provenance and in the skill's Synthetic Data Notice; (3) the artifact remains eligible for downstream skill delivery (rejoin DI-7/DI-8), but the delivered skill's Synthetic Data Notice MUST carry the non-reproducibility qualification. If the researcher does not authorize the exception, the missing seed stays a BLOCKER — request a re-run that records one.

  **How condition (1) reaches CPS-GEN.** Record the authorization in STATE.md § Synthetic Path Tracking > **T4 Missing-Seed Exception** before the import script runs, then leave `seed` unset (`None` / `NULL`) and set the config key **`seed_exception`** (default `None` / `NULL`) to a non-empty string pointing at that record (e.g. `"STATE.md § Synthetic Path Tracking > T4 Missing-Seed Exception"`); the block never prints its value. `seed_recorded` stays non-declarable via `not_applicable` — `seed_exception` is the only way a missing seed clears, and it does not clear silently:
  - a valid integer `seed`, `seed_exception` unset ⇒ the usual `[PASS] seed_recorded` line;
  - `seed` unset, `seed_exception` set, tier 4 ⇒ `[WARNING] seed_recorded: tier 4 import with no recorded seed — researcher-authorized non-reproducible T4 exception (authorization recorded in STATE)` ⇒ verdict at best `PASSED WITH WARNINGS`;
  - `seed_exception` set at tier 1–3 ⇒ `[FAIL] seed_recorded: seed_exception is honored only at tier 4`;
  - both set ⇒ `[FAIL] seed_recorded: seed and seed_exception are both set — record one`;
  - neither set ⇒ `[FAIL] seed_recorded: the generation seed is not an integer recorded in this script's config` (never `[NOT VERIFIED]`; the verdict is `FAILED`).

  Setting `seed_exception` without a recorded authorization is a process violation, not a config choice; QAS-C checks that the pointer resolves to one. At T4 with no profile report, CPS-GEN does not run, so the same policy is applied by QAS-C (c10) against the user's generation log and the STATE record.

Everything downstream of DS-5 (rejoin DI-7/DI-8) is identical across T1–T4 except the `data-provenance` value.

---

## Rejoin DI-7 / DI-8: Skill Authoring with Synthetic Provenance

After DS-5 passes, skill authoring proceeds per `WORKFLOW_PHASE_DO_AUTHORING.md` (Stages DI-7/DI-8) — same authoring agent, same template, same delivery — with these **synthetic-provenance overrides**. Pass all of them into the DI-7 authoring invocation:

1. **`data-provenance` frontmatter** set to the tier value: `synthetic-profile-t1`, `synthetic-profile-t2`, `synthetic-profile-t3`, or `synthetic-local-t4` (never `real`). This key and its vocabulary are defined in `DATA_SOURCE_SKILL_TEMPLATE.md`.
2. **Mandatory "Synthetic Data Notice" section** in the skill (per the template): states that the skill was built from a disclosure-controlled profile of sensitive data the container never saw; that the bundled/example data is synthetic; and — foregrounded — the scaffold-not-substitute doctrine: **all findings must be finalized by re-running the vetted code against the real data, in the environment where the real data lives.** If the artifact was produced under the authorized T4 missing-seed exception (§ T4 Variant), the Notice MUST additionally carry the **"non-reproducible T4 synthetic artifact"** qualification.
3. **Every skill mention of the data carries the scaffold caveat.** Decision trees, example fetches, and quick-reference tables that reference the dataset note that values are synthetic and structurally (not analytically) representative.
4. **Bundle the provenance scripts** into `.claude/skills/{skill_name}/scripts/` (the existing DI-7 script-bundling pattern): the customized local profiling script (`profile_{dataset_slug}.{R,py}`; at T4, the synthesizer `synthesize_{dataset_slug}.{R,py}` and any companion profiler), the DS-3 report-intake validator, and the DS-5 generation script (at T4, the DS-5 import script) — so the whole synthetic construction is reproducible. Do **not** bundle the profile report itself unless the user explicitly approves (it is a summary of their sensitive data); reference its schema instead.
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
| Sensitivity gate outcome 3 recorded | Data Source Info > Sensitivity Gate = 3; Sensitivity Gate Outcome with its reason (unsure / unprotected); Current Position unchanged until DS-1 starts (then Current Phase DO-2 (Profiling & Reconciliation), Current Stage DS-1) |
| PSU-DS1 confirmed (GDS-0) | Chosen tier; suppression threshold; relationship spec; at T4 with a companion profiler run, the T4 Companion Profile Tier; Key Decisions Made |
| DS-1 complete (GDS-1) | Profiling Script Version Handed Off (the customized script's path and tier config); QAS-A row of Synthetic QA Status — verdict **and** its count line (passed / warnings / blockers / not verified / skipped / info); Files Created This Session |
| DS-2 handoff issued | Wait-State Status = Awaiting user local run (DS-2); Next Actions naming the expected file(s); User Restart Prompt (wait state) |
| DS-2 files returned (GDS-2) | Report Path (the JSON report; at T4, record the synthetic data file and log under Files Created This Session and set T4 Local-Synthesis Variant? = Yes); Wait-State Status = Report received (DS-3) |
| DS-3 complete (GDS-3) | **CPS-INTAKE row** (verdict + count line) and **QAS-B row** (verdict + count line) — or, at T4 with no profile report only, both `EXEMPT (T4, no profile report)` + reason; Wait-State Status = Past intake; any disclosure event (the GDS-3 list) escalated and recorded in Key Decisions Made |
| DS-4 complete + PSU-DS2 (GDS-4) | Profiling Preliminary Notes > DS-4 row = WRITTEN; Interpretation Tracking section (a separate top-level STATE section) — User Decision + Final Interpretation, all rows; Pre-Authoring Research choice |
| DS-5 complete (GDS-5) | Synthetic parquet path (Files Created This Session; at T4 with no profile report it was recorded when the import ran before DS-4); Generation Seed; **CPS-GEN row** (verdict + count line — or, at T4 with no profile report only, `EXEMPT (T4, no profile report)` + reason) and **QAS-C row** (verdict + count line); at T4 under the authorized missing-seed exception, the **T4 Missing-Seed Exception** field (written before the import script runs, since `seed_exception` points at it) |
| Any QAS BLOCKER, or any CPS `FAILED` | QA Blockers table; Error Budget Consumed; revision status |
| Context ELEVATED+ | Context Snapshot + restart prompt (DS-2 and post-PSU-DS2 are natural restart boundaries) |
| Rejoin DI-7 | Current Position → Current Stage DI-7, Current Phase DO-3 (Skill Authoring & Delivery); pass provenance overrides to authoring (the `data-provenance` value follows from Disclosure Tier) |

**Record the verdict *and* the counts.** The § Synthetic QA Status table in STATE.md carries five rows — QAS-A, CPS-INTAKE, QAS-B, CPS-GEN, QAS-C — each with its enum and its count columns. A recorded `PASSED` with no counts cannot be distinguished later from a `PASSED` over checks that never ran, which is the failure this contract exists to prevent. `PENDING` is the pre-run value; there is no `ISSUES` value on any row. The one non-verdict value is `EXEMPT (T4, no profile report)`, legal only on the CPS-INTAKE, QAS-B and CPS-GEN rows at tier 4 when no report crossed; it records its reason in place of counts.

**Natural restart boundaries:** DS-2 (waiting on the user's local run) and post-PSU-DS2 (interpretations confirmed, before generation). If utilization is ELEVATED or higher at either, finalize STATE.md and recommend resuming in a fresh session.

---

## Verification Checklists

#### DS-1 (Script Preparation)
- [ ] Shipped asset **copied** (not edited/executed in place) to `scripts/local_profiling/`
- [ ] Only the Config block customized; suppression logic left structural
- [ ] Zero-DAAF-dependency, self-contained, IAT + REVIEW-BEFORE-SHARING block intact
- [ ] Script NOT executed in-container
- [ ] `QAS-A RESULT: PASSED` with `0 blockers, 0 not verified, 0 skipped` (a1–a11 all ran, edge cases traced) — no forbidden emission reachable

#### DS-2 (User Local Run)
- [ ] Plain-language handoff issued (get script out, run one command locally, two outputs, review `.txt`, return only JSON), naming the script file for the user's local language
- [ ] Disclosure-review instruction explicit: guidance + exact candidate; inspect category levels, `n_levels_binned`/`__OTHER__`, `withheld`/`reason`, cross-tab `null`, relationship `available`, and tier match
- [ ] (T4) Level 4 handoff issued: return exactly the synthetic data file and `synthesis_log.txt` (unchanged), never the real data or the fitted model
- [ ] Wait state recorded in STATE.md with restart prompt
- [ ] Returned JSON present and non-empty in `data/profile_report/` (T4: the synthetic data file and the log, plus any companion JSON)

#### DS-3 (Report Intake & Validation)
- [ ] DS-3 script carries the CPS-INTAKE block copied verbatim from VALIDATION_CHECKPOINTS.md, with the values set in the block's own Config section; it recomputes independently (not echoing embedded all_passed)
- [ ] `CPS-INTAKE VALIDATION: PASSED` or `PASSED WITH WARNINGS`, count line recorded
- [ ] `QAS-B RESULT: PASSED` or `WARNING`, count line recorded; any finding on the GDS-3 disclosure-events list escalated as a disclosure event
- [ ] Report confirmed trustworthy before any generation
- [ ] (T4, no profile report) DS-3 skipped; CPS-INTAKE and QAS-B rows recorded `EXEMPT (T4, no profile report)` with their reason

#### DS-4 (Interpretation)
- [ ] All interpretations marked `[PRELIMINARY]` with report-based basis
- [ ] (T4, no profile report) the DS-5 import ran first (any CSV converted, with its exchange manifest); data-ingest loaded the imported Parquet in a file-first script, and each basis names the synthetic rows or the user's description
- [ ] Tier-driven confidence limits stated per interpretation
- [ ] Domain decomposition + exclusion observations produced
- [ ] PSU-DS2 presented; every Interpretation Tracking row has a Final Interpretation
- [ ] Pre-Authoring Research Offer presented (skippable)

#### DS-5 (Generation & Validation)
- [ ] Generation seeded; seed recorded in the log (T4: the seed from the user's generation log, or the authorized exception below)
- [ ] Synthetic parquet written to `data/synthetic/` (not `data/raw/`)
- [ ] Categoricals drawn only from emitted levels; `__OTHER__` preserved; identifiers value-free
- [ ] DS-5 script carries the CPS-GEN block copied verbatim from VALIDATION_CHECKPOINTS.md, with the values set in the block's own Config section; `CPS-GEN VALIDATION: PASSED` or `PASSED WITH WARNINGS`, count line recorded — or, only at T4 with no profile report, the CPS-GEN row recorded `EXEMPT (T4, no profile report)` with its reason (the block not run)
- [ ] `QAS-C RESULT: PASSED` or `WARNING` (c1–c11), count line recorded; `row_count_matched`, `column_set_and_types`, `other_bucket_preserved`, `no_fabricated_categories`, `identifier_scaffolds_typed_value_free` clear, and `seed_recorded` clear unless the researcher-authorized T4 missing-seed exception applies (then a WARNING)
- [ ] (T4) user-supplied synthetic imported from `data/profile_report/` by `scripts/synth_generate/01_import-synthetic.{py,R}`, seed taken from `synthesis_log.txt`, + validated against the report (CPS-GEN embedded at the script's end, `tier = 4`) or, with no report, against declared metadata; if it arrived as CSV, converted to Parquet with an exchange manifest recorded as the first in-container action
- [ ] (T4) missing seed handled per policy — BLOCKER by default, or the researcher-authorized "non-reproducible T4 synthetic artifact" exception recorded in STATE (T4 Missing-Seed Exception), passed to CPS-GEN as `seed_exception` (`[WARNING] seed_recorded`), and carried in provenance + Synthetic Data Notice

#### Rejoin (DI-7/DI-8)
- [ ] `data-provenance` frontmatter set to the tier value (not `real`)
- [ ] "Synthetic Data Notice" section present with scaffold-not-substitute doctrine
- [ ] Provenance scripts bundled (local profiler + intake validator + generation script)
- [ ] Every data mention carries the scaffold caveat
- [ ] Delivery message surfaces provenance + finalize-against-real-data requirement
