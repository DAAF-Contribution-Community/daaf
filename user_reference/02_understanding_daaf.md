# 02. Understanding and Working with DAAF

This guide is designed to turn a new user into a confident user. It expands on the README and installation guide's brief overview into a thorough walkthrough of how DAAF works, what it produces, what to expect, where it can fail, and how to think about AI-assisted research analysis for your workflows more critically. This will guide you through your first real analysis with DAAF to understand what's happening under the hood, and suggest further testing pathways to really get comfortable with the strengths and weaknesses of DAAF.

> **Quick tip before you begin**: If you have any questions, concerns, issues, or confusion about **anything** you read in this guide: Ask Claude for help! Point it to any document, section, or sentence, and then ask it to help you understand it better. It has visibility into the whole project documentation at-will, so it should be able to help you out as you go. This kind of personalized assistance should be invaluable for anyone getting onboarded into using DAAF and Claude Code more generally!

[**Back to main**](https://github.com/DAAF-Contribution-Community/daaf/tree/main)

---

## Table of Contents
- [**Core Concept: Context Windows and Prompt Engineering 101**](#core-concept-context-windows-and-prompt-engineering-101)
- [**The Six Engagement Modes**](#the-six-engagement-modes)
- [**The Mental Model: Orchestrator, Agents, Skills, Validation**](#the-mental-model-orchestrator-agents-skills-validation)
- [**What a Full Pipeline Analysis Looks Like**](#what-a-full-pipeline-analysis-looks-like)
- [**Anatomy of a Completed Analysis**](#anatomy-of-a-completed-analysis)
- [**Looking at an Actual Example Project**](#looking-at-an-actual-example-project)
- [**Easing in with Progressively More Advanced Queries**](#easing-in-with-progressively-more-advanced-queries)
- [**Session Management: Multi-Session Work and Recovery**](#session-management-multi-session-work-and-recovery)
- [**Where Things Live in the Repository**](#where-things-live-in-the-repository)
- [**Recommended Next Steps**](#recommended-next-steps)

---

## Core Concept: Context Windows and Prompt Engineering 101

Alright, before we begin ANYTHING else, we need to cover the first and most foundational concept in the current paradigm of LLMs: context windows and prompt engineering. There are a ton of materials around the web about this, and it'd be helpful for you to probably ask Claude to tell you more about it. I need you to know this before you do ANYTHING else with DAAF because it will fundamentally shape how you use and interact with DAAF, as well as what you should expect from it. Here's the long story short:

1. LLMs are designed to be really good at **predicting the next word when given a sequence of words**. They learn how to do this "well" in a variety of ways, but that's really the crux of it: everything about their current functionality, no matter how fancy or surprising (e.g., making powerpoints, searching the web, writing/running code, etc.), is still predicated on that one simple premise.
2. With that in mind, how "well" LLMs work and what they can do is **extremely dependent** on the words you provide to it before you ask it to predict the next one. These preliminary words we provide to LLMs first are known as **"context"** (a thankfully intuitive choice of term!). This concept of context is absolutely mission-critical for any work with LLMs for two key reasons:
    * Different LLMs can only "digest" and use a certain amount of context at a time before predicting the next word, which is known as its **"context window"**. GPT-3, for example, could only really "read" ~1500 words to predict the next one; any more than that was ignored or would break it. One frontier of LLM advancement is thus expanding the amount of context a specific LLM can even consider before it predicts the next word ("expanding the context window"), because the more context a model can incorporate, the more content-area expertise, skills, framing, etc. it can use for tasks you want it to do later on. Claude Opus 4.6, for example, has a context window of ~150,000 words by default, and they're beta testing context windows of ~750,000 words at time of writing.
    * Another frontier of LLM advancement is teaching the LLM how to carefully and thoughtfully pay attention to different aspects of its provided context more judiciously. For example, maybe you ask an LLM assistant to write you an email to a colleague after providing it both a copy of your most recent email to that colleague, and the general gist of what you want to say. If it treated every word evenly, it might stick too closely to the original email, and not understand that the gist of your new message is actually **much more important**. This is a SUPER complicated process, but it establishes an important dynamic: **Not all context is treated equally,** and so we need to account for that when providing an LLM with context. LLMs can get strangely confused and become erratic when their context windows are filled in ways they can't really process: this is known as **context rot**, and needs to be avoided at all costs.
3. The complex task of trying to **maximize an LLM's performance at a requested task** by carefully deciding (a) exactly what context, and how much, to give an LLM given its current context window limitations, and (b) how to structure that provided context strategically and optimally for the task at hand to prevent confusion/distraction, is what is known as **prompt engineering**. It's more of an art than a science in most circumstances, but that's the general idea.

So with that in mind, DAAF can be thought of as a way for me to help other researchers by **automating and simplifying the prompt-engineering process** specifically for core aspects of the data analysis and research process. This is how we accomplish the core requirement of making DAAF scalable. Every single thing about how I've designed DAAF is really just fundamentally designed to tell Claude exactly **what** I think it needs to know, **when** I think it needs to know it, so it does what we want **more often and with higher quality** on average. Ignoring the fancy terms like agents, subagents, skills, orchestrators, etc. -- DAAF is just a series of pre-cooked "recipes" of context that we feed to Claude before it tries to do what you ask, with the hope that it'll be thus be more successful at doing it transparently and rigorously and reproducibly like a scientist would prefer. Anyone can put this together without DAAF in simpler ways or just ad-hoc (i.e., by writing a single very long, custom prompt to regular Claude Code) -- I'm just trying to make it easier for people with sensible defaults and opinionated standards of rigor.

This then leads to three (hopefully very intuitive) of the core things to be aware of when using and working with DAAF:

* In addition to the prompt engineering DAAF orchestrates behind the scenes, **what you ask Claude to do and how you ask it to do it** is an immensely important element of getting better quality output from DAAF/Claude. So a lot of what we'll talk about here is how to do this thoughtfully and well to maximize your chances of getting something useful from DAAF.
* The system is **designed to intelligently select and inject the right context to Claude before your query/question/chat**, based on what you provide in your query/question/chat. But this is **NOT** foolproof, and simply cannot account for every possibility. Feel free to go off the beaten path at will, but just be aware that it's going to necessarily be less supported and structured from there; you may ultimately find it's not working very well for what you want, because I wasn't able to design for that style of work. Trying to write your query in a different way can help, or you can help us improve DAAF by [opening an issue](https://github.com/DAAF-Contribution-Community/daaf/issues) and telling us about it!
* Because thoughtfully shaping the context is our way of shaping Claude's thinking from what I lovingly describe as an over-eager recent MBA graduate to a thoughtful, careful research colleague, DAAF really only works with the cutting-edge models like Opus 4.6, and it pushes them to their limit to take advantage of their full context windows where possible. **This is why it is SO expensive to use at this time**; settling for less, we sacrifice a lot of expertise and reliability and rigor. It's a careful balancing act of optimization that no one really has fully figured out!

So that's the gist for now. Onward, to actually using DAAF!

---

## The Six Engagement Modes

DAAF first classifies every request you make into one of six **engagement modes**. This is how we properly prompt-engineer Claude, because each mode triggers a fundamentally different workflow, different outputs, and different expectations for what input you'll need to provide to steer it well. Understanding these modes is the single most useful thing you can do to work with DAAF effectively, because it helps you frame your questions in the way most likely to get you what you actually want, and better understand what's going on behind the scenes.

Before doing anything else, DAAF will tell you which mode it's classifying your request into, explain why, and ask you to confirm. This is intentional. You should always have the chance to say "actually, I just wanted a quick lookup" or "actually, let's go deeper on this." Here's what each of them do, and how the workflow works so you know when and why you'd use each:

### Data Lookup Mode

**Trigger words:** "what are the values for," "how is X defined," "lookup," "what does this variable mean," "explain this table..."

**What it is:** A quick, focused lookup about available data tables and variables. You have a specific question about a data source, variable, coded value, or definition, and you want a direct answer without any exploration overhead. DAAF loads a single relevant data knowledge source skill and gives you what you need quickly. You can think of this like a data documentation oracle -- saving you some time on determining what data are available, limitations, year ranges, etc.

**What you get:**
- A direct, specific answer to your question
- Supporting context where relevant (e.g., "this variable uses coded values where 1=Regular school, 2=Special education, 3=Vocational...")
- Pointers to relevant documentation if you want to dig deeper

**Expected time investment:** Seconds. One question, one answer.

**When to use it:** When you already know what you're looking for and just need the specific detail. "What does `free_lunch` mean in the CCD data?" "What years are available for CRDC?" "What's the difference between `enrollment` and `fall_enrollment` in IPEDS?"

**When NOT to use it:** When your question is actually broader than you realize. If you find yourself asking five Data Lookup questions in a row, you probably want Data Discovery mode instead (described next). DAAF will suggest this if it notices the pattern.

### Data Discovery Mode

**Trigger words:** "what data exists," "is it possible," "feasibility," "what's available," "can DAAF do," "explore", "can you tell me more about variables related to..."

**What it is:** A focused investigation into what data is available, whether an analysis is feasible, and what you'd be working with if you decided to go deeper. Think of it as scoping and reconnaissance -- DAAF explores the landscape and reports back to you with what it found, but isn't running any sort of data analysis. Think of this like a scoping partner, above and beyond a basic documentation look-up.

**What you get:**
- A findings summary describing available data sources, variables, year ranges, and geographic coverage
- Key caveats and limitations for each relevant data source
- A feasibility assessment -- can the question be addressed with available data?
- If the answer is "yes, this looks promising," DAAF will offer to escalate to Full Pipeline mode

**Expected time investment:** A few minutes of conversation, usually just one or two exchanges. It might launch some "subagents" to do some digging in the background for a few minutes, too.

**When to use it:** When you're not sure what data exists for a topic, when you want to know if a question is answerable before committing to a full analysis, or when you're brainstorming research directions and want to see what's possible. This is genuinely a great starting point for new users -- ask DAAF what it can do before asking it to do it.

**When NOT to use it:** When you already know what general data exists and you're ready to analyze it with a specific research question. In that case, jump straight to Full Pipeline.

**Escalation:** If Data Discovery turns up promising data, DAAF will suggest: "Based on these findings, would you like me to proceed with a Full Pipeline analysis?" You can say yes, refine the question, or say no and walk away with just the findings.

### Full Pipeline Mode

**Trigger words:** "analyze," "research," "create," "generate," "what's the relationship between..."

**What it is:** This is the DAAF will take your research question and run a complete analytic workflow across 5 phases: exploring available data, creating a detailed research plan, fetching and cleaning data, running analyses and creating visualizations, and delivering a comprehensive report with all supporting artifacts. This is what DAAF was fundamentally built to do as its main use-case (not to say the other modes aren't also very useful!).

**What you get:**
- A detailed research plan documenting every methodological decision
- All raw and processed data files (parquet format)
- A complete set of versioned, validated Python scripts covering every step of the analysis
- Statistical analysis results and high-quality data visualizations
- A compiled marimo notebook walking you through every script and its execution logs
- A stakeholder report synthesizing key findings, methodology, and limitations
- A lessons-learned document with data and process insights

**Expected time investment:** About 5-10 minutes of active engagement time spread across 4-5 "check-in" points where DAAF pauses for your review and approval, a few hours of DAAF working independently in the background, and then whatever time you (rightfully, importantly) dedicate to reviewing the final outputs. And, of course, whatever API fees you incur along the way. Full duration will depend heavily on how complex your query is: primarily how many scripts it needs to write, rewrite, and QA. Plan accordingly!

**When to use it:** When you have a genuine research question you want to explore with data. It can be as simple as "How has enrollment in rural schools changed over the past decade?" or as complex as "What's the relationship between school-level poverty, access to advanced coursework, and disciplinary disparities, controlling for school size and urbanicity?" DAAF will scope accordingly.

**When NOT to use it:** When you just need a quick answer, a variable definition, or want to know if certain data even exists. That's what the other modes are for -- and using Full Pipeline mode for a simple question is like driving a semi-truck to the corner store.

### Revision and Extension Mode

**Trigger words:** "fix," "update," "change," "modify the analysis," "revise," "redo," "can you adjust," "extend"

**What it is:** You have an existing analysis that needs changes or extension, and you want DAAF's help to improve it. Maybe you want to rethink a measure, add a new variable, change the year range, run a different statistical test, or fix something that didn't look right. First, point DAAF to the name of the project folder. Then, DAAF locates your existing project, reads the Plan, and creates a *new version* of the relevant artifacts -- it never modifies the originals.

**What you get:**
- A new version of the Plan document incorporating your changes
- Updated scripts, data, and outputs as needed
- A full Final Review even for minor fixes (no shortcuts on quality)
- All prior versions preserved in the same project folder

**Expected time investment:** Depends on the scope of the revision. Changing a year range might take 15 minutes; fundamentally rethinking the methodology could be nearly as long as a new analysis (and you may seriously want to consider going that route instead with clearer and more directed prompts/research questions, depending!).

**When to use it:** After you've received a completed analysis and want to adjust something. Reference your project by keywords or date -- e.g., "Can you update the Texas poverty analysis to include 2023 data?" or "In the 2026-01-15 enrollment study, can we use a different measure of school size?"

**How the version system works:** All versions live in the same project folder. Prior versions are **never** modified or overwritten -- that's a non-negotiable rule. The versioning uses date suffixes: the original analysis might be `2026-01-24`, revision 1 becomes `2026-01-24a`, revision 2 becomes `2026-01-24b`, and so on. This means you always have a full audit trail of how the analysis evolved.

**When NOT to use it:** When your existing analysis is fundamentally flawed or you want to ask a substantially different research question. At that point, starting a new Full Pipeline analysis with better-targeted prompts will produce cleaner results than trying to revise the original into something it wasn't designed to answer.

### Data Ingest

**When to use:** You have a raw data file (CSV, Parquet, Excel, etc.) that you want to profile and add as a reusable data source for future analyses.

**What happens:** DAAF runs a thorough profiling protocol (up to 11 scripts, depending on data characteristics) in 3 top-level phases (Setup, Profiling, Skill Creation). The Profiling phase contains 4 sub-phases: Structural Discovery, Statistical Deep Dive, Relational Analysis, and Interpretation & Reconciliation. You review the findings and confirm the interpretations before DAAF creates a standalone data source skill. The entire process is tracked in a reproducible research project folder.

**What you get:** A standalone data source skill (`.claude/skills/`) that future analyses can reference, plus a research project folder with all profiling scripts, QA reviews, and session state.

**Checkpoints:** 2 -- one after project setup (to confirm the profiling plan), and one after profiling completes (to review and confirm/modify the preliminary interpretations before they become part of the skill).

**Example prompts:**
- "I have a CSV of county-level election returns I'd like to profile and add as a data source"
- "Profile this parquet file and create a skill I can use in future analyses"
- "I want to ingest a new dataset about hospital readmission rates"

### Reproducibility Verification Mode

**Trigger words:** "verify," "reproduce," "reproduction," "does this replicate," "check reproducibility," "verify this analysis..."

**What it is:** You have an existing completed analysis (from a Full Pipeline run or otherwise) and you want to mechanically verify that it reproduces from its marimo notebook. DAAF decompiles the notebook back into standalone scripts, re-executes each one, compares the new outputs against the originals, and cross-references the Report's claims against the actual analytic results. The goal is to provide an independent, systematic assessment of whether the analysis holds up end-to-end.

**What you get:**
- A Reproduction Report documenting what matched, what diverged, and any methodological concerns discovered during the process
- An overall assessment of **FULLY REPRODUCED** (all outputs match within tolerance, report claims supported), **PARTIALLY REPRODUCED** (some outputs diverge or some claims unsupported, but core findings hold), or **NOT REPRODUCED** (significant divergences or unsupported claims that undermine the analysis)
- Detailed comparison logs showing exactly where and how outputs differed, if at all

**Two key user decisions:**
- **Whether to re-fetch data** (default: yes). Re-fetching tests whether the analysis reproduces against the current state of the data source. Skipping re-fetch tests whether the analysis reproduces from the already-downloaded raw data files.
- **Methodological review depth** (default: light). A light review focuses on mechanical reproduction -- do the scripts run and produce matching outputs? A deep review additionally scrutinizes methodological choices, statistical assumptions, and interpretation quality.

**Expected time investment:** Depends on the complexity of the original analysis. A straightforward single-source analysis might take 15-30 minutes; a multi-source analysis with extensive transformations could take longer. You'll review the Reproduction Report at the end.

**When to use it:** After completing a Full Pipeline analysis and wanting to verify it reproduces before sharing or publishing. When reviewing someone else's DAAF analysis and wanting an independent verification. For periodic verification of important findings to ensure they still hold against updated data sources.

**When NOT to use it:** When you already know the analysis needs changes -- use Revision and Extension mode instead. When the analysis was never completed or has no notebook -- there's nothing to reproduce from.

### Switching Between Modes

DAAF supports clean transitions between modes when it makes sense:

| From | To | When it happens |
|------|----|-----------------|
| Data Discovery | Full Pipeline | Findings suggest a feasible and valuable analysis |
| Data Lookup | Data Discovery | Your question reveals a broader data landscape worth exploring |
| Data Lookup | Full Pipeline | A quick lookup reveals an actionable analysis opportunity |
| Data Discovery | Data Ingest | Do you have a raw data file you want to profile and make reusable? |
| Data Ingest | Full Pipeline | Skill created — would you like to analyze this data now? |
| Full Pipeline | Data Ingest | Analysis needs a dataset that has no existing skill yet |
| Full Pipeline | Revision and Extension | You just completed an analysis and want to adjust or extend something |
| Revision and Extension | Full Pipeline | The revision scope grows beyond what targeted modification can handle |
| Data Ingest | Revision and Extension | You want to modify or extend the skill that was just created |
| Full Pipeline (complete) | Reproducibility Verification | User wants to verify their analysis reproduces |
| Reproducibility Verification | Revision and Extension | Divergence found, user wants to fix original |
| Reproducibility Verification | Full Pipeline | Original analysis is fundamentally broken |

DAAF will always propose these escalations explicitly and wait for your confirmation. It should never silently switch modes on you.

---

## The Mental Model: Orchestrator, Agents, Skills, Validation

Okay, this is the section where I want to give you genuine intuition for how this all works under the hood. You don't *need* to understand the architecture to use DAAF -- you can absolutely just type a research question and let it run. But if you want to understand *why* DAAF does what it does, *why* it pauses when it pauses, and *why* the output is structured the way it is, this section will hopefully make all of that click.

I'm going to use an analogy that I think captures it well: **DAAF is intended to mirror the workflows of a well-run research lab** with you as the PI.

### The Orchestrator: Your Lab Director

When you type a message to DAAF, you're talking to the **orchestrator**, whose core orchestration behavior is defined by the [`daaf-orchestrator` skill](../.claude/skills/daaf-orchestrator/SKILL.md), while universal execution rules come from [`CLAUDE.md`](../CLAUDE.md). Think of the orchestrator as a lab director -- the person who takes your research question, figures out what needs to be done, decides who on the team should do each piece, coordinates the whole effort, and reports back to you at key milestones.

The orchestrator should NOT be doing the hands-on work itself, because its primary value-add and contribution is coordination and workflow management. It doesn't write analysis scripts, it doesn't clean data, it doesn't run regressions. What it does is:

- **Classify your request** into an engagement mode (Full Pipeline, Data Discovery, etc.)
- **Delegate tasks** in proper sequence to specialized agents, itself providing them with the right context and instructions they need to do their jobs well
- **Enforce quality gates** -- certain milestones that MUST be passed before work continues and the work product changes hands from one agent to another
- **Report progress** to you and pause for your approval at key junctures to ensure you, the PI, approve of the direction of the work. It will also enforce work revisions as needed if you request it
- **Keep the big picture in mind** -- tracking what's been done, what's next, and what decisions have been made, to ensure it's addressing the core intentions/vision of the PI

The orchestrator is the most important part of DAAF, because it needs to simultaneously understand the whole workflow process and the broad context of the work in mind, while also being technical enough and specific enough to give precise, targeted instructions and context to every other LLM assistant involved in the process.

### Specialized Agents: Your Research Team

The "team members" in this lab are **agents** -- versions of Claude provided a clear behavioral protocol and persona defining exactly how they should think and operate. You can even see the exact context instructions provided to each in [the agents folder](../.claude/agents/). Agents are not knowledge repositories; they're *behavioral definitions*. An agent answers the question: "How should I behave when I'm doing this specific type of work?"

Here's a few examples of the team members with the links to each of their actual instruction files if you want to dig in more:

| Agent | Role in the Lab Analogy | What They Actually Do | 
|-------|------------------------|----------------------|
| [**research-executor**](../.claude/agents/research-executor.md) | Technician/Analyst | Executes one data task at a time (fetch, clean, transform, analyze) with meticulous pre/post validation |
| [**code-reviewer**](../.claude/agents/code-reviewer.md) | Senior Technician/Analyst | Reviews every single script the research-executor produces, looking for bugs, methodology errors, and data quality issues |
| [**source-researcher**](../.claude/agents/source-researcher.md) | Research Assistant | Deep-dives into a specific data source's documentation, collection protocols, caveats, and gotchas for shared team awareness |
| [**data-planner**](../.claude/agents/data-planner.md) | Research Design Lead | Synthesizes all the preliminary findings into a detailed, executable research plan |

The point here is that we want to provide very different context to Claude when faced with different tasks. Trying to get Claude to do everything equally well is impossible given fixed context window limitations, and trying to do so will ultimately confuse it and cause dreaded **context rot** (where an LLM becomes unpredictable, incoherent, and erratic due to over-filled or poorly structured context it can't make sense of). This means that we need to split responsibilities across "versions" of Claude provided very different instructions and behavioral protocols to get it to perform these tasks well in tandem.

> **Quick definitional note:** An **Agent** is the general phrase we use to describe any tailored/pre-specified set of behavioral protocols for an LLM assistant. Each of the above team members in this analogy are Agent definitions. As a user, you can ask Claude directly to take on an agent persona and begin working. However, with DAAF's default workflows, the orchestrator actually calls up and tasks each agent above itself, so you never have to; agents become **subagents** when they are called by another assistant in this way, instead of directly by the user.

Ultimately, the orchestrator's job is to know which agent/team member to call up at any one time, and to also know very thoughtfully what it needs to tell that subagent in order for the subagent to do its job effectively with necessary context and guidance. You can see how the orchestrator is trained to talk with these agents in [the agents README](../.claude/agents/README.md) and [the orchestrator's full pipeline reference](../.claude/skills/daaf-orchestrator/references/full-pipeline.md)). Subagent orchestration is an extremely new and active area of development in the broader field of AI at-large right now, which is part of why a system as complex as DAAF has only recently become possible.

### Skills: Your Team's Reference Library

If agents define *behavior* ("how should I work?"), then **skills** define *knowledge* ("what do I need to know?"). Skills are basically structured knowledge documents that agents load into their own context on demand. You can think of them as specialized reference manuals that your research team pulls off the shelf when they need domain-specific information or how-to's for a niche task or issue. These are nice because they are easily transferable across agents, and so work well for implementing knowledge/context that several agents are likely to need access to for their work.

DAAF's skills are currently organized into a few categories:

**Data source skills** -- one for each major education data source:
- What endpoints exist and what they contain
- What variables mean and how they're coded
- What caveats and limitations to watch for
- What suppression rules apply (e.g., cells with fewer than a certain number of students are suppressed for privacy)
- More historical/contextual information about the source dataset and its collection, nuances, etc.
- `education-data-explorer` and `education-data-query` for finding and fetching data
- `education-data-context` for interpreting data caveats and coded values

**Technical skills** -- how to use certain toolsets:
- `data-scientist` for general methodology, mindset/philosophy, and rigor principles
- `polars` for data manipulation (similar to tidyverse or pandas)
- `plotnine` for static, publication-quality plots (ggplot2 in Python)
- `plotly` for interactive visualizations
- `marimo` for reactive Python notebooks

**Meta skills** -- for extending DAAF itself:
- `skill-authoring` for creating and integrating new skills in a unified format and with best practices
- `agent-authoring` for creating and integrating new agents in a unified format, and with best practices 

**The key insight:** In DAAF, skills are generally intended to be loaded *by agents*, not by the orchestrator. When the orchestrator delegates a task to the research-executor, it tells the agent: "Load the `education-data-source-ccd` skill for this task." The agent pulls up the relevant reference material, uses it to guide its work, and then returns its findings to the orchestrator. This keeps the orchestrator's context lean (it doesn't need to hold the full contents of every skill in memory) and ensures each agent gets exactly the knowledge it needs for its specific task.

<img width="743" height="377" alt="orchestrator_diagram" src="https://github.com/user-attachments/assets/d8c297e0-376e-4543-b219-98ea44a74e93" />

### Dual-Layer Validation: Your Lab's Quality Control System

This is where DAAF really earns its keep, and honestly where I think the biggest gap exists in most ad-hoc LLM-assisted analysis today. DAAF uses two independent layers of validation that work together to catch errors:

**Layer 1: Primary Validation (Checkpoint Protocol, CP1-CP4)**

These are validation checks *embedded directly in the analysis scripts themselves*. Every script the research-executor writes includes built-in assertions and checks that run automatically:

| Checkpoint | When It Runs | What It Catches |
|------------|-------------|-----------------|
| **CP1** | After data fetch | Empty datasets, wrong data types, >90% missing values in critical fields |
| **CP2** | After data cleaning | Invalid coded values, suppression rates above 50%, impossible analysis types |
| **CP3** | After each transformation | Unexpected row loss (>90%), broken joins, surprise null values |
| **CP4** | Before final output | Missing required outputs, deviations from the plan |

If a checkpoint fails, execution stops. Period. DAAF doesn't try to power through -- it reports the failure and either attempts a fix or escalates to you.

**Layer 2: Secondary Validation (QA Code Review, QA1-QA4b)**

After every single script passes its embedded checkpoints, a *completely separate agent* -- the `code-reviewer` -- independently inspects both the code and its output data. The code-reviewer approaches each script with an adversarial mindset, specifically looking for:

| QA Checkpoint | When It Runs | What It Catches |
|---------------|-------------|-----------------|
| **QA1** | After fetch scripts | Schema problems, ID uniqueness violations, suspicious distributions |
| **QA2** | After cleaning scripts | Incorrect coded value handling, flawed filtering logic |
| **QA3** | After transformation scripts | Bad join cardinality, aggregation errors, derived column mistakes |
| **QA4a** | After analysis scripts | Invalid statistical methods, violated assumptions, unreliable results |
| **QA4b** | After visualization scripts | Misleading charts, incorrect data sources, missing labels |

**Why two layers?** Because they catch different types of errors. Primary validation catches *operational failures* -- the data is empty, the types are wrong, something clearly broke. Secondary QA catches *methodological errors* -- the code runs fine and produces output, but the methodology is wrong, the join logic is subtly off, or the interpretation doesn't match what the data actually shows. These are the insidious errors that humans regularly miss when reviewing LLM-generated code, and they're exactly the errors that matter most for research integrity.

**The critical rule:** Every script should get both layers of review. No exceptions. And the code-reviewer inspects each script *immediately* after it's executed -- not batched at the end of a stage. This matters because an error in script 1 that goes undetected will silently propagate through scripts 2, 3, and 4, compounding into a mess that's far harder to diagnose and fix.

### How the Pieces Fit Together

Here's how a typical task flows through the system during a Full Pipeline analysis:

1. **You** ask a research question
2. **The orchestrator** classifies the request as Full Pipeline and confirms with you
3. **The orchestrator** delegates data exploration to a subagent, which loads the `education-data-explorer` skill
4. **The orchestrator** delegates source deep-dives to `source-researcher` agents (one per data source), each loading the appropriate `education-data-source-*` skill
5. **The `research-synthesizer`** consolidates all findings into unified guidance
6. **The orchestrator** pauses for your review (Phase Status Update 1)
7. **The `data-planner`** creates a detailed Plan, validated by the **`plan-checker`**
8. **The orchestrator** pauses for your review again (Phase Status Update 2)
9. **A separate `research-executor`** is called up to work through each task in the Plan, one at a time, with **a separate `code-reviewer`** inspecting each script immediately after execution
10. **The orchestrator** pauses twice more for your review to provide updates and get your input on any key decisions/issues (Phase Status Updates 3 and 4)
11. **The `notebook-assembler`** compiles all scripts into a browsable notebook
12. **The `report-writer`** creates the stakeholder report
13. **The `data-verifier`** performs adversarial final verification on the final report, checking it closely for errors and drift from the outputs of the actual analytic scripts
14. **The orchestrator** delivers everything to you with file paths for final review.

That's the core loop. Every piece has a job. Every job has a quality check. Every quality check has consequences (stop, revise, or proceed). And you get four mandatory check-in points where DAAF pauses and waits for your explicit approval before continuing.

---

## Anatomy of a Completed Analysis

After a Full Pipeline run completes, you'll have a project folder containing everything DAAF produced.

### The Project Folder

Every analysis lives in a self-contained folder under `research/`, named with the date and a descriptive title:

```
research/2026-01-24_School_Poverty_Analysis/
├── 2026-01-24_School_Poverty_Analysis_Plan.md
├── 2026-01-24_School_Poverty_Analysis_Plan_Tasks.md
├── 2026-01-24_School_Poverty_Analysis.py
├── 2026-01-24_School_Poverty_Analysis_Report.md
├── LEARNINGS.md
├── STATE.md
├── scripts/
│   ├── run_with_capture.sh
│   ├── stage5_fetch/
│   │   ├── 01_fetch-ccd.py
│   │   └── 02_fetch-meps.py
│   ├── stage6_clean/
│   │   ├── 01_clean-ccd.py
│   │   └── 02_clean-meps.py
│   ├── stage7_transform/
│   │   ├── 01_join-data.py
│   │   └── 02_derive-variables.py
│   ├── stage8_analysis/
│   │   ├── 01_regression-poverty.py
│   │   └── 02_enrollment-plot.py
│   ├── cr/
│   │   ├── stage5_01_cr1.py
│   │   ├── stage5_02_cr1.py
│   │   ├── stage6_01_cr1.py
│   │   └── ...
│   └── debug/                        (if debugging was needed)
├── data/
│   ├── raw/
│   │   ├── 2026-01-24_ccd_schools.parquet
│   │   └── 2026-01-24_meps_poverty.parquet
│   └── processed/
│       ├── 2026-01-24_ccd_clean.parquet
│       └── 2026-01-24_analysis.parquet
└── output/
    ├── analysis/
    │   └── 2026-01-24_regression_results.parquet
    └── figures/
        └── 2026-01-24_poverty_distribution.png
```

Let's go through each piece.

### The Plan Document (Plan.md)

**What it is:** The single most important artifact in the project. Plan.md is DAAF's strategic research specification -- it captures everything about what was done and *why*. If the scripts are the "what," Plan.md is the "why."

**What's inside:**
- **Research Question** -- your original question, verbatim, plus any clarifications
- **Research Outcomes** -- specific, measurable topics the analysis must rigorously investigate and report on (e.g., "Relationship between school poverty rates and AP course enrollment is characterized with direction, magnitude, significance, and confidence intervals"). These define what must be *examined*, not what the answer should be. Directional predictions belong in the optional Hypotheses section.
- **Data Sources** -- which datasets are being used, what endpoints, what years, and why
- **Methodology** -- the statistical approach, key decisions, and their rationale
- **Risk Register** -- what could go wrong and how to handle it
- **Key Decisions Log** -- every methodological choice made during the project, with reasoning

**How to read it:** Start with the Research Question and Research Outcomes -- do they match your intent? If any outcomes read like hypotheses (predicting a direction), flag them. Check the Key Decisions Log for anything surprising. Plan.md is meant to be comprehensive enough that someone unfamiliar with the project could understand exactly what was done and why.

**Why it matters:** Plan.md is your audit trail. If you or a colleague ever needs to understand how a finding was derived, Plan.md traces the full chain of reasoning from question to methodology to execution. It's also what makes Revision and Extension Mode possible -- DAAF reads the existing Plan.md to understand what was done before proposing changes.

A companion file, **Plan_Tasks.md**, contains the detailed machine-readable task specifications that DAAF uses internally to execute each step. It includes the exact ordered Transformation Sequence of tasks (fetch, clean, transform, analyze, visualize) with dependencies, wave assignments for parallel execution, and input/output file paths. Both files are frozen after planning completes. You can review Plan_Tasks.md if you want to audit the specific task definitions, but Plan.md is the primary document for understanding the research design.

### The Scripts Directory

**What it is:** The primary execution artifacts. I cannot stress this enough -- **the scripts are the real work product**, not the notebook. Every data fetch, every cleaning operation, every transformation, every analysis, and every visualization is captured as a standalone Python script in the `scripts/` directory, organized by stage. I cannot stress enough: Get a sense for how these scripts are actually written and run: **this is the secret sauce of why anything about DAAF is worth anything at all**. Without the core engine of data analysis being transparent, rigorous, and reproducible, nothing else that comes out of this process is valuable. Spend time here.

**What's inside each script:**
- Clear section headers (`# --- Config ---`, `# --- Load ---`, `# --- Transform ---`, `# --- Validate ---`, `# --- Save ---`)
- Inline audit trail comments explaining the *intent* and *reasoning* behind every operation (not just what the code does, but *why*)
- Embedded validation assertions (`assert`, `print` statements showing data shape, distributions, etc.)
- An **appended execution log** at the bottom of each script (added automatically after execution) showing exactly what happened: duration, exit code, stdout/stderr output, pre/post data state

**How to read scripts:** Scripts read top-to-bottom like a lab notebook -- no functions, no classes, no jumping around. Start at the top, follow the comments, and then check the execution log outputs at the bottom. The execution log is the "ground truth" for what actually happened when the script ran.

**Script versioning:** When a script fails QA and needs to be revised:
- Original `01_task.py` keeps its failed output (it's part of the audit trail)
- Revision `01_task_a.py` contains the fixes with its own execution log
- Further revisions use `_b.py`, `_c.py`, etc.
- The notebook only includes the final successful version

**The `cr/` subdirectory:** This is where the code-reviewer's QA inspection scripts live. Each `cr` script is a diagnostic that the code-reviewer wrote and ran to verify a specific analysis script. The naming convention is `stage{N}_{step}_cr{iteration}.py` -- so `stage5_01_cr1.py` is the code-reviewer's first inspection of the first Stage 5 script. If the reviewer found something suspicious and needed to investigate further, you'll see `cr2`, `cr3`, etc.

### The Marimo Notebook

**What it is:** A compiled walkthrough of all the validated scripts, assembled into an interactive marimo notebook that you can view in your browser. It is *not* where the analysis was done -- it's a presentation layer that lets you browse the completed work.

**What's inside:**
- **Section headers** identifying which script stage is being shown
- **Code cells** containing the literal code from each script file (commented out so it doesn't re-execute)
- **Execution log accordions** showing exactly what happened when each script ran -- verbatim, not summarized
- **Data inspection cells** that load the output parquet files and display them as interactive tables (the *only* new code in the notebook)

**What you won't see:** New analysis code, interactive dashboards, filter widgets, or additional transformations. The notebook is a viewer, not an analysis tool. This is by design -- it ensures that what you see in the notebook is exactly what was executed and validated in the scripts, with nothing added or changed.

**How to view it:** From inside your Docker container:
```bash
marimo run 'research/YYYY-MM-DD_Title/YYYY-MM-DD_Notebook.py' --host 0.0.0.0 --port 2718 --headless
```
Then open [http://localhost:2718](http://localhost:2718) in your normal web browser. You can also open the `.py` file in any text editor -- marimo notebooks are just Python.

### The Report

**What it is:** A stakeholder-facing summary report synthesizing the key findings, methodology, data, limitations, and visualizations into a readable narrative. Think of it as the "executive summary" version of the analysis -- what a colleague, policymaker, or reviewer would want to read to understand what was found and how.

**What's inside:**
- Executive summary with headline findings
- Detailed methodology section (data sources, cleaning approach, statistical methods)
- Key findings with supporting statistics and figure references
- Data limitations and caveats
- Appendices with technical details

**How it differs from the notebook:** The notebook is for thorough *methodological inspection* -- browsing every line of code and verifying what happened. The report is for *communication* -- telling the story of what was found and what it means. They're complementary artifacts serving different audiences.

**How to view it:** The report is a Markdown (.md) file. You can open it in any text editor, but it'll look much nicer in a Markdown viewer. I recommend copying the contents into a free online viewer like [StackEdit](https://stackedit.io/app), or installing a Markdown viewer extension for your code editor.

### Data Files (Raw and Processed)

**`data/raw/`** -- The original data files exactly as they were fetched from the data sources. These are your "original ingredients" and are never modified after download.

**`data/processed/`** -- Cleaned and transformed versions of the data, including the final analysis dataset. These are the files that were actually used for statistical analyses and visualizations.

**Why parquet?** Every data file is saved in Apache Parquet format. Parquet is a columnar storage format that preserves data types (integers stay integers, dates stay dates), compresses efficiently, and is fast to read. CSV files lose type information (everything becomes a string), which introduces subtle bugs. Parquet prevents an entire category of data quality issues. You can open parquet files in Python (with `polars` or `pandas`), R (with `arrow`), or many other tools.

### Output: Analysis Results and Figures

**`output/analysis/`** -- Statistical analysis results saved as parquet files. Regression coefficients, summary statistics, comparison tables, etc.

**`output/figures/`** -- Data visualizations saved as PNG images. These are the same figures referenced in the report. You can open them with any image viewer.

### STATE.md and LEARNINGS.md

**STATE.md** -- A session state file that tracks DAAF's progress through the analysis. It records transformation progress, checkpoint statuses, runtime decisions, and any blockers encountered. It also accumulates the QA Findings Summary (aggregated quality review results across all stages), the Final Review Log (from the end-of-pipeline verification), and any Runtime Risks discovered during execution. If a session is interrupted (context exhaustion, network issues, etc.), STATE.md allows DAAF to resume exactly where it left off. You generally don't need to read this unless debugging a session issue.

**LEARNINGS.md** -- A lessons-learned document capturing insights about the data and the analysis process. This includes data idiosyncrasies discovered during the analysis, interpretation concerns, and suggested improvements to DAAF's documentation. This file is designed to be immediately actionable -- you can share it back with the community to help improve DAAF for future users.

## Looking at an Actual Example Project

To help illustrate what DAAF does and how it works, I've included in the main repository an example project in the research folder focused on trying to tease out the [**complicated/misleading relationship between college selectivity and graduation rates**](../research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/). With that folder, you can explore basically everything that DAAF has to offer for a Full Pipeline Analysis -- from the [Plan document](../research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Plan.md), the [full report](../research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Report.md), and a variety of analytic scripts along the way (see a [data fetch example](../research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/03_fetch-admissions.py), a [data transformation/join example](../research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/03_join-resources.py), a [code QA example](../research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage6_08_cr2.py), and a [statistical analysis example](../research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/03_correlation-matrix.py)).

This was just a random test run that I decided to record via video for demo purposes, and it felt appropriate to upload the full and complete output in all dimensions for transparency's sake. I do **not** post this because I think it's spotless and perfect and great -- I present this warts and all, knowing that it isn't great with some of its interpretation, and some of the report is frankly a little overblown in its conclusions. That's part of the point here: there's a LOT to be impressed by in this work, but it IS NOT PERFECT and DOES need human review. Please use DAAF accordingly!!!

In any case, this demo project should give you a good sense of what to expect, and how DAAF ultimately works.

---

## Easing in with Progressively More Advanced Queries

Rather than try to jump in with a complete Full Pipeline Analysis at once, I strongly recommend testing out the simpler features and engagement modes first. The whole premise of this project is that DAAF is surprisingly robust, but I think the right way to build confidence is to start small and work your way up. Here's a concrete progression I'd recommend, designed to let you assess DAAF's knowledge and capabilities at each level of complexity:

### Level 1: Quick Ask (Data Lookup Mode)

Ask Claude to explain a single dataset or variable you're already familiar with. This tests DAAF's domain knowledge against your own expertise.

```
What is the CRDC dataset and what does it contain? How often is
it collected?
```

or

```
How is free/reduced-price lunch eligibility defined in the CCD
data? What are the coded values?
```

**What you're testing:** Does DAAF know the data as well as you do? Are there gaps in its knowledge? Does it mention the right caveats? Feel free to ask follow-ups or dig into specific details -- this is a safe, low-stakes way to calibrate your trust.

### Level 2: Thorough Documentation Review (Data Discovery Mode)

Ask Claude to help you figure out what's available within a broad conceptual category of data. This tests DAAF's ability to explore multiple options, consider trade-offs, notice year overlaps or gaps, and so on.

```
I'm considering a research project looking more at college and university finances. Can you help me explore what datasets and variables are likely to be of interest for this work?
```

or

```
I know there are a couple of different ways of measuring school poverty. Can you give me a good sense of what the options are and what their relative trade-offs might be?
```

**What you're testing:** How does DAAF surface relevant information, variables, tables, and so on, when faced with broader options and less explicit direction? What issues might arise, and does it seem to recognize strengths/pitfalls of each possibility it flags appropriately?

### Level 3: Data Ingestion (Data Ingest Mode)

If you have your own dataset that you'd like to bring into DAAF, try profiling it with Data Ingest mode. This is a great way to expand DAAF's capabilities with your own data.

```
I have a CSV of county-level election returns I'd like to profile
and add as a data source. The file is at:
/daaf/data/county-elections/election_returns_2024.csv
```

or

```
Profile this parquet file and create a skill I can use in future
analyses: /daaf/research/my-data/hospital_readmissions.parquet
I also have a data dictionary at: /daaf/research/my-data/codebook.pdf
```

**What you're testing:** Can DAAF systematically profile a dataset you know well, detect its structure, identify coded values and quality issues, and produce a reusable skill? Do its preliminary interpretations match your domain knowledge? This is also a great way to contribute back to the community by sharing new data source skills.

### Level 4: Single Variable Analysis (Simple Full Pipeline)

Ask DAAF to analyze a single variable from a single dataset you already know well. This will kick off a Full Pipeline run, but a very simple and approachable one.

```
Can you analyze the distribution of school-level poverty rates
across all public elementary schools in California for the most
recent year available? I'm interested in basic descriptive
statistics and a histogram.
```

**What you're testing:** Can DAAF correctly fetch, clean, and describe a dataset you're already familiar with? Do the descriptive statistics match what you'd expect? Is the cleaning approach reasonable? This is where you start validating DAAF's *execution* quality, not just its knowledge.

### Level 5: Simple Correlational/Longitudinal Analysis

Ask DAAF to look at the relationship between two variables of interest, possibly over time.

```
Help me understand how average school-level poverty rates have
changed over the past decade for public high schools, broken out
by urbanicity (city, suburb, town, rural). Show me the trends
and any notable patterns.
```

**What you're testing:** Can DAAF handle multi-year data, create meaningful groupings, and produce time-series visualizations? Are the trends sensible? Does it properly handle years with data quality issues (COVID years, for instance)?

### Level 6: Multivariate Analysis

Now get more abstract and complex. Ask about relationships between multiple variables that require joining data sources and more sophisticated statistical approaches.

```
Help me better understand the relationships between college
selectivity, student academic preparedness, graduation rates,
and student socioeconomic backgrounds. What patterns emerge
when we look at these together?
```

or

```
What linkages exist between school-level resources (per-pupil
expenditure, teacher-student ratio), student socioeconomic
status, and access to advanced coursework? Can you tease apart
these relationships?
```

**What you're testing:** Can DAAF correctly join multiple data sources, handle the complexity of multi-variable analysis, and produce interpretable results? This is where DAAF's rigorous validation pipeline really earns its keep -- there are many more places for subtle errors to creep in.

**Pro tip for this level:** You can even ask DAAF what you should ask it! Try:

```
I'm trying to think of moderately complex research questions
I could use to test the DAAF system, based on the education
data available. Can you suggest a few options related to
educational equity?
```

### Level 7: Replication Exercises

The ultimate test of an analytical framework: can it reproduce results from published research? I am actively trying to assess DAAF's performance by replicating studies conducted by the [Urban Institute's Learning Curve series](https://www.urban.org/projects/learning-curve), which leverage the same Education Data Portal datasets DAAF currently has access to. Many of these studies have [open-source code available](https://github.com/UrbanInstitute/The-Learning-Curve/tree/main) for direct comparison.

You'll want to pick one where the data was solely pulled from the Education Data Portal, and then think about exactly how to rephrase and pose the research question to DAAF to reasonably target the same questions and variables if full, actual replication is your goal. Feel free to steer it as needed conceptually to align.

**What you're testing:** The gold standard -- can DAAF produce results consistent with published, expert-produced research? This is the most rigorous test possible and will surface any systematic issues in the pipeline. There is a genuine and important garden of branching pathways issue here, where different phrasing may suggest different priorities (and thus different decisions made about data specification trade-offs, etc.), but you should be able to get into the right territory. You should also be able to diagnose where and why things diverged, if they did.

If you run replication exercises, I would genuinely love to hear about your results. Please share your findings by [opening an issue](https://github.com/DAAF-Contribution-Community/daaf/issues) -- this kind of validation is invaluable for the entire community.

### Level 8: Charting your own path

From here, you've hopefully gotten a good sense of what DAAF can and cannot do as of right now. It's got strengths, it's got limitations, and there are ways to use it that will probably be more or less useful for different people. My goal here is not to make the single, end-all-be-all best tool for everyone, but to create a unified, pretty good starting point. Use it how you see fit, and if you find ways to make it work better for you, people in the community would probably also benefit from you sharing that knowledge back with others! See [**04. Extending DAAF**](04_extending_daaf.md) and [**05. Contributing**](../CONTRIBUTING.md) for more info there.

Either way, please do keep me posted on what you learn and experience! This is a joint exploration endeavor, at the end of the day.

---

## Session Management: Multi-Session Work and Recovery

Real research analyses take time -- often more time than a single Claude Code session can handle. DAAF is designed to handle this gracefully through its session state management system. Here's what you need to know.

### Understanding Context and Sessions

Claude Code operates within a fixed context window (at time of writing) of roughly 200,000 tokens. As DAAF works through a Full Pipeline analysis, delegating tasks to agents, receiving results, and coordinating the workflow, it gradually fills up this context. When it gets too full, Claude's performance degrades, and it becomes increasingly susceptible to erratic behavior due to **context rot**.

To prevent this, DAAF monitors its own context utilization continuously and manages this proactively:

| Utilization | What Happens |
|-------------|-------------|
| **Below 40%** | Normal operation, no special actions |
| **40-60%** | DAAF starts delegating more work to subagents to keep the orchestrator's context lean |
| **60-75%** | DAAF finishes its current work unit, updates STATE.md thoroughly, and warns you that a restart may be needed soon |
| **Above 75%** | DAAF finalizes STATE.md and recommends restarting the session |

### How Session Recovery Works

When a session needs to restart (whether due to context exhaustion, network interruption, or you simply closing your terminal), DAAF doesn't lose your progress. Here's why:

1. **STATE.md** captures the exact point where work stopped -- which stage, which script, what's been completed, what's next
2. **The Plan document** contains the full methodology and task sequence
3. **All scripts and data files** are already saved to disk
4. **LEARNINGS.md** captures any insights accumulated so far

To resume a session, simply start a new Claude Code session and tell DAAF to pick up where it left off:

```
I need to resume the school poverty analysis we were working on.
The project folder is at research/2026-01-24_School_Poverty_Analysis/
```

DAAF will read STATE.md, understand where it stopped, and resume from that exact point. You don't need to re-explain your research question or re-run any completed stages.

**Reproducibility Verification mode note:** RV mode uses `Reproduction_Report.md` as its session state document instead of STATE.md. If an RV session is interrupted, the Reproduction Report contains a "Session Continuity" section with a restart prompt. The recovery process works the same way — start a new session and paste the restart prompt, and DAAF will pick up where it left off.

### Tips for Multi-Session Work

- **Don't panic if a session ends mid-analysis.** This is undesired but not unexpected for complex analyses. The whole STATE.md system exists precisely for this reason.
- **A session restart is not a failure state.** We're constantly and deliberately toe-ing the line between "giving enough context for Claude to do a good job at what we're asking for" and "filling up the context so much that it gets confused and does weird stuff" to optimize our performance. The session restart is our way of maintaining that balance deliberately as a pressure valve.
- **Let DAAF finish its current "atomic unit" before stopping it as the context window begins to fill.** If DAAF is in the middle of executing a script and running QA, try to let it complete that cycle before stopping. Interrupting mid-script is recoverable but creates a messier restart.
- **You can always check progress.** At any point, you can ask DAAF: "What's the current status of the analysis?" and it'll tell you where things stand.
- **Complex analyses may take several sessions.** A nine-source, multi-year analysis with extensive transformations and multiple statistical tests can easily fill up multiple context windows. This is fine -- I've designed the system such that each session picks up seamlessly and as painlessly as possible from where the last one left off. But it definitely can be annoying doing it multiple times!

---

## Where Things Live in the Repository

Here's a quick reference for what each part of the DAAF repository contains and who it's for:

| Directory | What's In It | Who It's For |
|-----------|-------------|-------------|
| `research/` | Your analysis projects -- notebooks, data, reports, scripts | **You** (this is where all your work lives) |
| `user_reference/` | User documentation (you're reading one right now) | **You** (human-written guides and FAQs) |
| `.claude/agents/` | Specialized agent protocols (12 behavioral definitions) | **DAAF** (and curious users who want to understand how agents work) |
| `agent_reference/` | Detailed workflow documentation, templates, validation rules | **DAAF** (internal reference material for the orchestrator and agents) |
| `.claude/skills/` | Skill definitions providing domain knowledge | **DAAF** (and users who want to create new skills) |
| `scripts/` | Shared utility scripts (like `run_with_capture.sh`) | **DAAF** (copied into each project during setup) |

**Key insight for new users:** Everything you need to review, share, or reproduce is inside the project folder. You can copy the entire folder to a colleague and they'd have everything needed to understand and verify the analysis. That's the whole point of reproducibility.

---

## Recommended Next Steps

- [**03. Best Practices**](03_best_practices.md) — Tips for working with Claude Code, writing effective prompts, ensuring quality and rigor with DAAF, reviewing outputs, and managing context
- [**06. FAQ: Philosophy**](06_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**07. FAQ: Technical Support**](07_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, authentication errors, and other common errors
- [**Back to main**](https://github.com/DAAF-Contribution-Community/daaf/tree/main)
