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
- [**Viewing Quarto Documents**](#viewing-quarto-documents)
- [**Viewing Session Logs in Your Browser**](#viewing-session-logs-in-your-browser)
- [**Keeping DAAF Updated**](#keeping-daaf-updated)
- [**Advanced Installation & Configuration**](#advanced-installation--configuration)
- [**Setup Troubleshooting**](#setup-troubleshooting)

---


**Installing DAAF is extremely easy and straightforward.** No prior experience with terminal, Docker, or Claude Code required. That being said, I put a LOT of explanations and detail together here so you have a strong sense and intuition for what's going on under the hood -- which I think is extremely valuable so you have a better handle on why things operate the way they do, or how to manage things in case anything goes wrong. Besides the reading, this whole process really shouldn't take you more than 10 minutes start-to-finish!


## Prerequisites

Before installing DAAF, there are three (technically four) key prerequisites. Please read the Anthropic account requirement especially closely; the price of access has historically been the highest barrier to entry, but this is changing.

### 0. A computer with internet access

You'll need internet access to download the project files and interact with DAAF/Claude (which itself always requires internet). Note that all data analyses will be conducted using your actual computer hardware, so you should have a computer that's generally capable of running intermediate-level data analysis (same sort of requirements you'd face if you wanted to analyze these same datasets in R/Stata/Python regularly). Don't worry about actual Python or R packages/libraries/dependencies, that's all handled carefully for you behind the scenes!

### 1. Anthropic Account & Authentication

Claude Code is the AI assistant platform that powers this project. It runs inside your terminal (not in a web browser) and needs to link in with an Anthropic account for billing/usage purposes. Because we're relying on cutting-edge frontier models and asking them to do a **LOT** of thorough work for us (deep-diving into data, writing a lot of code, checking a lot of code, rewriting code, writing intensive plans, etc., etc.), we will generally need to have a **high-usage** Anthropic account. Here are your main options:

| Option | Cost | Setup | Key Tradeoff |
|--------|------|-------|--------------|
| **Anthropic Max subscription** (recommended for heavy use) | $100-200/mo flat | Interactive login on first launch -- no config needed | Best value for heavy use. You can get by with much less (perhaps even the $20/mo Pro plan) if you're doing smaller, more discrete tasks with DAAF. [Get one here](https://claude.com/pricing/max) or [upgrade an existing plan](https://claude.ai/upgrade). Team/Enterprise subscriptions also work, but mileage may vary based on organizational settings/limits. |
| **Anthropic API key** | Pay-per-use (can get expensive fast) | Interactive login on first launch -- no config needed | Unlimited use, but a full pipeline analysis can cost $50+ in API fees. I'd have paid roughly 10x more via API key than my Max subscription. [Get one here](https://console.anthropic.com/). |
| **OpenRouter** | Pay-per-token via openrouter.ai with a 5.5% fee on credit purchases | Configure via `environment_settings.txt` ([instructions below](#configure-authentication-via-environment_settingstxt)) | No Anthropic subscription required. OpenRouter provides access to Anthropic's Claude models as well as high-performing open-weight alternatives. **GLM 5.2** in particular [benchmarks competitively with the Opus line](https://daaf.openaugments.org/bench/) at roughly 33% of the cost — an excellent option if you want strong performance without a monthly commitment. [Get a key here](https://openrouter.ai/). |
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
2. **Builds the Docker image** with Python 3.12, 50+ data science packages, geospatial libraries, and Claude Code pre-installed, plus R 4.5.3 with 60+ pinned R data science packages and the Quarto CLI 1.7.29. R is a first-class execution language in every DAAF image — it ships alongside Python with nothing to enable (see [**R support (included)**](#r-support-included) below for details). The first build downloads everything and takes a few minutes; subsequent rebuilds use Docker's layer cache and are much faster.
3. **Downloads the DAAF repository** directly into the Docker volume inside the container. This gives you a full file edit and version history via Git.
4. **Enforces security controls on Claude.** One of the big benefits of using Docker is that we can really keep Claude Code under control. The Docker container runs as a non-root user with all Linux capabilities dropped (`cap_drop: ALL`) and privilege escalation explicitly blocked (`no-new-privileges`). Even if Claude Code somehow tried to do something it shouldn't, the operating system kernel would stop it.

**If the build seems to hang** during `[3/4]`, give it a little extra time since installing the 50+ packages including geospatial libraries can take a minute here and there. As long as the output occasionally moves and updates every few minutes, let it finish. If anything goes wrong, you can close the terminal, delete the `daaf-docker` folder, and run the installer again; nothing is permanently changed on your computer.

### Launch Claude Code with DAAF

Now, you'll use your terminal to enter the DAAF installation directory it just created with all the main utility files, `daaf-docker/`. Once you're in there, you can run a helper script I created to make it easy to launch DAAF and Claude Code in the Docker container automatically.

**macOS / Linux (Terminal) -- recommended:**

```bash
cd daaf-docker
bash daaf.sh
```

**Windows (PowerShell) -- recommended:**

```powershell
cd daaf-docker
.\daaf.ps1
```

The DAAF Control Panel (`daaf.sh` on macOS/Linux, `daaf.ps1` on Windows) is an interactive menu with a status dashboard, service management, and all DAAF operations in one place. Select "Launch Claude Code" from the menu to get started.

**Alternative -- launch Claude Code directly:**

```bash
cd daaf-docker
bash run_daaf.sh          # macOS / Linux
```

```powershell
cd daaf-docker
.\run_daaf.ps1            # Windows
```

> **Note:** Each platform has its own native Control Panel — `daaf.sh` on macOS/Linux and `daaf.ps1` on Windows. On macOS and Linux, bash is already built in; the Control Panel runs on the system `/bin/bash` (macOS ships version 3.2), so **no Homebrew or newer bash is needed** — just run `bash daaf.sh`. On Windows, `.\daaf.ps1` runs directly in PowerShell with no extra tools required.

On first launch, Claude Code should prompt you to authenticate (API key or subscription login). Follow its instructions to complete the process as needed based on your method. Remember that CTRL+C actually exits the terminal, so use (Windows/Linux: CTRL+SHIFT+C and CTRL+V) and (macOS: Cmd+C and Cmd+V) if you want to copy/paste. You may need to copy and paste the link into your browser; be careful to check it for erroneous line-breaks in the URL if you run into issues!

### Configure Claude Code (required)

Once you're in, there are a few settings to adjust to ensure that the workflow is able to operate as expected. First, type the following into Claude's chat window:

```bash
/config
```

And then change the following settings by navigating down with your arrow keys, editing settings with left-right arrow keys, and hitting Enter when done:

- **"Auto-compact"** -- set to **False**. DAAF manages its own context carefully; auto-compaction can disrupt its orchestration and cause unexpected behavior.
- **"Verbose output"** -- set to **True**. Verbose output lets you see what DAAF's agents are actually thinking behind the scenes, making it much easier to detect shortcuts in thinking, laziness in loading proper file references, and inconsistent logic/confusion. See [Understanding DAAF — Two Kinds of "Memory"](02_understanding_daaf.md#two-kinds-of-memory) for a deeper explanation of why this happens and what to watch for.

Note that you can check which Claude model is being used by checking the indicator below the chat line (Opus, Sonnet, Haiku). DAAF defaults to using Opus 4.6 with 1 million token context -- no action needed on your part. You can change which Claude model is being used at any time by typing `/model`. All original development and testing of this project was done using **Opus 4.5** and **Opus 4.6**, but subsequent [empirical benchmarking across available Anthropic and open-weight models](https://daaf.openaugments.org/bench/) has shown that several models perform excellently with DAAF's orchestration workflows:

| Model | Benchmark Performance | Relative Cost | Best For |
|-------|----------------------|---------------|----------|
| **Opus 4.6** (default) | Strong | 1.0x (baseline) | Maximum analytical reasoning depth; complex methodology |
| **Sonnet 4.6** | Excellent — #2 overall, outperforms Opus on orchestration benchmarks | ~0.66x | Best cost-performance ratio with an Anthropic subscription |
| **GLM 5.2** (via OpenRouter) | Excellent — #4 overall, competitive with the Opus line | ~0.33x | Strong performance without an Anthropic subscription |

Opus 4.6 remains the default for its analytical reasoning depth on complex tasks, but Sonnet 4.6 is a genuinely excellent alternative at a fraction of the cost, and GLM 5.2 via OpenRouter makes DAAF accessible without any Anthropic subscription at all. Note that these benchmarks test orchestration conformance (following protocols, dispatching agents, loading skills) — not analytical depth. Opus may still have an edge on the hardest analytical reasoning, but the gap is smaller than previously assumed. See the [DAAFBench results](https://daaf.openaugments.org/bench/) for the full breakdown.

Opus 4.6 (unlike Opus 4.5) also allows you to select its "thinking level" by tapping left-and-right arrow keys while Opus 4.6 is selected on the /model selector in Claude Code. All tests I've conducted to date are using the "High" setting -- as this is a case where quality is far more important than quantity, I strongly recommend doing the same. This will have usage and API limit ramifications, though, so it is a reasonable thing to test out the tradeoffs for yourself. The [DAAFBench results](https://daaf.openaugments.org/bench/) are a great starting reference for understanding the quality-cost frontier across models. Please do report back with any findings so we can continue to refine this guidance!

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
bash daaf.sh
```

**Windows (PowerShell):**

```powershell
cd daaf-docker
.\daaf.ps1
```

The DAAF Control Panel provides an interactive menu with a status dashboard, service management, and all DAAF operations in one place.

**Alternative -- launch Claude Code directly:**

```bash
cd daaf-docker
bash run_daaf.sh         # macOS / Linux
```

```powershell
cd daaf-docker
.\run_daaf.ps1           # Windows
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
| DAAF Control Panel | `bash daaf.sh` | `.\daaf.ps1` |
| Start session | `bash run_daaf.sh` | `.\run_daaf.ps1` |
| End session | `/exit` → `exit` → `docker compose down` | Same |
| Browse/edit files | `bash run_vscode.sh` | `.\run_vscode.ps1` |
| View notebooks (Python/marimo) | `bash view_notebooks.sh` | `.\view_notebooks.ps1` |
| View documents (R/Quarto) | `bash view_quarto.sh` | `.\view_quarto.ps1` |
| View session logs | `bash view_logs.sh` | `.\view_logs.ps1` |
| Back up research | `bash backup_daaf.sh` | `.\backup_daaf.ps1` |
| Update DAAF | `bash update_daaf.sh` | `.\update_daaf.ps1` |


---

## How to Manage DAAF Project Files and Output

Your research files, data, and outputs live inside the **Docker volume** we created during installation — a storage area managed by Docker. Think of the `daaf-docker/` folder on your computer as just the "recipe" that was used to set everything up, while the Docker volume is the actual "kitchen" where all the work happens.

This means:
- **Your work persists** — stopping or restarting the Docker container does NOT delete anything. The Docker volume retains all your research outputs, data, and notebooks across restarts, rebuilds, and even `docker compose down`. A second, dedicated Docker volume (`daaf-claude-config`) holds all of Claude Code's own state — your login/authentication, session history and transcripts (used by `/resume`), and any installed plugins — so those persist across the same operations too, including image rebuilds. (The only command that erases either volume is an explicit `docker compose down -v` or `docker volume rm`.)
- **Files don't automatically appear on your computer** — unlike a traditional shared folder, files created inside the container are stored in the Docker volume, not directly on your desktop. To access them directly, you can use the included file editor (VSCode -- see below).
- **Only the Docker volume is accessible to Claude** — Claude can only see what's in the Docker volume. Your documents, photos, and everything else are completely isolated.

### Viewing and Editing Files

The easiest way to browse, edit, and manage your files is with DAAF's built-in **browser-based code editor** (VS Code in the browser). Run this from your `daaf-docker` folder on your computer (no need to enter the container):

```bash
cd daaf-docker
bash run_vscode.sh              # macOS / Linux
.\run_vscode.ps1                # Windows
```

This opens a full VS Code editor at the URL [http://localhost:2720](http://localhost:2720) running in your favorite browser where you can explore the entire DAAF file tree, edit files, preview Markdown reports, view/edit Python and R scripts, and track changes with the built-in Git tools. It comes pre-loaded with extensions for Python and R syntax highlighting, Markdown preview, Git history visualization, CSV viewing, and folder compression (for easy downloads — see *Getting files OUT of the container* below). The password is displayed in the terminal when you launch the script (default: `daaf`). A few things worth highlighting:

- **The default access password is "daaf"** but the password can be customized at any time in your environment_settings.txt file. See the environment_settings_example.txt in your daaf-docker folder for instructions there.
- **Markdown preview:** Right-click any `.md` file and select **"Open Preview"**, or press `Shift+Ctrl+V`, to see rendered Markdown with proper formatting — headers, tables, links, and all. This is the easiest way to read DAAF's reports and plans.
- **File management:** Use the file explorer sidebar to browse, create, rename, move, and delete files. You can also drag and drop files from your computer into the sidebar to import them into the Docker volume.
- **Git integration:** The Source Control panel (left sidebar) shows uncommitted changes, lets you view diffs, and browse commit history — useful for reviewing what DAAF produced during a session.
- **Search:** Use `Ctrl+Shift+F` (or `Cmd+Shift+F` on Mac) to search across all files — helpful for finding specific variables, scripts, or content across a project.

**Getting files INTO the container:** To bring files from your computer into the Docker volume for DAAF to use (e.g., a dataset you want to profile), simply drag and drop them from your computer onto the code editor's file explorer sidebar. This works for individual files *and* for whole folders — drop a folder and the editor copies its entire contents (including subfolders) into the location you drop it. Drag-and-drop upload works in Chrome, Edge, and Firefox.

**Getting files OUT of the container:** How you export depends on whether you want a single file or a whole folder:

- **A single file** — right-click the file in the explorer sidebar and choose **Download**. This works in every browser.
- **A whole folder (works in any browser)** — the most reliable way to export a folder is to zip it first: right-click the folder, choose **Compress → zip**, then right-click the new `.zip` file that appears next to the folder and choose **Download**. You get one tidy archive on your computer that you can unzip normally. When compressing, stick to the **zip**, **tar**, or **tgz** options — the **bz2** and **7z** choices will fail, because the tools they need aren't installed in the container.
- **A whole folder (Chrome or Edge only, shortcut)** — if you use Chrome or Edge, you can also right-click a folder and choose **Download** directly. Your browser asks you to pick a destination folder on your computer and then copies the files into it individually (you get the files themselves, not a single zip). This shortcut relies on a browser capability that only Chrome and Edge provide, so in Firefox or Safari, use the Compress → zip → Download method above instead.

The **Compress → zip** submenu comes from a built-in extension, so it's ready to use immediately with no setup. (One caveat for long-time users: if your DAAF install predates this extension and you don't see the **Compress** menu, update DAAF and rebuild once — `bash rebuild_daaf.sh` or `.\rebuild_daaf.ps1` from your `daaf-docker` folder — to pick it up.) If you prefer working in the integrated terminal, `zip -r archive.zip myfolder/` (or `tar czf archive.tgz myfolder/`) produces the same kind of archive, which you can then download by right-clicking it.

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

The backup script creates a date-versioned folder (e.g., `2026-04-21_daaf_backup/`) in your `daaf-docker` directory. Multiple backups on the same day are automatically suffixed (`2026-04-21a_daaf_backup/`, `2026-04-21b_daaf_backup/`, etc.). Feel free to move or copy these folders to another location on your computer (or an external drive) for safekeeping.

The backup covers both DAAF volumes: your research data, plus Claude Code's own state (your login, session history, and plugins) in a hidden `.daaf-claude-config/` subfolder. **Because the backup includes your Claude Code login credentials, treat backup folders as sensitive** — store them somewhere private, and if you share a backup with a colleague for collaboration, delete the `.daaf-claude-config/` subfolder from the copy first. (The backup also contains one or two small hidden manifest files you can ignore — the restore consumes them automatically. `.daaf-permissions` records which files were executable, so the restore can put file permissions back correctly even when the backup was stored on a Windows drive, which does not preserve them. `.daaf-symlinks`, present only when your data contains symbolic links, records those links so the restore can recreate them — this is what lets backups complete cleanly on Windows, where the copy step would otherwise stop at the first symbolic link.)

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

If the backup contains Claude Code state (newer backups do — see above), the restore also brings back your Claude Code login and session history, replacing whatever login is currently in the installation. Older backups made before this feature restore your research data only, with a note that you'll need to run `/login` in Claude Code afterward.

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

> **Note:** The Log Explorer reads from DAAF's session archive (the session logs folder that DAAF populates as you work). It has something to show only *after* you have run at least one Claude Code session — until then the archive is empty and the viewer has nothing to display. This is true even for the per-project view below: project log viewing draws on the same archived session records, so a project with no archived sessions yet will come up empty.

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

### Viewing Quarto Documents

> This applies to R projects.

R projects produce **Quarto** notebooks (`.qmd` files) instead of Marimo notebooks. Quarto renders to HTML by default, giving you a polished document with narrative text, executed code, tables, and figures -- all viewable in any web browser.

**Quickest way -- from your host machine (no container shell needed):**

```bash
cd daaf-docker
bash view_quarto.sh                                 # macOS / Linux: list available notebooks
.\view_quarto.ps1                                   # Windows: list available notebooks
```

Run with no argument to list every `.qmd` notebook across your research projects. To render and open one, re-run with its project folder name (or a direct path to the `.qmd`):

```bash
bash view_quarto.sh 2026-01-24_Your_Project         # macOS / Linux
.\view_quarto.ps1 2026-01-24_Your_Project           # Windows
```

The script renders the notebook to a single self-contained HTML file inside the container, copies it out to a `quarto_html/` folder next to your `docker-compose.yml`, and opens it in your default browser. It handles starting the container if it isn't already running. This is the R-notebook counterpart to `view_notebooks.sh` for Python (marimo) projects.

> **Don't see `view_quarto.sh` / `.ps1` in your `daaf-docker` folder yet?** It's a recent addition, so a slightly older install may not have it copied out. You can grab it straight from the container -- run one of these from your `daaf-docker` folder (with the container running):
>
> ```bash
> # macOS / Linux
> docker compose cp daaf-docker:/daaf/scripts/host/view_quarto.sh ./view_quarto.sh
> chmod +x view_quarto.sh
> ```
>
> ```powershell
> # Windows
> docker compose cp daaf-docker:/daaf/scripts/host/view_quarto.ps1 .\view_quarto.ps1
> ```

**Manual alternative -- rendering from inside the container:**

If you'd rather render by hand (or want the HTML in a specific place), you can run Quarto directly inside the container:

```bash
quarto render research/YYYY-MM-DD_Your_Project/notebook.qmd
```

This produces an HTML file (e.g., `notebook.html`) in the same directory. To view it, copy it out of the container to your host machine:

```bash
# From your host terminal (not inside the container)
docker cp daaf-docker:/daaf/research/YYYY-MM-DD_Your_Project/notebook.html ./notebook.html
```

Then open the HTML file in any browser. You can also browse and open the `.qmd` source files directly in the browser-based VS Code editor (see "Viewing and Editing Files" above) -- they're plain Markdown with R code chunks, so they're perfectly readable as source.

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
- **Syncs utility scripts** — automatically copies updated host-side scripts (the Control Panel, run, backup, rebuild, update, and the rest) out of the container to your `daaf-docker` folder. It figures out the full list from the newly updated repository itself, so newly added host scripts are picked up automatically without you having to do anything. If a host file has drifted from the repository version (a stale copy from an interrupted sync, for example), the updater replaces it and saves your previous copy as `<name>.pre-update` in the same folder — delete it once everything works, or rename it back to restore.
- **Auto-rebuilds if needed** — if the Dockerfile or docker-compose.yml changed, it offers to run `rebuild_daaf` automatically

> **If the updater tells you it updated itself, run it once more.** The update script is one of the files it keeps in sync, so occasionally an update includes a newer version of the updater. When that happens it copies the new updater into place and prints a notice asking you to run `bash update_daaf.sh` (or `.\update_daaf.ps1`) again. This second run uses the new updater and finishes applying everything. This is expected and safe — running it twice never does any harm, and if there is nothing left to do it will simply report "Already up to date!" and exit.

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

- Downloads some utility scripts (`run_daaf`, `update_daaf`, `backup_daaf`, `restore_from_backup`, `rebuild_daaf`, `view_logs`, `view_notebooks`, `view_quarto`, `run_vscode`) to your host machine so you have all the same convenience tools as a fresh install
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

### If a build is slow or fails

**First build takes a while (both architectures).** The first image build downloads a large stack of Python and R packages, so it takes several minutes and has quiet stretches with little output. This is normal — the build is not hung — and it happens only once; later starts are fast because Docker caches the image. DAAF's R packages install as pre-built binaries on **both x86_64 and Apple Silicon (arm64)** — there is no longer an arm64-specific "compile from source" penalty (the pinned R package mirror publishes binaries for both architectures on DAAF's Ubuntu base). The installer and `rebuild_daaf` scripts print a brief heads-up on arm64 machines so the quiet phase is not mistaken for a hang.

**Unclipped build logs (`DAAF_DIAG_BUILD`).** If a build fails and the useful error detail was cut off — you'll see a line like `[output clipped, log limit 2MiB reached]` (the exact limit varies by Docker version) — re-run the installer or rebuild with the `DAAF_DIAG_BUILD=1` prefix to capture the full, unclipped log:

**macOS / Linux:**
```bash
DAAF_DIAG_BUILD=1 bash rebuild_daaf.sh
```

**Windows (PowerShell):**
```powershell
$env:DAAF_DIAG_BUILD = "1"; .\rebuild_daaf.ps1
```

This routes the build through a separate diagnostic builder with raised log limits. Two things to know: it uses its own build cache (so the first diagnostic build is slower than a normal cached rebuild), and it is a **one-off command prefix**, not a key to put in `environment_settings.txt`. If the diagnostic builder can't be created for any reason, the scripts automatically fall back to a normal build.

Back up your Docker volume first (see [**Backing Up Your Work**](#backing-up-your-work)) if you have research data or framework customizations you want to preserve.

If the installer detects a previous attempt that didn't complete successfully (e.g., the Docker build failed partway through), it will note this and proceed automatically — no override needed.

### Running multiple DAAF instances

Most people run a single DAAF installation and never need this section. But if you want **two (or more) independent DAAF installs on the same machine** — for example, one folder for work and another for personal projects, each with its own Docker volume and research history — you can, with a small amount of configuration.

Two things must be unique per install so they don't collide:

1. **The Compose project name** — this determines the container name and the Docker volume (`<project>_daaf-data`) that holds your files. Two installs sharing a project name would share a volume.
2. **The three published localhost ports** — `2718` (notebooks), `2719` (log viewer), and `2720` (VS Code). Two installs cannot both publish the same host port.

To set up a second instance, install DAAF into a second, separate `daaf-docker` folder as usual, then in **that folder's** `environment_settings.txt` set a distinct project name and three free ports:

```
DAAF_PROJECT_NAME=daaf-personal
DAAF_PORT_MARIMO=2818
DAAF_PORT_LOGVIEWER=2819
DAAF_PORT_VSCODE=2820
```

(These four variables are documented in `environment_settings_example.txt`. Any free ports work — the numbers above are just an example offset by 100.)

Then recreate that instance's container so Compose picks up the new project name and ports:

```
docker compose down
bash run_daaf.sh            # macOS / Linux
.\run_daaf.ps1             # Windows
```

The DAAF launcher and control-panel scripts (`run_daaf`, `daaf`, the `view_*` browsers, `update`, `rebuild`, `backup`, `restore`) read these values from `environment_settings.txt` automatically, so the status dashboard and the browser URLs they print will point at the correct ports for each instance.

> **If you run bare `docker compose` commands directly** (outside the provided scripts) in a multi-instance folder, you must also create a `.env` file in that `daaf-docker` folder containing the same `DAAF_PROJECT_NAME` / `DAAF_PORT_*` lines. Docker Compose reads `.env` (and your shell environment) when resolving the `${...}` placeholders in `docker-compose.yml`, but it does **not** read `environment_settings.txt` for that purpose — that file only feeds the container's own environment. The DAAF scripts bridge this gap for you; bare `docker compose` does not.

> **Changing these on an existing install** requires the same `docker compose down` + relaunch: the project name and published ports are baked in at container-creation time, so a running container will not adopt new values until it is recreated. Your data volume moves with the project name — renaming `DAAF_PROJECT_NAME` on an existing install points it at a *different* (empty) volume, so choose the name once, up front.

### Building with the developer test toolchain (DAAF_DEV)

Most people never need this section — it is for **framework developers** who want to run DAAF's own shell and PowerShell test suites (`bats` and Pester) *inside* the container, so an in-container run reproduces what the project's CI does.

Unlike the multi-instance keys above (which are runtime settings), `DAAF_DEV` is a **build-time** flag: it changes what gets installed into the Docker image. To turn it on, add this line to your `daaf-docker` folder's `environment_settings.txt`:

```
DAAF_DEV=1
```

Then rebuild the image so the flag takes effect:

```
bash rebuild_daaf.sh         # macOS / Linux
.\rebuild_daaf.ps1           # Windows
```

With `DAAF_DEV=1`, the build additionally installs `shellcheck`, `bats`, PowerShell 7, Pester, PSScriptAnalyzer, and the GitHub CLI (`gh`). You can then run the suites from inside the container (`bash run_daaf.sh bash`):

```
bats tests/bash/
pwsh -NoProfile -Command "Invoke-Pester -Path ./tests/powershell/"
shellcheck -x scripts/host/*.sh
```

When `DAAF_DEV` is unset or `0` (the default for every normal install), none of this tooling is installed and the image is byte-for-byte identical to a standard build — so leaving it off costs you nothing.

**Authenticating the GitHub CLI (`GH_TOKEN`).** To use `gh` without interactive login, add a `GH_TOKEN=...` line to your `environment_settings.txt` — a classic Personal Access Token with `repo` + `workflow` scopes (the commented `GH_TOKEN` entry in `environment_settings_example.txt` documents this). With the token in place, `gh` authenticates automatically: framework developers can inspect CI runs and failure logs (`gh run view --log-failed`), work pull requests and issues from inside the container, and push over HTTPS (the dev image pre-registers `gh` as git's credential helper). Changing the token later only requires recreating the container — not a rebuild.

> **DAAF_DEV is a build flag, not a runtime setting.** It only matters at `docker compose build` time. The install and rebuild scripts bridge it from `environment_settings.txt` into the shell environment so the build picks it up; if you run bare `docker compose build` yourself, put `DAAF_DEV=1` in a `.env` file (or your shell environment) the same way you would for the multi-instance keys. Turning it on or off requires a rebuild to change the installed toolchain.

### R support (included)

Every DAAF image ships with **R** as a first-class execution language alongside Python — there is nothing to enable and no flag to set. The build installs:

- **R 4.5.3** (the current DAAF-pinned R release)
- **60+ pinned R packages** covering data manipulation (tidyverse), visualization (ggplot2, plotly, gt), econometrics (fixest, plm, survey), spatial analysis (sf, terra), and machine learning (tidymodels) — installed from a **date-pinned Posit Package Manager (P3M) snapshot** so rebuilds produce identical package versions
- **Quarto CLI 1.7.29** — R's literate-programming notebook system, the R equivalent of Marimo for Python

Including R (with the full package set and Quarto) accounts for roughly **2.2 GB** of the image size (measured: 8.61 GB with R vs. 6.4 GB without).

**To use R**, just tell DAAF "set execution language to R" at the start of a session — no configuration files to edit. See the [R and Language Support FAQ](07_faq_technical.md#r-and-language-support) for details on switching between languages.

The smoke tests and their runner in `scripts/smoke_tests/` exercise each R library skill, plus a Python import smoke (`smoke_imports.py`) covering the pinned Python analysis stack; all run via `run_all_smoke_tests.sh` in any DAAF container.

### Configure authentication via environment_settings.txt

By default, Claude Code prompts you to log in interactively the first time you launch it (browser-based OAuth or pasting an API key). This works great for Max subscription and direct API key setups. However, if you're using **OpenRouter**, a **cloud provider** (Bedrock/Vertex), or simply want your authentication to persist automatically without interactive login, you can configure it through the `environment_settings.txt` file in your `daaf-docker` folder.

Your `daaf-docker` folder includes an `environment_settings_example.txt` template that documents all six supported authentication methods with the exact environment variables needed for each. To set it up:

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

#### Model routing for alternative providers (optional)

DAAF splits its background helper agents across two Claude model tiers to balance quality against cost: a stronger tier (**Opus**) for high-judgment work like planning, review, and verification, and a faster tier (**Sonnet**) for well-defined work like fetching and profiling data. If you use Anthropic directly (Max subscription or API key), this happens automatically and you don't need to do anything.

If you point DAAF at an **alternative provider** (OpenRouter, or a cloud platform serving non-Claude models like GLM), the names "opus" and "sonnet" won't exist on your endpoint. You have two options, both set in `environment_settings.txt`:

- **Keep the two tiers, using your own models** — map each tier to one of your provider's models:
  ```bash
  ANTHROPIC_DEFAULT_OPUS_MODEL=your-strong-model-slug      # e.g. z-ai/glm-5.2
  ANTHROPIC_DEFAULT_SONNET_MODEL=your-fast-model-slug      # e.g. z-ai/glm-5.2-air
  ```
  DAAF then routes high-judgment work to your strong model and routine work to your fast one.

- **Use a single model for everything** — simplest if you'd rather not think about tiers:
  ```bash
  CLAUDE_CODE_SUBAGENT_MODEL=your-model-slug
  ```
  Every helper agent runs on that one model.

If you set **neither** on a non-Claude session, DAAF still works: a built-in check keeps helper agents on your session's model instead of trying to reach a Claude model that isn't there. Setting one of the options above is recommended for the best results. The exact variable names are documented in `environment_settings_example.txt` as well.

#### GPT (OpenAI) models via OpenRouter (Option C, extended)

OpenRouter also serves **OpenAI GPT models**, and DAAF can drive them through the same "Option C" setup above — GPT runs the full DAAF agentic stack (multi-tool loops, subagent dispatch, the two-tier model routing) with **no proxy or code changes**, just environment variables. Validated live on 2026-07-09.

Uncomment the OpenRouter section and set the model variables to GPT slugs (note the `openai/` prefix that OpenRouter uses):

```bash
# --- Option C: OpenRouter, pointed at GPT models ---
ANTHROPIC_BASE_URL=https://openrouter.ai/api
ANTHROPIC_AUTH_TOKEN=your_openrouter_api_key_here
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=openai/gpt-5.6-sol
ANTHROPIC_DEFAULT_OPUS_MODEL=openai/gpt-5.6-sol       # strong tier (Opus-analog)
ANTHROPIC_DEFAULT_SONNET_MODEL=openai/gpt-5.6-terra   # fast tier (Sonnet-analog)
CLAUDE_CODE_MAX_CONTEXT_TOKENS=1050000               # see "known limitations" below
```

Recommended GPT slugs (context windows and roles verified against OpenRouter on 2026-07-09):

| Slug | Context window | Role in DAAF | Notes |
|------|---------------|--------------|-------|
| `openai/gpt-5.6-sol` | 1,050,000 | **Strong tier (Opus-analog) — recommended default** | $5 / $30 per M tokens in/out |
| `openai/gpt-5.6-terra` | 1,050,000 | **Fast tier (Sonnet-analog) — recommended default** | $2.50 / $15 per M tokens |
| `openai/gpt-5.6-luna` | 1,050,000 | Economy (Haiku-analog) | $1 / $6 per M tokens; unused by DAAF's two-tier routing (Haiku tier excluded by policy) |
| `openai/gpt-5.5` / `openai/gpt-5.4` | 1,050,000 | Previous strong-tier options | Still work; superseded by the 5.6 family at equal-or-better pricing |
| `openai/gpt-5.2` | 400,000 | Previous fast-tier option | Smaller window than Terra at similar price |
| `openai/gpt-5.*-chat` | 128,000 | Not recommended | Small window; avoid for pipeline work |

The two-tier routing described above works identically: map `ANTHROPIC_DEFAULT_OPUS_MODEL` / `ANTHROPIC_DEFAULT_SONNET_MODEL` to your chosen GPT slugs, and DAAF's cost-control ceiling stands down automatically for non-Claude models.

> **GPT-5.6 tier naming:** the GPT-5.6 family uses OpenAI's tier-analog names — *Sol* (strong; Opus-analog), *Terra* (mid; Sonnet-analog), and *Luna* (economy; Haiku-analog) — all with 1,050,000-token windows. DAAF's recommended defaults are Sol and Terra, validated live through the full agentic stack (including subagent dispatch on the tier remaps) on 2026-07-09, the day of the OpenRouter release.
>
> **Avoid the `-pro` slugs via OpenRouter (Option C):** despite listing the same 1,050,000-token windows and identical pricing, `gpt-5.6-sol-pro` / `-terra-pro` / `-luna-pro` fail with hard "Prompt is too long" API errors once a session's real context reaches roughly 50k tokens — through the Anthropic-compatible endpoint their token accounting runs ~4x the non-pro count against an enforced ~200k ceiling, and the inflation also makes them bill ~2-4x more for identical work. Empirically verified across all three -pro variants in the 2026-07-10 DAAFBench smoke battery (see `benchmarks/README.md` § 1). The non-pro slugs are unaffected.

**Restart the container** (`docker compose down`, then `bash run_daaf.sh`) to pick up the changes. No rebuild is needed for OpenRouter — it is config-only.

#### Option F: OpenAI API directly (DAAF provider shim)

If you have an **OpenAI API key** and would rather talk to OpenAI directly (no OpenRouter middle-hop), DAAF ships a lightweight translation shim that presents an Anthropic-compatible endpoint on `localhost` and forwards to OpenAI. It has **zero new dependencies** and starts automatically inside the container.

> **Billing prerequisite — API credits are separate from ChatGPT.** An OpenAI API key only works if its platform.openai.com project has **prepaid credits purchased**: adding a payment card alone is not enough (the $5+ credit purchase is a separate step), and new API accounts receive no free credits. A ChatGPT Plus/Pro subscription does **not** include API access — ChatGPT and the API are separate billing systems, and there is **no OpenAI-sanctioned** way to run a third-party tool like DAAF on a ChatGPT subscription (subscription usage is scoped to OpenAI's official apps; verified against OpenAI's terms and Codex documentation, 2026-07-11). An unfunded key fails with an instant `429 insufficient_quota` on every request — see the [technical FAQ entry on instant 429s](07_faq_technical.md#q-my-gpt-session-fails-instantly-with-429-errors-on-every-request-option-f). DAAF *does* ship an **unofficial, dev-lane** path that reuses your Codex (ChatGPT) OAuth login against OpenAI's undocumented Codex backend — see the ["ChatGPT subscription lane"](#option-f-alternate-lane-chatgpt-subscription-codex-backend) below. It is a proof-of-concept, **not** an OpenAI-sanctioned API method: it may break if OpenAI changes the backend, and you are responsible for compliance with OpenAI's terms. The sanctioned, robust path remains the API-key lane described here.

Set two variables in `environment_settings.txt` to turn it on, plus the Claude Code side that points at the local shim:

```bash
# --- Option F: OpenAI API directly, via the DAAF provider shim ---
DAAF_PROVIDER_SHIM=openai
OPENAI_API_KEY=sk-your_openai_api_key_here

# Point Claude Code at the local shim (bare GPT slugs — no openai/ prefix here):
ANTHROPIC_BASE_URL=http://127.0.0.1:4141
ANTHROPIC_AUTH_TOKEN=daaf-shim-local
ANTHROPIC_API_KEY=
ANTHROPIC_DEFAULT_OPUS_MODEL=gpt-5.6-sol[1m]         # strong tier (Opus-analog); [1m] = 1M window hint
ANTHROPIC_DEFAULT_SONNET_MODEL=gpt-5.6-terra[1m]     # fast tier (Sonnet-analog); [1m] = 1M window hint
CLAUDE_CODE_MAX_CONTEXT_TOKENS=1050000               # see "Context window on GPT sessions" below
```

**Sessions start on the Claude default — switch with `/model`.** The session start model is set by `ANTHROPIC_MODEL` in the `env` block of DAAF's project `.claude/settings.json` (shipped as `claude-opus-4-8[1m]`; most DAAF users run Claude). That settings.json value overrides the container environment — verified empirically — so do **not** set `ANTHROPIC_MODEL` in `environment_settings.txt`. On a GPT setup, run `/model` after launch (a forgotten switch fails loudly on the first message, so there is no silent wrong-model risk), or make GPT your standing default by editing the `"ANTHROPIC_MODEL"` line in `/daaf/.claude/settings.json` — see the [FAQ entry on session start model](07_faq_technical.md#q-my-gpt-session-starts-on-a-claude-model-instead-of-my-gpt-model).

**This option requires an image rebuild** (the shim's auto-launch is baked into the container entrypoint), whereas Option C is config-only. After setting the variables, rebuild and restart per the [rebuild instructions](#keeping-daaf-updated) (`bash rebuild_daaf.sh` / `.\rebuild_daaf.ps1`). On boot, the container entrypoint starts the shim automatically and supervises it (a keepalive restarts it if it exits); you do not normally need to touch it.

For troubleshooting, a manager script controls the shim and a health endpoint reports its status:

```bash
bash /daaf/scripts/provider_shim/start_shim.sh --status   # is it running?
curl -s http://127.0.0.1:4141/health                       # health check
```

The shim's log lives at `/daaf/scripts/provider_shim/logs/shim.log`. Backend errors are logged with the OpenAI error body and rate-limit headers (shim v1.1.1+, credential-scrubbed), so the log names the exact cause — e.g. `insufficient_quota` (billing) vs a true rate limit; the [technical FAQ](07_faq_technical.md#q-my-gpt-session-fails-instantly-with-429-errors-on-every-request-option-f) walks through the triage. The manager also accepts `--start`, `--stop`, and `--auto`. Defaults are fine for almost everyone; the tuning variables (`SHIM_PORT`, `SHIM_BACKEND_BASE_URL`, `SHIM_BACKEND_API_KEY`, `SHIM_STRIP_MODEL_PREFIX`, `SHIM_SANITIZE_TOOLS`, `SHIM_REASONING_EFFORT`, `SHIM_TEXT_VERBOSITY`) are documented in `environment_settings_example.txt`. Tool-call sanitization is **on by default** (`SHIM_SANITIZE_TOOLS`): the shim silently strips known GPT tool-call quirks (empty `pages` parameters, `isolation` fills on subagent dispatches, redundant sandbox flags) that otherwise each cost a wasted error round-trip; every strip is recorded in the shim log. Set `SHIM_SANITIZE_TOOLS=0` (and restart the shim — the flag is read at startup) when running DAAFBench against shim-routed models, which must observe raw model behavior; confirm via the `/health` endpoint's `sanitize_tools` field.

**Reasoning effort (shim v1.2.2+).** The shim always sets the OpenAI request's reasoning effort, resolved by a four-tier precedence chain — first present wins: (1) a per-request signal from Claude Code, (2) a `#<effort>` suffix you append to a model slug (e.g. `ANTHROPIC_DEFAULT_SONNET_MODEL=gpt-5.6-terra[1m]#medium`; it works alongside the `[1m]` window hint and is stripped before the request reaches OpenAI), (3) the `SHIM_REASONING_EFFORT` env var, and (4) the default `high` (parity with DAAF Claude sessions). Valid values are `none`, `low`, `medium`, `high`, `xhigh`, and `max` (`max` is gpt-5.6-only). Leave everything unset to get `high` everywhere; set the env var or a slug suffix only if you want a different level.

> **The `/model` effort selector does not work for GPT slugs.** Claude Code gates the in-UI reasoning-effort selector by model-ID pattern, and for an unrecognized (GPT) slug it pins `high` on every request — so toggling the selector has no effect on GPT sessions. As of **shim v1.2.3** the shim recognizes that pinned inbound `high` as unset and falls through to your slug/env steer, which reactivates tiers (2) and (3) above as the real controls. To run GPT at a non-default effort, use the `#<effort>` slug suffix or `SHIM_REASONING_EFFORT` — not the `/model` selector.

See the [technical FAQ entry on controlling GPT reasoning effort](07_faq_technical.md#q-how-do-i-control-gpt-reasoning-effort-option-f).

**Response verbosity (shim v1.2.4+).** Separately from reasoning effort, the shim sends OpenAI's `text.verbosity` control on every request, defaulting to `high` for parity with DAAF's warm, educational posture (`high` adds warmth and volume; `low` is terse); set `SHIM_TEXT_VERBOSITY=low` or `medium` in `environment_settings.txt` if GPT responses feel too long, and see the [technical FAQ entry on terse GPT responses](07_faq_technical.md#q-gpt-responses-feel-terse-compared-to-claude-option-f) if they feel too brief.

**Context window on GPT sessions.** Claude Code enforces its context-window budget *locally*, and for a model slug it does not recognize it assumes a small (~200K) window — far below the real 1,050,000 of the gpt-5.6 family. Two things keep GPT sessions from ending prematurely at a fraction of the true window. First, **append `[1m]` to your GPT slugs** in the model variables (e.g. `ANTHROPIC_DEFAULT_OPUS_MODEL=gpt-5.6-sol[1m]`, as shown above): Claude Code reads `[1m]` as a "this model has a 1M window" hint and budgets the full window, then strips the suffix before sending, so the shim and OpenAI backend see the bare `gpt-5.6-sol`. (`CLAUDE_CODE_AUTO_COMPACT_WINDOW=1000000` is an equivalent env-var alternative if you prefer not to touch the slugs.) Second, **shim v1.2.1 calibrates its token-count estimates against the real backend counts**: earlier versions estimated a request's size from its raw JSON byte length, which over-counted realistic Claude Code envelopes (large tool schemas plus escaping) by roughly 1.6–1.9× and could end a session client-side ("Prompt is too long") well below the real window; v1.2.1 learns the true tokens-per-byte ratio from each backend response and estimates slightly *under* the real count, so the failure mode is a loud, recoverable backend error rather than silent premature death. If a GPT session still reports "Context limit reached" / "Prompt is too long" at low utilization, see the [technical FAQ entry on low-utilization context errors](07_faq_technical.md#q-my-gpt-session-says-context-limit-reached--prompt-is-too-long-at-low-utilization).

#### Option F, alternate lane: ChatGPT subscription (Codex backend)

The same shim can route Claude Code through your **ChatGPT subscription's Codex backend** instead of a pay-per-token OpenAI API key. It is the *same* shim and the *same* Responses translator — only the **authentication and endpoint** differ: instead of a `SHIM_BACKEND_API_KEY`, the shim reads an OAuth access token from your `codex` login and POSTs to OpenAI's Codex Responses backend.

> **This is an unofficial, dev-lane path — read this first.** It reuses Codex's OAuth against an **undocumented, OpenAI-controlled backend**. It is **not** an OpenAI-sanctioned API method (OpenAI's terms scope subscription usage to their own official apps), it **may break at any time** if OpenAI changes the backend, and **you are responsible for compliance with OpenAI's terms of service.** Treat it as a proof-of-concept / dev lane. The API-key lane above (`SHIM_BACKEND_MODE` unset → `openai`) is the sanctioned, robust fallback.

**Prerequisites — the developer image.** This lane needs the **Codex CLI**, which is installed into the image **only** when `DAAF_DEV=1` is set in `environment_settings.txt` **before the image is built** (see [Building with the developer test toolchain](#building-with-the-developer-test-toolchain-daaf_dev)). Confirm it inside the container before going further:

```bash
codex --version    # expect 0.144.1 or newer
```

If that reports `codex: command not found`, you are not on the developer image — set `DAAF_DEV=1`, rebuild (`bash rebuild_daaf.sh` / `.\rebuild_daaf.ps1`), and re-enter the container before continuing.

**Setup.** With the developer image confirmed, five steps take you from a fresh container to a working ChatGPT lane.

1. **Enable device-code login in your ChatGPT settings — do this first.** On chatgpt.com, open your **personal account → security settings** and turn on **device-code login**. This toggle is **off by default** and is the single easiest step to miss: the login in step 2 fails immediately without it. Device-code login is what lets you authenticate with no browser or loopback callback inside the container.
2. **Log in inside the container.** Run:
   ```bash
   codex login --device-auth
   ```
   It prints a **URL and a one-time code**. Open the URL in a browser on **any device** — your laptop or phone, it need not be the container — sign in to ChatGPT, and enter the code. There is no in-container browser, no `localhost:1455` loopback, and no port forwarding to set up. (The command is `codex login --device-auth`, **not** `codex auth`, which does not exist — and bare `codex login` defaults to a browser-loopback flow that cannot complete headless in the container, so the `--device-auth` flag is essential.)
3. **The login is stored in a persisted, backed-up location.** `CODEX_HOME` is already set by Docker Compose to the `codex-daaf` store (`/home/appuser/.claude/codex-daaf`), and the container pre-creates that directory on a fresh volume. After a successful login, `auth.json` exists there — and because the store is persisted and backed up, **your login survives container rebuilds**, so you only do this once.
4. **Switch the shim to the ChatGPT lane.** In `environment_settings.txt`:
   ```bash
   DAAF_PROVIDER_SHIM=openai        # still the master on/off switch for the shim
   SHIM_BACKEND_MODE=chatgpt        # route through the Codex/OAuth lane, not the API-key lane
   ANTHROPIC_BASE_URL=http://127.0.0.1:4141
   ANTHROPIC_AUTH_TOKEN=daaf-shim-local
   ANTHROPIC_API_KEY=
   ANTHROPIC_DEFAULT_OPUS_MODEL=gpt-5.6-sol[1m]
   ANTHROPIC_DEFAULT_SONNET_MODEL=gpt-5.6-terra[1m]
   CLAUDE_CODE_MAX_CONTEXT_TOKENS=1050000
   ```
   In this mode `OPENAI_API_KEY` / `SHIM_BACKEND_API_KEY` are **ignored** — the OAuth token is the credential. (Switching an already-built developer image between the two Option F lanes needs no further rebuild; only the initial `DAAF_DEV=1` image build does.)
5. **Recreate the container** to apply (`docker compose down`, then `bash run_daaf.sh` / `.\run_daaf.ps1`). The shim reads `SHIM_BACKEND_MODE` at startup.

**Confirm it's working.** After the container comes back up, check the shim log:

```bash
cat /daaf/scripts/provider_shim/logs/shim.log
```

A healthy ChatGPT lane logs `backend_mode=chatgpt` at startup and then healthy `200` responses once a GPT session is running. Start a session, run `/model` to select your GPT slug (the [API-key lane above](#option-f-openai-api-directly-daaf-provider-shim) explains why sessions open on the Claude default), and send a message.

**How auth stays fresh.** The shim reads the OAuth access token from `auth.json` in your `CODEX_HOME` store and **refreshes it automatically** (the access token lasts ~10 days; the shim refreshes only when it is near expiry or after a backend rejection, and it never logs any token value). If a refresh ever fails permanently, the shim's log tells you to run `codex login --device-auth` again.

**Troubleshooting.**

| Symptom | Cause and fix |
|---------|---------------|
| `codex login --device-auth` fails immediately | Device-code login is not enabled in your ChatGPT security settings — do step 1 above. |
| `codex: command not found` | You are not on the developer image. Set `DAAF_DEV=1` and rebuild (`rebuild_daaf.sh` / `rebuild_daaf.ps1`). |
| Shim log tells you to re-login | The OAuth token refresh failed permanently — run `codex login --device-auth` again inside the container. |

**Running more than one container.** Each DAAF container does its **own** `codex login`, which creates an **independent refresh-token grant** — there is no credential collision between containers. They share only your ChatGPT **usage pool** (the 5-hour and weekly caps), so running two in parallel simply draws that pool down faster. This is the clean way to run parallel DAAF instances. (The subtler case is running several codex-based tools — the `codex` CLI, `codex-plugin-cc`, the shim — inside a *single* container off the *same* login: that can rarely trigger a refresh-token-rotation race. To isolate them, give each its own `codex login` under a separate `CODEX_HOME`; `CODEX_HOME` and the `SHIM_OAUTH_TOKEN_URL` / `SHIM_OAUTH_CLIENT_ID` override variables in `environment_settings_example.txt` are the hooks for that. None of this is needed for a normal single-tool setup.)

See the [technical FAQ entry on the ChatGPT subscription lane](07_faq_technical.md#q-can-i-use-my-chatgpt-subscription-instead-of-an-openai-api-key-option-f).

#### Known limitations of GPT sessions (both lanes)

GPT support is a **power-user option**, offered with honest framing rather than as a first-class guarantee. Be aware of the following:

- **Context utilization is estimated, not exact.** OpenRouter's Anthropic-compatible endpoint does not implement token counting, so Claude Code falls back to estimation on GPT sessions (the shim does the same). The context bar and utilization warnings are close approximations, not precise counts.
- **Set `CLAUDE_CODE_MAX_CONTEXT_TOKENS` to your model's real window.** Claude Code assumes a 200k window for models it doesn't recognize, which is wrong for the 400k and 1,050,000-token GPT models. Setting this variable (as shown in the blocks above) makes the statusline and context-management thresholds accurate. DAAF's statuslines also carry a built-in GPT window map as a backstop, but the explicit variable is authoritative.
- **GPT keeps DAAF's conservative context thresholds.** DAAF applies its cautious context-quality gates (elevated/high/critical at 40/60/75%) to GPT models by policy, because their quality-at-long-context behavior is not yet DAAF-validated. This is deliberate and not configurable.
- **OpenRouter's Anthropic endpoint is officially scoped to Anthropic models.** GPT works through it (proven live), but OpenRouter documents this endpoint for Claude models — it is effectively unsupported territory the vendor could change at any time.
- **Anthropic does not officially support routing Claude Code to non-Claude models** through any gateway. DAAF offers these lanes as a tested power-user capability, not something either vendor guarantees.

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
- **Claude Code asks me to log in again** — This should be rare. Claude Code's authentication state lives in a dedicated Docker volume (`daaf-claude-config`, mounted at `/home/appuser/.claude`, with `CLAUDE_CONFIG_DIR` pointing there so credentials and `~/.claude.json` land in it too). That volume persists across container restarts, `docker compose down`, and image rebuilds — so a normal restart or update should not lose your login. If you *are* prompted to log in again after a routine restart, just complete `/login` once; it will persist from then on. Two things to know: (1) running `docker compose down -v` (note the `-v`) or manually deleting the volume erases this state — avoid `-v` unless you intend to wipe everything; (2) if you prefer key-based auth that never needs an interactive login, configure your credentials in the `environment_settings.txt` file (see [**Configure authentication via environment_settings.txt**](#configure-authentication-via-environment_settingstxt) above), which sets authentication from the environment on every start.
- **OpenRouter: "model not found" or authentication errors** — Double-check three things: (1) `ANTHROPIC_BASE_URL` must be exactly `https://openrouter.ai/api` with no `/v1` suffix (the `/v1` variant is for OpenAI-compatible tools, not Claude Code), (2) `ANTHROPIC_API_KEY` must be set to an empty value (`ANTHROPIC_API_KEY=`), not removed entirely — if it's unset, Claude Code falls back to Anthropic's servers, and (3) if you previously logged in with Anthropic interactively, run `/logout` inside Claude Code to clear cached credentials. You can verify your connection is working by typing `/status` inside Claude Code and checking the [OpenRouter Activity Dashboard](https://openrouter.ai/activity) for incoming requests.

---

## Recommended Next Steps

- [**02. Understanding and Working with DAAF**](02_understanding_daaf.md) — Learn to work with DAAF for the first time: what to expect, how to use it, and how to test its strengths and limitations
- [**06. FAQ: Philosophy**](06_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**07. FAQ: Technical Support**](07_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, authentication errors, and other common errors

---

[**Back to main**](https://github.com/DAAF-Contribution-Community/daaf/tree/main)
