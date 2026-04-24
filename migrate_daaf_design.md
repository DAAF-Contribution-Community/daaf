# Migration Script Design Document: `migrate_daaf.sh`

**Author:** DAAF Framework Development
**Date:** 2026-04-24
**Status:** Draft for Review
**Script:** `/daaf/migrate_daaf.sh` (846 lines, bash)

---

## 1. Problem Statement

DAAF's `minor_revisions_v202` branch introduces a comprehensive suite of host-side operations scripts (`update_daaf.sh`, `backup_daaf.sh`, `rebuild_daaf.sh`, `run_daaf.sh`, `view_logs.sh`) that automate the update, backup, and daily-use lifecycle. Users on the current `main` branch have **none** of these scripts and cannot use them without a one-time migration.

### The Chicken-and-Egg Problem

Three compounding gaps prevent users from simply running `update_daaf.sh`:

| Gap | What users on `main` have | What `update_daaf.sh` requires |
|-----|---------------------------|-------------------------------|
| **No host scripts** | Zero operations scripts in their host directory | `update_daaf.sh` must exist on the host to run |
| **No git remote** (v2.0.0+ only) | `entrypoint.sh` created a local-only `git init` repo with no remote | `update_daaf.sh` does `git fetch origin` which requires a configured remote |
| **Unrelated git history** (v2.0.0+ only) | The local `git init` commit shares no common ancestor with upstream | `git merge`/`git pull` refuses to merge unrelated histories |

### Why Not Just Re-Install?

A fresh re-install (`install.sh`) would destroy:
- **Git audit trail** — DAAF agents commit every script version, plan update, and data transformation during research sessions. These commits form the reproducibility audit trail.
- **Framework customizations** — Users may have edited `CLAUDE.md`, modified skills, tweaked agent definitions, or adjusted templates.
- **Research files** — While `research/` could be manually preserved, the process is error-prone and the git history linking research changes to framework state would be lost.

The migration script preserves all of these.

---

## 2. Installation Eras

DAAF has been installed three different ways across its release history:

### Era 1: v1.0.0 (`git clone` based)

- **Install method:** `git clone https://github.com/DAAF-Contribution-Community/daaf.git` on the host, then `docker run busybox cp -a /source/. /dest/` to copy everything (including `.git/`) into the Docker volume.
- **Git state in container:** Full repository with complete history and `origin` remote pointing to GitHub.
- **entrypoint.sh:** Did NOT exist at this version — the real `.git/` from the clone was preserved.
- **docker-compose.yml:** Lacked the `name: daaf` field, so the Compose project name was derived from the directory name (typically `daaf` from the clone).
- **Migration difficulty:** Easy — just download host scripts. `update_daaf.sh` works immediately because the git repo already has a remote and real history.

### Era 2: v2.0.0 and v2.0.1 (ZIP download based)

- **Install method:** Download ZIP from GitHub → extract → `docker run busybox cp` → `docker compose up`. The Dockerfile's ENTRYPOINT ran `scripts/entrypoint.sh` on first container start.
- **entrypoint.sh behavior:**
  ```bash
  git init /daaf
  git -C /daaf branch -m main
  git -C /daaf config user.email "daaf@local"
  git -C /daaf config user.name "DAAF Container"
  git -C /daaf add -A
  git -C /daaf commit -m "Initial commit: DAAF framework"
  ```
- **Git state in container:** Local-only repo with a single "Initial commit" that has NO connection to upstream history. No remote configured. Subsequent DAAF agent commits build on this orphan root.
- **docker-compose.yml:** Has `name: daaf`, so container name is always `daaf-daaf-docker-1`.
- **Migration difficulty:** Medium — requires adding a remote, grafting local history onto upstream, and fixing file permissions.

### Era 3: Post-v2.0.1 `main` commits (4 commits after v2.0.1 tag)

- Same as Era 2. The entrypoint.sh was still active on `main` up to the current HEAD.

### Note: `entrypoint.sh` Is Idempotent

A concern raised during review: could `entrypoint.sh` re-run when the migration script starts the container (step 4), potentially re-initializing the git repo? The answer is **no** — `entrypoint.sh` guards all its operations with `if [ ! -d "/daaf/.git" ]`. Since the git repo already exists from the original first-boot, the entrypoint does nothing on subsequent starts. This is safe.

### Structural Constants Across All Eras

- **Docker volume name:** `daaf_daaf-data` — hardcoded in all installation instructions across all versions. Safe to rely on.
- **Volume mount point:** `/daaf` — consistent across all versions.
- **Container name:** `daaf-daaf-docker-1` for v2.0.0+ (explicit `name: daaf`). May vary for v1.0.0 if user renamed their directory. Must be discovered dynamically.

