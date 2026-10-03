#!/usr/bin/env bash
# bash-safety.sh — PreToolUse hook that blocks dangerous Bash commands
#
# This is the primary safety guardrail for this project's container (DAAF and
# the Claude Code Starter Kit share this body; see SITE CONFIG). It reads
# the tool invocation JSON from stdin and inspects the command field for
# patterns that are destructive, privilege-escalating, or data-exfiltrating.
# It also enforces safety-system integrity (section 7): shell writes to the
# hook, log, and settings files bypass the Edit/Write deny rules and are
# blocked as user-only; ad-hoc package installation (section 8): runtime
# package changes drift from the Dockerfile and are blocked; and a provenance
# boundary (section 6): model-initiated shell writes to /tmp, /var/tmp and
# /dev/shm are blocked because they are outside the Docker-volume backup
# boundary and the audit trail.
#
# Exit codes (Claude Code PreToolUse convention):
#   0 = allow the command to proceed
#   2 = BLOCK the command (stderr message shown to the model)
#
# Design principle:
#   Block the dangerous *pattern*, not the tool. For example, `git push`
#   is fine (the permission prompt handles it), but `git push --force`
#   rewrites remote history and is always blocked. Similarly, `curl <url>`
#   is fine, but `curl <url> | bash` is arbitrary code execution. The /tmp
#   provenance guard follows the same principle: reading the hooks' own /tmp
#   coordination caches is fine, but *writing* working files there is blocked.
#
# Fail-closed input posture (2026-09-26, harmonization fix 1): the hook BLOCKS
#   (exit 2) when jq is missing, when stdin is empty, and when stdin is not
#   exactly one JSON object (unparseable text, a bare scalar or array,
#   whitespace only, or several concatenated JSON values). Before this, any
#   such stdin made `jq -r .tool_name` fail or print several lines, TOOL_NAME
#   was not exactly "Bash", and the hook ALLOWED at the non-Bash gate — which
#   contradicted the fail-closed contract above. A concatenated payload (a
#   benign object followed by a Bash one) slipped past that gate the same way.
#   Claude Code sends exactly one object per call, so this is defence in
#   depth. CREDIT: the finding and the gate's wording come from DAAF's
#   2026-09-24 hook-maintenance session (Claude Code 2.1.281 upgrade), which
#   found the class in enforce-file-first.sh
#   (research/2026-09-24_FrameworkDev_ClaudeCode_Upgrade_2.1.281/hook_patches/
#   enforce-file-first.diff); DAAF's orchestrator then confirmed it reached
#   this hook (probe K03-K11: all ALLOWED before the gate).
#
# ===========================================================================
# CLASSIFICATION PIPELINE (stages 0a-0e), rewritten 2026-09-18
# ===========================================================================
#   The pattern checks in sections 1-8 are raw-string regexes. They cannot,
#   by themselves, tell a command that IS dangerous from a string that merely
#   DESCRIBES one. Stage 0 builds SCAN_CMD — a working copy of the command in
#   which every span of text has been classified as DATA or CODE — and
#   sections 1-8 then scan SCAN_CMD instead of the raw text.
#
#   Classification vocabulary (used throughout the stage-0 comments):
#     EXCISE       — remove the span entirely, leaving an inert placeholder
#                    (` __QARG__ `, ` __HDOC__ `). OPT-IN: only when the span's
#                    RECEIVER is provably a data consumer (see 0a's heredoc
#                    receiver allowlist and 0c's `_DATACONS_RE`/`_GITDATA_RE`).
#     CANONICALIZE — strip the quote/escape characters, KEEP the content, so
#                    an obfuscated command name (`"rm"`, `r\m`, `r'm'`) is
#                    scanned in its canonical spelling. Never weaker.
#     PROMOTE      — the span is a code carrier's body (`bash -c '…'`,
#                    `eval '…'`, `find -exec sh -c '…'`). Strip the quotes AND
#                    insert a `; ` separator so the body's first word becomes
#                    segment-anchored and every command-position guard sees it.
#     KEEP         — leave the span byte-for-byte intact; it is scanned as
#                    today. Every ambiguous parse degrades to KEEP.
#
#   MONOTONICITY CONTRACT (restated 2026-09-18 fix cycle 1): text is removed
#   only when its RECEIVER IS PROVABLY A DATA CONSUMER; otherwise the quotes
#   are stripped and the content is scanned. Concretely, EXCISE is the only
#   stage-0 operation that can remove text, it is OPT-IN, and it fires only
#   when (a) the span is a whole-word quoted ARGUMENT that is shell-provably
#   inert AND (b) the command receiving it is on an explicit data-consumer
#   allowlist (0a: HEREDOC_DATA_CONSUMERS + `git commit`; 0c: `_DATACONS_RE`,
#   `_GITDATA_RE`, `git commit -m`). Every other span CANONICALIZES, PROMOTES
#   or is KEPT — all of which preserve or strengthen the scan. Consequently no
#   stage-0 change can make this hook weaker than the pre-2026-09-18 hook
#   against anything that hook already caught, except where a case was an
#   acknowledged false positive.
#
#   Stage order (each stage feeds the next):
#     0a  heredoc-body excision      — runs on the RAW multi-line command,
#                                      before whitespace collapse, because it
#                                      needs line structure.
#     --  NORM_CMD                   — drop backslash line-continuations, then
#                                      collapse whitespace to single spaces.
#     0b  `git commit -m` message excision (the original 2026-07-17 §0).
#     0c  general quoted-span classification.
#     0d  escape canonicalization (`r\m` → `rm`).
#     0e  `$IFS` hard block.
#
#   CARRIER LIST (0c PROMOTE): `eval`, `xargs`, `source`, `.`, `ssh`, `su`,
#   `sudo`, `find -exec/-execdir/-ok`, and any short-flag bundle containing
#   `-c` OR `-C` (`-c`, `-C`, `-lc`, `-ec`, `-cm`) whose receiver is a shell
#   (`bash sh zsh dash ksh mksh busybox su sudo ssh env`), optionally reached
#   by an absolute or relative PATH (`/bin/bash -c`), optionally preceded by
#   the shell's own flags (`bash -x -c`, `bash --norc -c`), and optionally
#   followed by `--` (`bash -c -- '…'`). Wrappers before the shell
#   (`timeout 5 bash -c`, `nohup bash -c`, `env bash -c`) are covered because
#   the shell token itself is matched anywhere in the left context.
#
#   HEREDOC RECEIVER ALLOWLIST (0a): a heredoc body is DATA only when its
#   receiver is a data consumer. SOURCE: qwen-code PR #10446, quoted in
#   output/preliminary_notes/2026-09-18_research_community-guard-hooks.md §2 —
#   "Removing it and stripping bodies for any bare receiver reintroduces 53
#   hand-corpus and 91 fuzz cases where a deny'd command runs with no prompt
#   at all — measured." A heredoc into bash/sh/python/node/R IS code and its
#   body is KEPT (and `;`-joined so each body line is segment-anchored).
#
#   GUARDFALL CLASSES (Adversa AI taxonomy; see
#   output/preliminary_notes/2026-09-18_research_guardfall-and-data-vs-code.md
#   §1, §3, §4) and their status after this revision:
#     A  quote/escape merge (`"rm"`, `r''m`, `s\udo`)   — CLOSED by 0c + 0d.
#     B  `$IFS` word-splitting obfuscation              — CLOSED by 0e.
#     C  substitution-computed binary names             — RESIDUAL (see below).
#     D  pipeline into an interpreter                   — PARTIAL, §4.
#     E  alternative argv shapes vs. protected paths    — PARTIAL, §7.
#
#   ACCEPTED RESIDUALS (unchanged risk, documented not fixed):
#     - Class C: `$(echo rm) -rf /` — a substitution that COMPUTES a command
#       name is not evaluated here. Only the existing `$(`/backtick openers in
#       §1/§3/§5 catch the common shapes.
#     - Interpreter bodies are canonicalized and scanned for literal patterns
#       but not decomposed — a dangerous command *computed* inside python/perl/
#       node/R code is not caught. (A LITERAL pattern in such a body does
#       block: `python3 -c "os.system('rm -rf /')"`, `perl -e`, `node -e`,
#       `Rscript -e 'system(…)'` are cases FC09-FC12.)
#     - cwd-relative evasion: `cd .claude` in one call then `cp x hooks/y` in
#       the next is beyond single-command string matching.
#     - Program-argument /tmp writes: `python x.py /tmp/out/` (see §6).
#     - Spans beyond the 64-span / 20-heredoc bounds are KEPT (fail-closed).
#     - Commands longer than 20 000 characters skip stages 0c AND 0d entirely
#       (the global size guard below) and are scanned raw, exactly as the
#       pre-2026-09-18 hook did. Above 20 kB the prose false-positive class
#       therefore returns — a long document mentioning `sudo apt update` inside
#       an `echo` can block — which is the deliberate fail-closed trade.
#   The container posture (non-root, `cap_drop: ALL`, no host $HOME) bounds the
#   blast radius of every residual: the credential-exfiltration harm that
#   dominates GuardFall's threat model is already removed. What container
#   isolation does NOT protect is `.claude/hooks/`, `.claude/logs/`,
#   `.claude/settings.json` and `.claude/settings.local.json` — the PRIMARY
#   PROTECTED ASSET of this hook, guarded by §7, together with any site-specific
#   directories listed in SITE_EXTRA_PROTECTED_DIRS (DAAF:
#   `benchmarks/harness/hooks/`, which registers an active PreToolUse hook).
#
# Normalization note:
#   NORM_CMD drops backslash line-continuations before collapsing whitespace,
#   so a multi-line command (`cp f \` ⏎ `.claude/hooks/x`) cannot slip a stray
#   `\` token between a verb and its target and defeat the adjacency patterns
#   in sections 1-5.
#
# Implementation constraints (deliberate):
#   bash-internal `[[ =~ ]]` (POSIX ERE) plus grep/sed — no extra dependencies
#   beyond jq. No `set -e` (the ERR trap is the failure posture). Every loop is
#   bounded and counts progress with `_iter=$((_iter + 1))`, never `((i++))`
#   (which returns 1 when the result is 0 and would fire the ERR trap).
#
# Hook event: PreToolUse (matcher: "Bash")
# Registered in: .claude/settings.json
#
# ===========================================================================
# HARMONIZED FILE (2026-09-26) — shared by DAAF and the Claude Code Starter Kit
# ===========================================================================
#   PROVENANCE CHAIN
#     1. DAAF hardened draft, 2026-09-18 (stages 0a-0e + §1-§8 rewrite; DAAF
#        red-team rounds 1-3, fix cycles 1-2; 1,415 lines).
#     2. Starter-kit port, 2026-09-24: DAAF's R3-F1/R3-F2 applied, then the
#        starter kit's own red-team rounds 3-5 (their REDTEAM_R4/R5 reports):
#        F1-F20, R5-T1, G10-G43, C1-C5, D1-D6, S1 (1,992 lines, verdict SHIP).
#     3. DAAF fix cycles 3-4, 2026-09-24, in parallel on DAAF's own draft: the
#        shared pipe-receiver vocabulary, receiver terminators, quoted/escaped
#        receivers, extra shells + dot-source, flag-ARG wrapper items, the
#        `$mount` opener fix, and the `$(curl …)` family (b1/b2).
#     4. Harmonized 2026-09-26: the starter-kit round-5 file is the BASE; the
#        DAAF cycle-3/4 work in (3) is ported onto the base's regexes and
#        reconciled with its F6/F7/F7b/F12/F20 (one implementation each, no
#        duplicates). Every ported change carries a dated comment
#        `2026-09-26 (harmonization, DAAF cycle-3/4 port: …)` at its site.
#
#   SITE CONFIG (the block right after this header)
#     Both projects run this BYTE-IDENTICAL body. Every project-specific value
#     lives in the SITE CONFIG block, and `diff` of the two projects' files
#     must show only lines inside that block. Values:
#       SITE_ROOT                   absolute project root (regex-safe chars
#                                   only: letters, digits, `_`, `-`, `.`, `/`).
#                                   Drives the §1 root targets (`rm -rf
#                                   <root>/*`, `<root>/.*`, F9 backstop, G28),
#                                   G29 `<root>/.git`, G43 `find <root>
#                                   -delete`, G10 `<root>/.claude`, the
#                                   `$VAR/<top-level>` list (_RM_VARTOP), and
#                                   the paths in the §9 Remotion message.
#       SITE_EXTRA_PROTECTED_DIRS   extra §7 protected directories beyond
#                                   `.claude/hooks`, `.claude/logs`,
#                                   `.claude/settings*.json` (DAAF:
#                                   `benchmarks/harness/hooks`). Dots are
#                                   escaped and `/` widened to PSEP. Four §7
#                                   block messages (copy, target-verb,
#                                   redirect, in-place edit) name them via
#                                   _PROT_LABEL; the others do not list paths.
#       SITE_SCRATCH_DIR            where §6 tells the model to put temp files.
#       SITE_REBUILD_HINT           the §8 "rebuild …" wording.
#       SITE_ENABLE_REMOTION_GUARD  1 = run §9, the starter kit's Remotion
#                                   bundle-per-call disk guard (site extension;
#                                   0 at DAAF, where the section is inert).
#       SITE_REMOTION_DIR           the Remotion project directory §9 names.
#     Values DERIVED from these (_ROOT_RE, _ROOT_TOP, _PROT_LABEL right after
#     the block; _PROT_EXTRA in §7, next to PROTECTED_DIRS) are computed in the
#     shared body — never edit them per site.
#     The home directory is matched generically (`/home/<any user>`), not by
#     a site user name.
#
#   CHANGE LEDGER — starter-kit rounds 3-5 (fix ids are marked at their sites)
#     R3-F1  §5 mount guard opens on a quote-bearing set (A03/A04); refined by
#            the DAAF port to SEG_OPEN_MNT (below).
#     R3-F2  `|&` and wrapper-prefixed 0c pipe receivers; superseded by the
#            shared receiver vocabulary (below).
#     F1-F20 (round 4): F1 protected-destination end anchor accepts a
#            following separator/redirect; F2/F2b mv, shred, unlink, git rm/mv
#            as target verbs, /bin-qualified verbs, -t/--target-directory; F3
#            VAR= after wrappers; F4 shell keywords as segment openers; F5
#            dot/glob/home/top-level/.claude rm targets; F6 heredoc pipe
#            receivers; F7/F7b wrapped curl receivers and `bash -c "$(curl …)"`;
#            F8 git push/branch flag bundles; F9 word-anywhere backstop for
#            catastrophic rm targets; F10 no excision inside `$(`/`<(`/
#            backtick; F11a/b write-then-execute; F12 unquoted echo/printf
#            feeding a shell; F13 0c window 64 -> 256; F14 single-word
#            `git log -S` pattern excised; F15 /tmp argv shapes; F16 pip/uv
#            spellings; F17 `sed -Ei`, `perl -pi`; F18 `>|` and glob
#            components under .claude/; F19 `\/` folding in 0d; F20 more
#            wrappers (doas ionice chrt taskset stdbuf unshare nsenter strace
#            ltrace flock chronic).
#     Round 5: R5-T1 write-then-execute counts only an EXECUTION-position
#            recurrence (`_exec_recurs`); G10 copy/move/extract into `.claude`
#            itself; G11 find -exec / xargs mutations of protected paths; G28
#            `rm -rf /*$(…)`; G29 recursive rm of the project `.git`; G36a
#            `//tmp`, `/./tmp`; G36b plain ANSI-C `$'…'` canonicalized; G37
#            `mkdir -p --`, `tar -C/tmp`, `--directory=`; G39 git global options
#            before the verb, tree-ish before `.`, `checkout -f`; G40
#            path-qualified sudo/su/mount/chroot; G41 `chmod 1777`, comma-list
#            modes, `install -m`; G43 unfiltered `find <root> -delete`; C1
#            `git switch -f`/`--discard-changes`; C2 `doas`; C3 `chmod
#            --reference=<system path>`; C4 0a line bail 4000 -> 1000; C5a/b a
#            quoted span written to a file the command then executes is
#            promoted, and a typed `\n` in a promoted body becomes `; `.
#     G10 and G29 were user-ratified at BOTH sites (starter kit D8/D9; DAAF
#     2026-09-26 decision (2)).
#
#   CHANGE LEDGER — DAAF cycle-3/4 port (2026-09-26)
#     P1  PIPE_OP / PIPE_RECV_PRE / PIPE_SHELLS / PIPE_INTERPS / PIPE_RECV_END:
#         ONE receiver vocabulary for 0a _HD_PIPE_RE, 0c _PIPEFEED_RE, F12's
#         _EF1 and both §4 downloader guards (flag-ARG wrapper items, bare
#         numbers, quoted VAR= values; `mksh ash fish csh tcsh \.`; right
#         terminators `; & | )` backtick). `env` is a wrapper, never a receiver
#         NAME. The heredoc list keeps F6's `ssh sudo su`.
#     P2  quote/backslash-stripped copy of the tail (0c rule 5a) and of the
#         heredoc line (0a) is tested as well (`| "bash"`, `| ba\sh`,
#         `| env 'bash'`, `| env -S 'bash -x'`).
#     P3  _PIPEFEED_RE left run admits `2>&1`, `>&`, `&>`, `|&` as units.
#     P4  SEG_OPEN_MNT for both §5 mount guards (no bare `$`: `ls $mount`
#         and friends stop false-blocking; the quote opener stays for R3-F1).
#     P5  one `$(curl …)` download-execute guard = F7b ∪ DAAF b1 ∪ DAAF b2.
#
#   CHANGE LEDGER — post-merge (both sites)
#     G29q  2026-09-26 (harmonization, G29 quoted form): _ROOTVAR, the project
#           root through a variable with an optional double quote on each side
#           (0c rule 5b KEEPS `"${…}"` spans with their quotes), shared by
#           _RM_ROOT, G29 and G43. Closes `rm -rf "${CLAUDE_PROJECT_DIR}/.git"`,
#           `rm -rf "${BASE_DIR}"`, `rm -rf "${PROJECT_DIR}/*"`, `rm -rf
#           $CLAUDE_PROJECT_DIR/`, `find "${CLAUDE_PROJECT_DIR}" -delete`.
#     HF1   2026-09-26 (harmonization fix 1), both sites:
#           (a) WRAPPERS argument run: named argument-taking flags + one
#               token, non-command-shaped tokens, and the flock/taskset
#               positional operand (`timeout -s KILL 5 docker run`, `env -u
#               HOME cp … .claude/hooks/`, `xargs -I {} cp …`, `flock lk
#               docker run`) — consistency-review BLOCKER B1, a regression vs
#               the pre-2026-09-18 hook in both projects;
#           (b) _HOMEVAR/_CWDVAR: `rm -rf "${HOME}"`, `"${HOME}/"`,
#               `"${PWD}"`, `"${OLDPWD}"`, `find "${HOME}" -delete` (the
#               former braced-home/cwd residual; user-approved);
#           (c) the one-object stdin gate (see "Fail-closed input posture");
#           (d) comment corrections (SEG_OPEN_Q users and quote-survival
#               sources, §5 opener history, §4 receiver boundary).
#
#   CHANGE LEDGER — section 10 accidental environment-disclosure guard (2026-10-02)
#     E1  New section 10 (ENV_DISCLOSURE_GUARD), placed after section 9, before
#         the final allow. Four categories mirror run_with_capture.sh's env-
#         print scan: A whole-env dump (bare env/set/export -p/printenv, no
#         operand); B credential-named value to output/file (echo/printf + an
#         unescaped $NAME, or declare -p/typeset -p/printenv NAME); C a
#         /proc/<pid>/environ read; D an interpreter one-liner printing a whole-
#         env object. Functional accidental shapes only, not an adversarial
#         sieve (same posture as section 8b's _EF1 / R5-T1).
#     E2  "credential-named" is decided WITHOUT the SECRET-NAME-VOCAB carriers
#         (orchestrator decision 2026-10-01 after a repo NAME census): an
#         UPPERCASE name whose LAST underscore segment is one of KEY APIKEY
#         TOKEN SECRET PASSWORD PASSWD PASSPHRASE CREDENTIAL CREDS DSN PAT;
#         single-segment names, plurals, and ..._SESSION/..._AUTH/..._COOKIE are
#         exempt. bash-safety carries NO vocab copy and no carrier marker, so
#         the "does NOT carry it" comments in output-scanner.sh / audit-log.sh
#         stay accurate.
#     E3  Additive accumulator (_ENV10_ACC): 0a records an unquoted-delimiter
#         data-consumer heredoc body; 0c records a double-quoted excised span
#         containing `$`. Category B scans it alongside SCAN_CMD. NO stage-0
#         classification changed - the accumulator only keeps a copy, so no
#         ALLOW->BLOCK or BLOCK->ALLOW shift in sections 1-9 is possible.
#     E4  grep -E for all section-10 matching (not bash `=~`) to avoid nested-
#         quantifier backtracking; a cheap bash substring prefilter skips the
#         greps on the common path.
#     E5  (_c, 2026-10-03, task B3 FP gate) category D's bare ENVIRON token
#         gained a trailing boundary ([^A-Z0-9_[]|$). Without it, an interpreter
#         one-liner naming an identifier that merely STARTS with ENVIRON
#         (ENVIRONMENT, ENVIRON_LABEL) false-blocked (measured against the
#         recorded-session + docs corpora). A pure tightening of a new section-10
#         alternative: it can only turn a section-10 block into an allow, never
#         create a block, so no ALLOW->BLOCK is introduced and no section-1..9
#         behavior changes. awk whole-env forms (`print ENVIRON`, `for (k in
#         ENVIRON)`) still match via the EOL / `)` / space boundary.
#     E6  (_d, 2026-10-03, COMMENT-ONLY — no code change) documentation
#         refinements to the section-10 residual notes, proven comment-only
#         (diff against _c touches `#`-lines only): (1) the B3-gate accepted-FP
#         note now names the grep/regex SEARCH-PATTERN class explicitly — a
#         grep whose quoted pattern contains the /proc/<pid>/environ path, a
#         regex alternation ending `|env)`, a jq filter containing `(set)`, and
#         a `python -c` string naming a whole-env token — and flags that these
#         shapes recur in hook-maintenance / search work; (2) the category-B
#         accepted-FP wording is broadened from "an uppercase loop variable"
#         to any uppercase variable whose last `_`-segment is a credential
#         keyword, echoed/printed (e.g. $CACHE_KEY, $SORT_KEY, $SESSION_TOKEN);
#         (3) the `2>`-redirect sink exclusion is named next to the pipe
#         exclusion in both the header residuals and the section 10 design
#         comment. No regex, accumulator, prefilter, or stage-0 rule changed.
#
#   DOCUMENTED RESIDUALS (merged from both projects; all ALLOW today)
#     Section 10 env-disclosure guard (2026-10-02; ALLOW today unless noted):
#     - A value copied into another variable first, a name computed at run
#       time, or a lowercase environment name (category B is uppercase-only).
#     - A dump written to a file BY an interpreter, and process-listing env
#       display (`ps eww`) are not modelled.
#     - `declare`/`typeset`/`compgen` listing forms other than `-p`, and bare
#       `export`, are not matched (names-only listings must stay allowed).
#     - A whole-env dump PIPED into a filter (`env | grep PATH`, `set | wc -l`)
#       is allowed: category A treats only a terminal or a file as a sink, not
#       a pipe, so filtered inspection is not interfered with (pinned FC28).
#       A `2>`-redirect is likewise not a sink: `env 2>f` is not matched (the
#       `2` sits before the `>`, outside category A's `([;&)]|>|$)` sink set),
#       so a dump whose stdout is not captured stays allowed — a miss, not an
#       FP, documented here for parity with the pipe exclusion.
#     - A 0a bail (oversized/kinked heredoc) loses the receiver link, so its
#       body is not accumulated.
#     - Secrets passed into a network request are a sanctioned use, out of
#       scope. Adversarial bypass shapes are out of scope by decision.
#     - ACCEPTED FALSE POSITIVES (BLOCK today): any uppercase variable (not
#       only a loop variable) whose last `_`-segment is a credential keyword,
#       echoed or printed — e.g. $CACHE_KEY, $SORT_KEY, $SESSION_TOKEN block
#       just as $DB_PASSWORD does; the suffix set was chosen knowingly by the
#       2026-10-01 NAME census, and each block message names a safe
#       alternative. Also: a single-quoted single-token span that 0c
#       canonicalizes.
#     - ACCEPTED FALSE POSITIVES (BLOCK today; task B3 FP gate, 2026-10-03):
#       an env-disclosure token sitting inside a quoted DATA argument that a
#       nested-quote shape kept out of stage-0 excision, so section 10 reads it
#       as an action. This is a SEARCH-PATTERN class that recurs specifically
#       in hook-maintenance / grep work, where the quoted argument is itself a
#       search pattern or interpreter string that merely NAMES an env token
#       rather than acting on one. The shapes seen in this repo's own dev work:
#         * a `grep` whose quoted pattern contains the `/proc/<pid>/environ`
#           path (category C matches the path literal anywhere);
#         * a regex alternation ending `...|env)` — e.g. a grep
#           `(txt|json|env)` — where category A reads the trailing `)` as a
#           subshell/segment terminator after `env`;
#         * a jq filter containing `(set)` such as `Bash(set)` (same
#           `)`-after-`set` read as category A);
#         * a `python -c "..."` string that also names a whole-env token
#           (category D's interpreter gate AND the token both land in the span).
#       Root cause is stage-0 quote excision not reaching these nested-quote
#       spans, not the section-10 regexes; narrowing A/C/D to defeat it safely
#       needs a stage-0 change, deferred as out of scope for this guard.
#       Measured rate of the category-A/C data-token FPs: 4 / 1060 gated
#       recorded-session commands.
#     - Variable-indirected command text evaluated later: `A='sudo id' eval
#       "$A"`, `A='docker run alpine' eval "$A"`, `A='pip install x' eval
#       "$A"` (DAAF r3 A01/A05/A15). A KEEP'd `VAR=` value is command-anchored
#       only for guards whose opener set includes a quote (§1 SEG_OPEN_Q, §5
#       SEG_OPEN_MNT); §3, §5 docker run, §7 and §8 use quote-free anchors.
#       A13 (`A='sudo id' echo hi`) is inert. A value set in a PRIOR tool call
#       is undetectable by single-command matching in any case.
#     - Runtime-computed stdin into a shell: `git log --grep='x' | sh`,
#       `jq -r '.cmd' f.json | bash` (DAAF r2 D04/D15). A LITERAL quoted
#       payload piped into a shell is promoted and blocks.
#     - Pipe receivers not modelled: `| ${SHELL}` (P11, computed name),
#       `| ssh host` / `| ssh host bash` in 0c (P16/P17; `tar c . | ssh host
#       'tar x'` is common and benign — the HEREDOC list does include ssh),
#       `| at now` (P21), `| awk -f -` (P20), `| sh.exe`, `| bash5` (S16/S17;
#       name-suffix variants), `| bash-completion` (F23 is benign).
#     - `echo 'x' |  & bash` (P35, a space inside `|&`) is INERT: bash rejects
#       it as a syntax error (`syntax error near unexpected token '&'`)
#       before anything runs, so there is nothing to block.
#     - Class C generally: a command NAME or target computed by substitution
#       (`$(echo rm) -rf /`, `X=rm; $X -rf /`), a dangerous target in a
#       variable with no signal in its name (`D=/; rm -rf "$D"`, `rm -rf
#       ${PWD:-/}`), a target on stdin (`echo / | xargs rm -rf`), encoded
#       payloads (`base64 -d | bash`).
#     - Other variable-rooted targets with no quote support or no arm (found
#       while fixing HF1(b); ALLOW on the live hook too): `find "$PWD"
#       -delete` / `find ${PWD} -delete` (G43 has no working-directory arm)
#       and a quoted `rm -rf "${D}/usr"` (_RM_VARTOP admits no quote).
#     - Wrapper spellings HF1(a) leaves open: a positional operand of a wrapper
#       other than flock/taskset that looks like a command name; an argument-
#       taking flag outside _WRAP_ARGFLAG whose argument is a plain word; and
#       F12's own wrapper list (_WRAPRUN), which is separate: `env -u HOME echo
#       mount /dev/sda /mnt | bash` ALLOWS (as on the live hook).
#     - ADVERSARIAL COVERAGE GAP (user decision 2026-09-26, both projects):
#       R5-T1 (`_exec_recurs`, the execution-position recurrence test) and F12
#       (`_EF1`, the unquoted echo/printf-into-a-shell rewrite) have NO
#       adversarial red-team cases in either project. In both projects an
#       automated safety classifier stopped the red-team agent while it was
#       authoring bypass strings for them. The rows that exist are functional
#       pins, not an adversarial sweep. The user accepted this as a documented
#       residual for now; adversarial cases for these two mechanisms should come
#       from a human author.
#     - Interpreter bodies are canonicalized and scanned for literal patterns
#       but not decomposed: `python3 -c "shutil.rmtree('/')"`,
#       `open('.claude/hooks/x','w')`. A LITERAL dangerous command in such a
#       body blocks. Accepted false positives from the same mechanism:
#       `python3 -c "print('mount the volume, then docker run')"` (R4N41) and
#       `echo "$IFS" | od -c` (R4N54, 0e).
#     - Write-then-execute through a different spelling of the same file
#       (absolute vs relative path, `$PWD/f`, symlink, variable) or an
#       interpreter missing from _XR_INTERP; a mutation hidden inside `find
#       … -exec sh -c '…'` reaching a protected path through `{}`.
#     - cwd-relative evasion across calls (`cd .claude`, then `cp x hooks/y`)
#       and `env -C <dir>` / `/usr/bin/env` before a relative write.
#     - Program-argument /tmp writes (`python x.py /tmp/out/`), `find … -exec
#       <writer> … /tmp/ …`, `TMPDIR=/tmp python3 x.py`, `sponge`, `split`,
#       `tar -czf /tmp/…`.
#     - Keyword-opened package installs (`if …; then pip install x; fi`): §8
#       anchors on `^`/`;`/`&`/`|` only.
#     - The 0c 256-character left-context window (see TRUNCATION in 0c);
#       spans beyond 64 / heredocs beyond 20 are KEPT (fail-closed); commands
#       over 20,000 characters skip 0c/0d and are scanned raw (the prose
#       false-positive class returns there — the deliberate trade that keeps
#       the hook inside the 5 s PreToolUse timeout).
#     - Out-of-scope families: scp/rsync exfiltration, `kill -9 -1`,
#       `git reflog expire` + `git gc --prune=now`, `docker container run`.
#     - Non-string `tool_name` (2026-09-27; DAAF Phase 4 component review N4,
#       the same class as enforce-single-command.sh Known Residual R7): ONE
#       well-formed JSON object whose `tool_name` is not the STRING "Bash" is
#       allowed unscanned, whatever its `tool_input.command` holds. The
#       one-object stdin gate checks only that stdin is exactly one object; it
#       does not check the TYPE of `tool_name`. An array (`["Bash"]`), an
#       object, `null`, a number, or a missing key makes `jq -r '.tool_name //
#       empty'` print something other than exactly `Bash` (or nothing), and the
#       `!= "Bash"` gate reads that as "not a Bash call". Probe
#       (scripts/scratch/hf3_toolname_probe.sh in DAAF's research workspace,
#       command `rm -rf /`): the string form exits 2; array, object, null,
#       number and missing exit 0, on the DAAF and starter-kit variants alike.
#       Accepted because Claude Code always sends `tool_name` as a string, so
#       a payload with any other type is not a real Bash call reaching this
#       hook (inference from the hook input contract, not a harness test).
#       Closing it would be one more clause in the stdin gate's jq test
#       (`(.[0].tool_name | type) == "string"`); deliberately not done in the
#       revision that added this entry, which is comment-only. Pinned ALLOW
#       today (FC240).
#     - Accepted false positives: `install -d .claude` (G10); a contrived
#       `xargs -0 grep -e rm …` over a protected path (G11); a quoted grep
#       pattern piped via `2>&1` into `python3 script.py` (P3; the rule-5a
#       interpreter-with-script over-block, fail-closed); `x --opt='y z' rm
#       -rf /` (DAAF r3 A19/A21, the F9 backstop — artificial shapes);
#       HF1(a)'s SHARED flag-letter class: _WRAP_ARGFLAG is one letter set for
#       every wrapper, so when a wrapper's own flag with an allowlisted letter
#       takes NO argument, the real command is swallowed as that flag's
#       "argument" and the command's first argument is read as the verb —
#       `strace -D grep mount f` (FC239), `unshare -U …`, `ltrace -S …`,
#       `nsenter -a …` (the letters are argument-taking for sudo/env/xargs);
#       and, because the `grep -i` guards also read `-c` as the allowlisted
#       `-C`, `strace -c grep mount f`, `exec -c grep mount f` (FC211/FC212).
#       Needs a no-argument flag, then a command whose FIRST argument is a
#       guarded verb (fail-closed; per-wrapper letter sets would close it).
#
#   VERIFICATION: see the harmonization record in DAAF's research workspace
#   (research/2026-09-18_FrameworkDev_SafetyHookHardening/SESSION_NOTES.md)
#   and the starter kit's REDTEAM_R5_REPORT.md for the pre-merge baseline.
# ===========================================================================

