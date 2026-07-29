#!/usr/bin/env bats
# ============================================================================
# Tests for update_daaf.sh -- DAAF Update Script
# ============================================================================
# update_daaf.sh is the most complex script: state machine with ahead/behind
# detection, merge/rebase paths, stash handling, conflict resolution.
# These tests focus on preflight checks and early-exit paths that can be
# tested without a real Docker daemon.
# ============================================================================

load 'test_helper'

setup() {
    common_setup
    mock_docker
    create_fake_compose_file
    # Isolate the ambient environment: dev-container installs export
    # DAAF_BRANCH (e.g. daaf_dev_r2), which steers update_daaf.sh onto the
    # cross-branch update path and broke the "Already up to date" tests
    # locally while CI (var unset) stayed green. Tests that exercise
    # DAAF_BRANCH behavior export it explicitly inside their own subshells,
    # so unsetting here pins every test to the CI-equivalent baseline.
    unset DAAF_BRANCH
}

teardown() {
    common_teardown
    # Clean up lock directories that may be left by lock contention tests
    rmdir /tmp/daaf-update.lock.d 2>/dev/null || true
}

# --- Syntax ---

@test "update_daaf.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
}

# --- Preflight: missing docker-compose.yml ---

@test "update_daaf.sh fails when docker-compose.yml is missing" {
    rm -f docker-compose.yml
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "docker-compose.yml"
}

# --- Preflight: missing Docker ---

@test "update_daaf.sh fails when docker command is not found" {
    mock_no_docker
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker"
}

# --- Preflight: Docker daemon not running ---

@test "update_daaf.sh fails when Docker daemon is not running" {
    MOCK_DOCKER_INFO_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

# --- DAAF_NESTED behavior ---

@test "update_daaf.sh suppresses pause trap when DAAF_NESTED=1" {
    export DAAF_NESTED=1
    # Will fail at some docker step, but should not pause
    MOCK_DOCKER_COMPOSE_EXIT=1
    MOCK_DOCKER_PS_OUTPUT=""
    run bash "${REPO_ROOT}/scripts/host/update_daaf.sh"
    refute_output --partial "Press Enter"
}

# --- Helper function: prompt_choice ---

@test "update_daaf.sh defines prompt_choice helper function" {
    # Verify the function exists in the script source
    run grep -c "prompt_choice()" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- Helper function: handle_conflict ---

@test "update_daaf.sh defines handle_conflict helper function" {
    run grep -c "handle_conflict()" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- Helper function: sync_host_scripts ---

@test "update_daaf.sh defines sync_host_scripts helper function" {
    run grep -c "sync_host_scripts()" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- Helper function: check_build_changes ---

@test "update_daaf.sh defines check_build_changes helper function" {
    run grep -c "check_build_changes()" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- Helper function: finish_update ---

@test "update_daaf.sh defines finish_update helper function" {
    run grep -c "finish_update()" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- ERR trap defined ---

@test "update_daaf.sh defines an ERR trap for cleanup" {
    run grep -c "trap cleanup_on_error ERR" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- Banner display ---

@test "update_daaf.sh displays the DAAF Updater banner" {
    export DAAF_NESTED=1
    # Will fail at preflight but should show banner first
    MOCK_DOCKER_INFO_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_output --partial "DAAF Updater"
}

# --- DAAF_BRANCH override ---

@test "update_daaf.sh uses DAAF_BRANCH variable in banner tip" {
    # The script references DAAF_BRANCH for branch resolution
    run grep -c "DAAF_BRANCH" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# ============================================================================
# Behavioral tests -- sourced functions
# ============================================================================
# Source the script in test mode so all helper functions are available
# without executing the main state-machine logic.
#
# The sourcing pattern:
#   DAAF_TEST_MODE=1 source update_daaf.sh   (defines functions, then returns)
#   trap - ERR                                (remove ERR trap from sourced script)
#   set +eu                                   (disable strict mode for test flexibility)
#
# After sourcing, these functions are callable:
#   prompt_choice, handle_conflict, sync_host_scripts,
#   check_build_changes, finish_update, cleanup_on_error
# ============================================================================

# --- sync_host_scripts behavioral tests ---
#
# The sync mechanism was redesigned: instead of a hardcoded pathspec diffed by
# the (old) running script, it derives the file list from the POST-UPDATE repo
# state (git ls-files at new HEAD), copies any host-appropriate file MISSING on
# the host unconditionally (tier A / existence-heal), and copies files that
# CHANGED in old_head..new_head (tier B). Mocks below therefore respond to
# `ls-files` in addition to `rev-parse HEAD`, `diff --name-only`, and `cp`.

@test "update: sync_host_scripts derives list from ls-files (not a hardcoded pathspec)" {
    # The redesign must NOT diff a hardcoded scripts/host/*.sh pathspec inside
    # the running script. It should call git ls-files against the new HEAD.
    run grep -c "ls-files 'scripts/host/\*'" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "update: sync_host_scripts skips when repo lists no host files" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        # ls-files returns nothing -> function returns early, no output.
        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "abc1234" ;;
                *ls-files*) echo "" ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "abc1234"
    '
    assert_success
    refute_output --partial "Syncing"
}

@test "update: sync_host_scripts existence-heal copies a file missing on host" {
    # daaf.sh is absent from the host dir (fresh TEST_DIR). Even with old_head
    # == new_head (nothing pulled), tier A must copy it out.
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "samehash" ;;
                *ls-files*) printf "scripts/host/daaf.sh\nscripts/host/run_daaf.sh\n" ;;
                cp*) return 0 ;;
                *) return 0 ;;
            esac
        }

        # old_head == new_head: no diff/tier-B, only existence-heal runs.
        sync_host_scripts "samehash"
    '
    assert_success
    assert_output --partial "Syncing utility scripts..."
    assert_output --partial "Updated: daaf.sh"
    assert_output --partial "Updated: run_daaf.sh"
}

@test "update: sync_host_scripts existence-heal skips files already present" {
    # Pre-create run_daaf.sh on the host; only the missing daaf.sh should copy.
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        touch ./run_daaf.sh

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "samehash" ;;
                *ls-files*) printf "scripts/host/daaf.sh\nscripts/host/run_daaf.sh\n" ;;
                cp*) return 0 ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "samehash"
    '
    assert_success
    assert_output --partial "Updated: daaf.sh"
    refute_output --partial "Updated: run_daaf.sh"
}

@test "update: sync_host_scripts tier B copies files changed in the update range" {
    # run_daaf.sh already present on host (so tier A skips it), but it changed
    # in old_head..new_head, so tier B must refresh it.
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        touch ./run_daaf.sh ./backup_daaf.sh ./daaf.sh

        # The cp mock MATERIALIZES the destination ($3): tier B stages the
        # incoming copy as a sibling file before comparing/backing-up/renaming,
        # so a mock that only returns 0 leaves the staged file missing and the
        # rename fails.
        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "new5678" ;;
                *ls-files*) printf "scripts/host/daaf.sh\nscripts/host/run_daaf.sh\nscripts/host/backup_daaf.sh\n" ;;
                *diff*--name-only*) printf "scripts/host/run_daaf.sh\nscripts/host/backup_daaf.sh\n" ;;
                cp*) printf "repo version\n" > "$3" ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "old1234"
    '
    assert_success
    assert_output --partial "Syncing updated utility scripts..."
    assert_output --partial "Updated: run_daaf.sh"
    assert_output --partial "Updated: backup_daaf.sh"
}

@test "update: tier B backs up an existing differing host copy before overwrite" {
    # Field finding 2026-07-17 (v2.0.1 vector, class E): a host copy that
    # differs from what tier B delivers must be saved to the rolling
    # <name>.pre-update BEFORE overwrite -- the tier C recoverability contract
    # applies to every overwrite path. (On old-era migrations every host
    # script is "changed in range", so tier B -- not tier C -- performs the
    # drift heal.)
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        printf "drifted local content\n" > ./run_daaf.sh

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "new5678" ;;
                *ls-files*) printf "scripts/host/run_daaf.sh\n" ;;
                *diff*--name-only*) printf "scripts/host/run_daaf.sh\n" ;;
                cp*) printf "repo version\n" > "$3" ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "old1234"
        echo "host-after: $(cat ./run_daaf.sh)"
        if [ -f ./run_daaf.sh.pre-update ]; then echo "backup: $(cat ./run_daaf.sh.pre-update)"; fi
    '
    assert_success
    assert_output --partial "Updated: run_daaf.sh (your previous copy was saved as run_daaf.sh.pre-update)"
    assert_output --partial "host-after: repo version"
    assert_output --partial "backup: drifted local content"
}

