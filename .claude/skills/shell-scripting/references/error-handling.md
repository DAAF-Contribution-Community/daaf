# Error Handling

Cross-language error handling philosophy and patterns for DAAF shell scripts. Covers the fail-closed principle, user-facing output conventions, exit code standards, Docker-specific error handling, and dependency validation.

---

## Fail-Closed Principle

Security-critical scripts (hooks, safety checks) must fail closed: if the script cannot determine whether an action is safe, it must **block the action**. Uncertainty always resolves to denial.

```bash
# GOOD: fail-closed — missing dependency blocks the action
if ! command -v jq >/dev/null 2>&1; then
    echo "ERROR: jq is required but not found. Cannot verify safety." >&2
    exit 2  # Block (DAAF hook convention)
fi

# BAD: fail-open — missing dependency allows the action through
if ! command -v jq >/dev/null 2>&1; then
    echo "WARNING: jq not found, skipping check" >&2
    exit 0  # Allow (dangerous for security hooks)
fi
```

**When fail-closed applies:**
- All scripts in `.claude/hooks/`
- Any script that gates a destructive operation (backup verification, pre-deploy checks)
- Any script that validates permissions or credentials

**When fail-open is acceptable:**
- Non-critical convenience scripts (status displays, formatting helpers)
- Optional enhancement checks (style linting, optional metrics collection)

---

## User-Facing Output Conventions

### Two-Part Error Messages

Every error message must include TWO parts: **what went wrong** AND **what to do about it**:

```bash
# GOOD: explains both problem and remedy
echo "ERROR: Docker daemon is not running." >&2
echo "  Fix: Start Docker Desktop, or run 'sudo systemctl start docker'" >&2

# BAD: states the problem but leaves the user stranded
echo "ERROR: Docker not available" >&2
```

```powershell
# GOOD
Write-Error "Docker daemon is not running. Start Docker Desktop or run 'sudo systemctl start docker'"

# BAD
Write-Error "Docker not available"
```

### Output Routing

All diagnostic output goes to stderr so it does not contaminate stdout data streams:

```bash
# Status messages → stderr
echo "INFO: Starting backup..." >&2

# Error messages → stderr
echo "ERROR: Backup failed: disk full" >&2

# Data output → stdout (capturable by callers)
echo "$result"
```

### Color Formatting (Bash)

Use `tput` for portable color codes, and respect the `NO_COLOR` environment variable and non-TTY contexts:

```bash
# --- Color setup ---
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    RED=$(tput setaf 1)
    GREEN=$(tput setaf 2)
    YELLOW=$(tput setaf 3)
    CYAN=$(tput setaf 6)
    RESET=$(tput sgr0)
else
    RED="" GREEN="" YELLOW="" CYAN="" RESET=""
fi

# --- Helper functions ---
info()    { echo "${CYAN}INFO:${RESET} $*" >&2; }
success() { echo "${GREEN}SUCCESS:${RESET} $*" >&2; }
warn()    { echo "${YELLOW}WARNING:${RESET} $*" >&2; }
error()   { echo "${RED}ERROR:${RESET} $*" >&2; }
```

