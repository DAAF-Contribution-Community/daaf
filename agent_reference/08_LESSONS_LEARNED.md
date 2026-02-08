# Lessons Learned Protocol

This document defines the systematic capture AND consumption of insights to build institutional knowledge and improve future work.

---

## Purpose

Every analysis produces learning opportunities beyond its immediate findings:
- API behaviors not documented elsewhere
- Data quality patterns
- Methodology insights
- Performance optimizations
- Common pitfalls to avoid

Capturing these lessons prevents repeated mistakes and accelerates future analyses. **Equally important:** consuming prior learnings ensures we don't repeat past mistakes.

---

## Consuming Prior Learnings (Stage 2-4)

**Before diving into a new analysis, check what we've already learned.**

### Two-Level Learning Sources

| Source | Location | Contains | When to Check |
|--------|----------|----------|---------------|
| **Repository-level** | Embedded in `education-data-source-*` skills | Consolidated API gotchas, variable mappings, endpoint behaviors | **Always** (skills load automatically) |
| **Project-level** | `research/*/LEARNINGS.md` | Analysis-specific insights, methodology discoveries | When using similar data sources |

### When to Search Prior Learnings

**Stage 2 (Data Exploration):** Before exploring data sources
```
Search: research/*/LEARNINGS.md for mentions of [data source]
Purpose: Find prior gotchas with this data source
```

**Stage 3 (Source Deep-Dive):** When investigating specific sources
```
Search: research/*/LEARNINGS.md for [source name] (e.g., "IPEDS", "CCD")
Purpose: Find variable name discrepancies, API quirks, suppression patterns
```

**Stage 4 (Planning):** When designing methodology
```
Search: research/*/LEARNINGS.md for [analysis type] (e.g., "join", "enrollment", "trends")
Purpose: Find methodology insights and time sinks to avoid
```

### Search Pattern

```bash
# Find all project learnings mentioning a data source
grep -rl "IPEDS\|ipeds" research/*/LEARNINGS.md

# Find learnings about specific issues
grep -rn "didn't work\|failed\|gotcha" research/*/LEARNINGS.md
```

### Orchestrator Protocol for Prior Learnings

**During Stage 2 (Data Exploration):**

1. **Check repository-level learnings:**
   - Source-specific `education-data-source-*` skills contain accumulated API gotchas, variable mappings, and endpoint behaviors directly
   - No additional action needed (skills handle this)

2. **Search project-level learnings (if ≥3 prior analyses exist):**
   ```python
   Task({
       description: "Search prior learnings",
       prompt: """Search for LEARNINGS.md files in research/ that mention:
       - Data sources: [list from Stage 2 findings]
       - Analysis type keywords: [relevant terms]

       Return: Relevant gotchas, warnings, or recommendations.""",
       subagent_type: "Plan"
   })
   ```

3. **Integrate findings into Plan:**
   - Add relevant prior learnings to Plan's Risk Register
   - Reference specific LEARNINGS.md files in Plan's "Prior Art" section (if added)

### Prior Learnings Checklist (Stage 4)

Before finalizing the Plan, verify:

- [ ] Source-specific `education-data-source-*` skills checked for relevant gotchas
- [ ] If using IPEDS: Checked for enrollment/finance endpoint quirks
- [ ] If using CCD: Checked for enrollment disaggregator requirements
- [ ] If using CRDC: Checked for disaggregation path requirements
- [ ] Prior project LEARNINGS.md searched for similar analysis types
- [ ] Relevant warnings incorporated into Risk Register

### What to Extract from Prior Learnings

| Category | Look For | Add To |
|----------|----------|--------|
| **API Gotchas** | Variable name mismatches, endpoint behaviors | Plan: Critical Warnings |
| **Data Quality** | Suppression rates, missing year patterns | Plan: Risk Register |
| **Methodology** | What worked/didn't work for similar analyses | Plan: Methodology Specification |
| **Time Sinks** | Tasks that took longer than expected | Plan: Risk Register (timeline) |

---

## Per-Session Capture

### When to Capture

Document lessons **during** the analysis, not just at the end:
- When encountering unexpected behavior
- When a technique works particularly well
- When abandoning an approach
- When discovering undocumented API behavior
- When finding data quality issues

### Where to Capture

Create `LEARNINGS.md` in the project folder:

```
research/YYYY-MM-DD [Title]/
├── LEARNINGS.md                      # Session learnings
├── YYYY-MM-DD [Title] Plan.md
├── YYYY-MM-DD [Title].py
├── ...
```

### Template

```markdown
# Learnings: [Project Title]

**Date:** YYYY-MM-DD
**Data Sources:** [list]
**Analysis Type:** [description]

---

## What Worked Well

Approaches that succeeded and should be reused:

- **[Technique/Pattern]:** [Description of what worked and why]
- **[Technique/Pattern]:** [Description]

---

## What Didn't Work

Approaches that failed, with explanations:

- **[Approach]:** [What was tried]
  - **Why it failed:** [Root cause]
  - **Alternative:** [What worked instead]

- **[Approach]:** [What was tried]
  - **Why it failed:** [Root cause]
  - **Alternative:** [What worked instead]

---

## Surprises

Unexpected findings about data, APIs, or methodology:

- **[Finding]:** [Description]
  - **Impact:** [How this affected the analysis]
  - **Recommendation:** [How to handle in future]

---

## API/Data Gotchas

Specific issues with data sources worth documenting:

### [Source Name] (e.g., CCD)

- **[Variable/Endpoint]:** [Issue description]
  - **Example:** [Concrete example]
  - **Workaround:** [How to handle]

### [Source Name]

- **[Variable/Endpoint]:** [Issue description]

---

## Time Sinks

What took longer than expected and how to avoid:

- **[Task]:** [What took extra time]
  - **Root cause:** [Why]
  - **Optimization:** [How to avoid in future]
  - **Estimated time saved:** [if applicable]

---

## Reusable Patterns

Code snippets, queries, or approaches to extract for reuse:

### [Pattern Name]

**Use case:** [When to use this]

```python
# [Code snippet]
```

**Notes:** [Any caveats or variations]

---

## Data Quality Notes

Issues specific to this dataset/analysis:

| Variable | Issue | Rate | Handling |
|----------|-------|------|----------|
| [var] | [issue] | [X%] | [approach] |

---

## Questions for Future Investigation

Open questions raised by this analysis:

- [ ] [Question 1]
- [ ] [Question 2]
- [ ] [Question 3]

---

## Recommendations for Similar Analyses

If someone were to do a similar analysis:

1. **Start with:** [First step recommendation]
2. **Watch out for:** [Key pitfall]
3. **Don't bother with:** [Approach to skip]
4. **Make sure to:** [Critical step not to miss]
```

