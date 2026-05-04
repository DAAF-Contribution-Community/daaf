# Migration Guide Plan: DAAF Feature Parity Specification

## Purpose of This Plan

This document defines the complete structure, content strategy, and section-by-section blueprint for the DAAF Migration Guide -- a **feature-parity specification** that catalogs every capability DAAF requires, documents the design intent behind each capability, explains how it is currently realized on Claude Code, and specifies what an implementer must build on any target harness to achieve equivalent behavior.

**Critical framing distinction:** Many of DAAF's most important features are *DAAF's own design decisions implemented on top of Claude Code*, not Claude Code features that DAAF passively consumes. File-first execution, context self-monitoring, compaction avoidance, defense-in-depth, immutable script versioning -- these are all architectural choices DAAF made. Claude Code doesn't provide file-first execution by default; DAAF designed it and enforces it via hooks, instructions, and conventions. The guide must capture the *design intent* behind each feature so an implementer understands the "why" and can make equivalent design decisions on their platform, even when the mechanisms differ.

The migration guide is NOT a migration plan for any specific harness. It is a **harness-neutral feature specification** organized so that someone porting DAAF to ANY harness can:
1. Understand what capability DAAF needs and why it exists
2. See how DAAF currently implements it (distinguishing native Claude Code primitives from DAAF-built layers)
3. Know the exact behavioral specification to replicate
4. Assess their target harness's equivalent mechanisms (or lack thereof)
5. Understand which other features depend on each capability

---

## Document Structure

### Part I: Foundation and Orientation

#### 1. Introduction and How to Use This Guide
**Description:** Frames the document for its audience: a developer (or AI agent) tasked with porting DAAF to a non-Claude-Code harness. Explains DAAF's purpose (research orchestration framework), what Claude Code provides (the runtime harness), and why portability matters. Defines key terminology: "harness" (the AI coding agent runtime), "framework" (DAAF itself), "feature" (a harness capability DAAF uses). Explains the migration complexity ratings used throughout. Provides a reading path: readers targeting a specific harness can jump to the relevant cross-reference boxes, while readers doing a full port should read sequentially.

**Feeds from:** Finding 09 (external harnesses -- for framing why this guide exists), Finding 08 (instruction loading -- for the conceptual distinction between harness primitives and framework content)

**Key content points:**
- What DAAF is (one paragraph, self-contained)
- What Claude Code provides (runtime, not content)
- The harness vs. framework distinction
- Migration complexity rating definitions (see below)
- Reading path and navigation guide

**Detail level:** Concise (500-700 words). This is orientation, not technical content.

**Cross-references:** Links to the complexity rating system (Section 2), the feature inventory (Part II), and the harness landscape (Part IV).

---

#### 2. Migration Complexity Rating System
**Description:** Defines the classification system applied to every feature throughout the guide. Each feature receives ratings on three axes: (a) **Criticality** -- how essential the feature is to DAAF's operation, (b) **Portability** -- how easily the feature transfers to other harnesses, and (c) **Interdependence** -- how many other features depend on it.

**Feeds from:** All 9 findings (each contains a "Migration Considerations" section with complexity assessments)

**Key content points:**

**Criticality ratings:**
| Rating | Meaning | Example |
|--------|---------|---------|
| CRITICAL | DAAF cannot function without this; must be fully replicated | Subagent dispatch, CLAUDE.md injection, hook-based safety blocking |
| HIGH | DAAF degrades significantly without this; partial workarounds may exist | Per-agent tool restrictions, skill preloading, context monitoring |
| MEDIUM | Loss reduces quality or convenience but DAAF can operate | Session archiving, output scanning, status line |
| LOW | Nice-to-have; loss is cosmetic or easily worked around | Output style setting, thinking summaries, first-run onboarding |

**Portability ratings:**
| Rating | Meaning |
|--------|---------|
| NATIVE | Target harness has a direct equivalent feature |
| ADAPTABLE | Target harness has a related feature that can be configured to match |
| REIMPLEMENTABLE | No direct equivalent but can be built using the harness's extension mechanisms (hooks, plugins, etc.) |
| ARCHITECTURAL | Requires fundamental harness changes or a wrapper/middleware layer |

**Interdependence scale:** Count of other features that depend on this one (0 = isolated, 5+ = foundational).

**Detail level:** Brief (300-400 words plus the tables). This is a reference section consulted throughout.

---

### Part II: Feature Specifications (The Core of the Guide)

This is the largest section, organized from most critical/foundational to most peripheral. Each feature section follows a standard template that separates *design intent* from *current implementation* from *replication specification*:

