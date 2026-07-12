#!/bin/bash
# bash-safety.sh — PreToolUse hook that blocks dangerous Bash commands
#
# This is the primary safety guardrail for the DAAF environment. It reads
# the tool invocation JSON from stdin and inspects the command field for
# patterns that are destructive, privilege-escalating, or data-exfiltrating.
# It also enforces safety-system integrity (section 6), Dockerfile-only
# package management (section 7), and a provenance boundary (section 8):
# model-initiated shell writes to /tmp are blocked because /tmp is outside
# the Docker-volume backup boundary and the audit trail.
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
#   provenance guard follows the same principle: reading /tmp coordination
#   caches is fine, but *writing* working files to /tmp is blocked.
#
# Hook event: PreToolUse (matcher: "Bash")
# Registered in: .claude/settings.json

# Fail CLOSED: if anything unexpected goes wrong, block the command.
# This is a security hook — ambiguous failures must not silently allow execution.
trap 'echo "BLOCKED by bash-safety hook: unexpected error in safety check" >&2; exit 2' ERR

# --- Dependency check (fail-closed) ---
# Without jq, we cannot inspect the tool invocation JSON. Failing open here
# would silently bypass ALL safety checks, so we must block. (The `|| VAR=""`
# fallbacks below would otherwise turn a missing jq into a silent allow.)
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

# Normalize: drop backslash line continuations, then collapse whitespace
# for more reliable matching (a continuation would otherwise leave a stray
# backslash token that defeats every single-line pattern below)
NORM_CMD=$(echo "$CMD" | sed 's/\\$//' | tr -s '[:space:]' ' ')

# ---------------------------------------------------------------------------
# block: Print a descriptive error to stderr and exit 2 to block execution
# ---------------------------------------------------------------------------
block() {
    echo "BLOCKED by bash-safety hook: $1" >&2
    exit 2
}

# ---------------------------------------------------------------------------
# Pattern checks — order: most dangerous first
# ---------------------------------------------------------------------------

# 1. DESTRUCTIVE FILESYSTEM OPERATIONS
#    rm -rf with dangerous targets (root, home, current dir, wildcards)
if echo "$NORM_CMD" | grep -qiE 'rm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r)\s+(/|/\*|~|\$HOME|\.\.|\.|\*)'; then
    block "Recursive force-delete targeting dangerous path. Use targeted 'rm' on specific files instead."
fi

# 2. DESTRUCTIVE GIT OPERATIONS
#    Force push — rewrites remote history
if echo "$NORM_CMD" | grep -qiE 'git\s+push\s+.*(-f|--force|--force-with-lease)'; then
    block "Force push rewrites remote history. Use regular 'git push' instead."
fi

#    Hard reset — destroys uncommitted work
if echo "$NORM_CMD" | grep -qiE 'git\s+reset\s+--hard'; then
    block "Hard reset destroys uncommitted changes. Use 'git stash' to save work first."
fi

#    Clean -f — permanently deletes untracked files
if echo "$NORM_CMD" | grep -qiE 'git\s+clean\s+(-[a-z]*f|--force)'; then
    block "git clean -f permanently deletes untracked files. Review with 'git clean -n' first."
fi

#    Checkout . or restore . — discards all working changes
if echo "$NORM_CMD" | grep -qiE 'git\s+(checkout|restore)\s+\.'; then
    block "This discards all working directory changes. Use 'git stash' to save work first."
fi

#    Branch force-delete
if echo "$NORM_CMD" | grep -qiE 'git\s+branch\s+-D'; then
    block "Force-deleting a branch is irreversible. Use 'git branch -d' (safe delete) instead."
fi

# 3. PRIVILEGE ESCALATION
if echo "$NORM_CMD" | grep -qiE '(^|\s|;|&&|\|\|)sudo\s'; then
    block "Privilege escalation via sudo is not permitted in this environment."
fi

