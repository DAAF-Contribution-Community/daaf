# To Do: Harden Shell Write Protection for Logs and Claude Session JSONL Files

**Status:** Deferred — ready for a future Framework Development session
**Priority:** High
**Origin date:** 2026-07-18
**Work type:** Modify Existing — safety-critical Bash hook and regression coverage

## Purpose

Extend DAAF's shell-command safety boundary so ordinary Bash-mediated mutations cannot directly alter archived DAAF logs, research-project logs, or Claude Code JSONL state. The work must preserve path-only and metadata-only inspection while blocking direct write primitives whenever a protected destination is visible in the submitted command.

This document is self-contained. A future session should still re-read the live files and verify all assumptions before editing because the hook, Claude Code, and repository may have changed after 2026-07-18.

## Problem Statement

DAAF currently uses two distinct enforcement layers:

1. Claude Code permission rules in `/daaf/.claude/settings.json` govern built-in file-editing tools.
2. `/daaf/.claude/hooks/bash-safety.sh` inspects submitted Bash command text before execution.

The settings layer now denies built-in edits for these path classes:

```text
/.claude/logs/**
//home/appuser/.claude/**/*.jsonl
/research/*/logs/**
```

Each path has both `Edit(...)` and `Write(...)` entries. `Edit(...)` is the forward-compatible operative form in current Claude Code documentation. Retaining `Write(...)` for the installed Claude Code 2.1.202 is a conservative compatibility **inference** from the documented version boundary, not behavior proven by current documentation or a runtime evaluator. When DAAF upgrades to Claude Code 2.1.210 or later, remove the path-scoped `Write(...)` entries: the current documentation says they are accepted but unmatched at those versions and generate startup warnings.

Those settings rules do **not** make Bash writes safe. The live hook already detects several direct mutations of project `.claude/logs`, but its protection is command-form-dependent and does not presently define `/home/appuser/.claude/**/*.jsonl` or research-project `logs/` directories as protected target classes. Wrapper commands, interpreters, alternate redirections, and runtime path indirection create additional gaps.

## Protected Path Classes

The future hook change must cover:

1. DAAF project logs:
   ```text
   /daaf/.claude/logs/**
   .claude/logs/**
   /.claude/logs/**
   ```

2. Research-project archived logs, where one direct child of `/daaf/research` is the project folder:
   ```text
   /daaf/research/<project-folder>/logs/**
   research/<project-folder>/logs/**
   /research/<project-folder>/logs/**
   ```

3. Every `.jsonl` beneath the Claude configuration volume:
   ```text
   /home/appuser/.claude/**/*.jsonl
   ~/.claude/**/*.jsonl
   $HOME/.claude/**/*.jsonl
   ${HOME}/.claude/**/*.jsonl
   ```
   The home-variable forms can be blocked only when recognizable in the submitted command.

### Absolute content boundary

Never open, display, grep inside, parse, hash, line-count, copy, move, touch, truncate, or otherwise consume or alter the contents of a real `.jsonl` file while developing or testing this change. Path names and filesystem metadata—type, mode, owner, byte size, and timestamps—are sufficient for inventory. Tests must feed synthetic command strings to the hook; they must not execute the represented mutations.

## Objective

Modify `bash-safety.sh` so a submitted Bash command is denied when it visibly attempts to mutate a protected target through a supported write primitive, including when that primitive appears behind a common wrapper or interpreter carrier.

The hook should remain fail-closed on parsing ambiguity affecting these safety-critical paths and should produce an actionable denial message that identifies the protected log/transcript boundary without printing file contents.

## Non-Goals

This task does not promise an OS-level write prohibition. In particular, it does not guarantee detection of:

- destinations assembled entirely from runtime variables;
- encoded or dynamically decoded paths;
- paths inherited through an already-established current working directory;
- writes through previously opened file descriptors;
- interpreter programs that derive the destination without a recognizable protected fragment;
- kernel-, process-, mount-, or container-level mutations outside Claude Code's tool path.

A later design may investigate sandbox `denyWrite`, mount policy, or filesystem permissions as a separate defense. Do not add those mechanisms silently to this task: they have broader compatibility and deployment implications and require their own scoping checkpoint.

## Required Mutation Coverage

For each protected path class, map and test the following families.

### Redirections and shell file opens

Block visible protected destinations used with:

```text
>
>>
>|
<>
2> and other numbered file-descriptor redirects
3>> and other numbered appends
&>
&>>
```

Include here-document and here-string commands when their output is redirected to a protected destination. Account for quoting, repeated slashes, and intervening `./` segments.

### Direct filesystem mutation tools

Cover at minimum:

| Family | Commands / forms |
|---|---|
| Stream output | `tee`, including append mode |
| Copy/move/sync | `cp`, `mv`, `rsync`, `install` |
| Removal/linking | `rm`, `ln` |
| Raw/write utilities | `dd`, `truncate`, `touch` |
| In-place editing | `sed -i` and accepted equivalent in-place forms |
| Metadata mutation | `chmod`, `chown`, `chgrp`, `chattr` where available |

