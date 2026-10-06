#!/usr/bin/env bats
# ============================================================================
# Tests for restore_from_backup.sh -- DAAF Restore from Backup
# ============================================================================
# Key testable logic: backup discovery, preflight checks, running container
# detection, destructive warning, copy-then-swap, and verification.
# ============================================================================

load 'test_helper'

# Fix pass #26 pinned the helper image: every `docker run`/`create` now carries
# DAAF_BUSYBOX_PIN (test_helper.bash) where it used to say `busybox`, and the mock's call
# log records it verbatim. BB_RE is that string escaped for grep -E / grep (BRE) patterns
# (test_helper's DAAF_BUSYBOX_PIN_RE), so a log pattern still names the exact image.
BB_RE="${DAAF_BUSYBOX_PIN_RE}"

setup() {
    common_setup
    mock_docker
}

# Re-open any chmod-000 fixture folder (the read-error tests below) before the shared
# teardown's `rm -rf`, which cannot descend into an unreadable folder -- this runs on
# pass AND on failure, so no fixture outlives its test (backup_twin_parity.bats pattern).
teardown() {
    chmod -R u+rwx "${TEST_DIR}" 2>/dev/null || true
    common_teardown
}

# =========================================================================
# Copy-then-swap logging mock (restore-local)
# =========================================================================
# Models every docker call the copy-then-swap restore makes, logs each call as ONE
# line (embedded newlines of the multi-line `sh -c` programs folded to spaces) to
# ${TEST_DIR}/docker_calls.log, and tracks helper containers in ${TEST_DIR}/helpers
# ("<label> <cid>" lines: `docker create --label` adds, `docker rm -f <cid>` removes,
# `docker ps -aq --filter label=<label>` lists) so a leaked helper is observable.
# The volume names assume DAAF_PROJECT_NAME / DAAF_DATA_VOLUME_NAME are unset (the
# mock unsets them): live daaf_daaf-data / daaf_daaf-claude-config, temps
# <live>-restore-tmp, swap containers <live>-restore-swap. Calls are told apart by
# their program text / mounts, never by call order. Knobs (all optional, exported):
#   RM_AVAIL_KB / RM_LIVE_KB / RM_SRC_KB  space markers (defaults 104857600/1000/1000)
#   RM_SWAP_AVAIL_KB      AVAIL_KB for the second (temp-mounted) space check only
#   RM_SPACE_FAIL=1       both space checks exit 1 with no markers (unmeasurable)
#   RM_TEMP_COUNT         RESTORED_FILES printed for the TEMP volume (default 1)
#   RM_TEMP_COUNT_MODE    errors | fail  (temp count unreadable)
#   RM_LIVE_COUNT         RESTORED_FILES for the live volume (default RM_TEMP_COUNT)
#   RM_LIVE_MODE          errors | fail | bare | errorsfail | countfail | zero
#   RM_SWAP_VERIFY / RM_CLAUDE_SWAP_VERIFY  MATCH (default) | MISMATCH | ERRORS | NONE
#   RM_MANIFESTS          which `test -f` probes find a manifest; space-separated words
#                         perms symlinks claudesymlinks (default: all three)
#   RM_FAIL               the ONE step that fails: tmpcreate claudetmpcreate create
#                         claudecreate cp claudecp strip chown claudechown perms
#                         symlinks claudesymlinks marker swap claudeswap tmprm leftoverrm
#                         psswap (the pre-swap `docker ps` re-check itself fails)
#   RM_LEFTOVER           full names of leftover temp volumes that exist (exact match)
#   RM_VOLUMES            other existing volume names (only `volume ls --filter` sees them)
#   RM_LEFTOVER_MARKER    yes (marker present: probe exit 3) | err (probe exit 125)
#   RM_SWAP_CONTAINER / RM_CLAUDE_SWAP_CONTAINER  running | stopped
#   RM_RUNNING            first `ps --filter volume=` answer (cleared by compose down)
#   RM_RUNNING_AT_SWAP    the pre-swap re-check's answer
#   RM_INTERRUPT_AT       cp | swap | count: the mock sends SIGINT to the restore script
#                         ($$) -- count = the post-swap live count, after both swaps
#   (dispatch #7, review round 1)
#   RM_INSPECT_FAIL       volume | container: the exact-name leftover inspect fails with
#                         a daemon error that is NOT "no such ..." (could not check)
#   RM_IDENTITY / RM_CLAUDE_IDENTITY  how `volume inspect --format {{.Labels}}` answers
#                         for the data / Claude temp: ok (default: the labels its create
#                         set) | vanished (no such volume) | recreated (another run's
#                         token) | vanished_after_create / recreated_after_create (ok
#                         only for the check right after create) | vanished_after_marker
#                         (ok until the marker was written into it)
#   RM_TEMP_NOT_EMPTY     data | claude: the new temp's `find /dest -mindepth 1` lists a file
#   RM_SWAP_VERIFY_ENTRIES / RM_CLAUDE_SWAP_VERIFY_ENTRIES  the ENTRIES line (default 3:3)
#   RM_FAIL=emptycheck    the new-temp emptiness check itself fails (exit 1)
#   RM_FAIL=crash         the permission replay call EXITS the script (status 7): an
#                         unexpected failure stand-in (the mock runs in the script's shell)
#   (fix round 2, review round 2)
#   RM_INSPECT_FAIL also makes the exact-name LISTS fail with the daemon error
#                         (volume -> `volume ls -q`; container -> `ps -a --format` and
#                         `ps --format`), so "could not check" still refuses (S3 fallback)
#   RM_INSPECT_ODD        volume | container: the exact-name inspect fails with text that
#                         is NOT a recognised "no such ..." message; the lists still work
#   RM_LIST_FAIL          volume | container | running | container_after_swap: that exact-
#                         name list fails (container_after_swap: only once the data swap ran)
#   RM_SWAP_STATE_STDERR  first | last: a running swap container's inspect also prints a
#                         stderr line before / after its "true" (I-A: stdout only)
#   RM_SWAP_EXIT          the data swap's exit code (default 0; RM_FAIL=swap is exit 1)
#   RM_SWAP_AFTER         stopped | running: the data swap container exists (in inspect and
#                         the lists) once the data swap ran -- e.g. a 125 that started it
#   RM_IDENTITY=vanished_after_swap  the data temp vanishes once the data swap ran
#   RM_EMPTYCHECK_STDERR=1  the new-temp emptiness check also prints a stderr line
#   RM_INTERRUPT_AT       pause: the first `volume rm` arms a SIGINT to the script 1 s later
#                         (it is then waiting at the exit pause); pause_swap: the data swap
#                         call arms it (use with RM_FAIL=swap) -- real-pty tests only
#   (fix round 3, review round 3)
#   RM_CLAUDE_SWAP_EXIT   the Claude swap's exit code (default 0; RM_FAIL=claudeswap is 1)
#   RM_INTERRUPT_AT       cleanup: the first `volume rm` sends SIGINT to the script ($$)
#                         at once -- with RM_FAIL=crash that is mid-way through the EXIT
#                         handler's cleanup (S-b)
#   (2026-10-02, startup check)
#   RM_FAIL=psstart       the startup `docker ps --filter volume=` itself fails (exit 125)
#   RM_PS_START_STDERR=1  that startup check also prints a stderr line (exit 0)
#   (fix pass #19, field test 2026-10-05: D1 holders, D3)
#   RM_HOLDERS            containers that hold a volume, as listed by the holder check
#                         `ps -a --filter volume=<X> --format {{.ID}} {{.State}}` (its own
#                         arm; the format is ONE argument): space-separated words
#                         <volume>=<id>:<state>, e.g. daaf_daaf-data-restore-tmp=c9be7425c57c:created.
#                         A plain `rm <id>` removes a created/exited/dead holder from later
#                         lists (${TEST_DIR}/holders_removed) and fails like the daemon for any
#                         other state; a `volume rm` of a volume that still has a holder fails
#                         "volume is in use" (field test, section 5) -- so a skipped holder
#                         removal is observable.
#   RM_HOLDERS_LATE       same form; listed only from the SECOND holder list of that volume on
#                         (a holder that appeared after the leftover check pass)
#   RM_HOLDERS_PS_FAIL    volume names whose holder list FAILS: stderr RM_HOLDERS_PS_SAID (may
#                         hold several lines; default a daemon-down line), exit
#                         RM_HOLDERS_PS_EXIT (default 1)
#   RM_HOLDERS_PS_NOISE=1 a holder list that works also prints a stderr line (stdout only)
#   RM_HOLDER_RM_FAIL     holder ids whose plain `rm <id>` fails (a daemon stderr line)
#   RM_VOLUME_RM_SAID     stderr text printed by a `volume rm` that FAILS under RM_FAIL=tmprm /
#                         leftoverrm (may hold several lines)
#   RM_INTERRUPT_AT       claudeswap: the Claude swap call sends SIGINT to the script ($$)
#   (fix round 7, review round 6, R5)
#   RM_SWAP_RUNNING_AT_RM swap container names that are RUNNING by the time the leftover
#                         path removes them (they were stopped at the check, before the
#                         y/n prompt): a PLAIN `rm <name>` fails like the daemon; `rm -f`
#                         would remove it (a mutant)
#   (fix round 8, delta review of round 7, ISSUE 1)
#   RM_SWAP_GONE_AT_RM    swap container names that VANISHED before the leftover path
#                         removes them: a PLAIN `rm <name>` exits 1 with "No such container"
#                         (docker CLI rm.go ignores not-found only for -f)
#   RM_SWAP_REMOVING_AT_RM swap container names whose plain `rm <name>` exits 1 with the
#                         daemon's "removal of container <name> is already in progress"
#                         (moby daemon/delete.go)
_mock_restore_docker() {
    unset DAAF_PROJECT_NAME DAAF_DATA_VOLUME_NAME
    : > "${TEST_DIR}/docker_calls.log"
    : > "${TEST_DIR}/helpers"
    : > "${TEST_DIR}/holder_lists"
    : > "${TEST_DIR}/holders_removed"
    rm -f "${TEST_DIR}/pause_armed" "${TEST_DIR}/cleanup_interrupted"
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        local a="$*" st="${TEST_DIR}" mode v lbl cid
        printf '%s\n' "${a//$'\n'/ }" >> "${st}/docker_calls.log"
        case "$1" in
            info) return 0 ;;
            compose) : > "${st}/composed_down"; return 0 ;;
            volume)
                case "${2:-}" in
                    inspect)
                        if [ "${3:-}" = "--format" ]; then
                            # Identity check: answer with the labels the create recorded.
                            for v in "$@"; do :; done
                            if [[ "${v}" == *claude-config-restore-tmp ]]; then mode="${RM_CLAUDE_IDENTITY:-ok}"; else mode="${RM_IDENTITY:-ok}"; fi
                            if [ "${mode}" = vanished_after_marker ]; then
                                if grep -qF -- "-v ${v}:/dest ${DAAF_BUSYBOX_PIN} touch /dest/.daaf-restore-swap-started" "${st}/docker_calls.log"; then mode=vanished; else mode=ok; fi
                            fi
                            if [ "${mode}" = vanished_after_swap ]; then
                                if grep -q -- "--sig-proxy=false --name [^ ]* -v ${v}:/src:ro " "${st}/docker_calls.log"; then mode=vanished; else mode=ok; fi
                            fi
                            # *_after_create: the check right after `volume create` (this
                            # volume's first identity inspect) passes; later ones do not --
                            # the temp was removed / replaced while the prompt waited.
                            case "${mode}" in
                                vanished_after_create|recreated_after_create)
                                    if [ "$(grep -cxF -- "volume inspect --format {{.Labels}} ${v}" "${st}/docker_calls.log")" -gt 1 ]; then mode="${mode%_after_create}"; else mode=ok; fi
                                    ;;
                            esac
                            case "${mode}" in
                                vanished) echo "Error response from daemon: get ${v}: no such volume" >&2; return 1 ;;
                                recreated) echo "map[org.daaf.restore-run:20260101000000-1-99 org.daaf.restore-tmp-for:x]"; return 0 ;;
                            esac
                            if [ -f "${st}/labels.${v}" ]; then cat "${st}/labels.${v}"; return 0; fi
                            echo "Error response from daemon: get ${v}: no such volume" >&2
                            return 1
                        fi
                        if [ -n "${RM_INSPECT_FAIL:-}" ] && [ "${RM_INSPECT_FAIL}" = volume ]; then
                            case "${3:-}" in
                                *-restore-tmp)
                                    echo "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?" >&2
                                    return 1
                                    ;;
                            esac
                        fi
                        if [ "${RM_INSPECT_ODD:-}" = volume ]; then
                            case "${3:-}" in
                                *-restore-tmp)
                                    echo "Error response from daemon: unexpected reply (simulated, not a not-found message)" >&2
                                    return 1
                                    ;;
                            esac
                        fi
                        for v in ${RM_LEFTOVER:-} ${RM_VOLUMES:-}; do
                            if [ "${v}" = "${3:-}" ]; then return 0; fi
                        done
                        case "${3:-}" in *-restore-tmp) echo "Error response from daemon: get ${3}: no such volume" >&2; return 1 ;; esac
                        return 0
                        ;;
                    ls)
                        # `volume ls -q` is the S3 exact-name fallback (it lists every
                        # name; restore compares whole lines). It fails like the inspect
                        # under RM_INSPECT_FAIL=volume, or alone under RM_LIST_FAIL=volume.
                        if [ "${RM_INSPECT_FAIL:-}" = volume ] || [ "${RM_LIST_FAIL:-}" = volume ]; then
                            echo "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?" >&2
                            return 1
                        fi
                        # `--filter name=` is an UNANCHORED regex in real Docker; modeled
                        # as a substring match (only a mutant would use it).
                        mode=""
                        for v in "$@"; do case "${v}" in name=*) mode="${v#name=}" ;; esac; done
                        for v in ${RM_LEFTOVER:-} ${RM_VOLUMES:-}; do
                            case "${v}" in *"${mode}"*) echo "${v}" ;; esac
                        done
                        return 0
                        ;;
                    create)
                        if [[ "${a}" == *claude-config-restore-tmp* ]]; then
                            if [ "${RM_FAIL:-}" = claudetmpcreate ]; then return 1; fi
                        elif [ "${RM_FAIL:-}" = tmpcreate ]; then return 1; fi
                        # Record the labels like Docker (`{{.Labels}}` prints map[k:v ...],
                        # sorted by key) for the identity check.
                        lbl=""
                        mode=""
                        for v in "$@"; do
                            if [ "${mode}" = label ]; then lbl="${lbl:+${lbl}
}${v/=/:}"; fi
                            if [ "${v}" = "--label" ]; then mode=label; else mode=""; fi
                        done
                        printf 'map[%s]\n' "$(printf '%s\n' "${lbl}" | LC_ALL=C sort | tr '\n' ' ' | sed 's/ $//')" > "${st}/labels.${v}"
                        return 0
                        ;;
                    rm)
                        # RM_INTERRUPT_AT=pause: a SIGINT to the script ($$) 1 s from now,
                        # when it is waiting at the exit pause (armed once; fds closed so
                        # the sleeper does not hold the pty open). The sleeper is an EXEC'd
                        # `sh -c` (fix pass #18/#19): the restore now reads this call's
                        # stderr through `$(docker volume rm ... 2>&1 > /dev/null)`, and a
                        # FORKED subshell would inherit bash's saved copy of that pipe, so
                        # the substitution would block until the sleeper exits and the
                        # SIGINT would land mid-cleanup instead of at the pause.
                        if [ "${RM_INTERRUPT_AT:-}" = pause ] && [ ! -f "${st}/pause_armed" ]; then
                            : > "${st}/pause_armed"
                            sh -c 'sleep 1; kill -INT "$1"' sh "$$" > /dev/null 2>&1 < /dev/null &
                        fi
                        if [ "${RM_INTERRUPT_AT:-}" = cleanup ] && [ ! -f "${st}/cleanup_interrupted" ]; then
                            : > "${st}/cleanup_interrupted"
                            kill -INT "$$"
                        fi
                        # D1: a volume that a container still references is "in use".
                        lbl="$(_rm_holder_lines "${3:-}" | awk '{ print $1 }' | tr '\n' ' ' | sed 's/ $//')"
                        if [ -n "${lbl}" ]; then
                            echo "Error response from daemon: remove ${3:-}: volume is in use - [${lbl}]" >&2
                            return 1
                        fi
                        for v in ${RM_LEFTOVER:-}; do
                            if [ "${v}" = "${3:-}" ]; then
                                if [ "${RM_FAIL:-}" = leftoverrm ]; then
                                    if [ -n "${RM_VOLUME_RM_SAID:-}" ]; then printf '%s\n' "${RM_VOLUME_RM_SAID}" >&2; fi
                                    return 1
                                fi
                                return 0
                            fi
                        done
                        if [ "${RM_FAIL:-}" = tmprm ]; then
                            if [ -n "${RM_VOLUME_RM_SAID:-}" ]; then printf '%s\n' "${RM_VOLUME_RM_SAID}" >&2; fi
                            return 1
                        fi
                        return 0
                        ;;
                esac
                return 0
                ;;
            container)
                if [ "${2:-}" = inspect ]; then
                    for v in "$@"; do :; done
                    if [ -n "${RM_INSPECT_FAIL:-}" ] && [ "${RM_INSPECT_FAIL}" = container ]; then
                        echo "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?" >&2
                        return 1
                    fi
                    if [ "${RM_INSPECT_ODD:-}" = container ]; then
                        echo "Error response from daemon: unexpected reply (simulated, not a not-found message)" >&2
                        return 1
                    fi
                    case "${v}" in
                        *-restore-swap) mode="$(_rm_swap_state "${v}")" ;;
                        *) mode="" ;;
                    esac
                    case "${mode}" in
                        running)
                            # I-A: a stderr line before / after the state; only stdout counts.
                            if [ "${RM_SWAP_STATE_STDERR:-}" = first ]; then echo "WARNING: simulated daemon notice" >&2; fi
                            echo true
                            if [ "${RM_SWAP_STATE_STDERR:-}" = last ]; then echo "WARNING: simulated daemon notice" >&2; fi
                            return 0
                            ;;
                        stopped) echo false; return 0 ;;
                    esac
                    echo "Error: No such container: ${v}" >&2
                    return 1
                fi
                return 0
                ;;
            ps)
                # D1 (fix pass #19): the holder list of a temp volume, STDOUT lines
                # "<id> <state>" (RM_HOLDERS / RM_HOLDERS_LATE / RM_HOLDERS_PS_FAIL). Its own
                # arm, before the others: it once fell into the startup-check branch. The
                # format must arrive as ONE argument (a split one is a mock error, 99).
                if [[ "${a}" == "ps -a --filter volume="*" --format {{.ID}} {{.State}}" ]]; then
                    if [ "$#" -ne 6 ] || [ "${6:-}" != '{{.ID}} {{.State}}' ]; then
                        echo "MOCK: unexpected holder-list argv ($# args): ${a}" >&2
                        return 99
                    fi
                    v="${4#volume=}"
                    for lbl in ${RM_HOLDERS_PS_FAIL:-}; do
                        if [ "${lbl}" = "${v}" ]; then
                            printf '%s\n' "${RM_HOLDERS_PS_SAID:-Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?}" >&2
                            return "${RM_HOLDERS_PS_EXIT:-1}"
                        fi
                    done
                    printf '%s\n' "${v}" >> "${st}/holder_lists"
                    if [ "${RM_HOLDERS_PS_NOISE:-}" = 1 ]; then echo "WARNING: simulated docker config notice" >&2; fi
                    _rm_holder_lines "${v}"
                    return 0
                fi
                # The S3 exact-name lists (review round 2): `ps -a --format {{.Names}}`
                # (all containers) and `ps --format {{.Names}}` (running only), STDOUT
                # names one per line. Near-miss names prove the match is whole-line.
                if [ "${a}" = "ps -a --format {{.Names}}" ] || [ "${a}" = "ps --format {{.Names}}" ]; then
                    if [ "${a}" = "ps --format {{.Names}}" ]; then mode=running; else mode=container; fi
                    lbl=""
                    if [ "${RM_LIST_FAIL:-}" = container_after_swap ] && grep -q -- "--sig-proxy=false --name [^ ]*-restore-swap " "${st}/docker_calls.log"; then lbl=fail; fi
                    if [ "${RM_INSPECT_FAIL:-}" = container ] || [ "${RM_LIST_FAIL:-}" = "${mode}" ] || [ "${lbl}" = fail ]; then
                        echo "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?" >&2
                        return 1
                    fi
                    echo "daaf_daaf-data-restore-swap-old"
                    echo "x-daaf_daaf-claude-config-restore-swap"
                    for v in daaf_daaf-data-restore-swap daaf_daaf-claude-config-restore-swap; do
                        lbl="$(_rm_swap_state "${v}")"
                        if [ "${lbl}" = running ]; then echo "${v}"; fi
                        if [ "${lbl}" = stopped ] && [ "${mode}" = container ]; then echo "${v}"; fi
                    done
                    return 0
                fi
                if [[ "${a}" == *"-aq"* ]]; then
                    for v in "$@"; do case "${v}" in label=*) lbl="${v#label=}" ;; esac; done
                    awk -v l="${lbl:-}" '$1 == l { print $2 }' "${st}/helpers"
                elif [[ "${a}" == *"--filter"*"--filter"* ]]; then
                    # The swap-time re-check. RM_FAIL=psswap: `docker ps` itself fails.
                    # A stderr line on success too: names must come from stdout only.
                    if [ "${RM_FAIL:-}" = psswap ]; then
                        echo "Cannot connect to the Docker daemon at unix:///var/run/docker.sock." >&2
                        return 1
                    fi
                    echo "fake-docker-ps-stderr-notice" >&2
                    if [ -n "${RM_RUNNING_AT_SWAP:-}" ]; then echo "${RM_RUNNING_AT_SWAP}"; fi
                else
                    # The startup check (one volume filter). RM_FAIL=psstart: `docker ps`
                    # itself fails (exit 125); RM_PS_START_STDERR=1: a stderr line on success.
                    if [ "${RM_FAIL:-}" = psstart ]; then
                        echo "Cannot connect to the Docker daemon at unix:///var/run/docker.sock." >&2
                        return 125
                    fi
                    if [ "${RM_PS_START_STDERR:-}" = 1 ]; then echo "WARNING: simulated docker config notice" >&2; fi
                    if [ ! -f "${st}/composed_down" ] && [ -n "${RM_RUNNING:-}" ]; then
                        echo "${RM_RUNNING}"
                    fi
                fi
                return 0
                ;;
            create)
                lbl=""
                for v in "$@"; do
                    if [ "${mode:-}" = label ]; then lbl="${v}"; fi
                    if [ "${v}" = "--label" ]; then mode=label; else mode=""; fi
                done
                if [[ "${a}" == *claude-config-restore-tmp* ]]; then cid=claudecid1111; else cid=helpercid0000; fi
                printf '%s %s\n' "${lbl}" "${cid}" >> "${st}/helpers"
                echo "${cid}"
                if [ "${RM_FAIL:-}" = create ] && [ "${cid}" = helpercid0000 ]; then return 1; fi
                if [ "${RM_FAIL:-}" = claudecreate ] && [ "${cid}" = claudecid1111 ]; then return 1; fi
                return 0
                ;;
            cp)
                if [ "${RM_INTERRUPT_AT:-}" = cp ]; then kill -INT "$$"; fi
                if [[ "${a}" == *".daaf-claude-config/."* ]]; then
                    if [ "${RM_FAIL:-}" = claudecp ]; then return 1; fi
                elif [ "${RM_FAIL:-}" = cp ]; then
                    echo "Error: simulated copy failure" >&2
                    return 1
                fi
                return 0
                ;;
            rm)
                # D1: a PLAIN `rm <id>` (no -f) is the holder removal; like the daemon it
                # refuses a holder that is not stopped (daemon/delete.go).
                if [ "${2:-}" != "-f" ]; then
                    # R5: a swap container that started after the leftover check.
                    for v in ${RM_SWAP_RUNNING_AT_RM:-}; do
                        if [ "${v}" = "${2:-}" ]; then
                            echo "Error response from daemon: cannot remove container \"/${2}\": container is running: stop the container before removing or force remove" >&2
                            return 1
                        fi
                    done
                    # Fix round 8: a swap container that vanished / is being removed.
                    for v in ${RM_SWAP_GONE_AT_RM:-}; do
                        if [ "${v}" = "${2:-}" ]; then
                            echo "Error response from daemon: No such container: ${2}" >&2
                            return 1
                        fi
                    done
                    for v in ${RM_SWAP_REMOVING_AT_RM:-}; do
                        if [ "${v}" = "${2:-}" ]; then
                            echo "Error response from daemon: removal of container ${2} is already in progress" >&2
                            return 1
                        fi
                    done
                    for v in ${RM_HOLDER_RM_FAIL:-}; do
                        if [ "${v}" = "${2:-}" ]; then
                            echo "Error response from daemon: cannot remove container \"/${2}\": simulated failure" >&2
                            return 1
                        fi
                    done
                    mode=""
                    for v in ${RM_HOLDERS:-} ${RM_HOLDERS_LATE:-}; do
                        lbl="${v#*=}"
                        if [ "${lbl%%:*}" = "${2:-}" ]; then mode="$(printf '%s' "${lbl#*:}" | tr '[:upper:]' '[:lower:]')"; fi
                    done
                    case "${mode}" in
                        created|exited|dead|"") ;;
                        *)
                            echo "Error response from daemon: cannot remove container \"/${2:-}\": container is ${mode}: stop the container before removing or force remove" >&2
                            return 1
                            ;;
                    esac
                    printf '%s\n' "${2:-}" >> "${st}/holders_removed"
                    return 0
                fi
                for v in "$@"; do cid="${v}"; done
                awk -v c="${cid}" '$2 != c' "${st}/helpers" > "${st}/helpers.new"
                mv "${st}/helpers.new" "${st}/helpers"
                return 0
                ;;
            run)
                case "${a}" in
                    *"AVAIL_KB="*)
                        if [ "${RM_SPACE_FAIL:-0}" = 1 ]; then echo "stat: simulated failure" >&2; return 1; fi
                        if [[ "${a}" == *"-restore-tmp:/src:ro"* ]]; then
                            echo "AVAIL_KB=${RM_SWAP_AVAIL_KB:-${RM_AVAIL_KB:-104857600}}"
                            echo "LIVE_KB=${RM_LIVE_KB:-1000}"
                            echo "SRC_KB=${RM_SRC_KB:-1000}"
                        else
                            echo "AVAIL_KB=${RM_AVAIL_KB:-104857600}"
                            echo "LIVE_KB=${RM_LIVE_KB:-1000}"
                        fi
                        return 0
                        ;;
                    *"test ! -e /src/.daaf-restore-swap-started"*)
                        case "${RM_LEFTOVER_MARKER:-}" in
                            yes) return 3 ;;
                            err) return 125 ;;
                        esac
                        return 0
                        ;;
                    *"--name "*"-restore-swap"*)
                        if [[ "${a}" == *claude-config-restore-swap* ]]; then
                            if [ "${RM_INTERRUPT_AT:-}" = claudeswap ]; then kill -INT "$$"; fi
                            if [ "${RM_FAIL:-}" = claudeswap ]; then return 1; fi
                            return "${RM_CLAUDE_SWAP_EXIT:-0}"
                        fi
                        if [ "${RM_INTERRUPT_AT:-}" = swap ]; then kill -INT "$$"; fi
                        if [ "${RM_INTERRUPT_AT:-}" = pause_swap ]; then
                            : > "${st}/pause_armed"
                            # Exec'd sleeper, as in the `volume rm` arm (fix pass #19).
                            sh -c 'sleep 1; kill -INT "$1"' sh "$$" > /dev/null 2>&1 < /dev/null &
                        fi
                        if [ "${RM_FAIL:-}" = swap ]; then return 1; fi
                        return "${RM_SWAP_EXIT:-0}"
                        ;;
                    *"cmp -s /tmp/src.lst"*)
                        if [[ "${a}" == *claude-config-restore-tmp* ]]; then mode="${RM_CLAUDE_SWAP_VERIFY:-MATCH}"; else mode="${RM_SWAP_VERIFY:-MATCH}"; fi
                        case "${mode}" in
                            MATCH) echo "SWAP_VERIFY=MATCH" ;;
                            MISMATCH) echo "SWAP_VERIFY=MISMATCH" ;;
                            ERRORS) echo "SWAP_VERIFY_ERRORS=1" ;;
                            NONE) return 125 ;;
                        esac
                        if [[ "${a}" == *claude-config-restore-tmp* ]]; then
                            echo "SWAP_VERIFY_ENTRIES=${RM_CLAUDE_SWAP_VERIFY_ENTRIES:-3:3}"
                        else
                            echo "SWAP_VERIFY_ENTRIES=${RM_SWAP_VERIFY_ENTRIES:-3:3}"
                        fi
                        return 0
                        ;;
                    *"find /dest -mindepth 1"*)
                        if [ "${RM_FAIL:-}" = emptycheck ]; then echo "find: simulated failure" >&2; return 1; fi
                        if [[ "${a}" == *claude-config-restore-tmp* ]]; then mode=claude; else mode=data; fi
                        if [ "${RM_TEMP_NOT_EMPTY:-}" = "${mode}" ]; then echo "/dest/someone-elses-file"; fi
                        if [ "${RM_EMPTYCHECK_STDERR:-}" = 1 ]; then echo "WARNING: simulated docker notice on stderr" >&2; fi
                        return 0
                        ;;
                    *"RESTORED_FILES="*)
                        if [[ "${a}" == *"-restore-tmp:/dest:ro"* ]]; then
                            case "${RM_TEMP_COUNT_MODE:-}" in
                                errors) echo "RESTORED_COUNT_ERRORS=2"; return 0 ;;
                                fail) echo "temp count container failed" >&2; return 1 ;;
                            esac
                            echo "RESTORED_FILES=${RM_TEMP_COUNT:-1}"
                            return 0
                        fi
                        # The post-swap count runs in $( ); $$ is still the script's PID.
                        if [ "${RM_INTERRUPT_AT:-}" = count ]; then kill -INT "$$"; fi
                        case "${RM_LIVE_MODE:-}" in
                            errors) echo "RESTORED_COUNT_ERRORS=2"; return 0 ;;
                            fail) echo "verification container failed" >&2; return 1 ;;
                            bare) echo "1"; return 0 ;;
                            errorsfail) echo "RESTORED_COUNT_ERRORS=2"; return 1 ;;
                            countfail) echo "RESTORED_FILES=1"; return 1 ;;
                            zero) echo "RESTORED_FILES=0"; return 0 ;;
                        esac
                        echo "RESTORED_FILES=${RM_LIVE_COUNT:-${RM_TEMP_COUNT:-1}}"
                        return 0
                        ;;
                    *"test -f /dest/.daaf-permissions"*)
                        if [[ " ${RM_MANIFESTS-perms symlinks claudesymlinks} " == *" perms "* ]]; then return 0; fi
                        return 1
                        ;;
                    *"test -f /dest/.daaf-symlinks"*)
                        if [[ "${a}" == *claude-config-restore-tmp* ]]; then mode=claudesymlinks; else mode=symlinks; fi
                        if [[ " ${RM_MANIFESTS-perms symlinks claudesymlinks} " == *" ${mode} "* ]]; then return 0; fi
                        return 1
                        ;;
                    *"chmod 644"*)
                        if [ "${RM_FAIL:-}" = perms ]; then return 1; fi
                        if [ "${RM_FAIL:-}" = crash ]; then exit 7; fi
                        return 0
                        ;;
                    *"ln -sf"*)
                        if [[ "${a}" == *claude-config-restore-tmp* ]]; then mode=claudesymlinks; else mode=symlinks; fi
                        if [ "${RM_FAIL:-}" = "${mode}" ]; then return 1; fi
                        return 0
                        ;;
                    *"rm -rf /dest/.daaf-claude-config"*)
                        if [ "${RM_FAIL:-}" = strip ]; then return 1; fi
                        return 0
                        ;;
                    *"chown -R 1000:1000 /dest"*)
                        if [[ "${a}" == *claude-config-restore-tmp* ]]; then mode=claudechown; else mode=chown; fi
                        if [ "${RM_FAIL:-}" = "${mode}" ]; then return 1; fi
                        return 0
                        ;;
                    *"touch /dest/.daaf-restore-swap-started"*)
                        if [ "${RM_FAIL:-}" = marker ]; then return 1; fi
                        return 0
                        ;;
                esac
                return 0
                ;;
        esac
        return 0
    }
    # The state of swap container $1 (running | stopped | empty = absent), shared by the
    # inspect arm and the exact-name lists. The data swap container also exists once the
    # data swap ran when RM_SWAP_AFTER says so.
    _rm_swap_state() {
        local m
        if [[ "$1" == *claude-config-restore-swap ]]; then
            m="${RM_CLAUDE_SWAP_CONTAINER:-}"
        else
            m="${RM_SWAP_CONTAINER:-}"
            if [ -z "${m}" ] && [ -n "${RM_SWAP_AFTER:-}" ] && grep -q -- "--sig-proxy=false --name $1 " "${TEST_DIR}/docker_calls.log"; then
                m="${RM_SWAP_AFTER}"
            fi
        fi
        printf '%s' "${m}"
    }
    # The "<id> <state>" holder lines of volume $1 (RM_HOLDERS, plus RM_HOLDERS_LATE once
    # that volume was listed twice), minus the holders a plain `rm` already removed.
    # Always exit 0 (it runs inside the script's `set -e` shell).
    _rm_holder_lines() {
        local w id words="${RM_HOLDERS:-}"
        if [ "$(grep -cxF -- "$1" "${TEST_DIR}/holder_lists" || true)" -ge 2 ]; then words="${words} ${RM_HOLDERS_LATE:-}"; fi
        for w in ${words}; do
            [ "${w%%=*}" = "$1" ] || continue
            id="${w#*=}"
            if grep -qxF -- "${id%%:*}" "${TEST_DIR}/holders_removed"; then continue; fi
            printf '%s %s\n' "${id%%:*}" "${id#*:}"
        done
        return 0
    }
    export -f docker _rm_swap_state _rm_holder_lines
}

