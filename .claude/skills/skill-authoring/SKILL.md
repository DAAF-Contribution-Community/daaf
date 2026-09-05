---
name: skill-authoring
description: >-
  Guide for creating and auditing DAAF skills (SKILL.md). Covers frontmatter, metadata vocabulary, progressive disclosure, decision trees, reference files. Use when creating, reviewing, or debugging skill loading. For agent files, use agent-authoring.
metadata:
  audience: any-agent
  domain: skill-development
---

# Skill Authoring

Guide for creating and auditing DAAF agent skills. Covers SKILL.md format, frontmatter requirements and validation rules, controlled vocabulary for metadata, progressive disclosure patterns, decision trees, reference files, and bundled resource organization. Use when creating a new skill, reviewing or auditing skill structure and frontmatter, or debugging skill loading and triggering issues. For creating agent definition files (.claude/agents/*.md), use agent-authoring instead.

Quick reference for creating well-structured Skills. Use decision trees below to find guidance, then load detailed references as needed.

## What is a Skill?

A Skill is a reusable instruction set that extends agent capabilities:

- **SKILL.md file**: Required entry point with YAML frontmatter + Markdown body
- **Progressive disclosure**: Metadata loaded at startup, body on trigger, resources on-demand
- **Bundled resources**: Optional `scripts/`, `references/`, `assets/` directories
- **On-demand loading**: Agent calls `skill({ name: "skill-name" })` to load

## How to Use This Skill

### Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `quickstart.md` | Minimal skill, directory setup | Creating first skill |
| `frontmatter.md` | YAML spec, validation rules, description writing | Writing frontmatter |
| `structure.md` | Body patterns, section templates, content patterns | Organizing content |
| `progressive-disclosure.md` | Three-level loading, splitting | Managing token budget |
| `references-resources.md` | scripts/, references/, assets/ | Adding bundled resources |
| `testing-iteration.md` | Test prompts, iteration workflow, multi-model testing | Validating and improving skills |
| `gotchas.md` | Anti-patterns, validation errors, diagnostics | Debugging or reviewing |

### Reading Order

1. **Creating a skill?** Start with `quickstart.md` then `frontmatter.md`
2. **Structuring content?** Read `structure.md` then `progressive-disclosure.md`
3. **Adding resources?** See `references-resources.md`
4. **Testing and improving?** See `testing-iteration.md`
5. **Having issues?** Check `gotchas.md` first

## Quick Decision Trees

### "I need to create a skill"

```
Creating a new skill?
├─ Where to put it → ./references/quickstart.md
├─ Minimal example → ./references/quickstart.md
├─ Write frontmatter → ./references/frontmatter.md
├─ Name validation → ./references/frontmatter.md
└─ Description best practices → ./references/frontmatter.md
```

### "I need to structure the body"

```
Structuring SKILL.md body?
├─ Workflow-based (sequential steps) → ./references/structure.md
├─ Task-based (tool collection) → ./references/structure.md
├─ Reference-based (standards/specs) → ./references/structure.md
├─ Capabilities-based (features) → ./references/structure.md
├─ Decision tree format → ./references/structure.md
└─ Table conventions → ./references/structure.md
```

### "I need to manage content size"

```
Content too large?
├─ Understand three-level loading → ./references/progressive-disclosure.md
├─ When to split into references → ./references/progressive-disclosure.md
├─ Domain-specific organization → ./references/progressive-disclosure.md
├─ Framework/variant splitting → ./references/progressive-disclosure.md
└─ Token budget guidelines → ./references/progressive-disclosure.md
```

### "I need to add resources"

```
Adding bundled resources?
├─ Executable scripts → ./references/references-resources.md
├─ Documentation files → ./references/references-resources.md
├─ Template assets → ./references/references-resources.md
├─ When to use each type → ./references/references-resources.md
└─ Directory structure → ./references/references-resources.md
```

### "I need to test or improve a skill"

```
Testing or iterating?
├─ Create test prompts → ./references/testing-iteration.md
├─ Test triggering accuracy → ./references/testing-iteration.md
├─ Iterate based on feedback → ./references/testing-iteration.md
├─ Test across models → ./references/testing-iteration.md
└─ Observe navigation patterns → ./references/testing-iteration.md
```

### "Something isn't working"

```
Debugging a skill?
├─ Skill not loading → ./references/gotchas.md
├─ Skill undertriggering → ./references/gotchas.md
├─ Skill overtriggering → ./references/gotchas.md
├─ Validation errors → ./references/gotchas.md
├─ Name format issues → ./references/frontmatter.md
├─ Description too long → ./references/frontmatter.md
└─ Common anti-patterns → ./references/gotchas.md
```

## Quick Reference

### Minimal SKILL.md Template

```yaml
---
name: my-skill-name
description: What this skill does. When to use it (specific triggers).
metadata:
  audience: target-users
  domain: skill-domain
---

# My Skill Name

Brief intro sentence.

## Section 1

Content here.
```

### Directory Structure

```
.claude/skills/<name>/
├── SKILL.md              # Required
├── scripts/              # Optional: executable code
├── references/           # Optional: documentation
└── assets/               # Optional: templates, images
```

### Frontmatter Validation Rules

| Field | Required | Constraints |
|-------|----------|-------------|
| `name` | Yes | Lowercase alphanumeric + hyphens, 1-64 chars, no leading/trailing/consecutive hyphens |
| `description` | Yes | 1-1024 chars, no angle brackets (`<` `>`), include what + when |
| `when_to_use` | No | Optional; appended to `description` in the skill listing and counts toward the 1,536-char combined display cap. Not a DAAF default — see `./references/frontmatter.md` |
| `metadata` | No | Key-value pairs (strings) |

### Name Validation Regex

```
^[a-z0-9]+(-[a-z0-9]+)*$
```

### Content Limits

| Component | Limit | Notes |
|-----------|-------|-------|
| Name | 64 chars | Lowercase hyphen-case |
| Description (frontmatter) | 1,024 chars | Validation limit (Agent Skills spec). Display: combined `description` + `when_to_use` is truncated at 1,536 chars per skill in the skill listing (the `skillListingMaxDescChars` default); the truncation breakdown is reported by `/doctor`, not a startup notification |
| Description (body) | 2-5 sentences (~400-1,000 chars) | Expanded description as plain paragraph after `# Title`; at least as informative as the frontmatter description, adding detail omitted from the listing for budget economy |
| SKILL.md body | <500 lines | Guideline, not enforced |
| SKILL.md body | <5000 words | Keep concise |
| Metadata per skill | ~100 words | Always in context |

> **Version note:** Display caps verified against the Claude Code settings reference on 2026-09-05 (CC 2.1.261). The per-skill listing cap is 1,536 chars (the `skillListingMaxDescChars` default; positive integer). The listing as a whole is bounded by `skillListingBudgetFraction` (a fraction >0 and ≤1, default 0.01 = 1% of the context window; DAAF sets 0.1 as a guardrail — well above any listing size DAAF ships, so truncation only fires if the listing ever grows past 10% of the window); when the listing exceeds that budget, the least-used skills' descriptions are dropped first (names kept). The truncation breakdown is inspectable via `/doctor` (since 2.1.144), not a startup notification. If observed behavior differs, verify against current Claude Code docs rather than assuming this table is correct. See `./references/frontmatter.md` for the full length model, including the aggregate listing budget shared across all skills.

### Core Principles

| Principle | Meaning |
|-----------|---------|
| **Concise is Key (SKILL.md)** | The SKILL.md body shares context with conversation history; justify every token there. Claude is already smart — only add context it doesn't already have |
| **Thorough is Key (references)** | Reference files are loaded on-demand at Level 3. Their token cost is incurred only when needed, so they should be comprehensive — encode all discovered knowledge rather than summarizing. Err on the side of more detail in reference files |
| **Progressive Disclosure** | Load only what's needed, when needed |
| **Appropriate Freedom** | Match specificity to task fragility (high freedom for flexible tasks, low freedom for fragile/critical operations) |
| **Explain the Why** | Use reasoning over rigid directives. If you find yourself writing ALWAYS/NEVER in all caps, reframe and explain the reasoning instead — it's more effective |
| **Examples over Prose** | Show input/output pairs rather than describing behavior in paragraphs |
| **Test and Iterate** | Create test prompts, observe behavior, refine. See `./references/testing-iteration.md` |

### Essential Do's

- Before creating a new skill, read 1-2 existing skills of the same type as structural exemplars (e.g., for data source skills, read an existing data source SKILL.md; for tool skills, read `polars` or `plotnine`)
- Before authoring, consider a scoped online survey of the skill's domain (best practices, alternative implementations, practitioner guides) — external grounding beats ungrounded inference. When working with a user, offer this rather than silently skipping it (formalized in Framework Development mode as the Pre-Authoring Research Offer: `.claude/skills/daaf-orchestrator/references/framework-development-mode.md` § Pre-Authoring Research Offer)
- Include "what it does" AND "when to use it" in description
- Write a complete, information-rich frontmatter description (up to the 1,024-char validation limit) — this is the ONLY text agents see when deciding whether to load a skill, so it should carry the full triggering context, not a compressed teaser
- Practice budget-aware economy: 40+ DAAF skills share an aggregate skill-listing budget (~1% of the context window). When the listing overflows, descriptions for the least-invoked skills are dropped first — so spend characters where they earn triggering accuracy, not on exhaustive feature lists
- Write an expanded body description as a plain paragraph immediately after the `# Title` heading — it should elaborate beyond the frontmatter (detailed scope, additional triggers, fine-grained disambiguation), guaranteeing complete context once the skill is loaded
- Prioritize in the description, in order: (1) what it is, (2) key triggers/use cases, (3) disambiguation from similar skills (e.g., "For FE use pyfixest; for GLM use statsmodels")
- Write descriptions in third person ("Processes files" not "I help you process files")
- Make descriptions slightly "pushy" to combat undertriggering
- Front-load identity and triggers in the description — the skill listing caps the combined description + when_to_use text at 1,536 chars, and readers (agent and human alike) weight the opening words most heavily
- Explain *why* behind instructions, not just *what*
- Use decision trees for navigation
- Keep SKILL.md under 500 lines
- Split large content into `references/` files
- Use tables for quick lookup
- Use consistent terminology throughout (pick one term, stick with it)
- Test skills with realistic prompts before finalizing
- Test scripts before including
- Include metadata references (codebook URLs) for data source skills — see `datasets-reference.md` codebook column

### Essential Don'ts

- Don't include README.md, CHANGELOG.md, or auxiliary docs
- Don't put "When to Use" sections in body (loaded too late)
- Don't duplicate content between SKILL.md and references
- Don't nest references more than one level deep
- Don't use angle brackets in description
- Don't start/end name with hyphens
- Don't use heavy-handed ALWAYS/NEVER/MUST in all caps — explain reasoning instead
- Don't offer too many options — provide a default with an escape hatch
- Don't include time-sensitive information (use "Old patterns" `<details>` sections if needed)
- Don't use Windows-style backslash paths (always forward slashes)

### Skill Registration

Skills are automatically discovered via their YAML frontmatter — the orchestrator sees all skills listed in the system message at conversation start. No manual registration is needed for triggering. Once the skill's `SKILL.md` is placed in `.claude/skills/{skill-name}/`, it becomes available immediately.

**Framework integration beyond discovery:** If the skill should be preloaded by specific agents (via `skills:` frontmatter), referenced in pipeline stage mappings, or wired into workflow documentation, additional registration is required. See `agent_reference/FRAMEWORK_INTEGRATION_CHECKLIST.md` § 1 (items S8-S10) for the complete list of conditional integration points.

## Data Source Skills: Metadata References

When authoring a data source skill, include a codebook reference section if codebooks exist for the source. Follow the existing pattern (modeled after PSEO):

```markdown
### [Source] Codebooks

| Dataset | Codebook Path |
|---------|---------------|
| ... | `path/to/codebook_name` |

> Codebooks are `.xls` files on both mirrors. See `datasets-reference.md` for full catalog
> and `fetch-patterns.md` for `get_codebook_url()`. For human reference — not parsed programmatically.
```

The codebook path comes from the `codebook` column in `datasets-reference.md`. Metadata files are for human reference only — they are not parsed programmatically by the pipeline.

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Directory location | `./references/quickstart.md` |
| Minimal example | `./references/quickstart.md` |
| First skill walkthrough | `./references/quickstart.md` |
| Name field spec | `./references/frontmatter.md` |
| Description field spec | `./references/frontmatter.md` |
| Description writing tips | `./references/frontmatter.md` |
| Optional fields | `./references/frontmatter.md` |
| Validation rules | `./references/frontmatter.md` |
| Body patterns | `./references/structure.md` |
| Decision tree format | `./references/structure.md` |
| Table conventions | `./references/structure.md` |
| Section templates | `./references/structure.md` |
| Content patterns (checklists, feedback loops) | `./references/structure.md` |
| Three-level loading | `./references/progressive-disclosure.md` |
| Content splitting | `./references/progressive-disclosure.md` |
| Token budget | `./references/progressive-disclosure.md` |
| scripts/ directory | `./references/references-resources.md` |
| Script error handling | `./references/references-resources.md` |
| references/ directory | `./references/references-resources.md` |
| assets/ directory | `./references/references-resources.md` |
| Test prompts | `./references/testing-iteration.md` |
| Triggering tests | `./references/testing-iteration.md` |
| Multi-model testing | `./references/testing-iteration.md` |
| Iteration workflow | `./references/testing-iteration.md` |
| Observing skill behavior | `./references/testing-iteration.md` |
| Validation errors | `./references/gotchas.md` |
| Anti-patterns | `./references/gotchas.md` |
| Undertriggering / overtriggering | `./references/gotchas.md` |
| Library/tool skill version verification | `./references/gotchas.md` |
| Pre-submission checklist | `./references/gotchas.md` |