if echo "$NORM_CMD" | grep -qiE '(^|\s|;|&&|\|\|)su\s'; then
    block "Switching user via su is not permitted in this environment."
fi

if echo "$NORM_CMD" | grep -qiE 'chmod\s+(777|u\+s)'; then
    block "Setting world-writable (777) or setuid permissions is not permitted."
fi

# 4. DANGEROUS NETWORK PATTERNS
#    Pipe-to-shell — arbitrary remote code execution
if echo "$NORM_CMD" | grep -qiE '(curl|wget)\s+.*\|\s*(bash|sh|zsh|dash|source)'; then
    block "Piping downloaded content to a shell is arbitrary code execution. Download first, review, then execute."
fi

#    File exfiltration — uploading local files to arbitrary URLs
if echo "$NORM_CMD" | grep -qiE 'curl\s+.*(-d\s*@|-F\s*.*=@|--data-binary\s*@|--data\s*@|--upload-file)'; then
    block "Uploading local files via curl is a data exfiltration risk. Review the file and destination first."
fi

# 5. CONTAINER ESCAPE ATTEMPTS
if echo "$NORM_CMD" | grep -qiE '(^|\s|;|&&|\|\|)docker\s+run'; then
    block "Running nested Docker containers is not permitted in this environment."
fi

if echo "$NORM_CMD" | grep -qiE '(^|\s|;|&&|\|\|)(mount|chroot)\s'; then
    block "Filesystem mount/chroot is not permitted in this environment."
fi

# 6. SAFETY-SYSTEM TAMPERING (added 2026-07-11)
#    settings.json denies Edit/Write on .claude/hooks/ and .claude/logs/,
#    but shell writes (cp, mv, tee, redirection, sed -i, chmod) would
#    bypass those rules. Hook and log changes are USER-ONLY operations:
#    the user edits/copies the files himself, or deliberately lifts the
#    deny. Read access (cat, grep, ls, bash <hook> for testing) stays open,
#    as do git index operations (add, update-index) for committing.
#    The mutation verb must start a command segment (^ or after ;|&) so
#    flags like `git update-index --chmod=+x` don't false-positive.
if echo "$NORM_CMD" | grep -qE '(^|[;&|]) ?(cp|mv|rm|ln|install|dd|tee|touch|truncate|chmod|chown|chattr) [^|;&<>]*\.claude/(hooks|logs)'; then
    block "Writing to .claude/hooks or .claude/logs via shell bypasses the Edit/Write deny rules (anti-tampering). These changes are user-only — ask the user to apply them."
fi

if echo "$NORM_CMD" | grep -qE '>>? ?[^ ]*\.claude/(hooks|logs)'; then
    block "Redirecting output into .claude/hooks or .claude/logs bypasses the Edit/Write deny rules (anti-tampering). These changes are user-only — ask the user to apply them."
fi

if echo "$NORM_CMD" | grep -qE '\bsed [^|;&]*-i[^|;&]*\.claude/(hooks|logs)'; then
    block "In-place editing of .claude/hooks or .claude/logs bypasses the Edit/Write deny rules (anti-tampering). These changes are user-only — ask the user to apply them."
fi

# 7. AD-HOC PACKAGE INSTALLATION (added 2026-07-11)
#    The container environment is defined by the Dockerfile; installing or
#    removing packages at runtime creates unreproducible drift that a
#    rebuild silently reverts. Add the package to the Dockerfile and
#    rebuild (scripts/host/rebuild.sh) instead. Read-only commands
#    (pip list, pip show, uv --version) remain allowed.
if echo "$NORM_CMD" | grep -qiE '(^|[;&|]) ?(pip3?|pipx) (install|uninstall)\b'; then
    block "Runtime package changes drift from the Dockerfile and vanish on rebuild. Add the package to the Dockerfile and rebuild via scripts/host/rebuild.sh."
fi