---

## Repository-Level Consolidation

### When to Consolidate

Consolidate project learnings into repository-level documentation:
- After completing 5+ analyses
- Quarterly (whichever comes first)
- When major patterns emerge across projects

### Consolidation Target

Learnings are consolidated directly into the relevant `education-data-source-*` skills (e.g., API gotchas for CCD go into `education-data-source-ccd`, IPEDS gotchas into `education-data-source-ipeds`, etc.). This ensures source-specific knowledge is available automatically when subagents load the skill.

### Consolidation Categories

#### 1. API Gotchas

Variable name discrepancies, pagination issues, rate limiting, endpoint quirks.

```markdown
### [Source]: [Endpoint]

**Issue:** [Description]
**Discovered:** [Date/Project]
**Example:**
```
[Example code or query]
```
**Workaround:**
```
[Solution code or approach]
```
```

#### 2. Data Quality Issues

Source-specific patterns that affect analysis validity.

```markdown
### [Source]: [Issue Type]

**Pattern:** [Description]
**Frequency:** [How often encountered]
**Detection:** [How to identify]
**Handling:** [Recommended approach]
```

#### 3. Methodology Insights

What works for which question types, common transformation pitfalls.

```markdown
### [Analysis Type]: [Insight]

**Context:** [When this applies]
**Recommendation:** [What to do]
**Rationale:** [Why this works]
**Example projects:** [Where this was learned]
```

#### 4. Performance Optimizations

When to use bulk download vs. API, caching strategies, large dataset handling.

```markdown
### [Optimization Type]

**Use when:** [Conditions]
**Approach:** [What to do]
**Impact:** [Expected improvement]
**Trade-offs:** [What you give up]
```

---

## Integration with Workflow

### During Analysis (Stages 1-10)

As issues arise:
1. Note the issue immediately in LEARNINGS.md (if created early)
2. Don't wait until end of analysis
3. Include concrete examples
4. Document workarounds as you discover them

**Note:** While you can create LEARNINGS.md early and document as you go, it's **REQUIRED** to exist by the end of Stage 12.

### At Stage 12 (Final Review) - MANDATORY

**LEARNINGS.md creation is a REQUIRED gate criterion for Stage 12.**

The orchestrator MUST:
1. Create `LEARNINGS.md` in the project folder
2. Populate at minimum: What Worked Well, What Didn't Work, API/Data Gotchas
3. Flag items for repository-level consolidation
4. Include LEARNINGS.md in the delivery message

Stage 12 Gate Criteria includes:
- [ ] **LEARNINGS.md created and complete** (REQUIRED)
- [ ] Key findings flagged for repository consolidation
- [ ] Reusable patterns identified
- [ ] Items flagged for consolidation noted in delivery

See `02_WORKFLOW_STAGES.md: Stage 12` for the complete gate criteria and quick template.

### Session Recovery (Protocol 6)

When resuming:
1. Read prior session's LEARNINGS.md
2. Note known issues to avoid
3. Reference documented workarounds

---

## Learning Categories Reference

### Category: API Behavior

- Pagination edge cases
- Rate limiting patterns
- Variable naming inconsistencies
- Endpoint response variations
- Authentication/access issues

### Category: Data Quality

- Suppression patterns by source
- Missing value encoding
- Year-over-year definition changes
- State-level reporting variations
- COVID-19 data impacts

### Category: Methodology

- Transformation approaches
- Aggregation strategies
- Join key selection
- Validation techniques
- Visualization patterns

### Category: Performance

- Query optimization
- Bulk download strategies
- Memory management
- Parallel processing
- Caching approaches

### Category: Process

- Stage ordering insights
- Checkpoint timing
- Error recovery patterns
- User communication
- Documentation practices

---

## Quick Capture Template

For rapid capture during analysis, use this abbreviated format:

```markdown
## Quick Note: [timestamp]

**Category:** [API/Data/Method/Perf/Process]
**Issue:** [One-line description]
**Context:** [What I was doing]
**Solution:** [What worked]
**Flag for consolidation:** [Yes/No]
```

These quick notes can be expanded into full entries at Stage 12.

---

## Anti-Patterns

### Don't Do

- Wait until end to document (you'll forget details)
- Document only failures (successes are valuable too)
- Skip the "why" (reasons matter more than what)
- Duplicate existing documentation (link instead)
- Over-generalize from single instances (note sample size)

### Do Instead

- Capture in the moment
- Document both successes and failures
- Always explain the reason
- Reference existing docs, extend don't repeat
- Be specific about when insights apply