---

## 3. Core Technical Approach: History Grafting

### The Problem With Unrelated Histories

The `entrypoint.sh`-created repo has a root commit ("Initial commit: DAAF framework") that shares no ancestor with any commit in the upstream GitHub repository. Git operations that require a common ancestor — `merge`, `pull`, `rebase` — will refuse to operate on these unrelated histories.

### The Solution: `git replace --graft`

`git replace --graft <commit> <new-parent>` tells git to treat `<commit>` as if its parent is `<new-parent>`. This is:
- **Non-destructive** — the original commit object is unchanged; a "replace ref" is created alongside it
- **Transparent** — all git commands (log, merge, pull, diff) honor replace refs automatically
- **Local-only** — replace refs are not pushed to remotes, which is fine since this repo is local-only

After grafting the local initial commit onto the matching upstream commit:

```
upstream:  ... → B → C → D → E  (origin/main)
                  ↘
local:             A → L1 → L2 → L3  (HEAD)
```

Where A is the entrypoint.sh commit grafted onto B (the matching upstream commit), and L1-L3 are audit trail commits from DAAF agents. All local commits are preserved.

### Finding the Matching Upstream Commit

The local initial commit's file tree is an exact copy of some specific upstream commit (whichever version the user downloaded as a ZIP). We identify it by comparing **blob hashes** — the SHA-1 fingerprints of file contents.

**Why blob comparison, not tree comparison:** Git tree hashes encode both file content AND file permissions (mode bits). GitHub's ZIP downloads lose executable bits on most extraction tools (macOS Archive Utility, Windows Explorer). When `entrypoint.sh` runs `git add -A` on files with lost executable bits, the tree hash differs from upstream even though the file contents are identical. Blob hashes depend only on content, making them immune to this problem.

**Matching procedure:**
1. Extract the initial local commit's blob fingerprint: sorted list of `(blob_hash, filepath)` pairs
2. Try known targets first (tags v2.0.1, v2.0.0, v1.0.0, then origin/main HEAD) — fast, covers most users
3. If no exact match, iterate through ALL commits on origin/main (newest first, since recent installs are more likely)
4. Accept exact match immediately; track best fuzzy match (highest blob overlap)
5. If no exact match, accept fuzzy match at ≥95% overlap
6. If still no match, fall back to grafting onto the latest tag with a warning

**Performance:** The full search runs inside a single `docker exec` call to avoid per-invocation overhead. Inside the container, each commit check involves `git ls-tree -r` + `sort` + `diff`, taking ~0.1s. For 323 commits: ~30-60 seconds total.

### Post-Graft: Verification

After grafting, the script verifies the graft works by running `git merge-base HEAD origin/main`. If a common ancestor is found, the graft is confirmed functional. If not, a warning is displayed with re-run instructions.

### Post-Graft: Permission Normalization

After grafting, we normalize file permissions to prevent spurious diffs on future merges. For each file that is `100755` in the upstream tree but `100644` locally (due to ZIP extraction), we run `git update-index --chmod=+x`. These index changes are committed directly — the script does NOT use `git add -A`, which would risk staging unrelated uncommitted changes (e.g., modified research files or framework edits). The `update-index` calls already modify the git index, so a plain `git commit` captures exactly the permission fixes.

---

## 4. Script Architecture

### Execution Environment

- Runs on the **host machine** (macOS or Linux), not inside the container
- Reaches into the container via `docker exec` for git operations
- Designed to be curl-pipeable: `curl -fsSL https://raw.githubusercontent.com/.../migrate_daaf.sh | bash`
- All interactive prompts are guarded by `[ -t 0 ]` (skipped when piped)

### Flow Diagram

