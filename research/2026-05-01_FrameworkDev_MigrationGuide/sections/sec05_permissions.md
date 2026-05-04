## 5. Permission and Security System

**Classification: HYBRID** -- Claude Code provides the allow/deny pattern matching engine and agent permission modes. DAAF designed the specific pattern set, the 9-layer defense-in-depth architecture, the coordinating enforcement hooks, the credential management strategy, and the behavioral guardrails that together form the security model.

**Criticality:** HIGH | **Interdependencies:** 6 (agent system, hook system, instruction loading, logging/audit, context management, tool system)

---

### Design Intent

AI-assisted research requires broad tool access for productivity, yet the AI cannot be fully trusted not to make destructive mistakes, leak sensitive information, or circumvent its own guardrails. DAAF addresses this through **defense-in-depth**: multiple independent protection layers, each covering a different attack surface, so that no single-point failure compromises the system.

Three principles guide the design:

1. **Transparency over convenience.** The researcher must see and approve consequential actions. This means erring on the side of prompting for confirmation rather than auto-allowing, even for operations that are technically safe, because visibility into what the AI does is itself a form of safety.
2. **Enforcement over instruction.** Where a constraint is critical, it must be enforced programmatically (via hooks, permission modes, or deny rules), not merely stated in instructions. Instructions can be ignored or misinterpreted; runtime restrictions cannot.
3. **Layered redundancy.** Each critical protection is enforced by at least two independent mechanisms. Credential access, for example, is blocked at three separate layers -- any one of which would be sufficient, but all three exist because any single layer might fail.

---

### What It Does

The permission and security system controls what the AI agent can do, what it cannot do, and what requires human approval. It operates across nine layers, from the outermost OS-level containment to the innermost behavioral instructions. The system resolves every tool invocation into one of three outcomes: **auto-approved** (the tool executes immediately), **hard-blocked** (the tool is prevented from executing with an error message), or **user-prompted** (the researcher is asked to approve or deny the operation). Beyond this three-tier resolution, the system also protects its own integrity -- hooks and audit logs are deny-protected so the AI cannot modify its own guardrails or tamper with the audit trail.

---

### Current Realization on Claude Code

#### The Three-Tier Matching Engine (Native Primitive)

Claude Code provides a permission system in `settings.json` with two arrays -- `allow` and `deny` -- under the `permissions` key. Every tool invocation is evaluated against both lists:

1. **If the invocation matches a `deny` pattern** -- hard-blocked. The tool does not execute. Deny always wins over allow.
2. **If the invocation matches an `allow` pattern** -- auto-approved. The tool executes without prompting the user.
3. **If the invocation matches neither** -- the user is prompted. They can approve, deny, or approve for the remainder of the session.

**Pattern syntax:** `ToolName(glob_pattern)` where the glob is matched against the tool's primary argument. For Bash, that is the command string; for Read/Write/Edit, the file path; for Task/Agent, the `subagent_type`. A bare tool name without parentheses (e.g., `Grep`) matches all invocations of that tool. Wildcards `*` and `**` follow standard glob semantics.

#### The Allow List (38 Patterns -- DAAF-Designed Selection)

DAAF's allow list is organized into four functional categories. The selection criteria for each category reflect deliberate design reasoning about what is safe to auto-approve.

**Bash commands (23 patterns):** These cover script execution (`python`, `python3`, `bash`, `marimo run/edit`), read-only inspection (`ls`, `head`, `wc -l`, `file`, `find`, `cd`), non-destructive creation (`mkdir`, `cp`, `chmod +x`), and read-only git operations plus staging (`git status`, `git diff`, `git log`, `git add`, `git --version`). The common thread is that none of these commands destroy data or have irreversible side effects. Script execution commands are further gated by `bash-safety.sh` (globally) and `enforce-file-first.sh` (on coding agents). Critically, `git commit` and `git push` are deliberately excluded -- see Design Choices below.

**Bare tools (6 patterns):**

| Pattern | Rationale |
|---------|-----------|
| `Grep`, `Glob` | Search tools -- pure read operations, no side effects |
| `Edit`, `Write` | File modification tools -- auto-allowed because every invocation targets a specific named file (path visible in tool call), and destructive overwrites are rare in the DAAF workflow which creates new versions rather than modifying existing files |
| `Skill` | Skill loading -- reads skill content into context, no external effects |
| `WebSearch` | Web search -- retrieves public search results only, cannot send data |

**Subagent dispatch (8 patterns):**

