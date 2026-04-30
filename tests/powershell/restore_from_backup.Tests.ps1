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

        It "uses cp -a (not cp -r) for permission-preserving copy" {
            $Content | Should -Match 'cp -a /source/\. /dest/'
            $Content | Should -Not -Match 'cp -r /source/\. /dest/'
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