```
┌─────────────────────────────────────────┐
│  1. PREFLIGHT                           │
│  Docker running? Volume exists?         │
│  Determine host directory               │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│  2. DOWNLOAD HOST SCRIPTS               │
│  curl 5 utility scripts from GitHub raw │
│  Update docker-compose.yml if v1.0.0    │
│  chmod +x all .sh files                 │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│  3. BACKUP                              │
│  Calls backup_daaf.sh (full volume)     │
│  Always runs — not optional             │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│  4. START CONTAINER                     │
│  Dynamic container discovery via volume │
│  filter. Start if stopped, compose up   │
│  if no container exists.                │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│  5. DETECT ERA                          │
│  Check for git remote in container      │
│  Remote exists? → Era 1 (easy path)     │
│  No remote? → Era 2 (graft path)       │
└──────────┬───────────────┬──────────────┘
           │               │
    ┌──────▼──────┐  ┌─────▼──────────────┐
    │  6a. ERA 1  │  │  6b. ERA 2          │
    │  git fetch  │  │  Add remote         │
    │  Set track  │  │  Fetch full history │
    │  Done       │  │  Blob-match commit  │
    └──────┬──────┘  │  Graft history      │
           │         │  Fix permissions     │
           │         │  Set tracking        │
           │         └─────┬───────────────┘
           │               │
    ┌──────▼───────────────▼──────────────┐
    │  7. OFFER UPDATE                    │
    │  Prompt to run update_daaf.sh now   │
    │  (skipped in non-interactive mode)  │
    └──────────────────┬──────────────────┘
                       │
    ┌──────────────────▼──────────────────┐
    │  8. SUCCESS MESSAGE                 │
    │  Summary of what was done           │
    │  Instructions for going forward     │
    └─────────────────────────────────────┘
```

### Helper Functions

| Function | Purpose |
|----------|---------|
| `prompt_choice` | Interactive y/n prompt with input validation |
| `container_git` | Run git inside the container, suppress stderr, strip `\r` |
| `container_git_verbose` | Same but allows stderr through (for progress output) |
| `container_exec` | Run arbitrary command inside the container |
| `cleanup_on_error` | ERR trap: reassuring message (backup-aware — only claims backup exists if step 3 completed), re-run instructions |

### Idempotency Design

Every mutation is guarded by a pre-check:

