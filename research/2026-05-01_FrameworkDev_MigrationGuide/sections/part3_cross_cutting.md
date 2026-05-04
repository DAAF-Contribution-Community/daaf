# Part III: Cross-Cutting Concerns

## 11. Feature Interdependency Map

DAAF's features do not exist in isolation. A permission deny rule that protects hook scripts from modification only matters if hooks exist; hooks that enforce file-first execution only matter if the instruction layer has told agents what file-first execution means; context monitoring only functions if the hook system can inject utilization data into agent conversations. These dependencies are not incidental -- they are structural. Porting features in the wrong order produces a system where enforcement mechanisms reference concepts the model has never been told about, or where safety layers protect infrastructure that does not yet exist.

This section maps those dependencies as a practical aid for migration planning.

### Dependency Layers

DAAF's features organize into eight dependency layers. Each layer assumes all layers below it are operational. The layers are numbered bottom-up: Layer 0 is the foundation that everything else requires.

```
  Layer 7 ── DAAF Conventions ─────────── research quality depends on this
     |       (file-first, IAT, naming,
     |        versioning, code style)
     |
  Layer 6 ── Logging / Audit ─────────── reproducibility depends on this
     |       (audit-log, archive-session,
     |        run_with_capture, output-scanner)
     |
  Layer 5 ── Context Management ──────── session viability depends on this
     |       (context-reporter, thresholds,
     |        STATE.md, persistence, recovery)
     |
  Layer 4 ── Skill System ────────────── domain knowledge depends on this
     |       (SKILL.md, progressive disclosure,
     |        frontmatter preloading)
     |
  Layer 3 ── Hook System ─────────────── enforcement depends on this
     |       (lifecycle events, blocking/injection,
     |        12 hook scripts, inter-hook comms)
     |
  Layer 2 ── Permission System ───────── safety depends on this
     |       (allow/deny lists, agent permission
     |        modes, three-tier matching)
     |
  Layer 1 ── Agent System ────────────── orchestration depends on this
     |       (definition, dispatch, isolation,
     |        frontmatter, tool restrictions)
     |
  Layer 0 ── Instruction Loading ─────── everything depends on this
             (CLAUDE.md, settings.json,
              system reminders, .claudeignore)
```

### Layer Dependency Details

| Layer | Depends On | Key Rationale |
|-------|-----------|---------------|
| **0: Instruction Loading** | Nothing (root) | CLAUDE.md carries universal rules; settings.json configures the runtime. Every subsequent layer assumes instructions are loaded. |
| **1: Agent System** | Layer 0 | Agents inherit CLAUDE.md; frontmatter references skills and hooks from settings.json. Without agents, no delegation or role-based access. |
| **2: Permission System** | Layers 0, 1 | Permissions live in settings.json (L0); agent permission modes are per-agent config (L1). Without permissions, read-only agents can write and denied commands execute freely. |
| **3: Hook System** | Layers 0, 1, 2 | Hook registrations live in settings.json (L0); per-agent hooks are in frontmatter (L1); hooks and permissions cooperate -- deny rules protect hook scripts while hooks enforce behaviors (L2). |
| **4: Skill System** | Layers 0, 1, 3 | Skill metadata loaded via system reminders (L0); skills preloaded via agent frontmatter (L1); orchestrator skill loading chain uses three cooperating hooks (L3). |
| **5: Context Management** | Layers 0, 1, 3, 4 | Threshold rules in CLAUDE.md (L0); subagent isolation fundamental to context budget (L1); context-reporter is a hook (L3); skill loading is a major context consumer (L4). |
| **6: Logging / Audit** | Layers 0, 2, 3 | Deny rules protect log files (L0/L2); audit-log, output-scanner, archive-session, and recover-session-logs are all hooks (L3). |
| **7: DAAF Conventions** | Layers 0, 3, 6 | Conventions defined in CLAUDE.md (L0); enforce-file-first.sh is a hook (L3); run_with_capture.sh is part of logging infrastructure (L6). |

### Tightly Coupled Feature Clusters

Some features are so interdependent that porting one without the others produces a non-functional or incoherent result. These clusters must be ported together:

