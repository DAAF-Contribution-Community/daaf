#!/usr/bin/env bash
# ============================================================================
# DAAF Documentation Triage Lint -- a review queue, not a gate
# ============================================================================
# Lists lines in the shipped file set that a reviewer should check against
# agent_reference/DOCUMENTATION_STANDARDS.md. Every pattern here has false
# positives, so each hit is a question for a human, not a verdict. The scan
# exits 0 whenever it completes, whatever it finds; --strict turns families A
# and E into a pass/fail check for a release gate.
#
# Shipped set: every tracked file except research/, CHANGELOG.md,
# benchmarks/CHANGELOG.md and *.jsonl (binary files are skipped). The scan
# uses `git grep` over tracked content, so a maintainer checkout and a CI
# clone give the same result for families A to D. --untracked adds new files
# that are not ignored, for a check before they are staged.
#
# Families:
#   A  Unshipped references (all shipped files): maintainer workspace paths
#      (research/YYYY-MM-DD_FrameworkDev_... and _AdHoc_...), maintainer-local
#      tools and hook-patch bundles (nuke_daaf, run_daaf_dev, daaf-release-prep,
#      apply_hook_patches), and text that labels
#      itself "maintainer-only" or "not shipped". Example project paths such as
#      research/2026-01-24_School_Analysis are not matched.
#   B  History wording (docs: *.md, *.txt, *.cff outside tests/): a narrow
#      pattern such as "formerly", "as of v3", "the old script".
#   C  Dated stamps (user-facing files and agent_reference/): a YYYY-MM-DD date
#      on a line with no external-context token (Claude Code, a 2.1.N version,
#      a model name, API, a URL, a vendor or data-source name). Dates that
#      start a file name (2026-01-24_x, 2026-01-24a_x) and skill freshness keys
#      are not matched.
#   D  Internal codes (user-facing files only): Stage N, PSU..., G1, GFD-,
#      GDI-1, GDS-1, QA1, QAP, QAS, QAS-A, CP1, CPP, CPS-INTAKE, CPS-GEN, DI-1,
#      DS-1, RV-1. Bare CPS is not matched: it also names the Current
#      Population Survey.
#   E  Paths hidden by .git/info/exclude (all shipped files). Only a
#      maintainer checkout has that file; when it is absent or holds no
#      patterns (CI), E is skipped with a one-line note. Paths hidden by
#      .gitignore are runtime folders every install creates and are not
#      reported. A research/ path is reported only when the workspace exists
#      on disk and family A does not already match it.
#
# Tiers group the output in review-priority order:
#   1 user docs        README.md, user_reference/, CITATION.cff, CONTRIBUTING.md,
#                      CODE_OF_CONDUCT.md, scripts/host/README.txt
#   2 host and config  scripts/host/*, Dockerfile, docker-compose.yml,
#                      .claude/scripts/*
#   3 orchestrator     .claude/skills/daaf-orchestrator/**,
#                      agent_reference/WORKFLOW_PHASE*.md
#   4 user-read templates  agent_reference/{REPORT,PLAN,PLAN_TASKS,STATE,
#                      REPRODUCTION_REPORT}_TEMPLATE.md, STATE_TEMPLATE_*.md,
#                      AI_DISCLOSURE_REFERENCE.md
#   5 runtime messages .claude/hooks/*, scripts/*.sh
#   6 everything else
#
# Allowlist: tests/lint/docs-triage-allowlist.tsv under the scanned repo.
# Tab-separated columns: path_glob, family, fragment, reason. path_glob uses
# `*` (matches across /) and `?`; family is one letter, a comma list (A,E) or
# `*`; fragment is a fixed string the line must contain, or `*` for the whole
# file. Lines starting with # are comments. Entries that match nothing are
# reported as stale on a full scan (no --family filter).
#
# Usage:
#   bash tests/lint/docs-triage.sh [options]
#     --root DIR          scan the git repository at DIR (default: this repo)
#     --format text|tsv   text (default) or tab-separated rows with a header:
#                         tier, family, file, line, text
#     --family LIST       comma list of families to scan, e.g. A,E; * alone
#                         means all families (the same as no --family)
#     --tier LIST         comma list of tiers to report, e.g. 1,2
#     --strict            exit 1 if any reported, non-allowlisted A or E hit
#     --untracked         also scan untracked files that are not ignored
#     -h, --help          show this help
#   NO_COLOR=1 disables color; color is also off when stdout is not a terminal.
#
# Exit codes:
#   0  scan completed (hits or not), or --strict found no A/E hit
#   1  --strict and at least one non-allowlisted A or E hit was reported
#   2  could not run: bad arguments, not a git work tree, git missing,
#      unreadable allowlist, or a git command failed
# ============================================================================

