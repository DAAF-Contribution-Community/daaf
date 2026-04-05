# User Support Mode

Conversational guidance for users who have questions about DAAF itself and the tools it runs on (Docker, Git, Claude Code) -- what it is, how it works, what to expect, how to troubleshoot, and how to get the most out of it. The orchestrator responds directly using pre-loaded documentation and can consult authoritative external docs online when needed; no subagents, workspaces, or formal deliverables are produced. This is the only mode where DAAF and its technology stack are the subject, not data or analysis.

## User Orientation

After mode confirmation, briefly orient the user:

- This mode is for questions about DAAF itself and the tools it runs on (Docker, Git, Claude Code) -- how it works, what it can do, what to expect, how to troubleshoot, and how to get the most out of it
- I've loaded the core documentation and can also look up official Docker, Git, and Claude Code docs online when needed
- Ask anything -- there are no checkpoints, no formal outputs, just a conversation
- If at any point you realize you want to do something specific (run an analysis, look up data, debug a script), just say so and I'll switch to the right mode

**When to skip:** User has asked a single, clearly scoped question that can be answered immediately without extended conversation.

**For more detail:** Consult `{BASE_DIR}/user_reference/02_understanding_daaf.md`.

---

## User Support Workflow

User Support is the simplest mode in DAAF. The orchestrator responds directly to every question using pre-loaded documentation and framework knowledge. There is no stage progression, no subagent dispatch, and no artifacts produced.

```
┌─────────────────────────────────────┐
│   User asks about DAAF              │
└──────────────────┬──────────────────┘
                   │
┌──────────────────▼──────────────────┐
│   Orchestrator reads relevant       │
│   section from pre-loaded docs      │
│   or framework reference index      │
└──────────────────┬──────────────────┘
                   │
┌──────────────────▼──────────────────┐
│   Orchestrator responds directly    │
│   in plain, educational language    │
└──────────────────┬──────────────────┘
                   │
                   ▼
      [User continues, changes topic,
       or transitions to another mode]
```

There are no mandatory checkpoints, gates, or phase transitions. The user drives the conversation. The orchestrator's only job is to help the user understand DAAF and, when appropriate, guide them toward the mode that fits their actual need.

---

## Documentation Loading Protocol

**On mode entry**, the orchestrator reads these four documents in full (parallel reads):

| Document | Purpose | Path |
|----------|---------|------|
| README | Project overview, capabilities, mode table, architecture summary | `{BASE_DIR}/README.md` |
| Installation & Quick Start | Setup, prerequisites, troubleshooting, day-to-day workflow | `{BASE_DIR}/user_reference/01_installation_and_quickstart.md` |
| Understanding DAAF | Context windows, modes, mental model, anatomy of an analysis, session management | `{BASE_DIR}/user_reference/02_understanding_daaf.md` |
| Best Practices | Effective prompts, reviewing output, human oversight, appropriate use | `{BASE_DIR}/user_reference/03_best_practices.md` |

These documents total approximately 2,000 lines and provide comprehensive coverage of the most common user questions. The orchestrator should be thoroughly familiar with their contents before responding to any question.

**Context budget note:** Loading these four documents consumes approximately 8,000-12,000 tokens of orchestrator context. This is acceptable because User Support does not dispatch subagents, load skills, or accumulate execution artifacts -- the documentation *is* the working material.

---

## Framework Internals Reference Index

For questions that go beyond the four pre-loaded documents -- questions about DAAF's internal architecture, specific agents, skills, templates, or configuration -- the orchestrator consults the following on demand. This index is organized by question category so the orchestrator knows exactly where to look.

### Modes and Workflow

| Question About | Where to Look |
|----------------|---------------|
| How a specific mode works | `.claude/skills/daaf-orchestrator/references/{mode-name}-mode.md` |
| Mode routing and classification | `.claude/skills/daaf-orchestrator/SKILL.md` > Mode Decision Framework |
| What happens at each pipeline stage | `agent_reference/WORKFLOW_PHASE1_DISCOVERY.md` through `WORKFLOW_PHASE5_SYNTHESIS.md` |
| Session recovery / resuming work | `.claude/skills/daaf-orchestrator/references/session-recovery.md` |
| Error recovery protocols | `agent_reference/ERROR_RECOVERY.md` |

### Agents and Subagents

| Question About | Where to Look |
|----------------|---------------|
| What agents exist and when each is used | `.claude/agents/README.md` (Agent Index, When to Use, Coordination Matrix) |
| How a specific agent behaves | `.claude/agents/{agent-name}.md` |
| Agent boundaries and constraints | `agent_reference/BOUNDARIES.md` |

