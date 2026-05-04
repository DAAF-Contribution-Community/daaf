# DAAF Migration Guide — Section Index

> **Status:** Draft complete (2026-05-01)
> **Total sections:** 14 + appendices (planned)
> **Workspace:** `/daaf/research/2026-05-01_FrameworkDev_MigrationGuide/`

This index routes to all sections of the DAAF Feature Parity Specification — a comprehensive guide for porting DAAF to any AI coding harness.

---

## How to Read This Guide

Each section is **self-contained** — read only what you need. Sections are ordered by dependency (foundational first), so sequential reading works for full ports.

Every feature section follows the same template: Design Intent → What It Does → Current Realization on Claude Code → Design Choices and Rationale → Replication Specification → Harness Landscape → Dependencies.

Features are classified as **Native Primitive** (harness provides it), **DAAF-Built** (DAAF invented it on top of harness primitives), or **Hybrid** (harness provides mechanism, DAAF designs significant layers on top).

---

## Plan and Research

| Document | Path | Description |
|----------|------|-------------|
| Migration Guide Plan | `MIGRATION_GUIDE_PLAN.md` | Section-by-section blueprint with writing strategy |
| Research Findings (9 files) | `findings/` | 288KB of detailed research across all dimensions |

---

## Part I: Foundation and Orientation

| Section | File | Words | Description |
|---------|------|-------|-------------|
| 1. Introduction | `sections/part1_foundation.md` | ~600 | What DAAF is, harness vs framework distinction, feature classification system |
| 2. Rating System | `sections/part1_foundation.md` | ~550 | Criticality / Portability / Interdependence axes |

---

## Part II: Feature Specifications (Core)

| Section | File | Classification | Criticality | Words |
|---------|------|---------------|-------------|-------|
| 3. Instruction Loading | `sections/sec03_instruction_loading.md` | Hybrid | CRITICAL | ~2,800 |
| 4. Agent System | `sections/sec04_agent_system.md` | Hybrid | CRITICAL | ~4,620 |
| 5. Permissions & Security | `sections/sec05_permissions.md` | Hybrid | HIGH | ~3,550 |
| 6. Skill System | `sections/sec06_skills.md` | Hybrid | HIGH | ~3,700 |
| 7. Hook System | `sections/sec07_hooks.md` | Hybrid | CRITICAL | ~5,470 |
| 8. Context Management | `sections/sec08_context.md` | DAAF-Built | HIGH | ~4,950 |
| 9. Logging & Audit Trail | `sections/sec09_logging.md` | DAAF-Built | HIGH | ~3,526 |
| 10. Tool System | `sections/sec10_tools.md` | Hybrid | HIGH | ~2,589 |

---

## Part III: Cross-Cutting Concerns

| Section | File | Words | Description |
|---------|------|-------|-------------|
| 11. Interdependency Map | `sections/part3_cross_cutting.md` | ~1,045 | 8-layer dependency diagram, porting order, feature clusters |
| 12. Distinctive Contributions | `sections/part3_cross_cutting.md` | ~1,932 | 6 features unique to DAAF with no harness equivalent |
| 13. Converged Standards | `sections/part3_cross_cutting.md` | ~1,057 | 5 cross-harness standards that ease migration |

---

## Part IV: Harness Landscape Reference

| Section | File | Words | Description |
|---------|------|-------|-------------|
| 14. Comparison Matrix | `sections/part4_harness_landscape.md` | ~1,800 | 5 harnesses rated against DAAF features |

---

## Part V: Appendices (Planned)

Appendices can be generated from the research findings files. They are not yet written as separate documents but the source material is complete.

| Appendix | Source | Content |
|----------|--------|---------|
| A. Feature Inventory | All findings | Master table of every feature with ratings |
| B. Agent Inventory | `findings/02_agent_system.md` | 14 agents with all frontmatter fields |
| C. Skill Inventory | `findings/03_skill_system.md` | 36 skills with metadata |
| D. Hook Registration Map | `findings/01_hooks_system.md` | Complete registration table |
| E. Permission Patterns | `findings/04_settings_permissions.md` | 38 allow + 35 deny patterns |
| F. settings.json Structure | `findings/04_settings_permissions.md` | Full annotated configuration |
| G. Glossary | All findings | DAAF and Claude Code terminology |

---

## Summary Statistics

- **Total written:** ~39,473 words across 12 files
- **Research base:** ~288KB across 9 findings files
- **Features documented:** 8 core features + 6 distinctive contributions + 5 converged standards
- **Harnesses surveyed:** 5 (Codex CLI, Cursor, OpenCode, Aider, Windsurf)