Do not rely solely on the mutating command appearing at the start of a shell segment. Test destinations followed by trailing options as well as conventional destination-final forms.

### Wrappers and alternate command positions

Map and block protected mutations routed through:

```text
find ... -exec
xargs
env
command
time
nice
pipeline-position commands
```

The scanner should distinguish a read-only `find` inventory from a mutating `find -exec` action.

### Shell and interpreter carriers

When a protected target is visible in the submitted command, cover mutation programs carried by:

```text
bash -c
sh -c
python / python3
perl
ruby
node
```

The design must explicitly document whether it blocks any interpreter invocation containing a protected literal or attempts a narrower write-capability test. For safety-critical transcript paths, favor a clear fail-closed rule over fragile parsing of arbitrary program text, but include ALLOW controls to measure false positives.

### Working-directory shortcuts

Evaluate `cd` and `pushd` into protected directories. DAAF's one-command-per-call hook reduces ordinary multi-command state changes, but shell carriers and persistent shell behavior may still make short relative writes possible. Document what is blocked and what remains beyond lexical inspection.

## Design Constraint: Lexical Inspection Is Not Semantic Resolution

`bash-safety.sh` receives command text, not the process's eventual system calls. It can normalize and inspect recognizable path fragments, command tokens, quoting, and redirections; it cannot prove the runtime destination of every write.

The completed change must state this limitation in:

- hook comments near the protected-target logic;
- the regression battery's scope statement;
- the relevant Defense-in-Depth documentation if user approval includes that file;
- the final Framework Development checkpoint.

Do not describe the result as making JSONL files immutable or impossible to modify. The accurate claim is that DAAF blocks the tested direct and wrapper-mediated Bash forms when a protected destination is statically recognizable.

## Likely Files to Modify

Read every target in full before editing and confirm the list during Framework Development Checkpoint 1.

| File | Expected role |
|---|---|
| `/daaf/.claude/hooks/bash-safety.sh` | Live safety hook; human-controlled deployment target only after a staged draft passes validation |
| `/daaf/scripts/test_safety_hooks.sh` | Standing synthetic command-envelope regression battery; add primitive × path-class cases |
| `/daaf/tests/bash/bash_safety.bats` | Focused BATS coverage using the `BASH_SAFETY_SH` draft override |
| `/daaf/CLAUDE.md` | Update the Defense-in-Depth description only with explicit user approval |
| `/daaf/.claude/skills/shell-scripting/references/testing.md` | Update battery documentation if invocation or coverage contracts change |
| A dated Framework Development workspace | Hold `bash-safety.sh.proposed`, session notes, and any losslessly persisted review/research notes |

The current static settings test is `/daaf/tests/bash/settings_permissions.bats`. It verifies the structured-tool rules but is not a Bash-hook test and must not be repurposed to claim runtime matcher coverage.

## Staged Draft and Human-Controlled Deployment

The live hook is safety-protected. Follow this sequence:

1. Start a new Framework Development session and complete Phase 1 scoping.
2. Run the existing live-hook regression suites to establish a green baseline.
3. Copy the live hook into a dated research workspace as a proposed draft using the repository's approved workflow.
4. Modify only the staged draft during authoring.
5. Test the draft with:
   ```bash
   bash /daaf/scripts/test_safety_hooks.sh /absolute/path/to/bash-safety.sh.proposed
   BASH_SAFETY_SH=/absolute/path/to/bash-safety.sh.proposed bats /daaf/tests/bash/bash_safety.bats
   ```
6. Run parser and ShellCheck validation on the draft.
7. Complete adversarial, consistency, and completeness reviews.
8. Present Framework Development Checkpoint 2.
9. Only after explicit user approval, have the user deploy the byte-identical tested draft to `/daaf/.claude/hooks/bash-safety.sh` through a host editor or a user-typed command.
10. Verify the deployed hook is byte-identical to the tested draft and that Git still records mode `100755`.
11. Re-run the live-hook suites and workspace invariant checker.

Do not use opaque shell writes to modify the live hook. Do not weaken or deregister any safety hook to make deployment easier.

## Required Regression Matrix

All cases must live inside the battery/BATS files and reach the hook through a synthetic PreToolUse JSON envelope. Never put dangerous case strings in the outer invocation command.

### BLOCK controls

For representative targets from all three protected path classes, include:

- direct and nested paths;
- project-relative, settings-root-like, and absolute forms;
- single-quoted and double-quoted targets;
- repeated `/` and embedded `./` segments;
- every supported redirection;
- every direct mutation command listed above;
- trailing-option variants for copy-style commands;
- wrapper forms (`find -exec`, `xargs`, `env`, `command`, `time`, `nice`);
- shell carriers and each supported interpreter;
- `~`, `$HOME`, and `${HOME}` home-path spellings;
- `cd`/`pushd` cases chosen during design.

