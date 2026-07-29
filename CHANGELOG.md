# Changelog

All notable changes to DAAF for each release version are documented here, in reverse chronological order.

## Table of Contents

- [v3.0.1 -- 2026-07-29](#v301--2026-07-29)
- [v3.0.0 -- 2026-07-17](#v300--2026-07-17)
- [v2.1.0 -- 2026-05-02](#v210--2026-05-02)
- [v2.0.1 -- 2026-04-05](#v201--2026-04-05)
- [v2.0.0 -- 2026-03-31](#v200--2026-03-31)
- [v1.0.0 -- 2026-02-22](#v100--2026-02-22)

---

## v3.0.1 -- 2026-07-29

### Data Analyst Augmentation Framework -- Stability and Polish

v3.0.1 is a simple patch release: no flashy new functionality to be aware of, just steady work making v3.0.0's foundations more solid and adding a handful of genuinely useful conveniences on top. Most of it is under-the-hood hardening -- backups that fail loudly instead of quietly, lifecycle scripts that handle more edge cases, and OpenAI provider routing that's steadier and easier to sign into -- alongside a few new opt-in features worth knowing about: read-only host-folder mounts (give DAAF access to an actual folder on your computer!), setting up a shared research workspace across separate DAAF installs, and speed controls for the GPT provider route.

One practical note for existing users: updating will prompt a rebuild (the updater detects the Dockerfile change and offers it to you) -- accept it and you're done.

### Detailed Notes

Disclosure: These notes were AI-drafted from a verified inventory of the release's commits and then reviewed by hand -- they're kept concise for a patch release, but they capture what actually changed.

#### Provider Shim Improvements

The provider shim (the local adapter that lets DAAF run on your OpenAI or ChatGPT account) advanced to **v1.3.9**, with the work concentrated in making it smoother for operating with daily use:

- **Multimodal handling** so image-bearing requests translate cleanly through the shim (e.g., for data visualization design work).
- **GPT Fast / GPT Priority speed controls** -- a new operator command, `bash /daaf/scripts/provider_shim/gpt_fast.sh {on|off|status}`, lets you opt into faster priority service on the GPT route, turn it back off, and check the current state at a glance.
- **Better logging and diagnostics** for when something needs troubleshooting.
- **Steadier stability and sign-in.** ChatGPT-lane authentication is now handled by the bundled `codex` CLI, which makes signing in more reliable, and your ChatGPT plan-usage quota is now surfaced right in the status bar.

#### Link Host Folders and Share a Workspace Across Installs

Two new opt-in conveniences for people whose data or workflows don't fit neatly inside a single Docker container management system:

- **Read-only host-folder mounts.** You can now expose a folder from your own machine to DAAF as a read-only `/host_data` mount -- handy for large local datasets you'd rather not copy in by hand. It's read-only by design, so DAAF can draw from it but never writes back (or corrupts data!); the usual reproducibility conventions still ask you to copy anything you actually use into the project itself, but feel free to override as you see fit.
- **A shared research workspace.** A new `DAAF_DATA_VOLUME_NAME` setting lets two installs point at the same research volume, so you can (for example) run one body of work across two differently-configured containers (pit Claude models against GPT models, for example!).

#### Analytics Stack: pyfixest 0.60

The Python fixed-effects library `pyfixest` moved from 0.40 to **0.60**. The old 0.40 wheel shipped broken dependency metadata; 0.60 is clean and current. The corresponding skill got a full refresh so agents work against the real 0.60 API rather than a stale mental model, a now-incorrect cross-skill note (about `feglm` fixed-effects support) was corrected in the same sweep, and new smoke tests guard the analytical stack against silent breakage on future rebuilds.

#### Safer Housekeeping

A cluster of quiet reliability fixes across the host tooling and the safety system:

- **DAAF File Backups fail loudly, not silently.** If a copy is corroborated as truncated, the backup now reports a hard failure instead of a false success.
- **Hardened lifecycle scripts.** Parsing, rounding, and environment handling were tightened on both the Bash and PowerShell sides, closing a class of platform-specific edge cases.
- **Broader write-protection** for session logs and audit trails, keeping the record tamper-resistant.
- **Effort level is now an overridable default** rather than a hard pin, so the `/effort` command works as expected.

#### Status Bar and Context Monitoring

The status bar now surfaces your Codex plan-usage quota if you're using that route, and both its rendering and the underlying model detection were hardened so the display stays accurate across a wider range of setups.

#### For Contributors

A couple of contributor-facing improvements. DAAFBench -- DAAF's model-behavior benchmark harness -- got reliability work and scoring-validity corrections. In the interest of transparency: one scoring correction was significant enough that I rescored the archived results in place, and previously published GPT dispatch-compliance numbers rose as a result (from roughly 49% to 74%). On the testing side, the provider shim gained a dedicated CI suite (184 offline tests), and the Bash/PowerShell test coverage expanded further.

**Full Changelog**: [v3.0.0...v3.0.1](https://github.com/DAAF-Contribution-Community/daaf/compare/v3.0.0...v3.0.1)
<!-- AT TAG TIME: verify tag exists and this compare link resolves -->

---

## v3.0.0 -- 2026-07-17

### Data Analyst Augmentation Framework -- Opening Doors

If v1.0.0 was about proving the concept of DAAF, v2.0.0 (*Gaining Altitude*) about rebuilding DAAF’s core framework engine for far greater flexibility and robustness, and v2.1.0 (*The Frictionless Update*) was about making it genuinely easy to install and run, then v3.0.0 is about something more fundamental to the mission of DAAF: *who gets to use DAAF at all.* This is an update designed to better meet researchers where they are. Every earlier version was geared towards a particular kind of user: someone who's comfortable enough in Python, who has an Anthropic subscription/API budget to spend, whose data is non-proprietary and/or public enough to be safe to share with AI assistants, and who just wants to run a single project on a single machine. Each of those assumptions was a barrier to entry and a limitation of what DAAF could offer to researchers across the sciences.

v3.0.0 takes almost all of these most impactful walls down, and I'm hoping that if you're reading this, you'll find DAAF is now for **you**. 

- The **language wall** falls as R becomes a first-class execution lane: enormous for social science, education research, epidemiology, and policy analysis, where R is often the native tongue. (Coming from Stata? Tell DAAF and it’ll translate any R or Python code it writes for you in the comments!)
- The **provider and cost wall** falls because DAAF can now run AI models from all major contenders: use an Anthropic API key or Claude subscription, use an OpenRouter account and API key (for any and all models available, inclusive of Claude/OpenAI/open-source), and/or use an OpenAI API key or ChatGPT subscription. Claude Code remains the driver of the system, but it can now "speak" with pretty much any service you have access to (which is especially valuable and timely given the currently intense cost-competition happening across the industry!).
- The **sensitive data wall** gets softened for researchers whose data can never leave a secure environment (HIPAA- or FERPA-governed, enclave-bound, or otherwise restricted): DAAF now comes bundled with a privacy-preserving synthetic-data generation and analysis workflow. In other words, DAAF helps you summarize/profile an existing dataset with a helper script from afar (with as much or as little detail as you can provide under your data protection agreements) and then uses the summary statistical output to construct a fully synthetic "twin" dataset it can operate on and analyze to help you rapidly prototype code *without ever exposing it to your real data.*
- The **operations wall** falls with a consolidated and much more user-friendly DAAF Control Panel interface on every operating system (no more remembering "run_daaf.sh" or "backup_daaf.sh" -- it's just "daaf.sh" for everything now!), more advanced configuration options for any type of setup, a self-healing updater, better and more sophisticated backup processes, and security hardening throughout. I've updated the Claude Code version in the container, bringing a ton of nice quality-of-life updates there (much better subagent viewability) plus access to Fable, and do a better job of saving your Claude Code configurations (so rebuilding is now truly painless! No more logging in over and over).
- And the **scale wall** falls as DAAF can now support installing arbitrarily many versions of DAAF with different configurations, environments, and setups: run multiple projects side by side, each in its own container, on its own provider or endpoint, even its own DAAF version. For example, I now have my Anthropic subscription working with Claude in one container, while my OpenAI subscription works with GPT-5.6 Sol in another container! Advanced users can even point them to the same research work and have them duke it out.

All of this comes while actually *enhancing the safety guardrails in the same sweep*. This release expands DAAF's defense-in-depth safety guards, adds more pre-flight system checks, hardens and enhances the development environment experience and workflow for contributors, fixes several research-integrity gaps, and is backed by extensive model-performance testing through our new [DAAFBench analyses](https://daaf.openaugments.org/bench).

Everything about DAAF is free and open-source, and always will be. The goal with today's update is to make DAAF accessible and relevant to more researchers, in more circumstances, as carefully and responsibly as ever.

**New to DAAF? Start with the new Getting Started video.** To go with this release, I've recorded a full tutorial and walkthrough: **[Claude Code for Social Scientists: Get Started with DAAF in 30 Minutes](https://youtu.be/BPlR9bXZxnY)**. It takes you through the entire installation process and gets you oriented to the whole environment: the Docker setup, Claude Code, and DAAF itself, plus the everyday essentials like managing files in the browser editor, using the session log viewer, and keeping your installation up to date.

I've worked really hard to get all of these various systems up and running and robust enough for daily use. That being said, everything requires testing and feedback from users to improve so I know how things go under real-world conditions! Whether you’re one of the ~2,000 unique installers of DAAF so far or just getting started today, I’d love to hear from you!! If you have any feedback, ideas, suggestions, or just want to let me know how it’s going, I’d love to hear from you at our [Discord community](https://discord.gg/7FWTnZJDqy) or at [support@openaugments.org](mailto:support@openaugments.org).

### Important Notes for Existing Users

If you're coming from an existing installation, v3.0.0 is a larger release than its recent predecessors, and a few things will need your attention to update smoothly.

- **Back up your work.** For those coming from v2.1.0 (anyone who has the update_daaf.sh/ps1 script), the updater automatically asks you to back up your work. You should do this just in case! Otherwise, download your /research folder from the Docker Volume just in case for safe keeping. I've developed some really careful systems to not do anything harmful while updating, but better safe than sorry.
- **Run your updater TWICE.** Because of a limitation in the older updater, you'll just need to run your updater script twice in a row. The **first run** applies most everything, as well as some helpful updates to the updater itself. The **second run** uses the freshly upgraded updater to deliver the new daaf.sh/daaf.ps1 control panel for you to start using instead of the older helper scripts (keep them there! daaf.sh/ps1 uses them behind the scenes). If everything is already current, it simply reports "Already up to date!", and it is always safe to re-run. 
- If coming from a **pre-v2.1.0** installation (any install without the built-in `update_daaf` script in your installation folder), use the `migrate_daaf` path instead: see the [migration guide in the Installation and Quickstart guide](user_reference/01_installation_and_quickstart.md#migrating-from-an-older-installation).
- When you've started it up again, **confirm your execution language.** Python remains the default, set in CLAUDE.md for all agents to respect, but R is now a fully supported alternative. If you want to change the default, just ask Claude. You can also set it on a per-project basis; just let Claude know when you start a project or revisit an older project.
- **New safety/reproducibility/auditability rules your custom scripts and workflows must respect.** A handful of constraints are now enforced to protect reproducibility and the core audit trail: runtime package installs are blocked for **both Python and R** (ask Claude to instead add packages to the Dockerfile's user-additions block and rebuild) to ensure actual reproducibility and portability; scratch and intermediate files must be written inside the project folder, never in the Docker container's ephemeral `/tmp` (so you can keep them in the Docker Volume and via backups, otherwise they just disappear on rebuild!); shell commands must run one per call (no `&&`, `;`, or `||` chaining); and agents no longer make git commits by default. That last item is a new opt-in **"Git commit management"** preference — leave it off and every script version is still preserved in the working tree as your complete audit trail; turn it on and DAAF may offer commits at natural milestones for you to approve.
- **Running more than one instance.** You can now run as many distinct installs of DAAF as you'd like! You'll need to set up some command line arguments before installing to do so: Give each simultaneous instance a distinct `DAAF_PROJECT_NAME` and non-conflicting `DAAF_PORT_*` values in its `environment_settings.txt` so their containers and browser ports don't collide. See the Advanced Configuration section of the [Installation and Quickstart guide](user_reference/01_installation_and_quickstart.md#advanced-installation--configuration).

If you run into any issues, please don't hesitate to create a GitHub Issue, reach us on our [Discord community](https://discord.gg/7FWTnZJDqy), or email [support@openaugments.org](mailto:support@openaugments.org).

### Detailed Notes

Disclosure: Headline info above was initially drafted by Fable and then edited carefully by hand. Detailed notes below are all Fable but capture the right info!

#### First-Class R Support

DAAF now treats your execution language as a first-class choice. Pick R — at first run or any time — and the entire pipeline follows: code-producing agents write `.R` scripts instead of `.py`, load R libraries instead of their Python counterparts, and assemble **Quarto** notebooks instead of Marimo. Python remains the default and is unchanged; nothing about existing Python work is disturbed.

Under the hood, this is a routing architecture rather than one skill pretending to know every library. The `data-scientist` methodology skill picks the right *method* for your question, then routes to a language-specific library skill for the implementation. v3.0.0 adds **18 new skills (growing the catalog from 36 to 54)**, most of them the R analytic stack: `tidyverse` (data manipulation), `ggplot2` (graphics), `fixest` and `plm` (fixed-effects and panel models), `r-stats` (regression, GLMs, time series), `survey-r` (complex surveys), `sf-terra` (spatial), `tidymodels` (machine learning), `igraph-r` (networks), `gt` (tables), `plotly-r` (interactive graphics), and `quarto` (notebooks). Python's side grew too, with `great-tables` (publication-quality tables) and `igraph` (network analysis). Rounding out the eighteen: `python-r-translation` and `stata-r-translation` for readers coming from other languages, and the `synthetic-data-workflow` and `daaf-deploy-smoke-testing` skills described elsewhere in these notes. Method-to-library routing now happens by execution language, so "use a fixed-effects model" resolves to `fixest` in R and `pyfixest` in Python automatically. R scripts are held to the same **file-first execution** discipline as Python (direct `Rscript` calls are blocked in coding agents in favor of the audited capture wrapper), and the image ships R **smoke tests** covering the analytical stack.

The R lane reaches DAAF's bundled data expertise, too. All 15 existing data-source skills — the federal education catalog (CCD, IPEDS, CRDC, College Scorecard, EDFacts, SAIPE, and more) plus county-level presidential election returns — gained R-oriented access and filtering examples alongside strengthened source-specific safeguards: coded-value and suppression handling, coverage and selection limits, reporting lags, and historical-change cautions stay attached to the code that needs them. Each source skill also makes its verification hierarchy explicit — trust the actual data first, the source's live codebook second, and the skill's summary third — so an agent that hits a discrepancy investigates instead of assuming its own documentation is right. To be clear about scope: no new data sources were added in this release; this is the same catalog, made more careful and more bilingual.

**R is engineered for parity.** Every method family routes to an R equivalent, notebooks compile to Quarto, and — new in this release — reproducibility verification enforces *synchronized, fail-closed parity contracts for both languages* (see *Reproducibility Verification Hardening* below). Our standing position: **if you find a workflow that works in Python but not R, we treat that as a bug — please report it.**

That said, parity is a goal we hold ourselves to, not a blanket guarantee, and a few asymmetries are worth knowing about:

- **One intentional difference:** under the new UTF-8 locale, base R's `sort()` and `order()` use ICU dictionary-style collation rather than raw byte order (see the *R Unicode (UTF-8) Handling Fix* section below). This is the correct, standard behavior; it is called out so a re-ordered result doesn't surprise you.
- **Causal-inference reference code is currently Python-oriented** (matching/IPW/AIPW, synthetic control, causal ML/DML/CATE, Heckman selection, mediation). R users are routed to `fixest`/`plm`/`r-stats` plus the R library skills; the identification logic is identical, but the worked examples are Python-first. Worth checking for your workflow.
- **A couple of methods are Python-only today:** the DBSCAN and HDBSCAN density-clustering algorithms, and complete point-pattern spatial modeling in R is not claimed. If one of these is central to your study, confirm the route before committing.
- **Regression-table tooling differs by design:** R has a `modelsummary` pathway alongside `gt`; Python's `great-tables` handles formatted data tables and points regression output to the estimator's own tables (e.g., `pyfixest`'s `etable()`). Plan cross-language reports with that in mind.

Bayesian modeling, survival analysis, and deep learning remain outside DAAF's current skill coverage in either language — escalate rather than assume a route exists.

One more thing that makes the whole system friendlier: **if you read code most comfortably in another language, just say so.** Whether you're a Stata user working in Python, a Python user working in R, or an R user working in Python, DAAF can add inline translational comments in your home language via its translation skills — set once as a persistent preference and applied automatically from then on.

#### Runtime Modernization: Ubuntu Noble, R 4.5.3, and Quarto

To carry the R toolchain, the container moved to a modern **Ubuntu 24.04 "Noble"** base image with system Python 3.12, **R 4.5.3**, and a pinned **Quarto** install, on freshly organized and pinned package layers. R packages install from prebuilt binaries on both Intel and Apple Silicon, so the framework's R stack no longer compiles from source on Macs. Because this is a base-image change, **an image rebuild is required** before you rely on v3.0.0 — when you update, the updater detects the Docker-file changes and offers to run the rebuild for you (you can also run `rebuild_daaf` yourself any time). Adding your own packages still goes through the Dockerfile's user-additions block followed by a rebuild, which keeps the environment reproducible.

#### Provider Routes: Run DAAF on Your Own Account

DAAF no longer assumes one way to reach a model. You can run it on:

- **Anthropic** — your Claude subscription (interactive login or OAuth token) or a direct `ANTHROPIC_API_KEY`. This is the **supported** baseline route.
- **OpenRouter** — point DAAF at OpenRouter for broader model and provider flexibility, configured entirely through `environment_settings.txt`.
- **OpenAI API via DAAF's provider shim** — a local adapter translates between Claude Code and an OpenAI backend, so an `OPENAI_API_KEY` can drive DAAF.
- **Your existing ChatGPT subscription** — the same shim, in its ChatGPT/Codex mode, lets a ChatGPT subscription power DAAF. This route has a lower backend context ceiling (~370k tokens, measured) than the API routes. You'll authenticate with the bundled Codex program in the background (using its CLI).

The three newer routes (OpenAI API, OpenRouter, ChatGPT-subscription) are **supported pathways under active, extensive testing** — they work, and we want your reports as more people use them. Model-name remapping environment variables let you map DAAF's model tiers onto whatever your provider offers, and context-window detection now queries each route for the real context length of the model you're actually running (the ChatGPT lane instead applies its measured backend ceiling), so DAAF's context-management math stays honest across providers.

#### The DAAF Control Panel: One Front Door for Everything

Day-to-day operations used to mean remembering half a dozen helper scripts (`run_daaf`, `backup_daaf`, `view_logs`, ...). Those scripts still exist — but you no longer need to think about them. A single menu-driven **Control Panel** (`daaf.sh` on macOS/Linux, `daaf.ps1` on Windows) is now the one front door: launch Claude Code, browse and edit files in the browser VS Code, inspect session logs, open Python (Marimo) or R (Quarto) notebooks, or drop into a container shell — plus backup, restore, update, and rebuild — all from one numbered menu. The panel also shows a live services dashboard that checks whether each browser service (notebooks, session logs, editor) is *actually listening* right now, not just configured to exist, so "is it running?" has a real answer at a glance.

Both panels are first-class citizens on their platform. The Windows panel is native PowerShell (compatible back to Windows PowerShell 5.1) rather than a Bash-shaped experience through a compatibility layer, and it takes real care with interactive sessions so Claude Code and container shells behave properly when launched from a menu. The macOS/Linux panel runs on the stock Bash 3.2 that ships with every Mac — no newer Bash required. And both are multi-instance aware: they read your instance's project name and ports, so the panel always talks to *its own* containers and services.

#### Self-Healing Updater and Drift Healing

The `update_daaf` script continues to get more resilient:

- **Self-healing sync:** Host tool files that a previous update missed (for example, because they were added in a release you skipped over) are now delivered automatically on the next run, even when there is nothing new to pull.
- **Drift healing:** If a host script on your machine differs from the repository version and was not part of this update, the updater now heals it automatically: your existing copy is first saved alongside it as `<name>.pre-update`, then the file is updated to the repository version. Host tool scripts have no supported local-edit use case -- all of your configuration lives in `environment_settings.txt`, which the updater never syncs or touches -- so a differing host script means staleness, not customization. If the backup cannot be written, the file is **never overwritten**; the updater instead warns you by name and prints the exact command to adopt the repository version manually. The closing summary explains which files were healed and how to restore any of them by renaming its `.pre-update` copy back.
- **Clearer conflict guidance:** When re-applying your local Dockerfile / docker-compose customizations conflicts with an update, the message now explains plainly what happened, reassures you that your changes are safe in a git stash, and points you to DAAF's User Support mode for a guided walkthrough.

Underneath all of the host tooling, every host-facing script is now held to strict plain-ASCII text, enforced by an automated lint gate — quietly ending a class of character-encoding corruption that could break these scripts on some Windows and macOS terminal configurations.

#### Smarter, Safer Backups and Restore

The backup and restore pathway grew up in this release, because copying a Docker volume across platforms is deceptively tricky:

- **Backups verify themselves.** Before copying, the backup checks that your disk has room (with a buffer to spare). Afterwards, it doesn't just trust the copy command's exit code — it compares file counts and byte totals between the source and the backup and warns you about any meaningful discrepancy.
- **Windows backups no longer silently truncate.** Symlinks inside the volume could abort a Windows-side copy partway through and quietly drop everything after them. Backups now stage the data in a helper container, record symlinks in a manifest, and stream a symlink-free tree to your host — the links are replayed faithfully on restore. A companion permissions manifest means a Windows round trip no longer scrambles which files are executable.
- **Your Claude sign-in and session history are backed up too.** Alongside the research data, backups capture the persistent Claude state volume (described under *Keeping Pace with Claude Code* below), so a restored machine picks up with your login and session history intact. Because of that, **a backup folder is sensitive** — the backup finishes with an explicit warning to store it privately and never attach it to tickets, repositories, or shared drives.
- **Restore is deliberately explicit.** Restoring shows you exactly what will be overwritten and requires typing `RESTORE` to proceed — and if something fails partway, it tells you plainly what state your volumes are in rather than pretending success.

#### Multi-Instance Support

You can now run more than one DAAF instance on the same machine without them colliding. New `DAAF_PROJECT_NAME` and `DAAF_PORT_*` settings in `environment_settings.txt` let each instance use its own container name and its own published host ports (Marimo, log viewer, VS Code). The container name is derived from your compose project rather than hardcoded, so the helper scripts target the right container automatically.

#### Environment Settings: Seeded Automatically, Handled Safely

All of your configuration lives in one place — `environment_settings.txt` in your installation folder — and v3.0.0 makes that file much easier to live with. The installer now creates it for you from the annotated template and carries forward any setup values you provided at install time (a custom project name, ports, and so on), so a customized installation keeps its identity across future launches and updates; an existing settings file is never overwritten. On the host side, the lifecycle scripts read only a small allowlist of instance keys from the file and never execute it as code — a deliberate safety choice, because the same file holds your API keys. And when a script does need to persist a setting on your behalf, it writes carefully: your comments and structure are preserved, and it tells you exactly what it changed.

The browser code editor now ships with a tenth extension, [vscode-archive](https://open-vsx.org/extension/YuTengjing/vscode-archive), which adds a right-click **Compress** menu in the file explorer. This closes a long-standing gap: the editor's built-in "Download..." action only handles whole folders in Chrome and Edge (and even there copies files one by one rather than producing an archive). Now, in any browser, you can right-click a folder, compress it to a single `.zip`, and download that — making it much easier to get your research files out of the container. The Installation and Quickstart guide has a new walkthrough of getting files into and out of the container, and the technical FAQ has a new entry on downloading whole folders.

#### Privacy-Preserving Synthetic Data Workflow

DAAF can now help you work with data that **can't leave your secure environment** -- sensitive, proprietary, PII-bearing, HIPAA/FERPA-governed, or enclave-bound data that shouldn't enter the container at all. A new `synthetic-data-workflow` skill adds a privacy-preserving path to Data Onboarding: at the start of onboarding, a **sensitivity gate** asks directly whether your data is safe to bring in. If it isn't, DAAF hands you a self-contained, disclosure-controlled profiling script that you run locally, wherever the data lives. Only a summary profile report crosses the boundary -- you review every number in it first -- and DAAF builds a realistically-shaped **synthetic** dataset and a data source skill from that report alone. You develop and debug your entire analysis against the synthetic stand-in, then run the finished, vetted code against the real data yourself to get the actual results. The synthetic data is a code-development scaffold, not an analytic substitute, and every synthetic-derived skill and report says so. Your data-governance, disclosure-review, and legal obligations remain your own to meet — the workflow reduces exposure; it doesn't adjudicate it. A four-tier disclosure ladder (schema, marginals, relationships, and full local high-fidelity synthesis) lets you share only as much as your work truly requires. See the new technical-FAQ entry, "Can I use DAAF with data that can't leave my secure environment?"

To power the in-container generation step, the framework image now includes `simstudy` and `fabricatr` (R) and `faker` (Python) as core, presence-gated packages, with matching smoke tests (`scripts/smoke_tests/smoke_synthetic_data_workflow.R`/`.py`). Tier 4 synthesis tools (`synthpop`, `sdv`) are deliberately excluded from the image -- that tier runs on your own machine, never in the container.

#### R Unicode (UTF-8) Handling Fix

DAAF's container previously shipped with no locale configured, which left R running under the bare POSIX/C locale. Python is immune to this -- it quietly coerces itself to UTF-8 at startup -- but R has no equivalent mechanism, so it would **silently corrupt non-ASCII (UTF-8) text**: reading a Unicode-containing YAML config could return nothing at all (a NULL with only a warning), and accented or non-Latin characters in data or scripts could come back byte-mangled. This release fixes the root cause by setting the image locale to `C.UTF-8` (via `LANG`/`LC_ALL`), so R handles Unicode correctly out of the box. `C.UTF-8` was chosen deliberately over a full locale like `en_US.UTF-8` because it ships in the base image with no extra packages and leaves number and date formatting untouched -- it keeps `.` as the decimal separator and English diagnostic messages. As defense-in-depth, the education-data-query skill's R fetch pattern now also self-heals the locale at runtime for anyone still on an older image, and a new zero-cost check in the deployment smoke suite asserts R's locale is correct after any rebuild.

**One intentional behavior change to be aware of:** under a UTF-8 locale, base R's `sort()` and `order()` switch from raw byte order to ICU dictionary-style collation, so alphabetical sorts that mix upper/lower case or accented characters may order slightly differently than before. This is the correct, standard behavior and affects only base-R sorting -- `dplyr::arrange()` and the shell `sort` command are locale-independent and unaffected. An image rebuild is required for the fix to take effect.

#### Safety and Execution Boundaries

Every new door in this release comes with a matching guardrail, because the whole point of DAAF is that its output is *worth reviewing* — and that depends on the container staying in a known, reproducible state. v3.0.0 strengthens several protections, all aimed at the same thing: making it hard to accidentally knock the container out of that state.

- **No surprise package installs — now in R too.** Installing packages at runtime is blocked for both Python and R, at two layers: a check on shell commands and a scan of script contents (so an `install.packages()` buried inside an R script is caught before it runs). Packages belong in the Dockerfile so that a rebuild reproduces your environment exactly.
- **Scratch files stay inside the project.** Writing working files to `/tmp` is blocked, because `/tmp` sits outside DAAF's backup and audit boundary; intermediate files live in the project where they're preserved and reviewable.
- **One command per shell call.** Chaining commands with `&&`, `;`, or `||` is blocked so each action stays individually visible to the safety and permission layers.
- **Dispatch guardrails.** Requests for remote or worktree `isolation` are stripped from subagent dispatches (neither works in the container), and a subagent can't request a more expensive model tier than the session is using — respecting your cost choices. A subagent also can't spawn its own subagents; work returns to the coordinator for redelegation.

None of these change how you do research; they're the seatbelts that let DAAF move fast without losing the audit trail.

#### Two-Tier Model Routing: Right-Sized Intelligence

Behind the scenes, DAAF's coordinator delegates work to specialist agents — and in v3.0.0 that delegation became deliberately cost-aware. Every specialist role now has a considered default tier: high-judgment roles (research planning, adversarial code review, final verification, debugging, and the analysts who produce your actual data work) run on the most capable model tier, while well-specified mechanical roles (structured lookups, notebook assembly, reference tracing) run on a faster, cheaper one. The coordinator can escalate a specific dispatch when the task turns out to be harder than its role suggests — a failed attempt gets retried with more capability, and the last-line quality gates are never downgraded. The principle is simple: you shouldn't pay flagship prices for mechanical steps, and a session you deliberately started on a cheaper model should never quietly dispatch more expensive helpers (that's the model-ceiling guard above). On alternative providers, the same two-tier logic maps onto whichever models you've configured.

#### Research-Workflow Integrity

A cluster of smaller fixes makes DAAF a more faithful research partner, led by what you'll actually notice:

- **Agents no longer commit to git by default.** Your working tree — with every preserved script version — is the complete audit trail, untouched. A new opt-in "Git commit management" preference turns on milestone commit offers if you'd rather have them (only ever executed with your approval).
- **A sanctioned way to revise a script.** A new `create_script_revision.sh` utility makes the next version of a failed script while preserving the original's immutable execution log, so the record of what was tried stays intact.
- **Plans and state stay in sync.** After you accept a change to a research plan, DAAF now re-syncs the session state file so a later session resumes from an accurate picture, and a single canonical scope policy keeps plan sizing consistent.
- **Claims are graded by evidence.** Agents across the fleet now distinguish what they *observed* — a command that actually ran, quoted with its output — from what they *inferred*, and they're required to say which is which. Claims that something is unavailable or impossible carry the highest evidence bar (those false negatives fail silently and compound), and completion accounting comes from tool output rather than memory. In short: when DAAF tells you something ran, it's because it ran.

#### Reproducibility Verification Hardening

DAAF's Reproducibility Verification mode — re-run an existing analysis and compare the results against the originals — was formalized and hardened in this release, with Python and R held to the same synchronized checks. The comparison machinery is now **fail-closed**: if something can't be verified, it stops and says so rather than quietly passing. Under the hood that means a path-containment audit that keeps a reproduction inside its own sandbox, artifact-by-artifact comparison against the original data files, and tolerance-aware log comparison that can tell a trailing-decimal difference from a real divergence. During this release's development, all six reproducibility test suites passed at 98/98 checks. As ever, reproducibility support helps you re-run and compare an analysis — it does not guarantee bit-identical results, because environment drift and re-fetched data are real.

#### Keeping Pace with Claude Code: Fable Support, Background Agents, and Live Telemetry

DAAF rides on Claude Code, and Claude Code has been moving fast — this release updates the pinned version from 2.1.112 to **2.1.202** and adapts DAAF to genuinely take advantage of what arrived in between.

- **Fable-ready.** Anthropic's new Claude 5 family (Fable, and its restricted-availability sibling Mythos) is recognized everywhere model identity matters in DAAF. Because these models sustain quality much deeper into large context windows, DAAF's session-health system gives them their own validated thresholds — double the token budget before the first caution light, compared to the conservative defaults that still govern Opus, Sonnet, and non-Claude models — and the cost-control guard that keeps specialist agents from out-ranking your chosen session model understands the new tier ordering. If you run DAAF on Fable, the framework knows exactly what it's working with.
- **Specialist agents now work in the background.** Newer Claude Code releases run subagents as background processes, and DAAF leaned in: the old one-at-a-time foreground restriction is retired, so a wave of specialists can genuinely work in parallel. To keep that parallelism from costing rigor, the coordinator follows an explicit "wave barrier" discipline — it waits for every specialist in a dispatched wave to report back before drawing conclusions, so an early result never gets over-weighted just because it arrived first.
- **Live telemetry for every agent.** A new status bar shows your session's model, git branch, reasoning-effort level, a live context meter, and (on subscription plans) your rate-limit windows — and a companion agent panel shows each background specialist's model, status, and its own context meter. Under the hood, DAAF's monitoring became fully subagent-aware: every specialist is measured against its own transcript and its own model's context window, never the coordinator's, so workload warnings always land with the right agent.
- **Log in once — your Claude setup now survives everything short of deleting it.** Claude Code's configuration and state — your login, your settings, and your full session history with resumable transcripts (plus your Codex login, on the ChatGPT lane) — now live in their own persistent Docker volume, separate from the research workspace. Container restarts, updates, and even full image rebuilds no longer log you out or erase your session history: you can rebuild the image and then resume yesterday's session right where it left off. Only explicitly removing the volume clears this state. A huge quality-of-life win for anyone who rebuilds often.
- **Smaller adaptations continue throughout.** Dispatch-time guards now use Claude Code's newer hook protocols (that's what powers the isolation stripping and model-ceiling checks described above), session bookkeeping survives container rebuilds, and the harness defaults are tuned for research work — high reasoning effort, hour-long prompt caching, and no silent auto-compaction of your session history.

#### Testing: Deployment Smoke Checks and DAAFBench

Two new contributor-facing testing systems back this release. **Deployment smoke testing** verifies that a *live* DAAF install actually works end to end through whatever provider route it's configured for — tiered probes cover everything from a zero-cost preflight (route and environment coherence, hooks, statuslines, shim health) through a small live functional battery, plus a zero-cost deterministic battery of the framework's own test suites — a battery that now begins by testing the smoke harness itself, so the checks are themselves checked. **DAAFBench** is how we studied model behavior: we extensively tested how different models perform across DAAF's protocol pipeline — including over the new provider routes, with every archived result carrying fail-closed provenance of exactly which model and route produced it — in order to understand and harden real-world behavior, and we share the results publicly at https://daaf.openaugments.org/bench.

This release expands deterministic tests, analytical-library smokes, deployment-smoke tooling, and DAAFBench protocol-adherence evaluation; these layers have distinct scopes and do not certify scientific validity, research quality, or every provider route. Where we cite results, we cite what actually ran — for example, the six reproducibility suites recorded above at 98/98, and the safety-hook battery recorded at 119/119 as the R package-install guard landed — rather than any blanket "all tests pass" claim.

#### For Contributors

If you'd like to contribute, the CONTRIBUTING guide has expanded for v3: it now maps which kind of change touches which registration points, spells out the evidence a pull request should carry (including honest disclosure of which platform and provider route you tested), and adds guidance for custom-agent compatibility and interpreting benchmark results. Start there — see [CONTRIBUTING.md](CONTRIBUTING.md).

**Full Changelog**: [v2.1.0...v3.0.0](https://github.com/DAAF-Contribution-Community/daaf/compare/v2.1.0...v3.0.0)
<!-- AT TAG TIME: verify tag exists and this compare link resolves -->

---

## v2.1.0 -- 2026-05-02

### Data Analyst Augmentation Framework -- The Frictionless Update

If v2.0.0 was about building out the reliaibility, robustness, and extensibility of DAAF's core analytical engine, v2.1.0 is about making it actually easy to set up, run, and maintain for real-world workflows and collaboration. For example, the original installation process asked users to juggle Docker commands, download and unzip GitHub repos, and manage the Docker volume filesystem. That friction was one of the biggest barrier to adoption, and this release implements a huge number of quality-of-life improvements to fix that. A single command now handles the entire installation. Named helper scripts replace every Docker incantation you'd need to remember and handles all of the back-end container management for you. A one-line update system means you can stay current without losing your work, regardless of when you installed DAAF for the first time. And a new session log viewer gives you a window into what DAAF is actually doing every step of the way, which is crucial for diagnostics and intuition when using the system.

Beyond the operations story, this release also sets up a number of smaller infrastructural improvements -- for example, specialist agents can return more detailed findings, and I've implemented a code-testing pipeline to help ensure every release of DAAF ships without unexpected issues or bugs. More details for the highlights of this release are listed out below!

### One-Line Installer

DAAF can now be installed with a single command on both macOS/Linux and Windows. The previous multi-step manual process has been replaced by a one-line installer that handles everything automatically -- downloading the necessary files, building the Docker image, and setting up your workspace.  Getting started with DAAF and Claude Code in a secure, well-curated, and fully reproducible environment for research has never been easier! This took a LOT of experimentation and testing, since these scripts are designed to be run on your computer, and I had to account for various versions of Windows, MacOSX, etc. etc. which is quite a headache.

### Helper Scripts for Everyday Operations

A complete suite of "helper" convenience scripts (available for both macOS/Linux and Windows) now makes it painless and straightforward to handle the most common DAAF operations. Instead of remembering Docker commands, you can simply run a script:

- **`run_daaf`** -- Start DAAF and Claude Code (automatically sets up the docker container and runs the main commands for you)
- **`update_daaf`** -- Update to the latest DAAF version available, backing up your work automatically before making changes, and helping you integrate framework changes and customizations together (more on that below)
- **`backup_daaf`** / **`restore_from_backup`** -- Save and restore snapshots of your entire DAAF workspace effortlessly. Also allows for painless sharing of entire repositories with colleagues!
- **`rebuild_daaf`** -- Rebuild the Docker image when needed to update configurations, library installs, updates, etc.
- **`view_logs`** -- Open the session log viewer in your browser to easily inspect and view what DAAF is doing at every step of its work (more on that below)
- **`run_vscode`** -- Open a full VS Code editor in your browser for browsing, editing, uploading, downloading, and reviewing files inside the container (more on that below)
- **`view_notebooks`** -- Open Marimo to browse your analysis notebooks

Every script has both a Bash (.sh, for MacOSX and Linux) and PowerShell (.ps1, for Windows) variant, and all are covered by automated tests and quality checks. This was, by far, the most time-consuming part of this release -- making cross-platform shell scripts that work reliably across macOS, Linux, and Windows is genuinely hard, and the number of edge cases to navigate and problem-solve for was humbling. I suspect there will still be some issues that I couldn't identify on my own, so please do let me know what errors and problems you encounter!

### Update and Migration Pathway

Existing DAAF users can now update to the latest version without losing their work or framework customizations in a very guided process. The `update_daaf` script automatically backs up your workspace before making any changes and uses intelligent file-change detection to handle file conflicts gracefully -- leaning on Claude Code itself to help resolve conflicts between your customizations and new framework updates. 

For anyone coming from an older version that doesn't have this script built-in (so anything before this very release), a dedicated `migrate_daaf` script detects your installation type, connects you to the update process, and gets everything organized in a guided walkthrough. Check the [Installation and Quickstart guide](user_reference/01_installation_and_quickstart.md#migrating-from-an-older-installation) for details -- just one line of code to run in your terminal to get caught up.

### Session Log Viewer

A new in-browser session transcript viewer makes it much easier to see what DAAF is doing under the hood and to diagnose issues when they arise. You can browse past sessions, search across transcripts, filter by session, and inspect individual tool calls -- all from a clean web interface. Launch it with the `view_logs` helper script. This has been genuinely useful for development too -- being able to trace exactly what happened in a subagent's session has saved hours of debugging.

### In-Browser VS Code (code-server)

DAAF now ships with a full VS Code editor (code-server) that runs inside the container and opens right in your browser. Before this, if you wanted to look at files DAAF produced -- scripts, data, reports, logs -- your options were scrolling through the terminal, digging through Docker Desktop's clunky file browser, or copying files out to your host machine. None of that is a great experience when you're trying to review an analysis or understand what happened during a session.

Now you just run `run_vscode` from your installation folder and a complete file editor and browser environment opens in your browser -- file tree, syntax highlighting, search across files, Git history, upload and download files, all of it. It comes pre-loaded with nine extensions (Python, GitLens, Git Graph, Rainbow CSV, Markdown support, and more) and a clean dark theme, so it's ready to use immediately. Everything stays inside the container's security boundary, and you don't need to change anything on your own computer to manage it.

This is one of those changes that sounds minor on paper but makes a huge difference in practice. DAAF produces a *lot* of artifacts over the course of a session, and being able to browse and inspect them in a real editor — instead of one file at a time in the terminal — makes reviewing work dramatically more natural. It's also a much friendlier way to explore the framework itself if you're learning how DAAF works or building new skills and agents.

### Environment Variable Support

DAAF now supports secure environment variable configuration via an `environment_settings.txt` file that lives on your host machine (outside the container and inaccessible to Claude). You can set API keys for Claude Code authentication, data source access, and alternative providers -- all in one place. The file is automatically loaded at container startup, and DAAF's safety system prevents Claude from ever reading or accessing it directly. An annotated example template (`environment_settings_example.txt` in your `daaf-docker/` folder) walks you through every option.

### OpenRouter Support (Experimental)

DAAF now supports running Claude Code through OpenRouter as an alternative to a direct Anthropic API key, opening the door for greater model and provider flexibility. Configuration is handled entirely through the `environment_settings.txt` file -- no code changes needed. Context window detection was also updated to correctly query OpenRouter's API for the real context length of whatever model you're running. **Note:** This integration is experimental. It works, but you may encounter rough edges. Direct Anthropic API access remains the recommended and most reliable option.

### Preliminary Phase Notes Persistence

Specialist agent findings (source research, data profiling, synthesis) are now saved to disk as complete markdown files in `output/preliminary_notes/`. Previously, DAAF's coordinator held compressed summaries in its own working memory -- which meant later stages of analysis were working from shortened versions of earlier findings. Now the full findings are saved to a file and later agents read directly from that file, so nothing is lost to summarization. This is a quiet change, but it meaningfully improves analytical continuity across long sessions.

### Shell Scripting Skill

A new `shell-scripting` skill teaches Claude the conventions and standards used across all of DAAF's helper scripts -- covering Bash, PowerShell, error handling, testing, and cross-platform gotchas. Five reference files (~2,200 lines total) cover everything from script templates to testing patterns. This means that when DAAF needs to write or modify shell scripts (or when contributors submit new ones), they'll follow consistent, well-tested patterns.

### Automated Testing and Quality Checks

New automated pipelines run on every proposed code change to help ensure that DAAF's helper scripts remain reliable as the project evolves:

- **Script quality scanning** catches common scripting errors and enforces DAAF-specific conventions automatically on every code change
- **Unit test suites** verify that both the Bash and PowerShell variants of every helper script behave correctly in isolation
- **Full lifecycle tests** exercise the complete workflow -- install, run, backup, update, rebuild, and migrate -- in a fresh Docker environment to catch problems that only appear when everything runs together
- **Pre-commit checks** flag scripting issues before they're even committed, so problems are caught as early as possible

### Under the Hood

- **Specialist agent word limits raised:** Agents can now return substantially longer findings (general agents doubled from 1,000 to 2,000 words; data profiling agents from 2,500 to 3,500), reducing the chance of truncated or incomplete results
- **Prompt caching enabled:** Repeated sessions now benefit from cached context via a new default Claude setting, improving token efficiency and reducing cost
- **Session log collection fixed:** The log collector now correctly finds all agent transcripts from a session, even when sub-agents never directly mention the project directory
- **System prompt trimmed:** Removed ~144 lines of illustrative examples from the always-loaded system prompt -- content that was consuming working memory on every single turn without adding operational value
- **Container startup simplified:** Git identity configuration moved into the image build itself, eliminating an extra startup step and simplifying the boot process
- **Claude Code updated** to version 2.1.112, from the latest pin of 2.1.87

### What's Coming Next

- **R Support** -- Bringing first-class R language support to DAAF, as well as dual-language handling for Python and R in tandem. Long time coming, but will be worth it!
- **Benchmarking tests** -- Creating an automated benchmarking process for DAAF with test cases for plan quality, code generation adherence, and quality checkpoint compliance: the beginning of systematic testing for how well different Claude models follow DAAF's conventions (and thus understanding what settings matter, and/or whether other models from other providers like open-source options are viable yet).
- **More video tutorials and walkthroughs** -- Expanding the library of guided video content

**Full Changelog**: [v2.0.1...v2.1.0](https://github.com/DAAF-Contribution-Community/daaf/compare/v2.0.1...v2.1.0)

---

## v2.0.1 — 2026-04-05

### Data Analyst Augmentation Framework — Minor Revisions

Minor revisions: Adds an explicit "User Support Mode" as DAAF's 9th engagement mode (with better documentation reading/routing for a variety of issues/questions related to DAAF, Claude Code, Docker, and Git), hardens session archiving in the event of accidental crash or unintended closes/session termination, improves user documentation with diagrams and extended content, and archives complete session logs for both sample projects (college selectivity analysis) for better transparency and future educational materials.

**Full Changelog**: [v2.0.0...v2.0.1](https://github.com/DAAF-Contribution-Community/daaf/compare/v2.0.0...v2.0.1)

---

## v2.0.0 — 2026-03-31

### Data Analyst Augmentation Framework — Gaining Altitude Release

DAAF v2.0.0 is a ground-up architectural overhaul driven by four reinforcing goals: greater **extensibility and customizability**, broad **methodological capability expansions**, heightened alignment with **reproducibility best practices as the default**, and improved **token efficiency**. The v1.0.0 framework worked, but it was overly monolithic and fragile; every session loaded thousands of lines of workflow documentation regardless of the task, and adding new capabilities (data domains, analytical methods, engagement patterns) required modifying deeply entangled files ad hoc every single time. v2.0.0 decomposes the system into modular, progressively-disclosed components that load just-in-time, so the orchestrator and agents see only what they need for the current task/mode at hand. This same modularity makes the framework straightforwardly extensible: new data domains, analytical skills, engagement modes, and agent types can be added by authoring self-contained files and running a registration checklist. Not only that, but the new Framework Development mode makes all of these processes and updates happen basically without effort; the meta-improvement systems are working fantastically (having used it extensively for this release!). The net effect is a system that uses context more efficiently, adheres to its own protocols more reliably, can cover far more methodological territory, and scales to new research domains without architectural friction. Finally, the addition of new modes like Ad Hoc Collaboration and Reproducibility Verification begin to move DAAF from a nascent proof-of-concept to a tool that can start to genuinely add value across many domains of the research and science community.

### The Headline Changes

- **Architecture:** `CLAUDE.md` shrinks from ~1,800 lines to ~500 lines of universal conventions. Orchestration logic moves into a dedicated `daaf-orchestrator` skill with reference files loaded just-in-time — so a light-lift Data Lookup session never loads the 1,950-line Full Pipeline spec. Monolithic workflow documentation is split into phase-specific files, each loaded only when the orchestrator reaches that phase. The research Plan document is decomposed into 3 purpose-specific files (Plan, Plan\_Tasks, State), allowing the orchestrator to hold strategy and status in context while referencing task details by path.

- **Engagement Modes: 4 to 8.** New modes: Data Onboarding (formerly Data Ingest, now a full orchestrated mode with API acquisition and multi-file support), Ad Hoc Collaboration, Reproducibility Verification, and Framework Development modes. Existing modes of Data Lookup (renamed from Targeted Assist), Data Discovery (renamed from Discovery), and Full Pipeline are greatly improved across the board.

- **Analytical Skills: 7 new library skills + 2 translation skills.** Each skill follows the same SKILL.md + deep references architecture, so adding support for a new library is a matter of authoring — not framework modification. New skills: statsmodels, pyfixest, linearmodels, scikit-learn (unsupervised + supervised + fairness), geopandas, svy (complex survey analysis), science-communication, plus a major expansion of the data-scientist methodology skill with 8 new reference files covering causal inference, descriptive analysis, survey analysis, geospatial, unsupervised, supervised ML, and statistical modeling. Two cross-language translation skills (r-python-translation, stata-python-translation) enable inline code annotations for users coming from R or Stata backgrounds, powered by a persistent user language preference system.

- **Citation Propagation and Verification.** A distributed citation flow spans the entire pipeline: 13 skills carry canonical citation blocks with inclusion thresholds, the research-executor tracks citations as it works, the orchestrator accumulates them in STATE.md, and the report-writer renders a four-subsection References section with rationale lines. A centralized `CITATION_REFERENCE.md` index covers ~30 methods and tools. A pre-launch audit verified 1,005 references across 46 files and corrected 58 errors (fabricated authors, incorrect API claims, deprecated parameters, dead URLs).

- **Claude Code Platform Adaptations.** Systematic adjustments to DAAF's infrastructure based on testing against Claude Code's actual runtime behavior: a new search-agent replaces generic Plan dispatches (which lacked reasoning depth), subagent transcripts are now archived alongside orchestrator sessions, the 250-character frontmatter truncation limit is accommodated with a two-tier description architecture, the Dockerfile is fully pinned and smoke-tested, and audit logs now carry per-agent identity for traceability.

- **Agent Architecture:** All agents relocated to `.claude/agents/` for native Claude Code discovery. Named agent dispatch replaces generic `subagent_type`, so each agent loads exactly its own protocol and preloaded skills — no wasted context on irrelevant behavioral instructions. Per-agent hook enforcement (`enforce-file-first.sh`) mechanically blocks direct Python execution in coding agents, ensuring protocol adherence at the infrastructure layer rather than relying on prompt compliance alone.

- **Research Integrity:** AI Use Disclosure section (GUIDE-LLM aligned) added to all reports. `CITATION.cff` for machine-readable software citation. Session metadata tracking (DAAF version, model ID, timestamps). Session log collection utilities. First-time user transparency statement on LLM limitations and researcher responsibility.

- **Self-Modification:** Framework Development mode + `framework-engineer` agent + `FRAMEWORK_INTEGRATION_CHECKLIST.md` make DAAF formally self-extensible. New skills, agents, and modes can be added through structured authoring and a registration checklist — the framework is designed to grow without requiring core rewrites.

---

### Painfully Detailed Changelog

Note that Claude absolutely had to help me write most of this, there were like 100 commits to shift through major changes on.

**Reading lens:** Nearly every change below serves one or both of two goals. _Token efficiency:_ reducing what gets loaded into context so agents see only relevant instructions and adhere to them more reliably. _Extensibility:_ making it easy to add new data domains, analytical methods, engagement modes, and agent types without modifying core framework files. These goals reinforce each other -- modular components are both cheaper to load and easier to extend.

#### 1. Core Architecture Streamlining

##### 1.1 Orchestrator Extraction and Progressive Disclosure

The most fundamental change in v2.0.0 is the extraction of orchestration logic from `CLAUDE.md` into the `daaf-orchestrator` skill (`SKILL.md` + 9 reference files). `CLAUDE.md` retains only universal execution philosophy, code style rules, project conventions, and safety boundaries -- content that applies to all agents equally. The orchestrator skill handles mode classification, user communication, subagent dispatch, and workflow coordination.

This enables far better **progressive disclosure**: the orchestrator loads only the reference file for the confirmed engagement mode, rather than ingesting thousands of lines of workflow documentation upfront. Each mode reference file is self-contained with its own invocation templates, gate definitions, PSU (Phase Status Update) templates, and escalation triggers.

Had to figure out a way to ensure that the daaf-orchestrator skill correctly got loaded only by the LLM assistant interacting directly with the user, and ensure that it does so reliably regardless of how the user starts the conversation (via some reminder hooks and checks). This'll be one of those things that's unfortunately annoyingly hard to port to other systems, because the way this works is currently very Claude Code specific. See 4.2 below for more information.

##### 1.2 Workflow Phase Decomposition

The monolithic `02_WORKFLOW_STAGES.md` (1,628 lines) and `03_SKILL_INVOCATIONS.md` (1,847 lines) are replaced by five phase-specific workflow files for the Full Pipeline Mode:

| File | Content |
|------|---------|
| `WORKFLOW_PHASE1_DISCOVERY.md` | Stages 1-3.5: Goal refinement, data exploration, source deep-dives, synthesis |
| `WORKFLOW_PHASE2_PLANNING.md` | Stages 4-4.5: Plan creation, plan verification |
| `WORKFLOW_PHASE3_ACQUISITION.md` | Stages 5-6: Data fetch, cleaning, QA |
| `WORKFLOW_PHASE4_ANALYSIS.md` | Stages 7-10: Transform, analysis, visualization, QA aggregation |
| `WORKFLOW_PHASE5_SYNTHESIS.md` | Stages 11-12: Report writing, final verification |

Each file contains stage-specific invocation templates, gate criteria, verification checklists, and PSU content. The orchestrator loads them progressively as execution advances through phases, which makes session restarts far more efficient and focused, with better instructional adherence along the way.

**Data Onboarding** also receives its own progressive workflow files in the same manner, now that it's been upgraded to a full-fledged mode

- `WORKFLOW_PHASE_DO_PROFILING.md` (~855 lines) — Parts A-D profiling protocol
- `WORKFLOW_PHASE_DO_AUTHORING.md` (~270 lines) — Skill authoring and validation

##### 1.3 Plan Document Decomposition

The research Plan document is split into three purpose-specific files:

| Document | Purpose |
|----------|---------|
| `Plan.md` | Research strategy, methodology, goals, hypotheses, scope decisions |
| `Plan_Tasks.md` | Executable Transformation Sequence — task blocks for subagent dispatch, organized in parallelizable waves |
| `STATE.md` | Session state for recovery — current stage, script status, gate status, blockers, session metadata |

This separation allows the orchestrator to hold `Plan.md` and `STATE.md` in full context while referencing `Plan_Tasks.md` only by path, significantly improving context efficiency for multi-stage sessions.

**New templates:** `PLAN_TASKS_TEMPLATE.md`, expanded `STATE_TEMPLATE.md`

##### 1.4 Deleted Legacy Files

| Removed File | Replacement |
|--------------|-------------|
| `agent_reference/01_PROTOCOLS.md` | Content distributed to `full-pipeline.md` and `session-recovery.md` |
| `agent_reference/02_WORKFLOW_STAGES.md` | Five `WORKFLOW_PHASE*.md` files |
| `agent_reference/03_SKILL_INVOCATIONS.md` | Inline in `WORKFLOW_PHASE*.md` files |
| `agent_reference/07_CONTEXT_MANAGEMENT.md` | Consolidated into `CLAUDE.md` and `daaf-orchestrator/SKILL.md` |
| `agent_reference/08_LESSONS_LEARNED.md` | Replaced by per-project `LEARNINGS.md` |
| `agent_reference/EXECUTION_CAPTURE.md` | Merged into `SCRIPT_EXECUTION_REFERENCE.md` |
| `agent_reference/PLAN_TEMPLATE_INGEST.md` | Deleted (Data Onboarding does not produce a Plan.md) |
| `scripts/md-outline.sh` | Deleted (superseded by direct file reads) |
| `agents/README.md` (old location) | Replaced by `.claude/agents/README.md` |

##### 1.5 File Renames

| Old Name | New Name |
|----------|----------|
| `04_BOUNDARIES.md` | `BOUNDARIES.md` |
| `05_VALIDATION_CHECKPOINTS.md` | `VALIDATION_CHECKPOINTS.md` |
| `06_ERROR_RECOVERY.md` | `ERROR_RECOVERY.md` |
| `SCRIPT_TEMPLATE.md` | `SCRIPT_EXECUTION_REFERENCE.md` |
| `data-ingest-mode.md` | `data-onboarding-mode.md` |
| `STATE_TEMPLATE_INGEST.md` | `STATE_TEMPLATE_ONBOARDING.md` |
| `discovery-mode.md` | `data-discovery-mode.md` |
| `targeted-assist-mode.md` | `data-lookup-mode.md` |
| `revision-mode.md` | `revision-and-extension-mode.md` |

---

#### 2. Expanded and Refined Engagement Modes (from 4 to 8)

##### 2.1 Data Onboarding Mode (formerly Data Ingest)

Elevated from a simple agent invocation to a fully orchestrated mode with its own state template, profiling protocol, and skill authoring workflow. The mode profiles datasets across four parts (Structural, Statistical, Relational, Interpretation) using up to 11 scripts, with orchestrator checkpoints after setup and after critical findings review.

**New in v2.0.0:**

- **API acquisition (DI-0):** Conditional phase for API-based data sources. The agent researches the API, writes an acquisition script, and stops for user review before execution (external network call boundary).
- **Multi-file support:** Two classification types — HORIZONTAL (same structure, union-able) and HIERARCHICAL (different entity levels, must be linked). Hierarchical mode adds per-file script suffixes, a cross-file inventory script, and a mandatory cross-level linkage test script.
- **Progressive disclosure:** Profiling protocol extracted to `WORKFLOW_PHASE_DO_PROFILING.md`, skill authoring to `WORKFLOW_PHASE_DO_AUTHORING.md` — loaded just-in-time.
- **Terminology:** "Phase A/B/C/D" renamed to "Part A/B/C/D" to avoid collision with Full Pipeline's use of "phases."
- **Verbosity standards:** Subagent output cap raised from 1,000 to 2,500 words. Scripts must print complete per-column stats — execution logs are archival with no size limit.
- **Skill quality targets:** New required `analytical-context.md` reference file (including mandatory "What is NOT Included" exclusion table and "Temporal Scope" section). Reference content targets 3x-6x the SKILL.md line count with a hard minimum floor of 3x. Per-file minimums (150-200+ lines).
- **Domain Assessment protocol:** Before authoring reference files, the engineer must identify analytical domains, group columns into clusters, and create dedicated topic-specific reference files for any domain requiring 50+ lines of explanation.
- **Exclusion documentation pipeline:** DI-1 intake collects known exclusions, profiling scripts extract exclusion statements from documentation ("does not include," "excludes," "limited to"), and `analytical-context.md` requires a structured exclusion table (minimum 2 entries).
- **Cross-dataset discovery:** A new authoring step globs for all sibling DAAF data source skills to identify complementary sources sharing join keys, with worked Polars join examples in the skill.
- **Edge case handling:** When profiling confirms no coded/sentinel values, `value-interpretation.md` is created instead of an empty `coded-values.md`, documenting negative value semantics, null patterns, and expected ranges.
- **Profiling script bundling:** Profiling scripts are now bundled with skills in a `scripts/` subdirectory for provenance.
- **Naming convention:** Formal `{domain}-data-source-{acronym}` pattern with validation regex.

##### 2.2 Ad Hoc Collaboration Mode (NEW)

A flexible, user-driven dispatch loop without fixed stages, gates, or mandatory deliverables. The orchestrator operates as a thought partner, responding to conversational questions or dispatching to specialized agents as needed. Thanks to Alberto Guzman-Alvarez and Preston Magouirk for the great nudging in this direction!

**Key features:**

- Deferred workspace creation — folder only created when first artifact is produced
- `SESSION_NOTES.md` as lightweight continuity artifact (replacing STATE.md)
- Orchestrator loads `data-scientist` skill directly (exception to the standard subagent-loads-skills pattern)
- 2,000-word agent output cap (vs. standard 1,000-word pipeline cap)
- Dispatch table mapping user needs to agents

##### 2.3 Reproducibility Verification Mode (NEW)

A four-stage workflow for re-executing an existing analysis and comparing outputs against originals:

| Stage | Activity |
|-------|----------|
| RV-1 | Intake, setup, notebook decompilation into individual scripts |
| RV-2 | Sequential re-execution with comparison |
| RV-3 | Report claim verification against reproduced data |
| RV-4 | Synthesis into Reproduction Report |

**Supporting infrastructure:**

- `decompile_notebook.py` — CLI tool to extract individual scripts from a marimo notebook with a `MANIFEST.md`
- `compare_execution_logs.py` — programmatic comparison of original vs. reproduced script execution logs (row counts, column counts, key statistics, checkpoint pass/fail)
- `collect_session_logs.sh` — finds and copies matching session transcripts into a project's `logs/` directory
- `normalize_project_dir.py` — batch path normalization across decompiled scripts
- `REPRODUCTION_REPORT_TEMPLATE.md` — the Reproduction Report serves as both deliverable and session state document
- Mode-specific behavioral overrides in `code-reviewer`, `data-verifier`, and `report-writer` agents

##### 2.4 Framework Development Mode (NEW)

Enables structured, auditable self-modification of DAAF framework components (skills, agents, modes, templates, hooks, configuration).

**Key features:**

- `framework-engineer` agent with six core behaviors: template fidelity, read-before-write, integration completeness, cross-file consistency, minimal disruption, draft-then-place
- `FRAMEWORK_INTEGRATION_CHECKLIST.md` — canonical registration-point checklist for all component types (skills, agents, modes) with mandatory and conditional items
- Two checkpoints: after scoping (confirm approach) and after review pass (approve final state)
- Bidirectional escalation paths to/from all other modes
- **LEARNINGS.md feedback loop:** New "Incorporate Learnings" work type closes the gap between System Update Action Plans generated at project completion and their consumption back into the framework. A 3-subagent exploration protocol scans all `research/*/LEARNINGS.md` files, checks which items have already been addressed, and proposes prioritized execution order. Full Pipeline and Data Onboarding delivery messages proactively suggest Framework Development mode when action plan items exist.

This works so darn well, I'm really mad I didn't make this sooner! It's made the last legs of development on DAAF v2.0.0 so, so, so much better.

##### 2.5 Data Lookup Mode (renamed from Targeted Assist)

Renamed for clarity — the previous name was ambiguous about the mode's purpose. No behavioral changes; purely a nomenclature improvement.

##### 2.6 Data Discovery Mode (renamed from Discovery)

Renamed for disambiguation from the general concept of "discovery." No behavioral changes.

##### 2.7 Revision and Extension Mode (expanded from Revision Mode)

- Renamed to clarify that the mode handles both fixing existing work and extending it with new analyses
- Added formal escalation triggers, output format (Revision Status Update template), and session recovery guidance
- Added "AI Use Disclosure in Revisions" section for disclosure inheritance across versions

##### 2.8 Mode Confirmation Hard Gate

A formal "HARD GATE" is introduced at mode classification: the orchestrator must confirm the mode with the user and receive explicit approval before proceeding. A **Turn Boundary Rule** enforces that no reference files are loaded and no subagents are dispatched in the same turn as the confirmation message. A **Confirmation Self-Check** checklist validates compliance.

---

#### 3. Agent Architecture

##### 3.1 Agent Relocation

All agent definition files moved from `agents/` to `.claude/agents/` to leverage Claude Code's native subagent discovery mechanism. The old `agents/` directory and its 1,180-line README are removed.

A new `.claude/agents/README.md` (~630 lines) serves as the agent index with key inputs, outputs, and cross-references. This also allows the Orchestrator to more efficiently launch agents with pre-loaded agent protocols and default Skills, saving tokens and improving adherence.

##### 3.2 Named Agent Dispatch

All `subagent_type` values changed from generic strings (`"general-purpose"`, `"Plan"`) to agent-specific names (`"research-executor"`, `"code-reviewer"`, `"data-planner"`, etc.). Claude Code automatically loads the agent's protocol file and applies its `tools` and `permissionMode` settings.

##### 3.3 New Agents

| Agent | Purpose |
|-------|---------|
| `framework-engineer` | Framework artifact authoring and integration (Framework Development Mode) |
| `search-agent` | DAAF-native read-only explorer replacing generic `Plan` dispatches across all modes (see §11.1) |
| `data-ingest` (expanded) | Dataset profiling with multi-file and API support (Data Onboarding Mode) |

##### 3.4 Agent Invocation Template Consolidation

Invocation templates were removed from individual agent files and consolidated into the canonical `WORKFLOW_PHASE*.md` files, eliminating hundreds of lines of duplication. Agent files now focus exclusively on behavioral protocol and anti-patterns.

##### 3.5 Universal Tool Access

The `Skill` tool was added to all 14 agent frontmatter `tools` lists, enabling direct skill invocation from any agent. The `debugger` also gained `WebFetch` and `WebSearch`.

---

#### 4. Enforcement Infrastructure

##### 4.1 File-First Execution Hook (`enforce-file-first.sh`)

A PreToolUse hook that mechanically blocks direct `python`/`python3` invocations, enforcing the file-first execution protocol at the hook layer. Registered per-agent (research-executor, code-reviewer, debugger, data-ingest) rather than globally. Uses fail-closed design with an ERR trap. Framework utility scripts in `/daaf/scripts/` are whitelisted. Currently scoped narrowly to code agents in the pipeline, though we may want to consider adding to the orchestrator and all agents eventually (just gets complicated with things like Marimo notebooks and other utility scripts).

##### 4.2 Orchestrator Loading Enforcement

Two new hooks ensure the `daaf-orchestrator` skill is loaded at session start:

- `remind-orchestrator.sh` (UserPromptSubmit) — injects a reminder if the skill hasn't been loaded
- `flag-orchestrator-loaded.sh` (PostToolUse on Skill) — writes a session flag when loaded, silencing reminders

##### 4.3 Claude-Code-Guide Denial (`deny-claude-code-guide.sh`)

Blocks the built-in `claude-code-guide` subagent type (Haiku model) from being dispatched within DAAF, as it lacks the reasoning depth for framework-aware work and often is just plain wrong. Hook suggests we launch a search-agent to look directly at the Claude Code documentation online via websearch and webfetch tools. Provides alternative guidance. It's such a good idea with such bad execution; why did they do it like this?

##### 4.4 Context Reporter Improvements

- Time-based rate limiting (60-second injection interval) replacing content-based deduplication
- Human-readable timestamps in utilization messages
- Baseline estimate adjusted from 40k to 20k tokens
- **Subagent support fix:** The hook relied on a session-specific cache file for `MAX_CONTEXT` that did not exist for subagents (different session IDs). Fixed with a fallback chain that finds the parent orchestrator's cache. `CLAUDE.md` expanded with subagent-specific threshold-action table, early return protocol (5 required elements: file paths, findings summary, incomplete task list, decisions/assumptions, confidence assessment), and STATE.md coordination guidance for subagents returning under context pressure.
- Adjusted context utilization thresholds to be either percentages OR raw token counts at 150k, 200k, and 250k. While Opus and Sonnet can now handle token windows of up to 1m tokens, there's A LOT of evidence that its performance deteriorates quickly -- and regardless, costs skyrocket per turn because of it. May need to revisit later.

##### 4.5 Logging and Audit

- Session log exclusion removed from `.claudeignore` — transcripts now visible for reproducibility collection
- Edit/Write deny rules added for `.claude/logs/` to prevent audit log modification
- `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS: "1"` added to settings
- **Per-agent audit traceability:** `agent_type` and `agent_id` fields added to every JSONL audit log entry, enabling post-session filtering by specific agent. Orchestrator calls default to `"orchestrator"`; subagent calls populate the actual agent type and unique ID.
- Added some utility scripts that automatically pull in copies of relevant session logs into a given project for full auditability in the full pipeline mode.

---

#### 5. Analytical Skills

##### 5.1 New Python Library Skills

| Skill | Lines (SKILL.md + refs) | Key Coverage |
|-------|------------------------|--------------|
| **statsmodels** | ~4,300 | OLS/WLS/GLS, GLM (logit, probit, Poisson, NB), robust regression, ARIMA/SARIMAX/VAR, mixed effects, diagnostics, hypothesis testing |
| **pyfixest** | ~2,400 | High-dimensional FE (OLS/IV/Poisson), DiD (TWFE, did2s, lpdid, Sun-Abraham), wild bootstrap, publication tables via `etable()`. Targets v0.40.0 with breaking-change documentation. |
| **linearmodels** | ~2,900 | PanelOLS (FE/RE), BetweenOLS, FirstDifferenceOLS, Fama-MacBeth, IV2SLS/LIML/GMM, SUR, IV3SLS, asset pricing. Cross-library syntax comparison tables. |
| **scikit-learn** | ~3,000 | KMeans, DBSCAN, HDBSCAN, PCA, t-SNE, UMAP, GMM (unsupervised). Logistic regression, random forest, gradient boosting, SVM, Ridge/Lasso (supervised). Preprocessing, pipelines, cross-validation, feature selection. Targets v1.8.0. |
| **geopandas** | ~3,400 | GeoDataFrames, spatial joins, CRS/projections, raster integration (rasterio, xarray), PySAL ecosystem (Moran's I, LISA, spatial regression), visualization (matplotlib + contextily, folium, lonboard). Targets v1.1.3. |
| **svy** | ~1,700 | Complex survey data analysis: design specification (strata, PSU, weights, FPC), variance estimation (Taylor linearization, BRR, jackknife, bootstrap), survey-weighted GLM regression (gaussian, binomial, Poisson), domain/subpopulation estimation, calibration, survey data I/O. Targets v0.13.0 (supersedes archived samplics). |
| **science-communication** | ~1,700 | Audience analysis, narrative frameworks (Pyramid Principle, SCQA, AIDA), plain-language translation, hedging/uncertainty (IPCC calibrated), deliverable templates (executive summary, policy brief), accessibility/equity, pre-release review checklist. |

Each skill follows the SKILL.md + deep references architecture with decision trees for routing and explicit boundary documentation against sibling skills.

##### 5.2 Cross-Language Translation Skills and User Language Preferences

Two translation skills provide verb-by-verb mappings from R and Stata to their Python equivalents, enabling inline code annotations for users with non-Python backgrounds.

| Skill | Lines (SKILL.md + refs) | Key Coverage |
|-------|------------------------|--------------|
| **r-python-translation** | ~7,400 | tidyverse → polars, ggplot2 → plotnine, fixest → pyfixest, survey → svy, sf → geopandas, plm → linearmodels. Paradigm differences, gotchas, external resources. |
| **stata-python-translation** | ~8,700 | Data management, strings/dates/labels, regression modeling, causal inference, visualization, survey/spatial/ML, workflow/environment. Mirrors the R skill architecture. |

**User Language Preference System:** A persistent, cross-session preference mechanism stored in `CLAUDE.md` § User Preferences. The orchestrator detects R/Stata background signals (explicit: "I use R"; implicit: R/Stata syntax in pseudocode), proposes persisting the preference, and silently propagates a translation directive to all 4 code-producing agents (research-executor, code-reviewer, debugger, data-ingest) across all sessions. Wired into 5 mode reference documents and 2 workflow phase invocation templates.

##### 5.3 Supervised ML Track

- New `supervised-ml.md` methodology reference for the `data-scientist` skill covering prediction vs. inference (Shmueli 2010), bias-variance tradeoff, cross-validation strategies, model selection, feature importance caveats, algorithmic fairness impossibility theorems, and reporting standards
- New `scikit-learn/references/interpretation.md` — SHAP (TreeExplainer, KernelExplainer), permutation importance, partial dependence, ICE plots
- New `scikit-learn/references/fairness.md` — fairlearn MetricFrame, ThresholdOptimizer, ExponentiatedGradient, demographic parity, equalized odds
- LightGBM and XGBoost sections added to classification and regression references
- Supervised ML routing wired into Full Pipeline modeling library selection

##### 5.4 Data-Scientist Skill Expansion

The `data-scientist` skill was restructured from a single "statistical analysis" routing branch into seven methodology-specific routing trees with eight new reference files (~5,050 lines total):

| Reference File | Coverage |
|---|---|
| `causal-inference.md` | DAGs, potential outcomes, RCT, IV/2SLS, RD, DiD, synthetic control, matching/PSM |
| `descriptive-analysis.md` | Summary statistics, distributions, cross-tabulations, temporal patterns |
| `statistical-modeling.md` | Model selection, assumption checking, diagnostics |
| `survey-analysis.md` | Complex survey design anatomy, weight selection, variance estimation methods, domain estimation, plausible values, survey-weighted regression, federal survey reference table, pitfalls checklist |
| `exploratory-unsupervised.md` | Clustering, PCA, nonlinear embeddings, cluster validation |
| `supervised-ml.md` | Prediction vs. inference, cross-validation, fairness, reporting |
| `geospatial-analysis.md` | MAUP, CRS, spatial autocorrelation, spatial regression |
| `geospatial-operations.md` | Spatial joins, weights, LISA, interpolation, zonal statistics |

A ~125-row topic index in SKILL.md maps specific analytical topics to the correct reference file. Beefy, but definitely worthwhile and still extensible.

##### 5.5 Modeling Library Pipeline Wiring

- `data-planner` task specs now require a `<skill>` element specifying the modeling library
- `research-executor` skill loading tables updated with conditional library loading and fallback rules
- `debugger` gains a "Modeling Library Gotchas" section with per-library failure mode summaries
- `report-writer` gains conditional Step 5.5 for science-communication skill loading when target audience is non-technical
- `PLAN_TEMPLATE.md` gains a "Target Audience" field controlling communication skill routing

---

#### 6. Research Integrity and Attribution

##### 6.1 AI Use Disclosure (GUIDE-LLM Alignment)

A structured AI Use Disclosure section is added to all reports, mapping to the GUIDE-LLM v2026 reporting checklist (Feuerriegel et al.). `AI_DISCLOSURE_REFERENCE.md` maps every checklist item (A.1 through G.1) to its DAAF artifact source, tagged as `[AUTO]` (auto-populated by report-writer) or `[RESEARCHER]` (requires human completion).

Session metadata (DAAF version via git commit hash, model ID, session dates, transcript path) is captured in STATE.md at project setup and passed through to the report-writer.

AI disclosure guidance is added for all modes — including Data Discovery, Data Lookup, Revision and Extension, and Reproducibility Verification.

##### 6.2 Citation Framework

- `CITATION.cff` — machine-readable software citation (CFF standard) identifying DAAF 2.0.0 as citable software
- APA and BibTeX citation formats in README
- Layered citation guidance (DAAF + Claude + data sources + GUIDE-LLM)
- "Software & Tools" citations sub-section in report template
- FORCE11 software citation principles alignment

##### 6.3 Citation Propagation System

A distributed citation flow that tracks methodological and software attribution across the entire pipeline, from skill loading through report generation:

1. **Skill-level citation blocks:** 13 skills now carry `## Citation` sections with canonical citation text, "Cite when" / "Do not cite when" inclusion thresholds, and secondary citation guidance.
2. **Research-executor tracking:** New `Citation Tracking` core behavior and `Citations` output section. The executor reports a table of `software`/`method` type citations with rationale as part of its return format.
3. **Orchestrator accumulation:** STATE.md gains a `Citations Accumulated` section with four tables (Data Sources, Methodological References, Software & Tools, Reporting Standards). DAAF, marimo, and GUIDE-LLM are pre-populated at project setup.
4. **Report-writer rendering:** The References section is now sourced from STATE.md (not verbatim Stage 6 text) and rendered as four subsections with "_Cited because:_" rationale lines for non-data-source entries.
5. **Verification:** The data-verifier gains a citation verification step. `CITATION_REFERENCE.md` serves as a centralized index covering ~30 methods and tools with inclusion thresholds and a parsimony principle ("A report with 5 well-justified citations is better than one with 30 perfunctory ones").

User-facing documentation (first-run transparency statement, Understanding DAAF guide, Best Practices guide) updated to explain the References section and advise researchers that citations are "best-effort, not guaranteed."

##### 6.4 Pre-Launch Citation Audit

A systematic audit verified 1,005 citations, references, URLs, and attributed API claims across 46 skill reference files in 12 skill areas. 58 corrections applied:

- **HIGH (5):** Fabricated author names, wrong page numbers, reversed author order, wrong journal name
- **MEDIUM (19):** Incorrect API claims across polars (6), statsmodels (3), linearmodels (3), marimo (3), scikit-learn (1), plotnine (1), plotly (2)
- **LOW (32):** Outdated claims, deprecated parameters, incomplete option lists, dead URLs

---

#### 7. Skill Metadata and Authoring

##### 7.1 Controlled Vocabulary

Formal controlled vocabulary defined for skill frontmatter:

- `audience`: `any-agent`, `research-orchestrator`, `research-planner`, `research-coders`, `research-writers`
- `domain`: `data-source`, `data-access`, `data-documentation`, `python-library`, `research-methodology`, `research-orchestration`, `research-communication`, `skill-development`
- Standard keys: `library-version`, `skill-authored`, `skill-last-updated`

Applied uniformly across all 35 skill files with description enrichment.

##### 7.2 Skill Authoring Guide Updates

- "Concise is Key" replaced with "Right-Size Each Level": SKILL.md concise, reference files comprehensive
- Reference file density guidelines: 3x-6x ratio of reference lines to SKILL.md lines
- Anemic reference files flagged as harmful as bloated SKILL.md files
- Data source skill naming convention: `{domain}-data-source-{acronym}` with validation regex
- **250-character frontmatter limit accommodation** — see §11.2

---

#### 8. User Experience

##### 8.1 Tone and Voice Standards

Comprehensive tone specification added to the orchestrator:

- **Warm:** Encouraging, acknowledges good questions, celebrates interesting findings
- **Thoughtful:** Explains _why_ things matter, connects dots between phases
- **Patient and methodical:** Never rushes past decision points, confirms understanding
- **Educational:** Explains data caveats and methodology tradeoffs as they arise
- **Direct but not terse:** Concise without being cold
- **Honest about uncertainty:** Plain acknowledgment of ambiguity and limitations

##### 8.2 Plain-Language Communication

A translation table maps internal terminology to user-facing language (e.g., "PSU" becomes "phase checkpoint," "QA" becomes "quality review," "Stage N" becomes "step" or activity description). Internal terms like "Composite execution pattern" and "Gate GN" are never exposed.

##### 8.3 Welcome Preamble

Every conversation begins with a brief introduction to DAAF. An expanded orientation is triggered on newcomer signals ("how does this work," "what can you do"). Context-sensitive help table maps user signals to appropriate documentation files.

##### 8.4 First-Time User Transparency Statement

A first-run onboarding hook detects new users (via `activity.log` session count) and presents a candid transparency statement before the normal welcome flow. The statement covers what DAAF is and isn't, inherent LLM limitations (hallucination, sycophancy, over-confidence, non-determinism), the probabilistic nature of DAAF's quality improvements, the primacy of researcher expertise, and practical guidance for new users. Delivered in conversational tone, not as a terms-of-service wall.

---

#### 9. Infrastructure and Environment

##### 9.1 Dockerfile

New package layers for:

- **Econometrics:** linearmodels, rdrobust, marginaleffects, arch, pydynpd, svy
- **Geospatial:** geopandas, rasterio, xarray, rioxarray, contextily, folium, libpysal, esda, spreg, mapclassify, rasterstats, geopy, osmnx
- **Geospatial system libraries:** libgdal-dev, gdal-bin, libgeos-dev, libproj-dev (required by fiona, a transitive dependency of rasterstats)
- **ML:** shap, fairlearn, lightgbm, umap-learn
- **Utilities:** poppler-utils (PDF support), tabulate, great-tables, wildboottest, fastexcel

**Post-smoke-test stabilization:** 16 previously-floating packages pinned to exact versions for reproducible builds. `samplics` removed (superseded by svy). `kaleido` removed (Chromium dependency incompatible with container; plotly skill updated with workaround guidance to use plotnine for static figures). A follow-up smoke test run (246 tests) corrected additional skill documentation in pyfixest, svy, and plotly. Docker volume permissions fixed for macOS (named volumes with root ownership blocking `appuser`).

Model configuration updated to `claude-opus-4-6[1m]` (1M context window).

##### 9.2 New Utility Scripts

| Script | Purpose |
|--------|---------|
| `scripts/decompile_notebook.py` | Extract individual scripts from a marimo notebook |
| `scripts/compare_execution_logs.py` | Compare original vs. reproduced execution logs |
| `scripts/collect_session_logs.sh` | Find and copy matching session transcripts |
| `scripts/normalize_project_dir.py` | Batch path normalization across decompiled scripts |

##### 9.3 Installation Simplification

Git removed as a host-machine prerequisite. Installation now uses ZIP download (`curl`/`Invoke-WebRequest`) instead of `git clone`, reducing prerequisites from four to three. `docker-compose.yml` gains `name: daaf` for folder-independent volume naming (ZIP extracts to `daaf-main/` rather than `daaf/`). Update procedure rewritten with ZIP-based commands that copy framework files into the Docker volume while preserving the `research/` folder.

##### 9.4 CLAUDE.md Philosophy

The Identity section was expanded from a brief description to a full philosophical statement: DAAF as a "force-multiplying exo-skeleton," the five core requirements (Transparent, Rigorous, Reproducible, Responsible, Scalable), and the primacy of human researcher judgment.

---

#### 10. Documentation

##### 10.1 New Reference Files

| File | Purpose |
|------|---------|
| `AI_DISCLOSURE_REFERENCE.md` | GUIDE-LLM checklist mapping for all modes |
| `FRAMEWORK_INTEGRATION_CHECKLIST.md` | Registration-point checklists for skills, agents, modes |
| `MODE_TEMPLATE.md` | Template for authoring new engagement modes |
| `PLAN_TASKS_TEMPLATE.md` | Template for the task-block document |
| `REPRODUCTION_REPORT_TEMPLATE.md` | Template for Reproducibility Verification output |
| `STATE_TEMPLATE_ONBOARDING.md` | State template for Data Onboarding mode |
| `CITATION_REFERENCE.md` | Citation index for pipeline citation propagation and verification |

##### 10.2 Expanded Templates

- `AGENT_TEMPLATE.md` — expanded with per-agent hook registration, skills-in-frontmatter guidance
- `DATA_SOURCE_SKILL_TEMPLATE.md` — API data access skeleton, multi-file structure section, analytical-context.md requirement
- `MODE_TEMPLATE.md` — expanded from 6-item to 13-item checklist with naming conventions and exemplar references
- `REPORT_TEMPLATE.md` — AI Use Disclosure section, Software & Tools citations
- `STATE_TEMPLATE.md` — session metadata, per-script QA status, gate status tracking

##### 10.3 User Documentation Updates

All files in `user_reference/` updated to reflect eight engagement modes, three-document Plan structure, Data Onboarding capabilities, and Framework Development mode. Best practices and extending-DAAF guides revised.

---

#### 11. Claude Code Platform Adaptations

Changes driven by testing DAAF against Claude Code's actual runtime behavior, addressing platform constraints and improving observability.

##### 11.1 search-agent Replaces Generic Plan Dispatches

Generic `Plan` subagent dispatches lacked reasoning depth for DAAF's domain-aware exploration tasks. A new `search-agent` (413-line agent definition, full 12-section template) serves as DAAF's 14th agent — a broad-purpose, read-only explorer with web access (WebSearch, WebFetch) and skill-aware domain knowledge. All exploration dispatches across Data Discovery, Data Lookup, Framework Development, and Full Pipeline modes changed from `Plan` to `search-agent`. The `Plan` generic type is de-prioritized rather than removed. The `Explore` subagent type remains blocked (runs on Haiku); error messages now recommend `search-agent`.

##### 11.2 Frontmatter Description Truncation Accommodation

Claude Code silently truncates skill frontmatter `description` fields at ~250 characters. All 35 DAAF skills (previously 381-813 chars) were losing trigger and disambiguation text without any visible error. All descriptions condensed to fit within 250 characters. Full descriptions preserved as plain paragraphs immediately after the `# Title` heading in each SKILL.md body. The skill-authoring reference (`frontmatter.md`) updated with the 250-char hard limit, budget priorities, and the "Full Description in Body" pattern.

##### 11.3 Subagent Transcript Archiving

Previously, only the orchestrator's session transcript was archived. A new observability pipeline captures subagent activity:

- **`subagent-registry.sh`** — new `SubagentStop` hook records each subagent's metadata (agent\_type, agent\_id, transcript\_path, tool\_uses, duration) to a per-session JSONL registry file
- **`archive-session.sh` expansion** — at session end, copies each subagent's JSONL transcript into the archive with `_subagent_{id}` suffixes, renders companion Markdown files, and appends a "Subagent Activity" summary table to the orchestrator's Markdown archive
- **Unified naming convention:** `{date}_{time}_{session}_orchestrator.{jsonl,md}` and `{date}_{time}_{session}_subagent_{id}.{jsonl,md}` — all files from one session sort together

##### 11.4 Script Execution Portability

- `run_with_capture.sh` changed from `python` to `python3` for PEP 394 portability
- Copy-into-project pattern eliminated across 17 files — all execution now references the canonical copy at `{BASE_DIR}/scripts/run_with_capture.sh` rather than per-project copies
- Shell script executable permission convention established: all `.sh` files must be committed with mode `100755` via `git update-index --chmod=+x`, documented across 6 framework files (CLAUDE.md, framework-engineer agent, integration checklist, script execution reference, skill-authoring reference, framework-development mode)

---

### Breaking Changes Summary

These changes affect the internal framework structure. External users consuming DAAF analyses are unaffected.

| Change | Impact | Migration |
|--------|--------|-----------|
| `CLAUDE.md` reduced to conventions only | Orchestration logic must be loaded via `daaf-orchestrator` skill | Load skill at session start (enforced by hooks) |
| Agents moved from `agents/` to `.claude/agents/` | Path references must update | All internal references updated |
| `subagent_type` changed to agent-specific names | Orchestrator dispatch must use named agents | All invocation templates updated |
| Plan split into Plan + Plan\_Tasks + State | Existing single-Plan projects structurally incompatible | Create Plan\_Tasks.md and STATE.md from existing Plan |
| Multiple reference files renamed/deleted | Hardcoded path references break | See File Renames table above |
| "Data Ingest" renamed to "Data Onboarding" | Mode name references must update | All internal references updated |
| "Phase A/B/C/D" renamed to "Part A/B/C/D" | Data Onboarding terminology must update | All internal references updated |
| Direct `python` calls blocked in coding agents | Must use `run_with_capture.sh` wrapper | Already enforced by hook |
| `claude-code-guide` subagent blocked | Cannot dispatch Haiku-based guide agent | Use `search-agent` (has WebFetch/WebSearch) |
| Generic `Plan` dispatches replaced by `search-agent` | Exploration tasks use named agent | All invocation templates updated |
| `run_with_capture.sh` path changed from `{PROJECT_DIR}` to `{BASE_DIR}` | Per-project copy references break | All execution now uses `{BASE_DIR}/scripts/run_with_capture.sh` |

**Full Changelog**: [v1.0.0...v2.0.0](https://github.com/DAAF-Contribution-Community/daaf/compare/v1.0.0...v2.0.0)

---

## v1.0.0 — 2026-02-22

### Data Analyst Augmentation Framework — Launch Release

The initial public release of DAAF, an open-source, extensible AI-augmented research workflow for Claude Code that allows skilled researchers to rapidly scale their expertise and accelerate data analysis — without sacrificing transparency, rigor, or reproducibility.

#### Core Framework

- Multi-stage research pipeline with mandatory validation and quality checkpoints at every stage
- Specialized agents that tackle each stage of the research pipeline with specific insights, strategies, and expertise (e.g., research-executor, code-reviewer, data-planner, plan-checker, data-verifier, source-researcher)
- Per-script QA with adversarial code review where every transformation has a validation, and all data operations are stored in a file-first format for maximum auditability

#### Skills Ecosystem

- Analytical tools for data analysis: Polars, plotnine, Plotly, marimo, data-scientist
- Data sources: 15 source-specific data skills (CCD, IPEDS, CRDC, Scorecard, EDFacts, MEPS, SAIPE, FSA, NHGIS, NCCS, PSEO, EADA, NACUBO, Campus Safety) plus query, explorer, and context skills, to answer hundreds of meaningful research questions about education out-of-the-box
- Extensibility tools to easily expand the data domains to any field/dataset you need

#### Documentation

- User guides: installation/quickstart, understanding DAAF, best practices, extending DAAF, philosophy FAQ, technical FAQ
- 10-minute demo video walkthrough
- Complete example project for review (College Graduation Rate Selectivity Analysis)

#### Infrastructure

- Docker containerized environment with defense-in-depth security
- Pre-commit hooks, audit logging, session archiving
- LGPL-3.0 license (core framework open; extensions can be proprietary)
