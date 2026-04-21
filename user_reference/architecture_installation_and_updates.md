# Architecture: Installation and Update System

Technical reference for DAAF maintainers and contributors. This document describes
the design rationale, internal mechanics, and tradeoff analysis behind the
installation and update infrastructure.

---

## Table of Contents

- [1. Architecture Overview](#1-architecture-overview)
- [2. Install Scripts](#2-install-scripts)
- [3. Update Architecture](#3-update-architecture)
- [4. Design Decisions and Tradeoffs](#4-design-decisions-and-tradeoffs)
- [5. Future Considerations](#5-future-considerations)

---

## 1. Architecture Overview

### Two-Phase Install: Minimal Build Context, Then Git Clone

DAAF's installation separates image building from repository delivery using a
two-phase approach:

| Phase | What Happens | Where |
|-------|-------------|-------|
| **Phase 1: Build** | Download 2 files (~5 KB), build Docker image | Host machine |
| **Phase 2: Populate** | `git clone --depth 1` the full repository into the named volume | Inside the container |

**Phase 1** creates a minimal build directory on the host (`daaf-docker/` in the
user's current terminal directory) with
only the files Docker needs at build time:

- `Dockerfile` -- image recipe (Python, system libs, pip packages, Claude Code)
- `docker-compose.yml` -- service definitions, volume mapping, security config

These 2 files are the Docker build context. Nothing else from the repository is
needed to construct the image because DAAF's framework files (agents, skills,
hooks, templates) are not baked into the image -- they live in a Docker named
volume that is populated in Phase 2.

**Phase 2** starts the freshly built container, then runs `git clone` inside it
to populate the `/daaf` volume with the full repository, including `.git`
history. This gives the container a working git remote, which is the foundation
of the update system.

### Why This Architecture

Three approaches were considered:

| Approach | Pros | Cons |
|----------|------|------|
| **Full repo clone on host** | Standard git workflow | Requires git on user's machine; Windows git can have line-ending issues; bind mounts have performance and permission problems on macOS/Windows |
| **Zip download + busybox copy** (legacy) | No git dependency on host | No update story beyond re-downloading the zip; overwrites local edits silently; no conflict visibility |
| **Minimal build context + clone into volume** (current) | No git on host needed; full update story via `update.sh`; clean container-host boundary; named volume avoids bind mount issues | Slightly more complex install script; Dockerfile changes require copy-back step |

The current approach was chosen because it provides the best update experience
(git-native inside the container) while keeping host-side requirements to a
minimum (Docker Desktop only). The tradeoff is the container-host boundary for
Dockerfile changes, which is handled with advisory messaging (see Section 3).

### The Container-Host Boundary

A fundamental constraint of this architecture: **Docker Compose reads the
Dockerfile from the host filesystem, but DAAF's working copy lives inside the
container's named volume.** When `update.sh` pulls a new Dockerfile into the
volume, it cannot directly trigger a rebuild -- the user must copy the updated
file back to the host build directory and run `docker compose up -d --build`
from the host terminal.

This boundary is inherent to Docker's architecture. The update script detects
Dockerfile changes and prints exact copy-back commands, but cannot automate the
rebuild itself because it runs inside the container.

### Named Volume Strategy

DAAF uses a Docker named volume (`daaf-data`) rather than a bind mount:

| Concern | Named Volume | Bind Mount |
|---------|-------------|------------|
| **Performance** | Native filesystem speed | Severe degradation on macOS (osxfs/virtiofs), moderate on Windows (WSL2 passthrough) |
| **Permissions** | Consistent UID mapping with init container fix | Host UID vs. container UID mismatches cause permission errors |
| **Portability** | Works identically across OS | Path syntax differs; `.git` behavior varies |
| **User visibility** | Files not directly visible on host (requires `docker cp` or Docker Desktop) | Files visible in host filesystem |
| **Persistence** | Survives `docker compose down`, container removal, image rebuilds | Tied to host directory |

The init container (`daaf-init` in `docker-compose.yml`) runs `chown -R
1000:1000 /daaf` as root before the main container starts, repairing any
ownership mismatches (especially common on macOS where Docker volumes may have
files owned by root or the host UID 501).

---

## 2. Install Scripts

Two install scripts provide identical behavior for their respective platforms:

- `/daaf/install.sh` -- macOS and Linux (Bash)
- `/daaf/install.ps1` -- Windows (PowerShell 5.1+)

### Step-by-Step Flow

Both scripts follow the same 4-step sequence:

```
[1/4] Create build directory
      mkdir -p ./daaf-docker
      (PowerShell: New-Item -ItemType Directory)

[2/4] Download 2 build-context files
      curl/Invoke-WebRequest from raw.githubusercontent.com:
        - Dockerfile
        - docker-compose.yml

[3/4] Build Docker image
      COMPOSE_PROJECT_NAME=daaf docker compose up -d --build

[4/4] Clone DAAF into volume
      docker compose exec -T daaf-docker git clone --depth 1 ...
      docker compose exec -T daaf-docker bash -c 'cp -a /tmp/daaf-clone/. /daaf/ && rm -rf /tmp/daaf-clone'
```

The clone uses a `/tmp/daaf-clone` staging directory because git refuses to
clone into a non-empty directory, and `/daaf` already exists as the volume mount
point. The `cp -a` preserves permissions and symlinks, then the staging
directory is cleaned up.

### The `COMPOSE_PROJECT_NAME=daaf` Requirement

Docker Compose derives volume names from the project name:
`{project_name}_{volume_name}`. Without an explicit project name, Docker Compose
defaults to the directory name, which varies by user (could be `daaf-docker`,
`downloads`, etc.). Setting `COMPOSE_PROJECT_NAME=daaf` ensures:

- The volume is always named `daaf_daaf-data`
- The container is always named `daaf-daaf-docker-1`
- `docker cp` commands in documentation and update scripts work predictably
- The legacy manual install (which uses `docker compose` from the extracted
  `daaf-main` directory without this env var) produces `daaf_daaf-data` because
  the `docker-compose.yml` itself sets `name: daaf` at the top level

For the one-line installer, the env var is set before the `docker compose` call.
For manual installs, the compose file's top-level `name: daaf` field handles it.

### Docker Readiness Wait Loop

After `docker compose up -d`, the container may not be immediately ready to
accept `exec` commands (the image may still be starting, the init container may
still be running, etc.). Both scripts implement a polling loop:

```
Retry up to 30 times, sleeping 2 seconds between attempts (60s total):
  docker compose exec -T daaf-docker true
  If exit code 0 -> container is ready, proceed
  If exit code != 0 -> increment counter, sleep 2, retry
If 30 retries exhausted -> print error, exit 1
```

The `-T` flag disables pseudo-TTY allocation, which is necessary because piped
installers (`curl | bash`, `irm | iex`) do not have an interactive terminal
attached. The `true` command is the simplest possible health check -- it succeeds
if the container is running and the exec interface is available.

### Error Recovery: Clone Failure

If the git clone fails (network issue, GitHub outage), the scripts:

1. Report that the Docker image was built successfully (Phase 1 completed)
2. Print the exact retry commands the user can run manually
3. Exit with code 1

This is a deliberate partial-success design: the expensive image build is
preserved, and only the lightweight clone needs to be retried.

### Cross-Platform Differences

| Concern | `install.sh` (Bash) | `install.ps1` (PowerShell) |
|---------|--------------------|-----------------------------|
| **Error handling** | `set -euo pipefail` (exit on any error) | `$ErrorActionPreference = "Stop"` |
| **TLS** | System default (modern TLS) | Explicitly enables TLS 1.2: `[Net.ServicePointManager]::SecurityProtocol` -- required on PowerShell 5.1 which defaults to TLS 1.0/1.1 |
| **Docker check** | `command -v docker` + `docker info` stderr redirect | `Get-Command docker` + `$LASTEXITCODE` check |
| **Download** | `curl -fsSL` (fail silently on HTTP errors, show errors, follow redirects, silent progress) | `Invoke-WebRequest -Uri ... -OutFile ...` |
| **File paths** | `$(pwd)/daaf-docker` | `(Get-Location)\daaf-docker` |
| **Daemon check** | `docker info &> /dev/null 2>&1` | `$null = docker info 2>&1` then check `$LASTEXITCODE` |
| **Line continuation** | `\` | `` ` `` (backtick) |

---

## 3. Update Architecture

**File:** `/daaf/scripts/update.sh`

### Design Philosophy: "Show, Don't Force"

The update script operates on a principle of **advisory transparency**: it
detects the current git state, explains what it found in plain language (with
explanations of git concepts for non-technical users), presents options, and
never runs destructive operations without explicit user choice. When a situation
is too complex for the script to handle safely (detached HEAD, fork without
upstream remote), it prints the exact manual commands and exits.

Key invariants:
- A backup is always created before any modifications
- Interactive prompts gate every operation that modifies the working tree
- Conflict resolution is always left to the user -- the script exits with
  instructions rather than attempting automatic resolution
- The script requires an interactive terminal (`[ ! -t 0 ]` check) and refuses
  to run in piped/scripted contexts

### The Backup System

Before any modifications, the script creates two independent backup mechanisms:

| Backup Type | What It Is | Why It Exists |
|-------------|-----------|---------------|
| **tar.gz archive** (`/daaf/daaf-backup-{timestamp}.tar.gz`) | Complete snapshot of `/daaf` excluding `.git/`, `.claude/logs/`, and other backup archives | Safety net for users unfamiliar with git; can be extracted to restore files regardless of git state; can be copied to host via `docker cp` |
| **Git backup branch** (`backup/pre-update-{timestamp}`) | Branch pointer at the pre-update HEAD commit | Enables instant git-native rollback via `git reset --hard backup/pre-update-{timestamp}`; no file extraction needed |

Both exist because they serve different recovery scenarios. The tar.gz is
insurance against git state corruption -- even if the git repository becomes
unusable, the archive provides a path back. The git branch is the fast-path
rollback for users comfortable with git.

The backup is created lazily (only when the script is about to modify something)
and only once per run (the `BACKUP_CREATED` flag prevents duplicate backups).
After creating the backup, the script recommends downloading it to the host via
`docker cp` before proceeding, with a y/n prompt to continue.

### Git State Decision Tree

The update script handles 6 distinct git states. The following decision tree
shows the flow:

```
Start
  |
  v
Has git remote?
  |
  +-- NO --> Print: "Add remote or use zip update method" --> EXIT
  |
  +-- YES
        |
        v
    Is origin the upstream repo?
      |
      +-- NO (fork detected)
      |     |
      |     v
      |   Has 'upstream' remote?
      |     +-- NO --> Print: "Add upstream remote" --> EXIT
      |     +-- YES --> Use 'upstream' as source remote
      |
      +-- YES --> Use 'origin' as source remote
            |
            v
        Fetch from remote
            |
            v
        On a named branch?
          |
          +-- NO (detached HEAD) --> Print: "Checkout a branch" --> EXIT
          |
          +-- YES
                |
                v
            Already up to date? (same commit, no dirty files)
              |
              +-- YES --> Print: "Nothing to do" --> EXIT
              |
              +-- NO
                    |
                    v
                On the default branch (main/master)?
                  |
                  +-- NO (feature branch)
                  |     |
                  |     v
                  |   STATE 1: NON-DEFAULT BRANCH
                  |   Prompt: Update + merge, or abort
                  |   Flow: stash -> checkout main -> pull -> checkout back -> merge -> unstash
                  |
                  +-- YES
                        |
                        v
                    Has local commits ahead of remote?
                      |
                      +-- YES
                      |     |
                      |     v
                      |   STATE 2: LOCAL COMMITS ON DEFAULT BRANCH
                      |   Prompt: Merge, Squash-Rebase, or Abort
                      |   Merge: git merge upstream/main
                      |   Rebase: reset --soft merge-base -> commit -> rebase upstream/main
                      |
                      +-- NO
                            |
                            v
                        Has uncommitted changes?
                          |
                          +-- YES
                          |     |
                          |     v
                          |   STATE 3: DIRTY WORKING TREE, NO LOCAL COMMITS
                          |   Prompt: Stash + update + pop, Show diff first, or Abort
                          |
                          +-- NO
                                |
                                v
                              STATE 4: CLEAN, BEHIND REMOTE
                              Create backup, pull, done
```

States summarized:

| State | Branch | Local Commits | Dirty Files | Action |
|-------|--------|---------------|-------------|--------|
| 1 | Non-default | Any | Any | Stash, checkout default, pull, checkout back, merge |
| 2 | Default | Yes (ahead) | Any | User chooses: merge or squash-then-rebase |
| 3 | Default | No | Yes | Stash, pull, pop |
| 4 | Default | No | No | Straight pull |
| 5 | Detached HEAD | N/A | N/A | Advisory exit |
| 6 | No remote | N/A | N/A | Advisory exit |

### Interactive Prompts: Automated vs. User Choice

| Operation | Behavior | Rationale |
|-----------|----------|-----------|
| Backup creation | Automated (with proceed/abort prompt) | Always safe, always needed |
| `git fetch` | Automated | Read-only, no risk |
| `git pull` (clean state) | Automated after backup | No conflicts possible |
| `git stash` / `git stash pop` | Automated when needed | Reversible via backup branch |
| Merge vs. rebase | User chooses | Different tradeoffs; user must understand implications |
| Fork setup (`upstream` remote) | Advisory only (prints commands) | Modifying remotes on a fork has workflow implications the script cannot assess |
| Detached HEAD resolution | Advisory only (prints commands) | Multiple valid paths; user intent matters |
| Conflict resolution | Advisory only (prints commands, exits) | Conflict resolution is inherently manual |

### The Squash-Then-Rebase Strategy

When a user has local commits on the default branch, the rebase option uses a
squash-then-rebase technique rather than a standard multi-commit rebase:

```
1. Find merge-base (common ancestor of HEAD and upstream/main)
2. git reset --soft {merge-base}
   (Moves HEAD back but keeps all changes staged)
3. git commit -m "Local DAAF customizations (N commits, squashed ...)"
   (Creates a single commit containing all local changes)
4. git rebase upstream/main
   (Replays that single commit on top of the latest upstream)
```

**Why squash first:** A standard `git rebase` replays each local commit
individually. If upstream changed a file that was touched in commits 2 and 5 of
7 local commits, the user faces two separate conflict resolution rounds. By
squashing first, there is at most one conflict resolution step, regardless of
how many local commits existed. This is critical for DAAF's target audience,
many of whom are not experienced git users.

**Tradeoff:** Individual commit messages are lost (combined into one summary
message). The backup branch preserves the original history if needed.

**When users should choose merge vs. rebase:**
- **Merge** preserves full local commit history and is safer for users
  unfamiliar with rebase. It creates a merge commit but does not rewrite history.
- **Rebase** produces a cleaner linear history and is preferable when local
  changes are small customizations (a modified skill, an adjusted template) that
  the user wants to keep tidy on top of upstream.

### Conflict Resolution

The script's approach to conflicts is uniform across all paths: detect the
failure, print an explanation of what happened, provide exact resolution
commands, provide exact rollback commands, and exit with code 1. The script
never attempts automatic conflict resolution.

For each conflict scenario, the exit message includes:
- What "conflict" means in plain language
- How to identify conflict markers (`<<<<<<<` / `>>>>>>>`)
- Commands to finish resolution (`git add` + `git commit` or `git rebase --continue`)
- Commands to undo everything (`git merge --abort` or `git rebase --abort`, then `git reset --hard {backup_branch}`)
- Stash recovery commands if changes were stashed

### Dockerfile Change Detection and Rebuild

After a successful update, `print_completion()` diffs the old and new HEAD
against `Dockerfile` and `docker-compose.yml`:

```bash
git diff --name-only "${old_head}..${new_head}" -- Dockerfile docker-compose.yml
```

If either file changed, the script prints:
1. Which files changed
2. The exact `docker cp` commands to copy them to the host build directory
3. The exact `docker compose up -d --build` command to rebuild

This detection is advisory, not automated, because of the container-host
boundary (see Section 1). The rebuild must happen on the host.

---

## 4. Design Decisions and Tradeoffs

### Why git clone instead of zip download

The primary motivation is the update story. With a git clone:
- `git pull` provides incremental updates (only changed files transfer)
- `git diff` shows exactly what changed
- `git merge` surfaces conflicts explicitly instead of silently overwriting
- `git stash` preserves local edits across updates
- `git log` provides full change history

With a zip download, every update is a full re-download and destructive
overwrite. There is no mechanism to detect, preserve, or merge local edits.

### Why tar.gz backup before updates

DAAF targets researchers who may not be proficient with git. If an update goes
wrong and the git state becomes confusing, having a simple archive file that can
be extracted to restore everything provides a safety net that does not require
git knowledge to use. The archive can also be copied off the container to the
host filesystem, providing a backup that survives even container deletion.

### Why squash-then-rebase as an option

Standard multi-commit rebase can produce multiple conflict resolution rounds --
one per commit that touches a conflicting file. For users with many small local
commits (framework tweaks accumulated over time), this creates a frustrating
experience. Squashing to a single commit guarantees at most one conflict
resolution step.

The tradeoff (loss of individual commit messages) is acceptable because:
- The backup branch preserves the original history
- Local customization commits are typically small tweaks, not complex features
  with meaningful individual commit messages
- A single "Local DAAF customizations" commit is often more useful in the log
  than a series of minor edits

### Why rebuild detection is advisory, not automated

The update script runs inside the container. Docker Compose reads the Dockerfile
from the host filesystem. These are different filesystems separated by the
container boundary. The script cannot:
- Write to the host build directory
- Invoke `docker compose build` from inside the container
- Restart its own container

Therefore, it prints exact commands and leaves execution to the user. This is
an inherent limitation of the volume-based architecture, not a design choice
that could be easily changed.

### Why interactive prompts for safe operations but advisory-only for complex ones

The script automates operations where the outcome is predictable and reversible
(fetch, stash, pull on clean state). It uses interactive prompts for operations
where the user must choose between meaningfully different strategies (merge vs.
rebase). It exits with advisory instructions for situations where:
- The script cannot determine user intent (detached HEAD)
- The operation requires host-side action (rebuild)
- The operation has workflow implications beyond the update (fork remote setup)

This graduated approach keeps the common case (clean pull) fast while ensuring
complex cases get human judgment.

### The decision NOT to include a `curl | bash` warning

The install scripts are downloaded via `curl -fsSL ... | bash` (macOS/Linux) and
`irm ... | iex` (Windows). This pattern is standard practice for developer tools
(Homebrew, Rust/rustup, nvm, Claude Code itself). The scripts download from
known GitHub URLs (`raw.githubusercontent.com/DAAF-Contribution-Community/daaf/main/...`)
pointing to a specific repository and branch. Adding warnings about this pattern
would create friction for the primary audience without meaningfully improving
security for users who would not read or understand such warnings.

---

## 5. Future Considerations

### Dev Containers Integration

A `.devcontainer/devcontainer.json` configuration could enable VS Code and
GitHub Codespaces integration, allowing users to open DAAF in a development
container directly from the repository. Initial scoping identified this as
feasible but orthogonal to the current CLI-focused workflow. The main benefit
would be for contributors who want IDE integration; the main risk is maintaining
a parallel configuration path. Findings from initial investigation are available
if this work is prioritized.

### `.dockerignore` for Build Performance

The current architecture sidesteps `.dockerignore` concerns because the build
context is only 3 files (~7 KB). However, if the architecture ever changes to
include more files in the build context (e.g., baking framework files into the
image), a `.dockerignore` would become important to prevent sending the entire
repository (including `research/` data files) to the Docker daemon as build
context.

### `local_overrides/` Directory for User Customizations

A dedicated directory for user customizations that are excluded from git tracking
(via `.gitignore`) could provide a clean separation between upstream framework
files and local modifications. This would eliminate the merge/rebase complexity
for common customizations like modified skills or adjusted templates. The
tradeoff is increased framework complexity (override resolution logic in agents)
and the risk of override files drifting out of sync with the files they modify.

### Automating the Dockerfile Copy-Back Step

The manual `docker cp` step for Dockerfile changes is the most common source of
user confusion in the update flow. Potential approaches:

- A host-side companion script that wraps `docker cp` + `docker compose build`
- Mounting the host build directory as a secondary volume for write-back
- Baking a version-check mechanism into the container startup that compares
  volume Dockerfile against image metadata

Each approach adds complexity and has its own failure modes. The current
advisory approach is simple and reliable, even if it requires an extra manual
step. This is worth revisiting if user feedback indicates the copy-back step
is a significant friction point.