| Pattern | Rationale |
|---------|-----------|
| `Task(general-purpose)`, `Agent(general-purpose)` | Built-in generic agent type -- frequently used for ad-hoc tasks |
| `Task(Plan)`, `Agent(Plan)` | Built-in read-only agent type -- cannot modify files |
| `Task(Explore)`, `Agent(Explore)` | In the allow list but immediately blocked by the `enforce-explore-model.sh` hook. This ordering is deliberate: the allow list prevents the permission prompt, and the hook catches the invocation with a structured redirect message. If it were not in the allow list, the user would see a confusing permission prompt for something that will be blocked regardless |
| `Task(search-agent)`, `Agent(search-agent)` | DAAF's replacement for Explore -- read-only, inherits Opus model |

#### The Deny List (35 Patterns -- DAAF-Designed Selection)

DAAF's deny list is organized into six categories, each addressing a distinct threat surface. Deny rules are absolute -- they cannot be overridden by the user during a session.

**1. Destructive filesystem (2 patterns):**

| Pattern | Threat |
|---------|--------|
| `Bash(rm -rf *)` | Recursive forced deletion -- could destroy entire project |
| `Bash(rm -r /*)` | Recursive deletion from root -- catastrophic |

**2. Privilege escalation (4 patterns):**

| Pattern | Threat |
|---------|--------|
| `Bash(sudo *)` | Superuser access -- breaks container isolation model |
| `Bash(su *)` | User switching -- same |
| `Bash(chmod 777 *)` | World-writable permissions -- security hole |
| `Bash(chmod u+s *)` | Setuid bit -- privilege escalation vector |

**3. Container escape (4 patterns):**

| Pattern | Threat |
|---------|--------|
| `Bash(docker run *)` | Nested container -- escape from isolation |
| `Bash(docker exec *)` | Execute in another container -- lateral movement |
| `Bash(mount *)` | Mount filesystems -- access host resources |
| `Bash(chroot *)` | Change root -- sandbox escape |

**4. Destructive git (8 patterns):**

| Pattern | Threat |
|---------|--------|
| `Bash(git push --force *)`, `Bash(git push -f *)` | Force push -- destroys remote history |
| `Bash(git reset --hard *)`, `Bash(git reset --hard)` | Hard reset -- discards all uncommitted work |
| `Bash(git clean -f *)` | Force clean -- removes untracked files permanently |
| `Bash(git checkout .)` | Checkout all -- discards all working tree changes |
| `Bash(git restore .)` | Restore all -- same as checkout |
| `Bash(git branch -D *)` | Force delete branch -- loses branch history |

**5. Credential protection (13 patterns):**

| Pattern | Tool | Threat |
|---------|------|--------|
| `Read(.env)`, `Read(.env.*)` | Read | Expose environment secrets |
| `Read(**/*.pem)`, `Read(**/*.key)` | Read | Expose private keys/certificates |
| `Read(**/credentials*)`, `Read(**/*secret*)` | Read | Expose credential files |
| `Write(.env)`, `Write(.env.*)` | Write | Create/overwrite secret files |
| `Edit(.env)`, `Edit(.env.*)` | Edit | Modify secret files |
| `Read(environment_settings*)`, `Write(environment_settings*)`, `Edit(environment_settings*)` | Read/Write/Edit | DAAF's host-side credential file (Docker Compose injection) |

**6. Infrastructure self-protection (4 patterns):**

| Pattern | Threat |
|---------|--------|
| `Edit(.claude/hooks/*)`, `Write(.claude/hooks/*)` | The AI modifying its own safety hooks -- guardrail collapse |
| `Edit(.claude/logs/*)`, `Write(.claude/logs/*)` | The AI tampering with the audit trail -- evidence destruction |

#### Agent Permission Modes (Native Primitive, DAAF-Configured)

Claude Code supports two permission modes set via the `permissionMode` field in agent frontmatter:

| Mode | Filesystem Effect | DAAF Usage |
|------|-------------------|------------|
| `default` | Full read/write -- agent can create, edit, and delete files | 9 agents: research-executor, code-reviewer, data-planner, debugger, data-ingest, framework-engineer, notebook-assembler, report-writer, research-synthesizer |
| `plan` | Read-only -- agent can read files and run read-only commands but cannot write, edit, or create files | 5 agents: data-verifier, integration-checker, plan-checker, search-agent, source-researcher |

`plan` mode operates at the Claude Code runtime level, making it a harder constraint than the settings.json deny list. Even if a `plan`-mode agent somehow received Write or Edit tools, the runtime would block the operation. This is enforcement by design, not by instruction.

