#!/usr/bin/env bash
# bash-safety.sh — PreToolUse hook that blocks dangerous Bash commands
#
# This is the primary safety guardrail for the DAAF environment. It reads
# the tool invocation JSON from stdin and inspects the command field for
# patterns that are destructive, privilege-escalating, or data-exfiltrating.
# It also enforces safety-system integrity (section 7): shell writes to the
# hook, log, and settings files bypass the Edit/Write deny rules and are
# blocked as user-only; ad-hoc package installation (section 8): runtime
# package changes drift from the Dockerfile and are blocked; and a provenance
# boundary (section 6): model-initiated shell writes to /tmp are blocked
# because /tmp is outside the Docker-volume backup boundary and the audit trail.
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
#   provenance guard follows the same principle: reading DAAF's own /tmp
#   coordination caches is fine, but *writing* working files to /tmp is blocked.
#
# Normalization note:
#   NORM_CMD drops backslash line-continuations before collapsing whitespace,
#   so a multi-line command (`cp f \` ⏎ `.claude/hooks/x`) cannot slip a stray
#   `\` token between a verb and its target and defeat the adjacency patterns
#   in sections 1-5.
#
# Quote-awareness note (section 0):
#   A `git commit -m` message body is DATA, not code. Before the pattern checks
#   run, section 0 excises shell-provably-inert commit-message bodies from a
#   working copy (SCAN_CMD) so a message that merely *describes* a dangerous
#   command (e.g. "docs: explain why rm -rf / is blocked") no longer false-
#   blocks. Single-quoted bodies are excised unconditionally (POSIX-inert);
#   double-quoted bodies are excised only when free of backtick / $( / ${ ;
#   any ambiguity fails closed to leaving the text intact (still scanned).
#
# Hook event: PreToolUse (matcher: "Bash")
# Registered in: .claude/settings.json

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

# Normalize: drop backslash line continuations, then collapse whitespace.
# sed processes line-by-line, so it strips a trailing backslash on every line
# BEFORE tr collapses the newlines into single spaces. Without this, a
# backslash line-continuation would leave a stray `\` token between a verb and
# its target (e.g. `cp f \ .claude/hooks/x`) and defeat the verb/whitespace-
# adjacency regexes in sections 1-5.
NORM_CMD=$(echo "$CMD" | sed 's/\\$//' | tr -s '[:space:]' ' ')

# ---------------------------------------------------------------------------
# block: Print a descriptive error to stderr and exit 2 to block execution
# ---------------------------------------------------------------------------
block() {
    echo "BLOCKED by bash-safety hook: $1" >&2
    exit 2
}

# ---------------------------------------------------------------------------
# 0. QUOTE-AWARE COMMIT-MESSAGE EXCISION (added 2026-07-17)
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
#   MONOTONICITY / FAIL-CLOSED: excision only ever *removes* text the shell
#   itself cannot execute — a single-quoted body is POSIX-inert, and a double-
#   quoted body free of command/parameter substitution cannot execute. Every
#   ambiguous parse degrades to NOT stripping, so the carve-out can never make
#   the guard weaker than the live hook against anything it already catches.
#   Sections 1-8 below all scan $SCAN_CMD (== $NORM_CMD when nothing was excised).
#
#   ACCEPTED RESIDUALS (all fail-closed — they keep BLOCKING):
#     (1) Double-quoted bodies containing ${...}, $(...), or a backtick are left
#         intact and still scanned — a real substitution executes at commit time.
#         Escape hatch for a legitimately dangerous-LOOKING message: single-quote
#         it, or use `git commit -F <file>`.
#     (2) ANSI-C $'...' and locale $"..." bodies are left intact (the `$` before
#         the quote never reaches the gap), even though $'...' is inert — the
#         mispairing / eval edge cases are not worth handling in a regex.
#     (3) Concatenated partial quoting (`-m "a"'b'`) excises only the matched
#         quote-pair; any leftover piece stays in the scanned text.
#     (4) The §3/§5 opener tightening below newly blocks backtick/$(-prefixed
#         danger words in NON-commit commands (e.g. echo 'use `sudo x`') — inert
#         there, accepted as a fail-closed trade. Commit messages are unaffected
#         because this excision stage runs first.
#     (5) SCOPE: this stage fixes commit-message false positives (plus one
#         substitution-opener false negative in §3/§5). It does NOT close the
#         general raw-string regex-guard bypass class (GuardFall) — that remains
#         covered by container isolation and the permission layers.
#
#   IMPLEMENTATION: bash-internal [[ =~ ]] (POSIX ERE) only — no extra deps, no
#   per-pattern subprocess. A non-matching =~ inside an `if`/`while` condition
#   does not trip the ERR trap, and loop progress is counted with
#   _iter=$((_iter + 1)) (never ((_iter++)), which returns 1 when the result is 0
#   and would fire the trap).
SCAN_CMD="$NORM_CMD"

