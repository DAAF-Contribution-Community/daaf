# 04. Extending DAAF

This guide focuses on the primary extension path: bringing new datasets, data domain expertise, and methodological tooling into DAAF for your own purposes. If you want to make any of these modifications available to the broader community by sharing these changes/extensions back with the DAAF project, see [**05. Contributing to DAAF**](../CONTRIBUTING.md).

> **Guided framework modification:** For any of the extension tasks below, you can use DAAF's **Framework Development mode** — just tell DAAF you want to create or modify a skill, agent, mode, or template, and it will scope the work, follow canonical templates, execute integration checklists, and run a multi-angle review pass to ensure consistency. Framework Development mode is especially useful for complex changes that touch multiple files.

[**Back to main**](https://github.com/DAAF-Contribution-Community/daaf/tree/main)

---

## Table of Contents

- [**The Extension Model: Skills, Agents, and Data Onboarding**](#the-extension-model-skills-agents-and-data-onboarding)
- [**Step-by-Step: Profiling a New Dataset with Data Onboarding Mode**](#step-by-step-profiling-a-new-dataset-with-data-onboarding-mode)
- [**Step-by-Step: Authoring Other Types of New Skills**](#step-by-step-authoring-other-types-of-new-skills)
- [**Adding a New Agent**](#adding-a-new-agent)
- [**Testing Your New Extension End-to-End**](#testing-your-new-extension-end-to-end)
- [**Submitting Your Extension for Inclusion**](#submitting-your-extension-for-inclusion)
- [**Customizing Your Python Environment**](#customizing-your-python-environment)
- [**Recommended Next Steps**](#recommended-next-steps)

---

## The Extension Model: Skills, Agents, and Data Onboarding

Here's the fundamental insight behind DAAF's extensibility: **the framework is intended to separate what it *knows* from how it *behaves*.** This is a really important distinction that makes the whole extension model work, so let me try to explain it clearly.

Building from our initial discussion of agents and skills from [**02. Understanding and Working with DAAF**](02_understanding_daaf.md), DAAF has two main types of building blocks:

- **Skills** are structured knowledge documents. They tell DAAF's agents *what they need to know* about a specific topic -- a data source, a Python library, a visualization framework, a domain of expertise. Think of skills as extremely thorough, well-organized reference guides that an agent loads into its context when it needs specialized knowledge to do its job, and can be easily shared or transferred across multiple agents.

- **Agents** are behavioral protocols. They tell a subagent *how to behave* -- what steps to follow, what to validate, when to stop, how to format output. Think of agents as detailed job descriptions that define a specific role in the pipeline (the code reviewer, the data planner, the report writer, etc.).

This separation is what makes DAAF extensible without being fragile. When you want DAAF to work with a new dataset, you generally shouldn't need to touch the workflow, the validation logic, or the agent protocols at all. You just add a new skill that teaches the existing agents about the new data. The agents already know *how* to fetch, clean, transform, and analyze data -- they just need to be told the specifics of *your* data.

### The Three Extension Paths

| Extension Type | What You're Adding | Tool to Use | Result |
|----------------|-------------------|-------------|--------|
| **Data source** | Knowledge about a specific dataset | Data Onboarding Mode | A new `data-source-skill` |
| **Methodology** | Knowledge about a statistical or analytical method | `skill-authoring` skill | A new `methodology-skill` |
| **Domain expertise** | Knowledge about a content area or field | `skill-authoring` skill | A new `context-skill` |

The most common extension path by far -- and the one I'll spend the most time on in this guide -- is adding new data sources. DAAF has a dedicated engagement mode for this purpose: **Data Onboarding Mode**, which orchestrates a thorough profiling protocol and generates the skill documentation for you. You still need to review its output (this is *always* true with DAAF), but it should dramatically reduce the manual effort involved.

For methodology and domain expertise skills, the process is lighter-weight -- you ask DAAF to use the `skill-authoring` skill, point it at documentation or literature to research, and it drafts a skill for you to review and refine. I'll cover that process too, but it's more straightforward than data onboarding.

## Step-by-Step: Profiling a New Dataset with Data Onboarding Mode

Data Onboarding Mode is DAAF's built-in workflow for turning a raw dataset (or online dataset source) into a comprehensive data source skill it can begin using in tandem with other data source skills. It automates the tedious but critical work of profiling every column, detecting coded values, checking data quality, and reconciling what any provided documentation says against what the data actually contains. The entire process is tracked in a reproducible research project folder under `research/`. In addition to the instructions below, I've also made a [10-minute video tutorial](https://youtu.be/G5uKSlI6jls) giving you the intuition and overview for how this works.

### Before You Start

You'll need:

1. **A data file or API access** — either a data file in a supported format (parquet, CSV, Excel, or TSV) or access to an API that serves the data (see "Onboarding Data from an API" below). Public data sources are strongly preferred. If you're working with proprietary or sensitive data, please be *extremely* careful to abide by your organization's AI policy and data protection standards -- Claude will be examining the actual contents of the data.
2. **Any available documentation** -- codebooks, data dictionaries, README files, or documentation website URLs. These aren't strictly required, but they dramatically improve the quality of the resulting skill because the agent can cross-reference what the documentation *says* against what the data *actually shows*.
3. **A sense of how the data will be used** -- what research questions it might inform, what domain it belongs to, and which columns are most important for your purposes.

### Onboarding Data from an API

If your data source is available via a REST API rather than as a downloadable file, DAAF can handle the acquisition for you during Data Onboarding. You'll need:

1. **API documentation** — a URL to the API docs, or a description of how the API works (endpoints, authentication method, response format). DAAF will research the API on your behalf, but having documentation to point to dramatically improves the quality of the resulting fetch scripts.
2. **An API key** — most APIs require authentication. Add your key to the `.env` file in your `daaf-docker` folder on the host machine (see [API Keys in the Installation Guide](01_installation_and_quickstart.md#set-up-data-source-api-keys) for the pattern). DAAF will ask you which environment variable name holds your key.
3. **A sense of what you want to download** — which endpoint, what filters (date range, geography, etc.), and roughly how much data to expect.

DAAF will research the API, write a fetch script for your approval, download the data, and then proceed with the standard profiling workflow. The fetch script is saved as a reproducible artifact — you (or DAAF) can re-run it any time to get fresh data.

**Local vs. live access:** During setup, DAAF will ask whether you prefer to download the data once and work with the local copy (simpler, works offline) or always query the API live in future analyses (keeps data current). You can change this preference later by modifying the data source skill's "Data Access" section.

**Complex APIs:** If the API you're working with offers many endpoints and datasets (like Harvard Dataverse, or a large government open data platform), DAAF will suggest whether the API access documentation should live inside the data source skill (simpler, fine for most cases) or in a separate query/connector skill (better if you plan to onboard multiple datasets from the same API over time). This is always your call.

**OAuth-protected APIs:** DAAF handles simple API key authentication natively (you set an environment variable, and DAAF writes scripts that read it). If your API requires OAuth (browser-based login, token refresh flows), you'll need to obtain a bearer/access token manually first and provide it as an environment variable. DAAF will guide you through this if it detects the API uses OAuth during its research phase.

### Onboarding Multiple Related Files

If your data source comes as multiple related files — for example, one file per year (same structure), or a set of files at different levels of aggregation (schools, districts, states) — DAAF can profile them all together as a single onboarding project.

When you provide multiple files, DAAF will ask you:
- **Same structure or different?** Files with the same columns (one per year, one per state) are combined into one dataset for profiling. Files with different structures (schools vs. districts) are profiled separately with cross-file relationship testing.
- **One skill or many?** By default, DAAF creates one unified skill covering all files. You can also opt for one skill per entity type if you prefer more granular documentation per table.

The important thing is to provide all related files at intake rather than profiling them one at a time — this lets DAAF test the relationships between files (join coverage, key integrity, temporal alignment) and document those relationships in the resulting skill.

---

### Where Your New Skill Will Fit in

When you ask DAAF to work with any current data source (say, CCD enrollment data), here's the flow:

1. The **orchestrator** dispatches a subagent to explore available data (Stage 2)
2. The subagent **loads the relevant skill** (e.g., `education-data-source-ccd`) into its context
3. The skill tells the subagent everything it needs: what variables exist, what the coded values mean, what the known pitfalls are, how to access the data
4. The subagent uses that knowledge to do its job and returns findings to the orchestrator

The key thing to understand: When you add a new data source skill, we just need the orchestrator to know what it is and when it'd be useful so it can instruct its subagents on when to load it for their specific task. To do this, you're primarily adding knowledge to the system at two points:

1. **Exploration (Stage 2-3):** Your skill tells agents what data is available, what variables exist, and what caveats to watch for
2. **Context application (Stage 6):** Your skill tells agents how to handle coded values, missing data patterns, and source-specific quirks during cleaning

The fetch mechanics (Stage 5) are mostly handled by the query skill and mirror configuration. If your data source is available through the existing mirrors, you may not need to change anything there. If your data comes from a different source entirely, you'll need to either add a new mirror configuration or provide the data files directly.

---

### Preparing Your Data

Place your data file anywhere accessible inside `/daaf/` — the ingest process will copy it into the research project's `data/raw/` folder during setup. A common convention is to place files in `/daaf/data/` or alongside the research folder (e.g., `/daaf/data/county-elections/election_returns_2024.csv`). If you have documentation files (codebooks, data dictionaries, etc.), put those alongside the data file. See [**01. Installation and Quickstart**](01_installation_and_quickstart.md) for reminders on managing files within the Docker volume if needed.

A few practical considerations:

- **File size:** The agent can handle files up to about 1GB without special handling. For larger files, it'll ask you about a sampling strategy before proceeding.
- **File format:** Parquet is ideal (fast, preserves types). CSV works fine but may have type inference quirks. Excel files work using the `openpyxl` library, included with the standard installation Docker for DAAF.
- **Multiple files:** If your data source spans multiple files (e.g., one file per year, or separate files for schools vs. districts), you can provide them all at once during Data Onboarding — see "Onboarding Multiple Related Files" below. DAAF will profile them together and test cross-file relationships automatically.

### Running Data Onboarding Mode

Just ask DAAF to ingest or profile a new dataset conversationally -- it will classify the request as Data Onboarding Mode automatically. Something like:

```
I have a new dataset I'd like to profile and integrate into DAAF.
The data file is at: /daaf/research/my-data/state_spending_2023.parquet
I also have a codebook at: /daaf/research/my-data/codebook.xlsx
The documentation website is: https://example.gov/data-documentation

This is state-level education spending data. I'd like to use it
for analyzing per-pupil expenditure trends across states. The most
important columns are probably the ones related to total spending,
enrollment counts, and state identifiers.
```

DAAF will classify this as a Data Onboarding request, set up a research project folder, and execute a systematic profiling protocol (up to 11 scripts, depending on your data's characteristics). The profiling runs across 4 sub-phases:

**Phase 1 -- Structural Discovery:** Basic shape of the data (rows, columns, memory footprint, column types) and initial column-level profiling. This gives the agent a bird's-eye view of what it's working with, including null rates, unique value counts, and basic distributions.

**Phase 2 -- Statistical Deep Dive:** Detailed statistics for every column -- full distribution analysis for numeric columns, category enumeration for categorical columns, temporal pattern analysis, and outlier detection. If your data has date/year columns or geographic identifiers, this phase also analyzes temporal coverage gaps and entity coverage against known universes.

**Phase 3 -- Relational Analysis:** Identifying potential key columns (high uniqueness suggests an identifier), foreign keys (naming patterns like `_id` suffixes), hierarchical relationships between columns, cross-column dependency patterns, and detection of coded values (those suspicious negative numbers like -1, -2, -9 that often mean "missing" or "suppressed" rather than being real values).

**Phase 4 -- Interpretation & Reconciliation:** This is where it gets interesting. The agent uses column names, value patterns, and domain conventions to make educated guesses about what each column *means*. Every interpretation is explicitly marked as `[PRELIMINARY]` -- the agent knows it's hypothesizing, not asserting. Column named `fips`? Probably a FIPS geographic code. Column with values 0 and 1? Probably a binary indicator, but is 1 "Yes" or "Male" or "Urban"? The agent will flag the ambiguity. This phase also produces overall data quality scores and a comprehensive profile summary.

If you provided documentation, the profiling protocol also runs **Documentation Reconciliation**: it parses your codebook or data dictionary, extracts every claim it can find (column definitions, expected types, coded value meanings), and then *verifies each claim against the actual data.* Documentation says there are 50 columns? The agent checks. Codebook says `state_code` should be a string? The agent confirms or flags the mismatch. This reconciliation is one of the most valuable things Data Onboarding Mode does -- it catches the disturbingly common case where documentation is outdated or describes a different version of the data than what you actually have.

### Reviewing the Profile Output

The agent will return a structured report with:

- **Structural summary:** Row/column counts, memory size, format
- **Column summary:** Type, null rate, unique count, and notes for every column
- **Coded values detected:** Which columns have potential coded values, and whether documentation confirms their meaning
- **Quality assessment:** Scores for completeness, documentation accuracy, and coded value coverage
- **Preliminary interpretations:** The agent's best guesses for what columns mean, each flagged with a confidence level and basis for the interpretation
- **Discrepancies found:** Every case where documentation contradicted observed data, with evidence for both sides
- **User review requested:** Explicit questions for you to answer -- which interpretations are correct, how to handle undocumented values, whether missing columns are expected

**This review step is not optional.** The whole point of marking interpretations as `[PRELIMINARY]` is that *you* need to confirm or correct them. The agent has done the mechanical work of profiling, but the semantic understanding -- what these columns actually *mean* in context -- requires your domain expertise. Take the time to go through the review questions carefully. Your answers will directly determine the quality of the resulting skill.

Once you've provided your feedback, the agent uses your corrections to finalize the skill and writes it to `.claude/skills/[skill-name]/`. From there, you can start a fresh session with DAAF and ask it to analyze it alongside whatever other datasets you'd like! I'd strongly recommend running it through some simple paces to get it tested and any issues worked out first.

---

## Step-by-Step: Authoring Other Types of New Skills

### Methodology Skills (via Skill-Authoring)

For adding knowledge about a statistical method, Python library, or analytical technique, you'll use the `skill-authoring` skill directly. This is more free-form than data onboarding, and the content depends heavily on what you're documenting. You may find it helpful to refer DAAF to other standard skills this one will be most like. Python library? Try referencing the `plotnine` or `polars` skills. Wanting to do something more methodological in nature? Try pointing it to the `data-scientist` skill. And so on. My hope is that as the community continues to extend DAAF in a few directions, we'll have plenty of exemplars to point to.

Ask DAAF something like:

```
I'd like to create a new methodology skill for pyfixest
(fixed-effects regression in Python). Please use the
skill-authoring skill to guide the process, and research
the pyfixest documentation online to build a comprehensive
reference. You might refer to the `polars` skill as a model
for some of what it could look like. Please run some initial
explorations and then come back to me with a plan for my
approval.
```

DAAF will use the `skill-authoring` skill to guide the process. The skill-authoring skill provides detailed guidance on:

- **Frontmatter requirements:** The YAML header that every skill needs, including naming conventions (lowercase-hyphenated, 1-64 chars) and description best practices
- **Body structure patterns:** Different organizing patterns depending on whether the skill is workflow-based (sequential steps), task-based (tool collection), reference-based (standards/specs), or capabilities-based (features)
- **Progressive disclosure:** How to keep the main SKILL.md under 500 lines by splitting detailed content into `references/` files
- **Decision trees:** How to write effective navigation trees that help agents find what they need quickly
- **Content limits:** SKILL.md body should stay under 500 lines and 5,000 words -- be concise and justify every token. Reference files have different economics: they load on-demand, so thoroughness is preferred over brevity (target 3x+ SKILL.md lines collectively for data source skills)

The resulting skill gets placed at `.claude/skills/[skill-name]/SKILL.md` with optional `references/`, `scripts/`, and `assets/` subdirectories.

### Domain Expertise Skills (via Skill-Authoring)

Same process as methodology skills, but the content focuses on domain knowledge rather than tooling. For example, you might create a skill that documents the nuances of interpreting graduation rate data, or the policy context around school funding formulas, or the methodological considerations for analyzing panel data in education research.

```
I'd like to create a context skill for understanding Community
Eligibility Provision (CEP) and its impact on free/reduced-price
lunch data. This is critical context for anyone analyzing school
poverty measures after 2014. Please use the skill-authoring skill
and launch a few web searching subagents to research this topic
in depth before coming up with a plan for my approval.
```

### Registering Your New Skill

Skills are automatically discovered via their YAML frontmatter — every skill with a `SKILL.md` file in `.claude/skills/{skill-name}/` appears in the system message at conversation start. No manual registration is needed for any skill type (data source, methodology, or domain expertise).

The key to good discoverability is writing a clear, descriptive `description` field in your skill's YAML frontmatter. This description is what the orchestrator sees when deciding which skill to load, so make it specific about what the skill covers and when to use it.

---

## Adding a New Agent

Adding data sources is the most common extension path, but sometimes you need something different: a new **behavioral role** in the pipeline. Maybe you need a specialized validator for a particular type of analysis, or a new synthesis pattern for cross-domain work, or a domain-specific planner that understands the constraints of your field. That's when you add a new agent.

This is a less common operation and a more involved one. Agents are deeply wired into the DAAF ecosystem -- they have producer/consumer relationships with other agents, they reference shared protocols, and they need to be discoverable by the orchestrator. The `agent-authoring` skill exists specifically to guide you through this process and tries to make sure nothing gets missed.

### The Agent-Authoring Workflow

Ask DAAF to use the `agent-authoring` skill:

```
I need to create a new agent for [describe the behavioral role]. I'd
like this to be an agent focused on [x, y, z], and likely should be 
involved in doing [a, b, c] at [specific part of the research process].
Please use the agent-authoring skill to guide me through the process,
and let me know what more detail would be useful to make sure this is
successful.
```

The workflow has five phases:

**Phase 1: Design (before writing).** This is where you get crystal clear on the fundamentals. The agent-authoring skill will make sure you can answer five critical questions:

1. What does this agent do and why does it exist? (one sentence)
2. Which pipeline stage(s) does it operate in?
3. Which existing agents are most similar, and how does yours differ?
4. Does it need file-write access (`general-purpose`) or is it read-only (`Plan`)?
5. Will it need to invoke any skills?

If any of these answers are vague, the agent-authoring skill will push you to sharpen them. This upfront clarity is genuinely important -- a poorly defined role leads to a poorly functioning agent.

**Phase 2: Author.** Write the agent definition file following the canonical 12-section template (defined in `agent_reference/AGENT_TEMPLATE.md`). The required sections include: Identity, Inputs, Core Behaviors, Protocol, Output Format, Boundaries, STOP Conditions, Anti-Patterns, Quality Standards, Invocation, References, and Consumers. The agent-authoring skill provides section-by-section guidance and a self-validation checklist covering everything from minimum anti-pattern counts to expected file length (400-700 lines).

**Phase 3: Integrate.** This is the step where the most things can go wrong if you're not careful. A new agent needs to be registered across multiple files in the DAAF ecosystem. The agent-authoring skill provides a complete integration checklist organized into tiers:

- **Tier 1 (Mandatory):** Every new agent must be registered in `.claude/agents/README.md` (the canonical agent registry, with entries in 4 sections: Agent Index, When to Use, Coordination Matrix, and Agent catalog)
- **Tier 2 (Conditional):** Additional updates if the agent maps to a specific pipeline stage
- **Tier 3 (Conditional):** Additional updates if the agent affects specific workflow areas

**Phase 4: Validate.** Verification checks to confirm cross-agent consistency and completeness. The skill provides specific grep commands to run.

**Phase 5: Human review.** This is non-negotiable. You *must* review the agent file yourself for accuracy, intention, completeness, and value before it's considered done.

### Key Resources

| Resource | Purpose |
|----------|---------|
| `agent-authoring` skill | Full workflow with integration checklist |
| `agent_reference/AGENT_TEMPLATE.md` | Canonical 12-section template |
| `.claude/agents/README.md` | Current agent landscape, commonly confused pairs, coordination matrix |

For changes to *existing* agents (modifying behavior rather than adding new ones), see [**05. Contributing to DAAF**](../CONTRIBUTING.md).

---

## Testing Your New Extension End-to-End

You've created a new skill (or agent). How do you know it actually works? Here's a practical testing sequence, ordered from lightest to heaviest.

### Data Discovery Test

The simplest test: can DAAF find your new skill and understand what it's for?

```
What data sources does DAAF know about? Can you tell me about
[your new data source]?
```

If the skill is properly placed, DAAF should be able to describe the data source, list key variables, and mention important caveats. If it can't find the skill or gives a generic response, verify that the skill's YAML frontmatter has a clear `description` field and that `SKILL.md` is in `.claude/skills/{skill-name}/`.

### Fetch Test

If your data source is accessible through the mirror system (or available as a local file), test that DAAF can actually retrieve and load the data:

```
Can you fetch [your data source] for [year] and show me the first
few rows and basic summary statistics?
```

This tests the data access pathway -- the dataset paths in your skill, the mirror configuration, and the basic loading mechanics. The fetch should complete with a CP1 validation (shape, types, missingness checks). If CP1 fails, it usually means the dataset path in your skill doesn't match what's actually available on the mirror, or the expected column structure differs from reality.

### Context Test

This tests whether your skill's coded value mappings, missing data codes, and caveats are being correctly applied during data cleaning:

```
Can you fetch and clean [your data source] for [year], making sure
to handle any coded missing values and apply the source-specific
caveats documented in the skill?
```

Watch the cleaning script that DAAF produces. It should reference the specific coded values, suppression patterns, and pitfalls documented in your skill. If it's treating -9 as a real numeric value instead of a missing data code, the coded value documentation in your skill may not be clear enough.

### Full Pipeline Test

The gold standard: run a simple research question that exercises your new skill through the entire pipeline.

```
Using [your new data source], can you analyze [simple, well-defined
research question]? Keep the scope narrow -- I just want to verify
the data flows through correctly.
```

Pick a question that's deliberately simple -- something like "What is the average [measure] by [grouping variable] for [year]?" You're not testing analytical sophistication here, you're testing integration. Does the data flow through fetch, clean, transform, and analysis without errors? Do the coded values get handled correctly? Does the report reference the right caveats?

### Methodology/Domain Skill Test

For non-data-source skills, the testing is more straightforward:

```
I'd like to run a [method from your new skill] analysis on
[some existing DAAF data]. Can you walk me through the approach?
```

Check that DAAF references your skill's guidance -- the correct function calls, the appropriate assumptions to validate, the known limitations to document.

---

## Submitting Your Extension for Inclusion

If you've created a useful skill or agent and want to share it with the broader DAAF community -- please do! The whole point of this being open-source is that the framework gets better as more people contribute their domain expertise. A skill you create for, say, health survey data or labor market statistics could save someone else weeks of profiling work.

### Before You Submit

A few things to check:

- **Quality:** Did you thoroughly review the Data Onboarding output and correct any preliminary interpretations? Skills with `[PRELIMINARY]` markers still in place aren't ready for sharing.
- **Completeness:** Does the skill follow the appropriate template (for data sources)? Does it have at least 2 decision trees? Is the Common Pitfalls section substantive?
- **Privacy:** Does the skill reference only publicly accessible data? If it was built from proprietary data, make sure the skill documentation doesn't leak any confidential information or values.
- **Testing:** Have you run at least a Discovery Test and a Fetch Test to confirm the skill works end-to-end?

### How to Submit

See [**05. Contributing to DAAF**](../CONTRIBUTING.md) for the full contribution workflow. The short version: fork the repository, add your skill files, update the registration entries, and submit a pull request. The contribution guide covers pull request formatting, quality standards, and the review process in detail.

If you're not comfortable with the pull request process, you can also [open an issue](https://github.com/DAAF-Contribution-Community/daaf/issues) describing your new skill and sharing the files -- the community can help get it integrated.

### LEARNINGS.md: The Other Way to Contribute

Even if you're not creating new skills, there's a contribution path that requires almost zero effort: **sharing your LEARNINGS.md files.** Every time DAAF completes a Full Pipeline project, it produces a LEARNINGS.md file documenting everything it learned about data quirks, process issues, and methodology edge cases along the way. These learnings are written to be immediately actionable -- they often contain specific suggestions for updating skills, improving documentation, or adding new pitfall entries.

You can also incorporate learnings directly into your own DAAF instance: start a new session and say "incorporate learnings" — Framework Development mode will scan your project LEARNINGS.md files, present a consolidated backlog of framework improvements, and walk you through implementing them.

To share learnings with the broader community, [open an issue](https://github.com/DAAF-Contribution-Community/daaf/issues) with your LEARNINGS.md content — the community can fold those insights back into the shared framework. This is genuinely one of the most impactful things you can do — every project run generates practical knowledge that benefits every future project.

---

## Customizing Your Python Environment

DAAF ships with a comprehensive Python data science stack (50+ packages covering statistics, econometrics, geospatial analysis, machine learning, visualization, and more). But research is unpredictable -- you may need a package we didn't anticipate. This section covers how to add Python packages, system-level libraries, and other software to your DAAF environment.

### The Recommended Path: Modify the Dockerfile

The best way to add packages is to ask DAAF to edit the `Dockerfile` and then rebuild the container. This is a multi-step process and involves one step that's easy to miss, so the rest of this section walks through the whole thing carefully.

**Why this approach is the right one** (rather than installing packages at runtime, covered further below):

- **Reproducible** -- anyone building from your Dockerfile gets the same environment, every time
- **Persistent** -- your packages survive container rebuilds, restarts, and updates
- **Permission-safe** -- Dockerfile installs run as root during the build process, so you never hit the permission restrictions that exist at runtime

#### The Container-Host Boundary (Read This First)

When DAAF is installed, the Docker image is built from files on your host computer, but the full DAAF codebase (including a copy of the Dockerfile) lives inside the Docker volume. This means **there are two copies of the Dockerfile and docker-compose.yml**, and they live in different places:

| Copy | Location | Who edits it | Who reads it |
|------|----------|--------------|--------------|
| **Volume copy** (inside the container) | `/daaf/Dockerfile` as seen from inside the running container | DAAF/Claude Code, while you're running a session | Nothing -- it's just a working copy inside the container |
| **Host copy** (on your computer) | Your `daaf-docker/` build directory on your host (wherever you ran the installer, or `daaf-main/Dockerfile` if you installed manually) | You, via a "copy back" command after DAAF finishes | `docker compose up -d --build`, when run from the host |

The two files start out identical, but they can drift apart as soon as either side is modified. Critically, **`docker compose up -d --build` only ever reads the host copy** -- it has no knowledge of the volume copy at all. But when you ask DAAF to add a package to the Dockerfile, DAAF edits the **volume copy** (the only one Claude can see and edit from inside the container).

**The fix is simple but easy to forget:** after DAAF edits the in-container Dockerfile (or docker-compose.yml), you need to copy that updated file back to the host build directory *before* running the container rebuild. The step-by-step process below walks through this carefully, and you should follow it exactly the first time.

#### Step-by-Step Process

**1. Ask DAAF to edit the Dockerfile.** Inside your DAAF session, ask Claude to add your package. For example:

```
I'd like to add networkx==3.4.2 to the Dockerfile so I can use
it for graph analysis. Please add it to the appropriate block.
```

DAAF will recognize this as a Framework Development task and pause for your approval before modifying the Dockerfile (modifying the Dockerfile is one of DAAF's "ask first" boundaries -- it never edits this file silently). You'll see exactly which block DAAF wants to add the package to and the version pin it's proposing. You can approve the change, adjust it, or ask DAAF to verify version compatibility against the existing pinned packages first -- a `uv pip compile` dry-run is a good safety check before committing to a rebuild, especially for packages with many transitive dependencies.

The Dockerfile organizes Python packages into several `RUN uv pip install --system` blocks with comment headers describing each category (core data science, econometrics, geospatial, visualization, ML). DAAF will pick the most appropriate block. Here's what the resulting block might look like for the `networkx` example:

```dockerfile
# Install core data science packages
RUN uv pip install --system \
    numpy==2.4.2 \
    pandas==3.0.0 \
    polars==1.38.1 \
    ...
    scikit-learn==1.8.0 \
    networkx==3.4.2
```

A few things to note about the Dockerfile syntax (DAAF will handle these for you, but it's helpful to recognize them when reviewing the proposed change):
- Every line in a `RUN` block except the last ends with a backslash (`\`) to continue the command
- Versions are pinned with `==` (e.g., `networkx==3.4.2`) for reproducibility -- DAAF can look up the latest version on [PyPI](https://pypi.org/) for you, or use a version you specify
- If you're unsure which version to pin, you can ask DAAF to use the latest compatible version, but pinning a specific version is strongly recommended

**2. Exit the container and rebuild.** After DAAF finishes editing the Dockerfile, exit Claude Code and the container, then run the rebuild script:

```bash
# Inside Claude Code
/exit

# Now you're back in the container shell (prompt looks like appuser@xxxx:/daaf$)
# Exit the container too
exit

# From your host terminal, navigate to your daaf-docker folder and rebuild
cd daaf-docker
bash rebuild_daaf.sh         # macOS / Linux
.\rebuild_daaf.ps1           # Windows
```

The rebuild script handles the tricky part automatically: it copies the updated Dockerfile and docker-compose.yml from inside the container back to your host build directory (where `docker compose` reads them), then rebuilds the Docker image. Docker uses **layer caching**, so only the changed layers are rebuilt -- you'll see the new package being downloaded and installed in the build output.

**Why is this step needed?** The Dockerfile lives in two places -- inside the Docker volume (where DAAF just edited it) and in your `daaf-docker/` folder on your computer (where `docker compose` reads it for builds). The rebuild script bridges this gap so the two copies stay in sync.

**3. Re-enter the container and verify.** After the rebuild completes, re-enter the container and confirm the package is available:

```bash
bash run_daaf.sh bash        # macOS / Linux
.\run_daaf.ps1 bash          # Windows
pip list | grep networkx
```

You should see your new package listed with the version you pinned. That's it -- your new package is now a permanent part of your DAAF environment, and it will survive future restarts and rebuilds (as long as you keep your host Dockerfile around, which you should be backing up periodically anyway).

<details>
<summary>Manual alternative (copy and rebuild by hand)</summary>

If you'd rather run the individual commands instead of using the rebuild script:

```bash
cd daaf-docker
docker cp daaf-daaf-docker-1:/daaf/Dockerfile ./Dockerfile
docker compose up -d --build
```

The copy step must come **before** the rebuild. You can also copy via Docker Desktop's GUI: Containers → expand `daaf` → click `daaf-daaf-docker-1` → Files tab → navigate to `/daaf/Dockerfile` → right-click → Save, and overwrite the host copy.
</details>

### Adding System-Level Dependencies

Some Python packages require underlying C libraries to compile or run correctly. Geospatial packages are the most common example -- `geopandas` needs GDAL, GEOS, and PROJ, which is why DAAF's Dockerfile already installs those system libraries via `apt-get`.

If you're adding a Python package that needs a system library, you'll need to ask DAAF to update **two** places in the Dockerfile:

**1. Add the system library** to the appropriate `apt-get install` block near the top of the Dockerfile:

```dockerfile
# ============================================
# Install System Dependencies (Git)
# ============================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    jq \
    git \
    poppler-utils \
    libfoo-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
```

**2. Add the Python package** to the appropriate `RUN uv pip install --system` block (as described above).

Both changes go in the same Dockerfile, so a single rebuild covers them both. After DAAF finishes both edits, follow Steps 2-3 from "Step-by-Step Process" above: exit the container, then run `bash rebuild_daaf.sh` (or `.\rebuild_daaf.ps1` on Windows) from your `daaf-docker` folder. The rebuild script copies the updated Dockerfile and docker-compose.yml from the container to the host and rebuilds the image in one step.

If you're unsure whether a Python package needs a system library, try adding just the Python package first -- the build will fail with a clear error message if a system dependency is missing, and you can ask DAAF to add the missing library then (and run `rebuild_daaf` again after the second edit).

### Runtime Installation for Quick Testing

Sometimes you just want to try a package quickly during a session without going through the rebuild process. You can do that:

```bash
uv pip install --user networkx
```

This installs the package into your user directory inside the container, which works because it doesn't require root privileges. You can start using the package immediately in your current session.

**Important caveat:** Runtime-installed packages are **ephemeral**. They are stored in the container's filesystem, not in the Docker volume where your research data lives. This means they will be **lost** when the container is rebuilt or restarted (e.g., after running `docker compose up -d --build` or `docker compose down` followed by `docker compose up -d`). Think of runtime installs as a test drive -- once you've confirmed the package works for your needs, add it to the Dockerfile to make it permanent.

The recommended workflow is:
1. Install at runtime to test: `uv pip install --user <package>`
2. Verify it works for your use case
3. Add it to the Dockerfile and rebuild to make it permanent

### Understanding the `uv` Package Manager

You may have noticed that DAAF uses `uv` rather than plain `pip` for package installation. `uv` is a fast, Rust-based Python package manager that's fully compatible with pip but significantly faster -- often 10-50x faster for large installs. The Dockerfile uses `uv pip install --system` (which installs packages system-wide during the build, when running as root). At runtime, since you're running as a non-root user, use `uv pip install --user` instead.

Both `uv` and regular `pip` work at runtime -- `pip install --user <package>` is equally valid. The main advantage of `uv` is speed, which matters more during Dockerfile rebuilds than during one-off runtime installs.

### Checking What's Already Installed

Before adding a package, you might want to check if it's already available. You have a few options:

- **Ask DAAF directly:** "What Python packages are installed?" -- DAAF can check for you
- **Run `pip list`** inside the container to see all installed packages
- **Run `pip show <package>`** to check if a specific package is installed and see its version
- **Read the Dockerfile** to see exactly what's pinned and organized by category

### Common Scenarios

**"I need networkx for graph analysis"**

Ask DAAF to add `networkx==3.4.2` (or your preferred version) to the core data science `RUN` block in the Dockerfile, then follow Steps 2-3 from "Step-by-Step Process" above (exit and run `rebuild_daaf`). No system dependencies needed.

**"I need a specific version of a package that's already installed"**

Ask DAAF to edit the version pin in the Dockerfile. For example, to change Polars from `1.38.1` to `1.39.0`, find `polars==1.38.1` and change it to `polars==1.39.0`. Then follow the same Steps 2-3 from "Step-by-Step Process" above (exit and run `rebuild_daaf`) -- the container-host boundary applies to version-pin edits exactly the same way it applies to new package additions. Be cautious with version changes -- other packages may depend on the currently pinned version, so test your analysis after upgrading. Ask DAAF/Claude Code to run a `uv pip compile` dry-run to test compatibility between all the package versions before committing to the rebuild.

**"I need an R package or want to use R"**

DAAF is a Python-based environment and does not include R. However, DAAF includes translation skills (`r-python-translation` and `stata-python-translation`) that can help you find Python equivalents for R or Stata operations you're familiar with. If you tell DAAF "I usually do this in R with dplyr," it can show you how to accomplish the same thing in Python with Polars.

**"I need a package that requires compilation and it's failing"**

Some packages need a C/C++ compiler or specific development headers. Ask DAAF to check the package's installation documentation for required system dependencies, add them to the `apt-get install` block in the Dockerfile, and (if not already present) add the Python package itself to the appropriate `RUN uv pip install --system` block. Then follow Steps 2-3 from "Step-by-Step Process" above (exit and run `rebuild_daaf`). Common examples include packages needing `build-essential`, `libhdf5-dev`, or database client libraries.

**"Can I use `apt-get` or `sudo` inside the running container?"**

No. The container runs as a non-root user (`appuser`) with all Linux capabilities dropped (`cap_drop: ALL`) and privilege escalation explicitly blocked. This is a deliberate security hardening measure -- it prevents both you and Claude from accidentally (or intentionally) making system-level changes at runtime that could compromise the container's integrity. All system-level software must be installed through the Dockerfile and built into the image.

---

## Recommended Next Steps

- [**05. Contributing to DAAF**](../CONTRIBUTING.md) — Get involved in developing DAAF! How to file issues via GitHub, support expanding the capabilities of the framework, contribute to educational tutorials and how-to's, and more!
- [**06. FAQ: Philosophy**](06_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**07. FAQ: Technical Support**](07_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, authentication errors, and other common errors
- [**Back to main**](https://github.com/DAAF-Contribution-Community/daaf/tree/main)
