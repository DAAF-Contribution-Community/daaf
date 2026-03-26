# Data Onboarding: Skill Authoring & Delivery (Stages DI-7 and DI-8)

Loaded by the orchestrator when profiling is complete and the user has confirmed interpretations at PSU-DI2. Contains the skill authoring invocation template, CPP-SKILL validation, reference file guidance, and delivery format. The main mode reference file (`data-onboarding-mode.md`) contains the workflow overview, gate definitions, execution cycle, and PSU templates.

---

## Skill Authoring Invocation Template

Invoked at Stage DI-7 after PSU-DI2 user confirmation of preliminary interpretations.

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

**PROFILING SCRIPTS:** All executed scripts with execution logs are in `{project_dir}/scripts/`.
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
2. Read STATE.md for provenance, user-confirmed interpretations, and reconciliation findings
3. Use user-confirmed interpretations (not preliminary) for all semantic claims
4. Author SKILL.md per canonical 12-section data source template
5. Create reference files in .claude/skills/{skill_name}/references/:
   - columns.md — full column definitions, types, null rates (from scripts 02, 03)
   - coded-values.md — all coded/sentinel value mappings (from scripts 03, 09)
   - data-quality.md — data quality observations, anomalies, doc discrepancies (from scripts 09, 11)
   - variable-definitions.md — semantic column interpretations, user-confirmed (from script 10 + PSU-DI2)
   - Additional topic-specific reference files as warranted by the data source (see guidance below)
6. Save draft to {project_dir}/output/skill_draft/ and final to .claude/skills/{skill_name}/

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
    implications for generalizability?
  * **Valid and Invalid Analyses:** Structured tables showing what analyses are appropriate
    vs. problematic, with reasoning:
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
    Include specific variable names and access guidance, not just source names.
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
- [ ] coded-values.md enumerates ALL coded/sentinel values found during profiling
- [ ] data-quality.md catalogs ALL anomalies from profiling scripts
- [ ] variable-definitions.md groups columns by semantic family with descriptions
- [ ] analytical-context.md exists with study design, population coverage, and valid/invalid analysis sections
- [ ] analytical-context.md contains >= 3 valid and >= 3 invalid analysis patterns
- [ ] Total reference file lines >= 3x SKILL.md lines (target; not a blocker if close)
- [ ] Reference files contain ~40-60% interpretive/analytical content (not purely data description)
- [ ] CPP-SKILL results reported as itemized pass/fail per check item (not just overall status)
- [ ] Additional topic-specific reference files created where source complexity warrants

**OUTPUT FORMAT (2500-word hard cap):**
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
