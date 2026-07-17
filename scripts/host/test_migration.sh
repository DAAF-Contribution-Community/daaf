#!/usr/bin/env bash
# ============================================================================
# DAAF Migration End-to-End Test (macOS / Linux)
# ============================================================================
# Automated harness that walks the ACTUAL end-user install pathway for a chosen
# historical DAAF version, plants user work, runs the migration script from the
# local repo, and verifies the end state:
#   1. Nukes any existing DAAF Docker resources (clean slate)
#   2. Installs the old version THE WAY USERS ACTUALLY DID at that version:
#        Era 1 (v1.0.0)         git clone + busybox copy + docker compose up
#                               (/daaf gets a full .git: origin remote, main)
#        Era 2 (v2.0.0/v2.0.1)  ZIP download + busybox copy + docker compose up
#                               (no .git in a ZIP; that era's container
#                               entrypoint git-inits a LOCAL-ONLY repo with a
#                               synthetic root commit and NO remote -- the
#                               state migrate_daaf's graft machinery exists for)
#        Era 3 (v2.1.0+/branch) the version's own scripts/host/install.sh
#   3. Verifies the install produced the era's expected git state (the harness
#      never fakes era state by mutating the repo -- the pathway must produce it)
#   4. Creates committed framework changes + research files
#   5. Creates uncommitted user work (untracked files + a dirty tracked file,
#      which exercises the updater's stash/pop path)
#   6. Runs the migration script (from the local repo, not GitHub)
#   7. Runs era-conditional verification checks
#   8. (Optional) Exercises DAAF_PROJECT_NAME multi-instance support end-to-end
#      by standing up a SECOND coexisting instance and tearing it down again
#
# FIDELITY PRINCIPLE: Phases 2-3 replay the documented install commands from
# user_reference/01_installation_and_quickstart.md AT THE CHOSEN TAG as closely
# as possible. The point is to mirror what a real user's machine actually ran,
# so migration bugs surface authentically. Deliberate, documented deviations --
# each exists only to pin a moving target to a reproducible historical state:
#   - Era 1: users cloned when main WAS v1.0.0; a clone today lands on current
#     main. After the documented clone, the harness runs
#     `git checkout -B main v1.0.0` to rewind main to the tag. (The object
#     store still contains newer history than a 2026-era user had; migration
#     only fetches and sets upstream, so this is inert.)
#   - Era 2: users downloaded main.zip; the harness downloads the TAG's ZIP
#     (archive/refs/tags/<tag>.zip) for the same reason. Same busybox copy,
#     same compose build, same entrypoint git-init as the era produced.
#   - Era 3 with a vX.Y.Z tag: install.sh clones `--depth 1 -b <tag>`, which
#     leaves a detached HEAD that no real user had (users installed from
#     branch main). The harness normalizes with `git checkout -B main` at that
#     commit so the git state matches a real install of that vintage. Branch
#     values (e.g. daaf_dev) need no normalization and get none.
#
# EXPECT INTERACTIVE PROMPTS: migrate/update ask about running the update,
# backup, and rebuild -- you drive those choices, exactly as an end user would,
# and the Phase 7 checks are designed to pass whichever way you answer.
# (Unlike the .ps1 twin, the .sh child scripts pass DAAF_NESTED per-invocation
# and do not clobber it, so no stray exit pauses are expected here.)
#
# BUILD COST: Era 1/2 runs build the OLD Dockerfiles -- authentic and slow
# (10+ min cold). v1.0.0 pins no base-image digest (floating tag) and does not
# pin Claude Code, so that build may drift or break as upstreams move; the
# harness fails loudly if so rather than papering over it. Era 1 may also
# surface authentic-era permission pain (v2.0.1 added a chown repair command
# precisely because real users hit it) -- such failures are findings, not
# harness bugs.
#
# Usage:
#   bash test_migration.sh                            # v2.0.1, Era 2 (interactive)
#   DAAF_TEST_VERSION=v1.0.0 bash test_migration.sh   # Era 1
#   DAAF_TEST_VERSION=v2.1.0 bash test_migration.sh   # Era 3 (tag)
#   DAAF_TEST_VERSION=daaf_dev bash test_migration.sh # Era 3 (branch)
#   DAAF_TEST_VERSION=fresh bash test_migration.sh    # FRESH-INSTALL track (no migration)
#   SKIP_MULTI_INSTANCE=1 bash test_migration.sh      # skip the slower phase 8
#   bash test_migration.sh --auto                     # non-interactive single vector
#   bash test_migration.sh --all                      # matrix: fresh + v1.0.0 + v2.0.1 + v2.1.0
#   bash test_migration.sh --skip-multi-instance      # CLI form of SKIP_MULTI_INSTANCE=1
#
# Environment variables:
#   DAAF_TEST_VERSION      Tag/branch to install (default: v2.0.1 -- the
#                          richest migration path: ZIP era, graft required)
#   DAAF_TEST_ERA          Override era pathway: "1", "2", or "3" (default:
#                          auto -- v1.0.0=1, v2.0.0/v2.0.1=2, everything
#                          else=3). Tags below v2.1.0 cannot run era 3: no
#                          scripts/host/install.sh exists at those tags.
#   DAAF_MIGRATION_BRANCH  Branch for migration script downloads
#                          (default: daaf_dev -- keep this tracking the branch
#                           currently under update-testing)
#   SKIP_MULTI_INSTANCE    Set to "1" to skip the multi-instance phase (8),
#                          which lengthens the run (fresh build + teardown)
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - git on the host PATH (Era 1 replays the documented git clone)
#   - Internet connection (to pull old versions from GitHub)
#   - This script must be run from a local clone of the DAAF repo
#     (it copies migrate_daaf.sh from the local repo)
#
# Which versions of the local scripts?
#   - migrate_daaf.sh and install.sh are taken from the LOCAL repo this harness
#     runs from (scripts/host/ two levels up). They must be checked out to the
#     branch under test -- typically the same branch as DAAF_MIGRATION_BRANCH
#     (default: daaf_dev). The harness tests THAT checkout's migration/install
#     logic.
#   - The OLD version being migrated FROM is controlled by DAAF_TEST_VERSION
#     and is fetched from GitHub at that tag (clone, ZIP, or install.sh
#     download depending on era), independent of the local repo.
#
# ----------------------------------------------------------------------------
# TWO TRACKS
# ----------------------------------------------------------------------------
#   MIGRATION TRACK (default): install an OLD version the era-authentic way,
#     plant fixtures, run migrate_daaf.sh, then (in --auto) drive update_daaf.sh,
#     and verify the end state. This is everything below Phase 2.
#   FRESH-INSTALL TRACK (DAAF_TEST_VERSION=fresh): no old version, no migration.
#     Runs the LOCAL install.sh from a clean slate, verifies the install landed
#     (container up, branch, host scripts present+executable, environment_settings
#     seeded, functional smoke), and asserts a second install is refused by the
#     existing-install guard. Exits after its own compact results block.
#
# ----------------------------------------------------------------------------
# INTERACTIVE vs AUTO
# ----------------------------------------------------------------------------
#   INTERACTIVE (default): migrate/update prompts are answered by the tester at
#     the TTY, exactly as an end user would. Phase 7 checks pass whichever way
#     the update offer is answered; newest-endpoint checks (Phase 7b) run only
#     if the captured migrate output shows an update actually ran.
#   AUTO (--auto, or DAAF_TEST_AUTO=1, implied by --all): forces the child
#     scripts non-interactive by exporting CI=1 (the IS_INTERACTIVE seam shared
#     by install.sh/migrate_daaf.sh: CI set => IS_INTERACTIVE=false =>
#     prompt_choice auto-selects the first valid choice: backup=y, strategy=1,
#     rebuild=y). Because migrate_daaf.sh SKIPS its update offer when
#     non-interactive, --auto drives update_daaf.sh itself from the host dir
#     after migration, enabling the Phase 7b newest-endpoint checks + class E.
#
# ----------------------------------------------------------------------------
# EXPECTED RUNTIME
# ----------------------------------------------------------------------------
#   A single migration vector with a cold Docker cache is ~15-30 min (old-era
#   builds are authentic and slow). The full --all matrix (fresh + 3 migration
#   vectors), each building at least once, is ~45-90+ min. Budget accordingly;
#   nothing here is fast, by design (the point is a real end-to-end pathway).
#
# ----------------------------------------------------------------------------
# FIXTURE MANIFEST (classes A-E)
# ----------------------------------------------------------------------------
#   Every fixture below is planted BEFORE migration and verified AFTER. Classes
#   B/C/D/E are capability-probed or mode-gated: when the probe/precondition is
#   not met (an old era lacks the target section, or update did not run) the
#   corresponding check is a SKIP, never a FAIL.
#
#   Class A  Always-on. New-file markers + a research project, committed and
#            uncommitted. Upstream owns none of these paths, so update merges
#            can never conflict on them. (Phases 4/5, original coverage.)
#   Class B  Appends to EXISTING framework files (merge/stash coverage):
#            B(i)  COMMITTED   Dockerfile "USER ADDITIONS" block append.
#                              Probe: grep 'USER ADDITIONS' /daaf/Dockerfile.
#                              Marker: # test-migration-marker-B: dockerfile-user-block
#            B(ii) UNCOMMITTED CLAUDE.md append (dirty tracked -> stash/pop path).
#                              Probe: grep 'Primary execution language' CLAUDE.md.
#                              Marker: <!-- test-migration-marker-Bii -->
#   Class C  COMMITTED CLAUDE.md prose append (merge coverage on a tracked file).
#            Probe: grep '## Identity' /daaf/CLAUDE.md.
#            Marker: test-migration-marker-C
#   Class D  HOST-side environment_settings.txt byte-identity across migration
#            (and update). cksum captured pre-migration, re-checked in Phase 7.
#            Applicable only when the era's install seeded the file.
#   Class E  Host-script DRIFT-HEAL (auto-mode only). A marker line is appended
#            to <host>/view_logs.sh before update; a healthy update re-syncs the
#            script (marker gone) and backs up the drifted copy as
#            view_logs.sh.pre-update. Verified in Phase 7b.
#
#   NOTE on B/C appends to tracked framework files: these deliberately exercise
#   the updater's merge/stash paths that class-A new-file markers cannot. Appends
#   land at END-OF-FILE, which 3-way-merges cleanly unless upstream also rewrote
#   the file's final lines; if that ever happens the update aborts on a conflict
#   and the class B/C checks FAIL loudly -- which is the correct signal, not a
#   harness bug.
#
# ----------------------------------------------------------------------------
# FLAGS / ENV REFERENCE
# ----------------------------------------------------------------------------
#   CLI flags (parsed by tm_parse_args):
#     --all                  Run the whole matrix (implies --auto). Aggregates
#                            child TEST_MIGRATION_SUMMARY lines into a scoreboard.
#     --auto                 Non-interactive single vector (exports CI=1 to the
#                            child scripts; drives update itself).
#     --skip-multi-instance  Skip Phase 8 (CLI equivalent of SKIP_MULTI_INSTANCE=1).
#   Environment variables:
#     DAAF_TEST_VERSION          Tag/branch to install, or "fresh" (default v2.0.1).
#     DAAF_TEST_ERA              Force era pathway 1|2|3 (default: auto by version).
#     DAAF_MIGRATION_BRANCH      Branch whose migrate/install/host scripts are tested.
#     DAAF_TEST_AUTO=1           Env equivalent of --auto.
#     DAAF_TEST_MATRIX=1         Env equivalent of --all.
#     DAAF_TEST_MATRIX_VERSIONS  Override the matrix vector list (space-separated).
#     DAAF_TEST_MATRIX_FULL_MULTI=1  Let matrix children run Phase 8 (default: they
#                                skip it for speed; the fresh vector never runs it).
#     SKIP_MULTI_INSTANCE=1      Skip Phase 8.
#     DAAF_TEST_MODE=1           Source-only: define functions (incl. tm_*) and
#                                return before any execution (used by the bats suite).
#
# ----------------------------------------------------------------------------
# MACHINE-READABLE SUMMARY
# ----------------------------------------------------------------------------
#   Every single-vector run emits exactly ONE line, as its final stdout line
#   (from the EXIT trap), in this grammar:
#     TEST_MIGRATION_SUMMARY vector=<v> status=<PASS|FAIL|INFRA> pass=<n> fail=<n> skip=<n>
#   status semantics (tm_classify_status): INFRA = migration/work never reached
#   (setup broke); FAIL = the work ran but >=1 check failed; PASS = the work ran
#   and every non-skipped check passed. The --all matrix parses this line per
#   child to build its scoreboard and its own nonzero exit on any non-PASS.
#
# ----------------------------------------------------------------------------
# .sh / .ps1 DIVERGENCES (kept in sync with test_migration.ps1)
# ----------------------------------------------------------------------------
#   Four platform divergences, each forced by a real Windows/PowerShell constraint:
#   1. Non-interactive seam: the .sh rides CI=1 (IS_INTERACTIVE=false); the .ps1
#      reads no CI var and instead detects [Console]::IsInputRedirected, so its
#      auto mode REDIRECTS the child's stdin from an empty file (same net effect:
#      prompts auto-select the first valid choice). The .sh child scripts pass
#      DAAF_NESTED per-invocation and do not clobber it, so no stray exit-pause is
#      expected on this side.
#   2. Existing-install refusal: install.sh's refusal path exits nonzero;
#      install.ps1's ends in `Wait-ForUser; return`, so a refused re-install exits
#      0. The fresh track therefore asserts the refusal STRING in captured output
#      on the .ps1 side, never a nonzero exit code.
#   3. Interactive child-output capture: the .sh tees child output even
#      interactively (so it can detect an update from migrate's own offer); an
#      interactive .ps1 cannot capture console-inherited child output, so Phase 7b
#      (newest-endpoint) coverage requires auto mode there.
#   4. Host-script executable bit + set: the .sh asserts `-x` on downloaded host
#      scripts; Windows has no executable bit, so the .ps1 uses a Test-Path
#      presence check only. The host-script SET also differs -- the .sh expects
#      daaf.sh + daaf_lib.sh (the macOS/Linux Control Panel), the .ps1 the .ps1
#      variants and never daaf.sh/daaf_lib.sh (commit 4fa8c43) -- reflected in the
#      fresh track and Check 9's list.
#   (The B(i)/B(ii) three-way + Class C observe-only fixture semantics are now
#   shared by both twins -- no longer a divergence.)
#   install.sh existence is guarded before the fresh track and before the
#   multi-instance bring-up in both twins (shared behavior, not a divergence).
#
# ============================================================================

