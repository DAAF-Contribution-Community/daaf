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