@test "update: tier B leaves no backup when the host copy already matches" {
    # An identical host copy is refreshed in place with NO .pre-update: a
    # spurious rolling backup here would clobber a meaningful one from an
    # earlier heal.
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        printf "repo version\n" > ./run_daaf.sh

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "new5678" ;;
                *ls-files*) printf "scripts/host/run_daaf.sh\n" ;;
                *diff*--name-only*) printf "scripts/host/run_daaf.sh\n" ;;
                cp*) printf "repo version\n" > "$3" ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "old1234"
        if [ -f ./run_daaf.sh.pre-update ]; then echo "backup-exists"; else echo "no-backup"; fi
    '
    assert_success
    assert_output --partial "Updated: run_daaf.sh"
    refute_output --partial "saved as run_daaf.sh.pre-update"
    assert_output --partial "no-backup"
}

@test "update: sync_host_scripts ignores changed files outside the platform filter" {
    # A .ps1 file changed upstream must NOT be copied on a Unix host, and
    # install.sh / migrate_daaf.sh (bootstrap-only) are excluded even if changed.
    # test_migration.sh (dev-only harness) is excluded too -- and because it
    # matches the *.sh case it would be synced WITHOUT the explicit exclusion,
    # so this assertion pins the exclusion, not merely the platform filter.
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        touch ./run_daaf.sh ./daaf.sh

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "new5678" ;;
                *ls-files*) printf "scripts/host/daaf.sh\nscripts/host/run_daaf.sh\nscripts/host/run_daaf.ps1\nscripts/host/install.sh\nscripts/host/migrate_daaf.sh\nscripts/host/test_migration.sh\n" ;;
                *diff*--name-only*) printf "scripts/host/run_daaf.ps1\nscripts/host/install.sh\nscripts/host/migrate_daaf.sh\nscripts/host/test_migration.sh\n" ;;
                cp*) return 0 ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "old1234"
    '
    assert_success
    refute_output --partial "run_daaf.ps1"
    refute_output --partial "Updated: install.sh"
    refute_output --partial "Updated: migrate_daaf.sh"
    refute_output --partial "Updated: test_migration.sh"
}

@test "update: sync_host_scripts syncs README.txt on Unix (shared plain-text file)" {
    # README.txt is not a .sh file but must pass the platform filter on Unix hosts.
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "new5678" ;;
                *ls-files*) printf "scripts/host/README.txt\n" ;;
                *diff*--name-only*) printf "scripts/host/README.txt\n" ;;
                cp*) return 0 ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "old1234"
    '
    assert_success
    assert_output --partial "Updated: README.txt"
}

@test "update: sync_host_scripts prints self-update notice when update_daaf.sh changed" {
    # update_daaf.sh present on host (tier A skips) but changed in the range ->
    # tier B refreshes it and the self-update re-run notice must fire.
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        touch ./update_daaf.sh

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "new5678" ;;
                *ls-files*) printf "scripts/host/update_daaf.sh\n" ;;
                *diff*--name-only*) printf "scripts/host/update_daaf.sh\n" ;;
                cp*) printf "repo version\n" > "$3" ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "old1234"
    '
    assert_success
    assert_output --partial "The updater itself was updated"
    assert_output --partial "Re-run it"
}

@test "update: sync_host_scripts does NOT print self-update notice for other changes" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        touch ./run_daaf.sh

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "new5678" ;;
                *ls-files*) printf "scripts/host/run_daaf.sh\n" ;;
                *diff*--name-only*) printf "scripts/host/run_daaf.sh\n" ;;
                cp*) return 0 ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "old1234"
    '
    assert_success
    refute_output --partial "The updater itself was updated"
}

@test "update: sync_host_scripts reports copy failures by name with recovery hint" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        # Unset DAAF_PROJECT_NAME so the hint resolves deterministically to the
        # fallback "daaf", independent of the host/container environment (this
        # container exports DAAF_PROJECT_NAME).
        unset DAAF_PROJECT_NAME

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "samehash" ;;
                *ls-files*) printf "scripts/host/daaf.sh\nscripts/host/run_daaf.sh\n" ;;
                cp*) return 1 ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "samehash"
    '
    assert_success
    assert_output --partial "Warning: could not copy daaf.sh"
    assert_output --partial "Warning: could not copy run_daaf.sh"
    # Manual-recovery hint now uses the project-resolved `docker cp
    # <project>-daaf-docker-1:` form (c5f69b6): a fresh user shell lacks
    # DAAF_PROJECT_NAME, so `docker compose cp` would resolve the wrong project.
    # DAAF_PROJECT_NAME is unset above, so the fallback 'daaf' is used.
    assert_output --partial "docker cp daaf-daaf-docker-1:/daaf/scripts/host/daaf.sh ./daaf.sh"
    assert_output --partial "docker cp daaf-daaf-docker-1:/daaf/scripts/host/run_daaf.sh ./run_daaf.sh"
}

@test "update: sync_host_scripts up-to-date path heals with empty old_head" {
    # Called with no old_head (the up-to-date early-exit path). Only tier A runs;
    # a missing file is still delivered even though nothing was pulled.
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "samehash" ;;
                *ls-files*) printf "scripts/host/daaf.sh\n" ;;
                cp*) return 0 ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts
    '
    assert_success
    assert_output --partial "Updated: daaf.sh"
}

# --- sync_host_scripts drift-heal tests (tier C) ---
#
# Tier C compares host files that EXIST and were NOT copied this run against the
# repo copy staged via a bulk `docker compose cp scripts/host <tmp>/repo_host`.
# The mock below implements `compose cp` by populating the destination tree so a
# local `cmp -s` can run for real. On drift (f0506f6), it now HEALS the host
# file: back up the old copy to `<name>.pre-update`, then overwrite with the repo
# version. If the backup step fails, the host file is left untouched (old-style
# warning). The drift loop also skips the currently-running updater script.

@test "update: sync_host_scripts heals a drifted host file with a .pre-update backup" {
    # run_daaf.sh exists on host with DIFFERENT content than the repo copy, and
    # is NOT in the changed range -> tier A/B skip it, tier C must heal it:
    # overwrite with the repo version and save the old copy as run_daaf.sh.pre-update.
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        printf "host-customized\n" > ./run_daaf.sh

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "samehash" ;;
                *ls-files*) printf "scripts/host/run_daaf.sh\n" ;;
                *"compose cp"*)
                    # Last arg is the destination repo_host dir. Populate it with
                    # the pristine repo copy (different from the host copy above).
                    dest="${@: -1}"
                    mkdir -p "${dest}"
                    printf "pristine-repo\n" > "${dest}/run_daaf.sh"
                    return 0 ;;
                cp*) return 0 ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "samehash"
        echo "---HOSTFILE---"
        cat ./run_daaf.sh
        echo "---BACKUP---"
        cat ./run_daaf.sh.pre-update
    '
    assert_success
    # (c) per-file "Updated:" line naming the .pre-update backup, plus the closing summary.
    assert_output --partial "Updated: run_daaf.sh (your previous copy was saved as run_daaf.sh.pre-update)"
    assert_output --partial "One or more host files were stale and have been updated"
    assert_output --partial "restore one by"
    # (a) host file now holds the repo version.
    assert_output --partial "---HOSTFILE---"
    assert_output --partial "pristine-repo"
    # (b) the .pre-update backup holds the OLD host content.
    assert_output --partial "---BACKUP---"
    assert_output --partial "host-customized"
}

@test "update: sync_host_scripts does NOT warn when host file matches repo" {
    # Identical content -> cmp -s succeeds -> no drift warning.
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        printf "identical\n" > ./run_daaf.sh

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "samehash" ;;
                *ls-files*) printf "scripts/host/run_daaf.sh\n" ;;
                *"compose cp"*)
                    dest="${@: -1}"
                    mkdir -p "${dest}"
                    printf "identical\n" > "${dest}/run_daaf.sh"
                    return 0 ;;
                cp*) return 0 ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "samehash"
    '
    assert_success
    refute_output --partial "differs from the repository version"
}