set -euo pipefail

TAB="$(printf '\t')"

usage() {
    awk '/^# Usage:/ { p = 1 } p && /^# ====/ { exit } p { sub(/^# ?/, ""); print }' "${BASH_SOURCE[0]}"
}

die() {
    echo "docs-triage: ERROR: $1" >&2
    exit 2
}

# --- Arguments ---
ROOT_ARG=""
FORMAT="text"
FAMILIES="A,B,C,D,E"
FAMILY_FILTERED=0
TIERS="1,2,3,4,5,6"
STRICT=0
UNTRACKED=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --root)
            [ "$#" -ge 2 ] || die "--root needs a directory (see --help)"
            ROOT_ARG="$2"; shift 2 ;;
        --format)
            [ "$#" -ge 2 ] || die "--format needs text or tsv (see --help)"
            FORMAT="$2"; shift 2 ;;
        --family)
            [ "$#" -ge 2 ] || die "--family needs a list such as A,E (see --help)"
            FAMILIES="$2"; FAMILY_FILTERED=1; shift 2 ;;
        --tier)
            [ "$#" -ge 2 ] || die "--tier needs a list such as 1,2 (see --help)"
            TIERS="$2"; shift 2 ;;
        --strict)
            STRICT=1; shift ;;
        --untracked)
            UNTRACKED=1; shift ;;
        -h|--help)
            usage; exit 0 ;;
        *)
            die "unknown argument '$1' (see --help)" ;;
    esac
done

case "${FORMAT}" in
    text|tsv) ;;
    *) die "--format must be text or tsv, not '${FORMAT}'" ;;
esac

FAMILIES="$(printf '%s' "${FAMILIES}" | tr '[:lower:]' '[:upper:]' | tr -d ' ')"
# `*` alone means every family, the same as giving no --family.
if [ "${FAMILIES}" = "*" ]; then
    FAMILIES="A,B,C,D,E"
    FAMILY_FILTERED=0
fi
case ",${FAMILIES}," in
    *,,*) die "--family list has an empty item: '${FAMILIES}'" ;;
esac
# read -a splits on commas without pathname expansion, so an item such as `*`
# is checked as text instead of expanding to the file names in the cwd.
IFS=, read -r -a FAMILY_ITEMS <<< "${FAMILIES}"
for f in "${FAMILY_ITEMS[@]}"; do
    case "${f}" in
        A|B|C|D|E) ;;
        *) die "unknown family '${f}' (families are A, B, C, D, E, or * alone for all)" ;;
    esac
done

TIERS="$(printf '%s' "${TIERS}" | tr -d ' ')"
case ",${TIERS}," in
    *,,*) die "--tier list has an empty item: '${TIERS}'" ;;
esac
IFS=, read -r -a TIER_ITEMS <<< "${TIERS}"
for t in "${TIER_ITEMS[@]}"; do
    case "${t}" in
        1|2|3|4|5|6) ;;
        *) die "unknown tier '${t}' (tiers are 1 to 6)" ;;
    esac
done

has_family() {
    case ",${FAMILIES}," in
        *",$1,"*) return 0 ;;
        *) return 1 ;;
    esac
}

