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

        It "uses staging + docker cp (not bind-mounted cp -a) for the volume copy" {
            # The copy mechanism is a STAGING container (`docker run -d`) + `docker
            # wait` + `docker cp` from /staging, which strips symlinks so a Windows
            # `docker cp` does not abort mid-archive. It streams through the daemon,
            # not file-by-file across the Docker Desktop bind-mount layer, and does
            # NOT `docker cp` the live volume directly.
            $Content | Should -Match 'docker run -d -v'
            $Content | Should -Match 'docker wait'
            $Content | Should -Match ':/staging/\.'
        }

        It "removes the staging container after copying" {
            # Both the data-volume copy (finally block) and the Claude copy must
            # tear down their `docker run -d` staging container with docker rm -f.
            $Content | Should -Match 'docker rm -f \$StageCid'
            $Content | Should -Match 'docker rm -f \$ClaudeStageCid'
        }

        It "stages the volume to strip symlinks and records .daaf-symlinks" {
            # Windows `docker cp` aborts on symlinks it cannot create, truncating the
            # archive. The staging program strips symlinks into a ".daaf-symlinks"
            # manifest so the copied tree is symlink-free. The program must be
            # quote-free (shared with the .sh twin; embedded " breaks PS 5.1 args).
            $Content | Should -Match '\.daaf-symlinks'
            $Content | Should -Match 'find /staging -type l -exec rm -f'
        }

        It "treats a nonzero staging exit as a fatal error before any host bytes" {
            $Content | Should -Match 'Failed to stage the Docker volume'
            $Content | Should -Match '\$StageStatus -ne 0'
        }

        It "staging gate NAMES the offending symlink(s) to STDOUT before exit 3" {
            # On a gate trip the container-side program prints the offenders to STDOUT
            # before `exit 3` (empirically verified against real sh in
            # scripts/scratch/backup_gate_probe/run_probe.sh: tab -> matching line via
            # `grep -f`; newline -> the full link_paths list). The offenders go to
            # STDOUT, not stderr: PS 5.1's native `2>&1` merge dropped the container's
            # stderr in the field (2026-07-14), so the offender list never reached the
            # user; stdout is version-agnostic. Structurally assert both branches emit a
            # header and dump the offenders, stay quote-free, and do NOT redirect to
            # stderr (the fragile PS 5.1 leg -- `>&2` must be gone from those lines).
            $Content | Should -Match 'embeds a newline'
            $Content | Should -Match 'cat /tmp/link_paths'
            $Content | Should -Match 'embed a tab'
            $Content | Should -Match 'grep -f /tmp/tab_pat /tmp/link_paths'
            $Content | Should -Not -Match 'cat /tmp/link_paths >&2'
            $Content | Should -Not -Match 'grep -f /tmp/tab_pat /tmp/link_paths >&2'
        }

        It "relays the detached staging container log on the fatal failure path" {
            # The staging container is DETACHED (`docker run -d`), so the gate's
            # offender output goes to the container LOG, not the terminal. The driver
            # must fetch it with `docker logs` and relay it under a "Details from the
            # staging scan" header. Assert the fatal path captures $StageLog via
            # `docker logs $StageCid` and prints the header.
            $Content | Should -Match 'docker logs \$StageCid'
            $Content | Should -Match 'Details from the staging scan'
        }

        It "fetches the staging log before removing the container (fatal path)" {
            # Ordering guard: in the fatal failure block, the `docker logs $StageCid`
            # capture must appear BEFORE the `docker rm -f $StageCid` that follows it
            # -- after removal the log is gone. `$null = docker rm -f $StageCid` occurs
            # in three places (start-failure guard, this fatal path, and the copy
            # finally), so anchor on the FIRST rm occurrence AT OR AFTER the $StageLog
            # capture rather than the first rm in the whole file.
            $logsIdx = $Content.IndexOf('$StageLog = (docker logs $StageCid')
            $logsIdx | Should -BeGreaterThan -1
            $rmIdx   = $Content.IndexOf('$null = docker rm -f $StageCid 2>&1', $logsIdx)
            $rmIdx   | Should -BeGreaterThan $logsIdx
        }

        It "relays the detached staging log on the Claude-volume WARNING path" {
            # The Claude staging failure stays a WARNING (asymmetric with the fatal
            # data-volume path) but must still relay the offender list captured from
            # the detached container's log before the finally removes it.
            $Content | Should -Match 'docker logs \$ClaudeStageCid'
            $Content | Should -Match '\$ClaudeStageLog'
        }

        It "labels an empty staging log instead of silently omitting details" {
            # When the fetched staging log is empty/whitespace, the driver must print a
            # clearly labeled fallback line rather than dropping the details block -- so
            # a future stream regression (like the PS 5.1 stderr-drop that motivated
            # moving the gate to stdout) is VISIBLE, not ambiguous. Both the data-volume
            # fatal path and the Claude-volume WARNING path emit this fallback, each
            # indented under the always-printed "Details from the staging scan:" header.
            $Content | Should -Match 'no details could be retrieved from the staging container'
            # Exactly two occurrences (data-fatal + Claude-WARNING).
            $matchCount = ([regex]::Matches($Content, 'no details could be retrieved from the staging container')).Count
            $matchCount | Should -Be 2
        }

        It "verifies the copied file count against the source scan" {
            # Do not trust docker cp's exit code alone (the Windows symlink-abort
            # surfaced with a zero exit): a count-shortfall must warn loudly.
            $Content | Should -Match 'Backup file-count mismatch'
        }

        It "prints the actual final host-side count, not a fabricated 100%" {
            # The old unconditional "100%" lied on truncated copies. The final line
            # must derive the percent from the real FileCount.
            $Content | Should -Match '\$FinalPercent'
        }

        It "checks available disk space before copying" {
            $Content | Should -Match 'Insufficient disk space'
            $Content | Should -Match 'System\.IO\.DriveInfo'
        }

        It "records the executable-permission manifest" {
            # The manifest ".daaf-permissions" is written into the backup root so a
            # Windows (NTFS) round-trip -- which loses POSIX modes -- can be undone
            # on restore. Generated container-side with -perm -0100 (owner-exec).
            $Content | Should -Match '\.daaf-permissions'
            $Content | Should -Match 'find /source -type f -perm -0100'
        }

        It "writes the manifest BOM-free with a no-BOM UTF8 encoding" {
            # PS 5.1 encoding trap: > / Out-File default to UTF-16 and -Encoding UTF8
            # adds a BOM. The manifest must be BOM-free LF bytes, so it is written via
            # WriteAllLines with New-Object System.Text.UTF8Encoding($false).
            $Content | Should -Match 'System\.Text\.UTF8Encoding\(\$false\)'
            $Content | Should -Match 'WriteAllLines'
        }

        It "treats a manifest write failure as a WARNING, not fatal" {
            $Content | Should -Match 'Could not record the executable-permission manifest'
        }

        It "performs size-based backup verification" {
            $Content | Should -Match 'Size verification'
            $Content | Should -Match 'Backup size mismatch'
        }

        It "docker scan command uses safe quoting for Windows arg passing" {
            # Regression: embedded " in strings passed to native exes on Windows
            # causes silent argument truncation. See shell-scripting gotchas.md.
            $scanLine = ($Content -split "`n") | Where-Object { $_ -match 'stat.*awk' }
            $scanLine | Should -Not -BeNullOrEmpty
            $scanLine | Should -Match 'stat -c %s'
            $scanLine | Should -Match "awk '"
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

Describe "backup_daaf.ps1 Import-DaafSettingsInline" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $env:DAAF_TEST_MODE = "1"
        . "$RepoRoot/scripts/host/backup_daaf.ps1"
    }

    AfterAll {
        Remove-Item Env:DAAF_TEST_MODE -ErrorAction SilentlyContinue
    }

    BeforeEach {
        $script:TmpDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-backup-settings-$(Get-Random)")
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
        [System.IO.File]::WriteAllBytes($script:SettingsFile, [System.Text.Encoding]::ASCII.GetBytes("DAAF_PORT_MARIMO=3001`r`n"))
        Import-DaafSettingsInline -SettingsFile $script:SettingsFile
        $env:DAAF_PORT_MARIMO | Should -Be "3001"
    }

    It "ignores non-DAAF keys" {
        Set-Content -Path $script:SettingsFile -Value "ANTHROPIC_API_KEY=sk-secret`nDAAF_PROJECT_NAME=safe"
        Import-DaafSettingsInline -SettingsFile $script:SettingsFile
        $env:DAAF_PROJECT_NAME | Should -Be "safe"
        $env:ANTHROPIC_API_KEY | Should -BeNullOrEmpty
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
    # Wait-AndExit (the only function exposed)
    # -----------------------------------------------------------------
    Context "Wait-AndExit function" {
        It "is callable after dot-sourcing" {
            Get-Command Wait-AndExit -ErrorAction SilentlyContinue |
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
            # Compares source vs backup logical byte sums
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

# ============================================================================
# Dry-run mode
# ============================================================================

Describe "backup_daaf.ps1 dry-run mode" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:OrigDryRun = $env:DAAF_DRY_RUN
        $script:OrigNested = $env:DAAF_NESTED
    }

    AfterAll {
        $env:DAAF_DRY_RUN = $script:OrigDryRun
        $env:DAAF_NESTED = $script:OrigNested
    }

    It "completes successfully with DAAF_DRY_RUN=1" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $null = & "$RepoRoot/scripts/host/backup_daaf.ps1" *>&1
        $LASTEXITCODE | Should -BeIn @(0, $null)
    }

    It "produces DRY-RUN markers in output" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/backup_daaf.ps1" *>&1
        ($output | Out-String) | Should -BeLike "*``[DRY-RUN``]*"
    }
}

