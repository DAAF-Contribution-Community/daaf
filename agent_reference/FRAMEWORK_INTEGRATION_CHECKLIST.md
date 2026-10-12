# Framework Integration Checklist

> **Purpose:** Comprehensive registration-point checklists for every DAAF framework component type. Used by the `framework-engineer` agent and the orchestrator during Framework Development mode to ensure no wiring point is missed.
>
> **Canonical authority:** This document is the single authoritative integration checklist for all component types. Per-skill supplementary checklists (e.g., in `agent-authoring` or `MODE_TEMPLATE.md`) provide walkthrough detail and contextual guidance but should not be used as the primary checklist. When discrepancies exist, this document governs.
>
> **When to read:** Every framework-engineer invocation. Also useful for manual framework modifications.

---

## How to Use This Document

Each section covers one component type (Skill, Agent, Mode, Reference File, Hook, Host-Facing Script, Provider Shim, Scholarly Search Backend). Items are marked:
- **[M]** = Mandatory (must be completed for every instance)
- **[C]** = Conditional (required only when the stated condition applies)

After completing each item, note the status: Done, Skipped (with reason), or N/A.

---

## 1. Adding or Modifying a Skill

### New Skill Checklist

| # | Item | Req | File | Section / Location |
|---|------|-----|------|--------------------|
| S1 | Create skill directory `.claude/skills/{skill-name}/` | [M] | — | Directory name must exactly match `name` field in frontmatter |
| S2 | Create `SKILL.md` with valid YAML frontmatter (`name`, `description`) | [M] | `.claude/skills/{skill-name}/SKILL.md` | Frontmatter: `name` (lowercase-hyphen, 1-64 chars), `description` (1-1024 chars, what + when, third person) |
| S3 | Add `metadata` dict if applicable (`audience`, `domain`) | [C] | `.claude/skills/{skill-name}/SKILL.md` | Controlled vocabulary per `skill-authoring` skill |
| S4 | Create `references/` subdirectory with reference files | [C] | `.claude/skills/{skill-name}/references/` | Flat structure (no nesting). For data source skills: 3x+ SKILL.md lines |
| S5 | For data source skills: follow `DATA_SOURCE_SKILL_TEMPLATE.md` (13 sections) | [C] | `.claude/skills/{skill-name}/SKILL.md` | Mandatory sections in exact order; Truth Hierarchy blockquote; provenance metadata |
| S6 | Verify SKILL.md body is under 500 lines / 5000 words | [M] | `.claude/skills/{skill-name}/SKILL.md` | Extract overflow to `references/` |
| S7 | Verify description triggers appropriately (no undertriggering or overtriggering) | [M] | `.claude/skills/{skill-name}/SKILL.md` | Test with realistic prompts |
| S8 | If skill should be preloaded by an agent, add to that agent's `skills:` frontmatter | [C] | `.claude/agents/{agent-name}.md` | YAML frontmatter `skills` field |
| S9 | If skill is used in a specific pipeline stage, add to `full-pipeline-mode.md` > Skill-to-Stage Mapping | [C] | `.claude/skills/daaf-orchestrator/references/full-pipeline-mode.md` | Skill-to-Stage Mapping table |
| S10 | If skill is used in WORKFLOW_PHASE invocation templates, add reference there | [C] | `agent_reference/WORKFLOW_PHASE*.md` | Stage-specific invocation template |

### Modifying an Existing Skill

| # | Item | Req | File | What to Check |
|---|------|-----|------|----|
| SM1 | Read the full SKILL.md before editing | [M] | Target skill | Understand structure and content flow |
| SM2 | If changing the description, verify triggering behavior hasn't degraded | [M] | Target skill | Test with prompts that should and should not trigger |
| SM3 | If adding references, verify `references/` stays flat (no nested dirs) | [C] | Target skill | Directory structure |
| SM4 | If changing the name, rename the directory to match | [M] | Target skill | Directory name = frontmatter `name` |
| SM5 | Check if any agents preload this skill (search for skill name in `skills:` fields) | [C] | `.claude/agents/*.md` | Grep for skill name in agent frontmatter |
| SM6 | If changing routing or decision-tree content, find and synchronize files that restate the routing | [C] | `.claude/agents/*.md`, `.claude/skills/daaf-orchestrator/references/*.md` | Grep for library/skill names enumerated in the changed routing (duplicated summaries drift silently) |

---

## 2. Adding or Modifying an Agent

### New Agent Checklist

> For the complete section-by-section walkthrough, invoke the `agent-authoring` skill and read `references/integration-checklist.md`. This checklist covers registration points only.

| # | Item | Req | File | Section / Location |
|---|------|-----|------|--------------------|
| A1 | Create agent file following AGENT_TEMPLATE.md (all 12 sections) | [M] | `.claude/agents/{agent-name}.md` | 400-700 lines target |
| A1b | Assign `model:` frontmatter tier (`opus` or `sonnet`) per orchestrator SKILL.md Model Selection guidance | [M] | `.claude/agents/{agent-name}.md` | YAML frontmatter `model` field; two-tier policy (haiku excluded) — see `.claude/skills/daaf-orchestrator/SKILL.md` > "Model Selection for Subagent Dispatch" |
| A1c | Include an EXPLICIT `tools:` list that never contains `Agent` or `Task` | [M] | `.claude/agents/{agent-name}.md` | YAML frontmatter `tools` field. Omitting the field inherits ALL tools (including `Agent`), which would let the agent nest dispatches — always enumerate tools explicitly and exclude `Agent`/`Task`. This upholds the dispatch-authority invariant (all dispatch authority belongs to the orchestrator; see `agent_reference/BOUNDARIES.md` § Process Violations). Second enforcement layer: the `block-nested-dispatch.sh` PreToolUse hook denies any subagent-originated dispatch, covering the generic built-in types that have no DAAF-authored `tools:` list. |
| A2 | Verify Core Distinction table differentiates from closest neighbors | [M] | `.claude/agents/{agent-name}.md` | Section 2: Identity |
| A3 | Add to Agent Index table | [M] | `.claude/agents/README.md` | Agent Index table |
| A4 | Add "When to Use" subsection | [M] | `.claude/agents/README.md` | When to Use section |
| A5 | Add to Agent Coordination Matrix (producer/consumer rows) | [M] | `.claude/agents/README.md` | Agent Coordination Matrix table |
| A6 | Add to Commonly Confused Pairs if applicable | [C] | `.claude/agents/README.md` | Commonly Confused Pairs table |
| A7 | Update Orchestration Flow diagram if agent participates in pipeline | [C] | `.claude/agents/README.md` | Orchestration Flow ASCII diagram |
| A8 | Add to Subagent Type Selection table in orchestrator SKILL.md | [C] | `.claude/skills/daaf-orchestrator/SKILL.md` | Named Agents table |
| A9 | Add to `full-pipeline-mode.md` Core Workflow tables if stage-specific | [C] | `.claude/skills/daaf-orchestrator/references/full-pipeline-mode.md` | Core Workflow, Handoffs, Stage Gates tables |
| A10 | Add invocation template to appropriate WORKFLOW_PHASE file | [C] | `agent_reference/WORKFLOW_PHASE*.md` | Stage-specific section |
| A11 | Add to BOUNDARIES.md if agent has unique boundary considerations | [C] | `agent_reference/BOUNDARIES.md` | Appropriate section |
| A12 | Add to ERROR_RECOVERY.md if agent has error recovery patterns | [C] | `agent_reference/ERROR_RECOVERY.md` | Agent-specific section or routing table |
| A13 | Register per-agent hooks in frontmatter if coding agent | [C] | `.claude/agents/{agent-name}.md` | YAML `hooks` field (e.g., enforce-file-first.sh) |
| A14 | Update root `README.md` Agent Ecosystem table and agent count (distinct from `.claude/agents/README.md`) | [M] | `README.md` (project root) | Agent Ecosystem section |
| A15 | Update CLAUDE.md if agent affects documented workflows | [C] | `CLAUDE.md` | Relevant section |
| A16 | Update `user_reference/` docs if agent is user-visible | [C] | `user_reference/*.md` | Relevant descriptions |

