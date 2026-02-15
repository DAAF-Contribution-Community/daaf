# 01. Installation & Quick Start

This is the complete first-time installation and setup guide for DAAF. This document covers every step from installing prerequisites to running your first session, as well as tips for file management, viewing compiled research script notebooks, and troubleshooting.

[**Back to main**](../.)

---

## Table of Contents
- [**Prerequisites**](#prerequisites)
- [**Installing DAAF**](#installing-daaf)
- [**Day-to-Day Start/Stop Workflow**](#day-to-day-startstop-workflow)
- [**How to Manage DAAF Project Files and Output**](#how-to-manage-daaf-project-files-and-output)
- [**Keeping DAAF Updated**](#keeping-daaf-updated)
- [**Viewing Marimo Notebooks in Your Browser**](#viewing-marimo-notebooks-in-your-browser)
- [**Setup Troubleshooting**](#setup-troubleshooting)
- [**Recommended Next Steps**](#recommended-next-steps)

---

## Prerequisites

Before installing DAAF, there are four (technically five) key prerequisites. Please read the Anthropic account requirement especially closely; the price of the necessary subscription is definitively the highest barrier to entry at this time. I hope this will change in the near future with greater testing and community support for open-source models!

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

### 3. Git

Git is software that primarily helps people track file changes and updates. It helps people identify exact line changes, and collect a full history of all changes in sequence (you can see that history for DAAF [here](https://github.com/DAAF-Contribution-Community/daaf/commits/main/)!) In this case, we're using Git to help you download ("clone") this project's core files to your computer. You'll use it just once during setup. If you continue to use Claude Code at all, and plan to use this project, I HIGHLY recommend you learn more about how to use Git for project and file management. It is absolutely necessary to better track and understand and review how Claude is changing things in your workspace later on. If you run into any Git-related errors during install, you may need to restart your computer to let the install fully sink in.

**Install:**
- **macOS**: You will first need to use the Terminal mentioned above to install [Homebrew](https://brew.sh/). Follow the directions on that site, and then install Git by following directions here: [git-scm.com/downloads](https://git-scm.com/downloads).
- **Windows**: You can install Git via the installer available for download at [git-scm.com/downloads](https://git-scm.com/downloads)
- **Linux**: You probably already know what to do, but otherwise, follow directions at [git-scm.com/downloads](https://git-scm.com/downloads)

### 4. Docker Desktop

Docker is a program designed to help people create self-contained, isolated environments (called a "container") on your computer that are strictly separated from everything else, and extremely easy to replicate and share. This protects your computer and prevents Claude Code from messing with anything it shouldn't be, and it ensures that even if somehow things go catastrophic, you can easily spin up a new virtual environment back up in minutes with zero consequences. In this project, I also use Docker to install every needed piece of software in a predictable and stress-free way to have Python, data science libraries, and Claude Code all ready to go in one step. Think of it like a lightweight virtual computer running inside your computer that gets created via a very specific recipe, every single time. Docker Desktop includes everything you need (including Docker Compose, which coordinates the setup). After installing, make sure Docker Desktop is actually running before proceeding. If you're worried, you can see exactly what is installed by reading the Dockerfile in this repository -- feel free to ask your favorite LLM to help you interpret and inspect it, if you'd like. If you run into any Docker-related errors during install, you may need to restart your computer to let the install fully sink in.

**Install:** [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)

---

## Installing DAAF

Okay, with all the prerequisites out of the way, installation itself is only seven very easy copy-paste steps and will only take about 5 minutes start-to-finish with a decent internet connection.

### Step 1: Choose a project download location on your computer and open it in your terminal

Using your terminal, first navigate to the folder where you want the installation files downloaded to:

```bash
# Change the below to the folder you want!
cd "C:\Users\Downloads"

```

### Step 2: Use Git to download the project files and enter the Project Directory

```bash
# Now actually download the project files to your computer from GitHub
git clone https://github.com/DAAF-Contribution-Community/daaf.git

# Enter the newly downloaded project directory
cd daaf
```

This creates a `daaf` folder containing all the project files. You should now be inside the project directory. You can confirm this worked correctly by typing `ls` to list the installation files in this folder: you'll see files like `CLAUDE.md`, `docker-compose.yml`, `Dockerfile`, and folders like `agents/`, `user_documentation/`, etc.

> **Important:** The `git clone` command creates a folder named `daaf` by default. **Do not rename this folder** before you finish this full process.

### Step 3: Copy the project files into Docker

Rather than let Claude use and edit files directly on your computer, we're going to make a **secure copy** for Claude to operate on separately using Docker. Run this command next, making sure that Docker Desktop is currently running in the background:

```bash
# This uses Docker to help us copy files from your installation folder into a place Docker can work in later
docker run --rm -v "${PWD}:/source:ro" -v "daaf_daaf-data:/dest" busybox cp -a /source/. /dest/
```

This copies all the project files into a **"Docker volume"** — a storage area managed by Docker that will serve as the Docker container's working directory. Think of it like creating a dedicated workspace inside Docker where all your research, data, and outputs will live. The `daaf/` folder on your computer is used as the starting point here, but going forward, the Docker volume is where the actual work happens (see "How to Manage DAAF Project Files and Output" below for more on this). You can confirm this worked correctly by looking at the Volumes panel in the Docker Desktop app left-side toolbar: you should see a Volume listed named `daaf_daaf-data` in the list.

### Step 4: Use Docker to create and start the container

```bash
# This code uses the docker-compose.yaml file to begin the Docker container with specific pre-sets
docker compose up -d --build
```

This builds an isolated/protected Docker container with all the necessary tools pre-installed (Python, data science packages, Claude Code) using the Dockerfile provided and the copied project files from the Docker volume we just made. The first time, this downloads base images and installs all packages — expect it to take a few minutes as it pulls in all the needed software. Subsequent starts are really fast since Docker caches everything. You can confirm this worked correctly by looking at the Images panel in the Docker Desktop app left-side toolbar: you should see an Image listed named `daaf-daaf-docker` in the list. You'll also see one named `busybox` -- this was just a temporary super-basic image we used to do the file transfer in the step above!

### Step 5: Open a terminal session inside the Docker container

Once the Docker container setup is complete, your terminal will resume in the project folder. Run the following command to "enter" the Docker container we just created and turned on.

```bash
docker compose exec daaf-docker bash
```

This opens your terminal session *inside* the container, separated from the rest of your computer and running with all the software just installed. You'll notice your terminal prompt changes — that's how you know you're "inside." Think of this like activating a mini virtual computer, within your computer, that you're now interacting with exclusively via this terminal. You can confirm this worked correctly by looking at the Containers panel in the Docker Desktop app left-side toolbar: you should see a Container listed named `daaf` in the list, with a dropdown extension/accordion button that'll reveal another item in the list named `daaf-docker-1`. 

### Step 6: Launch Claude Code

Now that we're in, we should have everything we need to start working. Enter the following command to launch Claude Code, configured with everything DAAF has to offer and ready to run.

```bash
claude
```
On first launch, Claude Code should prompt you to authenticate (API key or subscription login). Follow its instructions to complete the process as needed based on your method. Remember that CTRL+C actually exits the terminal, so use (Windows/Linux: CTRL+SHIFT+C and CTRL+V) and (macOS: Cmd+C and Cmd+V) if you want to copy/paste.

### Step 7: Adjust some quick configuration settings

Once you're in, there are a few settings to adjust to ensure that the workflow is able to operate as expected. First, type the following into Claude's chat window:

```bash
/config
```

And then change the **"Auto-compact"** setting to **False** and **"Verbose output"** setting to **True** by navigating down with your arrow keys and hitting Enter when the option is selected. When the settings are changed correctly, you can then hit the ESC key to return to the regular Claude chat and begin working.

**Recommended model:** You can check which Claude model is being used by checking the indicator below the chat line (Opus, Sonnet, Haiku). You can change which Claude model is being used at any time by typing `/model`. All development and testing of this project was done using **Opus 4.5** and **Opus 4.6**. I unfortunately think that these models are absolutely required; other models (Sonnet, Haiku) are not nearly as capable and produce erratic, inconsistent results. The complexity of tasks embedded in the DAAF workflow (multi-agent orchestration) relies on the model's ability to follow complex, multi-step protocols reliably. This is also the reason why the Claude Max subscription is a likely prerequisite here: Opus models are very resource-intensive, and it's hard to complete the DAAF workflows under the "Pro" or "Free" tiers accordingly.

Opus 4.6 (unlike Opus 4.5) also allows you to select its "thinking level" by tapping left-and-right arrow keys while Opus 4.6 is selected on the /model selector in Claude Code. All tests I've conducted to date are using the "High" setting -- as this is a case where quality is far more important than quantity, I strongly recommend doing the same. This will have usage and API limit ramificiations, though, so it is a reasonable thing to test out the tradeoffs for yourself! Please do report back with any findings so we can incorporate that into our guidance here.

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

> **Quick tip before you go any further**: Now that you have Claude Code up and running with DAAF, you can actually start asking Claude for help! If you have any questions, concerns, issues, or confusion about **anything** you read in this guide or other parts of the User Documentation: Ask Claude about it! Point it to any document, section, or sentence, and then ask it to help you understand it better. It has visibility into the whole project documentation at-will, so it should be able to help you out as you go. This kind of personalized assistance should be invaluable for anyone getting onboarded into using DAAF and Claude Code more generally!

---

## Day-to-Day Start/Stop Workflow

Now that you've got DAAF installed and running for the first time, let's talk through simple commands you'll use to get in and out of this workflow day-to-day, as well as how to manage files produced by DAAF.

### Starting a New Session

Once you've completed the above Docker installation steps, your daily workflow is just to open your terminal again and run the following commands:

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

When you're ready to end a session, you have two options. The first option: Close the terminal window, and then use your Docker Desktop app window to "pause" your Docker container (click the Containers panel in the left-side toolbar, look for "daaf" in the list that appears, hit the "Stop" button). The other option is to do this fully through the terminal: 

```bash
# Exit Claude Code first. You can also just press CTRL+C twice
/exit
# That gets you back into the terminal window, running *within* your Docker container. 
# You'll know you're still in the Docker container if your command line says something like, "appuser@5jhfdsn54:/daaf$" before whatever you type
# So now let's exit the Docker container
exit
# And then we can turn off the Docker container
docker compose down

# You can then just close your terminal. All the DAAF files and research outputs remain safe and persist in the Docker volume we created at installation time
```

## How to Manage DAAF Project Files and Output

Your research files, data, and outputs live inside the **Docker volume** we created during installation — a storage area managed by Docker, **copied from** the `daaf/` folder on your computer. Think of the `daaf/` folder on your computer as the "recipe" that was used to set everything up, while the Docker volume is the actual "kitchen" where all the work happens.

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

Since your research files live inside the Docker volume, it'll be extremely important to regularly back up your work separately from the Docker volume. You can do that most easily using the Docker Desktop method above (go into the Docker volume file viewer and download the whole daaf or research folder to somewhere else on your computer).

### Viewing report Markdown (.md) files

LLM assistants work best on text files, which means that proprietary document formats like Microsoft Word or Google Docs aren't great for this type of work. DAAF produces all its output report documents in Markdown (.md) format. You can open these in any basic text editor, but basic text editors tend not to display the formatting very nicely. I recommend installing a basic Markdown viewer, or you can copy the Markdown text into any free online viewer (e.g., [StackEdit](https://stackedit.io/app)) 

---

## Keeping DAAF Updated

DAAF is actively being developed and updated. If you'd like to pull in the latest fixes, extensions, and updates (which for a while may be as often as daily!!), updating is straightforward. Since the project files live inside the Docker volume, the update happens inside the container -- the files that are visible on your original computer's folder are just old copies, now. Before updating, I recommend backing up your Docker volume's research folder as a precaution (see "Backing Up Your Work" above).

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

Note that `git pull` inside the container shouldn't impact any of your research files. `git pull` also won't work correctly if you've made any edits to the core DAAF workflow or documentation files (basically, anything outside of the research folder). In that case, you may want to submit a Pull request for your changes (if you've made useful updates you want to share broadly!) -- otherwise, you'll need to navigate your own merge conflicts and such (a topic for general Git tutorials, rather than here!).

---

## Viewing Marimo Notebooks in Your Browser

The assistant uses a python library called "marimo" to create streamlined python code "notebooks" as part of its analysis. It can also use this library to create nice, interactive dashboards for you of analyses it has completed. To **view** one in your browser:

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

Then open [http://localhost:2718](http://localhost:2718) in your computer's browser (no need to mess with anything in the terminal here). The notebook renders there as an interactive document. The nice thing about these is that they're also written in regular Python code, so you can inspect its code very easily in any text browser as well.

To **edit** a notebook interactively, use `marimo edit` instead of `marimo run`:

```bash
marimo edit 'research/YYYY-MM-DD Title/YYYY-MM-DD Notebook Name.py' --host 0.0.0.0 --port 2718 --headless
```

---

## Setup Troubleshooting

- **"git: The term 'git' is not recognized as the name of a cmdlet, function, script file, or operable program" or "git: command not found"** — Make sure you have Git installed successfully. You may need to restart your computer after installation for it to fully register in your Terminal.
- **"docker: The term 'docker' is not recognized as the name of a cmdlet, function, script file, or operable program" or "docker: command not found"** — Make sure you have Docker installed successfully. You may need to restart your computer after installation for it to fully register in your Terminal.
- **"unable to get image 'daaf-daaf-docker'"** — Make sure Docker Desktop is running and that you've run the initial `docker compose up -d --build` command during installation to create the necessary Docker image first. You can confirm it exists in the Docker Desktop app Images panel on the left-side toolbar.
- **"service "daaf-docker" is not running"** — Make sure Docker Desktop is running and that you've run the `docker compose up -d` command to start the Docker container first. You can confirm it's running in the Docker Desktop app Containers panel on the left-side toolbar.
- **Container seems really slow to build the first time** — The first `docker compose up --build` downloads base images and installs all packages. This is a one-time cost — subsequent starts are fast since Docker caches everything.
- **"I can't find my research files on my computer"** — With Docker volumes, your research files live inside Docker's managed storage, not in the `daaf/` folder on your computer. See **How to Manage DAAF Project Files and Output** above for more information.
- **"Port 2718 already in use" when trying to view Marimo notebooks** — Another process is using that port. Either stop it, or change the port mapping in `docker-compose.yml` (e.g., `"3000:2718"` to use port 3000 on your host).
- **Claude Code asks for an API key every time** — Claude Code stores its configuration inside the container. If you fully remove the container (`docker compose down`), you may need to re-authenticate next time. To avoid this, you can set `ANTHROPIC_API_KEY` as an environment variable in a `.env` file in the project root (the `.gitignore` already prevents `.env` from being shared publicly).

---

## Recommended Next Steps

- [**02. Understanding and Working with DAAF**](02_understanding_daaf.md) — Learn to work with DAAF for the first time: what to expect, how to use it, and how to test its strengths and limitations
- [**06. FAQ: Philosophy**](06_faq_philosophy.md) — Grapples with the broader implications of this work, AI automation in general, model advancement pace, approaching the "exponential", environmental ethics, what this means for the next generation of researchers, and more
- [**07. FAQ: Technical Support**](07_faq_technical.md) — Covers frequently asked questions about Docker, issues with Claude Code, usage limits, authentication errors, and other common errors
- [**Back to main**](../.)
