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
