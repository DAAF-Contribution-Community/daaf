#!/usr/bin/env bash
# enforce-single-command.sh — PreToolUse hook that blocks command chaining
#
# Enforces the CLAUDE.md rule: "Every Bash tool call must contain exactly
# one command. No &&, ;, or || chaining."
#
# This prevents chained commands from bypassing safety hooks and permission
# checks that evaluate each Bash call individually. Claude Code evaluates a
# Bash tool call as a unit; a chain lets a second, unvetted command ride along
# behind a first one that looks benign.
#
# ---------------------------------------------------------------------------
# DETECTION STRATEGY (in order)
# ---------------------------------------------------------------------------
#   1. Strip `#` comments. A `#` that begins a word in normal (unquoted) state
#      ends its physical line. Runs FIRST so that a `<<` or an operator that
#      lives only inside a comment cannot steer later steps.
#   2. Remove heredoc bodies, quote-aware. `<<` opens a heredoc only when the
#      walker is outside single/double quotes, is not looking at `<<<` (a
#      here-string), and is not inside `$(( … ))`. Closing-delimiter lines are
#      compared with a trailing `\r` stripped (CRLF-originated text) and with
#      leading whitespace stripped. Multiple heredocs on one line (`cat <<A
#      <<B`) are queued and closed in order. `<<-` is supported.
#   3. Collapse line continuations (backslash immediately before newline).
#   4. Drop whitespace-only lines (they carry no command and would otherwise
#      become spurious `;` separators in step 5).
#   5. Convert remaining newlines to `;` so they are caught as separators.
#   6. Scan with a quote-aware, nesting-aware awk state machine that tracks
#      single/double quote state, `()`/`[]` nesting depth, and backslash
#      escapes, flagging operators only at the top level.
#   7. Recurse into shell-carrier bodies. A quoted span whose preceding token
#      is `eval`, `source`, or `.`, or a `-…c` flag whose own preceding token
#      is a shell (`bash sh zsh dash ksh mksh busybox`, with or without a
#      leading path), is extracted and run through the SAME scan (bounded to
#      3 levels). `python3 -c "a; b"` is NOT a carrier and stays allowed.
#
# OPERATORS FLAGGED at top level: `&&`, `||`, `;`, and a lone `&`.
#
# EXCEPTIONS (all deliberate, all covered by tests/bash/enforce_single_command.bats):
#   - `;` is allowed when the command begins with a compound keyword (for,
#     while, until, if, elif, case, select) — there `;` is syntax, not
#     chaining. The same exemption applies inside a carrier body.
#   - A lone `&` is NOT chaining when it is part of `&&` (handled as AND),
#     `&>` / `&>>` (redirect), `>&` / `<&` / `N>&M` (fd duplication), `|&`
#     (pipe), or when only whitespace and `;` follow it (a trailing background
#     `&` chains nothing).
#   - Trailing `;` (nothing but whitespace/`;` after it) is not chaining.
#   - Operators inside quotes, inside `$( )` / `(( ))` / `[[ ]]` / `[ ]`, or
#     backslash-escaped, are ignored.
#   - Pipes (`|`) are allowed outright: a pipeline is one command by the
#     one-command rule, and every stage is visible to the safety hooks.
#
# ---------------------------------------------------------------------------
# KNOWN RESIDUALS (accepted, documented, NOT defects to be silently fixed)
# ---------------------------------------------------------------------------
#   R1. Whole-command compound exemption. Once a command STARTS with a
#       compound keyword, every top-level `;` in it is exempt — so
#       `for i in 1; do :; done; rm x` is allowed. Scoping the exemption to
#       the construct requires command-position keyword-depth tracking
#       (open on for/while/until/if/case, close on done/fi/esac) and was
#       deferred for false-positive risk (`echo done` must not close).
#   R2. Bare subshell / brace groups at top level are not scanned:
#       `(echo a; echo b)` and `(cd x && make)` are allowed because `(` raises
#       nesting depth, which is what makes `$( )` arguments safe. Separating
#       the two requires distinguishing `$(`/`<(`/`((` from a bare `(` at
#       command position; deferred for false-positive risk.
#   R3. `$(a; b)` computed arguments are by design ONE command with a computed
#       argument, and stay allowed (this is the behavior R2 protects).
#   R4. `|&` is a pipe (stdout+stderr), and pipes are allowed by the
#       one-command rule.
#   R5. Heredocs are not re-detected inside a carrier body. `#` comments ARE
#       stripped there (step 7 applies step 1 to the body before scanning),
#       but `bash -c "cat <<EOF …"` has its body scanned as ordinary text.
#       This errs toward scanning MORE, so it can only produce a false
#       positive, never a missed chain.
#   R6. `ssh host 'a && b'` stays allowed. This hook's carrier set is the local
#       shell set (`bash sh zsh dash ksh mksh busybox`), so a remote command
#       body is not decomposed and its chain is not counted. bash-safety.sh
#       takes the opposite view — its stage-0c carrier list DOES include `ssh`
#       (any quoted span to the right of an `ssh` token is promoted), because
#       there the question is "can this text execute?" rather than "how many
#       commands does this Bash call run HERE?". The asymmetry is deliberate:
#       the one-command rule exists so each LOCAL command is independently
#       vetted by the local hooks, and a remote chain is outside that scope.
#   R7. [2026-09-27, Phase 4 component review N4] A single, well-formed JSON
#       object whose `tool_name` is not the STRING "Bash" is allowed unscanned,
#       whatever its `tool_input.command` holds. The one-object stdin gate
#       checks only that stdin is exactly one object; it does not check the
#       TYPE of `tool_name`. An array (`["Bash"]`), an object, `null`, a number,
#       or a missing key makes `jq -r '.tool_name // empty'` print something
#       other than exactly `Bash` (or nothing), and the `!= "Bash"` gate reads
#       that as "not a Bash call" (probe: scripts/scratch/hf2_n4_probe.sh in the
#       2026-09-18 workspace — rows N4A/N4O/N4N/N4I/N4M exit 0 on this file and
#       on the 2026-09-26 install, N4S with the string exits 2). Accepted
#       because Claude Code always sends `tool_name` as a string; a payload with
#       any other type is not a real Bash call reaching this hook (inference
#       from the hook input contract, not a harness test). Closing it would be
#       one more clause in the stdin gate's jq test (`(.[0].tool_name | type) ==
#       "string"`), deliberately not done in `_a`, which stays purely additive
#       to the installed file. Pinned as ALLOW today in both regression suites.
#
# ---------------------------------------------------------------------------
# FAILURE POSTURE
# ---------------------------------------------------------------------------
#   - Fail-CLOSED on unexpected shell errors (ERR trap → exit 2), on a missing
#     `jq`, and on empty input.
#   - Fail-OPEN on unrecognized scanner output (the `*)` case). This is a
#     CONVENTION hook, not a security boundary — `bash-safety.sh` is the
#     security layer — so a scanner bug must not block all Bash usage. The
#     heredoc stripper, by contrast, must never be able to HIDE a chain; that
#     is why step 2 is quote-aware (see the SML2 evasion in
#     research/2026-09-18_FrameworkDev_SafetyHookHardening/).
#
# Fail-closed input posture [2026-09-26]: the hook BLOCKS (exit 2) when jq is
# missing, when stdin is empty, and when stdin is not exactly one JSON object
# (unparseable text, whitespace only, a bare scalar or array, or several
# concatenated JSON values). Previously anything that was not one object made
# `jq -r .tool_name` yield "" or several lines, so the `!= "Bash"` gate read
# "not a Bash call" and ALLOWED -- contradicting the fail-closed contract
# above. The concrete case: a benign object followed by a Bash object with a
# chained command yields TOOL_NAME="Read<newline>Bash" (or "Bash<newline>Bash"),
# so the chain was never scanned. Claude Code sends exactly one JSON object per
# hook call, so this gate is defense-in-depth and is not expected to fire on
# real traffic. Credit: the 2026-09-24 hook-maintenance session found this
# class in enforce-file-first.sh
# (research/2026-09-24_FrameworkDev_ClaudeCode_Upgrade_2.1.281/hook_patches/enforce-file-first.diff);
# the same jq test is applied here (only the hook name in the message
# differs). Pinned by the "(NEW 2026-09-26)" cases in both regression suites.
#
# Exit codes (Claude Code PreToolUse convention):
#   0 = allow the command to proceed
#   2 = BLOCK the command (stderr message shown to the model)
#
# NOTE: settings.json gives this hook a 5 s timeout and a timed-out command
# hook ALLOWS the tool call (Anthropic hooks docs). All processing is linear
# in command length; tests/bash/enforce_single_command.bats asserts a 20 kB
# command and a 500-line heredoc complete in under 2 s.
#
# Dependencies: bash, awk, sed, tr, jq (no new dependencies vs. the 2026-07
# version).
#
# Hook event: PreToolUse (matcher: "Bash")
# Registered in: .claude/settings.json

