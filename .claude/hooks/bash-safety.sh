#!/usr/bin/env bash
# bash-safety.sh — PreToolUse hook that blocks dangerous Bash commands
#
# This is the primary safety guardrail for the DAAF environment. It reads
# the tool invocation JSON from stdin and inspects the command field for
# patterns that are destructive, privilege-escalating, or data-exfiltrating.
# It also enforces a provenance boundary (section 6): model-initiated shell
# writes to /tmp are blocked because /tmp is outside the Docker-volume backup
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
#   provenance guard follows the same principle: reading DAAF's own /tmp
#   coordination caches is fine, but *writing* working files to /tmp is blocked.
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

# Normalize: collapse whitespace for more reliable matching
NORM_CMD=$(echo "$CMD" | tr -s '[:space:]' ' ')

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
if echo "$NORM_CMD" | grep -qiE "([0-9]?>>?|[0-9]?>\||&>) *${TMP_DEST}"; then
    block "Output redirection (>, >>, >|, 2>, &>) into /tmp is blocked. $SCRATCH_HINT"
fi

#    6b. tee writing to /tmp — /tmp may appear ANYWHERE in tee's destination
#        list (tee accepts multiple files: `tee a.txt /tmp/x.txt`), so match a
#        /tmp token anywhere in tee's argument run. The [^<|]* stops the match
#        at an input-redirect (`<`) or pipe (`|`) boundary, so the sanctioned
#        `tee /daaf/out.txt < /tmp/input` (write project, read /tmp) still
#        passes and a downstream `| grep /tmp` isn't misread as a tee target.
if echo "$NORM_CMD" | grep -qiE "\btee\b[^<|]* ${TMP_DEST}"; then
    block "Writing to /tmp via tee is blocked. $SCRATCH_HINT"
fi

#    6c. Copy/move/sync/install with a /tmp DESTINATION argument. These take a
#        trailing destination, and /tmp may legitimately appear as the SOURCE
#        (the sanctioned rescue: `cp /tmp/claude-model-x {PROJECT_DIR}/...`).
#        Anchor to end-of-command so only a /tmp *destination* is blocked.
if echo "$NORM_CMD" | grep -qiE "\b(cp|mv|rsync|install)\b.* ${TMP_DEST_END}"; then
    block "Copying/moving (cp/mv/rsync/install) into /tmp is blocked. $SCRATCH_HINT"
fi

#    6d. Directory / file creation in /tmp: mkdir (with flags) and touch.
if echo "$NORM_CMD" | grep -qiE "\bmkdir\b( +-[a-zA-Z]+)* +${TMP_DEST}"; then
    block "Creating directories (mkdir) in /tmp is blocked. $SCRATCH_HINT"
fi

if echo "$NORM_CMD" | grep -qiE "\btouch\b.* ${TMP_DEST}"; then
    block "Creating files (touch) in /tmp is blocked. $SCRATCH_HINT"
fi

#    6e. Downloads written into /tmp: curl -o/--output, wget -O.
if echo "$NORM_CMD" | grep -qiE "\bcurl\b.*(-o|--output) +${TMP_DEST}"; then
    block "Downloading (curl -o) into /tmp is blocked. $SCRATCH_HINT"
fi

if echo "$NORM_CMD" | grep -qiE "\bwget\b.*-O +${TMP_DEST}"; then
    block "Downloading (wget -O) into /tmp is blocked. $SCRATCH_HINT"
fi

#    6f. In-place edits of /tmp files: sed -i.
if echo "$NORM_CMD" | grep -qiE "\bsed\b.* -i[a-zA-Z.]*.* ${TMP_DEST}"; then
    block "Editing /tmp files in place (sed -i) is blocked. $SCRATCH_HINT"
fi

#    6g. Archive extraction into /tmp: unzip -d /tmp, tar -C /tmp.
if echo "$NORM_CMD" | grep -qiE "\bunzip\b.* -d +${TMP_DEST}"; then
    block "Extracting (unzip -d) into /tmp is blocked. $SCRATCH_HINT"
fi

if echo "$NORM_CMD" | grep -qiE "\btar\b.* -C +${TMP_DEST}"; then
    block "Extracting (tar -C) into /tmp is blocked. $SCRATCH_HINT"
fi

#    6h. Cloning a repo into /tmp: git clone ... /tmp/dest.
if echo "$NORM_CMD" | grep -qiE "\bgit +clone\b.* ${TMP_DEST}"; then
    block "Cloning (git clone) into /tmp is blocked. $SCRATCH_HINT"
fi

#    6i. Block-copy into /tmp: dd of=/tmp/... (the write target is `of=`, so a
#        /tmp source in `if=` — the sanctioned read direction — is not matched).
if echo "$NORM_CMD" | grep -qiE "\bdd\b.* of=${TMP_DEST}"; then
    block "Writing to /tmp via dd (of=) is blocked. $SCRATCH_HINT"
fi

#    6j. Truncating/creating /tmp files: truncate.
if echo "$NORM_CMD" | grep -qiE "\btruncate\b.* ${TMP_DEST}"; then
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
if echo "$NORM_CMD" | grep -qiE "(^|[;|&] *)ln .* ${TMP_DEST}"; then
    block "Symlinks involving /tmp (ln — either direction) are blocked; /tmp targets dangle after restart. $SCRATCH_HINT"
fi

# ---------------------------------------------------------------------------
# All checks passed — allow the command
# ---------------------------------------------------------------------------
exit 0