_BT=$'\x60'   # a literal backtick, isolated so the char classes below stay legible
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
# Pattern checks — order: most dangerous first
# ---------------------------------------------------------------------------

# 1. DESTRUCTIVE FILESYSTEM OPERATIONS
#    rm -rf with dangerous targets (root, home, current dir, wildcards)
if echo "$SCAN_CMD" | grep -qiE 'rm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r)\s+(/|/\*|~|\$HOME|\.\.|\.|\*)'; then
    block "Recursive force-delete targeting dangerous path. Use targeted 'rm' on specific files instead."
fi

# 2. DESTRUCTIVE GIT OPERATIONS
#    Force push — rewrites remote history
if echo "$SCAN_CMD" | grep -qiE 'git\s+push\s+.*(-f|--force|--force-with-lease)'; then
    block "Force push rewrites remote history. Use regular 'git push' instead."
fi

#    Hard reset — destroys uncommitted work
if echo "$SCAN_CMD" | grep -qiE 'git\s+reset\s+--hard'; then
    block "Hard reset destroys uncommitted changes. Use 'git stash' to save work first."
fi

#    Clean -f — permanently deletes untracked files
if echo "$SCAN_CMD" | grep -qiE 'git\s+clean\s+(-[a-z]*f|--force)'; then
    block "git clean -f permanently deletes untracked files. Review with 'git clean -n' first."
fi

#    Checkout . or restore . — discards all working changes
if echo "$SCAN_CMD" | grep -qiE 'git\s+(checkout|restore)\s+\.'; then
    block "This discards all working directory changes. Use 'git stash' to save work first."
fi

#    Branch force-delete
if echo "$SCAN_CMD" | grep -qiE 'git\s+branch\s+-D'; then
    block "Force-deleting a branch is irreversible. Use 'git branch -d' (safe delete) instead."
fi

# 3. PRIVILEGE ESCALATION
#    The pre-context alternation includes a backtick and `$(` opener (added
#    2026-07-17) so a substitution-embedded `sudo`/`su` — e.g. "`sudo id`" or
#    "$(sudo id)" inside a NON-single-quoted context — is caught. (Commit-message
#    prose is handled upstream by the §0 excision, which runs first.)
if echo "$SCAN_CMD" | grep -qiE '(^|\s|;|&&|\|\||`|\$\()sudo\s'; then
    block "Privilege escalation via sudo is not permitted in this environment."
fi

if echo "$SCAN_CMD" | grep -qiE '(^|\s|;|&&|\|\||`|\$\()su\s'; then
    block "Switching user via su is not permitted in this environment."
fi

if echo "$SCAN_CMD" | grep -qiE 'chmod\s+(777|u\+s)'; then
    block "Setting world-writable (777) or setuid permissions is not permitted."
fi

# 4. DANGEROUS NETWORK PATTERNS
#    Pipe-to-shell — arbitrary remote code execution
if echo "$SCAN_CMD" | grep -qiE '(curl|wget)\s+.*\|\s*(bash|sh|zsh|dash|source)'; then
    block "Piping downloaded content to a shell is arbitrary code execution. Download first, review, then execute."
fi

