# 01. Installation & Quick Start

This is the complete first-time installation and setup guide for DAAF. This document covers every step from installing prerequisites to running your first session, as well as tips for file management, viewing compiled research script notebooks, and troubleshooting.

---

## Documentation Table of Contents

- [**00. README**](../.) — **\[Prerequisite\]** Vision and purpose, what DAAF does and does not do, core design philosophy, acknowledgments
- **01. Installation & Quick Start** — **\[This document\]** Get started! Installation prerequisites, step-by-step 5-minute setup, day-to-day usage, and troubleshooting
- [**02. Understanding DAAF**](02_understanding_daaf.md) — Learn to work with DAAF for the first time: what to expect, engagement modes explained, your first analysis walkthrough
- [**03. Best Practices**](03_best_practices.md) — Tips for working with Claude Code, writing effective prompts, ensuring quality and rigor with DAAF, reviewing outputs, and managing context
- [**04. Extending DAAF**](04_extending_daaf.md) — How to add new data source skills, analytical tools and methodologies, and creating your own additional specialized agents
- [**05. Contributing**](05_contributing.md) — Get involved in developing DAAF! How to file issues via GitHub, support expanding the capabilities of the framework, contribute to educational tutorials and how-to's, and more!
- [**06. FAQ: Technical**](06_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, design rationale, authentication errors, and other common errors
- [**07. FAQ: Philosophy**](07_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**Back to main**](../.)

---

## Prerequisites

Before installing DAAF, there are four (technically five) key prerequisites. Please read the Claude requirement especially closely; the price of the necessary subscription is definitively the highest barrier to entry at this time. I hope this will change in the near future with greater testing and community support for open-source models!

### 0. A computer with internet access

You'll need internet access to download the project files and interact with DAAF/Claude (which itself always requires internet). Datasets will also be downloaded from the Urban Institute Education Data Portal, which will also require an internet connection. Note that all analyses will be conducted using your computer hardware, so you should have a computer that's generally capable of running intermediate-level data analysis (same sort of requirements you'd face if you wanted to analyze these same datasets in R/Stata/Python regularly).

### 1. Terminal

It's probably going to feel a bit weird, but you'll interact with DAAF/Claude Code through your **Terminal** (also called the command line or shell) -- a text-based interface on your computer where you type commands and instructions to your computer. You can think of this as the code-base way to do all the things you would normally do on your computer by clicking around a standard user interface (navigating folders, copying files, deleting things, etc.). Getting started is strange, but then when it's running, it's basically like any other AI assistant chatbot window with worse font. Your computer definitely already has this, but if you're not used to working in the terminal, here are some basics:

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
| Cancel a running command | `Cmd/Ctrl + C` | Stops whatever is currently running |
| Scroll up to see past output | Scroll or `Shift + Page Up` | See output that scrolled off screen |

**Tips:**
- You can paste commands into the terminal (`Cmd + V` on Mac, `Ctrl + V` or right-click on Windows)
- Press the up arrow key to recall previous commands
- Tab completion works — start typing a file/folder name and press `Tab` to auto-complete it
- Claude Code had a lot of graphical glitches for me on Windows when using Powershell. I have found the free version of [Warp](https://www.warp.dev/) to be a much cleaner, more reliable experience (you can skip creating an account and skip using any of their AI features, it's totally free), but Powershell will still work if you don't want to install any other software.

### 2. Git

Git is software that primarily helps people track file changes and updates. It helps people identify exact line changes, and collect a full history of all changes in sequence (you can see that history for DAAF [here](https://github.com/brhkim/daaf/commits/main/)!) In this case, we're using Git to help you download ("clone") this project's core files to your computer. You'll use it just once during setup. If you continue to use Claude Code at all, and plan to use this project, I HIGHLY recommend you learn more about how to use Git for project and file management. It is absolutely necessary to better track and understand and review how Claude is changing things in your workspace later on. If you run into any Git-related errors during install, you may need to restart your computer to let the install fully sink in.

**Install:**
- **macOS**: You will first need to use the Terminal mentioned above to install [Homebrew](https://brew.sh/). Follow the directions on that site, and then install Git by following directions here: [git-scm.com/downloads](https://git-scm.com/downloads).
- **Windows**: You can install Git via the installer available for download at [git-scm.com/downloads](https://git-scm.com/downloads)
- **Linux**: You probably already know what to do, but otherwise, follow directions at [git-scm.com/downloads](https://git-scm.com/downloads)

### 3. Docker Desktop

Docker is a program designed to help people create self-contained, isolated environments (called a "container") on your computer that are strictly separated from everything else, and extremely easy to replicate and share. This protects your computer and prevents Claude Code from messing with anything it shouldn't be, and it ensures that even if somehow things go catastrophic, you can easily spin up a new virtual environment back up in minutes with zero consequences. In this project, I also use Docker to install every needed piece of software in a predictable and stress-free way to have Python, data science libraries, and Claude Code all ready to go in one step. Think of it like a lightweight virtual computer running inside your computer that gets created via a very specific recipe, every single time. Docker Desktop includes everything you need (including Docker Compose, which coordinates the setup). After installing, make sure Docker Desktop is actually running before proceeding. If you're worried, you can see exactly what is installed by reading the Dockerfile in this repository -- feel free to ask your favorite LLM to help you interpret and inspect it, if you'd like. If you run into any Docker-related errors during install, you may need to restart your computer to let the install fully sink in.

**Install:** [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)

### 4. Anthropic Account & Authentication

Claude Code is the AI assistant that powers this project. It runs inside your terminal (not in a web browser) and needs to link in with an Anthropic account for billing/usage purposes. For the account setup, you have two options:

- **Anthropic Max subscription** — If you have a Claude Max plan, Claude Code will walk you through linking your account interactively. This is probably going to be the biggest barrier-to-entry for testing this work, but, unfortunately, these AI research pipelines are intensive enough that you simply cannot get enough usage with a free or Pro plan.
- **Anthropic API key** — [Get one here](https://console.anthropic.com/). This is a pay-per-use key that you'll paste into Claude Code when prompted. This allows unlimited use as long as you're willing to pay. Just note, this can get VERY expensive, very quickly. I HIGHLY recommend getting a Max subscription for this project, instead, as they are explicitly subsidizing these sorts of costs via their subscription model.

Claude Code will prompt you to choose your authentication method the first time you run it — you don't need to configure anything in advance. Note that many terminal interfaces "hide" any password-entry you're asked to do, so if you don't see your typing "working," it's working but hiding it from view for your privacy. If you're concerned about privacy otherwise: Nothing (including your credentials) ever leave your computer in the course of this project's workflows, and I've enforced a LOT of safety checks to ensure Claude doesn't accidentally share it with anyone, either. This can be directly verified in the code. Note that you can easily port this whole project over to a CLI tool of your choice (OpenCode, Codex, Gemini CLI, etc.) with a little bit of effort (the hooks are really the only hard part -- everything like the agents and skills should port over immediately). Fork this repo, work with your favorite tool to convert it over, and please continue to share it broadly with others!!!

---

## Installing DAAF

Okay, with all the prerequisites out of the way, installation itself is only seven easy steps and will only take a few minutes with a decent internet connection.

### Step 1: Choose a project download location on your computer and open it in your terminal

Using your terminal, first navigate to the folder where you want this project to live:

```bash
# Navigate to the folder where you want this project to live. Change the below to the folder you want!
cd "C:\Users\Documents"

```

### Step 2: Use Git to download the project files and enter the Project Directory

```bash
# Download the project files to your computer
git clone https://github.com/brhkim/daaf.git

# Enter the project directory
cd daaf
```

This creates a `daaf` folder containing all the project files. You should now be inside the project directory. You'll see files like `CLAUDE.md`, `docker-compose.yml`, `Dockerfile`, and folders like `agents/`, `research/`, etc.

> **Important:** The `git clone` command creates a folder named `daaf` by default. **Do not rename this folder** before you finish this full process.

### Step 3: Copy the project files into Docker

Rather than let Claude use and edit files directly on your computer, we're going to make a secure copy for Claude to operate on separately using Docker. Run this command next, making sure that Docker Desktop is currently running in the background:

```bash
docker run --rm -v "${PWD}:/source:ro" -v "daaf_daaf-data:/dest" busybox cp -a /source/. /dest/
```

This copies all the project files into a **Docker volume** — a storage area managed by Docker that will serve as the container's working directory. Think of it like creating a dedicated workspace inside Docker where all your research, data, and outputs will live. The `daaf/` folder on your computer is used as the starting point here, but going forward, the Docker volume is where the actual work happens (see "How to Manage DAAF Project Files and Output" below for more on this).

### Step 4: Use Docker to create and start the container

```bash
docker compose up -d --build
```

This builds an isolated/protected Docker container with all the necessary tools pre-installed (Python, data science packages, Claude Code) using the Dockerfile provided and the copied project files from the volume we just made. The first time, this downloads base images and installs all packages — expect it to take a few minutes as it pulls in all the needed software. Subsequent starts are really fast since Docker caches everything.

### Step 5: Open a terminal session inside the Docker container

Once the Docker container setup is complete, your terminal will resume in the project folder. Run the following command to "enter" the Docker container we just created.

```bash
docker compose exec daaf-docker bash
```

This opens a terminal session *inside* the container, separated from the rest of your computer and running with all the software just installed. You'll notice your terminal prompt changes — that's how you know you're "inside." Think of this like activating a mini virtual computer, within your computer.

### Step 6: Launch Claude Code

Now that we're in, it has everything it needs to start working. Enter the following command to launch Claude Code, configured with everything DAAF has to offer and ready to run.

```bash
claude
```
On first launch, Claude Code will prompt you to authenticate (API key or subscription login). Follow its instructions to complete the process as needed based on your method. For Windows users, remember that CTRL+C actually exits the terminal, so use CTRL+SHIFT+C and CTRL+SHIFT+V if you want to copy/paste.

### Step 7: Adjust some quick configuration settings

Once you're in, there are a few settings to adjust to ensure that the workflow is able to operate as expected. First, type the following into Claude's chat window:

```bash
/config
```

And then change the "auto-compact" setting to False by navigating down with your arrow keys and hitting Enter when it's selected. It should then show "False", after which you can hit the ESC key to return to the regular Claude chat.

**Recommended model:** You can check and change which Claude model is being used at any time (Opus, Sonnet, Haiku) by typing `/model`. You should also see the exact model being used below the chatline. All development and testing of this project was done using **Opus 4.5** and **Opus 4.6**. I unfortunately think that these models are absolutely required; other models (Sonnet, Haiku) are not nearly as capable and produce erratic, inconsistent results. The complexity of tasks embedded in the DAAF workflow (multi-agent orchestration) relies on the model's ability to follow complex, multi-step protocols reliably. This is also the reason why the Claude Max subscription is a likely prerequisite here: Opus models are very resource-intensive, and it's hard to complete the DAAF workflows under the "Pro" or "Free" tiers accordingly.

Opus 4.6 (unlike Opus 4.5) also allows you to select its "thinking level" by tapping left-and-right arrow keys while Opus 4.6 is selected on the /model selector in Claude Code. All tests I've conducted to date are using the "High" setting -- as this is a case where quality is far more important than quantity, I strongly recommend doing the same. This will have usage and API limit ramificiations, though, so it is a reasonable thing to test out the tradeoffs for yourself! Please do report back with any findings so we can incorporate that into our guidance here.

---

## First Launch: Confirming Everything Works

Once you've gotten Claude Code running in your terminal and your model is set, you're ready to start interacting with the DAAF-empowered Claude Code. Before you do anything else, let's confirm that Claude is actually seeing and using all the DAAF resources first:

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

I promise that's genuinely the first response I got back while testing this! Talking conversationally with Claude in this way is one easy way you could get oriented to using DAAF. Ask it questions, dig into features, talk about pros and cons, and so on. It will intelligently reference both the user documentation and the workflow documentation as relevant (but it never hurts to remind it, "...based on the project documentation"). 

From here, you can interact with Claude the same way you would with any AI assistant, but it'll "kick in" its DAAF-powered workflows and skillsets whenever relevant to supercharge anything related to data analysis work, data documentation spelunking, data exploration, and so on. If you want a gentle onboarding guide for actually using DAAF (fully written by a human for other humans!), we'll cover that in the next section: [**02. Understanding DAAF**](02_understanding_daaf.md). I used to be a high school English teacher, so this is the fun part for me, honestly. 

That being said, let's go over just a few more technical details and how-to's before we get there.

---

## Day-to-Day Start/Stop Workflow

Now that you've got DAAF running, let's talk through simple commands you'll use to get in and out of this workflow, as well as how to manage files.

### Starting a Session

Once you've completed the above Docker installation steps, your daily workflow is just:

```bash
# Get into the project directory, inputting the right file path for your own system
cd "C:\Users\Documents\daaf"
# Make sure Docker Desktop is running on your computer, then start the Docker container:
docker compose up -d
# Enter into the Docker container again
docker compose exec daaf-docker bash
# Run Claude
claude
```

### Ending a Session

When you're ready to end a session, you have two options. The first option: Close the terminal window, and then use your Docker Desktop window to "pause" your Docker container (look for "daaf" and click the expand arrow next to it, then "daaf-daaf-docker-1" in your Containers panel). The other option is to do this fully through the terminal: 

```bash
# Exit Claude Code first. You can also just press CTRL+C
/exit
# That gets you back into the terminal window, running *within* your Docker container. Let's exit the Docker container
exit
# Now let's turn off the Docker container
docker compose down

# You can then just close your terminal.
```

## How to Manage DAAF Project Files and Output

Your research files, data, and outputs live inside the **Docker volume** we created during installation — a storage area managed by Docker, **copied from** the `daaf/` folder on your computer. Think of the `daaf/` folder on your computer as the "recipe" that was used to set everything up, while the Docker volume is the actual "kitchen" where all the work happens.

This means:
- **Your work persists** — stopping or restarting the container does NOT delete anything. The Docker volume retains all your research outputs, data, and notebooks across restarts, rebuilds, and even `docker compose down`.
- **Files don't automatically appear on your computer** — unlike a traditional shared folder, files created inside the container are stored in the Docker volume, not directly on your desktop. To access them directly, you'll use Docker Desktop or simple copy commands (see below).
- **Only the volume is accessible to Claude** — Claude can only see what's in the volume. Your documents, photos, and everything else are completely isolated.

### Viewing Files in Docker Desktop

The easiest way to browse your files is through Docker Desktop's graphical interface:

1. Open **Docker Desktop**
2. Click **Containers** in the left sidebar
3. Click the "expand" arrow on the container named **`daaf`** and then click on the name **`daaf-daaf-docker-1`**
4. Select the **Files** tab to see the file tree
5. Navigate into `daaf` and then `research` to find your project folders

From here, you can download copies of individual folders or files to your computer by right-clicking on them. You can also Import files into the Volume from your computer by right-clicking, as well.

### Backing Up Your Work

Since your research files live inside the Docker volume, it'll be extremely important to regularly back up your work separately from the Volume. You can do that most easily using the Docker Desktop method above (go into the volume file viewer and download the whole daaf or research folder to somewhere else on your computer).

### Viewing report Markdown (.md) files

LLM assistants work best on text files, which means that proprietary document formats like Microsoft Word or Google Docs aren't great for this type of work. DAAF produces all its output report documents in Markdown (.md) format. You can open these in any basic text editor, but basic text editors tend not to display the formatting very nicely. I recommend installing a basic Markdown viewer, or you can copy the Markdown text into any free online viewer (e.g., [StackEdit](https://stackedit.io/app)) 

---

## Keeping DAAF Updated

DAAF is actively being developed and updated. If you'd like to pull in the latest fixes, extensions, and updates (which for a while may be as often as daily!!), updating is straightforward. Since the project files live inside the Docker volume, the update happens inside the container -- the files that are visible on your original computer's folder are just old copies, now. Before updating, I recommend backing up your volume's research folder as a precaution (see "Backing Up Your Work" above).

```bash
# Get into the project directory, inputting the right file path for your own system
cd "C:\Users\Documents\daaf"
# Make sure Docker Desktop is running on your computer, then start the Docker container:
docker compose up -d
# Enter into the Docker container
docker compose exec daaf-docker bash
# Pull down the latest updates (this runs inside the container, updating the Docker volume)
git pull origin main
```

Note that `git pull` inside the container won't work correctly if you've made any edits to the core DAAF workflow or documentation files (basically, anything outside of the research folder). In that case, you may want to submit a Pull request for your changes (if you've made useful updates you want to share broadly!) -- otherwise, you'll need to navigate your own merge conflicts and such (a topic for general Git tutorials, rather than here!).

---

## Viewing Marimo Notebooks in Your Browser

The assistant uses a python library called "marimo" to create streamlined python code "notebooks" as part of its analysis. It can also use this library to create nice, interactive dashboards for you of analyses it has completed. To view one in your browser:

```bash
# Get into the project directory, inputting the right file path for your own system
cd "C:\Users\Documents\daaf"
# Make sure Docker Desktop is running on your computer, then start the Docker container:
docker compose up -d
# Enter into the Docker container again
docker compose exec daaf-docker bash
# Inside the container, you can run the following command to view a notebook 
# Note that the first bit should be the (replace the path with your actual notebook)
marimo run 'research/YYYY-MM-DD Title/YYYY-MM-DD Notebook Name.py' --host 0.0.0.0 --port 2718 --headless
```

Then open [http://localhost:2718](http://localhost:2718) in your computer's browser (no need to mess with anything in the terminal here). The notebook renders there as an interactive document.

To edit a notebook interactively, use `marimo edit` instead of `marimo run`:

```bash
marimo edit 'research/YYYY-MM-DD Title/YYYY-MM-DD Notebook Name.py' --host 0.0.0.0 --port 2718 --headless
```

---

## What the Container Includes

<!-- MIGRATE: README section "What the Container Includes" — moves here in full; README will not retain -->

You don't need to install any of these — Docker handles it all — but for your reference:

| Component | What it does |
|-----------|-------------|
| Python 3.12 | Runs the analysis code |
| polars, pandas, numpy | Data manipulation and analysis |
| plotnine, plotly, matplotlib | Charts and visualizations |
| marimo | Interactive notebooks for reviewing analyses |
| Claude Code | The AI assistant you interact with |

---

## Setup Troubleshooting

**"Cannot connect to the Docker daemon"** — Make sure Docker Desktop is running (look for the whale icon in your system tray / menu bar).
**"Port 2718 already in use"** — Another process is using that port. Either stop it, or change the port mapping in `docker-compose.yml` (e.g., `"3000:2718"` to use port 3000 on your host).
**Claude Code asks for an API key every time** — Claude Code stores its configuration inside the container. If you fully remove the container (`docker compose down`), you may need to re-authenticate next time. To avoid this, you can set `ANTHROPIC_API_KEY` as an environment variable in a `.env` file in the project root (the `.gitignore` already prevents `.env` from being shared publicly).
**Container seems slow to build the first time** — The first `docker compose up --build` downloads base images and installs all packages. This is a one-time cost — subsequent starts are fast since Docker caches everything.
**"command not found: docker"** — Docker Desktop may not be installed, may not be running, or your terminal needs to be restarted after the initial installation. Close and reopen your terminal, and then make sure Docker Desktop is installed and running.
**"I can't find my research files on my computer"** — With Docker volumes, your research files live inside Docker's managed storage, not in the `daaf/` folder on your computer. See **How to Manage DAAF Project Files and Output** above for more information.

---

## Recommended Next Steps

- [**02. Understanding DAAF**](02_understanding_daaf.md) — Learn to work with DAAF for the first time: what to expect, engagement modes explained, your first analysis walkthrough
- [**06. FAQ: Technical**](06_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, design rationale, authentication errors, and other common errors
- [**07. FAQ: Philosophy**](07_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**Back to main**](../.)
