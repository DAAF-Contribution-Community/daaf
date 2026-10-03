# shellcheck shell=bash
# shellcheck disable=SC2034  # the FS_* globals are this helper's outputs, read by the caller
# ============================================================================
# fake_shapes.bash -- run-time builders for credential-SHAPED test fixtures
# ============================================================================
# Shared by secret-handling tests (first user: tests/bash/audit_log.bats, the
# hook bundle revision _d cases). Plain bash: no bats functions, no option
# changes (set -e/-u/pipefail are left as the caller has them), nothing
# printed when sourced, safe under `set -uo pipefail`. Load it with
#   bats:      load 'helpers/fake_shapes'
#   non-bats:  . "<repo>/tests/bash/helpers/fake_shapes.bash"
#              (e.g. "$(dirname "${BASH_SOURCE[0]}")/../tests/bash/helpers/
#              fake_shapes.bash" from a script in scripts/)
# The file name avoids the substring "secret" on purpose: settings.json denies
# Read(**/*secret*), so a helper named that way could not be read by any
# agent, reviewers included.
#
# THE NO-LITERAL RULE (binding for this file and for every caller)
#   No file, diff, tool call, commit message or chat message may contain a
#   whole credential-shaped literal. Earlier attempts to write such fixtures
#   triggered automated safety stops, inferred to come from realistic secrets
#   passing through a model's context. So:
#     - Every fake value is GENERATED at run time (fake_filler: sha256sum of
#       a fixed seed word), never written. Names that complete a credential
#       shape (header names, flags, schemes, key names) are assembled from
#       split string fragments joined by concatenation.
#     - Callers assert OUTCOMES and stay quiet: use fake_expect_redacted /
#       fake_expect_kept below. Never pass a generated value to bats'
#       assert_output / refute_output (the test_helper fallbacks print the raw
#       $output on failure), never echo FS_TEXT / FS_VALUE, never `cat` a log
#       that holds them. To debug, print lengths, marker counts or
#       fake_mask's masked line.
#     - On failure bats prints the failing SOURCE line; it holds unexpanded
#       variable names only, which is why no literal may sit in a test body.
#
# BUILDERS (each sets the same five globals; nothing is printed)
#   FS_TEXT    the whole fixture text (a command line) carrying the shape
#   FS_VALUE   the generated secret part (must not reach a redacted log)
#   FS_NEEDLE  the value with its unique neighbouring context; this is what
#              the checks look for, so a short value (1-3 characters) is not
#              confused with the same characters elsewhere in the text
#   FS_MARKER  the [REDACTED:<family>] family a redacting hook should emit
#              (empty for a shape that must be KEPT, e.g. a token counter)
#   FS_NAME    the header / flag / key name used (fragments joined)
#
#   fake_api_key_header   [LEN=32] [SEED]
#   fake_password_flag    [LEN=24] [FORM=space|equals|quoted|quoted_equals]
#                         [FLAG] [SEED]
#   fake_url_userinfo     [LEN=20] [FORM=plain|at] [SEED]
#   fake_pass_assignment  [LEN=24] [NAME] [SEED] [FORM=plain|quoted]
#   fake_curl_user        [LEN=20] [FORM=long|short|attached|continued] [SEED]
#   fake_token_counter    [DIGITS=9] [SEED]      (numeric; must be kept)
#   fake_token_assignment [LEN=24] [SEED]        (non-numeric sibling)
#   The quoted / at forms split the value in two halves joined by a space
#   (or an "@"), so a check can tell when only the first half was redacted.
#
#   SECTION-10 NAME / COMMAND builders (bash-safety.sh accidental environment-
#   disclosure guard). Unlike the value builders above these carry NO secret
#   value — section 10 matches credential-shaped NAMES and whole-environment
#   commands, not values — so they set FS_NAME and FS_TEXT and CLEAR
#   FS_VALUE/FS_NEEDLE/FS_MARKER. Feed FS_TEXT to a hook-verdict check
#   (run_case / _run_hook), not the fake_expect_* redaction checks.
#   fake_env10_name  SEGMENT [PREFIX]        -> FS_NAME (fragment-assembled)
#   fake_env10_cmd   FORM [SEGMENT] [PREFIX] -> FS_TEXT (a whole command line)
#
# LOW-LEVEL
#   fake_filler LEN [SEED]   sets FS_FILL to LEN lowercase hex characters
#   fake_digits LEN [SEED]   sets FS_FILL to LEN decimal digits
#   fake_mask TEXT           sets FS_MASKED: FS_VALUE -> <fake>, then every
#                            run of 6+ hex characters -> <hex>
#
# CHECKS (silent on success; on failure print the case name, lengths,
# marker and needle counts, and a MASKED line, then return 1)
#   fake_expect_redacted CASE TEXT [MARKER]   marker present; needle absent;
#                                             value (8+ chars) absent; for
#                                             16+ chars its first and last 8
#                                             characters absent too
#   fake_expect_kept     CASE TEXT            needle present, unchanged
#   Both checks FAIL (fail closed) when FS_NEEDLE is empty or unset, e.g.
#   when no builder has run: a check with nothing to look for proves nothing.
#
# EXTENDING (Track B and later): add builders that set the same FS_* globals
# (e.g. a credential-NAME builder or a whole-command builder) and reuse the
# checks; keep every new literal split and every value generated.
# ============================================================================