#    File exfiltration — uploading local files to arbitrary URLs
if echo "$SCAN_CMD" | grep -qiE 'curl\s+.*(-d\s*@|-F\s*.*=@|--data-binary\s*@|--data\s*@|--upload-file)'; then
    block "Uploading local files via curl is a data exfiltration risk. Review the file and destination first."
fi

# 5. CONTAINER ESCAPE ATTEMPTS
#    The pre-context alternation gains the same backtick / `$(` openers as §3.
if echo "$SCAN_CMD" | grep -qiE '(^|\s|;|&&|\|\||`|\$\()docker\s+run'; then
    block "Running nested Docker containers is not permitted in this environment."
fi

if echo "$SCAN_CMD" | grep -qiE '(^|\s|;|&&|\|\||`|\$\()(mount|chroot)\s'; then
    block "Filesystem mount/chroot is not permitted in this environment."
fi

# 6. PROVENANCE BOUNDARY — /tmp WRITES
#    /tmp is outside the Docker-volume backup boundary and the audit trail, and
#    the session log viewer renders /tmp paths as broken references. Agents that
#    write working files there lose them silently. The correct home for any
#    temporary or intermediate file is inside the project, which IS backed up
#    and audited.
#
#    This guard is deliberately WRITE-OPERATOR-GATED: it matches only shell
#    operations that *write into* /tmp, never bare /tmp string presence. Reads
#    (cat, ls, head, tail, grep, jq, stat, wc, ... on /tmp paths) must pass,
#    because DAAF's own hooks and statuslines legitimately cache coordination
#    state in /tmp (e.g. /tmp/claude-ctx-window-*, /tmp/claude-model-*) and
#    agents sometimes read those caches via Bash. Reading /tmp and redirecting
#    the output INTO the project is the sanctioned rescue pattern and must pass.
#
#    ACCEPTED RESIDUAL GAPS (covered by the instruction layer — CLAUDE.md
#    § Boundaries & Safety > Provenance Boundary — not by this shell hook):
#      - Program-argument writes, where /tmp is passed as an argument to a
#        program that writes there internally (e.g. `python x.py /tmp/out/`).
#        A shell-level regex cannot see inside the program, and blocking any
#        command that merely *contains* a /tmp token would break the read and
#        rescue passes above.
#      - `find ... -exec <writer> ... /tmp/ ... \;`, where the write happens in
#        a spawned subcommand the top-level scan does not decompose.
#    These are deliberately out of scope here; the CLAUDE.md prohibition and the
#    settings.json Write/Edit(//tmp/**) deny rules are the compensating controls.
#
#    A /tmp destination is /tmp/ (a path under /tmp) or bare /tmp used as a
#    directory argument. The shared alternative-location hint:
SCRATCH_HINT="Working files belong inside the project (use {PROJECT_DIR}/scripts/scratch/), not /tmp — /tmp is outside the backup and audit boundary."

#    A /tmp destination token: /tmp followed by a slash-path, or bare /tmp at a
#    word boundary (end of string, space, or shell metacharacter). Kept as a
#    single reusable fragment so every write-operator check stays consistent.
TMP_DEST='/tmp(/[^ ;|&<>]*)?([ ;|&<>]|$)'

#    Destination-ANCHORED variant: the /tmp token must be the trailing path
#    argument (end of command, optional trailing whitespace). Used for commands
#    where /tmp may appear as EITHER source or destination — cp/mv/rsync/install.
#    Anchoring to end-of-command matches `cp f /tmp/x` (dest is /tmp → block) but
#    not `cp /tmp/x f` (source is /tmp, dest is project → the sanctioned rescue).
TMP_DEST_END='/tmp(/[^ ;|&<>]*)? *$'

#    6a. Output redirection into /tmp: >, >>, 2>, &>, 1>, and the clobber
#        operator >| — followed by /tmp. Covers `head -n 5 f.py > /tmp/x.py`,
#        `cmd 2> /tmp/err`, and `cmd >| /tmp/out`. Reading a /tmp file and
#        redirecting into a project path is NOT matched here, because the
#        redirect target is the project path, not /tmp.
if echo "$SCAN_CMD" | grep -qiE "([0-9]?>>?|[0-9]?>\||&>) *${TMP_DEST}"; then
    block "Output redirection (>, >>, >|, 2>, &>) into /tmp is blocked. $SCRATCH_HINT"
