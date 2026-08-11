# 01. Installation & Quick Start

This is the complete first-time installation and setup guide for DAAF. This document covers every step from installing prerequisites to running your first session, as well as tips for file management, viewing compiled research script notebooks, and troubleshooting.

[**Back to main**](https://github.com/DAAF-Contribution-Community/daaf/tree/main)

---

## Table of Contents
- [**Prerequisites**](#prerequisites)
- [**Installing DAAF**](#installing-daaf)
- [**Day-to-Day Start/Stop Workflow**](#day-to-day-startstop-workflow)
- [**How to Manage DAAF Project Files and Output**](#how-to-manage-daaf-project-files-and-output)
- [**Viewing Session Logs in Your Browser**](#viewing-session-logs-in-your-browser)
- [**Viewing Marimo Notebooks in Your Browser**](#viewing-marimo-notebooks-in-your-browser)
- [**Viewing Quarto Documents**](#viewing-quarto-documents)
- [**Keeping DAAF Updated**](#keeping-daaf-updated)
- [**Advanced Installation & Configuration**](#advanced-installation--configuration)
- [**Setup Troubleshooting**](#setup-troubleshooting)
- [**Recommended Next Steps**](#recommended-next-steps)

---


**Installing DAAF is extremely easy and straightforward.** No prior experience with terminal, Docker, or Claude Code required. That being said, I put a LOT of explanations and detail together here so you have a strong sense and intuition for what's going on under the hood -- which I think is extremely valuable so you have a better handle on why things operate the way they do, or how to manage things in case anything goes wrong. Besides the reading, this whole process really shouldn't take you more than 10 minutes start-to-finish! This guide is complete, but you may also find our dedicated [Getting Started website guide](https://daaf.openaugments.org/get-started.html) more visually clear and helpful if you prefer diagrams, images, etc. on our DAAF homepage

**Prefer to watch first?** If you'd rather see the whole thing before diving in, the Getting Started video walks through the entire installation start-to-finish and then tours the everyday essentials — the browser-based file editor, the session log viewer, and keeping your install updated — in about 30 minutes. Click the thumbnail to watch:

<p align="center">
  <a href="https://youtu.be/BPlR9bXZxnY">
    <img width="720" alt="Claude Code for Social Scientists: Get Started with DAAF in 30 Minutes" src="https://img.youtube.com/vi/BPlR9bXZxnY/maxresdefault.jpg" />
  </a>
</p>


## Prerequisites

Before installing DAAF, there are three (technically four) key prerequisites. Please read the account & authentication requirement especially closely; the price of access has historically been the highest barrier to entry, but this is changing.

### 0. A computer with internet access

You'll need internet access to download the project files and interact with DAAF/Claude (which itself always requires internet). Note that all data analyses will be conducted using your actual computer hardware, so you should have a computer that's generally capable of running intermediate-level data analysis (same sort of requirements you'd face if you wanted to analyze these same datasets in R/Stata/Python regularly). Don't worry about actual Python or R packages/libraries/dependencies, that's all handled carefully for you behind the scenes! It's also worth setting aside a little room on your drive: plan for roughly **15-20 GB of free storage space** — enough for the Docker image (the full data-science stack) plus comfortable room for your research data as projects accumulate. That's a one-time footprint for most users, and nothing to stress about on a typical modern laptop.

### 1. AI Provider Account & Authentication

Claude Code is the AI assistant platform that powers this project. It runs inside your terminal (not in a web browser) and needs to connect to an AI provider account for billing/usage purposes. Anthropic (the maker of Claude) is the default and most thoroughly tested provider, but DAAF also runs on OpenRouter, OpenAI's GPT models, and organizational cloud platforms like Bedrock and Vertex AI. Because we're relying on cutting-edge frontier models and asking them to do a **LOT** of thorough work for us (deep-diving into data, writing a lot of code, checking a lot of code, rewriting code, writing intensive plans, etc., etc.), we will generally need a **high-usage** account with whichever provider you choose. Here are your main options:

| Option | Cost | Setup | Key Tradeoff |
|--------|------|-------|--------------|
| **Anthropic Max subscription** (recommended for heavy use) | $100-200/mo flat | Interactive login on first launch -- no config needed | Best value for heavy use. You can get by with much less (perhaps even the $20/mo Pro plan) if you're doing smaller, more discrete tasks with DAAF. [Get one here](https://claude.com/pricing/max) or [upgrade an existing plan](https://claude.ai/upgrade). Team/Enterprise subscriptions also work, but mileage may vary based on organizational settings/limits. |
| **Anthropic API key** | Pay-per-use (can get expensive fast) | Interactive login on first launch -- no config needed | Unlimited use, but a full pipeline analysis can cost $50+ in API fees. I'd have paid roughly 10x more via API key than my Max subscription. [Get one here](https://console.anthropic.com/). |
| **OpenRouter** | Pay-per-token via openrouter.ai with a 5.5% fee on credit purchases | Configure via `environment_settings.txt` ([instructions below](#configure-authentication-via-environment_settingstxt)) | No Anthropic subscription required. OpenRouter provides access to Anthropic's Claude models as well as high-performing open-weight alternatives: [per DAAFBench](https://daaf.openaugments.org/bench/), **Kimi K3** reaches the top performance tier outright, **GLM 5.2** sits among the Opus-line models at ~22% of Opus 4.8's cost, and **DeepSeek V4 Flash** / **Gemma 4 31B** deliver credible budget performance at ~2-3% — strong options at every price point without a monthly commitment. [Get a key here](https://openrouter.ai/). |
| **OpenAI** (API key or ChatGPT subscription) | OpenAI API pay-per-use, or your existing ChatGPT subscription | Configure via `environment_settings.txt` + one rebuild ([Option F instructions](#option-f-openai-api-directly-daaf-provider-shim)) | Run DAAF on GPT models with no Anthropic account. These are supported routes that benefit from wider community testing; the ChatGPT-subscription lane in particular has a smaller context ceiling, so it comes with practical [session-length guidance](#option-f-alternate-lane-chatgpt-subscription-codex-backend). |
| **Cloud providers** (Bedrock, Vertex AI) | Per your organization's arrangement | Configure via `environment_settings.txt` ([instructions below](#configure-authentication-via-environment_settingstxt)) | Route through your org's existing cloud platform. DAAF provides configuration templates for these (see `environment_settings_example.txt` in `daaf-docker` for the required variables), aimed at organizations already running on Bedrock or Vertex. Note that DAAF's maintainers haven't been able to validate these two routes end-to-end ourselves — so treat them as a starting point you'll stand up and test in your own environment, and please share reports if you run them. |

**Not sure which to pick?** Start with the lower Max subscription ($100/mo plan) to test things out and get a sense of how you might want to use DAAF. Then adjust methods or subscription levels as need arises.

**How authentication works:** For the **Max subscription** and **API key** options, Claude Code will prompt you to authenticate interactively the first time you run it -- you don't need to configure anything in advance. For **OpenRouter**, **OpenAI**, and **cloud provider** setups, you'll configure credentials via the `environment_settings.txt` file instead (instructions below). You can always switch between methods later (type `/login` inside Claude Code to change your interactive authentication, or update your `environment_settings.txt` file and restart the container). Note that many terminal interfaces "hide" any password-entry you're asked to do, so if you don't see your typing "working," it's working but hiding it from view for your privacy.

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

The DAAF Control Panel (`daaf.sh` on macOS/Linux, `daaf.ps1` on Windows) is an interactive menu with a status dashboard, service management, and all DAAF operations in one place. The dashboard is live — it shows at a glance which of DAAF's web services (notebooks, log viewer, and the browser-based code editor) are actually up and listening, so you can see the state of your install before choosing an action. Select **option 1, "Start Claude Code,"** from the menu to get started.

**Prefer not to type in the terminal? Double-click instead.**

If terminal commands feel like a hassle, you can open the Control Panel straight from your file explorer:

- **Windows:** open the `daaf-docker` folder in File Explorer and double-click **`daaf.bat`**. The installer also drops a **DAAF** shortcut (`DAAF.lnk`) inside that same folder — drag it to your Desktop or taskbar if you want one-click access from there.
- **macOS:** open the `daaf-docker` folder in Finder and double-click **`DAAF.command`**.
- **Linux:** no double-click launcher ships, because Linux desktop environments run double-clicked scripts too inconsistently to rely on. Use the terminal command above instead — most file managers offer a right-click "Open Terminal Here" on the `daaf-docker` folder, after which you just run `bash daaf.sh`.

These launchers are thin shortcuts to the very same Control Panel — they simply move into the `daaf-docker` folder and run `daaf.sh`/`daaf.ps1` for you. The terminal commands above always work as the universal fallback on every platform. (If you ever obtain `DAAF.command` by downloading it in a browser rather than from the installer, macOS may block it once as coming from an "unidentified developer" — allow it via **System Settings > Privacy & Security > "Open Anyway"**. Copies the installer places for you are not blocked.)

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

### Configure Claude Code (optional)

Once you're in, there are a few settings you can adjust to your liking. You can check which Claude model is being used by checking the indicator below the chat line (Opus, Sonnet, Haiku). DAAF defaults to using **Opus 4.8** with 1 million token context -- no action needed on your part. You can change which Claude model is being used at any time by typing `/model`. Development and testing has spanned several Anthropic model generations, and [empirical benchmarking across 29 Anthropic, OpenAI, Google, and open-weight models](https://daaf.openaugments.org/bench/) has shown that several models perform excellently with DAAF's orchestration workflows -- at very different price points.

The short version, as of the July 2026 corpus: **Fable 5** is the top performer if budget is not a constraint; **GPT-5.6 Sol** and **Sonnet 5** deliver top-tier performance at moderate cost; **GPT-5.6 Luna** covers most of that capability for a fraction of the spend; and on the open-weights side, **Kimi K3** reaches the top tier while **GLM 5.2**, **DeepSeek V4 Flash**, and **Gemma 4 31B** anchor the self-hosting and budget end. The canonical, regularly refreshed guidance table lives in the FAQ — see [**Which Claude model should I use?**](07_faq_technical.md#q-which-claude-model-should-i-use) — and because new model generations arrive faster than we can revise this guide, treat [daaf.openaugments.org/bench](https://daaf.openaugments.org/bench/) as the live results page rather than assuming any table in the docs is current. It helps to be clear about what these scores can and can't decide for you. This testing (called DAAFBench, with full public results at [daaf.openaugments.org/bench](https://daaf.openaugments.org/bench/)) measures how reliably a model *follows DAAF's process* — classifying your request correctly, dispatching the right specialists, loading the right skills, and honoring the confirmation gates. That is exactly the question that matters when you're weighing a model against your budget: it tells you which models you can trust to drive the framework faithfully at a given price point. What it does **not** measure is which model produces *better research* — the depth of analytical reasoning and judgment on the hardest problems. Opus may still have an edge there, though the gap between the top models is smaller than once assumed. So use the scores to pick a model you can afford that stays on-protocol, and remember that your own review of the output is still what judges the quality of the analysis itself.

Current Claude models also let you select a "thinking level" by tapping the left-and-right arrow keys while the model is selected on the /model selector in Claude Code. All tests I've conducted to date use the "High" setting -- as this is a case where quality is far more important than quantity, I strongly recommend doing the same. This will have usage and API limit ramifications, though, so it is a reasonable thing to test out the tradeoffs for yourself. The [DAAFBench results](https://daaf.openaugments.org/bench/) are a great starting reference for understanding the quality-cost frontier across models. Please do report back with any findings so we can continue to refine this guidance!

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

The DAAF Control Panel provides an interactive menu with a status dashboard, service management, and all DAAF operations in one place. Choose **option 1, "Start Claude Code,"** to begin a session.

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

The DAAF Control Panel is your launcher for any DAAF-related tools, but you can also launch them individually if you'd prefer for any reason. Some useful things to be aware of:

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

The easiest way to browse, edit, and manage your files is with DAAF's built-in **browser-based code editor** (VS Code in the browser). The simplest way to open it is from the **DAAF Control Panel** — run `bash daaf.sh` (`.\daaf.ps1` on Windows) in your `daaf-docker` folder and choose **option 2, "Browse Files (VS Code)."** If you prefer the direct command, run this from your `daaf-docker` folder on your computer (no need to enter the container):

```bash
cd daaf-docker
bash run_vscode.sh              # macOS / Linux
.\run_vscode.ps1                # Windows
```

This opens a full VS Code editor at the URL [http://localhost:2720](http://localhost:2720) running in your favorite browser where you can explore the entire DAAF file tree, edit files, preview Markdown reports, view/edit Python and R scripts, and track changes with the built-in Git tools. It comes pre-loaded with extensions for Python and R syntax highlighting, Markdown preview, Git history visualization, CSV viewing, and folder compression (for easy downloads — see *Getting files OUT of the container* below). The password is displayed in the terminal when you launch the script (default: `daaf`). A few things worth highlighting:

- **The default access password is "daaf"** but the password can be customized at any time in your environment_settings.txt file. See the environment_settings_example.txt in your daaf-docker folder for instructions there.
- **Markdown preview:** Right-click any `.md` file and select **"Open Preview"**, or press `Shift+Ctrl+V`, to see rendered Markdown with proper formatting — headers, tables, links, and all. This is the easiest way to read DAAF's reports and plans.
- **File management:** Use the file explorer sidebar to browse, create, rename, move, and delete files. You can also drag and drop files from your computer into the sidebar to import them into the Docker volume.
- **Git integration:** The Source Control panel (left sidebar) shows uncommitted changes and lets you view diffs — the most direct way to review exactly what DAAF produced during a session — and, if you've enabled the optional "Git commit management" preference, browse commit history too.
- **Search:** Use `Ctrl+Shift+F` (or `Cmd+Shift+F` on Mac) to search across all files — helpful for finding specific variables, scripts, or content across a project.

**Getting files INTO the container:** To bring files from your computer into the Docker volume for DAAF to use (e.g., a dataset you want to profile), simply drag and drop them from your computer onto the code editor's file explorer sidebar. This works for individual files *and* for whole folders — drop a folder and the editor copies its entire contents (including subfolders) into the location you drop it. Drag-and-drop upload works in Chrome, Edge, and Firefox.

**Getting files OUT of the container:** How you export depends on whether you want a single file or a whole folder:

- **A single file** — right-click the file in the explorer sidebar and choose **Download**. This works in every browser.
- **A whole folder (works in any browser)** — the most reliable way to export a folder is to zip it first: right-click the folder, choose **Compress → zip**, then right-click the new `.zip` file that appears next to the folder and choose **Download**. You get one tidy archive on your computer that you can unzip normally. When compressing, stick to the **zip**, **tar**, or **tgz** options — the **bz2** and **7z** choices will fail, because the tools they need aren't installed in the container.
- **A whole folder (Chrome or Edge only, shortcut)** — if you use Chrome or Edge, you can also right-click a folder and choose **Download** directly. Your browser asks you to pick a destination folder on your computer and then copies the files into it individually (you get the files themselves, not a single zip). This shortcut relies on a browser capability that only Chrome and Edge provide, so in Firefox or Safari, use the Compress → zip → Download method above instead.

The **Compress → zip** submenu comes from a built-in extension, so it's ready to use immediately with no setup. (One caveat for long-time users: if your DAAF install predates this extension and you don't see the **Compress** menu, update DAAF and rebuild once — `bash rebuild_daaf.sh` or `.\rebuild_daaf.ps1` from your `daaf-docker` folder — to pick it up.) If you prefer working in the integrated terminal, `zip -r archive.zip myfolder/` (or `tar czf archive.tgz myfolder/`) produces the same kind of archive, which you can then download by right-clicking it.

You can also use the Docker Desktop GUI to explore the DAAF docker volume by navigating to the Volumes panel, clicking the daaf_daaf-data volume, and interacting with the file navigator here.

**Getting files in and out — quick tips:**

- **Downloading a report or figure folder (the easy path):** right-click the folder in the editor's file explorer and choose **Compress → zip** (provided by the built-in vscode-archive extension, which also offers **Decompress**), then right-click the new `.zip` and choose **Download** — you get one tidy archive on your computer (full details in *Getting files OUT of the container* above).
- **Getting a large research folder out wholesale:** rather than zipping folder by folder, take a full **backup** — from the DAAF Control Panel choose **option 7, "Create Backup"** — which copies *everything* (all your research data) out to your host machine in one step. See [**Backing Up Your Work**](#backing-up-your-work) below.
- **Bringing files in:** drag and drop them from your computer straight onto the editor's file explorer sidebar — this works for single files and whole folders (see *Getting files INTO the container* above).

### Linking Host Folders into the Container (Bind Mounts)

The drag-and-drop upload described above is the right tool for most files. But if you have a **large local dataset** — tens of gigabytes of parquet, a folder of survey extracts, a directory you refresh regularly from elsewhere — copying it through the browser editor is slow and duplicates the data into the Docker volume. For those cases you can **bind-mount** a folder on your computer straight into the container, so DAAF reads your files in place. Reach for this when the data is bulky or lives naturally on your host; stick with the [drag-and-drop upload](#viewing-and-editing-files) for the occasional single file or small dataset.

DAAF ships this capability **off by default** as a commented-out block in `docker-compose.yml` that you opt into. The recommended pattern is a **read-only** mount of one host folder onto `/host_data` inside the container.

**Set it up (edit in the container, then rebuild):**

1. **Open the container's copy of `docker-compose.yml`.** Edit it *inside* the container — either ask Claude to edit `/daaf/docker-compose.yml`, or open it in the [browser-based code editor](#viewing-and-editing-files). This matters: `rebuild_daaf.sh` copies the container's compose file *out* to your host and rebuilds from it, so a host-side edit is silently overwritten on the next rebuild. Editing the container copy is the only change that survives.
2. **Uncomment the bind-mount block** in the `daaf-docker` service's `volumes:` section and set `source:` to the folder on your computer you want to expose. Leave `read_only: true` in place:
   ```yaml
   # In the daaf-docker service, under volumes:
   - type: bind
     source: /Users/yourname/datasets   # <-- your host folder (Windows: C:\Users\yourname\datasets)
     target: /host_data
     read_only: true
   ```
3. **Rebuild so the host picks up the change:**

   **macOS / Linux (Terminal):**
   ```bash
   cd daaf-docker
   bash rebuild_daaf.sh
   ```

   **Windows (PowerShell):**
   ```powershell
   cd daaf-docker
   .\rebuild_daaf.ps1
   ```

Your files now appear at `/host_data` inside the container, and DAAF can read them directly.

**Why the long (`type: bind`) syntax?** DAAF uses the verbose form on purpose: if you mistype `source:`, Docker **fails loudly** with a clear error. The short one-line form (`./typo:/host_data`) instead **silently creates an empty directory** at the bad path — so a typo would leave DAAF staring at an empty `/host_data` with no hint why.

**Permissions: will your files be readable?** The container runs as a non-root user, `appuser` (UID/GID **1000**), and — unlike the two managed Docker volumes — a bind mount is **not** ownership-corrected by DAAF's `daaf-init` step. Whether `appuser` can read your files therefore depends on your platform:

| Your platform | Read-only mount | What's happening |
|---------------|-----------------|------------------|
| **macOS (Docker Desktop)** | Generally just works | Docker Desktop translates/fakes ownership, so your files appear owned by the container user regardless of your Mac UID (behavior is version-dependent; rare file-sharing bugs exist) |
| **Windows — `/mnt/c/...` (WSL2)** or a path shared in Docker Desktop | Just works | Windows permissions are translated through the Docker Desktop file-sharing layer |
| **Native Linux** | Works **if** UID 1000 can read the files | Real UID/GID pass-through — no translation layer. Only the numbers matter, not usernames |
| **Windows — WSL filesystem path** (`/home/<you>` inside a distro) | Works **if** UID 1000 can read the files | Native Linux rules apply inside the distro — the same case as native Linux |

On the two "if" rows, diagnose with `ls -ln` (the `-n` shows **numeric** owner IDs): if your files aren't owned by `1000` and aren't world-readable, `appuser` can't read them. The simplest fix for a read-only data folder is to make it group- or world-readable on the host.

**Advanced: write-enabled mounts.** Keep `read_only: true` unless you have a specific reason to let the container write back to your host folder — a read-only mount is safer and keeps DAAF from ever modifying your source data. If you *do* need writes (drop `read_only: true`), permissions get stricter:

- **Native Linux / WSL-filesystem paths:** the container writes files as UID 1000, so align ownership — either `chown` the host folder to UID 1000, or add yourself to a shared group and make the folder group-writable. **Don't reach for `chmod 777`** — it works, but it exposes the folder to every user on the machine; group alignment is the right tool.
- **macOS and Windows `/mnt/c` paths:** writes "just work" through the Docker Desktop translation layer, with files landing under your host user on the other side.

> **Reproducibility trade-off — a deliberate decision to make.** Bind-mounted files live **outside** DAAF's archive and hash boundary: they are not captured by `backup_daaf.sh` and not part of the project's audit trail. That means reproducing the analysis later depends on *you* guaranteeing the same files are present at the same mount point — DAAF can't freeze them for you. The recommended mitigation is to have your **fetch scripts copy** the inputs you actually use from `/host_data` into the project's own `data/raw/` directory (with the normal raw-data naming conventions). The bind mount then serves as a fast on-ramp, while the archived working copy inside the project keeps the audit trail complete.

> **Boundary.** `/host_data` is *not* covered by `backup_daaf.sh`, so never treat it as a place to store DAAF outputs — write results into your project as usual. And never point a bind mount at the container's own system paths (`/daaf`, `/daaf/.claude`, and the like): mounting over DAAF's own files would shadow them and break the install.

### Backing Up Your Work

Since your research files live inside the Docker volume, it'll be extremely important to regularly back up your work separately from the Docker volume. The easiest way is from the **DAAF Control Panel** — run `bash daaf.sh` (`.\daaf.ps1` on Windows) in your `daaf-docker` folder and choose **option 7, "Create Backup."** (If you've set up a [shared research workspace](#sharing-one-research-workspace-across-two-installs-advanced) across two installs, note the caveat in that section: run backups from **one** install only.) If you'd rather call the backup script directly, that works too:

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

The backup script also checks itself as it goes: it verifies there's enough free disk space before it starts (and stops with a clear message if there isn't), and after copying it compares the backup against the original — checking both the number of files and their total size. How a shortfall is handled depends on how serious it is. If the copy step itself reports an error *and* fewer files landed than the volume scan expected, the backup is treated as genuinely incomplete: the script stops with an error and a nonzero exit code, and tells you to delete the partial backup folder and re-run once the problem is resolved (any tool that ran the backup for you — the updater or the migration tool — then halts too, rather than continuing on top of a bad backup). A milder discrepancy — the copy reported success but the file count or total size is still a little off — is flagged as a warning instead: the backup finishes, but its completion banner reads `Backup completed WITH WARNINGS -- verify before relying on it` rather than the plain `Backup complete!`, so a questionable backup never passes silently.

The backup covers both DAAF volumes: your research data, plus Claude Code's own state (your login, session history, and plugins) in a hidden `.daaf-claude-config/` subfolder. **Because the backup includes your Claude Code login credentials, treat backup folders as sensitive** — store them somewhere private, and if you share a backup with a colleague for collaboration, delete the `.daaf-claude-config/` subfolder from the copy first. (The backup also contains one or two small hidden manifest files you can ignore — the restore consumes them automatically. `.daaf-permissions` records which files were executable, so the restore can put file permissions back correctly even when the backup was stored on a Windows drive, which does not preserve them. `.daaf-symlinks`, present only when your data contains symbolic links, records those links so the restore can recreate them — this is what lets backups complete cleanly on Windows, where the copy step would otherwise stop at the first symbolic link.)

You can also back up manually using Docker Desktop's GUI: go into the Docker volume file viewer (see above) and download the whole `daaf` or `research` folder to somewhere else on your computer.

### Restoring from a Backup

If you need to restore your DAAF installation from a backup, the simplest path is the **DAAF Control Panel** — run `bash daaf.sh` (`.\daaf.ps1` on Windows) in your `daaf-docker` folder and choose **option 8, "Restore from Backup."** It (like the direct script below) searches your `daaf-docker` folder for backup folders, lets you pick one, and handles replacing the Docker volume contents cleanly. To call the restore script directly instead:

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

**Important:** Restoring is a destructive operation -- the script completely erases the current Docker volume contents and replaces them with the backup. Make sure DAAF is not running when you restore (run `docker compose down` first if needed). The script checks for running containers and warns you if any are active. Because it is destructive, the restore will not proceed until you explicitly confirm — it asks you to type `RESTORE` (in capital letters) before it overwrites anything, and cancels safely if you type anything else.

If the backup contains Claude Code state (newer backups do — see above), the restore also brings back your Claude Code login and session history, replacing whatever login is currently in the installation. Older backups made before this feature restore your research data only, with a note that you'll need to run `/login` in Claude Code afterward.

**A note on git and DAAF:** A full git repository is set up inside the Docker volume during installation (via the `git clone` in the installer). By default, DAAF does **not** make git commits during your research sessions — and it doesn't need to. Every script version is preserved right in your project folder, including failed attempts (DAAF saves fixes as new numbered versions rather than overwriting the original), so the project folder itself is a complete, human-readable audit trail of your research. If you'd like git-based version tracking on top of that, you can turn on the optional **"Git commit management"** preference (in `CLAUDE.md`, under § User Preferences); once enabled, DAAF will suggest commits at natural milestones and always ask you before committing anything. Either way, a remote is configured by default (pointing to the upstream DAAF repository for updates), but nothing is ever pushed there without your explicit instruction. Your research work lives safely in the Docker volume. If you want a GitHub backup for your work, ask Claude how to make your own repository and save to it accordingly.

### Viewing Session Logs in Your Browser

DAAF includes an interactive timeline viewer (the **DAAF Log Explorer**) that lets you visually explore what happened during any session -- every tool call, subagent dispatch, and file reference, organized chronologically.

**Quickest way -- from the DAAF Control Panel:** run `bash daaf.sh` (`.\daaf.ps1` on Windows) in your `daaf-docker` folder and choose **option 3, "View Session Logs."** You can also call the script directly from your host machine (no container shell needed):

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

**Quickest way — from the DAAF Control Panel:** run `bash daaf.sh` (`.\daaf.ps1` on Windows) in your `daaf-docker` folder and choose **option 4, "View Marimo Notebooks (Python)."** You can also call the script directly from your host machine (no container shell needed):

```bash
cd daaf-docker
bash view_notebooks.sh       # macOS / Linux
.\view_notebooks.ps1         # Windows
```

This opens marimo's built-in notebook browser at [http://localhost:2718](http://localhost:2718), where you can browse all your research projects and open any notebook for viewing or editing. The script handles starting the container if it isn't already running. The nice thing about these is that they're also written in regular Python code, so you can inspect its code very easily in any text editor as well.

### Viewing Quarto Documents

> This applies to R projects.

R projects produce **Quarto** notebooks (`.qmd` files) instead of Marimo notebooks. In a Full Pipeline project, the Quarto file is a polished **audit document**: it presents narrative context, the literal code from already-executed R scripts, their captured execution logs, existing figures, and small static data previews. The archived Stage 5-8 script chunks remain disabled during rendering; only explicitly enabled preview chunks run. Rendering therefore validates and formats the document—it does not rerun the analytical pipeline. The resulting HTML is viewable in any web browser.

**Quickest way -- from the DAAF Control Panel:** run `bash daaf.sh` (`.\daaf.ps1` on Windows) in your `daaf-docker` folder and choose **option 5, "View Quarto Notebooks (R)."** You can also call the script directly from your host machine (no container shell needed):

```bash
cd daaf-docker
bash view_quarto.sh                                 # macOS / Linux
.\view_quarto.ps1                                   # Windows
```

With no argument -- including when you choose **option 5** in the DAAF Control Panel -- the viewer recursively discovers every `.qmd` anywhere below `research/`, sorts the paths deterministically, and shows a numbered picker. Enter a notebook number to render it. Enter `0`, press Enter on a blank choice, type `q` or `Q`, or send end-of-file to cancel cleanly and return without rendering.

You can still bypass the picker by passing either a project folder or a direct `.qmd` path. A project name is accepted only when exactly one notebook exists anywhere below that project; if recursive lookup finds multiple notebooks, the viewer refuses to guess and prints the paths so you can use the direct form:

```bash
bash view_quarto.sh 2026-01-24_Your_Project
bash view_quarto.sh research/2026-01-24_Your_Project/output/analysis/notebook.qmd

.\view_quarto.ps1 2026-01-24_Your_Project
.\view_quarto.ps1 research/2026-01-24_Your_Project/output/analysis/notebook.qmd
```

The script renders the selected notebook to a single self-contained HTML file inside the container, copies it out to a `quarto_html/` folder next to your `docker-compose.yml`, and opens it in your default browser. It handles starting the container if it isn't already running. The host output keeps only the notebook's **flat basename** (for example, both `project-a/output/analysis/report.qmd` and `project-b/report.qmd` become `quarto_html/report.html`), so a later render with the same basename overwrites the earlier file. Set `QUARTO_HTML_DIR` to a different host directory before each render when you need to retain both. This is the R-notebook counterpart to `view_notebooks.sh` for Python (marimo) projects.

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

DAAF is actively being developed and updated. If you'd like to pull in the latest fixes, extensions, and updates (which for a while may be as often as daily!!), updating is straightforward. Before updating, I recommend backing up your Docker volume's research folder as a precaution (see "Backing Up Your Work" above). The update process is also demonstrated in the [Getting Started video](https://youtu.be/BPlR9bXZxnY).

### If you installed with the one-line installer (recommended method)

Assuming you used `install.sh` or `install.ps1`, your DAAF container has a full git repository with a remote configured. The simplest way to update is from the **DAAF Control Panel** — run `bash daaf.sh` (`.\daaf.ps1` on Windows) in your `daaf-docker` folder and choose **option 9, "Check for Updates."** If you prefer, you can also run the update script directly from your `daaf-docker` folder on the host:

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
- **Offers Claude Code for conflicts** — if a merge conflict occurs, you can launch Claude Code directly to help resolve it interactively. And you don't have to start over afterward: once the conflict is resolved and committed, just re-run the updater — it picks up where it left off, restoring any set-aside changes and finishing the remaining steps (script syncing and the rebuild check) automatically
- **Syncs utility scripts** — automatically copies updated host-side scripts (the Control Panel, run, backup, rebuild, update, and the rest) out of the container to your `daaf-docker` folder. It figures out the full list from the newly updated repository itself, so newly added host scripts are picked up automatically without you having to do anything. If a host file has drifted from the repository version (a stale copy from an interrupted sync, for example), the updater replaces it and saves your previous copy as `<name>.pre-update` in the same folder — delete it once everything works, or rename it back to restore.
- **Auto-rebuilds if needed** — if the Dockerfile or docker-compose.yml changed, it offers to run `rebuild_daaf` automatically

> **If the updater tells you it updated itself, run it once more.** The update script is one of the files it keeps in sync, so occasionally an update includes a newer version of the updater. When that happens it copies the new updater into place and prints a notice asking you to run `bash update_daaf.sh` (or `.\update_daaf.ps1`) again. This second run uses the new updater and finishes applying everything. This is expected and safe — running it twice never does any harm, and if there is nothing left to do it will simply report "Already up to date!" and exit.

By default, the update script auto-detects the remote's default branch (`main` or `master`). If you want to update from a specific branch instead (e.g., `dev`), you can tell the updater which branch to track in one of three ways.

**Direct invocation (one-off).** Set `DAAF_BRANCH` right on the update command:

```bash
# macOS / Linux
DAAF_BRANCH=dev bash update_daaf.sh

# Windows PowerShell
$env:DAAF_BRANCH = "dev"; .\update_daaf.ps1
```

**From the Control Panel.** If you run updates through the DAAF Control Panel (`daaf.sh` / `daaf.ps1`) rather than calling `update_daaf` directly, the variable must be **exported** (macOS/Linux) or set as a process-scoped `$env:` variable (Windows) *before* you launch the panel. The panel runs the updater as a child process, and a child process only inherits variables that were exported or process-scoped — a plain, unexported shell variable will not carry through:

```bash
# macOS / Linux
export DAAF_BRANCH=dev
bash daaf.sh

# Windows PowerShell
$env:DAAF_BRANCH = "dev"
.\daaf.ps1
```

**Persisted in `environment_settings.txt`.** `DAAF_BRANCH` is a recognized key in your `environment_settings.txt` file, so you can set it there once and every future update follows it without re-typing:

```
DAAF_BRANCH=dev
```

You usually don't even have to add that line by hand: when you run an update with `DAAF_BRANCH` set in your environment (either of the two methods above) and the update succeeds, the updater **saves that branch into your existing `environment_settings.txt` for you** (keeping a `.pre-update` backup of the prior file), so later updates track it automatically. If you have no `environment_settings.txt` yet, it prints a short note instead of creating one. When a branch is set in both places, the environment value always wins for that run.

If `DAAF_BRANCH` is set nowhere, the updater defaults to `main` (or `master` if `main` doesn't exist). Either way, the script validates that the branch exists on the remote before proceeding.

> **Tags behave differently from branches for updates.** `DAAF_BRANCH` steers *ongoing* updates, and only a **branch** can be followed — a version tag like `v3.0.1` is a fixed snapshot with nowhere newer to move to. The updater handles a tag two ways depending on where it came from:
> - **Set in your environment** (e.g. `DAAF_BRANCH=v3.0.1 bash update_daaf.sh`): the updater **declines**, explains why, makes no changes, and points you at the supported way to move onto a release — re-running the installer pinned to that tag (see ["Installing a specific version or branch"](#installing-a-specific-version-or-branch) below). A tag is never saved as your update branch, so ongoing updates keep tracking your persisted or default branch.
> - **Left over in `environment_settings.txt`** (for example after a tagged install): the updater prints a warning naming the file and key, then falls back to the auto-detected default branch for that run so you are never locked out. Edit the file to set a real branch (or remove the line) to silence the warning.

Your research files in `research/` are not tracked by git (they're local to your volume), so they are completely unaffected by updates.

**If the Dockerfile changed** (new packages, updated Claude Code version, etc.), you'll also need to rebuild the Docker image. The update script will detect this automatically and print instructions. The easiest way to rebuild is from the **DAAF Control Panel** — run `bash daaf.sh` (`.\daaf.ps1` on Windows) in your `daaf-docker` folder and choose **option 10, "Rebuild Container."** The direct command works too:

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
git checkout v3.0.1
```

Check the [Releases page](https://github.com/DAAF-Contribution-Community/daaf/releases) to see what's changed in each version.

### Migrating from an older installation

If you installed DAAF **v2.0.1 or earlier** — back when the installation process involved downloading a ZIP file and copying it into Docker — you may not have the update scripts (`update_daaf.sh` / `update_daaf.ps1`) in your `daaf-docker` folder. Without these scripts, you can't use the standard update process described above.

**How to tell if this applies to you:** Open your `daaf-docker` folder on your computer (wherever you originally set up DAAF). If you don't see a file called `update_daaf.sh` (macOS/Linux) or `update_daaf.ps1` (Windows), you need to run the one-time update migration first.

**What the migration does:**

- Downloads the host-side utility scripts (the `daaf` Control Panel and its `daaf_lib` helper library, plus `run_daaf`, `update_daaf`, `backup_daaf`, `restore_from_backup`, `rebuild_daaf`, `view_logs`, `view_notebooks`, `view_quarto`, and `run_vscode`) to your host machine so you have all the same convenience tools as a fresh install
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
export DAAF_BRANCH=v3.0.1
curl -fsSL "https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/${DAAF_BRANCH}/scripts/host/install.sh" | bash

# Install from a development branch
export DAAF_BRANCH=dev
curl -fsSL "https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/${DAAF_BRANCH}/scripts/host/install.sh" | bash
```

**Windows (PowerShell):**

```powershell
# Install a tagged release
$env:DAAF_BRANCH="v3.0.1"; irm "https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/$env:DAAF_BRANCH/scripts/host/install.ps1" | iex

# Install from a development branch
$env:DAAF_BRANCH="dev"; irm "https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/$env:DAAF_BRANCH/scripts/host/install.ps1" | iex
```

This fetches the installer itself from the specified branch or tag, and also controls the Docker build files and repository clone, so everything comes from the specified ref consistently. The `export` on macOS/Linux is required so that the variable is inherited by the `bash` process on the other side of the pipe. Check the [Releases page](https://github.com/DAAF-Contribution-Community/daaf/releases) to see available versions. If `DAAF_BRANCH` is not set, the installer defaults to `main`.

> **Note:** The installer accepts both branch names and version tags, but the **updater** (`update_daaf.sh` / `update_daaf.ps1`) tracks branches only. Because of this, when you install pinned to a *tag* the installer deliberately does **not** persist it into `environment_settings.txt` (a persisted tag would block future updates), so you do not need to do anything special at update time — updates fall back to the default branch automatically. See [Keeping DAAF Updated](#keeping-daaf-updated) above for exactly how the updater treats a tag set in your environment versus one left in the settings file.

### Automatic settings seeding at install time

When the installer finishes, it sets up your `environment_settings.txt` so any DAAF options you chose at install time carry forward on their own:

- **If you have no `environment_settings.txt` yet** (a typical fresh install), the installer copies the `environment_settings_example.txt` template into place as your new `environment_settings.txt`, then activates any of the six install-time `DAAF_*` options it finds in your environment — `DAAF_PROJECT_NAME`, `DAAF_PORT_MARIMO`, `DAAF_PORT_LOGVIEWER`, `DAAF_PORT_VSCODE`, `DAAF_DEV`, and `DAAF_BRANCH` — writing each one into the file in its proper place (in context, right where that setting is documented). So if you exported any of these before installing (for a specific branch, a second instance, or a developer build), you don't have to re-enter them: they're already saved for every future launch and update.
- **`DAAF_BRANCH` is seeded only when it names a branch.** If you installed pinned to a version *tag* (e.g. `v3.0.1`), the installer does **not** write that tag into the file — a persisted tag would block future updates — and prints a short note saying so. Ongoing updates then track the default branch (see [Keeping DAAF Updated](#keeping-daaf-updated)).
- **Seeded settings take effect immediately — the installer restarts the container for you.** Because Docker injects `environment_settings.txt` into the container when the container is *created*, and a fresh install creates the container before the seeded file exists, the installer finishes by briefly recreating the container so your new settings file is in effect right away. This is automatic and takes only a few seconds; your files are safe in the Docker volume. You will *not* see the "environment_settings.txt has been modified since this container was started" note on your first launch after a fresh install. In the rare event this restart step fails, the installer prints instructions — just run `docker compose down` from your `daaf-docker` folder and launch normally, which applies the settings the same way.
- **A reinstall never overwrites an existing `environment_settings.txt`.** If the file already exists, the installer leaves it completely untouched — your real API keys and settings are safe — and notes that any `DAAF_*` variables you set were used for that install run only. Because a reinstall reuses your existing file rather than re-reading your environment, install-time env vars must be set again on each reinstall to steer *that run*, and if you want to persist a *changed* value you edit the file yourself.
- **The installer always prints an outcome note** at the end telling you exactly what happened — which values were seeded, that an existing file was preserved, or (in the rare event seeding can't complete) manual instructions for copying the template yourself. Seeding never blocks or fails the install.

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

**First build takes a while (both architectures).** The first image build downloads a large stack of Python and R packages, so it takes several minutes and has quiet stretches with little output. This is normal — the build is not hung — and it happens only once; later starts are fast because Docker caches the image.

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

Most people run a single DAAF installation and never need this section. But if you want **two (or more) independent DAAF installs on the same machine** — for example, one folder for work and another for personal projects, each with its own Docker volume and research history — you can, with a small amount of configuration. (If instead you want two installs to **share** one research workspace — say, to work the same projects from both a Claude and a ChatGPT install — see [Sharing One Research Workspace Across Two Installs](#sharing-one-research-workspace-across-two-installs-advanced) below; that pattern is the deliberate exception to the per-instance volumes described here.)

Two things must be unique per install so they don't collide:

1. **The Compose project name** — this determines the container name and the Docker volume (`<project>_daaf-data`) that holds your files. Two installs sharing a project name would share a volume.
2. **The three published localhost ports** — `2718` (notebooks), `2719` (log viewer), and `2720` (VS Code). Two installs cannot both publish the same host port.

To set up a second instance, choose a distinct project name and three free host ports, **set them as environment variables first, then run the installer** into a second, separate folder. Setting them *before* the install matters: they take effect during the install itself — so the second instance builds with the right project name and ports and never collides with the first — and the installer's [automatic settings seeding](#automatic-settings-seeding-at-install-time) writes them straight into the new instance's `environment_settings.txt`, so they persist for every later launch and update with nothing more to do.

**macOS / Linux (Terminal):**

```bash
export DAAF_PROJECT_NAME=daaf-personal
export DAAF_PORT_MARIMO=2818
export DAAF_PORT_LOGVIEWER=2819
export DAAF_PORT_VSCODE=2820
curl -fsSL https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/install.sh | bash
```

**Windows (PowerShell):**

```powershell
$env:DAAF_PROJECT_NAME = "daaf-personal"
$env:DAAF_PORT_MARIMO = "2818"
$env:DAAF_PORT_LOGVIEWER = "2819"
$env:DAAF_PORT_VSCODE = "2820"
irm https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/install.ps1 | iex
```

(These four variables are documented in `environment_settings_example.txt`. Any free ports work — the numbers above are just an example offset by 100. On macOS/Linux the `export` is what lets the values carry through the pipe into the installer; on Windows `$env:` values are process-scoped and carry through automatically.)

After the install, `environment_settings.txt` in that second folder is the permanent home for these values — the installer seeded them there for you. To change them later, edit that file and recreate the container:

```
docker compose down
bash run_daaf.sh            # macOS / Linux
.\run_daaf.ps1             # Windows
```

The DAAF launcher and control-panel scripts (`run_daaf`, `daaf`, the `view_*` browsers, `update`, `rebuild`, `backup`, `restore`) read these values from `environment_settings.txt` automatically, so the status dashboard and the browser URLs they print will point at the correct ports for each instance.

> **If you run bare `docker compose` commands directly** (outside the provided scripts) in a multi-instance folder, you must also create a `.env` file in that `daaf-docker` folder containing the same `DAAF_PROJECT_NAME` / `DAAF_PORT_*` lines. Docker Compose reads `.env` (and your shell environment) when resolving the `${...}` placeholders in `docker-compose.yml`, but it does **not** read `environment_settings.txt` for that purpose — that file only feeds the container's own environment. The DAAF scripts bridge this gap for you; bare `docker compose` does not.

> **Changing these on an existing install** requires the same `docker compose down` + relaunch: the project name and published ports are baked in at container-creation time, so a running container will not adopt new values until it is recreated. Your data volume moves with the project name — renaming `DAAF_PROJECT_NAME` on an existing install points it at a *different* (empty) volume, so choose the name once, up front.

### Sharing One Research Workspace Across Two Installs (Advanced)

The section above sets up **independent** instances — each with its own research volume and history. This one does the opposite: it points **two** DAAF installs at a **single, shared research workspace**, so both can work the same `research/` folder, projects, and audit trail.

The motivating scenario is running **two different AI providers against one body of work** — for example, one install authenticated to your **Claude (Anthropic) subscription** and a second install on your **ChatGPT subscription** via the [provider shim](#option-f-alternate-lane-chatgpt-subscription-codex-backend). Each install keeps its **own** configuration and authentication volume (`<project>_daaf-claude-config`), so their logins never collide — only the *research data* volume is shared.

DAAF supports this with a setting, **`DAAF_DATA_VOLUME_NAME`**, plus a second commented opt-in block in `docker-compose.yml`. `DAAF_DATA_VOLUME_NAME` overrides the full Docker volume name for the shared research data (leave it unset and each install gets its own default `<project>_daaf-data`, exactly as in the section above). Its value must match the `name:` in the compose file's external-volume block. The steps below convert two installs to share one volume.

**Step 1 — Install the first instance normally.** Follow the standard [installation](#installing-daaf), let it run, and confirm your research data is where you expect. Its data volume is `<project1>_daaf-data` (where `<project1>` is its `DAAF_PROJECT_NAME`, default `daaf` — so the default volume is `daaf_daaf-data`).

**Step 2 — Convert the first install to an external (shared) volume.** Edit the **container's** copy of `docker-compose.yml` (via Claude or the [browser editor](#viewing-and-editing-files) — remember `rebuild_daaf.sh` copies the container's copy out over the host one, so the container-side edit is the one that survives). Uncomment the external-volume block under the top-level `daaf-data:` key and set `name:` to the volume's **existing** full name:

   ```yaml
   volumes:
     daaf-data:
       external: true
       name: daaf_daaf-data      # <-- your existing <project1>_daaf-data volume
   ```

   Then set the matching line in the **host** `environment_settings.txt`:

   ```
   DAAF_DATA_VOLUME_NAME=daaf_daaf-data
   ```

   Rebuild (`bash rebuild_daaf.sh` / `.\rebuild_daaf.ps1`). Nothing about this install's behavior changes — it still uses the same data — but the volume is now declared `external`, which has one important consequence: **`docker compose down -v` will no longer delete it.** Compose never removes external volumes, so your shared research data is now immune to an accidental `-v` wipe. (Deliberate deletion still works via `docker volume rm` — see the caveats.)

**Step 3 — Install the second instance, pre-seeded to the shared volume.** Install into a **different folder**, giving it a distinct project name, distinct ports, **its own provider/auth settings** (e.g. the [ChatGPT-subscription shim lane](#option-f-alternate-lane-chatgpt-subscription-codex-backend)), and `DAAF_DATA_VOLUME_NAME` **exported at install time** so it lands in the new install's `environment_settings.txt` from the start (the value stays inert until Step 4 activates the shared volume):

   **macOS / Linux (Terminal):**

   ```bash
   export DAAF_PROJECT_NAME=daaf-gpt
   export DAAF_PORT_MARIMO=2818
   export DAAF_PORT_LOGVIEWER=2819
   export DAAF_PORT_VSCODE=2820
   export DAAF_DATA_VOLUME_NAME=daaf_daaf-data     # same shared volume as install #1
   curl -fsSL https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/install.sh | bash
   ```

   **Windows (PowerShell):**

   ```powershell
   $env:DAAF_PROJECT_NAME = "daaf-gpt"
   $env:DAAF_PORT_MARIMO = "2818"
   $env:DAAF_PORT_LOGVIEWER = "2819"
   $env:DAAF_PORT_VSCODE = "2820"
   $env:DAAF_DATA_VOLUME_NAME = "daaf_daaf-data"
   irm https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/scripts/host/install.ps1 | iex
   ```

**Step 4 — Convert the second install identically.** The installer still had to create the container from a compose file referencing this instance's *own* `<project2>_daaf-data`, so a transitional volume (`daaf-gpt_daaf-data` in the example) now exists and holds only the fresh repo clone. Convert this install exactly as in Step 2 — uncomment the external block in its container compose, set `name: daaf_daaf-data`, confirm `DAAF_DATA_VOLUME_NAME=daaf_daaf-data` is in its `environment_settings.txt`, and rebuild. Once it comes up on the shared volume, delete the now-orphaned transitional volume:

   ```bash
   docker volume ls | grep daaf-gpt_daaf-data      # confirm it exists and is unused
   docker volume rm daaf-gpt_daaf-data             # remove the orphaned transitional volume
   ```

**Step 5 — Steady state.** Both installs now mount the **same** `daaf_daaf-data` volume, which means they share **one** `/daaf` — including a single canonical `docker-compose.yml` and the whole framework tree. Because there is only one copy of those files, a rebuild of *either* install reads and writes the *same* compose file, so the two installs stay consistent by construction; you never maintain two diverging compose files. Each install still keeps its own separate `*_daaf-claude-config` volume, so its provider login and session history remain its own.

> **Caveats — read before you rely on this.**
> - **One active pipeline per research project at a time.** Docker provides *no* write coordination between two containers on one volume. Running two analysis pipelines against the same project simultaneously can corrupt files. Coordinate yourself: let one install work a given project at a time. (Working *different* projects in the shared workspace concurrently is fine.)
> - **Back up from one install only.** Both installs see the same data, so a single `backup_daaf.sh` run from *either* one captures everything — running backups from both just duplicates work and can race.
> - **Shim state splits across the two volumes.** Each container runs at most one provider-shim instance at a time. The shim's operational telemetry on the shared workspace (`scripts/provider_shim/logs/`) is therefore install-shared, while its reasoning-cache continuity file stays per-container on that install's own `*_daaf-claude-config` volume (`~/.claude/provider_shim/reasoning_cache.json`) — so the shim lane's reasoning continuity never crosses between the two installs.
> - **Deleting the shared volume is deliberate.** Because it's external, `docker compose down -v` won't touch it. To actually delete it you must bring **both** installs down (no container may reference it) and run `docker volume rm daaf_daaf-data` explicitly.
> - **The second install's initial clone is discarded.** The transitional `<project2>_daaf-data` volume created at Step 3 held only a fresh repo clone; converting to the shared volume in Step 4 abandons it (you delete it), and install #2 adopts install #1's existing `/daaf`. That's expected.

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

Including R (with the full package set and Quarto) accounts for roughly **2 GB** of the image size — approximately 8.6 GB with R versus 6.4 GB without — though the exact figures vary with your Docker version and platform.

**To use R**, just tell DAAF "set execution language to R" at the start of a session — no configuration files to edit. See the [R and Language Support FAQ](07_faq_technical.md#r-and-language-support) for details on switching between languages.

#### Coming from Stata or R? Get code comments in your language

If your background is in **Stata** or **R** rather than Python, you don't have to read unfamiliar code cold. Just tell DAAF your background once — for example, "I'm coming from Stata" or "my background is in R" — and it will offer to save that as a preference. From then on, every piece of analysis code DAAF writes carries inline comments showing the equivalent command in your language: Stata users see the `reghdfe`, `xtreg`, `esttab`, and `svy:` equivalents next to the Python (or R) that runs, and R users see their familiar `tidyverse`/`fixest` equivalents. This is powered by DAAF's built-in translation skills, so it stays accurate to the actual code. The preference persists across sessions, and turning it on is entirely conversational — there are no configuration files to edit and nothing to set up in advance. (Under the hood this sets the cross-language annotation preference described in `CLAUDE.md` § User Preferences; you never have to touch that file yourself.)

### Configure authentication via environment_settings.txt

By default, Claude Code prompts you to log in interactively the first time you launch it (browser-based OAuth or pasting an API key). This works great for Max subscription and direct API key setups — and since your login now persists across rebuilds, signing in once is genuinely enough. However, if you're using **OpenRouter**, a **cloud provider** (Bedrock/Vertex), or simply want your authentication to persist automatically without interactive login, you can configure it through the `environment_settings.txt` file in your `daaf-docker` folder. (Subscription users who run *several* DAAF installs, or who want fully non-interactive startup, have one more option there: a one-time `claude setup-token` command mints a long-lived token you can paste into the file — see Option B in its authentication section. A normal single install doesn't need it.)

Your `daaf-docker` folder includes an `environment_settings_example.txt` template. It opens with a table of contents and is organized into six numbered, lifecycle-tagged sections — **[1] Install & Update Settings**, **[2] Claude Code Authentication**, **[3] Model Routing**, **[4] Alternative Providers & Shim**, **[5] Data Source API Keys**, and **[6] Workspace & Developer Options** — so you can jump straight to the part you need. Authentication lives in **section [2]**, which covers the five direct authentication options (Options A-E) — plus interactive browser login, which needs no environment variables — and points to **section [4]** for the OpenAI/ChatGPT provider shim (Option F). To set it up:

1. **Make sure you have an `environment_settings.txt` file.** Recent installs seed one for you automatically ([see above](#automatic-settings-seeding-at-install-time)), so you may already have one — check your `daaf-docker` folder. If it isn't there yet, copy the template:

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

DAAF splits its background helper agents across two Claude model tiers to balance quality against cost: a stronger tier (**Opus**) for high-judgment and hands-on data work like planning, fetching and profiling data, review, and verification, and a faster tier (**Sonnet**) for well-defined support work like structured lookups and notebook assembly. If you use Anthropic directly (Max subscription or API key), this happens automatically and you don't need to do anything.

If you point DAAF at an **alternative provider** (OpenRouter, or a cloud platform serving non-Claude models like GLM), the names "opus" and "sonnet" won't exist on your endpoint. You have two options, both set in `environment_settings.txt`:

- **Keep the two tiers, using your own models** — map each tier to one of your provider's models:
  ```bash
  ANTHROPIC_DEFAULT_OPUS_MODEL=your-strong-model-slug
  ANTHROPIC_DEFAULT_SONNET_MODEL=your-fast-model-slug
  ```
  DAAF then routes high-judgment work to your strong model and routine work to your fast one.

  `CLAUDE_CODE_MAX_CONTEXT_TOKENS` is a **global** override: the same value
  applies to the main session and every subagent, not separately to each model.
  For the recommended 1,048,576-token declaration for exact `z-ai/glm-5.2`,
  keep every route on that exact model by mapping both tiers to it:
  ```bash
  ANTHROPIC_MODEL=z-ai/glm-5.2
  ANTHROPIC_DEFAULT_OPUS_MODEL=z-ai/glm-5.2
  ANTHROPIC_DEFAULT_SONNET_MODEL=z-ai/glm-5.2
  CLAUDE_CODE_MAX_CONTEXT_TOKENS=1048576
  ```
  Equivalently, you can flatten subagent routing to exact `z-ai/glm-5.2` with
  `CLAUDE_CODE_SUBAGENT_MODEL`. OpenRouter currently reports 1,048,576 tokens
  for exact `z-ai/glm-5.2`. This is the model's **physical** capacity; it does
  **not** claim that quality stays constant across the entire window. GLM keeps
  DAAF's conservative context-quality gates: ELEVATED at 150k or 40%, HIGH at
  200k or 60%, and CRITICAL at 250k or 75%, whichever trigger fires first.

  If you want `z-ai/glm-5.2-air` as the fast tier, do **not** reuse exact
  `z-ai/glm-5.2`'s 1,048,576 declaration unless you independently verify Air's
  current physical window and confirm the chosen global value is valid for the
  main session and every routed subagent. This runtime path has no supported
  per-model context-window override.

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
# Strong tier (Opus-analog):
ANTHROPIC_DEFAULT_OPUS_MODEL=openai/gpt-5.6-sol
# Fast tier (Sonnet-analog):
ANTHROPIC_DEFAULT_SONNET_MODEL=openai/gpt-5.6-terra
# Context window -- see "known limitations" below:
CLAUDE_CODE_MAX_CONTEXT_TOKENS=1050000
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
> **Avoid the `-pro` slugs via OpenRouter (Option C) — they fail and cost more.** `gpt-5.6-sol-pro` / `-terra-pro` / `-luna-pro` error out with hard "Prompt is too long" failures once a session grows past roughly 50k tokens, and they bill ~2-4x more for identical work (their token accounting runs ~4x the non-pro count against an enforced ~200k ceiling). Empirically verified across all three -pro variants in the 2026-07-10 DAAFBench smoke battery (see `benchmarks/README.md` § 1); the non-pro slugs are unaffected.

**Restart the container** (`docker compose down`, then `bash run_daaf.sh`) to pick up the changes. No rebuild is needed for OpenRouter — it is config-only.

#### Option F: OpenAI API directly (DAAF provider shim)

**Who this is for:** researchers who have an **OpenAI API key** (pay-per-use) and would rather talk to OpenAI directly, with no OpenRouter middle-hop.

**What you'll end up with:** DAAF running on GPT models through a lightweight translation shim that ships built into DAAF. The shim presents an Anthropic-compatible endpoint on `localhost`, forwards your requests to OpenAI, and starts automatically inside the container — once it's set up, you normally won't think about it again. (Would you rather use a **ChatGPT subscription** than a pay-per-use API key? Skip ahead to the [ChatGPT subscription lane](#option-f-alternate-lane-chatgpt-subscription-codex-backend) below.)

> **Billing prerequisite — API credits are separate from ChatGPT.** An OpenAI API key only works if its platform.openai.com project has **prepaid credits purchased**: adding a payment card alone is not enough (the $5+ credit purchase is a separate step), and new API accounts receive no free credits. A ChatGPT Plus/Pro subscription does **not** include API access — ChatGPT and the API are separate billing systems, and there is **no OpenAI-sanctioned** way to run a third-party tool like DAAF on a ChatGPT subscription (subscription usage is scoped to OpenAI's official apps; verified against OpenAI's terms and Codex documentation, 2026-07-11). An unfunded key fails with an instant `429 insufficient_quota` on every request — see the [technical FAQ entry on instant 429s](07_faq_technical.md#q-my-gpt-session-fails-instantly-with-429-errors-on-every-request-option-f). DAAF *does* ship a supported alternative that reuses your Codex (ChatGPT) OAuth login to route through your ChatGPT subscription — see the ["ChatGPT subscription lane"](#option-f-alternate-lane-chatgpt-subscription-codex-backend) below. It's a functional, carefully built route, but it works through a backend interface OpenAI doesn't officially offer for third-party tools, so it may change if OpenAI changes the backend, and you are responsible for compliance with OpenAI's terms. The API-key lane described here is the alternative if you'd rather stay on an officially offered interface.

**Setup — four steps from an API key to a working GPT session.**

**Step 1 — Add your settings to `environment_settings.txt`.** Open that file in your `daaf-docker` folder and add the block below, pasting your real OpenAI API key in place of the placeholder. The first settings activate the shim, bind the exact OpenAI route needed by its controller, and authenticate the API; the rest point Claude Code at it and choose your GPT models:

```bash
# --- Option F: OpenAI API directly, via the DAAF provider shim ---
DAAF_PROVIDER_SHIM=openai
# Exact route value required by gpt_fast.sh:
SHIM_BACKEND_MODE=openai
OPENAI_API_KEY=sk-your_openai_api_key_here

# Point Claude Code at the local shim (bare GPT slugs — no openai/ prefix here):
ANTHROPIC_BASE_URL=http://127.0.0.1:4141
ANTHROPIC_AUTH_TOKEN=daaf-shim-local
ANTHROPIC_API_KEY=
# Hide the native /fast control; use gpt_fast.sh below instead:
CLAUDE_CODE_DISABLE_FAST_MODE=1
# Strong tier (Opus-analog) and fast tier (Sonnet-analog); [1m] = 1M window hint:
ANTHROPIC_DEFAULT_OPUS_MODEL=gpt-5.6-sol[1m]
ANTHROPIC_DEFAULT_SONNET_MODEL=gpt-5.6-terra[1m]
# Context window -- see "Context window on GPT sessions" below:
CLAUDE_CODE_MAX_CONTEXT_TOKENS=1050000
```

**Step 2 — Rebuild the image.** Unlike Option C (which is config-only), this lane needs a one-time rebuild, because the shim's auto-launch is baked into the container entrypoint. From the DAAF Control Panel choose **option 10, "Rebuild Container,"** or run `bash rebuild_daaf.sh` (`.\rebuild_daaf.ps1` on Windows) directly — see the [rebuild instructions](#keeping-daaf-updated). On boot, the container starts the shim automatically and keeps it alive (restarting it if it ever exits), so you normally never have to touch it.

**Step 3 — Start Claude Code, then switch to your GPT model with `/model`.** Sessions always *open* on the Claude default; you switch once you're in. (Why: the start model is set by `ANTHROPIC_MODEL` in DAAF's project `.claude/settings.json`, shipped as `claude-opus-4-8[1m]` because most DAAF users run Claude, and that value intentionally overrides the container environment — so do **not** set `ANTHROPIC_MODEL` in `environment_settings.txt`.) Just run `/model` after launch and pick your GPT slug; a forgotten switch fails loudly on the very first message, so there is no silent wrong-model risk. To make GPT your standing default instead, edit the `"ANTHROPIC_MODEL"` line in `/daaf/.claude/settings.json` — see the [FAQ entry on session start model](07_faq_technical.md#q-my-gpt-session-starts-on-a-claude-model-instead-of-my-gpt-model).

**Step 4 — Confirm it's working (optional).** If a GPT session ever misbehaves, a small manager script and a health endpoint let you check the shim at a glance:

```bash
bash /daaf/scripts/provider_shim/start_shim.sh --status    # is it running?
bash /daaf/scripts/provider_shim/start_shim.sh --restart # replace it atomically
curl -s http://127.0.0.1:4141/health                      # health check
```

In short: `--status` tells you whether the shim is healthy, and `--restart` safely replaces it in one step (it stops the old shim, waits, launches a fresh one, and confirms it's ready). Reach for `--restart` whenever you change shim settings or a session misbehaves. **One important caution: if the active Claude Code session itself routes through this shim, never ask it to run `--stop` and then `--start` in separate turns**—the stop severs your own session's route before the later turn can run. Always use `--restart`, which does both under a single lock.

Behind these commands, the manager is heavily hardened against the classic failure modes of background services — leftover files from crashed runs, interrupted starts and stops, and processes that merely look like the shim — so a `--restart` reliably lands you in a clean, healthy state. If you're curious exactly what it protects against (and where those protections honestly stop), that's covered under **Lifecycle safety and its limits** in the troubleshooting reference at the end of this lane.

That's the whole setup. The paragraphs that follow are optional reading you can come back to when you need it — and deeper mechanics and diagnostics live in **Under the hood / troubleshooting reference** at the very end of this lane.

**Optional tuning.**

**Reasoning effort.** The shim always sets the OpenAI request's reasoning effort, resolved by a four-tier precedence chain — first present wins: (1) a per-request signal from Claude Code, (2) a `#<effort>` suffix you append to a model slug (e.g. `ANTHROPIC_DEFAULT_SONNET_MODEL=gpt-5.6-terra[1m]#medium`; it works alongside the `[1m]` window hint and is stripped before the request reaches OpenAI), (3) the `SHIM_REASONING_EFFORT` env var, and (4) the default `high` (parity with DAAF Claude sessions). Valid values are `none`, `low`, `medium`, `high`, `xhigh`, and `max` (`max` is gpt-5.6-only). Leave everything unset to get `high` everywhere; set the env var or a slug suffix only if you want a different level.

> **The `/model` effort selector does not work for GPT slugs.** Claude Code gates the in-UI reasoning-effort selector by model-ID pattern, and for an unrecognized (GPT) slug it pins `high` on every request — so toggling the selector has no effect on GPT sessions. DAAF's provider shim recognizes that pinned inbound `high` as unset and falls through to your slug/env steer, which reactivates tiers (2) and (3) above as the real controls. To run GPT at a non-default effort, use the `#<effort>` slug suffix or `SHIM_REASONING_EFFORT` — not the `/model` selector.

See the [technical FAQ entry on controlling GPT reasoning effort](07_faq_technical.md#q-how-do-i-control-gpt-reasoning-effort-option-f).

**Response verbosity.** Separately from reasoning effort, the shim sends OpenAI's `text.verbosity` control on every request, defaulting to `medium` to balance decision-focused responses with enough detail for DAAF evidence and caveats (`high` adds warmth and volume; `low` is terse). Set `SHIM_TEXT_VERBOSITY=high` or `low` in `environment_settings.txt` if you prefer a more expansive or more concise style, and see the [technical FAQ entry on GPT response verbosity](07_faq_technical.md#q-how-do-i-control-gpt-response-verbosity-option-f) for details.

##### GPT Fast Mode on the provider-shim routes

Mirroring OpenAI Codex's "Fast mode" and API "Priority mode", you can turn on an equivalent with the GPT shim in DAAF. This basically turns on a speed-up from the model side of things, resulting in faster generation at the cost of greater subscription usage rates or higher API fees. To activate this in your session:

**First, disable the native Claude Code `/fast` control.** The Claude Code mode itself doesn't work with the GPT models and can get confusing with settings, so we need to turn it off first. Set this exact line in your host `environment_settings.txt` file:

```bash
CLAUDE_CODE_DISABLE_FAST_MODE=1
```

Then rebuild the container (`bash daaf.sh` / `.\daaf.ps1` and select the Rebuild option), and start a **new Claude Code session** afterwards.

**Then run the appropriate fast command for the shim** to check the current state, turn the boost on, or turn it off:

```bash
bash /daaf/scripts/provider_shim/gpt_fast.sh status
bash /daaf/scripts/provider_shim/gpt_fast.sh on
bash /daaf/scripts/provider_shim/gpt_fast.sh off
```

From the Claude Code prompt window, you can prefix the same command with `!`, for example `!bash /daaf/scripts/provider_shim/gpt_fast.sh on` to run it directly in the chat. The boost is **off by default**, and turning it `on` requires the `CLAUDE_CODE_DISABLE_FAST_MODE=1` line above; `off` and `status` always work. Which product you get depends on your route:

| Your Option F route | What "on" gives you | Product name |
|----------------|---------------------|--------------|
| ChatGPT subscription (`SHIM_BACKEND_MODE=chatgpt`) | Faster responses, drawn from your ChatGPT subscription credits | **GPT Fast** |
| OpenAI API key (`SHIM_BACKEND_MODE=openai`) | Priority processing, billed through your OpenAI API account | **GPT Priority** |

**A word on cost.** **GPT Priority can cost more** than ordinary API processing and depends on your provider, model, project/account, and usage-tier eligibility — the controller warns you before it enables it. GPT Fast draws on your ChatGPT subscription's own credit and eligibility rules; current Codex documentation describes roughly **1.5×** speed and says GPT-5.6 and GPT-5.5 use **2.5× Standard ChatGPT credits**. Either way, requesting the boost doesn't guarantee you were served it on any given request.

**Optional reading — under the hood.** The setting is persistent and shim-wide, and it's bound to the active route: switching routes resets it off, and switching back doesn't restore the old state — run `on` again on the new route. Requesting the faster tier is not the same as being served it; only the provider's actual response settles what served a given request, and the controller's `status` shows the latest such result the running shim has seen (qualified by model and completion time), not a promise about your current turn. One early ChatGPT-subscription probe requested priority and was served the standard tier — a dated, single-shape result, kept scoped to that old request rather than read as a standing entitlement test. The full policy semantics, wire-contract details, and version history live in the shim code, its tests, and git history.

**Context window on GPT sessions.** Two small settings tell Claude Code how big your GPT model's context window really is — without them it assumes a small (~200K) window for slugs it doesn't recognize, far below the 1,050,000-token window of the gpt-5.6 family.

- **On the direct OpenAI-API shim route,** append `[1m]` to your bare GPT slugs (e.g. `ANTHROPIC_DEFAULT_OPUS_MODEL=gpt-5.6-sol[1m]`, as shown above) and set `CLAUDE_CODE_MAX_CONTEXT_TOKENS=1050000`. Claude Code reads `[1m]` as a 1M-window hint and strips it before sending.
- **On OpenRouter,** keep the provider-prefixed bare slug (e.g. `ANTHROPIC_MODEL=openai/gpt-5.6-sol`) and set `CLAUDE_CODE_MAX_CONTEXT_TOKENS=1050000`. Don't add `[1m]` to provider-prefixed slugs — it isn't established for that form.
- **On the [ChatGPT-subscription (Codex) lane below](#option-f-alternate-lane-chatgpt-subscription-codex-backend),** set `CLAUDE_CODE_MAX_CONTEXT_TOKENS=370000` instead — that backend caps input around 370,000 tokens (measured for `gpt-5.6-sol`, 2026-07-16), and no client hint can raise it.

*Why it matters:* the declaration keeps Claude Code and DAAF measuring utilization against the same real window. DAAF does **not** use `CLAUDE_CODE_AUTO_COMPACT_WINDOW` — automatic compaction stays off because it can disrupt orchestration. If a GPT session reports "Context limit reached" / "Prompt is too long" at low utilization, see the [technical FAQ entry on low-utilization context errors](07_faq_technical.md#q-my-gpt-session-says-context-limit-reached--prompt-is-too-long-at-low-utilization).

**Optional 64K Claude Code output budget.** Claude Code defaults `CLAUDE_CODE_MAX_OUTPUT_TOKENS` to `32000` and supports a maximum of `64000`. If unusually long specialist work is being cut off, you may opt in by adding the plain decimal `CLAUDE_CODE_MAX_OUTPUT_TOKENS=64000` (the form supported by the pinned Claude Code 2.1.202) to the **host** `daaf-docker/environment_settings.txt` before Claude Code/the container starts, then recreate the container through the normal host flow. This is not free context: thinking tokens count toward the output budget, and raising the reservation leaves less context for conversation history and tool results, which can cause DAAF's context-pressure stop/restart guidance to fire earlier. Your provider or selected model may enforce a lower limit regardless. Keep specialist final returns bounded even with 64K enabled; prefer the default `32000` unless you have a concrete truncation problem. See the [technical FAQ entry](07_faq_technical.md#q-how-do-i-opt-in-to-a-64k-claude-code-output-budget) for the tradeoff summary.

##### Under the hood / troubleshooting reference (Option F)

**Optional reading.** Here for when you want to look under the hood or diagnose a problem. These mechanics are shared by both shim lanes (this one and the ChatGPT lane below).

**Logs and diagnostics.** The shim keeps its own diagnostic log at `/daaf/scripts/provider_shim/logs/shim.log`. It records only technical metadata — timings, status codes, error types, retry counts, and request-correlation IDs — and **never** your prompts or text, tool inputs, image bytes or URLs, credentials, raw response streams, or full request/response bodies. If a GPT session misbehaves, run `--restart` and check that log; the [technical FAQ](07_faq_technical.md#q-my-gpt-session-fails-instantly-with-429-errors-on-every-request-option-f) walks through common status/type/code triage such as `insufficient_quota` (billing) versus a true rate limit. The shim is a persistent daemon: changing its Python source does not update the already-running process. After any source update, run `bash /daaf/scripts/provider_shim/start_shim.sh --restart`, then confirm that `curl -s http://127.0.0.1:4141/health` reports `"version": "1.3.18"` before testing the new behavior.

**Session continuity across rebuilds.** On a shim lane, the shim keeps a small reasoning-cache file (`~/.claude/provider_shim/reasoning_cache.json`) that carries GPT reasoning continuity from one turn to the next. It lives on your per-install `daaf-claude-config` volume, so it survives container restarts and image rebuilds — you don't have to do anything to preserve it. Only an explicit `docker compose down -v` or `docker volume rm` erases it.

**Images.** The shim accepts images in your messages and tool results and forwards them to OpenAI without inspecting or logging the bytes; the [image troubleshooting entry](07_faq_technical.md#q-what-image-inputs-does-the-provider-shim-support) lists exactly what's accepted. Image support was verified with a dated privacy-safe probe (a 2026-07-18 Base64-PNG request) — that's evidence the shape worked on that date, not an official OpenAI guarantee.

**Advanced tuning.** Tool-call sanitization is on by default (`SHIM_SANITIZE_TOOLS`); the shim quietly strips known GPT tool-call quirks that would otherwise waste an error round-trip. Turn it off (`SHIM_SANITIZE_TOOLS=0`, then restart) only when running DAAFBench, which must observe raw model behavior. The remaining tuning variables are documented in `environment_settings_example.txt`.

**Lifecycle safety and its limits.** For readers who want the precise picture of how `--start`/`--stop`/`--restart` avoid acting on the wrong thing: the lifecycle manager treats PID files and its private stream workspace as typed, identity-bound capabilities rather than trusting pathnames alone. Workspace cleanup atomically moves each captured `.owner` and `output.fifo` entry to an unpredictable private quarantine name, revalidates that quarantined inode, and deletes only on a match; a one-time same-UID substitute is restored when safely possible and cleanup reports non-success instead of falsely claiming completion. Because Linux provides no inode-conditional deletion primitive, the final removal necessarily addresses the quarantined entry by its name; the unguessable random name makes interference in that instant a matter of blind chance rather than an achievable target, so member cleanup is best-effort hardening against same-UID substitution, not an absolute identity-bound deletion guarantee. Before escalating a verified serving process from TERM to KILL on Linux, the manager requires the same PID, exact accepted argv role, and unchanged `/proc` process start-time token; a reused PID is not KILLed. These checks protect against stale evidence, accidental or concurrent substitution, non-continuous same-UID replacement, and interrupted lifecycle operations. They do **not** claim protection against a continuously racing malicious process running as the same UID with signal or `ptrace` access; defending against that stronger active-adversary model would require privilege separation and native primitives beyond this manager.

#### Option F, alternate lane: ChatGPT subscription (Codex backend)

**Who this is for:** researchers who already pay for a **ChatGPT Plus/Pro subscription** and would rather use it than buy pay-per-token OpenAI API credits.

**What you'll end up with:** the same DAAF provider shim as Option F above, but pointed at your ChatGPT subscription's Codex backend. You authenticate once with your ChatGPT login (an OAuth token from your `codex` login) instead of an API key, and from there everything works the same. Request translation, tools, and the content-block lifecycle are shared across both lanes; only the authentication and endpoint differ. (The lane's deeper wire-level behavior — how it handles streaming, tolerates the optional fields the undocumented Codex backend may omit, and formats reasoning summaries — is documented in the [technical FAQ](07_faq_technical.md#q-can-i-use-my-chatgpt-subscription-instead-of-an-openai-api-key-option-f).)

> **A supported route we've built carefully — and DAAF's newest, so help us test it.** This lane routes Claude Code through your ChatGPT subscription, and we've done the engineering to make it a smooth, productive experience — it's exercised by DAAF's own benchmark runs. One thing to know up front, said plainly: it works through a backend interface that OpenAI doesn't officially offer for third-party tools like DAAF (OpenAI scopes subscription usage to its own official apps), so OpenAI could change that backend and disrupt the lane at any time, and **you are responsible for compliance with OpenAI's terms of service.** Because it's the newest route, please treat it as the one most likely to have rough edges and tell us about anything you hit. If you'd prefer to stay on an interface OpenAI officially offers, the API-key lane above (exact `SHIM_BACKEND_MODE=openai`) is the alternative.

**Prerequisite — confirm the standard-image Codex CLI.** The pinned **Codex CLI ships in every DAAF image**. Its presence is optional infrastructure only: it does not change DAAF's default provider, authenticate you, or activate the shim. Confirm Codex installed successfully inside the container before going further:

```bash
codex --version    # expect 0.144.1
```

If that reports `codex: command not found`, your image predates the universal installation or was built from a stale Dockerfile. Update DAAF, then rebuild (`bash rebuild_daaf.sh` / `.\rebuild_daaf.ps1`) so the host build uses the current Dockerfile, and re-enter the container before continuing. Setting `DAAF_DEV=1` is not the fix for a current image.

**Setup.** With Codex confirmed, five steps take you from a fresh container to a working ChatGPT lane. The lane remains explicitly opt-in: device-code OAuth and the shim settings below are both required.

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
   CLAUDE_CODE_DISABLE_FAST_MODE=1   # hide native /fast; use gpt_fast.sh below
   ANTHROPIC_DEFAULT_OPUS_MODEL=gpt-5.6-sol[1m]
   ANTHROPIC_DEFAULT_SONNET_MODEL=gpt-5.6-terra[1m]
   CLAUDE_CODE_MAX_CONTEXT_TOKENS=370000   # Codex lane: backend-capped ~370k (measured), NOT 1,050,000 — see below
   ```
   In this mode `OPENAI_API_KEY` / `SHIM_BACKEND_API_KEY` are **ignored** — the OAuth token is the credential. Codex availability alone does not select this lane; both `DAAF_PROVIDER_SHIM=openai` and `SHIM_BACKEND_MODE=chatgpt` are explicit opt-ins. **Note the `CLAUDE_CODE_MAX_CONTEXT_TOKENS=370000`** above: unlike the API-key lane's full `1050000`, the ChatGPT/Codex backend caps input around 370,000 tokens (measured for `gpt-5.6-sol`, 2026-07-16), independent of the model's true 1M window on the API route — and no `[1m]` hint or client setting can raise it. Declaring `370000` keeps Claude Code and DAAF's utilization accounting aligned with that ceiling; a breach surfaces as a clean `invalid_request_error` (`context_length_exceeded`). Re-measure with `scripts/provider_shim/probe_context_ceiling.py` if OpenAI changes the backend.
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
| `codex: command not found` | The image predates the universal Codex installation or was built from a stale Dockerfile. Update DAAF and rebuild (`rebuild_daaf.sh` / `rebuild_daaf.ps1`) so the current Dockerfile is used; `DAAF_DEV=1` is not required. |
| Shim log tells you to re-login | The OAuth token refresh failed permanently — run `codex login --device-auth` again inside the container. |

**Running more than one container.** Each DAAF container does its **own** `codex login`, which creates an **independent refresh-token grant** — there is no credential collision between containers. They share only your ChatGPT **usage pool** (the 5-hour and weekly caps), so running two in parallel simply draws that pool down faster. This is the clean way to run parallel DAAF instances. (The subtler case is running several codex-based tools — the `codex` CLI, the [Codex plugin](#using-the-codex-plugin-for-claude-code), the shim — inside a *single* container off the *same* login. As of shim v1.3.0 the shim is a pure *reader* of `auth.json`: it never rewrites the store, delegating every token refresh to the `codex` CLI — the single writer per `CODEX_HOME` — so the old shim-versus-other-tool rotation race is structurally eliminated. What stays unverified is *codex-versus-codex*: two independent codex invocations against one `CODEX_HOME` (for instance the plugin and the shim's delegated refresh firing at nearly the same moment). The safe posture is therefore still to give each codex-based tool its own `codex login` under a separate `CODEX_HOME`. None of this is needed for a normal single-tool setup.)

See the [technical FAQ entry on the ChatGPT subscription lane](07_faq_technical.md#q-can-i-use-my-chatgpt-subscription-instead-of-an-openai-api-key-option-f).

#### Using the Codex Plugin for Claude Code

Separate from the provider-shim lanes above, OpenAI ships an official plugin — **`codex-plugin-cc`** — that lets a Claude Code session **delegate a task to Codex** for a second opinion: a code review, an adversarial review, a rescue attempt. It adds slash commands like `/codex:review` and `/codex:adversarial-review`. Think of it as a way to get an *independent* model's eyes on a piece of work, complementary to DAAF's own review agents — not a provider route for running DAAF itself.

**What's already in the image.** The plugin shells out to the local `codex` CLI, and DAAF bakes that in (a pinned static binary — the same one the ChatGPT lane uses). Node.js is present and version-sufficient too, guaranteed by the Dockerfile. `npm` isn't included, but nothing here needs it — Codex is already installed, so if a plugin step ever mentions a missing `npm`, that's the harmless reason and you can ignore it.

**Install and authenticate (inside a Claude Code session):**

```
/plugin marketplace add openai/codex-plugin-cc
/plugin install codex@openai-codex
/reload-plugins
/codex:setup
```

Then authenticate Codex with the same headless device-code flow the ChatGPT lane uses:

```bash
codex login --device-auth
```

As with the shim's ChatGPT lane, this requires **device-code login enabled in your ChatGPT security settings** (off by default — enable it first, or the login fails immediately).

**Which setups are safe.** There are two race-free ways to use the plugin:

1. **Two containers (the natural pairing with the ChatGPT lane).** Run the plugin in a container on the **Anthropic route** (Claude subscription/API), and keep the ChatGPT-subscription **shim lane** in a *separate* container. Because each container has its own config volume, each has its own Codex login — the plugin and the shim never touch the same token. This pairs naturally with the [shared-workspace setup above](#sharing-one-research-workspace-across-two-installs-advanced).
2. **One Anthropic-route container plus the plugin.** If the container is *not* running the ChatGPT shim lane, nothing else is consuming the Codex login, so the plugin is the sole consumer and there is no contention.

> **Do not add the Codex plugin to a container that is already using the ChatGPT-subscription shim lane.** In that lane the shim is *itself* a consumer of your Codex login: it reads the OAuth token from `auth.json` and (as of shim v1.3.0) triggers refreshes by invoking the `codex` CLI against its `CODEX_HOME` rather than rewriting the file itself. Adding a second consumer of the same login — the plugin, or for that matter running the `codex` CLI by hand — is exactly the unverified *codex-versus-codex* case described above: two codex invocations can still rotate the refresh token at nearly the same moment, and a lost rotation **permanently invalidates the login** (a `refresh_token_reused` lockout that forces a fresh `codex login`). If you genuinely must run both in one container, give each tool its own **separate `CODEX_HOME`** with its own **separate `codex login --device-auth`**, so they never share a token file. Either way, remember that all logins on one ChatGPT account draw from the **same usage pool** (the 5-hour and weekly caps), so adding a second Codex consumer spends that pool faster.

#### Known limitations of GPT sessions (both lanes)

GPT support is a **supported capability we've engineered carefully** — actively tested, including through DAAF's own benchmark runs, and still gathering wider community experience across different setups. A few specifics are worth knowing:

- **Context utilization is estimated, not exact.** OpenRouter's Anthropic-compatible endpoint does not implement token counting, so Claude Code falls back to estimation on GPT sessions (the shim does the same). The context bar and utilization warnings are close approximations, not precise counts.
- **Set `CLAUDE_CODE_MAX_CONTEXT_TOKENS` to match your route.** Claude Code assumes a small (~200k) window for models it doesn't recognize, which is wrong for the large GPT windows. Set it to `1050000` on the API-key and OpenRouter routes, or to `370000` on the ChatGPT-subscription (Codex) lane, whose backend caps input around 370k tokens regardless of the model's true 1M window. DAAF detects your model and applies the matching quality thresholds automatically. Re-measure the Codex ceiling with `scripts/provider_shim/probe_context_ceiling.py` if OpenAI changes it.
- **OpenRouter's Anthropic endpoint is officially scoped to Anthropic models.** GPT works through it (proven live), but OpenRouter documents this endpoint for Claude models — it is effectively unsupported territory the vendor could change at any time.
- **Anthropic does not officially support routing Claude Code to non-Claude models** through any gateway. DAAF offers and tests these lanes as a supported capability, not something either vendor guarantees.

### Set up data source API keys

Most DAAF data sources — including all built-in education data from the Urban Institute — are **freely accessible with no authentication required**. You can skip this step entirely if you're only working with education data.

However, some data domains require API keys from their hosting platforms. The table below shows API keys for data sources that ship with DAAF. When you onboard a new data source from an API via Data Onboarding Mode, DAAF will guide you through setting up the appropriate environment variable using the same pattern shown here. You can set multiple API keys simultaneously — each uses a unique environment variable name.

| Data Source | Environment Variable | Where to Get a Key |
|-------------|---------------------|-------------------|
| County Presidential Election Returns (Harvard Dataverse) | `HARVARD_DATAVERSE_API_KEY` | [dataverse.harvard.edu](https://dataverse.harvard.edu/) → Log in → Account name (top-right) → API Token → Create Token |

#### Recommended: Use an environment_settings.txt file (persistent across restarts)

Your `daaf-docker` folder includes an `environment_settings_example.txt` template (data source keys live in its **section [5]**). If you don't already have an `environment_settings.txt` — recent installs seed one for you — copy the template, then fill in your keys:

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
- **"Port 2718 already in use" when trying to view Marimo notebooks** — Another process is using that port. Either stop it, or move DAAF's notebook port by setting `DAAF_PORT_MARIMO` (e.g. `DAAF_PORT_MARIMO=3718`) in your `daaf-docker` folder's `environment_settings.txt`, then recreate the container (`docker compose down`, then `bash run_daaf.sh` / `.\run_daaf.ps1`). Prefer this over hand-editing `docker-compose.yml` — updates and rebuilds regenerate that file and would discard a manual port change.
- **"Port 2719 already in use" when trying to view session logs** — Same fix: stop the conflicting process, or set `DAAF_PORT_LOGVIEWER` (e.g. `DAAF_PORT_LOGVIEWER=3719`) in `environment_settings.txt` and recreate the container. Port 2719 is used by the DAAF Log Explorer (`generate_log_viewer.sh`).
- **"Port 2720 already in use" when trying to open the browser-based code editor** — Same fix: stop the conflicting process, or set `DAAF_PORT_VSCODE` (e.g. `DAAF_PORT_VSCODE=3720`) in `environment_settings.txt` and recreate the container. Port 2720 is used by the browser-based code editor (`run_vscode.sh` / `run_vscode.ps1`).
- **Permission denied errors inside the container (especially on macOS)** — If you see errors like `Permission denied` when Claude tries to read or write files, the Docker volume likely has files owned by root or your host UID instead of the container's `appuser` (UID 1000). This is a known issue with Docker Desktop on macOS. The `docker-compose.yml` includes an init service (`daaf-init`) that automatically fixes file ownership on every startup. To resolve this: stop the container (`docker compose down`), then restart it (`docker compose up -d`) — the init service will repair permissions before the main container starts. If you still have issues, you can fix permissions manually:
  ```bash
  docker run --rm -v "daaf_daaf-data:/daaf" busybox chown -R 1000:1000 /daaf
  ```
- **Claude Code asks me to log in again** — This should be rare. Claude Code's authentication state lives in a dedicated Docker volume (`daaf-claude-config`, mounted at `/home/appuser/.claude`, with `CLAUDE_CONFIG_DIR` pointing there so credentials and `~/.claude.json` land in it too). That volume persists across container restarts, `docker compose down`, and image rebuilds — so a normal restart or update should not lose your login. If you *are* prompted to log in again after a routine restart, just complete `/login` once; it will persist from then on. Two things to know: (1) running `docker compose down -v` (note the `-v`) or manually deleting the volume erases this state — avoid `-v` unless you intend to wipe everything; (2) if you prefer key-based auth that never needs an interactive login, configure your credentials in the `environment_settings.txt` file (see [**Configure authentication via environment_settings.txt**](#configure-authentication-via-environment_settingstxt) above), which sets authentication from the environment on every start.
- **OpenRouter: "model not found" or authentication errors** — Double-check three things: (1) `ANTHROPIC_BASE_URL` must be exactly `https://openrouter.ai/api` with no `/v1` suffix (the `/v1` variant is for OpenAI-compatible tools, not Claude Code), (2) your OpenRouter key must be in `ANTHROPIC_AUTH_TOKEN`, with `ANTHROPIC_API_KEY` set to an empty value (`ANTHROPIC_API_KEY=`), not removed entirely — if it's unset, Claude Code falls back to Anthropic's servers, and (3) if you previously logged in with Anthropic interactively, run `/logout` inside Claude Code to clear cached credentials. You can verify your connection is working by typing `/status` inside Claude Code and checking the [OpenRouter Activity Dashboard](https://openrouter.ai/activity) for incoming requests.

---

## Recommended Next Steps

- [**02. Understanding and Working with DAAF**](02_understanding_daaf.md) — Learn to work with DAAF for the first time: what to expect, how to use it, and how to test its strengths and limitations
- [**06. FAQ: Philosophy**](06_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**07. FAQ: Technical Support**](07_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, authentication errors, and other common errors

---

[**Back to main**](https://github.com/DAAF-Contribution-Community/daaf/tree/main)
