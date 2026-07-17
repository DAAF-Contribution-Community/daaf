# ============================================================================
# Pester tests for test_migration.ps1 -- DAAF Migration Test harness (Windows)
# ============================================================================
# Mirrors the .sh twin's bats suite (tests/bash/test_migration.bats): exercises
# the pure tm_* helper functions via the DAAF_TEST_MODE source seam, with no
# docker and no network. The source guard in test_migration.ps1 returns before any
# harness body executes, so dot-sourcing only defines the tm_* functions.

Describe "test_migration.ps1 syntax" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
    }

    It "parses without errors" {
        $errors = Test-ScriptSyntax -Path "$RepoRoot/scripts/host/test_migration.ps1"
        $errors | Should -BeNullOrEmpty
    }
}

Describe "test_migration.ps1 pure helper functions (tm_*)" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $env:DAAF_TEST_MODE = "1"
        . "$RepoRoot/scripts/host/test_migration.ps1"
    }

    AfterAll {
        Remove-Item Env:DAAF_TEST_MODE -ErrorAction SilentlyContinue
    }

    Context "tm_detect_era" {
        It "maps v1.0.0 to era 1 (clone)"     { tm_detect_era "v1.0.0"   | Should -Be "1" }
        It "maps v2.0.0 to era 2 (ZIP)"       { tm_detect_era "v2.0.0"   | Should -Be "2" }
        It "maps v2.0.1 to era 2 (ZIP)"       { tm_detect_era "v2.0.1"   | Should -Be "2" }
        It "maps v2.1.0 to era 3 (install)"   { tm_detect_era "v2.1.0"   | Should -Be "3" }
        It "maps a branch name to era 3"      { tm_detect_era "daaf_dev" | Should -Be "3" }
    }

    Context "tm_version_ge_floor" {
        It "returns 0 for the floor v2.1.0"           { tm_version_ge_floor "v2.1.0"  | Should -Be 0 }
        It "returns 0 for v2.10.0 (numeric, not lexical)" { tm_version_ge_floor "v2.10.0" | Should -Be 0 }
        It "returns 1 for a tag below the floor"      { tm_version_ge_floor "v2.0.1"  | Should -Be 1 }
        It "returns 2 for a non-vX.Y.Z tag"           { tm_version_ge_floor "daaf_dev" | Should -Be 2 }
    }

    Context "tm_matrix_vectors" {
        It "defaults to fresh + one vector per era" {
            (tm_matrix_vectors) | Should -Be @('fresh', 'v1.0.0', 'v2.0.1', 'v2.1.0')
        }
        It "honors DAAF_TEST_MATRIX_VERSIONS override" {
            $saved = $env:DAAF_TEST_MATRIX_VERSIONS
            try {
                $env:DAAF_TEST_MATRIX_VERSIONS = 'a b'
                (tm_matrix_vectors) | Should -Be @('a', 'b')
            } finally {
                if ($null -ne $saved) { $env:DAAF_TEST_MATRIX_VERSIONS = $saved }
                else { Remove-Item Env:DAAF_TEST_MATRIX_VERSIONS -ErrorAction SilentlyContinue }
            }
        }
    }

    Context "tm_emit_summary + tm_parse_summary_field round-trip" {
        It "emits the byte-identical grammar and parses each field back" {
            $line = tm_emit_summary "v2.0.1" "PASS" 10 0 3
            $line | Should -Be "TEST_MIGRATION_SUMMARY vector=v2.0.1 status=PASS pass=10 fail=0 skip=3"
            (tm_parse_summary_field $line "vector") | Should -Be "v2.0.1"
            (tm_parse_summary_field $line "status") | Should -Be "PASS"
            (tm_parse_summary_field $line "pass")   | Should -Be "10"
            (tm_parse_summary_field $line "fail")   | Should -Be "0"
            (tm_parse_summary_field $line "skip")   | Should -Be "3"
        }
    }

    Context "tm_classify_status" {
        It "classifies not-reached as INFRA"        { tm_classify_status "false" 0 | Should -Be "INFRA" }
        It "classifies reached-with-failures as FAIL" { tm_classify_status "true" 2 | Should -Be "FAIL" }
        It "classifies reached-clean as PASS"        { tm_classify_status "true" 0 | Should -Be "PASS" }
    }

    Context "tm_matrix_verdict" {
        # Reconciles the parsed summary status against the child's actual exit code.
        It "PASS with rc 0 passes the vector (0)"        { tm_matrix_verdict "PASS" 0 | Should -Be 0 }
        It "PASS with a nonzero rc fails the vector (1)" { tm_matrix_verdict "PASS" 1 | Should -Be 1 }
        It "FAIL status fails even with rc 0 (1)"        { tm_matrix_verdict "FAIL" 0 | Should -Be 1 }
        It "INFRA status fails (1)"                       { tm_matrix_verdict "INFRA" 0 | Should -Be 1 }
        It "an UNKNOWN(rc=N) placeholder fails (1)"       { tm_matrix_verdict "UNKNOWN(rc=5)" 5 | Should -Be 1 }
    }

    Context "tm_parse_args" {
        It "-All sets RunAll and implies AutoMode" {
            $r = tm_parse_args @('-All')
            $r.RunAll | Should -BeTrue
            $r.AutoMode | Should -BeTrue
        }
        It "--all (bash form) sets RunAll and implies AutoMode" {
            $r = tm_parse_args @('--all')
            $r.RunAll | Should -BeTrue
            $r.AutoMode | Should -BeTrue
        }
        It "-Auto sets AutoMode only" {
            $r = tm_parse_args @('-Auto')
            $r.AutoMode | Should -BeTrue
            $r.RunAll | Should -BeFalse
        }
        It "-SkipMultiInstance sets SkipMultiCli only" {
            $r = tm_parse_args @('-SkipMultiInstance')
            $r.SkipMultiCli | Should -BeTrue
            $r.RunAll | Should -BeFalse
            $r.AutoMode | Should -BeFalse
        }
        It "combined flags fold together" {
            $r = tm_parse_args @('-Auto', '-SkipMultiInstance')
            $r.AutoMode | Should -BeTrue
            $r.SkipMultiCli | Should -BeTrue
            $r.RunAll | Should -BeFalse
        }
        It "ignores unknown tokens (env-driven child invocation)" {
            $empty = tm_parse_args @()
            $empty.RunAll | Should -BeFalse
            $empty.AutoMode | Should -BeFalse
            $empty.SkipMultiCli | Should -BeFalse
            $r = tm_parse_args @('--nonsense', 'positional')
            $r.RunAll | Should -BeFalse
            $r.AutoMode | Should -BeFalse
            $r.SkipMultiCli | Should -BeFalse
        }
    }

    Context "Test-ConflictAutoResolvable (round-5 conflict-journey eligibility)" {
        # Eligible ONLY when a merge is in progress (MergeHead non-empty) AND the
        # unmerged set is EXACTLY CLAUDE.md. Everything else fails loudly.
        It "MergeHead + exactly CLAUDE.md is eligible" {
            Test-ConflictAutoResolvable "abc123def456" "CLAUDE.md" | Should -BeTrue
        }
        It "tolerates trailing CR/whitespace on both inputs" {
            Test-ConflictAutoResolvable "abc123`r" "  CLAUDE.md `r" | Should -BeTrue
        }
        It "empty MergeHead is not eligible" {
            Test-ConflictAutoResolvable "" "CLAUDE.md" | Should -BeFalse
            Test-ConflictAutoResolvable "  `r" "CLAUDE.md" | Should -BeFalse
        }
        It "a multi-file unmerged set is not eligible" {
            Test-ConflictAutoResolvable "abc123" "CLAUDE.md`nDockerfile" | Should -BeFalse
        }
        It "a wrong single file (Dockerfile only) is not eligible" {
            Test-ConflictAutoResolvable "abc123" "Dockerfile" | Should -BeFalse
        }
        It "MergeHead present but empty unmerged set is not eligible" {
            Test-ConflictAutoResolvable "abc123" "" | Should -BeFalse
        }
    }
}