```
### Feature Name
**Criticality:** [rating] | **Interdependencies:** [count]

#### Design Intent
[What problem does this feature solve? What design decision did DAAF make and why?
This is the "why" -- the reasoning an implementer needs to understand before they
can make equivalent choices on their platform.]

#### What It Does
[Functional description -- what the feature accomplishes for DAAF. Behavior specification
independent of implementation.]

#### Current Realization on Claude Code
[How DAAF implements this feature today. Clearly distinguish:
- **Native primitive:** Feature provided by Claude Code that DAAF configures/uses
  (e.g., agent frontmatter, permission allow/deny lists)
- **DAAF-built layer:** Feature that DAAF designed and implemented on top of
  Claude Code primitives (e.g., file-first execution, context self-monitoring,
  defense-in-depth). Include the specific hooks, settings, instructions, and
  conventions that realize the design.
- **Hybrid:** Feature combining a Claude Code primitive with significant DAAF
  configuration/extension (e.g., the permission system uses Claude Code's
  allow/deny mechanism but DAAF's specific pattern choices embody deliberate
  design decisions)]

#### Design Choices and Rationale
[For each significant design choice in this feature: what was chosen, what
alternatives exist, and why this choice was made. This is critical for
implementers who may face different tradeoffs on their platform.
Example: "Read is NOT auto-allowed despite being non-destructive -- DAAF
intentionally requires user confirmation for every file read to maintain
the principle that the researcher sees everything the AI accesses."]

#### Replication Specification
[Precise, harness-neutral requirements for achieving feature parity:
- Required capabilities in the target harness
- Behavioral contract: inputs, outputs, failure modes, timing
- Acceptance criteria: how to verify the feature works correctly
- Degraded-mode options: if full parity isn't achievable, what's the
  minimum viable subset?]

#### Harness Landscape
[Brief cross-reference to which surveyed harnesses have equivalent mechanisms.
Not a migration plan -- just awareness of what's available.]

#### Dependencies
[Which other DAAF features this one requires or feeds into]
```

**The "Design Choices and Rationale" section is essential.** Many DAAF features look like simple configuration (e.g., a list of denied commands in settings.json) but embody deliberate design reasoning (e.g., "we deny editing hook scripts because hooks are the enforcement layer -- if the AI can modify its own guardrails, the safety model collapses"). An implementer who only sees the configuration without understanding the reasoning will make subtly wrong choices on their platform.

---

#### 3. Instruction Loading and Project Configuration
**Description:** How DAAF's instructions reach the model across a 10-layer hierarchy is both a Claude Code capability and a DAAF architectural design. Claude Code provides the primitives (CLAUDE.md auto-loading, settings.json, system reminders, agent frontmatter). DAAF designed the progressive disclosure architecture that orchestrates *when* and *how* each instruction layer loads, keeping context lean while ensuring every agent has the right knowledge at the right time. The 10-layer hierarchy, the progressive loading cascade, and the separation of universal rules (CLAUDE.md) from mode-specific instructions (orchestrator skill) from agent-specific protocols (agent body) — these are all DAAF design decisions.

**Classification: HYBRID** — Claude Code provides auto-loading of CLAUDE.md, settings.json parsing, system-reminder injection, and agent frontmatter. DAAF designed the 10-layer architecture, progressive disclosure cascade, content separation strategy, and the hook-enforced skill loading chain.

**Feeds from:** Finding 08 (instruction loading -- primary), Finding 04 (settings/permissions), Finding 03 (skill system)

**Key content points:**
- The 10-layer instruction hierarchy with loading order
- CLAUDE.md: auto-discovery, directory-walking, injection as `<system-reminder>`, content scope (377 lines of universal rules), visibility to all agents
- settings.json: 6 top-level keys, environment variables (ANTHROPIC_MODEL, effort level, feature toggles), how it configures the runtime
- The `.claudeignore` file: 12 patterns, prevents indexing vs. prevents access distinction
- System reminders: date, email, git status, environment, skills list, model identity
- User preferences as persistent config stored in CLAUDE.md
- Output style setting ("Explanatory")

**Detail level:** HIGH. Every instruction source must be documented precisely because instruction loading is the foundation for all agent behavior. Include the complete settings.json structure and CLAUDE.md section inventory.

**Cross-references:** Section 4 (agents inherit CLAUDE.md), Section 6 (skills loaded as instructions), Section 7 (hooks inject instructions)

---

#### 4. Agent System: Definition, Dispatch, and Isolation
**Description:** The agent system is the architectural backbone of DAAF's multi-agent orchestration. Claude Code provides the primitives (agent definition files with YAML frontmatter, the Agent/Task dispatch tools, per-agent tool restrictions, permission modes, context isolation). DAAF designed the 15 specialized agents, the 12-section protocol template, the structured output contracts, the skill-preloading strategy, the wave-based parallelism patterns, and the hooks that block unsuitable agent types. The key DAAF design decisions include: which agents get write access vs. read-only, which agents are trusted with web access, the model inheritance strategy (all agents on Opus), and blocking Explore/claude-code-guide agents that would run on weaker models.

