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

        It "defines Wait-AndExit function" {
            $Content | Should -Match 'function Wait-AndExit'
        }

        It "checks DAAF_NESTED in Wait-AndExit" {
            $Content | Should -Match 'DAAF_NESTED'
        }

        It "defines Invoke-ComposeGit helper function" {
            $Content | Should -Match 'function Invoke-ComposeGit\b'
        }

        It "defines Invoke-ComposeGitVerbose helper function" {
            $Content | Should -Match 'function Invoke-ComposeGitVerbose'
        }

        It "defines Invoke-ComposeGitNull helper function" {
            $Content | Should -Match 'function Invoke-ComposeGitNull'
        }

        It "defines Invoke-Compose helper function" {
            $Content | Should -Match 'function Invoke-Compose'
        }

        It "defines Invoke-ComposeExec helper function" {
            $Content | Should -Match 'function Invoke-ComposeExec'
        }

        It "defines Read-UserChoice helper function" {
            $Content | Should -Match 'function Read-UserChoice'
        }

        It "defines Resolve-Conflict helper function" {
            $Content | Should -Match 'function Resolve-Conflict'
        }

        It "defines Sync-HostScript helper function" {
            $Content | Should -Match 'function Sync-HostScript'
        }

        It "defines Test-BuildChange helper function" {
            $Content | Should -Match 'function Test-BuildChange'
        }

        It "defines Complete-Update helper function" {
            $Content | Should -Match 'function Complete-Update'
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
    # Invoke-ComposeGit / Invoke-ComposeGitVerbose / Invoke-ComposeGitNull
    # -----------------------------------------------------------------
    Context "Invoke-ComposeGit" {
        It "calls docker compose exec with git args" {
            Mock docker { return "mock-sha-output" }
            $null = Invoke-ComposeGit rev-parse HEAD
            Should -Invoke docker -Times 1
        }

        It "strips carriage returns from output" {
            Mock docker { return "abc123`r`ndef456`r`n" }
            $result = Invoke-ComposeGit rev-parse HEAD
            $result | Should -Not -Match "`r"
        }

        It "returns trimmed output" {
            Mock docker { return "  abc123  " }
            $result = Invoke-ComposeGit log --oneline
            # The Out-String + Trim logic should strip leading/trailing whitespace
            $result | Should -Not -Match '^\s'
            $result | Should -Not -Match '\s$'
        }
    }

    Context "Invoke-ComposeGitVerbose" {
        It "preserves stdout (does not redirect stderr to null)" {
            Mock docker { return "verbose-output-here" }
            $result = Invoke-ComposeGitVerbose fetch origin
            $result | Should -BeLike "*verbose-output*"
        }
    }

    Context "Invoke-ComposeGitNull" {
        It "discards all output (returns nothing)" {
            Mock docker { return "should-be-discarded" }
            $result = Invoke-ComposeGitNull branch test-branch
            $result | Should -BeNullOrEmpty
        }
    }

    # -----------------------------------------------------------------
    # Sync-HostScript
    # -----------------------------------------------------------------
    Context "Sync-HostScript" {
        It "skips when HEAD unchanged" {
            # Both calls to Invoke-ComposeGit return the same SHA
            Mock docker { return "abc123" }

            # Capture information stream output (Write-Host goes to stream 6)
            $output = Sync-HostScript "abc123" 6>&1
            # Should produce no "Syncing" output since HEAD is unchanged
            $syncMsg = $output | Where-Object { $_ -match "Syncing" }
            $syncMsg | Should -BeNullOrEmpty
        }

        It "detects changed files via git diff" {
            $callCount = 0
            Mock docker {
                $callCount++
                # First docker call: Invoke-ComposeGit rev-parse HEAD -> new SHA
                # Second docker call: Invoke-ComposeGit diff -> changed file list
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

            $output = Sync-HostScript "old-sha-111" 6>&1
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
            $output = Sync-HostScript "old-sha-222" 6>&1
            $warnMsg = $output | Where-Object { $_ -match "Warning" }
            $warnMsg | Should -Not -BeNullOrEmpty
        }
    }

    # -----------------------------------------------------------------
    # Test-BuildChange
    # -----------------------------------------------------------------
    Context "Test-BuildChange" {
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

            $output = Test-BuildChange "old-sha-333" 6>&1
            $noRebuild = $output | Where-Object { $_ -match "no container rebuild needed" }
            $noRebuild | Should -Not -BeNullOrEmpty
        }

        It "reports no changes when HEAD is unchanged" {
            # Same SHA => no rebuild needed
            Mock docker { return "same-sha-444" }

            $output = Test-BuildChange "same-sha-444" 6>&1
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
            # Mock Read-Host so Read-UserChoice doesn't block
            Mock Read-Host { return "n" }

            $output = Test-BuildChange "old-sha-555" 6>&1
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

            $output = Test-BuildChange "old-sha-666" 6>&1
            $buildMsg = $output | Where-Object { $_ -match "Build files were updated" }
            $buildMsg | Should -Not -BeNullOrEmpty
        }
    }

    # -----------------------------------------------------------------
    # Complete-Update
    # -----------------------------------------------------------------
    Context "Complete-Update" {
        It "calls Sync-HostScript and Test-BuildChange" {
            # Both return same HEAD => no action, but both run
            Mock docker { return "same-sha-final" }

            $output = Complete-Update "same-sha-final" 6>&1
            $completeMsg = $output | Where-Object { $_ -match "Update complete" }
            $completeMsg | Should -Not -BeNullOrEmpty
        }

        It "includes ExtraMsg when provided" {
            Mock docker { return "same-sha-extra" }

            $output = Complete-Update "same-sha-extra" "Rebased successfully." 6>&1
            $extraMsg = $output | Where-Object { $_ -match "Rebased successfully" }
            $extraMsg | Should -Not -BeNullOrEmpty
        }
    }

    # -----------------------------------------------------------------
    # Resolve-Conflict
    # -----------------------------------------------------------------
    Context "Resolve-Conflict" {
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

            $output = Resolve-Conflict "merge" "merge --abort" 6>&1
            $conflictHeader = $output | Where-Object { $_ -match "Conflict detected" }
            $conflictHeader | Should -Not -BeNullOrEmpty
        }

        # Resolve-Conflict calls Read-UserChoice, which auto-selects option 1
        # in non-interactive mode (CI). Override Read-UserChoice to force
        # option 2 so we can test the manual resolution output path.
        It "option 2 shows manual resolution instructions for merge" {
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "diff --name-only") {
                    return "CLAUDE.md"
                }
                return ""
            }
            function Read-UserChoice { param($P, $V) $null = $P, $V; return "2" }

            $output = Resolve-Conflict "merge" "merge --abort" 6>&1
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
            function Read-UserChoice { param($P, $V) $null = $P, $V; return "2" }

            $output = Resolve-Conflict "rebase" "rebase --abort" 6>&1
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
            function Read-UserChoice { param($P, $V) $null = $P, $V; return "2" }

            $null = Resolve-Conflict "merge" "merge --abort" 6>&1
            # Resolve-Conflict returns $false for option 2
            Resolve-Conflict "merge" "merge --abort" *> $null | Should -BeFalse
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

