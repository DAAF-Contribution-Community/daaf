# Best Practices

> **Prerequisites:** [README](../README.md) and [Understanding DAAF](02_understanding_daaf.md) — you should understand the engagement modes and the overall workflow before reading this guide.

Practical wisdom for getting the most out of DAAF while maintaining research quality. This guide helps you write effective prompts, review outputs critically, and understand your role in the human-AI research partnership.

---

## Writing Effective Prompts

<!-- MIGRATE: README "Getting Started Tips" — "What makes a good request?" section with examples -->
<!-- NEW: Expand with more examples and a framework for thinking about prompt specificity -->

How to frame your research questions so DAAF can produce the best results.

### What Makes a Good Request

**Be specific** — "Analyze California high schools" is better than "analyze schools." The key dimensions to include:
- **Geography**: Which state, district, or national scope?
- **Time period**: Which years?
- **Data granularity**: Schools, districts, or colleges?
- **Analysis focus**: What relationship, trend, or comparison?

### Good vs. Less-Good Examples

<!-- MIGRATE: README "Getting Started Tips" — the good/less-good examples -->
<!-- MIGRATE: README "Example Requests" — Full Pipeline, Discovery, Targeted Assist, Revision examples -->

✅ **Good:** "Analyze school poverty rates in Texas from 2018-2022, breaking down trends by district type"
- Specific geography, time period, and analysis dimension

✅ **Good:** "What poverty measures exist for schools and which is most reliable?"
- Clear question, open to assistant expertise

❌ **Less Good:** "Tell me about schools"
- Too broad; assistant will ask clarifying questions

