# Part I: Foundation and Orientation

## 1. Introduction and How to Use This Guide

### What DAAF Is

The Data Analyst Augmentation Framework (DAAF) is a research orchestration system that imposes structure, guardrails, and audit trails on AI-assisted data analysis. It coordinates multiple specialized AI agents through a multi-stage pipeline — from data discovery through acquisition, transformation, analysis, and reporting — with the goal of producing scientific work that is transparent, rigorous, reproducible, and responsible. DAAF is not an AI coding agent itself. It is a *framework* that runs on top of one.

### What a Harness Is

Throughout this guide, **harness** refers to the AI coding agent runtime that executes DAAF's instructions. Claude Code is DAAF's current harness. Codex CLI, Cursor, OpenCode, Aider, and Windsurf are alternative harnesses surveyed in the companion landscape analysis. A harness provides the execution environment: the model interface, tool definitions, file access, agent dispatch mechanisms, lifecycle hooks, and permission systems. DAAF provides the *content* that fills those mechanisms — the instructions, the agent protocols, the skill library, the safety rules, and the architectural conventions that make the system suitable for research.

### The Critical Distinction: Framework vs. Harness

Many of DAAF's most important capabilities are **DAAF's own design decisions implemented on top of harness primitives**, not features the harness provides by default. This distinction is essential for anyone porting DAAF, and the guide enforces it rigorously.

Consider file-first execution: every Python operation in DAAF must be written to a script file, executed through a capture wrapper that appends stdout/stderr to the script, and never modified after its output is recorded. Claude Code does not provide this. Claude Code provides Bash execution and file I/O — generic primitives. DAAF *designed* the file-first protocol and *enforces* it through a combination of written instructions (in CLAUDE.md), a blocking hook (enforce-file-first.sh), and a capture wrapper script (run_with_capture.sh). An implementer who looks at file-first execution and thinks "I need to find my harness's equivalent feature" will search in vain. The correct understanding is: "I need to *build* this using whatever primitives my harness offers."

