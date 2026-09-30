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
            # wait` + `docker cp` from /staging, which strips symlinks and special
            # files (named pipes, sockets, device nodes) so a Windows
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
            # manifest (and deletes special files, no manifest) so the copied tree is
            # free of both. The program must be
            # quote-free (shared with the .sh twin; embedded " breaks PS 5.1 args).
            $Content | Should -Match '\.daaf-symlinks'
            $Content | Should -Match 'find /staging -type l -exec rm -f'
        }

        It "staging program deletes named pipes, sockets, and device nodes after the symlink strip" {
            # Windows `docker cp` creates nothing for a FIFO/device entry, then aborts
            # the whole extraction on the follow-up timestamp call (field failure
            # 2026-09-29, sibling project on a variant script: a stale provider-shim
            # output.fifo stopped a backup; last progress reading 94%).
            # The here-string's LAST line must be the grouped special-file strip,
            # directly after the symlink strip. (Byte parity with the .sh twin and
            # the zero-double-quote rule are enforced by backup_twin_parity.bats; the
            # strip's runtime behavior is exercised under a real sh in
            # backup_daaf.bats.)
            $stripLine = 'find /staging \( -type p -o -type s -o -type b -o -type c \) -exec rm -f {} +'
            $m = [regex]::Match($Content, "(?s)\`$StageProgram = @'\r?\n(.*?)\r?\n'@")
            $m.Success | Should -BeTrue
            $programLines = $m.Groups[1].Value -split "\r?\n"
            # Exact, case-sensitive line pins (-BeExactly): these are text-identity claims.
            $programLines[-8] | Should -BeExactly $stripLine
            $programLines[-9] | Should -BeExactly 'find /staging -type l -exec rm -f {} +'
            # Only the success-path snapshot-count block follows the strips: the count,
            # then the markers -- or STAGED_COUNT_ERRORS instead when the count hit
            # read errors (review round 2, F1).
            $programLines[-6] | Should -BeExactly 'if test -s /tmp/count_err; then'
            $programLines[-5] | Should -BeExactly 'echo STAGED_COUNT_ERRORS=$(grep -c ^ /tmp/count_err)'
            $programLines[-4] | Should -BeExactly 'else'
            $programLines[-3] | Should -BeExactly 'echo STAGED_FILES=${counts% *}'
            $programLines[-2] | Should -BeExactly 'echo STAGED_KB=${counts#* }'
            $programLines[-1] | Should -BeExactly 'fi'
        }

        It "scan appends a special-file count as the 5th line and parses it bounds-checked" {
            # Appended AFTER the four existing values (index contract unchanged). Under
            # Set-StrictMode 3.0 an out-of-range index throws, so index [4] is read only
            # when present, via TryParse (non-numeric/missing -> 0).
            $Content | Should -Match ([regex]::Escape("&& find /source \( -type p -o -type s -o -type b -o -type c \) | wc -l && "))
            $Content | Should -Match ([regex]::Escape('if ($ScanLines.Count -ge 5) {'))
            $Content | Should -Match ([regex]::Escape('[int]::TryParse("$($ScanLines[4])".Trim(), [ref]$SpecialFilesParsed)'))
            $Content | Should -Match ([regex]::Escape('Note: skipping $SpecialFiles named pipe/socket/device file(s) -- runtime-only, not backed up.'))
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
            $scanLine = ($Content -split "`n") | Where-Object { $_ -match '^\$ScanOutput = docker run' }
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

        # -----------------------------------------------------------------
        # Regression: fail-closed staging-status parse (boolean-gated TryParse)
        # -----------------------------------------------------------------
        # [int]::TryParse writes 0 into the [ref] on a parse FAILURE, so the old
        # `$null = [int]::TryParse(..., [ref]$StageStatus)` form silently overwrote the
        # fail-closed default with 0 whenever `docker wait` emitted a non-numeric last
        # line (a daemon error merged via 2>&1) -- flipping the fatal gate from "abort"
        # to "proceed to copy a partial staged tree." The fix parses into a temp var and
        # adopts it ONLY when TryParse returns $true (mirrors restore_from_backup.ps1's
        # backup-number check, `[int]::TryParse($Choice, [ref]$ChoiceNum)`).
        Context "Regression: fail-closed staging-status parse (boolean-gated TryParse)" {
            It "gates the data-volume staging status on TryParse's boolean via a temp var" {
                $Content | Should -Match '\[int\]::TryParse\("\$StageStatusRaw"\.Trim\(\), \[ref\]\$StageStatusParsed\)'
                $Content | Should -Match '\$StageStatus = \$StageStatusParsed'
                # The fail-open idiom for the status var must be gone.
                $Content | Should -Not -Match '\$null = \[int\]::TryParse\("\$StageStatusRaw"'
            }
            It "gates the Claude-volume staging status the same fail-closed way" {
                $Content | Should -Match '\[int\]::TryParse\("\$ClaudeStageStatusRaw"\.Trim\(\), \[ref\]\$ClaudeStageStatusParsed\)'
                $Content | Should -Match '\$ClaudeStageStatus = \$ClaudeStageStatusParsed'
                $Content | Should -Not -Match '\$null = \[int\]::TryParse\("\$ClaudeStageStatusRaw"'
            }
            It "keeps the explicit fail-closed default of 1 for both staging statuses" {
                $Content | Should -Match '\$StageStatus = 1'
                $Content | Should -Match '\$ClaudeStageStatus = 1'
            }
        }

        # -----------------------------------------------------------------
        # Regression: floored 1% tolerances (no banker's rounding)
        # -----------------------------------------------------------------
        # `[long]($TotalFiles / 100)` round-half-to-even diverges from the bash twin's
        # truncating integer division (350 -> 4 vs floor 3). The fix uses [math]::Floor
        # to match bash (backup_daaf.sh COUNT_TOLERANCE / TOLERANCE_KB) and
        # restore_from_backup.ps1 ($Tolerance).
        Context "Regression: floored 1% tolerances (no banker's rounding)" {
            It "floors the file-count tolerance with [math]::Floor (not a bare [long] cast)" {
                $Content | Should -Match '\[math\]::Max\(1, \[long\]\[math\]::Floor\(\$TotalFiles / 100\)\)'
                $Content | Should -Not -Match '\[long\]\(\$TotalFiles / 100\)'
            }
            It "floors the size tolerance with [math]::Floor (not a bare [long] cast)" {
                $Content | Should -Match '\[math\]::Max\(1, \[long\]\[math\]::Floor\(\$SourceSizeKB / 100\)\)'
                $Content | Should -Not -Match '\[long\]\(\$SourceSizeKB / 100\)'
            }
        }

        # -----------------------------------------------------------------
        # Regression: docker cp exit code is cached and never coerced to 0
        # -----------------------------------------------------------------
        # A Start-Process -PassThru Process can report ExitCode as $null unless its
        # Handle was opened while the process was alive (widely reported .NET/PS
        # quirk; INFERENCE -- not reproducible on this Linux runner). The old
        # `else { 0 }` then turned an unknown (possibly failed) copy into a clean
        # success and disarmed the corroborated short-copy check.
        Context "Regression: docker cp exit code is cached and never coerced to 0" {
            It "caches the copy process handle immediately after Start-Process" {
                $startIdx  = $Content.IndexOf('$CopyProcess = Start-Process -FilePath "docker"')
                $handleIdx = $Content.IndexOf('$null = $CopyProcess.Handle')
                $loopIdx   = $Content.IndexOf('while (-not $CopyProcess.HasExited)')
                $startIdx  | Should -BeGreaterThan -1
                $handleIdx | Should -BeGreaterThan $startIdx
                # Before the polling loop -- i.e. while docker cp is still running.
                $loopIdx   | Should -BeGreaterThan $handleIdx
            }
            It "no longer coerces a null ExitCode to 0" {
                $Content | Should -Not -Match 'else \{ 0 \}'
                $Content | Should -Match ([regex]::Escape('$CopyExitKnown = ($null -ne $CopyExitCode)'))
            }
            It "gates the fatal and Note branches on a KNOWN exit code" {
                $Content | Should -Match ([regex]::Escape('if ($CopyExitKnown -and $CopyExitCode -ne 0 -and $FileCount -lt $ExpectedFiles -and -not $CountIsLowerBound) {'))
                $Content | Should -Match ([regex]::Escape('} elseif ($CopyExitKnown -and $CopyExitCode -ne 0) {'))
                $Content | Should -Match ([regex]::Escape('if ($CopyExitKnown -and $CopyExitCode -ne 0) {'))
            }
            It "latches HadWarnings on the known-nonzero, full-count Note branch" {
                $noteIdx = $Content.IndexOf('} elseif ($CopyExitKnown -and $CopyExitCode -ne 0) {')
                $nextIdx = $Content.IndexOf('} elseif (-not $CopyExitKnown) {', $noteIdx)
                $noteIdx | Should -BeGreaterThan -1
                $nextIdx | Should -BeGreaterThan $noteIdx
                $Content.Substring($noteIdx, $nextIdx - $noteIdx) | Should -Match '\$HadWarnings = \$true'
            }
            It "builds the docker cp argument string with ConvertTo-DaafNativeArg (not an array)" {
                $Content | Should -Match ([regex]::Escape('$CopyArgs = (@(''cp'', "${StageCid}:/staging/.", $HostPath) | ForEach-Object { ConvertTo-DaafNativeArg $_ }) -join '' '''))
                $Content | Should -Match ([regex]::Escape('-ArgumentList $CopyArgs'))
                $Content | Should -Not -Match '-ArgumentList @\('
            }
            It "warns and latches HadWarnings on an unknown exit code" {
                $unknownIdx = $Content.IndexOf('} elseif (-not $CopyExitKnown) {')
                $unknownIdx | Should -BeGreaterThan -1
                $branch = $Content.Substring($unknownIdx, 1200)
                $branch | Should -Match 'WARNING: The file copy''s exit code could not be read, and only \$FileCountLabel of \$ExpectedFiles'
                $branch | Should -Match 'Note: The file copy''s exit code could not be read'
                $branch | Should -Match '\$HadWarnings = \$true'
                # The unknown zero-file case is an ERROR, not "volume may be empty".
                $Content | Should -Match ([regex]::Escape('} elseif (-not $CopyExitKnown -and $ExpectedFiles -gt 0) {'))
            }
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

    It "rejects a whitespace-padded key (column-0 strict, parity with bash)" {
        # A leading-space key like "  DAAF_PROJECT_NAME=..." is not flush at column 0.
        # The bash loaders' `case` glob rejects it; the PS loader must too (key extracted
        # WITHOUT .Trim()), so a padded key resolves identically -- to nothing -- on both
        # platforms rather than silently working on Windows only. Pre-fix, the trimmed key
        # matched the whitelist and the value was adopted.
        Set-Content -Path $script:SettingsFile -Value "  DAAF_PROJECT_NAME=padded"
        Import-DaafSettingsInline -SettingsFile $script:SettingsFile
        $env:DAAF_PROJECT_NAME | Should -BeNullOrEmpty
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

    # -----------------------------------------------------------------
    # Executable semantics: fail-closed parse + floored tolerance
    # -----------------------------------------------------------------
    # These run the FIXED snippets directly so a behavioral regression (not just a
    # text edit) is caught. Each would produce the wrong value under the pre-fix form.
    Context "Fail-closed parse + floored tolerance (executable semantics)" {
        It "keeps the staging status fail-closed at 1 on non-numeric docker wait output" {
            # Reproduce the exact parse snippet and feed it a merged daemon error line.
            # The pre-fix `$null = [int]::TryParse(...)` overwrote the default with 0.
            $StageStatusRaw = "Error response from daemon: no such container"
            $StageStatus = 1
            $StageStatusParsed = 0
            if ($null -ne $StageStatusRaw -and [int]::TryParse("$StageStatusRaw".Trim(), [ref]$StageStatusParsed)) {
                $StageStatus = $StageStatusParsed
            }
            $StageStatus | Should -Be 1
        }
        It "adopts a genuine numeric zero status when docker wait succeeds cleanly" {
            $StageStatusRaw = "0"
            $StageStatus = 1
            $StageStatusParsed = 0
            if ($null -ne $StageStatusRaw -and [int]::TryParse("$StageStatusRaw".Trim(), [ref]$StageStatusParsed)) {
                $StageStatus = $StageStatusParsed
            }
            $StageStatus | Should -Be 0
        }
        It "floors an odd-hundred-half tolerance to 3, not banker's-rounded 4" {
            # 350/100: [long](...) banker's-rounds to 4; [math]::Floor gives 3, matching
            # the bash twin's truncating integer division. The second assertion documents
            # (with executable evidence) exactly the divergence the fix removes.
            ([long][math]::Floor(350 / 100)) | Should -Be 3
            ([long](350 / 100)) | Should -Be 4
        }
        It "IDIOM DOC (not a regression guard): the exit-code read idiom yields UNKNOWN for a null ExitCode" {
            # IDIOM-DOCUMENTATION TEST: this runs a COPY of the read idiom, so it cannot
            # fail if backup_daaf.ps1 regresses. It documents, with executable evidence,
            # that the idiom maps the Windows symptom ($null) to UNKNOWN, where the
            # pre-fix `else { 0 }` yielded a clean 0. The REAL regression guards are the
            # structural assertions in "Regression: docker cp exit code is cached and
            # never coerced to 0" (handle cache present, `else { 0 }` absent, branches
            # gated on $CopyExitKnown).
            $CopyProcess = [pscustomobject]@{ ExitCode = $null }
            $CopyExitCode = $null
            try {
                $CopyExitCode = $CopyProcess.ExitCode
            } catch {
                $CopyExitCode = $null
            }
            $CopyExitKnown = ($null -ne $CopyExitCode)
            $CopyExitKnown | Should -BeFalse
            $CopyExitCode | Should -BeNullOrEmpty
        }
        It "IDIOM DOC (not a regression guard): the exit-code read idiom yields UNKNOWN for a throwing getter" {
            # IDIOM-DOCUMENTATION TEST: a COPY of the idiom (see the test above); it
            # documents that a throwing ExitCode getter is caught rather than aborting
            # under EAP=Stop. The structural assertions are the real guard.
            $CopyProcess = [pscustomobject]@{}
            $CopyProcess | Add-Member -MemberType ScriptProperty -Name ExitCode -Value { throw 'Process must exit before requested information can be determined.' }
            $CopyExitCode = $null
            try {
                $CopyExitCode = $CopyProcess.ExitCode
            } catch {
                $CopyExitCode = $null
            }
            ($null -ne $CopyExitCode) | Should -BeFalse
        }
        It "reads a real process's nonzero exit after caching its handle" {
            # Executable evidence on THIS runner that the cache + read idiom returns the
            # true exit status of a Start-Process -PassThru child (the Windows
            # handle-release quirk itself cannot be reproduced here).
            # Space-free child commands: Start-Process joins ArgumentList elements with
            # spaces, so an element like 'exit 5' would be split on this runner.
            $onWindows = ($PSVersionTable.PSVersion.Major -lt 6) -or $IsWindows
            $shell    = if ($onWindows) { 'cmd.exe' } else { 'sh' }
            $argList  = if ($onWindows) { @('/c', 'exit', '5') } else { @('-c', 'false') }
            $expected = if ($onWindows) { 5 } else { 1 }
            $CopyProcess = Start-Process -FilePath $shell -ArgumentList $argList -NoNewWindow -PassThru
            $null = $CopyProcess.Handle
            $CopyProcess.WaitForExit()
            $CopyExitCode = $null
            try {
                $CopyExitCode = $CopyProcess.ExitCode
            } catch {
                $CopyExitCode = $null
            }
            $CopyExitCode | Should -Be $expected
        }
    }
}

# ============================================================================
# Count helpers + zero-tolerance structure (2026-09-29 long-path undercount)
# ============================================================================
# Field run (Windows PowerShell 5.1, LongPathsEnabled=0): Get-ChildItem counted 72,834
# files where a container-side count of the same folder found 73,021, and the 1%
# tolerance hid it. These pin the replacement: marker parsing, the never-silent
# PowerShell fallback, and zero tolerance against the staged snapshot.

Describe "backup_daaf.ps1 count helpers and verification structure" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $env:DAAF_TEST_MODE = "1"
        . "$RepoRoot/scripts/host/backup_daaf.ps1"
        $script:Content = Get-Content "$RepoRoot/scripts/host/backup_daaf.ps1" -Raw
    }

    AfterAll {
        Remove-Item Env:DAAF_TEST_MODE -ErrorAction SilentlyContinue
    }

    Context "Get-DaafCountMarker" {
        It "parses a well-formed marker from mixed output (string array)" {
            Get-DaafCountMarker -Lines @('noise', 'STAGED_FILES=73021', 'STAGED_KB=12') -Name 'STAGED_FILES' | Should -Be 73021
        }
        It "parses from one multi-line string with CRLF endings and surrounding whitespace" {
            Get-DaafCountMarker -Lines "x`r`n  STAGED_KB=512  `r`n" -Name 'STAGED_KB' | Should -Be 512
        }
        It "returns `$null for a missing marker, empty input, or `$null input" {
            Get-DaafCountMarker -Lines @('STAGED_KB=1') -Name 'STAGED_FILES' | Should -BeNullOrEmpty
            Get-DaafCountMarker -Lines @() -Name 'STAGED_FILES' | Should -BeNullOrEmpty
            Get-DaafCountMarker -Lines $null -Name 'STAGED_FILES' | Should -BeNullOrEmpty
        }
        It "returns `$null for garbage: non-digits, sign, suffix, prefix text, overflow" {
            foreach ($bad in @('STAGED_FILES=abc', 'STAGED_FILES=-3', 'STAGED_FILES=3x', 'x STAGED_FILES=3', 'STAGED_FILES=', 'STAGED_FILES=99999999999999999999')) {
                Get-DaafCountMarker -Lines @($bad) -Name 'STAGED_FILES' | Should -BeNullOrEmpty -Because "input [$bad]"
            }
        }
        It "does not match a marker whose name merely contains the requested name" {
            Get-DaafCountMarker -Lines @('XSTAGED_FILES=5') -Name 'STAGED_FILES' | Should -BeNullOrEmpty
        }
        It "last valid occurrence wins" {
            Get-DaafCountMarker -Lines @('BACKUP_FILES=1', 'BACKUP_FILES=2') -Name 'BACKUP_FILES' | Should -Be 2
        }
        It "reads through ErrorRecord objects mixed into 2>&1 output" {
            $rec = [System.Management.Automation.ErrorRecord]::new([Exception]::new('daemon noise'), 'x', 'NotSpecified', $null)
            Get-DaafCountMarker -Lines @($rec, 'BACKUP_KB=9') -Name 'BACKUP_KB' | Should -Be 9
        }
    }

    Context "Measure-DaafBackupTree (PowerShell fallback count)" {
        BeforeEach {
            $script:Tree = Join-Path $TestDrive ("tree-" + [guid]::NewGuid().ToString('N'))
            $null = New-Item -ItemType Directory -Path (Join-Path $script:Tree 'sub'), (Join-Path $script:Tree '.daaf-claude-config/deep')
            [IO.File]::WriteAllBytes((Join-Path $script:Tree 'a.bin'), (New-Object byte[] 1000))
            [IO.File]::WriteAllBytes((Join-Path $script:Tree 'sub/b.bin'), (New-Object byte[] 2000))
            [IO.File]::WriteAllBytes((Join-Path $script:Tree 'sub/.daaf-symlinks'), (New-Object byte[] 100))
            [IO.File]::WriteAllBytes((Join-Path $script:Tree '.daaf-symlinks'), (New-Object byte[] 50))
            [IO.File]::WriteAllBytes((Join-Path $script:Tree '.daaf-permissions'), (New-Object byte[] 50))
            [IO.File]::WriteAllBytes((Join-Path $script:Tree '.daaf-claude-config/deep/c.json'), (New-Object byte[] 70))
        }
        It "applies ROOT-relative exclusions only (nested same-name files count), sums bytes and floors KB" {
            $m = Measure-DaafBackupTree -Root $script:Tree -ExcludeRootFiles @('.daaf-symlinks', '.daaf-permissions') -ExcludeRootDirs @('.daaf-claude-config')
            $m.Files | Should -Be 3
            $m.Bytes | Should -Be 3100
            $m.KB | Should -Be 3
            $m.Errors | Should -Be 0
        }
        It "reports enumeration errors instead of hiding them (unreadable folder -> lower bound)" -Skip:(($PSVersionTable.PSVersion.Major -lt 6) -or $IsWindows -or ((& id -u) -eq '0')) {
            # Stand-in for the Windows path-length failure: a folder Get-ChildItem
            # cannot read. SilentlyContinue alone would return 3 with no signal.
            $locked = Join-Path $script:Tree 'locked'
            $null = New-Item -ItemType Directory -Path $locked
            [IO.File]::WriteAllBytes((Join-Path $locked 'hidden.bin'), (New-Object byte[] 10))
            & chmod 000 $locked
            try {
                $m = Measure-DaafBackupTree -Root $script:Tree -ExcludeRootFiles @('.daaf-symlinks', '.daaf-permissions') -ExcludeRootDirs @('.daaf-claude-config')
                $m.Errors | Should -BeGreaterThan 0
                $m.Files | Should -Be 3
            } finally {
                & chmod 755 $locked
            }
        }
        It "returns an error (not a crash) for a missing root" {
            $m = Measure-DaafBackupTree -Root (Join-Path $TestDrive 'does-not-exist')
            $m.Files | Should -Be 0
            $m.Errors | Should -Be 1
        }
        It "compares root exclusions case-SENSITIVELY, like the container's find -path" -Skip:(($PSVersionTable.PSVersion.Major -lt 6) -or $IsWindows -or $IsMacOS) {
            # Review round 2 (F5j): -contains / OrdinalIgnoreCase excluded a root
            # ".DAAF-SYMLINKS" that the container count includes. Needs a case-sensitive
            # filesystem to hold both spellings side by side (Linux).
            [IO.File]::WriteAllBytes((Join-Path $script:Tree '.DAAF-SYMLINKS'), (New-Object byte[] 7))
            $null = New-Item -ItemType Directory -Path (Join-Path $script:Tree '.DAAF-Claude-Config')
            [IO.File]::WriteAllBytes((Join-Path $script:Tree '.DAAF-Claude-Config/x'), (New-Object byte[] 3))
            $m = Measure-DaafBackupTree -Root $script:Tree -ExcludeRootFiles @('.daaf-symlinks', '.daaf-permissions') -ExcludeRootDirs @('.daaf-claude-config')
            $m.Files | Should -Be 5
            $m.Bytes | Should -Be 3110
        }
    }

    Context "Verification structure" {
        It "never uses Get-ChildItem + SilentlyContinue as the authoritative count" {
            # The only remaining GCI calls are the progress display and the fallback
            # helper, which captures -ErrorVariable.
            $gci = @(($Content -split "`n") | Where-Object { $_ -match '^\s*[^#]*Get-ChildItem ' })
            $gci.Count | Should -Be 2
            ($gci -join "`n") | Should -Match '-ErrorVariable enumErrors'
            ($gci -join "`n") | Should -Match '\$Copied = @\(Get-ChildItem'
        }
        It "counts the host folder container-side via a read-only bind mount, by direct invocation" {
            $Content | Should -Match ([regex]::Escape('@(docker run --rm -v "${HostPath}:/b:ro" busybox sh -c $BackupCountProgram 2>&1)'))
            $Content | Should -Match ([regex]::Escape('$HostCountExit = $LASTEXITCODE'))
        }
        It "the backup-folder count uses the staged count's exact predicate and single-pass KB formula" {
            $stage = [regex]::Match($Content, "(?s)\`$StageProgram = @'\r?\n(.*?)\r?\n'@").Groups[1].Value
            $count = [regex]::Match($Content, "(?s)\`$BackupCountProgram = @'\r?\n(.*?)\r?\n'@").Groups[1].Value
            $line = 'counts=$(find . -type f ! -path ./.daaf-symlinks ! -path ./.daaf-permissions ! -path ./.daaf-claude-config/\* -exec stat -c %s {} + 2>/tmp/count_err | awk \{n++\;s+=\$1\}\ END\ \{print\ n+0,int\(s/1024\)\})'
            # Case-sensitive (-MatchExactly): an identity claim on program text.
            $stage | Should -MatchExactly ([regex]::Escape($line))
            $count | Should -MatchExactly ([regex]::Escape($line))
            # The visibility sentinel (empty bind mount -> fallback, review B1).
            $count | Should -MatchExactly ([regex]::Escape('if test -e ./.daaf-symlinks; then seen=1; fi'))
            $count | Should -MatchExactly ([regex]::Escape('echo BACKUP_SENTINEL=$seen'))
            # Read errors withhold the count (review round 2, F1).
            $count | Should -MatchExactly ([regex]::Escape(': > /tmp/count_err'))
            $count | Should -MatchExactly ([regex]::Escape('echo BACKUP_COUNT_ERRORS=$(grep -c ^ /tmp/count_err)'))
            # Both quote-free (PS 5.1 argv; the .sh twin's parity extractor).
            $count | Should -Not -Match '["'']'
            $stage | Should -Not -Match '"'
        }
        It "requires BACKUP_SENTINEL=1 before trusting the container-side count" {
            $Content | Should -Match ([regex]::Escape("if ((Get-DaafCountMarker -Lines `$HostCountOutput -Name 'BACKUP_SENTINEL') -eq 1) {"))
            $Content | Should -Match ([regex]::Escape('$HostCountBlind = $true'))
        }
        It "empty-guards the data-volume staging container removal in its finally" {
            $Content | Should -Match '(?s)if \(-not \[string\]::IsNullOrEmpty\(\$StageCid\)\) \{\s+\$innerEAP = \$ErrorActionPreference; \$ErrorActionPreference = "SilentlyContinue"\s+\$null = docker rm -f \$StageCid 2>&1'
        }
        It "counts Claude state with the staged predicate on the fallback path too" {
            $Content | Should -Match ([regex]::Escape('$ClaudeFallback = Measure-DaafBackupTree -Root $ClaudeDestPath -ExcludeRootFiles @($SymlinksManifest, $PermissionsManifest) -ExcludeRootDirs @($ClaudeSubDir)'))
        }
        It "starts the staging container's try/finally before docker wait (no leak window)" {
            $cidIdx = $Content.IndexOf('$stageStartOk = ($LASTEXITCODE -eq 0')
            $tryIdx = $Content.IndexOf('try {', $cidIdx)
            $waitIdx = $Content.IndexOf('$StageStatusRaw = (docker wait $StageCid')
            $finallyIdx = $Content.IndexOf('} finally {', $waitIdx)
            $rmIdx = $Content.IndexOf('$null = docker rm -f $StageCid 2>&1', $finallyIdx)
            $tryIdx | Should -BeGreaterThan $cidIdx
            $waitIdx | Should -BeGreaterThan $tryIdx
            # The first finally after the wait is the one that removes the container.
            $rmIdx | Should -BeGreaterThan $finallyIdx
            $Content.IndexOf('} finally {', $tryIdx) | Should -Be $finallyIdx
            # And no exit inside it: the staging failure only sets a flag.
            $Content.Substring($tryIdx, $finallyIdx - $tryIdx) | Should -Not -Match '(?m)Wait-AndExit|^\s*exit\b'
        }
        It "reads the snapshot markers from docker logs BEFORE the copy's finally removes the container" {
            $logsIdx = $Content.IndexOf('$StageDoneLog = @(docker logs $StageCid 2>&1)')
            $finallyRm = $Content.IndexOf('} finally {', $logsIdx)
            $logsIdx | Should -BeGreaterThan -1
            $finallyRm | Should -BeGreaterThan $logsIdx
        }
        It "applies ZERO tolerance with staged counts and keeps 1% only on the fallback path" {
            $Content | Should -Match '(?s)if \(\$HaveStagedCounts\) \{\s+\$CountTolerance = 0\s+\$ExpectedLabel = "Snapshot"\s+\} else \{\s+\$CountTolerance = \[math\]::Max\(1'
            $Content | Should -Match '(?s)if \(\$HaveStagedCounts\) \{\s+\$ToleranceKB = 0\s+\} else \{\s+\$ToleranceKB = \[math\]::Max\(1'
        }
        It "latches HadWarnings when the PowerShell fallback count is a lower bound" {
            $idx = $Content.IndexOf('if ($Fallback.Errors -gt 0) {')
            $idx | Should -BeGreaterThan -1
            $Content.Substring($idx, 600) | Should -Match '\$HadWarnings = \$true'
        }
        It "long-path notice is informational: it never latches HadWarnings" {
            $idx = $Content.IndexOf('if ($LongPathFiles -gt 0) {')
            $end = $Content.IndexOf('Write-Host ""', $idx)
            $idx | Should -BeGreaterThan -1
            $Content.Substring($idx, $end - $idx) | Should -Not -Match 'HadWarnings'
        }
        It "S5: the scan still returns 6 parseable lines when the informational long-path segment fails" -Skip:(($PSVersionTable.PSVersion.Major -lt 6) -or $IsWindows) {
            # Expand the REAL scan string the way PowerShell would ($LongPathMinRel and
            # the backtick-escaped `$1/`$0), point /source at a fixture, and run it
            # under the local sh (dash + mawk here, not busybox). Then break ONLY the
            # long-path segment: the grouped `{ ... || echo 0; }` must turn that into 0
            # rather than failing the whole `&&` chain ("Could not scan").
            $line = @(($Content -split "`n") | Where-Object { $_ -match '^\$ScanOutput = docker run' })[0]
            $m = [regex]::Match($line, 'busybox sh -c "(.*)"\s*$')
            $m.Success | Should -BeTrue
            # Set-Variable: the value is consumed by ExpandString, which the analyzer's
            # used-variable rule cannot see.
            Set-Variable -Name LongPathMinRel -Value 10
            $expanded = $ExecutionContext.InvokeCommand.ExpandString($m.Groups[1].Value)
            $src = Join-Path $TestDrive ('scan-' + [guid]::NewGuid().ToString('N'))
            $null = New-Item -ItemType Directory -Path (Join-Path $src 'a-rather-long-folder-name')
            [IO.File]::WriteAllText((Join-Path $src 'x.txt'), 'x')
            [IO.File]::WriteAllText((Join-Path $src 'a-rather-long-folder-name/y.txt'), 'y')
            $prog = $expanded.Replace('/source', $src)
            $out = @(& sh -c $prog)
            $LASTEXITCODE | Should -Be 0
            $out.Count | Should -Be 6
            $out[0].Trim() | Should -Be '2'
            $broken = [regex]::Replace($prog, '\{ find \S+ -type f \| awk -v m=10 .*? \|\| echo 0; \}', '{ false || echo 0; }')
            $broken | Should -Not -Be $prog
            $out = @(& sh -c $broken)
            $LASTEXITCODE | Should -Be 0
            $out.Count | Should -Be 6
            $out[5].Trim() | Should -Be '0'
        }
        It "computes the long-path threshold before New-Item creates the backup folder" {
            $Content.IndexOf('$LongPathMinRel = 260 - $BackupPathPrefixLen') | Should -BeLessThan $Content.IndexOf('New-Item -ItemType Directory -Path $BackupName')
        }
        It "is ASCII-only with no BOM" {
            $bytes = [IO.File]::ReadAllBytes("$RepoRoot/scripts/host/backup_daaf.ps1")
            @($bytes | Where-Object { $_ -gt 127 }).Count | Should -Be 0
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

    It "parses the 5-line scan mock and prints the special-file skip note" {
        # The dry-run docker mock emits a 5th scan line of 2 (twin of the .sh mock).
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/backup_daaf.ps1" *>&1
        ($output | Out-String) | Should -BeLike "*Note: skipping 2 named pipe/socket/device file(s) -- runtime-only, not backed up.*"
    }

    It "parses the 6th scan line and prints the long-path notice" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/backup_daaf.ps1" *>&1
        ($output | Out-String) | Should -BeLike "*Note: 3 file(s) will have paths longer than Windows' 260-character limit in*"
    }

    It "F4: names the resolved Source volume under the Backup name, honouring DAAF_PROJECT_NAME and DAAF_DATA_VOLUME_NAME" {
        # Review round 2: a user diffed a backup against the wrong install's volume
        # because the output never said which volume was backed up.
        $saved = @{ P = $env:DAAF_PROJECT_NAME; V = $env:DAAF_DATA_VOLUME_NAME }
        Push-Location -LiteralPath $TestDrive
        try {
            $env:DAAF_DRY_RUN = "1"
            $env:DAAF_NESTED = "1"
            $env:DAAF_PROJECT_NAME = "daaf2"
            Remove-Item Env:DAAF_DATA_VOLUME_NAME -ErrorAction SilentlyContinue
            $out = & "$RepoRoot/scripts/host/backup_daaf.ps1" *>&1 | Out-String
            $out | Should -BeLike "*Source volume: daaf2_daaf-data*"
            $env:DAAF_DATA_VOLUME_NAME = "gpt_sub_daaf-data"
            $out = & "$RepoRoot/scripts/host/backup_daaf.ps1" *>&1 | Out-String
            $out | Should -BeLike "*Source volume: gpt_sub_daaf-data*"
            $out | Should -Not -BeLike "*daaf2_daaf-data*"
            $lines = @($out -split "\r?\n")
            $i = -1
            for ($k = 0; $k -lt $lines.Count; $k++) { if ($lines[$k].StartsWith('Backup name: ')) { $i = $k; break } }
            $i | Should -BeGreaterThan -1
            $lines[$i + 1] | Should -BeExactly 'Source volume: gpt_sub_daaf-data'
        } finally {
            Pop-Location
            $env:DAAF_PROJECT_NAME = $saved.P
            $env:DAAF_DATA_VOLUME_NAME = $saved.V
        }
    }
}

# ============================================================================
# End-to-end copy path with a fake `docker` executable on PATH (non-Windows)
# ============================================================================
# Runs the REAL script past the dry-run exit: scan parse, staging launch/wait, the
# Start-Process `docker cp` + handle cache + exit-code read, and the verification
# branches. A bash fake `docker` (written to $TestDrive) models each subcommand,
# driven by FAKE_* env vars. Linux/macOS only: the fake is a shell script, and the
# Windows-only ExitCode-null quirk is not reproducible here -- these cases prove the
# plumbing and branch logic, not the quirk itself.

Describe "backup_daaf.ps1 end-to-end copy path (fake docker)" -Skip:(($PSVersionTable.PSVersion.Major -lt 6) -or $IsWindows) {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:SavedEnv = @{}
        foreach ($k in @('PATH', 'DAAF_DRY_RUN', 'DAAF_NESTED', 'DAAF_TEST_MODE', 'DAAF_PROJECT_NAME', 'DAAF_DATA_VOLUME_NAME')) {
            $script:SavedEnv[$k] = [Environment]::GetEnvironmentVariable($k, 'Process')
        }
        Remove-Item Env:DAAF_DRY_RUN, Env:DAAF_TEST_MODE, Env:DAAF_PROJECT_NAME, Env:DAAF_DATA_VOLUME_NAME -ErrorAction SilentlyContinue
        $env:DAAF_NESTED = "1"

        $script:FakeBin = Join-Path $TestDrive 'bin'
        $null = New-Item -ItemType Directory -Force -Path $script:FakeBin
        $fakeDocker = @'
#!/usr/bin/env bash
# Fake docker for backup_daaf.Tests.ps1 (end-to-end). FAKE_* env vars drive it.
case "${1:-}" in
    info) exit 0 ;;
    volume)
        # Data volume exists; the Claude-config volume does not (skip that block).
        case "$*" in *claude-config*) exit 1 ;; esac
        exit 0 ;;
    run)
        if [ "${2:-}" = "-d" ]; then echo stagecid0000; exit 0; fi
        # Permission-manifest scan: no exec files.
        case "$*" in *"-perm -0100"*) exit 0 ;; esac
        case "$*" in *":/b:ro"*)
            # Container-side backup-folder count. The -v value must arrive as ONE
            # argument ("<host path>:/b:ro") naming an existing folder -- a spaced
            # path that split would fail here. Then run the REAL program under the
            # local sh with its `cd /b` pointed at that folder (GNU find, not
            # busybox: same predicates).
            [ "${FAKE_COUNT_FAIL:-0}" = "1" ] && exit 1
            [ "$3" = "-v" ] || { echo "fake docker: expected -v as 3rd arg" >&2; exit 64; }
            host="${4%:/b:ro}"
            [ -d "${host}" ] || { echo "fake docker: bind source is not a folder: ${host}" >&2; exit 65; }
            # FAKE_EMPTY_MOUNT=1 models Docker Desktop presenting an EMPTY folder for
            # the bind mount (docker/for-win#14271): the program sees nothing.
            if [ "${FAKE_EMPTY_MOUNT:-0}" = "1" ]; then
                host="$(dirname "${host}")/empty-mount-view"
                mkdir -p "${host}"
            fi
            prog="${!#}"
            # The program's container /tmp/ (its /tmp/count_err) is relocated to a
            # private mktemp dir (under TMPDIR when set), removed after the run.
            ctmp="$(mktemp -d)"
            FAKE_B="${host}" sh -c "$(printf '%s\n' "${prog}" | sed -e 's#^cd /b$#cd "$FAKE_B"#' -e "s#/tmp/#${ctmp}/#g")"
            rc=$?
            rm -rf "${ctmp}"
            exit "${rc}" ;;
        esac
        # Volume scan: count, du -sk, du -sh, logical KB (0 skips the size check),
        # then the optional 5th special-file line and 6th long-path line.
        printf '%s\n' "${FAKE_SCAN_COUNT:-0}" "$(printf '512\t/source')" '500K' '0'
        if [ -n "${FAKE_SPECIAL:-}" ]; then printf '%s\n' "${FAKE_SPECIAL}"; fi
        if [ -n "${FAKE_LONG:-}" ]; then printf '%s\n' "${FAKE_LONG}"; fi
        exit 0 ;;
    wait) echo 0; exit 0 ;;
    logs)
        # Snapshot markers from the (detached) staging container's log.
        [ "${FAKE_LOGS_FAIL:-0}" = "1" ] && exit 1
        printf '%b' "${FAKE_STAGE_LOG:-}"
        exit 0 ;;
    cp)
        # `docker cp SRC DEST` is exactly three argv entries. More means the caller
        # let a spaced destination split (the Start-Process -ArgumentList array bug):
        # fail loudly, as real docker would, instead of copying somewhere else.
        if [ "$#" -ne 3 ]; then
            echo "fake docker: cp expects 3 arguments, got $#" >&2
            exit 64
        fi
        dest="${!#}"
        mkdir -p "${dest}"
        i=0
        while [ "${i}" -lt "${FAKE_CP_FILES:-0}" ]; do
            : > "${dest}/f${i}"
            i=$((i + 1))
        done
        # The staged tree always carries the root .daaf-symlinks manifest (the
        # visibility sentinel); FAKE_CP_NO_MANIFEST=1 models a copy that lost it.
        [ "${FAKE_CP_NO_MANIFEST:-0}" = "1" ] || : > "${dest}/.daaf-symlinks"
        # FAKE_CP_LOCKED=1 adds a folder PowerShell cannot read (stand-in for the
        # Windows path-length skip): its one file makes the fallback a lower bound.
        if [ "${FAKE_CP_LOCKED:-0}" = "1" ]; then
            mkdir -p "${dest}/locked"
            : > "${dest}/locked/hidden"
            chmod 000 "${dest}/locked"
        fi
        exit "${FAKE_CP_EXIT:-0}" ;;
    *) exit 0 ;;
