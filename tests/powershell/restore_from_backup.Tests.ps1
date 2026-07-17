# ============================================================================
# Pester tests for restore_from_backup.ps1 -- DAAF Restore from Backup
# ============================================================================

Describe "restore_from_backup.ps1" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
    }

    Context "Syntax validation" {
        It "parses without errors" {
            $errors = Test-ScriptSyntax -Path "$RepoRoot/scripts/host/restore_from_backup.ps1"
            $errors | Should -BeNullOrEmpty
        }
    }

    Context "Script structure" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/restore_from_backup.ps1" -Raw
        }

        It "sets ErrorActionPreference to Stop" {
            $Content | Should -Match '\$ErrorActionPreference\s*=\s*[''"]Stop[''"]'
        }

        It "enables Set-StrictMode -Version 3.0 AFTER the DAAF_TEST_MODE guard" {
            # Strict mode is dynamically scoped -- it must be placed after the
            # DAAF_TEST_MODE dot-source guard so Pester's dot-sourcing (which returns
            # at the guard) never leaks strict mode into the whole test session, while
            # real executions run fully protected. Assert BOTH presence and ordering.
            $Content | Should -Match 'Set-StrictMode -Version 3\.0'
            $guardIdx  = $Content.IndexOf('$env:DAAF_TEST_MODE -eq "1"')
            $strictIdx = $Content.IndexOf('Set-StrictMode -Version 3.0')
            $guardIdx  | Should -BeGreaterThan -1
            $strictIdx | Should -BeGreaterThan $guardIdx
        }

        It "defines Wait-AndExit function" {
            $Content | Should -Match 'function Wait-AndExit'
        }

        It "checks DAAF_NESTED in Wait-AndExit" {
            $Content | Should -Match 'DAAF_NESTED'
        }

        It "checks for Docker with Get-Command" {
            $Content | Should -Match 'Get-Command docker'
        }

        It "checks Docker daemon with docker info" {
            $Content | Should -Match 'docker info'
        }

        It "checks volume exists" {
            $Content | Should -Match 'docker volume inspect'
        }

        It "checks for running containers using the volume" {
            $Content | Should -Match 'docker ps --filter'
        }

        It "searches for backup folders matching date pattern" {
            $Content | Should -Match 'daaf_backup'
            $Content | Should -Match '\\d\{4\}-\\d\{2\}-\\d\{2\}'
        }

        It "contains destructive warning text" {
            $Content | Should -Match 'DESTRUCTIVE OPERATION'
        }

        It "requires RESTORE confirmation" {
            $Content | Should -Match 'Type RESTORE to confirm'
        }

        It "clears volume before copying (rm -rf step)" {
            $Content | Should -Match 'rm -rf /dest'
        }

        It "uses docker cp (not bind-mounted cp -a)" {
            # The copy mechanism is `docker create` + `docker cp` -- one for the
            # data volume, one for the Claude state volume -- and must NOT use the
            # old bind-mounted `cp -a /source` busybox copy.
            $Content | Should -Match 'docker create'
            $Content | Should -Match 'docker cp'
            $Content | Should -Not -Match 'cp -a /source'
        }

        It "repairs volume ownership after docker cp writes as root" {
            # `docker cp` INTO a container writes files as root; restore must chown
            # the volume back to appuser (UID 1000), matching daaf-init.
            $Content | Should -Match 'chown -R 1000:1000 /dest'
        }

        It "replays executable permissions from the manifest (Step 2d)" {
            # When ".daaf-permissions" is present, normalize files to 644 and
            # re-apply 755 to the manifest's paths (undoing NTFS mode loss).
            $Content | Should -Match '\.daaf-permissions'
            $Content | Should -Match 'find /dest -type f -exec chmod 644'
            $Content | Should -Match 'chmod 755'
        }

        It "skips normalization when the manifest is absent (backward compat)" {
            # No manifest => no normalization (blanket 644 would strip exec from
            # every script and be worse than the fabricated 0755). The absent-manifest
            # NOTE covers both an older backup AND a failed manifest write (Fix 3).
            $Content | Should -Match 'it may predate'
            $Content | Should -Match 'the manifest write may have failed during'
            $Content | Should -Match 'no normalization was applied'
        }

        It "replays symlinks from the manifest (Step 2e)" {
            # When ".daaf-symlinks" is present, recreate each link (path TAB target)
            # container-side, chown -h it to appuser, and strip the manifest.
            $Content | Should -Match '\.daaf-symlinks'
            $Content | Should -Match 'ln -sf -- '
            $Content | Should -Match 'chown -h 1000:1000'
        }

        It "passes the symlink-replay sh -c program without embedded double-quotes" {
            # The Step 2e replay program is shared logically with the .sh twin; an
            # embedded double quote would be re-parsed by the Windows C runtime and
            # mangle the argument. Assert the $symlinkReplayScript VALUE (text between
            # the outer PS delimiters) contains no double-quote char, and that it uses
            # the octal-printf BOM idiom (busybox sed has no \xNN escapes), not sed.
            # The BOM printf uses DOUBLE backslashes in the PS source so sh receives a
            # single backslash after its own unquoted-backslash processing.
            $replayLine = ($Content -split "`n") | Where-Object { $_ -match '\$symlinkReplayScript\s*=' }
            $replayLine | Should -Not -BeNullOrEmpty
            $value = ($replayLine -replace '^\s*\$symlinkReplayScript\s*=\s*"', '') -replace '"\s*$', ''
            $value | Should -Not -Match '"'
            $value | Should -Match "printf \\\\357\\\\273\\\\277"
        }

        It "invokes the symlink replay for BOTH the data volume AND the Claude volume" {
            # Regression guard for the review BLOCKER: an earlier draft ported the
            # symlink-replay call only to the DATA volume and silently omitted it from
            # the Claude-state restore block, so Claude-volume symlinks were never
            # recreated. A file-wide grep for ".daaf-symlinks" (or even for
            # "$symlinkReplayScript") PASSES on that broken state because the string is
            # present once -- which is exactly how the gap slipped through review. Assert
            # the program is actually INVOKED against two DISTINCT `/dest` volumes: one
            # bound to $VolumeName (data) and one bound to $ClaudeVolumeName (Claude).
            # Match the full `docker run ... sh -c $symlinkReplayScript` invocation lines
            # so a bare definition without a second call site cannot satisfy this.
            $invokeLines = ($Content -split "`n") | Where-Object {
                $_ -match 'docker run .*-v "\$\{[A-Za-z]+\}:/dest".*busybox sh -c \$symlinkReplayScript'
            }
            @($invokeLines).Count | Should -BeGreaterOrEqual 2
            # One invocation must bind the DATA volume, the other the CLAUDE volume.
            ($invokeLines -join "`n") | Should -Match '\$\{VolumeName\}:/dest'
            ($invokeLines -join "`n") | Should -Match '\$\{ClaudeVolumeName\}:/dest'
        }

        It "defines the symlink replay program unconditionally before the manifest probe" {
            # The program must be defined BEFORE the DATA-volume manifest probe so the
            # Claude-volume replay can reuse it even when the data volume had no symlink
            # manifest -- otherwise a Set-StrictMode read of an unset variable would
            # throw. Assert the definition precedes both the data-volume probe and the
            # Claude-restore block. Ordering is what makes the shared-program reuse safe.
            $defIdx    = $Content.IndexOf('$symlinkReplayScript =')
            $probeIdx  = $Content.IndexOf('$symlinkManifestPresent = ')
            # Anchor on the section-header marker (unique) rather than the bare phrase,
            # which also appears in an explanatory comment ABOVE the definition.
            $claudeIdx = $Content.IndexOf('--- Restore the Claude Code state volume ---')
            $defIdx    | Should -BeGreaterThan -1
            $probeIdx  | Should -BeGreaterThan $defIdx
            $claudeIdx | Should -BeGreaterThan $defIdx
        }

        It "passes the replay sh -c program without embedded double-quotes (Windows arg safety)" {
            # Regression: embedded " in a string passed to a native exe on Windows
            # is silently mangled by the C runtime (see shell-scripting gotchas.md).
            # The replay sh -c program is built with sh single-quotes and
            # backtick-escaped sh variables. Assert that the $replayScript VALUE (the
            # text between the outer PS delimiters) contains no double-quote chars:
            # after stripping the leading `$replayScript = "` and the trailing `"`,
            # no `"` may remain.
            $replayLine = ($Content -split "`n") | Where-Object { $_ -match '\$replayScript\s*=' }
            $replayLine | Should -Not -BeNullOrEmpty
            $value = ($replayLine -replace '^\s*\$replayScript\s*=\s*"', '') -replace '"\s*$', ''
            $value | Should -Not -Match '"'
            # And it must use the sh single-quote idioms, not double-quotes. The BOM is
            # stripped via octal printf (busybox sed has no \xNN escapes), NOT sed. The
            # regex needs a literal backslash before each octal group, hence \\ per byte.
            $value | Should -Match "printf '\\357\\273\\277'"
            $value | Should -Not -Match "sed '1s"
        }

        It "excludes both manifests and the Claude subfolder from the listing/scan counts" {
            # The listing loop and the Scanning-backup count must exclude BOTH the
            # ".daaf-permissions" and ".daaf-symlinks" manifests so all four counts
            # (listing, scan, verification, backup completion report) agree exactly.
            $Content | Should -Match '\$_\.Name -ne \$PermissionsManifest'
            $Content | Should -Match '\$_\.Name -ne \$SymlinksManifest'
            $Content | Should -Match '\+ Claude state'
        }

        It "verifies file count after restore" {
            $Content | Should -Match 'Verifying restore'
        }

        It "includes file count mismatch check" {
            $Content | Should -Match 'File count mismatch'
        }

        It "displays available backups with numbered list" {
            $Content | Should -Match 'Available backups'
        }

        It "defines Import-DaafSettingsInline" {
            $Content | Should -Match 'function Import-DaafSettingsInline'
        }

        It "derives volume name from DAAF_PROJECT_NAME env var (PS 5.1 safe, no ?? operator)" {
            $Content | Should -Match 'DAAF_PROJECT_NAME'
            $Content | Should -Match '_daaf-data'
            # No PS7-only null-coalescing operator
            $Content | Should -Not -Match '\?\?'
        }
    }
}