if echo "$NORM_CMD" | grep -qiE '\bpython3? (-[^ ]+ )*-m pip (install|uninstall)\b'; then
    block "Runtime package changes (python -m pip) drift from the Dockerfile and vanish on rebuild. Add the package to the Dockerfile and rebuild via scripts/host/rebuild.sh."
fi

if echo "$NORM_CMD" | grep -qiE '(^|[;&|]) ?uv (pip (install|uninstall|sync)|add|remove|sync|tool (install|run))\b'; then
    block "Runtime package changes via uv drift from the Dockerfile and vanish on rebuild. Add the package to the Dockerfile and rebuild via scripts/host/rebuild.sh."
fi

if echo "$NORM_CMD" | grep -qiE '(^|[;&|]) ?uvx\b|\beasy_install\b|\bconda (install|remove|update)\b'; then
    block "Runtime package execution/installation (uvx/easy_install/conda) drifts from the Dockerfile. Add the tool to the Dockerfile and rebuild via scripts/host/rebuild.sh."
fi

# 8. PROVENANCE BOUNDARY — /tmp WRITES (ported from DAAF 2026-07-11)
#    /tmp is outside the Docker-volume backup boundary and the audit trail.
#    Agents that write working files there lose them silently on container
#    restart, and backups never capture them. The correct home for any
#    temporary or intermediate file is scratch/ inside the project, which
#    IS backed up and audited.
#
#    This guard is deliberately WRITE-OPERATOR-GATED: it matches only shell
#    operations that *write into* /tmp, never bare /tmp string presence.
#    Reads (cat, ls, head, tail, grep, jq, stat, wc, ... on /tmp paths) must
#    pass, because hooks and statuslines legitimately cache coordination
#    state in /tmp and agents sometimes read those caches via Bash. Reading
#    /tmp and redirecting the output INTO the project is the sanctioned
#    rescue pattern and must pass.
#
#    ACCEPTED RESIDUAL GAPS (covered by the instruction layer — CLAUDE.md
#    Safety Model > Provenance Boundary — not by this shell hook):
#      - Program-argument writes, where /tmp is passed as an argument to a
#        program that writes there internally (e.g. `python x.py /tmp/out/`).
#      - `find ... -exec <writer> ... /tmp/ ... \;` spawned subcommands.
#    The CLAUDE.md prohibition and the settings.json Write/Edit(//tmp/**)
#    deny rules are the compensating controls.
SCRATCH_HINT="Working files belong inside the project (use scratch/), not /tmp — /tmp is outside the backup and audit boundary."

#    A /tmp destination token: /tmp followed by a slash-path, or bare /tmp at a
#    word boundary (end of string, space, or shell metacharacter).
TMP_DEST='/tmp(/[^ ;|&<>]*)?([ ;|&<>]|$)'

#    Destination-ANCHORED variant: the /tmp token must be the trailing path
#    argument. Used for commands where /tmp may appear as EITHER source or
#    destination — cp/mv/rsync/install. Matches `cp f /tmp/x` (dest is /tmp →
#    block) but not `cp /tmp/x f` (source is /tmp, dest is project → rescue).
TMP_DEST_END='/tmp(/[^ ;|&<>]*)? *$'

#    8a. Output redirection into /tmp: >, >>, 2>, &>, 1>, >|
if echo "$NORM_CMD" | grep -qiE "([0-9]?>>?|[0-9]?>\||&>) *${TMP_DEST}"; then
    block "Output redirection (>, >>, >|, 2>, &>) into /tmp is blocked. $SCRATCH_HINT"
fi

#    8b. tee writing to /tmp — /tmp may appear anywhere in tee's destination
#        list; [^<|]* stops at an input-redirect or pipe boundary so
#        `tee project/out.txt < /tmp/input` still passes.
if echo "$NORM_CMD" | grep -qiE "\btee\b[^<|]* ${TMP_DEST}"; then
    block "Writing to /tmp via tee is blocked. $SCRATCH_HINT"