# fake_filler LEN [SEED] -> FS_FILL (LEN hex chars; deterministic per seed).
fake_filler() {
    local want="${1:-16}" seed="${2:-daaf-fake-seed}" out="" n=0 h=""
    while [ "${#out}" -lt "$want" ]; do
        h="$(builtin printf '%s:%s' "$seed" "$n" | sha256sum)"
        out+="${h%% *}"
        n=$((n + 1))
    done
    FS_FILL="${out:0:want}"
}

# fake_digits LEN [SEED] -> FS_FILL (LEN decimal digits).
fake_digits() {
    local d=""
    fake_filler "${1:-9}" "${2:-daaf-fake-digits}"
    d="${FS_FILL//a/1}"; d="${d//b/2}"; d="${d//c/3}"
    d="${d//d/4}"; d="${d//e/5}"; d="${d//f/6}"
    # A leading zero would still be numeric; keep it non-zero for readability.
    if [ "${d:0:1}" = "0" ]; then d="9${d:1}"; fi
    FS_FILL="$d"
}

# Header name split across fragments; the value is generated.
fake_api_key_header() {
    local len="${1:-32}" seed="${2:-daaf-fake-header}"
    fake_filler "$len" "$seed"
    FS_NAME="X-""Api""-Key"
    FS_VALUE="$FS_FILL"
    FS_TEXT="curl -s -H \"${FS_NAME}: ${FS_VALUE}\" https://api.example.invalid/v1/items"
    FS_NEEDLE=": ${FS_VALUE}"
    FS_MARKER="credential-assignment"
}

# FORM: space          --flag VALUE      (rule 10, credential-flag)
#       equals         --flag=VALUE      (rule 9 when 8+ chars, else rule 10)
#       quoted         --flag 'VA LUE'   (rule 10; a quoted value may hold a space)
#       quoted_equals  --flag='VA LUE'   (rule 9 when the first half is 8+
#                                         chars, to the closing quote; else rule 10)
fake_password_flag() {
    local len="${1:-24}" form="${2:-space}" flag="${3:-}" seed="${4:-daaf-fake-flag}" half=0
    if [ -z "$flag" ]; then flag="--""pass""word"; fi
    fake_filler "$len" "$seed"
    FS_NAME="$flag"
    FS_MARKER="credential-flag"
    case "$form" in
        equals)
            FS_VALUE="$FS_FILL"
            FS_TEXT="mysql --user app ${flag}=${FS_VALUE} --host db.example.invalid"
            FS_NEEDLE="=${FS_VALUE} --host"
            if [ "$len" -ge 8 ]; then FS_MARKER="credential-assignment"; fi
            ;;
        quoted)
            half=$((len / 2))
            FS_VALUE="${FS_FILL:0:half} ${FS_FILL:half}"
            FS_TEXT="mysql --user app ${flag} '${FS_VALUE}' --host db.example.invalid"
            FS_NEEDLE="${FS_VALUE}"
            ;;
        quoted_equals)
            half=$((len / 2))
            FS_VALUE="${FS_FILL:0:half} ${FS_FILL:half}"
            FS_TEXT="mysql --user app ${flag}='${FS_VALUE}' --host db.example.invalid"
            FS_NEEDLE="${FS_VALUE}"
            if [ "$half" -ge 8 ]; then FS_MARKER="credential-assignment"; fi
            ;;
        *)
            FS_VALUE="$FS_FILL"
            FS_TEXT="mysql --user app ${flag} ${FS_VALUE} --host db.example.invalid"
            FS_NEEDLE=" ${FS_VALUE} --host"
            ;;
    esac
}