❌ **Less Good:** "Compare state test scores between California and Texas"
- Methodologically invalid (state tests aren't comparable); assistant will block and explain

**Full Pipeline examples:**
- "Analyze graduation rates by state for the past 5 years"
- "Research the relationship between school poverty and enrollment in California"
- "Create an analysis of college endowment growth trends"

**Discovery examples:**
- "What data is available on school discipline?"
- "Is it feasible to analyze teacher salaries by district?"
- "What poverty measures exist for schools?"

**Targeted Assist examples:**
- "What does the enrollment variable mean in CCD data?"
- "What are the coded values for charter school status?"
- "How is the graduation rate calculated in IPEDS?"

**Revision examples:**
- "Update the school poverty analysis to include 2023 data"
- "Fix the enrollment filter in my Texas schools analysis"
- "Add a breakdown by district type to the existing analysis"

### The Specificity Spectrum

<!-- NEW: Framework for understanding how specific your prompt needs to be -->

How prompt specificity affects DAAF's behavior: too vague triggers clarifying questions, too prescriptive may constrain useful exploration, and the sweet spot gives clear scope with room for expertise.

---

## Choosing the Right Engagement Mode

<!-- NEW: Practical decision guide building on the mode descriptions in 02 -->

How to choose between Full Pipeline, Discovery, Targeted Assist, and Revision based on what you actually need.

### When Discovery Is Better Than Full Pipeline

Situations where exploration is more valuable than committing to a full analysis.

### When to Start Targeted and Escalate

How a quick lookup can inform whether a larger analysis is worthwhile.

### Recognizing When You Need Revision Mode

How to reference previous work and what kinds of changes are possible.

---

## Reviewing the Plan Before Execution

<!-- NEW: Practical guidance for the Plan review gate — what to look for, what to push back on -->

The Plan is your last chance to shape the analysis before data is touched. Here's what to check.

### Key Sections to Review

What the research question, observable truths, transformation sequence, and risk register should contain.

### Red Flags to Watch For

Signs that the Plan may lead to problems: vague methodology, missing validation criteria, overly ambitious scope.

### How to Request Changes

How to ask for Plan revisions — what's easy to change, what requires rethinking.

---

## Interpreting Validation Checkpoints and STOP Conditions

<!-- MIGRATE: README "Built-in Safeguards" table (partial) -->
<!-- NEW: Practical interpretation guide — what each checkpoint means for the user -->

What it means when DAAF reports CP1 PASSED, what a STOP condition looks like, and what you should do in each case.

### Understanding Checkpoint Results (CP1-CP4)

What each checkpoint validates, what PASSED/WARNING/FAILED means, and when you need to act.

### When DAAF Stops and Asks for Guidance

What STOP conditions look like, why they happen, and how to evaluate the options DAAF presents.

### QA Findings: BLOCKER vs. WARNING vs. INFO

How the code reviewer's findings are classified and what they mean for your analysis.

---

## Reviewing Notebooks, Reports, and Script Logs

<!-- MIGRATE: README "Understanding Generated Notebooks" (partial — the code example and explanation) -->
<!-- NEW: Practical review guidance for each artifact type -->

How to read and critically evaluate each artifact DAAF produces.

### Reading the Notebook

What to look at in the notebook: script code cells, execution log accordions, validation results.

### Reading the Report

What the report contains, how findings relate to the notebook, and how to verify key claims.

### Reading Script Execution Logs

How to find and interpret the embedded execution logs in script files, including versioned scripts (`_a`, `_b` suffixes).

---

## Human Oversight Responsibilities

<!-- MIGRATE: README "Important Caveats" — the risk/mitigation/responsibility table -->
<!-- MIGRATE: README "Human Oversight & Best Practices" section -->
<!-- NEW: Frame as a "trust-but-verify" partnership model -->

Your role in the human-AI research partnership and what you're responsible for verifying.

### The Trust-but-Verify Framework

The assistant includes several safeguards to support quality:

| Safeguard | Description |
|-----------|-------------|
| **Iteration Protocol** | Every transformation follows 5 steps: DESCRIBE → CODE → EXECUTE → VALIDATE → DECIDE |
| **Validation Checkpoints** | Four required checkpoints (CP1-CP4) verify data quality at fetch, cleaning, transformation, and output stages |
| **Secondary QA Review** | Independent code-reviewer agent validates every script with adversarial analysis |
| **Batch Size Limits** | Maximum 1-2 transformations per iteration to prevent error accumulation |
| **STOP Conditions** | Automatic escalation when data quality thresholds are breached (e.g., >50% suppression, validation failures) |
| **Plan Documentation** | Every analysis has a Plan document capturing all decisions and their rationale |
| **Transformation Sequence** | Pre-planned list of transformations with expected outcomes, validation criteria, and join cardinality |
| **Version Control** | All files are versioned; no in-place modifications |
| **Source Citations** | Proper citations generated for all data sources |

### What DAAF Validates Automatically

The safeguards that run without your involvement (checkpoints, QA, iteration protocol).

### What Requires Your Judgment

Methodology decisions, finding interpretation, policy implications — things AI cannot validate.

---

## When and How to Request Revisions

<!-- MIGRATE: README "Returning to Previous Work" section (partial) -->
<!-- NEW: Practical guidance on framing revision requests -->

How to modify, extend, or fix a previous analysis.

### Types of Revisions

Adding data years, changing geographic scope, fixing methodology, extending analysis dimensions.

### Framing Revision Requests

How to reference the original work and specify what should change.

### What Gets a New Version vs. What Gets a New Project

When revisions create new version files vs. when you should start fresh.

---

## Appropriate vs. Inappropriate Use Cases

<!-- MIGRATE: README "Important Caveats" — "Appropriate Use Cases" section (the checkmark/X lists) -->
<!-- MIGRATE: README "What Cannot Be Compared" section -->
<!-- NEW: Expand with more nuanced guidance about proof-of-concept limitations -->

Understanding the boundaries of what DAAF can and should be used for.

### Appropriate Uses

Learning, exploratory analysis with oversight, demonstrating AI-assisted research patterns, educational purposes.

### Uses Requiring Extensive Additional Validation

Policy analysis, publication-ready research — possible but requires significant human verification beyond what DAAF provides.

### Never Appropriate

High-stakes decisions based solely on AI outputs, cross-state assessment comparisons, analysis with >50% suppression.

**What Cannot Be Compared:**
Some analyses are methodologically invalid regardless of data availability. The assistant will block:

- **Cross-state assessment comparisons** — State tests are not comparable
- **Analyses with >50% suppression** — Insufficient data for valid conclusions

---

## Managing Long Analyses and Session Recovery

<!-- NEW: Practical guidance for multi-session analyses -->

What happens when an analysis takes longer than a single session and how to resume work.

### How Session State is Preserved

What STATE.md tracks and how it enables resumption.

### Resuming a Previous Session

How to paste the restart prompt to continue where you left off.

### When to Start a New Session vs. Continue

Signs that context quality is degrading and a fresh session would produce better results.

---

## Next Steps

- **[Understanding DAAF](02_understanding_daaf.md)** — If you haven't read the conceptual guide yet
- **[FAQ: Technical](06_faq_technical.md)** — Troubleshooting and configuration questions
- **[FAQ: Philosophy](07_faq_philosophy.md)** — Why DAAF works the way it does
