---
name: skill-authoring
description: Guide for creating Agent Skills. Covers SKILL.md format, frontmatter requirements, progressive disclosure patterns, decision trees, reference files, and bundled resources. Use when creating a new skill, reviewing skill structure, or debugging skill loading issues.
metadata:
  audience: llm-agents
  domain: meta-skill
---

# Skill Authoring

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
| `frontmatter.md` | YAML spec, validation rules | Writing frontmatter |
| `structure.md` | Body patterns, section templates | Organizing content |
| `progressive-disclosure.md` | Three-level loading, splitting | Managing token budget |
| `references-resources.md` | scripts/, references/, assets/ | Adding bundled resources |
| `gotchas.md` | Anti-patterns, validation errors | Debugging or reviewing |

### Reading Order

1. **Creating a skill?** Start with `quickstart.md` then `frontmatter.md`
2. **Structuring content?** Read `structure.md` then `progressive-disclosure.md`
3. **Adding resources?** See `references-resources.md`
4. **Having issues?** Check `gotchas.md` first

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

### "Something isn't working"

```
Debugging a skill?
├─ Skill not loading → ./references/gotchas.md
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
| `metadata` | No | Key-value pairs (strings) |

### Name Validation Regex

```
^[a-z0-9]+(-[a-z0-9]+)*$
```

### Content Limits

| Component | Limit | Notes |
|-----------|-------|-------|
| Name | 64 chars | Lowercase hyphen-case |
| Description | 1024 chars | Loaded at startup for all skills |
| SKILL.md body | <500 lines | Guideline, not enforced |
| SKILL.md body | <5000 words | Keep concise |
| Metadata per skill | ~100 words | Always in context |

### Core Principles

| Principle | Meaning |
|-----------|---------|
| **Concise is Key** | Context window is shared; justify every token |
| **Progressive Disclosure** | Load only what's needed, when needed |
| **Appropriate Freedom** | Match specificity to task fragility |
| **Examples over Prose** | Show, don't tell |

### Essential Do's

- Include "what it does" AND "when to use it" in description
- Use decision trees for navigation
- Keep SKILL.md under 500 lines
- Split large content into `references/` files
- Use tables for quick lookup
- Test scripts before including

### Essential Don'ts

- Don't include README.md, CHANGELOG.md, or auxiliary docs
- Don't put "When to Use" sections in body (loaded too late)
- Don't duplicate content between SKILL.md and references
- Don't nest references more than one level deep
- Don't use angle brackets in description
- Don't start/end name with hyphens

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Directory location | `./references/quickstart.md` |
| Minimal example | `./references/quickstart.md` |
| First skill walkthrough | `./references/quickstart.md` |
| Name field spec | `./references/frontmatter.md` |
| Description field spec | `./references/frontmatter.md` |
| Optional fields | `./references/frontmatter.md` |
| Validation rules | `./references/frontmatter.md` |
| Body patterns | `./references/structure.md` |
| Decision tree format | `./references/structure.md` |
| Table conventions | `./references/structure.md` |
| Section templates | `./references/structure.md` |
| Three-level loading | `./references/progressive-disclosure.md` |
| Content splitting | `./references/progressive-disclosure.md` |
| Token budget | `./references/progressive-disclosure.md` |
| scripts/ directory | `./references/references-resources.md` |
| references/ directory | `./references/references-resources.md` |
| assets/ directory | `./references/references-resources.md` |
| Validation errors | `./references/gotchas.md` |
| Anti-patterns | `./references/gotchas.md` |
| Pre-submission checklist | `./references/gotchas.md` |