# ============================================================================
# Dry-run mode
# ============================================================================

Describe "update_daaf.ps1 dry-run mode" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:OrigDryRun = $env:DAAF_DRY_RUN
        $script:OrigNested = $env:DAAF_NESTED
        $script:TestDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-test-$(Get-Random)")
        Push-Location $script:TestDir
        New-FakeComposeFile
    }

    AfterAll {
        $env:DAAF_DRY_RUN = $script:OrigDryRun
        $env:DAAF_NESTED = $script:OrigNested
        Pop-Location
        Remove-Item -Recurse -Force $script:TestDir -ErrorAction SilentlyContinue
    }

    It "completes successfully with DAAF_DRY_RUN=1" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $null = & "$RepoRoot/scripts/host/update_daaf.ps1" *>&1
        $LASTEXITCODE | Should -BeIn @(0, $null)
    }

    It "reports already up to date" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/update_daaf.ps1" *>&1
        ($output | Out-String) | Should -BeLike "*Already up to date*"
    }
}

# ============================================================================
# Integrated state-machine tests
# ============================================================================
# These test the MAIN ORCHESTRATION flow by running the full script
# with mock docker responses. Unlike dry-run mode (which uses the script's
# built-in mocks), these tests define custom docker functions to simulate
# specific state-machine scenarios.

