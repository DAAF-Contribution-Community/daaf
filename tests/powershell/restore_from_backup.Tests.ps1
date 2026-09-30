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

        It "uses docker cp (not bind-mounted cp -a)" {
            # The copy mechanism is `docker create` + `docker cp` -- one for the
            # data volume, one for the Claude state volume -- and must NOT use the
            # old bind-mounted `cp -a /source` busybox copy.
            $Content | Should -Match 'docker create'
            $Content | Should -Match 'docker cp'
            $Content | Should -Not -Match 'cp -a /source'
        }

        It "repairs volume ownership after docker cp writes as root" {
            # `docker cp` INTO a container writes files as root; restore must chown
            # the volume back to appuser (UID 1000), matching daaf-init.
            $Content | Should -Match 'chown -R 1000:1000 /dest'
        }

        It "replays executable permissions from the manifest (Step 2d)" {
            # When ".daaf-permissions" is present, normalize files to 644 and
            # re-apply 755 to the manifest's paths (undoing NTFS mode loss).
            $Content | Should -Match '\.daaf-permissions'
            $Content | Should -Match 'find /dest -type f -exec chmod 644'
            $Content | Should -Match 'chmod 755'
        }

        It "skips normalization when the manifest is absent (backward compat)" {
            # No manifest => no normalization (blanket 644 would strip exec from
            # every script and be worse than the fabricated 0755). The absent-manifest
            # NOTE covers both an older backup AND a failed manifest write (Fix 3).
            $Content | Should -Match 'it may predate'
            $Content | Should -Match 'the manifest write may have failed during'
            $Content | Should -Match 'no normalization was applied'
        }

        It "replays symlinks from the manifest (Step 2e)" {
            # When ".daaf-symlinks" is present, recreate each link (path TAB target)
            # container-side, chown -h it to appuser, and strip the manifest.
            $Content | Should -Match '\.daaf-symlinks'
            $Content | Should -Match 'ln -sf -- '
            $Content | Should -Match 'chown -h 1000:1000'
        }

        It "passes the symlink-replay sh -c program without embedded double-quotes" {
            # The Step 2e replay program is shared logically with the .sh twin; an
            # embedded double quote would be re-parsed by the Windows C runtime and
            # mangle the argument. Assert the $symlinkReplayScript VALUE (text between
            # the outer PS delimiters) contains no double-quote char, and that it uses
            # the octal-printf BOM idiom (busybox sed has no \xNN escapes), not sed.
            # The BOM printf uses DOUBLE backslashes in the PS source so sh receives a
            # single backslash after its own unquoted-backslash processing.
            $replayLine = ($Content -split "`n") | Where-Object { $_ -match '\$symlinkReplayScript\s*=' }
            $replayLine | Should -Not -BeNullOrEmpty
            $value = ($replayLine -replace '^\s*\$symlinkReplayScript\s*=\s*"', '') -replace '"\s*$', ''
            $value | Should -Not -Match '"'
            $value | Should -Match "printf \\\\357\\\\273\\\\277"
        }

        It "invokes the symlink replay for BOTH the data volume AND the Claude volume" {
            # Regression guard for the review BLOCKER: an earlier draft ported the
            # symlink-replay call only to the DATA volume and silently omitted it from
            # the Claude-state restore block, so Claude-volume symlinks were never
            # recreated. A file-wide grep for ".daaf-symlinks" (or even for
            # "$symlinkReplayScript") PASSES on that broken state because the string is
            # present once -- which is exactly how the gap slipped through review. Assert
            # the program is actually INVOKED against two DISTINCT `/dest` volumes: one
            # bound to $VolumeName (data) and one bound to $ClaudeVolumeName (Claude).
            # Match the full `docker run ... sh -c $symlinkReplayScript` invocation lines
            # so a bare definition without a second call site cannot satisfy this.
            $invokeLines = ($Content -split "`n") | Where-Object {
                $_ -match 'docker run .*-v "\$\{[A-Za-z]+\}:/dest".*busybox sh -c \$symlinkReplayScript'
            }
            @($invokeLines).Count | Should -BeGreaterOrEqual 2
            # One invocation must bind the DATA volume, the other the CLAUDE volume.
            ($invokeLines -join "`n") | Should -Match '\$\{VolumeName\}:/dest'
            ($invokeLines -join "`n") | Should -Match '\$\{ClaudeVolumeName\}:/dest'
        }

        It "defines the symlink replay program unconditionally before the manifest probe" {
            # The program must be defined BEFORE the DATA-volume manifest probe so the
            # Claude-volume replay can reuse it even when the data volume had no symlink
            # manifest -- otherwise a Set-StrictMode read of an unset variable would
            # throw. Assert the definition precedes both the data-volume probe and the
            # Claude-restore block. Ordering is what makes the shared-program reuse safe.
            $defIdx    = $Content.IndexOf('$symlinkReplayScript =')
            $probeIdx  = $Content.IndexOf('$symlinkManifestPresent = ')
            # Anchor on the section-header marker (unique) rather than the bare phrase,
            # which also appears in an explanatory comment ABOVE the definition.
            $claudeIdx = $Content.IndexOf('--- Restore the Claude Code state volume ---')
            $defIdx    | Should -BeGreaterThan -1
            $probeIdx  | Should -BeGreaterThan $defIdx
            $claudeIdx | Should -BeGreaterThan $defIdx
        }

        It "passes the replay sh -c program without embedded double-quotes (Windows arg safety)" {
            # Regression: embedded " in a string passed to a native exe on Windows
            # is silently mangled by the C runtime (see shell-scripting gotchas.md).
            # The replay sh -c program is built with sh single-quotes and
            # backtick-escaped sh variables. Assert that the $replayScript VALUE (the
            # text between the outer PS delimiters) contains no double-quote chars:
            # after stripping the leading `$replayScript = "` and the trailing `"`,
            # no `"` may remain.
            $replayLine = ($Content -split "`n") | Where-Object { $_ -match '\$replayScript\s*=' }
            $replayLine | Should -Not -BeNullOrEmpty
            $value = ($replayLine -replace '^\s*\$replayScript\s*=\s*"', '') -replace '"\s*$', ''
            $value | Should -Not -Match '"'
            # And it must use the sh single-quote idioms, not double-quotes. The BOM is
            # stripped via octal printf (busybox sed has no \xNN escapes), NOT sed. The
            # regex needs a literal backslash before each octal group, hence \\ per byte.
            $value | Should -Match "printf '\\357\\273\\277'"
            $value | Should -Not -Match "sed '1s"
        }

        It "excludes both manifests and the Claude subfolder from the listing/scan counts" {
            # The listing loop and the Scanning-backup count must exclude BOTH root
            # manifests and the Claude subfolder so the counts (listing, scan,
            # verification, backup completion report) agree. The listing stays on
            # PowerShell (Measure-DaafBackupTree) and marks read errors with "+".
            $excl = '-ExcludeRootFiles @($PermissionsManifest, $SymlinksManifest) -ExcludeRootDirs @($ClaudeSubDir)'
            $Content | Should -Match ([regex]::Escape('$listing = Measure-DaafBackupTree -Root $dir.FullName ' + $excl))
            $Content | Should -Match ([regex]::Escape('if ($listing.Errors -gt 0) { $fileCount = "$($listing.Files)+" }'))
            $Content | Should -Match '\+ Claude state'
        }

        It "counts the SELECTED backup container-side (authoritative), with a never-silent fallback" {
            # 2026-09-29: Windows PowerShell 5.1 Get-ChildItem undercounted a backup
            # with long paths (72,834 vs 73,021) -- a spurious post-restore mismatch.
            $Content | Should -Match ([regex]::Escape('@(docker run --rm -v "${SelectedPath}:/b:ro" busybox sh -c $BackupCountProgram 2>&1)'))
            $Content | Should -Match ([regex]::Escape("Get-DaafCountMarker -Lines `$ScanCountOutput -Name 'BACKUP_FILES'"))
            $Content | Should -Match ([regex]::Escape('$ScanFallback = Measure-DaafBackupTree -Root $SelectedPath'))
            $Content | Should -Match ([regex]::Escape('$TotalFilesLabel = "$TotalFiles+"'))
            # No Get-ChildItem + SilentlyContinue count remains outside the helper.
            @(($Content -split "`n") | Where-Object { $_ -match '^\s*[^#]*Get-ChildItem .*-Recurse' }).Count | Should -Be 1
        }

        It "carries BYTE-IDENTICAL copies of backup_daaf.ps1's count helpers" {
            $backup = Get-Content "$RepoRoot/scripts/host/backup_daaf.ps1" -Raw
            foreach ($fn in @('Get-DaafCountMarker', 'Measure-DaafBackupTree')) {
                $pat = "(?ms)^function $fn \{.*?^\}"
                $a = [regex]::Match($backup, $pat).Value
                $b = [regex]::Match($Content, $pat).Value
                $a | Should -Not -BeNullOrEmpty
                # -BeExactly: -Be is case-INsensitive, which would pass a copy that
                # differs only in case (e.g. -contains vs -Contains) -- not byte identity.
                $b | Should -BeExactly $a -Because "$fn must stay byte-identical across backup/restore"
            }
        }

        It "is ASCII-only with no BOM" {
            $bytes = [IO.File]::ReadAllBytes("$RepoRoot/scripts/host/restore_from_backup.ps1")
            @($bytes | Where-Object { $_ -gt 127 }).Count | Should -Be 0
        }

        It "verifies file count after restore" {
            $Content | Should -Match 'Verifying restore'
        }

        It "includes file count mismatch check" {
            $Content | Should -Match 'File count mismatch'
        }

        It "latches a WITH WARNINGS completion banner without changing the exit code" {
            # Mirrors backup_daaf.ps1's $HadWarnings. One init; eight latch sites: the
            # lower-bound scan count, the permission and symlink replays, the unverified
            # post-restore count, the file-count mismatch, and the Claude-state clear,
            # copy and symlink replay. A new success-path WARNING must latch too (update
            # this count and backup_twin_parity.bats's restore latch pin together).
            ([regex]::Matches($Content, [regex]::Escape('$HadWarnings = $false'))).Count | Should -Be 1
            ([regex]::Matches($Content, [regex]::Escape('$HadWarnings = $true'))).Count | Should -Be 8
            $bannerLines = @(
                'if ($HadWarnings) {',
                '    Write-Host "  Restore completed WITH WARNINGS -- verify before relying on it"',
                '} else {',
                '    Write-Host "  Restore complete!"',
                '}'
            )
            $Content | Should -Match ((@($bannerLines | ForEach-Object { [regex]::Escape($_) })) -join '\r?\n')
            # The warnings run still ends on the success exit (callers branch on it).
            $Content | Should -Match 'Wait-AndExit 0\s*$'
        }

        It "counts the restored volume with the backup count's root exclusions, one stat line per file" {
            # Review round 2 (F5h): `find /dest -type f | wc -l` counted a root manifest
            # left behind by a failed replay (and newline names twice).
            # FU2 (2026-09-30): the count's stderr is captured in-container and the result
            # is a marker (RESTORED_FILES / RESTORED_COUNT_ERRORS) parsed with
            # Get-DaafCountMarker -- a merged stderr line can no longer read as "0 files".
            $Content | Should -MatchExactly ([regex]::Escape("busybox sh -c 'set -e; : > /tmp/count_err; n=`$(find /dest -type f ! -path /dest/.daaf-symlinks ! -path /dest/.daaf-permissions ! -path /dest/.daaf-claude-config/\* -exec stat -c %s {} + 2>/tmp/count_err | wc -l); if test -s /tmp/count_err; then echo RESTORED_COUNT_ERRORS=`$(grep -c ^ /tmp/count_err); else echo RESTORED_FILES=`$((n)); fi' 2>&1)"))
            $Content | Should -MatchExactly ([regex]::Escape("`$RestoredCount = Get-DaafCountMarker -Lines `$VerifyOutput -Name 'RESTORED_FILES'"))
            $Content | Should -MatchExactly ([regex]::Escape('WARNING: Could not verify the restored file count'))
            $Content | Should -Not -Match ([regex]::Escape("'find /dest -type f | wc -l'"))
            $Content | Should -Not -Match ([regex]::Escape('[int]::TryParse(($VerifyOutput'))
        }

        It "treats a Docker count with read errors as unavailable (BACKUP_COUNT_ERRORS)" {
            $Content | Should -Match ([regex]::Escape("`$ScanCountErrors = Get-DaafCountMarker -Lines `$ScanCountOutput -Name 'BACKUP_COUNT_ERRORS'"))
            $Content | Should -Match ([regex]::Escape('Note: Docker hit $ScanCountErrors read error(s) while counting this backup'))
        }

        It "treats a container count of 0 as unavailable and never warns on a satisfied lower bound" {
            $Content | Should -Match ([regex]::Escape('if ($null -ne $TotalFiles -and $null -ne $TotalSizeKB -and $TotalFiles -gt 0) {'))
            $Content | Should -Match ([regex]::Escape('if ($TotalFilesIsLowerBound -and $RestoredCount -ge $TotalFiles) {'))
            $Content | Should -Match ([regex]::Escape('Backup: $TotalFilesLabel files, Restored: $RestoredCount files'))
        }

        It "displays available backups with numbered list" {
            $Content | Should -Match 'Available backups'
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

Describe "restore_from_backup.ps1 Import-DaafSettingsInline" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $env:DAAF_TEST_MODE = "1"
        . "$RepoRoot/scripts/host/restore_from_backup.ps1"
    }

    AfterAll {
        Remove-Item Env:DAAF_TEST_MODE -ErrorAction SilentlyContinue
    }

    BeforeEach {
        $script:TmpDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-restore-settings-$(Get-Random)")
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
        [System.IO.File]::WriteAllBytes($script:SettingsFile, [System.Text.Encoding]::ASCII.GetBytes("DAAF_PORT_VSCODE=3020`r`n"))
        Import-DaafSettingsInline -SettingsFile $script:SettingsFile
        $env:DAAF_PORT_VSCODE | Should -Be "3020"
    }

    It "ignores non-DAAF keys" {
        Set-Content -Path $script:SettingsFile -Value "ANTHROPIC_API_KEY=sk-secret`nDAAF_PROJECT_NAME=safe"
        Import-DaafSettingsInline -SettingsFile $script:SettingsFile
        $env:DAAF_PROJECT_NAME | Should -Be "safe"
        $env:ANTHROPIC_API_KEY | Should -BeNullOrEmpty
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

    It "dry-run listing shows a plain count for a readable backup (no lower-bound '+')" {
        Push-Location $script:TestDir
        try {
            $null = New-Item -ItemType Directory -Path (Join-Path $script:TestDir "2026-01-01_daaf_backup") -Force
            $null = New-Item -ItemType File -Path (Join-Path $script:TestDir "2026-01-01_daaf_backup/f1") -Force
            $null = New-Item -ItemType File -Path (Join-Path $script:TestDir "2026-01-01_daaf_backup/.daaf-symlinks") -Force
            $env:DAAF_DRY_RUN = "1"
            $env:DAAF_NESTED = "1"
            $output = & "$RepoRoot/scripts/host/restore_from_backup.ps1" *>&1 | Out-String
            $output | Should -BeLike "*2026-01-01_daaf_backup  (1 files,*"
        } finally {
            Pop-Location
        }
    }

    It "dry-run listing marks an incompletely-read backup as a lower bound ('N+ files')" -Skip:(($PSVersionTable.PSVersion.Major -lt 6) -or $IsWindows -or ((& id -u) -eq '0')) {
        # An unreadable folder stands in for the Windows path-length failure.
        Push-Location $script:TestDir
        $locked = Join-Path $script:TestDir "2026-01-02_daaf_backup/locked"
        try {
            $null = New-Item -ItemType Directory -Path $locked -Force
            $null = New-Item -ItemType File -Path (Join-Path $script:TestDir "2026-01-02_daaf_backup/f1") -Force
            $null = New-Item -ItemType File -Path (Join-Path $locked "hidden") -Force
            & chmod 000 $locked
            $env:DAAF_DRY_RUN = "1"
            $env:DAAF_NESTED = "1"
            $output = & "$RepoRoot/scripts/host/restore_from_backup.ps1" *>&1 | Out-String
            $output | Should -BeLike "*2026-01-02_daaf_backup  (1+ files,*"
        } finally {
            & chmod 755 $locked
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

# ============================================================================
# End-to-end with a fake `docker` on PATH (non-Windows): count paths (2026-09-29)
# ============================================================================
# Runs the REAL script in a child pwsh with the two prompts answered on stdin
# ("1" = the only backup, "RESTORE"). -NonInteractive is deliberately NOT passed:
# with it, Read-Host refuses to read (observed on pwsh 7.6); without it, Read-Host
# consumes the piped lines. A bash fake `docker` models each subcommand; the
# container-side count runs the REAL $BackupCountProgram under the local sh.

Describe "restore_from_backup.ps1 end-to-end count paths (fake docker)" -Skip:(($PSVersionTable.PSVersion.Major -lt 6) -or $IsWindows) {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:FakeBin = Join-Path $TestDrive 'bin'
        $null = New-Item -ItemType Directory -Force -Path $script:FakeBin
        $fakeDocker = @'
#!/usr/bin/env bash
# Fake docker for restore_from_backup.Tests.ps1 (end-to-end). FAKE_* env vars drive it.
case "${1:-}" in
    info|volume|cp|rm) exit 0 ;;
    ps) exit 0 ;;
    create) echo fakecid0000; exit 0 ;;
    run)
        case "$*" in *":/b:ro"*)
            [ "${FAKE_COUNT_FAIL:-0}" = "1" ] && exit 1
            host="${4%:/b:ro}"
            [ -d "${host}" ] || { echo "fake docker: bind source is not a folder: ${host}" >&2; exit 65; }
            # FAKE_EMPTY_MOUNT=1: Docker Desktop shows an EMPTY folder for the mount.
            if [ "${FAKE_EMPTY_MOUNT:-0}" = "1" ]; then
                host="$(dirname "${host}")/empty-mount-view"
                mkdir -p "${host}"
            fi
            prog="${!#}"
            # Relocate the program's container /tmp/ (its /tmp/count_err) to a private
            # mktemp dir (under TMPDIR when set), removed after the run.
            ctmp="$(mktemp -d)"
            FAKE_B="${host}" sh -c "$(printf '%s\n' "${prog}" | sed -e 's#^cd /b$#cd "$FAKE_B"#' -e "s#/tmp/#${ctmp}/#g")"
            rc=$?
            rm -rf "${ctmp}"
            exit "${rc}" ;;
        esac
        # Manifest probes: no manifests in the restored volume.
        case "$*" in *"test -f"*) exit 1 ;; esac
        # Post-restore verification count. FAKE_VERIFY_MODE: ok (RESTORED_FILES marker),
        # errors (the program's read-error marker instead), fail (docker run exits 1),
        # errorsfail (the read-error marker AND a nonzero exit), countfail (a count
        # marker but a nonzero exit -- the count is then not trusted).
        case "$*" in *"find /dest -type f "*"RESTORED_FILES="*)
            case "${FAKE_VERIFY_MODE:-ok}" in
                errors) echo "RESTORED_COUNT_ERRORS=2"; exit 0 ;;
                fail) echo "fake docker: verification container failed" >&2; exit 1 ;;
                errorsfail) echo "RESTORED_COUNT_ERRORS=2"; exit 1 ;;
                countfail) echo "RESTORED_FILES=${FAKE_RESTORED:-0}"; exit 1 ;;
            esac
            echo "RESTORED_FILES=${FAKE_RESTORED:-0}"; exit 0 ;;
        esac
        # Volume clear, Claude-subfolder strip, chown: succeed.
        exit 0 ;;
    *) exit 0 ;;