# Print every logged docker call that WRITES to a LIVE volume (empty = none):
# `volume create` / `volume rm` of a name that is not a -restore-tmp volume, the swap
# call (named -restore-swap container, or any --sig-proxy run), and any `-v <name>:/dest`
# mount without `:ro` whose volume is not a -restore-tmp volume. Read-only mounts of the
# live volume (space check, final count) are allowed.
_live_writes() {
    awk '
        /^volume (create|rm) / { if ($NF !~ /-restore-tmp$/) { print "live volume op: " $0 }; next }
        /--name [^ ]*-restore-swap/ || /--sig-proxy/ { print "swap: " $0; next }
        {
            s = $0
            while (match(s, /-v [^ ]+:\/dest( |$)/)) {
                m = substr(s, RSTART, RLENGTH)
                if (m !~ /-restore-tmp:\/dest/) { print "live write mount: " $0; break }
                s = substr(s, RSTART + RLENGTH)
            }
        }
    ' "$1"
}

# The live volumes were never written (call after `run`; it re-runs `run`).
_assert_no_live_write() {
    [ -f "${TEST_DIR}/docker_calls.log" ]
    run _live_writes "${TEST_DIR}/docker_calls.log"
    assert_output ""
}

# Standard backup fixture: N plain data files (default 1), no manifests, no Claude.
_make_backup() {
    local b="${TEST_DIR}/2026-01-01_daaf_backup" i
    mkdir -p "${b}"
    for i in $(seq 1 "${1:-1}"); do printf 'data\n' > "${b}/f${i}"; done
}

# --- Syntax ---

@test "restore_from_backup.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

# --- Preflight: missing Docker ---

@test "restore: fails when docker command is not found" {
    mock_no_docker
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker"
}

# --- Preflight: Docker daemon not running ---

@test "restore: fails when Docker daemon is not running" {
    MOCK_DOCKER_INFO_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

# --- Preflight: volume not found ---

@test "restore: fails when Docker volume does not exist" {
    MOCK_DOCKER_VOLUME_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "not found"
}

# --- No backups found ---

@test "restore: fails when no backup folders exist" {
    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_failure
    assert_output --partial "No backup folders found"
}

@test "restore: suggests daaf-docker folder when no backups found" {
    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_failure
    assert_output --partial "daaf-docker"
}

# --- Backup discovery ---

@test "restore: discovers backup folders matching date pattern" {
    local today
    today=$(date +%Y-%m-%d)
    mkdir -p "${TEST_DIR}/${today}_daaf_backup"
    touch "${TEST_DIR}/${today}_daaf_backup/file1"

    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    # Pipe empty input so read fails and script exits
    run bash -c 'echo "" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    # Should list the backup even if selection fails
    assert_output --partial "${today}_daaf_backup"
}

@test "restore: discovers multiple backups with suffixes" {
    local today
    today=$(date +%Y-%m-%d)
    mkdir -p "${TEST_DIR}/${today}_daaf_backup"
    mkdir -p "${TEST_DIR}/${today}a_daaf_backup"
    touch "${TEST_DIR}/${today}_daaf_backup/f1"
    touch "${TEST_DIR}/${today}a_daaf_backup/f1"

    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    run bash -c 'echo "" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_output --partial "${today}_daaf_backup"
    assert_output --partial "${today}a_daaf_backup"
}

@test "restore: listing excludes Claude subfolder and manifest, annotates Claude state" {
    local today
    today=$(date +%Y-%m-%d)
    mkdir -p "${TEST_DIR}/${today}_daaf_backup"
    # Two data files, a manifest, and a non-empty Claude subfolder.
    touch "${TEST_DIR}/${today}_daaf_backup/data1"
    touch "${TEST_DIR}/${today}_daaf_backup/data2"
    printf 'scripts/run.sh\n' > "${TEST_DIR}/${today}_daaf_backup/.daaf-permissions"
    mkdir -p "${TEST_DIR}/${today}_daaf_backup/.daaf-claude-config"
    touch "${TEST_DIR}/${today}_daaf_backup/.daaf-claude-config/creds"

    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    run bash -c 'echo "" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    # Count must be the 2 data files only (not the manifest, not the Claude file).
    assert_output --partial "(2 files + Claude state,"
}

@test "restore: listing shows plain count when no Claude state present" {
    local today
    today=$(date +%Y-%m-%d)
    mkdir -p "${TEST_DIR}/${today}_daaf_backup"
    touch "${TEST_DIR}/${today}_daaf_backup/data1"
    printf 'scripts/run.sh\n' > "${TEST_DIR}/${today}_daaf_backup/.daaf-permissions"

    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    run bash -c 'echo "" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    # 1 data file, no Claude annotation, manifest excluded from the count.
    assert_output --partial "(1 files,"
    refute_output --partial "Claude state"
}

@test "restore: ignores directories not matching backup pattern" {
    mkdir -p "${TEST_DIR}/2026-04-21_daaf_backup"
    mkdir -p "${TEST_DIR}/random_folder"
    mkdir -p "${TEST_DIR}/not_a_backup"
    touch "${TEST_DIR}/2026-04-21_daaf_backup/f1"

    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    run bash -c 'echo "" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_output --partial "2026-04-21_daaf_backup"
    refute_output --partial "random_folder"
    refute_output --partial "not_a_backup"
}

# --- DAAF_NESTED behavior ---

@test "restore: suppresses pause trap when DAAF_NESTED=1" {
    export DAAF_NESTED=1
    MOCK_DOCKER_VOLUME_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    refute_output --partial "Press Enter"
}

# --- Banner ---

@test "restore: displays the DAAF Restore banner" {
    export DAAF_NESTED=1
    MOCK_DOCKER_VOLUME_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_output --partial "DAAF Restore from Backup"
}

# --- Structural: safety features present ---

@test "restore: contains destructive warning text" {
    run grep -c "DESTRUCTIVE OPERATION" "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: requires RESTORE confirmation" {
    run grep -c "Type RESTORE to confirm" "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: clears the live volume only inside the swap program (copy-then-swap)" {
    # Copy-then-swap (2026-10-01): there is no live clear before the copy any more; the
    # live volume is emptied only by SWAP_PROGRAM, after the checked temp copy and the
    # RESTORE confirmation. Exactly one `rm -rf /dest/*` remains, and it is in it --
    # gated on the state marker in /src (review round 1, B1: nothing is erased unless
    # /src is this run's marked temp copy). Review round 2 (S1): a missing marker exits 3
    # (`|| exit 3`), a code of its own, so the host can say "nothing was replaced".
    run grep -c 'rm -rf /dest/\*' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_output "1"
    run grep -c "^SWAP_PROGRAM='trap : INT TERM HUP; test -f /src/.daaf-restore-swap-started || exit 3; rm -rf /dest/\* " "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_output "1"
}

@test "restore: uses docker cp (not bind-mounted cp -a)" {
    # The copy mechanism is `docker create` + `docker cp` -- it must invoke a
    # quoted `docker cp "` (one for the data volume, one for the Claude state
    # volume) and must NOT use the old bind-mounted `cp -a /source` busybox copy.
    run grep -c 'docker create' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
    run grep -c 'docker cp "' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
    run grep -c "cp -a /source" "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_failure
}

@test "restore: repairs volume ownership after docker cp writes as root" {
    # `docker cp` INTO a container writes files as root; the restore must chown the
    # volume back to appuser (UID 1000) container-side, matching daaf-init.
    run grep -c "chown -R 1000:1000 /dest" "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: replays executable permissions from the manifest" {
    # Step 3d: when ".daaf-permissions" is present, normalize files to 644 and
    # re-apply 755 to the manifest's paths (undoing NTFS mode loss).
    run grep -c '\.daaf-permissions' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
    run grep -c 'find /dest -type f -exec chmod 644' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
    run grep -c 'chmod 755' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: skips normalization when the manifest is absent (backward compat)" {
    # No manifest => no normalization (blanket 644 would strip exec from every
    # script and be worse than the fabricated 0755). The absent-manifest NOTE must
    # cover BOTH causes: an older backup, or a manifest whose write failed at backup
    # time (Fix 3) -- so it reads "may predate permission preservation".
    run grep -c 'it may predate' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
    run grep -c 'the manifest write may have failed during' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
    run grep -c 'no normalization was applied' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: replays symlinks from the manifest (Step 3e)" {
    # Step 3e: when ".daaf-symlinks" is present, recreate each link (path TAB target)
    # container-side and chown -h it, then strip the manifest from the volume.
    run grep -c '\.daaf-symlinks' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
    run grep -c 'ln -sf -- ' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
    run grep -c 'chown -h 1000:1000' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: replays symlinks for BOTH the data volume AND the Claude volume" {
    # Regression guard for the review BLOCKER (which surfaced first in the .ps1 twin):
    # a draft that recreates symlinks only for the DATA volume and silently omits the
    # Claude-state volume still PASSES a file-wide grep for ".daaf-symlinks" or
    # "ln -sf --", because the string is present at least once. Assert the replay
    # idiom (`ln -sf --`) appears exactly TWICE -- once in the data-volume Step 3e
    # block and once in the Claude-state restore block -- and that a replay is
    # actually nested inside the CLAUDE_VOLUME_NAME restore path, not only the data one.
    run bash -c "grep -c 'ln -sf -- ' \"${REPO_ROOT}/scripts/host/restore_from_backup.sh\""
    assert_success
    assert_output "2"
    # The Claude-volume replay must live below the "Restore the Claude Code state
    # volume" header and bind CLAUDE_VOLUME_NAME:/dest. Slice the file from that header
    # to EOF and confirm both a CLAUDE_VOLUME_NAME-bound `docker run ... sh -c` and an
    # `ln -sf --` inside that region -- proving the replay is wired for the second
    # volume, not just referenced globally.
    # Copy-then-swap: the replay runs on the Claude TEMP volume (prepared before the swap).
    # The image is the pinned constant (fix pass #26), never a bare `busybox`.
    run bash -c "awk '/Restore the Claude Code state volume/{f=1} f' \"${REPO_ROOT}/scripts/host/restore_from_backup.sh\" | grep -cF 'CLAUDE_TEMP_VOLUME_NAME}:/dest\" \"\${BUSYBOX_IMAGE}\" sh -c'"
    assert_success
    assert_output "1"
    run bash -c "awk '/Restore the Claude Code state volume/{f=1} f' \"${REPO_ROOT}/scripts/host/restore_from_backup.sh\" | grep -c 'ln -sf -- '"
    assert_success
    assert_output "1"
}

@test "restore: symlink replay program is quote-free (Windows arg safety)" {
    # The Step 3e sh -c replay program is shared logically with the .ps1 twin; an
    # embedded double quote would corrupt Windows PS 5.1 arg parsing. It uses octal
    # printf for the BOM (busybox sed has no \\xNN escapes), never tr -d.
    run grep -c 'bom=$(printf' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
    run grep -c 'IFS=$tab read -r p t' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: excludes .daaf-symlinks from listing and scan counts" {
    # A backup with 1 data file, both manifests, and no Claude state must list and
    # scan as "1 files" (neither manifest counted).
    local today
    today=$(date +%Y-%m-%d)
    mkdir -p "${TEST_DIR}/${today}_daaf_backup"
    touch "${TEST_DIR}/${today}_daaf_backup/data1"
    printf 'scripts/run.sh\n' > "${TEST_DIR}/${today}_daaf_backup/.daaf-permissions"
    printf 'sub/link\ttarget\n' > "${TEST_DIR}/${today}_daaf_backup/.daaf-symlinks"

    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    run bash -c 'echo "" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_output --partial "(1 files,"
    refute_output --partial "(2 files"
    refute_output --partial "(3 files"
}

@test "restore: listing and scan exclude only ROOT manifests (a nested same-name data file counts)" {
    # Root-relative exclusions, the rule every count site shares: a data file named
    # .daaf-symlinks or .daaf-permissions deeper in the tree is restored content, so
    # the listing must show 3 files here, not 1 (the old name-anywhere `-not -name`
    # form dropped both nested files).
    local today
    today=$(date +%Y-%m-%d)
    mkdir -p "${TEST_DIR}/${today}_daaf_backup/sub"
    touch "${TEST_DIR}/${today}_daaf_backup/data1"
    touch "${TEST_DIR}/${today}_daaf_backup/sub/.daaf-symlinks"
    touch "${TEST_DIR}/${today}_daaf_backup/sub/.daaf-permissions"
    printf 'scripts/run.sh\n' > "${TEST_DIR}/${today}_daaf_backup/.daaf-permissions"
    : > "${TEST_DIR}/${today}_daaf_backup/.daaf-symlinks"

    export DAAF_NESTED=1 RM_TEMP_COUNT=3
    _mock_restore_docker

    # Select backup 1, then cancel at the RESTORE prompt: the scan count is printed
    # before the prompt, so both counts are observable without restoring. (The temp
    # copy holds 3 files too, so the prompt is reached.)
    run bash -c 'printf "1\nno\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_output --partial "(3 files,"
    assert_output --partial "Found 3 files"
    assert_output --partial "Restore cancelled."
}

@test "restore: listing and scan count a file whose NAME holds a newline once (NUL count, like the backup)" {
    # Review round 2 (F5g): the listing and scan counted lines (`wc -l`), while the
    # backup's completion report counts NULs, so a newline name made them disagree.
    local today
    today=$(date +%Y-%m-%d)
    mkdir -p "${TEST_DIR}/${today}_daaf_backup/sub"
    touch "${TEST_DIR}/${today}_daaf_backup/data1"
    touch "${TEST_DIR}/${today}_daaf_backup/sub/name"$'\n'"with-newline"
    : > "${TEST_DIR}/${today}_daaf_backup/.daaf-symlinks"

    export DAAF_NESTED=1 RM_TEMP_COUNT=2
    _mock_restore_docker

    run bash -c 'printf "1\nno\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_output --partial "(2 files,"
    assert_output --partial "Found 2 files"
    refute_output --partial "(3 files,"
    assert_output --partial "Restore cancelled."
    # Every host-side NUL count runs tr in the C locale (macOS multibyte tr).
    run grep -c -- "-print0.*| LC_ALL=C tr -dc '\\\\000' | wc -c" "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_output "1"
}

@test "restore: replays symlinks when the backup contains a symlink manifest" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    printf 'sub/link\t../target\n' > "${TEST_DIR}/2026-01-01_daaf_backup/.daaf-symlinks"

    export DAAF_NESTED=1

    # Step 3e probes the TEMP volume with `docker run ... test -f /dest/.daaf-symlinks`.
    # Model the symlink manifest as PRESENT; the permissions manifest as ABSENT.
    export RM_MANIFESTS="symlinks"
    _mock_restore_docker

    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_success
    assert_output --partial "Restoring symlinks"
    # The replay ran against the temp copy, never the live volume.
    run grep -E "daaf_daaf-data-restore-tmp:/dest ${BB_RE} sh -c .*ln -sf" "${TEST_DIR}/docker_calls.log"
    assert_success
}

@test "restore: no-ops symlink replay when the manifest is absent" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    # No .daaf-symlinks manifest in this backup.

    export DAAF_NESTED=1

    # Both manifests probe ABSENT (test -f => 1); verification returns a count.
    export RM_MANIFESTS=""
    _mock_restore_docker

    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    # No symlink manifest => the "Restoring symlinks" line must NOT appear, and the
    # restore still completes. The two informational NOTEs this older-style backup
    # triggers (no permission manifest, no Claude state) do NOT latch the warnings
    # banner: the plain banner, never "WITH WARNINGS" (partial match on "complete!"
    # so "Restore completed WITH WARNINGS" cannot satisfy it).
    assert_success
    refute_output --partial "Restoring symlinks"
    assert_output --partial "NOTE: No .daaf-permissions manifest found"
    assert_output --partial "NOTE: This backup does not contain Claude Code state"
    assert_output --partial "Restore complete!"
    refute_output --partial "WITH WARNINGS"
    # The mock prints the RESTORED_FILES marker, so this is the VERIFIED happy path,
    # not the "could not verify" fallback a bare number used to drift into.
    assert_output --partial "Verified: 1 files in restored volume."
    assert_output --partial "Files:    1 files in volume"
    refute_output --partial "Could not verify the restored file count"
}

@test "restore: checks for running containers before restoring" {
    run grep -c "docker ps --filter" "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: the startup running-container check reads docker ps's exit code (no || true)" {
    # 2026-10-02: a failing startup `docker ps` refuses (behaviour: the "startup:" cases).
    run grep -cF 'RUNNING_CONTAINERS="$(docker ps --filter "volume=${VOLUME_NAME}" --format '"'"'{{.Names}}'"'"' 2>/dev/null)" || RUNNING_CONTAINERS_EXIT=$?' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_output "1"
    run grep -c 'docker ps --filter.*|| true' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_output "0"
}

@test "restore: verifies file count after restore" {
    run grep -c "Verifying restore" "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: compares the restored count EXACTLY with the checked temp copy's count" {
    # Review round 1 (B1 item 4): the old 1%-tolerance "File count mismatch" WARNING
    # against the backup count is gone; the restored count must equal the temp count.
    run grep -c '"${RESTORED_COUNT}" -ne "${TEMP_COUNT}"' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_output "1"
    run grep -c "File count mismatch" "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_output "0"
}

# --- Invalid selection ---

@test "restore: rejects non-numeric selection" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"

    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    run bash -c 'echo "abc" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure
    assert_output --partial "Invalid selection"
}

@test "restore: rejects out-of-range selection" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"

    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    run bash -c 'echo "99" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure
    assert_output --partial "Invalid selection"
}

# --- Cancellation ---

@test "restore: cancels when user does not type RESTORE" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"

    export DAAF_NESTED=1
    _mock_restore_docker

    run bash -c 'printf "1\nno\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_success
    assert_output --partial "Restore cancelled. Your DAAF data has not been changed."
    # Copy-then-swap: the confirmation now comes AFTER the temp copy was checked; a
    # cancel there removes the temp copy and never touches the live volume.
    assert_output --partial "The backup was copied into Docker and checked: 1 files."
    run grep -cxF 'volume rm daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    _assert_no_live_write
}

# --- Running container detection ---

@test "restore: offers to stop running containers" {
    export DAAF_NESTED=1
    MOCK_DOCKER_VOLUME_EXIT=0

    # Override docker to return a container name for ps --filter
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            ps)
                echo "daaf-daaf-docker-1"
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    # Decline the stop prompt
    run bash -c 'echo "n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_output --partial "container is currently running"
    assert_output --partial "Restore cancelled"
}