| Mutation | Guard |
|----------|-------|
| Add remote | Check if `origin` remote already exists |
| Graft history | Check if initial commit already has a parent (graft already applied) |
| Fix permissions | Check each file's current mode before updating |
| Download scripts | Always overwrite (safe — they're framework scripts, not user data) |
| Backup | Always runs (safe — creates timestamped copy, never overwrites) |

The script is safe to run multiple times. A second run detects the completed migration and skips the heavy steps.

---

## 5. Edge Cases and Failure Modes

### Edge Case Matrix

| Scenario | Detection | Handling |
|----------|-----------|---------|
| **v1.0.0, standard directory** | Remote exists, points to DAAF repo | Era 1: fetch + track |
| **v1.0.0, renamed directory** | Remote exists, container name differs | Dynamic container discovery handles it |
| **v1.0.0, remote points elsewhere** | Remote exists, URL doesn't match DAAF repo | Warn but proceed (user may have forked) |
| **v2.0.0 exact tag install** | Blob match hits v2.0.0 tag | Graft onto v2.0.0 |
| **v2.0.1 exact tag install** | Blob match hits v2.0.1 tag | Graft onto v2.0.1 |
| **Inter-tag install** | No tag match, full search finds exact commit | Graft onto exact commit |
| **Modified files before first boot** | No exact match, fuzzy match ≥95% | Graft onto best match with note |
| **Heavily modified installation** | No match ≥95% | Fall back to latest tag with warning |
| **No .git directory at all** | `git rev-list` fails | Error: suggest fresh install |
| **Container not running** | `docker ps` finds stopped container | `docker start` + readiness wait |
| **No container exists** | Volume exists but no container | `docker compose up -d` with downloaded compose file |
| **Docker not running** | `docker info` fails | Error with clear instructions |
| **No internet** | curl downloads fail | Error before any mutations |
| **Previous partial migration** | Remote exists but no graft yet | Skips remote add, proceeds with graft |
| **Migration already complete** | Remote exists AND graft in place | Skips both, goes to success |
| **User on non-main branch** | Container's HEAD is on a custom branch | Sets tracking for `main` branch specifically (not the current branch); user's custom branch is unaffected |

### Failure Recovery

All failures are recoverable:

1. **Pre-backup failures** (steps 1-2): No mutations have occurred. Re-run safely.
2. **Post-backup, pre-graft failures** (steps 3-5): Backup exists. Re-run safely (idempotent guards).
3. **Graft failure** (step 6b): The `git replace --graft` is atomic — it either succeeds or doesn't. Re-run safely.
4. **Permission fix failure**: Partial permission fixes are harmless. Re-run completes the remainder.

The ERR trap provides reassuring messaging, notes that a backup exists, and instructs the user to re-run.

---

## 6. Security Considerations

| Concern | Mitigation |
|---------|-----------|
| **Downloaded scripts could be tampered with** | Scripts are downloaded from the official GitHub repository over HTTPS. This is the same trust model as the original installation. |
| **Container exec runs as container user** | All `docker exec` commands run as the container's `appuser` (UID 1000), not root. The container has `cap_drop: ALL` and `no-new-privileges`. |
| **Backup contains all user data** | Backup is created in the host directory (user-controlled). No data leaves the local machine. |
| **Git replace refs** | Replace refs are local-only and not transmitted on push/fetch. They affect only the local repository's view of history. |

---

## 7. What the Migration Does NOT Do

- **Does not modify research files** — `research/` is never touched
- **Does not delete any git commits** — old commits become orphaned (reachable via reflog for ~90 days) but are never deleted
- **Does not modify the Docker image** — only git operations inside the volume. The container image is unchanged unless the user opts into a rebuild.
- **Does not push anything** — all operations are local
- **Does not modify framework files** — only git metadata (remote, replace refs, index modes). Actual file contents on disk are unchanged.
- **Does not handle Windows** — a separate `migrate_daaf.ps1` is needed for PowerShell users

---

## 7a. Rollback Instructions

If the migration needs to be undone:

```bash
# Remove the graft (restore orphan history):
docker exec daaf-daaf-docker-1 git -C /daaf replace -d <initial-commit-sha>

# Remove the remote:
docker exec daaf-daaf-docker-1 git -C /daaf remote remove origin

# Full restore from backup (replaces entire volume):
docker run --rm \
  -v "/path/to/backup:/source:ro" \
  -v "daaf_daaf-data:/dest" \
  busybox sh -c 'rm -rf /dest/* /dest/.* 2>/dev/null; cp -a /source/. /dest/'
```

The graft can also be recreated by re-running `migrate_daaf.sh` (it's idempotent).

## 7b. Expected `git fsck` Warnings

After migration, `git fsck` may report warnings related to the grafted root commit. This is because `git fsck` ignores replace refs and checks the original commit objects. These warnings are **expected and harmless** — they do not indicate corruption. All normal git operations (log, merge, pull, diff) honor the replace refs and work correctly.

---

## 8. Testing Strategy

### Manual Test Scenarios

| Test | Setup | Expected Result |
|------|-------|----------------|
| **Era 1 fresh** | `git clone` → busybox cp → compose up | Detects remote, fetches, downloads scripts, done |
| **Era 2 v2.0.1** | ZIP of v2.0.1 → busybox cp → compose up (entrypoint runs) | Blob matches v2.0.1 tag, grafts, fixes perms |
| **Era 2 v2.0.0** | ZIP of v2.0.0 → same | Blob matches v2.0.0 tag |
| **Era 2 inter-tag** | ZIP of a commit between v2.0.0 and v2.0.1 → same | Full search finds exact commit |
| **Era 2 with research** | Same as v2.0.1 but user has done research sessions (extra commits) | Initial commit still matches; subsequent commits preserved |
| **Era 2 with framework edits** | Same but user modified CLAUDE.md | Graft preserves the edit as a local commit |
| **Idempotent re-run** | Run migrate_daaf.sh twice | Second run detects completed migration, skips heavy steps |
| **No container** | Volume exists, container deleted | Creates container via compose, then migrates |
| **Offline** | No internet after volume check | Fails at download step with clear message |

### Post-Migration Validation

After migration, the following should be true:
1. `git remote -v` shows `origin` pointing to `https://github.com/DAAF-Contribution-Community/daaf.git`
2. `git log --oneline` shows local commits with upstream history accessible via the graft
3. `git fetch origin` succeeds
4. `bash update_daaf.sh` runs successfully (may or may not find updates depending on branch state)
5. All files in `research/` are unchanged
6. `git diff HEAD` shows no unexpected changes (permissions normalized, no content changes)

---

## 9. Future Considerations

- **`migrate_daaf.ps1`**: PowerShell equivalent for Windows users. Same logic, different shell syntax. Should be created before the branch merges to `main`.
- **install.sh integration**: Consider having `install.sh` detect old-style installations and suggest running `migrate_daaf.sh` instead of refusing. Currently `install.sh` says "use update_daaf.sh" which doesn't exist for these users.
- **Deprecation timeline**: Once the migration has been available for a reasonable period (e.g., 2-3 releases), the migration logic could be folded into `update_daaf.sh` itself as a one-time bootstrap step, and `migrate_daaf.sh` could be retired.
- **Pre-v1.0.0 installations**: Theoretically possible but extremely unlikely. The migration script does not specifically handle these (the Docker setup was fundamentally different — bind mounts instead of named volumes). Users in this situation would need a fresh install.