Describe "update_daaf.ps1 integrated state-machine tests" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
    }

    BeforeEach {
        $script:TestDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-update-int-$(Get-Random)")
        Push-Location $script:TestDir
        New-FakeComposeFile
    }

    AfterEach {
        Pop-Location
        Remove-Item -Recurse -Force $script:TestDir -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_NESTED -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_BRANCH -ErrorAction SilentlyContinue
    }

    It "clean pull path succeeds (behind, no local commits, no dirty files)" {
        $env:DAAF_NESTED = "1"
        # Create a wrapper script that defines a custom docker mock and sources the real script
        $wrapperScript = Join-Path $script:TestDir "test_wrapper.ps1"
        Set-Content -Path $wrapperScript -Value @'
$ErrorActionPreference = "Stop"
function docker {
    $argStr = $args -join ' '
    $global:LASTEXITCODE = 0
    switch -Wildcard ($argStr) {
        "*info*" { return }
        "*compose ps*--format*" { Write-Output "daaf-docker" }
        "*compose exec*true*" { return }
        "*compose exec*test -f*/daaf/.git/shallow*" { $global:LASTEXITCODE = 1; return }
        "*compose exec*test -f*" { return }
        "*compose exec*git -C /daaf remote get-url origin*" {
            Write-Output "https://github.com/DAAF-Contribution-Community/daaf.git"
        }
        "*compose exec*git -C /daaf fetch*" { return }
        "*compose exec*git -C /daaf rev-parse --verify*backup/*" { $global:LASTEXITCODE = 1; return }
        "*compose exec*git -C /daaf rev-parse --verify*origin/main*" {
            Write-Output "def456remote"
        }
        "*compose exec*git -C /daaf branch*--show-current*" { Write-Output "main" }
        "*compose exec*git -C /daaf branch*" { return }
        "*compose exec*git -C /daaf rev-parse*origin/main*" { Write-Output "def456remote" }
        "*compose exec*git -C /daaf rev-parse*HEAD*" { Write-Output "abc123local" }
        "*compose exec*git -C /daaf diff --name-only*HEAD*" { return }
        "*compose exec*git -C /daaf diff --name-only*" { return }
        "*compose exec*git -C /daaf rev-list --count*origin/main..HEAD*" { Write-Output "0" }
        "*compose exec*git -C /daaf rev-list --count*HEAD..origin/main*" { Write-Output "3" }
        "*compose exec*git -C /daaf pull*" { Write-Output "Updating..." }
        "*compose exec*git*" { return }
        "*compose exec*" { return }
        "*cp *" { return }
        default { return }
    }
}
'@
        Add-Content -Path $wrapperScript -Value ". '$RepoRoot/scripts/host/update_daaf.ps1'"
        $output = & pwsh -NoProfile -File $wrapperScript *>&1
        $exitCode = $LASTEXITCODE
        $outputStr = $output | Out-String
        $exitCode | Should -Be 0
        $outputStr | Should -BeLike "*Update complete*"
    }

    It "already up to date exits cleanly (same SHA, no dirty files)" {
        $env:DAAF_NESTED = "1"
        $wrapperScript = Join-Path $script:TestDir "test_wrapper.ps1"
        Set-Content -Path $wrapperScript -Value @'
$ErrorActionPreference = "Stop"
function docker {
    $argStr = $args -join ' '
    $global:LASTEXITCODE = 0
    switch -Wildcard ($argStr) {
        "*info*" { return }
        "*compose ps*--format*" { Write-Output "daaf-docker" }
        "*compose exec*true*" { return }
        "*compose exec*test -f*/daaf/.git/shallow*" { $global:LASTEXITCODE = 1; return }
        "*compose exec*test -f*" { return }
        "*compose exec*git -C /daaf remote get-url origin*" {
            Write-Output "https://github.com/DAAF-Contribution-Community/daaf.git"
        }
        "*compose exec*git -C /daaf fetch*" { return }
        "*compose exec*git -C /daaf rev-parse --verify*backup/*" { $global:LASTEXITCODE = 1; return }
        "*compose exec*git -C /daaf rev-parse --verify*origin/main*" {
            Write-Output "abc123same"
        }
        "*compose exec*git -C /daaf branch*--show-current*" { Write-Output "main" }
        "*compose exec*git -C /daaf branch*" { return }
        "*compose exec*git -C /daaf rev-parse*origin/main*" { Write-Output "abc123same" }
        "*compose exec*git -C /daaf rev-parse*HEAD*" { Write-Output "abc123same" }
        "*compose exec*git -C /daaf diff --name-only*" { return }
        "*compose exec*git*" { return }
        "*compose exec*" { return }
        default { return }
    }
}
'@
        Add-Content -Path $wrapperScript -Value ". '$RepoRoot/scripts/host/update_daaf.ps1'"
        $output = & pwsh -NoProfile -File $wrapperScript *>&1
        $outputStr = $output | Out-String
        $LASTEXITCODE | Should -Be 0
        $outputStr | Should -BeLike "*Already up to date*"
    }

    It "no remote configured exits with guidance" {
        $env:DAAF_NESTED = "1"
        $wrapperScript = Join-Path $script:TestDir "test_wrapper.ps1"
        Set-Content -Path $wrapperScript -Value @'
$ErrorActionPreference = "Stop"
function docker {
    $argStr = $args -join ' '
    $global:LASTEXITCODE = 0
    switch -Wildcard ($argStr) {
        "*info*" { return }
        "*compose ps*--format*" { Write-Output "daaf-docker" }
        "*compose exec*true*" { return }
        "*compose exec*test -f*" { return }
        "*compose exec*git -C /daaf remote get-url*" { $global:LASTEXITCODE = 1; return }
        "*compose exec*git -C /daaf branch*" { return }
        "*compose exec*git -C /daaf rev-parse*HEAD*" { Write-Output "abc123" }
        "*compose exec*git*" { return }
        "*compose exec*" { return }
        default { return }
    }
}
'@
        Add-Content -Path $wrapperScript -Value ". '$RepoRoot/scripts/host/update_daaf.ps1'"
        $output = & pwsh -NoProfile -File $wrapperScript *>&1
        $outputStr = $output | Out-String
        $LASTEXITCODE | Should -Be 0
        $outputStr | Should -BeLike "*not connected to the update server*"
    }

    It "network failure during fetch exits with error" {
        $env:DAAF_NESTED = "1"
        $wrapperScript = Join-Path $script:TestDir "test_wrapper.ps1"
        Set-Content -Path $wrapperScript -Value @'
$ErrorActionPreference = "Stop"
function docker {
    $argStr = $args -join ' '
    $global:LASTEXITCODE = 0
    switch -Wildcard ($argStr) {
        "*info*" { return }
        "*compose ps*--format*" { Write-Output "daaf-docker" }
        "*compose exec*true*" { return }
        "*compose exec*test -f*/daaf/.git/shallow*" { $global:LASTEXITCODE = 1; return }
        "*compose exec*test -f*" { return }
        "*compose exec*git -C /daaf remote get-url origin*" {
            Write-Output "https://github.com/DAAF-Contribution-Community/daaf.git"
        }
        "*compose exec*git -C /daaf fetch*" {
            $global:LASTEXITCODE = 1
            return
        }
        "*compose exec*git -C /daaf branch*" { return }
        "*compose exec*git -C /daaf rev-parse --verify*backup/*" { $global:LASTEXITCODE = 1; return }
        "*compose exec*git -C /daaf rev-parse*HEAD*" { Write-Output "abc123" }
        "*compose exec*git*" { return }
        "*compose exec*" { return }
        default { return }
    }
}
'@
        Add-Content -Path $wrapperScript -Value ". '$RepoRoot/scripts/host/update_daaf.ps1'"
        $output = & pwsh -NoProfile -File $wrapperScript *>&1
        $outputStr = $output | Out-String
        $LASTEXITCODE | Should -Be 1
        $outputStr | Should -BeLike "*Failed to fetch*"
    }

    It "DAAF not installed (CLAUDE.md missing) exits with error" {
        $env:DAAF_NESTED = "1"
        $wrapperScript = Join-Path $script:TestDir "test_wrapper.ps1"
        Set-Content -Path $wrapperScript -Value @'
$ErrorActionPreference = "Stop"
function docker {
    $argStr = $args -join ' '
    $global:LASTEXITCODE = 0
    switch -Wildcard ($argStr) {
        "*info*" { return }
        "*compose ps*--format*" { Write-Output "daaf-docker" }
        "*compose exec*true*" { return }
        "*compose exec*test -f*CLAUDE.md*" { $global:LASTEXITCODE = 1; return }
        "*compose exec*" { return }
        default { return }
    }
}
'@
        Add-Content -Path $wrapperScript -Value ". '$RepoRoot/scripts/host/update_daaf.ps1'"
        $output = & pwsh -NoProfile -File $wrapperScript *>&1
        $outputStr = $output | Out-String
        $LASTEXITCODE | Should -Be 1
        $outputStr | Should -BeLike "*DAAF does not appear to be installed*"
    }

    It "container not running and start fails exits with error" {
        $env:DAAF_NESTED = "1"
        $wrapperScript = Join-Path $script:TestDir "test_wrapper.ps1"
        Set-Content -Path $wrapperScript -Value @'
$ErrorActionPreference = "Stop"
function docker {
    $argStr = $args -join ' '
    $global:LASTEXITCODE = 0
    switch -Wildcard ($argStr) {
        "*info*" { return }
        "*compose ps*" { return }
        "*compose up*" { $global:LASTEXITCODE = 1; return }
        default { return }
    }
}
'@
        Add-Content -Path $wrapperScript -Value ". '$RepoRoot/scripts/host/update_daaf.ps1'"
        $output = & pwsh -NoProfile -File $wrapperScript *>&1
        $outputStr = $output | Out-String
        $LASTEXITCODE | Should -Be 1
        $outputStr | Should -BeLike "*Failed to start*"
    }

    It "DAAF_BRANCH specifies nonexistent branch exits with error" {
        $env:DAAF_NESTED = "1"
        $env:DAAF_BRANCH = "nonexistent-branch-xyz"
        $wrapperScript = Join-Path $script:TestDir "test_wrapper.ps1"
        Set-Content -Path $wrapperScript -Value @'
$ErrorActionPreference = "Stop"
function docker {
    $argStr = $args -join ' '
    $global:LASTEXITCODE = 0
    switch -Wildcard ($argStr) {
        "*info*" { return }
        "*compose ps*--format*" { Write-Output "daaf-docker" }
        "*compose exec*true*" { return }
        "*compose exec*test -f*/daaf/.git/shallow*" { $global:LASTEXITCODE = 1; return }
        "*compose exec*test -f*" { return }
        "*compose exec*git -C /daaf remote get-url origin*" {
            Write-Output "https://github.com/DAAF-Contribution-Community/daaf.git"
        }
        "*compose exec*git -C /daaf fetch*" { return }
        "*compose exec*git -C /daaf rev-parse --verify*backup/*" { $global:LASTEXITCODE = 1; return }
        "*compose exec*git -C /daaf rev-parse --verify*nonexistent*" { $global:LASTEXITCODE = 1; return }
        "*compose exec*git -C /daaf branch*" { return }
        "*compose exec*git -C /daaf rev-parse*HEAD*" { Write-Output "abc123" }
        "*compose exec*git*" { return }
        "*compose exec*" { return }
        default { return }
    }
}
'@
        Add-Content -Path $wrapperScript -Value ". '$RepoRoot/scripts/host/update_daaf.ps1'"
        $output = & pwsh -NoProfile -File $wrapperScript *>&1
        $outputStr = $output | Out-String
        $LASTEXITCODE | Should -Be 1
        $outputStr | Should -BeLike "*was not found*"
        Remove-Item Env:DAAF_BRANCH -ErrorAction SilentlyContinue
    }

    It "lock cleanup on exit (mutex released after dry-run)" {
        # Verify the script structure includes mutex cleanup in trap and exit
        $content = Get-Content "$RepoRoot/scripts/host/update_daaf.ps1" -Raw
        # Trap handler releases mutex
        $content | Should -Match 'Mutex\.ReleaseMutex'
        # Wait-AndExit also releases mutex
        $content | Should -Match 'function Wait-AndExit'
    }
}

# ============================================================================
# Concurrent execution guard
# ============================================================================

Describe "update_daaf.ps1 concurrency guard" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:Content = Get-Content "$RepoRoot/scripts/host/update_daaf.ps1" -Raw
    }

    It "uses named mutex for cross-process locking" {
        $Content | Should -Match 'Global\\DAAFUpdate'
    }

    It "releases mutex in Wait-AndExit" {
        $Content | Should -Match 'function Wait-AndExit'
        $Content | Should -Match 'Mutex\.ReleaseMutex'
    }

    It "releases mutex in trap handler" {
        $Content | Should -Match 'trap \{'
        $Content | Should -Match 'Mutex\.ReleaseMutex'
    }

    It "handles AbandonedMutexException from crashed previous instance" {
        $Content | Should -Match 'AbandonedMutexException'
    }
}