# Fail CLOSED: if anything unexpected goes wrong, block the command.
# This is a safety-adjacent hook — ambiguous failures must not silently allow.
trap 'echo "BLOCKED by enforce-single-command hook: unexpected error in chain detection" >&2; exit 2' ERR

# --- Dependency check (fail-closed) ---
if ! command -v jq &>/dev/null; then
    echo "BLOCKED by enforce-single-command hook: jq is not installed (required for hook)" >&2
    exit 2
fi

INPUT=$(cat)

# --- Empty input guard (fail-closed) ---
if [[ -z "$INPUT" ]]; then
    echo "BLOCKED by enforce-single-command hook: received empty input (expected JSON)" >&2
    exit 2
fi

# --- Fail-closed on malformed input ---
# INTENT: anything other than exactly one JSON object (non-JSON text, a
#   scalar/array, whitespace only, concatenated values) must not reach the
#   `!= "Bash"` allow gate below, where a failed or multi-line TOOL_NAME reads
#   as "not a Bash call" and ALLOWS.
# REASONING: `-s` slurps every value on stdin into one array so the count can
#   be checked; `-e` makes jq exit non-zero on a false result, and a parse
#   error is non-zero too. Runs inside `if !`, so the ERR trap does not fire.
# ASSUMES: Claude Code always sends exactly one object (see header,
#   "Fail-closed input posture"), so this should never block real traffic.
#   The gate does NOT check the type of `tool_name`: a non-string value passes
#   here and then ALLOWS at the `!= "Bash"` gate (Known Residual R7).
if ! printf '%s' "$INPUT" | jq -e -s 'length == 1 and (.[0] | type == "object")' >/dev/null 2>&1; then
    echo "BLOCKED by enforce-single-command hook: stdin is not a single JSON object (malformed hook input)" >&2
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
# block: Print a descriptive error to stderr and exit 2
# ---------------------------------------------------------------------------
block() {
    cat >&2 <<ENDBLOCK
BLOCKED by enforce-single-command hook: $1

DAAF requires exactly one command per Bash tool call.
Split chained commands into separate Bash calls:

  Wrong:  mkdir -p /path && cp file /path
  Right:  Two separate Bash calls, each with one command

This rule ensures each command is independently evaluated by safety hooks
and permission checks. See CLAUDE.md § "One Command Per Call".
ENDBLOCK
    exit 2
}