# scheme://user:VALUE@host -- scheme split across fragments.
# FORM: plain  the value is one hex run
#       at     the value holds a raw "@" between its halves (VAL@UE), which
#              RFC 3986 forbids in userinfo but which occurs in practice
fake_url_userinfo() {
    local len="${1:-20}" form="${2:-plain}" seed="${3:-daaf-fake-userinfo}" scheme="" half=0
    scheme="post""gres"
    fake_filler "$len" "$seed"
    FS_NAME="app_user"
    if [ "$form" = "at" ]; then
        half=$((len / 2))
        FS_VALUE="${FS_FILL:0:half}@${FS_FILL:half}"
    else
        FS_VALUE="$FS_FILL"
    fi
    FS_TEXT="psql ${scheme}://${FS_NAME}:${FS_VALUE}@db.example.invalid:5432/analytics"
    FS_NEEDLE=":${FS_VALUE}@"
    FS_MARKER="url-userinfo"
}

# NAME=VALUE with a segment-bounded PASS / PASSPHRASE key name.
# FORM: plain   NAME=VALUE
#       quoted  NAME='VA LUE' (halves joined by a space; rule 9 needs the
#               first half to be 8+ characters)
fake_pass_assignment() {
    local len="${1:-24}" name="${2:-}" seed="${3:-daaf-fake-pass}" form="${4:-plain}" half=0
    if [ -z "$name" ]; then name="DB_""PASS"; fi
    fake_filler "$len" "$seed"
    FS_NAME="$name"
    FS_MARKER="credential-assignment"
    if [ "$form" = "quoted" ]; then
        half=$((len / 2))
        FS_VALUE="${FS_FILL:0:half} ${FS_FILL:half}"
        FS_TEXT="export ${name}='${FS_VALUE}'"
        FS_NEEDLE="${FS_VALUE}"
    else
        FS_VALUE="$FS_FILL"
        FS_TEXT="export ${name}=${FS_VALUE}"
        FS_NEEDLE="=${FS_VALUE}"
    fi
}

# curl's user option, "name:VALUE" -- command and flag split across fragments.
# FORM: long       curl --user NAME:VALUE URL
#       short      curl -u NAME:VALUE URL
#       attached   curl -uNAME:VALUE URL
#       continued  curl -s \<newline>  --user NAME:VALUE URL (a multi-line
#                  command with a backslash line continuation)
fake_curl_user() {
    local len="${1:-20}" form="${2:-long}" seed="${3:-daaf-fake-curl-user}" cmd="" flag=""
    cmd="cu""rl"
    case "$form" in
        short) flag="-""u " ;;
        attached) flag="-""u" ;;
        continued) flag="\\"$'\n'"  --""user " ;;
        *) flag="--""user " ;;
    esac
    fake_filler "$len" "$seed"
    FS_NAME="app_user"
    FS_VALUE="$FS_FILL"
    FS_TEXT="${cmd} -s ${flag}${FS_NAME}:${FS_VALUE} https://api.example.invalid/v1/items"
    FS_NEEDLE=":${FS_VALUE} https"
    FS_MARKER="credential-flag"
}

# A usage counter: "tokens: <digits>". Must be KEPT (F4).
fake_token_counter() {
    local n="${1:-9}" seed="${2:-daaf-fake-counter}"
    fake_digits "$n" "$seed"
    FS_NAME="tokens"
    FS_VALUE="$FS_FILL"
    FS_TEXT="echo ${FS_NAME}: ${FS_VALUE} used"
    FS_NEEDLE="${FS_NAME}: ${FS_VALUE} used"
    FS_MARKER=""
}

