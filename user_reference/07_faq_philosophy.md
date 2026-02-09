# FAQ: Philosophy & Design Rationale

> **Prerequisite:** [README](../README.md) — specifically the Vision & Purpose and Important Caveats sections.

This document addresses the "why" behind DAAF's design decisions and the broader questions about AI in research. It's where the project's intellectual contribution lives — beyond the technical how-to, these are the ideas and principles that shaped the framework.

---

## DAAF Design Rationale

### Q: Why iterative validation instead of batch execution?

<!-- NEW: Expand from README "Core Philosophy" section and CLAUDE.md "Iteration Protocol" -->

The case for validating every transformation immediately rather than writing a complete pipeline and debugging at the end. Why this is especially critical when AI generates the code.

### Q: Why multi-agent instead of single-agent?

<!-- MIGRATE: README "Architecture Overview" — "Why Multiple Agents?" paragraph -->
<!-- NEW: Expand with deeper reasoning about context degradation and specialization -->

The fundamental problem with single-agent systems (context growth degrades quality) and how decomposing work into focused agents with fresh context addresses it.

### Q: Why human-in-the-loop at every gate?

<!-- NEW: Expand from README "Important Caveats" and "Human Oversight" sections -->

Why the system stops for human review at critical junctures rather than running autonomously, and what the gate structure (G1-G11) accomplishes.

### Q: Why file-first execution instead of interactive notebooks?

<!-- MIGRATE: README "File-First Execution" section (partial) -->
<!-- NEW: Deeper rationale about reproducibility and audit trails -->

Why all code is written to script files before execution, why execution logs are embedded in the scripts, and why the notebook assembles scripts rather than containing new code.

### Q: Why is this a proof-of-concept and not production software?

<!-- MIGRATE: README FAQ "Is this ready for production use?" -->
<!-- NEW: Deeper discussion of what "production" would require -->

The gap between demonstrating AI-assisted research patterns and deploying them at scale. What would need to change — and what might not be solvable yet.

No. This is a proof-of-concept demonstrating AI-assisted research patterns. All outputs require human review. Don't be lazy, don't trust it without verifying. DO NOT give Claude access to any proprietary or private data. If you want to use this for your actual important work, you need to work with your IT to ensure you've got all the necessary agreements and file protections in place before trying to use this system with your data. Do not mess around, do not take risks -- do your homework here.

### Q: Why so many validation layers? Isn't this overkill?

<!-- NEW: Rationale for defense-in-depth validation -->

The case for redundant validation: primary checkpoints (CP1-CP4), secondary QA (QA1-QA4), plan validation, and final verification. Why each layer catches different types of errors.

### Q: Why does the Plan document exist? Can't the AI just start analyzing?

<!-- NEW: Rationale for explicit planning before execution -->

Why separating planning from execution produces better results: methodology review, scope control, and preventing the AI from going down the wrong path with expensive data operations.

---

## AI in Research: Broader Questions

### Q: Can AI meaningfully assist with complex research tasks?

This project explores a critical question: **Can AI meaningfully assist with complex research tasks while maintaining the rigor that social science demands?**

Our answer: Yes, but only with extensive guardrails, modular quality assurance, and human oversight at every critical juncture. DAAF demonstrates what this looks like in practice — multi-agent decomposition, iterative validation, human gates, and full auditability.

<!-- NEW: Expand with nuanced discussion of where AI adds genuine value (data wrangling, documentation, systematic validation) vs. where it still struggles (novel methodology, causal inference, domain expertise) -->

### Q: What does the hallucination problem mean for data analysis specifically?

Large language models can generate plausible-sounding but incorrect outputs. In data analysis specifically, this manifests as:
- Fabricated statistics or counts
- Incorrect methodology application
- Plausible but wrong transformations (e.g., wrong join key, incorrect filter logic)
- Confident-sounding interpretation of patterns that don't exist

This system includes multiple layers of validation specifically to catch such errors, but **no automated system can guarantee correctness**. Human review of all outputs is essential.

<!-- NEW: Expand with data-analysis-specific hallucination risks and how DAAF's validation layers address each one -->

### Q: What's the appropriate level of trust for AI-generated analysis?

<!-- MIGRATE: README "Important Caveats" — risk/mitigation/responsibility table -->
<!-- NEW: Framework for thinking about trust levels -->

A framework for calibrating trust: trust the process (well-validated), verify the outputs (always), question the interpretation (human judgment required). Why "trust but verify" is the right stance.

### Q: How does DAAF's approach relate to reproducibility and open science?

<!-- NEW: Connection to broader reproducibility movement -->

How DAAF's design principles (file-first execution, embedded logs, version control, documented methodology) align with and contribute to reproducibility goals in social science research.

### Q: What does AI assistance replace in a research workflow, and what doesn't it replace?

<!-- NEW: Honest assessment of AI's role -->

What DAAF automates well (data wrangling, systematic validation, documentation generation) vs. what remains fundamentally human (research question formulation, methodological judgment, interpretation, policy implications).

---

## Looking Forward

### Q: Where could this approach go?

<!-- NEW: Future directions for AI-assisted research -->

Potential evolution paths: more data domains, stronger validation, integration with existing research tools, community-contributed skills, and improved AI models reducing hallucination risk.

### Q: What would need to change for production use?

<!-- NEW: Roadmap-level discussion of the gap between PoC and production -->

Security hardening, performance optimization, testing infrastructure, user management, and the fundamental question of whether AI-generated analysis should ever run without human review.

### Q: Why GPL-3.0 for an AI research tool?

We chose GPL-3.0 to ensure that improvements to this proof-of-concept remain open and accessible to the research community. AI-assisted research tools should be transparent and auditable—proprietary forks would undermine this goal.

<!-- NEW: Expand into broader argument about open-source AI research tooling and why transparency is non-negotiable for tools that assist with research -->

### Q: How does DAAF relate to other AI coding tools?

<!-- NEW: Positioning relative to Claude Code, Copilot, Cursor, etc. -->

DAAF is not a general-purpose coding assistant — it's a domain-specific research framework built on top of Claude Code. How it differs from and complements other AI development tools.

---

## Next Steps

- **[README](../README.md)** — The foundation document
- **[Understanding DAAF](02_understanding_daaf.md)** — The conceptual guide to how it all works
- **[Best Practices](03_best_practices.md)** — Practical guidance for using DAAF effectively