@test "restore: warns about Claude Code sessions when containers running" {
    run grep -c "Claude Code sessions" "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

# =========================================================================
# Dry-run mode
# =========================================================================

@test "restore: dry-run completes successfully with backups present" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"

    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: dry-run produces DRY-RUN markers" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"

    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh" 2>&1
    assert_success
    assert_output --partial "[DRY-RUN]"
}

@test "restore: dry-run shows backup count" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    mkdir -p "${TEST_DIR}/2026-01-02_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    touch "${TEST_DIR}/2026-01-02_daaf_backup/f1"

    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh" 2>&1
    assert_success
    assert_output --partial "2 backup(s)"
}

@test "restore: dry-run succeeds when no backups exist" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
    assert_output --partial "No backup folders found"
}

# =========================================================================
# --- Error paths ---
# =========================================================================

@test "restore: running container detected offers to stop" {
    export DAAF_NESTED=1
    MOCK_DOCKER_VOLUME_EXIT=0

    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            ps)
                echo "daaf-daaf-docker-1"
                return 0
                ;;
            compose)
                shift
                case "$1" in
                    down) return 0 ;;
                    *)    return 0 ;;
                esac
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    # User answers 'y' to stop, then the script continues looking for backups
    # No backups exist so it exits with failure
    run bash -c 'echo "y" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"' 2>&1
    assert_output --partial "container is currently running"
    assert_output --partial "must be stopped before restoring"
    assert_output --partial "Stopping containers"
}

@test "restore: user declines to stop container exits cleanly" {
    export DAAF_NESTED=1
    MOCK_DOCKER_VOLUME_EXIT=0

    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            ps)
                echo "daaf-daaf-docker-1"
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash -c 'echo "n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_success
    assert_output --partial "Restore cancelled"
}

@test "restore: a failed live replacement (swap) exits 1 and KEEPS the temp copy with recovery steps" {
    # Was "volume clear fails exits with error". Copy-then-swap has no live clear before
    # the copy: the live volume is cleared only inside the swap program, so the
    # equivalent failure is the swap itself (its rm -rf / cp -a) exiting nonzero. The
    # temp copy may then hold the only complete copy, so it must NOT be removed.
    _make_backup
    export DAAF_NESTED=1 RM_FAIL=swap
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure 1
    assert_output --partial "ERROR: Replacing your DAAF data did not complete (exit 1)."
    assert_output --partial "Your DAAF data may now be incomplete. The checked copy of the backup is"
    assert_output --partial "kept in Docker (volume(s): daaf_daaf-data-restore-tmp), and your backup"
    assert_output --partial "folder 2026-01-01_daaf_backup/ is unchanged. To finish, run this restore again"
    assert_output --partial "bash restore_from_backup.sh"
    assert_output --partial "It will offer to remove the leftover copy (answer y) and then redo the restore."
    refute_output --partial "Restore complete"
    run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    # The swap ran with --sig-proxy=false under its fixed, unlabelled name.
    run grep -cE "^run --rm --sig-proxy=false --name daaf_daaf-data-restore-swap -v daaf_daaf-data-restore-tmp:/src:ro -v daaf_daaf-data:/dest ${BB_RE} sh -c trap : INT TERM HUP; " "${TEST_DIR}/docker_calls.log"
    assert_output "1"
}

@test "restore: zero files after the swap goes through the after-swap failure path (temp kept, exit 1)" {
    # Review round 1 (I4): was "0 files found ... Consider re-running or reinstalling
    # DAAF", which hid the kept temp copy and the unchanged backup folder.
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    export DAAF_NESTED=1
    # The temp copy checks out (1 file); the post-swap count of the LIVE volume reads 0.
    export RM_LIVE_MODE=zero
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure 1
    assert_output --partial "ERROR: After replacing your DAAF data, it holds 0 files, but the checked"
    assert_output --partial "       copy held 1."
    assert_output --partial "kept in Docker (volume(s): daaf_daaf-data-restore-tmp), and your backup"
    assert_output --partial "It will offer to remove the leftover copy (answer y) and then redo the restore."
    refute_output --partial "reinstalling DAAF"
    refute_output --partial "Restore complete"
    run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
}

@test "restore: a restored count that differs from the temp count by ONE is an after-swap failure (exact, no 1% tolerance)" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    for i in $(seq 1 200); do
        touch "${TEST_DIR}/2026-01-01_daaf_backup/f${i}"
    done
    export DAAF_NESTED=1
    # 199 of 200 was within the old 1% tolerance (a silent pass); now it fails.
    export RM_TEMP_COUNT=200 RM_LIVE_COUNT=199
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure 1
    assert_output --partial "ERROR: After replacing your DAAF data, it holds 199 files, but the checked"
    assert_output --partial "       copy held 200."
    assert_output --partial "Your DAAF data may now be incomplete. The checked copy of the backup is"
    refute_output --partial "File count mismatch"
    refute_output --partial "Restore complete"
    run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
}

@test "restore: subfolder-strip failure on the TEMP copy stops before the prompt; live data untouched" {
    # Was "...exits with hygiene warning" ("may REMAIN inside the data volume"). The
    # strip now runs on the temporary copy, so a failure just stops the restore: the
    # temp copy is removed and the live volume was never written.
    _make_backup
    export DAAF_NESTED=1 RM_FAIL=strip
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure 1
    assert_output --partial "ERROR: Failed to remove the .daaf-claude-config subfolder from the temporary copy."
    assert_output --partial "Your DAAF data has not been changed."
    refute_output --partial "DESTRUCTIVE OPERATION"
    run grep -cxF 'volume rm daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    _assert_no_live_write
}

@test "restore: ownership-repair (chown) failure on the TEMP copy stops before the prompt" {
    # Was "...exits with ownership warning" ("Failed to repair ownership").
    _make_backup
    export DAAF_NESTED=1 RM_FAIL=chown
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure 1
    assert_output --partial "ERROR: Failed to set file ownership in the temporary copy."
    assert_output --partial "Your DAAF data has not been changed."
    refute_output --partial "DESTRUCTIVE OPERATION"
    run grep -cxF 'volume rm daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    _assert_no_live_write
}

@test "restore: no backup folders found exits with error" {
    # No backup directories created in TEST_DIR
    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    run bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_failure
    assert_output --partial "No backup folders found"
}

# --- Step 3d: permission replay ---

@test "restore: replays permissions when the backup contains a manifest" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    printf 'scripts/run.sh\n' > "${TEST_DIR}/2026-01-01_daaf_backup/.daaf-permissions"

    export DAAF_NESTED=1

    # Step 3d probes the TEMP volume with `docker run ... test -f /dest/.daaf-permissions`.
    # Model the manifest as PRESENT (test -f => 0) so the replay sh -c path runs.
    export RM_MANIFESTS="perms"
    _mock_restore_docker

    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_success
    assert_output --partial "Restoring executable permissions"
    run grep -E "daaf_daaf-data-restore-tmp:/dest ${BB_RE} sh -c .*chmod 644" "${TEST_DIR}/docker_calls.log"
    assert_success
}

@test "restore: notes older backups that predate the permission manifest" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    # No .daaf-permissions manifest in this backup (older backup).

    export DAAF_NESTED=1

    # Step 3d probes with `docker run ... test -f /dest/.daaf-permissions`. Model the
    # manifest as ABSENT (test -f => 1) so the "predates" branch runs. Verification
    # still returns a non-zero count so the restore succeeds.
    export RM_MANIFESTS="symlinks"
    _mock_restore_docker

    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_success
    assert_output --partial "may predate"
    assert_output --partial "permission preservation"
}

# =========================================================================
# --- Helper-container reap on `docker create` launch failure ---
# =========================================================================
# `docker create` echoes a CID to stdout; if the command then exits nonzero the
# command substitution has ALREADY captured that CID. Copy-then-swap labels every
# prepare-phase helper (org.daaf.restore-tmp-for=<live volume>) and reaps them by an
# exact label filter before removing the temp volume (a leftover helper keeps the
# temp volume "in use"). The mock tracks created/removed helpers in ${TEST_DIR}/helpers,
# so a leak is observable after `run` (a bats array does not survive the subshell).

@test "restore: main create launch failure reaps the captured helper container (by label)" {
    _make_backup
    export DAAF_NESTED=1 RM_FAIL=create
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure 1
    assert_output --partial "ERROR: Could not create the helper container for the copy."
    assert_output --partial "Your DAAF data has not been changed."
    # Reaped via the exact label filter, then the temp volume removed.
    run grep -cxF 'ps -aq --filter label=org.daaf.restore-tmp-for=daaf_daaf-data' "${TEST_DIR}/docker_calls.log"
    assert_success
    run grep -cxF 'rm -f helpercid0000' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    run grep -cxF 'volume rm daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    run cat "${TEST_DIR}/helpers"
    assert_output ""
    _assert_no_live_write
}

@test "restore: Claude create launch failure reaps the captured CID and STOPS (D2: fatal, nothing changed)" {
    # Was "...(WARNING, not fatal)". User decision D2 (2026-10-01): a Claude-state
    # preparation failure stops the restore before ANY volume is replaced, so the data
    # and its login state stay consistent. The captured CID is still reaped (never
    # blanked), and BOTH temp volumes are removed.
    _make_full_backup
    export DAAF_NESTED=1 RM_FAIL=claudecreate
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure 1
    assert_output --partial "ERROR: Could not prepare the Claude Code state (login and session history)"
    assert_output --partial "from this backup: copying it into Docker failed."
    assert_output --partial "Your DAAF data has not been changed."
    refute_output --partial "DESTRUCTIVE OPERATION"
    refute_output --partial "Restore complete"
    run grep -cxF 'rm -f claudecid1111' "${TEST_DIR}/docker_calls.log"
    assert_success
    run grep -cxF 'volume rm daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    run grep -cxF 'volume rm daaf_daaf-claude-config-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    run cat "${TEST_DIR}/helpers"
    assert_output ""
    _assert_no_live_write
}

# =========================================================================
# --- FU1: a host read error makes the backup count a LOWER BOUND ---
# =========================================================================
# _daaf_tree_count captures find's stderr with the count; any error line makes the
# count a lower bound. The listing shows it as "N+" with a note; the scan of the
# SELECTED backup REFUSES (ERROR, exit 1) before the destructive prompt, because
# `docker cp` would hit the same unreadable files partway through the copy into the temporary volume.
# The fixture is a chmod-000 subfolder inside TEST_DIR (teardown re-opens it). Root
# reads through mode 000, so these skip there.

_make_locked_backup() {
    local b="${TEST_DIR}/2026-01-01_daaf_backup"
    mkdir -p "${b}/locked"
    touch "${b}/f1"
    touch "${b}/locked/hidden"
    : > "${b}/.daaf-symlinks"
    chmod 000 "${b}/locked"
}

@test "restore FU1: listing shows an unreadable backup's count as 'N+' with a lower-bound note" {
    [ "$(id -u)" -ne 0 ] || skip "root can read a chmod-000 folder"
    _make_locked_backup
    export DAAF_NESTED=1
    # Empty selection: the listing prints, then the invalid selection exits 1.
    run bash -c 'echo "" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_output --partial "1) 2026-01-01_daaf_backup  (1+ files,"
    assert_output --partial "(some folders in this backup could not be read; the file count is a lower bound)"
}

@test "restore FU1: the scan REFUSES an unreadable backup (exit 1) before the destructive prompt" {
    [ "$(id -u)" -ne 0 ] || skip "root can read a chmod-000 folder"
    _make_locked_backup
    export DAAF_NESTED=1
    # Log every docker call: the refusal must precede any temp-volume create or copy.
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        printf '%s\n' "$*" >> "${TEST_DIR}/docker_calls.log"
        case "$1" in
            info|volume|ps) return 0 ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure 1
    assert_output --partial "ERROR: Could not read every file in this backup folder (at least 1 files were"
    # Reworded for copy-then-swap (user decision D4): the refusal is kept, the reason
    # is that the copy would fail partway, no longer that live data would be erased.
    assert_output --partial "readable), so it cannot be restored safely: the copy would most likely fail"
    assert_output --partial "partway on the same problem. Your DAAF data has not been changed."
    assert_output --partial "First error: find:"
    assert_output --partial "Make every folder and file in 2026-01-01_daaf_backup/ readable by your user account"
    # Never reached the destructive warning or its "Type RESTORE" prompt (bash's
    # `read -p` prints no prompt when stdin is a pipe, so the banner above it is the
    # observable anchor), and never touched the volume.
    refute_output --partial "DESTRUCTIVE OPERATION"
    refute_output --partial "Type RESTORE"
    refute_output --partial "Found "
    run grep -F 'rm -rf' "${TEST_DIR}/docker_calls.log"
    assert_failure
    run grep -E '^(create|cp|volume create|volume rm) ' "${TEST_DIR}/docker_calls.log"
    assert_failure
}

# =========================================================================
# --- Unreadable FILES and an unreadable backup ROOT also refuse ---
# =========================================================================
# `find` opens folders, never regular files, so _daaf_tree_count cannot see a mode-000
# (or root-owned 0600) FILE in a readable folder. The scan's second pass tests every
# regular file with POSIX `[ -r ]` and refuses before the destructive prompt. A backup
# ROOT the user cannot enter refuses at selection time. Root reads through mode 000, so
# these skip there; teardown re-opens every mode (chmod -R u+rwx) before removal.

# Log every docker call so a test can prove no volume was touched.
_mock_logging_docker() {
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        printf '%s\n' "$*" >> "${TEST_DIR}/docker_calls.log"
        return 0
    }
    export -f docker
}

_assert_no_volume_touched() {
    refute_output --partial "DESTRUCTIVE OPERATION"
    refute_output --partial "Found "
    if [ -f "${TEST_DIR}/docker_calls.log" ]; then
        run grep -F 'rm -rf' "${TEST_DIR}/docker_calls.log"
        assert_failure
        # A refusal comes before copy-then-swap: no temp volume, helper, copy or swap.
        run grep -E '^(create|cp|rm|volume create|volume rm) ' "${TEST_DIR}/docker_calls.log"
        assert_failure
        _assert_no_live_write
    fi
}

@test "restore: a mode-000 FILE in a readable folder REFUSES before the destructive prompt" {
    [ "$(id -u)" -ne 0 ] || skip "root can read a chmod-000 file"
    local b="${TEST_DIR}/2026-01-01_daaf_backup"
    mkdir -p "${b}/sub"
    touch "${b}/f1" "${b}/sub/f2" "${b}/sub/secret"
    : > "${b}/.daaf-symlinks"
    chmod 000 "${b}/sub/secret"
    export DAAF_NESTED=1
    _mock_logging_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure 1
    # The folder count saw nothing wrong (find lists folders, not file contents)...
    refute_output --partial "Could not read every file in this backup folder"
    # ...so the file pass is what refused.
    assert_output --partial "ERROR: 1 file(s) in this backup folder cannot be read by your user account,"
    assert_output --partial "so it cannot be restored safely: the copy would most likely fail partway"
    assert_output --partial "on the same files. Your DAAF data has not been changed."
    assert_output --partial "First unreadable file: 2026-01-01_daaf_backup/sub/secret"
    assert_output --partial "Make every file in 2026-01-01_daaf_backup/ readable by your user account (check its"
    assert_output --partial "ownership and permissions -- e.g. a file created with sudo), then re-run the restore."
    _assert_no_volume_touched
}

@test "restore: unreadable files are COUNTED, including in the Claude subfolder and a root manifest" {
    [ "$(id -u)" -ne 0 ] || skip "root can read a chmod-000 file"
    local b="${TEST_DIR}/2026-01-01_daaf_backup"
    mkdir -p "${b}/.daaf-claude-config"
    touch "${b}/f1" "${b}/.daaf-claude-config/creds"
    : > "${b}/.daaf-permissions"
    chmod 000 "${b}/.daaf-claude-config/creds" "${b}/.daaf-permissions"
    export DAAF_NESTED=1
    _mock_logging_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure 1
    # `docker cp` copies the whole folder, so excluded-from-count paths are still checked.
    assert_output --partial "ERROR: 2 file(s) in this backup folder cannot be read by your user account,"
    _assert_no_volume_touched
}

@test "restore: a clean, fully readable backup is NOT refused by the file check" {
    local b="${TEST_DIR}/2026-01-01_daaf_backup"
    mkdir -p "${b}/sub" "${b}/.daaf-claude-config"
    touch "${b}/f1" "${b}/sub/f2" "${b}/.daaf-claude-config/creds"
    : > "${b}/.daaf-symlinks"
    : > "${b}/.daaf-permissions"
    export DAAF_NESTED=1 RM_TEMP_COUNT=2
    _mock_restore_docker
    # Cancel at the confirmation: reaching the destructive banner is the pass condition.
    run bash -c 'printf "1\nno\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_success
    assert_output --partial "Found 2 files"
    assert_output --partial "DESTRUCTIVE OPERATION"
    assert_output --partial "Restore cancelled."
    refute_output --partial "cannot be read by your user account"
    refute_output --partial "Could not check that every file"
    refute_output --partial "ERROR:"
}

@test "restore: a file check that cannot finish REFUSES (defensive branch)" {
    local b="${TEST_DIR}/2026-01-01_daaf_backup"
    mkdir -p "${b}"
    touch "${b}/f1"
    # A PATH shim `find` that fails ONLY the file-check invocation (`-exec sh -c ...`)
    # and passes every other call (the count) to the real find.
    local real_find
    real_find="$(command -v find)"
    mkdir -p "${TEST_DIR}/shim"
    printf '#!/usr/bin/env bash\ncase " $* " in *" -exec sh -c "*) echo "find: simulated check failure" >&2; exit 1 ;; esac\nexec "%s" "$@"\n' "${real_find}" > "${TEST_DIR}/shim/find"
    chmod +x "${TEST_DIR}/shim/find"
    export PATH="${TEST_DIR}/shim:${PATH}"
    export DAAF_NESTED=1
    _mock_logging_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure 1
    assert_output --partial "ERROR: Could not check that every file in this backup folder is readable, so it"
    assert_output --partial "cannot be restored safely. Your DAAF data has not been changed."
    assert_output --partial "First error: find: simulated check failure"
    refute_output --partial "file(s) in this backup folder cannot be read"
    _assert_no_volume_touched
}

@test "restore: an unreadable backup ROOT refuses at selection with a refusal-style ERROR (no bare cd error)" {
    [ "$(id -u)" -ne 0 ] || skip "root can enter a chmod-000 folder"
    local b="${TEST_DIR}/2026-01-01_daaf_backup"
    mkdir -p "${b}"
    touch "${b}/f1"
    chmod 000 "${b}"
    export DAAF_NESTED=1
    _mock_logging_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure 1
    assert_output --partial "ERROR: Could not open the backup folder 2026-01-01_daaf_backup/, so it cannot be restored."
    assert_output --partial "Your DAAF data has not been changed."
    assert_output --partial "First error: "
    assert_output --partial "Permission denied"
    assert_output --partial "Make 2026-01-01_daaf_backup/ and every folder and file in it readable by your user"
    assert_output --partial "account (check its ownership and permissions), then re-run the restore."
    refute_output --partial "Selected: "
    refute_output --partial "Scanning backup..."
    _assert_no_volume_touched
}

# =========================================================================
# --- FU2: the post-restore count is a MARKER program ---
# =========================================================================
# RESTORED_FILES=<n> only when the count's stderr was empty, else
# RESTORED_COUNT_ERRORS=<lines>. Unavailable (error marker, docker failure, or no
# marker) is a WARNING with exit 0 -- never the false "0 files found" ERROR; a count
# READ as 0 still exits 1 ("restore: zero files after restore exits with error").

# VERIFY_MODE picks the post-swap (LIVE) count's behavior; the temp copy's count is
# exact (1), so the swap runs and only the final check varies. No manifests.
_mock_verify_docker() {
    export RM_LIVE_MODE="${VERIFY_MODE}" RM_MANIFESTS=""
    _mock_restore_docker
}

@test "restore FU2: a post-restore count with read errors is a WARNING, exit 0, never '0 files found'" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    export DAAF_NESTED=1 VERIFY_MODE=errors
    _mock_verify_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_success
    assert_output --partial "WARNING: Could not verify the restored file count: Docker hit 2 read error(s)"
    assert_output --partial "while counting the restored volume."
    assert_output --partial "The copy itself reported success, so your data is most likely in place. Start"
    assert_output --partial "Files:    not verified (the restored file count could not be read)"
    refute_output --partial "0 files found"
    refute_output --partial "File count mismatch"
    refute_output --partial "not verified files in volume"
    # An unverified count latches the banner; the exit code stays 0 (asserted above).
    assert_output --partial "Restore completed WITH WARNINGS -- verify before relying on it"
    refute_output --partial "Restore complete!"
}

@test "restore FU2: a failed or marker-less post-restore count is a WARNING, exit 0" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    export DAAF_NESTED=1
    # fail: the verification container exits 1. bare: an old-style bare number with
    # no RESTORED_FILES marker is not trusted as a count.
    for mode in fail bare; do
        export VERIFY_MODE="${mode}"
        _mock_verify_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
        assert_success
        assert_output --partial "WARNING: Could not verify the restored file count (the count inside Docker did not"
        assert_output --partial "Files:    not verified (the restored file count could not be read)"
        refute_output --partial "0 files found"
        refute_output --partial "files in restored volume."
        assert_output --partial "Restore completed WITH WARNINGS -- verify before relying on it"
        refute_output --partial "Restore complete!"
    done
}

# Marker parity with the .ps1 twin (restore_from_backup.Tests.ps1 "FU2: nonzero exit
# ..."): both parse the markers on ANY exit, let an error marker choose the read-error
# WARNING variant, and trust a count marker only on exit 0.
@test "restore FU2: nonzero exit + read-error marker gives the read-error WARNING variant (twin parity)" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    export DAAF_NESTED=1 VERIFY_MODE=errorsfail
    _mock_verify_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_success
    assert_output --partial "WARNING: Could not verify the restored file count: Docker hit 2 read error(s)"
    assert_output --partial "while counting the restored volume."
    refute_output --partial "the count inside Docker did not"
    assert_output --partial "Files:    not verified (the restored file count could not be read)"
    refute_output --partial "0 files found"
    assert_output --partial "Restore completed WITH WARNINGS -- verify before relying on it"
}

@test "restore FU2: nonzero exit + a count marker is not trusted (exit-code WARNING variant, twin parity)" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    export DAAF_NESTED=1 VERIFY_MODE=countfail
    _mock_verify_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_success
    assert_output --partial "WARNING: Could not verify the restored file count (the count inside Docker did not"
    assert_output --partial "run cleanly, exit 1)."
    refute_output --partial "files in restored volume."
    assert_output --partial "Files:    not verified (the restored file count could not be read)"
    assert_output --partial "Restore completed WITH WARNINGS -- verify before relying on it"
}