@test "update: sync_host_scripts drift heal overwrites the host file with the repo version" {
    # The drifted host file must end up byte-for-byte identical to the repo copy,
    # and the OLD host content must be preserved in <name>.pre-update.
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        printf "host-customized\n" > ./run_daaf.sh

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "samehash" ;;
                *ls-files*) printf "scripts/host/run_daaf.sh\n" ;;
                *"compose cp"*)
                    dest="${@: -1}"
                    mkdir -p "${dest}"
                    printf "pristine-repo\n" > "${dest}/run_daaf.sh"
                    return 0 ;;
                cp*) return 0 ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "samehash"
        # Assert the byte-for-byte outcome directly (not via --partial): the host
        # file is now the repo copy, and the backup is exactly the old content.
        [ "$(cat ./run_daaf.sh)" = "pristine-repo" ] && echo "HOST_OK"
        [ "$(cat ./run_daaf.sh.pre-update)" = "host-customized" ] && echo "BACKUP_OK"
    '
    assert_success
    assert_output --partial "HOST_OK"
    assert_output --partial "BACKUP_OK"
}

@test "update: sync_host_scripts drift does NOT overwrite when the .pre-update backup fails" {
    # Backup-failure safety valve (f0506f6): if the rolling .pre-update backup
    # cannot be written, the host file is NEVER overwritten and the old-style
    # warning with the project-resolved manual hint is printed instead.
    #
    # Force the backup step to fail with a `cp` shell-function override that
    # returns non-zero whenever the destination is the ".pre-update" backup path,
    # and delegates to the real `cp` for every other invocation (e.g. the repo
    # overwrite, which must never be reached here). This targets exactly the
    # `cp -f "./run_daaf.sh" "./run_daaf.sh.pre-update"` backup line.
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        unset DAAF_PROJECT_NAME
        printf "host-customized\n" > ./run_daaf.sh

        cp() {
            case "${!#}" in
                *.pre-update) return 1 ;;
                *) command cp "$@" ;;
            esac
        }

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "samehash" ;;
                *ls-files*) printf "scripts/host/run_daaf.sh\n" ;;
                *"compose cp"*)
                    dest="${@: -1}"
                    command mkdir -p "${dest}"
                    printf "pristine-repo\n" > "${dest}/run_daaf.sh"
                    return 0 ;;
                cp*) return 0 ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "samehash"
        # Host file must be UNCHANGED (backup failed -> never overwrite).
        [ "$(cat ./run_daaf.sh)" = "host-customized" ] && echo "HOST_UNCHANGED"
        [ ! -e ./run_daaf.sh.pre-update ] && echo "NO_BACKUP_FILE"
    '
    assert_success
    assert_output --partial "HOST_UNCHANGED"
    assert_output --partial "NO_BACKUP_FILE"
    # Old-style warning with the project-resolved manual hint (DAAF_PROJECT_NAME
    # unset -> fallback "daaf"). The "backup step failed" branch is the one hit.
    assert_output --partial "WARNING: run_daaf.sh is stale but could not be updated"
    assert_output --partial "backup step failed"
    assert_output --partial "docker cp daaf-daaf-docker-1:/daaf/scripts/host/run_daaf.sh ./run_daaf.sh"
    # No heal summary since nothing was actually updated.
    refute_output --partial "One or more host files were stale and have been updated"
}

@test "update: sync_host_scripts drift does NOT overwrite when the repo->host write fails after a successful backup" {
    # Third contract branch (f0506f6): the .pre-update backup SUCCEEDS but the
    # subsequent repo->host overwrite FAILS. The host file is left unchanged, the
    # (now-redundant) backup remains, and the "(write failed)" warning with the
    # project-resolved manual hint is printed. This is a distinct, separately
    # worded branch from the "backup step failed" path above.
    #
    # Force ONLY the overwrite to fail with a destination-aware `cp` override: the
    # backup copy (destination "*.pre-update") delegates to the real `cp` and
    # succeeds; the overwrite copy (destination "./run_daaf.sh", NOT .pre-update)
    # returns non-zero. Order matters -- the backup runs first and must succeed,
    # so the .pre-update file exists before the failing overwrite.
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        unset DAAF_PROJECT_NAME
        printf "host-customized\n" > ./run_daaf.sh

        cp() {
            case "${!#}" in
                *.pre-update) command cp "$@" ;;
                *) return 1 ;;
            esac
        }

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "samehash" ;;
                *ls-files*) printf "scripts/host/run_daaf.sh\n" ;;
                *"compose cp"*)
                    dest="${@: -1}"
                    command mkdir -p "${dest}"
                    printf "pristine-repo\n" > "${dest}/run_daaf.sh"
                    return 0 ;;
                cp*) return 0 ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "samehash"
        # Host file UNCHANGED (overwrite failed -> never leaves a partial repo copy).
        [ "$(cat ./run_daaf.sh)" = "host-customized" ] && echo "HOST_UNCHANGED"
        # Backup SUCCEEDED, so the .pre-update file exists and holds the old content.
        [ "$(cat ./run_daaf.sh.pre-update)" = "host-customized" ] && echo "BACKUP_EXISTS"
    '
    assert_success
    assert_output --partial "HOST_UNCHANGED"
    assert_output --partial "BACKUP_EXISTS"
    # "(write failed)"-branch warning + project-resolved manual hint (fallback "daaf").
    assert_output --partial "WARNING: run_daaf.sh is stale but could not be updated"
    assert_output --partial "write failed"
    assert_output --partial "docker cp daaf-daaf-docker-1:/daaf/scripts/host/run_daaf.sh ./run_daaf.sh"
    # This branch does not set drift_found -> no heal summary, and it is NOT the
    # "backup step failed" wording (that is the other branch).
    refute_output --partial "One or more host files were stale and have been updated"
    refute_output --partial "backup step failed"
}

@test "update: sync_host_scripts drift loop skips the running updater script itself" {
    # The drift loop must never overwrite update_daaf.sh from tier C, even when it
    # exists on host and drifts from the repo copy (self-overwrite mid-execution
    # risks running corrupted content; Tier B is the sanctioned self-refresh).
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        # update_daaf.sh present on host and DRIFTED; run_daaf.sh present + identical
        # (so the run has no other drift and prints no heal output).
        printf "host-updater\n" > ./update_daaf.sh
        printf "identical\n" > ./run_daaf.sh

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "samehash" ;;
                *ls-files*) printf "scripts/host/update_daaf.sh\nscripts/host/run_daaf.sh\n" ;;
                *"compose cp"*)
                    dest="${@: -1}"
                    mkdir -p "${dest}"
                    printf "repo-updater\n" > "${dest}/update_daaf.sh"
                    printf "identical\n" > "${dest}/run_daaf.sh"
                    return 0 ;;
                cp*) return 0 ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "samehash"
        # The running updater must be byte-for-byte unchanged (never healed).
        [ "$(cat ./update_daaf.sh)" = "host-updater" ] && echo "UPDATER_UNTOUCHED"
        [ ! -e ./update_daaf.sh.pre-update ] && echo "NO_UPDATER_BACKUP"
    '
    assert_success
    assert_output --partial "UPDATER_UNTOUCHED"
    assert_output --partial "NO_UPDATER_BACKUP"
    refute_output --partial "Updated: update_daaf.sh"
}

@test "update: sync_host_scripts does NOT drift-check a freshly-copied file" {
    # daaf.sh is MISSING on host -> tier A copies it -> it is excluded from tier C
    # even if the staged repo copy differs (which it will not, but the point is
    # freshly-copied files are never drift-warned).
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        # daaf.sh absent (tier A will copy it); run_daaf.sh present + identical.
        printf "identical\n" > ./run_daaf.sh

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "samehash" ;;
                *ls-files*) printf "scripts/host/daaf.sh\nscripts/host/run_daaf.sh\n" ;;
                *"compose cp"*)
                    dest="${@: -1}"
                    mkdir -p "${dest}"
                    # Staged repo copy of daaf.sh differs from whatever tier A put
                    # on host, but daaf.sh is in SYNC_COPIED so must be skipped.
                    printf "repo-daaf\n" > "${dest}/daaf.sh"
                    printf "identical\n" > "${dest}/run_daaf.sh"
                    return 0 ;;
                cp*) return 0 ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "samehash"
    '
    assert_success
    assert_output --partial "Updated: daaf.sh"
    refute_output --partial "WARNING: daaf.sh differs"
}

@test "update: sync_host_scripts degrades gracefully when drift staging fails" {
    # `docker compose cp` (bulk stage) fails -> drift check is skipped with a
    # single notice, and the run still succeeds (never aborts the update).
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        printf "host-customized\n" > ./run_daaf.sh

        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "samehash" ;;
                *ls-files*) printf "scripts/host/run_daaf.sh\n" ;;
                *"compose cp"*) return 1 ;;
                cp*) return 0 ;;
                *) return 0 ;;
            esac
        }

        sync_host_scripts "samehash"
    '
    assert_success
    assert_output --partial "could not check host scripts for drift"
    refute_output --partial "differs from the repository version"
}