set -euo pipefail

# --- Color setup ---
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    RED=$(tput setaf 1)
    GREEN=$(tput setaf 2)
    YELLOW=$(tput setaf 3)
    CYAN=$(tput setaf 6)
    BOLD=$(tput bold)
    RESET=$(tput sgr0)
else
    RED="" GREEN="" YELLOW="" CYAN="" BOLD="" RESET=""
fi

info()    { echo "${CYAN}INFO:${RESET} $*" >&2; }
success() { echo "${GREEN}SUCCESS:${RESET} $*" >&2; }
warn()    { echo "${YELLOW}WARNING:${RESET} $*" >&2; }
error()   { echo "${RED}ERROR:${RESET} $*" >&2; }

# ============================================================================
# Pure helper functions (tm_*)  --  no docker, no network, unit-testable
# ============================================================================
# These carry no side effects beyond stdout and their own return code, so the
# bats suite (tests/bash/test_migration.bats) can `DAAF_TEST_MODE=1 source` this
# file and exercise them directly. Keep them Bash 3.2 clean (no associative
# arrays, no ${x^^}, no mapfile).

tm_detect_era() {
    # Map a version string to its authentic install-era pathway.
    #   v1.0.0           -> 1 (clone)
    #   v2.0.0 / v2.0.1  -> 2 (ZIP)
    #   everything else  -> 3 (install.sh / branch)
    # A DAAF_TEST_ERA override belongs to the CALLER, not here.
    case "$1" in
        v1.0.0)        echo "1" ;;
        v2.0.0|v2.0.1) echo "2" ;;
        *)             echo "3" ;;
    esac
}

tm_version_ge_floor() {
    # Compare a vX.Y.Z tag against the Era-3 floor (v2.1.0 = 2001000):
    #   return 0  tag >= v2.1.0
    #   return 1  tag <  v2.1.0
    #   return 2  not a vX.Y.Z tag (a branch name) -- caller decides
    # 10# prefixes stop a zero-padded component being mis-read as octal; the
    # single-integer encoding keeps "v2.10.0" > "v2.2.0" (a lexical compare fails).
    if [[ "$1" =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
        local encoded
        encoded=$(( (10#${BASH_REMATCH[1]}) * 1000000 + (10#${BASH_REMATCH[2]}) * 1000 + (10#${BASH_REMATCH[3]}) ))
        if [ "${encoded}" -ge 2001000 ]; then
            return 0
        fi
        return 1
    fi
    return 2
}

tm_matrix_vectors() {
    # The default matrix: the fresh-install track plus one vector per era.
    echo "${DAAF_TEST_MATRIX_VERSIONS:-fresh v1.0.0 v2.0.1 v2.1.0}"
}

tm_emit_summary() {
    # tm_emit_summary <vector> <status> <pass> <fail> <skip>
    # The single machine-readable line the matrix driver (and any CI wrapper)
    # parses. Field order is fixed; see tm_parse_summary_field.
    printf 'TEST_MIGRATION_SUMMARY vector=%s status=%s pass=%s fail=%s skip=%s\n' \
        "$1" "$2" "$3" "$4" "$5"
}

tm_parse_summary_field() {
    # tm_parse_summary_field <summary-line> <field-name> -> echoes the value.
    # Splits on spaces so a value can never span a field boundary.
    echo "$1" | tr ' ' '\n' | sed -n "s/^${2}=//p" | head -1
}

tm_classify_status() {
    # tm_classify_status <migration_reached:true|false> <fail_count>
    #   INFRA  the meaningful work never ran (setup broke before migration/install)
    #   FAIL   the work ran but >=1 check failed
    #   PASS   the work ran and every non-skipped check passed
    if [ "$1" != "true" ]; then
        echo "INFRA"
        return 0
    fi
    if [ "${2:-0}" -gt 0 ]; then
        echo "FAIL"
        return 0
    fi
    echo "PASS"
}

tm_matrix_verdict() {
    # tm_matrix_verdict <status> <rc> -> return 0 (vector passed) / 1 (vector failed)
    # Reconcile the parsed summary status against the child's ACTUAL exit code: a
    # vector passes only when the child reported PASS *and* exited zero. A nonzero
    # child rc fails the vector even when status=PASS (a summary line can report
    # PASS while a later teardown/exit path returns nonzero). Any non-PASS status
    # (FAIL, INFRA, or an UNKNOWN(rc=N) placeholder) also fails. rc defaults to 0.
    if [ "$1" = "PASS" ] && [ "${2:-0}" -eq 0 ]; then
        return 0
    fi
    return 1
}

tm_parse_args() {
    # Iterate argv and set the RUN_ALL / AUTO_MODE / SKIP_MULTI_CLI globals.
    # --all implies --auto (a matrix cannot pause for prompts). Unknown tokens
    # are ignored so an env-driven child invocation (which passes no args) is a
    # no-op here.
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --all)                 RUN_ALL=1; AUTO_MODE=1 ;;
            --auto)                AUTO_MODE=1 ;;
            --skip-multi-instance) SKIP_MULTI_CLI=1 ;;
            *)                     : ;;
        esac
        shift
    done
}

# --- Source-only guard (D8) ---
# When sourced with DAAF_TEST_MODE=1, return here: the bats suite gets the tm_*
# functions above without running any of the harness body below. Placed AFTER
# all pure-function definitions and BEFORE arg parsing / execution, mirroring the
# guard in migrate_daaf.sh / install.sh / update_daaf.sh / rebuild_daaf.sh.
if [ "${DAAF_TEST_MODE:-}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi

# --- Argument / mode parsing ---
RUN_ALL=0
AUTO_MODE=0
SKIP_MULTI_CLI=0
tm_parse_args "$@"

# Env fallbacks: the non-CLI entry points. The matrix driver re-invokes children
# with DAAF_TEST_AUTO=1 (not --auto), and CI wrappers may prefer env toggles.
if [ "${DAAF_TEST_MATRIX:-}" = "1" ]; then RUN_ALL=1; fi
if [ "${DAAF_TEST_AUTO:-}" = "1" ]; then AUTO_MODE=1; fi
if [ "${SKIP_MULTI_INSTANCE:-}" = "1" ]; then SKIP_MULTI_CLI=1; fi
# A matrix run is always non-interactive (mirror --all's implication for the
# DAAF_TEST_MATRIX=1 env path).
if [ "${RUN_ALL}" = "1" ]; then AUTO_MODE=1; fi
# Fold the unified skip flag back onto SKIP_MULTI_INSTANCE so the existing Phase 8
# gate + banner honor a --skip-multi-instance CLI flag without further edits.
if [ "${SKIP_MULTI_CLI}" = "1" ]; then
    SKIP_MULTI_INSTANCE=1
fi

# --- Matrix driver (--all / DAAF_TEST_MATRIX=1) ---
# Runs the whole vector list as CHILD processes of this same script (one clean
# process per vector -- no cross-vector state), tees each child's combined output
# to a per-vector log under a mktemp-d root, parses the child's final
# TEST_MIGRATION_SUMMARY line, and builds a scoreboard. Exits nonzero if any
# child was not PASS. This branch EXITs before the single-vector setup below, so
# no single-vector EXIT trap or summary is installed for the driver itself.
if [ "${RUN_ALL}" = "1" ]; then
    _self_dir="$(cd "$(dirname "$0")" && pwd)"
    SELF_PATH="${_self_dir}/$(basename "$0")"
    MATRIX_DIR="$(mktemp -d)"
    MATRIX_STAMP="$(date +%Y%m%d-%H%M%S)"
    MATRIX_LOGDIR="${MATRIX_DIR}/matrix-${MATRIX_STAMP}"
    mkdir -p "${MATRIX_LOGDIR}"

    echo ""
    echo "${BOLD}==========================================${RESET}"
    echo "${BOLD}  DAAF Migration Test -- MATRIX (--all)${RESET}"
    echo "${BOLD}==========================================${RESET}"
    echo ""
    echo "  Vectors:  $(tm_matrix_vectors)"
    echo "  Logs:     ${MATRIX_LOGDIR}"
    echo ""

    # Children skip Phase 8 by default (each build+teardown is expensive); opt in
    # with DAAF_TEST_MATRIX_FULL_MULTI=1. The fresh vector never runs Phase 8.
    child_skip=1
    if [ "${DAAF_TEST_MATRIX_FULL_MULTI:-}" = "1" ]; then
        child_skip=0
    fi

    MATRIX_FAIL=0
    SCOREBOARD=""
    for vec in $(tm_matrix_vectors); do
        this_skip="${child_skip}"
        if [ "${vec}" = "fresh" ]; then
            this_skip=1
        fi
        logf="${MATRIX_LOGDIR}/${vec}.log"
        echo "${BOLD}--- vector: ${vec} ---${RESET}"
        set +e
        # DAAF_TEST_MATRIX is cleared for children: on the env entry path
        # (DAAF_TEST_MATRIX=1 bash test_migration.sh) the exported value would
        # otherwise be inherited and turn every child into another matrix
        # driver (infinite recursion). The --all flag path never exports it.
        env DAAF_TEST_MATRIX= \
            DAAF_TEST_VERSION="${vec}" \
            DAAF_TEST_AUTO=1 \
            SKIP_MULTI_INSTANCE="${this_skip}" \
            bash "${SELF_PATH}" 2>&1 | tee "${logf}"
        child_rc="${PIPESTATUS[0]}"
        set -e
        summary_line=$(grep '^TEST_MIGRATION_SUMMARY ' "${logf}" | tail -1 || true)
        vstatus=$(tm_parse_summary_field "${summary_line}" status)
        vpass=$(tm_parse_summary_field "${summary_line}" pass)
        vfail=$(tm_parse_summary_field "${summary_line}" fail)
        vskip=$(tm_parse_summary_field "${summary_line}" skip)
        # Reconcile the parsed status with the child's actual exit code (see
        # tm_matrix_verdict): a missing summary line falls back to UNKNOWN(rc=N);
        # a PASS status riding a nonzero child rc is annotated PASS(rc=N)! on the
        # scoreboard and counted as a failure by the verdict below.
        if [ -z "${vstatus}" ]; then
            vstatus="UNKNOWN(rc=${child_rc})"
            vlabel="${vstatus}"
        elif [ "${vstatus}" = "PASS" ] && [ "${child_rc}" -ne 0 ]; then
            vlabel="PASS(rc=${child_rc})!"
        else
            vlabel="${vstatus}"
        fi
        SCOREBOARD="${SCOREBOARD}\n  ${vec}: ${vlabel} (pass=${vpass:-?} fail=${vfail:-?} skip=${vskip:-?})"
        if ! tm_matrix_verdict "${vstatus}" "${child_rc}"; then
            MATRIX_FAIL=1
        fi
        echo ""
    done

    echo "${BOLD}==========================================${RESET}"
    echo "${BOLD}  Matrix Scoreboard${RESET}"
    echo "${BOLD}==========================================${RESET}"
    printf '%b\n' "${SCOREBOARD}"
    echo ""
    echo "  Per-vector logs: ${MATRIX_LOGDIR}"
    echo ""
    if [ "${MATRIX_FAIL}" -ne 0 ]; then
        error "One or more matrix vectors did not PASS."
        exit 1
    fi
    success "All matrix vectors passed."
    exit 0
fi

# --- Configuration ---
# Default install-from version: v2.0.1 -- the richest migration path (ZIP era:
# no remote, synthetic root commit, graft + permission-fix machinery all get
# exercised). Override with DAAF_TEST_VERSION for the other pathways.
readonly TEST_VERSION="${DAAF_TEST_VERSION:-v2.0.1}"
# Default migration branch: the branch whose migrate_daaf.sh + host scripts are
# under test. Keep this pointing at the CURRENT update-testing branch (today:
# daaf_dev). Overridable per-run via DAAF_MIGRATION_BRANCH without editing here.
readonly MIGRATION_BRANCH="${DAAF_MIGRATION_BRANCH:-daaf_dev}"
readonly REPO="DAAF-Contribution-Community/daaf"

# --- Era detection ---
# Era 1 = v1.0.0            clone-based: full .git, origin remote, branch main
# Era 2 = v2.0.0 / v2.0.1   ZIP-based: entrypoint git-inits a local-only repo
#                           (synthetic root commit, no remote)
# Era 3 = v2.1.0+ / branch  modern install.sh pathway (shipped at the ref)
# DAAF_TEST_ERA overrides the pathway (e.g. to run a branch through the ZIP
# flow); the auto-detect maps each version to the pathway its real users had.
if [ -n "${DAAF_TEST_ERA:-}" ]; then
    TEST_ERA="${DAAF_TEST_ERA}"
elif [ "${TEST_VERSION}" = "v1.0.0" ]; then
    TEST_ERA="1"
elif [ "${TEST_VERSION}" = "v2.0.0" ] || [ "${TEST_VERSION}" = "v2.0.1" ]; then
    TEST_ERA="2"
else
    TEST_ERA="3"
fi
readonly TEST_ERA

case "${TEST_ERA}" in
    1|2|3) ;;
    *)
        error "DAAF_TEST_ERA '${TEST_ERA}' is invalid. Use 1 (clone), 2 (ZIP), or 3 (install.sh)."
        exit 1
        ;;
esac