@test "restore FU2: a post-restore count READ as RESTORED_FILES=0 exits 1 (not the unavailable WARNING)" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    export DAAF_NESTED=1 VERIFY_MODE=zero
    _mock_verify_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure 1
    assert_output --partial "ERROR: After replacing your DAAF data, it holds 0 files, but the checked"
    refute_output --partial "Could not verify the restored file count"
    # A fatal exit prints neither banner.
    refute_output --partial "Restore complete!"
    refute_output --partial "Restore completed WITH WARNINGS"
}

# =========================================================================
# --- Completion banner: the WITH WARNINGS latch ---
# =========================================================================
# Every non-fatal WARNING on the success path latches HAD_WARNINGS, and the final
# banner then reads "Restore completed WITH WARNINGS -- verify before relying on it"
# instead of "Restore complete!" -- with the exit code UNCHANGED (0), because callers
# (daaf.sh run_delegate) branch on the exit code only. The mismatch, unverified-count
# and Claude-create cases above assert the latch too; these cover the clean baseline
# and the remaining WARNING sites. The fixture is a CURRENT-style backup (both root
# manifests plus a non-empty Claude subfolder), so every probe finds its manifest and
# a clean run prints no NOTE at all. BANNER_FAIL picks the one step that fails.

_make_full_backup() {
    local b="${TEST_DIR}/2026-01-01_daaf_backup"
    mkdir -p "${b}/.daaf-claude-config"
    touch "${b}/f1"
    printf 'scripts/run.sh\n' > "${b}/.daaf-permissions"
    : > "${b}/.daaf-symlinks"
    touch "${b}/.daaf-claude-config/creds"
}

# BANNER_FAIL picks the one WARNING site: perms / symlinks / claudesymlinks fail that
# replay on the temp copy (RM_FAIL); space makes both free-space checks unmeasurable;
# tmprm makes the final removal of the temp volumes fail. The old "claudeclear" site is
# gone: copy-then-swap has no separate Claude clear, and a Claude preparation failure
# is now fatal (D2) instead of a WARNING.
_mock_banner_docker() {
    unset RM_FAIL RM_SPACE_FAIL
    case "${BANNER_FAIL:-none}" in
        perms|symlinks|claudesymlinks|tmprm) export RM_FAIL="${BANNER_FAIL}" ;;
        space) export RM_SPACE_FAIL=1 ;;
    esac
    _mock_restore_docker
}

@test "restore banner: a clean run prints 'Restore complete!' and never WITH WARNINGS" {
    _make_full_backup
    export DAAF_NESTED=1 BANNER_FAIL=none
    _mock_banner_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_success
    assert_output --partial "Restoring executable permissions"
    assert_output --partial "Restoring symlinks"
    assert_output --partial "Verified: 1 files in restored volume."
    assert_output --partial "Claude Code state restored."
    refute_output --partial "WARNING: Could not"
    refute_output --partial "WARNING: Failed"
    assert_output --partial "  Restore complete!"
    refute_output --partial "WITH WARNINGS"
    # The report and next-step lines follow the banner either way.
    assert_output --partial "Files:    1 files in volume"
    assert_output --partial "You can now start DAAF with:"
}

@test "restore banner: each remaining WARNING site latches WITH WARNINGS, exit 0" {
    _make_full_backup
    export DAAF_NESTED=1
    local step expect
    for step in perms symlinks claudesymlinks space tmprm; do
        case "${step}" in
            perms) expect="WARNING: Could not fully replay executable permissions." ;;
            symlinks) expect="WARNING: Could not fully replay symlinks from the manifest." ;;
            claudesymlinks) expect="WARNING: Could not fully replay Claude state symlinks." ;;
            space) expect="WARNING: Could not check the free space inside Docker before the restore." ;;
            tmprm) expect="WARNING: Could not remove the temporary copy of your data (Docker volume(s): daaf_daaf-data-restore-tmp daaf_daaf-claude-config-restore-tmp)." ;;
        esac
        export BANNER_FAIL="${step}"
        _mock_banner_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
        assert_success
        assert_output --partial "${expect}"
        assert_output --partial "Restore completed WITH WARNINGS -- verify before relying on it"
        refute_output --partial "Restore complete!"
        # The verified data-volume count and the next steps still print.
        assert_output --partial "Files:    1 files in volume"
        assert_output --partial "You can now start DAAF with:"
    done
}

# =========================================================================
# --- Copy-then-swap: every new branch (2026-10-01) ---
# =========================================================================
# The backup is copied into TEMPORARY volumes, checked, confirmed (RESTORE), and only
# then swapped into the live volumes inside Docker. Each case below drives one branch
# with _mock_restore_docker and asserts the user-visible outcome, the exit code, what
# happened to the temp volumes, and (before any swap) that the LIVE volumes were never
# written (_assert_no_live_write). Answers are piped; DAAF_NESTED=1 suppresses the pause.

_RESTORE_SH_REL="scripts/host/restore_from_backup.sh"

@test "copy-then-swap SELF-TEST: the live-write guard flags every live write and passes temp-only work" {
    printf '%s\n' \
        'volume create --label org.daaf.restore-tmp-for=daaf_daaf-data daaf_daaf-data-restore-tmp' \
        'create --label org.daaf.restore-tmp-for=daaf_daaf-data -v daaf_daaf-data-restore-tmp:/dest busybox' \
        'run --rm -v daaf_daaf-data:/dest:ro busybox sh -c a=1' \
        'run --rm -v daaf_daaf-data:/dest:ro -v daaf_daaf-data-restore-tmp:/src:ro busybox sh -c a=1' \
        'volume rm daaf_daaf-data-restore-tmp' > "${TEST_DIR}/clean.log"
    run _live_writes "${TEST_DIR}/clean.log"
    assert_output ""
    local bad
    for bad in 'volume rm daaf_daaf-data' 'volume create daaf_daaf-data' \
        'run --rm -v daaf_daaf-data:/dest busybox rm -rf /dest/x' \
        'create -v daaf_daaf-claude-config:/dest busybox' \
        'run --rm -v daaf_daaf-data-restore-tmp:/src:ro -v daaf_daaf-data:/dest busybox sh -c x' \
        'run --rm --sig-proxy=false --name daaf_daaf-data-restore-swap busybox sh -c x'; do
        printf '%s\n' "${bad}" > "${TEST_DIR}/bad.log"
        run _live_writes "${TEST_DIR}/bad.log"
        assert_output --partial "${bad}"
    done
}

@test "copy-then-swap: a clean run swaps both volumes, removes both temps, leaks no helper" {
    _make_full_backup
    export DAAF_NESTED=1
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "  Restore complete!"
    assert_output --partial "Claude Code state prepared."
    assert_output --partial "Claude Code state restored."
    run grep -c -- '--sig-proxy=false --name daaf_daaf-data-restore-swap -v daaf_daaf-data-restore-tmp:/src:ro -v daaf_daaf-data:/dest ' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    run grep -c -- '--sig-proxy=false --name daaf_daaf-claude-config-restore-swap -v daaf_daaf-claude-config-restore-tmp:/src:ro -v daaf_daaf-claude-config:/dest ' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    # The state marker went into both temps before the swaps; both temps removed after.
    run grep -c 'touch /dest/.daaf-restore-swap-started' "${TEST_DIR}/docker_calls.log"
    assert_output "2"
    run grep -cxE 'volume rm daaf_daaf-(data|claude-config)-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "2"
    run cat "${TEST_DIR}/helpers"
    assert_output ""
}

@test "copy-then-swap: temp volume create fails -> ERROR, exit 1, nothing changed, nothing to remove" {
    _make_backup
    export DAAF_NESTED=1 RM_FAIL=tmpcreate
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "ERROR: Could not create a temporary Docker volume ('daaf_daaf-data-restore-tmp') for the restore."
    assert_output --partial "Your DAAF data has not been changed."
    refute_output --partial "DESTRUCTIVE OPERATION"
    refute_output --partial "The temporary copy could not be removed"
    run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    run grep -c '^create ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    _assert_no_live_write
}

@test "copy-then-swap: the copy into the temp volume fails -> exit 1, helper reaped, temp removed" {
    _make_backup
    export DAAF_NESTED=1 RM_FAIL=cp
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "Error: simulated copy failure"
    assert_output --partial "ERROR: Copying the backup into Docker failed (see the message above)."
    assert_output --partial "Your DAAF data has not been changed."
    refute_output --partial "DESTRUCTIVE OPERATION"
    run grep -cxF 'volume rm daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    run cat "${TEST_DIR}/helpers"
    assert_output ""
    _assert_no_live_write
}

@test "copy-then-swap: a temp count that differs from the backup (more, or 0) stops before the prompt" {
    _make_backup
    export DAAF_NESTED=1
    local n
    for n in 2 0; do
        export RM_TEMP_COUNT="${n}"
        _mock_restore_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        assert_failure 1
        assert_output --partial "ERROR: The temporary copy holds ${n} files, but the backup has 1,"
        assert_output --partial "so the copy into Docker is not complete."
        assert_output --partial "Your DAAF data has not been changed."
        refute_output --partial "DESTRUCTIVE OPERATION"
        run grep -cxF 'volume rm daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
        assert_output "1"
        _assert_no_live_write
    done
}

@test "copy-then-swap: a temp count that cannot be read (error marker or failed container) stops before the prompt" {
    _make_backup
    export DAAF_NESTED=1
    local m
    for m in errors fail; do
        export RM_TEMP_COUNT_MODE="${m}"
        _mock_restore_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        assert_failure 1
        assert_output --partial "ERROR: Could not count the files in the temporary copy (exit "
        assert_output --partial "cannot be checked against the backup."
        assert_output --partial "Your DAAF data has not been changed."
        refute_output --partial "DESTRUCTIVE OPERATION"
        _assert_no_live_write
    done
}

@test "copy-then-swap: every Claude-state preparation failure stops the restore (D2), both temps removed" {
    _make_full_backup
    export DAAF_NESTED=1
    local step expect
    for step in claudetmpcreate claudecp claudechown; do
        case "${step}" in
            claudetmpcreate) expect="from this backup: a temporary Docker volume could not be created." ;;
            *) expect="from this backup: copying it into Docker failed." ;;
        esac
        export RM_FAIL="${step}"
        _mock_restore_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        assert_failure 1
        assert_output --partial "ERROR: Could not prepare the Claude Code state (login and session history)"
        assert_output --partial "${expect}"
        assert_output --partial "Your DAAF data has not been changed."
        refute_output --partial "DESTRUCTIVE OPERATION"
        run grep -cxF 'volume rm daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
        assert_output "1"
        run cat "${TEST_DIR}/helpers"
        assert_output ""
        _assert_no_live_write
    done
    # claudetmpcreate never created the Claude temp, so it is not removed then; the
    # other two remove it (checked on the last iteration).
    run grep -cxF 'volume rm daaf_daaf-claude-config-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
}

@test "copy-then-swap: cancel at RESTORE removes both temps, leaves live untouched, exit 0" {
    _make_full_backup
    export DAAF_NESTED=1
    _mock_restore_docker
    run bash -c 'printf "1\nno\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "DESTRUCTIVE OPERATION"
    assert_output --partial "Restore cancelled. Your DAAF data has not been changed."
    refute_output --partial "The temporary copy could not be removed"
    run grep -cxE 'volume rm daaf_daaf-(data|claude-config)-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "2"
    run grep -c 'touch /dest/.daaf-restore-swap-started' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    _assert_no_live_write
}

@test "copy-then-swap: cancel at RESTORE whose temp removal fails prints the removal command, exit 0" {
    _make_backup
    export DAAF_NESTED=1 RM_FAIL=tmprm
    _mock_restore_docker
    run bash -c 'printf "1\nno\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    # Fix pass #18 (field test 2026-10-05, D1): the kept-temp block, with no reason line
    # when Docker gave none, and the hint for a volume Docker says is in use.
    assert_output --partial "$(printf '%s\n' \
        'Restore cancelled. Your DAAF data has not been changed.' \
        'The temporary copy could not be removed.' \
        'To free the space it uses, run:' \
        '  docker volume rm daaf_daaf-data-restore-tmp' \
        'If Docker says it is in use, first run' \
        '  docker ps -a --filter volume=daaf_daaf-data-restore-tmp' \
        'and remove each container it lists with docker rm <ID>, then try again.')"
    refute_output --partial "The temporary copy could not be removed. To free the space it uses, run:"
    refute_output --partial "Docker said:"
    _assert_no_live_write
}

@test "copy-then-swap: a container using the live data at swap time stops the restore before the swap" {
    _make_backup
    export DAAF_NESTED=1 RM_RUNNING_AT_SWAP="other-daaf-1"
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "ERROR: A container started using your DAAF data while the restore was being"
    assert_output --partial "prepared: other-daaf-1"
    assert_output --partial "Stop it (docker compose down) and run the restore again."
    assert_output --partial "Your DAAF data has not been changed."
    # Names from stdout only: the mock's stderr notice is never listed as a container.
    refute_output --partial "fake-docker-ps-stderr-notice"
    run grep -cxF 'volume rm daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    _assert_no_live_write
}

@test "copy-then-swap: a docker ps that FAILS at swap time refuses (could not check), both temps removed, live untouched" {
    # Before 2026-10-01 a failing re-check (`2>/dev/null || true`) read as "nothing is
    # running" and the swap went ahead. Now: refuse before the marker and the swap.
    _make_full_backup
    export DAAF_NESTED=1 RM_FAIL=psswap
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "ERROR: Could not check whether DAAF is running (docker ps failed, exit 1),"
    assert_output --partial "       so your data cannot be replaced safely. Make sure Docker Desktop is running,"
    assert_output --partial "       then run the restore again."
    assert_output --partial "Your DAAF data has not been changed."
    refute_output --partial "A container started using your DAAF data"
    refute_output --partial "Cannot connect to the Docker daemon"
    refute_output --partial "Replacing your DAAF data with the checked copy"
    run grep -cxE 'volume rm daaf_daaf-(data|claude-config)-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "2"
    run grep -c 'touch /dest/.daaf-restore-swap-started' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    _assert_no_live_write
}

@test "startup: a docker ps that FAILS refuses (could not check), exit 1, before anything is created" {
    # Until 2026-10-02 the startup check was `2>/dev/null || true`: a failing docker ps
    # read as "nothing is running" and the restore went on.
    _make_backup
    export DAAF_NESTED=1 RM_FAIL=psstart
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "ERROR: Could not check whether DAAF is running (docker ps failed, exit 125),"
    assert_output --partial "       so the restore cannot start safely. This restore has not changed anything."
    assert_output --partial "       Make sure Docker Desktop is running, then run the restore again."
    refute_output --partial "Cannot connect to the Docker daemon"
    refute_output --partial "currently running"
    refute_output --partial "Available backups"
    run grep -c -E '^(volume create|create|run) ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    _assert_no_live_write
}

@test "startup: a docker ps stderr line with exit 0 is not a running container (the restore goes on)" {
    _make_backup
    export DAAF_NESTED=1 RM_PS_START_STDERR=1
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    refute_output --partial "currently running"
    refute_output --partial "simulated docker config notice"
    refute_output --partial "Could not check whether DAAF is running"
    assert_output --partial "Restore complete!"
}

@test "copy-then-swap: the state-marker write fails -> exit 1 before any swap, temps removed" {
    _make_backup
    export DAAF_NESTED=1 RM_FAIL=marker
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "ERROR: Could not prepare the temporary copy for the final step."
    assert_output --partial "Your DAAF data has not been changed."
    run grep -cxF 'volume rm daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    _assert_no_live_write
}

@test "copy-then-swap: a swap check that mismatches or cannot be read keeps the temp copy, exit 1" {
    _make_backup
    export DAAF_NESTED=1
    local m
    for m in MISMATCH ERRORS NONE; do
        export RM_SWAP_VERIFY="${m}"
        _mock_restore_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        assert_failure 1
        assert_output --partial "ERROR: After replacing your DAAF data, it could not be confirmed to match the"
        assert_output --partial "checked copy (file names, sizes, permissions and owners)."
        assert_output --partial "kept in Docker (volume(s): daaf_daaf-data-restore-tmp), and your backup"
        refute_output --partial "Restore complete"
        run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
        assert_output "0"
    done
}

@test "copy-then-swap: the Claude swap failing (or not checking out) keeps BOTH temps, exit 1" {
    _make_full_backup
    export DAAF_NESTED=1
    local m
    for m in swap verify; do
        unset RM_FAIL RM_CLAUDE_SWAP_VERIFY
        if [ "${m}" = swap ]; then export RM_FAIL=claudeswap; else export RM_CLAUDE_SWAP_VERIFY=MISMATCH; fi
        _mock_restore_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        assert_failure 1
        # Review round 2 (S5): plain language -- the project files are in place, only the
        # login and history are not. Review round 3 (S-a): the Claude swap ran in both
        # cases, so the old login may be gone too.
        assert_output --partial "Your project files (DAAF data) were restored and checked. Only the Claude Code"
        assert_output --partial "Your previous Claude Code login may also be gone now; running the restore again"
        refute_output --partial "Your data volume was already replaced."
        refute_output --partial "Your DAAF data may now be incomplete."
        assert_output --partial "kept in Docker (volume(s): daaf_daaf-data-restore-tmp daaf_daaf-claude-config-restore-tmp), and your backup"
        if [ "${m}" = swap ]; then
            assert_output --partial "ERROR: Replacing the Claude Code state (login and session history) did not"
        else
            assert_output --partial "ERROR: After replacing the Claude Code state, it could not be confirmed to match"
        fi
        run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
        assert_output "0"
    done
}

@test "copy-then-swap: a failed temp removal after a verified restore is a latched WARNING, exit 0" {
    _make_backup
    export DAAF_NESTED=1 RM_FAIL=tmprm
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    # Fix pass #18: no reason line (Docker printed nothing), then the hint lines.
    assert_output --partial "$(printf '%s\n' \
        'WARNING: Could not remove the temporary copy of your data (Docker volume(s): daaf_daaf-data-restore-tmp).' \
        '         Your DAAF data was restored. To free the space it uses, run:' \
        '           docker volume rm daaf_daaf-data-restore-tmp' \
        '         If Docker says it is in use, first run' \
        '           docker ps -a --filter volume=daaf_daaf-data-restore-tmp' \
        '         and remove each container it lists with docker rm <ID>, then try again.')"
    assert_output --partial "Restore completed WITH WARNINGS -- verify before relying on it"
    refute_output --partial "Restore complete!"
}

@test "copy-then-swap: a leftover temp volume, answer y -> removed, then the restore runs to the end" {
    _make_backup
    export DAAF_NESTED=1 RM_LEFTOVER="daaf_daaf-data-restore-tmp"
    _mock_restore_docker
    run bash -c 'printf "1\ny\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "A temporary copy left behind by an earlier restore that did not finish was found:"
    assert_output --partial "  - Docker volume 'daaf_daaf-data-restore-tmp'"
    assert_output --partial "That earlier restore stopped before it replaced anything, so your current"
    assert_output --partial "DAAF data was not changed by it."
    assert_output --partial "Your backup folders are not affected, so this temporary copy is not needed."
    assert_output --partial "Removed the leftover temporary copy."
    assert_output --partial "  Restore complete!"
    # Removed once as a leftover (before the new create) and once at the end.
    run grep -nxE '(volume rm|volume create --label org.daaf.restore-tmp-for=daaf_daaf-data --label org.daaf.restore-run=[0-9]+-[0-9]+-[0-9]+) daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
    [ "${#lines[@]}" -eq 3 ]
    [ "${lines[0]#*:}" = "volume rm daaf_daaf-data-restore-tmp" ]
    [[ "${lines[1]#*:}" == "volume create --label org.daaf.restore-tmp-for=daaf_daaf-data --label org.daaf.restore-run="* ]]
    [ "${lines[2]#*:}" = "volume rm daaf_daaf-data-restore-tmp" ]
}

@test "copy-then-swap: a leftover temp volume, answer n -> cancelled, exit 0, removal command shown, nothing created" {
    _make_backup
    export DAAF_NESTED=1 RM_LEFTOVER="daaf_daaf-data-restore-tmp daaf_daaf-claude-config-restore-tmp"
    _mock_restore_docker
    run bash -c 'printf "1\nn\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "  - Docker volume 'daaf_daaf-claude-config-restore-tmp'"
    assert_output --partial "Restore cancelled. Your DAAF data has not been changed."
    assert_output --partial "To remove the temporary copy later, run:"
    assert_output --partial "  docker volume rm daaf_daaf-data-restore-tmp daaf_daaf-claude-config-restore-tmp"
    run grep -cE '^(volume create|volume rm|create|cp) ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    _assert_no_live_write
}

@test "copy-then-swap: a leftover that cannot be removed -> ERROR with the commands, exit 1, nothing created" {
    _make_backup
    export DAAF_NESTED=1 RM_LEFTOVER="daaf_daaf-data-restore-tmp" RM_FAIL=leftoverrm
    _mock_restore_docker
    run bash -c 'printf "1\ny\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "ERROR: Could not remove the temporary copy left by the earlier restore."
    assert_output --partial "       Your DAAF data has not been changed."
    assert_output --partial "       Make sure no other restore is running (and Docker Desktop is running), then"
    assert_output --partial "         docker volume rm daaf_daaf-data-restore-tmp"
    # S3's next step for a removal that keeps failing is now the holder hint (fix pass
    # #18, D1); the old "restart Docker Desktop" line is gone from this message. (A
    # never-started holder does not go away on its own while Docker keeps running; a
    # Docker restart is expected to remove it -- moby restore(), inference -- but the
    # restore now removes such holders itself.)
    assert_output --partial "$(printf '%s\n' \
        '       If Docker says it is in use, first run' \
        '         docker ps -a --filter volume=daaf_daaf-data-restore-tmp' \
        '       and remove each container it lists with docker rm <ID>, then try again.')"
    refute_output --partial "restart Docker Desktop"
    # Docker printed nothing, so there is no "Docker said:" line.
    refute_output --partial "Docker said:"
    refute_output --partial "Removed the leftover temporary copy."
    run grep -cE '^(volume create|create|cp) ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    _assert_no_live_write
}

@test "copy-then-swap: the leftover message says whether the earlier restore had started replacing data" {
    _make_backup
    export DAAF_NESTED=1
    local m
    for m in yes err stopped; do
        unset RM_LEFTOVER RM_LEFTOVER_MARKER RM_SWAP_CONTAINER
        case "${m}" in
            yes|err) export RM_LEFTOVER="daaf_daaf-data-restore-tmp" RM_LEFTOVER_MARKER="${m}" ;;
            stopped) export RM_SWAP_CONTAINER=stopped ;;
        esac
        _mock_restore_docker
        run bash -c 'printf "1\nn\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        assert_success
        refute_output --partial "That earlier restore stopped before it replaced anything"
        case "${m}" in
            err)
                assert_output --partial "It could not be checked whether that earlier restore had started replacing"
                assert_output --partial "your DAAF data, so your current DAAF data may be incomplete. Continuing redoes"
                ;;
            *)
                assert_output --partial "That earlier restore had started replacing your DAAF data, so your current"
                assert_output --partial "DAAF data may be incomplete. Continuing redoes the restore from the backup"
                ;;
        esac
    done
    # The stopped swap container is listed and its removal command is shown.
    assert_output --partial "  - Docker container 'daaf_daaf-data-restore-swap' (stopped)"
    assert_output --partial "  docker rm daaf_daaf-data-restore-swap"
}

@test "copy-then-swap: a stopped leftover swap container is removed on y (a PLAIN rm by its exact name, never -f)" {
    _make_backup
    export DAAF_NESTED=1 RM_SWAP_CONTAINER=stopped
    _mock_restore_docker
    run bash -c 'printf "1\ny\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "Removed the leftover temporary copy."
    run grep -cxF 'rm daaf_daaf-data-restore-swap' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    # Review round 6 (R5): never forced -- a swap started meanwhile under the same name
    # must survive (see the R5 test below).
    run grep -cE '^rm (-f|--force) .*-restore-swap$' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
}

@test "R5: a leftover swap container that became RUNNING after the prompt is NOT removed (plain rm refused); the run refuses, exit 1, no volume touched" {
    # Stopped at the check, before the y/n prompt; running by the time the leftover path
    # removes it (another window's restore started its swap under the same name). The
    # daemon refuses a plain rm of a running container, so it survives; the restore stops
    # with Docker's reason and touches no leftover volume.
    _make_backup
    export DAAF_NESTED=1 RM_SWAP_CONTAINER=stopped RM_LEFTOVER="daaf_daaf-data-restore-tmp" \
        RM_SWAP_RUNNING_AT_RM="daaf_daaf-data-restore-swap"
    _mock_restore_docker
    run bash -c 'printf "1\ny\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "$(printf '%s\n' \
        '' \
        'ERROR: Could not remove the temporary copy left by the earlier restore.' \
        '       Docker said: Error response from daemon: cannot remove container "/daaf_daaf-data-restore-swap": container is running: stop the container before removing or force remove' \
        '       This restore did not change anything, but your DAAF data may still be' \
        '       incomplete from the earlier restore. Run the restore again to finish it.' \
        '       Make sure no other restore is running (and Docker Desktop is running), then' \
        '       run this restore again, or remove it yourself with:' \
        '         docker rm daaf_daaf-data-restore-swap' \
        '         docker volume rm daaf_daaf-data-restore-tmp' \
        '       If Docker says it is in use, first run' \
        '         docker ps -a --filter volume=daaf_daaf-data-restore-tmp' \
        '       and remove each container it lists with docker rm <ID>, then try again.')"
    refute_output --partial "docker rm -f"
    refute_output --partial "Removed the leftover temporary copy."
    # One plain rm attempt, never a forced one.
    run grep -cxF 'rm daaf_daaf-data-restore-swap' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    run grep -cE '^rm (-f|--force) .*-restore-swap$' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    # The leftover volume is left alone: only the check pass listed its holders, and no
    # volume was removed or created.
    run grep -cxF 'ps -a --filter volume=daaf_daaf-data-restore-tmp --format {{.ID}} {{.State}}' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    run grep -cE '^(volume rm|volume create|create|cp) ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    _assert_no_live_write
}