# The non-numeric sibling of the counter: still a credential assignment.
fake_token_assignment() {
    local len="${1:-24}" seed="${2:-daaf-fake-token}"
    fake_filler "$len" "$seed"
    FS_NAME="session_""token"
    FS_VALUE="$FS_FILL"
    FS_TEXT="echo ${FS_NAME}=${FS_VALUE}"
    FS_NEEDLE="=${FS_VALUE}"
    FS_MARKER="credential-assignment"
}

# ---------------------------------------------------------------------------
# SECTION-10 (bash-safety.sh accidental environment-disclosure guard) builders.
# These carry NO secret VALUE: section 10 matches credential-shaped NAMES and
# whole-environment commands, not values. The credential last segment is still
# assembled from two fragments so no whole credential-shaped name is ever a
# single literal in this file (the NO-LITERAL RULE above). FS_VALUE/FS_NEEDLE/
# FS_MARKER are cleared; callers feed FS_TEXT to a hook-verdict check.
# ---------------------------------------------------------------------------

# fake_env10_name SEGMENT [PREFIX] -> FS_NAME, an UPPERCASE credential-shaped
# variable name whose LAST underscore segment is SEGMENT. SEGMENT selects one of
# section 10's keywords, each split across two fragments so the keyword is never
# a single literal; PREFIX (default APP; may itself contain underscores) is
# joined with "_" at run time, so the whole credential-shaped name is assembled,
# never written.
fake_env10_name() {
    local seg="${1:-key}" prefix="${2:-APP}" kw=""
    case "$seg" in
        key)        kw="K""EY" ;;
        apikey)     kw="API""KEY" ;;
        token)      kw="TOK""EN" ;;
        secret)     kw="SEC""RET" ;;
        password)   kw="PASS""WORD" ;;
        passwd)     kw="PASS""WD" ;;
        passphrase) kw="PASS""PHRASE" ;;
        credential) kw="CREDENT""IAL" ;;
        creds)      kw="CRE""DS" ;;
        dsn)        kw="DS""N" ;;
        pat)        kw="PA""T" ;;
        *)          kw="K""EY" ;;
    esac
    FS_NAME="${prefix}_${kw}"
}

# fake_env10_cmd FORM [SEGMENT] [PREFIX] -> FS_TEXT, a whole command line in a
# section-10 shape around a credential-shaped name (built by fake_env10_name).
# FORMs:
#   echo echo_braced printf declare_p typeset_p printenv   category-B BLOCK shapes
#   heredoc        0a accumulator: unquoted-delimiter heredoc body expands $NAME
#   grep_redirect  0c accumulator: double-quoted span holding $NAME, redirected
#   plural presence   must-stay-ALLOWED (…_KEYS plural; ${NAME:+set} presence)
#   loop_fp        accepted FP: an uppercase loop variable echoed
#   squote_fp      accepted FP: a single-quoted single-token span 0c canonicalizes
#   stress         a long (240-char) credential-shaped identifier echoed
fake_env10_cmd() {
    local form="${1:-echo}" seg="${2:-key}" prefix="${3:-APP}" i=0 long=""
    if [ "$form" = "stress" ]; then
        while [ "$i" -lt 240 ]; do long="${long}A"; i=$((i + 1)); done
        fake_env10_name "$seg" "$long"
    else
        fake_env10_name "$seg" "$prefix"
    fi
    case "$form" in
        echo)          FS_TEXT="echo \$${FS_NAME}" ;;
        echo_braced)   FS_TEXT="echo \"\${${FS_NAME}}\"" ;;
        printf)        FS_TEXT="printf '%s' \"\$${FS_NAME}\"" ;;
        declare_p)     FS_TEXT="declare -p ${FS_NAME}" ;;
        typeset_p)     FS_TEXT="typeset -p ${FS_NAME}" ;;
        printenv)      FS_TEXT="printenv ${FS_NAME}" ;;
        heredoc)       FS_TEXT=$'cat <<EOF\n$'"${FS_NAME}"$'\nEOF' ;;
        grep_redirect) FS_TEXT="grep \"lead \$${FS_NAME} tail\" data.txt > out.txt" ;;
        plural)        FS_TEXT="echo \"\$${FS_NAME}S\"" ;;
        presence)      FS_TEXT="[ -n \"\${${FS_NAME}:+set}\" ]" ;;
        loop_fp)       FS_TEXT="for ${FS_NAME} in a b; do echo \$${FS_NAME}; done" ;;
        squote_fp)     FS_TEXT="echo '\$${FS_NAME}'" ;;
        stress)        FS_TEXT="echo \$${FS_NAME}" ;;
        *)             FS_TEXT="echo \$${FS_NAME}" ;;
    esac
    FS_VALUE=""; FS_NEEDLE=""; FS_MARKER=""
}