fi

#    6b. tee writing to /tmp — /tmp may appear ANYWHERE in tee's destination
#        list (tee accepts multiple files: `tee a.txt /tmp/x.txt`), so match a
#        /tmp token anywhere in tee's argument run. The [^<|]* stops the match
#        at an input-redirect (`<`) or pipe (`|`) boundary, so the sanctioned
#        `tee /daaf/out.txt < /tmp/input` (write project, read /tmp) still
#        passes and a downstream `| grep /tmp` isn't misread as a tee target.
if echo "$SCAN_CMD" | grep -qiE "\btee\b[^<|]* ${TMP_DEST}"; then
    block "Writing to /tmp via tee is blocked. $SCRATCH_HINT"
fi

#    6c. Copy/move/sync/install with a /tmp DESTINATION argument. These take a
#        trailing destination, and /tmp may legitimately appear as the SOURCE
#        (the sanctioned rescue: `cp /tmp/claude-model-x {PROJECT_DIR}/...`).
#        Anchor to end-of-command so only a /tmp *destination* is blocked.
if echo "$SCAN_CMD" | grep -qiE "\b(cp|mv|rsync|install)\b.* ${TMP_DEST_END}"; then
    block "Copying/moving (cp/mv/rsync/install) into /tmp is blocked. $SCRATCH_HINT"
fi

#    6d. Directory / file creation in /tmp: mkdir (with flags) and touch.
if echo "$SCAN_CMD" | grep -qiE "\bmkdir\b( +-[a-zA-Z]+)* +${TMP_DEST}"; then
    block "Creating directories (mkdir) in /tmp is blocked. $SCRATCH_HINT"
fi

if echo "$SCAN_CMD" | grep -qiE "\btouch\b.* ${TMP_DEST}"; then
    block "Creating files (touch) in /tmp is blocked. $SCRATCH_HINT"
fi

#    6e. Downloads written into /tmp: curl -o/--output, wget -O.
if echo "$SCAN_CMD" | grep -qiE "\bcurl\b.*(-o|--output) +${TMP_DEST}"; then
    block "Downloading (curl -o) into /tmp is blocked. $SCRATCH_HINT"
fi

if echo "$SCAN_CMD" | grep -qiE "\bwget\b.*-O +${TMP_DEST}"; then
    block "Downloading (wget -O) into /tmp is blocked. $SCRATCH_HINT"
fi

#    6f. In-place edits of /tmp files: sed -i.
if echo "$SCAN_CMD" | grep -qiE "\bsed\b.* -i[a-zA-Z.]*.* ${TMP_DEST}"; then
    block "Editing /tmp files in place (sed -i) is blocked. $SCRATCH_HINT"
fi

#    6g. Archive extraction into /tmp: unzip -d /tmp, tar -C /tmp.
if echo "$SCAN_CMD" | grep -qiE "\bunzip\b.* -d +${TMP_DEST}"; then
    block "Extracting (unzip -d) into /tmp is blocked. $SCRATCH_HINT"
fi

if echo "$SCAN_CMD" | grep -qiE "\btar\b.* -C +${TMP_DEST}"; then
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

#    6k. Symlinks involving /tmp — blocked in BOTH directions. `ln -s src /tmp/l`
#        writes a link into /tmp; `ln -s /tmp/target projectlink` creates a
#        project file that dangles after container restart (the /tmp target does
#        not survive) — itself a provenance hazard. Either /tmp as link name or
#        as link target is blocked.
#
#        `ln` is anchored to COMMAND-START position — start of string or right
#        after a command separator (;, |, &) — rather than a bare \bln\b word
#        boundary. `ln` is only two characters and appears inside common flags
#        (e.g. `ls -ln /tmp`, where -ln is the ls long+numeric flag); a word
#        boundary would false-block those reads. Command-start anchoring matches
#        `ln` only when it is the command being invoked.
if echo "$SCAN_CMD" | grep -qiE "(^|[;|&] *)ln .* ${TMP_DEST}"; then
    block "Symlinks involving /tmp (ln — either direction) are blocked; /tmp targets dangle after restart. $SCRATCH_HINT"
