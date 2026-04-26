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

        It "defines Pause-For-User function" {
            $Content | Should -Match 'function Pause-For-User'
        }

        It "checks DAAF_NESTED in Pause-For-User" {
            $Content | Should -Match 'DAAF_NESTED'
        }

        It "defines Prompt-Choice helper function" {
            $Content | Should -Match 'function Prompt-Choice'
        }

        It "defines Container-Git helper function" {
            $Content | Should -Match 'function Container-Git\b'
        }

        It "defines Container-Git-Verbose helper function" {
            $Content | Should -Match 'function Container-Git-Verbose'
        }

        It "defines Container-Exec helper function" {
            $Content | Should -Match 'function Container-Exec'
        }

        It "defines Container-Shell helper function" {
            $Content | Should -Match 'function Container-Shell\b'
        }

        It "defines Container-Shell-Verbose helper function" {
            $Content | Should -Match 'function Container-Shell-Verbose'
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
    # Container-Git
    # -----------------------------------------------------------------
    Context "Container-Git" {
        It "executes git command in container" {
            Mock docker { return "mock-sha-output" }
            $result = Container-Git rev-parse HEAD
            Should -Invoke docker -Times 1
        }

        It "strips carriage returns from output" {
            Mock docker { return "abc123`r`ndef456`r`n" }
            $result = Container-Git log --oneline
            $result | Should -Not -Match "`r"
        }

        It "returns trimmed output" {
            Mock docker { return "  abc123  " }
            $result = Container-Git rev-parse HEAD
            $result | Should -Not -Match '^\s'
            $result | Should -Not -Match '\s$'
        }
    }

    # -----------------------------------------------------------------
    # Container-Git-Verbose
    # -----------------------------------------------------------------
    Context "Container-Git-Verbose" {
        It "preserves output content" {
            Mock docker { return "verbose-fetch-progress" }
            $result = Container-Git-Verbose fetch origin
            $result | Should -BeLike "*verbose-fetch*"
        }
    }

    # -----------------------------------------------------------------
    # Container-Exec
    # -----------------------------------------------------------------
    Context "Container-Exec" {
        It "runs arbitrary command in container" {
            Mock docker { $global:LASTEXITCODE = 0 }
            Container-Exec test -f /daaf/CLAUDE.md
            Should -Invoke docker -Times 1
            $LASTEXITCODE | Should -Be 0
        }
    }

    # -----------------------------------------------------------------
    # Container-Shell / Container-Shell-Verbose
    # -----------------------------------------------------------------
    Context "Container-Shell" {
        It "runs shell command and returns string" {
            Mock docker { return "shell-output-here" }
            $result = Container-Shell "echo hello"
            $result | Should -BeLike "*shell-output*"
        }

        It "strips carriage returns" {
            Mock docker { return "line1`r`nline2`r`n" }
            $result = Container-Shell "ls /daaf"
            $result | Should -Not -Match "`r"
        }
    }

    Context "Container-Shell-Verbose" {
        It "returns output including stderr content" {
            Mock docker { return "verbose-shell-output" }
            $result = Container-Shell-Verbose "ls -la /daaf"
            $result | Should -BeLike "*verbose-shell*"
        }
    }

    # -----------------------------------------------------------------
    # Prompt-Choice
    # -----------------------------------------------------------------
    Context "Prompt-Choice" {
        It "returns valid selection" {
            Mock Read-Host { return "y" }
            $result = Prompt-Choice "Choose [y/n]" @("y", "n")
            $result | Should -Be "y"
        }

        It "normalizes input to lowercase" {
            Mock Read-Host { return "Y" }
            $result = Prompt-Choice "Choose [y/n]" @("y", "n")
            $result | Should -Be "y"
        }

        It "trims whitespace from input" {
            Mock Read-Host { return "  n  " }
            $result = Prompt-Choice "Choose [y/n]" @("y", "n")
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
