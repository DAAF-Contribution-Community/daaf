# Hook Message Updates — bash-safety.sh §8 (Docker "user additions block")

**Date:** 2026-07-13
**Related framework change:** Introduction of the Dockerfile **user additions block** (see the `USER ADDITIONS` banner near the end of `/daaf/Dockerfile`, and the threaded guidance in `user_reference/04_extending_daaf.md`, `user_reference/07_faq_technical.md`, `CLAUDE.md`, `agent_reference/BOUNDARIES.md`, `agent_reference/ERROR_RECOVERY.md`, and `framework-development-mode.md`).

## Why this is a staged handoff, not a direct edit

Hook scripts under `.claude/hooks/` are the framework's **root of trust** and are **user-only to modify**. DAAF blocks agents from writing to them (both the `Edit`/`Write` deny rules and the `bash-safety.sh` §7 anti-tampering guard). The framework-engineer agent therefore does **not** edit `bash-safety.sh` — it drafts the proposed change here, and **you (the user) apply it** from a host terminal or via a `!`-prefixed session command (neither is subject to the hooks).

## What to change

The five §8 package-install block messages in `/daaf/.claude/hooks/bash-safety.sh` all point users to "Add the package to the Dockerfile and rebuild (...)". This handoff proposes appending a short clause to each so the guidance also names the **user additions block** as the fast-rebuild default — consistent with every other surface. The messages render inside a blocked-command error, so the additions are kept terse.

Line numbers are those observed on 2026-07-13 (they may drift; match on the message text, which is unique per block).

---

### 1. `pip`/`pipx` install/uninstall/run — line 376

**Current:**
```
    block "Runtime package changes drift from the Dockerfile and vanish on rebuild. Add the package to the Dockerfile and rebuild (exit the container, then run \`bash rebuild_daaf.sh\` from the daaf-docker folder)."
```

**Proposed:**
```
    block "Runtime package changes drift from the Dockerfile and vanish on rebuild. Add the package to the Dockerfile and rebuild (exit the container, then run \`bash rebuild_daaf.sh\` from the daaf-docker folder) — preferably in the user additions block near the end of the Dockerfile for a fast rebuild."
```

---

### 2. `python -m pip` install/uninstall — line 385

**Current:**
```
    block "Runtime package changes (python -m pip) drift from the Dockerfile and vanish on rebuild. Add the package to the Dockerfile and rebuild (exit the container, then run \`bash rebuild_daaf.sh\` from the daaf-docker folder)."
```

**Proposed:**
```
    block "Runtime package changes (python -m pip) drift from the Dockerfile and vanish on rebuild. Add the package to the Dockerfile and rebuild (exit the container, then run \`bash rebuild_daaf.sh\` from the daaf-docker folder) — preferably in the user additions block near the end of the Dockerfile for a fast rebuild."
```

---

### 3. `uv` pip/add/remove/sync/tool — line 392

**Current:**
```
    block "Runtime package changes via uv drift from the Dockerfile and vanish on rebuild. Add the package to the Dockerfile and rebuild (exit the container, then run \`bash rebuild_daaf.sh\` from the daaf-docker folder)."
```

**Proposed:**
```
    block "Runtime package changes via uv drift from the Dockerfile and vanish on rebuild. Add the package to the Dockerfile and rebuild (exit the container, then run \`bash rebuild_daaf.sh\` from the daaf-docker folder) — preferably in the user additions block near the end of the Dockerfile for a fast rebuild."
```

---

### 4. `uv run --with` — line 396

**Current:**
```
    block "\`uv run --with\` implicitly installs the named package into an ephemeral environment (runtime drift). Add the package to the Dockerfile and rebuild (exit the container, then run \`bash rebuild_daaf.sh\` from the daaf-docker folder)."
```

**Proposed:**
```
    block "\`uv run --with\` implicitly installs the named package into an ephemeral environment (runtime drift). Add the package to the Dockerfile and rebuild (exit the container, then run \`bash rebuild_daaf.sh\` from the daaf-docker folder) — preferably in the user additions block near the end of the Dockerfile for a fast rebuild."
```

---

### 5. `uvx`/`easy_install`/`conda` — line 413

**Current:**
```
    block "Runtime package execution/installation (uvx/easy_install/conda) drifts from the Dockerfile. Add the tool to the Dockerfile and rebuild (exit the container, then run \`bash rebuild_daaf.sh\` from the daaf-docker folder)."
```

**Proposed:**
```
    block "Runtime package execution/installation (uvx/easy_install/conda) drifts from the Dockerfile. Add the tool to the Dockerfile and rebuild (exit the container, then run \`bash rebuild_daaf.sh\` from the daaf-docker folder) — preferably in the user additions block near the end of the Dockerfile for a fast rebuild."
```

---

## How to apply (user)

These are the only changes to `bash-safety.sh` in this batch. Apply them from **outside** the agent's blocked path — the browser-based code editor (or any host editor pointed at the Docker volume), or a `!`-prefixed session command. After applying, re-run the safety-hook regression battery to confirm the §8 blocks still fire and nothing else regressed:

```
bash /daaf/scripts/test_safety_hooks.sh
```

(and/or the bats suite: `bats /daaf/tests/bash/`). The message text is not asserted by the block-behavior tests, so these edits should be behavior-preserving — the blocks fire on the same commands, only the guidance clause is longer.
