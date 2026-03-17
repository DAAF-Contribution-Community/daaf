# Verification Checklists by Stage

**Stage 4 (Plan Creation) Verification:**
- [ ] Research question clearly stated (not placeholder)
- [ ] Research Outcomes section has ≥3 investigation/measurement objectives that do not pre-specify directional results
- [ ] Hypotheses (if any) are clearly separated from Research Outcomes and include basis citations
- [ ] Data Sources table complete with endpoints and years
- [ ] Transformation Sequence table has all tasks with waves assigned
- [ ] Every task has explicit file paths (no placeholders like "TBD")
- [ ] Every task has a skill or agent identified
- [ ] Every join task has cardinality specified (1:1, 1:many, many:1)
- [ ] Every task has verifiable "done" condition
- [ ] Risk Register identifies ≥1 risk with mitigation
- [ ] Wave dependencies are correct (no circular dependencies)
- [ ] Validation checkpoints specified for each phase

**Stage 2 (Data Exploration) Verification:**
- [ ] Recommended Data Level specified (not "TBD" or placeholder)
- [ ] Candidate Endpoints table has ≥1 endpoint with complete rows
- [ ] Key Variables table has actual variable names (not "[add more]")
- [ ] Variables Flagged for Deep-Dive has rationale for each flag
- [ ] Completeness Assessment checkboxes all marked
- [ ] Confidence Assessment present with overall confidence level
- [ ] If confidence is LOW: resolution plan or escalation present

**Stage 3 (Source Deep-Dive) Verification:**
- [ ] Source name explicitly stated
- [ ] Source-Specific Caveats table populated (not empty)
- [ ] Coded Value Mappings complete for all flagged variables
- [ ] Suppression Patterns documented with typical rates
- [ ] Cross-region comparability assessed (if multi-region analysis, e.g., cross-state for education)
- [ ] Critical Warnings have mitigation strategies
- [ ] Confidence Assessment present
- [ ] If confidence is LOW: resolution present

**Stage 3.5 (Findings Synthesis) Verification:**
- [ ] All source findings consolidated into unified summary
- [ ] Cross-source conflicts identified and resolved (or flagged for Plan)
- [ ] Join feasibility assessed with key considerations documented
- [ ] Unified guidance ready for data-planner input
- [ ] Confidence Assessment present

**Stage 5 (Data Retrieval) Verification:**
- [ ] Fetch Summary has actual counts (not "TBD")
- [ ] CP1 Status explicitly stated (PASSED/FAILED/WARNING)
- [ ] File locations provided with actual filenames
- [ ] If CP1 FAILED: Stop reason documented
- [ ] If data lag ≥3 years: Flagged for user notification
- [ ] If flag years (per FLAG_YEARS in Plan Domain Configuration) included: Flagged with warning

**Stage 6 (Context Application) Verification:**
- [ ] Cleaning Applied table shows actual row counts removed
- [ ] CP2 Status explicitly stated
- [ ] Suppression rate calculated and reported
- [ ] Validity Check completed (Yes/No/Conditional)
- [ ] Citation text present and complete
- [ ] File locations provided
- [ ] If CP2 FAILED: Stop reason documented

**Stage 7 (Transformation) Verification:**
- [ ] Pre-state and post-state both documented
- [ ] Row change percentage calculated
- [ ] Invariants checked with PASS/FAIL status
- [ ] Overall status: PASSED/FAILED/WARNING
- [ ] If FAILED: Issue description and proposed fix present
- [ ] For joins: Cardinality validation performed

**Stage 8.1 (Statistical Analysis) Verification:**
- [ ] Statistical method appropriate for data type and research question
- [ ] Assumptions validated before analysis (documented in script)
- [ ] Results saved to `output/analysis/` as parquet
- [ ] Key findings documented with effect sizes and confidence intervals
- [ ] Interpretation aligned with Research Outcomes in Plan
- [ ] Overall status: PASSED/FAILED/WARNING

**Stage 8.2 (Visualization) Verification:**
- [ ] All Plan-specified figures generated
- [ ] Figures saved to `output/figures/` as PNG
- [ ] Proper labeling (title, axes, legend, source note)
- [ ] Data source in visualization matches analysis dataset
- [ ] Colorblind-safe palette used
- [ ] Overall status: PASSED/FAILED/WARNING

**Stage 12 (Final Verification) Output Verification:**
- [ ] Independent assessment performed (expectations listed before Plan comparison)
- [ ] All four verification layers completed (Existence, Substantive, Wired, Coherent)
- [ ] Research question stress test result stated with reasoning
- [ ] At least one key finding traced end-to-end (Telephone Game test performed)
- [ ] Confidence assessment completed for all five aspects with rationale
- [ ] Verification Quality Self-Check results included (all 8 questions)
- [ ] If PASSED: conclusion articulates WHY the analysis is sound, not just absence of failures