fi

# 7. SAFETY-SYSTEM TAMPERING (added 2026-07-11)
#    settings.json denies Edit/Write on .claude/hooks/ and .claude/logs/, but
#    shell writes (cp, mv, tee, redirection, sed -i, chmod) bypass those
#    tool-scoped rules — and `Bash(cp *)` is auto-approved. Hook and log
#    changes are USER-ONLY operations: the user edits/copies the files himself,
#    or deliberately lifts the deny. Read access (cat, grep, ls, `bash <hook>`
#    for testing) stays open, as do git index operations (add, update-index)
#    for committing. The mutation verb must start a command segment (^ or after
#    ;|&) so flags like `git update-index --chmod=+x` do NOT false-positive —
#    that workflow must keep working.
#
#    Protected paths extend beyond the original hook/log dirs:
#      - .claude/hooks/ and .claude/logs/  (Edit/Write already denied there)
#      - benchmarks/harness/hooks/         (settings.json registers
#        block-git-writes.sh from there — an active PreToolUse Bash hook)
#      - .claude/settings.json and .claude/settings.local.json — the ROOT OF
#        TRUST. A shell overwrite here could deregister every hook, so shell
#        writes are blocked. The Edit/Write TOOLS deliberately remain usable on
#        settings.json so supported, diff-visible settings edits keep working;
#        only opaque shell writes are blocked.
#
#    PATH-SEPARATOR NORMALIZATION (PSEP): a literal `.claude/hooks` also names
#    the same inode via `.claude//hooks` (repeated slash) and `.claude/./hooks`
#    (dot-segment). Both were probe-confirmed to slip past a single-slash pattern
#    and reach the real hooks dir. PSEP replaces every inter-component `/` with a
#    fragment that tolerates repeated slashes and `./` segments, so the pattern
#    matches every spelling of the same path. We deliberately do NOT collapse
#    `//` in the whole scanned command string (SCAN_CMD) — that would corrupt
#    legitimate `//` in URLs and other arguments; the tolerance is scoped to the
#    protected paths.
PSEP='/+(\./+)*'
PROTECTED_DIRS="(\.claude${PSEP}(hooks|logs)|benchmarks${PSEP}harness${PSEP}hooks|\.claude${PSEP}settings(\.local)?\.json)"

#    Mutation verbs are split into two groups, mirroring the §6c asymmetry
#    (TMP_DEST_END). COPY-VERBS (cp|mv|rsync|install) take a trailing DESTINATION,
#    and a protected path may legitimately appear as the read-direction SOURCE
#    (`cp .claude/settings.json backup.json`, `cp .claude/hooks/x.sh research/`).
#    So copy-verbs match only when the protected path is the destination —
#    end-anchored (protected path + optional filename continuation + optional
#    trailing spaces at end of segment). Source-position protected paths pass.
#    (rsync was previously missing from §7 entirely — it is in §6's list — and is
#    added here in the copy-verb group.)
#      ACCEPTED RESIDUAL: GNU trailing-flag forms like `cp evil.sh .claude/hooks/ -v`
#      evade the end anchor — the same accepted trade-off as live §6c.
#    TARGET-VERBS (rm|ln|dd|tee|touch|truncate|chmod|chown|chattr) take the
#    protected path as the thing they act ON in any argument position, so they
#    keep the match-anywhere form; a source-reading FP for these is negligible.
#
#    RESIDUAL RISK (parallel to §6's documented find/cwd notes): (a)
#    `find ... -exec cp ... .claude/hooks/ \;` is not caught — the verb is not at
#    a command-segment start, the same class as §6's -exec gap; (b) cwd-relative
#    evasion (`cd .claude` in one call, then `cp x hooks/y` in the next) is beyond
#    single-command string-matching — the same residual class as §6.
PROT_DEST_END="(/[^ ;|&<>]*)? *\$"
if echo "$SCAN_CMD" | grep -qE "(^|[;&|]) ?(cp|mv|rsync|install) [^|;&<>]*${PROTECTED_DIRS}${PROT_DEST_END}"; then
    block "Copying/moving (cp/mv/rsync/install) INTO the safety system (.claude/hooks, .claude/logs, benchmarks/harness/hooks, or .claude/settings*.json) via shell bypasses the Edit/Write deny rules (anti-tampering). These changes are user-only — ask the user to apply them. (Reading FROM a protected path — a source-position backup — is allowed.)"