# --- check_build_changes behavioral tests ---

@test "update: check_build_changes detects Dockerfile modifications" {
    # Pipe "n" to decline the rebuild prompt
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "new5678" ;;
                *diff*--name-only*) echo "Dockerfile" ;;
                *) return 0 ;;
            esac
        }
        echo "n" | check_build_changes "old1234"
    '
    assert_success
    assert_output --partial "Build files were updated"
}

@test "update: check_build_changes detects docker-compose.yml modifications" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        docker() {
            case "$*" in
                *rev-parse*HEAD*) echo "new5678" ;;
                *diff*--name-only*) echo "docker-compose.yml" ;;
                *) return 0 ;;
            esac
        }
        echo "n" | check_build_changes "old1234"
    '
    assert_success
    assert_output --partial "Build files were updated"
}

@test "update: check_build_changes reports no changes when unchanged" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        docker() {
            case "$1" in
                compose)
                    # rev-parse HEAD returns same hash as old_head
                    echo "samehash"
                    return 0
                    ;;
                *) return 0 ;;
            esac
        }
        check_build_changes "samehash"
    '
    assert_success
    assert_output --partial "No Dockerfile changes"
}

# --- finish_update behavioral tests ---

@test "update: finish_update calls sync and check_build_changes" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        BACKUP_BRANCH="backup/test-branch"

        # Override downstream functions to track calls
        sync_host_scripts() { echo "SYNC_CALLED:$1"; }
        check_build_changes() { echo "CHECK_CALLED:$1"; }

        finish_update "oldhash123"
    '
    assert_success
    assert_output --partial "SYNC_CALLED:oldhash123"
    assert_output --partial "CHECK_CALLED:oldhash123"
    assert_output --partial "Update complete!"
}

@test "update: finish_update displays extra message when provided" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        BACKUP_BRANCH="backup/test-branch"

        sync_host_scripts() { :; }
        check_build_changes() { :; }

        finish_update "oldhash123" "Your commits were rebased."
    '
    assert_success
    assert_output --partial "Update complete!"
    assert_output --partial "Your commits were rebased."
}

# --- prompt_choice behavioral tests ---
# Note: IS_INTERACTIVE is false inside `bash -c` subshells (no /dev/tty),
# which triggers the non-interactive auto-select path. To test the
# interactive read path, we define a wrapper that bypasses the check.

@test "update: prompt_choice auto-selects first choice in non-interactive mode" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        echo "ignored" | prompt_choice "Continue? [y/n]: " "y n"
    '
    assert_success
    assert_output --partial "y"
}

@test "update: prompt_choice auto-selects first of multi-option set" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        echo "ignored" | prompt_choice "Choose [1/2/3]: " "1 2 3"
    '
    assert_success
    assert_output --partial "1"
}

@test "update: prompt_choice reads input interactively when stdin is a TTY" {
    # Override prompt_choice to remove the TTY check, simulating interactive mode
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        prompt_choice() {
            local prompt_text="$1"
            local valid_choices="$2"
            local choice=""
            read -r choice
            choice=$(echo "${choice}" | tr "[:upper:]" "[:lower:]")
            if echo "${valid_choices}" | grep -qw "${choice}"; then
                echo "${choice}"
            fi
        }
        echo "y" | prompt_choice "Continue? [y/n]: " "y n"
    '
    assert_success
    assert_output --partial "y"
}

@test "update: prompt_choice normalizes uppercase to lowercase" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        prompt_choice() {
            local prompt_text="$1"
            local valid_choices="$2"
            local choice=""
            read -r choice
            choice=$(echo "${choice}" | tr "[:upper:]" "[:lower:]")
            if echo "${valid_choices}" | grep -qw "${choice}"; then
                echo "${choice}"
            fi
        }
        echo "Y" | prompt_choice "Continue? [y/n]: " "y n"
    '
    assert_success
    assert_output --partial "y"
}

# --- handle_conflict behavioral tests ---

@test "update: handle_conflict shows conflicting file list" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        BACKUP_BRANCH="backup/test-branch"

        docker() {
            case "$*" in
                *diff*--diff-filter=U*) printf "CLAUDE.md\nscripts/host/run_daaf.sh\n" ;;
                *) return 0 ;;
            esac
        }

        # Pipe "2" to choose manual resolution (avoids interactive Claude launch)
        echo "2" | handle_conflict "merge" "merge --abort" || true
    '
    assert_output --partial "CLAUDE.md"
    assert_output --partial "scripts/host/run_daaf.sh"
}

# handle_conflict calls prompt_choice internally. Since IS_INTERACTIVE is
# false in bash -c subshells, prompt_choice auto-selects option 1. We
# override prompt_choice to force option 2 for testing the manual path.

@test "update: handle_conflict option 2 shows manual resolution instructions" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        BACKUP_BRANCH="backup/test-branch"

        docker() {
            case "$1" in
                compose)
                    shift
                    case "$1" in
                        exec) printf "file.txt\n"; return 0 ;;
                        *) return 0 ;;
                    esac
                    ;;
                *) return 0 ;;
            esac
        }

        prompt_choice() { echo "2"; }
        handle_conflict "merge" "merge --abort" || true
    '
    assert_output --partial "resolve the conflicts manually"
}

@test "update: handle_conflict merge type shows git add + commit instructions" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        BACKUP_BRANCH="backup/test-branch"

        docker() {
            case "$1" in
                compose)
                    shift
                    case "$1" in
                        exec) printf "file.txt\n"; return 0 ;;
                        *) return 0 ;;
                    esac
                    ;;
                *) return 0 ;;
            esac
        }

        prompt_choice() { echo "2"; }
        handle_conflict "merge" "merge --abort" || true
    '
    assert_output --partial "git commit"
    # Merge type should NOT show rebase --continue
    refute_output --partial "git rebase --continue"
}

@test "update: handle_conflict rebase type shows git rebase --continue" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        BACKUP_BRANCH="backup/test-branch"

        docker() {
            case "$1" in
                compose)
                    shift
                    case "$1" in
                        exec) printf "file.txt\n"; return 0 ;;
                        *) return 0 ;;
                    esac
                    ;;
                *) return 0 ;;
            esac
        }

        prompt_choice() { echo "2"; }
        handle_conflict "rebase" "rebase --abort" || true
    '
    assert_output --partial "git rebase --continue"
}

@test "update: handle_conflict returns 1 when conflicts remain" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        BACKUP_BRANCH="backup/test-branch"

        docker() {
            case "$1" in
                compose)
                    shift
                    case "$1" in
                        exec) printf "file.txt\n"; return 0 ;;
                        *) return 0 ;;
                    esac
                    ;;
                *) return 0 ;;
            esac
        }

        echo "2" | handle_conflict "merge" "merge --abort"
    '
    assert_failure
}

# --- Safety tests ---

@test "update: ERR trap is registered after sourcing" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        # Do NOT clear the trap -- we want to verify it exists
        set +eu
        trap -p ERR
    '
    assert_success
    assert_output --partial "cleanup_on_error"
}

@test "update: locking uses portable mkdir (no flock)" {
    # Verify the script uses mkdir for locking, not flock
    run grep -ci 'mkdir.*lock' "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]

    run grep -c 'flock' "${REPO_ROOT}/scripts/host/update_daaf.sh"
    [ "${output}" = "0" ]
}

@test "update: cleanup_on_error prints recovery guidance" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        # Mock docker to prevent actual docker calls in cleanup
        docker() { return 1; }

        cleanup_on_error 2>&1
    '
    assert_success
    assert_output --partial "Something went wrong unexpectedly"
    assert_output --partial "safe to re-run"
}

@test "update: cleanup_on_error mentions stash when STASHED=true" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu

        docker() { return 1; }
        STASHED=true

        cleanup_on_error 2>&1
    '
    assert_success
    assert_output --partial "stash pop"
}

# =========================================================================
# Dry-run mode
# =========================================================================

@test "update_daaf.sh: dry-run completes successfully" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
}

@test "update_daaf.sh: dry-run reports already up to date" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/update_daaf.sh" 2>&1
    assert_success
    assert_output --partial "Already up to date"
}