| Cluster | Features | Why They Couple |
|---------|----------|-----------------|
| **Safety enforcement** | Permission deny rules + bash-safety.sh hook + enforce-file-first.sh hook + .claudeignore | Each covers a different attack surface. Deny rules block tool-level access; bash-safety blocks dangerous commands; enforce-file-first blocks interactive Python; .claudeignore prevents discovery. Removing any one layer leaves a gap the others cannot cover. |
| **Context monitoring** | context-reporter.sh hook + context-bar.sh statusline + CLAUDE.md threshold tables + early-return protocol in agent bodies | The hook measures utilization; the statusline caches the context window size that the hook reads; CLAUDE.md defines what to do at each threshold; agent protocols define the early-return format. Without any piece, the system either cannot measure, cannot display, or cannot act. |
| **Orchestrator skill loading** | remind-orchestrator.sh + flag-orchestrator-loaded.sh + daaf-orchestrator SKILL.md | Three hooks cooperate to ensure the orchestrator loads its skill on the first user message and is not reminded again. The flag file links remind to flag; the skill content is what gets loaded. |
| **File-first execution** | CLAUDE.md instructions + enforce-file-first.sh hook + run_with_capture.sh wrapper + immutable versioning convention | Instructions tell agents the rule; the hook blocks violations; the wrapper captures output; the versioning convention preserves history. Each alone is incomplete. |
| **Session lifecycle** | archive-session.sh + recover-session-logs.sh + collect_session_logs.sh + activity.log | The archiver preserves sessions at normal exit; recovery catches crashed sessions; collection gathers project-relevant logs; the activity log tracks all session starts. They share naming conventions, directory structures, and idempotency logic. |

### Suggested Porting Order

Based on the dependency analysis above, the recommended porting sequence is:

1. **Instruction loading** (Layer 0) -- Get CLAUDE.md equivalent and settings/config working first. Everything else depends on this.
2. **Agent system** (Layer 1) -- Stand up agent definitions, dispatch, and context isolation. Without agents, you cannot test any multi-agent behavior.
3. **Permission system** (Layer 2) + **Hook system** (Layer 3) -- Port these together. Permissions define the access control rules; hooks enforce them. The safety enforcement cluster requires both.
4. **Skill system** (Layer 4) -- Once agents can dispatch and hooks can fire, add progressive skill loading.
5. **Context management** (Layer 5) -- Requires hooks (for context-reporter) and agents (for subagent monitoring). Port the monitoring hook, then the CLAUDE.md threshold rules, then the persistence mechanisms.
6. **Logging and audit** (Layer 6) -- Requires hooks (for audit-log, output-scanner, archiver). Port the audit log first (simplest), then script execution capture, then session archiving.
7. **DAAF conventions** (Layer 7) -- Mostly instruction-driven. Once the instruction layer and hook enforcement are working, conventions are largely a matter of getting the right text into CLAUDE.md and agent protocols.

This order ensures that at every step, the dependencies for the current layer are already in place.

---

## 12. DAAF's Distinctive Design Contributions

Six of DAAF's capabilities have no equivalent in any surveyed AI coding harness -- not in Claude Code itself, not in Codex CLI, not in Cursor, OpenCode, Aider, or Windsurf. These are not configurations of existing features. They are architectural inventions that DAAF designed to solve problems specific to AI-assisted scientific research.

These six features represent DAAF's core value proposition. An implementer who understands them deeply understands what separates DAAF from a generic AI coding workflow. Each is documented here with the design problem it solves, the design solution DAAF chose, and why the solution matters for research integrity.

### 12.1 Context Self-Monitoring with Graduated Responses

**The design problem: silent quality degradation.** LLMs produce progressively worse output as context utilization increases -- repeating information, forgetting decisions, generating contradictions -- and this degradation is *silent*. Every other surveyed harness addresses context limits with a single mechanism (automatic compaction) that triggers once, late. None monitor quality degradation or take graduated actions before the crisis point.

**DAAF's design solution.** A three-component system:

1. **Measurement.** The `context-reporter.sh` hook parses the session transcript to calculate total token utilization, fires on every tool call and user message (rate-limited to 60-second intervals), and injects the measurement into the model's conversation as a system reminder. Crucially, it uses a *dual-threshold* trigger system where either percentage of context window OR absolute token count activates the threshold -- whichever fires first. On DAAF's 1M-token context window, the percentage threshold alone would not fire ELEVATED until 400k tokens. The absolute threshold fires at 150k, which is where empirical evidence shows quality begins declining.

