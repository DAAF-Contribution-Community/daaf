# 05. Contributing

**UNDER CONSTRUCTION, EVERYTHING HERE SUBJECT TO CHANGE BY LAUNCH** This guide covers all forms of contribution to DAAF, from filing an issue to modifying core framework components. Whether you've found a bug, want to improve documentation, or are building new agents — this is where to start.

[**Back to main**](../.)

---

## Ways to Contribute

<!-- NEW: Spectrum from easy to advanced contributions -->

Contributions come in many forms, ranging from quick feedback to deep framework work. Here's the spectrum from easiest to most involved.

### Low Barrier

- Filing bug reports with session log excerpts
- Suggesting documentation improvements
- Reporting data source issues (missing variables, incorrect coded values)
- Sharing your experience and use cases

### Medium Effort

- Improving existing documentation
- Adding new data source skills (see [Extending DAAF](04_extending_daaf.md))
- Writing FAQ entries based on your experience
- Testing with different data sources and reporting results

### High Effort

- Writing or modifying agent protocols
- Changing validation logic or checkpoint definitions
- Adding new framework capabilities
- Improving the Docker setup or CI/CD pipeline

---

## Filing Effective Issues

<!-- MIGRATE: README section "Filing Issues" — complete section including bug reports, feature requests, data source issues -->

How to write issue reports that make debugging and resolution easier.

### Bug Reports

When opening a bug report, please include:

- **What you asked the assistant to do** — the prompt or request you gave
- **What happened vs. what you expected** — be specific about the failure
- **Which stage failed** — if you can tell (e.g., "it failed during data fetch" or "the plan looked wrong")
- **Session log excerpts** — check `.claude/logs/sessions/` for the relevant Markdown log. Copy the section where things went wrong (redact any API keys or sensitive content first)
- **Your environment** — Docker or native install, OS, Claude Code authentication method (API key vs. subscription)

### Feature Requests and Suggestions

- **What you're trying to accomplish** — the research question or workflow
- **What's missing or could be better** — be specific about the gap
- **Ideas for how it could work** — if you have them (totally optional)

### Data Source Issues

- **Which data source** — e.g., CCD, IPEDS, Scorecard
- **The API endpoint or variables involved** — if you can identify them
- **What the data looked like vs. what was expected** — row counts, unexpected values, missing columns

---

## Using Session Logs for Debugging and Issue Reports

<!-- MIGRATE: README FAQ "Session Logs & Diagnostics" — both Q&A entries -->
<!-- MIGRATE: README "Filing Issues" — "Tips for including session logs" subsection -->

How to find, read, and include session logs when reporting issues.

### Where Session Logs Are Stored

Claude Code automatically archives a complete log of every session when it ends. These are stored locally in `.claude/logs/sessions/` in two formats:

| Format | File Pattern | Purpose |
|--------|-------------|---------|
| **Markdown** (`.md`) | `YYYY-MM-DD_HH-MM-SS_<session-id>.md` | Human-readable transcript with tool calls, timestamps, and token usage |
| **JSONL** (`.jsonl`) | `YYYY-MM-DD_HH-MM-SS_<session-id>.jsonl` | Raw machine-readable transcript (full API-level detail) |

Additionally, `.claude/logs/activity.log` records a timestamped entry every time a session starts, giving you a quick overview of usage history.

**These logs are gitignored by default** (they may contain sensitive content or API details), so they stay on your local machine and are never pushed to the repository.

### Reading Session Logs for Debugging

Session logs are invaluable when something goes wrong. The Markdown logs show you exactly what the assistant did, in order — every tool call, every file read/write, every subagent invocation, and the full output at each step. If you need to file a bug report or understand an unexpected result:

1. Find the relevant session log in `.claude/logs/sessions/` (sorted by timestamp)
2. Open the `.md` file to review what happened in a readable format
3. Look for the point where things went wrong — you'll see the exact tool calls and their results
4. When filing an issue, include relevant excerpts from the log (redact any sensitive data first)

