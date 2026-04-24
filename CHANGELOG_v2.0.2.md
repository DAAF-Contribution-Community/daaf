# DAAF v2.0.2 -- Operations Infrastructure & Migration Support

**Release date:** 2026-04-24

This release focuses on making DAAF easier to install, update, and maintain.
If you're an existing user, the most important thing in this release is the
**migration script** -- a one-liner that connects your installation to the
update pipeline so you never have to manually update again.

---

## What's New

### One-Line Installer

- **`install.sh` / `install.ps1`** -- Automated installation with a single
  terminal command. Downloads Docker build files, builds the image, and sets up
  the DAAF container with everything ready to go.
- Replaces the old multi-step ZIP download process from v2.0.0 and v2.0.1.

### Update Infrastructure

A complete suite of host-side utility scripts for day-to-day operations:

- **`update_daaf.sh` / `update_daaf.ps1`** -- Automated framework updates with
  backup, conflict detection, and merge support
- **`backup_daaf.sh` / `backup_daaf.ps1`** -- One-command full volume backup
- **`rebuild_daaf.sh` / `rebuild_daaf.ps1`** -- One-command Docker image rebuild
- **`run_daaf.sh` / `run_daaf.ps1`** -- One-command launcher for Claude Code
  inside the DAAF container
- **`view_logs.sh` / `view_logs.ps1`** -- Session log browser with HTML viewer

### Migration Script

- **`migrate_daaf.sh` / `migrate_daaf.ps1`** -- A one-time migration for
  existing installations that bridges the gap between the old installation
  method and the new update infrastructure.
- Automatically connects your local git history to the upstream repository so
  that `update_daaf.sh` works going forward.
- Preserves all research data, framework customizations, and your full audit
  trail of commits.
- Creates a backup before making any changes. Safe to re-run if interrupted.

### Framework & Documentation Improvements

- 38 modified framework files across agents, modes, workflows, and core
  configuration (`CLAUDE.md`)
- Improved session logging and crash recovery
- Updated installation guide and quickstart documentation

---

## How to Update

Pick the scenario that matches your situation.

### Scenario 1: "I installed the old way (ZIP download) and don't have update scripts"

**This is the most common scenario for existing users.** You installed DAAF by
downloading a ZIP from GitHub and following the original setup instructions. You
don't have `update_daaf.sh` or any of the other utility scripts yet.

Run the migration script first. It will download all the utility scripts, back
up your data, and connect your installation to the update pipeline -- all in one
step.

**macOS / Linux (Terminal):**

```bash
curl -fsSL https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/migrate_daaf.sh | bash
```

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/migrate_daaf.ps1 | iex
```

After the migration completes, use `update_daaf.sh` (or `update_daaf.ps1`) for
all future updates -- you won't need the migration script again.

**Good to know:**
- The migration creates a timestamped backup of your entire DAAF volume before
  making any changes.
- It is idempotent -- safe to run multiple times. If something interrupts it
  partway through, just run it again.
- Your research data, framework customizations, and git commit history are all
  preserved.

### Scenario 2: "I installed with `install.sh` or `install.ps1`"

You already have the update scripts. Just run:

**macOS / Linux:**

```bash
cd daaf-docker
bash update_daaf.sh
```

**Windows:**

```powershell
cd daaf-docker
.\update_daaf.ps1
```

### Scenario 3: "I want to start fresh"

Use the new one-line installer. This replaces the old ZIP download method
entirely.

**macOS / Linux:**

```bash
curl -fsSL https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/install.sh | bash
```

**Windows:**

```powershell
irm https://raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/install.ps1 | iex
```

**Note:** A fresh install creates a new DAAF volume. If you have an existing
installation with research data you want to keep, use the migration path
(Scenario 1) instead, or back up your `research/` folder before proceeding.

---

## Breaking Changes

- **`scripts/entrypoint.sh` removed.** Git configuration is now baked into the
  Dockerfile at build time. If you are managing your Docker setup manually
  (outside the provided scripts), you will need to rebuild your image.
- **Port 2719 is now mapped** for the session log viewer. If you have a custom
  `docker-compose.yml`, add the port mapping or use `rebuild_daaf.sh` to pick
  up the new configuration automatically.

---

## Technical Notes

The migration script uses `git replace --graft` to connect your local commit
history to the upstream repository. This is a standard, non-destructive git
operation -- it creates a lightweight pointer that tells git your local history
descends from the upstream release you originally installed. All normal git
commands (log, merge, pull, diff) work transparently after the graft.

After migration, `git fsck` may report warnings about the grafted root commit.
These warnings are **expected and harmless** -- they do not indicate corruption.
Everything works correctly for day-to-day use.
