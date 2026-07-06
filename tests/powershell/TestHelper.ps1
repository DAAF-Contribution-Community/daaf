# ============================================================================
# Pester Test Helper -- shared setup for all DAAF PowerShell script tests
# ============================================================================
# Dot-source this from every .Tests.ps1 file in BeforeAll:
#   . "$PSScriptRoot/TestHelper.ps1"
#
# Provides:
#   - $RepoRoot  -- absolute path to the repository root
#   - Common test directory setup/teardown patterns (documented below)
#   - Notes on Docker mock patterns for Pester
# ============================================================================

# Path to the repository root (parent of tests/powershell/)
$script:RepoRoot = (Resolve-Path "$PSScriptRoot/../..").Path

# ============================================================================
# Test Directory Lifecycle
# ============================================================================
# Use these patterns in your Describe/Context blocks:
#
#   BeforeAll {
#       . "$PSScriptRoot/TestHelper.ps1"
#       $script:TestDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-test-$(Get-Random)")
#       Push-Location $script:TestDir
#   }
#
#   AfterAll {
#       Pop-Location
#       Remove-Item -Recurse -Force $script:TestDir -ErrorAction SilentlyContinue
#   }
#
# CWD-leak safety: New-FakeComposeFile writes to $script:TestDir by default (NOT
# the ambient CWD), so a crash between Push-Location and Pop-Location can no
# longer clobber files at the repo root. Prefer passing -Directory $script:TestDir
# explicitly at call sites for full independence from CWD state.

# ============================================================================
# Docker Mock Patterns
# ============================================================================
# Pester cannot mock native commands directly. The pattern is:
#
# 1. Declare a function with the same name:
#      function docker {}
#
# 2. Mock the function:
#      Mock docker { $global:LASTEXITCODE = 0; return "mock output" }
#
# 3. For testing failure:
#      Mock docker { $global:LASTEXITCODE = 1 }
#
# 4. Verify calls:
#      Should -Invoke docker -Times 1
#
# IMPORTANT: The function declaration (step 1) must appear BEFORE the Mock
# call. Place it in BeforeAll or Context-level BeforeAll.

# ============================================================================
# Syntax Validation Helper
# ============================================================================
# Validates that a PowerShell script parses without syntax errors.
# Returns the error collection (empty array means no errors).

function Test-ScriptSyntax {
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    $errors = $null
    $tokens = $null
    [System.Management.Automation.Language.Parser]::ParseFile(
        $Path,
        [ref]$tokens,
        [ref]$errors
    ) | Out-Null
    return $errors
}

# ============================================================================
# Fake docker-compose.yml Creator
# ============================================================================

function New-FakeComposeFile {
    [Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSUseShouldProcessForStateChangingFunctions', '')]
    param(
        # Explicit target directory. Defaults to the caller's $script:TestDir (the
        # per-test temp dir set in BeforeAll) rather than the ambient CWD. Writing
        # to (Get-Location).Path was the root cause of the repo-root leak: a test
        # that crashed between Push-Location and Pop-Location left CWD at the repo
        # root, so the next call clobbered /daaf/docker-compose.yml. Never default
        # to the ambient CWD -- require a real temp target, and fail loudly if the
        # caller has no $script:TestDir to fall back to.
        [string]$Directory = $script:TestDir
    )

    if ([string]::IsNullOrEmpty($Directory)) {
        throw "New-FakeComposeFile: no target directory. Pass -Directory or set \$script:TestDir in BeforeAll (never writes to the ambient CWD)."
    }

    $content = @"
name: daaf
services:
  daaf-docker:
    image: daaf:latest
    volumes:
      - daaf-data:/daaf
      - daaf-claude-config:/home/appuser/.claude
    environment:
      - CLAUDE_CONFIG_DIR=/home/appuser/.claude
volumes:
  daaf-data:
  daaf-claude-config:
"@
    Set-Content -Path (Join-Path $Directory "docker-compose.yml") -Value $content
}