**Key points:**
- `[ -t 1 ]` checks if stdout is a terminal (not a pipe or file)
- `NO_COLOR` is a community convention (https://no-color.org/) — respect it
- When colors are disabled, the helper functions still work, just without formatting

### Color Formatting (PowerShell)

PowerShell has built-in color support via `-ForegroundColor`:

```powershell
function Write-Info    { param([string]$Message) Write-Host "INFO: $Message" -ForegroundColor Cyan }
function Write-Success { param([string]$Message) Write-Host "SUCCESS: $Message" -ForegroundColor Green }
function Write-Warn    { param([string]$Message) Write-Host "WARNING: $Message" -ForegroundColor Yellow }
# Write-Error already has its own formatting
```

---

## Exit Code Conventions

### Standard Exit Codes

| Code | Meaning | When to Use |
|------|---------|-------------|
| 0 | Success | Script completed normally |
| 1 | General error | Catchall for unspecified failures |
| 2 | Blocked | DAAF hook convention: action should be prevented |

### Reserved Ranges for DAAF Scripts

Scripts that need more granular exit codes should use these ranges:

| Range | Category | Examples |
|-------|----------|---------|
| 0 | Success | — |
| 1 | General error | — |
| 2 | Blocked (hooks) | Safety check failed, unauthorized action |
| 10-19 | Docker failures | 10: daemon not running, 11: build failed, 12: compose failed |
| 20-29 | Configuration errors | 20: config file missing, 21: invalid config value |
| 30-39 | Dependency errors | 30: required tool missing, 31: wrong version |

### Consistent Exit in Bash

```bash
# Named exit codes for readability
readonly EXIT_SUCCESS=0
readonly EXIT_ERROR=1
readonly EXIT_BLOCKED=2
readonly EXIT_DOCKER_UNAVAILABLE=10

if ! docker info >/dev/null 2>&1; then
    error "Docker daemon is not running. Start Docker Desktop."
    exit "$EXIT_DOCKER_UNAVAILABLE"
fi
```

### Consistent Exit in PowerShell

```powershell
$EXIT_SUCCESS = 0
$EXIT_ERROR = 1
$EXIT_BLOCKED = 2
$EXIT_DOCKER_UNAVAILABLE = 10

if (-not (docker info 2>$null)) {
    Write-Error "Docker daemon is not running. Start Docker Desktop."
    exit $EXIT_DOCKER_UNAVAILABLE
}
```

---

## Docker-Specific Error Handling

Docker operations are uniquely error-prone because they combine native command exit codes, complex stderr output, asynchronous container startup, and machine-readable output formats.

### Pre-Docker Validation

Always check two things before any Docker operation:

```bash
# 1. Is Docker installed?
if ! command -v docker >/dev/null 2>&1; then
    error "Docker not found. Install from https://docs.docker.com/get-docker/"
    exit 10
fi

# 2. Is Docker daemon running?
if ! docker info >/dev/null 2>&1; then
    error "Docker daemon is not running. Start Docker Desktop."
    exit 10
fi
```

### Check Exit Codes After Every Call

```bash
# Bash — use if-not pattern (compatible with set -e)
if ! docker compose up -d; then
    error "docker compose up failed. Check logs: docker compose logs"
    exit 12
fi
```

```powershell
# PowerShell
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker compose up failed. Check logs: docker compose logs"
    exit 12
}
```

### Capture Build Output

Docker build output should be captured to a log file AND displayed to the user. On failure, direct the user to the log:

```bash
BUILD_LOG="$(mktemp)"
trap 'rm -f "$BUILD_LOG"' EXIT

echo "[2/4] Building Docker image..."
if ! docker build -t myimage . 2>&1 | tee "$BUILD_LOG"; then
    error "Docker build failed. Full log: $BUILD_LOG"
    # Don't delete the log on failure — keep trap but skip cleanup
    trap - EXIT
    exit 11
fi
```

### Machine-Readable Status Checks

Never parse human-readable Docker output. Use machine-readable formats:

```bash
# GOOD: JSON output for programmatic parsing
docker compose ps --format json | jq -r '.[] | select(.State != "running") | .Name'

# GOOD: Go template for specific fields
docker inspect --format '{{.State.Status}}' mycontainer

# BAD: parsing human-readable table output
docker compose ps | grep "Up" | awk '{print $1}'
```

### Bounded Readiness Loops

When waiting for a container to become ready, always set a maximum wait time:

```bash
MAX_WAIT=60
INTERVAL=2
elapsed=0

echo "Waiting for service to be ready..."
while [ "$elapsed" -lt "$MAX_WAIT" ]; do
    if docker compose exec -T myservice pg_isready >/dev/null 2>&1; then
        success "Service is ready."
        break
    fi
    sleep "$INTERVAL"
    elapsed=$((elapsed + INTERVAL))
done

if [ "$elapsed" -ge "$MAX_WAIT" ]; then
    error "Service did not become ready within ${MAX_WAIT}s."
    # Capture diagnostic info
    docker compose logs myservice >&2
    exit 12
fi
```

**Key points:**
- Always have a maximum wait (`MAX_WAIT`)
- Capture stderr during readiness loops for diagnostics on timeout
- On timeout, dump container logs to help the user diagnose

---

## Dependency Validation

Check all external dependencies at script start, before any mutations:

### Bash Pattern

```bash
# --- Preflight ---
missing=()
for cmd in docker jq git curl; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        missing+=("$cmd")
    fi
done

if [ ${#missing[@]} -gt 0 ]; then
    error "Missing required tools: ${missing[*]}"
    echo "  Install with your package manager, e.g.:" >&2
    echo "    apt-get install ${missing[*]}" >&2
    echo "    brew install ${missing[*]}" >&2
    exit 30
fi
```

### PowerShell Pattern

```powershell
# --- Preflight ---
$missing = @()
foreach ($cmd in @('docker', 'git')) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        $missing += $cmd
    }
}

if ($missing.Count -gt 0) {
    Write-Error "Missing required tools: $($missing -join ', '). Install before proceeding."
    exit 30
}
```

### Version Checks

When a minimum version is required, validate it explicitly:

```bash
# Check Docker Compose v2
if ! docker compose version >/dev/null 2>&1; then
    error "Docker Compose v2 required. Found: legacy docker-compose."
    echo "  Upgrade: https://docs.docker.com/compose/install/" >&2
    exit 31
fi
```

---

## DAAF Composability Patterns

### DAAF_NESTED Flag

When scripts call other scripts, use `DAAF_NESTED` to suppress interactive behavior:

```bash
# Outer script
export DAAF_NESTED=1
bash ./inner_script.sh
ec=$?
unset DAAF_NESTED

if [ $ec -ne 0 ]; then
    error "Inner script failed with exit code $ec"
    exit $ec
fi
```

```bash
# Inner script (at the end)
if [ "${DAAF_NESTED:-}" != "1" ]; then
    echo ""
    echo "Press Enter to close..."
    read -r
fi
exit "$exit_code"
```

### Idempotent Operations

Scripts should be safe to run multiple times. Check for prior state before acting:

```bash
# Idempotent backup
if [ -d "$BACKUP_DIR" ]; then
    info "Backup already exists at $BACKUP_DIR — skipping."
else
    info "Creating backup at $BACKUP_DIR..."
    cp -r "$TARGET_DIR" "$BACKUP_DIR"
fi

# Idempotent container start
if docker compose ps --format json | jq -e '.[] | select(.Name == "myservice" and .State == "running")' >/dev/null 2>&1; then
    info "Service already running — skipping start."
else
    docker compose up -d myservice
fi
```
