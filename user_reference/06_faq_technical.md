# 06. FAQ: Technical

Operational questions with concrete answers. If you're stuck, troubleshooting, or curious about a technical choice — check here first.

---

## Documentation Table of Contents

- [**00.** README](../README.md) — \[**Prerequisite**\] Vision and purpose, what DAAF does and does not do, core design philosophy, acknowledgments
- [**01.** Installation & Quick Start](01_installation_and_quickstart.md) — Get started! Installation prerequisites, step-by-step 5-minute setup, day-to-day usage, and troubleshooting
- [**02.** Understanding DAAF](02_understanding_daaf.md) — Learn to work with DAAF for the first time: what to expect, engagement modes explained, your first analysis walkthrough
- [**03.** Best Practices](03_best_practices.md) — Tips for working with Claude Code, writing effective prompts, ensuring quality and rigor with DAAF, reviewing outputs, and managing context
- [**04.** Extending DAAF](04_extending_daaf.md) — How to add new data source skills, analytical tools and methodologies, and creating your own additional specialized agents
- [**05.** Contributing](05_contributing.md) — Get involved in developing DAAF! How to file issues via GitHub, support expanding the capabilities of the framework, contribute to educational tutorials and how-to's, and more!
- **06.** FAQ: Technical — \[**This document**\] Covers frequently asked questions about Docker, issues with Claude Code, usage limits, authentication errors, and other common errors (this document)
- [**07.** FAQ: Philosophy](07_faq_philosophy.md) — Design rationale, AI in research, broader questions about this approach

---

## Setup and Docker

<!-- NOTE: README installation/troubleshooting content moves to 01_installation_and_quickstart.md -->
<!-- These FAQ entries should cross-reference or lightly duplicate 01's troubleshooting, tailored for Q&A format -->

### Q: Docker Desktop says "Cannot connect to the Docker daemon"

<!-- CROSS-REF: 01_installation_and_quickstart.md "Docker Daemon Not Running" — summarize here in Q&A format -->

How to verify Docker Desktop is running and restart it.

### Q: "Port 2718 already in use" when trying to view a notebook

<!-- CROSS-REF: 01_installation_and_quickstart.md "Port Conflicts" — summarize here in Q&A format -->

How to identify and resolve port conflicts, including changing the port mapping.

### Q: The container seems slow to build the first time

<!-- CROSS-REF: 01_installation_and_quickstart.md "Slow First Build" — summarize here in Q&A format -->

Why the first build takes longer and that subsequent starts are fast.

### Q: "command not found: docker" after installing Docker Desktop

<!-- CROSS-REF: 01_installation_and_quickstart.md "'command not found: docker'" — summarize here in Q&A format -->

Terminal restart requirements after Docker installation.

### Q: How do I update DAAF to the latest version?

<!-- NEW: Anticipated question — pulling updates from the repository -->

How to pull the latest changes from the repository and rebuild the container.

### Q: Can I run DAAF without Docker?

<!-- NEW: Anticipated question — native installation possibility -->

Why Docker is recommended, and what you'd need to set up manually if you chose to run natively (not recommended or supported).

---

## Authentication

<!-- CROSS-REF: 01_installation_and_quickstart.md "Authentication Persistence" and "Anthropic Account & Authentication" -->

### Q: Claude Code asks for my API key every time I start the container

<!-- CROSS-REF: 01_installation_and_quickstart.md "Authentication Persistence" — summarize here in Q&A format -->

Why this happens with `docker compose down` and how to persist authentication via `.env` file.

### Q: Should I use an API key or a Pro/Max subscription?

<!-- CROSS-REF: 01_installation_and_quickstart.md "Anthropic Account & Authentication" — summarize here in Q&A format -->

Comparison of the two authentication methods, cost implications, and the maintainer's experience with Max plan.

### Q: Can I use a different AI provider (OpenAI, Google, etc.)?

<!-- NEW: Anticipated question about alternative providers -->

DAAF is designed for Claude Code but the architecture is portable. Brief guidance on what adaptation would require.

---

## Session Logs and Diagnostics

<!-- MIGRATE: README FAQ "Session Logs & Diagnostics" — both Q&A entries -->

### Q: Where are session logs stored?

Claude Code automatically archives a complete log of every session when it ends. These are stored locally in `.claude/logs/sessions/` in two formats:

| Format | File Pattern | Purpose |
|--------|-------------|---------|
| **Markdown** (`.md`) | `YYYY-MM-DD_HH-MM-SS_<session-id>.md` | Human-readable transcript with tool calls, timestamps, and token usage |
| **JSONL** (`.jsonl`) | `YYYY-MM-DD_HH-MM-SS_<session-id>.jsonl` | Raw machine-readable transcript (full API-level detail) |