#### .claudeignore (DAAF-Designed, Claude Code Primitive)

The `.claudeignore` file (12 patterns, `.gitignore` syntax) prevents Claude Code from **discovering** credential files during indexing. It is complementary to but independent of the deny list:

- `.claudeignore` prevents **discovery** -- the AI never learns the files exist
- Deny rules prevent **access** -- even if the AI learns a path, it cannot read or write the file

Current patterns: `.env`, `.env.*`, `.env.local`, `.env.production`, `environment_settings.txt`, `environment_settings*.txt`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `**/credentials*`, `**/secrets/`.

#### Pre-commit Hooks (Independent Layer, Standard Tooling)

Seven pre-commit checks from `.pre-commit-config.yaml` serve as a commit-time safety net, catching anything that escapes all runtime layers:

- `check-added-large-files` (500KB max) -- prevents accidental data file commits
- `detect-private-key` -- catches private key material at commit time
- `check-merge-conflict` -- catches unresolved merge markers
- `check-yaml` -- validates YAML syntax (relevant for settings and agent files)
- `end-of-file-fixer`, `trailing-whitespace` -- code hygiene
- `shellcheck` (warning+ severity, bash shell) -- validates hook script quality

These use the standard `pre-commit` framework and are fully independent of Claude Code.

#### Container Isolation (Outermost Layer)

DAAF runs inside a Docker container with `cap_drop: ALL` and a non-root user -- the blast-radius boundary ensuring that even if every software layer fails, the AI cannot access the host filesystem or escalate privileges.

---

### Design Choices and Rationale

This subsection documents the reasoning behind each major permission design choice. An implementer who understands these rationales will make correct security decisions on any platform, even when the specific mechanisms differ.

**Read is NOT auto-allowed.** Despite being a non-destructive operation, `Read` is deliberately excluded from the allow list. Every file read prompts the researcher for confirmation. The reasoning is transparency, not safety: the researcher must be able to see every file the AI accesses. In a research context, knowing what information the AI used to form its analysis is as important as the analysis itself. This is a conscious tradeoff of convenience for auditability.

**WebFetch is NOT auto-allowed, but WebSearch is.** `WebSearch` retrieves public search results -- it sends a query string and receives search listings. It cannot transmit project data. `WebFetch`, by contrast, makes arbitrary HTTP requests to arbitrary URLs with arbitrary payloads. A `curl -d @file` equivalent in the form of WebFetch could exfiltrate local data to a remote server. The asymmetry in the allow list reflects this asymmetry in risk: search is read-only from the network perspective, while fetch is read-write.

**git commit requires user approval.** `git add` is auto-allowed (staging is reversible), but `git commit` is not in the allow list. The researcher controls what enters the permanent record. A commit is an assertion that the staged changes are intentional and correct -- that judgment must remain with the human. Similarly, `git push` is excluded: publishing to a remote repository is an irreversible dissemination act.

**Named DAAF agents are NOT pre-allowed.** The allow list includes four agent types: `general-purpose`, `Plan`, `Explore`, and `search-agent`. All 14 named DAAF agents (research-executor, code-reviewer, data-planner, etc.) are conspicuously absent. This means dispatching any specialist agent prompts the researcher for approval. The rationale is transparency: the researcher should be aware when the orchestrator is delegating to a new specialist, what that specialist will do, and with what context. Generic types are allowed because they are lightweight and frequently used; named agents represent significant autonomous work that merits awareness.

**Hook scripts are deny-protected against modification.** The deny list includes `Edit(.claude/hooks/*)` and `Write(.claude/hooks/*)`. This is the self-protection principle: hooks are the enforcement layer for DAAF's safety model. If the AI could modify `bash-safety.sh`, it could remove the check that blocks `rm -rf`. If it could modify `enforce-file-first.sh`, it could bypass the file-first execution protocol. Deny-protecting hooks ensures that the enforcement layer is tamper-proof -- the AI cannot weaken its own guardrails.