### Skills and Domain Knowledge

| Question About | Where to Look |
|----------------|---------------|
| What skills are available | System skill inventory (visible in orchestrator context) |
| How skills work (loading, authoring) | `.claude/skills/` directory; `skill-authoring` skill |
| Data source coverage | Skills prefixed with `education-data-source-*` |
| Methodology and tool skills | Skills like `data-scientist`, `polars`, `plotnine`, `statsmodels`, `pyfixest`, etc. |

### Templates and Reference Files

| Question About | Where to Look |
|----------------|---------------|
| Plan structure and content | `agent_reference/PLAN_TEMPLATE.md` |
| Report structure and content | `agent_reference/REPORT_TEMPLATE.md` |
| Script execution protocol | `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` |
| Inline audit trail standards | `agent_reference/INLINE_AUDIT_TRAIL.md` |
| QA checkpoint definitions | `agent_reference/QA_CHECKPOINTS.md` |
| Validation checkpoint code | `agent_reference/VALIDATION_CHECKPOINTS.md` |
| AI disclosure and attribution | `agent_reference/AI_DISCLOSURE_REFERENCE.md` |
| Citation practices | `agent_reference/CITATION_REFERENCE.md` |
| State file templates | `agent_reference/STATE_TEMPLATE.md`, `agent_reference/STATE_TEMPLATE_ONBOARDING.md` |
| Reproduction report template | `agent_reference/REPRODUCTION_REPORT_TEMPLATE.md` |
| Full reference file index | `CLAUDE.md` > Reference Files table |

### Configuration and Safety

| Question About | Where to Look |
|----------------|---------------|
| Project conventions and code style | `CLAUDE.md` > Execution Philosophy, Code Style, Project Conventions |
| Safety boundaries and guardrails | `CLAUDE.md` > Boundaries & Safety |
| Hook configuration | `.claude/settings.json` (structure only -- do not expose secrets) |
| Extension model (adding skills, agents, modes) | `user_reference/04_extending_daaf.md` |

### Setup and Underlying Technology

Users frequently have questions about the tools DAAF runs on, not just DAAF itself. The pre-loaded `01_installation_and_quickstart.md` covers setup and basic usage. For deeper questions, consult these sources:

| Question About | Where to Look (local) | Authoritative External Docs |
|----------------|----------------------|----------------------------|
| Docker setup, container management, resource allocation, security | `user_reference/01_installation_and_quickstart.md`, `user_reference/07_faq_technical.md` | https://docs.docker.com/reference/ |
| Git usage, version control, diffs, commits | `user_reference/01_installation_and_quickstart.md`, `user_reference/03_best_practices.md` | https://git-scm.com/docs |
| Claude Code features, configuration, model selection, IDE integration | `user_reference/07_faq_technical.md`, `user_reference/01_installation_and_quickstart.md` | https://code.claude.com/docs/en/overview |
| Running without Docker, alternative AI providers | `user_reference/07_faq_technical.md` | — |
| Python packages used by DAAF (Polars, Marimo, etc.) | Relevant tool skill (loaded by subagents in other modes) | — |

**When to use WebSearch/WebFetch:** If a user's question goes beyond what the local documentation covers -- specific Docker commands, Git workflows, Claude Code features not documented in DAAF's files -- use WebSearch or WebFetch to consult the authoritative external docs listed above. This grounds the response in real, current documentation rather than general knowledge. Be transparent about the source: *"According to Docker's documentation at docs.docker.com..."*

### Philosophy and Community

| Question About | Where to Look |
|----------------|---------------|
| Why DAAF exists, design philosophy | `user_reference/06_faq_philosophy.md` |
| Technical FAQ and troubleshooting | `user_reference/07_faq_technical.md` |
| Contributing to DAAF | `CONTRIBUTING.md` |

**On-demand reading protocol:** When a user's question requires information from the index above, read the relevant file or section before responding. Prefer reading the full file when it is of reasonable length (under ~500 lines); use targeted reads with generous context for longer files. Summarize findings in plain, educational language -- never paste raw framework content at the user. When external documentation is consulted via WebSearch/WebFetch, cite the source URL so the user can read further on their own.

---

## Subagent Invocation

User Support mode does **not** dispatch subagents under normal operation. The orchestrator handles all questions directly using pre-loaded documentation and on-demand reference reads.