### Modifying an Existing Agent

| # | Item | Req | File | What to Check |
|---|------|-----|------|----|
| AM1 | Read the full agent file before editing | [M] | Target agent | Understand structure |
| AM2 | Verify changes don't overlap with another agent's responsibilities | [M] | `.claude/agents/README.md` | Commonly Confused Pairs |
| AM3 | If changing the agent's scope, update README.md When to Use + Coordination Matrix | [C] | `.claude/agents/README.md` | Affected sections |
| AM4 | If changing inputs/outputs, update consumer/producer entries | [C] | `.claude/agents/README.md` | Agent Coordination Matrix |
| AM5 | If changing the name, update all references (SKILL.md, WORKFLOW_PHASE, etc.) | [M] | Multiple files | Grep for old name |
| AM6 | If the agent's stage coverage changes, sweep ALL stage-mapping tables and update each — agent stage columns are a recurring, easy-to-miss registration surface | [C] | `.claude/agents/README.md`, `agent_reference/WORKFLOW_PHASE*.md`, `.claude/skills/daaf-orchestrator/references/*-mode.md` | Agent Index "Stage(s)" column + Coordination Matrix, workflow-phase stage tables, and mode-reference stage/agent tables |

---

## 3. Adding or Modifying a Mode

### New Mode Checklist

| # | Item | Req | File | Section / Location |
|---|------|-----|------|--------------------|
| M1 | Create mode reference file following MODE_TEMPLATE.md | [M] | `.claude/skills/daaf-orchestrator/references/{mode-name}-mode.md` | Required sections: description, User Orientation, Workflow, Subagent Invocation, Output Format, Boundaries, Escalation Triggers |
| M1a | If the mode dispatches subagents, include the wave barrier discipline note in the Subagent Invocation section (mid-wave completion notifications are status-only; no synthesis, gates, or checkpoints until the whole wave returns), citing `SKILL.md` § Subagent Coordination > "Wave Barrier Discipline (Async Dispatch)" | [C] | `.claude/skills/daaf-orchestrator/references/{mode-name}-mode.md` | Subagent Invocation section |
| M2 | Update YAML frontmatter description (mode count) | [M] | `.claude/skills/daaf-orchestrator/SKILL.md` | Frontmatter `description` field |
| M3 | Update Expanded Orientation bullet (mode count + description) | [M] | `.claude/skills/daaf-orchestrator/SKILL.md` | Welcome Preamble > Expanded Orientation |
| M4 | Update Engagement Mode Classification count word | [M] | `.claude/skills/daaf-orchestrator/SKILL.md` | "classify it into one of N engagement modes" |
| M5 | Add branch to Mode Decision Framework tree | [M] | `.claude/skills/daaf-orchestrator/SKILL.md` | Mode Decision Framework code block |
| M6 | Add row to Mode Summary Table | [M] | `.claude/skills/daaf-orchestrator/SKILL.md` | Mode Summary Table |
| M7 | Add confirmation template | [M] | `.claude/skills/daaf-orchestrator/SKILL.md` | Confirmation Templates by Mode |
| M8 | Add escalation paths (from AND to new mode) | [M] | `.claude/skills/daaf-orchestrator/SKILL.md` | Mode Escalation Paths table |
| M9 | Add row to Reference File Index | [M] | `.claude/skills/daaf-orchestrator/SKILL.md` | What to Load Next > Reference File Index. **Note:** `{mode-name}-mode.md` files register *here* (the orchestrator SKILL.md Reference File Index), NOT in CLAUDE.md's Reference Files table — that table lists `agent_reference/` docs (plus `.claude/agents/README.md`), not mode files |
| M10 | Add branch to Documentation Loading Decision Tree | [M] | `.claude/skills/daaf-orchestrator/SKILL.md` | Documentation Loading Decision Tree code block |
| M11 | Add mode-specific boundaries | [M] | `agent_reference/BOUNDARIES.md` | Mode-Specific Boundaries section |
| M12 | Update README.md mode count and table | [M] | `README.md` | Engagement Modes section |
| M13 | Add mode subsection to user_reference/02 | [M] | `user_reference/02_understanding_daaf.md` | The N Engagement Modes section (header, TOC, intro, subsection, transition table) |
| M14 | Add mode-specific AI disclosure guidance | [M] | `agent_reference/AI_DISCLOSURE_REFERENCE.md` | Mode-Specific Disclosure Guidance section |
| M15 | Update session-recovery.md with recovery pattern | [M] | `.claude/skills/daaf-orchestrator/references/session-recovery.md` | Purpose section + conditional recovery steps |
| M16 | Add mode-specific error recovery (if non-trivial) | [C] | `agent_reference/ERROR_RECOVERY.md` | Mode-specific recovery section |
| M17 | Create state template (if different from Full Pipeline) | [C] | `agent_reference/STATE_TEMPLATE_{MODE}.md` | New file + add to CLAUDE.md Reference Files table |
| M18 | Update CONTRIBUTING.md if mode affects contribution workflow | [C] | `CONTRIBUTING.md` | Relevant tier sections |
| M19 | Add FAQ entry if mode is likely to generate user questions | [C] | `user_reference/07_faq_technical.md` | New Q&A entry |
| M20 | Add progressive testing level entry | [C] | `user_reference/02_understanding_daaf.md` | Progressive testing levels section |
| M21 | Update user_reference/04 if mode affects extension model | [C] | `user_reference/04_extending_daaf.md` | Relevant section |