# ============================================================================
# Error paths
# ============================================================================

Describe "backup_daaf.ps1 error paths" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:Content = Get-Content "$RepoRoot/scripts/host/backup_daaf.ps1" -Raw
    }

    Context "Copy operation fails with zero files" {
        It "handles copy failure resulting in zero files (exit 1, ERROR)" {
            # The script checks FileCount -eq 0 and CopyExitCode -ne 0, outputs ERROR
            $Content | Should -Match 'Backup failed \(exit code'
            $Content | Should -Match '\$FileCount -eq 0'
        }
    }

    Context "Copy partially succeeds" {
        It "handles non-zero exit but files copied (warning, not error)" {
            # When CopyExitCode != 0 but FileCount > 0, script shows Note about warnings
            $Content | Should -Match 'File copy reported warnings'
            $Content | Should -Match 'files were transferred'
        }
    }

    Context "Corroborated short copy is fatal" {
        It "fails when a non-zero copy exit AND a short file count agree" {
            # Two corroborating signals (nonzero exit + count below the scan) mean a
            # genuinely truncated backup, so the script aborts fatally.
            $Content | Should -Match '\$CopyExitCode -ne 0 -and \$FileCount -lt \$TotalFiles'
            $Content | Should -Match 'only \$FileCount of \$TotalFiles expected files were copied'
        }
        It "tells the user to delete the partial backup folder and re-run" {
            $Content | Should -Match 'This backup is incomplete and must not be relied on'
            $Content | Should -Match 'partial backup folder and re-run'
        }
    }

    Context "Warnings-aware completion banner" {
        It "prints the plain banner when no warnings were latched" {
            $Content | Should -Match 'Backup complete!'
        }
        It "prints the WITH WARNINGS banner when the latch is set" {
            $Content | Should -Match 'Backup completed WITH WARNINGS -- verify before relying on it'
        }
        It "latches HadWarnings at the non-fatal WARNING sites" {
            # Initialized false, and set true in each non-fatal WARNING path.
            $Content | Should -Match '\$HadWarnings = \$false'
            $Content | Should -Match '\$HadWarnings = \$true'
        }
    }

    Context "Volume scan unexpected format" {
        It "handles scan failure with error" {
            # When docker run for scan fails (LASTEXITCODE != 0), script exits with error
            $Content | Should -Match 'Could not scan Docker volume'
        }
    }
}
