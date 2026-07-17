# Bash Standards

Comprehensive standards for writing Bash scripts in DAAF. Covers preamble rules, quoting discipline, variable handling, ShellCheck integration, signal handling, and prohibited patterns.

---

## Preamble

Every Bash script starts with exactly these two lines:

```bash
#!/usr/bin/env bash
set -euo pipefail
```

**What each flag does:**

| Flag | Name | Behavior | Nuance |
|------|------|----------|--------|
| `-e` | errexit | Exit immediately on non-zero return | Commands in conditionals (`if cmd; then`) are automatically exempt |
| `-u` | nounset | Exit on unbound (undeclared) variables | Use `${VAR:-default}` for intentionally optional variables |
| `-o pipefail` | pipefail | Pipeline returns the exit code of the *last* failing command, not the last command | Without this, `failing_cmd \| grep foo` returns grep's exit code, hiding the failure |

**When to add `set -E`:**

Add `set -E` (errtrace) when using `trap ... ERR` inside functions or subshells. Without `-E`, ERR traps are not inherited by functions:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "ERROR on line $LINENO" >&2; exit 1' ERR
```

**Exception — hooks that must inspect failures:**

Hooks that need to examine a failure and decide whether to block or allow should not use `set -e`. Instead, use an explicit ERR trap with controlled exit codes:

```bash
#!/usr/bin/env bash
set -uo pipefail
# Deliberately omit -e: this hook inspects failures and decides exit code

trap 'echo "ERROR: unexpected failure in hook" >&2; exit 2' ERR

# ... inspection logic with explicit error handling ...
```

This pattern is used by `bash-safety.sh` and `enforce-file-first.sh` in DAAF.

---

## Quoting Discipline

Unquoted variables are the single most common source of Bash bugs. The rule is simple: **quote everything.**

### Always Quote

```bash
# Variables
echo "$var"
echo "${var}"

# Command substitutions
result="$(some_command)"

# Array expansion
for item in "${array[@]}"; do

# Paths with possible spaces
cp "$source" "$destination"
```

### Use Braces for Adjacency

```bash
# Good: braces disambiguate where the variable name ends
echo "${var}_suffix"
echo "${filename}.bak"

