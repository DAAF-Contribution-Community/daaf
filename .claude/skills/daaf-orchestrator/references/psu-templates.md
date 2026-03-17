# PSU Templates and Content Requirements

## PSU Template

Every Phase Status Update MUST follow this format:

```
**Phase Status Update: Phase [N] Complete — [Phase Name]**

**Summary:**
[2-3 sentence overview of what was accomplished in this phase]

**Key Findings:**
- [Finding 1]
- [Finding 2]
- [Finding 3]

**Decisions Made:**
| Decision | Rationale | Impact |
|----------|-----------|--------|
| [decision] | [why] | [what it affects] |

**Warnings & Issues:**
| Item | Severity | Status | Details |
|------|----------|--------|---------|
| [item] | WARNING/INFO | Resolved/Open | [details] |

[If no warnings: "No warnings or issues encountered in this phase."]

**Artifacts Produced:**
- [File path 1]: [description]
- [File path 2]: [description]

**Next Phase Preview:**
Phase [N+1] ([Phase Name]) will [brief description of what comes next and what it involves].

**Please confirm you'd like to proceed to Phase [N+1], or let me know if you'd like me to revisit or adjust anything from Phase [N].**
```

## PSU-Specific Content Requirements

**PSU1 (Discovery → Planning):**
- Data sources identified (with endpoints and year ranges)
- Key variables and their availability
- Source-specific caveats and limitations discovered
- Suppression patterns and cross-region comparability issues (e.g., cross-state for education)
- Feasibility assessment and recommended analytical approach
- Any LOW-confidence items requiring user input

**PSU2 (Planning → Data Acquisition):**
- Research question as stated in Plan
- Methodology summary (statistical approach, key decisions)
- Data sources and year ranges confirmed
- Transformation sequence overview (number of tasks, waves)
- Research Outcomes the analysis will investigate
- Hypotheses (if any) and their basis
- Risk Register highlights
- Plan-checker validation result (PASSED/PASSED_WITH_WARNINGS and any warnings)
- User informed of full Plan filepath and instructed to read it closely for their deep review

**PSU3 (Data Acquisition → Analysis):**
- Datasets acquired: source, shape, date range, file paths
- Data quality summary: missingness rates, suppression rates per dataset
- Cleaning actions taken and their impact (rows removed, values recoded)
- QA summary: QA1/QA2 results for each script (PASSED/WARNING with details)
- Any deviations from the Plan during fetch/clean
- Data readiness assessment for analysis phase

**PSU4 (Analysis → Synthesis):**
- Transformation summary: joins performed, derived variables, final analysis dataset shape
- Statistical analysis results: key findings with effect sizes and confidence intervals
- Key visualizations produced (reference file paths for user to inspect)
- QA summary: QA3/QA4a/QA4b results across all scripts
- Accumulated warnings from Stages 5-8 (the Stage 10 QA aggregation)
- Any deviations from Plan methodology
- Notebook compilation status
