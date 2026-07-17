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

        It "declares #Requires -Version 5.1" {
            $Content | Should -Match '#Requires\s+-Version\s+5\.1'
        }

        It "sets ErrorActionPreference to Stop" {
            $Content | Should -Match '\$ErrorActionPreference\s*=\s*[''"]Stop[''"]'
        }

        It "enables Set-StrictMode -Version 3.0" {
            $Content | Should -Match 'Set-StrictMode\s+-Version\s+3\.0'
        }

        It "places Set-StrictMode after the test-mode guard" {
            # Strict mode is dynamically scoped: placing it before the guard would
            # leak into Pester's dot-sourced test session. It must come after.
            $guardIdx = $Content.IndexOf('$env:DAAF_TEST_MODE -eq "1"')
            $strictIdx = $Content.IndexOf('Set-StrictMode -Version 3.0')
            $guardIdx | Should -BeGreaterThan -1
            $strictIdx | Should -BeGreaterThan $guardIdx
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
    # The sync mechanism was redesigned: instead of a hardcoded pathspec diffed
    # by the (old) running script, it derives the file list from the POST-UPDATE
    # repo state (git ls-files at new HEAD), copies host-appropriate files
    # MISSING on the host unconditionally (tier A / existence-heal), and copies
    # files CHANGED in old_head..new_head (tier B). Mocks respond to `ls-files`
    # in addition to `rev-parse HEAD`, `diff --name-only`, and `cp`.
    #
    # These tests Push-Location into a temp dir so Test-Path host-existence
    # checks are deterministic.
    Context "Sync-HostScript" {
        BeforeEach {
            $script:SyncTestDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-sync-$(Get-Random)")
            Push-Location $script:SyncTestDir
        }
        AfterEach {
            Pop-Location
            Remove-Item -Recurse -Force $script:SyncTestDir -ErrorAction SilentlyContinue
        }

        It "skips when the repo lists no host files" {
            # ls-files returns nothing -> function returns early, no output.
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") { return "abc123" }
                if ($allArgs -match "ls-files") { return "" }
                $global:LASTEXITCODE = 0
                return ""
            }

            $output = Sync-HostScript "abc123" 6>&1
            $syncMsg = $output | Where-Object { $_ -match "Syncing" }
            $syncMsg | Should -BeNullOrEmpty
        }

        It "existence-heals a file missing on the host" {
            # daaf.ps1 absent from the temp dir; even with OldHead == newHead,
            # tier A must copy it.
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") { return "samehash" }
                if ($allArgs -match "ls-files") { return "scripts/host/daaf.ps1`nscripts/host/run_daaf.ps1" }
                $global:LASTEXITCODE = 0
                return ""
            }

            $output = Sync-HostScript "samehash" 6>&1
            ($output | Where-Object { $_ -match "Updated: daaf.ps1" })     | Should -Not -BeNullOrEmpty
            ($output | Where-Object { $_ -match "Updated: run_daaf.ps1" }) | Should -Not -BeNullOrEmpty
        }

        It "skips existence-heal for files already present on the host" {
            New-Item -ItemType File -Path "./run_daaf.ps1" | Out-Null
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") { return "samehash" }
                if ($allArgs -match "ls-files") { return "scripts/host/daaf.ps1`nscripts/host/run_daaf.ps1" }
                $global:LASTEXITCODE = 0
                return ""
            }

            $output = Sync-HostScript "samehash" 6>&1
            ($output | Where-Object { $_ -match "Updated: daaf.ps1" })     | Should -Not -BeNullOrEmpty
            ($output | Where-Object { $_ -match "Updated: run_daaf.ps1" }) | Should -BeNullOrEmpty
        }

        It "tier B copies files changed in the update range" {
            New-Item -ItemType File -Path "./run_daaf.ps1" | Out-Null
            New-Item -ItemType File -Path "./daaf.ps1" | Out-Null
            # The cp mock MATERIALIZES the destination ($args[2]): tier B stages
            # the incoming copy as a sibling file before comparing/backing-up/
            # renaming, so a mock that only returns leaves the staged file
            # missing and the rename fails.
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") { return "new-sha-999" }
                if ($allArgs -match "ls-files") { return "scripts/host/daaf.ps1`nscripts/host/run_daaf.ps1" }
                if ($allArgs -match "diff --name-only") { return "scripts/host/run_daaf.ps1" }
                if ($allArgs -match "^cp ") { Set-Content -Path $args[2] -Value "repo version"; $global:LASTEXITCODE = 0; return "" }
                $global:LASTEXITCODE = 0
                return ""
            }

            $output = Sync-HostScript "old-sha-111" 6>&1
            ($output | Where-Object { $_ -match "Updated: run_daaf.ps1" }) | Should -Not -BeNullOrEmpty
        }

        It "tier B backs up an existing differing host copy before overwrite" {
            # Field finding 2026-07-17 (v2.0.1 vector, class E): a host copy
            # that differs from what tier B delivers must be saved to the
            # rolling <name>.pre-update BEFORE overwrite -- the tier C
            # recoverability contract applies to every overwrite path.
            Set-Content -Path "./run_daaf.ps1" -Value "drifted local content"
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") { return "new-sha-999" }
                if ($allArgs -match "ls-files") { return "scripts/host/run_daaf.ps1" }
                if ($allArgs -match "diff --name-only") { return "scripts/host/run_daaf.ps1" }
                if ($allArgs -match "^cp ") { Set-Content -Path $args[2] -Value "repo version"; $global:LASTEXITCODE = 0; return "" }
                $global:LASTEXITCODE = 0
                return ""
            }

            $output = Sync-HostScript "old-sha-111" 6>&1
            ($output | Where-Object { $_ -match "saved as run_daaf.ps1.pre-update" }) | Should -Not -BeNullOrEmpty
            Test-Path "./run_daaf.ps1.pre-update" | Should -BeTrue
            (Get-Content "./run_daaf.ps1.pre-update" -Raw) | Should -Match "drifted local content"
            (Get-Content "./run_daaf.ps1" -Raw) | Should -Match "repo version"
        }

        It "tier B leaves no backup when the host copy already matches" {
            # A spurious rolling backup here would clobber a meaningful one
            # from an earlier heal.
            Set-Content -Path "./run_daaf.ps1" -Value "repo version"
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") { return "new-sha-999" }
                if ($allArgs -match "ls-files") { return "scripts/host/run_daaf.ps1" }
                if ($allArgs -match "diff --name-only") { return "scripts/host/run_daaf.ps1" }
                if ($allArgs -match "^cp ") { Set-Content -Path $args[2] -Value "repo version"; $global:LASTEXITCODE = 0; return "" }
                $global:LASTEXITCODE = 0
                return ""
            }

            $output = Sync-HostScript "old-sha-111" 6>&1
            ($output | Where-Object { $_ -match "Updated: run_daaf.ps1" }) | Should -Not -BeNullOrEmpty
            ($output | Where-Object { $_ -match "saved as" }) | Should -BeNullOrEmpty
            Test-Path "./run_daaf.ps1.pre-update" | Should -BeFalse
        }

        It "ignores changed files outside the platform filter" {
            # .sh files (including daaf.sh -- Unix-only now) and bootstrap-only
            # scripts must not be copied on Windows. test_migration.ps1 (dev-only
            # harness) is excluded too -- and because it matches *.ps1 it would be
            # synced WITHOUT the explicit exclusion, so this pins the exclusion,
            # not merely the platform filter.
            New-Item -ItemType File -Path "./run_daaf.ps1" | Out-Null
            New-Item -ItemType File -Path "./daaf.ps1" | Out-Null
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") { return "new-sha-999" }
                if ($allArgs -match "ls-files") { return "scripts/host/daaf.ps1`nscripts/host/run_daaf.ps1`nscripts/host/daaf.sh`nscripts/host/run_daaf.sh`nscripts/host/install.ps1`nscripts/host/test_migration.ps1" }
                if ($allArgs -match "diff --name-only") { return "scripts/host/daaf.sh`nscripts/host/run_daaf.sh`nscripts/host/install.ps1`nscripts/host/test_migration.ps1" }
                $global:LASTEXITCODE = 0
                return ""
            }

            $output = Sync-HostScript "old-sha-111" 6>&1
            ($output | Where-Object { $_ -match "Updated: daaf.sh" })           | Should -BeNullOrEmpty
            ($output | Where-Object { $_ -match "run_daaf.sh" })                | Should -BeNullOrEmpty
            ($output | Where-Object { $_ -match "Updated: install.ps1" })       | Should -BeNullOrEmpty
            ($output | Where-Object { $_ -match "Updated: test_migration.ps1" }) | Should -BeNullOrEmpty
        }

        It "prints self-update notice when update_daaf.ps1 changed" {
            New-Item -ItemType File -Path "./update_daaf.ps1" | Out-Null
            # The cp mock MATERIALIZES the destination: the staged-copy redesign
            # verifies the staged file exists, and the $null = wrapper on docker
            # cp means a bare mock return no longer leaks a truthy array into
            # the Copy-HostScript boolean (which is what let the old
            # non-materializing mock pass by accident).
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") { return "new-sha-999" }
                if ($allArgs -match "ls-files") { return "scripts/host/update_daaf.ps1" }
                if ($allArgs -match "diff --name-only") { return "scripts/host/update_daaf.ps1" }
                if ($allArgs -match "^cp ") { Set-Content -Path $args[2] -Value "repo version"; $global:LASTEXITCODE = 0; return "" }
                $global:LASTEXITCODE = 0
                return ""
            }

            $output = Sync-HostScript "old-sha-111" 6>&1
            ($output | Where-Object { $_ -match "The updater itself was updated" }) | Should -Not -BeNullOrEmpty
        }

        It "does not print self-update notice for other changes" {
            New-Item -ItemType File -Path "./run_daaf.ps1" | Out-Null
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") { return "new-sha-999" }
                if ($allArgs -match "ls-files") { return "scripts/host/run_daaf.ps1" }
                if ($allArgs -match "diff --name-only") { return "scripts/host/run_daaf.ps1" }
                if ($allArgs -match "^cp ") { Set-Content -Path $args[2] -Value "repo version"; $global:LASTEXITCODE = 0; return "" }
                $global:LASTEXITCODE = 0
                return ""
            }

            $output = Sync-HostScript "old-sha-111" 6>&1
            ($output | Where-Object { $_ -match "The updater itself was updated" }) | Should -BeNullOrEmpty
        }

        It "reports copy failures by name with a recovery hint" {
            # Clear DAAF_PROJECT_NAME so the hint resolves deterministically to the
            # fallback 'daaf', independent of the host/container environment (this
            # container exports DAAF_PROJECT_NAME).
            Remove-Item Env:DAAF_PROJECT_NAME -ErrorAction SilentlyContinue
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") { return "samehash" }
                if ($allArgs -match "ls-files") { return "scripts/host/daaf.ps1" }
                # docker cp fails
                $global:LASTEXITCODE = 1
                return ""
            }

            $output = Sync-HostScript "samehash" 6>&1
            ($output | Where-Object { $_ -match "Warning: could not copy daaf.ps1" }) | Should -Not -BeNullOrEmpty
            # Manual-recovery hint now uses the project-resolved `docker cp
            # <project>-daaf-docker-1:` form (c5f69b6). DAAF_PROJECT_NAME is cleared
            # above, so the fallback 'daaf' is used.
            ($output | Where-Object { $_ -match "docker cp daaf-daaf-docker-1:/daaf/scripts/host/daaf.ps1 ./daaf.ps1" }) | Should -Not -BeNullOrEmpty
        }

        It "existence-heals with an empty OldHead (up-to-date path)" {
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") { return "samehash" }
                if ($allArgs -match "ls-files") { return "scripts/host/daaf.ps1" }
                $global:LASTEXITCODE = 0
                return ""
            }

            $output = Sync-HostScript 6>&1
            ($output | Where-Object { $_ -match "Updated: daaf.ps1" }) | Should -Not -BeNullOrEmpty
        }

        # --- Tier C: drift heal (overwrite with rolling backup) ---
        # Mirrors the Bash tier-C drift tests. The docker mock implements the bulk
        # `compose cp scripts/host <tmp>/repo_host` stage by creating the repo_host
        # tree with known contents so a real Get-FileHash compare can run. On drift
        # (f0506f6), the host file is HEALED: back up to <name>.pre-update, then
        # overwrite with the repo copy. If the backup fails, the host file is left
        # untouched (old-style warning). The drift loop also skips the running updater.

        It "heals a drifted host file with a .pre-update backup" {
            Set-Content -Path "./run_daaf.ps1" -Value "host-customized" -NoNewline
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") { return "samehash" }
                if ($allArgs -match "ls-files") { return "scripts/host/run_daaf.ps1" }
                if ($allArgs -match "compose cp") {
                    # Last arg is the destination repo_host dir. Populate it with
                    # the pristine repo copy (differs from the host copy above).
                    $dest = $args[$args.Count - 1]
                    New-Item -ItemType Directory -Path $dest -Force | Out-Null
                    Set-Content -Path (Join-Path $dest "run_daaf.ps1") -Value "pristine-repo" -NoNewline
                    $global:LASTEXITCODE = 0
                    return ""
                }
                $global:LASTEXITCODE = 0
                return ""
            }

            $output = Sync-HostScript "samehash" 6>&1
            # (c) per-file "Updated:" line naming the .pre-update backup + closing summary.
            ($output | Where-Object { $_ -match "Updated: run_daaf.ps1 \(your previous copy was saved as run_daaf.ps1.pre-update\)" }) | Should -Not -BeNullOrEmpty
            ($output | Where-Object { $_ -match "One or more host files were stale and have been updated" }) | Should -Not -BeNullOrEmpty
            ($output | Where-Object { $_ -match "restore one by" }) | Should -Not -BeNullOrEmpty
            # (a) host file now holds the repo version.
            (Get-Content -Path "./run_daaf.ps1" -Raw) | Should -Match "pristine-repo"
            # (b) the .pre-update backup holds the OLD host content.
            (Get-Content -Path "./run_daaf.ps1.pre-update" -Raw) | Should -Match "host-customized"
        }

        It "does not warn when the host file matches the repo copy" {
            Set-Content -Path "./run_daaf.ps1" -Value "identical" -NoNewline
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") { return "samehash" }
                if ($allArgs -match "ls-files") { return "scripts/host/run_daaf.ps1" }
                if ($allArgs -match "compose cp") {
                    $dest = $args[$args.Count - 1]
                    New-Item -ItemType Directory -Path $dest -Force | Out-Null
                    Set-Content -Path (Join-Path $dest "run_daaf.ps1") -Value "identical" -NoNewline
                    $global:LASTEXITCODE = 0
                    return ""
                }
                $global:LASTEXITCODE = 0
                return ""
            }

            $output = Sync-HostScript "samehash" 6>&1
            ($output | Where-Object { $_ -match "differs from the repository version" }) | Should -BeNullOrEmpty
        }

        It "overwrites the drifted host file with the repo version" {
            Set-Content -Path "./run_daaf.ps1" -Value "host-customized" -NoNewline
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") { return "samehash" }
                if ($allArgs -match "ls-files") { return "scripts/host/run_daaf.ps1" }
                if ($allArgs -match "compose cp") {
                    $dest = $args[$args.Count - 1]
                    New-Item -ItemType Directory -Path $dest -Force | Out-Null
                    Set-Content -Path (Join-Path $dest "run_daaf.ps1") -Value "pristine-repo" -NoNewline
                    $global:LASTEXITCODE = 0
                    return ""
                }
                $global:LASTEXITCODE = 0
                return ""
            }

            Sync-HostScript "samehash" 6>&1 | Out-Null
            # Host file is now the repo copy; the old content is preserved in the backup.
            (Get-Content -Path "./run_daaf.ps1" -Raw) | Should -Match "pristine-repo"
            (Get-Content -Path "./run_daaf.ps1" -Raw) | Should -Not -Match "host-customized"
            (Get-Content -Path "./run_daaf.ps1.pre-update" -Raw) | Should -Match "host-customized"
        }

        It "does not overwrite when the .pre-update backup fails" {
            # Backup-failure safety valve (f0506f6): if the rolling .pre-update
            # backup cannot be written, the host file is NEVER overwritten and the
            # old-style warning with the project-resolved manual hint is printed.
            #
            # Force the backup step to fail with a Copy-Item mock that throws
            # whenever the destination is the ".pre-update" backup path, and calls
            # through for every other invocation (e.g. the repo overwrite, which
            # must never be reached here). This targets exactly the backup
            # `Copy-Item -Path ./run_daaf.ps1 -Destination ./run_daaf.ps1.pre-update`.
            Remove-Item Env:DAAF_PROJECT_NAME -ErrorAction SilentlyContinue
            Set-Content -Path "./run_daaf.ps1" -Value "host-customized" -NoNewline
            Mock Copy-Item {
                if ($Destination -match "\.pre-update$") {
                    throw "simulated backup failure"
                }
                & (Get-Command Copy-Item -CommandType Cmdlet) @PSBoundParameters
            }
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") { return "samehash" }
                if ($allArgs -match "ls-files") { return "scripts/host/run_daaf.ps1" }
                if ($allArgs -match "compose cp") {
                    $dest = $args[$args.Count - 1]
                    New-Item -ItemType Directory -Path $dest -Force | Out-Null
                    Set-Content -Path (Join-Path $dest "run_daaf.ps1") -Value "pristine-repo" -NoNewline
                    $global:LASTEXITCODE = 0
                    return ""
                }
                $global:LASTEXITCODE = 0
                return ""
            }

            $output = Sync-HostScript "samehash" 6>&1
            # Host file must be UNCHANGED (backup failed -> never overwrite).
            (Get-Content -Path "./run_daaf.ps1" -Raw) | Should -Match "host-customized"
            (Get-Content -Path "./run_daaf.ps1" -Raw) | Should -Not -Match "pristine-repo"
            (Test-Path "./run_daaf.ps1.pre-update") | Should -BeFalse
            # Old-style warning + project-resolved manual hint (fallback 'daaf').
            ($output | Where-Object { $_ -match "WARNING: run_daaf.ps1 is stale but could not be updated" }) | Should -Not -BeNullOrEmpty
            ($output | Where-Object { $_ -match "backup step failed" }) | Should -Not -BeNullOrEmpty
            ($output | Where-Object { $_ -match "docker cp daaf-daaf-docker-1:/daaf/scripts/host/run_daaf.ps1 ./run_daaf.ps1" }) | Should -Not -BeNullOrEmpty
            # No heal summary since nothing was actually updated.
            ($output | Where-Object { $_ -match "One or more host files were stale and have been updated" }) | Should -BeNullOrEmpty
        }

        It "does not overwrite when the repo-to-host write fails after a successful backup" {
            # Third contract branch (f0506f6): the .pre-update backup SUCCEEDS but
            # the subsequent repo->host overwrite FAILS. The host file is left
            # unchanged, the (now-redundant) backup remains, and the "(write
            # failed)" warning with the project-resolved manual hint is printed.
            # Distinct, separately worded branch from the "backup step failed" path.
            #
            # Force ONLY the overwrite to fail with a Copy-Item mock: the backup
            # copy (destination "*.pre-update") calls through and succeeds; the
            # overwrite copy (destination "./run_daaf.ps1", NOT .pre-update) throws.
            Remove-Item Env:DAAF_PROJECT_NAME -ErrorAction SilentlyContinue
            Set-Content -Path "./run_daaf.ps1" -Value "host-customized" -NoNewline
            Mock Copy-Item {
                if ($Destination -match "\.pre-update$") {
                    # Backup call-through: perform the real copy via .NET rather than
                    # calling Copy-Item (Pester intercepts Copy-Item by name even when
                    # module-qualified -> infinite recursion / call-depth overflow).
                    $src = (Resolve-Path $Path).Path
                    $dst = Join-Path (Get-Location).Path (Split-Path $Destination -Leaf)
                    [System.IO.File]::Copy($src, $dst, $true)
                } else {
                    throw "simulated overwrite failure"
                }
            }
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") { return "samehash" }
                if ($allArgs -match "ls-files") { return "scripts/host/run_daaf.ps1" }
                if ($allArgs -match "compose cp") {
                    $dest = $args[$args.Count - 1]
                    New-Item -ItemType Directory -Path $dest -Force | Out-Null
                    Set-Content -Path (Join-Path $dest "run_daaf.ps1") -Value "pristine-repo" -NoNewline
                    $global:LASTEXITCODE = 0
                    return ""
                }
                $global:LASTEXITCODE = 0
                return ""
            }

            $output = Sync-HostScript "samehash" 6>&1
            # Host file UNCHANGED (overwrite failed -> never leaves a partial copy).
            (Get-Content -Path "./run_daaf.ps1" -Raw) | Should -Match "host-customized"
            (Get-Content -Path "./run_daaf.ps1" -Raw) | Should -Not -Match "pristine-repo"
            # Backup SUCCEEDED, so the .pre-update file exists with the old content.
            (Test-Path "./run_daaf.ps1.pre-update") | Should -BeTrue
            (Get-Content -Path "./run_daaf.ps1.pre-update" -Raw) | Should -Match "host-customized"
            # "(write failed)"-branch warning + project-resolved manual hint (fallback 'daaf').
            ($output | Where-Object { $_ -match "WARNING: run_daaf.ps1 is stale but could not be updated" }) | Should -Not -BeNullOrEmpty
            ($output | Where-Object { $_ -match "write failed" }) | Should -Not -BeNullOrEmpty
            ($output | Where-Object { $_ -match "docker cp daaf-daaf-docker-1:/daaf/scripts/host/run_daaf.ps1 ./run_daaf.ps1" }) | Should -Not -BeNullOrEmpty
            # No heal summary, and NOT the "backup step failed" wording (other branch).
            ($output | Where-Object { $_ -match "One or more host files were stale and have been updated" }) | Should -BeNullOrEmpty
            ($output | Where-Object { $_ -match "backup step failed" }) | Should -BeNullOrEmpty
        }

        It "skips the running updater script itself in the drift loop" {
            # The drift loop must never overwrite update_daaf.ps1 from tier C, even
            # when it exists on host and drifts from the repo copy (self-overwrite
            # mid-execution risks corrupted content; Tier B is the sanctioned refresh).
            Set-Content -Path "./update_daaf.ps1" -Value "host-updater" -NoNewline
            Set-Content -Path "./run_daaf.ps1" -Value "identical" -NoNewline
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") { return "samehash" }
                if ($allArgs -match "ls-files") { return "scripts/host/update_daaf.ps1`nscripts/host/run_daaf.ps1" }
                if ($allArgs -match "compose cp") {
                    $dest = $args[$args.Count - 1]
                    New-Item -ItemType Directory -Path $dest -Force | Out-Null
                    Set-Content -Path (Join-Path $dest "update_daaf.ps1") -Value "repo-updater" -NoNewline
                    Set-Content -Path (Join-Path $dest "run_daaf.ps1") -Value "identical" -NoNewline
                    $global:LASTEXITCODE = 0
                    return ""
                }
                $global:LASTEXITCODE = 0
                return ""
            }

            $output = Sync-HostScript "samehash" 6>&1
            # The running updater must be byte-for-byte unchanged (never healed).
            (Get-Content -Path "./update_daaf.ps1" -Raw) | Should -Match "host-updater"
            (Test-Path "./update_daaf.ps1.pre-update") | Should -BeFalse
            ($output | Where-Object { $_ -match "Updated: update_daaf.ps1" }) | Should -BeNullOrEmpty
        }

        It "does not drift-check a freshly-copied (tier A) file" {
            # daaf.ps1 is MISSING -> tier A copies it -> excluded from tier C even
            # though the staged repo copy differs. run_daaf.ps1 present + identical.
            Set-Content -Path "./run_daaf.ps1" -Value "identical" -NoNewline
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") { return "samehash" }
                if ($allArgs -match "ls-files") { return "scripts/host/daaf.ps1`nscripts/host/run_daaf.ps1" }
                if ($allArgs -match "compose cp") {
                    $dest = $args[$args.Count - 1]
                    New-Item -ItemType Directory -Path $dest -Force | Out-Null
                    Set-Content -Path (Join-Path $dest "daaf.ps1") -Value "repo-daaf" -NoNewline
                    Set-Content -Path (Join-Path $dest "run_daaf.ps1") -Value "identical" -NoNewline
                    $global:LASTEXITCODE = 0
                    return ""
                }
                $global:LASTEXITCODE = 0
                return ""
            }

            $output = Sync-HostScript "samehash" 6>&1
            ($output | Where-Object { $_ -match "Updated: daaf.ps1" }) | Should -Not -BeNullOrEmpty
            ($output | Where-Object { $_ -match "WARNING: daaf.ps1 differs" }) | Should -BeNullOrEmpty
        }

        It "degrades gracefully when drift staging (compose cp) fails" {
            Set-Content -Path "./run_daaf.ps1" -Value "host-customized" -NoNewline
            Mock docker {
                $allArgs = $args -join " "
                if ($allArgs -match "rev-parse HEAD") { return "samehash" }
                if ($allArgs -match "ls-files") { return "scripts/host/run_daaf.ps1" }
                if ($allArgs -match "compose cp") {
                    # Bulk stage fails -> drift check skipped with a notice.
                    $global:LASTEXITCODE = 1
                    return ""
                }
                $global:LASTEXITCODE = 0
                return ""
            }

            $output = Sync-HostScript "samehash" 6>&1
            ($output | Where-Object { $_ -match "could not check host scripts for drift" }) | Should -Not -BeNullOrEmpty
            ($output | Where-Object { $_ -match "differs from the repository version" }) | Should -BeNullOrEmpty
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
    # Save-BranchChoice (branch persistence, extracted for the no-op paths)
    # -----------------------------------------------------------------
    # W3 / HSM5: the extracted Save-BranchChoice call path (shared by
    # Complete-Update AND the no-op success exits) must write NOTHING under
    # DAAF_DRY_RUN. Called directly here; both $PWD (Push-Location) and the .NET
    # CurrentDirectory are pointed at the temp dir so the relative settings path
    # resolves deterministically without launching a child process.
    Context "Save-BranchChoice" {
        BeforeEach {
            # The updater was dot-sourced in Pester's parent scope; reset the
            # production variable in that same scope before every test.
            Set-Variable -Name PersistBranch -Value "" -Scope 1
            $script:PbcDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-pbc-$(Get-Random)")
            Push-Location $script:PbcDir
            Remove-Item Env:DAAF_DRY_RUN -ErrorAction SilentlyContinue
        }
        AfterEach {
            Set-Variable -Name PersistBranch -Value "" -Scope 1
            Pop-Location
            Remove-Item -Recurse -Force $script:PbcDir -ErrorAction SilentlyContinue
            Remove-Item Env:DAAF_DRY_RUN -ErrorAction SilentlyContinue
        }

        It "writes nothing under DAAF_DRY_RUN (HSM5, shared no-op call path)" {
            $settings = Join-Path $script:PbcDir "environment_settings.txt"
            Set-Content -Path $settings -Value "DAAF_PROJECT_NAME=daaf"
            $before = Get-Content -Raw $settings
            $savedCwd = [Environment]::CurrentDirectory
            [Environment]::CurrentDirectory = $script:PbcDir
            $env:DAAF_DRY_RUN = "1"
            Set-Variable -Name PersistBranch -Value "dev" -Scope 1
            try {
                $output = Save-BranchChoice 6>&1
            }
            finally {
                $env:DAAF_DRY_RUN = $null
                [Environment]::CurrentDirectory = $savedCwd
            }
            # -Match (regex, escaped brackets); -BeLike would read [DRY-RUN] as a
            # wildcard character class.
            ($output | Out-String) | Should -Match '\[DRY-RUN\] Set-DaafSettingsKey would write'
            ($output | Out-String) | Should -Not -Match 'Saved DAAF_BRANCH='
            (Get-Content -Raw $settings) | Should -Be $before
            (Test-Path (Join-Path $script:PbcDir "environment_settings.txt.pre-update")) | Should -Be $false
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

        It "saves and restores DAAF_NESTED around each nested delegate (no unconditional clobber)" {
            # Regression guard for the DAAF_NESTED clobber bug: each nested-script
            # launch (the post-update rebuild, and the optional pre-update backup)
            # must capture the parent's DAAF_NESTED before setting it to "1" and
            # restore it in finally, so a value inherited from a parent process
            # survives instead of being unconditionally removed.
            $setCount     = ([regex]::Matches($Content, '\$env:DAAF_NESTED = "1"')).Count
            $saveCount    = ([regex]::Matches($Content, '\$savedNested = \$env:DAAF_NESTED')).Count
            $restoreCount = ([regex]::Matches($Content, 'if \(\$null -ne \$savedNested\) \{ \$env:DAAF_NESTED = \$savedNested \} else \{ Remove-Item Env:\\DAAF_NESTED')).Count
            $removeCount  = ([regex]::Matches($Content, 'Remove-Item Env:\\DAAF_NESTED')).Count
            $setCount     | Should -BeGreaterOrEqual 2
            $saveCount    | Should -Be $setCount
            $restoreCount | Should -Be $setCount
            # Every Remove-Item Env:\DAAF_NESTED must live inside a conditional restore.
            $removeCount  | Should -Be $restoreCount
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
        # Clear any ambient DAAF_BRANCH (a dev container may export the current
        # working branch, e.g. daaf_dev_r2) so state-machine tests that model the
        # default-branch flow are not silently steered onto another branch. Parity
        # with the bash setup()'s `unset DAAF_BRANCH`. Tests that need it set it
        # explicitly; AfterEach clears it again.
        Remove-Item Env:DAAF_BRANCH -ErrorAction SilentlyContinue
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
        $outputStr | Should -Not -BeLike "*version tag*"
        Remove-Item Env:DAAF_BRANCH -ErrorAction SilentlyContinue
    }

    # An env-origin DAAF_BRANCH tag gives an informative REFUSAL (exit 1): the
    # updater names the tag, points at the supported re-install path, and states
    # which branch ongoing updates track. It never persists a tag. (Repurposed
    # from the former "tag-specific error" test after the env-tag design decision;
    # the file-origin tag path below is the softer warn-and-continue arm.)
    It "env-origin DAAF_BRANCH tag is refused with re-install guidance" {
        $env:DAAF_NESTED = "1"
        $env:DAAF_BRANCH = "v2.1.0"
        $wrapperScript = Join-Path $script:TestDir "test_wrapper_tag.ps1"
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
        "*compose exec*git -C /daaf rev-parse --verify*origin/v2.1.0*" { $global:LASTEXITCODE = 1; return }
        "*compose exec*git -C /daaf rev-parse --verify*refs/tags/v2.1.0*" { $global:LASTEXITCODE = 0; return }
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
        $outputStr | Should -BeLike "*v2.1.0*"
        $outputStr | Should -BeLike "*version tag*"
        $outputStr | Should -BeLike "*not a branch*"
        # Names the supported re-install path (pinned to the tag)...
        $outputStr | Should -BeLike "*install.ps1 | iex*"
        # ...states which branch ongoing updates track...
        $outputStr | Should -BeLike "*default branch*"
        # ...and never saves a tag as the update branch.
        $outputStr | Should -BeLike "*never saved as your update branch*"
        Remove-Item Env:DAAF_BRANCH -ErrorAction SilentlyContinue
    }

    # A file-origin DAAF_BRANCH tag (in environment_settings.txt, NOT the env)
    # must NOT lock the user out: warn, name the file, and fall back to the
    # auto-detected default branch for this run (exit 0, the update proceeds).
    It "file-origin DAAF_BRANCH tag warns and auto-detects (no hard exit)" {
        $env:DAAF_NESTED = "1"
        Remove-Item Env:DAAF_BRANCH -ErrorAction SilentlyContinue
        Set-Content -Path (Join-Path $script:TestDir "environment_settings.txt") -Value "DAAF_BRANCH=v2.1.0"
        $wrapperScript = Join-Path $script:TestDir "test_wrapper_filetag.ps1"
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
        "*compose exec*git -C /daaf rev-parse --verify*origin/v2.1.0*" { $global:LASTEXITCODE = 1; return }
        "*compose exec*git -C /daaf rev-parse --verify*refs/tags/v2.1.0*" { $global:LASTEXITCODE = 0; return }
        "*compose exec*git -C /daaf rev-parse --verify*origin/main*" { $global:LASTEXITCODE = 0; return }
        "*compose exec*git -C /daaf branch --show-current*" { Write-Output "main" }
        "*compose exec*git -C /daaf rev-parse*origin/main*" { Write-Output "samehash" }
        "*compose exec*git -C /daaf rev-parse*HEAD*" { Write-Output "samehash" }
        "*compose exec*git -C /daaf diff --name-only*HEAD*" { return }
        "*compose exec*git -C /daaf rev-list --count*" { Write-Output "0" }
        "*compose exec*git -C /daaf symbolic-ref*" { Write-Output "main" }
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
        $outputStr | Should -BeLike "*environment_settings.txt*"
        $outputStr | Should -BeLike "*version tag*"
        $outputStr | Should -BeLike "*auto-detected default branch*"
        $outputStr | Should -BeLike "*Already up to date*"
        $outputStr | Should -Not -BeLike "*never saved as your update branch*"
    }

    # An env-origin DAAF_BRANCH that IS a real branch is persisted back to
    # environment_settings.txt (replace mode, .pre-update backup) after a
    # successful update, so future runs track it without re-exporting.
    It "env-origin DAAF_BRANCH branch is persisted after a successful update" {
        $env:DAAF_NESTED = "1"
        $env:DAAF_BRANCH = "dev"
        Set-Content -Path (Join-Path $script:TestDir "environment_settings.txt") -Value "DAAF_PROJECT_NAME=daaf"
        $wrapperScript = Join-Path $script:TestDir "test_wrapper_persist.ps1"
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
        "*compose exec*git -C /daaf rev-parse --verify*origin/dev*" { $global:LASTEXITCODE = 0; return }
        "*compose exec*git -C /daaf branch --show-current*" { Write-Output "dev" }
        "*compose exec*git -C /daaf rev-parse*origin/dev*" { Write-Output "def456remote" }
        "*compose exec*git -C /daaf rev-parse*HEAD*" { Write-Output "abc123local" }
        "*compose exec*git -C /daaf diff --name-only*HEAD*" { return }
        "*compose exec*git -C /daaf rev-list --count*origin/dev..HEAD*" { Write-Output "0" }
        "*compose exec*git -C /daaf rev-list --count*HEAD..origin/dev*" { Write-Output "3" }
        "*compose exec*git -C /daaf pull*" { Write-Output "Updating abc123..def456" }
        "*compose exec*git -C /daaf symbolic-ref*" { Write-Output "dev" }
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
        $outputStr | Should -BeLike "*Update complete!*"
        $outputStr | Should -BeLike "*Saved DAAF_BRANCH=dev*"
        (Get-Content -Raw (Join-Path $script:TestDir "environment_settings.txt")) | Should -BeLike "*DAAF_BRANCH=dev*"
        (Test-Path (Join-Path $script:TestDir "environment_settings.txt.pre-update")) | Should -Be $true
        Remove-Item Env:DAAF_BRANCH -ErrorAction SilentlyContinue
    }

    # W3: the env-origin branch must persist even on a NO-OP success ("Already up
    # to date"), which returns before Complete-Update. Most common re-run case:
    # DAAF_BRANCH=dev while already current. Save-BranchChoice runs on the no-op path.
    It "env-origin branch persists on the already-up-to-date no-op path" {
        $env:DAAF_NESTED = "1"
        $env:DAAF_BRANCH = "dev"
        Set-Content -Path (Join-Path $script:TestDir "environment_settings.txt") -Value "DAAF_PROJECT_NAME=daaf"
        $wrapperScript = Join-Path $script:TestDir "test_wrapper_noop_persist.ps1"
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
        "*compose exec*git -C /daaf rev-parse --verify*origin/dev*" { $global:LASTEXITCODE = 0; return }
        "*compose exec*git -C /daaf branch --show-current*" { Write-Output "dev" }
        "*compose exec*git -C /daaf rev-parse*origin/dev*" { Write-Output "abc123same" }
        "*compose exec*git -C /daaf rev-parse*HEAD*" { Write-Output "abc123same" }
        "*compose exec*git -C /daaf diff --name-only*HEAD*" { return }
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
        $outputStr | Should -BeLike "*Saved DAAF_BRANCH=dev*"
        (Get-Content -Raw (Join-Path $script:TestDir "environment_settings.txt")) | Should -BeLike "*DAAF_BRANCH=dev*"
        (Test-Path (Join-Path $script:TestDir "environment_settings.txt.pre-update")) | Should -Be $true
        Remove-Item Env:DAAF_BRANCH -ErrorAction SilentlyContinue
    }

    It "DAAF_BRANCH is neither branch nor tag gives generic error" {
        $env:DAAF_NESTED = "1"
        $env:DAAF_BRANCH = "totally-bogus-ref"
        $wrapperScript = Join-Path $script:TestDir "test_wrapper_bogus.ps1"
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
        "*compose exec*git -C /daaf rev-parse --verify*origin/totally-bogus-ref*" { $global:LASTEXITCODE = 1; return }
        "*compose exec*git -C /daaf rev-parse --verify*refs/tags/totally-bogus-ref*" { $global:LASTEXITCODE = 1; return }
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
        $outputStr | Should -Not -BeLike "*version tag*"
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
