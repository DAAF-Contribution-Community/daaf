# ============================================================================
# Pester tests for migrate_daaf.ps1 -- DAAF Migration Script (Windows)
# ============================================================================

Describe "migrate_daaf.ps1" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
    }

    Context "Syntax validation" {
        It "parses without errors" {
            $errors = Test-ScriptSyntax -Path "$RepoRoot/scripts/host/migrate_daaf.ps1"
            $errors | Should -BeNullOrEmpty
        }
    }

    Context "Script structure" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/migrate_daaf.ps1" -Raw
        }

        It "sets ErrorActionPreference to Stop" {
            $Content | Should -Match '\$ErrorActionPreference\s*=\s*[''"]Stop[''"]'
        }

        It "defines Wait-ForUser function" {
            $Content | Should -Match 'function Wait-ForUser'
        }

        It "checks DAAF_NESTED in Wait-ForUser" {
            $Content | Should -Match 'DAAF_NESTED'
        }

        It "defines Read-UserChoice helper function" {
            $Content | Should -Match 'function Read-UserChoice'
        }

        It "defines Invoke-ContainerGit helper function" {
            $Content | Should -Match 'function Invoke-ContainerGit\b'
        }

        It "defines Invoke-ContainerGitVerbose helper function" {
            $Content | Should -Match 'function Invoke-ContainerGitVerbose'
        }

        It "defines Invoke-ContainerExec helper function" {
            $Content | Should -Match 'function Invoke-ContainerExec'
        }

        It "defines Invoke-ContainerShell helper function" {
            $Content | Should -Match 'function Invoke-ContainerShell\b'
        }

        It "defines Invoke-ContainerShellVerbose helper function" {
            $Content | Should -Match 'function Invoke-ContainerShellVerbose'
        }

        It "has a trap handler for unexpected failures" {
            $Content | Should -Match 'trap \{'
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

        It "supports DAAF_BRANCH environment variable" {
            $Content | Should -Match 'DAAF_BRANCH'
        }

        It "detects non-interactive mode" {
            $Content | Should -Match 'NonInteractive'
        }

        It "detects Era 1 (clone-based) installations" {
            $Content | Should -Match 'clone-based installation'
        }

        It "detects Era 2 (ZIP-based) installations" {
            $Content | Should -Match 'ZIP-based installation'
        }

        It "performs a backup before migration" {
            $Content | Should -Match 'backup_daaf\.ps1'
        }

        It "handles fork detection" {
            $Content | Should -Match 'IsFork'
        }

        It "performs graft for ERA 2 installations" {
            $Content | Should -Match 'replace --graft'
        }

        It "fixes file permissions for ZIP downloads" {
            $Content | Should -Match 'Fixing file permissions'
        }

        It "sets upstream tracking branch" {
            $Content | Should -Match 'set-upstream-to=origin/main'
        }

        It "offers to run update after migration" {
            $Content | Should -Match 'Run update'
        }

        It "sets TLS 1.2 for GitHub downloads" {
            $Content | Should -Match 'Tls12'
        }

        It "claims idempotency in its header" {
            $Content | Should -Match 'idempotent'
        }
    }
}

# ============================================================================
# Behavioral tests -- dot-source the script and call functions directly
# ============================================================================

