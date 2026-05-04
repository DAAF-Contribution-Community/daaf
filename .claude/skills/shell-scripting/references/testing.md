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

  bats-tests:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true
      - uses: bats-core/bats-action@4.0.0
        with:
          tests: tests/bash/

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
- **BATS:** Ubuntu + macOS (covers most Bash environments; skip Windows)
- **Pester:** All three OS (PowerShell behavior varies across platforms)
- **Submodules:** Required for BATS helper libraries

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
