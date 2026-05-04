# Changelog

All notable changes to DAAF for each release version are documented here, in reverse chronological order.

## Table of Contents

- [v2.1.0 — 2026-05-02](#v210--2026-05-02)
- [v2.0.1 — 2026-04-05](#v201--2026-04-05)
- [v2.0.0 — 2026-03-31](#v200--2026-03-31)
- [v1.0.0 — 2026-02-22](#v100--2026-02-22)

---

## v2.1.0 -- 2026-05-02

### Data Analyst Augmentation Framework -- Quality of Life Release

If v2.0.0 was about building out the reliaibility, robustness, and extensibility of DAAF's core analytical engine, v2.1.0 is about making it actually easy to set up, run, and maintain for real-world workflows and collaboration. For example, the original installation process asked users to juggle Docker commands, download and unzip GitHub repos, and manage the Docker volume filesystem. That friction was one of the biggest barrier to adoption, and this release implements a huge number of quality-of-life improvements to fix that. A single command now handles the entire installation. Named helper scripts replace every Docker incantation you'd need to remember and handles all of the back-end container management for you. A one-line update system means you can stay current without losing your work, regardless of when you installed DAAF for the first time. And a new session log viewer gives you a window into what DAAF is actually doing every step of the way, which is crucial for diagnostics and intuition when using the system.

Beyond the operations story, this release also sets up a number of smaller infrastructural improvements -- for example, specialist agents can return more detailed findings, and I've implemented a code-testing pipeline to help ensure every release of DAAF ships without unexpected issues or bugs. More details for the highlights of this release are listed out below!

### One-Line Installer

DAAF can now be installed with a single command on both macOS/Linux and Windows. The previous multi-step manual process has been replaced by a one-line installer that handles everything automatically -- downloading the necessary files, building the Docker image, and setting up your workspace.  Getting started with DAAF and Claude Code in a secure, well-curated, and fully reproducible environment for research has never been easier! This took a LOT of experimentation and testing, since these scripts are designed to be run on your computer, and I had to account for various versions of Windows, MacOSX, etc. etc. which is quite a headache.

### Helper Scripts for Everyday Operations

A complete suite of "helper" convenience scripts (available for both macOS/Linux and Windows) now makes it painless and straightforward to handle the most common DAAF operations. Instead of remembering Docker commands, you can simply run a script:

- **`run_daaf`** -- Start DAAF and Claude Code (automatically sets up the docker container and runs the main commands for you)
- **`update_daaf`** -- Update to the latest DAAF version available, backing up your work automatically before making changes, and helping you integrate framework changes and customizations together (more on that below)
- **`backup_daaf`** / **`restore_from_backup`** -- Save and restore snapshots of your entire DAAF workspace effortlessly. Also allows for painless sharing of entire repositories with colleagues!
- **`rebuild_daaf`** -- Rebuild the Docker image when needed to update configurations, library installs, updates, etc.
- **`view_logs`** -- Open the session log viewer in your browser to easily inspect and view what DAAF is doing at every step of its work (more on that below)
- **`run_vscode`** -- Open a full VS Code editor in your browser for browsing, editing, uploading, downloading, and reviewing files inside the container (more on that below)
- **`view_notebooks`** -- Open Marimo to browse your analysis notebooks

Every script has both a Bash (.sh, for MacOSX and Linux) and PowerShell (.ps1, for Windows) variant, and all are covered by automated tests and quality checks. This was, by far, the most time-consuming part of this release -- making cross-platform shell scripts that work reliably across macOS, Linux, and Windows is genuinely hard, and the number of edge cases to navigate and problem-solve for was humbling. I suspect there will still be some issues that I couldn't identify on my own, so please do let me know what errors and problems you encounter!

### Update and Migration Pathway

Existing DAAF users can now update to the latest version without losing their work or framework customizations in a very guided process. The `update_daaf` script automatically backs up your workspace before making any changes and uses intelligent file-change detection to handle file conflicts gracefully -- leaning on Claude Code itself to help resolve conflicts between your customizations and new framework updates. 

For anyone coming from an older version that doesn't have this script built-in (so anything before this very release), a dedicated `migrate_daaf` script detects your installation type, connects you to the update process, and gets everything organized in a guided walkthrough. Check the [Installation and Quickstart guide](user_reference/01_installation_and_quickstart.md#migrating-from-an-older-installation) for details -- just one line of code to run in your terminal to get caught up.

### Session Log Viewer

A new in-browser session transcript viewer makes it much easier to see what DAAF is doing under the hood and to diagnose issues when they arise. You can browse past sessions, search across transcripts, filter by session, and inspect individual tool calls -- all from a clean web interface. Launch it with the `view_logs` helper script. This has been genuinely useful for development too -- being able to trace exactly what happened in a subagent's session has saved hours of debugging.

### In-Browser VS Code (code-server)

DAAF now ships with a full VS Code editor (code-server) that runs inside the container and opens right in your browser. Before this, if you wanted to look at files DAAF produced -- scripts, data, reports, logs -- your options were scrolling through the terminal, digging through Docker Desktop's clunky file browser, or copying files out to your host machine. None of that is a great experience when you're trying to review an analysis or understand what happened during a session.

Now you just run `run_vscode` from your installation folder and a complete file editor and browser environment opens in your browser -- file tree, syntax highlighting, search across files, Git history, upload and download files, all of it. It comes pre-loaded with nine extensions (Python, GitLens, Git Graph, Rainbow CSV, Markdown support, and more) and a clean dark theme, so it's ready to use immediately. Everything stays inside the container's security boundary, and you don't need to change anything on your own computer to manage it.

This is one of those changes that sounds minor on paper but makes a huge difference in practice. DAAF produces a *lot* of artifacts over the course of a session, and being able to browse and inspect them in a real editor — instead of one file at a time in the terminal — makes reviewing work dramatically more natural. It's also a much friendlier way to explore the framework itself if you're learning how DAAF works or building new skills and agents.

### Environment Variable Support

DAAF now supports secure environment variable configuration via an `environment_settings.txt` file that lives on your host machine (outside the container and inaccessible to Claude). You can set API keys for Claude Code authentication, data source access, and alternative providers -- all in one place. The file is automatically loaded at container startup, and DAAF's safety system prevents Claude from ever reading or accessing it directly. An annotated example template (`environment_settings_example.txt` in your `daaf-docker/` folder) walks you through every option.

### OpenRouter Support (Experimental)

DAAF now supports running Claude Code through OpenRouter as an alternative to a direct Anthropic API key, opening the door for greater model and provider flexibility. Configuration is handled entirely through the `environment_settings.txt` file -- no code changes needed. Context window detection was also updated to correctly query OpenRouter's API for the real context length of whatever model you're running. **Note:** This integration is experimental. It works, but you may encounter rough edges. Direct Anthropic API access remains the recommended and most reliable option.

### Preliminary Phase Notes Persistence

Specialist agent findings (source research, data profiling, synthesis) are now saved to disk as complete markdown files in `output/preliminary_notes/`. Previously, DAAF's coordinator held compressed summaries in its own working memory -- which meant later stages of analysis were working from shortened versions of earlier findings. Now the full findings are saved to a file and later agents read directly from that file, so nothing is lost to summarization. This is a quiet change, but it meaningfully improves analytical continuity across long sessions.

### Shell Scripting Skill

A new `shell-scripting` skill teaches Claude the conventions and standards used across all of DAAF's helper scripts -- covering Bash, PowerShell, error handling, testing, and cross-platform gotchas. Five reference files (~2,200 lines total) cover everything from script templates to testing patterns. This means that when DAAF needs to write or modify shell scripts (or when contributors submit new ones), they'll follow consistent, well-tested patterns.

### Automated Testing and Quality Checks

New automated pipelines run on every proposed code change to help ensure that DAAF's helper scripts remain reliable as the project evolves:

- **Script quality scanning** catches common scripting errors and enforces DAAF-specific conventions automatically on every code change
- **Unit test suites** verify that both the Bash and PowerShell variants of every helper script behave correctly in isolation
- **Full lifecycle tests** exercise the complete workflow -- install, run, backup, update, rebuild, and migrate -- in a fresh Docker environment to catch problems that only appear when everything runs together
- **Pre-commit checks** flag scripting issues before they're even committed, so problems are caught as early as possible

### Under the Hood

- **Specialist agent word limits raised:** Agents can now return substantially longer findings (general agents doubled from 1,000 to 2,000 words; data profiling agents from 2,500 to 3,500), reducing the chance of truncated or incomplete results
- **Prompt caching enabled:** Repeated sessions now benefit from cached context via a new default Claude setting, improving token efficiency and reducing cost
- **Session log collection fixed:** The log collector now correctly finds all agent transcripts from a session, even when sub-agents never directly mention the project directory
- **System prompt trimmed:** Removed ~144 lines of illustrative examples from the always-loaded system prompt -- content that was consuming working memory on every single turn without adding operational value
- **Container startup simplified:** Git identity configuration moved into the image build itself, eliminating an extra startup step and simplifying the boot process
- **Claude Code updated** to version 2.1.112, from the latest pin of 2.1.87

### What's Coming Next

- **R Support** -- Bringing first-class R language support to DAAF, as well as dual-language handling for Python and R in tandem. Long time coming, but will be worth it!
- **Benchmarking tests** -- Creating an automated benchmarking process for DAAF with test cases for plan quality, code generation adherence, and quality checkpoint compliance: the beginning of systematic testing for how well different Claude models follow DAAF's conventions (and thus understanding what settings matter, and/or whether other models from other providers like open-source options are viable yet).
- **More video tutorials and walkthroughs** -- Expanding the library of guided video content

**Full Changelog**: [v2.0.1...v2.1.0](https://github.com/DAAF-Contribution-Community/daaf/compare/v2.0.1...v2.1.0)

---

## v2.0.1 — 2026-04-05

### Data Analyst Augmentation Framework — Minor Revisions

Minor revisions: Adds an explicit "User Support Mode" as DAAF's 9th engagement mode (with better documentation reading/routing for a variety of issues/questions related to DAAF, Claude Code, Docker, and Git), hardens session archiving in the event of accidental crash or unintended closes/session termination, improves user documentation with diagrams and extended content, and archives complete session logs for both sample projects (college selectivity analysis) for better transparency and future educational materials.

**Full Changelog**: [v2.0.0...v2.0.1](https://github.com/DAAF-Contribution-Community/daaf/compare/v2.0.0...v2.0.1)

---

## v2.0.0 — 2026-03-31

### Data Analyst Augmentation Framework — Gaining Altitude Release

DAAF v2.0.0 is a ground-up architectural overhaul driven by four reinforcing goals: greater **extensibility and customizability**, broad **methodological capability expansions**, heightened alignment with **reproducibility best practices as the default**, and improved **token efficiency**. The v1.0.0 framework worked, but it was overly monolithic and fragile; every session loaded thousands of lines of workflow documentation regardless of the task, and adding new capabilities (data domains, analytical methods, engagement patterns) required modifying deeply entangled files ad hoc every single time. v2.0.0 decomposes the system into modular, progressively-disclosed components that load just-in-time, so the orchestrator and agents see only what they need for the current task/mode at hand. This same modularity makes the framework straightforwardly extensible: new data domains, analytical skills, engagement modes, and agent types can be added by authoring self-contained files and running a registration checklist. Not only that, but the new Framework Development mode makes all of these processes and updates happen basically without effort; the meta-improvement systems are working fantastically (having used it extensively for this release!). The net effect is a system that uses context more efficiently, adheres to its own protocols more reliably, can cover far more methodological territory, and scales to new research domains without architectural friction. Finally, the addition of new modes like Ad Hoc Collaboration and Reproducibility Verification begin to move DAAF from a nascent proof-of-concept to a tool that can start to genuinely add value across many domains of the research and science community.

### The Headline Changes

- **Architecture:** `CLAUDE.md` shrinks from ~1,800 lines to ~500 lines of universal conventions. Orchestration logic moves into a dedicated `daaf-orchestrator` skill with reference files loaded just-in-time — so a light-lift Data Lookup session never loads the 1,950-line Full Pipeline spec. Monolithic workflow documentation is split into phase-specific files, each loaded only when the orchestrator reaches that phase. The research Plan document is decomposed into 3 purpose-specific files (Plan, Plan\_Tasks, State), allowing the orchestrator to hold strategy and status in context while referencing task details by path.

- **Engagement Modes: 4 to 8.** New modes: Data Onboarding (formerly Data Ingest, now a full orchestrated mode with API acquisition and multi-file support), Ad Hoc Collaboration, Reproducibility Verification, and Framework Development modes. Existing modes of Data Lookup (renamed from Targeted Assist), Data Discovery (renamed from Discovery), and Full Pipeline are greatly improved across the board.

- **Analytical Skills: 7 new library skills + 2 translation skills.** Each skill follows the same SKILL.md + deep references architecture, so adding support for a new library is a matter of authoring — not framework modification. New skills: statsmodels, pyfixest, linearmodels, scikit-learn (unsupervised + supervised + fairness), geopandas, svy (complex survey analysis), science-communication, plus a major expansion of the data-scientist methodology skill with 8 new reference files covering causal inference, descriptive analysis, survey analysis, geospatial, unsupervised, supervised ML, and statistical modeling. Two cross-language translation skills (r-python-translation, stata-python-translation) enable inline code annotations for users coming from R or Stata backgrounds, powered by a persistent user language preference system.

- **Citation Propagation and Verification.** A distributed citation flow spans the entire pipeline: 13 skills carry canonical citation blocks with inclusion thresholds, the research-executor tracks citations as it works, the orchestrator accumulates them in STATE.md, and the report-writer renders a four-subsection References section with rationale lines. A centralized `CITATION_REFERENCE.md` index covers ~30 methods and tools. A pre-launch audit verified 1,005 references across 46 files and corrected 58 errors (fabricated authors, incorrect API claims, deprecated parameters, dead URLs).

- **Claude Code Platform Adaptations.** Systematic adjustments to DAAF's infrastructure based on testing against Claude Code's actual runtime behavior: a new search-agent replaces generic Plan dispatches (which lacked reasoning depth), subagent transcripts are now archived alongside orchestrator sessions, the 250-character frontmatter truncation limit is accommodated with a two-tier description architecture, the Dockerfile is fully pinned and smoke-tested, and audit logs now carry per-agent identity for traceability.

- **Agent Architecture:** All agents relocated to `.claude/agents/` for native Claude Code discovery. Named agent dispatch replaces generic `subagent_type`, so each agent loads exactly its own protocol and preloaded skills — no wasted context on irrelevant behavioral instructions. Per-agent hook enforcement (`enforce-file-first.sh`) mechanically blocks direct Python execution in coding agents, ensuring protocol adherence at the infrastructure layer rather than relying on prompt compliance alone.

- **Research Integrity:** AI Use Disclosure section (GUIDE-LLM aligned) added to all reports. `CITATION.cff` for machine-readable software citation. Session metadata tracking (DAAF version, model ID, timestamps). Session log collection utilities. First-time user transparency statement on LLM limitations and researcher responsibility.

- **Self-Modification:** Framework Development mode + `framework-engineer` agent + `FRAMEWORK_INTEGRATION_CHECKLIST.md` make DAAF formally self-extensible. New skills, agents, and modes can be added through structured authoring and a registration checklist — the framework is designed to grow without requiring core rewrites.

---

### Painfully Detailed Changelog

Note that Claude absolutely had to help me write most of this, there were like 100 commits to shift through major changes on.

**Reading lens:** Nearly every change below serves one or both of two goals. _Token efficiency:_ reducing what gets loaded into context so agents see only relevant instructions and adhere to them more reliably. _Extensibility:_ making it easy to add new data domains, analytical methods, engagement modes, and agent types without modifying core framework files. These goals reinforce each other -- modular components are both cheaper to load and easier to extend.

#### 1. Core Architecture Streamlining

##### 1.1 Orchestrator Extraction and Progressive Disclosure

The most fundamental change in v2.0.0 is the extraction of orchestration logic from `CLAUDE.md` into the `daaf-orchestrator` skill (`SKILL.md` + 9 reference files). `CLAUDE.md` retains only universal execution philosophy, code style rules, project conventions, and safety boundaries -- content that applies to all agents equally. The orchestrator skill handles mode classification, user communication, subagent dispatch, and workflow coordination.

This enables far better **progressive disclosure**: the orchestrator loads only the reference file for the confirmed engagement mode, rather than ingesting thousands of lines of workflow documentation upfront. Each mode reference file is self-contained with its own invocation templates, gate definitions, PSU (Phase Status Update) templates, and escalation triggers.

Had to figure out a way to ensure that the daaf-orchestrator skill correctly got loaded only by the LLM assistant interacting directly with the user, and ensure that it does so reliably regardless of how the user starts the conversation (via some reminder hooks and checks). This'll be one of those things that's unfortunately annoyingly hard to port to other systems, because the way this works is currently very Claude Code specific. See 4.2 below for more information.

##### 1.2 Workflow Phase Decomposition

The monolithic `02_WORKFLOW_STAGES.md` (1,628 lines) and `03_SKILL_INVOCATIONS.md` (1,847 lines) are replaced by five phase-specific workflow files for the Full Pipeline Mode:

| File | Content |
|------|---------|
| `WORKFLOW_PHASE1_DISCOVERY.md` | Stages 1-3.5: Goal refinement, data exploration, source deep-dives, synthesis |
| `WORKFLOW_PHASE2_PLANNING.md` | Stages 4-4.5: Plan creation, plan verification |
| `WORKFLOW_PHASE3_ACQUISITION.md` | Stages 5-6: Data fetch, cleaning, QA |
| `WORKFLOW_PHASE4_ANALYSIS.md` | Stages 7-10: Transform, analysis, visualization, QA aggregation |
| `WORKFLOW_PHASE5_SYNTHESIS.md` | Stages 11-12: Report writing, final verification |

Each file contains stage-specific invocation templates, gate criteria, verification checklists, and PSU content. The orchestrator loads them progressively as execution advances through phases, which makes session restarts far more efficient and focused, with better instructional adherence along the way.

**Data Onboarding** also receives its own progressive workflow files in the same manner, now that it's been upgraded to a full-fledged mode

- `WORKFLOW_PHASE_DO_PROFILING.md` (~855 lines) — Parts A-D profiling protocol
- `WORKFLOW_PHASE_DO_AUTHORING.md` (~270 lines) — Skill authoring and validation

##### 1.3 Plan Document Decomposition

The research Plan document is split into three purpose-specific files:

| Document | Purpose |
|----------|---------|
| `Plan.md` | Research strategy, methodology, goals, hypotheses, scope decisions |
| `Plan_Tasks.md` | Executable Transformation Sequence — task blocks for subagent dispatch, organized in parallelizable waves |
| `STATE.md` | Session state for recovery — current stage, script status, gate status, blockers, session metadata |

This separation allows the orchestrator to hold `Plan.md` and `STATE.md` in full context while referencing `Plan_Tasks.md` only by path, significantly improving context efficiency for multi-stage sessions.

**New templates:** `PLAN_TASKS_TEMPLATE.md`, expanded `STATE_TEMPLATE.md`

##### 1.4 Deleted Legacy Files

| Removed File | Replacement |
|--------------|-------------|
| `agent_reference/01_PROTOCOLS.md` | Content distributed to `full-pipeline.md` and `session-recovery.md` |
| `agent_reference/02_WORKFLOW_STAGES.md` | Five `WORKFLOW_PHASE*.md` files |
| `agent_reference/03_SKILL_INVOCATIONS.md` | Inline in `WORKFLOW_PHASE*.md` files |
| `agent_reference/07_CONTEXT_MANAGEMENT.md` | Consolidated into `CLAUDE.md` and `daaf-orchestrator/SKILL.md` |
| `agent_reference/08_LESSONS_LEARNED.md` | Replaced by per-project `LEARNINGS.md` |
| `agent_reference/EXECUTION_CAPTURE.md` | Merged into `SCRIPT_EXECUTION_REFERENCE.md` |
| `agent_reference/PLAN_TEMPLATE_INGEST.md` | Deleted (Data Onboarding does not produce a Plan.md) |
| `scripts/md-outline.sh` | Deleted (superseded by direct file reads) |
| `agents/README.md` (old location) | Replaced by `.claude/agents/README.md` |

##### 1.5 File Renames

| Old Name | New Name |
|----------|----------|
| `04_BOUNDARIES.md` | `BOUNDARIES.md` |
| `05_VALIDATION_CHECKPOINTS.md` | `VALIDATION_CHECKPOINTS.md` |
| `06_ERROR_RECOVERY.md` | `ERROR_RECOVERY.md` |
| `SCRIPT_TEMPLATE.md` | `SCRIPT_EXECUTION_REFERENCE.md` |
| `data-ingest-mode.md` | `data-onboarding-mode.md` |
| `STATE_TEMPLATE_INGEST.md` | `STATE_TEMPLATE_ONBOARDING.md` |
| `discovery-mode.md` | `data-discovery-mode.md` |
| `targeted-assist-mode.md` | `data-lookup-mode.md` |
| `revision-mode.md` | `revision-and-extension-mode.md` |

---

#### 2. Expanded and Refined Engagement Modes (from 4 to 8)

##### 2.1 Data Onboarding Mode (formerly Data Ingest)

Elevated from a simple agent invocation to a fully orchestrated mode with its own state template, profiling protocol, and skill authoring workflow. The mode profiles datasets across four parts (Structural, Statistical, Relational, Interpretation) using up to 11 scripts, with orchestrator checkpoints after setup and after critical findings review.

**New in v2.0.0:**

- **API acquisition (DI-0):** Conditional phase for API-based data sources. The agent researches the API, writes an acquisition script, and stops for user review before execution (external network call boundary).
- **Multi-file support:** Two classification types — HORIZONTAL (same structure, union-able) and HIERARCHICAL (different entity levels, must be linked). Hierarchical mode adds per-file script suffixes, a cross-file inventory script, and a mandatory cross-level linkage test script.
- **Progressive disclosure:** Profiling protocol extracted to `WORKFLOW_PHASE_DO_PROFILING.md`, skill authoring to `WORKFLOW_PHASE_DO_AUTHORING.md` — loaded just-in-time.
- **Terminology:** "Phase A/B/C/D" renamed to "Part A/B/C/D" to avoid collision with Full Pipeline's use of "phases."
- **Verbosity standards:** Subagent output cap raised from 1,000 to 2,500 words. Scripts must print complete per-column stats — execution logs are archival with no size limit.
- **Skill quality targets:** New required `analytical-context.md` reference file (including mandatory "What is NOT Included" exclusion table and "Temporal Scope" section). Reference content targets 3x-6x the SKILL.md line count with a hard minimum floor of 3x. Per-file minimums (150-200+ lines).
- **Domain Assessment protocol:** Before authoring reference files, the engineer must identify analytical domains, group columns into clusters, and create dedicated topic-specific reference files for any domain requiring 50+ lines of explanation.
- **Exclusion documentation pipeline:** DI-1 intake collects known exclusions, profiling scripts extract exclusion statements from documentation ("does not include," "excludes," "limited to"), and `analytical-context.md` requires a structured exclusion table (minimum 2 entries).
- **Cross-dataset discovery:** A new authoring step globs for all sibling DAAF data source skills to identify complementary sources sharing join keys, with worked Polars join examples in the skill.
- **Edge case handling:** When profiling confirms no coded/sentinel values, `value-interpretation.md` is created instead of an empty `coded-values.md`, documenting negative value semantics, null patterns, and expected ranges.
- **Profiling script bundling:** Profiling scripts are now bundled with skills in a `scripts/` subdirectory for provenance.
- **Naming convention:** Formal `{domain}-data-source-{acronym}` pattern with validation regex.

##### 2.2 Ad Hoc Collaboration Mode (NEW)

A flexible, user-driven dispatch loop without fixed stages, gates, or mandatory deliverables. The orchestrator operates as a thought partner, responding to conversational questions or dispatching to specialized agents as needed. Thanks to Alberto Guzman-Alvarez and Preston Magouirk for the great nudging in this direction!

**Key features:**

- Deferred workspace creation — folder only created when first artifact is produced
- `SESSION_NOTES.md` as lightweight continuity artifact (replacing STATE.md)
- Orchestrator loads `data-scientist` skill directly (exception to the standard subagent-loads-skills pattern)
- 2,000-word agent output cap (vs. standard 1,000-word pipeline cap)
- Dispatch table mapping user needs to agents

##### 2.3 Reproducibility Verification Mode (NEW)

A four-stage workflow for re-executing an existing analysis and comparing outputs against originals:

| Stage | Activity |
|-------|----------|
| RV-1 | Intake, setup, notebook decompilation into individual scripts |
| RV-2 | Sequential re-execution with comparison |
| RV-3 | Report claim verification against reproduced data |
| RV-4 | Synthesis into Reproduction Report |

**Supporting infrastructure:**

- `decompile_notebook.py` — CLI tool to extract individual scripts from a marimo notebook with a `MANIFEST.md`
- `compare_execution_logs.py` — programmatic comparison of original vs. reproduced script execution logs (row counts, column counts, key statistics, checkpoint pass/fail)
- `collect_session_logs.sh` — finds and copies matching session transcripts into a project's `logs/` directory
- `normalize_project_dir.py` — batch path normalization across decompiled scripts
- `REPRODUCTION_REPORT_TEMPLATE.md` — the Reproduction Report serves as both deliverable and session state document
- Mode-specific behavioral overrides in `code-reviewer`, `data-verifier`, and `report-writer` agents

##### 2.4 Framework Development Mode (NEW)

Enables structured, auditable self-modification of DAAF framework components (skills, agents, modes, templates, hooks, configuration).

**Key features:**

- `framework-engineer` agent with six core behaviors: template fidelity, read-before-write, integration completeness, cross-file consistency, minimal disruption, draft-then-place
- `FRAMEWORK_INTEGRATION_CHECKLIST.md` — canonical registration-point checklist for all component types (skills, agents, modes) with mandatory and conditional items
- Two checkpoints: after scoping (confirm approach) and after review pass (approve final state)
- Bidirectional escalation paths to/from all other modes
- **LEARNINGS.md feedback loop:** New "Incorporate Learnings" work type closes the gap between System Update Action Plans generated at project completion and their consumption back into the framework. A 3-subagent exploration protocol scans all `research/*/LEARNINGS.md` files, checks which items have already been addressed, and proposes prioritized execution order. Full Pipeline and Data Onboarding delivery messages proactively suggest Framework Development mode when action plan items exist.

This works so darn well, I'm really mad I didn't make this sooner! It's made the last legs of development on DAAF v2.0.0 so, so, so much better.

##### 2.5 Data Lookup Mode (renamed from Targeted Assist)

Renamed for clarity — the previous name was ambiguous about the mode's purpose. No behavioral changes; purely a nomenclature improvement.

##### 2.6 Data Discovery Mode (renamed from Discovery)

Renamed for disambiguation from the general concept of "discovery." No behavioral changes.

##### 2.7 Revision and Extension Mode (expanded from Revision Mode)

- Renamed to clarify that the mode handles both fixing existing work and extending it with new analyses
- Added formal escalation triggers, output format (Revision Status Update template), and session recovery guidance
- Added "AI Use Disclosure in Revisions" section for disclosure inheritance across versions

##### 2.8 Mode Confirmation Hard Gate

A formal "HARD GATE" is introduced at mode classification: the orchestrator must confirm the mode with the user and receive explicit approval before proceeding. A **Turn Boundary Rule** enforces that no reference files are loaded and no subagents are dispatched in the same turn as the confirmation message. A **Confirmation Self-Check** checklist validates compliance.

---

#### 3. Agent Architecture

##### 3.1 Agent Relocation

All agent definition files moved from `agents/` to `.claude/agents/` to leverage Claude Code's native subagent discovery mechanism. The old `agents/` directory and its 1,180-line README are removed.

A new `.claude/agents/README.md` (~630 lines) serves as the agent index with key inputs, outputs, and cross-references. This also allows the Orchestrator to more efficiently launch agents with pre-loaded agent protocols and default Skills, saving tokens and improving adherence.

##### 3.2 Named Agent Dispatch

All `subagent_type` values changed from generic strings (`"general-purpose"`, `"Plan"`) to agent-specific names (`"research-executor"`, `"code-reviewer"`, `"data-planner"`, etc.). Claude Code automatically loads the agent's protocol file and applies its `tools` and `permissionMode` settings.

##### 3.3 New Agents

| Agent | Purpose |
|-------|---------|
| `framework-engineer` | Framework artifact authoring and integration (Framework Development Mode) |
| `search-agent` | DAAF-native read-only explorer replacing generic `Plan` dispatches across all modes (see §11.1) |
| `data-ingest` (expanded) | Dataset profiling with multi-file and API support (Data Onboarding Mode) |

##### 3.4 Agent Invocation Template Consolidation

Invocation templates were removed from individual agent files and consolidated into the canonical `WORKFLOW_PHASE*.md` files, eliminating hundreds of lines of duplication. Agent files now focus exclusively on behavioral protocol and anti-patterns.

##### 3.5 Universal Tool Access

The `Skill` tool was added to all 14 agent frontmatter `tools` lists, enabling direct skill invocation from any agent. The `debugger` also gained `WebFetch` and `WebSearch`.

---

#### 4. Enforcement Infrastructure

##### 4.1 File-First Execution Hook (`enforce-file-first.sh`)

A PreToolUse hook that mechanically blocks direct `python`/`python3` invocations, enforcing the file-first execution protocol at the hook layer. Registered per-agent (research-executor, code-reviewer, debugger, data-ingest) rather than globally. Uses fail-closed design with an ERR trap. Framework utility scripts in `/daaf/scripts/` are whitelisted. Currently scoped narrowly to code agents in the pipeline, though we may want to consider adding to the orchestrator and all agents eventually (just gets complicated with things like Marimo notebooks and other utility scripts).

##### 4.2 Orchestrator Loading Enforcement

Two new hooks ensure the `daaf-orchestrator` skill is loaded at session start:

- `remind-orchestrator.sh` (UserPromptSubmit) — injects a reminder if the skill hasn't been loaded
- `flag-orchestrator-loaded.sh` (PostToolUse on Skill) — writes a session flag when loaded, silencing reminders

##### 4.3 Claude-Code-Guide Denial (`deny-claude-code-guide.sh`)

Blocks the built-in `claude-code-guide` subagent type (Haiku model) from being dispatched within DAAF, as it lacks the reasoning depth for framework-aware work and often is just plain wrong. Hook suggests we launch a search-agent to look directly at the Claude Code documentation online via websearch and webfetch tools. Provides alternative guidance. It's such a good idea with such bad execution; why did they do it like this?

##### 4.4 Context Reporter Improvements

- Time-based rate limiting (60-second injection interval) replacing content-based deduplication
- Human-readable timestamps in utilization messages
- Baseline estimate adjusted from 40k to 20k tokens
- **Subagent support fix:** The hook relied on a session-specific cache file for `MAX_CONTEXT` that did not exist for subagents (different session IDs). Fixed with a fallback chain that finds the parent orchestrator's cache. `CLAUDE.md` expanded with subagent-specific threshold-action table, early return protocol (5 required elements: file paths, findings summary, incomplete task list, decisions/assumptions, confidence assessment), and STATE.md coordination guidance for subagents returning under context pressure.
- Adjusted context utilization thresholds to be either percentages OR raw token counts at 150k, 200k, and 250k. While Opus and Sonnet can now handle token windows of up to 1m tokens, there's A LOT of evidence that its performance deteriorates quickly -- and regardless, costs skyrocket per turn because of it. May need to revisit later.

##### 4.5 Logging and Audit

- Session log exclusion removed from `.claudeignore` — transcripts now visible for reproducibility collection
- Edit/Write deny rules added for `.claude/logs/` to prevent audit log modification
- `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS: "1"` added to settings
- **Per-agent audit traceability:** `agent_type` and `agent_id` fields added to every JSONL audit log entry, enabling post-session filtering by specific agent. Orchestrator calls default to `"orchestrator"`; subagent calls populate the actual agent type and unique ID.
- Added some utility scripts that automatically pull in copies of relevant session logs into a given project for full auditability in the full pipeline mode.

---

#### 5. Analytical Skills

##### 5.1 New Python Library Skills

| Skill | Lines (SKILL.md + refs) | Key Coverage |
|-------|------------------------|--------------|
| **statsmodels** | ~4,300 | OLS/WLS/GLS, GLM (logit, probit, Poisson, NB), robust regression, ARIMA/SARIMAX/VAR, mixed effects, diagnostics, hypothesis testing |
| **pyfixest** | ~2,400 | High-dimensional FE (OLS/IV/Poisson), DiD (TWFE, did2s, lpdid, Sun-Abraham), wild bootstrap, publication tables via `etable()`. Targets v0.40.0 with breaking-change documentation. |
| **linearmodels** | ~2,900 | PanelOLS (FE/RE), BetweenOLS, FirstDifferenceOLS, Fama-MacBeth, IV2SLS/LIML/GMM, SUR, IV3SLS, asset pricing. Cross-library syntax comparison tables. |
| **scikit-learn** | ~3,000 | KMeans, DBSCAN, HDBSCAN, PCA, t-SNE, UMAP, GMM (unsupervised). Logistic regression, random forest, gradient boosting, SVM, Ridge/Lasso (supervised). Preprocessing, pipelines, cross-validation, feature selection. Targets v1.8.0. |
| **geopandas** | ~3,400 | GeoDataFrames, spatial joins, CRS/projections, raster integration (rasterio, xarray), PySAL ecosystem (Moran's I, LISA, spatial regression), visualization (matplotlib + contextily, folium, lonboard). Targets v1.1.3. |
| **svy** | ~1,700 | Complex survey data analysis: design specification (strata, PSU, weights, FPC), variance estimation (Taylor linearization, BRR, jackknife, bootstrap), survey-weighted GLM regression (gaussian, binomial, Poisson), domain/subpopulation estimation, calibration, survey data I/O. Targets v0.13.0 (supersedes archived samplics). |
| **science-communication** | ~1,700 | Audience analysis, narrative frameworks (Pyramid Principle, SCQA, AIDA), plain-language translation, hedging/uncertainty (IPCC calibrated), deliverable templates (executive summary, policy brief), accessibility/equity, pre-release review checklist. |

Each skill follows the SKILL.md + deep references architecture with decision trees for routing and explicit boundary documentation against sibling skills.

##### 5.2 Cross-Language Translation Skills and User Language Preferences

Two translation skills provide verb-by-verb mappings from R and Stata to their Python equivalents, enabling inline code annotations for users with non-Python backgrounds.

| Skill | Lines (SKILL.md + refs) | Key Coverage |
|-------|------------------------|--------------|
| **r-python-translation** | ~7,400 | tidyverse → polars, ggplot2 → plotnine, fixest → pyfixest, survey → svy, sf → geopandas, plm → linearmodels. Paradigm differences, gotchas, external resources. |
| **stata-python-translation** | ~8,700 | Data management, strings/dates/labels, regression modeling, causal inference, visualization, survey/spatial/ML, workflow/environment. Mirrors the R skill architecture. |

**User Language Preference System:** A persistent, cross-session preference mechanism stored in `CLAUDE.md` § User Preferences. The orchestrator detects R/Stata background signals (explicit: "I use R"; implicit: R/Stata syntax in pseudocode), proposes persisting the preference, and silently propagates a translation directive to all 4 code-producing agents (research-executor, code-reviewer, debugger, data-ingest) across all sessions. Wired into 5 mode reference documents and 2 workflow phase invocation templates.

##### 5.3 Supervised ML Track

- New `supervised-ml.md` methodology reference for the `data-scientist` skill covering prediction vs. inference (Shmueli 2010), bias-variance tradeoff, cross-validation strategies, model selection, feature importance caveats, algorithmic fairness impossibility theorems, and reporting standards
- New `scikit-learn/references/interpretation.md` — SHAP (TreeExplainer, KernelExplainer), permutation importance, partial dependence, ICE plots
- New `scikit-learn/references/fairness.md` — fairlearn MetricFrame, ThresholdOptimizer, ExponentiatedGradient, demographic parity, equalized odds
- LightGBM and XGBoost sections added to classification and regression references
- Supervised ML routing wired into Full Pipeline modeling library selection

##### 5.4 Data-Scientist Skill Expansion

The `data-scientist` skill was restructured from a single "statistical analysis" routing branch into seven methodology-specific routing trees with eight new reference files (~5,050 lines total):

| Reference File | Coverage |
|---|---|
| `causal-inference.md` | DAGs, potential outcomes, RCT, IV/2SLS, RD, DiD, synthetic control, matching/PSM |
| `descriptive-analysis.md` | Summary statistics, distributions, cross-tabulations, temporal patterns |
| `statistical-modeling.md` | Model selection, assumption checking, diagnostics |
| `survey-analysis.md` | Complex survey design anatomy, weight selection, variance estimation methods, domain estimation, plausible values, survey-weighted regression, federal survey reference table, pitfalls checklist |
| `exploratory-unsupervised.md` | Clustering, PCA, nonlinear embeddings, cluster validation |
| `supervised-ml.md` | Prediction vs. inference, cross-validation, fairness, reporting |
| `geospatial-analysis.md` | MAUP, CRS, spatial autocorrelation, spatial regression |
| `geospatial-operations.md` | Spatial joins, weights, LISA, interpolation, zonal statistics |

A ~125-row topic index in SKILL.md maps specific analytical topics to the correct reference file. Beefy, but definitely worthwhile and still extensible.

##### 5.5 Modeling Library Pipeline Wiring

- `data-planner` task specs now require a `<skill>` element specifying the modeling library
- `research-executor` skill loading tables updated with conditional library loading and fallback rules
- `debugger` gains a "Modeling Library Gotchas" section with per-library failure mode summaries
- `report-writer` gains conditional Step 5.5 for science-communication skill loading when target audience is non-technical
- `PLAN_TEMPLATE.md` gains a "Target Audience" field controlling communication skill routing

---

#### 6. Research Integrity and Attribution

##### 6.1 AI Use Disclosure (GUIDE-LLM Alignment)

A structured AI Use Disclosure section is added to all reports, mapping to the GUIDE-LLM v2026 reporting checklist (Feuerriegel et al.). `AI_DISCLOSURE_REFERENCE.md` maps every checklist item (A.1 through G.1) to its DAAF artifact source, tagged as `[AUTO]` (auto-populated by report-writer) or `[RESEARCHER]` (requires human completion).

Session metadata (DAAF version via git commit hash, model ID, session dates, transcript path) is captured in STATE.md at project setup and passed through to the report-writer.

AI disclosure guidance is added for all modes — including Data Discovery, Data Lookup, Revision and Extension, and Reproducibility Verification.

##### 6.2 Citation Framework

- `CITATION.cff` — machine-readable software citation (CFF standard) identifying DAAF 2.0.0 as citable software
- APA and BibTeX citation formats in README
- Layered citation guidance (DAAF + Claude + data sources + GUIDE-LLM)
- "Software & Tools" citations sub-section in report template
- FORCE11 software citation principles alignment

##### 6.3 Citation Propagation System

A distributed citation flow that tracks methodological and software attribution across the entire pipeline, from skill loading through report generation:

1. **Skill-level citation blocks:** 13 skills now carry `## Citation` sections with canonical citation text, "Cite when" / "Do not cite when" inclusion thresholds, and secondary citation guidance.
2. **Research-executor tracking:** New `Citation Tracking` core behavior and `Citations` output section. The executor reports a table of `software`/`method` type citations with rationale as part of its return format.
3. **Orchestrator accumulation:** STATE.md gains a `Citations Accumulated` section with four tables (Data Sources, Methodological References, Software & Tools, Reporting Standards). DAAF, marimo, and GUIDE-LLM are pre-populated at project setup.
4. **Report-writer rendering:** The References section is now sourced from STATE.md (not verbatim Stage 6 text) and rendered as four subsections with "_Cited because:_" rationale lines for non-data-source entries.
5. **Verification:** The data-verifier gains a citation verification step. `CITATION_REFERENCE.md` serves as a centralized index covering ~30 methods and tools with inclusion thresholds and a parsimony principle ("A report with 5 well-justified citations is better than one with 30 perfunctory ones").

User-facing documentation (first-run transparency statement, Understanding DAAF guide, Best Practices guide) updated to explain the References section and advise researchers that citations are "best-effort, not guaranteed."

##### 6.4 Pre-Launch Citation Audit

A systematic audit verified 1,005 citations, references, URLs, and attributed API claims across 46 skill reference files in 12 skill areas. 58 corrections applied:

- **HIGH (5):** Fabricated author names, wrong page numbers, reversed author order, wrong journal name
- **MEDIUM (19):** Incorrect API claims across polars (6), statsmodels (3), linearmodels (3), marimo (3), scikit-learn (1), plotnine (1), plotly (2)
- **LOW (32):** Outdated claims, deprecated parameters, incomplete option lists, dead URLs

---

#### 7. Skill Metadata and Authoring

##### 7.1 Controlled Vocabulary

Formal controlled vocabulary defined for skill frontmatter:

- `audience`: `any-agent`, `research-orchestrator`, `research-planner`, `research-coders`, `research-writers`
- `domain`: `data-source`, `data-access`, `data-documentation`, `python-library`, `research-methodology`, `research-orchestration`, `research-communication`, `skill-development`
- Standard keys: `library-version`, `skill-authored`, `skill-last-updated`

Applied uniformly across all 35 skill files with description enrichment.

##### 7.2 Skill Authoring Guide Updates

- "Concise is Key" replaced with "Right-Size Each Level": SKILL.md concise, reference files comprehensive
- Reference file density guidelines: 3x-6x ratio of reference lines to SKILL.md lines
- Anemic reference files flagged as harmful as bloated SKILL.md files
- Data source skill naming convention: `{domain}-data-source-{acronym}` with validation regex
- **250-character frontmatter limit accommodation** — see §11.2

---

#### 8. User Experience

##### 8.1 Tone and Voice Standards

Comprehensive tone specification added to the orchestrator:

- **Warm:** Encouraging, acknowledges good questions, celebrates interesting findings
- **Thoughtful:** Explains _why_ things matter, connects dots between phases
- **Patient and methodical:** Never rushes past decision points, confirms understanding
- **Educational:** Explains data caveats and methodology tradeoffs as they arise
- **Direct but not terse:** Concise without being cold
- **Honest about uncertainty:** Plain acknowledgment of ambiguity and limitations

##### 8.2 Plain-Language Communication

A translation table maps internal terminology to user-facing language (e.g., "PSU" becomes "phase checkpoint," "QA" becomes "quality review," "Stage N" becomes "step" or activity description). Internal terms like "Composite execution pattern" and "Gate GN" are never exposed.

##### 8.3 Welcome Preamble

Every conversation begins with a brief introduction to DAAF. An expanded orientation is triggered on newcomer signals ("how does this work," "what can you do"). Context-sensitive help table maps user signals to appropriate documentation files.

##### 8.4 First-Time User Transparency Statement

A first-run onboarding hook detects new users (via `activity.log` session count) and presents a candid transparency statement before the normal welcome flow. The statement covers what DAAF is and isn't, inherent LLM limitations (hallucination, sycophancy, over-confidence, non-determinism), the probabilistic nature of DAAF's quality improvements, the primacy of researcher expertise, and practical guidance for new users. Delivered in conversational tone, not as a terms-of-service wall.

---

#### 9. Infrastructure and Environment

##### 9.1 Dockerfile

New package layers for:

- **Econometrics:** linearmodels, rdrobust, marginaleffects, arch, pydynpd, svy
- **Geospatial:** geopandas, rasterio, xarray, rioxarray, contextily, folium, libpysal, esda, spreg, mapclassify, rasterstats, geopy, osmnx
- **Geospatial system libraries:** libgdal-dev, gdal-bin, libgeos-dev, libproj-dev (required by fiona, a transitive dependency of rasterstats)
- **ML:** shap, fairlearn, lightgbm, umap-learn
- **Utilities:** poppler-utils (PDF support), tabulate, great-tables, wildboottest, fastexcel

**Post-smoke-test stabilization:** 16 previously-floating packages pinned to exact versions for reproducible builds. `samplics` removed (superseded by svy). `kaleido` removed (Chromium dependency incompatible with container; plotly skill updated with workaround guidance to use plotnine for static figures). A follow-up smoke test run (246 tests) corrected additional skill documentation in pyfixest, svy, and plotly. Docker volume permissions fixed for macOS (named volumes with root ownership blocking `appuser`).

Model configuration updated to `claude-opus-4-6[1m]` (1M context window).

##### 9.2 New Utility Scripts

| Script | Purpose |
|--------|---------|
| `scripts/decompile_notebook.py` | Extract individual scripts from a marimo notebook |
| `scripts/compare_execution_logs.py` | Compare original vs. reproduced execution logs |
| `scripts/collect_session_logs.sh` | Find and copy matching session transcripts |
| `scripts/normalize_project_dir.py` | Batch path normalization across decompiled scripts |

##### 9.3 Installation Simplification

Git removed as a host-machine prerequisite. Installation now uses ZIP download (`curl`/`Invoke-WebRequest`) instead of `git clone`, reducing prerequisites from four to three. `docker-compose.yml` gains `name: daaf` for folder-independent volume naming (ZIP extracts to `daaf-main/` rather than `daaf/`). Update procedure rewritten with ZIP-based commands that copy framework files into the Docker volume while preserving the `research/` folder.

##### 9.4 CLAUDE.md Philosophy

The Identity section was expanded from a brief description to a full philosophical statement: DAAF as a "force-multiplying exo-skeleton," the five core requirements (Transparent, Rigorous, Reproducible, Responsible, Scalable), and the primacy of human researcher judgment.

---

#### 10. Documentation

##### 10.1 New Reference Files

| File | Purpose |
|------|---------|
| `AI_DISCLOSURE_REFERENCE.md` | GUIDE-LLM checklist mapping for all modes |
| `FRAMEWORK_INTEGRATION_CHECKLIST.md` | Registration-point checklists for skills, agents, modes |
| `MODE_TEMPLATE.md` | Template for authoring new engagement modes |
| `PLAN_TASKS_TEMPLATE.md` | Template for the task-block document |
| `REPRODUCTION_REPORT_TEMPLATE.md` | Template for Reproducibility Verification output |
| `STATE_TEMPLATE_ONBOARDING.md` | State template for Data Onboarding mode |
| `CITATION_REFERENCE.md` | Citation index for pipeline citation propagation and verification |

##### 10.2 Expanded Templates

- `AGENT_TEMPLATE.md` — expanded with per-agent hook registration, skills-in-frontmatter guidance
- `DATA_SOURCE_SKILL_TEMPLATE.md` — API data access skeleton, multi-file structure section, analytical-context.md requirement
- `MODE_TEMPLATE.md` — expanded from 6-item to 13-item checklist with naming conventions and exemplar references
- `REPORT_TEMPLATE.md` — AI Use Disclosure section, Software & Tools citations
- `STATE_TEMPLATE.md` — session metadata, per-script QA status, gate status tracking

##### 10.3 User Documentation Updates

All files in `user_reference/` updated to reflect eight engagement modes, three-document Plan structure, Data Onboarding capabilities, and Framework Development mode. Best practices and extending-DAAF guides revised.

---

#### 11. Claude Code Platform Adaptations

Changes driven by testing DAAF against Claude Code's actual runtime behavior, addressing platform constraints and improving observability.

##### 11.1 search-agent Replaces Generic Plan Dispatches

Generic `Plan` subagent dispatches lacked reasoning depth for DAAF's domain-aware exploration tasks. A new `search-agent` (413-line agent definition, full 12-section template) serves as DAAF's 14th agent — a broad-purpose, read-only explorer with web access (WebSearch, WebFetch) and skill-aware domain knowledge. All exploration dispatches across Data Discovery, Data Lookup, Framework Development, and Full Pipeline modes changed from `Plan` to `search-agent`. The `Plan` generic type is de-prioritized rather than removed. The `Explore` subagent type remains blocked (runs on Haiku); error messages now recommend `search-agent`.

##### 11.2 Frontmatter Description Truncation Accommodation

Claude Code silently truncates skill frontmatter `description` fields at ~250 characters. All 35 DAAF skills (previously 381-813 chars) were losing trigger and disambiguation text without any visible error. All descriptions condensed to fit within 250 characters. Full descriptions preserved as plain paragraphs immediately after the `# Title` heading in each SKILL.md body. The skill-authoring reference (`frontmatter.md`) updated with the 250-char hard limit, budget priorities, and the "Full Description in Body" pattern.

##### 11.3 Subagent Transcript Archiving

Previously, only the orchestrator's session transcript was archived. A new observability pipeline captures subagent activity:

- **`subagent-registry.sh`** — new `SubagentStop` hook records each subagent's metadata (agent\_type, agent\_id, transcript\_path, tool\_uses, duration) to a per-session JSONL registry file
- **`archive-session.sh` expansion** — at session end, copies each subagent's JSONL transcript into the archive with `_subagent_{id}` suffixes, renders companion Markdown files, and appends a "Subagent Activity" summary table to the orchestrator's Markdown archive
- **Unified naming convention:** `{date}_{time}_{session}_orchestrator.{jsonl,md}` and `{date}_{time}_{session}_subagent_{id}.{jsonl,md}` — all files from one session sort together

##### 11.4 Script Execution Portability

- `run_with_capture.sh` changed from `python` to `python3` for PEP 394 portability
- Copy-into-project pattern eliminated across 17 files — all execution now references the canonical copy at `{BASE_DIR}/scripts/run_with_capture.sh` rather than per-project copies
- Shell script executable permission convention established: all `.sh` files must be committed with mode `100755` via `git update-index --chmod=+x`, documented across 6 framework files (CLAUDE.md, framework-engineer agent, integration checklist, script execution reference, skill-authoring reference, framework-development mode)

---

### Breaking Changes Summary

These changes affect the internal framework structure. External users consuming DAAF analyses are unaffected.

| Change | Impact | Migration |
|--------|--------|-----------|
| `CLAUDE.md` reduced to conventions only | Orchestration logic must be loaded via `daaf-orchestrator` skill | Load skill at session start (enforced by hooks) |
| Agents moved from `agents/` to `.claude/agents/` | Path references must update | All internal references updated |
| `subagent_type` changed to agent-specific names | Orchestrator dispatch must use named agents | All invocation templates updated |
| Plan split into Plan + Plan\_Tasks + State | Existing single-Plan projects structurally incompatible | Create Plan\_Tasks.md and STATE.md from existing Plan |
| Multiple reference files renamed/deleted | Hardcoded path references break | See File Renames table above |
| "Data Ingest" renamed to "Data Onboarding" | Mode name references must update | All internal references updated |
| "Phase A/B/C/D" renamed to "Part A/B/C/D" | Data Onboarding terminology must update | All internal references updated |
| Direct `python` calls blocked in coding agents | Must use `run_with_capture.sh` wrapper | Already enforced by hook |
| `claude-code-guide` subagent blocked | Cannot dispatch Haiku-based guide agent | Use `search-agent` (has WebFetch/WebSearch) |
| Generic `Plan` dispatches replaced by `search-agent` | Exploration tasks use named agent | All invocation templates updated |
| `run_with_capture.sh` path changed from `{PROJECT_DIR}` to `{BASE_DIR}` | Per-project copy references break | All execution now uses `{BASE_DIR}/scripts/run_with_capture.sh` |

**Full Changelog**: [v1.0.0...v2.0.0](https://github.com/DAAF-Contribution-Community/daaf/compare/v1.0.0...v2.0.0)

---

## v1.0.0 — 2026-02-22

### Data Analyst Augmentation Framework — Launch Release

The initial public release of DAAF, an open-source, extensible AI-augmented research workflow for Claude Code that allows skilled researchers to rapidly scale their expertise and accelerate data analysis — without sacrificing transparency, rigor, or reproducibility.

#### Core Framework

- Multi-stage research pipeline with mandatory validation and quality checkpoints at every stage
- Specialized agents that tackle each stage of the research pipeline with specific insights, strategies, and expertise (e.g., research-executor, code-reviewer, data-planner, plan-checker, data-verifier, source-researcher)
- Per-script QA with adversarial code review where every transformation has a validation, and all data operations are stored in a file-first format for maximum auditability

#### Skills Ecosystem

- Analytical tools for data analysis: Polars, plotnine, Plotly, marimo, data-scientist
- Data sources: 15 source-specific data skills (CCD, IPEDS, CRDC, Scorecard, EDFacts, MEPS, SAIPE, FSA, NHGIS, NCCS, PSEO, EADA, NACUBO, Campus Safety) plus query, explorer, and context skills, to answer hundreds of meaningful research questions about education out-of-the-box
- Extensibility tools to easily expand the data domains to any field/dataset you need

#### Documentation

- User guides: installation/quickstart, understanding DAAF, best practices, extending DAAF, philosophy FAQ, technical FAQ
- 10-minute demo video walkthrough
- Complete example project for review (College Graduation Rate Selectivity Analysis)

#### Infrastructure

- Docker containerized environment with defense-in-depth security
- Pre-commit hooks, audit logging, session archiving
- LGPL-3.0 license (core framework open; extensions can be proprietary)
