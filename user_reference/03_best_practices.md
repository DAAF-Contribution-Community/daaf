# 03. Best Practices

Practical wisdom for getting the most out of DAAF while maintaining research quality. This guide helps you write effective prompts, review outputs critically, and understand your role in the human-AI research partnership.

[**Back to main**](../.)

---

## Table of Contents
- [**Writing Effective Prompts**](#writing-effective-prompts)
- [**Reviewing the Plan Before Execution**](#reviewing-the-plan-before-execution)
- [**Interpreting Validation Checkpoints and STOP Conditions**](#interpreting-validation-checkpoints-and-stop-conditions)
- [**Reviewing Notebooks, Reports, and Script Logs**](#reviewing-notebooks-reports-and-script-logs)
- [**Human Oversight Responsibilities**](#human-oversight-responsibilities)
- [**When and How to Request Revisions**](#when-and-how-to-request-revisions)
- [**Appropriate vs. Inappropriate Use Cases**](#appropriate-vs-inappropriate-use-cases)
- [**Using Git Version Control**](#using-git-version-control)
- [**Using VSCode and Similar Interfaces**](#using-vscode-and-similar-interfaces)
- [**Recommended Next Steps**](#recommended-next-steps)

---

## Writing Effective Prompts

This is the single most impactful thing you can do to improve the quality of what DAAF produces. I realize that "write better prompts" has become almost cliche advice at this point, but I want to be very concrete here about what that actually means in practice -- because the specifics really matter for a structured research system like DAAF and your experience with using it.

### What Makes a Good Request

Building off of what we discussed in [**02. Understanding and Working with DAAF**](02_understanding_daaf.md) re: context management principles: A good request ultimately helps steer the LLM in the right directions and enhances its likelihood of doing what you really want it to do. As many in the AI space are advocating, you really need to ask yourself: What kind of instruction would **you** need to do the task you're asking well? What kind of specifics, details, and process guidance would be helpful for you, or a colleague you're delegating to? Time spent crafting your prompt with more detail and specifics pay off almost infinitely for quality down the road.

When it comes to DAAF, there are a few dimensions of specificity you can provide to help it scope and navigate the work properly:

- **Geography**: Are you interested in a particular state, region, or just nation-wide? Or all of the above, separately? Be specific
- **Time period**: Which years? Something specific like "2018-2022" is ideal, knowing that it may need to adjust based on specific data availability and trade-offs. "The past few years" works but is vague and encourages DAAF to make assumptions you might not agree with. Explicit is better.
- **Data granularity**: Are you interested in individual schools, school districts, or colleges/universities? This determines which datasets DAAF reaches for, and what feels most important
- **Analysis focus**: What relationship, trend, or comparison are you trying to understand? "The relationship between poverty and enrollment" is much more actionable than "general socioeconomics."
- **Priorities**: What matters most to you about this analysis? If it has to make trade-offs, what should go first? Every analysis involves complicated decision-making, so giving it more insight here can help it align with what you'd want it to do.
- **Desired insights**: What are you really trying to say, or learn, or do with the data analysis? Giving it a sense of your goals will also help it make better decisions.

You do *not* need to know the exact dataset names, variable codes, or statistical methods. If you know them, great, but if not, that's fine -- that is genuinely part of what DAAF is designed to handle rigorously on our behalf. What you *do* need to provide is a clear enough picture that DAAF can make intelligent decisions about those things as it works -- decisions you'll then review and approve before anything gets executed.

With that in mind, there are actually some appreciable trade-offs in being too vague or too prescriptive:

**Being too vague** triggers a round of clarifying questions. This is not a catastrophe -- DAAF is designed to ask before it assumes -- but it adds an extra back-and-forth that slows you down.

**Being too prescriptive** can actually constrain useful exploration. If you say "Use CCD enrollment counts and MEPS poverty estimates for schools in Texas from 2019-2022, join on NCES school ID, and run an OLS regression with XYZ as the covariates," you may miss that DAAF would have recommended SAIPE district-level poverty estimates instead, or flagged that 2020 CCD data has significant COVID-related reporting gaps. If you know enough about your data context to be this confident, go for it, but you may benefit from engaging with DAAF on scoping and ideation.

**The sweet spot** gives DAAF clear scope with room for expertise. You specify *what you want to learn* and *roughly where to look*, and let DAAF present its thoughts on *how* that you can further shape and revise. Then you review its proposal in the Plan document and push back before any data is touched.

---

## Reviewing the Plan Before Execution

The Plan is arguably the most important artifact DAAF produces. It is your **last chance** to shape the entire analysis before any data is fetched, any code is written, or any computation is spent. I cannot overstate this: time spent carefully reviewing the Plan is the single highest-leverage activity in the entire DAAF workflow.

After DAAF creates the Plan and validates it internally (via the plan-checker agent), it will present you with a Phase Status Update (PSU2) that summarizes the Plan and gives you the exact file path to read it yourself. **Read the actual file.** The PSU2 summary is helpful but it is a summary -- the full Plan contains critical details about methodology, risk, and scope that the summary necessarily condenses.

### Key Sections to Review

Here is what to look at, roughly in order of priority:

**1. Research Question**

Does the stated research question match what you actually asked? This sounds obvious, but misinterpretation happens -- especially when your original request was somewhat open-ended. If the research question has been narrowed or reframed in a way that does not match your intent, flag it now.

**2. Observable Truths (Must-Haves)**

These are the concrete, testable statements that define what "success" looks like for the analysis. Good observable truths are specific and measurable:

- *Good:* "Analysis shows year-over-year enrollment change from 2018-2022 for Texas charter vs. traditional public schools"
- *Bad:* "Analysis is comprehensive and covers enrollment trends"

There should be at least 3 observable truths. If any of them feel vague or subjective, push back. These truths are what DAAF uses to verify the final output -- if they are squishy, the final verification will be squishy too.

**3. Transformation Sequence**

This is the table of every data operation DAAF plans to execute, in order, with dependencies. Each row will become a separate script that gets executed and reviewed. Look for:

- **Does the sequence make logical sense?** Data should be fetched before it is cleaned, cleaned before it is joined, joined before it is analyzed.
- **Are the join keys specified?** If DAAF plans to merge two datasets, the Plan should specify exactly which columns will be used for the join and what kind of join it is (1:1, 1:many, etc.).
- **Are file paths explicit?** Every task should specify exact input and output file paths, not placeholders like `[TBD]` or `[filename]`.
- **Do the verification criteria make sense?** Each task should have a concrete "done" condition -- something like "Row count > 0 AND row count < 200,000" rather than "Data looks correct."

**4. Risk Register**

The Plan should identify at least one risk with a mitigation strategy. Common risks include: data suppression reducing sample size, COVID-era data gaps, coded value changes across years, and join key mismatches. If you know of risks that DAAF has not identified, add them now. A Plan with zero identified risks is a red flag, not a sign of confidence.

**5. Data Sources and Year Ranges**

Confirm that DAAF is pulling from the right sources for the right years. Pay particular attention to:
- Is the year range correct for your question?
- Are there known data gaps in those years (e.g., COVID disruptions in 2020-2021)?
- Is the geographic scope what you intended?

### Red Flags to Watch For

These are signs that the Plan may need revision before you approve it:

| Red Flag | What It Might Mean | What to Do |
|----------|-------------------|------------|
| Observable Truths are vague or subjective | Final verification will not be rigorous | Ask for more specific, measurable truths |
| No risks identified | Plan may be overconfident | Ask about suppression rates, data gaps, and join complexity |
| Placeholder file paths (`[TBD]`, `[filename]`) | Plan may not be fully specified | Ask DAAF to complete the paths before proceeding |
| Very large scope (50 states, 20 years, 5+ data sources) | Analysis may run very long and incur high API costs | Consider narrowing scope first |
| Missing join cardinality | Joins may produce unexpected row multiplication or loss | Ask DAAF to specify 1:1, 1:many, or many:1 for each join |
| No mention of suppression or missing data | Plan may not account for data quality realities | Ask about expected suppression rates for your data sources and scope |
| Statistical method seems inappropriate | May not match data structure or research question | Ask DAAF to justify its methodological choice |

### How to Request Changes

When you want to change something in the Plan, be specific about what and why, while opening room for discussion. Here are some examples:

> "Can we change the year range to 2019-2022 instead of 2016-2022? I want to avoid pre-ESSA data."

> "I think we should add urbanicity as a control variable in the regression. I think the poverty-enrollment relationship differs significantly between urban and rural schools, right?"

> "The observable truth about suppression rates should probably specify a threshold -- I'd say that suppression rates below 30% are acceptable for proceeding."

> "I do not think OLS regression is the right approach here given the panel structure of the data. Can you consider a fixed-effects model instead?"

**What is easy to change at this stage:** Year ranges, geographic scope, control variables, output format, observable truth language, risk register additions, file naming.

**What requires more thought:** Statistical methodology changes, adding or removing data sources, changing the unit of analysis (e.g., from schools to districts), fundamentally restructuring the transformation sequence.

When in doubt, just tell DAAF what you are thinking. It will let you know if the change is straightforward or if it requires a more significant Plan revision.

---

## Interpreting Validation Checkpoints and STOP Conditions

DAAF runs a *lot* of validation. This is very much by design -- the core philosophy is "every transformation has a validation, no exceptions." But as a user, you do not need to understand every internal check. What you need to understand is: **what the results mean and when you need to act.**

### Understanding Checkpoint Results (CP1-CP4)

DAAF has four primary validation checkpoints embedded directly in its code scripts. These run automatically during execution and check for operational problems -- things like empty data, corrupted values, or data loss.

**CP1: Post-Fetch Validation** -- *"Did we get the data we expected?"*

This runs right after DAAF downloads data from a source. It checks:
- Did data actually come back? (Not empty)
- Are the expected columns present?
- Are the data types correct?
- What is the missingness rate for critical fields?

**What PASSED means:** The data arrived, has the expected structure, and critical fields are mostly populated. You probably will not hear about this unless something went wrong.

**What FAILED means:** Something fundamental is wrong -- the data source returned nothing, critical columns are missing, or more than 90% of a critical field is null. DAAF will STOP and explain the problem. Your options will typically include: trying a different data source, adjusting the scope, or acknowledging a limitation and proceeding with caution.

**CP2: Post-Cleaning Validation** -- *"Is the cleaned data usable?"*

This runs after DAAF has processed the raw data -- filtering out coded values (like -1 for "missing," -2 for "not applicable"), handling suppression, and applying data quality rules. It checks:
- What percentage of data was suppressed or removed?
- Are coded values properly handled (no stray -1s or -2s remaining in analysis columns)?
- Is enough data left for meaningful analysis?

**What PASSED means:** The cleaning worked as expected and the remaining data is sufficient for analysis. Suppression rates are within acceptable bounds.

**What WARNING means:** Suppression rates are elevated (typically 30-50%) -- enough data remains for analysis, but your results may be less precise, particularly for subgroup breakdowns. DAAF will document this but proceed.

**What FAILED means:** Suppression exceeds 50%, meaning more than half the data is missing or suppressed. DAAF will STOP -- this is a hard threshold because analysis on data with >50% suppression is generally unreliable. You will need to decide whether to narrow your scope, change your data source, or acknowledge this as a fundamental limitation.

**CP3: Post-Transformation Validation** -- *"Did the data transformation do what we intended?"*

This runs after every join, aggregation, or derived-variable calculation. It checks:
- Did the row count change as expected? (Joins should not unexpectedly multiply rows)
- Are there new unexpected null values?
- Do derived variables have reasonable distributions?

**What PASSED means:** The transformation produced the expected results. Row counts, null patterns, and distributions look reasonable.

**What FAILED means:** Something went wrong -- row counts dropped by more than 90%, a join produced unexpected nulls, or derived values are clearly incorrect. DAAF will stop and investigate.

**CP4: Pre-Output Validation** -- *"Does the final output meet our commitments?"*

This runs during the synthesis phase (Stages 11-12), checking the complete output against what the Plan promised. It validates:
- Are all required columns present in the analysis dataset?
- Do all promised output files exist (figures, analysis results, report)?
- Are all Observable Truths from the Plan satisfied?
- Does the report have all required sections?

**What PASSED means:** Everything the Plan promised has been delivered. The analysis is consistent with the original research question.

**What FAILED means:** Something is missing -- a figure was not generated, a report section is incomplete, or an Observable Truth was not satisfied. DAAF will identify the gap and attempt to resolve it.

### When DAAF Stops and Asks for Guidance

STOP conditions are moments when DAAF pauses execution and escalates to you. This is **a good thing** -- it means the system is working as intended. DAAF does not power through problems silently. When it encounters something it cannot or should not resolve on its own, it stops and asks you.

Common STOP conditions and what to do about them:

| STOP Condition | What Happened | What You Will See | Your Options |
|----------------|--------------|-------------------|-------------|
| Empty data returned | The data source had no data for your query | Explanation of what was requested and what came back | Adjust scope, try different source, or acknowledge limitation |
| Suppression >50% | More than half the data is suppressed/missing | Suppression rate calculation and affected breakdowns | Narrow geography, reduce subgroups, use different measure |
| Row loss >90% | A transformation (join, filter) dropped most rows | Pre and post row counts with explanation | Check join keys, verify filter logic, adjust criteria |
| Cross-state assessment comparison | You asked to compare test scores across states | Explanation of why this is methodologically invalid | Reframe question (within-state trends are valid) |
| QA BLOCKER after 2 revisions | Code review found a problem that could not be resolved in 2 attempts | Description of the issue, what was tried, why it persists | Guide DAAF's approach, simplify the task, or accept limitation |
| Data unavailable | The dataset simply does not exist for your scope | Explanation of what was looked for | Choose a different data source or adjust scope |

When DAAF stops, it will present the issue in a structured format: what happened, what it tried, your options (with pros and cons), and its recommendation. You do not need to have a solution -- you just need to tell DAAF which direction to go. "Try option 2" or "Let us narrow to just California and see if that helps" are perfectly fine responses.

### QA Findings: BLOCKER vs. WARNING vs. INFO

In addition to the CP checkpoints above, every script DAAF writes gets independently reviewed by a separate code-reviewer agent. Think of this as a second pair of eyes -- an adversarial reviewer whose job is to find problems the original code might have missed. The reviewer classifies its findings by severity:

**INFO:** An observation that does not indicate a problem but is worth noting. Example: "The dataset has 47 states represented instead of 50, which is expected given the query filters." You will generally not see these unless you dig into the QA scripts.

**WARNING:** A potential issue that does not block progress but should be documented. Example: "Suppression rate for rural schools is 38%, which may limit subgroup analysis precision." Warnings are accumulated and presented to you at the Phase Status Update after analysis (PSU4). They do not stop execution, but they flag things you should consider when interpreting results.

**BLOCKER:** A genuine problem that must be fixed before proceeding. Example: "The join produced 40% more rows than expected, indicating a many-to-many join where a many-to-one was specified." Blockers trigger a revision cycle -- DAAF will attempt to fix the script (up to 2 attempts) and re-submit it for review. If the blocker persists after 2 fix attempts, DAAF escalates to you.

The key thing to understand about this system is that **DAAF catches and resolves most issues automatically.** The vast majority of QA findings are INFO or WARNING -- problems that are noted and documented but do not require your intervention. You only hear about BLOCKERs that could not be resolved, and those are rare.

---

## Reviewing Notebooks, Reports, and Script Logs

When a Full Pipeline analysis completes, you will receive several artifacts. Here is how to actually read and evaluate each one, and -- just as importantly -- what to look at first.

### Where to Start

I recommend this review order:

1. **Report** -- Start here for the big picture. Does the narrative make sense? Do the findings answer your research question?
2. **Figures** -- Look at the visualizations referenced in the report. Do they show what the report claims they show?
3. **Plan** -- Skim the Final Review Log section (appended at the end) to see if DAAF flagged any deviations or concerns.
4. **Notebook** -- Dive into specific stages if you want to verify how a particular result was derived.
5. **Script logs** -- Go here for the deepest level of detail on any specific step.

You do *not* need to read everything in detail every time. The report is the synthesis; the notebook is the evidence; the scripts are the primary source. Go as deep as you need to based on how much you trust the results and how high-stakes the analysis is.

### Reading the Report

The report follows a standard structure (Executive Summary, Key Findings, Data & Methodology, Limitations, etc.). When reviewing it, focus on:

**Key Findings:** Are these findings genuinely supported by the data? Look for specificity -- "Enrollment declined by 12% between 2019 and 2022" is verifiable. "Enrollment showed interesting trends" is not.

**Limitations section:** This is often the most important section. DAAF is instructed to be candid about limitations, suppression rates, data gaps, and caveats. Read this carefully. If the limitations section is suspiciously short or generic, that is a red flag -- not because DAAF is hiding something, but because the system may not have adequately identified the limitations.

**Figure references:** The report should reference specific figures by filename. Verify that the referenced figures exist and actually show what the report says they show. This is a simple but effective check.

**Data source citations:** The report should cite each data source used. Verify that these match the sources specified in the Plan.

### Reading the Notebook

The marimo notebook is a walkthrough tool -- it assembles the actual scripts that were executed (verbatim, not rewritten) alongside their execution logs. When you open it in your browser, you will see:

- **Section headers** identifying which stage and script is being displayed
- **Code cells** containing the literal code from the script files
- **Execution log accordions** you can expand to see what happened when the script ran: runtime, exit code, row counts before and after, validation results

What to look for in the notebook:

- **Execution logs that show warnings or unexpected values.** Expand the accordions and scan for anything that looks off.
- **Row counts at each stage.** You should be able to trace the data from raw (usually large) to processed (usually smaller after filtering) to analysis (potentially larger or smaller depending on joins). Dramatic unexpected changes in row count deserve investigation.
- **Validation results.** Each script includes embedded validation. Look for CP status: PASSED, WARNING, or FAILED.

What you will *not* see in the notebook:

- New analysis code that was not in the scripts (the notebook compiles scripts, it does not create new code)
- Interactive dashboards or widgets (unless you specifically requested one as a follow-up deliverable)
- Any transformations without embedded execution logs

### Reading Script Execution Logs

Every script file in the `scripts/` directory has its execution log appended to the end of the file as comments. You can read these in any text editor. The execution log includes:

- **Start/end timestamps** and total runtime
- **Exit code** (0 = success, non-zero = failure)
- **stdout** -- everything the script printed during execution (row counts, validation messages, summary statistics)
- **stderr** -- any warnings or errors that occurred

If a script failed, you will also find versioned revisions:
- `01_fetch-ccd.py` -- Original (with its failed log embedded)
- `01_fetch-ccd_a.py` -- First revision (with its own log)
- `01_fetch-ccd_b.py` -- Second revision, if the first fix did not work

The notebook only includes the final successful version, but all versions are preserved in the `scripts/` directory for audit trail purposes. If you want to understand *why* a script needed revision, read the original's execution log and the QA review that flagged the issue (stored in `scripts/cr/`).

### Reading QA Review Scripts

The `scripts/cr/` directory contains the code-reviewer's inspection scripts for each stage. These are named by convention:

- `stage5_01_cr1.py` -- First QA review of Stage 5, script 01
- `stage7_02_cr2.py` -- Second QA iteration for Stage 7, script 02

These scripts contain the adversarial checks that the code-reviewer ran, along with their results. If a QA review returned WARNING or BLOCKER, the findings will be in these files. You generally do not need to read these unless you are investigating a specific concern -- but they are there for full transparency.

---

## Human Oversight Responsibilities

I want to frame this section carefully, because I think the right mental model here is genuinely important.

DAAF is not an oracle. It is not an autonomous research system that you can walk away from and trust to get things right. It is not "fire-and-forget." Yes, it is a very powerful -- and sometimes surprisingly thorough -- assistant that operates under strict guardrails. But it is still an LLM-based system, which means it is fundamentally susceptible to the same limitations as all LLM systems: hallucination, sycophancy, over-confidence, and subtle logical errors that look plausible on the surface.

What makes DAAF different from using Claude (or any LLM) ad-hoc is the sheer volume of structured verification layered into the process. But those layers of verification do not eliminate the need for human judgment. They *reduce* the surface area of what you need to verify, and they make verification *easier* by giving you organized, traceable artifacts. That is the exo-skeleton metaphor: DAAF amplifies your expertise, but your expertise is still the thing doing the real work to ensure that outputs are worth anything at all.

### What DAAF Validates Automatically

These safeguards run without your involvement throughout the pipeline:

| Safeguard | What It Does | Where It Happens |
|-----------|-------------|-----------------|
| **Primary Checkpoints (CP1-CP4)** | Validates data at fetch, clean, transform, and output stages -- catches empty data, type errors, data loss, missing outputs | Embedded in every script |
| **Secondary QA (QA1-QA4b)** | Independent adversarial review of every script by a separate code-reviewer agent | After every script execution |
| **Iteration Protocol** | Forces every transformation into small steps: DESCRIBE, CODE, EXECUTE, VALIDATE, DECIDE | During all data operations |
| **Batch Size Limits** | Maximum 1-2 transformations per execution cycle to prevent error accumulation | During Stages 5-8 |
| **STOP Conditions** | Automatic pause when data quality thresholds are breached | Throughout execution |
| **Version Control** | Every file revision is saved separately -- nothing is ever overwritten | All stages |
| **Plan-Checker Validation** | Automated 6-dimension validation of the Plan before execution begins | Stage 4.5 |
| **Source Citations** | Proper citations generated automatically for all data sources used | Report generation |

That is a substantial amount of automated quality control. It means that the majority of *operational* errors -- wrong data types, broken joins, corrupted files, missing columns, data loss during transformation -- will be caught before you ever see the results.

### What Requires Your Judgment

But automated validation cannot assess everything. Here is what still requires a human researcher with domain expertise:

**Formulating the right question.** Is this a good question? Is it rooted in reasonable assumptions? Does it account for what we know from the literature? DAAF is thoughtful, and will likely push back on strange or erroneous assumptions, but it'll also definitely back down if you ask it to. You need to be the final say in what is or isn't worth investigating.

**Methodological appropriateness.** Is the statistical method right for this research question and data structure? DAAF will choose a method and justify its choice, but the justification might be plausible-sounding without being correct. If you have strong priors about methodology, bring them to the Plan review.

**Substantive interpretation.** DAAF will report that "enrollment declined by 12%," but it cannot tell you whether that decline is policy-relevant, expected, or alarming. It cannot contextualize findings within the broader policy landscape or institutional realities you may know about. That is your job.

**Causal claims.** DAAF is designed to be careful about causal language, but LLMs can drift into causal framing even with guardrails. Scrutinize any finding that implies causation -- especially in observational data, which is all that DAAF currently works with.

**Data source appropriateness.** DAAF knows a lot about the technical properties of each dataset -- variable names, coded values, suppression rules. But it may not know that a particular data source has known quality issues in a specific year for a specific state that were discussed at a conference you attended. Your contextual knowledge matters.

**Sufficiency for your use case.** DAAF can tell you the suppression rate is 28% and that this is within its acceptable bounds. Whether 28% suppression is acceptable *for your specific use case* -- whether this is an exploratory analysis for internal discussion or a finding that will inform a policy decision -- is a judgment call that only you can make.

**Ethical considerations.** DAAF does not assess the ethical dimensions of your analysis. If you are working with data that involves vulnerable populations, politically sensitive topics, or potential for misuse of findings, those considerations are entirely your responsibility.

---

## When and How to Request Revisions

One of DAAF's most practically useful features is the ability to revise and extend completed analyses without starting from scratch. The version control system means every revision creates new files alongside the originals -- nothing gets lost.

### Types of Revisions

Here is a rough guide to common revision types and what to expect:

**Quick adjustments** (usually straightforward):
- Changing a filter value ("exclude schools with enrollment < 50 instead of < 100")
- Updating year ranges ("add 2023 to the existing 2018-2022 analysis")
- Changing visualization details ("use a bar chart instead of a line chart for the state comparison")
- Adjusting the report framing ("emphasize the equity angle more")

**Moderate changes** (may require re-running some stages):
- Adding a new breakdown dimension ("also break down by urbanicity")
- Adding a control variable to a regression
- Switching from one poverty measure to another
- Adding a robustness check or sensitivity analysis

**Major changes** (close to starting over -- consider a new project):
- Changing the unit of analysis (schools to districts, or vice versa)
- Switching the primary data source entirely
- Fundamentally changing the research question
- Changing the statistical methodology (from descriptive to causal inference, for example)

### Framing Revision Requests

When requesting a revision, include:

1. **Which project** -- by title, date, or both. "The Texas poverty analysis from 2026-02-10" or "the CRDC discipline study."
2. **What specifically to change** -- the more precise, the better. "Change the enrollment threshold from 50 to 100" is better than "adjust the enrollment filter."
3. **Why** (if it is not obvious) -- "I realized virtual schools are skewing the enrollment trends" helps DAAF understand the intent, not just the mechanics.
4. **Downstream expectations** -- if you know the change should affect later stages, say so. "Re-run the regression after updating the filter" tells DAAF that you want the downstream analysis updated, not just the data cleaning step.

### What Gets a New Version vs. What Gets a New Project

**New version** (same project folder, new suffixed files):
- The core research question stays the same
- You are refining, extending, or correcting the existing analysis
- The same data sources are used (potentially with additions)
- The revision builds on the existing Plan's logic

**New project** (new project folder, fresh start):
- The research question is fundamentally different
- You are switching to entirely different data sources
- The unit of analysis has changed
- The prior work does not serve as a useful foundation

When you are on the fence, DAAF will offer its assessment. But a useful rule of thumb: if the existing Plan would need more than 50% of its transformation sequence rewritten, you are probably better off with a new project.

---

## Appropriate vs. Inappropriate Use Cases

DAAF is still very much in its nasceny, and there is only so much that one person and his friends can do to check guardrails, test robustness, and so on. With that in mind, it is important to be extremely transparent about what that means in practice.

### Appropriate Uses

These are genuinely good applications for DAAF in its current state:

- **Exploratory analysis with expert oversight.** You have a research question, you want to see what the data shows, you have a good sense of what to expect already, and you are prepared to critically evaluate the results. This is the sweet spot.
- **Learning and skill-building.** DAAF is excellent for learning how datasets work, what variables are available, and how data pipelines are constructed. Even if you never use DAAF's outputs directly, working with the system teaches you things about the data.
- **Rapid prototyping of analyses.** You need to quickly test whether an analysis direction is viable before investing significant manual effort. DAAF can produce a working prototype in a fraction of the time.
- **Scaling established methodologies.** You have already done this kind of analysis manually and know what correct output looks like. DAAF lets you run the same analysis across more states, more years, or more breakdowns than you could do alone.
- **Demonstrating AI-assisted research patterns.** DAAF is useful for showing colleagues, students, or stakeholders what rigorous AI-assisted research can look like -- and what guardrails it requires.
- **Producing replication-style exercises.** Running DAAF against questions where published answers already exist (from Urban Institute Learning Curve or similar) is an excellent way to evaluate both DAAF's capabilities and its limitations.

### Uses Requiring Extensive Additional Validation

These are possible but carry significant caveats:

- **Policy-informing analysis.** If your analysis will inform real policy decisions, DAAF's output should be treated as a *starting point* that requires thorough independent verification by a qualified researcher. Every finding should be checked against known benchmarks, and the methodology should be reviewed by someone with deep domain expertise.
- **Publication-adjacent work.** DAAF can accelerate the data preparation and exploratory analysis phases of a study destined for publication, but the analytical decisions, robustness checks, and interpretation must be held to the standard of your target venue -- which typically means significant additional human work beyond what DAAF produces.
- **Cross-dataset analyses involving complex joins.** DAAF handles joins reasonably well for well-documented datasets, but joins between datasets with different geographic units, different year definitions, or ambiguous key relationships require careful human scrutiny.

### Never Appropriate

These should not be done with DAAF (or any LLM-based system) regardless of the guardrails:

- **High-stakes decisions based solely on AI outputs.** Never use DAAF's results as the sole basis for decisions that significantly affect people -- resource allocation, program elimination, individual assessments, legal proceedings. Always have qualified humans independently verify any findings that will drive consequential decisions.
- **Analysis presented as AI-generated without disclosure.** If you use DAAF to produce analysis, you should disclose the role of AI assistance in your work. Transparency is non-negotiable in my view. DAAF is designed to make this easy by documenting exactly what it did, but the responsibility to disclose is yours.

---

## Using Git Version Control

When you start using DAAF, you'll find that it produces a LOT of files, and it does a LOT of things at once. Once best practice I'd strongly encourage is to get comfortable with using Git for version control. This is part of why I treat it as a prerequisite for using DAAF in the installation process (spoilers: there were other ways to do it!): This type of work with LLMs just benefits so immensely from having a full audit log of file edits and changes at all times, with the ability to roll back changes and identify issues quickly.

I would strongly recommend making a private "fork" of the DAAF repository for you to work in and back up all of your research files to (though DAAF by default will NOT back up your parquet data files to avoid accidentally sharing data up to the cloud). Teaching Git is a bit beyond the scope of this project, but you absolutely can and should ask Claude to tell you more about:

- What does it mean to make a fork of a GitHub repo?
- What does Git actually do, and why is it useful?
- What's a commit? What does it do?
- How can I track changes in DAAF using Git? What would that workflow look like?
- What tools can I use to make this whole process easier?

There are also a ton of guides online and on YouTube, etc. Take some time to get oriented! It's an immensely useful skillset.

---

## Using VSCode and Similar Interfaces

In addition to using Git, and part and parcel with it: I currently use [VSCode](https://code.visualstudio.com) as my main driver for working with DAAF and Claude Code. VSCode is basically a nice interface that collects all of the following in an easy-to-use sort of format:
- File management within the Docker volume (using the "Dev containers" extension)
- File editing for markdown files, and viewing markdown files in their rendered format
- Tracking changes for files using Git in a super easy and intuitive interface
- Doing intensive file searches, edits, and similar

There are a bunch of similar alternatives that are also designed to be a bit more teched-up with coding agents built in (e.g., Cursor), but I've found VSCode to work great! Your mileage may vary -- the recommendation here is really just, find an interface that works for you and your workflow to make this work easier and reduce the frictions involved.

---

## Recommended Next Steps

- [**04. Extending DAAF**](04_extending_daaf.md) — How to add new data source skills, analytical tools and methodologies, and creating your own additional specialized agents
- [**06. FAQ: Philosophy**](06_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**07. FAQ: Technical Support**](07_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, authentication errors, and other common errors
- [**Back to main**](../.)