esac
'@
        $fakePath = Join-Path $script:FakeBin 'docker'
        [System.IO.File]::WriteAllText($fakePath, ($fakeDocker -replace "`r", ""))
        & chmod +x $fakePath
        $env:PATH = $script:FakeBin + [System.IO.Path]::PathSeparator + $script:SavedEnv['PATH']

        function Invoke-FakeBackup {
            param([int]$ScanCount, [string]$Special = "", [int]$CpFiles, [int]$CpExit = 0, [string]$WorkPrefix = "run-",
                [string]$StageLog = "", [string]$Long = "", [switch]$CountFail, [switch]$LogsFail,
                [switch]$EmptyMount, [switch]$NoManifest, [switch]$Locked)
            $env:FAKE_SCAN_COUNT = "$ScanCount"
            $env:FAKE_CP_FILES = "$CpFiles"
            $env:FAKE_CP_EXIT = "$CpExit"
            if ($Special -ne "") { $env:FAKE_SPECIAL = $Special } else { Remove-Item Env:FAKE_SPECIAL -ErrorAction SilentlyContinue }
            if ($Long -ne "") { $env:FAKE_LONG = $Long } else { Remove-Item Env:FAKE_LONG -ErrorAction SilentlyContinue }
            $env:FAKE_STAGE_LOG = $StageLog
            if ($CountFail) { $env:FAKE_COUNT_FAIL = "1" } else { $env:FAKE_COUNT_FAIL = "0" }
            if ($LogsFail) { $env:FAKE_LOGS_FAIL = "1" } else { $env:FAKE_LOGS_FAIL = "0" }
            if ($EmptyMount) { $env:FAKE_EMPTY_MOUNT = "1" } else { $env:FAKE_EMPTY_MOUNT = "0" }
            if ($NoManifest) { $env:FAKE_CP_NO_MANIFEST = "1" } else { $env:FAKE_CP_NO_MANIFEST = "0" }
            if ($Locked) { $env:FAKE_CP_LOCKED = "1" } else { $env:FAKE_CP_LOCKED = "0" }
            # Per-run working dir: the script writes its backup folder into CWD, so
            # $WorkPrefix controls whether the backup destination path has a space.
            $work = Join-Path $TestDrive ($WorkPrefix + [guid]::NewGuid().ToString('N'))
            $null = New-Item -ItemType Directory -Path $work
            Push-Location -LiteralPath $work
            try {
                $out = & "$RepoRoot/scripts/host/backup_daaf.ps1" *>&1 | Out-String
                $code = $LASTEXITCODE
            } finally {
                Pop-Location
                # Re-open any locked fixture folder so TestDrive cleanup can remove it.
                foreach ($lk in @(Get-ChildItem -LiteralPath $work -Recurse -Directory -Filter 'locked' -ErrorAction SilentlyContinue)) {
                    & chmod 755 $lk.FullName
                }
            }
            [pscustomobject]@{ Output = $out; ExitCode = $code }
        }
    }

    AfterAll {
        foreach ($k in $script:SavedEnv.Keys) {
            [Environment]::SetEnvironmentVariable($k, $script:SavedEnv[$k], 'Process')
        }
        Remove-Item Env:FAKE_SCAN_COUNT, Env:FAKE_CP_FILES, Env:FAKE_CP_EXIT, Env:FAKE_SPECIAL, Env:FAKE_LONG, Env:FAKE_STAGE_LOG, Env:FAKE_COUNT_FAIL, Env:FAKE_LOGS_FAIL, Env:FAKE_EMPTY_MOUNT, Env:FAKE_CP_NO_MANIFEST, Env:FAKE_CP_LOCKED -ErrorAction SilentlyContinue
    }

    # --- Review round 1 fixes (B1 empty bind mount, I2 wording, I3 lower bound) ---

    It "B1: an empty bind-mount view (no sentinel) falls back to PowerShell instead of reporting 0 files" {
        $r = Invoke-FakeBackup -ScanCount 3 -CpFiles 3 -StageLog 'STAGED_FILES=3\nSTAGED_KB=0\n' -EmptyMount
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*Docker could not see the files in the backup folder*"
        $r.Output | Should -Not -BeLike "*0 files were copied*"
        $r.Output | Should -Not -BeLike "*Backup failed*"
        $r.Output | Should -BeLike "*Files:    3 files copied*"
        # A Note, not a warning: the copy itself is unaffected.
        $r.Output | Should -BeLike "*Backup complete!*"
    }

    It "B1: a backup missing its .daaf-symlinks manifest is a WARNING (the copy lost a file)" {
        $r = Invoke-FakeBackup -ScanCount 3 -CpFiles 3 -StageLog 'STAGED_FILES=3\nSTAGED_KB=0\n' -NoManifest
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*missing its .daaf-symlinks file*"
        $r.Output | Should -BeLike "*Backup completed WITH WARNINGS*"
    }

    It "I2: a shortfall against the snapshot is reported as missing files, not 'may be incomplete'" {
        $r = Invoke-FakeBackup -ScanCount 4 -CpFiles 3 -StageLog 'STAGED_FILES=4\nSTAGED_KB=0\n'
        $r.Output | Should -BeLike "*1 file(s) from the snapshot are missing from this backup. Do not rely on it.*"
        $r.Output | Should -BeLike "*re-running will not fix*"
        $r.Output | Should -Not -BeLike "*may be incomplete*"
    }

    It "I2: EXTRA files against the snapshot are reported as extras, with the data complete" {
        $r = Invoke-FakeBackup -ScanCount 2 -CpFiles 3 -StageLog 'STAGED_FILES=2\nSTAGED_KB=0\n'
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*Snapshot: 2 files, Backup: 3 files (difference: 1)*"
        $r.Output | Should -BeLike "*files that are not in the snapshot*"
        $r.Output | Should -BeLike "*The DAAF data itself appears complete.*"
        $r.Output | Should -Not -BeLike "*missing from this backup*"
        $r.Output | Should -BeLike "*Backup completed WITH WARNINGS*"
    }

    It "I2: a KB mismatch with equal counts says the file contents differ" {
        $r = Invoke-FakeBackup -ScanCount 2 -CpFiles 2 -StageLog 'STAGED_FILES=2\nSTAGED_KB=5\n'
        $r.Output | Should -Not -BeLike "*file-count mismatch*"
        $r.Output | Should -BeLike "*the file contents differ in size from the*"
        $r.Output | Should -Not -BeLike "*may be incomplete*"
    }

    It "I3: a nonzero copy exit with a short LOWER-BOUND count is a WARNING, not the fatal error" -Skip:((& id -u) -eq '0') {
        # Container count fails -> PowerShell fallback; the locked folder makes it a
        # lower bound (3+). Snapshot 4 + exit 1 used to trip the corroborated fatal.
        $r = Invoke-FakeBackup -ScanCount 4 -CpFiles 3 -CpExit 1 -StageLog 'STAGED_FILES=4\nSTAGED_KB=0\n' -CountFail -Locked
        $r.ExitCode | Should -Be 0
        $r.Output | Should -Not -BeLike "*must not be relied on*"
        $r.Output | Should -BeLike "*That count is a lower bound*"
        $r.Output | Should -BeLike "*Snapshot: 4 files, Backup: 3+ files (difference: up to 1; the backup count is a lower bound)*"
        $r.Output | Should -BeLike "*cannot tell whether these*"
        $r.Output | Should -BeLike "*Backup completed WITH WARNINGS*"
    }

    # --- Review round 2 fixes (F1 read errors, F5a lower-bound zero, F5c next step) ---

    It "F1: a Docker count that hits a read error is UNAVAILABLE, never an exact short count" -Skip:((& id -u) -eq '0') {
        # No -CountFail: the REAL $BackupCountProgram runs and its `find` cannot read
        # the locked folder. Before the fix it printed BACKUP_FILES=3 with the sentinel
        # and exit 0, trusted as exact: "1 file(s) from the snapshot are missing".
        $r = Invoke-FakeBackup -ScanCount 4 -CpFiles 3 -StageLog 'STAGED_FILES=4\nSTAGED_KB=0\n' -Locked
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*Docker hit 1 read error(s) while counting the backup folder*"
        $r.Output | Should -Not -BeLike "*missing from this backup*"
        $r.Output | Should -Not -BeLike "*must not be relied on*"
        $r.Output | Should -BeLike "*Snapshot: 4 files, Backup: 3+ files (difference: up to 1; the backup count is a lower bound)*"
        $r.Output | Should -BeLike "*Backup completed WITH WARNINGS*"
    }

    It "F1: the same read error with a nonzero copy exit is still NOT the fatal short-copy branch" -Skip:((& id -u) -eq '0') {
        $r = Invoke-FakeBackup -ScanCount 4 -CpFiles 3 -CpExit 1 -StageLog 'STAGED_FILES=4\nSTAGED_KB=0\n' -Locked
        $r.ExitCode | Should -Be 0
        $r.Output | Should -Not -BeLike "*must not be relied on*"
        $r.Output | Should -BeLike "*That count is a lower bound*"
    }

    It "F5a: a lower-bound count of 0 says the backup could not be verified, never 'volume may be empty'" -Skip:((& id -u) -eq '0') {
        $r = Invoke-FakeBackup -ScanCount 1 -CpFiles 0 -StageLog 'STAGED_FILES=1\nSTAGED_KB=0\n' -Locked
        $r.ExitCode | Should -Be 1
        $r.Output | Should -BeLike "*ERROR: The backup could not be verified*"
        $r.Output | Should -BeLike "*This does not show the backup is*"
        $r.Output | Should -Not -BeLike "*may be empty*"
        $r.Output | Should -Not -BeLike "*0 of 1 expected files were copied*"
    }

    It "F5c: the missing-manifest WARNING tells the user to re-run" {
        $r = Invoke-FakeBackup -ScanCount 3 -CpFiles 3 -StageLog 'STAGED_FILES=3\nSTAGED_KB=0\n' -NoManifest
        $r.Output | Should -BeLike "*Re-run the backup; restoring this one would not recreate symbolic links.*"
    }

    It "F4: prints the Source volume line with the resolved name (default)" {
        $r = Invoke-FakeBackup -ScanCount 3 -CpFiles 3 -StageLog 'STAGED_FILES=3\nSTAGED_KB=0\n'
        $r.Output | Should -BeLike "*Source volume: daaf_daaf-data*"
    }

    It "I3: the same shortfall with an EXACT count stays fatal" {
        $r = Invoke-FakeBackup -ScanCount 4 -CpFiles 3 -CpExit 1 -StageLog 'STAGED_FILES=4\nSTAGED_KB=0\n'
        $r.ExitCode | Should -Be 1
        $r.Output | Should -BeLike "*ERROR: Backup failed (exit code 1); only 3 of 4 expected files were copied.*"
    }

    # --- Snapshot count, container-side verification, long-path notice (2026-09-29) ---
    # The fake copies FAKE_CP_FILES empty files; the container-side count is the REAL
    # $BackupCountProgram run against that folder, so these cases exercise the
    # marker parse, the zero-tolerance comparison and the fallbacks end to end.

    It "snapshot markers + container-side count agree: Snapshot line, plain banner" {
        $r = Invoke-FakeBackup -ScanCount 3 -CpFiles 3 -StageLog 'STAGED_FILES=3\nSTAGED_KB=0\n'
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*Snapshot: 3 files.*"
        $r.Output | Should -Not -BeLike "*Could not*"
        $r.Output | Should -BeLike "*Progress: 3 / 3 files (100%)*"
        $r.Output | Should -BeLike "*Files:    3 files copied*"
        $r.Output | Should -BeLike "*Backup complete!*"
    }

    It "zero tolerance: a 1-file shortfall against the snapshot warns (1% floor would hide it)" {
        $r = Invoke-FakeBackup -ScanCount 4 -CpFiles 3 -StageLog 'STAGED_FILES=4\nSTAGED_KB=0\n'
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*WARNING: Backup file-count mismatch.*"
        $r.Output | Should -BeLike "*Snapshot: 4 files, Backup: 3 files (difference: 1)*"
        $r.Output | Should -BeLike "*Backup completed WITH WARNINGS*"
    }

    It "zero tolerance: a KB mismatch against the snapshot warns" {
        # Files are empty (0 KB); the snapshot claims 5 KB.
        $r = Invoke-FakeBackup -ScanCount 2 -CpFiles 2 -StageLog 'STAGED_FILES=2\nSTAGED_KB=5\n'
        $r.Output | Should -BeLike "*WARNING: Backup size mismatch.*"
        $r.Output | Should -BeLike "*Snapshot: 5 KB, Backup: 0 KB*"
        $r.Output | Should -BeLike "*Backup completed WITH WARNINGS*"
    }

    It "snapshot differing from the live scan is explained and is the verification target" {
        $r = Invoke-FakeBackup -ScanCount 5 -CpFiles 2 -StageLog 'STAGED_FILES=2\nSTAGED_KB=0\n'
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*Snapshot: 2 files (3 fewer than the scan*"
        $r.Output | Should -Not -BeLike "*mismatch*"
        $r.Output | Should -BeLike "*Backup complete!*"
    }

    It "missing, garbage, or unreadable markers fall back to the scan (1% tolerance) with a Note" {
        foreach ($case in @(@{ Log = '' }, @{ Log = 'STAGED_FILES=abc\nSTAGED_KB=0\n' }, @{ Log = 'STAGED_FILES=3\n' },
                            @{ Log = 'STAGED_FILES=99999999999999999999\nSTAGED_KB=0\n' }, @{ Log = 'STAGED_FILES=3\nSTAGED_KB=0\n'; Fail = $true })) {
            # Scan 2, copy 3: diff 1 is inside the fallback's floor-1 tolerance.
            $r = Invoke-FakeBackup -ScanCount 2 -CpFiles 3 -StageLog $case.Log -LogsFail:([bool]$case['Fail'])
            $r.ExitCode | Should -Be 0 -Because "log case [$($case.Log)]"
            $r.Output | Should -BeLike "*Could not read the snapshot's file count*"
            $r.Output | Should -Not -BeLike "*mismatch*"
            $r.Output | Should -BeLike "*Backup complete!*"
        }
    }

    It "container-side count failure falls back to PowerShell, says so, and still verifies" {
        $r = Invoke-FakeBackup -ScanCount 3 -CpFiles 3 -StageLog 'STAGED_FILES=3\nSTAGED_KB=0\n' -CountFail
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*Could not count the backup folder inside Docker (exit 1)*"
        $r.Output | Should -Not -BeLike "*LOWER BOUND*"
        $r.Output | Should -BeLike "*Backup complete!*"
    }

    It "a backup path with a space reaches the container-side count as ONE -v argument" {
        $r = Invoke-FakeBackup -ScanCount 3 -CpFiles 3 -StageLog 'STAGED_FILES=3\nSTAGED_KB=0\n' -WorkPrefix "OneDrive - Org "
        $r.Output | Should -Not -BeLike "*fake docker:*"
        $r.Output | Should -Not -BeLike "*Could not count the backup folder inside Docker*"
        $r.Output | Should -BeLike "*Backup complete!*"
    }

    It "long-path notice prints from scan index [5] and does NOT latch warnings" {
        $r = Invoke-FakeBackup -ScanCount 3 -Special "0" -Long "7" -CpFiles 3 -StageLog 'STAGED_FILES=3\nSTAGED_KB=0\n'
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*Note: 7 file(s) will have paths longer than Windows' 260-character limit in*"
        $r.Output | Should -BeLike "*C:\daaf*"
        $r.Output | Should -BeLike "*Backup complete!*"
    }

    It "non-numeric long-path line reads as 0 (no notice, no strict-mode crash)" {
        $r = Invoke-FakeBackup -ScanCount 3 -Special "0" -Long "abc" -CpFiles 3 -StageLog 'STAGED_FILES=3\nSTAGED_KB=0\n'
        $r.ExitCode | Should -Be 0
        $r.Output | Should -Not -BeLike "*260-character*"
        $r.Output | Should -BeLike "*Backup complete!*"
    }

    It "clean copy with special files: prints the skip note and a plain banner" {
        $r = Invoke-FakeBackup -ScanCount 3 -Special "4" -CpFiles 3 -CpExit 0
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*Note: skipping 4 named pipe/socket/device file(s) -- runtime-only, not backed up.*"
        $r.Output | Should -BeLike "*Backup complete!*"
        $r.Output | Should -Not -BeLike "*WITH WARNINGS*"
        $r.Output | Should -Not -BeLike "*exit code could not be read*"
    }

    It "older 4-line scan (no special line) runs clean under strict mode with no note" {
        $r = Invoke-FakeBackup -ScanCount 3 -CpFiles 3 -CpExit 0
        $r.ExitCode | Should -Be 0
        $r.Output | Should -Not -BeLike "*Note: skipping*"
        $r.Output | Should -BeLike "*Backup complete!*"
    }

    It "nonzero docker cp exit with a short count is read (not coerced) and is fatal" {
        $r = Invoke-FakeBackup -ScanCount 5 -CpFiles 2 -CpExit 1
        $r.ExitCode | Should -Be 1
        $r.Output | Should -BeLike "*ERROR: Backup failed (exit code 1); only 2 of 5 expected files were copied.*"
        $r.Output | Should -BeLike "*must not be relied on*"
    }

    It "nonzero docker cp exit with a full count prints the Note, completes (exit 0), and latches WITH WARNINGS" {
        # The copy itself flagged a problem, so the banner must not claim an
        # unqualified success -- but with no shortfall the run is not fatal. (The
        # Claude-config volume is absent in this fake, so the Note is the ONLY
        # warning source on this run.)
        $r = Invoke-FakeBackup -ScanCount 3 -CpFiles 3 -CpExit 1
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*Note: File copy reported warnings (exit code 1); 3 of 3 expected files were transferred.*"
        $r.Output | Should -Not -BeLike "*must not be relied on*"
        $r.Output | Should -BeLike "*Backup completed WITH WARNINGS -- verify before relying on it*"
        $r.Output | Should -Not -BeLike "*Backup complete!*"
    }

    It "a backup destination under a folder with a space reaches docker cp as ONE argument" {
        # F4 regression: the old array -ArgumentList split "$HostPath" at the space,
        # so docker cp got 4+ arguments (the fake exits 64) and nothing landed.
        $r = Invoke-FakeBackup -ScanCount 3 -CpFiles 3 -CpExit 0 -WorkPrefix "run with space-"
        $r.Output | Should -Not -BeLike "*cp expects 3 arguments*"
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*Progress: 3 / 3 files (100%)*"
        $r.Output | Should -BeLike "*Backup complete!*"
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
            $Content | Should -Match '\$CopyExitCode -ne 0 -and \$FileCount -lt \$ExpectedFiles'
            $Content | Should -Match 'only \$FileCountLabel of \$ExpectedFiles expected files were copied'
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

# ============================================================================
# FU5: docker programs as PowerShell itself expands them (5.1-safe syntax)
# ============================================================================
# No `sh`, no Linux-only skip, and only Windows PowerShell 5.1-safe syntax, so this
# block CAN run under 5.1. CI does not currently do so: .github/workflows/ci-scripts.yml
# runs Pester with `shell: pwsh` (PowerShell 7) on both its ubuntu-latest and
# windows-latest legs, so in CI this exercises PowerShell 7's expansion only. A 5.1
# Pester leg would need a CI workflow change (maintainer-only); until then a 5.1 run is
# local/manual. The REAL `docker run` line is lifted from the script
# and run through PowerShell's own parser and string expansion
# ([scriptblock]::Create + dot-invoke: the same rules as Invoke-Expression, without the
# analyzer's Invoke-Expression rule) against a `docker` FUNCTION that records its argv.
# A function takes precedence over docker.exe, so no Docker is needed. This pins what
# the expansion hands to docker; the native-argument layer that follows is why the
# program must carry no `"` and must not end in `\` (PS 5.1 re-quotes an argument
# containing a space, and a trailing backslash would escape that closing quote).
# Case-sensitive matchers throughout (-BeExactly / -MatchExactly / .Contains / -ceq):
# these are identity claims on program text. PS 5.1-safe syntax only.

Describe "backup/restore .ps1 docker programs under PowerShell's own expansion (FU5)" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:BackupText = [IO.File]::ReadAllText("$RepoRoot/scripts/host/backup_daaf.ps1")
        $script:RestoreText = [IO.File]::ReadAllText("$RepoRoot/scripts/host/restore_from_backup.ps1")
    }

    It "the REAL scan line hands docker the literal `${c% *} and `${c#* }, and interpolates ONLY `$LongPathMinRel" {
        $lines = @(($script:BackupText -split "`r?`n") | Where-Object { $_ -match '^\$ScanOutput = docker run' })
        $lines.Count | Should -Be 1
        $m = [regex]::Match($lines[0], 'busybox sh -c "(.*)"\s*$')
        $m.Success | Should -BeTrue
        $literal = $m.Groups[1].Value
        # At source level the only UNESCAPED `$` in the double-quoted program is
        # $LongPathMinRel; every other `$` is backtick-escaped for the container's sh.
        $unescaped = @([regex]::Matches($literal, '(?<!`)\$[A-Za-z_{(]+') | ForEach-Object { $_.Value })
        $unescaped.Count | Should -Be 1
        $unescaped[0] | Should -BeExactly '$LongPathMinRel'

        $cap = @{}
        function docker { $cap['Argv'] = $args; '42' }
        # Set-Variable: consumed by the lifted line, which the analyzer's
        # used-variable rule cannot see.
        Set-Variable -Name VolumeName -Value 'my vol_daaf-data'
        Set-Variable -Name LongPathMinRel -Value 173
        . ([scriptblock]::Create($lines[0]))

        $argv = @($cap['Argv'])
        $argv.Count | Should -Be 8
        $argv[0] | Should -BeExactly 'run'
        $argv[3] | Should -BeExactly 'my vol_daaf-data:/source:ro'
        $argv[6] | Should -BeExactly '-c'
        $prog = [string]$argv[7]
        $prog.Contains('echo ${c% *}') | Should -BeTrue
        $prog.Contains('echo ${c#* }') | Should -BeTrue
        $prog.Contains('c=$(find . -type f') | Should -BeTrue
        $prog.Contains('s+=$1}') | Should -BeTrue
        $prog.Contains('length($0) - 8 >= m') | Should -BeTrue
        $prog | Should -MatchExactly ([regex]::Escape('awk -v m=173 '))
        $prog.Contains('LongPathMinRel') | Should -BeFalse
        $prog.Contains('`') | Should -BeFalse
        $prog.Contains('"') | Should -BeFalse
        $prog.EndsWith('\') | Should -BeFalse
        # Exactly the source literal with the backtick escapes removed and ONLY
        # $LongPathMinRel substituted -- nothing else was interpolated or dropped.
        $expected = $literal.Replace('$LongPathMinRel', '173').Replace('`$', '$')
        ($prog -ceq $expected) | Should -BeTrue
    }

    It "`$BackupCountProgram (backup and restore) and `$StageProgram carry no double quote and no trailing backslash" {
        $pattern = "(?s)\`$BackupCountProgram = @'\r?\n(.*?)\r?\n'@"
        $backupCount = [regex]::Match($script:BackupText, $pattern)
        $restoreCount = [regex]::Match($script:RestoreText, $pattern)
        $stage = [regex]::Match($script:BackupText, "(?s)\`$StageProgram = @'\r?\n(.*?)\r?\n'@")
        $backupCount.Success | Should -BeTrue
        $restoreCount.Success | Should -BeTrue
        $stage.Success | Should -BeTrue
        foreach ($text in @($backupCount.Groups[1].Value, $restoreCount.Groups[1].Value, $stage.Groups[1].Value)) {
            $text.Length | Should -BeGreaterThan 0
            $text.Contains('"') | Should -BeFalse
            $text.TrimEnd().EndsWith('\') | Should -BeFalse
        }
        # Line endings aside, the two $BackupCountProgram copies are the same program.
        ($backupCount.Groups[1].Value.Replace("`r", '') -ceq $restoreCount.Groups[1].Value.Replace("`r", '')) | Should -BeTrue
    }

    It "the REAL post-restore count line hands docker the marker program verbatim (no double quote, no trailing backslash)" {
        $lines = @(($script:RestoreText -split "`r?`n") | Where-Object { $_ -match '^\$VerifyOutput = @\(docker run' })
        $lines.Count | Should -Be 1
        $cap = @{}
        function docker { $cap['Argv'] = $args; 'RESTORED_FILES=1' }
        Set-Variable -Name VolumeName -Value 'my vol_daaf-data'
        . ([scriptblock]::Create($lines[0]))

        $argv = @($cap['Argv'])
        $argv.Count | Should -Be 8
        $argv[3] | Should -BeExactly 'my vol_daaf-data:/dest:ro'
        $prog = [string]$argv[7]
        $prog.Contains(': > /tmp/count_err;') | Should -BeTrue
        $prog.Contains('2>/tmp/count_err | wc -l') | Should -BeTrue
        $prog.Contains('echo RESTORED_COUNT_ERRORS=$(grep -c ^ /tmp/count_err)') | Should -BeTrue
        $prog.Contains('echo RESTORED_FILES=$((n))') | Should -BeTrue
        $prog.Contains('"') | Should -BeFalse
        $prog.EndsWith('\') | Should -BeFalse
    }
}