### Modifying an Existing Mode

| # | Item | Req | File | What to Check |
|---|------|-----|------|----|
| MM1 | Read the full mode reference file before editing | [M] | Target mode | Understand workflow and structure |
| MM2 | If changing trigger conditions, verify no overlap with other modes | [M] | `.claude/skills/daaf-orchestrator/SKILL.md` | Mode Decision Framework tree |
| MM3 | If changing outputs, update Mode Summary Table | [C] | `.claude/skills/daaf-orchestrator/SKILL.md` | Mode Summary Table |
| MM4 | If changing escalation paths, update both directions | [C] | `.claude/skills/daaf-orchestrator/SKILL.md` | Mode Escalation Paths |
| MM5 | If changing boundaries, update BOUNDARIES.md | [C] | `agent_reference/BOUNDARIES.md` | Mode-Specific Boundaries |
| MM6 | If changing user-facing description, update user_reference/02 | [C] | `user_reference/02_understanding_daaf.md` | Mode subsection |

---

## 4. Adding or Modifying a Reference File

### New Reference File Checklist

| # | Item | Req | File | Section / Location |
|---|------|-----|------|--------------------|
| R1 | Create file in `agent_reference/` with clear purpose statement | [M] | `agent_reference/{file-name}.md` | First paragraph states purpose and audience |
| R2 | Add to CLAUDE.md Reference Files table | [M] | `CLAUDE.md` | Reference Files table |
| R3 | Add trigger conditions ("When to Read") in all referencing documents | [M] | Various | Agent Section 12, WORKFLOW_PHASE files, orchestrator SKILL.md |
| R4 | Wire into Documentation Loading Decision Tree if loaded by orchestrator | [C] | `.claude/skills/daaf-orchestrator/SKILL.md` | Documentation Loading Decision Tree |
| R5 | Wire into agent Section 12 if used by specific agents | [C] | `.claude/agents/{agent-name}.md` | Section 12: References table |
| R6 | Wire into WORKFLOW_PHASE file if stage-specific | [C] | `agent_reference/WORKFLOW_PHASE*.md` | Progressive loading notes |

### Modifying an Existing Reference File

| # | Item | Req | File | What to Check |
|---|------|-----|------|----|
| RM1 | Read the full file before editing | [M] | Target file | Understand structure |
| RM2 | Check which agents and skills reference this file | [M] | Multiple | Grep for filename |
| RM3 | If changing the file's scope or purpose, update CLAUDE.md table description | [C] | `CLAUDE.md` | Reference Files table |
| RM4 | If renaming, update all references across codebase | [M] | Multiple | Grep for old name |

---

## 5. Adding or Modifying a Hook

> **Note:** Hook files in `.claude/hooks/` are protected by deny rules. This checklist documents the registration points for awareness. Actual hook creation requires human intervention or explicit permission override.

### New Hook Checklist

| # | Item | Req | File | Section / Location |
|---|------|-----|------|--------------------|
| H1 | Create hook script in `.claude/hooks/` | [M] | `.claude/hooks/{hook-name}.sh` | Failure posture must match the hook's role: fail-closed (ERR trap → exit 2) for safety gates; fail-open (`exit 0` on all paths) for observability/reminder hooks (see HM2) |
| H1b | Set executable permissions and ensure Git tracks the executable bit | [M] | `.claude/hooks/{hook-name}.sh` | Run `chmod +x <file>`, then `git update-index --chmod=+x <file>`. Verify with `git ls-files -s <file>` — mode must be `100755`, not `100644`. |
| H2 | Register in settings.json (project-wide) OR agent frontmatter (per-agent) | [M] | `.claude/settings.json` or `.claude/agents/{agent}.md` | `hooks` section with event type + matcher |
| H3 | Add to the Defense-in-Depth Architecture table in `agent_reference/BOUNDARIES.md` (CLAUDE.md § Defense-in-Depth Architecture carries only a summary pointer) | [M] | `agent_reference/BOUNDARIES.md` | § Defense-in-Depth Architecture (Enforcement Layers) table |
| H4 | Add to hooks registration summary in framework hierarchy docs | [C] | Documentation | Hook event type table |
| H5 | Test with both allow and block scenarios | [M] | — | Verify exit code 0 (allow) and exit code 2 (block) |

> **Applies to all `.sh` files, not just hooks.** Item H1b (executable permissions) applies whenever any `.sh` file is created or modified in the repository — including utility scripts in `scripts/` (e.g., `run_with_capture.sh`, `collect_session_logs.sh`). Shell scripts that are not executable will fail silently when invoked with `./script.sh` syntax and will be stored incorrectly in Git history. Always run `chmod +x` and `git update-index --chmod=+x` for every `.sh` file.

> **Cache placement principle (for hooks that persist state):** match a cache's storage to the lifetime of the fact it caches. `/tmp` holds **session-runtime facts** (active model, context window, throttle timestamps) — the container-rebuild wipe is free cache invalidation for them. Coordination state that must survive rebuilds — **transcript-lifetime facts**, e.g. the orchestrator-loaded flag (`orchestrator-loaded-<session_id>`) — lives in `~/.claude/daaf-state/` (claude-config volume, same lifetime as the session transcripts). Rationale and precedent: `.claude/hooks/remind-orchestrator.sh` header and `research/2026-07-15_FrameworkDev_ResumeReminderFix/`.

### Modifying an Existing Hook

> Precedent: the 2026-07-15 orchestrator-flag relocation (`research/2026-07-15_FrameworkDev_ResumeReminderFix/`), where these steps were derived by analogy from the New Hook Checklist.

| # | Item | Req | File | What to Check |
|---|------|-----|------|----|
| HM1 | Read the full hook script before editing; identify its event type, matcher(s), input fields consumed, and exit-code contract | [M] | Target hook | Header comment vs. actual behavior |
| HM2 | Preserve the hook's failure posture — fail-closed (ERR trap → block) for safety gates, fail-open (`exit 0` always) for observability/reminder hooks — unless changing that posture is the point of the edit | [M] | Target hook | ERR trap and exit codes before vs. after |
| HM3 | Draft-test-deploy: `.claude/hooks/` is deny-protected, so author the revision as a draft in a session workspace, test it by piping synthetic JSON event payloads to the draft, then have the user copy it into place (`cp` onto the existing file preserves the executable bit) | [M] | Session workspace → `.claude/hooks/{hook-name}.sh` | Draft passes ShellCheck + functional probes before deployment |
| HM4 | Verify deployment: deployed file byte-identical to the tested draft (`diff` empty) and Git mode still `100755` (`git ls-files -s`) | [M] | `.claude/hooks/{hook-name}.sh` | Empty diff; mode column |
| HM5 | Confirm registrations still match the hook's behavior (event type + every matcher, in `settings.json` and any agent frontmatter) — or update them if the edit changes when the hook should fire | [M] | `.claude/settings.json`, `.claude/agents/*.md` | Grep for the hook name |
| HM6 | If the edit changes paths, patterns, or state locations the hook reads/writes (cache files, flag files, log paths), sweep live framework surfaces for the old value and update — including the hook's Defense-in-Depth Architecture row in `agent_reference/BOUNDARIES.md` if listed there. Archival research documents and session logs are NOT updated | [C] | `agent_reference/BOUNDARIES.md`, live docs | Grep old fragment; zero hits outside archival locations |
| HM7 | If regression tests cover the hook (`tests/bash/*.bats`), update and re-run them | [C] | `tests/bash/` | Grep for the hook name in `tests/` |