# ============================================================================
# Import-DaafSettingsInline unit tests
# ============================================================================

Describe "restore_from_backup.ps1 Import-DaafSettingsInline" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $env:DAAF_TEST_MODE = "1"
        . "$RepoRoot/scripts/host/restore_from_backup.ps1"
    }

    AfterAll {
        Remove-Item Env:DAAF_TEST_MODE -ErrorAction SilentlyContinue
    }

    BeforeEach {
        $script:TmpDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-restore-settings-$(Get-Random)")
        $script:SettingsFile = Join-Path $script:TmpDir "environment_settings.txt"
        Remove-Item Env:DAAF_PROJECT_NAME  -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_PORT_MARIMO   -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_PORT_LOGVIEWER -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_PORT_VSCODE   -ErrorAction SilentlyContinue
    }

    AfterEach {
        Remove-Item -Recurse -Force $script:TmpDir -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_PROJECT_NAME  -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_PORT_MARIMO   -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_PORT_LOGVIEWER -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_PORT_VSCODE   -ErrorAction SilentlyContinue
    }

    It "picks up DAAF_PROJECT_NAME from the settings file" {
        Set-Content -Path $script:SettingsFile -Value "DAAF_PROJECT_NAME=myinstance"
        Import-DaafSettingsInline -SettingsFile $script:SettingsFile
        $env:DAAF_PROJECT_NAME | Should -Be "myinstance"
    }

    It "lets an already-set env var win over the file" {
        Set-Content -Path $script:SettingsFile -Value "DAAF_PROJECT_NAME=fromfile"
        $env:DAAF_PROJECT_NAME = "fromshell"
        Import-DaafSettingsInline -SettingsFile $script:SettingsFile
        $env:DAAF_PROJECT_NAME | Should -Be "fromshell"
    }

    It "is a no-op when the settings file is absent" {
        $absentPath = Join-Path $script:TmpDir "nonexistent.txt"
        Import-DaafSettingsInline -SettingsFile $absentPath
        $env:DAAF_PROJECT_NAME | Should -BeNullOrEmpty
    }

    It "tolerates CRLF line endings" {
        [System.IO.File]::WriteAllBytes($script:SettingsFile, [System.Text.Encoding]::ASCII.GetBytes("DAAF_PORT_VSCODE=3020`r`n"))
        Import-DaafSettingsInline -SettingsFile $script:SettingsFile
        $env:DAAF_PORT_VSCODE | Should -Be "3020"
    }

    It "ignores non-DAAF keys" {
        Set-Content -Path $script:SettingsFile -Value "ANTHROPIC_API_KEY=sk-secret`nDAAF_PROJECT_NAME=safe"
        Import-DaafSettingsInline -SettingsFile $script:SettingsFile
        $env:DAAF_PROJECT_NAME | Should -Be "safe"
        $env:ANTHROPIC_API_KEY | Should -BeNullOrEmpty
    }
}