**Audit logs are deny-protected against modification.** The deny list includes `Edit(.claude/logs/*)` and `Write(.claude/logs/*)`. The audit log is an append-only record written by the `audit-log.sh` hook via shell redirection (raw filesystem I/O within the hook process, bypassing Claude Code's permission system). The AI agent cannot write to it via Write or Edit tools, ensuring the audit trail remains tamper-proof.

**Credential files are blocked at THREE independent layers.** Access to `.env`, `*.pem`, `*.key`, `credentials*`, and similar files is prevented by (1) `.claudeignore` preventing discovery, (2) deny rules preventing Read/Write/Edit access, and (3) `output-scanner.sh` detecting leaked credential patterns in tool output. Any single layer suffices in the common case, but defense-in-depth accounts for the uncommon: `.claudeignore` might miss a non-standard filename, a deny pattern might not match a new extension, or a credential might appear in command output rather than from a file read. Three layers cover discovery, access, and output vectors independently.

**plan-mode agents physically cannot write, not just instructed not to.** Five DAAF agents use `permissionMode: plan`. Instructions to "not write" can be ignored; omitting Write/Edit from tool lists can be circumvented via Bash (`echo data > file.txt`). The `plan` mode operates at Claude Code's runtime level, intercepting filesystem operations below the tool layer and blocking writes regardless of how they are attempted. This is the "enforcement over instruction" principle: for security-critical constraints, use the strongest available mechanism.

**Container with cap_drop ALL is the blast-radius boundary.** The Docker container runs with all capabilities dropped and a non-root user. If the AI somehow bypasses every software layer, it is still contained by OS-level isolation: no host filesystem access, no privilege escalation, no network services beyond Docker Compose mappings. The container does not understand DAAF's rules -- it simply prevents entire categories of action at the kernel level, which is why it is the appropriate outermost layer.

**Explore is simultaneously allowed and hook-blocked.** `Explore` appears in the allow list *and* is blocked by `enforce-explore-model.sh`. If Explore were in the deny list, the user would see a confusing "blocked" message for something that is not dangerous, just quality-inappropriate (runs on Haiku). If absent from both lists, the user would be prompted before the hook blocked it anyway. By placing it in the allow list, the permission system auto-approves, and the hook immediately catches and redirects with a structured message explaining why search-agent should be used instead.

**bash-safety.sh provides redundant regex coverage over deny rules.** The deny list uses glob matching; `bash-safety.sh` independently uses regex matching. Glob patterns match the command string as presented, while regex can detect commands within pipelines, subshells, or variable expansions. The hook also covers threats not easily expressed as globs: piped-to-shell patterns (`curl ... | bash`), data exfiltration (`curl -d @file`), and context-dependent destructive patterns.

---

### The 9-Layer Defense-in-Depth Architecture

Each layer operates independently. A failure in any single layer does not compromise the others.

| Layer | Mechanism | What It Covers | Fail Mode |
|-------|-----------|----------------|-----------|
| **1. Container isolation** | Docker with `cap_drop: ALL`, non-root user | OS-level blast radius -- prevents host access, privilege escalation, network escape | N/A (kernel-enforced) |
| **2. File exclusion** | `.claudeignore` (12 patterns) | Discovery prevention -- credential files never appear in the AI's file index | Silent -- files simply invisible |
| **3. Permission deny rules** | `settings.json` deny list (35 patterns) | Access prevention -- hard-blocks Read/Write/Edit of credential files, destructive commands, infrastructure modification | Hard block with error message |
| **4. Permission allow rules** | `settings.json` allow list (38 patterns) | Convenience + transparency calibration -- auto-approves known-safe operations, forces prompts for everything else | Falls through to user prompt |
| **5. Agent permission modes** | Frontmatter `permissionMode: plan` | Filesystem-level read-only for 5 agents | Runtime block on any write attempt |
| **6. PreToolUse hooks** | `bash-safety.sh`, `enforce-file-first.sh`, `enforce-explore-model.sh`, `enforce-foreground-agents.sh`, `deny-claude-code-guide.sh` | Active blocking -- destructive commands, file-first enforcement, model quality, background agent prevention | Fail-closed (exit 2 or JSON deny) |
| **7. PostToolUse hooks** | `audit-log.sh`, `output-scanner.sh` | Audit trail + secret detection -- records every tool use, scans output for leaked credentials | Fail-open (observability, not blocking) |
| **8. Pre-commit hooks** | `.pre-commit-config.yaml` (8 checks) | Commit-time safety net -- catches large files, private keys, merge conflicts before they enter version control | Blocks commit on detection |
| **9. Behavioral guardrails** | CLAUDE.md instruction-following | Stated rules covering scope boundaries, credential handling, destructive command avoidance | Soft -- depends on model compliance |

The layers are ordered from most to least reliable. Container isolation is kernel-enforced; behavioral guardrails depend on probabilistic instruction-following. Critical protections (credential access, destructive commands) are covered by Layers 1-6; Layer 9 handles scope boundaries where enforcement is less critical.

---

### The Credential Management Pattern

Secrets never enter the container filesystem. The pattern:

1. The user places API keys and credentials in `environment_settings.txt` on the **host** machine (in the `daaf-docker/` directory, outside the container).
2. Docker Compose reads this file and injects its contents as environment variables at container startup.
3. Python scripts access keys via `os.environ['KEY_NAME']` as standard practice.
4. Claude cannot see the file -- it is outside the container filesystem, excluded by `.claudeignore`, and deny-protected in settings.json.

This pattern means credentials exist only as in-memory environment variables inside the container. They never touch a file that the AI could read, and they never appear in version control.

---

### Replication Specification

**Required capabilities in the target harness:**

1. **Three-tier tool permission resolution:** The harness must evaluate every tool invocation against an allow list (auto-approve), a deny list (hard-block), and a default action (prompt the user). Deny must always override allow.
2. **Pattern-based matching:** Permissions must match against the tool's arguments (command string, file path, agent type), not just the tool name. Glob or regex syntax at minimum.
3. **Agent-level filesystem enforcement:** The harness must support a read-only mode that prevents file writes at the runtime level, not just by removing write tools. Bash-based file creation must also be blocked.
4. **Pre-execution interception:** The harness must support blocking tool calls before they execute, with the ability to return a descriptive error message to the model.
5. **Post-execution observation:** The harness must support inspecting tool output after execution, at minimum for secret detection.
6. **Self-protection:** The harness must support deny rules that prevent the AI from modifying its own configuration, hooks, and logs.
7. **Container or equivalent isolation:** The runtime must operate within a restricted execution environment that limits filesystem access, network access, and privilege escalation independently of all software layers.

**Behavioral contract:**

- Deny evaluation is checked before allow evaluation. If both match, deny wins.
- A blocked operation returns an error message visible to the model (so it can adjust behavior).
- The allow/deny lists are stored in version-controlled configuration, shared across all users of the project.
- Agent permission modes are declared per agent and enforced at runtime, not configurable by the AI at runtime.

**Acceptance criteria:**

- Feature parity is achieved when: (a) all 35 deny patterns block their target operations, (b) all 38 allow patterns auto-approve their target operations, (c) all unmatched operations prompt the user, (d) `plan`-mode agents cannot create or modify files via any mechanism, (e) hook scripts and audit logs cannot be modified by the AI via any tool, (f) credential files cannot be read by the AI, and (g) a containerized or sandboxed execution environment limits blast radius independently of software protections.

**Degraded-mode options:**

- Without argument-level pattern matching: tool-level allow/deny combined with hook-based argument inspection can approximate the behavior.
- Without agent permission modes: omit write tools from read-only agents AND hook Bash to block file-writing commands. Weaker (pattern-based Bash blocking may miss edge cases) but serviceable.
- Without container isolation: OS-level user permissions (restricted account with limited filesystem access) provide partial coverage.

---

### Harness Landscape

- **Codex (OpenAI):** Sandboxed container with network isolation; `.codexignore` equivalent to `.claudeignore`. Closest parity for container isolation layer.
- **Cursor:** Allow/deny rules and agent modes. No container isolation (runs on user's machine).
- **OpenCode:** Permission configuration and hook-based blocking. Container isolation depends on deployment.
- **Windsurf / Aider:** Limited permission configuration. Significant middleware needed for equivalent deny-list granularity.

---

### Dependencies

| Depends On | Relationship |
|------------|-------------|
| **Instruction Loading (Section 3)** | CLAUDE.md carries the behavioral guardrails (Layer 9) and the credential handling instructions |
| **Agent System (Section 4)** | Agent permission modes (`plan` vs. `default`) are declared in agent frontmatter |
| **Hook System (Section 7)** | Five PreToolUse hooks and two PostToolUse hooks provide Layers 6-7 of defense-in-depth |
| **Logging/Audit (Section 9)** | Audit log and output scanner are protected by deny rules; their integrity depends on the permission system |
| **Tool System (Section 10)** | The one-command-per-Bash-call convention ensures each command is individually evaluated against permissions |

| Depended On By | Relationship |
|----------------|-------------|
| **Agent System (Section 4)** | Tool-access tiers and permission modes are enforced by this system |
| **Hook System (Section 7)** | Hook scripts are protected from modification by deny rules in this system |
| **Logging/Audit (Section 9)** | Audit log integrity depends on deny rules preventing AI modification |
| **Context Management (Section 8)** | Context monitoring hooks operate within the permission framework |
