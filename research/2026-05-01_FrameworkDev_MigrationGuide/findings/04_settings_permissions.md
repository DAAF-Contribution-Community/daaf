# DAAF Settings, Permissions, and Security Configuration — Complete Migration Reference

> **Generated:** 2026-05-01
> **Purpose:** Comprehensive documentation of DAAF's use of Claude Code's settings, permissions, and security systems, sufficient to reconstruct the entire security configuration in another AI coding harness.

---

## 1. settings.json — Six Top-Level Keys

**File:** `/daaf/.claude/settings.json` (228 lines)

The file contains six top-level keys:

| Key | Type | Purpose |
|-----|------|---------|
| `statusLine` | object | Custom TUI status bar — runs `context-bar.sh` to show model, dir, branch, and real-time context utilization |
| `permissions` | object | Contains `allow` (38 entries) and `deny` (35 entries) arrays |
| `env` | object | 7 environment variables for model selection, effort level, and feature toggles |
| `outputStyle` | string | `"Explanatory"` — more detailed response formatting |
| `showThinkingSummaries` | boolean | `true` — shows abbreviated thinking blocks |
| `hooks` | object | Shell script registrations across 5 lifecycle events |

---

## 2. Permission System — Complete Inventory

### 2.1 Allow List (38 patterns) — Auto-approved Operations

Includes:
- **Bash commands:** `marimo run/edit`, `pip list`, `python`/`python3`, `bash`, `ls`, `mkdir`, `git status/diff/log/add`, `cp`, `chmod +x`, `cd`, `head`, `wc -l`, `file`, `find`
- **Bare tools (all invocations):** `Grep`, `Glob`, `Edit`, `Write`, `Skill`, `WebSearch`
- **Subagents:** `Task/Agent(general-purpose)`, `Task/Agent(Plan)`, `Task/Agent(Explore)`, `Task/Agent(search-agent)`

### 2.2 Deny List (35 patterns) — Hard-blocked Operations

Six categories:

1. **Destructive filesystem (2):** `rm -rf *`, `rm -r /*`
2. **Privilege escalation (4):** `sudo`, `su`, `chmod 777`, `chmod u+s`
3. **Container escape (4):** `docker run`, `docker exec`, `mount`, `chroot`
4. **Destructive git (8):** `push --force/-f`, `reset --hard`, `clean -f`, `checkout .`, `restore .`, `branch -D`
5. **Credential protection (13):** Read/Write/Edit for `.env`, `.env.*`, `*.pem`, `*.key`, `credentials*`, `*secret*`, `environment_settings*`
6. **Infrastructure protection (4):** Edit/Write for `.claude/hooks/*` and `.claude/logs/*`

### 2.3 Notable Design Choices

- `Read` is NOT in the allow list — every file read prompts the user (conservative default)
- `WebFetch` is NOT auto-allowed despite `WebSearch` being allowed
- `git commit` and `git push` require user approval every time
- DAAF-specific agent types (e.g., `research-executor`, `code-reviewer`) are NOT pre-allowed — only built-in and search-agent types are
- Infrastructure self-protection: hooks and logs are deny-protected against modification

### 2.4 Three-Tier Matching Logic

- Match `allow` pattern → auto-approved
- Match `deny` pattern → hard-blocked (deny wins over allow)
- Match neither → user prompted
- Pattern syntax: `ToolName(glob_pattern)` — glob wildcards `*` and `**` against the tool's primary argument (command string for Bash, file_path for Read/Write/Edit, subagent_type for Task/Agent)

---

## 3. settings.local.json

Does not exist in DAAF. DAAF intentionally uses only the project-level `settings.json` shared via version control to ensure uniform security across all users.

---

## 4. Agent Permission Modes

14 agents split into two modes:

| Mode | Count | Agents | Effect |
|------|-------|--------|--------|
| `default` | 9 | research-executor, framework-engineer, notebook-assembler, code-reviewer, research-synthesizer, data-planner, data-ingest, report-writer, debugger | Full tool access subject to settings.json |
| `plan` | 5 | source-researcher, search-agent, plan-checker, data-verifier, integration-checker | Read-only — Write/Edit/Bash blocked regardless of settings.json |

`plan` mode is a harder constraint than settings.json — it restricts at the Claude Code runtime level. The `tools` frontmatter field further constrains which specific tools each agent can access.

**Per-agent hook registration:** `enforce-file-first.sh` is registered only in the frontmatter of coding agents (research-executor, code-reviewer, debugger, data-ingest), not globally. This means the orchestrator and read-only agents are exempt.

---

## 5. Hooks System — 12 Scripts Across 5 Events

### 5.1 Security Hooks (fail CLOSED — block on error)

