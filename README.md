# DAAF: Data Analyst Augmentation Framework

(TODO: README is still WIP) An open-source, extensible agentic workflow that allows skilled researchers to rapidly scale their expertise and accelerate data analysis by as much as 5-10x -- without sacrificing rigor or reproducibility. This project is a core proof-of-concept demonstrating how AI can assist with rigorous, reproducible data analysis given the right frameworks, instructions, and capabilities. Currently demonstrated with U.S. education data from the Urban Institute Education Data Portal, and extensible to new data domains, methodologies, and domains through additional Skills and data ingestion processes.

---

## Documentation Table of Contents

- **00. README** — **\[This document\]** Vision and purpose, what DAAF does and does not do, core design philosophy, acknowledgments
- [**01. Installation & Quick Start**](user_reference/01_installation_and_quickstart.md) — Get started! Installation prerequisites, step-by-step 5-minute setup, day-to-day usage, and troubleshooting
- [**02. Understanding DAAF**](user_reference/02_understanding_daaf.md) — Learn to work with DAAF for the first time: what to expect, engagement modes explained, your first analysis walkthrough
- [**03. Best Practices**](user_reference/03_best_practices.md) — Tips for working with Claude Code, writing effective prompts, ensuring quality and rigor with DAAF, reviewing outputs, and managing context
- [**04. Extending DAAF**](user_reference/04_extending_daaf.md) — How to add new data source skills, analytical tools and methodologies, and creating your own additional specialized agents
- [**05. Contributing**](user_reference/05_contributing.md) — Get involved in developing DAAF! How to file issues via GitHub, support expanding the capabilities of the framework, contribute to educational tutorials and how-to's, and more!
- [**06. FAQ: Technical**](user_reference/06_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, design rationale, authentication errors, and other common errors
- [**07. FAQ: Philosophy**](user_reference/07_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more

---

## Vision & Purpose

This project explores a critical question: **Can an AI/LLM meaningfully assist with complex research tasks while maintaining the rigor that social science demands?**

Our answer: Yes, but only with extensive guardrails, self-monitoring and self-revision protocols, and human oversight at every critical juncture.

### What This Project Demonstrates

1. **Multi-Agent Architecture for Quality**: Rather than relying on a single AI to handle everything, we decompose research into specialized agents—planners, executors, reviewers, verifiers—each with focused responsibilities and explicit protocols.

2. **Iterative Validation**: Every data transformation is validated immediately. Errors are caught at the transformation where they occur, not downstream.

3. **Auditability by Design**: Every script includes embedded execution logs. Every decision is documented. Any human reviewer can trace exactly what happened and why.

4. **Human-in-the-Loop**: The system stops and escalates at decision points. Plans require approval. Quality gates require human verification.

### Why Education Data as the Demonstration Domain?

DAAF is designed to be domain-extensible — new data sources can be integrated by authoring Skills (see the `skill-authoring` skill) and profiling datasets (see the `data-ingest` agent). We chose the [Urban Institute Education Data Portal](https://educationdata.urban.org/) as our initial demonstration domain because it offers:

- High-quality, well-documented public data
- Real policy relevance (K-12 schools, colleges, outcomes)
- Sufficient complexity to stress-test the system (multiple sources, coded values, suppression rules, cross-state comparability issues)

The architecture, agents, validation protocols, and workflow stages are domain-agnostic — only the Skills are domain-specific.

---

## Important Caveats

**This is a proof-of-concept, not a production system.**

### Hallucination Risk

Large language models can generate plausible-sounding but incorrect outputs. This system includes multiple layers of validation specifically to catch such errors, but **no automated system can guarantee correctness**.

**Human review of all outputs is essential.**

<!-- TODO: By deciding to use this repository... The maintainers of this repository take absolutely no responsibility for any errors produced by this system; any mistakes not caught are your own -->

### What This Means in Practice

| Risk | Mitigation | Human Responsibility |
|------|------------|---------------------|
| Incorrect methodology | Plan review before execution | Verify approach is sound |
| Data misinterpretation | Extensive validation checkpoints | Review validation reports |
| Wrong conclusions | Final verification stage | Critically evaluate findings |
| Hallucinated statistics | All code produces auditable outputs | Cross-check key numbers |

### Appropriate Use Cases

✅ **Appropriate:**
- Learning how AI can assist research workflows
- Accelerating exploratory data analysis with human oversight
- Demonstrating multi-agent quality assurance patterns
- Educational purposes and research into AI assistance

❌ **Not Appropriate (without extensive additional validation):**
- Policy decisions without human expert review
- Publication-ready analysis without methodological verification
- High-stakes decisions based solely on AI outputs

---

## What It Does

Ask research questions about your domain of interest. Get documented, reproducible analyses with full methodology and stakeholder-ready reports. The system currently ships with 14+ education data source Skills covering U.S. K-12 schools, districts, and colleges — and can be extended to new domains.

**Example:**

> "Analyze school poverty rates in Texas over the past 5 years"

The assistant will:

1. Identify the right data sources (MEPS for poverty, CCD for school info)
2. Create a research plan documenting methodology decisions
3. Fetch and validate the data with quality checks
4. Generate a marimo notebook with interactive analysis
5. Produce a stakeholder report with findings and limitations

Every analysis includes proper data citations, documented caveats, and validation at each step.

---

## Core Philosophy: Rigorous, Iterative Validation

This assistant is built on a principle of **"validate early, validate often"** to ensure research quality and reproducibility.

### The Iteration Protocol

Unlike traditional analyses where code is written in large batches and tested at the end, this assistant follows a mandatory **Iteration Protocol** for every data transformation:

1. **DESCRIBE** — State what will be done and the expected outcome
2. **CODE** — Write the transformation to a **script file first** (not executed yet)
3. **EXECUTE** — Run as a single Bash call: `bash {PROJECT_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/.../script.py` (automatically captures output and appends log)
4. **VALIDATE** — Compare pre/post state, check invariants
5. **DECIDE** — PASSED → proceed to next | FAILED → create versioned copy and fix

This protocol ensures errors are caught at the transformation where they occur, not downstream.

### File-First Execution

**All analysis code is written to script files before execution.** This ensures:
- **Reproducibility:** Anyone can re-run `python script.py` to reproduce results
- **Auditability:** Each script file contains embedded execution logs showing exactly what happened
- **Version History:** Failed scripts get `_a`, `_b`, `_c` suffixes—the original with its failed output is preserved

The marimo notebook **LITERALLY COPIES** successful script file contents into cells for review. It does NOT contain new analysis code, dashboards, or interactive widgets—just verbatim script code.

### How It Works in Practice

**Small, Discrete Increments** — Data transformations are performed one at a time (max 1-2 operations per cycle), validated before proceeding to the next transformation

**Script-Based Validation** — Every transformation is written to a script file first, executed via Bash, and the output (including validation results) is appended to the script as comments. The marimo notebook then COPIES these validated scripts verbatim into cells (no new code).

**Validation Checkpoints** — Four required checkpoints (CP1-CP4) verify data quality at fetch, cleaning, transformation, and output stages

### What This Means for You

**You get more reliable analysis:**
- Errors are caught immediately, not after hours of computation
- Every step is verified before the next one begins
- Data quality issues are flagged automatically
- Full audit trail of all transformations

**You maintain control:**
- Review validation reports at key milestones
- Approve methodology before execution
- Understand exactly what changed at each step

**Example of the difference:**

| Traditional Approach | This Assistant's Approach |
|---------------------|---------------------------|
| Write 10 transformations | Execute transformation #1 |
| Run all code | ✅ Validate: 100K→50K rows, all CA schools |
| Debug errors | Execute transformation #2 |
| Re-run everything | ✅ Validate: No negative enrollments |
| Hope it worked | Execute transformation #3... |

This iterative validation means **you spend less time debugging and more time interpreting results**, because the data pipeline is verified at every step.

<!-- TODO: Consider whether the full comparison table above is needed in the README or if a shorter version would work better here, with the detailed version in 02_understanding_daaf.md -->

---

## How to Use This Assistant

### Engagement Modes

The assistant supports four modes based on your needs:

| Mode | When to Use | What You Get |
|------|-------------|--------------|
| **Full Pipeline** | Need a complete analysis with report | Plan + Notebook + Report |
| **Discovery** | Exploring what data exists or feasibility | Findings summary (no code) |
| **Targeted Assist** | Quick lookup (variable definitions, coded values) | Direct answer |
| **Revision** | Updating or fixing a previous analysis | New version of Plan + Notebook + Report |

The assistant will classify your request and confirm the mode before proceeding.

<!-- TODO: Consider adding 2-3 sentences here about the orchestrator → agents → skills mental model as a brief bridge. Something like: "Behind the scenes, DAAF coordinates specialized agents — planners, executors, reviewers — each with fresh context and focused protocols. This decomposition is what makes the quality guarantees possible." -->

### Example Requests

**Full Pipeline:**
- "Analyze graduation rates by state for the past 5 years"
- "Research the relationship between school poverty and enrollment in California"
- "Create an analysis of college endowment growth trends"

**Discovery:**
- "What data is available on school discipline?"
- "Is it feasible to analyze teacher salaries by district?"
- "What poverty measures exist for schools?"

**Targeted Assist:**
- "What does the enrollment variable mean in CCD data?"
- "What are the coded values for charter school status?"
- "How is the graduation rate calculated in IPEDS?"

**Revision:**
- "Update the school poverty analysis to include 2023 data"
- "Fix the enrollment filter in my Texas schools analysis"
- "Add a breakdown by district type to the existing analysis"

For detailed guidance on writing effective prompts, choosing the right mode, and reviewing outputs, see **[Best Practices](user_reference/03_best_practices.md)**.

For a complete walkthrough of what to expect during an analysis — including the 5 phases, how to review artifacts, and session recovery — see **[Understanding DAAF](user_reference/02_understanding_daaf.md)**.

---

## Available Data Sources

The assistant connects to 15+ education data sources through the Urban Institute Education Data Portal:

### K-12 Data

| Source | Description | Key Variables |
|--------|-------------|---------------|
| **CCD** | Common Core of Data — public school/district directory, enrollment, staffing, finance | Enrollment, FRL eligibility, school type, staffing counts |
| **CRDC** | Civil Rights Data Collection — discipline, course access, equity indicators | Suspensions, expulsions, AP enrollment, harassment |
| **EDFacts** | State assessment results, graduation rates, accountability | Proficiency rates, ACGR graduation rates |
| **MEPS** | Model Estimates of Poverty in Schools — school-level poverty | Poverty rate at 100% FPL |
| **SAIPE** | Small Area Income and Poverty Estimates — district-level poverty | Children in poverty, median income |

### Postsecondary Data

| Source | Description | Key Variables |
|--------|-------------|---------------|
| **IPEDS** | Integrated Postsecondary Education Data System — comprehensive college data | Enrollment, graduation rates, finance, staffing |
| **College Scorecard** | Post-college outcomes from Treasury/IRS data | Earnings, debt, repayment rates |
| **PSEO** | Postsecondary Employment Outcomes — graduate employment | Earnings by field, employment by industry |
| **FSA** | Federal Student Aid — Title IV program data | Pell grants, loans, default rates |
| **NACUBO** | Endowment study data | Endowment size, investment returns |
| **EADA** | Equity in Athletics — college sports data | Participation, coaching, expenses by gender |
| **Campus Safety** | Clery Act crime statistics | Campus crime, fire safety |

### Supporting Data

| Source | Description |
|--------|-------------|
| **NHGIS** | Census geography and demographic data for school communities |
| **NCCS** | Nonprofit organization data for private institutions |

---

## Architecture Overview

This system uses a **multi-agent architecture** where specialized agents handle different aspects of the research workflow, coordinated by an orchestrator.

### Why Multiple Agents?

Single-agent systems face a fundamental problem: as context grows, quality degrades. By decomposing work into specialized agents with focused responsibilities, each agent operates with fresh context and clear protocols.

### Agent Ecosystem (12 Specialized Agents)

| Agent | Role | Quality Contribution |
|-------|------|---------------------|
| **research-executor** | Execute data tasks (fetch, clean, transform) | File-first execution with embedded logs |
| **code-reviewer** | Secondary QA review | Adversarial validation of every script |
| **data-planner** | Create research plans | Explicit methodology before execution |
| **plan-checker** | Validate plans before execution | Catch issues before they propagate |
| **data-verifier** | Final adversarial verification | Goal-backward coherence checking |
| **source-researcher** | Deep-dive into data sources | Understand caveats before using data |
| **research-synthesizer** | Consolidate multi-source findings | Resolve conflicts between sources |
| **debugger** | Diagnose failures scientifically | Systematic error resolution |
| **notebook-assembler** | Compile scripts into notebook | Literal copying, no new code |
| **report-writer** | Synthesize pipeline artifacts into stakeholder report | Ensures analysis results are accurately communicated with proper limitations and figure references |
| **integration-checker** | Verify component wiring | Ensure data flows correctly |
| **data-ingest** | Profile new datasets and author documentation skills | Comprehensive data profiling before use |

### Dual-Layer Validation

Every transformation passes through **two independent validation layers**:

**1. Primary Validation (CP1-CP4):** Embedded in execution scripts
- CP1: Post-fetch (schema, types, expected rows)
- CP2: Post-clean (coded values, suppression rates)
- CP3: Post-transform (row preservation, join validation)
- CP4: Pre-output (completeness, Plan alignment)

**2. Secondary QA (QA1-QA4):** Independent code-reviewer agent
- Creates separate inspection scripts
- Uses adversarial "skeptical lenses"
- Can block execution and require revision

### Skills as Knowledge Modules (24 Skills)

Skills provide domain knowledge without behavioral protocols:
- **14 education data source skills** (CCD, IPEDS, CRDC, Scorecard, etc.)
- **3 infrastructure skills** (explorer, query, context)
- **6 data science/development tools** (polars, plotnine, marimo, etc.)

For a deeper dive into how the orchestrator, agents, and skills interact — including what a completed analysis folder looks like — see **[Understanding DAAF](user_reference/02_understanding_daaf.md)**.

---

## Human Oversight

<!-- TODO: Consider expanding this into a brief (5-8 sentence) summary of the human oversight philosophy. Key points to hit: the system stops at decision points, plans require approval, validation gates require human review, and some analyses are methodologically invalid and will be blocked (e.g., cross-state assessment comparisons). The current README had a full "Built-in Safeguards" table and "What Cannot Be Compared" section — decide how much of that flavor to preserve here vs. leaving it all in 03. -->

The assistant includes safeguards like validation checkpoints, secondary QA review, automatic STOP conditions, and mandatory Plan approval — but **human review of all outputs is essential**. Some analyses are methodologically invalid regardless of data availability (e.g., cross-state assessment comparisons) and will be blocked automatically.

For detailed guidance on your role in the human-AI research partnership, reviewing outputs, and understanding what the system can and cannot validate, see **[Best Practices](user_reference/03_best_practices.md)**.

---

## Contributing

We welcome contributions! This is an open-source proof-of-concept, and there are many ways to help:

- **Report issues:** Found a bug or have a suggestion? [Open an issue](https://github.com/brhkim/daaf/issues)
- **Improve documentation:** Help make the system more accessible
- **Add skills:** Create new data source or tool skills
- **Enhance agents:** Improve agent protocols and validation logic
- **Streamline workflows:** Help me figure out how to reduce the bulk of CLAUDE.md without breaking everything

Please review existing issues before creating new ones, and be respectful in all interactions. I'm not a software developer, so a lot of this true open-source collaboration work will take some time to acclimate to!

For detailed guidance on filing effective issues (including how to use session logs), development setup, and framework modifications, see the **[Contributing Guide](user_reference/05_contributing.md)**.

---

## License

This project is licensed under the **GNU Lesser General Public License v3.0** (LGPL-3.0-or-later).

**The simple version:** Anyone can use this for any reason. If you make improvements to the **core DAAF framework**, those improvements must be shared back with the entire community. However, any extensions you build **in addition to and on top of the framework** can remain private and yours to use as you wish.

### What This Means
- **Freedom to use**: Use this software for any purpose, including with proprietary data and systems
- **Freedom to study**: Access and modify the source code
- **Freedom to share**: Distribute copies
- **Freedom to improve**: Distribute your modifications

### The Core vs. Extensions Principle

Unlike the standard GPL, the LGPL distinguishes between **modifying the framework itself** and **building on top of it**:

**Modifications to DAAF's core** must be shared if you distribute them, such as (but not limited to):
- Changes to the orchestrator logic, workflow stages, or validation protocols
- Modifications to existing agent definitions or bundled Skills
- Bug fixes or enhancements to DAAF's Python workflows and protocols

**Extensions built on DAAF** are yours to keep open or proprietary as you see fit, such as (but not limited to):
- Private data source Skills you author for your own databases
- Custom agents you create for your organization's specific workflows
- Research methodologies and analysis scripts you develop using DAAF
- All data, outputs, reports, notebooks, and visualizations you produce via DAAF

**Important:** Copyleft obligations only trigger when you **distribute** a modified version of DAAF to others. Internal use within your organization — no matter how extensively you modify the framework — requires no sharing whatsoever.

### Practical Examples

| Scenario | Must you share open-source? | Why |
|----------|----------------|-----|
| You fix a bug in DAAF's orchestrator and publish your fork | **Yes** | This modifies the core framework and is distributed |
| You create a Skill for your agency's private student database | **No** | This is an extension — a new file that uses DAAF's interfaces |
| You add a custom agent for your team's internal review process | **No** | New agents are extensions, and internal use never triggers sharing |
| You apply a proprietary statistical methodology in your analysis scripts | **No** | Analysis scripts are your work product, not part of DAAF |
| You modify DAAF's validation checkpoints for internal use only | **No** | Internal modifications are never subject to LGPL obligations |
| You work with FERPA-protected, classified, or proprietary data | **No** | Data processed by the framework is never affected by the license |
| You run DAAF in a private Docker container within your organization | **No** | Running software internally is not distribution |
| You modify the DAAF core framework and want to sell as new software | **Yes** | Distributing modified core framework code triggers LGPL |

### Why LGPL-3.0-or-later?

We chose LGPL-3.0-or-later to balance openness with practical adoption. It ensures that the core research tooling remains open and transparent — anyone who improves the framework's orchestration, agents, or validation protocols and distributes those improvements must share them back with the community.

At the same time, it allows DAAF to be used in a diverse range of contexts — including those involving sensitive, proprietary, or classified data — without requiring users to open-source their data configurations, research methodologies, or analysis outputs. This matters because many of the researchers and analysts who would benefit most from DAAF work with data that cannot be made public (government agencies, healthcare researchers, private-sector analysts, etc.).

See [LICENSE](LICENSE) and [COPYING.LESSER](COPYING.LESSER) for the full license text.

> **Note:** This summary is provided for convenience and does not constitute legal advice. The authoritative license terms are in the LICENSE and COPYING.LESSER files. If you have specific compliance questions, consult a qualified attorney.

---

## Acknowledgments

### Urban Institute Education Data Portal

The current proof-of-concept iteration of this project would not be possible without the **[Urban Institute Education Data Portal](https://educationdata.urban.org/)**—a remarkable public resource that harmonizes data from over a dozen federal education data sources into a single, well-documented API.

We are deeply grateful to the Urban Institute for:
- Making high-quality education data freely accessible to researchers
- Providing excellent documentation and consistent data structures
- Harmonizing complex federal datasets that would otherwise require significant expertise to navigate
- Supporting the research community with responsive maintenance and updates

If you use DAAF or the Education Data Portal in your work, please cite the Urban Institute appropriately. See the [Education Data Portal documentation](https://educationdata.urban.org/documentation/) for citation guidelines. Please be extremely kind and appreciative of them -- they were not aware of DAAF until well into development (in fairness, it didn't seem worth sharing until I could confirm it actually worked well!).

### Inspiration

Several core workflow patterns in this project—particularly around agent specialization, shared working memory, and task decomposition—were vastly improved thanks to excellent practices in **[Get Shit Done](https://github.com/glittercowboy/get-shit-done)** by [@glittercowboy](https://github.com/glittercowboy). If you're more into the world of software development, that's an amazing resource to work from!

Early thinking for this project began in mid-2025 as I saw growing agentic automation in the software development sphere, but was rapidly accelerated when I first read Dr. Anton Korinek's working paper, [AI Agents for Economic Research](https://www.genaiforecon.org/JEL-2025-Aug-AIAgents.pdf). I highly recommend a read and tracking his lab's work going forward -- more relevant than ever now, I think and hope, with the launch of DAAF.

## Recommended Next Steps

- [**01. Installation & Quick Start**](01_installation_and_quickstart.md) — Get started! Installation prerequisites, step-by-step 5-minute setup, day-to-day usage, and troubleshooting
- [**06. FAQ: Technical**](06_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, design rationale, authentication errors, and other common errors
- [**07. FAQ: Philosophy**](07_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
