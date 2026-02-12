# 01. Installation & Quick Start

This is the complete first-time installation and setup guide for DAAF. This document covers every step from installing prerequisites to running your first session.

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
- **Windows:** Open "PowerShell" or "Command Prompt" from the Start menu (PowerShell is recommended)
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
- Claude Code was immensely buggy for me on Windows using Powershell. I have found the free version of [Warp](https://www.warp.dev/) to be a much cleaner, more reliable experience (but feel free to turn off all their extra AI features and account shenanigans).

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

Okay, with all the prerequisites out of the way, installation itself is only six easy steps and will only take a few minutes with a decent internet connection.

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

### Step 3: Use Docker to create and start the container

```bash
docker compose up -d --build
```

This builds a Docker container with all the tools pre-installed using the Dockerfile provided with the project folder you just downloaded (Python, data science packages, Claude Code). The first time, this downloads base images and installs all packages — expect it to take a few minutes as it pulls in all the needed software. Subsequent starts are really fast since Docker caches everything. The `-d` flag in the command runs it in the background so you get your terminal back.

### Step 4: Open a terminal session inside the Docker container

Once the Docker container setup is complete, your terminal will resume in the project folder. Run the following command to "enter" the Docker container we just created (which will use some configuration settings from the docker-compose.yaml file in our project folder, too).

```bash
docker compose exec daaf-docker bash
```

This opens a terminal session *inside* the container, separated from the rest of your computer and running with all the software just installed. You'll notice your terminal prompt changes — that's how you know you're "inside." Think of this like activating a mini virtual computer, within your computer.

### Step 5: Launch Claude Code

Now that we're in, it has everything it needs to start working. Enter the following command to launch Claude Code, configured with everything DAAF has to offer and ready to run.

```bash
claude
```
On first launch, Claude Code will prompt you to authenticate (API key or subscription login). Follow its instructions to complete the process as needed based on your method. For Windows users, remember that CTRL+C actually exits the terminal, so use CTRL+SHIFT+C and CTRL+SHIFT+V if you want to copy/paste.

### Step 6: Select Your Model

You can check which Claude model is being used at any time (Opus, Sonnet, Haiku). To set this, run the following command at any time:

```bash
/model
```

**Recommended model:** All development and testing of this project was done using **Opus 4.5** and **Opus 4.6**. I unfortunately think that these models are absolutely required; other models (Sonnet, Haiku) are not nearly as capable and produce erratic, inconsistent results. The complexity of tasks embedded in the DAAF workflow (multi-agent orchestration) relies on the model's ability to follow complex, multi-step protocols reliably. This is also the reason why the Claude Max subscription is a likely prerequisite here: Opus models are very resource-intensive, and it's hard to complete the DAAF workflows under the "Pro" or "Free" tiers accordingly.

---

## First Launch: Confirming Everything Works

Once you've gotten Claude Code running in your terminal and your model is set, you're ready to start asking the DAAF-empowered Claude any question you'd like. You may find it helpful to reference what's available in the (Urban Institute Education Data Portal)[https://educationdata.urban.org/documentation/] (the current datasets available for demonstration). Or, you can just ask it: "Hey Claude, I'm interested in understanding what kind of data we have available on \[Colleges/High Schools/School Districts\]. Can you give me a brief summary of the sorts of data you can analyze on this subject?"

### Easing in with progressively more advanced queries

You can use DAAF in a couple of different ways, which we'll get into in the next few tutorial files. But I'd recommend starting small:
1. Ask Claude to explain to you a single dataset or variable -- see what it says, feeling free to ask follow-ups or dig into certain details.
2. Ask Claude to help you analyze a single varible for a simple subset from a single dataset. This will probably kick off a full analysis, but a very simple and approachable one.
3. Ask Claude to help you understand the relationship between two variables of interest for \[Colleges/High Schools/School Districts\]. See if you can learn more about that relationship over time, as well.
4. Get more abstract, complex, or high-level. For example, ask Claude to help you better understand the nuances of the relationships between college selectivity, student academic preparedness, graduation rates, and student socioeconomic backgrounds. Or ask it how you might better understand what linkages may exist between school-level resources, student socioeconomic status, and access to advanced coursework. You can even ask it what you should ask it, based on the data it has available: "I'm trying to get started with the DAAF system. I'm trying to think of a few moderately complex, abstract research questions I could ask you to conduct data analysis on, based on the data current available to you. Do you have a few examples you can surface related to [Topic A/B/C]?"
5. I am actively trying to assess DAAF's performance by replicating studies conducted by the [Urban Institute Learning Curve series](https://www.urban.org/projects/learning-curve) which leverage the same Education Data Portal datasets DAAF currently has access to -- especially as they have [open-source code available](https://github.com/UrbanInstitute/The-Learning-Curve/tree/main) for direct comparison afterwards. Run some tests of your own, and please do let me know what you find!

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

When you're ready to end a session, you have two options. The first option: Close the terminal window, and then use your Docker Desktop window to "pause" your Docker container (look for "daaf-docker-1" in your Containers panel). The other option is to do this fully through the terminal: 

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

Your local `daaf/` folder is connected to the container. This means:

- **Files sync both ways** — when the assistant creates a report or dataset inside the container, it appears in the folder on your computer too. You can open these files normally. You can also bring in files into this folder that you'd like Claude to see, review, or inspect (e.g., other public datasets you're comfortable with it profiling using the data-ingest agent)
- **Your work persists** — stopping the container doesn't delete your research outputs. They continue live in your project folder.
- **Only this folder is accessible to Claude** — the container cannot see any other files on your computer. Your documents, photos, and everything else are completely isolated.

Projects produced by DAAF will be stored in a folder called "research" within the DAAF installation folder you selected. For file management purposes, I strongly recommend making backup copies of these project folders intermittently. As mentioned above, if you use DAAF for anything more than exploration, I strongly recommend learning how to use Git to backup your files and track filechanges robustly.

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
**"command not found: docker"** — Docker Desktop may not be installed, or your terminal needs to be restarted after installation. Close and reopen your terminal, and make sure Docker Desktop is installed and running.

---

## Recommended Next Steps

- [**02. Understanding DAAF**](02_understanding_daaf.md) — Learn to work with DAAF for the first time: what to expect, engagement modes explained, your first analysis walkthrough
- [**06. FAQ: Technical**](06_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, design rationale, authentication errors, and other common errors
- [**07. FAQ: Philosophy**](07_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**Back to main**](../.)