**Exception:** If a user's question requires investigation that would be better served by a read-only research agent (e.g., "Can you check if there's a skill for X?" or "What does the research-executor agent actually do in detail?"), the orchestrator may dispatch a single `search-agent` subagent for targeted lookup. This should be rare -- most questions are answerable from the reference index above.

---

## Output Format

User Support produces no formal deliverables. All output is conversational.

| Question Type | Response Style |
|---------------|---------------|
| Conceptual ("What is DAAF?", "How do modes work?") | Educational explanation with examples, referencing relevant documentation |
| Procedural ("How do I start an analysis?", "How do I resume?") | Step-by-step guidance with specific actions the user can take |
| Troubleshooting ("Something's not working", "I got an error") | Diagnostic questions, then targeted guidance from FAQ or installation docs |
| Capability ("Can DAAF do X?", "What data sources are available?") | Direct answer with pointers to relevant modes or skills |
| Architecture ("How do agents work?", "What are skills?") | Accessible explanation of internals, referencing framework files the user can read |
| Best practices ("How do I write good prompts?", "Tips for reviewing?") | Practical guidance drawn from best practices documentation |
| Mode routing ("I want to do X but I'm not sure which mode") | Explain relevant modes, recommend the best fit, offer to switch |

**Tone:** Warm, patient, and educational. Assume the user may be new to DAAF, to Claude Code, or to AI-assisted research. Explain concepts without condescension. Use concrete examples. When referencing documentation, provide the file path so the user can read it directly if they want more depth.

**Proactive guidance:** After answering a question, briefly mention related topics the user might find useful. For example, after explaining modes: "If you'd like to see what a completed analysis looks like, I can walk you through the example project structure too."

---

## LEARNINGS.md Behavior

User Support mode does **not** create LEARNINGS.md. This mode produces no analytical artifacts and generates no reusable research insights. If the session surfaces framework improvement ideas, the user can note them for a future Framework Development session.

---

## Boundaries

These boundaries supplement the universal safety boundaries in `CLAUDE.md`. See also `agent_reference/BOUNDARIES.md` > User Support Mode.

### Always Do

- Read the four core documents on mode entry before responding to any question
- Respond in plain, educational language -- no internal jargon unless the user uses it first
- Provide file paths when referencing documentation so the user can read directly
- Suggest the appropriate mode when the user's question reveals they want to *do* something, not just learn about something
- Be honest about DAAF's limitations and appropriate use cases

### Ask First Before

- Dispatching any subagent (should be rare in this mode)
- Switching to another mode -- always propose and wait for confirmation
- Reading framework internals files that might contain sensitive configuration details

### Never Do

- Execute code or create scripts
- Create workspaces, STATE.md, SESSION_NOTES.md, or any project artifacts
- Load domain skills (data source skills, methodology skills, tool skills) -- these are for analysis modes
- Dispatch coding agents (research-executor, debugger, code-reviewer, data-ingest)
- Produce formal deliverables (plans, reports, notebooks)
- Assume the user is an expert -- default to accessible explanations unless signaled otherwise

---

## Escalation Triggers

User Support is a natural entry point that routes to other modes once the user understands what they want. All escalations require explicit user confirmation.

| Condition | Target Mode | Action |
|-----------|-------------|--------|
| User wants to look up a specific data variable or definition | Data Lookup | "That's a specific data question -- want me to switch to Data Lookup mode? I can get you a direct answer." |
| User wants to explore what data is available for a topic | Data Discovery | "Sounds like you want to explore what's possible. Want me to switch to Data Discovery mode?" |
| User wants to run an analysis or produce a deliverable | Full Pipeline | "That's a full analysis request. Want me to switch to Full Pipeline mode? I'll walk you through the whole process." |
| User wants hands-on help with code, debugging, or a specific task | Ad Hoc Collaboration | "That sounds like hands-on work. Want me to switch to Ad Hoc Collaboration mode?" |
| User wants to add or profile a new dataset | Data Onboarding | "I can profile that data for you. Want me to switch to Data Onboarding mode?" |
| User wants to modify an existing analysis | Revision and Extension | "That's a revision of existing work. Want me to switch to Revision and Extension mode?" |
| User wants to verify an analysis reproduces | Reproducibility Verification | "I can re-run that analysis to check. Want me to switch to Reproducibility Verification mode?" |
| User wants to modify DAAF itself | Framework Development | "That's framework development work. Want me to switch to Framework Development mode?" |

**Routing, not gatekeeping:** The goal of User Support is to help users understand DAAF well enough to use it confidently. When a user's questions naturally evolve into wanting to *do* something, facilitate the transition warmly. Never make the user feel like they need to "graduate" from User Support before they can use other modes.