### Retiring a Hook

> Deregistration is the inverse of the New Hook Checklist, but with pitfalls of its own — a hook may be registered under multiple matchers, and its name typically appears in documentation surfaces beyond `settings.json`. Precedent: the 2026-07-02 retirement of `enforce-foreground-agents.sh`, where these steps had to be derived by inverting H1-H5.

| # | Item | Req | File | Section / Location |
|---|------|-----|------|--------------------|
| HR1 | Remove the hook's registration from ALL `settings.json` hook chains — check every event type and every matcher (a hook may be registered under multiple matchers, e.g., both `Task` and `Agent`). Validate JSON afterward (`jq empty .claude/settings.json`) | [M] | `.claude/settings.json` | `hooks` section, all event types |
| HR2 | Remove any agent-frontmatter registrations (`hooks:` blocks) | [C] | `.claude/agents/*.md` | YAML frontmatter `hooks` field — grep for the hook name |
| HR3 | Sweep live framework surfaces for references to the hook name and update or remove each — CLAUDE.md, the Defense-in-Depth Architecture table in `agent_reference/BOUNDARIES.md` (if listed), README.md, skills, agent definitions, `agent_reference/`, `user_reference/`, `scripts/`. Archival research documents are NOT updated — corrections belong in new dated documents | [M] | Multiple | Grep for the hook name across live surfaces |
| HR4 | Decide the script file's fate. Deletion requires human action (`.claude/hooks/` is deny-protected); until deleted, the script is unregistered-but-present. Git history preserves it either way | [M] | `.claude/hooks/{hook-name}.sh` | Note the decision; flag deletion for human execution |
| HR5 | Record the retirement rationale (why the hook is no longer needed) in a dated document in an appropriate research workspace, including what would need re-registration if the retirement were ever reversed | [M] | `research/{workspace}/` | New dated document |
| HR6 | Verify: a repo-wide grep for the hook name returns hits only in archival locations and (if retained) the inert script itself; `git diff` on `settings.json` shows only the intended deregistration | [M] | — | Final verification |

---

## 6. Adding or Modifying a Host-Facing Script

> **Scope:** Files under `scripts/host/` — the launchers and lifecycle tools that run on the **user's own machine** (macOS/Linux/Windows), not inside the container. These have distribution and portability registration points that in-container scripts do not.

### New Host-Facing Script Checklist

| # | Item | Req | File | Section / Location |
|---|------|-----|------|--------------------|
| HS1 | Create the `.sh` script under `scripts/host/` following Bash 3.2 + BSD portability standards | [M] | `scripts/host/{name}.sh` | See `shell-scripting` skill > `bash-standards.md` "Host-Script Portability" — host scripts run on macOS `/bin/bash` 3.2 |
| HS2 | Create the matching `.ps1` cross-platform pair (or document why none is needed) | [M] | `scripts/host/{name}.ps1` | The hygiene-checks CI job enforces `.sh`/`.ps1` pair parity for `scripts/host/` |
| HS3 | Set executable bit and record it in Git | [M] | `scripts/host/{name}.sh` | `chmod +x`, then `git update-index --chmod=+x`; verify `git ls-files -s` shows `100755` (see § 5 note) |
| HS4 | Add the script to the **fresh-install download list** in `install.sh` | [M] | `scripts/host/install.sh` | The `curl … -o` download block that fetches host scripts via GitHub raw. A file missing here will not exist for fresh installs |
| HS5 | Add the script to the fresh-install download list in `install.ps1` | [M] | `scripts/host/install.ps1` | The PowerShell equivalent download block (`.ps1` files, plus `daaf.sh`/`daaf_lib.sh` which Windows runs via Git Bash/WSL) |
| HS6 | **Updater sync — usually no action needed.** The updater self-derives its host-script list from the post-update repository state, so newly added `scripts/host/` files matching the platform filter (`*.sh` on Unix, `*.ps1` on Windows) are picked up automatically. **Exception:** files of any *other* type (e.g., `.txt` like `README.txt` and `environment_settings_example.txt`) must be explicitly added to the platform filter in **both** updaters or they will be silently excluded from sync | [M] | `scripts/host/update_daaf.sh`, `update_daaf.ps1` | Do **not** hand-edit a per-file sync allowlist for scripts — the updater intentionally reads the file list from the new repo state (not a hardcoded list in the old script), which is what heals the historical chicken-and-egg where a hardcoded allowlist in the *running* (old) updater could never deliver a file it did not already know about. The platform *filter* (file-type rules) is the one part that still requires a hand edit, and only for novel file types |
| HS7 | Add `DAAF_NESTED` handling and a `DAAF_DRY_RUN` smoke path so CI can exercise it | [M] | `scripts/host/{name}.sh` / `.ps1` | Required by the `daaf-conventions` linter (DAAF_NESTED) and consumed by the smoke-tests / bats-bash32 CI jobs |
| HS8 | Add the script to the smoke-test lists in `ci-scripts.yml` (bash, pwsh 7, PS 5.1, and the `bash:3.2` job) | [M] | `.github/workflows/ci-scripts.yml` | Smoke-tests job + bats-bash32 job. Interactive menu-loop scripts must be driven with input on stdin and any state their code paths require |
| HS9 | Create a `.bats` (and Pester `.Tests.ps1`) unit test | [C] | `tests/bash/{name}.bats`, `tests/powershell/{name}.Tests.ps1` | Required if the script has non-trivial logic beyond a thin launcher |
| HS10 | Add to the migration fetch list if it is a bootstrap tool users may lack | [C] | `scripts/host/migrate_daaf.sh` / `.ps1` | Only for one-time migration tooling; most scripts are covered by install + updater self-sync |
| HS11 | Document user-facing scripts in the quickstart Quick Reference table | [C] | `user_reference/01_installation_and_quickstart.md` | Quick Reference table + relevant workflow section, if the script is meant to be run directly by users |
| HS12 | If the script (or an accompanying config change) introduces persistent state that must survive container rebuilds, verify a named volume (or bind mount) is registered in `docker-compose.yml` AND the mount point is documented | [C] | `docker-compose.yml` | `volumes:` section + the doc surface describing the mount. State written to an unmounted container path is silently lost on rebuild; a compose-volume addition without a checklist row was nearly missed (precedent: the `~/.claude/daaf-state/` claude-config volume; see the § 5 cache-placement principle note) |

