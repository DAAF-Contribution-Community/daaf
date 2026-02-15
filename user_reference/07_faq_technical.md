# 07. FAQ: Technical Support

Operational questions with concrete answers. If you're stuck, troubleshooting, or curious about a technical choice -- check here first.

[**Back to main**](../.)

---

## Table of Contents
- [**Setup and Settings**](#setup-and-settings)
- [**Session Logs and Diagnostics**](#session-logs-and-diagnostics)
- [**Technology Choices**](#technology-choices)
- [**Performance and Configuration**](#performance-and-configuration)
- [**Data Access Issues**](#data-access-issues)
- [**Common Error Messages**](#common-error-messages)
- [**Recommended Next Steps**](#recommended-next-steps)

---

## Setup and Settings

### Q: Can I run DAAF without Docker?

Technically yes, but I really don't recommend it, and it's not something I will support. Part of my installation process is, explicitly, me paternalistically enforcing some best practices and guardrails for the many people using DAAF likely to be new to AI assistants.

Docker does three important things for DAAF beyond just convenience:

1. **Isolation and safety.** The container runs as a non-root user and privilege escalation explicitly blocked. This means even if Claude Code tried to do something destructive, the operating system itself would prevent it. Running natively on your machine without these protections in place means Claude Code has whatever permissions *you* have -- which is probably a lot more than you'd want an AI assistant to have when they suffer from context rot and act extremely erratically.

2. **Reproducibility.** The Dockerfile pins every dependency -- Python 3.12, specific versions of Polars, plotnine, statsmodels, and everything else. When I say "this works," I mean it works with *that* exact stack. It also abstracts away issues with OS management (e.g., Windows versus Linux), and other extremely annoying variables that can affect how well or predictably software runs. Running natively means you're on your own for dependency management, and a surprising number of things can go wrong when library versions don't match. Python management has historically been a nightmare, and I am thoroughly shocked at how much Docker smooths over, which is time worth its weight in gold in my view.

3. **Clean slate recovery.** If something goes badly wrong inside the container, you can blow it away and rebuild from scratch in minutes with basically zero consequences to your actual machine. That's a really nice safety net when you're letting an AI write and execute code.

If you want to go this route: be my guest, but you'll need to figure it out on your own. I would firmly posit that anyone who's ready and qualified to do this independently **already** knows how to do it without my help.

---

### Q: Should I use an API key or a Max subscription?

I strongly recommend the **Max subscription** ($100/mo or $200/mo depending on tier). Here's why:

DAAF is extremely usage-intensive by design. It's doing a *lot* of work: deep-diving into data documentation, writing code, having another instance of Claude review that code line by line, writing plans, writing reports, and so on. All of that consumes tokens. With an API key, you pay per token, and a single full-pipeline analysis can easily burn through $50-100+ in API costs depending on the complexity. With a Max subscription, that same analysis is covered by your flat monthly rate.

From my own testing, I estimate I'd pay roughly **10x more** going with API billing versus my Max subscription. The Max plan is Anthropic explicitly subsidizing heavy usage like this -- take advantage of it.

The tradeoffs:

| Factor | API Key | Max Subscription |
|--------|---------|------------------|
| **Cost model** | Pay per token (uncapped) | Flat monthly ($100-200/mo) |
| **Cost predictability** | Variable, can spike | Fixed |
| **Usage limits** | Unlimited (as long as you pay) | Subject to usage limits within your plan tier |
| **Rate limiting** | Minimal | May hit rate limits during very heavy sessions |
| **Best for** | Light/occasional use, or organizational API budgets | Regular DAAF usage (recommended) |

One thing to note: the Max plan does have usage limits per time window. If you're running several DAAF analyses in parallel (which you absolutely can do!), you may occasionally hit a rate limit and need to wait a bit. The API key doesn't have that issue, but your wallet will feel it instead.

### Q: Which Claude model should I use?

**Use Opus 4.5 or Opus 4.6.** All development and testing was done on these models, and I genuinely don't think the others are up to the task.

The DAAF workflow is complex -- it involves multi-agent orchestration, following detailed multi-step protocols, making judgment calls about data quality, writing careful code, and then critically reviewing that same code from a different perspective. Sonnet and Haiku are capable models for many things, but they consistently produce erratic, inconsistent results with DAAF's workflow complexity. The instructions are simply too nuanced and layered for models that optimize for speed over depth.

Opus 4.6 also supports configurable "thinking levels" (you can toggle this in the `/model` selector by tapping the left/right arrow keys). I've done all my testing with the **"High"** thinking setting, and I strongly recommend the same. This is a case where quality matters far more than speed -- you want Claude to think carefully about your data, not rush through it.

That said, higher thinking levels do consume more of your usage allocation, so there's a legitimate tradeoff to explore. If you experiment with different thinking levels, I'd genuinely love to hear about your results -- please share back so we can update this guidance.

### Q: How do I change the Claude model during a session?

Type `/model` in the Claude Code chat window. You'll see a list of available models -- use the arrow keys to select one and press Enter. The change takes effect immediately for all subsequent interactions in that session.

You can also adjust the thinking level for Opus 4.6 by pressing the left and right arrow keys while Opus 4.6 is highlighted in the model selector.

### Q: Can I use DAAF with a different AI provider (OpenAI, Google, etc.)?

Not out of the box, but it's more portable than you might think.

DAAF is built on Claude Code, which is Anthropic's CLI agent tool. The vast majority of what DAAF actually *is* -- the agent protocols, skill documents, workflow definitions, validation checkpoints -- is just structured text in Markdown files. None of that is Anthropic-specific. What *is* specific to Claude Code are the hooks system (the safety guardrails that block dangerous commands, scan outputs for secrets, etc.) and some of the tool invocation patterns.

If you wanted to port DAAF to another agent harness (Gemini CLI, Codex, OpenCode, etc.), here's what would transfer immediately:
- All agent files (`agents/*.md`)
- All skill files (`.claude/skills/*/SKILL.md`)
- All reference documentation (`agent_reference/*.md`)
- The overall workflow design and validation philosophy

What would need adaptation:
- The hooks system (`.claude/hooks/`) -- these are shell scripts that hook into Claude Code's execution lifecycle
- The `.claude/settings.json` permission configuration
- Any Claude Code-specific invocation patterns (the `Task` tool, subagent types)

I would honestly be thrilled if someone forked DAAF and adapted it for another provider. The more researchers who have access to rigorous AI-assisted analysis tooling, the better. I'd also love to see someone test this with open-source models -- please reach out if you've got the capacity to explore that.

### Q: Is my data sent to Anthropic? What about privacy?

Your data does pass through Anthropic's API when Claude Code processes it -- that's how the AI works. However, a few important things to know:

1. **Nothing leaves your computer via the DAAF workflow itself.** DAAF's hooks and safety rails are designed to prevent Claude from uploading, exfiltrating, or sharing your data files themselves. You can verify this by reading the hook scripts in `.claude/hooks/`.

2. **Anthropic's data policies apply.** How Anthropic handles API data is governed by their privacy policy and terms of service. As of this writing, Anthropic states that API inputs and outputs are not used to train models, but you should verify their current policies yourself. This is a main reason why I focused on public datasets for DAAF out-of-the-box.

3. **The container provides additional isolation.** Because DAAF runs inside Docker with dropped capabilities and no privilege escalation, the blast radius of any unexpected behavior is contained (i.e., files it can accidentally upload to the internet, or send via email, or etc. etc.).

4. **DAAF enforces credential safety.** The framework actively prevents reading, writing, or committing files that look like credentials (`.env`, `*.pem`, `*.key`, etc.). It won't prevent everything, but it'll give you a good set of starting guardrails to help protect yourself.

**Bottom line:** If you're working with sensitive, proprietary, or regulated data, talk to your IT team and legal counsel before using DAAF or any AI tool with that data. DAAF provides strong *local* safety guarantees, but the data still transits through Anthropic's infrastructure for inference. Do not mess around here -- do your homework and be a good steward of your data.

---

### Q: Is there a free way to use DAAF?

Not in a practical sense for full-pipeline analyses, unfortunately. The free and Pro tiers of Claude simply don't provide enough usage for the volume of work DAAF demands. You might be able to do some lightweight Discovery Mode queries (asking what data is available, looking up variable definitions), but a full analysis pipeline will exhaust a lower-tier plan very quickly.

This is genuinely the biggest barrier to entry for DAAF, and I wish it were different. I hope that as model costs continue to decrease and open-source models become more capable, a more accessible option will emerge. If you have the capacity to test DAAF with open-source models or alternative providers, please reach out -- that's high on the list of things I'd love community help with.

---

## Session Logs and Diagnostics

### Q: Where are session logs stored?

Claude Code automatically archives a complete log of every session when it ends. These are stored locally in `.claude/logs/sessions/` in two formats:

| Format | File Pattern | Purpose |
|--------|-------------|---------|
| **Markdown** (`.md`) | `YYYY-MM-DD_HH-MM-SS_<session-id>.md` | Human-readable transcript with tool calls, timestamps, and token usage |
| **JSONL** (`.jsonl`) | `YYYY-MM-DD_HH-MM-SS_<session-id>.jsonl` | Raw machine-readable transcript (full API-level detail) |

Additionally, `.claude/logs/activity.log` records a timestamped entry every time a session starts, giving you a quick overview of usage history.

**These logs are gitignored by default** (they may contain sensitive content or API details), so they stay on your local machine and are never pushed to the repository.

### Q: How can I use session logs for debugging?

Session logs are invaluable when something goes wrong. The Markdown logs show you exactly what the assistant did, in order -- every tool call, every file read/write, every subagent invocation, and the full output at each step.

1. Find the relevant session log in `.claude/logs/sessions/` (sorted by timestamp)
2. Open the `.md` file to review what happened in a readable format
3. Look for the point where things went wrong -- you'll see the exact tool calls and their results
4. When filing an issue, include relevant excerpts from the log (redact any sensitive data first)

The `.jsonl` file contains the complete raw transcript if deeper inspection is needed.

### Q: Are session logs shared or uploaded anywhere?

No. Session logs are gitignored and stay entirely on your local machine (specifically, inside the Docker volume). They are never pushed to the repository, never uploaded to Anthropic, and never shared with anyone. If you choose to file a bug report and include log excerpts, that's your choice -- but the system never does this automatically.

### Q: What about the STATE.md file? How is that different from session logs?

They serve very different purposes:

**Session logs** are a complete, raw transcript of everything that happened in a Claude Code session. They're automatically generated, stored in `.claude/logs/`, and are primarily useful for debugging after the fact. Think of these as a security camera recording -- comprehensive but not curated.

**STATE.md** is a structured progress tracker that DAAF creates during full-pipeline analyses. It lives inside your project folder (`research/[project]/STATE.md`) and tracks what stage the analysis is at, which checkpoints have passed, what decisions were made, and what needs to happen next. Its primary purpose is enabling **session recovery** -- if your session runs out of context (the model's working memory fills up), you can start a fresh session and STATE.md tells the new session exactly where to pick up. Think of this as a bookmark with detailed notes.

---

## Technology Choices

### Q: Why Polars instead of Pandas?

A few reasons, and they're all about making AI-generated code more reliable.

**Clarity of intent.** Polars has a much more explicit code syntax. When you chain operations in Polars, what you're doing is unambiguous -- there's generally one obvious way to express a given transformation. Pandas, by contrast, has a lot of historical baggage and multiple ways to do the same thing (`.loc` vs `.iloc` vs `[]`, `apply` vs vectorized operations, etc.). When an AI is generating code, reducing ambiguity is extremely important because it reduces the surface area for subtle bugs. I just think it's way, way easier to skim and read.

**Better performance for the defaults.** Polars is faster than Pandas for most operations, especially on larger datasets, because it's built on Rust and uses lazy evaluation by default. This matters less for small datasets, but education data can get large -- millions of rows across years and states.

**Immutability.** Polars DataFrames are immutable by default -- operations return new DataFrames rather than modifying existing ones in place. This is a huge win for auditing and debugging AI-generated code, because you can always inspect the state before and after a transformation without worrying about hidden mutations.

**Type strictness.** Polars is stricter about types than Pandas, which means type-related bugs surface immediately rather than silently propagating through a pipeline.

That said, Pandas is still installed in the container and available if needed. Polars syntax is also very similar to R's tidyverse (intentionally so), which may feel familiar if you're coming from that ecosystem. I'd welcome new skills for the ecosystem to leverage Pandas and R just as robustly in the future!

### Q: Why Marimo instead of Jupyter?

This one's pretty straightforward: Jupyter notebooks and AI code editors are a terrible combination, and marimo solves nearly all the pain points.

**Version control.** Jupyter notebooks are JSON files with embedded outputs, base64-encoded images, and execution counts. They produce enormous, unreadable diffs in Git, and merge conflicts are essentially impossible to resolve by hand. Marimo notebooks are **plain Python files**. You can diff them, merge them, and read them in any text editor. For a project that's all about auditability and reproducibility, this matters enormously.

**Hidden state.** Jupyter's biggest footgun is that cells can be run out of order, creating hidden state that makes notebooks unreproducible. You can run cell 5, then cell 3, then cell 7, and get results that depend on that exact execution order -- but nothing in the notebook records that order. Marimo enforces a dependency graph between cells. If cell B uses a variable from cell A, marimo *knows* that and won't let you break that relationship. Run them in any order and you get the same result.

**AI editability.** Because marimo notebooks are plain Python, Claude can read and write them the same way it handles any other `.py` file. Editing a Jupyter `.ipynb` file requires manipulating JSON structure, cell metadata, kernel info, and output encodings -- it's fragile and error-prone for AI tools. Marimo is dramatically simpler and more reliable for this use case. Far, far, far easier.

### Q: Why Docker instead of a virtual environment?

A virtual environment (venv, conda, etc.) handles one thing well: Python package isolation. Docker handles that *plus* a whole lot more that matters for this project.

**Security isolation.** DAAF lets an AI agent write and execute arbitrary code on your behalf. That's inherently risky. Docker runs the entire environment as a non-root user with all Linux capabilities dropped and privilege escalation explicitly blocked. Even if Claude Code somehow tried to `rm -rf /` or `sudo` something malicious, the operating system kernel would stop it cold. A virtualenv gives you none of that -- Claude would run with your full user permissions.

**Complete reproducibility.** Docker pins *everything*: the OS (Debian Bookworm), Python version (3.12), system packages, Python libraries, and Claude Code itself. When I say DAAF works, I mean it works in that exact environment. Virtualenvs only manage Python packages, not system-level dependencies, OS differences, or tool versions.

**Clean recovery.** If something goes wrong -- a corrupted package, a broken state, whatever -- you can tear down the container and rebuild from scratch in minutes. Your data persists in the Docker volume, completely unaffected. Try doing that with a corrupted virtualenv.

**Cross-platform consistency.** Docker runs the same way on Mac, Windows, and Linux. No more "it works on my machine" problems.

### Q: Why parquet for all data files?

DAAF saves all data exclusively as parquet files, never CSV. Here's why:

**Type preservation.** CSV files have no concept of data types -- everything is text, and your analysis tool has to guess what each column is. Integers, floats, dates, booleans -- it's all just strings in a CSV. Parquet preserves exact types, so a column that's an integer stays an integer, a date stays a date, and you never get bitten by implicit type coercion bugs. When AI is generating data pipelines, removing this entire category of potential errors is a significant win.

**Compression.** Parquet uses columnar compression, so files are dramatically smaller than equivalent CSVs -- often 5-10x smaller. Education datasets can be large, and storage adds up.

**Speed.** Polars (and Pandas, for that matter) reads parquet files much faster than CSV files, especially for large datasets. Parquet also supports reading specific columns without loading the entire file, which is useful for exploration.

**Metadata.** Parquet files carry schema information -- column names, types, and nullability -- right in the file. No more guessing at encodings, delimiters, or quoting rules.

### Q: Why are scripts the primary artifact instead of notebooks?

This is one of DAAF's most distinctive design choices, and it's worth understanding the reasoning.

In most data science workflows, the notebook *is* the work product -- you write code in cells, run them interactively, and the notebook captures both the code and its output. DAAF flips this: **scripts are the primary artifact**, and the notebook is assembled *from* those scripts at the end.

**Reproducibility.** Each script is a self-contained, executable Python file that can be run independently from the command line. You don't need a notebook server, you don't need to run cells in a specific order, and there's no hidden state. Run the script, get the output. Every time.

**Audit trail.** Each script includes its own execution log appended as a comment block at the bottom -- the exact output from when it was run, including timestamps, row counts, and validation results. This means the evidence of what happened is embedded directly in the artifact, not in a separate log file you might lose track of.

**Version control.** When a script needs revision (say, the code-reviewer finds a bug), the original script is preserved and a new version is created (`_a.py`, `_b.py`). The full history of attempts and fixes is visible in the file system. The marimo notebook only includes the final successful version, but the intermediate attempts remain available for audit.

**Separation of execution from presentation.** The notebook's job in DAAF is to *present* the completed work in an interactive, explorable format -- not to *do* the work. This separation means the notebook can't accidentally introduce bugs or hidden state, because it's literally just displaying what the scripts already produced.

---

## Performance and Configuration

### Q: The analysis seems to be taking a very long time. Is that normal?

Probably, yes. A full-pipeline DAAF analysis is not a quick process, and that's by design.

Here's what's happening under the hood: DAAF breaks every analysis into 12 stages across 5 phases. For the data-heavy stages (5 through 8), *every single script* goes through an execute-then-review cycle -- Claude writes the code, runs it, then a separate instance of Claude reviews it line by line. If the reviewer finds issues, the script gets revised and re-reviewed. This happens for every fetch script, every cleaning script, every transformation script, every analysis script, and every visualization script. It's a lot of work, and it takes time.

**Typical timelines for a full-pipeline analysis:**

| Phase | What's happening | Typical duration |
|-------|-----------------|------------------|
| Phase 1 (Discovery) | Exploring data sources, deep-diving into documentation | 5-15 minutes |
| Phase 2 (Planning) | Creating the research plan, validating it | 20-30 minutes |
| Phase 3 (Data Acquisition) | Fetching data, cleaning it, QA on each script | 30-45 minutes |
| Phase 4 (Analysis) | Transformations, statistical analysis, visualizations, QA on each | 60-90 minutes |
| Phase 5 (Synthesis) | Assembling notebook, writing report, final review | 20-30 minutes |

So a typical full run can easily exceed **2-3 hours of Claude's active processing time**, plus the time you spend reviewing and confirming at phase boundaries (the Phase Status Updates where it pauses and waits for your input).

**What makes things slower:**
- More data sources (each needs its own fetch/clean/QA cycle)
- Complex joins across multiple datasets
- QA revisions (when the code-reviewer catches issues)
- Rate limiting (if you're on a Max subscription and hit your usage window)
- Network latency when fetching data from the Urban Institute portal

**When to worry:** If a single stage seems stuck for more than 20-30 minutes with no progress updates or seeming changes to the window, something may have gone wrong. Check whether Claude is waiting for your input (it pauses at phase boundaries). If it genuinely seems stuck, you can interrupt it with Ctrl+C and ask it to check its STATE.md and resume.

### Q: Can I allocate more resources to the Docker container?

Yes, but it's probably not necessary. DAAF's Docker container is running Claude Code (which talks to Anthropic's servers for the AI part) and Python scripts (which run locally for data processing). The AI inference isn't happening on your machine -- it happens on Anthropic's infrastructure. The local compute is just for running Python data operations.

That said, if you're working with very large datasets and the Python scripts themselves are running slowly, you can adjust Docker Desktop's resource allocation:

1. Open **Docker Desktop**
2. Go to **Settings** (gear icon)
3. Select **Resources**
4. Increase **CPUs** and **Memory** as needed

For most DAAF analyses, the defaults are fine. If you're working with datasets in the tens of millions of rows, bumping memory up to 4-8 GB may help. But honestly, if your data is that large, the bottleneck will be Anthropic's API response time, not local computation.

### Q: Can I run DAAF analyses in parallel?

Yes! Because each Claude Code session runs independently with its own context, you can absolutely open multiple terminal windows, each running their own Claude Code session inside the same Docker container, each working on different research questions simultaneously.

This is one of the exciting aspects of the workflow -- you can kick off an analysis on school enrollment trends, then open a new terminal and start a completely separate analysis on college graduation rates, and they'll run side by side without interfering with each other. Each project gets its own folder in `research/`, its own Plan, its own STATE.md, and its own set of scripts.

The practical constraint is your Anthropic usage allocation. Each parallel session consumes tokens independently, so running three analyses simultaneously will eat through your Max plan allocation roughly three times as fast. Plan accordingly.

---

## Data Access Issues

### Q: The assistant says data is unavailable or returns empty results

This usually means one of a few things:

**The data legitimately doesn't exist for your request.** Not every dataset covers every year, every state, or every variable combination. Education data has significant publication lags (see the next question), and some data collections simply don't include certain measures. DAAF should tell you what it looked for and why it came up empty.

**The data mirror is down or unreachable.** DAAF fetches data from the Urban Institute Education Data Portal's API. If the portal is experiencing downtime or maintenance, fetches will fail. You can check the portal's status at [educationdata.urban.org](https://educationdata.urban.org/). This is usually temporary -- wait and try again.

**The endpoint or filters are wrong.** Occasionally, the assistant may construct a query that doesn't quite match the API's expected parameters. If you suspect this, check the session logs to see the exact query that was attempted, and compare it against the [Education Data Portal documentation](https://educationdata.urban.org/documentation/).

**What you can do:**
1. Ask DAAF to try a broader query (fewer filters, wider year range) to see if any data is available at all
2. Use Discovery Mode to explore what data *is* available for your topic before committing to a full analysis
3. Check the Education Data Portal documentation directly to confirm the data you want actually exists
4. If the portal seems down, wait and try again later

### Q: How current is the education data?

Education data has significant publication lags that vary by source. This is not a DAAF limitation -- it's how federal education data works. Agencies need time to collect, clean, validate, and publish data, so the most recent available data is typically 1-3 years behind the current date.

Some rough guidelines as of this writing:

| Data Source | Typical Lag | Example |
|-------------|-------------|---------|
| CCD (K-12 schools) | 1-2 years | In 2026, most recent may be 2023-24 |
| IPEDS (colleges) | 1-2 years | In 2026, most recent may be 2023-24 |
| CRDC (civil rights) | 2-3 years | Less frequent collection cycles |
| Scorecard (outcomes) | 1-2 years | Some earnings data lags further |
| EdFacts (assessments) | 1-2 years | In 2026, most recent may be 2023-24 |

DAAF knows about these lags -- during the Discovery phase (Stage 2), it will check what years are actually available for each data source before proposing an analysis plan. If you ask for data from the current year, it should proactively tell you that data isn't available yet and suggest the most recent available years instead.

### Q: Can I use my own data files instead of the built-in sources?

Yes, and DAAF has a built-in tool for exactly this -- the **data-ingest agent**.

The data-ingest agent helps you profile a new dataset and create the documentation artifacts (a "skill") that DAAF's other agents need to work with your data effectively. This includes cataloging variables, documenting types and distributions, identifying potential data quality issues, and creating the structured metadata that DAAF uses during analysis.

See [**04. Extending DAAF**](04_extending_daaf.md) for detailed guidance on this process.

**Important caveat:** If you're working with proprietary, sensitive, or regulated data, make sure you've done your due diligence on data governance *before* feeding it to any AI tool. Your data transits through Anthropic's infrastructure for inference. Talk to your IT and legal teams first. I cannot stress this enough.

---

## Common Error Messages

### Q: "STOP: Suppression rate >50%"

This means more than half of the data values in a critical column are suppressed (hidden/masked). Education data is frequently suppressed to protect student privacy -- for example, if a school has fewer than a certain number of students in a demographic group, the data for that group is replaced with a suppression code rather than the actual value.

When more than 50% of your data is suppressed, any statistical analysis on the remaining data would be unreliable at best and misleading at worst. DAAF is being cautious and responsible here by stopping rather than producing garbage results.

**What you can do:**
- **Broaden your scope.** Suppression is more common at granular levels (individual schools) than at aggregate levels (districts, states). Try analyzing at a higher aggregation level.
- **Reduce demographic disaggregation.** Suppression rates increase dramatically when you slice data into small subgroups. Broader demographic categories may have less suppression.
- **Try a different year or time range.** Some years have better coverage than others.
- **Accept the limitation and document it.** Sometimes the data simply isn't there for the analysis you want to do -- that's a genuine finding, not a failure.

### Q: The notebook won't render in my browser

If you've run the `marimo run` command but can't see anything at `http://localhost:2718`, check these things in order:

1. **Is the container running?** Check Docker Desktop's Containers panel. The `daaf` container should show as running.

2. **Did you include the right flags?** The command needs `--host 0.0.0.0 --port 2718 --headless` for Docker. The full command should look like:
   ```bash
   marimo run 'research/[your-project]/[notebook-name].py' --host 0.0.0.0 --port 2718 --headless
   ```

3. **Is the port mapped correctly?** Check your `docker-compose.yml` -- the line `"2718:2718"` under `ports:` maps the container's port to your host machine. If you changed this, use the host-side port in your browser.

4. **Is something else using port 2718?** See the port conflict question above.

5. **Try a different browser or incognito/private window.** Occasionally, browser extensions or cached state can interfere.

6. **Check for errors in the terminal.** If marimo itself hit an error (e.g., a missing dependency or a syntax error in the notebook), the error will appear in the terminal where you ran the `marimo run` command.

### Q: "Context utilization CRITICAL" and the session seems to stop

This isn't an error -- it's DAAF being responsible about Claude's working memory.

Claude has a finite context window (roughly 200K tokens). As a session progresses and Claude processes more information, that window fills up. DAAF monitors this continuously and has defined thresholds:

| Utilization | Status | What happens |
|-------------|--------|-------------|
| <40% | NOMINAL | Normal operations |
| 40-60% | ELEVATED | Works normally but starts delegating more to subagents |
| 60-75% | HIGH | Finishes current work, prepares for session restart |
| >75% | CRITICAL | Stops new work, asks you to restart the session |

When you see CRITICAL, it means Claude's context window is nearly full and continuing would degrade the quality of its work. This is by design -- DAAF would rather stop and restart cleanly than continue with increasingly unreliable output.

**What to do:**
1. Claude should have already updated STATE.md with your current progress and provided a restart prompt
2. Copy the restart prompt it gives you
3. Type `/clear` to reset the session (this clears Claude's context but keeps all files intact)
4. Paste the restart prompt into the fresh session
5. Claude will read STATE.md and resume exactly where it left off, with a full fresh context window

This process is seamless when it works well -- the session state system was designed specifically for this scenario. Think of it like saving your game before the battery dies.

### Q: Claude seems to have forgotten earlier instructions or decisions

This is a symptom of **context degradation** -- Claude's working memory is getting full, and earlier information is effectively being crowded out by newer content. It doesn't mean the information is literally gone, but Claude's ability to attend to it decreases as the context fills up.

DAAF has several mechanisms to handle this:

1. **Context monitoring** catches this proactively. The system should flag elevated utilization before it gets this bad.
2. **STATE.md** records all key decisions, so even if Claude "forgets," the information is retrievable from the file.
3. **The Plan document** serves as persistent memory for methodology decisions.
4. **Session restart** via Protocol 6 gives Claude a completely fresh context window while preserving all progress.

If you notice Claude asking questions it already asked, or making decisions that contradict earlier ones, the best course of action is to prompt it to check its STATE.md and Plan, or to restart the session with `/clear` and the restart prompt.

---

## Recommended Next Steps

- [**00. README**](../.) — Vision and purpose, project goals, what DAAF does and does not do, core design philosophy, acknowledgments
- [**01. Installation & Quick Start**](01_installation_and_quickstart.md) — Get started! Installation prerequisites, step-by-step 5-minute setup, day-to-day usage, and troubleshooting
- [**Back to main**](../.)