# Bad: shell tries to expand $var_suffix as one variable
echo "$var_suffix"
```

### Glob Safety

```bash
# Good: ./ prefix prevents filenames starting with - from being parsed as options
for f in ./*.txt; do

# Bad: a file named -rf.txt would be interpreted as an option
for f in *.txt; do
```

### Arrays for Command Arguments

When building command-line arguments dynamically, use arrays instead of string concatenation:

```bash
# Good: each element is a separate argument, properly quoted
local -a cmd_args=("--flag" "$value" "--output" "$outfile")
my_command "${cmd_args[@]}"

# Bad: word splitting and glob expansion can corrupt arguments
cmd_args="--flag $value --output $outfile"
my_command $cmd_args
```

### Separate Declaration from Assignment

When using `local` with command substitution, separate the declaration from the assignment. The `local` builtin always returns 0, masking the exit code of the command substitution:

```bash
# Good: if cmd fails, set -e catches it
local result
result=$(some_command)

# Bad: local masks the exit code — if some_command fails, $? is still 0
local result=$(some_command)
```

This is ShellCheck SC2155 and one of the most insidious Bash bugs. See `gotchas.md` for details.

---

## Variable Handling

### Readonly for Constants

```bash
readonly BASE_DIR="/daaf"
readonly MAX_RETRIES=3
```

### Default Values

```bash
# Provide a default if unset (compatible with set -u)
verbose="${VERBOSE:-0}"
config_file="${CONFIG_FILE:-./config.yml}"

# Provide a default if unset or empty
output_dir="${OUTPUT_DIR:-.}"
```

### Parameter Validation

```bash
# Require a positional argument
if [ $# -lt 1 ]; then
    echo "Usage: $(basename "$0") <input-file>" >&2
    exit 1
fi

input_file="$1"

# Validate the argument
if [ ! -f "$input_file" ]; then
    echo "ERROR: File not found: $input_file" >&2
    exit 1
fi
```

---

## Never Do

These patterns are banned in DAAF scripts:

| Pattern | Problem | Alternative |
|---------|---------|-------------|
| `eval "$cmd"` | Arbitrary code execution, injection attacks | Use arrays: `"${cmd[@]}"` |
| `` `command` `` (backticks) | Cannot nest, harder to read | `$(command)` |
| Parsing `ls` output | Breaks on spaces, newlines, special chars in filenames | `for f in ./*.ext` or `find ... -print0 \| xargs -0` |
| `$*` when you mean `"$@"` | Joins all arguments into a single string | `"$@"` preserves individual arguments |
| `[ $var = "value" ]` | Word splitting if var is empty or contains spaces | `[ "$var" = "value" ]` or `[[ $var = "value" ]]` |

---

## ShellCheck Integration

[ShellCheck](https://www.shellcheck.net/) is the standard linter for Bash scripts.

### Running ShellCheck

```bash
shellcheck -x -S warning script.sh
```

| Flag | Purpose |
|------|---------|
| `-x` | Follow `source`/`.` includes to check sourced files |
| `-S warning` | Set minimum severity to warning (skip style/info) |

### Top Findings to Watch

| Code | Description | Fix |
|------|-------------|-----|
| SC2086 | Unquoted variable | Add double quotes: `"$var"` |
| SC2046 | Unquoted command substitution | Add double quotes: `"$(cmd)"` |
| SC2155 | `local var=$(cmd)` masks return code | Separate: `local var; var=$(cmd)` |
| SC2164 | `cd` without `\|\| exit` | Add fallback: `cd "$dir" \|\| exit 1` |
| SC2006 | Backtick command substitution | Use `$(...)` instead |

### Suppressing Warnings

Only suppress with an inline comment explaining why:

```bash
# shellcheck disable=SC2034 -- variable used by sourced script
readonly MY_CONFIG="value"
```

Bare `# shellcheck disable=SCXXXX` without an explanation comment is not acceptable — the reasoning must be documented.

---

## Signal Handling and Cleanup

### Basic Cleanup Pattern

```bash
#!/usr/bin/env bash
set -euo pipefail

# --- Variables ---
TMPDIR=""

# --- Cleanup (register immediately after variables) ---
cleanup() {
    rm -f "${TMPDIR:?}/"*  # -f makes it idempotent
    rmdir "$TMPDIR" 2>/dev/null || true
}
trap cleanup EXIT

# --- Setup ---
TMPDIR="$(mktemp -d)"

# ... rest of script ...
```

**Key principles:**

1. **Place `trap` immediately after variable declarations**, before any operations that create state needing cleanup
2. **Use `trap ... EXIT`** — it fires on normal exit, errors (`set -e`), and most signals (SIGINT, SIGTERM)
3. **Create temp files with `mktemp`**, then register for cleanup immediately
4. **Make cleanup idempotent**: use `rm -f` (not `rm`), guard with `|| true` where needed
5. **Use single quotes in trap string** to defer variable expansion:

```bash
# Good: $TMPFILE expands at trap execution time (uses current value)
trap 'rm -f "$TMPFILE"' EXIT

# Bad: $TMPFILE expands at trap definition time (may be empty)
trap "rm -f $TMPFILE" EXIT
```

### ERR Trap for Diagnostics

For scripts where you want to report the failing line on unexpected errors:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

trap 'echo "ERROR: Script failed at line $LINENO. Command: $BASH_COMMAND" >&2' ERR

# ... script body ...
```

The `-E` flag ensures the ERR trap is inherited by functions and subshells.

### Probe and Test-Harness Hygiene (Self-Cleaning Filesystem Objects)

A scratch probe or test harness that creates **invariant-violating filesystem objects** — symlinks, and especially symlinks with pathological names (embedded tabs or newlines) — must delete those objects before it exits, from **inside the probe script itself**. The cleanup binds via a `trap`, not via the dispatch prompt that launched the probe:

```bash
#!/usr/bin/env bash
set -euo pipefail

# --- Config ---
readonly PROBE_DIR="${PROJECT_DIR}/scripts/scratch"

# --- Cleanup (register before creating any objects) ---
cleanup() {
    # Delete every symlink this probe may have created under its own dir.
    # `find … -type l -delete` removes only symlinks (not real files) and is
    # NOT blocked by bash-safety.sh — unlike `rm -rf` of the scratch tree.
    find "$PROBE_DIR" -type l -delete 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# --- Probe body: create symlinks, exercise the code under test ---
mkdir -p "$PROBE_DIR"
ln -s /some/target "$PROBE_DIR/$(printf 'pathological\tname')"
# ... run the gate/verification logic against the symlink ...
```

**Why cleanup lives in the probe, not the dispatch prompt.** A dispatch-prompt instruction ("clean up your symlinks before returning") binds only the one agent it addresses. It does not bind a *future* runner — another engineer's harness, or a reviewer manually re-running the gate logic outside the harness's own trap. This bit DAAF concretely on 2026-07-14: verification probes left symlinks with tab/newline names under `scripts/scratch/`, and the leftovers broke real user backups **three separate times** (twice via engineers' harnesses, once via a reviewer running gate logic by hand outside any trap). A `trap cleanup EXIT INT TERM` inside the probe covers every one of those runners; a prompt covers only the addressee.

**Why `find … -type l -delete` and not `rm -rf`.** The `bash-safety.sh` hook blocks `rm -rf` of scratch directories, but plain `rm` and `find … -delete` are allowed. `find "$PROBE_DIR" -type l -delete` is also *narrower* than deleting the tree — it removes exactly the symlinks (the invariant-violating objects) and leaves real scratch files intact for provenance.

**Verification step.** After the probe runs, confirm the workspace is clean by invoking the workspace invariant checker, which walks the live filesystem for unauthorized symlinks (Invariant 1) and repo-root leak artifacts — zero-byte stubs, `*.pre-migrate` backups, or a stray `daaf-docker/` directory left by a wrong-CWD host-tool dry-run (Invariant 2) — since git cannot see untracked scratch:

```bash
bash "${BASE_DIR}/scripts/check_workspace_invariants.sh"   # prints an OK line on pass; exits 1 and lists offenders (control chars escaped) on violation
```

The checker is the *checkable invariant* that binds everyone, complementing the per-probe trap that binds each runner. A green run here is the gate: if it lists an offending symlink, a probe leaked it — delete the object before proceeding.

### Composable Scripts (DAAF_NESTED)

When one script calls another, suppress interactive features (like pause-before-exit) in the inner script:

```bash
# In the outer script:
export DAAF_NESTED=1
bash ./inner_script.sh
unset DAAF_NESTED

# In the inner script:
if [ "${DAAF_NESTED:-}" = "1" ]; then
    exit "$exit_code"
fi
# ... interactive pause logic ...
```

---

## Script Structure

Organize scripts with clear section headers:

```bash
#!/usr/bin/env bash
set -euo pipefail

# --- Config ---
readonly BASE_DIR="/daaf"
readonly MAX_RETRIES=3

# --- Functions ---
# (Keep minimal — prefer inline logic for simple scripts)

# --- Preflight ---
command -v docker >/dev/null 2>&1 || { echo "ERROR: docker not found" >&2; exit 1; }

# --- Main ---
echo "[1/3] Starting operation..."
# ...
echo "[2/3] Processing..."
# ...
echo "[3/3] Finalizing..."

echo "Done."
```

### Progress Indicators

Use numbered steps for multi-step scripts so the user can track progress:

```bash
echo "[1/4] Checking prerequisites..."
echo "[2/4] Backing up current state..."
echo "[3/4] Applying changes..."
echo "[4/4] Verifying results..."
```

---

## Host-Script Portability (Bash 3.2 + BSD userland)

There are two Bash worlds in DAAF, and they have different portability rules:

- **In-container scripts** (`.claude/hooks/`, `scripts/` root utilities, anything run inside the Docker image) execute under the Bash and GNU coreutils installed by the Dockerfile — a modern, known environment. Write for that environment; do not assume anything the Dockerfile does not install.
- **Host scripts** (`scripts/host/*.sh`, and anything documented to run on the user's own machine) execute on *the user's* shell, which you do not control. These must target **Bash 3.2 + BSD userland**.

### Why Bash 3.2 for host scripts

macOS still ships **Bash 3.2.57** at `/bin/bash` and always will: Bash 4.0+ is GPLv3, which Apple declines to bundle, so the system bash has been frozen at the last GPLv2 release for over a decade. Users who follow DAAF's documented launch command (`bash daaf.sh`) get `/bin/bash` — 3.2 — unless they have separately installed a newer bash via Homebrew, which we cannot assume. Requiring Homebrew bash would be a real adoption barrier and a support burden, so the correct fix is to make host scripts run on 3.2, not to document a workaround.

This bit us concretely: a review change once "cleaned up" backup-directory parsing into a glob array and used `${backup_dirs[-1]}` to grab the newest entry. Negative array subscripts are a Bash 4.3 feature; on 3.2 the expansion fails with `bad array subscript`, and because the script ran `set -euo pipefail`, the whole Control Panel crashed on every startup once a backup existed. ShellCheck passed (it has no version pin and does not warn on `arr[-1]`), and `bash -n` passed (it is a runtime expansion error, not a parse error) — so *nothing caught it statically*. The lesson: 4.x-isms are invisible to the usual linters and must be banned explicitly and exercised under a real 3.2 interpreter in CI.

### Banned constructs in host scripts

| Construct | Introduced | 3.2-safe alternative |
|-----------|-----------|----------------------|
| `${arr[-1]}` (negative subscript) | 4.3 | `${arr[${#arr[@]}-1]}` (arithmetic subscripts work in 3.2) |
| `declare -A` (associative arrays) | 4.0 | Parallel indexed arrays, or a `case` lookup |
| `mapfile` / `readarray` | 4.0 | `while IFS= read -r line; do …; done < file` |
| `${var,,}` / `${var^^}` (case modification) | 4.0 | `tr '[:upper:]' '[:lower:]'` / `tr '[:lower:]' '[:upper:]'` |
| `&>>` (append both streams) | 4.0 | `>>file 2>&1` |
| `coproc` | 4.0 | Named pipe (`mkfifo`) or a temp file |

`&>foo` (truncating redirect of both streams) *is* valid in 3.2 and is not banned; only the appending `&>>` form is 4.0+. When in doubt, prefer the explicit `>file 2>&1` form, which reads identically on every version.

These bans are enforced by `tests/lint/check-daaf-conventions.sh` (a grep gate over `scripts/host/*.sh`) and exercised at runtime by the `bats-bash32` job in `ci-scripts.yml`, which runs the host scripts under the official `bash:3.2` image. See `./testing.md` for the CI layout.

### BSD vs GNU userland pitfalls

Host scripts also call external tools, and macOS ships **BSD** versions of them, not GNU. Flags that "always work" on Linux frequently differ or are absent on BSD. The common traps:

| GNU (Linux) idiom | Breaks on BSD/macOS because | Portable alternative |
|-------------------|------------------------------|----------------------|
| `sed -i 's/a/b/' f` | BSD `sed -i` requires a backup-suffix argument (`sed -i '' …`) | Write to a temp file and `mv`, or `sed -i.bak` then remove `.bak` |
| `date -d '2 days ago'` | BSD `date` has no `-d`; it uses `-v` | Compute in the shell, or require GNU `date` explicitly (avoid on host) |
| `stat -c '%s' f` | BSD `stat` uses `-f '%z'`, different format codes | `wc -c <f` for size; avoid `stat` format strings on host |
| `readlink -f path` | BSD `readlink` has no `-f` | `cd "$(dirname "$path")" && pwd -P` pattern |
| `grep -P` (PCRE) | BSD `grep` has no `-P` | `grep -E` (ERE) with a portable pattern |

Prefer POSIX-defined tools and flags for host scripts. When a task genuinely needs GNU behavior, do it *inside the container* (where GNU coreutils are installed) via `docker compose exec` rather than on the host.

### In-container commands: only what the Dockerfile installs

A related failure mode is the mirror image of the version problem: assuming a binary exists in the container when the image never installed it. A host script once probed container ports with `ss -tlnp`, but `iproute2` is not in the Dockerfile, so `ss` did not exist and every probe silently failed (stderr was discarded), making the status dashboard and service-stop logic misreport. The container-side scripts had already solved the same problem with `/proc/net/tcp` parsing — no extra binary needed.

The rule: **a command you run inside the container must be part of the Dockerfile's installed set** (or the base image's guaranteed contents). Before adding a new in-container command to a host or container script, confirm it is installed; if it is not, either add it to the Dockerfile deliberately (a rebuild-gated change) or use a mechanism that is already present. Suppressing the command's stderr (`2>/dev/null`) turns a missing-binary error into a silent wrong answer — validate the dependency instead.

---

## Compliance Checklist

Use this checklist when writing or reviewing any Bash script:

| # | Item | Check |
|---|------|-------|
| 1 | Shebang is `#!/usr/bin/env bash` | First line |
| 2 | `set -euo pipefail` (add `-E` if using ERR trap in functions) | Second line |
| 3 | All variables double-quoted | No bare `$var` |
| 4 | `local` declarations separate from `$(cmd)` assignments | No `local x=$(cmd)` |
| 5 | No `eval`, no backticks, no `ls` parsing | `grep -n 'eval\|` `` ` `` |
| 6 | `trap cleanup EXIT` for any temp files or state | After variable block |
| 7 | Cleanup function is idempotent | Uses `rm -f`, `|| true` |
| 8 | ShellCheck passes with `-x -S warning` | `shellcheck -x -S warning script.sh` |
| 9 | Errors go to stderr with actionable guidance | `echo "ERROR: ..." >&2` (or `error()` helper — see `error-handling.md`) |
| 10 | Positional arguments validated with usage message | `if [ $# -lt N ]; then` |
| 11 | External dependencies checked at script start | `command -v tool` block |
| 12 | Progress steps use `[N/M]` format | Visual scan |
| 13 | Host scripts (`scripts/host/*.sh`) avoid Bash-4.x-only constructs and BSD-incompatible flags | See "Host-Script Portability" above; enforced by `check-daaf-conventions.sh` + `bats-bash32` CI job |
| 14 | In-container commands are part of the Dockerfile's installed set | No probing with un-installed binaries (e.g. `ss`); validate, don't suppress |
| 15 | Host scripts (`scripts/host/*.sh`) never pipe a live producer into `grep -q` (SIGPIPE/pipefail inversion) | Sanctioned idiom is capture-then-grep the value first; enforced by `check-daaf-conventions.sh` section 9 |
