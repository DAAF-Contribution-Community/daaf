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

### Set `TMPDIR` for In-Container bats and Pester Runs

Both runners put their fixtures under the system temp directory, which is `/tmp`
unless `TMPDIR` says otherwise. bats sets `BATS_TMPDIR="${TMPDIR:-/tmp}"`
(`/usr/libexec/bats-core/bats`), and a suite's own `mktemp -d` fixtures follow
`TMPDIR` too. Pester's `$TestDrive` comes from `[System.IO.Path]::GetTempPath()`
on Linux (`Get-TempDirectory` in `Pester.psm1`), which reads `TMPDIR`. DAAF forbids
working-file writes to `/tmp` because it sits outside the backup and audit boundary
(CLAUDE.md § Provenance Boundary). The command line names no `/tmp` path, so the
`bash-safety.sh` guard cannot see these writes. Point `TMPDIR` at a scratch
directory inside the project instead: `{PROJECT_DIR}/scripts/scratch/tmp` in a
research project, or `scratch/tmp` in a Framework Development workspace. Create it
first, because bats refuses to start when `BATS_TMPDIR` does not exist. One command
per Bash call:

```bash
mkdir -p <project>/scratch/tmp
```

```bash
env TMPDIR=<project>/scratch/tmp bats tests/bash/x.bats
```

```bash
env TMPDIR=<project>/scratch/tmp pwsh -NoProfile -Command "Invoke-Pester -Path tests/powershell/x.Tests.ps1 -Output Detailed"
```

Notes:
- **Fixtures must clean themselves up.** An in-session `rm -r` of a leftover
  fixture directory may be denied by the permission system (this happened to both
  the orchestrator and review subagents during the 2026-09-29 backup work), so do
  not plan on removing fixtures after the run. Remove anything a test creates
  (e.g. a `mktemp -d` from `setup`) in `teardown` / `AfterAll`, on pass and on
  failure. The runners clean up their own directories: bats removes its run
  directory on exit unless `--no-tempdir-cleanup` is given, and Pester removes
  `$TestDrive` when the top-level block finishes.
- **An interrupted run can leave the bats run directory behind.** That directory
  holds a symlink that bats creates for each test file
  (`bats-exec-file`), which `bash scripts/check_workspace_invariants.sh` flags as
  unauthorized. Run the checker after in-container test runs, and ask the user to
  remove any leftovers it reports.

---

## DAAF Safety-Hook Regression Batteries

DAAF ships **four** standing regression surfaces for the two security-critical PreToolUse hooks — a `.sh` battery and a `bats` suite for each hook — plus `bats` suites for the other safety-relevant hooks, the execution wrapper and the checked-in permission rules (see "Other hook and wrapper suites" below). Read these before writing or modifying `bash-safety.sh` or `enforce-single-command.sh`: they are where you add a case for any new block (or allow) behavior, and how you prove a change before it goes live.

| Surface | Covers | Invocation |
|---------|--------|------------|
| `scripts/test_safety_hooks.sh` | `bash-safety.sh` (destructive commands, pipe-to-shell, exfiltration, container escape, /tmp provenance guard, anti-tampering, package-install guard, the §0 quote-aware commit-message carve-out, and the 2026-09-18 stage-0a–0e classification pipeline) | `bash scripts/test_safety_hooks.sh` tests the **live** hook. Pass a path to test a **staged draft** before install: `bash scripts/test_safety_hooks.sh <draft-path>` |
| `tests/bash/bash_safety.bats` | `bash-safety.sh` — the full hook (see below) | `bats tests/bash/bash_safety.bats`; override with `BASH_SAFETY_SH=<draft-path>` |
| `scripts/test_enforce_single_command.sh` | `enforce-single-command.sh` (command-chaining detection: `&&`/`;`/`\|\|`/newlines, quote- and nesting-aware) | `bash scripts/test_enforce_single_command.sh`; override with `HOOK=<draft-path>` |
| `tests/bash/enforce_single_command.bats` | `enforce-single-command.sh` — quoting, nesting, heredocs, comments, and the documented residuals | `bats tests/bash/enforce_single_command.bats`; override with `ENFORCE_SINGLE_COMMAND_SH=<draft-path>` |

Each surface accepts a **draft path**, which is the sanctioned way to validate a hook change **before** it is installed: `.claude/hooks/` is write-protected (anti-tampering guard), so the workflow is stage the draft to a scratch path, run every surface for that hook against it, then hand the user the install command (see `../../../../agent_reference/ERROR_RECOVERY.md` > "PreToolUse Safety-Hook Blocks" for the staged-draft → user-install pattern). Note the mechanism differs by surface: the `.sh` batteries take the draft path as a **positional argument** (`test_safety_hooks.sh`) or the **`HOOK=` environment variable** (`test_enforce_single_command.sh`), while the two `bats` suites take a per-suite **environment override**.