2. **Graduated response protocol.** Four severity levels (NOMINAL, ELEVATED, HIGH, CRITICAL) with distinct, role-specific action requirements. The orchestrator's actions escalate from "continue normally" through "monitor and delegate more" to "complete current atomic unit and update STATE.md" to "cease immediately and finalize STATE.md." Subagents have parallel but distinct protocols, culminating in the early-return protocol (see Section 12.6). The graduated approach means DAAF does not wait for a crisis -- it begins adapting workload distribution at ELEVATED, well before quality is visibly affected.

3. **Persistence mechanisms.** Five file-based systems (STATE.md, SESSION_NOTES.md, LEARNINGS.md, preliminary notes, Plan_Tasks.md extraction protocol) that preserve information losslessly to disk, enabling session recovery without depending on in-context summaries that compaction would destroy.

**Why it matters.** DAAF's research pipelines can span dozens of subagent dispatches and hundreds of tool calls across multiple sessions. Without proactive quality monitoring, the difference between a reliable research output and an unreliable one is invisible until human review -- which is exactly what DAAF exists to make more efficient. Context self-monitoring is the mechanism that keeps AI-assisted research worth reviewing.

### 12.2 File-First Execution Protocol

**The design problem: ephemeral computation.** Standard AI coding workflows execute Python interactively -- computation happens, results appear on screen, and the execution context is lost. No permanent record ties specific code to specific output. No surveyed harness enforces non-ephemeral execution or captures execution output alongside source code.

**DAAF's design solution.** A mandatory three-step protocol enforced at three independent layers:

1. **Write.** Every Python operation is written as a complete, standalone script to the appropriate `scripts/` directory. No interactive execution, no notebook cells, no one-liners in the shell.

2. **Execute.** The script is run exclusively through `run_with_capture.sh`, a wrapper that pipes stdout and stderr through `tee`, captures the output to a temp file, records execution metadata (timestamp, duration, exit code), and appends the complete output to the script file itself as Python comments.

3. **Capture.** After execution, the script file contains both the source code and its complete output as a single, self-contained artifact. The `run_with_capture.sh` wrapper includes re-run protection: it refuses to execute a script that already has an appended execution log.

The three enforcement layers are: CLAUDE.md instructions (behavioral -- tells agents the rule), the `enforce-file-first.sh` hook (programmatic -- blocks direct `python`/`python3` invocations for coding agents), and the `run_with_capture.sh` wrapper itself (structural -- the only sanctioned execution path). This is deliberate defense-in-depth: instructions can be ignored by the model, hooks can fail, so both exist as independent enforcement.

**Why it matters.** Every research computation in DAAF exists as a permanent, self-documenting artifact. A reviewer can open any script file, read the code top-to-bottom, see exactly what it produced, and assess whether the output supports the conclusions drawn from it. This is the operational definition of reproducibility for AI-assisted research.

### 12.3 Inline Audit Trail (IAT)

**The design problem: opaque code.** AI-generated code is syntactically correct but semantically opaque. A reviewer seeing `df = df.filter(pl.col("grade") >= 9)` cannot tell *why* grade 9 was chosen -- the analytical reasoning is invisible. No surveyed harness mandates structured inline documentation targeting the specific problem of making AI analytical decisions auditable.

**DAAF's design solution.** A mandatory commenting convention with three structured prefixes:

- `# INTENT:` -- What a code block does and why it exists. Documents the analytical purpose, not the syntax.
- `# REASONING:` -- Why this approach was chosen over alternatives. Documents the decision, not just the outcome.
- `# ASSUMES:` -- What data properties the code depends on. Documents the preconditions that, if violated, would make the code produce wrong results.

Additionally, section preamble comments orient readers to each major code block (`# --- Config ---`, `# --- Load ---`, `# --- Transform ---`, `# --- Validate ---`, `# --- Save ---`), and inline annotations explain non-obvious single operations.

The convention is enforced through CLAUDE.md instructions (which all agents see) and agent protocol files (which specify IAT as a quality standard). The code-reviewer agent specifically checks for IAT completeness.