> **Why the install lists are hand-maintained but the updater is not:** Fresh installs download host scripts before any repo exists on the host, so `install.sh`/`install.ps1` must name each file explicitly (there is nothing to derive a list from yet). The updater, by contrast, runs *after* pulling the new repo state into the container, so it can and does enumerate the current `scripts/host/` contents itself — making a hardcoded updater list both redundant and a recurring source of "new file silently never delivered" bugs. Register new host scripts in the two install lists; leave the updater alone.

### Modifying an Existing Host-Facing Script

| # | Item | Req | File | What to Check |
|---|------|-----|------|----|
| HSM1 | Read the full script (and its `.ps1` pair) before editing | [M] | Target script(s) | Keep the pair behaviorally in sync |
| HSM2 | Re-run the portability gate after editing | [M] | — | `bash tests/lint/check-daaf-conventions.sh` — no Bash-4.x-only constructs in `scripts/host/*.sh` |
| HSM3 | If renaming, update both install download lists and the CI smoke lists | [M] | `install.sh`, `install.ps1`, `ci-scripts.yml` | The updater self-heals renames on next update, but installs and CI reference the name directly |
| HSM4 | Keep `.sh` and `.ps1` behavior aligned | [M] | Both pair members | Parity is enforced for existence by CI, but not for behavior — that is on the author |
| HSM5 | If the script has a `DAAF_DRY_RUN` arm, verify no write sites are reachable under dry-run after the edit | [M] | Target script(s) | Dry-run must create nothing on disk (see the 2026-07-14 root-stub incident, `research/2026-07-15_FrameworkDev_CwdLeakRootStubs/`): sweep the changed script for `touch`/`mkdir`/`cp`/`mv`/redirects/`chmod` (`New-Item`/`Set-Content`/`Copy-Item`/`Move-Item`/`Out-File` in `.ps1`) and confirm each is gated to the real-run branch; `scripts/check_workspace_invariants.sh` Invariant 2 and the "dry-run creates nothing" regression tests in `tests/bash/{migrate_daaf,install}.bats` are the mechanical backstops |

---

## 7. Adding or Modifying the Provider Shim

> **Scope:** The in-container provider shim under `scripts/provider_shim/` — the shim service (`anthropic_openai_shim.py`, an ASGI app translating the Anthropic Messages API to the OpenAI Responses API), its lifecycle manager (`start_shim.sh`), and companion CLIs (e.g., `probe_context_ceiling.py`). The shim is core infrastructure for the OpenAI/ChatGPT provider route: a persistent, contract-bearing daemon whose `/health` schema, `SHIM_*` env vars, and `SHIM_BACKEND_MODE` lane values are consumed by hooks, statuslines, the deploy-smoke harness, and the DAAFBench provenance layer. It is neither a hook (§ 5, `.claude/hooks/`) nor a host-facing script (§ 6, `scripts/host/`), so it carries its own registration points.

> **Precedent:** These items derive from the shim's development history across six sessions (v1.0.0 → v1.2.10) — e.g., `research/2026-07-09_FrameworkDev_OpenAI_Provider/`, `research/2026-07-10_FrameworkDev_ShimToolSanitization/`, and `research/2026-07-16_FrameworkDev_ShimWireTolerance/`. The gap they close was recorded as a follow-up learning signal in `ShimWireTolerance/SESSION_NOTES.md`.

### New Shim Capability or Backend Lane Checklist

