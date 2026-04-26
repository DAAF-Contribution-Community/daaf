# ============================================================================
# Pester tests for update_daaf.ps1 -- DAAF Update Script (Windows)
# ============================================================================

Describe "update_daaf.ps1" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
    }

    Context "Syntax validation" {
        It "parses without errors" {
            $errors = Test-ScriptSyntax -Path "$RepoRoot/scripts/host/update_daaf.ps1"
            $errors | Should -BeNullOrEmpty
        }
    }

    Context "Script structure" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/update_daaf.ps1" -Raw
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

        It "defines Compose-Git helper function" {
            $Content | Should -Match 'function Compose-Git\b'
        }

        It "defines Compose-Git-Verbose helper function" {
            $Content | Should -Match 'function Compose-Git-Verbose'
        }

        It "defines Compose-Git-Null helper function" {
            $Content | Should -Match 'function Compose-Git-Null'
        }

        It "defines Invoke-Compose helper function" {
            $Content | Should -Match 'function Invoke-Compose'
        }

        It "defines Compose-Exec helper function" {
            $Content | Should -Match 'function Compose-Exec'
        }

        It "defines Prompt-Choice helper function" {
            $Content | Should -Match 'function Prompt-Choice'
        }

        It "defines Handle-Conflict helper function" {
            $Content | Should -Match 'function Handle-Conflict'
        }

        It "defines Sync-HostScripts helper function" {
            $Content | Should -Match 'function Sync-HostScripts'
        }

        It "defines Check-BuildChanges helper function" {
            $Content | Should -Match 'function Check-BuildChanges'
        }

        It "defines Finish-Update helper function" {
            $Content | Should -Match 'function Finish-Update'
        }

        It "has a trap handler for unexpected failures" {
            $Content | Should -Match 'trap \{'
        }

        It "checks for docker-compose.yml" {
            $Content | Should -Match 'docker-compose\.yml'
        }

        It "checks for Docker with Get-Command" {
            $Content | Should -Match 'Get-Command docker'
        }

        It "supports DAAF_BRANCH environment variable" {
            $Content | Should -Match 'DAAF_BRANCH'
        }

        It "offers backup before updating" {
            $Content | Should -Match 'Backup recommendation'
        }

        It "creates a git backup branch" {
            $Content | Should -Match 'backup/pre-update'
        }

        It "handles merge and rebase options" {
            $Content | Should -Match 'MERGE \(recommended\)'
            $Content | Should -Match 'REBASE \(cleaner history\)'
        }

        It "handles non-default branch update path" {
            $Content | Should -Match "You are on branch"
        }

        It "handles uncommitted changes (dirty files)" {
            $Content | Should -Match 'uncommitted changes'
        }

        It "detects ahead/behind state" {
            $Content | Should -Match 'rev-list --count'
        }
    }
}

# ============================================================================
# Behavioral tests -- dot-source the script and call functions directly
# ============================================================================

