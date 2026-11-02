---
name: agent-authoring
description: >-
  Guide for creating DAAF agent definition files. Covers 12-section template, hook registration, skills-in-frontmatter, integration checklist. Use when adding or revising agents. For SKILL.md files, use skill-authoring instead.
metadata:
  audience: any-agent
  domain: skill-development
---

# Agent Authoring

Guide for creating new DAAF agent definition files with full ecosystem integration. Covers the 12-section agent template, cross-agent consistency standards, per-agent hook registration, skills-in-frontmatter assignment, and the complete integration checklist for wiring new agents into documentation. Use when adding a new specialized agent, revising agent structure, configuring per-agent hooks, or verifying agent integration completeness. For creating SKILL.md files (not agent definition files), use skill-authoring instead.

Create new DAAF agents that conform to the canonical template and are fully wired into the system documentation for discoverability and usability.

## What This Skill Does

- Guides creation of agent `.md` files conforming to `agent_reference/AGENT_TEMPLATE.md` (12 mandatory sections)
- Ensures cross-agent consistency (standardized confidence model, Learning Signal, STOP format, etc.)
- Provides a **complete integration checklist** covering every file that references agents across the codebase to ensure it is discoverable and its invocation patterns are well-understood by the system agents
- Complements `skill-authoring`: this skill handles the behavioral protocol file; if the new agent also needs a companion skill, invoke `skill-authoring` separately

## Decision Tree: What Do You Need?

```
What are you doing?
│
├─ Creating a brand-new agent
│   └─ Follow "New Agent Workflow" below
│
├─ Revising an existing agent to match the template
│   └─ Read: references/template-walkthrough.md
│          + agent_reference/AGENT_TEMPLATE.md (the canonical blueprint)
│
├─ Checking if an agent is fully integrated into the ecosystem
│   └─ Read: references/integration-checklist.md
│
├─ Understanding what must be identical across all agents
│   └─ Read: references/cross-agent-standards.md
│
└─ Understanding the current agent landscape before adding to it
    └─ Read: .claude/agents/README.md (Agent Index + "Commonly Confused Pairs")
```

## New Agent Workflow

### Phase 1: Design (before writing)

Before locking in answers to the design questions below, consider whether a scoped online survey of analogous agent architectures and role designs — how other frameworks decompose specialist responsibilities, structure agent protocols, and draw boundaries between overlapping roles — would sharpen those answers. External grounding beats ungrounded inference: seeing how the problem has already been solved tends to produce a crisper role definition and a cleaner Core Distinction than reasoning from first principles alone. When the authoring is user-initiated, offer this survey to the user rather than deciding unilaterally. In Framework Development mode this is formalized as the **Pre-Authoring Research Offer** (`.claude/skills/daaf-orchestrator/references/framework-development-mode.md` § Pre-Authoring Research Offer), where the orchestrator dispatches a web-capable search-agent before authoring; outside that mode, apply the same instinct proportionately.

Before beginning, you MUST have a clear, coherent, and compelling answer to each of the following questions:

1. **Define the role** in one sentence — what does this agent do and why does it exist?
2. **Identify pipeline stage(s)** — which stage(s) does it operate in, or is it "any/on-demand"?
3. **Identify similar agents** — read `.claude/agents/README.md` (Agent Index + "Commonly Confused Pairs") to find the 1-3 most similar existing agents. You MUST differentiate from these in your Core Distinction table.
4. **Determine subagent type:**
   - `general-purpose` — needs file writes, code execution, or tool access beyond reading
   - `Plan` — read-only validation, discovery, or verification. For a named agent, read-only means a `tools` list with no Write or Edit; `permissionMode: plan` is ignored when the parent runs in auto, bypassPermissions or acceptEdits mode, so never rely on it
   - **Enumerate the `tools:` list explicitly, and never include `Agent` or `Task`.** Omitting the `tools:` field inherits ALL tools (including `Agent`), which would let the agent dispatch nested subagents. DAAF's dispatch-authority invariant is that all dispatch authority belongs to the orchestrator (see `agent_reference/BOUNDARIES.md` § Process Violations); a subagent returns work to the orchestrator for redelegation rather than nesting. Two other layers surround it — the harness spawn-depth limit (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` in settings.json `env`, which withholds Agent/Task from every subagent (observed 2026-11-02, Claude Code 2.1.281)) and the `block-nested-dispatch.sh` backstop hook — but the explicit `tools:` list is the layer you control as the agent author, and it holds even if the depth limit is lifted. Always spell it out.
   - **Never set `omitClaudeMd` in the frontmatter.** The field (added Claude Code 2.1.271) detaches the subagent from CLAUDE.md — DAAF's constitution for subagents, carrying the execution philosophy, file-first protocol, IAT standards, safety boundaries, and the context-threshold curve. An agent that omits it is silently unbound by all of them, and nothing in its own file would reveal that. No DAAF agent has a use case for it.