**Classification: HYBRID** — Claude Code provides agent definition format, dispatch tools, frontmatter parsing, permission modes, context isolation. DAAF designed the agent specialization architecture, behavioral protocols, output contracts, tool-access tiers, and blocking hooks.

**Feeds from:** Finding 02 (agent system -- primary), Finding 07 (tool system -- tool restrictions), Finding 05 (context management -- agent isolation)

**Key content points:**
- Agent definition file format: location (`.claude/agents/`), naming convention, YAML frontmatter schema (8 fields with complete specification), markdown body (12-section template)
- Frontmatter fields in detail: `name`, `description`, `tools`, `permissionMode`, `model`, `skills`, `hooks`, `maxTurns` -- defaults, valid values, current usage across all 15 agents
- Three tool-access tiers: full read/write (7 agents), read-only (4), read-only+web (1), full+web (2)
- Two permission modes: `default` (read/write) vs. `plan` (read-only at filesystem level)
- Agent dispatch mechanics: the Agent/Task tool call structure, parameter types, name-to-file routing
- Context composition at spawn: system prompt + CLAUDE.md + agent body + preloaded skills + orchestrator prompt -- what is inherited vs. what is NOT (conversation history is NOT inherited)
- Subagent return mechanics: text output as return value, 2000-word cap, structured format
- Parallel dispatch: up to 5 concurrent foreground agents, wave-based parallelism
- Generic vs. named agent types: `general-purpose`, `Plan`, `Explore` (blocked), `claude-code-guide` (blocked)
- Model selection: inheritance chain, ANTHROPIC_MODEL env var, why all agents run on Opus
- Complete frontmatter inventory for all 15 agents

**Detail level:** VERY HIGH. This is DAAF's architectural core. Include the complete agent inventory table, the tool matrix, the frontmatter schema, and the dispatch call structure. Include the complete prompt template structure showing how orchestrator prompts are composed.

**Cross-references:** Section 5 (permission system layers), Section 6 (skill preloading), Section 7 (per-agent hooks), Section 8 (context isolation)

---

#### 5. Permission and Security System
**Description:** DAAF's defense-in-depth security architecture is a DAAF-designed, multi-layered security model built using Claude Code primitives (allow/deny patterns, agent permission modes) combined with DAAF-built enforcement (hooks, container isolation, pre-commit checks, behavioral guardrails). The settings.json patterns embody deliberate design decisions — each allowed/denied pattern has a reason rooted in DAAF's transparency, safety, and research integrity principles. This section must document not just *what* is allowed/denied, but *why each choice was made*.

**Classification: HYBRID** — Claude Code provides the allow/deny matching engine and agent permission modes; DAAF designed the specific pattern set, the layered architecture, and the coordinating enforcement hooks.

**Feeds from:** Finding 04 (settings/permissions -- primary), Finding 01 (hooks -- safety hooks), Finding 02 (agent system -- permission modes)

**Key content points:**
- The 9-layer defense-in-depth architecture (enumerated with what each layer covers)
- settings.json permission system: allow list (38 patterns with categories), deny list (35 patterns with 6 categories), three-tier matching logic
- **Design rationale for each pattern category:**
  - Why `Read` is NOT auto-allowed (transparency: researcher sees every file the AI accesses)
  - Why `WebFetch` is NOT auto-allowed despite `WebSearch` being allowed (WebFetch can exfiltrate data; WebSearch only retrieves public info)
  - Why `git commit` requires approval (researcher controls what enters the permanent record)
  - Why named DAAF agents are NOT pre-allowed (transparency: researcher is aware when specialists are dispatched)
  - Why hook scripts and audit logs are deny-protected (self-protection: the AI cannot modify its own guardrails or tamper with the audit trail)
  - Why credential files are blocked at THREE layers (.claudeignore + deny rules + output-scanner) (defense-in-depth: any single layer might fail)
- Agent permission modes: `default` vs. `plan` — the design choice to make certain agents physically incapable of writing, not just instructed not to
- Infrastructure self-protection principle: deny rules on `.claude/hooks/*` and `.claude/logs/*`
- The credential management pattern: secrets never enter the container filesystem
- Container isolation as the outermost blast radius boundary

**Detail level:** HIGH. Include the complete allow and deny pattern lists with design rationale for each category. The security model is non-negotiable for research integrity.

**Cross-references:** Section 4 (agent permission modes), Section 7 (hooks as enforcement layer)

---

#### 6. Skill System: Progressive Knowledge Disclosure
**Description:** The skill system is a collaboration between Claude Code primitives and DAAF design. Claude Code provides the Skill tool, SKILL.md format, automatic filesystem discovery, and frontmatter-based preloading. DAAF designed the three-level progressive disclosure architecture, the "skills loaded by subagents, not orchestrator" principle, the trust model distinguishing curated knowledge from LLM inference, the metadata controlled vocabulary, the hook-enforced orchestrator skill loading chain, and the 36 domain-specific skills themselves. The key DAAF design insight is that skills are *context-efficient knowledge injection* — the 250-char description truncation at Level 1 means all 36 skills cost only ~3,600 words of always-on context, with full content loaded on demand.