@test "R8: a leftover swap container that VANISHED before its removal (plain rm: No such container) counts as removed; the leftover volume is removed and the restore continues" {
    # Delta review of round 7 (ISSUE 1): its --rm finished, Docker restarted, or another
    # window removed it while the y/n prompt waited. docker CLI rm.go ignores not-found
    # only for -f, so the plain rm exits 1 -- read as success, not as a failure.
    _make_backup
    export DAAF_NESTED=1 RM_SWAP_CONTAINER=stopped RM_LEFTOVER="daaf_daaf-data-restore-tmp" \
        RM_SWAP_GONE_AT_RM="daaf_daaf-data-restore-swap"
    _mock_restore_docker
    run bash -c 'printf "1\ny\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "Removed the leftover temporary copy."
    refute_output --partial "ERROR: Could not remove the temporary copy left by the earlier restore."
    refute_output --partial "No such container"
    assert_output --partial "  Restore complete!"
    # One plain rm attempt, never a forced one; the leftover volume was removed (before
    # the new temp was created).
    run grep -cxF 'rm daaf_daaf-data-restore-swap' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    run grep -cE '^rm (-f|--force) .*-restore-swap$' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    local rmv crt
    rmv="$(grep -nxF 'volume rm daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log" | head -n 1 | cut -d: -f1)"
    crt="$(grep -nE '^volume create .*daaf_daaf-data-restore-tmp$' "${TEST_DIR}/docker_calls.log" | head -n 1 | cut -d: -f1)"
    [ -n "${rmv}" ] && [ -n "${crt}" ] && [ "${rmv}" -lt "${crt}" ]
}

@test "R8: a leftover swap container whose removal is ALREADY IN PROGRESS refuses (exit 1) with Docker's reason; no volume touched" {
    _make_backup
    export DAAF_NESTED=1 RM_SWAP_CONTAINER=stopped RM_LEFTOVER="daaf_daaf-data-restore-tmp" \
        RM_SWAP_REMOVING_AT_RM="daaf_daaf-data-restore-swap"
    _mock_restore_docker
    run bash -c 'printf "1\ny\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "$(printf '%s\n' \
        '' \
        'ERROR: Could not remove the temporary copy left by the earlier restore.' \
        '       Docker said: Error response from daemon: removal of container daaf_daaf-data-restore-swap is already in progress' \
        '       This restore did not change anything, but your DAAF data may still be' \
        '       incomplete from the earlier restore. Run the restore again to finish it.')"
    refute_output --partial "Removed the leftover temporary copy."
    run grep -cxF 'rm daaf_daaf-data-restore-swap' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    run grep -cE '^(volume rm|volume create|create|cp) ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    _assert_no_live_write
}

@test "copy-then-swap: a RUNNING leftover swap container refuses (exit 1) before anything is created" {
    _make_backup
    export DAAF_NESTED=1 RM_CLAUDE_SWAP_CONTAINER=running
    _mock_restore_docker
    run bash -c 'printf "1\ny\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "ERROR: An earlier restore is still replacing your DAAF data inside Docker"
    assert_output --partial "(Docker container 'daaf_daaf-claude-config-restore-swap' is running). Wait a few minutes for it to"
    assert_output --partial "finish, then run this restore again. This restore has not changed anything."
    run grep -cE '^(volume create|volume rm|create|cp|rm) ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    _assert_no_live_write
}

@test "copy-then-swap: a similarly named volume is NOT a leftover (exact-name check, never a filter regex)" {
    _make_backup
    export DAAF_NESTED=1 RM_VOLUMES="daaf_daaf-data-restore-tmp-old x-daaf_daaf-data-restore-tmp"
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    refute_output --partial "A temporary copy left behind by an earlier restore"
    assert_output --partial "  Restore complete!"
    run grep -cxF 'volume inspect daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    run grep -c '^volume ls' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
}

@test "copy-then-swap: insufficient free space refuses before ANY volume is created" {
    _make_backup
    export DAAF_NESTED=1 RM_AVAIL_KB=0
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "ERROR: There is not enough free space inside Docker for this restore."
    assert_output --partial "The restore needs about 1.0 GB free inside Docker (it makes a temporary"
    assert_output --partial "0.0 GB free. Free up space for Docker (for example, delete unused"
    assert_output --partial "data), then run the restore again."
    assert_output --partial "       Your DAAF data has not been changed."
    run grep -cE '^(volume create|create|cp) ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    _assert_no_live_write
}

@test "copy-then-swap: the first space check refuses below max(B, 2B - L) + 1 GiB and passes at it" {
    # B = the scan's data KB (du -sk of the backup, which here has no manifests and no
    # Claude subfolder), computed the same way; L = 0, so the peak is 2B.
    _make_backup
    head -c 20000 /dev/zero > "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    local b_kb need
    b_kb="$(du -sk "${TEST_DIR}/2026-01-01_daaf_backup" | awk '{print $1}')"
    [ "${b_kb}" -gt 0 ]
    need=$(( 2 * b_kb + 1048576 ))
    # RM_SRC_KB=0 keeps the later swap re-check (F + L >= S + margin) out of the way.
    export DAAF_NESTED=1 RM_LIVE_KB=0 RM_SRC_KB=0 RM_AVAIL_KB=$(( need - 1 ))
    _mock_restore_docker
    run bash -c 'printf "1\nno\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "ERROR: There is not enough free space inside Docker for this restore."
    export RM_AVAIL_KB="${need}"
    _mock_restore_docker
    run bash -c 'printf "1\nno\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    refute_output --partial "not enough free space"
    assert_output --partial "Restore cancelled. Your DAAF data has not been changed."
}

@test "copy-then-swap: the swap space re-check refuses when F + L < S + 1 GiB and passes at equality" {
    _make_backup
    export DAAF_NESTED=1 RM_LIVE_KB=1000 RM_SRC_KB=5000000 RM_SWAP_AVAIL_KB=$(( 5000000 + 1048576 - 1000 - 1 ))
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "ERROR: There is not enough free space inside Docker to replace your data with the"
    assert_output --partial "checked copy: it needs about 5.8 GB free, Docker has 5.8 GB."
    assert_output --partial "Your DAAF data has not been changed."
    refute_output --partial "DESTRUCTIVE OPERATION"
    run grep -cxF 'volume rm daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    _assert_no_live_write
    export RM_SWAP_AVAIL_KB=$(( 5000000 + 1048576 - 1000 ))
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "  Restore complete!"
}

@test "copy-then-swap: unmeasurable free space is a latched WARNING; the restore continues with a Note at the prompt" {
    _make_backup
    export DAAF_NESTED=1 RM_SPACE_FAIL=1
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "WARNING: Could not check the free space inside Docker before the restore."
    assert_output --partial "The restore needs up to about 1.0 GB free inside Docker. If it"
    assert_output --partial "runs out while preparing, it stops without changing your DAAF data."
    assert_output --partial "Note: The free space inside Docker could not be checked. Replacing your data"
    assert_output --partial "kept so you can run the restore again."
    assert_output --partial "Restore completed WITH WARNINGS -- verify before relying on it"
}

@test "copy-then-swap: Ctrl+C while preparing removes the temp copy, exit 130" {
    # The mock sends SIGINT to the restore script itself ($$) from inside `docker cp`,
    # i.e. mid-preparation. (That the EXIT handler -- and its pause -- still runs after
    # the INT handler is checked under a real pty in the "pause prompt" test below.)
    _make_backup
    export DAAF_NESTED=1 RM_INTERRUPT_AT=cp
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 130
    assert_output --partial "Restore interrupted. Your DAAF data has not been changed."
    refute_output --partial "DESTRUCTIVE OPERATION"
    # The EXIT handler does not clean up a second time (the INT handler already did).
    refute_output --partial "The restore stopped before replacing anything"
    run grep -cxF 'volume rm daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    run cat "${TEST_DIR}/helpers"
    assert_output ""
    _assert_no_live_write
}

@test "copy-then-swap: Ctrl+C during the swap NEVER removes the temp copy (it may be the only complete one)" {
    _make_backup
    export DAAF_NESTED=1 RM_INTERRUPT_AT=swap
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 130
    assert_output --partial "Restore interrupted while your DAAF data was being replaced."
    assert_output --partial "The replacement keeps running inside Docker until it finishes. Your backup"
    assert_output --partial "  bash restore_from_backup.sh"
    run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    run grep -c '^ps -aq ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
}

@test "copy-then-swap: the EXIT handler keeps the pause prompt -- it still runs after a Ctrl+C (real pty)" {
    # The pause only arms on a terminal (`-c /dev/tty` and `-t 1`) outside CI and
    # DAAF_NESTED, so run the script under `script` (util-linux) for a pty. The third
    # answer line is the Enter the pause waits for.
    command -v script > /dev/null || skip "script (util-linux) not installed"
    _make_backup
    export RM_INTERRUPT_AT=cp
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n\n" | env -u CI -u DAAF_NESTED SHELL=/bin/bash script -qec "bash \"'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'\"" /dev/null'
    assert_output --partial "Restore interrupted. Your DAAF data has not been changed."
    assert_output --partial "Press Enter to continue"
    run grep -cxF 'volume rm daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
}

@test "copy-then-swap: one EXIT handler from the copy-then-swap section on; the interrupt handler resets INT/TERM only" {
    # Seven trap lines in all: the top pause (EXIT, until the copy-then-swap section),
    # the INT/TERM handler, the EXIT handler that replaces the top pause (cleanup before
    # a swap + the same pause), two resets of INT/TERM only (inside the handler, and
    # after the final cleanup), and two inside the EXIT handler: review round 3 (S-b) --
    # its first act after saving the status IGNORES INT/TERM, so a Ctrl+C cannot abort
    # its cleanup; review round 2 (I-B) -- right before the pause it re-arms INT/TERM to
    # exit with that saved status, so a Ctrl+C at the pause neither runs the interrupt
    # handler nor turns the code into 130. Nothing ever resets EXIT.
    run grep -cE "^[[:space:]]*trap " "${REPO_ROOT}/${_RESTORE_SH_REL}"
    assert_output "7"
    run grep -cE "^[[:space:]]*trap .* EXIT\$" "${REPO_ROOT}/${_RESTORE_SH_REL}"
    assert_output "2"
    run grep -cxF "trap _restore_on_exit EXIT" "${REPO_ROOT}/${_RESTORE_SH_REL}"
    assert_output "1"
    run grep -cxF "trap _restore_on_interrupt INT TERM" "${REPO_ROOT}/${_RESTORE_SH_REL}"
    assert_output "1"
    run grep -cxE "[[:space:]]*trap - INT TERM" "${REPO_ROOT}/${_RESTORE_SH_REL}"
    assert_output "2"
    run grep -cxE "[[:space:]]*trap 'exit \"\\$\\{RESTORE_EXIT_STATUS\\}\"' INT TERM" "${REPO_ROOT}/${_RESTORE_SH_REL}"
    assert_output "1"
    run grep -cxF "    trap '' INT TERM" "${REPO_ROOT}/${_RESTORE_SH_REL}"
    assert_output "1"
    # The ignore is the handler's line right after the status is saved (S-b)...
    run bash -c "grep -A 1 -xE '[[:space:]]*RESTORE_EXIT_STATUS=\\\$\\?' '${REPO_ROOT}/${_RESTORE_SH_REL}' | tail -n 1"
    assert_output "    trap '' INT TERM"
    # ...and the re-arm is the line right before the pause (I-B).
    run bash -c "grep -B 1 -xF '    if [ \"\${RESTORE_PAUSE_ON_EXIT}\" -eq 1 ]; then' '${REPO_ROOT}/${_RESTORE_SH_REL}' | head -n 1"
    assert_output "    trap 'exit \"\${RESTORE_EXIT_STATUS}\"' INT TERM"
    run grep -cE "trap - .*EXIT" "${REPO_ROOT}/${_RESTORE_SH_REL}"
    assert_output "0"
}

@test "copy-then-swap: temp/swap names follow DAAF_DATA_VOLUME_NAME and DAAF_PROJECT_NAME (multi-instance)" {
    _make_full_backup
    _mock_restore_docker
    export DAAF_NESTED=1 DAAF_DATA_VOLUME_NAME=shared-data DAAF_PROJECT_NAME=proj
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    run grep -cxE 'volume create --label org.daaf.restore-tmp-for=shared-data --label org.daaf.restore-run=[0-9]+-[0-9]+-[0-9]+ shared-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    run grep -cxE 'volume create --label org.daaf.restore-tmp-for=proj_daaf-claude-config --label org.daaf.restore-run=[0-9]+-[0-9]+-[0-9]+ proj_daaf-claude-config-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    run grep -c -- '--name shared-data-restore-swap -v shared-data-restore-tmp:/src:ro -v shared-data:/dest ' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
}

@test "copy-then-swap: the dry run creates no temp volume, helper or swap (HSM5)" {
    _make_backup
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/${_RESTORE_SH_REL}"
    assert_success
    assert_output --partial "Restore dry-run complete!"
    refute_output --partial "[DRY-RUN] docker volume create"
    refute_output --partial "[DRY-RUN] docker create"
    refute_output --partial "[DRY-RUN] docker container"
    refute_output --partial "restore-tmp"
    refute_output --partial "restore-swap"
}

# =========================================================================
# --- Review round 1 fixes (dispatch #7, 2026-10-01) ---
# =========================================================================
# B1: the swap may only ever use the temp copy THIS run created and checked (identity
# label re-checked before the marker and before each swap; ENTRIES n:n, n > 0; exact
# post-swap count). I1: end of input is a cancel; any exit before a swap removes this
# run's temps. I2: an inspect failure is never "absent"; a fresh temp must be empty and
# ours. I3: "nothing changed" wording after an earlier swap had started. S2/S3/item 5.

@test "B1: a temp volume that VANISHED while the RESTORE prompt waited -> refuse, nothing removed, no marker, no swap" {
    _make_full_backup
    export DAAF_NESTED=1 RM_IDENTITY=vanished_after_create
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "ERROR: The temporary copy of the backup in Docker (volume 'daaf_daaf-data-restore-tmp') was changed by"
    assert_output --partial "       started in another window. It was not used, and nothing was removed."
    assert_output --partial "       Your DAAF data has not been changed."
    assert_output --partial "       Close any other restore window, then run this restore again."
    refute_output --partial "Replacing your DAAF data with the checked copy"
    run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    run grep -c 'touch /dest/.daaf-restore-swap-started' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    run grep -c '^ps -aq ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    _assert_no_live_write
}

@test "B1: a temp volume RECREATED by another run (different token) while the prompt waited -> refuse, nothing removed" {
    _make_backup
    export DAAF_NESTED=1 RM_IDENTITY=recreated_after_create
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "was changed by"
    assert_output --partial "It was not used, and nothing was removed."
    run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    _assert_no_live_write
}

@test "B1: a temp volume that vanished AFTER the marker write is re-checked right before the swap -> no swap" {
    _make_backup
    export DAAF_NESTED=1 RM_IDENTITY=vanished_after_marker
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "It was not used, and nothing was removed."
    run grep -c 'touch /dest/.daaf-restore-swap-started' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    _assert_no_live_write
}

@test "B1: the identity check runs before the marker write and again before each swap (call order)" {
    _make_full_backup
    export DAAF_NESTED=1
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    # data temp: after create, before the marker, before its swap = 3 checks.
    run grep -cxF 'volume inspect --format {{.Labels}} daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "3"
    run grep -cxF 'volume inspect --format {{.Labels}} daaf_daaf-claude-config-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "3"
    # The last data check comes after the marker write and before the data swap.
    run bash -c "grep -n -e 'volume inspect --format {{.Labels}} daaf_daaf-data-restore-tmp' -e 'touch /dest/.daaf-restore-swap-started' -e '--name daaf_daaf-data-restore-swap' '${TEST_DIR}/docker_calls.log' | tail -n 3 | cut -d: -f2-"
    [[ "${lines[0]}" == *"touch /dest/.daaf-restore-swap-started"* ]]
    [ "${lines[1]}" = "volume inspect --format {{.Labels}} daaf_daaf-data-restore-tmp" ]
    [[ "${lines[2]}" == *"--name daaf_daaf-data-restore-swap"* ]]
}

@test "B1: the Claude temp changed before the Claude swap -> after-swap failure, data temp kept, Claude temp not listed" {
    _make_full_backup
    export DAAF_NESTED=1 RM_CLAUDE_IDENTITY=vanished_after_marker
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "ERROR: The temporary copy of the Claude Code state (volume 'daaf_daaf-claude-config-restore-tmp')"
    assert_output --partial "window -- so it was not used."
    refute_output --partial "Your data volume was already replaced."
    assert_output --partial "Your project files (DAAF data) were restored and checked. Only the Claude Code"
    assert_output --partial "kept in Docker (volume(s): daaf_daaf-data-restore-tmp), and your backup"
    run grep -c -- '--name daaf_daaf-claude-config-restore-swap' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
}

@test "B1: a data-volume MATCH over two EMPTY trees (ENTRIES 0:0) or unequal/missing ENTRIES is rejected after the swap" {
    _make_backup
    export DAAF_NESTED=1
    local e
    for e in 0:0 3:2 none; do
        export RM_SWAP_VERIFY_ENTRIES="${e}"
        _mock_restore_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        assert_failure 1
        assert_output --partial "ERROR: After replacing your DAAF data, it could not be confirmed to match the"
        assert_output --partial "kept in Docker (volume(s): daaf_daaf-data-restore-tmp), and your backup"
        refute_output --partial "Restore complete"
    done
}

@test "B1: an EMPTY Claude volume (ENTRIES 0:0, a backup taken before any login) still restores" {
    _make_full_backup
    export DAAF_NESTED=1 RM_CLAUDE_SWAP_VERIFY_ENTRIES=0:0
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "Claude Code state restored."
    assert_output --partial "  Restore complete!"
}

@test "I1: end of input at the RESTORE prompt is a cancel: exit 0, both temps removed, live untouched" {
    _make_full_backup
    export DAAF_NESTED=1
    _mock_restore_docker
    run bash -c 'printf "1\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "DESTRUCTIVE OPERATION"
    assert_output --partial "Restore cancelled. Your DAAF data has not been changed."
    run grep -cxE 'volume rm daaf_daaf-(data|claude-config)-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "2"
    _assert_no_live_write
}

@test "I1: end of input at the leftover prompt is a no: exit 0, nothing created or removed" {
    _make_backup
    export DAAF_NESTED=1 RM_LEFTOVER="daaf_daaf-data-restore-tmp"
    _mock_restore_docker
    run bash -c 'printf "1\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "Restore cancelled. Your DAAF data has not been changed."
    assert_output --partial "  docker volume rm daaf_daaf-data-restore-tmp"
    run grep -cE '^(volume create|volume rm|create|cp) ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
}

@test "I1: an UNEXPECTED exit while preparing (not a handled path) still removes this run's temps" {
    # RM_FAIL=crash: the permission-replay call exits the script with status 7, the way
    # an unguarded command failing under `set -e` would. The EXIT handler cleans up.
    _make_full_backup
    export DAAF_NESTED=1 RM_FAIL=crash
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 7
    assert_output --partial "The restore stopped before replacing anything (see the message above)."
    assert_output --partial "Your DAAF data has not been changed."
    assert_output --partial "Its temporary copy was removed."
    run grep -cxF 'volume rm daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    _assert_no_live_write
}

@test "I2: a leftover inspect that FAILS (not 'no such ...') refuses: could not check, nothing created" {
    _make_backup
    export DAAF_NESTED=1
    local k
    for k in volume container; do
        export RM_INSPECT_FAIL="${k}"
        _mock_restore_docker
        run bash -c 'printf "1\ny\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        assert_failure 1
        assert_output --partial "ERROR: Could not check for a temporary copy left by an earlier restore (docker"
        assert_output --partial "       ${k} inspect failed: Cannot connect to the Docker daemon"
        assert_output --partial "This restore has not changed anything. Make sure Docker Desktop is running,"
        refute_output --partial "A temporary copy left behind by an earlier restore"
        run grep -cE '^(volume create|volume rm|create|cp|rm) ' "${TEST_DIR}/docker_calls.log"
        assert_output "0"
        _assert_no_live_write
    done
}

@test "I2: a NEW temp volume that is not empty (or cannot be checked) is refused and LEFT ALONE" {
    _make_backup
    export DAAF_NESTED=1
    local m
    for m in notempty checkfail; do
        unset RM_TEMP_NOT_EMPTY RM_FAIL
        if [ "${m}" = notempty ]; then export RM_TEMP_NOT_EMPTY=data; else export RM_FAIL=emptycheck; fi
        _mock_restore_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        assert_failure 1
        assert_output --partial "ERROR: Could not confirm that the new temporary Docker volume 'daaf_daaf-data-restore-tmp' is empty"
        assert_output --partial "and was created by this restore, so it was left as it is (it may belong to"
        assert_output --partial "Your DAAF data has not been changed."
        refute_output --partial "DESTRUCTIVE OPERATION"
        run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
        assert_output "0"
        run grep -c '^cp ' "${TEST_DIR}/docker_calls.log"
        assert_output "0"
        _assert_no_live_write
    done
}

@test "I2: a reused volume (create kept another run's labels) is refused right after create" {
    _make_backup
    export DAAF_NESTED=1 RM_IDENTITY=recreated
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "Could not confirm that the new temporary Docker volume 'daaf_daaf-data-restore-tmp' is empty"
    run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
}

@test "I2: a non-empty new CLAUDE temp is left alone; the data temp this run created is removed" {
    _make_full_backup
    export DAAF_NESTED=1 RM_TEMP_NOT_EMPTY=claude
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "new temporary Docker volume 'daaf_daaf-claude-config-restore-tmp' is empty"
    run grep -cxF 'volume rm daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    run grep -cxF 'volume rm daaf_daaf-claude-config-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    _assert_no_live_write
}

@test "I3: after a leftover whose swap HAD started, 'nothing changed' messages say the data may still be incomplete" {
    _make_backup
    export DAAF_NESTED=1 RM_LEFTOVER="daaf_daaf-data-restore-tmp" RM_LEFTOVER_MARKER=yes
    _mock_restore_docker
    # (a) answer n at the leftover prompt
    run bash -c 'printf "1\nn\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "Restore cancelled. This restore did not change anything, but your DAAF data may still be"
    assert_output --partial "incomplete from the earlier restore. Run the restore again to finish it."
    refute_output --partial "Your DAAF data has not been changed."
    # (b) answer y, then cancel at RESTORE
    _mock_restore_docker
    run bash -c 'printf "1\ny\nno\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "Restore cancelled. This restore did not change anything, but your DAAF data may still be"
    refute_output --partial "Your DAAF data has not been changed."
    # (c) answer y, then a refusal before the swap (ERROR-block indentation)
    export RM_FAIL=marker
    _mock_restore_docker
    run bash -c 'printf "1\ny\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "       This restore did not change anything, but your DAAF data may still be"
    assert_output --partial "       incomplete from the earlier restore. Run the restore again to finish it."
    refute_output --partial "Your DAAF data has not been changed."
}

@test "I3: a leftover whose swap could NOT be checked also gets the incomplete wording; a clean leftover does not" {
    _make_backup
    export DAAF_NESTED=1 RM_LEFTOVER="daaf_daaf-data-restore-tmp" RM_LEFTOVER_MARKER=err
    _mock_restore_docker
    run bash -c 'printf "1\nn\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "Restore cancelled. This restore did not change anything, but your DAAF data may still be"
    unset RM_LEFTOVER_MARKER
    _mock_restore_docker
    run bash -c 'printf "1\nn\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "Restore cancelled. Your DAAF data has not been changed."
    refute_output --partial "This restore did not change anything"
}

@test "item 5 + S3: the leftover prompt says to answer n while another restore window is open; refusals name a next step" {
    _make_backup
    export DAAF_NESTED=1 RM_LEFTOVER="daaf_daaf-data-restore-tmp"
    _mock_restore_docker
    run bash -c 'printf "1\nn\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "If another restore window is still open, answer n."
    unset RM_LEFTOVER
    export RM_SWAP_CONTAINER=running
    _mock_restore_docker
    run bash -c 'printf "1\ny\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "       If this keeps happening, restart Docker Desktop and try again."
}