# ============================================================================
# Integrated state-machine tests
# ============================================================================
# These test the MAIN ORCHESTRATION flow (not individual helper functions).
# The script is run as a full process with carefully crafted docker mock
# responses that dispatch on the git subcommand arguments.

# --- Helper: create a dispatch-based docker mock ---
# Sets up a docker function that dispatches on the full argument string.
# Callers configure behavior via MOCK_* variables before running the script.
setup_state_machine() {
    create_fake_compose_file
    export DAAF_NESTED=1
}

@test "update: clean pull path succeeds (behind, no local commits, no dirty files)" {
    setup_state_machine
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/CLAUDE.md"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/.git/shallow"*) return 1 ;;
                *"compose exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"compose exec"*"fetch"*) return 0 ;;
                *"compose exec"*"rev-parse --verify"*"backup/"*) return 1 ;;
                *"compose exec"*"rev-parse --verify"*"origin/main"*) return 0 ;;
                *"compose exec"*"branch --show-current"*) echo "main" ;;
                *"compose exec"*"rev-parse"*"origin/main"*) echo "def456remote" ;;
                *"compose exec"*"rev-parse"*"HEAD"*) echo "abc123local" ;;
                *"compose exec"*"diff --name-only"*"HEAD"*) echo "" ;;
                *"compose exec"*"rev-list --count"*"origin/main..HEAD"*) echo "0" ;;
                *"compose exec"*"rev-list --count"*"HEAD..origin/main"*) echo "3" ;;
                *"compose exec"*"pull"*) echo "Updating abc123..def456" ; return 0 ;;
                *"compose exec"*"branch"*) return 0 ;;
                *"compose exec"*"symbolic-ref"*) echo "main" ;;
                "cp"*) return 0 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_success
    assert_output --partial "Update complete!"
    assert_output --partial "Pulling updates..."
}

@test "update: already up to date exits cleanly (same SHA, no dirty files)" {
    setup_state_machine
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/CLAUDE.md"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/.git/shallow"*) return 1 ;;
                *"compose exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"compose exec"*"fetch"*) return 0 ;;
                *"compose exec"*"rev-parse --verify"*"backup/"*) return 1 ;;
                *"compose exec"*"rev-parse --verify"*"origin/main"*) return 0 ;;
                *"compose exec"*"branch --show-current"*) echo "main" ;;
                *"compose exec"*"rev-parse"*"origin/main"*) echo "abc123same" ;;
                *"compose exec"*"rev-parse"*"HEAD"*) echo "abc123same" ;;
                *"compose exec"*"diff --name-only"*"HEAD"*) echo "" ;;
                *"compose exec"*"branch"*) return 0 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_success
    assert_output --partial "Already up to date"
}

@test "update: already-up-to-date path still existence-heals a missing host script" {
    setup_state_machine
    # Same SHA everywhere (nothing to pull), but daaf.sh is missing on the host.
    # The up-to-date early exit must still call sync_host_scripts and copy it.
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/CLAUDE.md"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/.git/shallow"*) return 1 ;;
                *"compose exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"compose exec"*"fetch"*) return 0 ;;
                *"compose exec"*"rev-parse --verify"*"backup/"*) return 1 ;;
                *"compose exec"*"rev-parse --verify"*"origin/main"*) return 0 ;;
                *"compose exec"*"branch --show-current"*) echo "main" ;;
                *"compose exec"*"rev-parse"*"origin/main"*) echo "abc123same" ;;
                *"compose exec"*"rev-parse"*"HEAD"*) echo "abc123same" ;;
                *"compose exec"*"diff --name-only"*"HEAD"*) echo "" ;;
                *"compose exec"*"ls-files"*) echo "scripts/host/daaf.sh" ;;
                *"compose exec"*"branch"*) return 0 ;;
                "cp"*) return 0 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_success
    assert_output --partial "Already up to date"
    assert_output --partial "Updated: daaf.sh"
}

@test "update: no remote configured exits with guidance" {
    setup_state_machine
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*) return 0 ;;
                *"compose exec"*"remote get-url"*) echo "" ; return 1 ;;
                *"compose exec"*"branch"*) return 0 ;;
                *"compose exec"*"rev-parse"*"HEAD"*) echo "abc123" ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    # exit 0 with guidance message
    assert_success
    assert_output --partial "not connected to the update server"
}

@test "update: network failure during fetch exits with error" {
    setup_state_machine
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*) return 0 ;;
                *"compose exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"compose exec"*"fetch"*) echo "fatal: unable to access" >&2 ; return 1 ;;
                *"compose exec"*"branch"*) return 0 ;;
                *"compose exec"*"rev-parse"*"HEAD"*) echo "abc123" ;;
                *"compose exec"*"rev-parse --verify"*"backup/"*) return 1 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_failure
    assert_output --partial "Failed to fetch"
}

@test "update: lock contention exits with already running message" {
    setup_state_machine
    # Create the lock directory before running the script
    mkdir -p /tmp/daaf-update.lock.d
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_failure
    assert_output --partial "already running"
    # Clean up the lock
    rmdir /tmp/daaf-update.lock.d 2>/dev/null || true
}

@test "update: lock cleanup on exit (trap removes lock dir)" {
    setup_state_machine
    # Run the script in dry-run mode so it completes cleanly, then check that
    # the lock directory no longer exists.
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    # Lock directory should be cleaned up by the EXIT trap
    [ ! -d /tmp/daaf-update.lock.d ]
}

# ============================================================================
# Error path tests
# ============================================================================

@test "update: container not running and start fails exits with error" {
    setup_state_machine
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*) echo "" ;;
                *"compose up"*) echo "ERROR: Cannot start" >&2 ; return 1 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_failure
    assert_output --partial "Failed to start"
}

# --- Pre-update backup gate ---
# The updater's pre-update backup is prompted/optional. In the non-interactive test
# harness prompt_choice auto-selects the FIRST valid choice ("y"), so these tests
# exercise the opted-in path: a FAILED backup must abort the update with a clear
# message, and a SUCCESSFUL backup must let it continue (the abort must not
# false-fire). A declined backup (CHOICE=n) is unreachable non-interactively, so it
# is not exercised here.

@test "update: opted-in backup failure aborts the update with a clear message" {
    setup_state_machine
    # Stub backup script the updater will find in the CWD and run; it fails (exit 1).
    cat > "${TEST_DIR}/backup_daaf.sh" <<'STUB'
#!/usr/bin/env bash
echo "STUB BACKUP RAN"
exit 1
STUB
    chmod +x "${TEST_DIR}/backup_daaf.sh"
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/CLAUDE.md"*) return 0 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_failure
    assert_output --partial "STUB BACKUP RAN"
    assert_output --partial "Backup failed (exit code 1)"
    assert_output --partial "The update will not proceed without a successful backup"
}

@test "update: opted-in backup success lets the update continue past the backup step" {
    setup_state_machine
    # Stub backup script that succeeds (exit 0); the update must NOT abort and should
    # proceed to its normal outcome (same SHA everywhere -> "Already up to date").
    cat > "${TEST_DIR}/backup_daaf.sh" <<'STUB'
#!/usr/bin/env bash
echo "STUB BACKUP RAN"
exit 0
STUB
    chmod +x "${TEST_DIR}/backup_daaf.sh"
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/CLAUDE.md"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/.git/shallow"*) return 1 ;;
                *"compose exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"compose exec"*"fetch"*) return 0 ;;
                *"compose exec"*"rev-parse --verify"*"backup/"*) return 1 ;;
                *"compose exec"*"rev-parse --verify"*"origin/main"*) return 0 ;;
                *"compose exec"*"branch --show-current"*) echo "main" ;;
                *"compose exec"*"rev-parse"*"origin/main"*) echo "abc123same" ;;
                *"compose exec"*"rev-parse"*"HEAD"*) echo "abc123same" ;;
                *"compose exec"*"diff --name-only"*"HEAD"*) echo "" ;;
                *"compose exec"*"branch"*) return 0 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_success
    assert_output --partial "STUB BACKUP RAN"
    assert_output --partial "Already up to date"
    refute_output --partial "The update will not proceed without a successful backup"
}

@test "update: DAAF not installed (CLAUDE.md missing) exits with error" {
    setup_state_machine
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*/daaf/CLAUDE.md*) return 1 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_failure
    assert_output --partial "DAAF does not appear to be installed"
}