Use synthetic examples such as `example.jsonl`. Do not point a case at a real session UUID or archive path when a representative fake path proves the rule.

### ALLOW controls

Preserve legitimate metadata and similarly named non-target work:

- `stat` on a protected path;
- path-only `find ... -printf` without mutating `-exec` actions;
- `findmnt` for mount metadata;
- directories named `logs` outside the three protected classes;
- a non-JSONL file under `/home/appuser/.claude/`;
- a `.jsonl` path outside `/home/appuser/.claude/`;
- safe commands that merely discuss a protected pattern in a shell-inert commit message, consistent with the existing quote-aware carve-out;
- false-positive probes for interpreter commands that do not write, according to the selected fail-closed design.

### Anti-vacuity requirements

- Include at least one self-test or deliberate draft mutation proving that the new test selection fails when one protected class is removed.
- Report counts from actual test output, not memory.
- Keep project-log, research-log, and Claude-home JSONL cases separately identifiable in failure output.

## Validation Commands

Probe each tool before declaring it unavailable. Expected validation includes:

```bash
bash -n /absolute/path/to/bash-safety.sh.proposed
shellcheck -x -S warning /absolute/path/to/bash-safety.sh.proposed
bash /daaf/scripts/test_safety_hooks.sh /absolute/path/to/bash-safety.sh.proposed
BASH_SAFETY_SH=/absolute/path/to/bash-safety.sh.proposed bats /daaf/tests/bash/bash_safety.bats
git -C /daaf diff --check
bash /daaf/scripts/check_workspace_invariants.sh
git -C /daaf ls-files -s .claude/hooks/bash-safety.sh scripts/test_safety_hooks.sh
```

After human deployment, additionally require an empty `diff` between the proposed and live hooks and rerun the battery against the live hook.

## Review Plan

Because this is a Moderate safety-critical hook modification, run three independent read-only reviews in one complete wave:

1. **Consistency review:** path classes, docs, tests, denial messages, and duplicated descriptions agree.
2. **Security/quality review:** adversarially search for direct forms the live hook blocks but the draft newly allows, new bypasses in the added logic, false positives, parser ambiguity, and performance/pathological-input issues.
3. **Completeness review:** verify `/daaf/agent_reference/FRAMEWORK_INTEGRATION_CHECKLIST.md` §5 items HM1–HM7, executable modes, test wiring, and documentation surfaces.

Do not synthesize or act on partial review returns; wait for the complete wave.

## Acceptance Criteria

The task is complete only when all of the following are observed:

- [ ] Phase 1 re-verifies the live hook and affected files before edits.
- [ ] Project `.claude/logs`, direct research-project `logs`, and Claude-home `.jsonl` targets have explicit tested coverage.
- [ ] The required direct primitives, redirection variants, wrappers, and interpreter carriers are represented in tests.
- [ ] Read-only metadata ALLOW controls remain green.
- [ ] Existing safety-hook regression cases remain green.
- [ ] The staged draft passes `bash -n` and ShellCheck.
- [ ] The complete safety battery and focused BATS suite pass against the staged draft.
- [ ] All three reviews return and any confirmed issues are resolved or explicitly accepted by the user.
- [ ] Workspace invariants pass.
- [ ] The user approves deployment.
- [ ] The deployed live hook is byte-identical to the tested draft and remains Git mode `100755`.
- [ ] Post-deployment live suites pass.
- [ ] The final report distinguishes tested lexical coverage from unproven OS-level immutability.

## Dependencies and Scope Boundaries

- Use Framework Development mode and obtain explicit approval before modifying settings, hooks, or CLAUDE.md.
- Follow `/daaf/agent_reference/FRAMEWORK_INTEGRATION_CHECKLIST.md` §5 HM1–HM7.
- Follow `/daaf/.claude/skills/shell-scripting/references/testing.md` for draft-path battery and BATS conventions.
- Preserve the absolute prohibition on consuming real JSONL contents.
- Do not install runtime packages.
- Do not modify CI workflows without separate authorization.
- Do not commit unless the repository's Git commit preference is enabled and the user separately approves the commit.
- Do not expand this task into sandbox, mount, ownership, retention, archival, or backup-policy changes without a new scope checkpoint.

## References

- Claude Code permissions documentation: https://code.claude.com/docs/en/permissions
- Universal DAAF rules: `/daaf/CLAUDE.md`
- Hook integration checklist: `/daaf/agent_reference/FRAMEWORK_INTEGRATION_CHECKLIST.md` §5 HM1–HM7
- Shell test guidance: `/daaf/.claude/skills/shell-scripting/references/testing.md`
- Current static settings contract: `/daaf/tests/bash/settings_permissions.bats`
- Live hook: `/daaf/.claude/hooks/bash-safety.sh`
- Standing shell battery: `/daaf/scripts/test_safety_hooks.sh`
- Focused Bash safety BATS suite: `/daaf/tests/bash/bash_safety.bats`