# Content pins for fixes whose absence caused real field failures (field run 4,
# 2026-07-17). The docker-driven phases cannot execute under Pester, so these
# pin the load-bearing source lines: reverting a fix breaks the pin.
Describe "test_migration.ps1 field-run 4 regression pins" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:HarnessText = Get-Content -Raw "$RepoRoot/scripts/host/test_migration.ps1"
    }

    It "defines the summary contract (function + trap) ABOVE the matrix driver" {
        # PowerShell traps are scope-wide: the trap fires for driver-branch
        # errors too, so Write-SummaryOnce must already be defined when the
        # driver runs (field run 4: CommandNotFoundException in the trap killed
        # the whole matrix mid-loop).
        $idxFunc = $script:HarnessText.IndexOf('function Write-SummaryOnce')
        $idxTrap = $script:HarnessText.IndexOf('trap { Write-SummaryOnce; break }')
        $idxDriver = $script:HarnessText.IndexOf('--- Matrix driver')
        $idxFunc | Should -BeGreaterThan 0
        $idxTrap | Should -BeGreaterThan 0
        $idxDriver | Should -BeGreaterThan 0
        $idxFunc | Should -BeLessThan $idxDriver
        $idxTrap | Should -BeLessThan $idxDriver
    }

    It "Write-SummaryOnce never emits from the matrix driver (RunAll guard)" {
        # The grammar is one summary line per CHILD vector; the driver reports
        # via scoreboard + exit code only.
        $script:HarnessText | Should -Match '(?s)function Write-SummaryOnce.{0,2000}?if \(\$script:RunAll\) \{ return \}'
    }

    It "matrix child pipeline stringifies child stderr under scoped EAP" {
        # PS 5.1 wraps child stderr as ErrorRecords under 2>&1; with EAP=Stop
        # the first record (git clone progress) terminates the driver loop.
        $script:HarnessText | Should -Match ([regex]::Escape('2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath $logf'))
    }

    It "wraps era-install bare native calls in Invoke-NativeLogged" {
        $script:HarnessText | Should -Match ([regex]::Escape('Invoke-NativeLogged { git clone'))
        $script:HarnessText | Should -Match ([regex]::Escape('Invoke-NativeLogged { docker compose up -d --build }'))
    }

    It "drives update_daaf.ps1 branch-faithfully (DAAF_BRANCH on both driven runs)" {
        # Without DAAF_BRANCH the updater auto-detects main and merges GitHub
        # origin/main instead of the branch under test.
        $pair = [regex]::Escape('$env:DAAF_BRANCH = $MigrationBranch') + '\s+' + [regex]::Escape('$env:DAAF_NESTED = "1"')
        ([regex]::Matches($script:HarnessText, $pair)).Count | Should -BeGreaterOrEqual 2
    }

    It "Era-3 tag normalization completes refspec, origin/main, and tracking" {
        $script:HarnessText | Should -Match ([regex]::Escape('git -C /daaf remote set-branches origin main'))
        $script:HarnessText | Should -Match ([regex]::Escape('git -C /daaf fetch --depth 1 origin main'))
        $script:HarnessText | Should -Match ([regex]::Escape('git -C /daaf branch --set-upstream-to=origin/main main'))
    }

    It "Class D comparison exempts the sanctioned DAAF_BRANCH persist" {
        # The driven update's env-origin DAAF_BRANCH is intentionally persisted
        # into environment_settings.txt by update_daaf; both Class D hash sites
        # must filter that line or the sanctioned write reads as fixture loss.
        $script:HarnessText | Should -Match ([regex]::Escape('function Get-ClassDHash'))
        $script:HarnessText | Should -Match ([regex]::Escape("Where-Object { `$_ -notmatch '^DAAF_BRANCH=' }"))
        ([regex]::Matches($script:HarnessText, [regex]::Escape('Get-ClassDHash $ClassDPath'))).Count | Should -Be 2
    }

    It "Era-1 verify failure surfaces raw git stderr + ownership probes" {
        $script:HarnessText | Should -Match ([regex]::Escape('Raw git probe output'))
        $script:HarnessText | Should -Match ([regex]::Escape('ls -ldn /daaf /daaf/.git'))
    }
}