@test "S2: after a verified restore, each temp's marker is deleted BEFORE its volume rm" {
    _make_full_backup
    export DAAF_NESTED=1
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    local t
    for t in daaf_daaf-data-restore-tmp daaf_daaf-claude-config-restore-tmp; do
        run bash -c "grep -n -e '-v ${t}:/dest ${BB_RE} rm -f /dest/.daaf-restore-swap-started' -e '^volume rm ${t}\$' '${TEST_DIR}/docker_calls.log' | cut -d: -f2-"
        [[ "${lines[0]}" == *"-v ${t}:/dest ${DAAF_BUSYBOX_PIN} rm -f /dest/.daaf-restore-swap-started"* ]]
        [ "${lines[1]}" = "volume rm ${t}" ]
    done
    # Not on a cancel (no marker was written then). assert_success + the cancel line make
    # sure the run reached the RESTORE prompt, so the zero below is not vacuous.
    _mock_restore_docker
    run bash -c 'printf "1\nno\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "Restore cancelled. Your DAAF data has not been changed."
    run grep -cxE 'volume rm daaf_daaf-(data|claude-config)-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "2"
    run grep -c 'rm -f /dest/.daaf-restore-swap-started' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
}

@test "consistency 7: a Ctrl+C AFTER both swaps finished does not claim the data is 'being replaced'" {
    _make_full_backup
    export DAAF_NESTED=1 RM_INTERRUPT_AT=count
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 130
    assert_output --partial "Restore interrupted after your DAAF data had been replaced and checked, while"
    assert_output --partial "(volume(s): daaf_daaf-data-restore-tmp daaf_daaf-claude-config-restore-tmp). To be sure everything is in place, run"
    refute_output --partial "while your DAAF data was being replaced"
    run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
}

# =========================================================================
# --- Review round 2 fixes (fix round 2, 2026-10-01) ---
# =========================================================================
# S1: a data swap that provably did not run (its own exit 3 -- review round 3, I-1: ONLY
# exit 3; Docker's 125 can follow a daemon restart mid-swap) is "nothing was replaced"
# with a careful cleanup; any other exit, 125 included, stays on the after-swap path. I-A: a running swap's state is read from stdout only.
# S3: unrecognised inspect error text falls back to the exact-name lists. SF2: a refusal
# about a temp that may be someone else's reaps no helpers. S2: a refusal after the
# marker write unmarks this run's other temps, removing nothing. S5: Claude failures
# after the data swap say the project files are in place. S7: end of input at the two
# early prompts. I-B: a Ctrl+C at the exit pause keeps the exit code (real pty).

# Every logged docker call AFTER the data swap call ($1 = log).
_calls_after_data_swap() {
    awk '/--sig-proxy=false --name daaf_daaf-data-restore-swap /{f=1; next} f' "$1"
}

@test "S1: a data swap that exits 3 (no marker in /src) -> NOTHING replaced, exit 1, careful cleanup (identity, unmark, rm; no reap)" {
    _make_full_backup
    export DAAF_NESTED=1 RM_SWAP_EXIT=3
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "ERROR: The temporary copy of the backup in Docker was gone or could not be used"
    assert_output --partial "       (exit 3), so NOTHING was replaced. Run the restore again."
    assert_output --partial "       Your DAAF data has not been changed."
    refute_output --partial "Your DAAF data may now be incomplete."
    refute_output --partial "Replacing your DAAF data did not complete"
    refute_output --partial "Replacing the Claude Code state..."
    refute_output --partial "The temporary copy could not be removed"
    # Careful: no label reap anywhere in the run (the only reap would be this cleanup).
    run grep -c '^ps -aq ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    # After the swap: each temp's identity is checked, then its marker is deleted, then
    # it is removed -- in that order, and nothing else (exit 3 needs no container probe).
    run _calls_after_data_swap "${TEST_DIR}/docker_calls.log"
    assert_output "$(printf '%s\n' \
        'volume inspect --format {{.Labels}} daaf_daaf-data-restore-tmp' \
        'volume inspect --format {{.Labels}} daaf_daaf-claude-config-restore-tmp' \
        "run --rm --label org.daaf.restore-tmp-for=daaf_daaf-data -v daaf_daaf-data-restore-tmp:/dest ${DAAF_BUSYBOX_PIN} rm -f /dest/.daaf-restore-swap-started" \
        'volume rm daaf_daaf-data-restore-tmp' \
        "run --rm --label org.daaf.restore-tmp-for=daaf_daaf-claude-config -v daaf_daaf-claude-config-restore-tmp:/dest ${DAAF_BUSYBOX_PIN} rm -f /dest/.daaf-restore-swap-started" \
        'volume rm daaf_daaf-claude-config-restore-tmp')"
}

@test "S1: exit 3 whose temp removal fails leaves a MARKER-FREE leftover and prints the removal command" {
    _make_backup
    export DAAF_NESTED=1 RM_SWAP_EXIT=3 RM_FAIL=tmprm
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "(exit 3), so NOTHING was replaced. Run the restore again."
    assert_output --partial "$(printf '%s\n' \
        '       The temporary copy could not be removed.' \
        '       To free the space it uses, run:' \
        '         docker volume rm daaf_daaf-data-restore-tmp' \
        '       If Docker says it is in use, first run' \
        '         docker ps -a --filter volume=daaf_daaf-data-restore-tmp' \
        '       and remove each container it lists with docker rm <ID>, then try again.')"
    refute_output --partial "Your DAAF data may now be incomplete."
    # The marker was deleted BEFORE the (failed) removal, so the next run reports this
    # leftover as a restore that "stopped before it replaced anything".
    run _calls_after_data_swap "${TEST_DIR}/docker_calls.log"
    assert_output "$(printf '%s\n' \
        'volume inspect --format {{.Labels}} daaf_daaf-data-restore-tmp' \
        "run --rm --label org.daaf.restore-tmp-for=daaf_daaf-data -v daaf_daaf-data-restore-tmp:/dest ${DAAF_BUSYBOX_PIN} rm -f /dest/.daaf-restore-swap-started" \
        'volume rm daaf_daaf-data-restore-tmp')"
}

@test "S1: exit 3 after the data temp VANISHED leaves that name alone (no unmark, no rm); the Claude temp is still removed" {
    _make_full_backup
    export DAAF_NESTED=1 RM_SWAP_EXIT=3 RM_IDENTITY=vanished_after_swap
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "(exit 3), so NOTHING was replaced. Run the restore again."
    refute_output --partial "The temporary copy could not be removed"
    run grep -cxF 'volume rm daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    run grep -c -- '-v daaf_daaf-data-restore-tmp:/dest [^ ]* rm -f /dest/.daaf-restore-swap-started' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    run grep -cxF 'volume rm daaf_daaf-claude-config-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    run grep -c '^ps -aq ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
}

@test "S1/I-1: exit 125 with the swap container GONE stays on the after-swap path: temps and marker kept, no container probe" {
    # Review round 3 (I-1): a daemon restart mid-swap can make `docker run` return 125
    # after the rm ran (moby PR #34999 / #46857), and the container is then gone too --
    # so a gone container is no proof that nothing was replaced.
    _make_full_backup
    export DAAF_NESTED=1 RM_SWAP_EXIT=125
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "ERROR: Replacing your DAAF data did not complete (exit 125)."
    assert_output --partial "       Your DAAF data may now be incomplete. The checked copy of the backup is"
    assert_output --partial "       kept in Docker (volume(s): daaf_daaf-data-restore-tmp daaf_daaf-claude-config-restore-tmp), and your backup"
    refute_output --partial "NOTHING was replaced"
    refute_output --partial "Your DAAF data has not been changed."
    refute_output --partial "Replacing the Claude Code state..."
    # Nothing after the swap: no container probe, no list, no unmark, no removal, no reap.
    run _calls_after_data_swap "${TEST_DIR}/docker_calls.log"
    assert_output ""
    run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    run grep -c -- ':/dest [^ ]* rm -f /dest/.daaf-restore-swap-started' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
}

@test "S1/I-1: exit 125 while the swap container STILL EXISTS (stopped or running) stays on the after-swap path, temp kept" {
    _make_backup
    export DAAF_NESTED=1 RM_SWAP_EXIT=125
    local s
    for s in stopped running; do
        export RM_SWAP_AFTER="${s}"
        _mock_restore_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        assert_failure 1
        assert_output --partial "ERROR: Replacing your DAAF data did not complete (exit 125)."
        assert_output --partial "Your DAAF data may now be incomplete. The checked copy of the backup is"
        assert_output --partial "kept in Docker (volume(s): daaf_daaf-data-restore-tmp), and your backup"
        refute_output --partial "NOTHING was replaced"
        run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
        assert_output "0"
        run grep -c -- ':/dest [^ ]* rm -f /dest/.daaf-restore-swap-started' "${TEST_DIR}/docker_calls.log"
        assert_output "0"
    done
}

@test "S1/I-1: exit 125 with an unrecognised inspect error or a failing list stays on the after-swap path; nothing is listed after the swap" {
    _make_backup
    export DAAF_NESTED=1 RM_SWAP_EXIT=125 RM_INSPECT_ODD=container
    local c
    for c in absent listed listfail; do
        unset RM_SWAP_AFTER RM_LIST_FAIL
        case "${c}" in
            listed) export RM_SWAP_AFTER=stopped ;;
            listfail) export RM_LIST_FAIL=container_after_swap ;;
        esac
        _mock_restore_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        assert_failure 1
        assert_output --partial "ERROR: Replacing your DAAF data did not complete (exit 125)."
        assert_output --partial "Your DAAF data may now be incomplete."
        refute_output --partial "NOTHING was replaced"
        run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
        assert_output "0"
        run grep -c -- ':/dest [^ ]* rm -f /dest/.daaf-restore-swap-started' "${TEST_DIR}/docker_calls.log"
        assert_output "0"
        # No container inspect or exact-name list once the swap ran.
        run _calls_after_data_swap "${TEST_DIR}/docker_calls.log"
        assert_output ""
    done
}

@test "S1: any other nonzero data-swap exit (1, 2, 125, 126, 137) stays on the after-swap path without probing the container" {
    _make_backup
    export DAAF_NESTED=1
    local e
    for e in 1 2 125 126 137; do
        export RM_SWAP_EXIT="${e}"
        _mock_restore_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        assert_failure 1
        assert_output --partial "ERROR: Replacing your DAAF data did not complete (exit ${e})."
        refute_output --partial "NOTHING was replaced"
        run _calls_after_data_swap "${TEST_DIR}/docker_calls.log"
        refute_output --partial "container inspect"
        run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
        assert_output "0"
    done
}

@test "I-A: a RUNNING swap whose inspect also prints a stderr line (first or last) is still refused as running" {
    _make_backup
    export DAAF_NESTED=1 RM_SWAP_CONTAINER=running
    local w
    for w in first last; do
        export RM_SWAP_STATE_STDERR="${w}"
        _mock_restore_docker
        run bash -c 'printf "1\ny\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        assert_failure 1
        assert_output --partial "ERROR: An earlier restore is still replacing your DAAF data inside Docker"
        assert_output --partial "(Docker container 'daaf_daaf-data-restore-swap' is running). Wait a few minutes for it to"
        refute_output --partial "(stopped)"
        refute_output --partial "WARNING: simulated daemon notice"
        run grep -cxF 'rm -f daaf_daaf-data-restore-swap' "${TEST_DIR}/docker_calls.log"
        assert_output "0"
        run grep -cE '^(volume create|volume rm|create|cp|rm) ' "${TEST_DIR}/docker_calls.log"
        assert_output "0"
        _assert_no_live_write
    done
}

@test "S3: a leftover VOLUME inspect with unrecognised error text -> the exact-name list decides (absent / listed / list fails)" {
    _make_backup
    export DAAF_NESTED=1 RM_INSPECT_ODD=volume
    # (a) absent from `volume ls -q` (near-miss names only): the restore runs to the end.
    export RM_VOLUMES="daaf_daaf-data-restore-tmp-old x-daaf_daaf-data-restore-tmp"
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "  Restore complete!"
    refute_output --partial "A temporary copy left behind by an earlier restore"
    run grep -cxF 'volume ls -q' "${TEST_DIR}/docker_calls.log"
    assert_output "2"
    # (b) listed: offered as a leftover (answer n).
    unset RM_VOLUMES
    export RM_LEFTOVER="daaf_daaf-data-restore-tmp"
    _mock_restore_docker
    run bash -c 'printf "1\nn\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "  - Docker volume 'daaf_daaf-data-restore-tmp'"
    assert_output --partial "Restore cancelled. Your DAAF data has not been changed."
    # (c) the list fails too: could not check -> refuse, nothing created.
    unset RM_LEFTOVER
    export RM_LIST_FAIL=volume
    _mock_restore_docker
    run bash -c 'printf "1\ny\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "ERROR: Could not check for a temporary copy left by an earlier restore (docker"
    assert_output --partial "       volume inspect failed: Error response from daemon: unexpected reply"
    run grep -cE '^(volume create|volume rm|create|cp|rm) ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    _assert_no_live_write
}

@test "S3: a leftover CONTAINER inspect with unrecognised error text -> the lists decide (absent / stopped / running / list fails)" {
    _make_backup
    export DAAF_NESTED=1 RM_INSPECT_ODD=container
    local c
    for c in absent stopped running allfail runfail; do
        unset RM_SWAP_CONTAINER RM_LIST_FAIL
        case "${c}" in
            stopped) export RM_SWAP_CONTAINER=stopped ;;
            running) export RM_SWAP_CONTAINER=running ;;
            allfail) export RM_LIST_FAIL=container ;;
            runfail) export RM_SWAP_CONTAINER=stopped RM_LIST_FAIL=running ;;
        esac
        _mock_restore_docker
        run bash -c 'printf "1\nn\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        case "${c}" in
            absent)
                # Near-miss names in the list do not count: no leftover; "n" at RESTORE.
                assert_success
                refute_output --partial "A temporary copy left behind by an earlier restore"
                assert_output --partial "Restore cancelled. Your DAAF data has not been changed."
                run grep -cxF 'ps --format {{.Names}}' "${TEST_DIR}/docker_calls.log"
                assert_output "0"
                ;;
            stopped)
                assert_success
                assert_output --partial "  - Docker container 'daaf_daaf-data-restore-swap' (stopped)"
                assert_output --partial "  docker rm daaf_daaf-data-restore-swap"
                ;;
            running)
                assert_failure 1
                assert_output --partial "(Docker container 'daaf_daaf-data-restore-swap' is running). Wait a few minutes for it to"
                ;;
            *)
                assert_failure 1
                assert_output --partial "ERROR: Could not check for a temporary copy left by an earlier restore (docker"
                assert_output --partial "       container inspect failed: Error response from daemon: unexpected reply"
                ;;
        esac
        run grep -cxF 'ps -a --format {{.Names}}' "${TEST_DIR}/docker_calls.log"
        [ "${output}" -ge 1 ]
        if [ "${c}" != absent ]; then
            run grep -cE '^(volume create|create|cp) ' "${TEST_DIR}/docker_calls.log"
            assert_output "0"
        fi
    done
}

@test "SF2: a new-temp refusal reaps NO helpers; the Claude-temp refusal removes the data temp only after an identity check" {
    _make_full_backup
    export DAAF_NESTED=1
    local m
    for m in data claude; do
        export RM_TEMP_NOT_EMPTY="${m}"
        _mock_restore_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        assert_failure 1
        assert_output --partial "Could not confirm that the new temporary Docker volume"
        run grep -c '^ps -aq ' "${TEST_DIR}/docker_calls.log"
        assert_output "0"
    done
    # Claude refusal: the data temp's identity check (its second) comes right before its removal.
    run bash -c "grep -n -e '^volume inspect --format {{.Labels}} daaf_daaf-data-restore-tmp\$' -e '^volume rm daaf_daaf-data-restore-tmp\$' '${TEST_DIR}/docker_calls.log' | cut -d: -f2-"
    assert_output "$(printf '%s\n' \
        'volume inspect --format {{.Labels}} daaf_daaf-data-restore-tmp' \
        'volume inspect --format {{.Labels}} daaf_daaf-data-restore-tmp' \
        'volume rm daaf_daaf-data-restore-tmp')"
    # ...and a data temp that is no longer this run's by then is left alone.
    export RM_IDENTITY=recreated_after_create
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    run grep -c '^ps -aq ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
}

@test "SF2: a stray stderr line during the new-temp emptiness check does not cause a refusal" {
    _make_full_backup
    export DAAF_NESTED=1 RM_EMPTYCHECK_STDERR=1
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "  Restore complete!"
    refute_output --partial "Could not confirm that the new temporary Docker volume"
    run grep -c 'find /dest -mindepth 1' "${TEST_DIR}/docker_calls.log"
    assert_output "2"
}

@test "S2: a refusal AFTER the marker write deletes the marker from this run's other temp and removes NOTHING" {
    _make_full_backup
    export DAAF_NESTED=1 RM_IDENTITY=vanished_after_marker
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "ERROR: The temporary copy of the backup in Docker (volume 'daaf_daaf-data-restore-tmp') was changed by"
    assert_output --partial "It was not used, and nothing was removed."
    run grep -c -- "-v daaf_daaf-claude-config-restore-tmp:/dest ${BB_RE} rm -f /dest/.daaf-restore-swap-started" "${TEST_DIR}/docker_calls.log"
    assert_output "1"
    # The changed (data) temp is not touched; nothing is removed or reaped; no swap.
    run grep -c -- '-v daaf_daaf-data-restore-tmp:/dest [^ ]* rm -f /dest/.daaf-restore-swap-started' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    run grep -c '^ps -aq ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    _assert_no_live_write
}

@test "S2: a refusal BEFORE the marker write unmarks nothing (no marker was written)" {
    _make_full_backup
    export DAAF_NESTED=1 RM_IDENTITY=vanished_after_create
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "It was not used, and nothing was removed."
    run grep -c 'rm -f /dest/.daaf-restore-swap-started' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
}

@test "MARKERS_WRITTEN: a failed marker write unmarks each temp BEFORE removing it" {
    _make_full_backup
    export DAAF_NESTED=1 RM_FAIL=marker
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "ERROR: Could not prepare the temporary copy for the final step."
    local t
    for t in daaf_daaf-data-restore-tmp daaf_daaf-claude-config-restore-tmp; do
        run bash -c "grep -e '-v ${t}:/dest ${BB_RE} rm -f /dest/.daaf-restore-swap-started' -e '^volume rm ${t}\$' '${TEST_DIR}/docker_calls.log'"
        assert_success
        [ "${#lines[@]}" -eq 2 ]
        [[ "${lines[0]}" == *"-v ${t}:/dest ${DAAF_BUSYBOX_PIN} rm -f /dest/.daaf-restore-swap-started" ]]
        [ "${lines[1]}" = "volume rm ${t}" ]
    done
    _assert_no_live_write
}

@test "S5: every Claude failure after the data swap says the project files are in place, only login/history are not" {
    _make_full_backup
    export DAAF_NESTED=1
    local m expect kept
    for m in identity swap verify; do
        unset RM_CLAUDE_IDENTITY RM_FAIL RM_CLAUDE_SWAP_VERIFY
        kept="daaf_daaf-data-restore-tmp daaf_daaf-claude-config-restore-tmp"
        case "${m}" in
            identity)
                export RM_CLAUDE_IDENTITY=vanished_after_marker
                expect="       window -- so it was not used."
                kept="daaf_daaf-data-restore-tmp"
                ;;
            swap)
                export RM_FAIL=claudeswap
                expect="       complete (exit 1)."
                ;;
            verify)
                export RM_CLAUDE_SWAP_VERIFY=MISMATCH
                expect="       the checked copy."
                ;;
        esac
        _mock_restore_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        assert_failure 1
        assert_output --partial "${expect}"
        assert_output --partial "       Your project files (DAAF data) were restored and checked. Only the Claude Code"
        assert_output --partial "       login and session history were not restored."
        assert_output --partial "       kept in Docker (volume(s): ${kept}), and your backup"
        assert_output --partial "       folder 2026-01-01_daaf_backup/ is unchanged. To finish, run this restore again"
        assert_output --partial "       It will offer to remove the leftover copy (answer y) and then redo the restore."
        refute_output --partial "Your DAAF data may now be incomplete."
        refute_output --partial "Your data volume was already replaced."
        refute_output --partial "Restore complete"
        run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
        assert_output "0"
    done
}

@test "S-a: once the Claude swap RAN (exit 1 / 125, or its check failed) the message says the old login may be gone; not when it refused (3) or was never run" {
    _make_full_backup
    export DAAF_NESTED=1
    local m ran ranblock oldline
    ranblock="$(printf '%s\n' \
        "       Your project files (DAAF data) were restored and checked. Only the Claude Code" \
        "       login and session history were not restored." \
        "       Your previous Claude Code login may also be gone now; running the restore again" \
        "       puts the backup's login and history back." \
        "       The checked copy of the backup is" \
        "       kept in Docker (volume(s): daaf_daaf-data-restore-tmp daaf_daaf-claude-config-restore-tmp), and your backup")"
    oldline="       login and session history were not restored. The checked copy of the backup is"
    for m in exit1 exit125 mismatch unreadable refused3 identity; do
        unset RM_CLAUDE_IDENTITY RM_CLAUDE_SWAP_EXIT RM_CLAUDE_SWAP_VERIFY
        ran=1
        case "${m}" in
            exit1) export RM_CLAUDE_SWAP_EXIT=1 ;;
            exit125) export RM_CLAUDE_SWAP_EXIT=125 ;;
            mismatch) export RM_CLAUDE_SWAP_VERIFY=MISMATCH ;;
            unreadable) export RM_CLAUDE_SWAP_VERIFY=NONE ;;
            refused3) export RM_CLAUDE_SWAP_EXIT=3; ran=0 ;;
            identity) export RM_CLAUDE_IDENTITY=vanished_after_marker; ran=0 ;;
        esac
        _mock_restore_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        echo "S-a case=${m} ran=${ran}"
        assert_failure 1
        assert_output --partial "       Your project files (DAAF data) were restored and checked. Only the Claude Code"
        if [ "${ran}" -eq 1 ]; then
            assert_output --partial "${ranblock}"
            refute_output --partial "${oldline}"
        else
            assert_output --partial "${oldline}"
            refute_output --partial "Your previous Claude Code login may also be gone now"
            refute_output --partial "puts the backup's login and history back."
        fi
        run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
        assert_output "0"
    done
}

@test "S7: end of input at the stop-the-container prompt is a no: exit 0, 'Restore cancelled', nothing stopped" {
    _make_backup
    export DAAF_NESTED=1 RM_RUNNING="daaf-daaf-docker-1"
    _mock_restore_docker
    run bash -c 'bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'" < /dev/null'
    assert_success
    assert_output --partial "The DAAF container is currently running:"
    assert_output --partial "Restore cancelled. Stop the container manually and try again:"
    assert_output --partial "  docker compose down"
    [ ! -f "${TEST_DIR}/composed_down" ]
    run grep -cE '^(volume create|volume rm|create|cp|compose) ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
}

@test "S7: end of input at the backup-number prompt is an invalid (empty) selection: exit 1 with the usual message" {
    _make_backup
    export DAAF_NESTED=1
    _mock_restore_docker
    run bash -c 'bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'" < /dev/null'
    assert_failure 1
    assert_output --partial "ERROR: Invalid selection ''. Please enter a number between 1 and 1."
    refute_output --partial "Selected: "
    run grep -cE '^(volume create|volume rm|create|cp) ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
}

@test "I-B: a Ctrl+C at the exit pause keeps the exit code (0 / 1) and prints no interrupt text (real pty)" {
    # The pause only arms on a terminal, so run under `script` (util-linux). The mock
    # arms a SIGINT to the script 1 s after its last docker call, while it waits at
    # "Press Enter to continue". stdin stays open (sleep) so the pause is not ended by
    # end of input. Cases: a cancel at RESTORE (exit 0), a refusal before the swap
    # (marker write fails, exit 1), and an after-swap failure (exit 1; before the fix
    # the INT handler said the data was "being replaced" and the code became 130).
    command -v script > /dev/null || skip "script (util-linux) not installed"
    _make_backup
    local c want input
    for c in cancel refuse afterswap; do
        unset RM_FAIL RM_INTERRUPT_AT
        case "${c}" in
            cancel) export RM_INTERRUPT_AT=pause; want=0; input='1\nno\n' ;;
            refuse) export RM_INTERRUPT_AT=pause RM_FAIL=marker; want=1; input='1\nRESTORE\n' ;;
            afterswap) export RM_INTERRUPT_AT=pause_swap RM_FAIL=swap; want=1; input='1\nRESTORE\n' ;;
        esac
        export I_B_INPUT="${input}"
        _mock_restore_docker
        run bash -c '(printf "${I_B_INPUT}"; sleep 3) | env -u CI -u DAAF_NESTED SHELL=/bin/bash script -qec "bash \"'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'\"" /dev/null'
        echo "I-B case=${c} status=${status} want=${want}"
        [ "${status}" -eq "${want}" ]
        assert_output --partial "Press Enter to continue"
        refute_output --partial "Restore interrupted"
        refute_output --partial "being replaced"
        # The delayed SIGINT was armed (that it lands at the pause is shown by the
        # `trap - INT TERM` mutant, which turns these codes into 130).
        [ -f "${TEST_DIR}/pause_armed" ]
    done
}