@test "update: DAAF_BRANCH specifies nonexistent branch exits with error" {
    setup_state_machine
    run bash -c '
        export DAAF_BRANCH="nonexistent-branch-xyz"
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/CLAUDE.md"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/.git/shallow"*) return 1 ;;
                *"compose exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"compose exec"*"fetch"*) return 0 ;;
                *"compose exec"*"rev-parse --verify"*"backup/"*) return 1 ;;
                *"compose exec"*"rev-parse --verify"*"origin/nonexistent-branch-xyz"*) return 1 ;;
                *"compose exec"*"rev-parse --verify"*"refs/tags/nonexistent-branch-xyz"*) return 1 ;;
                *"compose exec"*"branch"*) return 0 ;;
                *"compose exec"*"rev-parse"*"HEAD"*) echo "abc123" ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_failure
    assert_output --partial "nonexistent-branch-xyz"
    assert_output --partial "was not found"
    refute_output --partial "version tag"
}

# An env-origin DAAF_BRANCH that resolves to a version tag gives an informative
# REFUSAL (exit 1): the updater tracks a branch for ongoing updates and cannot
# advance to a fixed tag, so it names the tag, points at the supported re-install
# path, and states which branch ongoing updates track. It never persists a tag.
# (Repurposed from the former "tag-specific error" test after the env-tag design
# decision -- the file-origin tag path below is the softer warn-and-continue arm.)
@test "update: env-origin DAAF_BRANCH tag is refused with re-install guidance" {
    setup_state_machine
    run bash -c '
        export DAAF_BRANCH="v2.1.0"
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/CLAUDE.md"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/.git/shallow"*) return 1 ;;
                *"compose exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"compose exec"*"fetch"*) return 0 ;;
                *"compose exec"*"rev-parse --verify"*"backup/"*) return 1 ;;
                *"compose exec"*"rev-parse --verify"*"origin/v2.1.0"*) return 1 ;;
                *"compose exec"*"rev-parse --verify"*"refs/tags/v2.1.0"*) return 0 ;;
                *"compose exec"*"branch"*) return 0 ;;
                *"compose exec"*"rev-parse"*"HEAD"*) echo "abc123" ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_failure
    assert_output --partial "v2.1.0"
    assert_output --partial "version tag"
    assert_output --partial "not a branch"
    # Names the supported re-install path (pinned to the tag)...
    assert_output --partial "DAAF_BRANCH=v2.1.0 bash -c"
    # ...and states which branch ongoing updates track.
    assert_output --partial "default branch"
    # A tag is never saved as the update branch.
    assert_output --partial "never saved as your update branch"
}

# A file-origin DAAF_BRANCH tag (set in environment_settings.txt, NOT the
# environment) must NOT lock the user out: warn, name the file, and fall back to
# the auto-detected default branch for this run (exit 0, the update proceeds).
@test "update: file-origin DAAF_BRANCH tag warns and auto-detects (no hard exit)" {
    setup_state_machine
    printf 'DAAF_BRANCH=v2.1.0\n' > "${TEST_DIR}/environment_settings.txt"
    run bash -c '
        unset DAAF_BRANCH
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/CLAUDE.md"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/.git/shallow"*) return 1 ;;
                *"compose exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"compose exec"*"fetch"*) return 0 ;;
                *"compose exec"*"rev-parse --verify"*"backup/"*) return 1 ;;
                *"compose exec"*"rev-parse --verify"*"origin/v2.1.0"*) return 1 ;;
                *"compose exec"*"rev-parse --verify"*"refs/tags/v2.1.0"*) return 0 ;;
                *"compose exec"*"rev-parse --verify"*"origin/main"*) return 0 ;;
                *"compose exec"*"branch --show-current"*) echo "main" ;;
                *"compose exec"*"rev-parse"*"origin/main"*) echo "samehash" ;;
                *"compose exec"*"rev-parse"*"HEAD"*) echo "samehash" ;;
                *"compose exec"*"diff --name-only"*"HEAD"*) echo "" ;;
                *"compose exec"*"rev-list --count"*) echo "0" ;;
                *"compose exec"*"symbolic-ref"*) echo "main" ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_success
    assert_output --partial "environment_settings.txt"
    assert_output --partial "version tag"
    assert_output --partial "auto-detected default branch"
    assert_output --partial "Already up to date"
    # The file-tag warning is a soft warning, not the env-tag refusal.
    refute_output --partial "never saved as your update branch"
}

# An env-origin DAAF_BRANCH that IS a real branch is persisted back to
# environment_settings.txt (replace mode, with a .pre-update backup) after a
# successful update, so future runs track it without re-exporting.
@test "update: env-origin DAAF_BRANCH branch is persisted after a successful update" {
    setup_state_machine
    printf 'DAAF_PROJECT_NAME=daaf\n' > "${TEST_DIR}/environment_settings.txt"
    run bash -c '
        export DAAF_BRANCH="dev"
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/CLAUDE.md"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/.git/shallow"*) return 1 ;;
                *"compose exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"compose exec"*"fetch"*) return 0 ;;
                *"compose exec"*"rev-parse --verify"*"backup/"*) return 1 ;;
                *"compose exec"*"rev-parse --verify"*"origin/dev"*) return 0 ;;
                *"compose exec"*"branch --show-current"*) echo "dev" ;;
                *"compose exec"*"rev-parse"*"origin/dev"*) echo "def456remote" ;;
                *"compose exec"*"rev-parse"*"HEAD"*) echo "abc123local" ;;
                *"compose exec"*"diff --name-only"*"HEAD"*) echo "" ;;
                *"compose exec"*"rev-list --count"*"origin/dev..HEAD"*) echo "0" ;;
                *"compose exec"*"rev-list --count"*"HEAD..origin/dev"*) echo "3" ;;
                *"compose exec"*"pull"*) echo "Updating abc123..def456" ; return 0 ;;
                *"compose exec"*"branch"*) return 0 ;;
                *"compose exec"*"symbolic-ref"*) echo "dev" ;;
                "cp"*) return 0 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_success
    assert_output --partial "Update complete!"
    assert_output --partial "Saved DAAF_BRANCH=dev"
    run cat "${TEST_DIR}/environment_settings.txt"
    assert_output --partial "DAAF_BRANCH=dev"
    [ -f "${TEST_DIR}/environment_settings.txt.pre-update" ]
}

# finish_update's persistence block is fully DAAF_DRY_RUN gated (HSM5): with a
# PERSIST_BRANCH set and DAAF_DRY_RUN=1, it must write NOTHING -- no DAAF_BRANCH
# line, no .pre-update backup -- while still printing the upsert intent.
@test "update: finish_update branch persistence writes nothing under DAAF_DRY_RUN" {
    printf 'DAAF_PROJECT_NAME=daaf\n' > "${TEST_DIR}/environment_settings.txt"
    before="$(cat "${TEST_DIR}/environment_settings.txt")"
    run bash -c '
        cd "'"${TEST_DIR}"'"
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        # Export AFTER sourcing so the gate is live when upsert runs inside
        # finish_update (a source-time prefix would not survive to the call).
        export DAAF_DRY_RUN=1
        BACKUP_BRANCH="backup/test-branch"
        PERSIST_BRANCH="dev"
        sync_host_scripts() { :; }
        check_build_changes() { :; }
        finish_update "oldhash123"
    '
    assert_success
    assert_output --partial "Update complete!"
    assert_output --partial "[DRY-RUN] upsert_settings_key would write"
    refute_output --partial "Saved DAAF_BRANCH="
    after="$(cat "${TEST_DIR}/environment_settings.txt")"
    [ "${before}" = "${after}" ]
    [ ! -f "${TEST_DIR}/environment_settings.txt.pre-update" ]
}

# W3: the env-origin branch must persist even on a NO-OP success ("Already up to
# date"), which exits before finish_update. This is the most common re-run case
# (`DAAF_BRANCH=dev update` while already current): persist_branch_choice is now
# called on the no-op path so the choice is still saved.
@test "update: env-origin branch persists on the already-up-to-date no-op path" {
    setup_state_machine
    printf 'DAAF_PROJECT_NAME=daaf\n' > "${TEST_DIR}/environment_settings.txt"
    run bash -c '
        export DAAF_BRANCH="dev"
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/CLAUDE.md"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/.git/shallow"*) return 1 ;;
                *"compose exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"compose exec"*"fetch"*) return 0 ;;
                *"compose exec"*"rev-parse --verify"*"backup/"*) return 1 ;;
                *"compose exec"*"rev-parse --verify"*"origin/dev"*) return 0 ;;
                *"compose exec"*"branch --show-current"*) echo "dev" ;;
                *"compose exec"*"rev-parse"*"origin/dev"*) echo "abc123same" ;;
                *"compose exec"*"rev-parse"*"HEAD"*) echo "abc123same" ;;
                *"compose exec"*"diff --name-only"*"HEAD"*) echo "" ;;
                *"compose exec"*"branch"*) return 0 ;;
                "cp"*) return 0 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_success
    assert_output --partial "Already up to date"
    assert_output --partial "Saved DAAF_BRANCH=dev"
    run cat "${TEST_DIR}/environment_settings.txt"
    assert_output --partial "DAAF_BRANCH=dev"
    [ -f "${TEST_DIR}/environment_settings.txt.pre-update" ]
}

