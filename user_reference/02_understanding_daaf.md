# 02. Understanding and Working with DAAF

This guide is designed to turn a new user into a confident user. It expands on the README and installation guide's brief overview into a thorough walkthrough of how DAAF works, what it produces, what to expect, where it can fail, and how to think about AI-assisted research analysis for your workflows more critically. This will guide you through your first real analysis with DAAF to understand what's happening under the hood, and suggest further testing pathways to really get comfortable with the strengths and weaknesses of DAAF.

[**Back to main**](../.)

---

## Table of Contents
- [**Core Concept: Context Windows and Prompt Engineering 101**](#core-concept-context-windows-and-prompt-engineering-101)
- [**The Four Engagement Modes**](#the-four-engagement-modes)
- [**The Mental Model: Orchestrator, Agents, Skills, Validation**](#the-mental-model-orchestrator-agents-skills-validation)
- [**What a Full Pipeline Analysis Looks Like**](#what-a-full-pipeline-analysis-looks-like)
- [**Anatomy of a Completed Analysis**](#anatomy-of-a-completed-analysis)
- [**Available Data Sources**](#available-data-sources)
- [**Your First Full Analysis: A Guided Walkthrough**](#your-first-full-analysis-a-guided-walkthrough)
- [**Easing in with Progressively More Advanced Queries**](#easing-in-with-progressively-more-advanced-queries)
- [**Session Management: Multi-Session Work and Recovery**](#session-management-multi-session-work-and-recovery)
- [**Where Things Live in the Repository**](#where-things-live-in-the-repository)
- [**Recommended Next Steps**](#recommended-next-steps)

---

> **Quick tip before you begin**: If you have any questions, concerns, issues, or confusion about **anything** you read in this guide: Ask Claude for help! Point it to any document, section, or sentence, and then ask it to help you understand it better. It's got visibility into the whole project documentation at-will, so it should be able to help you out as you go. This kind of personalized assistance should be invaluable for anyone getting onboarded into using DAAF and Claude Code more generally!

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
* The system is designed to intelligently "select" the right context to provide to Claude before your query/question/chat, based on what you provide in your query/question/chat. But this is **NOT** foolproof, and simply cannot account for every possibility. You may find it's not working very well for what you want, because I wasn't able to design for that style of work. Trying to write your query in a different way can help, or you can help us improve DAAF by [opening an issue](https://github.com/DAAF-Contribution-Community/daaf/issues) and telling us about it!
* Because thoughtfully shaping the context is our way of shaping Claude's thinking from what I lovingly describe as an over-eager recent MBA graduate to a thoughtful, careful research colleague, DAAF really only works with the cutting-edge models like Opus 4.6, and it pushes them to their limit to take advantage of their full context windows where possible. This is why it is SO expensive to use at this time; settling for less, we sacrifice a lot of expertise and reliability and rigor. It's a careful balancing act of optimization that no one really has fully figured out!

So that's the gist for now. Onward, to actually using DAAF!

---

## The Four Engagement Modes

DAAF first classifies every request you make into one of four **engagement modes**. This is how we properly prompt-engineer Claude, because each mode triggers a fundamentally different workflow, different outputs, and different expectations for what input you'll need to provide to steer it well. Understanding these modes is the single most useful thing you can do to work with DAAF effectively, because it helps you frame your questions in the way most likely to get you what you actually want, and better understand what's going on behind the scenes.

Before doing anything else, DAAF will tell you which mode it's classifying your request into, explain why, and ask you to confirm. This is intentional. You should always have the chance to say "actually, I just wanted a quick lookup" or "actually, let's go deeper on this." Here's what each of them do, and how the workflow works so you know when and why you'd use each:

### Targeted Assist Mode

**Trigger words:** "what are the values for," "how is X defined," "lookup," "what does this variable mean," "explain this table..."

**What it is:** A quick, focused lookup about available data tables and variables. You have a specific question about a data source, variable, coded value, or definition, and you want a direct answer without any exploration overhead. DAAF loads a single relevant data knowledge source skill and gives you what you need quickly. You can think of this like a data documentation oracle -- saving you some time on determining what data are available, limitations, year ranges, etc.

**What you get:**
- A direct, specific answer to your question
- Supporting context where relevant (e.g., "this variable uses coded values where 1=Regular school, 2=Special education, 3=Vocational...")
- Pointers to relevant documentation if you want to dig deeper

**Expected time investment:** Seconds. One question, one answer.

**When to use it:** When you already know what you're looking for and just need the specific detail. "What does `free_lunch` mean in the CCD data?" "What years are available for CRDC?" "What's the difference between `enrollment` and `fall_enrollment` in IPEDS?"

**When NOT to use it:** When your question is actually broader than you realize. If you find yourself asking five Targeted Assist questions in a row, you probably want Discovery mode instead (described next). DAAF will suggest this if it notices the pattern.

### Discovery Mode

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

**Escalation:** If Discovery turns up promising data, DAAF will suggest: "Based on these findings, would you like me to proceed with a Full Pipeline analysis?" You can say yes, refine the question, or say no and walk away with just the findings.

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

### Revision Mode

**Trigger words:** "fix," "update," "change," "modify the analysis," "revise," "redo," "can you adjust"

**What it is:** You have an existing analysis that needs changes, and you want DAAF's help to improve it. Maybe you want to rethink a measure, add a new variable, change the year range, run a different statistical test, or fix something that didn't look right. First, point DAAF to the name of the project folder. Then, DAAF locates your existing project, reads the Plan, and creates a *new version* of the relevant artifacts -- it never modifies the originals.

**What you get:**
- A new version of the Plan document incorporating your changes
- Updated scripts, data, and outputs as needed
- A full Final Review even for minor fixes (no shortcuts on quality)
- All prior versions preserved in the same project folder

**Expected time investment:** Depends on the scope of the revision. Changing a year range might take 15 minutes; fundamentally rethinking the methodology could be nearly as long as a new analysis (and you may seriously want to consider going that route instead with clearer and more directed prompts/research questions, depending!).

**When to use it:** After you've received a completed analysis and want to adjust something. Reference your project by keywords or date -- e.g., "Can you update the Texas poverty analysis to include 2023 data?" or "In the 2026-01-15 enrollment study, can we use a different measure of school size?"

**How the version system works:** All versions live in the same project folder. Prior versions are **never** modified or overwritten -- that's a non-negotiable rule. The versioning uses date suffixes: the original analysis might be `2026-01-24`, revision 1 becomes `2026-01-24a`, revision 2 becomes `2026-01-24b`, and so on. This means you always have a full audit trail of how the analysis evolved.

### Switching Between Modes

DAAF supports clean transitions between modes when it makes sense:

| From | To | When it happens |
|------|----|-----------------|
| Discovery | Full Pipeline | Findings suggest a feasible and valuable analysis |
| Targeted Assist | Discovery | Your question reveals a broader data landscape worth exploring |
| Targeted Assist | Full Pipeline | A quick lookup reveals an actionable analysis opportunity |

DAAF will always propose these escalations explicitly and wait for your confirmation. It should never silently switch modes on you.

---

## The Mental Model: Orchestrator, Agents, Skills, Validation

Okay, this is the section where I want to give you genuine intuition for how this all works under the hood. You don't *need* to understand the architecture to use DAAF -- you can absolutely just type a research question and let it run. But if you want to understand *why* DAAF does what it does, *why* it pauses when it pauses, and *why* the output is structured the way it is, this section will hopefully make all of that click.

I'm going to use an analogy that I think captures it well: **DAAF is intended to mirror the workflows of a well-run research lab** with you as the PI.

### The Orchestrator: Your Lab Director

When you type a message to DAAF, you're talking to the **orchestrator**, whose behavior is dictated by the [`CLAUDE.md`](../CLAUDE.md) file as its main context. Think of the orchestrator as a lab director -- the person who takes your research question, figures out what needs to be done, decides who on the team should do each piece, coordinates the whole effort, and reports back to you at key milestones.

The orchestrator should NOT be doing the hands-on work itself, because its primary value-add and contribution is coordination and workflow management. It doesn't write analysis scripts, it doesn't clean data, it doesn't run regressions. What it does is:

- **Classify your request** into an engagement mode (Full Pipeline, Discovery, etc.)
- **Delegate tasks** in proper sequence to specialized agents, itself providing them with the right context and instructions they need to do their jobs well
- **Enforce quality gates** -- certain milestones that MUST be passed before work continues and the work product changes hands from one agent to another
- **Report progress** to you and pause for your approval at key junctures to ensure you, the PI, approve of the direction of the work. It will also enforce work revisions as needed if you request it
- **Keep the big picture in mind** -- tracking what's been done, what's next, and what decisions have been made, to ensure it's addressing the core intentions/vision of the PI

The orchestrator is the most important part of DAAF, because it needs to simultaneously understand the whole workflow process and the broad context of the work in mind, while also being technical enough and specific enough to give precise, targeted instructions and context to every other LLM assistant involved in the process.

### Specialized Agents: Your Research Team

The "team members" in this lab are **agents** -- versions of Claude provided a clear behavioral protocol and persona defining exactly how they should think and operate. You can even see the exact context instructions provided to each in [the agents folder](../agents/). Agents are not knowledge repositories; they're *behavioral definitions*. An agent answers the question: "How should I behave when I'm doing this specific type of work?"

Here's a few examples of the team members with the links to each of their actual instruction files if you want to dig in more:

| Agent | Role in the Lab Analogy | What They Actually Do | 
|-------|------------------------|----------------------|
| [**research-executor**](../agents/research-executor.md) | Technician/Analyst | Executes one data task at a time (fetch, clean, transform, analyze) with meticulous pre/post validation |
| [**code-reviewer**](../agents/code-reviewer.md) | Senior Technician/Analyst | Reviews every single script the research-executor produces, looking for bugs, methodology errors, and data quality issues |
| [**source-researcher**](../agents/source-researcher.md) | Research Assistant | Deep-dives into a specific data source's documentation, collection protocols, caveats, and gotchas for shared team awareness |
| [**data-planner**](../agents/data-planner.md) | Research Design Lead | Synthesizes all the preliminary findings into a detailed, executable research plan |

The point here is that we want to provide very different context to Claude when faced with different tasks. Trying to get Claude to do everything equally well is impossible given fixed context window limitations, and trying to do so will ultimately confuse it and cause dreaded **context rot** (where an LLM becomes unpredictable, incoherent, and erratic due to over-filled or poorly structured context it can't make sense of). This means that we need to split responsibilities across "versions" of Claude provided very different instructions and behavioral protocols to get it to perform these tasks well in tandem.

> **Quick definitional note:** An **Agent** is the general phrase we use to describe any tailored/pre-specified set of behavioral protocols for an LLM assistant. Each of the above team members in this analogy are Agent definitions. As a user, you can ask Claude directly to take on an agent persona and begin working. However, with DAAF's default workflows, the orchestrator actually calls up and tasks each agent above itself, so you never have to; agents become **subagents** when they are called by another assistant in this way, instead of directly by the user.

Ultimately, the orchestrator's job is to know which agent/team member to call up at any one time, and to also know very thoughtfully what it needs to tell that subagent in order for the subagent to do its job effectively with necessary context and guidance. You can see how the orchestrator is trained to talk with these agents in [the agents README](../agents/README.md) and [the orchestrator skill invocation reference](../agent_reference/03_SKILL_INVOCATIONS.md)). Subagent orchestration is an extremely new and active area of development in the broader field of AI at-large right now, which is part of why a system as complex as DAAF has only recently become possible.

### Skills: Your Team's Reference Library (24 Volumes)

If agents define *behavior* ("how should I work?"), then **skills** define *knowledge* ("what do I need to know?"). Skills are structured knowledge documents that agents load on demand -- think of them as specialized reference manuals that your research team pulls off the shelf when they need domain-specific information.

There are currently 24 skills organized into a few categories:

**Data source skills** (14 skills) -- one for each major education data source:
- What endpoints exist and what they contain
- What variables mean and how they're coded
- What caveats and limitations to watch for
- What suppression rules apply (e.g., cells with fewer than a certain number of students are suppressed for privacy)
- Common cross-state comparability issues

**Tool skills** (5 skills) -- how to use specific Python libraries:
- `polars` for data manipulation (similar to tidyverse or pandas)
- `plotnine` for static, publication-quality plots (ggplot2 in Python)
- `plotly` for interactive visualizations
- `marimo` for reactive Python notebooks
- `data-scientist` for general methodology and rigor principles

**Meta skills** (2 skills) -- for extending DAAF itself:
- `skill-authoring` for creating new skills
- `education-data-explorer` and `education-data-query` for finding and fetching data
- `education-data-context` for interpreting data caveats and coded values

**The key insight:** Skills are loaded *by agents*, not by the orchestrator. When the orchestrator delegates a task to the research-executor, it tells the agent: "Load the `education-data-source-ccd` skill for this task." The agent pulls up the relevant reference material, uses it to guide its work, and then returns its findings to the orchestrator. This keeps the orchestrator's context lean (it doesn't need to hold the full contents of every skill in memory) and ensures each agent gets exactly the knowledge it needs for its specific task.

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

After every single script passes its embedded checkpoints, a *completely separate agent* -- the code-reviewer -- independently inspects both the code and its output data. The code-reviewer approaches each script with an adversarial mindset, specifically looking for:

| QA Checkpoint | When It Runs | What It Catches |
|---------------|-------------|-----------------|
| **QA1** | After fetch scripts | Schema problems, ID uniqueness violations, suspicious distributions |
| **QA2** | After cleaning scripts | Incorrect coded value handling, flawed filtering logic |
| **QA3** | After transformation scripts | Bad join cardinality, aggregation errors, derived column mistakes |
| **QA4a** | After analysis scripts | Invalid statistical methods, violated assumptions, unreliable results |
| **QA4b** | After visualization scripts | Misleading charts, incorrect data sources, missing labels |

**Why two layers?** Because they catch different types of errors. Primary validation catches *operational failures* -- the data is empty, the types are wrong, something clearly broke. Secondary QA catches *logical errors* -- the code runs fine and produces output, but the methodology is wrong, the join logic is subtly off, or the interpretation doesn't match what the data actually shows. These are the insidious errors that humans regularly miss when reviewing LLM-generated code, and they're exactly the errors that matter most for research integrity.

**The critical rule:** Every script gets both layers. No exceptions. And the code-reviewer inspects each script *immediately* after it's executed -- not batched at the end of a stage. This matters because an error in script 1 that goes undetected will silently propagate through scripts 2, 3, and 4, compounding into a mess that's far harder to diagnose and fix.

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
9. **The `research-executor`** works through each task in the Plan, one at a time, with **the `code-reviewer`** inspecting each script immediately after execution
10. **The orchestrator** pauses twice more for your review (Phase Status Updates 3 and 4)
11. **The `notebook-assembler`** compiles all scripts into a browsable notebook
12. **The `report-writer`** creates the stakeholder report
13. **The `data-verifier`** performs adversarial final verification
14. **The orchestrator** delivers everything to you with file paths

That's the core loop. Every piece has a job. Every job has a quality check. Every quality check has consequences (stop, revise, or proceed). And you get four mandatory check-in points where DAAF pauses and waits for your explicit approval before continuing.

---

## What a Full Pipeline Analysis Looks Like

Let me walk you through what actually happens during a Full Pipeline analysis -- not the technical details of agent invocations and gate conditions, but what *you'll see* and what *you'll need to do* at each phase. The whole process has 5 phases and 12 stages, but from your perspective, there are really just 4 "chapters" separated by mandatory check-in points.

### Phase 1: Discovery & Scoping (Stages 1-3.5)

**What happens:** DAAF takes your research question and goes on a deep reconnaissance mission. It explores what data sources are available, what variables exist, what years are covered, and -- critically -- what the caveats and limitations are. It does all of this by dispatching specialized agents to investigate each relevant data source in depth, and then consolidating everything into a unified picture.

**What you'll see:** After confirming your engagement mode, DAAF will go quiet for a few minutes while its exploration agents work. Then it'll come back with a **Phase Status Update** -- a structured summary of what it found. This will typically include:

- Which data sources are relevant to your question (and which aren't)
- What key variables are available and what they measure
- Year ranges and geographic coverage
- Source-specific caveats you should know about (suppression rules, COVID-era data quality issues, cross-state comparability problems, etc.)
- A feasibility assessment: can your question be answered with available data?
- A recommended analytical approach

**What you need to do:** Read the findings summary. This is your first and most important quality check -- does DAAF's understanding of your question match what you actually meant? Are there data sources it missed or included unnecessarily? Do the caveats raise concerns you want to discuss?

Then: confirm you'd like to proceed to planning, ask questions, or redirect.

### Phase 2: Planning (Stages 4-4.5)

**What happens:** DAAF creates a detailed research plan -- and I mean *detailed*. The Plan document captures the research question verbatim, the full methodology (what data to fetch, how to clean it, what transformations to apply, what analyses to run, what visualizations to create), the exact sequence of tasks with dependencies, expected outputs, risk factors, and "Observable Truths" -- specific, measurable outcomes the analysis should produce. This Plan is then independently validated by a plan-checker agent across six dimensions (completeness, consistency, feasibility, testability, clarity, scope).

**What you'll see:** A second Phase Status Update with:

- The research question as stated in the Plan
- A methodology summary (what statistical approaches, key decisions)
- The data sources and year ranges confirmed
- An overview of the task sequence (how many tasks, in what order)
- The plan-checker's validation result
- The exact file path to the Plan document so you can read it in full

**What you need to do:** This is the most important review point. **Read the Plan.** Not just the summary DAAF gives you -- the actual Plan document. This is the contract for everything that follows. If the methodology is wrong, the year range is off, or a key variable is missing, *this is the time to catch it*. Everything from here forward executes according to the Plan.

Then: confirm you'd like to proceed to data acquisition, request revisions, or adjust scope.

### Phase 3: Data Acquisition & Preparation (Stages 5-6)

**What happens:** DAAF fetches the actual data from configured data access mirrors, validates it against expectations (CP1), then cleans it -- handling coded values, filtering out suppressed data, calculating missingness rates, and preparing it for analysis (CP2). Every single script goes through the full execute-then-QA loop: the research-executor writes and runs the script, then the code-reviewer independently inspects both the code and the output data.

**What you'll see:** A third Phase Status Update summarizing:

- Datasets acquired: what sources, how many records, what years, file paths
- Data quality: missingness rates, suppression rates for each dataset
- Cleaning actions taken and their impact (rows removed, values recoded)
- QA results for each script (did the code-reviewer find any issues?)
- Any deviations from the Plan during fetch/clean
- An assessment of whether the data is ready for analysis

**What you need to do:** Review the data quality summary. Are suppression rates acceptable? Did cleaning remove an alarming number of records? Are the missingness patterns expected given what you know about the data? This is where domain expertise matters most -- DAAF can report the numbers, but *you* know whether a 15% suppression rate in rural districts is concerning or expected.

Then: confirm you'd like to proceed to analysis, or flag concerns.

### Phase 4: Analysis & Notebook Development (Stages 7-10)

**What happens:** This is where the actual analysis work gets done. DAAF executes transformations (joins, derived variables, aggregations) one at a time with validation after each, runs the statistical analyses specified in the Plan, generates visualizations, assembles everything into a marimo notebook, and aggregates all QA findings from the entire pipeline for a final quality review.

**What you'll see:** A fourth Phase Status Update with:

- Transformation summary: what joins were performed, what variables were derived, the final analysis dataset shape
- Statistical results: key findings with effect sizes and confidence intervals
- Key visualizations (with file paths so you can inspect them)
- The full QA aggregation across all stages -- any accumulated warnings from the code-reviewer
- Any deviations from the Plan methodology
- Notebook compilation status

**What you need to do:** Review the key findings and visualizations. Do the results make substantive sense given your domain knowledge? Are there any surprising findings that warrant deeper investigation? Check the QA aggregation -- if there are accumulated warnings, do any of them concern you?

Then: confirm you'd like DAAF to generate the final report and complete verification.

### Phase 5: Synthesis & Delivery (Stages 11-12)

**What happens:** The report-writer agent synthesizes everything -- the Plan, notebook, statistical results, visualizations, and QA findings -- into a stakeholder report. Then the data-verifier performs adversarial final verification: does the analysis actually answer the research question? Do the data, notebook, and report all tell the same story? Are there any silent failures or stub outputs? Finally, DAAF consolidates all the lessons learned during the project and delivers everything to you.

**What you'll see:** A delivery summary with:

- File paths to every artifact (Plan, notebook, report, data files, figures, lessons learned)
- A brief summary of key findings
- Any final caveats or limitations
- A learnings summary highlighting insights about the data and process

**What you need to do:** Review the deliverables! Open the report, inspect the notebook, look at the visualizations. This is the part where your expertise as a researcher really matters -- DAAF has done its best to be rigorous and transparent, but *you* are the one who ultimately validates whether the analysis is sound, the interpretation is reasonable, and the conclusions are justified. That's the whole point of the human-in-the-loop philosophy.

---

## Anatomy of a Completed Analysis

After a Full Pipeline run completes, you'll have a project folder containing everything DAAF produced. Let me walk you through each artifact so you know what you're looking at and how to use it.

### The Project Folder

Every analysis lives in a self-contained folder under `research/`, named with the date and a descriptive title:

```
research/2026-01-24 School Poverty Analysis/
├── 2026-01-24 School Poverty Analysis Plan.md
├── 2026-01-24 School Poverty Analysis.py
├── 2026-01-24 School Poverty Analysis Report.md
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

### The Plan Document

**What it is:** The single most important artifact in the project. The Plan is DAAF's research design document -- it captures everything about what was done and *why*. If the scripts are the "what," the Plan is the "why."

**What's inside:**
- **Research Question** -- your original question, verbatim, plus any clarifications
- **Observable Truths** -- specific, measurable outcomes the analysis must produce (e.g., "Analysis will report the correlation between school poverty rates and AP course enrollment, with confidence intervals")
- **Data Sources** -- which datasets are being used, what endpoints, what years, and why
- **Methodology** -- the statistical approach, key decisions, and their rationale
- **Transformation Sequence** -- the exact ordered list of tasks (fetch, clean, transform, analyze, visualize) with dependencies, wave assignments for parallel execution, and input/output file paths
- **Risk Register** -- what could go wrong and how to handle it
- **Key Decisions Log** -- every methodological choice made during the project, with reasoning
- **Final Review Log** -- notes from the data-verifier's final check

**How to read it:** Start with the Research Question and Observable Truths -- do they match your intent? Then skim the Transformation Sequence to understand the flow of work. Check the Key Decisions Log for anything surprising. The Plan is meant to be comprehensive enough that someone unfamiliar with the project could understand exactly what was done and why.

**Why it matters:** The Plan is your audit trail. If you or a colleague ever needs to understand how a finding was derived, the Plan traces the full chain of reasoning from question to methodology to execution. It's also what makes Revision Mode possible -- DAAF reads the existing Plan to understand what was done before proposing changes.

### The Scripts Directory

**What it is:** The primary execution artifacts. I cannot stress this enough -- **the scripts are the real work product**, not the notebook. Every data fetch, every cleaning operation, every transformation, every analysis, and every visualization is captured as a standalone Python script in the `scripts/` directory, organized by stage.

**What's inside each script:**
- Clear section headers (`# --- Config ---`, `# --- Load ---`, `# --- Transform ---`, `# --- Validate ---`, `# --- Save ---`)
- Inline audit trail comments explaining the *intent* and *reasoning* behind every operation (not just what the code does, but *why*)
- Embedded validation assertions (`assert`, `print` statements showing data shape, distributions, etc.)
- An **appended execution log** at the bottom of each script (added automatically after execution) showing exactly what happened: duration, exit code, stdout/stderr output, pre/post data state

**How to read scripts:** Scripts read top-to-bottom like a lab notebook -- no functions, no classes, no jumping around. Start at the top, follow the comments, and check the execution log at the bottom. The execution log is the "ground truth" for what actually happened when the script ran.

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
marimo run 'research/YYYY-MM-DD Title/YYYY-MM-DD Notebook.py' --host 0.0.0.0 --port 2718 --headless
```
Then open [http://localhost:2718](http://localhost:2718) in your browser. You can also open the `.py` file in any text editor -- marimo notebooks are just Python.

### The Report

**What it is:** A stakeholder-facing summary report synthesizing the key findings, methodology, data, limitations, and visualizations into a readable narrative. Think of it as the "executive summary" version of the analysis -- what a colleague, policymaker, or reviewer would want to read to understand what was found and how.

**What's inside:**
- Executive summary with headline findings
- Detailed methodology section (data sources, cleaning approach, statistical methods)
- Key findings with supporting statistics and figure references
- Data limitations and caveats
- Appendices with technical details

**How it differs from the notebook:** The notebook is for *inspection* -- browsing every line of code and verifying what happened. The report is for *communication* -- telling the story of what was found and what it means. They're complementary artifacts serving different audiences.

**How to view it:** The report is a Markdown (.md) file. You can open it in any text editor, but it'll look much nicer in a Markdown viewer. I recommend copying the contents into a free online viewer like [StackEdit](https://stackedit.io/app), or installing a Markdown viewer extension for your code editor.

### Data Files (Raw and Processed)

**`data/raw/`** -- The original data files exactly as they were fetched from the data sources. These are your "original ingredients" and are never modified after download.

**`data/processed/`** -- Cleaned and transformed versions of the data, including the final analysis dataset. These are the files that were actually used for statistical analyses and visualizations.

**Why parquet?** Every data file is saved in Apache Parquet format. Parquet is a columnar storage format that preserves data types (integers stay integers, dates stay dates), compresses efficiently, and is fast to read. CSV files lose type information (everything becomes a string), which introduces subtle bugs. Parquet prevents an entire category of data quality issues. You can open parquet files in Python (with `polars` or `pandas`), R (with `arrow`), or many other tools.

### Output: Analysis Results and Figures

**`output/analysis/`** -- Statistical analysis results saved as parquet files. Regression coefficients, summary statistics, comparison tables, etc.

**`output/figures/`** -- Data visualizations saved as PNG images. These are the same figures referenced in the report. You can open them with any image viewer.

### STATE.md and LEARNINGS.md

**STATE.md** -- A session state file that tracks DAAF's progress through the analysis. If a session is interrupted (context exhaustion, network issues, etc.), STATE.md allows DAAF to resume exactly where it left off. You generally don't need to read this unless debugging a session issue.

**LEARNINGS.md** -- A lessons-learned document capturing insights about the data and the analysis process. This includes data idiosyncrasies discovered during the analysis, interpretation concerns, and suggested improvements to DAAF's documentation. This file is designed to be immediately actionable -- you can share it back with the community to help improve DAAF for future users.

---

## Available Data Sources

DAAF comes ready to work with 14+ education data sources via the Urban Institute Education Data Portal. Here's what's available:

### K-12 Data Sources

| Source | Description | Key Variables |
|--------|-------------|---------------|
| **CCD** | Common Core of Data -- public school/district directory, enrollment, staffing, finance | Enrollment, FRL eligibility, school type, staffing counts |
| **CRDC** | Civil Rights Data Collection -- discipline, course access, equity indicators | Suspensions, expulsions, AP enrollment, harassment |
| **EDFacts** | State assessment results, graduation rates, accountability | Proficiency rates, ACGR graduation rates |
| **MEPS** | Model Estimates of Poverty in Schools -- school-level poverty | Poverty rate at 100% FPL |
| **SAIPE** | Small Area Income and Poverty Estimates -- district-level poverty | Children in poverty, median income |

### Postsecondary Data Sources

| Source | Description | Key Variables |
|--------|-------------|---------------|
| **IPEDS** | Integrated Postsecondary Education Data System -- comprehensive college data | Enrollment, graduation rates, finance, staffing |
| **College Scorecard** | Post-college outcomes from Treasury/IRS data | Earnings, debt, repayment rates |
| **PSEO** | Postsecondary Employment Outcomes -- graduate employment | Earnings by field, employment by industry |
| **FSA** | Federal Student Aid -- Title IV program data | Pell grants, loans, default rates |
| **NACUBO** | Endowment study data | Endowment size, investment returns |
| **EADA** | Equity in Athletics -- college sports data | Participation, coaching, expenses by gender |
| **Campus Safety** | Clery Act crime statistics | Campus crime, fire safety |

### Supporting Data Sources

| Source | Description |
|--------|-------------|
| **NHGIS** | Census geography and demographic data for school communities |
| **NCCS** | Nonprofit organization data for private institutions |

These data sources can be combined in powerful ways. For example, you might join CCD enrollment data with MEPS poverty estimates and CRDC discipline data to analyze how school-level poverty relates to disciplinary patterns while controlling for enrollment size and school type. DAAF handles the complexity of these cross-source joins for you, including navigating the different ID systems, year availability, and suppression rules across sources.

---

## Your First Full Analysis: A Guided Walkthrough

Alright, let's do this for real. I'm going to walk you through a complete analysis from start to finish -- what you type, what DAAF says back, and what you need to do at each step. I'll use a straightforward research question that's genuinely interesting and exercises multiple data sources: **How does school-level poverty relate to access to Advanced Placement (AP) courses?**

This walkthrough assumes you've completed the installation from [01. Installation & Quick Start](01_installation_and_quickstart.md) and have Claude Code running inside your Docker container.

### Step 1: Start with Discovery (optional but recommended)

Before diving into a full analysis, I'd recommend starting with a Discovery mode question to see what's available. Type something like:

```
What data does DAAF have access to about school poverty and AP course
enrollment? I'm interested in understanding the relationship between
these at the school level.
```

DAAF will classify this as **Discovery Mode** and confirm:

```
Engagement Mode: Discovery
Reasoning: You're asking what data exists for a specific topic
before committing to analysis
Scope: Identify available data sources, variables, and feasibility
```

Confirm, and DAAF will come back with a findings summary describing:
- **CCD** has school-level enrollment data and school characteristics
- **MEPS** has school-level poverty estimates
- **CRDC** has AP course enrollment data by school
- Available years, geographic scope, and key caveats for each

This gives you a feel for the data landscape before you commit to a full analysis.

### Step 2: Request a Full Pipeline Analysis

Now that you know the data exists, ask for the analysis:

```
Let's go ahead and analyze the relationship between school-level
poverty and AP course access. I'd like to look at this nationally
for the most recent year of overlapping data across sources. Let's
look at this for regular public high schools specifically.
```

DAAF will classify this as **Full Pipeline Mode** and present a Pre-Flight Check:

```
Full Pipeline Analysis: Pre-Flight Check

This analysis will create:
- [ ] Research Plan document
- [ ] STATE.md session state file
- [ ] Comprehensive analytic scripts covering data fetch, clean,
      join, transformation, analysis, and QA
- [ ] Validated datasets (raw + processed)
- [ ] Marimo notebook walkthrough
- [ ] Statistical analysis results
- [ ] Key data visualizations
- [ ] Summary stakeholder report
- [ ] LEARNINGS.md lessons learned

Estimated scope:
- Data sources: CCD, MEPS, CRDC
- Years: [most recent overlapping year]
- Approximate records: ~15,000-20,000 high schools
- Geographic scope: National

Please confirm whether you'd like me to begin with this approach,
or let me know if you have any changes you'd like to make.
```

Review the scope and confirm. DAAF will then go to work on Phase 1 (data exploration and source deep-dives).

### Step 3: Review Phase 1 Findings

After several minutes, DAAF will present **Phase Status Update 1** -- a comprehensive summary of what it found during discovery and source investigation. This will include:

- Specific endpoints and variables identified for each data source
- Year overlap analysis (e.g., "CCD and CRDC both have 2020-21 data, but MEPS most recent is 2019-20")
- Caveats: COVID impacts on 2020-21 data, CRDC data suppression patterns, MEPS estimation methodology
- Recommended approach: which year to use, how to handle suppression, join strategy

**Your job:** Read this carefully. Are there caveats that concern you? Does the recommended year make sense? Do you want to adjust scope?

Confirm to proceed to Phase 2 (planning).

### Step 4: Review the Plan

DAAF will create a detailed Plan and have it independently validated, then present **Phase Status Update 2** with a Plan summary and the exact filepath.

**Your job: Read the Plan document.** I mean it -- actually open the file and read through it. Pay special attention to:

- **Observable Truths:** Are these the outcomes you care about?
- **Transformation Sequence:** Does the task flow make logical sense?
- **Methodology:** Are the statistical approaches appropriate for your question?
- **Risk Register:** Are the identified risks reasonable?

If everything looks good, confirm to proceed to data acquisition.

### Step 5: Monitor Execution (Phases 3 and 4)

DAAF will now work through the analysis pipeline -- fetching data, cleaning it, transforming it, running analyses, and creating visualizations. Each script gets written, executed, and independently reviewed by the code-reviewer before the next one begins.

You'll see two more Phase Status Updates (PSU3 after data acquisition, PSU4 after analysis), each summarizing what happened and asking for your confirmation. These are your opportunities to catch issues before DAAF moves forward.

**What to watch for in PSU3 (data quality):**
- Suppression rates -- are they reasonable for your analysis?
- Row counts -- did cleaning remove an unexpected number of records?
- Missingness -- are critical variables sufficiently populated?

**What to watch for in PSU4 (analysis results):**
- Do the statistical findings make substantive sense?
- Are the visualizations clear and accurate?
- Were there any accumulated QA warnings that concern you?

### Step 6: Review Deliverables

After you confirm PSU4, DAAF generates the report, runs final verification, and delivers everything with file paths. You'll receive:

- **The Report** -- Read through the key findings, methodology, and limitations
- **The Notebook** -- Browse the compiled scripts and their execution logs in your browser
- **The Visualizations** -- Inspect the figures in `output/figures/`
- **LEARNINGS.md** -- See what data quirks and process insights emerged

**How to open the notebook:**
```bash
marimo run 'research/2026-MM-DD School Poverty AP Access/2026-MM-DD School Poverty AP Access.py' --host 0.0.0.0 --port 2718 --headless
```

Then navigate to [http://localhost:2718](http://localhost:2718) in your browser.

### What Comes Next?

Once you've reviewed the deliverables, you have several options:

- **Request revisions:** "Can you redo the analysis controlling for school size?"
- **Request additional deliverables:** "Can you create an interactive dashboard of the key findings?"
- **Request sub-analyses:** "Can you run this separately for urban vs. rural schools?"
- **Move on:** Start a new analysis on a different topic

All of these are just another message to DAAF. Revisions and additions will be handled through Revision Mode, creating new versioned artifacts while preserving the originals.

---

## Easing in with Progressively More Advanced Queries

I get it -- jumping straight into a Full Pipeline analysis on day one is a lot. The whole premise of this project is that DAAF is surprisingly robust, but I think the right way to build confidence is to start small and work your way up. Here's a concrete progression I'd recommend, designed to let you assess DAAF's knowledge and capabilities at each level of complexity:

### Level 1: Quick Ask (Targeted Assist Mode)

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

### Level 2: Single Variable Analysis (Simple Full Pipeline)

Ask DAAF to analyze a single variable from a single dataset you already know well. This will kick off a Full Pipeline run, but a very simple and approachable one.

```
Can you analyze the distribution of school-level poverty rates
across all public elementary schools in California for the most
recent year available? I'm interested in basic descriptive
statistics and a histogram.
```

**What you're testing:** Can DAAF correctly fetch, clean, and describe a dataset you're already familiar with? Do the descriptive statistics match what you'd expect? Is the cleaning approach reasonable? This is where you start validating DAAF's *execution* quality, not just its knowledge.

### Level 3: Simple Correlational/Longitudinal Analysis

Ask DAAF to look at the relationship between two variables of interest, possibly over time.

```
Help me understand how average school-level poverty rates have
changed over the past decade for public high schools, broken out
by urbanicity (city, suburb, town, rural). Show me the trends
and any notable patterns.
```

**What you're testing:** Can DAAF handle multi-year data, create meaningful groupings, and produce time-series visualizations? Are the trends sensible? Does it properly handle years with data quality issues (COVID years, for instance)?

### Level 4: Multivariate Analysis

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

### Level 5: Replication Exercises

The ultimate test of an analytical framework: can it reproduce results from published research? I am actively trying to assess DAAF's performance by replicating studies conducted by the [Urban Institute's Learning Curve series](https://www.urban.org/projects/learning-curve), which leverage the same Education Data Portal datasets DAAF currently has access to. Many of these studies have [open-source code available](https://github.com/UrbanInstitute/The-Learning-Curve/tree/main) for direct comparison.

```
I'd like to replicate the findings from [specific Urban Institute
study]. Can you help me reproduce their analysis using the same
data sources?
```

**What you're testing:** The gold standard -- can DAAF produce results consistent with published, peer-reviewed research? This is the most rigorous test possible and will surface any systematic issues in the pipeline.

If you run replication exercises, I would genuinely love to hear about your results. Please share your findings by [opening an issue](https://github.com/DAAF-Contribution-Community/daaf/issues) -- this kind of validation is invaluable for the entire community.

---

## Session Management: Multi-Session Work and Recovery

Real research analyses take time -- often more time than a single Claude Code session can handle. DAAF is designed to handle this gracefully through its session state management system. Here's what you need to know.

### Understanding Context and Sessions

Claude Code operates within a "context window" -- a fixed amount of information (roughly 200,000 tokens) that it can hold in working memory at any time. As DAAF works through a Full Pipeline analysis, delegating tasks to agents, receiving results, and coordinating the workflow, it gradually fills up this context. When it gets too full, the session needs to restart.

DAAF monitors its own context utilization continuously and manages this proactively:

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
The project folder is at research/2026-01-24 School Poverty Analysis/
```

DAAF will read STATE.md, understand where it stopped, and resume from that exact point. You don't need to re-explain your research question or re-run any completed stages.

### Tips for Multi-Session Work

- **Don't panic if a session ends mid-analysis.** This is normal and expected for complex analyses. The whole STATE.md system exists precisely for this reason.
- **Let DAAF finish its current "atomic unit" before stopping.** If DAAF is in the middle of executing a script and running QA, try to let it complete that cycle before stopping. Interrupting mid-script is recoverable but creates a messier restart.
- **You can always check progress.** At any point, you can ask DAAF: "What's the current status of the analysis?" and it'll tell you where things stand.
- **Complex analyses may take 2-4 sessions.** A three-source, multi-year analysis with extensive transformations and multiple statistical tests can easily fill up multiple context windows. This is fine -- each session picks up seamlessly from where the last one left off.

---

## Where Things Live in the Repository

Here's a quick reference for what each part of the DAAF repository contains and who it's for:

| Directory | What's In It | Who It's For |
|-----------|-------------|-------------|
| `research/` | Your analysis projects -- notebooks, data, reports, scripts | **You** (this is where all your work lives) |
| `user_reference/` | User documentation (you're reading one right now) | **You** (human-written guides and FAQs) |
| `agents/` | Specialized agent protocols (12 behavioral definitions) | **DAAF** (and curious users who want to understand how agents work) |
| `agent_reference/` | Detailed workflow documentation, templates, validation rules | **DAAF** (internal reference material for the orchestrator and agents) |
| `.claude/skills/` | Skill definitions providing domain knowledge | **DAAF** (and users who want to create new skills) |
| `scripts/` | Shared utility scripts (like `run_with_capture.sh`) | **DAAF** (copied into each project during setup) |

Each analysis creates a self-contained project folder under `research/`:

```
research/YYYY-MM-DD [Title]/
├── YYYY-MM-DD [Title] Plan.md          # Research plan and decisions
├── YYYY-MM-DD [Title].py               # Marimo WALKTHROUGH (assembles scripts)
├── YYYY-MM-DD [Title] Report.md        # Stakeholder SUMMARY
├── scripts/                            # *** PRIMARY EXECUTION ARTIFACTS ***
│   │                                   # Each script has embedded execution log
│   ├── stage5_fetch/                   # Data retrieval scripts
│   ├── stage6_clean/                   # Data cleaning scripts
│   ├── stage7_transform/              # Transformation scripts
│   ├── stage8_analysis/               # Analysis and visualization scripts
│   ├── cr/                            # Code-reviewer QA inspection scripts
│   └── debug/                         # Debugger diagnostic scripts (if needed)
├── data/
│   ├── raw/                           # Original fetched data (.parquet)
│   └── processed/                     # Cleaned and transformed data (.parquet)
├── output/
│   ├── analysis/                      # Statistical results (.parquet)
│   └── figures/                       # Visualizations (.png)
├── STATE.md                           # Session state for recovery
└── LEARNINGS.md                       # Lessons learned
```

**Key insight for new users:** Everything you need to review, share, or reproduce is inside the project folder. You can copy the entire folder to a colleague and they'd have everything needed to understand and verify the analysis. That's the whole point of reproducibility.

---

## Recommended Next Steps

- [**03. Best Practices**](03_best_practices.md) — Tips for working with Claude Code, writing effective prompts, ensuring quality and rigor with DAAF, reviewing outputs, and managing context
- [**06. FAQ: Philosophy**](06_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**07. FAQ: Technical Support**](07_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, authentication errors, and other common errors
- [**Back to main**](../.)