fi

if echo "$SCAN_CMD" | grep -qE "(^|[;&|]) ?(rm|ln|dd|tee|touch|truncate|chmod|chown|chattr) [^|;&<>]*${PROTECTED_DIRS}"; then
    block "Modifying the safety system (.claude/hooks, .claude/logs, benchmarks/harness/hooks, or .claude/settings*.json) via shell (rm/ln/dd/tee/touch/truncate/chmod/chown/chattr) bypasses the Edit/Write deny rules (anti-tampering). These changes are user-only — ask the user to apply them."
fi

if echo "$SCAN_CMD" | grep -qE ">>? ?[^ ]*${PROTECTED_DIRS}"; then
    block "Redirecting output into the safety system (.claude/hooks, .claude/logs, benchmarks/harness/hooks, or .claude/settings*.json) bypasses the Edit/Write deny rules (anti-tampering). These changes are user-only — ask the user to apply them."
fi

#    The sed verb is anchored to a command-segment start (^ or after ;|&),
#    matching the mutation-verb and redirect checks above, so a protected path
#    named in descriptive prose (a `git commit -m` message that mentions
#    `sed -i ... .claude/hooks/`) no longer false-blocks — only a real in-place
#    edit whose `sed` begins a command segment is caught.
#      ACCEPTED RESIDUAL: pipeline-fed forms like `xargs sed -i ... .claude/hooks/f`
#      where the verb is not at a segment start are no longer caught — the same
#      accepted class as the §7 `find -exec` residual documented above.
if echo "$SCAN_CMD" | grep -qE "(^|[;&|]) ?sed [^|;&]*-i[^|;&]*${PROTECTED_DIRS}"; then
    block "In-place editing of the safety system (.claude/hooks, .claude/logs, benchmarks/harness/hooks, or .claude/settings*.json) bypasses the Edit/Write deny rules (anti-tampering). These changes are user-only — ask the user to apply them."
fi

# 8. AD-HOC PACKAGE INSTALLATION (added 2026-07-11)
#    The container environment is defined by the Dockerfile; installing or
#    removing packages at runtime creates unreproducible drift that a rebuild
#    silently reverts — and `Bash(python *)` auto-approves `python -m pip
#    install` today. Add the package to the Dockerfile and rebuild instead.
#    Read-only commands (pip list, pip show, uv --version) and `pip download`
#    (fetch-only, no install) remain allowed.
#
#    Evasions closed this round (all probe-confirmed against the prior draft):
#      - versioned interpreters (`python3.11`) and two-token flags
#        (`python -W ignore -m pip`) — the python matcher now accepts any
#        interpreter spelling and any intervening tokens before `-m pip`.
#      - `pipx run` (fetches+executes an ephemeral package) — added to pipx.
#      - `conda env update` / `conda create` (mutate the environment) — added.
#      - `uv run --with pkg` (implicitly installs pkg for the run) — added.

#    pip/pipx: `pipx run` and `pipx runpip` fetch+execute ephemeral packages, so
#    they join install/uninstall.
if echo "$SCAN_CMD" | grep -qiE '(^|[;&|]) ?(pip3?|pipx) (install|uninstall|run|runpip)\b'; then
    block "Runtime package changes drift from the Dockerfile and vanish on rebuild. Add the package to the Dockerfile and rebuild (exit the container, then run \`bash rebuild_daaf.sh\` from the daaf-docker folder) — preferably in the user additions block near the end of the Dockerfile for a fast rebuild."