# =========================================================================
# --- Review round 3 fixes (fix round 3, 2026-10-01) ---
# =========================================================================
# I-1 (exit 125 is the after-swap path) and S-a (Claude login wording) are covered in
# the S1 / S-a tests above. S-b: the EXIT handler's cleanup ignores INT/TERM. S-c: the
# careful-cleanup flag is set before the swap-started flag is cleared. S-d: the
# fallback assert_failure rejects a non-numeric expected status.

@test "S-b: a Ctrl+C during the EXIT handler's cleanup cannot abort it: the cleanup finishes, the original exit code kept" {
    # RM_FAIL=crash exits the script (status 7) while preparing (before the Claude temp
    # exists), so the EXIT handler cleans up the data temp; RM_INTERRUPT_AT=cleanup sends
    # SIGINT to the script from inside that `volume rm` -- mid-cleanup. Without the
    # ignore, the re-armed `exit` trap ends the script right there: the removal result is
    # never recorded and "Its temporary copy was removed." (or the removal command) is
    # never printed.
    _make_backup
    export DAAF_NESTED=1 RM_FAIL=crash RM_INTERRUPT_AT=cleanup
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 7
    assert_output --partial "The restore stopped before replacing anything (see the message above)."
    assert_output --partial "Your DAAF data has not been changed."
    assert_output --partial "Its temporary copy was removed."
    refute_output --partial "Restore interrupted"
    [ -f "${TEST_DIR}/cleanup_interrupted" ]
    run grep -cxF 'volume rm daaf_daaf-data-restore-tmp' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
}

@test "S-c: the swap-not-run path sets the careful-cleanup flag BEFORE it clears the swap-started flag" {
    # A Ctrl+C between the two assignments must still find the swap "started" (temps
    # kept), never an ordinary cleanup that reaps helpers and skips the identity check.
    run bash -c "sed -n '/^_restore_fail_swap_not_run() {\$/,/^}\$/p' '${REPO_ROOT}/${_RESTORE_SH_REL}' | sed -n '2,3p'"
    assert_output "$(printf '%s\n' '    TEMP_CLEANUP_CAREFUL=1' '    SWAP_STARTED=0')"
    # It is the only place that clears the flag (the other line is its initialisation).
    run grep -cxE '[[:space:]]*SWAP_STARTED=0' "${REPO_ROOT}/${_RESTORE_SH_REL}"
    assert_output "2"
}

# Run test_helper.bash's FALLBACK assert_failure in a child bash: $1 = the status the
# `run` had, the rest = assert_failure's arguments. Prints SKIP-LIBS when bats-assert
# is installed (its own assert_failure replaces the fallback, so there is nothing to test).
_fallback_assert_failure() {
    mkdir -p "${TEST_DIR}/nolibs/sub"
    bash -c 'load() { return 0; }; BATS_TEST_DIRNAME="$1"; . "$2"; if [ "${_BATS_HELPERS_LOADED}" = true ]; then echo SKIP-LIBS; exit 0; fi; status="$3"; output=""; shift 3; assert_failure "$@"' _ "${TEST_DIR}/nolibs/sub" "${REPO_ROOT}/tests/bash/test_helper.bash" "$@"
}

@test "S-d: test_helper's fallback assert_failure fails loudly on a non-numeric expected status" {
    run _fallback_assert_failure 1 1
    if [ "${output}" = SKIP-LIBS ]; then skip "bats-assert is installed: the fallback is not defined"; fi
    assert_success
    run _fallback_assert_failure 1
    assert_success
    run _fallback_assert_failure 1 2
    assert_failure 1
    assert_output --partial "assert_failure failed: expected status 2, got 1"
    run _fallback_assert_failure 1 l
    assert_failure 1
    assert_output --partial "assert_failure failed: expected status 'l' is not a number"
    run _fallback_assert_failure 1 ''
    assert_failure 1
    assert_output --partial "is not a number"
    run _fallback_assert_failure 1 -1
    assert_failure 1
    assert_output --partial "is not a number"
    run _fallback_assert_failure 0
    assert_failure 1
    assert_output --partial "assert_failure failed: expected non-zero exit"
}

# =========================================================================
# --- Fix pass #19: field test 2026-10-05 (D1 holders, D3 wording) ---
# =========================================================================
# D1 (observed on Windows, field test results section 5): a Ctrl+C between `docker run`'s
# create and start left a never-started ("Created"), unlabelled container that still
# referenced the temp volume, so `docker volume rm` failed every time and the leftover
# could never be removed. Removal now lists the holders (`ps -a --filter volume=<temp>
# --format '{{.ID}} {{.State}}'`, stdout only), removes created / exited / dead ones with a
# PLAIN `docker rm <id>` (never -f), then the volume. Any other state means another restore
# may still be using it: nothing is removed. A failed list is "could not check", never "no
# holders". Careful cleanup (TEMP_CLEANUP_CAREFUL) neither lists nor removes holders. The
# mock fails `volume rm` while a holder remains, as the daemon did. D3: a Ctrl+C during the
# Claude Code swap names the Claude state, not the data that was already replaced.

_D1_DATA_TMP="daaf_daaf-data-restore-tmp"
_D1_CLAUDE_TMP="daaf_daaf-claude-config-restore-tmp"

# The removal-related docker calls in log order ($1 = log; $2 = how many, default all):
# holder lists, label reaps, container removals, volume removals and creates (a create
# is shown as `volume create <name>`, its per-run label dropped).
_d1_calls() {
    grep -E '^(ps -a --filter volume=|ps -aq --filter label=|rm |volume rm |volume create )' "$1" \
    | sed -E 's/^volume create .* ([^ ]+)$/volume create \1/' \
    | sed -n "1,${2:-\$}p"
}

# The same calls from the first holder list on.
_d1_calls_from_list() {
    _d1_calls "$1" | awk '/^ps -a --filter volume=/ { f = 1 } f'
}

# A holder-list call line for volume $1.
_d1_list() { printf 'ps -a --filter volume=%s --format {{.ID}} {{.State}}' "$1"; }

@test "D1: a leftover answered y whose temp a never-started (Created) container holds -> rm <id> BEFORE volume rm, removed, restore runs" {
    # The deterministic replica of the field test's Run 5a recovery: there the leftover
    # removal failed with "volume is in use - [c9be7425c57c...]" (the mock does the same
    # while the holder remains).
    _make_backup
    export DAAF_NESTED=1 RM_LEFTOVER="${_D1_DATA_TMP}" RM_HOLDERS="${_D1_DATA_TMP}=c9be7425c57c:created"
    _mock_restore_docker
    run bash -c 'printf "1\ny\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "Removed the leftover temporary copy."
    assert_output --partial "  Restore complete!"
    refute_output --partial "Could not remove the temporary copy"
    refute_output --partial "volume is in use"
    # Check pass (nothing removed yet), the label reap, then the removal pass: a fresh
    # list, the PLAIN rm of the holder, the volume -- and only then the new temp.
    run _d1_calls "${TEST_DIR}/docker_calls.log" 7
    assert_output "$(printf '%s\n' \
        "$(_d1_list "${_D1_DATA_TMP}")" \
        'ps -aq --filter label=org.daaf.restore-tmp-for=daaf_daaf-data' \
        'ps -aq --filter label=org.daaf.restore-tmp-for=daaf_daaf-claude-config' \
        "$(_d1_list "${_D1_DATA_TMP}")" \
        'rm c9be7425c57c' \
        "volume rm ${_D1_DATA_TMP}" \
        "volume create ${_D1_DATA_TMP}")"
    run grep -c -- '^rm -f c9be7425c57c$' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    run cat "${TEST_DIR}/holders_removed"
    assert_output "c9be7425c57c"
}

@test "D1: exited and dead holders (any letter case) are removed the same way, per volume, before each volume rm" {
    _make_backup
    export DAAF_NESTED=1 RM_LEFTOVER="${_D1_DATA_TMP} ${_D1_CLAUDE_TMP}" \
        RM_HOLDERS="${_D1_DATA_TMP}=e1:exited ${_D1_DATA_TMP}=d1:Dead ${_D1_CLAUDE_TMP}=c1:created"
    _mock_restore_docker
    run bash -c 'printf "1\ny\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "Removed the leftover temporary copy."
    assert_output --partial "  Restore complete!"
    run _d1_calls "${TEST_DIR}/docker_calls.log" 12
    assert_output "$(printf '%s\n' \
        "$(_d1_list "${_D1_DATA_TMP}")" \
        "$(_d1_list "${_D1_CLAUDE_TMP}")" \
        'ps -aq --filter label=org.daaf.restore-tmp-for=daaf_daaf-data' \
        'ps -aq --filter label=org.daaf.restore-tmp-for=daaf_daaf-claude-config' \
        "$(_d1_list "${_D1_DATA_TMP}")" \
        'rm e1' \
        'rm d1' \
        "volume rm ${_D1_DATA_TMP}" \
        "$(_d1_list "${_D1_CLAUDE_TMP}")" \
        'rm c1' \
        "volume rm ${_D1_CLAUDE_TMP}" \
        "volume create ${_D1_DATA_TMP}")"
}

@test "D1: a running/paused/restarting/removing or UNKNOWN-state (weird) holder of a leftover refuses (exit 1) after the check pass, before the reap and the swap-container rm, removing NOTHING" {
    _make_backup
    export DAAF_NESTED=1
    local s
    # `weird` (review round 6, NIT6): a state not known to the script is taken as live,
    # never as removable (the allow-list is created|exited|dead).
    for s in running paused restarting removing weird; do
        # The data temp's holder is removable; the CLAUDE temp's is not. Every leftover
        # is checked before anything is removed, so the data holder survives too.
        export RM_LEFTOVER="${_D1_DATA_TMP} ${_D1_CLAUDE_TMP}" RM_SWAP_CONTAINER=stopped \
            RM_HOLDERS="${_D1_DATA_TMP}=s1:created ${_D1_CLAUDE_TMP}=r1:${s}"
        _mock_restore_docker
        run bash -c 'printf "1\ny\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        echo "D1 busy state=${s}"
        assert_failure 1
        assert_output --partial "$(printf '%s\n' \
            '' \
            'ERROR: Something is still using the temporary copy left by the earlier restore' \
            "       (Docker volume '${_D1_CLAUDE_TMP}'), so it was not removed. Another restore may" \
            '       still be running.' \
            '       This restore did not change anything, but your DAAF data may still be' \
            '       incomplete from the earlier restore. Run the restore again to finish it.' \
            '       Wait a few minutes and close any other restore window, then run this' \
            '       restore again.')"
        refute_output --partial "Removed the leftover temporary copy."
        # Only the two holder lists: no label reap, no swap-container rm, no holder rm,
        # no volume rm, nothing created.
        run _d1_calls_from_list "${TEST_DIR}/docker_calls.log"
        assert_output "$(printf '%s\n' "$(_d1_list "${_D1_DATA_TMP}")" "$(_d1_list "${_D1_CLAUDE_TMP}")")"
        run grep -cE '^(rm|ps -aq|volume rm|volume create|create|cp) ' "${TEST_DIR}/docker_calls.log"
        assert_output "0"
        _assert_no_live_write
    done
    # A holder that started AFTER the check pass is caught by the removal pass's fresh
    # list: the same refusal, after the reap, still with nothing removed.
    export RM_LEFTOVER="${_D1_DATA_TMP}" RM_HOLDERS="" RM_HOLDERS_LATE="${_D1_DATA_TMP}=r9:running"
    unset RM_SWAP_CONTAINER
    _mock_restore_docker
    run bash -c 'printf "1\ny\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "       (Docker volume '${_D1_DATA_TMP}'), so it was not removed. Another restore may"
    assert_output --partial "       Your DAAF data has not been changed."
    run _d1_calls_from_list "${TEST_DIR}/docker_calls.log"
    assert_output "$(printf '%s\n' \
        "$(_d1_list "${_D1_DATA_TMP}")" \
        'ps -aq --filter label=org.daaf.restore-tmp-for=daaf_daaf-data' \
        'ps -aq --filter label=org.daaf.restore-tmp-for=daaf_daaf-claude-config' \
        "$(_d1_list "${_D1_DATA_TMP}")")"
}

@test "D1: a docker ps that FAILS while checking a leftover's holders refuses (could not check, Docker said), exit 1, nothing removed" {
    _make_backup
    export DAAF_NESTED=1 RM_LEFTOVER="${_D1_DATA_TMP}" RM_HOLDERS_PS_FAIL="${_D1_DATA_TMP}" RM_HOLDERS_PS_EXIT=2 \
        RM_HOLDERS="${_D1_DATA_TMP}=c9be7425c57c:created" \
        RM_HOLDERS_PS_SAID=$'WARNING: simulated docker config notice\nCannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?   \n'
    _mock_restore_docker
    run bash -c 'printf "1\ny\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    # Docker said = the LAST non-empty stderr line, trimmed.
    assert_output --partial "$(printf '%s\n' \
        '' \
        'ERROR: Could not check what is using the temporary copy left by the earlier' \
        "       restore (Docker volume '${_D1_DATA_TMP}'; docker ps failed, exit 2), so it was not removed." \
        '       Docker said: Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?' \
        '       Your DAAF data has not been changed.' \
        '       Make sure Docker Desktop is running, then run this restore again.')"
    refute_output --partial "Docker said: WARNING"
    refute_output --partial "Removed the leftover temporary copy."
    # A failed list is never "no holders": no reap, no rm, no volume rm, nothing created.
    run grep -c "^$(_d1_list "${_D1_DATA_TMP}")\$" "${TEST_DIR}/docker_calls.log"
    [ "${output}" -ge 1 ]
    run grep -cE '^(rm|ps -aq|volume rm|volume create|create|cp) ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    _assert_no_live_write
}

@test "D1: a stray stderr line from a holder list that works is not a holder (stdout only)" {
    _make_backup
    export DAAF_NESTED=1 RM_LEFTOVER="${_D1_DATA_TMP}" RM_HOLDERS_PS_NOISE=1 RM_HOLDERS="${_D1_DATA_TMP}=c9be7425c57c:created"
    _mock_restore_docker
    run bash -c 'printf "1\ny\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "Removed the leftover temporary copy."
    refute_output --partial "simulated docker config notice"
    run grep -cxF 'rm c9be7425c57c' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
}

@test "D1: cleanup after a prepare failure or a cancel at RESTORE removes a Created holder, then the temp (no kept-temp text)" {
    _make_backup
    export DAAF_NESTED=1 RM_HOLDERS="${_D1_DATA_TMP}=c9be7425c57c:created"
    local m input
    for m in prepfail cancel; do
        unset RM_FAIL
        if [ "${m}" = prepfail ]; then export RM_FAIL=cp; input='1\nRESTORE\n'; else input='1\nno\n'; fi
        export D1_INPUT="${input}"
        _mock_restore_docker
        run bash -c 'printf "${D1_INPUT}" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        echo "D1 cleanup case=${m}"
        if [ "${m}" = prepfail ]; then
            assert_failure 1
            assert_output --partial "ERROR: Copying the backup into Docker failed (see the message above)."
            assert_output --partial "       Your DAAF data has not been changed."
        else
            assert_success
            assert_output --partial "Restore cancelled. Your DAAF data has not been changed."
        fi
        refute_output --partial "The temporary copy could not be removed"
        refute_output --partial "If Docker says it is in use"
        run _d1_calls_from_list "${TEST_DIR}/docker_calls.log"
        assert_output "$(printf '%s\n' "$(_d1_list "${_D1_DATA_TMP}")" 'rm c9be7425c57c' "volume rm ${_D1_DATA_TMP}")"
        _assert_no_live_write
    done
}

@test "D1: cleanup with a BUSY holder keeps the temp and prints the kept-temp block (prepare failure, cancel, Ctrl+C, unexpected exit)" {
    _make_backup
    export DAAF_NESTED=1 RM_HOLDERS="${_D1_DATA_TMP}=r1:running"
    local m lead want input
    for m in prepfail cancel interrupt crash; do
        unset RM_FAIL RM_INTERRUPT_AT
        lead=""
        input='1\nRESTORE\n'
        case "${m}" in
            prepfail) export RM_FAIL=cp; lead="       "; want=1 ;;
            cancel) input='1\nno\n'; want=0 ;;
            interrupt) export RM_INTERRUPT_AT=cp; want=130 ;;
            crash) export RM_FAIL=crash; want=7 ;;
        esac
        export D1_INPUT="${input}"
        _mock_restore_docker
        run bash -c 'printf "${D1_INPUT}" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        echo "D1 busy cleanup case=${m} status=${status} want=${want}"
        [ "${status}" -eq "${want}" ]
        assert_output --partial "$(printf '%s\n' \
            "${lead}The temporary copy could not be removed." \
            "${lead}Something is still using it; another restore may still be running." \
            "${lead}To free the space it uses, run:" \
            "${lead}  docker volume rm ${_D1_DATA_TMP}" \
            "${lead}If Docker says it is in use, first run" \
            "${lead}  docker ps -a --filter volume=${_D1_DATA_TMP}" \
            "${lead}and remove each container it lists with docker rm <ID>, then try again.")"
        refute_output --partial "Docker said:"
        refute_output --partial "Its temporary copy was removed."
        # The temp is kept: no holder rm, no volume rm.
        run grep -cE "^(rm r1|volume rm ${_D1_DATA_TMP})\$" "${TEST_DIR}/docker_calls.log"
        assert_output "0"
        run grep -cxF "$(_d1_list "${_D1_DATA_TMP}")" "${TEST_DIR}/docker_calls.log"
        assert_output "1"
        _assert_no_live_write
    done
}

@test "D1: cleanup whose holder list FAILS keeps the temps; the first failure's reason (exit + Docker said) and a two-volume hint" {
    _make_full_backup
    export DAAF_NESTED=1 RM_HOLDERS_PS_FAIL="${_D1_DATA_TMP}" RM_HOLDERS="${_D1_CLAUDE_TMP}=r2:running"
    _mock_restore_docker
    run bash -c 'printf "1\nno\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "$(printf '%s\n' \
        'Restore cancelled. Your DAAF data has not been changed.' \
        'The temporary copy could not be removed.' \
        'Could not check what is using it (docker ps failed, exit 1).' \
        'Docker said: Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?' \
        'To free the space it uses, run:' \
        "  docker volume rm ${_D1_DATA_TMP} ${_D1_CLAUDE_TMP}" \
        'If Docker says it is in use, first run' \
        "  docker ps -a --filter volume=${_D1_DATA_TMP} --filter volume=${_D1_CLAUDE_TMP}" \
        'and remove each container it lists with docker rm <ID>, then try again.')"
    refute_output --partial "Something is still using it"
    run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
    run grep -c '^rm r2$' "${TEST_DIR}/docker_calls.log"
    assert_output "0"
}

@test "D1: careful cleanup (swap exit 3, a refused new temp) lists and removes NO holder; an identity refusal touches nothing" {
    local m
    for m in exit3 newtemp identity; do
        unset RM_SWAP_EXIT RM_TEMP_NOT_EMPTY RM_IDENTITY
        _make_full_backup
        export DAAF_NESTED=1 RM_HOLDERS="${_D1_DATA_TMP}=c9be7425c57c:created"
        case "${m}" in
            exit3) export RM_SWAP_EXIT=3 ;;
            newtemp) export RM_TEMP_NOT_EMPTY=claude ;;
            identity) export RM_IDENTITY=vanished_after_create ;;
        esac
        _mock_restore_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        echo "D1 careful case=${m}"
        assert_failure 1
        if [ "${m}" = identity ]; then
            assert_output --partial "It was not used, and nothing was removed."
        else
            # The volume rm is still tried; the daemon says "in use", which is shown.
            assert_output --partial "$(printf '%s\n' \
                '       The temporary copy could not be removed.' \
                "       Docker said: Error response from daemon: remove ${_D1_DATA_TMP}: volume is in use - [c9be7425c57c]" \
                '       To free the space it uses, run:')"
        fi
        # No holder list and no holder removal (the temp may be another restore's).
        run grep -c '^ps -a --filter volume=' "${TEST_DIR}/docker_calls.log"
        assert_output "0"
        run grep -c '^rm c9be7425c57c$' "${TEST_DIR}/docker_calls.log"
        assert_output "0"
        if [ "${m}" = identity ]; then
            run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
            assert_output "0"
        else
            run grep -cxF "volume rm ${_D1_DATA_TMP}" "${TEST_DIR}/docker_calls.log"
            assert_output "1"
        fi
    done
}

@test "D1: final cleanup after a verified restore with a busy holder (or a failed list) -> WARNING with reason and hint, still restored, latched" {
    _make_backup
    export DAAF_NESTED=1
    local m note
    for m in busy listfail; do
        unset RM_HOLDERS RM_HOLDERS_PS_FAIL
        if [ "${m}" = busy ]; then
            export RM_HOLDERS="${_D1_DATA_TMP}=r1:running"
            note='         Something is still using it; another restore may still be running.'
        else
            export RM_HOLDERS_PS_FAIL="${_D1_DATA_TMP}"
            note="$(printf '%s\n' \
                '         Could not check what is using it (docker ps failed, exit 1).' \
                '         Docker said: Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?')"
        fi
        _mock_restore_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        echo "D1 final case=${m}"
        assert_success
        assert_output --partial "$(printf '%s\n' \
            "WARNING: Could not remove the temporary copy of your data (Docker volume(s): ${_D1_DATA_TMP})." \
            "${note}" \
            '         Your DAAF data was restored. To free the space it uses, run:' \
            "           docker volume rm ${_D1_DATA_TMP}" \
            '         If Docker says it is in use, first run' \
            "           docker ps -a --filter volume=${_D1_DATA_TMP}" \
            '         and remove each container it lists with docker rm <ID>, then try again.')"
        assert_output --partial "Verified: 1 files in restored volume."
        assert_output --partial "Files:    1 files in volume"
        assert_output --partial "Restore completed WITH WARNINGS -- verify before relying on it"
        refute_output --partial "Restore complete!"
        run grep -cE "^(rm r1|volume rm ${_D1_DATA_TMP})\$" "${TEST_DIR}/docker_calls.log"
        assert_output "0"
    done
}

@test "D1: a failed leftover removal shows Docker's own reason as 'Docker said:' (volume in use; a holder rm that fails); no restart line" {
    _make_backup
    export DAAF_NESTED=1
    local m said
    for m in volumerm holderrm; do
        unset RM_FAIL RM_VOLUME_RM_SAID RM_HOLDERS RM_HOLDER_RM_FAIL
        export RM_LEFTOVER="${_D1_DATA_TMP}"
        if [ "${m}" = volumerm ]; then
            # The field test's text, after an earlier line and before a trailing blank one:
            # the LAST non-empty line, trimmed.
            export RM_FAIL=leftoverrm \
                RM_VOLUME_RM_SAID=$'Error response from daemon: an earlier line\nError response from daemon: remove daaf_daaf-data-restore-tmp: volume is in use - [c9be7425c57cdf99]  \n'
            said='Error response from daemon: remove daaf_daaf-data-restore-tmp: volume is in use - [c9be7425c57cdf99]'
        else
            export RM_HOLDERS="${_D1_DATA_TMP}=c9be7425c57c:created" RM_HOLDER_RM_FAIL=c9be7425c57c
            said='Error response from daemon: cannot remove container "/c9be7425c57c": simulated failure'
        fi
        _mock_restore_docker
        run bash -c 'printf "1\ny\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        echo "D1 leftover failure case=${m}"
        assert_failure 1
        assert_output --partial "$(printf '%s\n' \
            '' \
            'ERROR: Could not remove the temporary copy left by the earlier restore.' \
            "       Docker said: ${said}" \
            '       Your DAAF data has not been changed.' \
            '       Make sure no other restore is running (and Docker Desktop is running), then' \
            '       run this restore again, or remove it yourself with:' \
            "         docker volume rm ${_D1_DATA_TMP}" \
            '       If Docker says it is in use, first run' \
            "         docker ps -a --filter volume=${_D1_DATA_TMP}" \
            '       and remove each container it lists with docker rm <ID>, then try again.')"
        refute_output --partial "restart Docker Desktop"
        refute_output --partial "an earlier line"
        run grep -cE '^(volume create|create|cp) ' "${TEST_DIR}/docker_calls.log"
        assert_output "0"
        if [ "${m}" = holderrm ]; then
            # The holder could not be removed, so the volume was not tried.
            run grep -c '^volume rm ' "${TEST_DIR}/docker_calls.log"
            assert_output "0"
        fi
    done
}