# ============================================================================
# Behavioral tests -- dot-source to verify functions
# ============================================================================

Describe "restore_from_backup.ps1 behavioral tests" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"

        $env:DAAF_TEST_MODE = "1"
        . "$RepoRoot/scripts/host/restore_from_backup.ps1"

        $script:Content = Get-Content "$RepoRoot/scripts/host/restore_from_backup.ps1" -Raw
    }

    AfterAll {
        Remove-Item Env:DAAF_TEST_MODE -ErrorAction SilentlyContinue
    }

    Context "Wait-AndExit function" {
        It "is callable after dot-sourcing" {
            Get-Command Wait-AndExit -ErrorAction SilentlyContinue |
                Should -Not -BeNullOrEmpty
        }
    }

    Context "Backup folder pattern matching" {
        It "uses regex pattern for date-based backup names" {
            $Content | Should -Match '\\d\{4\}-\\d\{2\}-\\d\{2\}'
        }

        It "matches suffixed backup names (a, b, c)" {
            $Content | Should -Match '\[a-z\]\?'
        }
    }

    Context "Safety features" {
        It "sorts backups descending (newest first)" {
            $Content | Should -Match 'Sort-Object.*-Descending'
        }

        It "validates numeric input with TryParse" {
            $Content | Should -Match 'TryParse'
        }

        It "handles cancelled restore gracefully" {
            $Content | Should -Match 'Restore cancelled'
        }
    }
}