# ===========================================================================
# ===== SITE CONFIG — the only section that differs between projects =====
# ===========================================================================
# Site: DAAF (Data Analyst Augmentation Framework)
SITE_ROOT='/daaf'
SITE_EXTRA_PROTECTED_DIRS=('benchmarks/harness/hooks')
SITE_SCRATCH_DIR='{PROJECT_DIR}/scripts/scratch/'
# SC2016: backticks in the hint (if any) are literal message text, not expansions.
# shellcheck disable=SC2016
SITE_REBUILD_HINT='(exit the container, then run `bash rebuild_daaf.sh` from the daaf-docker folder) — preferably in the user additions block near the end of the Dockerfile for a fast rebuild'
SITE_ENABLE_REMOTION_GUARD=0
SITE_REMOTION_DIR=''
# ===== END SITE CONFIG =====================================================

# --- Values DERIVED from the site config (shared body; never edit per site) ---
_ROOT_RE="${SITE_ROOT//./'\.'}"
_ROOT_TOP="${SITE_ROOT#/}"
_ROOT_TOP="${_ROOT_TOP%%/*}"
_PROT_LABEL='.claude/hooks, .claude/logs, '
for _pe in "${SITE_EXTRA_PROTECTED_DIRS[@]}"; do
    _PROT_LABEL+="${_pe}, "
done
_PROT_LABEL+='or .claude/settings*.json'

# Fail CLOSED: if anything unexpected goes wrong, block the command.
# This is a security hook — ambiguous failures must not silently allow execution.
trap 'echo "BLOCKED by bash-safety hook: unexpected error in safety check" >&2; exit 2' ERR

# --- Dependency check (fail-closed) ---
# Without jq, we cannot inspect the tool invocation JSON. Failing open here
# would silently bypass ALL safety checks, so we must block.
if ! command -v jq &>/dev/null; then
    echo "BLOCKED by bash-safety hook: jq is not installed (required for hook)" >&2
    exit 2
fi

INPUT=$(cat)

# --- Fail-closed on malformed input (2026-09-26, harmonization fix 1) ---
# Claude Code always sends exactly one JSON object. Anything else (non-JSON
# text, a scalar/array, whitespace only, empty stdin, concatenated values) is
# abnormal and must not reach the `!= "Bash"` allow gate below, where a failed
# parse — or a multi-line TOOL_NAME from two concatenated objects — would read
# as "not a Bash call" and ALLOW. `-s` slurps every value on stdin so the count
# can be checked; jq exits non-zero on a parse error or a false result. Wording
# and form mirror DAAF's 2026-09-24 hook-maintenance enforce-file-first.sh
# patch; see "Fail-closed input posture" in the header.
# The gate does NOT check the type of `tool_name`: a non-string value passes
# here and then ALLOWS at the `!= "Bash"` gate (documented residual
# "Non-string `tool_name`" in the header; pinned FC240).
if ! printf '%s' "$INPUT" | jq -e -s 'length == 1 and (.[0] | type == "object")' >/dev/null 2>&1; then
    echo "BLOCKED by bash-safety hook: stdin is not a single JSON object (malformed hook input)" >&2
    exit 2
fi

# Only inspect Bash tool calls
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null) || TOOL_NAME=""
if [[ "$TOOL_NAME" != "Bash" ]]; then
    exit 0
fi

# Extract the command string
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null) || CMD=""
if [[ -z "$CMD" ]]; then
    exit 0
fi

# ---------------------------------------------------------------------------
# block: Print a descriptive error to stderr and exit 2 to block execution
# ---------------------------------------------------------------------------
block() {
    echo "BLOCKED by bash-safety hook: $1" >&2
    exit 2
}

# ---------------------------------------------------------------------------
# Shared vocabulary — wrapper commands and segment openers
# ---------------------------------------------------------------------------
#   WHY shared: before 2026-09-18 only §5 knew about wrapper prefixes, so
#   `env cp evil.sh .claude/hooks/x.sh` (probe BY26) and `time conda install x`
#   walked past the §7/§8 segment anchors. Hoisting the alternation into one
#   variable makes every command-position guard agree on what "a command starts
#   here" means. SOURCE: RoaringFerrum/claude-code-bash-guardian —
#   "Enhanced Wrapper Command Detection: Intelligently detects and scans
#   wrapper commands (timeout, xargs, sudo, etc.)"
#   (output/preliminary_notes/2026-09-18_research_community-guard-hooks.md §3).
#
#   2026-09-18 (fix cycle 1, red-team SB2): each wrapper may now carry its own
#   flags and numeric/duration arguments. The previous alternation had a flag
#   allowance ONLY for `timeout N`, so `nice -n 5 rm -rf ~`, `env -i cp x
#   .claude/hooks/y`, `xargs -0 rm -rf /` and `timeout -k 2 5 mount x y` all
#   walked past every wrapper-aware anchor (the live hook blocked the first
#   three via its word-anywhere patterns — a genuine regression). The argument
#   run is deliberately narrow — a `-flag` token or a bare `[0-9.smhd]+`
#   duration/number — so it cannot swallow an arbitrary command name. (`rm`,
#   `mv`, `mount`, `cp` all contain characters outside `[0-9.smhd]`.)
#
#   2026-09-26 (harmonization fix 1, consistency-review BLOCKER B1): a wrapper
#   flag that takes a SEPARATE argument ended the run at its argument, so
#   `timeout -s KILL 5 docker run x`, `env -u HOME docker run x` and
#   `exec -a x docker run x` walked past every WRAPPED anchor (the live
#   pre-2026-09-18 hook blocked the docker forms — a regression in both
#   projects), and `env -u HOME mount|pip install|cp … .claude/hooks/`,
#   `xargs -I {} cp {} .claude/hooks/`, `flock <lockfile> docker run x` were
#   never caught (probe corpus scripts/scratch/hf1_item1_cases.txt). Each
#   wrapper token (_WRAP_ITEM) may now also be:
#     (a) a NAMED argument-taking flag plus ONE non-flag token: the short
#         letters in _WRAP_ARGFLAG (`timeout -s KILL`, `env -u HOME`,
#         `env -C dir`, `env -S str`, `exec -a name`, `xargs -a file`,
#         `xargs -d x`, `xargs -E eof`, `strace -o f`, `strace -e x`,
#         `time -o f`, `stdbuf -o L`, `sudo -u/-g/-D/-U x`) and the long
#         spellings that take a separate argument (`--signal KILL`,
#         `--unset HOME`, `--chdir dir`, …);
#     (b) any token that cannot be a command name — it starts with a digit or
#         one of `{ % @ = , +` (`taskset -c 0-3`, `taskset 0x1`,
#         `xargs -I {}`, `time -f %e`, `timeout -k 1s`);
#     (c) and `flock`/`taskset` consume their MANDATORY positional argument
#         (the lock file, the CPU mask) after their options (`flock lk cmd`,
#         `flock -n lk cmd`, `taskset ff cmd`) — exact, since both commands
#         always read that operand before the command they run.
#   WHY NOT PIPE_RECV_PRE's generic `-flag [ARG]` item: there the run must end
#   at an interpreter NAME, so an over-long parse can only fail. Here it ends
#   at ANY guarded verb, and a generic argument slot swallows the real command
#   after a flag that takes no argument, making that command's first argument
#   the "verb": `xargs -0 grep -l mount`, `env -i grep mount /etc/fstab`,
#   `time -p grep …`, `stdbuf -oL grep …`, `strace -f grep …` all
#   false-blocked in a prototype (six new FPs in hf1_item1_cases.txt, rows
#   AN07-AN10/AN16/AN22). So the flag letters are an allowlist that excludes
#   every common no-argument wrapper flag (`-i -0 -p -r -t -v -x -f -l`) and
#   the letters whose argument is always numeric (covered by (b)). Over-
#   swallowing can never cause a MISS — a POSIX ERE matches if ANY parse
#   matches, and every item is optional — so the only cost of a wider item is
#   a false positive. ACCEPTED FP (documented; 2026-09-27 reworded after the
#   Phase 4 component review, W2): _WRAP_ARGFLAG is ONE letter set shared by
#   every wrapper, not a per-wrapper table. A letter that takes an argument for
#   one wrapper (`sudo -D dir`, `sudo -U user`, `env -S str`, `xargs -a file`)
#   is read the same way after a wrapper whose flag with that letter takes
#   none, so the command is swallowed as the flag's "argument" and its first
#   argument becomes the "verb": `strace -D grep mount f` (FC239),
#   `unshare -U grep mount f`, `ltrace -S grep mount f`, `nsenter -a grep
#   mount f` all block. The §1/§5/§8/doas guards also use `grep -i`, which
#   reads `-c` as `-C`, so `strace -c grep mount f`, `exec -c grep mount f`,
#   `setsid -c grep mount f` block too (FC211/FC212). Every member needs a
#   no-argument flag in the allowlisted set, then a command whose FIRST
#   argument is a guarded verb — rare in agent use and fail-closed. A
#   per-wrapper flag table would close the class at the cost of a much larger
#   regex; not done.
#   Timing: +~10 ms per call, no super-linear growth
#   (scripts/scratch/hf1_perf_stress.sh, 15-17 kB ambiguous wrapper runs).
_WRAP_ARGFLAG='-[adegosuCDESU]|--(signal|kill-after|unset|chdir|split-string|user|group|arg-file|delimiter|max-args|max-procs|adjustment|output|input|error|format|wait|timeout|conflict-exit-code|command|class|classdata)'
_WRAP_ITEM="(-[^ ;|&]+|[0-9.smhd]+|[0-9{%@=,+][^ ;|&]*|(${_WRAP_ARGFLAG}) +[^- ;|&][^ ;|&]*)"
WRAPPERS="((sudo|doas|env|command|exec|xargs|nohup|setsid|eval|time|nice|ionice|chrt|taskset|stdbuf|unshare|nsenter|strace|ltrace|flock|chronic|busybox|timeout)( +${_WRAP_ITEM})*|(flock|taskset)( +${_WRAP_ITEM})* +[^- ;|&][^ ;|&]*)"

_BT=$'\x60'   # a literal backtick, isolated so the char classes below stay legible
_SQ=$'\x27'   # a literal single quote
_DQ='"'

#   VARPRE: leading `VAR=value ` assignments. A command segment may legally
#   begin with any number of them (`TMPDIR=/tmp mktemp`, `FOO=1 rm -rf /`), and
#   before 2026-09-18 fix cycle 1 every segment-start anchor treated the first
#   assignment as the verb and stopped matching (red-team F9). Unquoted values
#   may not contain a separator, so this can never cross a segment boundary.
#
#   2026-09-18 (fix cycle 2, red-team R2-F2/V03/V09): the value alternation now
#   also spans a QUOTED value. `MSG='hello world' rm -rf /` and `A="x y" rm -rf /`
#   both walked past every segment-start anchor before, because the unquoted
#   `[^ ;|&]*` run stopped at the space INSIDE the quotes, leaving `world` /
#   `y"` as the apparent verb. The quoted alternatives are listed first and are
#   bounded by their own closing quote, so they still cannot cross a segment
#   boundary (an unterminated quote falls back to the unquoted run).
#   This widening is only operative because 0c KEEPS a quoted span whose left
#   context is a `VAR=` assignment — see the 0c VAR= trace comment below.
VARPRE="([A-Za-z_][A-Za-z0-9_]*=(${_SQ}[^${_SQ}]*${_SQ}|${_DQ}[^${_DQ}]*${_DQ}|[^ ;|&]*) +)*"

#   SEG_OPEN: the character/token set that can begin a command. `-exec`/
#   `-execdir` are included because `find … -exec <verb>` runs <verb> as a
#   command (GuardFall Class E; probe BY47).
SEG_OPEN="(^|[;&|(){]|${_BT}|\\\$\\(|[[:space:]]-exec(dir)?[[:space:]]|[[:space:]](then|do|else|elif|if|while|until|!)[[:space:]]|^![[:space:]])"

#   SEG_OPEN_Q: SEG_OPEN plus the quote characters and `$`. Used by §1's main
#   rm guard and its G29 `.git` guard. §5's two mount guards use SEG_OPEN_MNT
#   (below): the same quote openers without the bare `$`. Every other anchor
#   uses a quote-free set (SEG_OPEN, SEG7, or its own).
#   WHY the asymmetry: a quote that SURVIVES 0c into SCAN_CMD is text that
#   stage 0 deliberately left intact, and a quote opener lets a guard still
#   see its first word in command position. Five sources survive:
#     - an unterminated quote (0c stops; the remainder is KEPT);
#     - an ANSI-C `$'…'` / locale `$"…"` body (0c rule 1; plain ANSI-C bodies
#       are canonicalized since R5-G36b);
#     - a `VAR=` assignment value (rule 1b — `A='rm -rf /' eval "$A"`);
#     - a double-quoted span containing a backtick, `$(` or `${` (rule 5b —
#       `"${CLAUDE_PROJECT_DIR}/.git"`, which _ROOTVAR/_HOMEVAR/_CWDVAR admit);
#     - a `git commit -m` message body that feeds a pipe into an interpreter
#       (rule 5a KEEP — `git commit -m 'rm -rf /' | bash`).
#   Bats "unterminated double quote" and "ANSI-C $'...' body left intact"
#   depend on this. `$` is included so an indirected command name
#   (`RM=rm; $RM -rf /`, probe BY29) keeps blocking.
SEG_OPEN_Q="(^|[;&|(){${_SQ}${_DQ}\$]|${_BT}|\\\$\\(|[[:space:]]-exec(dir)?[[:space:]]|[[:space:]](then|do|else|elif|if|while|until|!)[[:space:]]|^![[:space:]])"

#   WRAPPED: zero or more leading `VAR=value ` assignments (VARPRE, added
#   2026-09-18 fix cycle 1) followed by zero or more wrapper tokens, between a
#   segment opener and the verb. Folding VARPRE in here rather than repeating it
#   at each call site is what makes every segment-start anchor — §1, §5, §6l,
#   §7, §8 — agree on the same notion of "a command starts here".
WRAPPED="${VARPRE}(${WRAPPERS} ${VARPRE})*"

#   SEG_OPEN_MNT — 2026-09-26 (harmonization, DAAF cycle-3/4 port: DAAF fix
#   cycle 4 FIX-3). §5's mount/umount/chroot opener set: SEG_OPEN_Q's quote
#   characters, `$(`, backtick and keyword openers, but WITHOUT the bare `$`.
#   The quote opener is needed for a KEEP'd `VAR=` value (`A='mount /dev/sda
#   /mnt' eval "$A"`, DAAF r3 A03/A04 — the R3-F1 reason). The bare `$` was
#   not: after 0c CANONICALIZES `"$mount"` to `$mount`, it made `mount`
#   command-anchored in benign `ls $mount`, `df -h "$mount"`, `echo $chroot`,
#   `cd "$umount"`, `findmnt | grep "$mount"` (DAAF r4 M40-M43, M56 — false
#   blocks in the starter-kit round-5 file). `$(` and the backtick stay, so a
#   substitution-opened `$(mount …)` is still caught. §1 keeps SEG_OPEN_Q
#   (its bare `$` catches `RM=rm; $RM -rf /`, probe BY29).
SEG_OPEN_MNT="(^|[;&|(){${_SQ}${_DQ}]|${_BT}|\\\$\\(|[[:space:]]-exec(dir)?[[:space:]]|[[:space:]](then|do|else|elif|if|while|until|!)[[:space:]]|^![[:space:]])"

