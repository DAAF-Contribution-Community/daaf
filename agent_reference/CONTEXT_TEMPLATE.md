# Design Context Template

**Purpose:** Capture design decisions and ambiguity resolutions BEFORE planning. This document ensures downstream agents have guidance without re-asking questions.

**When to Use:** Between Stage 3 (Source Deep-Dive) and Stage 4 (Plan Creation), especially when:
- Multiple valid approaches exist
- Trade-offs need documentation
- User preferences affect methodology
- Ambiguities emerged during exploration

---

## Template

```markdown
# Design Context: [Project Title]

## Created
**Date:** YYYY-MM-DD
**Stage:** Pre-Planning (after Stage 3)

---

## Research Context

### Original Question
> [Verbatim user request]

### Refined Question
[Your interpretation as a clear, answerable research question]

### Scope Boundaries
| In Scope | Out of Scope |
|----------|--------------|
| [Include] | [Exclude] |
| [Include] | [Exclude] |

---

## Ambiguities Identified

*List ambiguities discovered during Stage 2-3 exploration*

### Ambiguity 1: [Title]
**Question:** [The unclear aspect]
**Options:**
1. [Option A with implications]
2. [Option B with implications]
3. [Option C with implications]

**Resolution:** [Which option, decided by whom]
**Rationale:** [Why this choice]

### Ambiguity 2: [Title]
[Repeat structure]

---

## Design Decisions

*Record each decision that affects downstream execution*

| Decision | Options Considered | Choice | Rationale | Decided By |
|----------|-------------------|--------|-----------|------------|
| Data source | CCD vs PSS | CCD | Public schools focus | User |
| Year range | 2018-2023 vs 2020-2023 | 2020-2023 | Avoid COVID transition | Agent |
| Poverty measure | FRPL vs MEPS | MEPS | CEP makes FRPL unreliable | Agent |
| Suppression handling | Exclude vs Aggregate | Aggregate to district | Preserves sample size | User |
| Geographic scope | National vs State | California only | User preference | User |

---

## Methodology Choices

### Data Source Selection
**Selected:** [Source name]
**Alternatives Considered:** [Other sources]
**Why Selected:** [Rationale]

### Unit of Analysis
**Selected:** [Schools | Districts | Colleges]
**Why:** [Rationale]

### Time Period
**Selected:** [Year range]
**Why:** [Rationale, including any data availability constraints]

### Key Variable Definitions
| Variable | Definition | Source | Notes |
|----------|------------|--------|-------|
| [var1] | [how measured] | [source] | [any caveats] |
| [var2] | [how measured] | [source] | [any caveats] |

---

## Constraints Discovered

*Constraints that limit what the analysis can do*

### Data Constraints
| Constraint | Source | Impact | Mitigation |
|------------|--------|--------|------------|
| MEPS available 2018-2022 only | Stage 3 | Limits recent years | Use 2022 as latest |
| Suppression in small schools | CCD skill | ~15% data loss | Document in limitations |

### Methodological Constraints
| Constraint | Why | Impact |
|------------|-----|--------|
| Cannot compare across states | Different assessments | State-specific analysis only |
| Cannot impute suppressed values | Statistical validity | Exclude suppressed records |

### QA Expectations & Tolerance

*Anticipated QA findings and acceptable thresholds for this analysis*

| Stage | QA Checkpoint | Expected Checks | Acceptable Threshold | Notes |
|-------|---------------|-----------------|----------------------|-------|
| 5 (Fetch) | QA1 | Schema, year coverage, ID uniqueness | No BLOCKERs | Standard validation |
| 6 (Clean) | QA2 | Coded values filtered, suppression rate | Suppression <50% | >30% triggers WARNING |
| 7 (Transform) | QA3 | Join cardinality, row preservation | <10% unexpected loss | Fan-out is BLOCKER |
| 8 (Viz) | QA4 | Figure exists, data source accurate | Figures readable | Visual sanity check |

**QA Tolerance Decisions:**

| Decision | Tolerance | Rationale |
|----------|-----------|-----------|
| Suppression rate | <50% (STOP), <30% (PASS), 30-50% (WARNING) | Standard Education Data Portal thresholds |
| Row loss in joins | <10% acceptable | Some schools won't match across sources |
| [Custom for analysis] | [threshold] | [rationale] |

---

## Trade-offs Accepted

*Explicit acknowledgment of what was sacrificed for what benefit*

| We Accepted | In Order To | Downside |
|-------------|-------------|----------|
| Older data (2022 vs 2023) | Use MEPS poverty measure | 1-year lag |
| State-only scope | Avoid cross-state comparability issues | Less generalizable |
| District-level aggregation | Reduce suppression | Lose school-level detail |

---

## Downstream Implications

*What this context means for later stages*

### For Stage 4 (Planning)
- Plan must specify [specific constraint]
- Transformation sequence must include [specific step]
- Risk register should include [specific risk]

### For Stage 5 (Data Retrieval)
- Query must include year filter for [years]
- Must fetch from [endpoint] with [filters]

### For Stage 6 (Context Application)
- Use MEPS poverty, not FRPL
- Aggregate to district if school-level suppression > 30%

### For Stage 7 (Transformation)
- Join CCD + MEPS on ncessch (1:1 expected)
- Calculate [specific derived variable]

### For Stage 11 (Report)
- Limitations must note [specific limitation]
- Cannot claim [specific invalid claim]

### For QA Substages (5-QA through 8-QA)
- QA1 should verify [specific schema or coverage expectation]
- QA2 should check suppression rate against [threshold] tolerance
- QA3 should validate [specific join cardinality or transformation]
- QA4 should confirm [specific figure requirements]
- [Any analysis-specific QA focus areas]

---

## Open Questions

*Questions that couldn't be resolved and need user input*

| Question | Options | Impact of Deferring |
|----------|---------|-------------------|
| [Question] | [Options] | [What happens if we proceed without answer] |

---

## Approval

- [ ] User reviewed ambiguities and decisions
- [ ] User approved methodology choices
- [ ] Open questions resolved or deferred with acknowledgment

**Approved by:** [User | Agent if within autonomous scope]
**Date:** YYYY-MM-DD

---

## Change Log

| Date | Change | Reason |
|------|--------|--------|
| YYYY-MM-DD | Initial creation | Pre-planning context |
```