**Why it matters.** IAT makes AI-generated code auditable without running it. A human reviewer can follow every analytical decision by reading the source alone. Combined with file-first execution (which appends the output), a single script file tells the complete story: what was intended, what was assumed, what code was written, and what it produced. This transforms code review from "does this look right?" to "do these assumptions hold and do these decisions follow from the research question?"

### 12.4 Immutable Script Versioning

**The design problem: lost failure history.** When code fails in typical workflows, the developer fixes the bug in place and re-runs. The failed version is overwritten. For research, this destroys critical information: *what was tried, why it failed, and what changed*. No surveyed harness preserves both failed code and its execution output as paired artifacts.

**DAAF's design solution.** An immutable versioning convention with four rules:

1. Once `run_with_capture.sh` appends an execution log to a script, that file is never modified again. It becomes a sealed historical record.
2. Fixes go into a new file with a letter suffix: `01_task.py` (failed) becomes `01_task_a.py` (first fix attempt), then `01_task_b.py` (second fix), and so on.
3. All versions -- failed and successful -- remain in the same directory and are committed to version control.
4. A maximum of two self-revision attempts (_a, _b) is permitted before the agent must escalate to the debugger agent, preventing infinite retry loops.

**Why it matters.** A project's `scripts/` directory tells the complete story of every analytical attempt. A reviewer can see that the initial join produced zero rows (in `01_join.py`), that a key mismatch was identified and fixed (in `01_join_a.py`, which still failed due to a type error), and that the final version succeeded (in `01_join_b.py`). This history is invaluable for assessing research reliability -- a clean run on the first attempt is more trustworthy than one that required three corrections, and a reviewer should know the difference.

### 12.5 Defense-in-Depth Security Architecture

**The design problem: single-point-of-failure safety.** Most harnesses offer one or two safety mechanisms. If that single mechanism fails, there is no fallback. The surveyed landscape confirms: the maximum is four uncoordinated layers (Codex, Cursor). No harness coordinates its safety layers into a unified, mutually-reinforcing architecture.

**DAAF's design solution.** A nine-layer security model where each layer is independent, each covers a different attack surface, and the failure of any single layer does not compromise the overall safety posture:

1. **Container isolation** (Docker with `cap_drop: ALL`, non-root user) -- OS-level blast radius containment.
2. **`.claudeignore`** -- Prevents the AI from discovering sensitive files (`.env`, `*.pem`, `*.key`, `credentials*`).
3. **Permission deny rules** (35 patterns in settings.json) -- Blocks specific tool operations (editing hooks, writing to log files, reading credential files).
4. **Permission allow rules** (38 patterns in settings.json) -- Only explicitly approved operations auto-execute; everything else requires user confirmation.
5. **Agent permission modes** (`plan` mode makes agents physically read-only at the filesystem level, not just instructed to be read-only).
6. **PreToolUse blocking hooks** (bash-safety.sh, enforce-file-first.sh, enforce-explore-model.sh, enforce-foreground-agents.sh, deny-claude-code-guide.sh) -- Programmatic interception and blocking of disallowed actions before they execute.
7. **PostToolUse advisory hooks** (output-scanner.sh) -- Detects credential patterns in tool output and warns the model not to propagate them.
8. **Behavioral guardrails** (CLAUDE.md instructions) -- Rules that the model follows by instruction: never display API keys, never push without permission, never expand scope without approval.
9. **Pre-commit hooks** (.pre-commit-config.yaml) -- Catches large files, private keys, and merge conflicts at the git commit boundary.

The key architectural principle is *infrastructure self-protection*: deny rules prevent the AI from modifying its own guardrails (hook scripts in `.claude/hooks/*`) or tampering with the audit trail (log files in `.claude/logs/*`). If the AI could edit `bash-safety.sh`, it could remove the very check that prevents destructive commands. DAAF closes this loop.

**Why it matters.** Research data carries ethical and legal obligations. A framework that handles student records, financial data, or health information cannot rely on a single safety mechanism. DAAF's layered approach means that even if the model finds a way to circumvent one layer (e.g., crafting a command that passes bash-safety's regex), other layers (deny rules, container isolation, user confirmation prompts) still provide protection.

### 12.6 Subagent Early-Return Protocol