**Classification: HYBRID** — Claude Code provides the Skill tool, discovery, frontmatter parsing, and preloading mechanism. DAAF designed the progressive disclosure architecture, the loading governance model, the trust framework, and all skill content.

**Feeds from:** Finding 03 (skill system -- primary), Finding 02 (agent system -- skill preloading), Finding 08 (instruction loading -- skill as Layer 8)

**Key content points:**
- Three-level progressive disclosure: metadata (always loaded, ~100 words/skill), body (on skill trigger, <5000 words), references (on demand, no limit)
- SKILL.md format: YAML frontmatter (name, description at 250-char truncation, metadata dict), markdown body, references/ subdirectory
- Skill discovery: automatic filesystem scanning, no manual registration
- Loading paths: explicit Skill tool call, frontmatter preloading (`skills:` field), slash command
- The "skills loaded by subagents, not orchestrator" principle with 3 exceptions
- Skill categories: 16 data source, 11 Python library, 2 data access, 1 data documentation, 1 methodology, 1 orchestration, 1 communication, 3 meta-development
- Metadata controlled vocabulary: audience, domain, library-version, skill-authored, skill-last-updated
- Decision tree pattern: ASCII box-drawing navigation within skills
- Trust model: curated knowledge vs. LLM inference, staleness detection via `skill-last-updated`
- Token budget: Level 1 fixed cost (~3600 words for 36 skills), Level 2 on demand, Level 3 on demand
- The orchestrator-loaded flag chain: remind-orchestrator -> Skill call -> flag-orchestrator-loaded (3 hooks cooperating)
- Integration points beyond discovery: agent frontmatter, pipeline stage mappings, orchestrator dispatch tables

**Detail level:** HIGH. Include the complete skill inventory table, the frontmatter specification, and the loading lifecycle diagram. Skills are a distinguishing DAAF capability with growing cross-harness support.

**Cross-references:** Section 3 (CLAUDE.md carries skill metadata awareness), Section 4 (agent frontmatter preloading), Section 7 (PostToolUse hook on Skill)

---

#### 7. Hook System: Runtime Behavior Injection
**Description:** The hook system is the primary *mechanism* through which DAAF enforces its design decisions at runtime. Claude Code provides the hook infrastructure (5 event types, JSON stdin protocol, exit code semantics, matcher-based routing, per-agent frontmatter hooks). DAAF designed and implemented all 12 hook scripts, the fail-closed vs. fail-open architecture, the inter-hook communication pattern (via /tmp files), and the deterministic skill-loading chain. Hooks are where DAAF's design intent becomes runtime reality — file-first enforcement, safety blocking, context monitoring, audit logging, and session management all flow through this system.

**Classification: HYBRID** — Claude Code provides the hook infrastructure (event lifecycle, stdin/stdout protocol, exit code semantics, matcher routing). DAAF designed all hook scripts, the three functional categories (safety/observability/behavioral), the fail-closed/fail-open architecture, inter-hook communication, and agent-scoped hook registration strategy.

**Feeds from:** Finding 01 (hooks system -- primary), Finding 04 (settings/permissions -- hook registration), Finding 06 (logging -- observability hooks)

**Key content points:**
- 5 event types: SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, SessionEnd
- Registration: settings.json (project-wide, 13 registrations) vs. agent frontmatter (per-agent, 4 agents)
- Matcher semantics: empty string (all tools), tool name (Bash, Task, Agent, Skill)
- Input protocol: JSON on stdin with common fields (session_id, transcript_path, hook_event_name) plus event-specific fields (tool_name, tool_input, tool_response, agent_type, agent_id)
- Output protocol: exit codes (0=allow, 1=error, 2=block), stdout processing by event, JSON hookSpecificOutput (permissionDecision deny vs. additionalContext injection)
- All 12 hooks documented: purpose, event, matcher, input/output, fail mode, subagent firing behavior
- Three functional categories: safety (fail-closed: bash-safety, enforce-file-first, enforce-explore-model, enforce-foreground-agents, deny-claude-code-guide), observability (fail-open: audit-log, output-scanner, archive-session, recover-session-logs, context-reporter), behavioral (remind-orchestrator, flag-orchestrator-loaded)
- Per-agent hooks: only `enforce-file-first.sh` on 4 coding agents -- design rationale
- Subagent firing matrix: which hooks fire for orchestrator vs. subagents
- Inter-hook communication via /tmp files: 5 cache files linking context-bar, context-reporter, audit-log, remind-orchestrator, flag-orchestrator-loaded
- The deterministic skill loading chain (3 hooks cooperating)

**Detail level:** VERY HIGH. Include the complete registration table, every hook's specification, the subagent firing matrix, and the inter-hook communication diagram. Hooks are the primary enforcement mechanism for DAAF's safety and quality guarantees.