# Content pins for the round-5 conflict -> resolve -> resume journey (2026-07-17):
# a nonzero first driven update whose unmerged set is exactly CLAUDE.md is not a
# FAIL -- the harness simulates the guided resolution and re-drives the resumable
# updater, scoring the whole journey. Strings are byte-identical to the .sh twin.
Describe "test_migration.ps1 field-run 5 conflict-journey pins" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:HarnessText = Get-Content -Raw "$RepoRoot/scripts/host/test_migration.ps1"
    }

    It "captures the mid-merge state (capture-then-test, no live grep)" {
        $script:HarnessText | Should -Match ([regex]::Escape('Invoke-ContainerGit rev-parse -q --verify MERGE_HEAD'))
        $script:HarnessText | Should -Match ([regex]::Escape('Invoke-ContainerGit diff --name-only --diff-filter=U'))
    }

    It "gates the recovery on the pure Test-ConflictAutoResolvable helper" {
        $script:HarnessText | Should -Match ([regex]::Escape('Test-ConflictAutoResolvable $MergeHead $Unmerged'))
    }

    It "resolves via checkout --theirs + re-append + the frozen commit message" {
        $script:HarnessText | Should -Match ([regex]::Escape('Invoke-ContainerGit checkout --theirs -- CLAUDE.md'))
        $script:HarnessText | Should -Match ([regex]::Escape('Resolved merge conflicts from DAAF update (harness-simulated guided resolution)'))
    }

    It "scores the journey with its own check name (parity with the .sh twin)" {
        ([regex]::Matches($script:HarnessText, [regex]::Escape('Update conflict journey completed (conflict -> resolved -> resumed update exit'))).Count | Should -Be 2
    }

    It "appends the resume run's capture to UpdateOut (union for the self-update grep)" {
        $script:HarnessText | Should -Match ([regex]::Escape('$ResumeUpdateOut = "$($script:UpdateOut).resume"'))
    }
}