The `.jsonl` file contains the complete raw transcript if deeper inspection is needed.

### Including Log Excerpts in Issues

When including session log excerpts in issues:

1. Open the `.md` log file for the session where the problem occurred
2. Find the relevant section (search for the stage or error message)
3. Copy just the relevant portion — you don't need the whole log
4. **Redact sensitive information** — remove any API keys, file paths with personal info, or data that shouldn't be public
5. Wrap excerpts in a `<details>` block to keep the issue tidy:

````markdown
<details>
<summary>Session log excerpt</summary>

```
(paste the relevant section of your session log here)
```

</details>
````

Issue templates are available when you [create a new issue](https://github.com/brhkim/daaf/issues/new/choose) to help guide you through this.

---

## Development Setup

<!-- NEW: Setup guidance for contributors who want to modify the framework, beyond the basic Docker install -->

How to set up your environment for framework development, including how the codebase is organized.

### Beyond the Basic Docker Install

Additional setup steps for contributors: enabling pre-commit hooks, understanding the test structure, and development workflow.

### Understanding the Development Workflow

How to make changes, test them, and verify they work before submitting.

---

## Understanding the Codebase

<!-- NEW: Guide to the codebase structure for contributors — deeper than the user-facing overview in 02 -->

A contributor-oriented map of the codebase, explaining how agents, agent_reference, and skills relate to each other.

### agents/ — Behavioral Protocols

What agent files contain (execution patterns, validation rules) and how they're loaded by the orchestrator.

### agent_reference/ — Framework Reference

What the reference files contain (templates, protocols, checkpoint definitions) and when they're consulted.

### .claude/skills/ — Domain Knowledge

How skills are structured, where they live, and how they're loaded by subagents.

### How Agents, Skills, and the Orchestrator Interact

The execution flow from user request through orchestrator to subagent to skill and back.

---

## Framework Modification Guidance

<!-- NEW: Guidance for modifying core framework components -->

How to approach changes to agents, protocols, validation logic, and other framework components.

### Writing or Modifying Agents

What an agent protocol file should contain, how to test agent behavior, and conventions to follow.

### Changing Protocols and Validation

How to modify validation checkpoints, STOP conditions, or stage gate logic safely.

### Adding New Framework Capabilities

How to extend the framework with new stages, agents, or tools while maintaining compatibility.

---

## Code Style and Conventions

<!-- NEW: Coding and documentation conventions for the project -->

Style guidelines for Python scripts, markdown documentation, agent protocols, and skill definitions.

### Python Conventions

Naming, formatting, and documentation expectations for scripts and notebooks.

### Markdown Conventions

Structure and formatting expectations for documentation files.

### Commit Message Conventions

How commit messages should be formatted (the `plan:`, `data:`, `feat:`, `docs:` prefixes).

---

## License: GPL-3.0

<!-- MIGRATE: README section "License" — complete section including "What This Means" and "Copyleft Requirement" -->

What the GPL-3.0 license means for your contributions and forks.

### What This Means for Contributors

- Freedom to use: Use this software for any purpose
- Freedom to study: Access and modify the source code
- Freedom to share: Distribute copies
- Freedom to improve: Distribute your modifications

If you distribute modified versions of this software, you must:
- Release your modifications under GPL-3.0
- Make source code available
- Preserve copyright notices

### What This Means for Forks

If you distribute modified versions, you must release your modifications under GPL-3.0 and make source code available.

### Why GPL-3.0?

We chose GPL-3.0 to ensure that improvements to this proof-of-concept remain open and accessible to the research community. AI-assisted research tools should be transparent and auditable—proprietary forks would undermine this goal.

---

## Community Norms and Expectations

<!-- NEW: Community standards for interaction -->

How to interact respectfully in issues, pull requests, and discussions. The project maintainer's note about being new to open-source collaboration.

---

## Recommended Next Steps

- [**06. FAQ: Technical**](06_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, design rationale, authentication errors, and other common errors
- [**07. FAQ: Philosophy**](07_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**Back to main**](../.)