**`tests/bash/bash_safety.bats`.** No longer a focused §0 carve-out suite: as of the 2026-09-18 hardening pass it is the broad suite for the whole hook — the companion suite spanning stage 0a (heredoc-body classification), 0b (the original commit-message carve-out), 0c (general quoted-span classification), 0d (escape canonicalization), 0e (the `$IFS` block), and §§1–8 (destructive filesystem and git operations, privilege escalation, network patterns, container escape, the /tmp provenance boundary, safety-system tampering, package installs), plus timing gates. The two timing gates run tracked fixtures, `tests/fixtures/bash_safety/perf_probe.sh` (a ~20 kB command with 300 quoted spans and 20 heredocs) and `tests/fixtures/bash_safety/perf_gate.sh` (32 kB and 64 kB padded commands that must still BLOCK), each under a 2 s budget; both resolve the hook path from their own location, accept a draft path as `$1`, and a missing fixture FAILs rather than skips — which is why they live under `tests/`, not in a git-excluded research workspace where a fresh clone or CI would not find them. Draft-testable via a `BASH_SAFETY_SH` override (mirroring `block_nested_dispatch.bats`'s `BLOCK_NESTED_DISPATCH_SH`): `BASH_SAFETY_SH=/path/to/draft/bash-safety.sh bats tests/bash/bash_safety.bats`. It defaults to the live hook, against which the ALLOW cases from any not-yet-installed hardening pass fail by design (the pass is exactly what makes them pass).

**Harmonized suites (2026-09-26).** `bash-safety.sh` shares one body with a sibling project, the Claude Code Starter Kit, so both bash-safety suites carry that project's permanent rows under *their* IDs (PT*/R4*/R5*) next to DAAF's own FC*/HZ* rows, and the two suites are **mirrored 1:1** — same IDs, strings and verdicts. Keep them mirrored by generating each block for both files from one row specification rather than hand-editing one suite and copying to the other, and confirm the ID sets match (an empty `comm -3` of the two ID lists).

**SITE CONFIG testing note.** Every project-specific value in `bash-safety.sh` lives in its SITE CONFIG block (`SITE_ROOT`, `SITE_EXTRA_PROTECTED_DIRS`, …), and `diff` of the two projects' copies must show only lines inside that block. So a suite run against the *other* site's variant is a useful refactor check: it must fail **only site rows** — those that name `/daaf`, a `/daaf/.git` or `/daaf/.claude` form, or `benchmarks/harness/hooks`. Most carry the `site-adapted` tag, plus the `HZB15` SITE CONFIG smoke row, but four older rows are untagged and also fail at the other site: three `benchmarks` rows in the battery only ("cp double-slash benchmarks", "cp into benchmarks hooks", "redirect benchmarks hooks") and `FC36` (project-root delete). The observed baseline on the starter-kit variant is 12 battery failures (`TOTAL: 749, PASS: 737, FAIL: 12`) and 9 `bats` failures. `HZB09` names `/daaf` but is untagged because it passes at both sites. Any failure outside that set means the shared body diverged. When you add a row that names a site value, tag it `site-adapted` in its description.

**`tests/bash/enforce_single_command.bats`.** The companion suite for the chaining hook, added with the 2026-09-18 hardening pass and draft-testable the same way: `ENFORCE_SINGLE_COMMAND_SH=/path/to/draft/enforce-single-command.sh bats tests/bash/enforce_single_command.bats`. It covers quote-awareness, `$( )` / `[[ ]]` / `(( ))` nesting, heredoc bodies, `#` comments, backslash escapes, and carrier decomposition, and it pins the four documented residuals as ALLOW-today cases tagged with their IDs: R1 closed-compound chains and R2 bare subshells (both deferred); R6, `ssh host 'a && b'`, whose remote body is not decomposed by design (the remote body runs on the remote host, not in this Bash call); and R7, a single stdin object whose `tool_name` is not a string, which reads as "not Bash" (the one-object gate checks the object count, not the field type). `scripts/test_enforce_single_command.sh` pins R6 and R7 too. So a future change that deliberately flips one surfaces as a failing test to update rather than passing silently. Both suites also carry the "(NEW 2026-09-26)" one-object stdin-gate cases (concatenated objects, malformed text, whitespace only, a bare string or array), fed as raw stdin (see the key-technique note below). Like `bash_safety.bats` it defaults to the live hook, against which the new-behavior cases fail by design until the draft is installed.

**`tests/bash/output_scanner.bats`.** The suite for the `output-scanner.sh` **PostToolUse** hook (secret detection in tool output; advisory, always exits 0). Because the hook never blocks, every case asserts exit 0, and the verdict is the stdout: a warning naming the credential family, or silence on clean output. The cases cover every credential family the hook names and the `tool_response` shapes it must handle: a plain string (scanned exactly as before, with the 10 kB window measured on the raw text), and an object or array (e.g. Read/Grep/Glob output), which the hook renders as compact JSON text before scanning. Draft-testable via an `OUTPUT_SCANNER_SH` override: `OUTPUT_SCANNER_SH=/path/to/draft/output-scanner.sh bats tests/bash/output_scanner.bats`. Credential-shaped fixtures are assembled from split string fragments (`"AKIA""IOSF…"`, `"-----BEGIN RSA ""PRIVATE KEY-----"`). Private-key headers in particular must stay split: a whole header literal makes the pre-commit `detect-private-key` hook reject the commit. The suite (57 cases) also covers the value-based warning from the hook-maintenance bundle (revision `_b`, installed 2026-09-27). Its one case marked `(_c)` pins revision `_c` (`apply_hook_patches_c.sh`) and fails on the installed hook until that revision is installed; `audit_log.bats` (68 cases) has seven such cases.

**Other hook and wrapper suites.** Each is a single `bats` file with a per-suite draft override, following the same stage-then-test pattern:

| Suite | Covers | Draft override |
|-------|--------|----------------|
| `tests/bash/audit_log.bats` | `audit-log.sh`: pattern and value-based redaction, the pattern cap and regex-failure guard on every target, NUL safety, fallback record, xtrace guard, and the pin that the `SECRET-NAME-VOCAB v1` block is identical in its three carriers | `AUDIT_LOG_SH` (plus `OUTPUT_SCANNER_SH` for the cross-carrier pin) |
| `tests/bash/deny_claude_code_guide.bats` | `deny-claude-code-guide.sh`: the banned `subagent_type`, jq-free fallback, concatenated-stream deny | `DENY_CLAUDE_CODE_GUIDE_SH` |
| `tests/bash/enforce_explore_model.bats` | `enforce-explore-model.sh`: the same shape for `Explore` | `ENFORCE_EXPLORE_MODEL_SH` |
| `tests/bash/enforce_file_first.bats` | `enforce-file-first.sh`: direct interpreter blocks and the one-object stdin gate | `ENFORCE_FILE_FIRST_SH` |
| `tests/bash/block_nested_dispatch.bats` | `block-nested-dispatch.sh` | `BLOCK_NESTED_DISPATCH_SH` |
| `tests/bash/run_with_capture.bats` | `scripts/run_with_capture.sh`: the package-install and environment-secret print scans (exit 3), evidence verification (exit 74), and the vocabulary pin | `RUN_WITH_CAPTURE_SH` (defaults to the repository copy) |
| `tests/bash/settings_permissions.bats` | static contract for `.claude/settings.json` deny rules, including the environment-disclosure `Bash(...)` entries; does not prove matcher semantics | none |

The six hook-maintenance suites (the first five rows plus `output_scanner.bats`) run together as one command in the bundle's `README_c.md` § 6, which also gives the expected counts before and after install. The environment-value cases in `audit_log.bats` and `output_scanner.bats` set their own fake `DAAFTEST_*` variables and assert only on those; the stderr-silence and xtrace cases also run the hook under `env -i`, so only the fake variables exist. `run_with_capture.bats` checks script text and needs no environment values. Never write a test that reads or prints the real environment.

**Key technique — case strings live inside the battery, never on the command line.** Each battery feeds its test-case command strings to the hook from *inside* the battery file. Passing a case string as a command-line argument to the invocation would route it through the live PreToolUse hooks, which would vet (and potentially block) the case string itself before the battery ever ran. So the batteries are always invoked **bare** (the single optional argument to `test_safety_hooks.sh` is a hook *path*, not a case string). When adding coverage, add the case to the battery file — do not try to exercise it from the invoking command line.

**Raw-stdin exception.** Normally a helper wraps each case string in a one-object `jq` envelope (`{tool_name:"Bash",tool_input:{command:…}}`). The one-object stdin-gate cases cannot use that helper, because their subject *is* the envelope: concatenated objects, malformed text, whitespace only, empty stdin, a bare string or array. Those cases pipe their text to the hook verbatim through a separate raw helper: `run_case_raw` in `scripts/test_safety_hooks.sh` and `_run_hook_raw` in `tests/bash/bash_safety.bats` (FC227-FC238, plus the FC240 pin for the non-string `tool_name` residual), `test_raw_stdin` in `scripts/test_enforce_single_command.sh` and `_run_hook_raw` in `tests/bash/enforce_single_command.bats` (the "(NEW 2026-09-26)" cases and the R7 pin). The raw payloads still live inside the suite files, so the key technique above holds. Use the raw helper only for cases about the envelope itself; every command-content case goes through the normal helper, so a case never depends on a hand-built envelope being valid JSON.

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
      - uses: actions/checkout@v5
      - uses: ludeeus/action-shellcheck@2.0.0
        with:
          severity: warning
          scandir: ./scripts

  psscriptanalyzer:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
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
      - uses: actions/checkout@v5
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
      - uses: actions/checkout@v5
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
      - uses: actions/checkout@v5
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
      - uses: actions/checkout@v5
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