# Content pins for the field-run 5 finding 3b/3c fixes (2026-07-17). 3b: a guarded
# git safe.directory exemption window spanning the harness's own pre-migrate
# old-container git ops (phase 3 verify + phase 4/5 fixture plants), opened before
# the first such op and closed before migrate runs (only if the harness added it),
# so migrate's own section-4b fix is still exercised end-to-end on the root-owned
# Era-1 (v1.0.0) payload. 3c: the Era-1 raw-git diagnostics now capture native
# stderr under PS 5.1 (empty on Windows before the fix). Docker-driven, so these
# pin the load-bearing source ordering/guards. Notes are byte-identical to the .sh.
Describe "test_migration.ps1 field-run 5 finding 3b/3c pins" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:HarnessText = Get-Content -Raw "$RepoRoot/scripts/host/test_migration.ps1"
    }

    It "opens the safe.directory window before the first phase-3 era-verify git op, and closes it before migrate" {
        $idxVerifyHeader = $script:HarnessText.IndexOf('[3/7] Verify Era')
        $idxAdd = $script:HarnessText.IndexOf('Invoke-ContainerExec git config --global --add safe.directory /daaf')
        # First Invoke-ContainerGit call site AFTER the phase-3 header (the OPEN
        # block uses Invoke-ContainerExec, so it never matches this).
        $idxFirstGit = $script:HarnessText.IndexOf('Invoke-ContainerGit ', $idxVerifyHeader)
        $idxUnset = $script:HarnessText.IndexOf('Invoke-ContainerExec git config --global --unset-all safe.directory')
        $idxMigrate = $script:HarnessText.IndexOf('Invoke-HardenedScriptAuto -Path (Join-Path $HostDir "migrate_daaf.ps1")')
        $idxVerifyHeader | Should -BeGreaterThan 0
        $idxAdd | Should -BeGreaterThan $idxVerifyHeader
        $idxAdd | Should -BeLessThan $idxFirstGit
        $idxUnset | Should -BeGreaterThan 0
        $idxAdd | Should -BeLessThan $idxUnset
        $idxUnset | Should -BeLessThan $idxMigrate
    }

    It "gates the safe.directory window close on the harness having added it, with a targeted removal" {
        $script:HarnessText | Should -Match ([regex]::Escape('if ($script:HarnessAddedSafeDir) {'))
        $script:HarnessText | Should -Match ([regex]::Escape("Invoke-ContainerExec git config --global --unset-all safe.directory '^/daaf`$'"))
    }

    It "guards the safe.directory window open (capture-then-test) with byte-identical notes" {
        $script:HarnessText | Should -Match ([regex]::Escape('@(Invoke-ContainerExec git config --global --get-all safe.directory)'))
        $script:HarnessText | Should -Match ([regex]::Escape("-contains '/daaf'"))
        $script:HarnessText | Should -Match ([regex]::Escape('Git safe.directory exemption window OPENED (harness added /daaf)'))
        $script:HarnessText | Should -Match ([regex]::Escape('Git safe.directory exemption window CLOSED (harness removed its /daaf entry)'))
    }

    It "captures Era-1 raw git stderr under scoped EAP=Continue + per-object stringify (PS 5.1 fix)" {
        # The prior SilentlyContinue + Out-String dropped native stderr ErrorRecords
        # on PS 5.1, so $gitDiag came back EMPTY on Windows where the .sh twin printed
        # git's dubious-ownership fatal. Continue + 2>&1 + ForEach-Object "$_" surfaces it.
        $script:HarnessText | Should -Match ([regex]::Escape("git -C /daaf remote get-url origin 2>&1 | ForEach-Object { `"`$_`" }"))
        $script:HarnessText | Should -Match ([regex]::Escape("ls -ldn /daaf /daaf/.git 2>&1 | ForEach-Object { `"`$_`" }"))
    }
}