| # | Item | Req | File | Section / Location |
|---|------|-----|------|--------------------|
| P1 | Implement the capability or backend lane in the shim and bump `SHIM_VERSION` | [M] | `scripts/provider_shim/anthropic_openai_shim.py` | `SHIM_VERSION` constant; for a new lane, the supported-mode set `_BACKEND_MODE_SUPPORTED` |
| P2 | Document every new/changed shim env var (`SHIM_*`, `CODEX_HOME`, `OPENAI_API_KEY`/`SHIM_BACKEND_API_KEY`) on all three lockstep surfaces, and register it in route detection's env-key allowlist | [M] | `scripts/provider_shim/anthropic_openai_shim.py` (Config header), `scripts/provider_shim/start_shim.sh` (header), `scripts/host/environment_settings_example.txt` (Option F), `scripts/deploy_smoke/route_detection.py` (env-key allowlist / `note_var` calls) | The shim Config block, the manager header, and the user-facing setup guide must stay identical — an env var added to one but not the others drifts silently. Route detection must recognize every env var the shim reads |
| P3 | If the `/health` schema gains, renames, or drops a field — or the shim's usage/token reporting shape changes — reconcile every consumer | [C] | `benchmarks/harness/route_provenance.py` (`PROVENANCE_ALLOWLIST`, `_validate_health_payload()`), `scripts/deploy_smoke/smoke_probes.py` (`probe_shim_health()`), `benchmarks/harness/executor.py` (`*_not_exposed_by_deployed_shim` token-accounting caveat tags) | `/health` is the shim's serialization contract; `PROVENANCE_ALLOWLIST` is a fail-closed boundary and the validator/probe assert the field set. `executor.py`'s caveat tags assert which usage/token fields the deployed shim does *not* expose — they go silently stale if a shim change starts exposing them |
| P4 | If `SHIM_BACKEND_MODE` gains a value, propagate the new lane to route classification | [C] | `scripts/deploy_smoke/route_detection.py` (`SHIM_ROUTES`), `benchmarks/harness/route_provenance.py` (lane checks) | Route detection and DAAFBench provenance both branch on the supported-mode set |
| P5 | If the new lane needs context-window/threshold gating, update the lane-gate condition in all three consumers | [C] | `.claude/hooks/context-reporter.sh`, `.claude/scripts/context-bar.sh`, `.claude/scripts/subagent-bar.sh` | The condition `[[ "${DAAF_PROVIDER_SHIM:-}" == "openai" && "${SHIM_BACKEND_MODE:-}" == "chatgpt" ]]` is duplicated verbatim in all three (verified by grep; no shared helper) — change all three in lockstep. These are user-only surfaces (deny-protected hook / settings-registered statuslines) — flag for the user rather than shell-editing |
| P6 | Restart the running daemon after any code change and confirm the new version via `GET /health` | [M] | `scripts/provider_shim/start_shim.sh` (`--stop`/`--start`/`--status`), `GET http://127.0.0.1:4141/health` | "Stale-process trap": editing the source does not update the live daemon — verify the `version` field in `/health` matches the new `SHIM_VERSION` |
| P7 | Add or extend the test suites and re-run them | [M] | `tests/provider_shim/` (`test_reasoning_formatting.py`, `test_stream_hardening.py`, `_loopback_harness.py`), `benchmarks/tests/` (`test_chatgpt_route.py`, `test_probe_model_route.py`, `test_artifacts_and_preflight.py`), `tests/bash/` (the three consumer `.bats` suites) | Cover the new behavior in the shim suites and the DAAFBench route/provenance suites; the `.bats` suites cover the lane-gating consumers |
| P8 | Rebase any loopback mock fixture on captured live-wire evidence, not documentation-derived shapes; never let a self-test reimplement the logic it tests | [M] | `tests/provider_shim/_loopback_harness.py`, `scripts/provider_shim/probe_context_ceiling.py` (`--self-test`) | Fixtures encoding doc-derived event shapes never seen on the live wire give false coverage (the v1.2.7 outage lesson) — reconcile mock vs. live before trusting a fixture. Likewise, a self-test must drive the real code path (e.g., via injection): a reimplemented check passes even when the real path is broken (the `probe_context_ceiling.py --self-test` precedent) |
| P9 | Scrub any new upstream-controlled field before it enters a log line | [M] | `scripts/provider_shim/anthropic_openai_shim.py` (`_scrub_log_token()`, `_scrub_and_trim_body()`) | Log-injection recurred when new fields bypassed the control-char scrub (`_SCRUB_CTRL_RE`); any field sourced from the backend/upstream stream must pass one of the scrub helpers |
| P10 | Sync the user- and contributor-facing doc surfaces where behavior claims change | [C] | `scripts/host/environment_settings_example.txt`, `user_reference/07_faq_technical.md`, `user_reference/01_installation_and_quickstart.md`, `README.md`, `CONTRIBUTING.md`, `CLAUDE.md` | Update only where a behavior claim actually changed; `CLAUDE.md` shim passages are gated — flag for user approval rather than editing unilaterally |
| P11 | Run the `daaf-deploy-smoke-testing` skill's live smoke test after the change | [M] | `daaf-deploy-smoke-testing` skill (Tier 0 shim `/health` preflight + Tier 1 live round-trip) | Per `CONTRIBUTING.md` (deploy-smoke guidance), a provider-shim change requires a deploy-smoke run against the active route |
| P12 | A companion CLI under `scripts/provider_shim/` that owns its own non-`SHIM_*` env-var family (e.g., `render_codex_config.py` and `DAAF_CODEX_CONFIG_<N>`): keep its template section, user docs, and tests in lockstep | [C] | the CLI's header docstring, `scripts/host/environment_settings_example.txt` (its own section, e.g. §4.6), `user_reference/01_installation_and_quickstart.md`, `user_reference/07_faq_technical.md`, its `tests/provider_shim/test_*.py` plus the `start_shim.sh` wiring cases in `tests/bash/start_shim.bats` | P2's tri-surface rule covers `SHIM_*` only, so a separate family drifts unless swept on its own: accepted name pattern, value rules, refusal/secret-guard wording, and how users check the outcome (e.g. `start_shim.sh --status`) must read the same everywhere. Users edit only `environment_settings.txt`, so the template text is the primary contract |

> **Duplicated-constant caution:** Facts the shim asserts — context-window ceilings above all (e.g., the 919,000-token ChatGPT-subscription cap measured 2026-09-05) — are restated across ~10 doc surfaces plus multiple benchmark/test sites with no single source. When a shim change alters such a fact, sweep every sibling consumer, not just the one literal you came in to change. CC1/CC7 catch count words; this catches duplicated *facts*.

### Modifying Existing Shim Behavior

| # | Item | Req | File | What to Check |
|---|------|-----|------|----|
| PM1 | Read the shim source region you are changing, its Config header, and the `/health` contract before editing | [M] | `scripts/provider_shim/anthropic_openai_shim.py` | Header comment / changelog vs. actual behavior; the shim is 4000+ lines — read generously around the target region |
| PM2 | If the edit changes the `/health` schema, reconcile the three consumers (allowlist, validator, smoke probe) | [C] | `benchmarks/harness/route_provenance.py`, `scripts/deploy_smoke/smoke_probes.py` | Same reconciliation as P3 |
| PM3 | If the edit adds/changes shim env vars (`SHIM_*`, `CODEX_HOME`, key vars) or `SHIM_BACKEND_MODE` values, update the tri-surface docs and route detection/provenance | [C] | env template, `start_shim.sh`, `route_detection.py`, `route_provenance.py` | Same lockstep as P2/P4 |
| PM4 | Bump `SHIM_VERSION` and restart the daemon; confirm via `GET /health` | [M] | `anthropic_openai_shim.py`, `start_shim.sh` | Stale-process trap (see P6) — a code edit without a restart leaves the old daemon serving |
| PM5 | Re-run the shim, benchmarks, and `.bats` suites; rebase touched loopback fixtures on live-wire evidence | [M] | `tests/provider_shim/`, `benchmarks/tests/`, `tests/bash/` | See P7/P8 |
| PM6 | Retiring a backend lane: remove the value from every surface that enumerates it, and record the rationale | [C] | `_BACKEND_MODE_SUPPORTED`, `SHIM_ROUTES`, `route_provenance.py` lane checks, the three lane-gate consumers, tri-surface docs; `research/{workspace}/` | Inverse of P4/P5; a lane value typically appears in more places than the one that motivated the change — grep the value repo-wide. Record why in a dated research doc (per the § 5 HR5 precedent) |

---

## 8. Adding or Modifying a Scholarly Search Backend

> **Scope:** A backend adapter for DAAF's scholarly-search CLI, `scripts/scholar_search.sh` (core `scripts/scholar_search.py`, one adapter per source in `scripts/scholar_backends/`): for example PubMed/Europe PMC, CORE, SSRN/RePEc, or an institutional discovery API. The core owns everything that protects the audit trail (guards, artifacts, the MANIFEST, fusion, the shared rate gate); an adapter only builds requests through the core's `Http` object, maps responses to the common record schema and parses cost headers, and never writes files. The step-by-step procedure (intake, docs research, scaffold, live smoke, register, review) is `.claude/skills/scholarly-search/references/adding-a-backend.md`, with skeletons in `references/_BACKEND_TEMPLATE.md`; this section lists the registration points only and does not restate that procedure. A source with only a website search page is **not** a backend: it goes through `web_fetch.sh` under the `web-retrieval` skill (`adding-a-backend.md` § "First decision: API or website?").