# ============================================================================
# Dry-run mode
# ============================================================================

Describe "restore_from_backup.ps1 dry-run mode" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:OrigDryRun = $env:DAAF_DRY_RUN
        $script:OrigNested = $env:DAAF_NESTED
        $script:TestDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-restore-test-$(Get-Random)")
    }

    AfterAll {
        $env:DAAF_DRY_RUN = $script:OrigDryRun
        $env:DAAF_NESTED = $script:OrigNested
        Remove-Item -Recurse -Force $script:TestDir -ErrorAction SilentlyContinue
    }

    It "dry-run succeeds when no backups exist" {
        Push-Location $script:TestDir
        try {
            $env:DAAF_DRY_RUN = "1"
            $env:DAAF_NESTED = "1"
            $output = & "$RepoRoot/scripts/host/restore_from_backup.ps1" *>&1
            $LASTEXITCODE | Should -BeIn @(0, $null)
            ($output | Out-String) | Should -BeLike "*No backup folders found*"
        } finally {
            Pop-Location
        }
    }

    It "dry-run completes successfully with backups present" {
        Push-Location $script:TestDir
        try {
            $null = New-Item -ItemType Directory -Path (Join-Path $script:TestDir "2026-01-01_daaf_backup") -Force
            $null = New-Item -ItemType File -Path (Join-Path $script:TestDir "2026-01-01_daaf_backup/f1") -Force
            $env:DAAF_DRY_RUN = "1"
            $env:DAAF_NESTED = "1"
            $null = & "$RepoRoot/scripts/host/restore_from_backup.ps1" *>&1
            $LASTEXITCODE | Should -BeIn @(0, $null)
        } finally {
            Pop-Location
        }
    }

    It "dry-run produces DRY-RUN markers" {
        Push-Location $script:TestDir
        try {
            $null = New-Item -ItemType Directory -Path (Join-Path $script:TestDir "2026-01-01_daaf_backup") -Force
            $null = New-Item -ItemType File -Path (Join-Path $script:TestDir "2026-01-01_daaf_backup/f1") -Force
            $env:DAAF_DRY_RUN = "1"
            $env:DAAF_NESTED = "1"
            $output = & "$RepoRoot/scripts/host/restore_from_backup.ps1" *>&1
            ($output | Out-String) | Should -BeLike "*``[DRY-RUN``]*"
        } finally {
            Pop-Location
        }
    }
}