Describe "migrate_daaf.ps1 behavioral tests" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"

        $env:DAAF_TEST_MODE = "1"
        . "$RepoRoot/scripts/host/migrate_daaf.ps1"

        # Declare a docker function so Pester can mock it
        function docker {}
    }

    AfterAll {
        Remove-Item Env:DAAF_TEST_MODE -ErrorAction SilentlyContinue
    }

    # -----------------------------------------------------------------
    # Invoke-ContainerGit
    # -----------------------------------------------------------------
    Context "Invoke-ContainerGit" {
        It "executes git command in container" {
            Mock docker { return "mock-sha-output" }
            $null = Invoke-ContainerGit rev-parse HEAD
            Should -Invoke docker -Times 1
        }

        It "strips carriage returns from output" {
            Mock docker { return "abc123`r`ndef456`r`n" }
            $result = Invoke-ContainerGit log --oneline
            $result | Should -Not -Match "`r"
        }

        It "returns trimmed output" {
            Mock docker { return "  abc123  " }
            $result = Invoke-ContainerGit rev-parse HEAD
            $result | Should -Not -Match '^\s'
            $result | Should -Not -Match '\s$'
        }
    }

    # -----------------------------------------------------------------
    # Invoke-ContainerGitVerbose
    # -----------------------------------------------------------------
    Context "Invoke-ContainerGitVerbose" {
        It "preserves output content" {
            Mock docker { return "verbose-fetch-progress" }
            $result = Invoke-ContainerGitVerbose fetch origin
            $result | Should -BeLike "*verbose-fetch*"
        }
    }

    # -----------------------------------------------------------------
    # Invoke-ContainerExec
    # -----------------------------------------------------------------
    Context "Invoke-ContainerExec" {
        It "runs arbitrary command in container" {
            Mock docker { $global:LASTEXITCODE = 0 }
            Invoke-ContainerExec test -f /daaf/CLAUDE.md
            Should -Invoke docker -Times 1
            $LASTEXITCODE | Should -Be 0
        }
    }

    # -----------------------------------------------------------------
    # Invoke-ContainerShell / Invoke-ContainerShellVerbose
    # -----------------------------------------------------------------
    Context "Invoke-ContainerShell" {
        It "runs shell command and returns string" {
            Mock docker { return "shell-output-here" }
            $result = Invoke-ContainerShell "echo hello"
            $result | Should -BeLike "*shell-output*"
        }

        It "strips carriage returns" {
            Mock docker { return "line1`r`nline2`r`n" }
            $result = Invoke-ContainerShell "ls /daaf"
            $result | Should -Not -Match "`r"
        }
    }

    Context "Invoke-ContainerShellVerbose" {
        It "returns output including stderr content" {
            Mock docker { return "verbose-shell-output" }
            $result = Invoke-ContainerShellVerbose "ls -la /daaf"
            $result | Should -BeLike "*verbose-shell*"
        }
    }

    # -----------------------------------------------------------------
    # Read-UserChoice
    # -----------------------------------------------------------------
    Context "Read-UserChoice" {
        It "returns valid selection" {
            Mock Read-Host { return "y" }
            $result = Read-UserChoice "Choose [y/n]" @("y", "n")
            $result | Should -Be "y"
        }

        It "normalizes input to lowercase" {
            Mock Read-Host { return "Y" }
            $result = Read-UserChoice "Choose [y/n]" @("y", "n")
            $result | Should -Be "y"
        }

        It "trims whitespace from input" {
            Mock Read-Host { return "  n  " }
            $result = Read-UserChoice "Choose [y/n]" @("y", "n")
            $result | Should -Be "n"
        }
    }

    # -----------------------------------------------------------------
    # Era detection patterns (verified via source analysis)
    # -----------------------------------------------------------------
    Context "Era detection patterns" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/migrate_daaf.ps1" -Raw
        }

        It "no remote indicates Era 2 (ZIP-based)" {
            # When origin URL is empty/whitespace, DetectedEra should be "2"
            $Content | Should -Match 'IsNullOrWhiteSpace\(\$OriginUrl\)'
            $Content | Should -Match '\$DetectedEra = "2"'
        }

        It "remote with upstream repo URL indicates Era 1" {
            $Content | Should -Match '\$OriginUrl -match \$Repo'
            $Content | Should -Match '\$DetectedEra = "1"'
        }

        It "idempotency: graft already in place skips graft step" {
            $Content | Should -Match 'History graft already in place'
            $Content | Should -Match '\$InitialParentCount -gt 0'
        }
    }

    # -----------------------------------------------------------------
    # Safety mechanisms
    # -----------------------------------------------------------------
    Context "Safety mechanisms" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/migrate_daaf.ps1" -Raw
        }

        It "uses System.Threading.Mutex for locking" {
            $Content | Should -Match 'System\.Threading\.Mutex'
            $Content | Should -Not -Match 'flock'
        }

        It "mutex uses Global scope for cross-process visibility" {
            $Content | Should -Match 'Global\\DAAFMigrate'
        }

        It "backup call precedes destructive operations" {
            # backup_daaf.ps1 is called in section 3, before era detection/graft in sections 5-6
            $backupPos = $Content.IndexOf('backup_daaf.ps1')
            $graftPos = $Content.IndexOf('replace --graft')
            $backupPos | Should -BeLessThan $graftPos
        }

        It "trap handler releases mutex on failure" {
            $Content | Should -Match 'trap \{'
            $Content | Should -Match 'Mutex\.ReleaseMutex'
        }
    }
}
