# Lessons Learned Protocol

This document defines the systematic capture AND consumption of insights to build institutional knowledge and improve future work.

---

## Purpose

Every analysis produces learning opportunities beyond its immediate findings:
- Data download behaviors not documented elsewhere
- Data quality patterns
- Methodology insights
- Performance optimizations
- Common pitfalls to avoid

Capturing these lessons prevents repeated mistakes and accelerates future analyses. **Equally important:** incorporating and formalizing prior learnings ensures we don't repeat past mistakes.

---

## Incremental Capture Protocol

### Creation Trigger

LEARNINGS.md is a project-specific log of ongoing learnings created at **Stage 4** (alongside Plan + STATE.md). The skeleton includes project metadata and empty section headers from the template below.

**Gate G3 requires:** Plan + STATE.md + LEARNINGS.md all exist before proceeding to Stage 4.5.

### Learning Signal Format

Agents (research-executor, code-reviewer, debugger) include a lightweight Learning Signal field in their output:

```
**Learning Signal:** [Category: Access|Data|Method|Perf|Process] — [One-line insight] | or "None"
```

**Examples:**
- `**Learning Signal:** CCD enrollment value codes were not as expected in the codebook; codes needed to be explicitly examined for progress to continue`
- `**Learning Signal:** Data — MEPS poverty rates have 15% suppression in rural counties (higher than Plan estimate of 5%)`
- `**Learning Signal:** None`

### Accumulation Flow

```
Agent returns with Learning Signal
     ↓
Orchestrator extracts signal (if not "None")
     ↓
Orchestrator appends to STATE.md "Pending Learning Signals" buffer
     ↓
At next flush trigger → orchestrator appends buffered signals to LEARNINGS.md
     ↓
Clear STATE.md buffer
```

### Flush Triggers

The orchestrator writes buffered signals to LEARNINGS.md at these points:

1. **Phase boundary** — end of Phase 1 (after Stage 3/3.5), Phase 2 (after Stage 4.5), Phase 3 (after Stage 6-QA), Phase 4 (after Stage 8-QA / Stage 10)
2. **After blocker resolution** — a resolved BLOCKER often yields the richest learnings
3. **After debugging session** — debugger agent's Prevention section feeds learnings directly
4. **At utilization gates** (40%, 60%) — ensures learnings are persisted before potential session end

*Not* at every stage transition or every subagent return — that would be too frequent and disruptive.

### Flush Operation

What the orchestrator does at each flush:

1. Read pending signals from STATE.md buffer
2. Categorize each signal into the appropriate LEARNINGS.md section (Access/Data Gotchas, What Worked Well, Surprises, etc.)
3. Append as a quick-capture entry with stage number and timestamp
4. Clear the STATE.md buffer
5. This should take ~1 minute of orchestrator time, not a subagent invocation

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

*This template is created as a skeleton at Stage 4 (project metadata + empty section headers) and populated incrementally during Stages 5-8 via Learning Signals. At Stage 12, entries are consolidated and the System Update Action Plan is appended.*

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

Unexpected findings about data, access, or methodology:

- **[Finding]:** [Description]
  - **Impact:** [How this affected the analysis]
  - **Recommendation:** [How to handle in future]

---

## Access/Data Gotchas

Specific issues with data sources worth documenting:

### [Source Name] (e.g., CCD)

- **[Variable/Data Source]:** [Issue description]
  - **Example:** [Concrete example]
  - **Workaround:** [How to handle]

### [Source Name]

- **[Variable/Data Source]:** [Issue description]

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

## Stage 12 Consolidation & Post-Processing

### Step A: Consolidation

By Stage 12, LEARNINGS.md should already contain incremental entries from Stages 5-8. The orchestrator now consolidates:

1. **Review incremental entries** — Are there sections still empty? Reflect on whether signals were missed or if there genuinely were no learnings in that category.
2. **Expand quick-capture entries** — Entries that warrant more detail get expanded with context, examples, and recommendations.
3. **Deduplicate** — Multiple signals about the same issue get merged into one entry.
4. **Ensure minimum sections populated:** What Worked Well, What Didn't Work, Access/Data Gotchas.
5. **Flush any remaining signals** from STATE.md buffer.

This replaces the old "create from scratch at Stage 12" approach. Because entries were captured incrementally, consolidation is a review-and-polish task, not a reconstruction-from-memory task.

### Step B: System Update Action Plan

After consolidation, the orchestrator adds a final section to LEARNINGS.md:

```markdown
---

## System Update Action Plan

*Generated at project completion. Each item maps a learning to a specific
system file with a proposed change. This plan is NOT auto-executed — it
serves as a work queue for future system maintenance.*

### Priority Legend
- **P1 (High):** Prevents incorrect results in future analyses
- **P2 (Medium):** Improves efficiency or clarity
- **P3 (Low):** Nice-to-have improvement

### Action Items

| # | Learning | Target File | Change Type | Proposed Change | Priority |
|---|---------|-------------|-------------|-----------------|----------|
| 1 | [1-line learning summary] | `path/to/file.md` | [Add/Update/Clarify] | [Specific proposed change] | P1 |
| 2 | ... | ... | ... | ... | P2 |

### Grouped by Target

#### Skills (`.claude/skills/*/SKILL.md`)
- [ ] [Skill name]: [What to add/change] (from Learning #N)

#### Agents (`agents/*.md`)
- [ ] [Agent name]: [What to add/change] (from Learning #N)

#### Agent Reference (`agent_reference/*.md`)
- [ ] [File name]: [What to add/change] (from Learning #N)

#### Orchestrator (`CLAUDE.md`)
- [ ] [Section]: [What to add/change] (from Learning #N)

### Not Actionable (Context Only)
- [Learnings that are project-specific and don't generalize to system updates]
```

The orchestrator produces this by:
1. Reading each learning entry in the consolidated LEARNINGS.md
2. For each: determining if it generalizes beyond this project
3. If yes: identifying the specific target file(s) and drafting a concrete change description
4. If no: placing it in "Not Actionable" with brief reasoning
5. Assigning priority based on impact (P1 = correctness, P2 = efficiency, P3 = polish)

### Session Recovery (Protocol 6)

When resuming:
1. Read prior session's LEARNINGS.md
2. Note known issues to avoid
3. Reference documented workarounds

---

## Learning Categories Reference

### Category: Data Access Behavior

- Rate limiting patterns
- Variable naming inconsistencies
- File size inconsistencies or issues
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

*This is the primary format used during incremental capture (not just a convenience shortcut). Learning Signals from agents are expanded into quick-capture entries when flushed to LEARNINGS.md.*

For rapid capture during analysis, use this abbreviated format:

```markdown
## Quick Note: [timestamp]

**Category:** [Access/Data/Method/Perf/Process]
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
- Treat Stage 12 as the primary capture point (use incremental capture instead)

### Do Instead

- Capture in the moment
- Document both successes and failures
- Always explain the reason
- Reference existing docs, extend don't repeat
- Be specific about when insights apply