**The design problem: context exhaustion without recovery.** A subagent that exhausts its context window either returns degraded output or fails entirely -- both waste the orchestrator's context budget and risk losing completed work. No surveyed harness defines a protocol for what subagents should do when they detect approaching exhaustion.

**DAAF's design solution.** A structured protocol where subagents monitor their own context utilization (via the same context-reporter hook that monitors the orchestrator) and return early with a standardized output format when pressure exceeds defined thresholds:

At ELEVATED (>= 40% or >= 150k tokens), the subagent assesses remaining work honestly and begins structuring return output. At HIGH (>= 60% or >= 200k tokens), the subagent completes only its current atomic unit and returns immediately. At CRITICAL (>= 75% or >= 250k tokens), the subagent stops immediately.

The early return must include five elements:
1. All file paths created or modified (absolute paths)
2. Summary of completed work and findings
3. Explicit list of tasks not yet started or partially completed
4. Decisions made or assumptions applied that the next agent needs to know
5. Confidence assessment of completed work

This structured format allows the orchestrator to seamlessly continue the work -- either by dispatching a fresh subagent with the incomplete items or by handling them directly. The orchestrator updates STATE.md with the partial results so nothing is lost across session boundaries.

**Why it matters.** DAAF's research pipelines routinely involve subagents that load domain skills (5k-20k tokens each), read data files, execute scripts, and analyze results. A single subagent can easily consume 100k+ tokens on a complex task. Without the early-return protocol, this subagent would either produce declining-quality output in its final turns or silently fail, wasting the orchestrator's context budget on re-dispatch. The protocol converts a potential total loss into a partial, well-documented completion that preserves all work done so far.

---

## 13. Industry-Converged Standards

Not all of DAAF's architecture requires custom implementation on a new harness. Five significant capability areas have converged toward cross-harness standards as of 2026, meaning that DAAF's patterns in these areas can port with reduced effort -- sometimes with no changes at all.

### 13.1 SKILL.md / Agent Skills

**The standard.** The `agentskills.io` open standard defines a file format for packaging domain knowledge that AI coding agents can discover and load on demand. A skill is a directory containing a `SKILL.md` file with YAML frontmatter (name, description, metadata) and a markdown body, optionally accompanied by a `references/` subdirectory for supplementary material.

**DAAF's usage.** DAAF implements 36 skills across seven categories (16 data source, 11 Python library, 2 data access, 1 methodology, 1 orchestration, 3 meta-development, and others). Skills are discovered automatically via filesystem scanning. The 250-character description truncation at Level 1 means all 36 skills cost only approximately 3,600 words of always-on context, with full content loaded on demand. DAAF adds a metadata controlled vocabulary (`audience`, `domain`, `library-version`, `skill-authored`, `skill-last-updated`) and a trust model distinguishing curated knowledge from LLM inference.

**Harness support.** Claude Code (native), Codex CLI (native, with 2% context budget cap and auto-wiring of MCP dependencies), Cursor (native, with skills marketplace for discovery). OpenCode, Aider, and Windsurf lack native support.

**Migration effort.** For Codex and Cursor: DAAF's SKILL.md files transfer with zero changes. The open standard ensures format compatibility. DAAF's metadata vocabulary and trust model would need to be documented in the target's instruction file (AGENTS.md equivalent) since those are DAAF conventions, not standard features.

### 13.2 AGENTS.md / Custom Instructions

**The standard.** Every surveyed harness supports a project-level instruction file that is automatically loaded into agent contexts. The filename and discovery mechanism vary, but the concept is universal: a markdown file in the project root that defines behavioral rules, conventions, and context for the AI agent.

**DAAF's usage.** DAAF's `CLAUDE.md` (377 lines) defines universal rules visible to all agents: execution philosophy, code style, context management thresholds, safety boundaries, project conventions, and reference file index. It is the only instruction layer guaranteed to reach every agent in the system.

**Harness support.** Claude Code (`CLAUDE.md`, hierarchical with directory walking), Codex CLI (`AGENTS.md`, hierarchical with directory proximity), OpenCode (`AGENTS.md` plus `instructions` config paths), Cursor (`.cursor/rules/*.mdc` with four activation modes), Aider (`CONVENTIONS.md`, flat, explicitly loaded), Windsurf (rules files with four activation modes). All six harnesses support this pattern.