# ============================================================================
# Field-Run Triage Round 6 (2026-07-17): volume ownership repair window
# ============================================================================
# The documented Era-1 install leaves the volume payload root-owned (busybox
# cp -a preserves the bind mount's presented owner; no daaf-init repair service
# until v2.0.0), so phase 4-5 fixture plants cannot write /daaf as the
# container's uid-1000 user. The harness repairs ownership after the phase-3
# verify (OPEN), restores the captured original owner before migrate (CLOSE) so
# migrate's own section-4c repair is exercised end-to-end, and a universal
# phase-7 check asserts post-migration writability. Notes byte-identical to .sh.
Describe "test_migration.ps1 field-run 6 ownership-window pins" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:HarnessText = Get-Content -Raw "$RepoRoot/scripts/host/test_migration.ps1"
    }

    It "opens the ownership window after the phase-3 verify and before phase-4 fixture plants" {
        $idxVerify = $script:HarnessText.IndexOf('Era 1 state verified')
        $idxOpen = $script:HarnessText.IndexOf('Volume ownership repair window OPENED')
        $idxPhase4 = $script:HarnessText.IndexOf('Simulate committed user work')
        $idxVerify | Should -BeGreaterThan 0
        $idxOpen | Should -BeGreaterThan $idxVerify
        $idxOpen | Should -BeLessThan $idxPhase4
    }

    It "restores the captured original owner (never hardcoded) before migrate, gated on the harness having repaired it" {
        $script:HarnessText | Should -Match ([regex]::Escape('if ($script:HarnessRepairedOwnership) {'))
        $script:HarnessText | Should -Match ([regex]::Escape('chown -R "$($script:OrigOwnerUid):$($script:OrigOwnerGid)" /daaf'))
        $idxClose = $script:HarnessText.IndexOf('Volume ownership repair window CLOSED')
        $idxMigrate = $script:HarnessText.IndexOf('Invoke-HardenedScriptAuto -Path (Join-Path $HostDir "migrate_daaf.ps1")')
        $idxClose | Should -BeGreaterThan 0
        $idxClose | Should -BeLessThan $idxMigrate
    }

    It "gates the window on Era 1, captures the owner under scoped EAP=Continue, with byte-identical notes" {
        $script:HarnessText | Should -Match ([regex]::Escape("busybox stat -c '%u' /daaf"))
        $script:HarnessText | Should -Match ([regex]::Escape('Volume ownership repair window OPENED (harness chowned the payload from'))
        $script:HarnessText | Should -Match ([regex]::Escape('Volume ownership repair window CLOSED (harness restored the payload owner to'))
    }

    It "asserts post-migration writability on every vector with the twin-identical check string" {
        $script:HarnessText | Should -Match ([regex]::Escape('Post-migration container user can write /daaf (ownership repaired)'))
        $script:HarnessText | Should -Match ([regex]::Escape('touch /daaf/.daaf-write-probe && rm -f /daaf/.daaf-write-probe'))
    }
}
