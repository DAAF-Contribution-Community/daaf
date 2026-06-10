# 01. Installation & Quick Start

This is the complete first-time installation and setup guide for DAAF. This document covers every step from installing prerequisites to running your first session, as well as tips for file management, viewing compiled research script notebooks, and troubleshooting.

[**Back to main**](https://github.com/DAAF-Contribution-Community/daaf/tree/main)

---

## Table of Contents
- [**Prerequisites**](#prerequisites)
- [**Installing DAAF**](#installing-daaf)
- [**Recommended Next Steps**](#recommended-next-steps)
- [**Day-to-Day Start/Stop Workflow**](#day-to-day-startstop-workflow)
- [**How to Manage DAAF Project Files and Output**](#how-to-manage-daaf-project-files-and-output)
- [**Viewing Marimo Notebooks in Your Browser**](#viewing-marimo-notebooks-in-your-browser)
- [**Viewing Session Logs in Your Browser**](#viewing-session-logs-in-your-browser)
- [**Keeping DAAF Updated**](#keeping-daaf-updated)
- [**Advanced Installation & Configuration**](#advanced-installation--configuration)
- [**Setup Troubleshooting**](#setup-troubleshooting)

---


**Installing DAAF is extremely easy and straightforward.** No prior experience with terminal, Docker, or Claude Code required. That being said, I put a LOT of explanations and detail together here so you have a strong sense and intuition for what's going on under the hood -- which I think is extremely valuable so you have a better handle on why things operate the way they do, or how to manage things in case anything goes wrong. Besides the reading, this whole process really shouldn't take you more than 10 minutes start-to-finish!


## Prerequisites

Before installing DAAF, there are three (technically four) key prerequisites. Please read the Anthropic account requirement especially closely; the price of the necessary subscription is definitively the highest barrier to entry at this time. I hope this will change in the near future with greater testing and community support for open-source models!

### 0. A computer with internet access

You'll need internet access to download the project files and interact with DAAF/Claude (which itself always requires internet). Note that all data analyses will be conducted using your actual computer hardware, so you should have a computer that's generally capable of running intermediate-level data analysis (same sort of requirements you'd face if you wanted to analyze these same datasets in R/Stata/Python regularly). Don't worry about actual Python packages/libraries/dependencies, that's all handled carefully for you behind the scenes!

### 1. Anthropic Account & Authentication

Claude Code is the AI assistant platform that powers this project. It runs inside your terminal (not in a web browser) and needs to link in with an Anthropic account for billing/usage purposes. Because we're relying on cutting-edge frontier models and asking them to do a **LOT** of thorough work for us (deep-diving into data, writing a lot of code, checking a lot of code, rewriting code, writing intensive plans, etc., etc.), we need to have a **high-usage** Anthropic account. Unfortunately, the free and standard "Pro"-level plans will simply not be sufficient for the time being; given current pricing at $100-200/mo, this is the biggest barrier-to-entry for engaging in this work. Here are your main options:

| Option | Cost | Setup | Key Tradeoff |
|--------|------|-------|--------------|
| **Anthropic Max subscription** (recommended) | $100-200/mo flat | Interactive login on first launch -- no config needed | Best value for heavy use; I rarely hit limits even with very heavy use on the $200/mo plan. You can get by with much less if you're doing smaller, more discrete tasks with DAAF. [Get one here](https://claude.com/pricing/max) or [upgrade an existing plan](https://claude.ai/upgrade). Team/Enterprise subscriptions also work, but mileage may vary based on organizational settings/limits. |
| **Anthropic API key** | Pay-per-use (can get expensive fast) | Interactive login on first launch -- no config needed | Unlimited use, but a full pipeline analysis can cost $50+ in API fees. I'd have paid roughly 10x more via API key than my Max subscription. [Get one here](https://console.anthropic.com/). |
| **OpenRouter** | Pay-per-token via openrouter.ai with a 5.5% fee on credit purchases | Configure via `environment_settings.txt` ([instructions below](#configure-authentication-via-environment_settingstxt)) | No Anthropic subscription required; solid alternative if you want to avoid a monthly commitment or already use OpenRouter. **Caveat:** DAAF requires Opus-class models -- stick with Anthropic's Opus through OpenRouter for now. GLM 5.1 and Kimi K2.6 are cheaper and fairly viable models from early scoping, but require more testing and caution. [Get a key here](https://openrouter.ai/). |
| **Cloud providers** (Bedrock, Vertex AI) | Per your organization's arrangement | Configure via `environment_settings.txt` ([instructions below](#configure-authentication-via-environment_settingstxt)) | Route through your org's existing cloud platform. See `environment_settings_example.txt` in `daaf-docker` for required variables. |

**Not sure which to pick?** Start with the lower Max subscription ($100/mo plan) to test things out and get a sense of how you might want to use DAAF. Then adjust methods or subscription levels as need arises.

**How authentication works:** For the **Max subscription** and **API key** options, Claude Code will prompt you to authenticate interactively the first time you run it -- you don't need to configure anything in advance. For **OpenRouter** and **cloud provider** setups, you'll configure credentials via the `environment_settings.txt` file instead (instructions below). You can always switch between methods later (type `/login` inside Claude Code to change your interactive authentication, or update your `environment_settings.txt` file and restart the container). Note that many terminal interfaces "hide" any password-entry you're asked to do, so if you don't see your typing "working," it's working but hiding it from view for your privacy.

**A note on credentials security:** Your Claude and/or API credentials only ever sit locally on your computer or go directly to the service provider, and I've enforced a LOT of safety checks to ensure Claude doesn't accidentally share it with anyone, either. This can be directly verified in the code.

**A note on data security and privacy:** I strongly recommend starting your practice with DAAF using publicly available, non-private data. DAAF can be extended for use with any datasets from any domains, but you'll need to do some additional homework to understand whether your current license with Anthropic/Claude Code offers the necessary data privacy and security protections for any proprietary or PII data. Please see the [Data Privacy FAQ](07_faq_technical.md#q-is-my-data-sent-to-anthropic-what-about-privacy) for more details.

### 2. Terminal

It's probably going to feel a bit weird, but you'll interact with DAAF/Claude Code through your **Terminal** (also called the command line or shell) -- a text-based interface on your computer where you type commands and instructions to your computer. You can think of this as the code-based way to do all the things you would normally do on your computer by clicking around a standard user interface (navigating folders, copying files, deleting things, etc.). Getting started is strange and a little intimidating, but when Claude Code is actually running, it's basically like any other AI assistant chatbot window with worse font. Your computer definitely already has this, but if you're not used to working in the terminal, here are some basics:

**Opening your terminal:**
- **Mac:** Open the "Terminal" app (search for it in Spotlight with `Cmd + Space`)
- **Windows:** Open "PowerShell" from the Start menu (PowerShell is strongly recommended as Command Prompt/cmd often does not contain all the proper permissions and functions!)
- **Linux:** Open your terminal emulator (usually `Ctrl + Alt + T`)

**Helpful terminal basics:**
| What you want to do | Command | Example |
|---------------------|---------|---------|
| See where you are | `pwd` | Shows `/Users/yourname/daaf` |
| List files here | `ls` | Shows files and folders in current directory |
| Move into a folder in the current directory | `cd foldername` | `cd daaf-docker` |
| Go up one folder level | `cd ..` | Goes to the parent directory |
| Clear the screen | `clear` | Clears clutter (your history is still there) |
| Cancel a running command | `Ctrl + C` | Stops whatever is currently running |
| Copy highlighted text (macOS) | `Cmd + C` | Copies text, normal hotkeys for macOS |
| Copy highlighted text (Windows) | `Ctrl + Shift + C` | Copies text, note the need for Shift in Windows!! |
| Scroll up to see past output | Scroll or `Shift + Page Up` | See output that scrolled off screen |

**Tips:**
- You can paste commands into the terminal (`Cmd + V` on Mac, `Ctrl + V` or right-click on Windows)
- Press the up arrow key to recall previous commands
- Tab completion works — start typing a file/folder name and press `Tab` to auto-complete it
- Claude Code had a lot of graphical glitches for me on Windows when using Powershell. I have found the free version of [Warp](https://www.warp.dev/) to be a much cleaner, more reliable experience (you can skip creating an account and skip using any of their AI features, it's totally free), but Powershell will still work if you don't want to install any other software.

### 3. Docker Desktop

Docker is a program designed to help people create self-contained, isolated environments (called a "container") on your computer that are strictly separated from everything else, and extremely easy to replicate and share. This protects your computer and prevents Claude Code from messing with anything it shouldn't be, and it ensures that even if somehow things go catastrophic, you can easily spin up a new virtual environment back up in minutes with zero consequences. In this project, I also use Docker to install every needed piece of software in a predictable and stress-free way to have Python, data science libraries, and Claude Code all ready to go in one step. Think of it like a lightweight virtual computer running inside your computer that gets created via a very specific recipe, every single time. Docker Desktop includes everything you need (including Docker Compose, which coordinates the setup). After installing, make sure Docker Desktop is actually running before proceeding. If you're worried, you can see exactly what is installed by reading the Dockerfile in this repository -- feel free to ask your favorite LLM to help you interpret and inspect it, if you'd like. If you run into any Docker-related errors during install, you may need to restart your computer to let the install fully sink in.

**Install:** [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)

---

## Installing DAAF

With all the prerequisites out of the way, installation is a single command that takes 5-15 minutes with a decent internet connection. The installer downloads some initial helper files, builds a Docker image with the full data science stack and Claude Code in a fully replicable way, and then downloads the complete DAAF repository into the container so that Claude Code runs using all of the added DAAF files.

### One-Line Install

Make sure Docker Desktop is running in the background, then open your terminal, navigate to your desired installation directory, and paste the command for your operating system:

**macOS / Linux (Terminal):**

```bash
curl -fsSL https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/install.sh | bash
```

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/install.ps1 | iex
```

The installer will show its progress as it works through four steps: creating a build directory, downloading the Docker files, building the image, and cloning DAAF into the container. When it finishes, it prints instructions for entering the container and launching Claude Code.

**What you should expect to see:**

```
╔══════════════════════════════════════════════════════╗
║          DAAF Installer                              ║
║          Data Analyst Augmentation Framework         ║
╚══════════════════════════════════════════════════════╝

[1/4] Creating build directory...
[2/4] Downloading Docker files...
[3/4] Building Docker image (this may take a few minutes)...
....[lots of text scrolling by]
[4/4] Cloning DAAF repository into container...

✓ Installation complete!
```

The actual output will include more detail as each step progresses, but these are the key milestones to watch for.

### What the installer does

1. **Creates an installation directory** called `daaf-docker/` in whatever folder your terminal is currently in, containing all the files you'll need to run and manage DAAF from here on. For example, if you open your terminal and it starts in your home folder (`~` on Mac/Linux, `C:\Users\YourName` on Windows), that's where `daaf-docker/` will be created. You can `cd` to a different location first if you'd prefer to install elsewhere.
2. **Builds the Docker image** with Python 3.12, 50+ data science packages, geospatial libraries, and Claude Code pre-installed. The first build downloads everything and takes a few minutes; subsequent rebuilds use Docker's layer cache and are much faster.
3. **Downloads the DAAF repository** directly into the Docker volume inside the container. This gives you a full file edit and version history via Git.
4. **Enforces security controls on Claude.** One of the big benefits of using Docker is that we can really keep Claude Code under control. The Docker container runs as a non-root user with all Linux capabilities dropped (`cap_drop: ALL`) and privilege escalation explicitly blocked (`no-new-privileges`). Even if Claude Code somehow tried to do something it shouldn't, the operating system kernel would stop it.

**If the build seems to hang** during `[3/4]`, give it a little extra time since installing the 50+ packages including geospatial libraries can take a minute here and there. As long as the output occasionally moves and updates every few minutes, let it finish. If anything goes wrong, you can close the terminal, delete the `daaf-docker` folder, and run the installer again; nothing is permanently changed on your computer.

### Launch Claude Code with DAAF

Now, you'll use your terminal to enter the DAAF installation directory it just created with all the main utility files, `daaf-docker/`. Once you're in there, you can run a helper script I created to make it easy to launch DAAF and Claude Code in the Docker container automatically.

**macOS / Linux (Terminal):**

```bash
cd daaf-docker
bash run_daaf.sh
```

**Windows (PowerShell):**

```powershell
cd daaf-docker
.\run_daaf.ps1
```

On first launch, Claude Code should prompt you to authenticate (API key or subscription login). Follow its instructions to complete the process as needed based on your method. Remember that CTRL+C actually exits the terminal, so use (Windows/Linux: CTRL+SHIFT+C and CTRL+V) and (macOS: Cmd+C and Cmd+V) if you want to copy/paste. You may need to copy and paste the link into your browser; be careful to check it for erroneous line-breaks in the URL if you run into issues!

### Configure Claude Code (required)

Once you're in, there are a few settings to adjust to ensure that the workflow is able to operate as expected. First, type the following into Claude's chat window:

```bash
/config
```

And then change the following settings by navigating down with your arrow keys, editing settings with left-right arrow keys, and hitting Enter when done:

- **"Auto-compact"** -- set to **False**. DAAF manages its own context carefully; auto-compaction can disrupt its orchestration and cause unexpected behavior.
- **"Verbose output"** -- set to **True**. Verbose output lets you see what DAAF's agents are actually thinking behind the scenes, making it much easier to detect shortcuts in thinking, laziness in loading proper file references, and inconsistent logic/confusion. See [Understanding DAAF — Two Kinds of "Memory"](02_understanding_daaf.md#two-kinds-of-memory) for a deeper explanation of why this happens and what to watch for.

Note that you can check which Claude model is being used by checking the indicator below the chat line (Opus, Sonnet, Haiku). DAAF defaults to using Opus 4.6 with 1 million token context -- no action needed on your part. You can change which Claude model is being used at any time by typing `/model`. All development and testing of this project was done using **Opus 4.5** and **Opus 4.6**. I unfortunately think that these models are absolutely required; other models (Sonnet, Haiku) are cheaper but not nearly as capable and produce erratic, inconsistent results. The complexity of tasks embedded in the DAAF workflow (multi-agent orchestration) relies on the model's ability to follow complex, multi-step protocols reliably. This is also the reason why the Claude Max subscription is a likely prerequisite here: Opus models are very resource-intensive, and it's hard to complete the DAAF workflows under the "Pro" or "Free" tiers accordingly.

Opus 4.6 (unlike Opus 4.5) also allows you to select its "thinking level" by tapping left-and-right arrow keys while Opus 4.6 is selected on the /model selector in Claude Code. All tests I've conducted to date are using the "High" setting -- as this is a case where quality is far more important than quantity, I strongly recommend doing the same. This will have usage and API limit ramifications, though, so it is a reasonable thing to test out the tradeoffs for yourself (inclusive of Sonnet 4.6, which is also a viable experiment for the quality-cost frontier)! Please do report back with any findings so we can incorporate that into our guidance here.

After these settings are done, you're ready to begin working!

### First Launch: Confirming Everything Works

Once you've gotten Claude Code running in your terminal and your model is set, you're ready to start interacting with the DAAF-empowered Claude Code. Before you do anything else, let's confirm that Claude is actually seeing and using all the DAAF resources/guidelines first:

```
Hey Claude, can you tell me more about DAAF? What does it do, and
why is it useful for researchers wanting to use Claude Code for data
analysis work? Give me the elevator pitch for a newcomer
```

If setup was successful and everything went through correctly, you should get back something quite specific and descriptive to the effect of:

```
DAAF: Data Analyst Augmentation Framework
The Elevator Pitch
DAAF is an agent orchestration system built on top of Claude Code
that transforms it from a general-purpose coding assistant into a
rigorous, reproducible research pipeline. It's designed for
researchers who want AI-assisted data analysis but can't afford
the typical pitfalls: hallucinated results, unreproducible workflows,
silent data errors, or black-box methodology.

The Problem It Solves
When researchers use LLMs for data analysis, several things go wrong:
1. No validation discipline — the AI writes a transformation, moves on,
and nobody checks if it corrupted the data
2. No audit trail — you get a result but can't trace how it was derived
or what decisions were made along the way
3. Context collapse — long analyses exhaust the AI's context window,
leading to forgotten constraints and degraded output quality
4. Scope drift — the AI quietly expands or changes the analysis
without the researcher noticing
5. No reproducibility — if you wanted to re-run the analysis or hand
it to a colleague, you couldn't

How DAAF Addresses This
DAAF wraps Claude Code in a multi-agent pipeline with 12 stages across
5 phases...
```

On first run, it should present you with a user acknowledgment statement telling you more about your responsibilities in using DAAF, and then it should jump right in. You should get something equally specific to the above after confirming. 

Talking conversationally with Claude in this way is one easy way you could get oriented to using DAAF. Ask it questions, dig into features, talk about pros and cons, and so on. It will intelligently reference both the user documentation and the workflow documentation as relevant (but it never hurts to remind it, "Based on a thorough read of the DAAF project documentation, can you tell me...?").

From here, you can interact with Claude the same way you would with any AI assistant, but it'll "kick in" its DAAF-powered workflows and skillsets whenever relevant to supercharge anything related to data analysis work, data documentation spelunking, data exploration, and so on. If you want a gentle onboarding guide for actually using DAAF, head to [**02. Understanding and Working with DAAF**](02_understanding_daaf.md) next. 

The rest of this guide covers basic day-to-day workflows, file management, keeping DAAF updated, and advanced configuration options — browse those at your own pace.

> **Quick tip before you go any further**: Now that you have Claude Code up and running with DAAF, you can actually start asking Claude for help! If you have any questions, concerns, issues, or confusion about **anything** you read in this guide or other parts of the User Documentation: Ask Claude about it! DAAF has a dedicated **User Support** mode for exactly this -- just ask it what DAAF is, how something works, or what to do when you're stuck, and it will load its own documentation and walk you through it in plain language. This includes questions about the underlying tools too -- Docker, Git, Claude Code -- it can look up official documentation for those online when needed. Point it to any document, section, or sentence, and then ask it to help you understand it better. It has visibility into the whole project documentation at-will, so it should be able to help you out as you go. This kind of personalized assistance should be invaluable for anyone getting onboarded into using DAAF and Claude Code more generally!

---

## Day-to-Day Start/Stop Workflow

### Starting a New Session

Once you've completed the installation, your daily workflow is just to open your terminal again and run a single command. Make sure Docker Desktop is running first!

**Quick start (recommended):**

**macOS / Linux (Terminal):**

```bash
cd daaf-docker
bash run_daaf.sh
```

**Windows (PowerShell):**

```powershell
cd daaf-docker
.\run_daaf.ps1
```

The `run_daaf` script handles everything: starts the container if it's not already running, then launches Claude Code directly. To enter the container shell instead of Claude Code (for manual commands, setting API keys, etc.), pass `bash` as an argument:

```bash
bash run_daaf.sh bash        # macOS / Linux
.\run_daaf.ps1 bash          # Windows
```

**Manual alternative (if you prefer individual commands):**

```bash
# Navigate to your daaf-docker folder (wherever you ran the installer)
cd daaf-docker

# Start the container (if it's not already running)
docker compose up -d
# Enter the container
docker compose exec daaf-docker bash
# Launch Claude Code
claude
```

### Quick Reference

| Operation | macOS / Linux | Windows |
|-----------|---------------|---------|
| Start session | `bash run_daaf.sh` | `.\run_daaf.ps1` |
| End session | `/exit` → `exit` → `docker compose down` | Same |
| Browse/edit files | `bash run_vscode.sh` | `.\run_vscode.ps1` |
| View notebooks | `bash view_notebooks.sh` | `.\view_notebooks.ps1` |
| View session logs | `bash view_logs.sh` | `.\view_logs.ps1` |
| Back up research | `bash backup_daaf.sh` | `.\backup_daaf.ps1` |
| Update DAAF | `bash update_daaf.sh` | `.\update_daaf.ps1` |


---

## How to Manage DAAF Project Files and Output

Your research files, data, and outputs live inside the **Docker volume** we created during installation — a storage area managed by Docker. Think of the `daaf-docker/` folder on your computer as just the "recipe" that was used to set everything up, while the Docker volume is the actual "kitchen" where all the work happens.

This means:
- **Your work persists** — stopping or restarting the Docker container does NOT delete anything. The Docker volume retains all your research outputs, data, and notebooks across restarts, rebuilds, and even `docker compose down`.
- **Files don't automatically appear on your computer** — unlike a traditional shared folder, files created inside the container are stored in the Docker volume, not directly on your desktop. To access them directly, you can use the included file editor (VSCode -- see below).
- **Only the Docker volume is accessible to Claude** — Claude can only see what's in the Docker volume. Your documents, photos, and everything else are completely isolated.

### Viewing and Editing Files

The easiest way to browse, edit, and manage your files is with DAAF's built-in **browser-based code editor** (VS Code in the browser). Run this from your `daaf-docker` folder on your computer (no need to enter the container):

```bash
cd daaf-docker
bash run_vscode.sh              # macOS / Linux
.\run_vscode.ps1                # Windows
```

This opens a full VS Code editor at the URL [http://localhost:2720](http://localhost:2720) running in your favorite browser where you can explore the entire DAAF file tree, edit files, preview Markdown reports, view/edit Python scripts, and track changes with the built-in Git tools. It comes pre-loaded with extensions for Python syntax highlighting, Markdown preview, Git history visualization, and CSV viewing. The password is displayed in the terminal when you launch the script (default: `daaf`). A few things worth highlighting:

- **The default access password is "daaf"** but the password can be customized at any time in your environment_settings.txt file. See the environment_settings_example.txt in your daaf-docker folder for instructions there.
- **Markdown preview:** Right-click any `.md` file and select **"Open Preview"**, or press `Shift+Ctrl+V`, to see rendered Markdown with proper formatting — headers, tables, links, and all. This is the easiest way to read DAAF's reports and plans.
- **File management:** Use the file explorer sidebar to browse, create, rename, move, and delete files. You can also drag and drop files from your computer into the sidebar to import them into the Docker volume.
- **Git integration:** The Source Control panel (left sidebar) shows uncommitted changes, lets you view diffs, and browse commit history — useful for reviewing what DAAF produced during a session.
- **Search:** Use `Ctrl+Shift+F` (or `Cmd+Shift+F` on Mac) to search across all files — helpful for finding specific variables, scripts, or content across a project.

**Importing files into the Docker volume:** To bring files from your computer into the Docker volume for DAAF to use (e.g., a dataset you want to profile), you can simply drag and drop files into the code editor's file explorer sidebar. You can also download files by right-clicking them and selecting Download.

You can also use the Docker Desktop GUI to explore the DAAF docker volume by navigating to the Volumes panel, clicking the daaf_daaf-data volume, and interacting with the file navigator here.

### Backing Up Your Work

Since your research files live inside the Docker volume, it'll be extremely important to regularly back up your work separately from the Docker volume. The easiest way is with the included backup script:

**macOS / Linux (Terminal):**

```bash
cd daaf-docker
bash backup_daaf.sh
```

**Windows (PowerShell):**

```powershell
cd daaf-docker
.\backup_daaf.ps1
```

The backup script creates a date-versioned folder (e.g., `2026-04-21_daaf_backup/`) in your `daaf-docker` directory. Multiple backups on the same day are automatically suffixed (`2026-04-21a_daaf_backup/`, `2026-04-21b_daaf_backup/`, etc.). Feel free to move or copy these folders to another location on your computer (or an external drive) for safekeeping, or share them with colleagues as needed for collaboration purposes.

You can also back up manually using Docker Desktop's GUI: go into the Docker volume file viewer (see above) and download the whole `daaf` or `research` folder to somewhere else on your computer.

### Restoring from a Backup

If you need to restore your DAAF installation from a backup, use the included restore script. It searches your `daaf-docker` folder for backup folders, lets you pick one, and handles replacing the Docker volume contents cleanly.

**macOS / Linux (Terminal):**

```bash
cd daaf-docker
bash restore_from_backup.sh
```

**Windows (PowerShell):**

```powershell
cd daaf-docker
.\restore_from_backup.ps1
```

**Important:** Restoring is a destructive operation -- the script completely erases the current Docker volume contents and replaces them with the backup. Make sure DAAF is not running when you restore (run `docker compose down` first if needed). The script checks for running containers and warns you if any are active.

**A note on git and DAAF:** A full git repository is set up inside the Docker volume during installation (via the `git clone` in the installer). During research sessions, DAAF's agents will make **local git commits** inside the container to track every script version, data transformation, and plan update — this creates a detailed audit trail of your research that you can review with standard git tools (like `git log`). A remote is configured by default (pointing to the upstream DAAF repository for updates), but nothing is ever pushed there without your explicit instruction. Your research work lives safely in the Docker volume, and the local git history is there purely for traceability and reproducibility within your own projects. If you want a GitHub backup for your work, ask Claude how to make your own repository and save to it accordingly.

### Viewing Session Logs in Your Browser

DAAF includes an interactive timeline viewer (the **DAAF Log Explorer**) that lets you visually explore what happened during any session -- every tool call, subagent dispatch, and file reference, organized chronologically.

**Quickest way -- from your host machine (no container shell needed):**

```bash
cd daaf-docker
bash view_logs.sh            # macOS / Linux
.\view_logs.ps1              # Windows
```

This starts the container (if needed), generates the manifest from all sessions in the overarching session logs folder, and starts the server. Open the URL it prints in your browser. Press Ctrl+C to stop.

**From inside the container** (for per-project viewing):

```bash
# 1. Copy and collect relevant logs into your project (if not already done)
bash /daaf/scripts/collect_session_logs.sh /daaf/research/YYYY-MM-DD_Your_Project

# 2. Generate the project-specific manifest and start the server
bash /daaf/scripts/generate_log_viewer.sh /daaf/research/YYYY-MM-DD_Your_Project
```

Port 2719 is mapped in `docker-compose.yml` for this purpose, alongside port 2718 (Marimo notebooks).

### Viewing Marimo Notebooks in Your Browser

DAAF uses a python library called "marimo" to create streamlined python code "notebooks" as part of its analysis. It can also use this library to create nice, interactive dashboards for you of analyses it has completed.

**Quickest way — from your host machine (no container shell needed):**

```bash
cd daaf-docker
bash view_notebooks.sh       # macOS / Linux
.\view_notebooks.ps1         # Windows
```

This opens marimo's built-in notebook browser at [http://localhost:2718](http://localhost:2718), where you can browse all your research projects and open any notebook for viewing or editing. The script handles starting the container if it isn't already running. The nice thing about these is that they're also written in regular Python code, so you can inspect its code very easily in any text editor as well.

---

## Keeping DAAF Updated

DAAF is actively being developed and updated. If you'd like to pull in the latest fixes, extensions, and updates (which for a while may be as often as daily!!), updating is straightforward. Before updating, I recommend backing up your Docker volume's research folder as a precaution (see "Backing Up Your Work" above).

### If you installed with the one-line installer (recommended method)

Assuming you used `install.sh` or `install.ps1`, your DAAF container has a full git repository with a remote configured. Updating is a single command run from your `daaf-docker` folder on the host:

```bash
cd daaf-docker

bash update_daaf.sh          # macOS / Linux
.\update_daaf.ps1            # Windows
```

The update script handles everything for you:
- **Offers to back up first** — runs `backup_daaf` to create a full copy of your Docker volume before making any changes
- **Checks for the GitHub remote copy** — if you used the manual install (no remote), it tells you how to add one
- **Fetches and compares** — shows you how many new commits are available
- **Checks for local edits** — if you've customized any framework files (CLAUDE.md, a skill, a template, etc.), it shows you exactly what you changed and presents options instead of overwriting anything
- **Handles local commits** — if you've committed your own changes, it offers to merge or rebase them with the update
- **Pulls safely** — if there are no local changes, it pulls the latest updates automatically
- **Offers Claude Code for conflicts** — if a merge conflict occurs, you can launch Claude Code directly to help resolve it interactively
- **Syncs utility scripts** — automatically copies any updated host-side scripts (run, backup, rebuild, update) from the container
- **Auto-rebuilds if needed** — if the Dockerfile or docker-compose.yml changed, it offers to run `rebuild_daaf` automatically

By default, the update script auto-detects the remote's default branch (`main` or `master`). If you installed from a specific branch (e.g., `dev`) and want to keep updating from that branch, set the `DAAF_BRANCH` environment variable:

```bash
# macOS / Linux
DAAF_BRANCH=dev bash update_daaf.sh

# Windows PowerShell
$env:DAAF_BRANCH = "dev"; .\update_daaf.ps1
```

If `DAAF_BRANCH` is not set, the updater defaults to `main` (or `master` if `main` doesn't exist). The script validates that the specified branch exists on the remote before proceeding.

> **Note:** `DAAF_BRANCH` must be a **branch name** for the updater — not a version tag like `v2.1.0`. Tags are fixed snapshots and cannot receive updates. If you installed from a tag, the updater will automatically pull from `main` when `DAAF_BRANCH` is not set. You can use tags with the installer (see "Installing a specific version or branch" below), but for ongoing updates, use the default or specify a branch.

Your research files in `research/` are not tracked by git (they're local to your volume), so they are completely unaffected by updates.

**If the Dockerfile changed** (new packages, updated Claude Code version, etc.), you'll also need to rebuild the Docker image. The update script will detect this automatically and print instructions. 

```bash
# From your host terminal, navigate to your daaf-docker folder and rebuild
cd daaf-docker
bash rebuild_daaf.sh         # macOS / Linux
.\rebuild_daaf.ps1           # Windows
```

The rebuild script handles everything: it copies the updated Dockerfile and docker-compose.yml from the container to the host, then rebuilds the image. This copy step is needed because `docker compose up --build` reads the host copy of the Dockerfile, not the one inside the container.

Most updates don't change the Dockerfile, so usually `git pull` inside the container is all you need.

**Prefer to update to specific releases only?** If you'd rather update in discrete, tested versions instead of tracking the latest changes on `main`, you can check out a specific tag:

```bash
# Inside the container
git fetch --tags
git checkout v2.1.0
```

Check the [Releases page](https://github.com/DAAF-Contribution-Community/daaf/releases) to see what's changed in each version.

### Migrating from an older installation

If you installed DAAF **v2.0.1 or earlier** — back when the installation process involved downloading a ZIP file and copying it into Docker — you may not have the update scripts (`update_daaf.sh` / `update_daaf.ps1`) in your `daaf-docker` folder. Without these scripts, you can't use the standard update process described above.

**How to tell if this applies to you:** Open your `daaf-docker` folder on your computer (wherever you originally set up DAAF). If you don't see a file called `update_daaf.sh` (macOS/Linux) or `update_daaf.ps1` (Windows), you need to run the one-time update migration first.

**What the migration does:**

- Downloads some utility scripts (`run_daaf`, `update_daaf`, `backup_daaf`, `restore_from_backup`, `rebuild_daaf`, `view_logs`, `view_notebooks`, `run_vscode`) to your host machine so you have all the same convenience tools as a fresh install
- Creates a full backup of your Docker volume before making any changes
- Connects your local git history to the official DAAF repository so that future updates can merge in cleanly
- Preserves everything — your research files, any framework customizations you've made, and your full git audit trail are all kept intact

**Running the migration:**

The migration is a single command, just like the original installer. Make sure Docker Desktop is running, open your terminal, navigate to your `daaf-docker` folder, and run:

| Platform | One-liner |
|----------|-----------|
| **macOS / Linux** | `curl -fsSL https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/migrate_daaf.sh \| bash` |
| **Windows PowerShell** | `irm https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/migrate_daaf.ps1 \| iex` |

The migration script is safe to re-run if it gets interrupted — it detects what's already been completed and picks up where it left off. Your research files are never modified; only git metadata (the connection to the upstream repository) is updated.

**After migration:** You'll have all the same utility scripts as a fresh install. From this point forward, you can use `update_daaf.sh` / `update_daaf.ps1` for all future updates, exactly as described in the section above.

---

## Advanced Installation & Configuration

The sections below cover additional installation options for users with specific needs. If you completed the standard installation above and everything is working, you can skip this entire section and come back later if and when you need it.

### Installing a specific version or branch

By default, the installer pulls the latest code from the `main` branch. To install a specific release or branch instead, set the `DAAF_BRANCH` environment variable before running the installer:

**macOS / Linux (Terminal):**

```bash
# Install a tagged release
export DAAF_BRANCH=v2.1.0
curl -fsSL "https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/${DAAF_BRANCH}/scripts/host/install.sh" | bash

# Install from a development branch
export DAAF_BRANCH=dev
curl -fsSL "https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/${DAAF_BRANCH}/scripts/host/install.sh" | bash
```

**Windows (PowerShell):**

```powershell
# Install a tagged release
$env:DAAF_BRANCH="v2.1.0"; irm "https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/$env:DAAF_BRANCH/scripts/host/install.ps1" | iex

# Install from a development branch
$env:DAAF_BRANCH="dev"; irm "https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/$env:DAAF_BRANCH/scripts/host/install.ps1" | iex
```

This fetches the installer itself from the specified branch or tag, and also controls the Docker build files and repository clone, so everything comes from the specified ref consistently. The `export` on macOS/Linux is required so that the variable is inherited by the `bash` process on the other side of the pipe. Check the [Releases page](https://github.com/DAAF-Contribution-Community/daaf/releases) to see available versions. If `DAAF_BRANCH` is not set, the installer defaults to `main`.

> **Note:** The installer accepts both branch names and version tags, but the **updater** (`update_daaf.sh` / `update_daaf.ps1`) only accepts branch names. If you install from a tag, you do not need to set `DAAF_BRANCH` when updating — the updater will automatically pull from `main`.

### Re-installing DAAF

If you run the installer on a system where DAAF is already installed, it will detect the existing installation and stop with a warning. This is a safety feature — re-running the installer would overwrite your framework files (CLAUDE.md, skills, agents, templates) and local git history, though your research data in `research/` would not be deleted.

**To update DAAF** (recommended — preserves your local changes), use the update script instead:

```bash
cd daaf-docker
bash update_daaf.sh          # macOS / Linux
.\update_daaf.ps1            # Windows
```

See [**Keeping DAAF Updated**](#keeping-daaf-updated) for details on what the update script does.

**To force a complete re-install** (overwrites all framework files), set the `DAAF_FORCE_REINSTALL` environment variable:

**macOS / Linux:**
```bash
DAAF_FORCE_REINSTALL=1 bash -c "$(curl -fsSL https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/install.sh)"
```

**Windows (PowerShell):**
```powershell
$env:DAAF_FORCE_REINSTALL = "1"; irm https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/install.ps1 | iex
```

Back up your Docker volume first (see [**Backing Up Your Work**](#backing-up-your-work)) if you have research data or framework customizations you want to preserve.

If the installer detects a previous attempt that didn't complete successfully (e.g., the Docker build failed partway through), it will note this and proceed automatically — no override needed.

### Configure authentication via environment_settings.txt

By default, Claude Code prompts you to log in interactively the first time you launch it (browser-based OAuth or pasting an API key). This works great for Max subscription and direct API key setups. However, if you're using **OpenRouter**, a **cloud provider** (Bedrock/Vertex), or simply want your authentication to persist automatically without interactive login, you can configure it through the `environment_settings.txt` file in your `daaf-docker` folder.

Your `daaf-docker` folder includes an `environment_settings_example.txt` template that documents all five supported authentication methods with the exact environment variables needed for each. To set it up:

1. **Copy the template** (if you haven't already):

   **macOS / Linux (Terminal):**
   ```bash
   cd daaf-docker
   cp environment_settings_example.txt environment_settings.txt
   ```

   **Windows (PowerShell):**
   ```powershell
   cd daaf-docker
   Copy-Item environment_settings_example.txt environment_settings.txt
   ```

2. **Open `environment_settings.txt` in any text editor** and uncomment the section matching your authentication method. For example, to use OpenRouter:
   ```bash
   # --- Option C: OpenRouter (third-party model gateway) ---
   ANTHROPIC_BASE_URL=https://openrouter.ai/api
   ANTHROPIC_AUTH_TOKEN=your_openrouter_api_key_here
   ANTHROPIC_API_KEY=
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   ```
   Replace `your_openrouter_api_key_here` with your actual OpenRouter API key (format: `sk-or-v1-...`). Get one at [openrouter.ai/settings/keys](https://openrouter.ai/settings/keys). Note that `ANTHROPIC_API_KEY=` must be set to an empty value (not removed entirely) — this tells Claude Code to use the auth token instead of trying to authenticate directly with Anthropic.

3. **Restart the container** to pick up the changes:
   ```bash
   docker compose down
   bash run_daaf.sh            # macOS / Linux
   .\run_daaf.ps1              # Windows
   ```

4. **If you previously logged in interactively** with Anthropic, run `/logout` inside Claude Code before switching to an `environment_settings.txt`-based method — cached credentials can take priority over environment variables.

> **Only uncomment ONE authentication section.** If multiple methods are set, Claude Code uses the highest-priority one (see the priority order documented in `environment_settings_example.txt`). This can lead to unexpected billing if, for example, you have both an API key and an OAuth token set.

> **Note:** The `environment_settings.txt` file is also where you'll configure data source API keys (covered in the next section). Both authentication and data source credentials live in the same file and are loaded together when the container starts.

### Set up data source API keys

Most DAAF data sources — including all built-in education data from the Urban Institute — are **freely accessible with no authentication required**. You can skip this step entirely if you're only working with education data.

However, some data domains require API keys from their hosting platforms. The table below shows API keys for data sources that ship with DAAF. When you onboard a new data source from an API via Data Onboarding Mode, DAAF will guide you through setting up the appropriate environment variable using the same pattern shown here. You can set multiple API keys simultaneously — each uses a unique environment variable name.

| Data Source | Environment Variable | Where to Get a Key |
|-------------|---------------------|-------------------|
| County Presidential Election Returns (Harvard Dataverse) | `HARVARD_DATAVERSE_API_KEY` | [dataverse.harvard.edu](https://dataverse.harvard.edu/) → Log in → Account name (top-right) → API Token → Create Token |

#### Recommended: Use an environment_settings.txt file (persistent across restarts)

Your `daaf-docker` folder includes an `environment_settings_example.txt` template. Copy it to `environment_settings.txt` and fill in your keys:

**macOS / Linux (Terminal):**
```bash
cd daaf-docker
cp environment_settings_example.txt environment_settings.txt
```

**Windows (PowerShell):**
```powershell
cd daaf-docker
Copy-Item environment_settings_example.txt environment_settings.txt
```

Then open `environment_settings.txt` in any text editor and uncomment/fill in the keys you need:

```bash
# Remove the leading # and replace the placeholder with your actual key
HARVARD_DATAVERSE_API_KEY=your_token_here
```

The `environment_settings.txt` file is loaded automatically when the container starts. Edits to `environment_settings.txt` are not applied while the container is running — you need to recreate it to pick up changes:

```bash
docker compose down
bash run_daaf.sh            # macOS / Linux
.\run_daaf.ps1              # Windows
```

> **Security note:** The `environment_settings.txt` file lives on your host machine (in `daaf-docker/`), is gitignored by default, and is never visible to Claude inside the container. DAAF's safety guardrails prevent Claude from reading or writing environment settings files by design — your credentials stay strictly on your side of the boundary.

#### Alternative: Set keys manually in the container shell

If you prefer not to use an `environment_settings.txt` file, you can set environment variables directly inside the container before launching Claude Code:

```bash
# Enter the container shell
bash run_daaf.sh bash        # macOS / Linux
.\run_daaf.ps1 bash          # Windows

# Set the key for this session
export HARVARD_DATAVERSE_API_KEY="your_token_here"

# Then launch Claude Code
claude
```

To make manual exports persist across container restarts, add the `export` line to `~/.bashrc` inside the container:

```bash
echo 'export HARVARD_DATAVERSE_API_KEY="your_token_here"' >> ~/.bashrc
```

Note that the `environment_settings.txt` file approach above is simpler and recommended — it persists automatically and you can edit it with your normal text editor on your computer without entering the container.

If you skip this step and later try to analyze election data, DAAF will inform you that the API key is missing and point you back to these instructions.

---

## Setup Troubleshooting

> **Tip:** If you run into an issue not listed here, or you want more help understanding any of these errors, try asking DAAF directly -- its **User Support** mode can help troubleshoot Docker, Git, and Claude Code problems and can look up the latest official documentation online.

- **"docker: The term 'docker' is not recognized as the name of a cmdlet, function, script file, or operable program" or "docker: command not found"** — Make sure you have Docker installed successfully. You may need to restart your computer after installation for it to fully register in your Terminal.
- **Malformed authentication URL when trying to log in to Claude Code** — If you're trying to copy the URL authentication link, be careful to check it for erroneous line-breaks in the URL. Paste this into a simple notepad editor and remove any extra line-breaks, then try pasting the revised URL into your browser.
- **"unable to get image 'daaf-daaf-docker'"** — Make sure Docker Desktop is running and that the installer completed successfully. If the installer finished without errors, the image should already exist -- you can confirm in the Docker Desktop app Images panel on the left-side toolbar. If it's missing, try running the installer again.
- **"service "daaf-docker" is not running"** — Make sure Docker Desktop is running and that you've started the container. The `run_daaf` script handles this automatically, but you can also confirm the container is running in the Docker Desktop app Containers panel on the left-side toolbar. If the container isn't listed, try running the installer again.
- **Container seems really slow to build the first time** — The initial installation downloads base images and installs all packages. This is a one-time cost — subsequent starts are fast since Docker caches everything.
- **"I can't find my research files on my computer"** — With Docker volumes, your research files live inside Docker's managed storage, not in the project folder on your computer. See **How to Manage DAAF Project Files and Output** above for more information.
- **"Port 2718 already in use" when trying to view Marimo notebooks** — Another process is using that port. Either stop it, or change the port mapping in `docker-compose.yml` (e.g., `"127.0.0.1:3000:2718"` to use port 3000 on your host).
- **"Port 2719 already in use" when trying to view session logs** — Same fix: stop the conflicting process, or change the port mapping (e.g., `"127.0.0.1:3001:2719"`). Port 2719 is used by the DAAF Log Explorer (`generate_log_viewer.sh`).
- **"Port 2720 already in use" when trying to open the browser-based code editor** — Same fix: stop the conflicting process, or change the port mapping (e.g., `"127.0.0.1:3002:2720"`). Port 2720 is used by the browser-based code editor (`run_vscode.sh` / `run_vscode.ps1`).
- **Permission denied errors inside the container (especially on macOS)** — If you see errors like `Permission denied` when Claude tries to read or write files, the Docker volume likely has files owned by root or your host UID instead of the container's `appuser` (UID 1000). This is a known issue with Docker Desktop on macOS. The `docker-compose.yml` includes an init service (`daaf-init`) that automatically fixes file ownership on every startup. To resolve this: stop the container (`docker compose down`), then restart it (`docker compose up -d`) — the init service will repair permissions before the main container starts. If you still have issues, you can fix permissions manually:
  ```bash
  docker run --rm -v "daaf_daaf-data:/daaf" busybox chown -R 1000:1000 /daaf
  ```
- **Claude Code asks for an API key every time** — Claude Code stores its authentication state inside the Docker volume, so it persists across normal container restarts. If your authentication state is lost, the most reliable fix is to configure your credentials in the `environment_settings.txt` file (see [**Configure authentication via environment_settings.txt**](#configure-authentication-via-environment_settingstxt) above) — this ensures authentication persists automatically on every container start. Alternatively, you can add your key to `~/.bashrc` inside the container: `echo 'export ANTHROPIC_API_KEY="your_key_here"' >> ~/.bashrc`.
- **OpenRouter: "model not found" or authentication errors** — Double-check three things: (1) `ANTHROPIC_BASE_URL` must be exactly `https://openrouter.ai/api` with no `/v1` suffix (the `/v1` variant is for OpenAI-compatible tools, not Claude Code), (2) `ANTHROPIC_API_KEY` must be set to an empty value (`ANTHROPIC_API_KEY=`), not removed entirely — if it's unset, Claude Code falls back to Anthropic's servers, and (3) if you previously logged in with Anthropic interactively, run `/logout` inside Claude Code to clear cached credentials. You can verify your connection is working by typing `/status` inside Claude Code and checking the [OpenRouter Activity Dashboard](https://openrouter.ai/activity) for incoming requests.

---

## Recommended Next Steps

- [**02. Understanding and Working with DAAF**](02_understanding_daaf.md) — Learn to work with DAAF for the first time: what to expect, how to use it, and how to test its strengths and limitations
- [**06. FAQ: Philosophy**](06_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**07. FAQ: Technical Support**](07_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, authentication errors, and other common errors

---

[**Back to main**](https://github.com/DAAF-Contribution-Community/daaf/tree/main)