- **`bash-safety.sh`** (PreToolUse, Bash matcher): Regex-based blocking of destructive commands, privilege escalation, pipe-to-shell, file exfiltration, container escape. Provides redundant coverage with deny list using more expressive regex matching.
- **`enforce-file-first.sh`** (PreToolUse, agent-scoped Bash matcher): Blocks direct python execution, requiring `run_with_capture.sh` wrapper for audit trail. Whitelists framework utility scripts.
- **`enforce-explore-model.sh`** (PreToolUse, Task matcher): Blocks `Explore` subagent type (runs on Haiku) — recommends `search-agent` instead.
- **`enforce-foreground-agents.sh`** (PreToolUse, Agent/Task matcher): Blocks `run_in_background: true` agents (cannot prompt for permissions).
- **`deny-claude-code-guide.sh`** (PreToolUse, Agent/Task matcher): Blocks `claude-code-guide` built-in (runs on Haiku).

### 5.2 Observability Hooks (fail OPEN — never block)

- **`context-reporter.sh`** (UserPromptSubmit + PreToolUse): Injects context utilization data with severity levels. Rate-limited to 60-second intervals. Supports subagents via fallback context window cache.
- **`remind-orchestrator.sh`** (UserPromptSubmit): Reminds to load `daaf-orchestrator` skill. On first-ever session, injects transparency onboarding from `first-run-transparency.txt`.
- **`flag-orchestrator-loaded.sh`** (PostToolUse, Skill matcher): Sets flag when daaf-orchestrator loads; stops reminders.
- **`audit-log.sh`** (PostToolUse): Appends JSONL entries to `.claude/logs/audit.jsonl` — timestamp, session, tool, target, DAAF version, model, agent type.
- **`output-scanner.sh`** (PostToolUse): Scans tool output for AWS keys, API tokens (sk-), GitHub PATs, Stripe keys, private key blocks, and long Bearer tokens.
- **`archive-session.sh`** (SessionEnd): Archives transcripts as JSONL + Markdown, including subagent transcripts. Idempotent, supports crash recovery.
- **`recover-session-logs.sh`** (SessionStart): Activity logging + background crash recovery for orphaned sessions.

---

## 6. .claudeignore — 12 Patterns

Prevents Claude Code from indexing credential files: `.env`, `.env.*`, `.env.local`, `.env.production`, `environment_settings.txt`, `environment_settings*.txt`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `**/credentials*`, `**/secrets/`.

Complementary to but independent of permission deny rules — `.claudeignore` prevents discovery while deny rules prevent access.

---

## 7. Pre-commit Hooks — 8 Checks

From `pre-commit-hooks` v5.0.0: `check-added-large-files` (500KB max), `detect-private-key`, `check-merge-conflict`, `check-yaml`, `end-of-file-fixer`, `trailing-whitespace`.

From `shellcheck-py` v0.10.0.1: `shellcheck` (warning+ severity, bash shell).

These are the commit-time safety net.

---

## 8. Environment Variable / Credential Pattern

Secrets stay on the host machine in `environment_settings.txt`, injected by Docker Compose as environment variables. Scripts access via `os.environ[]`. Claude cannot see the file (outside container FS + `.claudeignore` + deny rules).

---

## 9. Defense-in-Depth Architecture — 9 Layers

1. Container isolation (Docker, `cap_drop: ALL`, non-root)
2. File exclusion (`.claudeignore`)
3. Permission system (`settings.json` allow/deny/prompt)
4. Agent permission modes (frontmatter `plan` vs `default`)
5. PreToolUse hooks (active blocking)
6. PostToolUse hooks (audit + secret detection)
7. Session lifecycle hooks (archival + recovery)
8. Pre-commit hooks (commit-time safety)
9. Behavioral guardrails (CLAUDE.md instruction-following)

---

## 10. Status Line Configuration

**Source:** `statusLine` key in settings.json references `.claude/scripts/context-bar.sh`

Displays model, directory, branch, context utilization % with visual bar, and last user message. Writes context window size to a shared cache (`/tmp/claude-ctx-window-{session_id}`) read by `context-reporter.sh` — enabling the cross-script context monitoring system.

Note: The context-bar.sh script contains logic for overriding context window size when using OpenRouter as a provider — indicating DAAF supports non-Anthropic model providers.

---

## 11. Migration Considerations

### Claude Code-Specific Primitives (must be reimplemented)

| Primitive | Migration Complexity | Notes |
|-----------|---------------------|-------|
| Permission allow/deny patterns | HIGH | Three-tier matching with tool-specific glob patterns |
| Agent permission modes (`plan` vs `default`) | HIGH | Runtime-level read-only enforcement |
| Hook system (5 event types) | HIGH | Pre/post execution interception, exit code semantics |
| `.claudeignore` file exclusion | MEDIUM | Prevents indexing/discovery |
| `statusLine` configuration | LOW | Terminal UI convenience |
| `outputStyle` setting | LOW | Response formatting preference |
| `env` variable injection | LOW | Standard environment variable pattern |
| `showThinkingSummaries` | LOW | UI preference |

### Portable Content

- Permission patterns themselves are just string lists — the matching engine is harness-specific
- Hook scripts are bash — portable to any Unix-like environment with appropriate trigger wiring
- .claudeignore patterns follow .gitignore syntax — widely understood
- Pre-commit hooks use the pre-commit framework — fully independent of Claude Code