---

## Usage Instructions

### When to Create

Create CONTEXT.md when:
1. Stage 2-3 exploration reveals ambiguities
2. Multiple valid approaches exist
3. User input is needed before planning
4. Trade-offs need explicit documentation

### How to Create

1. **Collect ambiguities** from Stage 2-3 findings
2. **Present options** to user (or resolve autonomously if within scope)
3. **Document decisions** with rationale
4. **Identify constraints** that affect downstream work
5. **Note implications** for each future stage

### How Downstream Agents Use It

Include relevant CONTEXT.md sections when invoking subagents:

```python
Task({
    description: "Stage 5: Fetch data",
    prompt: """
    **DESIGN CONTEXT:**
    - Data source: MEPS (not FRPL) per CONTEXT.md decision
    - Years: 2020-2022 (MEPS availability constraint)
    - Scope: California only (user preference)

    [Task specification]
    """,
    subagent_type: "general-purpose"
})
```

### Integration with Plan

CONTEXT.md feeds into Plan creation:
- Decisions → Decisions Log
- Constraints → Risk Register
- Methodology → Methodology Specification
- Implications → Task specifications

---

## Example

```markdown
# Design Context: Example School Poverty Analysis

## Created
**Date:** YYYY-MM-DD
**Stage:** Pre-Planning (after Stage 3)

## Research Context

### Original Question
> "How does school poverty relate to enrollment in California?"

### Refined Question
What is the relationship between Model Estimates of Poverty (MEPS) and school enrollment patterns in California public schools?

### Scope Boundaries
| In Scope | Out of Scope |
|----------|--------------|
| California public schools | Other states |
| K-12 schools | Pre-K, postsecondary |
| 2020-2022 academic years | Earlier years |
| MEPS poverty measure | FRPL-based poverty |

## Ambiguities Identified

### Ambiguity 1: Poverty Measure
**Question:** Should we use FRPL percentage or MEPS poverty rate?
**Options:**
1. FRPL percentage (traditional, widely available)
2. MEPS poverty rate (accounts for CEP, more accurate)

**Resolution:** MEPS
**Rationale:** CEP participation makes FRPL unreliable; MEPS provides consistent cross-school comparison

### Ambiguity 2: Handling Small Schools
**Question:** How to handle schools with <50 students where suppression is common?
**Options:**
1. Exclude small schools entirely
2. Aggregate to district level
3. Keep with suppression caveat

**Resolution:** Option 2 (aggregate to district) if suppression >30% at school level
**Rationale:** Preserves more data while avoiding false precision

## Design Decisions

| Decision | Options Considered | Choice | Rationale | Decided By |
|----------|-------------------|--------|-----------|------------|
| Poverty measure | FRPL vs MEPS | MEPS | CEP unreliability | Agent |
| Year range | 2018-2023 vs 2020-2022 | 2020-2022 | MEPS availability | Data constraint |
| Geographic scope | National vs CA | California | User request | User |
| Small school handling | Exclude vs Aggregate | Aggregate if >30% supp | Balance coverage vs accuracy | Agent |

## Constraints Discovered

### Data Constraints
| Constraint | Source | Impact | Mitigation |
|------------|--------|--------|------------|
| MEPS only through 2022 | education-data-source-meps | No 2023 data | Use 2022 as latest |
| ~15% suppression in small schools | CCD skill | Missing poverty data | Aggregate to district |

## Downstream Implications

### For Stage 5 (Data Retrieval)
- Fetch CCD schools: fips=6, years=2020-2022
- Fetch MEPS: years=2020-2022

### For Stage 6 (Context Application)
- Use MEPS `pct_poverty` not CCD `free_reduced_lunch`
- Check suppression rate; if >30%, aggregate to district

### For Stage 11 (Report)
- Limitations: MEPS methodology, 2022 latest year
- Cannot compare to other states (different measures)

### For QA Substages (5-QA through 8-QA)
| Stage | QA Checkpoint | Expected Checks | Acceptable Threshold |
|-------|---------------|-----------------|---------------------|
| 5-QA | QA1 | Schema validation, NCESSCH uniqueness | 100% unique NCESSCHs |
| 6-QA | QA2 | MEPS poverty used (not FRPL), suppression handled | Suppression rate <30% |
| 7-QA | QA3 | Join cardinality 1:1, no unexpected NAs | >95% match rate |
| 8-QA | QA4 | Figures reference correct data file | All figure paths valid |

**QA Tolerance Decisions:**
- Accept WARNING for up to 5% unmatched schools in join
- BLOCKER if join drops >20% of schools

## Approval
- [x] User reviewed ambiguities and decisions
- [x] User approved methodology choices
- [x] Open questions resolved

**Approved by:** User
**Date:** YYYY-MM-DD
```
