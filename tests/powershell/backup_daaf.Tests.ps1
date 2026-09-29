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
            $programLines[-1] | Should -Be $stripLine
            $programLines[-2] | Should -Be 'find /staging -type l -exec rm -f {} +'
        }

        It "scan appends a special-file count as the 5th line and parses it bounds-checked" {
            # Appended AFTER the four existing values (index contract unchanged). Under
            # Set-StrictMode 3.0 an out-of-range index throws, so index [4] is read only
            # when present, via TryParse (non-numeric/missing -> 0).
            $Content | Should -Match ([regex]::Escape("&& find /source \( -type p -o -type s -o -type b -o -type c \) | wc -l"""))
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

        # -----------------------------------------------------------------
        # Regression: fail-closed staging-status parse (boolean-gated TryParse)
        # -----------------------------------------------------------------
        # [int]::TryParse writes 0 into the [ref] on a parse FAILURE, so the old
        # `$null = [int]::TryParse(..., [ref]$StageStatus)` form silently overwrote the
        # fail-closed default with 0 whenever `docker wait` emitted a non-numeric last
        # line (a daemon error merged via 2>&1) -- flipping the fatal gate from "abort"
        # to "proceed to copy a partial staged tree." The fix parses into a temp var and
        # adopts it ONLY when TryParse returns $true (mirrors restore_from_backup.ps1:279).
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
                $Content | Should -Match ([regex]::Escape('if ($CopyExitKnown -and $CopyExitCode -ne 0 -and $FileCount -lt $TotalFiles) {'))
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
                $branch | Should -Match 'WARNING: The file copy''s exit code could not be read, and only \$FileCount of \$TotalFiles'
                $branch | Should -Match 'Note: The file copy''s exit code could not be read'
                $branch | Should -Match '\$HadWarnings = \$true'
                # The unknown zero-file case is an ERROR, not "volume may be empty".
                $Content | Should -Match ([regex]::Escape('} elseif (-not $CopyExitKnown -and $TotalFiles -gt 0) {'))
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
        # Volume scan: count, du -sk, du -sh, logical KB (0 skips the size check),
        # then the optional 5th special-file line.
        printf '%s\n' "${FAKE_SCAN_COUNT:-0}" "$(printf '512\t/source')" '500K' '0'
        if [ -n "${FAKE_SPECIAL:-}" ]; then printf '%s\n' "${FAKE_SPECIAL}"; fi
        exit 0 ;;
    wait) echo 0; exit 0 ;;
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
        exit "${FAKE_CP_EXIT:-0}" ;;
    *) exit 0 ;;
esac
'@
        $fakePath = Join-Path $script:FakeBin 'docker'
        [System.IO.File]::WriteAllText($fakePath, ($fakeDocker -replace "`r", ""))
        & chmod +x $fakePath
        $env:PATH = $script:FakeBin + [System.IO.Path]::PathSeparator + $script:SavedEnv['PATH']

        function Invoke-FakeBackup {
            param([int]$ScanCount, [string]$Special = "", [int]$CpFiles, [int]$CpExit = 0, [string]$WorkPrefix = "run-")
            $env:FAKE_SCAN_COUNT = "$ScanCount"
            $env:FAKE_CP_FILES = "$CpFiles"
            $env:FAKE_CP_EXIT = "$CpExit"
            if ($Special -ne "") { $env:FAKE_SPECIAL = $Special } else { Remove-Item Env:FAKE_SPECIAL -ErrorAction SilentlyContinue }
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
            }
            [pscustomobject]@{ Output = $out; ExitCode = $code }
        }
    }

    AfterAll {
        foreach ($k in $script:SavedEnv.Keys) {
            [Environment]::SetEnvironmentVariable($k, $script:SavedEnv[$k], 'Process')
        }
        Remove-Item Env:FAKE_SCAN_COUNT, Env:FAKE_CP_FILES, Env:FAKE_CP_EXIT, Env:FAKE_SPECIAL -ErrorAction SilentlyContinue
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