fi

#    8c. Copy/move/sync/install with a /tmp DESTINATION argument (trailing).
if echo "$NORM_CMD" | grep -qiE "\b(cp|mv|rsync|install)\b.* ${TMP_DEST_END}"; then
    block "Copying/moving (cp/mv/rsync/install) into /tmp is blocked. $SCRATCH_HINT"
fi

#    8d. Directory / file creation in /tmp: mkdir (with flags) and touch.
if echo "$NORM_CMD" | grep -qiE "\bmkdir\b( +-[a-zA-Z]+)* +${TMP_DEST}"; then
    block "Creating directories (mkdir) in /tmp is blocked. $SCRATCH_HINT"
fi

if echo "$NORM_CMD" | grep -qiE "\btouch\b.* ${TMP_DEST}"; then
    block "Creating files (touch) in /tmp is blocked. $SCRATCH_HINT"
fi

#    8e. Downloads written into /tmp: curl -o/--output, wget -O.
if echo "$NORM_CMD" | grep -qiE "\bcurl\b.*(-o|--output) +${TMP_DEST}"; then
    block "Downloading (curl -o) into /tmp is blocked. $SCRATCH_HINT"
fi

if echo "$NORM_CMD" | grep -qiE "\bwget\b.*-O +${TMP_DEST}"; then
    block "Downloading (wget -O) into /tmp is blocked. $SCRATCH_HINT"
fi

#    8f. In-place edits of /tmp files: sed -i.
if echo "$NORM_CMD" | grep -qiE "\bsed\b.* -i[a-zA-Z.]*.* ${TMP_DEST}"; then
    block "Editing /tmp files in place (sed -i) is blocked. $SCRATCH_HINT"
fi

#    8g. Archive extraction into /tmp: unzip -d /tmp, tar -C /tmp.
if echo "$NORM_CMD" | grep -qiE "\bunzip\b.* -d +${TMP_DEST}"; then
    block "Extracting (unzip -d) into /tmp is blocked. $SCRATCH_HINT"
fi

if echo "$NORM_CMD" | grep -qiE "\btar\b.* -C +${TMP_DEST}"; then
    block "Extracting (tar -C) into /tmp is blocked. $SCRATCH_HINT"
fi

#    8h. Cloning a repo into /tmp: git clone ... /tmp/dest.
if echo "$NORM_CMD" | grep -qiE "\bgit +clone\b.* ${TMP_DEST}"; then
    block "Cloning (git clone) into /tmp is blocked. $SCRATCH_HINT"
fi

#    8i. Block-copy into /tmp: dd of=/tmp/... (a /tmp source in if= is the
#        sanctioned read direction and is not matched).
if echo "$NORM_CMD" | grep -qiE "\bdd\b.* of=${TMP_DEST}"; then
    block "Writing to /tmp via dd (of=) is blocked. $SCRATCH_HINT"
fi

#    8j. Truncating/creating /tmp files: truncate.
if echo "$NORM_CMD" | grep -qiE "\btruncate\b.* ${TMP_DEST}"; then
    block "Truncating/creating /tmp files (truncate) is blocked. $SCRATCH_HINT"
fi

#    8k. Symlinks involving /tmp — blocked in BOTH directions (link in /tmp,
#        or project link to a /tmp target that dangles after restart).
#        `ln` is anchored to COMMAND-START position — it is only two chars
#        and appears inside common flags (`ls -ln /tmp`); a bare word
#        boundary would false-block those reads.
if echo "$NORM_CMD" | grep -qiE "(^|[;|&] *)ln .* ${TMP_DEST}"; then
    block "Symlinks involving /tmp (ln — either direction) are blocked; /tmp targets dangle after restart. $SCRATCH_HINT"
fi

# ---------------------------------------------------------------------------
# All checks passed — allow the command
# ---------------------------------------------------------------------------
exit 0