# ============================================================================
# Error paths
# ============================================================================

Describe "restore_from_backup.ps1 error paths" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:Content = Get-Content "$RepoRoot/scripts/host/restore_from_backup.ps1" -Raw
    }

    Context "Running container detected" {
        It "offers to stop running containers" {
            $Content | Should -Match 'container is currently running'
            $Content | Should -Match 'Stop the container now'
        }

        It "stops containers when user agrees" {
            $Content | Should -Match 'Stopping containers'
            $Content | Should -Match 'docker compose down'
        }
    }

    Context "User declines to stop container" {
        It "cancels restore when user declines stop (exit 0)" {
            $Content | Should -Match 'Restore cancelled\. Stop the container manually'
        }
    }

    Context "Invalid backup selection" {
        It "rejects non-numeric input (exit 1)" {
            $Content | Should -Match 'TryParse'
            $Content | Should -Match 'Invalid selection'
        }

        It "rejects out-of-range selection (exit 1)" {
            $Content | Should -Match '\$ChoiceNum -lt 1 -or \$ChoiceNum -gt \$Backups\.Count'
        }
    }

    Context "User cancels at RESTORE confirmation" {
        It "exits cleanly when user types something other than RESTORE (exit 0)" {
            $Content | Should -Match '\$Confirm -ne "RESTORE"'
            $Content | Should -Match 'Restore cancelled'
        }
    }

    Context "Volume clear fails" {
        It "exits with error when volume clear fails (exit 1)" {
            $Content | Should -Match 'Failed to clear Docker volume'
            $Content | Should -Match 'inconsistent state'
        }
    }

    Context "Zero files after restore" {
        It "exits with error when zero files found after restore (exit 1)" {
            $Content | Should -Match '\$RestoredCount -eq 0'
            $Content | Should -Match '0 files found in restored volume'
        }
    }

    Context "File count mismatch after restore" {
        It "shows warning when file count differs beyond tolerance" {
            $Content | Should -Match 'File count mismatch'
            $Content | Should -Match 'restore may be incomplete'
        }
    }

    Context "No backup folders found" {
        It "exits with error when no backups exist (exit 1)" {
            $Content | Should -Match 'No backup folders found'
            $Content | Should -Match 'daaf-docker folder'
        }
    }
}