fi

#    python -m pip: interpreter may be versioned (`python3.11`) or the `py`
#    launcher, and ANY tokens may sit between it and `-m pip` (`python -W ignore
#    -m pip install`). The theoretical FP — a user script literally named to make
#    `-m pip install` appear as its args (`python myscript.py -m pip install`) —
#    is an accepted edge, far rarer than the evasions this closes.
if echo "$SCAN_CMD" | grep -qiE '\b(python[0-9.]*|py) [^|;&]*-m pip (install|uninstall)\b'; then
    block "Runtime package changes (python -m pip) drift from the Dockerfile and vanish on rebuild. Add the package to the Dockerfile and rebuild (exit the container, then run \`bash rebuild_daaf.sh\` from the daaf-docker folder) — preferably in the user additions block near the end of the Dockerfile for a fast rebuild."
fi

#    uv: pip/add/remove/sync/tool subcommands, plus `uv run --with pkg` which
#    installs pkg into the run's ephemeral environment (checked separately below
#    because --with may trail other `uv run` args).
if echo "$SCAN_CMD" | grep -qiE '(^|[;&|]) ?uv (pip (install|uninstall|sync)|add|remove|sync|tool (install|run))\b'; then
    block "Runtime package changes via uv drift from the Dockerfile and vanish on rebuild. Add the package to the Dockerfile and rebuild (exit the container, then run \`bash rebuild_daaf.sh\` from the daaf-docker folder) — preferably in the user additions block near the end of the Dockerfile for a fast rebuild."
fi

if echo "$SCAN_CMD" | grep -qiE '(^|[;&|]) ?uv run [^|;&]*--with\b'; then
    block "\`uv run --with\` implicitly installs the named package into an ephemeral environment (runtime drift). Add the package to the Dockerfile and rebuild (exit the container, then run \`bash rebuild_daaf.sh\` from the daaf-docker folder) — preferably in the user additions block near the end of the Dockerfile for a fast rebuild."
fi

#    conda: install/remove/update/create, plus `conda env update`/`conda env
#    create` (which mutate or build an environment from a yaml file). uvx and
#    easy_install join here. All three alternatives are grouped under ONE
#    command-segment anchor (^|[;&|]) so a token named in descriptive prose (a
#    `git commit -m` message that lists `easy_install`/`conda install`-type
#    commands) no longer false-blocks — the previous form anchored only the
#    leading uvx alternative, leaving the easy_install/conda branches as bare
#    word-boundary matches that fired on prose.
#      ACCEPTED RESIDUAL: wrapper-prefixed forms (`time conda install x`,
#      `env conda install x`, `nice -n5 easy_install x`) put the verb after a
#      non-separator token and are no longer caught — the same residual class
#      that has always applied to the segment-anchored pip/uv checks above and
#      the §7 mutation verbs (e.g. `time cp ...`), now extended to these two.
if echo "$SCAN_CMD" | grep -qiE '(^|[;&|]) ?(uvx\b|easy_install\b|conda (install|remove|update|create|env (update|create))\b)'; then
    block "Runtime package execution/installation (uvx/easy_install/conda) drifts from the Dockerfile. Add the tool to the Dockerfile and rebuild (exit the container, then run \`bash rebuild_daaf.sh\` from the daaf-docker folder) — preferably in the user additions block near the end of the Dockerfile for a fast rebuild."
fi