# ---------------------------------------------------------------------------
# Shared awk function: strip_comments(s)
#
# INTENT: remove `#`-to-end-of-line comments so that operators mentioned in a
#   comment are not read as chaining (item 14 / case SFP1:
#   `echo hi # this && that` was a false positive).
# REASONING: defined once here and injected into BOTH awk programs below (the
#   pre-processing pass and the scanner's carrier recursion) so the two can
#   never drift apart. A `#` is only a comment when it BEGINS a word in normal
#   state — bash treats `echo a#b` as a literal `a#b`, and `#` inside quotes is
#   data.
# ASSUMES: `sq` is defined in the including awk program as a single-quote
#   character (awk has no clean literal-single-quote syntax inside a
#   single-quoted shell string).
# NOTE ON COST: the function accumulates output by SLICE, not character by
#   character, so a 20 kB command costs O(n) string work rather than O(n^2).
#   This matters because a hook that exceeds its 5 s timeout ALLOWS the call.
# ---------------------------------------------------------------------------
read -r -d '' AWK_STRIP_COMMENTS <<'AWKFN' || true
function strip_comments(s,   out, i, j, n, c, st, esc, wstart, segstart) {
    out = ""; segstart = 1; st = 0; esc = 0; wstart = 1
    n = length(s)
    for (i = 1; i <= n; i++) {
        c = substr(s, i, 1)
        if (esc)          { esc = 0; wstart = 0; continue }
        if (st == 1)      { if (c == sq) st = 0; continue }
        if (st == 2)      { if (c == "\\") esc = 1; else if (c == "\"") st = 0; continue }
        if (c == "\\")    { esc = 1; wstart = 0; continue }
        if (c == sq)      { st = 1; wstart = 0; continue }
        if (c == "\"")    { st = 2; wstart = 0; continue }
        if (c == "#" && wstart) {
            # Word-initial # in normal state: drop through end of physical line.
            out = out substr(s, segstart, i - segstart)
            j = i
            while (j <= n && substr(s, j, 1) != "\n") j++
            segstart = j          # keep the newline itself (line structure matters)
            i = j - 1
            wstart = 1
            continue
        }
        # A word can begin after whitespace or after any of these separators.
        if (c == " " || c == "\t" || c == "\n" || c == ";" || c == "&" || c == "|" || c == "(" || c == "{")
            wstart = 1
        else
            wstart = 0
    }
    out = out substr(s, segstart)
    return out
}
AWKFN