5. **Determine skill dependencies** — will this agent need to invoke any skills?
6. **Determine hook requirements** — will this agent need per-agent hooks? (see "Per-Agent Hooks" below)
7. **Determine model tier** — which model tier should this agent default to? `opus` for high-judgment, adversarial, or synthesis roles; `sonnet` for well-specified, mechanical, or skill-guided roles. Haiku is excluded by DAAF policy. See `.claude/skills/daaf-orchestrator/SKILL.md` > "Model Selection for Subagent Dispatch" for the routing rationale and the current per-agent tier table.

If any of these answers are vague, in doubt, or incomplete, the quality and reliability of the ensuing agent file will suffer. If the agent authoring process has been initiated by the user, make sure to ask these questions directly, and ask follow-up questions to enhance the quality of their responses as you go. Before proceeding to Phase 2, make sure the user agrees with your enhanced answers explicitly.

### Phase 2: Author (write the definition)

1. Read `agent_reference/AGENT_TEMPLATE.md` for the canonical 12-section structure
2. Read `references/template-walkthrough.md` for section-by-section guidance and common mistakes
3. Read `references/cross-agent-standards.md` for mandatory standardized elements
4. Write the agent file to `.claude/agents/[agent-name].md` following the template exactly
5. Run self-validation:
   - [ ] All 12 sections present (11 REQUIRED + 1 CONDITIONAL)
   - [ ] Core Distinction table differentiates from identified similar agents
   - [ ] Confidence Assessment uses standardized H/M/L model with rationale
   - [ ] Learning Signal uses standardized 5-category model
   - [ ] Anti-patterns in 4-column table format (# | Anti-Pattern | Problem | Correct Approach) (minimum 5)
   - [ ] STOP Conditions use standardized format
   - [ ] Invocation Pattern gives the `subagent_type` and points to the canonical invocation template (WORKFLOW_PHASE or mode reference file); a full Agent() example, if shown, matches that template, BASE_DIR line included when the template has one
   - [ ] COMPLETE criteria: minimum 3
   - [ ] INCOMPLETE criteria: minimum 3
   - [ ] Self-Check has minimum 4 questions
   - [ ] Total length 400-700 lines (flag if approaching 800+)
   - [ ] Large inline code blocks minimized (extract to `agent_reference/` only if shared across agents)
   - [ ] `enforce-file-first.sh` registered in frontmatter if `Bash` is in `tools`, read-only agents included (see "Per-Agent Hooks" below)
   - [ ] `model:` field present with a justified tier (`opus` or `sonnet` per DAAF policy; see design question 7)
   - [ ] `omitClaudeMd` absent from the frontmatter — it detaches the agent from CLAUDE.md, DAAF's constitution for subagents (see design question 4 and FRAMEWORK_INTEGRATION_CHECKLIST.md item A1d); probe with `grep -rn omitClaudeMd .claude/agents/`
   - [ ] Explicit `tools:` list present and does NOT include `Agent` or `Task` (dispatch-authority invariant — omitting the field inherits ALL tools including `Agent`; see design question 4 and FRAMEWORK_INTEGRATION_CHECKLIST.md item A1c)
   - [ ] Text follows `agent_reference/DOCUMENTATION_STANDARDS.md` for its audience: the agent file is agent-facing, so precise internal terms are fine; any message template in it that a user will read follows § S3 Plain for Users
   - [ ] `description` written for its primary reader, the orchestrator deciding when to dispatch: what the agent does, when to use it, and how it differs from its closest neighbor

### Phase 3: Integrate (wire into the ecosystem)

1. Read `agent_reference/FRAMEWORK_INTEGRATION_CHECKLIST.md` § 2 for the canonical checklist of registration points
2. Execute all [M] (mandatory) items — A1, A1b, A1c, A1d, A2-A5
3. Review and execute applicable [C] (conditional) items — A6-A13, A15-A16
4. Run cross-cutting consistency checks (§ 10) — count words, cross-references, naming
5. For supplementary walkthrough detail, also consult `references/integration-checklist.md`

### Phase 4: Validate (confirm completeness)

Run these verification checks:

```bash
# 1. Verify agent appears in the agent registry (expect 3+: index, When to Use, coordination matrix)
grep -c "agent-name" .claude/agents/README.md

# 2. Cross-agent consistency (run for new agent file)
grep -c "HIGH.*MEDIUM.*LOW\|BLOCKER.*WARNING.*INFO\|Learning Signal\|STOP Conditions" .claude/agents/[agent-name].md
```

### Phase 5: Human review

Before any agent authoring process is fully complete, a human user MUST review it for accuracy, intention, completeness, and value. When Phase 4 is complete, you MUST ask the user for review, providing as many details, file references, and decision points as possible to ensure full clarity for their awareness and revision if needed.

## Quick Reference: Current Agent Landscape

Consult `.claude/agents/README.md` for the authoritative Agent Index with:
- Agent name, purpose, subagent type, stage(s), and key distinction
- Commonly Confused Pairs (critical for writing your Core Distinction)
- Agent Coordination Matrix (producer/consumer relationships)
- Invocation patterns for every agent

## Reference Files

| File | When to Read | Purpose |
|------|-------------|---------|
| `references/template-walkthrough.md` | Writing or revising an agent | Section-by-section guidance for AGENT_TEMPLATE.md |
| `references/integration-checklist.md` | After writing, during Phase 3 | Complete list of files to update |
| `references/cross-agent-standards.md` | During writing, for consistency | Mandatory identical elements across all agents |

## Relationship to Other Skills and Resources

| Resource | Relationship |
|----------|-------------|
| `skill-authoring` skill | Invoke separately if the new agent also needs a companion skill |
| `agent_reference/AGENT_TEMPLATE.md` | The structural blueprint — read directly during Phase 2 |
| `agent_reference/PLAN_TEMPLATE.md` | Reference for wave-based task sequencing and plan structure |
| `.claude/agents/README.md` | The single source of truth for the agent landscape — read during Phase 1 |
| `data-ingest` agent | Related: creates new data source skills; agent-authoring creates new agents |

## Per-Agent Hooks

Agents can register hooks in their YAML frontmatter that fire only when that agent
is active. This is distinct from project-wide hooks in `settings.json` which fire
for all contexts.

**When to use per-agent hooks vs project-wide hooks:**

| Scope | Register in | Example |
|-------|-------------|---------|
| All agents, all contexts | `settings.json` | `bash-safety.sh` (destructive command prevention) |
| Specific agents only | Agent frontmatter `hooks` field | `enforce-file-first.sh` (file-first protocol for every agent with `Bash` in `tools`); `adjudicator-read-scope.sh` (citation-adjudicator's read boundary) |

**Per-agent hook for every Bash holder: `enforce-file-first.sh`**

Any agent with `Bash` in its `tools` list MUST register this hook. It blocks
direct `python`/`python3` and `Rscript` invocations (the whitelisted
`/daaf/scripts/` utilities excepted), enforcing the file-first execution
protocol at the hook layer. Read-only status is no exemption: under auto mode,
DAAF's normal parent mode, Claude Code ignores a subagent's `permissionMode`
(it also does under bypassPermissions and acceptEdits), so an agent with Bash
can run Python or write files whatever its frontmatter says. Only the `tools`
list (no Write/Edit) and this hook constrain it; the hook does not block other
writing commands (`quarto render`, redirects), so the agent's boundary text must.

Agents that register it (every Bash holder): research-executor, code-reviewer,
debugger, data-ingest, search-agent, source-researcher, research-synthesizer,
data-planner, notebook-assembler, report-writer, framework-engineer,
data-verifier, integration-checker, plan-checker, literature-searcher,
paper-reader, literature-synthesizer.

Agents without it: the orchestrator, and citation-adjudicator, whose `tools`
list is Read only (it reads one path named in its prompt and searches nothing;
it registers `adjudicator-read-scope.sh` instead, below).

A read-only agent that must search files usually needs Bash anyway: on native
Claude Code builds the Glob and Grep tools are absent (removed in 2.1.117;
anthropics/claude-code#80526) and search runs through Bash, so a `tools` list of
Read, Glob and Grep alone leaves the agent unable to search there. Keep Glob and
Grep in the list for builds that have them, add Bash with this hook, and limit
Bash to read-only inspection in the boundary text. An agent that only reads
paths its prompt names searches nothing, so it can hold Read alone and then
needs no `enforce-file-first.sh` (a hook that keeps it inside the files it
names is a separate matter: see the agent-specific hook below).

The hook can also block a harmless read-only search: it reads a `|` inside a
regex alternation as a pipe, so a `grep -E` pattern containing `|python3 `,
`;python ` or `|Rscript` is refused as direct interpreter execution. Pass the
alternatives as separate `-e` patterns instead (`grep -n -e 'foo' -e 'python3 x'`).
Every agent that searches through Bash should carry this tip in one line of its
search guidance, pointing here.

**Agent-specific hook: `adjudicator-read-scope.sh`** (citation-adjudicator
only). Read opens any path, so a Read-only `tools` list does not keep an agent
to the files its prompt names. This hook does that for the reference checker:
registered with `matcher: ""`, it sees every tool call of that agent, allows
only a Read of a bundle file (a canonical absolute path to an existing
`research/…/data/adjudication_bundles/{batch_id}.json`) and denies everything
else, fail-closed. Its coverage and limits are in `agent_reference/BOUNDARIES.md`
§ Defense-in-Depth Architecture, its tests in
`tests/bash/adjudicator_read_scope.bats`. Another agent that must stay inside
named files needs a hook of its own, drafted for the user to install (hooks are
user-only). Install the script before the frontmatter registers it: on Claude
Code 2.1.281 a registered hook whose script is missing does not block (verified
against the Claude Code hooks reference on 2026-10-27).

**Frontmatter syntax** (for `enforce-file-first.sh`; citation-adjudicator's
block has the same shape, with `matcher: ""` and its own command):

```yaml
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "$CLAUDE_PROJECT_DIR/.claude/hooks/enforce-file-first.sh"
          timeout: 5
```

**Hook authoring conventions:**
- Hook scripts live in `.claude/hooks/` and are protected by the deny rule `Edit(.claude/hooks/*)` — human-only deployment. An `Edit` rule covers all file-editing tools (`Write` included) — "Edit rules apply to all built-in tools that edit files", and `Write(path)` rules "never match" (Claude Code permissions docs; verified live on 2.1.261) — so no paired `Write(...)` rule is needed (adding one is inert and emits a startup warning). Shell-level writes to the same paths are blocked separately by `bash-safety.sh`
- Use `exit 2` with stderr message to block Bash commands (convention from `bash-safety.sh`)
- Use JSON `permissionDecision: deny` output for Agent/Task tool hooks (convention from `enforce-explore-model.sh`)
- A fail-closed guard on a non-Bash tool may print the JSON deny and also exit 2 (convention from `adjudicator-read-scope.sh`): exit 2 blocks even when the JSON is malformed, whereas JSON that cannot be parsed on an exit-0 path lets the call through (Claude Code hooks reference, verified 2026-10-27)
- Fail-closed design: ERR trap should block, not allow — and neither the trap nor the deny path may depend on the very tool whose absence they cover (pre-check `jq`; fall back to stderr + `exit 2`, never `jq -n`, so a missing dependency cannot turn a deny into a silent allow)
- Verify dependencies (e.g., `jq`) explicitly rather than relying on fallbacks that silently degrade

## Skills in Agent Frontmatter

Agents can preload skills via the `skills` frontmatter field. The skill is loaded
into the agent's context when it starts, providing domain knowledge without
requiring the agent to invoke the Skill tool.

**Syntax:**

```yaml
# Single skill
skills: data-scientist

# Multiple skills (YAML block list — matches official Claude Code docs)
skills:
  - data-scientist
  - polars
```

The full skill content is injected into the agent's context at startup. The agent
does NOT need to call the Skill tool for preloaded skills — doing so would load
the content a second time and waste context tokens.

**When to assign skills to an agent:**
- The agent routinely needs the skill's domain knowledge (e.g., all coding agents preload `data-scientist`)
- The skill provides methodology or conventions the agent must follow (not just reference data)
- The skill is small enough to fit without consuming excessive context

**When NOT to assign skills:**
- The agent only occasionally needs the skill — let it invoke via the Skill tool on demand instead
- The skill is large (e.g., data source skills with extensive reference tables) — on-demand loading is more context-efficient
- The skill is for a different domain than the agent's core responsibility

**Current skill assignments:**

| Skill | Assigned to |
|-------|-------------|
| `data-scientist` | research-executor, code-reviewer, debugger, data-ingest, data-planner, plan-checker, data-verifier, source-researcher, research-synthesizer, integration-checker, report-writer, notebook-assembler |
| `marimo` | notebook-assembler |
| `quarto` | notebook-assembler |
| `skill-authoring` | framework-engineer |
| `agent-authoring` | framework-engineer |
| `scholarly-search` | literature-searcher |
| `literature-review` | literature-searcher, literature-synthesizer |
| `pdf-reading` | paper-reader |

The table mirrors the agents' `skills:` frontmatter. Each new agent adds or extends its rows as part of its own registration; skills an agent loads on demand rather than preloading are not listed.

## Naming Convention

- **File:** `.claude/agents/[lowercase-hyphenated].md`
- **Frontmatter name:** `lowercase-hyphenated` (must match directory/file convention)
- **Title:** `# [Agent Name] Agent` (title case with "Agent" suffix)
- **Description:** Third person, includes WHAT the agent does AND WHEN to use it
- **Reserved leading words:** a new agent, mode or reference file's basename (a skill's directory name is unaffected, since its file is `SKILL.md`) must not start with `report`, `summary`, `findings` or `analysis` in any case (`reporting.md` too): framework-engineer, a subagent, could not create it with Write (CLAUDE.md § Project Conventions > Subagent File Output)
