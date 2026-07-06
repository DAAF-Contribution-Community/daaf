# Testing Shell Scripts

Testing strategies for Bash and PowerShell scripts in DAAF. Covers BATS for Bash, Pester for PowerShell, CI workflow configuration, Docker mocking strategies, and test taxonomy.

---

## Test Taxonomy

Not all tests are equal. Use the right level for the right purpose:

| Level | Docker Required | Run When | What It Verifies |
|-------|-----------------|----------|------------------|
| **Lint** (ShellCheck + PSScriptAnalyzer) | No | Every push | Syntax, quoting, known bug patterns |
| **Unit** (mocked externals) | No | Every push | Logic, argument parsing, error paths, output formatting |
| **Smoke** (`--help`, `--dry-run`) | No | Every push | Script loads, prints usage, exits cleanly |
| **Integration** (real Docker) | Yes | Manual / nightly | End-to-end behavior with actual containers |

**What to test:**
- Argument parsing and validation
- Error paths (missing files, missing tools, bad input)
- Output formatting (correct messages, correct stream)
- Exit codes (0 for success, correct non-zero for each failure mode)
- Preflight checks (dependency detection)
- Idempotency (safe to run twice)

**What to skip:**
- Actual Docker builds (slow, flaky, need real daemon)
- Network operations (use mocks or recorded responses)
- Full directory tree creation (test the logic, not the filesystem)

---

## BATS (Bash Automated Testing System)

### Setup

