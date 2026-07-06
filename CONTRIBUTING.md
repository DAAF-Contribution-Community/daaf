# 05. Contributing to DAAF

This guide covers all forms of contribution to DAAF, from filing an issue to modifying core framework components. Whether you've found a bug, want to improve documentation, or want to help the broader community by building new functionality: this is where to start. That being said, there's an important distinction between generally **extending** DAAF for your own purposes (adding new skills, data sources, and agents; see [**04. Extending DAAF**](user_reference/04_extending_daaf.md) for more there) and **contributing** to DAAF itself (sharing back your work, improvements, suggestions, and ideas with the broader community; this guide). If you're still getting oriented and want to understand how DAAF works before contributing, you can ask DAAF directly -- it has a **User Support** mode for exactly that kind of question (see [**02. Understanding and Working with DAAF**](user_reference/02_understanding_daaf.md) for more).

[**Back to main**](https://github.com/DAAF-Contribution-Community/daaf/tree/main)

---

## Table of Contents
- [**Introduction**](#introduction)
- [**Governance**](#governance)
- [**Community Norms**](#community-norms)
- [**Quick Start: Contribution Workflow**](#quick-start-contribution-workflow)
- [**Developer Certificate of Origin**](#developer-certificate-of-origin)
- [**Ways to Contribute**](#ways-to-contribute)
- [**What Makes a Good Contribution**](#what-makes-a-good-contribution)
- [**Filing Effective Issues**](#filing-effective-issues)
- [**Testing Your Changes**](#testing-your-changes)
- [**Using Session Logs for Debugging and Issue Reports**](#using-session-logs-for-debugging-and-issue-reports)
- [**License**](#license)
- [**Recommended Next Steps**](#recommended-next-steps)

---

## Introduction

Thank you for your interest in contributing to DAAF. Whether you're reporting a bug, suggesting an improvement, authoring a new data source skill, or proposing changes to core framework logic -- your contribution is valued and appreciated. Before participating, please review the project's [Contributor Covenant Code of Conduct v2.0](CODE_OF_CONDUCT.md). By participating, you agree to uphold its standards. Instances of unacceptable behavior may be reported to the project maintainer, Brian Heseung Kim ([@brhkim](https://github.com/brhkim)). All reports will be reviewed and investigated promptly and confidentially.

**A note from the maintainer:**
As an important heads-up: I am a researcher by training, not a software developer, and this is my first significant open-source project. I am still learning the norms, tooling, and rhythms of open-source collaboration. If something about the contribution process feels rough around the edges, please bear with me -- and please do not hesitate to suggest improvements. I welcome patience, candor, and constructive feedback as this project and its community grow together. Thank you!
-- Brian Heseung Kim ([@brhkim](https://github.com/brhkim))

---

## Governance

DAAF follows a **Benevolent Dictator (BD)** governance model.

**Project lead:** Brian Heseung Kim ([@brhkim](https://github.com/brhkim)) serves as the project lead with final decision-making authority on design direction, feature acceptance, and release timing.

All contributions are welcome and will be reviewed thoughtfully. Disagreements are resolved through discussion, but the project lead retains the final call. This model may evolve as the community grows; any changes will be documented in this section.

**Why this model?** DAAF is a young project with strong, carefully considered opinions about research rigor, transparency, and reproducibility. A single decision-maker ensures coherent design across the framework's many interacting components -- agents, skills, protocols, validation logic, and orchestration workflow. This transparency avoids false expectations: contributors know up front how decisions are made, rather than discovering it after investing significant effort.

---

## Community Norms

DAAF is built by and for researchers. That shapes the kind of community I want this to be -- one where intellectual rigor, honest feedback, and mutual respect are the defaults.

### Tone and Expectations

- **Be direct and honest.** If you think something is wrong, say so clearly. If you think a design decision is misguided, make your case. I would much rather hear a well-reasoned disagreement than polite silence.
- **Be kind while being direct.** Directness and kindness are not in tension. You can say "I think this validation logic is fundamentally broken because X" without being dismissive or hostile about it.
- **Assume good faith.** This project involves deeply opinionated design decisions -- the kind that reasonable people can genuinely disagree on. When you encounter a choice that seems wrong, start by asking why it was made that way before assuming it was made carelessly.
- **Share your expertise generously.** DAAF sits at the intersection of data science, research methodology, software engineering, and AI agent design. Nobody is an expert in all of these. If you know something relevant, please be open about sharing it, even if it feels obvious to you. It probably isn't obvious to everyone, and we can all stand to keep learning across the board!

### How Discussions Happen

- **Issues** are the primary venue for bug reports, feature requests, and focused discussions about specific changes. If you want to propose something, open an issue first before writing code so we can discuss and plan out high-level approaches together.
- **Pull request reviews** are where detailed technical feedback happens. Expect substantive review -- this isn't a rubber-stamp process. I'll explain my reasoning when requesting changes, and I appreciate the same from contributors.
- **Broader discussions** about design direction, philosophy, or large-scale changes should start as GitHub Discussions or issues tagged with `discussion`. These tend to benefit from more voices and more time.

### Response Times

I maintain this project alongside a full-time research career, so response times may not always be immediate. I'll do my best to acknowledge issues and PRs within a few days, but detailed review may take longer. If something is urgent (e.g., a security issue or a data integrity bug), flag it clearly in the issue title so I can prioritize accordingly!

### AI-Generated Contributions

Given what DAAF is, it would be somewhat ironic to ban AI-assisted contributions entirely. That said: if you use an LLM to help draft documentation, generate code, or explore ideas, **you are responsible for the quality and correctness of the result.** Take ownership and be thoughtful about what you're asking others to review and spend time engaging with. Submitting unreviewed AI-generated output as a contribution is just not going to fly here -- the same way submitting unreviewed DAAF output as a research finding is not acceptable. Review and understand everything yourself before you submit, **please**.

---

## Quick Start: Contribution Workflow

*New to Git and GitHub? GitHub's [contribution guide](https://docs.github.com/en/get-started/quickstart/contributing-to-projects) walks through the basics, or you can ask DAAF's User Support mode for help with the workflow.*

The standard contribution workflow has ten steps:

1. **Open an issue** and begin a conversation about what you want to improve/add/suggest (ideally starting here!) 
2. **Fork** the repository on GitHub.
3. **Clone** your fork:
   ```bash
   git clone https://github.com/YOUR-USERNAME/daaf.git
   ```
4. **Create a feature branch** from `main`:
   ```bash
   git checkout -b my-feature main
   ```
5. **Install pre-commit hooks** (already included in the main DAAF Dockerfile setup, but here just in case):
   ```bash
   pip install pre-commit && pre-commit install
   ```
6. **Make your changes**, then commit with a DCO sign-off (see [Developer Certificate of Origin](#developer-certificate-of-origin) below):
   ```bash
   git commit -s -m "feat: add new data source skill for NHGIS"
   ```
7. **Push** to your fork:
   ```bash
   git push origin my-feature
   ```
8. **Open a pull request** against `main` on the upstream repository.
9. **Address review feedback** from the maintainer.
10. **Maintainer merges** (squash and merge).

### Commit Message Format

Use a prefix that describes the nature of the change, followed by a colon and a short description. Claude is really good about following these if you point it to this documentation while you work and commit changes.

| Prefix | Use For | Example |
|--------|---------|---------|
| `feat:` | New features or capabilities | `feat: add campus safety data source skill` |
| `fix:` | Bug fixes | `fix: correct suppression rate calculation in CP2` |
| `docs:` | Documentation changes | `docs: clarify session recovery protocol` |
| `refactor:` | Code restructuring without behavior change | `refactor: simplify plan-checker validation loop` |
| `test:` | Adding or modifying tests | `test: add validation for IPEDS coded values` |
| `chore:` | Maintenance, dependencies, CI/CD | `chore: update pre-commit hook versions` |
| `skill:` | New or modified skill files | `skill: update CCD variable definitions for 2025` |
| `agent:` | New or modified agent protocols | `agent: add retry logic to research-executor` |
| `data:` | Data-related changes (mirrors, schemas) | `data: add 2025 CRDC mirror endpoint` |
| `plan:` | Plan template or planning logic changes | `plan: add risk register section to template` |

---

## Developer Certificate of Origin

All contributions to DAAF must be signed off under the [Developer Certificate of Origin v1.1](https://developercertificate.org/) (DCO). By signing off, you certify that you have the right to submit the contribution under the project's open-source license.

<details>
<summary><strong>Full DCO Text (click to expand)</strong></summary>

```
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.

Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```
</details>

### How to Sign Off

Add the `-s` flag when committing:

```bash
git commit -s -m "feat: description of change"
```

This appends a `Signed-off-by` line to your commit message:

```
feat: description of change

Signed-off-by: Your Name <your.email@example.com>
```

Git uses the name and email from your `user.name` and `user.email` configuration.

**If you forgot to sign off on your most recent commit:**

```bash
git commit --amend -s --no-edit
```

**If you forgot to sign off on multiple commits in your branch:**

Use an interactive rebase to amend each commit. For example, to rebase the last 3 commits:

```bash
git rebase HEAD~3 --exec 'git commit --amend -s --no-edit'
```

Pull requests without DCO sign-off on all commits will be asked to add sign-off before merging.

---

## Ways to Contribute

Contributions come in many forms -- from a two-minute bug report to deep framework work that takes weeks. Here's the full spectrum, with enough detail to help you figure out where to start and what's actually involved.

### Low Barrier (minutes to an hour)

These are the contributions that anyone can make, regardless of technical depth. They're also genuinely some of the most valuable -- the "low effort" label describes the time investment, not the impact.

- **Filing bug reports with session log excerpts.** Something broke? The session logs in `.claude/logs/sessions/` capture exactly what happened. Grab the relevant section, redact any sensitive content, and [open an issue](https://github.com/DAAF-Contribution-Community/daaf/issues). Even a bare "this failed with this error" report is useful -- but a report with log context is *extremely* useful. See [Filing Effective Issues](#filing-effective-issues) below for guidance.

- **Suggesting documentation improvements.** Found a confusing paragraph? A broken link? An explanation that assumes knowledge you don't have? Open an issue pointing to the specific section and describing what's unclear. Better yet, propose replacement text. The documentation is written for researchers who may be new to AI agents, so clarity matters enormously.

- **Reporting data source issues.** If you notice that a skill documents a variable as having values 1-5, but the actual data has values 1-7 -- that's a real finding that prevents silent data errors for every future user. Similarly, if a coded value mapping is wrong, a suppression threshold is outdated, or a caveat is missing, please report it. These reports directly improve the quality of every analysis DAAF runs.

- **Sharing your LEARNINGS.md files.** Every time DAAF completes a Full Pipeline project, it produces a LEARNINGS.md documenting everything it learned about data quirks, process issues, and methodology edge cases. These are written to be immediately actionable -- they often contain specific suggestions for updating skills, improving documentation, or adding new pitfall entries. If you [open an issue](https://github.com/DAAF-Contribution-Community/daaf/issues) with your LEARNINGS.md content, the community can fold those insights back into the framework. This is genuinely one of the highest-impact, lowest-effort things you can do.

- **Sharing your experience and use cases.** Tried DAAF on a research question and have thoughts on how it went? Even informal feedback helps me understand how people are actually using the system versus how I imagined they'd use it. These observations shape priorities for what to improve next.

### Medium Effort (a few hours to a couple days)

These contributions require more engagement but are well within reach for anyone who's used DAAF a few times and has some familiarity with Markdown and the project structure.

- **Improving existing documentation.** This goes beyond "point out what's confusing" to actually rewriting sections, adding examples, restructuring for clarity, or filling gaps. Good documentation contributions require understanding the material well enough to explain it better -- which often means running DAAF yourself and noting where the docs don't match reality. The user-facing documentation (`user_reference/` files and this CONTRIBUTING guide) is a great starting point. If you're comfortable with the internal architecture, the `agent_reference/` files could also use fresh eyes from people who aren't me.

- **Adding new data source skills.** This is probably the single most impactful medium-effort contribution. DAAF ships with skills for 40+ education data sources, but there are entire data domains waiting to be integrated. Use **Data Onboarding mode** to profile a public dataset (the `data-ingest` agent handles the profiling work), review its output carefully, and submit the resulting skill. The full process is documented in [**04. Extending DAAF**](user_reference/04_extending_daaf.md) -- the profiling agent does the heavy lifting, but your domain expertise in reviewing and correcting its output is what makes the skill actually reliable. **Important:** To distinctions above, creating the skill is an *extension*. Submitting it to the shared repository via PR is the *contribution*.

- **Adding methodology or domain expertise skills.** Similarly, if you have deep knowledge of a statistical method (pyfixest, Bayesian analysis, cluster analysis), a Python library (geopandas, networkx), or a domain area (school finance policy, graduation rate interpretation), you can use the `skill-authoring` skill to draft a new skill and submit it. These skills directly expand what DAAF can do competently -- without them, DAAF falls back to the model's general training, which is often not specific enough for rigorous work.

- **Writing FAQ entries based on your experience.** The FAQ documents ([**07. FAQ: Technical Support**](user_reference/07_faq_technical.md) and [**06. FAQ: Philosophy**](user_reference/06_faq_philosophy.md)) are living documents that grow from real user questions. If you ran into something confusing, chances are good that someone else will too. Writing up the question and answer saves future users the same frustration.

- **Testing with different data sources and reporting results.** If you run DAAF with a data source it hasn't seen before -- especially one outside the education domain -- and document what happened (what worked, what broke, what was surprising), that's extremely valuable feedback for understanding where the framework generalizes well and where it doesn't.

### High Effort (days to weeks)

These contributions involve modifying the core framework -- the agents, protocols, validation logic, or orchestration workflow. They require a solid understanding of DAAF's architecture and a willingness to engage with the project's strongly opinionated design philosophy. If you're considering work at this level, I'd strongly recommend opening an issue to discuss your approach *before* writing code. This saves everyone time and helps me give early feedback on whether the direction aligns with the project's design principles.

- **Writing or modifying agent protocols.** DAAF has many specialized agents, each with detailed behavioral protocols (in the `.claude/agents/` directory). Modifying an existing agent's protocol -- say, making the code-reviewer more thorough about a specific class of errors, or improving the research-executor's handling of edge cases -- requires understanding how that agent fits into the broader pipeline, what its inputs and outputs look like, and how changes ripple through dependent stages. New agents are an even bigger undertaking. Read [`.claude/agents/README.md`](.claude/agents/README.md) for the full landscape, and see the `agent-authoring` skill for the creation workflow if you're adding a new one. The key thing to understand: agents don't work in isolation. Every agent has producers (who send it input) and consumers (who depend on its output), and changes need to respect those contracts. Extensive pre/post testing is **essential** to ensuring its proper use and integration without causing unintended consequences downstream.

- **Changing validation logic or checkpoint definitions.** The validation framework (CP1-CP4 checkpoints, QA1-QA4b reviews, stage gates) is one of the most carefully designed parts of DAAF, and is arguably the most important part of how it all works. It exists to catch both operational failures (empty data, wrong types) and logical errors (wrong methodology, misinterpretation). If you want to modify checkpoint thresholds, add new validation criteria, or change the gate enforcement logic, you'll need to understand the full validation chain documented in [`agent_reference/VALIDATION_CHECKPOINTS.md`](agent_reference/VALIDATION_CHECKPOINTS.md) and [`agent_reference/QA_CHECKPOINTS.md`](agent_reference/QA_CHECKPOINTS.md). Changes here have outsized impact -- a relaxed threshold might let subtle data corruption through, while an overly strict one might cause unnecessary STOP conditions.

- **Adding new framework capabilities.** This is the broadest category -- anything from adding support for new output formats, to implementing parallel execution optimizations, to building new orchestration patterns. The bar for framework changes is high because DAAF's components are deeply interconnected. A change to the workflow stages, for instance, potentially affects the [orchestrator skill references](.claude/skills/daaf-orchestrator/references/full-pipeline-mode.md), the [workflow phase files](agent_reference/) in `agent_reference/`, [`CLAUDE.md`](CLAUDE.md), multiple agent protocols, the Plan template, the State template, and the integration checker. That said, well-considered framework improvements are exactly the kind of contribution that benefits everyone, and I'm genuinely excited to collaborate on them.

- **Improving the Docker setup or CI/CD pipeline.** If you have DevOps expertise, the containerization and deployment infrastructure could definitely benefit from more experienced hands. I built the Docker setup to be functional and secure, but I'm a researcher, not a DevOps engineer -- there are almost certainly improvements to be made in build performance, layer caching, security hardening, and CI/CD automation. Please help!

- **Porting to other coding agent platforms.** DAAF is built on Claude Code, but the vast majority of the tooling -- Skills, Agents, `agent_reference/` protocols -- can be ported to any similar agentic coding harness (Gemini CLI, Codex, OpenCode, etc.). The Hooks system is the most platform-specific component and will need more finessing. If you're interested in bringing DAAF to other platforms, this would be an incredibly valuable contribution that opens the framework to a much broader user base.

- **Coding language expansion.** DAAF currently works in the Python ecosystem by default. But it's entirely possible to adapt it for R, Julia, or any other analytic language that runs from the command line. I chose Polars (which follows similar syntax to R's tidyverse) partly to split the difference, but native R support would open DAAF to a huge population of researchers who think in R and shouldn't have to switch.

### Extension vs. Contribution: Where's the Line?

This comes up often enough that it's worth being explicit. The rule of thumb from [**04. Extending DAAF**](user_reference/04_extending_daaf.md):

> **If you're adding a new `.md` file to `.claude/skills/` or `.claude/agents/`, you're extending. If you're editing existing files in `agent_reference/`, `.claude/agents/`, or the root `CLAUDE.md`, you're contributing.**

This distinction matters for two reasons. First, it determines which guide to follow -- extension workflows are in [**04. Extending DAAF**](user_reference/04_extending_daaf.md), contribution workflows are here. Second, it has licensing implications under LGPL-3.0: extensions you build on top of DAAF are yours to keep proprietary or open-source as you choose, while modifications to the core framework must be shared back if you distribute them. See the [**README**](README.md#open-source--licensing) for the full details.

In practice, many contributions involve *both* -- for example, creating a new data source skill (extension) that also touches agent definitions or reference files (contribution). That's totally fine. Just be aware that edits to core framework files fall under the contribution category.

---

## What Makes a Good Contribution

Not every contribution needs to be huge, but every contribution should meet a baseline standard of quality. Here's what I look for when reviewing PRs, and what I'd encourage you to aim for.

### Documentation Contributions

- **Accuracy first.** If you're describing how something works, make sure it actually works that way. Run it yourself. The worst documentation is confidently wrong documentation.
- **Match the voice.** DAAF's documentation is written in a conversational, first-person style -- warm but direct, honest about limitations, educational in framing. Read the README and existing user docs to calibrate. Overly formal or corporate-sounding prose will stick out. We may want to revisit this paradigm in the future, but it's extremely important to me for now that these materials are all highly approachable and pedagogically-forward.
- **Explain the "why," not just the "what."** DAAF has a lot of opinionated design decisions. When documenting them, explain the reasoning. "DAAF requires per-script QA (not batched at stage end)" is fine, but "DAAF requires per-script QA because batching means errors in script 1 propagate silently through scripts 2, 3, and 4 -- compounding data corruption that's far harder to diagnose" is much better.
- **Link generously.** The documentation suite is interconnected. When you mention a concept that's explained elsewhere, link to it. Don't make readers hunt.

### Skill Contributions

- **No `[PRELIMINARY]` markers.** If the Data Onboarding process flagged interpretations as preliminary, you need to resolve them before submitting. That's the whole point of the human review step.
- **Follow the canonical structure.** Data source skills have a 12-section template (see [**04. Extending DAAF**](user_reference/04_extending_daaf.md) for the full walkthrough). Methodology and domain skills are more free-form, but should still follow the patterns in the `skill-authoring` skill.
- **Substantive pitfalls section.** The Common Pitfalls section is arguably the most valuable part of any data source skill. "Data may have missing values" is not a useful pitfall. "Free/reduced lunch counts are unreliable after ~2014 due to Community Eligibility Provision (CEP) -- use direct certification data instead" is a useful pitfall. The difference is specificity and actionability.
- **Tested end-to-end.** At minimum, run a Data Discovery Test and a Fetch Test (see [Testing Your Changes](#testing-your-changes) below).

### Agent and Protocol Contributions

- **Understand the ripple effects.** Agents and protocols are deeply interconnected. Before modifying one, trace its dependencies -- what sends it input? What consumes its output? What stage gates does it affect? The `.claude/agents/README.md` file has a coordination matrix that maps these relationships.
- **Maintain the validation chain.** DAAF's core principle is "every transformation has a validation." Contributions that weaken this chain -- by relaxing thresholds, skipping checkpoints, or bypassing gates -- will face significant scrutiny. If you think a threshold is too strict, make the case with evidence from real analyses.
- **Document your reasoning.** In the PR description, explain *why* you're making the change, not just *what* you changed. What problem did you encounter? What alternatives did you consider? Why is this approach better?

### Code Contributions

- **Follow the existing patterns.** DAAF's Python code follows specific conventions -- Polars over pandas, parquet over CSV, file-first execution (write to file then run, never inline execution), inline audit trail documentation. Read [`agent_reference/SCRIPT_EXECUTION_REFERENCE.md`](agent_reference/SCRIPT_EXECUTION_REFERENCE.md) and [`agent_reference/INLINE_AUDIT_TRAIL.md`](agent_reference/INLINE_AUDIT_TRAIL.md) for the standards. These don't need to be hard-and-fast forever, but you should have a good reason for deviating if you do.
- **Include validation.** Every script should validate its own output -- check shapes, assert expected conditions, report statistics. This is a core framework requirement and expectation of users based on the primary goals/framing of the project.

---

## Filing Effective Issues

A well-written issue saves everyone time -- including yours, because it means I can actually reproduce and fix the problem instead of going back and forth asking for details. Here's what makes issues actionable.

### Bug Reports

When opening a bug report, the more context you can provide, the faster it gets resolved. The ideal bug report includes:

- **What you asked DAAF/Claude to do** -- the prompt or request you gave. Exact wording is helpful because DAAF's behavior depends heavily on how requests are classified (Full Pipeline vs. Data Discovery vs. Data Lookup).
- **What happened vs. what you expected** -- be specific about the failure. "It didn't work" is hard to debug. "It produced a cleaned dataset with 50,000 rows when I expected ~200,000, and the suppression rate was 75% which triggered a STOP condition" is very debuggable.
- **Which stage failed** -- if you can identify it. DAAF's multi-stage pipeline means the same symptom can have very different causes depending on where it occurs. Even a rough sense ("it failed during data fetch" or "the plan looked wrong" or "the code reviewer flagged something as a BLOCKER") helps narrow things down enormously. Look at the output files for each as needed, as well as any failed script file versions and accompanying comments/output logs.
- **Session log excerpts** -- check `.claude/logs/sessions/` for the relevant Markdown log. These logs capture the full sequence of tool calls, subagent invocations, and their results. Copy the section where things went wrong (redact any API keys or sensitive content first!!!). See [Using Session Logs](#using-session-logs-for-debugging-and-issue-reports) below for details on finding and reading these logs.
- **Your environment** -- Docker or native install, OS, Claude Code authentication method (API key vs. subscription), and which Claude model you were using (Opus 4.5, Opus 4.6, Sonnet, etc.). Model differences can produce meaningfully different behavior. Please note it'll be REALLY hard to diagnose issues if you're not using the standard, recommendation installation format followed by users -- if you're contributing, please make that a priority.
- **Reproducibility** -- Can you trigger the same failure again? If so, does it happen every time or intermittently? Intermittent failures are often context-window-related (the model "forgets" something at higher utilization) or just the unfortunate nature of working with LLMs (remember, the goal is not to **eliminate slop**, which is likely impossible in the LLM paradigm, but to just drastically reduce it), while consistent failures usually point to a real bug in the framework logic.

### Feature Requests and Suggestions

- **What you're trying to accomplish** -- the research question or workflow that motivated the request. This context helps me understand whether the feature fits DAAF's mission or is better solved a different way.
- **What's missing or could be better** -- be specific about the gap. "DAAF should be better at statistics" is hard to act on. "DAAF doesn't have a skill for survival analysis, so when I asked it to analyze time-to-graduation data, it fell back to basic descriptive statistics instead of using Kaplan-Meier curves" is a clear, actionable gap.
- **Ideas for how it could work** -- if you have them (totally optional). Even rough sketches of how you imagine a feature working can be helpful, but don't feel pressured to design the solution. Sometimes the best feature requests are just clear articulations of the problem.

### Data Source Issues

- **Which data source** -- e.g., CCD, IPEDS, Scorecard. Include the specific skill name if you know it (e.g., `education-data-source-ccd`).
- **The API endpoint or variables involved** -- if you can identify them. For example: "The `school_type` variable in the CCD schools endpoint" is much more actionable than "a variable was wrong."
- **What the data looked like vs. what was expected** -- row counts, unexpected values, missing columns, coded values that don't match the skill documentation. If the actual data contradicts the skill's documentation, that's exactly the kind of discrepancy that needs to be caught and fixed.

### Issue Etiquette

- **Search first.** Check if someone has already reported the same issue. If they have, add your experience as a comment -- additional data points help even if the issue is already known.
- **One issue per issue.** If you found three separate problems, file three separate issues. This makes tracking and resolution much cleaner.
- **Use labels when available.** The issue templates will suggest labels. Using them helps me prioritize.
- **Follow up.** If I ask a clarifying question on your issue, please respond when you can. Stale issues with unanswered questions are hard to act on and tend to languish.

---

## Testing Your Changes

Before submitting a PR, you'll want to verify that your changes actually work the way you intend -- and more importantly, that they don't break things that were working before. Here's a practical testing sequence, from lightest to heaviest.

### For Documentation Changes

Documentation changes are the easiest to test:

1. **Read it aloud.** Seriously. If it sounds awkward or confusing when spoken, it reads that way too.
2. **Check all links.** Every `[text](url)` should point to a real file or section. Broken links are one of the most common documentation issues.
3. **Check cross-references.** If you reference a concept, stage, agent, or protocol, make sure the reference is accurate. DAAF's documentation is heavily interconnected -- an inaccurate cross-reference can send someone down the wrong path.
4. **Render the Markdown.** Use a Markdown previewer (VS Code's built-in preview, a browser extension, or an online tool like [StackEdit](https://stackedit.io/app)) to make sure tables render correctly, code blocks are properly fenced, and formatting is as intended.

### For Skill Contributions

If you're submitting a new or modified skill, run through this sequence (also described in more detail in [**04. Extending DAAF**](user_reference/04_extending_daaf.md)):

1. **Data Discovery test.** Ask DAAF: "What data sources does DAAF know about? Can you tell me about [your new data source]?" Skills are auto-discovered via YAML frontmatter, so DAAF should describe it accurately. If it can't find the skill, verify that the skill's YAML frontmatter has a clear description and that `SKILL.md` is placed in `.claude/skills/{skill-name}/`.

2. **Fetch test.** Ask DAAF to fetch data using your skill and show basic summary statistics. This tests the data access pathway -- dataset paths, mirror configuration, and loading mechanics. If CP1 validation fails, it usually means the dataset path doesn't match what's available on the mirror.

3. **Context test.** Ask DAAF to fetch *and clean* the data, watching for correct handling of coded values, missing data codes, and source-specific caveats. The cleaning script should reference the specific coded values and pitfalls documented in your skill.

4. **Full pipeline test (optional but ideal).** Run a simple, well-defined research question through the entire pipeline. Keep the scope deliberately narrow -- you're testing integration, not analytical sophistication.

### For Agent and Protocol Changes

Agent and protocol changes are the hardest to test because their effects cascade through the pipeline:

1. **Trace the dependency chain.** Before testing, identify which stages and other agents are affected by your change. The [`.claude/agents/README.md`](.claude/agents/README.md) coordination matrix is your friend here.

2. **Run the affected stage.** The minimum viable test is running a DAAF analysis that exercises the stage your change affects. Watch the session log carefully for the specific agent invocations related to your change.

3. **Check gate satisfaction.** Every stage has gate criteria (documented in `.claude/skills/daaf-orchestrator/references/full-pipeline-mode.md`). Verify that your change doesn't cause a previously-passing gate to fail, or a previously-failing gate to pass when it shouldn't.

4. **Run a full pipeline (strongly recommended).** For changes to core agents (research-executor, code-reviewer, data-planner) or validation logic, nothing substitutes for running a complete analysis start-to-finish and verifying that all stages complete successfully.

### For Hook or Infrastructure Changes

If you're modifying hooks (`.claude/hooks/`), Docker configuration, or other infrastructure:

1. **Test in a clean environment.** Start from a fresh Docker build (`docker compose up -d --build`) to make sure your changes work from a clean state, not just from your existing environment.
2. **Verify hook execution.** Check `.claude/logs/` for evidence that hooks fired correctly (audit log entries, session archives, etc.).
3. **Test the safety boundaries.** If your change is anywhere near the safety infrastructure (the `bash-safety.sh` hook, permission deny rules, etc.), test that the safety boundaries are still enforced. Try a few commands that should be blocked and verify they're still blocked.

**Running the shell/PowerShell test suites in-container.** The `scripts/host/` lifecycle scripts and shared libraries are covered by `bats` (Bash) and Pester (PowerShell) suites under `tests/`, plus `shellcheck`, `PSScriptAnalyzer`, and `tests/lint/check-daaf-conventions.sh`. These run in CI (`.github/workflows/ci-scripts.yml`) on every push that touches a script. To reproduce that toolchain **inside the DAAF container** rather than installing it on your host, set `DAAF_DEV=1` in your `daaf-docker` folder's `environment_settings.txt` and rebuild (`rebuild_daaf.sh` / `.ps1`) — this installs `shellcheck`, `bats`, PowerShell 7, Pester, and PSScriptAnalyzer into the image. Then, from inside the container (`bash run_daaf.sh bash`):

```bash
bats tests/bash/
shellcheck -x scripts/host/*.sh
bash tests/lint/check-daaf-conventions.sh
pwsh -NoProfile -Command "Invoke-Pester -Path ./tests/powershell/"
pwsh -NoProfile -Command "Get-ChildItem ./scripts/host/*.ps1 | ForEach-Object { Invoke-ScriptAnalyzer -Path \$_.FullName -Settings ./.github/linters/PSScriptAnalyzerSettings.psd1 }"
```

`DAAF_DEV` is an opt-in build flag: when it is unset or `0` (the default), none of this tooling is installed and the image is identical to a standard build. See `user_reference/01_installation_and_quickstart.md` ("Building with the developer test toolchain") for details.

---

## Using Session Logs for Debugging and Issue Reports

Session logs are automatically archived transcripts of every Claude Code session, stored in `.claude/logs/sessions/` as both human-readable Markdown and machine-readable JSONL files. They capture every tool call, subagent dispatch, and file operation -- making them invaluable for debugging and issue reports.

For details on finding, reading, and browsing session logs (including the DAAF Log Explorer interactive viewer), see [**FAQ: Session Logs and Diagnostics**](user_reference/07_faq_technical.md#session-logs-and-diagnostics).

### Including Log Excerpts in Issues

When including session log excerpts in issue reports:

1. Open the `.md` log file for the session where the problem occurred
2. Find the relevant section (search for the stage or error message)
3. Copy just the relevant portion -- you do not need the whole log
4. **Redact sensitive information** -- remove any API keys, file paths with personal info, or data that should not be public
5. Wrap excerpts in a `<details>` block to keep the issue tidy:

````markdown
<details>
<summary>Session log excerpt</summary>

```
(paste the relevant section of your session log here)
```

</details>
````

Issue templates are available when you [create a new issue](https://github.com/DAAF-Contribution-Community/daaf/issues/new/choose) to help guide you through this.

---

## License

DAAF is licensed under **LGPL-3.0-or-later** (GNU Lesser General Public License v3.0 or any later version). The license is implemented as two files in the repository root:

| File | Contents |
|------|----------|
| [LICENSE](LICENSE) | The full text of the GNU General Public License v3.0 (the base license) |
| [COPYING.LESSER](COPYING.LESSER) | The GNU Lesser General Public License v3.0 additions that apply on top of the GPL-3.0 base |

### What This Means for Contributors

- **Your contributions to the core framework** are licensed under LGPL-3.0-or-later. By signing off under the DCO (see above), you certify that you have the right to submit your contribution under this license.
- **Extensions you build on top of the framework** (custom skills, agents, analysis scripts, data configurations) are yours. The LGPL does not require you to open-source extensions that use the framework's interfaces without modifying the framework itself.
- **If you distribute modified versions of the core framework**, you must release those core modifications under LGPL-3.0-or-later and make the corresponding source code available.

For a detailed explanation of what counts as "core" versus "extension," including practical examples, see the [**Open Source & Licensing**](README.md#open-source--licensing) section of the README.

---

## Recommended Next Steps

- [**04. Extending DAAF**](user_reference/04_extending_daaf.md) -- How to add new data source skills, analytical tools and methodologies, creating your own additional specialized agents, and customizing the Python environment
- [**06. FAQ: Philosophy**](user_reference/06_faq_philosophy.md) -- Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**07. FAQ: Technical Support**](user_reference/07_faq_technical.md) -- Covers frequently asked questions about Docker, issues with Claude Code, usage limits, authentication errors, and other common errors
- [**Back to main**](https://github.com/DAAF-Contribution-Community/daaf/tree/main)