@test "D3: Ctrl+C during the Claude Code swap names the Claude state (data already replaced), exit 130, nothing removed; the data swap keeps its line" {
    _make_full_backup
    export DAAF_NESTED=1
    local m
    for m in claudeswap swap; do
        export RM_INTERRUPT_AT="${m}"
        _mock_restore_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        echo "D3 case=${m}"
        assert_failure 130
        if [ "${m}" = claudeswap ]; then
            assert_output --partial "$(printf '%s\n' \
                'Restore interrupted while the Claude Code state (login and session history) was being replaced.' \
                'Your project files (DAAF data) were already replaced and checked.' \
                'The replacement keeps running inside Docker until it finishes. Your backup' \
                'folder 2026-01-01_daaf_backup/ is unchanged. Wait a few minutes, then run this restore' \
                'again and choose the same backup:' \
                '  bash restore_from_backup.sh')"
            refute_output --partial "Restore interrupted while your DAAF data was being replaced."
        else
            assert_output --partial "$(printf '%s\n' \
                'Restore interrupted while your DAAF data was being replaced.' \
                'The replacement keeps running inside Docker until it finishes. Your backup')"
            refute_output --partial "Claude Code state (login and session history) was being replaced"
            refute_output --partial "were already replaced and checked"
        fi
        # No temp removal (and no holder list or reap) once a swap started.
        run grep -cE '^(volume rm |ps -a --filter volume=|ps -aq )' "${TEST_DIR}/docker_calls.log"
        assert_output "0"
    done
}

@test "D1: the removal helper only ever removes this run's two temp names (name guard); its statuses (unit, real function text)" {
    # The script's test mode returns before these functions are defined, so the real
    # function text is extracted (as S-c does) and run with a logging docker stand-in.
    sed -n -e '/^_restore_last_line() {$/,/^}$/p' -e '/^_restore_remove_volume() {$/,/^}$/p' \
        "${REPO_ROOT}/${_RESTORE_SH_REL}" > "${TEST_DIR}/rmvol.sh"
    run grep -cE '^(_restore_last_line|_restore_remove_volume)\(\) \{$' "${TEST_DIR}/rmvol.sh"
    assert_output "2"
    cat > "${TEST_DIR}/rmvol_driver.sh" <<'DRIVER'
set -euo pipefail
. "$1"
LOG="$2"
TEMP_VOLUME_NAME=x_daaf-data-restore-tmp
CLAUDE_TEMP_VOLUME_NAME=x_daaf-claude-config-restore-tmp
: > "${LOG}"
docker() {
    printf '%s\n' "$*" >> "${LOG}"
    if [ "$1" = ps ]; then
        if [ "${STUB_PS_EXIT:-0}" -ne 0 ]; then printf 'noise line\n  Daemon down  \n' >&2; return "${STUB_PS_EXIT}"; fi
        printf '%s\n' "${STUB_HOLDERS:-}"
    fi
    return 0
}
try() {
    local st=0
    _restore_remove_volume "$@" || st=$?
    echo "[$1] ${2:-plain}: status=${st} said=${RESTORE_RM_SAID} psexit=${RESTORE_RM_PS_EXIT} calls=$(tr '\n' '|' < "${LOG}")"
    : > "${LOG}"
}
for n in x_daaf-data x_daaf-claude-config x_daaf-data-restore-tmp-old xx_daaf-data-restore-tmp ''; do
    try "${n}"
    try "${n}" careful
done
try x_daaf-data-restore-tmp careful
STUB_HOLDERS='abc created' try x_daaf-claude-config-restore-tmp check
STUB_HOLDERS=$'abc created\ndef Running' try x_daaf-data-restore-tmp
STUB_HOLDERS='abc Exited' try x_daaf-data-restore-tmp
STUB_PS_EXIT=4 try x_daaf-data-restore-tmp
DRIVER
    run bash "${TEST_DIR}/rmvol_driver.sh" "${TEST_DIR}/rmvol.sh" "${TEST_DIR}/rmvol.log"
    assert_success
    assert_output "$(printf '%s\n' \
        '[x_daaf-data] plain: status=1 said= psexit=0 calls=' \
        '[x_daaf-data] careful: status=1 said= psexit=0 calls=' \
        '[x_daaf-claude-config] plain: status=1 said= psexit=0 calls=' \
        '[x_daaf-claude-config] careful: status=1 said= psexit=0 calls=' \
        '[x_daaf-data-restore-tmp-old] plain: status=1 said= psexit=0 calls=' \
        '[x_daaf-data-restore-tmp-old] careful: status=1 said= psexit=0 calls=' \
        '[xx_daaf-data-restore-tmp] plain: status=1 said= psexit=0 calls=' \
        '[xx_daaf-data-restore-tmp] careful: status=1 said= psexit=0 calls=' \
        '[] plain: status=1 said= psexit=0 calls=' \
        '[] careful: status=1 said= psexit=0 calls=' \
        '[x_daaf-data-restore-tmp] careful: status=0 said= psexit=0 calls=volume rm x_daaf-data-restore-tmp|' \
        '[x_daaf-claude-config-restore-tmp] check: status=0 said= psexit=0 calls=ps -a --filter volume=x_daaf-claude-config-restore-tmp --format {{.ID}} {{.State}}|' \
        '[x_daaf-data-restore-tmp] plain: status=2 said= psexit=0 calls=ps -a --filter volume=x_daaf-data-restore-tmp --format {{.ID}} {{.State}}|' \
        '[x_daaf-data-restore-tmp] plain: status=0 said= psexit=0 calls=ps -a --filter volume=x_daaf-data-restore-tmp --format {{.ID}} {{.State}}|rm abc|volume rm x_daaf-data-restore-tmp|' \
        '[x_daaf-data-restore-tmp] plain: status=3 said=Daemon down psexit=4 calls=ps -a --filter volume=x_daaf-data-restore-tmp --format {{.ID}} {{.State}}|ps -a --filter volume=x_daaf-data-restore-tmp --format {{.ID}} {{.State}}|')"
}

# =========================================================================
# --- Fix pass #26 (F1 compatibility): version check, helper image check, pin ---
# =========================================================================
# Right after `docker info` the restore reads `docker version` and refuses (exit 1,
# nothing changed) when the client or Engine major is below 25 or cannot be read; any
# major other than the tested 29 prints a NOTE and continues (no WARNING latch). After
# the volume check it makes sure the PINNED helper image is present (`docker pull` when
# `image inspect` fails; refuse when the pull fails) -- all of it BEFORE any prompt. Every
# docker mock here delegates those calls to test_helper's mock_docker_shared_arms
# (MOCK_DOCKER_VERSION / _IMAGE_INSPECT_EXIT / _PULL_*); MOCK_DOCKER_ARGV_LOG records
# the exact argv of EVERY call, which the restore mock's own log does not.

# The restore's version-refusal block for client $1 / Engine $2 ($3 = "old" | "read").
_f1_restore_version_refusal() {
    local first
    if [ "$3" = old ]; then
        first="ERROR: This Docker version is too old for the restore (Docker client $1, Docker Engine $2)."
    else
        first="ERROR: Could not read the Docker version (Docker client $1, Docker Engine $2)."
    fi
    printf '%s\n' "${first}" \
        '       The restore needs Docker 25.0 or newer, for both the Docker client and Docker Engine' \
        '       (Docker Desktop 4.27.1 or newer). Update Docker, then run the restore again.' \
        '       (Docker Desktop or Docker Engine is required; Podman is not supported.)' \
        '       Nothing was changed.'
}

# Byte offset of $2 in $1 (-1 when absent): orders text that may share an output line.
_f1_offset() {
    local pre
    case "$1" in *"$2"*) ;; *) echo -1; return 0 ;; esac
    pre="${1%%"$2"*}"
    echo "${#pre}"
}

@test "F1 version: 29.x on both sides prints no NOTE; another major >= 25 (client or Engine) prints the NOTE once and the restore runs to the end" {
    _make_backup
    export DAAF_NESTED=1
    local c v note
    # "<docker version stdout>|<expected NOTE, empty = none>". The multi-line case: only
    # the LAST non-empty stdout line is the version (a notice line above it is ignored).
    for c in \
        "29.1.3 29.1.3|" \
        "29.0.0 29.4.1|" \
        $'WARNING: a notice line\n29.1.3 29.1.3\n|' \
        "25.0.2 29.1.3|NOTE: The restore has not been tested with this Docker version (Docker client 25.0.2, Docker Engine 29.1.3; tested: 29). Continuing." \
        "29.1.3 28.5.1|NOTE: The restore has not been tested with this Docker version (Docker client 29.1.3, Docker Engine 28.5.1; tested: 29). Continuing." \
        "30.0.0 30.0.0|NOTE: The restore has not been tested with this Docker version (Docker client 30.0.0, Docker Engine 30.0.0; tested: 29). Continuing."; do
        v="${c%%|*}"
        note="${c#*|}"
        export MOCK_DOCKER_VERSION="${v}"
        _mock_restore_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        echo "case version=[${v}]"
        assert_success
        assert_output --partial "  Restore complete!"
        refute_output --partial "WITH WARNINGS"
        refute_output --partial "ERROR:"
        if [ -z "${note}" ]; then
            refute_output --partial "NOTE: The restore has not been tested"
        else
            assert_output --partial "${note}"
            [ "$(grep -c 'NOTE: The restore has not been tested' <<< "${output}")" -eq 1 ]
        fi
    done
}

@test "F1 version: a client or Engine below 25 refuses, exit 1, the exact ERROR lines on stderr, and NO docker call after info + version" {
    _make_backup
    export DAAF_NESTED=1 MOCK_DOCKER_ARGV_LOG="${TEST_DIR}/argv.log"
    local v
    for v in "24.0.7 29.1.3" "29.1.3 24.0.7" "20.10.24 20.10.24"; do
        export MOCK_DOCKER_VERSION="${v}"
        : > "${MOCK_DOCKER_ARGV_LOG}"
        _mock_restore_docker
        # stderr ONLY (stdout to /dev/null): the refusal is exactly these five lines.
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'" 2>&1 > /dev/null'
        echo "case version=[${v}]"
        assert_failure 1
        assert_output "$(_f1_restore_version_refusal "${v% *}" "${v#* }" old)"
        run mock_docker_argv_show "${MOCK_DOCKER_ARGV_LOG}"
        assert_output "$(printf '%s\n' '[info]' '[version] [--format] [{{.Client.Version}} {{.Server.Version}}]')"
    done
}

@test "F1 version: an empty, partial or unparsable version refuses with 'Could not read', exit 1, nothing after info + version" {
    _make_backup
    export DAAF_NESTED=1 MOCK_DOCKER_ARGV_LOG="${TEST_DIR}/argv.log"
    local c v shown exitc
    # "<stdout>|<exit>|<client shown> <Engine shown>". "24.0.7 abc": unreadable wins
    # over too-old (the Engine side cannot be judged at all).
    for c in "|0|unknown unknown" "|1|unknown unknown" "29.1.3|0|29.1.3 unknown" "abc def|0|abc def" "v29.1.3 29.1.3|0|v29.1.3 29.1.3" "24.0.7 abc|0|24.0.7 abc"; do
        v="${c%%|*}"
        exitc="${c#*|}"; exitc="${exitc%%|*}"
        shown="${c##*|}"
        export MOCK_DOCKER_VERSION="${v}" MOCK_DOCKER_VERSION_EXIT="${exitc}"
        : > "${MOCK_DOCKER_ARGV_LOG}"
        _mock_restore_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'" 2>&1 > /dev/null'
        echo "case version=[${v}] exit=${exitc}"
        assert_failure 1
        assert_output "$(_f1_restore_version_refusal "${shown% *}" "${shown#* }" read)"
        run mock_docker_argv_show "${MOCK_DOCKER_ARGV_LOG}"
        assert_output "$(printf '%s\n' '[info]' '[version] [--format] [{{.Client.Version}} {{.Server.Version}}]')"
    done
}

# Review fix round 9 (ISSUE 1): a client of 25 or newer that cannot talk to an Engine
# older than 25.0 fails `docker info` itself, so the version check above is never
# reached. The info-failure branch reads `docker version` too and, when the client's
# major parses as >= 25 and the Engine's version is empty or unparsable, adds these two
# lines (client $1) after the unchanged "not running" line. Same exit 1.
_f1_restore_info_hint() {
    printf '%s\n' \
        "       If Docker is running, its Docker Engine may be older than 25.0 (Docker client $1)." \
        '       The restore needs Docker 25.0 or newer (Docker Desktop 4.27.1 or newer).'
}

@test "F1 info hint: docker info fails, client >= 25 and an empty or unparsable Engine -> the 'not running' line plus the old-Engine hint on stderr, exit 1, nothing after info + version" {
    export DAAF_NESTED=1 MOCK_DOCKER_INFO_EXIT=1 MOCK_DOCKER_ARGV_LOG="${TEST_DIR}/argv.log"
    local c v exitc client
    # "<docker version stdout>|<its exit>|<client shown>". A real 29.x client facing an
    # old Engine prints its own version and fails on the server part (inference: not
    # observed against a real old Engine), hence the nonzero exits; only the LAST
    # non-empty stdout line counts.
    for c in "29.1.3|1|29.1.3" "29.1.3 |1|29.1.3" "25.0.0 abc|0|25.0.0" $'WARNING: a notice\n30.0.1|1|30.0.1' "29|1|29" "29.1.3 v24.0.7|1|29.1.3"; do
        v="${c%%|*}"
        exitc="${c#*|}"; exitc="${exitc%%|*}"
        client="${c##*|}"
        export MOCK_DOCKER_VERSION="${v}" MOCK_DOCKER_VERSION_EXIT="${exitc}"
        : > "${MOCK_DOCKER_ARGV_LOG}"
        # stderr ONLY (stdout to /dev/null): the "not running" line and the hint.
        run bash -c 'bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'" < /dev/null 2>&1 > /dev/null'
        echo "case version=[${v}] exit=${exitc}"
        assert_failure 1
        assert_output "$(printf '%s\n' 'ERROR: Docker Desktop does not seem to be running. Please start it and try again.'; _f1_restore_info_hint "${client}")"
        run mock_docker_argv_show "${MOCK_DOCKER_ARGV_LOG}"
        assert_output "$(printf '%s\n' '[info]' '[version] [--format] [{{.Client.Version}} {{.Server.Version}}]')"
    done
}

@test "F1 info hint: docker info fails and the client is below 25, unparsable or absent, or the Engine version reads -> ONLY the unchanged 'not running' line, exit 1" {
    export DAAF_NESTED=1 MOCK_DOCKER_INFO_EXIT=1 MOCK_DOCKER_ARGV_LOG="${TEST_DIR}/argv.log"
    local c v exitc
    # "24.0.7": client below 25. "", "abc", "v29.1.3", "123456.0": no parsable client
    # (a major of six or more digits is unparsable in both twins). "29.1.3 29.1.3" and
    # "29.1.3 24.0.7": the Engine's version reads, so the hint does not apply.
    for c in "24.0.7|1" "|1" "abc|1" "v29.1.3|1" "123456.0|1" "29.1.3 29.1.3|0" "29.1.3 24.0.7|0"; do
        v="${c%%|*}"
        exitc="${c#*|}"
        export MOCK_DOCKER_VERSION="${v}" MOCK_DOCKER_VERSION_EXIT="${exitc}"
        : > "${MOCK_DOCKER_ARGV_LOG}"
        run bash -c 'bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'" < /dev/null 2>&1 > /dev/null'
        echo "case version=[${v}] exit=${exitc}"
        assert_failure 1
        assert_output 'ERROR: Docker Desktop does not seem to be running. Please start it and try again.'
        run mock_docker_argv_show "${MOCK_DOCKER_ARGV_LOG}"
        assert_output "$(printf '%s\n' '[info]' '[version] [--format] [{{.Client.Version}} {{.Server.Version}}]')"
    done
}

@test "F1 image: a present helper image is inspected by its pinned name right after the volume check and NOT pulled" {
    _make_backup
    export DAAF_NESTED=1 MOCK_DOCKER_ARGV_LOG="${TEST_DIR}/argv.log"
    : > "${MOCK_DOCKER_ARGV_LOG}"
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "  Restore complete!"
    refute_output --partial "Downloading the small helper image"
    run bash -c "mock_docker_argv_show '${MOCK_DOCKER_ARGV_LOG}' | head -n 5"
    [ "${lines[0]}" = '[info]' ]
    [ "${lines[1]}" = '[version] [--format] [{{.Client.Version}} {{.Server.Version}}]' ]
    [ "${lines[2]}" = '[volume] [inspect] [daaf_daaf-data]' ]
    [ "${lines[3]}" = "[image] [inspect] [${DAAF_BUSYBOX_PIN}]" ]
    [[ "${lines[4]}" == "[ps] "* ]]
    run grep -c '^pull' "${MOCK_DOCKER_ARGV_LOG}"
    assert_output "0"
}

@test "F1 image: a missing helper image is pulled (pinned name, progress shown) before anything else, then the restore runs to the end" {
    _make_backup
    export DAAF_NESTED=1 MOCK_DOCKER_ARGV_LOG="${TEST_DIR}/argv.log" MOCK_DOCKER_IMAGE_INSPECT_EXIT=1
    : > "${MOCK_DOCKER_ARGV_LOG}"
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "$(printf '%s\n' \
        'Downloading the small helper image busybox that the restore needs...' \
        '1.37.0: Pulling from library/busybox' \
        "Status: Downloaded newer image for ${DAAF_BUSYBOX_PIN}")"
    assert_output --partial "  Restore complete!"
    refute_output --partial "ERROR:"
    run bash -c "mock_docker_argv_show '${MOCK_DOCKER_ARGV_LOG}' | head -n 6"
    [ "${lines[3]}" = "[image] [inspect] [${DAAF_BUSYBOX_PIN}]" ]
    [ "${lines[4]}" = "[pull] [${DAAF_BUSYBOX_PIN}]" ]
    [[ "${lines[5]}" == "[ps] "* ]]
    run grep -c '^pull' "${MOCK_DOCKER_ARGV_LOG}"
    assert_output "1"
}

@test "F1 image: a failed pull refuses, exit 1, with Docker's last line and 'Nothing was changed.', before ANY volume, container or prompt" {
    _make_backup
    export DAAF_NESTED=1 MOCK_DOCKER_ARGV_LOG="${TEST_DIR}/argv.log" MOCK_DOCKER_IMAGE_INSPECT_EXIT=1 MOCK_DOCKER_PULL_EXIT=1
    local said
    # Docker's LAST non-empty stderr line, trimmed, is the one shown.
    export MOCK_DOCKER_PULL_STDERR=$'Using default tag: noise\n  Error response from daemon: Get "https://registry-1.docker.io/v2/": dial tcp: lookup registry-1.docker.io: no such host  \n\n'
    said='Error response from daemon: Get "https://registry-1.docker.io/v2/": dial tcp: lookup registry-1.docker.io: no such host'
    : > "${MOCK_DOCKER_ARGV_LOG}"
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'" 2>&1 > /dev/null'
    assert_failure 1
    assert_output "$(printf '%s\n' '' \
        'ERROR: The restore needs the small helper image busybox and could not download it.' \
        '       Check the internet connection and that Docker Desktop is running, then run the restore again.' \
        "       Docker said: ${said}" \
        '       Nothing was changed.')"
    # Nothing was created or run: the calls end with the failed pull.
    run mock_docker_argv_show "${MOCK_DOCKER_ARGV_LOG}"
    assert_output "$(printf '%s\n' '[info]' '[version] [--format] [{{.Client.Version}} {{.Server.Version}}]' \
        '[volume] [inspect] [daaf_daaf-data]' "[image] [inspect] [${DAAF_BUSYBOX_PIN}]" "[pull] [${DAAF_BUSYBOX_PIN}]")"
    # A pull that failed with nothing on stderr: no "Docker said:" line at all.
    export MOCK_DOCKER_PULL_STDERR=""
    _mock_restore_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_failure 1
    assert_output --partial "$(printf '%s\n' \
        'Downloading the small helper image busybox that the restore needs...' '' \
        'ERROR: The restore needs the small helper image busybox and could not download it.' \
        '       Check the internet connection and that Docker Desktop is running, then run the restore again.' \
        '       Nothing was changed.')"
    refute_output --partial "Docker said:"
    refute_output --partial "Available backups"
    _assert_no_live_write
}

@test "F1 order: the version NOTE and the image download come BEFORE the three prompts (stop, backup number, RESTORE), each asked once (real pty)" {
    # `read -p` prints its prompt only on a terminal, so run under `script` for a pty.
    command -v script > /dev/null || skip "script (util-linux) not installed"
    _make_backup
    export DAAF_NESTED=1 RM_RUNNING=daaf-daaf-docker-1 MOCK_DOCKER_VERSION="30.0.0 30.0.0" MOCK_DOCKER_IMAGE_INSPECT_EXIT=1
    _mock_restore_docker
    run bash -c 'printf "y\n1\nRESTORE\n" | env -u CI SHELL=/bin/bash script -qec "bash \"'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'\"" /dev/null'
    assert_success
    assert_output --partial "  Restore complete!"
    local note dl p1 p2 p3
    note="$(_f1_offset "${output}" 'NOTE: The restore has not been tested with this Docker version')"
    dl="$(_f1_offset "${output}" 'Downloading the small helper image busybox that the restore needs...')"
    p1="$(_f1_offset "${output}" 'Stop the container now? (y/n): ')"
    p2="$(_f1_offset "${output}" 'Enter backup number to restore (1-1): ')"
    p3="$(_f1_offset "${output}" 'Type RESTORE to confirm, or anything else to cancel: ')"
    echo "offsets note=${note} download=${dl} stop=${p1} number=${p2} RESTORE=${p3}"
    # One assertion per line: a failing [ ] that is not the LAST command of an && list
    # does not trip bats' errexit, so a chained form would pass vacuously.
    [ "${note}" -ge 0 ]
    [ "${note}" -lt "${dl}" ]
    [ "${dl}" -lt "${p1}" ]
    [ "${p1}" -lt "${p2}" ]
    [ "${p2}" -lt "${p3}" ]
    # Exactly three prompts, no fourth (no leftover prompt, no repeat).
    [ "$(grep -oE 'Stop the container now\? \(y/n\): |Enter backup number to restore \(1-1\): |Type RESTORE to confirm, or anything else to cancel: |Remove it and continue\? \(y/n\): ' <<< "${output}" | wc -l)" -eq 3 ]
}

@test "F1 order: the CI answers y / 1 / RESTORE (piped, running container) still drive a full restore" {
    # ci-integration.yml: printf 'y\n1\nRESTORE\n' | bash restore_from_backup.sh. The new
    # checks read no input, so each answer still reaches its own prompt.
    _make_backup
    export DAAF_NESTED=1 RM_RUNNING=daaf-daaf-docker-1 MOCK_DOCKER_IMAGE_INSPECT_EXIT=1
    _mock_restore_docker
    run bash -c 'printf "y\n1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
    assert_success
    assert_output --partial "container is currently running"
    assert_output --partial "Stopping containers"
    assert_output --partial "  Restore complete!"
    [ -f "${TEST_DIR}/composed_down" ]
    run grep -c -- '--sig-proxy=false --name daaf_daaf-data-restore-swap ' "${TEST_DIR}/docker_calls.log"
    assert_output "1"
}

@test "F1 pin: every docker run/create image argument is the pinned busybox digest, never a bare busybox (full restore, and a leftover answered y)" {
    _make_full_backup
    export DAAF_NESTED=1 MOCK_DOCKER_ARGV_LOG="${TEST_DIR}/argv.log" MOCK_DOCKER_IMAGE_INSPECT_EXIT=1
    local scenario n
    for scenario in full leftover; do
        unset RM_LEFTOVER RM_LEFTOVER_MARKER
        : > "${MOCK_DOCKER_ARGV_LOG}"
        if [ "${scenario}" = leftover ]; then
            export RM_LEFTOVER=daaf_daaf-data-restore-tmp RM_LEFTOVER_MARKER=yes
            _mock_restore_docker
            run bash -c 'printf "1\ny\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        else
            _mock_restore_docker
            run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/'"${_RESTORE_SH_REL}"'"'
        fi
        echo "scenario=${scenario}"
        assert_success
        assert_output --partial "  Restore complete!"
        run mock_docker_argv_images "${MOCK_DOCKER_ARGV_LOG}"
        n="${#lines[@]}"
        echo "run/create calls: ${n}"
        # Non-vacuous: copy, strip, chown, both replays + probes, counts, markers, swaps...
        [ "${n}" -ge 20 ]
        run bash -c "mock_docker_argv_images '${MOCK_DOCKER_ARGV_LOG}' | grep -vxF -- '${DAAF_BUSYBOX_PIN}'"
        assert_output ""
        # No argument anywhere names another busybox (bare, :latest, another digest).
        run awk -F '\037' -v pin="${DAAF_BUSYBOX_PIN}" '{ for (i = 1; i < NF; i++) if ($i ~ /^busybox([:@]|$)/ && $i != pin) print }' "${MOCK_DOCKER_ARGV_LOG}"
        assert_output ""
        run grep -c "^image"$'\037'"inspect"$'\037'"${DAAF_BUSYBOX_PIN}"$'\037'"\$" "${MOCK_DOCKER_ARGV_LOG}"
        assert_output "1"
        run grep -c "^pull"$'\037'"${DAAF_BUSYBOX_PIN}"$'\037'"\$" "${MOCK_DOCKER_ARGV_LOG}"
        assert_output "1"
    done
    # The leftover scenario did run the leftover's marker probe (a busybox `run`).
    run grep -c 'test ! -e /src/.daaf-restore-swap-started' "${MOCK_DOCKER_ARGV_LOG}"
    assert_output "1"
}