# W3 / HSM5: the extracted persist_branch_choice call path (shared by finish_update
# AND the no-op success exits) must write NOTHING under DAAF_DRY_RUN -- no
# DAAF_BRANCH line, no .pre-update backup -- while still printing the upsert intent.
@test "update: persist_branch_choice writes nothing under DAAF_DRY_RUN (no-op call path)" {
    printf 'DAAF_PROJECT_NAME=daaf\n' > "${TEST_DIR}/environment_settings.txt"
    before="$(cat "${TEST_DIR}/environment_settings.txt")"
    run bash -c '
        cd "'"${TEST_DIR}"'"
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        # Export AFTER sourcing so the gate is live when upsert runs inside
        # persist_branch_choice (a source-time prefix would not survive the call).
        export DAAF_DRY_RUN=1
        PERSIST_BRANCH="dev"
        persist_branch_choice
    '
    assert_success
    assert_output --partial "[DRY-RUN] upsert_settings_key would write"
    refute_output --partial "Saved DAAF_BRANCH="
    after="$(cat "${TEST_DIR}/environment_settings.txt")"
    [ "${before}" = "${after}" ]
    [ ! -f "${TEST_DIR}/environment_settings.txt.pre-update" ]
}

@test "update: DAAF_BRANCH is neither branch nor tag gives generic error" {
    setup_state_machine
    run bash -c '
        export DAAF_BRANCH="totally-bogus-ref"
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/CLAUDE.md"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/.git/shallow"*) return 1 ;;
                *"compose exec"*"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"compose exec"*"fetch"*) return 0 ;;
                *"compose exec"*"rev-parse --verify"*"backup/"*) return 1 ;;
                *"compose exec"*"rev-parse --verify"*"origin/totally-bogus-ref"*) return 1 ;;
                *"compose exec"*"rev-parse --verify"*"refs/tags/totally-bogus-ref"*) return 1 ;;
                *"compose exec"*"branch"*) return 0 ;;
                *"compose exec"*"rev-parse"*"HEAD"*) echo "abc123" ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_failure
    assert_output --partial "totally-bogus-ref"
    assert_output --partial "was not found"
    refute_output --partial "version tag"
}

# ============================================================================
# Interrupted-update resume (round-5 field finding 1)
# ============================================================================
# A genuine merge conflict makes the non-interactive updater exit 1 mid-merge.
# The user resolves, commits, and re-runs; the re-run must finish the journey
# (rebuild detection + tier-B host-script sync + stash restore) via a persisted
# resume marker rather than landing on the tier-A-only "already up to date" exit.

# --- write_resume_marker ---

@test "update: write_resume_marker writes the marker to the repo .git dir" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        OLD_HEAD="oldsha123"; TIMESTAMP="2026-01-01-000000"
        docker() {
            case "$*" in
                *"cat > /daaf/.git/daaf-update-resume"*) command touch "'"${TEST_DIR}"'/marker_write_attempted" ; return 0 ;;
                *) return 0 ;;
            esac
        }
        write_resume_marker
    '
    assert_success
    [ -f "${TEST_DIR}/marker_write_attempted" ]
}

@test "update: write_resume_marker is a no-op under DAAF_DRY_RUN" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        export DAAF_DRY_RUN=1
        OLD_HEAD="oldsha123"; TIMESTAMP="t"
        docker() {
            case "$*" in
                *"daaf-update-resume"*) command touch "'"${TEST_DIR}"'/marker_write_attempted" ; return 0 ;;
                *) return 0 ;;
            esac
        }
        write_resume_marker
    '
    assert_success
    [ ! -f "${TEST_DIR}/marker_write_attempted" ]
}

# --- finish_update clears the marker (single chokepoint) ---

@test "update: finish_update clears the resume marker on success" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        BACKUP_BRANCH="backup/test"
        sync_host_scripts() { :; }
        check_build_changes() { :; }
        persist_branch_choice() { :; }
        docker() {
            case "$*" in
                *"rm -f /daaf/.git/daaf-update-resume"*) command touch "'"${TEST_DIR}"'/marker_cleared" ; return 0 ;;
                *) return 0 ;;
            esac
        }
        finish_update "oldsha"
    '
    assert_success
    assert_output --partial "Update complete!"
    [ -f "${TEST_DIR}/marker_cleared" ]
}

# --- _find_update_backup_stash targets ONLY the "DAAF update backup" stash ---

@test "update: _find_update_backup_stash returns only the DAAF update backup ref" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        docker() {
            case "$*" in
                *"stash list"*) printf "stash@{0}: On main: WIP unrelated edit\nstash@{1}: On main: DAAF update backup 2026-01-01\n" ;;
                *) return 0 ;;
            esac
        }
        _find_update_backup_stash
    '
    assert_success
    assert_output "stash@{1}"
}

@test "update: _find_update_backup_stash returns nothing when no backup stash exists" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        docker() {
            case "$*" in
                *"stash list"*) printf "stash@{0}: On main: WIP unrelated edit\n" ;;
                *) return 0 ;;
            esac
        }
        _find_update_backup_stash
    '
    assert_success
    assert_output ""
}

# --- resume_finalize pops the backup stash, then finishes the update ---

@test "update: resume_finalize pops the backup stash then finishes against recorded OLD_HEAD" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        BACKUP_BRANCH="backup/test"
        OLD_HEAD="recordedsha"
        sync_host_scripts() { echo "SYNC:$1"; }
        check_build_changes() { echo "CHECK:$1"; }
        persist_branch_choice() { :; }
        docker() {
            case "$*" in
                *"stash list"*) printf "stash@{0}: On main: DAAF update backup 2026\n" ;;
                *"stash pop stash@{0}"*) echo "POPPED"; return 0 ;;
                *) return 0 ;;
            esac
        }
        resume_finalize
    '
    assert_success
    assert_output --partial "Restoring your set-aside changes..."
    assert_output --partial "POPPED"
    assert_output --partial "SYNC:recordedsha"
    assert_output --partial "CHECK:recordedsha"
    assert_output --partial "Update complete!"
}

@test "update: resume_finalize skips stash pop silently when no backup stash exists" {
    run bash -c '
        DAAF_TEST_MODE=1 source "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
        trap - ERR
        set +eu
        BACKUP_BRANCH="backup/test"
        OLD_HEAD="recordedsha"
        sync_host_scripts() { :; }
        check_build_changes() { :; }
        persist_branch_choice() { :; }
        docker() {
            case "$*" in
                *"stash list"*) echo "" ;;
                *"stash pop"*) command touch "'"${TEST_DIR}"'/unexpected_pop" ; return 0 ;;
                *) return 0 ;;
            esac
        }
        resume_finalize
    '
    assert_success
    refute_output --partial "Restoring your set-aside changes..."
    assert_output --partial "Update complete!"
    [ ! -f "${TEST_DIR}/unexpected_pop" ]
}

# --- Full-script: mid-merge guard exits 1 ---

@test "update: a still-in-progress merge guides the user and exits 1" {
    setup_state_machine
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/CLAUDE.md"*) return 0 ;;
                *"MERGE_HEAD"*) echo "yes" ;;
                *"rebase-merge"*) echo "" ;;
                *"daaf-update-resume"*) echo "" ;;
                *"compose exec"*"branch"*) return 0 ;;
                *"compose exec"*"rev-parse"*"HEAD"*) echo "abc123" ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_failure
    assert_output --partial "An update is still in progress"
    assert_output --partial "git commit"
    # It must NOT proceed to fetch/branch resolution.
    refute_output --partial "Update complete!"
}

# --- Full-script: resume routes the up-to-date early exit into finish_update ---
# The crux of the fix: on the re-run HEAD already equals the remote (the user
# committed the resolved merge), so we hit "already up to date". Because a valid
# marker records the PRE-update OLD_HEAD, rebuild detection runs against THAT
# baseline (diff shows Dockerfile) instead of the same-run HEAD (which would be
# equal and skip). Reverting the RESUMING routing sends this down the tier-A-only
# exit and neither the stash pop nor "Build files were updated" appears.