#   PIPE RECEIVER VOCABULARY — 2026-09-26 (harmonization, DAAF cycle-3/4 port:
#   DAAF fix cycle 3 R3-F2/R3-F3 and fix cycle 4 FIX-1/FIX-4). ONE definition
#   of "the program that receives a pipe", shared by every pipe-into-an-
#   interpreter test: 0a `_HD_PIPE_RE`, 0c `_PIPEFEED_RE` (rule 5a), the F12
#   unquoted-echo rewrite, and both §4 downloader guards. It supersedes the
#   per-site `(${WRAPPERS}[[:space:]]+)*` runs of round 4's F6/F7 and R3-F2.
#   PIPE_OP        `|` or `|&` (stdout+stderr pipe).
#   PIPE_RECV_PRE  any run of: a WRAPPERS token (with its own flags); a
#                  `-flag ARG` item (`env -u HOME`, `exec -a x`, `env -C dir`,
#                  `timeout -s KILL 5` — DAAF r4 P28-P32, H44, S06/S07); a bare
#                  number/duration; or a `VAR=value` assignment including a
#                  QUOTED value (`| FOO='a b' bash`, DAAF r4 P26/P27). The
#                  argument of a `-flag ARG` item is one non-flag token, so it
#                  never crosses into the receiver by force; the receiver is
#                  still required to be an interpreter NAME, so `| env LC_ALL=C
#                  sort`, `| nice -n 5 wc -l`, `| timeout 5 jq .` stay ALLOW.
#                  Degenerate `| env -u bash` blocks (backtracking leaves
#                  `bash` as the receiver) — fail-closed, documented.
#                  This generic item stays generic ON PURPOSE: WRAPPERS
#                  (2026-09-26 harmonization fix 1) uses an allowlisted
#                  flag set instead, because its run ends at any guarded
#                  verb, not only at an interpreter name (see WRAPPERS).
#   PIPE_SHELLS    shell receivers. Adds `mksh ash fish csh tcsh` and the
#                  dot-source `\.` (DAAF r4 P18/P19/P22/P37/P38, H43, S10).
#                  `env` is deliberately NOT a receiver NAME anywhere: it is
#                  consumed as a wrapper, so `| env bash` BLOCKS and
#                  `cat <<'EOF' | env LC_ALL=C sort` (prose body) ALLOWS.
#   PIPE_INTERPS   non-shell interpreters.
#   PIPE_RECV_END  right boundary after the receiver name: whitespace, `;`,
#                  `&`, `|`, `)`, backtick, or end (DAAF r4 P12 `| bash; echo`,
#                  P13 `(… | bash)`, P33 `| bash|cat`, S01, S02 `x=$(… | sh)`,
#                  S13, S15 `| python3)`).
PIPE_OP='\|&?[[:space:]]*'
PIPE_RECV_PRE="((${WRAPPERS}|-[^[:space:];&|]+([[:space:]]+[^-[:space:];&|][^[:space:];&|]*)?|[0-9.smhd]+|[A-Za-z_][A-Za-z0-9_]*=(${_SQ}[^${_SQ}]*${_SQ}|${_DQ}[^${_DQ}]*${_DQ}|[^ ;|&]*))[[:space:]]+)*"
PIPE_SHELLS='bash|sh|zsh|dash|ksh|mksh|ash|fish|csh|tcsh|source|\.'
PIPE_INTERPS='python[0-9.]*|perl|ruby|node|php|R|Rscript'
PIPE_RECV_END="([[:space:];&|)${_BT}]|\$)"

# ---------------------------------------------------------------------------
# 0a. HEREDOC-BODY CLASSIFICATION (added 2026-09-18)
# ---------------------------------------------------------------------------
#   WHY: NORM_CMD collapses a multi-line command into one line, so a heredoc
#   body is scanned as if every word in it were a command. Probes HD3-HD6 and
#   HD8 are the novice-facing failure: `cat <<'EOF' > notes.md` + a sentence
#   mentioning `sudo apt update` was BLOCKED by the live hook.
#
#   WHAT THIS CLOSES: the heredoc-prose false-positive class (HD3-HD6, HD8).
#   WHAT IT MUST NOT OPEN: a heredoc into an interpreter is CODE. HD10-HD12
#   must keep blocking. The receiver allowlist is the load-bearing gate — see
#   the header's HEREDOC RECEIVER ALLOWLIST note and the measured qwen-code
#   regression it cites.
#
#   A body is EXCISED to ` __HDOC__ ` only when ALL of:
#     (i)   the delimiter was quoted (`<<'EOF'`, `<<"EOF"`) OR the body
#           contains none of  `  $(  ${   (no substitution can execute);
#     (ii)  the receiver — the first command word on the heredoc line, after
#           leading VAR=val assignments and after wrappers — is in
#           HEREDOC_DATA_CONSUMERS (`git` only as `git commit`);
#     (iii) the heredoc line does not pipe into an interpreter/shell.
#   Otherwise the body is KEPT and each body line is prefixed with `; ` so its
#   first word is segment-anchored (HD12 `bash <<'EOF'` / `rm -rf /` blocks on
#   the §1 command-position anchor precisely because of this join).
#
#   FAIL-CLOSED BAILOUTS (strip nothing, scan the original command):
#     - an unterminated heredoc;
#     - more than one `<<` opener on a single line;
#     - a delimiter that does not parse as `[A-Za-z_][A-Za-z0-9_]*` (this is
#       also what keeps `$(( 1 << 2 ))` arithmetic out of the stage: the token
#       after `<<` there is a digit);
#     - more than 20 heredoc openers in one command;
#     - a line containing `<<` that is longer than 1000 chars (4000 before
#       round 5, R5-C4), or a command longer than 40000 chars (bounded-work
#       guarantee for the 5 s hook timeout).
#   `<<<` here-strings are skipped explicitly. `<<` inside a quoted span is not
#   an opener (the scan below is quote-aware), which is what makes
#   `echo "x <<EOF"` safe to leave alone.
#   NOT A DATA CONSUMER — `awk` (removed 2026-09-18 fix cycle 1, red-team SB4):
#   `awk -f - <<EOF` reads its PROGRAM from stdin, so the heredoc body is code,
#   not data (`BEGIN{system("rm -rf /")}`). awk's program can also arrive as a
#   quoted argument with the heredoc supplying data, but distinguishing the two
#   shapes correctly is exactly the kind of parse this stage degrades to
#   fail-closed on. Removing awk keeps `awk '{print $1}' <<EOF` / `data` / `EOF`
#   allowed anyway — the KEPT body (`; data`) matches no guard.
HEREDOC_DATA_CONSUMERS=" cat tee head tail wc grep egrep fgrep sort uniq cut tr jq diff cmp printf column fold fmt nl od xxd base64 md5sum sha1sum sha256sum "
_HD_WRAP_RE="^(${WRAPPERS})\$"
_HD_ASSIGN_RE='^[A-Za-z_][A-Za-z0-9_]*='
_HD_DELIM_RE="^(-?)[[:space:]]*(${_SQ}([A-Za-z_][A-Za-z0-9_]*)${_SQ}|${_DQ}([A-Za-z_][A-Za-z0-9_]*)${_DQ}|([A-Za-z_][A-Za-z0-9_]*))"
#   _HD_PIPE_RE — 2026-09-26 (harmonization, DAAF cycle-3/4 port): the heredoc
#   line's pipe receiver uses the shared PIPE_OP/PIPE_RECV_PRE/PIPE_RECV_END
#   vocabulary, so `| bash; echo done` (DAAF r4 H40), `| bash|cat` (H46),
#   `| mksh` (H43) and `| timeout -s KILL 5 bash` (H44) keep the body. Round
#   4's F6 receivers `ssh sudo su` are KEPT here (heredoc only; `| ssh host`
#   runs the body remotely, DAAF r4 H42). `env` is removed from the receiver
#   list: it is consumed as a wrapper, so `| env bash` still keeps the body
#   while `cat <<'EOF' | env LC_ALL=C sort` with prose is excised (ALLOW).
_HD_PIPE_RE="${PIPE_OP}${PIPE_RECV_PRE}([^[:space:]]*/)?(${PIPE_SHELLS}|${PIPE_INTERPS}|eval|xargs|ssh|sudo|su)${PIPE_RECV_END}"
_HDWF_RE='(>>?|tee([[:space:]]+-a)?)[[:space:]]*([^[:space:];&|<>]+)'

# _exec_recurs FILE TEXT (round 5, R5-T1) — succeeds when FILE appears in TEXT
# in an EXECUTION position. Used by the write-then-execute rules (0a F11a and
# 0c F11b): a heredoc body or quoted span written to a file is DATA unless the
# same command later RUNS that file. Round 4 counted ANY later mention of the
# filename, so the everyday idiom "write notes that name a dangerous command,
# then `git add` / `wc -l` / `cat` / `grep` / `diff` the notes file" was
# false-blocked (13 of 14 rows in redteam_r5_fp_notes.txt). Execution positions
# recognised, each after a command-position opener (start of line, `; & | ( {`,
# backtick, `$(`, a shell keyword, find's -exec) plus VAR= assignments and
# wrappers (WRAPPED):
#   (1) the script argument of a shell or interpreter word, optionally path-
#       qualified and flag-bearing (`bash s.sh`, `sudo sh -x s.sh`,
#       `python3 -u x.py`, `source s.sh`, `. s.sh`);
#   (2) a direct invocation of the file (`./s.sh`, `dir/s.sh`, `/abs/s.sh`);
#   (3) the target of a chmod whose mode grants execute (`chmod +x s.sh`,
#       `chmod 755 s.sh`) — which only ever precedes execution.
# Spelling variants normalised: surrounding quotes and a leading `./` on either
# side; any directory prefix on the later mention also matches (fail-closed).
# NOT MODELLED (documented residuals): a later mention through a different
# spelling of the same inode (absolute vs relative path, `$PWD/s.sh`, a symlink,
# a variable holding the name), and an interpreter reached by a name not in
# _XR_INTERP. A carrier body that merely operates on the file (`bash -c 'wc -l
# f'`) DOES count as execution (flag arguments are consumed loosely) — the
# fail-closed direction.
_XR_INTERP='(bash|sh|zsh|dash|ksh|mksh|busybox|source|\.|python[0-9.]*|pypy[0-9.]*|node|nodejs|deno|bun|perl|ruby|php|lua|Rscript|R|tclsh|expect|awk|gawk)'
_exec_recurs() {
    local _f="$1" _t="$2" _q _c _fq
    _f="${_f//[${_SQ}${_DQ}]/}"
    _f="${_f#./}"
    [[ -z "$_f" ]] && return 1
    [[ "$_t" == *"$_f"* ]] || return 1
    _q=$(printf '%s' "$_f" | sed -E 's/[][\.*^$?+(){}|]/\\&/g')
    _c="(^|[;&|({${_BT}]|\\\$\\(|[[:space:]](then|do|else|elif|if|while|until|!|-exec|-execdir|-ok)[[:space:]])[[:space:]]*${WRAPPED}"
    _fq="[${_SQ}${_DQ}]?([^[:space:];&|${_SQ}${_DQ}]*/)?${_q}[${_SQ}${_DQ}]?([[:space:];&|)]|\$)"
    printf '%s\n' "$_t" | grep -qE \
        -e "${_c}([^[:space:];&|]*/)?${_XR_INTERP}([[:space:]]+-[^[:space:];&|]+([[:space:]]+[^-[:space:];&|][^[:space:];&|]*)?)*[[:space:]]+${_fq}" \
        -e "${_c}${_fq}" \
        -e "(^|[[:space:];&|])chmod([[:space:]]+-[^[:space:];&|]+)*[[:space:]]+([^[:space:];&|]*[+=][^[:space:];&|]*x[^[:space:];&|]*|[0-7]*[1357][0-7]*)([[:space:]]+[^[:space:];&|]+)*[[:space:]]+${_fq}"
}

# §10 ENV-DISCLOSURE ACCUMULATOR (added with §10, 2026-10-02): stage 0a/0c
# EXCISE or `;`-join text that the shell would NOT execute, but that text can
# still expand a `$NAME` and so DISCLOSE a value. §10 cannot see such a span in
# SCAN_CMD once it is excised. This additive accumulator records the bodies of
# the two excised shapes that still expand (an unquoted-delimiter data-consumer
# heredoc body; a double-quoted data span containing `$`) so §10 can scan them
# for credential-named expansions (category B). It changes NO stage-0
# classification — it only keeps a copy. Empty on the common path.
_ENV10_ACC=""

