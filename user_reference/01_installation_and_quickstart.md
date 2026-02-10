# 01. Installation & Quick Start

This is the complete installation and setup guide for DAAF. All installation instructions, prerequisites, and setup troubleshooting live here — the README focuses on what DAAF is and why it exists, then points here for setup. This document covers every step from installing prerequisites to running your first session.

---

## Documentation Table of Contents

- [**00. README**](../README.md) — **\[Prerequisite\]** Vision and purpose, what DAAF does and does not do, core design philosophy, acknowledgments
- **01. Installation & Quick Start** — **\[This document\]** Get started! Installation prerequisites, step-by-step 5-minute setup, day-to-day usage, and troubleshooting
- [**02. Understanding DAAF**](02_understanding_daaf.md) — Learn to work with DAAF for the first time: what to expect, engagement modes explained, your first analysis walkthrough
- [**03. Best Practices**](03_best_practices.md) — Tips for working with Claude Code, writing effective prompts, ensuring quality and rigor with DAAF, reviewing outputs, and managing context
- [**04. Extending DAAF**](04_extending_daaf.md) — How to add new data source skills, analytical tools and methodologies, and creating your own additional specialized agents
- [**05. Contributing**](05_contributing.md) — Get involved in developing DAAF! How to file issues via GitHub, support expanding the capabilities of the framework, contribute to educational tutorials and how-to's, and more!
- [**06. FAQ: Technical**](06_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, design rationale, authentication errors, and other common errors
- [**07. FAQ: Philosophy**](07_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**Back to main**](../.)

---

## Prerequisites Deep Dive

Before installing DAAF, you need four things on your computer. This section explains each one and why it's needed.

<!-- MIGRATE: README section "Prerequisites" — subsections 1-4 (Git, Docker Desktop, Anthropic account, Terminal) -->
<!-- This is now the SOLE home for prerequisite details; README will link here instead -->

### Git

<!-- MIGRATE: README "Prerequisites" subsection "1. Git" — moves here in full; README will not retain -->

Git is a version control tool that primarily helps people track software file changes and updates. In this case, it lets you download ("clone") this project to your computer (all the files you see above). You'll use it just once during setup. The Git installer is straightforward — the default options are generally fine. If you continue to use Claude Code at all, and plan to use this project, I HIGHLY recommend you learn more about how to use Git for project and file management. It is absolutely necessary to better track and understand how Claude is changing things in your workspace later on.

**Install:** [git-scm.com/downloads](https://git-scm.com/downloads)

### Docker Desktop

<!-- MIGRATE: README "Prerequisites" subsection "2. Docker Desktop" — moves here in full; README will not retain -->

Docker is a program designed to help people create self-contained, isolated environments (called a "container") on your computer that are strictly separated from everything else, and extremely easy to replicate and share. This protects your computer and prevents Claude Code from messing with anything it shouldn't be, and it ensures that even if somehow things go catastrophic, you can easily spin a new virtual environment back up in minutes. In this project, I use Docker to install every needed piece of software in a predictable and stress-free way, that has Python, data science libraries, and Claude Code all pre-installed. Think of it like a lightweight virtual computer running inside your computer. Docker Desktop includes everything you need (including Docker Compose, which coordinates the setup). After installing, make sure Docker Desktop is running before proceeding. If you're worried, you can see exactly what is installed by reading the Dockerfile in this repository -- feel free to ask your favorite LLM to help you interpret and inspect it, if you'd like.

**Install:** [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)

### Anthropic Account & Authentication

<!-- MIGRATE: README "Prerequisites" subsection "3. An Anthropic account" — moves here in full; README will not retain -->

Claude Code is the AI assistant that powers this project. It runs inside your terminal (not in a web browser) and needs to authenticate with Anthropic. You have two options:
- **Anthropic API key** — [Get one here](https://console.anthropic.com/). This is a pay-per-use key that you'll paste into Claude Code when prompted. Just note, this can get VERY expensive, very quickly. I HIGHLY recommend getting a Pro/Max subscription for this project.
- **Anthropic Pro/Max subscription** — If you have a Claude Pro or Max plan, Claude Code can authenticate through your subscription instead. It will walk you through this interactively. I am on the top-level Max plan and it is more than enough for my usage and development of this project, but admittedly a very high barrier to entry. Conversely, I think Pro will probably not be enough for reliably using it more than once every 4 hours (their rate limiting window), but it's worth testing! Please let me know your experiences.

Claude Code will prompt you to choose your authentication method the first time you run it — you don't need to configure anything in advance. Note that you can easily port this whole project over to a CLI tool of your choice (OpenCode, Codex, etc.) with a little bit of effort. Fork this repo, work with your favorite tool to convert it over, and please continue to share it broadly with others!!!

### Terminal Basics

<!-- MIGRATE: README "Prerequisites" subsection "4. A terminal program" — moves here in full; README will not retain -->
<!-- Includes the terminal basics table and tips -->

You'll interact with the assistant through your **terminal** (also called the command line or shell), where you type commands and press Enter to run them. This project is used entirely through the terminal — the text-based interface on your computer where you type commands. Your computer definitely already has this, but if you're not used to working in the terminal, here are some basics:

**Opening your terminal:**
- **Mac:** Open the "Terminal" app (search for it in Spotlight with `Cmd + Space`)
- **Windows:** Open "PowerShell" or "Command Prompt" from the Start menu (PowerShell is recommended)
- **Linux:** Open your terminal emulator (usually `Ctrl + Alt + T`)

**Helpful terminal basics:**
| What you want to do | Command | Example |
|---------------------|---------|---------|
| See where you are | `pwd` | Shows `/Users/yourname/daaf` |
| List files here | `ls` | Shows files and folders in current directory |
| Move into a folder | `cd foldername` | `cd daaf` |
| Go up one folder | `cd ..` | Goes to the parent directory |
| Clear the screen | `clear` | Clears clutter (your history is still there) |
| Cancel a running command | `Ctrl + C` | Stops whatever is currently running |
| Scroll up to see past output | Scroll or `Shift + Page Up` | See output that scrolled off screen |

**Tips:**
- You can paste commands into the terminal (`Cmd + V` on Mac, `Ctrl + V` or right-click on Windows)
- Press the up arrow key to recall previous commands
- Tab completion works — start typing a file/folder name and press `Tab` to auto-complete it

---

## Step-by-Step Installation

<!-- MIGRATE: README section "Quick Start" — the 6 commands with "What just happened?" explanations -->
<!-- This is now the SOLE home for installation steps; README will link here instead -->

### Step 1: Choose a Location and Clone the Repository

Navigate to the folder where you want this project to live, then download it:

```bash
# Navigate to the folder where you want this project to live. Change the below to the folder you want!
cd "C:\Users\Documents"

# Download the project to your computer
git clone https://github.com/brhkim/daaf.git
```

This creates a `daaf` folder containing all the project files.

### Step 2: Enter the Project Directory

```bash
cd daaf
```

You should now be inside the project directory. You'll see files like `CLAUDE.md`, `docker-compose.yml`, `Dockerfile`, and folders like `agents/`, `research/`, etc.

### Step 3: Build and Start the Container

```bash
docker compose up -d --build
```

This builds a Docker container with all the tools pre-installed using the Dockerfile provided with this project (Python, data science packages, Claude Code). The first time, this downloads base images and installs all packages — expect it to take a few minutes. Subsequent starts are fast since Docker caches everything.

The `-d` flag runs it in the background so you get your terminal back.

### Step 4: Open a Session Inside the Container

```bash
docker compose exec daaf-docker bash
```

This opens a terminal session *inside* the container, separated from the rest of your computer and running with all the software just installed. You'll notice your prompt changes — that's how you know you're "inside."

### Step 5: Launch Claude Code

```bash
claude
```

On first launch, Claude Code will prompt you to authenticate (API key or subscription login). After that, you're in — start asking research questions.

### Step 6: Select Your Model

<!-- MIGRATE: README "Prerequisites" subsection about recommended model (Opus 4.5/4.6) — moves here; README will not retain -->

```bash
/model
```

**Recommended model:** All development and testing of this project was done using **Opus 4.5** and **Opus 4.6**. I strongly recommend using one of these models for the best results. You can change your model at any time inside Claude Code by typing `/model` and selecting from the list. Other models (Sonnet, Haiku) have not been tested with this workflow and may produce inconsistent results — especially for the multi-agent orchestration and validation stages, which rely on the model's ability to follow complex, multi-step protocols reliably.

---

## First Launch: Confirming Everything Works

<!-- NEW: A short checklist or test sequence to verify the setup is working correctly -->

A quick verification sequence to confirm Docker is running, the container is healthy, Claude Code is authenticated, and the correct model is selected.

---

## Day-to-Day Start/Stop Workflow

<!-- MIGRATE: README section "Day-to-Day Usage" — moves here in full; README will not retain -->

The daily commands to start a session, work, and shut down — plus what happens to your files when the container stops.

### Starting a Session

Once installed, your daily workflow is just:

```bash
# Get into the project directory, inputting the right file path for your own system
cd "C:\Users\Documents\daaf"
# Make sure Docker Desktop is running on your computer, then:
docker compose up -d
docker compose exec daaf-docker bash
claude
```

### Ending a Session

```bash
# Type /exit or press Ctrl+C to leave Claude Code, then:
exit
docker compose down
```

### What Persists Between Sessions

<!-- MIGRATE: README section "How Files Work" (partial) — moves here; README will not retain -->

Your files are safe — they're on your computer, not just inside the container. Stopping the container doesn't delete your research outputs.

---

## How Files Sync Between Container and Host

<!-- MIGRATE: README section "How Files Work" — moves here in full; README will not retain -->

Your local `daaf/` folder is connected to the container. This means:

- **Files sync both ways** — when the assistant creates a report or dataset inside the container, it appears in the folder on your computer too. You can open these files normally.
- **Your work persists** — stopping the container doesn't delete your research outputs. They live in your project folder.
- **Only this folder is accessible** — the container cannot see any other files on your computer. Your documents, photos, and everything else are completely isolated.

---

## Viewing Marimo Notebooks in Your Browser

<!-- MIGRATE: README section "Viewing Marimo Notebooks" — moves here in full; README will not retain -->

The assistant uses a python library called "marimo" to create streamlined python code "notebooks" as part of its analysis. It can also use this library to create nice, interactive dashboards for you of analyses it has completed. To view one in your browser:

```bash
# Inside the container — view a notebook (replace the path with your actual notebook)
marimo run research/YYYY-MM-DD\ Title/notebook.py --host 0.0.0.0 --port 2718 --headless
```

Then open [http://localhost:2718](http://localhost:2718) in your computer's browser (no need to mess with anything in the terminal here). The notebook renders there as an interactive document.

To edit a notebook interactively, use `marimo edit` instead of `marimo run`:

```bash
marimo edit research/YYYY-MM-DD\ Title/notebook.py --host 0.0.0.0 --port 2718 --headless
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

<!-- MIGRATE: README section "Troubleshooting" (the 5 items under Installation) — moves here in full; README will not retain -->
<!-- NEW: Additional troubleshooting items anticipated from project structure analysis -->

### Docker Daemon Not Running

**"Cannot connect to the Docker daemon"** — Make sure Docker Desktop is running (look for the whale icon in your system tray / menu bar).

### Port Conflicts

**"Port 2718 already in use"** — Another process is using that port. Either stop it, or change the port mapping in `docker-compose.yml` (e.g., `"3000:2718"` to use port 3000 on your host).

### Authentication Persistence

**Claude Code asks for an API key every time** — Claude Code stores its configuration inside the container. If you fully remove the container (`docker compose down`), you may need to re-authenticate next time. To avoid this, you can set `ANTHROPIC_API_KEY` as an environment variable in a `.env` file in the project root (the `.gitignore` already prevents `.env` from being shared publicly).

### Slow First Build

**Container seems slow to build the first time** — The first `docker compose up --build` downloads base images and installs all packages. This is a one-time cost — subsequent starts are fast since Docker caches everything.

### "command not found: docker"

**"command not found: docker"** — Docker Desktop may not be installed, or your terminal needs to be restarted after installation. Close and reopen your terminal, and make sure Docker Desktop is installed and running.

### Container Won't Start After System Update

<!-- NEW: Anticipated issue — Docker Desktop updates sometimes require attention -->

What to try if Docker Desktop was updated or the system was restarted.

### Permission Issues on Linux

<!-- NEW: Anticipated issue — Docker group membership on Linux -->

How to add your user to the `docker` group if you see permission errors.

---

## Recommended Next Steps

- [**02. Understanding DAAF**](02_understanding_daaf.md) — Learn to work with DAAF for the first time: what to expect, engagement modes explained, your first analysis walkthrough
- [**06. FAQ: Technical**](06_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, design rationale, authentication errors, and other common errors
- [**07. FAQ: Philosophy**](07_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
