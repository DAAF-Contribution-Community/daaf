# Learnings: Safety Hook Hardening (2026-07-11)

**Session:** Framework Development — bash-safety.sh anti-tampering + package-install guards
**Commit:** 89a18d3 (`feat(safety): anti-tampering + package-install guards for bash-safety hook`)

## Observation

After the hardened hook went live, two consecutive `git commit -m` attempts were
themselves blocked by the new guards — not because they did anything unsafe, but
because the **commit message text described the blocked commands**. The hook
scans the entire command string (message included), so descriptive prose that
recites trigger tokens matches the guard.

Root cause: a subset of the new checks match by word boundary anywhere in the
command string, rather than being anchored to a command-segment start the way the
mutation-verb and pip/uv checks are. Specifically:

- §7 in-place-edit check `\bsed [^|;&]*-i[^|;&]*(PROTECTED_DIRS)` — un-anchored.
  Tripped by a message containing an in-place-sed phrase followed later by a
  protected path.
- §8 tool-name alternation — the ephemeral-runner/legacy-installer/conda branch
  uses bare word-boundary anchors (`\b...\b`) for two of its three alternatives,
  while the leading uvx alternative is segment-anchored. The two word-boundary
  alternatives match those tool names in prose.

By contrast, the mutation-verb (§7), redirect (§7), and pip/pipx/uv (§8) checks
are anchored to `(^|[;&|])` and did **not** fire on prose, because the only
command-segment start in a `git commit` invocation is `git` itself.

## Impact

Low severity, benign, but a real usability wrinkle: any Bash command whose *text*
enumerates these specific tokens (a `git commit -m`, an `echo`/heredoc, a doc-gen
command) will be blocked. Workarounds are trivial (reword to a higher level of
abstraction, use the Edit tool, or run via a user-typed `!` command). No safety
weakness — the guard is over-eager on descriptive text, not under-eager on real
commands. The adversarial review had flagged "commit-message mentions" as a
candidate false-positive class; this confirms it for the two un-anchored checks.

## System Update Action Plan

| # | Learning | Target File | Change Type | Proposed Change | Priority | Source Project |
|---|----------|-------------|-------------|-----------------|----------|----------------|
| 1 | Two new safety checks match blocked tokens in descriptive prose because they are un-anchored | `.claude/hooks/bash-safety.sh` (LIVE safety file — requires staged-draft → user-install protocol; agent cannot self-install) | Modify Existing | Anchor the §7 `sed -i` check and the §8 `easy_install`/`conda` alternatives to command position `(^\|[;&\|]) ?`, matching how the mutation-verb and pip/uv checks are already anchored, so descriptive text (commit messages, echoes) stops tripping them. Verify real in-place-edit and real conda/easy_install invocations still BLOCK. | P3 | 2026-07-11_hooks_revisions |
| 2 | Regression battery lacks cases proving prose/description does not false-trigger | `scripts/test_safety_hooks.sh` | Modify Existing | Add ALLOW cases for command strings that *mention* blocked tokens without invoking them: a `git commit -m` whose message names `sed -i`, `easy_install`, `conda install`, and a protected path; an `echo` mentioning `pip install`. These lock in the anchoring fix from item 1 and prevent regression. | P3 | 2026-07-11_hooks_revisions |

## Notes for whoever picks this up

- Both items are a matched pair — item 2's ALLOW cases will fail until item 1's
  anchoring lands, so do item 1 first, then add the cases and confirm 100% pass.
- This is a live safety file: draft in a scratch/staged path, run the battery
  against the draft, then hand the single `cp` install to the user (the hook now
  blocks agent writes into `.claude/hooks/`). Same protocol used this session.
- Do NOT over-correct: the goal is to stop matching *prose*, not to narrow what
  real commands are caught. Keep the un-anchored behavior's security intent — a
  real `sed -i ... .claude/hooks/x` or `conda install x` must still BLOCK.
- Deliberately left as a follow-up rather than fixed in-session: changing a live
  safety file warrants its own scoped Framework Development pass with a fresh
  review, not a tail-end edit to an already-reviewed commit.