# --- Repository ---
command -v git >/dev/null 2>&1 || die "git is not installed"
command -v awk >/dev/null 2>&1 || die "awk is not installed"

if [ -n "${ROOT_ARG}" ]; then
    START_DIR="${ROOT_ARG}"
else
    START_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
fi
[ -d "${START_DIR}" ] || die "no such directory: ${START_DIR}"
if ! REPO="$(git -C "${START_DIR}" rev-parse --show-toplevel 2>/dev/null)"; then
    die "${START_DIR} is not inside a git work tree"
fi

ALLOWLIST="${REPO}/tests/lint/docs-triage-allowlist.tsv"
ALLOW_SOURCE="${ALLOWLIST}"
if [ ! -e "${ALLOWLIST}" ]; then
    ALLOW_SOURCE="/dev/null"
elif [ ! -r "${ALLOWLIST}" ]; then
    die "allowlist exists but cannot be read: ${ALLOWLIST}"
fi

# Pathspec magic that removes the unshipped parts of the tracked set.
SHIPPED_EXCLUDES=(
    ':(exclude)research/'
    ':(exclude)CHANGELOG.md'
    ':(exclude)benchmarks/CHANGELOG.md'
    ':(exclude)*.jsonl'
)

# --- Patterns (POSIX ERE as git grep reads them) ---
# A: case-insensitive; the workspace pattern requires the session-type word so
# that illustrative project paths in examples do not match.
A_WORKSPACE_RE='research/20[0-9]{2}-[0-9]{2}-[0-9]{2}[a-z]?_(FrameworkDev|AdHoc)_'
A_TOOLS_RE='nuke_daaf|run_daaf_dev|daaf-release-prep|apply_hook_patches'
A_LABEL_RE='maintainer[- ]only|not shipped'

# B: case-insensitive whole-word match. Kept narrow on purpose: broad words
# such as "previously", "no longer" or "legacy" are mostly legitimate.
B_RE='formerly|(new|added|introduced|changed|removed) in v[0-9]+|as of v[0-9]+|before (that|this) (change|fix)|(before|after) the fix|the old (script|logic|warning|list|behaviou?r|approach|name)'

# C: a date not followed by a letter, digit or underscore (which would make it
# part of a file name or timestamp), minus lines carrying a token that marks an
# outside fact. Case-sensitive so that "API" does not match inside words.
C_DATE_RE='(^|[^0-9])20[0-9]{2}-[0-9]{2}-[0-9]{2}([^0-9A-Za-z_]|$)'
C_EXTERNAL_RE='Claude Code|claude-|2\.1\.[0-9]|[Gg][Pp][Tt]-|Opus|Sonnet|Haiku|Fable|Mythos|GLM|Gemini|Codex|OpenRouter|Anthropic|OpenAI|API|https?://|www\.|PyPI|CRAN|Docker (Desktop|Engine|[0-9])|Ubuntu|Windows|macOS|GitHub|upstream|vendor|fetched|retrieved|accessed|OpenAlex|Semantic Scholar|ERIC|Scite|Elicit|arXiv|Crossref|Census|NCES|Urban Institute|[Pp]ortal|mirror|vintage|UV_EXCLUDE_NEWER|UBUNTU_SNAPSHOT|snapshot'
C_SKILLKEY_RE='skill-(authored|last-updated):'

# D: case-sensitive whole-word match.
D_RE='PSU[-A-Z0-9]*|Stage [0-9]+|G[0-9]+|GFD-[A-Z0-9-]*|GDI-[0-9]+|GDS-[0-9]+|QA[0-9][a-z0-9]*|QAP[0-9]*|QAS(-[A-C])?|CP[0-9]+|CPP[0-9]*|CPS-(INTAKE|GEN)|DI-[0-9]+|DS-[0-9]+|RV-[0-9]+'

