# Education Data Research Assistant

An open-source proof-of-concept demonstrating how AI can assist with rigorous, reproducible analysis of U.S. education data—while keeping humans firmly in the loop.

---

## Vision & Purpose

This project explores a critical question: **Can AI meaningfully assist with complex research tasks while maintaining the rigor that social science demands?**

Our answer: Yes, but only with extensive guardrails, modular quality assurance, and human oversight at every critical juncture.

### What This Project Demonstrates

1. **Multi-Agent Architecture for Quality**: Rather than relying on a single AI to handle everything, we decompose research into specialized agents—planners, executors, reviewers, verifiers—each with focused responsibilities and explicit protocols.

2. **Iterative Validation**: Every data transformation is validated immediately. Errors are caught at the transformation where they occur, not downstream.

3. **Auditability by Design**: Every script includes embedded execution logs. Every decision is documented. Any human reviewer can trace exactly what happened and why.

4. **Human-in-the-Loop**: The system stops and escalates at decision points. Plans require approval. Quality gates require human verification.

### Why Education Data?

We chose the [Urban Institute Education Data Portal](https://educationdata.urban.org/) as our demonstration domain because it offers:

- High-quality, well-documented public data
- Real policy relevance (K-12 schools, colleges, outcomes)
- Sufficient complexity to stress-test the system (multiple sources, coded values, suppression rules, cross-state comparability issues)

---

## Important Caveats

**This is a proof-of-concept, not a production system.**

### Hallucination Risk

Large language models can generate plausible-sounding but incorrect outputs. This system includes multiple layers of validation specifically to catch such errors, but **no automated system can guarantee correctness**.

**Human review of all outputs is essential.**

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

Ask questions about U.S. K-12 schools, districts, and colleges. Get documented, reproducible analyses with full methodology and stakeholder-ready reports.

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
3. **EXECUTE** — Run via Bash: `python script.py 2>&1`
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

### Getting Started Tips

**First time using the assistant?**

1. **Start with Discovery Mode** — Ask "What data is available on [your topic]?" to understand options
2. **Be specific** — "Analyze California high schools" is better than "analyze schools"
3. **Expect interaction** — The assistant will return to you at key decision points to review validation reports
4. **Review the Plan** — Before data analysis begins, you'll get a Plan document to review (you can request changes)
5. **Check validation cells** — When you receive a notebook, look at the validation cells to understand what the assistant verified

**What makes a good request?**

✅ **Good:** "Analyze school poverty rates in Texas from 2018-2022, breaking down trends by district type"
- Specific geography, time period, and analysis dimension

✅ **Good:** "What poverty measures exist for schools and which is most reliable?"
- Clear question, open to assistant expertise

❌ **Less Good:** "Tell me about schools"
- Too broad; assistant will ask clarifying questions

❌ **Less Good:** "Compare state test scores between California and Texas"
- Methodologically invalid (state tests aren't comparable); assistant will block and explain

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

### What to Expect

For a Full Pipeline analysis, the assistant follows a structured workflow:

```
Your Question → Discovery → Planning → Data Acquisition → Analysis → Delivery
```

**Phase 1: Discovery & Scoping**
- Classifies your request and confirms scope
- Explores available data sources and variables
- Documents limitations and caveats

**Phase 2: Planning**
- Creates a Plan document capturing all methodology decisions
- Specifies data queries, cleaning approach, and output format

**Phase 3: Data Acquisition**
- Fetches data from the Education Data Portal API
- Validates data quality and handles coded values
- Documents suppression rates and missing data

**Phase 4: Analysis & Notebook**
- Sub-Stage 7.1: Performs exploratory data analysis (EDA) first, without transformations
- Sub-Stage 7.2: Executes transformations **one at a time** following the Iteration Protocol
- Sub-Stage 7.3: Final CP3 validation after all transformations complete
- Stage 8: Creates visualizations after all transformations are validated
- Stage 9: Assembles a marimo notebook displaying pre-executed scripts with their embedded validation logs

**Phase 5: Synthesis & Delivery**
- Generates a stakeholder report
- Completes final review against original request
- Delivers all artifacts with file paths

### Returning to Previous Work

To revise or update a previous analysis:

1. Reference the project by keywords or date (e.g., "the Texas poverty analysis" or "the 2026-01-15 enrollment study")
2. Describe what needs to change
3. The assistant will locate your project, read the existing Plan, and create a new version

**Version System:** All versions are preserved in the same project folder:

```
research/2026-01-24 School Poverty Analysis/
├── 2026-01-24 School Poverty Analysis Plan.md       (Original)
├── 2026-01-24 School Poverty Analysis.py            (Original - assembles scripts)
├── 2026-01-24 School Poverty Analysis Report.md     (Original)
├── 2026-01-24a School Poverty Analysis Plan.md      (Revision 1)
├── 2026-01-24a School Poverty Analysis.py
├── 2026-01-24a School Poverty Analysis Report.md
├── scripts/                                         (*** PRIMARY EXECUTION ARTIFACTS ***)
│   ├── stage5_fetch/                                (Data retrieval scripts)
│   ├── stage6_clean/                                (Context application scripts)
│   ├── stage7_transform/                            (Transformation scripts)
│   └── stage8_viz/                                  (Visualization scripts)
├── data/
│   ├── raw/
│   └── processed/
└── output/
    └── figures/
```

Prior versions are never modified or overwritten.

### Understanding Generated Notebooks

Marimo notebooks **assemble pre-executed scripts** rather than containing new analysis code. When you receive a notebook, you'll see:

```python
# Cell: Section header for a script stage
mo.md("## Stage 7.1: Filter to California Schools")
mo.md("**Script:** `scripts/stage7_transform/01_filter-california.py`")

# Cell: Display the executed script code (can be re-run interactively)
# === CODE FROM 01_filter-california.py ===
pre_shape = df.shape
df_ca = df.filter(pl.col("fips") == 6)
post_shape = df_ca.shape
# ... validation logic ...

# Cell: Display execution log (parsed from script's embedded comments)
mo.accordion({
    "Execution Log (2026-01-24 14:32:05)": mo.md("""
    - Duration: 2.3s
    - Exit code: 0
    - Pre-state: 100,000 rows
    - Post-state: 8,500 rows (California only)
    - CP3 Status: PASSED ✅
    """)
})
```

**Why this matters:**
- **Scripts are the primary artifacts** — the actual analysis code lives in `scripts/`, not the notebook
- **Embedded execution logs** — you can see exactly what happened when each script ran
- **Full audit trail** — each script's output is preserved as comments in the script file
- **Reproducibility** — run `python scripts/stage7_transform/01_filter-california.py` to reproduce any step

**What you won't see:**
- New analysis code written directly in the notebook
- Transformations without embedded execution logs
- Scripts executed interactively without file capture

The notebook is a **walkthrough tool** for reviewing the validated analysis, not the source of the analysis itself. See `scripts/` for the primary execution artifacts.

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

### Agent Ecosystem (11 Specialized Agents)

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
- **7 data science/development tools** (polars, plotnine, marimo, ruff, etc.)

---

## Human Oversight & Best Practices

### Built-in Safeguards

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

### What Cannot Be Compared

Some analyses are methodologically invalid regardless of data availability. The assistant will block:

- **Cross-state assessment comparisons** — State tests are not comparable
- **Analyses with >50% suppression** — Insufficient data for valid conclusions

---

## Repository Structure

| Directory | Purpose |
|-----------|---------|
| `research/` | Analysis projects (notebooks, data, reports) |
| `agents/` | Specialized agent protocols (11 behavioral definitions) |
| `agent_reference/` | Detailed protocols, templates, and reference tables |
| `.claude/skills/` | Skill definitions (24 skills for data sources and tools) |

### Project Folder Structure

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
│   ├── raw/                          # Original API responses (.parquet, .csv)
│   └── processed/                    # Cleaned data (.parquet, .csv)
├── output/
│   └── figures/                      # Exported visualizations
```

**Key insight:** Scripts are the PRIMARY execution artifacts, not afterthoughts. The marimo notebook assembles them into an interactive walkthrough; it doesn't contain separate, new code.

---

## Installation

### Prerequisites

You need four things before starting:

**1. Git** — [Install Git](https://git-scm.com/downloads)

Git is a version control tool that primarily helps people track software file changes and updates. In this case, it lets you download ("clone") this project to your computer (all the files you see above). You'll use it just once during setup. The Git installer is straightforward — the default options are generally fine. If you continue to use Claude Code at all, and plan to use this project, I HIGHLY recommend you learn more about how to use Git for project and file management. It is absolutely necessary to better track and understand how Claude is changing things in your workspace later on.

**2. Docker Desktop** — [Install Docker Desktop](https://www.docker.com/products/docker-desktop/)

Docker is a program designed to help people create self-contained, isolated environments (called a "container") on your computer that are strictly separated from everything else, and extremely easy to replicate and share. This protects your computer and prevents Claude Code from messing with anything it shouldn't be, and it ensures that even if somehow things go catastrophic, you can easily spin a new virtual environment back up in minutes. In this project, I use Docker to install every needed piece of software in a predictable and stress-free way, that has Python, data science libraries, and Claude Code all pre-installed. Think of it like a lightweight virtual computer running inside your computer. Docker Desktop includes everything you need (including Docker Compose, which coordinates the setup). After installing, make sure Docker Desktop is running before proceeding. If you're worried, you can see exactly what is installed by reading the Dockerfile in this repository -- feel free to ask your favorite LLM to help you interpret and inspect it, if you'd like.

**3. An Anthropic account** — for Claude Code access

Claude Code is the AI assistant that powers this project. It runs inside your terminal (not in a web browser) and needs to authenticate with Anthropic. You have two options:
- **Anthropic API key** — [Get one here](https://console.anthropic.com/). This is a pay-per-use key that you'll paste into Claude Code when prompted. Just note, this can get VERY expensive, very quickly. I HIGHLY recommend getting a Pro/Max subscription for this project.
- **Anthropic Pro/Max subscription** — If you have a Claude Pro or Max plan, Claude Code can authenticate through your subscription instead. It will walk you through this interactively. I am on the top-level Max plan and it is more than enough for my usage and development of this project, but admittedly a very high barrier to entry. Conversely, I think Pro will probably not be enough for reliably using it more than once every 4 hours (their rate limiting window), but it's worth testing! Please let me know your experiences.

Claude Code will prompt you to choose your authentication method the first time you run it — you don't need to configure anything in advance. Note that you can easily port this whole project over to a CLI tool of your choice (OpenCode, Codex, etc.) with a little bit of effort. Fork this repo, work with your favorite tool to convert it over, and please continue to share it broadly with others!!!

**Recommended model:** All development and testing of this project was done using **Opus 4.5** and **Opus 4.6**. I strongly recommend using one of these models for the best results. You can change your model at any time inside Claude Code by typing `/model` and selecting from the list. Other models (Sonnet, Haiku) have not been tested with this workflow and may produce inconsistent results — especially for the multi-agent orchestration and validation stages, which rely on the model's ability to follow complex, multi-step protocols reliably.

**4. A terminal program** — for setting up the project and running Claude Code itself

You'll interact with the assistant through your **terminal** (also called the command line or shell), where you type commands and press Enter to run them. This project is used entirely through the terminal — the text-based interface on your computer where you type commands. Your computer definitely already has this, but if you're not used to working in the terminal, here are some basics:

**Opening your terminal:**
- **Mac:** Open the "Terminal" app (search for it in Spotlight with `Cmd + Space`)
- **Windows:** Open "PowerShell" or "Command Prompt" from the Start menu (PowerShell is recommended)
- **Linux:** Open your terminal emulator (usually `Ctrl + Alt + T`)

**Helpful terminal basics:**
| What you want to do | Command | Example |
|---------------------|---------|---------|
| See where you are | `pwd` | Shows `/Users/yourname/daaf` |
| List files here | `ls` | Shows files and folders in current directory |
| Move into a folder | `cd foldername` | `cd daaf` |
| Go up one folder | `cd ..` | Goes to the parent directory |
| Clear the screen | `clear` | Clears clutter (your history is still there) |
| Cancel a running command | `Ctrl + C` | Stops whatever is currently running |
| Scroll up to see past output | Scroll or `Shift + Page Up` | See output that scrolled off screen |

**Tips:**
- You can paste commands into the terminal (`Cmd + V` on Mac, `Ctrl + V` or right-click on Windows)
- Press the up arrow key to recall previous commands
- Tab completion works — start typing a file/folder name and press `Tab` to auto-complete it


### Quick Start

Once you have all the prerequisites above, open your terminal and run these commands one at a time:

```bash
# 0. Navigate to the folder where you want this project to live. Change the below to the folder you want!
cd "C:\Users\Documents" 

# 1. Download the project to your computer
git clone https://github.com/brhkim/daaf.git

# 2. Move into the project folder once it's downloaded
cd daaf

# 3. Build and start the container (this takes a few minutes the first time because Docker is going to download the necessary software from the internet and get it ready for you)
docker compose up -d --build

# 4. Once that's complete, open an interactive session inside the container
docker compose exec daaf-docker bash

# 5. Start Claude Code
claude

# 6. Check or change your model to Opus 4.6
/model
```

On step 5, Claude Code will prompt you to authenticate (API key or subscription login). After that, you're in — start asking research questions.

**What just happened?**
- Step 1 downloaded all the project files to a `daaf` folder on your computer
- Step 2 moved your terminal into that folder
- Step 3 built a Docker container with all the tools pre-installed using the Dockerfile provided with this project (Python, data science packages, Claude Code)
- Step 4 opened a terminal session *inside* that container, separated from the rest of your computer and running with all the software we just installed into the Docker image
- Step 5 launched the Claude Code assistant, ready to help with education data research. 
- Step 6 ensured you're using Opus 4.6 for this work, as it's basically required given the complexity of tasks at play here.

### What the Container Includes

You don't need to install any of these — Docker handles it all — but for your reference:

| Component | What it does |
|-----------|-------------|
| Python 3.12 | Runs the analysis code |
| polars, pandas, numpy | Data manipulation and analysis |
| plotnine, plotly, matplotlib | Charts and visualizations |
| marimo | Interactive notebooks for reviewing analyses |
| Claude Code | The AI assistant you interact with |
| ruff | Keeps code clean and formatted |

### How Files Work

Your local `daaf/` folder is connected to the container. This means:

- **Files sync both ways** — when the assistant creates a report or dataset inside the container, it appears in the folder on your computer too. You can open these files normally.
- **Your work persists** — stopping the container doesn't delete your research outputs. They live in your project folder.
- **Only this folder is accessible** — the container cannot see any other files on your computer. Your documents, photos, and everything else are completely isolated.

### Viewing Marimo Notebooks

The assistant uses a python library called "marimo" to create streamlined python code "notebooks" as part of its analysis. It can also use this library to create nice, interactive dashboards for you of analyses it has completed To view one in your browser:

```bash
# Inside the container — view a notebook (replace the path with your actual notebook)
marimo run research/YYYY-MM-DD\ Title/notebook.py --host 0.0.0.0 --port 2718 --headless
```

Then open [http://localhost:2718](http://localhost:2718) in your computer's browser no need to mess with anything in the terminal here). The notebook renders there as an interactive document.

To edit a notebook interactively, use `marimo edit` instead of `marimo run`:

```bash
marimo edit research/YYYY-MM-DD\ Title/notebook.py --host 0.0.0.0 --port 2718 --headless
```

### Day-to-Day Usage

Once installed, your daily workflow is just:

```bash
# Get into the project directory, inputting the right file path for your own system
cd "C:\Users\Documents\daaf"
# Make sure Docker Desktop is running on your computer, then:
docker compose up -d
docker compose exec daaf-docker bash
claude
```

When you're done for the day:

```bash
# Type /exit or press Ctrl+C to leave Claude Code, then:
exit
docker compose down
```

Your files are safe — they're on your computer, not just inside the container.

### Troubleshooting

**"Cannot connect to the Docker daemon"**
- Make sure Docker Desktop is running (look for the whale icon in your system tray / menu bar)

**"Port 2718 already in use"**
- Another process is using that port. Either stop it, or change the port mapping in `docker-compose.yml` (e.g., `"3000:2718"` to use port 3000 on your host)

**Claude Code asks for an API key every time**
- Claude Code stores its configuration inside the container. If you fully remove the container (`docker compose down`), you may need to re-authenticate next time. To avoid this, you can set `ANTHROPIC_API_KEY` as an environment variable in a `.env` file in the project root (the `.gitignore` already prevents `.env` from being shared publicly)

**Container seems slow to build the first time**
- The first `docker compose up --build` downloads base images and installs all packages. This is a one-time cost — subsequent starts are fast since Docker caches everything

**"command not found: docker"**
- Docker Desktop may not be installed, or your terminal needs to be restarted after installation. Close and reopen your terminal, and make sure Docker Desktop is installed and running

---

## Frequently Asked Questions

> **Note:** This section will be expanded based on community questions.

### General

**Q: Is this ready for production use?**

A: No. This is a proof-of-concept demonstrating AI-assisted research patterns. All outputs require human review. Don't be lazy, don't trust it without verifying. DO NOT give Claude access to any proprietary or private data. If you want to use this for your actual important work, you need to work with your IT to ensure you've got all the necessary agreements and file protections in place before trying to use this system with your data. Do not mess around, do not take risks -- do your homework here.

**Q: What data sources are currently supported?**

A: The system connects to 14+ education data sources through the Urban Institute Education Data Portal. See [Available Data Sources](#available-data-sources).

**Q: Can I use this for non-education research?**

A: The architecture patterns are generalizable, but the skills and protocols are specifically designed for education data. Adapting to other domains would require creating new skills and potentially modifying agent protocols. I've provided a "data-ingest" agent to help you with that process for a given (non-proprietary/sensitive) table and data documentation you might have, as well as a "skill-authoring" skill that gives your assistant a sense of the best practices for how to set it up. 

**Q: It's asking me to confirm basically everything, and it's taking forever. Can't it just run on its own?**

A: So, in general, you shouldn't just let Claude cook without paying attention. One layer of robustness is being in the loop and paying attention to what it's doing. Sometimes it gets into a rut, and then finds very strange and ill-advised workarounds. But if you really want to risk it, it's possible to "dangerously skip permissions" -- a setting called exactly that for a reason. I won't advise on how to do that here, please feel free to look it up on your own if you want to take on that liability! Because this is running in Docker, you may also need to an environment variable in your terminal to indicate it's a sandbox -- your assistant can help you there if you want.

### Technical

**Q: Why Polars instead of Pandas?**

A: Polars offers better performance in general and a, in my opinion, much more legible and intuitive coding process that reduces ambiguity — important when AI is generating code.

**Q: Why Marimo instead of Jupyter?**

A: Marimo notebooks are pure Python files (better for version control) and enforce cell dependencies (reducing hidden state bugs). This works far better for version control, and is far, far, far easier for an LLM assistant to edit without messing things up versus Jupyter.

### Session Logs & Diagnostics

**Q: Where are session logs stored?**

A: Claude Code automatically archives a complete log of every session when it ends. These are stored locally in `.claude/logs/sessions/` in two formats:

| Format | File Pattern | Purpose |
|--------|-------------|---------|
| **Markdown** (`.md`) | `YYYY-MM-DD_HH-MM-SS_<session-id>.md` | Human-readable transcript with tool calls, timestamps, and token usage |
| **JSONL** (`.jsonl`) | `YYYY-MM-DD_HH-MM-SS_<session-id>.jsonl` | Raw machine-readable transcript (full API-level detail) |

Additionally, `.claude/logs/activity.log` records a timestamped entry every time a session starts, giving you a quick overview of usage history.

**These logs are gitignored by default** (they may contain sensitive content or API details), so they stay on your local machine and are never pushed to the repository.

**Q: How can I use session logs for debugging?**

A: Session logs are invaluable when something goes wrong. The Markdown logs show you exactly what the assistant did, in order — every tool call, every file read/write, every subagent invocation, and the full output at each step. If you need to file a bug report or understand an unexpected result:

1. Find the relevant session log in `.claude/logs/sessions/` (sorted by timestamp)
2. Open the `.md` file to review what happened in a readable format
3. Look for the point where things went wrong — you'll see the exact tool calls and their results
4. When filing an issue, include relevant excerpts from the log (redact any sensitive data first)

The `.jsonl` file contains the complete raw transcript if deeper inspection is needed.

### Troubleshooting

*Coming soon based on common issues.*

---

## Contributing

We welcome contributions! This is an open-source proof-of-concept, and there are many ways to help:

- **Report issues:** Found a bug or have a suggestion? [Open an issue](https://github.com/brhkim/daaf/issues)
- **Improve documentation:** Help make the system more accessible
- **Add skills:** Create new data source or tool skills
- **Enhance agents:** Improve agent protocols and validation logic
- **Streamline workflows:** Help me figure out how to reduce the bulk of CLAUDE.md without breaking everything

Please review existing issues before creating new ones, and be respectful in all interactions. I'm not a software developer, so a lot of this true open-source collaboration work will take some time to acclimate to!

### Filing Issues

Good issue reports make debugging much easier. When opening an issue, please include:

**For bug reports:**
- **What you asked the assistant to do** — the prompt or request you gave
- **What happened vs. what you expected** — be specific about the failure
- **Which stage failed** — if you can tell (e.g., "it failed during data fetch" or "the plan looked wrong")
- **Session log excerpts** — check `.claude/logs/sessions/` for the relevant Markdown log. Copy the section where things went wrong (redact any API keys or sensitive content first)
- **Your environment** — Docker or native install, OS, Claude Code authentication method (API key vs. subscription)

**For feature requests or suggestions:**
- **What you're trying to accomplish** — the research question or workflow
- **What's missing or could be better** — be specific about the gap
- **Ideas for how it could work** — if you have them (totally optional)

**For data source issues:**
- **Which data source** — e.g., CCD, IPEDS, Scorecard
- **The API endpoint or variables involved** — if you can identify them
- **What the data looked like vs. what was expected** — row counts, unexpected values, missing columns

**Tips for including session logs:**

Your session logs in `.claude/logs/sessions/` contain a full record of what the assistant did. When including excerpts in issues:

1. Open the `.md` log file for the session where the problem occurred
2. Find the relevant section (search for the stage or error message)
3. Copy just the relevant portion — you don't need the whole log
4. **Redact sensitive information** — remove any API keys, file paths with personal info, or data that shouldn't be public
5. Wrap excerpts in a `<details>` block to keep the issue tidy:

````markdown
<details>
<summary>Session log excerpt</summary>

```
(paste the relevant section of your session log here)
```

</details>
````

Issue templates are available when you [create a new issue](https://github.com/brhkim/daaf/issues/new/choose) to help guide you through this.

---

## License

This project is licensed under the **GNU General Public License v3.0** (GPL-3.0).

### What This Means

- ✅ **Freedom to use**: Use this software for any purpose
- ✅ **Freedom to study**: Access and modify the source code
- ✅ **Freedom to share**: Distribute copies
- ✅ **Freedom to improve**: Distribute your modifications

### Copyleft Requirement

If you distribute modified versions of this software, you must:
- Release your modifications under GPL-3.0
- Make source code available
- Preserve copyright notices

### Why GPL-3.0?

We chose GPL-3.0 to ensure that improvements to this proof-of-concept remain open and accessible to the research community. AI-assisted research tools should be transparent and auditable—proprietary forks would undermine this goal.

See [LICENSE](LICENSE.md) for the full license text.

---

## Acknowledgments

### Urban Institute Education Data Portal

This project would not be possible without the **[Urban Institute Education Data Portal](https://educationdata.urban.org/)**—a remarkable public resource that harmonizes data from over a dozen federal education data sources into a single, well-documented API.

We are deeply grateful to the Urban Institute for:
- Making high-quality education data freely accessible to researchers
- Providing excellent documentation and consistent data structures
- Harmonizing complex federal datasets that would otherwise require significant expertise to navigate
- Supporting the research community with responsive maintenance and updates

If you use this tool or the Education Data Portal in your work, please cite the Urban Institute appropriately. See the [Education Data Portal documentation](https://educationdata.urban.org/documentation/) for citation guidelines. Please be extremely kind and appreciative of them -- they are probably going to accidentally get DDOS'd by people wanting to use this and Claude being dumb about API calls. Please remind Claude to be careful about that (though it's part of its instructions already, couldn't hurt to say)!

### Inspiration

Several core workflow patterns in this project—particularly around agent specialization, shared working memory, and task decomposition—were vastly improved thanks to excellent practices in **[Get Shit Done](https://github.com/glittercowboy/get-shit-done)** by [@glittercowboy](https://github.com/glittercowboy). If you're more into the world of software development, that's an amazing resource to work from!
