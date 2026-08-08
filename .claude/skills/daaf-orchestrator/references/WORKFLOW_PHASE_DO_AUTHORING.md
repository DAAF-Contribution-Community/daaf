# Data Onboarding: Skill Authoring & Delivery (Stages DI-7 and DI-8)

Loaded by the orchestrator when profiling is complete and the user has confirmed interpretations at PSU-DI2. Contains the optional pre-authoring research dispatch, the skill authoring invocation template, CPP-SKILL validation, reference file guidance, and delivery format. The main mode reference file (`data-onboarding-mode.md`) contains the workflow overview, gate definitions, execution cycle, and PSU templates.

> **Synthetic path rejoin.** When the session arrived via the synthetic (privacy-preserving) path — DI-1 sensitivity gate → Stages DS-1–DS-5 — these stages still apply, but the DI-7 authoring invocation MUST include the synthetic-provenance overrides defined in `WORKFLOW_PHASE_DO_SYNTHETIC.md` § "Rejoin DI-7 / DI-8: Skill Authoring with Synthetic Provenance" (`data-provenance` frontmatter value, the mandatory "Synthetic Data Notice" section, bundling of the customized profiling + generation scripts, and the scaffold-not-substitute doctrine). Read that section alongside this file before dispatching DI-7 on the synthetic path.

---

## Pre-Authoring Research (Optional)

Runs **only if the user accepts the Pre-Authoring Research Offer** presented after PSU-DI2 (the offer text and interaction rules live in `data-onboarding-mode.md` § PSU Templates > Pre-Authoring Research Offer). If the user skipped, ignore this section and proceed directly to the Skill Authoring Invocation Template below.

**Why this exists.** Profiling establishes *what the data looks like*; it cannot establish the collection methodology, population coverage rationale, valid/invalid analytical patterns, or documented limitations that make a data source skill genuinely useful. Those live in the source's official documentation and the research/practitioner literature. Grounding the skill in real sources beats ungrounded inference (see `CLAUDE.md` § "Skill information awareness"). The research runs to completion and its findings are persisted **before** the DI-7 skill-authoring subagent is dispatched, so DI-7 can consume them as an input.

**Executor.** Dispatch a `search-agent` (read-only, web-capable via WebSearch plus the DAAF fetch protocol — `web-retrieval` skill, DAAF-aware). Keeping the research in its own dispatch keeps it separate, auditable, and complete before authoring begins. Do NOT fold the research into the DI-7 authoring subagent — the separation is what makes the research trail reviewable and lets profiling (observed) be reconciled against literature (reported) as an explicit input.

> **Async dispatch note.** The pre-authoring research is a single `search-agent` dispatch, not a wave. Under async dispatch it returns via a completion notification; do not persist its notes, dispatch DI-7, or advance until that return has arrived and been written to disk. See `SKILL.md` § Subagent Coordination > "Wave Barrier Discipline (Async Dispatch)."