The same applies to context self-monitoring (DAAF's dual-threshold severity system with graduated response protocols), defense-in-depth security (nine coordinated safety layers), immutable script versioning (the _a/_b/_c progression preserving every attempt including failures), and the Inline Audit Trail convention (INTENT/REASONING/ASSUMES comment prefixes). None of these exist in any surveyed harness. They are DAAF inventions.

### Three-Way Feature Classification

Every feature documented in this guide is classified into one of three categories:

- **Native Primitive.** The harness provides this capability directly. DAAF configures or consumes it but did not design it. Example: Claude Code's automatic discovery and injection of CLAUDE.md files into all agent contexts.
- **DAAF-Built.** DAAF designed and implemented this capability entirely. The harness contributes only generic infrastructure (file I/O, shell execution, hook events). Example: the context self-monitoring system with its four severity levels, dual thresholds, and role-specific action protocols.
- **Hybrid.** The harness provides a mechanism; DAAF designs significant layers on top. Example: the permission system — Claude Code provides allow/deny pattern matching, but the specific patterns DAAF chose, the design rationale behind each one, and the coordinating enforcement hooks are all DAAF's architecture.

This classification appears in every feature section so that implementers know whether they are looking for an equivalent harness feature, building a new layer, or doing both.

### How to Read This Guide

Each section is self-contained. An implementer porting a specific subsystem — hooks, agents, permissions — can read only the relevant section without loss of meaning. Cross-references link related sections where features depend on each other.

Part II (Sections 3-10) is the core of the guide: detailed feature specifications organized from most foundational to most peripheral. Part III addresses cross-cutting concerns including the full interdependency map and DAAF's distinctive design contributions. Part IV provides a condensed harness landscape reference. Appendices contain complete inventories and configuration listings.

For a full port, reading sequentially from Section 3 forward is recommended. The dependency layers in Section 11 suggest a porting order.

### Key Terminology

| Term | Definition |
|------|------------|
| **Harness** | The AI coding agent runtime (Claude Code, Codex CLI, Cursor, etc.) that provides execution infrastructure |
| **Framework** | DAAF itself — the instructions, agents, skills, conventions, and enforcement layers that run on top of a harness |
| **Primitive** | A capability the harness provides natively (e.g., hook events, agent dispatch, file I/O) |
| **Layer** | A DAAF-designed capability built on top of harness primitives (e.g., file-first execution, context monitoring) |
| **Feature** | Any capability documented in this guide, whether native primitive, DAAF-built layer, or hybrid |

---

## 2. Migration Complexity Rating System

Every feature in this guide is rated on three axes. These ratings appear in the header of each feature section and are aggregated in the master inventory table (Appendix A).

### Criticality

How essential is this feature to DAAF's operation?

| Rating | Definition | Example |
|--------|------------|---------|
| **CRITICAL** | DAAF cannot function without this feature. Must be fully replicated for the framework to operate at all. | Subagent dispatch (the entire multi-agent orchestration model depends on it); CLAUDE.md injection (universal rules must reach every agent); hook-based safety blocking (the enforcement mechanism for DAAF's safety guarantees) |
| **HIGH** | DAAF degrades significantly without this feature. Partial workarounds may exist but reduce quality, safety, or reproducibility. | Per-agent tool restrictions (without them, read-only agents can write); skill preloading (without it, agents lack domain knowledge at spawn); context utilization monitoring (without it, quality degrades silently at high utilization) |
| **MEDIUM** | Loss reduces quality or convenience, but DAAF can still operate and produce valid research output. | Session archiving (transcripts are valuable but not required for research correctness); output secret scanning (defense-in-depth layer, not sole protection); the terminal status line (operator convenience, not functional requirement) |
| **LOW** | Nice-to-have. Loss is cosmetic, affects only developer experience, or is easily worked around with manual effort. | Output style setting (affects response formatting, not content); thinking summaries display (developer visibility, not agent behavior); first-run onboarding transparency notice (one-time user communication) |

### Portability

How easily does this feature transfer to another harness?

| Rating | Definition |
|--------|------------|
| **NATIVE** | The target harness provides a direct equivalent feature. Configuration may differ but the capability exists. Example: CLAUDE.md auto-loading maps directly to Codex's AGENTS.md auto-loading. |
| **ADAPTABLE** | The target harness has a related feature that can be configured or extended to match DAAF's requirements. The mapping is not one-to-one but the foundation exists. Example: Cursor's `.mdc` rule files can replicate CLAUDE.md's role, but DAAF's single-file hierarchy must be restructured into multiple activation-conditional rule files. |
| **REIMPLEMENTABLE** | No direct equivalent exists, but the harness's extension mechanisms (hooks, plugins, scripts) provide sufficient infrastructure to build the feature from scratch. Example: file-first execution can be built on any harness that supports pre-execution hooks and shell script execution. |
| **ARCHITECTURAL** | The feature requires capabilities the harness does not offer and cannot reasonably approximate. Implementing it would require modifying the harness itself, wrapping it in middleware, or fundamentally rethinking the approach. Example: porting DAAF's multi-agent orchestration to Aider, which has no agent dispatch system. |

### Interdependence

How many other DAAF features depend on this one?

This axis is a simple count of features that require or directly consume this feature's output. It quantifies how foundational a feature is to the overall architecture:

| Count | Interpretation | Example |
|-------|---------------|---------|
| **0** | Isolated. Can be ported (or omitted) independently with no impact on other features. | Output style setting — no other feature reads or depends on it |
| **1-2** | Low coupling. Removing it affects a small, identifiable set of features. | Session archiving — consumed by crash recovery and the log viewer |
| **3-4** | Moderate coupling. Central to a functional cluster but not system-wide. | The skill system — consumed by agent preloading, orchestrator dispatch, progressive disclosure loading |
| **5+** | Foundational. Many features assume this exists. Must be ported early; changes here ripple system-wide. | CLAUDE.md injection (depended on by all 14 agents, the permission system, coding conventions, context management rules, and safety guardrails); the hook system (depended on by safety enforcement, context monitoring, audit logging, skill loading governance, and file-first execution) |

### Using the Ratings Together

The three axes are designed to be read in combination. A feature rated **CRITICAL / ARCHITECTURAL / 5+** (e.g., multi-agent dispatch on a harness without agent support) represents the highest migration difficulty: it is essential, cannot be approximated with existing mechanisms, and many other features depend on it. A feature rated **LOW / NATIVE / 0** (e.g., output style) represents the lowest: it is optional, has a direct equivalent, and nothing else depends on it.

When planning a migration, prioritize by criticality first (CRITICAL features are non-negotiable), then by interdependence (high-interdependence features must be ported before their dependents), and finally by portability (ARCHITECTURAL features require the most design work and should be scoped early).