**Cross-references:** Section 5 (hooks as security layer), Section 8 (context-reporter hook), Section 9 (audit-log and archive-session hooks)

---

#### 8. Context Management and Monitoring
**Description:** Context management is one of DAAF's most significant DAAF-designed features. Claude Code offers automatic compaction (lossy summarization when context grows large). DAAF actively foregoes this, instead designing and implementing its own context self-monitoring protocol: a hook-based utilization tracker with dual thresholds, graduated response rules for both orchestrator and subagents, an early-return protocol, and five file-based persistence mechanisms that preserve information losslessly. This entire system is a DAAF architectural decision — none of it exists in Claude Code by default.

**Classification: DAAF-BUILT** — Claude Code provides the transcript JSONL (from which tokens are calculated) and the hook system (through which monitoring is injected). Everything else — the thresholds, the severity levels, the graduated actions, the persistence mechanisms, the early-return protocol — is DAAF's design.

**Feeds from:** Finding 05 (context management -- primary), Finding 01 (hooks -- context-reporter), Finding 02 (agents -- context isolation and return caps)

**Key content points:**
- Why DAAF disables auto-compaction: information loss unacceptable, DAAF has its own system, compaction disrupts orchestration state
- The context-reporter hook: technical implementation, token calculation formula (input + cache_read + cache_creation), context window size discovery via cross-script /tmp cache, rate limiting (60s gate)
- Dual-threshold severity system: NOMINAL (<40% AND <150k), ELEVATED (>=40% OR >=150k), HIGH (>=60% OR >=200k), CRITICAL (>=75% OR >=250k)
- Why absolute thresholds matter: on a 1M window, 40% = 400k tokens -- too late for quality
- Orchestrator actions by threshold: continue, monitor/delegate, complete atomic unit + STATE.md, cease immediately
- Subagent actions by threshold: continue, assess/prioritize, return early, stop immediately
- Early return protocol: 5 required elements in structured return
- Context degradation symptoms: 6 observable symptoms with severity mapping
- Quality primacy rule: thresholds control WHEN to restart, never WHETHER to maintain quality
- Orchestrator context budget: ~2000 words max in main context, what gets delegated vs. what stays
- Five persistence mechanisms: STATE.md (primary session state), SESSION_NOTES.md (lightweight for ad-hoc modes), LEARNINGS.md (cross-session learning signals), Preliminary notes (lossless subagent returns to disk), Plan_Tasks.md extraction protocol (selective reading)
- The restart prompt pattern: pre-formatted prompt in STATE.md for session resumption
- Session recovery protocol: 7-step procedure for resuming after context clear
- Dispatch as context preservation: subagent dispatch explicitly used to protect orchestrator context

**Detail level:** HIGH. Include the threshold tables, the persistence mechanism specifications, and the restart prompt format. Context management is what makes DAAF's multi-stage research pipelines viable across session boundaries.

**Cross-references:** Section 4 (agent context isolation), Section 7 (context-reporter hook), Section 9 (session archiving)

---

#### 9. Logging, Audit Trail, and Session Management
**Description:** DAAF's observability and reproducibility infrastructure is almost entirely DAAF-designed. Claude Code provides raw JSONL transcripts and hook lifecycle events; DAAF builds everything else: a structured audit log, secret detection scanning, human-readable session archives with subagent discovery, crash recovery, and — most critically — the **file-first execution protocol** with `run_with_capture.sh`, immutable script versioning, and Inline Audit Trail (IAT) conventions. File-first execution is the cornerstone of DAAF's reproducibility guarantee: every analysis operation exists as a script file with its execution output appended as an immutable record. This is a DAAF invention, not a Claude Code feature.

**Classification: DAAF-BUILT** — Claude Code provides JSONL transcripts and hook events. DAAF designed and built: the audit log format, the output scanner, the session archiver (474 lines of jq-powered JSONL-to-Markdown conversion), the crash recovery system, the file-first execution protocol (run_with_capture.sh + enforce-file-first.sh hook + CLAUDE.md instructions), immutable script versioning (_a/_b/_c progression), IAT comment conventions, log collection, and the interactive log viewer.

**Feeds from:** Finding 06 (logging/sessions -- primary), Finding 01 (hooks -- observability hooks), Finding 07 (tool system -- file-first execution)

**Key content points:**
- **File-first execution protocol (DAAF-designed):**
  - Design intent: every Python operation must exist as a permanent, auditable script with captured output — no ephemeral interactive execution
  - Three enforcement layers: CLAUDE.md instructions (behavioral), enforce-file-first.sh hook (programmatic, agent-scoped), run_with_capture.sh wrapper (captures stdout/stderr and appends to script)
  - Why three layers: defense-in-depth — instructions can be ignored, hooks can fail, so both exist as independent enforcement
  - The immutable artifact pattern: once a script has its output appended, it is never modified; fixes go to _a.py, _b.py versions
  - Re-run protection: run_with_capture.sh refuses to execute a script that already has an output log
