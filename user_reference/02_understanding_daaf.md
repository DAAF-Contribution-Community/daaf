# 02. Understanding DAAF

This is the conceptual guide that turns an installer into a confident user. It expands on the README's brief overview into a thorough walkthrough of how DAAF works, what it produces, and how to think about AI-assisted research analysis. Read this before your first analysis to understand what's happening under the hood.

---

## Documentation Table of Contents

- [**00. README**](../.) — **\[Prerequisite\]** Vision and purpose, what DAAF does and does not do, core design philosophy, acknowledgments
- [**01. Installation & Quick Start**](01_installation_and_quickstart.md) — **\[Prerequisite\]** Get started! Installation prerequisites, step-by-step 5-minute setup, day-to-day usage, and troubleshooting
- **02. Understanding DAAF** — **\[This document\]** Learn to work with DAAF for the first time: what to expect, engagement modes explained, your first analysis walkthrough
- [**03. Best Practices**](03_best_practices.md) — Tips for working with Claude Code, writing effective prompts, ensuring quality and rigor with DAAF, reviewing outputs, and managing context
- [**04. Extending DAAF**](04_extending_daaf.md) — How to add new data source skills, analytical tools and methodologies, and creating your own additional specialized agents
- [**05. Contributing**](05_contributing.md) — Get involved in developing DAAF! How to file issues via GitHub, support expanding the capabilities of the framework, contribute to educational tutorials and how-to's, and more!
- [**06. FAQ: Technical**](06_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, design rationale, authentication errors, and other common errors
- [**07. FAQ: Philosophy**](07_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**Back to main**](../.)

---

## The Four Engagement Modes

<!-- MIGRATE: README section "Engagement Modes" (the table and descriptions) -->
<!-- Expand each mode with more detail, expected duration, and when to switch between modes -->

DAAF classifies every request into one of four modes. Understanding these modes helps you frame your questions effectively.

### Full Pipeline Mode

<!-- MIGRATE: README "Engagement Modes" table row for Full Pipeline + "What to Expect" section -->

For a Full Pipeline analysis, the assistant follows a structured workflow:

**Phase 1: Discovery & Scoping**
- Classifies your request and confirms scope
- Explores available data sources and variables
- Documents limitations and caveats

**Phase 2: Planning**
- Creates a Plan document capturing all methodology decisions
- Specifies data queries, cleaning approach, and output format

**Phase 3: Data Acquisition & Preparation**
- Fetches data from the configured data access mirrors/sources
- Validates data quality and handles coded values
- Documents suppression rates and missing data

**Phase 4: Analysis & Notebook Development**
- Sub-Stage 7.1: Performs exploratory data analysis (EDA) first, without transformations
- Sub-Stage 7.2: Executes transformations **one at a time** following the Iteration Protocol
- Sub-Stage 7.3: Final CP3 validation after all transformations complete
- Stage 8: Creates visualizations after all transformations are validated
- Stage 9: Assembles a marimo notebook displaying pre-executed scripts with their embedded validation logs

**Phase 5: Synthesis & Delivery**
- Generates a stakeholder report
- Completes final review against original request
- Delivers all artifacts with file paths

### Discovery Mode

<!-- MIGRATE: README "Engagement Modes" table row for Discovery -->

When to use it, what it produces (findings summary, no code), and how it can escalate to Full Pipeline if the data looks promising.

### Targeted Assist Mode

<!-- MIGRATE: README "Engagement Modes" table row for Targeted Assist -->

When to use it (quick lookups, variable definitions), what you get back (direct answer), and its boundaries.

### Revision Mode

<!-- MIGRATE: README "Engagement Modes" table row for Revision + "Returning to Previous Work" section -->
<!-- MIGRATE: README "Returning to Previous Work" — version system explanation and folder structure -->

When to use it, how to reference previous work, and how the version system preserves all prior versions.

To revise or update a previous analysis:

1. Reference the project by keywords or date (e.g., "the Texas poverty analysis" or "the 2026-01-15 enrollment study")
2. Describe what needs to change
3. The assistant will locate your project, read the existing Plan, and create a new version

**Version System:** All versions are preserved in the same project folder. Prior versions are never modified or overwritten. Revisions use date suffixes: original `2026-01-24`, revision 1 `2026-01-24a`, revision 2 `2026-01-24b`, etc.

---

## The Mental Model: Orchestrator, Agents, Skills, Validation

<!-- MIGRATE: README section "Architecture Overview" — "Why Multiple Agents?" + agent table -->
<!-- Expand into a narrative explanation of how the pieces interact -->

A deeper explanation of DAAF's multi-agent architecture and how it maintains quality throughout an analysis.

### The Orchestrator

<!-- NEW: Explain the orchestrator's role as coordinator — not present in README as a separate concept -->

What the orchestrator does: maintains context, delegates to specialized agents, enforces gates, and reports progress to you.

### Specialized Agents (12)

<!-- MIGRATE: README "Agent Ecosystem" table -->

What each agent does and why decomposing work into specialized roles improves quality. The 12 agents include: research-executor (data tasks), code-reviewer (QA), data-planner (plans), plan-checker (plan validation), data-verifier (final verification), source-researcher (data source deep-dives), research-synthesizer (consolidating findings), debugger (error diagnosis), notebook-assembler (script compilation), report-writer (stakeholder report generation), integration-checker (component wiring), and data-ingest (new dataset profiling).

### Skills as Knowledge Modules (24)

<!-- MIGRATE: README "Skills as Knowledge Modules" paragraph -->

How skills provide domain knowledge (data source documentation, tool expertise) without behavioral protocols.

### Dual-Layer Validation

<!-- MIGRATE: README "Dual-Layer Validation" section (CP1-CP4 and QA1-QA4) -->

How primary validation (embedded in scripts) and secondary QA (independent code reviewer) work together to catch errors.

---

## What a Full Pipeline Analysis Looks Like

<!-- MIGRATE: README "What to Expect" section (Phase 1-5 breakdown) -->
<!-- Expand each phase with more detail about what happens and what you'll see -->

A walkthrough of the 5 phases and 12 stages, from your initial question to final delivery.

### Phase 1: Discovery & Scoping (Stages 1-3)

What happens when DAAF explores available data and identifies limitations.

### Phase 2: Planning (Stage 4)

How the Plan document captures methodology decisions before any data is touched.

### Phase 3: Data Acquisition & Preparation (Stages 5-6)

How data is fetched, validated, cleaned, and prepared for analysis.

### Phase 4: Analysis & Notebook Development (Stages 7-10)

How transformations are executed one at a time with validation, visualizations are created, the notebook is assembled, and QA findings are aggregated.

### Phase 5: Synthesis & Delivery (Stages 11-12)

How the report is generated and final verification ensures everything aligns with the original request.

---

## Anatomy of a Completed Analysis

<!-- MIGRATE: README "Project Folder Structure" section (the directory tree) -->
<!-- NEW: Expand with explanations of what each file IS and how to read/use it -->

What you'll find in a completed project folder and how to interpret each artifact.

### The Plan Document

What the Plan contains (research question, methodology, transformation sequence) and why it matters.

### The Scripts Directory

<!-- MIGRATE: README discussion of scripts as primary artifacts -->

**Scripts are the PRIMARY execution artifacts**, not afterthoughts. Each script contains embedded execution logs showing exactly what happened when it ran.

When a script fails, it gets versioned:
- Original `01_task.py` keeps its failed output (audit trail)
- Revision `01_task_a.py` contains fixes + its own output
- Further revisions use `_b.py`, `_c.py`, etc.
- The marimo notebook only includes the final successful version

### The Marimo Notebook

<!-- MIGRATE: README section "Understanding Generated Notebooks" -->

Marimo notebooks **assemble pre-executed scripts** rather than containing new analysis code. When you receive a notebook, you'll see:

- **Section header cells** identifying which script stage is being shown
- **Code cells** containing the LITERAL code from the script files (can be re-run interactively)
- **Execution log accordions** showing exactly what happened when the script ran (duration, exit code, pre/post state, validation results)

**What you won't see:**
- New analysis code written directly in the notebook
- Transformations without embedded execution logs
- Scripts executed interactively without file capture

The notebook is a **walkthrough tool** for reviewing the validated analysis, not the source of the analysis itself. See `scripts/` for the primary execution artifacts.

### The Report

What the stakeholder report contains and how it differs from the notebook.

### Data Files (Raw and Processed)

What's in `data/raw/` vs. `data/processed/` and why everything is stored as parquet.

### Output Figures

Where visualizations are saved and how they're referenced in the report.

---

## Available Data Sources

<!-- MIGRATE: README section "Available Data Sources" (all three tables: K-12, Postsecondary, Supporting) -->

Overview of the 14+ education data source skills currently available.

### K-12 Data Sources

| Source | Description | Key Variables |
|--------|-------------|---------------|
| **CCD** | Common Core of Data — public school/district directory, enrollment, staffing, finance | Enrollment, FRL eligibility, school type, staffing counts |
| **CRDC** | Civil Rights Data Collection — discipline, course access, equity indicators | Suspensions, expulsions, AP enrollment, harassment |
| **EDFacts** | State assessment results, graduation rates, accountability | Proficiency rates, ACGR graduation rates |
| **MEPS** | Model Estimates of Poverty in Schools — school-level poverty | Poverty rate at 100% FPL |
| **SAIPE** | Small Area Income and Poverty Estimates — district-level poverty | Children in poverty, median income |

### Postsecondary Data Sources

| Source | Description | Key Variables |
|--------|-------------|---------------|
| **IPEDS** | Integrated Postsecondary Education Data System — comprehensive college data | Enrollment, graduation rates, finance, staffing |
| **College Scorecard** | Post-college outcomes from Treasury/IRS data | Earnings, debt, repayment rates |
| **PSEO** | Postsecondary Employment Outcomes — graduate employment | Earnings by field, employment by industry |
| **FSA** | Federal Student Aid — Title IV program data | Pell grants, loans, default rates |
| **NACUBO** | Endowment study data | Endowment size, investment returns |
| **EADA** | Equity in Athletics — college sports data | Participation, coaching, expenses by gender |
| **Campus Safety** | Clery Act crime statistics | Campus crime, fire safety |

### Supporting Data Sources

| Source | Description |
|--------|-------------|
| **NHGIS** | Census geography and demographic data for school communities |
| **NCCS** | Nonprofit organization data for private institutions |

---

## Your First Full Analysis: A Guided Walkthrough

<!-- NEW: Step-by-step narrative of what to type and what to expect -->

A hands-on walkthrough of a simple analysis from start to finish, showing what you'll type, what DAAF will ask, and what outputs you'll receive.

### Step 1: Start with Discovery

Example: asking what poverty data is available for schools.

### Step 2: Review Discovery Findings

What DAAF reports back and how to decide whether to proceed.

### Step 3: Request a Full Pipeline Analysis

How to frame a specific analysis request based on discovery findings.

### Step 4: Review the Plan

What to look for in the Plan document before execution begins.

### Step 5: Monitor Execution

What progress updates look like and when DAAF will ask for your input.

### Step 6: Review Deliverables

How to open and interpret the notebook, report, and data files.

## Easing in with progressively more advanced queries

You can use DAAF in a couple of different ways, as mentioned above. Given that the main premise of this project is that it is surprisingly robust, I'd recommend starting small and asking it questions you largely already know the answer to, to assess its knowledge and way of responding. For example:
1. \[Quick Ask\] Ask Claude to explain to you a single dataset or variable you're already familiar with -- see what it says, feeling free to ask follow-ups or dig into certain details.
2. \[Single Variable Analysis\]Ask Claude to help you analyze a single varible for a simple subset from a single dataset you're already familiar with. This will probably kick off a full analysis, but a very simple and approachable one.
3. \[Simple Correlational Longitudinal Analysis\] Ask Claude to help you understand the relationship between two variables of interest for \[Colleges/High Schools/School Districts\]. Ask it to unpack that relationship over time, as well.
4. \[Multivariate Analysis\] Then get more abstract, complex, or high-level. For example, ask Claude to help you better understand the nuances of the relationships between college selectivity, student academic preparedness, graduation rates, and student socioeconomic backgrounds. Or ask it how you might better understand what linkages may exist between school-level resources, student socioeconomic status, and access to advanced coursework. You can even ask it what you should ask it, based on the data it has available: "I'm trying to get started with the DAAF system. I'm trying to think of a few moderately complex, abstract research questions I could ask you to conduct data analysis on, based on the data current available to you. Do you have a few examples you can surface related to [Topic A/B/C]?"
5. \[Replication Exercises\] I am actively trying to assess DAAF's performance by replicating studies conducted by the [Urban Institute Learning Curve series](https://www.urban.org/projects/learning-curve) which leverage the same Education Data Portal datasets DAAF currently has access to -- especially as they have [open-source code available](https://github.com/UrbanInstitute/The-Learning-Curve/tree/main) for direct comparison afterwards. Run some tests of your own, and please do let me know what you find!

---

## Where Things Live in the Repository

<!-- MIGRATE: README section "Repository Structure" (the directory table) -->
<!-- NEW: Add context about what each directory means for a user vs. a contributor -->

| Directory | Purpose |
|-----------|---------|
| `research/` | Analysis projects produced by DAAF (notebooks, data, reports) |
| `user_reference/` | User documentation (you're reading it) |
| `agents/` | Specialized agent protocols that dictate certain task workflows |
| `agent_reference/` | Detailed workflow documentation, templates, and reference tables |
| `.claude/skills/` | Skill definitions that provide agents with specific knowledge or toolsets |

Each analysis creates a self-contained project folder:

```
research/YYYY-MM-DD [Title]/
├── YYYY-MM-DD [Title] Plan.md        # Analysis plan and decisions
├── YYYY-MM-DD [Title].py             # Marimo WALKTHROUGH (assembles scripts)
├── YYYY-MM-DD [Title] Report.md      # Stakeholder SUMMARY (separate artifact)
├── scripts/                          # *** PRIMARY EXECUTION ARTIFACTS ***
│   │                                 # Each script has embedded execution log
│   ├── stage5_fetch/                 # Data retrieval scripts
│   ├── stage6_clean/                 # Context application scripts
│   ├── stage7_transform/             # Transformation scripts (may have _a, _b versions)
│   ├── stage8_viz/                   # Visualization scripts
│   └── debug/                        # Debugger diagnostic scripts
├── data/
│   ├── raw/                          # Original data access responses (.parquet)
│   └── processed/                    # Cleaned data (.parquet)
├── output/
│   └── figures/                      # Exported visualizations
```

**Key insight:** Scripts are the PRIMARY execution artifacts, not afterthoughts. The marimo notebook assembles them into an interactive walkthrough; it doesn't contain separate, new code.

---

## Recommended Next Steps

- [**03. Best Practices**](03_best_practices.md) — Tips for working with Claude Code, writing effective prompts, ensuring quality and rigor with DAAF, reviewing outputs, and managing context
- [**06. FAQ: Technical**](06_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, design rationale, authentication errors, and other common errors
- [**07. FAQ: Philosophy**](07_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**Back to main**](../.)
