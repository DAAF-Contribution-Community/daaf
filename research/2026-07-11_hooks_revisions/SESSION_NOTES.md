# Session Notes: Framework Development — Safety Hook Hardening (starter-kit handoff)

**Started:** 2026-07-11
**Workspace:** /daaf/research/2026-07-11_hooks_revisions
**Work Type:** Multi-Component (modify bash-safety.sh + settings.json, new test battery, doc updates)

## Accomplishments

- Phase 1 scoping complete: 3 parallel read-only explorations (hook state, settings.json surface, workspace/testing/docs)
- All handoff memo claims verified against ground truth (see Key Decisions / Findings)

## Key Findings (Phase 1)

- **Backslash-continuation bug CONFIRMED** (probe-verified): current `NORM_CMD=$(echo "$CMD" | tr -s '[:space:]' ' ')` at bash-safety.sh:53 leaves stray `\` tokens. Impact is on sections 1–5 (verb/whitespace-adjacency regexes); the /tmp section (§6) was probe-tested and is NOT defeated (`\` not in its excluded char class). Proposed fix (`sed 's/\\$//'` before `tr`) probe-verified correct — sed strips trailing `\` per-line. Note: `enforce-single-command.sh` already collapses continuations (line 110); bash-safety does not.
- **Memo section numbering off by one:** live hook has sections 1–6 (§6 = /tmp provenance, lines 132–264). New sections should be §7 (tampering) and §8 (packages), appended after §6.
- **settings.json claims all CONFIRMED:** `Bash(cp *)` and `Bash(python *)` in allow list; Edit/Write denies on hooks/logs bind only those tools; no pip/uv/conda denies anywhere; `benchmarks/harness/hooks/block-git-writes.sh` registered as PreToolUse Bash hook (file exists); `Write/Edit(//tmp/**)` denies present; `ENABLE_PROMPT_CACHING_1H=1`. No settings.local.json.
- **NEW GAP beyond memo:** `.claude/settings.json` itself has zero write protection of any kind (probe: grep for settings.json in deny list → empty). Shell `cp/tee/sed -i` could overwrite it and deregister every hook. Root-of-trust hole.
- **`git update-index --chmod=+x`** currently prompts (not allowed, not denied) — memo's command-position anchoring correctly avoids breaking it.
- **Workspace contents:** starter-kit `bash-safety.sh` (290 lines; §6 tampering, §7 packages, §8 /tmp — different ordering than live), `test-safety-hooks.sh` (86 cases; 66 portable, 20 gws-specific), starter-kit `settings.json` (240 lines, has the 8 pip/uv deny rules). `gws-safety.sh` NOT included (not needed — DAAF has no gws CLI).
- **Existing precedent:** `scripts/test_enforce_single_command.sh` (669 lines, same run_case harness); TmpProvenance session (2026-07-06) used staged-draft → battery → human-deploy workflow.
- **Conventions:** shebang must be `#!/usr/bin/env bash` (handoff uses `#!/bin/bash`); live SCRATCH_HINT wording is more precise than handoff's — retain live §6 as-is.

## Key Decisions

- **CONFIRMED (Checkpoint 1, 2026-07-11):** Modify the LIVE hook (append §7 tampering + §8 packages + NORM_CMD backslash fix) rather than adopt handoff file wholesale — preserves live /tmp section wording and numbering.
- **CONFIRMED:** Extend tampering guard beyond memo to include `.claude/settings*.json` (root-of-trust gap found in scoping). Shell writes only — Edit tool path deliberately stays open so supported settings edits (visible diffs) keep working.
- **CONFIRMED:** Package installs are a HARD BLOCK (user chose memo approach over ask-tier alternative after explicit discussion) — user judged avoiding runtime-install drift worth the QoL cost. The 8 settings.json deny rules ARE included as the backup layer.
- **CONFIRMED:** Port battery into `scripts/` (66 portable cases, prune 20 gws cases), add new cases: backslash-continuation regressions, settings.json protection, benchmarks/harness/hooks path, git update-index --chmod=+x stays allowed.
- **CONFIRMED:** Install protocol: draft in workspace `staged/` → battery green → user-approved single `cp` install last (TmpProvenance pattern; memo install-order warning). User confirmed `!`-typed commands are not subject to hooks (their escape hatch for future hook maintenance).
- Out of scope (user confirmed): ask-tier technique (note-only), MCP denies (no MCP entries today), gws-safety.sh (no gws CLI).

## Integration Status

**Component:** bash-safety.sh (staged draft), settings.json (8 deny additions, live), scripts/test_safety_hooks.sh (new, live), docs (live)
**Checklist:** FRAMEWORK_INTEGRATION_CHECKLIST.md § 5 — H1 done, H1b done (battery 100755 verified; staged draft chmod +x, git-mode deferred to install), H2 N/A (registration unchanged), H3 done, H4 N/A, H5 done (battery)
**Phase 3 artifacts (framework-engineer, COMPLETED):**
- CREATED `/daaf/research/2026-07-11_hooks_revisions/staged/bash-safety.sh` — NORM_CMD fix + §7 tampering + §8 packages; §1–6 byte-identical to live (empty diff verified). NOT installed — user installs.
- CREATED `/daaf/scripts/test_safety_hooks.sh` — 79 cases; staged: 79/79 PASS; live hook: 46/79 (33 expected FAILs = the gap being closed: 11 tampering + 7 extended paths + 3 backslash + 12 packages). Zero regressions on shared cases.
- MODIFIED `/daaf/.claude/settings.json` (+8 pip/uv/uvx denies, jq-validated), `/daaf/CLAUDE.md` (defense table ×2 rows + new Safety-System Integrity & Runtime Package Installation subsections), `/daaf/agent_reference/BOUNDARIES.md` (+2 rows), `/daaf/user_reference/07_faq_technical.md` (+2 FAQ entries). README/CONTRIBUTING verified non-restating (left as-is).
**Install command (user-only, pending Checkpoint 2):** `cp /daaf/research/2026-07-11_hooks_revisions/staged/bash-safety.sh /daaf/.claude/hooks/bash-safety.sh` then `git -C /daaf update-index --chmod=+x .claude/hooks/bash-safety.sh`, then re-run `bash /daaf/scripts/test_safety_hooks.sh` (expect ALL TESTS PASSED).

## Phase 4 Review + Fix Round (COMPLETE)

**3-angle review wave (Consistency/opus, Quality/opus, Completeness/sonnet):**
- Consistency: §1–6 byte-identical to live (empty diff); path-set/deny/count all consistent. 1 WARNING (stale FAQ runtime-install entries).
- Quality (adversarial, ~30 probes): 79/79 battery green BUT found 7 real evasions (`.claude//hooks`, `.claude/./hooks`, `python3.11 -m pip`, `python -W ignore -m pip`, `pipx run`, `conda env update`, `uv run --with`; rsync missing from §7) + 2 real FPs (source-side cp backups of settings.json/hook blocked). Recommended fix-before-install.
- Completeness: H1/H1b/H2/H3/H5 verified; 2 WARNINGs (CONTRIBUTING.md doesn't point to battery; 04_extending_daaf.md teaches runtime pip install now blocked).

**Fix round (framework-engineer/opus, COMPLETED):** §7 PSEP slash-normalization + copy-verb end-anchor split (rsync added) + residual comments; §8 broadened python/pipx/conda/uv-run matchers; battery 79→97 cases; +3 conda/easy_install denies; reconciled FAQ ~393/401, 04_extending_daaf.md runtime-install section, CONTRIBUTING.md battery pointer, CLAUDE.md deny row 8→11 tools.

**Independent re-probe (adversarial reviewer, 30 probes):** all 7 evasions now BLOCK, both FPs now ALLOW, zero new evasions/FPs. Battery 97/97 staged; live hook 50/97 (47 expected-fail = gap closed). §1–6 still byte-identical. ShellCheck clean. Two accepted residuals documented in-hook (find -exec, GNU trailing flag) — same class as existing §6 residuals.

## Ready to Install (pending Checkpoint 2 approval)

**User-only install (single command; agent is now blocked from writing .claude/hooks/):**
1. `cp /daaf/research/2026-07-11_hooks_revisions/staged/bash-safety.sh /daaf/.claude/hooks/bash-safety.sh`
2. `git -C /daaf update-index --chmod=+x .claude/hooks/bash-safety.sh`
3. `git -C /daaf ls-files -s .claude/hooks/bash-safety.sh` (expect 100755)
4. `bash /daaf/scripts/test_safety_hooks.sh` (expect ALL TESTS PASSED / 97 PASS against now-live hook)

Live (already applied): settings.json (+11 denies), scripts/test_safety_hooks.sh, CLAUDE.md, BOUNDARIES.md, user_reference/07_faq_technical.md, user_reference/04_extending_daaf.md, CONTRIBUTING.md.
Scratch: research/2026-07-11_hooks_revisions/scripts/scratch/regex_proto.sh (provenance).

## Open Questions

- Adopt settings.json self-protection extension? (recommended yes)
- Adopt memo item 5 (ask-tier technique) anywhere now, or note-only? (recommended note-only)
- MCP denies (memo item 6): no MCP entries in settings.json today — defer?

## AI Disclosure

This session used DAAF (Data Analyst Augmentation Framework) in Framework
Development mode. DAAF contributed to: scoping exploration of safety hooks and
permission configuration, verification of handoff memo claims via executed
probes, and (pending) authoring of hook modifications, deny rules, regression
battery, and documentation updates. The researcher directed all framework
design decisions and approved all changes.