#    R package installation (added 2026-07-16). The Python guards above left R
#    completely uncovered: `R CMD INSTALL`, `Rscript -e 'install.packages(...)'`,
#    and the many `remotes`/`devtools`/`pak`/`renv`/`BiocManager` install verbs
#    all created the same unreproducible runtime drift the Dockerfile is meant to
#    prevent. This subsection closes the shell-visible R paths. (The dominant R
#    path — `install.packages()` written INSIDE a `.R` script and executed via
#    scripts/run_with_capture.sh — is invisible to any shell-level hook; it is
#    covered at the wrapper by run_with_capture.sh's pre-execution content scan,
#    and for coding agents additionally by enforce-file-first.sh blocking direct
#    Rscript invocation. This hook covers the command-line R forms.)
#
#    8a. `R CMD INSTALL pkg.tar.gz` — segment-anchored. The R-eval gate in 8b
#        cannot catch this because its install-token set keys on the R-function
#        spellings (`install.packages`, `install_github`, ...), and `CMD INSTALL`
#        is neither — so it needs its own check.
if echo "$SCAN_CMD" | grep -qiE '(^|[;&|]) ?R CMD INSTALL\b'; then
    block "Runtime R package installation (R CMD INSTALL) drifts from the Dockerfile and vanishes on rebuild. Add the package to the Dockerfile and rebuild (exit the container, then run \`bash rebuild_daaf.sh\` from the daaf-docker folder) — preferably in the user additions block near the end of the Dockerfile for a fast rebuild."
fi

#    8b. R-eval installs: an R interpreter invoked at a command-segment start AND
#        an install-family token appearing ANYWHERE in the command. The two
#        conditions are ANDed so that neither alone false-blocks:
#          - The R-invocation gate `(^|[;&|]) ?(Rscript[0-9.]*|R|r)\b` requires
#            Rscript/R/littler-`r` to actually START a command segment. The `\b`
#            keeps `rm`/`rsync`/`render` (r followed by a word char) from matching,
#            and the segment anchor keeps a mid-string ` R ` (e.g. a commit-message
#            word or a `.R` filename argument) from matching.
#          - The install-token set is matched token-anywhere so heredocs and
#            piped one-liners are caught after whitespace normalization:
#            `echo 'install.packages("x")' | R --no-save` collapses to a single
#            line whose `| R` trips the gate and whose `install.packages` trips
#            the token set.
#        Requiring BOTH means a bare `R --version` (gate yes, token no) and a
#        `grep -rn "install.packages" scripts/` or `git commit -m "... in R"`
#        (token yes, gate no — no segment-start R invocation) both pass.
#      ACCEPTED RESIDUALS: (1) token obfuscation via variable expansion or base64
#        (`R -e "$(echo ...)"`) is not decoded by a shell regex — the same class
#        as the §6/§7 cwd/-exec residuals. (2) `R -f script.R` where the install
#        lives in the file is not visible here — covered for coding agents by
#        enforce-file-first.sh and at the wrapper by run_with_capture.sh's scan.
#        (3) HOOK-WIDE residuals shared with the conda block (see the note at the
#        uvx/easy_install/conda check above): wrapper-prefixed invocations
#        (`env Rscript ...`, `time Rscript ...`, `nice Rscript ...`) put the R
#        interpreter after a non-separator token so the segment-start gate does
#        not fire, and a quoted interpreter name (`'Rscript' -e ...`) escapes the
#        bare-word gate — the same evasion class that applies to every
#        segment-anchored §8 check. Both are accepted here; for coding agents
#        enforce-file-first.sh independently blocks these direct-Rscript forms.
R_INSTALL_TOKENS='install\.packages|update\.packages|remove\.packages|install_(github|gitlab|bitbucket|cran|version|local|url|git|svn|bioc|dev)|pkg_install|pak::pak|renv::(install|restore|update|rebuild)|BiocManager::install|biocLite'
if echo "$SCAN_CMD" | grep -qiE '(^|[;&|]) ?(Rscript[0-9.]*|R|r)\b' && echo "$SCAN_CMD" | grep -qiE "$R_INSTALL_TOKENS"; then
    block "Runtime R package installation (install.packages / remotes / devtools / pak / renv / BiocManager, etc.) drifts from the Dockerfile and vanishes on rebuild. Add the package to the Dockerfile and rebuild (exit the container, then run \`bash rebuild_daaf.sh\` from the daaf-docker folder) — preferably in the user additions block near the end of the Dockerfile for a fast rebuild."
fi

# ---------------------------------------------------------------------------
# All checks passed — allow the command
# ---------------------------------------------------------------------------
exit 0