> **Precedent:** Build session S1 (2026-10-02 to 2026-10-06) shipped five adapters (openalex, semantic_scholar, eric, crossref, unpaywall); S2 (2026-10-11) added scite and elicit as the first real run of this workflow, including the POST path, a timed-429 policy, split storage for `retractions`, and paid asynchronous reports. Design source and session record: `research/2026-10-02_FrameworkDev_ScholarlySearch/` (spec §5.5; SESSION_NOTES "S2 Paid backends").

### New Scholarly Search Backend Checklist

| # | Item | Req | File | Section / Location |
|---|------|-----|------|--------------------|
| SB1 | Record the intake with the user and decide the license class: what the source covers and which coverage gap it closes, access model (keyless / free key / paid, per-call cost), storage and redistribution terms, rate limits. Class `open`, `cc-by-nc` or `restricted` (anything that bars storing or sharing → `restricted`) | [M] | `research/{workspace}/SESSION_NOTES.md` | `adding-a-backend.md` Step 1. A website-only source stops here and is routed to `web_fetch.sh` |
| SB2 | Have a search-agent fetch the vendor's API docs **and** terms with `web_fetch.sh` into the workspace, so every claim in the reference file traces to a stored page | [M] | `research/{workspace}/web_fetches/` | `adding-a-backend.md` Step 2. framework-engineer does no agent-reading web retrieval (`framework-development-mode.md` § Pre-Authoring Research Offer) |
| SB3 | Create the adapter from `_BACKEND_TEMPLATE.md` § 1: the `§§ CONTRACT` block (`NAME`, `LABEL`, `KEY_ENV`, `REQUIRED_KEY`, `LICENSE_CLASS`, `RATE_LIMIT` lanes from the documented limit plus margin, `CAPABILITIES`, `DEFAULT_IN_FIND = False`, `FIND_LEGS` when `search` is declared, `ATTRIBUTION`), keys in headers only, requests only through `Http`, failures only as `BackendError` | [M] | `scripts/scholar_backends/<name>.py` | `unpaywall.py` is the worked example; exception kinds and their exit codes: `adding-a-backend.md` § "What an adapter may raise" |
| SB4 | Register the module in the `ADAPTERS` tuple and confirm the import-time registry validation passes: `registry.validate_adapter(<module>)` returns `[]`; `NAME`, `KEY_ENV`, every rate lane and every `FIND_LEGS` name are unique across adapters | [M] | `scripts/scholar_backends/__init__.py` | Any contract violation stops every `scholar_search` command with exit 1 before a request. `find --skip` / `retractions --skip` choices are generated from the registry, so `--help` is the live check |
| SB5 | If the vendor's 429 means a timed block ("blocked for N seconds"), declare `RETRY_POLICY = {"penalize_429_s": N}` | [C] | `scripts/scholar_backends/<name>.py` | Validated at import. The 429 is never retried; the lane pauses N s for every process and the call fails `busy` (exit 12). Precedent: `elicit.py` (300 s) |
| SB6 | If the backend sends POST, or starts paid or asynchronous work: a POST makes one attempt unless `idempotent=True`, which is reserved for reads sent as POST (Scite batch tallies) and never declared on a create; a non-idempotent POST follows no redirect: every 3xx (301/302/303/307/308) is refused and logged with its real status and chain (tool 1.5.0; 1.4.0 refused only 307/308); paid or async work needs **core** support following the Elicit pattern (spend flag refused before any request; a `creating` checkpoint row BEFORE the create; any create answer that does not prove nothing started (only a refusal before sending, or a 429 or another 4xx as the **direct** answer to the POST, does) is an **uncertain** create, including an accepted answer without a valid session ID and any refused redirect; checkpoint row before the first poll; capped poll loop that keeps polling unknown statuses; exit 13 plus a re-attach subcommand that never creates; duplicate-create guard with a documented close path for uncertain creates) and a `TOOL_VERSION` bump (tool 1.5.0) | [C] | `scripts/scholar_backends/<name>.py`, `scripts/scholar_search.py` (§ ELICIT) | `adding-a-backend.md` § "What an adapter may raise" (POST; "Paid or asynchronous work"). Reuse Elicit's shape; do not generalize the machinery before a second async backend exists |
| SB7 | Run the cheapest live call through the CLI (`DAAF_FETCH_CONTEXT` set, DEST inside the workspace; free calls only, plus a paid call (any call that can draw on a plan's usage or credits, listed in `framework-engineer.md` § Never Do) only when the dispatch carries the user's approval for that named call) and save the trimmed real response as the test fixture with a `_fixture_source` field; for a `restricted` source, keep the live response's exact shape but replace every value with an invented one (`_fixture_source` "SYNTHETIC; shape from live response <MANIFEST row, date>; values invented") | [M] | `tests/python/fixtures/scholar_search/<name>_*.json`; smoke DEST under `research/{workspace}/` | Live-wire evidence, not doc-derived shapes (the § 7 P8 lesson). If a live call is impossible, label the fixture DOC-DERIVED and log it as an open issue. The repository is published (user decision 2026-10-12), so vendor content from a restricted source never enters a fixture or a published doc; measured behavior (limits, vocabularies, field presence, sizes, timings) may |
| SB8 | Confirm the license class routes storage correctly: a `restricted` backend writes every artifact to `lit_search/restricted/`; a `restricted` adapter with the `retraction` capability returns facts only (status, notice DOIs and dates), because `retractions` keeps its digest in the open folder and splits only the raw response into `restricted/` (`SPLIT_STORAGE_COMMANDS`). Fixtures from a restricted source are synthetic (SB7) | [M] | `scripts/scholar_backends/<name>.py`; the smoke DEST | Probe: grep the open folder for vendor-only fields (none expected). S2 precedent: the user decided (2026-10-12) to replace the Scite and Elicit fixtures with synthetic ones |
| SB9 | Write the per-backend reference from `_BACKEND_TEMPLATE.md` § 2: Auth · Endpoints used · Cost and limits · Measured behavior (dated) · Storage and ToS · Exit mapping · Minimal smoke test | [M] | `.claude/skills/scholarly-search/references/<name>.md` | Claims trace to SB2's stored pages or SB7's MANIFEST rows |
| SB10 | Register in the skill: a Backends table row; a "Which command?" branch and an Other commands row for any new subcommand; a References table row; the frontmatter `description` when users will ask for the backend or its capability by name (re-check triggering per § 1 SM2; ≤ 1,024 characters) | [M] | `.claude/skills/scholarly-search/SKILL.md` | Keep the body under ~500 lines (§ 1 S6); detail belongs in the reference file |
| SB11 | Add the backend's row to the licensing matrix (storage, redistribution, attribution, status) | [M] | `.claude/skills/scholarly-search/references/licensing.md` | Matrix table |
| SB12 | Add a dated "Measured behavior: <Backend> (YYYY-MM-DD)" entry, newest first, plus its evidence-location line | [M] | `.claude/skills/scholarly-search/references/api-notes.md` | Say how each fact was observed (MANIFEST path, row) |
| SB13 | Keyed source: add a commented `#<NAME>_API_KEY=` line with the get-key URL, plan or cost, and what the key enables; then run `bats /daaf/tests/bash/environment_settings_example.bats` and quote the result | [C] | `scripts/host/environment_settings_example.txt` | Section [5], "Scholarly literature search" block. The file feeds two strict line parsers: keep the `#KEY=value` form, no inline comments |
| SB14 | Keyed source: add a row to the API-key table, worded consistently with SB13 | [C] | `user_reference/01_installation_and_quickstart.md` | § "Set up data source API keys" table |
| SB15 | Add unit tests: the mapper against SB7's fixture; `test_registry_contract` covers the new adapter automatically; keyed → extend `test_backends_never_prints_key_values`; mocked tests for POST/async paths and the exit mapping. Run the suite file-first: a captured script under the session's `scripts/` that runs `python3 -m unittest discover -s /daaf/tests/python -p "test_scholar_search.py"` in a subprocess and prints its result line, executed with `run_with_capture.sh` (never typed interactively); quote the result line. The protected core regions (spend gate, duplicate guard, restricted routing / split storage, secret-guard call sites, POST retry/redirect rules, `verify` rules) change only when the dispatch names them, and their tests stay green | [M] | `tests/python/test_scholar_search.py` | `_BACKEND_TEMPLATE.md` § 3 |
| SB16 | If the adapter joins an existing multi-backend command (`retraction` → `retractions`; `search` with `DEFAULT_IN_FIND = True` → `find`), that command's MANIFEST row, stdout and digest change shape: bump `TOOL_VERSION`, grep for scripts and docs that parse the command, and tell their owners | [C] | `scripts/scholar_search.py`; consumers such as `.claude/skills/academic-manuscript/assets/verify_citations_template.py` and `references/quarto-manuscript-build.md` § 16 | Grep the subcommand name across `.claude/` and `agent_reference/`. S2 precedent: Scite joined `retractions` by default (`--skip scite` restores the previous sources), relayed to the Manuscript Preparation session |
| SB17 | Run the standard Framework Development review pass (3-angle for a new backend) and the workspace-invariants lint before Checkpoint 2 | [M] | — | `framework-development-mode.md` § Phase 4; `bash scripts/check_workspace_invariants.sh` |

### Modifying an Existing Scholarly Search Backend

| # | Item | Req | File | What to Check |
|---|------|-----|------|----|
| SBM1 | Read the adapter, its reference file and the core section it relies on before editing | [M] | `scripts/scholar_backends/<name>.py`, `references/<name>.md`, `scripts/scholar_search.py` | `§§` markers index the core; read generously around the target |
| SBM2 | When vendor behavior changed, re-measure through the CLI (so the probe leaves a MANIFEST row), then update the dated `api-notes.md` entry, the reference's Measured behavior, and the adapter's header comment or constant together | [M] | `api-notes.md`, `references/<name>.md`, adapter | Truth hierarchy: live measurement > vendor docs > the skill |
| SBM3 | If the contract changes (`NAME`, `KEY_ENV`, rate lanes, `FIND_LEGS`, capabilities, license class), re-run the registry validation and unit tests; a renamed `NAME` or `FIND_LEGS` leg changes the `--skip` / `--backends` choices, so grep for scripts and docs that pass the old value | [C] | `scripts/scholar_backends/__init__.py`, `tests/python/test_scholar_search.py` | Exit 1 at import means a contract violation; quote the test result |
| SBM4 | If the key, the plan it needs or what it enables changes, update the env template line (re-run its bats), the `user_reference/01` row and the SKILL.md Backends row in lockstep | [C] | `scripts/host/environment_settings_example.txt`, `user_reference/01_installation_and_quickstart.md`, `SKILL.md` | The three wordings agree |
| SBM5 | If the license class or storage routing changes, update `licensing.md`, the SKILL.md licensing section, the reference's Storage and ToS, and the restricted-routing tests | [C] | `references/licensing.md`, `SKILL.md`, `references/<name>.md`, tests | Grep the open folder of a fresh smoke run for vendor-only fields |
| SBM6 | If a command's output shape changes (row fields, stdout lines, digest), bump `TOOL_VERSION` and sweep or notify the consumers, as in SB16 | [C] | `scripts/scholar_search.py`; consumers | Grep the subcommand name |
| SBM7 | Retiring a backend: remove it from `ADAPTERS`, the SKILL.md tables, `licensing.md`, and the env template and `user_reference/01` rows; keep its `api-notes.md` history (a dated log is not rewritten); record the rationale in a dated research document | [C] | Multiple; `research/{workspace}/` | Inverse of SB4/SB10–SB14 (per the § 5 HR5 precedent); grep the backend name repo-wide afterwards |

---

## 9. Cross-Cutting Consistency Checks

After completing any component checklist above, run these universal verification steps:

| # | Check | How |
|---|-------|-----|
| CC1 | Count words are consistent | Grep for "N engagement modes", "N agents", etc. across all files |
| CC2 | Cross-references resolve | Verify every file path mentioned in any document actually exists |
| CC3 | Table schemas match | New rows have the same columns as existing rows |
| CC4 | Escalation paths are bidirectional | Both "from" and "to" modes acknowledge each path |
| CC5 | Naming conventions are followed | Skill dirs match frontmatter names; agent files are lowercase-hyphenated; mode refs end in `-mode.md` |
| CC6 | No orphaned components | Every new file is referenced by at least one other file |
| CC7 | No stale references | If anything was renamed or removed, old names don't appear elsewhere |
| CC8 | Code examples and prompt templates swept | Extends CC7: the stale-reference sweep must also grep for the old pattern *inside* fenced code blocks, invocation templates, and prompt templates, not just prose. Examples silently teach stale conventions if missed |

### Context-Threshold Profile Modifications

When changing a model-specific context-threshold profile:

- Keep `context-reporter.sh` and `subagent-bar.sh` profile assignments and adjacent comments in lockstep.
- Preserve the separation between profile membership, physical-window mapping, and provider route caps unless the approved change explicitly targets more than the profile.
- Add just-below/at boundary matrices for every changed percentage gate, retain full-window absolute-gate controls, and add a non-default-denominator matrix proving profile-wide behavior.
- Retain negative controls for neighboring models, malformed/future identifiers, unknown models, and any model families intentionally left conservative.
- Synchronize the canonical threshold reference, operational/user documentation, mode references, and every reproduced derived token boundary.
- For protected runtime files, draft in a session workspace, test the drafts through the suites' script-under-test seams, have the user deploy them, then verify byte identity, executable mode, registrations, and post-deployment regressions.