esac
'@
        $fakePath = Join-Path $script:FakeBin 'docker'
        [System.IO.File]::WriteAllText($fakePath, ($fakeDocker -replace "`r", ""))
        & chmod +x $fakePath

        function Invoke-FakeRestore {
            param([int]$DataFiles, [int]$Restored, [switch]$EmptyMount, [switch]$CountFail, [switch]$Locked, [string]$VerifyMode = 'ok')
            $work = Join-Path $TestDrive ('restore-' + [guid]::NewGuid().ToString('N'))
            $bk = Join-Path $work '2026-01-01_daaf_backup'
            $null = New-Item -ItemType Directory -Path $bk
            for ($i = 0; $i -lt $DataFiles; $i++) { [IO.File]::WriteAllText((Join-Path $bk "f$i"), 'x') }
            [IO.File]::WriteAllText((Join-Path $bk '.daaf-symlinks'), '')
            # (Not "$locked": PowerShell names are case-insensitive, so it would be the
            # [switch]$Locked parameter.)
            $lockedDir = Join-Path $bk 'locked'
            if ($Locked) {
                $null = New-Item -ItemType Directory -Path $lockedDir
                [IO.File]::WriteAllText((Join-Path $lockedDir 'hidden'), 'x')
                & chmod 000 $lockedDir
            }
            $envLines = @(
                "PATH=$($script:FakeBin)$([IO.Path]::PathSeparator)$env:PATH",
                'DAAF_NESTED=1',
                "FAKE_RESTORED=$Restored",
                "FAKE_EMPTY_MOUNT=$(if ($EmptyMount) { '1' } else { '0' })",
                "FAKE_COUNT_FAIL=$(if ($CountFail) { '1' } else { '0' })",
                "FAKE_VERIFY_MODE=$VerifyMode"
            )
            Push-Location -LiteralPath $work
            try {
                # env(1) sets the child's environment without touching this session's.
                $out = "1`nRESTORE`n" | & env @envLines pwsh -NoProfile -File "$RepoRoot/scripts/host/restore_from_backup.ps1" 2>&1 | Out-String
                $code = $LASTEXITCODE
            } finally {
                Pop-Location
                if ($Locked) { & chmod 755 $lockedDir }
            }
            [pscustomobject]@{ Output = $out; ExitCode = $code }
        }
    }

    It "B1: a container count of 0 with files present is treated as unavailable (never 'Found 0 files')" {
        $r = Invoke-FakeRestore -DataFiles 3 -Restored 3 -EmptyMount
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*Docker could not see the files in this backup folder*"
        $r.Output | Should -BeLike "*Found 3 files*"
        $r.Output | Should -Not -BeLike "*Found 0 files*"
        $r.Output | Should -Not -BeLike "*File count mismatch*"
        # The fallback note is informational (the PowerShell count read everything, so
        # it is exact): it does not latch the warnings banner, as in backup_daaf.ps1.
        $r.Output | Should -BeLike "*Restore complete!*"
        $r.Output | Should -Not -BeLike "*WITH WARNINGS*"
    }

    It "a readable backup is counted inside Docker with no fallback note" {
        $r = Invoke-FakeRestore -DataFiles 3 -Restored 3
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*Found 3 files*"
        $r.Output | Should -Not -BeLike "*Could not count the backup inside Docker*"
        $r.Output | Should -Not -BeLike "*Docker could not see*"
        $r.Output | Should -BeLike "*Verified: 3 files in restored volume.*"
        $r.Output.Contains('Files:    3 files in volume') | Should -BeTrue
        $r.Output | Should -Not -BeLike "*Could not verify the restored file count*"
        # Clean run: the plain banner. The two NOTEs this fixture triggers (no
        # permission manifest, no Claude state) are informational and do not latch.
        $r.Output | Should -BeLike "*NOTE: No .daaf-permissions manifest found*"
        $r.Output | Should -BeLike "*NOTE: This backup does not contain Claude Code state*"
        $r.Output | Should -BeLike "*  Restore complete!*"
        $r.Output | Should -Not -BeLike "*WITH WARNINGS*"
        $r.Output | Should -BeLike "*You can now start DAAF with:*"
    }

    # FU2: the post-restore count is a marker program. An UNAVAILABLE count (read-error
    # marker, or the verification container failing) is a WARNING with exit 0 -- the
    # copy succeeded, only the check could not run -- never the false "0 files found"
    # ERROR the old bare-number parse produced. A count READ as 0 is evidence: exit 1.
    It "FU2: a post-restore count with read errors is a WARNING, exit 0, never '0 files found'" {
        $r = Invoke-FakeRestore -DataFiles 3 -Restored 3 -VerifyMode 'errors'
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*WARNING: Could not verify the restored file count: Docker hit 2 read error(s)*"
        $r.Output | Should -BeLike "*The copy itself reported success, so your data is most likely in place.*"
        $r.Output.Contains('Files:    not verified (the restored file count could not be read)') | Should -BeTrue
        $r.Output | Should -Not -BeLike "*0 files found*"
        $r.Output | Should -Not -BeLike "*File count mismatch*"
        $r.Output | Should -Not -BeLike "*not verified files in volume*"
        # An unverified count latches the banner; the exit code stays 0 (asserted above).
        $r.Output | Should -BeLike "*Restore completed WITH WARNINGS -- verify before relying on it*"
        $r.Output | Should -Not -BeLike "*Restore complete!*"
    }

    It "FU2: a failed post-restore count container is a WARNING, exit 0, never '0 files found'" {
        $r = Invoke-FakeRestore -DataFiles 3 -Restored 3 -VerifyMode 'fail'
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*WARNING: Could not verify the restored file count (the count inside Docker did not*"
        $r.Output | Should -BeLike "*run cleanly, exit 1).*"
        $r.Output.Contains('Files:    not verified (the restored file count could not be read)') | Should -BeTrue
        $r.Output | Should -Not -BeLike "*0 files found*"
        $r.Output | Should -BeLike "*Restore completed WITH WARNINGS -- verify before relying on it*"
        $r.Output | Should -Not -BeLike "*Restore complete!*"
    }

    # Marker parity with the .sh twin (restore_from_backup.bats "restore FU2: ... nonzero
    # exit"): the markers are parsed on ANY exit, an error marker takes precedence in
    # choosing the WARNING variant, and a count marker is trusted only on exit 0.
    It "FU2: nonzero exit + read-error marker gives the read-error WARNING variant (twin parity)" {
        $r = Invoke-FakeRestore -DataFiles 3 -Restored 3 -VerifyMode 'errorsfail'
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*WARNING: Could not verify the restored file count: Docker hit 2 read error(s)*"
        $r.Output | Should -BeLike "*while counting the restored volume.*"
        $r.Output | Should -Not -BeLike "*the count inside Docker did not*"
        $r.Output.Contains('Files:    not verified (the restored file count could not be read)') | Should -BeTrue
        $r.Output | Should -Not -BeLike "*0 files found*"
        $r.Output | Should -BeLike "*Restore completed WITH WARNINGS -- verify before relying on it*"
    }

    It "FU2: nonzero exit + a count marker is not trusted (exit-code WARNING variant)" {
        $r = Invoke-FakeRestore -DataFiles 3 -Restored 3 -VerifyMode 'countfail'
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*WARNING: Could not verify the restored file count (the count inside Docker did not*"
        $r.Output | Should -BeLike "*run cleanly, exit 1).*"
        $r.Output | Should -Not -BeLike "*Verified: 3 files*"
        $r.Output.Contains('Files:    not verified (the restored file count could not be read)') | Should -BeTrue
        $r.Output | Should -BeLike "*Restore completed WITH WARNINGS -- verify before relying on it*"
    }

    It "FU2: a post-restore count READ as RESTORED_FILES=0 still exits 1" {
        $r = Invoke-FakeRestore -DataFiles 3 -Restored 0
        $r.ExitCode | Should -Be 1
        $r.Output | Should -BeLike "*ERROR: Verification failed -- 0 files found in restored volume.*"
        $r.Output | Should -Not -BeLike "*Could not verify the restored file count*"
        # A fatal exit prints neither banner.
        $r.Output | Should -Not -BeLike "*Restore complete!*"
        $r.Output | Should -Not -BeLike "*Restore completed WITH WARNINGS*"
    }

    It "a post-restore file-count mismatch is a WARNING that latches WITH WARNINGS, exit 0" {
        # 50 vs 10: far past the 1% tolerance (floor 1).
        $r = Invoke-FakeRestore -DataFiles 50 -Restored 10
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*WARNING: File count mismatch.*"
        $r.Output | Should -BeLike "*Backup: 50 files, Restored: 10 files (difference: 40)*"
        $r.Output | Should -BeLike "*Restore completed WITH WARNINGS -- verify before relying on it*"
        $r.Output | Should -Not -BeLike "*Restore complete!*"
        $r.Output | Should -BeLike "*You can now start DAAF with:*"
    }

    It "I3: a LOWER-BOUND backup count with at least that many restored files gets no mismatch warning, but latches WITH WARNINGS" -Skip:((& id -u) -eq '0') {
        # 10 restored vs a 3+ count: past the 1% tolerance (floor 1), so the old code
        # warned "restore may be incomplete" on exactly the long-path case. The note
        # stays informational (no mismatch WARNING), but a lower bound cannot prove the
        # restore complete, so the banner is latched -- as backup_daaf.ps1 latches its
        # own lower-bound count. Exit code unchanged (0).
        $r = Invoke-FakeRestore -DataFiles 3 -Restored 10 -CountFail -Locked
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*Found 3+ files*"
        $r.Output | Should -BeLike "*The backup count (3+ files) was a lower bound*"
        $r.Output | Should -Not -BeLike "*File count mismatch*"
        $r.Output | Should -Not -BeLike "*restore may be incomplete*"
        $r.Output | Should -BeLike "*Restore completed WITH WARNINGS -- verify before relying on it*"
        $r.Output | Should -Not -BeLike "*Restore complete!*"
    }

    It "F1: a Docker count that hits a read error falls back to PowerShell (never a short exact count)" -Skip:((& id -u) -eq '0') {
        # No -CountFail: the REAL program runs and cannot read the locked folder.
        # Before the fix it printed BACKUP_FILES=3 with exit 0 -- "Found 3 files" as
        # if exact -- and the 4-file restore then looked like a mismatch.
        $r = Invoke-FakeRestore -DataFiles 3 -Restored 4 -Locked
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*Docker hit 1 read error(s) while counting this backup*"
        $r.Output | Should -BeLike "*Found 3+ files*"
        $r.Output | Should -BeLike "*The backup count (3+ files) was a lower bound*"
        $r.Output | Should -Not -BeLike "*File count mismatch*"
    }

    It "I3: a restored count BELOW the lower bound still warns, labelled with '+'" -Skip:((& id -u) -eq '0') {
        $r = Invoke-FakeRestore -DataFiles 5 -Restored 1 -CountFail -Locked
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*WARNING: File count mismatch.*"
        $r.Output | Should -BeLike "*Backup: 5+ files, Restored: 1 files (difference: 4)*"
        $r.Output | Should -BeLike "*Restore completed WITH WARNINGS -- verify before relying on it*"
    }
}

# ============================================================================
# Error paths
# ============================================================================

Describe "restore_from_backup.ps1 error paths" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:Content = Get-Content "$RepoRoot/scripts/host/restore_from_backup.ps1" -Raw
    }

    Context "Running container detected" {
        It "offers to stop running containers" {
            $Content | Should -Match 'container is currently running'
            $Content | Should -Match 'Stop the container now'
        }

        It "stops containers when user agrees" {
            $Content | Should -Match 'Stopping containers'
            $Content | Should -Match 'docker compose down'
        }
    }

    Context "User declines to stop container" {
        It "cancels restore when user declines stop (exit 0)" {
            $Content | Should -Match 'Restore cancelled\. Stop the container manually'
        }
    }

    Context "Invalid backup selection" {
        It "rejects non-numeric input (exit 1)" {
            $Content | Should -Match 'TryParse'
            $Content | Should -Match 'Invalid selection'
        }

        It "rejects out-of-range selection (exit 1)" {
            $Content | Should -Match '\$ChoiceNum -lt 1 -or \$ChoiceNum -gt \$Backups\.Count'
        }
    }

    Context "User cancels at RESTORE confirmation" {
        It "exits cleanly when user types something other than RESTORE (exit 0)" {
            $Content | Should -Match '\$Confirm -ne "RESTORE"'
            $Content | Should -Match 'Restore cancelled'
        }
    }

    Context "Volume clear fails" {
        It "exits with error when volume clear fails (exit 1)" {
            $Content | Should -Match 'Failed to clear Docker volume'
            $Content | Should -Match 'inconsistent state'
        }
    }

    Context "Zero files after restore" {
        It "exits with error when zero files found after restore (exit 1)" {
            $Content | Should -Match '\$RestoredCount -eq 0'
            $Content | Should -Match '0 files found in restored volume'
        }
    }

    Context "File count mismatch after restore" {
        It "shows warning when file count differs beyond tolerance" {
            $Content | Should -Match 'File count mismatch'
            $Content | Should -Match 'restore may be incomplete'
        }
    }

    Context "No backup folders found" {
        It "exits with error when no backups exist (exit 1)" {
            $Content | Should -Match 'No backup folders found'
            $Content | Should -Match 'daaf-docker folder'
        }
    }
}
