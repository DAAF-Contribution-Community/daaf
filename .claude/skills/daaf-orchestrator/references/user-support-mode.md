# User Support Mode

Conversational guidance for users who have questions about DAAF itself and the tools it runs on (Docker, Git, Claude Code) -- what it is, how it works, what to expect, how to troubleshoot, and how to get the most out of it. The orchestrator responds directly using pre-loaded documentation and can consult authoritative external docs online when needed; no workspaces or formal deliverables are produced, and no subagents are used by default (a single `search-agent`, with the user's approval, is the one exception). This is the only mode where DAAF and its technology stack are the subject, not data or analysis.

## User Orientation

The mode confirmation already gave the user this preview, so do not repeat it after confirmation. Present these points only when the user signals they are new to DAAF or asks for more detail.

- This mode is for questions about DAAF itself and the tools it runs on (Docker, Git, Claude Code) -- how it works, what it can do, what to expect, how to troubleshoot, and how to get the most out of it
- I read DAAF's core documentation when this mode starts, read anything you point me to before answering about it, and can also look up official Docker, Git, and Claude Code docs online when needed
- Ask anything -- there are no checkpoints, no formal outputs, just a conversation
- If at any point you realize you want to do something specific (run an analysis, look up data, debug a script), just say so and I'll switch to the right mode

**For more detail:** Consult `{BASE_DIR}/user_reference/02_understanding_daaf.md`.

---

## Scope Check

- **Tier:** None. This mode is a conversation, so there is no scope step.
- **Read first:** the four core documents on mode entry (§ Documentation Loading Protocol), and anything the user points to (a file, an error message they saved, a docs page) before answering about it. A web page goes through `web_fetch.sh` (the `web-retrieval` skill). A PDF needs the single `search-agent` digest, so ask first (§ Subagent Invocation).
- **Where fetches land:** this mode never creates a workspace, so every `web_fetch.sh` call in it (a page the user pointed to, or official docs consulted later) uses the session's staging folder, `{scratchpad}/scope_staging/web_fetches/`, as DEST_DIR (`SKILL.md` § Scope Check > Read First). A PDF digest's ingest and record go to the same staging folder: the PDF into `{scratchpad}/scope_staging/papers/` and the record to `{scratchpad}/scope_staging/{date}_{slug}_materials-digest.md`. The staged files stay there; answers cite the URL or title, never the staged path.
- **If reading shows the user wants to do something:** propose the matching mode (§ Escalation Triggers) rather than widening this one.
- **Update-conflict walkthrough:** the mode confirmation is skipped when the updater launched the session and is waiting (one of the exceptions listed in `SKILL.md` § Mode Confirmation Gate); the conflicted files are read in step 2 before any resolution is proposed, and each resolution waits for the user's approval file by file.

The tier table is in `SKILL.md` § Scope Check.

---

## User Support Workflow

User Support is the simplest mode in DAAF. The orchestrator responds directly to every question using pre-loaded documentation and framework knowledge. There is no stage progression, no subagent dispatch by default (the one ask-first exception is in § Subagent Invocation), and no artifacts produced.

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

These documents total about 3,500 lines and provide comprehensive coverage of the most common user questions. The orchestrator should be thoroughly familiar with their contents before responding to any question.

**Context budget note:** The four documents hold about 62,500 words (`wc -w`), so loading them takes a large share of the orchestrator's context before the first answer. This is acceptable because User Support does not normally dispatch subagents, load skills, or accumulate execution artifacts -- the documentation *is* the working material. Watch the context-reporter's utilization in a long session as usual (CLAUDE.md § Context & Session Health).

---

## Framework Internals Reference Index

For questions that go beyond the four pre-loaded documents -- questions about DAAF's internal architecture, specific agents, skills, templates, or configuration -- the orchestrator consults the following on demand. This index is organized by question category so the orchestrator knows exactly where to look.

### Modes and Workflow

| Question About | Where to Look |
|----------------|---------------|
| How a specific mode works | `.claude/skills/daaf-orchestrator/references/{mode-name}-mode.md` |
| Mode routing and classification | `.claude/skills/daaf-orchestrator/SKILL.md` > Mode Decision Framework |
| The privacy-preserving / synthetic-data path (sensitivity gate) within Data Onboarding | `synthetic-data-workflow` skill + `.claude/skills/daaf-orchestrator/references/data-onboarding-mode.md` (DI-1 sensitivity gate) |
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
| Using DAAF with sensitive data that can't enter the container (synthetic-data protocol) | `synthetic-data-workflow` skill (privacy-preserving workflow: profile locally → share a disclosure-controlled report → DAAF builds a synthetic stand-in) |

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
| Bind mounts / sharing host folders into the container | `user_reference/01_installation_and_quickstart.md`, `user_reference/07_faq_technical.md` | https://docs.docker.com/engine/storage/bind-mounts/ |
| Running Claude and ChatGPT installs in parallel / sharing one research workspace | `user_reference/01_installation_and_quickstart.md`, `user_reference/07_faq_technical.md` | https://docs.docker.com/reference/compose-file/volumes/ |
| Git usage, version control, diffs, commits | `user_reference/01_installation_and_quickstart.md`, `user_reference/03_best_practices.md` | https://git-scm.com/docs |
| Claude Code features, configuration, model selection, IDE integration | `user_reference/07_faq_technical.md`, `user_reference/01_installation_and_quickstart.md` | https://code.claude.com/docs/en/overview |
| Running without Docker, alternative AI providers | `user_reference/07_faq_technical.md` | — |
| Python packages used by DAAF (Polars, Marimo, etc.) | Relevant tool skill (loaded by subagents in other modes) | — |

**When to use web access:** If a user's question goes beyond what the local documentation covers -- specific Docker commands, Git workflows, Claude Code features not documented in DAAF's files -- use WebSearch to find the authoritative external docs listed above and the DAAF fetch protocol (`bash /daaf/scripts/web_fetch.sh URL DEST_DIR`; the built-in WebFetch is blocked — see the `web-retrieval` skill) to retrieve them. DEST_DIR is the session's staging folder, `{scratchpad}/scope_staging/web_fetches/`, because this mode has no workspace (§ Scope Check). This grounds the response in real, current documentation rather than general knowledge. Be transparent about the source: *"According to Docker's documentation at docs.docker.com..."*

**When the user suspects a broken install.** DAAF's maintainers check installs with a deployment smoke test (the `daaf-deploy-smoke-testing` skill). It is a maintainer diagnostic, not a supported health command, but its free checks can be borrowed for troubleshooting. Offer it, say what it is, and let the user decide:

- **The command.** The user runs it themselves with the `!` prefix, so the output lands in the conversation (this mode runs no code itself): `! python3 /daaf/scripts/deploy_smoke/run_deploy_smoke.py --route <route> --tiers 0,N --yes`. Tiers 0 and N make no model call and cost nothing. The run writes a report folder and a package under `scripts/deploy_smoke/`, both kept out of git.
- **`--route`** is the install type the user names: `anthropic-subscription` (Claude subscription), `anthropic-api` (Anthropic API key), `openrouter`, `chatgpt-subscription` or `openai-api` (GPT through the provider shim). If they are unsure, start with `anthropic-subscription`: the first lines of the output name the `Detected route`, worked out from which settings are present. When it differs, T0.1 fails for that reason alone, so re-run with the detected route before reading anything else.
- **Reading it.** Near the end, `Report written: <folder>` names the report folder (the package and copy steps printed after it are for maintainers; the user can ignore them). Read that folder's `report.md` Diagnosis summary and explain each FAIL and WARN in plain language: what it means, and what the user can do about it. The skill's `references/interpreting-results.md` row for each probe gives the meaning and the fix. A WARN is often harmless.
- **A paid check, only on request.** Tier 1 (`--tiers 1 --yes`, the same route) makes one real model call, billed to or drawn from the user's plan. Offer it only if the user asks to go further, and say first that it costs one model call; `--yes` skips the runner's own cost prompt, so add it only once the user has agreed.

### Philosophy and Community

| Question About | Where to Look |
|----------------|---------------|
| Why DAAF exists, design philosophy | `user_reference/06_faq_philosophy.md` |
| Technical FAQ and troubleshooting | `user_reference/07_faq_technical.md` |
| Contributing to DAAF | `CONTRIBUTING.md` |

**On-demand reading protocol:** When a user's question requires information from the index above, read the relevant file or section before responding. Prefer reading the full file when it is of reasonable length (under ~500 lines); use targeted reads with generous context for longer files. Summarize findings in plain, educational language -- never paste raw framework content at the user. When external documentation is consulted via WebSearch and the DAAF fetch protocol (`web-retrieval` skill), cite the source URL so the user can read further on their own.

---

## Update Conflict Resolution Walkthrough

This walkthrough helps a user finish a DAAF update whose changes conflict with their
own. The conflicts come from the updater (`update_daaf.sh` on macOS and Linux,
`update_daaf.ps1` on Windows), and the user reaches this mode in one of two ways.
The closing step differs between them, so tell them apart first:

| How the session started | How to tell | What the updater is doing |
|-------------------------|-------------|---------------------------|
| **Updater waiting.** The user chose option 1, "Launch Claude Code to help resolve the conflicts"; the updater started Claude Code with `docker compose exec -it` and printed a prompt to paste | The prompt is the updater's own text: it starts "User support mode. I just ran the DAAF updater…" or "User support mode. The DAAF updater applied the framework update successfully…", and asks you to remind the user to type `/exit` | Waiting on the host for `/exit`, then finishing its remaining steps |
| **Updater not waiting.** The user started an ordinary session (`bash run_daaf.sh`, `.\run_daaf.ps1` on Windows) to get help. The updater suggests this after a stash conflict when the user chooses option 2, "Exit and resolve manually", and whenever conflicts are still unresolved after an updater-launched session ends; a user resolving by hand may also ask | Any other request for help with update conflicts, or the user says the updater window has closed. If you cannot tell, ask | Exited. After a merge or rebase conflict it recorded where it stopped, and running it again finishes the update; after a stash conflict it has already finished |

### Conflict types

The updater's prompt names one of three conflict types. The resolution
walkthrough (steps 1–5 below) is the same for all three — only the completion
command in step 4 differs.

| Prompt mentions | What happened | Completion command (step 4) |
|-----------------|---------------|---------------------------|
| "merge conflicts" | The updater merged the update into the user's branch, and the update and the user's own commits changed the same lines | `git commit -m "Resolved merge conflicts from DAAF update"` |
| "rebase conflicts" | User chose rebase; the squashed local commit conflicts with upstream | `git rebase --continue` |
| "stash conflicts" | The update itself succeeded, but the user's uncommitted edits (set aside before the update) conflict with the updated files when put back | `git stash drop` (the stash contents are already in the working tree). No commit: the edits were uncommitted and stay uncommitted, as the updater's prompt says ("Do not commit") |

**Commits in this walkthrough.** CLAUDE.md § User Preferences sets "Git commit
management: disabled", under which no agent runs `git commit`. This walkthrough is
a deliberate exception to that preference, scoped to this walkthrough alone: the
user chose to resolve the update's conflicts with DAAF, and the update is not
finished until the merge is committed or the rebase continued. So after the user
has approved the resolutions, you run the merge or rebase completion command
yourself. The stash case never commits.

### What the orchestrator must do

**1. Classify as User Support mode.** When the updater is waiting, its "User
support mode" prefix is an explicit mode signal: skip the mode confirmation gate,
because the user asked for this help by choosing option 1 in the updater (one of
the exceptions listed in `SKILL.md` § Mode Confirmation Gate). When it is not
waiting, confirm the mode as usual (the User Support template), then continue here.

**2. Determine the conflict type** — check the user's prompt for "merge",
"rebase", or "stash". If it does not say, `git status` shows whether a merge or a
rebase is in progress; unmerged files with neither in progress are a stash
conflict. Then identify the conflicting files:
`git diff --name-only --diff-filter=U`. Read each one to understand both sides.

**3. Walk the user through resolution interactively** — for each file:
- Explain what the local side is (the user's customization) and what the
  upstream side is (the DAAF update)
- Recommend which version to keep, or how to merge both intelligently
- **Do not resolve or edit any file without the user's explicit approval.** Present the
  proposed resolutions file-by-file and wait for confirmation for each individual case before making changes.
- After the user approves a given resolution, edit the file to remove all conflict
  markers (`<<<<<<<`, `=======`, `>>>>>>>`) and run `git add <file>` for that file.
  Never `git add .` or `git add -A`: the user's untracked research folders must stay
  out of git. (The updater's own prompt stages with `git add -u`, which stages only
  files git already tracks, to the same effect.)
- **Watch for escalation signals** — see "Escalation to Framework Development"
  below. If you detect them, flag the situation before continuing with
  mechanical resolution.

**4. Complete the git operation** — after all files are resolved, run the
completion command from the table above for the conflict type (see "Commits in
this walkthrough"). Then check `git status`: no unmerged paths remain, and no
merge or rebase is in progress. The tree is not expected to be clean: the user's
untracked research folders are usually listed, and after a stash conflict so are
the user's own restored edits. Never stage or commit those to make it look clean.

**5. Tell the user how to finish the update.** It depends on how the session
started:

| | Merge or rebase conflict | Stash conflict |
|---|---|---|
| **Updater waiting** | The user types `/exit` and control returns to the updater. It puts back any uncommitted edits it set aside before the update (if those conflict, it offers this walkthrough again, as a stash conflict), syncs its host scripts and checks whether a Docker rebuild is needed | The user types `/exit`; the updater syncs its host scripts and checks whether a Docker rebuild is needed |
| **Updater not waiting** | The user leaves this session and runs the updater again from the host terminal: `bash update_daaf.sh`, or `.\update_daaf.ps1` on Windows. It picks up where it stopped: it puts back any set-aside edits and finishes the same remaining steps | Nothing more to run: the updater finished its remaining steps before it exited |

If the user closes the terminal instead of typing `/exit` while the updater is
waiting, the updater's remaining steps are skipped. Tell the user, in the matching
form:

> Updater waiting, merge or rebase: "All the conflicts are resolved, and git has
> finished combining the update with your changes. Type `/exit` now to return to
> the updater so it can finish up. (If the updater already stopped and told you
> some conflicts remain or the update isn't finished, it isn't waiting: type
> `/exit`, then run it again from your host terminal instead: `bash update_daaf.sh`,
> or `.\update_daaf.ps1` on Windows. It picks up where it stopped.)"
>
> Updater waiting, stash: "All the conflicts are resolved. Your own edits are back
> in place, still uncommitted, just as they were before the update. Type `/exit`
> now to return to the updater so it can finish up."
>
> Updater not waiting, merge or rebase: "All the conflicts are resolved, and git
> has finished combining the update with your changes. To finish the update, type
> `/exit` to leave this session, then run the updater again from your host terminal:
> `bash update_daaf.sh` (on Windows, `.\update_daaf.ps1`). It picks up where it
> stopped."
>
> Updater not waiting, stash: "All the conflicts are resolved. Your own edits are
> back in place, still uncommitted, just as they were before the update. The
> updater already finished its other steps, so there's nothing more to run."

### Escalation to Framework Development

Sometimes update conflicts are symptoms of a deeper integration problem. Resolving
the conflict markers lets git finish the update, but the user's customization may
not actually *work* with the updated framework. Watch for these signals during
step 3:

**Escalation signals:**

| Signal | What It Suggests |
|--------|-----------------|
| Conflicts in an agent, mode, or skill file where the upstream side restructured sections, renamed fields, or changed the template format | The customization needs architectural re-integration, not just a merge fix |
| User's custom component references registration points (tables, escalation paths, loading trees) that moved or changed structure upstream | Cross-file wiring is broken — resolving one file won't fix the integration |
| Multiple interconnected files conflict (e.g., a custom mode's reference file + its entries in the orchestrator skill + BOUNDARIES.md) | The customization is a multi-component modification that needs systematic re-integration |
| After resolving conflict markers, the merged result contains contradictions (e.g., a section references a field that no longer exists, or a table row doesn't match the new column structure) | Mechanical merge produced a syntactically clean but semantically broken artifact |
| User asks "how do I make my customization work with this new version?" or "will my changes still work?" | The user recognizes the problem goes beyond conflict markers |

**When signals are detected:**

1. **Finish the git operation first** (steps 4-5): the update is not finished
   until it is done. Resolve conflict markers to the best
   reasonable approximation (favor upstream for structural changes, preserve the
   user's *intent* in comments if needed). Complete the merge/rebase/stash-drop.
2. **Tell the user what you observed.** Be specific about which files have
   deeper integration issues and why mechanical resolution isn't sufficient.
3. **Propose the escalation:**

> "The conflicts are resolved, so the update can finish: [updater waiting: type
> `/exit` and let the updater finish / not waiting, merge or rebase: run the
> updater again as I described / not waiting, stash: nothing more to run]. But I
> noticed that your [customization description] may need more than a merge fix to
> work with the updated framework — [brief explanation of what changed upstream].
> After the update finishes, you can start a new session and ask me to help with
> that in Framework Development mode. I'd scope what changed, check how your
> customization connects, and re-integrate it properly."

4. **Do not attempt Framework Development work in this session.** Framework
   Development requires a normal session with full scoping and checkpoints, and
   when the updater is waiting it is still running on the host until `/exit`.
   The user finishes the update (step 5), then starts a new session.

---

## Subagent Invocation

User Support mode does **not** dispatch subagents under normal operation. The orchestrator handles all questions directly using pre-loaded documentation and on-demand reference reads.

**Exception:** If a user's question requires investigation that would be better served by a research agent (e.g., "Can you check if there's a skill for X?" or "What does the research-executor agent actually do in detail?"), the orchestrator may dispatch a single `search-agent` subagent for targeted lookup. This should be rare -- most questions are answerable from the reference index above.

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

**Proactive guidance:** After answering a question, briefly mention related topics the user might find useful. For example, after explaining modes: "If you'd like to see what a completed analysis looks like, I can walk you through the project structure in `user_reference/02_understanding_daaf.md`."

**Turn-end briefing.** Even in this purely conversational mode, close a substantive turn by orienting the user to what you covered and what they can do next, following DAAF's Turn-End Briefing standard — lead with the answer, spend the user's attention only where it earns its place, and resist over-structuring a short reply. See the master statement in `SKILL.md` § User-Facing Communication Standards > "Turn-End Briefing."

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
- Editing a conflicted file in the update-conflict walkthrough: each resolution waits for the user's approval, file by file (§ Update Conflict Resolution Walkthrough)

### Never Do

- Execute code or create scripts. The one exception is the update-conflict walkthrough: editing the conflicted files the user approved and running its git commands (`git status`, `git diff`, `git add <file>`, the completion command), as § Update Conflict Resolution Walkthrough describes
- Create workspaces, STATE.md, SESSION_NOTES.md, or any project artifacts (`web_fetch.sh` artifacts, and a PDF digest's ingest and record, go to the session's staging folder, which is not a workspace: § Scope Check)
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
| User wants to do a literature review (find and review the published research on a question), not learn how one works | Literature Review | "That sounds like a literature review. Want me to switch to Literature Review mode? I'll search the published research with you and check every reference." |
| User wants to run an analysis or produce a deliverable | Full Pipeline | "That's a full analysis request. Want me to switch to Full Pipeline mode? I'll walk you through the whole process." |
| User wants hands-on help with code, debugging, or a specific task | Ad Hoc Collaboration | "That sounds like hands-on work. Want me to switch to Ad Hoc Collaboration mode?" |
| User wants to add or profile a new dataset | Data Onboarding | "I can profile that data for you. Want me to switch to Data Onboarding mode?" |
| User wants to modify an existing analysis | Revision and Extension | "That's a revision of existing work. Want me to switch to Revision and Extension mode?" |
| User wants to verify an analysis reproduces | Reproducibility Verification | "I can re-run that analysis to check. Want me to switch to Reproducibility Verification mode?" |
| User wants to modify DAAF itself | Framework Development | "That's framework development work. Want me to switch to Framework Development mode?" |
| Update conflict resolution reveals customizations that need architectural re-integration beyond merge fixes | Framework Development | Follow the "Escalation to Framework Development" procedure above. User-facing message: "The conflicts are resolved, but your [customization] may need deeper re-integration with the updated framework. Once the update has finished, start a new session and ask me to help in Framework Development mode." |

**Routing, not gatekeeping:** The goal of User Support is to help users understand DAAF well enough to use it confidently. When a user's questions naturally evolve into wanting to *do* something, facilitate the transition warmly. Never make the user feel like they need to "graduate" from User Support before they can use other modes.
