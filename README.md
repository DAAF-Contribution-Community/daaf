# DAAF: the Data Analyst Augmentation Framework

**Summary:** DAAF is an open-source, extensible workflow for Claude Code that allows **skilled researchers** to rapidly scale their expertise and accelerate data analysis by as much as 5-10x -- without sacrificing the transparency, rigor, or reproducibility demanded by our core scientific principles. DAAF explicitly embraces the fact that LLM research assistants will never be perfect and can never be trusted as a matter of course. But by providing strict guardrails, enforcing best practices, and ensuring the highest levels of auditability possible, DAAF ensures that LLM research assistants can still be **immensely valuable** for critically-minded researchers capable of verifying and reviewing their work. In energetic and vocal opposition to the deeply misguided attempts to *replace* human researchers, DAAF is intended to be a force-multiplying *"exo-skeleton"* for researchers (firmly keeping humans-in-the-loop). 

Install and begin using it in as little as 10 minutes from a fresh computer with a high-usage Anthropic account. The base framework comes ready to analyze any or all of the 40+ foundational public education datasets available via the [Urban Institute Education Data Portal](https://educationdata.urban.org/documentation/), and is readily extensible to new data domains and methodologies with a suite of built-in tools to ingest new data sources and craft new Skill files at will. 

By open-sourcing DAAF as an open and extensible framework (see more on [Open-source Licensing](#open-source-licensing) below), I hope to provide a foundational resource that the entire community of researchers and data scientists can use, benefit from, learn from, and extend via critical conversations and collaboration together. By pairing DAAF with an intensive array of educational materials, tutorials, blog deep-dives, and videos via project documentation and the [DAAF Field Guide Substack](https://daafguide.substack.com/) (much, much more to come!!), I also hope to rapidly accelerate the readiness of the scientific community to genuinely and critically engage with AI disruption and transformation writ large. More than anything, I just hope all of this work can somehow be useful for my many peers and colleagues trying to "catch up" to this rapidly developing (and extremely scary) frontier. 

Learn more about my vision for DAAF, what makes DAAF different from other attempts to create LLM research assistants, what DAAF currently can and cannot do as of today, how you can get involved, and how you can get started with DAAF yourself by diving in below.

---

## User Documentation Table of Contents

- **00. README** — **\[This document\]** Vision and purpose, project goals, what DAAF does and does not do, core design philosophy, acknowledgments
- [**01. Installation & Quick Start**](user_reference/01_installation_and_quickstart.md) — Get started! Installation prerequisites, step-by-step 5-minute setup, day-to-day usage, and troubleshooting
- [**02. Understanding and Working with DAAF**](user_reference/02_understanding_daaf.md) — Learn to work with DAAF for the first time: what to expect, how to use it, and how to test its strengths and limitations
- [**03. Best Practices**](user_reference/03_best_practices.md) — Tips for working with Claude Code, writing effective prompts, ensuring quality and rigor with DAAF, reviewing outputs, and managing context
- [**04. Extending DAAF**](user_reference/04_extending_daaf.md) — How to add new data source skills, analytical tools and methodologies, and creating your own additional specialized agents
- [**05. Contributing**](user_reference/05_contributing.md) — Get involved in developing DAAF! How to file issues via GitHub, support expanding the capabilities of the framework, contribute to educational tutorials and how-to's, and more!
- [**06. FAQ: Technical**](user_reference/06_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, design rationale, authentication errors, and other common errors
- [**07. FAQ: Philosophy**](user_reference/07_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more

---

## README Table of Contents
- [**Vision & Purpose**](#vision--purpose)
- [**What DAAF Can Do Today**](#what-daaf-can-do-today)
- [**What DAAF Can Do With Your Help**](#what-daaf-can-do-with-your-help)
- [**Recommended Next Steps**](#recommended-next-steps)
- [**Open-source Licensing**](#prerequisites)
- [**Acknowledgments**](#acknowledgments)
- [**About the Author**](#about-the-author)

---

## Vision & Purpose

This project attempts to answer a critical question facing all of scientific research and data science today: **How can responsible researchers use modern AI/LLM agents to meaningfully accelerate complex quantitative data analysis tasks while maintaining the rigor and reproducibility that good science demands?**

I firmly believe any real answer to this question in the current LLM-centric paradigm of AI will need to fulfill four core requirements to be useful:
- **1. Transparent:** Because LLMs will always be susceptible to lying, hallucinating, and cutting corners, researchers need to be able to easily **audit and inspect everything an LLM produces** at every step
- **2. Scalable:** Because most LLMs are trained as generalists susceptible to sycophancy and overconfidence, researchers need to be able to easily **provide structured, targeted expertise and guidance to LLM agents at scale** -- injecting the right information at the right time for any specific task the LLM engages with, using minimal effort
- **3. Rigorous:** Because LLMs can work at speeds orders of magnitude faster than humans, researchers need to be assured that the general output of any LLM assistants are **high-enough quality by default to be worth producing and reviewing** -- minimizing (but not eliminating) the share of work produced that is AI slop
- **4. Reproducible:** Because good science needs to be reproducible, researchers need to be able to **reproduce everything LLMs do on their behalf** through well-documented and executable code from start-to-finish

DAAF is a set of **forever free, completely open-source, and highly structured workflows** to operationalize and enforce the core requirements when using Claude Code, a popular LLM agent program built on Anthropic's Claude AI. Any researcher willing to pay for a high-usage Anthropic account can begin using this in as little as 10 minutes (alas, an importantly high barrier-to-entry with prices starting at $100/mo given the resource-intensivity of the frontier models capable of this work). DAAF ultimately allows researchers to more confidently and productively leverage Claude Code for rigorous research work by addressing each core requirement in its fundamental design principles:
- **1. Transparent:** DAAF forces Claude Code to operate using **file-first principles**: All data inspections, operations, or analyses it conducts are drafted and then run first as actual Python file, enforcing full transparency into everything it does data-wise. Any and all "thinking" it does during the analytic process are stored as verbose comments, plan documents, and structured code output that you can review and intervene on at any time. Every single edit/revision to any file in the workflow is saved separately with changelog, so the full history of work is saved for future reference.
- **2. Scalable:** DAAF provides a comprehensive and extensible set of explicit **instructions and standards enforcing highly opinionated best practices** (via agent and skill documents) to guide each and every step of Claude's analytic workflow, so you don't have to hold its hand. Use DAAF's robust defaults, or edit them to your own taste and needs.
- **3. Rigorous:** DAAF's workflows force Claude to be **paranoid, self-doubting, self-checking, and extremely thorough** before it tries to show you **anything**. Any code Claude produces is broken into hyper-atomic steps that are reviewed by another instance of Claude instructed to be highly adversarial and extremely exacting in its code inspections. Any user-facing plans and reports it produces are first informed by deep-dives into the actual data documentation and actual exploratory analyses on the data itself, then also reviewed by a thoughtful and equally informed counterpart to ensure it addresses your core research goals and questions. Slop can never be completely removed, but it can be heavily reduced in scale.
- **4. Reproducible:** DAAF ensures that every single data file, script, and output are automatically stored throughout the entire process. Your final outputs include both an in-depth, high quality summary report, as well as a compiled analytic walkthrough allowing you to review and explore every single line of code, as well as every single data file produced along the way. This ensures that you **DO NOT** have to just trust DAAF or Claude Code -- you can and should verify everything yourself.

The end-result? I believe that a skilled researcher using DAAF and Claude Code can **easily produce 5-10x the amount of rigorous, careful, and thoughtful data analysis** over what they could complete alone or with more ad-hoc/interactive engagement with LLM assistants -- a sort of **force-multiplying exo-skeleton for researchers with trained experts at the helm** (i.e., human-in-the-loop, in energetic and vocal opposition to deeply misguided attempts to replace researchers entirely). DAAF explicitly embraces the fact that LLM research assistants will never be perfect and can never be trusted as a matter of course. But with a skilled researcher at the helm, LLM research assistants shaped by DAAF can still be immensely useful in scaling the value of the researcher's hard-won expertise.

By open-sourcing this work as an open and extensible framework (see more on [Open-source Licensing](#open-source-licensing) below), I hope to provide a foundational resource that the entire community of researchers and data scientists can use, benefit from, learn from, and extend via critical conversations and collaboration together. By pairing DAAF with an intensive array of educational materials, tutorials, blog deep-dives, and videos via project documentation and the [DAAF Field Guide Substack](https://daafguide.substack.com/) (much, much more to come!!), I also hope to rapidly accelerate the readiness of the scientific community to genuinely and critically engage with AI disruption and transformation writ large. More than anything, I just hope all of this work can somehow be useful for my many peers and colleagues trying to "catch up" to this rapidly developing (and extremely scary) frontier.

---

## What DAAF Can Do Today

As of launch, DAAF can be downloaded, installed, and run by any skilled researcher in as little as 10 minutes on a fresh computer (see [**01. Installation & Quick Start**](user_reference/01_installation_and_quickstart.md) for installation instructions). 

For demonstration purposes, DAAF comes out-of-the-box ready to analyze any or all of the 40+ foundational public education datasets available via the [Urban Institute Education Data Portal](https://educationdata.urban.org/documentation/). A skilled researcher can then ask any arbitrarily simple or complex research question you can think of, and DAAF will thoroughly, carefully, and robustly explore whether and how to address your inquiry with the data at hand. Once you approve a given plan, it will spring into execution mode: using a series of coding and QA agents in a loop, it'll conduct every single step of data analysis necessary (from fetching the data online, to filtering, to transforming, to joining, to analyzing, to visualizing) to address your research question, updating you at regular intervals for your input on developing data issues, shortcomings, and other key decision points. At the end of the process, it will produce for you:

1. A summary report describing the approach, data, and results for your research question, complete with data visualizations and key limitations
2. Every single code, data, and diagnostics file produced along the way for full replicability
3. A consolidated `marimo` python notebook walking you through every completed step and allowing you to inspect every intermediary dataset in one easy-to-audit place
4. An in-depth "Lessons Learned" document highlighting any data issues, interpretation concerns, analytic problems, or limitations that you can immediately "feed back" into DAAF to improve its documentation and workflows for the next go-around -- self-improvement with every single project run.

Then: Want to rethink how a measure was created? Ask for it. Want to create a concise one-pager for a specific stakeholder or policymaker audience? Ask for it. Want an interactive visualization dashboard helping you inspect and explore a key measure? Ask for it. Want to do a subsample analysis or run a new robustness check? You get the idea.

A full start-to-finish project, from potentially vague idea to report, and any follow-up deliverables you could possibly want, in about 10 minutes of active engagement time, a little over an hour of humming independently in the background, whatever API fees you incur along the way, and the time you rightfully and importantly dedicate to reviewing its work (an absolute must-do, no exceptions!). 

And it can be done **in parallel with as many other LLM-assisted projects running** as you can stand to keep track of at the same time.

Ready to get started? See [**01. Installation & Quick Start**](user_reference/01_installation_and_quickstart.md) for installation instructions and [**02. Understanding and Working with DAAF**](user_reference/02_understanding_daaf.md) for in-depth guidance on how to start piloting the system for yourself.

---

## What DAAF Can Do With Your Help

While built with the public education datasets out-of-the-box for demonstration purposes, DAAF also includes a suite of tools that allow advanced users to easily and rapidly extend its capabilities in a number of important directions:
- **Data ingestion:** Ask DAAF to invoke the `data-ingest` agent, point it to a dataset (being extremely careful to ensure that you abide by your organization's AI policy and data protection standards for it!!!), and provide any codebook or documentation available. DAAF will carefully build an intensive set of data documentation via manual data diagnostics and exploration, allowing it to use that data robustly and carefully in any future research request.
- **Methodological skill extensions:** Ask DAAF to use the `skill-authoring` skill and conduct deep research online for documentation or literature on a given methodological toolset for Python (e.g., pyfixest, predictive analytics, cluster analysis, etc.) to generate a new methodological toolset it can reference for future analyses.
- **Content area knowledge skill extensions:** Similarly, ask DAAF to use the `skill-authoring` skill and conduct deep research online for literature on a given area of domain expertise to help it navigate future analyses with more appropriate intuition, data concerns, and limitations
- **Better, more robust, and more efficient workflows:** At launch, DAAF is fully functioning and shockingly robust based on various batteries of testing and reproducibility inspections. That being said, this framework is still very much in its nascency, and will need to be broken and amended and improved as more people push it to its current limits. If you find a bug or have a suggestion, please [open an issue!](https://github.com/brhkim/daaf/issues)
- **Coding language agnosticism:** Today, DAAF works primarily in the Python ecosystem as its default analytic language. That being said, it is entirely possible to replace Python with any analytic toolset that can be installed open-source and run from the command line (e.g., R). I use the Polars library (which follows extremely similar syntax to tidyverse) to try and split the difference, but future collaborators can help us incorporate other languages more freely to suit more analytic workflows and organizational contexts.

I welcome community contributions to any of these ends! If you tackle any of the above, please share back with the community for us all to benefit as this framework expands. Please review existing issues before creating new ones, and be respectful in all interactions. I'm not a software developer, so a lot of this true open-source collaboration work will take some time to acclimate to! For detailed guidance on filing effective issues (including how to use session logs), development setup, and making your own framework modifications, see [**05. Contributing**](user_reference/05_contributing.md).

### Why Education Data as the Demonstration Domain?

DAAF is designed to be domain-extensible — new data sources can be integrated by authoring Skills and profiling datasets (see the `data-ingest` agent). I chose the [Urban Institute Education Data Portal](https://educationdata.urban.org/) as the initial demonstration domain for DAAF because it offers:

- High-quality, well-documented public data
- Real, immediate policy relevance (K-12 schools, districts, colleges, outcomes)
- Sufficient complexity to stress-test the system (multiple sources, coded values, suppression rules, cross-state comparability issues)

The architecture, agents, validation protocols, and workflow stages are domain-agnostic — only the Skills are domain-specific.

---

## Recommended Next Steps

- [**01. Installation & Quick Start**](user_reference/01_installation_and_quickstart.md) — Get started! Installation prerequisites, step-by-step 5-minute setup, day-to-day usage, and troubleshooting
- [**06. FAQ: Technical**](user_reference/06_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, design rationale, authentication errors, and other common errors
- [**07. FAQ: Philosophy**](user_reference/07_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more

---

## Open-source Licensing

**Critical Note:** This summary is provided for convenience and does not constitute legal advice. See [LICENSE](LICENSE) and [COPYING.LESSER](COPYING.LESSER) for the full license text. If you have specific compliance questions, consult a qualified attorney.

This project is very intentionally licensed under the **GNU Lesser General Public License v3.0** (LGPL-3.0-or-later). What does that mean? 

**The simple version:** Anyone can use and access the DAAF project for any reason, for free, forever, because I think this work is way, way, way too important and high-stakes to treat it as anything but a shared and collective effort we should all be able to contribute to and benefit from. If you make improvements or changes to the **core DAAF framework** and want to distribute that version as your own, those core framework improvements **must also** be shared back with the entire community as open-source. However, any extensions you build **in addition to and on top of the framework** (e.g., skills for proprietary and private datasets, skills methodological tools, bespoke agents for new domains, etc.) can remain private and yours to use as you wish.

This specific license ensures that the core research tooling offered by DAAF remains open and transparent and community-driven. At the same time, it allows DAAF to be used in a diverse range of contexts — including those involving sensitive, proprietary, or classified data — without requiring users to open-source their data configurations, research methodologies, or analysis outputs. This matters because many of the researchers and analysts who would benefit most from DAAF work with data that cannot be made public (government agencies, healthcare researchers, private-sector analysts, etc.).

### The Core vs. Extensions Principle

Unlike the standard GPL, the LGPL distinguishes between **modifying the framework itself** and **building on top of it**. In either case, note that copyleft obligations only trigger when you **distribute** a modified version of DAAF to others. Internal use within your organization — no matter how extensively you modify the framework — requires no sharing whatsoever. For example:

**Modifications to DAAF's core** must be shared open-source if you distribute them yourself, such as (but not limited to):
- Changes to the orchestrator logic, workflow stages, or validation protocols
- Modifications to existing agent definitions or bundled Skills
- Bug fixes or enhancements to DAAF's Python workflows and protocols

**Extensions built on DAAF** are yours to keep proprietary or open-source as you see fit, such as (but not limited to):
- Private data source Skills you author for your own databases
- Custom agents you create for your organization's specific workflows
- Research methodologies and analysis scripts you develop using DAAF
- All data, outputs, reports, notebooks, and visualizations you produce via DAAF

### Practical Examples

| Scenario | Must you share open-source? | Why |
|----------|----------------|-----|
| You fix a bug in DAAF's orchestrator and publish your fork | **Yes** | This modifies the core framework and is distributed |
| You create a Skill for your agency's private student database | **No** | This is an extension — a new file that uses DAAF's interfaces |
| You add a custom agent for your team's internal review process | **No** | New agents are extensions, and internal use never triggers sharing |
| You apply a proprietary statistical methodology in your analysis scripts | **No** | Analysis scripts are your work product, not part of DAAF |
| You modify DAAF's validation checkpoints for internal use only | **No** | Internal modifications are never subject to LGPL obligations |
| You work with FERPA-protected, classified, or proprietary data | **No** | Data processed by the framework is never affected by the license |
| You run DAAF in a private Docker container within your organization | **No** | Running software internally is not distribution |
| You modify the DAAF core framework and want to sell as new software | **Yes** | Distributing modified core framework code triggers LGPL |

---

## Acknowledgments

### Urban Institute Education Data Portal

The current proof-of-concept iteration of this project would not be possible without the **[Urban Institute Education Data Portal](https://educationdata.urban.org/)**—a remarkable public resource that harmonizes data from over a dozen federal education data sources into a single, well-documented API.

I am deeply grateful to the Urban Institute for:
- Making high-quality education data freely accessible to researchers
- Providing excellent documentation and consistent data structures
- Harmonizing complex federal datasets that would otherwise require significant expertise to navigate
- Supporting the research community with responsive maintenance and updates

If you use DAAF or the Education Data Portal in your work, please cite the Urban Institute appropriately. See the [Education Data Portal documentation](https://educationdata.urban.org/documentation/) for citation guidelines. Please be extremely kind and appreciative of them -- they were not aware of DAAF until well into development (in fairness, it didn't seem worth sharing until I could confirm it actually worked well!).

### Inspiration

Several core workflow patterns in this project—particularly around agent specialization, shared working memory, and task decomposition—were vastly improved thanks to excellent practices in **[Get Shit Done](https://github.com/glittercowboy/get-shit-done)** by [@glittercowboy](https://github.com/glittercowboy). If you're more into the world of software development, that's an amazing resource to work from!

Early thinking for this project began in mid-2025 as I saw growing agentic automation in the software development sphere, but was rapidly accelerated when I first read Dr. Anton Korinek's working paper, [AI Agents for Economic Research](https://www.genaiforecon.org/JEL-2025-Aug-AIAgents.pdf). I highly recommend a read and tracking his lab's work going forward -- more relevant than ever now, I think and hope, with the launch of DAAF.

## About the Author
Hello! If you don't know me, my name is Brian Heseung Kim (@brhkim in most places). I have been at the frontier of finding rigorous, careful, and auditable ways of using LLMs and their predecessors in social science research since roughly 2018, when I thought: hey, machine learning seems like kind of a big deal that [I probably need to learn more about](https://drive.google.com/file/d/1ShZeS2wRWu_ifWREfctj3D4TyYZch0hL/view?usp=drive_link). When I saw the massive potential for research of all kinds as well as the extreme dangers of mis-use, I then focused my [entire Ph.D. dissertation](https://libraetd.lib.virginia.edu/public_view/nz806060w) trying to teach others how to use these new tools responsibly (finished in mid-2022, many months before ChatGPT had even been released!). Today, I [continue](https://journals.sagepub.com/doi/10.3102/0013189X241276814) to [work](https://journals.sagepub.com/doi/10.3102/00028312241292309) on [that frontier](https://link.springer.com/article/10.1007/s11162-025-09847-5) and help lead the data science and research wing for a large education non-profit using many of these approaches (though please note that I am currently working on DAAF solely in my capacity as a private individual and independent researcher).

I started working on DAAF in the summer of 2025 when reading [Dr. Korinek's article mentioned above](https://www.genaiforecon.org/JEL-2025-Aug-AIAgents.pdf). I thought to myself: With a sufficiently carefully crafted set of agents, why *wouldn't* I be able to accelerate my work on multiple frontiers? And with detailed and intentional prompting instructions, why *wouldn't* I be able to make it as paranoid and thoughtful about data as I am myself? I immediately began exploring options to deploy agentic systems, but found both that agentic frameworks were still too far from formalized to be worth investing in, and that model quality and complexity just didn't quite seem to be there yet. That all really seemed to change in late November 2025 with the [release of Claude Opus 4.5](https://www.anthropic.com/news/claude-opus-4-5) and the increasing capabilities built into [agentic workflows via Claude Code](https://www.anthropic.com/news/enabling-claude-code-to-work-more-autonomously) and similar agentic coding harnesses (e.g., Codex, Gemini CLI, OpenCode, etc.). I began experimentation in December, 2025, and actual development on the first stages of DAAF in January, 2026. Several very intense marathon weekends of coding, testing, writing, and scoping with colleagues later, and here we are today. As an aside, I started my career as a traditionally-certified public high school English teacher, which is part of why so much of DAAF is packaged as an educational endeavor: While I've cultivated many crucial skills in formalizing research toolsets and rigorous guardrails from my research endeavors, I think one of my most important value-adds for the field today will be in helping peers and colleagues rapidly skill-up on this frontier.
