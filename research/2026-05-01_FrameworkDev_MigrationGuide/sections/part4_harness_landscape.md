# Part IV: Harness Landscape Reference

## 14. Harness Comparison Matrix

This section is an awareness resource, not a migration plan. It consolidates the feature survey from Finding 09 into a compact reference that answers one question: for each critical DAAF capability, which alternative harnesses have native equivalents, which offer partial coverage, and which have nothing?

The value of this reference is twofold. First, it helps a prospective implementer quickly assess how much custom work a given target harness would require. Second, it highlights where DAAF's architecture has become portable through industry convergence versus where DAAF remains architecturally unique.

All assessments are based on official documentation and developer community resources surveyed in April-May 2026. Harness capabilities evolve; these snapshots will require periodic re-validation.

### Readiness Tiers

The five surveyed harnesses fall into three tiers based on how many of DAAF's critical capabilities have direct or near-direct equivalents. Tier assignment reflects feature *coverage*, not quality -- a Tier 3 harness may be excellent at what it does; it simply does not do enough of what DAAF requires.

**Tier 1 -- Closest Feature Parity**

> **Codex CLI** (OpenAI). Most DAAF features have direct equivalents. AGENTS.md provides hierarchical project instructions with directory-proximity precedence. The SKILL.md open standard is natively supported with a formalized 2% context budget cap and auto-wiring of MCP dependencies declared in skills. The hook system exposes five event types (matching Claude Code's count) with concurrent hook execution and enterprise-managed hooks via `requirements.toml`. Custom named agents with per-agent model override, subagent spawning with configurable `max_depth`, and built-in pause/resume for long-running goals are all present. The primary gaps are: per-command deny patterns (Codex uses profile-based permission modes rather than DAAF's granular allow/deny pattern lists), file-first execution (would require a custom hook implementation), and model lock-in to the GPT-5 family only.

> **Cursor** (AI IDE). The strongest subagent system among all surveyed harnesses: async subagents (parent continues while children work), recursive spawning, and up to eight parallel agents. Hooks include a `subagentStart` event for intercepting subagent creation and a `failClosed` option for security-critical enforcement -- both features absent from Claude Code. The `.cursor/rules/` system offers more granular activation modes than CLAUDE.md (always-on, mentionable, Cascade-requested, glob-attached). SKILL.md is natively supported with a skills marketplace for discovery. The primary gaps are: IDE-first architecture (no pure CLI mode for headless container operation, which is a fundamental mismatch for DAAF's Docker model), context monitoring that does not trigger until 95% capacity (far too late for DAAF's quality-first approach), and no per-command deny patterns.

**Tier 2 -- Partial Coverage**

