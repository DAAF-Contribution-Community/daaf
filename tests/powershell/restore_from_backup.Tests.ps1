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

        It "clears the live volume ONLY inside the swap program (copy-then-swap)" {
            # Before copy-then-swap, Step 1 ran `rm -rf /dest/...` against the LIVE volume
            # before anything was copied. Now the only clear of /dest is the first command
            # of $SwapProgram, which runs after the temp copy was checked and RESTORE typed.
            $Content | Should -Match 'rm -rf /dest'
            $clearLines = @(($Content -split "`n") | Where-Object { $_ -match 'rm -rf /dest/\*' })
            $clearLines.Count | Should -Be 1
            $clearLines[0] | Should -Match '^\$SwapProgram = '
        }

        It "uses docker cp (not bind-mounted cp -a) into the TEMPORARY volumes" {
            # The copy mechanism is `docker create` + `docker cp` -- one for the
            # data volume, one for the Claude state volume -- and must NOT use the
            # old bind-mounted `cp -a /source` busybox copy. The helpers now mount the
            # temp volumes, never the live ones.
            $Content | Should -Match 'docker create'
            $Content | Should -Match 'docker cp'
            $Content | Should -Not -Match 'cp -a /source'
            $Content | Should -Match ([regex]::Escape('docker create --label "$RestoreLabel=$VolumeName" -v "${TempVolumeName}:/dest" busybox 2>$null'))
            $Content | Should -Match ([regex]::Escape('docker create --label "$RestoreLabel=$ClaudeVolumeName" -v "${ClaudeTempVolumeName}:/dest" busybox 2>$null'))
        }

        It "repairs ownership on BOTH temporary copies after docker cp writes as root" {
            # `docker cp` INTO a container writes files as root; restore must chown
            # the copy back to appuser (UID 1000), matching daaf-init. The chown now runs
            # on the temp volumes (the swap's `cp -a` carries ownership into live).
            $chownLines = @(($Content -split "`n") | Where-Object { $_ -match [regex]::Escape("'chown', '-R', '1000:1000', '/dest'") })
            $chownLines.Count | Should -Be 2
            ($chownLines -join "`n") | Should -Match ([regex]::Escape('"${TempVolumeName}:/dest", ''busybox'', ''chown'''))
            ($chownLines -join "`n") | Should -Match ([regex]::Escape('"${ClaudeTempVolumeName}:/dest", ''busybox'', ''chown'''))
        }

        It "replays executable permissions from the manifest (Step 3d)" {
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

        It "replays symlinks from the manifest (Step 3e)" {
            # When ".daaf-symlinks" is present, recreate each link (path TAB target)
            # container-side, chown -h it to appuser, and strip the manifest.
            $Content | Should -Match '\.daaf-symlinks'
            $Content | Should -Match 'ln -sf -- '
            $Content | Should -Match 'chown -h 1000:1000'
        }

        It "passes the symlink-replay sh -c program without embedded double-quotes" {
            # The Step 3e replay program is shared logically with the .sh twin; an
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

        It "invokes the symlink replay for BOTH the data and the Claude TEMPORARY volumes" {
            # Regression guard for the review BLOCKER: an earlier draft ported the
            # symlink-replay call only to the DATA volume and silently omitted it from
            # the Claude-state restore block, so Claude-volume symlinks were never
            # recreated. A file-wide grep for ".daaf-symlinks" (or even for
            # "$symlinkReplayScript") PASSES on that broken state because the string is
            # present once -- which is exactly how the gap slipped through review. Assert
            # the program is actually INVOKED against two DISTINCT `/dest` volumes.
            # Copy-then-swap (2026-10-01): the replays run on the TEMPORARY copies
            # ($TempVolumeName / $ClaudeTempVolumeName) before RESTORE; the swap carries
            # the links into the live volumes. The invocation lines now start
            # `$null = docker run --rm --label ...`, which the pattern still matches.
            $invokeLines = ($Content -split "`n") | Where-Object {
                $_ -match 'docker run .*-v "\$\{[A-Za-z]+\}:/dest".*busybox sh -c \$symlinkReplayScript'
            }
            @($invokeLines).Count | Should -Be 2
            ($invokeLines -join "`n") | Should -Match '\$\{TempVolumeName\}:/dest"'
            ($invokeLines -join "`n") | Should -Match '\$\{ClaudeTempVolumeName\}:/dest"'
            # Neither replay may write to a LIVE volume.
            ($invokeLines -join "`n") | Should -Not -Match '\$\{VolumeName\}:/dest"'
            ($invokeLines -join "`n") | Should -Not -Match '\$\{ClaudeVolumeName\}:/dest"'
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

        It "compares the restored count EXACTLY with the checked temp copy's count (no 1% tolerance)" {
            # Review round 1 (B1 fix 4, I4): the post-swap count must EQUAL the temp copy's
            # count from step 3f; any difference -- including 0 -- goes through the
            # after-swap failure text (temp copy kept, exit 1). The old 1% "File count
            # mismatch" WARNING and the "0 files found ... reinstalling DAAF" ERROR are gone.
            $Content | Should -Match ([regex]::Escape('} elseif ($RestoredCount -ne $TempCount) {'))
            $Content | Should -Match ([regex]::Escape('Write-DaafRestoreSwapFailure -Lines @("ERROR: After replacing your DAAF data, it holds $RestoredCount files, but the checked",'))
            $Content | Should -Not -Match 'File count mismatch'
            # (A comment still explains the old false "0 files found" ERROR; code lines only.)
            @(($Content -split "`n") | Where-Object { $_ -notmatch '^\s*#' -and $_ -match '0 files found' }).Count | Should -Be 0
            $Content | Should -Not -Match 'reinstalling DAAF'
        }

        It "latches a WITH WARNINGS completion banner without changing the exit code" {
            # Mirrors backup_daaf.ps1's $HadWarnings. One init; seven latch sites
            # (copy-then-swap, review round 1): the lower-bound scan count, the free space
            # that could not be checked, the permission and symlink replays (on the temp
            # copy), the Claude-state symlink replay, the unverified post-restore count, and
            # the temporary copy that could not be removed after a successful restore. (The
            # old Claude-state "clear"/"copy" WARNINGs stop the restore before anything is
            # replaced; the old file-count-mismatch WARNING is now an exact-count after-swap
            # failure.) A new success-path WARNING must latch too (update this count and
            # backup_twin_parity.bats's restore latch pin together).
            ([regex]::Matches($Content, [regex]::Escape('$HadWarnings = $false'))).Count | Should -Be 1
            ([regex]::Matches($Content, [regex]::Escape('$HadWarnings = $true'))).Count | Should -Be 7
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

        It "treats a container count of 0 as unavailable; a fallback or N+ count is a LOWER BOUND for the temp copy" {
            $Content | Should -Match ([regex]::Escape('if ($null -ne $TotalFiles -and $null -ne $TotalSizeKB -and $TotalFiles -gt 0) {'))
            # Review round 1 (S4): a PowerShell-fallback count -- "N" or "N+" -- is never
            # authoritative, so the temp copy must reach it; only a Docker count is exact.
            $Content | Should -Match ([regex]::Escape('$tempShort = ($TempCount -eq 0) -or ($TempCount -lt $TotalFiles) -or ((-not $TotalFilesIsLowerBound) -and (-not $TotalFilesFromFallback) -and $TempCount -ne $TotalFiles)'))
            # The restored count equals the temp copy's, so it is consistent with an N+ count.
            $Content | Should -Match ([regex]::Escape('Note: The backup count ($TotalFilesLabel files) was a lower bound; the restored volume holds'))
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
# Copy-then-swap structure (2026-10-01): pins that need the AST or the programs'
# VALUES (dot-sourced in DAAF_TEST_MODE: the names and programs are defined above
# the test-mode guard). Behaviour is covered end-to-end further below.
# ============================================================================

Describe "restore_from_backup.ps1 copy-then-swap structure" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:Path = "$RepoRoot/scripts/host/restore_from_backup.ps1"
        $script:Content = Get-Content $script:Path -Raw
        $script:Lines = @($script:Content -split "`n")
        $script:ShContent = Get-Content "$RepoRoot/scripts/host/restore_from_backup.sh" -Raw
        $tokens = $null
        $parseErrors = $null
        $script:Ast = [System.Management.Automation.Language.Parser]::ParseFile($script:Path, [ref]$tokens, [ref]$parseErrors)
        # The one try/finally of the copy-then-swap flow (its finally reads $SwapStarted).
        $script:SwapTry = @($script:Ast.FindAll({
            param($n)
            ($n -is [System.Management.Automation.Language.TryStatementAst]) -and ($null -ne $n.Finally) -and ($n.Finally.Extent.Text -match 'SwapStarted')
        }, $true))
        $env:DAAF_TEST_MODE = "1"
        . $script:Path
        # The flow's helper functions sit BELOW the test-mode guard, where dot-sourcing
        # stops; define the three pure checks from the AST so they can be unit-tested.
        foreach ($fnName in @('Test-DaafRestoreTempIdentity', 'Test-DaafRestoreNotFound', 'Test-DaafRestoreSwapChecked')) {
            $fnAst = $script:Ast.Find({
                param($n) ($n -is [System.Management.Automation.Language.FunctionDefinitionAst]) -and ($n.Name -eq $fnName)
            }, $true)
            . ([scriptblock]::Create($fnAst.Extent.Text))
        }
    }

    AfterAll {
        Remove-Item Env:DAAF_TEST_MODE -ErrorAction SilentlyContinue
    }

    It "derives every copy-then-swap name from the RESOLVED volume names" {
        $VolumeName | Should -Not -BeNullOrEmpty
        $TempVolumeName | Should -Be "${VolumeName}-restore-tmp"
        $ClaudeTempVolumeName | Should -Be "${ClaudeVolumeName}-restore-tmp"
        $SwapContainerName | Should -Be "${VolumeName}-restore-swap"
        $ClaudeSwapContainerName | Should -Be "${ClaudeVolumeName}-restore-swap"
        $RestoreLabel | Should -BeExactly 'org.daaf.restore-tmp-for'
        $SwapMarker | Should -BeExactly '.daaf-restore-swap-started'
    }

    It "starts the swap program with the INT/TERM/HUP trap (a forwarded Ctrl+C must not stop it after rm)" {
        $SwapProgram | Should -Not -BeNullOrEmpty
        $SwapProgram.StartsWith('trap : INT TERM HUP; ') | Should -BeTrue
        # Review round 1 (B1): nothing is erased unless the source holds this run's state
        # marker; then the clear and the copy are one && chain; the marker goes last.
        # Review round 2 (S1): a missing marker exits 3 (`|| exit 3`), so the host can
        # tell "refused before its rm" from a swap that failed partway.
        $SwapProgram.Contains('; test -f /src/.daaf-restore-swap-started || exit 3; rm -rf /dest/* /dest/.[!.]* /dest/..?* && cp -a /src/. /dest/ && ') | Should -BeTrue
        $SwapProgram.EndsWith('&& rm -f /dest/.daaf-restore-swap-started') | Should -BeTrue
    }

    It "accepts a swap comparison only with SWAP_VERIFY=MATCH and equal ENTRIES (n > 0 for the data volume)" {
        # Review round 1 (B1): two EMPTY trees "match" (ENTRIES=0:0). The data volume must
        # be non-empty; the Claude volume may be empty (a backup taken before any login).
        Test-DaafRestoreSwapChecked -Lines @('SWAP_VERIFY=MATCH', 'SWAP_VERIFY_ENTRIES=3:3') -NonEmpty | Should -BeTrue
        Test-DaafRestoreSwapChecked -Lines @('SWAP_VERIFY=MATCH', 'SWAP_VERIFY_ENTRIES=0:0') -NonEmpty | Should -BeFalse
        Test-DaafRestoreSwapChecked -Lines @('SWAP_VERIFY=MATCH', 'SWAP_VERIFY_ENTRIES=0:0') | Should -BeTrue
        Test-DaafRestoreSwapChecked -Lines @('SWAP_VERIFY=MATCH', 'SWAP_VERIFY_ENTRIES=3:2') | Should -BeFalse
        Test-DaafRestoreSwapChecked -Lines @('SWAP_VERIFY=MATCH') | Should -BeFalse
        Test-DaafRestoreSwapChecked -Lines @('SWAP_VERIFY=MISMATCH', 'SWAP_VERIFY_ENTRIES=3:3') | Should -BeFalse
        Test-DaafRestoreSwapChecked -Lines @('SWAP_VERIFY_ERRORS=2', 'SWAP_VERIFY_ENTRIES=0:0') | Should -BeFalse
        # Exact markers only (case-sensitive, whole line).
        Test-DaafRestoreSwapChecked -Lines @('swap_verify=match', 'SWAP_VERIFY_ENTRIES=3:3') | Should -BeFalse
        Test-DaafRestoreSwapChecked -Lines @('SWAP_VERIFY=MATCHED', 'SWAP_VERIFY_ENTRIES=3:3') | Should -BeFalse
        # The data call passes -NonEmpty; the Claude call does not.
        @($Lines | Where-Object { $_ -match 'Test-DaafRestoreSwapChecked -Lines \$swapCheck -NonEmpty' }).Count | Should -Be 1
        @($Lines | Where-Object { $_ -match 'Test-DaafRestoreSwapChecked -Lines \$swapCheck\)' }).Count | Should -Be 1
    }

    It "reads the identity label from 'docker volume inspect --format {{.Labels}}' (exact key:value word)" {
        # The .ps1 calls docker directly here; a function named docker (defined in this
        # It's scope) shadows it, and reads $fakeLabels / $fakeExit through PowerShell's
        # dynamic scoping.
        $fakeLabels = ''
        $fakeExit = 0
        function docker { $global:LASTEXITCODE = $fakeExit; if ($fakeLabels -ne '') { $fakeLabels } }
        $fakeLabels = "map[$($RestoreRunLabel):$($RestoreRunId) $($RestoreLabel):daaf_daaf-data]"
        Test-DaafRestoreTempIdentity -Name 'x' | Should -BeTrue
        $fakeLabels = "map[$($RestoreLabel):daaf_daaf-data $($RestoreRunLabel):$($RestoreRunId)]"
        Test-DaafRestoreTempIdentity -Name 'x' | Should -BeTrue
        $fakeLabels = "map[$($RestoreRunLabel):other-run $($RestoreLabel):daaf_daaf-data]"
        Test-DaafRestoreTempIdentity -Name 'x' | Should -BeFalse
        # A token that merely STARTS with ours is not ours.
        $fakeLabels = "map[$($RestoreRunLabel):$($RestoreRunId)x]"
        Test-DaafRestoreTempIdentity -Name 'x' | Should -BeFalse
        $fakeLabels = 'map[]'
        Test-DaafRestoreTempIdentity -Name 'x' | Should -BeFalse
        # A failed inspect is "not ours", even if it printed our label text.
        $fakeExit = 1
        $fakeLabels = "map[$($RestoreRunLabel):$($RestoreRunId)]"
        Test-DaafRestoreTempIdentity -Name 'x' | Should -BeFalse
    }

    It "treats only 'no such volume/container/object' as absent (any other inspect failure is 'could not check')" {
        Test-DaafRestoreNotFound -Lines @('Error response from daemon: get x: no such volume') | Should -BeTrue
        Test-DaafRestoreNotFound -Lines @('Error response from daemon: No such container: x') | Should -BeTrue
        Test-DaafRestoreNotFound -Lines @('Error: No such object: x') | Should -BeTrue
        Test-DaafRestoreNotFound -Lines @('Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?') | Should -BeFalse
        Test-DaafRestoreNotFound -Lines @() | Should -BeFalse
    }

    It "keeps the three container programs quote-free and BYTE-IDENTICAL to the .sh twin's" {
        $pairs = @(
            @{ Ps = $SpaceProgram; Sh = 'SPACE_PROGRAM' },
            @{ Ps = $SwapProgram; Sh = 'SWAP_PROGRAM' },
            @{ Ps = $SwapVerifyProgram; Sh = 'SWAP_VERIFY_PROGRAM' }
        )
        foreach ($p in $pairs) {
            $p.Ps | Should -Not -BeNullOrEmpty
            # Windows PowerShell 5.1 native-argument rule: no `"` in a container program.
            $p.Ps | Should -Not -Match '"' -Because "$($p.Sh) must not contain a double quote"
            $m = [regex]::Match($ShContent, "(?m)^$($p.Sh)='([^']*)'\r?$")
            $m.Success | Should -BeTrue -Because "the .sh must define $($p.Sh) on one single-quoted line"
            $p.Ps | Should -BeExactly $m.Groups[1].Value -Because "$($p.Sh) is shared with the .sh twin"
        }
    }

    It "checks the temp copy with the SAME count program as the post-restore check (textually identical)" {
        $tempLine = @($Lines | Where-Object { $_ -match '^\s*\$TempVerifyOutput = @\(docker run ' })
        $liveLine = @($Lines | Where-Object { $_ -match '^\$VerifyOutput = @\(docker run ' })
        $tempLine.Count | Should -Be 1
        $liveLine.Count | Should -Be 1
        $tempLine[0] | Should -Match ([regex]::Escape('-v "${TempVolumeName}:/dest:ro" busybox sh -c '''))
        $liveLine[0] | Should -Match ([regex]::Escape('-v "${VolumeName}:/dest:ro" busybox sh -c '''))
        $progRe = "busybox sh -c '([^']*)' 2>&1\)"
        $tempProg = [regex]::Match($tempLine[0], $progRe).Groups[1].Value
        $liveProg = [regex]::Match($liveLine[0], $progRe).Groups[1].Value
        $tempProg | Should -Not -BeNullOrEmpty
        $tempProg | Should -BeExactly $liveProg
    }

    It "runs each swap in ONE named container with --sig-proxy=false (temp :ro, live writable)" {
        $Content | Should -Match ([regex]::Escape("@('run', '--rm', '--sig-proxy=false', '--name', `$SwapContainerName, '-v', `"`${TempVolumeName}:/src:ro`", '-v', `"`${VolumeName}:/dest`", 'busybox', 'sh', '-c', `$SwapProgram)"))
        $Content | Should -Match ([regex]::Escape("@('run', '--rm', '--sig-proxy=false', '--name', `$ClaudeSwapContainerName, '-v', `"`${ClaudeTempVolumeName}:/src:ro`", '-v', `"`${ClaudeVolumeName}:/dest`", 'busybox', 'sh', '-c', `$SwapProgram)"))
        # The swap containers carry no label, so a label reap can never kill one.
        @($Lines | Where-Object { $_ -match '--sig-proxy=false' -and $_ -match 'RestoreLabel' }).Count | Should -Be 0
    }

    It "mounts each LIVE volume writable in exactly one place: its swap" {
        foreach ($v in @('VolumeName', 'ClaudeVolumeName')) {
            $writable = @($Lines | Where-Object { $_ -match ('"\$\{' + $v + '\}:/dest"') })
            $writable.Count | Should -Be 1 -Because "only the swap may write to `$$v"
            $writable[0] | Should -Match '--sig-proxy=false'
        }
        # No volume create/rm of a live name: every `volume create` / `volume rm` names a
        # temp volume (or a leftover temp volume, $tv). A create carries both labels.
        foreach ($l in @($Lines | Where-Object { $_ -match "'volume', '(create|rm)'" })) {
            $l | Should -Match "'volume', '(create|rm)'(, '--label', `"[^`"]+`")*, (\`$TempVolumeName|\`$ClaudeTempVolumeName|\`$tv)\)"
        }
        @($Lines | Where-Object { $_ -match "'volume', 'create', '--label', `"\`$RestoreLabel=[^`"]+`", '--label', `"\`$RestoreRunLabel=\`$RestoreRunId`"" }).Count | Should -Be 2
    }

    It "checks for leftovers by EXACT name (volume/container inspect), never an unanchored volume ls filter" {
        $Content | Should -Match ([regex]::Escape("@('volume', 'inspect', `$tv)"))
        $Content | Should -Match ([regex]::Escape("@('container', 'inspect', '--format', '{{.State.Running}}', `$sc)"))
        # Review round 2 (S3): the exact-name FALLBACK lists every name (`volume ls -q`,
        # `ps [-a] --format {{.Names}}`) and compares whole lines; a `--filter name=`
        # list (an unanchored regex) is still never used.
        $Content | Should -Match ([regex]::Escape("@('volume', 'ls', '-q')"))
        $Content | Should -Not -Match "volume ls --filter|'volume', 'ls', '--filter'"
    }

    It "captures helper container IDs from stdout ONLY (no 2>&1 into the CID)" {
        $createLines = @($Lines | Where-Object { $_ -match 'docker create ' -and $_ -notmatch '^\s*#' })
        $createLines.Count | Should -Be 2
        foreach ($l in $createLines) {
            $l | Should -Match '2>\$null\)\s*$'
            $l | Should -Not -Match '2>&1'
        }
    }

    It "asks for RESTORE only after the temp copy was checked, and swaps only after RESTORE" {
        $tempCheck = $Content.IndexOf('Write-Host "Verified: $TempCount files in the temporary copy."')
        $claudePrep = $Content.IndexOf('Write-Host "Claude Code state prepared."')
        $restore = $Content.IndexOf('$Confirm = Read-Host "Type RESTORE to confirm, or anything else to cancel"')
        $running = $Content.IndexOf('$runningNowLines = @(docker ps --filter ')
        $marker = $Content.IndexOf("'touch', `"/dest/`$SwapMarker`"")
        $started = $Content.IndexOf('$SwapStarted = $true')
        $swap = $Content.IndexOf("'--sig-proxy=false', '--name', `$SwapContainerName")
        foreach ($i in @($tempCheck, $claudePrep, $restore, $running, $marker, $started, $swap)) { $i | Should -BeGreaterThan -1 }
        $restore | Should -BeGreaterThan $tempCheck
        $restore | Should -BeGreaterThan $claudePrep
        $running | Should -BeGreaterThan $restore
        $marker | Should -BeGreaterThan $running
        $started | Should -BeGreaterThan $marker
        $swap | Should -BeGreaterThan $started
    }

    It "has exactly one try/finally for the flow, with NO exit or Wait-AndExit inside the try or the finally" {
        # Calling `exit` from inside a try whose finally must run is version-fragile on
        # Windows PowerShell 5.1; outcomes are flags acted on after the finally.
        $SwapTry.Count | Should -Be 1
        foreach ($block in @($SwapTry[0].Body, $SwapTry[0].Finally)) {
            $exits = @($block.FindAll({
                param($n)
                ($n -is [System.Management.Automation.Language.ExitStatementAst]) -or
                (($n -is [System.Management.Automation.Language.CommandAst]) -and ($n.GetCommandName() -eq 'Wait-AndExit'))
            }, $true))
            $exits.Count | Should -Be 0
        }
    }

    It "ends an interrupted run with exit 130 ONLY under DAAF_NESTED, as the finally's LAST statement, never for an error" {
        # 2026-10-02: under pwsh a Ctrl+C inside the try used to end the process with 0.
        # Behaviour: the "Ctrl+C (SIGINT to pwsh)" cases in the end-to-end block.
        $finStatements = @($SwapTry[0].Finally.Statements)
        $finStatements[-1].Extent.Text | Should -BeExactly 'if ($Interrupted -and $env:DAAF_NESTED) { [Environment]::Exit(130) }'
        $finStatements[-2].Extent.Text | Should -BeExactly '$Interrupted = (-not $ReachedEnd) -and (-not $Faulted) -and ($null -eq $PrepFail) -and ($null -eq $SwapFail) -and (-not $Cancelled) -and ($null -eq $ChangedTemp)'
        # The one catch records an unexpected error and rethrows it unchanged.
        $SwapTry[0].CatchClauses.Count | Should -Be 1
        $catchStatements = @($SwapTry[0].CatchClauses[0].Body.Statements)
        $catchStatements.Count | Should -Be 2
        $catchStatements[0].Extent.Text | Should -BeExactly '$Faulted = $true'
        $catchStatements[1].Extent.Text | Should -BeExactly 'throw'
        $Content | Should -Match ([regex]::Escape('$Faulted = $false'))
        # The only hard process exit in the script.
        @($Lines | Where-Object { $_ -match '\[Environment\]::Exit' -and $_ -notmatch '^\s*#' }).Count | Should -Be 1
    }

    It "refuses at startup when the running-container 'docker ps' FAILS (its exit code is read)" {
        $i = [array]::FindIndex([string[]]$Lines, [Predicate[string]]{ param($l) $l -match '^\$RunningContainers = @\(docker ps --filter "volume=\$VolumeName" --format ''\{\{\.Names\}\}'' 2>\$null\)' })
        $i | Should -BeGreaterThan -1
        $Lines[$i + 1] | Should -Match '^\$runningContainersExit = \$LASTEXITCODE'
        $Content | Should -Match ([regex]::Escape('if ($runningContainersExit -ne 0) {'))
    }

    It "never removes a temp volume in the finally once the swap has started (two guards)" {
        # Guard 1: the finally calls the cleanup only when no swap has started -- and not
        # when a temp is no longer this run's (review round 1, B1: that refusal removes
        # nothing, not even the label reap; behaviour pinned by the "B1:" cases).
        $fin = $SwapTry[0].Finally
        $cleanupCalls = @($fin.FindAll({
            param($n) ($n -is [System.Management.Automation.Language.CommandAst]) -and ($n.GetCommandName() -eq 'Invoke-DaafRestoreTempCleanup')
        }, $true))
        $cleanupCalls.Count | Should -Be 1
        $fin.Extent.Text | Should -Match ([regex]::Escape('if (-not $SwapStarted -and $null -eq $ChangedTemp) { Invoke-DaafRestoreTempCleanup }'))
        $fin.Extent.Text | Should -Not -Match "'volume', 'rm'"
        # Guard 2: the cleanup itself is a no-op after a swap started, unless -Final.
        $fn = $Ast.Find({
            param($n) ($n -is [System.Management.Automation.Language.FunctionDefinitionAst]) -and ($n.Name -eq 'Invoke-DaafRestoreTempCleanup')
        }, $true)
        $fn | Should -Not -BeNullOrEmpty
        $fn.Body.EndBlock.Statements[0].Extent.Text | Should -BeExactly 'if ($script:SwapStarted -and -not $Final) { return }'
        # The only -Final call comes after every check (just before the banner).
        @($Lines | Where-Object { $_ -match 'Invoke-DaafRestoreTempCleanup -Final' }).Count | Should -Be 1
        $Content.IndexOf('Invoke-DaafRestoreTempCleanup -Final') | Should -BeGreaterThan $Content.IndexOf('$RestoredCount = Get-DaafCountMarker')
    }

    It "sets the swap-start flag immediately before the data swap call" {
        $i = [array]::FindIndex([string[]]$Lines, [Predicate[string]]{ param($l) $l -match '^\s*\$SwapStarted = \$true' })
        $i | Should -BeGreaterThan -1
        $Lines[$i + 1] | Should -Match "'--sig-proxy=false', '--name', \`$SwapContainerName"
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

    It "HSM5: dry-run with a backup present reaches no copy-then-swap step (no write site)" {
        # The dry-run stub echoes every unmodeled docker call as "[DRY-RUN] docker ...";
        # the run must exit before the leftover check, the space check and every
        # temp-volume, helper, swap or cleanup call.
        Push-Location $script:TestDir
        try {
            $null = New-Item -ItemType Directory -Path (Join-Path $script:TestDir "2026-01-01_daaf_backup") -Force
            $null = New-Item -ItemType File -Path (Join-Path $script:TestDir "2026-01-01_daaf_backup/f1") -Force
            $env:DAAF_DRY_RUN = "1"
            $env:DAAF_NESTED = "1"
            $output = & "$RepoRoot/scripts/host/restore_from_backup.ps1" *>&1 | Out-String
            $output | Should -BeLike "*Restore dry-run complete!*"
            $output | Should -Not -BeLike "*restore-tmp*"
            $output | Should -Not -BeLike "*restore-swap*"
            $output | Should -Not -BeLike "*Preparing a temporary copy*"
            $output | Should -Not -BeLike "*DESTRUCTIVE OPERATION*"
            $output | Should -Not -BeLike "*``[DRY-RUN``] docker*"
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
# Every call is appended to FAKE_CALL_LOG as ONE line (newlines inside arguments, e.g.
# the multi-line $BackupCountProgram, are folded to spaces). Volumes are stateful:
# each is a file "vol.<name>" in FAKE_STATE, so `volume create/inspect/rm/ls` behave
# like Docker's (the test seeds the live volumes and any leftover temp volume).
# Failure switches are FAKE_* exit codes / modes, all defaulting to success.
if [ -n "${FAKE_CALL_LOG:-}" ]; then
    printf '%s\n' "$(printf '%s' "$*" | tr '\n' ' ')" >> "${FAKE_CALL_LOG}"
fi
st="${FAKE_STATE:-.}"
# FAKE_INTERRUPT_AT=cp|swap: send SIGINT to the calling pwsh (Ctrl+C stand-in), then
# finish normally -- a real swap keeps running inside Docker after Ctrl+C.
interrupt_here() {
    if [ "${FAKE_INTERRUPT_AT:-}" = "$1" ]; then kill -INT "${PPID}" 2>/dev/null; sleep 2; fi
}
# A volume file holds that volume's labels, one "key=value" line each (seeded volumes
# have none). FAKE_INSPECT_FAIL=volume|container: an exact-name inspect of a temp volume /
# swap container fails with a daemon error (not "no such ..."), as a transient error would.
daemon_down() { echo "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?" >&2; exit 1; }
# Review round 2 (S3): FAKE_INSPECT_ODD=volume|container -- the exact-name inspect fails
# with error text that is NOT a recognised "no such ..." message, while the exact-name
# lists (`volume ls -q`, `ps [-a] --format {{.Names}}`) still work; FAKE_LIST_FAIL=1 makes
# those lists fail too. FAKE_INSPECT_FAIL (above) implies both: inspect AND lists fail.
odd_error() { echo "Error response from daemon: fake unexpected failure" >&2; exit 1; }
# A stray stderr line (a Docker config WARNING stand-in).
stray_warning() { echo "WARNING: fake docker config notice" >&2; }
vol_inspect=""; vol_list_fail=0; ctr_inspect=""; ctr_list_fail=0
case "${FAKE_INSPECT_FAIL:-}" in
    volume) vol_inspect=daemon; vol_list_fail=1 ;;
    container) ctr_inspect=daemon; ctr_list_fail=1 ;;
esac
case "${FAKE_INSPECT_ODD:-}" in
    volume) vol_inspect=odd ;;
    container) ctr_inspect=odd ;;
esac
if [ "${FAKE_LIST_FAIL:-0}" = "1" ]; then vol_list_fail=1; ctr_list_fail=1; fi
# Once the DATA swap has run (state file "swapped"): FAKE_AFTER_SWAP_INSPECT=odd|fail
# makes the container inspect fail with odd text (fail: the lists fail too), and
# FAKE_AFTER_SWAP_CONTAINER=running|stopped says the data swap container still exists
# (review round 3, I-1: the script no longer probes the container after a swap; exit 125
# always takes the after-swap path, so these switches only prove that no probe happens).
if [ -e "${st}/swapped" ]; then
    case "${FAKE_AFTER_SWAP_INSPECT:-}" in
        odd) ctr_inspect=odd ;;
        fail) ctr_inspect=odd; ctr_list_fail=1 ;;
    esac
fi
# The state of a swap container: running | stopped | "" (absent).
ctr_mode() {
    case "$1" in
        *claude-config-restore-swap) printf '%s' "${FAKE_CLAUDE_SWAP_CONTAINER:-}" ;;
        *-restore-swap)
            if [ -e "${st}/swapped" ] && [ -n "${FAKE_AFTER_SWAP_CONTAINER:-}" ]; then
                printf '%s' "${FAKE_AFTER_SWAP_CONTAINER}"
            else
                printf '%s' "${FAKE_SWAP_CONTAINER:-}"
            fi ;;
    esac
}
# The volume mounted at container path $1 (/dest or /src) in this call's arguments.
# State markers are modelled per volume: file "marker.<volume>" in FAKE_STATE.
mount_vol() {
    want="$1"; shift; prev=""
    for a in "$@"; do
        if [ "${prev}" = "-v" ]; then
            case "${a}" in *":${want}"|*":${want}:ro") printf '%s' "${a%%:*}"; return ;; esac
        fi
        prev="${a}"
    done
}
case "${1:-}" in
    info) exit 0 ;;
    volume)
        case "${2:-}" in
            inspect)
                name="${!#}"
                case "$*" in
                    *"--format {{.Labels}} "*)
                        # The per-run identity check. FAKE_IDENTITY (data temp) /
                        # FAKE_CLAUDE_IDENTITY (Claude temp) change the volume just before
                        # the Nth check of that name (1 = right after create, 2 = before the
                        # state marker, 3 = right before its swap):
                        #   vanished_after_create  -- removed before check 2
                        #   recreated_after_create -- re-made by another run before check 2
                        #   vanished_after_marker  -- removed before check 3
                        case "${name}" in
                            *claude-config-restore-tmp) mode="${FAKE_CLAUDE_IDENTITY:-}" ;;
                            *-restore-tmp) mode="${FAKE_IDENTITY:-}" ;;
                            *) mode="" ;;
                        esac
                        n=$(( $(cat "${st}/inspectn.${name}" 2>/dev/null || echo 0) + 1 ))
                        echo "${n}" > "${st}/inspectn.${name}"
                        case "${mode}:${n}" in
                            vanished_after_create:2|vanished_after_marker:3) rm -f "${st}/vol.${name}" "${st}/marker.${name}" ;;
                            recreated_after_create:2)
                                printf '%s\n' "org.daaf.restore-run=other-run-token" "org.daaf.restore-tmp-for=other" > "${st}/vol.${name}" ;;
                        esac
                        if [ ! -e "${st}/vol.${name}" ]; then
                            echo "Error response from daemon: get ${name}: no such volume" >&2; exit 1
                        fi
                        # Docker prints a Go map: map[k1:v1 k2:v2], keys sorted.
                        labels="$(LC_ALL=C sort "${st}/vol.${name}" | sed 's/=/:/' | tr '\n' ' ')"
                        echo "map[${labels% }]"
                        exit 0 ;;
                esac
                case "${name}" in
                    *-restore-tmp)
                        if [ "${vol_inspect}" = "daemon" ]; then daemon_down; fi
                        if [ "${vol_inspect}" = "odd" ]; then odd_error; fi ;;
                esac
                [ -e "${st}/vol.${name}" ] && exit 0
                echo "Error response from daemon: get ${name}: no such volume" >&2; exit 1 ;;
            create)
                name="${!#}"
                case "${name}" in
                    *claude-config-restore-tmp) fail="${FAKE_CLAUDE_TEMP_CREATE_EXIT:-0}" ;;
                    *) fail="${FAKE_TEMP_CREATE_EXIT:-0}" ;;
                esac
                if [ "${fail}" != "0" ]; then echo "fake docker: volume create failed" >&2; exit "${fail}"; fi
                # FAKE_IDENTITY=reused: another run created this name between the leftover
                # check and this create; Docker then silently REUSES it with its labels.
                if [ "${FAKE_IDENTITY:-}" = "reused" ] && [ "${name%-restore-tmp}" != "${name}" ] && [ "${name%claude-config-restore-tmp}" = "${name}" ]; then
                    printf '%s\n' "org.daaf.restore-run=other-run-token" "org.daaf.restore-tmp-for=other" > "${st}/vol.${name}"
                fi
                # An existing volume is reused unchanged (labels kept), like Docker.
                if [ ! -e "${st}/vol.${name}" ]; then
                    : > "${st}/vol.${name}"
                    prev=""
                    for a in "$@"; do
                        if [ "${prev}" = "--label" ]; then printf '%s\n' "${a}" >> "${st}/vol.${name}"; fi
                        prev="${a}"
                    done
                fi
                echo "${name}"; exit 0 ;;
            rm)
                if [ "${FAKE_VOLUME_RM_EXIT:-0}" != "0" ]; then echo "Error response from daemon: volume is in use" >&2; exit "${FAKE_VOLUME_RM_EXIT}"; fi
                rm -f "${st}/vol.${3:-}" "${st}/marker.${3:-}"; exit 0 ;;
            ls)
                # The S3 exact-name fallback uses `volume ls -q` (every name). Real
                # `--filter name=X` is an UNANCHORED match; modelled as a substring.
                if [ "${vol_list_fail}" = "1" ]; then daemon_down; fi
                pat=""
                for a in "$@"; do case "${a}" in name=*) pat="${a#name=}" ;; esac; done
                for f in "${st}"/vol.*; do
                    [ -e "${f}" ] || continue
                    n="${f##*/vol.}"
                    case "${n}" in *"${pat}"*) echo "${n}" ;; esac
                done
                exit 0 ;;
        esac
        exit 0 ;;
    container)
        # container inspect --format {{.State.Running}} <name>
        name="${!#}"
        if [ "${ctr_inspect}" = "daemon" ]; then daemon_down; fi
        if [ "${ctr_inspect}" = "odd" ]; then odd_error; fi
        mode="$(ctr_mode "${name}")"
        case "${mode}" in
            running|stopped)
                state=false
                if [ "${mode}" = "running" ]; then state=true; fi
                # I-A (review round 2): FAKE_INSPECT_STDERR=first|last prints a stray
                # stderr line before / after the state (the pause keeps the order when
                # a caller merges the two streams).
                case "${FAKE_INSPECT_STDERR:-}" in
                    first) stray_warning; sleep 0.3; echo "${state}" ;;
                    last) echo "${state}"; sleep 0.3; stray_warning ;;
                    *) echo "${state}" ;;
                esac
                exit 0 ;;
        esac
        echo "Error response from daemon: No such container: ${name}" >&2; exit 1 ;;
    ps)
        case "$*" in
            # S3 exact-name fallback lists (every container / running ones only), names
            # on stdout. Modelled names: the default project's two swap containers.
            "ps -a --format {{.Names}}"|"ps --format {{.Names}}")
                if [ "${ctr_list_fail}" = "1" ]; then daemon_down; fi
                for c in daaf_daaf-data-restore-swap daaf_daaf-claude-config-restore-swap; do
                    m="$(ctr_mode "${c}")"
                    case "${2:-}:${m}" in
                        *:running|-a:stopped) echo "${c}" ;;
                    esac
                done
                exit 0 ;;
            # Label reap (ps -aq --filter label=...=<data volume>): FAKE_HELPER_IDS.
            *"label="*"-data")
                if [ -n "${FAKE_HELPER_IDS:-}" ]; then printf '%s\n' ${FAKE_HELPER_IDS}; fi
                exit 0 ;;
            # Two volume filters = the re-check right before the swap. FAKE_PS_AT_SWAP_EXIT:
            # `docker ps` itself fails. A stderr line on success too: the names must come
            # from stdout only (a `2>&1` capture would list it as a container).
            *"volume="*"volume="*)
                if [ "${FAKE_PS_AT_SWAP_EXIT:-0}" != "0" ]; then
                    echo "error during connect: this error may indicate that the docker daemon is not running" >&2
                    exit "${FAKE_PS_AT_SWAP_EXIT}"
                fi
                echo "fake-docker-ps-stderr-notice" >&2
                if [ -n "${FAKE_RUNNING_AT_SWAP:-}" ]; then echo "${FAKE_RUNNING_AT_SWAP}"; fi
                exit 0 ;;
            # One volume filter = the initial running-container check (before the backup
            # list). FAKE_INITIAL_PS_STDERR=1: a stray stderr line, which must never be
            # listed as a container; FAKE_RUNNING_AT_START: a running container's name.
            # FAKE_PS_AT_START_EXIT: `docker ps` itself fails (2026-10-02: refuse).
            "ps --filter volume="*)
                if [ "${FAKE_PS_AT_START_EXIT:-0}" != "0" ]; then
                    echo "error during connect: this error may indicate that the docker daemon is not running" >&2
                    exit "${FAKE_PS_AT_START_EXIT}"
                fi
                if [ "${FAKE_INITIAL_PS_STDERR:-0}" = "1" ]; then stray_warning; fi
                if [ -n "${FAKE_RUNNING_AT_START:-}" ]; then echo "${FAKE_RUNNING_AT_START}"; fi
                exit 0 ;;
        esac
        exit 0 ;;
    create)
        if [ "${FAKE_HELPER_CREATE_EXIT:-0}" != "0" ]; then echo "fake docker: create failed" >&2; exit "${FAKE_HELPER_CREATE_EXIT}"; fi
        echo fakecid0000
        # A stderr line AFTER the ID: a `2>&1` capture would end on this line.
        echo "fake-docker-stderr-notice" >&2
        exit 0 ;;
    cp)
        case "${2:-}" in
            *".daaf-claude-config/.")
                if [ "${FAKE_CLAUDE_CP_EXIT:-0}" != "0" ]; then echo "fake docker: claude copy failed" >&2; exit "${FAKE_CLAUDE_CP_EXIT}"; fi ;;
            *)
                interrupt_here cp
                if [ "${FAKE_CP_EXIT:-0}" != "0" ]; then echo "Error response from daemon: fake copy failure" >&2; exit "${FAKE_CP_EXIT}"; fi ;;
        esac
        exit 0 ;;
    rm)
        if [ "${FAKE_RM_EXIT:-0}" != "0" ]; then echo "fake docker: rm failed" >&2; exit "${FAKE_RM_EXIT}"; fi
        exit 0 ;;
    run)
        # A NAMED volume that does not exist is created (empty, no labels) when a container
        # mounts it -- Docker's behaviour, and the B1 hazard the identity checks guard.
        prev=""
        for a in "$@"; do
            if [ "${prev}" = "-v" ]; then
                src="${a%%:*}"
                case "${src}" in /*|"") ;; *) [ -e "${st}/vol.${src}" ] || : > "${st}/vol.${src}" ;; esac
            fi
            prev="${a}"
        done
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
        # The swaps (--sig-proxy=false, named): FAKE_SWAP_EXIT / FAKE_CLAUDE_SWAP_EXIT. The
        # data swap records that it ran (state file "swapped"; see FAKE_AFTER_SWAP_*).
        case "$*" in *"--sig-proxy=false"*)
            case "$*" in
                *"claude-config-restore-swap"*) exit "${FAKE_CLAUDE_SWAP_EXIT:-0}" ;;
                *) : > "${st}/swapped"; interrupt_here swap; exit "${FAKE_SWAP_EXIT:-0}" ;;
            esac ;;
        esac
        prog="${!#}"
        case "${prog}" in
            # Leftover state-marker probe: FAKE_LEFTOVER_MARKER=absent|present|fail
            # forces the answer; unset, it reads the modelled marker of the /src volume.
            *"test ! -e /src/"*)
                case "${FAKE_LEFTOVER_MARKER:-}" in
                    present) exit 3 ;;
                    fail) echo "fake docker: probe failed" >&2; exit 125 ;;
                    absent) exit 0 ;;
                esac
                if [ -e "${st}/marker.$(mount_vol /src "$@")" ]; then exit 3; fi
                exit 0 ;;
            # Free-space program: FAKE_SPACE_EXIT, FAKE_AVAIL_KB (first check),
            # FAKE_SWAP_AVAIL_KB (the re-check, which also mounts the temp at /src),
            # FAKE_LIVE_KB, FAKE_SRC_KB. Default: 100 GB free.
            *"AVAIL_KB="*)
                if [ "${FAKE_SPACE_EXIT:-0}" != "0" ]; then echo "stat: unrecognized option: f" >&2; exit "${FAKE_SPACE_EXIT}"; fi
                case "$*" in
                    *":/src:ro"*)
                        echo "AVAIL_KB=${FAKE_SWAP_AVAIL_KB:-${FAKE_AVAIL_KB:-104857600}}"
                        echo "LIVE_KB=${FAKE_LIVE_KB:-1000}"
                        echo "SRC_KB=${FAKE_SRC_KB:-1000}" ;;
                    *)
                        echo "AVAIL_KB=${FAKE_AVAIL_KB:-104857600}"
                        echo "LIVE_KB=${FAKE_LIVE_KB:-1000}" ;;
                esac
                exit 0 ;;
            # Post-swap comparison: FAKE_SWAP_VERIFY / FAKE_CLAUDE_SWAP_VERIFY =
            # MATCH|MISMATCH|ERRORS|fail (no marker, exit 1). FAKE_SWAP_VERIFY_ENTRIES /
            # FAKE_CLAUDE_SWAP_VERIFY_ENTRIES: the ENTRIES pair printed with MATCH/MISMATCH
            # (default 3:3; "none" prints no ENTRIES line).
            *"SWAP_VERIFY=MATCH"*)
                case "$*" in
                    *"claude-config-restore-tmp"*) v="${FAKE_CLAUDE_SWAP_VERIFY:-MATCH}"; e="${FAKE_CLAUDE_SWAP_VERIFY_ENTRIES:-3:3}" ;;
                    *) v="${FAKE_SWAP_VERIFY:-MATCH}"; e="${FAKE_SWAP_VERIFY_ENTRIES:-3:3}" ;;
                esac
                case "${v}" in
                    MATCH|MISMATCH)
                        echo "SWAP_VERIFY=${v}"
                        if [ "${e}" != "none" ]; then echo "SWAP_VERIFY_ENTRIES=${e}"; fi
                        exit 0 ;;
                    ERRORS) echo "SWAP_VERIFY_ERRORS=2"; echo "SWAP_VERIFY_ENTRIES=0:0"; exit 0 ;;
                esac
                echo "fake docker: comparison container failed" >&2; exit 1 ;;
            # Permission replay (chmod 644 + 755): FAKE_PERMS_REPLAY_EXIT.
            *"chmod 644"*) exit "${FAKE_PERMS_REPLAY_EXIT:-0}" ;;
            # Symlink replay: FAKE_SYMLINK_REPLAY_EXIT / FAKE_CLAUDE_SYMLINK_REPLAY_EXIT.
            *"ln -sf -- "*)
                case "$*" in
                    *"claude-config-restore-tmp:/dest "*) exit "${FAKE_CLAUDE_SYMLINK_REPLAY_EXIT:-0}" ;;
                esac
                exit "${FAKE_SYMLINK_REPLAY_EXIT:-0}" ;;
        esac
        # Count programs (RESTORED_FILES marker). The TEMP copy's check:
        # FAKE_TEMP_VERIFY_MODE ok|errors|fail|countfail with FAKE_TEMP_COUNT.
        # The post-restore (live) check: FAKE_VERIFY_MODE: ok (RESTORED_FILES marker),
        # errors (the program's read-error marker instead), fail (docker run exits 1),
        # errorsfail (the read-error marker AND a nonzero exit), countfail (a count
        # marker but a nonzero exit -- the count is then not trusted).
        case "$*" in *"find /dest -type f "*"RESTORED_FILES="*)
            case "$*" in *"-restore-tmp:/dest:ro"*)
                case "${FAKE_TEMP_VERIFY_MODE:-ok}" in
                    errors) echo "RESTORED_COUNT_ERRORS=2"; exit 0 ;;
                    fail) echo "fake docker: temp count container failed" >&2; exit 1 ;;
                    countfail) echo "RESTORED_FILES=${FAKE_TEMP_COUNT:-0}"; exit 1 ;;
                esac
                echo "RESTORED_FILES=${FAKE_TEMP_COUNT:-0}"; exit 0 ;;
            esac
            case "${FAKE_VERIFY_MODE:-ok}" in
                errors) echo "RESTORED_COUNT_ERRORS=2"; exit 0 ;;
                fail) echo "fake docker: verification container failed" >&2; exit 1 ;;
                errorsfail) echo "RESTORED_COUNT_ERRORS=2"; exit 1 ;;
                countfail) echo "RESTORED_FILES=${FAKE_RESTORED:-0}"; exit 1 ;;
            esac
            echo "RESTORED_FILES=${FAKE_RESTORED:-0}"; exit 0 ;;
        esac
        # Plain-argument helpers (no sh -c), matched on their full argument tail.
        case "$*" in
            *" test -f /dest/.daaf-permissions")
                [ "${FAKE_PERMS_MANIFEST:-0}" = "1" ] && exit 0; exit 1 ;;
            *"claude-config-restore-tmp:/dest:ro busybox test -f /dest/.daaf-symlinks")
                [ "${FAKE_CLAUDE_SYMLINKS_MANIFEST:-0}" = "1" ] && exit 0; exit 1 ;;
            *" test -f /dest/.daaf-symlinks")
                [ "${FAKE_SYMLINKS_MANIFEST:-0}" = "1" ] && exit 0; exit 1 ;;
            *" rm -rf /dest/.daaf-claude-config") exit "${FAKE_STRIP_EXIT:-0}" ;;
            *"claude-config-restore-tmp:/dest busybox chown -R 1000:1000 /dest") exit "${FAKE_CLAUDE_CHOWN_EXIT:-0}" ;;
            *" chown -R 1000:1000 /dest") exit "${FAKE_CHOWN_EXIT:-0}" ;;
            # The state marker is modelled per volume ("marker.<volume>"): the write
            # creates it, the marker `rm -f` (cleanup unmark / S2) deletes it.
            # FAKE_MARK_EXIT fails every marker write; FAKE_CLAUDE_MARK_EXIT only the
            # Claude temp's (written after the data temp's).
            *" touch /dest/.daaf-restore-swap-started")
                v="$(mount_vol /dest "$@")"
                fail="${FAKE_MARK_EXIT:-0}"
                case "${v}" in *claude-config-restore-tmp) if [ "${fail}" = "0" ]; then fail="${FAKE_CLAUDE_MARK_EXIT:-0}"; fi ;; esac
                if [ "${fail}" != "0" ]; then exit "${fail}"; fi
                : > "${st}/marker.${v}"
                exit 0 ;;
            # S2: the final cleanup deletes the marker from each temp before `volume rm`.
            *" busybox rm -f /dest/.daaf-restore-swap-started")
                rm -f "${st}/marker.$(mount_vol /dest "$@")"
                exit 0 ;;
            # I2: a NEW temp must be empty. FAKE_TEMP_NOT_EMPTY=data|claude lists a stray
            # file in that temp; FAKE_EMPTY_CHECK_EXIT makes the check itself fail;
            # FAKE_FIND_STDERR=1 adds a stray stderr line to a successful, empty listing.
            *" busybox find /dest -mindepth 1")
                if [ "${FAKE_EMPTY_CHECK_EXIT:-0}" != "0" ]; then echo "fake docker: empty check failed" >&2; exit "${FAKE_EMPTY_CHECK_EXIT}"; fi
                if [ "${FAKE_FIND_STDERR:-0}" = "1" ]; then stray_warning; fi
                case "$*:${FAKE_TEMP_NOT_EMPTY:-}" in
                    *"claude-config-restore-tmp:/dest:ro "*":claude") echo "/dest/stray-file" ;;
                    *"claude-config-restore-tmp:/dest:ro "*) ;;
                    *":data") echo "/dest/stray-file" ;;
                esac
                exit 0 ;;
        esac
        echo "fake docker: unmodelled run: $*" >&2
        exit 0 ;;
    *) exit 0 ;;
esac
'@
        $fakePath = Join-Path $script:FakeBin 'docker'
        [System.IO.File]::WriteAllText($fakePath, ($fakeDocker -replace "`r", ""))
        & chmod +x $fakePath

        # Runs the real script against a fresh fixture. -Restored / -TempCount default to
        # the fixture's data-file count. Prompts are answered on stdin in order: the
        # backup number ("1"), the leftover y/n (only when -LeftoverAnswer is given; the
        # prompt appears only when a leftover exists), then -ConfirmAnswer (default RESTORE).
        # -SeedVolumes pre-creates extra volumes (e.g. a leftover temp volume); -Fake
        # passes extra FAKE_* switches. -EndInput: stdin ENDS after the backup number (and
        # -LeftoverAnswer, when given), so the next Read-Host meets end of input. A string
        # piped to a native command gets ONE trailing newline appended (observed on pwsh
        # 7.6: "1" arrives as "1\n", "1`n" as "1\n\n" -- a blank line, not end of input),
        # so that stdin is joined with no trailing newline. Returns Output, ExitCode, Calls
        # (the fake's call log, one line per docker call), Volumes (the volumes left) and
        # Markers (the volumes that still hold the modelled state marker).
        function Invoke-FakeRestore {
            param(
                [int]$DataFiles = 3,
                [int]$Restored = -1,
                [int]$TempCount = -1,
                [switch]$EmptyMount,
                [switch]$CountFail,
                [switch]$Locked,
                [string]$VerifyMode = 'ok',
                [switch]$WithClaude,
                [int]$BigFileKB = 0,
                [string]$ConfirmAnswer = 'RESTORE',
                [string]$LeftoverAnswer = '',
                [switch]$EndInput,
                [string[]]$SeedVolumes = @(),
                [hashtable]$Fake = @{},
                # -NotNested: run WITHOUT DAAF_NESTED (unset in the child, as when the
                # user starts the script in their own window) instead of DAAF_NESTED=1.
                [switch]$NotNested
            )
            $work = Join-Path $TestDrive ('restore-' + [guid]::NewGuid().ToString('N'))
            $bk = Join-Path $work '2026-01-01_daaf_backup'
            $null = New-Item -ItemType Directory -Path $bk
            for ($i = 0; $i -lt $DataFiles; $i++) { [IO.File]::WriteAllText((Join-Path $bk "f$i"), 'x') }
            [IO.File]::WriteAllText((Join-Path $bk '.daaf-symlinks'), '')
            $fileTotal = $DataFiles
            if ($BigFileKB -gt 0) {
                # Apparent size only (SetLength): the real count program sums `stat -c %s`.
                $fs = [IO.File]::Create((Join-Path $bk 'big.bin'))
                try { $fs.SetLength([long]$BigFileKB * 1024) } finally { $fs.Dispose() }
                $fileTotal++
            }
            if ($Restored -lt 0) { $Restored = $fileTotal }
            if ($TempCount -lt 0) { $TempCount = $fileTotal }
            if ($WithClaude) {
                $claudeDir = Join-Path $bk '.daaf-claude-config'
                $null = New-Item -ItemType Directory -Path $claudeDir
                [IO.File]::WriteAllText((Join-Path $claudeDir '.credentials.json'), '{}')
            }
            # (Not "$locked": PowerShell names are case-insensitive, so it would be the
            # [switch]$Locked parameter.)
            $lockedDir = Join-Path $bk 'locked'
            if ($Locked) {
                $null = New-Item -ItemType Directory -Path $lockedDir
                [IO.File]::WriteAllText((Join-Path $lockedDir 'hidden'), 'x')
                & chmod 000 $lockedDir
            }
            $state = Join-Path $work 'docker-state'
            $null = New-Item -ItemType Directory -Path $state
            foreach ($v in (@('daaf_daaf-data', 'daaf_daaf-claude-config') + $SeedVolumes)) {
                [IO.File]::WriteAllText((Join-Path $state "vol.$v"), '')
            }
            $callLog = Join-Path $work 'docker-calls.log'
            # `env -u DAAF_NESTED` (an option, so it comes first) removes it from the
            # child's environment.
            $envLines = @('DAAF_NESTED=1')
            if ($NotNested) { $envLines = @('-u', 'DAAF_NESTED') }
            $envLines += @(
                "PATH=$($script:FakeBin)$([IO.Path]::PathSeparator)$env:PATH",
                # Pin the default names (live: daaf_daaf-data / daaf_daaf-claude-config).
                'DAAF_PROJECT_NAME=daaf',
                'DAAF_DATA_VOLUME_NAME=',
                "FAKE_STATE=$state",
                "FAKE_CALL_LOG=$callLog",
                "FAKE_RESTORED=$Restored",
                "FAKE_TEMP_COUNT=$TempCount",
                "FAKE_EMPTY_MOUNT=$(if ($EmptyMount) { '1' } else { '0' })",
                "FAKE_COUNT_FAIL=$(if ($CountFail) { '1' } else { '0' })",
                "FAKE_VERIFY_MODE=$VerifyMode"
            )
            foreach ($k in $Fake.Keys) { $envLines += "$k=$($Fake[$k])" }
            if ($EndInput) {
                $stdin = '1'
                if ($LeftoverAnswer -ne '') { $stdin += "`n$LeftoverAnswer" }
            } else {
                $stdin = "1`n"
                if ($LeftoverAnswer -ne '') { $stdin += "$LeftoverAnswer`n" }
                $stdin += "$ConfirmAnswer`n"
            }
            Push-Location -LiteralPath $work
            try {
                # env(1) sets the child's environment without touching this session's.
                $out = $stdin | & env @envLines pwsh -NoProfile -File "$RepoRoot/scripts/host/restore_from_backup.ps1" 2>&1 | Out-String
                $code = $LASTEXITCODE
            } finally {
                Pop-Location
                if ($Locked) { & chmod 755 $lockedDir }
            }
            $calls = @()
            if (Test-Path -LiteralPath $callLog) { $calls = @(Get-Content -LiteralPath $callLog) }
            $vols = @(Get-ChildItem -LiteralPath $state -Force -Filter 'vol.*' | ForEach-Object { $_.Name.Substring(4) })
            # Volumes that still hold the (modelled) state marker.
            $marks = @(Get-ChildItem -LiteralPath $state -Force -Filter 'marker.*' | ForEach-Object { $_.Name.Substring(7) })
            [pscustomobject]@{ Output = $out; ExitCode = $code; Calls = $calls; Volumes = $vols; Markers = $marks }
        }

        # Index of the first call-log line matching a regex (-1 when none).
        function Get-CallIndex {
            param([string[]]$Calls, [string]$Pattern)
            for ($i = 0; $i -lt $Calls.Count; $i++) { if ($Calls[$i] -match $Pattern) { return $i } }
            return -1
        }

        # "The live volumes were not touched" from the call log: no `volume rm` or
        # `volume create` of a LIVE name, no writable mount of a live volume (only `:ro`
        # mounts, for the space check), and no swap. Pass a slice to check a prefix.
        function Assert-LiveUntouched {
            param([string[]]$Calls)
            $live = '(daaf_daaf-data|daaf_daaf-claude-config)'
            @($Calls | Where-Object { $_ -match ('^volume (rm|create)( .*)? ' + $live + '$') }).Count | Should -Be 0 -Because 'a live volume is never removed or (re)created'
            @($Calls | Where-Object { $_ -match ('-v ' + $live + ':/dest( |$)') }).Count | Should -Be 0 -Because 'no live volume may be mounted writable before the swap'
            @($Calls | Where-Object { $_ -match '--sig-proxy=false' -or $_ -match '--name \S+-restore-swap' }).Count | Should -Be 0 -Because 'no swap may run'
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

    It "copy-then-swap clean run: temp copy checked, RESTORE asked, then ONE swap, compare, live count, temp removed" {
        $r = Invoke-FakeRestore -DataFiles 3
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*Your current DAAF data is not touched until you confirm below.*"
        $r.Output | Should -BeLike "*Verified: 3 files in the temporary copy.*"
        $r.Output | Should -BeLike "*The backup was copied into Docker and checked: 3 files.*"
        $r.Output | Should -BeLike "*Replacing your DAAF data with the checked copy...*"
        $r.Output | Should -BeLike "*  Restore complete!*"
        # Output order: the temp check, then the RESTORE prompt, then the swap.
        $r.Output.IndexOf('Verified: 3 files in the temporary copy.') | Should -BeLessThan $r.Output.IndexOf('Type RESTORE to confirm')
        $r.Output.IndexOf('Type RESTORE to confirm') | Should -BeLessThan $r.Output.IndexOf('Replacing your DAAF data with the checked copy')
        # Call order.
        $c = $r.Calls
        $create = Get-CallIndex $c '^volume create --label org\.daaf\.restore-tmp-for=daaf_daaf-data --label org\.daaf\.restore-run=\d{14}-\d+-[0-9a-f]{32} daaf_daaf-data-restore-tmp$'
        $cp = Get-CallIndex $c '^cp .*/2026-01-01_daaf_backup/\. fakecid0000:/dest/$'
        $tempCount = Get-CallIndex $c '-v daaf_daaf-data-restore-tmp:/dest:ro busybox sh -c set -e; : > /tmp/count_err'
        $mark = Get-CallIndex $c '-v daaf_daaf-data-restore-tmp:/dest busybox touch /dest/\.daaf-restore-swap-started$'
        $swap = Get-CallIndex $c '^run --rm --sig-proxy=false --name daaf_daaf-data-restore-swap -v daaf_daaf-data-restore-tmp:/src:ro -v daaf_daaf-data:/dest busybox sh -c trap : INT TERM HUP; '
        $compare = Get-CallIndex $c '-v daaf_daaf-data-restore-tmp:/src:ro -v daaf_daaf-data:/dest:ro busybox sh -c export LC_ALL=C;'
        $liveCount = Get-CallIndex $c '^run --rm -v daaf_daaf-data:/dest:ro busybox sh -c set -e; : > /tmp/count_err'
        $remove = Get-CallIndex $c '^volume rm daaf_daaf-data-restore-tmp$'
        foreach ($i in @($create, $cp, $tempCount, $mark, $swap, $compare, $liveCount, $remove)) { $i | Should -BeGreaterThan -1 }
        $cp | Should -BeGreaterThan $create
        $tempCount | Should -BeGreaterThan $cp
        $mark | Should -BeGreaterThan $tempCount
        $swap | Should -BeGreaterThan $mark
        $compare | Should -BeGreaterThan $swap
        $liveCount | Should -BeGreaterThan $compare
        $remove | Should -BeGreaterThan $liveCount
        # Exactly one swap; nothing touched the live volume before it.
        @($c | Where-Object { $_ -match '--sig-proxy=false' }).Count | Should -Be 1
        Assert-LiveUntouched -Calls $c[0..($swap - 1)]
        # The temp volume is gone; the live volumes remain.
        $r.Volumes | Should -Not -Contain 'daaf_daaf-data-restore-tmp'
        $r.Volumes | Should -Contain 'daaf_daaf-data'
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
        # (Narrowed 2026-10-01: "Verified: 3 files in the temporary copy." now precedes the
        # swap; the assertion is about the post-restore count only.)
        $r.Output | Should -Not -BeLike "*Verified: 3 files in restored volume*"
        $r.Output.Contains('Files:    not verified (the restored file count could not be read)') | Should -BeTrue
        $r.Output | Should -BeLike "*Restore completed WITH WARNINGS -- verify before relying on it*"
    }

    # Review round 1 (I4 + B1 fix 4): the post-swap count must EQUAL the checked temp
    # copy's count. Any difference -- 0, one fewer, one more -- is an after-swap failure:
    # the temp copy is kept, the recovery steps are printed, exit 1. Was: "0 files found
    # ... Consider re-running or reinstalling DAAF" (exit 1) and a 1% WARNING (exit 0).
    It "exact post-swap count: RESTORED_FILES=<Restored> vs a temp copy of 3 is an after-swap failure (temp kept, exit 1)" -ForEach @(
        @{ Restored = 0 },
        @{ Restored = 2 },
        @{ Restored = 4 }
    ) {
        $r = Invoke-FakeRestore -DataFiles 3 -TempCount 3 -Restored $Restored
        $r.ExitCode | Should -Be 1
        $r.Output | Should -BeLike "*ERROR: After replacing your DAAF data, it holds $Restored files, but the checked*"
        $r.Output | Should -BeLike "*       copy held 3.*"
        $r.Output | Should -BeLike "*Your DAAF data may now be incomplete. The checked copy of the backup is*"
        $r.Output | Should -BeLike "*kept in Docker (volume(s): daaf_daaf-data-restore-tmp), and your backup*"
        $r.Output | Should -BeLike "*It will offer to remove the leftover copy (answer y) and then redo the restore.*"
        $r.Output | Should -Not -BeLike "*Could not verify the restored file count*"
        $r.Output | Should -Not -BeLike "*0 files found*"
        $r.Output | Should -Not -BeLike "*reinstalling DAAF*"
        $r.Output | Should -Not -BeLike "*File count mismatch*"
        # A fatal exit prints neither banner, and nothing removes the kept copy.
        $r.Output | Should -Not -BeLike "*Restore complete!*"
        $r.Output | Should -Not -BeLike "*Restore completed WITH WARNINGS*"
        $r.Volumes | Should -Contain 'daaf_daaf-data-restore-tmp'
        (Get-CallIndex $r.Calls '^volume rm ') | Should -Be -1
    }

    It "I3: a LOWER-BOUND backup count reached by the temp copy gets an informational note, but latches WITH WARNINGS" -Skip:((& id -u) -eq '0') {
        # 10 files in the temp copy (and so in the restored volume) vs a 3+ count: the
        # note stays informational, but a lower bound cannot prove the restore complete,
        # so the banner is latched -- as backup_daaf.ps1 latches its own lower-bound
        # count. Exit code unchanged (0).
        $r = Invoke-FakeRestore -DataFiles 3 -TempCount 10 -Restored 10 -CountFail -Locked
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*Found 3+ files*"
        $r.Output | Should -BeLike "*The backup count (3+ files) was a lower bound; the restored volume holds*"
        $r.Output | Should -BeLike "*10 files, which is consistent with it.*"
        $r.Output | Should -Not -BeLike "*restore may be incomplete*"
        $r.Output | Should -BeLike "*Restore completed WITH WARNINGS -- verify before relying on it*"
        $r.Output | Should -Not -BeLike "*Restore complete!*"
    }

    It "F1: a Docker count that hits a read error falls back to PowerShell (never a short exact count)" -Skip:((& id -u) -eq '0') {
        # No -CountFail: the REAL program runs and cannot read the locked folder.
        # Before the fix it printed BACKUP_FILES=3 with exit 0 -- "Found 3 files" as
        # if exact -- and the 4-file temp copy would then have been refused as "more".
        $r = Invoke-FakeRestore -DataFiles 3 -TempCount 4 -Restored 4 -Locked
        $r.ExitCode | Should -Be 0
        $r.Output | Should -BeLike "*Docker hit 1 read error(s) while counting this backup*"
        $r.Output | Should -BeLike "*Found 3+ files*"
        $r.Output | Should -BeLike "*Verified: 4 files in the temporary copy.*"
        $r.Output | Should -BeLike "*The backup count (3+ files) was a lower bound*"
    }

    It "I3: with a LOWER-BOUND backup count, a restored count that differs from the temp copy is still an after-swap failure" -Skip:((& id -u) -eq '0') {
        # The lower bound only relaxes the TEMP check (step 3f); the post-swap count is
        # compared with the temp copy's, exactly.
        $r = Invoke-FakeRestore -DataFiles 5 -TempCount 6 -Restored 1 -CountFail -Locked
        $r.ExitCode | Should -Be 1
        $r.Output | Should -BeLike "*Found 5+ files*"
        $r.Output | Should -BeLike "*ERROR: After replacing your DAAF data, it holds 1 files, but the checked*"
        $r.Output | Should -BeLike "*       copy held 6.*"
        $r.Volumes | Should -Contain 'daaf_daaf-data-restore-tmp'
    }

    # ------------------------------------------------------------------------
    # Copy-then-swap (2026-10-01): every branch, driven by the fake's FAKE_* switches.
    # "Live untouched" is asserted from the call log (Assert-LiveUntouched).
    # ------------------------------------------------------------------------

    Context "failures BEFORE the swap leave the live data untouched (exit 1, temp removed)" {
        It "<Name>" -ForEach @(
            @{ Name = 'temp volume create fails'; Fake = @{ FAKE_TEMP_CREATE_EXIT = '1' }; Expect = "ERROR: Could not create a temporary Docker volume ('daaf_daaf-data-restore-tmp') for the restore."; TempMade = $false },
            @{ Name = 'helper container create fails'; Fake = @{ FAKE_HELPER_CREATE_EXIT = '1' }; Expect = 'ERROR: Could not create the helper container for the copy.'; TempMade = $true },
            @{ Name = 'temp copy (docker cp) fails'; Fake = @{ FAKE_CP_EXIT = '1' }; Expect = 'ERROR: Copying the backup into Docker failed.'; TempMade = $true },
            @{ Name = 'Claude-subfolder strip fails'; Fake = @{ FAKE_STRIP_EXIT = '1' }; Expect = 'ERROR: Failed to remove the .daaf-claude-config subfolder from the temporary copy.'; TempMade = $true },
            @{ Name = 'ownership repair fails'; Fake = @{ FAKE_CHOWN_EXIT = '1' }; Expect = 'ERROR: Failed to set file ownership in the temporary copy.'; TempMade = $true },
            @{ Name = 'state marker write fails'; Fake = @{ FAKE_MARK_EXIT = '1' }; Expect = 'ERROR: Could not prepare the temporary copy for the final step.'; TempMade = $true }
        ) {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake $Fake
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*$Expect*"
            $r.Output | Should -BeLike "*Your DAAF data has not been changed.*"
            $r.Output | Should -Not -BeLike "*Restore complete*"
            Assert-LiveUntouched -Calls $r.Calls
            $r.Volumes | Should -Not -Contain 'daaf_daaf-data-restore-tmp'
            $removed = Get-CallIndex $r.Calls '^volume rm daaf_daaf-data-restore-tmp$'
            if ($TempMade) { $removed | Should -BeGreaterThan -1 } else { $removed | Should -Be -1 }
        }

        It "a failed copy names Docker's own last line" {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_CP_EXIT = '1' }
            $r.Output | Should -BeLike "*Docker said: Error response from daemon: fake copy failure*"
        }

        It "a failed copy reaps the labelled helper containers BEFORE removing the temp volume" {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_CP_EXIT = '1'; FAKE_HELPER_IDS = 'helper1' }
            $reap = Get-CallIndex $r.Calls '^ps -aq --filter label=org\.daaf\.restore-tmp-for=daaf_daaf-data$'
            $rmHelper = Get-CallIndex $r.Calls '^rm -f helper1$'
            $rmVol = Get-CallIndex $r.Calls '^volume rm daaf_daaf-data-restore-tmp$'
            $reap | Should -BeGreaterThan -1
            $rmHelper | Should -BeGreaterThan $reap
            $rmVol | Should -BeGreaterThan $rmHelper
        }

        It "the helper CID comes from stdout only (a stderr line after it is not part of the ID)" {
            $r = Invoke-FakeRestore -DataFiles 3
            $r.ExitCode | Should -Be 0
            (Get-CallIndex $r.Calls '^cp .* fakecid0000:/dest/$') | Should -BeGreaterThan -1
            (Get-CallIndex $r.Calls '^rm -f fakecid0000$') | Should -BeGreaterThan -1
            @($r.Calls | Where-Object { $_ -match 'fake-docker-stderr-notice' }).Count | Should -Be 0
        }

        It "a temp removal failure after a prepare failure prints the removal command (exit 1)" {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_CP_EXIT = '1'; FAKE_VOLUME_RM_EXIT = '1' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*The temporary copy could not be removed. To free the space it uses, run:*"
            $r.Output | Should -BeLike "*docker volume rm daaf_daaf-data-restore-tmp*"
            Assert-LiveUntouched -Calls $r.Calls
        }
    }

    Context "checking the temporary copy against the backup count" {
        It "an EXACT backup count must match exactly: fewer files stop the restore" {
            $r = Invoke-FakeRestore -DataFiles 3 -TempCount 2
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: The temporary copy holds 2 files, but the backup has 3,*"
            $r.Output | Should -BeLike "*so the copy into Docker is not complete.*"
            $r.Output | Should -BeLike "*Your DAAF data has not been changed.*"
            # RESTORE is asked only after the check passed.
            $r.Output | Should -Not -BeLike "*DESTRUCTIVE OPERATION*"
            $r.Output | Should -Not -BeLike "*Type RESTORE to confirm*"
            Assert-LiveUntouched -Calls $r.Calls
            $r.Volumes | Should -Not -Contain 'daaf_daaf-data-restore-tmp'
        }

        It "an EXACT backup count must match exactly: MORE files stop the restore too" {
            $r = Invoke-FakeRestore -DataFiles 3 -TempCount 4
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: The temporary copy holds 4 files, but the backup has 3,*"
            Assert-LiveUntouched -Calls $r.Calls
        }

        It "a LOWER-BOUND backup count (N+) passes when the temp copy holds at least N" -Skip:((& id -u) -eq '0') {
            $r = Invoke-FakeRestore -DataFiles 3 -TempCount 10 -Restored 10 -CountFail -Locked
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*Found 3+ files*"
            $r.Output | Should -BeLike "*Verified: 10 files in the temporary copy.*"
            $r.Output | Should -BeLike "*Restore completed WITH WARNINGS*"
        }

        It "a LOWER-BOUND backup count (N+) stops the restore when the temp copy holds fewer than N" -Skip:((& id -u) -eq '0') {
            $r = Invoke-FakeRestore -DataFiles 3 -TempCount 2 -CountFail -Locked
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: The temporary copy holds 2 files, but the backup has 3+,*"
            Assert-LiveUntouched -Calls $r.Calls
        }

        It "a temp count that cannot be read stops the restore (<Mode>)" -ForEach @(
            @{ Mode = 'fail'; Exit = '1' },
            @{ Mode = 'errors'; Exit = '0' },
            @{ Mode = 'countfail'; Exit = '1' }
        ) {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_TEMP_VERIFY_MODE = $Mode }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: Could not count the files in the temporary copy (exit $Exit), so it*"
            $r.Output | Should -BeLike "*cannot be checked against the backup.*"
            Assert-LiveUntouched -Calls $r.Calls
            $r.Volumes | Should -Not -Contain 'daaf_daaf-data-restore-tmp'
        }
    }

    Context "Claude Code state" {
        It "a clean run with Claude state swaps BOTH volumes and removes BOTH temps" {
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*Claude Code state prepared.*"
            $r.Output | Should -BeLike "*Claude Code state restored.*"
            $r.Output | Should -BeLike "*  Restore complete!*"
            (Get-CallIndex $r.Calls '^run --rm --sig-proxy=false --name daaf_daaf-claude-config-restore-swap -v daaf_daaf-claude-config-restore-tmp:/src:ro -v daaf_daaf-claude-config:/dest busybox sh -c trap : INT TERM HUP; ') | Should -BeGreaterThan -1
            # Both prepared before the first swap; the Claude copy comes from the subfolder.
            $firstSwap = Get-CallIndex $r.Calls '--sig-proxy=false'
            (Get-CallIndex $r.Calls '^cp .*/\.daaf-claude-config/\. fakecid0000:/dest/$') | Should -BeLessThan $firstSwap
            Assert-LiveUntouched -Calls $r.Calls[0..($firstSwap - 1)]
            $r.Volumes | Should -Not -Contain 'daaf_daaf-data-restore-tmp'
            $r.Volumes | Should -Not -Contain 'daaf_daaf-claude-config-restore-tmp'
        }

        It "Claude preparation failure stops BEFORE any swap (<Name>), removing both temps" -ForEach @(
            @{ Name = 'temp volume create'; Fake = @{ FAKE_CLAUDE_TEMP_CREATE_EXIT = '1' }; Expect = 'from this backup: a temporary Docker volume could not be created.' },
            @{ Name = 'copy'; Fake = @{ FAKE_CLAUDE_CP_EXIT = '1' }; Expect = 'from this backup: copying it into Docker failed.' },
            @{ Name = 'ownership repair'; Fake = @{ FAKE_CLAUDE_CHOWN_EXIT = '1' }; Expect = 'from this backup: copying it into Docker failed.' }
        ) {
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude -Fake $Fake
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: Could not prepare the Claude Code state (login and session history)*"
            $r.Output | Should -BeLike "*$Expect*"
            $r.Output | Should -BeLike "*Your DAAF data has not been changed.*"
            Assert-LiveUntouched -Calls $r.Calls
            $r.Volumes | Should -Not -Contain 'daaf_daaf-data-restore-tmp'
            $r.Volumes | Should -Not -Contain 'daaf_daaf-claude-config-restore-tmp'
        }

        It "a Claude swap failure keeps BOTH temps and says the project files were restored, the old login may be gone (exit 1)" {
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude -Fake @{ FAKE_CLAUDE_SWAP_EXIT = '7' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: Replacing the Claude Code state (login and session history) did not*"
            $r.Output | Should -BeLike "*complete (exit 7).*"
            $r.Output | Should -BeLike "*Your project files (DAAF data) were restored and checked.*"
            $r.Output | Should -BeLike "*Your previous Claude Code login may also be gone now; running the restore again*"
            $r.Output | Should -BeLike "*kept in Docker (volume(s): daaf_daaf-data-restore-tmp daaf_daaf-claude-config-restore-tmp)*"
            $r.Volumes | Should -Contain 'daaf_daaf-data-restore-tmp'
            $r.Volumes | Should -Contain 'daaf_daaf-claude-config-restore-tmp'
            (Get-CallIndex $r.Calls '^volume rm ') | Should -Be -1
        }

        It "a Claude comparison mismatch after its swap keeps both temps (exit 1)" {
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude -Fake @{ FAKE_CLAUDE_SWAP_VERIFY = 'MISMATCH' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: After replacing the Claude Code state, it could not be confirmed to match*"
            $r.Volumes | Should -Contain 'daaf_daaf-claude-config-restore-tmp'
            (Get-CallIndex $r.Calls '^volume rm ') | Should -Be -1
        }
    }

    Context "the RESTORE confirmation and the swap-time re-check" {
        It "cancel at RESTORE: temp removed, live untouched, exit 0" {
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude -ConfirmAnswer 'no'
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*Restore cancelled. Your DAAF data has not been changed.*"
            $r.Output | Should -Not -BeLike "*Restore complete*"
            Assert-LiveUntouched -Calls $r.Calls
            $r.Volumes | Should -Not -Contain 'daaf_daaf-data-restore-tmp'
            $r.Volumes | Should -Not -Contain 'daaf_daaf-claude-config-restore-tmp'
        }

        It "cancel at RESTORE with a failing temp removal prints the removal command, exit 0" {
            $r = Invoke-FakeRestore -DataFiles 3 -ConfirmAnswer 'no' -Fake @{ FAKE_VOLUME_RM_EXIT = '1' }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*Restore cancelled. Your DAAF data has not been changed.*"
            $r.Output | Should -BeLike "*docker volume rm daaf_daaf-data-restore-tmp*"
        }

        It "a container started on the live volume while preparing: refuse before the swap (exit 1)" {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_RUNNING_AT_SWAP = 'other-daaf-1' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: A container started using your DAAF data while the restore was being*"
            $r.Output | Should -BeLike "*prepared: other-daaf-1*"
            $r.Output | Should -BeLike "*Your DAAF data has not been changed.*"
            # Names from stdout only: the fake's stderr notice is never listed.
            $r.Output | Should -Not -BeLike "*fake-docker-ps-stderr-notice*"
            Assert-LiveUntouched -Calls $r.Calls
            $r.Volumes | Should -Not -Contain 'daaf_daaf-data-restore-tmp'
        }

        It "docker ps FAILS at the swap-time re-check: refuse (could not check), both temps removed, live untouched (exit 1)" {
            # Before 2026-10-01 the re-check read `docker ps` through 2>&1, so a failure
            # was refused with docker's error text listed as a "container" name.
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude -Fake @{ FAKE_PS_AT_SWAP_EXIT = '1' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: Could not check whether DAAF is running (docker ps failed, exit 1),*"
            $r.Output | Should -BeLike "*       so your data cannot be replaced safely. Make sure Docker Desktop is running,*"
            $r.Output | Should -BeLike "*       then run the restore again.*"
            $r.Output | Should -BeLike "*Your DAAF data has not been changed.*"
            $r.Output | Should -Not -BeLike "*A container started using your DAAF data*"
            $r.Output | Should -Not -BeLike "*error during connect*"
            $r.Output | Should -Not -BeLike "*Replacing your DAAF data with the checked copy*"
            Assert-LiveUntouched -Calls $r.Calls
            (Get-CallIndex $r.Calls 'touch /dest/\.daaf-restore-swap-started') | Should -Be -1
            $r.Volumes | Should -Not -Contain 'daaf_daaf-data-restore-tmp'
            $r.Volumes | Should -Not -Contain 'daaf_daaf-claude-config-restore-tmp'
        }
    }

    Context "failures DURING or AFTER the swap keep the checked copy (exit 1)" {
        It "the swap fails: temp kept, recovery steps, exit 1, nothing removed after the swap" {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_SWAP_EXIT = '5' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: Replacing your DAAF data did not complete (exit 5).*"
            $r.Output | Should -BeLike "*Your DAAF data may now be incomplete. The checked copy of the backup is*"
            $r.Output | Should -BeLike "*kept in Docker (volume(s): daaf_daaf-data-restore-tmp), and your backup*"
            $r.Output | Should -BeLike "*folder 2026-01-01_daaf_backup\ is unchanged.*"
            $r.Output.Contains('.\restore_from_backup.ps1') | Should -BeTrue
            $r.Output | Should -BeLike "*It will offer to remove the leftover copy (answer y) and then redo the restore.*"
            $r.Output | Should -Not -BeLike "*Your DAAF data has not been changed*"
            # The S5 "project files were restored" text is for Claude failures only.
            $r.Output | Should -Not -BeLike "*Your project files (DAAF data) were restored and checked*"
            $r.Output | Should -Not -BeLike "*NOTHING was replaced*"
            $r.Volumes | Should -Contain 'daaf_daaf-data-restore-tmp'
            $swap = Get-CallIndex $r.Calls '--sig-proxy=false'
            $swap | Should -BeGreaterThan -1
            @($r.Calls[$swap..($r.Calls.Count - 1)] | Where-Object { $_ -match '^volume rm |^rm -f ' }).Count | Should -Be 0
        }

        It "the post-swap comparison does not match (<Mode>): temp kept, exit 1" -ForEach @(
            @{ Mode = 'MISMATCH' },
            @{ Mode = 'ERRORS' },
            @{ Mode = 'fail' }
        ) {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_SWAP_VERIFY = $Mode }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: After replacing your DAAF data, it could not be confirmed to match the*"
            $r.Output | Should -BeLike "*checked copy (file names, sizes, permissions and owners).*"
            $r.Output | Should -BeLike "*kept in Docker (volume(s): daaf_daaf-data-restore-tmp)*"
            $r.Output | Should -Not -BeLike "*Verifying restore...*"
            $r.Volumes | Should -Contain 'daaf_daaf-data-restore-tmp'
            (Get-CallIndex $r.Calls '^volume rm ') | Should -Be -1
        }

        It "a temp removal failure after a fully checked restore is a latched WARNING, exit 0" {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_VOLUME_RM_EXIT = '1' }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*WARNING: Could not remove the temporary copy of your data (Docker volume(s): daaf_daaf-data-restore-tmp).*"
            $r.Output | Should -BeLike "*Your DAAF data was restored. To free the space it uses, run:*"
            $r.Output | Should -BeLike "*docker volume rm daaf_daaf-data-restore-tmp*"
            $r.Output | Should -BeLike "*Restore completed WITH WARNINGS -- verify before relying on it*"
            $r.Output | Should -Not -BeLike "*Restore complete!*"
        }
    }

    Context "Ctrl+C (SIGINT to pwsh) -- the try/finally" -Skip:($IsMacOS) {
        # Invoke-FakeRestore sets DAAF_NESTED=1 (the Control Panel's setting) unless
        # -NotNested: nested, an interrupt exits 130 (2026-10-02); on its own, 0.
        It "interrupted while PREPARING: the finally removes the temp, says nothing changed" {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_INTERRUPT_AT = 'cp' }
            $r.Output | Should -BeLike "*Restore interrupted. Your DAAF data has not been changed.*"
            $r.Output | Should -Not -BeLike "*Type RESTORE to confirm*"
            Assert-LiveUntouched -Calls $r.Calls
            (Get-CallIndex $r.Calls '^volume rm daaf_daaf-data-restore-tmp$') | Should -BeGreaterThan -1
            $r.Volumes | Should -Not -Contain 'daaf_daaf-data-restore-tmp'
        }

        It "interrupted while PREPARING under DAAF_NESTED exits 130" {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_INTERRUPT_AT = 'cp' }
            $r.ExitCode | Should -Be 130
        }

        It "interrupted DURING the swap: the finally keeps the temp and explains how to finish" {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_INTERRUPT_AT = 'swap' }
            $r.Output | Should -BeLike "*Restore interrupted while your DAAF data was being replaced.*"
            $r.Output | Should -BeLike "*The replacement keeps running inside Docker until it finishes.*"
            $r.Output.Contains('.\restore_from_backup.ps1') | Should -BeTrue
            $r.Output | Should -Not -BeLike "*Restore complete*"
            $r.Volumes | Should -Contain 'daaf_daaf-data-restore-tmp'
            (Get-CallIndex $r.Calls '^volume rm ') | Should -Be -1
        }

        It "interrupted DURING the swap under DAAF_NESTED exits 130, after the finally's full text" {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_INTERRUPT_AT = 'swap' }
            $r.ExitCode | Should -Be 130
            # The last line of the finally's text was printed before the process ended.
            $r.Output.Contains('  .\restore_from_backup.ps1') | Should -BeTrue
            $r.Markers | Should -Contain 'daaf_daaf-data-restore-tmp'
        }

        It "run on its own (no DAAF_NESTED), interrupted while PREPARING: same text and cleanup, exit 0 (known limit)" {
            $r = Invoke-FakeRestore -DataFiles 3 -NotNested -Fake @{ FAKE_INTERRUPT_AT = 'cp' }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*Restore interrupted. Your DAAF data has not been changed.*"
            Assert-LiveUntouched -Calls $r.Calls
            $r.Volumes | Should -Not -Contain 'daaf_daaf-data-restore-tmp'
            $r.Output | Should -Not -BeLike "*Press Enter to continue*"
        }

        It "run on its own (no DAAF_NESTED), interrupted DURING the swap: same text, temp kept, exit 0 (known limit)" {
            $r = Invoke-FakeRestore -DataFiles 3 -NotNested -Fake @{ FAKE_INTERRUPT_AT = 'swap' }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*Restore interrupted while your DAAF data was being replaced.*"
            $r.Volumes | Should -Contain 'daaf_daaf-data-restore-tmp'
            (Get-CallIndex $r.Calls '^volume rm ') | Should -Be -1
        }

        It "an unexpected ERROR inside the try (not a Ctrl+C) under DAAF_NESTED keeps PowerShell's exit 1, never 130" {
            # Fault injection: a SRC_KB at the Int64 maximum makes the space re-check's
            # shortfall a [double] past Int64, so binding it to Format-DaafRestoreGB's
            # [long] parameter throws inside the try (no realistic volume is that big).
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_SRC_KB = '9223372036854775807' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*Int64*"
            Assert-LiveUntouched -Calls $r.Calls
            $r.Volumes | Should -Not -Contain 'daaf_daaf-data-restore-tmp'
        }
    }

    Context "leftovers from an earlier restore" {
        It "no leftover: no y/n prompt, and every name is checked by exact name" {
            $r = Invoke-FakeRestore -DataFiles 3
            $r.Output | Should -Not -BeLike "*Remove it and continue?*"
            (Get-CallIndex $r.Calls '^volume inspect daaf_daaf-data-restore-tmp$') | Should -BeGreaterThan -1
            (Get-CallIndex $r.Calls '^volume inspect daaf_daaf-claude-config-restore-tmp$') | Should -BeGreaterThan -1
            (Get-CallIndex $r.Calls '^container inspect --format \{\{\.State\.Running\}\} daaf_daaf-data-restore-swap$') | Should -BeGreaterThan -1
        }

        It "a volume whose name merely CONTAINS the temp name is not a leftover (exact match)" {
            $r = Invoke-FakeRestore -DataFiles 3 -SeedVolumes @('daaf_daaf-data-restore-tmp-old')
            $r.ExitCode | Should -Be 0
            $r.Output | Should -Not -BeLike "*Remove it and continue?*"
            $r.Volumes | Should -Contain 'daaf_daaf-data-restore-tmp-old'
            (Get-CallIndex $r.Calls 'daaf_daaf-data-restore-tmp-old') | Should -Be -1
        }

        It "a leftover temp volume (y): removed, then the restore runs normally" {
            $r = Invoke-FakeRestore -DataFiles 3 -SeedVolumes @('daaf_daaf-data-restore-tmp') -LeftoverAnswer 'y'
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*A temporary copy left behind by an earlier restore that did not finish was found:*"
            $r.Output | Should -BeLike "*- Docker volume 'daaf_daaf-data-restore-tmp'*"
            $r.Output | Should -BeLike "*That earlier restore stopped before it replaced anything, so your current*"
            $r.Output | Should -BeLike "*Removed the leftover temporary copy.*"
            $r.Output | Should -BeLike "*  Restore complete!*"
            $rm = Get-CallIndex $r.Calls '^volume rm daaf_daaf-data-restore-tmp$'
            $create = Get-CallIndex $r.Calls '^volume create .* daaf_daaf-data-restore-tmp$'
            $rm | Should -BeGreaterThan -1
            $create | Should -BeGreaterThan $rm
        }

        It "a leftover temp volume (n): cancel, exit 0, prints the removal command, nothing created" {
            $r = Invoke-FakeRestore -DataFiles 3 -SeedVolumes @('daaf_daaf-data-restore-tmp') -LeftoverAnswer 'n'
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*Restore cancelled. Your DAAF data has not been changed.*"
            $r.Output | Should -BeLike "*To remove the temporary copy later, run:*"
            $r.Output | Should -BeLike "*  docker volume rm daaf_daaf-data-restore-tmp*"
            $r.Volumes | Should -Contain 'daaf_daaf-data-restore-tmp'
            (Get-CallIndex $r.Calls '^volume (create|rm) ') | Should -Be -1
            Assert-LiveUntouched -Calls $r.Calls
        }

        It "a leftover that cannot be removed: ERROR, exit 1, nothing created" {
            $r = Invoke-FakeRestore -DataFiles 3 -SeedVolumes @('daaf_daaf-data-restore-tmp') -LeftoverAnswer 'y' -Fake @{ FAKE_VOLUME_RM_EXIT = '1' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: Could not remove the temporary copy left by the earlier restore.*"
            $r.Output | Should -BeLike "*docker volume rm daaf_daaf-data-restore-tmp*"
            (Get-CallIndex $r.Calls '^volume create ') | Should -Be -1
            Assert-LiveUntouched -Calls $r.Calls
        }

        It "a leftover holding the swap marker says the earlier restore HAD started replacing data" {
            $r = Invoke-FakeRestore -DataFiles 3 -SeedVolumes @('daaf_daaf-data-restore-tmp') -LeftoverAnswer 'n' -Fake @{ FAKE_LEFTOVER_MARKER = 'present' }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*That earlier restore had started replacing your DAAF data, so your current*"
            $r.Output | Should -Not -BeLike "*stopped before it replaced anything*"
            (Get-CallIndex $r.Calls '^run --rm -v daaf_daaf-data-restore-tmp:/src:ro busybox sh -c test ! -e /src/\.daaf-restore-swap-started \|\| exit 3$') | Should -BeGreaterThan -1
        }

        It "a leftover whose marker cannot be checked says so" {
            $r = Invoke-FakeRestore -DataFiles 3 -SeedVolumes @('daaf_daaf-data-restore-tmp') -LeftoverAnswer 'n' -Fake @{ FAKE_LEFTOVER_MARKER = 'fail' }
            $r.Output | Should -BeLike "*It could not be checked whether that earlier restore had started replacing*"
        }

        It "a RUNNING swap container from an earlier restore: refuse, exit 1, nothing touched" {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_SWAP_CONTAINER = 'running' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: An earlier restore is still replacing your DAAF data inside Docker*"
            $r.Output | Should -BeLike "*(Docker container 'daaf_daaf-data-restore-swap' is running).*"
            (Get-CallIndex $r.Calls '^(volume (create|rm)|rm -f|create) ') | Should -Be -1
            Assert-LiveUntouched -Calls $r.Calls
        }

        It "a STOPPED swap container counts as 'had started' and is removed on y" {
            $r = Invoke-FakeRestore -DataFiles 3 -LeftoverAnswer 'y' -Fake @{ FAKE_SWAP_CONTAINER = 'stopped' }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*- Docker container 'daaf_daaf-data-restore-swap' (stopped)*"
            $r.Output | Should -BeLike "*That earlier restore had started replacing your DAAF data*"
            (Get-CallIndex $r.Calls '^rm -f daaf_daaf-data-restore-swap$') | Should -BeGreaterThan -1
        }
    }

    Context "free space inside Docker" {
        # B = 20480 KB (a 20 MiB file), L = 1000 KB: need max(B, 2B - L) + max(10% of B,
        # 1 GiB) = 39960 + 1048576 = 1088536 KB.
        It "exactly enough free space passes" {
            $r = Invoke-FakeRestore -DataFiles 3 -BigFileKB 20480 -Fake @{ FAKE_AVAIL_KB = '1088536'; FAKE_LIVE_KB = '1000' }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -Not -BeLike "*not enough free space*"
            $r.Output | Should -BeLike "*  Restore complete!*"
        }

        It "one KB short refuses BEFORE any volume is created (exit 1)" {
            $r = Invoke-FakeRestore -DataFiles 3 -BigFileKB 20480 -Fake @{ FAKE_AVAIL_KB = '1088535'; FAKE_LIVE_KB = '1000' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: There is not enough free space inside Docker for this restore.*"
            $r.Output | Should -BeLike "*The restore needs about 1.0 GB free inside Docker*"
            $r.Output | Should -BeLike "*Your DAAF data has not been changed.*"
            (Get-CallIndex $r.Calls '^(volume create|create|cp) ') | Should -Be -1
            Assert-LiveUntouched -Calls $r.Calls
        }

        It "the space check mounts the live volume read-only" {
            $r = Invoke-FakeRestore -DataFiles 3
            (Get-CallIndex $r.Calls '^run --rm -v daaf_daaf-data:/dest:ro busybox sh -c a=\$\(stat -f -c %a /dest\)') | Should -BeGreaterThan -1
        }

        It "too little space for the SWAP (re-check with the temp copy in place) stops before RESTORE" {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_SWAP_AVAIL_KB = '1000' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: There is not enough free space inside Docker to replace your data with the*"
            $r.Output | Should -BeLike "*checked copy: it needs about 1.0 GB free, Docker has 0.0 GB.*"
            $r.Output | Should -Not -BeLike "*Type RESTORE to confirm*"
            Assert-LiveUntouched -Calls $r.Calls
            $r.Volumes | Should -Not -Contain 'daaf_daaf-data-restore-tmp'
        }

        It "unmeasurable free space is a latched WARNING; the restore continues (exit 0)" {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_SPACE_EXIT = '1' }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*WARNING: Could not check the free space inside Docker before the restore.*"
            $r.Output | Should -BeLike "*The restore needs up to about 1.0 GB free inside Docker.*"
            $r.Output | Should -BeLike "*Note: The free space inside Docker could not be checked. Replacing your data*"
            $r.Output | Should -BeLike "*Restore completed WITH WARNINGS -- verify before relying on it*"
            $r.Output | Should -Not -BeLike "*Restore complete!*"
        }
    }

    Context "replay latches on the temporary copy (behavioural; previously count-pinned only)" {
        It "permission replay succeeds: no WARNING, plain banner, replay ran on the TEMP volume" {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_PERMS_MANIFEST = '1' }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*Restoring executable permissions from .daaf-permissions...*"
            $r.Output | Should -Not -BeLike "*Could not fully replay executable permissions*"
            $r.Output | Should -BeLike "*  Restore complete!*"
            (Get-CallIndex $r.Calls '-v daaf_daaf-data-restore-tmp:/dest busybox sh -c set -e; manifest=/dest/\.daaf-permissions; find /dest -type f -exec chmod 644') | Should -BeGreaterThan -1
        }

        It "permission replay fails: latched WARNING, exit 0" {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_PERMS_MANIFEST = '1'; FAKE_PERMS_REPLAY_EXIT = '1' }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*WARNING: Could not fully replay executable permissions.*"
            $r.Output | Should -BeLike "*Your data was copied intact; only file permissions may be off.*"
            $r.Output | Should -BeLike "*Restore completed WITH WARNINGS -- verify before relying on it*"
        }

        It "symlink replay fails: latched WARNING, exit 0, replay ran on the TEMP volume" {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_SYMLINKS_MANIFEST = '1'; FAKE_SYMLINK_REPLAY_EXIT = '1' }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*Restoring symlinks from .daaf-symlinks...*"
            $r.Output | Should -BeLike "*WARNING: Could not fully replay symlinks from the manifest.*"
            $r.Output | Should -BeLike "*Your data was copied intact; only symbolic links may be missing.*"
            $r.Output | Should -BeLike "*Restore completed WITH WARNINGS -- verify before relying on it*"
            (Get-CallIndex $r.Calls '-v daaf_daaf-data-restore-tmp:/dest busybox sh -c set -ef; IFS=;') | Should -BeGreaterThan -1
        }

        It "Claude-state symlink replay fails: latched WARNING, exit 0" {
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude -Fake @{ FAKE_CLAUDE_SYMLINKS_MANIFEST = '1'; FAKE_CLAUDE_SYMLINK_REPLAY_EXIT = '1' }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*WARNING: Could not fully replay Claude state symlinks.*"
            $r.Output | Should -BeLike "*Restore completed WITH WARNINGS -- verify before relying on it*"
            (Get-CallIndex $r.Calls '-v daaf_daaf-claude-config-restore-tmp:/dest busybox sh -c set -ef; IFS=;') | Should -BeGreaterThan -1
        }
    }

    # ------------------------------------------------------------------------
    # Review round 1 (2026-10-01), mirroring tests/bash/restore_from_backup.bats "B1:",
    # "I1:", "I2:", "I3:", "item 5 + S3:" and "S2:". B1: each temp volume carries a
    # per-run identity label, re-checked before the state marker and before each swap;
    # a temp that is no longer ours is refused and NOTHING is removed. I1: end of input
    # at a prompt is a cancel. I2: an inspect failure is never "absent"; a new temp must
    # be empty and ours. I3: "nothing changed" wording after an earlier swap had started.
    # ------------------------------------------------------------------------

    Context "B1: the temporary copy must still be this run's when it is used" {
        It "a temp volume that VANISHED while the RESTORE prompt waited: refuse, nothing removed, no marker, no swap" {
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude -Fake @{ FAKE_IDENTITY = 'vanished_after_create' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: The temporary copy of the backup in Docker (volume 'daaf_daaf-data-restore-tmp') was changed by*"
            $r.Output | Should -BeLike "*       started in another window. It was not used, and nothing was removed.*"
            $r.Output | Should -BeLike "*       Your DAAF data has not been changed.*"
            $r.Output | Should -BeLike "*       Close any other restore window, then run this restore again.*"
            $r.Output | Should -Not -BeLike "*Replacing your DAAF data with the checked copy*"
            (Get-CallIndex $r.Calls '^volume rm ') | Should -Be -1
            (Get-CallIndex $r.Calls 'touch /dest/\.daaf-restore-swap-started') | Should -Be -1
            # "Nothing was removed" includes another run's prepare helpers (the label reap).
            (Get-CallIndex $r.Calls '^ps -aq ') | Should -Be -1
            Assert-LiveUntouched -Calls $r.Calls
            # The Claude temp this run made is left too (the next run lists it as a leftover).
            $r.Volumes | Should -Contain 'daaf_daaf-claude-config-restore-tmp'
        }

        It "a temp volume RECREATED by another run (different token) while the prompt waited: refuse, nothing removed" {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_IDENTITY = 'recreated_after_create' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*was changed by*"
            $r.Output | Should -BeLike "*It was not used, and nothing was removed.*"
            (Get-CallIndex $r.Calls '^volume rm ') | Should -Be -1
            (Get-CallIndex $r.Calls '^ps -aq ') | Should -Be -1
            $r.Volumes | Should -Contain 'daaf_daaf-data-restore-tmp'
            Assert-LiveUntouched -Calls $r.Calls
        }

        It "a temp volume that vanished AFTER the marker write is re-checked right before the swap: no swap" {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_IDENTITY = 'vanished_after_marker' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*It was not used, and nothing was removed.*"
            @($r.Calls | Where-Object { $_ -match 'touch /dest/\.daaf-restore-swap-started' }).Count | Should -Be 1
            (Get-CallIndex $r.Calls '^volume rm ') | Should -Be -1
            (Get-CallIndex $r.Calls '^ps -aq ') | Should -Be -1
            Assert-LiveUntouched -Calls $r.Calls
        }

        It "the identity check runs after create, before the marker write and before each swap (call order)" {
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude
            $r.ExitCode | Should -Be 0
            $c = $r.Calls
            @($c | Where-Object { $_ -ceq 'volume inspect --format {{.Labels}} daaf_daaf-data-restore-tmp' }).Count | Should -Be 3
            @($c | Where-Object { $_ -ceq 'volume inspect --format {{.Labels}} daaf_daaf-claude-config-restore-tmp' }).Count | Should -Be 3
            $dataChecks = @(for ($i = 0; $i -lt $c.Count; $i++) { if ($c[$i] -ceq 'volume inspect --format {{.Labels}} daaf_daaf-data-restore-tmp') { $i } })
            $claudeChecks = @(for ($i = 0; $i -lt $c.Count; $i++) { if ($c[$i] -ceq 'volume inspect --format {{.Labels}} daaf_daaf-claude-config-restore-tmp') { $i } })
            $create = Get-CallIndex $c '^volume create .* daaf_daaf-data-restore-tmp$'
            $restore = Get-CallIndex $c '^ps --filter volume=daaf_daaf-data --filter volume=daaf_daaf-claude-config '
            $lastMark = -1
            for ($i = 0; $i -lt $c.Count; $i++) { if ($c[$i] -match 'touch /dest/\.daaf-restore-swap-started$') { $lastMark = $i } }
            $dataSwap = Get-CallIndex $c '--name daaf_daaf-data-restore-swap '
            $claudeSwap = Get-CallIndex $c '--name daaf_daaf-claude-config-restore-swap '
            foreach ($i in @($create, $restore, $lastMark, $dataSwap, $claudeSwap)) { $i | Should -BeGreaterThan -1 }
            # 1: right after its create (before the RESTORE-time re-check); 2: after RESTORE,
            # before the marker; 3: after the marker, right before its own swap.
            $dataChecks[0] | Should -BeGreaterThan $create
            $dataChecks[0] | Should -BeLessThan $restore
            $dataChecks[1] | Should -BeGreaterThan $restore
            $dataChecks[1] | Should -BeLessThan $lastMark
            $dataChecks[2] | Should -BeGreaterThan $lastMark
            $dataChecks[2] | Should -Be ($dataSwap - 1)
            $claudeChecks[1] | Should -BeLessThan $lastMark
            $claudeChecks[2] | Should -BeGreaterThan $dataSwap
            $claudeChecks[2] | Should -Be ($claudeSwap - 1)
        }

        It "the Claude temp changed before the Claude swap: after-swap failure, data temp kept, Claude temp not listed" {
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude -Fake @{ FAKE_CLAUDE_IDENTITY = 'vanished_after_marker' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: The temporary copy of the Claude Code state (volume 'daaf_daaf-claude-config-restore-tmp')*"
            $r.Output | Should -BeLike "*window -- so it was not used.*"
            $r.Output | Should -BeLike "*kept in Docker (volume(s): daaf_daaf-data-restore-tmp), and your backup*"
            (Get-CallIndex $r.Calls '--name daaf_daaf-claude-config-restore-swap') | Should -Be -1
            (Get-CallIndex $r.Calls '^volume rm ') | Should -Be -1
            $r.Volumes | Should -Contain 'daaf_daaf-data-restore-tmp'
        }

        It "a data-volume comparison with ENTRIES <Entries> is rejected after the swap (temp kept, exit 1)" -ForEach @(
            @{ Entries = '0:0' },
            @{ Entries = '3:2' },
            @{ Entries = 'none' }
        ) {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_SWAP_VERIFY_ENTRIES = $Entries }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: After replacing your DAAF data, it could not be confirmed to match the*"
            $r.Output | Should -BeLike "*kept in Docker (volume(s): daaf_daaf-data-restore-tmp), and your backup*"
            $r.Output | Should -Not -BeLike "*Restore complete*"
            (Get-CallIndex $r.Calls '^volume rm ') | Should -Be -1
        }

        It "an EMPTY Claude volume (ENTRIES 0:0, a backup taken before any login) still restores" {
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude -Fake @{ FAKE_CLAUDE_SWAP_VERIFY_ENTRIES = '0:0' }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*Claude Code state restored.*"
            $r.Output | Should -BeLike "*  Restore complete!*"
        }
    }

    Context "I1: end of input at a prompt is a cancel" {
        It "end of input at the RESTORE prompt: cancel, exit 0, both temps removed, live untouched" {
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude -EndInput
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*DESTRUCTIVE OPERATION*"
            $r.Output | Should -BeLike "*Restore cancelled. Your DAAF data has not been changed.*"
            $r.Output | Should -Not -BeLike "*Replacing your DAAF data*"
            @($r.Calls | Where-Object { $_ -match '^volume rm daaf_daaf-(data|claude-config)-restore-tmp$' }).Count | Should -Be 2
            $r.Volumes | Should -Not -Contain 'daaf_daaf-data-restore-tmp'
            $r.Volumes | Should -Not -Contain 'daaf_daaf-claude-config-restore-tmp'
            Assert-LiveUntouched -Calls $r.Calls
        }

        It "end of input at the leftover prompt: a no, exit 0, nothing created or removed" {
            $r = Invoke-FakeRestore -DataFiles 3 -SeedVolumes @('daaf_daaf-data-restore-tmp') -EndInput
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*Remove it and continue? (y/n)*"
            $r.Output | Should -BeLike "*Restore cancelled. Your DAAF data has not been changed.*"
            $r.Output | Should -BeLike "*  docker volume rm daaf_daaf-data-restore-tmp*"
            @($r.Calls | Where-Object { $_ -match '^(volume create|volume rm|create|cp) ' }).Count | Should -Be 0
            $r.Volumes | Should -Contain 'daaf_daaf-data-restore-tmp'
        }
    }

    Context "I2: exact-name checks that cannot be made, and new temps that are not empty or not ours" {
        It "a leftover <Kind> inspect that FAILS (not 'no such ...') refuses: could not check, nothing created" -ForEach @(
            @{ Kind = 'volume' },
            @{ Kind = 'container' }
        ) {
            $r = Invoke-FakeRestore -DataFiles 3 -LeftoverAnswer 'y' -Fake @{ FAKE_INSPECT_FAIL = $Kind }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: Could not check for a temporary copy left by an earlier restore (docker*"
            $r.Output | Should -BeLike "*       $Kind inspect failed: Cannot connect to the Docker daemon*"
            $r.Output | Should -BeLike "*This restore has not changed anything. Make sure Docker Desktop is running,*"
            $r.Output | Should -BeLike "*If this keeps happening, restart Docker Desktop*"
            $r.Output | Should -Not -BeLike "*A temporary copy left behind by an earlier restore*"
            @($r.Calls | Where-Object { $_ -match '^(volume create|volume rm|create|cp|rm) ' }).Count | Should -Be 0
            Assert-LiveUntouched -Calls $r.Calls
        }

        It "a NEW temp volume that is <Name> is refused and LEFT ALONE" -ForEach @(
            @{ Name = 'not empty'; Fake = @{ FAKE_TEMP_NOT_EMPTY = 'data' } },
            @{ Name = 'not checkable (the empty check fails)'; Fake = @{ FAKE_EMPTY_CHECK_EXIT = '1' } },
            @{ Name = 'a reused volume carrying another run''s labels'; Fake = @{ FAKE_IDENTITY = 'reused' } }
        ) {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake $Fake
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: Could not confirm that the new temporary Docker volume 'daaf_daaf-data-restore-tmp' is empty*"
            $r.Output | Should -BeLike "*and was created by this restore, so it was left as it is (it may belong to*"
            $r.Output | Should -BeLike "*Your DAAF data has not been changed.*"
            $r.Output | Should -Not -BeLike "*DESTRUCTIVE OPERATION*"
            (Get-CallIndex $r.Calls '^volume rm ') | Should -Be -1
            (Get-CallIndex $r.Calls '^cp ') | Should -Be -1
            # SF2 (review round 2): the refused temp may be another restore's, so its prepare
            # helpers are not reaped either (no label reap at all).
            (Get-CallIndex $r.Calls '^ps -aq ') | Should -Be -1
            $r.Volumes | Should -Contain 'daaf_daaf-data-restore-tmp'
            Assert-LiveUntouched -Calls $r.Calls
        }

        It "a non-empty new CLAUDE temp is left alone; the data temp this run created is removed" {
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude -Fake @{ FAKE_TEMP_NOT_EMPTY = 'claude' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*new temporary Docker volume 'daaf_daaf-claude-config-restore-tmp' is empty*"
            @($r.Calls | Where-Object { $_ -ceq 'volume rm daaf_daaf-data-restore-tmp' }).Count | Should -Be 1
            @($r.Calls | Where-Object { $_ -ceq 'volume rm daaf_daaf-claude-config-restore-tmp' }).Count | Should -Be 0
            $r.Volumes | Should -Contain 'daaf_daaf-claude-config-restore-tmp'
            Assert-LiveUntouched -Calls $r.Calls
            # SF2 (review round 2): careful cleanup -- no label reap, and the data temp is
            # removed only after an identity check made AFTER the Claude refusal.
            (Get-CallIndex $r.Calls '^ps -aq ') | Should -Be -1
            $claudeRefusal = Get-CallIndex $r.Calls 'claude-config-restore-tmp:/dest:ro busybox find /dest -mindepth 1$'
            $after = @($r.Calls[($claudeRefusal + 1)..($r.Calls.Count - 1)])
            $idCheck = Get-CallIndex $after '^volume inspect --format \{\{\.Labels\}\} daaf_daaf-data-restore-tmp$'
            $rmData = Get-CallIndex $after '^volume rm daaf_daaf-data-restore-tmp$'
            $claudeRefusal | Should -BeGreaterThan -1
            $idCheck | Should -BeGreaterThan -1
            $rmData | Should -BeGreaterThan $idCheck
        }

        It "SF2: a refused Claude temp, with the DATA temp no longer this run's at cleanup: nothing is removed" {
            # The data temp is re-made by another run between its creation and the careful
            # cleanup's identity check, so it is left alone too.
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude -Fake @{ FAKE_TEMP_NOT_EMPTY = 'claude'; FAKE_IDENTITY = 'recreated_after_create' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*new temporary Docker volume 'daaf_daaf-claude-config-restore-tmp' is empty*"
            (Get-CallIndex $r.Calls '^volume rm ') | Should -Be -1
            (Get-CallIndex $r.Calls '^ps -aq ') | Should -Be -1
            @($r.Calls | Where-Object { $_ -ceq 'volume inspect --format {{.Labels}} daaf_daaf-data-restore-tmp' }).Count | Should -Be 2
            $r.Volumes | Should -Contain 'daaf_daaf-data-restore-tmp'
            $r.Volumes | Should -Contain 'daaf_daaf-claude-config-restore-tmp'
            Assert-LiveUntouched -Calls $r.Calls
        }

        It "a stray stderr line during the new-temp emptiness check does not refuse" {
            # Review round 2: through 2>&1 a Docker config WARNING once made every new temp
            # look non-empty. The listing is read from stdout only.
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude -Fake @{ FAKE_FIND_STDERR = '1' }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -Not -BeLike "*Could not confirm that the new temporary Docker volume*"
            $r.Output | Should -BeLike "*Claude Code state restored.*"
            $r.Output | Should -BeLike "*  Restore complete!*"
        }
    }

    Context "I3: 'nothing changed' wording after an earlier restore had started replacing data" {
        It "a leftover with the swap marker: answer n says the data may still be incomplete" {
            $r = Invoke-FakeRestore -DataFiles 3 -SeedVolumes @('daaf_daaf-data-restore-tmp') -LeftoverAnswer 'n' -Fake @{ FAKE_LEFTOVER_MARKER = 'present' }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*Restore cancelled. This restore did not change anything, but your DAAF data may still be*"
            $r.Output | Should -BeLike "*incomplete from the earlier restore. Run the restore again to finish it.*"
            $r.Output | Should -Not -BeLike "*Your DAAF data has not been changed.*"
        }

        It "a leftover with the swap marker: answer y, then cancel at RESTORE" {
            $r = Invoke-FakeRestore -DataFiles 3 -SeedVolumes @('daaf_daaf-data-restore-tmp') -LeftoverAnswer 'y' -ConfirmAnswer 'no' -Fake @{ FAKE_LEFTOVER_MARKER = 'present' }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*Restore cancelled. This restore did not change anything, but your DAAF data may still be*"
            $r.Output | Should -Not -BeLike "*Your DAAF data has not been changed.*"
        }

        It "a leftover with the swap marker: answer y, then a refusal before the swap (ERROR-block indentation)" {
            $r = Invoke-FakeRestore -DataFiles 3 -SeedVolumes @('daaf_daaf-data-restore-tmp') -LeftoverAnswer 'y' -Fake @{ FAKE_LEFTOVER_MARKER = 'present'; FAKE_MARK_EXIT = '1' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: Could not prepare the temporary copy for the final step.*"
            $r.Output | Should -BeLike "*       This restore did not change anything, but your DAAF data may still be*"
            $r.Output | Should -BeLike "*       incomplete from the earlier restore. Run the restore again to finish it.*"
            $r.Output | Should -Not -BeLike "*Your DAAF data has not been changed.*"
        }

        It "a leftover whose marker could NOT be checked gets the incomplete wording; a clean leftover does not" {
            $r = Invoke-FakeRestore -DataFiles 3 -SeedVolumes @('daaf_daaf-data-restore-tmp') -LeftoverAnswer 'n' -Fake @{ FAKE_LEFTOVER_MARKER = 'fail' }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*Restore cancelled. This restore did not change anything, but your DAAF data may still be*"
            $r = Invoke-FakeRestore -DataFiles 3 -SeedVolumes @('daaf_daaf-data-restore-tmp') -LeftoverAnswer 'n'
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*Restore cancelled. Your DAAF data has not been changed.*"
            $r.Output | Should -Not -BeLike "*This restore did not change anything*"
        }

        It "a stopped swap container also counts as 'had started' (incomplete wording on n)" {
            $r = Invoke-FakeRestore -DataFiles 3 -LeftoverAnswer 'n' -Fake @{ FAKE_SWAP_CONTAINER = 'stopped' }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*Restore cancelled. This restore did not change anything, but your DAAF data may still be*"
        }
    }

    Context "item 5 + S3, and S2" {
        It "the leftover prompt says to answer n while another restore window is open; refusals name a next step" {
            $r = Invoke-FakeRestore -DataFiles 3 -SeedVolumes @('daaf_daaf-data-restore-tmp') -LeftoverAnswer 'n'
            $r.Output | Should -BeLike "*If another restore window is still open, answer n.*"
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_SWAP_CONTAINER = 'running' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*       If this keeps happening, restart Docker Desktop and try again.*"
            $r = Invoke-FakeRestore -DataFiles 3 -SeedVolumes @('daaf_daaf-data-restore-tmp') -LeftoverAnswer 'y' -Fake @{ FAKE_VOLUME_RM_EXIT = '1' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*       If this keeps happening, restart Docker Desktop and try again.*"
        }

        It "S2: after a verified restore, each temp's state marker is deleted BEFORE its volume rm; not on a cancel" {
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude
            $r.ExitCode | Should -Be 0
            foreach ($t in @('daaf_daaf-data-restore-tmp', 'daaf_daaf-claude-config-restore-tmp')) {
                $unmark = Get-CallIndex $r.Calls ("-v $([regex]::Escape($t)):/dest busybox rm -f /dest/\.daaf-restore-swap-started$")
                $rmVol = Get-CallIndex $r.Calls ('^volume rm ' + [regex]::Escape($t) + '$')
                $unmark | Should -BeGreaterThan -1
                $rmVol | Should -BeGreaterThan $unmark
                # The unmark runs after every check (after the live count).
                $unmark | Should -BeGreaterThan (Get-CallIndex $r.Calls '^run --rm -v daaf_daaf-data:/dest:ro busybox sh -c set -e; : > /tmp/count_err')
            }
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude -ConfirmAnswer 'no'
            (Get-CallIndex $r.Calls 'rm -f /dest/\.daaf-restore-swap-started') | Should -Be -1
        }
    }

    Context "S4: a backup count from the PowerShell fallback is a LOWER BOUND for the temp copy" {
        # Docker could not count the folder (empty bind-mount view, or the count failed),
        # so the count came from Get-ChildItem: never authoritative, even without read
        # errors. The temp copy must reach it; more is fine.
        It "fallback after an EMPTY bind-mount view (3 files): a temp copy of 5 passes" {
            $r = Invoke-FakeRestore -DataFiles 3 -TempCount 5 -Restored 5 -EmptyMount
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*Found 3 files*"
            $r.Output | Should -BeLike "*Verified: 5 files in the temporary copy.*"
            $r.Output | Should -BeLike "*Verified: 5 files in restored volume.*"
        }

        It "fallback after a failed Docker count (3 files): a temp copy of 4 passes" {
            $r = Invoke-FakeRestore -DataFiles 3 -TempCount 4 -Restored 4 -CountFail
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*Could not count the backup inside Docker*"
            $r.Output | Should -BeLike "*Verified: 4 files in the temporary copy.*"
        }

        It "fallback count (3 files): a temp copy of 2 is still refused before the prompt" {
            $r = Invoke-FakeRestore -DataFiles 3 -TempCount 2 -CountFail
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: The temporary copy holds 2 files, but the backup has 3,*"
            $r.Output | Should -Not -BeLike "*Type RESTORE to confirm*"
            Assert-LiveUntouched -Calls $r.Calls
        }

        It "a Docker (exact) count is still exact: a temp copy of 4 vs 3 is refused" {
            $r = Invoke-FakeRestore -DataFiles 3 -TempCount 4
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: The temporary copy holds 4 files, but the backup has 3,*"
        }
    }

    # ------------------------------------------------------------------------
    # Review round 2 (2026-10-01), mirroring the .sh twin's fix round 2. S1: a data swap
    # that provably replaced NOTHING (ONLY the program's own refusal, exit 3 -- review
    # round 3, I-1: Docker's 125 can follow a daemon restart mid-swap, after the rm ran)
    # is not reported as "may be incomplete"; its cleanup is careful. I-A: a swap container's running state is read from stdout only. S3: an
    # inspect error that is not "no such ..." falls back to exact-name lists. S2: a
    # refusal after the marker write unmarks this run's other temp. S5: plain wording for
    # a Claude failure after the data swap was checked.
    # ------------------------------------------------------------------------

    Context "S1: a data swap that provably replaced NOTHING" {
        It "swap exit <Exit> (<Why>): 'NOTHING was replaced', exit 1, careful cleanup, marker-free" -ForEach @(
            @{ Exit = '3'; Why = 'its own refusal'; Fake = @{} }
        ) {
            # (Not "$fake": PowerShell names are case-insensitive, so it would be $Fake.)
            $merged = @{ FAKE_SWAP_EXIT = $Exit }
            foreach ($k in $Fake.Keys) { $merged[$k] = $Fake[$k] }
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude -Fake $merged
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: The temporary copy of the backup in Docker was gone or could not be used*"
            $r.Output | Should -BeLike "*       (exit $Exit), so NOTHING was replaced. Run the restore again.*"
            $r.Output | Should -BeLike "*       Your DAAF data has not been changed.*"
            $r.Output | Should -Not -BeLike "*incomplete*"
            $r.Output | Should -Not -BeLike "*Replacing your DAAF data did not complete*"
            $r.Output | Should -Not -BeLike "*Restore interrupted*"
            $r.Output | Should -Not -BeLike "*Restore complete*"
            $c = $r.Calls
            $swap = Get-CallIndex $c '--name daaf_daaf-data-restore-swap '
            $swap | Should -BeGreaterThan -1
            Assert-LiveUntouched -Calls $c[0..($swap - 1)]
            (Get-CallIndex $c '--name daaf_daaf-claude-config-restore-swap') | Should -Be -1
            $after = @($c[($swap + 1)..($c.Count - 1)])
            # Exit 3 is decided without asking Docker: no container probe, no exact-name list.
            (Get-CallIndex $after '^container inspect ') | Should -Be -1
            (Get-CallIndex $after '^ps -a --format ') | Should -Be -1
            # Careful cleanup: no label reap; per temp: identity check, marker rm -f, volume rm.
            (Get-CallIndex $c '^ps -aq ') | Should -Be -1
            foreach ($t in @('daaf_daaf-data-restore-tmp', 'daaf_daaf-claude-config-restore-tmp')) {
                $te = [regex]::Escape($t)
                $id = Get-CallIndex $after ('^volume inspect --format \{\{\.Labels\}\} ' + $te + '$')
                $unmark = Get-CallIndex $after ('-v ' + $te + ':/dest busybox rm -f /dest/\.daaf-restore-swap-started$')
                $rm = Get-CallIndex $after ('^volume rm ' + $te + '$')
                $id | Should -BeGreaterThan -1 -Because "$t is identity-checked before removal"
                $unmark | Should -BeGreaterThan $id -Because "$t loses its marker after the identity check"
                $rm | Should -BeGreaterThan $unmark -Because "$t is removed after its marker"
            }
            $r.Volumes | Should -Not -Contain 'daaf_daaf-data-restore-tmp'
            $r.Volumes | Should -Not -Contain 'daaf_daaf-claude-config-restore-tmp'
            $r.Markers.Count | Should -Be 0
        }

        It "swap exit 3 whose temp cannot be removed leaves a MARKER-FREE leftover" {
            # The kept temp no longer holds the state marker, so the next run reports that
            # the earlier restore "stopped before it replaced anything" -- which is true.
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_SWAP_EXIT = '3'; FAKE_VOLUME_RM_EXIT = '1' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*(exit 3), so NOTHING was replaced. Run the restore again.*"
            $r.Output | Should -BeLike "*The temporary copy could not be removed. To free the space it uses, run:*"
            $r.Output | Should -BeLike "*docker volume rm daaf_daaf-data-restore-tmp*"
            $r.Output | Should -Not -BeLike "*incomplete*"
            $r.Volumes | Should -Contain 'daaf_daaf-data-restore-tmp'
            $r.Markers | Should -Not -Contain 'daaf_daaf-data-restore-tmp'
        }

        It "swap exit 3 after an earlier restore HAD started: the 'may still be incomplete' wording" {
            $r = Invoke-FakeRestore -DataFiles 3 -SeedVolumes @('daaf_daaf-data-restore-tmp') -LeftoverAnswer 'y' -Fake @{ FAKE_LEFTOVER_MARKER = 'present'; FAKE_SWAP_EXIT = '3' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*(exit 3), so NOTHING was replaced. Run the restore again.*"
            $r.Output | Should -BeLike "*       This restore did not change anything, but your DAAF data may still be*"
            $r.Output | Should -Not -BeLike "*Your DAAF data has not been changed.*"
            $r.Output | Should -Not -BeLike "*Your DAAF data may now be incomplete*"
        }

        # Review round 3 (I-1): 125 is the after-swap path whether or not the swap container
        # still exists -- a daemon restart mid-swap can return 125 after the rm ran (moby
        # PR #34999 / #46857), and the container may then be gone as well.
        It "swap exit 125 when <Name>: the after-swap path (temp and its marker kept, exit 1)" -ForEach @(
            @{ Name = 'the swap container is gone'; Fake = @{} },
            @{ Name = 'odd inspect text (the exact-name list would say absent)'; Fake = @{ FAKE_AFTER_SWAP_INSPECT = 'odd' } },
            @{ Name = 'the swap container still exists (stopped)'; Fake = @{ FAKE_AFTER_SWAP_CONTAINER = 'stopped' } },
            @{ Name = 'the swap container is still running'; Fake = @{ FAKE_AFTER_SWAP_CONTAINER = 'running' } },
            @{ Name = 'odd inspect text, and the exact-name list says it exists'; Fake = @{ FAKE_AFTER_SWAP_INSPECT = 'odd'; FAKE_AFTER_SWAP_CONTAINER = 'stopped' } },
            @{ Name = 'its state cannot be checked (odd inspect text, the list fails)'; Fake = @{ FAKE_AFTER_SWAP_INSPECT = 'fail' } }
        ) {
            $merged = @{ FAKE_SWAP_EXIT = '125' }
            foreach ($k in $Fake.Keys) { $merged[$k] = $Fake[$k] }
            $r = Invoke-FakeRestore -DataFiles 3 -Fake $merged
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: Replacing your DAAF data did not complete (exit 125).*"
            $r.Output | Should -BeLike "*Your DAAF data may now be incomplete. The checked copy of the backup is*"
            $r.Output | Should -BeLike "*kept in Docker (volume(s): daaf_daaf-data-restore-tmp), and your backup*"
            $r.Output | Should -Not -BeLike "*NOTHING was replaced*"
            $r.Volumes | Should -Contain 'daaf_daaf-data-restore-tmp'
            # The marker stays: it is the evidence that a swap may have started.
            $r.Markers | Should -Contain 'daaf_daaf-data-restore-tmp'
            $swap = Get-CallIndex $r.Calls '--sig-proxy=false'
            @($r.Calls[($swap + 1)..($r.Calls.Count - 1)] | Where-Object { $_ -match '^volume rm |^rm -f |busybox rm -f ' }).Count | Should -Be 0
            # No container probe or exact-name list once the swap ran (nothing to decide).
            @($r.Calls[($swap + 1)..($r.Calls.Count - 1)] | Where-Object { $_ -match '^container inspect |^ps -a --format ' }).Count | Should -Be 0
        }
    }

    Context "I-A: a swap container's running state is read from stdout only" {
        It "a RUNNING swap whose inspect prints a stderr line <Where> is still refused as running" -ForEach @(
            @{ Where = 'first' },
            @{ Where = 'last' }
        ) {
            $r = Invoke-FakeRestore -DataFiles 3 -LeftoverAnswer 'y' -Fake @{ FAKE_SWAP_CONTAINER = 'running'; FAKE_INSPECT_STDERR = $Where }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: An earlier restore is still replacing your DAAF data inside Docker*"
            $r.Output | Should -BeLike "*(Docker container 'daaf_daaf-data-restore-swap' is running).*"
            $r.Output | Should -Not -BeLike "*Remove it and continue?*"
            (Get-CallIndex $r.Calls '^(volume (create|rm)|rm -f|create) ') | Should -Be -1
            Assert-LiveUntouched -Calls $r.Calls
        }

        It "a STOPPED swap whose inspect prints a stderr line <Where> is a stopped leftover, not running" -ForEach @(
            @{ Where = 'first' },
            @{ Where = 'last' }
        ) {
            $r = Invoke-FakeRestore -DataFiles 3 -LeftoverAnswer 'n' -Fake @{ FAKE_SWAP_CONTAINER = 'stopped'; FAKE_INSPECT_STDERR = $Where }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*- Docker container 'daaf_daaf-data-restore-swap' (stopped)*"
            $r.Output | Should -BeLike "*Remove it and continue? (y/n)*"
            $r.Output | Should -Not -BeLike "*is still replacing your DAAF data*"
        }
    }

    Context "S3: an inspect error that is not 'no such ...' falls back to the exact-name lists" {
        It "<Name>" -ForEach @(
            @{ Name = 'volume: odd error, list says absent -> proceeds'; Fake = @{ FAKE_INSPECT_ODD = 'volume' }; Seed = @(); Answer = ''; Exit = 0
               Like = @('*  Restore complete!*'); NotLike = @('*Remove it and continue?*', '*Could not check for a temporary copy*'); List = '^volume ls -q$' },
            @{ Name = 'volume: odd error, list says listed -> leftover prompt'; Fake = @{ FAKE_INSPECT_ODD = 'volume' }; Seed = @('daaf_daaf-data-restore-tmp'); Answer = 'n'; Exit = 0
               Like = @("*- Docker volume 'daaf_daaf-data-restore-tmp'*", '*Remove it and continue? (y/n)*'); NotLike = @('*Could not check for a temporary copy*'); List = '^volume ls -q$' },
            @{ Name = 'volume: odd error, list fails -> refuses'; Fake = @{ FAKE_INSPECT_ODD = 'volume'; FAKE_LIST_FAIL = '1' }; Seed = @(); Answer = 'y'; Exit = 1
               Like = @('*ERROR: Could not check for a temporary copy left by an earlier restore (docker*', '*       volume inspect failed: Error response from daemon: fake unexpected failure).*'); NotLike = @('*Remove it and continue?*'); List = '^volume ls -q$' },
            @{ Name = 'container: odd error, lists say absent -> proceeds'; Fake = @{ FAKE_INSPECT_ODD = 'container' }; Seed = @(); Answer = ''; Exit = 0
               Like = @('*  Restore complete!*'); NotLike = @('*Remove it and continue?*', '*Could not check for a temporary copy*'); List = '^ps -a --format \{\{\.Names\}\}$' },
            @{ Name = 'container: odd error, listed but not running -> stopped leftover'; Fake = @{ FAKE_INSPECT_ODD = 'container'; FAKE_SWAP_CONTAINER = 'stopped' }; Seed = @(); Answer = 'n'; Exit = 0
               Like = @("*- Docker container 'daaf_daaf-data-restore-swap' (stopped)*", '*Remove it and continue? (y/n)*'); NotLike = @('*is still replacing your DAAF data*'); List = '^ps --format \{\{\.Names\}\}$' },
            @{ Name = 'container: odd error, listed as running -> refused as running'; Fake = @{ FAKE_INSPECT_ODD = 'container'; FAKE_SWAP_CONTAINER = 'running' }; Seed = @(); Answer = 'y'; Exit = 1
               Like = @('*ERROR: An earlier restore is still replacing your DAAF data inside Docker*'); NotLike = @('*Remove it and continue?*'); List = '^ps --format \{\{\.Names\}\}$' },
            @{ Name = 'container: odd error, list fails -> refuses'; Fake = @{ FAKE_INSPECT_ODD = 'container'; FAKE_LIST_FAIL = '1' }; Seed = @(); Answer = 'y'; Exit = 1
               Like = @('*       container inspect failed: Error response from daemon: fake unexpected failure).*'); NotLike = @('*Remove it and continue?*'); List = '^ps -a --format \{\{\.Names\}\}$' }
        ) {
            $r = Invoke-FakeRestore -DataFiles 3 -SeedVolumes $Seed -LeftoverAnswer $Answer -Fake $Fake
            $r.ExitCode | Should -Be $Exit
            foreach ($p in $Like) { $r.Output | Should -BeLike $p }
            foreach ($p in $NotLike) { $r.Output | Should -Not -BeLike $p }
            (Get-CallIndex $r.Calls $List) | Should -BeGreaterThan -1
            # The fallback never uses an unanchored `--filter name=` list.
            (Get-CallIndex $r.Calls '--filter name=') | Should -Be -1
            if ($Exit -ne 0) {
                @($r.Calls | Where-Object { $_ -match '^(volume create|volume rm|create|cp|rm) ' }).Count | Should -Be 0
                Assert-LiveUntouched -Calls $r.Calls
            }
        }
    }

    Context "S2 and the marker-written flag: a refusal after the marker write" {
        It "a data temp that changed after the marker write: this run's Claude temp loses its marker (identity-checked); nothing removed" {
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude -Fake @{ FAKE_IDENTITY = 'vanished_after_marker' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*(volume 'daaf_daaf-data-restore-tmp') was changed by*"
            $r.Output | Should -BeLike "*It was not used, and nothing was removed.*"
            $c = $r.Calls
            $lastMark = -1
            for ($i = 0; $i -lt $c.Count; $i++) { if ($c[$i] -match 'touch /dest/\.daaf-restore-swap-started$') { $lastMark = $i } }
            $claudeId = -1
            for ($i = 0; $i -lt $c.Count; $i++) { if ($c[$i] -ceq 'volume inspect --format {{.Labels}} daaf_daaf-claude-config-restore-tmp') { $claudeId = $i } }
            $unmark = Get-CallIndex $c '-v daaf_daaf-claude-config-restore-tmp:/dest busybox rm -f /dest/\.daaf-restore-swap-started$'
            $lastMark | Should -BeGreaterThan -1
            $claudeId | Should -BeGreaterThan $lastMark
            $unmark | Should -BeGreaterThan $claudeId
            (Get-CallIndex $c '^volume rm ') | Should -Be -1
            (Get-CallIndex $c '^ps -aq ') | Should -Be -1
            (Get-CallIndex $c '--sig-proxy=false') | Should -Be -1
            $r.Volumes | Should -Contain 'daaf_daaf-claude-config-restore-tmp'
            $r.Markers | Should -Not -Contain 'daaf_daaf-claude-config-restore-tmp'
            Assert-LiveUntouched -Calls $c
        }

        It "... and when the Claude temp is no longer this run's either, its marker is left alone" {
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude -Fake @{ FAKE_IDENTITY = 'vanished_after_marker'; FAKE_CLAUDE_IDENTITY = 'vanished_after_marker' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*It was not used, and nothing was removed.*"
            (Get-CallIndex $r.Calls 'busybox rm -f /dest/\.daaf-restore-swap-started$') | Should -Be -1
            (Get-CallIndex $r.Calls '^volume rm ') | Should -Be -1
        }

        It "a marker write that fails for the Claude temp: the data temp (already marked) is unmarked before its removal" {
            # $MarkersWritten: once any marker may exist, the ordinary pre-swap cleanup
            # deletes it before `volume rm`, so a temp that then cannot be removed is not
            # later reported as a restore that had started replacing the data.
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude -Fake @{ FAKE_CLAUDE_MARK_EXIT = '1'; FAKE_VOLUME_RM_EXIT = '1' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: Could not prepare the temporary copy for the final step.*"
            $r.Output | Should -BeLike "*Your DAAF data has not been changed.*"
            $unmark = Get-CallIndex $r.Calls '-v daaf_daaf-data-restore-tmp:/dest busybox rm -f /dest/\.daaf-restore-swap-started$'
            $rm = Get-CallIndex $r.Calls '^volume rm daaf_daaf-data-restore-tmp$'
            $unmark | Should -BeGreaterThan -1
            $rm | Should -BeGreaterThan $unmark
            $r.Volumes | Should -Contain 'daaf_daaf-data-restore-tmp'
            $r.Markers.Count | Should -Be 0
            Assert-LiveUntouched -Calls $r.Calls
        }
    }

    Context "S5: a Claude Code state failure after the data swap was replaced and checked" {
        It "Claude <Name>: says plainly that the project files were restored and only the login/history were not" -ForEach @(
            @{ Name = 'swap fails'; Fake = @{ FAKE_CLAUDE_SWAP_EXIT = '7' }; Expect = '*ERROR: Replacing the Claude Code state (login and session history) did not*'; Kept = 'daaf_daaf-data-restore-tmp daaf_daaf-claude-config-restore-tmp' },
            @{ Name = 'comparison does not match'; Fake = @{ FAKE_CLAUDE_SWAP_VERIFY = 'MISMATCH' }; Expect = '*ERROR: After replacing the Claude Code state, it could not be confirmed to match*'; Kept = 'daaf_daaf-data-restore-tmp daaf_daaf-claude-config-restore-tmp' },
            @{ Name = 'temp changed by something else'; Fake = @{ FAKE_CLAUDE_IDENTITY = 'vanished_after_marker' }; Expect = "*ERROR: The temporary copy of the Claude Code state (volume 'daaf_daaf-claude-config-restore-tmp')*"; Kept = 'daaf_daaf-data-restore-tmp' }
        ) {
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude -Fake $Fake
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike $Expect
            $r.Output | Should -BeLike "*       Your project files (DAAF data) were restored and checked. Only the Claude Code*"
            $r.Output | Should -BeLike "*       login and session history were not restored.*"
            $r.Output | Should -BeLike "*kept in Docker (volume(s): $Kept), and your backup*"
            $r.Output | Should -BeLike "*It will offer to remove the leftover copy (answer y) and then redo the restore.*"
            $r.Output | Should -Not -BeLike "*Your DAAF data may now be incomplete*"
            $r.Output | Should -Not -BeLike "*Your data volume was already replaced*"
            $r.Output | Should -Not -BeLike "*After replacing your DAAF data*"
            (Get-CallIndex $r.Calls '^volume rm ') | Should -Be -1
        }
    }

    # Review round 3 (S-a): once the Claude swap container ran (any exit but its own
    # refusal, 3, or a comparison that failed), the old login may be erased too.
    Context "S-a: the Claude failure text says the old login may be gone only when the Claude swap ran" {
        BeforeAll {
            $script:RanBlock = @(
                '       Your project files (DAAF data) were restored and checked. Only the Claude Code',
                '       login and session history were not restored.',
                '       Your previous Claude Code login may also be gone now; running the restore again',
                "       puts the backup's login and history back.",
                '       The checked copy of the backup is',
                '       kept in Docker (volume(s): daaf_daaf-data-restore-tmp daaf_daaf-claude-config-restore-tmp), and your backup')
            $script:OldLine = '       login and session history were not restored. The checked copy of the backup is'
        }

        It "Claude <Name>: the 'old login may be gone' lines are <Shown>" -ForEach @(
            @{ Name = 'swap exit 7'; Fake = @{ FAKE_CLAUDE_SWAP_EXIT = '7' }; Ran = $true; Shown = 'shown' },
            @{ Name = 'swap exit 125'; Fake = @{ FAKE_CLAUDE_SWAP_EXIT = '125' }; Ran = $true; Shown = 'shown' },
            @{ Name = 'comparison mismatch'; Fake = @{ FAKE_CLAUDE_SWAP_VERIFY = 'MISMATCH' }; Ran = $true; Shown = 'shown' },
            @{ Name = 'comparison unreadable'; Fake = @{ FAKE_CLAUDE_SWAP_VERIFY = 'fail' }; Ran = $true; Shown = 'shown' },
            @{ Name = 'swap refused (exit 3)'; Fake = @{ FAKE_CLAUDE_SWAP_EXIT = '3' }; Ran = $false; Shown = 'not shown' },
            @{ Name = 'temp changed by something else (swap never run)'; Fake = @{ FAKE_CLAUDE_IDENTITY = 'vanished_after_marker' }; Ran = $false; Shown = 'not shown' }
        ) {
            $r = Invoke-FakeRestore -DataFiles 3 -WithClaude -Fake $Fake
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*       Your project files (DAAF data) were restored and checked. Only the Claude Code*"
            if ($Ran) {
                $r.Output | Should -Match ((@($RanBlock | ForEach-Object { [regex]::Escape($_) })) -join '\r?\n')
                $r.Output | Should -Not -BeLike "*$OldLine*"
            } else {
                $r.Output | Should -BeLike "*$OldLine*"
                $r.Output | Should -Not -BeLike "*Your previous Claude Code login may also be gone now*"
                $r.Output | Should -Not -BeLike "*puts the backup's login and history back.*"
            }
            (Get-CallIndex $r.Calls '^volume rm ') | Should -Be -1
        }
    }

    Context "the initial running-container check: names from stdout only; a failing docker ps refuses" {
        It "a stray stderr line from 'docker ps' is not a running container (no stop prompt)" {
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_INITIAL_PS_STDERR = '1' }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -Not -BeLike "*The DAAF container is currently running*"
            $r.Output | Should -BeLike "*  Restore complete!*"
        }

        It "a running container is listed by its name only, never the stderr line" {
            # The stop prompt reads "1" (not y): the restore is cancelled, exit 0.
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_INITIAL_PS_STDERR = '1'; FAKE_RUNNING_AT_START = 'daaf-docker-1' }
            $r.ExitCode | Should -Be 0
            $r.Output | Should -BeLike "*The DAAF container is currently running:*"
            $r.Output | Should -BeLike "*  - daaf-docker-1*"
            $r.Output | Should -Not -BeLike "*fake docker config notice*"
            $r.Output | Should -BeLike "*Restore cancelled. Stop the container manually and try again:*"
        }

        It "a docker ps that FAILS at startup refuses (could not check), exit 1, before anything is created" {
            # Until 2026-10-02 the exit code was not read: a failing check meant "nothing
            # is running" and the restore went on.
            $r = Invoke-FakeRestore -DataFiles 3 -Fake @{ FAKE_PS_AT_START_EXIT = '125' }
            $r.ExitCode | Should -Be 1
            $r.Output | Should -BeLike "*ERROR: Could not check whether DAAF is running (docker ps failed, exit 125),*"
            $r.Output | Should -BeLike "*       so the restore cannot start safely. This restore has not changed anything.*"
            $r.Output | Should -BeLike "*       Make sure Docker Desktop is running, then run the restore again.*"
            $r.Output | Should -Not -BeLike "*error during connect*"
            $r.Output | Should -Not -BeLike "*The DAAF container is currently running*"
            $r.Output | Should -Not -BeLike "*Available backups*"
            (Get-CallIndex $r.Calls '^volume create ') | Should -Be -1
            (Get-CallIndex $r.Calls '^create ') | Should -Be -1
            (Get-CallIndex $r.Calls '^run ') | Should -Be -1
            Assert-LiveUntouched -Calls $r.Calls
            $r.Volumes | Should -Not -Contain 'daaf_daaf-data-restore-tmp'
        }
    }
}

# ============================================================================
# The real swap program under the local sh (non-Windows): the INT trap is what keeps a
# forwarded Ctrl+C from stopping the swap after `rm` and before `cp` (live EMPTY).
# ============================================================================

Describe "restore_from_backup.ps1 swap program under a local sh" -Skip:(($PSVersionTable.PSVersion.Major -lt 6) -or $IsWindows) {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $env:DAAF_TEST_MODE = "1"
        . "$RepoRoot/scripts/host/restore_from_backup.ps1"
        # Relocate /src and /dest into a fixture root (paths here hold no spaces), and
        # inject a SIGINT to the shell itself between the clear and the copy.
        # -NoMarker: the source lacks the state marker (an EMPTY volume Docker re-created
        # under a vanished temp name, B1); -NoKill: no injected SIGINT.
        function Invoke-LocalSwap {
            param([string]$Program, [switch]$NoMarker, [switch]$NoKill)
            $root = Join-Path $TestDrive ('swap-' + [guid]::NewGuid().ToString('N'))
            $src = Join-Path $root 'src'
            $dest = Join-Path $root 'dest'
            $null = New-Item -ItemType Directory -Path (Join-Path $src 'sub')
            $null = New-Item -ItemType Directory -Path (Join-Path $dest 'old')
            [IO.File]::WriteAllText((Join-Path $src 'top.txt'), 'a')
            [IO.File]::WriteAllText((Join-Path $src 'sub/run.sh'), '#!/bin/sh')
            if (-not $NoMarker) { [IO.File]::WriteAllText((Join-Path $src '.daaf-restore-swap-started'), '') }
            [IO.File]::WriteAllText((Join-Path $dest 'old/keep'), 'old')
            $prog = $Program.Replace(' /src', " $src").Replace(' /dest', " $dest")
            if (-not $NoKill) { $prog = $prog.Replace('&& cp -a', '&& kill -INT $$ && cp -a') }
            $null = & sh -c $prog 2>&1
            [pscustomobject]@{ Exit = $LASTEXITCODE; Dest = @(Get-ChildItem -LiteralPath $dest -Force -Recurse -Name | Sort-Object) }
        }
    }

    AfterAll {
        Remove-Item Env:DAAF_TEST_MODE -ErrorAction SilentlyContinue
    }

    It "a SIGINT between the clear and the copy does NOT stop the swap (the copy completes)" {
        $r = Invoke-LocalSwap -Program $SwapProgram
        $r.Exit | Should -Be 0
        $r.Dest | Should -Contain 'top.txt'
        $r.Dest | Should -Contain 'sub'
        $r.Dest | Should -Not -Contain 'old'
        # The state marker is deleted from the live copy as the last step.
        $r.Dest | Should -Not -Contain '.daaf-restore-swap-started'
    }

    It "control: the same program WITHOUT the trap is stopped by that SIGINT (live left empty)" {
        # Proves the injected SIGINT reaches the shell, so the test above is meaningful.
        $r = Invoke-LocalSwap -Program ($SwapProgram -replace '^trap : INT TERM HUP; ', '')
        $r.Exit | Should -Not -Be 0
        $r.Dest.Count | Should -Be 0
    }

    It "B1: a source WITHOUT this run's state marker erases nothing (nonzero exit, live kept)" {
        # A temp volume that vanished and was re-created EMPTY by Docker has no marker:
        # the swap must refuse before its rm -rf -- with exit 3 exactly (review round 2,
        # S1): the host maps 3 to "NOTHING was replaced", any other code to "may be
        # incomplete".
        $r = Invoke-LocalSwap -Program $SwapProgram -NoMarker -NoKill
        $r.Exit | Should -Be 3
        $r.Dest | Should -Contain 'old'
        $r.Dest | Should -Not -Contain 'top.txt'
    }

    It "the swap verify program reports MATCH with ENTRIES 0:0 for two EMPTY trees (why the host requires n > 0)" {
        $root = Join-Path $TestDrive ('verify-' + [guid]::NewGuid().ToString('N'))
        $src = Join-Path $root 'src'
        $dest = Join-Path $root 'dest'
        $ctmp = Join-Path $root 'ctmp'
        foreach ($d in @($src, $dest, $ctmp)) { $null = New-Item -ItemType Directory -Path $d }
        # Relocate the program's /src, /dest and container /tmp into the fixture.
        $prog = $SwapVerifyProgram.Replace('/tmp/', "$ctmp/").Replace('cd /$t', "cd $root/`$t")
        $out = @(& sh -c $prog 2>&1)
        $out | Should -Contain 'SWAP_VERIFY=MATCH'
        $out | Should -Contain 'SWAP_VERIFY_ENTRIES=0:0'
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

    Context "Live-volume replacement fails" {
        # Was "Volume clear fails": the old Step 1 cleared the live volume first, and its
        # failure printed "Failed to clear Docker volume" / "inconsistent state". With
        # copy-then-swap the live volume is cleared only inside the swap; its equivalent
        # failure keeps the checked temp copy and prints recovery steps (exit 1).
        # Behaviour is covered end-to-end in "copy-then-swap (fake docker)" below.
        It "exits with error and keeps the checked copy when the swap fails (exit 1)" {
            $Content | Should -Match ([regex]::Escape('ERROR: Replacing your DAAF data did not complete (exit $swapExit).'))
            $Content | Should -Match 'Your DAAF data may now be incomplete\. The checked copy of the backup is'
            $Content | Should -Match ([regex]::Escape('kept in Docker (volume(s): $(Get-DaafRestoreKeptTempList))'))
            $Content | Should -Not -Match 'Failed to clear Docker volume'
            $Content | Should -Not -Match 'inconsistent state'
        }
    }

    Context "Restored count differs from the checked temp copy (including zero)" {
        # Was "Zero files after restore" ("0 files found ... reinstalling DAAF") and "File
        # count mismatch after restore" (a 1% WARNING). Review round 1 (I4, B1 fix 4): any
        # difference is an after-swap failure that keeps the temp copy. Behaviour: the
        # "exact post-swap count" cases in the end-to-end block.
        It "routes a differing post-swap count through the after-swap failure text (exit 1)" {
            $Content | Should -Match ([regex]::Escape('} elseif ($RestoredCount -ne $TempCount) {'))
            $Content | Should -Match ([regex]::Escape('"       copy held $TempCount.")'))
            $Content | Should -Not -Match '\$RestoredCount -eq 0'
            $Content | Should -Not -Match 'restore may be incomplete'
        }
    }

    Context "No backup folders found" {
        It "exits with error when no backups exist (exit 1)" {
            $Content | Should -Match 'No backup folders found'
            $Content | Should -Match 'daaf-docker folder'
        }
    }
}