**Migration effort.** Low to moderate. The *content* of CLAUDE.md is fully portable text. The structural mapping varies: Codex requires minimal restructuring (rename to `AGENTS.md`), Cursor requires splitting into multiple `.mdc` files with activation conditions, and Aider requires explicit loading via `--read` flags. The critical requirement is that the instruction content reaches *all* agents including subagents -- not all harnesses guarantee this by default.

### 13.3 MCP (Model Context Protocol)

**The standard.** An open protocol for connecting AI agents to external tools and data sources through a standardized server interface.

**DAAF's usage.** DAAF does not currently use MCP (built-in tools suffice), but MCP availability on a target harness matters for future data source connector extensions.

**Harness support.** Claude Code, Codex CLI (with auto-wiring), OpenCode, Cursor (with marketplace), Windsurf (with pre-built integrations). Five of six harnesses; only Aider lacks support.

**Migration effort.** Not applicable for current DAAF functionality. Any future MCP-based integrations would port across harnesses with minimal adaptation.

### 13.4 Hooks / Lifecycle Events

**The standard.** An emerging convention where the harness exposes lifecycle events (before/after tool execution, session start/end, user prompt submission) and allows project-defined scripts to intercept them. Event names are converging around `PreToolUse` and `PostToolUse`, with `SessionStart` and `SessionEnd` also common. The ability to *block* execution (via exit codes or return values) versus merely *observe* it is a critical distinction.

**DAAF's usage.** DAAF registers 12 hook scripts across 5 event types (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, SessionEnd) with 15 total registrations in settings.json plus 4 per-agent registrations in frontmatter. Hooks are DAAF's primary enforcement mechanism -- 5 safety hooks (fail-closed), 5 observability hooks (fail-open), and 2 behavioral hooks. The inter-hook communication pattern (via `/tmp` cache files) and the deterministic skill-loading chain (three hooks cooperating) are DAAF-specific extensions beyond the basic event model.

**Harness support.** Claude Code (5 events, blocking via exit code 2), Codex CLI (5 events, concurrent hooks, managed enterprise hooks), Cursor (6+ events including `subagentStart`, `failClosed` option), OpenCode (plugin-based hooks including compaction hook). Aider has no hook system. Four of five harnesses with hooks support blocking semantics on pre-execution events.

**Migration effort.** Moderate. The hook registration format differs across harnesses (settings.json vs. config.toml vs. plugin files), but the conceptual model is converging. DAAF's hook scripts are standard Bash reading JSON from stdin -- they can run on any harness that passes equivalent JSON payloads. The main porting work is mapping DAAF's event names and JSON field names to the target harness's equivalents, and replicating the inter-hook communication patterns.

### 13.5 Subagent Context Isolation

**The standard.** When a parent agent dispatches a subagent, the subagent operates in a separate context window. It does not inherit the parent's conversation history. It receives only the system prompt, project-level instructions, its agent-specific configuration, and the dispatch prompt. This isolation is essential for managing context budgets in multi-agent architectures.

**DAAF's usage.** Context isolation is foundational to DAAF's architecture. The orchestrator maintains a lean context (~2,000 words of working memory) by delegating skill loading, data exploration, code execution, and deep research to subagents. Each subagent bears the context cost of its own work in its own window. Subagent returns are processed through a two-tier protocol: the full return is written to disk (preliminary notes) while only a compressed summary (3-5 bullets, file paths, status) enters the orchestrator's context. Without isolation, every skill load (5k-20k tokens) and every script execution would consume the orchestrator's budget directly.

**Harness support.** Claude Code (native via Agent tool), Codex CLI (native with configurable `max_depth`), Cursor (native with async subagents and recursive spawning), OpenCode (native with event-driven coordination). Aider and Windsurf lack multi-agent dispatch entirely.

**Migration effort.** Low for Codex, Cursor, and OpenCode -- the isolation model is architecturally equivalent. The key verification is that project-level instructions (CLAUDE.md equivalent) are inherited by subagents automatically, which is confirmed for Codex and Cursor. The 2,000-word return cap and the two-tier information architecture (orchestrator summary vs. disk-persisted full findings) are DAAF conventions that port via instruction files, not harness features.