# E: path-like tokens; the awk copy below must match this one.
E_LINE_RE='[A-Za-z0-9_.-]/[A-Za-z0-9_.-]'

# --- Shared awk code ---
# Tier assignment from a repo-relative path.
AWK_TIER='
function tier(f) {
    if (f == "README.md" || f == "CITATION.cff" || f == "CONTRIBUTING.md" || f == "CODE_OF_CONDUCT.md" || f == "scripts/host/README.txt" || f ~ /^user_reference\//) return 1
    if (f ~ /^scripts\/host\// || f == "Dockerfile" || f == "docker-compose.yml" || f ~ /^\.claude\/scripts\//) return 2
    if (f ~ /^\.claude\/skills\/daaf-orchestrator\// || f ~ /^agent_reference\/WORKFLOW_PHASE[^\/]*\.md$/) return 3
    if (f ~ /^agent_reference\/(REPORT|PLAN|PLAN_TASKS|STATE|REPRODUCTION_REPORT)_TEMPLATE\.md$/ || f ~ /^agent_reference\/STATE_TEMPLATE_[^\/]*\.md$/ || f == "agent_reference/AI_DISCLOSURE_REFERENCE.md") return 4
    if (f ~ /^\.claude\/hooks\// || f ~ /^scripts\/[^\/]*\.sh$/) return 5
    return 6
}
function clean(s) {
    gsub(/\r/, "", s)
    gsub(/\t/, " ", s)
    return s
}
'

# Turns `git grep -n --column --null` output (NULs already turned into tabs)
# into rows: tier, family, file, line, column, text.
AWK_ROW="${AWK_TIER}"'
{
    text = $4
    for (i = 5; i <= NF; i++) text = text " " $i
    printf "%d\t%s\t%s\t%s\t%s\t%s\n", tier($1), fam, $1, $2, $3, clean(text)
}
'

# Extracts path-like tokens from `git grep -n --null` lines and normalizes them
# the same way in both modes: mode=tokens prints each token; mode=hits prints
# a family E row for each token present in the ENVIRON map DT_E_MAP.
AWK_E="${AWK_TIER}"'
function norm(t) {
    if (substr(t, 1, 6) == "/daaf/") t = substr(t, 7)
    else if (substr(t, 1, 1) == "/") return ""
    while (substr(t, 1, 2) == "./") t = substr(t, 3)
    while (t ~ /[.]$/) t = substr(t, 1, length(t) - 1)
    if (t !~ /[^\/]\/[^\/]/) return ""
    if (t ~ /(^|\/)\.\.(\/|$)/ || t ~ /^\.git(\/|$)/) return ""
    return t
}
BEGIN {
    re = "/?[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)+/?"
    if (mode == "hits") {
        n = split(ENVIRON["DT_E_MAP"], rows, "\n")
        for (i = 1; i <= n; i++) {
            if (rows[i] == "") continue
            split(rows[i], kv, "\t")
            hidden[kv[1]] = kv[2]
        }
    }
}
{
    file = $1; ln = $2
    text = $3
    for (i = 4; i <= NF; i++) text = text " " $i
    text = clean(text)
    s = text; off = 0
    delete seen
    while (match(s, re)) {
        tok = norm(substr(s, RSTART, RLENGTH))
        pos = off + RSTART
        off = off + RSTART + RLENGTH - 1
        s = substr(s, RSTART + RLENGTH)
        if (tok == "") continue
        if (mode == "tokens") { print tok; continue }
        if ((tok in hidden) && !(tok in seen)) {
            seen[tok] = 1
            printf "%d\tE\t%s\t%s\t%d\t%s\n", tier(file), file, ln, pos, text
        }
    }
}
'

# Applies the allowlist and the tier filter, then renders text or TSV.
AWK_FINAL='
function glob2re(g,    out, i, c) {
    out = "^"
    for (i = 1; i <= length(g); i++) {
        c = substr(g, i, 1)
        if (c == "*") out = out ".*"
        else if (c == "?") out = out "."
        else if (index(".[]()+^$|{}\\", c) > 0) out = out "[" (c == "\\" ? "\\\\" : (c == "^" ? "\\^" : c)) "]"
        else out = out c
    }
    return out "$"
}
function famok(list, f) {
    return list == "*" || index("," list ",", "," f ",") > 0
}
function excerpt(t, col,    start, n) {
    if (match(t, /^[ \t]+/)) { t = substr(t, RLENGTH + 1); col = col - RLENGTH }
    n = 200
    if (length(t) <= n) return t
    start = col - 60
    if (start < 1) start = 1
    if (start + n > length(t) + 1) start = length(t) + 1 - n
    return (start > 1 ? "..." : "") substr(t, start, n) (start + n <= length(t) ? "..." : "")
}
BEGIN {
    FS = "\t"
    split("user docs|host scripts and edited config|orchestrator|user-read templates|runtime messages|everything else", tname, "|")
    fname["A"] = "unshipped references"
    fname["B"] = "history wording"
    fname["C"] = "dated stamps"
    fname["D"] = "internal codes"
    fname["E"] = "paths hidden by .git/info/exclude"
    nf = split(families, flist, ",")
    nt = split(tiers, tsel, ",")
    for (i = 1; i <= nt; i++) tierok[tsel[i]] = 1
    if (color == 1) { B1 = "\033[1m"; B0 = "\033[0m"; Y1 = "\033[0;33m" } else { B1 = ""; B0 = ""; Y1 = "" }
}
phase == 1 {
    sub(/\r$/, "")
    if ($0 ~ /^[ \t]*#/ || $0 ~ /^[ \t]*$/) next
    if (NF < 4 || $1 == "" || $2 == "" || $3 == "") { bad[++nbad] = FNR; next }
    na++
    are[na] = glob2re($1); afam[na] = toupper($2); afrag[na] = $3
    aline[na] = FNR; araw[na] = $1 " | " $2 " | " $3; amatch[na] = 0
    next
}
{
    t = $1; f = $2; file = $3; ln = $4; col = $5; text = $6
    allowed = 0
    for (i = 1; i <= na; i++) {
        if (file ~ are[i] && famok(afam[i], f) && (afrag[i] == "*" || index(text, afrag[i]) > 0)) {
            amatch[i]++
            allowed = 1
        }
    }
    if (allowed) { nallowed++; next }
    if (!(t in tierok)) next
    nh++
    ht[nh] = t; hf[nh] = f; hfile[nh] = file; hl[nh] = ln; hx[nh] = excerpt(text, col)
    cnt[t, f]++; rowtot[t]++; coltot[f]++
    if (f == "A" || f == "E") strict_hits++
}
END {
    rc = (strict == 1 && strict_hits > 0) ? 10 : 0
    if (format == "tsv") {
        print "tier\tfamily\tfile\tline\ttext"
        for (i = 1; i <= nh; i++) printf "%s\t%s\t%s\t%s\t%s\n", ht[i], hf[i], hfile[i], hl[i], hx[i]
        for (i = 1; i <= nbad; i++) printf "docs-triage: malformed allowlist line %d (needs 4 tab-separated columns)\n", bad[i] > "/dev/stderr"
        if (stale_check == 1) for (i = 1; i <= na; i++) if (amatch[i] == 0 && !(e_skipped == 1 && afam[i] == "E"))
            printf "docs-triage: stale allowlist entry, line %d: %s\n", aline[i], araw[i] > "/dev/stderr"
        if (e_note != "") print "docs-triage: " e_note > "/dev/stderr"
        exit rc
    }
    print B1 "DAAF documentation triage" B0 " (a review queue for DOCUMENTATION_STANDARDS.md, not a gate)"
    print "Repository: " repo
    print "Shipped files: " nshipped "   Families: " families "   Tiers: " tiers
    if (e_note != "") print Y1 "Note: " e_note B0
    print ""
    print B1 "Summary" B0 " (non-allowlisted hits by tier and family)"
    hdr = sprintf("  %-38s", "Tier")
    for (j = 1; j <= nf; j++) hdr = hdr sprintf("%6s", flist[j])
    print hdr sprintf("%8s", "total")
    for (i = 1; i <= 6; i++) {
        if (!(i in tierok)) continue
        line = sprintf("  %-38s", i " " tname[i])
        for (j = 1; j <= nf; j++) line = line sprintf("%6d", cnt[i, flist[j]] + 0)
        print line sprintf("%8d", rowtot[i] + 0)
    }
    line = sprintf("  %-38s", "Total")
    for (j = 1; j <= nf; j++) line = line sprintf("%6d", coltot[flist[j]] + 0)
    print line sprintf("%8d", nh + 0)
    print ""
    print "Allowlisted hits (suppressed): " (nallowed + 0) "   Allowlist entries: " (na + 0)
    if (stale_check == 1) {
        ns = 0
        for (i = 1; i <= na; i++) if (amatch[i] == 0 && !(e_skipped == 1 && afam[i] == "E")) stale[++ns] = i
        print "Stale allowlist entries (match nothing; remove or fix them): " ns
        for (k = 1; k <= ns; k++) print "  line " aline[stale[k]] ": " araw[stale[k]]
    } else {
        print "Stale allowlist entries: not checked (a --family filter is set)"
    }
    for (i = 1; i <= nbad; i++) print "Malformed allowlist line " bad[i] " (needs 4 tab-separated columns): ignored"
    if (strict == 1) print "Strict mode: " (strict_hits + 0) " non-allowlisted A/E hit(s)"
    lastt = ""; lastf = ""
    for (i = 1; i <= nh; i++) {
        if (ht[i] != lastt) { print ""; print B1 "== Tier " ht[i] ": " tname[ht[i]] " ==" B0; lastt = ht[i]; lastf = "" }
        if (hf[i] != lastf) { print "-- " hf[i] ": " fname[hf[i]] " --"; lastf = hf[i] }
        print hfile[i] ":" hl[i] ": " hx[i]
    }
    exit rc
}
'

# --- Scanners ---
# Runs git grep over tracked files and, with --untracked, a second time over the
# untracked, non-ignored files inside the same pathspec. Two runs are needed
# because `git grep --untracked` skips tracked files that an ignore rule also
# matches (e.g. scripts/host/environment_settings_example.txt). Arguments:
# git grep options, then `--`, then the pathspec. git grep exits 1 when nothing
# matches; only a higher code is a failure.
gg() {
    local opts=() specs=() extra=() in_specs=0 arg f rc=0
    for arg in "$@"; do
        if [ "${in_specs}" -eq 0 ] && [ "${arg}" = "--" ]; then
            in_specs=1
        elif [ "${in_specs}" -eq 0 ]; then
            opts+=("${arg}")
        else
            specs+=("${arg}")
        fi
    done
    git -C "${REPO}" grep "${opts[@]}" -- "${specs[@]}" || rc=$?
    if [ "${rc}" -gt 1 ]; then
        echo "docs-triage: ERROR: git grep failed (exit ${rc})" >&2
        return 2
    fi
    [ "${UNTRACKED}" -eq 1 ] || return 0
    while IFS= read -r -d '' f; do
        extra+=(":(literal)${f}")
    done < <(git -C "${REPO}" ls-files -z --others --exclude-standard -- "${specs[@]}")
    [ "${#extra[@]}" -gt 0 ] || return 0
    rc=0
    git -C "${REPO}" grep --untracked "${opts[@]}" -- "${extra[@]}" || rc=$?
    if [ "${rc}" -gt 1 ]; then
        echo "docs-triage: ERROR: git grep --untracked failed (exit ${rc})" >&2
        return 2
    fi
    return 0
}

# Runs one family's git grep and emits rows. $1 = family letter; the rest are
# git grep arguments up to and including the pathspec.
scan_lines() {
    local fam="$1"
    shift
    gg -n --column --null -I "$@" \
        | tr '\000' '\t' \
        | LC_ALL=C awk -F '\t' -v fam="${fam}" "${AWK_ROW}"
}

scan_A() {
    scan_lines A -i -E -e "${A_WORKSPACE_RE}" -e "${A_TOOLS_RE}" -e "${A_LABEL_RE}" \
        -- . "${SHIPPED_EXCLUDES[@]}"
}

scan_B() {
    scan_lines B -i -w -E -e "${B_RE}" \
        -- '*.md' '*.txt' '*.cff' ':(exclude)tests/' "${SHIPPED_EXCLUDES[@]}"
}

scan_C() {
    scan_lines C -E -e "${C_DATE_RE}" --and --not -e "${C_EXTERNAL_RE}" --and --not -e "${C_SKILLKEY_RE}" \
        -- README.md CITATION.cff CONTRIBUTING.md CODE_OF_CONDUCT.md user_reference/ \
           scripts/host/ Dockerfile docker-compose.yml .claude/scripts/ agent_reference/ \
           "${SHIPPED_EXCLUDES[@]}"
}

scan_D() {
    scan_lines D -w -E -e "${D_RE}" \
        -- README.md user_reference/ scripts/host/ \
           agent_reference/REPORT_TEMPLATE.md agent_reference/PLAN_TEMPLATE.md \
           agent_reference/PLAN_TASKS_TEMPLATE.md agent_reference/STATE_TEMPLATE.md \
           'agent_reference/STATE_TEMPLATE_*.md' agent_reference/REPRODUCTION_REPORT_TEMPLATE.md \
           agent_reference/AI_DISCLOSURE_REFERENCE.md \
           "${SHIPPED_EXCLUDES[@]}"
}

# Family E needs the map of hidden tokens first; build_e_map sets E_MAP and
# E_NOTE. It reads .git/info/exclude through git, so the git dir is resolved
# rather than assumed (worktrees keep it elsewhere).
E_MAP=""
E_NOTE=""
E_SKIPPED=0
build_e_map() {
    local exclude_file tokens checked src pattern path ws ws_re rc
    exclude_file="$(git -C "${REPO}" rev-parse --git-path info/exclude)"
    case "${exclude_file}" in
        /*) ;;
        *) exclude_file="${REPO}/${exclude_file}" ;;
    esac
    if [ ! -f "${exclude_file}" ] || ! grep -q -v -e '^[[:space:]]*#' -e '^[[:space:]]*$' "${exclude_file}"; then
        E_NOTE="family E skipped: .git/info/exclude is absent or has no patterns (normal outside a maintainer checkout)"
        E_SKIPPED=1
        return 0
    fi
    tokens="$(gg -n --null -I -E -e "${E_LINE_RE}" -- . "${SHIPPED_EXCLUDES[@]}" \
        | tr '\000' '\t' \
        | LC_ALL=C awk -F '\t' -v mode=tokens "${AWK_E}" \
        | LC_ALL=C sort -u)"
    [ -n "${tokens}" ] || return 0
    # check-ignore exits 1 when no path is ignored; only a higher code is an error.
    rc=0
    checked="$(printf '%s\n' "${tokens}" | git -C "${REPO}" check-ignore --no-index -v -n --stdin)" || rc=$?
    if [ "${rc}" -gt 1 ]; then
        E_NOTE="family E skipped: git check-ignore failed (exit ${rc})"
        E_SKIPPED=1
        return 0
    fi
    ws_re="^${A_WORKSPACE_RE}"
    while IFS="${TAB}" read -r src path; do
        pattern="${src#*:*:}"
        src="${src%%:*}"
        [ "${src}" = ".git/info/exclude" ] || [ "${src}" = "${exclude_file}" ] || continue
        case "${pattern}" in '!'*) continue ;; esac
        case "${path}" in
            research/*)
                # A workspace that family A already names, or an example path
                # with no workspace behind it, is not an E hit.
                ws="${path#research/}"
                ws="${ws%%/*}"
                if [[ "research/${ws}_" =~ ${ws_re} ]]; then
                    continue
                fi
                [ -d "${REPO}/research/${ws}" ] || continue
                ;;
        esac
        E_MAP="${E_MAP}${path}${TAB}${pattern}
"
    done <<EOF
${checked}
EOF
}

scan_E() {
    [ "${E_SKIPPED}" -eq 0 ] || return 0
    [ -n "${E_MAP}" ] || return 0
    gg -n --null -I -E -e "${E_LINE_RE}" -- . "${SHIPPED_EXCLUDES[@]}" \
        | tr '\000' '\t' \
        | DT_E_MAP="${E_MAP}" LC_ALL=C awk -F '\t' -v mode=hits "${AWK_E}"
}

# --- Run ---
START_SECONDS="${SECONDS}"

if has_family E; then
    build_e_map
fi

if [ "${UNTRACKED}" -eq 1 ]; then
    NSHIPPED="$(git -C "${REPO}" ls-files --cached --others --exclude-standard -- . "${SHIPPED_EXCLUDES[@]}" | wc -l | tr -d ' ')"
else
    NSHIPPED="$(git -C "${REPO}" ls-files -- . "${SHIPPED_EXCLUDES[@]}" | wc -l | tr -d ' ')"
fi

COLOR=0
if [ -z "${NO_COLOR:-}" ] && [ -t 1 ] && [ "${FORMAT}" = "text" ]; then
    COLOR=1
fi

STALE_CHECK=1
[ "${FAMILY_FILTERED}" -eq 0 ] || STALE_CHECK=0

# Runs inside a pipeline with errexit off, so each failure returns explicitly.
run_scans() {
    if has_family A; then scan_A || return 2; fi
    if has_family B; then scan_B || return 2; fi
    if has_family C; then scan_C || return 2; fi
    if has_family D; then scan_D || return 2; fi
    if has_family E; then scan_E || return 2; fi
    return 0
}

# PIPESTATUS tells a failed scan (exit 2) apart from the renderer's strict
# signal (10), which a single pipeline status would merge.
set +e
run_scans \
    | LC_ALL=C sort -t "${TAB}" -k1,1n -k2,2 -k3,3 -k4,4n \
    | LC_ALL=C awk -v phase=1 -v format="${FORMAT}" -v families="${FAMILIES}" \
        -v tiers="${TIERS}" -v strict="${STRICT}" -v color="${COLOR}" \
        -v repo="${REPO}" -v nshipped="${NSHIPPED}" -v e_note="${E_NOTE}" \
        -v e_skipped="${E_SKIPPED}" -v stale_check="${STALE_CHECK}" \
        "${AWK_FINAL}" "${ALLOW_SOURCE}" phase=2 -
PIPE_STATUS=("${PIPESTATUS[@]}")
set -e

# 141 = SIGPIPE: the reader closed the output early (e.g. `| head`).
if [ "${PIPE_STATUS[2]}" -eq 141 ]; then
    exit 141
fi

if [ "${PIPE_STATUS[0]}" -ne 0 ] || [ "${PIPE_STATUS[1]}" -ne 0 ] \
    || { [ "${PIPE_STATUS[2]}" -ne 0 ] && [ "${PIPE_STATUS[2]}" -ne 10 ]; }; then
    echo "docs-triage: ERROR: the scan did not complete (exit codes: ${PIPE_STATUS[*]})" >&2
    exit 2
fi

if [ "${FORMAT}" = "text" ]; then
    echo ""
    echo "Scan time: $((SECONDS - START_SECONDS))s"
fi

if [ "${PIPE_STATUS[2]}" -eq 10 ]; then
    exit 1
fi
exit 0