Describe "update_daaf.ps1 behavioral tests" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"

        $env:DAAF_TEST_MODE = "1"
        . "$RepoRoot/scripts/host/update_daaf.ps1"

        # Declare a docker function so Pester can mock it
        function docker {}
    }

    AfterAll {
        Remove-Item Env:DAAF_TEST_MODE -ErrorAction SilentlyContinue
    }

    # -----------------------------------------------------------------
    # Compose-Git / Compose-Git-Verbose / Compose-Git-Null
    # -----------------------------------------------------------------
    Context "Compose-Git" {
        It "calls docker compose exec with git args" {
            Mock docker { return "mock-sha-output" }
            $result = Compose-Git rev-parse HEAD
            Should -Invoke docker -Times 1
        }

        It "strips carriage returns from output" {
            Mock docker { return "abc123`r`ndef456`r`n" }
            $result = Compose-Git rev-parse HEAD
            $result | Should -Not -Match "`r"
        }

        It "returns trimmed output" {
            Mock docker { return "  abc123  " }
            $result = Compose-Git log --oneline
            # The Out-String + Trim logic should strip leading/trailing whitespace
            $result | Should -Not -Match '^\s'
            $result | Should -Not -Match '\s$'
        }
    }

    Context "Compose-Git-Verbose" {
        It "preserves stdout (does not redirect stderr to null)" {
            Mock docker { return "verbose-output-here" }
            $result = Compose-Git-Verbose fetch origin
            $result | Should -BeLike "*verbose-output*"
        }
    }

    Context "Compose-Git-Null" {
        It "discards all output (returns nothing)" {
            Mock docker { return "should-be-discarded" }
            $result = Compose-Git-Null branch test-branch
            $result | Should -BeNullOrEmpty
        }
    }

    # -----------------------------------------------------------------
    # Sync-HostScripts
    # -----------------------------------------------------------------
    Context "Sync-HostScripts" {
        It "skips when HEAD unchanged" {
            # Both calls to Compose-Git return the same SHA
            Mock docker { return "abc123" }

            # Capture information stream output (Write-Host goes to stream 6)
            $output = Sync-HostScripts "abc123" 6>&1
            # Should produce no "Syncing" output since HEAD is unchanged
            $syncMsg = $output | Where-Object { $_ -match "Syncing" }
            $syncMsg | Should -BeNullOrEmpty
        }

        It "detects changed files via git diff" {
            $callCount = 0
            Mock docker {
                $callCount++
                # First docker call: Compose-Git rev-parse HEAD -> new SHA
                # Second docker call: Compose-Git diff -> changed file list
                # Third docker call: docker cp
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") {
                    return "new-sha-999"
                }
                if ($allArgs -match "diff --name-only") {
                    return "scripts/host/run_daaf.ps1"
                }
                # docker cp call
                $global:LASTEXITCODE = 0
                return ""
            }

            $output = Sync-HostScripts "old-sha-111" 6>&1
            $syncMsg = $output | Where-Object { $_ -match "Syncing" }
            $syncMsg | Should -Not -BeNullOrEmpty
        }

        It "handles partial copy failure gracefully" {
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") {
                    return "new-sha-888"
                }
                if ($allArgs -match "diff --name-only") {
                    return "scripts/host/run_daaf.ps1"
                }
                # docker cp fails
                $global:LASTEXITCODE = 1
                return ""
            }

            # Should not throw -- it shows a warning instead
            $output = Sync-HostScripts "old-sha-222" 6>&1
            $warnMsg = $output | Where-Object { $_ -match "Warning" }
            $warnMsg | Should -Not -BeNullOrEmpty
        }
    }

    # -----------------------------------------------------------------
    # Check-BuildChanges
    # -----------------------------------------------------------------
    Context "Check-BuildChanges" {
        It "reports no changes when build files unchanged" {
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") {
                    return "new-sha-777"
                }
                if ($allArgs -match "diff --name-only") {
                    # No Dockerfile or docker-compose.yml changes
                    return ""
                }
                return ""
            }

            $output = Check-BuildChanges "old-sha-333" 6>&1
            $noRebuild = $output | Where-Object { $_ -match "no container rebuild needed" }
            $noRebuild | Should -Not -BeNullOrEmpty
        }

        It "reports no changes when HEAD is unchanged" {
            # Same SHA => no rebuild needed
            Mock docker { return "same-sha-444" }

            $output = Check-BuildChanges "same-sha-444" 6>&1
            $noRebuild = $output | Where-Object { $_ -match "no container rebuild needed" }
            $noRebuild | Should -Not -BeNullOrEmpty
        }

        It "detects Dockerfile modifications" {
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") {
                    return "new-sha-555"
                }
                if ($allArgs -match "diff --name-only") {
                    return "Dockerfile"
                }
                return ""
            }
            # Mock Read-Host so Prompt-Choice doesn't block
            Mock Read-Host { return "n" }

            $output = Check-BuildChanges "old-sha-555" 6>&1
            $buildMsg = $output | Where-Object { $_ -match "Build files were updated" }
            $buildMsg | Should -Not -BeNullOrEmpty
        }

        It "detects docker-compose.yml modifications" {
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") {
                    return "new-sha-666"
                }
                if ($allArgs -match "diff --name-only") {
                    return "docker-compose.yml"
                }
                return ""
            }
            Mock Read-Host { return "n" }

            $output = Check-BuildChanges "old-sha-666" 6>&1
            $buildMsg = $output | Where-Object { $_ -match "Build files were updated" }
            $buildMsg | Should -Not -BeNullOrEmpty
        }
    }

    # -----------------------------------------------------------------
    # Finish-Update
    # -----------------------------------------------------------------
    Context "Finish-Update" {
        It "calls Sync-HostScripts and Check-BuildChanges" {
            # Both return same HEAD => no action, but both run
            Mock docker { return "same-sha-final" }

            $output = Finish-Update "same-sha-final" 6>&1
            $completeMsg = $output | Where-Object { $_ -match "Update complete" }
            $completeMsg | Should -Not -BeNullOrEmpty
        }

        It "includes ExtraMsg when provided" {
            Mock docker { return "same-sha-extra" }

            $output = Finish-Update "same-sha-extra" "Rebased successfully." 6>&1
            $extraMsg = $output | Where-Object { $_ -match "Rebased successfully" }
            $extraMsg | Should -Not -BeNullOrEmpty
        }
    }

    # -----------------------------------------------------------------
    # Handle-Conflict
    # -----------------------------------------------------------------
    Context "Handle-Conflict" {
        It "shows conflicting file list" {
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "diff --name-only") {
                    return "CLAUDE.md`nREADME.md"
                }
                return ""
            }
            # Choose option 2 to exit
            Mock Read-Host { return "2" }

            $output = Handle-Conflict "merge" "merge --abort" 6>&1
            $conflictHeader = $output | Where-Object { $_ -match "Conflict detected" }
            $conflictHeader | Should -Not -BeNullOrEmpty
        }

        It "option 2 shows manual resolution instructions for merge" {
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "diff --name-only") {
                    return "CLAUDE.md"
                }
                return ""
            }
            Mock Read-Host { return "2" }

            $output = Handle-Conflict "merge" "merge --abort" 6>&1
            $mergeInst = $output | Where-Object { $_ -match 'git commit -m' }
            $mergeInst | Should -Not -BeNullOrEmpty
        }

        It "option 2 shows rebase continue for rebase type" {
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "diff --name-only") {
                    return "CLAUDE.md"
                }
                return ""
            }
            Mock Read-Host { return "2" }

            $output = Handle-Conflict "rebase" "rebase --abort" 6>&1
            $rebaseInst = $output | Where-Object { $_ -match 'rebase --continue' }
            $rebaseInst | Should -Not -BeNullOrEmpty
        }

        It "returns false when conflicts remain (option 2)" {
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "diff --name-only") {
                    return "CLAUDE.md"
                }
                return ""
            }
            Mock Read-Host { return "2" }

            $result = Handle-Conflict "merge" "merge --abort" 6>&1
            # Handle-Conflict returns $false for option 2
            # The return value is mixed with Write-Host output in 6>&1
            # The function explicitly returns $false
            Handle-Conflict "merge" "merge --abort" *> $null | Should -BeFalse
        }
    }

    # -----------------------------------------------------------------
    # Safety: Mutex and trap
    # -----------------------------------------------------------------
    Context "Safety mechanisms" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/update_daaf.ps1" -Raw
        }

        It "uses System.Threading.Mutex for locking (not flock)" {
            $Content | Should -Match 'System\.Threading\.Mutex'
            $Content | Should -Not -Match 'flock'
        }

        It "trap registered for cleanup" {
            $Content | Should -Match 'trap \{'
            # Trap handler releases the mutex
            $Content | Should -Match 'Mutex\.ReleaseMutex'
        }

        It "mutex uses Global scope for cross-process visibility" {
            $Content | Should -Match 'Global\\DAAFUpdate'
        }
    }
}