> **OpenCode** (open-source CLI). The defining advantage is model diversity: 75+ LLM providers including OpenAI, Anthropic, Google, AWS Bedrock, and local models via Ollama, with per-agent model selection and mid-session switching. The agent system supports primary agents, subagents, and custom agent definitions with event-driven peer-to-peer coordination. A plugin architecture (JS/TS plugins in `.opencode/plugins/`) provides extensibility for hooks, tools, and rules. Being open source (Go, MIT-licensed) allows modification of the harness itself. The primary gaps are: no native skill/knowledge system (DAAF's 36 skills would need plugin-based reimplementation), a simpler permission model without per-command deny patterns, immature logging infrastructure without structured audit trails, and no equivalent of DAAF's context utilization monitoring with severity thresholds.

**Tier 3 -- Significant Gaps**

> **Windsurf** (AI IDE, Cognition/Codeium). A capable single-agent tool with unique strengths: "Flow awareness" tracks user actions, edits, and clipboard to infer intent; the "Memories" feature provides genuine cross-session persistent learning; the proprietary SWE-1.5 model is reported at 13x the speed of Sonnet 4.5; and JSONL transcripts with full conversation context serve enterprise audit/compliance needs. However, Cascade is a single persistent agent -- there is no multi-agent orchestration, no named agent definitions, and no parallel dispatch. The hook system is limited to three event types focused on compliance logging rather than tool-call interception. No skill system, no per-command permissions (enterprise tier only), and no CLI/container operation mode. Additionally, platform ownership changes (Codeium acquired by Cognition in late 2025) introduce stability considerations.

> **Aider** (open-source CLI). An excellent pair programming tool with the broadest model support (100+ providers via LiteLLM), a philosophically aligned git-first workflow (every AI edit becomes an atomic commit), and a clever Architect/Editor dual-model mode that separates reasoning from code formatting. The tree-sitter-based repo map provides intelligent context without loading full files. However, Aider fundamentally lacks the infrastructure DAAF requires: no agent/subagent system, no hook/event system, no permission system, no skill/knowledge system, no MCP support, and no context monitoring. It could serve as a component within a larger orchestration system but cannot replace Claude Code as DAAF's harness without building an entire framework layer on top of it.

### Cross-Harness Comparison Matrix

The matrix below evaluates each harness against DAAF's critical feature areas using four ratings:

- **Native** -- The harness provides this capability as a built-in feature with minimal configuration required.
- **Partial** -- The harness provides a related capability that covers some but not all of the feature's requirements.
- **Plugin** -- No built-in support, but the harness's extension mechanism (hooks, plugins, marketplace) could be used to build it.
- **None** -- No built-in support and no practical extension mechanism for this capability.

| DAAF Feature | Codex CLI | Cursor | OpenCode | Windsurf | Aider |
|---|---|---|---|---|---|
| **Custom instructions** (CLAUDE.md equivalent) | Native | Native | Native | Native | Partial |
| **Named agent definitions** | Native | Native | Native | None | None |
| **Subagent dispatch + isolation** | Native | Native | Native | None | None |
| **Hooks / lifecycle events** | Native | Native | Plugin | Partial | None |
| **Permission allow/deny** | Partial | Partial | Partial | Partial | None |
| **Skill / knowledge system** | Native | Native | None | None | None |
| **Context monitoring** | Partial | Partial | Partial | None | None |
| **Session persistence** | Native | Native | Native | Partial | Partial |
| **Model selection per agent** | Partial | Native | Native | Native | Native |
| **Audit logging** | Partial | Partial | Partial | Partial | Partial |
| **CLI / container compatibility** | Native | Partial | Native | None | Native |

**Reading the matrix.** A column of "Native" does not mean migration is trivial -- it means the target harness has the *primitive* on which DAAF's design can be built. DAAF's specific configurations, conventions, and inter-feature coordination must still be ported. A "Partial" on permissions, for example, means the harness has a permission concept but lacks DAAF's granular per-command deny patterns. A "Plugin" means the capability can be constructed but does not exist out of the box.

**Notable patterns across the matrix:**

*Instructions and skills have converged.* Custom instruction files and the SKILL.md standard are the most portable DAAF capabilities. Codex and Cursor support both natively; the content transfers with zero or minimal structural changes.

*Multi-agent orchestration is the primary divider between tiers.* The Tier 1/Tier 2 harnesses all support named agents with subagent dispatch and context isolation. The Tier 3 harnesses do not. Since DAAF's entire architecture -- from skill loading to context management to safety enforcement -- depends on multi-agent orchestration, this single capability is the strongest predictor of migration feasibility.

*Permission granularity is universally weaker.* No surveyed harness matches DAAF's per-command allow/deny pattern lists (38 allow patterns, 35 deny patterns across 6 categories). Codex uses profile-based modes (Auto/Read-only/Full Access); Cursor uses tool-name-based rules; OpenCode has per-action-type configuration. All are coarser than DAAF's approach. An implementer porting DAAF's defense-in-depth security architecture would need to compensate for this gap through hooks.

*Context monitoring is universally shallower.* Every harness has some form of context management (compaction, token limits, context budgets), but none implements DAAF's dual-threshold severity system with graduated response protocols. Codex's skill budget (2% cap) is the most sophisticated alternative -- it manages a specific category of context consumption -- but does not extend to overall utilization monitoring with role-specific escalation actions. This remains a custom-build requirement on any target.

*Model diversity and model lock-in are inversely correlated with orchestration maturity.* Aider (100+ providers) and OpenCode (75+ providers) offer the broadest model choice but have weaker orchestration. Codex has the strongest orchestration parity with DAAF but is locked to OpenAI models. Only Cursor combines multi-model support with strong orchestration.

### Features Without Equivalents Anywhere

Six DAAF capabilities have no direct equivalent in any surveyed harness and would require custom implementation regardless of target:

1. **Context utilization severity thresholds** -- NOMINAL/ELEVATED/HIGH/CRITICAL with dual triggers (percentage OR absolute token count, whichever fires first) and role-specific graduated response protocols. Other harnesses compact; DAAF *monitors, adapts, and gracefully degrades*.

2. **File-first execution with `run_with_capture.sh`** -- The mandatory write-execute-capture pattern where stdout/stderr are appended to the script file as an immutable execution record. Git commits approximate a code trail but do not capture execution output inline with source.

3. **Inline Audit Trail (IAT)** -- The INTENT/REASONING/ASSUMES commenting convention that makes every analytical decision in AI-generated code explicitly auditable. This is a documentation convention, not a harness feature, but DAAF enforces it through instructions and agent protocols.

4. **Immutable script versioning** -- Failed scripts retain their execution logs as sealed artifacts; fixes go to `_a.py`, `_b.py` suffixes. All versions are preserved for traceability. No harness provides or enforces this pattern.

5. **Defense-in-depth with nine coordinated layers** -- Container isolation, `.claudeignore`, deny rules, allow rules, agent permission modes, PreToolUse blocking hooks, PostToolUse advisory hooks, behavioral guardrails, and pre-commit hooks. Other harnesses have subsets (Codex and Cursor reach four layers), but none coordinate the full stack with the infrastructure self-protection principle (the AI cannot modify its own guardrails).

6. **Subagent early-return protocol** -- A structured format for subagents to return partial but well-documented results when context pressure forces early termination, enabling the orchestrator to seamlessly continue the work. Other harnesses isolate subagent context but define no protocol for what happens when that context runs low.

These six features represent DAAF's core architectural distinctiveness. They are what makes DAAF a *research integrity framework* rather than a generic AI coding workflow. Any migration that omits them produces a system that can generate code but cannot guarantee the transparency, reproducibility, and auditability that DAAF exists to provide.

### The Convergence Trajectory

DAAF's architecture is becoming more portable over time, not less. The SKILL.md format originated with Claude Code and is now an open standard (`agentskills.io`) adopted by Codex and Cursor. The AGENTS.md / custom instructions pattern is a de facto convention across all harnesses. MCP is supported by five of six surveyed harnesses. Hook systems with blocking semantics exist in four of five. Subagent context isolation is standard in Codex, OpenCode, and Cursor.

The practical implication: the *mechanisms* for building a DAAF-equivalent system are increasingly available across harnesses. The *design decisions* -- what to enforce, why, and how the pieces coordinate -- remain DAAF's distinctive contribution. This migration guide documents those decisions precisely so that an implementer on any harness can make equivalent choices rather than cargo-culting configurations whose rationale has been lost.
