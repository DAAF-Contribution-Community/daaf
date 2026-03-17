# Context Completeness Checklists

**Before invoking ANY Stage 5-8 subagent, verify context is complete.** Incomplete context causes subagent confusion, wasted tokens, and incorrect results.

**Stage 5 (Fetch) Checklist:**
- [ ] Research question inlined
- [ ] Years specified (exact range, not "recent years")
- [ ] Geographic scope specified (state, national, etc.)
- [ ] Filters specified (exact conditions)
- [ ] Expected row count range specified
- [ ] Output file paths specified (not placeholder)
- [ ] Missingness and coded value expectations mentioned
- [ ] Risk Register items for fetch included (from Plan)
- [ ] Domain query skill specified
- [ ] Script follows IAT documentation standards

**Stage 6 (Clean) Checklist:**
- [ ] Raw data location specified (exact path from Stage 5 output)
- [ ] Source caveats from Stage 3 inlined (not just referenced)
- [ ] Coded value handling specification provided
- [ ] Suppression tolerance thresholds specified
- [ ] Critical columns identified (from Plan Research Outcomes)
- [ ] Risk Register items for cleaning included
- [ ] Domain context skill specified (or N/A)
- [ ] Script follows IAT documentation standards

**Stage 7 (Transform) Checklist:**
- [ ] Prior transformation context inlined (EDA findings, prior transform results)
- [ ] Invariants to maintain listed (from prior transformations)
- [ ] Transformation specification complete (exact columns, exact conditions)
- [ ] Expected outcome specified (row count, shape)
- [ ] Join cardinality specified (if join task)
- [ ] Risk Register items included
- [ ] Research Outcome contribution stated
- [ ] Script follows IAT documentation standards

**Code-Reviewer (QA) Checklist:**
- [ ] Script path specified (exact path)
- [ ] Plan expectations INLINED (not just path) — row counts, tolerances, critical columns
- [ ] QA tolerance thresholds specified (BLOCKER if, WARNING if)
- [ ] Risk Register items included
- [ ] Research Outcome contribution stated
- [ ] Prior QA findings accumulated (if any WARNING items from prior scripts)
- [ ] Coded values from Plan inlined
- [ ] IAT compliance expectations stated

**Stage 8.1 (Analysis) Checklist:**
- [ ] Analysis dataset path specified (exact path from Stage 7 output)
- [ ] Statistical method specified (regression, summary stats, comparison, etc.)
- [ ] Dependent and independent variables identified
- [ ] Grouping/stratification variables specified (if applicable)
- [ ] Expected output format specified (summary table, model results, etc.)
- [ ] Output file path specified (`output/analysis/[date]_[description].parquet`)
- [ ] Significance thresholds or interpretation guidelines provided
- [ ] Research Outcome contribution stated
- [ ] Risk Register items included
- [ ] Script follows IAT documentation standards

**Stage 8.2 (Visualization) Checklist:**
- [ ] Analysis dataset and/or analysis results paths specified
- [ ] Figure specification provided (chart type, variables, grouping)
- [ ] Output file path specified (`output/figures/[date]_[description].png`)
- [ ] Labeling requirements stated (title, axes, legend, source note)
- [ ] Accessibility considerations noted (colorblind-safe palette, etc.)
- [ ] Research Outcome contribution stated
- [ ] Risk Register items included
- [ ] Script follows IAT documentation standards

**If any checklist item is unchecked:** Add the missing context before invoking. Incomplete context = subagent asks clarifying questions = wasted round-trip.
