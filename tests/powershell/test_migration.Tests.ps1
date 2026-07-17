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
