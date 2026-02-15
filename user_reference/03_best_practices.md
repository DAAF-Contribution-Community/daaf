# 03. Best Practices

**UNDER CONSTRUCTION, EVERYTHING HERE SUBJECT TO CHANGE BY LAUNCH** Practical wisdom for getting the most out of DAAF while maintaining research quality. This guide helps you write effective prompts, review outputs critically, and understand your role in the human-AI research partnership.

[**Back to main**](../.)

---

## Table of Contents
- [**Writing Effective Prompts**](#writing-effective-prompts)
- [**Choosing the Right Engagement Mode**](#choosing-the-right-engagement-mode)
- [**Reviewing the Plan Before Execution**](#reviewing-the-plan-before-execution)
- [**Interpreting Validation Checkpoints and STOP Conditions**](#interpreting-validation-checkpoints-and-stop-conditions)
- [**Reviewing Notebooks, Reports, and Script Logs**](#reviewing-notebooks-reports-and-script-logs)
- [**Human Oversight Responsibilities**](#human-oversight-responsibilities)
- [**When and How to Request Revisions**](#when-and-how-to-request-revisions)
- [**Appropriate vs. Inappropriate Use Cases**](#appropriate-vs-inappropriate-use-cases)
- [**Managing Long Analyses and Session Recovery**](#managing-long-analyses-and-session-recovery)
- [**Recommended Next Steps**](#recommended-next-steps)

---

## Writing Effective Prompts

This is the single most impactful thing you can do to improve the quality of what DAAF produces. I realize that "write better prompts" has become almost cliche advice at this point, but I want to be very concrete here about what that actually means in practice -- because the specifics really matter for a structured research system like DAAF.

### What Makes a Good Request

A good request gives DAAF the four dimensions it needs to scope the work properly:

- **Geography**: Which state, district, or national scope? "California" is much better than "the west coast." "National" is fine if that's what you want.
- **Time period**: Which years? "2018-2022" is ideal. "The past few years" works but forces DAAF to make assumptions you might not agree with.
- **Data granularity**: Are you interested in individual schools, school districts, or colleges/universities? This determines which datasets DAAF reaches for.
- **Analysis focus**: What relationship, trend, or comparison are you trying to understand? "The relationship between poverty and enrollment" is much more actionable than "poverty stuff."

You do *not* need to know the exact dataset names, variable codes, or statistical methods. That is genuinely what DAAF is here to help with. What you *do* need to provide is a clear enough picture that DAAF can make intelligent decisions about those things on your behalf -- decisions you'll then review and approve before anything gets executed.

### Good vs. Less-Good Examples

**Full Pipeline examples (analysis, research, data deliverables):**

| Quality | Example | Why |
|---------|---------|-----|
| Great | "Analyze how school poverty rates in Texas changed from 2018-2022, breaking down trends by school type (charter vs. traditional) and urbanicity" | Specific geography, time range, outcome variable, and two comparison dimensions |
| Good | "Research the relationship between school poverty and enrollment trends in California" | Clear relationship question with geography; time period will be clarified |
| Okay | "Analyze graduation rates by state for the past 5 years" | Has a measure and timeframe, but 50-state analyses are very large -- DAAF will ask about scope |
| Weak | "Tell me about school poverty" | Too broad. DAAF will ask you several clarifying questions before it can proceed |

**Discovery examples (what exists, feasibility):**

| Quality | Example | Why |
|---------|---------|-----|
| Great | "What school-level poverty measures exist, and which would be most reliable for analyzing Title I eligibility gaps?" | Clear topic, specific application, asks for a recommendation |
| Good | "Is it feasible to analyze teacher salaries by district using the available data?" | Direct feasibility question with clear scope |
| Okay | "What data is available on school discipline?" | Workable but broad -- DAAF will identify many endpoints and may ask which angle you care about |

**Targeted Assist examples (quick lookups, definitions):**

| Quality | Example | Why |
|---------|---------|-----|
| Great | "What are the coded values for the charter school status variable in CCD data, and how have those codes changed over time?" | Names the exact dataset and variable, asks a specific follow-up |
| Good | "How is the graduation rate calculated in IPEDS?" | Clear, focused question about a specific metric |
| Okay | "What does enrollment mean?" | Enrollment means different things in different datasets -- DAAF will need to ask which data source |

**Revision examples (changes to existing work):**

| Quality | Example | Why |
|---------|---------|-----|
| Great | "In the Texas poverty analysis from 2026-02-10, update the enrollment filter to exclude virtual schools and re-run the regression" | Names the project, specifies the exact change, and identifies the downstream impact |
| Good | "Add 2023 data to the school poverty analysis and update the trend charts" | Clear scope of change |
| Okay | "Fix my last analysis" | DAAF can probably find it, but "fix" could mean a lot of things |

### The Specificity Spectrum

Here is something I think is genuinely important to internalize: there is a sweet spot for prompt specificity, and it is not "as specific as possible."

**Too vague** triggers a round of clarifying questions. This is not a catastrophe -- DAAF is designed to ask before it assumes -- but it adds an extra back-and-forth that slows you down.

**Too prescriptive** can actually constrain useful exploration. If you say "Use CCD enrollment counts and MEPS poverty estimates for schools in Texas from 2019-2022, join on NCES school ID, and run an OLS regression," you have effectively written the Plan yourself. That is fine if you know exactly what you want, but you may miss that DAAF would have recommended SAIPE district-level poverty estimates instead, or flagged that 2020 CCD data has significant COVID-related reporting gaps.

**The sweet spot** gives DAAF clear scope with room for expertise. You specify *what you want to learn* and *roughly where to look*, and let DAAF figure out the best *how*. Then you review its proposal in the Plan document and push back before any data is touched.

Here is a concrete example of what I mean:

> **Too vague:** "Analyze poverty and schools."
>
> **Sweet spot:** "I want to understand how school-level poverty rates relate to enrollment trends across Texas, roughly 2018-2022. I'm particularly interested in whether the relationship differs between charter and traditional public schools."
>
> **Too prescriptive:** "Download CCD school directory data for Texas 2018-2022 from the schools endpoint, filter to charter_text values, join with MEPS poverty data on ncessch, calculate year-over-year enrollment change as a percentage, and run a fixed-effects panel regression with school and year fixed effects."

The sweet spot works best because DAAF has deep knowledge of the available data sources, their limitations, their coded values, and their quirks. It will surface things you might not have considered -- like the fact that charter school definitions changed in CCD between certain years, or that MEPS poverty estimates have substantial suppression in rural areas. That is exactly the kind of expert guidance you want from the system, and you only get it if you leave room for it.

---

## Choosing the Right Engagement Mode

If you have read [**02. Understanding and Working with DAAF**](02_understanding_daaf.md), you already know about the four modes. Here is the practical decision guide for choosing between them.

### The Quick Decision Tree

Ask yourself these questions in order:

1. **Do I already have an analysis from DAAF that I need to change?** If yes -- Revision Mode.
2. **Do I know exactly what analysis I want, and I am ready to commit to a full pipeline?** If yes -- Full Pipeline Mode.
3. **Am I trying to figure out whether an analysis is even possible with the available data?** If yes -- Discovery Mode.
4. **Do I just need a quick answer about a variable, coded value, or data source?** If yes -- Targeted Assist.

If you are unsure, **start with Discovery**. It is always easier to escalate from Discovery to Full Pipeline than to realize halfway through a Full Pipeline analysis that the data does not support your question. Discovery is low-cost -- it does not create files, write code, or commit you to anything.

### When Discovery Is Better Than Full Pipeline

Use Discovery when:

- **You are exploring a new topic** and do not yet know what data exists. "What variables does CRDC collect on school discipline?" is a Discovery question, not a Full Pipeline request.
- **You are uncertain about feasibility.** "Can I analyze teacher experience levels by school poverty status?" is best answered with a quick Discovery pass first. DAAF might find that the data is there but heavily suppressed, or that the variable you want is only available for certain years.
- **You want to compare potential approaches.** "What are the different ways to measure school poverty, and what are the tradeoffs?" is Discovery territory.
- **You are working with a data source you have never used before.** A Discovery pass lets DAAF surface the caveats and limitations before you invest in a full analysis.

Discovery is fast, cheap (in terms of API usage), and informational. If the findings look promising, DAAF will offer to escalate to a Full Pipeline analysis -- you just confirm and it transitions smoothly.

### When to Start Targeted and Escalate

Targeted Assist is for quick lookups: "What are the values of the `school_type` variable in CCD?" or "How does IPEDS define first-time, full-time students?" These should produce a direct answer in a single exchange, no Plan document, no code.

But sometimes a quick lookup reveals that the question is more complex than you expected. Maybe you ask about a variable and discover it has been redefined across years, or that it interacts with suppression rules in ways that affect your planned analysis. In those cases, DAAF will suggest escalating:

> "Based on these findings, the coded values for this variable changed in 2018, which could affect year-over-year comparisons. Would you like me to explore this more thoroughly in Discovery mode?"

You do not need to plan this in advance. Just start where you are, and let the findings guide the escalation.

### Recognizing When You Need Revision Mode

Revision Mode is for when you already have a completed DAAF analysis and want to modify it. It is **not** for starting over -- it is for building on what exists. Typical revision triggers:

- **Adding a year of data:** "Update the analysis to include 2023 data."
- **Changing a filter or scope:** "Re-run but exclude virtual schools."
- **Adding a new dimension:** "Add a breakdown by urbanicity."
- **Fixing an error you caught:** "The enrollment filter should be >= 100, not >= 50."
- **Extending the analysis:** "Now run the same regression but with district-level controls."

When you request a revision, reference the existing project clearly -- by its title, its date, or both. DAAF will locate the existing Plan, read it, create a new version, and work from there. All prior versions are preserved; nothing gets overwritten.

One important note: some "revisions" are really new projects in disguise. If you want to change the research question entirely, switch data sources, or apply a fundamentally different methodology, it is usually cleaner to start fresh with a new Full Pipeline request rather than revise the old one. DAAF will not prevent you from doing a massive revision, but it may suggest starting over if the scope of changes is large enough that building on the old Plan would be more confusing than helpful.

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

When you want to change something in the Plan, be specific about what and why. Here are some examples:

> "Change the year range to 2019-2022 instead of 2016-2022 -- I want to avoid pre-ESSA data."

> "Add urbanicity as a control variable in the regression. I think the poverty-enrollment relationship differs significantly between urban and rural schools."

> "The observable truth about suppression rates should specify a threshold -- say that suppression rates below 30% are acceptable for proceeding."

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

DAAF is not an oracle. It is not an autonomous research system that you can walk away from and trust to get things right. It is a very powerful -- and sometimes surprisingly thorough -- research *assistant* that operates under strict guardrails. But it is still an LLM-based system, which means it is fundamentally susceptible to the same limitations as all LLM systems: hallucination, sycophancy, over-confidence, and subtle logical errors that look plausible on the surface.

What makes DAAF different from using Claude (or any LLM) ad-hoc is the sheer volume of structured verification layered into the process. But those layers of verification do not eliminate the need for human judgment. They *reduce* the surface area of what you need to verify, and they make verification *easier* by giving you organized, traceable artifacts. That is the exo-skeleton metaphor: DAAF amplifies your expertise, but your expertise is still the thing doing the real work.

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

**Methodological appropriateness.** Is the statistical method right for this research question and data structure? DAAF will choose a method and justify its choice, but the justification might be plausible-sounding without being correct. If you have strong priors about methodology, bring them to the Plan review.

**Substantive interpretation.** DAAF will report that "enrollment declined by 12%," but it cannot tell you whether that decline is policy-relevant, expected, or alarming. It cannot contextualize findings within the broader policy landscape or institutional realities you may know about. That is your job.

**Causal claims.** DAAF is designed to be careful about causal language, but LLMs can drift into causal framing even with guardrails. Scrutinize any finding that implies causation -- especially in observational data, which is all that DAAF currently works with.

**Data source appropriateness.** DAAF knows a lot about the technical properties of each dataset -- variable names, coded values, suppression rules. But it may not know that a particular data source has known quality issues in a specific year for a specific state that were discussed at a conference you attended. Your contextual knowledge matters.

**Sufficiency for your use case.** DAAF can tell you the suppression rate is 28% and that this is within its acceptable bounds. Whether 28% suppression is acceptable *for your specific use case* -- whether this is an exploratory analysis for internal discussion or a finding that will inform a policy decision -- is a judgment call that only you can make.

**Ethical considerations.** DAAF does not assess the ethical dimensions of your analysis. If you are working with data that involves vulnerable populations, politically sensitive topics, or potential for misuse of findings, those considerations are entirely your responsibility.

### The Trust-but-Verify Compact

Here is how I think about the division of labor:

| Risk Category | What Could Go Wrong | DAAF's Role | Your Role |
|--------------|---------------------|-------------|-----------|
| **Data integrity** | Corrupted, missing, or wrong data | Catches most issues via CP1-CP4 and QA1-QA4b | Spot-check key values against known benchmarks |
| **Analytical logic** | Wrong joins, bad aggregations, incorrect formulas | Catches most issues via per-script QA review | Verify that the transformation sequence makes logical sense |
| **Methodology** | Wrong statistical approach, violated assumptions | Flags some issues; chooses method and justifies | Evaluate whether the method is appropriate for your question |
| **Interpretation** | Over-claiming, under-qualifying, missing context | Generates Limitations section; documents caveats | Assess whether findings are substantively meaningful and properly qualified |
| **Scope** | Analyzing the wrong thing, missing the point | Confirms scope at multiple gates (PSU1, PSU2) | Verify the research question matches your intent |
| **Ethical/policy** | Inappropriate use, harm to populations | Does not assess | Entirely your responsibility |

The bottom line: DAAF handles the *execution quality* -- making sure the code runs correctly, the data is handled properly, and the outputs are internally consistent. You handle the *research quality* -- making sure the right question is being asked, the right method is being used, the findings are properly interpreted, and the whole thing is fit for purpose.

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

I want to be honest about this, because DAAF is a proof-of-concept and it is important to understand what that means in practice.

### Appropriate Uses

These are genuinely good applications for DAAF in its current state:

- **Exploratory analysis with expert oversight.** You have a research question, you want to see what the data shows, and you are prepared to critically evaluate the results. This is the sweet spot.
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
- **Cross-state assessment score comparisons.** State assessments are not comparable across states. Period. DAAF is hard-coded to block these, and for very good reason. If you need cross-state comparisons of student achievement, use NAEP or another common assessment -- and even then, proceed with great care.
- **Analysis on heavily suppressed data.** When more than 50% of your data is suppressed or missing, no amount of sophisticated methodology can overcome the fundamental problem that you do not have enough data. DAAF blocks these for your protection.
- **Analysis presented as AI-generated without disclosure.** If you use DAAF to produce analysis, you should disclose the role of AI assistance in your work. Transparency is non-negotiable. DAAF is designed to make this easy by documenting exactly what it did, but the responsibility to disclose is yours.

### A Note on the Proof-of-Concept Reality

DAAF is a working system that produces real, useful output. But it is also a proof-of-concept that has not yet been battle-tested by a large community of users across a wide range of research questions. This means:

- **There are edge cases that have not been found yet.** I have tested extensively against the education datasets, but I have not tested every variable, every year range, every join combination, or every state. You may find bugs, gaps in documentation, or unexpected behaviors.
- **The validation system is thorough but not exhaustive.** The multi-layer QA catches a lot, but it cannot catch everything -- especially subtle methodological errors that require deep domain expertise to identify.
- **Performance and cost vary significantly by query complexity.** A simple single-dataset descriptive analysis is fast and cheap. A multi-source, multi-year, multi-state analysis with complex joins will take longer, cost more, and have more opportunities for things to go wrong.

This is why I built DAAF as an open-source community project rather than a product. The system needs more eyes, more testing, more edge cases discovered and documented, and more diverse research questions thrown at it. If you find issues, please [open an issue](https://github.com/DAAF-Contribution-Community/daaf/issues) -- you are contributing to making this better for everyone.

---

## Managing Long Analyses and Session Recovery

Full Pipeline analyses -- especially complex ones with multiple data sources, many transformation steps, or large datasets -- can take a while. The actual computation time is not the bottleneck; it is the number of agent invocations and QA cycles. A moderately complex analysis might involve 15-25 separate script executions, each followed by a code review -- and that adds up.

DAAF is designed to handle this, but there are practical realities you should understand.

### How Session State Is Preserved

Every Full Pipeline analysis produces a `STATE.md` file in the project folder. This file tracks:

- **Current stage:** Where in the 12-stage pipeline the analysis currently is
- **Checkpoint results:** Which CPs have been run and their statuses
- **QA results:** Which scripts have been reviewed and their QA verdicts
- **Key decisions:** Methodology choices and their rationale
- **Blockers:** Any unresolved issues

STATE.md is updated continuously as the analysis progresses. It is the single most important file for session recovery -- if context runs out or you need to resume in a new session, STATE.md tells DAAF exactly where to pick up.

### Resuming a Previous Session

If a session ends -- whether because of context exhaustion, an API limit, a network interruption, or simply because you closed the terminal -- you can resume by starting a new Claude Code session and pasting the restart prompt that STATE.md provides. It will look something like:

> "Resume the analysis in `research/2026-02-10 Texas Poverty Analysis/`. Read STATE.md first, then continue from the current stage."

DAAF will read STATE.md, orient itself, and continue from where it left off. You do not need to re-explain the research question or re-approve the Plan -- all of that context is preserved in the project files.

### When to Start a New Session vs. Continue

Context exhaustion is a reality of working with LLMs. DAAF monitors its context utilization and will proactively recommend a session restart when context starts getting tight (typically around 60-75% utilization). Signs that a restart is warranted:

- **DAAF explicitly recommends it.** It will tell you when context is getting high and suggest saving state for restart.
- **Responses are getting noticeably slower or less detailed.** This can be a sign of context pressure.
- **DAAF is forgetting things you told it earlier in the conversation.** If it asks about something you already discussed, context may be degrading.

A session restart is **not** a failure state. It is a designed-in pressure valve. The STATE.md + restart prompt system exists precisely so that the analysis can be split across multiple sessions without loss of quality. In fact, a clean restart at full context capacity will generally produce *better* results than trying to push through with degraded context.

For very complex analyses, you should expect to use 2-3 sessions. That is normal and by design.

---

## Recommended Next Steps

- [**04. Extending DAAF**](04_extending_daaf.md) — How to add new data source skills, analytical tools and methodologies, and creating your own additional specialized agents
- [**06. FAQ: Philosophy**](06_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**07. FAQ: Technical Support**](07_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, authentication errors, and other common errors
- [**Back to main**](../.)
