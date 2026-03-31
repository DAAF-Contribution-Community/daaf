<!--
  README v2.0.0 DRAFT — Restructured for clarity and discoverability

  Content identified for eventual FAQ migration (NOT removed here, just noted):
  - Author's four project goals (Awareness, Education, High Standards, Accelerating Research) — currently in FAQ/Philosophy territory
  - Full author biography and origin story — condensed here, full version could live in FAQ
  - Extended licensing philosophy — condensed here, expanded version in FAQ
  - "What are DAAF's current limitations?" honest self-assessment — good candidate for FAQ entry

  Anchor changes from v1 README (cross-reference impact):
  - #summary-what-is-daaf → removed (was the old H2; summary is now the opening section, no anchor needed)
  - #vision--purpose → removed (content merged into summary + design principles)
  - #what-daaf-can-do-today → removed (content distributed to summary, key features, engagement modes)
  - #what-daaf-can-do-with-your-help → #contributing (condensed)
  - #why-open-source-what-does-it-mean-for-daaf → #open-source--licensing
  - #how-to-cite → #how-to-cite (preserved)
  - #recommended-next-steps → #recommended-next-steps (preserved)
  - #about-the-author → #about-the-author (preserved)
  - #acknowledgments → #acknowledgments (preserved)
  - NEW anchors: #quick-start, #key-features, #design-principles, #engagement-modes,
    #demo--sample-project, #why-education-data, #user-documentation
-->

<img width="4096" height="1296" alt="DAAF Logo" src="https://github.com/user-attachments/assets/616fae4e-2bd7-44aa-a52c-954d473dbb10" />

<p align="center">
  <a href="https://github.com/DAAF-Contribution-Community/daaf/releases"><img src="https://img.shields.io/badge/version-v2.0.0-blue" alt="Version v2.0.0"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-LGPL--3.0--or--later-green" alt="License: LGPL-3.0-or-later"></a>
  <a href="https://github.com/DAAF-Contribution-Community/daaf/stargazers"><img src="https://img.shields.io/github/stars/DAAF-Contribution-Community/daaf?style=flat" alt="GitHub Stars"></a>
  <a href="https://github.com/DAAF-Contribution-Community/daaf/commits/main"><img src="https://img.shields.io/github/last-commit/DAAF-Contribution-Community/daaf" alt="Last Commit"></a>
</p>