**Model tier.** Mechanical documentation lookup stays `sonnet` (search-agent's default). If the accepted scope is **Deep** — interpretive synthesis across methodology literature and practitioner guides rather than straight documentation retrieval — add an explicit `model: opus` override on the dispatch, per the orchestrator SKILL.md Model Selection doctrine ("a search-agent dispatch is review-role or interpretive-synthesis work … rather than mechanical lookup"). Focused/documentation-only research stays `sonnet`.

### Pre-Authoring Research Invocation Template

**Purpose:** Ground the skill's analytical context in external sources  |  **Runs:** after PSU-DI2, before DI-7 (only if user accepted)  |  **Subagent:** search-agent  |  **Skills:** `data-scientist`

```python
Agent({
    description: "Pre-authoring research for {source_name}",
    prompt: """You have access to a skill tool. First, call the skill tool with name 'data-scientist'.

**BASE_DIR:** {BASE_DIR}
All relative paths resolve from BASE_DIR.

**TASK:**
Research the data source **{source_name}** online to gather the methodological and
analytical context that data profiling cannot produce. This research will be folded
into a data source skill about to be authored. Ground every claim in a real source —
this is exactly the context that must NOT be invented.

**WHAT PROFILING ALREADY ESTABLISHED (do not re-derive):**
{2-4 sentence summary of confirmed structure, columns, temporal scope, and the key
quality anomalies from PSU-DI2 — so the agent researches context, not the schema}

**RESEARCH SCOPE:** {Focused | Deep, per user's accepted decision}
- Focused: official source documentation + known caveats and analytical guidance
- Deep: the above plus methodology literature and practitioner guides

**SOURCE MIX:** {Mixed | user-specified subset — e.g., "official docs only", "official + academic"}
- Prioritize the mix the user selected. Default Mixed = official documentation +
  academic literature + practitioner guides.

**FOCUS AREAS (seeded from profiling; user may have adjusted):**
{profiling-seeded focus list — e.g., "whether the 2015 temporal break corresponds to a
known methodology change; the meaning of the -3 suppression code; documented population
exclusions"}

**WHAT TO GATHER (map to the skill sections these feed):**
- Study/survey design: who collects this data, under what mandate/methodology, and why
- Population coverage: who is included AND excluded, and the generalizability implications
- Valid vs. invalid analyses: what this source supports vs. what misuses it, with reasoning
- Known limitations, caveats, suppression/rounding conventions, and methodology breaks
- Resolution of the seeded focus-area questions above

**EVIDENCE REQUIREMENTS:**
- Every substantive claim MUST carry its source URL inline. A claim without a URL is
  not usable — omit it or clearly mark it as unverified inference.
- Prefer primary/official documentation over secondary summaries; note when a claim
  rests only on a practitioner blog vs. official docs.
- If you cannot find grounding for a seeded focus area, say so explicitly rather than
  filling the gap with inference.

**OUTPUT FORMAT (1500-word hard cap):**

### Source Research: {source_name}
**Scope executed:** [Focused | Deep] | **Source mix:** [what you actually consulted]

### Study/Survey Design
[Findings with inline source URLs]

### Population Coverage (Included / Excluded)
[Findings with inline source URLs]

### Valid vs. Invalid Analyses
| Pattern | Valid/Invalid | Reasoning | Source URL |
|---------|---------------|-----------|-----------|

### Limitations, Caveats & Conventions
[Suppression, rounding, methodology breaks, comparability boundaries — with URLs]

### Seeded Focus Areas — Resolution
| Focus Area (from profiling) | What the sources say | Source URL | Confidence |
|-----------------------------|----------------------|-----------|------------|

### Sources Consulted
| Source | Type (official/academic/practitioner) | URL |
|--------|---------------------------------------|-----|

### Confidence & Gaps
**Overall Confidence:** [HIGH | MEDIUM | LOW]
- [Focus areas left unresolved or resting on weak sources]

### Learning Signal
**Learning Signal:** [Category] — [One-line insight] | "None"

After completing the skill's Required Actions, return findings using the format above.""",
    subagent_type: "search-agent"
    # For Deep scope only, add:  model: "opus"
})
```

### Persistence

When the search-agent returns, persist the full, unmodified return losslessly to disk **before** dispatching DI-7 (per orchestrator SKILL.md § Subagent Return Processing):

| Agent Return | Write To |
|-------------|----------|
| search-agent (pre-authoring research) | `{project_dir}/output/preliminary_notes/{date}_preDI7_research_{source}.md` |

Prepend the standard provenance header (per orchestrator SKILL.md § Subagent Return Processing — the two-line HTML-comment block naming the agent type, stage identifier `preDI7-research`, and generation timestamp). Confirm the file exists on disk before proceeding — this is a gate condition, exactly as for profiling preliminary notes. Record the file in STATE.md Files Created This Session.

**Claim adjudication.** Pre-authoring research is web-sourced (reported), not observed. Where a research finding conflicts with a profiling observation, profiling (observed) outranks the literature (reported). Carry any URL-less or weakly-sourced claim forward marked as unverified, per the orchestrator's claim-adjudication rule.

---

## Skill Authoring Invocation Template

Invoked at Stage DI-7 after PSU-DI2 user confirmation of preliminary interpretations.

> **Async dispatch note.** DI-7 dispatches a single skill-authoring subagent (not a parallel wave). Under async dispatch, it returns via a completion notification rather than a synchronous tool return. Do not advance to DI-8 review, evaluate CPP-SKILL results, or present the skill to the user until that return has arrived and been fully processed. The DI-8 review iteration loop is likewise sequential — each re-invocation's return must be received before re-running CPP-SKILL validation or presenting the revised skill.

**Purpose:** Author the data source skill  |  **Stage:** DI-7  |  **Subagent:** general-purpose  |  **Skills:** `data-scientist`, `skill-authoring`

```python
Agent({
    description: "Stage DI-7: Skill authoring for {skill_name}",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Call the skill tool with name 'data-scientist'.
Then, call the skill tool with name 'skill-authoring'.
Read `agent_reference/DATA_SOURCE_SKILL_TEMPLATE.md` for the canonical 12-section order.

**PROJECT DIRECTORY:** {project_dir}

**PROJECT STATE:** {path_to_STATE_md}
Read the full STATE.md file. Key sections for skill authoring:
- **Data Source Info** — provenance, source provider, origin URL, format, domain context
- **Interpretation Tracking** — user-confirmed interpretations (use Final Interpretation column, not Preliminary)
- **Documentation Reconciliation Summary** — discrepancies between docs and data (if populated)
- **Profiling Progress** — script paths for all executed profiling scripts

**SOURCE DOCUMENTATION:** Before authoring, read any available documentation files referenced
in STATE.md (codebook PDFs, README files, technical documentation, methodology papers).
These are the source of methodological context, study design information, population coverage,
and analytical limitations that cannot be derived from profiling scripts alone. Reference
files must synthesize both profiling-derived observations AND documentation-derived context.
If a documentation website URL is in STATE.md, fetch key pages for methodology context.

**PROFILING PRELIMINARY NOTES:** Consolidated profiling findings from each phase are at:
- {project_dir}/output/preliminary_notes/{date}_partA_structural-discovery.md
- {project_dir}/output/preliminary_notes/{date}_partB_statistical-deep-dive.md
- {project_dir}/output/preliminary_notes/{date}_partC_relational-analysis.md
- {project_dir}/output/preliminary_notes/{date}_partD_interpretation-reconciliation.md
Read these preliminary notes FIRST for structured summaries and recommendations from
each profiling phase. These complement the execution logs in scripts/ — the preliminary
notes provide the narrative, confidence assessments, and recommendations; the execution
logs provide the granular data-level detail.

**PRE-AUTHORING RESEARCH NOTES (OPTIONAL — present only if the user accepted the
research offer):**
- {project_dir}/output/preliminary_notes/{date}_preDI7_research_{source}.md
This file contains externally-sourced context (study/survey design, population coverage,
valid/invalid analyses, limitations) gathered from official documentation and the
research/practitioner literature — the context profiling cannot produce. Use it to
enrich analytical-context.md and the limitations/pitfalls content especially. Two rules
when incorporating it:
1. **Carry source URLs.** Externally-sourced claims you put into the skill should retain
   their source URL (in the reference file, near the claim) so the analyst can trace them.
   A research claim with no URL is unverified inference — do not present it as fact.
2. **Profiling outranks literature on conflicts.** Where a research finding conflicts with
   what profiling actually observed in the data, the profiling observation wins; note the
   discrepancy in the skill (e.g., "documentation states X, but profiling of this extract
   found Y"). Observed beats reported.
If this file is absent, the user skipped pre-authoring research — proceed using profiling
findings and any user-supplied documentation as before.

**PROFILING SCRIPTS:** All executed scripts with execution logs are in `{project_dir}/scripts/`.
The preliminary notes above provide a consolidated narrative layer; consult the execution
logs below for granular data when the notes reference specific findings.
Read these scripts as primary sources for data-level skill content:
- Scripts 01-03 (structural) → schema, column details, data access patterns
- Script 04 (distributions) → distribution notes, Common Pitfalls
- Scripts 05-06 (temporal/entity) → coverage scope, Common Pitfalls (if executed)
- Script 07 (key-integrity) → Key Identifiers, join keys
- Scripts 08-09 (correlation/quality) → anomaly catalog, coded values, Common Pitfalls
- Script 10 (interpretation) → Decision Trees, variable definitions
- Script 11 (reconciliation) → data-quality, discrepancies (if executed)

**BENCHMARK CALIBRATION:** Before writing reference files, read 1-2 reference files from an
existing hand-authored data source skill to calibrate expected depth and density. Good
examples: `education-data-source-ipeds/references/graduation-rates.md` (methodology +
valid/invalid + alternatives) or `education-data-source-ccd/references/variable-definitions.md`
(comprehensive per-variable documentation with semantic groupings). If these paths do not
exist in the current environment, proceed using the density targets below as your guide.

**TARGET SKILL:**
- Name: {skill_name}
- Location: .claude/skills/{skill_name}/SKILL.md
- Draft: {project_dir}/output/skill_draft/SKILL.md

**TASK:**

Part 1 — Skill Authoring:
1. Read all executed profiling scripts from {project_dir}/scripts/ (check STATE.md Profiling Progress for paths)
2. Read STATE.md for provenance, user-confirmed interpretations, reconciliation findings, and any known exclusions from intake
3. Use user-confirmed interpretations (not preliminary) for all semantic claims
4. **Domain Assessment:** Before writing reference files, identify the source's 2-3 major
   analytical domains — the distinct research areas or methodological concerns that warrant
   dedicated documentation. Group columns and use cases into clusters. For each domain that
   requires 50+ lines of explanation (methodology, limitations, valid/invalid usage), plan a
   dedicated topic-specific reference file (e.g., `movers-design.md`, `vote-mode-reconstruction.md`,
   `covariate-structure.md`). If the source has 3+ distinct analytical use cases, at least one
   topic-specific file is required. These files should be 40-60% interpretive — explaining *why*
   limitations exist and *how* they affect specific analyses.
5. **Cross-Dataset Discovery:** Glob for all `.claude/skills/*-data-source-*/SKILL.md` files.
   Read their frontmatter descriptions to identify complementary data sources that share join
   keys (e.g., county FIPS, unitid, state codes). For sources with shared keys, create a worked
   join example (Polars for Python, dplyr for R) in the Related Data Sources section or in analytical-context.md's
   Alternative/Complementary Sources section. Include actual column names, join type, and a
   validation check.
6. Author SKILL.md per canonical 12-section data source template
7. Create reference files in .claude/skills/{skill_name}/references/:
   - columns.md — full column definitions, types, null rates (from scripts 02, 03)
   - coded-values.md — all coded/sentinel value mappings (from scripts 03, 09).
     **If no coded/sentinel values were found** (script 09 confirmed no sentinels):
     create `value-interpretation.md` instead. Document what values ARE present —
     negative value semantics, null patterns, expected ranges, value patterns that
     could be mistaken for codes. More useful than a file that merely states "no codes found."
   - data-quality.md — data quality observations, anomalies, doc discrepancies (from scripts 09, 11)
   - variable-definitions.md — semantic column interpretations, user-confirmed (from script 10 + PSU-DI2)
   - analytical-context.md — study design, population coverage, valid/invalid analyses (see detailed guidance below)
   - Topic-specific files — one per major analytical domain identified in the Domain Assessment (step 4)
8. Save draft to {project_dir}/output/skill_draft/ and final to .claude/skills/{skill_name}/
9. **Bundle Profiling Scripts:** Copy all executed profiling scripts (from STATE.md Profiling
   Progress table) to `.claude/skills/{skill_name}/scripts/`. These provide provenance and
   enable re-profiling if the source data updates. Do NOT copy QA review scripts (cr/ directory)
   — only the primary profiling scripts. Add a row to the Topic Index pointing to `./scripts/`
   for "Data profiling scripts (provenance)".

**REFERENCE FILE THOROUGHNESS GUIDANCE:**
Reference files are the primary vehicle for encoding detailed knowledge. They are loaded
on-demand (not at startup), so their token cost is incurred only when relevant. This means
reference files should be COMPREHENSIVE — err on the side of more detail, not less.

Density targets for reference files:
- columns.md: Every column documented with type, null rate, unique count, value range,
  and a semantic description. For datasets with <100 columns, include ALL columns.
  Target: 3-5 lines per column minimum.
- coded-values.md: Every coded/sentinel value fully enumerated. Include value-to-meaning
  mappings for ALL categorical columns, not just the most important ones. Document
  sentinel values (-1, -2, -3, 999, etc.) with their specific meanings per column if
  they differ. Target: comprehensive enough that an analyst never needs to inspect raw data
  to understand a code.
- data-quality.md: Every anomaly from the profiling scripts cataloged with severity,
  affected columns, row counts, and recommended handling. Include cross-column consistency
  observations. Document suppression patterns, rounding conventions, and any data-vs-docs
  discrepancies. Target: 150+ lines for complex sources.
- variable-definitions.md: Group columns by semantic family (identifiers, outcomes,
  demographics, etc.). Include derived metric recipes, naming convention patterns,
  join key guidance with specific examples, and temporal/coverage notes. Target: 150+ lines.
- analytical-context.md (REQUIRED for all skills): Methodology and research context that
  cannot be derived from data profiling alone. This file synthesizes documentation,
  codebooks, and domain knowledge. Required sections:
  * **Study/Survey Design:** Who collected this data, under what mandate/methodology, and
    why? (e.g., "mandated by Student Right-to-Know Act" or "linked IRS tax records to
    Census data"). Draw from documentation files referenced in STATE.md.
  * **Population Coverage:** Who is included AND excluded, and why? What are the
    implications for generalizability? MUST include an explicit **"What is NOT Included"**
    subsection documenting known exclusions:
    ### What is NOT Included
    | Exclusion | Evidence | Impact on Research |
    |-----------|----------|-------------------|
    | [e.g., "Private schools"] | [Source: documentation / profiling observation] | [e.g., "Cannot generalize to all K-12"] |
    Minimum: 2 exclusions documented (even if obvious, like "private schools not included").
    Sources of exclusion information: user-provided exclusions from DI-1 intake (recorded
    in STATE.md), exclusion statements extracted from documentation during Part D
    reconciliation, and coverage boundaries observed during Part B entity profiling.
  * **Temporal Scope:** What time period does this data cover? What cohorts, years, or
    waves? For cross-sectional data: what historical moment does this represent, and can
    it be compared to other time periods? For longitudinal data: are there schema changes
    or methodology breaks? Include explicit "DO NOT compare across this boundary" guidance
    if applicable (following the education skills' historical-changes.md pattern). If the
    data could be confused with more recent or more frequent data, flag this prominently.
  * **Valid and Invalid Analyses:** Structured tables showing what analyses are appropriate
    vs. problematic, with reasoning. Use concrete examples with real place names, variable
    names, or values where possible (following the OI Neighborhoods analytical-context.md
    pattern):
    ### Valid Analyses
    | Analysis | Why Valid |
    |----------|----------|
    | [specific analysis pattern] | [reasoning] |
    ### Invalid or Problematic Analyses
    | Analysis | Why Problematic |
    |----------|-----------------|
    | [specific analysis pattern] | [reasoning] |
    Minimum: 3 valid and 3 invalid patterns.
  * **Limitations by Research Context:** How do data limitations differentially affect
    specific research designs? Provide 2-3 worked scenarios (e.g., "if studying gender
    gaps within Black outcomes at high income levels, suppression substantially reduces
    your sample" vs. "if studying overall racial mobility gaps using pooled gender,
    suppression has minimal impact").
  * **Alternative/Complementary Sources:** What other datasets address this source's gaps?
    Include specific variable names and access guidance, not just source names. Use the
    cross-dataset discovery results (step 5) to identify DAAF skills that complement this
    source. Include worked join examples (Polars for Python, dplyr for R) for sources with shared join keys.
  Target: 200+ lines.
- Additional topic-specific files: Create when ANY of these apply:
  (a) The source has a major known limitation requiring >50 lines of explanation
  (b) The source spans multiple survey components or analytical domains
  (c) The source has significant historical changes affecting longitudinal use
  (d) The source's data collection process is non-obvious and affects interpretation
  (e) The source is commonly used alongside another specific source
  Use the hand-authored education data source skills as benchmarks — they average
  ~400 lines per reference file.

Overall reference file target: Collectively, reference files should total at least 3x
the SKILL.md line count. For a 300-line SKILL.md, aim for 900+ lines of reference
files. The hand-authored education skills average ~2,200 lines of reference content.

**Content quality target:** Reference files should be approximately 40-60% interpretive/
analytical guidance (why limitations exist, how they affect specific analyses, what
alternatives exist, when comparisons are valid vs invalid) and 40-60% factual data
description (code tables, column definitions, value enumerations). Pure data description
without analytical guidance produces reference files that are less useful than the
raw data itself.

Part 2 — CPP-SKILL Validation:
7. Run CPP-SKILL validation (checklist below). ALL checks must pass.

**CPP-SKILL VALIDATION:**

Skill template compliance:
- [ ] All 12 canonical sections in correct order
- [ ] Frontmatter includes provenance dates
- [ ] Value Encodings Warning in position 4 with comparison table
- [ ] Decision Trees: at least 2
- [ ] Missing Data Codes subsection in Quick Reference
- [ ] Truth Hierarchy blockquote in Data Access
- [ ] Common Pitfalls: 3-column table with >=3 rows
- [ ] Related Data Sources includes domain explorer and query skills (if they exist)
- [ ] Total SKILL.md under 500 lines

Reference file density:
- [ ] columns.md covers ALL columns (not just a subset)
- [ ] coded-values.md enumerates ALL coded/sentinel values found during profiling (or value-interpretation.md if no codes — documenting negative value semantics, null patterns, expected ranges)
- [ ] data-quality.md catalogs ALL anomalies from profiling scripts
- [ ] variable-definitions.md groups columns by semantic family with descriptions
- [ ] analytical-context.md exists with study design, population coverage, temporal scope, and valid/invalid analysis sections
- [ ] analytical-context.md Population Coverage contains explicit "What is NOT Included" subsection with >= 2 exclusions
- [ ] analytical-context.md contains Temporal Scope section documenting time coverage and comparison boundaries
- [ ] analytical-context.md contains >= 3 valid and >= 3 invalid analysis patterns (with concrete examples)
- [ ] Total reference file lines >= 3x SKILL.md lines (hard minimum; target 4-6x for complex sources)
- [ ] Reference files contain ~40-60% interpretive/analytical content (not purely data description)
- [ ] If source has 3+ distinct analytical use cases: at least one topic-specific reference file exists
- [ ] If source shares join keys with other DAAF skills: cross-dataset join example present in Related Data Sources or analytical-context.md
- [ ] Profiling scripts bundled in .claude/skills/{skill_name}/scripts/ (excluding QA/cr scripts)
- [ ] CPP-SKILL results reported as itemized pass/fail per check item (not just overall status)

**OUTPUT FORMAT (3500-word hard cap):**
### Skill Authoring: {skill_name}
- CPP-SKILL Status (template compliance) — itemized pass/fail per checklist item
- Line count: SKILL.md [N] lines, reference files [N] total lines ([ratio]x)
- Reference files created: [list with line counts]
- Skill maturity: Initial characterization (v1) — see delivery notes""",
    subagent_type: "general-purpose"
})
```

---

## Skill Authoring Invocation Checklist

Before dispatching the skill authoring subagent (Stage DI-7), verify:

- [ ] Project directory path specified (absolute)
- [ ] STATE.md path specified (subagent reads full file)
- [ ] PSU-DI2 user review is complete (Interpretation Tracking table has Final Interpretation column populated)
- [ ] Target skill name and directory path specified
- [ ] Skill name conflict checked (no existing skill at `.claude/skills/{skill_name}/`)
- [ ] `{BASE_DIR}` path specified (for skill placement in `.claude/skills/`)

---

## DI-8: Review, Iteration & Delivery

### Skill Review Iteration Loop

After DI-7 completes and the skill passes CPP-SKILL compliance, the orchestrator presents the skill to the user (via the delivery format in the main mode reference). If the user requests changes:

1. **Classify the request:**
   - **Minor** (description wording, frontmatter tweaks, reference file corrections): Orchestrator handles directly via targeted edits
   - **Moderate** (restructure decision trees, add missing reference content, adjust coded value tables): Re-invoke the skill authoring subagent with the user's specific feedback
   - **Major** (fundamental reinterpretation, wrong skill structure, missing entire analytical dimensions): Recommend switching to Framework Development mode for deeper revision

2. **Iteration limits:** Maximum 2 re-invocations of the skill authoring subagent. If the user's feedback cannot be addressed within 2 iterations, present the current state and suggest Framework Development mode:

   > "I've made two rounds of revisions. For the more substantial changes you're describing, Framework Development mode would give us more flexibility to restructure the skill. Want me to switch?"

3. **After each iteration:** Re-run CPP-SKILL validation on the revised skill. Update STATE.md Skill Authoring Status.

### Skill Maturity Framing

The DI-8 delivery message (defined in the main mode reference) should set appropriate expectations about skill maturity:

**Include in delivery:** This skill captures everything discoverable through automated profiling — structural characteristics, statistical distributions, data quality patterns, and preliminary interpretations confirmed by your review. As you use this data in future analyses, you'll likely discover additional edge cases, domain-specific pitfalls, and analytical patterns worth documenting. You can refine the skill at any time using Framework Development mode, or it will naturally improve as the pipeline encounters and documents new findings.

**Skill maturity levels** (for STATE.md and skill metadata):
- **v1 (Initial):** Created by Data Onboarding — automated profiling + user-confirmed interpretations
- **v2 (Battle-tested):** Refined after use in 1+ Full Pipeline analyses — edge cases discovered and documented
- **v3 (Mature):** Comprehensive coverage validated through multiple analyses and reproductions

The orchestrator records the maturity level in STATE.md's Skill Authoring Status section. The skill's SKILL.md does not explicitly show maturity level — it's tracked in the onboarding project's STATE.md for provenance.