CMD_SCAN="$CMD"
if [[ "$CMD" == *'<<'* && "$CMD" == *$'\n'* && ${#CMD} -le 40000 ]]; then
    _hd_bail=0
    _hd_out=""
    _hd_delim=""      # active terminator; empty = not inside a body
    _hd_keep=0        # 1 = this body is CODE (keep, `;`-join)
    _hd_dc=0          # 1 = receiver is a DATA consumer (for the §10 accumulator)
    _hd_quoted=0      # 1 = delimiter was quoted
    _hd_open=""       # the opener line (F11a)
    _hd_body=""       # accumulated body lines (newline separated)
    _hd_count=0
    _hd_lines=()
    mapfile -t _hd_lines <<< "$CMD"
    for _hd_line in "${_hd_lines[@]}"; do
        if [[ $_hd_bail -eq 1 ]]; then
            break
        fi
        if [[ -n "$_hd_delim" ]]; then
            # --- inside a body: look for the terminator ---
            _hd_t="${_hd_line#"${_hd_line%%[![:space:]]*}"}"   # lstrip
            _hd_t="${_hd_t%$'\r'}"                              # tolerate CRLF
            if [[ "$_hd_t" == "$_hd_delim" ]]; then
                if [[ $_hd_keep -eq 0 ]] && [[ "$_hd_open" =~ $_HDWF_RE ]]; then
                    # F11a, narrowed in round 5 (R5-T1): KEEP only when the
                    # written file is later EXECUTED, not merely mentioned.
                    if _exec_recurs "${BASH_REMATCH[3]}" "$CMD"; then
                        _hd_keep=1     # write-then-execute: the body is code
                    fi
                fi
                # SC2016: the single-quoted `$(`, `${` and backtick are LITERAL text being searched for, not expansions.
                # shellcheck disable=SC2016
                if [[ $_hd_keep -eq 0 ]] && [[ $_hd_quoted -eq 1 || ( "$_hd_body" != *'`'* && "$_hd_body" != *'$('* && "$_hd_body" != *'${'* ) ]]; then
                    _hd_out+=" __HDOC__"$'\n'
                else
                    # KEEP: `;`-join so every body line is segment-anchored.
                    while IFS= read -r _hd_b; do
                        [[ -z "$_hd_b" ]] && continue
                        _hd_out+="; ${_hd_b}"$'\n'
                    done <<< "$_hd_body"
                    _hd_out+="; ${_hd_t}"$'\n'
                fi
                # §10 (additive): an UNQUOTED-delimiter heredoc fed to a data
                # consumer still expands `$NAME` in its body, whether 0a excised
                # it (inert data) or kept it (a pipe-into-shell flipped _hd_keep,
                # which is why _hd_dc is a separate flag). Record the body so §10
                # can scan it for credential-named expansions (category B).
                if [[ $_hd_dc -eq 1 && $_hd_quoted -eq 0 ]]; then
                    _ENV10_ACC+="${_hd_body}"$'\n'
                fi
                _hd_delim=""
                _hd_body=""
            else
                _hd_body+="${_hd_line}"$'\n'
            fi
            continue
        fi
        # --- not inside a body: quote-aware scan for a `<<` opener ---
        if [[ "$_hd_line" != *'<<'* ]]; then
            _hd_out+="${_hd_line}"$'\n'
            continue
        fi
        # R5-C4 (round 5 part C): the per-line bail is 1000 chars (was 4000).
        # The quote-aware scan below walks the line one character at a time and
        # its cost grows faster than linearly with line length (measured on the
        # round-5 draft: 10 lines x 3,990 chars ~1.0-1.2 s; 40 lines x 990 chars
        # ~0.5 s). A real heredoc opener line is never this long, and bailing is
        # fail-closed: nothing is stripped and the raw command is scanned.
        if [[ ${#_hd_line} -gt 1000 ]]; then
            _hd_bail=1
            break
        fi
        _hd_n=${#_hd_line}
        _hd_i=0
        _hd_q=0        # 0 none, 1 single, 2 double
        _hd_pos=-1
        _hd_opens=0
        while [[ $_hd_i -lt $_hd_n ]]; do
            _hd_ch="${_hd_line:_hd_i:1}"
            if [[ $_hd_q -eq 1 ]]; then
                [[ "$_hd_ch" == "$_SQ" ]] && _hd_q=0
            elif [[ $_hd_q -eq 2 ]]; then
                # SC1003: '\' is a one-character literal backslash, not an attempt to escape a quote.
                # shellcheck disable=SC1003
                if [[ "$_hd_ch" == '\' ]]; then
                    _hd_i=$((_hd_i + 1))
                elif [[ "$_hd_ch" == "$_DQ" ]]; then
                    _hd_q=0
                fi
            else
                # SC1003: '\' is a one-character literal backslash, not an attempt to escape a quote.
                # shellcheck disable=SC1003
                case "$_hd_ch" in
                    "$_SQ") _hd_q=1 ;;
                    "$_DQ") _hd_q=2 ;;
                    '\')    _hd_i=$((_hd_i + 1)) ;;
                    '<')
                        if [[ "${_hd_line:_hd_i+1:1}" == '<' ]]; then
                            if [[ "${_hd_line:_hd_i+2:1}" == '<' ]]; then
                                _hd_i=$((_hd_i + 2))          # <<< here-string
                            else
                                _hd_opens=$((_hd_opens + 1))
                                _hd_pos=$_hd_i
                                _hd_i=$((_hd_i + 1))
                            fi
                        fi
                        ;;
                esac
            fi
            _hd_i=$((_hd_i + 1))
        done
        if [[ $_hd_opens -eq 0 ]]; then
            _hd_out+="${_hd_line}"$'\n'
            continue
        fi
        if [[ $_hd_opens -gt 1 ]]; then
            _hd_bail=1
            break
        fi
        _hd_count=$((_hd_count + 1))
        if [[ $_hd_count -gt 20 ]]; then
            _hd_bail=1
            break
        fi
        _hd_after="${_hd_line:_hd_pos+2}"
        if [[ ! "$_hd_after" =~ $_HD_DELIM_RE ]]; then
            _hd_bail=1
            break
        fi
        _hd_quoted=0
        if [[ -n "${BASH_REMATCH[3]}" ]]; then
            _hd_delim="${BASH_REMATCH[3]}"; _hd_quoted=1
        elif [[ -n "${BASH_REMATCH[4]}" ]]; then
            _hd_delim="${BASH_REMATCH[4]}"; _hd_quoted=1
        else
            _hd_delim="${BASH_REMATCH[5]}"
        fi
        # Receiver: first command word before the `<<`, skipping VAR=val and wrappers.
        _hd_pre="${_hd_line:0:_hd_pos}"
        _hd_recv=""
        # Word-split the pre-heredoc text with GLOBBING DISABLED (`set -f`):
        # unquoted `*` or `?` in that text (e.g. `cat *.md <<EOF`) would
        # otherwise be pathname-expanded against the cwd, making the receiver
        # depend on the filesystem (red-team F7).
        set -f
        # shellcheck disable=SC2206
        _hd_toks=( $_hd_pre )
        set +f
        _hd_j=0
        while [[ $_hd_j -lt ${#_hd_toks[@]} ]]; do
            _hd_tk="${_hd_toks[_hd_j]}"
            if [[ "$_hd_tk" =~ $_HD_ASSIGN_RE ]] || [[ "$_hd_tk" =~ $_HD_WRAP_RE ]] || [[ "$_hd_tk" == "timeout" ]]; then
                _hd_j=$((_hd_j + 1))
                continue
            fi
            _hd_recv="${_hd_tk##*/}"
            break
        done
        _hd_keep=1
        _hd_dc=0          # reset per heredoc; set only for a data-consumer receiver
        if [[ "$HEREDOC_DATA_CONSUMERS" == *" ${_hd_recv} "* ]]; then
            _hd_keep=0
            _hd_dc=1      # §10: body still expands $NAME even though it is data
        elif [[ "$_hd_recv" == "git" ]] && [[ "$_hd_pre" == *"git commit"* ]]; then
            _hd_keep=0
        fi
        # 2026-09-26 (harmonization, DAAF cycle-3/4 port: DAAF FIX-2, r4 H47):
        # also test a quote- and backslash-stripped COPY of the heredoc line, so
        # a receiver hidden by quoting (`| "bash"`, `| ba\sh`, `| env 'bash'`)
        # still keeps the body. Only this decision uses the copy; the emitted
        # line is the original.
        _hd_line_n="${_hd_line//[\'\"\\]/}"
        if [[ "$_hd_line" =~ $_HD_PIPE_RE ]] || [[ "$_hd_line_n" =~ $_HD_PIPE_RE ]]; then
            _hd_keep=1
        fi
        _hd_out+="${_hd_line}"$'\n'
        _hd_open="$_hd_line"
        _hd_body=""
    done
    # Unterminated heredoc, or any bailout → strip nothing (fail-closed).
    if [[ $_hd_bail -eq 0 && -z "$_hd_delim" ]]; then
        CMD_SCAN="$_hd_out"
    fi
fi

# Normalize, in three steps:
#   1. Join backslash line continuations (`cp f \` ⏎ `.claude/hooks/x`). Without
#      this, a continuation would leave a stray `\` token between a verb and its
#      target and defeat the verb/whitespace-adjacency regexes in sections 1-5.
#   2. Turn every REMAINING newline into `; `. WHY (changed 2026-09-18): a
#      newline IS a command separator in bash, but the previous normalization
#      collapsed it to a plain SPACE. That was harmless while the guards matched
#      their verbs anywhere in the string; now that §1/§5/§7/§8 anchor verbs to
#      a command-segment start, a space would hide the second line of a
#      multi-line command entirely (adversarial case A69:
#      `echo "x <<EOF"` ⏎ `rm -rf /`, which the pre-2026-09-18 hook blocked).
#      Heredoc bodies never reach this step with their newlines intact — 0a has
#      already either excised them or `;`-joined them.
#        ACCEPTED COST: a newline INSIDE a multi-line quoted string also becomes
#        `;`, so a quoted paragraph whose second line begins with `mount`/
#        `docker run` can now false-block. That is the fail-closed direction and
#        the shape is rare; a single-line message or `git commit -F <file>` is
#        the escape hatch.
#   3. Collapse runs of whitespace to single spaces (the trailing space that the
#      previous `echo`-based pipeline produced is preserved by `printf '%s '`).
_nc="${CMD_SCAN//\\$'\n'/}"
_nc="${_nc//$'\n'/; }"
NORM_CMD=$(printf '%s ' "$_nc" | tr -s '[:space:]' ' ')

# ---------------------------------------------------------------------------
# 0b. QUOTE-AWARE COMMIT-MESSAGE EXCISION (added 2026-07-17, unchanged)
# ---------------------------------------------------------------------------
#   WHY: A `git commit -m` message body is DATA, not code — but the raw-string
#   pattern checks in sections 1-8 cannot tell "run `rm -rf /`" (a message that
#   DESCRIBES a dangerous command) from an actual `rm -rf /`. That produced a
#   class of false BLOCKS: benign commit messages that merely MENTION rm -rf,
#   sudo, curl|bash, > /tmp/x, git push --force, etc. all tripped the guards.
#   This stage removes shell-provably-inert message bodies from the scanned text
#   (SCAN_CMD) BEFORE the pattern checks run, so a described danger no longer
#   blocks a real commit. (Prior art: GuardFall / Adversa AI's "classify quoted
#   spans as data" recommendation, which names the commit-message case exactly.)
#
#   RETAINED VERBATIM in the 2026-09-18 revision even though 0c below
#   generalizes it: every case in tests/bash/bash_safety.bats and
#   scripts/test_safety_hooks.sh that exercises the `-m"attached"` form, the
#   `--message=` form, the `-am` bundle, and the pipe-revert guard depends on
#   this stage's exact behavior. 0c is additive, not a replacement.
#
#   MONOTONICITY / FAIL-CLOSED: excision only ever *removes* text the shell
#   itself cannot execute — a single-quoted body is POSIX-inert, and a double-
#   quoted body free of command/parameter substitution cannot execute. Every
#   ambiguous parse degrades to NOT stripping.
#
#   ACCEPTED RESIDUALS (all fail-closed — they keep BLOCKING):
#     (1) Double-quoted bodies containing ${...}, $(...), or a backtick are left
#         intact and still scanned — a real substitution executes at commit time.
#         Escape hatch for a legitimately dangerous-LOOKING message: single-quote
#         it, or use `git commit -F <file>`.
#     (2) ANSI-C $'...' and locale $"..." bodies are left intact (the `$` before
#         the quote never reaches the gap), even though $'...' is inert.
#     (3) Concatenated partial quoting (`-m "a"'b'`) excises only the matched
#         quote-pair; any leftover piece stays in the scanned text.
SCAN_CMD="$NORM_CMD"

# Gate: only attempt excision when a `git commit` actually starts a command
# segment. NORM_CMD has single collapsed spaces, so ` ?` and single spaces suffice.
_GATE_RE='(^|[;&|]) ?git commit'
# One flag+span occurrence per iteration. ANCHOR keeps the leading separator.
# PREFIX is `git commit` + a SAFE intervening run containing no separators,
# quotes, `$`, or backtick — so excision never crosses a separator and always
# halts before an unparsed quoted/expandable argument (fail-closed). FLAG bundles
# ONLY git commit's boolean short flags (whitelist aeinopqsv) ending in m, or
# --message[=]; `-cm` and friends cannot match by construction. GAP is one
# optional space (attached forms -m"..."/--message="..." have none; a `$` right
# after the flag — $'...' / $"..." — therefore never reaches a quote and stays
# intact). SPAN is single-quoted OR escape-aware double-quoted (\\. so \" does
# not terminate the span; an unterminated quote fails the match, stripping nothing).
_EX_ANCHOR='(^|[;&|] ?)'
_EX_PREFIX="(git commit[^;&|'\"\$${_BT}]*)"
_EX_FLAG='(-[aeinopqsv]*m|--message=?)'
_EX_SPAN="('[^']*'|\"(\\\\.|[^\"\\\\])*\")"
EXCISE_RE="${_EX_ANCHOR}${_EX_PREFIX}${_EX_FLAG} ?${_EX_SPAN}"
# Revert trigger: an excised commit segment that feeds a pipe — the message could
# be re-interpreted as code downstream (e.g. `git commit -m '<danger>' | xargs bash -c`).
_REVERT_RE='__QMSG__[^;&]*\|'

if [[ "$SCAN_CMD" =~ $_GATE_RE ]]; then
    _iter=0
    while [[ $_iter -lt 8 ]]; do
        if [[ "$SCAN_CMD" =~ $EXCISE_RE ]]; then
            _full="${BASH_REMATCH[0]}"
            _anchor="${BASH_REMATCH[1]}"
            _prefix="${BASH_REMATCH[2]}"
            _flag="${BASH_REMATCH[3]}"
            _span="${BASH_REMATCH[4]}"
            # Double-quoted body that can expand/execute → leave intact and STOP
            # entirely (no later span in this command is stripped past an ambiguous
            # one) — fail-closed, and avoids re-match churn.
            if [[ "${_span:0:1}" == '"' ]]; then
                _body="${_span:1:${#_span}-2}"
                # SC2016: the single-quoted `$(`, `${` and backtick are LITERAL text being searched for, not expansions.
                # shellcheck disable=SC2016
                if [[ "$_body" == *'`'* || "$_body" == *'$('* || "$_body" == *'${'* ]]; then
                    break
                fi
            fi
            # Excise: replace the whole matched flag+span with the flag + an inert
            # UNQUOTED placeholder (so a later `-m` can still match across it). The
            # quoted "$_full" pattern makes the substitution treat the match literally.
            _rebuilt="${_anchor}${_prefix}${_flag} __QMSG__"
            _new="${SCAN_CMD/"$_full"/"$_rebuilt"}"
            # No progress (matched text not found literally) → stop, don't spin.
            if [[ "$_new" == "$SCAN_CMD" ]]; then
                break
            fi
            SCAN_CMD="$_new"
        else
            break
        fi
        _iter=$((_iter + 1))
    done
    # If the excised commit segment feeds a pipe, the "inert" message may be
    # re-executed downstream — revert to the raw command so the pattern checks
    # see everything (fail-closed).
    if [[ "$SCAN_CMD" =~ $_REVERT_RE ]]; then
        SCAN_CMD="$NORM_CMD"
    fi
fi

# ---------------------------------------------------------------------------
# 0c. GENERAL QUOTED-SPAN CLASSIFICATION (added 2026-09-18)
# ---------------------------------------------------------------------------
#   WHY: 0b solved the commit-message case only. Every other quoted string was
#   still scanned as code, producing the largest observed false-positive class —
#   probes FP9-FP12, FP16-FP19 (`echo "chmod 777 is never acceptable"`,
#   `grep -n 'mount point' /etc/fstab`, `grep -rn "rm -rf /" docs/`,
#   `git log --grep="git reset --hard"`) — while simultaneously LEAVING a
#   bypass open, because a quoted COMMAND NAME (`"rm" -rf /`, probe BY27) was
#   also scanned in its non-canonical spelling and missed.
#
#   SOURCE for the design: the dcg SpanKind table (single-quoted = Data,
#   Unknown → Executed) and Continue's five-stage evaluator, Step 1 —
#   "Quote pairs are absorbed: `r''m` becomes `rm`. Class A is closed."
#   (output/preliminary_notes/2026-09-18_research_guardfall-and-data-vs-code.md
#   §3, §4.) Classifying by POSITION rather than by quote style is what lets
#   one mechanism fix an FP class and close a bypass class at the same time.
#
#   The loop walks single-quoted `'[^']*'` and escape-aware double-quoted spans
#   left to right (bounded at 64 spans; anything past that is KEPT). For each
#   span the two tokens to its LEFT and the single character to its RIGHT
#   decide the classification, in this priority order:
#
#     1. preceded by `$`            → KEEP  ($'…' ANSI-C / $"…" locale; 0b
#                                    residual (2), preserved here so the bats
#                                    "ANSI-C body left intact" case still blocks)
#     1b. `VAR=` assignment value   → KEEP  (so the quote-spanning VARPRE can
#                                    consume it; see the RULE 1b trace below)
#     2. carrier body               → PROMOTE   (`bash -c 'mount x y'` → `; mount x y`)
#     2b. shell `-c` fallback       → PROMOTE   (defence in depth, R2-F3)
#     3. command position           → CANONICALIZE (`"rm" -rf /` → `rm -rf /`)
#     4. attached / word-internal   → CANONICALIZE (`r'm'`, `"$VAR"/path`,
#                                    `--grep=` is treated as a whole word, not attached)
#     5. whole-word argument:
#        5a. feeds a pipe into an interpreter → PROMOTE, unless it is a
#            `git commit -m` message body, in which case KEEP.
#        5b. double-quoted with ` / $( / ${        → KEEP (can execute)
#        5c. whitespace-bearing AND its RECEIVER IS A DATA CONSUMER
#                                                  → EXCISE to ` __QARG__ `
#        5d. everything else                       → CANONICALIZE
#
#   EXCISION IS OPT-IN (revised 2026-09-18, fix cycle 1, red-team SB1/SB3).
#   The first draft inverted 5c/5d: ANY whitespace-bearing whole-word span was
#   excised, so every carrier shape the (then narrower) _SHELLC_RE/_CARRIER_RE
#   failed to recognise had its body DELETED from the scan — `/bin/bash -c
#   'rm -rf /'`, `bash -x -c '…'`, `env bash -c '…'`, and every interpreter
#   pivot (`python3 -c "…os.system('rm -rf /')"`, `perl -e`, `node -e`,
#   `Rscript -e`) became a silent allow where the pre-2026-09-18 hook blocked.
#   That is a true regression, not an FP fix, and it is exactly what the
#   MONOTONICITY CONTRACT forbids.
#
#   Now: text is removed only when its receiver is PROVABLY a data consumer —
#   `_DATACONS_RE` (echo/printf/grep/rg/cat/jq/… — never awk), `_GITDATA_RE`
#   (`git log --grep=` / `-S` / `-G`), or a `git commit -m`/`--message` body.
#   In every other case the quotes are stripped and the CONTENT IS SCANNED.
#   Carrier PROMOTE (rule 2) and the per-span pipefeed rule (5a) keep
#   precedence over both, so a recognised carrier is still strengthened rather
#   than merely preserved.
#
#   Rule 5a replaces the "global revert" sketched in the design. A global
#   revert is coarser than it needs to be: it would restore EVERY span in the
#   command, re-breaking `git commit -m 'sudo prose' | bash`, which the live
#   hook allows and scripts/test_safety_hooks.sh asserts must keep allowing
#   (§3's opener set deliberately excludes a bare single quote). Deciding
#   per-span at classification time is strictly stronger for non-message spans
#   (PROMOTE > KEEP: `echo 'sudo id' | bash` now BLOCKS) while preserving the
#   documented commit-message behavior exactly (`git commit -m 'rm -rf /' | bash`
#   still BLOCKS, via KEEP + §1's quote-inclusive anchor).
#
#   TRUNCATION (corrected in round 5; round 4's fix F13 widened the window from
#   64 to 256 characters): only the last 256 characters of the left context are
#   inspected, so the per-span work is O(1). Truncation is NOT purely
#   fail-closed. Splitting a token can turn a non-carrier into a carrier
#   (PROMOTE) or a non-command-position into one (CANONICALIZE), both of which
#   keep the text; but it can also HIDE a carrier's shell word when that word
#   lies more than 256 characters left of the body (`bash` + a very long flag
#   run + `-c '…'`). The span then falls through to CANONICALIZE: the text is
#   still scanned, but its first word is no longer segment-anchored, so a
#   command-position guard (§5 mount, §7, §8) can miss it. The §1 backstop (F9)
#   still catches the catastrophic `rm` targets in that shape, and 256
#   characters covers any realistic flag run. Documented residual.
#
#   PROVEN BY: FP9-FP12, FP16-FP19 (ALLOW); BY24, BY27, BY48 (BLOCK); and the
#   carrier BLOCK cases QS1-QS12 in the two regression suites.
_QSPAN_RE="^([^${_SQ}${_DQ}]*)(${_SQ}[^${_SQ}]*${_SQ}|${_DQ}(\\\\.|[^${_DQ}\\\\])*${_DQ})(.*)\$"
_CARRIER_RE='(^|[[:space:]])(eval|xargs|source|\.|ssh|su|sudo|-exec|-execdir|-ok)[[:space:]]+$'
# ssh is special: its remote command is not the token right after `ssh` — a
# hostname (and often user@host / -p flags) sits in between, so
# `ssh host 'rm -rf /'` would miss the immediate-predecessor test above
# (adversarial case A14; the pre-2026-09-18 hook blocked it). Any quoted span
# anywhere to the right of an `ssh` token is therefore treated as a carrier
# body. Over-matching here (`grep ssh 'pattern'`) only PROMOTES, which keeps
# the text in the scan — the fail-closed direction.
_SSH_RE='(^|[[:space:]])ssh[[:space:]]'
# _SHELLC_RE (widened 2026-09-18 fix cycle 1, red-team SB1): a `-c`-bearing
# short-flag bundle whose receiver is a shell. Three additions, each a probe-
# observed miss in the first draft:
#   ([^[:space:]]*/)?        an absolute or relative PATH to the shell
#                            (`/bin/bash -c '…'`, `/usr/bin/sh -c '…'`)
#   ([[:space:]]+-[^…]+)*    intervening flags before the bundle
#                            (`bash -x -c '…'`, `bash --norc -c '…'`)
#   ([[:space:]]+--)?        an end-of-options marker after it
#                            (`bash -c -- '…'`)
# 2026-09-18 (fix cycle 2, red-team R2-F1/B03/B04): the intervening-flag group
# now admits an OPTIONAL ARGUMENT after each flag, so an option that takes a
# value no longer breaks the chain — `bash -o pipefail -c 'rm -rf /'` and
# `bash -O extglob -c 'mount x y'` previously failed the group at `pipefail` /
# `extglob` (neither starts with `-`) and the body was merely canonicalized
# rather than promoted. The argument run excludes a leading `-` so a following
# FLAG is never swallowed as the previous flag's argument (`bash -x -c '…'`
# still parses as two flags), and it cannot cross whitespace, so it cannot
# swallow the `-c` bundle itself.
# The shell list is deliberately identical to the path-stripping shell set in
# enforce-single-command.sh (`bash sh zsh dash ksh mksh busybox`, plus the
# carrier-only `su sudo ssh env`), so the two hooks agree on what "a shell" is.
_SHELLC_RE='(^|[[:space:]])([^[:space:]]*/)?(bash|sh|zsh|dash|ksh|mksh|busybox|su|sudo|ssh|env)([[:space:]]+-[^[:space:]]+([[:space:]]+[^-][^[:space:]]*)?)*[[:space:]]+-[a-zA-Z]*[cC][a-zA-Z]*([[:space:]]+--)?[[:space:]]+$'
_CMDPOS_RE="(^|[;&|({])[[:space:]]*${VARPRE}(${WRAPPERS}[[:space:]]+)*\$"
_MSGFLAG_RE='(^|[[:space:]])(-[aeinopqsv]*m|--message=?)[[:space:]]*$'
# _PIPEFEED_RE (widened 2026-09-18 fix cycle 2, red-team R2-F4): the interpreter
# on the receiving end of the pipe may be reached by an absolute or relative
# PATH — `echo 'sudo id' | /bin/bash` fed a shell but did not match the bare
# word list, so the span was canonicalized instead of promoted. The optional
# `([^[:space:]]*/)?` prefix mirrors the same allowance already made in
# _SHELLC_RE and _DATACONS_RE. It requires a `/`, so a distinct command whose
# name merely ENDS in an interpreter name (`mysh`) is still not matched.
# R3-F2 (applied 2026-09-24 during the port, red-team round 3 cases J01/J04):
# the pipe operator may be `|&` (stdout+stderr), and the receiving interpreter
# may sit behind a wrapper token — `echo 'rm -rf /' |& bash` and
# `echo 'rm -rf /' | env bash` both fed a shell but failed the old bare `\|`
# + bare-word shape, so the span was merely canonicalized instead of promoted
# to a command segment. `curl … | jq .` and `curl … | sha256sum` stay ALLOW:
# jq and sha256sum are not interpreters and are absent from the receiver list.
# 2026-09-26 (harmonization, DAAF cycle-3/4 port): the receiver now uses the
# shared PIPE_OP/PIPE_RECV_PRE/PIPE_SHELLS/PIPE_INTERPS/PIPE_RECV_END
# vocabulary (flag-ARG wrapper items, quoted VAR= values, `mksh ash fish csh
# tcsh \.`, terminators `; & | )` backtick). The LEFT run (DAAF fix cycle 3,
# r3f probes R05/R06/R09) also admits the `&`-bearing operators `2>&1`, `>&`,
# `&>` and an earlier `|&` as units, so `echo 'rm -rf /' 2>&1 | bash` and
# `… |& cat | bash` promote; a lone `&` (background, `&&`) and `;` are still
# segment boundaries. Accepted cost (same as DAAF's cycle-4 draft): a quoted
# grep pattern piped through `2>&1` into `python3 script.py` now promotes too
# (DAAF r4 F13) — the pre-existing rule-5a interpreter-with-script over-block
# (F12/F14 `echo 'pip install x' | python3 check.py`), fail-closed.
_PIPEFEED_RE="^([^;&]|[<>]&|&>|\\|&)*${PIPE_OP}${PIPE_RECV_PRE}([^[:space:]]*/)?(${PIPE_SHELLS}|${PIPE_INTERPS}|eval|xargs)${PIPE_RECV_END}"
_RCBOUND_RE='[[:space:];&|)]'
# _VARASSIGN_RE (added 2026-09-18 fix cycle 2, red-team R2-F2/V03/V09): the left
# context ends in a `VAR=` assignment, so this span is the assignment's VALUE.
# The anchor is a space or start-of-string before the name, which is what keeps
# `--grep='pat'` out (there `=` is preceded by `grep`, itself preceded by `-`,
# not by whitespace) — that span must stay on the _GITDATA_RE EXCISE path.
_VARASSIGN_RE='(^|[[:space:]])[A-Za-z_][A-Za-z0-9_]*=$'
# Shell-word / `-c`-flag pair for the 0c defence-in-depth fallback (R2-F3).
_CFLAGTAIL_RE='(^|[[:space:]])-[a-zA-Z]*c[a-zA-Z]*([[:space:]]+--)?[[:space:]]+$'
_SHELLWORD_RE='(^|[[:space:]])([^[:space:]]*/)?(bash|sh|zsh|dash|ksh|mksh|busybox)([[:space:]]|$)'

# --- EXCISE RECEIVER ALLOWLIST (added 2026-09-18 fix cycle 1, red-team SB1/SB3)
# EXCISE is now OPT-IN. A whole-word quoted span loses its content only when the
# receiving command is provably a DATA consumer. Two regexes decide that:
#   _DATACONS_RE  the preceding command word (after wrappers, after an optional
#                 path, and across intervening non-separator argument tokens) is
#                 one of the heredoc data consumers plus `echo` and `rg`.
#                 Intervening tokens are allowed because `printf '%s\n' 'prose'`
#                 puts a format string between the verb and the prose span.
#                 awk is absent by construction (see HEREDOC_DATA_CONSUMERS).
#   _GITDATA_RE   a `git log`/`git show`/`git grep` pattern flag — `--grep=`,
#                 `--grep `, `-S `, `-G ` — whose argument is a search pattern.
#                 (The attached `-S'pat'` form never reaches here: its left
#                 context ends in a non-space character, so rule 4 —
#                 attached/word-internal — CANONICALIZES it first. Fail-closed.)
# Truncation of the left context to 256 chars can only DROP the anchor and make
# THESE two regexes fail, which downgrades EXCISE to CANONICALIZE — the safe
# direction. (Truncation is not safe everywhere; see TRUNCATION above.)
# Kept literal (not derived from HEREDOC_DATA_CONSUMERS at runtime) so the hook
# spawns no extra subprocess on every invocation. The 26-word shared core must
# stay in sync (`_DC_WORDS` adds only `echo` and `rg`); `awk` must be absent
# from BOTH.
_DC_WORDS='echo|rg|cat|tee|head|tail|wc|grep|egrep|fgrep|sort|uniq|cut|tr|jq|diff|cmp|printf|column|fold|fmt|nl|od|xxd|base64|md5sum|sha1sum|sha256sum'
_DATACONS_RE="(^|[[:space:];&|(){])(${WRAPPERS}[[:space:]]+)*([^[:space:]]*/)?(${_DC_WORDS})([[:space:]]+[^[:space:];&|()]+)*[[:space:]]+\$"
_GITDATA_RE='git +(log|show|grep)([^;&|]*[[:space:]])?(--grep=|--grep[[:space:]]+|-S[[:space:]]+|-G[[:space:]]+)$'
# F10 (r4 prototype): the data consumer sits inside an unclosed $( / <( / backtick, so its
# output is CAPTURED by an enclosing command (eval, bash, source) — not provably data.
# SC2016: the single-quoted `$(`, `${` and backtick are LITERAL text being searched for, not expansions.
# shellcheck disable=SC2016
_CAPT_RE='(\$\(|<\(|`)[^)`]*$'
_REEXEC_RE='^[^;&|]*(>>?|\|[[:space:]]*tee([[:space:]]+-a)?)[[:space:]]*([^[:space:];&|<>]+)'
# F11b (r4; narrowed in round 5, R5-T1): the span's segment writes a file (> f, >> f,
# | tee f) and the rest of the command EXECUTES that file (bash f, ./f, python f,
# chmod +x f — see _exec_recurs): the data is about to run, so it is not excised.
# A later non-executing mention (git add f, wc -l f, cat f) no longer counts.
_reexec_tail() {
    local _t="$1" _wf _after
    if [[ "$_t" =~ $_REEXEC_RE ]]; then
        _wf="${BASH_REMATCH[3]}"
        [[ -z "$_wf" ]] && return 1
        _after="${_t#*"$_wf"}"
        _exec_recurs "$_wf" "$_after" && return 0
    fi
    return 1
}

# GLOBAL SIZE GUARD (added 2026-09-18 fix cycle 1, red-team SB5). Stages 0c and
# 0d are the only stage-0 work whose cost grows with command length after the
# 0a line/command bounds. Above 20 000 characters we skip BOTH and scan the raw
# normalized command instead. That is the FAIL-CLOSED direction — an unclassified
# command is scanned as code, exactly as the pre-2026-09-18 hook did — and it is
# what keeps a padded command from approaching the 5 s settings.json hook
# timeout (a timed-out PreToolUse hook ALLOWS the call, which is the worst
# possible failure mode for a safety guard).
_qs_skip=0
if [[ ${#SCAN_CMD} -gt 20000 ]]; then
    _qs_skip=1
fi

# F12 (r4 prototype): `echo rm -rf / | bash`, `eval $(echo ...)`, `bash <(echo ...)`.
# Insert `; ` after the echo/printf verb so its arguments become segment-anchored.
# _WRAPRUN must keep EXACTLY four capturing groups: _EF1's `\8` counts them (N5
# warning below).
_WRAPRUN='((sudo|env|command|exec|xargs|nohup|setsid|eval|time|nice|busybox|timeout)( +(-[^ ;|&]+|[0-9.smhd]+))* +)*'
# 2026-09-26 (harmonization, DAAF cycle-3/4 port): the RECEIVER half of _EF1
# (everything after the pipe) uses the shared PIPE_RECV_PRE / PIPE_SHELLS /
# PIPE_INTERPS / PIPE_RECV_END vocabulary, so `echo mount x y | env -u HOME
# bash`, `| mksh`, `| bash; echo` are rewritten like `| bash`. The change sits
# wholly inside capture group 8, so the `\1`/`\8` numbering is unchanged.
# MAINTENANCE WARNING (2026-09-27, Phase 4 component review N5): `\8` in _EF1's
# replacement is a positional group NUMBER, and it is 8 only because exactly
# seven groups open before the tail: 1 = the kept prefix, 2 = the left anchor,
# 3-6 = _WRAPRUN's FOUR groups (the repeated wrapper run, the wrapper name, one
# flag item, the item's alternation), 7 = `(echo|printf)`. Adding or removing a
# capturing group in _WRAPRUN (POSIX ERE has no non-capturing form) or anywhere
# before the tail shifts the tail to another number; sed then substitutes the
# wrong span without any error, and F12 silently stops rewriting. So: keep
# _WRAPRUN at four groups, or renumber `\8` in the same edit and re-run the
# _EF1 pins (R4A38, R4A39). _EF2 uses only `\1` and is unaffected.
_EF_SHELLS="(${PIPE_SHELLS}|${PIPE_INTERPS}|eval)"
_EF1="s/((^|[;&|(]|\\\$\\(|<\\() *${_WRAPRUN}(echo|printf) +)([^|;&\"']*\\|&? *${PIPE_RECV_PRE}([^ ]*\\/)?${_EF_SHELLS}${PIPE_RECV_END})/\\1; \\8/"
_EF2="s/((^|[;&|] *)${_WRAPRUN}(bash|sh|zsh|dash|ksh|eval|source|\\.)( +-[^ ;|&]+)*( *;)? *[\"']?(\\\$\\(|<\\(|\`) *(echo|printf) +)/\\1; /"
if [[ $_qs_skip -eq 0 ]]; then
    SCAN_CMD=$(printf '%s' "$SCAN_CMD" | sed -E -e "$_EF1" -e "$_EF2")
fi
_ANSI_PLAIN_RE="^[^[:space:]\\\\;&|<>()${_BT}\$${_SQ}${_DQ}]+\$"   # R5-G36b
_qs_done=""
_qs_rest="$SCAN_CMD"
_iter=0
while [[ $_qs_skip -eq 0 && $_iter -lt 64 ]]; do
    if [[ "$_qs_rest" != *"$_SQ"* && "$_qs_rest" != *"$_DQ"* ]]; then
        break
    fi
    if [[ ! "$_qs_rest" =~ $_QSPAN_RE ]]; then
        break            # unbalanced quote → KEEP the remainder (fail-closed)
    fi
    _qs_pre="${BASH_REMATCH[1]}"
    _qs_span="${BASH_REMATCH[2]}"
    _qs_tail="${BASH_REMATCH[4]}"
    _qs_left="${_qs_done}${_qs_pre}"
    # NOTE: `${var: -256}` returns the EMPTY string when |offset| exceeds the
    # length, which would silently blank the left context for every short
    # command — guard the slice explicitly.
    _qs_lt="$_qs_left"
    if [[ ${#_qs_left} -gt 256 ]]; then
        _qs_lt="${_qs_left:${#_qs_left}-256}"
    fi
    _qs_lc="${_qs_left: -1}"
    _qs_rc="${_qs_tail:0:1}"
    _qs_body="${_qs_span:1:${#_qs_span}-2}"
    # SC2016 + SC1003 (scope: this whole classification if/elif chain, the
    # narrowest scope shellcheck allows for an `elif` condition): the chain
    # compares against the literal strings `$(`/`${` (rule 5b) and a literal
    # backslash '\' (R5-G36b escaped-`$` test). Neither is an expansion or a
    # quote escape.
    # shellcheck disable=SC2016,SC1003
    if [[ "$_qs_lc" == '$' ]]; then
        _qs_repl="$_qs_span"
        # R5-G36b (round 5, r4 finding 36): an ANSI-C `$'…'` span whose body has no
        # backslash, whitespace or shell metacharacter means EXACTLY its body (ANSI-C
        # differs from plain quoting only in backslash escapes), so it is
        # canonicalized — `$` and quotes dropped — instead of KEPT: `r$'m' -rf /`,
        # `> $'/tmp/x'`, `rm -rf $'/home/<user>'` then reach §1/§6 as plain words.
        # Anything else (escapes, prose with spaces) is still KEPT verbatim, and an
        # escaped `\$` before the quote is left alone.
        if [[ "${_qs_span:0:1}" == "$_SQ" && -n "$_qs_body" && "${_qs_left: -2:1}" != '\' \
              && "$_qs_body" =~ $_ANSI_PLAIN_RE ]]; then
            _qs_left="${_qs_left%\$}"
            _qs_repl="$_qs_body"
        fi
    elif [[ "$_qs_lc" == '=' ]] && [[ "$_qs_lt" =~ $_VARASSIGN_RE ]]; then
        # RULE 1b — VAR= ASSIGNMENT VALUE → KEEP (added 2026-09-18 fix cycle 2,
        # red-team R2-F2/V03/V09). This is the branch that makes the widened
        # VARPRE operative: VARPRE can only consume a quoted value if the value
        # is STILL QUOTED when §1-§8 run. Traced on `MSG='hello world' rm -rf /`:
        #   PROMOTE      → `MSG=; hello world rm -rf /` — `rm` is preceded by
        #                  `world`, so no segment-start anchor matches → MISS.
        #   CANONICALIZE → `MSG=hello world rm -rf /` — same miss (verified with
        #                  scripts/scratch/r2f_make_dump.sh on the fix-cycle-1
        #                  draft: `SCAN_CMD=[MSG=hello world rm -rf / ]`).
        #   KEEP         → `MSG='hello world' rm -rf /` — VARPRE's quoted-value
        #                  alternation consumes the whole assignment and `rm`
        #                  lands on the §1 anchor → BLOCK.
        # KEEP is also no weaker than CANONICALIZE for a dangerous VALUE
        # (`A='rm -rf /' foo`), because §1's opener set SEG_OPEN_Q includes the
        # quote characters themselves, so the body is still scanned in command
        # position. Every other rule below would break one of the two, so this
        # branch sits second, above the carrier test (a `VAR=` left context can
        # never be a carrier body: the carrier tests all require a whole-word
        # span, i.e. `_qs_lc` empty or a space).
        _qs_repl="$_qs_span"
    elif [[ -z "$_qs_left" || "$_qs_lc" == ' ' ]] && { [[ "$_qs_lt" =~ $_CARRIER_RE ]] || [[ "$_qs_lt" =~ $_SHELLC_RE ]] || [[ "$_qs_lt" =~ $_SSH_RE ]]; }; then
        _qs_repl="; ${_qs_body}"
    elif [[ -z "$_qs_left" || "$_qs_lc" == ' ' ]] && [[ "$_qs_lt" =~ $_CFLAGTAIL_RE ]] && [[ "$_qs_lt" =~ $_SHELLWORD_RE ]]; then
        # RULE 2b — SHELL `-c` FALLBACK → PROMOTE (defence in depth, added
        # 2026-09-18 fix cycle 2, red-team R2-F3). If the immediately preceding
        # token is a `-…c…` flag bundle AND a shell word appears anywhere
        # earlier in the (256-char) left context, the span is almost certainly a
        # shell command body even though the precise _SHELLC_RE shape above did
        # not match. Promoting is the fail-closed direction: the body is kept
        # AND segment-anchored. Deliberately restricted to the SHELL half of the
        # carrier set — a non-shell `-c` body (`python3 -c 'print("hello
        # world")'`) is not shell code and must keep falling through to
        # CANONICALIZE, which preserves the pre-2026-09-18 literal-pattern scan
        # without inventing segment boundaries inside foreign-language source.
        # REACHABLE TODAY (probed with scripts/scratch/r2f_fallback_probe.sh):
        # `sh - -c 'mount x y'` — the POSIX bare `-` argument fails _SHELLC_RE's
        # `-[^[:space:]]+` flag run (it needs at least one character after the
        # dash) but is caught here (case FC46). The same probe confirms
        # `python3 -c` / `perl -c` do NOT reach this branch. Beyond that one
        # shape the branch is insurance: the NEXT unanticipated flag spelling
        # fails closed instead of open.
        _qs_repl="; ${_qs_body}"
    elif [[ "$_qs_lt" =~ $_CMDPOS_RE ]]; then
        _qs_repl="$_qs_body"
    elif { [[ -n "$_qs_lc" && "$_qs_lc" != ' ' && "$_qs_lc" != '=' ]]; } || { [[ -n "$_qs_rc" ]] && [[ ! "$_qs_rc" =~ $_RCBOUND_RE ]]; }; then
        _qs_repl="$_qs_body"
    elif [[ "$_qs_tail" =~ $_PIPEFEED_RE ]] || { _qs_tail_n="${_qs_tail//[\'\"\\]/}"; [[ "$_qs_tail_n" =~ $_PIPEFEED_RE ]]; }; then
        # 2026-09-26 (harmonization, DAAF cycle-3/4 port: DAAF FIX-2, r4
        # P05/P09/P10/P41): rule 5a runs on the RAW tail, before later spans are
        # canonicalized, so a receiver hidden by quotes or backslashes
        # (`| "bash"`, `| ba\sh`, `| env 'bash'`, `| env -S 'bash -x'`) escaped
        # the pipefeed test and the span fell through to the data-consumer
        # EXCISE. A quote- and backslash-stripped COPY of the tail is tested too.
        if [[ "$_qs_lt" =~ $_MSGFLAG_RE ]] && [[ "$_qs_left" == *"git commit"* ]]; then
            _qs_repl="$_qs_span"
        else
            _qs_repl="; ${_qs_body}"
        fi
    elif [[ "${_qs_span:0:1}" == "$_DQ" ]] && { [[ "$_qs_body" == *"$_BT"* || "$_qs_body" == *'$('* || "$_qs_body" == *'${'* ]]; }; then
        _qs_repl="$_qs_span"
    elif [[ ! "$_qs_lt" =~ $_CAPT_RE ]] && _reexec_tail "$_qs_tail"; then
        # R5-C5a (round 5, part C): the span is written to a file that the same
        # command then EXECUTES (_reexec_tail / _exec_recurs), so its body is
        # script, not data. PROMOTE it like a carrier body instead of
        # canonicalizing it in place, so every command in it is segment-anchored.
        _qs_repl="; ${_qs_body}"
    elif [[ ! "$_qs_lt" =~ $_CAPT_RE ]] && ! _reexec_tail "$_qs_tail" \
         && { { [[ "$_qs_body" == *" "* ]] && { [[ "$_qs_lt" =~ $_DATACONS_RE ]] \
         || { [[ "$_qs_lt" =~ $_MSGFLAG_RE ]] && [[ "$_qs_left" == *"git commit"* ]]; }; }; } \
         || [[ "$_qs_lt" =~ $_GITDATA_RE ]]; }; then
        # §10 (additive): a DOUBLE-quoted data span excised here still has its
        # `$NAME` expanded by the shell (a span with `${`/`$(`/backtick was
        # already KEPT by the rule-5b branch above, so a surviving `$` is a bare
        # $NAME). Record it so §10 can scan it for credential-named expansions
        # (category B). Single-quoted spans cannot expand, so they are skipped.
        if [[ "${_qs_span:0:1}" == "$_DQ" && "$_qs_body" == *'$'* ]]; then
            _ENV10_ACC+="${_qs_body}"$'\n'
        fi
        _qs_repl=" __QARG__ "
    else
        _qs_repl="$_qs_body"
    fi
    # R5-C5b (round 5, part C): a PROMOTED body is shell script about to run.
    # printf and `echo -e` turn a typed `\n` into a real newline, i.e. a command
    # boundary, but stage 0d would later fold `\nrm` into `nrm` and hide the
    # command. Translate each literal backslash-n in a promoted body into "; "
    # first. Fail-closed: it can only add segment boundaries.
    if [[ "${_qs_repl:0:2}" == "; " ]]; then
        _qs_repl="${_qs_repl//\\n/; }"
    fi
    _qs_done="${_qs_left}${_qs_repl}"
    _qs_rest="$_qs_tail"
    _iter=$((_iter + 1))
done
SCAN_CMD="${_qs_done}${_qs_rest}"

# Re-collapse runs of spaces that EXCISE/PROMOTE may have introduced, because
# several §6/§7 patterns below use a literal single space between tokens.
# Bash-internal (no subprocess); 8 halvings cover 256 consecutive spaces.
_iter=0
while [[ $_qs_skip -eq 0 && $_iter -lt 8 ]]; do
    _qs_new="${SCAN_CMD//  / }"
    if [[ "$_qs_new" == "$SCAN_CMD" ]]; then
        break
    fi
    SCAN_CMD="$_qs_new"
    _iter=$((_iter + 1))
done

# ---------------------------------------------------------------------------
# 0d. ESCAPE CANONICALIZATION (added 2026-09-18)
# ---------------------------------------------------------------------------
#   WHY: GuardFall Class A also covers backslash-splitting of a command name —
#   probes BY28 (`r\m -rf /`) and BY39 (`s\udo id`) both ran past the live hook.
#   In bash, a backslash before an ordinary character is simply removed, so
#   `r\m` IS `rm`. Deleting a backslash that precedes an alphanumeric character
#   reproduces exactly that rule and nothing else: `\;`, `\\`, `\"`, `\ `, `\$`
#   are all left alone, so `find … -exec … \;` and escaped quotes are untouched.
#   Runs after 0c so that escapes inside a KEPT quoted span are not rewritten
#   before the span has been classified.
#   ACCEPTED COST: a literal filename containing `\a` would be canonicalized in
#   the scan copy. It is only the scan copy; the command itself is untouched.
#
#   PERFORMANCE (rewritten 2026-09-18 fix cycle 1, red-team SB5). The first
#   draft looped up to 64 times over `_ESC_RE='(.*)\\([a-zA-Z0-9])(.*)'`. Each
#   iteration is an O(n) backtracking scan with a LEADING `.*`, and it removes
#   exactly ONE backslash — so the stage was O(64·n) with a large constant and
#   measured 3.0 s at 32 kB and >5 s (settings.json hook timeout → ALLOW) at
#   64 kB, versus 0.01 s for the live hook. `sed -E` does the whole
#   substitution in ONE non-backtracking pass over the buffer, and handles an
#   unbounded number of escapes rather than the first 64.
#   NOTE: `$( )` strips the trailing newline sed emits; `printf '%s'` adds none,
#   so SCAN_CMD round-trips byte-for-byte apart from the intended deletions.
if [[ $_qs_skip -eq 0 ]]; then
    SCAN_CMD=$(printf '%s' "$SCAN_CMD" | sed -E 's/\\([a-zA-Z0-9\/])/\1/g')
fi

# ---------------------------------------------------------------------------
# 0e. $IFS OBFUSCATION — HARD BLOCK (added 2026-09-18)
# ---------------------------------------------------------------------------
#   WHY: GuardFall Class B. `rm$IFS-rf$IFS/` executes `rm -rf /` while
#   containing no whitespace at all, so every whitespace-adjacency regex in
#   sections 1-8 misses it. `shlex.split` does not expand it either (probe in
#   the literature return: `'rm$IFS-x$IFS/tmp'` → a single token). There is no
#   legitimate reason for an agent to reference $IFS in a one-shot Bash tool
#   call, so the whole token is refused rather than reasoned about.
#   2026-09-18 fix cycle 1 (red-team F6): the `$` must not itself be escaped.
#   `echo \$IFS` prints the literal four characters `$IFS` — nothing is
#   word-split — so the `(^|[^\\])` prefix lets it pass while `rm$IFS-rf$IFS/`,
#   `${IFS}` and a leading `$IFS` still block. 0d runs first but only removes a
#   backslash before an ALPHANUMERIC, so `\$` survives to be tested here.
#   ACCEPTED EDGE (unchanged, deliberate): `echo "$IFS"` in prose still blocks —
#   0c CANONICALIZES the single-token span to a bare `$IFS`, which is
#   indistinguishable here from the obfuscation form. Single-quote it
#   (`echo '$IFS'`… also canonicalizes) or write the word out instead.
if echo "$SCAN_CMD" | grep -qE '(^|[^\\])\$\{?IFS'; then
    block "Reference to \$IFS in a command is word-splitting obfuscation (it hides argument boundaries from the safety scan). Write the command with ordinary spaces."
fi

# ---------------------------------------------------------------------------
# Pattern checks — order: most dangerous first
# ---------------------------------------------------------------------------

# 1. DESTRUCTIVE FILESYSTEM OPERATIONS
#    WHY THE REWRITE (2026-09-18): the previous pattern
#      rm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r)\s+(/|/\*|~|\$HOME|\.\.|\.|\*)
#    had an unanchored target alternation, so EVERY absolute path matched `/`,
#    every dotfile matched `\.`, and every glob matched `\*` — probes FP5-FP8
#    (`rm -rf ./build`, `rm -rf .pytest_cache`, `rm -rf *.tmp`,
#    `rm -rf <root>/some/project/…/tmpdir`) were all false-blocked. It also required
#    r and f in ONE bundle, so `rm -r -f /`, `rm --recursive --force /` and
#    `rm -rf -- /` (BY1-BY3) all walked past.
#
#    The rewrite: a segment-anchored verb (optionally /bin/ or /usr/bin/
#    qualified, optionally wrapper-prefixed, optionally after `find -exec`), a
#    flag run that must contain a recursive flag in ANY order or spelling, and
#    a TOKEN-EXACT dangerous target. `--force` is no longer required, matching
#    dcg's rule — "Recursive deletion outside temp, with or without --force"
#    (output/preliminary_notes/2026-09-18_research_community-guard-hooks.md §P4).
#      CLOSES: BY1, BY2, BY3, BY27 (via 0c), BY28 (via 0d), BY47 (find rule).
#      FIXES:  FP5, FP6, FP7, FP8.
#      RESIDUAL: a dangerous target reached through a variable whose value the
#      hook cannot see (`rm -rf "$D"`) — Class C, unchanged.
#    NOTE on SEG_OPEN_Q: §1's rm guards (this one and G29) accept a quote
#    character as an opener, as do §5's mount guards (SEG_OPEN_MNT). See the
#    SEG_OPEN_Q comment above — by the time §1 runs, a surviving quote is text
#    stage 0 deliberately left intact (five sources, listed there).
_RM_FLAG='(--[a-z-]+|--|-[a-zA-Z]+)'
_RM_REC='(-[a-zA-Z]*[rR][a-zA-Z]*|--recursive)'
#
#    2026-09-18 fix cycle 1 (red-team F8): the PROJECT ROOT joins the dangerous
#    target set. `rm -rf <root>/*` wipes the entire repo and every content
#    project — the single most destructive command available inside this
#    container — yet it matched none of the targets above (it is not `/`, not
#    `*`, not `~`). It was only ever deny-rule-backstopped, which is one layer,
#    not two. The target is TOKEN-EXACT, so the ordinary in-project deletes
#    `rm -rf ./build` and `rm -rf <root>/scratch/x/tmp` still pass: the
#    character after `<root>/` in those is a path component, not a boundary.
#    `${PROJECT_DIR}`/`${BASE_DIR}` are covered in bare and `/*` forms because
#    agent-written scripts and prompts address the root through those names.
#
#    2026-09-26 (harmonization, G29 quoted form): _ROOTVAR is the ONE spelling of
#    "the project root through a variable", shared by _RM_ROOT, G29 and G43. It
#    admits an optional double quote on each side because 0c rule 5b KEEPS a
#    double-quoted span containing `${` byte-for-byte, so `"${CLAUDE_PROJECT_DIR}"`
#    reaches §1 WITH its quotes (the unbraced `"$BASE_DIR"` is canonicalized and
#    never needed this). Before this, `rm -rf "${CLAUDE_PROJECT_DIR}/.git"`,
#    `rm -rf "${BASE_DIR}"`, `rm -rf "${PROJECT_DIR}/*"` and `find
#    "${CLAUDE_PROJECT_DIR}" -delete` all ALLOWED (Unit B FC169 + C2 probe
#    Q01-Q47). The root var form also gains a bare trailing `/` (`rm -rf
#    $CLAUDE_PROJECT_DIR/`), which the literal `<root>/?` form already had.
#    Still token-exact: `"${PROJECT_DIR}"/build`, `"${BASE_DIR}/research/x"` ALLOW.
_ROOTVAR='"?\$\{?(CLAUDE_PROJECT_DIR|PROJECT_DIR|BASE_DIR)\}?"?'
_RM_ROOT="${_ROOT_RE}"'/\*|'"${_ROOT_RE}"'/?|'"${_ROOTVAR}"'(/\*|/)?'
#
#    2026-09-24 PORT ADDITION — the four dangerous-`rm` shapes that Claude Code
#    2.1.281 began catching natively. They are encoded here so the hook does not
#    depend on the harness version (a downgrade, a different client, or an SDK
#    session must be guarded by the same rules):
#
#      (a) _RM_CWDVAR  — a shell variable that names the working directory:
#          `rm -rf $PWD`, `rm -rf "$PWD"/`, `rm -rf ${PWD}`, plus OLDPWD/CWD.
#          (`"$PWD"` reaches this pattern unquoted: stage 0c CANONICALIZES a
#          whitespace-free double-quoted argument.)
#      (b) _RM_CMDSUB  — the target IS command-substitution output:
#          `rm -r "$(pwd)"`, `rm -rf $(pwd)`, `rm -rf \`pwd\``. The substitution
#          may keep its surrounding quotes, because a body containing `$(` is
#          KEPT verbatim by 0c rule 5b. Only a BARE substitution token (with an
#          optional trailing `/` or `/*`) matches, so `rm -rf "$(pwd)"/build`
#          — a named subdirectory — stays ALLOW.
#      (c) _RM_VARTOP  — a variable immediately followed by a TOP-LEVEL system
#          directory name: `rm -rf $VAR/usr`, `rm -rf ${D}/etc`. If the variable
#          is empty the command deletes the real /usr. The suffix must be a
#          top-level name, which is what keeps `rm -r "$OUT_DIR"/frames` ALLOW.
#      (d) _RM_BSLASH  — a lone backslash as the target (`rm -rf \`). Bash
#          removes the backslash and the target becomes empty/next-token, which
#          is never an intended delete.
#
#    RESIDUAL (documented, not guessed at): a dangerous target reached through a
#    variable whose value the hook cannot see and whose NAME carries no signal
#    (`D=/; rm -rf "$D"`, `rm -rf "$TARGET"`) stays ALLOW. Blocking every
#    `rm -r "$VAR"` would break the ordinary, correct in-project idiom
#    (`rm -r "$OUT_DIR"/frames`), so the shape is left to the instruction layer
#    and the settings.json deny rules. GuardFall Class C, unchanged.
#
#    2026-09-26 (harmonization fix 1, quoted HOME/PWD forms — user-approved):
#    _CWDVAR and _HOMEVAR are the _ROOTVAR idea applied to the working-directory
#    and home variables. 0c rule 5b KEEPS a double-quoted span containing `${`
#    byte-for-byte, so `rm -rf "${HOME}"`, `"${HOME}/"`, `"${HOME}/*"`,
#    `"${PWD}"`, `"${OLDPWD}"` and `find "${HOME}" -delete` reached §1 WITH
#    their quotes and ALLOWED (FC181-FC183, formerly pinned as a documented
#    residual). Each fragment admits an optional double quote on each side of
#    the variable; a closing quote after a `/` or `/*` suffix is taken by the
#    guards' trailing boundary class, which already includes both quotes. Still
#    token-exact: `rm -rf "${HOME}/scratch_dir"`, `rm -rf "${HOME}/.cache/pip"`
#    and `rm -rf "${PWD}"/build` — a named subdirectory — stay ALLOW.
_CWDVAR='"?\$\{?(PWD|OLDPWD|CWD)\}?"?'
_HOMEVAR='"?\$\{?HOME\}?"?'
_RM_CWDVAR="${_CWDVAR}"'(/\*|/)?'
# SC2016: the single-quoted `$(`, `${` and backtick are LITERAL text being searched for, not expansions.
# shellcheck disable=SC2016
_RM_CMDSUB='["'"'"']?(\$\([^)]*\)|`[^`]*`)["'"'"']?(/\*|/)?'
_RM_VARTOP='\$\{?[A-Za-z_][A-Za-z0-9_]*\}?/(usr|etc|bin|sbin|lib|lib64|var|opt|boot|dev|proc|sys|root|home|srv|run|'"${_ROOT_TOP}"')(/[^ ;|&]*)?'
# SC1003: '\\' is the two-character regex for ONE literal backslash, not a quote escape.
# shellcheck disable=SC1003
_RM_BSLASH='\\'
# F5 (r4 prototype): glob/dot forms of the classic targets, literal top-level system dirs
# (mirrors _RM_VARTOP), the home directory in all spellings, and the .claude config dir.
_RM_LITTOP='/(usr|etc|bin|sbin|lib|lib64|var|opt|boot|dev|proc|sys|root|srv|run|mnt|media)/?'
_RM_HOME='(~|'"${_HOMEVAR}"'|/home/[^/ ;|&]+)(/|/\*|/\.\*|/\.claude/?|/\.claude/\*)?'
_RM_DOTS='(\./)?(\.\./)+(\*|\.\*)?|\./(\*|\.\*)?|\.\.|\.|\*(\.\*)?|\.\*|\.claude/?'
_RM_SLASH='//*\*?|/\*/?|/\.\./\*?|/\.\*'
_RM_WS="${_ROOT_RE}"'/\*|'"${_ROOT_RE}"'/?|'"${_ROOT_RE}"'/\.\*'
_RM_TGT="(${_RM_ROOT}|${_RM_WS}|${_RM_CWDVAR}|${_RM_CMDSUB}|${_RM_VARTOP}|${_RM_BSLASH}|${_RM_LITTOP}|${_RM_HOME}|${_RM_DOTS}|${_RM_SLASH})"
if echo "$SCAN_CMD" | grep -qiE "${SEG_OPEN_Q}[[:space:]]*${WRAPPED}(/(usr/)?bin/)?rm( +${_RM_FLAG})* +${_RM_REC}( +${_RM_FLAG})*( +[^ ;|&]+)* +${_RM_TGT}([[:space:]]|[;&|)${_SQ}${_DQ}]|\$)"; then
    block "Recursive force-delete targeting dangerous path. Use targeted 'rm' on specific files instead."
fi
# F9 (r4 prototype): word-anywhere BACKSTOP for the catastrophic targets only, so an
# unknown wrapper (ionice, stdbuf, taskset, strace ...) or an unmodelled keyword cannot
# hide them. Prose is already excised upstream; unquoted prose naming `rm -rf /` blocks,
# exactly as the pre-hardening hook did. 2026-09-26 (harmonization fix 1): the home
# arm is _HOMEVAR, so the quoted/braced `"${HOME}"` spellings are backstopped too.
if echo "$SCAN_CMD" | grep -qE "(^|[[:space:]])(/(usr/)?bin/)?rm +${_RM_REC}( +${_RM_FLAG})*( +[^ ;|&]+)* +(/|//*\\*|/\\*/?|~|~/|~/\\*|${_HOMEVAR}/?|${_ROOT_RE}/?|${_ROOT_RE}/\\*|/home/[^/ ;|&]+/?)([[:space:]]|[;&|)${_SQ}${_DQ}]|\$)"; then
    block "Recursive force-delete targeting dangerous path (backstop). Use targeted 'rm' on specific files instead."
fi

#    R5-G28 (round 5, r4 finding 28): a root-level GLOB target immediately followed
#    by a substitution — `rm -rf /*$(true)`, `rm -rf /*$X`, `rm -rf /*`+backtick. The
#    substitution usually expands to nothing, leaving `/*`. The main rule's trailing
#    boundary class does not include `$`/backtick (adding it there would also catch
#    benign `rm -rf ./$NAME` / `rm -rf <root>/$PROJECT`), so only the catastrophic
#    GLOB forms get the extra boundary here.
if echo "$SCAN_CMD" | grep -qE "(^|[[:space:];&|(])(/(usr/)?bin/)?rm( +${_RM_FLAG})* +${_RM_REC}( +${_RM_FLAG})*( +[^ ;|&]+)* +(//*\\*|/\\*/?|${_ROOT_RE}/\\*|~/\\*|\\\$\\{?HOME\\}?/\\*)(\\\$|${_BT})"; then
    block "Recursive force-delete of a root-level glob followed by a substitution (it expands to the glob when the substitution is empty). Use targeted 'rm' on specific files instead."
fi

#    R5-G29 (round 5, r4 finding 29 — a user judgement call, kept separable):
#    recursive deletion of the PROJECT's git directory — `rm -rf .git`, `./.git`,
#    `<root>/.git`, `${CLAUDE_PROJECT_DIR}/.git`, with or without `/` or `/*`.
#    It destroys all local history, branches and stashes in one call. Token-exact:
#    the target must START with `.git`/`./.git`/the project root, so deleting a
#    NESTED clone's metadata (`rm -rf scratch/tpl/.git`) and git's own temp dirs
#    (`rm -rf .git-rewrite`) stay ALLOW.
#    2026-09-26 (harmonization, G29 quoted form): the variable prefix is now
#    _ROOTVAR (see _RM_ROOT above), so the double-quoted braced spelling
#    `rm -rf "${CLAUDE_PROJECT_DIR}/.git"` — KEPT with its quotes by 0c rule 5b
#    — blocks like its unquoted and `"$CLAUDE_PROJECT_DIR/.git"` siblings (FC169).
if echo "$SCAN_CMD" | grep -qiE "${SEG_OPEN_Q}[[:space:]]*${WRAPPED}(/(usr/)?bin/)?rm( +${_RM_FLAG})* +${_RM_REC}( +${_RM_FLAG})*( +[^ ;|&]+)* +(${_ROOT_RE}/+|\\./+|${_ROOTVAR}/+)?\\.git(/+|/+\\*)?([[:space:]]|[;&|)${_SQ}${_DQ}]|\$)"; then
    block "Recursive deletion of the repository's .git directory destroys all local history. If this is really intended, ask the user to do it."
fi

#    find with a destructive action rooted at / or the home directory. Only the
#    dangerous ROOTS are matched, so `find . -name '*.tmp' -delete` and
#    `find scratch -delete` stay allowed (GuardFall Class E, probe BY47).
#    2026-09-26 (harmonization fix 1): the home root is _HOMEVAR plus an
#    optional `/` and closing quote, so the braced and double-quoted spellings
#    (`find ${HOME} -delete`, `find "${HOME}" -delete`, `find "${HOME}/" …`)
#    join `$HOME`; `find "${HOME}/.cache" -type f -delete` stays ALLOW.
if echo "$SCAN_CMD" | grep -qE "${SEG_OPEN}[[:space:]]*${WRAPPED}find +(/|~/|~|${_HOMEVAR}/?${_DQ}?) [^;&|]*(-delete|-exec(dir)? +${WRAPPED}(rm|shred))"; then
    block "find with a destructive action (-delete / -exec rm) rooted at / or \$HOME deletes outside the project. Scope the search to a project directory."
fi

#    R5-G43 (round 5, r4 finding 43): an UNFILTERED `find … -delete` rooted at the
#    project (`.`, `./`, `..`, `<root>`), `/home` or a user's home. With no name/
#    path/time filter it is `rm -rf <root>` by another name. Only traversal options
#    (-maxdepth/-mindepth/-type/-xdev/-depth/-L/-P/-H …) may sit between root and
#    -delete, so `find . -name '*.pyc' -delete`, `find . -type d -empty -delete` and
#    `find scratch -delete` stay ALLOW.
#    2026-09-26 (harmonization, G29 quoted form): the project root reached through
#    a variable (`find $CLAUDE_PROJECT_DIR -delete`, `find "${BASE_DIR}" -delete`,
#    `find "${PROJECT_DIR}/" -delete`) joins the root set via _ROOTVAR; it had no
#    variable arm at all. `find "${PROJECT_DIR}/scripts/scratch" -delete` and
#    `find "${CLAUDE_PROJECT_DIR}" -name '*.pyc' -delete` stay ALLOW.
#    2026-09-26 (harmonization fix 1): the home arm is _HOMEVAR (optional
#    quotes, braces), matching the project-root arm, so `find "${HOME}" -type f
#    -delete` blocks while `find "${HOME}/.cache" -type f -delete` stays ALLOW.
if echo "$SCAN_CMD" | grep -qE "${SEG_OPEN}[[:space:]]*${WRAPPED}(/(usr/)?bin/)?find +(\\.|\\./|\\.\\./?|${_ROOT_RE}/?|${_ROOTVAR}/?${_DQ}?|/home(/[^/ ;|&]+)?/?|~/?|${_HOMEVAR}/?${_DQ}?)( +-(maxdepth|mindepth|type|xtype|xdev|mount|depth|follow|L|P|H|noleaf|ignore_readdir_race)( +[^- ;|&][^ ;|&]*)?)* +-delete([[:space:]]|[;&|)]|\$)"; then
    block "An unfiltered 'find <project or home root> -delete' deletes everything under it. Add a -name/-path filter or scope the search to a specific subdirectory."
fi

# 2. DESTRUCTIVE GIT OPERATIONS
#    Force push — rewrites remote history.
#    WHY THE REWRITE: `git\s+push\s+.*(-f|--force|--force-with-lease)` matched
#    the SUBSTRING `-f`, so `git push origin my-feature` (probe FP1) was
#    blocked by the `y-f` inside the branch name, while the refspec forms
#    `git push origin +main` (BY34) and `git push --delete origin main` (BY35)
#    — both destructive — were missed. Now every dangerous form must appear as
#    a WHOLE TOKEN. `:<ref>` (delete-by-refspec) is matched only when the token
#    STARTS with a colon, so a `host:port` URL or a `src:dst` refspec is safe.
#      FIXES: FP1.  CLOSES: BY34, BY35.  KEEPS: BY33 (--force-with-lease).
#    R5-G39 (round 5, r4 finding 39): git GLOBAL options between `git` and the verb
#    (`git -C <root> push --force`, `git -c k=v reset --hard`) defeated every
#    `git +verb` anchor below. §2 therefore scans _GIT_SCAN, a copy of SCAN_CMD with
#    the global options (-C dir, -c k=v, --git-dir/--work-tree/--namespace, and the
#    argument-less -P/-p/--no-pager/--bare/--literal-pathspecs/--no-optional-locks/
#    --no-replace-objects) removed. Only §2 uses it; every other section keeps SCAN_CMD.
_GIT_SCAN=$(printf '%s' "$SCAN_CMD" | sed -E 's/(^|[^[:alnum:]_./-])git(( +-[Cc] *[^ ;|&]+)|( +--(git-dir|work-tree|namespace)(=| +)[^ ;|&]+)|( +(--no-pager|-P|-p|--paginate|--bare|--literal-pathspecs|--no-optional-locks|--no-replace-objects)))+ +/\1git /g')
if echo "$_GIT_SCAN" | grep -qiE 'git +push[^;&|]*[[:space:]](-[a-zA-Z]*f[a-zA-Z]*|--force(-with-lease|-if-includes)?(=[^[:space:]]*)?|-[a-zA-Z]*d[a-zA-Z]*|--delete|--mirror|--prune|\+[^[:space:];&|]+|:[^[:space:];&|]+)([[:space:]]|[;&|]|$)'; then
    block "Force push / remote-ref deletion rewrites or destroys remote history. Use regular 'git push' instead."
fi

#    Hard reset — destroys uncommitted work. (The FP18 case,
#    `git log --grep="git reset --hard"`, is fixed upstream by 0c, so this
#    pattern needs no change.)
if echo "$_GIT_SCAN" | grep -qiE 'git\s+reset\s+--hard'; then
    block "Hard reset destroys uncommitted changes. Use 'git stash' to save work first."
fi

#    Clean -f — permanently deletes untracked files
if echo "$_GIT_SCAN" | grep -qiE 'git\s+clean\s+(-[a-z]*f|--force)'; then
    block "git clean -f permanently deletes untracked files. Review with 'git clean -n' first."
fi

#    Checkout . or restore . — discards all working changes.
#    WHY THE REWRITE: `git\s+(checkout|restore)\s+\.` matched the leading dot
#    of any pathspec, so `git checkout .github/workflows/ci.yml` (FP14) and
#    `git restore ./scripts/x.py` (FP15) were blocked; meanwhile the real
#    whole-tree forms `git checkout -- .` (BY4) and
#    `git restore --staged --worktree .` (BY5) slipped past because of the
#    intervening flags. Now: optional flags and `--`, then a WHOLE-TOKEN `.`
#    or `./`.
#    R5-G39: a TREE-ISH (or any non-separator token) may precede the whole-tree `.`
#    — `git checkout HEAD -- .`, `git restore -s HEAD .` — and `git checkout -f`/
#    `--force` discards local changes on switch. `git checkout -b feature`,
#    `git checkout main -- scripts/x.py` and `git restore --staged x` stay ALLOW.
if echo "$_GIT_SCAN" | grep -qiE 'git +(checkout|restore)( +(--|-[^[:space:];&|]+|[A-Za-z0-9_~^@{}:./-]+))* +\.(/)?([[:space:]]|[;&|]|$)'; then
    block "This discards all working directory changes. Use 'git stash' to save work first."
fi
if echo "$_GIT_SCAN" | grep -qE 'git +checkout( +[^ ;&|]+)* +(-[a-zA-Z]*f[a-zA-Z]*|--force)([[:space:]]|[;&|]|$)'; then
    block "git checkout -f / --force discards uncommitted changes. Use 'git stash' to save work first."
fi

#    R5-C1 (round 5 part C): `git switch -f` / `--force` / `--discard-changes`
#    throws away uncommitted changes exactly like `git checkout -f` (R5-G39). The
#    flag must be a whole token that STARTS with `-`, so `git switch main`,
#    `git switch -c feature/fix` and `git switch --detach v1` stay ALLOW.
if echo "${_GIT_SCAN:-$SCAN_CMD}" | grep -qE 'git +switch( +[^ ;&|]+)* +(-[a-zA-Z]*f[a-zA-Z]*|--force|--discard-changes)([[:space:]]|[;&|]|$)'; then
    block "git switch -f / --discard-changes discards uncommitted changes. Use 'git stash' to save work first."
fi

#    Branch force-delete. Two checks, both CASE-SENSITIVE (the previous check
#    ran under grep -i, which made the recommended-safe `git branch -d` block
#    too — a latent false positive). Bundles containing both d and f (`-fd`,
#    `-df`) and the separated long forms (`--delete --force`, `-d -f`, BY6) are
#    now covered; `-D` alone still blocks.
if echo "$_GIT_SCAN" | grep -qE 'git +branch[^;&|]*[[:space:]](-[a-zA-Z]*D[a-zA-Z]*|-[a-zA-Z]*d[a-zA-Z]*f[a-zA-Z]*|-[a-zA-Z]*f[a-zA-Z]*d[a-zA-Z]*)([[:space:]]|[;&|]|$)'; then
    block "Force-deleting a branch is irreversible. Use 'git branch -d' (safe delete) instead."
fi
if echo "$_GIT_SCAN" | grep -qE 'git +branch[^;&|]*[[:space:]](-d|--delete)([[:space:]]|$)' \
   && echo "$_GIT_SCAN" | grep -qE 'git +branch[^;&|]*[[:space:]](-f|--force)([[:space:]]|$)'; then
    block "Force-deleting a branch is irreversible. Use 'git branch -d' (safe delete) instead."
fi

# 3. PRIVILEGE ESCALATION
#    The pre-context alternation includes a backtick and `$(` opener (added
#    2026-07-17) so a substitution-embedded `sudo`/`su` — e.g. "`sudo id`" or
#    "$(sudo id)" inside a NON-single-quoted context — is caught. Prose that
#    merely NAMES sudo (`echo "on the host you would use sudo apt install"`,
#    probe FP9, and heredoc prose HD3/HD8) is now excised upstream by 0c/0a, so
#    these two patterns are unchanged and simply stop false-firing.
if echo "$SCAN_CMD" | grep -qiE '(^|\s|;|&&|\|\||`|\$\()sudo\s'; then
    block "Privilege escalation via sudo is not permitted in this environment."
fi

#    R5-C2 (round 5 part C): `doas` is the OpenBSD sudo equivalent (packaged for
#    Linux as opendoas). Round 4 (F20) made it a WRAPPER, so `doas rm -rf /` already
#    blocked, but `doas id` on its own did not. Matched in COMMAND POSITION only
#    (SEG_OPEN + wrappers, optionally path-qualified), so `which doas`,
#    `ls -l /usr/bin/doas` and prose naming it stay ALLOW.
if echo "$SCAN_CMD" | grep -qiE "${SEG_OPEN}[[:space:]]*${WRAPPED}(/([^[:space:];&|]*/)?)?doas([[:space:]]|\$)"; then
    block "Privilege escalation via doas is not permitted in this environment."
fi

if echo "$SCAN_CMD" | grep -qiE '(^|\s|;|&&|\|\||`|\$\()su\s'; then
    block "Switching user via su is not permitted in this environment."
fi
#    R5-G40 (round 5, r4 finding 40): PATH-QUALIFIED sudo/su (`/usr/bin/sudo id`,
#    `/bin/su -`). Anchored to command position (SEG_OPEN + wrappers), so a path that
#    is merely an ARGUMENT (`ls -l /usr/bin/sudo`, `stat /bin/su`) stays ALLOW.
if echo "$SCAN_CMD" | grep -qiE "${SEG_OPEN}[[:space:]]*${WRAPPED}/([^[:space:];&|]*/)?(sudo|su)([[:space:]]|\$)"; then
    block "Privilege escalation via a path-qualified sudo/su is not permitted in this environment."
fi

#    chmod: the live pattern was `chmod\s+(777|u\+s)`, which missed `-R 777`
#    (BY7), the zero-padded `0777` (BY8), the symbolic `a+rwx` (BY9) and the
#    setuid numeric `4755` (BY10). The rewrite accepts a leading flag run and
#    enumerates the four dangerous shapes. `chmod +x`, `chmod u+x`,
#    `chmod 755`, `chmod 644` must stay allowed — the symbolic branch requires
#    a `w` granted to `a` or `o`, and the numeric branches require either 777
#    or a four-digit mode with a special-bit leading digit.
#      Note on [2467]: the design named 2/4/6 (setgid/setuid/both). 7xxx sets
#      all three special bits and is strictly more dangerous, so it is included.
_CHMOD_FLAGS='( +(-[a-zA-Z-]+|--[a-z-]+))*'
#    R5-G41 (round 5, r4 finding 41): `1777` (sticky + world-writable) joins the
#    numeric branch; the symbolic branches now read EVERY clause of a comma list
#    (`ug+rw,o+w`, `u+x,u+s`), not only the first; `install -m <mode>` gets the same
#    numeric check. `chmod +x`, `755`, `644`, `u+x,g+x`, `go-w` stay ALLOW.
_CHMOD_PRECL='([ugoa]*[+=-][rwxXst]*,)*'
if echo "$SCAN_CMD" | grep -qE "chmod${_CHMOD_FLAGS} +(0?777|1777|[2467][0-7][0-7][0-7])([[:space:]]|[;&|]|$)"; then
    block "Setting world-writable (777) or setuid/setgid permissions is not permitted."
fi
if echo "$SCAN_CMD" | grep -qE "chmod${_CHMOD_FLAGS} +${_CHMOD_PRECL}[ugoa]*[ao][ugoa]*[+=][rwxXst]*w"; then
    block "Granting world/all write permission (a+w, o+w, a+rwx) is not permitted."
fi
if echo "$SCAN_CMD" | grep -qE "chmod${_CHMOD_FLAGS} +${_CHMOD_PRECL}[ugoa]*[+=][rwxXt]*s"; then
    block "Setting setuid/setgid permissions is not permitted."
fi
if echo "$SCAN_CMD" | grep -qE "${SEG_OPEN}[[:space:]]*${WRAPPED}(/(usr/)?bin/)?install [^|;&]*(-m *|--mode(=| +))(0?777|1777|[2467][0-7][0-7][0-7])([[:space:]]|[;&|]|$)"; then
    block "install -m with a world-writable (777) or setuid/setgid mode is not permitted."
fi

#    R5-C3 (round 5 part C, r4 case R4C05): `chmod --reference=RFILE f` copies
#    RFILE's mode, which the scan cannot see. A SYSTEM file can carry exactly the
#    modes this section forbids (`/usr/bin/passwd` is setuid 4755, `/tmp` is 1777),
#    so a reference to a top-level system directory, /tmp, /home, `~` or `$HOME`
#    is blocked. A reference inside the project (`chmod --reference=scripts/a.sh
#    scripts/b.sh`, `--reference=<root>/…`) stays ALLOW: a project file only
#    holds a dangerous mode if an earlier command already set one.
if echo "$SCAN_CMD" | grep -qE "chmod( +[^ ;|&]+)* +--reference(=| +)(~|\\\$\\{?HOME\\}?|/(usr|etc|bin|sbin|lib|lib64|var|opt|boot|dev|proc|sys|root|srv|run|mnt|media|tmp|home)(/|[[:space:]]|[;&|]|\$))"; then
    block "chmod --reference to a system path copies a mode the safety scan cannot see (setuid from /usr/bin/passwd, 1777 from /tmp). Set the mode explicitly instead."
fi

# 4. DANGEROUS NETWORK PATTERNS
#    Pipe-to-shell — arbitrary remote code execution.
#    WHY THE TRAILING BOUNDARY: `\|\s*(bash|sh|…)` had no word boundary, so
#    `curl … | sha256sum` (FP3) and `curl … | shuf -n 1` (FP4) matched on the
#    `sh` prefix. The receiver name must now be followed by PIPE_RECV_END
#    (whitespace, `; & | )`, backtick, or end) — originally
#    `([[:space:]]|$|[;&|])`, widened by the 2026-09-26 port below.
#    2026-09-26 (harmonization, DAAF cycle-3/4 port): both downloader guards use
#    the shared receiver vocabulary (_DL_PIPE_PRE below = PIPE_OP +
#    PIPE_RECV_PRE + optional path), superseding round 4's F7 per-site wrapper
#    run. New: flag-ARG wrapper items (`| env -u HOME bash`, `| timeout -s KILL
#    5 bash`, DAAF r4 S06/S07), `mksh ash fish csh tcsh \.` (S10), and the
#    `)`/backtick terminators (`(curl … | bash)` S01, `x=$(curl … | sh)` S02,
#    `curl … | bash)` S13, `(curl … | python3)` S15). A quoted receiver reaches
#    here canonicalized by 0c (`| "bash"` → `| bash`, S04).
_DL_PIPE_PRE="(curl|wget)[[:space:]]+.*${PIPE_OP}${PIPE_RECV_PRE}([^[:space:]]*/)?"
if echo "$SCAN_CMD" | grep -qiE "${_DL_PIPE_PRE}(${PIPE_SHELLS})${PIPE_RECV_END}"; then
    block "Piping downloaded content to a shell is arbitrary code execution. Download first, review, then execute."
fi

#    Pipe into a BARE interpreter reading code from stdin (GuardFall Class D;
#    probe BY11 `curl -s https://x/i.sh | python3`). Deliberately narrow: the
#    interpreter must be followed by end-of-segment or by flag tokens ONLY.
#    `| python3 -m json.tool`, `| python3 script.py`, `| jq .`, `| sha256sum`
#    all stay allowed — SOURCE: Continue's Step 4 warning that treating every
#    pipe into python as risky over-prompts
#    (output/preliminary_notes/2026-09-18_research_guardfall-and-data-vs-code.md §4).
if echo "$SCAN_CMD" | grep -qE "${_DL_PIPE_PRE}(${PIPE_INTERPS})([[:space:]]+-[^[:space:];&|]*)*[[:space:]]*(\$|[;&|)${_BT}])"; then
    block "Piping downloaded content into a bare interpreter is arbitrary code execution. Download first, review, then execute."
fi

#    COMMAND-SUBSTITUTION DOWNLOAD-EXECUTE — ONE guard, three shapes.
#    2026-09-26 (harmonization, DAAF cycle-3/4 port): round 4's F7b and DAAF
#    fix cycle 4's add-on (b) guards b1/b2 closed overlapping parts of the same
#    family; they are merged here so the coverage is their UNION (starter-kit
#    R4D05-R4D07; DAAF r4 B01-B03, B06, B07):
#      F7b  a shell word, eval, source or `.` whose (optionally flag-bearing,
#           optionally 0c-promoted `; `) argument is a `$(curl …)`/backtick
#           substitution: `bash -c "$(curl …)"` → `bash -c ; $(curl …)`,
#           `eval "$(curl …)"`, `source "$(curl …)"`, `bash "$(curl …)"`.
#      b1   a substitution whose FIRST word is curl/wget in COMMAND position —
#           it executes the downloaded output as a command, whether it arrived
#           there by 0c promotion or was typed bare (`$(curl -s …/cmd)`).
#      b2   a NON-shell interpreter `-c`/`-e` body, or a `<<<` here-string into
#           a shell/interpreter, holding a still-quoted `"$(curl …)"` (0c rule
#           5b KEEPs it): `python3 -c "$(curl …)"`, `bash <<< "$(curl …)"`.
#    MUST ALLOW (DAAF FC85+ list): `echo "$(curl -s …)"`, `VAR="$(curl -s …)"`,
#    `jq . <<< "$(curl -s …)"`, `grep -c ok <<< "$(curl -s …)"`,
#    `python3 script.py "$(curl -s …)"`, `diff <(curl -s a) <(curl -s b)`.
#    curl/wget must sit IMMEDIATELY inside the substitution, so
#    `python3 -c "$(cat f)"` (a local file) is not matched.
_SUBEXE_INTERP='(bash|sh|zsh|dash|ksh|mksh|busybox|python[0-9.]*|perl|ruby|node|php|Rscript|R)'
if echo "$SCAN_CMD" | grep -qE \
     -e "(^|[[:space:]])(bash|sh|zsh|dash|ksh|eval|source|\\.)( +-[^ ;|&]+)*( *;)? *[\"']?(\\\$\\(|${_BT}) *(curl|wget)[[:space:]]" \
     -e "(^|[;&|])[[:space:]]*(\\\$\\(|${_BT})[[:space:]]*(curl|wget)([[:space:]]|\$)" \
     -e "(^|[[:space:]])([^[:space:]]*/)?${_SUBEXE_INTERP}[[:space:]]+([^;&|]*[[:space:]])?(-[a-zA-Z]*[ce][a-zA-Z]*|<<<)[[:space:]${_SQ}${_DQ}${_BT}]*(\\\$\\(|${_BT})[[:space:]]*(curl|wget)([[:space:]]|\$)"; then
    block "Executing downloaded content via command substitution (bash -c \"\$(curl …)\", eval \"\$(curl …)\", python3 -c \"\$(curl …)\", bash <<< \"\$(curl …)\") is arbitrary code execution. Download first, review, then execute."
fi

#    Process substitution: `bash <(curl …)` (probe BY12) is the same remote
#    code execution with no pipe character to match on.
if echo "$SCAN_CMD" | grep -qE '(bash|sh|zsh|dash|ksh|source|\.) +<\([[:space:]]*(curl|wget)'; then
    block "Executing a downloaded script via process substitution is arbitrary code execution. Download first, review, then execute."
fi

#    File exfiltration — uploading local files to arbitrary URLs. The live
#    pattern covered -d@/-F=@/--data@/--data-binary@/--upload-file; probes
#    BY14-BY17 showed `-T`, `--data-urlencode @`, `--json @` and wget's
#    `--post-file=`/`--body-file=` all uncovered.
if echo "$SCAN_CMD" | grep -qiE 'curl\b.*(-d\s*@|-F\s*.*=@|--data-binary\s*@|--data-raw\s*@|--data-urlencode\s*@|--json\s*@|--data\s*@|--upload-file|[[:space:]]-T[[:space:]])'; then
    block "Uploading local files via curl is a data exfiltration risk. Review the file and destination first."
fi

if echo "$SCAN_CMD" | grep -qiE 'wget\s+.*--(post-file|body-file)(=|[[:space:]])'; then
    block "Uploading local files via wget (--post-file / --body-file) is a data exfiltration risk. Review the file and destination first."
fi

# 5. CONTAINER ESCAPE ATTEMPTS
#    OPENER/WRAPPER DESIGN (comment rewritten 2026-09-18; history corrected
#    2026-09-26, harmonization fix 1). All three guards below — `docker run`,
#    mount/umount/chroot, and the path-qualified mount/umount/chroot — fire only
#    when the verb is in COMMAND POSITION: immediately after
#      - start of string,
#      - a command separator `; & |`,
#      - a grouping/boundary character from the SEG_OPEN class `( ) { `,
#        i.e. `(`, `)` and `{` (the closing paren is in the class because a
#        `$(…)`/subshell close is also a segment boundary),
#      - a substitution opener `` ` `` or `$(`,
#      - find's ` -exec` / ` -execdir`, or a shell keyword,
#      - and, for the two mount guards ONLY, a single or double quote
#        (SEG_OPEN_MNT; the `docker run` guard uses plain SEG_OPEN),
#    optionally followed by `VAR=value` assignments and one or more WRAPPERS
#    (the shared list: `sudo doas env command exec xargs nohup setsid eval time
#    nice ionice chrt taskset stdbuf unshare nsenter strace ltrace flock chronic
#    busybox timeout`, each with its own flags, numbers and flag arguments —
#    see WRAPPERS). The 2026-09-17 pass narrowed these guards from a bare
#    word-anywhere match to this shape, because `grep -n mount file.sh` and
#    prose mentioning `mount` were false-blocking
#    (scripts/scratch/mount_hook_e2e_2026-09-17.sh).
#
#    OPENER HISTORY of the mount guards, in three steps:
#      1. 2026-09-17: the single and double quote characters were ADDED to the
#         opener set to catch `bash -c 'mount x y'`.
#      2. 2026-09-18: they were REMOVED again, because they also blocked any
#         quoted string that merely BEGINS with `mount ` — probes FP11
#         (`echo 'mount the volume first'`) and FP12
#         (`grep -n 'mount point' /etc/fstab`). Stage 0c now PROMOTES a shell
#         carrier body to a real segment start (`bash -c ; mount x y`), so the
#         carrier case is covered by `;`.
#      3. 2026-09-24 R3-F1, refined 2026-09-26 (DAAF FIX-3 = P4): the quote
#         openers came BACK for a KEEP'd `VAR=` value (see R3-F1 below), now as
#         SEG_OPEN_MNT — quotes but no bare `$`. The prose FPs of step 2 stay
#         fixed because 0c excises data-consumer prose before this section.
#
#    The `docker run` guard is realigned to the same command-position shape.
#    It previously used a bare `(^|\s|;|&&|\|\||`|\$\()` pre-context, which
#    fired on unquoted prose (`echo docker run is blocked`) and missed wrapper
#    forms (`timeout 5 docker run x`). Its flag-argument wrapper forms
#    (`timeout -s KILL 5 docker run x`, `env -u HOME docker run x`) block
#    again since harmonization fix 1 (FC184-FC186).
if echo "$SCAN_CMD" | grep -qiE "${SEG_OPEN}[[:space:]]*${WRAPPED}docker +run([[:space:]]|[;&|]|$)"; then
    block "Running nested Docker containers is not permitted in this environment."
fi

#    R3-F1 (applied 2026-09-24 during the port): this guard opened on
#    SEG_OPEN_Q, not SEG_OPEN; since the 2026-09-26 port (P4, below) it opens
#    on SEG_OPEN_MNT. Red-team round 3 case A03/A04
#    (`A='mount /dev/sda /mnt' eval "$A"`) showed that 0c RULE 1b KEEPS a
#    quoted VAR= assignment value, so the only opener left in front of the
#    verb is the quote character itself. Section 1 already accepts quote
#    openers (SEG_OPEN_Q); this guard did not, and the live pre-hardening
#    hook DID block the shape — a regression. Prose that merely names
#    `mount` is excised upstream by 0c (its receiver is a data consumer), so
#    FP11/FP12 (`echo 'mount the volume first'`,
#    `grep -n 'mount point' /etc/fstab`) stay ALLOW.
#    2026-09-26 (harmonization, DAAF cycle-3/4 port: DAAF FIX-3): both mount
#    guards open on SEG_OPEN_MNT — SEG_OPEN_Q minus the bare `$` — so the quote
#    opener that R3-F1 needs is kept while `ls $mount`, `df -h "$mount"`,
#    `echo $chroot`, `cd "$umount"`, `findmnt | grep "$mount"` stop false-
#    blocking (DAAF r4 M40-M43, M56). See SEG_OPEN_MNT's definition.
if echo "$SCAN_CMD" | grep -qiE "${SEG_OPEN_MNT}[[:space:]]*${WRAPPED}(mount|umount|chroot)([[:space:]]|$)"; then
    block "Filesystem mount/chroot is not permitted in this environment."
fi
#    R5-G40: the same guard for a PATH-QUALIFIED verb (`/bin/mount …`,
#    `/usr/sbin/chroot /mnt`). Same opener set; `ls /mnt`, `stat /bin/mount` ALLOW.
if echo "$SCAN_CMD" | grep -qiE "${SEG_OPEN_MNT}[[:space:]]*${WRAPPED}/([^[:space:];&|]*/)?(mount|umount|chroot)([[:space:]]|\$)"; then
    block "Filesystem mount/chroot (path-qualified) is not permitted in this environment."
fi

# 6. PROVENANCE BOUNDARY — /tmp WRITES
#    /tmp is outside the Docker-volume backup boundary and the audit trail, and
#    the session log viewer renders /tmp paths as broken references. Agents that
#    write working files there lose them silently. The correct home for any
#    temporary or intermediate file is inside the project, which IS backed up
#    and audited.
#
#    This guard is deliberately WRITE-OPERATOR-GATED: it matches only shell
#    operations that *write into* the ephemeral roots, never bare string
#    presence. Reads (cat, ls, head, tail, grep, jq, stat, wc, ...) must pass,
#    because this project's own hooks and statuslines legitimately cache coordination
#    state in /tmp (e.g. /tmp/claude-ctx-window-*, /tmp/claude-model-*) and
#    agents sometimes read those caches via Bash. Reading /tmp and redirecting
#    the output INTO the project is the sanctioned rescue pattern and must pass.
#
#    2026-09-18 CHANGES:
#      - /var/tmp and /dev/shm join /tmp (probe BY19): both are outside the
#        backup boundary in exactly the same way.
#      - quoted destinations no longer need special handling. `echo hi >
#        "/tmp/x.txt"` (BY18) and `tee "/tmp/x"` (BY48) walked past the live
#        patterns because the quote characters sat between the operator and the
#        path; stage 0c now CANONICALIZES a single-token quoted argument, so
#        the path reaches these patterns unquoted.
#      - mktemp is blocked unless it is explicitly pointed somewhere else
#        (probe BY20): its default is $TMPDIR or /tmp.
#
#    ACCEPTED RESIDUAL GAPS (covered by the instruction layer — CLAUDE.md
#    § Boundaries & Safety > Provenance Boundary — not by this shell hook):
#      - Program-argument writes, where the path is passed to a program that
#        writes there internally (e.g. `python x.py /tmp/out/`, probe BY21).
#        A shell-level regex cannot see inside the program, and blocking any
#        command that merely *contains* a /tmp token would break the read and
#        rescue passes above.
#      - `find ... -exec <writer> ... /tmp/ ... \;`, where the write happens in
#        a spawned subcommand the top-level scan does not decompose.
SCRATCH_HINT="Working files belong inside the project (use ${SITE_SCRATCH_DIR}), not /tmp — /tmp is outside the backup and audit boundary."

#    The ephemeral roots, kept as one reusable fragment so every write-operator
#    check stays consistent.
#    R5-G36 (round 5, r4 finding 36): the roots tolerate repeated slashes and `./`
#    segments (`//tmp/x`, `/./tmp/x` name /tmp/x) — §7's PSEP idea applied here. A
#    relative `./tmp` or `scratch//tmp` is not matched: the root must START with `/`
#    right after the operator/space the §6 patterns require. (`\/` is folded by 0d.)
_TSEP='/+(\./+)*'
TMP_ROOT="(${_TSEP}tmp|${_TSEP}var${_TSEP}tmp|${_TSEP}dev${_TSEP}shm)"
TMP_DEST="${TMP_ROOT}(/[^ ;|&<>]*)?([ ;|&<>]|$)"

#    Destination-ANCHORED variant: the ephemeral token must be the trailing path
#    argument (end of command, optional trailing whitespace). Used for commands
#    where it may appear as EITHER source or destination — cp/mv/rsync/install.
#    Anchoring to end-of-command matches `cp f /tmp/x` (dest is /tmp → block) but
#    not `cp /tmp/x f` (source is /tmp, dest is project → the sanctioned rescue).
TMP_DEST_END="${TMP_ROOT}(/[^ ;|&<>]*)?( +-[-a-zA-Z0-9=]+)* *(\$|[;&|<>]|[0-9]?[<>])"

#    6a. Output redirection into /tmp: >, >>, 2>, &>, 1>, and the clobber
#        operator >| — followed by the ephemeral root.
if echo "$SCAN_CMD" | grep -qiE "([0-9]?>>?|[0-9]?>\||&>) *${TMP_DEST}"; then
    block "Output redirection (>, >>, >|, 2>, &>) into /tmp is blocked. $SCRATCH_HINT"
fi

#    6b. tee writing to /tmp — the path may appear ANYWHERE in tee's destination
#        list (tee accepts multiple files). The [^<|]* stops the match at an
#        input-redirect (`<`) or pipe (`|`) boundary, so the sanctioned
#        `tee <root>/out.txt < /tmp/input` still passes.
if echo "$SCAN_CMD" | grep -qiE "\btee\b[^<|]* ${TMP_DEST}"; then
    block "Writing to /tmp via tee is blocked. $SCRATCH_HINT"
fi

#    6c. Copy/move/sync/install with an ephemeral DESTINATION argument.
if echo "$SCAN_CMD" | grep -qiE "\b(cp|mv|rsync|install)\b.* ${TMP_DEST_END}" || echo "$SCAN_CMD" | grep -qiE "\b(cp|mv|install)\b[^|;&]*(-t|--target-directory[= ]) *${TMP_DEST}"; then
    block "Copying/moving (cp/mv/rsync/install) into /tmp is blocked. $SCRATCH_HINT"
fi

#    6d. Directory / file creation in /tmp: mkdir (with flags) and touch.
#        R5-G37 (round 5): the flag run also admits `--` and long flags (`--parents`).
if echo "$SCAN_CMD" | grep -qiE "\bmkdir\b( +-[-a-zA-Z]+)* +${TMP_DEST}"; then
    block "Creating directories (mkdir) in /tmp is blocked. $SCRATCH_HINT"
fi

if echo "$SCAN_CMD" | grep -qiE "\btouch\b.* ${TMP_DEST}"; then
    block "Creating files (touch) in /tmp is blocked. $SCRATCH_HINT"
fi

#    6e. Downloads written into /tmp: curl -o/--output, wget -O.
if echo "$SCAN_CMD" | grep -qiE "\bcurl\b.*(-o|--output|--output-dir) *${TMP_DEST}"; then
    block "Downloading (curl -o) into /tmp is blocked. $SCRATCH_HINT"
fi

if echo "$SCAN_CMD" | grep -qiE "\bwget\b.*(-[a-zA-Z]*O|-P|--directory-prefix=?) *${TMP_DEST}"; then
    block "Downloading (wget -O) into /tmp is blocked. $SCRATCH_HINT"
fi

#    6f. In-place edits of /tmp files: sed -i.
if echo "$SCAN_CMD" | grep -qiE "\bsed\b.* -i[a-zA-Z.]*.* ${TMP_DEST}"; then
    block "Editing /tmp files in place (sed -i) is blocked. $SCRATCH_HINT"
fi

#    6g. Archive extraction into /tmp: unzip -d /tmp, tar -C /tmp.
#        R5-G37 (round 5): attached `-d/tmp`, `-C/tmp` and tar's `--directory[=| ]`.
if echo "$SCAN_CMD" | grep -qiE "\bunzip\b.* -d *${TMP_DEST}"; then
    block "Extracting (unzip -d) into /tmp is blocked. $SCRATCH_HINT"
fi

if echo "$SCAN_CMD" | grep -qiE "\btar\b.* (-C *|--directory(=| +))${TMP_DEST}"; then
    block "Extracting (tar -C) into /tmp is blocked. $SCRATCH_HINT"
fi

#    6h. Cloning a repo into /tmp: git clone ... /tmp/dest.
if echo "$SCAN_CMD" | grep -qiE "\bgit +clone\b.* ${TMP_DEST}"; then
    block "Cloning (git clone) into /tmp is blocked. $SCRATCH_HINT"
fi

#    6i. Block-copy into /tmp: dd of=/tmp/... (the write target is `of=`, so a
#        /tmp source in `if=` — the sanctioned read direction — is not matched).
if echo "$SCAN_CMD" | grep -qiE "\bdd\b.* of=${TMP_DEST}"; then
    block "Writing to /tmp via dd (of=) is blocked. $SCRATCH_HINT"
fi

#    6j. Truncating/creating /tmp files: truncate.
if echo "$SCAN_CMD" | grep -qiE "\btruncate\b.* ${TMP_DEST}"; then
    block "Truncating/creating /tmp files (truncate) is blocked. $SCRATCH_HINT"
fi

#    6k. Symlinks involving /tmp — blocked in BOTH directions. `ln` is anchored
#        to COMMAND-START position rather than a bare \bln\b word boundary,
#        because `ln` is only two characters and appears inside common flags
#        (e.g. `ls -ln /tmp`, where -ln is the ls long+numeric flag).
if echo "$SCAN_CMD" | grep -qiE "(^|[;|&] *)ln .* ${TMP_DEST}"; then
    block "Symlinks involving /tmp (ln — either direction) are blocked; /tmp targets dangle after restart. $SCRATCH_HINT"
fi

#    6l. mktemp — its default destination is $TMPDIR or /tmp (probe BY20).
#        Allowed only when explicitly redirected elsewhere with -p /
#        --tmpdir= / a TMPDIR= prefix naming a non-ephemeral directory.
#        2026-09-18 fix cycle 1 (red-team F9): the segment anchor reaches
#        through leading `VAR=value ` assignments (VARPRE, folded into
#        WRAPPED), so `TMPDIR=/tmp mktemp` — which previously defeated the gate
#        by putting a non-verb token first — now BLOCKS, while
#        `TMPDIR=<root>/scratch mktemp` is recognised as an explicit redirect and
#        ALLOWS.
if echo "$SCAN_CMD" | grep -qE "(^|[;&|]) ?${WRAPPED}mktemp([[:space:]]|[;&|]|$)"; then
    _mk_ok=0
    if echo "$SCAN_CMD" | grep -qE "(TMPDIR=|--tmpdir=|-p +)${TMP_ROOT}"; then
        _mk_ok=0
    elif echo "$SCAN_CMD" | grep -qE "(TMPDIR=|--tmpdir=|-p +)[^ ;|&]+"; then
        _mk_ok=1
    fi
    if [[ $_mk_ok -eq 0 ]]; then
        block "mktemp defaults to /tmp, which is outside the backup and audit boundary. $SCRATCH_HINT"
    fi
fi

# 7. SAFETY-SYSTEM TAMPERING (added 2026-07-11; hardened 2026-09-18)
#    settings.json denies Edit/Write on .claude/hooks/ and .claude/logs/, but
#    shell writes (cp, mv, tee, redirection, sed -i, chmod) bypass those
#    tool-scoped rules — and `Bash(cp *)` is auto-approved. Hook and log
#    changes are USER-ONLY operations. Read access (cat, grep, ls, `bash <hook>`
#    for testing) stays open, as do git index operations (add, update-index).
#
#    THIS IS THE HIGHEST-VALUE SECTION IN THE HOOK. Container isolation
#    (non-root, cap_drop ALL) already removes the credential-exfiltration harm
#    that dominates GuardFall's threat model; what it does NOT protect is the
#    hook/settings files themselves. GuardFall's Class E ("alternative argv
#    shapes … Class E survives the most guards") lands squarely here.
#
#    2026-09-18 ADDITIONS, each closing an observed bypass:
#      - WRAPPERS before the verb: `env cp evil.sh .claude/hooks/x.sh` (BY26).
#      - ` -exec` / ` -execdir` as an opener: `find … -exec cp … .claude/hooks/`.
#      - shell carriers: `sh -c "cp evil.sh .claude/hooks/x.sh"` (BY24) is
#        promoted to a segment start by stage 0c and then matches normally.
#      - trailing GNU flags before the end anchor:
#        `cp evil.sh .claude/hooks/ -v` (BY23).
#      - Class E argv shapes: `tar -C <protected>`, `unzip -d <protected>`,
#        `find … <protected> … -delete`.
#
#    Protected paths extend beyond the original hook/log dirs:
#      - .claude/hooks/ and .claude/logs/  (Edit/Write already denied there)
#      - any site-specific directory in SITE_EXTRA_PROTECTED_DIRS (DAAF:
#        benchmarks/harness/hooks/, from which settings.json registers
#        block-git-writes.sh — an active PreToolUse Bash hook).
#      - .claude/settings.json and .claude/settings.local.json — the ROOT OF
#        TRUST. A shell overwrite here could deregister every hook.
#
#    PATH-SEPARATOR NORMALIZATION (PSEP): a literal `.claude/hooks` also names
#    the same inode via `.claude//hooks` and `.claude/./hooks`. Both were
#    probe-confirmed to slip past a single-slash pattern. PSEP replaces every
#    inter-component `/` with a fragment that tolerates repeated slashes and
#    `./` segments. We deliberately do NOT collapse `//` in SCAN_CMD — that
#    would corrupt legitimate `//` in URLs.
#
#    RESIDUAL RISK (updated 2026-09-18): the `find -exec` and wrapper-prefix
#    residuals documented here before this revision are now CLOSED (see the
#    additions above). What remains is (a) cwd-relative evasion (`cd .claude`
#    in one call, then `cp x hooks/y` in the next), which is beyond
#    single-command string matching and is bounded by the one-command-per-call
#    rule plus the audit log; and (b) a protected path computed at runtime from
#    a variable or substitution (GuardFall Class C).
PSEP='/+(\./+)*'
#    Site-specific extra protected directories (SITE_EXTRA_PROTECTED_DIRS) join
#    the alternation with every `.` escaped and every `/` widened to PSEP.
_PROT_EXTRA=''
for _pe in "${SITE_EXTRA_PROTECTED_DIRS[@]}"; do
    _pe_re="${_pe//./'\.'}"
    _PROT_EXTRA+="|${_pe_re//\//"$PSEP"}"
done
PROTECTED_DIRS="(\.claude${PSEP}(hooks|logs)${_PROT_EXTRA}|\.claude${PSEP}settings(\.local)?\.json|\.claude${PSEP}[^ /;|&]*[][*?{][^ /;|&]*)"

#    Mutation verbs are split into two groups, mirroring the §6c asymmetry
#    (TMP_DEST_END). COPY-VERBS (cp|rsync|install) take a trailing DESTINATION,
#    and a protected path may legitimately appear as the read-direction SOURCE
#    (`cp .claude/settings.json backup.json`). So they match only when the
#    protected path is the destination: end-anchored, tolerating trailing GNU
#    flags (`-v`, `--verbose`, `-a`) and, since round 4 (F1), a following
#    separator or redirect (`cp x .claude/hooks/y; echo done`). A destination
#    given with `-t`/`--target-directory` is matched by its own rule (F2b).
#    TARGET-VERBS (rm|mv|ln|dd|tee|touch|truncate|chmod|chown|chattr|shred|
#    unlink|git rm|git mv) act ON the protected path in any argument position,
#    so they keep the match-anywhere form. `mv` belongs here, not with the copy
#    verbs (round 4, finding 3 / fix F2): moving FROM a protected path removes
#    it (`mv .claude/hooks .claude/hooks.bak` disables every hook), so for `mv`
#    the source position is itself a mutation.
SEG7="(^|[;&|]|[[:space:]]-exec(dir)?[[:space:]]|[[:space:]](then|do|else|elif|if|while|until|!)[[:space:]]|^![[:space:]])"
#    The trailing run tolerates GNU flags placed AFTER the destination
#    (`cp evil.sh .claude/hooks/ -v`, probe BY23) and find's `-exec` terminators
#    (`\;` / `+`), so `find … -exec cp {} .claude/hooks/x.sh \;` is caught too.
PROT_DEST_END="(/[^ ;|&<>]*)?( +(\\\\;|\\+|-[-a-zA-Z0-9=]+))* *(\$|[;&|<>]|[0-9]?[<>])"
if echo "$SCAN_CMD" | grep -qE "${SEG7} ?${WRAPPED}(/(usr/)?bin/)?(cp|mv|install) [^|;&<>]*(-t|--target-directory[= ]) *[^ ;|&]*${PROTECTED_DIRS}"; then
    block "Copying/moving INTO the safety system via -t/--target-directory bypasses the Edit/Write deny rules (anti-tampering)."
fi
if echo "$SCAN_CMD" | grep -qE "${SEG7} ?${WRAPPED}(/(usr/)?bin/)?(cp|rsync|install) [^|;&<>]*${PROTECTED_DIRS}${PROT_DEST_END}"; then
    block "Copying (cp/rsync/install) INTO the safety system (${_PROT_LABEL}) via shell bypasses the Edit/Write deny rules (anti-tampering). These changes are user-only — ask the user to apply them. (Reading FROM a protected path — a source-position backup — is allowed.)"
fi

if echo "$SCAN_CMD" | grep -qE "${SEG7} ?${WRAPPED}(/(usr/)?bin/)?(rm|mv|ln|dd|tee|touch|truncate|chmod|chown|chattr|shred|unlink|git +(rm|mv)) [^|;&<>]*${PROTECTED_DIRS}"; then
    block "Modifying the safety system (${_PROT_LABEL}) via shell (rm/mv/ln/dd/tee/touch/truncate/chmod/chown/chattr/shred/unlink/git rm/git mv) bypasses the Edit/Write deny rules (anti-tampering). These changes are user-only — ask the user to apply them."
fi

if echo "$SCAN_CMD" | grep -qE ">>?\|? ?[^ ]*${PROTECTED_DIRS}"; then
    block "Redirecting output into the safety system (${_PROT_LABEL}) bypasses the Edit/Write deny rules (anti-tampering). These changes are user-only — ask the user to apply them."
fi

#    The sed verb is anchored to a command-segment start (plus wrappers and
#    -exec), so a protected path named in descriptive prose no longer
#    false-blocks — only a real in-place edit is caught.
if echo "$SCAN_CMD" | grep -qE "${SEG7} ?${WRAPPED}(sed [^|;&]*-[a-zA-Z]*i[^|;&]*|perl [^|;&]*-[a-zA-Z]*i[^|;&]*)${PROTECTED_DIRS}"; then
    block "In-place editing of the safety system (${_PROT_LABEL}) bypasses the Edit/Write deny rules (anti-tampering). These changes are user-only — ask the user to apply them."
fi

#    Class E argv shapes against protected paths: archive extraction with an
#    explicit output directory, and find's own delete action.
if echo "$SCAN_CMD" | grep -qE "${SEG7} ?${WRAPPED}(tar|unzip) [^|;&]*(-C|-d) +[^ ;|&]*${PROTECTED_DIRS}"; then
    block "Extracting an archive INTO the safety system (tar -C / unzip -d) bypasses the Edit/Write deny rules (anti-tampering). These changes are user-only — ask the user to apply them."
fi

if echo "$SCAN_CMD" | grep -qE "${SEG7} ?${WRAPPED}find [^|;&]*${PROTECTED_DIRS}[^|;&]*-delete"; then
    block "Deleting safety-system files via find -delete bypasses the Edit/Write deny rules (anti-tampering). These changes are user-only — ask the user to apply them."
fi

#    R5-G10 (round 5, r4 finding 10 — a user judgement call, kept separable): the
#    DESTINATION is the `.claude` directory ITSELF (`.claude`, `.claude/`,
#    `<root>/.claude`, `~/.claude`, `$HOME/.claude`, `/home/<u>/.claude`). A source
#    named `hooks` or `settings.json` then lands on a protected path without the
#    protected name ever appearing in the command (`cp -r scratch/hooks .claude/`).
#    Destination-exact: a deeper destination (`cp x .claude/skills/new/`,
#    `.claude/agents/`) and `.claude` as the SOURCE (`cp -r .claude scratch/bak`) stay
#    ALLOW. tar needs an extract flag (`x`, --extract, --get), so archiving FROM
#    `.claude` with `-C .claude` stays ALLOW.
_CLDIR='(\./)?(('"${_ROOT_RE}"'|~|\$\{?HOME\}?|/home/[^/ ;|&]+)/+)?\.claude(/+\.?)*'
_CLDIR_END="( +(\\\\;|\\+|-[-a-zA-Z0-9=]+))* *(\$|[;&|<>]|[0-9]?[<>])"
if echo "$SCAN_CMD" | grep -qE "${SEG7} ?${WRAPPED}(/(usr/)?bin/)?(cp|mv|rsync|install) [^|;&<>]* ${_CLDIR}${_CLDIR_END}" \
   || echo "$SCAN_CMD" | grep -qE "${SEG7} ?${WRAPPED}(/(usr/)?bin/)?(cp|mv|install) [^|;&<>]*(-t|--target-directory[= ]) *${_CLDIR}([[:space:]]|[;&|<>]|\$)" \
   || echo "$SCAN_CMD" | grep -qE "${SEG7} ?${WRAPPED}(/(usr/)?bin/)?unzip [^|;&]* -d *${_CLDIR}([[:space:]]|[;&|<>]|\$)" \
   || { echo "$SCAN_CMD" | grep -qE "${SEG7} ?${WRAPPED}(/(usr/)?bin/)?tar [^|;&]* (-C *|--directory(=| +))${_CLDIR}([[:space:]]|[;&|<>]|\$)" \
        && echo "$SCAN_CMD" | grep -qE "(^|[;&|[:space:]])tar( +[^ |;&]+)* +(-?[a-zA-Z]*x[a-zA-Z]*|--extract|--get)([[:space:]]|[;&|]|\$)"; }; then
    block "Copying/moving/extracting INTO the .claude directory itself can overwrite the safety system (a source named hooks or settings.json lands on the protected path). Copy into a specific subdirectory such as .claude/skills/<name>/, or ask the user."
fi

#    R5-G11 (round 5, r4 finding 11): the protected path is find's ROOT and the
#    mutation happens in -exec/-execdir/-ok (`find .claude/hooks … -exec rm {} \;`),
#    or the protected path is listed and PIPED into `xargs <verb>`. Read-only uses
#    (`find .claude/hooks -name '*.sh'`, `-exec wc -l {} +`, `| xargs grep -l x`,
#    `-exec cp {} scratch/ \;` — a backup) stay ALLOW: only mutating verbs count.
_G11_VERBS='(rm|mv|chmod|chown|chattr|shred|unlink|truncate|tee|touch)([[:space:]]|[;&|)]|$)|(sed|perl) [^|;&]*-[a-zA-Z]*i'
if echo "$SCAN_CMD" | grep -qE "${SEG7} ?${WRAPPED}(/(usr/)?bin/)?find [^|;&]*${PROTECTED_DIRS}[^|;&]*[[:space:]]-(exec|execdir|ok|okdir) +${WRAPPED}(/(usr/)?bin/)?(${_G11_VERBS})" \
   || echo "$SCAN_CMD" | grep -qE "${PROTECTED_DIRS}[^;&]*\\|&? *${VARPRE}(/(usr/)?bin/)?xargs( +-[^ ;|&]+( +[^- ;|&][^ ;|&]*)?)* +${WRAPPED}(/(usr/)?bin/)?(${_G11_VERBS})"; then
    block "Mutating safety-system files through find -exec or xargs bypasses the Edit/Write deny rules (anti-tampering). These changes are user-only — ask the user to apply them."
fi

# 8. AD-HOC PACKAGE INSTALLATION (added 2026-07-11; wrappers added 2026-09-18)
#    The container environment is defined by the Dockerfile; installing or
#    removing packages at runtime creates unreproducible drift that a rebuild
#    silently reverts — and `Bash(python *)` auto-approves `python -m pip
#    install` today. Add the package to the Dockerfile and rebuild instead.
#    Read-only commands (pip list, pip show, uv --version) and `pip download`
#    (fetch-only, no install) remain allowed.
#
#    2026-09-18: every segment anchor in this section now accepts the shared
#    WRAPPERS alternation, closing the "wrapper-prefixed forms (`time conda
#    install x`, `env Rscript -e …`)" residual that the previous revision
#    documented as accepted. The companion "quoted interpreter name"
#    residual (`'Rscript' -e …`) is closed upstream by stage 0c, which
#    CANONICALIZES a quoted command-position token.
#    `python -m ensurepip` (probe BY31) is added below. `npm` is deliberately
#    NOT guarded at either site: DAAF's image has no npm (`command -v npm`
#    printed nothing when this was decided), and the starter kit's image has a
#    real npm project whose dependency installs are legitimate work (its
#    battery row PT33). The block messages end with SITE_REBUILD_HINT.

#    pip/pipx: `pipx run` and `pipx runpip` fetch+execute ephemeral packages, so
#    they join install/uninstall.
if echo "$SCAN_CMD" | grep -qiE "(^|[;&|]) ?${WRAPPED}([^ ;|&]*/)?(pip3?(\.[0-9]+)?|pipx)( +-[^ ;|&]+)* +(install|uninstall|run|runpip)\b"; then
    block "Runtime package changes drift from the Dockerfile and vanish on rebuild. Add the package to the Dockerfile and rebuild ${SITE_REBUILD_HINT}."
fi

#    python -m pip: interpreter may be versioned (`python3.11`) or the `py`
#    launcher, and ANY tokens may sit between it and `-m pip`.
if echo "$SCAN_CMD" | grep -qiE '\b(python[0-9.]*|py) [^|;&]*-m *pip( +-[^ ;|&]+)* +(install|uninstall)\b'; then
    block "Runtime package changes (python -m pip) drift from the Dockerfile and vanish on rebuild. Add the package to the Dockerfile and rebuild ${SITE_REBUILD_HINT}."
fi

#    python -m ensurepip bootstraps pip into the environment — the same runtime
#    drift by a different verb (probe BY31).
if echo "$SCAN_CMD" | grep -qiE '\b(python[0-9.]*|py) [^|;&]*-m ensurepip\b'; then
    block "\`python -m ensurepip\` bootstraps pip into the runtime environment (Dockerfile drift). Add what you need to the Dockerfile and rebuild ${SITE_REBUILD_HINT}."
fi

#    uv: pip/add/remove/sync/tool subcommands, plus `uv run --with pkg` which
#    installs pkg into the run's ephemeral environment.
if echo "$SCAN_CMD" | grep -qiE "(^|[;&|]) ?${WRAPPED}uv( +-[^ ;|&]+)* +(pip( +-[^ ;|&]+)* +(install|uninstall|sync)|add|remove|sync|tool +(install|run))\b"; then
    block "Runtime package changes via uv drift from the Dockerfile and vanish on rebuild. Add the package to the Dockerfile and rebuild ${SITE_REBUILD_HINT}."
fi

if echo "$SCAN_CMD" | grep -qiE "(^|[;&|]) ?${WRAPPED}uv run [^|;&]*--with\b"; then
    block "\`uv run --with\` implicitly installs the named package into an ephemeral environment (runtime drift). Add the package to the Dockerfile and rebuild ${SITE_REBUILD_HINT}."
fi

#    conda / uvx / easy_install, grouped under ONE command-segment anchor so a
#    token named in descriptive prose no longer false-blocks.
if echo "$SCAN_CMD" | grep -qiE "(^|[;&|]) ?${WRAPPED}(uvx\b|easy_install\b|conda (install|remove|update|create|env (update|create))\b)"; then
    block "Runtime package execution/installation (uvx/easy_install/conda) drifts from the Dockerfile. Add the tool to the Dockerfile and rebuild ${SITE_REBUILD_HINT}."
fi

#    R package installation (added 2026-07-16). Shared at both sites: DAAF runs
#    R; the starter kit's image has no R (`command -v R` empty there), where the
#    guard costs two greps, cannot false-fire on a command that could succeed,
#    and is correct in advance should that Dockerfile gain r-base. The
#    run_with_capture.sh / enforce-file-first.sh wrappers named below are DAAF
#    components (no counterpart in the starter kit).
#    The dominant R path —
#    `install.packages()` written INSIDE a `.R` script and executed via
#    scripts/run_with_capture.sh — is invisible to any shell-level hook; it is
#    covered at the wrapper by run_with_capture.sh's pre-execution content scan,
#    and for coding agents additionally by enforce-file-first.sh. This hook
#    covers the command-line R forms.
#
#    8a. `R CMD INSTALL pkg.tar.gz` — segment-anchored.
if echo "$SCAN_CMD" | grep -qiE "(^|[;&|]) ?${WRAPPED}R CMD INSTALL\b"; then
    block "Runtime R package installation (R CMD INSTALL) drifts from the Dockerfile and vanishes on rebuild. Add the package to the Dockerfile and rebuild ${SITE_REBUILD_HINT}."
fi

#    8b. R-eval installs: an R interpreter invoked at a command-segment start
#        (now also after wrappers) AND an install-family token appearing
#        ANYWHERE. The two conditions are ANDed so that neither alone
#        false-blocks: a bare `R --version` (gate yes, token no) and a
#        `grep -rn "install.packages" scripts/` (token yes, gate no) both pass.
#      ACCEPTED RESIDUALS: (1) token obfuscation via variable expansion or
#        base64 (`R -e "$(echo ...)"`) is not decoded by a shell regex — the
#        same Class C residual as elsewhere. (2) `R -f script.R` where the
#        install lives in the file is not visible here — covered at the wrapper
#        by run_with_capture.sh's scan.
R_INSTALL_TOKENS='install\.packages|update\.packages|remove\.packages|install_(github|gitlab|bitbucket|cran|version|local|url|git|svn|bioc|dev)|pkg_install|pak::pak|renv::(install|restore|update|rebuild)|BiocManager::install|biocLite'
if echo "$SCAN_CMD" | grep -qiE "(^|[;&|]) ?${WRAPPED}(Rscript[0-9.]*|R|r)\b" && echo "$SCAN_CMD" | grep -qiE "$R_INSTALL_TOKENS"; then
    block "Runtime R package installation (install.packages / remotes / devtools / pak / renv / BiocManager, etc.) drifts from the Dockerfile and vanishes on rebuild. Add the package to the Dockerfile and rebuild ${SITE_REBUILD_HINT}."
fi

# ---------------------------------------------------------------------------
# 9. REMOTION BUNDLE-PER-CALL DISK GUARD (added 2026-09-14)
#    Marker for the regression battery: REMOTION_BUNDLE_GUARD
#
#    SITE EXTENSION (2026-09-26 harmonization): this section runs only when
#    SITE_ENABLE_REMOTION_GUARD=1 (the Claude Code Starter Kit); at DAAF it is
#    inert. Its message names SITE_ROOT and SITE_REMOTION_DIR.
#    Carried forward (2026-09-24) from the starter kit's live hook, where it
#    was section 9. The only change then was that it scans SCAN_CMD (the
#    stage-0 classified copy) like
#    every other section, instead of NORM_CMD — so a Remotion CLI invocation
#    hidden inside `bash -c '...'` is promoted to a command segment and caught,
#    while prose in a heredoc or an excised data argument that merely NAMES
#    `remotion render` no longer false-blocks.
#
#    Every Remotion CLI render/bundle subcommand builds a fresh webpack bundle
#    and COPIES the entire publicDir into a new `remotion-webpack-bundle-*`
#    temp directory. A loop of `npx remotion still ...` calls therefore
#    multiplies public/ by the number of stills, and any process killed
#    mid-render orphans its bundle. On 2026-09-14 that filled this container's
#    1 TB disk mid-arc and stopped work.
#
#    The sanctioned paths bundle ONCE per invocation against a curated small
#    publicDir, pin TMPDIR inside the project, and always delete the bundle:
#      <SITE_REMOTION_DIR>/tools/cards.mjs   - QA card stills (builders)
#      <SITE_REMOTION_DIR>/tools/render.mjs  - renderMedia (orchestrator only)
#    A command line that invokes either tool is exempt, so a wrapper that
#    happens to mention the CLI in a comment or argument still passes.
#
#    NOT matched (deliberately allowed): `remotion studio` (serves in place,
#    no per-call bundle copy), `remotion versions`, `--help`, and any other
#    read-only subcommand.
REMOTION_CLI_RENDER='(^|[;&|[:space:]])(npx[[:space:]]+(--[^[:space:]]+[[:space:]]+)*)?remotion[[:space:]]+(still|render|bundle|benchmark)([[:space:]]|$)'
REMOTION_SAFE_TOOL='tools/(cards|render)\.mjs'

if [[ "${SITE_ENABLE_REMOTION_GUARD:-0}" == "1" ]] \
   && echo "$SCAN_CMD" | grep -qE "$REMOTION_CLI_RENDER" \
   && ! echo "$SCAN_CMD" | grep -qE "$REMOTION_SAFE_TOOL"; then
    # The message is a QUOTED heredoc (its backticks are literal text); the two
    # site values are substituted afterwards with quoted replacements.
    _rm_msg=$(cat <<'REMOTION_MSG'
bare `remotion still|render|bundle|benchmark` is not permitted in this project.

Each CLI call rebuilds a webpack bundle and copies the whole publicDir into a
fresh temp directory; repeated calls filled this container's disk on 2026-09-14.

Use the project tools instead - they bundle ONCE per invocation against a
curated publicDir, pin TMPDIR to @RDIR@/.remotion-tmp/, and always
remove the bundle:

  QA card stills :  node @ROOT@/@RDIR@/tools/cards.mjs jobs.json
  Renders        :  node @ROOT@/@RDIR@/tools/render.mjs --composition ID --out FILE
                    (orchestrator only - builders never render media)

Large media is served over HTTP, not from public/. Start the server first:
  python3 @ROOT@/scripts/media_server.py --start

`remotion studio` is unaffected and remains allowed.
See @ROOT@/@RDIR@/tools/README.md.
REMOTION_MSG
)
    _rm_msg="${_rm_msg//@ROOT@/"$SITE_ROOT"}"
    block "${_rm_msg//@RDIR@/"$SITE_REMOTION_DIR"}"
fi

# ---------------------------------------------------------------------------
# 10. ACCIDENTAL ENVIRONMENT-DISCLOSURE GUARD (added 2026-10-02)
#     Marker for the regression battery: ENV_DISCLOSURE_GUARD
#
#     PURPOSE. Everything a command prints or writes can land in an audit log,
#     a session archive, or a file. This container's environment holds real API
#     keys. This guard blocks the FUNCTIONAL, accidental shapes that would dump
#     the environment or a credential-named value — the same posture as
#     run_with_capture.sh's pre-execution env-print scan, but for shell commands
#     typed at the command line. It is NOT an adversarial sieve: obfuscated or
#     indirected shapes are out of scope (see RESIDUALS). The design priority is
#     to not interfere with regular work, so every clause is narrow and every
#     block message names the CATEGORY and a SAFE ALTERNATIVE, never the matched
#     text (the battery and bats both echo a block message, so it must carry no
#     credential-shaped substring).
#
#     FOUR CATEGORIES (mirroring run_with_capture.sh):
#       A  Whole-environment dump: a bare `env` / `set` / `export -p` /
#          `printenv` in command position with NO operand (only flags, then a
#          terminator, pipe or redirect). The same command followed by a program
#          to run stays allowed (`env FOO=1 cmd`, `env -i python x.py`).
#       B  A credential-named variable sent to output or a file. Two shapes:
#          an `echo`/`printf` whose segment then expands an UNESCAPED `$NAME`
#          (or `${NAME}`); and a name-literal print form (`declare -p NAME`,
#          `typeset -p NAME`, `printenv NAME`). "credential-named" = an
#          UPPERCASE name whose LAST underscore segment is one of KEY, APIKEY,
#          TOKEN, SECRET, PASSWORD, PASSWD, PASSPHRASE, CREDENTIAL, CREDS, DSN,
#          PAT. Single-segment names (no underscore) are exempt — a bare
#          $TOKEN/$PATH/$HOME is almost always benign — and so are plurals
#          (…_KEYS, …_TOKENS), …_SESSION, …_AUTH, …_COOKIE (orchestrator
#          decision 2026-10-01 after a repo-wide NAME census: of 23 names that
#          hit the earlier shared vocab, only the `*_API_KEY` family were real
#          credentials). Path-valued credential variables are conventionally
#          named `*_CREDENTIALS` / `*_FILE` / `*_PATH`, whose last segment is a
#          plural or is not in the set, so they fall out naturally (B4). B scans
#          SCAN_CMD AND the §10 accumulator (the stage-0-excised spans that still
#          expand). Case-SENSITIVE: lowercase shell names are usually loop or
#          local variables, so matching them would cause many false positives.
#       C  Process-environment file read: any `/proc/<pid>/environ` path. There
#          is no benign need to read it here.
#       D  Interpreter one-liner that prints a whole environment object. Same
#          AND-shape as §8b: an interpreter in command position AND a whole-env
#          token anywhere (os.environ, Sys.getenv(), process.env, %ENV, ENVIRON,
#          ENV.<method>). Neither alone blocks (`python3 --version`, or a
#          `grep os.environ file.py`, both pass). Case-SENSITIVE so prose like
#          "environment" never matches the uppercase %ENV/ENVIRON tokens, and so
#          single-variable reads (os.environ["X"], process.env.X, $ENV{X},
#          ENV["X"], ENVIRON["X"]) fall through as benign. ENVIRON carries a
#          trailing boundary ([^A-Z0-9_[]|$) so an interpreter one-liner that
#          merely names an identifier STARTING with ENVIRON (ENVIRONMENT,
#          ENVIRON_LABEL) is not false-blocked; awk's whole-env forms (bare
#          `print ENVIRON`, `for (k in ENVIRON)`) still match (trailing EOL or
#          `)` / space is in the boundary class).
#
#     WHY AN ACCUMULATOR. Stage 0a/0c EXCISE heredoc and double-quoted data
#     spans as shell-inert, but the shell still expands `$NAME` inside an
#     unquoted-delimiter heredoc body and a double-quoted span. Widening the
#     stage-0 rules would pull prose into the word-anywhere guards; instead a
#     purely additive accumulator (_ENV10_ACC, populated in 0a and 0c above)
#     keeps a copy of exactly those spans for category B. No stage-0
#     classification changed. A/C/D scan SCAN_CMD only — a whole-env token or a
#     /proc path sitting in an excised DATA span is text, not an action, so
#     scanning the accumulator for them would only add false positives.
#
#     FAIL-CLOSED. Over 20,000 chars 0c is skipped and text stays visible in
#     SCAN_CMD, so §10 still sees it (fail-closed). A 0a bail loses the receiver
#     link, so a body is not accumulated (residual). The ERR trap does not fire
#     inside an `if` condition, so the regression suites pin at least one BLOCK
#     row per category to catch a malformed regex.
#
#     ACCEPTED FALSE POSITIVES (BLOCK today): any uppercase variable (not only
#     a loop variable) whose last `_`-segment is a credential keyword, echoed
#     or printed (e.g. $CACHE_KEY, $SORT_KEY, $SESSION_TOKEN); a single-quoted
#     single-token span that 0c canonicalizes. RESIDUALS (ALLOW today): a
#     whole-env dump PIPED into a filter (`env | grep PATH`, `set | wc -l`) — a
#     pipe is not treated as a sink, so filtered inspection stays allowed
#     (category A sinks are a terminal or a file only); likewise a `2>`
#     stderr-redirect (`env 2>f`) is not a sink (the `2` sits before the `>`,
#     outside the `([;&)]|>|$)` set), so it stays allowed — a miss, not an FP;
#     a value first copied into another
#     variable; a name computed at run time; lowercase environment names; a
#     dump written to a file by an interpreter; `declare`/`compgen`/`typeset`
#     listing forms other than `-p`; bare `export`; a 0a bail body; secrets
#     passed into a network request (sanctioned use). Adversarial coverage is
#     functional-only, as for §8b's _EF1 / R5-T1.
#
#     PERF. A cheap bash-only substring prefilter skips the greps entirely on
#     the common path (no env/set/export/proc/ENV/`$`/declare/typeset present).
#     Vocab matching uses grep -E, not bash `=~`, to avoid nested-quantifier
#     backtracking on long identifiers (the audit-log W1 jq lesson).
_ENV10_NAME='[A-Z][A-Z0-9]*(_[A-Z0-9]+)*_(KEY|APIKEY|TOKEN|SECRET|PASSWORD|PASSWD|PASSPHRASE|CREDENTIAL|CREDS|DSN|PAT)'
# A credential-named parameter expansion: $NAME or ${NAME}, with a trailing
# boundary so plurals (…_KEYS) do not match. Used for the accumulator scan,
# where the preceding char is guaranteed non-backslash: the leading ([^\]|^)
# rejects an escaped \$ when the span starts mid-string.
_ENV10_EXP='([^\]|^)[$]\{?('"$_ENV10_NAME"')(\}|[^A-Z0-9_]|$)'
# The expansion TAIL (no leading guard) and the MID run between a print verb's
# space and the `$`: any text not crossing a segment end whose LAST char (if
# any) is NOT a backslash, so an escaped `\$` is not matched even when the `$`
# follows the verb's separating space directly.
_ENV10_EXPTAIL='[$]\{?('"$_ENV10_NAME"')(\}|[^A-Z0-9_]|$)'
_ENV10_MID='([^;&|]*[^\;&|])?'
# A: a variable-listing command with no operand (flags only), then a TERMINAL
# or FILE sink — a segment end (`; & )`, newline-as-`;`, end of string) or a
# redirect (`>`). A PIPE is deliberately NOT a sink here: `env | grep PATH`,
# `set | wc -l` are benign filtered inspection (pinned ALLOW, e.g. FC28), and
# blocking them would interfere with regular work.
_ENV10_A_RE="${SEG_OPEN}${WRAPPED}((env|set)|export[[:space:]]+-p|printenv)[[:space:]]*([;&)]|>|\$)"
# B shape 1: echo/printf whose SAME segment then expands a credential name.
_ENV10_B_PRINT="${SEG_OPEN}${WRAPPED}(echo|printf)[[:space:]]${_ENV10_MID}${_ENV10_EXPTAIL}"
# B shape 2: a name-literal print form naming a credential variable.
_ENV10_B_NAME="${SEG_OPEN}${WRAPPED}((declare|typeset)[[:space:]]+-[A-Za-z]*p[A-Za-z]*[[:space:]]+|printenv[[:space:]]+(-0[[:space:]]+)?)(${_ENV10_NAME})([^A-Z0-9_]|\$)"
# C: a /proc/<pid>/environ path anywhere.
_ENV10_C_RE='/proc/[^[:space:]/]+/environ'
# D: an interpreter in command position (gate) AND a whole-env token (anywhere).
_ENV10_D_INTERP="${SEG_OPEN}${WRAPPED}([^[:space:]/;&|]*/)?(python[0-9.]*|Rscript[0-9.]*|R|node|nodejs|perl[0-9.]*|ruby[0-9.]*|gawk|mawk|awk)\\b"
_ENV10_D_TOK='os\.environ([^._A-Za-z0-9[]|\.(items|values|copy|keys)|$)|Sys\.getenv\([[:space:]]*(\)|names|unset)|process\.env([^._A-Za-z0-9[]|$)|%ENV|ENVIRON([^A-Z0-9_[]|$)|ENV\.(to_h|to_a|each_pair|each|inspect|keys|values|sort)'

# Combined text for category B (SCAN_CMD plus the stage-0-excised spans).
_env10_all="$SCAN_CMD"$'\n'"$_ENV10_ACC"

if [[ "$_env10_all" == *'$'* || "$_env10_all" == *env* || "$_env10_all" == *set* \
   || "$_env10_all" == *export* || "$_env10_all" == *proc* || "$_env10_all" == *ENV* \
   || "$_env10_all" == *getenv* || "$_env10_all" == *declare* || "$_env10_all" == *typeset* ]]; then
    if echo "$SCAN_CMD" | grep -qE "$_ENV10_A_RE"; then
        block "Accidental whole-environment disclosure (category: environment dump). A bare env / set / export -p / printenv writes every variable — including this container's real API keys — to output or a file, where it lands in the audit log and backups. To confirm a variable is set without revealing it, test its presence with [ -n \"\${VAR:+set}\" ]; to list names only, use compgen -v; to run a program under a modified environment, give env a command to run."
    fi
    # B over SCAN_CMD needs the printing verb or name-literal form; B over the
    # accumulator needs only the expansion itself, because every span in the
    # accumulator was already an ARGUMENT to a data consumer that prints or
    # writes it (its verb is not part of the recorded span).
    if echo "$SCAN_CMD" | grep -qE "$_ENV10_B_PRINT" \
       || echo "$SCAN_CMD" | grep -qE "$_ENV10_B_NAME" \
       || { [[ -n "$_ENV10_ACC" ]] && echo "$_ENV10_ACC" | grep -qE "$_ENV10_EXP"; }; then
        block "Accidental credential disclosure (category: credential-named variable sent to output or a file). Expanding a variable whose name ends in KEY/APIKEY/TOKEN/SECRET/PASSWORD/PASSWD/PASSPHRASE/CREDENTIAL/CREDS/DSN/PAT, and echoing it or writing it to a file, would copy the secret into the permanent audit record. Confirm the credential is configured by printing its presence or length instead ([ -n \"\${NAME:+set}\" ] or \${#NAME}), and pass the value straight to the program that needs it rather than echoing it."
    fi
    if echo "$SCAN_CMD" | grep -qE "$_ENV10_C_RE"; then
        block "Accidental environment disclosure (category: process-environment file read). Reading a /proc/<pid>/environ file exposes that process's entire environment, credentials included. There is no benign need to read it here; to check a variable, print its presence or length instead."
    fi
    if echo "$SCAN_CMD" | grep -qE "$_ENV10_D_INTERP" && echo "$SCAN_CMD" | grep -qE "$_ENV10_D_TOK"; then
        block "Accidental environment disclosure (category: interpreter one-liner environment print). An inline interpreter command that prints a whole environment object (os.environ, Sys.getenv(), process.env, %ENV, ENV, ENVIRON) writes every variable, credentials included, to output. Print a single variable's presence or length instead, or move the logic into a script run via run_with_capture.sh, which scans for environment prints."
    fi
fi

# ---------------------------------------------------------------------------
# All checks passed — allow the command
# ---------------------------------------------------------------------------
exit 0