@test "update: valid resume marker finishes the update off the up-to-date exit" {
    setup_state_machine
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/CLAUDE.md"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/.git/shallow"*) return 1 ;;
                *"MERGE_HEAD"*) echo "" ;;
                *"rebase-merge"*) echo "" ;;
                *"daaf-update-resume"*) printf "OLD_HEAD=oldrecorded\nTIMESTAMP=t\n" ;;
                *"^{commit}"*) return 0 ;;
                *"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"fetch"*) return 0 ;;
                *"rev-parse --verify"*"backup/"*) return 1 ;;
                *"rev-parse --verify"*"origin/main"*) return 0 ;;
                *"branch --show-current"*) echo "main" ;;
                *"rev-parse"*"origin/main"*) echo "newsha" ;;
                *"rev-parse"*"HEAD"*) echo "newsha" ;;
                *"diff --name-only"*"HEAD"*) echo "" ;;
                *"stash list"*) printf "stash@{0}: On main: DAAF update backup 2026\n" ;;
                *"stash pop"*) return 0 ;;
                *"ls-files"*) echo "" ;;
                *"diff --name-only"*) echo "Dockerfile" ;;
                *"compose exec"*"branch"*) return 0 ;;
                "cp"*) return 0 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_success
    assert_output --partial "Resuming interrupted update..."
    assert_output --partial "Restoring your set-aside changes..."
    # Rebuild detection ran against the RECORDED pre-update head, not the same-run HEAD.
    assert_output --partial "Build files were updated"
    assert_output --partial "Update complete!"
}

# --- Full-script: invalid marker fails open (delete + continue normally) ---

@test "update: an invalid resume marker is ignored and the run continues normally" {
    setup_state_machine
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/CLAUDE.md"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/.git/shallow"*) return 1 ;;
                *"MERGE_HEAD"*) echo "" ;;
                *"rebase-merge"*) echo "" ;;
                *"daaf-update-resume"*) printf "OLD_HEAD=bogusref\nTIMESTAMP=t\n" ;;
                *"^{commit}"*) return 1 ;;
                *"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"fetch"*) return 0 ;;
                *"rev-parse --verify"*"backup/"*) return 1 ;;
                *"rev-parse --verify"*"origin/main"*) return 0 ;;
                *"branch --show-current"*) echo "main" ;;
                *"rev-parse"*"origin/main"*) echo "samesha" ;;
                *"rev-parse"*"HEAD"*) echo "samesha" ;;
                *"diff --name-only"*"HEAD"*) echo "" ;;
                *"ls-files"*) echo "" ;;
                *"compose exec"*"branch"*) return 0 ;;
                "cp"*) return 0 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_success
    assert_output --partial "leftover update marker with no valid restart point"
    assert_output --partial "Already up to date"
    refute_output --partial "Resuming interrupted update..."
    # Fail-open means the normal tier-A no-op exit, NOT resume finalization.
    refute_output --partial "Update complete!"
}

# --- Full-script: resume routes the DEFAULT-branch AHEAD>0 block into finish ---
# The blind spot the review caught: on the re-run the user committed the resolved
# merge, so HEAD is a merge commit (!= remote -> up-to-date check fails), BEHIND=0
# but AHEAD>0 carries the local merge/customization commits. Execution enters the
# default-branch AHEAD>0 block, which historically never checked RESUMING and
# re-showed the merge/rebase/abort menu -- stranding the set-aside stash (tree is
# now clean, STASHED=false). The fix routes RESUMING=true into resume_finalize
# before the menu. This pins: (a) the finalizer runs (stash pop + Update complete),
# (b) the menu never prints, (c) exit 0.

@test "update: resume finishes off the default-branch AHEAD>0 block (menu suppressed)" {
    setup_state_machine
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/CLAUDE.md"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/.git/shallow"*) return 1 ;;
                *"MERGE_HEAD"*) echo "" ;;
                *"rebase-merge"*) echo "" ;;
                *"daaf-update-resume"*) printf "OLD_HEAD=oldrecorded\nTIMESTAMP=t\n" ;;
                *"^{commit}"*) return 0 ;;
                *"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"fetch"*) return 0 ;;
                *"rev-parse --verify"*"backup/"*) return 1 ;;
                *"rev-parse --verify"*"origin/main"*) return 0 ;;
                *"branch --show-current"*) echo "main" ;;
                *"rev-parse"*"origin/main"*) echo "remotesha" ;;
                *"rev-parse"*"HEAD"*) echo "mergesha" ;;
                *"diff --name-only"*"HEAD"*) echo "" ;;
                *"rev-list --count"*"origin/main..HEAD"*) echo "1" ;;
                *"rev-list --count"*"HEAD..origin/main"*) echo "0" ;;
                *"stash list"*) printf "stash@{0}: On main: DAAF update backup 2026\n" ;;
                *"stash pop"*) return 0 ;;
                *"ls-files"*) echo "" ;;
                *"diff --name-only"*) echo "" ;;
                *"compose exec"*"branch"*) return 0 ;;
                "cp"*) return 0 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_success
    # (a) Routed into the resume finalizer.
    assert_output --partial "Detected an interrupted update -- finishing it now."
    assert_output --partial "Restoring your set-aside changes..."
    assert_output --partial "Update complete!"
    # (b) The merge/rebase/abort menu never printed.
    refute_output --partial "1) MERGE (recommended)"
    refute_output --partial "Choose [1/2/3]"
    refute_output --partial "that aren'\''t in"
    # (c) No fresh-pull re-run note when BEHIND=0.
    refute_output --partial "run the updater again to get them"
}

# --- Full-script: AHEAD>0 resume corner where new upstream arrived (BEHIND>0) ---
# Rare: new upstream commits landed between the conflict and the re-run. The fix
# always finishes the interrupted update first (never mixes it with a fresh pull),
# then prints a note telling the user to re-run for the new commits.

@test "update: resume off the AHEAD>0 block prints a re-run note when BEHIND>0" {
    setup_state_machine
    run bash -c '
        docker() {
            local all_args="$*"
            case "$all_args" in
                "info") return 0 ;;
                *"compose ps"*"--format"*) echo "daaf-docker" ;;
                *"compose exec"*"true"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/CLAUDE.md"*) return 0 ;;
                *"compose exec"*"test -f"*"/daaf/.git/shallow"*) return 1 ;;
                *"MERGE_HEAD"*) echo "" ;;
                *"rebase-merge"*) echo "" ;;
                *"daaf-update-resume"*) printf "OLD_HEAD=oldrecorded\nTIMESTAMP=t\n" ;;
                *"^{commit}"*) return 0 ;;
                *"remote get-url"*"origin"*) echo "https://github.com/DAAF-Contribution-Community/daaf.git" ;;
                *"fetch"*) return 0 ;;
                *"rev-parse --verify"*"backup/"*) return 1 ;;
                *"rev-parse --verify"*"origin/main"*) return 0 ;;
                *"branch --show-current"*) echo "main" ;;
                *"rev-parse"*"origin/main"*) echo "remotesha" ;;
                *"rev-parse"*"HEAD"*) echo "mergesha" ;;
                *"diff --name-only"*"HEAD"*) echo "" ;;
                *"rev-list --count"*"origin/main..HEAD"*) echo "1" ;;
                *"rev-list --count"*"HEAD..origin/main"*) echo "2" ;;
                *"stash list"*) printf "stash@{0}: On main: DAAF update backup 2026\n" ;;
                *"stash pop"*) return 0 ;;
                *"ls-files"*) echo "" ;;
                *"diff --name-only"*) echo "" ;;
                *"compose exec"*"branch"*) return 0 ;;
                "cp"*) return 0 ;;
                *) return 0 ;;
            esac
        }
        export -f docker
        bash "'"${REPO_ROOT}"'/scripts/host/update_daaf.sh"
    '
    assert_success
    assert_output --partial "Detected an interrupted update -- finishing it now."
    assert_output --partial "Update complete!"
    # The fresh-pull re-run note fires because BEHIND>0.
    assert_output --partial "The interrupted update was completed first."
    assert_output --partial "run the updater again to get them"
    assert_output --partial "bash update_daaf.sh"
    # Still no menu -- the interrupted update is finished first, never mixed.
    refute_output --partial "1) MERGE (recommended)"
    refute_output --partial "Choose [1/2/3]"
}
