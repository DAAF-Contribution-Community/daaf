# 01. Installation & Quick Start

This is the complete first-time installation and setup guide for DAAF. This document covers every step from installing prerequisites to running your first session, as well as tips for file management, viewing compiled research script notebooks, and troubleshooting.

[**Back to main**](https://github.com/DAAF-Contribution-Community/daaf/tree/main)

---

## Table of Contents
- [**Prerequisites**](#prerequisites)
- [**Installing DAAF**](#installing-daaf)
- [**Day-to-Day Start/Stop Workflow**](#day-to-day-startstop-workflow)
- [**How to Manage DAAF Project Files and Output**](#how-to-manage-daaf-project-files-and-output)
- [**Keeping DAAF Updated**](#keeping-daaf-updated)
- [**Viewing Marimo Notebooks in Your Browser**](#viewing-marimo-notebooks-in-your-browser)
- [**Viewing Session Logs in Your Browser**](#viewing-session-logs-in-your-browser)
- [**Setup Troubleshooting**](#setup-troubleshooting)
- [**Recommended Next Steps**](#recommended-next-steps)

---

## Prerequisites

Before installing DAAF, there are three (technically four) key prerequisites. Please read the Anthropic account requirement especially closely; the price of the necessary subscription is definitively the highest barrier to entry at this time. I hope this will change in the near future with greater testing and community support for open-source models!

### 0. A computer with internet access

You'll need internet access to download the project files and interact with DAAF/Claude (which itself always requires internet). Datasets will also be downloaded from the Urban Institute Education Data Portal as you conduct research work, which will also require an internet connection. Note that all data analyses will be conducted using your actual computer hardware, so you should have a computer that's generally capable of running intermediate-level data analysis (same sort of requirements you'd face if you wanted to analyze these same datasets in R/Stata/Python regularly). Don't worry about actual R/Stata/Python packages/libraries/dependencies, that's all handled carefully for you behind the scenes!

### 1. Anthropic Account & Authentication

Claude Code is the AI assistant that powers this project. It runs inside your terminal (not in a web browser) and needs to link in with an Anthropic account for billing/usage purposes. Because we're relying on cutting-edge frontier models and asking them to do a **LOT** of thorough work for us (deep-diving into data, writing a lot of code, checking a lot of code, rewriting code, writing intensive plans, etc., etc.), we need to have a **high-usage** Anthropic account. Unfortunately, the free and standard "Pro"-level plans will simply not be sufficient for the time being; given current pricing at $100-200/mo, this is the biggest barrier-to-entry for engaging in this work.

For the account setup, that means you have two main options:

- **Anthropic Max subscription** — [Get one here](https://claude.com/pricing/max), or if you already have an active Anthropic account, you can [upgrade your plan here](https://claude.ai/upgrade). I rarely hit my usage limits running multiple projects at once on the $200/mo plan; your mileage may vary on the $100/mo plan. You can also use an existing Team or Enterprise subscription, but your mileage may vary substantially there too based on your exact organizational settings/limits.
- **Anthropic API key** — [Get one here](https://console.anthropic.com/). This is a pay-per-use key that you'll paste into Claude Code when prompted. This allows unlimited use as long as you're willing to pay -- but this can get VERY expensive, *very* quickly. A fairly straightforward descriptive analysis with relatively few dataset joins via raw API fees can easily be between $30-60. I HIGHLY recommend getting a Max subscription for this project, instead, as they are explicitly subsidizing these sorts of costs via their subscription model. Initial testing on my end indicates I would have paid roughly 10x more for my usage going with the API key versus just my Max subscription plan.
- **Third-party platform use** — If your company has an Amazon Bedrock or Vertex AI or similar partnership as part of your organizational plan with Anthropic, you can also leverage these settings instead. I'm not familiar enough with this myself and wouldn't be able to support much, but you should follow whatever instructions your plan admins have given you to link your account with Claude Code more generally.

Whichever route you choose, Claude Code will prompt you to choose your authentication method the first time you run it — you don't need to configure anything in advance. You can also always start with one option and change later (e.g., try billing via API for a short test and then transition to a Max subscription); you can adjust your settings by typing `/login` when chatting with Claude. Note that many terminal interfaces "hide" any password-entry you're asked to do, so if you don't see your typing "working," it's working but hiding it from view for your privacy. If you're concerned about privacy otherwise: Nothing (including your credentials) ever leave your computer in the course of this project's workflows, and I've enforced a LOT of safety checks to ensure Claude doesn't accidentally share it with anyone, either. This can be directly verified in the code. 

Finally, note that you can easily port this whole project over to a CLI tool of your choice (OpenCode, Codex, Gemini CLI, etc.) with a little bit of effort (the hooks are really the only hard part -- everything like the agents and skills should port over immediately). Fork this repo, work with your favorite tool to convert it over, and please continue to share it broadly with others!!! I would be excited to have people test this on open-source models, as well -- please reach out if you've got capacity to that end.

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
| Move into a folder in the current directory | `cd foldername` | `cd daaf` |
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

> **Need additional Python packages or tools?** DAAF comes pre-installed with a comprehensive data science stack, but you can add your own packages by editing the Dockerfile and rebuilding. See [**04. Extending DAAF -- Customizing Your Python Environment**](04_extending_daaf.md#customizing-your-python-environment) for step-by-step instructions, including how to test packages at runtime before making them permanent.

**Install:** [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)

---

## Installing DAAF

With all the prerequisites out of the way, installation is a single command that takes about 5 minutes with a decent internet connection. The installer downloads some initial helper files, builds a Docker image with the full data science stack and Claude Code in a fully replicable way, and then downloads the complete DAAF repository into the container so that Claude Code runs using all of the added DAAF files.

### One-Line Install (Recommended)

Make sure Docker Desktop is running, then open your terminal and paste the command for your operating system:

<table>
<tr>
<td><strong>macOS / Linux (Terminal)</strong></td>
<td><strong>Windows (PowerShell)</strong></td>
</tr>
<tr>
<td>

```bash
curl -fsSL https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/install.sh | bash
```

</td>
<td>

```powershell
irm https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/install.ps1 | iex
```

</td>
</tr>
</table>

The installer will show its progress as it works through four steps: creating a build directory, downloading the Docker files, building the image, and cloning DAAF into the container. When it finishes, it prints instructions for entering the container and launching Claude Code.

#### Installing a specific version or branch

By default, the installer pulls the latest code from the `main` branch. To install a specific release or branch instead, set the `DAAF_BRANCH` environment variable before running the installer:

<table>
<tr>
<td><strong>macOS / Linux (Terminal)</strong></td>
<td><strong>Windows (PowerShell)</strong></td>
</tr>
<tr>
<td>

```bash
# Install a tagged release
export DAAF_BRANCH=v2.1.0
curl -fsSL "https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/${DAAF_BRANCH}/install.sh" | bash

# Install from a development branch
export DAAF_BRANCH=dev
curl -fsSL "https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/${DAAF_BRANCH}/install.sh" | bash
```

</td>
<td>

```powershell
# Install a tagged release
$env:DAAF_BRANCH="v2.1.0"; irm "https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/$env:DAAF_BRANCH/install.ps1" | iex

# Install from a development branch
$env:DAAF_BRANCH="dev"; irm "https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/$env:DAAF_BRANCH/install.ps1" | iex
```

</td>
</tr>
</table>

This fetches the installer itself from the specified branch, and also controls the Docker build files and repository clone, so everything comes from the specified branch or tag consistently. The `export` on macOS/Linux is required so that the variable is inherited by the `bash` process on the other side of the pipe. Check the [Releases page](https://github.com/DAAF-Contribution-Community/daaf/releases) to see available versions. If `DAAF_BRANCH` is not set, the installer defaults to `main`.

#### What the installer does

1. **Creates an installation directory** called `daaf-docker/` in whatever folder your terminal is currently in, containing the Dockerfile, docker-compose.yml, and convenience scripts (`run_daaf`, `backup_daaf`, and `rebuild_daaf`). For example, if you open your terminal and it starts in your home folder (`~` on Mac/Linux, `C:\Users\YourName` on Windows), that's where `daaf-docker/` will be created. You can `cd` to a different location first if you'd prefer to install elsewhere.
2. **Builds the Docker image** with Python 3.12, 50+ data science packages, geospatial libraries, and Claude Code pre-installed. The first build downloads everything and takes a few minutes; subsequent rebuilds use Docker's layer cache and are much faster.
3. **Downloads the DAAF repository** directly into the Docker volume inside the container. This gives you a full git repository.
4. **Prints post-install instructions** showing you how to enter the container, launch Claude Code, and configure it.

Behind the scenes, the Docker Compose setup also:

- **Fixes file permissions.** An init service runs before the main container starts, ensuring all files in the Docker volume are owned by the correct user. This prevents "Permission denied" errors, especially on macOS where Docker volumes can end up with mismatched ownership.
- **Pins Claude Code.** The Dockerfile installs a specific, tested version of Claude Code (with auto-updates disabled) to ensure consistent behavior across builds.
- **Enforces security hardening.** The container runs as a non-root user with all Linux capabilities dropped (`cap_drop: ALL`) and privilege escalation explicitly blocked (`no-new-privileges`). Even if Claude Code somehow tried to do something it shouldn't, the operating system kernel would stop it.

You can confirm the install worked by looking at Docker Desktop: in the **Images** panel you should see `daaf-daaf-docker`, and in the **Containers** panel you should see `daaf` with a sub-entry `daaf-docker-1`.

#### Enter the container and launch Claude Code

<table>
<tr>
<td><strong>macOS / Linux (Terminal)</strong></td>
<td><strong>Windows (PowerShell)</strong></td>
</tr>
<tr>
<td>

```bash
cd daaf-docker
bash run_daaf.sh
```

</td>
<td>

```powershell
cd daaf-docker
.\run_daaf.ps1
```

</td>
</tr>
</table>

The `run_daaf` script starts the container if needed and launches Claude Code directly. To enter the container shell instead (e.g., for setting API keys), pass `bash` as an argument: `bash run_daaf.sh bash` (or `.\run_daaf.ps1 bash` on Windows). You can also use the manual commands if you prefer: `docker compose exec daaf-docker bash` to enter the container, then `claude` to launch.

On first launch, Claude Code should prompt you to authenticate (API key or subscription login). Follow its instructions to complete the process as needed based on your method. Remember that CTRL+C actually exits the terminal, so use (Windows/Linux: CTRL+SHIFT+C and CTRL+V) and (macOS: Cmd+C and Cmd+V) if you want to copy/paste.

#### Configure Claude Code (required)

Once you're in, there are a few settings to adjust to ensure that the workflow is able to operate as expected. First, type the following into Claude's chat window:

```bash
/config
```

And then change the **"Auto-compact"** setting to **False** and **"Verbose output"** setting to **True** by navigating down with your arrow keys and hitting Enter when the option is selected. When the settings are changed correctly, you can then hit the ESC key to return to the regular Claude chat and begin working.

**Recommended model:** You can check which Claude model is being used by checking the indicator below the chat line (Opus, Sonnet, Haiku). You can change which Claude model is being used at any time by typing `/model`. All development and testing of this project was done using **Opus 4.5** and **Opus 4.6**. I unfortunately think that these models are absolutely required; other models (Sonnet, Haiku) are not nearly as capable and produce erratic, inconsistent results. The complexity of tasks embedded in the DAAF workflow (multi-agent orchestration) relies on the model's ability to follow complex, multi-step protocols reliably. This is also the reason why the Claude Max subscription is a likely prerequisite here: Opus models are very resource-intensive, and it's hard to complete the DAAF workflows under the "Pro" or "Free" tiers accordingly.

Opus 4.6 (unlike Opus 4.5) also allows you to select its "thinking level" by tapping left-and-right arrow keys while Opus 4.6 is selected on the /model selector in Claude Code. All tests I've conducted to date are using the "High" setting -- as this is a case where quality is far more important than quantity, I strongly recommend doing the same. This will have usage and API limit ramificiations, though, so it is a reasonable thing to test out the tradeoffs for yourself! Please do report back with any findings so we can incorporate that into our guidance here.

### Optional: Set up data source API keys

Most DAAF data sources — including all built-in education data from the Urban Institute — are **freely accessible with no authentication required**. You can skip this step entirely if you're only working with education data.

However, some data domains require API keys from their hosting platforms. The table below shows API keys for data sources that ship with DAAF. When you onboard a new data source from an API via Data Onboarding Mode, DAAF will guide you through setting up the appropriate environment variable using the same pattern shown here. You can set multiple API keys simultaneously — each uses a unique environment variable name.

If you plan to use any of these data sources, you'll need to set the corresponding environment variable **inside the Docker container, before launching Claude Code**:

| Data Source | Environment Variable | Where to Get a Key |
|-------------|---------------------|-------------------|
| County Presidential Election Returns (Harvard Dataverse) | `HARVARD_DATAVERSE_API_KEY` | [dataverse.harvard.edu](https://dataverse.harvard.edu/) → Log in → Account name (top-right) → API Token → Create Token |

To set a key for your current session:

```bash
# Run this inside the Docker container, BEFORE running `claude`
export HARVARD_DATAVERSE_API_KEY="your_token_here"
```

To make it persist across container restarts, add the `export` line to `~/.bashrc` inside the container:

```bash
echo 'export HARVARD_DATAVERSE_API_KEY="your_token_here"' >> ~/.bashrc
```

> **Note:** DAAF's safety guardrails prevent Claude from reading or writing `.env` files, so environment variables must be set directly in the shell. This is by design — your credentials stay in temporary memory only and are never written to files that could be accidentally committed to a public repository or shared outside the container.

If you skip this step and later try to analyze election data, DAAF will inform you that the API key is missing and point you back to these instructions.

---

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

I promise that's genuinely the first response I got back while testing this! Talking conversationally with Claude in this way is one easy way you could get oriented to using DAAF. Ask it questions, dig into features, talk about pros and cons, and so on. It will intelligently reference both the user documentation and the workflow documentation as relevant (but it never hurts to remind it, "Based on a thorough read of the DAAF project documentation, can you tell me...?"). 

From here, you can interact with Claude the same way you would with any AI assistant, but it'll "kick in" its DAAF-powered workflows and skillsets whenever relevant to supercharge anything related to data analysis work, data documentation spelunking, data exploration, and so on. If you want a gentle onboarding guide for actually using DAAF (fully written by a human for other humans!), we'll cover that in the next section: [**02. Understanding and Working with DAAF**](02_understanding_daaf.md). I used to be a high school English teacher, so this is the fun part for me, honestly. 

That being said, let's go over just a few more technical details and how-to's before we get there.

> **Quick tip before you go any further**: Now that you have Claude Code up and running with DAAF, you can actually start asking Claude for help! If you have any questions, concerns, issues, or confusion about **anything** you read in this guide or other parts of the User Documentation: Ask Claude about it! DAAF has a dedicated **User Support** mode for exactly this -- just ask it what DAAF is, how something works, or what to do when you're stuck, and it will load its own documentation and walk you through it in plain language. This includes questions about the underlying tools too -- Docker, Git, Claude Code -- it can look up official documentation for those online when needed. Point it to any document, section, or sentence, and then ask it to help you understand it better. It has visibility into the whole project documentation at-will, so it should be able to help you out as you go. This kind of personalized assistance should be invaluable for anyone getting onboarded into using DAAF and Claude Code more generally!

---

## Day-to-Day Start/Stop Workflow

Now that you've got DAAF installed and running for the first time, let's talk through simple commands you'll use to get in and out of this workflow day-to-day, as well as how to manage files produced by DAAF.

### Starting a New Session

Once you've completed the installation, your daily workflow is just to open your terminal again and run a single command. Make sure Docker Desktop is running first!

**Quick start (recommended):**

<table>
<tr>
<td><strong>macOS / Linux (Terminal)</strong></td>
<td><strong>Windows (PowerShell)</strong></td>
</tr>
<tr>
<td>

```bash
cd daaf-docker
bash run_daaf.sh
```

</td>
<td>

```powershell
cd daaf-docker
.\run_daaf.ps1
```

</td>
</tr>
</table>

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

### Ending a Session

When you're ready to end a session, you have two options. The first option: Close the terminal window, and then use your Docker Desktop app window to "pause" your Docker container (click the Containers panel in the left-side toolbar, look for "daaf" in the list that appears, hit the "Stop" button). The other option is to do this fully through the terminal:

```bash
# Exit Claude Code first. You can also just press CTRL+C twice
/exit
# That gets you back into the terminal window, running *within* your Docker container.
# You'll know you're still in the Docker container if your command line says something like, "appuser@5jhfdsn54:/daaf$" before whatever you type
# So now let's exit the Docker container
exit
# And then we can turn off the Docker container (make sure you're in the daaf-docker folder)
docker compose down

# You can then just close your terminal. All the DAAF files and research outputs remain safe and persist in the Docker volume we created at installation time
```

## How to Manage DAAF Project Files and Output

Your research files, data, and outputs live inside the **Docker volume** we created during installation — a storage area managed by Docker. Think of the `daaf-docker/` folder on your computer as the "recipe" that was used to set everything up, while the Docker volume is the actual "kitchen" where all the work happens.

This means:
- **Your work persists** — stopping or restarting the container does NOT delete anything. The Docker volume retains all your research outputs, data, and notebooks across restarts, rebuilds, and even `docker compose down`.
- **Files don't automatically appear on your computer** — unlike a traditional shared folder, files created inside the container are stored in the Docker volume, not directly on your desktop. To access them directly, you'll use Docker Desktop or simple copy commands (see below).
- **Only the Docker volume is accessible to Claude** — Claude can only see what's in the Docker volume. Your documents, photos, and everything else are completely isolated.

### Viewing Files in Docker Desktop

The easiest way to browse your files is through Docker Desktop's graphical interface:

1. Open **Docker Desktop**
2. Click **Containers** in the left-side toolbar
3. Click the "expand" arrow on the container named **`daaf`** and then click on the name **`daaf-daaf-docker-1`**
4. Select the **Files** tab to see the file tree
5. Navigate into `daaf` and then `research` to find your project folders

From here, you can download copies of individual folders or files to your computer by right-clicking on them. You can also Import files into the Docker volume from your computer by right-clicking, as well.

### Backing Up Your Work

Since your research files live inside the Docker volume, it'll be extremely important to regularly back up your work separately from the Docker volume. The easiest way is with the included backup script:

<table>
<tr>
<td><strong>macOS / Linux (Terminal)</strong></td>
<td><strong>Windows (PowerShell)</strong></td>
</tr>
<tr>
<td>

```bash
cd daaf-docker
bash backup_daaf.sh
```

</td>
<td>

```powershell
cd daaf-docker
.\backup_daaf.ps1
```

</td>
</tr>
</table>

The backup script creates a date-versioned folder (e.g., `2026-04-21_daaf_backup/`) in your `daaf-docker` directory. Multiple backups on the same day are automatically suffixed (`2026-04-21a_daaf_backup/`, `2026-04-21b_daaf_backup/`, etc.). Move or copy these folders to another location on your computer (or an external drive) for safekeeping.

You can also back up manually using Docker Desktop's GUI: go into the Docker volume file viewer (see above) and download the whole `daaf` or `research` folder to somewhere else on your computer.

**A note on git and DAAF:** A full git repository is set up inside the Docker volume during installation (via the `git clone` in the installer). During research sessions, DAAF's agents will make **local git commits** inside the container to track every script version, data transformation, and plan update — this creates a detailed audit trail of your research that you can review with standard git tools (like `git log`). A remote is configured by default (pointing to the upstream DAAF repository for updates), but nothing is ever pushed there without your explicit instruction. Your research work lives safely in the Docker volume, and the local git history is there purely for traceability and reproducibility within your own projects. If you want a GitHub backup for your work, ask Claude how to make your own repository and save to it accordingly.

### Viewing report Markdown (.md) files

LLM assistants work best on text files, which means that proprietary document formats like Microsoft Word or Google Docs aren't great for this type of work. DAAF produces all its output report documents in Markdown (.md) format. You can open these in any basic text editor, but basic text editors tend not to display the formatting very nicely. I recommend installing a basic Markdown viewer, or you can copy the Markdown text into any free online viewer (e.g., [StackEdit](https://stackedit.io/app)) 

---

## Keeping DAAF Updated

DAAF is actively being developed and updated. If you'd like to pull in the latest fixes, extensions, and updates (which for a while may be as often as daily!!), updating is straightforward. Before updating, I recommend backing up your Docker volume's research folder as a precaution (see "Backing Up Your Work" above).

### If you installed with the one-line installer (recommended method)

If you used `install.sh` or `install.ps1`, your DAAF container has a full git repository with a remote configured. Updating is a single command run inside the container:

```bash
# Navigate to your daaf-docker folder and enter the container shell (if you're not already inside)
cd daaf-docker
bash run_daaf.sh bash        # macOS / Linux
.\run_daaf.ps1 bash          # Windows

# Run the update script
bash /daaf/scripts/update.sh
```

You can also enter the container manually with `docker compose exec daaf-docker bash` if you prefer.

The update script handles everything for you:
- **Checks for a remote** — if you used the manual install (no remote), it tells you how to add one
- **Fetches and compares** — shows you how many new commits are available
- **Checks for local edits** — if you've customized any framework files (CLAUDE.md, a skill, a template, etc.), it shows you exactly what you changed and presents options instead of overwriting anything
- **Pulls safely** — if there are no local changes, it pulls the latest updates automatically
- **Detects Dockerfile changes** — if the Dockerfile or docker-compose.yml changed, it prints the exact copy-back and rebuild commands you need to run on your host

Your research files in `research/` are not tracked by git (they're local to your volume), so they are completely unaffected by updates.

**If you prefer to update manually with git** (or need more control), you can always run `git pull` directly. If you've made local edits, git will warn you about conflicts instead of silently overwriting your changes:

```bash
# Option 1: Save your changes, update, then re-apply
git stash
git pull
git stash pop
# If there are conflicts, git will tell you which files need manual review

# Option 2: See what you changed before deciding
git diff
```

**If the Dockerfile changed** (new packages, updated Claude Code version, etc.), you'll also need to rebuild the Docker image. The update script will detect this automatically and print instructions. If you're updating manually, check whether `Dockerfile` appears in the `git pull` output — if so, exit the container and run the rebuild script:

```bash
# Exit Claude Code and the container
/exit
exit

# From your host terminal, navigate to your daaf-docker folder and rebuild
cd daaf-docker
bash rebuild_daaf.sh         # macOS / Linux
.\rebuild_daaf.ps1           # Windows
```

The rebuild script handles everything: it copies the updated Dockerfile and docker-compose.yml from the container to the host, then rebuilds the image. This copy step is needed because `docker compose up --build` reads the host copy of the Dockerfile, not the one inside the container.

<details>
<summary>Manual alternative (if you prefer individual commands)</summary>

```bash
cd daaf-docker
docker cp daaf-daaf-docker-1:/daaf/Dockerfile ./Dockerfile
docker cp daaf-daaf-docker-1:/daaf/docker-compose.yml ./docker-compose.yml
docker compose up -d --build
```

The copy step must come **before** the rebuild.
</details>

Most updates don't change the Dockerfile, so usually `git pull` inside the container is all you need.

**Prefer to update to specific releases only?** If you'd rather update in discrete, tested versions instead of tracking the latest changes on `main`, you can check out a specific tag:

```bash
# Inside the container
git fetch --tags
git checkout v2.1.0
```

Check the [Releases page](https://github.com/DAAF-Contribution-Community/daaf/releases) to see what's changed in each version.

---

## Viewing Marimo Notebooks in Your Browser

The assistant uses a python library called "marimo" to create streamlined python code "notebooks" as part of its analysis. It can also use this library to create nice, interactive dashboards for you of analyses it has completed. To **view** one in your browser:

```bash
# Navigate to your daaf-docker folder and enter the container shell
cd daaf-docker
bash run_daaf.sh bash        # macOS / Linux
.\run_daaf.ps1 bash          # Windows

# Inside the container, run the following command to view a notebook
# (replace the path with your actual notebook)
marimo run 'research/YYYY-MM-DD_Title/YYYY-MM-DD_Notebook_Name.py' --host 0.0.0.0 --port 2718 --headless
```

Then open [http://localhost:2718](http://localhost:2718) in your computer's browser (no need to mess with anything in the terminal here). The notebook renders there as an interactive document. The nice thing about these is that they're also written in regular Python code, so you can inspect its code very easily in any text browser as well.

To **edit** a notebook interactively, use `marimo edit` instead of `marimo run`:

```bash
marimo edit 'research/YYYY-MM-DD_Title/YYYY-MM-DD_Notebook_Name.py' --host 0.0.0.0 --port 2718 --headless
```

If you prefer manual Docker commands, you can also enter the container with `docker compose up -d` followed by `docker compose exec daaf-docker bash`.

---

## Viewing Session Logs in Your Browser

DAAF can generate an interactive timeline viewer for your session logs, letting you visually explore what happened during an analysis -- every tool call, subagent dispatch, and file reference, organized chronologically.

```bash
# Enter the container shell (if you're not already inside)
cd daaf-docker
bash run_daaf.sh bash        # macOS / Linux
.\run_daaf.ps1 bash          # Windows

# 1. Collect logs into your project (if not already done)
bash /daaf/scripts/collect_session_logs.sh /daaf/research/YYYY-MM-DD_Your_Project

# 2. Generate the viewer and start the server
bash /daaf/scripts/generate_log_viewer.sh /daaf/research/YYYY-MM-DD_Your_Project --serve
```

Then open the URL it prints (typically `http://localhost:2719/...`) in your browser. Press Ctrl+C to stop the server when done.

Port 2719 is mapped in `docker-compose.yml` for this purpose, alongside port 2718 (Marimo notebooks).

---

## Setup Troubleshooting

> **Tip:** If you run into an issue not listed here, or you want more help understanding any of these errors, try asking DAAF directly -- its **User Support** mode can help troubleshoot Docker, Git, and Claude Code problems and can look up the latest official documentation online.

- **"docker: The term 'docker' is not recognized as the name of a cmdlet, function, script file, or operable program" or "docker: command not found"** — Make sure you have Docker installed successfully. You may need to restart your computer after installation for it to fully register in your Terminal.
- **"unable to get image 'daaf-daaf-docker'"** — Make sure Docker Desktop is running and that you've run the initial `docker compose up -d --build` command during installation to create the necessary Docker image first. You can confirm it exists in the Docker Desktop app Images panel on the left-side toolbar.
- **"service "daaf-docker" is not running"** — Make sure Docker Desktop is running and that you've run the `docker compose up -d` command to start the Docker container first. You can confirm it's running in the Docker Desktop app Containers panel on the left-side toolbar.
- **Container seems really slow to build the first time** — The first `docker compose up -d --build` downloads base images and installs all packages. This is a one-time cost — subsequent starts are fast since Docker caches everything.
- **"I can't find my research files on my computer"** — With Docker volumes, your research files live inside Docker's managed storage, not in the project folder on your computer. See **How to Manage DAAF Project Files and Output** above for more information.
- **"Port 2718 already in use" when trying to view Marimo notebooks** — Another process is using that port. Either stop it, or change the port mapping in `docker-compose.yml` (e.g., `"3000:2718"` to use port 3000 on your host).
- **"Port 2719 already in use" when trying to view session logs** — Same fix: stop the conflicting process, or change the port mapping (e.g., `"3001:2719"`). Port 2719 is used by the session log viewer (`generate_log_viewer.sh --serve`).
- **Permission denied errors inside the container (especially on macOS)** — If you see errors like `Permission denied` when Claude tries to read or write files, the Docker volume likely has files owned by root or your host UID instead of the container's `appuser` (UID 1000). This is a known issue with Docker Desktop on macOS. The `docker-compose.yml` includes an init service (`daaf-init`) that automatically fixes file ownership on every startup. To resolve this: stop the container (`docker compose down`), then restart it (`docker compose up -d`) — the init service will repair permissions before the main container starts. If you still have issues, you can fix permissions manually:
  ```bash
  docker run --rm -v "daaf_daaf-data:/daaf" busybox chown -R 1000:1000 /daaf
  ```
- **Claude Code asks for an API key every time** — Claude Code stores its configuration inside the Docker volume, so it persists across normal container restarts. However, if your authentication state is lost, you can persist your API key by adding it to `~/.bashrc` inside the container: `echo 'export ANTHROPIC_API_KEY="your_key_here"' >> ~/.bashrc`. Note: DAAF's safety guardrails prevent Claude from reading `.env` files, so environment variables should be set directly in the shell or via `~/.bashrc` (consistent with the API key setup in Step 8).

---

## Recommended Next Steps

- [**02. Understanding and Working with DAAF**](02_understanding_daaf.md) — Learn to work with DAAF for the first time: what to expect, how to use it, and how to test its strengths and limitations
- [**06. FAQ: Philosophy**](06_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**07. FAQ: Technical Support**](07_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, authentication errors, and other common errors
- [**Back to main**](https://github.com/DAAF-Contribution-Community/daaf/tree/main)