**DAAF, the Data Analyst Augmentation Framework,** is an open-source, extensible workflow for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that allows skilled researchers to rapidly scale their expertise and accelerate data analysis by as much as 5-10x -- without sacrificing the transparency, rigor, or reproducibility demanded by our core scientific principles. In energetic and vocal opposition to deeply misguided attempts to *replace* human researchers, DAAF is a force-multiplying *"exo-skeleton"* for researchers with trained experts at the helm -- firmly keeping humans-in-the-loop. The base framework comes ready to analyze any or all of the 40+ foundational public education datasets available via the [Urban Institute Education Data Portal](https://educationdata.urban.org/documentation/), and is readily extensible to new data domains and methodologies. Install and begin using it in as little as 10 minutes from a fresh computer.

<p align="center">
  <a href="https://youtu.be/ZAM9OA0AlUs"><strong>Demo Video</strong></a> &nbsp;|&nbsp;
  <a href="user_reference/01_installation_and_quickstart.md"><strong>Installation Guide</strong></a> &nbsp;|&nbsp;
  <a href="#user-documentation"><strong>Documentation</strong></a> &nbsp;|&nbsp;
  <a href="https://daafguide.substack.com/"><strong>Substack</strong></a> &nbsp;|&nbsp;
  <a href="CONTRIBUTING.md"><strong>Contributing</strong></a>
</p>

---

## Quick Start

**Requirements:** [Git](https://git-scm.com/downloads), [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running), and an [Anthropic Max subscription](https://claude.com/pricing/max) ($100-200/mo) or [API key](https://console.anthropic.com/). Opus 4.5/4.6 models required. See [Installation Guide](user_reference/01_installation_and_quickstart.md) for full details and prerequisites.

```bash
# 1. Clone the repository
git clone https://github.com/DAAF-Contribution-Community/daaf.git
cd daaf

# 2. Copy project files into a secure Docker volume
docker run --rm -v "${PWD}:/source:ro" -v "daaf_daaf-data:/dest" busybox cp -a /source/. /dest/

# 3. Build and start the container
docker compose up -d --build

# 4. Enter the container and launch Claude Code
docker compose exec daaf-docker bash
claude
```

On first launch, Claude Code will prompt you to authenticate. Set your model to **Opus 4.5** or **Opus 4.6** via `/model`, and set **Auto-compact** to **False** and **Verbose output** to **True** via `/config`. You're ready to go. ([3-minute video of the full install](https://www.youtube.com/watch?v=jqkVLXA1CV4))

---

## Key Features

- **File-first transparency.** Every data operation is written to a script file and executed with full audit trail -- no interactive/hidden execution. Every edit, every revision, every decision is saved and reviewable.
- **Multi-agent QA pipeline.** Code produced by the research-executor is broken into hyper-atomic steps and reviewed by an adversarial code-reviewer agent. Plans and reports are similarly vetted by informed counterparts. Slop can never be completely removed, but it can be heavily reduced.
- **Eight engagement modes.** From quick data lookups to end-to-end research pipelines with four human checkpoints, DAAF adapts to what you actually need (see [Engagement Modes](#engagement-modes) below).
- **Fully reproducible pipelines.** Every data file, script, and output is stored and documented. Final outputs include a consolidated [marimo](https://marimo.io/) notebook for exploration and a summary report with data visualizations and limitations.
- **Extensible to new data domains.** Use Data Onboarding mode to profile and integrate any new dataset in minutes. Use the skill-authoring tools to add new methodological toolsets and domain expertise. ([10-minute tutorial](https://youtu.be/G5uKSlI6jls))
- **GUIDE-LLM disclosure built in.** All reports include AI use attribution following the [GUIDE-LLM](https://llm-checklist.com/) consensus reporting checklist, with session transcripts archived for unprecedented transparency.
- **Safety-first architecture.** Docker isolation, destructive command prevention, credential protection, and programmatic guardrails -- not just instructions, but enforced hooks and permission rules. (See [CLAUDE.md](CLAUDE.md) for full details.)

---

## Design Principles

DAAF explicitly embraces the fact that LLM research assistants will never be perfect and can never be trusted as a matter of course. But with the right guardrails, they can still be immensely valuable for critically-minded researchers. Every design decision serves four core requirements:

- **Transparent.** Because LLMs will always be susceptible to lying, hallucinating, and cutting corners, DAAF forces Claude Code to operate using file-first principles: all data operations are drafted and run as actual Python files, all reasoning is stored as verbose comments, plan documents, and structured code output that you can review and intervene on at any time.
- **Scalable.** Because most LLMs are trained as generalists susceptible to sycophancy and overconfidence, DAAF provides a comprehensive and extensible set of explicit instructions and standards enforcing highly opinionated best practices (via agent and skill documents), injecting the right information at the right time for any specific task -- so you don't have to hold its hand every time.
- **Rigorous.** Because LLMs can work at speeds orders of magnitude faster than humans, DAAF's workflows force Claude to be meticulous, cautious, self-checking, and extremely thorough. Code is broken into hyper-atomic steps and adversarially reviewed. Plans and reports are informed by deep-dives into actual data documentation and actual exploratory analyses, then also reviewed by equally informed counterparts.
- **Reproducible.** Because good science needs to be reproducible, every single data file, script, and output is automatically stored throughout the entire process. You **do not** have to just trust DAAF or Claude Code -- you can and should verify everything yourself.

---

## Engagement Modes

DAAF supports eight engagement modes, each tailored to a different type of request:

| Mode | What It Does | Key Output |
|------|-------------|------------|
| **Data Onboarding** | Profile a new dataset and create a reusable data source skill | SKILL.md + Research project |
| **Data Lookup** | Quick lookup of a variable, coded value, or definition | Direct answer |
| **Data Discovery** | Read-only data exploration -- no code, no downloads | Findings summary |
| **Ad Hoc Collaboration** | Flexible working session -- debug, review code, brainstorm approaches, write scripts | Conversation + workspace artifacts |
| **Full Pipeline** | End-to-end research analysis with 4 human checkpoints | Plan + Scripts + Notebook + Report |
| **Revision and Extension** | Update or extend an existing analysis (new version, original preserved) | Updated artifacts |
| **Reproducibility Verification** | Verify that an existing analysis reproduces from its notebook | Reproduction Report |
| **Framework Development** | Modify DAAF itself -- create or edit skills, agents, modes, templates | Framework artifacts + integration report |

Ready to get started? See [Installation Guide](user_reference/01_installation_and_quickstart.md) for setup and [Understanding and Working with DAAF](user_reference/02_understanding_daaf.md) for in-depth usage guidance.

---

## Demo & Sample Project

- [**Watch the 10-minute demo**](https://youtu.be/ZAM9OA0AlUs) walking through all the main functionalities of DAAF
- Browse the corresponding [full sample project archive](./research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/) or jump straight to the [main report](./research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Report.md)
- Never used Claude Code? [See how quick the full install is from start-to-finish](https://www.youtube.com/watch?v=jqkVLXA1CV4) (3 minutes)

---

## Why Education Data?

DAAF is designed to be domain-extensible -- new data sources can be integrated by authoring Skills and profiling datasets (see **Data Onboarding mode** and this [10-minute tutorial](https://youtu.be/G5uKSlI6jls)). I chose the [Urban Institute Education Data Portal](https://educationdata.urban.org/) as the initial demonstration domain because it offers:

- High-quality, well-documented public data
- Real, immediate policy relevance (K-12 schools, districts, colleges, outcomes)
- Sufficient complexity to stress-test the system (multiple sources, coded values, suppression rules, cross-state comparability issues)

The architecture, agents, validation protocols, and workflow stages are domain-agnostic -- only the Skills are domain-specific.

---

## Contributing

DAAF is still very much in its nascency and will need the support of the community to really be ready for more serious use in research workflows. If you're interested in pushing this frontier forward, you can contribute by:

- **Filing bug reports and sharing LEARNINGS.md files** -- even a quick issue with session log context is extremely valuable. Every completed project produces actionable learnings that help DAAF self-improve.
- **Expanding data sources and methodological tools** -- use Data Onboarding mode to profile new datasets, or use the skill-authoring tools to package new statistical methods and domain expertise into reusable skills.
- **Improving workflows, documentation, and efficiency** -- DAAF is *extremely* usage-hungry and likely far moreso than it needs to be. Suggestions for balancing quality with speed, better documentation, and clearer onboarding are all welcome.
- **Porting to other platforms and languages** -- the vast majority of DAAF's tooling can be ported to any similar agentic coding harness (Gemini CLI, Codex, OpenCode, etc.), and the analytic language can be extended beyond Python to R, Julia, and more.

See [**Contributing to DAAF**](CONTRIBUTING.md) for the full contribution guide and [**Extending DAAF**](user_reference/04_extending_daaf.md) for how to add new capabilities for your own use.

---

## User Documentation

- **00. README** -- **\[This document\]** Project overview, quick start, design philosophy, and acknowledgments
- [**01. Installation & Quick Start**](user_reference/01_installation_and_quickstart.md) -- Prerequisites, step-by-step setup, day-to-day usage, and troubleshooting
- [**02. Understanding and Working with DAAF**](user_reference/02_understanding_daaf.md) -- What to expect, how to use DAAF, and how to test its strengths and limitations
- [**03. Best Practices**](user_reference/03_best_practices.md) -- Prompting tips, quality assurance, reviewing outputs, and managing context
- [**04. Extending DAAF**](user_reference/04_extending_daaf.md) -- Adding new data source skills, analytical tools, and specialized agents
- [**05. Contributing to DAAF**](CONTRIBUTING.md) -- Filing issues, contribution workflows, and community norms
- [**06. FAQ: Philosophy**](user_reference/06_faq_philosophy.md) -- Broader implications of AI in research, equity, environmental costs, and more
- [**07. FAQ: Technical Support**](user_reference/07_faq_technical.md) -- Docker issues, Claude Code troubleshooting, usage limits, and common errors

---

## How to Cite

If you use DAAF in your research, please cite it. Software citation ensures credit for open-source tools and supports reproducibility by recording the exact version used.

**Plain text (APA):**

> Kim, B. H. (2026). *DAAF: Data Analyst Augmentation Framework* (Version 2.0.0) [Computer software]. https://github.com/DAAF-Contribution-Community/daaf

**BibTeX:**

```bibtex
@software{kim2026daaf,
  author = {Kim, Brian Heseung},
  title = {{DAAF}: Data Analyst Augmentation Framework},
  year = {2026},
  url = {https://github.com/DAAF-Contribution-Community/daaf},
  version = {2.0.0},
  license = {LGPL-3.0-or-later}
}
```

GitHub also provides a "Cite this repository" button (powered by the [`CITATION.cff`](CITATION.cff) file) that generates APA and BibTeX citations automatically. Following [FORCE11 Principle 6](https://force11.org/info/software-citation-principles-published-2016/) (Specificity), please cite the **exact version** of DAAF you used -- every DAAF report automatically records the git commit hash and version in its AI Use Disclosure section.

### Layered Citation Guidance

When using DAAF, there are multiple layers of tooling involved. We recommend citing each layer that substantively contributed:

| Layer | What to Cite | When |
|-------|-------------|------|
| **DAAF** (this framework) | Kim (2026), as above | Always -- if DAAF managed your workflow |
| **Claude** (the AI model) | Anthropic model card or technical report for the model version used | Always -- see the AI Use Disclosure in your report |
| **Data sources** | Per data source documentation (e.g., Urban Institute Education Data Portal) | Always -- cite every data source used |
| **GUIDE-LLM checklist** | Feuerriegel et al. (2026), as cited in [Acknowledgments](#acknowledgments) | When including AI use disclosure in publications |

---

## Open Source & Licensing

This project is very intentionally licensed under the **GNU Lesser General Public License v3.0** (LGPL-3.0-or-later). Anyone can use and access DAAF for any reason, for free, forever, because I think this work is way, way, way too important and high-stakes to treat it as anything but a shared and collective effort we should all be able to contribute to and benefit from. Internal use personally or within your organization -- no matter how extensively you modify the framework -- is completely unrestricted.

More restrictions kick in only if you want to **distribute a modified version** of DAAF. Core framework improvements must also be licensed open-source, but any extensions you build on top of the framework (skills for proprietary datasets, bespoke agents, etc.) can remain private and yours to use as you wish under any license. This ensures DAAF remains open and community-driven while allowing use in contexts involving sensitive, proprietary, or classified data. For the full philosophy behind this decision, see [FAQ: Philosophy](user_reference/06_faq_philosophy.md). See [LICENSE](LICENSE) and [COPYING.LESSER](COPYING.LESSER) for the full license text.

---

## About the Author

Hello! If you don't know me, my name is Brian Heseung Kim ([@brhkim](https://github.com/brhkim)). I have been at the frontier of finding rigorous, careful, and auditable ways of using LLMs and their predecessors in social science research since roughly 2018. I focused my [entire Ph.D. dissertation](https://libraetd.lib.virginia.edu/public_view/nz806060w) on teaching others how to use these tools responsibly (finished in mid-2022, months before ChatGPT had even been released), and I [continue](https://journals.sagepub.com/doi/10.3102/0013189X241276814) to [work](https://journals.sagepub.com/doi/10.3102/00028312241292309) on [that frontier](https://link.springer.com/article/10.1007/s11162-025-09847-5) today. I lead the data science and research wing for a large education non-profit (though I am currently working on DAAF solely in my capacity as a private individual and independent researcher). As a former public high school English teacher, much of why DAAF is packaged as an educational endeavor comes from my deep belief that one of my most important value-adds will be in helping peers and colleagues rapidly skill-up on this frontier.

---

## Acknowledgments

### Urban Institute Education Data Portal

The current proof-of-concept iteration of this project would not be possible without the **[Urban Institute Education Data Portal](https://educationdata.urban.org/)** -- a remarkable public resource that harmonizes data from over a dozen federal education data sources into a single, well-documented API. I am deeply grateful to the Urban Institute for making high-quality education data freely accessible, providing excellent documentation and consistent data structures, harmonizing complex federal datasets, and supporting the research community with responsive maintenance and updates.

If you use DAAF or the Education Data Portal in your work, please cite the Urban Institute appropriately. See the [Education Data Portal documentation](https://educationdata.urban.org/documentation/) for citation guidelines. Please be extremely kind and appreciative of them -- they were not aware of DAAF until well into development (in fairness, it didn't seem worth sharing until I could confirm it actually worked well!).

### GUIDE-LLM Reporting Checklist

DAAF integrates the **[GUIDE-LLM](https://llm-checklist.com/)** reporting checklist into all output workflows to help researchers transparently and rigorously disclose how AI was used in their work. GUIDE-LLM is a consensus-based reporting standard developed by over 80 experts for studies using large language models in the behavioral and social sciences.

> Feuerriegel, S., Barrie, C., Crockett, M. J., Globig, L. K., McLoughlin, K. L., Mirea, D.-M., Spirling, A., Yang, D., ..., Rathje, S., & Ribeiro, M. H. (2026). A consensus-based reporting checklist for large language models in behavioral and social science. Available at: https://llm-checklist.com/

### Inspiration

Several core workflow patterns in this project -- particularly around agent specialization, shared working memory, and task decomposition -- were vastly improved thanks to excellent practices in **[Get Shit Done](https://github.com/glittercowboy/get-shit-done)** by [@glittercowboy](https://github.com/glittercowboy). If you're more into the world of software development, that's an amazing resource to work from!

Early thinking for this project was rapidly accelerated by Dr. Anton Korinek's working paper, [AI Agents for Economic Research](https://www.genaiforecon.org/JEL-2025-Aug-AIAgents.pdf). I highly recommend a read and tracking his lab's work going forward.

---

## Recommended Next Steps

- [**Installation Guide**](user_reference/01_installation_and_quickstart.md) -- Get DAAF up and running in 10 minutes
- [**Understanding and Working with DAAF**](user_reference/02_understanding_daaf.md) -- Learn how to use DAAF effectively for the first time
- [**FAQ: Philosophy**](user_reference/06_faq_philosophy.md) -- Broader implications of AI in research, equity, environmental costs, and what this means for the next generation
- [**Watch the demo**](https://youtu.be/ZAM9OA0AlUs) -- See DAAF in action end-to-end