Use [bats-core](https://github.com/bats-core/bats-core) (the actively maintained fork) with helper libraries:

```bash
# Add as git submodules
git submodule add https://github.com/bats-core/bats-core.git test/libs/bats
git submodule add https://github.com/bats-core/bats-support.git test/libs/bats-support
git submodule add https://github.com/bats-core/bats-assert.git test/libs/bats-assert
git submodule add https://github.com/bats-core/bats-file.git test/libs/bats-file
```

### File Naming Convention

```
tests/bash/{script_name}.bats
```

Example: tests for `install_daaf.sh` go in `tests/bash/install_daaf.bats`.

### Basic Test Structure

```bash
#!/usr/bin/env bats

# Load helper libraries
load '../libs/bats-support/load'
load '../libs/bats-assert/load'

# --- Setup/Teardown ---

setup() {
    # Create temp directory for test isolation
    TEST_DIR="$(mktemp -d)"
    export TEST_DIR
}

teardown() {
    rm -rf "$TEST_DIR"
}

# --- Tests ---

@test "shows usage when no arguments provided" {
    run bash ./scripts/my_script.sh
    assert_failure
    assert_output --partial "Usage:"
}

@test "exits 0 on valid input" {
    run bash ./scripts/my_script.sh "$TEST_DIR/valid-input.txt"
    assert_success
}

@test "exits 1 when input file does not exist" {
    run bash ./scripts/my_script.sh "/nonexistent/path"
    assert_failure
    assert_output --partial "ERROR:"
}

@test "error messages go to stderr" {
    run bash ./scripts/my_script.sh "/nonexistent/path"
    assert_failure
    # bats captures both stdout and stderr in $output by default
    assert_output --partial "ERROR:"
}
```

### Key BATS Assertions

| Assertion | What It Checks |
|-----------|---------------|
| `assert_success` | Exit code is 0 |
| `assert_failure` | Exit code is non-zero |
| `assert_output "exact text"` | Exact match on combined stdout+stderr |
| `assert_output --partial "text"` | Substring match |
| `assert_line --index 0 "text"` | First line matches |
| `refute_output --partial "text"` | Text is NOT in output |
| `assert_equal "$actual" "$expected"` | String equality |

### Running Tests

```bash
# Run all tests
./test/libs/bats/bin/bats tests/bash/

# Run a specific test file
./test/libs/bats/bin/bats tests/bash/install_daaf.bats

# Run with TAP output (for CI)
./test/libs/bats/bin/bats --tap tests/bash/
```

---

## Docker Mocking (Bash)

Most DAAF scripts call Docker. For unit tests, mock it:

### Strategy 1: Function Override (Simplest)

Override the `docker` command with a function, then export it so subshells see it:

```bash
setup() {
    # Track calls for verification
    DOCKER_CALLS=()
    MOCK_DOCKER_EXIT=0

    docker() {
        DOCKER_CALLS+=("$*")
        return "$MOCK_DOCKER_EXIT"
    }
    export -f docker
}

@test "calls docker compose up" {
    run bash ./scripts/start.sh
    assert_success

    # Verify docker was called with expected arguments
    [[ "${DOCKER_CALLS[0]}" == *"compose up"* ]]
}

@test "handles docker failure" {
    MOCK_DOCKER_EXIT=1

    run bash ./scripts/start.sh
    assert_failure
    assert_output --partial "ERROR"
}
```

### Strategy 2: bats-mock (For Verifying Call Sequences)

When you need to verify the exact sequence and arguments of Docker calls:

```bash
load '../libs/bats-mock/stub'

setup() {
    stub docker \
        "info : echo 'Docker is running'" \
        "compose up -d : echo 'Started'"
}

teardown() {
    unstub docker
}

@test "checks docker info before compose up" {
    run bash ./scripts/start.sh
    assert_success
    # unstub verifies all expected calls were made in order
}
```

### Strategy 3: PATH Manipulation

Create a fake `docker` script in a temp directory and prepend it to PATH:

```bash
setup() {
    MOCK_BIN="$(mktemp -d)"
    cat > "$MOCK_BIN/docker" <<'MOCK'
#!/usr/bin/env bash
echo "mock-docker: $*" >> "${MOCK_LOG:-/dev/null}"
exit "${MOCK_DOCKER_EXIT:-0}"
MOCK
    chmod +x "$MOCK_BIN/docker"
    export PATH="$MOCK_BIN:$PATH"
    export MOCK_LOG="$MOCK_BIN/calls.log"
}

teardown() {
    rm -rf "$MOCK_BIN"
}
```

---

## Pester (PowerShell)

### Setup

Pester v5.7+ comes pre-installed with PowerShell 7. For PowerShell 5.1:

```powershell
Install-Module -Name Pester -Force -SkipPublisherCheck -MinimumVersion 5.7.0
```

### File Naming Convention

```
tests/powershell/{ScriptName}.Tests.ps1
```

Example: tests for `Install-DAAF.ps1` go in `tests/powershell/Install-DAAF.Tests.ps1`.

### Basic Test Structure

```powershell
Describe "Install-DAAF" {

    BeforeAll {
        # Source the script under test
        . $PSScriptRoot/../../scripts/Install-DAAF.ps1
    }

    Context "when Docker is not installed" {
        BeforeAll {
            # Must declare the function before mocking
            function docker {}
            Mock docker { throw "not found" }
        }

        It "exits with error" {
            { Install-DaafComponent -ComponentName "test" } | Should -Throw
        }

        It "displays an actionable error message" {
            # Capture error output
            try {
                Install-DaafComponent -ComponentName "test"
            }
            catch {
                $_.Exception.Message | Should -BeLike "*Docker*"
            }
        }
    }

    Context "when Docker is running" {
        BeforeAll {
            function docker {}
            Mock docker {
                $global:LASTEXITCODE = 0
                return "mock output"
            }
        }

        It "completes successfully" {
            { Install-DaafComponent -ComponentName "test" } | Should -Not -Throw
        }

        It "calls docker with correct arguments" {
            Install-DaafComponent -ComponentName "test"
            Should -Invoke docker -Times 1 -ParameterFilter {
                $args -contains "build"
            }
        }
    }
}
```

### Key Pester Assertions

| Assertion | What It Checks |
|-----------|---------------|
| `Should -Be $expected` | Exact equality |
| `Should -BeLike "*pattern*"` | Wildcard match |
| `Should -BeTrue` | Boolean true |
| `Should -Throw` | Exception thrown |
| `Should -Not -Throw` | No exception |
| `Should -Invoke cmd -Times N` | Mock called N times |

### Mocking Native Commands in Pester

PowerShell cannot mock native commands directly. Declare a dummy function first, then mock it:

```powershell
# Step 1: Declare a function with the same name
function docker {}

# Step 2: Mock the function
Mock docker {
    $global:LASTEXITCODE = 0
    return "mock output"
}

# Step 3: Verify calls
Should -Invoke docker -Times 2
```

**For testing $LASTEXITCODE behavior:**

```powershell
# Simulate docker failure
Mock docker {
    $global:LASTEXITCODE = 1
    # Return nothing — simulates a failed build
}

It "detects docker build failure" {
    { Start-DockerBuild } | Should -Throw "*failed*"
}
```

### Running Tests

```powershell
# Run all tests
Invoke-Pester -Path ./tests/powershell/ -Output Detailed

# Run with code coverage
Invoke-Pester -Path ./tests/powershell/ -CodeCoverage ./scripts/*.ps1

# Run with CI output
Invoke-Pester -Path ./tests/powershell/ -CI
```

---

## In-Container Validation Toolchain (DAAF_DEV)

The `DAAF_DEV=1` opt-in image bakes the full shell-validation toolchain directly
into the container, so scripts can be parsed, tested, and linted *in place*
without a separate runner. This exists **only in `DAAF_DEV=1` builds** — a
default (non-dev) container will not have `pwsh` or the linters on PATH.

**What's installed (DAAF_DEV builds):**

| Tool | Version | Purpose |
|------|---------|---------|
| `pwsh` | 7.6.3 (at `/usr/bin/pwsh`) | PowerShell parse + Pester runner |
| Pester | 5.7.1 | PowerShell test framework |
| PSScriptAnalyzer | 1.24.0 | PowerShell linter |
| `shellcheck` | (Dockerfile-installed) | Bash linter |
| `bats` | (Dockerfile-installed) | Bash test framework |

**Always probe before declaring a tool unavailable.** Do not assume "there's no
`pwsh` in this container" from memory — the DAAF_DEV image provides it. State that
a validation tool is "not available" only *after* a failed probe, and report the
exact probe command you ran so the claim is auditable.

```bash
# Probe (run before claiming any validation tool is missing)
command -v pwsh          # PowerShell 7
command -v shellcheck    # Bash linter
bats --version           # Bash test framework
```

**Canonical validation commands (once a probe confirms the tool is present):**

```bash
# Parse a PowerShell script (0 errors expected) — pattern applies to any .ps1
pwsh -NoProfile -Command '$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("scripts/host/run_daaf.ps1",[ref]$null,[ref]$e); if($e){$e; exit 1}'

# Run the Pester suite
pwsh -NoProfile -Command 'Invoke-Pester -Path tests/powershell/ -Output Detailed'

# Lint a PowerShell script with the accepted-pattern suppressions
pwsh -NoProfile -Command 'Invoke-ScriptAnalyzer -Path scripts/host/run_daaf.ps1 -Settings .github/linters/PSScriptAnalyzerSettings.psd1'
```

Notes:
- The `.github/linters/PSScriptAnalyzerSettings.psd1` settings file suppresses
  accepted fleet patterns (e.g. `PSAvoidUsingWriteHost`), so lint findings against
  it are real deviations, not style noise. Always pass `-Settings` — a bare
  `Invoke-ScriptAnalyzer` will flag accepted patterns.
- `Invoke-ScriptAnalyzer -Path` takes a **single** string, not an array — lint one
  file per invocation (loop for multiple files).

---

## CI Workflow (GitHub Actions)

### Recommended Matrix

```yaml
name: Shell Script CI

on:
  push:
    paths:
      - '**.sh'
      - '**.ps1'
      - '**.bats'
      - '**/Tests.ps1'
      - '.github/workflows/shell-ci.yml'
  pull_request:
    paths:
      - '**.sh'
      - '**.ps1'
      - '**.bats'
      - '**/Tests.ps1'

jobs:
  shellcheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ludeeus/action-shellcheck@2.0.0
        with:
          severity: warning
          scandir: ./scripts

  psscriptanalyzer:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: devblackops/github-action-psscriptanalyzer@v2
        with:
          path: ./scripts
          recurse: true
          output: results.sarif

  # BATS unit/smoke tests run on ubuntu only (bats results are stable across
  # platforms; the goal here is assertion coverage, not environment coverage).
  bats-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true
      - uses: bats-core/bats-action@4.0.0
        with:
          tests: tests/bash/

  # Cross-platform *smoke* tests (DAAF_DRY_RUN=1) cover the environment
  # dimension that unit tests do not: macOS Bash 3.2 and Windows PS 5.1
  # runtime behavior. This is where 4.x-only constructs surface on macOS.
  #
  # NOTE: interactive entry points (e.g. daaf.sh) cannot be included in a
  # plain loop — they block on `read` waiting for menu input. DAAF's real
  # CI handles this by running daaf.sh in a SEPARATE step with `printf 'q\n'`
  # piped to stdin and a seeded *_daaf_backup directory to exercise the
  # gather_status last-backup code path. Non-interactive lifecycle scripts
  # (install, backup, update, etc.) are run in the loop below.
  # See .github/workflows/ci-scripts.yml for the authoritative implementation.
  smoke-tests:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      # Non-interactive lifecycle scripts — run each individually
      - if: matrix.os != 'windows-latest'
        run: |
          for f in install backup_daaf rebuild_daaf update_daaf migrate_daaf \
                   restore_from_backup view_logs view_notebooks run_vscode run_daaf; do
            DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "scripts/host/${f}.sh" >/dev/null || exit 1
          done
      # Interactive entry point: drive with a quit choice on stdin (macOS only
      # — Bash 3.2 coverage; see the bats-bash32 job for the container version)
      - if: matrix.os == 'macos-latest'
        run: |
          mkdir -p ./2026-06-18_daaf_backup
          printf 'q\n' | DAAF_DRY_RUN=1 /bin/bash scripts/host/daaf.sh >/dev/null
          rm -rf ./2026-06-18_daaf_backup

  # Deterministic Bash 3.2 coverage on ubuntu via the official bash:3.2 image.
  # Three steps: (1) syntax-check all host scripts with `bash -n`, (2) DRY_RUN
  # smoke of the non-interactive lifecycle scripts, (3) daaf.sh Control Panel
  # driven with `printf 'q\n'` and a seeded backup dir. See
  # .github/workflows/ci-scripts.yml for the authoritative implementation.
  bats-bash32:
    runs-on: ubuntu-latest
    container:
      image: bash:3.2
    steps:
      - uses: actions/checkout@v4
      # Step 1: syntax check
      - run: |
          for f in scripts/host/*.sh; do bash -n "$f" || exit 1; done
      # Step 2: lifecycle smoke
      - run: |
          for f in install backup_daaf rebuild_daaf update_daaf migrate_daaf \
                   restore_from_backup view_logs view_notebooks run_vscode run_daaf; do
            DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "scripts/host/${f}.sh" >/dev/null 2>&1 || exit 1
          done
      # Step 3: daaf.sh Control Panel (interactive, driven with q)
      - run: |
          mkdir -p ./2026-06-18_daaf_backup
          printf 'q\n' | DAAF_DRY_RUN=1 bash scripts/host/daaf.sh >/dev/null
          rm -rf ./2026-06-18_daaf_backup

  pester-tests:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - shell: pwsh
        run: |
          Invoke-Pester -Path ./tests/powershell/ -CI -Output Detailed
```

### Key Points

- **Path filtering:** Only run when shell-related files change (saves CI minutes)
- **ShellCheck:** Ubuntu only (same results cross-platform)
- **PSScriptAnalyzer:** Ubuntu only (same results cross-platform)
- **BATS:** Ubuntu only — bats assertion results are stable across platforms, so a second OS buys little. Environment differences are covered by the smoke and bash32 jobs instead (see below).
- **Smoke (DRY_RUN):** All three OS. This is the layer that catches *environment*-specific runtime behavior: macOS system Bash 3.2 and Windows PS 5.1. Interactive entry points that run a menu loop (e.g. `daaf.sh`) are driven with a quit choice on stdin and any state their code paths require (e.g. a seeded `*_daaf_backup` dir) so the historically fragile branch actually executes.
- **bash32 (container):** Ubuntu, inside the official `bash:3.2` image. Deterministic Bash 3.2 coverage that does not depend on macOS-runner bash drift; catches runtime-only 3.2 incompatibilities that parse cleanly and that ShellCheck cannot flag. See `./bash-standards.md` > "Host-Script Portability" for the banned-construct list this job backstops.
- **Pester:** All three OS (PowerShell behavior varies across platforms)
- **Submodules:** Required for BATS helper libraries

> **Why not run BATS on macOS too?** An earlier version of this reference recommended BATS on ubuntu + macOS. In practice, DAAF splits the concern: BATS on ubuntu owns *assertion* coverage, while the smoke and `bash:3.2` jobs own *environment* coverage (which is what actually catches Bash 3.2 defects). This mirrors DAAF's real `ci-scripts.yml`. Provisioning BATS inside the Alpine-based `bash:3.2` image is brittle (no `apk` bats package, no `git`/`make` to bootstrap bats-core), so that job uses syntax + DRY_RUN smoke rather than the full bats suite.

---

## Test Checklist

When adding tests for a new script:

| # | Item | Notes |
|---|------|-------|
| 1 | `--help` / no-args shows usage | Smoke test |
| 2 | Valid input exits 0 | Happy path |
| 3 | Missing file exits non-zero with error | Error path |
| 4 | Missing dependency detected | Preflight check |
| 5 | Error messages include remediation | Two-part errors |
| 6 | Docker calls use mocks (not real daemon) | Unit test isolation |
| 7 | Idempotent: running twice is safe | Re-run test |
| 8 | Exit codes match documented conventions | See error-handling.md |