Additionally, `.claude/logs/activity.log` records a timestamped entry every time a session starts, giving you a quick overview of usage history.

**These logs are gitignored by default** (they may contain sensitive content or API details), so they stay on your local machine and are never pushed to the repository.

### Q: How can I use session logs for debugging?

Session logs are invaluable when something goes wrong. The Markdown logs show you exactly what the assistant did, in order — every tool call, every file read/write, every subagent invocation, and the full output at each step.

1. Find the relevant session log in `.claude/logs/sessions/` (sorted by timestamp)
2. Open the `.md` file to review what happened in a readable format
3. Look for the point where things went wrong — you'll see the exact tool calls and their results
4. When filing an issue, include relevant excerpts from the log (redact any sensitive data first)

The `.jsonl` file contains the complete raw transcript if deeper inspection is needed.

### Q: Are session logs shared or uploaded anywhere?

<!-- NEW: Anticipated privacy question -->

Session logs are gitignored and stay on your local machine. They are never pushed to the repository.

---

## Technology Choices

<!-- MIGRATE: README FAQ "Technical" — Why Polars? Why Marimo? -->
<!-- NEW: Additional technology choice rationale -->

### Q: Why Polars instead of Pandas?

Polars offers better performance in general and a, in my opinion, much more legible and intuitive coding process that reduces ambiguity — important when AI is generating code.

### Q: Why Marimo instead of Jupyter?

Marimo notebooks are pure Python files (better for version control) and enforce cell dependencies (reducing hidden state bugs). This works far better for version control, and is far, far, far easier for an LLM assistant to edit without messing things up versus Jupyter.

### Q: Why Docker instead of a virtual environment?

<!-- NEW: Anticipated question about containerization choice -->

Isolation, reproducibility, and protection — why a container provides stronger guarantees than a virtualenv.

### Q: Why parquet for all data files?

<!-- NEW: Anticipated question about data format choice -->

Parquet's advantages for data analysis: columnar storage, type preservation, compression, and fast I/O with Polars.

### Q: Why are scripts the primary artifact instead of notebooks?

<!-- NEW: Anticipated question — this is a distinctive design choice -->

Reproducibility, auditability, and version control — scripts with embedded logs provide a stronger audit trail than notebook cells.

---

## Performance and Configuration

### Q: Which Claude model should I use?

<!-- CROSS-REF: 01_installation_and_quickstart.md "Select Your Model" — summarize here in Q&A format -->

Why Opus 4.5/4.6 is recommended and what to expect from other models.

### Q: How do I change the Claude model during a session?

<!-- CROSS-REF: 01_installation_and_quickstart.md "Select Your Model" -->

Using the `/model` command to switch models.

### Q: The analysis seems to be taking a very long time. Is that normal?

<!-- NEW: Anticipated question about analysis duration -->

What affects duration (data size, number of transformations, QA depth) and what's typical.

### Q: Can I allocate more resources to the Docker container?

<!-- NEW: Anticipated question about container resources -->

How to adjust Docker Desktop's resource allocation for better performance.

---

## Data Access Issues

<!-- NEW: Anticipated data-related troubleshooting -->

### Q: The assistant says data is unavailable or returns empty results

What this usually means (mirror issues, incorrect endpoint, data not yet available for requested years) and how to troubleshoot.

### Q: How current is the education data?

Publication lag varies by source — some sources have 1-2 year lags. How to check data availability for specific sources.

### Q: Can I use my own data files instead of the built-in sources?

<!-- NEW: Anticipated question about custom data -->

How custom data could be integrated and what the data-ingest agent can help with.

---

## Common Error Messages

<!-- NEW: Section for documenting common errors and their resolutions as they're discovered -->

### Q: "STOP: Suppression rate >50%"

What this means (too much data is suppressed for valid analysis) and what options you have.

### Q: "STOP: Cross-state assessment comparison"

<!-- MIGRATE: README "What Cannot Be Compared" (partial) -->

Why state assessments can never be compared across states and what alternatives exist.

### Q: The notebook won't render in my browser

How to verify the container is running, the port is mapped correctly, and the marimo command is correct.

---

## Next Steps

- **[Installation & Quick Start](01_installation_and_quickstart.md)** — If you're still setting up
- **[Best Practices](03_best_practices.md)** — Tips for effective use
- **[FAQ: Philosophy](07_faq_philosophy.md)** — Why DAAF works the way it does
