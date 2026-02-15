# 05. Contributing to DAAF

This guide covers all forms of contribution to DAAF, from filing an issue to modifying core framework components. Whether you've found a bug, want to improve documentation, or are building new agents — this is where to start.

---

## Table of Contents
- [**Introduction**](#introduction)
- [**Governance**](#governance)
- [**Quick Start: Contribution Workflow**](#quick-start-contribution-workflow)
- [**Developer Certificate of Origin**](#developer-certificate-of-origin)
- [**Ways to Contribute**](#ways-to-contribute)
- [**Filing Effective Issues**](#filing-effective-issues)
- [**Using Session Logs for Debugging and Issue Reports**](#using-session-logs-for-debugging-and-issue-reports)
- [**License**](#license)
- [**Recommended Next Steps**](#recommended-next-steps)

---

## Introduction

Thank you for your interest in contributing to DAAF. Whether you are reporting a bug, suggesting an improvement, authoring a new data source skill, or proposing changes to core framework logic, your contribution is valued and appreciated. Before participating, please review the project's [Contributor Covenant Code of Conduct v2.0](CODE_OF_CONDUCT.md). By participating, you agree to uphold its standards. Instances of unacceptable behavior may be reported to the project maintainer, Brian Heseung Kim ([@brhkim](https://github.com/brhkim)). All reports will be reviewed and investigated promptly and confidentially.

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

## Quick Start: Contribution Workflow

The standard contribution workflow has nine steps:

1. **Fork** the repository on GitHub.
2. **Clone** your fork:
   ```bash
   git clone https://github.com/YOUR-USERNAME/daaf.git
   ```
3. **Create a feature branch** from `main`:
   ```bash
   git checkout -b my-feature main
   ```
4. **Install pre-commit hooks** (one-time setup):
   ```bash
   pip install pre-commit && pre-commit install
   ```
5. **Make your changes**, then commit with a DCO sign-off (see [Developer Certificate of Origin](#developer-certificate-of-origin) below):
   ```bash
   git commit -s -m "feat: add new data source skill for NHGIS"
   ```
6. **Push** to your fork:
   ```bash
   git push origin my-feature
   ```
7. **Open a pull request** against `main` on the upstream repository.
8. **Address review feedback** from the maintainer.
9. **Maintainer merges** (squash and merge).

### Commit Message Format

Use a prefix that describes the nature of the change, followed by a colon and a short description.

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

### Full DCO Text

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

Contributions come in many forms, ranging from quick feedback to deep framework work. Here is the spectrum from easiest to most involved.

### Low Barrier

- Filing bug reports with session log excerpts
- Suggesting documentation improvements
- Reporting data source issues (missing variables, incorrect coded values)
- Sharing your experience and use cases

### Medium Effort

- Improving existing documentation
- Adding new data source or methodology skills (see [**04. Extending DAAF**](user_reference/04_extending_daaf.md))
- Writing FAQ entries based on your experience
- Testing with different data sources and reporting results

### High Effort

- Writing or modifying agent protocols
- Changing validation logic or checkpoint definitions
- Adding new framework capabilities
- Improving the Docker setup or CI/CD pipeline

---

## Filing Effective Issues

How to write issue reports that make debugging and resolution easier.

### Bug Reports

When opening a bug report, please include:

- **What you asked the assistant to do** -- the prompt or request you gave
- **What happened vs. what you expected** -- be specific about the failure
- **Which stage failed** -- if you can tell (e.g., "it failed during data fetch" or "the plan looked wrong")
- **Session log excerpts** -- check `.claude/logs/sessions/` for the relevant Markdown log. Copy the section where things went wrong (redact any API keys or sensitive content first)
- **Your environment** -- Docker or native install, OS, Claude Code authentication method (API key vs. subscription)

### Feature Requests and Suggestions

- **What you're trying to accomplish** -- the research question or workflow
- **What's missing or could be better** -- be specific about the gap
- **Ideas for how it could work** -- if you have them (totally optional)

### Data Source Issues

- **Which data source** -- e.g., CCD, IPEDS, Scorecard
- **The API endpoint or variables involved** -- if you can identify them
- **What the data looked like vs. what was expected** -- row counts, unexpected values, missing columns

---

## Using Session Logs for Debugging and Issue Reports

How to find, read, and include session logs when reporting issues.

### Where Session Logs Are Stored

Claude Code automatically archives a complete log of every session when it ends. These are stored locally in `.claude/logs/sessions/` in two formats:

| Format | File Pattern | Purpose |
|--------|-------------|---------|
| **Markdown** (`.md`) | `YYYY-MM-DD_HH-MM-SS_<session-id>.md` | Human-readable transcript with tool calls, timestamps, and token usage |
| **JSONL** (`.jsonl`) | `YYYY-MM-DD_HH-MM-SS_<session-id>.jsonl` | Raw machine-readable transcript (full API-level detail) |

Additionally, `.claude/logs/activity.log` records a timestamped entry every time a session starts, giving you a quick overview of usage history, while `.claude/logs/audit.jsonl` gives a full inventory of every tool call by Claude for additional diagnostics.

**These logs are gitignored by default** (they may contain sensitive content or API details), so they stay on your local machine and are never pushed to the repository.

### Reading Session Logs for Debugging

Session logs are invaluable when something goes wrong. The Markdown logs show you exactly what the assistant did, in order -- every tool call, every file read/write, every subagent invocation, and the full output at each step. If you need to file a bug report or understand an unexpected result:

1. Find the relevant session log in `.claude/logs/sessions/` (sorted by timestamp)
2. Open the `.md` file to review what happened in a readable format
3. Look for the point where things went wrong -- you will see the exact tool calls and their results
4. When filing an issue, include relevant excerpts from the log (redact any sensitive data first)

The `.jsonl` file contains the complete raw transcript if deeper inspection is needed.

### Including Log Excerpts in Issues

When including session log excerpts in issues:

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

For a detailed explanation of what counts as "core" versus "extension," including practical examples, see the [**Why open-source? What does it mean for DAAF?**](README.md#why-open-source-what-does-it-mean-for-daaf) section of the README.

---

## Recommended Next Steps

- [**06. FAQ: Technical**](user_reference/06_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, design rationale, authentication errors, and other common errors
- [**07. FAQ: Philosophy**](user_reference/07_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**Back to main**](.)