# ---------------------------------------------------------------------------
# PRE-PROCESSING
# ---------------------------------------------------------------------------

# 1. Strip `#` comments (see AWK_STRIP_COMMENTS above).
#    INTENT: item 14. Runs FIRST so a `<<` that exists only inside a comment
#    (`echo hi # <<EOF`) cannot make step 2 swallow the following lines.
PROCESSED=$(printf '%s\n' "$CMD" | awk -v sq="'" "
$AWK_STRIP_COMMENTS
BEGIN { buf = \"\"; first = 1 }
{ if (first) { buf = \$0; first = 0 } else { buf = buf \"\n\" \$0 } }
END { printf \"%s\", strip_comments(buf) }
")

# 2. Strip heredoc bodies, QUOTE-AWARE.
#
#    INTENT (item 8): keep the line containing `<<DELIM` but remove the body
#      through the closing delimiter line, so that prose or data inside a
#      heredoc is not mistaken for chained commands.
#    WHAT THIS CLOSES: the previous version matched `<<` ANYWHERE on a line,
#      including inside quotes. `echo "x <<EOF"` followed by `rm a; rm b`
#      (case SML2) therefore treated line 2 as a heredoc body and never
#      scanned the chain — a scan EVASION, not a convention gap. The walker
#      below only opens a heredoc when it is outside single/double quotes.
#    ALSO CLOSED: `<<<` here-strings are no longer read as heredoc openers;
#      `<<` inside `$(( … ))` (a left-shift) is ignored; a closing delimiter
#      line with a trailing `\r` now terminates the body (the CRLF regression
#      case pinned by qwen-code issue #10446, quoted in
#      output/preliminary_notes/2026-09-18_research_guardfall-and-data-vs-code.md §4).
#    ASSUMES: quote state and the escape flag carry ACROSS lines, because a
#      double-quoted string may legitimately span newlines.
#    CONSERVATIVE BIAS: when a delimiter cannot be parsed, no heredoc is
#      opened — the lines stay in the text and get SCANNED. Unterminated
#      heredocs consume the remainder only when the opener was genuinely
#      outside quotes, which is the only way a delimiter is ever queued.
#      Leading whitespace is stripped before every delimiter comparison (not
#      only for `<<-`); that is looser than bash but errs toward CLOSING the
#      body early, i.e. toward scanning more text, not less.
PROCESSED=$(printf '%s\n' "$PROCESSED" | awk -v sq="'" '
BEGIN { st = 0; esc = 0; arith = 0; nq = 0 }
{
    line = $0

    # --- Inside one or more pending heredoc bodies: drop lines until closed ---
    if (nq > 0) {
        t = line
        sub(/\r$/, "", t)            # CRLF-originated delimiter line
        sub(/^[ \t]+/, "", t)        # <<- (and, deliberately, plain <<)
        if (t == dq[1]) {
            for (k = 1; k < nq; k++) dq[k] = dq[k + 1]
            nq--
        }
        next                         # body lines are data, never scanned
    }

    # --- Normal line: walk it for heredoc openers, carrying quote state ---
    n = length(line)
    for (i = 1; i <= n; i++) {
        c = substr(line, i, 1)
        if (esc)       { esc = 0; continue }
        if (st == 1)   { if (c == sq) st = 0; continue }
        if (st == 2)   { if (c == "\\") esc = 1; else if (c == "\"") st = 0; continue }
        if (c == "\\") { esc = 1; continue }
        if (c == sq)   { st = 1; continue }
        if (c == "\"") { st = 2; continue }

        # $(( … )) arithmetic: << there is a left shift, not a heredoc.
        if (c == "$" && substr(line, i + 1, 2) == "((") { arith++; i += 2; continue }
        if (arith > 0) {
            if (substr(line, i, 2) == "))") { arith--; i++ }
            continue
        }

        if (c == "<" && substr(line, i + 1, 1) == "<") {
            if (substr(line, i + 2, 1) == "<") { i += 2; continue }   # <<< here-string
            j = i + 2
            if (substr(line, j, 1) == "-") j++                        # <<- form
            while (substr(line, j, 1) == " " || substr(line, j, 1) == "\t") j++
            qc = substr(line, j, 1)
            d = ""
            if (qc == sq || qc == "\"") {
                j++
                while (j <= n && substr(line, j, 1) != qc) { d = d substr(line, j, 1); j++ }
                j++                                                   # past closing quote
            } else {
                while (j <= n && substr(line, j, 1) ~ /[A-Za-z0-9_.-]/) { d = d substr(line, j, 1); j++ }
            }
            # Multiple heredocs on one line (cat <<A <<B) queue in order.
            if (d != "") { nq++; dq[nq] = d }
            i = j - 1
            continue
        }
    }
    print line
}
')

# 3. Collapse line continuations (backslash immediately before newline)
PROCESSED=$(printf '%s' "$PROCESSED" | sed -z 's/\\\n/ /g')

# 4. Drop whitespace-only lines.
#    INTENT: a blank line is not a command, so it must not become a separator
#      in step 5. Without this, `# comment` on line 1 (emptied by step 1)
#      followed by `echo a` produced `;echo a` and read as chaining.
#    REASONING: a line with no non-whitespace content cannot hide a chain, so
#      removing it is monotone-safe.
PROCESSED=$(printf '%s' "$PROCESSED" | awk 'NF > 0')

# 5. Convert remaining newlines to ; so they are caught as command separators.
#    Trailing newlines become trailing ; which the scanner ignores (it checks
#    whether non-whitespace content follows a ;).
PROCESSED=$(printf '%s' "$PROCESSED" | tr '\n' ';')

# ---------------------------------------------------------------------------
# SCAN for top-level operators using an awk state machine
#
# Tracks quote state, backslash escapes, and ()/[] nesting depth. Only flags
# operators found at the top level (outside quotes, outside parens/brackets).
#
# The -v sq="'" trick passes a single-quote character as an awk variable,
# avoiding the bash quoting nightmare of embedding literal single quotes
# inside a single-quoted awk program.
#
# Returns one of: "AND", "OR", "SEMI", "AMP", "OK"
# ---------------------------------------------------------------------------
SCAN_RESULT=$(printf '%s' "$PROCESSED" | awk -v sq="'" -v maxdepth=3 "
$AWK_STRIP_COMMENTS
"'
# is_carrier: does a quoted span sit in shell-CODE position?
#
# INTENT (item 13): `bash -c "echo a && echo b"` and `eval "echo a; echo b"`
#   chain two commands behind one tool call (cases SBY9, SBY10). The body is
#   shell code, so it must face the same scan as the outer command.
# REASONING: p1 is the token immediately before the span, p2 the one before
#   that. A `-…c` flag (covers -c, -ec, -lc, and xargs ... sh -c) whose owner
#   is a shell name makes the span code. A leading path is stripped so
#   /bin/bash -c is caught too. `python3 -c` / `awk` / `jq` are NOT carriers,
#   which is what keeps SFP3 and SFP9 allowed.
# ASSUMES: wrappers (env, command, exec, nohup, setsid, time, nice,
#   timeout N) sit to the LEFT of the shell name and therefore do not change
#   p1/p2 — `timeout 5 bash -c "…"` still presents p1="-c", p2="bash".
function is_carrier(p1, p2,   base) {
    if (p1 == "eval" || p1 == "source" || p1 == ".") return 1
    if (p1 ~ /^-[A-Za-z]*c$/) {
        base = p2
        sub(/^.*\//, "", base)
        if (base == "bash" || base == "sh" || base == "zsh" || base == "dash" ||
            base == "ksh" || base == "mksh" || base == "busybox") return 1
    }
    return 0
}

# starts_compound: does this text begin with a compound-command keyword?
# Used for the `;`-is-syntax exemption inside carrier bodies, mirroring the
# top-level exemption applied in the case statement below.
function starts_compound(s,   t) {
    t = s
    sub(/^[ \t\n;]+/, "", t)
    return (t ~ /^(for|while|until|if|elif|case|select)([ \t\n(]|$)/)
}

# handle_span: a quoted span just closed at top level — recurse if it is code.
function handle_span(body, d, p1, p2,   r) {
    if (d + 1 > maxdepth) return "OK"         # bounded recursion (3 levels)
    if (!is_carrier(p1, p2)) return "OK"
    r = scan(strip_comments(body), d + 1)
    if (r == "SEMI" && starts_compound(body)) return "OK"
    return r
}

# scan: the operator state machine. Returns AND / OR / SEMI / AMP / OK.
function scan(s, d,   i, n, c, c2, prevc, st, dep, esc, curw, p1, p2, pp1, pp2, spanstart, body, r, rest) {
    st = 0; dep = 0; esc = 0; curw = ""; p1 = ""; p2 = ""; spanstart = 0
    n = length(s)
    for (i = 1; i <= n; i++) {
        c = substr(s, i, 1)

        # --- Escaped character: consumed as literal text ---
        if (esc) { esc = 0; continue }

        # --- Single-quote state: no escaping; only a matching quote ends it ---
        if (st == 1) {
            if (c == sq) {
                st = 0
                body = substr(s, spanstart, i - spanstart)
                if (dep == 0) { r = handle_span(body, d, pp1, pp2); if (r != "OK") return r }
                curw = curw "Q"
            }
            continue
        }

        # --- Double-quote state: backslash escapes; a quote ends it ---
        if (st == 2) {
            if (c == "\\") { esc = 1; continue }
            if (c == "\"") {
                st = 0
                body = substr(s, spanstart, i - spanstart)
                if (dep == 0) { r = handle_span(body, d, pp1, pp2); if (r != "OK") return r }
                curw = curw "Q"
            }
            continue
        }

        # --- Normal state ---
        if (c == "\\") { esc = 1; continue }
        if (c == sq || c == "\"") {
            st = (c == sq) ? 1 : 2
            spanstart = i + 1
            # Token before the span: an attached form (bash -c"…") leaves the
            # flag in curw, a detached form (bash -c "…") has already flushed it.
            pp1 = (curw != "") ? curw : p1
            pp2 = (curw != "") ? p1   : p2
            continue
        }

        # Word boundary: flush the current word into the p1/p2 history.
        if (c == " " || c == "\t") {
            if (curw != "") { p2 = p1; p1 = curw; curw = "" }
            continue
        }

        # Track nesting: ( ) [ ]
        # Covers $(), (( )), [[ ]], [ ], and (residual R2) bare subshells.
        if (c == "(" || c == "[") { dep++; curw = ""; continue }
        if (c == ")" || c == "]") { if (dep > 0) dep--; curw = ""; continue }

        # Only check operators at top level (depth 0, normal state)
        if (dep > 0) continue

        # --- Two-character operators ---
        if (i < n) {
            c2 = substr(s, i + 1, 1)
            if (c == "&" && c2 == "&") return "AND"
            if (c == "|" && c2 == "|") return "OR"
        }

        # --- Single & : background operator (item 10) ---
        # INTENT: `sleep 1 & echo second` (case SBY1) runs two commands from
        #   one tool call, so it is chaining.
        # REASONING: a bare & is only chaining when something follows it. All
        #   other & shapes are redirects, fd dups, or pipes:
        #     &>  &>>   -> redirect        (next char is >)
        #     >&  <&  N>&M  |&  -> fd dup / pipe   (previous char is > < |)
        #     trailing &    -> nothing chained, treat like a trailing ;
        if (c == "&") {
            c2 = (i < n) ? substr(s, i + 1, 1) : ""
            prevc = (i > 1) ? substr(s, i - 1, 1) : ""
            if (c2 == ">") { curw = ""; continue }
            if (prevc == ">" || prevc == "<" || prevc == "|") { curw = ""; continue }
            rest = substr(s, i + 1)
            gsub(/[ \t\r\n;]/, "", rest)
            if (rest == "") return "OK"      # trailing & : nothing follows
            return "AMP"
        }

        # --- Single-character operator: semicolon ---
        if (c == ";") {
            # Ignore trailing semicolons: if only whitespace and more
            # semicolons remain after this point, it is not chaining.
            rest = substr(s, i + 1)
            gsub(/[ \t\r\n;]/, "", rest)
            if (rest != "") return "SEMI"
            return "OK"                      # nothing but separators remain
        }

        # Accumulate the current word, capped so a pathological single token
        # cannot make word tracking quadratic (carrier tokens are short).
        if (length(curw) < 64) curw = curw c
    }
    return "OK"
}
BEGIN { buf = ""; first = 1 }
{ if (first) { buf = $0; first = 0 } else { buf = buf "\n" $0 } }
END { print scan(buf, 0) }
')

# ---------------------------------------------------------------------------
# APPLY scan results
# ---------------------------------------------------------------------------
case "$SCAN_RESULT" in
    AND)
        block "Command chaining with '&&' detected."
        ;;
    OR)
        block "Command chaining with '||' detected."
        ;;
    AMP)
        block "Command chaining with '&' (background) detected."
        ;;
    SEMI)
        # Exception: compound commands use ; as syntactic structure.
        # Allow when the command STARTS with a compound keyword.
        # This avoids false positives on: for x in ...; do ...; done
        # While still blocking: cmd1 ; cmd2 (starts with cmd1, not a keyword)
        # Residual R1: the exemption covers the WHOLE command once it starts
        # with a keyword (see the header's Known Residuals block).
        if echo "$CMD" | grep -qE '^\s*(for|while|until|if|elif|case|select)\b'; then
            exit 0
        fi
        block "Command chaining with ';' detected."
        ;;
    OK)
        exit 0
        ;;
    *)
        # Unexpected scanner output — fail open with caution.
        # This is a convention enforcement hook, not a security boundary;
        # a scanner bug should not block all Bash usage.
        exit 0
        ;;
esac
