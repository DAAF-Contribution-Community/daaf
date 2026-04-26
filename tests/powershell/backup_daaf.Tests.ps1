# ============================================================================
# Pester tests for backup_daaf.ps1 -- DAAF Backup Utility (Windows)
# ============================================================================

Describe "backup_daaf.ps1" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
    }

    Context "Syntax validation" {
        It "parses without errors" {
            $errors = Test-ScriptSyntax -Path "$RepoRoot/scripts/host/backup_daaf.ps1"
            $errors | Should -BeNullOrEmpty
        }
    }

    Context "Script structure" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/backup_daaf.ps1" -Raw
        }

        It "sets ErrorActionPreference to Stop" {
            $Content | Should -Match '\$ErrorActionPreference\s*=\s*[''"]Stop[''"]'
        }

        It "defines Pause-And-Exit function" {
            $Content | Should -Match 'function Pause-And-Exit'
        }

        It "checks DAAF_NESTED in Pause-And-Exit" {
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

        It "uses date-based backup naming" {
            $Content | Should -Match 'yyyy-MM-dd'
        }

        It "implements suffix versioning (a, b, c)" {
            $Content | Should -Match '\[char\]\(97 \+ \$SuffixNum\)'
        }

        It "limits to 26 backups per day" {
            $Content | Should -Match '26'
            $Content | Should -Match 'Too many backups'
        }

        It "scans Docker volume for file count" {
            $Content | Should -Match 'Scanning Docker volume'
        }

        It "displays progress during copy" {
            $Content | Should -Match 'Progress:'
        }

        It "verifies file count after backup" {
            $Content | Should -Match 'files copied'
        }

        It "uses cp -a (not cp -r) for permission-preserving copy" {
            $Content | Should -Match 'cp -a /source/\. /dest/'
            $Content | Should -Not -Match 'cp -r /source/\. /dest/'
        }

        It "checks available disk space before copying" {
            $Content | Should -Match 'Insufficient disk space'
            $Content | Should -Match 'System\.IO\.DriveInfo'
        }

        It "performs size-based backup verification" {
            $Content | Should -Match 'Size verification'
            $Content | Should -Match 'Backup size mismatch'
        }
    }
}

# ============================================================================
# Behavioral tests -- dot-source to verify functions + source analysis
# ============================================================================

Describe "backup_daaf.ps1 behavioral tests" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"

        $env:DAAF_TEST_MODE = "1"
        . "$RepoRoot/scripts/host/backup_daaf.ps1"

        $script:Content = Get-Content "$RepoRoot/scripts/host/backup_daaf.ps1" -Raw
    }

    AfterAll {
        Remove-Item Env:DAAF_TEST_MODE -ErrorAction SilentlyContinue
    }

    # -----------------------------------------------------------------
    # Pause-And-Exit (the only function exposed)
    # -----------------------------------------------------------------
    Context "Pause-And-Exit function" {
        It "is callable after dot-sourcing" {
            Get-Command Pause-And-Exit -ErrorAction SilentlyContinue |
                Should -Not -BeNullOrEmpty
        }
    }

    # -----------------------------------------------------------------
    # Suffix generation logic (verified via source analysis)
    # -----------------------------------------------------------------
    Context "Suffix generation" {
        It "first backup of the day has no suffix" {
            # The initial BackupName has no suffix character
            $Content | Should -Match '\$BackupName = "\$\{Today\}_daaf_backup"'
        }

        It "generates suffix 'a' for second backup (when unsuffixed exists)" {
            # SuffixNum starts at 0 => [char](97 + 0) = 'a'
            $Content | Should -Match '\[char\]\(97 \+ \$SuffixNum\)'
            # Starting SuffixNum is 0
            $Content | Should -Match '\$SuffixNum = 0'
        }

        It "increments suffix for subsequent backups" {
            $Content | Should -Match '\$SuffixNum\+\+'
        }

        It "handles suffix exhaustion (a-z all used)" {
            $Content | Should -Match '\$SuffixNum -ge 26'
            $Content | Should -Match 'Too many backups for today \(26 max\)'
        }
    }

    # -----------------------------------------------------------------
    # Integrity verification
    # -----------------------------------------------------------------
    Context "Integrity verification" {
        It "backup includes size verification" {
            $Content | Should -Match 'Size verification'
            # Compares source vs backup byte counts
            $Content | Should -Match '\$SourceSizeKB'
            $Content | Should -Match '\$BackupSizeKB'
        }

        It "backup includes file count check" {
            $Content | Should -Match '\$FileCount'
            # Verifies FileCount is non-zero
            $Content | Should -Match '\$FileCount -eq 0'
        }

        It "size comparison uses 1% tolerance" {
            $Content | Should -Match '\$SourceSizeKB / 100'
            $Content | Should -Match '\$ToleranceKB'
        }
    }

    # -----------------------------------------------------------------
    # Disk space pre-check
    # -----------------------------------------------------------------
    Context "Disk space" {
        It "checks available disk space before backup" {
            $Content | Should -Match 'System\.IO\.DriveInfo'
            $Content | Should -Match 'AvailableFreeSpace'
        }

        It "adds 10% buffer to required space" {
            $Content | Should -Match '\$VolumeSizeKB \* 110 / 100'
        }

        It "aborts with clear message when space insufficient" {
            $Content | Should -Match 'Insufficient disk space for backup'
            $Content | Should -Match '\$AvailableKB -lt \$RequiredKB'
        }
    }
}