# --- Era/version compatibility guard ---
# Era 3 downloads scripts/host/install.sh from the chosen ref; tags below
# v2.1.0 predate that layout entirely (the host helper set landed at v2.1.0,
# commit a399639), so the download fails. Fail fast with a clear message.
# Only vX.Y.Z tags are checked -- branch names always carry the current layout.
# Comparison parses numeric components (a lexical compare is wrong: "v2.10.0"
# sorts before "v2.2.0" lexically). Written bash-3.2-safe: [[ =~ ]] +
# BASH_REMATCH, and 10# arithmetic prefixes so a zero-padded component is
# never mis-read as octal.
if [ "${TEST_ERA}" = "3" ] && [[ "${TEST_VERSION}" =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
    req_major=$((10#${BASH_REMATCH[1]}))
    req_minor=$((10#${BASH_REMATCH[2]}))
    req_patch=$((10#${BASH_REMATCH[3]}))
    # Encode as a single comparable integer (each component < 1000). Era 3
    # floor is v2.1.0 = 2*1000000 + 1*1000 + 0.
    req_num=$(( req_major * 1000000 + req_minor * 1000 + req_patch ))
    if [ "${req_num}" -lt 2001000 ]; then
        error "Era 3 requires v2.1.0 or newer (${TEST_VERSION} ships no scripts/host/install.sh)."
        error "Remove DAAF_TEST_ERA and let auto-detection replay the authentic pathway for ${TEST_VERSION}."
        exit 1
    fi
fi

# --- Docker identifier derivation (default "daaf" instance) ---
# All identifiers are derived from DAAF_PROJECT_NAME rather than hardcoded, so a
# non-default install is testable and so this mirrors how nuke_daaf.sh /
# backup_daaf.sh derive their names. Docker joins the compose project name to the
# service with a DASH (containers/image) and to declared volumes with an
# UNDERSCORE (verified against docker-compose.yml). Default project name "daaf"
# reproduces the original hardcoded values byte-for-byte.
readonly PROJECT_NAME="${DAAF_PROJECT_NAME:-daaf}"
readonly VOLUME_NAME="${PROJECT_NAME}_daaf-data"
readonly CLAUDE_VOLUME_NAME="${PROJECT_NAME}_daaf-claude-config"
readonly CONTAINER_MAIN="${PROJECT_NAME}-daaf-docker-1"
readonly CONTAINER_INIT="${PROJECT_NAME}-daaf-init-1"
readonly IMAGE_NAME="${PROJECT_NAME}-daaf-docker"

# --- Second-instance identifiers (Phase 8 multi-instance pass) ---
# A distinct project name proves DAAF_PROJECT_NAME actually reprojects every
# Docker object. Same derivation rules as above.
readonly SECOND_PROJECT_NAME="daaftest2"
readonly SECOND_VOLUME_NAME="${SECOND_PROJECT_NAME}_daaf-data"
readonly SECOND_CLAUDE_VOLUME_NAME="${SECOND_PROJECT_NAME}_daaf-claude-config"
readonly SECOND_CONTAINER_MAIN="${SECOND_PROJECT_NAME}-daaf-docker-1"
readonly SECOND_CONTAINER_INIT="${SECOND_PROJECT_NAME}-daaf-init-1"
readonly SECOND_IMAGE_NAME="${SECOND_PROJECT_NAME}-daaf-docker"
# Distinct host ports so the second instance does not collide with the first on
# the same host. Container ports stay fixed (2718/2719/2720); only the published
# host port varies. These key names match environment_settings_example.txt and
# the compose interpolation (DAAF_PORT_MARIMO / _LOGVIEWER / _VSCODE).
readonly SECOND_PORT_MARIMO="12718"
readonly SECOND_PORT_LOGVIEWER="12719"
readonly SECOND_PORT_VSCODE="12720"

# --- Era 1/2 project-name guard ---
# The historical pathways predate DAAF_PROJECT_NAME entirely: v1.0.0's compose
# file has no `name:` key (project name = directory name, which the documented
# flow fixes as "daaf"), and v2.0.x hardcodes `name: daaf`. A non-default
# project name is only meaningful for Era 3.
if [ "${TEST_ERA}" != "3" ] && [ "${PROJECT_NAME}" != "daaf" ]; then
    error "Era ${TEST_ERA} replays a pathway that predates DAAF_PROJECT_NAME;"
    error "only the default 'daaf' project is supported (got: '${PROJECT_NAME}')."
    exit 1
fi

# Locate the local repo root (where this script lives)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# The repo root is two levels up from scripts/host/
LOCAL_REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Verify local migrate_daaf.sh exists
if [ ! -f "${LOCAL_REPO_ROOT}/scripts/host/migrate_daaf.sh" ]; then
    error "Cannot find migrate_daaf.sh in the local repo."
    error "Expected at: ${LOCAL_REPO_ROOT}/scripts/host/migrate_daaf.sh"
    error "Run this script from within a DAAF repo clone."
    exit 1
fi

# Working directory for the test install
TEST_DIR="$(mktemp -d)"

# --- Test-result + summary state ---
# Initialized BEFORE the EXIT trap so the summary emitter inside cleanup() never
# dereferences an unset global if the script exits during early setup.
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0
FAILURES=""
SKIPS=""
VECTOR_NAME="${TEST_VERSION}"     # the vector this process reports as
MIGRATION_REACHED=false           # flipped true once the meaningful work begins
SUMMARY_EMITTED=false             # guards single emission of the summary line

cleanup() {
    info "Test working directory preserved at: ${TEST_DIR}"
    info "(Delete manually when done inspecting: rm -rf ${TEST_DIR})"
    # Pause before exit so the user can review output. Suppressed in --auto/matrix
    # mode (AUTO_MODE=1) in addition to the existing DAAF_NESTED / CI / non-tty cases.
    if [ "${AUTO_MODE:-0}" != "1" ] && [ -z "${DAAF_NESTED:-}" ] && [ -z "${CI:-}" ] && [ -c /dev/tty ] && [ -t 1 ]; then
        echo ""
        read -r -p "Press Enter to continue: " < /dev/tty
    fi
    # Machine-readable summary: emitted exactly ONCE, as the final stdout line,
    # so the matrix driver (and any CI wrapper) can parse this vector's outcome
    # regardless of where execution stopped. The SUMMARY_EMITTED guard prevents a
    # double line if cleanup somehow runs twice.
    if [ "${SUMMARY_EMITTED}" != "true" ]; then
        SUMMARY_EMITTED=true
        _final_status=$(tm_classify_status "${MIGRATION_REACHED}" "${TESTS_FAILED}")
        tm_emit_summary "${VECTOR_NAME}" "${_final_status}" "${TESTS_PASSED}" "${TESTS_FAILED}" "${TESTS_SKIPPED}"
    fi
}
trap cleanup EXIT

check() {
    local description="$1"
    local result="$2"
    if [ "${result}" = "0" ]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        echo "  ${GREEN}PASS${RESET}: ${description}"
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        FAILURES="${FAILURES}\n  FAIL: ${description}"
        echo "  ${RED}FAIL${RESET}: ${description}"
    fi
}

skip_note() {
    # Record an intentional skip: a check that does not apply to this vector/mode,
    # or whose fixture could not be planted (capability probe missed). A skip is
    # NOT a failure and does not affect PASS/FAIL classification.
    local description="$1"
    TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
    SKIPS="${SKIPS}\n  SKIP: ${description}"
    echo "  ${YELLOW}SKIP${RESET}: ${description}"
}

observe_note() {
    # Informational line (neither pass/fail/skip) -- context for the reader.
    echo "  ${CYAN}NOTE${RESET}: $*"
}

echo ""
echo "${BOLD}==========================================${RESET}"
echo "${BOLD}  DAAF Migration Test${RESET}"
echo "${BOLD}==========================================${RESET}"
echo ""
case "${TEST_ERA}" in
    1) ERA_LABEL="clone-based" ;;
    2) ERA_LABEL="ZIP-based" ;;
    *) ERA_LABEL="modern install.sh" ;;
esac
readonly ERA_LABEL

echo "  Version:   ${TEST_VERSION}"
echo "  Era:       ${TEST_ERA} (${ERA_LABEL})"
echo "  Migration: from local repo (branch: ${MIGRATION_BRANCH})"
echo "  Work dir:  ${TEST_DIR}"
echo "  Mode:      $([ "${AUTO_MODE}" = "1" ] && echo "auto (non-interactive)" || echo "interactive")"
echo "  Multi:     $([ "${SKIP_MULTI_INSTANCE:-}" = "1" ] && echo "skipped (SKIP_MULTI_INSTANCE=1)" || echo "enabled (phase 8)")"
echo ""

# --- Container helpers ---
# Defined ONCE, up front, rather than re-defined inside each phase. Both read the
# current value of the CONTAINER_NAME global at call time, so re-discovering the
# container (Phase 3 / Phase 7) just reassigns CONTAINER_NAME -- no redefinition
# needed. This mirrors how migrate_daaf.sh defines its container helpers once at
# the top, and it avoids the "function defined later" (SC2218) heuristic that a
# per-phase definition triggers.
CONTAINER_NAME=""
container_exec() {
    docker exec "${CONTAINER_NAME}" "$@" </dev/null
}
container_git() {
    docker exec "${CONTAINER_NAME}" git -C /daaf "$@" </dev/null 2>/dev/null | tr -d '\r'
}

# =====================================================================
# PHASE 1: Clean Slate
# =====================================================================
echo "[1/7] ${BOLD}Clean slate${RESET}"
echo "${BOLD}-------------------------------------------${RESET}"
echo ""

# Preflight
if ! command -v docker >/dev/null 2>&1; then
    error "Docker not found. Install Docker Desktop first."
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    error "Docker daemon is not running. Start Docker Desktop first."
    exit 1
fi

info "Removing any existing DAAF Docker resources..."

# Stop and remove containers (default instance)
docker rm -f "${CONTAINER_MAIN}" 2>/dev/null || true
docker rm -f "${CONTAINER_INIT}" 2>/dev/null || true

# Remove the data volume
docker volume rm "${VOLUME_NAME}" 2>/dev/null || true

# Remove the Claude Code state volume too. A prior run (or a migrated install)
# creates this once the current compose file is in play; leaving it behind would
# leak Claude auth/session state across test runs. Absence is tolerated (older
# installs predate it) -- the `|| true` swallows "no such volume".
docker volume rm "${CLAUDE_VOLUME_NAME}" 2>/dev/null || true

# Remove the image
docker rmi "${IMAGE_NAME}" 2>/dev/null || true

# Clean up any leftovers from a previous, possibly aborted, multi-instance pass
# (phase 8) so its state cannot poison this run's coexistence checks.
docker rm -f "${SECOND_CONTAINER_MAIN}" 2>/dev/null || true
docker rm -f "${SECOND_CONTAINER_INIT}" 2>/dev/null || true
docker volume rm "${SECOND_VOLUME_NAME}" 2>/dev/null || true
docker volume rm "${SECOND_CLAUDE_VOLUME_NAME}" 2>/dev/null || true
docker rmi "${SECOND_IMAGE_NAME}" 2>/dev/null || true

success "Clean slate achieved."
echo ""

# =====================================================================
# FRESH-INSTALL TRACK (DAAF_TEST_VERSION=fresh) -- no migration
# =====================================================================
# Exercises the LOCAL install.sh end to end from the clean slate above, then
# asserts the install landed and that a second install is refused. Exits after
# its own compact results block (the migration phases below do not apply).
if [ "${TEST_VERSION}" = "fresh" ]; then
    echo "[2/2] ${BOLD}Fresh-install track (local install.sh)${RESET}"
    echo ""

    # D7 guard: install.sh must exist in the local repo (mirror of the .ps1 Test-Path).
    if [ ! -f "${LOCAL_REPO_ROOT}/scripts/host/install.sh" ]; then
        error "Cannot find install.sh in the local repo -- fresh-install track needs it."
        error "Expected at: ${LOCAL_REPO_ROOT}/scripts/host/install.sh"
        exit 1
    fi

    FRESH_DIR="${TEST_DIR}/fresh"
    mkdir -p "${FRESH_DIR}"
    cd "${FRESH_DIR}" || { error "Cannot enter fresh install dir: ${FRESH_DIR}"; exit 1; }

    # 'Reached the meaningful work' -- classify PASS/FAIL, not INFRA. (There is no
    # migration in this track; MIGRATION_REACHED doubles as a work-started flag.)
    MIGRATION_REACHED=true

    info "Running local install.sh (branch ${MIGRATION_BRANCH})..."
    echo ""
    FRESH_INSTALL_EXIT=0
    if (
        export DAAF_BRANCH="${MIGRATION_BRANCH}"
        export DAAF_NESTED=1
        if [ "${AUTO_MODE}" = "1" ]; then export CI=1; fi
        bash "${LOCAL_REPO_ROOT}/scripts/host/install.sh"
    ); then
        FRESH_INSTALL_EXIT=0
    else
        FRESH_INSTALL_EXIT=$?
    fi
    echo ""

    if [ "${FRESH_INSTALL_EXIT}" -eq 0 ]; then
        check "Fresh install completed (exit 0)" "0"
    else
        error "Fresh install.sh did NOT complete successfully (exit ${FRESH_INSTALL_EXIT})."
        check "Fresh install completed (exit ${FRESH_INSTALL_EXIT})" "1"
    fi

    # Discover the freshly-created container and wait for exec readiness.
    CONTAINER_NAME=$(docker ps -a --filter "volume=${VOLUME_NAME}" --format '{{.Names}}' | head -1)
    if [ -n "${CONTAINER_NAME}" ]; then
        CONTAINER_STATE=$(docker inspect --format '{{.State.Status}}' "${CONTAINER_NAME}" 2>/dev/null || echo "unknown")
        if [ "${CONTAINER_STATE}" != "running" ]; then
            docker start "${CONTAINER_NAME}" >/dev/null 2>&1 || true
        fi
        RETRIES=0
        while [ "${RETRIES}" -lt 30 ]; do
            if container_exec true >/dev/null 2>&1; then
                break
            fi
            RETRIES=$((RETRIES + 1))
            sleep 2
        done
    fi

    if [ -n "${CONTAINER_NAME}" ] && container_exec true >/dev/null 2>&1; then
        check "Fresh container is exec-ready (${CONTAINER_NAME})" "0"
    else
        check "Fresh container is exec-ready" "1"
    fi

    # Branch check: install.sh clones the branch and leaves it checked out.
    FRESH_BRANCH=$(container_git branch --show-current 2>/dev/null || echo "")
    if [ "${FRESH_BRANCH}" = "${MIGRATION_BRANCH}" ]; then
        check "Fresh install checked out branch ${MIGRATION_BRANCH}" "0"
    else
        check "Fresh install checked out branch ${MIGRATION_BRANCH} (got: '${FRESH_BRANCH}')" "1"
    fi

    # Host scripts present + executable in the fresh daaf-docker dir.
    FRESH_HOST_DIR="${FRESH_DIR}/daaf-docker"
    for SCRIPT in daaf.sh daaf_lib.sh backup_daaf.sh restore_from_backup.sh rebuild_daaf.sh update_daaf.sh run_daaf.sh view_logs.sh view_notebooks.sh view_quarto.sh run_vscode.sh; do
        if [ -f "${FRESH_HOST_DIR}/${SCRIPT}" ] && [ -x "${FRESH_HOST_DIR}/${SCRIPT}" ]; then
            check "Fresh host script present + executable: ${SCRIPT}" "0"
        else
            check "Fresh host script present + executable: ${SCRIPT}" "1"
        fi
    done

    # environment_settings.txt seeded by install.sh.
    if [ -f "${FRESH_HOST_DIR}/environment_settings.txt" ]; then
        check "Fresh install seeded environment_settings.txt" "0"
    else
        check "Fresh install seeded environment_settings.txt" "1"
    fi

    # Functional smoke: git describe sane + hooks present.
    FRESH_GIT_DESC=$(container_git describe --tags --always 2>/dev/null || echo "")
    if [ -n "${FRESH_GIT_DESC}" ]; then
        check "Fresh install git describe returns a sane ref (${FRESH_GIT_DESC})" "0"
    else
        check "Fresh install git describe returns a sane ref" "1"
    fi
    if container_exec test -d /daaf/.claude/hooks; then
        check "Fresh install framework hooks present (.claude/hooks)" "0"
    else
        check "Fresh install framework hooks present (.claude/hooks)" "1"
    fi

    # Second install must be REFUSED by the existing-install guard (D3). Run it
    # again WITHOUT DAAF_FORCE_REINSTALL; expect a nonzero exit + the refusal text.
    info "Verifying a second install is refused by the existing-install guard..."
    SECOND_INSTALL_OUT="${FRESH_DIR}/second_install.out"
    SECOND_INSTALL_EXIT=0
    if (
        export DAAF_BRANCH="${MIGRATION_BRANCH}"
        export DAAF_NESTED=1
        if [ "${AUTO_MODE}" = "1" ]; then export CI=1; fi
        bash "${LOCAL_REPO_ROOT}/scripts/host/install.sh"
    ) >"${SECOND_INSTALL_OUT}" 2>&1; then
        SECOND_INSTALL_EXIT=0
    else
        SECOND_INSTALL_EXIT=$?
    fi
    if [ "${SECOND_INSTALL_EXIT}" -ne 0 ] && grep -q "existing DAAF installation was detected" "${SECOND_INSTALL_OUT}"; then
        check "Second fresh install refused (existing-install guard fired)" "0"
    else
        check "Second fresh install refused (existing-install guard fired) (exit ${SECOND_INSTALL_EXIT})" "1"
    fi

    # --- Fresh-track results ---
    echo ""
    echo "${BOLD}==========================================${RESET}"
    echo "${BOLD}  Fresh-Install Track Results${RESET}"
    echo "${BOLD}==========================================${RESET}"
    echo ""
    echo "  Passed:   ${GREEN}${TESTS_PASSED}${RESET}"
    echo "  Failed:   ${TESTS_FAILED}"
    echo "  Skipped:  ${TESTS_SKIPPED}"
    echo ""
    if [ "${TESTS_FAILED}" -gt 0 ]; then
        echo "${RED}  Failures:${RESET}"
        printf '%b\n' "${FAILURES}"
        echo ""
        error "Fresh-install track: some checks failed."
        exit 1
    fi
    success "Fresh-install track: all checks passed!"
    exit 0
fi

# =====================================================================
# PHASE 2: Install Old Version (era-authentic pathway)
# =====================================================================
echo "[2/7] ${BOLD}Install ${TEST_VERSION} (Era ${TEST_ERA} pathway: ${ERA_LABEL})${RESET}"
echo ""

cd "${TEST_DIR}" || { error "Cannot enter test directory: ${TEST_DIR}"; exit 1; }

# HOST_DIR is where migrate_daaf.sh will be run from in Phase 6 -- for each era
# this is the directory a real user would have run it from (the one holding
# docker-compose.yml).
HOST_DIR=""
# Era 2 only: the synthetic root commit's SHA, captured in Phase 3 before
# migration can graft it (initialized here for set -u safety on other eras).
ERA2_ROOT_SHA=""

if [ "${TEST_ERA}" = "1" ]; then
    # ----- Era 1: the documented v1.0.0 pathway -----
    # Verbatim flow from v1.0.0 user_reference/01_installation_and_quickstart.md:
    #   git clone https://github.com/DAAF-Contribution-Community/daaf.git
    #   cd daaf
    #   docker run --rm -v "${PWD}:/source:ro" -v "daaf_daaf-data:/dest" busybox cp -a /source/. /dest/
    #   docker compose up -d --build
    # (v1.0.0's busybox copy has NO sh -c wrapper -- that arrived in v2.0.0.)
    if ! command -v git >/dev/null 2>&1; then
        error "git not found on the host PATH -- Era 1 replays the documented git clone."
        exit 1
    fi

    info "Cloning DAAF repo (documented v1.0.0 flow)..."
    CLONE_DIR="${TEST_DIR}/daaf"
    if ! git clone "https://github.com/${REPO}.git" "${CLONE_DIR}"; then
        error "git clone failed -- cannot replay the Era 1 install."
        exit 1
    fi

    # Time-machine deviation (see header): rewind main to the tag, because a
    # v1.0.0-era user's clone HAD main at v1.0.0. checkout -B moves the branch
    # pointer and working tree while keeping origin + tracking config intact.
    if ! git -C "${CLONE_DIR}" checkout -B main "${TEST_VERSION}"; then
        error "git checkout -B main ${TEST_VERSION} failed -- cannot pin the Era 1 tree."
        exit 1
    fi

    cd "${CLONE_DIR}" || { error "Cannot enter clone dir: ${CLONE_DIR}"; exit 1; }
    info "Copying the clone into the Docker volume (documented busybox step)..."
    if ! docker run --rm -v "${PWD}:/source:ro" -v "${VOLUME_NAME}:/dest" busybox cp -a /source/. /dest/; then
        error "busybox copy into volume ${VOLUME_NAME} failed."
        exit 1
    fi

    # v1.0.0's compose file has no `name:` key, so the compose project name
    # comes from THIS directory's name ("daaf") -- reproducing the era's
    # container/volume names (daaf-daaf-docker-1 / daaf_daaf-data).
    info "Building and starting the v1.0.0 container (docker compose up -d --build)..."
    info "This builds the OLD Dockerfile -- authentic and slow on a cold cache..."
    if ! docker compose up -d --build; then
        error "docker compose up failed for the v1.0.0 build. If the base image or"
        error "Claude installer has drifted upstream, that is a real finding about"
        error "resurrecting this era -- see the header BUILD COST note."
        exit 1
    fi
    HOST_DIR="${CLONE_DIR}"

elif [ "${TEST_ERA}" = "2" ]; then
    # ----- Era 2: the documented v2.0.x ZIP pathway -----
    # Verbatim flow from v2.0.x user_reference/01_installation_and_quickstart.md
    # (macOS/Linux variant):
    #   curl -L -o daaf.zip https://github.com/.../archive/refs/heads/main.zip
    #   unzip daaf.zip
    #   cd daaf-main
    #   docker run --rm -v "${PWD}:/source:ro" -v "daaf_daaf-data:/dest" busybox sh -c 'cp -a /source/. /dest/'
    #   docker compose up -d --build
    # Time-machine deviation (see header): the TAG's ZIP stands in for that
    # era's main.zip. No .git comes out of a ZIP; the era's container
    # entrypoint git-inits /daaf on first start (verified verbatim at both
    # tags: git init, branch -m main, add -A, commit "Initial commit: DAAF
    # framework", NO remote) -- Phase 3 waits for and verifies that.
    if ! command -v unzip >/dev/null 2>&1; then
        error "unzip not found on the host PATH -- Era 2 replays the documented ZIP flow."
        exit 1
    fi

    info "Downloading release ZIP (documented v2.0.x flow, pinned to the tag)..."
    if ! curl -fsSL -o "${TEST_DIR}/daaf.zip" "https://github.com/${REPO}/archive/refs/tags/${TEST_VERSION}.zip"; then
        error "Failed to download the ${TEST_VERSION} ZIP from GitHub."
        exit 1
    fi
    if ! unzip -q "${TEST_DIR}/daaf.zip" -d "${TEST_DIR}"; then
        error "Failed to extract ${TEST_DIR}/daaf.zip."
        exit 1
    fi

    # GitHub names the ZIP's root folder <repo>-<ref> (with a version-like
    # tag's leading "v" stripped) -- detect it instead of hardcoding.
    # `|| true` guards the low-probability find-vs-head SIGPIPE race under
    # `set -e` (head -1 closing the pipe before find finishes writing).
    EXTRACT_DIR=$(find "${TEST_DIR}" -maxdepth 1 -type d -name 'daaf-*' | head -1 || true)
    if [ -z "${EXTRACT_DIR}" ]; then
        error "Could not find the extracted daaf-* folder under ${TEST_DIR}."
        exit 1
    fi

    cd "${EXTRACT_DIR}" || { error "Cannot enter extract dir: ${EXTRACT_DIR}"; exit 1; }
    info "Copying the extracted tree into the Docker volume (documented busybox step)..."
    if ! docker run --rm -v "${PWD}:/source:ro" -v "${VOLUME_NAME}:/dest" busybox sh -c 'cp -a /source/. /dest/'; then
        error "busybox copy into volume ${VOLUME_NAME} failed."
        exit 1
    fi

    # v2.0.x compose hardcodes `name: daaf`, so project naming is stable
    # regardless of this directory's name (daaf-2.0.1 etc.).
    info "Building and starting the ${TEST_VERSION} container (docker compose up -d --build)..."
    info "This builds the OLD Dockerfile -- authentic and slow on a cold cache..."
    if ! docker compose up -d --build; then
        error "docker compose up failed for the ${TEST_VERSION} build -- see the header BUILD COST note."
        exit 1
    fi
    HOST_DIR="${EXTRACT_DIR}"

else
    # ----- Era 3: the version's own install script (v2.1.0+ / branches) -----
    info "Installing DAAF via the ref's own install.sh from branch/tag: ${TEST_VERSION}"
    info "This will build the Docker image and clone the repo -- may take several minutes..."
    echo ""

    # Use the install script from the target version's own branch/tag. Download
    # to a temp file FIRST rather than `bash -c "$(curl ...)"`: on a curl
    # failure the command-substitution collapses to `bash -c ""`, which exits 0
    # and silently no-ops -- the install never runs, and the failure only
    # surfaces later as a confusing "volume not found" error. Fetching to a
    # file lets us fail loudly and precisely here if the download fails or
    # comes back empty.
    INSTALL_SCRIPT="${TEST_DIR}/install_old.sh"
    if ! curl -fsSL "https://raw.githubusercontent.com/${REPO}/${TEST_VERSION}/scripts/host/install.sh" -o "${INSTALL_SCRIPT}"; then
        error "Failed to download install.sh for ${TEST_VERSION} from GitHub."
        error "Check your internet connection and that the tag/branch '${TEST_VERSION}' exists."
        exit 1
    fi
    if [ ! -s "${INSTALL_SCRIPT}" ]; then
        error "Downloaded install.sh for ${TEST_VERSION} is empty -- aborting."
        exit 1
    fi
    DAAF_BRANCH="${TEST_VERSION}" DAAF_NESTED=1 bash "${INSTALL_SCRIPT}"

    # install.sh creates ./daaf-docker under the invocation directory.
    HOST_DIR="${TEST_DIR}/daaf-docker"
fi

# Verify install succeeded
if ! docker volume inspect "${VOLUME_NAME}" >/dev/null 2>&1; then
    error "Installation failed -- volume ${VOLUME_NAME} not found."
    exit 1
fi
if [ ! -f "${HOST_DIR}/docker-compose.yml" ]; then
    warn "docker-compose.yml not found in ${HOST_DIR} -- migration will treat this as a compose-less host dir."
fi

success "DAAF ${TEST_VERSION} installed via the Era ${TEST_ERA} pathway."
echo ""

# =====================================================================
# PHASE 3: Verify Era State
# =====================================================================
# The old harness "simulated" Era 2 here by stripping the remote from a modern
# shallow clone. That never produced a real Era 2 repo (genuine upstream
# history remained, and the shallow boundary commit's visible parent lines
# fooled migrate_daaf's graft-already-in-place check into skipping the graft
# entirely). Phase 2 now replays the real pathways, so this phase only WAITS
# for and VERIFIES the era state the install should have produced -- if the
# state is wrong, that is a broken replay and the run stops here rather than
# feeding Phase 7 misleading results.
echo "[3/7] ${BOLD}Verify Era ${TEST_ERA} state${RESET}"
echo ""

# Discover container (CONTAINER_NAME is a global the helpers read)
CONTAINER_NAME=$(docker ps -a --filter "volume=${VOLUME_NAME}" --format '{{.Names}}' | head -1)
if [ -z "${CONTAINER_NAME}" ]; then
    error "No container found using volume ${VOLUME_NAME}."
    exit 1
fi

CONTAINER_STATE=$(docker inspect --format '{{.State.Status}}' "${CONTAINER_NAME}" 2>/dev/null || echo "unknown")
if [ "${CONTAINER_STATE}" != "running" ]; then
    info "Starting container ${CONTAINER_NAME}..."
    docker start "${CONTAINER_NAME}" >/dev/null 2>&1
fi

# Wait for exec readiness (fresh first boot can lag briefly)
RETRIES=0
while [ "${RETRIES}" -lt 30 ]; do
    if container_exec true >/dev/null 2>&1; then
        break
    fi
    RETRIES=$((RETRIES + 1))
    sleep 2
done
if [ "${RETRIES}" -ge 30 ]; then
    error "Container ${CONTAINER_NAME} did not become exec-ready within 60 seconds."
    exit 1
fi

if [ "${TEST_ERA}" = "1" ]; then
    # Era 1 expectation: /daaf carries the clone's full .git -- origin remote
    # pointing at the official repo, branch main checked out.
    ORIGIN_CHECK=$(container_git remote get-url origin 2>/dev/null || echo "")
    BRANCH_CHECK=$(container_git branch --show-current 2>/dev/null || echo "")
    if echo "${ORIGIN_CHECK}" | grep -qi "${REPO}" && [ "${BRANCH_CHECK}" = "main" ]; then
        success "Era 1 state verified (origin remote + branch main from the clone)."
    else
        error "Era 1 replay did not produce the expected state (origin: '${ORIGIN_CHECK}', branch: '${BRANCH_CHECK}')."
        error "Expected the documented clone flow to leave origin=${REPO} and branch=main."
        exit 1
    fi

elif [ "${TEST_ERA}" = "2" ]; then
    # Era 2 expectation: the era's entrypoint git-inits /daaf on FIRST start
    # (git init; branch -m main; add -A; commit "Initial commit: DAAF
    # framework"; no remote). The commit of the full tree can take a few
    # seconds after the container reports running -- wait for HEAD to exist.
    info "Waiting for the era's entrypoint to git-init /daaf (first boot)..."
    RETRIES=0
    HEAD_SHA=""
    while [ "${RETRIES}" -lt 30 ]; do
        HEAD_SHA=$(container_git rev-parse HEAD 2>/dev/null || echo "")
        case "${HEAD_SHA}" in
            ""|*HEAD*) ;;  # not ready yet (empty, or literal "HEAD" from an unborn branch)
            *) break ;;
        esac
        RETRIES=$((RETRIES + 1))
        sleep 2
    done
    case "${HEAD_SHA}" in
        ""|*HEAD*)
            error "Era 2 entrypoint never produced an initial commit in /daaf (waited 60s)."
            error "The ZIP-era replay is broken -- inspect container logs: docker logs ${CONTAINER_NAME}"
            exit 1
            ;;
    esac

    ORIGIN_CHECK=$(container_git remote get-url origin 2>/dev/null || echo "")
    BRANCH_CHECK=$(container_git branch --show-current 2>/dev/null || echo "")
    COMMIT_COUNT=$(container_git rev-list --count HEAD 2>/dev/null || echo "0")
    if [ -z "${ORIGIN_CHECK}" ] && [ "${BRANCH_CHECK}" = "main" ] && [ "${COMMIT_COUNT}" = "1" ]; then
        # Capture the synthetic root's SHA NOW, pre-migration. Check 3 must
        # interrogate THIS commit later: `git replace --graft` adds a
        # replacement ref rather than rewriting the root, so post-graft
        # `rev-list --max-parents=0 HEAD` walks THROUGH the grafted root into
        # upstream history and returns upstream's genuine root -- parentless
        # by definition, forever. Inspecting that commit produced a false
        # FAIL on a healthy migration (repro: scripts/scratch/graft_repro.sh
        # in the session workspace).
        ERA2_ROOT_SHA="${HEAD_SHA}"
        success "Era 2 state verified (local-only repo, single synthetic root commit ${HEAD_SHA:0:12}, no remote)."
    else
        error "Era 2 replay did not produce the expected state (origin: '${ORIGIN_CHECK}', branch: '${BRANCH_CHECK}', commits: '${COMMIT_COUNT}')."
        error "Expected: no remote, branch main, exactly 1 entrypoint commit."
        exit 1
    fi

else
    # Era 3 expectation: install.sh cloned with origin retained. For a TAG,
    # the shallow `-b <tag>` clone leaves a detached HEAD no real user had
    # (real users installed from branch main) -- normalize per the header note.
    ORIGIN_CHECK=$(container_git remote get-url origin 2>/dev/null || echo "")
    if [ -z "${ORIGIN_CHECK}" ]; then
        error "Era 3 install left no origin remote -- unexpected for the modern install pathway."
        exit 1
    fi

    if [[ "${TEST_VERSION}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        info "Normalizing tag install to a real user's git state (checkout -B main at the tag commit)..."
        container_git checkout -B main 2>/dev/null || true
        BRANCH_CHECK=$(container_git branch --show-current 2>/dev/null || echo "")
        if [ "${BRANCH_CHECK}" != "main" ]; then
            error "Era 3 normalization failed -- expected branch main, got '${BRANCH_CHECK}'."
            exit 1
        fi
    fi
    success "Era 3 state verified (origin remote present: ${ORIGIN_CHECK})."
fi

echo ""

# =====================================================================
# PHASE 4: Simulate User Work (Committed)
# =====================================================================
echo "[4/7] ${BOLD}Simulate committed user work${RESET}"
echo ""

info "Creating committed framework changes and research files..."

# FIXTURE RULES (mirrored with the .ps1 twin):
#   - Framework-change markers live in NEW files (upstream has no such path,
#     so update merges can never conflict on them). The old CLAUDE.md-append
#     markers were conflict bait: daaf_dev heavily rewrites CLAUDE.md relative
#     to the old eras, and a merge conflict would abort the update for reasons
#     unrelated to migration correctness.
#   - Fixture existence is verified BEFORE migration runs, so a broken fixture
#     aborts here instead of surfacing as a bogus "not preserved" FAIL later.

# Create a research project
container_exec mkdir -p /daaf/research/2026-01-15_Test_Analysis/data /daaf/research/2026-01-15_Test_Analysis/scripts /daaf/research/2026-01-15_Test_Analysis/output
container_exec bash -c 'cat > /daaf/research/2026-01-15_Test_Analysis/scripts/01_fetch.py << "PYEOF"
# --- Config ---
import polars as pl

BASE_DIR = "/daaf"
PROJECT_DIR = f"{BASE_DIR}/research/2026-01-15_Test_Analysis"

# --- Load ---
# INTENT: Fetch test data for migration verification
print("Test script executed successfully")
PYEOF'

container_exec bash -c 'echo "Test analysis data" > /daaf/research/2026-01-15_Test_Analysis/data/test_data.txt'
container_exec bash -c 'echo "# Test Analysis" > /daaf/research/2026-01-15_Test_Analysis/README.md'

# Make a framework modification: a NEW file under agent_reference/ (see
# FIXTURE RULES above for why this is not a CLAUDE.md append).
container_exec bash -c 'echo "test-migration-marker: committed" > /daaf/agent_reference/test_migration_marker.md'

# Commit everything
container_git add -A
container_git commit -m "Test: Add research project and framework tweaks"

COMMITTED_SHA=$(container_git rev-parse HEAD)
if [ -z "${COMMITTED_SHA}" ]; then
    error "Fixture commit failed -- no HEAD SHA readable. Cannot proceed to migration with unplanted fixtures."
    exit 1
fi
# Verify the fixtures actually landed IN the commit (the old harness only
# discovered missing fixtures at Phase 7, after migration had already run).
COMMITTED_FILES=$(container_git show --name-only --format= HEAD)
for MUST_HAVE in \
    "research/2026-01-15_Test_Analysis/scripts/01_fetch.py" \
    "research/2026-01-15_Test_Analysis/data/test_data.txt" \
    "agent_reference/test_migration_marker.md"; do
    if ! echo "${COMMITTED_FILES}" | grep -qF "${MUST_HAVE}"; then
        error "Fixture file '${MUST_HAVE}' is missing from the fixture commit -- aborting before migration."
        exit 1
    fi
done
info "Committed changes at: ${COMMITTED_SHA:0:12}"

# --- Class B(i) + Class C: COMMITTED appends to EXISTING framework files ---
# These exercise the updater's 3-way MERGE path on tracked files (class-A markers
# only ever test new-file preservation). Each is capability-probed: an old era
# that lacks the target section is recorded as a skip-at-plant (observe_note),
# not planted, so a legitimately-absent target never becomes a spurious FAIL. The
# appends land at EOF, which merges cleanly unless upstream also rewrote the
# file's final lines -- if that happens the update aborts and the class B/C
# preservation checks FAIL loudly, which is the correct signal.
PLANTED_B1=false
if container_exec grep -q 'USER ADDITIONS' /daaf/Dockerfile; then
    container_exec bash -c 'printf "\n# test-migration-marker-B: dockerfile-user-block\n" >> /daaf/Dockerfile'
    PLANTED_B1=true
    observe_note "Class B(i) planted: committed Dockerfile user-block append."
else
    observe_note "Class B(i) not planted: Dockerfile has no USER ADDITIONS block at ${TEST_VERSION}."
fi
PLANTED_C=false
if container_exec grep -q '## Identity' /daaf/CLAUDE.md; then
    container_exec bash -c 'printf "\n<!-- test-migration-marker-C: committed CLAUDE.md prose line -->\n" >> /daaf/CLAUDE.md'
    PLANTED_C=true
    observe_note "Class C planted: committed CLAUDE.md prose append."
else
    observe_note "Class C not planted: CLAUDE.md has no '## Identity' section at ${TEST_VERSION}."
fi
if [ "${PLANTED_B1}" = "true" ] || [ "${PLANTED_C}" = "true" ]; then
    container_git add -A
    container_git commit -m "Test: class B(i)/C framework-file appends"
    B1C_FILES=$(container_git show --name-only --format= HEAD)
    if [ "${PLANTED_B1}" = "true" ] && ! echo "${B1C_FILES}" | grep -qF "Dockerfile"; then
        error "Class B(i) fixture missing from its commit -- aborting before migration."
        exit 1
    fi
    if [ "${PLANTED_C}" = "true" ] && ! echo "${B1C_FILES}" | grep -qF "CLAUDE.md"; then
        error "Class C fixture missing from its commit -- aborting before migration."
        exit 1
    fi
fi

success "Committed user work created."
echo ""

# =====================================================================
# PHASE 5: Simulate User Work (Uncommitted)
# =====================================================================
echo "[5/7] ${BOLD}Simulate uncommitted user work${RESET}"
echo ""

info "Creating uncommitted framework changes and research files..."

# Add more uncommitted research files (untracked -- the updater never touches
# untracked files, so these must survive verbatim)
container_exec mkdir -p /daaf/research/2026-02-10_WIP_Analysis/scripts
container_exec bash -c 'echo "Work in progress data" > /daaf/research/2026-02-10_WIP_Analysis/notes.md'
container_exec bash -c 'cat > /daaf/research/2026-02-10_WIP_Analysis/scripts/01_explore.py << "PYEOF"
# --- Config ---
# INTENT: WIP exploration script -- uncommitted
print("WIP script")
PYEOF'

# Make an uncommitted framework change: a NEW untracked file (see Phase 4
# FIXTURE RULES for why this is not a CLAUDE.md append).
container_exec bash -c 'echo "test-migration-marker: uncommitted" > /daaf/agent_reference/test_migration_marker_uncommitted.md'

# Dirty a TRACKED file: append a line to the README committed in Phase 4.
# This is what exercises the updater's stash/pop path (dirty tracked changes
# get stashed before the merge and popped after). It lives in research/ where
# upstream never writes, so the pop can never conflict.
container_exec bash -c 'echo uncommitted-stash-check >> /daaf/research/2026-01-15_Test_Analysis/README.md'

# --- Class B(ii): UNCOMMITTED append to a tracked framework file (CLAUDE.md) ---
# A dirty tracked change on a framework file -- exercises the updater's stash/pop
# path on a file upstream also owns (stronger than the research/ dirty-file above,
# which upstream never touches). Capability-probed; skipped-at-plant if the target
# line is absent in this era.
PLANTED_B2=false
if container_exec grep -q 'Primary execution language' /daaf/CLAUDE.md; then
    container_exec bash -c 'printf "\n<!-- test-migration-marker-Bii -->\n" >> /daaf/CLAUDE.md'
    PLANTED_B2=true
    observe_note "Class B(ii) planted: uncommitted CLAUDE.md append (stash/pop path)."
else
    observe_note "Class B(ii) not planted: CLAUDE.md lacks 'Primary execution language' at ${TEST_VERSION}."
fi

# Verify the uncommitted fixtures actually exist before migration runs
for MUST_EXIST in \
    "/daaf/research/2026-02-10_WIP_Analysis/notes.md" \
    "/daaf/research/2026-02-10_WIP_Analysis/scripts/01_explore.py" \
    "/daaf/agent_reference/test_migration_marker_uncommitted.md"; do
    if ! container_exec test -f "${MUST_EXIST}"; then
        error "Uncommitted fixture '${MUST_EXIST}' was not created -- aborting before migration."
        exit 1
    fi
done
if ! container_exec grep -q uncommitted-stash-check /daaf/research/2026-01-15_Test_Analysis/README.md; then
    error "Dirty-file fixture (README.md append) was not created -- aborting before migration."
    exit 1
fi
if [ "${PLANTED_B2}" = "true" ] && ! container_exec grep -q 'test-migration-marker-Bii' /daaf/CLAUDE.md; then
    error "Class B(ii) uncommitted fixture (CLAUDE.md append) was not created -- aborting before migration."
    exit 1
fi

success "Uncommitted user work created."
echo ""

# =====================================================================
# PHASE 6: Run Migration
# =====================================================================
echo "[6/7] ${BOLD}Run migration script${RESET}"
echo ""

# We have reached the meaningful work -- outcome now classifies PASS/FAIL, not
# INFRA. (Setup failures before this point classify INFRA via tm_classify_status.)
MIGRATION_REACHED=true

info "Copying migration script from local repo..."

# The host directory is era-specific (set in Phase 2): the clone dir (Era 1),
# the extracted ZIP dir (Era 2), or install.sh's daaf-docker dir (Era 3) --
# i.e., wherever a real user of that era would run migrate_daaf.sh from (the
# directory holding docker-compose.yml).
if [ ! -d "${HOST_DIR}" ]; then
    error "Era host directory vanished: ${HOST_DIR}"
    exit 1
fi

# Copy the local migration script to the host dir
cp "${LOCAL_REPO_ROOT}/scripts/host/migrate_daaf.sh" "${HOST_DIR}/migrate_daaf.sh"
chmod +x "${HOST_DIR}/migrate_daaf.sh"

info "Running migration with DAAF_BRANCH=${MIGRATION_BRANCH}..."
echo ""

cd "${HOST_DIR}" || { error "Cannot enter host directory: ${HOST_DIR}"; exit 1; }

# Snapshot whether the Claude state volume exists RIGHT NOW, immediately before
# migration runs. The backup-content assertion (Check 11) needs to know whether
# the source volume existed AT BACKUP TIME, and backup happens inside migration.
# Capturing the flag here -- rather than re-inspecting live after migration --
# makes the gate robust: anything migration does afterward (a fallback
# `docker compose up` against the current compose file, or phase 8's install.sh)
# can legitimately create the volume, and a post-migration inspect would then
# wrongly flip an absent-at-backup-time skip into a FAIL.
if docker volume inspect "${CLAUDE_VOLUME_NAME}" >/dev/null 2>&1; then
    CLAUDE_VOLUME_EXISTED_PRE_MIGRATION=true
else
    CLAUDE_VOLUME_EXISTED_PRE_MIGRATION=false
fi

# --- Class D baseline: host environment_settings.txt must survive migration (and
#     any driven update) byte-for-byte. cksum reads from stdin so the output is
#     just the checksum+size, with no filename to differ. Bash 3.2 portable.
CLASS_D_APPLICABLE=false
CLASS_D_PRE=""
if [ -f "${HOST_DIR}/environment_settings.txt" ]; then
    CLASS_D_APPLICABLE=true
    CLASS_D_PRE=$(cksum < "${HOST_DIR}/environment_settings.txt")
    observe_note "Class D baseline captured (environment_settings.txt cksum: ${CLASS_D_PRE})."
else
    observe_note "Class D not applicable: no environment_settings.txt in ${HOST_DIR} (era predates it)."
fi

# Run migration with the branch env var. Do NOT pipe input in: migrate_daaf.sh
# reads interactive prompts from /dev/tty (not stdin), so a piped "n" was a
# no-op that only obscured intent. Non-interactive detection inside the migration
# script auto-skips the optional update prompt on its own.
#
# Capture the exit status AND the combined output (via tee to migrate.out, which
# the interactive-mode update detection greps). `set -e` is temporarily lifted
# around the pipe so a nonzero migrate exit is reported rather than aborting the
# harness; PIPESTATUS[0] is migrate's own exit (tee always exits 0). In --auto we
# export CI=1 so migrate runs non-interactive (IS_INTERACTIVE=false); note migrate
# then SKIPS its update offer, so --auto drives update itself below.
MIGRATION_EXIT=0
MIGRATE_OUT="${TEST_DIR}/migrate.out"
if [ "${AUTO_MODE}" = "1" ]; then
    set +e
    CI=1 DAAF_BRANCH="${MIGRATION_BRANCH}" DAAF_NESTED=1 bash migrate_daaf.sh 2>&1 | tee "${MIGRATE_OUT}"
    MIGRATION_EXIT="${PIPESTATUS[0]}"
    set -e
else
    set +e
    DAAF_BRANCH="${MIGRATION_BRANCH}" DAAF_NESTED=1 bash migrate_daaf.sh 2>&1 | tee "${MIGRATE_OUT}"
    MIGRATION_EXIT="${PIPESTATUS[0]}"
    set -e
fi

echo ""
# Fix B: report the migration outcome TRUTHFULLY. A nonzero exit is a real FAIL
# fed into the results counter -- never printed as SUCCESS. Verification (Phase
# 7) still runs regardless, because it shows the blast radius of a failed
# migration; but it runs under a banner that makes clear migration itself failed.
if [ "${MIGRATION_EXIT}" -eq 0 ]; then
    success "Migration script completed (exit code 0)."
    check "Migration script completed successfully (exit 0)" "0"
else
    error "Migration script did NOT complete successfully (exit code ${MIGRATION_EXIT})."
    error "Verification below still runs to show the blast radius, but migration itself FAILED."
    check "Migration script completed successfully (exit ${MIGRATION_EXIT})" "1"
fi
echo ""

# =====================================================================
# UPDATE DRIVING (class E + Phase 7b prerequisite)
# =====================================================================
# migrate_daaf.sh SKIPS its update offer when non-interactive (verified in
# migrate_daaf.sh: "Non-interactive mode detected -- skipping update"), so in
# --auto the harness drives update_daaf.sh itself from the host dir. In
# interactive mode the tester already answered migrate's own update offer, so we
# only DETECT whether it ran from the captured migrate output.
UPDATE_RAN=false
UPDATE_OUT="${TEST_DIR}/update.out"
CLASS_E_PLANTED=false
if [ "${AUTO_MODE}" = "1" ]; then
    if [ -f "${HOST_DIR}/update_daaf.sh" ]; then
        # Class E: plant a drift marker on a host script; a healthy update re-syncs
        # it from the branch (marker gone) and backs up the drifted copy as
        # <script>.pre-update. Verified in Phase 7b.
        if [ -f "${HOST_DIR}/view_logs.sh" ]; then
            printf '\n# test-migration-marker-E: drifted host script\n' >> "${HOST_DIR}/view_logs.sh"
            CLASS_E_PLANTED=true
            observe_note "Class E planted: drift marker on ${HOST_DIR}/view_logs.sh."
        fi
        info "Driving update_daaf.sh (non-interactive) from ${HOST_DIR}..."
        echo ""
        set +e
        CI=1 DAAF_NESTED=1 bash "${HOST_DIR}/update_daaf.sh" 2>&1 | tee "${UPDATE_OUT}"
        UPDATE_EXIT="${PIPESTATUS[0]}"
        set -e
        UPDATE_RAN=true
        echo ""
        if [ "${UPDATE_EXIT}" -eq 0 ]; then
            check "Update script completed (exit 0)" "0"
        else
            check "Update script completed (exit ${UPDATE_EXIT})" "1"
        fi
        # Self-update two-run: if the updater reports it updated ITSELF, a real user
        # re-runs it once more. For the v2.1.0 vector migrate may have pre-seeded the
        # newest update_daaf.sh, so the banner may legitimately NOT appear -- record a
        # skip in that case rather than a FAIL (a known consequence of routing v2.1.0
        # through migrate, which downloads the newest host scripts before update runs).
        if grep -q 'updater itself was updated' "${UPDATE_OUT}"; then
            info "Self-update detected -- running update once more (as a real user would)..."
            echo ""
            set +e
            CI=1 DAAF_NESTED=1 bash "${HOST_DIR}/update_daaf.sh" 2>&1 | tee -a "${UPDATE_OUT}"
            UPDATE_EXIT2="${PIPESTATUS[0]}"
            set -e
            echo ""
            if [ "${UPDATE_EXIT2}" -eq 0 ]; then
                check "Self-update two-run reproduced (second update exit 0)" "0"
            else
                check "Self-update two-run reproduced (second update exit ${UPDATE_EXIT2})" "1"
            fi
        else
            skip_note "Self-update two-run: no 'updater itself was updated' banner (migrate pre-seeded the newest update_daaf.sh for ${TEST_VERSION})."
        fi
    else
        skip_note "Auto-mode update driving: no update_daaf.sh in ${HOST_DIR} (migration did not download it)."
    fi
else
    # Interactive mode: detect whether the tester accepted migrate's update offer.
    # Match the updater's OWN startup banner (the literal "DAAF Updater" echo in
    # update_daaf.sh -- string-anchored on purpose; line numbers drift),
    # which prints only after its source-only guard + lock -- i.e. only when the
    # updater actually executes. The prior pattern ('update_daaf|Running update|
    # updater') also matched migrate's unconditional banner line "...the new update
    # infrastructure (update_daaf.sh)." (migrate_daaf.sh:211), so a DECLINED update
    # was misread as UPDATE_RAN=true and forced Phase 7b hard checks against a
    # never-updated container.
    if grep -qF 'DAAF Updater' "${MIGRATE_OUT}"; then
        UPDATE_RAN=true
        observe_note "Interactive mode: migrate output indicates an update ran (newest-endpoint checks enabled)."
    else
        observe_note "Interactive mode: no update evidence in migrate output (update likely declined; Phase 7b will skip)."
    fi
fi
echo ""

# =====================================================================
# PHASE 7: Verification
# =====================================================================
echo "[7/7] ${BOLD}Verification${RESET}"
if [ "${MIGRATION_EXIT}" -ne 0 ]; then
    echo "  ${RED}(Migration FAILED with exit code ${MIGRATION_EXIT} -- the checks below report the blast radius, not a healthy migration.)${RESET}"
fi
echo ""

# Re-discover container (may have changed during migration)
CONTAINER_NAME=$(docker ps -a --filter "volume=${VOLUME_NAME}" --format '{{.Names}}' | head -1)
if [ -z "${CONTAINER_NAME}" ]; then
    error "No container found after migration!"
    exit 1
fi

CONTAINER_STATE=$(docker inspect --format '{{.State.Status}}' "${CONTAINER_NAME}" 2>/dev/null || echo "unknown")
if [ "${CONTAINER_STATE}" != "running" ]; then
    docker start "${CONTAINER_NAME}" >/dev/null 2>&1
    sleep 3
fi
# CONTAINER_NAME was just re-discovered above; the top-level helpers pick it up.

echo "${BOLD}  Git State Checks:${RESET}"

# Check 1: Remote exists and points to correct repo
ORIGIN_URL=$(container_git remote get-url origin 2>/dev/null || echo "")
if echo "${ORIGIN_URL}" | grep -qi "${REPO}"; then
    check "Remote 'origin' points to official DAAF repo" "0"
else
    check "Remote 'origin' points to official DAAF repo (got: '${ORIGIN_URL}')" "1"
fi

# Check 2: Upstream tracking is set.
# Expected tracking is era- and ref-aware:
#   - Era 1/2 and Era 3 TAGS: local main exists (from the era pathway or the
#     Phase 3 normalization), migrate sets main -> origin/main, and the
#     updater always returns HEAD to the branch it started on. Expect
#     origin/main.
#   - Era 3 BRANCH installs (e.g. daaf_dev): no local main ever exists; the
#     clone's branch keeps its own tracking (origin/<branch>). migrate's
#     set-upstream to main is a silent no-op there. (Historical wart: migrate
#     once printed "Tracking set: main -> origin/main" unconditionally, even on
#     that no-op; fixed as of commit 4cd280d (2026-07-17), which prints the
#     message only on set-upstream success and an honest NOTE otherwise. This
#     harness has always asserted the REAL git tracking state below, never the
#     printed string, so its behavior is unchanged either way.)
EXPECTED_TRACKING="origin/main"
if [ "${TEST_ERA}" = "3" ] && ! [[ "${TEST_VERSION}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    EXPECTED_TRACKING="origin/${TEST_VERSION}"
fi
TRACKING=$(container_git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || echo "")
if [ "${TRACKING}" = "${EXPECTED_TRACKING}" ]; then
    check "Upstream tracking set to ${EXPECTED_TRACKING}" "0"
else
    check "Upstream tracking set to ${EXPECTED_TRACKING} (got: '${TRACKING}')" "1"
fi

# Check 3: Era 2 only -- the graft must now exist ON THE SYNTHETIC ROOT whose
# SHA Phase 3 captured pre-migration. Do NOT re-discover the root with
# `rev-list --max-parents=0` here: after a SUCCESSFUL graft that command walks
# through the replaced root and returns upstream's genuine root, which is
# parentless forever -- inspecting it produced a false FAIL on a healthy
# migration (field run 3; repro in the session workspace's
# scripts/scratch/graft_repro.sh). cat-file honors replace refs, so the
# grafted parent is visible on the captured SHA.
if [ "${TEST_ERA}" = "2" ]; then
    if [ -n "${ERA2_ROOT_SHA}" ]; then
        # grep -c already prints "0" on no-match (while exiting 1) -- a
        # `|| echo "0"` fallback here would DOUBLE the output to "0\n0" under
        # pipefail and break the integer test below exactly when the graft is
        # absent. `|| true` absorbs the exit code; the :-0 guard covers the
        # only truly empty case (substitution failure).
        PARENT_COUNT=$(container_git cat-file -p "${ERA2_ROOT_SHA}" 2>/dev/null | grep -c '^parent ' || true)
        if [ "${PARENT_COUNT:-0}" -gt 0 ]; then
            check "Era 2 graft in place (synthetic root now has a parent)" "0"
        else
            check "Era 2 graft in place (synthetic root now has a parent)" "1"
        fi
    else
        check "Era 2 graft in place (pre-migration root SHA was not captured)" "1"
    fi
fi

# Check 3b (all eras): a common ancestor with origin/main must exist -- via
# genuine history (Era 1/3) or via the graft (Era 2). This is the property
# update_daaf's merges depend on.
MERGE_BASE=$(container_git merge-base HEAD origin/main 2>/dev/null || echo "")
if [ -n "${MERGE_BASE}" ]; then
    check "Common ancestor exists with origin/main" "0"
else
    check "Common ancestor exists with origin/main" "1"
fi

echo ""
echo "${BOLD}  Research File Checks:${RESET}"

# Check 4: Committed research project survived
if container_exec test -f /daaf/research/2026-01-15_Test_Analysis/scripts/01_fetch.py; then
    check "Committed research project preserved" "0"
else
    check "Committed research project preserved" "1"
fi

if container_exec test -f /daaf/research/2026-01-15_Test_Analysis/data/test_data.txt; then
    check "Committed research data preserved" "0"
else
    check "Committed research data preserved" "1"
fi

# Check 5: Uncommitted research files survived
if container_exec test -f /daaf/research/2026-02-10_WIP_Analysis/notes.md; then
    check "Uncommitted research files preserved" "0"
else
    check "Uncommitted research files preserved" "1"
fi

if container_exec test -f /daaf/research/2026-02-10_WIP_Analysis/scripts/01_explore.py; then
    check "Uncommitted WIP script preserved" "0"
else
    check "Uncommitted WIP script preserved" "1"
fi

echo ""
echo "${BOLD}  Framework State Checks:${RESET}"

# Check 6: Committed framework marker file survived (content-verified)
if container_exec grep -q 'test-migration-marker: committed' /daaf/agent_reference/test_migration_marker.md; then
    check "Committed framework changes preserved" "0"
else
    check "Committed framework changes preserved" "1"
fi

# Check 7: Uncommitted (untracked) framework marker file survived
if container_exec grep -q 'test-migration-marker: uncommitted' /daaf/agent_reference/test_migration_marker_uncommitted.md; then
    check "Uncommitted framework changes preserved" "0"
else
    check "Uncommitted framework changes preserved" "1"
fi

# Check 7b: Dirty tracked change survived. If the user took the update,
# update_daaf stashed this before merging and popped it after -- this line
# surviving is the stash/pop path working end to end. If the update was
# declined, migration alone must not have touched it either way.
if container_exec grep -q uncommitted-stash-check /daaf/research/2026-01-15_Test_Analysis/README.md; then
    check "Dirty tracked change preserved (updater stash/pop path)" "0"
else
    check "Dirty tracked change preserved (updater stash/pop path)" "1"
fi

# Check 8: Committed SHA still in history.
# Capture-then-grep, NOT `container_git log | grep -q`: grep -q exits on the
# first match and closes the pipe, git log upstream dies of SIGPIPE (141), and
# `set -o pipefail` turns a FOUND commit into a false "lost" FAIL. (Review
# repro: PIPESTATUS='141 0' with the piped form.)
GITLOG=$(container_git log --oneline)
if printf '%s\n' "${GITLOG}" | grep -q "${COMMITTED_SHA:0:7}"; then
    check "Committed changes still in git history" "0"
else
    check "Committed changes still in git history" "1"
fi

echo ""
echo "${BOLD}  Extended Fixture Checks (classes B/C/D):${RESET}"

# Outcome semantics for the B(i)/B(ii) appends to tracked framework files (a
# three-way outcome, backported from the .ps1 twin so both twins agree): marker
# present with NO git conflict markers = PASS; conflict markers in the file =
# CONFLICTED (a skip_note with a prominent note, since a conflict on a heavily-
# rewritten upstream file is an expected, non-defect outcome); marker absent with
# no conflict markers = FAIL. Class C is observe-only (never pass/fail). The
# conflict probe greps for 7-char git markers (<<<<<<< / >>>>>>>) INSIDE the
# container via container_exec -- a direct exit-code test, no host-side pipe, so
# pipefail cannot turn a found/not-found result into a spurious failure.
# '=======' is excluded because it occurs in ordinary Markdown.

# Class B(i): committed Dockerfile user-block append survived migration (merge path).
if [ "${PLANTED_B1}" = "true" ]; then
    if container_exec grep -q 'test-migration-marker-B: dockerfile-user-block' /daaf/Dockerfile; then
        b1_present=true
    else
        b1_present=false
    fi
    if container_exec grep -qE '<<<<<<<|>>>>>>>' /daaf/Dockerfile; then
        b1_conflict=true
    else
        b1_conflict=false
    fi
    if [ "${b1_conflict}" = "true" ]; then
        skip_note "Class B(i): CONFLICTED -- git conflict markers in /daaf/Dockerfile around the committed append (expected when upstream rewrote the file's tail; not a migration defect)."
    elif [ "${b1_present}" = "true" ]; then
        check "Class B(i): committed Dockerfile append preserved" "0"
    else
        check "Class B(i): committed Dockerfile append preserved" "1"
    fi
else
    skip_note "Class B(i): not planted (no USER ADDITIONS block at ${TEST_VERSION})."
fi

# Class C: committed CLAUDE.md prose append -- OBSERVE-ONLY (never pass/fail).
# On daaf_dev CLAUDE.md is heavily rewritten relative to the old eras, so a
# committed append near '## Identity' legitimately MAY hit a merge conflict on
# update. Recording the outcome as an observe note avoids a spurious FAIL on an
# expected conflict (matches the .ps1 twin; never touches TESTS_PASSED/FAILED).
if [ "${PLANTED_C}" = "true" ]; then
    if container_exec grep -q 'test-migration-marker-C' /daaf/CLAUDE.md; then
        observe_note "Class C: committed CLAUDE.md append is present after migration (merge preserved it)."
    else
        observe_note "Class C: committed CLAUDE.md append is NOT present after migration (likely a merge conflict/rewrite on this heavily-edited file -- observe-only, not a FAIL)."
    fi
else
    skip_note "Class C: not planted (no '## Identity' section at ${TEST_VERSION})."
fi

# Class B(ii): uncommitted CLAUDE.md append survived (updater stash/pop path).
# Same three-way outcome as B(i).
if [ "${PLANTED_B2}" = "true" ]; then
    if container_exec grep -q 'test-migration-marker-Bii' /daaf/CLAUDE.md; then
        b2_present=true
    else
        b2_present=false
    fi
    if container_exec grep -qE '<<<<<<<|>>>>>>>' /daaf/CLAUDE.md; then
        b2_conflict=true
    else
        b2_conflict=false
    fi
    if [ "${b2_conflict}" = "true" ]; then
        skip_note "Class B(ii): CONFLICTED -- git conflict markers in /daaf/CLAUDE.md around the uncommitted append (expected when upstream rewrote the file's tail; not a migration defect)."
    elif [ "${b2_present}" = "true" ]; then
        check "Class B(ii): uncommitted CLAUDE.md append preserved (stash/pop)" "0"
    else
        check "Class B(ii): uncommitted CLAUDE.md append preserved (stash/pop)" "1"
    fi
else
    skip_note "Class B(ii): not planted (no 'Primary execution language' line at ${TEST_VERSION})."
fi

# Class D: host environment_settings.txt byte-identical across migration (+update).
if [ "${CLASS_D_APPLICABLE}" = "true" ]; then
    if [ -f "${HOST_DIR}/environment_settings.txt" ]; then
        CLASS_D_POST=$(cksum < "${HOST_DIR}/environment_settings.txt")
        if [ "${CLASS_D_POST}" = "${CLASS_D_PRE}" ]; then
            check "Class D: environment_settings.txt byte-identical across migration" "0"
        else
            check "Class D: environment_settings.txt byte-identical (pre='${CLASS_D_PRE}' post='${CLASS_D_POST}')" "1"
        fi
    else
        check "Class D: environment_settings.txt still present after migration" "1"
    fi
else
    skip_note "Class D: no environment_settings.txt baseline (era predates it)."
fi

echo ""
echo "${BOLD}  Host Script Checks:${RESET}"

# Check 9: Host scripts were downloaded.
# This list mirrors what migrate_daaf.sh actually fetches today (see its
# "for FILE in ..." download loop): the full .sh utility set -- including
# daaf.sh + daaf_lib.sh (the macOS/Linux Control Panel) -- plus the two shipped
# text files. The .ps1 twin uses a DIFFERENT list (see test_migration.ps1):
# daaf.sh/daaf_lib.sh are never shipped to Windows (commit 4fa8c43), and Windows
# gets the .ps1 variants instead.
for SCRIPT in daaf.sh daaf_lib.sh backup_daaf.sh restore_from_backup.sh rebuild_daaf.sh update_daaf.sh run_daaf.sh view_logs.sh view_notebooks.sh view_quarto.sh run_vscode.sh environment_settings_example.txt README.txt; do
    if [ -f "${HOST_DIR}/${SCRIPT}" ]; then
        check "Host script downloaded: ${SCRIPT}" "0"
    else
        check "Host script downloaded: ${SCRIPT}" "1"
    fi
done

echo ""
echo "${BOLD}  Backup Checks:${RESET}"

# Check 10: Backup directory was created during migration
BACKUP_DIR=$(find "${HOST_DIR}" -maxdepth 1 -type d -name '*_daaf_backup' 2>/dev/null | head -1 || echo "")
if [ -n "${BACKUP_DIR}" ]; then
    check "Backup directory created during migration" "0"

    # Check 11: Backup content is complete. The on-disk backup layout produced by
    # backup_daaf.sh (verified against that script) is:
    #   <backup>/                      data-volume CONTENTS at the root (CLAUDE.md,
    #                                  research/, etc. -- copied via "docker cp .../.")
    #   <backup>/.daaf-claude-config/  Claude Code state volume payload (hidden
    #                                  subfolder; ONLY present if the claude-config
    #                                  volume existed at backup time)
    #   <backup>/.daaf-permissions     executable-permission manifest at the root
    #   <backup>/.daaf-symlinks        symlink manifest at the root (always present
    #                                  in current backups, 0-byte when the volume has
    #                                  no symlinks; absent only in pre-feature backups)
    #
    # Data payload: assert a known volume file (CLAUDE.md) is at the backup root.
    if [ -f "${BACKUP_DIR}/CLAUDE.md" ]; then
        check "Backup contains data-volume payload (CLAUDE.md at root)" "0"
    else
        check "Backup contains data-volume payload (CLAUDE.md at root)" "1"
    fi

    # Permissions manifest: always written by a current backup_daaf.sh.
    if [ -f "${BACKUP_DIR}/.daaf-permissions" ]; then
        check "Backup contains .daaf-permissions manifest" "0"
    else
        check "Backup contains .daaf-permissions manifest" "1"
    fi

    # Symlink manifest: CONDITIONAL on the backup ERA, not on symlink presence.
    # backup_daaf.sh's staging step always runs `paste`, which ALWAYS creates
    # .daaf-symlinks (a 0-byte file when the volume has no symlinks) -- so a CURRENT
    # backup always has the file, and absence means only that the backup predates
    # this feature. This harness replays pre-feature eras, where the manifest is
    # legitimately absent, so a missing file here is NOT a defect: present => PASS;
    # absent => informational skip (pre-feature backup).
    if [ -f "${BACKUP_DIR}/.daaf-symlinks" ]; then
        check "Backup contains .daaf-symlinks manifest" "0"
    else
        info "Skipped .daaf-symlinks check: no symlink manifest in this backup (it predates the symlink-safe backup feature; current backups always include the file, 0-byte when the volume has no symlinks)."
    fi

    # Claude state payload: CONDITIONAL. backup_daaf.sh only writes the
    # .daaf-claude-config/ subfolder when the claude-config volume exists at
    # backup time. Every era this harness replays (v1.0.0 through v2.1.0)
    # predates that volume -- their compose files define no claude-config
    # volume, and the migration backs up BEFORE any current-compose
    # `docker compose up` could create it, so the subfolder is legitimately
    # absent there. Gate the assertion on CLAUDE_VOLUME_EXISTED_PRE_MIGRATION --
    # the flag captured just before migration (phase 6) -- NOT on a live inspect
    # here: by this point migration (and, on non-skipped runs, phase 8's
    # install.sh) may have created the volume, which a live inspect would
    # mistake for "should have been in the backup." Three-way outcome:
    # subfolder present -> PASS; absent but volume existed pre-migration ->
    # FAIL (a real backup gap); absent and volume did not exist pre-migration ->
    # informational skip.
    if [ -d "${BACKUP_DIR}/.daaf-claude-config" ]; then
        check "Backup contains Claude state payload (.daaf-claude-config/)" "0"
    elif [ "${CLAUDE_VOLUME_EXISTED_PRE_MIGRATION}" = "true" ]; then
        # The volume existed at backup time yet the subfolder is missing -- real gap.
        check "Backup contains Claude state payload (.daaf-claude-config/)" "1"
    else
        info "Skipped Claude state payload check: source volume '${CLAUDE_VOLUME_NAME}' did not exist at backup time (install predates it)."
    fi
else
    check "Backup directory created during migration" "1"
    warn "Skipping backup-content checks: no backup directory to inspect."
fi

# =====================================================================
# PHASE 7b: Newest-Endpoint Verification (post-update)
# =====================================================================
# Gated on an actual update run (auto-mode drove it, or interactive accepted it).
# When no update ran there is no "newest endpoint" to assert, so every check here
# is a documented SKIP rather than a FAIL.
echo ""
echo "[7b] ${BOLD}Newest-endpoint checks (post-update)${RESET}"
echo ""
if [ "${UPDATE_RAN}" = "true" ]; then
    # Re-discover the container (an update rebuild may have replaced it).
    CONTAINER_NAME=$(docker ps -a --filter "volume=${VOLUME_NAME}" --format '{{.Names}}' | head -1)
    if [ -n "${CONTAINER_NAME}" ]; then
        CONTAINER_STATE=$(docker inspect --format '{{.State.Status}}' "${CONTAINER_NAME}" 2>/dev/null || echo "unknown")
        if [ "${CONTAINER_STATE}" != "running" ]; then
            docker start "${CONTAINER_NAME}" >/dev/null 2>&1 || true
            sleep 3
        fi
    fi

    # Rebuild evidence: update's check_build_changes invokes rebuild_daaf.sh when
    # the Dockerfile/compose changed across the update; rebuild prints these.
    if [ -f "${UPDATE_OUT}" ] && grep -qE 'Rebuilding Docker image|Rebuild complete' "${UPDATE_OUT}"; then
        check "Update triggered a Docker rebuild (build strings in update output)" "0"
    else
        skip_note "No rebuild strings in update output (Dockerfile/compose unchanged across this update -- rebuild legitimately not triggered)."
    fi

    # Noble base image: the HEAD Dockerfile is FROM ubuntu:24.04 (noble).
    OS_RELEASE=$(container_exec cat /etc/os-release 2>/dev/null || echo "")
    if echo "${OS_RELEASE}" | grep -q 'VERSION_CODENAME=noble'; then
        check "Container base image is Ubuntu noble (24.04) after update" "0"
    else
        check "Container base image is Ubuntu noble (24.04) after update" "1"
    fi

    # Functional smoke: container exec-ready + git sanity + hooks present.
    if container_exec true >/dev/null 2>&1; then
        check "Container exec-ready after update" "0"
    else
        check "Container exec-ready after update" "1"
    fi
    GIT_DESC=$(container_git describe --tags --always 2>/dev/null || echo "")
    if [ -n "${GIT_DESC}" ]; then
        check "git describe returns a sane ref after update (${GIT_DESC})" "0"
    else
        check "git describe returns a sane ref after update" "1"
    fi
    # Upstream tracking survives update (reuse the era-conditional expectation set
    # by Check 2 above).
    TRACKING_POST=$(container_git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || echo "")
    if [ "${TRACKING_POST}" = "${EXPECTED_TRACKING}" ]; then
        check "Upstream tracking still ${EXPECTED_TRACKING} after update" "0"
    else
        check "Upstream tracking still ${EXPECTED_TRACKING} after update (got: '${TRACKING_POST}')" "1"
    fi
    if container_exec test -d /daaf/.claude/hooks; then
        check "Framework hooks directory present after update (.claude/hooks)" "0"
    else
        check "Framework hooks directory present after update (.claude/hooks)" "1"
    fi

    # Class E drift-heal: the drifted host script was re-synced (marker gone) and
    # the drifted copy backed up as view_logs.sh.pre-update.
    if [ "${CLASS_E_PLANTED}" = "true" ]; then
        if grep -q 'test-migration-marker-E' "${HOST_DIR}/view_logs.sh" 2>/dev/null; then
            check "Class E: drifted host script re-synced by update (marker cleared)" "1"
        else
            check "Class E: drifted host script re-synced by update (marker cleared)" "0"
        fi
        if [ -f "${HOST_DIR}/view_logs.sh.pre-update" ]; then
            check "Class E: drifted host script backed up (view_logs.sh.pre-update)" "0"
        else
            check "Class E: drifted host script backed up (view_logs.sh.pre-update)" "1"
        fi
    else
        skip_note "Class E: drift marker not planted (auto-mode only; no view_logs.sh at update time)."
    fi
else
    skip_note "Newest-endpoint checks skipped: no update ran (interactive decline, or update_daaf.sh absent)."
fi

# =====================================================================
# PHASE 8: Multi-Instance Coexistence (DAAF_PROJECT_NAME end-to-end)
# =====================================================================
# WHY a POST-migration phase rather than a migrated multi-instance install:
# a historical multi-instance migration is impossible. Old DAAF versions predate
# DAAF_PROJECT_NAME, so every real old install carries the DEFAULT names -- there
# is no such thing as an "old daaftest2 install" to migrate. So the honest way to
# exercise the DAAF_PROJECT_NAME machinery is to stand up a fresh CURRENT-branch
# second instance ALONGSIDE the migrated default one and prove they coexist, then
# tear the second one down cleanly.
if [ "${SKIP_MULTI_INSTANCE:-}" != "1" ]; then
    echo ""
    echo "${BOLD}==========================================${RESET}"
    echo "${BOLD}  Phase 8: Multi-Instance Coexistence${RESET}"
    echo "${BOLD}==========================================${RESET}"
    echo ""
    echo "  Second project: ${SECOND_PROJECT_NAME}"
    echo "  Ports:          marimo=${SECOND_PORT_MARIMO} log=${SECOND_PORT_LOGVIEWER} vscode=${SECOND_PORT_VSCODE}"
    echo ""

    # D7 guard: the multi-instance bring-up runs the LOCAL install.sh. If it is
    # absent, skip the whole phase rather than error out after a passing migration
    # (mirror of the .ps1 Test-Path guard before its Phase-8 bring-up). The inner
    # 8a-8d block is left at its original indentation to keep this a surgical wrap.
    if [ ! -f "${LOCAL_REPO_ROOT}/scripts/host/install.sh" ]; then
        warn "install.sh not found in the local repo -- skipping multi-instance bring-up (D7 guard)."
        skip_note "Multi-instance phase skipped: install.sh absent from local repo."
    else

    # --- 8a. Create the second install directory + environment_settings.txt ---
    info "Creating second install directory and environment_settings.txt..."
    SECOND_DIR="${TEST_DIR}/instance2"
    mkdir -p "${SECOND_DIR}"

    # Write the four multi-instance keys the compose file interpolates. The key
    # names (DAAF_PROJECT_NAME / DAAF_PORT_MARIMO / DAAF_PORT_LOGVIEWER /
    # DAAF_PORT_VSCODE) match environment_settings_example.txt and how
    # install.sh/rebuild_daaf.sh read them. install.sh derives the volume name
    # from DAAF_PROJECT_NAME (shell env first), and compose interpolates all four
    # from the shell env at build/up time -- so exporting them below is what makes
    # the second instance actually reproject.
    {
        echo "DAAF_PROJECT_NAME=${SECOND_PROJECT_NAME}"
        echo "DAAF_PORT_MARIMO=${SECOND_PORT_MARIMO}"
        echo "DAAF_PORT_LOGVIEWER=${SECOND_PORT_LOGVIEWER}"
        echo "DAAF_PORT_VSCODE=${SECOND_PORT_VSCODE}"
    } > "${SECOND_DIR}/environment_settings.txt"
    success "Second environment_settings.txt written."
    echo ""

    # --- 8b. Bring up a fresh CURRENT-branch instance there ---
    # MECHANISM CHOICE: reuse the local install.sh (from the migration branch's
    # repo checkout) rather than hand-rolling `docker compose up`. Rationale:
    # install.sh is the ONLY mechanism that both (1) stands up the container with
    # the correct project-prefixed names AND (2) populates /daaf via git clone.
    # A bare `docker compose up` against the fetched compose file would start an
    # EMPTY-/daaf container (no repo clone), which is not a realistic instance and
    # would make the coexistence checks meaningless. install.sh already reads
    # DAAF_PROJECT_NAME (shell env wins) to derive its volume name, and compose
    # reads all four DAAF_* keys from the shell env for interpolation -- so we
    # export them, point install.sh at the current branch, and run it in the
    # second directory. DAAF_NESTED suppresses its exit pause.
    info "Bringing up second instance from branch '${MIGRATION_BRANCH}' via install.sh..."
    echo ""
    cd "${SECOND_DIR}" || { error "Cannot enter second install dir: ${SECOND_DIR}"; exit 1; }

    (
        export DAAF_PROJECT_NAME="${SECOND_PROJECT_NAME}"
        export DAAF_PORT_MARIMO="${SECOND_PORT_MARIMO}"
        export DAAF_PORT_LOGVIEWER="${SECOND_PORT_LOGVIEWER}"
        export DAAF_PORT_VSCODE="${SECOND_PORT_VSCODE}"
        export DAAF_BRANCH="${MIGRATION_BRANCH}"
        export DAAF_NESTED=1
        # Force a clean re-install so a leftover daaftest2 install (e.g. from an
        # aborted prior run whose phase-1 cleanup never ran) cannot make install.sh
        # halt at its "existing installation detected" prompt and hang/abort the harness.
        export DAAF_FORCE_REINSTALL=1
        bash "${LOCAL_REPO_ROOT}/scripts/host/install.sh"
    ) || warn "Second-instance install.sh exited non-zero -- coexistence checks below will show what actually came up."

    echo ""

    # --- 8c. Verify coexistence ---
    echo "${BOLD}  Multi-Instance Checks:${RESET}"

    # Second instance container is running
    SECOND_STATE=$(docker inspect --format '{{.State.Status}}' "${SECOND_CONTAINER_MAIN}" 2>/dev/null || echo "absent")
    if [ "${SECOND_STATE}" = "running" ]; then
        check "Second instance container running (${SECOND_CONTAINER_MAIN})" "0"
    else
        check "Second instance container running (${SECOND_CONTAINER_MAIN}) (state: ${SECOND_STATE})" "1"
    fi

    # Second instance volumes exist
    if docker volume inspect "${SECOND_VOLUME_NAME}" >/dev/null 2>&1; then
        check "Second instance data volume exists (${SECOND_VOLUME_NAME})" "0"
    else
        check "Second instance data volume exists (${SECOND_VOLUME_NAME})" "1"
    fi
    if docker volume inspect "${SECOND_CLAUDE_VOLUME_NAME}" >/dev/null 2>&1; then
        check "Second instance Claude volume exists (${SECOND_CLAUDE_VOLUME_NAME})" "0"
    else
        check "Second instance Claude volume exists (${SECOND_CLAUDE_VOLUME_NAME})" "1"
    fi

    # The migrated DEFAULT instance must still be intact (coexistence, untouched)
    if docker inspect "${CONTAINER_MAIN}" >/dev/null 2>&1; then
        check "Default instance container still present (${CONTAINER_MAIN})" "0"
    else
        check "Default instance container still present (${CONTAINER_MAIN})" "1"
    fi
    if docker volume inspect "${VOLUME_NAME}" >/dev/null 2>&1; then
        check "Default instance data volume still present (${VOLUME_NAME})" "0"
    else
        check "Default instance data volume still present (${VOLUME_NAME})" "1"
    fi

    echo ""

    # --- 8d. Tear the second instance down completely ---
    # Remove container, init container, and both volumes. IMAGE DECISION: remove
    # the second image too. `docker compose build` tags the image from the compose
    # PROJECT name, so with name=daaftest2 the second image is a DISTINCT tag
    # (daaftest2-daaf-docker), NOT shared with the default instance's
    # daaf-daaf-docker -- removing it cannot affect the default instance. The
    # busybox init IMAGE, by contrast, IS shared across instances, so leave it
    # alone (nuke_daaf.sh only removes busybox when no container references it).
    info "Tearing down the second instance (container, init, volumes, distinct image)..."
    docker rm -f "${SECOND_CONTAINER_MAIN}" >/dev/null 2>&1 || true
    docker rm -f "${SECOND_CONTAINER_INIT}" >/dev/null 2>&1 || true
    docker volume rm "${SECOND_VOLUME_NAME}" >/dev/null 2>&1 || true
    docker volume rm "${SECOND_CLAUDE_VOLUME_NAME}" >/dev/null 2>&1 || true
    docker rmi "${SECOND_IMAGE_NAME}" >/dev/null 2>&1 || true

    # Verify teardown succeeded
    if docker inspect "${SECOND_CONTAINER_MAIN}" >/dev/null 2>&1; then
        check "Second instance container removed" "1"
    else
        check "Second instance container removed" "0"
    fi
    if docker volume inspect "${SECOND_VOLUME_NAME}" >/dev/null 2>&1; then
        check "Second instance data volume removed" "1"
    else
        check "Second instance data volume removed" "0"
    fi

    # Coexistence sanity: the default instance survived the teardown untouched.
    if docker volume inspect "${VOLUME_NAME}" >/dev/null 2>&1; then
        check "Default instance data volume survived second-instance teardown" "0"
    else
        check "Default instance data volume survived second-instance teardown" "1"
    fi

    success "Second instance torn down."
    cd "${HOST_DIR}" || true
    echo ""
    fi  # end D7 install.sh-present guard
else
    echo ""
    info "Phase 8 (multi-instance) skipped via SKIP_MULTI_INSTANCE=1."
    echo ""
fi

# =====================================================================
# RESULTS
# =====================================================================
echo ""
echo "${BOLD}==========================================${RESET}"
echo "${BOLD}  Test Results${RESET}"
echo "${BOLD}==========================================${RESET}"
echo ""
echo "  Version:  ${TEST_VERSION}"
echo "  Era:      ${TEST_ERA}"
echo "  Passed:   ${GREEN}${TESTS_PASSED}${RESET}"
echo "  Failed:   $([ "${TESTS_FAILED}" -gt 0 ] && echo "${RED}" || echo "")${TESTS_FAILED}${RESET}"
echo "  Skipped:  ${YELLOW}${TESTS_SKIPPED}${RESET}"
echo ""

if [ "${TESTS_SKIPPED}" -gt 0 ]; then
    echo "${YELLOW}  Skips (not failures):${RESET}"
    printf '%b\n' "${SKIPS}"
    echo ""
fi

# The machine-readable TEST_MIGRATION_SUMMARY line is emitted by the EXIT trap
# (cleanup), so it is always the final stdout line regardless of exit path.
if [ "${TESTS_FAILED}" -gt 0 ]; then
    echo "${RED}  Failures:${RESET}"
    printf '%b\n' "${FAILURES}"
    echo ""
    error "Some checks failed. Inspect the container and test directory for details."
    echo "  Container:  ${CONTAINER_NAME}"
    echo "  Host dir:   ${HOST_DIR}"
    echo "  Test dir:   ${TEST_DIR}"
    exit 1
else
    success "All checks passed!"
    echo ""
    echo "  The DAAF Docker resources are still running for manual inspection."
    echo "  To clean up:  DAAF_NUKE_CONFIRM=1 bash ${LOCAL_REPO_ROOT}/scripts/host/nuke_daaf.sh"
    echo ""
fi