# _fake_count TEXT NEEDLE -> FS_COUNT (non-overlapping occurrences).
_fake_count() {
    local t="$1" s="$2" c=0
    if [ -z "$s" ]; then FS_COUNT=0; return 0; fi
    while [[ "$t" == *"$s"* ]]; do
        t="${t#*"$s"}"
        c=$((c + 1))
    done
    FS_COUNT="$c"
}

# fake_mask TEXT -> FS_MASKED.
fake_mask() {
    local t="$1" v="${FS_VALUE-}" m=""
    if [ -n "$v" ]; then t="${t//"$v"/<fake>}"; fi
    while [[ "$t" =~ [0-9a-fA-F]{6,} ]]; do
        m="${BASH_REMATCH[0]}"
        t="${t//"$m"/<hex>}"
    done
    FS_MASKED="$t"
}

# _fake_report CASE TEXT WHY MARKER -- the only output this helper produces.
# Every FS_* read is guarded (${FS_X-}), so the report itself never aborts
# under `set -u` when no builder has run.
_fake_report() {
    local name="$1" t="$2" why="$3" marker="$4" v="${FS_VALUE-}" nm=0 nn=0 nv=0 nr=0
    _fake_count "$t" "[REDACTED:${marker}]"; nm="$FS_COUNT"
    _fake_count "$t" "${FS_NEEDLE-}"; nn="$FS_COUNT"
    _fake_count "$t" "$v"; nv="$FS_COUNT"
    _fake_count "$t" "[REDACTED:"; nr="$FS_COUNT"
    fake_mask "$t"
    builtin printf 'fake_shapes: case "%s": %s\n' "$name" "$why"
    builtin printf '  text_len=%s value_len=%s needle_count=%s value_count=%s marker[%s]_count=%s any_marker_count=%s\n' \
        "${#t}" "${#v}" "$nn" "$nv" "$marker" "$nm" "$nr"
    builtin printf '  masked: %s\n' "${FS_MASKED:0:400}"
}

fake_expect_redacted() {
    local name="$1" t="$2" marker="${3:-${FS_MARKER-}}" v="${FS_VALUE-}" why=""
    if [ -z "${FS_NEEDLE-}" ]; then
        why="no needle set (run a builder first)"
    elif [[ "$t" != *"[REDACTED:${marker}]"* ]]; then
        why="marker [REDACTED:${marker}] missing"
    elif [[ "$t" == *"${FS_NEEDLE-}"* ]]; then
        why="value still present in its slot"
    elif [ "${#v}" -ge 8 ] && [[ "$t" == *"$v"* ]]; then
        why="value still present"
    elif [ "${#v}" -ge 16 ] && [[ "$t" == *"${v:0:8}"* ]]; then
        why="value prefix still present"
    elif [ "${#v}" -ge 16 ] && [[ "$t" == *"${v: -8}"* ]]; then
        why="value tail still present"
    fi
    if [ -n "$why" ]; then
        _fake_report "$name" "$t" "expected redacted: $why" "$marker"
        return 1
    fi
    return 0
}

fake_expect_kept() {
    local name="$1" t="$2"
    if [ -z "${FS_NEEDLE-}" ]; then
        _fake_report "$name" "$t" "expected kept: no needle set (run a builder first)" "${FS_MARKER-}"
        return 1
    fi
    if [[ "$t" != *"${FS_NEEDLE-}"* ]]; then
        _fake_report "$name" "$t" "expected kept: needle missing or altered" "${FS_MARKER-}"
        return 1
    fi
    return 0
}