- **Immutable script versioning (DAAF-designed):**
  - Design intent: preserve the complete history of attempts, including failures, as audit trail
  - All versions remain in the same directory for traceability
- **Inline Audit Trail / IAT (DAAF-designed):**
  - Design intent: every transformation in a script must document its reasoning inline using INTENT/REASONING/ASSUMES prefixes
  - Makes code auditable without running it — a human reviewer can follow every decision
- **Audit log system (DAAF-built on PostToolUse hook):** JSONL format, 7-8 fields, append-only with deny-rule protection
- **Output scanner (DAAF-built):** 7 credential patterns, advisory, 10KB scan limit
- **Session archiving (DAAF-built):** JSONL copy + Markdown conversion, subagent discovery, idempotency, crash recovery
- **Log viewer (DAAF-built):** interactive HTML SPA with timeline, subagent drill-down

**Detail level:** VERY HIGH for file-first execution, immutable versioning, and IAT (these are DAAF's most distinctive reproducibility features and have no equivalent anywhere). HIGH for audit-log and archiving. MEDIUM for log viewer.

**Cross-references:** Section 7 (hooks that implement logging), Section 5 (deny rules protecting log integrity), Section 10 (one-command-per-call rule supports file-first)

**Cross-references:** Section 7 (hooks that implement logging), Section 5 (deny rules protecting log integrity)

---

#### 10. Tool System and Calling Conventions
**Description:** The tool system is primarily a Claude Code native capability (17+ built-in tools with XML calling conventions), but DAAF layers significant design decisions on top: the one-command-per-Bash-call rule (to maintain safety hook granularity and permission clarity), per-agent tool restriction matrices (read-only agents physically cannot write), the file-first execution enforcement (connecting the tool system to the audit trail), and the deliberate non-use of MCP. Each of these is a DAAF design choice with a specific rationale.

**Classification: HYBRID** — Claude Code provides the tools, calling conventions, deferred tool loading, and per-agent tool restrictions. DAAF designed the one-command rule, the tool-access tier system, and the file-first execution pattern.

**Feeds from:** Finding 07 (tool system -- primary), Finding 02 (agent system -- tool restrictions), Finding 04 (settings -- allow/deny for tools)

**Key content points:**
- Complete tool inventory: 6 categories (file operations, search, command execution, web access, subagent/task management, knowledge/skill), with parameters and notes for each
- Calling conventions: XML function_calls syntax, parameter passing (strings vs. JSON for complex types), parallel tool calls in single response
- Deferred tools: ToolSearch mechanism, which tools are deferred (Task management), which always loaded (core 10)
- Per-agent tool restrictions: the `tools` frontmatter field, the complete agent-tool matrix
- DAAF-specific patterns: one command per Bash call (safety enforcement), file-first execution (write -> execute via run_with_capture -> capture), interactive Python prohibition (three enforcement layers)
- MCP: not used by DAAF, but `mcp__ide__executeCode` explicitly prohibited in BOUNDARIES.md
- Tool result processing: how errors are surfaced, hook-blocked command error messages

**Detail level:** MEDIUM. Focus on DAAF's specific patterns and restrictions rather than exhaustively documenting each tool's parameters.

**Cross-references:** Section 4 (per-agent tool restrictions), Section 5 (permission allow/deny for tools), Section 7 (PreToolUse hooks gate tool execution)

---

### Part III: Cross-Cutting Concerns

#### 11. Feature Interdependency Map
**Description:** A visual and tabular representation of how DAAF's features depend on each other. Critical for migration planning because features cannot be ported in isolation.

**Feeds from:** All findings (each documents dependencies)

**Key content points:**
- Dependency graph: which features must exist before others can function
- Suggested porting order based on dependency analysis
- Circular dependencies and how to break them
- Feature clusters: groups of features that must be ported together

**Proposed dependency layers (bottom-up):**
1. **Layer 0: Instruction loading** (CLAUDE.md equivalent, project config) -- everything depends on this
2. **Layer 1: Agent system** (definition, dispatch, isolation) -- core orchestration depends on this
3. **Layer 2: Permission system** (allow/deny, agent modes) -- safety depends on this
4. **Layer 3: Hook system** (lifecycle events, blocking/injection) -- enforcement depends on this
5. **Layer 4: Skill system** (progressive disclosure, preloading) -- domain knowledge depends on this
6. **Layer 5: Context management** (monitoring, persistence, recovery) -- session viability depends on this
7. **Layer 6: Logging/audit** (audit trail, archiving) -- reproducibility depends on this
8. **Layer 7: DAAF conventions** (file-first, IAT, naming, versioning) -- research quality depends on this

**Detail level:** MEDIUM. Concise tables and a dependency diagram. Navigation aid, not a specification.

---

#### 12. DAAF's Distinctive Design Contributions
**Description:** These are DAAF's most original architectural inventions — capabilities that no surveyed harness provides out of the box and that represent DAAF's core value proposition for rigorous research. They must be custom-built on any target platform, and they are where the most design-intent documentation is needed. An implementer who understands these features deeply understands what makes DAAF different from a generic AI coding workflow.

**Feeds from:** Finding 09 (external harnesses), Findings 05, 06, 08

**Key content points — for each, document the design problem, the design solution, and the implementation:**
1. **Context self-monitoring with graduated responses** — the problem of LLM quality degradation at high utilization; DAAF's dual-threshold severity system with role-specific action protocols
2. **File-first execution protocol** — the problem of ephemeral, unauditable interactive execution; DAAF's write-execute-capture pattern with three enforcement layers
3. **Inline Audit Trail (IAT)** — the problem of opaque code that can't be reviewed without running it; DAAF's INTENT/REASONING/ASSUMES convention that makes every analytical decision explicit
4. **Immutable script versioning** — the problem of lost failure history; DAAF's _a/_b/_c progression that preserves every attempt as an audit artifact
5. **Defense-in-depth security architecture** — the problem of single-point-of-failure safety; DAAF's 9-layer coordinated enforcement from container isolation through behavioral guardrails
6. **Subagent early-return protocol** — the problem of subagents exhausting context and producing degraded output; DAAF's structured return format that preserves completed work when context pressure forces early termination

**Detail level:** VERY HIGH. These are DAAF's most distinctive and valuable features. Each needs full design-intent documentation, not just implementation details.

---

#### 13. Industry-Converged Standards
**Description:** Features where DAAF's patterns have become or are becoming cross-harness standards, reducing migration effort.

**Feeds from:** Finding 09 (external harnesses), Finding 03 (skill system)

**Key content points:**
1. **SKILL.md / Agent Skills** -- `agentskills.io` open standard, adopted by Codex and Cursor
2. **AGENTS.md / Custom instructions** -- de facto convention across all harnesses
3. **MCP (Model Context Protocol)** -- supported by 5 of 6 surveyed harnesses
4. **Hooks/lifecycle events** -- 4 of 5 harnesses support hooks, event names converging
5. **Subagent context isolation** -- now standard in Codex, OpenCode, Cursor

**Detail level:** MEDIUM. Migration-effort-reduction guide, not a deep specification.

---

### Part IV: Harness Landscape Reference

#### 14. Harness Comparison Matrix
**Description:** Condensed cross-reference of 5 alternative harnesses against DAAF's critical features. NOT a migration plan; an awareness resource.

**Feeds from:** Finding 09 (external harnesses -- primary)

**Key content points:**
- Critical features comparison matrix
- Readiness tiers: Tier 1 (Codex, Cursor -- closest parity), Tier 2 (OpenCode -- partial), Tier 3 (Windsurf, Aider -- significant gaps)
- Per-harness summary boxes
- CLI/container operation compatibility

**Detail level:** MEDIUM. Summarize rather than reproduce Finding 09 in full.

---

### Part V: Appendices

#### Appendix A: Complete Feature Inventory Table
Single master table listing every Claude Code feature DAAF depends on, with criticality, portability notes, interdependence count, and the findings file(s) that document it.

#### Appendix B: Complete Agent Inventory
Full 15-agent table with all frontmatter fields, from Finding 02.

#### Appendix C: Complete Skill Inventory
Full 36-skill table with metadata, from Finding 03.

#### Appendix D: Complete Hook Registration Map
Full registration table (settings.json + per-agent), from Finding 01.

#### Appendix E: Complete Permission Pattern Lists
Full allow (38) and deny (35) pattern lists, from Finding 04.

#### Appendix F: settings.json Complete Structure
Full 228-line settings.json with annotations.

#### Appendix G: Glossary
Definitions of DAAF-specific and Claude Code-specific terminology.

---

## Key Migration Dimensions (Ordered by Criticality)

| Priority | Dimension | Criticality | Key Challenge | Primary Findings |
|----------|-----------|-------------|---------------|-----------------|
| 1 | Instruction loading (CLAUDE.md + system reminders) | CRITICAL | Auto-injection into ALL agent contexts | 08, 04 |
| 2 | Agent system (definition, dispatch, isolation) | CRITICAL | Named agents with per-agent config and fresh context windows | 02, 07 |
| 3 | Hook system (lifecycle events, blocking) | CRITICAL | 5 event types with blocking and injection semantics | 01, 04 |
| 4 | Permission system (allow/deny, agent modes) | HIGH | Three-tier matching with agent-level read-only enforcement | 04, 02 |
| 5 | Skill system (progressive disclosure) | HIGH | Three-level loading with 250-char description triggering | 03, 02 |
| 6 | Context management (monitoring, persistence) | HIGH | Dual-threshold monitoring, compaction disabled, 5 persistence mechanisms | 05, 01 |
| 7 | Tool system (restrictions, conventions) | HIGH | Per-agent tool allowlists, file-first execution enforcement | 07, 02 |
| 8 | Logging and audit trail | MEDIUM | JSONL audit log, session archiving, run_with_capture | 06, 01 |
| 9 | Session management (recovery, archiving) | MEDIUM | Crash recovery, transcript conversion, log collection | 06, 05 |
| 10 | External harness landscape awareness | LOW | Informational; no implementation required | 09 |

---

## Identified Gaps (Areas Needing Additional Research)

1. **Exact Claude Code hook input JSON schema:** Finding 01 notes that the JSON schema is inferred from what scripts parse, not from an authoritative specification. If Claude Code publishes a formal hook API spec, this should be cross-referenced.

2. **Nested subagent hook firing:** Whether hooks fire for sub-subagents (agents spawned by agents) is not explicitly documented. DAAF's enforce-foreground-agents hook may prevent this scenario, but the behavior should be confirmed.

3. **StatusLine input schema:** The `context-bar.sh` script receives JSON from Claude Code's statusLine system, but the schema differs from hook schemas and is documented only by observation.

4. **ToolSearch/deferred tool internals:** Understanding is based on session log analysis, not formal documentation. The exact mechanism for tool schema loading is partially opaque.

5. **Permission evaluation order:** Whether deny rules always override allow rules, or whether there is a more nuanced evaluation order, is not formally documented. Finding 04 notes "deny wins over allow" but the specifics of edge cases are unclear.

6. **Compaction disable mechanism:** DAAF instructs users to disable auto-compact via the `/config` menu (a user-level setting), not via settings.json. Whether this setting persists across sessions and whether it can be programmatically enforced needs confirmation.

7. **Agent return size enforcement:** The 2000-word cap on agent returns is a DAAF convention enforced via instructions, not a Claude Code runtime limit. Whether the target harness should enforce this programmatically (e.g., via a hook) or via instructions is a design decision.

---

## Estimated Document Length

| Part | Estimated Words |
|------|----------------|
| Part I: Foundation (Sections 1-2) | 1,000 |
| Part II: Features (Sections 3-10) | 15,000-20,000 |
| Part III: Cross-Cutting (Sections 11-13) | 3,000 |
| Part IV: Harness Landscape (Section 14) | 2,000 |
| Part V: Appendices (A-G) | 5,000 |
| **Total** | **26,000-31,000** |

The guide will be a substantial reference document. The core (Part II) can be read section-by-section as needed; no one needs to read all 26K+ words sequentially.

---

## Writing Principles

1. **Design-intent-first:** Lead every feature with *why* it exists, not *how* it's implemented. An implementer who understands the design reasoning can make good decisions on any platform; one who only has configuration details will cargo-cult the wrong things. The "Design Choices and Rationale" subsection is the most valuable part of each feature section.

2. **Clearly distinguish native vs. built:** Every feature must explicitly label which parts are Claude Code primitives (available in the harness by default), which parts are DAAF's own design implemented on top of those primitives, and which are hybrid. This prevents implementers from assuming they need a harness feature when they actually need to build a layer, or vice versa.

3. **Self-contained:** Each section should be understandable without reading the rest. A developer porting just the hook system should be able to read Section 7 alone.

4. **Specification-grade detail:** Include file paths, exact configuration values, complete inventories. Vague descriptions are worthless; the guide must say exactly which hooks, exactly what they check, exactly how they fail, and exactly *why those choices were made*.

5. **Harness-neutral in specification, concrete in realization:** The "Replication Specification" subsection should describe requirements in platform-agnostic terms ("DAAF requires pre-execution interception of tool calls with the ability to block execution and return an error message"). The "Current Realization on Claude Code" subsection should be concrete and specific ("This is implemented via a PreToolUse hook registered in settings.json with matcher 'Bash', exit code 2 blocks execution, stderr message is shown to the model").

6. **Cross-referenced:** Every section should note which other features depend on it. Interdependencies are the hardest part of migration.

7. **Actionable:** Each section's "Replication Specification" should end with clear acceptance criteria: "Feature parity is achieved when X, Y, and Z hold true." Include degraded-mode options where full parity isn't achievable.

8. **Capture the "why" behind every setting:** Many DAAF configurations look arbitrary without context. Every permission pattern, every denied command, every blocked agent type has a reason. Document it. Example: "Named DAAF agents are NOT in the auto-allow list despite being DAAF's own agents — this ensures the user is always aware when a new specialist is dispatched, maintaining the transparency principle."

---

## Writing Strategy

**Recommended writing order:** Start with Part II Sections 3-7 (critical/high features) since they contain the most essential migration information. Appendices can be generated semi-mechanically from the findings files. Parts I and III-IV serve as framing and can be written last.

**Source material:** All 9 findings files in `findings/` contain specification-grade detail. The writing task is primarily synthesis and restructuring, not new research.
