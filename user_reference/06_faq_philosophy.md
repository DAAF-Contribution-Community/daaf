# 06. FAQ: Philosophy & Design Rationale

**UNDER CONSTRUCTION, EVERYTHING HERE SUBJECT TO CHANGE BY LAUNCH** This document addresses the "why" behind DAAF's design decisions and the broader questions about AI in research. It's where the project's intellectual contribution lives — beyond the technical how-to, these are the ideas and principles that shaped the framework.

[**Back to main**](../.)

---

## Table of Contents

- [**DAAF Design Rationale**](#daaf-design-rationale)
  - [Why iterative validation instead of batch execution?](#q-why-iterative-validation-instead-of-batch-execution)
  - [Why multi-agent instead of single-agent?](#q-why-multi-agent-instead-of-single-agent)
  - [Why human-in-the-loop at every gate?](#q-why-human-in-the-loop-at-every-gate)
  - [Why file-first execution instead of interactive notebooks?](#q-why-file-first-execution-instead-of-interactive-notebooks)
  - [Why is this a proof-of-concept and not production software?](#q-why-is-this-a-proof-of-concept-and-not-production-software)
  - [Why so many validation layers? Isn't this overkill?](#q-why-so-many-validation-layers-isnt-this-overkill)
  - [Why does the Plan document exist?](#q-why-does-the-plan-document-exist-cant-the-ai-just-start-analyzing)
- [**AI in Research: Broader Questions**](#ai-in-research-broader-questions)
  - [Can AI meaningfully assist with complex research tasks?](#q-can-ai-meaningfully-assist-with-complex-research-tasks)
  - [What does the hallucination problem mean for data analysis specifically?](#q-what-does-the-hallucination-problem-mean-for-data-analysis-specifically)
  - [What's the appropriate level of trust for AI-generated analysis?](#q-whats-the-appropriate-level-of-trust-for-ai-generated-analysis)
  - [How does DAAF's approach relate to reproducibility and open science?](#q-how-does-daafs-approach-relate-to-reproducibility-and-open-science)
  - [What does AI assistance replace in a research workflow, and what doesn't it replace?](#q-what-does-ai-assistance-replace-in-a-research-workflow-and-what-doesnt-it-replace)
- [**Looking Forward**](#looking-forward)
  - [Where could this approach go?](#q-where-could-this-approach-go)
  - [What would need to change for production use?](#q-what-would-need-to-change-for-production-use)
  - [Why LGPL-3.0 for an AI research tool?](#q-why-lgpl-30-for-an-ai-research-tool)
  - [How does DAAF relate to other AI coding tools?](#q-how-does-daaf-relate-to-other-ai-coding-tools)
  - [What about the environmental and energy costs of this kind of intensive AI use?](#q-what-about-the-environmental-and-energy-costs-of-this-kind-of-intensive-ai-use)
  - [What does this mean for the next generation of researchers?](#q-what-does-this-mean-for-the-next-generation-of-researchers)
- [**Recommended Next Steps**](#recommended-next-steps)

---

## DAAF Design Rationale

### Q: Why iterative validation instead of batch execution?

The cardinal rule of DAAF is: **Every transformation has a validation. No exceptions.**

This is not a stylistic preference. It is the single most important design decision in the entire framework, and it flows directly from a hard truth about working with LLMs: AI-generated code is fundamentally less trustworthy than code written by a human expert, because the AI does not actually understand your data the way you do.

When a skilled researcher writes a data transformation, they carry rich contextual knowledge about what the data *should* look like at every step. They know that enrollment counts should never be negative, that a left join on district ID should not suddenly triple the row count, that a variable coded as 1-7 probably should not have values of 99 appearing after a recode. They notice when something looks wrong because they have deep intuition built over years of working with data like this. An LLM has none of that. It can write syntactically correct code that produces plausible-looking output while silently corrupting your data in ways that are extremely difficult to catch after the fact.

This is why DAAF refuses to let the AI write a complete pipeline and then debug the mess at the end. Instead, every single transformation -- every filter, every join, every recode, every aggregation -- is immediately followed by a validation checkpoint that confirms the transformation did what it was supposed to do. Did the row count change by a reasonable amount? Are the expected columns still present? Did any critical values become null? Is the distribution of key variables still sensible?

The practical consequence is that errors get caught at the exact point where they are introduced, when the context for understanding and fixing them is freshest. The alternative -- batch execution followed by end-to-end debugging -- is a nightmare even when humans write the code. When an AI writes the code, it is genuinely irresponsible. A wrong join key in step 2 of a 10-step pipeline can silently propagate through eight subsequent transformations, producing results that look superficially reasonable but are completely wrong. I have seen this happen. It is not a theoretical risk.

Is this slower than just letting the AI rip through a complete pipeline? Absolutely. Is it worth it? I firmly believe so. The time you "save" by skipping validation is time you will spend -- many times over -- trying to figure out where things went wrong after the fact. Or worse: you will never figure it out, and you will publish results based on corrupted data. That is not a tradeoff any responsible researcher should accept.

### Q: Why multi-agent instead of single-agent?

If you have used any LLM for an extended conversation, you have probably noticed that it starts to get... worse. The responses become more generic, it forgets things you told it earlier, it contradicts its own previous statements. This is not your imagination. It is a fundamental limitation called **context degradation**, and it is one of the most important practical constraints in working with LLMs today.

Every LLM has a finite context window -- a maximum amount of text it can "see" at any given time. As that window fills up with conversation history, code, data outputs, and accumulated instructions, the model's ability to attend carefully to all of it degrades. It is not that the information disappears; it is that the model's ability to use it effectively diminishes. Think of it like trying to hold an increasingly complex conversation while someone keeps handing you more and more documents to keep track of simultaneously.

For a complex research analysis that involves exploring data sources, writing a plan, fetching data, cleaning it, transforming it, analyzing it, visualizing it, assembling a notebook, writing a report, and conducting a final review -- you are talking about a LOT of accumulated context. A single-agent approach would require one LLM instance to hold all of that in its head simultaneously. By the time you get to the analysis stage, the model has largely forgotten the nuances of what it learned during data exploration. By the time you get to the report, it has forgotten half of its analysis decisions.

DAAF solves this by decomposing the work into specialized agents, each operating with a fresh context window focused on a specific task. The data explorer agent only needs to know about data discovery. The code reviewer agent only needs to know about the specific script it is reviewing. The report writer only needs the Plan, key findings, and template. Each agent gets the full benefit of a clean, focused context -- no degradation, no competing priorities, no forgotten constraints.

There is a second benefit that is equally important: **specialization**. Each agent operates under a specific behavioral protocol tailored to its role. The research executor follows atomic execution patterns. The code reviewer follows adversarial inspection patterns. The plan checker validates against six specific dimensions. You simply cannot instruct a single agent to be simultaneously careful, creative, adversarial, thorough, concise, and systematic -- those are genuinely different cognitive modes, and asking one agent to switch between them constantly produces mediocre results in all of them.

The cost is coordination overhead. The orchestrator (the main agent you interact with) has to manage handoffs between these specialized agents, maintain shared memory through the Plan and STATE documents, and ensure that information flows correctly between stages. That is real complexity. But I believe it is the right tradeoff: the alternative is a single agent that degrades in quality precisely when the analysis gets most complex and the stakes are highest.

### Q: Why human-in-the-loop at every gate?

This is the "exo-skeleton" philosophy in action, and I want to be very direct about what it means.

DAAF is not designed to do research for you. It is designed to be a force-multiplying tool for researchers who know what they are doing. The human is the researcher. DAAF is the exo-skeleton that lets you do 5-10x the work you could do alone. But you are still the one walking. You are still the one deciding where to go. And you are still the one responsible for making sure you get there correctly.

This is why DAAF has mandatory Phase Status Updates (PSUs) at every major phase boundary -- points where the system stops, presents you with everything it has done and found, and explicitly waits for your confirmation before proceeding. It is why there are 12 formal gates (G1-G12) that cannot be bypassed. It is why the Plan document requires your review before any data is fetched. It is why the system escalates to you immediately when it hits a STOP condition rather than trying to solve the problem autonomously.

I designed it this way because I firmly believe that the moment you remove the human from the loop in research, you are no longer doing research -- you are doing automation. And automation of research is, in my view, one of the most dangerous applications of AI currently being pursued. Not because the technology is not impressive, but because research requires judgment that LLMs simply do not have: judgment about what questions are worth asking, about whether a methodology is appropriate for a specific context, about what findings actually mean for policy and practice, about what limitations are serious enough to qualify conclusions.

Every gate in DAAF exists because there is a decision at that point that should not be delegated to an AI. Should we proceed with this data source given its limitations? Is this cleaning approach appropriate? Does this transformation make sense given what we know about the data generating process? Are these results plausible? Do these visualizations accurately represent what we found? These are not technical questions -- they are judgment questions, and they deserve a human answer.

Could DAAF run faster without these gates? Yes, dramatically. Could it produce "results" without any human intervention at all? Technically, yes. Would those results be trustworthy? Absolutely not. I would rather have a system that takes an hour with human oversight and produces one reliable analysis than a system that takes five minutes autonomously and produces ten analyses that might be complete nonsense.

### Q: Why file-first execution instead of interactive notebooks?

Every piece of code DAAF produces is first written to a file, then executed from that file, with the execution output captured and appended back to the file. This is deliberate, and it serves two purposes that I consider non-negotiable for research: **reproducibility** and **auditability**.

When an LLM executes code interactively (in a REPL or inline code block), the code exists only ephemerally. If something goes wrong, you cannot easily inspect what was run. If you want to reproduce the analysis, you have to hope the LLM can regenerate the same code -- which, given the stochastic nature of these models, it often cannot. If you want to audit the analysis months later, you have nothing to audit.

File-first execution means that every single operation the AI performs on your data is recorded as an actual Python script file that you can read, inspect, re-run independently, share with colleagues, and version-control. The execution logs embedded in each script show you exactly what happened when it ran -- row counts, validation results, warnings, everything. Nothing is ephemeral. Nothing is hidden. The complete history of every analytical decision is preserved in the filesystem.

This is also why DAAF's marimo notebook is an *assembler*, not a *creator*. The notebook compiles the final successful scripts into an interactive walkthrough -- it literally copies the script contents into notebook cells. It does not generate new code. It does not create new analyses. It does not build dashboards or widgets. The scripts are the primary artifacts; the notebook is a presentation layer. This distinction matters because it means you can always trace any result in the notebook back to the exact script that produced it, review the script's embedded execution log, and re-run it independently.

I know this is more rigid than the freeform notebook-first workflow that many data scientists prefer. But I believe that rigidity is exactly what is needed when the code is being written by an AI. You need to be able to see everything. You need to be able to re-run everything. You need to be able to hand the whole thing to a colleague and say: "Here is exactly what was done, in what order, with what results." File-first execution makes that possible. Interactive notebooks do not.

### Q: Why is this a proof-of-concept and not production software?

No. This is a proof-of-concept demonstrating AI-assisted research patterns. All outputs require human review. Don't be lazy, don't trust it without verifying. DO NOT give Claude access to any proprietary or private data. If you want to use this for your actual important work, you need to work with your IT to ensure you've got all the necessary agreements and file protections in place before trying to use this system with your data. Do not mess around, do not take risks -- do your homework here.

I want to expand on that, because the distinction between "proof-of-concept" and "production software" is genuinely important and I do not want anyone to gloss over it.

DAAF demonstrates that a carefully designed multi-agent system with extensive validation, human oversight, and full auditability *can* produce research outputs that are worth a skilled researcher's review time. That is genuinely novel, and I believe it is a meaningful contribution. But "worth reviewing" is a very different standard from "ready to deploy at scale in a production research environment."

Production readiness would require, at minimum: comprehensive automated testing of the framework itself (not just the analyses it produces), security hardening far beyond what Docker containerization provides, formal verification of the safety hooks and permission boundaries, performance optimization to reduce API costs, proper error handling for edge cases I have not yet encountered, multi-user support, and extensive real-world testing across diverse research contexts and data domains. None of that exists yet. This is version 0.x of an ambitious idea.

There is also a deeper question here that I do not think anyone has satisfactorily answered yet: **Should AI-generated analysis ever run without human review, even in a production system?** I am genuinely unsure. The validation layers in DAAF catch a lot, but they cannot catch everything -- particularly errors of interpretation, inappropriate methodology selection, or subtle data quality issues that require domain expertise to identify. Until I am convinced that automated validation can substitute for expert human judgment (and I am a long way from being convinced), I will continue to describe this as a tool that *assists* researchers rather than one that *replaces* the review process.

### Q: Why so many validation layers? Isn't this overkill?

I understand why it looks like overkill. DAAF has primary validation checkpoints (CP1-CP4) embedded in the code itself, secondary QA reviews (QA1-QA4b) conducted by a separate adversarial code-reviewer agent after every single script, automated plan validation before execution begins, and a final goal-backward verification at the end. That is a LOT of checking.

Here is why every layer exists: **defense-in-depth is the ONLY responsible approach when you cannot fully trust the code generator.**

Each validation layer catches a different category of error, and no single layer is sufficient on its own:

- **Primary checkpoints (CP1-CP4)** catch operational failures -- the data is empty, the types are wrong, too many rows disappeared, required columns are missing. These are the obvious, catastrophic errors. They are necessary but nowhere near sufficient.

- **Secondary QA (QA1-QA4b)** catches logical errors -- the join used the wrong key, the filter logic is inverted, the aggregation groups by the wrong variable, the statistical test violates its own assumptions. These are the errors that produce plausible-looking but wrong results. A separate adversarial reviewer catches things the executor missed because the reviewer is specifically instructed to be skeptical and to reason about *why* the code is correct, not just confirm that it runs.

- **Plan validation** catches design errors before any data is touched -- the methodology is inappropriate for the data structure, the scope is underspecified, the transformation sequence has missing dependencies, the observable truths are not actually testable with the available data. Catching these errors early prevents expensive rework later.

- **Final verification** catches coherence errors across the entire pipeline -- the report claims something the data does not support, a key finding was introduced somewhere but cannot be traced back to an actual analysis, the methodology described in the report does not match the methodology actually implemented in the code.

Could you build a lighter-weight system? Sure. Would it catch fewer errors? Absolutely. And when you are working with AI-generated code that can be confidently wrong in ways that look completely reasonable, those uncaught errors will eventually make it into a report, a publication, or a policy recommendation. I would rather have a system that is criticized for being too careful than one that lets bad analysis slip through because the validation was not thorough enough.

The analogy I keep coming back to is aerospace engineering. Nobody looks at the redundant safety systems in an aircraft and says "isn't this overkill?" They understand that when the consequences of failure are serious, redundancy is not waste -- it is responsibility. The consequences of publishing flawed research are serious. The validation layers are not overkill. They are the minimum I am comfortable with.

### Q: Why does the Plan document exist? Can't the AI just start analyzing?

The Plan document exists because the single most expensive mistake in AI-assisted research is not a coding bug -- it is scope drift and methodology drift, and they are both nearly invisible while they are happening.

Without a Plan, here is what actually happens: You ask the AI to analyze poverty rates in schools. It starts fetching data. Along the way, it decides that it also needs enrollment data. Then it decides that free lunch eligibility would be a better poverty measure than the one you had in mind. Then it decides to include five years of data instead of three because "more data is better." Then it joins on a key that introduces duplicate records. Then it runs a regression when you wanted descriptive statistics. Each of these decisions might be individually defensible, but collectively they mean you get back an analysis that does not answer your original question, uses a methodology you did not approve, and covers a scope you did not request. And because it all happened inside a single fast-moving execution, you have no idea where or why any of these decisions were made.

The Plan prevents this by forcing all of these decisions to be made explicitly, documented with rationale, and reviewed by you *before* any data is fetched or any code is written. It specifies exactly which data sources will be used, exactly which variables, exactly which years, exactly which transformations in exactly which order, exactly which analyses, and exactly what the expected outputs are. It identifies risks and their mitigations. It defines "Observable Truths" -- specific, testable statements that the analysis should be able to confirm or deny. It lays out a wave-based task sequence so that every agent knows exactly what it is supposed to do and what it depends on.

The Plan also serves as persistent shared memory across a workflow that can span hours and multiple sessions. When the code reviewer needs to check whether a transformation is correct, it checks against the Plan. When the report writer needs to describe the methodology, it reads the Plan. When you come back to the analysis weeks later and need to understand what was done, the Plan tells you. It is the single source of truth for the entire project.

Is creating the Plan an extra step that costs time? Yes. Does it sometimes feel like overhead when you just want to see some results? I am sure it does. But I have watched enough AI-assisted analyses go sideways to know that the time spent planning is recovered many times over in reduced rework, clearer communication, and results you can actually trust. The Plan is not bureaucracy -- it is insurance against the AI doing something expensive and wrong before you had a chance to notice.

---

## AI in Research: Broader Questions

### Q: Can AI meaningfully assist with complex research tasks?

This project explores a critical question: **Can AI meaningfully assist with complex research tasks while maintaining the rigor that social science demands?**

My answer, after months of intensive development and testing: Yes, but only with extensive guardrails, modular quality assurance, and human oversight at every critical juncture. DAAF demonstrates what this looks like in practice -- multi-agent decomposition, iterative validation, human gates, and full auditability. But I want to be much more specific about where the "yes" is strong and where it starts to wobble, because I think the research community needs honest assessments here, not hype.

**Where AI adds genuine, substantial value:**

- **Data wrangling.** This is where the acceleration is most dramatic and most reliable. The tedious, time-consuming work of fetching data from APIs, parsing documentation, cleaning coded values, handling missing data, reshaping datasets, and executing joins -- this is work that a skilled researcher knows *how* to do but that consumes enormous amounts of time. An LLM can draft these operations quickly, and the validation layers can catch the inevitable errors. For my own work, this is where I see the most honest 5-10x speedup.

- **Systematic documentation.** LLMs are genuinely good at generating structured documentation from code and data: describing what a script does, cataloging variable definitions, writing methodology sections based on actual implemented code, creating audit trails. The documentation is not always perfect, but it is a vastly better starting point than a blank page.

- **Systematic validation.** This one is counterintuitive, because I just spent several questions explaining why you cannot trust AI-generated code. But an AI reviewing *someone else's* code (even another AI's code) under explicit adversarial instructions turns out to be genuinely useful. The code reviewer agent catches real errors -- wrong join keys, inverted filter logic, violated assumptions -- because it is specifically tasked with being skeptical and is given a fresh context to work in.

- **Exploring unfamiliar data sources.** When you need to understand a new dataset -- what variables exist, how they are coded, what the suppression rules are, what the documented limitations are -- an AI can synthesize that documentation much faster than manual reading. It is not a substitute for actually reading the codebook yourself, but it is a powerful accelerator for initial orientation.

**Where AI struggles and should not be trusted without heavy human oversight:**

- **Novel methodology.** If your research requires a methodological approach that the AI has not seen extensively in its training data, it will either default to something more common (potentially inappropriate) or attempt something that sounds right but is subtly wrong. DAAF mitigates this through the Plan review stage, but the mitigation is *you* -- the human expert who knows whether the proposed methodology actually makes sense.

- **Causal inference and research design.** LLMs can execute a difference-in-differences analysis or an instrumental variables regression if you tell them to. But they cannot reason about whether those designs are actually valid for your specific context. They cannot think through threats to identification. They cannot evaluate whether an instrument satisfies the exclusion restriction. These are judgment calls that require deep understanding of both the methodology and the substantive domain.

- **Interpretation and implications.** The AI can tell you that a coefficient is statistically significant and its magnitude. It cannot tell you whether that magnitude is substantively meaningful, whether the finding is consistent with existing theory, what the policy implications are, or what the limitations of the interpretation are given the specific data generating process. This is where the researcher's expertise is irreplaceable.

- **Knowing what questions to ask.** Research starts with questions, and good questions come from deep engagement with a field, with theory, with prior findings, with the messy reality of the phenomenon being studied. An AI can help you *answer* a well-specified question. It cannot tell you which questions are worth asking in the first place.

The honest summary: AI assistance is transformative for the mechanical parts of research and genuinely useful for the systematic parts. It is unreliable for the judgment parts and absent for the creative parts. A framework like DAAF can maximize the value of the former while creating guardrails for the latter. But the researcher remains indispensable -- not as a formality, but as the actual source of intellectual value in the process.

### Q: What does the hallucination problem mean for data analysis specifically?

The hallucination problem in data analysis is both more specific and more dangerous than the general hallucination problem most people are familiar with. When an LLM generates a plausible-sounding but incorrect paragraph in an essay, a careful reader can often spot the issue. When an LLM generates a plausible-looking but incorrect data transformation, the error can be essentially invisible unless you have systematic validation in place.

Here is how hallucination manifests specifically in data work, and how DAAF's layers are designed to address each one:

**Fabricated statistics.** An LLM asked to summarize data can simply make up numbers -- reporting a mean of 42.7 when the actual mean is 38.2, or claiming 15% missingness when the real rate is 35%. This is not malice; it is the model generating plausible-sounding completions rather than computing actual values. DAAF addresses this through file-first execution: every statistic must be computed by actual Python code running on actual data, with the output captured and embedded in the script. The AI cannot just "say" what a number is; it has to compute it and show its work.

**Plausible-but-wrong joins.** This is one of the most insidious errors. The AI decides to join two datasets on a key that *looks* right but introduces duplicates, drops records, or creates nonsensical combinations. For example, joining school-level data to district-level data on year alone (instead of year and district ID), silently duplicating every school record for every district. The result looks like a normal dataset with more rows. DAAF addresses this through mandatory CP3 validation (checking row counts, join cardinality, and null rates before and after every transformation) and through the adversarial code reviewer (which specifically checks join logic against the Plan).

**Confident interpretation of nonexistent patterns.** Given a noisy dataset, an LLM can identify "trends" and "patterns" that are artifacts of random variation, coding errors, or its own misunderstanding of what the variables represent. It will present these interpretations with the same confidence as genuine findings. DAAF addresses this through the separation of analysis from interpretation (the AI runs the statistics; the human interprets them) and through the data-verifier agent's goal-backward verification (which traces every key finding back through the pipeline to confirm it is actually supported by the data).

**Silent methodology errors.** The AI applies a statistical test that violates its assumptions, uses a formula incorrectly, or implements a standard method with a subtle error (e.g., computing a weighted mean with the wrong weights). These errors produce output that looks like valid statistical results. DAAF addresses this through the QA4a checkpoint, which specifically validates statistical methodology -- checking assumptions, verifying formulas, and confirming that the method is appropriate for the data structure.

**Wrong coded value handling.** Education data (and most administrative data) is full of coded values: -1 means "missing," -2 means "not applicable," -9 means "suppressed." If the AI treats these as actual numeric values -- which it will happily do if not explicitly instructed otherwise -- your averages, sums, and distributions will be quietly corrupted. DAAF addresses this through mandatory source deep-dives (Stage 3) that document all coded values before any data is touched, and through CP2 validation that confirms coded values were handled correctly during cleaning.

Here is the uncomfortable truth: **no automated system can guarantee that all hallucination-related errors are caught.** DAAF's layers are designed to catch the most common and most dangerous categories, but novel failure modes are always possible. This is why human review of all outputs is not a nice-to-have -- it is a fundamental requirement. The validation layers are there to make your review more efficient by catching the obvious errors automatically, so you can focus your expert attention on the subtle ones.

### Q: What's the appropriate level of trust for AI-generated analysis?

I think about this as a three-level framework, and I want to be honest that I arrived at it through painful experience rather than elegant theorizing.

**Level 1: Trust the process.** If the process is well-designed -- if there are validation checkpoints, adversarial QA, human gates, full auditability, and documented methodology -- then you can trust that the *process* is sound. This is what DAAF provides. You can trust that the framework will catch a large class of errors, that it will stop when it encounters problems, and that it will produce artifacts you can inspect. Trusting the process does not mean trusting the outputs. It means trusting that the outputs were produced in a way that makes meaningful review possible.

**Level 2: Verify the outputs.** Every output of every stage should be verified by a human with domain expertise. Not spot-checked -- verified. Look at the data. Check the row counts. Examine the distributions. Read the code. Confirm the statistics. This is not optional, and it is not something DAAF can do for you. The framework's validation layers reduce the burden by catching mechanical errors, but they cannot substitute for a researcher looking at the results and asking: "Does this make sense given what I know about this domain?"

**Level 3: Question the interpretation.** Even when the data is correct and the analysis is properly executed, the interpretation of results requires human judgment. What do these findings mean? Are there alternative explanations? What are the limitations? What would we need to see to be more confident? How should these results inform practice or policy? These questions are not answerable by any AI system I have seen, and I am skeptical they will be answerable any time soon. This is where the researcher's training, experience, and substantive expertise are most irreplaceable.

The phrase "trust but verify" gets thrown around a lot, but I think it gets the emphasis wrong. A better framing: **Verify, then conditionally trust -- and always question the interpretation.** The trust is earned through verification, not assumed. And even verified results require expert interpretation.

I will add one more thing that I think is important: the appropriate level of trust should be *lower* for AI-generated analysis than for human-generated analysis, even when the AI analysis has been validated. Not because AI is inherently worse at coding (for routine operations it may actually be more reliable), but because the failure modes are different and less familiar. We have decades of experience understanding how human analysts make errors. We have much less experience understanding how LLMs fail in data contexts. Until that experience base grows, extra skepticism is warranted.

### Q: How does DAAF's approach relate to reproducibility and open science?

This is a question I care about deeply, and I think the connection is more organic than it might first appear.

The reproducibility crisis in social science is, at its core, a documentation and transparency problem. Studies fail to reproduce because critical methodological details were not recorded, because data processing steps were not documented, because analytical choices were made implicitly and never written down, because code was written interactively and not preserved. Researchers are not trying to be opaque -- they are just busy, and documentation is the first thing that gets cut when deadlines loom.

DAAF's design principles -- file-first execution, embedded execution logs, mandatory Plan documents, inline audit trails in every script, version-controlled everything, explicit documentation of every methodological decision -- are not primarily *about* reproducibility. They exist because they are necessary for responsible AI-assisted research. But they produce, almost as a side effect, a level of documentation and transparency that far exceeds what most manually-conducted analyses achieve.

Consider what a completed DAAF project produces:

- A Plan document that records every methodological decision with its rationale
- Numbered, versioned Python scripts for every data operation from fetch to visualization
- Embedded execution logs in every script showing exactly what happened when it ran
- Validation checkpoint results at every stage
- Adversarial QA reports for every script
- A compiled notebook that walks through the entire pipeline interactively
- A summary report with explicit methodology, limitations, and caveats
- A LEARNINGS document capturing data quality issues and interpretation concerns

All of that is automatically generated as part of the normal workflow. A colleague who wanted to reproduce the analysis could follow the scripts in order and get the same results (assuming the source data has not changed). A reviewer who wanted to understand a methodological choice could trace it through the Plan. An auditor who wanted to verify a specific claim could trace it backward from the report through the analysis, transformation, and raw data.

This is what I mean when I say DAAF naturally aligns with open science goals. It is not that I sat down and designed a reproducibility tool. It is that the constraints of responsible AI-assisted research -- transparency, auditability, documentation, version control -- happen to be the same constraints that open science advocates have been arguing for all along. The AI forces the issue because without these constraints, you genuinely cannot trust what it produces. And once you have them in place for the AI's benefit, they serve the research community's broader interests as well.

I do not want to oversell this. DAAF does not solve the reproducibility crisis. It does not address publication bias, p-hacking, or the perverse incentive structures in academia. But it does demonstrate that AI-assisted research, done carefully, can produce artifacts that meet a higher standard of documentation and transparency than most traditional workflows. That is worth something.

### Q: What does AI assistance replace in a research workflow, and what doesn't it replace?

I want to answer this as honestly as I can, because I think the research community is getting a lot of misleading signals from both the AI hype machine ("AI will do all the research!") and from the AI skeptics ("AI cannot contribute anything meaningful to research!"). Neither is right.

**What DAAF genuinely replaces or dramatically accelerates:**

- **Data wrangling and pipeline construction.** The mechanical work of writing fetch scripts, cleaning code, join operations, reshaping, and aggregation. This is typically 60-80% of the labor in a quantitative research project, and it is the part that benefits most from AI assistance. Not because the AI does it perfectly -- it does not -- but because it does it fast enough that even with extensive validation and revision, the net time savings are enormous.

- **Systematic validation.** Ironically, AI is quite good at checking AI's work, when instructed to do so adversarially with a fresh context. The code reviewer agent catches real bugs. The plan checker catches real design issues. This is validation that most researchers do not do thoroughly enough (if at all) because it is tedious and time-consuming. DAAF makes it systematic and automatic.

- **Documentation generation.** Writing methodology sections, documenting data processing decisions, creating audit trails, cataloging variable definitions, describing what scripts do -- all of this is work that researchers typically under-invest in because it does not produce new findings. The AI generates it as a natural byproduct of the workflow.

- **Initial data exploration.** When you need to orient yourself to a new data source -- what variables exist, what they mean, how they are coded, what the known limitations are -- the AI can synthesize that information much faster than manual documentation review.

**What DAAF does not replace and should never be expected to replace:**

- **Research question formulation.** The spark of genuine inquiry -- "I wonder if X is related to Y, and if so, what mechanism might explain it" -- comes from deep engagement with a field, with theory, with prior research, with the lived reality of the phenomenon being studied. No amount of AI assistance can substitute for a researcher who has spent years thinking about these questions.

- **Methodological judgment.** Choosing the right analytical approach for a specific research question given specific data constraints is a judgment call that requires understanding of both the methods and the substantive context. The AI can implement any method you choose. It cannot reliably choose for you.

- **Interpretation and meaning-making.** A regression coefficient is a number. What that number *means* -- for theory, for policy, for practice, for the specific communities affected -- is a deeply human question that requires domain expertise, ethical reasoning, and contextual understanding.

- **Quality judgment.** Knowing whether a result is "good enough" to report, whether a limitation is serious enough to qualify a conclusion, whether an unexpected finding is exciting or suspicious -- these are expert judgments that DAAF's validation layers cannot make. They can tell you whether the code ran correctly. They cannot tell you whether the analysis was worth running.

- **Ethical reasoning.** Research involves ethical considerations at every stage: Is it appropriate to study this population this way? Could these findings be misused? Are we centering the right voices? Are we being responsible with sensitive data? These questions require moral reasoning that AI systems are not equipped to provide.

The summary I keep coming back to: DAAF replaces the *labor* of research but not the *expertise*. It is a power tool, not a replacement operator. A power tool in the hands of a skilled craftsperson produces better work faster. A power tool in the hands of someone who does not understand the craft produces sawdust and injuries. This is why DAAF is designed as an exo-skeleton -- it assumes the researcher brings the expertise, and it provides the force multiplication.

---

## Looking Forward

### Q: Where could this approach go?

The honest answer is that I am not entirely sure, and I find that both exciting and terrifying.

The most straightforward evolution paths are:

- **More data domains.** DAAF's current demonstration uses U.S. education data, but the architecture is domain-agnostic. The agents, validation protocols, workflow stages, and orchestration logic do not care whether you are analyzing school enrollment, health outcomes, economic indicators, or climate data. Only the Skills are domain-specific. Community-contributed data source Skills could rapidly expand DAAF's coverage to new fields. I have built the `data-ingest` agent and `skill-authoring` tools specifically to make this extension as accessible as possible.

- **Community contribution and collective improvement.** Every DAAF project run generates a LEARNINGS.md file that captures data issues, interpretation concerns, and workflow improvements discovered along the way. These are designed to be immediately actionable -- specific suggestions for updating Skills, fixing documentation, adding validation checks. If users share these back (even as anonymous issue reports), the framework gets better with every project run across every user. This is the kind of distributed, iterative improvement that open-source communities do best.

- **Better models reducing hallucination risk.** As frontier LLMs improve, some of the validation layers in DAAF may become less critical. If future models are significantly less likely to fabricate statistics or write incorrect joins, the framework could potentially relax some checkpoints without sacrificing rigor. I would approach this cautiously and empirically -- removing validation layers only when sustained testing demonstrates they are no longer catching meaningful errors.

- **Integration with existing research tools and workflows.** DAAF currently operates as a standalone framework within Claude Code. Future development could integrate more tightly with existing research infrastructure: version control platforms, data repositories, collaboration tools, publication pipelines. The file-first execution and documented methodology already produce artifacts that fit naturally into these ecosystems.

- **Coding agent and language agnosticism.** DAAF is currently built on Claude Code and primarily uses Python, but the vast majority of the framework -- Skills, Agents, workflow protocols, validation logic -- is expressed in Markdown and could be ported to other agentic coding tools (Gemini CLI, Codex, OpenCode) and other analytic languages (R, Stata, Julia). I would love to see community members tackle these ports.

What I am less sure about -- and what I think deserves genuine, critical conversation -- is how this approach scales and what it means as models become more capable. If next year's models are 10x better at data analysis, does that make frameworks like DAAF more valuable (because they can do more) or less necessary (because the models need fewer guardrails)? I genuinely do not know. I suspect the answer is "both, in different ways." But I believe the core principle -- human oversight of AI-assisted research -- will remain essential regardless of model capability.

### Q: What would need to change for production use?

I want to be very transparent about the gap between where DAAF is today and where it would need to be for genuine production deployment in a research organization.

**Security hardening.** DAAF runs inside a Docker container with capabilities dropped and a non-root user, which provides basic isolation. Production use would require formal security audits, penetration testing, network isolation appropriate for the sensitivity of the data being analyzed, and potentially air-gapped deployments for classified or highly sensitive work. The current safety hooks (bash-safety.sh, output-scanner.sh) are good-faith engineering, not formally verified security boundaries.

**Testing infrastructure.** DAAF currently has no automated test suite. There are no unit tests for the validation checkpoints, no integration tests for the multi-agent workflow, no regression tests to confirm that framework changes do not break existing functionality. This is the most significant engineering gap, and it is the one I am most uncomfortable with. A production framework needs comprehensive testing, and building that test suite is a substantial effort.

**Performance optimization.** DAAF is, to be blunt, extremely resource-hungry. It makes many subagent calls, each consuming significant API tokens. The iterative validation approach -- while essential for quality -- multiplies the cost compared to a less careful system. Production use would benefit from intelligent caching, more efficient context management, and potentially model routing (using lighter models for routine tasks and reserving frontier models for complex ones).

**User management and access control.** The current framework assumes a single researcher working in a single Docker container. Production deployment for a research team would need multi-user support, role-based access control, shared project spaces, and probably a proper web interface rather than a terminal-based workflow.

**The fundamental open question.** And then there is the question I raised earlier that I do not think has been satisfactorily answered: Should AI-generated analysis ever be trusted without human review, even in a production system with extensive automated validation? My current answer is no. The validation layers catch a lot, but they cannot catch errors of judgment, interpretation, or contextual appropriateness. If production use means "analysts review DAAF output before using it," that is a workflow I am comfortable advocating for. If production use means "DAAF runs analyses automatically and results feed into decision-making pipelines without human review," I am not there yet, and I am not sure I will be.

I would rather be honest about these gaps than pretend they do not exist. DAAF is a proof-of-concept that demonstrates patterns and principles. Turning those patterns into production infrastructure is a genuinely different challenge that will require engineering resources, security expertise, and sustained real-world testing that are beyond what one researcher can provide alone.

### Q: Why LGPL-3.0 for an AI research tool?

DAAF is licensed under the **GNU Lesser General Public License v3.0** (LGPL-3.0-or-later), and the choice is deliberate. The core argument is simple: **transparency is non-negotiable for tools that assist with research.**

If a tool is helping produce research findings that will inform policy, shape public understanding, or contribute to the scientific record, then the research community must be able to inspect, audit, and understand exactly how that tool works. Proprietary black-box research tools are problematic enough when they are traditional statistical software. When they involve AI systems that can hallucinate, drift, and produce confident-sounding errors, opacity becomes genuinely dangerous.

The LGPL specifically (rather than the stricter GPL) reflects a practical reality: many researchers work with data that cannot be made public -- government agencies, healthcare organizations, private-sector analysts working with proprietary datasets. The LGPL ensures that the core framework remains open and auditable while allowing users to build private extensions (custom Skills for proprietary data sources, specialized agents for internal workflows) without being forced to open-source their data configurations or analysis outputs. The core stays transparent; the extensions stay flexible.

This also means that if someone improves the validation logic, fixes a bug in the orchestration workflow, or builds a better safety hook, those improvements flow back to the entire community. No one organization can take the framework, make it better, and lock those improvements away. The rising tide lifts all boats.

I believe this matters beyond DAAF specifically. As AI-assisted research tools proliferate, the research community will need to make a collective decision about whether these tools should be transparent or opaque. I firmly believe the answer must be transparency, especially during this early period when we are still learning how these tools fail. Open-source is not just a licensing preference -- it is an ethical position about the kind of research infrastructure our field should build on.

### Q: How does DAAF relate to other AI coding tools?

DAAF is **not** a general-purpose coding assistant. This distinction matters, and I want to be specific about it because the landscape of AI coding tools is genuinely confusing right now.

Tools like GitHub Copilot, Cursor, and even Claude Code itself (without DAAF) are general-purpose AI coding assistants. They help you write code faster across any domain -- web development, data science, systems programming, anything. They are interactive, flexible, and designed to be useful for the broadest possible range of tasks. They are genuinely excellent at what they do.

DAAF is a **domain-specific research framework** built on top of Claude Code. It does not make Claude Code better at general coding tasks. It constrains Claude Code's behavior in very specific ways that make it more suitable for one particular use case: producing rigorous, reproducible, auditable data analysis. Those constraints -- mandatory validation, human gates, Plan documents, file-first execution, adversarial QA -- would be annoying and counterproductive for general software development. They are essential for research.

The relationship is analogous to the difference between a general-purpose vehicle and a specialized research vessel. A car is great for getting around. A research vessel is specifically designed for oceanographic research -- it has stabilization systems, specialized sampling equipment, dedicated lab space, and safety protocols that a car does not need. You would not want to drive a research vessel to the grocery store. You would not want to do deep-sea research in a sedan.

DAAF uses Claude Code as its engine -- the underlying AI capability that can read files, write code, and execute commands. Everything else -- the multi-agent architecture, the validation framework, the workflow stages, the Skills system, the Plan management protocol -- is DAAF's contribution. You could strip all of that away and have plain Claude Code, which would be faster and more flexible but would lack all of the guardrails that make it suitable for research.

Can DAAF and general-purpose AI coding tools coexist? Absolutely. I use Claude Code without DAAF for general development work all the time. When I need to do rigorous data analysis, I use DAAF. Different tools for different jobs.

### Q: What about the environmental and energy costs of this kind of intensive AI use?

This is a question I think about and do not have a comfortable answer to. I want to be honest about that rather than hand-wave it away.

DAAF is resource-intensive. A single full-pipeline analysis involves dozens of subagent calls, each consuming significant compute on Anthropic's servers. The iterative validation approach -- executing a script, then running an adversarial review, then potentially revising and reviewing again -- multiplies the compute cost compared to a single-pass approach. The multi-agent architecture means multiple fresh context windows, each requiring inference. And I am recommending that researchers run multiple projects in parallel. The aggregate energy and compute footprint is substantial.

I do not have precise numbers for DAAF's carbon footprint per analysis. The major AI providers publish some information about their data center energy sources and efficiency, but translating that into per-inference environmental cost for a specific workflow is difficult. What I can say with confidence is that it is not zero, it is not trivial, and it matters.

Here is how I think about the tradeoff, honestly:

The environmental cost is real and should be weighed against the value produced. If DAAF enables a researcher to produce one high-quality, well-validated analysis that informs policy affecting millions of students, the energy cost may be justified. If DAAF is used to churn out dozens of low-value analyses that nobody reads, the cost is harder to defend. The tool does not make that judgment -- the researcher does.

There are also efficiency gains to consider. A researcher spending two weeks doing manual data wrangling also has an environmental footprint (office energy, computing resources, transportation). If DAAF compresses that to two hours of cloud compute, the net impact may be neutral or even positive. But I have not seen rigorous lifecycle analyses comparing these, and I am wary of arguments that amount to "the AI's footprint replaces the human's footprint" without actual data.

What I can commit to is that DAAF should be as efficient as possible for the quality level it produces. The framework is, as I have acknowledged, likely more resource-hungry than it strictly needs to be. Optimizing the number of subagent calls, reducing unnecessary validation passes, implementing intelligent caching, and potentially routing simpler tasks to lighter models are all legitimate paths to reducing the environmental cost without sacrificing rigor. I welcome contributions on this front specifically.

More broadly, I think the research community needs to develop norms and standards around the environmental costs of AI-assisted research, just as we have developed norms around other resource-intensive research methods (large-scale surveys, randomized controlled trials, longitudinal data collection). The cost is real. It should be part of the calculus. But it should be weighed against the full picture, not used as a blanket argument against AI assistance.

### Q: What does this mean for the next generation of researchers?

This is the question that keeps me up at night, and it is the reason I started my career as a high school teacher before becoming a researcher. I care deeply about what we are preparing the next generation to do and to be.

Here is what I worry about: If AI can do the mechanical parts of research -- the data wrangling, the code writing, the systematic validation -- then will the next generation of researchers ever develop the deep, intuitive understanding of data that comes from wrestling with it manually? Will they know what a messy dataset looks like? Will they understand why a join produces unexpected results? Will they have the hard-won intuition that tells them "this number does not look right" before they can articulate why?

These skills are not just nice-to-have. They are what makes a researcher capable of supervising AI-assisted work effectively. If you have never manually cleaned a dataset, you will not know what to look for when reviewing AI-generated cleaning code. If you have never debugged a failed join, you will not recognize the signs of a join that "succeeded" incorrectly. The exo-skeleton metaphor assumes the human inside it has strong muscles. What happens when the next generation grows up never developing those muscles because the exo-skeleton was always there?

I do not have a tidy answer to this. But I have some convictions:

**First, we need to teach both.** The next generation of researchers needs to learn traditional data skills -- manual data wrangling, code writing, debugging, working with messy data by hand -- AND they need to learn how to supervise, validate, and critically evaluate AI-assisted work. These are complementary skills, not substitutes. A curriculum that replaces data skills courses with "let the AI do it" courses would be catastrophically shortsighted.

**Second, critical evaluation becomes THE core skill.** If AI handles the production of analysis, then the most important thing we can teach is how to evaluate whether that analysis is any good. How to read code critically. How to spot implausible results. How to trace a finding back to its source. How to ask: "Is this actually answering the question I asked, or is it answering a different question that the AI substituted?" This is a learnable skill, and it is arguably more important in an AI-augmented world than in a manual one.

**Third, domain expertise becomes more valuable, not less.** When the mechanical parts of research are accelerated, the bottleneck shifts to the parts that require genuine expertise: formulating good questions, choosing appropriate methods, interpreting results in context, understanding the limitations of the data and the analysis. The researchers who will thrive are those with deep substantive knowledge -- the ones who know enough about their domain to ask hard questions and recognize when answers do not make sense.

**Fourth, we need to be honest with students about what is happening.** The pace of AI development is genuinely frightening. I use the word "scary" deliberately and without embarrassment. The landscape that today's graduate students will practice in is dramatically different from the one they are being trained for. They deserve honest conversations about what is changing, what is not, and what they need to be prepared for. This is part of why I have paired DAAF with educational materials and the DAAF Field Guide Substack -- because the tooling is only useful if people understand how to think about it critically.

This is ultimately why I describe DAAF as an educational endeavor as much as a technical one. The framework itself is a proof-of-concept. The deeper contribution -- or at least the deeper aspiration -- is helping my peers and colleagues engage with AI disruption thoughtfully, critically, and with their eyes wide open. I was a high school English teacher before I was a researcher, and some part of me will always believe that the most important thing I can do is help people learn. If DAAF can be useful for that, then it has served its purpose regardless of whether the specific technical implementation survives the next round of model improvements.

---

## Recommended Next Steps

- [**00. README**](../.) — Vision and purpose, project goals, what DAAF does and does not do, core design philosophy, acknowledgments
- [**01. Installation & Quick Start**](01_installation_and_quickstart.md) — Get started! Installation prerequisites, step-by-step 5-minute setup, day-to-day usage, and troubleshooting
- [**07. FAQ: Technical Support**](07_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, authentication errors, and other common errors
- [**Back to main**](../.)
